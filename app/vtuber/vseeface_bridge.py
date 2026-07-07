"""External VSeeFace bridge contract.

VSeeFace is never embedded into TigerCapture. The bridge owns only sidecar
process planning, VRM compatibility preflight, capture-source metadata, and the
BroadcastScene source contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Mapping

from app.broadcast_scene import (
    FIT_CONTAIN,
    SETTING_SUPPRESS_BLACK_FRAME,
    SOURCE_COLOR,
    SOURCE_INTERNAL_VRM,
    SOURCE_VSEEFACE,
    broadcast_scene_diagnostics,
)
from app.vtuber.openseeface_video_source import parse_crop
from app.vtuber.vrm_profile import inspect_vrm_profile
from app.vtuber.vmc_protocol import VMC_DEFAULT_HOST, VMC_VSEEFACE_RECEIVER_PORT, VMC_VSEEFACE_SENDER_PORT


BRIDGE_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.v1"
INTEGRATION_MODE = "external_sidecar"
CAPTURE_WINDOW = "window_capture"
CAPTURE_SPOUT2 = "spout2"
CAPTURE_VIRTUAL_CAMERA = "virtual_camera"
CAPTURE_NONE = "none"
SUPPORTED_CAPTURE_METHODS = frozenset({CAPTURE_WINDOW, CAPTURE_SPOUT2, CAPTURE_VIRTUAL_CAMERA, CAPTURE_NONE})
FRAMING_BUST_UP = "bust_up"
FRAMING_HALF_BODY = "half_body"
FRAMING_FULL_BODY = "full_body"
SUPPORTED_FRAMING_PRESETS = frozenset({FRAMING_BUST_UP, FRAMING_HALF_BODY, FRAMING_FULL_BODY})
INPUT_WEBCAM = "webcam"
INPUT_OPENSEEFACE_VIDEO = "openseeface_video"
SUPPORTED_INPUT_MODES = frozenset({INPUT_WEBCAM, INPUT_OPENSEEFACE_VIDEO})
INPUT_SOURCE_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.input_sources.v1"
INPUT_KIND_CAMERA_DEVICE = "camera_device"
INPUT_KIND_VIDEO_FILE = "video_file"
INPUT_KIND_MEDIA_POOL_VIDEO = "media_pool_video"
INPUT_KIND_TIMELINE_VIDEO_CLIP = "timeline_video_clip"
INPUT_STATUS_READY = "ready"
INPUT_STATUS_NOT_PROBED = "not_probed"
INPUT_STATUS_UNAVAILABLE = "unavailable"
INPUT_STATUS_BLACK_FRAME = "black_frame"
INPUT_STATUS_MISSING = "missing"
SUPPORTED_INPUT_SOURCE_KINDS = frozenset({
    INPUT_KIND_CAMERA_DEVICE,
    INPUT_KIND_VIDEO_FILE,
    INPUT_KIND_MEDIA_POOL_VIDEO,
    INPUT_KIND_TIMELINE_VIDEO_CLIP,
})
VIDEO_INPUT_EXTS = frozenset({
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".wmv",
    ".gif",
})
CAPTURE_STATUS_NOT_PROBED = "not_probed"
CAPTURE_STATUS_READY = "ready"
CAPTURE_STATUS_UNAVAILABLE = "capture_unavailable"
CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK = "virtual_camera_black_frame"
CAPTURE_STATUS_BLOCKED_REGISTRATION = "blocked_registration_required"
CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED = "virtual_camera_capture_failed"
CAPTURE_FALLBACK_SUPPRESS_BLACK_FRAME = "suppress_black_frame"
CAPTURE_FALLBACK_INTERNAL_VRM = "internal_vrm_renderer"
INTERNAL_VRM_FALLBACK_SOURCE_ID = "internal_vrm_fallback"
BRIDGE_STATE_READY = "ready"
BRIDGE_STATE_NEEDS_PROBE = "needs_probe"
BRIDGE_STATE_DEGRADED = "degraded"
BRIDGE_STATE_BLOCKED = "blocked"
BRIDGE_VIEW_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.view_model.v1"
BRIDGE_SETUP_FLOW_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.setup_flow.v1"
BRIDGE_INSTALL_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.install.v1"
BRIDGE_SIDECAR_SETTINGS_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.sidecar_settings_preview.v1"
BRIDGE_SIDECAR_APPLY_PLAN_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.sidecar_apply_plan.v1"
BRIDGE_SIDECAR_WORKFLOW_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.sidecar_workflow.v1"
BRIDGE_ACTION_PLAN_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.action_plan.v1"
ACTION_APPLY_SIDECAR_SETTINGS = "apply_sidecar_settings"
ACTION_USE_CAPTURE_SOURCE = "use_capture_source"
ACTION_RUN_CAPTURE_PROBE = "run_capture_probe"
ACTION_START_AND_PROBE_VSEEFACE = "start_vseeface_and_probe"
ACTION_SELECT_VSEEFACE_EXE = "select_vseeface_exe"
ACTION_SELECT_VRM0_AVATAR = "select_vrm0_avatar"
ACTION_FIX_RENDERING_OR_START_SCENE = "fix_vseeface_rendering_or_start_scene"
ACTION_KEEP_FALLBACK_SOURCE = "keep_fallback_source"
ACTION_USE_INTERNAL_VRM_FALLBACK = "use_internal_vrm_fallback"
ACTION_REGISTER_VSEEFACE_CAMERA = "register_vseeface_camera"
ACTION_CONFIRM_VIRTUAL_CAMERA = "confirm_vseeface_camera_enabled"
ACTION_SELECT_TRACKING_INPUT = "select_tracking_input_source"
ACTION_RUN_TRACKING_INPUT_PROBE = "run_tracking_input_probe"
ACTION_RECONNECT_TRACKING_INPUT = "reconnect_tracking_input_source"
ACTION_SELECT_CAPTURE_BACKEND = "select_capture_backend"
ACTION_SELECT_BROADCAST_FRAMING = "select_broadcast_framing"
ACTION_INSTALL_VSEEFACE_SIDECAR = "install_vseeface_sidecar"
ACTION_CONNECT_INSTALLED_VSEEFACE = "connect_installed_vseeface_sidecar"
ACTION_OPEN_VSEEFACE_DOWNLOAD_PAGE = "open_vseeface_download_page"
VSEEFACE_DOWNLOAD_PAGE_URL = "https://www.vseeface.icu/"


def standard_vtuber_camera_settings(preset: str = FRAMING_BUST_UP) -> dict[str, Any]:
    """Return product defaults for common VTuber broadcast framing.

    These values are bridge metadata and VSeeFace setup guidance. They do not
    imply that TigerCapture owns VSeeFace's internal camera.
    """
    key = str(preset or FRAMING_BUST_UP)
    if key not in SUPPORTED_FRAMING_PRESETS:
        key = FRAMING_BUST_UP
    if key == FRAMING_FULL_BODY:
        return {
            "preset": FRAMING_FULL_BODY,
            "target": "full_body_check",
            "composition": "head_to_toe",
            "fov_deg": 24.0,
            "camera_distance_m": 3.2,
            "camera_height_m": 1.15,
            "pitch_deg": 0.0,
            "eye_line_y": 0.24,
            "headroom": 0.08,
            "lower_frame": "feet",
            "broadcast_zoom": 1.0,
            "broadcast_offset_y": 0.0,
        }
    if key == FRAMING_HALF_BODY:
        return {
            "preset": FRAMING_HALF_BODY,
            "target": "waist_up",
            "composition": "head_to_waist",
            "fov_deg": 22.0,
            "camera_distance_m": 2.05,
            "camera_height_m": 1.25,
            "pitch_deg": 0.0,
            "eye_line_y": 0.32,
            "headroom": 0.07,
            "lower_frame": "waist",
            "broadcast_zoom": 1.35,
            "broadcast_offset_y": -0.08,
        }
    return {
        "preset": FRAMING_BUST_UP,
        "target": "head_and_shoulders",
        "composition": "head_to_mid_chest",
        "fov_deg": 20.0,
        "camera_distance_m": 1.45,
        "camera_height_m": 1.45,
        "pitch_deg": -6.0,
        "eye_line_y": 0.36,
        "headroom": 0.06,
        "lower_frame": "mid_chest",
        "broadcast_zoom": 1.65,
        "broadcast_offset_y": -0.18,
    }


@dataclass
class VSeeFaceCaptureConfig:
    method: str = CAPTURE_WINDOW
    source_id: str = "vseeface"
    window_title_hint: str = "VSeeFace"
    virtual_camera_name: str = "VSeeFaceCamera"
    spout_sender_name: str = "VSeeFace"
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    framing_preset: str = FRAMING_BUST_UP
    chroma_key: dict[str, Any] = field(default_factory=lambda: {"enabled": False})

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "VSeeFaceCaptureConfig":
        data = payload or {}
        method = str(data.get("method") or CAPTURE_WINDOW)
        if method not in SUPPORTED_CAPTURE_METHODS:
            method = CAPTURE_WINDOW
        return cls(
            method=method,
            source_id=str(data.get("source_id") or "vseeface"),
            window_title_hint=str(data.get("window_title_hint") or "VSeeFace"),
            virtual_camera_name=str(data.get("virtual_camera_name") or "VSeeFaceCamera"),
            spout_sender_name=str(data.get("spout_sender_name") or "VSeeFace"),
            width=max(1, int(data.get("width", 1920) or 1920)),
            height=max(1, int(data.get("height", 1080) or 1080)),
            fps=max(1.0, float(data.get("fps", 30.0) or 30.0)),
            framing_preset=_normalize_framing_preset(data.get("framing_preset") or data.get("framing")),
            chroma_key=dict(data.get("chroma_key") if isinstance(data.get("chroma_key"), Mapping) else {"enabled": False}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "source_id": self.source_id,
            "window_title_hint": self.window_title_hint,
            "virtual_camera_name": self.virtual_camera_name,
            "spout_sender_name": self.spout_sender_name,
            "width": int(self.width),
            "height": int(self.height),
            "fps": float(self.fps),
            "framing_preset": self.framing_preset,
            "camera": standard_vtuber_camera_settings(self.framing_preset),
            "chroma_key": dict(self.chroma_key),
        }


@dataclass
class VSeeFaceTrackingConfig:
    enabled: bool = False
    protocol: str = "vmc_osc"
    target_host: str = VMC_DEFAULT_HOST
    receive_port: int = VMC_VSEEFACE_RECEIVER_PORT
    send_port: int = VMC_VSEEFACE_SENDER_PORT

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "VSeeFaceTrackingConfig":
        data = payload or {}
        return cls(
            enabled=bool(data.get("enabled", False)),
            protocol=str(data.get("protocol") or "vmc_osc"),
            target_host=str(data.get("target_host") or VMC_DEFAULT_HOST),
            receive_port=max(1, min(65535, int(data.get("receive_port", VMC_VSEEFACE_RECEIVER_PORT) or VMC_VSEEFACE_RECEIVER_PORT))),
            send_port=max(1, min(65535, int(data.get("send_port", VMC_VSEEFACE_SENDER_PORT) or VMC_VSEEFACE_SENDER_PORT))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "protocol": self.protocol,
            "target_host": self.target_host,
            "receive_port": int(self.receive_port),
            "send_port": int(self.send_port),
        }


@dataclass
class VSeeFaceInputConfig:
    mode: str = INPUT_WEBCAM
    source_kind: str = INPUT_KIND_CAMERA_DEVICE
    source_id: str = "camera:default"
    camera_device_id: str = ""
    camera_device_name: str = "Default camera"
    camera_index: int | None = None
    video_path: str = ""
    media_pool_id: str = ""
    track_id: int | None = None
    clip_id: int | None = None
    source_in_ms: int = 0
    source_out_ms: int = 0
    timeline_in_ms: int = 0
    timeline_out_ms: int = 0
    openseeface_host: str = VMC_DEFAULT_HOST
    openseeface_port: int = VMC_VSEEFACE_SENDER_PORT
    width: int = 640
    height: int = 360
    fps: float = 24.0
    model: int = 3
    detection_threshold: float = 0.35
    try_hard: bool = False
    crop: tuple[float, float, float, float] | None = None
    realtime: bool = True

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "VSeeFaceInputConfig":
        data = payload or {}
        mode = str(data.get("mode") or data.get("source") or INPUT_WEBCAM).strip().casefold()
        mode = mode.replace("-", "_")
        if mode in {"camera", "web_camera", "webcam_camera"}:
            mode = INPUT_WEBCAM
        if mode not in SUPPORTED_INPUT_MODES:
            mode = INPUT_WEBCAM
        source_kind = _normalize_input_source_kind(data.get("source_kind") or data.get("kind"), mode=mode, data=data)
        if source_kind == INPUT_KIND_CAMERA_DEVICE:
            mode = INPUT_WEBCAM
        elif source_kind in {INPUT_KIND_VIDEO_FILE, INPUT_KIND_MEDIA_POOL_VIDEO, INPUT_KIND_TIMELINE_VIDEO_CLIP}:
            mode = INPUT_OPENSEEFACE_VIDEO
        return cls(
            mode=mode,
            source_kind=source_kind,
            source_id=str(data.get("source_id") or data.get("id") or _default_input_source_id(source_kind, data)),
            camera_device_id=str(data.get("camera_device_id") or data.get("device_id") or ""),
            camera_device_name=str(data.get("camera_device_name") or data.get("device_name") or data.get("camera_name") or "Default camera"),
            camera_index=_optional_int(data.get("camera_index", data.get("device_index"))),
            video_path=str(data.get("video_path") or data.get("video") or ""),
            media_pool_id=str(data.get("media_pool_id") or ""),
            track_id=_optional_int(data.get("track_id")),
            clip_id=_optional_int(data.get("clip_id")),
            source_in_ms=_nonnegative_int(data.get("source_in_ms")),
            source_out_ms=_nonnegative_int(data.get("source_out_ms")),
            timeline_in_ms=_nonnegative_int(data.get("timeline_in_ms")),
            timeline_out_ms=_nonnegative_int(data.get("timeline_out_ms")),
            openseeface_host=str(data.get("openseeface_host") or data.get("host") or VMC_DEFAULT_HOST),
            openseeface_port=max(1, min(65535, int(data.get("openseeface_port", data.get("port", VMC_VSEEFACE_SENDER_PORT)) or VMC_VSEEFACE_SENDER_PORT))),
            width=max(1, int(data.get("width", 640) or 640)),
            height=max(1, int(data.get("height", 360) or 360)),
            fps=max(1.0, float(data.get("fps", 24.0) or 24.0)),
            model=max(0, int(data.get("model", 3) or 3)),
            detection_threshold=max(0.0, min(1.0, float(data.get("detection_threshold", 0.35) or 0.35))),
            try_hard=bool(data.get("try_hard", False)),
            crop=_normalize_crop(data.get("crop")),
            realtime=bool(data.get("realtime", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "camera_device_id": self.camera_device_id,
            "camera_device_name": self.camera_device_name,
            "camera_index": self.camera_index,
            "video_path": self.video_path,
            "media_pool_id": self.media_pool_id,
            "track_id": self.track_id,
            "clip_id": self.clip_id,
            "source_in_ms": int(self.source_in_ms),
            "source_out_ms": int(self.source_out_ms),
            "timeline_in_ms": int(self.timeline_in_ms),
            "timeline_out_ms": int(self.timeline_out_ms),
            "openseeface_host": self.openseeface_host,
            "openseeface_port": int(self.openseeface_port),
            "width": int(self.width),
            "height": int(self.height),
            "fps": float(self.fps),
            "model": int(self.model),
            "detection_threshold": float(self.detection_threshold),
            "try_hard": bool(self.try_hard),
            "crop": list(self.crop) if self.crop else None,
            "realtime": bool(self.realtime),
        }


@dataclass
class VSeeFaceBridgeConfig:
    vseeface_exe: str = ""
    avatar_vrm: str = ""
    auto_launch: bool = True
    arguments: list[str] = field(default_factory=list)
    capture: VSeeFaceCaptureConfig = field(default_factory=VSeeFaceCaptureConfig)
    tracking: VSeeFaceTrackingConfig = field(default_factory=VSeeFaceTrackingConfig)
    input_source: VSeeFaceInputConfig = field(default_factory=VSeeFaceInputConfig)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "VSeeFaceBridgeConfig":
        data = payload or {}
        return cls(
            vseeface_exe=str(data.get("vseeface_exe") or data.get("exe") or ""),
            avatar_vrm=str(data.get("avatar_vrm") or data.get("vrm") or ""),
            auto_launch=bool(data.get("auto_launch", True)),
            arguments=[str(item) for item in (data.get("arguments") or [])],
            capture=VSeeFaceCaptureConfig.from_mapping(data.get("capture") if isinstance(data.get("capture"), Mapping) else {}),
            tracking=VSeeFaceTrackingConfig.from_mapping(data.get("tracking") if isinstance(data.get("tracking"), Mapping) else {}),
            input_source=VSeeFaceInputConfig.from_mapping(data.get("input") if isinstance(data.get("input"), Mapping) else {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": BRIDGE_SCHEMA,
            "integration_mode": INTEGRATION_MODE,
            "vseeface_exe": self.vseeface_exe,
            "avatar_vrm": self.avatar_vrm,
            "auto_launch": bool(self.auto_launch),
            "arguments": list(self.arguments),
            "capture": self.capture.to_dict(),
            "tracking": self.tracking.to_dict(),
            "input": self.input_source.to_dict(),
        }


def default_vseeface_exe(root: str | Path | None = None) -> Path:
    return default_vseeface_install_dir(root) / "VSeeFace" / "VSeeFace.exe"


def default_vseeface_install_dir(root: str | Path | None = None) -> Path:
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    return root_path / "external" / "tools" / "vseeface"


def default_milica_vrm(root: str | Path | None = None) -> Path:
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    return root_path / "external" / "assets" / "vtuber" / "booth_milica" / "Milica1.3free" / "Milica_v1.3.vrm"


def default_vseeface_bridge_config(root: str | Path | None = None) -> VSeeFaceBridgeConfig:
    return VSeeFaceBridgeConfig(
        vseeface_exe=str(default_vseeface_exe(root)),
        avatar_vrm=str(default_milica_vrm(root)),
    )


def vseeface_bridge_contract() -> dict[str, Any]:
    return {
        "schema": BRIDGE_SCHEMA,
        "integration_mode": INTEGRATION_MODE,
        "non_goals": [
            "do not embed VSeeFace binaries into TigerCapture runtime modules",
            "do not link against or modify VSeeFace internals",
            "do not make project files depend on VSeeFace being installed",
        ],
        "owns": [
            "external process launch plan",
            "VRM0 compatibility preflight",
            "capture source metadata",
            "capture readiness/fallback metadata",
            "internal VRM renderer fallback routing",
            "BroadcastScene source adapter",
            "OpenSeeFace video input planning",
            "future VMC/OSC tracking sync contract",
        ],
        "capture_methods": sorted(SUPPORTED_CAPTURE_METHODS),
        "fallback_modes": [CAPTURE_FALLBACK_SUPPRESS_BLACK_FRAME, CAPTURE_FALLBACK_INTERNAL_VRM],
        "framing_presets": sorted(SUPPORTED_FRAMING_PRESETS),
        "input_modes": sorted(SUPPORTED_INPUT_MODES),
        "input_source_kinds": sorted(SUPPORTED_INPUT_SOURCE_KINDS),
        "default_framing": FRAMING_BUST_UP,
        "broadcast_source_type": SOURCE_VSEEFACE,
    }


def build_vseeface_launch_plan(config: VSeeFaceBridgeConfig | Mapping[str, Any]) -> dict[str, Any]:
    cfg = config if isinstance(config, VSeeFaceBridgeConfig) else VSeeFaceBridgeConfig.from_mapping(config)
    exe = Path(cfg.vseeface_exe)
    args = [str(exe), *cfg.arguments]
    return {
        "schema": BRIDGE_SCHEMA,
        "integration_mode": INTEGRATION_MODE,
        "ok": exe.is_file(),
        "command": args,
        "cwd": str(exe.parent) if exe.parent else "",
        "auto_launch": bool(cfg.auto_launch),
        "errors": [] if exe.is_file() else ["vseeface_exe_missing"],
    }


def build_vseeface_install_status(
    config: VSeeFaceBridgeConfig | Mapping[str, Any] | None = None,
    *,
    root: str | Path | None = None,
    downloads_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return VSeeFace dependency/install status for setup UI."""
    cfg = config if isinstance(config, VSeeFaceBridgeConfig) else VSeeFaceBridgeConfig.from_mapping(config or {})
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    configured_exe = Path(cfg.vseeface_exe) if str(cfg.vseeface_exe or "").strip() else default_vseeface_exe(root_path)
    default_exe = default_vseeface_exe(root_path)
    install_dir = default_vseeface_install_dir(root_path)
    local_zips = _local_vseeface_zip_candidates(root_path, downloads_dir=downloads_dir)
    installed = configured_exe.is_file()
    default_installed = default_exe.is_file()
    if installed:
        state = "installed"
        tone = "ok"
        text = "VSeeFace executable is configured."
    elif default_installed:
        state = "installed_default"
        tone = "warning"
        text = "VSeeFace exists in the default sidecar folder but is not selected yet."
    elif local_zips:
        state = "zip_available"
        tone = "warning"
        text = "A local VSeeFace zip is available for sidecar install."
    else:
        state = "missing"
        tone = "blocked"
        text = "VSeeFace is not installed for the bridge."
    return {
        "schema": BRIDGE_INSTALL_SCHEMA,
        "state": state,
        "installed": installed,
        "default_installed": default_installed,
        "tone": tone,
        "text": text,
        "configured_exe": str(configured_exe),
        "default_exe": str(default_exe),
        "install_dir": str(install_dir),
        "download_page_url": VSEEFACE_DOWNLOAD_PAGE_URL,
        "local_zip_candidates": [str(item) for item in local_zips[:5]],
        "actions": [
            build_vseeface_install_action(config or default_vseeface_bridge_config(root_path), install_status={
                "state": state,
                "local_zip_candidates": [str(item) for item in local_zips[:5]],
                "install_dir": str(install_dir),
                "default_exe": str(default_exe),
            }),
            build_vseeface_connect_installed_action(install_status={
                "state": state,
                "default_exe": str(default_exe),
            }),
            _bridge_action(
                ACTION_SELECT_VSEEFACE_EXE,
                "Select existing VSeeFace.exe",
                "Choose an existing VSeeFace executable instead of installing a sidecar copy.",
                kind="ui",
                primary=False,
            ),
        ],
    }


def build_vseeface_install_plan(
    config: VSeeFaceBridgeConfig | Mapping[str, Any] | None = None,
    *,
    source_zip: str | Path | None = None,
    download_url: str = "",
    install_dir: str | Path | None = None,
    out_path: str | Path = "debugCapture\\vseeface_install_report.json",
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Return the explicit tool plan for installing the external sidecar."""
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    cfg = config if isinstance(config, VSeeFaceBridgeConfig) else VSeeFaceBridgeConfig.from_mapping(config or {})
    target_dir = Path(install_dir) if install_dir else default_vseeface_install_dir(root_path)
    configured_exe = Path(cfg.vseeface_exe) if str(cfg.vseeface_exe or "").strip() else target_dir / "VSeeFace" / "VSeeFace.exe"
    errors: list[str] = []
    warnings: list[str] = []
    if configured_exe.is_file():
        warnings.append("vseeface_already_installed")
    args = [
        "tools\\install_vseeface_sidecar.py",
        "--install-dir",
        str(target_dir),
        "--out",
        str(out_path or "debugCapture\\vseeface_install_report.json"),
    ]
    if source_zip:
        args.extend(["--source-zip", str(source_zip)])
    if download_url:
        args.extend(["--download-url", str(download_url)])
    return {
        "schema": BRIDGE_INSTALL_SCHEMA,
        "ok": not errors,
        "action_id": ACTION_INSTALL_VSEEFACE_SIDECAR,
        "auto_run": False,
        "requires_user_initiation": True,
        "requires_admin": False,
        "would_write_when_executed": True,
        "install_dir": str(target_dir),
        "expected_exe": str(target_dir / "VSeeFace" / "VSeeFace.exe"),
        "download_page_url": VSEEFACE_DOWNLOAD_PAGE_URL,
        "source_zip": str(source_zip or ""),
        "download_url": str(download_url or ""),
        "steps": [_tool_step("install_vseeface_sidecar", r".\.venv\Scripts\python.exe", args)],
        "errors": errors,
        "warnings": warnings,
        "notes": [
            "The tool may extract a local VSeeFace zip or download a URL only after explicit user execution.",
            "VSeeFace remains an external sidecar and is not embedded into TigerCapture.",
        ],
    }


def build_vseeface_install_action(
    config: VSeeFaceBridgeConfig | Mapping[str, Any] | None = None,
    *,
    install_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    status = install_status if isinstance(install_status, Mapping) else {}
    source_zip = ""
    local = status.get("local_zip_candidates") if isinstance(status.get("local_zip_candidates"), list) else []
    if local:
        source_zip = str(local[0])
    plan = build_vseeface_install_plan(
        config,
        source_zip=source_zip,
        install_dir=str(status.get("install_dir") or "") or None,
    )
    review_step = _ui_step(
        "review_vseeface_install",
        "dependency_installer",
        "Review the VSeeFace sidecar install source before running the installer.",
        registry_action="vtuber.vseeface_install_plan",
        form={
            "submit_action": "vtuber.vseeface_install_plan",
            "params": [
                {
                    "name": "source_zip",
                    "label": "VSeeFace zip",
                    "kind": "file",
                    "required": False,
                    "must_exist": True,
                    "file_filter": "VSeeFace zip (VSeeFace*.zip);;Zip files (*.zip)",
                },
                {
                    "name": "download_url",
                    "label": "Download URL",
                    "kind": "url",
                    "required": False,
                },
                {
                    "name": "install_dir",
                    "label": "Install folder",
                    "kind": "directory",
                    "required": False,
                },
            ],
        },
    )
    action_plan = dict(plan)
    action_plan["steps"] = [review_step] + [dict(step) for step in plan.get("steps", []) if isinstance(step, Mapping)]
    return {
        "id": ACTION_INSTALL_VSEEFACE_SIDECAR,
        "label": "Install VSeeFace sidecar",
        "description": "Download or extract VSeeFace into TigerCapture's external sidecar folder, then connect the bridge.",
        "kind": "tool",
        "primary": str(status.get("state") or "") in {"missing", "zip_available"},
        "blocking": str(status.get("state") or "") in {"missing", "zip_available"},
        "auto_run": False,
        "plan": action_plan,
    }


def build_vseeface_connect_installed_action(
    *,
    install_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    status = install_status if isinstance(install_status, Mapping) else {}
    default_exe = str(status.get("default_exe") or default_vseeface_exe())
    return {
        "id": ACTION_CONNECT_INSTALLED_VSEEFACE,
        "label": "Connect installed VSeeFace",
        "description": "Use the installed sidecar VSeeFace.exe for this bridge.",
        "kind": "ui",
        "primary": str(status.get("state") or "") in {"installed", "installed_default"},
        "blocking": str(status.get("state") or "") == "installed_default",
        "auto_run": False,
        "plan": _build_vseeface_bridge_action_plan(ACTION_CONNECT_INSTALLED_VSEEFACE),
        "default_exe": default_exe,
    }


def _local_vseeface_zip_candidates(
    root: str | Path | None = None,
    *,
    downloads_dir: str | Path | None = None,
) -> list[Path]:
    roots: list[Path] = []
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    roots.append(root_path / "debugCapture")
    if downloads_dir:
        roots.append(Path(downloads_dir))
    else:
        for base in (os.environ.get("USERPROFILE"), str(Path.home())):
            if base:
                roots.append(Path(base) / "Downloads")
    seen: set[str] = set()
    results: list[Path] = []
    for folder in roots:
        try:
            candidates = sorted(
                folder.glob("VSeeFace*.zip"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            continue
        for candidate in candidates:
            key = str(candidate.resolve()) if candidate.exists() else str(candidate)
            if key in seen or not candidate.is_file():
                continue
            seen.add(key)
            results.append(candidate)
    return results


def vseeface_bridge_preflight(config: VSeeFaceBridgeConfig | Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = config if isinstance(config, VSeeFaceBridgeConfig) else VSeeFaceBridgeConfig.from_mapping(config or {})
    exe = Path(cfg.vseeface_exe)
    install = build_vseeface_install_status(cfg)
    vrm = inspect_vrm_profile(cfg.avatar_vrm)
    launch = build_vseeface_launch_plan(cfg)
    errors: list[str] = []
    warnings: list[str] = []
    if not exe.is_file():
        errors.append("vseeface_exe_missing")
    if not vrm.get("ok"):
        errors.extend(str(item) for item in vrm.get("errors") or ["vrm_invalid"])
    elif not vrm.get("vseeface_compatible"):
        errors.append("vseeface_requires_vrm0")
    if cfg.input_source.mode == INPUT_OPENSEEFACE_VIDEO and not Path(cfg.input_source.video_path).is_file():
        warnings.append("openseeface_input_video_missing")
    warnings.extend(str(item) for item in vrm.get("warnings") or [])
    return {
        "schema": BRIDGE_SCHEMA,
        "integration_mode": INTEGRATION_MODE,
        "ok": not errors,
        "vseeface_exe": str(exe),
        "exe_exists": exe.is_file(),
        "avatar_vrm": str(cfg.avatar_vrm),
        "vrm": vrm,
        "capture": cfg.capture.to_dict(),
        "tracking": cfg.tracking.to_dict(),
        "input": cfg.input_source.to_dict(),
        "launch": launch,
        "install": install,
        "errors": errors,
        "warnings": warnings,
    }


def build_vseeface_sidecar_settings_preview(
    config: VSeeFaceBridgeConfig | Mapping[str, Any] | None = None,
    *,
    settings_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return the VSeeFace settings.ini changes that would be written.

    This is intentionally read-only. It prepares a user-reviewable payload for
    the external VSeeFace sidecar but does not write files or launch processes.
    """
    cfg = config if isinstance(config, VSeeFaceBridgeConfig) else VSeeFaceBridgeConfig.from_mapping(config or {})
    from app.vtuber.vseeface_sidecar_config import (
        OPENSEEFACE_TRACKING_CAMERA_NAME,
        build_sidecar_settings_values,
        default_vseeface_settings_path,
    )

    target = Path(settings_path) if settings_path else default_vseeface_settings_path()
    errors: list[str] = []
    warnings: list[str] = []
    avatar = str(cfg.avatar_vrm or "").strip()
    if not avatar:
        errors.append("avatar_vrm_missing")
    elif not Path(avatar).is_file():
        warnings.append("avatar_vrm_file_not_found")
    values: dict[str, str] = {}
    if avatar:
        values = build_sidecar_settings_values(
            avatar_vrm=avatar,
            openseeface_host=cfg.input_source.openseeface_host,
            openseeface_port=cfg.input_source.openseeface_port,
            camera_name=OPENSEEFACE_TRACKING_CAMERA_NAME,
            enable_virtual_camera=cfg.capture.method == CAPTURE_VIRTUAL_CAMERA,
        )
    return {
        "schema": BRIDGE_SIDECAR_SETTINGS_SCHEMA,
        "ok": not errors,
        "read_only": True,
        "would_write": False,
        "settings_path": str(target),
        "section": "OpenSeeDemo",
        "values": values,
        "input": cfg.input_source.to_dict(),
        "capture": cfg.capture.to_dict(),
        "errors": errors,
        "warnings": warnings,
        "notes": [
            "This preview does not write settings.ini.",
            "IP and Port configure VSeeFace's OpenSeeFace tracking input.",
            "VSeeFace remains an external sidecar.",
        ],
    }


def build_vseeface_sidecar_apply_plan(
    config: VSeeFaceBridgeConfig | Mapping[str, Any] | None = None,
    *,
    settings_path: str | Path | None = None,
    out_path: str | Path = "debugCapture\\vseeface_sidecar_config_report.json",
) -> dict[str, Any]:
    """Return the non-auto-run tool plan for writing sidecar settings."""
    preview = build_vseeface_sidecar_settings_preview(config, settings_path=settings_path)
    errors = [str(item) for item in preview.get("errors") or []]
    warnings = [str(item) for item in preview.get("warnings") or []]
    values = preview.get("values") if isinstance(preview.get("values"), Mapping) else {}
    capture = preview.get("capture") if isinstance(preview.get("capture"), Mapping) else {}
    ok = bool(preview.get("ok")) and bool(values.get("AvatarFile"))
    if not values.get("AvatarFile") and "avatar_vrm_missing" not in errors:
        errors.append("avatar_vrm_missing")
        ok = False

    args = [
        "tools\\configure_vseeface_sidecar.py",
        "--settings",
        str(preview.get("settings_path") or ""),
        "--avatar-vrm",
        str(values.get("AvatarFile") or ""),
        "--openseeface-host",
        str(values.get("IP") or VMC_DEFAULT_HOST),
        "--openseeface-port",
        str(values.get("Port") or VMC_VSEEFACE_SENDER_PORT),
        "--camera-name",
        str(values.get("CameraName") or "[OpenSeeFace tracking]"),
        "--out",
        str(out_path or "debugCapture\\vseeface_sidecar_config_report.json"),
    ]
    if str(capture.get("method") or "") != CAPTURE_VIRTUAL_CAMERA:
        args.append("--disable-virtual-camera")

    return {
        "schema": BRIDGE_SIDECAR_APPLY_PLAN_SCHEMA,
        "ok": ok,
        "action_id": ACTION_APPLY_SIDECAR_SETTINGS,
        "auto_run": False,
        "requires_user_initiation": True,
        "requires_admin": False,
        "preview_only": True,
        "would_write_when_executed": True,
        "settings_preview": preview,
        "steps": [_tool_step("write_sidecar_settings", r".\.venv\Scripts\python.exe", args)] if ok else [],
        "errors": errors,
        "warnings": warnings,
        "notes": [
            "This plan does not write settings.ini until an explicit executor runs the tool step.",
            "The tool step writes only VSeeFace's external sidecar settings.ini.",
        ],
    }


def build_vseeface_sidecar_workflow(
    config: VSeeFaceBridgeConfig | Mapping[str, Any] | None = None,
    *,
    settings_path: str | Path | None = None,
    out_path: str | Path = "debugCapture\\vseeface_sidecar_config_report.json",
    confirm: bool = False,
    allow_admin: bool = False,
) -> dict[str, Any]:
    """Return the full read-only UI workflow for sidecar settings."""
    from app.vtuber.vseeface_action_plan import build_vseeface_execution_gate
    from app.vtuber.vseeface_plan_executor import execute_vseeface_plan

    plan = build_vseeface_sidecar_apply_plan(
        config,
        settings_path=settings_path,
        out_path=out_path,
    )
    preview = plan.get("settings_preview") if isinstance(plan.get("settings_preview"), Mapping) else {}
    gate = build_vseeface_execution_gate(
        plan,
        confirm=bool(confirm),
        allow_admin=bool(allow_admin),
    )
    executor = execute_vseeface_plan(
        plan,
        confirm=bool(confirm),
        allow_admin=bool(allow_admin),
        execute=False,
    )
    state = _sidecar_workflow_state(preview, plan, gate, confirm=bool(confirm))
    return {
        "schema": BRIDGE_SIDECAR_WORKFLOW_SCHEMA,
        "ok": state in {"confirmation_required", "ready_to_execute"},
        "state": state,
        "read_only": True,
        "confirm": bool(confirm),
        "allow_admin": bool(allow_admin),
        "settings_preview": preview,
        "apply_plan": plan,
        "execution_gate": gate,
        "executor_dry_run": executor,
        "view": _sidecar_workflow_view(preview, plan, gate, executor, state=state),
    }


def build_vseeface_input_source_options(
    *,
    project_snapshot: Mapping[str, Any] | None = None,
    camera_devices: list[Mapping[str, Any]] | None = None,
    selected: VSeeFaceInputConfig | Mapping[str, Any] | None = None,
    input_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return UI-ready tracking input choices for VSeeFace/OpenSeeFace.

    VSeeFaceCamera registration is still a capture-output setup step. This
    list controls the face-tracking input: a real camera, a media-pool video,
    or a timeline clip that should be fed to the bundled OpenSeeFace tracker.
    """
    selected_input = selected if isinstance(selected, VSeeFaceInputConfig) else VSeeFaceInputConfig.from_mapping(selected or {})
    diagnostics = input_diagnostics if isinstance(input_diagnostics, Mapping) else {}
    options: list[dict[str, Any]] = []
    for row in _camera_input_options(camera_devices or [], selected_input, diagnostics):
        options.append(row)
    if isinstance(project_snapshot, Mapping):
        for row in _media_pool_input_options(project_snapshot, selected_input, diagnostics):
            options.append(row)
        for row in _timeline_clip_input_options(project_snapshot, selected_input, diagnostics):
            options.append(row)

    selected_id = _selected_input_option_id(selected_input, options)
    if not selected_id and selected_input.mode == INPUT_OPENSEEFACE_VIDEO and selected_input.video_path:
        custom = _video_file_input_option(selected_input)
        options.append(custom)
        selected_id = custom["id"]
    if not selected_id and options:
        selected_id = str(options[0].get("id") or "")
    selected_option = next((item for item in options if str(item.get("id") or "") == selected_id), None)
    input_summary = _input_sources_health_summary(options, selected_option)
    fallback = _input_sources_fallback_option(options, selected_option)
    if fallback:
        input_summary.update({
            "fallback_available": True,
            "recommended_fallback_id": str(fallback.get("id") or ""),
            "recommended_fallback_label": str(fallback.get("label") or ""),
            "recommended_fallback_kind": str(fallback.get("kind") or ""),
            "recommended_fallback_reason": "selected_tracking_input_unavailable",
        })
    return {
        "schema": INPUT_SOURCE_SCHEMA,
        "action": ACTION_SELECT_TRACKING_INPUT,
        "selected_id": selected_id,
        "selected": selected_option or _input_config_to_choice(selected_input),
        "options": options,
        "fallback": fallback,
        "counts": {
            "camera_devices": sum(1 for item in options if item.get("kind") == INPUT_KIND_CAMERA_DEVICE),
            "media_pool_videos": sum(1 for item in options if item.get("kind") == INPUT_KIND_MEDIA_POOL_VIDEO),
            "timeline_video_clips": sum(1 for item in options if item.get("kind") == INPUT_KIND_TIMELINE_VIDEO_CLIP),
        },
        "diagnostics": input_summary,
        "warnings": _input_sources_warnings(options, input_summary),
    }


def build_vseeface_bridge_status(
    config: VSeeFaceBridgeConfig | Mapping[str, Any],
    *,
    capture_diagnostics: Mapping[str, Any] | None = None,
    input_diagnostics: Mapping[str, Any] | None = None,
    project_snapshot: Mapping[str, Any] | None = None,
    camera_devices: list[Mapping[str, Any]] | None = None,
    width: int = 1920,
    height: int = 1080,
    fps: float = 30.0,
) -> dict[str, Any]:
    cfg = config if isinstance(config, VSeeFaceBridgeConfig) else VSeeFaceBridgeConfig.from_mapping(config)
    input_sources = build_vseeface_input_source_options(
        project_snapshot=project_snapshot,
        camera_devices=camera_devices,
        selected=cfg.input_source,
        input_diagnostics=input_diagnostics,
    )
    resolved_cfg = _bridge_config_with_resolved_input(cfg, input_sources)
    preflight = vseeface_bridge_preflight(resolved_cfg)
    sidecar_settings = build_vseeface_sidecar_settings_preview(resolved_cfg)
    scene = build_vseeface_broadcast_scene(
        resolved_cfg,
        width=width,
        height=height,
        fps=fps,
        capture_diagnostics=capture_diagnostics,
    )
    vseeface_source = next((item for item in scene["sources"] if item.get("id") == resolved_cfg.capture.source_id), {})
    source_settings = vseeface_source.get("settings") if isinstance(vseeface_source.get("settings"), Mapping) else {}
    capture_health = source_settings.get("capture_health") if isinstance(source_settings.get("capture_health"), Mapping) else {}
    available_frames = {resolved_cfg.capture.source_id: True} if capture_health.get("ready") is True else {}
    for scene_source in scene.get("sources", []):
        if isinstance(scene_source, Mapping) and str(scene_source.get("type") or "") == SOURCE_INTERNAL_VRM:
            available_frames[str(scene_source.get("id") or INTERNAL_VRM_FALLBACK_SOURCE_ID)] = True
    scene_diag = broadcast_scene_diagnostics(scene, available_frames)
    state = _resolve_bridge_state(preflight, capture_health, scene_diag)
    ui = _vseeface_bridge_state_ui(state, capture_health, preflight)
    actions = build_vseeface_bridge_actions(state, ui=ui, preflight=preflight, capture=capture_health)
    sidecar_action = build_vseeface_sidecar_settings_action(resolved_cfg, sidecar_settings=sidecar_settings)
    if sidecar_action is not None:
        actions.append(sidecar_action)
    report = {
        "schema": BRIDGE_SCHEMA,
        "integration_mode": INTEGRATION_MODE,
        "ok": state in {BRIDGE_STATE_READY, BRIDGE_STATE_NEEDS_PROBE, BRIDGE_STATE_DEGRADED},
        "state": state,
        "ui": ui,
        "actions": actions,
        "preflight": preflight,
        "input_sources": input_sources,
        "sidecar_settings": sidecar_settings,
        "capture": capture_health,
        "scene_diagnostics": scene_diag,
        "scene": scene,
    }
    report["setup_flow"] = build_vseeface_setup_flow(report)
    report["view"] = build_vseeface_bridge_view_model(report)
    return report


def build_vseeface_setup_flow(status: Mapping[str, Any]) -> dict[str, Any]:
    """Return a UI wizard-style flow from a bridge status report."""
    state = str(status.get("state") or BRIDGE_STATE_NEEDS_PROBE)
    preflight = status.get("preflight") if isinstance(status.get("preflight"), Mapping) else {}
    install = preflight.get("install") if isinstance(preflight.get("install"), Mapping) else {}
    capture = status.get("capture") if isinstance(status.get("capture"), Mapping) else {}
    input_sources = status.get("input_sources") if isinstance(status.get("input_sources"), Mapping) else {}
    sidecar_settings = status.get("sidecar_settings") if isinstance(status.get("sidecar_settings"), Mapping) else {}
    scene_diag = status.get("scene_diagnostics") if isinstance(status.get("scene_diagnostics"), Mapping) else {}
    actions = status.get("actions") if isinstance(status.get("actions"), list) else []
    action_by_id = {str(item.get("id") or ""): item for item in actions if isinstance(item, Mapping)}
    errors = [str(item) for item in preflight.get("errors") or []]
    warnings = [str(item) for item in preflight.get("warnings") or []]
    steps = [
        _setup_flow_step(
            "vseeface_install",
            "VSeeFace install",
            _install_setup_step_text(install),
            _install_setup_step_state(install),
            action_by_id.get(ACTION_INSTALL_VSEEFACE_SIDECAR),
            blocking=_install_setup_is_blocking(install),
        ),
        _setup_flow_step(
            "vseeface_exe",
            "VSeeFace executable",
            "Select the external VSeeFace executable.",
            _vseeface_exe_setup_step_state(preflight, install),
            action_by_id.get(ACTION_SELECT_VSEEFACE_EXE),
            blocking=not bool(preflight.get("exe_exists")),
        ),
        _setup_flow_step(
            "vrm0_avatar",
            "VRM0 avatar",
            "Select a VSeeFace-compatible VRM0 avatar.",
            _vrm_setup_step_state(preflight),
            action_by_id.get(ACTION_SELECT_VRM0_AVATAR),
            blocking="vseeface_requires_vrm0" in errors or "file_missing" in errors,
        ),
        _setup_flow_step(
            "tracking_input",
            "Tracking input",
            _tracking_input_step_text(input_sources),
            "warning" if "openseeface_input_video_missing" in warnings else "done",
            action_by_id.get(ACTION_SELECT_TRACKING_INPUT),
            blocking=False,
        ),
        _setup_flow_step(
            "capture_backend",
            "Capture backend",
            _capture_setup_step_text(capture),
            _capture_setup_step_state(state, capture, preflight),
            _capture_setup_action(action_by_id, capture, state),
            blocking=_capture_setup_is_blocking(capture),
        ),
        _setup_flow_step(
            "broadcast_scene",
            "Broadcast scene",
            _broadcast_setup_step_text(state, scene_diag),
            _broadcast_setup_step_state(state, scene_diag),
            action_by_id.get(ACTION_USE_CAPTURE_SOURCE) or action_by_id.get(ACTION_KEEP_FALLBACK_SOURCE),
            blocking=False,
        ),
    ]
    current = next((step for step in steps if step["state"] in {"current", "blocked", "warning"}), None)
    completed = sum(1 for step in steps if step["state"] == "done")
    return {
        "schema": BRIDGE_SETUP_FLOW_SCHEMA,
        "state": state,
        "ready": state == BRIDGE_STATE_READY,
        "current_step_id": str((current or {}).get("id") or ""),
        "completed_steps": completed,
        "total_steps": len(steps),
        "progress": completed / max(1, len(steps)),
        "requires_admin": any(bool(step.get("requires_admin")) for step in steps if step["state"] in {"current", "blocked"}),
        "steps": steps,
    }


def summarize_vseeface_capture_status(
    diagnostics: Mapping[str, Any] | None,
    *,
    method: str | None = None,
) -> dict[str, Any]:
    capture_method = str(method or CAPTURE_WINDOW)
    if capture_method not in SUPPORTED_CAPTURE_METHODS:
        capture_method = CAPTURE_WINDOW
    if not isinstance(diagnostics, Mapping):
        return {
            "schema": BRIDGE_SCHEMA,
            "method": capture_method,
            "probed": False,
            "ready": None,
            "status": CAPTURE_STATUS_NOT_PROBED,
            "ui": vseeface_capture_status_ui(CAPTURE_STATUS_NOT_PROBED, ready=None),
            "fallback_behavior": CAPTURE_FALLBACK_SUPPRESS_BLACK_FRAME,
            "fallback": _capture_fallback_summary(CAPTURE_STATUS_NOT_PROBED, None),
            "errors": [],
            "warnings": [],
            "recommendations": [],
        }

    errors = _collect_string_items(diagnostics, "errors")
    warnings = _collect_string_items(diagnostics, "warnings")
    recommendations = _collect_string_items(diagnostics, "recommendations")
    status = str(diagnostics.get("status") or "").strip()
    capture_method = _infer_capture_method_from_diagnostics(diagnostics, capture_method)
    ok_value = diagnostics.get("ok")
    ready: bool | None = None

    if (
        status == CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK
        or CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK in errors
        or CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK in _collect_nested_errors(diagnostics)
    ):
        status = CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK
        ready = False
        if "fix_vseeface_rendering_or_start_scene" not in recommendations:
            recommendations.append("fix_vseeface_rendering_or_start_scene")
    elif (
        status == CAPTURE_STATUS_BLOCKED_REGISTRATION
        or "vseeface_camera_not_registered" in errors
        or _virtual_camera_requires_registration(diagnostics)
    ):
        status = CAPTURE_STATUS_BLOCKED_REGISTRATION
        ready = False
        if "run_register_vseeface_camera_admin_bat_and_approve_uac" not in recommendations:
            recommendations.append("run_register_vseeface_camera_admin_bat_and_approve_uac")
    elif status == CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED or "virtual_camera_capture_failed" in errors:
        status = CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED
        ready = False
        if "confirm_vseeface_camera_enabled_and_vseeface_running" not in recommendations:
            recommendations.append("confirm_vseeface_camera_enabled_and_vseeface_running")
    elif bool(diagnostics.get("usable_window_capture")) and capture_method == CAPTURE_WINDOW:
        status = CAPTURE_STATUS_READY
        ready = True
    elif bool(diagnostics.get("usable_virtual_camera")) and capture_method == CAPTURE_VIRTUAL_CAMERA:
        status = CAPTURE_STATUS_READY
        ready = True
    elif status in {"ready", "ready_for_capture", "window_capture_ready"}:
        ready = True
        status = CAPTURE_STATUS_READY
    elif ok_value is not None:
        ready = bool(ok_value)
        if not status:
            status = CAPTURE_STATUS_READY if ready else CAPTURE_STATUS_UNAVAILABLE
    else:
        status = status or CAPTURE_STATUS_NOT_PROBED

    return {
        "schema": BRIDGE_SCHEMA,
        "method": capture_method,
        "probed": True,
        "ready": ready,
        "status": status,
        "ui": vseeface_capture_status_ui(status, ready=ready),
        "fallback_behavior": CAPTURE_FALLBACK_SUPPRESS_BLACK_FRAME,
        "fallback": _capture_fallback_summary(status, ready),
        "errors": errors,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def _capture_fallback_summary(status: str, ready: bool | None) -> dict[str, Any]:
    if ready is False:
        return {
            "mode": CAPTURE_FALLBACK_INTERNAL_VRM,
            "source_id": INTERNAL_VRM_FALLBACK_SOURCE_ID,
            "reason": str(status or CAPTURE_STATUS_UNAVAILABLE),
            "program_output": True,
            "requires_vseeface_capture": False,
        }
    return {
        "mode": "none",
        "source_id": "",
        "reason": "",
        "program_output": False,
        "requires_vseeface_capture": False,
    }


def _fallback_to_view(capture: Mapping[str, Any]) -> dict[str, Any]:
    fallback = capture.get("fallback") if isinstance(capture.get("fallback"), Mapping) else {}
    mode = str(fallback.get("mode") or "none")
    active = mode == CAPTURE_FALLBACK_INTERNAL_VRM and capture.get("ready") is False
    return {
        "mode": mode,
        "active": bool(active),
        "source_id": str(fallback.get("source_id") or ""),
        "label": "Internal VRM fallback" if active else "None",
        "program_output": bool(fallback.get("program_output", False)),
        "requires_vseeface_capture": bool(fallback.get("requires_vseeface_capture", False)),
    }


def vseeface_capture_status_ui(status: str, *, ready: bool | None = None) -> dict[str, str]:
    key = str(status or CAPTURE_STATUS_NOT_PROBED)
    if ready is True or key == CAPTURE_STATUS_READY:
        return {
            "label": "Ready",
            "severity": "ok",
            "action": "use_capture_source",
        }
    if key == CAPTURE_STATUS_NOT_PROBED:
        return {
            "label": "Not probed",
            "severity": "info",
            "action": "run_capture_probe",
        }
    if key == CAPTURE_STATUS_BLOCKED_REGISTRATION:
        return {
            "label": "Camera setup required",
            "severity": "blocked",
            "action": ACTION_REGISTER_VSEEFACE_CAMERA,
        }
    if key == CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED:
        return {
            "label": "Capture failed",
            "severity": "warning",
            "action": ACTION_CONFIRM_VIRTUAL_CAMERA,
        }
    if key == CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK or "black" in key:
        return {
            "label": "Black frame",
            "severity": "blocked",
            "action": "fix_vseeface_rendering_or_start_scene",
        }
    return {
        "label": "Capture unavailable",
        "severity": "warning",
        "action": "choose_spout2_or_virtual_camera_fallback",
    }


def build_vseeface_bridge_actions(
    state: str,
    *,
    ui: Mapping[str, Any] | None = None,
    preflight: Mapping[str, Any] | None = None,
    capture: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    action_id = str((ui or {}).get("action") or "")
    errors = [str(item) for item in (preflight or {}).get("errors") or []]
    input_source = preflight.get("input") if isinstance((preflight or {}).get("input"), Mapping) else {}
    actions: list[dict[str, Any]] = []
    if state == BRIDGE_STATE_READY:
        actions.append(_bridge_action(ACTION_USE_CAPTURE_SOURCE, "Use capture source", "Use the VSeeFace source in the broadcast scene.", primary=True))
        actions.append(_broadcast_framing_action())
        actions.append(_capture_backend_action())
        actions.append(_tracking_input_action())
        return actions
    if state == BRIDGE_STATE_NEEDS_PROBE:
        actions.append(_bridge_action(ACTION_RUN_CAPTURE_PROBE, "Run capture probe", "Probe the selected VSeeFace capture backend before showing it live.", kind="tool", primary=True, input_source=input_source))
        actions.append(_bridge_action(ACTION_START_AND_PROBE_VSEEFACE, "Start VSeeFace and probe", "Launch the external VSeeFace sidecar, then verify live process and capture readiness.", kind="tool", input_source=input_source))
        actions.append(_broadcast_framing_action())
        actions.append(_capture_backend_action())
        actions.append(_tracking_input_action())
        return actions
    if state == BRIDGE_STATE_BLOCKED:
        if action_id == ACTION_SELECT_VSEEFACE_EXE or "vseeface_exe_missing" in errors:
            install = preflight.get("install") if isinstance((preflight or {}).get("install"), Mapping) else {}
            connect_first = str(install.get("state") or "") in {"installed", "installed_default"}
            connect_action = build_vseeface_connect_installed_action(install_status=install)
            install_action = build_vseeface_install_action(preflight, install_status=install)
            actions.extend([connect_action, install_action] if connect_first else [install_action, connect_action])
            actions.append(_bridge_action(ACTION_SELECT_VSEEFACE_EXE, "Select VSeeFace.exe", "Choose the external VSeeFace executable.", primary=not connect_first and str(install.get("state") or "") not in {"missing", "zip_available"}, blocking=True))
        if action_id == ACTION_SELECT_VRM0_AVATAR or "vseeface_requires_vrm0" in errors or "file_missing" in errors:
            actions.append(_bridge_action(ACTION_SELECT_VRM0_AVATAR, "Select VRM0 avatar", "Choose a VSeeFace-compatible VRM0 avatar.", primary=not actions, blocking=True))
        if not actions:
            actions.append(_bridge_action("configure_vseeface_bridge", "Configure bridge", "Complete the VSeeFace executable and VRM0 avatar setup.", primary=True, blocking=True))
        actions.append(_broadcast_framing_action())
        actions.append(_capture_backend_action())
        actions.append(_tracking_input_action())
        return actions
    if state == BRIDGE_STATE_DEGRADED:
        capture_status = str((capture or {}).get("status") or "")
        actions.append(_internal_vrm_fallback_action(primary=True, input_source=input_source))
        if capture_status == CAPTURE_STATUS_BLOCKED_REGISTRATION or action_id == ACTION_REGISTER_VSEEFACE_CAMERA:
            actions.append(_bridge_action(ACTION_REGISTER_VSEEFACE_CAMERA, "Register VSeeFaceCamera", "Run the explicit VSeeFaceCamera registration setup with administrator approval.", kind="manual_setup", primary=False, blocking=True))
            actions.append(_broadcast_framing_action())
            actions.append(_capture_backend_action())
            actions.append(_tracking_input_action())
            return actions
        if capture_status == CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED or action_id == ACTION_CONFIRM_VIRTUAL_CAMERA:
            actions.append(_bridge_action(ACTION_CONFIRM_VIRTUAL_CAMERA, "Confirm virtual camera", "Confirm VSeeFace is running and its virtual camera output is enabled.", kind="manual_setup", primary=False, input_source=input_source))
            actions.append(_broadcast_framing_action())
            actions.append(_capture_backend_action())
            actions.append(_tracking_input_action())
            return actions
        actions.append(_bridge_action(ACTION_FIX_RENDERING_OR_START_SCENE, "Fix VSeeFace render", "Open VSeeFace and confirm the avatar scene renders to the selected capture backend.", kind="manual_setup", primary=False, input_source=input_source))
        if capture and capture.get("method") != CAPTURE_SPOUT2:
            actions.append(_bridge_action("try_spout2_or_other_capture", "Try another capture backend", "Use Spout2 or another capture backend if available.", kind="manual_setup"))
        actions.append(_broadcast_framing_action())
        actions.append(_capture_backend_action())
        actions.append(_tracking_input_action())
        return actions
    return [
        _bridge_action(ACTION_RUN_CAPTURE_PROBE, "Run capture probe", "Probe capture readiness.", kind="tool", primary=True, input_source=input_source),
        _broadcast_framing_action(),
        _capture_backend_action(),
        _tracking_input_action(),
    ]


def build_vseeface_bridge_view_model(status: Mapping[str, Any]) -> dict[str, Any]:
    state = str(status.get("state") or BRIDGE_STATE_NEEDS_PROBE)
    ui = status.get("ui") if isinstance(status.get("ui"), Mapping) else {}
    actions = status.get("actions") if isinstance(status.get("actions"), list) else []
    preflight = status.get("preflight") if isinstance(status.get("preflight"), Mapping) else {}
    install = preflight.get("install") if isinstance(preflight.get("install"), Mapping) else {}
    capture = status.get("capture") if isinstance(status.get("capture"), Mapping) else {}
    input_sources = status.get("input_sources") if isinstance(status.get("input_sources"), Mapping) else {}
    sidecar_settings = status.get("sidecar_settings") if isinstance(status.get("sidecar_settings"), Mapping) else {}
    scene_diag = status.get("scene_diagnostics") if isinstance(status.get("scene_diagnostics"), Mapping) else {}
    primary = next((item for item in actions if isinstance(item, Mapping) and item.get("primary")), None)
    secondaries = [item for item in actions if isinstance(item, Mapping) and not item.get("primary")]
    severity = str(ui.get("severity") or "info")
    return {
        "schema": BRIDGE_VIEW_SCHEMA,
        "title": "VSeeFace Bridge",
        "state": state,
        "show_debug": False,
        "badge": {
            "text": str(ui.get("label") or state),
            "tone": _tone_for_severity(severity),
        },
        "summary": _bridge_view_summary(state, capture, preflight),
        "fallback": _fallback_to_view(capture),
        "dependency": _install_to_view(install),
        "setup_flow": _setup_flow_to_view(status.get("setup_flow") if isinstance(status.get("setup_flow"), Mapping) else {}),
        "input_source": _input_source_to_view(input_sources),
        "sidecar_settings": _sidecar_settings_to_view(sidecar_settings),
        "primary_action": _action_to_view(primary),
        "secondary_actions": [_action_to_view(item) for item in secondaries],
        "cards": [
            _view_card("setup", "Setup", _setup_card_text(preflight), _setup_card_tone(preflight)),
            _view_card("capture", "Capture", _capture_card_text(capture), _capture_card_tone(capture, severity)),
            _view_card("scene", "Scene", _scene_card_text(scene_diag), _scene_card_tone(scene_diag)),
            _view_card("input", "Input", _input_card_text(input_sources), _input_card_tone(input_sources)),
            _view_card("sidecar", "Sidecar", _sidecar_card_text(sidecar_settings), _sidecar_card_tone(sidecar_settings)),
        ],
    }


def build_vseeface_bridge_action_plan(action_id: str) -> dict[str, Any]:
    return _build_vseeface_bridge_action_plan(action_id, input_source=None)


def _build_vseeface_bridge_action_plan(action_id: str, *, input_source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    action = str(action_id or "")
    py = r".\.venv\Scripts\python.exe"
    base = {
        "schema": BRIDGE_ACTION_PLAN_SCHEMA,
        "action_id": action,
        "auto_run": False,
        "requires_user_initiation": True,
        "requires_admin": False,
        "steps": [],
    }
    if action == ACTION_RUN_CAPTURE_PROBE:
        base["steps"] = [
            _tool_step("capture_backend_preflight", py, ["tools\\vseeface_capture_backend_preflight.py"]),
            _tool_step(
                "post_install_verify",
                py,
                _post_install_verify_args(
                    input_source,
                    out="debugCapture\\vseeface_post_install_report.json",
                ),
            ),
        ]
    elif action == ACTION_START_AND_PROBE_VSEEFACE:
        base["would_launch_external_process"] = True
        base["steps"] = [
            _tool_step("capture_backend_preflight", py, ["tools\\vseeface_capture_backend_preflight.py"]),
            _tool_step(
                "launch_and_verify_capture",
                py,
                _post_install_verify_args(
                    input_source,
                    out="debugCapture\\vseeface_post_install_report.json",
                    launch=True,
                ),
            ),
            _tool_step(
                "vseeface_live_check",
                py,
                [
                    "tools\\vseeface_live_check.py",
                    "--out",
                    "debugCapture\\vseeface_live_check.json",
                ],
            ),
            _tool_step("rerun_capture_backend_preflight", py, ["tools\\vseeface_capture_backend_preflight.py"]),
        ]
    elif action == ACTION_INSTALL_VSEEFACE_SIDECAR:
        base["would_write_when_executed"] = True
        install_plan = build_vseeface_install_plan()
        base["steps"] = [dict(step) for step in install_plan.get("steps", []) if isinstance(step, Mapping)]
        base["install_dir"] = install_plan.get("install_dir", "")
        base["expected_exe"] = install_plan.get("expected_exe", "")
        base["download_page_url"] = install_plan.get("download_page_url", "")
    elif action == ACTION_CONNECT_INSTALLED_VSEEFACE:
        base["steps"] = [
            _ui_step(
                "connect_installed_vseeface",
                "dependency_connect",
                "Connect the installed VSeeFace sidecar executable to this bridge.",
                registry_action="vtuber.vseeface_connect_installed_sidecar",
                form={
                    "submit_action": "vtuber.vseeface_connect_installed_sidecar",
                    "params": [
                        {
                            "name": "path",
                            "label": "VSeeFace.exe",
                            "kind": "file",
                            "required": False,
                            "must_exist": True,
                            "file_filter": "VSeeFace.exe (VSeeFace.exe);;Windows executable (*.exe)",
                        }
                    ],
                },
            )
        ]
    elif action == ACTION_REGISTER_VSEEFACE_CAMERA:
        base["requires_admin"] = True
        base["steps"] = [
            _tool_step(
                "prepare_registration_batch",
                py,
                [
                    "tools\\register_vseeface_camera.py",
                    "--out",
                    "debugCapture\\vseeface_camera_registration_plan.json",
                ],
            ),
            _tool_step(
                "launch_admin_registration",
                py,
                [
                    "tools\\register_vseeface_camera.py",
                    "--launch",
                    "--out",
                    "debugCapture\\vseeface_camera_registration_plan.json",
                ],
                requires_admin=True,
            ),
            _tool_step("rerun_capture_backend_preflight", py, ["tools\\vseeface_capture_backend_preflight.py"]),
        ]
    elif action == ACTION_CONFIRM_VIRTUAL_CAMERA:
        base["steps"] = [
            _manual_step("confirm_vseeface_running", "Open VSeeFace and confirm the avatar scene is running."),
            _manual_step("enable_virtual_camera", "Enable or keep enabled the VSeeFace virtual camera output."),
            _tool_step(
                "verify_virtual_camera",
                py,
                _post_install_verify_args(
                    input_source,
                    out="debugCapture\\vseeface_post_install_report.json",
                ),
            ),
        ]
    elif action == ACTION_FIX_RENDERING_OR_START_SCENE:
        base["steps"] = [
            _manual_step("confirm_vseeface_scene", "Open VSeeFace and confirm a VRM0 avatar is loaded and visible."),
            _manual_step("confirm_virtual_camera_enabled", "Confirm VSeeFaceCamera output is enabled."),
            _tool_step(
                "verify_nonblack_capture",
                py,
                _post_install_verify_args(
                    input_source,
                    out="debugCapture\\vseeface_post_install_report.json",
                ),
            ),
        ]
    elif action == ACTION_SELECT_VSEEFACE_EXE:
        base["steps"] = [
            _ui_step(
                "select_vseeface_exe",
                "file_picker",
                "Select the external VSeeFace.exe file.",
                registry_action="vtuber.vseeface_select_exe",
                form={
                    "submit_action": "vtuber.vseeface_select_exe",
                    "params": [
                        {
                            "name": "path",
                            "label": "VSeeFace.exe",
                            "kind": "file",
                            "required": True,
                            "must_exist": True,
                            "file_filter": "VSeeFace.exe (VSeeFace.exe);;Windows executable (*.exe)",
                        }
                    ],
                },
            )
        ]
    elif action == ACTION_SELECT_VRM0_AVATAR:
        base["steps"] = [
            _ui_step(
                "select_vrm0_avatar",
                "file_picker",
                "Select a VSeeFace-compatible VRM0 avatar.",
                registry_action="vtuber.vseeface_select_vrm0_avatar",
                form={
                    "submit_action": "vtuber.vseeface_select_vrm0_avatar",
                    "params": [
                        {
                            "name": "path",
                            "label": "VRM0 avatar",
                            "kind": "file",
                            "required": True,
                            "must_exist": True,
                            "file_filter": "VRM avatar (*.vrm)",
                        }
                    ],
                },
            )
        ]
    elif action == ACTION_SELECT_TRACKING_INPUT:
        base["steps"] = [
            _ui_step(
                "select_tracking_input_source",
                "camera_or_project_clip_picker",
                "Choose a real camera, a media-pool video, or a timeline clip as the OpenSeeFace tracking input.",
                registry_action="vtuber.vseeface_select_input_source",
                form={
                    "submit_action": "vtuber.vseeface_select_input_source",
                    "params": [
                        {
                            "name": "source_id",
                            "label": "Tracking input",
                            "kind": "input_source_id",
                            "required": True,
                            "source": "status.input_sources.options",
                        }
                    ],
                },
            )
        ]
    elif action == ACTION_SELECT_CAPTURE_BACKEND:
        base["steps"] = [
            _ui_step(
                "select_capture_backend",
                "capture_backend_picker",
                "Choose the VSeeFace capture backend.",
                registry_action="vtuber.vseeface_select_capture_backend",
                form={
                    "submit_action": "vtuber.vseeface_select_capture_backend",
                    "params": [
                        {
                            "name": "method",
                            "label": "Capture backend",
                            "kind": "enum",
                            "required": True,
                            "options": [
                                {"value": CAPTURE_WINDOW, "label": "Window capture"},
                                {"value": CAPTURE_VIRTUAL_CAMERA, "label": "Virtual camera (optional)"},
                                {"value": CAPTURE_SPOUT2, "label": "Spout2"},
                                {"value": CAPTURE_NONE, "label": "None"},
                            ],
                        },
                        {"name": "window_title_hint", "label": "Window title", "kind": "text", "required": False},
                        {"name": "virtual_camera_name", "label": "Virtual camera", "kind": "text", "required": False},
                        {"name": "spout_sender_name", "label": "Spout sender", "kind": "text", "required": False},
                    ],
                },
            )
        ]
    elif action == ACTION_SELECT_BROADCAST_FRAMING:
        base["steps"] = [
            _ui_step(
                "select_broadcast_framing",
                "framing_picker",
                "Choose the intended VTuber broadcast framing.",
                registry_action="vtuber.vseeface_select_framing",
                form={
                    "submit_action": "vtuber.vseeface_select_framing",
                    "params": [
                        {
                            "name": "framing_preset",
                            "label": "Broadcast framing",
                            "kind": "enum",
                            "required": True,
                            "options": [
                                {"value": FRAMING_BUST_UP, "label": "Bust-up"},
                                {"value": FRAMING_HALF_BODY, "label": "Half body"},
                                {"value": FRAMING_FULL_BODY, "label": "Full body"},
                            ],
                        }
                    ],
                },
            )
        ]
    elif action == ACTION_USE_CAPTURE_SOURCE:
        base["steps"] = [_ui_step("enable_vseeface_source", "scene_update", "Use the VSeeFace source in the broadcast scene.")]
    elif action == ACTION_USE_INTERNAL_VRM_FALLBACK:
        base["steps"] = [
            _ui_step(
                "enable_internal_vrm_fallback",
                "scene_update",
                "Use the internal VRM renderer for Program Output while keeping VSeeFace as an optional external bridge.",
            )
        ]
    elif action == ACTION_KEEP_FALLBACK_SOURCE:
        base["steps"] = [_ui_step("keep_fallback_source", "scene_update", "Keep fallback handling enabled for the VSeeFace source.")]
    else:
        base["steps"] = [_manual_step("inspect_bridge_status", "Inspect VSeeFace bridge status before taking action.")]
    return base


def build_vseeface_broadcast_source(
    config: VSeeFaceBridgeConfig | Mapping[str, Any],
    *,
    z_index: int = 10,
    capture_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config if isinstance(config, VSeeFaceBridgeConfig) else VSeeFaceBridgeConfig.from_mapping(config)
    capture = cfg.capture
    camera = standard_vtuber_camera_settings(capture.framing_preset)
    capture_health = summarize_vseeface_capture_status(capture_diagnostics, method=capture.method)
    return {
        "id": capture.source_id,
        "type": SOURCE_VSEEFACE,
        "name": "VSeeFace Avatar",
        "z_index": int(z_index),
        "transform": {
            "x": 0.0,
            "y": 0.0,
            "width": float(capture.width),
            "height": float(capture.height),
            "fit": FIT_CONTAIN,
            "opacity": 1.0,
            "visible": True,
        },
        "chroma_key": dict(capture.chroma_key),
        "settings": {
            "bridge_schema": BRIDGE_SCHEMA,
            "integration_mode": INTEGRATION_MODE,
            "capture_method": capture_health["method"],
            "window_title_hint": capture.window_title_hint,
            "virtual_camera_name": capture.virtual_camera_name,
            "spout_sender_name": capture.spout_sender_name,
            "framing_preset": capture.framing_preset,
            "camera": camera,
            "vseeface_exe": cfg.vseeface_exe,
            "avatar_vrm": cfg.avatar_vrm,
            "tracking": cfg.tracking.to_dict(),
            "input": cfg.input_source.to_dict(),
            "capture_ready": capture_health["ready"],
            "capture_status": capture_health["status"],
            "capture_health": capture_health,
            "fallback_behavior": CAPTURE_FALLBACK_SUPPRESS_BLACK_FRAME,
            "fallback_mode": str((capture_health.get("fallback") if isinstance(capture_health.get("fallback"), Mapping) else {}).get("mode") or "none"),
            "fallback_source_id": str((capture_health.get("fallback") if isinstance(capture_health.get("fallback"), Mapping) else {}).get("source_id") or ""),
            SETTING_SUPPRESS_BLACK_FRAME: True,
        },
    }


def _build_internal_vrm_fallback_source(
    cfg: VSeeFaceBridgeConfig,
    *,
    width: int,
    height: int,
    z_index: int,
    capture_health: Mapping[str, Any],
) -> dict[str, Any]:
    capture = cfg.capture
    fallback = capture_health.get("fallback") if isinstance(capture_health.get("fallback"), Mapping) else {}
    camera = standard_vtuber_camera_settings(capture.framing_preset)
    try:
        from app.vtuber.internal_vrm_fallback import internal_vrm_fallback_quality_policy
        from app.vtuber.vrm_renderer import VRM_RENDERER_SOFTWARE

        quality = internal_vrm_fallback_quality_policy(
            width=max(1, int(width)),
            height=max(1, int(height)),
            renderer=VRM_RENDERER_SOFTWARE,
            settings={"fps": capture.fps},
        )
    except Exception:
        quality = {"broadcast_ready": False, "warnings": ["internal_vrm_fallback_quality_unavailable"]}
    return {
        "id": str(fallback.get("source_id") or INTERNAL_VRM_FALLBACK_SOURCE_ID),
        "type": SOURCE_INTERNAL_VRM,
        "name": "Internal VRM Fallback",
        "z_index": int(z_index),
        "transform": {
            "x": 0.0,
            "y": 0.0,
            "width": float(max(1, int(width))),
            "height": float(max(1, int(height))),
            "fit": FIT_CONTAIN,
            "opacity": 1.0,
            "visible": True,
        },
        "chroma_key": {"enabled": False},
        "settings": {
            "schema": BRIDGE_SCHEMA,
            "source_role": "fallback_avatar_renderer",
            "fallback_for": capture.source_id,
            "fallback_mode": CAPTURE_FALLBACK_INTERNAL_VRM,
            "fallback_reason": str(capture_health.get("status") or ""),
            "program_output": True,
            "requires_vseeface_capture": False,
            "avatar_vrm": cfg.avatar_vrm,
            "input": cfg.input_source.to_dict(),
            "framing_preset": capture.framing_preset,
            "camera": camera,
            "renderer": {
                "type": "internal_vrm",
                "family": "vtuber_vrm",
                "renderer": "vrm_mtoon_software",
                "render_profile": "vrm_mtoon",
                "pbr_renderer": False,
                "ar_pbr_preview": False,
                "pose_driver": "openseeface_or_video_face_driver",
                "virtual_camera_required": False,
                "quality": quality,
            },
        },
    }


def _should_add_internal_vrm_fallback(capture_health: Mapping[str, Any]) -> bool:
    fallback = capture_health.get("fallback") if isinstance(capture_health.get("fallback"), Mapping) else {}
    return capture_health.get("ready") is False and str(fallback.get("mode") or "") == CAPTURE_FALLBACK_INTERNAL_VRM


def build_vseeface_broadcast_scene(
    config: VSeeFaceBridgeConfig | Mapping[str, Any],
    *,
    width: int = 1920,
    height: int = 1080,
    fps: float = 30.0,
    background: tuple[int, int, int, int] = (0, 0, 0, 255),
    capture_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = build_vseeface_broadcast_source(
        config,
        z_index=10,
        capture_diagnostics=capture_diagnostics,
    )
    source["transform"]["width"] = float(max(1, int(width)))
    source["transform"]["height"] = float(max(1, int(height)))
    source_settings = source.get("settings") if isinstance(source.get("settings"), Mapping) else {}
    capture_health = source_settings.get("capture_health") if isinstance(source_settings.get("capture_health"), Mapping) else {}
    sources = [
        {
            "id": "background",
            "type": SOURCE_COLOR,
            "name": "Background",
            "z_index": 0,
            "settings": {"color": list(_normalize_rgba(background))},
        },
        source,
    ]
    if _should_add_internal_vrm_fallback(capture_health):
        sources.append(_build_internal_vrm_fallback_source(
            config if isinstance(config, VSeeFaceBridgeConfig) else VSeeFaceBridgeConfig.from_mapping(config),
            width=width,
            height=height,
            z_index=9,
            capture_health=capture_health,
        ))
    return {
        "id": "vseeface_bridge_scene",
        "name": "VSeeFace Bridge",
        "canvas": {
            "width": max(1, int(width)),
            "height": max(1, int(height)),
            "fps": max(1.0, float(fps)),
            "background": list(_normalize_rgba(background)),
        },
        "sources": sources,
        "audio": [
            {"id": "mic", "name": "Mic/Aux", "source_id": "", "volume": 1.0, "muted": False, "monitor": False},
            {"id": "desktop", "name": "Desktop Audio", "source_id": "", "volume": 1.0, "muted": False, "monitor": False},
        ],
    }


def _normalize_framing_preset(value: Any) -> str:
    text = str(value or FRAMING_BUST_UP).strip().casefold().replace("-", "_")
    aliases = {
        "bust": FRAMING_BUST_UP,
        "bustup": FRAMING_BUST_UP,
        "close": FRAMING_BUST_UP,
        "close_up": FRAMING_BUST_UP,
        "upper_body": FRAMING_HALF_BODY,
        "waist": FRAMING_HALF_BODY,
        "waist_up": FRAMING_HALF_BODY,
        "full": FRAMING_FULL_BODY,
        "fullbody": FRAMING_FULL_BODY,
    }
    text = aliases.get(text, text)
    return text if text in SUPPORTED_FRAMING_PRESETS else FRAMING_BUST_UP


def _normalize_crop(value: Any) -> tuple[float, float, float, float] | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str):
            return parse_crop(value)
        if isinstance(value, (list, tuple)) and len(value) == 4:
            return parse_crop(",".join(str(item) for item in value))
    except (TypeError, ValueError):
        return None
    return None


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _nonnegative_int(value: Any, default: int = 0) -> int:
    parsed = _optional_int(value)
    return max(0, int(default if parsed is None else parsed))


def _normalize_input_source_kind(value: Any, *, mode: str, data: Mapping[str, Any]) -> str:
    text = str(value or "").strip().casefold().replace("-", "_")
    aliases = {
        "camera": INPUT_KIND_CAMERA_DEVICE,
        "webcam": INPUT_KIND_CAMERA_DEVICE,
        "web_camera": INPUT_KIND_CAMERA_DEVICE,
        "device": INPUT_KIND_CAMERA_DEVICE,
        "file": INPUT_KIND_VIDEO_FILE,
        "video": INPUT_KIND_VIDEO_FILE,
        "video_file": INPUT_KIND_VIDEO_FILE,
        "media_pool": INPUT_KIND_MEDIA_POOL_VIDEO,
        "media_pool_clip": INPUT_KIND_MEDIA_POOL_VIDEO,
        "media_pool_video": INPUT_KIND_MEDIA_POOL_VIDEO,
        "timeline": INPUT_KIND_TIMELINE_VIDEO_CLIP,
        "track": INPUT_KIND_TIMELINE_VIDEO_CLIP,
        "timeline_clip": INPUT_KIND_TIMELINE_VIDEO_CLIP,
        "timeline_video_clip": INPUT_KIND_TIMELINE_VIDEO_CLIP,
    }
    text = aliases.get(text, text)
    if text in SUPPORTED_INPUT_SOURCE_KINDS:
        return text
    if _optional_int(data.get("track_id")) is not None and _optional_int(data.get("clip_id")) is not None:
        return INPUT_KIND_TIMELINE_VIDEO_CLIP
    if data.get("media_pool_id"):
        return INPUT_KIND_MEDIA_POOL_VIDEO
    if mode == INPUT_OPENSEEFACE_VIDEO or data.get("video_path") or data.get("video"):
        return INPUT_KIND_VIDEO_FILE
    return INPUT_KIND_CAMERA_DEVICE


def _default_input_source_id(source_kind: str, data: Mapping[str, Any]) -> str:
    if source_kind == INPUT_KIND_TIMELINE_VIDEO_CLIP:
        track_id = _optional_int(data.get("track_id"))
        clip_id = _optional_int(data.get("clip_id"))
        if track_id is not None and clip_id is not None:
            return f"timeline:{track_id}:{clip_id}"
    if source_kind == INPUT_KIND_MEDIA_POOL_VIDEO and data.get("media_pool_id"):
        return f"media_pool:{data.get('media_pool_id')}"
    if source_kind == INPUT_KIND_VIDEO_FILE:
        video_path = str(data.get("video_path") or data.get("video") or "")
        return f"video_file:{video_path}" if video_path else "video_file:"
    camera_id = str(data.get("camera_device_id") or data.get("device_id") or "").strip()
    return f"camera:{camera_id}" if camera_id else "camera:default"


def _collect_string_items(payload: Mapping[str, Any], key: str) -> list[str]:
    values = payload.get(key)
    if not isinstance(values, (list, tuple, set)):
        return []
    return [str(item) for item in values]


def _collect_nested_errors(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("virtual_camera", "window_capture", "capture", "preflight"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            errors.extend(_collect_string_items(value, "errors"))
    return errors


def _infer_capture_method_from_diagnostics(diagnostics: Mapping[str, Any], fallback: str) -> str:
    status = str(diagnostics.get("status") or "").casefold()
    schema = str(diagnostics.get("schema") or "").casefold()
    if "virtual_camera" in status or "vseeface_post_install" in schema:
        return CAPTURE_VIRTUAL_CAMERA
    if isinstance(diagnostics.get("virtual_camera"), Mapping):
        return CAPTURE_VIRTUAL_CAMERA
    if isinstance(diagnostics.get("ffmpeg_camera"), Mapping):
        return CAPTURE_VIRTUAL_CAMERA
    if "window_capture" in status:
        return CAPTURE_WINDOW
    return fallback


def _virtual_camera_requires_registration(diagnostics: Mapping[str, Any]) -> bool:
    preflight = diagnostics.get("preflight") if isinstance(diagnostics.get("preflight"), Mapping) else {}
    virtual_camera = preflight.get("virtual_camera") if isinstance(preflight.get("virtual_camera"), Mapping) else {}
    return bool(virtual_camera.get("requires_admin_registration"))


def _resolve_bridge_state(
    preflight: Mapping[str, Any],
    capture_health: Mapping[str, Any],
    scene_diag: Mapping[str, Any],
) -> str:
    if not bool(preflight.get("ok")):
        return BRIDGE_STATE_BLOCKED
    if capture_health.get("ready") is True:
        return BRIDGE_STATE_READY
    if scene_diag.get("degraded_frame_sources"):
        return BRIDGE_STATE_DEGRADED
    return BRIDGE_STATE_NEEDS_PROBE


def _vseeface_bridge_state_ui(
    state: str,
    capture_health: Mapping[str, Any],
    preflight: Mapping[str, Any],
) -> dict[str, str]:
    if state == BRIDGE_STATE_READY:
        return {"label": "Ready", "severity": "ok", "action": "use_capture_source"}
    if state == BRIDGE_STATE_DEGRADED:
        ui = capture_health.get("ui") if isinstance(capture_health.get("ui"), Mapping) else {}
        return {
            "label": str(ui.get("label") or "Degraded"),
            "severity": str(ui.get("severity") or "warning"),
            "action": str(ui.get("action") or "inspect_capture_source"),
        }
    if state == BRIDGE_STATE_BLOCKED:
        errors = [str(item) for item in preflight.get("errors") or []]
        action = "configure_vseeface_exe_and_vrm0"
        if "vseeface_exe_missing" in errors:
            action = "select_vseeface_exe"
        elif "vseeface_requires_vrm0" in errors or "file_missing" in errors:
            action = "select_vrm0_avatar"
        return {"label": "Setup required", "severity": "blocked", "action": action}
    return {"label": "Run capture probe", "severity": "info", "action": "run_capture_probe"}


def _bridge_action(
    action_id: str,
    label: str,
    description: str,
    *,
    kind: str = "ui",
    primary: bool = False,
    blocking: bool = False,
    input_source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "description": description,
        "kind": kind,
        "primary": bool(primary),
        "blocking": bool(blocking),
        "auto_run": False,
        "plan": _build_vseeface_bridge_action_plan(action_id, input_source=input_source),
    }


def _tracking_input_action() -> dict[str, Any]:
    return _bridge_action(
        ACTION_SELECT_TRACKING_INPUT,
        "Select tracking input",
        "Choose a real camera, a media-pool video, or a timeline clip for face tracking.",
        kind="ui",
    )


def _internal_vrm_fallback_action(*, primary: bool, input_source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return _bridge_action(
        ACTION_USE_INTERNAL_VRM_FALLBACK,
        "Use internal VRM fallback",
        "Route Program Output through TigerCapture's internal VRM renderer while VSeeFace capture is unhealthy.",
        kind="fallback",
        primary=primary,
        input_source=input_source,
    )


def _capture_backend_action() -> dict[str, Any]:
    return _bridge_action(
        ACTION_SELECT_CAPTURE_BACKEND,
        "Select capture backend",
        "Choose how TigerCapture should receive VSeeFace output.",
        kind="ui",
    )


def _broadcast_framing_action() -> dict[str, Any]:
    return _bridge_action(
        ACTION_SELECT_BROADCAST_FRAMING,
        "Select framing",
        "Choose the intended VTuber broadcast framing.",
        kind="ui",
    )


def build_vseeface_sidecar_settings_action(
    config: VSeeFaceBridgeConfig | Mapping[str, Any],
    *,
    sidecar_settings: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return the UI action for reviewing and applying sidecar settings."""
    settings = sidecar_settings if isinstance(sidecar_settings, Mapping) else build_vseeface_sidecar_settings_preview(config)
    if not bool(settings.get("ok", False)):
        return None
    plan = build_vseeface_sidecar_apply_plan(config, settings_path=str(settings.get("settings_path") or "") or None)
    if not bool(plan.get("ok", False)):
        return None
    review_step = _ui_step(
        "review_sidecar_settings",
        "sidecar_settings_preview",
        "Review the VSeeFace sidecar settings before applying them.",
        registry_action="vtuber.vseeface_sidecar_apply_plan",
        form={
            "submit_action": "vtuber.vseeface_sidecar_apply_plan",
            "params": [
                {
                    "name": "settings_path",
                    "label": "VSeeFace settings.ini",
                    "kind": "file",
                    "required": False,
                    "must_exist": False,
                    "file_filter": "VSeeFace settings (settings.ini);;INI files (*.ini)",
                },
                {
                    "name": "out_path",
                    "label": "Report JSON",
                    "kind": "save_file",
                    "required": False,
                    "file_filter": "JSON report (*.json)",
                },
            ],
        },
    )
    action_plan = dict(plan)
    action_plan["steps"] = [review_step] + [dict(step) for step in plan.get("steps", []) if isinstance(step, Mapping)]
    return {
        "id": ACTION_APPLY_SIDECAR_SETTINGS,
        "label": "Apply sidecar settings",
        "description": "Review the external VSeeFace settings.ini update plan before writing it.",
        "kind": "tool",
        "primary": False,
        "blocking": False,
        "auto_run": False,
        "plan": action_plan,
    }


def _setup_flow_step(
    step_id: str,
    title: str,
    text: str,
    state: str,
    action: Mapping[str, Any] | None,
    *,
    blocking: bool = False,
) -> dict[str, Any]:
    action_view = _action_to_view(action)
    return {
        "id": step_id,
        "title": title,
        "text": text,
        "state": state if state in {"done", "current", "pending", "blocked", "warning"} else "pending",
        "blocking": bool(blocking),
        "action": action_view,
        "requires_admin": bool((action_view or {}).get("requires_admin", False)),
    }


def _install_setup_step_text(install: Mapping[str, Any]) -> str:
    state = str(install.get("state") or "")
    if state == "installed":
        return "VSeeFace sidecar executable is configured."
    if state == "installed_default":
        return "VSeeFace is installed in the default sidecar folder; select it to connect."
    if state == "zip_available":
        return "A local VSeeFace zip is available; run the install action to extract it."
    return "Install or select VSeeFace before connecting the bridge."


def _install_setup_step_state(install: Mapping[str, Any]) -> str:
    state = str(install.get("state") or "")
    if state in {"installed", "installed_default"}:
        return "done"
    if state in {"missing", "zip_available"}:
        return "current"
    return "blocked"


def _install_setup_is_blocking(install: Mapping[str, Any]) -> bool:
    return str(install.get("state") or "") in {"missing", "zip_available"}


def _vseeface_exe_setup_step_state(preflight: Mapping[str, Any], install: Mapping[str, Any]) -> str:
    if bool(preflight.get("exe_exists")):
        return "done"
    if str(install.get("state") or "") == "installed_default":
        return "current"
    return "pending" if _install_setup_is_blocking(install) else "current"


def _vrm_setup_step_state(preflight: Mapping[str, Any]) -> str:
    vrm = preflight.get("vrm") if isinstance(preflight.get("vrm"), Mapping) else {}
    if bool(vrm.get("vseeface_compatible")):
        return "done"
    errors = [str(item) for item in preflight.get("errors") or []]
    if "vseeface_requires_vrm0" in errors or "file_missing" in errors:
        return "current"
    return "pending" if not bool(preflight.get("exe_exists")) else "current"


def _tracking_input_step_text(input_sources: Mapping[str, Any]) -> str:
    selected = input_sources.get("selected") if isinstance(input_sources.get("selected"), Mapping) else {}
    label = str(selected.get("label") or "Default camera")
    kind = str(selected.get("kind") or INPUT_KIND_CAMERA_DEVICE)
    if kind == INPUT_KIND_CAMERA_DEVICE:
        return f"Tracking input is a camera: {label}."
    if kind == INPUT_KIND_MEDIA_POOL_VIDEO:
        return f"Tracking input is a Media Pool video: {label}."
    if kind == INPUT_KIND_TIMELINE_VIDEO_CLIP:
        return f"Tracking input is a timeline clip: {label}."
    return f"Tracking input is a video file: {label}."


def _capture_setup_step_text(capture: Mapping[str, Any]) -> str:
    ui = capture.get("ui") if isinstance(capture.get("ui"), Mapping) else {}
    label = str(ui.get("label") or capture.get("status") or "Not probed")
    if capture.get("ready") is True:
        return "Capture backend is ready."
    if capture.get("status") == CAPTURE_STATUS_BLOCKED_REGISTRATION:
        return "VSeeFaceCamera registration is required."
    if capture.get("status") == CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK:
        return "Capture is black; confirm VSeeFace is rendering a visible avatar."
    if capture.get("status") == CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED:
        return "Virtual camera capture failed; confirm VSeeFace output is enabled."
    return f"Capture backend needs verification: {label}."


def _capture_setup_step_state(state: str, capture: Mapping[str, Any], preflight: Mapping[str, Any]) -> str:
    if not bool(preflight.get("ok")):
        return "pending"
    if capture.get("ready") is True:
        return "done"
    if capture.get("ready") is False:
        return "blocked" if capture.get("status") == CAPTURE_STATUS_BLOCKED_REGISTRATION else "current"
    return "current" if state == BRIDGE_STATE_NEEDS_PROBE else "pending"


def _capture_setup_action(action_by_id: Mapping[str, Mapping[str, Any]], capture: Mapping[str, Any], state: str) -> Mapping[str, Any] | None:
    status = str(capture.get("status") or "")
    if status == CAPTURE_STATUS_BLOCKED_REGISTRATION:
        return action_by_id.get(ACTION_REGISTER_VSEEFACE_CAMERA)
    if status == CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED:
        return action_by_id.get(ACTION_CONFIRM_VIRTUAL_CAMERA)
    if status == CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK:
        return action_by_id.get(ACTION_FIX_RENDERING_OR_START_SCENE)
    if state == BRIDGE_STATE_NEEDS_PROBE:
        return action_by_id.get(ACTION_RUN_CAPTURE_PROBE)
    return action_by_id.get(ACTION_RUN_CAPTURE_PROBE)


def _capture_setup_is_blocking(capture: Mapping[str, Any]) -> bool:
    return str(capture.get("status") or "") == CAPTURE_STATUS_BLOCKED_REGISTRATION


def _broadcast_setup_step_text(state: str, scene_diag: Mapping[str, Any]) -> str:
    if state == BRIDGE_STATE_READY:
        return "VSeeFace is ready to use as a broadcast scene source."
    if scene_diag.get("degraded_frame_sources"):
        return "Scene uses the internal VRM fallback while VSeeFace capture is degraded."
    return "Broadcast scene waits for setup and capture verification."


def _broadcast_setup_step_state(state: str, scene_diag: Mapping[str, Any]) -> str:
    if state == BRIDGE_STATE_READY:
        return "done"
    if scene_diag.get("degraded_frame_sources"):
        return "warning"
    return "pending"


def _setup_flow_to_view(flow: Mapping[str, Any]) -> dict[str, Any]:
    steps = flow.get("steps") if isinstance(flow.get("steps"), list) else []
    current_step_id = str(flow.get("current_step_id") or "")
    current = next((step for step in steps if isinstance(step, Mapping) and str(step.get("id") or "") == current_step_id), None)
    return {
        "schema": BRIDGE_SETUP_FLOW_SCHEMA,
        "ready": bool(flow.get("ready", False)),
        "current_step_id": current_step_id,
        "current_title": str((current or {}).get("title") or ""),
        "current_text": str((current or {}).get("text") or ""),
        "progress": float(flow.get("progress", 0.0) or 0.0),
        "requires_admin": bool(flow.get("requires_admin", False)),
        "steps": [
            {
                "id": str(step.get("id") or ""),
                "title": str(step.get("title") or ""),
                "state": str(step.get("state") or "pending"),
                "action": step.get("action") if isinstance(step.get("action"), Mapping) else None,
            }
            for step in steps
            if isinstance(step, Mapping)
        ],
    }


def _bridge_config_with_resolved_input(cfg: VSeeFaceBridgeConfig, input_sources: Mapping[str, Any]) -> VSeeFaceBridgeConfig:
    selected = input_sources.get("selected") if isinstance(input_sources.get("selected"), Mapping) else {}
    input_payload = selected.get("input") if isinstance(selected.get("input"), Mapping) else None
    if not isinstance(input_payload, Mapping):
        return cfg
    return VSeeFaceBridgeConfig(
        vseeface_exe=cfg.vseeface_exe,
        avatar_vrm=cfg.avatar_vrm,
        auto_launch=cfg.auto_launch,
        arguments=list(cfg.arguments),
        capture=cfg.capture,
        tracking=cfg.tracking,
        input_source=VSeeFaceInputConfig.from_mapping(input_payload),
    )


def _camera_input_options(
    camera_devices: list[Mapping[str, Any]],
    selected: VSeeFaceInputConfig,
    input_diagnostics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = camera_devices or [{"id": "default", "name": selected.camera_device_name or "Default camera"}]
    options: list[dict[str, Any]] = []
    for idx, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            continue
        device_id = str(raw.get("id") or raw.get("device_id") or raw.get("name") or f"device_{idx}").strip() or f"device_{idx}"
        index = _optional_int(raw.get("index", raw.get("camera_index", raw.get("device_index"))))
        name = str(raw.get("name") or raw.get("label") or raw.get("device_name") or ("Default camera" if idx == 0 else f"Camera {idx + 1}"))
        option_id = f"camera:{device_id}"
        if device_id == "default":
            option_id = "camera:default"
        health = _camera_input_health(raw, option_id, input_diagnostics)
        input_payload = _input_payload_for_choice(
            selected,
            mode=INPUT_WEBCAM,
            source_kind=INPUT_KIND_CAMERA_DEVICE,
            source_id=option_id,
            camera_device_id="" if device_id == "default" else device_id,
            camera_device_name=name,
            camera_index=index,
            video_path="",
            media_pool_id="",
            track_id=None,
            clip_id=None,
            source_in_ms=0,
            source_out_ms=0,
            timeline_in_ms=0,
            timeline_out_ms=0,
        )
        options.append(
            {
                "id": option_id,
                "kind": INPUT_KIND_CAMERA_DEVICE,
                "mode": INPUT_WEBCAM,
                "label": name,
                "description": "Use a live camera as the OpenSeeFace tracking input.",
                "source_ref": {
                    "camera_device_id": "" if device_id == "default" else device_id,
                    "camera_index": index,
                },
                "status": health["status"],
                "tone": health["tone"],
                "actions": health["actions"],
                "diagnostics": health["diagnostics"],
                "input": input_payload,
            }
        )
    return options


def _media_pool_input_options(
    project_snapshot: Mapping[str, Any],
    selected: VSeeFaceInputConfig,
    input_diagnostics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for idx, item in enumerate(project_snapshot.get("media_pool") or []):
        if not isinstance(item, Mapping):
            continue
        path = str(item.get("path") or item.get("source_path") or "")
        if not _is_video_input_path(path) and str(item.get("kind") or "").casefold() != "video":
            continue
        media_id = str(item.get("id") or f"media_{idx + 1}")
        name = str(item.get("name") or Path(path).name or media_id)
        option_id = f"media_pool:{media_id}"
        health = _video_input_health(item, option_id, input_diagnostics, path=path)
        input_payload = _input_payload_for_choice(
            selected,
            mode=INPUT_OPENSEEFACE_VIDEO,
            source_kind=INPUT_KIND_MEDIA_POOL_VIDEO,
            source_id=option_id,
            video_path=path,
            media_pool_id=media_id,
            track_id=None,
            clip_id=None,
            source_in_ms=0,
            source_out_ms=0,
            timeline_in_ms=0,
            timeline_out_ms=0,
        )
        options.append(
            {
                "id": option_id,
                "kind": INPUT_KIND_MEDIA_POOL_VIDEO,
                "mode": INPUT_OPENSEEFACE_VIDEO,
                "label": name,
                "description": "Feed this media-pool video to OpenSeeFace for tracking.",
                "video_path": path,
                "source_ref": {"media_pool_id": media_id, "path": path},
                "status": health["status"],
                "tone": health["tone"],
                "actions": health["actions"],
                "diagnostics": health["diagnostics"],
                "input": input_payload,
            }
        )
    return options


def _timeline_clip_input_options(
    project_snapshot: Mapping[str, Any],
    selected: VSeeFaceInputConfig,
    input_diagnostics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for track_index, track in enumerate(project_snapshot.get("video_tracks") or []):
        if not isinstance(track, Mapping):
            continue
        track_id = _optional_int(track.get("id"))
        if track_id is None:
            continue
        for clip_index, clip in enumerate(track.get("clips") or []):
            if not isinstance(clip, Mapping):
                continue
            path = str(clip.get("source_path") or clip.get("path") or "")
            if not _is_video_input_path(path):
                continue
            clip_id = _optional_int(clip.get("id"))
            if clip_id is None:
                continue
            option_id = f"timeline:{track_id}:{clip_id}"
            name = str(clip.get("name") or Path(path).name or f"Clip {clip_id}")
            label = f"V{track_index + 1} Clip {clip_index + 1} - {name}"
            health = _video_input_health(clip, option_id, input_diagnostics, path=path)
            input_payload = _input_payload_for_choice(
                selected,
                mode=INPUT_OPENSEEFACE_VIDEO,
                source_kind=INPUT_KIND_TIMELINE_VIDEO_CLIP,
                source_id=option_id,
                video_path=path,
                media_pool_id="",
                track_id=track_id,
                clip_id=clip_id,
                source_in_ms=_nonnegative_int(clip.get("source_in_ms")),
                source_out_ms=_nonnegative_int(clip.get("source_out_ms")),
                timeline_in_ms=_nonnegative_int(clip.get("timeline_in_ms")),
                timeline_out_ms=_nonnegative_int(clip.get("timeline_out_ms")),
            )
            options.append(
                {
                    "id": option_id,
                    "kind": INPUT_KIND_TIMELINE_VIDEO_CLIP,
                    "mode": INPUT_OPENSEEFACE_VIDEO,
                    "label": label,
                    "description": "Feed this timeline clip to OpenSeeFace for tracking.",
                    "video_path": path,
                    "source_ref": {
                        "track_id": track_id,
                        "clip_id": clip_id,
                        "path": path,
                        "source_in_ms": input_payload["source_in_ms"],
                        "source_out_ms": input_payload["source_out_ms"],
                        "timeline_in_ms": input_payload["timeline_in_ms"],
                        "timeline_out_ms": input_payload["timeline_out_ms"],
                    },
                    "status": health["status"],
                    "tone": health["tone"],
                    "actions": health["actions"],
                    "diagnostics": health["diagnostics"],
                    "input": input_payload,
                }
            )
    return options


def _camera_input_health(
    raw: Mapping[str, Any],
    option_id: str,
    input_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    diag = _diagnostics_for_input(option_id, raw, input_diagnostics)
    raw_status = str(diag.get("status") or raw.get("status") or "").strip().casefold()
    errors = _collect_diagnostic_strings(diag, raw, "errors")
    warnings = _collect_diagnostic_strings(diag, raw, "warnings")
    recommendations = _collect_diagnostic_strings(diag, raw, "recommendations")
    if (
        bool(diag.get("black_frame") or raw.get("black_frame"))
        or "black" in raw_status
        or any("black" in item.casefold() for item in errors + warnings)
    ):
        status = INPUT_STATUS_BLACK_FRAME
    elif (
        bool(diag.get("available") is False or raw.get("available") is False)
        or bool(diag.get("connected") is False or raw.get("connected") is False)
        or raw_status in {"unavailable", "missing", "disconnected", "error", "failed"}
        or any(item.casefold() in {"unavailable", "disconnected", "camera_unavailable"} for item in errors)
    ):
        status = INPUT_STATUS_UNAVAILABLE
    elif (
        bool(diag.get("ready") is True or raw.get("ready") is True)
        or bool(diag.get("available") is True or raw.get("available") is True)
        or bool(diag.get("connected") is True or raw.get("connected") is True)
        or raw_status in {"ready", "ok", "connected", "available"}
    ):
        status = INPUT_STATUS_READY
    else:
        status = INPUT_STATUS_NOT_PROBED
    return _input_health_payload(
        status,
        kind=INPUT_KIND_CAMERA_DEVICE,
        errors=errors,
        warnings=warnings,
        recommendations=recommendations,
    )


def _video_input_health(
    raw: Mapping[str, Any],
    option_id: str,
    input_diagnostics: Mapping[str, Any],
    *,
    path: str,
) -> dict[str, Any]:
    diag = _diagnostics_for_input(option_id, raw, input_diagnostics)
    raw_status = str(diag.get("status") or raw.get("status") or "").strip().casefold()
    errors = _collect_diagnostic_strings(diag, raw, "errors")
    warnings = _collect_diagnostic_strings(diag, raw, "warnings")
    recommendations = _collect_diagnostic_strings(diag, raw, "recommendations")
    missing = (
        not str(path or "").strip()
        or bool(diag.get("missing") or raw.get("missing"))
        or bool(diag.get("exists") is False or raw.get("exists") is False)
        or raw_status in {"missing", "file_missing", "not_found"}
        or any(item.casefold() in {"missing", "file_missing", "not_found"} for item in errors)
    )
    if missing:
        status = INPUT_STATUS_MISSING
    elif (
        bool(diag.get("black_frame") or raw.get("black_frame"))
        or "black" in raw_status
        or any("black" in item.casefold() for item in errors + warnings)
    ):
        status = INPUT_STATUS_BLACK_FRAME
    else:
        status = INPUT_STATUS_READY
    return _input_health_payload(
        status,
        kind=str(raw.get("source_kind") or raw.get("kind") or INPUT_KIND_VIDEO_FILE),
        errors=errors,
        warnings=warnings,
        recommendations=recommendations,
    )


def _diagnostics_for_input(
    option_id: str,
    raw: Mapping[str, Any],
    input_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    rows = input_diagnostics.get("inputs") if isinstance(input_diagnostics.get("inputs"), Mapping) else {}
    candidates = [
        option_id,
        str(raw.get("id") or ""),
        str(raw.get("device_id") or ""),
        str(raw.get("camera_device_id") or ""),
        str(raw.get("path") or raw.get("source_path") or ""),
    ]
    for key in candidates:
        if key and isinstance(rows.get(key), Mapping):
            return dict(rows[key])
    selected = input_diagnostics.get("selected") if isinstance(input_diagnostics.get("selected"), Mapping) else None
    if selected and str(selected.get("id") or "") == option_id:
        return dict(selected)
    return {}


def _input_health_payload(
    status: str,
    *,
    kind: str,
    errors: list[str],
    warnings: list[str],
    recommendations: list[str],
) -> dict[str, Any]:
    normalized = _normalize_input_status(status)
    tone = _input_tone_for_status(normalized)
    return {
        "status": normalized,
        "tone": tone,
        "actions": _input_actions_for_status(normalized, kind),
        "diagnostics": {
            "status": normalized,
            "ready": normalized == INPUT_STATUS_READY,
            "errors": errors,
            "warnings": warnings,
            "recommendations": recommendations,
        },
    }


def _normalize_input_status(status: str) -> str:
    key = str(status or "").strip().casefold().replace("-", "_")
    if key in {"ready", "ok", "connected", "available"}:
        return INPUT_STATUS_READY
    if key in {"black", "black_frame", "all_black"}:
        return INPUT_STATUS_BLACK_FRAME
    if key in {"missing", "file_missing", "not_found"}:
        return INPUT_STATUS_MISSING
    if key in {"unavailable", "disconnected", "failed", "error"}:
        return INPUT_STATUS_UNAVAILABLE
    return INPUT_STATUS_NOT_PROBED


def _input_tone_for_status(status: str) -> str:
    if status == INPUT_STATUS_READY:
        return "ok"
    if status == INPUT_STATUS_NOT_PROBED:
        return "warning"
    return "blocked"


def _input_actions_for_status(status: str, kind: str) -> list[dict[str, Any]]:
    if kind == INPUT_KIND_CAMERA_DEVICE:
        if status == INPUT_STATUS_READY:
            return [
                {
                    "id": ACTION_RUN_TRACKING_INPUT_PROBE,
                    "label": "Verify camera",
                    "primary": False,
                }
            ]
        if status == INPUT_STATUS_NOT_PROBED:
            return [
                {
                    "id": ACTION_RUN_TRACKING_INPUT_PROBE,
                    "label": "Test camera",
                    "primary": True,
                }
            ]
        return [
            {
                "id": ACTION_RECONNECT_TRACKING_INPUT,
                "label": "Reconnect camera",
                "primary": True,
            },
            {
                "id": ACTION_SELECT_TRACKING_INPUT,
                "label": "Choose another input",
                "primary": False,
            },
        ]
    if status in {INPUT_STATUS_MISSING, INPUT_STATUS_UNAVAILABLE, INPUT_STATUS_BLACK_FRAME}:
        return [
            {
                "id": ACTION_SELECT_TRACKING_INPUT,
                "label": "Choose another input",
                "primary": True,
            }
        ]
    return []


def _collect_diagnostic_strings(
    diag: Mapping[str, Any],
    raw: Mapping[str, Any],
    key: str,
) -> list[str]:
    rows: list[str] = []
    for source in (diag, raw):
        value = source.get(key) if isinstance(source, Mapping) else None
        if isinstance(value, (list, tuple)):
            rows.extend(str(item) for item in value if str(item or "").strip())
        elif value:
            rows.append(str(value))
    return list(dict.fromkeys(rows))


def _input_sources_health_summary(
    options: list[dict[str, Any]],
    selected_option: Mapping[str, Any] | None,
) -> dict[str, Any]:
    statuses = [str(item.get("status") or INPUT_STATUS_NOT_PROBED) for item in options]
    selected_diag = (
        selected_option.get("diagnostics")
        if isinstance(selected_option, Mapping) and isinstance(selected_option.get("diagnostics"), Mapping)
        else {}
    )
    selected_status = str(
        (selected_option or {}).get("status")
        or selected_diag.get("status")
        or ""
    )
    return {
        "selected_status": selected_status or (statuses[0] if statuses else ""),
        "selected_tone": str((selected_option or {}).get("tone") or ""),
        "ready_count": sum(1 for status in statuses if status == INPUT_STATUS_READY),
        "needs_probe_count": sum(1 for status in statuses if status == INPUT_STATUS_NOT_PROBED),
        "unavailable_count": sum(1 for status in statuses if status in {INPUT_STATUS_UNAVAILABLE, INPUT_STATUS_BLACK_FRAME, INPUT_STATUS_MISSING}),
        "has_reconnectable_camera": any(
            item.get("kind") == INPUT_KIND_CAMERA_DEVICE
            and str(item.get("status") or "") in {INPUT_STATUS_UNAVAILABLE, INPUT_STATUS_BLACK_FRAME}
            for item in options
        ),
        "fallback_available": False,
        "recommended_fallback_id": "",
        "recommended_fallback_label": "",
        "recommended_fallback_kind": "",
        "recommended_fallback_reason": "",
    }


def _input_sources_fallback_option(
    options: list[dict[str, Any]],
    selected_option: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(selected_option, Mapping):
        return {}
    selected_status = str(selected_option.get("status") or "")
    if selected_status not in {INPUT_STATUS_UNAVAILABLE, INPUT_STATUS_BLACK_FRAME, INPUT_STATUS_MISSING}:
        return {}
    selected_id = str(selected_option.get("id") or "")
    preferred_kinds = (INPUT_KIND_TIMELINE_VIDEO_CLIP, INPUT_KIND_MEDIA_POOL_VIDEO, INPUT_KIND_VIDEO_FILE, INPUT_KIND_CAMERA_DEVICE)
    for kind in preferred_kinds:
        for option in options:
            if not isinstance(option, Mapping):
                continue
            if str(option.get("id") or "") == selected_id:
                continue
            if str(option.get("kind") or "") != kind:
                continue
            if str(option.get("status") or "") != INPUT_STATUS_READY:
                continue
            input_payload = option.get("input") if isinstance(option.get("input"), Mapping) else {}
            return {
                "id": str(option.get("id") or ""),
                "label": str(option.get("label") or ""),
                "kind": str(option.get("kind") or ""),
                "status": str(option.get("status") or ""),
                "tone": str(option.get("tone") or "ok"),
                "action": {
                    "id": ACTION_SELECT_TRACKING_INPUT,
                    "label": "Use suggested input",
                    "primary": True,
                    "source_id": str(option.get("id") or ""),
                    "input": dict(input_payload),
                },
            }
    return {}


def _input_sources_warnings(options: list[dict[str, Any]], summary: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not options:
        warnings.append("no_tracking_input_sources")
    selected_status = str(summary.get("selected_status") or "")
    if selected_status in {INPUT_STATUS_UNAVAILABLE, INPUT_STATUS_BLACK_FRAME, INPUT_STATUS_MISSING}:
        warnings.append(f"selected_tracking_input_{selected_status}")
    if summary.get("fallback_available"):
        warnings.append("tracking_input_fallback_available")
    if summary.get("needs_probe_count"):
        warnings.append("tracking_input_needs_probe")
    return warnings


def _video_file_input_option(selected: VSeeFaceInputConfig) -> dict[str, Any]:
    path = selected.video_path
    label = Path(path).name if path else "Video file"
    health = _video_input_health(
        {"source_kind": INPUT_KIND_VIDEO_FILE},
        selected.source_id or f"video_file:{path}",
        {},
        path=path,
    )
    input_payload = _input_payload_for_choice(
        selected,
        mode=INPUT_OPENSEEFACE_VIDEO,
        source_kind=INPUT_KIND_VIDEO_FILE,
        source_id=selected.source_id or f"video_file:{path}",
        video_path=path,
    )
    return {
        "id": input_payload["source_id"],
        "kind": INPUT_KIND_VIDEO_FILE,
        "mode": INPUT_OPENSEEFACE_VIDEO,
        "label": label,
        "description": "Feed this video file to OpenSeeFace for tracking.",
        "video_path": path,
        "source_ref": {"path": path},
        "status": health["status"],
        "tone": health["tone"],
        "actions": health["actions"],
        "diagnostics": health["diagnostics"],
        "input": input_payload,
    }


def _input_payload_for_choice(selected: VSeeFaceInputConfig, **overrides: Any) -> dict[str, Any]:
    data = selected.to_dict()
    data.update(overrides)
    return VSeeFaceInputConfig.from_mapping(data).to_dict()


def _selected_input_option_id(selected: VSeeFaceInputConfig, options: list[dict[str, Any]]) -> str:
    if selected.source_id and any(str(item.get("id") or "") == selected.source_id for item in options):
        return selected.source_id
    if selected.source_kind == INPUT_KIND_CAMERA_DEVICE:
        if selected.camera_device_id:
            wanted = f"camera:{selected.camera_device_id}"
            if any(str(item.get("id") or "") == wanted for item in options):
                return wanted
        camera = next((item for item in options if item.get("kind") == INPUT_KIND_CAMERA_DEVICE), None)
        return str(camera.get("id") or "") if camera else ""
    if selected.source_kind == INPUT_KIND_MEDIA_POOL_VIDEO and selected.media_pool_id:
        wanted = f"media_pool:{selected.media_pool_id}"
        if any(str(item.get("id") or "") == wanted for item in options):
            return wanted
    if selected.source_kind == INPUT_KIND_TIMELINE_VIDEO_CLIP and selected.track_id is not None and selected.clip_id is not None:
        wanted = f"timeline:{selected.track_id}:{selected.clip_id}"
        if any(str(item.get("id") or "") == wanted for item in options):
            return wanted
    selected_path = _casefold_path(selected.video_path)
    if selected_path:
        for item in options:
            if _casefold_path(str(item.get("video_path") or "")) == selected_path:
                return str(item.get("id") or "")
    return ""


def _input_config_to_choice(selected: VSeeFaceInputConfig) -> dict[str, Any]:
    payload = selected.to_dict()
    if selected.source_kind == INPUT_KIND_CAMERA_DEVICE:
        return {
            "id": selected.source_id or "camera:default",
            "kind": INPUT_KIND_CAMERA_DEVICE,
            "mode": INPUT_WEBCAM,
            "label": selected.camera_device_name or "Default camera",
            "description": "Use a live camera as the OpenSeeFace tracking input.",
            "source_ref": {"camera_device_id": selected.camera_device_id, "camera_index": selected.camera_index},
            "input": payload,
        }
    path = selected.video_path
    return {
        "id": selected.source_id or _default_input_source_id(selected.source_kind, payload),
        "kind": selected.source_kind,
        "mode": INPUT_OPENSEEFACE_VIDEO,
        "label": Path(path).name if path else "Video input",
        "description": "Feed a project video to OpenSeeFace for tracking.",
        "video_path": path,
        "source_ref": {
            "path": path,
            "media_pool_id": selected.media_pool_id,
            "track_id": selected.track_id,
            "clip_id": selected.clip_id,
        },
        "input": payload,
    }


def _is_video_input_path(path: str) -> bool:
    return Path(str(path or "")).suffix.casefold() in VIDEO_INPUT_EXTS


def _casefold_path(path: str) -> str:
    return str(path or "").replace("\\", "/").casefold()


def _action_to_view(action: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(action, Mapping):
        return None
    return {
        "id": str(action.get("id") or ""),
        "label": str(action.get("label") or ""),
        "kind": str(action.get("kind") or "ui"),
        "enabled": True,
        "primary": bool(action.get("primary", False)),
        "auto_run": bool(action.get("auto_run", False)),
        "requires_admin": bool((action.get("plan") if isinstance(action.get("plan"), Mapping) else {}).get("requires_admin", False)),
        "registry_action": _registry_action_for_plan(action.get("plan") if isinstance(action.get("plan"), Mapping) else {}),
        "form": _form_for_plan(action.get("plan") if isinstance(action.get("plan"), Mapping) else {}),
    }


def _view_card(card_id: str, title: str, text: str, tone: str) -> dict[str, str]:
    return {
        "id": card_id,
        "title": title,
        "text": text,
        "tone": tone,
    }


def _tool_step(step_id: str, program: str, args: list[str], *, requires_admin: bool = False) -> dict[str, Any]:
    return {
        "id": step_id,
        "kind": "tool",
        "program": program,
        "args": args,
        "requires_admin": bool(requires_admin),
        "auto_run": False,
    }


def _manual_step(step_id: str, text: str) -> dict[str, Any]:
    return {
        "id": step_id,
        "kind": "manual",
        "text": text,
        "auto_run": False,
    }


def _ui_step(
    step_id: str,
    control: str,
    text: str,
    *,
    registry_action: str = "",
    form: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    step = {
        "id": step_id,
        "kind": "ui",
        "control": control,
        "text": text,
        "auto_run": False,
    }
    if registry_action:
        step["registry_action"] = str(registry_action)
    if isinstance(form, Mapping):
        step["form"] = dict(form)
    return step


def _registry_action_for_plan(plan: Mapping[str, Any]) -> str:
    for step in plan.get("steps") if isinstance(plan.get("steps"), list) else []:
        if isinstance(step, Mapping) and str(step.get("registry_action") or ""):
            return str(step.get("registry_action") or "")
    return ""


def _form_for_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    for step in plan.get("steps") if isinstance(plan.get("steps"), list) else []:
        if isinstance(step, Mapping) and isinstance(step.get("form"), Mapping):
            return dict(step.get("form") or {})
    return {}


def _post_install_verify_args(input_source: Mapping[str, Any] | None, *, out: str, launch: bool = False) -> list[str]:
    args = ["tools\\verify_vseeface_post_install.py"]
    if launch:
        args.append("--launch-vseeface")
    source = input_source if isinstance(input_source, Mapping) else {}
    video_path = str(source.get("video_path") or "").strip()
    mode = str(source.get("mode") or "")
    if mode == INPUT_OPENSEEFACE_VIDEO and video_path:
        args.extend(["--video", video_path])
        port = _optional_int(source.get("openseeface_port"))
        if port is not None:
            args.extend(["--port", str(port)])
        fps = source.get("fps")
        if fps not in (None, ""):
            try:
                args.extend(["--fps", str(max(1.0, float(fps)))])
            except (TypeError, ValueError):
                pass
        crop = _crop_to_arg(source.get("crop"))
        if crop:
            args.extend(["--crop", crop])
    else:
        args.append("--skip-video-send")
    args.extend(["--out", out])
    return args


def _crop_to_arg(value: Any) -> str:
    crop = _normalize_crop(value)
    if not crop:
        return ""
    return ",".join(f"{item:.6g}" for item in crop)


def _bridge_view_summary(state: str, capture: Mapping[str, Any], preflight: Mapping[str, Any]) -> str:
    if state == BRIDGE_STATE_READY:
        return "VSeeFace capture is ready for the broadcast scene."
    if state == BRIDGE_STATE_DEGRADED:
        if capture.get("status") == CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK:
            return "VSeeFace capture is black; Program Output falls back to the internal VRM renderer."
        if capture.get("status") == CAPTURE_STATUS_BLOCKED_REGISTRATION:
            return "VSeeFaceCamera is not registered; Program Output falls back to the internal VRM renderer."
        if capture.get("status") == CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED:
            return "VSeeFace virtual camera capture failed; Program Output falls back to the internal VRM renderer."
        return "VSeeFace capture needs attention; Program Output falls back to the internal VRM renderer."
    if state == BRIDGE_STATE_BLOCKED:
        errors = [str(item) for item in preflight.get("errors") or []]
        if "vseeface_exe_missing" in errors:
            return "Select the external VSeeFace executable before using the bridge."
        if "vseeface_requires_vrm0" in errors:
            return "Select a VSeeFace-compatible VRM0 avatar."
        return "Complete VSeeFace bridge setup before using this source."
    return "Run a capture probe before showing VSeeFace live."


def _setup_card_text(preflight: Mapping[str, Any]) -> str:
    if bool(preflight.get("ok")):
        return "VSeeFace executable and VRM avatar are configured."
    errors = [str(item) for item in preflight.get("errors") or []]
    if "vseeface_exe_missing" in errors:
        return "VSeeFace executable is missing."
    if "vseeface_requires_vrm0" in errors:
        return "Avatar must be VRM0 for VSeeFace."
    return "Bridge setup is incomplete."


def _setup_card_tone(preflight: Mapping[str, Any]) -> str:
    return "ok" if bool(preflight.get("ok")) else "blocked"


def _install_to_view(install: Mapping[str, Any]) -> dict[str, Any]:
    actions = install.get("actions") if isinstance(install.get("actions"), list) else []
    primary = next((item for item in actions if isinstance(item, Mapping) and bool(item.get("primary"))), None)
    secondary = [item for item in actions if isinstance(item, Mapping) and item is not primary]
    return {
        "schema": BRIDGE_INSTALL_SCHEMA,
        "title": "VSeeFace Dependency",
        "state": str(install.get("state") or "missing"),
        "installed": bool(install.get("installed", False)),
        "tone": str(install.get("tone") or "blocked"),
        "text": str(install.get("text") or ""),
        "configured_exe": str(install.get("configured_exe") or ""),
        "default_exe": str(install.get("default_exe") or ""),
        "install_dir": str(install.get("install_dir") or ""),
        "download_page_url": str(install.get("download_page_url") or VSEEFACE_DOWNLOAD_PAGE_URL),
        "local_zip_available": bool(install.get("local_zip_candidates")),
        "primary_action": _action_to_view(primary),
        "secondary_actions": [_action_to_view(item) for item in secondary],
    }


def _capture_card_text(capture: Mapping[str, Any]) -> str:
    ui = capture.get("ui") if isinstance(capture.get("ui"), Mapping) else {}
    return str(ui.get("label") or capture.get("status") or "Not probed")


def _capture_card_tone(capture: Mapping[str, Any], severity: str) -> str:
    if capture.get("ready") is True:
        return "ok"
    if capture.get("ready") is False:
        return _tone_for_severity(severity)
    return "info"


def _scene_card_text(scene_diag: Mapping[str, Any]) -> str:
    if scene_diag.get("degraded_frame_sources"):
        return "Scene OK through internal VRM fallback."
    if bool(scene_diag.get("ok")):
        return "Scene diagnostics are OK."
    return "Scene is missing a required live source."


def _scene_card_tone(scene_diag: Mapping[str, Any]) -> str:
    if scene_diag.get("degraded_frame_sources"):
        return "warning"
    return "ok" if bool(scene_diag.get("ok")) else "blocked"


def _input_source_to_view(input_sources: Mapping[str, Any]) -> dict[str, Any]:
    selected = input_sources.get("selected") if isinstance(input_sources.get("selected"), Mapping) else {}
    counts = input_sources.get("counts") if isinstance(input_sources.get("counts"), Mapping) else {}
    diagnostics = input_sources.get("diagnostics") if isinstance(input_sources.get("diagnostics"), Mapping) else {}
    fallback = input_sources.get("fallback") if isinstance(input_sources.get("fallback"), Mapping) else {}
    selected_diagnostics = selected.get("diagnostics") if isinstance(selected.get("diagnostics"), Mapping) else {}
    return {
        "schema": INPUT_SOURCE_SCHEMA,
        "selected_id": str(input_sources.get("selected_id") or selected.get("id") or ""),
        "label": str(selected.get("label") or "Default camera"),
        "kind": str(selected.get("kind") or INPUT_KIND_CAMERA_DEVICE),
        "mode": str(selected.get("mode") or INPUT_WEBCAM),
        "status": str(selected.get("status") or diagnostics.get("selected_status") or INPUT_STATUS_NOT_PROBED),
        "tone": str(selected.get("tone") or diagnostics.get("selected_tone") or _input_card_tone(input_sources)),
        "actions": list(selected.get("actions") if isinstance(selected.get("actions"), list) else []),
        "diagnostics": dict(selected_diagnostics),
        "action": str(input_sources.get("action") or ACTION_SELECT_TRACKING_INPUT),
        "option_count": len(input_sources.get("options") if isinstance(input_sources.get("options"), list) else []),
        "camera_device_count": int(counts.get("camera_devices", 0) or 0),
        "media_pool_video_count": int(counts.get("media_pool_videos", 0) or 0),
        "timeline_video_clip_count": int(counts.get("timeline_video_clips", 0) or 0),
        "fallback_available": bool(fallback),
        "recommended_fallback_id": str(fallback.get("id") or ""),
        "recommended_fallback_label": str(fallback.get("label") or ""),
        "recommended_fallback_kind": str(fallback.get("kind") or ""),
        "recommended_fallback_action": dict(fallback.get("action") if isinstance(fallback.get("action"), Mapping) else {}),
    }


def _sidecar_settings_to_view(sidecar_settings: Mapping[str, Any]) -> dict[str, Any]:
    values = sidecar_settings.get("values") if isinstance(sidecar_settings.get("values"), Mapping) else {}
    errors = sidecar_settings.get("errors") if isinstance(sidecar_settings.get("errors"), list) else []
    warnings = sidecar_settings.get("warnings") if isinstance(sidecar_settings.get("warnings"), list) else []
    return {
        "schema": BRIDGE_SIDECAR_SETTINGS_SCHEMA,
        "ok": bool(sidecar_settings.get("ok", False)),
        "read_only": True,
        "would_write": False,
        "settings_path": str(sidecar_settings.get("settings_path") or ""),
        "avatar_file": str(values.get("AvatarFile") or ""),
        "camera_name": str(values.get("CameraName") or ""),
        "openseeface_endpoint": {
            "host": str(values.get("IP") or ""),
            "port": str(values.get("Port") or ""),
        },
        "virtual_camera_kept_enabled": str(values.get("KeepVirtualCamEnabled") or "") == "1",
        "tone": "blocked" if errors else ("warning" if warnings else "ok"),
    }


def _input_card_text(input_sources: Mapping[str, Any]) -> str:
    selected = input_sources.get("selected") if isinstance(input_sources.get("selected"), Mapping) else {}
    label = str(selected.get("label") or "Default camera")
    kind = str(selected.get("kind") or INPUT_KIND_CAMERA_DEVICE)
    if kind == INPUT_KIND_CAMERA_DEVICE:
        return f"Camera: {label}"
    if kind == INPUT_KIND_MEDIA_POOL_VIDEO:
        return f"Media pool: {label}"
    if kind == INPUT_KIND_TIMELINE_VIDEO_CLIP:
        return f"Timeline clip: {label}"
    return f"Video file: {label}"


def _input_card_tone(input_sources: Mapping[str, Any]) -> str:
    selected = input_sources.get("selected") if isinstance(input_sources.get("selected"), Mapping) else {}
    selected_tone = str(selected.get("tone") or "")
    if selected_tone:
        return selected_tone
    diagnostics = input_sources.get("diagnostics") if isinstance(input_sources.get("diagnostics"), Mapping) else {}
    selected_status = str(diagnostics.get("selected_status") or "")
    if selected_status:
        return _input_tone_for_status(selected_status)
    warnings = input_sources.get("warnings") if isinstance(input_sources.get("warnings"), list) else []
    return "warning" if warnings else "ok"


def _sidecar_card_text(sidecar_settings: Mapping[str, Any]) -> str:
    values = sidecar_settings.get("values") if isinstance(sidecar_settings.get("values"), Mapping) else {}
    errors = [str(item) for item in (sidecar_settings.get("errors") or [])]
    warnings = [str(item) for item in (sidecar_settings.get("warnings") or [])]
    if "avatar_vrm_missing" in errors:
        return "Select a VRM0 avatar before applying sidecar settings."
    if not bool(sidecar_settings.get("ok")):
        return "Sidecar settings are not ready."
    host = str(values.get("IP") or "")
    port = str(values.get("Port") or "")
    if "avatar_vrm_file_not_found" in warnings:
        return "Settings plan is ready, but the avatar file path needs checking."
    if host and port:
        return f"OpenSeeFace {host}:{port}"
    return "Sidecar settings plan is ready."


def _sidecar_card_tone(sidecar_settings: Mapping[str, Any]) -> str:
    errors = sidecar_settings.get("errors") if isinstance(sidecar_settings.get("errors"), list) else []
    warnings = sidecar_settings.get("warnings") if isinstance(sidecar_settings.get("warnings"), list) else []
    if errors:
        return "blocked"
    if warnings:
        return "warning"
    return "ok" if bool(sidecar_settings.get("ok")) else "info"


def _sidecar_workflow_state(
    preview: Mapping[str, Any],
    plan: Mapping[str, Any],
    gate: Mapping[str, Any],
    *,
    confirm: bool,
) -> str:
    if not bool(preview.get("ok", False)):
        return "blocked_settings"
    if not bool(plan.get("ok", False)):
        return "blocked_plan"
    if bool(gate.get("execute_allowed", False)):
        return "ready_to_execute"
    if bool(gate.get("requires_admin", False)) and "administrator_approval_required" in [str(item) for item in gate.get("warnings") or []]:
        return "admin_required"
    if not bool(gate.get("ok", False)):
        return "blocked_gate"
    if not confirm:
        return "confirmation_required"
    return "blocked_gate"


def _sidecar_workflow_view(
    preview: Mapping[str, Any],
    plan: Mapping[str, Any],
    gate: Mapping[str, Any],
    executor: Mapping[str, Any],
    *,
    state: str,
) -> dict[str, Any]:
    values = preview.get("values") if isinstance(preview.get("values"), Mapping) else {}
    endpoint = {
        "host": str(values.get("IP") or ""),
        "port": str(values.get("Port") or ""),
    }
    return {
        "schema": BRIDGE_SIDECAR_WORKFLOW_SCHEMA,
        "state": state,
        "tone": _sidecar_workflow_tone(state),
        "title": "VSeeFace Sidecar",
        "text": _sidecar_workflow_text(state),
        "progress": _sidecar_workflow_progress(state),
        "settings_path": str(preview.get("settings_path") or ""),
        "avatar_file": str(values.get("AvatarFile") or ""),
        "openseeface_endpoint": endpoint,
        "execute_allowed": bool(gate.get("execute_allowed", False)),
        "dry_run": bool(executor.get("dry_run", True)),
        "would_run": any(bool(step.get("would_run")) for step in executor.get("steps", []) if isinstance(step, Mapping)),
        "steps": _sidecar_workflow_steps(preview, plan, gate, executor, state=state),
        "next_action": _sidecar_workflow_next_action(state),
        "actions": [
            _sidecar_workflow_action("preview_settings", "Preview settings", "vtuber.vseeface_sidecar_settings_preview"),
            _sidecar_workflow_action("apply_plan", "Build apply plan", "vtuber.vseeface_sidecar_apply_plan"),
            _sidecar_workflow_action("execution_gate", "Check execution gate", "vtuber.vseeface_sidecar_execution_gate"),
            _sidecar_workflow_action("executor_dry_run", "Dry run executor", "vtuber.vseeface_sidecar_executor_dry_run"),
        ],
    }


def _sidecar_workflow_tone(state: str) -> str:
    if state == "ready_to_execute":
        return "ok"
    if state in {"confirmation_required", "admin_required"}:
        return "warning"
    return "blocked"


def _sidecar_workflow_text(state: str) -> str:
    if state == "ready_to_execute":
        return "Ready for explicit executor handoff."
    if state == "confirmation_required":
        return "Review and confirm before writing VSeeFace settings."
    if state == "admin_required":
        return "Administrator approval is required before execution."
    if state == "blocked_settings":
        return "Choose a valid VRM0 avatar before applying sidecar settings."
    if state == "blocked_plan":
        return "Sidecar apply plan is not ready."
    return "Execution gate is blocked."


def _sidecar_workflow_progress(state: str) -> float:
    if state == "ready_to_execute":
        return 1.0
    if state == "confirmation_required":
        return 0.75
    if state == "admin_required":
        return 0.75
    if state == "blocked_gate":
        return 0.5
    if state == "blocked_plan":
        return 0.25
    return 0.0


def _sidecar_workflow_steps(
    preview: Mapping[str, Any],
    plan: Mapping[str, Any],
    gate: Mapping[str, Any],
    executor: Mapping[str, Any],
    *,
    state: str,
) -> list[dict[str, Any]]:
    settings_ok = bool(preview.get("ok", False))
    plan_ok = bool(plan.get("ok", False))
    gate_ok = bool(gate.get("ok", False))
    dry_run_ready = any(bool(step.get("would_run")) for step in executor.get("steps", []) if isinstance(step, Mapping))
    return [
        {
            "id": "settings_preview",
            "label": "Settings preview",
            "state": "done" if settings_ok else "blocked",
            "tone": "ok" if settings_ok else "blocked",
            "registry_action": "vtuber.vseeface_sidecar_settings_preview",
        },
        {
            "id": "apply_plan",
            "label": "Apply plan",
            "state": "done" if plan_ok else ("pending" if settings_ok else "blocked"),
            "tone": "ok" if plan_ok else ("info" if settings_ok else "blocked"),
            "registry_action": "vtuber.vseeface_sidecar_apply_plan",
        },
        {
            "id": "execution_gate",
            "label": "Execution gate",
            "state": _sidecar_gate_step_state(gate, state),
            "tone": _sidecar_gate_step_tone(gate, state),
            "registry_action": "vtuber.vseeface_sidecar_execution_gate",
        },
        {
            "id": "executor_dry_run",
            "label": "Executor dry run",
            "state": "done" if dry_run_ready else ("pending" if gate_ok else "blocked"),
            "tone": "ok" if dry_run_ready else ("info" if gate_ok else "blocked"),
            "registry_action": "vtuber.vseeface_sidecar_executor_dry_run",
        },
    ]


def _sidecar_gate_step_state(gate: Mapping[str, Any], workflow_state: str) -> str:
    if bool(gate.get("execute_allowed", False)):
        return "done"
    if workflow_state in {"confirmation_required", "admin_required"}:
        return "current"
    return "blocked" if not bool(gate.get("ok", False)) else "pending"


def _sidecar_gate_step_tone(gate: Mapping[str, Any], workflow_state: str) -> str:
    if bool(gate.get("execute_allowed", False)):
        return "ok"
    if workflow_state in {"confirmation_required", "admin_required"}:
        return "warning"
    return "blocked" if not bool(gate.get("ok", False)) else "info"


def _sidecar_workflow_next_action(state: str) -> dict[str, Any] | None:
    if state == "confirmation_required":
        return _sidecar_workflow_action("confirm_sidecar_settings", "Confirm settings", "vtuber.vseeface_sidecar_workflow")
    if state == "ready_to_execute":
        return _sidecar_workflow_action("executor_dry_run", "Review executor dry run", "vtuber.vseeface_sidecar_executor_dry_run")
    if state == "admin_required":
        return _sidecar_workflow_action("execution_gate", "Review admin requirement", "vtuber.vseeface_sidecar_execution_gate")
    if state in {"blocked_settings", "blocked_plan"}:
        return _sidecar_workflow_action("preview_settings", "Preview settings", "vtuber.vseeface_sidecar_settings_preview")
    if state == "blocked_gate":
        return _sidecar_workflow_action("execution_gate", "Check execution gate", "vtuber.vseeface_sidecar_execution_gate")
    return None


def _sidecar_workflow_action(action_id: str, label: str, registry_action: str) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "registry_action": registry_action,
        "auto_run": False,
    }


def _tone_for_severity(severity: str) -> str:
    if severity == "ok":
        return "ok"
    if severity == "blocked":
        return "blocked"
    if severity == "warning":
        return "warning"
    return "info"


def _normalize_rgba(value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return tuple(max(0, min(255, int(item))) for item in value[:4])  # type: ignore[return-value]
