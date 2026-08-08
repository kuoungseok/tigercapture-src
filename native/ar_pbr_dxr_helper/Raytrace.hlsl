struct Vertex
{
    float3 position;
    float3 normal;
    float3 albedo;
    float metallic;
    float roughness;
};

struct Params
{
    float4 camera_position;
    float4 camera_forward;
    float4 camera_right;
    float4 camera_up;
    float4 light_position_intensity;
    uint width;
    uint height;
    uint samples;
    uint max_bounces;
    uint camera_visible;
    uint reflection_visible;
    uint path_traced;
    uint frame_seed;
    uint environment_width;
    uint environment_height;
    uint use_environment;
    float environment_rotation;
};

RWTexture2D<float4> Output : register(u0);
RaytracingAccelerationStructure Scene : register(t0);
StructuredBuffer<Vertex> Vertices : register(t1);
Texture2D<float4> EnvironmentMap : register(t2);
ConstantBuffer<Params> P : register(b0);

uint hash_u32(uint x)
{
    x ^= x >> 16;
    x *= 0x7feb352d;
    x ^= x >> 15;
    x *= 0x846ca68b;
    return x ^ (x >> 16);
}

float random01(inout uint state)
{
    state = hash_u32(state);
    return (state & 0x00ffffff) / 16777216.0;
}

float3 environment(float3 direction)
{
    if (P.use_environment != 0 && P.environment_width > 0 && P.environment_height > 0)
    {
        float u = frac(atan2(direction.z, direction.x) / 6.2831853 + 0.5 + P.environment_rotation);
        float v = acos(clamp(direction.y, -1.0, 1.0)) / 3.14159265;
        uint2 pixel = uint2(
            min(P.environment_width - 1, (uint)(u * P.environment_width)),
            min(P.environment_height - 1, (uint)(v * P.environment_height)));
        return max(EnvironmentMap.Load(int3(pixel, 0)).rgb, 0.0);
    }
    float t = saturate(direction.y * 0.5 + 0.5);
    float3 horizon = float3(0.32, 0.38, 0.50);
    float3 zenith = float3(0.035, 0.075, 0.18);
    float3 ground = float3(0.055, 0.045, 0.035);
    float3 base = direction.y >= 0.0
        ? lerp(horizon, zenith, pow(t, 0.65))
        : lerp(horizon * 0.22, ground, saturate(-direction.y));
    float3 sun_dir = normalize(float3(-0.45, 0.72, -0.52));
    float sun = pow(saturate(dot(direction, sun_dir)), 900.0) * 14.0;
    return base + sun * float3(1.0, 0.72, 0.38);
}

bool trace_scene(float3 origin, float3 direction, float t_min, float t_max,
                 out uint primitive, out float2 bary, out float distance)
{
    RayDesc ray;
    ray.Origin = origin;
    ray.Direction = direction;
    ray.TMin = t_min;
    ray.TMax = t_max;
    RayQuery<RAY_FLAG_NONE> query;
    query.TraceRayInline(Scene, RAY_FLAG_NONE, 0xff, ray);
    while (query.Proceed()) { }
    if (query.CommittedStatus() != COMMITTED_TRIANGLE_HIT)
    {
        primitive = 0;
        bary = 0.0;
        distance = t_max;
        return false;
    }
    primitive = query.CommittedPrimitiveIndex();
    bary = query.CommittedTriangleBarycentrics();
    distance = query.CommittedRayT();
    return true;
}

bool occluded(float3 origin, float3 direction, float distance)
{
    RayDesc ray;
    ray.Origin = origin;
    ray.Direction = direction;
    ray.TMin = 0.002;
    ray.TMax = max(0.003, distance - 0.004);
    RayQuery<RAY_FLAG_ACCEPT_FIRST_HIT_AND_END_SEARCH> query;
    query.TraceRayInline(Scene, RAY_FLAG_NONE, 0xff, ray);
    while (query.Proceed()) { }
    return query.CommittedStatus() == COMMITTED_TRIANGLE_HIT;
}

void surface(uint primitive, float2 bary, out float3 normal, out float3 albedo,
             out float metallic, out float roughness)
{
    uint base = primitive * 3;
    Vertex a = Vertices[base + 0];
    Vertex b = Vertices[base + 1];
    Vertex c = Vertices[base + 2];
    float3 weights = float3(1.0 - bary.x - bary.y, bary.x, bary.y);
    normal = normalize(a.normal * weights.x + b.normal * weights.y + c.normal * weights.z);
    albedo = saturate(a.albedo * weights.x + b.albedo * weights.y + c.albedo * weights.z);
    metallic = saturate(a.metallic * weights.x + b.metallic * weights.y + c.metallic * weights.z);
    roughness = clamp(a.roughness * weights.x + b.roughness * weights.y + c.roughness * weights.z, 0.03, 1.0);
}

float3 direct_lighting(float3 position, float3 normal, float3 albedo,
                       float metallic, float roughness, float3 view)
{
    float3 to_light = P.light_position_intensity.xyz - position;
    float distance = length(to_light);
    float3 light_dir = to_light / max(distance, 0.001);
    float ndotl = saturate(dot(normal, light_dir));
    if (ndotl <= 0.0 || occluded(position + normal * 0.003, light_dir, distance))
        return 0.0;
    float attenuation = P.light_position_intensity.w / max(1.0, distance * distance);
    float3 half_vector = normalize(light_dir + view);
    float ndoth = saturate(dot(normal, half_vector));
    float spec_power = lerp(180.0, 4.0, roughness);
    float3 f0 = lerp(0.04.xxx, albedo, metallic);
    float3 specular = f0 * pow(ndoth, spec_power) * (spec_power + 2.0) * 0.125;
    float3 diffuse = albedo * (1.0 - metallic) / 3.14159265;
    return (diffuse + specular) * ndotl * attenuation;
}

float3 hybrid_ray(float3 origin, float3 direction)
{
    uint primitive;
    float2 bary;
    float distance;
    if (!trace_scene(origin, direction, 0.001, 10000.0, primitive, bary, distance))
        return P.camera_visible != 0 ? environment(direction) : 0.0;

    float3 normal, albedo;
    float metallic, roughness;
    surface(primitive, bary, normal, albedo, metallic, roughness);
    float3 position = origin + direction * distance;
    float3 view = -direction;
    float3 color = direct_lighting(position, normal, albedo, metallic, roughness, view);
    color += albedo * (1.0 - metallic) * environment(normal) * 0.18;

    if (P.reflection_visible != 0)
    {
        float3 reflection = reflect(direction, normal);
        uint rp;
        float2 rb;
        float rd;
        float3 reflected_color;
        if (trace_scene(position + normal * 0.004, reflection, 0.001, 10000.0, rp, rb, rd))
        {
            float3 rn, ra;
            float rm, rr;
            surface(rp, rb, rn, ra, rm, rr);
            float3 rpos = position + normal * 0.004 + reflection * rd;
            reflected_color = direct_lighting(rpos, rn, ra, rm, rr, -reflection)
                + ra * environment(rn) * 0.12;
        }
        else
        {
            reflected_color = environment(reflection);
        }
        float fresnel = pow(1.0 - saturate(dot(normal, view)), 5.0);
        float reflection_weight = lerp(0.05 + 0.25 * fresnel, 0.82, metallic) * (1.0 - roughness * 0.55);
        color = lerp(color, reflected_color, saturate(reflection_weight));
    }
    return color;
}

float3 cosine_hemisphere(float3 normal, inout uint state)
{
    float r1 = random01(state);
    float r2 = random01(state);
    float phi = 6.2831853 * r1;
    float r = sqrt(r2);
    float3 tangent = normalize(abs(normal.y) < 0.999 ? cross(float3(0, 1, 0), normal) : cross(float3(1, 0, 0), normal));
    float3 bitangent = cross(normal, tangent);
    return normalize(tangent * (r * cos(phi)) + bitangent * (r * sin(phi)) + normal * sqrt(1.0 - r2));
}

float3 path_ray(float3 origin, float3 direction, inout uint state)
{
    float3 radiance = 0.0;
    float3 throughput = 1.0;
    [loop]
    for (uint bounce = 0; bounce < P.max_bounces; ++bounce)
    {
        uint primitive;
        float2 bary;
        float distance;
        if (!trace_scene(origin, direction, 0.001, 10000.0, primitive, bary, distance))
        {
            if (bounce == 0 || P.reflection_visible != 0)
                radiance += throughput * environment(direction);
            break;
        }
        float3 normal, albedo;
        float metallic, roughness;
        surface(primitive, bary, normal, albedo, metallic, roughness);
        float3 position = origin + direction * distance;
        radiance += throughput * direct_lighting(position, normal, albedo, metallic, roughness, -direction);
        float choose_specular = lerp(0.12, 0.9, metallic) * (1.0 - roughness * 0.45);
        if (random01(state) < choose_specular)
        {
            float3 perfect = reflect(direction, normal);
            float3 diffuse_lobe = cosine_hemisphere(normal, state);
            direction = normalize(lerp(perfect, diffuse_lobe, roughness * roughness));
            throughput *= lerp(0.04.xxx, albedo, metallic) / max(choose_specular, 0.05);
        }
        else
        {
            direction = cosine_hemisphere(normal, state);
            throughput *= albedo * (1.0 - metallic) / max(1.0 - choose_specular, 0.05);
        }
        origin = position + normal * 0.004;
        throughput = min(throughput, 4.0);
    }
    return radiance;
}

[numthreads(8, 8, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID)
{
    if (dispatch_id.x >= P.width || dispatch_id.y >= P.height)
        return;
    uint2 pixel = dispatch_id.xy;
    uint state = hash_u32(pixel.x + pixel.y * P.width + P.frame_seed * 1664525u);
    uint sample_count = max(1u, P.samples);
    float3 color = 0.0;
    float coverage = 0.0;
    [loop]
    for (uint sample_index = 0; sample_index < sample_count; ++sample_index)
    {
        float2 jitter = P.path_traced != 0
            ? float2(random01(state), random01(state))
            : float2(0.5, 0.5);
        float2 uv = (float2(pixel) + jitter) / float2(P.width, P.height);
        float2 screen = uv * 2.0 - 1.0;
        screen.y = -screen.y;
        float aspect = float(P.width) / float(P.height);
        float tan_half_fov = 0.41421356;
        float3 direction = normalize(
            P.camera_forward.xyz
            + P.camera_right.xyz * screen.x * aspect * tan_half_fov
            + P.camera_up.xyz * screen.y * tan_half_fov);
        uint coverage_primitive;
        float2 coverage_bary;
        float coverage_distance;
        coverage += trace_scene(
            P.camera_position.xyz,
            direction,
            0.001,
            10000.0,
            coverage_primitive,
            coverage_bary,
            coverage_distance) ? 1.0 : 0.0;
        color += P.path_traced != 0
            ? path_ray(P.camera_position.xyz, direction, state)
            : hybrid_ray(P.camera_position.xyz, direction);
    }
    color /= sample_count;
    color = color / (1.0 + color);
    color = pow(saturate(color), 1.0 / 2.2);
    float alpha = P.camera_visible != 0 ? 1.0 : saturate(coverage / sample_count);
    Output[pixel] = float4(color, alpha);
}
