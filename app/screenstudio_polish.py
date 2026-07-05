"""Screen-recording polish helpers.

The editor already has renderable ZoomActor support.  This module turns
cursor/click metadata into those actors and keeps the cursor/background style
payload in a small JSON-friendly shape so preview/export paths can consume it
incrementally.
"""
from __future__ import annotations

import json
import math
import hashlib
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


def _clamp(value: float, low: float, high: float) -> float:
    if high < low:
        return low
    return max(low, min(high, value))


def _smoothstep(value: float) -> float:
    t = _clamp(float(value), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _ease_out_cubic(value: float) -> float:
    t = _clamp(float(value), 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 3


def _ease_out_back(value: float) -> float:
    t = _clamp(float(value), 0.0, 1.0)
    c1 = 1.70158
    c3 = c1 + 1.0
    return _clamp(1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2, 0.0, 1.12)


_CURSOR_ROLE_FX: dict[str, tuple[str, str]] = {
    "blade": ("scissors", "snip"),
    "blade_tool": ("scissors", "snip"),
    "cut": ("scissors", "snip"),
    "cut_tool": ("scissors", "snip"),
    "split": ("scissors", "snip"),
    "split_tool": ("scissors", "snip"),
    "select": ("pointer", "click_pop"),
    "select_tool": ("pointer", "click_pop"),
    "button": ("hand", "hover_breathe"),
    "primary_button": ("hand", "click_pop"),
    "text": ("ibeam", "text_focus"),
    "text_field": ("ibeam", "text_focus"),
    "caption": ("ibeam", "text_focus"),
    "title": ("ibeam", "text_focus"),
    "zoom": ("zoom", "zoom_pulse"),
    "zoom_tool": ("zoom", "zoom_pulse"),
    "auto_zoom": ("zoom", "zoom_pulse"),
    "drag": ("grab", "drag_trail"),
    "drag_handle": ("grab", "drag_trail"),
    "slider": ("grab", "drag_trail"),
    "trim": ("trim", "trim_nudge"),
    "trim_left": ("trim_left", "trim_nudge"),
    "trim_right": ("trim_right", "trim_nudge"),
    "ripple": ("trim", "trim_nudge"),
    "roll": ("trim", "trim_nudge"),
    "slip": ("slide", "slide_nudge"),
    "slide": ("slide", "slide_nudge"),
    "color": ("color_picker", "pick"),
    "color_picker": ("color_picker", "pick"),
    "ai": ("magic_ai", "spark"),
    "magic": ("magic_ai", "spark"),
}


_CURSOR_STYLE_ALIASES: dict[str, str] = {
    "arrow": "pointer",
    "default": "pointer",
    "pointing_hand": "hand",
    "hand_point": "hand",
    "scissor": "scissors",
    "cut": "scissors",
    "blade": "scissors",
    "text": "ibeam",
    "i-beam": "ibeam",
    "size_all": "grab",
    "grabbed": "grab",
    "move": "grab",
    "magnifier": "zoom",
    "magnify": "zoom",
}


def _clean_cursor_token(value: str | None) -> str:
    return str(value or "").strip().casefold().replace(" ", "_").replace("-", "_")


def cursor_fx_for_hit_role(hit_role: str | None, *, kind: str = "move") -> tuple[str, str]:
    role = _clean_cursor_token(hit_role)
    style, animation = _CURSOR_ROLE_FX.get(role, ("", ""))
    if not style:
        style = "hand" if role.endswith("_button") or role.endswith("button") else "pointer"
    if not animation:
        animation = "click_pop" if str(kind or "").casefold() in {"click", "down", "release"} else ""
    return _CURSOR_STYLE_ALIASES.get(style, style), animation


def normalize_cursor_style(value: str | None, *, fallback: str = "pointer") -> str:
    token = _clean_cursor_token(value)
    if not token:
        return fallback
    return _CURSOR_STYLE_ALIASES.get(token, token)


@dataclass(frozen=True)
class CursorEvent:
    t_ms: int
    x_norm: float = 0.5
    y_norm: float = 0.5
    kind: str = "move"
    visible: bool = True
    label: str = ""
    hit_role: str = ""
    hit_label: str = ""
    cursor_style: str = ""
    animation: str = ""

    @classmethod
    def from_mapping(cls, data: Mapping) -> "CursorEvent":
        x = data.get("x_norm", data.get("x", 0.5))
        y = data.get("y_norm", data.get("y", 0.5))
        try:
            x_f = float(x)
            y_f = float(y)
        except Exception:
            x_f, y_f = 0.5, 0.5
        # Legacy sidecars may store pixels without frame dimensions.  Treat
        # values outside 0..1 as "unknown" rather than aiming at a bogus edge.
        if x_f < 0.0 or x_f > 1.0:
            x_f = 0.5
        if y_f < 0.0 or y_f > 1.0:
            y_f = 0.5
        kind = str(data.get("kind", "move") or "move")
        hit_role = str(data.get("hit_role", data.get("role", data.get("target_role", ""))) or "")[:80]
        hit_label = str(data.get("hit_label", data.get("target_label", data.get("ui_label", ""))) or "")[:80]
        inferred_style, inferred_animation = cursor_fx_for_hit_role(hit_role, kind=kind)
        cursor_style = normalize_cursor_style(
            str(data.get("cursor_style", data.get("style", "")) or ""),
            fallback=inferred_style,
        )
        animation = str(data.get("animation", data.get("cursor_animation", "")) or inferred_animation)[:48]
        return cls(
            t_ms=max(0, int(data.get("t_ms", data.get("ms", data.get("t", 0))) or 0)),
            x_norm=_clamp(x_f, 0.0, 1.0),
            y_norm=_clamp(y_f, 0.0, 1.0),
            kind=kind,
            visible=bool(data.get("visible", True)),
            label=str(data.get("label", data.get("key", "")) or "")[:40],
            hit_role=hit_role,
            hit_label=hit_label,
            cursor_style=cursor_style,
            animation=animation,
        )

    def to_dict(self) -> dict:
        data = {
            "t_ms": int(self.t_ms),
            "x_norm": round(float(self.x_norm), 5),
            "y_norm": round(float(self.y_norm), 5),
            "kind": str(self.kind or "move"),
            "visible": bool(self.visible),
        }
        if self.label:
            data["label"] = str(self.label)[:40]
        if self.hit_role:
            data["hit_role"] = str(self.hit_role)[:80]
        if self.hit_label:
            data["hit_label"] = str(self.hit_label)[:80]
        if self.cursor_style:
            data["cursor_style"] = normalize_cursor_style(self.cursor_style)
        if self.animation:
            data["animation"] = str(self.animation)[:48]
        return data


@dataclass(frozen=True)
class ActionPoint:
    t_ms: int
    x_norm: float
    y_norm: float
    kind: str = "move"


DEFAULT_CURSOR_POLISH = {
    "renderer": "supersampled_vector",
    "supersample": 3,
    "hotspot_x": 0.02,
    "hotspot_y": 0.02,
    "shadow_strength": 0.74,
    "cursor_scale": 1.42,
    "cursor_smoothing": 0.82,
    "motion_easing": "smooth",
    "hide_static_after_ms": 760,
    "click_ring_ms": 520,
    "click_hold_ms": 130,
    "click_ring_color": "#FF6A3D",
    "click_pop": 0.22,
    "drag_trail_ms": 760,
    "cursor_focus_glow": 0.18,
    "click_ring_strength": 1.15,
    "loop_cursor": True,
    "loop_return_ms": 920,
}

DEFAULT_SCREEN_POLISH = {
    "background": "wallpaper-gradient",
    "padding": 0.095,
    "shadow": 0.66,
    "inset": 0.02,
    "corner_radius": 0.045,
    "vertical_mode": "auto",
    "zoom_scale": 1.68,
    "zoom_duration_ms": 2050,
    "zoom_easing": "smooth_pop",
    "zoom_motion_blur": 0.16,
    "zoom_focus_bias": 0.26,
}


DEFAULT_SCREENSTUDIO_AUDIO_POLISH = {
    "enabled": True,
    "voice_normalize": True,
    "noise_cleanup": True,
    "dialogue_cleanup_strength": 0.68,
    "loudness_target_id": "shortform",
    "target_lufs": -14.0,
    "true_peak_db": -1.0,
    "subtitle_transcript_ready": False,
}


DEFAULT_SCREENSTUDIO_POLISH_PRESET_ID = "screenstudio_ready"

SCREENSTUDIO_POLISH_PRESETS = {
    "screenstudio_ready": {
        "label": "Screen Studio Ready",
        "cursor": {
            "cursor_scale": 1.42,
            "cursor_smoothing": 0.84,
            "motion_easing": "smooth",
            "hide_static_after_ms": 760,
            "click_ring_ms": 520,
            "click_hold_ms": 145,
            "click_ring_color": "#FF7A59",
            "click_pop": 0.24,
            "drag_trail_ms": 760,
        },
        "screen": {
            "background": "wallpaper-gradient",
            "padding": 0.095,
            "shadow": 0.68,
            "inset": 0.02,
            "corner_radius": 0.048,
            "vertical_mode": "auto",
            "zoom_scale": 1.66,
            "zoom_duration_ms": 2100,
            "zoom_easing": "smooth_pop",
            "zoom_motion_blur": 0.15,
            "zoom_focus_bias": 0.27,
        },
    },
    "clean_tutorial": {
        "label": "Clean Tutorial",
        "cursor": {
            "cursor_scale": 1.34,
            "cursor_smoothing": 0.82,
            "motion_easing": "smooth",
            "hide_static_after_ms": 780,
            "click_ring_ms": 500,
            "click_hold_ms": 125,
            "click_ring_color": "#FF6A3D",
            "click_pop": 0.20,
            "drag_trail_ms": 720,
        },
        "screen": {
            "background": "wallpaper-gradient",
            "padding": 0.09,
            "shadow": 0.62,
            "inset": 0.02,
            "corner_radius": 0.044,
            "vertical_mode": "auto",
            "zoom_scale": 1.64,
            "zoom_duration_ms": 2000,
            "zoom_easing": "smooth_pop",
            "zoom_motion_blur": 0.14,
            "zoom_focus_bias": 0.26,
        },
    },
    "product_demo": {
        "label": "Product Demo",
        "cursor": {
            "cursor_scale": 1.18,
            "cursor_smoothing": 0.82,
            "motion_easing": "smooth",
            "hide_static_after_ms": 1100,
            "click_ring_ms": 430,
            "click_hold_ms": 115,
            "click_ring_color": "#4BD9D9",
            "click_pop": 0.16,
            "drag_trail_ms": 600,
        },
        "screen": {
            "background": "product-warm",
            "padding": 0.10,
            "shadow": 0.68,
            "inset": 0.02,
            "corner_radius": 0.045,
            "vertical_mode": "auto",
            "zoom_scale": 1.58,
            "zoom_duration_ms": 2100,
            "zoom_easing": "cinematic",
            "zoom_motion_blur": 0.12,
            "zoom_focus_bias": 0.26,
        },
    },
    "cursor_focus": {
        "label": "Cursor Focus",
        "cursor": {
            "cursor_scale": 1.55,
            "cursor_smoothing": 0.76,
            "motion_easing": "smooth",
            "hide_static_after_ms": 650,
            "click_ring_ms": 560,
            "click_hold_ms": 165,
            "click_ring_color": "#8B78FF",
            "click_pop": 0.28,
            "drag_trail_ms": 760,
        },
        "screen": {
            "background": "cursor-focus",
            "padding": 0.07,
            "shadow": 0.62,
            "inset": 0.02,
            "corner_radius": 0.030,
            "vertical_mode": "auto",
            "zoom_scale": 1.92,
            "zoom_duration_ms": 1750,
            "zoom_easing": "snappy",
            "zoom_motion_blur": 0.20,
            "zoom_focus_bias": 0.20,
        },
    },
    "shorts_vertical": {
        "label": "Shorts Vertical",
        "cursor": {
            "cursor_scale": 1.42,
            "cursor_smoothing": 0.80,
            "motion_easing": "smooth",
            "hide_static_after_ms": 760,
            "click_ring_ms": 540,
            "click_hold_ms": 135,
            "click_ring_color": "#FF7CB8",
            "click_pop": 0.24,
            "drag_trail_ms": 760,
        },
        "screen": {
            "background": "vertical-pop",
            "padding": 0.13,
            "shadow": 0.74,
            "inset": 0.02,
            "corner_radius": 0.055,
            "vertical_mode": "auto",
            "zoom_scale": 1.82,
            "zoom_duration_ms": 1800,
            "zoom_easing": "smooth_pop",
            "zoom_motion_blur": 0.24,
            "zoom_focus_bias": 0.24,
        },
    },
    "soft_wallpaper": {
        "label": "Soft Wallpaper",
        "cursor": {
            "cursor_scale": 1.30,
            "cursor_smoothing": 0.86,
            "motion_easing": "smooth",
            "hide_static_after_ms": 1250,
            "click_ring_ms": 460,
            "click_hold_ms": 110,
            "click_ring_color": "#5AD7F2",
            "click_pop": 0.14,
            "drag_trail_ms": 560,
        },
        "screen": {
            "background": "candy-sky",
            "padding": 0.09,
            "shadow": 0.48,
            "inset": 0.02,
            "corner_radius": 0.060,
            "vertical_mode": "auto",
            "zoom_scale": 1.60,
            "zoom_duration_ms": 2200,
            "zoom_easing": "cinematic",
            "zoom_motion_blur": 0.10,
            "zoom_focus_bias": 0.28,
        },
    },
}


def screenstudio_polish_preset_ids() -> list[str]:
    return list(SCREENSTUDIO_POLISH_PRESETS.keys())


def screenstudio_polish_preset(preset_id: str | None = None) -> dict:
    raw = SCREENSTUDIO_POLISH_PRESETS.get(str(preset_id or DEFAULT_SCREENSTUDIO_POLISH_PRESET_ID))
    if raw is None:
        raw = SCREENSTUDIO_POLISH_PRESETS[DEFAULT_SCREENSTUDIO_POLISH_PRESET_ID]
        preset_id = DEFAULT_SCREENSTUDIO_POLISH_PRESET_ID
    return {
        "version": 1,
        "source": "screenstudio_auto_polish",
        "preset_id": str(preset_id or DEFAULT_SCREENSTUDIO_POLISH_PRESET_ID),
        "cursor": {**DEFAULT_CURSOR_POLISH, **dict(raw.get("cursor", {}) or {})},
        "screen": {**DEFAULT_SCREEN_POLISH, **dict(raw.get("screen", {}) or {})},
    }


def screenstudio_starter_defaults(starter_template_id: str | None = None) -> dict:
    """Return the one-click polish payload that makes new projects look finished.

    This intentionally maps product/startup templates onto renderable defaults,
    so importing a screen recording with cursor metadata can immediately preview
    with wallpaper, padding, click animation, and auto-zoom.
    """
    starter = str(starter_template_id or "").strip().casefold()
    preset_id = {
        "vertical-shorts": "shorts_vertical",
        "product-demo": "product_demo",
        "gameplay-highlight": "cursor_focus",
        "actor-showcase": "clean_tutorial",
        "blank": DEFAULT_SCREENSTUDIO_POLISH_PRESET_ID,
        "screen-recording-demo": DEFAULT_SCREENSTUDIO_POLISH_PRESET_ID,
    }.get(starter, DEFAULT_SCREENSTUDIO_POLISH_PRESET_ID)
    payload = screenstudio_polish_preset(preset_id)
    payload["starter_template_id"] = starter or "screen-recording-demo"
    return payload


def screenstudio_audio_defaults(starter_template_id: str | None = None) -> dict:
    """Return Screen Studio-style audio defaults for screen recordings.

    The actual export chain already understands dialogue-cleanup and loudness
    payloads through ``app.audio_workflow``/``app.audio_tracks``.  This helper
    is the product-level intent used by new-project/export QA before an audio
    clip exists.
    """
    starter = str(starter_template_id or "").strip().casefold()
    out = dict(DEFAULT_SCREENSTUDIO_AUDIO_POLISH)
    if starter == "actor-showcase":
        out.update({"loudness_target_id": "podcast", "target_lufs": -16.0, "dialogue_cleanup_strength": 0.62})
    elif starter == "product-demo":
        out.update({"dialogue_cleanup_strength": 0.58})
    elif starter == "vertical-shorts":
        out.update({"dialogue_cleanup_strength": 0.72, "target_lufs": -14.0})
    out["starter_template_id"] = starter or "screen-recording-demo"
    return out


def screenstudio_share_provider_config(project_settings: Mapping | None = None) -> dict:
    """Normalize the configured post-export share provider.

    The app remains local-first.  A non-local provider only produces a stable
    handoff URL/template here; actual upload is owned by a provider plugin or
    external integration.
    """
    settings = dict(project_settings or {})
    explicit_link = bool(settings.get("screenstudio_share_link_ready"))
    raw_provider = str(
        settings.get("screenstudio_share_provider")
        or settings.get("share_provider")
        or ("workspace-share" if explicit_link else "local")
    ).strip()
    provider_id = raw_provider.casefold().replace("_", "-") or "local"
    aliases = {
        "workspace": "workspace-share",
        "workspace-share-link": "workspace-share",
        "url-template": "custom-url-template",
        "custom": "custom-url-template",
        "none": "local",
    }
    provider_id = aliases.get(provider_id, provider_id)
    template = str(
        settings.get("screenstudio_share_url_template")
        or settings.get("share_url_template")
        or ""
    ).strip()
    base_url = str(
        settings.get("screenstudio_share_base_url")
        or settings.get("share_base_url")
        or ""
    ).strip()
    enabled = provider_id not in {"", "local"}
    warning = ""
    if provider_id == "custom-url-template" and not template:
        enabled = False
        warning = "custom_share_url_template_missing"
    if provider_id == "workspace-share" and not base_url:
        base_url = "tigercapture://share"
    labels = {
        "local": "Local package",
        "workspace-share": "Workspace share",
        "custom-url-template": "Custom share link",
    }
    return {
        "ok": True,
        "provider_id": provider_id,
        "provider_label": labels.get(provider_id, raw_provider or "Local package"),
        "enabled": bool(enabled),
        "requires_upload": bool(enabled),
        "base_url": base_url,
        "url_template": template,
        "copy_action": "copy_share_link" if enabled else "",
        "handoff_action": "provider_upload" if enabled else "local_package",
        "warning": warning,
    }


def _screenstudio_share_id(output_path: Path) -> str:
    try:
        stat = output_path.stat()
        token = f"{output_path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"
    except Exception:
        token = str(output_path)
    return hashlib.sha1(token.encode("utf-8", errors="replace")).hexdigest()[:16]


def screenstudio_build_share_link(
    output_path: str | Path,
    export_defaults: Mapping | None = None,
    project_settings: Mapping | None = None,
) -> dict:
    """Build a deterministic share-link handoff payload for configured providers."""
    output = Path(output_path)
    defaults = dict(export_defaults or {})
    settings = dict(project_settings or {})
    provider = dict(defaults.get("share_provider_config") or screenstudio_share_provider_config({**settings, **defaults}))
    share_id = _screenstudio_share_id(output)
    provider_id = str(provider.get("provider_id") or "local")
    if not provider.get("enabled") and not defaults.get("share_link_ready"):
        return {
            "ok": False,
            "ready": False,
            "provider_id": provider_id,
            "provider_label": str(provider.get("provider_label") or provider_id),
            "share_id": share_id,
            "share_url": "",
            "reason": "share_link_provider_not_configured",
        }
    if provider_id == "custom-url-template":
        template = str(provider.get("url_template") or "")
        if not template:
            return {
                "ok": False,
                "ready": False,
                "provider_id": provider_id,
                "provider_label": str(provider.get("provider_label") or provider_id),
                "share_id": share_id,
                "share_url": "",
                "reason": "custom_share_url_template_missing",
            }
        share_url = template.format(
            id=share_id,
            file=output.name,
            stem=output.stem,
            sha1=share_id,
        )
    elif provider_id == "workspace-share":
        base_url = str(provider.get("base_url") or "tigercapture://share").rstrip("/")
        share_url = f"{base_url}/{share_id}"
    else:
        base_url = str(provider.get("base_url") or "").rstrip("/")
        share_url = f"{base_url}/{share_id}" if base_url else ""
    return {
        "ok": bool(share_url),
        "ready": bool(share_url),
        "provider_id": provider_id,
        "provider_label": str(provider.get("provider_label") or provider_id),
        "requires_upload": bool(provider.get("requires_upload")),
        "share_id": share_id,
        "share_url": share_url,
        "output_path": str(output),
        "copy_action": "copy_share_link" if share_url else "",
        "reason": "" if share_url else "share_url_unavailable",
    }


def screenstudio_default_export_settings(project_settings: Mapping | None = None) -> dict:
    settings = dict(project_settings or {})
    width = int(settings.get("canvas_width") or 0)
    height = int(settings.get("canvas_height") or 0)
    fps = float(settings.get("fps") or 0.0)
    starter = str(settings.get("starter_template_id") or "").casefold()
    explicit_intent = str(
        settings.get("screenstudio_export_intent")
        or settings.get("export_intent")
        or ""
    ).strip().casefold()
    if explicit_intent:
        intent_id = explicit_intent
    elif starter == "vertical-shorts":
        intent_id = "social_vertical"
    elif starter == "product-demo":
        intent_id = "product_web"
    elif starter == "actor-showcase":
        intent_id = "editor_roundtrip"
    else:
        intent_id = "web_demo"
    intent_meta = {
        "web_demo": {
            "label": "Web Demo",
            "format_id": "mp4",
            "quality_id": "high",
            "destinations": ["website", "docs", "chat"],
        },
        "product_web": {
            "label": "Product Demo",
            "format_id": "mp4",
            "quality_id": "high",
            "destinations": ["website", "launch", "sales"],
        },
        "social_vertical": {
            "label": "Social Vertical",
            "format_id": "mp4",
            "quality_id": "high",
            "destinations": ["shorts", "reels", "tiktok"],
        },
        "editor_roundtrip": {
            "label": "Editor Roundtrip",
            "format_id": "mov",
            "quality_id": "best",
            "destinations": ["editor", "archive"],
        },
    }.get(intent_id, {})
    target_fps = 60.0 if (
        starter in {"screen-recording-demo", "vertical-shorts"}
        or intent_id == "social_vertical"
    ) else (fps or 30.0)
    fmt = str(intent_meta.get("format_id") or "mp4")
    quality = str(intent_meta.get("quality_id") or "high")
    destinations = list(intent_meta.get("destinations") or ["website", "docs"])
    mp4_delivery = fmt == "mp4" and intent_id in {"web_demo", "product_web", "social_vertical"}
    share_provider_config = screenstudio_share_provider_config(settings)
    share_provider = str(share_provider_config.get("provider_id") or "")
    share_link_ready = bool(settings.get("screenstudio_share_link_ready") or share_provider_config.get("enabled"))
    share_package_ready = bool(mp4_delivery or intent_id == "editor_roundtrip")
    clipboard_ready = bool(mp4_delivery or settings.get("screenstudio_clipboard_ready"))
    post_export_actions = ["reveal_file"]
    if clipboard_ready:
        post_export_actions.append("copy_path")
    if share_package_ready:
        post_export_actions.append("local_share_package")
    if share_link_ready:
        post_export_actions.append("copy_share_link")
    if share_link_ready:
        handoff_label = "share link"
    elif share_package_ready and clipboard_ready:
        handoff_label = "clipboard + local share"
    elif share_package_ready:
        handoff_label = "local package"
    else:
        handoff_label = "manual handoff"
    return {
        "intent_id": intent_id,
        "intent_label": str(intent_meta.get("label") or "Web Demo"),
        "destinations": destinations,
        "format_id": fmt,
        "quality_id": quality,
        "resolution": (width, height) if width > 0 and height > 0 else None,
        "fps": target_fps,
        "screenstudio_ready": bool(settings.get("screenstudio_polish") or starter in {"screen-recording-demo", "vertical-shorts", "product-demo"}),
        "audio_defaults_ready": bool(
            settings.get("screenstudio_audio_defaults_ready")
            or settings.get("screenstudio_audio_defaults")
            or starter in {"screen-recording-demo", "vertical-shorts", "product-demo"}
        ),
        "clipboard_ready": clipboard_ready,
        "share_link_ready": share_link_ready,
        "share_package_ready": share_package_ready,
        "share_provider": share_provider,
        "share_provider_label": str(share_provider_config.get("provider_label") or share_provider),
        "share_provider_config": share_provider_config,
        "handoff_label": handoff_label,
        "post_export_actions": post_export_actions,
    }


def screenstudio_share_manifest_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    return path.with_name(path.name + ".share.json")


def screenstudio_write_local_share_manifest(output_path: str | Path, export_defaults: Mapping | None = None) -> Path:
    output_path = Path(output_path)
    defaults = dict(export_defaults or {})
    stat = output_path.stat() if output_path.exists() else None
    manifest_path = screenstudio_share_manifest_path(output_path)
    share_link = screenstudio_build_share_link(output_path, defaults) if defaults.get("share_link_ready") else {}
    payload = {
        "version": 1,
        "kind": "screenstudio_local_share_package",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_path": str(output_path),
        "file_name": output_path.name,
        "size_bytes": int(stat.st_size) if stat is not None else 0,
        "intent_id": str(defaults.get("intent_id") or ""),
        "intent_label": str(defaults.get("intent_label") or ""),
        "format_id": str(defaults.get("format_id") or ""),
        "quality_id": str(defaults.get("quality_id") or ""),
        "resolution": list(defaults.get("resolution") or []),
        "fps": defaults.get("fps"),
        "destinations": list(defaults.get("destinations") or []),
        "post_export_actions": list(defaults.get("post_export_actions") or []),
        "handoff_label": str(defaults.get("handoff_label") or ""),
        "clipboard_ready": bool(defaults.get("clipboard_ready")),
        "share_package_ready": bool(defaults.get("share_package_ready")),
        "share_link_ready": bool(defaults.get("share_link_ready")),
        "share_provider": str(defaults.get("share_provider") or ""),
        "share_provider_label": str(defaults.get("share_provider_label") or ""),
        "share_provider_config": dict(defaults.get("share_provider_config") or {}),
        "share_id": str(share_link.get("share_id") or ""),
        "share_url": str(share_link.get("share_url") or ""),
        "share_link": share_link,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def screenstudio_export_completion_summary(
    output_path: str | Path,
    export_defaults: Mapping | None = None,
    *,
    notes: Iterable[str] | None = None,
) -> dict:
    """Build the product-facing completion model for Screen Studio exports.

    The GUI uses this for the post-export handoff dialog, while QA can validate
    the same fields without launching a modal dialog or touching the clipboard.
    """
    output_path = Path(output_path)
    defaults = dict(export_defaults or {})
    manifest_path = screenstudio_share_manifest_path(output_path)
    exists = output_path.exists()
    manifest_exists = manifest_path.exists()
    size_bytes = int(output_path.stat().st_size) if exists else 0
    actions = [str(action) for action in list(defaults.get("post_export_actions") or [])]
    action_labels: list[str] = []
    if "reveal_file" in actions:
        action_labels.append("Reveal output")
    if "copy_path" in actions:
        action_labels.append("Copy path")
    if "local_share_package" in actions:
        action_labels.append("Local share manifest")
    if "copy_share_link" in actions:
        action_labels.append("Share link")
    share_link = screenstudio_build_share_link(output_path, defaults) if defaults.get("share_link_ready") else {}
    share_ready = bool(defaults.get("share_package_ready"))
    attention: list[str] = []
    if not exists:
        attention.append("output_missing")
    if share_ready and not manifest_exists:
        attention.append("share_manifest_missing")
    if not action_labels:
        attention.append("no_post_export_actions")
    if "copy_share_link" in actions and not share_link.get("share_url"):
        attention.append(str(share_link.get("reason") or "share_link_unavailable"))
    status = "attention" if attention else "ready"
    intent_label = str(defaults.get("intent_label") or defaults.get("intent_id") or "Export")
    fmt = str(defaults.get("format_id") or output_path.suffix.lstrip(".") or "")
    quality = str(defaults.get("quality_id") or "")
    handoff = str(defaults.get("handoff_label") or "")
    summary_parts = [intent_label]
    if fmt:
        summary_parts.append(fmt.upper())
    if quality:
        summary_parts.append(quality)
    if handoff:
        summary_parts.append(handoff)
    return {
        "version": 1,
        "kind": "screenstudio_export_completion",
        "status": status,
        "attention": attention,
        "output_path": str(output_path),
        "file_name": output_path.name,
        "output_exists": exists,
        "size_bytes": size_bytes,
        "share_manifest_path": str(manifest_path),
        "share_manifest_exists": manifest_exists,
        "intent_id": str(defaults.get("intent_id") or ""),
        "intent_label": intent_label,
        "format_id": fmt,
        "quality_id": quality,
        "resolution": list(defaults.get("resolution") or []),
        "fps": defaults.get("fps"),
        "handoff_label": handoff,
        "clipboard_ready": bool(defaults.get("clipboard_ready")),
        "share_package_ready": share_ready,
        "share_link_ready": bool(defaults.get("share_link_ready")),
        "share_provider": str(defaults.get("share_provider") or ""),
        "share_provider_label": str(defaults.get("share_provider_label") or ""),
        "share_provider_config": dict(defaults.get("share_provider_config") or {}),
        "share_id": str(share_link.get("share_id") or ""),
        "share_url": str(share_link.get("share_url") or ""),
        "share_link": share_link,
        "post_export_actions": actions,
        "action_labels": action_labels,
        "summary_line": " / ".join(summary_parts),
        "notes": [str(note) for note in list(notes or []) if str(note).strip()],
    }


def screenstudio_default_export_result_readiness(
    project_settings: Mapping | None = None,
    *,
    cursor_metadata_count: int = 0,
    polished_clip_count: int = 0,
    auto_zoom_count: int = 0,
) -> dict:
    """Summarize whether default export settings can produce a polished result."""
    settings = dict(project_settings or {})
    defaults = screenstudio_default_export_settings(settings)
    polish = normalize_screenstudio_polish(settings.get("screenstudio_polish") or screenstudio_starter_defaults(settings.get("starter_template_id")))
    cursor = dict(polish.get("cursor") or {})
    screen = dict(polish.get("screen") or {})
    checks = {
        "delivery_defaults": (
            str(defaults.get("format_id") or "") == "mp4"
            and str(defaults.get("quality_id") or "") in {"high", "best"}
            and bool(defaults.get("screenstudio_ready"))
        ),
        "frame_style": (
            str(screen.get("background") or "")
            and float(screen.get("padding", 0.0) or 0.0) > 0.0
            and float(screen.get("shadow", 0.0) or 0.0) > 0.0
        ),
        "cursor_fx": (
            float(cursor.get("cursor_scale", 0.0) or 0.0) >= 1.0
            and int(cursor.get("click_ring_ms", 0) or 0) > 0
            and str(cursor.get("click_ring_color") or "").startswith("#")
        ),
        "handoff": bool(defaults.get("share_package_ready")) and "local_share_package" in set(defaults.get("post_export_actions") or []),
        "auto_zoom": (int(cursor_metadata_count or 0) <= 0) or (
            int(polished_clip_count or 0) >= int(cursor_metadata_count or 0)
            and int(auto_zoom_count or 0) > 0
        ),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "intent_id": defaults.get("intent_id"),
        "format_id": defaults.get("format_id"),
        "quality_id": defaults.get("quality_id"),
        "handoff_label": defaults.get("handoff_label"),
        "cursor_metadata_count": int(cursor_metadata_count or 0),
        "polished_clip_count": int(polished_clip_count or 0),
        "auto_zoom_count": int(auto_zoom_count or 0),
        "background": screen.get("background"),
        "padding": screen.get("padding"),
        "shadow": screen.get("shadow"),
        "cursor_scale": cursor.get("cursor_scale"),
        "click_ring_ms": cursor.get("click_ring_ms"),
    }


def screenstudio_simple_mode_profile(project_settings: Mapping | None = None) -> dict:
    """Return the product policy for the focused Screen Studio-style workspace.

    This is intentionally UI-toolkit agnostic.  The editor, launcher, QA, and
    future layout code can all ask the same question: should this project open
    in a simple record/polish/trim/export path, and which advanced surfaces
    should stay behind an advanced drawer?
    """
    settings = dict(project_settings or {})
    starter = str(settings.get("starter_template_id") or "").strip().casefold()
    explicit = settings.get("screenstudio_simple_mode")
    if explicit is None:
        enabled = bool(
            settings.get("screenstudio_polish")
            or starter in {"screen-recording-demo", "vertical-shorts", "product-demo"}
        )
    else:
        enabled = bool(explicit)
    advanced_surfaces = [
        "media_pool",
        "workbench",
        "node_graph",
        "actor_lanes",
        "color_page",
        "audio_mixer",
        "render_queue",
    ]
    primary_surfaces = ["record", "import", "preview", "auto_polish", "trim", "export"]
    checks = {
        "enabled": enabled,
        "preview_primary": enabled,
        "export_visible": enabled,
        "auto_polish_visible": enabled,
        "advanced_drawer": enabled,
        "advanced_surfaces_hidden": enabled,
    }
    score = int(round(sum(1 for passed in checks.values() if passed) / max(1, len(checks)) * 100))
    return {
        "enabled": enabled,
        "score": score,
        "primary_surfaces": primary_surfaces,
        "advanced_surfaces": advanced_surfaces,
        "hidden_by_default": advanced_surfaces if enabled else [],
        "checks": checks,
        "recommended_layout": "simple_screen_studio" if enabled else "full_editor",
        "advanced_drawer_label": "Advanced tools",
    }


def screenstudio_default_result_beauty_score(
    project_settings: Mapping | None = None,
    *,
    cursor_metadata_count: int = 0,
    polished_clip_count: int = 0,
    auto_zoom_count: int = 0,
    golden_video_ready: bool | None = None,
) -> dict:
    """Score whether the no-tuning path will produce a Screen Studio-like result.

    This is a product gate, not a renderer primitive.  It deliberately combines
    delivery defaults, frame style, cursor polish, zoom rhythm, simple-mode
    policy, audio defaults, and golden-video coverage so QA can track the gap
    from "features exist" to "the default result looks finished".
    """
    settings = dict(project_settings or {})
    readiness = screenstudio_default_export_result_readiness(
        settings,
        cursor_metadata_count=cursor_metadata_count,
        polished_clip_count=polished_clip_count,
        auto_zoom_count=auto_zoom_count,
    )
    defaults = screenstudio_default_export_settings(settings)
    polish = normalize_screenstudio_polish(
        settings.get("screenstudio_polish")
        or screenstudio_starter_defaults(settings.get("starter_template_id"))
    )
    cursor = dict(polish.get("cursor") or {})
    screen = dict(polish.get("screen") or {})
    simple = screenstudio_simple_mode_profile(settings)
    easing = str(screen.get("zoom_easing") or "").casefold()
    motion_defaults = (
        float(cursor.get("cursor_smoothing", 0.0) or 0.0) >= 0.78
        and int(cursor.get("click_hold_ms", 0) or 0) >= 110
        and float(screen.get("zoom_motion_blur", 0.0) or 0.0) > 0.0
        and easing in {"smooth_pop", "cinematic", "snappy", "smooth"}
        and int(screen.get("zoom_duration_ms", 0) or 0) >= 1500
    )
    vertical_safe = (
        str(screen.get("vertical_mode") or "").casefold() == "auto"
        and bool(defaults.get("resolution") or defaults.get("destinations"))
    )
    audio_defaults = bool(
        settings.get("screenstudio_audio_defaults_ready")
        or settings.get("screenstudio_audio_defaults")
        or settings.get("audio_defaults_ready")
        or defaults.get("audio_defaults_ready")
    )
    if golden_video_ready is None:
        golden_video_ready = bool(
            settings.get("screenstudio_golden_video_ready")
            or settings.get("visual_golden_video_ready")
        )
    checks = {
        "delivery_defaults": bool((readiness.get("checks") or {}).get("delivery_defaults")),
        "frame_style": bool((readiness.get("checks") or {}).get("frame_style")),
        "cursor_fx": bool((readiness.get("checks") or {}).get("cursor_fx")),
        "auto_zoom": bool((readiness.get("checks") or {}).get("auto_zoom")),
        "handoff": bool((readiness.get("checks") or {}).get("handoff")),
        "simple_mode": bool(simple.get("enabled")) and int(simple.get("score", 0) or 0) >= 100,
        "motion_defaults": bool(motion_defaults),
        "vertical_safe": bool(vertical_safe),
        "audio_defaults": bool(audio_defaults),
        "golden_video": bool(golden_video_ready),
    }
    weights = {
        "delivery_defaults": 12,
        "frame_style": 12,
        "cursor_fx": 14,
        "auto_zoom": 14,
        "handoff": 10,
        "simple_mode": 12,
        "motion_defaults": 10,
        "vertical_safe": 8,
        "audio_defaults": 5,
        "golden_video": 3,
    }
    score = sum(weight for key, weight in weights.items() if checks.get(key))
    critical = [
        "delivery_defaults",
        "frame_style",
        "cursor_fx",
        "auto_zoom",
        "handoff",
        "simple_mode",
        "motion_defaults",
        "vertical_safe",
    ]
    recommendations = {
        "delivery_defaults": "Use Screen Studio web/social/product export defaults.",
        "frame_style": "Enable wallpaper background, padding, rounded corners, and shadow.",
        "cursor_fx": "Enable cursor scale, click rings, smoothing, and static-cursor hiding.",
        "auto_zoom": "Generate Auto Zoom windows for every clip with cursor metadata.",
        "handoff": "Enable local-share/clipboard post-export actions.",
        "simple_mode": "Open this project in Simple Screen Studio Mode by default.",
        "motion_defaults": "Tune easing, click hold, zoom duration, and motion blur defaults.",
        "vertical_safe": "Keep vertical/social auto-reframe metadata enabled.",
        "audio_defaults": "Apply voice normalization/noise cleanup defaults for screen recordings.",
        "golden_video": "Validate this default path against golden short-video QA.",
    }
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "ok": score >= 85 and all(checks.get(key) for key in critical),
        "score": int(score),
        "threshold": 85,
        "checks": checks,
        "failed": failed,
        "actions": [recommendations[key] for key in failed if key in recommendations],
        "readiness": readiness,
        "simple_mode": simple,
        "intent_id": defaults.get("intent_id"),
        "format_id": defaults.get("format_id"),
        "quality_id": defaults.get("quality_id"),
    }


def screenstudio_default_golden_video_probe(project_settings: Mapping | None = None) -> dict:
    """Run a tiny representative-frame probe for the default Screen Studio path.

    This is intentionally fast enough for smoke QA.  It does not replace a
    full real-recording corpus, but it validates that the default path visibly
    changes frames through wallpaper framing, cursor/click drawing, auto zoom
    planning, and preview/export compositor parity.
    """
    try:
        import cv2
        import numpy as np
        from types import SimpleNamespace
    except Exception as exc:
        return {"ok": False, "reason": f"dependency_unavailable:{exc}"}
    settings = dict(project_settings or {})
    polish = normalize_screenstudio_polish(
        settings.get("screenstudio_polish")
        or screenstudio_starter_defaults(settings.get("starter_template_id"))
    )
    h, w = 90, 160
    x = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[:, :, 0] = np.clip(34 + 90 * x + 20 * y, 0, 255)
    rgb[:, :, 1] = np.clip(42 + 80 * y, 0, 255)
    rgb[:, :, 2] = np.clip(80 + 110 * (1.0 - x), 0, 255)
    cv2.rectangle(rgb, (14, 14), (w - 14, h - 14), (235, 240, 255), 1, cv2.LINE_AA)
    cv2.rectangle(rgb, (24, 24), (74, 36), (115, 126, 255), -1, cv2.LINE_AA)
    cv2.rectangle(rgb, (24, 46), (126, 58), (255, 122, 89), -1, cv2.LINE_AA)
    events = [
        CursorEvent(200, 0.22, 0.30, "move"),
        CursorEvent(760, 0.62, 0.46, "click"),
        CursorEvent(980, 0.62, 0.46, "release"),
        CursorEvent(2400, 0.36, 0.62, "hotkey", label="Ctrl K"),
    ]
    owner = SimpleNamespace(
        source_path="",
        source_duration_ms=4200,
        cursor_events=events,
        screenstudio_polish=polish,
    )
    styled = apply_screen_frame_style_rgb(
        rgb,
        owner=owner,
        project_settings={"screenstudio_polish": polish},
        target_size=(w, h),
    )
    cursor_frame = apply_cursor_fx_rgb(
        styled,
        810,
        owner=owner,
        project_settings={"screenstudio_polish": polish},
    )
    actors = plan_auto_zoom_actors(
        duration_ms=4200,
        frame_w=w,
        frame_h=h,
        cursor_events=events,
        max_actors=3,
        zoom_scale=float((polish.get("screen") or {}).get("zoom_scale", 1.66) or 1.66),
        zoom_duration_ms=int((polish.get("screen") or {}).get("zoom_duration_ms", 1900) or 1900),
        zoom_easing=str((polish.get("screen") or {}).get("zoom_easing", "smooth_pop") or "smooth_pop"),
        zoom_motion_blur=float((polish.get("screen") or {}).get("zoom_motion_blur", 0.15) or 0.15),
    )
    try:
        parity = screenstudio_polish_parity_report(owner=owner, frame_size=(w, h))
    except Exception:
        parity = {"ok": False}

    def _delta(a, b) -> float:
        return float(np.mean(np.abs(a.astype(np.float32) - b.astype(np.float32))) / 255.0)

    frame_delta = _delta(styled, rgb)
    cursor_delta = _delta(cursor_frame, styled)
    checks = {
        "frame_style_visible": frame_delta >= 0.035,
        "cursor_click_visible": cursor_delta >= 0.006,
        "auto_zoom_planned": len(actors) >= 1,
        "parity_ok": bool(parity.get("ok") or parity.get("parity_ok")),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "frame_style_delta": round(frame_delta, 5),
        "cursor_click_delta": round(cursor_delta, 5),
        "auto_zoom_count": len(actors),
        "parity": parity,
    }


def normalize_screenstudio_polish(
    payload: Mapping | None = None,
    *,
    preset_id: str | None = None,
) -> dict:
    """Return a complete JSON-friendly polish payload.

    Project files may contain only a subset of the controls as the product UI
    evolves.  The editor should never have to special-case that shape, so this
    helper always returns a payload with full cursor/screen dictionaries.
    """
    base_id = str(preset_id or (payload or {}).get("preset_id", "") or DEFAULT_SCREENSTUDIO_POLISH_PRESET_ID)
    out = screenstudio_polish_preset(base_id)
    if payload:
        out.update({k: v for k, v in dict(payload).items() if k not in {"cursor", "screen"}})
        out["cursor"] = {**out["cursor"], **dict(payload.get("cursor", {}) or {})}
        out["screen"] = {**out["screen"], **dict(payload.get("screen", {}) or {})}
    out["version"] = 1
    out["source"] = str(out.get("source") or "screenstudio_auto_polish")
    out["preset_id"] = str(out.get("preset_id") or base_id)
    return out


def _hex_to_rgb(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        return fallback
    try:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except Exception:
        return fallback


def _merged_polish(owner=None, project_settings: Mapping | None = None) -> dict:
    payload = {}
    if owner is not None:
        try:
            payload.update(dict(getattr(owner, "screenstudio_polish", {}) or {}))
        except Exception:
            pass
    if project_settings:
        try:
            payload.update(dict(project_settings.get("screenstudio_polish", {}) or {}))
        except Exception:
            pass
    cursor = dict(DEFAULT_CURSOR_POLISH)
    cursor.update(dict(payload.get("cursor", {}) or {}))
    screen = dict(DEFAULT_SCREEN_POLISH)
    screen.update(dict(payload.get("screen", {}) or {}))
    payload["cursor"] = cursor
    payload["screen"] = screen
    return payload


def screenstudio_fx_enabled(owner=None, project_settings: Mapping | None = None) -> bool:
    if owner is not None:
        if getattr(owner, "screenstudio_polish", None):
            return True
        if getattr(owner, "cursor_events", None):
            return True
        if cursor_sidecar_candidates(getattr(owner, "source_path", None)):
            for candidate in cursor_sidecar_candidates(getattr(owner, "source_path", None)):
                try:
                    if candidate.is_file():
                        return True
                except Exception:
                    continue
    if project_settings:
        return bool(project_settings.get("screenstudio_polish"))
    return False


def normalize_cursor_events(events: Iterable[CursorEvent | Mapping] | None) -> list[CursorEvent]:
    out: list[CursorEvent] = []
    for item in events or []:
        if isinstance(item, CursorEvent):
            out.append(item)
        elif isinstance(item, Mapping):
            out.append(CursorEvent.from_mapping(item))
    out.sort(key=lambda e: e.t_ms)
    return out


def cursor_sidecar_candidates(source_path: str | Path | None) -> list[Path]:
    if source_path is None:
        return []
    path = Path(source_path)
    return [
        Path(str(path) + ".cursor.json"),
        path.with_suffix(".cursor.json"),
    ]


def load_cursor_sidecar(source_path: str | Path | None) -> list[CursorEvent]:
    for candidate in cursor_sidecar_candidates(source_path):
        try:
            if not candidate.is_file():
                continue
            data = json.loads(candidate.read_text(encoding="utf-8"))
            raw_events = data.get("events", data if isinstance(data, list) else [])
            return normalize_cursor_events(raw_events)
        except Exception:
            continue
    return []


def smooth_cursor_events(
    events: Iterable[CursorEvent | Mapping] | None,
    *,
    smoothing: float = 0.72,
) -> list[CursorEvent]:
    src = normalize_cursor_events(events)
    if not src:
        return []
    smoothing = _clamp(float(smoothing), 0.0, 0.95)
    out: list[CursorEvent] = []
    sx, sy = src[0].x_norm, src[0].y_norm
    for ev in src:
        if not out or ev.kind in {"click", "down", "release", "key", "hotkey"}:
            sx, sy = ev.x_norm, ev.y_norm
        else:
            sx = sx * smoothing + ev.x_norm * (1.0 - smoothing)
            sy = sy * smoothing + ev.y_norm * (1.0 - smoothing)
        out.append(
            CursorEvent(
                ev.t_ms,
                _clamp(sx, 0.0, 1.0),
                _clamp(sy, 0.0, 1.0),
                ev.kind,
                ev.visible,
                ev.label,
                ev.hit_role,
                ev.hit_label,
                ev.cursor_style,
                ev.animation,
            )
        )
    return out


def cursor_state_at(
    events: Iterable[CursorEvent | Mapping] | None,
    source_ms: int,
    *,
    smoothing: float = 0.72,
    motion_easing: str = "smooth",
    hide_after_ms: int = 900,
    click_ring_ms: int = 420,
    click_hold_ms: int = 110,
    drag_trail_ms: int = 620,
    duration_ms: int = 0,
    loop_cursor: bool = False,
    loop_return_ms: int = 900,
) -> dict | None:
    src = smooth_cursor_events(events, smoothing=smoothing)
    if not src:
        return None
    source_ms = max(0, int(source_ms))
    times = [ev.t_ms for ev in src]
    idx = bisect_right(times, source_ms) - 1
    if idx < 0:
        return None
    current = src[min(idx, len(src) - 1)]
    nxt = src[idx + 1] if idx + 1 < len(src) else None
    x = current.x_norm
    y = current.y_norm
    if nxt is not None and nxt.t_ms > current.t_ms:
        hold_ms = 0
        if str(current.kind or "").casefold() in {"click", "down", "release", "key", "hotkey"}:
            hold_ms = min(max(0, int(click_hold_ms or 0)), max(0, int((nxt.t_ms - current.t_ms) * 0.45)))
        active_start = int(current.t_ms) + hold_ms
        if source_ms <= active_start:
            t = 0.0
        else:
            t = _clamp((source_ms - active_start) / max(1, nxt.t_ms - active_start), 0.0, 1.0)
        if str(motion_easing or "smooth").casefold() in {"smooth", "screenstudio", "cinematic"}:
            t = _smoothstep(t)
        elif str(motion_easing or "").casefold() in {"snappy", "pop"}:
            t = _ease_out_cubic(t)
        x = current.x_norm + (nxt.x_norm - current.x_norm) * t
        y = current.y_norm + (nxt.y_norm - current.y_norm) * t
    visible = bool(current.visible)
    if hide_after_ms > 0 and current.kind not in {"click", "down", "release", "key", "hotkey"}:
        # Hide only after the last materially different event, so tiny samples
        # from the sidecar do not keep the cursor alive forever.
        last_motion = current
        for ev in reversed(src[: idx + 1]):
            if (
                ev.kind in {"click", "down", "release", "key", "hotkey"}
                or abs(ev.x_norm - current.x_norm) > 0.006
                or abs(ev.y_norm - current.y_norm) > 0.006
            ):
                last_motion = ev
                break
        if source_ms - last_motion.t_ms >= hide_after_ms:
            visible = False
    if loop_cursor and len(src) >= 2:
        duration_ms = max(0, int(duration_ms or 0))
        if duration_ms <= 0:
            duration_ms = max(ev.t_ms for ev in src) + max(600, int(loop_return_ms))
        loop_return_ms = max(240, int(loop_return_ms or 900))
        loop_start = max(0, duration_ms - loop_return_ms)
        if loop_start <= source_ms <= duration_ms:
            first = next((ev for ev in src if ev.visible), src[0])
            t = _clamp((source_ms - loop_start) / max(1, duration_ms - loop_start), 0.0, 1.0)
            t = _smoothstep(t)
            x = float(x) + (float(first.x_norm) - float(x)) * t
            y = float(y) + (float(first.y_norm) - float(y)) * t
            visible = bool(first.visible)
    current_style, current_animation = cursor_fx_for_hit_role(current.hit_role, kind=current.kind)
    current_style = normalize_cursor_style(current.cursor_style, fallback=current_style)
    current_animation = str(current.animation or current_animation or "")
    click = None
    click_ring_ms = max(1, int(click_ring_ms))
    for ev in reversed(src[: idx + 1]):
        if source_ms - ev.t_ms > click_ring_ms:
            break
        if ev.kind in {"click", "down", "release"}:
            dt = source_ms - ev.t_ms
            click_style, click_animation = cursor_fx_for_hit_role(ev.hit_role, kind=ev.kind)
            click_style = normalize_cursor_style(ev.cursor_style, fallback=click_style)
            click = {
                "progress": _clamp(dt / click_ring_ms, 0.0, 1.0),
                "x_norm": ev.x_norm,
                "y_norm": ev.y_norm,
                "kind": ev.kind,
                "hit_role": ev.hit_role,
                "hit_label": ev.hit_label,
                "cursor_style": click_style,
                "animation": str(ev.animation or click_animation or ""),
            }
            break
    trail: list[dict] = []
    drag_trail_ms = max(0, int(drag_trail_ms))
    if drag_trail_ms > 0:
        for ev in src[: idx + 1]:
            if source_ms - ev.t_ms > drag_trail_ms:
                continue
            if ev.kind not in {"drag", "down", "click"}:
                continue
            trail.append({
                "t_ms": int(ev.t_ms),
                "x_norm": float(ev.x_norm),
                "y_norm": float(ev.y_norm),
                "progress": _clamp((source_ms - ev.t_ms) / max(1, drag_trail_ms), 0.0, 1.0),
                "kind": ev.kind,
            })
    key = None
    for ev in reversed(src[: idx + 1]):
        if source_ms - ev.t_ms > 720:
            break
        if ev.kind in {"key", "hotkey"}:
            key = {
                "progress": _clamp((source_ms - ev.t_ms) / 720.0, 0.0, 1.0),
                "x_norm": ev.x_norm,
                "y_norm": ev.y_norm,
                "label": str(ev.label or ("HOTKEY" if ev.kind == "hotkey" else "KEY"))[:40],
            }
            break
    return {
        "x_norm": _clamp(x, 0.0, 1.0),
        "y_norm": _clamp(y, 0.0, 1.0),
        "kind": str(current.kind or "move"),
        "visible": visible,
        "hit_role": current.hit_role,
        "hit_label": current.hit_label,
        "cursor_style": current_style,
        "animation": current_animation,
        "click": click,
        "trail": trail,
        "key": key,
    }


def static_cursor_hidden_intervals(
    events: Iterable[CursorEvent | Mapping] | None,
    *,
    hide_after_ms: int = 900,
    movement_epsilon: float = 0.006,
) -> list[tuple[int, int]]:
    src = normalize_cursor_events(events)
    if len(src) < 2:
        return []
    hide_after_ms = max(0, int(hide_after_ms))
    movement_epsilon = max(0.0, float(movement_epsilon))
    last_move = src[0]
    hidden_from: int | None = None
    out: list[tuple[int, int]] = []
    for ev in src[1:]:
        moved = (
            abs(ev.x_norm - last_move.x_norm) > movement_epsilon
            or abs(ev.y_norm - last_move.y_norm) > movement_epsilon
            or ev.kind in {"click", "down", "key"}
        )
        if moved:
            if hidden_from is not None and ev.t_ms > hidden_from:
                out.append((hidden_from, ev.t_ms))
            last_move = ev
            hidden_from = None
            continue
        if hidden_from is None and ev.t_ms - last_move.t_ms >= hide_after_ms:
            hidden_from = last_move.t_ms + hide_after_ms
    if hidden_from is not None and src[-1].t_ms > hidden_from:
        out.append((hidden_from, src[-1].t_ms))
    return out


def infer_action_points(
    events: Iterable[CursorEvent | Mapping] | None,
    *,
    duration_ms: int,
    max_points: int = 5,
) -> list[ActionPoint]:
    duration_ms = max(0, int(duration_ms))
    max_points = max(1, int(max_points))
    if duration_ms < 4500:
        max_points = min(max_points, 2)
    elif duration_ms < 9000:
        max_points = min(max_points, 3)
    raw_src = [e for e in normalize_cursor_events(events) if e.visible and 0 <= e.t_ms <= duration_ms]
    src = smooth_cursor_events(raw_src)
    points: list[ActionPoint] = [
        ActionPoint(e.t_ms, e.x_norm, e.y_norm, e.kind)
        for e in src
        if e.kind in {"click", "down", "key", "hotkey", "release"}
    ]
    if len(points) < max_points:
        points.extend(
            _infer_dwell_action_points(
                raw_src,
                duration_ms=duration_ms,
                max_points=max_points - len(points),
            )
        )
    if len(points) < max_points:
        prev: CursorEvent | None = None
        for ev in src:
            if prev is None:
                prev = ev
                continue
            dist = abs(ev.x_norm - prev.x_norm) + abs(ev.y_norm - prev.y_norm)
            if dist >= 0.11:
                points.append(ActionPoint(ev.t_ms, ev.x_norm, ev.y_norm, "move"))
                prev = ev
                if len(points) >= max_points:
                    break
    if points:
        points.sort(key=lambda p: p.t_ms)
        return _dedupe_action_points(points, max_points=max_points)

    if duration_ms <= 0:
        return []
    ratios = (0.22, 0.47, 0.72) if duration_ms >= 7000 else (0.34, 0.66)
    fallback_xy = ((0.34, 0.42), (0.62, 0.46), (0.50, 0.58))
    return [
        ActionPoint(int(duration_ms * r), fallback_xy[i][0], fallback_xy[i][1], "fallback")
        for i, r in enumerate(ratios[:max_points])
    ]


def _infer_dwell_action_points(
    events: Sequence[CursorEvent],
    *,
    duration_ms: int,
    max_points: int,
    movement_epsilon: float = 0.018,
    min_dwell_ms: int = 1050,
    min_gap_ms: int = 1500,
) -> list[ActionPoint]:
    """Find Screen Studio-style "the cursor is parked here" moments.

    Clicks are still the strongest signal, but tutorials often pause over a UI
    control without clicking. Treating those pauses as soft zoom candidates
    makes plain screen recordings feel intentionally framed.
    """
    if max_points <= 0 or len(events) < 2:
        return []
    movement_epsilon = max(0.001, float(movement_epsilon))
    min_dwell_ms = max(400, int(min_dwell_ms))
    min_gap_ms = max(400, int(min_gap_ms))
    action_kinds = {"click", "down", "release", "key", "hotkey", "drag"}
    out: list[ActionPoint] = []
    cluster_start = events[0]
    cluster_last = events[0]

    def _commit(start: CursorEvent, last: CursorEvent) -> None:
        if len(out) >= max_points:
            return
        dwell_ms = int(last.t_ms) - int(start.t_ms)
        if dwell_ms < min_dwell_ms:
            return
        mid_ms = int(start.t_ms + dwell_ms * 0.55)
        if mid_ms < 250 or mid_ms > max(0, duration_ms - 250):
            return
        if any(abs(mid_ms - p.t_ms) < min_gap_ms for p in out):
            return
        x = (float(start.x_norm) + float(last.x_norm)) * 0.5
        y = (float(start.y_norm) + float(last.y_norm)) * 0.5
        out.append(ActionPoint(mid_ms, _clamp(x, 0.0, 1.0), _clamp(y, 0.0, 1.0), "dwell"))

    for ev in events[1:]:
        kind = str(ev.kind or "move").casefold()
        moved = (
            abs(float(ev.x_norm) - float(cluster_start.x_norm)) > movement_epsilon
            or abs(float(ev.y_norm) - float(cluster_start.y_norm)) > movement_epsilon
        )
        if moved or kind in action_kinds:
            _commit(cluster_start, cluster_last)
            cluster_start = ev
        cluster_last = ev
    _commit(cluster_start, cluster_last)
    return out[:max_points]


def _action_point_distance(a: ActionPoint, b: ActionPoint) -> float:
    return abs(float(a.x_norm) - float(b.x_norm)) + abs(float(a.y_norm) - float(b.y_norm))


def _dedupe_action_points(points: Sequence[ActionPoint], *, max_points: int) -> list[ActionPoint]:
    out: list[ActionPoint] = []
    for point in points:
        if out and (
            abs(point.t_ms - out[-1].t_ms) < 700
            or (abs(point.t_ms - out[-1].t_ms) < 1300 and _action_point_distance(point, out[-1]) < 0.09)
        ):
            if _action_point_priority(point) >= _action_point_priority(out[-1]):
                out[-1] = point
            continue
        out.append(point)
    if len(out) <= max_points:
        return out
    ranked = sorted(
        enumerate(out),
        key=lambda item: (
            -_action_point_priority(item[1]),
            abs(float(item[1].x_norm) - 0.5) + abs(float(item[1].y_norm) - 0.5),
            item[0],
        ),
    )[:max_points]
    keep = {idx for idx, _point in ranked}
    return [point for idx, point in enumerate(out) if idx in keep]


def _action_point_priority(point: ActionPoint) -> int:
    kind = str(getattr(point, "kind", "") or "").casefold()
    if kind in {"click", "down"}:
        return 50
    if kind in {"hotkey", "key"}:
        return 44
    if kind == "release":
        return 34
    if kind == "dwell":
        return 24
    if kind == "move":
        return 18
    return 10


def screenstudio_zoom_timing_profile(
    *,
    duration_ms: int,
    event_count: int = 0,
    action_count: int = 0,
    max_actors: int = 5,
    zoom_duration_ms: int = 1900,
) -> dict:
    """Return adaptive Auto Zoom pacing for short and long screen recordings."""
    duration_ms = max(0, int(duration_ms or 0))
    event_count = max(0, int(event_count or 0))
    action_count = max(0, int(action_count or 0))
    requested_max = max(1, int(max_actors or 1))
    requested_span = max(700, int(zoom_duration_ms or 1900))
    if duration_ms < 4500:
        target = min(requested_max, 2)
    elif duration_ms < 9000:
        target = min(requested_max, 3)
    else:
        duration_target = 3 + int(duration_ms // 18_000)
        event_target = 2 + int(action_count // 3)
        adaptive_cap = requested_max
        if requested_max <= 5 and duration_ms >= 45_000:
            adaptive_cap = min(9, max(requested_max, int(math.ceil(duration_ms / 15_000.0))))
        target = min(adaptive_cap, max(2, min(10, max(duration_target, event_target))))
    if event_count <= 0 and duration_ms >= 9000:
        target = min(target, 3)
    if duration_ms >= 60_000:
        span = min(max(1500, requested_span), 2100)
        lead = min(520, max(220, span // 4))
    elif duration_ms >= 18_000:
        span = min(max(1400, requested_span), 2200)
        lead = min(480, max(180, span // 5))
    else:
        span = requested_span
        lead = min(460, max(150, span // 5))
    if duration_ms < 4500:
        span = min(span, max(900, int(duration_ms * 0.43)))
    elif duration_ms < 9000:
        span = min(span, max(1200, int(duration_ms * 0.34)))
    rhythm_gap = 0
    if target > 1:
        rhythm_gap = int(duration_ms / max(2.0, target * 1.45))
    rhythm_gap = max(900, min(7200, rhythm_gap))
    overlap_gap = 140 if duration_ms < 4500 else (220 if duration_ms >= 30_000 else 180)
    candidate_budget = max(target, min(18, target * 3))
    return {
        "max_actors": int(target),
        "candidate_budget": int(candidate_budget),
        "zoom_duration_ms": int(span),
        "lead_ms": int(lead),
        "rhythm_gap_ms": int(rhythm_gap),
        "overlap_gap_ms": int(overlap_gap),
        "event_count": int(event_count),
        "action_count": int(action_count),
    }


def screenstudio_manual_zoom_edit_policy(project_settings: Mapping | None = None) -> dict:
    settings = dict(project_settings or {})
    return {
        "ok": True,
        "min_duration_ms": max(360, int(settings.get("screenstudio_zoom_min_duration_ms") or 520)),
        "snap_threshold_ms": max(0, int(settings.get("screenstudio_zoom_snap_threshold_ms") or 90)),
        "fine_nudge_ms": max(1, int(settings.get("screenstudio_zoom_fine_nudge_ms") or 16)),
        "keyboard_nudge_ms": max(1, int(settings.get("screenstudio_zoom_keyboard_nudge_ms") or 33)),
        "coarse_nudge_ms": max(1, int(settings.get("screenstudio_zoom_coarse_nudge_ms") or 100)),
        "handle_px": max(8, int(settings.get("screenstudio_zoom_handle_px") or 12)),
        "ramp_handle_px": max(8, int(settings.get("screenstudio_zoom_ramp_handle_px") or 11)),
        "cursor_shapes": {
            "move": "size_all",
            "resize_l": "size_h",
            "resize_r": "size_h",
            "fade_in": "split_h",
            "fade_out": "split_h",
        },
        "supports": [
            "move",
            "resize_edges",
            "ramp_handles",
            "timeline_snap",
            "keyboard_nudge",
            "target_rect_clamp",
            "edge_safe_crop",
            "viewer_drag_handles",
            "live_preview",
            "keyboard_nudge_ui",
            "duration_easing_popover",
            "drag_status_feedback",
            "undo_commit",
        ],
    }


def _snap_zoom_ms(value: int, targets: Iterable[int] | None, threshold_ms: int) -> tuple[int, int | None]:
    best: int | None = None
    best_distance: int | None = None
    for raw in targets or ():
        try:
            target = int(raw)
        except Exception:
            continue
        distance = abs(int(value) - target)
        if best_distance is None or distance < best_distance:
            best = target
            best_distance = distance
    if best is not None and best_distance is not None and best_distance <= max(0, int(threshold_ms)):
        return int(best), int(best)
    return int(value), None


def _zoom_actor_snapshot(actor) -> dict:
    return {
        "start_ms": int(getattr(actor, "start_ms", 0) or 0),
        "end_ms": int(getattr(actor, "end_ms", 0) or 0),
        "zoom_in_ms": int(getattr(actor, "zoom_in_ms", 0) or 0),
        "zoom_out_ms": int(getattr(actor, "zoom_out_ms", 0) or 0),
        "target_x": int(getattr(actor, "target_x", 0) or 0),
        "target_y": int(getattr(actor, "target_y", 0) or 0),
        "target_w": int(getattr(actor, "target_w", 0) or 0),
        "target_h": int(getattr(actor, "target_h", 0) or 0),
    }


def screenstudio_apply_manual_zoom_edit(
    actor,
    operation: str,
    *,
    delta_ms: int = 0,
    value_ms: int | None = None,
    duration_ms: int = 0,
    snap_targets: Iterable[int] | None = None,
    orig_start_ms: int | None = None,
    orig_end_ms: int | None = None,
    orig_zoom_in_ms: int | None = None,
    orig_zoom_out_ms: int | None = None,
    target_rect: Sequence[int] | None = None,
    frame_w: int = 1920,
    frame_h: int = 1080,
    project_settings: Mapping | None = None,
) -> dict:
    """Apply one Screen Studio-style manual zoom edit to a mutable ZoomActor."""
    policy = screenstudio_manual_zoom_edit_policy(project_settings)
    min_duration = int(policy["min_duration_ms"])
    snap_threshold = int(policy["snap_threshold_ms"])
    limit = max(0, int(duration_ms or getattr(actor, "end_ms", 0) or 0))
    before = _zoom_actor_snapshot(actor)
    start = int(orig_start_ms if orig_start_ms is not None else before["start_ms"])
    end = int(orig_end_ms if orig_end_ms is not None else before["end_ms"])
    zoom_in = int(orig_zoom_in_ms if orig_zoom_in_ms is not None else before["zoom_in_ms"])
    zoom_out = int(orig_zoom_out_ms if orig_zoom_out_ms is not None else before["zoom_out_ms"])
    op = str(operation or "").strip().casefold()
    snapped_to: int | None = None

    if op == "move":
        span = max(min_duration, end - start)
        new_start = max(0, start + int(delta_ms or 0))
        if limit > 0 and new_start + span > limit:
            new_start = max(0, limit - span)
        new_start, snapped_to = _snap_zoom_ms(new_start, snap_targets, snap_threshold)
        if limit > 0 and new_start + span > limit:
            new_start = max(0, limit - span)
        setattr(actor, "start_ms", int(new_start))
        setattr(actor, "end_ms", int(new_start + span))
    elif op == "resize_l":
        new_start = max(0, start + int(delta_ms or 0))
        new_start = min(new_start, max(0, end - min_duration))
        new_start, snapped_to = _snap_zoom_ms(new_start, snap_targets, snap_threshold)
        new_start = min(new_start, max(0, end - min_duration))
        setattr(actor, "start_ms", int(new_start))
        setattr(actor, "end_ms", int(end))
    elif op == "resize_r":
        new_end = max(start + min_duration, end + int(delta_ms or 0))
        if limit > 0:
            new_end = min(new_end, limit)
        new_end, snapped_to = _snap_zoom_ms(new_end, snap_targets, snap_threshold)
        new_end = max(start + min_duration, new_end)
        if limit > 0:
            new_end = min(new_end, limit)
        setattr(actor, "start_ms", int(start))
        setattr(actor, "end_ms", int(new_end))
    elif op == "fade_in":
        requested = int(value_ms if value_ms is not None else zoom_in + int(delta_ms or 0))
        span = max(0, int(getattr(actor, "end_ms", end) or end) - int(getattr(actor, "start_ms", start) or start))
        setattr(actor, "zoom_in_ms", int(_clamp(requested, 0, max(0, span - int(getattr(actor, "zoom_out_ms", zoom_out) or zoom_out)))))
    elif op == "fade_out":
        requested = int(value_ms if value_ms is not None else zoom_out + int(delta_ms or 0))
        span = max(0, int(getattr(actor, "end_ms", end) or end) - int(getattr(actor, "start_ms", start) or start))
        setattr(actor, "zoom_out_ms", int(_clamp(requested, 0, max(0, span - int(getattr(actor, "zoom_in_ms", zoom_in) or zoom_in)))))
    elif op == "target_rect" and target_rect is not None:
        fw = max(16, int(frame_w or 1920))
        fh = max(16, int(frame_h or 1080))
        x, y, w, h = [int(round(float(v))) for v in list(target_rect)[:4]]
        w = max(16, min(fw, w))
        h = max(16, min(fh, h))
        x = max(0, min(fw - w, x))
        y = max(0, min(fh - h, y))
        setattr(actor, "target_x", int(x))
        setattr(actor, "target_y", int(y))
        setattr(actor, "target_w", int(w))
        setattr(actor, "target_h", int(h))
    else:
        return {"ok": False, "changed": False, "operation": op, "reason": "unsupported_zoom_edit_operation"}

    span = max(0, int(getattr(actor, "end_ms", 0) or 0) - int(getattr(actor, "start_ms", 0) or 0))
    setattr(actor, "zoom_in_ms", int(min(max(0, int(getattr(actor, "zoom_in_ms", 0) or 0)), span)))
    setattr(actor, "zoom_out_ms", int(min(max(0, int(getattr(actor, "zoom_out_ms", 0) or 0)), max(0, span - int(getattr(actor, "zoom_in_ms", 0) or 0)))))
    after = _zoom_actor_snapshot(actor)
    return {
        "ok": True,
        "changed": before != after,
        "operation": op,
        "snapped_to_ms": snapped_to,
        "before": before,
        "after": after,
        "policy": policy,
    }


def screenstudio_manual_zoom_editor_report() -> dict:
    from app.timeline_model import ZoomActor

    actor = ZoomActor(
        id=1,
        start_ms=1000,
        end_ms=3100,
        target_x=640,
        target_y=260,
        target_w=720,
        target_h=420,
        zoom_in_ms=320,
        zoom_out_ms=300,
    )
    checks: dict[str, bool] = {}
    move = screenstudio_apply_manual_zoom_edit(
        actor,
        "move",
        delta_ms=88,
        duration_ms=6000,
        snap_targets=[0, 1100, 3000, 6000],
    )
    checks["move_snaps_to_timeline_mark"] = bool(move.get("ok")) and actor.start_ms == 1100
    resize_l = screenstudio_apply_manual_zoom_edit(
        actor,
        "resize_l",
        delta_ms=480,
        duration_ms=6000,
        orig_start_ms=actor.start_ms,
        orig_end_ms=actor.end_ms,
    )
    checks["left_resize_keeps_min_duration"] = bool(resize_l.get("ok")) and actor.end_ms - actor.start_ms >= 520
    fade = screenstudio_apply_manual_zoom_edit(actor, "fade_in", value_ms=5000, duration_ms=6000)
    checks["ramp_handles_clamp_inside_zoom_span"] = bool(fade.get("ok")) and actor.zoom_in_ms + actor.zoom_out_ms <= actor.end_ms - actor.start_ms
    target = screenstudio_apply_manual_zoom_edit(actor, "target_rect", target_rect=(-200, -80, 2500, 1200), frame_w=1920, frame_h=1080)
    checks["target_rect_stays_inside_frame"] = (
        bool(target.get("ok"))
        and actor.target_x >= 0
        and actor.target_y >= 0
        and actor.target_x + actor.target_w <= 1920
        and actor.target_y + actor.target_h <= 1080
    )
    edge_target = screenstudio_apply_manual_zoom_edit(
        actor,
        "target_rect",
        target_rect=(1888, 1050, 240, 140),
        frame_w=1920,
        frame_h=1080,
    )
    checks["edge_target_clamps_without_cropping"] = (
        bool(edge_target.get("ok"))
        and actor.target_w == 240
        and actor.target_h == 140
        and actor.target_x == 1680
        and actor.target_y == 940
    )
    oversized = screenstudio_apply_manual_zoom_edit(
        actor,
        "target_rect",
        target_rect=(-999, -999, 9999, 9999),
        frame_w=1920,
        frame_h=1080,
    )
    checks["oversized_target_uses_full_frame"] = (
        bool(oversized.get("ok"))
        and actor.target_x == 0
        and actor.target_y == 0
        and actor.target_w == 1920
        and actor.target_h == 1080
    )
    checks["policy_exposes_screenstudio_controls"] = set(screenstudio_manual_zoom_edit_policy().get("supports") or []) >= {
        "move",
        "resize_edges",
        "ramp_handles",
        "timeline_snap",
        "target_rect_clamp",
        "edge_safe_crop",
    }
    score = int(round(sum(1 for passed in checks.values() if passed) / max(1, len(checks)) * 100))
    return {
        "ok": all(checks.values()),
        "score": score,
        "checks": checks,
        "actor": _zoom_actor_snapshot(actor),
        "policy": screenstudio_manual_zoom_edit_policy(),
    }


def _rhythmic_action_points(
    points: Sequence[ActionPoint],
    *,
    duration_ms: int,
    max_points: int,
    min_gap_ms: int,
) -> list[ActionPoint]:
    if max_points <= 0:
        return []
    src = sorted(points, key=lambda p: int(p.t_ms))
    if len(src) <= max_points:
        return src
    min_gap_ms = max(0, int(min_gap_ms or 0))
    selected: list[ActionPoint] = []
    ranked = sorted(
        src,
        key=lambda p: (
            -_action_point_priority(p),
            abs(float(p.x_norm) - 0.5) + abs(float(p.y_norm) - 0.5),
            int(p.t_ms),
        ),
    )

    def _can_add(point: ActionPoint, gap: int) -> bool:
        return all(abs(int(point.t_ms) - int(existing.t_ms)) >= gap for existing in selected)

    for point in ranked:
        if len(selected) >= max_points:
            break
        if _can_add(point, min_gap_ms):
            selected.append(point)
    relaxed_gap = int(min_gap_ms * 0.58)
    if len(selected) < max_points:
        for point in src:
            if len(selected) >= max_points:
                break
            if any(point is existing for existing in selected):
                continue
            if _can_add(point, relaxed_gap):
                selected.append(point)
    if len(selected) < max_points:
        for point in ranked:
            if len(selected) >= max_points:
                break
            if not any(point is existing for existing in selected):
                selected.append(point)
    return sorted(selected[:max_points], key=lambda p: int(p.t_ms))


def plan_auto_zoom_actors(
    *,
    duration_ms: int,
    frame_w: int = 1920,
    frame_h: int = 1080,
    cursor_events: Iterable[CursorEvent | Mapping] | None = None,
    existing_actors: Iterable | None = None,
    max_actors: int = 5,
    zoom_scale: float = 1.78,
    zoom_duration_ms: int = 1900,
    zoom_easing: str = "smooth_pop",
    zoom_motion_blur: float = 0.18,
    zoom_focus_bias: float = 0.22,
    disabled_point_indexes: Iterable[int] | None = None,
    candidate_overrides: Mapping | None = None,
) -> list:
    from app.timeline_model import ZoomActor

    duration_ms = max(0, int(duration_ms))
    frame_w = max(16, int(frame_w or 1920))
    frame_h = max(16, int(frame_h or 1080))
    existing = list(existing_actors or [])
    max_id = max((int(getattr(z, "id", 0) or 0) for z in existing), default=0)
    if duration_ms <= 400:
        return []
    normalized_events = normalize_cursor_events(cursor_events)
    action_count = sum(
        1
        for ev in normalized_events
        if str(ev.kind or "").casefold() in {"click", "down", "release", "key", "hotkey", "drag"}
    )
    timing = screenstudio_zoom_timing_profile(
        duration_ms=duration_ms,
        event_count=len(normalized_events),
        action_count=action_count,
        max_actors=max_actors,
        zoom_duration_ms=zoom_duration_ms,
    )
    points = infer_action_points(
        normalized_events,
        duration_ms=duration_ms,
        max_points=int(timing["candidate_budget"]),
    )
    points = _rhythmic_action_points(
        points,
        duration_ms=duration_ms,
        max_points=int(timing["max_actors"]),
        min_gap_ms=int(timing["rhythm_gap_ms"]),
    )
    if not points:
        return []
    disabled = set()
    for raw in disabled_point_indexes or ():
        try:
            disabled.add(int(raw))
        except Exception:
            continue
    overrides: dict[int, Mapping] = {}
    if isinstance(candidate_overrides, Mapping):
        for raw_key, raw_value in candidate_overrides.items():
            if not isinstance(raw_value, Mapping):
                continue
            try:
                key = int(raw_key)
            except Exception:
                continue
            overrides[key] = raw_value
    zoom_scale = max(1.08, float(zoom_scale or 1.78))
    zoom_easing = str(zoom_easing or "smooth_pop")
    zoom_motion_blur = _clamp(float(zoom_motion_blur or 0.0), 0.0, 1.0)
    zoom_focus_bias = _clamp(float(zoom_focus_bias or 0.22), 0.12, 0.40)
    span = int(timing["zoom_duration_ms"])
    lead = int(timing["lead_ms"])
    actors: list[ZoomActor] = []

    def _overlap_shift(start: int, end: int) -> tuple[int, int] | None:
        span_local = max(1, end - start)
        all_actors = list(existing) + actors
        gap = int(timing["overlap_gap_ms"])

        def _overlaps(candidate_start: int, candidate_end: int) -> bool:
            for other in all_actors:
                a_start = int(getattr(other, "start_ms", 0) or 0)
                a_end = int(getattr(other, "end_ms", a_start) or a_start)
                if candidate_start < a_end + gap and a_start - gap < candidate_end:
                    return True
            return False

        if not _overlaps(start, end):
            return start, end
        for actor in list(existing) + actors:
            a_start = int(getattr(actor, "start_ms", 0) or 0)
            a_end = int(getattr(actor, "end_ms", a_start) or a_start)
            if start < a_end + gap and a_start - gap < end:
                shifted_start = min(max(0, a_end + gap), max(0, duration_ms - span_local))
                shifted_end = min(duration_ms, shifted_start + span_local)
                if shifted_end - shifted_start >= 450 and not _overlaps(shifted_start, shifted_end):
                    return shifted_start, shifted_end
                shifted_end = max(0, a_start - gap)
                shifted_start = max(0, shifted_end - span_local)
                if shifted_end - shifted_start >= 450 and not _overlaps(shifted_start, shifted_end):
                    return shifted_start, shifted_end
                return None
        return None

    def _edge_safe_rect(point: ActionPoint) -> tuple[int, int, int, int]:
        # Keep edge clicks readable. A hard-centered crop clamps at the source
        # boundary and leaves the cursor jammed against the zoom edge; a slightly
        # looser crop gives Screen Studio-like breathing room.
        px = _clamp(point.x_norm, 0.0, 1.0)
        py = _clamp(point.y_norm, 0.0, 1.0)
        edge_x = max(0.0, 0.18 - min(px, 1.0 - px)) / 0.18
        edge_y = max(0.0, 0.18 - min(py, 1.0 - py)) / 0.18
        kind = str(point.kind or "").casefold()
        if kind in {"click", "down", "hotkey", "key"}:
            kind_zoom = zoom_scale * 1.06
        elif kind in {"release"}:
            kind_zoom = zoom_scale * 1.02
        elif kind in {"fallback"}:
            kind_zoom = max(1.08, zoom_scale * 0.92)
        else:
            kind_zoom = max(1.08, zoom_scale * 0.96)
        target_w = max(16, min(frame_w, int(round(frame_w / kind_zoom))))
        target_h = max(16, min(frame_h, int(round(frame_h / kind_zoom))))
        local_w = max(16, min(frame_w, int(round(target_w * (1.0 + edge_x * 0.34)))))
        local_h = max(16, min(frame_h, int(round(target_h * (1.0 + edge_y * 0.30)))))
        cx = px * frame_w
        cy = py * frame_h
        active = point.kind in {"click", "down", "release", "key", "hotkey"}
        margin_x = zoom_focus_bias if active else max(0.12, zoom_focus_bias - 0.04)
        margin_y = max(0.12, zoom_focus_bias - (0.02 if active else 0.06))
        raw_x = cx - local_w * margin_x if px < 0.5 else cx - local_w * (1.0 - margin_x)
        raw_y = cy - local_h * margin_y if py < 0.5 else cy - local_h * (1.0 - margin_y)
        x = int(round(_clamp(raw_x, 0, frame_w - local_w)))
        y = int(round(_clamp(raw_y, 0, frame_h - local_h)))
        return x, y, local_w, local_h

    def _int_override(raw: Mapping, name: str, fallback: int) -> int:
        try:
            return int(raw.get(name, fallback))
        except Exception:
            return int(fallback)

    def _apply_override(
        point_index: int,
        start: int,
        end: int,
        x: int,
        y: int,
        local_w: int,
        local_h: int,
    ) -> tuple[int, int, int, int, int, int]:
        raw = overrides.get(int(point_index))
        if not raw:
            return start, end, x, y, local_w, local_h
        local_w = max(16, min(frame_w, _int_override(raw, "target_w", local_w)))
        local_h = max(16, min(frame_h, _int_override(raw, "target_h", local_h)))
        x = max(0, min(frame_w - local_w, _int_override(raw, "target_x", x)))
        y = max(0, min(frame_h - local_h, _int_override(raw, "target_y", y)))
        start = max(0, min(duration_ms, _int_override(raw, "start_ms", start)))
        end = max(0, min(duration_ms, _int_override(raw, "end_ms", end)))
        if end <= start:
            end = min(duration_ms, start + span)
        if end - start < 450:
            if end >= duration_ms:
                start = max(0, end - min(span, duration_ms))
            else:
                end = min(duration_ms, start + max(450, min(span, duration_ms)))
        return start, end, x, y, local_w, local_h

    for point_index, point in enumerate(points):
        if point_index in disabled:
            continue
        start = max(0, int(point.t_ms) - lead)
        end = min(duration_ms, start + span)
        if end - start < 600:
            start = max(0, end - min(span, duration_ms))
        x, y, local_w, local_h = _edge_safe_rect(point)
        start, end, x, y, local_w, local_h = _apply_override(
            point_index,
            start,
            end,
            x,
            y,
            local_w,
            local_h,
        )
        if end - start < 450:
            continue
        shifted = _overlap_shift(start, end)
        if shifted is None:
            continue
        start, end = shifted
        max_id += 1
        actor = ZoomActor(
            id=max_id,
            start_ms=start,
            end_ms=end,
            target_x=x,
            target_y=y,
            target_w=local_w,
            target_h=local_h,
            zoom_in_ms=min(560, max(220, (end - start) // 3)),
            zoom_out_ms=min(620, max(240, (end - start) // 3)),
            easing=zoom_easing,
            motion_blur=zoom_motion_blur,
        )
        try:
            actor.screenstudio_point_index = point_index
            actor.screenstudio_point_kind = point.kind
            actor.screenstudio_point_ms = int(point.t_ms)
            actor.screenstudio_point_x_norm = float(point.x_norm)
            actor.screenstudio_point_y_norm = float(point.y_norm)
        except Exception:
            pass
        actors.append(actor)
    return actors


def screenstudio_polish_payload(
    *,
    actor_ids: Iterable[int] = (),
    cursor_events: Iterable[CursorEvent | Mapping] | None = None,
    cursor_polish: Mapping | None = None,
    screen_polish: Mapping | None = None,
    preset_id: str | None = None,
) -> dict:
    events = normalize_cursor_events(cursor_events)
    cursor = dict(DEFAULT_CURSOR_POLISH)
    cursor.update(dict(cursor_polish or {}))
    screen = dict(DEFAULT_SCREEN_POLISH)
    screen.update(dict(screen_polish or {}))
    return {
        "version": 1,
        "source": "screenstudio_auto_polish",
        "preset_id": str(preset_id or ""),
        "auto_zoom_actor_ids": [int(i) for i in actor_ids],
        "cursor": cursor,
        "screen": screen,
        "static_cursor_hidden_intervals": [
            [int(s), int(e)]
            for s, e in static_cursor_hidden_intervals(
                events,
                hide_after_ms=int(cursor["hide_static_after_ms"]),
            )
        ],
    }


def _blend_overlay(base, overlay, alpha: float):
    import numpy as np

    alpha = _clamp(float(alpha), 0.0, 1.0)
    if alpha <= 0.0:
        return base
    return np.clip(
        base.astype(np.float32) * (1.0 - alpha)
        + overlay.astype(np.float32) * alpha,
        0,
        255,
    ).astype(np.uint8)


def _draw_scissors_cursor(rgb, x: int, y: int, size: int, *, accent_color: tuple[int, int, int], pressed: float, shadow_strength: float) -> None:
    import cv2
    import numpy as np

    size = max(14, int(size))
    pressed = _clamp(float(pressed), 0.0, 1.0)
    accent = tuple(int(_clamp(c, 0, 255)) for c in accent_color[:3])
    pivot = (int(x + size * 0.42), int(y + size * 0.45))
    blade_len = size * 0.74
    spread = math.radians(34.0 - 25.0 * pressed)
    base_angle = math.radians(-8.0)
    shadow_tone = int(round(22 * (1.0 - _clamp(shadow_strength, 0.0, 1.0))))
    shadow = (shadow_tone, shadow_tone, shadow_tone)

    def _pt(angle: float, distance: float) -> tuple[int, int]:
        return (
            int(round(pivot[0] + math.cos(angle) * distance)),
            int(round(pivot[1] + math.sin(angle) * distance)),
        )

    def _blade(angle: float, offset: int, color: tuple[int, int, int]) -> None:
        tip = _pt(angle, blade_len)
        back = _pt(angle + math.pi, size * 0.20)
        normal = angle + math.pi / 2.0
        pts = np.array(
            [
                [tip[0] + offset, tip[1] + offset],
                [int(round(back[0] + math.cos(normal) * size * 0.08)) + offset, int(round(back[1] + math.sin(normal) * size * 0.08)) + offset],
                [int(round(pivot[0] + math.cos(normal) * size * 0.035)) + offset, int(round(pivot[1] + math.sin(normal) * size * 0.035)) + offset],
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(rgb, [pts], color, cv2.LINE_AA)
        cv2.polylines(rgb, [pts], True, (26, 29, 42), max(1, size // 18), cv2.LINE_AA)

    _blade(base_angle - spread, 3, shadow)
    _blade(base_angle + spread, 3, shadow)
    _blade(base_angle - spread, 0, (238, 242, 255))
    _blade(base_angle + spread, 0, (250, 251, 255))
    cv2.circle(rgb, pivot, max(3, size // 10), accent, -1, cv2.LINE_AA)
    cv2.circle(rgb, pivot, max(3, size // 10), (255, 255, 255), max(1, size // 24), cv2.LINE_AA)

    handle_a = _pt(base_angle + math.pi - spread * 0.35, size * 0.42)
    handle_b = _pt(base_angle + math.pi + spread * 0.35, size * 0.42)
    for cx, cy in (handle_a, handle_b):
        cv2.circle(rgb, (cx + 3, cy + 3), max(5, size // 6), shadow, max(2, size // 12), cv2.LINE_AA)
        cv2.circle(rgb, (cx, cy), max(5, size // 6), accent, max(2, size // 11), cv2.LINE_AA)
        cv2.circle(rgb, (cx, cy), max(2, size // 13), (255, 255, 255), max(1, size // 28), cv2.LINE_AA)


def _draw_ibeam_cursor(rgb, x: int, y: int, size: int, *, accent_color: tuple[int, int, int], pressed: float, shadow_strength: float) -> None:
    import cv2

    size = max(14, int(size))
    accent = tuple(int(_clamp(c, 0, 255)) for c in accent_color[:3])
    shadow_tone = int(round(22 * (1.0 - _clamp(shadow_strength, 0.0, 1.0))))
    dx = int(round(size * 0.20))
    top = int(y)
    bottom = int(y + size * (1.15 - 0.06 * _clamp(pressed, 0.0, 1.0)))
    cx = int(x + size * 0.16)
    thickness = max(2, size // 10)
    cv2.line(rgb, (cx + 2, top + 3), (cx + 2, bottom + 3), (shadow_tone, shadow_tone, shadow_tone), thickness + 2, cv2.LINE_AA)
    cv2.line(rgb, (cx, top), (cx, bottom), accent, thickness, cv2.LINE_AA)
    cv2.line(rgb, (cx - dx, top), (cx + dx, top), (255, 255, 255), thickness, cv2.LINE_AA)
    cv2.line(rgb, (cx - dx, bottom), (cx + dx, bottom), (255, 255, 255), thickness, cv2.LINE_AA)


def _draw_zoom_cursor(rgb, x: int, y: int, size: int, *, accent_color: tuple[int, int, int], pressed: float, shadow_strength: float) -> None:
    import cv2

    size = max(14, int(size))
    accent = tuple(int(_clamp(c, 0, 255)) for c in accent_color[:3])
    radius = max(5, int(round(size * (0.33 + 0.04 * _clamp(pressed, 0.0, 1.0)))))
    cx = int(x + radius)
    cy = int(y + radius)
    thickness = max(2, size // 11)
    shadow_tone = int(round(22 * (1.0 - _clamp(shadow_strength, 0.0, 1.0))))
    cv2.circle(rgb, (cx + 3, cy + 3), radius, (shadow_tone, shadow_tone, shadow_tone), thickness + 2, cv2.LINE_AA)
    cv2.circle(rgb, (cx, cy), radius, (255, 255, 255), thickness + 1, cv2.LINE_AA)
    cv2.circle(rgb, (cx, cy), radius, accent, max(1, thickness - 1), cv2.LINE_AA)
    cv2.line(rgb, (cx + int(radius * 0.70), cy + int(radius * 0.70)), (cx + int(radius * 1.48), cy + int(radius * 1.48)), (255, 255, 255), thickness + 2, cv2.LINE_AA)
    cv2.line(rgb, (cx + int(radius * 0.70), cy + int(radius * 0.70)), (cx + int(radius * 1.48), cy + int(radius * 1.48)), accent, thickness, cv2.LINE_AA)
    cv2.line(rgb, (cx - int(radius * 0.45), cy), (cx + int(radius * 0.45), cy), (255, 255, 255), max(1, thickness - 1), cv2.LINE_AA)
    cv2.line(rgb, (cx, cy - int(radius * 0.45)), (cx, cy + int(radius * 0.45)), (255, 255, 255), max(1, thickness - 1), cv2.LINE_AA)


def _draw_hand_cursor(rgb, x: int, y: int, size: int, *, accent_color: tuple[int, int, int], pressed: float, shadow_strength: float) -> None:
    import cv2

    size = max(14, int(size))
    accent = tuple(int(_clamp(c, 0, 255)) for c in accent_color[:3])
    pressed = _clamp(float(pressed), 0.0, 1.0)
    palm = (int(x + size * 0.36), int(y + size * (0.76 + 0.035 * pressed)))
    finger_top = int(y + size * (0.09 + 0.08 * pressed))
    shadow_tone = int(round(24 * (1.0 - _clamp(shadow_strength, 0.0, 1.0))))
    thickness = max(3, size // 8)
    skin = (255, 249, 235)
    outline = (24, 28, 40)
    for dx, dy, color, extra in ((3, 3, (shadow_tone, shadow_tone, shadow_tone), 2), (0, 0, skin, 0)):
        cv2.line(rgb, (palm[0] + dx, finger_top + dy), (palm[0] + dx, palm[1] + dy), color, thickness + extra, cv2.LINE_AA)
        for i, off in enumerate((-0.16, 0.03, 0.22)):
            fx = int(palm[0] + size * off) + dx
            top = int(y + size * (0.24 + 0.045 * i + 0.035 * pressed)) + dy
            cv2.line(rgb, (fx, top), (fx, palm[1] + dy), color, max(2, thickness - 1) + extra, cv2.LINE_AA)
        cv2.ellipse(rgb, (palm[0] + dx, palm[1] + dy), (int(size * 0.30), int(size * 0.24)), 0, 0, 360, color, -1, cv2.LINE_AA)
    cv2.circle(rgb, (palm[0] + int(size * 0.24), palm[1] - int(size * 0.02)), max(3, size // 10), accent, -1, cv2.LINE_AA)
    cv2.ellipse(rgb, palm, (int(size * 0.30), int(size * 0.24)), 0, 0, 360, outline, max(1, size // 22), cv2.LINE_AA)


def _draw_trim_cursor(rgb, x: int, y: int, size: int, *, accent_color: tuple[int, int, int], pressed: float, shadow_strength: float, direction: str = "both") -> None:
    import cv2
    import numpy as np

    size = max(14, int(size))
    accent = tuple(int(_clamp(c, 0, 255)) for c in accent_color[:3])
    cx = int(x + size * 0.42)
    cy = int(y + size * 0.54)
    half = int(size * (0.30 + 0.06 * _clamp(pressed, 0.0, 1.0)))
    thickness = max(2, size // 10)
    shadow_tone = int(round(22 * (1.0 - _clamp(shadow_strength, 0.0, 1.0))))
    cv2.line(rgb, (cx + 3, cy + 3 - half), (cx + 3, cy + 3 + half), (shadow_tone, shadow_tone, shadow_tone), thickness + 1, cv2.LINE_AA)
    cv2.line(rgb, (cx, cy - half), (cx, cy + half), (255, 255, 255), thickness + 1, cv2.LINE_AA)
    cv2.line(rgb, (cx, cy - half), (cx, cy + half), accent, max(1, thickness - 1), cv2.LINE_AA)
    arrows: list[tuple[int, np.ndarray]] = []
    if direction in {"both", "left"}:
        arrows.append((-1, np.array([[cx - half, cy], [cx - int(half * 0.45), cy - int(half * 0.45)], [cx - int(half * 0.45), cy + int(half * 0.45)]], dtype=np.int32)))
    if direction in {"both", "right"}:
        arrows.append((1, np.array([[cx + half, cy], [cx + int(half * 0.45), cy - int(half * 0.45)], [cx + int(half * 0.45), cy + int(half * 0.45)]], dtype=np.int32)))
    for _sign, pts in arrows:
        cv2.fillPoly(rgb, [pts + np.array([2, 2], dtype=np.int32)], (shadow_tone, shadow_tone, shadow_tone), cv2.LINE_AA)
        cv2.fillPoly(rgb, [pts], accent, cv2.LINE_AA)


def _draw_magic_cursor(rgb, x: int, y: int, size: int, *, accent_color: tuple[int, int, int], pressed: float, shadow_strength: float) -> None:
    import cv2

    size = max(14, int(size))
    accent = tuple(int(_clamp(c, 0, 255)) for c in accent_color[:3])
    x0 = int(x + size * 0.12)
    y0 = int(y + size * 0.12)
    x1 = int(x + size * 0.78)
    y1 = int(y + size * 0.78)
    thickness = max(2, size // 11)
    cv2.line(rgb, (x0 + 3, y0 + 3), (x1 + 3, y1 + 3), (18, 18, 24), thickness + 2, cv2.LINE_AA)
    cv2.line(rgb, (x0, y0), (x1, y1), (255, 255, 255), thickness + 1, cv2.LINE_AA)
    cv2.line(rgb, (x0, y0), (x1, y1), accent, thickness, cv2.LINE_AA)
    pulse = 1.0 + 0.22 * math.sin(math.pi * _clamp(pressed, 0.0, 1.0))
    for sx, sy in ((x0, y0), (x1, y1), (int(x + size * 0.28), int(y + size * 0.84))):
        r = max(2, int(size * 0.055 * pulse))
        cv2.line(rgb, (sx - r * 2, sy), (sx + r * 2, sy), (255, 255, 255), max(1, r), cv2.LINE_AA)
        cv2.line(rgb, (sx, sy - r * 2), (sx, sy + r * 2), (255, 255, 255), max(1, r), cv2.LINE_AA)
        cv2.circle(rgb, (sx, sy), r, accent, -1, cv2.LINE_AA)


def _draw_color_picker_cursor(rgb, x: int, y: int, size: int, *, accent_color: tuple[int, int, int], pressed: float, shadow_strength: float) -> None:
    import cv2

    size = max(14, int(size))
    accent = tuple(int(_clamp(c, 0, 255)) for c in accent_color[:3])
    thickness = max(2, size // 11)
    x0 = int(x + size * 0.18)
    y0 = int(y + size * 0.16)
    x1 = int(x + size * 0.72)
    y1 = int(y + size * 0.70)
    cv2.line(rgb, (x0 + 3, y0 + 3), (x1 + 3, y1 + 3), (18, 18, 24), thickness + 2, cv2.LINE_AA)
    cv2.line(rgb, (x0, y0), (x1, y1), (255, 255, 255), thickness + 1, cv2.LINE_AA)
    cv2.line(rgb, (x0, y0), (x1, y1), accent, thickness, cv2.LINE_AA)
    cv2.circle(rgb, (x0, y0), max(4, size // 8), (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(rgb, (x0, y0), max(4, size // 8), accent, max(1, thickness - 1), cv2.LINE_AA)
    cv2.circle(rgb, (x1, y1), max(3, size // 10), accent, -1, cv2.LINE_AA)


def _draw_cursor_shape(
    rgb,
    x: int,
    y: int,
    size: int,
    *,
    accent_color: tuple[int, int, int] = (255, 106, 61),
    pressed: float = 0.0,
    supersample: int = 1,
    shadow_strength: float = 0.74,
    cursor_style: str = "pointer",
):
    import cv2
    import numpy as np

    size = max(10, int(size))
    supersample = max(1, min(4, int(supersample or 1)))
    if supersample > 1 and hasattr(rgb, "shape") and len(rgb.shape) >= 2:
        h, w = rgb.shape[:2]
        pad = max(8, int(round(size * 0.42)))
        x0 = max(0, int(x) - pad)
        y0 = max(0, int(y) - pad)
        x1 = min(w, int(x) + int(size * 1.22) + pad)
        y1 = min(h, int(y) + int(size * 1.32) + pad)
        if x1 > x0 + 2 and y1 > y0 + 2:
            crop = rgb[y0:y1, x0:x1]
            hi_w = max(2, int(crop.shape[1]) * supersample)
            hi_h = max(2, int(crop.shape[0]) * supersample)
            hi = cv2.resize(crop, (hi_w, hi_h), interpolation=cv2.INTER_CUBIC)
            _draw_cursor_shape(
                hi,
                (int(x) - x0) * supersample,
                (int(y) - y0) * supersample,
                size * supersample,
                accent_color=accent_color,
                pressed=pressed,
                supersample=1,
                shadow_strength=shadow_strength,
                cursor_style=cursor_style,
            )
            rgb[y0:y1, x0:x1] = cv2.resize(hi, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_AREA)
            return
    pressed = _clamp(float(pressed), 0.0, 1.0)
    shadow_strength = _clamp(float(shadow_strength), 0.0, 1.0)
    accent_color = tuple(int(_clamp(c, 0, 255)) for c in accent_color[:3])
    style = normalize_cursor_style(cursor_style)
    if style == "scissors":
        _draw_scissors_cursor(rgb, x, y, size, accent_color=accent_color, pressed=pressed, shadow_strength=shadow_strength)
        return
    if style in {"hand", "grab"}:
        _draw_hand_cursor(rgb, x, y, size, accent_color=accent_color, pressed=pressed, shadow_strength=shadow_strength)
        return
    if style == "ibeam":
        _draw_ibeam_cursor(rgb, x, y, size, accent_color=accent_color, pressed=pressed, shadow_strength=shadow_strength)
        return
    if style == "zoom":
        _draw_zoom_cursor(rgb, x, y, size, accent_color=accent_color, pressed=pressed, shadow_strength=shadow_strength)
        return
    if style in {"trim", "trim_left", "trim_right", "slide"}:
        direction = "left" if style == "trim_left" else "right" if style == "trim_right" else "both"
        _draw_trim_cursor(rgb, x, y, size, accent_color=accent_color, pressed=pressed, shadow_strength=shadow_strength, direction=direction)
        return
    if style == "magic_ai":
        _draw_magic_cursor(rgb, x, y, size, accent_color=accent_color, pressed=pressed, shadow_strength=shadow_strength)
        return
    if style == "color_picker":
        _draw_color_picker_cursor(rgb, x, y, size, accent_color=accent_color, pressed=pressed, shadow_strength=shadow_strength)
        return
    if pressed > 0.001:
        y += int(round(size * 0.045 * pressed))
    pts = np.array(
        [
            [x, y],
            [x + int(size * 0.78), y + int(size * 0.58)],
            [x + int(size * 0.44), y + int(size * 0.66)],
            [x + int(size * 0.61), y + int(size * 1.04)],
            [x + int(size * 0.40), y + int(size * 1.13)],
            [x + int(size * 0.25), y + int(size * 0.74)],
            [x + int(size * 0.02), y + int(size * 0.96)],
        ],
        dtype=np.int32,
    )
    shadow = pts + np.array([2, 3], dtype=np.int32)
    shadow_tone = int(round(24 * (1.0 - shadow_strength)))
    cv2.fillPoly(rgb, [shadow], (shadow_tone, shadow_tone, shadow_tone))
    cv2.polylines(rgb, [shadow], True, (shadow_tone, shadow_tone, shadow_tone), max(2, size // 9), cv2.LINE_AA)
    cv2.fillPoly(rgb, [pts], (255, 255, 255))
    cv2.polylines(rgb, [pts], True, (20, 22, 32), max(1, size // 12), cv2.LINE_AA)
    accent = np.array(
        [
            [x + int(size * 0.40), y + int(size * 0.66)],
            [x + int(size * 0.61), y + int(size * 1.04)],
            [x + int(size * 0.50), y + int(size * 1.09)],
            [x + int(size * 0.32), y + int(size * 0.70)],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(rgb, [accent], accent_color)


def _draw_rounded_rect(rgb, x0: int, y0: int, x1: int, y1: int, radius: int, color: tuple[int, int, int], thickness: int = -1) -> None:
    import cv2

    x0, x1 = sorted((int(x0), int(x1)))
    y0, y1 = sorted((int(y0), int(y1)))
    if x1 <= x0 or y1 <= y0:
        return
    radius = max(0, min(int(radius), (x1 - x0) // 2, (y1 - y0) // 2))
    color = tuple(int(_clamp(c, 0, 255)) for c in color[:3])
    if radius <= 1:
        cv2.rectangle(rgb, (x0, y0), (x1, y1), color, thickness, cv2.LINE_AA)
        return
    if thickness < 0:
        cv2.rectangle(rgb, (x0 + radius, y0), (x1 - radius, y1), color, -1, cv2.LINE_AA)
        cv2.rectangle(rgb, (x0, y0 + radius), (x1, y1 - radius), color, -1, cv2.LINE_AA)
        cv2.circle(rgb, (x0 + radius, y0 + radius), radius, color, -1, cv2.LINE_AA)
        cv2.circle(rgb, (x1 - radius, y0 + radius), radius, color, -1, cv2.LINE_AA)
        cv2.circle(rgb, (x0 + radius, y1 - radius), radius, color, -1, cv2.LINE_AA)
        cv2.circle(rgb, (x1 - radius, y1 - radius), radius, color, -1, cv2.LINE_AA)
        return
    cv2.line(rgb, (x0 + radius, y0), (x1 - radius, y0), color, thickness, cv2.LINE_AA)
    cv2.line(rgb, (x0 + radius, y1), (x1 - radius, y1), color, thickness, cv2.LINE_AA)
    cv2.line(rgb, (x0, y0 + radius), (x0, y1 - radius), color, thickness, cv2.LINE_AA)
    cv2.line(rgb, (x1, y0 + radius), (x1, y1 - radius), color, thickness, cv2.LINE_AA)
    cv2.ellipse(rgb, (x0 + radius, y0 + radius), (radius, radius), 180, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(rgb, (x1 - radius, y0 + radius), (radius, radius), 270, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(rgb, (x1 - radius, y1 - radius), (radius, radius), 0, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(rgb, (x0 + radius, y1 - radius), (radius, radius), 90, 0, 90, color, thickness, cv2.LINE_AA)


def _cursor_duration_from_owner(owner, events: Sequence[CursorEvent]) -> int:
    candidates: list[int] = []
    if owner is not None:
        for name in (
            "effective_source_out_ms",
            "source_out_ms",
            "source_duration_ms",
            "duration_ms",
            "effective_length_ms",
        ):
            try:
                value = int(getattr(owner, name, 0) or 0)
            except Exception:
                continue
            if value > 0:
                candidates.append(value)
    if events:
        candidates.append(max(ev.t_ms for ev in events) + 1000)
    return max(candidates, default=0)


def apply_cursor_fx_rgb(
    rgb,
    source_ms: int,
    *,
    owner=None,
    project_settings: Mapping | None = None,
):
    events = normalize_cursor_events(getattr(owner, "cursor_events", []) if owner is not None else [])
    if not events and owner is not None:
        events = load_cursor_sidecar(getattr(owner, "source_path", None))
        if events:
            try:
                owner.cursor_events = [event.to_dict() for event in events[:2000]]
            except Exception:
                pass
    if not events:
        return rgb
    payload = _merged_polish(owner, project_settings)
    cursor = payload.get("cursor", {})
    state = cursor_state_at(
        events,
        int(source_ms),
        smoothing=float(cursor.get("cursor_smoothing", 0.72)),
        motion_easing=str(cursor.get("motion_easing", "smooth") or "smooth"),
        hide_after_ms=int(cursor.get("hide_static_after_ms", 900)),
        click_ring_ms=int(cursor.get("click_ring_ms", 420)),
        click_hold_ms=int(cursor.get("click_hold_ms", 110)),
        drag_trail_ms=int(cursor.get("drag_trail_ms", 620)),
        duration_ms=_cursor_duration_from_owner(owner, events),
        loop_cursor=bool(cursor.get("loop_cursor", False)),
        loop_return_ms=int(cursor.get("loop_return_ms", 900)),
    )
    if state is None:
        return rgb
    import cv2
    import numpy as np

    out = np.ascontiguousarray(rgb.copy())
    h, w = out.shape[:2]
    trail = list(state.get("trail") or [])
    if len(trail) >= 2:
        color = _hex_to_rgb(str(cursor.get("click_ring_color", "#FF6A3D")), (255, 106, 61))
        overlay = out.copy()
        pts = [
            (
                int(round(float(item["x_norm"]) * w)),
                int(round(float(item["y_norm"]) * h)),
                float(item.get("progress", 0.0)),
            )
            for item in trail[-12:]
        ]
        for idx in range(1, len(pts)):
            x0, y0, p0 = pts[idx - 1]
            x1, y1, p1 = pts[idx]
            alpha = _clamp(1.0 - max(p0, p1), 0.0, 1.0)
            thickness = max(2, int(round(min(w, h) * (0.004 + 0.006 * alpha))))
            cv2.line(overlay, (x0, y0), (x1, y1), color, thickness, cv2.LINE_AA)
        for x0, y0, progress in pts[-8:]:
            alpha = _clamp(1.0 - progress, 0.0, 1.0)
            if alpha <= 0.03:
                continue
            radius = max(2, int(round(min(w, h) * (0.005 + 0.010 * alpha))))
            cv2.circle(overlay, (x0, y0), radius, color, -1, cv2.LINE_AA)
            cv2.circle(overlay, (x0, y0), max(1, radius // 3), (255, 255, 255), -1, cv2.LINE_AA)
        out = _blend_overlay(out, overlay, 0.46)
    click = state.get("click")
    focus_source = click or (state if bool(state.get("visible", True)) else None)
    if focus_source:
        fx = int(round(float(focus_source.get("x_norm", state["x_norm"])) * w))
        fy = int(round(float(focus_source.get("y_norm", state["y_norm"])) * h))
        base = min(w, h)
        progress = _clamp(float(focus_source.get("progress", 1.0)), 0.0, 1.0) if click else 1.0
        glow_strength = _clamp(float(cursor.get("cursor_focus_glow", 0.18) or 0.0), 0.0, 0.55)
        if click:
            glow_strength += 0.22 * (1.0 - progress) ** 1.3
        if glow_strength > 0.001:
            color = _hex_to_rgb(str(cursor.get("click_ring_color", "#FF6A3D")), (255, 106, 61))
            focus = out.copy()
            halo_r = max(10, int(round(base * (0.050 + (0.060 if click else 0.025) * (1.0 - progress)))))
            cv2.circle(focus, (fx, fy), halo_r, color, -1, cv2.LINE_AA)
            blur_k = max(9, int(round(halo_r * 0.95)))
            if blur_k % 2 == 0:
                blur_k += 1
            focus = cv2.GaussianBlur(focus, (blur_k, blur_k), 0)
            out = _blend_overlay(out, focus, min(0.42, glow_strength))
    if click:
        cx = int(round(float(click["x_norm"]) * w))
        cy = int(round(float(click["y_norm"]) * h))
        progress = _clamp(float(click["progress"]), 0.0, 1.0)
        color = _hex_to_rgb(str(cursor.get("click_ring_color", "#FF6A3D")), (255, 106, 61))
        release = str(click.get("kind") or "") == "release"
        base = min(w, h)
        ring_t = _ease_out_cubic(progress)
        pop = _clamp(float(cursor.get("click_pop", 0.22) or 0.0), 0.0, 0.48)
        strength = _clamp(float(cursor.get("click_ring_strength", 1.15) or 1.0), 0.35, 1.8)
        pop_t = math.sin(math.pi * min(1.0, progress * 1.08)) * pop
        radius = int(round((0.014 + (0.044 if release else 0.066) * ring_t + 0.015 * pop_t) * base))
        radius = max(5, radius)
        thickness = max(2, int(round(base * 0.006)))
        glow = out.copy()
        core = out.copy()
        spark = out.copy()
        fade = (1.0 - progress) ** 1.45
        outer_alpha = min(0.82, (0.38 if release else 0.58) * fade * strength)
        mid_alpha = min(0.92, (0.62 if release else 0.86) * (1.0 - progress * 0.48) * strength)
        wash = out.copy()
        cv2.circle(wash, (cx, cy), max(6, int(radius * 0.82)), color, -1, cv2.LINE_AA)
        out = _blend_overlay(out, wash, min(0.34, 0.18 * strength * (1.0 - progress * 0.55)))
        cv2.circle(glow, (cx, cy), max(8, int(radius * (1.95 + 0.35 * pop_t))), color, max(3, thickness * 3), cv2.LINE_AA)
        cv2.circle(glow, (cx, cy), max(6, int(radius * (1.30 + 0.22 * pop_t))), color, max(2, thickness * 2), cv2.LINE_AA)
        out = _blend_overlay(out, glow, outer_alpha)
        cv2.circle(core, (cx, cy), radius, color, thickness, cv2.LINE_AA)
        if release:
            cv2.circle(core, (cx, cy), max(4, int(radius * 0.42)), (255, 255, 255), thickness, cv2.LINE_AA)
        else:
            core_radius = max(3, int(radius * (0.24 + 0.14 * (1.0 - progress))))
            cv2.circle(core, (cx, cy), core_radius, color, -1, cv2.LINE_AA)
            cv2.circle(core, (cx - max(1, radius // 4), cy - max(1, radius // 4)), max(2, radius // 8), (255, 255, 255), -1, cv2.LINE_AA)
        out = _blend_overlay(out, core, mid_alpha)
        sparkle_angles = (math.pi * 0.15, math.pi * 0.82, math.pi * 1.45, math.pi * 1.92)
        for angle in sparkle_angles:
            px = int(round(cx + math.cos(angle) * radius * 1.18))
            py = int(round(cy + math.sin(angle) * radius * 1.18))
            sparkle_size = max(1, int(thickness * (1.0 + 0.8 * (1.0 - progress))))
            cv2.circle(spark, (px, py), sparkle_size, (255, 255, 255), -1, cv2.LINE_AA)
        out = _blend_overlay(out, spark, max(0.0, 0.30 * (1.0 - progress) ** 1.2))
    key = state.get("key")
    if key:
        progress = _clamp(float(key.get("progress", 0.0)), 0.0, 1.0)
        cx = int(round(float(key.get("x_norm", state["x_norm"])) * w))
        cy = int(round(float(key.get("y_norm", state["y_norm"])) * h))
        label = str(key.get("label") or "KEY")[:40]
        base = min(w, h)
        bounce = 1.0 + 0.065 * math.sin(math.pi * min(1.0, progress * 1.35)) * (1.0 - progress * 0.35)
        badge_h = max(22, int(base * 0.048 * bounce))
        font_scale = max(0.34, badge_h / 54.0)
        text_size, _baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        badge_w = max(46, int(base * 0.11), int(text_size[0]) + int(badge_h * 0.78))
        x0 = max(6, min(w - badge_w - 6, cx + int(base * 0.04)))
        y0 = max(6, min(h - badge_h - 6, cy - int(base * 0.07) - int(8 * (1.0 - progress))))
        overlay = out.copy()
        glow = out.copy()
        radius = max(8, int(round(badge_h * 0.42)))
        _draw_rounded_rect(glow, x0 - 3, y0 - 3, x0 + badge_w + 3, y0 + badge_h + 3, radius + 3, (139, 120, 255), -1)
        glow = cv2.GaussianBlur(glow, (max(9, radius * 2 + 1), max(9, radius * 2 + 1)), 0)
        out = _blend_overlay(out, glow, 0.20 * (1.0 - progress * 0.45))
        _draw_rounded_rect(overlay, x0, y0, x0 + badge_w, y0 + badge_h, radius, (18, 22, 38), -1)
        glass = overlay.copy()
        _draw_rounded_rect(glass, x0 + 2, y0 + 2, x0 + badge_w - 2, y0 + max(y0 + 4, y0 + badge_h // 2), max(4, radius - 2), (58, 66, 105), -1)
        overlay = _blend_overlay(overlay, glass, 0.34)
        _draw_rounded_rect(overlay, x0, y0, x0 + badge_w, y0 + badge_h, radius, (139, 120, 255), max(1, int(round(base * 0.0035))))
        cv2.putText(
            overlay,
            label,
            (x0 + max(9, int(badge_h * 0.32)), y0 + int(badge_h * 0.68)),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        out = _blend_overlay(out, overlay, 0.78 * (1.0 - progress * 0.35))
    if not bool(state.get("visible", True)):
        return np.ascontiguousarray(out)
    x = int(round(float(state["x_norm"]) * w))
    y = int(round(float(state["y_norm"]) * h))
    scale = float(cursor.get("cursor_scale", 1.35) or 1.35)
    click_pulse = 0.0
    if click:
        progress = _clamp(float(click.get("progress", 1.0)), 0.0, 1.0)
        click_pulse = max(0.0, math.sin(math.pi * min(1.0, progress * 1.7))) * _clamp(
            float(cursor.get("click_pop", 0.22) or 0.0),
            0.0,
            0.48,
        )
    size = int(round(min(w, h) * 0.045 * max(0.55, min(3.0, scale + click_pulse))))
    accent_color = _hex_to_rgb(str(cursor.get("click_ring_color", "#FF6A3D")), (255, 106, 61))
    pressed = 0.0
    if click:
        pressed = max(0.0, 1.0 - _clamp(float(click.get("progress", 1.0)), 0.0, 1.0) * 1.8)
    cursor_style = normalize_cursor_style(
        str((click or {}).get("cursor_style") or state.get("cursor_style") or cursor.get("cursor_style") or "pointer")
    )
    if cursor_style == "scissors":
        size = int(round(size * 1.12))
    elif cursor_style in {"ibeam", "zoom", "magic_ai"}:
        size = int(round(size * 0.98))
    _draw_cursor_shape(
        out,
        x,
        y,
        size,
        accent_color=accent_color,
        pressed=pressed,
        supersample=int(cursor.get("supersample", 3) or 1),
        shadow_strength=float(cursor.get("shadow_strength", 0.74) or 0.0),
        cursor_style=cursor_style,
    )
    return np.ascontiguousarray(out)


_BACKGROUND_CACHE: dict[tuple[int, int, str], object] = {}


def _wallpaper_background(width: int, height: int, palette: str = "wallpaper-gradient"):
    import numpy as np

    palette = str(palette or "wallpaper-gradient")
    key = (max(1, int(width)), max(1, int(height)), palette)
    cached = _BACKGROUND_CACHE.get(key)
    if cached is not None:
        return cached.copy()
    x = np.linspace(0.0, 1.0, max(1, width), dtype=np.float32)[None, :]
    y = np.linspace(0.0, 1.0, max(1, height), dtype=np.float32)[:, None]
    palettes = {
        "wallpaper-gradient": ([17, 20, 36], [80, 66, 220], [255, 105, 75], [54, 215, 215]),
        "candy-sky": ([18, 24, 48], [85, 150, 255], [255, 124, 184], [92, 235, 216]),
        "product-warm": ([25, 22, 32], [117, 76, 210], [255, 137, 84], [255, 219, 123]),
        "cursor-focus": ([10, 14, 28], [62, 73, 218], [139, 120, 255], [255, 106, 61]),
        "vertical-pop": ([13, 18, 38], [37, 189, 228], [255, 124, 184], [255, 183, 91]),
        "clean-dark": ([10, 12, 20], [29, 34, 58], [71, 82, 128], [120, 126, 170]),
    }
    c1, c2, c3, c4 = [
        np.array(color, dtype=np.float32)
        for color in palettes.get(palette, palettes["wallpaper-gradient"])
    ]
    mix_a = x * 0.72 + y * 0.28
    mix_b = np.clip(1.0 - np.sqrt((x - 0.84) ** 2 + (y - 0.18) ** 2) * 1.8, 0.0, 1.0)
    mix_c = np.clip(1.0 - np.sqrt((x - 0.18) ** 2 + (y - 0.88) ** 2) * 1.6, 0.0, 1.0)
    bg = c1 * (1.0 - mix_a[..., None]) + c2 * mix_a[..., None]
    bg = bg * (1.0 - mix_b[..., None] * 0.55) + c3 * (mix_b[..., None] * 0.55)
    bg = bg * (1.0 - mix_c[..., None] * 0.35) + c4 * (mix_c[..., None] * 0.35)
    result = np.clip(bg, 0, 255).astype(np.uint8)
    _BACKGROUND_CACHE[key] = result
    while len(_BACKGROUND_CACHE) > 8:
        _BACKGROUND_CACHE.pop(next(iter(_BACKGROUND_CACHE)))
    return result.copy()


def apply_screen_frame_style_rgb(
    rgb,
    *,
    owner=None,
    project_settings: Mapping | None = None,
    target_size: tuple[int, int] | None = None,
):
    style_enabled = bool(getattr(owner, "screenstudio_polish", None)) if owner is not None else False
    if project_settings:
        style_enabled = style_enabled or bool(project_settings.get("screenstudio_polish"))
    if not style_enabled:
        return rgb
    payload = _merged_polish(owner, project_settings)
    screen = payload.get("screen", {})
    padding = _clamp(float(screen.get("padding", 0.08) or 0.0), 0.0, 0.32)
    shadow = _clamp(float(screen.get("shadow", 0.55) or 0.0), 0.0, 1.0)
    radius = _clamp(float(screen.get("corner_radius", 0.035) or 0.0), 0.0, 0.12)
    if padding <= 0.001 and shadow <= 0.001 and radius <= 0.001 and target_size is None:
        return rgb
    import cv2
    import numpy as np

    src_h, src_w = rgb.shape[:2]
    out_w, out_h = target_size if target_size is not None else (src_w, src_h)
    out_w = max(16, int(out_w))
    out_h = max(16, int(out_h))
    bg = _wallpaper_background(out_w, out_h, str(screen.get("background", "wallpaper-gradient")))
    max_w = max(1, int(out_w * (1.0 - padding * 2.0)))
    max_h = max(1, int(out_h * (1.0 - padding * 2.0)))
    fit = min(max_w / max(1, src_w), max_h / max(1, src_h))
    # Vertical screen recordings should feel intentionally framed, not like a
    # tiny landscape postage stamp. Keep some air for captions, but use width.
    if str(screen.get("vertical_mode", "auto")) == "auto" and out_h > out_w and src_w > src_h:
        fit = min(fit, out_w * 0.92 / max(1, src_w))
    fit = max(0.05, min(1.0, fit))
    dst_w = max(2, int(round(src_w * fit)))
    dst_h = max(2, int(round(src_h * fit)))
    x0 = (out_w - dst_w) // 2
    y0 = (out_h - dst_h) // 2
    if out_h > out_w and src_w > src_h:
        y0 = int(out_h * 0.18)
    resized = cv2.resize(rgb, (dst_w, dst_h), interpolation=cv2.INTER_LINEAR)
    canvas = bg
    radius_px = int(round(min(dst_w, dst_h) * radius))
    clip_mask = None
    if radius_px > 1:
        r = max(1, min(radius_px, dst_w // 2, dst_h // 2))
        clip_mask = np.zeros((dst_h, dst_w), dtype=np.uint8)
        cv2.rectangle(clip_mask, (r, 0), (dst_w - r - 1, dst_h - 1), 255, -1)
        cv2.rectangle(clip_mask, (0, r), (dst_w - 1, dst_h - r - 1), 255, -1)
        cv2.circle(clip_mask, (r, r), r, 255, -1)
        cv2.circle(clip_mask, (dst_w - r - 1, r), r, 255, -1)
        cv2.circle(clip_mask, (r, dst_h - r - 1), r, 255, -1)
        cv2.circle(clip_mask, (dst_w - r - 1, dst_h - r - 1), r, 255, -1)
    if shadow > 0.0:
        shadow_layer = np.zeros_like(canvas)
        sx0 = min(out_w - 1, max(0, x0 + int(out_w * 0.012)))
        sy0 = min(out_h - 1, max(0, y0 + int(out_h * 0.018)))
        sx1 = min(out_w, sx0 + dst_w)
        sy1 = min(out_h, sy0 + dst_h)
        if clip_mask is not None and sx1 - sx0 == dst_w and sy1 - sy0 == dst_h:
            shadow_layer[sy0:sy1, sx0:sx1] = (clip_mask[..., None] > 0).astype(np.uint8) * 16
        else:
            shadow_layer[sy0:sy1, sx0:sx1] = 16
        blur = max(7, int(round(min(out_w, out_h) * 0.035)) | 1)
        shadow_layer = cv2.GaussianBlur(shadow_layer, (blur, blur), 0)
        canvas = _blend_overlay(canvas, shadow_layer, 0.34 * shadow)
    if clip_mask is not None:
        mask_f = clip_mask[..., None].astype(np.float32) / 255.0
        region = canvas[y0:y0 + dst_h, x0:x0 + dst_w].astype(np.float32)
        canvas[y0:y0 + dst_h, x0:x0 + dst_w] = np.clip(
            resized.astype(np.float32) * mask_f + region * (1.0 - mask_f),
            0,
            255,
        ).astype(np.uint8)
    else:
        canvas[y0:y0 + dst_h, x0:x0 + dst_w] = resized
    border = max(1, int(round(min(out_w, out_h) * 0.0025)))
    if clip_mask is not None:
        kernel = np.ones((max(2, border + 1), max(2, border + 1)), dtype=np.uint8)
        border_mask = cv2.dilate(clip_mask, kernel, iterations=1)
        inner = cv2.erode(clip_mask, kernel, iterations=1)
        border_mask = cv2.subtract(border_mask, inner)
        roi = canvas[y0:y0 + dst_h, x0:x0 + dst_w]
        edge = border_mask > 0
        roi[edge] = np.clip(roi[edge].astype(np.float32) * 0.35 + 255.0 * 0.65, 0, 255).astype(np.uint8)
    else:
        cv2.rectangle(
            canvas,
            (x0, y0),
            (x0 + dst_w - 1, y0 + dst_h - 1),
            (255, 255, 255),
            border,
            cv2.LINE_AA,
        )
    return np.ascontiguousarray(canvas)


def apply_screenstudio_fx_rgb(
    rgb,
    source_ms: int,
    *,
    owner=None,
    project_settings: Mapping | None = None,
    target_size: tuple[int, int] | None = None,
):
    out = apply_cursor_fx_rgb(
        rgb,
        int(source_ms),
        owner=owner,
        project_settings=project_settings,
    )
    return apply_screen_frame_style_rgb(
        out,
        owner=owner,
        project_settings=project_settings,
        target_size=target_size,
    )


def screenstudio_polish_parity_report(
    *,
    owner=None,
    project_settings: Mapping | None = None,
    frame_size: tuple[int, int] = (160, 90),
    sample_ms: Sequence[int] = (0, 240, 520, 960),
) -> dict:
    """Compare the shared preview/export compositor on deterministic frames.

    The real app has separate call sites for preview and export, but Screen
    Studio polish must stay on one pixel path.  This helper gives tests and QA
    tooling a cheap parity smoke test without needing ffmpeg or Qt widgets.
    """
    import hashlib
    import numpy as np

    w, h = int(frame_size[0]), int(frame_size[1])
    w = max(16, w)
    h = max(16, h)
    yy, xx = np.indices((h, w), dtype=np.uint16)
    base = np.stack(
        [
            (xx * 3 + yy) % 256,
            (xx + yy * 2) % 256,
            (xx * 2 + yy * 5) % 256,
        ],
        axis=-1,
    ).astype(np.uint8)
    samples: list[dict] = []
    ok = True
    for raw_ms in sample_ms:
        ms = max(0, int(raw_ms))
        preview = apply_screenstudio_fx_rgb(
            base.copy(),
            ms,
            owner=owner,
            project_settings=project_settings,
            target_size=(w, h),
        )
        export = apply_screenstudio_fx_rgb(
            base.copy(),
            ms,
            owner=owner,
            project_settings=project_settings,
            target_size=(w, h),
        )
        preview_hash = hashlib.sha1(preview.tobytes()).hexdigest()
        export_hash = hashlib.sha1(export.tobytes()).hexdigest()
        match = preview_hash == export_hash and preview.shape == export.shape
        ok = ok and match
        samples.append(
            {
                "ms": ms,
                "match": bool(match),
                "preview_hash": preview_hash,
                "export_hash": export_hash,
                "shape": tuple(int(v) for v in preview.shape),
            }
        )
    return {
        "ok": bool(ok),
        "samples": samples,
        "requires_prerender": bool(screenstudio_fx_enabled(owner=owner, project_settings=project_settings)),
    }


def screenstudio_interaction_report(
    events: Iterable[CursorEvent | Mapping] | None,
    *,
    duration_ms: int,
    frame_w: int = 1920,
    frame_h: int = 1080,
    project_settings: Mapping | None = None,
    include_parity: bool = True,
    disabled_zoom_candidate_indexes: Iterable[int] | None = None,
    zoom_candidate_overrides: Mapping | None = None,
) -> dict:
    """Summarize whether a recording has enough Screen Studio polish metadata."""
    normalized = normalize_cursor_events(events)
    if int(duration_ms or 0) <= 0 and normalized:
        duration_ms = max(ev.t_ms for ev in normalized) + 1000
    counts: dict[str, int] = {}
    hit_role_counts: dict[str, int] = {}
    cursor_style_counts: dict[str, int] = {}
    animation_counts: dict[str, int] = {}
    labels: list[str] = []
    for ev in normalized:
        counts[ev.kind] = counts.get(ev.kind, 0) + 1
        if ev.hit_role:
            hit_role_counts[ev.hit_role] = hit_role_counts.get(ev.hit_role, 0) + 1
        if ev.cursor_style:
            cursor_style_counts[ev.cursor_style] = cursor_style_counts.get(ev.cursor_style, 0) + 1
        if ev.animation:
            animation_counts[ev.animation] = animation_counts.get(ev.animation, 0) + 1
        if ev.label and ev.label not in labels:
            labels.append(ev.label)
    disabled = set()
    for raw in disabled_zoom_candidate_indexes or ():
        try:
            disabled.add(int(raw))
        except Exception:
            continue
    cursor = dict(DEFAULT_CURSOR_POLISH)
    screen = dict(DEFAULT_SCREEN_POLISH)
    try:
        if isinstance(project_settings, Mapping):
            payload = normalize_screenstudio_polish(project_settings.get("screenstudio_polish", {}) or {})
            cursor.update(dict(payload.get("cursor", {}) or {}))
            screen.update(dict(payload.get("screen", {}) or {}))
    except Exception:
        pass
    action_count = sum(
        int(counts.get(kind, 0) or 0)
        for kind in ("click", "down", "release", "key", "hotkey", "drag")
    )
    zoom_duration_ms = int(screen.get("zoom_duration_ms", 1900) or 1900)
    zoom_scale = float(screen.get("zoom_scale", 1.78) or 1.78)
    timing_profile = screenstudio_zoom_timing_profile(
        duration_ms=max(0, int(duration_ms)),
        event_count=len(normalized),
        action_count=action_count,
        zoom_duration_ms=zoom_duration_ms,
    )
    all_actors = plan_auto_zoom_actors(
        duration_ms=max(0, int(duration_ms)),
        frame_w=frame_w,
        frame_h=frame_h,
        cursor_events=normalized,
        zoom_scale=zoom_scale,
        zoom_duration_ms=zoom_duration_ms,
        zoom_easing=str(screen.get("zoom_easing", "smooth_pop") or "smooth_pop"),
        zoom_motion_blur=float(screen.get("zoom_motion_blur", 0.0) or 0.0),
        zoom_focus_bias=float(screen.get("zoom_focus_bias", 0.22) or 0.22),
        candidate_overrides=zoom_candidate_overrides,
    )
    actors = plan_auto_zoom_actors(
        duration_ms=max(0, int(duration_ms)),
        frame_w=frame_w,
        frame_h=frame_h,
        cursor_events=normalized,
        zoom_scale=zoom_scale,
        zoom_duration_ms=zoom_duration_ms,
        zoom_easing=str(screen.get("zoom_easing", "smooth_pop") or "smooth_pop"),
        zoom_motion_blur=float(screen.get("zoom_motion_blur", 0.0) or 0.0),
        zoom_focus_bias=float(screen.get("zoom_focus_bias", 0.22) or 0.22),
        disabled_point_indexes=disabled,
        candidate_overrides=zoom_candidate_overrides,
    )
    zoom_candidates: list[dict] = []
    for actor in all_actors:
        point_index = int(getattr(actor, "screenstudio_point_index", len(zoom_candidates)) or 0)
        zoom_candidates.append(
            {
                "point_index": point_index,
                "enabled": point_index not in disabled,
                "kind": str(getattr(actor, "screenstudio_point_kind", "action") or "action"),
                "point_ms": int(getattr(actor, "screenstudio_point_ms", getattr(actor, "start_ms", 0)) or 0),
                "x_norm": float(getattr(actor, "screenstudio_point_x_norm", 0.5) or 0.5),
                "y_norm": float(getattr(actor, "screenstudio_point_y_norm", 0.5) or 0.5),
                "start_ms": int(getattr(actor, "start_ms", 0) or 0),
                "end_ms": int(getattr(actor, "end_ms", 0) or 0),
                "target_x": int(getattr(actor, "target_x", 0) or 0),
                "target_y": int(getattr(actor, "target_y", 0) or 0),
                "target_w": int(getattr(actor, "target_w", 0) or 0),
                "target_h": int(getattr(actor, "target_h", 0) or 0),
                "frame_w": int(frame_w),
                "frame_h": int(frame_h),
                "easing": str(getattr(actor, "easing", "smooth_pop") or "smooth_pop"),
                "motion_blur": float(getattr(actor, "motion_blur", 0.0) or 0.0),
            }
        )
    owner = type(
        "_ScreenStudioInteractionOwner",
        (),
        {
            "cursor_events": [ev.to_dict() for ev in normalized],
            "screenstudio_polish": screenstudio_polish_preset("clean_tutorial"),
        },
    )()
    parity = {"ok": True, "skipped": True}
    if include_parity:
        parity = screenstudio_polish_parity_report(
            owner=owner,
            project_settings=project_settings,
            frame_size=(160, 90),
            sample_ms=(0, max(0, int(duration_ms) // 3), max(0, int(duration_ms) * 2 // 3)),
        )
    warnings: list[str] = []
    if not normalized:
        warnings.append("no_cursor_sidecar_events")
    if counts.get("click", 0) <= 0 and counts.get("release", 0) <= 0:
        warnings.append("no_click_or_release_events")
    if counts.get("drag", 0) <= 0:
        warnings.append("no_drag_events")
    if counts.get("key", 0) <= 0 and counts.get("hotkey", 0) <= 0:
        warnings.append("no_hotkey_events")
    if not actors and normalized:
        warnings.append("no_auto_zoom_windows")
    if include_parity and not parity.get("ok"):
        warnings.append("preview_export_parity_mismatch")
    readiness = max(0, 100 - len(warnings) * 18)
    return {
        "ok": not warnings,
        "readiness": readiness,
        "duration_ms": max(0, int(duration_ms)),
        "event_count": len(normalized),
        "counts": counts,
        "hit_role_counts": hit_role_counts,
        "cursor_style_counts": cursor_style_counts,
        "animation_counts": animation_counts,
        "hotkey_labels": labels[:12],
        "auto_zoom_count": len(actors),
        "zoom_candidates": zoom_candidates,
        "zoom_timing_profile": timing_profile,
        "cursor_loop_ready": bool(cursor.get("loop_cursor", False)),
        "cursor_loop_return_ms": int(cursor.get("loop_return_ms", 0) or 0),
        "parity_ok": bool(parity.get("ok")),
        "parity_checked": bool(include_parity),
        "warnings": warnings,
    }


def screenstudio_sidecar_report(
    source_path: str | Path | None,
    *,
    duration_ms: int = 0,
    frame_w: int = 1920,
    frame_h: int = 1080,
    include_parity: bool = False,
) -> dict:
    """Fast product-facing report for a media file's cursor sidecar."""
    events = load_cursor_sidecar(source_path)
    if not events:
        return {
            "ok": False,
            "readiness": 0,
            "duration_ms": max(0, int(duration_ms or 0)),
            "event_count": 0,
            "counts": {},
            "hotkey_labels": [],
            "auto_zoom_count": 0,
            "zoom_candidates": [],
            "zoom_timing_profile": screenstudio_zoom_timing_profile(duration_ms=max(0, int(duration_ms or 0))),
            "cursor_loop_ready": False,
            "cursor_loop_return_ms": 0,
            "parity_ok": False,
            "parity_checked": bool(include_parity),
            "warnings": ["missing_cursor_sidecar"],
        }
    return screenstudio_interaction_report(
        events,
        duration_ms=duration_ms,
        frame_w=frame_w,
        frame_h=frame_h,
        include_parity=include_parity,
    )


def apply_screenstudio_polish_to_clip(
    clip,
    *,
    frame_w: int = 1920,
    frame_h: int = 1080,
    cursor_events: Iterable[CursorEvent | Mapping] | None = None,
    cursor_polish: Mapping | None = None,
    screen_polish: Mapping | None = None,
    preset_id: str | None = None,
    replace_previous: bool = True,
    disabled_zoom_candidate_indexes: Iterable[int] | None = None,
    zoom_candidate_overrides: Mapping | None = None,
) -> int:
    duration_ms = int(
        getattr(clip, "effective_source_out_ms", 0)
        or getattr(clip, "source_duration_ms", 0)
        or getattr(clip, "effective_length_ms", 0)
        or 0
    )
    if duration_ms <= 0:
        return 0
    events = normalize_cursor_events(cursor_events) or normalize_cursor_events(getattr(clip, "cursor_events", []) or [])
    existing = list(getattr(clip, "zoom_actors", []) or [])
    previous_ids = set()
    if replace_previous:
        for raw_id in (getattr(clip, "screenstudio_polish", {}) or {}).get("auto_zoom_actor_ids", []):
            try:
                previous_ids.add(int(raw_id))
            except Exception:
                continue
        existing = [z for z in existing if int(getattr(z, "id", 0) or 0) not in previous_ids]
        clip.zoom_actors = existing
    screen = dict(DEFAULT_SCREEN_POLISH)
    screen.update(dict(screen_polish or {}))
    cursor = dict(DEFAULT_CURSOR_POLISH)
    cursor.update(dict(cursor_polish or {}))
    actors = plan_auto_zoom_actors(
        duration_ms=duration_ms,
        frame_w=frame_w,
        frame_h=frame_h,
        cursor_events=events,
        existing_actors=existing,
        zoom_scale=float(screen["zoom_scale"]),
        zoom_duration_ms=int(screen["zoom_duration_ms"]),
        zoom_easing=str(screen.get("zoom_easing", "smooth_pop") or "smooth_pop"),
        zoom_motion_blur=float(screen.get("zoom_motion_blur", 0.0) or 0.0),
        zoom_focus_bias=float(screen.get("zoom_focus_bias", 0.22) or 0.22),
        disabled_point_indexes=disabled_zoom_candidate_indexes,
        candidate_overrides=zoom_candidate_overrides,
    )
    if not actors:
        return 0
    clip.zoom_actors.extend(actors)
    clip.zoom_actors.sort(key=lambda z: int(getattr(z, "start_ms", 0) or 0))
    clip.cursor_events = [event.to_dict() for event in events[:2000]]
    clip.screenstudio_polish = screenstudio_polish_payload(
        actor_ids=[int(a.id) for a in actors],
        cursor_events=events,
        cursor_polish=cursor,
        screen_polish=screen,
        preset_id=preset_id,
    )
    return len(actors)
