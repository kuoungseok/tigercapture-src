"""Post-install verification for the VSeeFace virtual camera bridge."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.openseeface_video_source import parse_crop, run_video_source  # noqa: E402
from app.vtuber.virtual_camera_probe import probe_virtual_camera_frames  # noqa: E402
from app.vtuber.vseeface_bridge import default_milica_vrm, default_vseeface_exe  # noqa: E402
from app.vtuber.vseeface_capture_diagnostics import inspect_capture_backends  # noqa: E402
from app.vtuber.vseeface_sidecar_config import (  # noqa: E402
    build_sidecar_settings_values,
    default_vseeface_settings_path,
    write_vseeface_sidecar_settings,
)


STATUS_READY = "ready_for_capture"
STATUS_BLOCKED_REGISTRATION = "blocked_registration_required"
STATUS_CAPTURE_FAILED = "virtual_camera_capture_failed"
STATUS_CAPTURE_BLACK = "virtual_camera_black_frame"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify VSeeFaceCamera after admin registration.")
    parser.add_argument("--video", default=str(ROOT / "debugCapture" / "trump_face_source.mp4"))
    parser.add_argument("--avatar-vrm", default=str(default_milica_vrm(ROOT)))
    parser.add_argument("--vseeface-exe", default=str(default_vseeface_exe(ROOT)))
    parser.add_argument("--port", type=int, default=39540)
    parser.add_argument("--duration-seconds", type=float, default=3.0)
    parser.add_argument("--fps", type=float, default=12.0)
    parser.add_argument("--crop", default="0.32,0.05,0.36,0.75")
    parser.add_argument("--launch-vseeface", action="store_true")
    parser.add_argument("--skip-video-send", action="store_true")
    parser.add_argument("--wait-seconds", type=float, default=8.0)
    parser.add_argument("--camera-max-index", type=int, default=8)
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "vseeface_post_install"))
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "vseeface_post_install_report.json"))
    args = parser.parse_args(argv)

    report = run_post_install_verification(
        video=Path(args.video),
        avatar_vrm=Path(args.avatar_vrm),
        vseeface_exe=Path(args.vseeface_exe),
        port=int(args.port),
        duration_seconds=float(args.duration_seconds),
        fps=float(args.fps),
        crop=parse_crop(args.crop),
        launch_vseeface=bool(args.launch_vseeface),
        skip_video_send=bool(args.skip_video_send),
        wait_seconds=float(args.wait_seconds),
        camera_max_index=int(args.camera_max_index),
        out_dir=Path(args.out_dir),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "status": report["status"], "out": str(out)}, ensure_ascii=False))
    return 0 if report["ok"] else 2


def run_post_install_verification(
    *,
    video: Path,
    avatar_vrm: Path,
    vseeface_exe: Path,
    port: int,
    duration_seconds: float,
    fps: float,
    crop: tuple[float, float, float, float] | None,
    launch_vseeface: bool,
    skip_video_send: bool,
    wait_seconds: float,
    camera_max_index: int,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    preflight = inspect_capture_backends(ROOT)
    status = determine_post_install_status(preflight)
    report: dict[str, Any] = {
        "schema": "tigerstudio.vtuber.vseeface_post_install_verification.v1",
        "ok": False,
        "status": status,
        "preflight": preflight,
        "settings": None,
        "vseeface_process": None,
        "video_source": None,
        "virtual_camera": None,
        "errors": [],
        "warnings": [],
    }
    if status == STATUS_BLOCKED_REGISTRATION:
        report["errors"].append("vseeface_camera_not_registered")
        report["next_action"] = "run_register_vseeface_camera_admin_bat_and_approve_uac"
        return report

    try:
        values = build_sidecar_settings_values(avatar_vrm=avatar_vrm, openseeface_port=port)
        report["settings"] = write_vseeface_sidecar_settings(default_vseeface_settings_path(), values).to_dict()
    except Exception as exc:
        report["warnings"].append(f"settings_write_failed:{exc}")

    if launch_vseeface:
        report["vseeface_process"] = _launch_vseeface(vseeface_exe, wait_seconds)

    if not skip_video_send:
        report["video_source"] = run_video_source(
            video=video,
            port=port,
            duration_seconds=duration_seconds,
            fps=fps,
            try_hard=True,
            detection_threshold=0.2,
            crop=crop,
            realtime=True,
            shutdown_timeout=1.0,
            log_data=out_dir / "openseeface_data.csv",
            log_output=out_dir / "openseeface_output.txt",
        )

    report["virtual_camera"] = probe_virtual_camera_frames(
        max_index=camera_max_index,
        frames_per_camera=8,
        out_dir=out_dir / "camera_frames",
    )
    report["ok"] = bool((report["virtual_camera"] or {}).get("ok"))
    if report["ok"]:
        report["status"] = STATUS_READY
        report["next_action"] = "use_virtual_camera_capture_backend"
    else:
        errors = set(str(item) for item in (report["virtual_camera"] or {}).get("errors") or [])
        if "virtual_camera_black_frame" in errors:
            report["status"] = STATUS_CAPTURE_BLACK
            report["errors"].append("virtual_camera_black_frame")
            report["next_action"] = "fix_vseeface_rendering_or_start_scene"
        else:
            report["status"] = STATUS_CAPTURE_FAILED
            report["errors"].append("virtual_camera_capture_failed")
            report["next_action"] = "confirm_vseeface_camera_enabled_and_vseeface_running"
    return report


def determine_post_install_status(preflight: dict[str, Any]) -> str:
    virtual_camera = preflight.get("virtual_camera") if isinstance(preflight.get("virtual_camera"), dict) else {}
    if not virtual_camera.get("registered"):
        return STATUS_BLOCKED_REGISTRATION
    return STATUS_READY


def _launch_vseeface(vseeface_exe: Path, wait_seconds: float) -> dict[str, Any]:
    if not vseeface_exe.is_file():
        return {"ok": False, "error": "vseeface_exe_missing", "exe": str(vseeface_exe)}
    _stop_vseeface()
    proc = subprocess.Popen(
        [str(vseeface_exe), "-force-d3d11", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "720"],
        cwd=str(vseeface_exe.parent),
    )
    time.sleep(max(0.5, float(wait_seconds)))
    alive = proc.poll() is None
    return {"ok": alive, "pid": proc.pid, "alive": alive, "exe": str(vseeface_exe)}


def _stop_vseeface() -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Process VSeeFace -ErrorAction SilentlyContinue | Stop-Process -Force"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
