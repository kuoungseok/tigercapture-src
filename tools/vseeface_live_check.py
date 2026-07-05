"""Check local VSeeFace sidecar readiness for VMC receiving."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vmc_protocol import VMC_VSEEFACE_RECEIVER_PORT, VMC_VSEEFACE_SENDER_PORT
from app.vtuber.vseeface_bridge import default_vseeface_exe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose VSeeFace process and VMC receiver readiness.")
    parser.add_argument("--port", type=int, default=VMC_VSEEFACE_RECEIVER_PORT)
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "vseeface_live_check.json"))
    args = parser.parse_args(argv)

    report = {
        "schema": "tigerstudio.vtuber.vseeface_live_check.v1",
        "vseeface_processes": _powershell_json("Get-Process | Where-Object { $_.ProcessName -like '*VSeeFace*' } | Select-Object Id,ProcessName,Responding,MainWindowTitle,StartTime"),
        "udp_ports": _netstat_udp_ports({VMC_VSEEFACE_RECEIVER_PORT, VMC_VSEEFACE_SENDER_PORT, int(args.port)}),
        "settings": _read_settings(),
        "plugins": _check_plugins(),
        "vmc_symbols": _inspect_vmc_symbols(),
        "log": _read_recent_log(),
        "ready": False,
        "errors": [],
        "warnings": [],
    }
    report["ready"] = bool(report["vseeface_processes"]) and any(int(row.get("local_port", 0)) == int(args.port) for row in report["udp_ports"])
    if not report["vseeface_processes"]:
        report["errors"].append("vseeface_process_missing")
    if not any(int(row.get("local_port", 0)) == int(args.port) for row in report["udp_ports"]):
        report["errors"].append("vmc_receiver_port_not_open")
    if report["settings"].get("duplicate_sections"):
        report["warnings"].append("settings_ini_duplicate_sections")
    if report["settings"].get("openseeface_tracking_endpoint"):
        report["warnings"].append("settings_ip_port_are_openseeface_tracking_not_vmc")
    if report["plugins"].get("disabled_leap_plugins"):
        report["warnings"].append("leap_plugins_disabled")
    if report["vmc_symbols"].get("exists") and report["vmc_symbols"].get("missing_required"):
        report["warnings"].append("vmc_symbols_missing")
    if report["log"].get("leap_null_reference_count", 0):
        report["warnings"].append("leap_null_reference_errors")
    if report["log"].get("leap_service_retry_count", 0):
        report["warnings"].append("leap_service_retry")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "ready": report["ready"],
        "process_count": len(report["vseeface_processes"]),
        "udp_ports": report["udp_ports"],
        "errors": report["errors"],
        "warnings": report["warnings"],
        "out": str(out),
    }, ensure_ascii=False))
    return 0 if report["ready"] else 2


def _powershell_json(script: str) -> list[dict]:
    command = ["powershell", "-NoProfile", "-Command", f"{script} | ConvertTo-Json -Depth 4"]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except Exception:
        return []
    text = (completed.stdout or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _netstat_udp_ports(ports: set[int]) -> list[dict]:
    try:
        completed = subprocess.run(["netstat", "-ano", "-p", "udp"], capture_output=True, text=True, timeout=10, check=False)
    except Exception:
        return []
    rows: list[dict] = []
    for line in (completed.stdout or "").splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0].upper() != "UDP":
            continue
        local = parts[1]
        pid = parts[-1]
        local_port = _parse_port(local)
        if local_port in ports:
            rows.append({"local": local, "local_port": local_port, "pid": int(pid) if pid.isdigit() else pid})
    return rows


def _parse_port(endpoint: str) -> int:
    try:
        return int(endpoint.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return 0


def _read_settings() -> dict:
    path = Path.home() / "AppData" / "LocalLow" / "Emiliana_vt" / "VSeeFace" / "settings.ini"
    wanted_keys = {
        "AvatarDirectory",
        "AvatarFile",
        "IP",
        "Port",
        "CameraName",
        "Camera",
        "AutoBlink",
        "SmoothAutoBlink",
        "GazeStrength",
        "LeapMotionMode",
        "TrackLeapMotion",
    }
    avatar_list = path.with_name("avatarList.ini")
    out = {
        "path": str(path),
        "exists": path.is_file(),
        "duplicate_sections": False,
        "leap_motion_mode": "",
        "values": {},
        "openseeface_tracking_endpoint": {},
        "avatar_list": {
            "path": str(avatar_list),
            "exists": avatar_list.is_file(),
            "entries": [],
        },
    }
    if avatar_list.is_file():
        out["avatar_list"]["entries"] = [
            line.strip()
            for line in avatar_list.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
    if not path.is_file():
        return out
    text = path.read_text(encoding="utf-8", errors="replace")
    out["duplicate_sections"] = text.count("[OpenSeeDemo]") > 1
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in wanted_keys:
            out["values"][key] = value.strip()
        if key == "LeapMotionMode":
            out["leap_motion_mode"] = value.strip()
    values = out["values"]
    if values.get("IP") or values.get("Port"):
        out["openseeface_tracking_endpoint"] = {
            "host": values.get("IP", ""),
            "port": values.get("Port", ""),
            "note": "settings.ini IP/Port configure VSeeFace OpenSeeFace tracking input, not the VMC receiver",
        }
    return out


def _check_plugins() -> dict:
    plugin_dir = default_vseeface_exe(ROOT).parent / "VSeeFace_Data" / "Plugins" / "x86_64"
    disabled = sorted(path.name for path in plugin_dir.glob("LeapCV*.codex_disabled"))
    present = sorted(path.name for path in plugin_dir.glob("LeapCV*.dll"))
    return {
        "plugin_dir": str(plugin_dir),
        "present_leap_plugins": present,
        "disabled_leap_plugins": disabled,
    }


def _inspect_vmc_symbols(root: Path = ROOT) -> dict:
    assembly = default_vseeface_exe(root).parent / "VSeeFace_Data" / "Managed" / "Assembly-CSharp.dll"
    required = [
        "VMCReceiverManager",
        "SetVMCEnabled",
        "SetVMCPort",
        "EVMC4U.ExternalReceiver",
        "/VMC/Ext/Bone/Pos",
        "/VMC/Ext/Blend/Val",
    ]
    optional = [
        "SetVMCIP",
        "VMCSendData",
        "/VMC/Ext/Rcv",
        "/VMC/Ext/OK",
        "/VMC/Ext/T",
    ]
    out = {
        "assembly_path": str(assembly),
        "exists": assembly.is_file(),
        "found": {},
        "missing_required": [],
        "runtime_receiver_api_present": False,
    }
    if not assembly.is_file():
        return out
    data = assembly.read_bytes()
    symbols = required + optional
    for symbol in symbols:
        out["found"][symbol] = _binary_contains_text(data, symbol)
    out["missing_required"] = [symbol for symbol in required if not out["found"].get(symbol)]
    out["runtime_receiver_api_present"] = all(
        out["found"].get(symbol)
        for symbol in ("VMCReceiverManager", "SetVMCEnabled", "SetVMCPort", "EVMC4U.ExternalReceiver")
    )
    return out


def _binary_contains_text(data: bytes, text: str) -> bool:
    raw = text.encode("utf-8", errors="ignore")
    wide = text.encode("utf-16le", errors="ignore")
    return raw in data or wide in data


def _read_recent_log() -> dict:
    path = Path.home() / "AppData" / "LocalLow" / "Emiliana_vt" / "VSeeFace" / "Player.log"
    out = {
        "path": str(path),
        "exists": path.is_file(),
        "leap_service_retry_count": 0,
        "leap_null_reference_count": 0,
        "recent_tail": "",
    }
    if not path.is_file():
        return out
    text = path.read_text(encoding="utf-8", errors="replace")
    tail = "\n".join(text.splitlines()[-80:])
    out["recent_tail"] = tail
    out["leap_service_retry_count"] = tail.count("Leap Service not connected")
    out["leap_null_reference_count"] = tail.count("Leap.Unity.LeapServiceProvider") + tail.count("FinalIKOrionLeapHandController")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
