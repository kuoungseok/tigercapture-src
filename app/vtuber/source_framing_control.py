"""User offsets and live-camera stabilization for VTuber framing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.vtuber.source_framing import SourceFramingSolution, solve_source_framing
from app.vtuber.video_face_driver import FaceMotionFrame


SOURCE_FRAMING_CONTROL_SCHEMA = "tigerstudio.vtuber.source_framing_control.v1"
SOURCE_FRAMING_LIVE_SCHEMA = "tigerstudio.vtuber.source_framing_live.v1"


@dataclass(frozen=True)
class FramingUserOffset:
    pan_x: float = 0.0
    pan_y: float = 0.0
    pan_z: float = 0.0
    zoom_delta: float = 0.0
    zoom_scale: float = 1.0
    camera_z_delta: float = 0.0
    lower_occlusion_y_delta: float = 0.0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "FramingUserOffset":
        data = payload or {}
        return cls(
            pan_x=_float(data.get("pan_x"), 0.0),
            pan_y=_float(data.get("pan_y"), 0.0),
            pan_z=_float(data.get("pan_z"), 0.0),
            zoom_delta=_float(data.get("zoom_delta"), 0.0),
            zoom_scale=_float(data.get("zoom_scale"), 1.0),
            camera_z_delta=_float(data.get("camera_z_delta"), 0.0),
            lower_occlusion_y_delta=_float(data.get("lower_occlusion_y_delta"), 0.0),
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "pan_x": float(self.pan_x),
            "pan_y": float(self.pan_y),
            "pan_z": float(self.pan_z),
            "zoom_delta": float(self.zoom_delta),
            "zoom_scale": float(self.zoom_scale),
            "camera_z_delta": float(self.camera_z_delta),
            "lower_occlusion_y_delta": float(self.lower_occlusion_y_delta),
        }


@dataclass(frozen=True)
class LiveFramingConfig:
    smoothing: float = 0.62
    dead_zone_pan: float = 0.012
    dead_zone_zoom: float = 0.045
    dead_zone_occlusion: float = 0.01
    min_update_interval_ms: int = 33
    lock_framing: bool = False

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "LiveFramingConfig":
        data = payload or {}
        return cls(
            smoothing=_clamp(_float(data.get("smoothing"), 0.62), 0.0, 0.95),
            dead_zone_pan=max(0.0, _float(data.get("dead_zone_pan"), 0.012)),
            dead_zone_zoom=max(0.0, _float(data.get("dead_zone_zoom"), 0.045)),
            dead_zone_occlusion=max(0.0, _float(data.get("dead_zone_occlusion"), 0.01)),
            min_update_interval_ms=max(0, int(_float(data.get("min_update_interval_ms"), 33))),
            lock_framing=bool(data.get("lock_framing", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "smoothing": float(self.smoothing),
            "dead_zone_pan": float(self.dead_zone_pan),
            "dead_zone_zoom": float(self.dead_zone_zoom),
            "dead_zone_occlusion": float(self.dead_zone_occlusion),
            "min_update_interval_ms": int(self.min_update_interval_ms),
            "lock_framing": bool(self.lock_framing),
        }


def apply_framing_user_offset(
    framing: SourceFramingSolution | Mapping[str, Any],
    user_offset: FramingUserOffset | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply manual pan/zoom/occlusion offsets while preserving automatic values."""
    automatic = _framing_to_dict(framing)
    auto_view = dict(automatic.get("model_view") or {})
    offset = user_offset if isinstance(user_offset, FramingUserOffset) else FramingUserOffset.from_mapping(user_offset)
    final_view = _apply_offset_to_model_view(auto_view, offset)
    final = {
        "model_view": final_view,
        "track_rotation": list(automatic.get("track_rotation") or [-5.0, 180.0, 0.0]),
    }
    return {
        "schema": SOURCE_FRAMING_CONTROL_SCHEMA,
        "ok": bool(automatic.get("ok", True)),
        "time_ms": int(automatic.get("time_ms") or 0),
        "preset": str(automatic.get("preset") or "bust_up"),
        "automatic": {
            "model_view": auto_view,
            "track_rotation": list(automatic.get("track_rotation") or [-5.0, 180.0, 0.0]),
        },
        "user_offset": offset.to_dict(),
        "final": final,
        "diagnostics": {
            "method": "automatic_framing_plus_user_offset",
            "clamped": _offset_clamp_diagnostics(auto_view, final_view, offset),
        },
    }


def update_live_source_framing(
    frame: FaceMotionFrame,
    frame_size: tuple[int, int],
    *,
    previous_state: Mapping[str, Any] | None = None,
    preset: str = "bust_up",
    subject_box: tuple[int, int, int, int] | None = None,
    subject_source: str | None = None,
    user_offset: FramingUserOffset | Mapping[str, Any] | None = None,
    config: LiveFramingConfig | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Update live-camera framing with smoothing, dead-zone, lock, and offsets."""
    cfg = config if isinstance(config, LiveFramingConfig) else LiveFramingConfig.from_mapping(config)
    auto = solve_source_framing(
        frame,
        frame_size,
        preset=preset,
        subject_box=subject_box,
        subject_source=subject_source,
    )
    previous = dict(previous_state or {})
    prev_view = dict(previous.get("model_view") or {})
    prev_rotation = list(previous.get("track_rotation") or [])
    prev_time = int(_float(previous.get("time_ms"), -1))
    now = int(frame.time_ms)
    throttled = bool(prev_view) and cfg.min_update_interval_ms > 0 and prev_time >= 0 and now - prev_time < cfg.min_update_interval_ms
    locked = bool(cfg.lock_framing and prev_view)
    if locked or throttled:
        stable_view = prev_view
        stable_rotation = prev_rotation or list(auto.track_rotation)
    else:
        stable_view = _stabilize_model_view(prev_view, dict(auto.model_view or {}), cfg)
        stable_rotation = _stabilize_rotation(prev_rotation, list(auto.track_rotation), cfg)
    stable = _solution_with_view(auto, stable_view, stable_rotation, diagnostics={
        "live_smoothing": cfg.smoothing,
        "lock_framing": bool(cfg.lock_framing),
        "locked": locked,
        "update_throttled": throttled,
    })
    controlled = apply_framing_user_offset(stable, user_offset)
    return {
        "schema": SOURCE_FRAMING_LIVE_SCHEMA,
        "ok": bool(auto.ok),
        "mode": "live_camera",
        "time_ms": now,
        "preset": stable.preset,
        "automatic": stable.to_dict(),
        "user_offset": controlled["user_offset"],
        "final": controlled["final"],
        "state": {
            "time_ms": now,
            "model_view": stable_view,
            "track_rotation": stable_rotation,
            "preset": stable.preset,
            "locked": locked,
            "update_throttled": throttled,
        },
        "diagnostics": {
            "config": cfg.to_dict(),
            "subject_source": (stable.diagnostics or {}).get("subject_source"),
            "method": "live_camera_framing_update",
        },
    }


def _apply_offset_to_model_view(model_view: Mapping[str, Any], offset: FramingUserOffset) -> dict[str, float | bool]:
    out: dict[str, float | bool] = dict(model_view)
    zoom = _float(model_view.get("zoom"), 1.0) * _clamp(offset.zoom_scale, 0.25, 4.0) + offset.zoom_delta
    out["zoom"] = _clamp(zoom, 0.2, 20.0)
    out["camera_z"] = _clamp(_float(model_view.get("camera_z"), 3.25) + offset.camera_z_delta, 0.2, 20.0)
    out["pan_x"] = _clamp(_float(model_view.get("pan_x"), 0.0) + offset.pan_x, -1.5, 1.5)
    out["pan_y"] = _clamp(_float(model_view.get("pan_y"), 0.0) + offset.pan_y, -3.0, 1.5)
    out["pan_z"] = _clamp(_float(model_view.get("pan_z"), 0.0) + offset.pan_z, -3.0, 3.0)
    out["lower_occlusion_y"] = _clamp(
        _float(model_view.get("lower_occlusion_y"), 1.0) + offset.lower_occlusion_y_delta,
        0.0,
        1.0,
    )
    out["auto_fit"] = bool(model_view.get("auto_fit", False))
    return out


def _stabilize_model_view(previous: Mapping[str, Any], current: Mapping[str, Any], cfg: LiveFramingConfig) -> dict[str, float | bool]:
    if not previous:
        return dict(current)
    out: dict[str, float | bool] = dict(current)
    for key in ("pan_x", "pan_y", "pan_z"):
        out[key] = _deadzone_lerp(_float(previous.get(key), 0.0), _float(current.get(key), 0.0), cfg.dead_zone_pan, cfg.smoothing)
    for key in ("zoom", "camera_z"):
        out[key] = _deadzone_lerp(_float(previous.get(key), 0.0), _float(current.get(key), 0.0), cfg.dead_zone_zoom, cfg.smoothing)
    out["lower_occlusion_y"] = _deadzone_lerp(
        _float(previous.get("lower_occlusion_y"), 1.0),
        _float(current.get("lower_occlusion_y"), 1.0),
        cfg.dead_zone_occlusion,
        cfg.smoothing,
    )
    out["auto_fit"] = bool(current.get("auto_fit", False))
    return out


def _stabilize_rotation(previous: list[Any], current: list[float], cfg: LiveFramingConfig) -> list[float]:
    if not previous:
        return [float(v) for v in current]
    out = [float(v) for v in current]
    out[0] = _deadzone_lerp(_float(previous[0] if previous else 0.0, 0.0), float(current[0]), 0.08, cfg.smoothing)
    return out


def _solution_with_view(
    source: SourceFramingSolution,
    model_view: Mapping[str, Any],
    track_rotation: list[Any],
    *,
    diagnostics: Mapping[str, Any],
) -> SourceFramingSolution:
    from dataclasses import replace

    diag = dict(source.diagnostics or {})
    diag.update(diagnostics)
    rotation = tuple(float(v) for v in (list(track_rotation) + [180.0, 0.0])[:3])
    return replace(source, model_view=dict(model_view), track_rotation=rotation, diagnostics=diag)


def _framing_to_dict(framing: SourceFramingSolution | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(framing, SourceFramingSolution):
        return framing.to_dict()
    data = dict(framing)
    if "framing" in data and isinstance(data.get("framing"), Mapping):
        return dict(data["framing"])
    return data


def _offset_clamp_diagnostics(
    automatic: Mapping[str, Any],
    final: Mapping[str, Any],
    offset: FramingUserOffset,
) -> list[str]:
    warnings: list[str] = []
    requested_zoom = _float(automatic.get("zoom"), 1.0) * _clamp(offset.zoom_scale, 0.25, 4.0) + offset.zoom_delta
    if requested_zoom != _float(final.get("zoom"), requested_zoom):
        warnings.append("zoom_clamped")
    requested_occlusion = _float(automatic.get("lower_occlusion_y"), 1.0) + offset.lower_occlusion_y_delta
    if requested_occlusion != _float(final.get("lower_occlusion_y"), requested_occlusion):
        warnings.append("lower_occlusion_y_clamped")
    return warnings


def _deadzone_lerp(previous: float, current: float, dead_zone: float, smoothing: float) -> float:
    if abs(current - previous) <= dead_zone:
        return previous
    return previous * smoothing + current * (1.0 - smoothing)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))
