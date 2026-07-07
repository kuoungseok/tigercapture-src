"""Diagnostics for VSeeFace capture backend selection."""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Mapping


CAPTURE_READY = "window_capture_ready"
CAPTURE_BLACK = "window_capture_black"
GRAPHICS_FAILED = "graphics_backend_failed"
CAPTURE_UNUSABLE = "window_capture_unusable"
BACKEND_READY = "ready"
BACKEND_NEEDS_CONFIGURATION = "needs_configuration"
BACKEND_NEEDS_INSTALL = "needs_install"
BACKEND_UNAVAILABLE = "unavailable"


def analyze_graphics_probe_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Classify a VSeeFace graphics probe report.

    The probe is intentionally conservative: a bright Unity error dialog is not
    a usable capture backend. A backend is usable only when its content is
    non-black and its log does not contain Unity graphics initialization errors.
    """
    variants = report.get("variants") if isinstance(report.get("variants"), list) else []
    usable: list[dict[str, Any]] = []
    black: list[dict[str, Any]] = []
    graphics_failed: list[dict[str, Any]] = []
    virtual_camera_black: list[dict[str, Any]] = []
    virtual_camera_usable: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for item in variants:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or "")
        flags = [str(flag) for flag in item.get("flags") or []]
        log_tail = str(item.get("log_tail") or "")
        printwindow = item.get("printwindow") if isinstance(item.get("printwindow"), Mapping) else {}
        virtual_camera = item.get("virtual_camera") if isinstance(item.get("virtual_camera"), Mapping) else {}
        content = printwindow.get("content") if isinstance(printwindow.get("content"), Mapping) else {}
        error_dialog = _looks_like_unity_error_dialog(printwindow, content)
        nonblack = bool(printwindow.get("content_nonblack")) and not error_dialog
        virtual_opened = bool(virtual_camera.get("opened"))
        virtual_nonblack = bool(virtual_camera.get("content_nonblack"))
        mean_luma = float(content.get("mean_luma", 0.0) or 0.0)
        unique_colors = int(content.get("unique_colors", 0) or 0)
        row = {
            "name": name,
            "flags": flags,
            "mean_luma": mean_luma,
            "unique_colors": unique_colors,
            "content_nonblack": nonblack,
            "virtual_camera_opened": virtual_opened,
            "virtual_camera_nonblack": virtual_nonblack,
            "graphics_failed": _has_graphics_failure(log_tail) or error_dialog,
        }
        rows.append(row)
        if row["graphics_failed"]:
            graphics_failed.append(row)
        elif nonblack:
            usable.append(row)
        else:
            black.append(row)
        if virtual_nonblack:
            virtual_camera_usable.append(row)
        elif virtual_opened:
            virtual_camera_black.append(row)

    if usable:
        status = CAPTURE_READY
        ok = True
    elif black and graphics_failed:
        status = CAPTURE_UNUSABLE
        ok = False
    elif black:
        status = CAPTURE_BLACK
        ok = False
    elif graphics_failed:
        status = GRAPHICS_FAILED
        ok = False
    else:
        status = CAPTURE_UNUSABLE
        ok = False

    recommendations = []
    if not ok:
        recommendations.extend([
            "switch_capture_method_to_spout2_or_virtual_camera",
            "do_not_block_broadcast_scene_on_window_capture",
            "keep_vseeface_as_external_sidecar",
        ])
    return {
        "schema": "tigerstudio.vtuber.vseeface_capture_diagnostics.v1",
        "ok": ok,
        "status": status,
        "usable_window_capture": bool(usable),
        "usable_virtual_camera": bool(virtual_camera_usable),
        "usable_variants": usable,
        "black_variants": black,
        "virtual_camera_usable_variants": virtual_camera_usable,
        "virtual_camera_black_variants": virtual_camera_black,
        "graphics_failed_variants": graphics_failed,
        "variants": rows,
        "recommendations": recommendations,
    }


def inspect_capture_backends(root: str | Path | None = None) -> dict[str, Any]:
    """Inspect local non-window VSeeFace capture backend availability."""
    from app.vtuber.vseeface_bridge import default_vseeface_exe

    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    vseeface_root = default_vseeface_exe(root_path).parent
    plugin_dir = vseeface_root / "VSeeFace_Data" / "Plugins" / "x86_64"
    unity_capture_dir = vseeface_root / "VSeeFace_Data" / "StreamingAssets" / "UnityCapture"
    obs_root = Path("C:/Program Files/obs-studio")
    obs_plugins = obs_root / "obs-plugins" / "64bit"
    obs_data_plugins = obs_root / "data" / "obs-plugins"

    spout_sender = plugin_dir / "NativeSpoutPlugin.dll"
    spout_receiver_candidates = []
    if obs_plugins.is_dir():
        spout_receiver_candidates.extend(obs_plugins.glob("*[Ss]pout*"))
    if obs_data_plugins.is_dir():
        spout_receiver_candidates.extend(obs_data_plugins.glob("**/*[Ss]pout*"))
    virtual_camera_dlls = [
        unity_capture_dir / "VSeeFaceCamera32bit.dll",
        unity_capture_dir / "VSeeFaceCamera64bit.dll",
    ]
    virtual_camera_registered = _registry_contains_any(("VSeeFaceCamera", "Unity Capture"))
    virtual_camera_registration_paths = _registry_inproc_server_paths(virtual_camera_registered)
    virtual_camera_registration_paths_exist = [
        str(path) for path in virtual_camera_registration_paths if Path(path).is_file()
    ]
    current_capture_dlls = {str(path.resolve()).casefold() for path in virtual_camera_dlls}
    current_registration_matches = [
        str(path)
        for path in virtual_camera_registration_paths
        if str(Path(path).resolve()).casefold() in current_capture_dlls
    ]
    registration_has_stale_paths = bool(virtual_camera_registration_paths) and (
        len(virtual_camera_registration_paths_exist) < len(virtual_camera_registration_paths)
        or len(current_registration_matches) < len(virtual_camera_registration_paths)
    )
    registration_stale = bool(virtual_camera_registration_paths) and not bool(current_registration_matches)
    registration_usable = bool(virtual_camera_registered) and not registration_stale
    obs_installed = (obs_root / "bin" / "64bit" / "obs64.exe").is_file()
    obs_virtual_camera_bundle = any(obs_data_plugins.glob("**/obs-virtualcam-module64.dll")) if obs_data_plugins.is_dir() else False
    payload = {
        "schema": "tigerstudio.vtuber.capture_backend_preflight.v1",
        "vseeface_root": str(vseeface_root),
        "spout2": {
            "sender_plugin": str(spout_sender),
            "sender_available": spout_sender.is_file(),
            "receiver_candidates": [str(path) for path in spout_receiver_candidates],
            "receiver_available": bool(spout_receiver_candidates),
        },
        "virtual_camera": {
            "bundle_dir": str(unity_capture_dir),
            "install_script": str(unity_capture_dir / "Install.bat"),
            "bundle_available": all(path.is_file() for path in virtual_camera_dlls),
            "registered": bool(virtual_camera_registered),
            "registration_usable": registration_usable,
            "registration_stale": registration_stale,
            "registration_has_stale_paths": registration_has_stale_paths,
            "registration_paths": [str(path) for path in virtual_camera_registration_paths],
            "registration_paths_exist": virtual_camera_registration_paths_exist,
            "registration_matches_current_install": current_registration_matches,
            "registration_matches": virtual_camera_registered,
            "requires_admin_registration": all(path.is_file() for path in virtual_camera_dlls) and not registration_usable,
        },
        "obs": {
            "installed": obs_installed,
            "obs64": str(obs_root / "bin" / "64bit" / "obs64.exe"),
            "virtual_camera_bundle_available": obs_virtual_camera_bundle,
        },
    }
    payload["decision"] = choose_capture_backend(payload)
    return payload


def choose_capture_backend(preflight: Mapping[str, Any], *, window_capture_ok: bool = False) -> dict[str, Any]:
    """Choose a capture backend without mutating the system."""
    spout = preflight.get("spout2") if isinstance(preflight.get("spout2"), Mapping) else {}
    virtual_camera = preflight.get("virtual_camera") if isinstance(preflight.get("virtual_camera"), Mapping) else {}
    if window_capture_ok:
        return {
            "preferred_backend": "window_capture",
            "status": BACKEND_READY,
            "reason": "window_capture_probe_passed",
            "next_action": "use_window_capture",
        }
    if bool(spout.get("sender_available")) and bool(spout.get("receiver_available")):
        return {
            "preferred_backend": "spout2",
            "status": BACKEND_NEEDS_CONFIGURATION,
            "reason": "spout_sender_and_receiver_available",
            "next_action": "enable_spout2_in_vseeface_and_capture_sender",
        }
    if bool(virtual_camera.get("registration_stale")):
        return {
            "preferred_backend": "virtual_camera",
            "status": BACKEND_NEEDS_INSTALL,
            "reason": "vseeface_camera_registered_to_stale_path",
            "next_action": "rerun_vseeface_camera_install_bat_as_admin",
        }
    registration_usable = bool(virtual_camera.get("registration_usable", virtual_camera.get("registered")))
    if registration_usable:
        return {
            "preferred_backend": "virtual_camera",
            "status": BACKEND_NEEDS_CONFIGURATION,
            "reason": "vseeface_camera_registered",
            "next_action": "enable_vseeface_virtual_camera_and_capture_device",
        }
    if bool(virtual_camera.get("requires_admin_registration")):
        return {
            "preferred_backend": "virtual_camera",
            "status": BACKEND_NEEDS_INSTALL,
            "reason": "vseeface_camera_bundle_present_but_not_registered",
            "next_action": "run_vseeface_camera_install_bat_as_admin",
        }
    if bool(spout.get("sender_available")):
        return {
            "preferred_backend": "spout2",
            "status": BACKEND_NEEDS_INSTALL,
            "reason": "spout_sender_available_but_no_receiver",
            "next_action": "install_or_bundle_spout2_receiver",
        }
    return {
        "preferred_backend": "none",
        "status": BACKEND_UNAVAILABLE,
        "reason": "no_non_window_capture_backend_available",
        "next_action": "keep_preview_noop_and_show_backend_setup",
    }


def _has_graphics_failure(log_tail: str) -> bool:
    markers = [
        "InitializeEngineGraphics failed",
        "PlayerInitEngineGraphics",
        "Forced GfxDevice",
    ]
    return any(marker in log_tail for marker in markers)


def _looks_like_unity_error_dialog(printwindow: Mapping[str, Any], content: Mapping[str, Any]) -> bool:
    size = printwindow.get("size") if isinstance(printwindow.get("size"), list) else []
    width = int(size[0]) if len(size) >= 1 else 0
    height = int(size[1]) if len(size) >= 2 else 0
    mean_luma = float(content.get("mean_luma", 0.0) or 0.0)
    unique_colors = int(content.get("unique_colors", 0) or 0)
    return 0 < width <= 700 and 0 < height <= 450 and mean_luma > 120.0 and unique_colors > 100


def _registry_contains_any(needles: tuple[str, ...]) -> list[str]:
    if not sys.platform.startswith("win"):
        return []
    try:
        import winreg
    except Exception:
        return []
    matches: list[str] = []
    roots = [
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\CLSID"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Classes\CLSID"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Classes\CLSID"),
    ]
    lowered = tuple(item.casefold() for item in needles)
    for hive, key_path in roots:
        try:
            with winreg.OpenKey(hive, key_path) as root_key:
                _scan_registry_key(winreg, root_key, key_path, lowered, matches, depth=2)
        except OSError:
            continue
    return sorted(set(matches))


def _registry_inproc_server_paths(matches: list[str]) -> list[str]:
    paths: list[str] = []
    for row in matches:
        path_text, sep, value = str(row or "").rpartition("=")
        if not sep:
            continue
        if "inprocserver32" not in path_text.casefold():
            continue
        value = value.strip().strip('"')
        if value:
            paths.append(value)
    return sorted(set(paths))


def _scan_registry_key(winreg, key, path: str, needles: tuple[str, ...], matches: list[str], *, depth: int) -> None:
    if depth < 0 or len(matches) >= 32:
        return
    try:
        value, _kind = winreg.QueryValueEx(key, "")
        text = str(value).casefold()
        if any(needle in text for needle in needles):
            matches.append(f"{path}={value}")
    except OSError:
        pass
    index = 0
    while len(matches) < 32:
        try:
            name = winreg.EnumKey(key, index)
        except OSError:
            break
        index += 1
        try:
            with winreg.OpenKey(key, name) as child:
                _scan_registry_key(winreg, child, f"{path}\\{name}", needles, matches, depth=depth - 1)
        except OSError:
            continue
