"""Render the downloaded Milica VRM with Trump OpenSeeFace motion applied.

This is a QA/preview tool, not the VSeeFace runtime. It uses the internal
AR/PBR packet renderer so the screenshot is based on the actual cached VRM mesh,
skin weights, MToon textures, and OpenSeeFace-driven pose values.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ar_pbr.gltf_loader import _accessor_array, _load_buffers, _load_gltf  # noqa: E402
from app.ar_pbr.software_renderer import _project, _transform_vertices  # noqa: E402
from app.ar_pbr.animation import animated_vertices_for_geometry  # noqa: E402
from app.ar_pbr.export_packet_renderer import render_offscreen_gpu_export_frame  # noqa: E402
from app.vtuber.openseeface_motion import load_openseeface_motion_csv, summarize_openseeface_motion  # noqa: E402
from app.vtuber.vrm_renderer import load_vrm_avatar_descriptor  # noqa: E402


DEFAULT_VRM = ROOT / "external" / "assets" / "vtuber" / "booth_milica" / "Milica1.3free" / "Milica_v1.3.vrm"
DEFAULT_DESCRIPTOR = ""
DEFAULT_CSV = ""
DEFAULT_OUT = ROOT / "debugCapture" / "milica_vrm_trump_actual_mapping_preview.png"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Milica VRM with OpenSeeFace Trump motion.")
    parser.add_argument("--vrm", default=str(DEFAULT_VRM))
    parser.add_argument("--descriptor", default=str(DEFAULT_DESCRIPTOR), help="Optional prebuilt descriptor JSON. If omitted, the durable VRM is imported directly.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Required OpenSeeFace motion CSV generated from an explicit source video.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--json-out", default="")
    parser.add_argument("--view", choices=("full", "closeup"), default="full")
    parser.add_argument("--upper-body-mode", choices=("seated", "none"), default="seated")
    parser.add_argument("--single-slot", choices=("neutral", "head", "mouth", "blink"), default="")
    parser.add_argument("--renderer", choices=("vrm-mtoon-gpu", "full-gpu"), default="vrm-mtoon-gpu")
    args = parser.parse_args(argv)

    vrm_path = Path(args.vrm)
    descriptor = _load_descriptor_or_vrm(_optional_arg_path(args.descriptor), vrm_path)
    csv_path = _required_csv_path(args.csv)
    frames = load_openseeface_motion_csv(csv_path)
    if not frames:
        raise SystemExit(f"No OpenSeeFace frames loaded: {csv_path}")

    morph_targets = _load_vrm_morph_targets(vrm_path)
    texture_paths = _expected_texture_paths(vrm_path)
    base_descriptor = _attach_vrm_textures(descriptor, texture_paths)
    base_descriptor = _attach_pose_animation(base_descriptor, frames, upper_body_mode=args.upper_body_mode)

    selected = _selected_frame_indices(frames, single_slot=args.single_slot)
    panels: list[Image.Image] = []
    panel_reports: list[dict[str, Any]] = []
    for slot, frame_index in enumerate(selected):
        frame = frames[frame_index]
        frame_descriptor = _apply_face_morphs(base_descriptor, morph_targets, frame)
        panel, diagnostics = _render_panel(
            descriptor=frame_descriptor,
            asset_path=vrm_path,
            time_ms=frame.time_ms,
            label=_frame_label_for_selection(args.single_slot, slot, frame),
            view=args.view,
            renderer=args.renderer,
        )
        panels.append(panel)
        panel_reports.append(
            {
                "slot": slot,
                "frame_index": frame_index,
                "time_ms": frame.time_ms,
                "yaw_deg": frame.yaw_deg,
                "pitch_deg": frame.pitch_deg,
                "roll_deg": frame.roll_deg,
                "mouth_open": frame.mouth_open,
                "blink_l": frame.blink_l,
                "blink_r": frame.blink_r,
                "renderer": {
                    "ok": diagnostics.get("ok"),
                    "renderer_quality": diagnostics.get("renderer_quality"),
                    "triangle_count": diagnostics.get("triangle_count"),
                    "pbr_sampled_triangle_count": diagnostics.get("pbr_sampled_triangle_count"),
                    "texture_sampled_triangle_count": diagnostics.get("texture_sampled_triangle_count"),
                    "warnings": diagnostics.get("warnings", [])[:6],
                    "errors": diagnostics.get("errors", [])[:6],
                },
            }
        )

    image = _compose_contact(panels, vrm_path, frames, panel_reports)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    json_out = Path(args.json_out) if args.json_out else out.with_suffix(".json")
    report = {
        "schema": "tigerstudio.vtuber.milica_trump_actual_mapping_preview.v1",
        "ok": True,
        "vrm": str(vrm_path),
        "csv": str(csv_path),
        "frame_count": len(frames),
        "view": args.view,
        "upper_body_mode": args.upper_body_mode,
        "single_slot": args.single_slot,
        "renderer": args.renderer,
        "openseeface": summarize_openseeface_motion(frames),
        "selected_frames": panel_reports,
        "limitations": [
            "Rendered through TigerCapture internal AR/PBR packet renderer, not a live VSeeFace window.",
            "VRM MToon main/normal textures, skin weights, head/neck/chest pose, and face morph targets are applied for QA.",
        ],
    }
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "json_out": str(json_out)}, ensure_ascii=False))
    return 0


def _load_descriptor(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    descriptor = data.get("descriptor") if isinstance(data, Mapping) else None
    if not isinstance(descriptor, dict):
        raise ValueError(f"Invalid descriptor cache: {path}")
    return descriptor


def _load_descriptor_or_vrm(descriptor_path: Path | None, vrm_path: Path) -> dict[str, Any]:
    if descriptor_path is not None:
        if not descriptor_path.is_file():
            raise FileNotFoundError(f"Descriptor JSON does not exist: {descriptor_path}")
        return _load_descriptor(descriptor_path)
    descriptor, diagnostics = load_vrm_avatar_descriptor(vrm_path)
    geometries = descriptor.get("geometries")
    if not isinstance(geometries, list) or not geometries:
        raise RuntimeError(f"Could not import VRM descriptor from durable asset: {vrm_path} ({diagnostics})")
    return descriptor


def _optional_arg_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    return Path(text) if text else None


def _required_csv_path(value: Any) -> Path:
    text = str(value or "").strip()
    if not text:
        raise SystemExit("--csv is required. Generate or select an OpenSeeFace CSV explicitly; debugCapture is not a durable default input.")
    path = Path(text)
    if not path.is_file():
        raise SystemExit(f"--csv does not exist: {path}")
    return path


def _expected_texture_paths(vrm_path: Path) -> dict[str, str]:
    cache_dir = ROOT / "debugCapture" / "ar_pbr_asset_cache" / "textures" / "Milica_v1_3_1fca2c885db2"
    if cache_dir.is_dir():
        return {
            "face_base": str((cache_dir / "image_0.png").resolve()),
            "face_normal": str((cache_dir / "image_2.png").resolve()),
            "body_base": str((cache_dir / "image_7.png").resolve()),
            "body_normal": str((cache_dir / "image_9.png").resolve()),
        }
    return _extract_texture_paths_from_vrm(vrm_path)


def _extract_texture_paths_from_vrm(vrm_path: Path) -> dict[str, str]:
    gltf, embedded_bin = _load_gltf(vrm_path)
    buffers = _load_buffers(vrm_path, gltf, embedded_bin)
    out_dir = ROOT / "debugCapture" / "ar_pbr_asset_cache" / "textures" / "Milica_v1_3_runtime"
    out_dir.mkdir(parents=True, exist_ok=True)
    images = gltf.get("images") or []
    result: dict[str, str] = {}
    for idx in (0, 2, 7, 9):
        if idx >= len(images):
            continue
        image = images[idx]
        buffer_view = image.get("bufferView")
        if buffer_view is None:
            continue
        raw = _buffer_view_bytes(gltf, buffers, buffer_view)
        path = out_dir / f"image_{idx}.png"
        path.write_bytes(raw)
        if idx == 0:
            result["face_base"] = str(path)
        elif idx == 2:
            result["face_normal"] = str(path)
        elif idx == 7:
            result["body_base"] = str(path)
        elif idx == 9:
            result["body_normal"] = str(path)
    return result


def _buffer_view_bytes(gltf: Mapping[str, Any], buffers: list[bytes], buffer_view_idx: Any) -> bytes:
    views = gltf.get("bufferViews") or []
    view = views[int(buffer_view_idx)]
    raw = buffers[int(view.get("buffer") or 0)]
    offset = int(view.get("byteOffset") or 0)
    length = int(view.get("byteLength") or 0)
    return bytes(raw[offset:offset + length])


def _attach_vrm_textures(descriptor: dict[str, Any], texture_paths: Mapping[str, str]) -> dict[str, Any]:
    out = deepcopy(descriptor)
    for mat in out.get("materials", []) or []:
        if not isinstance(mat, dict):
            continue
        material_id = str(mat.get("id") or "")
        is_face = material_id in {"mat_0", "mat_1", "mat_2"} or "face" in str(mat.get("name") or "").casefold()
        if not mat.get("base_texture"):
            mat["base_texture"] = texture_paths.get("face_base" if is_face else "body_base", "")
            if mat["base_texture"]:
                mat["base_texture_source"] = "milica_runtime_fallback"
        if not mat.get("normal_texture"):
            mat["normal_texture"] = texture_paths.get("face_normal" if is_face else "body_normal", "")
            if mat["normal_texture"]:
                mat["normal_texture_source"] = "milica_runtime_fallback"
        if mat.get("base_texture"):
            mat["base_color"] = [1.0, 1.0, 1.0, 1.0]
        if not mat.get("shader_model"):
            mat["shader_model"] = "vrm_mtoon"
        if not mat.get("source_shader"):
            mat["source_shader"] = "VRM/MToon"
        if "mtoon" in str(mat.get("shader_model") or mat.get("source_shader") or "").casefold():
            mat["unlit"] = True
    return out


def _attach_pose_animation(
    descriptor: dict[str, Any],
    frames: tuple[Any, ...],
    *,
    upper_body_mode: str = "seated",
) -> dict[str, Any]:
    out = deepcopy(descriptor)
    node_weights = {
        "node_10": (0.08, 0.08, 0.05, 0.00),   # Spine
        "node_11": (0.18, 0.18, 0.16, 0.00),   # Chest
        "node_12": (0.18, 0.18, 0.20, 0.00),   # UpperChest
        "node_17": (0.42, 0.38, -0.12, 0.18),  # Neck counter-balances torso roll
        "node_18": (1.00, 1.00, -0.24, 1.00),  # Head keeps face roll separate from shoulders
    }
    curves: dict[str, dict[str, Any]] = {}
    duration = max(frame.time_ms for frame in frames) if frames else 0
    for node_id, weights in node_weights.items():
        wx, wy, w_shoulder_z, w_face_z = weights
        curves[node_id] = {
            "rotation": {
                "x": [[float(frame.time_ms), float(frame.pitch_deg) * wx] for frame in frames],
                "y": [[float(frame.time_ms), float(frame.yaw_deg) * wy] for frame in frames],
                "z": [
                    [
                        float(frame.time_ms),
                        _frame_shoulder_roll(frame) * w_shoulder_z + float(frame.roll_deg) * w_face_z,
                    ]
                    for frame in frames
                ],
            }
        }
    if str(upper_body_mode or "").casefold() == "seated":
        curves.update(_seated_arm_curves(frames))
    out["animation_count"] = 1
    out["animation_clips"] = [
        {
            "id": "trump_openseeface_pose",
            "name": "Trump OpenSeeFace Pose",
            "duration_ms": float(duration),
            "model_curves": curves,
        }
    ]
    return out


def _seated_arm_curves(frames: tuple[Any, ...]) -> dict[str, dict[str, Any]]:
    arm_nodes = {
        "node_53": ((2.0, -4.0, 5.0), (0.03, 0.03, 0.05)),    # L shoulder
        "node_54": ((-12.0, 8.0, 72.0), (0.10, 0.04, 0.08)),   # L upper arm
        "node_55": ((-24.0, 14.0, 52.0), (0.05, 0.03, 0.00)),  # L lower arm
        "node_56": ((-6.0, 8.0, 8.0), (0.00, 0.00, 0.00)),     # L hand
        "node_72": ((2.0, 4.0, -5.0), (0.03, 0.03, 0.05)),     # R shoulder
        "node_73": ((-12.0, -8.0, -72.0), (0.10, 0.04, 0.08)), # R upper arm
        "node_74": ((-24.0, -14.0, -52.0), (0.05, 0.03, 0.00)),# R lower arm
        "node_75": ((-6.0, -8.0, -8.0), (0.00, 0.00, 0.00)),   # R hand
    }
    curves: dict[str, dict[str, Any]] = {}
    for node_id, (base, follow) in arm_nodes.items():
        curves[node_id] = {
            "rotation": {
                "x": [[float(frame.time_ms), float(base[0]) + float(frame.pitch_deg) * float(follow[0])] for frame in frames],
                "y": [[float(frame.time_ms), float(base[1]) + float(frame.yaw_deg) * float(follow[1])] for frame in frames],
                "z": [[float(frame.time_ms), float(base[2]) + _frame_shoulder_roll(frame) * float(follow[2])] for frame in frames],
            }
        }
    return curves


def _frame_shoulder_roll(frame: Any) -> float:
    value = getattr(frame, "shoulder_roll_deg", 0.0)
    try:
        if abs(float(value)) > 0.001:
            return float(value)
    except (TypeError, ValueError):
        pass
    return float(getattr(frame, "roll_deg", 0.0))


def _load_vrm_morph_targets(vrm_path: Path) -> dict[int, dict[int, list[list[float]]]]:
    gltf, embedded_bin = _load_gltf(vrm_path)
    buffers = _load_buffers(vrm_path, gltf, embedded_bin)
    meshes = gltf.get("meshes") or []
    if not meshes:
        return {}
    face_mesh = meshes[0]
    out: dict[int, dict[int, list[list[float]]]] = {}
    for prim_idx, primitive in enumerate(face_mesh.get("primitives") or []):
        targets = primitive.get("targets") or []
        prim_targets: dict[int, list[list[float]]] = {}
        for target_idx in (13, 14, 15, 39):
            if target_idx >= len(targets):
                continue
            accessor = targets[target_idx].get("POSITION") if isinstance(targets[target_idx], Mapping) else None
            if accessor is None:
                continue
            arr = _accessor_array(gltf, buffers, accessor)
            prim_targets[target_idx] = arr[:, :3].astype(float).tolist()
        out[prim_idx] = prim_targets
    return out


def _apply_face_morphs(
    descriptor: dict[str, Any],
    morph_targets: Mapping[int, Mapping[int, list[list[float]]]],
    frame: Any,
) -> dict[str, Any]:
    out = deepcopy(descriptor)
    morph_values = {
        39: max(0.0, min(1.0, float(frame.mouth_open))),  # A
        13: max(0.0, min(1.0, min(float(frame.blink_l), float(frame.blink_r)))),
        15: max(0.0, min(1.0, float(frame.blink_l))),
        14: max(0.0, min(1.0, float(frame.blink_r))),
    }
    for geometry in out.get("geometries", []) or []:
        if not isinstance(geometry, dict):
            continue
        name = str(geometry.get("name") or "")
        if not name.startswith("Face"):
            continue
        try:
            prim_idx = int(str(name).rsplit("_prim_", 1)[1])
        except Exception:
            continue
        targets = morph_targets.get(prim_idx) or {}
        vertices = geometry.get("vertices")
        if not isinstance(vertices, list) or not vertices:
            continue
        new_vertices: list[list[float]] = []
        for vertex_index, raw in enumerate(vertices):
            base = _vec3(raw)
            value = [base[0], base[1], base[2]]
            for target_idx, amount in morph_values.items():
                if amount <= 0.0:
                    continue
                deltas = targets.get(target_idx)
                if not deltas or vertex_index >= len(deltas):
                    continue
                delta = _vec3(deltas[vertex_index])
                value[0] += delta[0] * amount
                value[1] += delta[1] * amount
                value[2] += delta[2] * amount
            new_vertices.append(value)
        geometry["vertices"] = new_vertices
    return out


def _decimate_descriptor_for_contact(descriptor: dict[str, Any]) -> dict[str, Any]:
    """Keep all avatar parts visible while making the contact render responsive."""
    out = deepcopy(descriptor)
    caps = {
        "Face (merged).baked_prim_0": 1800,
        "Face (merged).baked_prim_1": 322,
        "Face (merged).baked_prim_2": 2600,
        "Body (merged).baked_prim_0": 2600,
        "Body (merged).baked_prim_1": 2400,
        "Body (merged).baked_prim_2": 1200,
        "Hair001 (merged).baked_prim_0": 7200,
    }
    total = 0
    for geometry in out.get("geometries", []) or []:
        if not isinstance(geometry, dict):
            continue
        triangles = geometry.get("triangles")
        if not isinstance(triangles, list):
            continue
        name = str(geometry.get("name") or "")
        cap = caps.get(name, 2600)
        if len(triangles) > cap:
            geometry["source_triangle_count"] = int(len(triangles))
            geometry["triangles"] = _even_sample(triangles, cap)
            geometry["triangle_count"] = int(len(geometry["triangles"]))
        total += int(len(geometry.get("triangles") or []))
    out["contact_preview_triangle_count"] = total
    return out


def _even_sample(rows: list[Any], target_count: int) -> list[Any]:
    if target_count <= 0 or len(rows) <= target_count:
        return list(rows)
    if target_count == 1:
        return [rows[len(rows) // 2]]
    last = len(rows) - 1
    out = []
    seen: set[int] = set()
    for i in range(target_count):
        idx = round(i * last / (target_count - 1))
        if idx not in seen:
            out.append(rows[idx])
            seen.add(idx)
    return out


def _render_panel(
    *,
    descriptor: dict[str, Any],
    asset_path: Path,
    time_ms: int,
    label: str,
    view: str = "full",
    renderer: str = "full-gpu",
) -> tuple[Image.Image, dict[str, Any]]:
    width, height = 380, 560
    base = _background(width, height)
    closeup = str(view).casefold() == "closeup"
    transform_position = [0.0, -1.42, 0.0] if closeup else [0.0, -0.08, 0.0]
    transform_scale = [5.10, 5.10, 5.10] if closeup else [2.70, 2.70, 2.70]
    focal = 650.0 if closeup else 620.0
    track = {
        "id": "milica_vrm_trump",
        "type": "ar_pbr_object",
        "asset_path": str(asset_path),
        "start_ms": 0,
        "end_ms": 60_000,
        "transform": {
            "position": transform_position,
            "rotation": [0.0, 180.0, 0.0],
            "scale": transform_scale,
        },
        "animation": {"auto_play": True, "loop": False, "speed": 1.0, "clip": "trump_openseeface_pose"},
        "shadow_catcher": True,
        "reflection_catcher": False,
        "occlusion": False,
        "render": {
            "lighting": {
                "light_azimuth": 28.0,
                "light_elevation": 42.0,
                "direct_strength": 0.65,
                "ibl_exposure": 1.15,
                "shadow_strength": 0.42,
                "hdri_id": "studio_small_09",
            }
        },
    }
    settings = {"camera_z": 3.05, "preserve_scene_layout": True}
    renderer_key = str(renderer or "").strip().casefold().replace("_", "-")
    if renderer_key in {"full-gpu", "vrm-mtoon-gpu", "vrm-gpu", "gpu"}:
        image, diagnostics = _render_full_gpu_panel(
            base,
            descriptor=descriptor,
            track=track,
            time_ms=int(time_ms),
            settings=settings,
            asset_path=asset_path,
        )
    else:
        image, diagnostics = _render_fast_vrm_contact(
            base,
            descriptor=descriptor,
            track=track,
            time_ms=int(time_ms),
            settings=settings,
            intrinsics={"fx": focal, "fy": focal, "cx": width * 0.5, "cy": height * (0.45 if closeup else 0.52)},
        )
    draw = ImageDraw.Draw(image)
    _, font, small = _fonts()
    draw.rounded_rectangle((16, 14, width - 16, 72), radius=10, fill=(17, 21, 26, 210), outline=(72, 92, 104, 180))
    draw.text((30, 24), label, font=font, fill=(238, 244, 248))
    draw.text((30, 50), "seated upper-body fallback", font=small, fill=(178, 194, 205))
    return image, diagnostics


def _render_full_gpu_panel(
    base: Image.Image,
    *,
    descriptor: dict[str, Any],
    track: dict[str, Any],
    time_ms: int,
    settings: Mapping[str, Any],
    asset_path: Path,
) -> tuple[Image.Image, dict[str, Any]]:
    full_settings = {
        **dict(settings or {}),
        "asset_descriptors": {
            str(track.get("id") or ""): descriptor,
            str(asset_path): descriptor,
        },
        "texture_max_size": 1024,
        "fit_padding": 0.03,
        "enable_shadow_map": False,
    }
    out, diagnostics = render_offscreen_gpu_export_frame(
        base,
        time_ms=int(time_ms),
        ar_tracks=[track],
        camera_solution={"frame_size": [base.size[0], base.size[1]]},
        settings=full_settings,
    )
    if isinstance(out, Image.Image):
        return out.convert("RGBA"), dict(diagnostics or {})
    return base.copy(), {
        "ok": False,
        "renderer_quality": "full_gpu_output_decode_failed",
        "errors": ["full GPU renderer did not return a PIL image"],
    }


def _render_fast_vrm_contact(
    base: Image.Image,
    *,
    descriptor: dict[str, Any],
    track: dict[str, Any],
    time_ms: int,
    settings: Mapping[str, Any],
    intrinsics: Mapping[str, float],
) -> tuple[Image.Image, dict[str, Any]]:
    import numpy as np

    width, height = base.size
    scene_bounds = descriptor.get("bounds") if isinstance(descriptor.get("bounds"), Mapping) else None
    materials = {
        str(mat.get("id") or ""): mat
        for mat in descriptor.get("materials", []) or []
        if isinstance(mat, Mapping)
    }
    textures = _texture_arrays(materials)
    color_buffer = np.asarray(base.convert("RGBA"), dtype=np.float32) / 255.0
    z_buffer = np.full((height, width), np.inf, dtype=np.float32)
    shadow_points: list[tuple[float, float]] = []
    triangle_count = 0
    sampled_count = 0
    visible_pixels = 0
    for geometry in descriptor.get("geometries", []) or []:
        if not isinstance(geometry, Mapping):
            continue
        vertices_raw = animated_vertices_for_geometry(
            geometry.get("vertices") or [],
            geometry=geometry,
            descriptor=descriptor,
            track=track,
            time_ms=time_ms,
        )
        temp_geometry = dict(geometry)
        temp_geometry["vertices"] = vertices_raw
        temp_geometry.pop("skin_inverse_bind_matrices", None)
        temp_geometry.pop("skin_weights", None)
        temp_geometry.pop("skin_joint_ids", None)
        vertices = _transform_vertices(
            temp_geometry,
            track,
            settings,
            scene_bounds,
            descriptor=None,
            time_ms=time_ms,
        )
        projected = _project(
            vertices,
            fx=float(intrinsics.get("fx", 705.0)),
            fy=float(intrinsics.get("fy", 705.0)),
            cx=float(intrinsics.get("cx", width * 0.5)),
            cy=float(intrinsics.get("cy", height * 0.52)),
        )
        material = materials.get(str(geometry.get("material_id") or ""), {})
        texture = textures.get(str(material.get("base_texture") or ""))
        uvs = geometry.get("uvs") if isinstance(geometry.get("uvs"), list) else []
        fallback = np.asarray(_material_fallback_rgba(material), dtype=np.float32) / 255.0
        for tri in geometry.get("triangles") or []:
            if not isinstance(tri, (list, tuple)) or len(tri) < 3:
                continue
            try:
                i0, i1, i2 = int(tri[0]), int(tri[1]), int(tri[2])
                p0, p1, p2 = projected[i0], projected[i1], projected[i2]
            except Exception:
                continue
            if max(p0[0], p1[0], p2[0]) < -1 or min(p0[0], p1[0], p2[0]) > width + 1:
                continue
            if max(p0[1], p1[1], p2[1]) < -1 or min(p0[1], p1[1], p2[1]) > height + 1:
                continue
            rendered = _rasterize_textured_triangle(
                color_buffer,
                z_buffer,
                (p0, p1, p2),
                (uvs[i0], uvs[i1], uvs[i2]) if texture is not None and len(uvs) > max(i0, i1, i2) else None,
                texture,
                fallback,
            )
            if rendered <= 0:
                continue
            shadow_points.extend([(p0[0], p0[1]), (p1[0], p1[1]), (p2[0], p2[1])])
            visible_pixels += int(rendered)
            if texture is not None and len(uvs) > max(i0, i1, i2):
                sampled_count += 1
            triangle_count += 1

    image = Image.fromarray(np.clip(color_buffer * 255.0, 0, 255).astype("uint8"), "RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_soft_contact_shadow(draw, shadow_points, width, height)
    return image, {
        "ok": visible_pixels > 0,
        "renderer_quality": "actual_vrm_zbuffer_uv_texture_pose_contact",
        "triangle_count": triangle_count,
        "texture_sampled_triangle_count": sampled_count,
        "visible_pixel_count": visible_pixels,
        "pbr_sampled_triangle_count": 0,
        "warnings": [],
        "errors": [] if visible_pixels > 0 else ["no visible pixels"],
    }


def _rasterize_textured_triangle(
    color_buffer: Any,
    z_buffer: Any,
    points: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
    uvs: tuple[Any, Any, Any] | None,
    texture: Any,
    fallback: Any,
) -> int:
    import numpy as np

    height, width = z_buffer.shape
    p0, p1, p2 = points
    x0, y0, z0 = float(p0[0]), float(p0[1]), float(p0[2])
    x1, y1, z1 = float(p1[0]), float(p1[1]), float(p1[2])
    x2, y2, z2 = float(p2[0]), float(p2[1]), float(p2[2])
    box_x0 = max(0, int(np.floor(min(x0, x1, x2))))
    box_y0 = max(0, int(np.floor(min(y0, y1, y2))))
    box_x1 = min(width, int(np.ceil(max(x0, x1, x2))) + 1)
    box_y1 = min(height, int(np.ceil(max(y0, y1, y2))) + 1)
    if box_x1 <= box_x0 or box_y1 <= box_y0:
        return 0
    denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(denom) <= 1.0e-8:
        return 0
    yy, xx = np.mgrid[box_y0:box_y1, box_x0:box_x1].astype(np.float32)
    px = xx + 0.5
    py = yy + 0.5
    w0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / denom
    w1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / denom
    w2 = 1.0 - w0 - w1
    mask = (w0 >= -0.001) & (w1 >= -0.001) & (w2 >= -0.001)
    if not bool(mask.any()):
        return 0
    z = w0 * z0 + w1 * z1 + w2 * z2
    target_z = z_buffer[box_y0:box_y1, box_x0:box_x1]
    visible = mask & (z < target_z)
    if not bool(visible.any()):
        return 0

    if texture is not None and uvs is not None:
        tex = np.asarray(texture, dtype=np.float32) / 255.0
        h, w = tex.shape[:2]
        try:
            u0, v0 = float(uvs[0][0]), float(uvs[0][1])
            u1, v1 = float(uvs[1][0]), float(uvs[1][1])
            u2, v2 = float(uvs[2][0]), float(uvs[2][1])
            u = np.mod(w0 * u0 + w1 * u1 + w2 * u2, 1.0)
            v = np.mod(w0 * v0 + w1 * v1 + w2 * v2, 1.0)
            tx = np.clip(np.rint(u * max(1, w - 1)).astype(np.int32), 0, max(0, w - 1))
            ty = np.clip(np.rint(v * max(1, h - 1)).astype(np.int32), 0, max(0, h - 1))
            src = tex[ty, tx, :4]
        except Exception:
            src = np.zeros((*visible.shape, 4), dtype=np.float32)
            src[:, :, :] = fallback
    else:
        src = np.zeros((*visible.shape, 4), dtype=np.float32)
        src[:, :, :] = fallback

    alpha = np.clip(src[:, :, 3], 0.0, 1.0)
    visible = visible & (alpha > 0.02)
    if not bool(visible.any()):
        return 0
    dst = color_buffer[box_y0:box_y1, box_x0:box_x1, :]
    a = alpha[:, :, None]
    dst[visible, :3] = src[visible, :3] * a[visible] + dst[visible, :3] * (1.0 - a[visible])
    dst[visible, 3] = np.maximum(dst[visible, 3], alpha[visible])
    target_z[visible] = z[visible]
    return int(np.count_nonzero(visible))


def _texture_arrays(materials: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for mat in materials.values():
        path = str(mat.get("base_texture") or "")
        if not path or path in out:
            continue
        try:
            import numpy as np

            out[path] = np.asarray(Image.open(path).convert("RGBA"), dtype="uint8")
        except Exception:
            out[path] = None
    return out


def _sample_texture_rgba(texture: Any, u: float, v: float) -> tuple[int, int, int, int]:
    import numpy as np

    arr = np.asarray(texture)
    h, w = arr.shape[:2]
    x = int(max(0, min(w - 1, round((u % 1.0) * (w - 1)))))
    y = int(max(0, min(h - 1, round((v % 1.0) * (h - 1)))))
    px = arr[y, x]
    return int(px[0]), int(px[1]), int(px[2]), int(px[3])


def _material_fallback_rgba(material: Mapping[str, Any]) -> tuple[int, int, int, int]:
    color = material.get("base_color")
    values = list(color) if isinstance(color, (list, tuple)) else [0.85, 0.82, 0.78, 1.0]
    values += [1.0, 1.0, 1.0, 1.0]
    return tuple(max(0, min(255, int(float(value) * 255))) for value in values[:4])  # type: ignore[return-value]


def _draw_soft_contact_shadow(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    width: int,
    height: int,
) -> None:
    if not points:
        return
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x0 = max(0, min(xs))
    x1 = min(width, max(xs))
    y1 = min(height, max(ys) + 18)
    y0 = max(0, y1 - max(14, (max(ys) - min(ys)) * 0.10))
    draw.ellipse((x0, y0, x1, y1), fill=(0, 0, 0, 55))


def _background(width: int, height: int) -> Image.Image:
    img = Image.new("RGBA", (width, height), (50, 58, 64, 255))
    pixels = img.load()
    for y in range(height):
        t = y / max(1, height - 1)
        top = (73, 85, 94)
        bottom = (32, 37, 43)
        color = tuple(int(top[i] * (1.0 - t) + bottom[i] * t) for i in range(3))
        for x in range(width):
            pixels[x, y] = (*color, 255)
    draw = ImageDraw.Draw(img, "RGBA")
    floor_y = int(height * 0.74)
    draw.polygon([(0, floor_y), (width, floor_y - 56), (width, height), (0, height)], fill=(82, 91, 96, 255))
    for step in range(-8, 18):
        y = floor_y + step * 34
        draw.line((0, y, width, y - 56), fill=(102, 112, 118, 110), width=1)
    for step in range(-12, 16):
        x = step * 48
        draw.line((x, floor_y + 90, x + width, floor_y - 28), fill=(102, 112, 118, 85), width=1)
    return img


def _compose_contact(
    panels: list[Image.Image],
    vrm_path: Path,
    frames: tuple[Any, ...],
    reports: list[dict[str, Any]],
) -> Image.Image:
    cols = len(panels)
    panel_w, panel_h = panels[0].size
    header_h = 118
    footer_h = 84
    canvas = Image.new("RGB", (cols * panel_w, header_h + panel_h + footer_h), (20, 24, 29))
    draw = ImageDraw.Draw(canvas)
    big, font, small = _fonts()
    draw.text((32, 24), "Milica VRM + Trump OpenSeeFace Mapping", font=big, fill=(242, 247, 250))
    subtitle = f"{vrm_path.name} | actual VRM mesh/textures + seated upper-body fallback | {len(frames)} tracking frames"
    draw.text((34, 72), subtitle, font=font, fill=(180, 195, 205))
    for idx, panel in enumerate(panels):
        canvas.paste(panel.convert("RGB"), (idx * panel_w, header_h))
    y = header_h + panel_h + 18
    for idx, report in enumerate(reports):
        x = idx * panel_w + 30
        renderer = report.get("renderer") or {}
        text = (
            f"yaw {report['yaw_deg']:+.1f}  pitch {report['pitch_deg']:+.1f}  "
            f"blink {max(report['blink_l'], report['blink_r']):.2f}  A {report['mouth_open']:.2f}"
        )
        draw.text((x, y), text, font=small, fill=(230, 236, 242))
        draw.text(
            (x, y + 26),
            f"tris {renderer.get('triangle_count', 0)}  pbr {renderer.get('pbr_sampled_triangle_count', 0)}",
            font=small,
            fill=(158, 174, 186),
        )
    return canvas


def _selected_frame_indices(frames: tuple[Any, ...], *, single_slot: str = "") -> list[int]:
    candidates = {
        "neutral": 0,
        "head": max(range(len(frames)), key=lambda i: abs(frames[i].yaw_deg) + abs(frames[i].roll_deg) * 0.7),
        "mouth": max(range(len(frames)), key=lambda i: frames[i].mouth_open),
        "blink": max(range(len(frames)), key=lambda i: max(frames[i].blink_l, frames[i].blink_r)),
    }
    wanted = str(single_slot or "").casefold()
    if wanted in candidates:
        return [candidates[wanted]]
    ordered = [
        candidates["neutral"],
        candidates["head"],
        max(range(len(frames)), key=lambda i: frames[i].mouth_open + max(frames[i].blink_l, frames[i].blink_r)),
    ]
    out: list[int] = []
    for idx in ordered:
        if idx not in out:
            out.append(idx)
    while len(out) < min(3, len(frames)):
        pick = round((len(frames) - 1) * len(out) / 2)
        if pick not in out:
            out.append(pick)
        else:
            break
    return out[:3]


def _frame_label(slot: int, frame: Any) -> str:
    names = ["neutral", "head", "mouth", "blink"]
    return f"{names[slot] if slot < len(names) else 'pose'}  {frame.time_ms / 1000.0:.2f}s"


def _frame_label_for_selection(single_slot: str, slot: int, frame: Any) -> str:
    wanted = str(single_slot or "").casefold()
    if wanted:
        return f"{wanted}  {frame.time_ms / 1000.0:.2f}s"
    return _frame_label(slot, frame)


def _vec3(value: Any) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else [0.0, 0.0, 0.0]
    values = list(source) + [0.0, 0.0, 0.0]
    return [float(values[0]), float(values[1]), float(values[2])]


def _fonts() -> tuple[Any, Any, Any]:
    try:
        return (
            ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 34),
            ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 20),
            ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 16),
        )
    except OSError:
        fallback = ImageFont.load_default()
        return fallback, fallback, fallback


if __name__ == "__main__":
    raise SystemExit(main())
