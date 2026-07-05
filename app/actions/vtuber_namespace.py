"""VTuber and VSeeFace Python action namespace registrations."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.actions.result import ActionResult, error_result, ok_result
from app.actions.schema import ActionSpec, schema_object


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _as_camera_devices(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(value):
        if isinstance(item, Mapping):
            rows.append(dict(item))
        elif item not in (None, ""):
            rows.append({"id": f"device_{idx}", "name": str(item), "index": idx})
    return rows


def register_vseeface_bridge_actions(registry: Any) -> None:
    """Register VSeeFace bridge actions without bloating the core registry."""
    adapter = registry.adapter

    def _select_input_source(params: Mapping[str, Any], dry_run: bool) -> ActionResult:
        action_id = "vtuber.vseeface_select_input_source"
        source_id = str(params.get("source_id") or "").strip()
        input_payload = params.get("input") if isinstance(params.get("input"), Mapping) else None
        camera_devices = _as_camera_devices(params.get("camera_devices"))
        media_limit = _as_int(params.get("media_limit", 200), 200)
        if not source_id and input_payload is None:
            return error_result(action_id, "source_id or input is required", dry_run=dry_run)
        if dry_run:
            sources = adapter.vseeface_input_sources(camera_devices=camera_devices, media_limit=media_limit)
            selected = None
            if input_payload is None:
                for option in (sources.get("input_sources") or {}).get("options") or []:
                    if isinstance(option, Mapping) and str(option.get("id") or "") == source_id:
                        selected = dict(option)
                        input_payload = option.get("input") if isinstance(option.get("input"), Mapping) else None
                        break
            if input_payload is None:
                return error_result(action_id, f"VSeeFace tracking input source not found: {source_id}", dry_run=True)
            from app.vtuber.vseeface_bridge import VSeeFaceInputConfig

            normalized = VSeeFaceInputConfig.from_mapping(input_payload).to_dict()
            return ok_result(
                action_id,
                {
                    "would_apply": True,
                    "summary": "VSeeFace tracking input would be selected.",
                    "selected_id": source_id or str(normalized.get("source_id") or ""),
                    "selected": selected or {"id": normalized.get("source_id", ""), "input": normalized},
                    "input": normalized,
                },
                dry_run=True,
                changed=False,
            )
        return ok_result(
            action_id,
            adapter.select_vseeface_input_source(
                source_id=source_id,
                input=input_payload,
                camera_devices=camera_devices,
                media_limit=media_limit,
            ),
            changed=True,
        )

    def _select_exe(params: Mapping[str, Any], dry_run: bool) -> ActionResult:
        action_id = "vtuber.vseeface_select_exe"
        path = str(params.get("path") or params.get("vseeface_exe") or "").strip()
        if not path:
            return error_result(action_id, "vseeface_exe path is required", dry_run=dry_run)
        if dry_run:
            exists = Path(path).is_file()
            return ok_result(
                action_id,
                {
                    "would_apply": True,
                    "summary": "VSeeFace executable path would be selected.",
                    "vseeface_exe": path,
                    "exists": exists,
                },
                warnings=[] if exists else ["vseeface_exe_missing"],
                dry_run=True,
                changed=False,
            )
        return ok_result(action_id, adapter.select_vseeface_exe(path=path), changed=True)

    def _connect_installed_sidecar(params: Mapping[str, Any], dry_run: bool) -> ActionResult:
        action_id = "vtuber.vseeface_connect_installed_sidecar"
        if dry_run:
            from app.vtuber.vseeface_bridge import default_vseeface_exe

            path = str(params.get("path") or params.get("vseeface_exe") or "") or str(default_vseeface_exe())
            exists = Path(path).is_file()
            return ok_result(
                action_id,
                {
                    "would_apply": True,
                    "summary": "Installed VSeeFace sidecar would be connected.",
                    "vseeface_exe": path,
                    "exists": exists,
                },
                warnings=[] if exists else ["vseeface_exe_missing"],
                dry_run=True,
                changed=False,
            )
        return ok_result(
            action_id,
            adapter.connect_installed_vseeface_sidecar(
                path=str(params.get("path") or ""),
                vseeface_exe=str(params.get("vseeface_exe") or ""),
            ),
            changed=True,
        )

    def _select_vrm0_avatar(params: Mapping[str, Any], dry_run: bool) -> ActionResult:
        action_id = "vtuber.vseeface_select_vrm0_avatar"
        path = str(params.get("path") or params.get("avatar_vrm") or params.get("vrm") or "").strip()
        if not path:
            return error_result(action_id, "avatar_vrm path is required", dry_run=dry_run)
        if dry_run:
            from app.vtuber.vrm_profile import inspect_vrm_profile

            profile = inspect_vrm_profile(path)
            warnings = [str(item) for item in profile.get("warnings") or []]
            if not bool(profile.get("ok")):
                warnings.append("vrm_invalid")
            elif not bool(profile.get("vseeface_compatible")):
                warnings.append("vseeface_requires_vrm0")
            return ok_result(
                action_id,
                {
                    "would_apply": True,
                    "summary": "VSeeFace VRM0 avatar path would be selected as the shared VTuber Studio Avatar Target.",
                    "avatar_vrm": path,
                    "selected_avatar_target_id": "vrm:vseeface_bridge",
                    "vrm": profile,
                },
                warnings=warnings,
                dry_run=True,
                changed=False,
            )
        return ok_result(action_id, adapter.select_vseeface_vrm0_avatar(path=path), changed=True)

    def _select_capture_backend(params: Mapping[str, Any], dry_run: bool) -> ActionResult:
        action_id = "vtuber.vseeface_select_capture_backend"
        method = str(params.get("method") or "").strip()
        if not method:
            return error_result(action_id, "capture method is required", dry_run=dry_run)
        if dry_run:
            from app.vtuber.vseeface_bridge import VSeeFaceCaptureConfig

            normalized = VSeeFaceCaptureConfig.from_mapping(params).to_dict()
            return ok_result(
                action_id,
                {
                    "would_apply": True,
                    "summary": "VSeeFace capture backend would be selected.",
                    "capture": normalized,
                },
                dry_run=True,
                changed=False,
            )
        return ok_result(
            action_id,
            adapter.select_vseeface_capture_backend(
                method=method,
                window_title_hint=str(params.get("window_title_hint") or ""),
                virtual_camera_name=str(params.get("virtual_camera_name") or ""),
                spout_sender_name=str(params.get("spout_sender_name") or ""),
                framing_preset=str(params.get("framing_preset") or ""),
            ),
            changed=True,
        )

    def _select_framing(params: Mapping[str, Any], dry_run: bool) -> ActionResult:
        action_id = "vtuber.vseeface_select_framing"
        framing = str(params.get("framing_preset") or params.get("framing") or "").strip()
        if not framing:
            return error_result(action_id, "framing_preset is required", dry_run=dry_run)
        if dry_run:
            from app.vtuber.vseeface_bridge import VSeeFaceCaptureConfig

            normalized = VSeeFaceCaptureConfig.from_mapping({"framing_preset": framing}).to_dict()
            return ok_result(
                action_id,
                {
                    "would_apply": True,
                    "summary": "VSeeFace broadcast framing would be selected.",
                    "framing_preset": normalized["framing_preset"],
                    "camera": normalized["camera"],
                    "capture": normalized,
                },
                dry_run=True,
                changed=False,
            )
        return ok_result(action_id, adapter.select_vseeface_framing(framing_preset=framing), changed=True)

    registry.register(
        ActionSpec(
            "vtuber.vseeface_input_sources",
            "Return selectable VSeeFace tracking inputs from camera devices, Media Pool, and timeline clips.",
            "vtuber",
            params_schema=schema_object(
                {
                    "camera_devices": {"type": "array"},
                    "input_diagnostics": {"type": "object"},
                    "media_limit": {"type": "integer", "minimum": 0},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_input_sources",
            adapter.vseeface_input_sources(
                camera_devices=_as_camera_devices(params.get("camera_devices")),
                input_diagnostics=params.get("input_diagnostics")
                if isinstance(params.get("input_diagnostics"), Mapping)
                else None,
                media_limit=_as_int(params.get("media_limit", 200), 200),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_bridge_status",
            "Return VSeeFace bridge status, view model, actions, and tracking input choices.",
            "vtuber",
            params_schema=schema_object(
                {
                    "camera_devices": {"type": "array"},
                    "capture_diagnostics": {"type": "object"},
                    "input_diagnostics": {"type": "object"},
                    "media_limit": {"type": "integer", "minimum": 0},
                    "width": {"type": "integer", "minimum": 1},
                    "height": {"type": "integer", "minimum": 1},
                    "fps": {"type": "number", "minimum": 1},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_bridge_status",
            adapter.vseeface_bridge_status(
                camera_devices=_as_camera_devices(params.get("camera_devices")),
                capture_diagnostics=params.get("capture_diagnostics")
                if isinstance(params.get("capture_diagnostics"), Mapping)
                else None,
                input_diagnostics=params.get("input_diagnostics")
                if isinstance(params.get("input_diagnostics"), Mapping)
                else None,
                media_limit=_as_int(params.get("media_limit", 200), 200),
                width=_as_int(params.get("width", 1920), 1920),
                height=_as_int(params.get("height", 1080), 1080),
                fps=_as_float(params.get("fps", 30.0), 30.0),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_action_preview",
            "Preview a VSeeFace bridge action plan without executing external tools.",
            "vtuber",
            params_schema=schema_object(
                {
                    "action_id": {"type": "string"},
                    "allow_admin": {"type": "boolean"},
                    "camera_devices": {"type": "array"},
                    "capture_diagnostics": {"type": "object"},
                    "media_limit": {"type": "integer", "minimum": 0},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_action_preview",
            adapter.preview_vseeface_bridge_action(
                action_id=str(params.get("action_id") or ""),
                allow_admin=bool(params.get("allow_admin", False)),
                camera_devices=_as_camera_devices(params.get("camera_devices")),
                capture_diagnostics=params.get("capture_diagnostics")
                if isinstance(params.get("capture_diagnostics"), Mapping)
                else None,
                media_limit=_as_int(params.get("media_limit", 200), 200),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_start_probe_plan",
            "Return a non-auto-run plan for launching VSeeFace and probing capture readiness.",
            "vtuber",
            params_schema=schema_object(
                {
                    "camera_devices": {"type": "array"},
                    "capture_diagnostics": {"type": "object"},
                    "input_diagnostics": {"type": "object"},
                    "media_limit": {"type": "integer", "minimum": 0},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_start_probe_plan",
            adapter.vseeface_start_probe_plan(
                camera_devices=_as_camera_devices(params.get("camera_devices")),
                capture_diagnostics=params.get("capture_diagnostics")
                if isinstance(params.get("capture_diagnostics"), Mapping)
                else None,
                input_diagnostics=params.get("input_diagnostics")
                if isinstance(params.get("input_diagnostics"), Mapping)
                else None,
                media_limit=_as_int(params.get("media_limit", 200), 200),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_start_probe_execution_gate",
            "Validate whether the VSeeFace start/probe plan can execute, without executing it.",
            "vtuber",
            params_schema=schema_object(
                {
                    "camera_devices": {"type": "array"},
                    "capture_diagnostics": {"type": "object"},
                    "input_diagnostics": {"type": "object"},
                    "media_limit": {"type": "integer", "minimum": 0},
                    "confirm": {"type": "boolean"},
                    "allow_admin": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_start_probe_execution_gate",
            adapter.vseeface_start_probe_execution_gate(
                camera_devices=_as_camera_devices(params.get("camera_devices")),
                capture_diagnostics=params.get("capture_diagnostics")
                if isinstance(params.get("capture_diagnostics"), Mapping)
                else None,
                input_diagnostics=params.get("input_diagnostics")
                if isinstance(params.get("input_diagnostics"), Mapping)
                else None,
                media_limit=_as_int(params.get("media_limit", 200), 200),
                confirm=bool(params.get("confirm", False)),
                allow_admin=bool(params.get("allow_admin", False)),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_start_probe_executor_dry_run",
            "Return the VSeeFace start/probe executor dry-run report without running tools.",
            "vtuber",
            params_schema=schema_object(
                {
                    "camera_devices": {"type": "array"},
                    "capture_diagnostics": {"type": "object"},
                    "input_diagnostics": {"type": "object"},
                    "media_limit": {"type": "integer", "minimum": 0},
                    "confirm": {"type": "boolean"},
                    "allow_admin": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_start_probe_executor_dry_run",
            adapter.vseeface_start_probe_executor_dry_run(
                camera_devices=_as_camera_devices(params.get("camera_devices")),
                capture_diagnostics=params.get("capture_diagnostics")
                if isinstance(params.get("capture_diagnostics"), Mapping)
                else None,
                input_diagnostics=params.get("input_diagnostics")
                if isinstance(params.get("input_diagnostics"), Mapping)
                else None,
                media_limit=_as_int(params.get("media_limit", 200), 200),
                confirm=bool(params.get("confirm", False)),
                allow_admin=bool(params.get("allow_admin", False)),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_start_probe_execute",
            "Launch VSeeFace and run capture probes after explicit confirmation.",
            "vtuber",
            params_schema=schema_object(
                {
                    "camera_devices": {"type": "array"},
                    "capture_diagnostics": {"type": "object"},
                    "input_diagnostics": {"type": "object"},
                    "media_limit": {"type": "integer", "minimum": 0},
                    "confirm": {"type": "boolean"},
                    "allow_admin": {"type": "boolean"},
                    "timeout_s": {"type": "number", "minimum": 1},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_start_probe_execute",
            adapter.vseeface_start_probe_execute(
                camera_devices=_as_camera_devices(params.get("camera_devices")),
                capture_diagnostics=params.get("capture_diagnostics")
                if isinstance(params.get("capture_diagnostics"), Mapping)
                else None,
                input_diagnostics=params.get("input_diagnostics")
                if isinstance(params.get("input_diagnostics"), Mapping)
                else None,
                media_limit=_as_int(params.get("media_limit", 200), 200),
                confirm=bool(params.get("confirm", False)),
                allow_admin=bool(params.get("allow_admin", False)),
                timeout_s=_as_float(params.get("timeout_s", 180.0), 180.0),
            ),
            changed=bool(params.get("confirm", False)),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_sidecar_settings_preview",
            "Return the VSeeFace settings.ini payload that would be written, without writing files.",
            "vtuber",
            params_schema=schema_object({"settings_path": {"type": "string"}}, additional_properties=True),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_sidecar_settings_preview",
            adapter.vseeface_sidecar_settings_preview(settings_path=str(params.get("settings_path") or "")),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_sidecar_apply_plan",
            "Return a non-auto-run plan for writing VSeeFace sidecar settings.",
            "vtuber",
            params_schema=schema_object(
                {"settings_path": {"type": "string"}, "out_path": {"type": "string"}},
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_sidecar_apply_plan",
            adapter.vseeface_sidecar_apply_plan(
                settings_path=str(params.get("settings_path") or ""),
                out_path=str(params.get("out_path") or ""),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_sidecar_execution_gate",
            "Validate whether the sidecar settings plan can be executed, without executing it.",
            "vtuber",
            params_schema=schema_object(
                {
                    "settings_path": {"type": "string"},
                    "out_path": {"type": "string"},
                    "confirm": {"type": "boolean"},
                    "allow_admin": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_sidecar_execution_gate",
            adapter.vseeface_sidecar_execution_gate(
                settings_path=str(params.get("settings_path") or ""),
                out_path=str(params.get("out_path") or ""),
                confirm=bool(params.get("confirm", False)),
                allow_admin=bool(params.get("allow_admin", False)),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_sidecar_executor_dry_run",
            "Return the VSeeFace sidecar executor dry-run report without running tools.",
            "vtuber",
            params_schema=schema_object(
                {
                    "settings_path": {"type": "string"},
                    "out_path": {"type": "string"},
                    "confirm": {"type": "boolean"},
                    "allow_admin": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_sidecar_executor_dry_run",
            adapter.vseeface_sidecar_executor_dry_run(
                settings_path=str(params.get("settings_path") or ""),
                out_path=str(params.get("out_path") or ""),
                confirm=bool(params.get("confirm", False)),
                allow_admin=bool(params.get("allow_admin", False)),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_sidecar_workflow",
            "Return the full read-only VSeeFace sidecar settings workflow for UI.",
            "vtuber",
            params_schema=schema_object(
                {
                    "settings_path": {"type": "string"},
                    "out_path": {"type": "string"},
                    "confirm": {"type": "boolean"},
                    "allow_admin": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_sidecar_workflow",
            adapter.vseeface_sidecar_workflow(
                settings_path=str(params.get("settings_path") or ""),
                out_path=str(params.get("out_path") or ""),
                confirm=bool(params.get("confirm", False)),
                allow_admin=bool(params.get("allow_admin", False)),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_install_plan",
            "Return a non-auto-run plan for installing the external VSeeFace sidecar.",
            "vtuber",
            params_schema=schema_object(
                {
                    "source_zip": {"type": "string"},
                    "download_url": {"type": "string"},
                    "install_dir": {"type": "string"},
                    "out_path": {"type": "string"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_install_plan",
            adapter.vseeface_install_plan(
                source_zip=str(params.get("source_zip") or ""),
                download_url=str(params.get("download_url") or ""),
                install_dir=str(params.get("install_dir") or ""),
                out_path=str(params.get("out_path") or ""),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_install_execution_gate",
            "Validate whether the VSeeFace sidecar install plan can execute, without executing it.",
            "vtuber",
            params_schema=schema_object(
                {
                    "source_zip": {"type": "string"},
                    "download_url": {"type": "string"},
                    "install_dir": {"type": "string"},
                    "out_path": {"type": "string"},
                    "confirm": {"type": "boolean"},
                    "allow_admin": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_install_execution_gate",
            adapter.vseeface_install_execution_gate(
                source_zip=str(params.get("source_zip") or ""),
                download_url=str(params.get("download_url") or ""),
                install_dir=str(params.get("install_dir") or ""),
                out_path=str(params.get("out_path") or ""),
                confirm=bool(params.get("confirm", False)),
                allow_admin=bool(params.get("allow_admin", False)),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_install_executor_dry_run",
            "Return the VSeeFace sidecar install executor dry-run report without running tools.",
            "vtuber",
            params_schema=schema_object(
                {
                    "source_zip": {"type": "string"},
                    "download_url": {"type": "string"},
                    "install_dir": {"type": "string"},
                    "out_path": {"type": "string"},
                    "confirm": {"type": "boolean"},
                    "allow_admin": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_install_executor_dry_run",
            adapter.vseeface_install_executor_dry_run(
                source_zip=str(params.get("source_zip") or ""),
                download_url=str(params.get("download_url") or ""),
                install_dir=str(params.get("install_dir") or ""),
                out_path=str(params.get("out_path") or ""),
                confirm=bool(params.get("confirm", False)),
                allow_admin=bool(params.get("allow_admin", False)),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_install_execute",
            "Execute the VSeeFace sidecar install plan after explicit confirmation.",
            "vtuber",
            params_schema=schema_object(
                {
                    "source_zip": {"type": "string"},
                    "download_url": {"type": "string"},
                    "install_dir": {"type": "string"},
                    "out_path": {"type": "string"},
                    "confirm": {"type": "boolean"},
                    "allow_admin": {"type": "boolean"},
                    "timeout_s": {"type": "number", "minimum": 1},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "vtuber.vseeface_install_execute",
            adapter.vseeface_install_execute(
                source_zip=str(params.get("source_zip") or ""),
                download_url=str(params.get("download_url") or ""),
                install_dir=str(params.get("install_dir") or ""),
                out_path=str(params.get("out_path") or ""),
                confirm=bool(params.get("confirm", False)),
                allow_admin=bool(params.get("allow_admin", False)),
                timeout_s=_as_float(params.get("timeout_s", 120.0), 120.0),
            ),
            changed=bool(params.get("confirm", False)),
        ),
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_connect_installed_sidecar",
            "Persist the installed VSeeFace sidecar executable path for the bridge.",
            "vtuber",
            params_schema=schema_object(
                {"path": {"type": "string"}, "vseeface_exe": {"type": "string"}},
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Connect installed VSeeFace sidecar",
        ),
        _connect_installed_sidecar,
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_select_exe",
            "Persist the external VSeeFace executable path for the bridge.",
            "vtuber",
            params_schema=schema_object(
                {"path": {"type": "string"}, "vseeface_exe": {"type": "string"}},
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Select VSeeFace executable",
        ),
        _select_exe,
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_select_vrm0_avatar",
            "Persist a VSeeFace-compatible VRM0 avatar path and select it as the shared VTuber Studio Avatar Target.",
            "vtuber",
            params_schema=schema_object(
                {"path": {"type": "string"}, "avatar_vrm": {"type": "string"}, "vrm": {"type": "string"}},
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Select VSeeFace VRM0 avatar",
        ),
        _select_vrm0_avatar,
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_select_capture_backend",
            "Persist the selected VSeeFace output capture backend.",
            "vtuber",
            params_schema=schema_object(
                {
                    "method": {"type": "string", "enum": ["window_capture", "virtual_camera", "spout2", "none"]},
                    "window_title_hint": {"type": "string"},
                    "virtual_camera_name": {"type": "string"},
                    "spout_sender_name": {"type": "string"},
                    "framing_preset": {"type": "string"},
                },
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Select VSeeFace capture backend",
        ),
        _select_capture_backend,
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_select_framing",
            "Persist the intended VSeeFace broadcast framing preset.",
            "vtuber",
            params_schema=schema_object(
                {
                    "framing_preset": {"type": "string", "enum": ["bust_up", "half_body", "full_body"]},
                    "framing": {"type": "string"},
                },
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Select VSeeFace framing",
        ),
        _select_framing,
    )
    registry.register(
        ActionSpec(
            "vtuber.vseeface_select_input_source",
            "Persist the selected VSeeFace/OpenSeeFace tracking input source.",
            "vtuber",
            params_schema=schema_object(
                {
                    "source_id": {"type": "string"},
                    "input": {"type": "object"},
                    "camera_devices": {"type": "array"},
                    "media_limit": {"type": "integer", "minimum": 0},
                },
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Select VSeeFace tracking input",
        ),
        _select_input_source,
    )


def register_vtuber_studio_actions(registry: Any) -> None:
    """Register shared VTuber Studio, VRM target, and Performance Source actions."""
    registry.register_adapter_action(
        "vtuber.studio.open",
        "Open the shared VTuber Studio window.",
        "vtuber",
        "open_vtuber_studio",
        params_schema=schema_object({"avatar_target_id": {"type": "string"}}),
        mutating=False,
        changed=False,
        async_kind="vtuber",
        dry_summary="shared VTuber Studio window would open",
    )
    registry.register_adapter_action(
        "vtuber.avatar_target.summary",
        "Return selectable VTuber Studio avatar targets.",
        "vtuber",
        "avatar_target_summary",
        params_schema=schema_object(
            {
                "target_id": {"type": "string"},
                "media_limit": {"type": "integer", "minimum": 0},
            }
        ),
        mutating=False,
        changed=False,
        async_kind="vtuber",
        dry_summary="avatar targets would be summarized",
    )
    registry.register_adapter_action(
        "vtuber.avatar_target.select",
        "Select the active Avatar Target inside the shared VTuber Studio.",
        "vtuber",
        "select_vtuber_avatar_target",
        params_schema=schema_object({"target_id": {"type": "string"}}, required=("target_id",)),
        required=("target_id",),
        undo_label="Select VTuber avatar target",
        async_kind="vtuber",
        dry_summary="avatar target selection would be saved",
    )
    registry.register_adapter_action(
        "vtuber.vrm.bridge_status",
        "Return VRM / VSeeFace Bridge target status for VTuber Studio.",
        "vtuber",
        "vrm_bridge_status",
        params_schema=schema_object(
            {
                "camera_devices": {"type": "array"},
                "capture_diagnostics": {"type": "object"},
                "input_diagnostics": {"type": "object"},
                "media_limit": {"type": "integer", "minimum": 0},
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
                "fps": {"type": "number", "minimum": 1},
            },
            additional_properties=True,
        ),
        mutating=False,
        changed=False,
        async_kind="vtuber",
        dry_summary="VRM / VSeeFace bridge status would be returned",
    )
    registry.register_adapter_action(
        "vtuber.vrm.pose_stream_preview",
        "Preview the VRM pose stream route without baking Live2D keys.",
        "vtuber",
        "vrm_pose_stream_preview",
        params_schema=schema_object(
            {
                "motion_csv": {"type": "string"},
                "camera_devices": {"type": "array"},
                "capture_diagnostics": {"type": "object"},
                "input_diagnostics": {"type": "object"},
                "media_limit": {"type": "integer", "minimum": 0},
            },
            additional_properties=True,
        ),
        mutating=False,
        changed=False,
        async_kind="vtuber",
        dry_summary="VRM pose stream route would be previewed",
    )
    registry.register_adapter_action(
        "vtuber.performance_source.summary",
        "Return Performance Source tracks, marked media, and Program Output rules.",
        "vtuber",
        "performance_source_summary",
        params_schema=schema_object({"time_ms": {"type": "integer", "minimum": 0}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="vtuber",
        dry_summary="performance-source state would be summarized",
    )
    registry.register_adapter_action(
        "vtuber.program_output_contract",
        "Return the Program Output background contract at a timeline time.",
        "vtuber",
        "program_output_contract",
        params_schema=schema_object({"time_ms": {"type": "integer", "minimum": 0}}),
        mutating=False,
        changed=False,
        async_kind="vtuber",
        dry_summary="program output contract would be checked",
    )
    registry.register_adapter_action(
        "vtuber.performance_source.mark_media",
        "Mark a Media Pool item as an input-only avatar Performance Source.",
        "vtuber",
        "mark_performance_source_media",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "enabled": {"type": "boolean"},
                "add_to_pool": {"type": "boolean"},
            },
            required=("path",),
        ),
        required=("path",),
        undo_label="Mark Performance Source media",
        async_kind="vtuber",
        dry_summary="media would be marked as a Performance Source",
    )
    registry.register_adapter_action(
        "vtuber.performance_source.add_clip",
        "Place media on a dedicated Performance Source track for avatar tracking.",
        "vtuber",
        "add_performance_source_clip",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "start_ms": {"type": "integer", "minimum": 0},
                "duration_ms": {"type": "integer", "minimum": 1},
            },
            required=("path",),
        ),
        required=("path",),
        undo_label="Add Performance Source clip",
        async_kind="vtuber",
        dry_summary="media would be placed on the Performance Source track",
    )
