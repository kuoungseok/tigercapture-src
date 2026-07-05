"""Write a VSeeFace bridge status JSON report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vseeface_bridge import (  # noqa: E402
    CAPTURE_STATUS_READY,
    CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK,
    VSeeFaceBridgeConfig,
    build_vseeface_bridge_status,
    default_vseeface_bridge_config,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write VSeeFace bridge status JSON.")
    parser.add_argument("--config", default="", help="Optional bridge config JSON.")
    parser.add_argument("--capture-report", default="", help="Optional capture diagnostics JSON.")
    parser.add_argument("--capture-status", default="", help="Synthetic status for local smoke checks.")
    parser.add_argument("--input-report", default="", help="Optional tracking input diagnostics JSON.")
    parser.add_argument("--project-snapshot", default="", help="Optional project snapshot JSON for media-pool/timeline input choices.")
    parser.add_argument(
        "--camera-device",
        action="append",
        default=[],
        help="Optional camera device label or id=name pair. Can be passed multiple times.",
    )
    parser.add_argument("--out", default="", help="Optional output JSON path.")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args(argv)

    config = _load_config(args.config)
    capture = _load_capture_diagnostics(args.capture_report, args.capture_status)
    input_diagnostics = _load_optional_json(args.input_report)
    project_snapshot = _load_project_snapshot(args.project_snapshot)
    camera_devices = _parse_camera_devices(args.camera_device)
    report = build_vseeface_bridge_status(
        config,
        capture_diagnostics=capture,
        input_diagnostics=input_diagnostics,
        project_snapshot=project_snapshot,
        camera_devices=camera_devices,
        width=int(args.width),
        height=int(args.height),
        fps=float(args.fps),
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(json.dumps({"ok": report["ok"], "state": report["state"], "out": str(out)}, ensure_ascii=False))
    else:
        print(text)
    return 0 if report["ok"] else 2


def _load_config(path_text: str) -> VSeeFaceBridgeConfig:
    if not path_text:
        return default_vseeface_bridge_config(ROOT)
    path = Path(path_text)
    return VSeeFaceBridgeConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))


def _load_capture_diagnostics(report_path: str, synthetic_status: str) -> dict[str, Any] | None:
    if report_path:
        return json.loads(Path(report_path).read_text(encoding="utf-8"))
    if synthetic_status == CAPTURE_STATUS_READY:
        return {"ok": True, "status": "ready_for_capture", "usable_window_capture": True}
    if synthetic_status == CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK:
        return {"ok": False, "status": synthetic_status, "errors": [synthetic_status]}
    return None


def _load_project_snapshot(path_text: str) -> dict[str, Any] | None:
    if not path_text:
        return None
    return json.loads(Path(path_text).read_text(encoding="utf-8"))


def _load_optional_json(path_text: str) -> dict[str, Any] | None:
    if not path_text:
        return None
    return json.loads(Path(path_text).read_text(encoding="utf-8"))


def _parse_camera_devices(rows: list[str]) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    for idx, raw in enumerate(rows or []):
        text = str(raw or "").strip()
        if not text:
            continue
        if "=" in text:
            device_id, name = text.split("=", 1)
        else:
            device_id, name = f"device_{idx}", text
        devices.append({"id": device_id.strip() or f"device_{idx}", "name": name.strip() or text, "index": idx})
    return devices


if __name__ == "__main__":
    raise SystemExit(main())
