"""Unreal Editor Python fallback for exporting an AnimSequence to Tiger AR/PBR."""
from __future__ import annotations

import json
import os
import traceback

import unreal


def _round(value: float) -> float:
    return round(float(value), 6)


def _tiger_position(value) -> list[float]:
    return [_round(value.x * 0.01), _round(value.z * 0.01), _round(-value.y * 0.01)]


def _tiger_quaternion(value) -> list[float]:
    x = float(value.x)
    y = float(value.z)
    z = -float(value.y)
    w = float(value.w)
    length = (x * x + y * y + z * z + w * w) ** 0.5 or 1.0
    return [_round(x / length), _round(y / length), _round(z / length), _round(w / length)]


def _sample_times(duration_s: float, max_samples: int) -> list[float]:
    if duration_s <= 0.0:
        return [0.0]
    sample_count = max(2, int(max_samples))
    return [duration_s * idx / max(1, sample_count - 1) for idx in range(sample_count)]


def _export_clip(asset_path: str, output_path: str, reference_mesh_path: str, max_samples: int, source_file: str) -> dict:
    if not asset_path:
        raise RuntimeError("AnimSequence asset path is required.")
    if not output_path:
        raise RuntimeError("Animation output path is required.")

    asset = unreal.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"Could not load AnimSequence: {asset_path}")
    options = unreal.AnimPoseEvaluationOptions()
    try:
        options.set_editor_property("should_retarget", False)
    except Exception:
        pass
    if reference_mesh_path:
        mesh = unreal.load_asset(reference_mesh_path)
        if mesh is not None:
            try:
                options.set_editor_property("optional_skeletal_mesh", mesh)
            except Exception:
                pass

    duration_s = float(asset.get_play_length() or getattr(asset, "sequence_length", 0.0) or 0.0)
    times = _sample_times(duration_s, max_samples)
    first_pose = asset.get_anim_pose_at_time(0.0, options)
    bone_names = [str(name) for name in first_pose.get_bone_names()]
    curves: dict[str, dict] = {}
    for bone_index, bone_name in enumerate(bone_names):
        curves[f"bone_{bone_index}"] = {
            "bone_name": bone_name,
            "translation": {"x": [], "y": [], "z": []},
            "rotation_quat": {"x": [], "y": [], "z": [], "w": []},
            "scale": {"x": [], "y": [], "z": []},
        }

    local_space = unreal.AnimPoseSpaces.LOCAL
    for time_s in times:
        pose = asset.get_anim_pose_at_time(float(time_s), options)
        time_ms = _round(time_s * 1000.0)
        for bone_index, bone_name in enumerate(bone_names):
            transform = pose.get_bone_pose(bone_name, local_space)
            position = _tiger_position(transform.translation)
            rotation = _tiger_quaternion(transform.rotation)
            scale = transform.scale3d
            curve = curves[f"bone_{bone_index}"]
            curve["translation"]["x"].append([time_ms, position[0]])
            curve["translation"]["y"].append([time_ms, position[1]])
            curve["translation"]["z"].append([time_ms, position[2]])
            curve["rotation_quat"]["x"].append([time_ms, rotation[0]])
            curve["rotation_quat"]["y"].append([time_ms, rotation[1]])
            curve["rotation_quat"]["z"].append([time_ms, rotation[2]])
            curve["rotation_quat"]["w"].append([time_ms, rotation[3]])
            curve["scale"]["x"].append([time_ms, _round(scale.x)])
            curve["scale"]["y"].append([time_ms, _round(scale.y)])
            curve["scale"]["z"].append([time_ms, _round(scale.z)])

    name = asset.get_name()
    safe_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name) or "animation"
    clip = {
        "id": safe_id,
        "name": name,
        "source_asset_path": source_file or asset_path,
        "source_mode": "unreal_editor_python_pose",
        "duration_ms": _round(duration_s * 1000.0),
        "frame_count": len(times),
        "frames_per_second": _round(len(times) / max(0.001, duration_s)),
        "sampled_frame_count": len(times),
        "rotation_space": "tiger_basis_quat_v1",
        "bone_names": bone_names,
        "model_curves": curves,
    }
    return {
        "schema": "tigerstudio.ar_pbr.unreal_animation_clip_export.v1",
        "exporter": "unreal_editor_python",
        "animation_clip": clip,
    }


def _main_batch(batch_json: str, batch_out: str) -> dict:
    items = json.loads(batch_json)
    if not isinstance(items, list):
        raise RuntimeError("TIGERSTUDIO_UNREAL_ANIM_BATCH_JSON must be a list.")
    results = []
    for index, item in enumerate(items):
        data = item if isinstance(item, dict) else {}
        out_path = str(data.get("out") or "").strip()
        source_file = str(data.get("source_file") or "").strip()
        try:
            payload = _export_clip(
                str(data.get("asset") or "").strip(),
                out_path,
                str(data.get("reference_mesh") or "").strip(),
                int(data.get("max_samples") or 90),
                source_file,
            )
            _write_payload(out_path, payload)
            results.append({"ok": True, "index": index, "out": out_path, "source_file": source_file})
        except Exception as exc:
            payload = {
                "schema": "tigerstudio.ar_pbr.unreal_animation_clip_export.v1",
                "ok": False,
                "error": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(limit=8),
            }
            if out_path:
                _write_payload(out_path, payload)
            results.append({
                "ok": False,
                "index": index,
                "out": out_path,
                "source_file": source_file,
                "error": type(exc).__name__,
                "message": str(exc),
            })
    payload = {
        "schema": "tigerstudio.ar_pbr.unreal_animation_batch_export.v1",
        "exporter": "unreal_editor_python_batch",
        "ok": all(bool(item.get("ok")) for item in results),
        "count": len(results),
        "results": results,
    }
    if batch_out:
        _write_payload(batch_out, payload)
    return payload


def _main() -> dict:
    batch_json = os.environ.get("TIGERSTUDIO_UNREAL_ANIM_BATCH_JSON", "").strip()
    if batch_json:
        return _main_batch(batch_json, os.environ.get("TIGERSTUDIO_UNREAL_ANIM_BATCH_OUT", "").strip())

    asset_path = os.environ.get("TIGERSTUDIO_UNREAL_ANIM_ASSET", "").strip()
    output_path = os.environ.get("TIGERSTUDIO_UNREAL_ANIM_OUT", "").strip()
    reference_mesh_path = os.environ.get("TIGERSTUDIO_UNREAL_REFERENCE_MESH", "").strip()
    max_samples = int(os.environ.get("TIGERSTUDIO_UNREAL_ANIM_MAX_SAMPLES", "90") or "90")
    source_file = os.environ.get("TIGERSTUDIO_UNREAL_ANIM_SOURCE_FILE", "").strip()
    if not asset_path:
        raise RuntimeError("TIGERSTUDIO_UNREAL_ANIM_ASSET is required.")
    if not output_path:
        raise RuntimeError("TIGERSTUDIO_UNREAL_ANIM_OUT is required.")

    return _export_clip(asset_path, output_path, reference_mesh_path, max_samples, source_file)


def _write_payload(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


try:
    out_path = (
        os.environ.get("TIGERSTUDIO_UNREAL_ANIM_OUT", "").strip()
        or os.environ.get("TIGERSTUDIO_UNREAL_ANIM_BATCH_OUT", "").strip()
    )
    payload = _main()
    if out_path:
        _write_payload(out_path, payload)
    unreal.log("TIGER_UNREAL_ANIM_EXPORT=" + json.dumps({"ok": True, "out": out_path}, ensure_ascii=False))
except Exception as exc:
    out_path = (
        os.environ.get("TIGERSTUDIO_UNREAL_ANIM_OUT", "").strip()
        or os.environ.get("TIGERSTUDIO_UNREAL_ANIM_BATCH_OUT", "").strip()
    )
    payload = {
        "schema": "tigerstudio.ar_pbr.unreal_animation_clip_export.v1",
        "ok": False,
        "error": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(limit=8),
    }
    if out_path:
        _write_payload(out_path, payload)
    unreal.log_error("TIGER_UNREAL_ANIM_EXPORT=" + json.dumps(payload, ensure_ascii=False))
