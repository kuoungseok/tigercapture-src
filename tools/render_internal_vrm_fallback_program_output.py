"""Render Program Output through the internal VRM fallback path."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.internal_vrm_fallback import (  # noqa: E402
    composite_internal_vrm_fallback_program_frame,
    render_internal_vrm_fallback_frame,
)
from app.vtuber.vseeface_bridge import (  # noqa: E402
    CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK,
    INTERNAL_VRM_FALLBACK_SOURCE_ID,
    build_vseeface_bridge_status,
    default_vseeface_bridge_config,
)


DEFAULT_CAPTURE_REPORT = ROOT / "debugCapture" / "vseeface_post_install_with_video_report.json"
DEFAULT_OUT = ROOT / "debugCapture" / "internal_vrm_fallback_program_output.png"
DEFAULT_JSON_OUT = ROOT / "debugCapture" / "internal_vrm_fallback_program_output.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Program Output with VSeeFace black capture suppressed.")
    parser.add_argument("--capture-report", default=str(DEFAULT_CAPTURE_REPORT))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--time-ms", type=int, default=0)
    parser.add_argument("--renderer", choices=("software-zbuffer", "full-gpu"), default="software-zbuffer")
    args = parser.parse_args(argv)

    width = max(1, int(args.width))
    height = max(1, int(args.height))
    capture = _load_capture_report(Path(args.capture_report))
    status = build_vseeface_bridge_status(
        default_vseeface_bridge_config(ROOT),
        capture_diagnostics=capture,
        width=width,
        height=height,
        fps=30.0,
    )
    scene = _force_green_chroma_background(dict(status["scene"]))
    fallback_source = _fallback_source(scene)
    fallback_frame, render_diag = render_internal_vrm_fallback_frame(
        fallback_source,
        time_ms=int(args.time_ms),
        width=width,
        height=height,
        renderer=str(args.renderer),
    )
    black_vseeface_frame = np.zeros((height, width, 3), dtype=np.uint8)
    program, composite_diag = composite_internal_vrm_fallback_program_frame(
        scene,
        np.asarray(fallback_frame.convert("RGBA")),
        vseeface_frame=black_vseeface_frame,
        source_id=str(fallback_source.get("id") or INTERNAL_VRM_FALLBACK_SOURCE_ID),
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(program[:, :, :3]).save(out)

    report = {
        "schema": "tigerstudio.vtuber.internal_vrm_fallback_program_output.v1",
        "ok": bool(render_diag.get("ok")) and bool(composite_diag.get("ok")),
        "out": str(out),
        "status_state": status.get("state"),
        "capture_status": (status.get("capture") or {}).get("status"),
        "program_output_excludes_performance_source": True,
        "vseeface_black_frame_input": True,
        "internal_vrm_fallback_source_id": str(fallback_source.get("id") or INTERNAL_VRM_FALLBACK_SOURCE_ID),
        "render": render_diag,
        "composite": composite_diag,
        "scene": scene,
    }
    json_out = Path(args.json_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(out), "json_out": str(json_out)}, ensure_ascii=False))
    return 0 if report["ok"] else 2


def _load_capture_report(path: Path) -> dict[str, Any]:
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    return {"ok": False, "status": CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK, "errors": [CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK]}


def _fallback_source(scene: Mapping[str, Any]) -> Mapping[str, Any]:
    for source in scene.get("sources") or []:
        if isinstance(source, Mapping) and str(source.get("id") or "") == INTERNAL_VRM_FALLBACK_SOURCE_ID:
            return source
    return {
        "id": INTERNAL_VRM_FALLBACK_SOURCE_ID,
        "settings": {"program_output": True, "requires_vseeface_capture": False},
    }


def _force_green_chroma_background(scene: dict[str, Any]) -> dict[str, Any]:
    canvas = scene.get("canvas") if isinstance(scene.get("canvas"), dict) else {}
    canvas["background"] = [0, 255, 0, 255]
    scene["canvas"] = canvas
    for source in scene.get("sources") or []:
        if not isinstance(source, dict) or str(source.get("id") or "") != "background":
            continue
        settings = source.get("settings") if isinstance(source.get("settings"), dict) else {}
        settings["color"] = [0, 255, 0, 255]
        source["settings"] = settings
    return scene


if __name__ == "__main__":
    raise SystemExit(main())
