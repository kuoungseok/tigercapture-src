import json
import struct
from pathlib import Path

from app.ar_pbr.asset_support import asset_support_status_text
from app.ar_pbr.asset_cache import asset_cache_diagnostics, load_asset_descriptor, store_asset_descriptor
from app.ar_pbr.importer import import_asset, import_track_asset, importer_backend_status


ASCII_FBX = """
; FBX 7.4.0 project file
FBXHeaderExtension:  {
    FBXHeaderVersion: 1003
    FBXVersion: 7400
}
GlobalSettings:  {
    Properties70:  {
        P: "UnitScaleFactor", "double", "Number", "",100
        P: "UpAxis", "int", "Integer", "",1
        P: "UpAxisSign", "int", "Integer", "",1
        P: "FrontAxis", "int", "Integer", "",2
        P: "FrontAxisSign", "int", "Integer", "",-1
        P: "CoordAxis", "int", "Integer", "",0
        P: "CoordAxisSign", "int", "Integer", "",1
    }
}
Objects:  {
    Geometry: 1000, "Geometry::RoadCone", "Mesh" {
        Vertices: *24 {
            a: -1,-2,0, 1,-2,0, 1,2,3, -1,2,3,
               -1,-2,0, 1,2,3, 0,0,2, 0,1,1
        }
        PolygonVertexIndex: *6 {
            a: 0,1,-3, 3,4,-6
        }
    }
    Model: 2000, "Model::RoadCone", "Mesh" {
        Properties70:  {
            P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0
        }
    }
    Material: 3000, "Material::OrangePaint", "" {
        Properties70:  {
            P: "DiffuseColor", "ColorRGB", "Color", "",1,0.35,0.1
            P: "SpecularFactor", "double", "Number", "",0.25
            P: "Shininess", "double", "Number", "",20
        }
    }
}
Connections:  {
    C: "OO",1000,2000
    C: "OO",3000,2000
}
"""


ASCII_ANIMATED_FBX = """
; FBX 7.4.0 project file
FBXHeaderExtension:  {
    FBXHeaderVersion: 1003
    FBXVersion: 7400
}
Objects:  {
    Geometry: 1000, "Geometry::AnimatedBox", "Mesh" {
        Vertices: *9 {
            a: -1,-1,0, 1,-1,0, 0,1,0
        }
        PolygonVertexIndex: *3 {
            a: 0,1,-3
        }
    }
    Model: 2000, "Model::AnimatedBox", "Mesh" {
        Properties70:  {
            P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0
        }
    }
    Model: 2100, "Model::Root", "LimbNode" {
        Properties70:  {
            P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0
        }
    }
    Deformer: 3000, "Deformer::Skin", "Skin" {
    }
    AnimationStack: 4000, "AnimStack::MoveRight", "" {
    }
    AnimationLayer: 4100, "AnimLayer::BaseLayer", "" {
    }
    AnimationCurveNode: 4200, "AnimCurveNode::T", "" {
    }
    AnimationCurve: 4300, "AnimCurve::T_X", "" {
        KeyTime: *2 {
            a: 0,46186158000
        }
        KeyValueFloat: *2 {
            a: 0,100
        }
    }
}
Connections:  {
    C: "OO",1000,2000
    C: "OO",4300,4200,"d|X"
    C: "OP",4200,2000,"Lcl Translation"
}
"""


ASCII_FBX_WITH_UV_SEAM = """
; FBX 7.4.0 project file
FBXHeaderExtension:  {
    FBXHeaderVersion: 1003
    FBXVersion: 7400
}
Objects:  {
    Geometry: 1000, "Geometry::UvSeamQuad", "Mesh" {
        Vertices: *12 {
            a: 0,0,0, 1,0,0, 1,1,0, 0,1,0
        }
        PolygonVertexIndex: *6 {
            a: 0,1,-3, 0,2,-4
        }
        LayerElementUV: 0 {
            MappingInformationType: "ByPolygonVertex"
            ReferenceInformationType: "IndexToDirect"
            UV: *12 {
                a: 0,0, 1,0, 1,1, 0.25,0.25, 0.75,0.75, 0,1
            }
            UVIndex: *6 {
                a: 0,1,2, 3,4,5
            }
        }
    }
    Model: 2000, "Model::UvSeamQuad", "Mesh" {
    }
}
Connections:  {
    C: "OO",1000,2000
}
"""


def _append_aligned(buffer: bytearray, payload: bytes) -> tuple[int, int]:
    offset = len(buffer)
    buffer.extend(payload)
    while len(buffer) % 4:
        buffer.append(0)
    return offset, len(payload)


def _write_minimal_vrm0_glb(path: Path) -> Path:
    positions = b"".join(struct.pack("<fff", *row) for row in [
        (-0.5, 0.0, 0.0),
        (0.5, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    ])
    indices = b"".join(struct.pack("<H", value) for value in [0, 1, 2])
    joints = bytes([
        0, 0, 0, 0,
        0, 0, 0, 0,
        0, 0, 0, 0,
    ])
    weights = b"".join(struct.pack("<ffff", 1.0, 0.0, 0.0, 0.0) for _ in range(3))

    blob = bytearray()
    position_offset, position_len = _append_aligned(blob, positions)
    index_offset, index_len = _append_aligned(blob, indices)
    joint_offset, joint_len = _append_aligned(blob, joints)
    weight_offset, weight_len = _append_aligned(blob, weights)
    gltf = {
        "asset": {"version": "2.0"},
        "extensionsUsed": ["KHR_materials_unlit", "VRM"],
        "extensions": {
            "VRM": {
                "exporterVersion": "UnitTest",
                "specVersion": "0.0",
                "meta": {
                    "title": "Milica Test",
                    "author": "unit-test",
                },
                "humanoid": {
                    "humanBones": [{"bone": "hips", "node": 1}],
                },
                "blendShapeMaster": {
                    "blendShapeGroups": [{"name": "Joy", "presetName": "joy", "binds": []}],
                },
                "secondaryAnimation": {
                    "boneGroups": [{"comment": "hair", "bones": [1]}],
                    "colliderGroups": [],
                },
                "materialProperties": [{
                    "name": "Face",
                    "shader": "VRM/MToon",
                    "floatProperties": {"_MToonVersion": 34},
                }],
            },
        },
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": position_offset, "byteLength": position_len},
            {"buffer": 0, "byteOffset": index_offset, "byteLength": index_len},
            {"buffer": 0, "byteOffset": joint_offset, "byteLength": joint_len},
            {"buffer": 0, "byteOffset": weight_offset, "byteLength": weight_len},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [-0.5, 0.0, 0.0],
                "max": [0.5, 1.0, 0.0],
            },
            {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
            {"bufferView": 2, "componentType": 5121, "count": 3, "type": "VEC4"},
            {"bufferView": 3, "componentType": 5126, "count": 3, "type": "VEC4"},
        ],
        "materials": [{
            "name": "Face",
            "pbrMetallicRoughness": {
                "baseColorFactor": [1.0, 0.8, 0.7, 1.0],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.9,
            },
            "extensions": {"KHR_materials_unlit": {}},
        }],
        "meshes": [{
            "name": "AvatarBody",
            "primitives": [{
                "attributes": {"POSITION": 0, "JOINTS_0": 2, "WEIGHTS_0": 3},
                "indices": 1,
                "material": 0,
            }],
        }],
        "skins": [{"joints": [1], "skeleton": 1}],
        "nodes": [
            {"name": "Avatar", "mesh": 0, "skin": 0},
            {"name": "hips"},
        ],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "
    bin_chunk = bytes(blob)
    while len(bin_chunk) % 4:
        bin_chunk += b"\x00"
    total_len = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    path.write_bytes(
        b"glTF"
        + struct.pack("<II", 2, total_len)
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
        + struct.pack("<I4s", len(bin_chunk), b"BIN\x00")
        + bin_chunk
    )
    return path


def _write_vrm0_mtoon_texture_glb(path: Path) -> Path:
    positions = b"".join(struct.pack("<fff", *row) for row in [
        (-0.5, 0.0, 0.0),
        (0.5, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    ])
    uvs = b"".join(struct.pack("<ff", *row) for row in [
        (0.0, 0.0),
        (1.0, 0.0),
        (0.5, 1.0),
    ])
    indices = b"".join(struct.pack("<H", value) for value in [0, 1, 2])
    png_blob = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05"
        b"\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    blob = bytearray()
    position_offset, position_len = _append_aligned(blob, positions)
    uv_offset, uv_len = _append_aligned(blob, uvs)
    index_offset, index_len = _append_aligned(blob, indices)
    main_offset, main_len = _append_aligned(blob, png_blob)
    bump_offset, bump_len = _append_aligned(blob, png_blob)
    gltf = {
        "asset": {"version": "2.0"},
        "extensionsUsed": ["VRM"],
        "extensions": {
            "VRM": {
                "exporterVersion": "UnitTest",
                "specVersion": "0.0",
                "meta": {
                    "title": "MToon Texture Test",
                    "author": "unit-test",
                },
                "humanoid": {
                    "humanBones": [{"bone": "hips", "node": 1}],
                },
                "blendShapeMaster": {"blendShapeGroups": []},
                "secondaryAnimation": {"boneGroups": [], "colliderGroups": []},
                "materialProperties": [{
                    "name": "Face",
                    "shader": "VRM/MToon",
                    "floatProperties": {"_MToonVersion": 34},
                    "textureProperties": {
                        "_MainTex": 0,
                        "_BumpMap": 1,
                    },
                }],
            },
        },
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": position_offset, "byteLength": position_len},
            {"buffer": 0, "byteOffset": uv_offset, "byteLength": uv_len},
            {"buffer": 0, "byteOffset": index_offset, "byteLength": index_len},
            {"buffer": 0, "byteOffset": main_offset, "byteLength": main_len},
            {"buffer": 0, "byteOffset": bump_offset, "byteLength": bump_len},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [-0.5, 0.0, 0.0],
                "max": [0.5, 1.0, 0.0],
            },
            {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC2"},
            {"bufferView": 2, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
        "images": [
            {"name": "face_main", "bufferView": 3, "mimeType": "image/png"},
            {"name": "face_normal", "bufferView": 4, "mimeType": "image/png"},
        ],
        "textures": [{"source": 0}, {"source": 1}],
        "materials": [{
            "name": "Face",
            "pbrMetallicRoughness": {
                "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.9,
            },
        }],
        "meshes": [{
            "name": "Face",
            "primitives": [{
                "attributes": {"POSITION": 0, "TEXCOORD_0": 1},
                "indices": 2,
                "material": 0,
            }],
        }],
        "nodes": [
            {"name": "Avatar", "mesh": 0},
            {"name": "hips"},
        ],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "
    bin_chunk = bytes(blob)
    while len(bin_chunk) % 4:
        bin_chunk += b"\x00"
    total_len = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    path.write_bytes(
        b"glTF"
        + struct.pack("<II", 2, total_len)
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
        + struct.pack("<I4s", len(bin_chunk), b"BIN\x00")
        + bin_chunk
    )
    return path


def _write_gltf_uv_transform_glb(path: Path) -> Path:
    positions = b"".join(struct.pack("<fff", *row) for row in [
        (-0.5, 0.0, 0.0),
        (0.5, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    ])
    uv0 = b"".join(struct.pack("<ff", *row) for row in [
        (0.0, 0.0),
        (0.0, 0.0),
        (0.0, 0.0),
    ])
    uv1 = b"".join(struct.pack("<ff", *row) for row in [
        (0.2, 0.3),
        (0.4, 0.5),
        (0.6, 0.7),
    ])
    indices = b"".join(struct.pack("<H", value) for value in [0, 1, 2])
    png_blob = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05"
        b"\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    blob = bytearray()
    position_offset, position_len = _append_aligned(blob, positions)
    uv0_offset, uv0_len = _append_aligned(blob, uv0)
    uv1_offset, uv1_len = _append_aligned(blob, uv1)
    index_offset, index_len = _append_aligned(blob, indices)
    image_offset, image_len = _append_aligned(blob, png_blob)
    gltf = {
        "asset": {"version": "2.0"},
        "extensionsUsed": ["KHR_texture_transform"],
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": position_offset, "byteLength": position_len},
            {"buffer": 0, "byteOffset": uv0_offset, "byteLength": uv0_len},
            {"buffer": 0, "byteOffset": uv1_offset, "byteLength": uv1_len},
            {"buffer": 0, "byteOffset": index_offset, "byteLength": index_len},
            {"buffer": 0, "byteOffset": image_offset, "byteLength": image_len},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [-0.5, 0.0, 0.0],
                "max": [0.5, 1.0, 0.0],
            },
            {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC2"},
            {"bufferView": 2, "componentType": 5126, "count": 3, "type": "VEC2"},
            {"bufferView": 3, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
        "images": [{"name": "atlas", "bufferView": 4, "mimeType": "image/png"}],
        "samplers": [{"wrapS": 10497, "wrapT": 33648}],
        "textures": [{"source": 0, "sampler": 0}],
        "materials": [{
            "name": "AtlasMat",
            "pbrMetallicRoughness": {
                "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                "baseColorTexture": {
                    "index": 0,
                    "texCoord": 1,
                    "extensions": {
                        "KHR_texture_transform": {
                            "offset": [0.1, 0.2],
                            "scale": [0.5, 2.0],
                        }
                    },
                },
            },
        }],
        "meshes": [{
            "name": "AtlasTri",
            "primitives": [{
                "attributes": {"POSITION": 0, "TEXCOORD_0": 1, "TEXCOORD_1": 2},
                "indices": 3,
                "material": 0,
            }],
        }],
        "nodes": [{"name": "AtlasNode", "mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "
    bin_chunk = bytes(blob)
    while len(bin_chunk) % 4:
        bin_chunk += b"\x00"
    total_len = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    path.write_bytes(
        b"glTF"
        + struct.pack("<II", 2, total_len)
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
        + struct.pack("<I4s", len(bin_chunk), b"BIN\x00")
        + bin_chunk
    )
    return path


def test_importer_status_accepts_fbx_without_external_renderer():
    status = importer_backend_status()

    assert status["fbx_supported"] is True
    assert status["external_renderer_required"] is False
    assert status["available_backends"]["internal_ascii_fbx"] is True
    assert "trimesh" in status["available_backends"]


def test_fbx_import_returns_safe_descriptor_when_backend_unavailable_or_file_invalid(tmp_path):
    fbx_path = tmp_path / "car.fbx"
    fbx_path.write_bytes(b"; FBX 7.4.0 placeholder\n")

    descriptor, diagnostics = import_asset(fbx_path)

    assert descriptor["type"] == "ar_pbr_asset"
    assert descriptor["source_ext"] == ".fbx"
    assert descriptor["requires_runtime_conversion"] is True
    assert descriptor["import_state"] in {"ready", "placeholder"}
    assert diagnostics["fbx_source"] is True
    if not diagnostics["imported"]:
        assert diagnostics["fallback"] is True
        assert descriptor["backend"] == "placeholder"


def test_ascii_fbx_import_extracts_runtime_descriptor(tmp_path):
    fbx_path = tmp_path / "road_cone.fbx"
    fbx_path.write_text(ASCII_FBX, encoding="utf-8")

    descriptor, diagnostics = import_asset(fbx_path)

    assert diagnostics["imported"] is True
    assert diagnostics["backend"] == "internal_ascii_fbx"
    assert descriptor["import_state"] == "ready"
    assert descriptor["source_fbx_version"] == 7400
    assert descriptor["mesh_count"] == 1
    assert descriptor["material_count"] == 1
    assert descriptor["models"][0]["name"] == "RoadCone"
    assert descriptor["materials"][0]["name"] == "OrangePaint"
    assert descriptor["materials"][0]["base_color"] == [1.0, 0.35, 0.1, 1.0]
    assert descriptor["units"]["scale_to_meters"] == 1.0
    assert descriptor["axes"]["up"] == "Y"
    assert descriptor["axes"]["forward"] == "-Z"
    assert descriptor["bounds"]["center"] == [0.0, 0.0, 1.5]
    assert descriptor["bounds"]["size"] == [2.0, 4.0, 3.0]
    assert descriptor["geometries"][0]["vertices"][0] == [-1.0, -2.0, 0.0]
    assert descriptor["geometries"][0]["triangle_count"] == 2
    assert descriptor["geometries"][0]["triangles"] == [[0, 1, 2], [3, 4, 5]]
    assert len(descriptor["connections"]) == 2


def test_ascii_fbx_import_splits_vertices_by_polygon_vertex_uv(tmp_path):
    fbx_path = tmp_path / "uv_seam.fbx"
    fbx_path.write_text(ASCII_FBX_WITH_UV_SEAM, encoding="utf-8")

    descriptor, diagnostics = import_asset(fbx_path, settings={"disable_descriptor_cache": True})

    assert diagnostics["imported"] is True
    assert diagnostics["backend"] == "internal_ascii_fbx"
    geometry = descriptor["geometries"][0]
    assert geometry["vertex_count"] == 4
    assert geometry["stored_vertex_count"] == 6
    assert geometry["triangle_count"] == 2
    assert geometry["triangles"] == [[0, 1, 2], [3, 4, 5]]
    assert geometry["uvs"][0] == [0.0, 0.0]
    assert geometry["uvs"][3] == [0.25, 0.25]
    assert geometry["source_indices"][0] == 0
    assert geometry["source_indices"][3] == 0


def test_ascii_fbx_import_extracts_animation_and_skeleton_metadata(tmp_path):
    fbx_path = tmp_path / "animated_box.fbx"
    fbx_path.write_text(ASCII_ANIMATED_FBX, encoding="utf-8")

    descriptor, diagnostics = import_asset(fbx_path)

    assert diagnostics["imported"] is True
    assert descriptor["animation_count"] == 1
    assert descriptor["animation_clips"][0]["name"] == "MoveRight"
    assert descriptor["animation_clips"][0]["duration_ms"] == 1000.0
    assert descriptor["animation_clips"][0]["model_curves"]["2000"]["translation"]["x"][-1] == [1000.0, 100.0]
    assert descriptor["skeletal_mesh_count"] == 1
    assert descriptor["skin_count"] == 1
    assert descriptor["bones"][0]["name"] == "Root"


def test_gltf_import_preserves_triangles_when_preview_budget_is_low(tmp_path):
    positions = []
    indices = []
    for tri_idx in range(120):
        base = len(positions)
        x = float(tri_idx % 12)
        y = float(tri_idx // 12)
        positions.extend([
            (x, y, 0.0),
            (x + 0.8, y, 0.0),
            (x + 0.4, y + 0.8, 0.2),
        ])
        indices.extend([base, base + 1, base + 2])
    position_blob = b"".join(struct.pack("<fff", *row) for row in positions)
    index_blob = b"".join(struct.pack("<H", value) for value in indices)
    png_blob = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05"
        b"\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    blob = position_blob + index_blob + png_blob
    (tmp_path / "mesh.bin").write_bytes(blob)
    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"uri": "mesh.bin", "byteLength": len(blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(position_blob)},
            {"buffer": 0, "byteOffset": len(position_blob), "byteLength": len(index_blob)},
            {
                "buffer": 0,
                "byteOffset": len(position_blob) + len(index_blob),
                "byteLength": len(png_blob),
            },
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(positions),
                "type": "VEC3",
                "min": [0.0, 0.0, 0.0],
                "max": [1.0, 1.0, 1.0],
            },
            {
                "bufferView": 1,
                "componentType": 5123,
                "count": len(indices),
                "type": "SCALAR",
            },
        ],
        "images": [{"name": "embedded_checker", "bufferView": 2, "mimeType": "image/png"}],
        "textures": [{"source": 0}],
        "materials": [{"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    asset = tmp_path / "pyramid.gltf"
    asset.write_text(json.dumps(gltf), encoding="utf-8")

    descriptor, diagnostics = import_asset(
        asset,
        settings={"disable_descriptor_cache": True, "max_triangles_per_geometry": 2},
    )

    assert diagnostics["backend"] == "internal_gltf"
    assert diagnostics["imported"] is True
    assert descriptor["geometries"][0]["triangle_count"] == 120
    assert len(descriptor["geometries"][0]["triangles"]) == 120
    assert Path(descriptor["materials"][0]["base_texture"]).exists()
    assert descriptor["materials"][0]["base_texture_source"] == "gltf_pbr_base_color_texture"
    assert descriptor["materials"][0]["pbr_available"] is True
    assert descriptor["render_profiles"]["default_profile"] == "authored"
    assert "marmoset_pbr" in descriptor["render_profiles"]["available_profiles"]
    assert descriptor["render_profiles"]["profiles"]["marmoset_pbr"]["available"] is True
    assert any("without import decimation" in warning for warning in diagnostics["warnings"])
    assert not any("decimated primitive" in warning for warning in diagnostics["warnings"])


def test_gltf_required_draco_compression_uses_placeholder_not_broken_mesh(tmp_path):
    asset = tmp_path / "compressed_car.gltf"
    asset.write_text(
        json.dumps({
            "asset": {"version": "2.0"},
            "extensionsUsed": ["KHR_draco_mesh_compression"],
            "extensionsRequired": ["KHR_draco_mesh_compression"],
            "buffers": [{"byteLength": 0}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 0}],
            "accessors": [
                {"componentType": 5123, "type": "SCALAR", "count": 3},
                {"componentType": 5126, "type": "VEC3", "count": 3},
            ],
            "meshes": [{
                "primitives": [{
                    "attributes": {"POSITION": 1},
                    "indices": 0,
                    "extensions": {
                        "KHR_draco_mesh_compression": {
                            "bufferView": 0,
                            "attributes": {"POSITION": 0},
                        },
                    },
                }],
            }],
            "nodes": [{"mesh": 0}],
            "scenes": [{"nodes": [0]}],
            "scene": 0,
        }),
        encoding="utf-8",
    )

    descriptor, diagnostics = import_asset(
        asset,
        settings={"disable_descriptor_cache": True, "placeholder_on_error": False},
    )

    assert diagnostics["imported"] is False
    assert diagnostics["fallback"] is True
    assert diagnostics["ok"] is False
    assert descriptor["backend"] == "placeholder"
    assert descriptor["geometries"] == []
    assert any("KHR_draco_mesh_compression" in warning for warning in diagnostics["warnings"])


def test_vrm0_import_uses_internal_gltf_avatar_path(tmp_path):
    asset = _write_minimal_vrm0_glb(tmp_path / "milica.vrm")

    descriptor, diagnostics = import_asset(
        asset,
        settings={"disable_descriptor_cache": True},
    )

    assert diagnostics["imported"] is True
    assert diagnostics["backend"] == "internal_gltf"
    assert diagnostics["vrm_source"] is True
    assert descriptor["source_ext"] == ".vrm"
    assert descriptor["source_format"] == "vrm"
    assert descriptor["vrm"]["profile"] == "VRM0"
    assert descriptor["vrm"]["title"] == "Milica Test"
    assert descriptor["skin_count"] == 1
    assert descriptor["skeletal_mesh_count"] == 1
    assert descriptor["materials"][0]["shader_model"] == "vrm_mtoon"
    assert descriptor["materials"][0]["unlit"] is True
    assert descriptor["support"]["support_level"] == "ready"
    assert descriptor["support"]["format_family"] == "vrm"
    assert descriptor["support"]["asset_kind"] == "humanoid_avatar"
    assert "vrm_avatar" in descriptor["support"]["feature_flags"]
    assert "vrm_mtoon_materials" in descriptor["support"]["feature_flags"]
    assert descriptor["support"]["render_path"] == "full_gpu_vrm_mtoon_cpu_baked_skeletal"
    assert asset_support_status_text(descriptor["support"]) == "Ready: VRM MToon"


def test_vrm0_import_reads_mtoon_texture_properties(tmp_path):
    asset = _write_vrm0_mtoon_texture_glb(tmp_path / "milica_textured.vrm")

    descriptor, diagnostics = import_asset(
        asset,
        settings={"disable_descriptor_cache": True},
    )

    material = descriptor["materials"][0]
    geometry = descriptor["geometries"][0]

    assert diagnostics["imported"] is True
    assert diagnostics["backend"] == "internal_gltf"
    assert descriptor["vrm"]["profile"] == "VRM0"
    assert material["shader_model"] == "vrm_mtoon"
    assert material["mtoon"] is True
    assert material["base_texture_source"] == "vrm0_mtoon_main_tex"
    assert material["normal_texture_source"] == "vrm0_mtoon_bump_map"
    assert material["pbr_available"] is False
    assert descriptor["render_profiles"]["source_style"] == "vrm_mtoon"
    assert descriptor["render_profiles"]["default_profile"] == "vrm_mtoon"
    assert descriptor["render_profiles"]["available_profiles"] == ["vrm_mtoon", "authored"]
    assert descriptor["render_profiles"]["profiles"]["vrm_mtoon"]["available"] is True
    assert descriptor["render_profiles"]["profiles"]["marmoset_pbr"]["available"] is False
    assert Path(material["base_texture"]).exists()
    assert Path(material["normal_texture"]).exists()
    assert geometry["uvs"] == [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]]


def test_gltf_import_preserves_texture_uv_set_and_transform(tmp_path):
    asset = _write_gltf_uv_transform_glb(tmp_path / "atlas.glb")

    descriptor, diagnostics = import_asset(
        asset,
        settings={"disable_descriptor_cache": True},
    )

    assert diagnostics["imported"] is True
    assert diagnostics["backend"] == "internal_gltf"
    material = descriptor["materials"][0]
    geometry = descriptor["geometries"][0]
    assert geometry["uvs"] == [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
    assert [[round(v, 3) for v in row] for row in geometry["uv_sets"]["1"]] == [
        [0.2, 0.3],
        [0.4, 0.5],
        [0.6, 0.7],
    ]
    assert material["base_uv_set"] == 1
    assert material["uv_set"] == 1
    assert material["base_uv_transform"] == {"offset": [0.1, 0.2], "scale": [0.5, 2.0], "rotation": 0.0}
    assert material["uv_transform"] == material["base_uv_transform"]
    assert material["base_wrap_s"] == "repeat"
    assert material["base_wrap_t"] == "mirrored_repeat"
    assert material["wrap_s"] == "repeat"
    assert material["wrap_t"] == "mirrored_repeat"


def test_binary_fbx_reports_internal_parser_skip_before_placeholder(tmp_path):
    fbx_path = tmp_path / "binary.fbx"
    fbx_path.write_bytes(b"Kaydara FBX Binary  \x00\x1a\x00" + b"\x00" * 64)

    descriptor, diagnostics = import_asset(fbx_path)

    assert descriptor["source_ext"] == ".fbx"
    if not diagnostics["imported"]:
        assert diagnostics["fallback"] is True
        assert any("internal_ascii_fbx skipped binary FBX" in warning for warning in diagnostics["warnings"])


def test_track_asset_import_resolves_relative_fbx_against_project_root(tmp_path):
    descriptor, diagnostics = import_track_asset(
        {"id": "car_track", "asset_path": "assets/car.fbx"},
        project_root=tmp_path,
    )

    assert descriptor["track_id"] == "car_track"
    assert descriptor["source_path"].endswith("assets\\car.fbx") or descriptor["source_path"].endswith("assets/car.fbx")
    assert diagnostics["track_id"] == "car_track"
    assert diagnostics["fallback"] is True
    assert "asset file does not exist" in diagnostics["warnings"]


def test_unsupported_asset_extension_is_reported():
    descriptor, diagnostics = import_asset("notes.txt")

    assert descriptor["import_state"] == "placeholder"
    assert diagnostics["ok"] is False
    assert diagnostics["fallback"] is True
    assert diagnostics["errors"]


def test_asset_descriptor_cache_roundtrip(tmp_path):
    fbx_path = tmp_path / "road_cone.fbx"
    fbx_path.write_text(ASCII_FBX, encoding="utf-8")
    descriptor, diagnostics = import_asset(fbx_path)

    info = store_asset_descriptor(descriptor, diagnostics=diagnostics, root=tmp_path)
    loaded = load_asset_descriptor(info["asset_id"], root=tmp_path)
    cache_diag = asset_cache_diagnostics(info["asset_id"], root=tmp_path)

    assert info["ok"] is True
    assert loaded == descriptor
    assert cache_diag["ok"] is True
