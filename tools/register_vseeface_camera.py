"""Prepare or launch VSeeFaceCamera DirectShow registration.

The actual registration requires Windows administrator rights. This tool never
blocks indefinitely on UAC; it writes a small admin batch and can optionally
launch it visibly for the user to approve.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vseeface_capture_diagnostics import inspect_capture_backends  # noqa: E402
from app.vtuber.vseeface_bridge import default_vseeface_exe  # noqa: E402


UNITY_CAPTURE_DIR = default_vseeface_exe(ROOT).parent / "VSeeFace_Data" / "StreamingAssets" / "UnityCapture"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or launch VSeeFaceCamera registration.")
    parser.add_argument("--launch", action="store_true", help="Launch the admin installer through UAC.")
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "vseeface_camera_registration_plan.json"))
    args = parser.parse_args(argv)

    before = inspect_capture_backends(ROOT)
    batch = _write_admin_batch()
    result = {
        "schema": "tigerstudio.vtuber.vseeface_camera_registration.v1",
        "ok": False,
        "admin_required": True,
        "registration_batch": str(batch),
        "before": before,
        "launched": False,
        "launch_error": "",
        "after": None,
        "next_action": "run_registration_batch_as_admin",
    }
    if before.get("virtual_camera", {}).get("registered"):
        result.update({
            "ok": True,
            "admin_required": False,
            "next_action": "capture_vseeface_camera_device",
        })
    elif args.launch:
        launched, error = _launch_admin_batch(batch)
        result["launched"] = launched
        result["launch_error"] = error
        result["next_action"] = "approve_uac_then_rerun_preflight" if launched else "run_registration_batch_as_admin"
    result["after"] = inspect_capture_backends(ROOT)
    if result["after"].get("virtual_camera", {}).get("registered"):
        result["ok"] = True
        result["admin_required"] = False
        result["next_action"] = "capture_vseeface_camera_device"

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": result["ok"],
        "launched": result["launched"],
        "admin_required": result["admin_required"],
        "next_action": result["next_action"],
        "out": str(out),
    }, ensure_ascii=False))
    return 0 if result["ok"] else 2


def _write_admin_batch() -> Path:
    dll32 = UNITY_CAPTURE_DIR / "VSeeFaceCamera32bit.dll"
    dll64 = UNITY_CAPTURE_DIR / "VSeeFaceCamera64bit.dll"
    out = ROOT / "debugCapture" / "register_vseeface_camera_admin.bat"
    lines = [
        "@echo off",
        "setlocal",
        "echo Registering VSeeFaceCamera DirectShow filters...",
        f'cd /d "{UNITY_CAPTURE_DIR}"',
        f'"%SystemRoot%\\SysWOW64\\regsvr32.exe" "{dll32}" "/i:UnityCaptureName=VSeeFaceCamera"',
        "if errorlevel 1 goto failed",
        f'"%SystemRoot%\\System32\\regsvr32.exe" "{dll64}" "/i:UnityCaptureName=VSeeFaceCamera"',
        "if errorlevel 1 goto failed",
        "echo.",
        "echo VSeeFaceCamera registration completed.",
        "pause",
        "exit /b 0",
        ":failed",
        "echo.",
        "echo VSeeFaceCamera registration failed.",
        "pause",
        "exit /b 1",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\r\n".join(lines) + "\r\n", encoding="ascii")
    return out


def _launch_admin_batch(batch: Path) -> tuple[bool, str]:
    try:
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Start-Process -FilePath '{batch}' -Verb RunAs",
            ],
            cwd=str(ROOT),
        )
        return True, ""
    except Exception as exc:
        return False, repr(exc)


if __name__ == "__main__":
    raise SystemExit(main())
