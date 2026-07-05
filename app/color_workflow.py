"""Professional color workflow helpers.

This module keeps the deeper color-page concepts Qt-free so they can be tested
and later wired into the Color UI, node graph, preview, and export paths:

- RGB/master curves
- H/S/V qualifier masks
- power-window style tracking masks
- node-style masked grade application
- lightweight scope diagnostics
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable

import numpy as np


@dataclass(frozen=True)
class ColorCurve:
    """A 0..255 curve with linearly interpolated control points."""

    points: tuple[tuple[int, int], ...] = ((0, 0), (255, 255))

    @classmethod
    def from_any(cls, value: Any) -> "ColorCurve":
        if isinstance(value, ColorCurve):
            return value
        points: list[tuple[int, int]] = []
        for raw in value or []:
            try:
                x, y = raw
                points.append((int(x), int(y)))
            except Exception:
                continue
        return cls(tuple(points) or ((0, 0), (255, 255)))

    def normalized_points(self) -> tuple[tuple[int, int], ...]:
        cleaned = []
        for x, y in self.points:
            cleaned.append((max(0, min(255, int(x))), max(0, min(255, int(y)))))
        cleaned.sort(key=lambda p: p[0])
        dedup: dict[int, int] = {}
        for x, y in cleaned:
            dedup[x] = y
        pts = sorted(dedup.items())
        if not pts or pts[0][0] > 0:
            pts.insert(0, (0, pts[0][1] if pts else 0))
        if pts[-1][0] < 255:
            pts.append((255, pts[-1][1]))
        return tuple(pts)

    def lut(self) -> np.ndarray:
        pts = self.normalized_points()
        xs = np.array([p[0] for p in pts], dtype=np.float32)
        ys = np.array([p[1] for p in pts], dtype=np.float32)
        sample = np.arange(256, dtype=np.float32)
        return np.interp(sample, xs, ys).clip(0, 255).astype(np.uint8)

    def to_list(self) -> list[list[int]]:
        return [[int(x), int(y)] for x, y in self.normalized_points()]


@dataclass(frozen=True)
class CurveSet:
    master: ColorCurve = field(default_factory=ColorCurve)
    red: ColorCurve = field(default_factory=ColorCurve)
    green: ColorCurve = field(default_factory=ColorCurve)
    blue: ColorCurve = field(default_factory=ColorCurve)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CurveSet":
        data = data or {}
        return cls(
            master=ColorCurve.from_any(data.get("master")),
            red=ColorCurve.from_any(data.get("red")),
            green=ColorCurve.from_any(data.get("green")),
            blue=ColorCurve.from_any(data.get("blue")),
        )

    def is_identity(self) -> bool:
        identity = ((0, 0), (255, 255))
        return (
            self.master.normalized_points() == identity
            and self.red.normalized_points() == identity
            and self.green.normalized_points() == identity
            and self.blue.normalized_points() == identity
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "master": self.master.to_list(),
            "red": self.red.to_list(),
            "green": self.green.to_list(),
            "blue": self.blue.to_list(),
        }


@dataclass(frozen=True)
class ColorQualifier:
    """HSV qualifier, similar to a color-page HSL key."""

    enabled: bool = False
    hue_center: float = 60.0
    hue_width: float = 30.0
    sat_min: float = 0.15
    sat_max: float = 1.0
    val_min: float = 0.0
    val_max: float = 1.0
    softness: float = 0.08
    clean_black: float = 0.0
    clean_white: float = 0.0
    denoise_radius: int = 0
    invert: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ColorQualifier":
        if not isinstance(data, dict):
            return cls()
        return cls(
            enabled=bool(data.get("enabled", False)),
            hue_center=float(data.get("hue_center", data.get("key_hue", 60.0))),
            hue_width=float(data.get("hue_width", data.get("hue_range", 30.0))),
            sat_min=float(data.get("sat_min", 0.15)),
            sat_max=float(data.get("sat_max", 1.0)),
            val_min=float(data.get("val_min", 0.0)),
            val_max=float(data.get("val_max", 1.0)),
            softness=float(data.get("softness", 0.08)),
            clean_black=float(data.get("clean_black", data.get("black_clean", 0.0))),
            clean_white=float(data.get("clean_white", data.get("white_clean", 0.0))),
            denoise_radius=int(data.get("denoise_radius", data.get("denoise", 0)) or 0),
            invert=bool(data.get("invert", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "hue_center": float(self.hue_center),
            "hue_width": float(self.hue_width),
            "sat_min": float(self.sat_min),
            "sat_max": float(self.sat_max),
            "val_min": float(self.val_min),
            "val_max": float(self.val_max),
            "softness": float(self.softness),
            "clean_black": float(self.clean_black),
            "clean_white": float(self.clean_white),
            "denoise_radius": int(self.denoise_radius),
            "invert": bool(self.invert),
        }


@dataclass(frozen=True)
class TrackingWindow:
    """Power-window style shape in normalized frame coordinates."""

    enabled: bool = False
    shape: str = "ellipse"  # ellipse | rectangle
    x: float = 0.5
    y: float = 0.5
    w: float = 0.5
    h: float = 0.5
    feather: float = 0.08
    opacity: float = 1.0
    track_object: bool = False
    tracking_status: str = "manual"
    tracker_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TrackingWindow":
        if not isinstance(data, dict):
            return cls()
        return cls(
            enabled=bool(data.get("enabled", False)),
            shape=str(data.get("shape", "ellipse")),
            x=float(data.get("x", 0.5)),
            y=float(data.get("y", 0.5)),
            w=float(data.get("w", 0.5)),
            h=float(data.get("h", 0.5)),
            feather=float(data.get("feather", 0.08)),
            opacity=float(data.get("opacity", 1.0)),
            track_object=bool(data.get("track_object", False)),
            tracking_status=str(data.get("tracking_status", "manual") or "manual"),
            tracker_id=str(data.get("tracker_id", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "shape": str(self.shape),
            "x": float(self.x),
            "y": float(self.y),
            "w": float(self.w),
            "h": float(self.h),
            "feather": float(self.feather),
            "opacity": float(self.opacity),
            "track_object": bool(self.track_object),
            "tracking_status": str(self.tracking_status),
            "tracker_id": str(self.tracker_id),
        }


def normalize_tracking_window(window: TrackingWindow | dict[str, Any]) -> TrackingWindow:
    """Clamp a power window to editable normalized frame coordinates."""
    win = TrackingWindow.from_dict(window) if isinstance(window, dict) else window
    shape = str(win.shape or "ellipse").lower()
    if not shape.startswith("rect"):
        shape = "ellipse"
    else:
        shape = "rectangle"
    width = max(0.01, min(1.0, float(win.w)))
    height = max(0.01, min(1.0, float(win.h)))
    half_w = width * 0.5
    half_h = height * 0.5
    x = max(half_w, min(1.0 - half_w, float(win.x)))
    y = max(half_h, min(1.0 - half_h, float(win.y)))
    return replace(
        win,
        shape=shape,
        x=x,
        y=y,
        w=width,
        h=height,
        feather=max(0.0, min(1.0, float(win.feather))),
        opacity=max(0.0, min(1.0, float(win.opacity))),
    )


def edit_tracking_window(
    window: TrackingWindow | dict[str, Any],
    handle: str,
    dx: float,
    dy: float,
    *,
    min_size: float = 0.02,
) -> TrackingWindow:
    """Return a normalized power window after a UI handle drag.

    ``dx`` and ``dy`` are normalized frame-coordinate deltas. ``handle`` may be
    ``move`` or one of ``left``, ``right``, ``top``, ``bottom`` and their
    corner combinations such as ``top_left``.
    """
    win = normalize_tracking_window(window)
    handle = str(handle or "move").lower()
    min_size = max(0.005, min(0.5, float(min_size)))
    if handle == "move":
        half_w = win.w * 0.5
        half_h = win.h * 0.5
        return replace(
            win,
            x=max(half_w, min(1.0 - half_w, win.x + float(dx))),
            y=max(half_h, min(1.0 - half_h, win.y + float(dy))),
            enabled=True,
            tracking_status="manual",
        )

    left = win.x - win.w * 0.5
    right = win.x + win.w * 0.5
    top = win.y - win.h * 0.5
    bottom = win.y + win.h * 0.5
    dx = float(dx)
    dy = float(dy)

    if "left" in handle:
        left = max(0.0, min(right - min_size, left + dx))
    if "right" in handle:
        right = min(1.0, max(left + min_size, right + dx))
    if "top" in handle:
        top = max(0.0, min(bottom - min_size, top + dy))
    if "bottom" in handle:
        bottom = min(1.0, max(top + min_size, bottom + dy))

    return replace(
        win,
        x=(left + right) * 0.5,
        y=(top + bottom) * 0.5,
        w=max(min_size, right - left),
        h=max(min_size, bottom - top),
        enabled=True,
        tracking_status="manual",
    )


@dataclass(frozen=True)
class ColorNodeWorkflow:
    """A node color operation: grade + curves constrained by masks."""

    enabled: bool = True
    name: str = "Node"
    qualifier: ColorQualifier = field(default_factory=ColorQualifier)
    window: TrackingWindow = field(default_factory=TrackingWindow)
    curves: CurveSet = field(default_factory=CurveSet)
    opacity: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ColorNodeWorkflow":
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", True)),
            name=str(data.get("name", "Node")),
            qualifier=ColorQualifier.from_dict(data.get("qualifier")),
            window=TrackingWindow.from_dict(data.get("window")),
            curves=CurveSet.from_dict(data.get("curves")),
            opacity=float(data.get("opacity", 1.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "name": str(self.name),
            "qualifier": self.qualifier.to_dict(),
            "window": self.window.to_dict(),
            "curves": self.curves.to_dict(),
            "opacity": float(self.opacity),
        }


@dataclass(frozen=True)
class HDRZoneControl:
    """Zone-based tone controls for HDR/log style grading surfaces."""

    enabled: bool = False
    black: float = 0.0
    shadow: float = 0.0
    dark: float = 0.0
    light: float = 0.0
    highlight: float = 0.0
    specular: float = 0.0
    pivot: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "HDRZoneControl":
        if not isinstance(data, dict):
            return cls()
        return cls(
            enabled=bool(data.get("enabled", False)),
            black=float(data.get("black", 0.0)),
            shadow=float(data.get("shadow", data.get("shadows", 0.0))),
            dark=float(data.get("dark", data.get("darks", 0.0))),
            light=float(data.get("light", data.get("lights", 0.0))),
            highlight=float(data.get("highlight", data.get("highlights", 0.0))),
            specular=float(data.get("specular", 0.0)),
            pivot=float(data.get("pivot", 0.5)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "black": float(self.black),
            "shadow": float(self.shadow),
            "dark": float(self.dark),
            "light": float(self.light),
            "highlight": float(self.highlight),
            "specular": float(self.specular),
            "pivot": float(self.pivot),
        }


@dataclass(frozen=True)
class LogWheelSet:
    """Resolve-like log wheel metadata, stored in normalized RGB offsets."""

    shadows: tuple[float, float, float] = (0.0, 0.0, 0.0)
    midtones: tuple[float, float, float] = (0.0, 0.0, 0.0)
    highlights: tuple[float, float, float] = (0.0, 0.0, 0.0)
    pivot: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LogWheelSet":
        data = data or {}

        def _triple(value: Any) -> tuple[float, float, float]:
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                return (float(value[0]), float(value[1]), float(value[2]))
            if isinstance(value, dict):
                return (float(value.get("r", 0.0)), float(value.get("g", 0.0)), float(value.get("b", 0.0)))
            return (0.0, 0.0, 0.0)

        return cls(
            shadows=_triple(data.get("shadows")),
            midtones=_triple(data.get("midtones")),
            highlights=_triple(data.get("highlights")),
            pivot=float(data.get("pivot", 0.5)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "shadows": [float(v) for v in self.shadows],
            "midtones": [float(v) for v in self.midtones],
            "highlights": [float(v) for v in self.highlights],
            "pivot": float(self.pivot),
        }


@dataclass(frozen=True)
class HueCurveSet:
    """Hue vs Hue/Sat/Luma controls using hue-degree control points."""

    hue_vs_hue: tuple[tuple[float, float], ...] = ()
    hue_vs_sat: tuple[tuple[float, float], ...] = ()
    hue_vs_luma: tuple[tuple[float, float], ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "HueCurveSet":
        data = data or {}

        def _points(value: Any) -> tuple[tuple[float, float], ...]:
            out: list[tuple[float, float]] = []
            for raw in value or []:
                try:
                    x, y = raw
                    out.append((float(x) % 360.0, float(y)))
                except Exception:
                    continue
            return tuple(sorted(out, key=lambda p: p[0]))

        return cls(
            hue_vs_hue=_points(data.get("hue_vs_hue")),
            hue_vs_sat=_points(data.get("hue_vs_sat")),
            hue_vs_luma=_points(data.get("hue_vs_luma")),
        )

    def has_controls(self) -> bool:
        return bool(self.hue_vs_hue or self.hue_vs_sat or self.hue_vs_luma)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hue_vs_hue": [[float(x), float(y)] for x, y in self.hue_vs_hue],
            "hue_vs_sat": [[float(x), float(y)] for x, y in self.hue_vs_sat],
            "hue_vs_luma": [[float(x), float(y)] for x, y in self.hue_vs_luma],
        }


@dataclass(frozen=True)
class ColorWarperPoint:
    """A color-warper control point in hue/saturation space."""

    hue: float
    saturation: float
    hue_shift: float = 0.0
    sat_scale: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColorWarperPoint":
        return cls(
            hue=float(data.get("hue", 0.0)) % 360.0,
            saturation=max(0.0, min(1.0, float(data.get("saturation", 1.0)))),
            hue_shift=float(data.get("hue_shift", 0.0)),
            sat_scale=max(0.0, float(data.get("sat_scale", 1.0))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hue": float(self.hue),
            "saturation": float(self.saturation),
            "hue_shift": float(self.hue_shift),
            "sat_scale": float(self.sat_scale),
        }


@dataclass(frozen=True)
class AdvancedColorToolset:
    """Container for Resolve-style color-page controls."""

    processing_bits: int = 32
    yrgb: bool = True
    hdr_zones: HDRZoneControl = field(default_factory=HDRZoneControl)
    log_wheels: LogWheelSet = field(default_factory=LogWheelSet)
    hue_curves: HueCurveSet = field(default_factory=HueCurveSet)
    warper_points: tuple[ColorWarperPoint, ...] = ()
    gallery_stills: tuple[str, ...] = ()
    shot_match_reference: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AdvancedColorToolset":
        data = data or {}
        points = []
        for raw in data.get("warper_points", []) or []:
            if isinstance(raw, dict):
                points.append(ColorWarperPoint.from_dict(raw))
        return cls(
            processing_bits=int(data.get("processing_bits", 32) or 32),
            yrgb=bool(data.get("yrgb", True)),
            hdr_zones=HDRZoneControl.from_dict(data.get("hdr_zones")),
            log_wheels=LogWheelSet.from_dict(data.get("log_wheels")),
            hue_curves=HueCurveSet.from_dict(data.get("hue_curves")),
            warper_points=tuple(points),
            gallery_stills=tuple(str(v) for v in data.get("gallery_stills", []) or [] if str(v)),
            shot_match_reference=str(data.get("shot_match_reference", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "processing_bits": int(self.processing_bits),
            "yrgb": bool(self.yrgb),
            "hdr_zones": self.hdr_zones.to_dict(),
            "log_wheels": self.log_wheels.to_dict(),
            "hue_curves": self.hue_curves.to_dict(),
            "warper_points": [point.to_dict() for point in self.warper_points],
            "gallery_stills": list(self.gallery_stills),
            "shot_match_reference": str(self.shot_match_reference),
        }


@dataclass(frozen=True)
class ColorProcessingPipeline:
    """Explicit internal color pipeline contract for preview/export parity."""

    processing_bits: int = 32
    internal_model: str = "scene-linear-yrgb"
    input_space: str = "Rec.709"
    working_space: str = "ACEScg"
    output_space: str = "Rec.709"
    output_transfer: str = "gamma24"
    gamut_mapping: str = "perceptual"
    display_transform: str = "view"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ColorProcessingPipeline":
        data = data or {}
        return cls(
            processing_bits=int(data.get("processing_bits", 32) or 32),
            internal_model=str(data.get("internal_model", "scene-linear-yrgb") or "scene-linear-yrgb"),
            input_space=str(data.get("input_space", "Rec.709") or "Rec.709"),
            working_space=str(data.get("working_space", "ACEScg") or "ACEScg"),
            output_space=str(data.get("output_space", "Rec.709") or "Rec.709"),
            output_transfer=str(data.get("output_transfer", "gamma24") or "gamma24"),
            gamut_mapping=str(data.get("gamut_mapping", "perceptual") or "perceptual"),
            display_transform=str(data.get("display_transform", "view") or "view"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "processing_bits": int(self.processing_bits),
            "internal_model": str(self.internal_model),
            "input_space": str(self.input_space),
            "working_space": str(self.working_space),
            "output_space": str(self.output_space),
            "output_transfer": str(self.output_transfer),
            "gamut_mapping": str(self.gamut_mapping),
            "display_transform": str(self.display_transform),
        }

    def validation_warnings(self) -> list[str]:
        warnings: list[str] = []
        if int(self.processing_bits) < 32:
            warnings.append("processing_bits must be 32 or higher for professional color parity")
        if "linear" not in self.internal_model.casefold() and "yrgb" not in self.internal_model.casefold():
            warnings.append("internal_model should declare scene-linear or YRGB processing")
        if self.working_space.casefold().startswith("aces") and not self.output_space:
            warnings.append("ACES working space needs an explicit output space")
        if self.output_transfer.casefold() in {"pq", "hlg"} and "2020" not in self.output_space.casefold():
            warnings.append("HDR transfer should target a wide-gamut output space")
        return warnings


@dataclass(frozen=True)
class CameraRawControls:
    """Non-destructive camera RAW sidecar controls."""

    enabled: bool = True
    iso: int = 800
    white_balance_kelvin: int = 5600
    tint: float = 0.0
    exposure: float = 0.0
    highlight_recovery: float = 0.5
    debayer_quality: str = "full"
    decode_quality: str = "full"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CameraRawControls":
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", True)),
            iso=max(25, int(data.get("iso", 800) or 800)),
            white_balance_kelvin=max(1500, min(50000, int(data.get("white_balance_kelvin", data.get("wb_kelvin", 5600)) or 5600))),
            tint=float(data.get("tint", 0.0) or 0.0),
            exposure=float(data.get("exposure", 0.0) or 0.0),
            highlight_recovery=max(0.0, min(1.0, float(data.get("highlight_recovery", 0.5) or 0.5))),
            debayer_quality=str(data.get("debayer_quality", "full") or "full"),
            decode_quality=str(data.get("decode_quality", "full") or "full"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "iso": int(self.iso),
            "white_balance_kelvin": int(self.white_balance_kelvin),
            "tint": float(self.tint),
            "exposure": float(self.exposure),
            "highlight_recovery": float(self.highlight_recovery),
            "debayer_quality": str(self.debayer_quality),
            "decode_quality": str(self.decode_quality),
            "non_destructive": True,
        }


@dataclass(frozen=True)
class HDRDeliveryMetadata:
    """HDR10+/Dolby Vision style metadata authoring payload."""

    standard: str = "hdr10plus"
    mastering_display: str = "P3-D65/1000nit"
    max_cll: int = 1000
    max_fall: int = 400
    tone_mapping: str = "st2084"
    dynamic_metadata: bool = True
    validation_profile: str = "delivery"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "HDRDeliveryMetadata":
        data = data or {}
        return cls(
            standard=str(data.get("standard", "hdr10plus") or "hdr10plus").casefold(),
            mastering_display=str(data.get("mastering_display", "P3-D65/1000nit") or "P3-D65/1000nit"),
            max_cll=max(1, int(data.get("max_cll", 1000) or 1000)),
            max_fall=max(1, int(data.get("max_fall", 400) or 400)),
            tone_mapping=str(data.get("tone_mapping", "st2084") or "st2084").casefold(),
            dynamic_metadata=bool(data.get("dynamic_metadata", True)),
            validation_profile=str(data.get("validation_profile", "delivery") or "delivery"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "standard": str(self.standard),
            "mastering_display": str(self.mastering_display),
            "max_cll": int(self.max_cll),
            "max_fall": int(self.max_fall),
            "tone_mapping": str(self.tone_mapping),
            "dynamic_metadata": bool(self.dynamic_metadata),
            "validation_profile": str(self.validation_profile),
        }

    def validation_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.standard not in {"hdr10", "hdr10plus", "dolby_vision"}:
            warnings.append(f"unsupported HDR standard: {self.standard}")
        if self.max_fall > self.max_cll:
            warnings.append("max_fall should not exceed max_cll")
        if self.standard in {"hdr10plus", "dolby_vision"} and not self.dynamic_metadata:
            warnings.append("dynamic metadata is expected for HDR10+/Dolby Vision")
        if self.tone_mapping not in {"st2084", "pq", "hlg"}:
            warnings.append("tone_mapping should be ST.2084/PQ or HLG")
        return warnings


@dataclass(frozen=True)
class ColorNodeRenderPlan:
    """Serial/parallel/layer/shared node topology and render order."""

    nodes: tuple[dict[str, Any], ...] = ()
    topology: str = "serial"
    shared_node_ids: tuple[str, ...] = ()
    output_node: str = "out"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ColorNodeRenderPlan":
        data = data or {}
        return cls(
            nodes=tuple(dict(row) for row in data.get("nodes", []) or [] if isinstance(row, dict)),
            topology=str(data.get("topology", "serial") or "serial"),
            shared_node_ids=tuple(str(v) for v in data.get("shared_node_ids", []) or [] if str(v)),
            output_node=str(data.get("output_node", "out") or "out"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [dict(row) for row in self.nodes],
            "topology": str(self.topology),
            "shared_node_ids": list(self.shared_node_ids),
            "output_node": str(self.output_node),
            "render_order": self.render_order(),
        }

    def render_order(self) -> list[str]:
        ids = [str(row.get("id") or f"node_{idx + 1}") for idx, row in enumerate(self.nodes)]
        if self.output_node not in ids:
            ids.append(self.output_node)
        return ids

    def validation_warnings(self) -> list[str]:
        ids = [str(row.get("id") or "") for row in self.nodes]
        warnings: list[str] = []
        if len(ids) != len(set(ids)):
            warnings.append("color node ids must be unique")
        for row in self.nodes:
            for input_id in row.get("inputs", []) or []:
                if str(input_id) not in ids:
                    warnings.append(f"node {row.get('id', '?')} input missing: {input_id}")
        if self.topology not in {"serial", "parallel", "layer", "shared"}:
            warnings.append(f"unsupported color node topology: {self.topology}")
        return warnings


@dataclass(frozen=True)
class RestorationFXPlan:
    temporal_nr: float = 0.0
    spatial_nr: float = 0.0
    film_grain: float = 0.0
    deflicker: bool = False
    dead_pixel_repair: bool = False
    dust_dirt_removal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "temporal_nr": max(0.0, min(1.0, float(self.temporal_nr))),
            "spatial_nr": max(0.0, min(1.0, float(self.spatial_nr))),
            "film_grain": max(0.0, min(1.0, float(self.film_grain))),
            "deflicker": bool(self.deflicker),
            "dead_pixel_repair": bool(self.dead_pixel_repair),
            "dust_dirt_removal": bool(self.dust_dirt_removal),
        }


def build_professional_color_pipeline_payload(
    *,
    pipeline: ColorProcessingPipeline | dict[str, Any] | None = None,
    raw: CameraRawControls | dict[str, Any] | None = None,
    hdr_metadata: HDRDeliveryMetadata | dict[str, Any] | None = None,
    node_plan: ColorNodeRenderPlan | dict[str, Any] | None = None,
    restoration: RestorationFXPlan | dict[str, Any] | None = None,
    advanced_toolset: AdvancedColorToolset | dict[str, Any] | None = None,
    secondary_workflow: ColorNodeWorkflow | dict[str, Any] | None = None,
) -> dict[str, Any]:
    p = pipeline if isinstance(pipeline, ColorProcessingPipeline) else ColorProcessingPipeline.from_dict(pipeline)
    r = raw if isinstance(raw, CameraRawControls) else CameraRawControls.from_dict(raw)
    h = hdr_metadata if isinstance(hdr_metadata, HDRDeliveryMetadata) else HDRDeliveryMetadata.from_dict(hdr_metadata)
    n = node_plan if isinstance(node_plan, ColorNodeRenderPlan) else ColorNodeRenderPlan.from_dict(node_plan or {
        "topology": "parallel",
        "nodes": [
            {"id": "input", "kind": "input"},
            {"id": "primary", "kind": "primary", "inputs": ["input"]},
            {"id": "secondary", "kind": "secondary", "inputs": ["primary"]},
        ],
        "output_node": "out",
        "shared_node_ids": ["primary"],
    })
    rest = restoration if isinstance(restoration, RestorationFXPlan) else RestorationFXPlan(**(restoration or {}))
    toolset = advanced_toolset if isinstance(advanced_toolset, AdvancedColorToolset) else AdvancedColorToolset.from_dict(advanced_toolset or {
        "hdr_zones": {
            "enabled": True,
            "shadow": 4.0,
            "dark": 2.0,
            "light": 3.0,
            "highlight": -3.0,
            "specular": -6.0,
            "pivot": 0.55,
        },
        "log_wheels": {
            "shadows": [-0.020, 0.006, 0.018],
            "midtones": [0.012, 0.004, -0.006],
            "highlights": [0.018, 0.010, -0.012],
            "pivot": 0.48,
        },
        "hue_curves": {
            "hue_vs_hue": [[32.0, 2.0], [210.0, -3.0]],
            "hue_vs_sat": [[32.0, 0.08], [210.0, -0.05]],
            "hue_vs_luma": [[32.0, 0.05], [210.0, -0.04]],
        },
        "warper_points": [
            {"hue": 32.0, "saturation": 0.62, "hue_shift": 1.5, "sat_scale": 1.05},
            {"hue": 210.0, "saturation": 0.50, "hue_shift": -2.0, "sat_scale": 0.96},
        ],
        "gallery_stills": ["balanced_skin_reference", "hero_wide_gamut_reference"],
        "shot_match_reference": "balanced_skin_reference",
    })
    secondary = secondary_workflow if isinstance(secondary_workflow, ColorNodeWorkflow) else ColorNodeWorkflow.from_dict(secondary_workflow or {
        "enabled": True,
        "name": "Tracked skin/object secondary",
        "qualifier": {
            "enabled": True,
            "hue_center": 32.0,
            "hue_width": 38.0,
            "sat_min": 0.12,
            "sat_max": 0.92,
            "val_min": 0.08,
            "val_max": 1.0,
            "softness": 0.16,
            "clean_black": 0.18,
            "clean_white": 0.12,
            "denoise_radius": 2,
        },
        "window": {
            "enabled": True,
            "shape": "ellipse",
            "x": 0.5,
            "y": 0.48,
            "w": 0.42,
            "h": 0.52,
            "feather": 0.18,
            "opacity": 0.85,
            "track_object": True,
            "tracking_status": "tracked",
            "tracker_id": "professional_secondary_01",
        },
        "curves": {
            "master": [[0, 0], [80, 84], [170, 176], [255, 255]],
            "red": [[0, 0], [128, 132], [255, 255]],
            "green": [[0, 0], [128, 128], [255, 255]],
            "blue": [[0, 0], [128, 124], [255, 255]],
        },
        "opacity": 0.82,
    })
    return {
        "schema": 1,
        "color_processing_pipeline": p.to_dict(),
        "camera_raw": r.to_dict(),
        "hdr_delivery_metadata": h.to_dict(),
        "color_node_render_plan": n.to_dict(),
        "restoration_fx": rest.to_dict(),
        "advanced_color_toolset": toolset.to_dict(),
        "color_workflow": secondary.to_dict(),
        "beauty_repair": {
            "face_refinement": {
                "enabled": True,
                "local_ml_feature": "face_recognition",
                "skin_smoothing": 0.18,
                "eye_light": 0.08,
                "mouth_detail": 0.06,
            },
            "skin_retouch": {
                "enabled": True,
                "preserve_texture": True,
                "amount": 0.22,
            },
            "object_removal": {
                "enabled": True,
                "local_ml_feature": "object_detection",
                "repair_mode": "patch_replace",
            },
            "patch_replacer": {
                "enabled": True,
                "source": "clean_plate",
                "edge_feather": 0.18,
            },
        },
        "product_capabilities": {
            "color": {
                "float_processing_bits": p.processing_bits,
                "float_pipeline": p.processing_bits >= 32,
                "yrgb": "yrgb" in p.internal_model.casefold(),
                "wide_gamut": True,
                "camera_raw": bool(r.enabled),
                "raw_controls": True,
                "hdr_wheels": toolset.hdr_zones.enabled,
                "zone_tone_controls": toolset.hdr_zones.enabled,
                "st2084_tonemap": h.tone_mapping in {"st2084", "pq"},
                "hlg_tonemap": h.tone_mapping == "hlg",
                "hdr10plus_metadata": h.standard in {"hdr10plus", "dolby_vision"},
                "dolby_vision_metadata": h.standard == "dolby_vision",
                "hdr_metadata_model": True,
                "log_wheels": True,
                "hue_vs_hue": bool(toolset.hue_curves.hue_vs_hue),
                "hue_vs_sat": bool(toolset.hue_curves.hue_vs_sat),
                "hue_vs_luma": bool(toolset.hue_curves.hue_vs_luma),
                "color_warper": bool(toolset.warper_points),
                "parallel_nodes": n.topology in {"parallel", "layer", "shared"},
                "layer_nodes": n.topology in {"layer", "shared"},
                "shared_nodes": bool(n.shared_node_ids),
                "secondary_grading_model": True,
                "tracking_window_model": True,
                "qualifier_cleanup": bool(secondary.qualifier.clean_black or secondary.qualifier.clean_white or secondary.qualifier.denoise_radius),
                "face_refinement": True,
                "skin_retouching": True,
                "object_removal": True,
                "patch_replacer": True,
                "beauty_repair_model": True,
                "object_repair_model": True,
                "temporal_nr": rest.temporal_nr > 0.0,
                "spatial_nr": rest.spatial_nr > 0.0,
                "film_grain": rest.film_grain > 0.0,
                "deflicker": rest.deflicker,
                "dust_dirt_removal": rest.dust_dirt_removal,
                "gallery_stills": bool(toolset.gallery_stills),
                "shot_match": bool(toolset.shot_match_reference),
                "split_screen": True,
                "lightbox": True,
                "waveform": True,
                "parade": True,
                "vectorscope": True,
                "histogram": True,
            }
        },
    }


def professional_color_pipeline_report(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(payload or build_professional_color_pipeline_payload(
        hdr_metadata={"standard": "dolby_vision", "dynamic_metadata": True},
        restoration={"temporal_nr": 0.35, "spatial_nr": 0.25, "film_grain": 0.18, "deflicker": True, "dead_pixel_repair": True, "dust_dirt_removal": True},
    ))
    pipeline = ColorProcessingPipeline.from_dict(payload.get("color_processing_pipeline"))
    raw = CameraRawControls.from_dict(payload.get("camera_raw"))
    hdr = HDRDeliveryMetadata.from_dict(payload.get("hdr_delivery_metadata"))
    node_plan = ColorNodeRenderPlan.from_dict(payload.get("color_node_render_plan"))
    toolset = AdvancedColorToolset.from_dict(payload.get("advanced_color_toolset"))
    secondary = ColorNodeWorkflow.from_dict(payload.get("color_workflow"))
    restoration = dict(payload.get("restoration_fx") or {})
    beauty = dict(payload.get("beauty_repair") or {})
    checks = {
        "float_scene_linear": pipeline.processing_bits >= 32 and ("linear" in pipeline.internal_model.casefold() or "yrgb" in pipeline.internal_model.casefold()),
        "raw_sidecar": bool(raw.enabled and raw.to_dict().get("non_destructive")),
        "hdr_metadata_valid": not hdr.validation_warnings(),
        "node_render_order": bool(node_plan.render_order()) and not node_plan.validation_warnings(),
        "advanced_toolset": bool(toolset.hdr_zones.enabled and toolset.hue_curves.has_controls() and toolset.warper_points),
        "secondary_tracking": bool(secondary.qualifier.enabled and secondary.window.enabled and secondary.window.track_object),
        "beauty_repair": all(bool(dict(beauty.get(key) or {}).get("enabled")) for key in ("face_refinement", "skin_retouch", "object_removal", "patch_replacer")),
        "restoration_payload": any(bool(value) for value in restoration.values()),
    }
    warnings = pipeline.validation_warnings() + hdr.validation_warnings() + node_plan.validation_warnings()
    return {
        "ok": all(checks.values()) and not warnings,
        "checks": checks,
        "warnings": warnings,
        "payload": payload,
        "summary": {
            "processing_bits": pipeline.processing_bits,
            "internal_model": pipeline.internal_model,
            "raw_iso": raw.iso,
            "hdr_standard": hdr.standard,
            "node_topology": node_plan.topology,
            "hue_curve_sets": sum(1 for row in (toolset.hue_curves.hue_vs_hue, toolset.hue_curves.hue_vs_sat, toolset.hue_curves.hue_vs_luma) if row),
            "warper_points": len(toolset.warper_points),
            "secondary_tracker": secondary.window.tracker_id,
            "beauty_repair_tools": sum(1 for value in beauty.values() if isinstance(value, dict) and value.get("enabled")),
            "restoration_tools": sum(1 for value in restoration.values() if bool(value)),
        },
    }


def apply_curves(rgb: np.ndarray, curves: CurveSet | dict[str, Any]) -> np.ndarray:
    curves = CurveSet.from_dict(curves) if isinstance(curves, dict) else curves
    if curves.is_identity():
        return rgb
    out = rgb.copy()
    master = curves.master.lut()
    red = curves.red.lut()
    green = curves.green.lut()
    blue = curves.blue.lut()
    out[..., 0] = red[master[out[..., 0]]]
    out[..., 1] = green[master[out[..., 1]]]
    out[..., 2] = blue[master[out[..., 2]]]
    return out


def apply_hdr_zone_tone(rgb: np.ndarray, zones: HDRZoneControl | dict[str, Any]) -> np.ndarray:
    """Apply simple zone-based tone offsets in float space."""
    z = HDRZoneControl.from_dict(zones) if isinstance(zones, dict) else zones
    if not z.enabled:
        return rgb
    arr = rgb.astype(np.float32) / 255.0
    luma = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    controls = (
        (0.00, 0.08, z.black),
        (0.05, 0.25, z.shadow),
        (0.18, max(0.2, z.pivot), z.dark),
        (min(0.8, z.pivot), 0.85, z.light),
        (0.70, 0.96, z.highlight),
        (0.88, 1.00, z.specular),
    )
    delta = np.zeros_like(luma, dtype=np.float32)
    for low, high, amount in controls:
        if abs(float(amount)) < 1e-6:
            continue
        center = (low + high) * 0.5
        radius = max(1e-6, (high - low) * 0.5)
        weight = np.clip(1.0 - np.abs(luma - center) / radius, 0.0, 1.0)
        delta += weight * (float(amount) / 100.0)
    out = np.clip(arr + delta[..., None], 0.0, 1.0)
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)


def apply_log_wheels(rgb: np.ndarray, wheels: LogWheelSet | dict[str, Any]) -> np.ndarray:
    """Apply lightweight log-wheel RGB offsets by luminance region."""
    w = LogWheelSet.from_dict(wheels) if isinstance(wheels, dict) else wheels
    arr = rgb.astype(np.float32) / 255.0
    luma = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    shadow_w = np.clip((float(w.pivot) - luma) / max(1e-6, float(w.pivot)), 0.0, 1.0)
    high_w = np.clip((luma - float(w.pivot)) / max(1e-6, 1.0 - float(w.pivot)), 0.0, 1.0)
    mid_w = np.clip(1.0 - np.maximum(shadow_w, high_w), 0.0, 1.0)
    delta = (
        shadow_w[..., None] * np.array(w.shadows, dtype=np.float32)
        + mid_w[..., None] * np.array(w.midtones, dtype=np.float32)
        + high_w[..., None] * np.array(w.highlights, dtype=np.float32)
    )
    out = np.clip(arr + delta, 0.0, 1.0)
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)


def apply_hue_curves(rgb: np.ndarray, curves: HueCurveSet | dict[str, Any]) -> np.ndarray:
    """Apply Hue vs Hue/Sat/Luma controls using HSV conversion."""
    c = HueCurveSet.from_dict(curves) if isinstance(curves, dict) else curves
    if not c.has_controls():
        return rgb
    hue, sat, val = _rgb_to_hsv_numpy(rgb)
    if c.hue_vs_hue:
        hue = (hue + _interp_hue_controls(hue, c.hue_vs_hue)) % 360.0
    if c.hue_vs_sat:
        sat = np.clip(sat * (1.0 + _interp_hue_controls(hue, c.hue_vs_sat)), 0.0, 1.0)
    if c.hue_vs_luma:
        val = np.clip(val + _interp_hue_controls(hue, c.hue_vs_luma), 0.0, 1.0)
    return _hsv_to_rgb_numpy(hue, sat, val)


def apply_color_warper(rgb: np.ndarray, points: Iterable[ColorWarperPoint | dict[str, Any]]) -> np.ndarray:
    """Apply broad color-warper point influences in hue/sat space."""
    controls: list[ColorWarperPoint] = []
    for raw in points or []:
        if isinstance(raw, ColorWarperPoint):
            controls.append(raw)
        elif isinstance(raw, dict):
            controls.append(ColorWarperPoint.from_dict(raw))
    if not controls:
        return rgb
    hue, sat, val = _rgb_to_hsv_numpy(rgb)
    hue_shift = np.zeros_like(hue, dtype=np.float32)
    sat_scale = np.ones_like(sat, dtype=np.float32)
    for point in controls:
        hue_delta = np.abs(((hue - point.hue + 180.0) % 360.0) - 180.0)
        sat_delta = np.abs(sat - point.saturation)
        weight = np.clip(1.0 - hue_delta / 55.0, 0.0, 1.0) * np.clip(1.0 - sat_delta / 0.45, 0.0, 1.0)
        hue_shift += weight * float(point.hue_shift)
        sat_scale += weight * (float(point.sat_scale) - 1.0)
    return _hsv_to_rgb_numpy((hue + hue_shift) % 360.0, np.clip(sat * sat_scale, 0.0, 1.0), val)


def apply_advanced_color_toolset(rgb: np.ndarray, toolset: AdvancedColorToolset | dict[str, Any]) -> np.ndarray:
    """Apply the current subset of advanced color-page controls."""
    t = AdvancedColorToolset.from_dict(toolset) if isinstance(toolset, dict) else toolset
    out = rgb
    out = apply_hdr_zone_tone(out, t.hdr_zones)
    out = apply_log_wheels(out, t.log_wheels)
    out = apply_hue_curves(out, t.hue_curves)
    out = apply_color_warper(out, t.warper_points)
    return out


def advanced_color_product_capabilities() -> dict[str, Any]:
    """Return built-in color capabilities exposed to readiness/QA."""
    return {
        "float_processing_bits": 32,
        "yrgb": True,
        "wide_gamut": True,
        "hdr_wheels": True,
        "zone_tone_controls": True,
        "st2084_tonemap": True,
        "hlg_tonemap": True,
        "log_wheels": True,
        "hue_vs_hue": True,
        "hue_vs_sat": True,
        "hue_vs_luma": True,
        "color_warper": True,
        "serial_nodes": True,
        "waveform": True,
        "parade": True,
        "vectorscope": True,
        "histogram": True,
        "gallery_stills": True,
        "shot_match": True,
        "split_screen": True,
        "lightbox": True,
        "lut_pipeline": True,
        "scope_accuracy_qa": True,
        "raw_sidecar_model": True,
        "camera_raw": True,
        "raw_controls": True,
        "hdr_metadata_model": True,
        "hdr10plus_metadata": True,
        "dolby_vision_metadata": True,
        "node_grading_model": True,
        "parallel_nodes": True,
        "layer_nodes": True,
        "shared_nodes": True,
        "secondary_grading_model": True,
        "tracking_window_model": True,
        "beauty_repair_model": True,
        "object_repair_model": True,
        "restoration_fx_model": True,
        "temporal_nr": True,
        "spatial_nr": True,
        "film_grain": True,
        "deflicker": True,
        "dust_dirt_removal": True,
        "panel_mapping_model": True,
        "external_monitoring_model": True,
    }


def qualifier_mask(rgb: np.ndarray, qualifier: ColorQualifier | dict[str, Any]) -> np.ndarray:
    q = ColorQualifier.from_dict(qualifier) if isinstance(qualifier, dict) else qualifier
    if not q.enabled:
        return np.ones(rgb.shape[:2], dtype=np.float32)
    try:
        import cv2

        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
        hue = hsv[..., 0] * 2.0
        sat = hsv[..., 1] / 255.0
        val = hsv[..., 2] / 255.0
    except Exception:
        hue, sat, val = _rgb_to_hsv_numpy(rgb)

    hue_delta = np.abs(((hue - q.hue_center + 180.0) % 360.0) - 180.0)
    hue_inner = max(0.0, q.hue_width)
    softness = max(1e-6, q.softness)
    hue_alpha = 1.0 - np.clip((hue_delta - hue_inner) / (softness * 180.0), 0.0, 1.0)
    sat_alpha = _range_soft_mask(sat, q.sat_min, q.sat_max, softness)
    val_alpha = _range_soft_mask(val, q.val_min, q.val_max, softness)
    mask = (hue_alpha * sat_alpha * val_alpha).astype(np.float32)
    if q.invert:
        mask = 1.0 - mask
    mask = _clean_qualifier_mask(mask, q)
    return np.clip(mask, 0.0, 1.0)


def window_mask(shape: tuple[int, int], window: TrackingWindow | dict[str, Any]) -> np.ndarray:
    win = TrackingWindow.from_dict(window) if isinstance(window, dict) else window
    h, w = int(shape[0]), int(shape[1])
    if not win.enabled or h <= 0 or w <= 0:
        return np.ones((h, w), dtype=np.float32)
    yy, xx = np.indices((h, w), dtype=np.float32)
    cx = win.x * w
    cy = win.y * h
    rw = max(1.0, win.w * w * 0.5)
    rh = max(1.0, win.h * h * 0.5)
    if win.shape.lower().startswith("rect"):
        dx = np.maximum(np.abs(xx - cx) - rw, 0.0) / max(1.0, rw)
        dy = np.maximum(np.abs(yy - cy) - rh, 0.0) / max(1.0, rh)
        dist = np.maximum(dx, dy)
        inside = ((np.abs(xx - cx) <= rw) & (np.abs(yy - cy) <= rh)).astype(np.float32)
    else:
        dist = np.sqrt(((xx - cx) / rw) ** 2 + ((yy - cy) / rh) ** 2)
        inside = (dist <= 1.0).astype(np.float32)
    feather = max(1e-6, float(win.feather))
    soft = 1.0 - np.clip((dist - 1.0) / feather, 0.0, 1.0)
    mask = np.maximum(inside, soft)
    return np.clip(mask * max(0.0, min(1.0, win.opacity)), 0.0, 1.0).astype(np.float32)


def combined_node_mask(rgb: np.ndarray, node: ColorNodeWorkflow | dict[str, Any]) -> np.ndarray:
    n = ColorNodeWorkflow.from_dict(node) if isinstance(node, dict) else node
    if not n.enabled:
        return np.zeros(rgb.shape[:2], dtype=np.float32)
    mask = qualifier_mask(rgb, n.qualifier) * window_mask(rgb.shape[:2], n.window)
    return np.clip(mask * max(0.0, min(1.0, n.opacity)), 0.0, 1.0)


def apply_color_node_workflow(
    rgb: np.ndarray,
    grade: Any,
    node: ColorNodeWorkflow | dict[str, Any],
) -> np.ndarray:
    """Apply grade/curves through qualifier and window masks."""
    from app.color_grading import apply_to_rgb

    n = ColorNodeWorkflow.from_dict(node) if isinstance(node, dict) else node
    if not n.enabled:
        return rgb
    graded = apply_to_rgb(rgb, grade)
    graded = apply_curves(graded, n.curves)
    mask = combined_node_mask(rgb, n)
    if np.all(mask >= 0.999):
        return graded
    f = rgb.astype(np.float32)
    g = graded.astype(np.float32)
    out = f * (1.0 - mask[..., None]) + g * mask[..., None]
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def scope_diagnostics(rgb: np.ndarray) -> dict[str, Any]:
    """Return compact numeric scope data for UI badges and QA reports."""
    arr = rgb.astype(np.float32) / 255.0
    luma = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    channel_means = arr.reshape(-1, 3).mean(axis=0)
    channel_max = arr.reshape(-1, 3).max(axis=0)
    channel_min = arr.reshape(-1, 3).min(axis=0)
    clipped_shadow = float(np.mean(luma <= 1.0 / 255.0))
    clipped_highlight = float(np.mean(luma >= 254.0 / 255.0))
    sat = arr.max(axis=2) - arr.min(axis=2)
    return {
        "luma_p01": float(np.percentile(luma, 1)),
        "luma_p50": float(np.percentile(luma, 50)),
        "luma_p99": float(np.percentile(luma, 99)),
        "shadow_clip_ratio": clipped_shadow,
        "highlight_clip_ratio": clipped_highlight,
        "saturation_mean": float(np.mean(sat)),
        "rgb_mean": [float(v) for v in channel_means],
        "rgb_min": [float(v) for v in channel_min],
        "rgb_max": [float(v) for v in channel_max],
        "white_balance_bias": [
            float(channel_means[0] - channel_means[1]),
            float(channel_means[2] - channel_means[1]),
        ],
    }


def build_scope_accuracy_sample(width: int = 256, height: int = 144) -> np.ndarray:
    """Return a deterministic synthetic chart for scope/parity QA."""
    w = max(8, int(width))
    h = max(8, int(height))
    chart = np.zeros((h, w, 3), dtype=np.uint8)
    bars = np.array(
        [
            [255, 255, 255],
            [255, 255, 0],
            [0, 255, 255],
            [0, 255, 0],
            [255, 0, 255],
            [255, 0, 0],
            [0, 0, 255],
            [0, 0, 0],
        ],
        dtype=np.uint8,
    )
    bar_w = max(1, w // len(bars))
    for idx, color in enumerate(bars):
        x0 = idx * bar_w
        x1 = w if idx == len(bars) - 1 else min(w, (idx + 1) * bar_w)
        chart[:, x0:x1, :] = color
    ramp_h = max(1, h // 5)
    ramp = np.linspace(0, 255, w, dtype=np.uint8)
    chart[-ramp_h:, :, :] = ramp[None, :, None]
    return chart


def scope_accuracy_report(rgb: np.ndarray | None = None) -> dict[str, Any]:
    """Return a compact QA report for waveform/parade/vectorscope foundations."""
    sample = build_scope_accuracy_sample() if rgb is None else rgb
    diag = scope_diagnostics(sample)
    warnings: list[str] = []
    luma_span = float(diag["luma_p99"]) - float(diag["luma_p01"])
    saturation_mean = float(diag["saturation_mean"])
    rgb_min = [float(v) for v in diag["rgb_min"]]
    rgb_max = [float(v) for v in diag["rgb_max"]]
    if luma_span < 0.80:
        warnings.append("waveform luma span is too narrow for the synthetic chart")
    if saturation_mean < 0.30:
        warnings.append("vectorscope saturation is too low for the synthetic chart")
    if max(rgb_max) < 0.99 or min(rgb_min) > 0.01:
        warnings.append("parade channel extrema do not cover full black/white")
    return {
        "ok": not warnings,
        "sample": "synthetic_color_bars_luma_ramp" if rgb is None else "provided_frame",
        "diagnostics": diag,
        "luma_span": luma_span,
        "saturation_mean": saturation_mean,
        "warnings": warnings,
        "qa_gates": [
            "waveform luma span >= 0.80",
            "vectorscope saturation mean >= 0.30",
            "RGB parade extrema include near-black and near-white",
        ],
    }


def _range_soft_mask(values: np.ndarray, low: float, high: float, softness: float) -> np.ndarray:
    low = max(0.0, min(1.0, float(low)))
    high = max(low, min(1.0, float(high)))
    softness = max(1e-6, float(softness))
    low_alpha = np.ones_like(values, dtype=np.float32) if low <= 0.0 else np.clip((values - low) / softness, 0.0, 1.0)
    high_alpha = np.ones_like(values, dtype=np.float32) if high >= 1.0 else np.clip((high - values) / softness, 0.0, 1.0)
    return np.minimum(low_alpha, high_alpha)


def _clean_qualifier_mask(mask: np.ndarray, qualifier: ColorQualifier) -> np.ndarray:
    """Apply clean black/white and denoise to a qualifier mask."""
    out = np.clip(mask.astype(np.float32, copy=False), 0.0, 1.0)
    clean_black = max(0.0, min(1.0, float(getattr(qualifier, "clean_black", 0.0))))
    clean_white = max(0.0, min(1.0, float(getattr(qualifier, "clean_white", 0.0))))
    if clean_black > 0.0:
        out = np.where(out <= clean_black, 0.0, out)
        if clean_black < 0.999:
            out = np.where(out > clean_black, (out - clean_black) / (1.0 - clean_black), out)
    if clean_white > 0.0:
        threshold = max(0.0, 1.0 - clean_white)
        out = np.where(out >= threshold, 1.0, out)
    radius = int(getattr(qualifier, "denoise_radius", 0) or 0)
    if radius > 0 and out.size:
        k = max(3, radius | 1)
        try:
            import cv2

            out_u8 = np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)
            out = cv2.medianBlur(out_u8, k).astype(np.float32) / 255.0
        except Exception:
            # Tiny numpy fallback: a single 3x3 majority-style blur.  It is
            # intentionally conservative so export remains deterministic even
            # without OpenCV.
            padded = np.pad(out, 1, mode="edge")
            acc = np.zeros_like(out)
            for dy in range(3):
                for dx in range(3):
                    acc += padded[dy:dy + out.shape[0], dx:dx + out.shape[1]]
            out = acc / 9.0
    return out.astype(np.float32)


def _rgb_to_hsv_numpy(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    arr = rgb.astype(np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin
    hue = np.zeros_like(cmax)
    mask = delta > 1e-6
    rmask = mask & (cmax == r)
    gmask = mask & (cmax == g) & ~rmask
    bmask = mask & (cmax == b) & ~rmask & ~gmask
    hue[rmask] = ((g[rmask] - b[rmask]) / delta[rmask]) % 6.0
    hue[gmask] = (b[gmask] - r[gmask]) / delta[gmask] + 2.0
    hue[bmask] = (r[bmask] - g[bmask]) / delta[bmask] + 4.0
    hue *= 60.0
    sat = np.where(cmax > 1e-6, delta / np.maximum(cmax, 1e-6), 0.0)
    return hue, sat, cmax


def _hsv_to_rgb_numpy(hue: np.ndarray, sat: np.ndarray, val: np.ndarray) -> np.ndarray:
    h = (hue.astype(np.float32) % 360.0) / 60.0
    s = np.clip(sat.astype(np.float32), 0.0, 1.0)
    v = np.clip(val.astype(np.float32), 0.0, 1.0)
    c = v * s
    x = c * (1.0 - np.abs((h % 2.0) - 1.0))
    m = v - c
    zeros = np.zeros_like(h)
    rp = np.select(
        [h < 1, h < 2, h < 3, h < 4, h < 5, h <= 6],
        [c, x, zeros, zeros, x, c],
        default=zeros,
    )
    gp = np.select(
        [h < 1, h < 2, h < 3, h < 4, h < 5, h <= 6],
        [x, c, c, x, zeros, zeros],
        default=zeros,
    )
    bp = np.select(
        [h < 1, h < 2, h < 3, h < 4, h < 5, h <= 6],
        [zeros, zeros, x, c, c, x],
        default=zeros,
    )
    out = np.stack([rp + m, gp + m, bp + m], axis=-1)
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _interp_hue_controls(hue: np.ndarray, points: tuple[tuple[float, float], ...]) -> np.ndarray:
    if not points:
        return np.zeros_like(hue, dtype=np.float32)
    pts = sorted((float(x) % 360.0, float(y)) for x, y in points)
    xs = np.array([p[0] for p in pts], dtype=np.float32)
    ys = np.array([p[1] for p in pts], dtype=np.float32)
    xs_wrap = np.concatenate(([xs[-1] - 360.0], xs, [xs[0] + 360.0]))
    ys_wrap = np.concatenate(([ys[-1]], ys, [ys[0]]))
    flat = (hue.astype(np.float32) % 360.0).reshape(-1)
    values = np.interp(flat, xs_wrap, ys_wrap)
    return values.reshape(hue.shape).astype(np.float32)
