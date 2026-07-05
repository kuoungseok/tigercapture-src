"""Small product-facing feedback models for preset application UX."""
from __future__ import annotations

from typing import Any, Mapping


_KIND_LABELS = {
    "effect": "FX",
    "transition": "Transition",
    "title": "Title",
    "caption_style": "Caption",
    "sticker": "Sticker",
    "motion": "Motion",
    "audio": "Audio",
    "color": "Color",
    "actor": "Actor",
    "template": "Template",
}

_BADGE_LABELS = {
    "effect": "FX",
    "transition": "TR",
    "title": "T",
    "caption_style": "CAP",
    "sticker": "ST",
    "motion": "MOT",
    "audio": "AUD",
    "color": "COL",
    "actor": "ACT",
    "template": "TPL",
}

_STRIP_COLORS = {
    "effect": "#ff6b4a",
    "transition": "#f4b434",
    "title": "#ec5da6",
    "caption_style": "#60a5ff",
    "sticker": "#7c5cff",
    "motion": "#35d0cc",
    "audio": "#64d980",
    "color": "#b47cff",
    "actor": "#ff8f5a",
    "template": "#8f7cff",
}


def preset_kind_label(kind: str) -> str:
    key = str(kind or "").casefold()
    return _KIND_LABELS.get(key, key.replace("_", " ").title() or "Preset")


def preset_badge_label(kind: str) -> str:
    key = str(kind or "").casefold()
    return _BADGE_LABELS.get(key, (preset_kind_label(key)[:3] or "PRE").upper())


def _format_ms(ms: int) -> str:
    try:
        value = max(0, int(ms))
    except Exception:
        value = 0
    seconds = value / 1000.0
    if seconds >= 60.0:
        minutes = int(seconds // 60)
        return f"{minutes}:{seconds - minutes * 60:04.1f}"
    return f"{seconds:.1f}s"


def preset_application_feedback_model(
    preset: Any,
    rows: list[Mapping[str, Any]] | None = None,
    *,
    focus_ms: int | None = None,
    track_label: str = "",
) -> dict[str, Any]:
    """Return a compact, UI-ready summary for a successful preset apply."""
    kind = str(getattr(preset, "kind", "") or "preset")
    name = str(getattr(preset, "name", getattr(preset, "id", "Preset")) or "Preset")
    clean_rows = [dict(row) for row in rows or [] if isinstance(row, Mapping)]
    actionable = [
        row for row in clean_rows
        if str(row.get("status") or "") not in {"template", "skipped", "blocked"}
    ]
    counts: dict[str, int] = {}
    durations: list[int] = []
    for row in actionable:
        row_kind = str(row.get("kind") or kind or "preset")
        label = preset_kind_label(row_kind)
        counts[label] = counts.get(label, 0) + 1
        try:
            duration = int(row.get("duration_ms", 0) or 0)
        except Exception:
            duration = 0
        if duration > 0:
            durations.append(duration)
    if not actionable:
        counts[preset_kind_label(kind)] = 1
    parts = [
        f"{label} {count}" if count > 1 else label
        for label, count in counts.items()
    ]
    where = _format_ms(focus_ms) if focus_ms is not None else ""
    duration_text = _format_ms(max(durations)) if durations else ""
    detail_bits = [bit for bit in (track_label, where, duration_text) if bit]
    return {
        "ok": True,
        "preset_id": str(getattr(preset, "id", "") or ""),
        "preset_name": name,
        "kind": kind,
        "badge": preset_badge_label(kind),
        "headline": f"{preset_kind_label(kind)} applied",
        "chip": f"{preset_badge_label(kind)} {name}",
        "detail": " · ".join(parts),
        "where": " · ".join(detail_bits),
        "applied_steps": len(actionable) if actionable else 1,
        "duration_ms": max(durations) if durations else 0,
        "toast_lines": [
            f"{preset_kind_label(kind)} applied",
            name,
            " · ".join(bit for bit in ((" · ".join(parts)), " · ".join(detail_bits)) if bit),
        ],
    }


def preset_drop_feedback_model(
    preset: Any,
    *,
    can_drop: bool,
    reason: str = "",
    project_ms: int | None = None,
    track_label: str = "",
) -> dict[str, Any]:
    kind = str(getattr(preset, "kind", "") or "preset")
    name = str(getattr(preset, "name", getattr(preset, "id", "Preset")) or "Preset")
    where = _format_ms(project_ms) if project_ms is not None else ""
    state = "ready" if can_drop else "blocked"
    verb = "Drop to apply" if can_drop else "Needs target"
    detail = reason if reason else "Release on a compatible clip or lane."
    return {
        "ok": True,
        "state": state,
        "can_drop": bool(can_drop),
        "preset_id": str(getattr(preset, "id", "") or ""),
        "kind": kind,
        "badge": preset_badge_label(kind),
        "chip": f"{verb}: {name}",
        "detail": " · ".join(bit for bit in (preset_kind_label(kind), track_label, where, detail) if bit),
        "reason": reason,
    }


def preset_timeline_strip_rows(
    preset: Any,
    rows: list[Mapping[str, Any]] | None = None,
    *,
    clip_start_ms: int = 0,
    clip_end_ms: int = 0,
) -> list[dict[str, Any]]:
    """Return UI-ready timeline strip/badge rows for applied preset state."""
    preset_id = str(getattr(preset, "id", "") or "")
    preset_name = str(getattr(preset, "name", preset_id or "Preset") or "Preset")
    preset_kind = str(getattr(preset, "kind", "") or "preset")
    clean_rows = [dict(row) for row in rows or [] if isinstance(row, Mapping)]
    actionable = [
        row for row in clean_rows
        if str(row.get("status") or "") not in {"blocked", "skipped"}
    ]
    if not actionable:
        actionable = [{"kind": preset_kind, "name": preset_name, "status": "applied"}]

    out: list[dict[str, Any]] = []
    for index, row in enumerate(actionable, start=1):
        kind = str(row.get("kind") or preset_kind or "preset")
        label = str(row.get("label") or row.get("name") or preset_name)
        badge = preset_badge_label(kind)
        try:
            start = int(row.get("start_ms", row.get("timeline_in_ms", row.get("target_ms", clip_start_ms))) or 0)
        except Exception:
            start = int(clip_start_ms or 0)
        try:
            end = int(row.get("end_ms", row.get("timeline_out_ms", 0)) or 0)
        except Exception:
            end = 0
        try:
            duration = int(row.get("duration_ms", 0) or 0)
        except Exception:
            duration = 0
        if end <= start:
            if duration <= 0 and clip_end_ms > clip_start_ms:
                duration = max(1, int(clip_end_ms) - int(clip_start_ms))
            elif duration <= 0:
                duration = 1800 if kind in {"effect", "color", "motion"} else 1200
            end = start + duration
        if clip_end_ms > clip_start_ms:
            start = max(int(clip_start_ms), start)
            end = min(int(clip_end_ms), max(start + 1, end))
        duration = max(1, end - start)
        color = _STRIP_COLORS.get(kind.casefold(), "#8f7cff")
        out.append({
            "id": f"{preset_id or 'preset'}:{index}",
            "preset_id": preset_id,
            "preset_name": preset_name,
            "kind": kind,
            "badge": badge,
            "label": label,
            "start_ms": start,
            "end_ms": end,
            "duration_ms": duration,
            "color": color,
            "lane": "preset_overlay",
            "compact": duration < 1200,
            "visible": True,
            "tooltip": f"{preset_kind_label(kind)} {label} · {_format_ms(duration)}",
            "source_status": str(row.get("status") or "applied"),
        })
    return out


def preset_preview_ab_model(
    preset: Any,
    *,
    before_signature: str = "",
    after_signature: str = "",
    sample_source: str = "current_frame",
) -> dict[str, Any]:
    """Describe the A/B preview contract for a preset card or preview dialog."""
    kind = str(getattr(preset, "kind", "") or "preset")
    name = str(getattr(preset, "name", getattr(preset, "id", "Preset")) or "Preset")
    before = str(before_signature or "")
    after = str(after_signature or "")
    has_pair = bool(before and after)
    changed = bool(has_pair and before != after)
    needs_real_frame = kind.casefold() in {"effect", "transition", "color", "motion"} and not before
    notes: list[str] = []
    if changed:
        notes.append("A/B preview differs from the source frame.")
    elif needs_real_frame:
        notes.append("Use the current viewer frame for a meaningful preview.")
    else:
        notes.append("Preview metadata is ready; no frame delta was provided.")
    return {
        "ok": True,
        "preset_id": str(getattr(preset, "id", "") or ""),
        "preset_name": name,
        "kind": kind,
        "badge": preset_badge_label(kind),
        "sample_source": sample_source,
        "before_label": "Before",
        "after_label": f"After · {preset_kind_label(kind)}",
        "changed": changed,
        "needs_real_frame": needs_real_frame,
        "split_mode": "wipe_ab" if kind.casefold() in {"effect", "transition", "color"} else "card_ab",
        "quality_notes": notes,
    }


def timeline_interaction_feedback_model(
    event: str,
    *,
    snap_ms: int | None = None,
    target_ms: int | None = None,
    mode: str = "",
    selected_count: int = 0,
    undo_label: str = "",
) -> dict[str, Any]:
    """Return compact feedback copy for timeline hover/drag/snap/undo UX."""
    event_key = str(event or "edit").casefold()
    mode_label = str(mode or "Select").title()
    chip_map = {
        "drag": "Move clip",
        "trim": "Trim edge",
        "ripple": "Ripple trim",
        "roll": "Roll edit",
        "slip": "Slip content",
        "slide": "Slide clip",
        "snap": "Snapped",
        "undo": "Undo ready",
        "redo": "Redo ready",
        "drop": "Drop target",
    }
    chip = chip_map.get(event_key, "Timeline edit")
    bits = [mode_label]
    if selected_count:
        bits.append(f"{int(selected_count)} selected")
    if target_ms is not None:
        bits.append(_format_ms(int(target_ms)))
    if snap_ms is not None:
        bits.append(f"snap {_format_ms(int(snap_ms))}")
    if undo_label:
        bits.append(str(undo_label))
    severity = "success" if event_key in {"snap", "drop"} else "info"
    if event_key in {"undo", "redo"}:
        severity = "neutral"
    return {
        "ok": True,
        "event": event_key,
        "chip": chip,
        "detail": " · ".join(bit for bit in bits if bit),
        "severity": severity,
        "commit_label": undo_label or chip.lower().replace(" ", "_"),
    }


def preset_discoverability_cards() -> list[dict[str, str]]:
    """Short hints shown by Media Pool / Workbench surfaces and QA."""
    return [
        {
            "id": "drag_to_clip",
            "surface": "Effect Presets",
            "title": "Drag onto a clip",
            "body": "Effects need a target video clip; the timeline shows a live apply chip and creates an FX badge on success.",
        },
        {
            "id": "right_click_badge",
            "surface": "Timeline",
            "title": "Use the badge menu",
            "body": "FX, TR, T, MOT, COL, and nested badges focus or edit the applied element without hunting through panels.",
        },
        {
            "id": "open_workbench",
            "surface": "Workbench",
            "title": "Inspect the selected clip",
            "body": "Select a clip or badge to reveal its editable stack, failure reason, and repair action in the Workbench.",
        },
        {
            "id": "quick_create",
            "surface": "Creator Assist",
            "title": "Quick Create stays inside the editor",
            "body": "Analyze current media, apply captions/markers/settings, stage exports, and copy publish text without switching modes.",
        },
    ]
