"""Render Milica VRM with camera framing inferred from a source face video log."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ar_pbr.export_packet_renderer import render_offscreen_gpu_export_frame  # noqa: E402
from app.vtuber.openseeface_motion import (  # noqa: E402
    load_openseeface_frame_size_csv,
    load_openseeface_motion_csv,
    summarize_openseeface_motion,
)
from app.vtuber.source_framing_control import apply_framing_user_offset  # noqa: E402
from app.vtuber.source_framing import (  # noqa: E402
    classify_source_exposure_for_framing,
    solve_source_framing_sequence,
    vrm_visibility_policy_for_source_exposure,
)
from app.vtuber.source_subject import detect_subject_boxes_for_motion_frames  # noqa: E402
from tools.render_milica_vrm_trump_mapping import (  # noqa: E402
    DEFAULT_CSV,
    DEFAULT_DESCRIPTOR,
    DEFAULT_VRM,
    _apply_face_morphs,
    _attach_pose_animation,
    _attach_vrm_textures,
    _expected_texture_paths,
    _load_descriptor,
    _load_vrm_morph_targets,
    _selected_frame_indices,
)


DEFAULT_OUT = ROOT / "debugCapture" / "milica_vrm_source_framing_preview.png"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Milica VRM using source-video framing.")
    parser.add_argument("--vrm", default=str(DEFAULT_VRM))
    parser.add_argument("--descriptor", default=str(DEFAULT_DESCRIPTOR))
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--json-out", default="")
    parser.add_argument("--slot", choices=("neutral", "head", "mouth", "blink"), default="head")
    parser.add_argument("--preset", choices=("auto", "bust_up", "half_body", "full_body"), default="auto")
    parser.add_argument("--video", default="", help="Optional source video used to detect real subject boxes.")
    parser.add_argument("--source-frame-size", default="", help="Optional WIDTHxHEIGHT override.")
    parser.add_argument("--render-size", type=int, default=1440)
    parser.add_argument("--texture-max-size", type=int, default=1024)
    parser.add_argument("--smoothing", type=float, default=0.35)
    parser.add_argument("--subject-detect-every", type=int, default=3)
    parser.add_argument("--subject-detect-scope", choices=("selected", "sequence"), default="selected")
    parser.add_argument("--no-lower-occlusion", action="store_true")
    parser.add_argument("--user-pan-x", type=float, default=0.0)
    parser.add_argument("--user-pan-y", type=float, default=0.0)
    parser.add_argument("--user-pan-z", type=float, default=0.0)
    parser.add_argument("--user-zoom-delta", type=float, default=0.0)
    parser.add_argument("--user-zoom-scale", type=float, default=1.0)
    parser.add_argument("--user-camera-z-delta", type=float, default=0.0)
    parser.add_argument("--user-lower-occlusion-y-delta", type=float, default=0.0)
    args = parser.parse_args(argv)

    vrm_path = Path(args.vrm)
    csv_path = Path(args.csv)
    descriptor = _load_descriptor(Path(args.descriptor))
    frames = load_openseeface_motion_csv(csv_path)
    if not frames:
        raise SystemExit(f"No OpenSeeFace frames loaded: {csv_path}")
    frame_size = _parse_frame_size(args.source_frame_size) or load_openseeface_frame_size_csv(csv_path) or (640, 360)
    frame_index = _selected_frame_indices(frames, single_slot=args.slot)[0]
    frame = frames[frame_index]
    subject_result = None
    subject_boxes = None
    subject_sources = None
    initial_source_exposure = classify_source_exposure_for_framing(frames, frame_size)
    initial_visibility_policy = vrm_visibility_policy_for_source_exposure(
        initial_source_exposure.get("source_exposure") or "unknown",
        requested_preset=args.preset,
        confidence=float(initial_source_exposure.get("confidence", 0.0) or 0.0),
        method=str(initial_source_exposure.get("method") or ""),
    )
    detect_preset = str(initial_visibility_policy["selected_framing_preset"])
    if str(args.video or "").strip():
        subject_result = detect_subject_boxes_for_motion_frames(
            Path(args.video),
            frames,
            source_frame_size=frame_size,
            preset=detect_preset,
            detect_every=max(1, int(args.subject_detect_every)),
            detect_indices=[frame_index] if args.subject_detect_scope == "selected" else None,
        )
        subject_boxes = subject_result.subject_boxes
        subject_sources = tuple(item.source for item in subject_result.frames)
        frames = _apply_subject_shoulder_roll(frames, subject_result)
        frame = frames[frame_index]
    source_exposure = classify_source_exposure_for_framing(frames, frame_size, subject_boxes=subject_boxes)
    visibility_policy = vrm_visibility_policy_for_source_exposure(
        source_exposure.get("source_exposure") or "unknown",
        requested_preset=args.preset,
        confidence=float(source_exposure.get("confidence", 0.0) or 0.0),
        method=str(source_exposure.get("method") or ""),
    )
    resolved_preset = str(visibility_policy["selected_framing_preset"])
    framing = solve_source_framing_sequence(
        frames,
        frame_size,
        preset=resolved_preset,
        smoothing=float(args.smoothing),
        subject_boxes=subject_boxes,
        subject_sources=subject_sources,
    )

    solution = framing[frame_index]
    framing_control = apply_framing_user_offset(solution, {
        "pan_x": float(args.user_pan_x),
        "pan_y": float(args.user_pan_y),
        "pan_z": float(args.user_pan_z),
        "zoom_delta": float(args.user_zoom_delta),
        "zoom_scale": float(args.user_zoom_scale),
        "camera_z_delta": float(args.user_camera_z_delta),
        "lower_occlusion_y_delta": float(args.user_lower_occlusion_y_delta),
    })
    final_model_view = dict(framing_control["final"]["model_view"])

    morph_targets = _load_vrm_morph_targets(vrm_path)
    descriptor = _attach_vrm_textures(descriptor, _expected_texture_paths(vrm_path))
    descriptor = _attach_pose_animation(descriptor, frames, upper_body_mode="seated")
    descriptor = _apply_face_morphs(descriptor, morph_targets, frame)

    size = max(512, int(args.render_size))
    base = _background(size, size)
    track = {
        "id": "milica_source_framing",
        "type": "ar_pbr_object",
        "asset_path": str(vrm_path),
        "start_ms": 0,
        "end_ms": 60_000,
        "transform": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [float(solution.track_rotation[0]), 180.0, 0.0],
            "scale": [4.75, 4.75, 4.75],
        },
        "animation": {"auto_play": True, "loop": False, "speed": 1.0, "clip": "trump_openseeface_pose"},
        "shadow_catcher": False,
        "reflection_catcher": False,
        "occlusion": False,
        "render": {
            "lighting": {
                "light_azimuth": 28.0,
                "light_elevation": 42.0,
                "direct_strength": 0.65,
                "ibl_exposure": 1.15,
                "shadow_strength": 0.0,
                "hdri_id": "studio_small_09",
            }
        },
    }
    settings = {
        "asset_descriptors": {track["id"]: descriptor, str(vrm_path): descriptor},
        "texture_max_size": max(256, int(args.texture_max_size)),
        "fit_padding": 0.03,
        "enable_shadow_map": False,
        "model_view": final_model_view,
    }
    image, diagnostics = render_offscreen_gpu_export_frame(
        base,
        time_ms=int(frame.time_ms),
        ar_tracks=[track],
        camera_solution={"frame_size": [size, size]},
        settings=settings,
    )
    if not args.no_lower_occlusion:
        image = _apply_lower_occlusion_preview(image, final_model_view)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGBA").save(out)

    report = {
        "schema": "tigerstudio.vtuber.milica_source_framing_preview.v1",
        "ok": bool(diagnostics.get("ok")),
        "vrm": str(vrm_path),
        "csv": str(csv_path),
        "source_frame_size": list(frame_size),
        "slot": args.slot,
        "preset": resolved_preset,
        "requested_preset": args.preset,
        "frame_index": frame_index,
        "frame": frame.to_dict(),
        "source_exposure": source_exposure,
        "visibility_policy": visibility_policy,
        "framing": solution.to_dict(),
        "framing_control": framing_control,
        "source_subject": subject_result.to_dict() if subject_result is not None else None,
        "openseeface": summarize_openseeface_motion(frames),
        "renderer": diagnostics,
    }
    json_out = Path(args.json_out) if args.json_out else out.with_suffix(".json")
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(out), "json_out": str(json_out)}, ensure_ascii=False))
    return 0 if report["ok"] else 2


def _apply_subject_shoulder_roll(frames: tuple[Any, ...], subject_result: Any) -> tuple[Any, ...]:
    subject_frames = tuple(getattr(subject_result, "frames", ()) or ())
    if not subject_frames:
        return frames
    out = []
    for index, frame in enumerate(frames):
        if index >= len(subject_frames):
            out.append(frame)
            continue
        roll = float(getattr(subject_frames[index], "shoulder_roll_deg", 0.0) or 0.0)
        if hasattr(frame, "shoulder_roll_deg"):
            out.append(replace(frame, shoulder_roll_deg=roll))
        else:
            out.append(frame)
    return tuple(out)


def _parse_frame_size(value: str) -> tuple[int, int] | None:
    text = str(value or "").strip().lower().replace(" ", "")
    if not text or "x" not in text:
        return None
    left, right = text.split("x", 1)
    try:
        width = int(left)
        height = int(right)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return (width, height)


def _background(width: int, height: int) -> Image.Image:
    image = Image.new("RGBA", (width, height), (58, 66, 72, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    for y in range(height):
        t = y / max(1, height - 1)
        color = (
            int(78 * (1.0 - t) + 38 * t),
            int(88 * (1.0 - t) + 44 * t),
            int(94 * (1.0 - t) + 49 * t),
            255,
        )
        draw.line((0, y, width, y), fill=color)
    return image


def _apply_lower_occlusion_preview(image: Image.Image, model_view: dict[str, Any] | Any) -> Image.Image:
    try:
        lower_y = float(dict(model_view).get("lower_occlusion_y", 1.0))
    except Exception:
        lower_y = 1.0
    if lower_y >= 0.995:
        return image
    out = image.convert("RGBA")
    y = max(0, min(out.height - 1, int(round(out.height * lower_y))))
    draw = ImageDraw.Draw(out, "RGBA")
    draw.rectangle((0, y, out.width, out.height), fill=(38, 45, 50, 255))
    draw.rectangle((0, y, out.width, y + max(2, out.height // 180)), fill=(74, 86, 92, 255))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
