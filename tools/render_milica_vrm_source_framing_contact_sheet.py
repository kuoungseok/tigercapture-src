"""Render a small QA contact sheet for source-video VTuber framing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ar_pbr.export_packet_renderer import render_offscreen_gpu_export_frame  # noqa: E402
from app.vtuber.openseeface_motion import (  # noqa: E402
    load_openseeface_frame_size_csv,
    load_openseeface_motion_csv,
    summarize_openseeface_motion,
)
from app.vtuber.source_framing import solve_source_framing_sequence  # noqa: E402
from app.vtuber.source_subject import detect_subject_boxes_for_motion_frames  # noqa: E402
from tools.render_milica_vrm_source_framing_preview import _background, _parse_frame_size  # noqa: E402
from tools.render_milica_vrm_source_framing_preview import _apply_lower_occlusion_preview  # noqa: E402
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


DEFAULT_OUT = ROOT / "debugCapture" / "milica_vrm_source_framing_contact_sheet.png"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a Milica VRM source-framing QA contact sheet.")
    parser.add_argument("--vrm", default=str(DEFAULT_VRM))
    parser.add_argument("--descriptor", default=str(DEFAULT_DESCRIPTOR))
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--video", default="")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--json-out", default="")
    parser.add_argument("--preset", choices=("bust_up", "half_body", "full_body"), default="bust_up")
    parser.add_argument("--slots", default="neutral,head,mouth")
    parser.add_argument("--source-frame-size", default="")
    parser.add_argument("--panel-size", type=int, default=640)
    parser.add_argument("--texture-max-size", type=int, default=1024)
    parser.add_argument("--smoothing", type=float, default=0.35)
    args = parser.parse_args(argv)

    vrm_path = Path(args.vrm)
    csv_path = Path(args.csv)
    descriptor = _load_descriptor(Path(args.descriptor))
    frames = load_openseeface_motion_csv(csv_path)
    if not frames:
        raise SystemExit(f"No OpenSeeFace frames loaded: {csv_path}")
    frame_size = _parse_frame_size(args.source_frame_size) or load_openseeface_frame_size_csv(csv_path) or (640, 360)

    slots = _parse_slots(args.slots)
    selected = [_selected_frame_indices(frames, single_slot=slot)[0] for slot in slots]
    subject_result = None
    subject_boxes = None
    subject_sources = None
    if str(args.video or "").strip():
        subject_result = detect_subject_boxes_for_motion_frames(
            Path(args.video),
            frames,
            source_frame_size=frame_size,
            preset=args.preset,
            detect_indices=selected,
        )
        subject_boxes = subject_result.subject_boxes
        subject_sources = tuple(item.source for item in subject_result.frames)
    framing = solve_source_framing_sequence(
        frames,
        frame_size,
        preset=args.preset,
        smoothing=float(args.smoothing),
        subject_boxes=subject_boxes,
        subject_sources=subject_sources,
    )

    morph_targets = _load_vrm_morph_targets(vrm_path)
    descriptor = _attach_vrm_textures(descriptor, _expected_texture_paths(vrm_path))
    descriptor = _attach_pose_animation(descriptor, frames, upper_body_mode="seated")

    panels: list[Image.Image] = []
    reports: list[dict[str, Any]] = []
    for slot, frame_index in zip(slots, selected):
        frame = frames[frame_index]
        solution = framing[frame_index]
        panel, diagnostics = _render_panel(
            descriptor=_apply_face_morphs(descriptor, morph_targets, frame),
            asset_path=vrm_path,
            time_ms=int(frame.time_ms),
            solution=solution.to_dict(),
            panel_size=max(512, int(args.panel_size)),
            texture_max_size=max(256, int(args.texture_max_size)),
        )
        _label_panel(panel, slot, frame, solution.to_dict())
        panels.append(panel)
        reports.append(
            {
                "slot": slot,
                "frame_index": frame_index,
                "time_ms": int(frame.time_ms),
                "yaw_deg": float(frame.yaw_deg),
                "pitch_deg": float(frame.pitch_deg),
                "roll_deg": float(frame.roll_deg),
                "mouth_open": float(frame.mouth_open),
                "blink": float(max(frame.blink_l, frame.blink_r)),
                "framing": solution.to_dict(),
                "renderer": {
                    "ok": diagnostics.get("ok"),
                    "triangle_count": diagnostics.get("triangle_count"),
                    "warnings": diagnostics.get("warnings", [])[:6],
                    "errors": diagnostics.get("errors", [])[:6],
                },
            }
        )

    image = _compose_contact_sheet(panels, reports, preset=args.preset, video=Path(args.video).name if args.video else "")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    report = {
        "schema": "tigerstudio.vtuber.source_framing_contact_sheet.v1",
        "ok": True,
        "vrm": str(vrm_path),
        "csv": str(csv_path),
        "video": str(args.video or ""),
        "preset": args.preset,
        "source_frame_size": list(frame_size),
        "openseeface": summarize_openseeface_motion(frames),
        "source_subject": subject_result.to_dict() if subject_result is not None else None,
        "selected_frames": reports,
    }
    json_out = Path(args.json_out) if args.json_out else out.with_suffix(".json")
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "json_out": str(json_out)}, ensure_ascii=False))
    return 0


def _render_panel(
    *,
    descriptor: dict[str, Any],
    asset_path: Path,
    time_ms: int,
    solution: dict[str, Any],
    panel_size: int,
    texture_max_size: int,
) -> tuple[Image.Image, dict[str, Any]]:
    base = _background(panel_size, panel_size)
    track = {
        "id": "milica_source_framing_contact",
        "type": "ar_pbr_object",
        "asset_path": str(asset_path),
        "start_ms": 0,
        "end_ms": 60_000,
        "transform": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [float((solution.get("track_rotation") or [-4.0])[0]), 180.0, 0.0],
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
        "asset_descriptors": {track["id"]: descriptor, str(asset_path): descriptor},
        "texture_max_size": texture_max_size,
        "fit_padding": 0.03,
        "enable_shadow_map": False,
        "model_view": dict(solution.get("model_view") or {}),
    }
    image, diagnostics = render_offscreen_gpu_export_frame(
        base,
        time_ms=time_ms,
        ar_tracks=[track],
        camera_solution={"frame_size": [panel_size, panel_size]},
        settings=settings,
    )
    return _apply_lower_occlusion_preview(image.convert("RGBA"), solution.get("model_view") or {}), diagnostics


def _parse_slots(value: str) -> list[str]:
    allowed = {"neutral", "head", "mouth", "blink"}
    out: list[str] = []
    for raw in str(value or "").split(","):
        slot = raw.strip().casefold()
        if slot in allowed and slot not in out:
            out.append(slot)
    return out or ["neutral", "head", "mouth"]


def _label_panel(panel: Image.Image, slot: str, frame: Any, solution: dict[str, Any]) -> None:
    draw = ImageDraw.Draw(panel, "RGBA")
    font, small = _fonts()
    model_view = dict(solution.get("model_view") or {})
    text = f"{slot}  {frame.time_ms / 1000.0:.2f}s"
    sub = f"yaw {frame.yaw_deg:+.1f}  A {frame.mouth_open:.2f}  zoom {float(model_view.get('zoom', 0.0)):.2f}"
    draw.rounded_rectangle((16, 14, panel.width - 16, 76), radius=7, fill=(14, 18, 22, 150))
    draw.text((28, 22), text, font=font, fill=(245, 249, 252, 255))
    draw.text((28, 50), sub, font=small, fill=(195, 208, 216, 255))


def _compose_contact_sheet(panels: list[Image.Image], reports: list[dict[str, Any]], *, preset: str, video: str) -> Image.Image:
    panel_w, panel_h = panels[0].size
    header_h = 96
    footer_h = 66
    canvas = Image.new("RGB", (panel_w * len(panels), header_h + panel_h + footer_h), (20, 24, 29))
    draw = ImageDraw.Draw(canvas)
    title, font = _fonts()
    draw.text((28, 20), "VRM Source-Video Framing QA", font=title, fill=(242, 247, 250))
    subtitle = f"preset={preset} | video={video or 'none'} | source subject boxes drive zoom/pan"
    draw.text((30, 58), subtitle, font=font, fill=(180, 195, 205))
    for index, panel in enumerate(panels):
        canvas.paste(panel.convert("RGB"), (index * panel_w, header_h))
    y = header_h + panel_h + 16
    for index, report in enumerate(reports):
        x = index * panel_w + 28
        framing = report.get("framing") or {}
        diag = dict(framing.get("diagnostics") or {})
        draw.text(
            (x, y),
            f"subject {diag.get('subject_source', 'none')}  box {diag.get('subject_box', [])}",
            font=font,
            fill=(176, 190, 200),
        )
    return canvas


def _fonts() -> tuple[Any, Any]:
    try:
        return (
            ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 24),
            ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 16),
        )
    except OSError:
        fallback = ImageFont.load_default()
        return fallback, fallback


if __name__ == "__main__":
    raise SystemExit(main())
