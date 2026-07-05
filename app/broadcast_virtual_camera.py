"""Virtual-camera planning for Discord and video-call Program Output."""
from __future__ import annotations

import os
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


VIRTUAL_CAMERA_SCHEMA = "tigerstudio.broadcast.virtual_camera_plan.v1"
VIRTUAL_CAMERA_DISCOVERY_SCHEMA = "tigerstudio.broadcast.virtual_camera_discovery.v1"
OBS_BRIDGE_SCHEMA = "tigerstudio.broadcast.obs_virtual_camera_bridge.v1"
OBS_BRIDGE_GATE_SCHEMA = "tigerstudio.broadcast.obs_virtual_camera_bridge_gate.v1"
OBS_BRIDGE_DRY_RUN_SCHEMA = "tigerstudio.broadcast.obs_virtual_camera_bridge_dry_run.v1"
OBS_BRIDGE_EXECUTE_SCHEMA = "tigerstudio.broadcast.obs_virtual_camera_bridge_execute.v1"

BACKEND_WINDOW_SHARE = "program_output_window_share"
BACKEND_PYVIRTUALCAM = "pyvirtualcam_device"
BACKEND_OBS = "obs_virtual_camera"
BACKEND_SPOUT = "spout2"
BACKEND_NDI = "ndi"

DEFAULT_PROGRAM_OUTPUT_WINDOW_TITLE = "Tiger Studio Program Output"
DEFAULT_OBS_SCENE_NAME = "Tiger Studio Program Output"
DEFAULT_OBS_SOURCE_NAME = "Tiger Studio Program Output"
DEFAULT_OBS_WEBSOCKET_HOST = "127.0.0.1"
DEFAULT_OBS_WEBSOCKET_PORT = 4455


def virtual_camera_output_plan(
    payload: Mapping[str, Any] | None = None,
    *,
    installed_backends: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a non-invasive output plan for Discord/video-call apps.

    The app must not silently install drivers. This plan tells the UI whether a
    virtual-camera backend is available and keeps window sharing as the safe
    fallback.
    """
    data = dict(payload or {})
    discovery = None
    if installed_backends is None and bool(data.get("discover", False)):
        discovery = discover_installed_virtual_camera_backends(data)
        installed = dict(discovery.get("installed_backends") or {})
    else:
        installed = dict(installed_backends or data.get("installed_backends") or {})
    preferred = str(data.get("backend") or data.get("preferred_backend") or "").strip()
    auto_select_installed = bool(data.get("auto_select_installed_backend", False))
    candidates = [
        _backend_row(BACKEND_PYVIRTUALCAM, "Virtual camera device", installed),
        _backend_row(BACKEND_OBS, "OBS Virtual Camera", installed),
        _backend_row(BACKEND_SPOUT, "Spout2 sender", installed),
        _backend_row(BACKEND_NDI, "NDI output", installed),
        {
            "id": BACKEND_WINDOW_SHARE,
            "label": "Program Output window share",
            "available": True,
            "requires_install": False,
            "driver": False,
            "recommended": False,
        },
    ]
    selected = next((row for row in candidates if row["id"] == preferred and row["available"]), None)
    if selected is None and auto_select_installed:
        selected = next((row for row in candidates if row["id"] != BACKEND_WINDOW_SHARE and row["available"]), None)
    if selected is None:
        selected = candidates[-1]
    warnings: list[str] = []
    if selected["id"] == BACKEND_WINDOW_SHARE:
        warnings.append("No virtual-camera backend is active; share the Program Output window in Discord/video-call apps.")
    operator_steps = _operator_steps(selected["id"])
    obs_bridge = None
    if selected["id"] == BACKEND_OBS:
        obs_bridge = obs_virtual_camera_bridge_plan(data, installed_backends=installed)
    result = {
        "schema": VIRTUAL_CAMERA_SCHEMA,
        "selected_backend": selected["id"],
        "selected": selected,
        "available": bool(selected["available"]),
        "manual_fallback": selected["id"] == BACKEND_WINDOW_SHARE,
        "output_contract": _output_contract(selected["id"]),
        "operator_steps": operator_steps,
        "candidates": candidates,
        "warnings": warnings,
        "install_policy": "user_approved_only",
        "default_backend_policy": "obs_free_first",
        "obs_optional": True,
    }
    if discovery is not None:
        result["discovery"] = discovery
    if obs_bridge is not None:
        result["obs_bridge"] = obs_bridge
    return result


def discover_installed_virtual_camera_backends(
    payload: Mapping[str, Any] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    path_exists: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    """Detect already-installed virtual-camera helpers without installing them.

    Detection is deliberately conservative and injectable for tests. The runtime
    may use the default filesystem probe, but no driver install or process start
    happens here.
    """
    data = dict(payload or {})
    env_map = dict(os.environ if env is None else env)
    exists = path_exists or _safe_path_exists
    warnings: list[str] = []

    obs_candidates = _obs_candidate_paths(data, env_map)
    obs_path = _first_existing_path(obs_candidates, exists)
    explicit_obs = str(data.get("obs_executable") or data.get("obs_path") or "").strip()
    if explicit_obs and not obs_path:
        warnings.append("OBS executable was provided but was not found.")

    installed_backends: dict[str, Any] = {
        BACKEND_OBS: {
            "available": bool(obs_path),
            "executable": obs_path,
            "detection": "path_probe" if obs_path else "not_detected",
        },
        BACKEND_PYVIRTUALCAM: _pyvirtualcam_backend_info(data),
        BACKEND_SPOUT: _optional_backend_from_payload(BACKEND_SPOUT, data),
        BACKEND_NDI: _optional_backend_from_payload(BACKEND_NDI, data),
    }
    return {
        "schema": VIRTUAL_CAMERA_DISCOVERY_SCHEMA,
        "installed_backends": installed_backends,
        "backends": installed_backends,
        "warnings": warnings,
        "install_policy": "user_approved_only",
    }


def obs_virtual_camera_bridge_plan(
    payload: Mapping[str, Any] | None = None,
    *,
    installed_backends: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the OBS bridge contract for Program Output virtual camera use."""
    data = dict(payload or {})
    if installed_backends is None:
        discovery = discover_installed_virtual_camera_backends(data) if bool(data.get("discover", False)) else None
        installed = dict((discovery or {}).get("installed_backends") or data.get("installed_backends") or {})
    else:
        discovery = None
        installed = dict(installed_backends)

    obs_info = _backend_info(BACKEND_OBS, installed)
    obs_executable = str(data.get("obs_executable") or data.get("obs_path") or obs_info.get("executable") or "").strip()
    available = _backend_available(BACKEND_OBS, installed) or bool(obs_executable and _safe_path_exists(obs_executable))
    program_window_title = str(data.get("program_window_title") or DEFAULT_PROGRAM_OUTPUT_WINDOW_TITLE).strip()
    scene_name = str(data.get("scene_name") or DEFAULT_OBS_SCENE_NAME).strip()
    source_name = str(data.get("source_name") or DEFAULT_OBS_SOURCE_NAME).strip()

    websocket_enabled = bool(data.get("websocket_enabled", data.get("use_websocket", False)))
    websocket_host = str(data.get("websocket_host") or DEFAULT_OBS_WEBSOCKET_HOST).strip()
    websocket_port = _int(data.get("websocket_port"), DEFAULT_OBS_WEBSOCKET_PORT)
    websocket_password_present = bool(data.get("websocket_password_present") or data.get("websocket_password"))
    if "obsws_available" in data:
        obsws_available = bool(data.get("obsws_available"))
    else:
        obsws_available = find_spec("obsws_python") is not None
    can_control_websocket = bool(available and websocket_enabled and obsws_available)

    warnings: list[str] = []
    if not available:
        warnings.append("OBS is not detected; use Program Output window sharing or install OBS manually.")
    elif not websocket_enabled:
        warnings.append("OBS WebSocket is not enabled; configure OBS manually or enable WebSocket control.")
    elif not obsws_available:
        warnings.append("obsws-python is unavailable; OBS setup remains a manual/operator step.")

    result = {
        "schema": OBS_BRIDGE_SCHEMA,
        "backend": BACKEND_OBS,
        "available": bool(available),
        "install_policy": "user_approved_only",
        "obs": {
            "executable": obs_executable,
            "detected": bool(available),
            "launch_supported": bool(available),
            "auto_launch_policy": "user_confirmed_only",
        },
        "program_output": {
            "window_title": program_window_title,
            "source_id": "program_output",
            "must_exclude_performance_source": True,
        },
        "obs_scene": {
            "scene_name": scene_name,
            "source_name": source_name,
            "source_kind": "window_capture",
            "capture_method": "window_title",
            "window_title": program_window_title,
        },
        "websocket": {
            "enabled": websocket_enabled,
            "host": websocket_host,
            "port": websocket_port,
            "password_present": websocket_password_present,
            "dependency": {
                "module": "obsws_python",
                "available": obsws_available,
                "lazy_import": True,
            },
            "can_control": can_control_websocket,
        },
        "automation": {
            "can_launch_obs": bool(available),
            "can_configure_scene": can_control_websocket,
            "can_start_virtual_camera": can_control_websocket,
            "requires_user_approval": True,
            "direct_driver_install": False,
        },
        "output_contract": _output_contract(BACKEND_OBS),
        "operator_steps": _obs_operator_steps(
            obs_executable=obs_executable,
            scene_name=scene_name,
            source_name=source_name,
            program_window_title=program_window_title,
            websocket_enabled=websocket_enabled,
            can_control_websocket=can_control_websocket,
        ),
        "warnings": warnings,
    }
    if discovery is not None:
        result["discovery"] = discovery
    return result


def obs_virtual_camera_bridge_execution_gate(
    payload: Mapping[str, Any] | None = None,
    *,
    installed_backends: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return whether OBS bridge automation is allowed and ready."""
    data = dict(payload or {})
    plan = obs_virtual_camera_bridge_plan(data, installed_backends=installed_backends)
    confirmed = bool(data.get("confirm", False))
    ready_blockers: list[str] = []
    execute_blockers: list[str] = []
    if not bool(plan.get("available", False)):
        ready_blockers.append("OBS is not detected.")
    websocket = plan.get("websocket") if isinstance(plan.get("websocket"), Mapping) else {}
    if not bool(websocket.get("enabled", False)):
        ready_blockers.append("OBS WebSocket is not enabled.")
    dependency = websocket.get("dependency") if isinstance(websocket.get("dependency"), Mapping) else {}
    if not bool(dependency.get("available", False)):
        ready_blockers.append("obsws-python is not available.")
    if not confirmed:
        execute_blockers.append("User confirmation is required before controlling OBS.")
    execute_blockers.extend(ready_blockers)
    return {
        "schema": OBS_BRIDGE_GATE_SCHEMA,
        "ready": not ready_blockers,
        "can_execute": not execute_blockers,
        "confirmed": confirmed,
        "confirm_required": True,
        "ready_blockers": ready_blockers,
        "execute_blockers": execute_blockers,
        "plan": plan,
    }


def obs_virtual_camera_bridge_executor_dry_run(
    payload: Mapping[str, Any] | None = None,
    *,
    installed_backends: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the OBS WebSocket operations without connecting to OBS."""
    gate = obs_virtual_camera_bridge_execution_gate(payload, installed_backends=installed_backends)
    operations = _obs_bridge_operations(gate["plan"])
    return {
        "schema": OBS_BRIDGE_DRY_RUN_SCHEMA,
        "would_execute": bool(gate.get("ready", False)),
        "can_execute_now": bool(gate.get("can_execute", False)),
        "operations": operations,
        "gate": gate,
    }


def execute_obs_virtual_camera_bridge(
    payload: Mapping[str, Any] | None = None,
    *,
    installed_backends: Mapping[str, Any] | None = None,
    client_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Apply the OBS bridge setup through obsws-python or an injected client."""
    data = dict(payload or {})
    gate = obs_virtual_camera_bridge_execution_gate(data, installed_backends=installed_backends)
    if not bool(gate.get("can_execute", False)):
        blockers = gate.get("execute_blockers") or ["OBS bridge execution is not allowed."]
        raise ValueError("; ".join(str(item) for item in blockers))
    plan = gate["plan"]
    websocket = plan.get("websocket") if isinstance(plan.get("websocket"), Mapping) else {}
    if client_factory is None:
        from obsws_python import ReqClient  # type: ignore

        client_factory = ReqClient
    client = client_factory(
        host=str(websocket.get("host") or DEFAULT_OBS_WEBSOCKET_HOST),
        port=int(websocket.get("port") or DEFAULT_OBS_WEBSOCKET_PORT),
        password=str(data.get("websocket_password") or ""),
    )
    applied = _apply_obs_bridge_operations(client, plan)
    return {
        "schema": OBS_BRIDGE_EXECUTE_SCHEMA,
        "executed": True,
        "operations": applied,
        "gate": gate,
    }


def _backend_row(backend_id: str, label: str, installed: Mapping[str, Any]) -> dict[str, Any]:
    available = _backend_available(backend_id, installed)
    info = _backend_info(backend_id, installed)
    return {
        "id": backend_id,
        "label": label,
        "available": available,
        "requires_install": not available,
        "driver": backend_id in {BACKEND_PYVIRTUALCAM, BACKEND_OBS, BACKEND_NDI},
        "recommended": available and backend_id in {BACKEND_PYVIRTUALCAM, BACKEND_OBS},
        "can_create_device": available and backend_id in {BACKEND_PYVIRTUALCAM, BACKEND_OBS, BACKEND_NDI},
        "program_output_source": "Tiger Studio Program Output",
        "executable": str(info.get("executable") or ""),
        "detection": str(info.get("detection") or ("configured" if available else "not_detected")),
        "module": str(info.get("module") or ""),
        "device_name": str(info.get("device_name") or ""),
    }


def _output_contract(backend_id: str) -> dict[str, Any]:
    if backend_id == BACKEND_PYVIRTUALCAM:
        return {
            "mode": "virtual_camera_device",
            "program_output_input": "rgb_frame_stream",
            "device_owner": "pyvirtualcam",
            "app_output": "Installed virtual camera device",
            "direct_driver_install": False,
            "frame_writer": "BroadcastVirtualCameraDeviceSession",
        }
    if backend_id == BACKEND_OBS:
        return {
            "mode": "obs_virtual_camera",
            "program_output_input": "window_capture",
            "device_owner": "OBS",
            "app_output": "Tiger Studio Program Output window",
            "direct_driver_install": False,
        }
    if backend_id == BACKEND_SPOUT:
        return {
            "mode": "spout_sender",
            "program_output_input": "spout2_sender",
            "device_owner": "external_spout_receiver",
            "app_output": "Tiger Studio Program Output texture",
            "direct_driver_install": False,
        }
    if backend_id == BACKEND_NDI:
        return {
            "mode": "ndi_output",
            "program_output_input": "ndi_sender",
            "device_owner": "NDI runtime",
            "app_output": "Tiger Studio Program Output NDI stream",
            "direct_driver_install": False,
        }
    return {
        "mode": "window_share",
        "program_output_input": "share_window",
        "device_owner": "video_call_app",
        "app_output": "Tiger Studio Program Output window",
        "direct_driver_install": False,
    }


def _operator_steps(backend_id: str) -> list[str]:
    if backend_id == BACKEND_PYVIRTUALCAM:
        return [
            "Start Tiger Studio virtual-camera device output.",
            "Select the installed virtual camera device in Discord or the video-call app.",
            "If no device appears, install a virtual-camera backend manually and retry.",
        ]
    if backend_id == BACKEND_OBS:
        return [
            "Open OBS and add Tiger Studio Program Output as a Window Capture source.",
            "Start OBS Virtual Camera.",
            "Select OBS Virtual Camera in Discord or the video-call app.",
        ]
    if backend_id == BACKEND_SPOUT:
        return [
            "Enable Tiger Studio Program Output as a Spout2 sender.",
            "Select the Spout receiver or bridge app that exposes a camera device.",
            "Select that camera in Discord or the video-call app.",
        ]
    if backend_id == BACKEND_NDI:
        return [
            "Enable Tiger Studio Program Output as an NDI stream.",
            "Select the NDI virtual input device in Discord or the video-call app.",
        ]
    return [
        "Open the Discord or video-call screen-share picker.",
        "Share the Tiger Studio Program Output window.",
    ]


def _backend_info(backend_id: str, installed: Mapping[str, Any]) -> dict[str, Any]:
    value = installed.get(backend_id)
    if isinstance(value, Mapping):
        return dict(value)
    return {"available": bool(value)}


def _backend_available(backend_id: str, installed: Mapping[str, Any]) -> bool:
    value = installed.get(backend_id)
    if isinstance(value, Mapping):
        return bool(value.get("available", value.get("detected", False)))
    return bool(value)


def _optional_backend_from_payload(backend_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
    installed = data.get("installed_backends")
    if isinstance(installed, Mapping):
        info = _backend_info(backend_id, installed)
        if info:
            return info
    return {
        "available": bool(data.get(f"{backend_id}_available", False)),
        "detection": "explicit_payload" if data.get(f"{backend_id}_available", False) else "not_detected",
    }


def _pyvirtualcam_backend_info(data: Mapping[str, Any]) -> dict[str, Any]:
    installed = data.get("installed_backends")
    if isinstance(installed, Mapping):
        info = _backend_info(BACKEND_PYVIRTUALCAM, installed)
        if info:
            return info
    explicit = data.get("pyvirtualcam_available")
    available = bool(explicit) if explicit is not None else find_spec("pyvirtualcam") is not None
    return {
        "available": available,
        "module": "pyvirtualcam",
        "device_name": str(data.get("virtual_camera_device") or data.get("device_name") or ""),
        "detection": "module_probe" if available and explicit is None else ("explicit_payload" if available else "not_detected"),
    }


def _obs_candidate_paths(data: Mapping[str, Any], env: Mapping[str, str]) -> list[str]:
    candidates: list[str] = []
    explicit = str(data.get("obs_executable") or data.get("obs_path") or env.get("OBS_EXECUTABLE") or "").strip()
    if explicit:
        candidates.append(explicit)
    raw_candidates = data.get("candidate_paths")
    if isinstance(raw_candidates, Sequence) and not isinstance(raw_candidates, (str, bytes, bytearray)):
        candidates.extend(str(path).strip() for path in raw_candidates if str(path).strip())
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        root = str(env.get(key) or "").strip()
        if not root:
            continue
        candidates.append(str(Path(root) / "obs-studio" / "bin" / "64bit" / "obs64.exe"))
        candidates.append(str(Path(root) / "obs-studio" / "bin" / "32bit" / "obs32.exe"))
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        marker = candidate.lower()
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(candidate)
    return deduped


def _first_existing_path(candidates: Sequence[str], exists: Callable[[str], bool]) -> str:
    for candidate in candidates:
        try:
            if candidate and exists(candidate):
                return candidate
        except Exception:
            continue
    return ""


def _safe_path_exists(path: str) -> bool:
    try:
        return Path(path).is_file()
    except Exception:
        return False


def _int(value: Any, default: int) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _obs_operator_steps(
    *,
    obs_executable: str,
    scene_name: str,
    source_name: str,
    program_window_title: str,
    websocket_enabled: bool,
    can_control_websocket: bool,
) -> list[str]:
    if can_control_websocket:
        return [
            "Open or launch OBS with user confirmation.",
            f"Use OBS WebSocket to create/select scene '{scene_name}'.",
            f"Create/update Window Capture source '{source_name}' for '{program_window_title}'.",
            "Start OBS Virtual Camera and select it in Discord or the video-call app.",
        ]
    first = f"Open OBS at {obs_executable}." if obs_executable else "Open OBS."
    steps = [
        first,
        f"Create or select scene '{scene_name}'.",
        f"Add Window Capture source '{source_name}' and choose '{program_window_title}'.",
        "Start OBS Virtual Camera.",
        "Select OBS Virtual Camera in Discord or the video-call app.",
    ]
    if websocket_enabled:
        steps.insert(1, "Install/enable obsws-python support before automatic OBS setup.")
    return steps


def _obs_bridge_operations(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    obs_scene = plan.get("obs_scene") if isinstance(plan.get("obs_scene"), Mapping) else {}
    websocket = plan.get("websocket") if isinstance(plan.get("websocket"), Mapping) else {}
    scene_name = str(obs_scene.get("scene_name") or DEFAULT_OBS_SCENE_NAME)
    source_name = str(obs_scene.get("source_name") or DEFAULT_OBS_SOURCE_NAME)
    window_title = str(obs_scene.get("window_title") or DEFAULT_PROGRAM_OUTPUT_WINDOW_TITLE)
    return [
        {
            "id": "connect_obs_websocket",
            "label": "Connect to OBS WebSocket",
            "host": str(websocket.get("host") or DEFAULT_OBS_WEBSOCKET_HOST),
            "port": int(websocket.get("port") or DEFAULT_OBS_WEBSOCKET_PORT),
        },
        {
            "id": "ensure_scene",
            "label": "Create or select OBS scene",
            "scene_name": scene_name,
        },
        {
            "id": "ensure_window_capture_source",
            "label": "Create or update Program Output Window Capture source",
            "scene_name": scene_name,
            "source_name": source_name,
            "source_kind": "window_capture",
            "window_title": window_title,
            "input_settings": {"window": window_title},
        },
        {
            "id": "start_virtual_camera",
            "label": "Start OBS Virtual Camera",
        },
    ]


def _apply_obs_bridge_operations(client: Any, plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    operations = _obs_bridge_operations(plan)
    scene_name = str(operations[1]["scene_name"])
    source_name = str(operations[2]["source_name"])
    input_settings = dict(operations[2]["input_settings"])
    applied: list[dict[str, Any]] = [{**operations[0], "status": "connected"}]

    scenes = _obs_scene_names(_call_obs_optional(client, "get_scene_list"))
    if scene_name not in scenes:
        _call_obs(client, "create_scene", sceneName=scene_name)
        applied.append({**operations[1], "status": "created"})
    else:
        applied.append({**operations[1], "status": "already_exists"})

    inputs = _obs_input_names(_call_obs_optional(client, "get_input_list"))
    if source_name not in inputs:
        _call_obs(
            client,
            "create_input",
            sceneName=scene_name,
            inputName=source_name,
            inputKind="window_capture",
            inputSettings=input_settings,
            sceneItemEnabled=True,
        )
        applied.append({**operations[2], "status": "created"})
    else:
        if callable(getattr(client, "set_input_settings", None)):
            _call_obs(client, "set_input_settings", inputName=source_name, inputSettings=input_settings, overlay=True)
            applied.append({**operations[2], "status": "updated"})
        else:
            applied.append({**operations[2], "status": "already_exists"})

    _call_obs(client, "start_virtual_cam")
    applied.append({**operations[3], "status": "started"})
    return applied


def _call_obs_optional(client: Any, method_name: str) -> Any:
    method = getattr(client, method_name, None)
    if not callable(method):
        return None
    return method()


def _call_obs(client: Any, method_name: str, **kwargs: Any) -> Any:
    method = getattr(client, method_name, None)
    if not callable(method):
        raise AttributeError(f"OBS WebSocket client does not support {method_name}")
    return method(**kwargs)


def _obs_scene_names(response: Any) -> set[str]:
    rows = _response_rows(response, "scenes")
    names: set[str] = set()
    for row in rows:
        if isinstance(row, Mapping):
            name = row.get("sceneName") or row.get("scene_name") or row.get("name")
        else:
            name = getattr(row, "sceneName", None) or getattr(row, "scene_name", None) or getattr(row, "name", None)
        if name:
            names.add(str(name))
    return names


def _obs_input_names(response: Any) -> set[str]:
    rows = _response_rows(response, "inputs")
    names: set[str] = set()
    for row in rows:
        if isinstance(row, Mapping):
            name = row.get("inputName") or row.get("input_name") or row.get("name")
        else:
            name = getattr(row, "inputName", None) or getattr(row, "input_name", None) or getattr(row, "name", None)
        if name:
            names.add(str(name))
    return names


def _response_rows(response: Any, key: str) -> list[Any]:
    if response is None:
        return []
    if isinstance(response, Mapping):
        value = response.get(key) or response.get(key.rstrip("s"))
    else:
        value = getattr(response, key, None)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []
