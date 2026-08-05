#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <dxcapi.h>
#include <wincodec.h>
#include <wrl/client.h>
#include <DirectXMath.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;
namespace fs = std::filesystem;

namespace
{
constexpr float kPi = 3.14159265358979323846f;

void check(HRESULT hr, const char* message)
{
    if (FAILED(hr))
    {
        std::ostringstream stream;
        stream << message << " (HRESULT 0x" << std::hex << static_cast<unsigned long>(hr) << ")";
        throw std::runtime_error(stream.str());
    }
}

std::string utf8(const std::wstring& value)
{
    if (value.empty()) return {};
    const int count = WideCharToMultiByte(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    std::string result(static_cast<size_t>(count), '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), result.data(), count, nullptr, nullptr);
    return result;
}

std::wstring wide(const std::string& value)
{
    if (value.empty()) return {};
    const int count = MultiByteToWideChar(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), nullptr, 0);
    std::wstring result(static_cast<size_t>(count), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), result.data(), count);
    return result;
}

std::string json_escape(const std::string& value)
{
    std::string out;
    out.reserve(value.size() + 8);
    for (const char c : value)
    {
        switch (c)
        {
        case '\\': out += "\\\\"; break;
        case '"': out += "\\\""; break;
        case '\n': out += "\\n"; break;
        case '\r': out += "\\r"; break;
        case '\t': out += "\\t"; break;
        default: out += c; break;
        }
    }
    return out;
}

D3D12_HEAP_PROPERTIES heap_properties(D3D12_HEAP_TYPE type)
{
    D3D12_HEAP_PROPERTIES props{};
    props.Type = type;
    props.CPUPageProperty = D3D12_CPU_PAGE_PROPERTY_UNKNOWN;
    props.MemoryPoolPreference = D3D12_MEMORY_POOL_UNKNOWN;
    props.CreationNodeMask = 1;
    props.VisibleNodeMask = 1;
    return props;
}

D3D12_RESOURCE_DESC buffer_desc(UINT64 size, D3D12_RESOURCE_FLAGS flags = D3D12_RESOURCE_FLAG_NONE)
{
    D3D12_RESOURCE_DESC desc{};
    desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    desc.Alignment = 0;
    desc.Width = size;
    desc.Height = 1;
    desc.DepthOrArraySize = 1;
    desc.MipLevels = 1;
    desc.Format = DXGI_FORMAT_UNKNOWN;
    desc.SampleDesc = {1, 0};
    desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    desc.Flags = flags;
    return desc;
}

D3D12_RESOURCE_BARRIER transition(ID3D12Resource* resource, D3D12_RESOURCE_STATES before, D3D12_RESOURCE_STATES after)
{
    D3D12_RESOURCE_BARRIER barrier{};
    barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition.pResource = resource;
    barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barrier.Transition.StateBefore = before;
    barrier.Transition.StateAfter = after;
    return barrier;
}

D3D12_RESOURCE_BARRIER uav_barrier(ID3D12Resource* resource)
{
    D3D12_RESOURCE_BARRIER barrier{};
    barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
    barrier.UAV.pResource = resource;
    return barrier;
}

struct Options
{
    bool capabilities = false;
    bool render = false;
    fs::path output;
    fs::path shader;
    fs::path vertices;
    fs::path environment;
    UINT environment_width = 0;
    UINT environment_height = 0;
    float environment_rotation = 0.0f;
    UINT width = 640;
    UINT height = 480;
    UINT samples = 1;
    UINT bounces = 3;
    bool path_traced = false;
    bool camera_visible = true;
    bool reflection_visible = true;
};

Options parse_options(int argc, wchar_t** argv)
{
    Options options;
    for (int i = 1; i < argc; ++i)
    {
        const std::wstring arg = argv[i];
        auto next = [&]() -> std::wstring {
            if (++i >= argc) throw std::runtime_error("missing value for command-line option");
            return argv[i];
        };
        if (arg == L"--capabilities-json") options.capabilities = true;
        else if (arg == L"--render" || arg == L"--render-proof") options.render = true;
        else if (arg == L"--output") options.output = next();
        else if (arg == L"--shader") options.shader = next();
        else if (arg == L"--vertices") options.vertices = next();
        else if (arg == L"--environment") options.environment = next();
        else if (arg == L"--environment-width") options.environment_width = static_cast<UINT>(std::stoul(next()));
        else if (arg == L"--environment-height") options.environment_height = static_cast<UINT>(std::stoul(next()));
        else if (arg == L"--environment-rotation") options.environment_rotation = std::stof(next());
        else if (arg == L"--width") options.width = static_cast<UINT>(std::stoul(next()));
        else if (arg == L"--height") options.height = static_cast<UINT>(std::stoul(next()));
        else if (arg == L"--samples") options.samples = static_cast<UINT>(std::stoul(next()));
        else if (arg == L"--bounces") options.bounces = static_cast<UINT>(std::stoul(next()));
        else if (arg == L"--mode") options.path_traced = next() == L"path_traced";
        else if (arg == L"--camera-visible") options.camera_visible = std::stoi(next()) != 0;
        else if (arg == L"--reflection-visible") options.reflection_visible = std::stoi(next()) != 0;
    }
    options.width = std::clamp(options.width, 16u, 4096u);
    options.height = std::clamp(options.height, 16u, 4096u);
    options.samples = std::clamp(options.samples, 1u, 256u);
    options.bounces = std::clamp(options.bounces, 1u, 8u);
    return options;
}

struct DeviceContext
{
    ComPtr<IDXGIAdapter1> adapter;
    ComPtr<ID3D12Device5> device;
    std::string name;
    D3D12_RAYTRACING_TIER tier = D3D12_RAYTRACING_TIER_NOT_SUPPORTED;
    bool shader_model_65 = false;
};

DeviceContext create_device()
{
    DeviceContext context;
    if (GetEnvironmentVariableW(L"TIGERSTUDIO_DXR_DEBUG", nullptr, 0) > 0)
    {
        ComPtr<ID3D12Debug> debug;
        if (SUCCEEDED(D3D12GetDebugInterface(IID_PPV_ARGS(&debug))))
            debug->EnableDebugLayer();
    }
    ComPtr<IDXGIFactory6> factory;
    check(CreateDXGIFactory2(0, IID_PPV_ARGS(&factory)), "CreateDXGIFactory2 failed");
    for (UINT index = 0;; ++index)
    {
        ComPtr<IDXGIAdapter1> adapter;
        if (factory->EnumAdapterByGpuPreference(index, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE, IID_PPV_ARGS(&adapter)) == DXGI_ERROR_NOT_FOUND)
            break;
        DXGI_ADAPTER_DESC1 desc{};
        adapter->GetDesc1(&desc);
        if ((desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) != 0) continue;
        ComPtr<ID3D12Device5> device;
        if (SUCCEEDED(D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_12_0, IID_PPV_ARGS(&device))))
        {
            D3D12_FEATURE_DATA_D3D12_OPTIONS5 options5{};
            if (FAILED(device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS5, &options5, sizeof(options5))))
                options5.RaytracingTier = D3D12_RAYTRACING_TIER_NOT_SUPPORTED;
            D3D12_FEATURE_DATA_SHADER_MODEL shader_model{D3D_SHADER_MODEL_6_5};
            const bool sm65 = SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_SHADER_MODEL, &shader_model, sizeof(shader_model)))
                && shader_model.HighestShaderModel >= D3D_SHADER_MODEL_6_5;
            if (!context.device || options5.RaytracingTier > context.tier)
            {
                context.adapter = adapter;
                context.device = device;
                context.name = utf8(desc.Description);
                context.tier = options5.RaytracingTier;
                context.shader_model_65 = sm65;
            }
        }
    }
    if (!context.device) throw std::runtime_error("no Direct3D 12 hardware adapter found");
    return context;
}

std::string device_messages(ID3D12Device* device)
{
    ComPtr<ID3D12InfoQueue> queue;
    if (FAILED(device->QueryInterface(IID_PPV_ARGS(&queue)))) return {};
    std::ostringstream stream;
    const UINT64 count = queue->GetNumStoredMessagesAllowedByRetrievalFilter();
    for (UINT64 index = 0; index < count; ++index)
    {
        SIZE_T size = 0;
        queue->GetMessage(index, nullptr, &size);
        std::vector<BYTE> storage(size);
        auto* message = reinterpret_cast<D3D12_MESSAGE*>(storage.data());
        if (SUCCEEDED(queue->GetMessage(index, message, &size)) && message->pDescription)
            stream << message->pDescription << " | ";
    }
    return stream.str();
}

std::string tier_name(D3D12_RAYTRACING_TIER tier)
{
    if (tier >= D3D12_RAYTRACING_TIER_1_1) return "1.1";
    if (tier >= D3D12_RAYTRACING_TIER_1_0) return "1.0";
    return "none";
}

void print_capabilities(const DeviceContext& context)
{
    const bool available = context.tier >= D3D12_RAYTRACING_TIER_1_1 && context.shader_model_65;
    std::cout
        << "{\"schema\":\"tigerstudio.ar_pbr.hardware_rt_helper.v1\""
        << ",\"hardware_ray_tracing\":" << (available ? "true" : "false")
        << ",\"api\":\"dxr\""
        << ",\"device\":\"" << json_escape(context.name) << "\""
        << ",\"raytracing_tier\":\"" << tier_name(context.tier) << "\""
        << ",\"shader_model_6_5\":" << (context.shader_model_65 ? "true" : "false")
        << ",\"renderer\":\"d3d12_inline_ray_query\""
        << ",\"process_isolated\":true}"
        << std::endl;
}

struct Vertex
{
    DirectX::XMFLOAT3 position;
    DirectX::XMFLOAT3 normal;
    DirectX::XMFLOAT3 albedo;
    float metallic;
    float roughness;
};
static_assert(sizeof(Vertex) == 44, "Vertex layout must match HLSL");

void add_triangle(std::vector<Vertex>& vertices,
                  DirectX::XMFLOAT3 a, DirectX::XMFLOAT3 b, DirectX::XMFLOAT3 c,
                  DirectX::XMFLOAT3 na, DirectX::XMFLOAT3 nb, DirectX::XMFLOAT3 nc,
                  DirectX::XMFLOAT3 color, float metallic, float roughness)
{
    vertices.push_back({a, na, color, metallic, roughness});
    vertices.push_back({b, nb, color, metallic, roughness});
    vertices.push_back({c, nc, color, metallic, roughness});
}

DirectX::XMFLOAT3 sphere_point(DirectX::XMFLOAT3 center, float radius, float theta, float phi)
{
    return {center.x + radius * std::sin(theta) * std::cos(phi),
            center.y + radius * std::cos(theta),
            center.z + radius * std::sin(theta) * std::sin(phi)};
}

DirectX::XMFLOAT3 sphere_normal(float theta, float phi)
{
    return {std::sin(theta) * std::cos(phi), std::cos(theta), std::sin(theta) * std::sin(phi)};
}

void add_sphere(std::vector<Vertex>& vertices, DirectX::XMFLOAT3 center, float radius,
                DirectX::XMFLOAT3 color, float metallic, float roughness)
{
    constexpr int latitudes = 20;
    constexpr int longitudes = 32;
    for (int y = 0; y < latitudes; ++y)
    {
        const float t0 = kPi * static_cast<float>(y) / latitudes;
        const float t1 = kPi * static_cast<float>(y + 1) / latitudes;
        for (int x = 0; x < longitudes; ++x)
        {
            const float p0 = 2.0f * kPi * static_cast<float>(x) / longitudes;
            const float p1 = 2.0f * kPi * static_cast<float>(x + 1) / longitudes;
            const auto a = sphere_point(center, radius, t0, p0);
            const auto b = sphere_point(center, radius, t1, p0);
            const auto c = sphere_point(center, radius, t1, p1);
            const auto d = sphere_point(center, radius, t0, p1);
            const auto na = sphere_normal(t0, p0);
            const auto nb = sphere_normal(t1, p0);
            const auto nc = sphere_normal(t1, p1);
            const auto nd = sphere_normal(t0, p1);
            if (y > 0) add_triangle(vertices, a, b, d, na, nb, nd, color, metallic, roughness);
            if (y + 1 < latitudes) add_triangle(vertices, d, b, c, nd, nb, nc, color, metallic, roughness);
        }
    }
}

std::vector<Vertex> make_scene()
{
    std::vector<Vertex> vertices;
    const DirectX::XMFLOAT3 up{0, 1, 0};
    const DirectX::XMFLOAT3 ground{0.42f, 0.38f, 0.33f};
    add_triangle(vertices, {-4, 0, -3}, {-4, 0, 4}, {4, 0, -3}, up, up, up, ground, 0.0f, 0.72f);
    add_triangle(vertices, {4, 0, -3}, {-4, 0, 4}, {4, 0, 4}, up, up, up, ground, 0.0f, 0.72f);
    add_sphere(vertices, {-0.82f, 0.82f, 0.15f}, 0.82f, {0.86f, 0.17f, 0.055f}, 0.0f, 0.30f);
    add_sphere(vertices, {0.92f, 0.70f, 0.55f}, 0.70f, {0.72f, 0.76f, 0.82f}, 1.0f, 0.11f);
    const DirectX::XMFLOAT3 wall_normal{0, 0, -1};
    const DirectX::XMFLOAT3 wall_color{0.08f, 0.36f, 0.62f};
    add_triangle(vertices, {-2.2f, 0.0f, 2.2f}, {2.2f, 0.0f, 2.2f}, {-2.2f, 3.0f, 2.2f}, wall_normal, wall_normal, wall_normal, wall_color, 0.0f, 0.42f);
    add_triangle(vertices, {-2.2f, 3.0f, 2.2f}, {2.2f, 0.0f, 2.2f}, {2.2f, 3.0f, 2.2f}, wall_normal, wall_normal, wall_normal, wall_color, 0.0f, 0.42f);
    return vertices;
}

std::vector<Vertex> load_scene_vertices(const fs::path& path)
{
    if (path.empty()) return make_scene();
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) throw std::runtime_error("vertex scene could not be opened");
    const auto byte_count = stream.tellg();
    if (byte_count <= 0 || byte_count % static_cast<std::streamoff>(sizeof(Vertex)) != 0)
        throw std::runtime_error("vertex scene has an invalid byte length");
    const size_t count = static_cast<size_t>(byte_count / static_cast<std::streamoff>(sizeof(Vertex)));
    if (count < 3 || count % 3 != 0)
        throw std::runtime_error("vertex scene must contain non-indexed triangles");
    std::vector<Vertex> vertices(count);
    stream.seekg(0, std::ios::beg);
    stream.read(reinterpret_cast<char*>(vertices.data()), byte_count);
    if (!stream) throw std::runtime_error("vertex scene read failed");
    return vertices;
}

std::vector<float> load_environment_pixels(const Options& options)
{
    if (options.environment.empty()) return {0.0f, 0.0f, 0.0f, 1.0f};
    if (options.environment_width == 0 || options.environment_height == 0)
        throw std::runtime_error("environment width and height are required");
    const UINT64 float_count = static_cast<UINT64>(options.environment_width) * options.environment_height * 4;
    std::ifstream stream(options.environment, std::ios::binary | std::ios::ate);
    if (!stream) throw std::runtime_error("environment float texture could not be opened");
    const auto byte_count = stream.tellg();
    if (byte_count != static_cast<std::streamoff>(float_count * sizeof(float)))
        throw std::runtime_error("environment float texture byte length does not match its dimensions");
    std::vector<float> pixels(static_cast<size_t>(float_count));
    stream.seekg(0, std::ios::beg);
    stream.read(reinterpret_cast<char*>(pixels.data()), byte_count);
    if (!stream) throw std::runtime_error("environment float texture read failed");
    return pixels;
}

ComPtr<ID3D12Resource> create_buffer(ID3D12Device* device, UINT64 size, D3D12_HEAP_TYPE heap,
                                     D3D12_RESOURCE_STATES state, D3D12_RESOURCE_FLAGS flags = D3D12_RESOURCE_FLAG_NONE)
{
    ComPtr<ID3D12Resource> resource;
    const auto props = heap_properties(heap);
    const auto desc = buffer_desc(size, flags);
    check(device->CreateCommittedResource(&props, D3D12_HEAP_FLAG_NONE, &desc, state, nullptr, IID_PPV_ARGS(&resource)),
          "CreateCommittedResource buffer failed");
    return resource;
}

template <typename T>
ComPtr<ID3D12Resource> create_upload(ID3D12Device* device, const std::vector<T>& data)
{
    const UINT64 size = static_cast<UINT64>(data.size()) * sizeof(T);
    auto resource = create_buffer(device, size, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    void* mapped = nullptr;
    D3D12_RANGE no_read{0, 0};
    check(resource->Map(0, &no_read, &mapped), "Map upload buffer failed");
    std::memcpy(mapped, data.data(), static_cast<size_t>(size));
    resource->Unmap(0, nullptr);
    return resource;
}

ComPtr<IDxcBlob> compile_shader(const fs::path& path)
{
    ComPtr<IDxcUtils> utils;
    ComPtr<IDxcCompiler3> compiler;
    check(DxcCreateInstance(CLSID_DxcUtils, IID_PPV_ARGS(&utils)), "DxcCreateInstance utils failed");
    check(DxcCreateInstance(CLSID_DxcCompiler, IID_PPV_ARGS(&compiler)), "DxcCreateInstance compiler failed");
    ComPtr<IDxcBlobEncoding> source;
    check(utils->LoadFile(path.c_str(), nullptr, &source), "DXC could not load Raytrace.hlsl");
    DxcBuffer buffer{source->GetBufferPointer(), source->GetBufferSize(), DXC_CP_UTF8};
    std::array<LPCWSTR, 10> args = {
        L"Raytrace.hlsl", L"-E", L"main", L"-T", L"cs_6_5",
        L"-O3", L"-HV", L"2021", L"-Qstrip_debug", L"-Qstrip_reflect"};
    ComPtr<IDxcResult> result;
    check(compiler->Compile(&buffer, args.data(), static_cast<UINT32>(args.size()), nullptr, IID_PPV_ARGS(&result)),
          "DXC Compile call failed");
    HRESULT status = E_FAIL;
    result->GetStatus(&status);
    if (FAILED(status))
    {
        ComPtr<IDxcBlobUtf8> errors;
        result->GetOutput(DXC_OUT_ERRORS, IID_PPV_ARGS(&errors), nullptr);
        throw std::runtime_error(errors && errors->GetStringLength() ? errors->GetStringPointer() : "HLSL compilation failed");
    }
    ComPtr<IDxcBlob> object;
    check(result->GetOutput(DXC_OUT_OBJECT, IID_PPV_ARGS(&object), nullptr), "DXC object output missing");
    return object;
}

struct alignas(256) Params
{
    DirectX::XMFLOAT4 camera_position;
    DirectX::XMFLOAT4 camera_forward;
    DirectX::XMFLOAT4 camera_right;
    DirectX::XMFLOAT4 camera_up;
    DirectX::XMFLOAT4 light_position_intensity;
    UINT width;
    UINT height;
    UINT samples;
    UINT max_bounces;
    UINT camera_visible;
    UINT reflection_visible;
    UINT path_traced;
    UINT frame_seed;
    UINT environment_width;
    UINT environment_height;
    UINT use_environment;
    float environment_rotation;
};

void save_png(const fs::path& path, UINT width, UINT height, UINT row_pitch, const BYTE* pixels)
{
    fs::create_directories(path.parent_path());
    ComPtr<IWICImagingFactory> factory;
    check(CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&factory)), "WIC factory failed");
    ComPtr<IWICStream> stream;
    check(factory->CreateStream(&stream), "WIC stream failed");
    check(stream->InitializeFromFilename(path.c_str(), GENERIC_WRITE), "WIC output open failed");
    ComPtr<IWICBitmapEncoder> encoder;
    check(factory->CreateEncoder(GUID_ContainerFormatPng, nullptr, &encoder), "WIC PNG encoder failed");
    check(encoder->Initialize(stream.Get(), WICBitmapEncoderNoCache), "WIC encoder init failed");
    ComPtr<IWICBitmapFrameEncode> frame;
    ComPtr<IPropertyBag2> properties;
    check(encoder->CreateNewFrame(&frame, &properties), "WIC frame create failed");
    check(frame->Initialize(properties.Get()), "WIC frame init failed");
    check(frame->SetSize(width, height), "WIC frame size failed");
    WICPixelFormatGUID format = GUID_WICPixelFormat32bppRGBA;
    check(frame->SetPixelFormat(&format), "WIC pixel format failed");
    check(frame->WritePixels(height, row_pitch, row_pitch * height, const_cast<BYTE*>(pixels)), "WIC WritePixels failed");
    check(frame->Commit(), "WIC frame commit failed");
    check(encoder->Commit(), "WIC encoder commit failed");
}

void wait_for_gpu(ID3D12CommandQueue* queue, ID3D12Fence* fence, UINT64 value, HANDLE event_handle)
{
    check(queue->Signal(fence, value), "queue signal failed");
    if (fence->GetCompletedValue() < value)
    {
        check(fence->SetEventOnCompletion(value, event_handle), "fence event failed");
        WaitForSingleObject(event_handle, INFINITE);
    }
}

void render(const DeviceContext& context, const Options& options)
{
    if (context.tier < D3D12_RAYTRACING_TIER_1_1 || !context.shader_model_65)
        throw std::runtime_error("DXR Tier 1.1 and Shader Model 6.5 are required for inline RayQuery rendering");
    auto* device = context.device.Get();
    D3D12_COMMAND_QUEUE_DESC queue_desc{};
    queue_desc.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
    ComPtr<ID3D12CommandQueue> queue;
    check(device->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&queue)), "command queue failed");
    ComPtr<ID3D12CommandAllocator> allocator;
    check(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&allocator)), "command allocator failed");
    ComPtr<ID3D12GraphicsCommandList4> command_list;
    check(device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator.Get(), nullptr, IID_PPV_ARGS(&command_list)),
          "command list failed");

    const auto vertices = load_scene_vertices(options.vertices);
    auto vertex_buffer = create_upload(device, vertices);
    const auto environment_pixels = load_environment_pixels(options);

    D3D12_RAYTRACING_GEOMETRY_DESC geometry{};
    geometry.Type = D3D12_RAYTRACING_GEOMETRY_TYPE_TRIANGLES;
    geometry.Flags = D3D12_RAYTRACING_GEOMETRY_FLAG_OPAQUE;
    geometry.Triangles.VertexBuffer.StartAddress = vertex_buffer->GetGPUVirtualAddress();
    geometry.Triangles.VertexBuffer.StrideInBytes = sizeof(Vertex);
    geometry.Triangles.VertexCount = static_cast<UINT>(vertices.size());
    geometry.Triangles.VertexFormat = DXGI_FORMAT_R32G32B32_FLOAT;

    D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_INPUTS blas_inputs{};
    blas_inputs.Type = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_BOTTOM_LEVEL;
    blas_inputs.DescsLayout = D3D12_ELEMENTS_LAYOUT_ARRAY;
    blas_inputs.Flags = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BUILD_FLAG_PREFER_FAST_TRACE;
    blas_inputs.NumDescs = 1;
    blas_inputs.pGeometryDescs = &geometry;
    D3D12_RAYTRACING_ACCELERATION_STRUCTURE_PREBUILD_INFO blas_info{};
    device->GetRaytracingAccelerationStructurePrebuildInfo(&blas_inputs, &blas_info);
    auto blas_scratch = create_buffer(device, blas_info.ScratchDataSizeInBytes, D3D12_HEAP_TYPE_DEFAULT,
                                      D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    auto blas = create_buffer(device, blas_info.ResultDataMaxSizeInBytes, D3D12_HEAP_TYPE_DEFAULT,
                              D3D12_RESOURCE_STATE_RAYTRACING_ACCELERATION_STRUCTURE,
                              D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_DESC blas_build{};
    blas_build.Inputs = blas_inputs;
    blas_build.ScratchAccelerationStructureData = blas_scratch->GetGPUVirtualAddress();
    blas_build.DestAccelerationStructureData = blas->GetGPUVirtualAddress();
    command_list->BuildRaytracingAccelerationStructure(&blas_build, 0, nullptr);
    auto blas_uav = uav_barrier(blas.Get());
    command_list->ResourceBarrier(1, &blas_uav);

    D3D12_RAYTRACING_INSTANCE_DESC instance{};
    instance.Transform[0][0] = 1.0f;
    instance.Transform[1][1] = 1.0f;
    instance.Transform[2][2] = 1.0f;
    instance.InstanceMask = 0xff;
    instance.AccelerationStructure = blas->GetGPUVirtualAddress();
    std::vector<D3D12_RAYTRACING_INSTANCE_DESC> instances{instance};
    auto instance_buffer = create_upload(device, instances);
    D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_INPUTS tlas_inputs{};
    tlas_inputs.Type = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_TOP_LEVEL;
    tlas_inputs.DescsLayout = D3D12_ELEMENTS_LAYOUT_ARRAY;
    tlas_inputs.Flags = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BUILD_FLAG_PREFER_FAST_TRACE;
    tlas_inputs.NumDescs = 1;
    tlas_inputs.InstanceDescs = instance_buffer->GetGPUVirtualAddress();
    D3D12_RAYTRACING_ACCELERATION_STRUCTURE_PREBUILD_INFO tlas_info{};
    device->GetRaytracingAccelerationStructurePrebuildInfo(&tlas_inputs, &tlas_info);
    auto tlas_scratch = create_buffer(device, tlas_info.ScratchDataSizeInBytes, D3D12_HEAP_TYPE_DEFAULT,
                                      D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    auto tlas = create_buffer(device, tlas_info.ResultDataMaxSizeInBytes, D3D12_HEAP_TYPE_DEFAULT,
                              D3D12_RESOURCE_STATE_RAYTRACING_ACCELERATION_STRUCTURE,
                              D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_DESC tlas_build{};
    tlas_build.Inputs = tlas_inputs;
    tlas_build.ScratchAccelerationStructureData = tlas_scratch->GetGPUVirtualAddress();
    tlas_build.DestAccelerationStructureData = tlas->GetGPUVirtualAddress();
    command_list->BuildRaytracingAccelerationStructure(&tlas_build, 0, nullptr);
    auto tlas_uav = uav_barrier(tlas.Get());
    command_list->ResourceBarrier(1, &tlas_uav);

    const UINT environment_width = options.environment.empty() ? 1u : options.environment_width;
    const UINT environment_height = options.environment.empty() ? 1u : options.environment_height;
    D3D12_RESOURCE_DESC environment_desc{};
    environment_desc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    environment_desc.Width = environment_width;
    environment_desc.Height = environment_height;
    environment_desc.DepthOrArraySize = 1;
    environment_desc.MipLevels = 1;
    environment_desc.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
    environment_desc.SampleDesc = {1, 0};
    environment_desc.Layout = D3D12_TEXTURE_LAYOUT_UNKNOWN;
    ComPtr<ID3D12Resource> environment_texture;
    const auto default_props = heap_properties(D3D12_HEAP_TYPE_DEFAULT);
    check(device->CreateCommittedResource(&default_props, D3D12_HEAP_FLAG_NONE, &environment_desc,
                                          D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(&environment_texture)),
          "environment texture failed");
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT environment_footprint{};
    UINT environment_rows = 0;
    UINT64 environment_row_size = 0;
    UINT64 environment_upload_size = 0;
    device->GetCopyableFootprints(
        &environment_desc, 0, 1, 0, &environment_footprint, &environment_rows,
        &environment_row_size, &environment_upload_size);
    auto environment_upload = create_buffer(
        device, environment_upload_size, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    void* environment_mapped = nullptr;
    D3D12_RANGE environment_no_read{0, 0};
    check(environment_upload->Map(0, &environment_no_read, &environment_mapped), "environment upload map failed");
    const UINT source_row_bytes = environment_width * 4 * sizeof(float);
    for (UINT row = 0; row < environment_height; ++row)
    {
        std::memcpy(
            static_cast<BYTE*>(environment_mapped) + environment_footprint.Offset
                + static_cast<size_t>(row) * environment_footprint.Footprint.RowPitch,
            reinterpret_cast<const BYTE*>(environment_pixels.data()) + static_cast<size_t>(row) * source_row_bytes,
            source_row_bytes);
    }
    environment_upload->Unmap(0, nullptr);
    D3D12_TEXTURE_COPY_LOCATION environment_src{};
    environment_src.pResource = environment_upload.Get();
    environment_src.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    environment_src.PlacedFootprint = environment_footprint;
    D3D12_TEXTURE_COPY_LOCATION environment_dst{};
    environment_dst.pResource = environment_texture.Get();
    environment_dst.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    command_list->CopyTextureRegion(&environment_dst, 0, 0, 0, &environment_src, nullptr);
    auto environment_transition = transition(
        environment_texture.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
    command_list->ResourceBarrier(1, &environment_transition);

    D3D12_RESOURCE_DESC output_desc{};
    output_desc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    output_desc.Width = options.width;
    output_desc.Height = options.height;
    output_desc.DepthOrArraySize = 1;
    output_desc.MipLevels = 1;
    output_desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    output_desc.SampleDesc = {1, 0};
    output_desc.Layout = D3D12_TEXTURE_LAYOUT_UNKNOWN;
    output_desc.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
    ComPtr<ID3D12Resource> output;
    check(device->CreateCommittedResource(&default_props, D3D12_HEAP_FLAG_NONE, &output_desc,
                                          D3D12_RESOURCE_STATE_UNORDERED_ACCESS, nullptr, IID_PPV_ARGS(&output)),
          "output texture failed");

    D3D12_DESCRIPTOR_HEAP_DESC heap_desc{};
    heap_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    heap_desc.NumDescriptors = 2;
    heap_desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    ComPtr<ID3D12DescriptorHeap> descriptor_heap;
    check(device->CreateDescriptorHeap(&heap_desc, IID_PPV_ARGS(&descriptor_heap)), "descriptor heap failed");
    D3D12_UNORDERED_ACCESS_VIEW_DESC uav_desc{};
    uav_desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    uav_desc.ViewDimension = D3D12_UAV_DIMENSION_TEXTURE2D;
    device->CreateUnorderedAccessView(output.Get(), nullptr, &uav_desc, descriptor_heap->GetCPUDescriptorHandleForHeapStart());
    const UINT descriptor_size = device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
    D3D12_CPU_DESCRIPTOR_HANDLE environment_handle = descriptor_heap->GetCPUDescriptorHandleForHeapStart();
    environment_handle.ptr += descriptor_size;
    D3D12_SHADER_RESOURCE_VIEW_DESC environment_srv{};
    environment_srv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
    environment_srv.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
    environment_srv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
    environment_srv.Texture2D.MipLevels = 1;
    device->CreateShaderResourceView(environment_texture.Get(), &environment_srv, environment_handle);

    std::array<D3D12_DESCRIPTOR_RANGE, 2> resource_ranges{};
    resource_ranges[0].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_UAV;
    resource_ranges[0].NumDescriptors = 1;
    resource_ranges[0].BaseShaderRegister = 0;
    resource_ranges[0].OffsetInDescriptorsFromTableStart = 0;
    resource_ranges[1].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
    resource_ranges[1].NumDescriptors = 1;
    resource_ranges[1].BaseShaderRegister = 2;
    resource_ranges[1].OffsetInDescriptorsFromTableStart = 1;
    std::array<D3D12_ROOT_PARAMETER, 4> root_params{};
    root_params[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
    root_params[0].DescriptorTable.NumDescriptorRanges = static_cast<UINT>(resource_ranges.size());
    root_params[0].DescriptorTable.pDescriptorRanges = resource_ranges.data();
    root_params[0].ShaderVisibility = D3D12_SHADER_VISIBILITY_ALL;
    root_params[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_SRV;
    root_params[1].Descriptor.ShaderRegister = 0;
    root_params[1].ShaderVisibility = D3D12_SHADER_VISIBILITY_ALL;
    root_params[2].ParameterType = D3D12_ROOT_PARAMETER_TYPE_SRV;
    root_params[2].Descriptor.ShaderRegister = 1;
    root_params[2].ShaderVisibility = D3D12_SHADER_VISIBILITY_ALL;
    root_params[3].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
    root_params[3].Descriptor.ShaderRegister = 0;
    root_params[3].ShaderVisibility = D3D12_SHADER_VISIBILITY_ALL;
    D3D12_ROOT_SIGNATURE_DESC root_desc{};
    root_desc.NumParameters = static_cast<UINT>(root_params.size());
    root_desc.pParameters = root_params.data();
    ComPtr<ID3DBlob> root_blob;
    ComPtr<ID3DBlob> root_error;
    check(D3D12SerializeRootSignature(&root_desc, D3D_ROOT_SIGNATURE_VERSION_1, &root_blob, &root_error),
          root_error ? static_cast<const char*>(root_error->GetBufferPointer()) : "root signature serialization failed");
    ComPtr<ID3D12RootSignature> root_signature;
    check(device->CreateRootSignature(0, root_blob->GetBufferPointer(), root_blob->GetBufferSize(), IID_PPV_ARGS(&root_signature)),
          "root signature creation failed");
    auto shader = compile_shader(options.shader);
    D3D12_COMPUTE_PIPELINE_STATE_DESC pso_desc{};
    pso_desc.pRootSignature = root_signature.Get();
    pso_desc.CS = {shader->GetBufferPointer(), shader->GetBufferSize()};
    ComPtr<ID3D12PipelineState> pipeline;
    const HRESULT pipeline_result = device->CreateComputePipelineState(&pso_desc, IID_PPV_ARGS(&pipeline));
    if (FAILED(pipeline_result))
    {
        const std::string messages = device_messages(device);
        check(pipeline_result, (std::string("compute pipeline failed: ") + messages).c_str());
    }

    using namespace DirectX;
    const bool external_scene = !options.vertices.empty();
    const XMVECTOR eye = external_scene
        ? XMVectorSet(0.0f, 0.15f, -4.2f, 0.0f)
        : XMVectorSet(0.0f, 1.55f, -5.4f, 0.0f);
    const XMVECTOR target = external_scene
        ? XMVectorSet(0.0f, 0.0f, 0.0f, 0.0f)
        : XMVectorSet(0.0f, 0.85f, 0.4f, 0.0f);
    const XMVECTOR forward_v = XMVector3Normalize(target - eye);
    const XMVECTOR right_v = XMVector3Normalize(XMVector3Cross(XMVectorSet(0, 1, 0, 0), forward_v));
    const XMVECTOR up_v = XMVector3Normalize(XMVector3Cross(forward_v, right_v));
    Params params{};
    XMStoreFloat4(&params.camera_position, eye);
    XMStoreFloat4(&params.camera_forward, forward_v);
    XMStoreFloat4(&params.camera_right, right_v);
    XMStoreFloat4(&params.camera_up, up_v);
    params.light_position_intensity = {-2.4f, 4.2f, -2.5f, 34.0f};
    params.width = options.width;
    params.height = options.height;
    params.samples = options.path_traced ? options.samples : 1;
    params.max_bounces = options.path_traced ? options.bounces : 1;
    params.camera_visible = options.camera_visible ? 1u : 0u;
    params.reflection_visible = options.reflection_visible ? 1u : 0u;
    params.path_traced = options.path_traced ? 1u : 0u;
    params.frame_seed = 1337u;
    params.environment_width = environment_width;
    params.environment_height = environment_height;
    params.use_environment = options.environment.empty() ? 0u : 1u;
    params.environment_rotation = options.environment_rotation;
    std::vector<Params> params_data{params};
    auto constant_buffer = create_upload(device, params_data);

    command_list->SetComputeRootSignature(root_signature.Get());
    command_list->SetPipelineState(pipeline.Get());
    ID3D12DescriptorHeap* heaps[] = {descriptor_heap.Get()};
    command_list->SetDescriptorHeaps(1, heaps);
    command_list->SetComputeRootDescriptorTable(0, descriptor_heap->GetGPUDescriptorHandleForHeapStart());
    command_list->SetComputeRootShaderResourceView(1, tlas->GetGPUVirtualAddress());
    command_list->SetComputeRootShaderResourceView(2, vertex_buffer->GetGPUVirtualAddress());
    command_list->SetComputeRootConstantBufferView(3, constant_buffer->GetGPUVirtualAddress());
    command_list->Dispatch((options.width + 7) / 8, (options.height + 7) / 8, 1);
    auto output_to_copy = transition(output.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    command_list->ResourceBarrier(1, &output_to_copy);

    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    UINT rows = 0;
    UINT64 row_size = 0;
    UINT64 readback_size = 0;
    device->GetCopyableFootprints(&output_desc, 0, 1, 0, &footprint, &rows, &row_size, &readback_size);
    auto readback = create_buffer(device, readback_size, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    D3D12_TEXTURE_COPY_LOCATION src{};
    src.pResource = output.Get();
    src.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    src.SubresourceIndex = 0;
    D3D12_TEXTURE_COPY_LOCATION dst{};
    dst.pResource = readback.Get();
    dst.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    dst.PlacedFootprint = footprint;
    command_list->CopyTextureRegion(&dst, 0, 0, 0, &src, nullptr);
    check(command_list->Close(), "command list close failed");
    ID3D12CommandList* lists[] = {command_list.Get()};
    queue->ExecuteCommandLists(1, lists);
    ComPtr<ID3D12Fence> fence;
    check(device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)), "fence failed");
    HANDLE event_handle = CreateEvent(nullptr, FALSE, FALSE, nullptr);
    if (!event_handle) throw std::runtime_error("CreateEvent failed");
    wait_for_gpu(queue.Get(), fence.Get(), 1, event_handle);
    CloseHandle(event_handle);
    void* mapped = nullptr;
    D3D12_RANGE read_range{0, static_cast<SIZE_T>(readback_size)};
    check(readback->Map(0, &read_range, &mapped), "readback map failed");
    save_png(options.output, options.width, options.height, footprint.Footprint.RowPitch,
             static_cast<const BYTE*>(mapped) + footprint.Offset);
    readback->Unmap(0, nullptr);
}
} // namespace

int wmain(int argc, wchar_t** argv)
{
    try
    {
        const HRESULT com_result = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        if (FAILED(com_result) && com_result != RPC_E_CHANGED_MODE)
            check(com_result, "COM initialization failed");
        Options options = parse_options(argc, argv);
        const fs::path exe = fs::absolute(argv[0]).parent_path();
        if (options.shader.empty()) options.shader = exe / L"Raytrace.hlsl";
        DeviceContext context = create_device();
        if (options.capabilities && !options.render)
        {
            print_capabilities(context);
            if (SUCCEEDED(com_result)) CoUninitialize();
            return 0;
        }
        if (!options.render) throw std::runtime_error("use --capabilities-json or --render --output <file.png>");
        if (options.output.empty()) throw std::runtime_error("--output is required");
        render(context, options);
        std::cout
            << "{\"ok\":true,\"hardware_ray_tracing\":true,\"api\":\"dxr\""
            << ",\"device\":\"" << json_escape(context.name) << "\""
            << ",\"raytracing_tier\":\"" << tier_name(context.tier) << "\""
            << ",\"renderer\":\"d3d12_inline_ray_query\""
            << ",\"mode\":\"" << (options.path_traced ? "path_traced" : "hybrid_rt") << "\""
            << ",\"samples\":" << (options.path_traced ? options.samples : 1)
            << ",\"scene\":\"" << (options.vertices.empty() ? "proof" : "external_mesh") << "\""
            << ",\"output\":\"" << json_escape(utf8(options.output.wstring())) << "\"}"
            << std::endl;
        if (SUCCEEDED(com_result)) CoUninitialize();
        return 0;
    }
    catch (const std::exception& exc)
    {
        std::cerr << "{\"ok\":false,\"error\":\"" << json_escape(exc.what()) << "\"}" << std::endl;
        return 2;
    }
}
