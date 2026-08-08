"""Deterministic accessibility audit for Painter UI documents."""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document
from app.painter_ui_themes import resolve_ui_theme_document


ACCESSIBILITY_AUDIT_SCHEMA = "tigerstudio.painter.ui.accessibility_audit.v1"
MIN_TOUCH_TARGET_PX = 44.0
_INTERACTIVE_ROLES = {"button", "checkbox", "link", "slider"}
_LABELLED_ROLES = _INTERACTIVE_ROLES | {"image", "progress"}
_HEX_COLOR = re.compile(r"^#([0-9a-f]{6}|[0-9a-f]{8})$", re.IGNORECASE)


def _effective_role(row: Mapping[str, Any]) -> str:
    accessibility = dict(row.get("accessibility") or {})
    role = str(accessibility.get("role") or "auto").strip().casefold()
    if role != "auto":
        return role
    return {
        "button": "button",
        "image": "image",
        "progress": "progress",
        "text": "text",
    }.get(str(row.get("kind") or ""), "none")


def _effective_label(row: Mapping[str, Any], role: str) -> str:
    accessibility = dict(row.get("accessibility") or {})
    label = str(accessibility.get("label") or "").strip()
    if label:
        return label
    if role in {"button", "heading", "text"}:
        return str((row.get("content") or {}).get("text") or "").strip()
    return ""


def _parse_color(value: Any) -> tuple[float, float, float, float] | None:
    text = str(value or "").strip()
    match = _HEX_COLOR.match(text)
    if match is None:
        return None
    payload = match.group(1)
    red = int(payload[0:2], 16) / 255.0
    green = int(payload[2:4], 16) / 255.0
    blue = int(payload[4:6], 16) / 255.0
    alpha = int(payload[6:8], 16) / 255.0 if len(payload) == 8 else 1.0
    return red, green, blue, alpha


def _luminance(color: tuple[float, float, float, float]) -> float:
    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(color[0])
        + 0.7152 * channel(color[1])
        + 0.0722 * channel(color[2])
    )


def _contrast_ratio(
    foreground: tuple[float, float, float, float],
    background: tuple[float, float, float, float],
) -> float:
    foreground_luminance = _luminance(foreground)
    background_luminance = _luminance(background)
    return (max(foreground_luminance, background_luminance) + 0.05) / (
        min(foreground_luminance, background_luminance) + 0.05
    )


def _contains(parent: Mapping[str, Any], child: Mapping[str, Any]) -> bool:
    return (
        float(parent.get("x") or 0.0) <= float(child.get("x") or 0.0)
        and float(parent.get("y") or 0.0) <= float(child.get("y") or 0.0)
        and float(parent.get("x") or 0.0) + float(parent.get("width") or 0.0)
        >= float(child.get("x") or 0.0) + float(child.get("width") or 0.0)
        and float(parent.get("y") or 0.0) + float(parent.get("height") or 0.0)
        >= float(child.get("y") or 0.0) + float(child.get("height") or 0.0)
    )


def _background_color(
    row: Mapping[str, Any],
    *,
    objects: Mapping[str, Mapping[str, Any]],
    artboards: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str]:
    own_fill = str((row.get("style") or {}).get("fill") or "").strip()
    if own_fill and _parse_color(own_fill) is not None:
        return own_fill, "object"
    parent_id = str(row.get("parent_id") or "")
    visited: set[str] = set()
    while parent_id and parent_id not in visited:
        visited.add(parent_id)
        parent = objects.get(parent_id)
        if parent is None:
            break
        fill = str((parent.get("style") or {}).get("fill") or "").strip()
        if _parse_color(fill) is not None:
            return fill, f"parent:{parent_id}"
        parent_id = str(parent.get("parent_id") or "")

    containing = [
        candidate
        for candidate in objects.values()
        if candidate.get("id") != row.get("id")
        and candidate.get("artboard_id") == row.get("artboard_id")
        and int(candidate.get("z_index") or 0) < int(row.get("z_index") or 0)
        and _contains(candidate, row)
        and _parse_color((candidate.get("style") or {}).get("fill")) is not None
    ]
    if containing:
        candidate = max(containing, key=lambda item: int(item.get("z_index") or 0))
        return str((candidate.get("style") or {}).get("fill")), (
            f"containing:{candidate['id']}"
        )
    artboard = artboards.get(str(row.get("artboard_id") or ""), {})
    return str(artboard.get("background") or "#FFFFFF"), "artboard"


def _issue(
    severity: str,
    rule_id: str,
    row: Mapping[str, Any] | None,
    message: str,
    remediation: str,
    **details: Any,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "rule_id": rule_id,
        "object_id": str((row or {}).get("id") or ""),
        "object_name": str((row or {}).get("name") or ""),
        "message": message,
        "remediation": remediation,
        **details,
    }


def audit_ui_accessibility(value: Mapping[str, Any] | None) -> dict[str, Any]:
    document = resolve_ui_theme_document(normalize_ui_document(value))
    objects = {row["id"]: row for row in document["objects"]}
    artboards = {row["id"]: row for row in document["artboards"]}
    issues: list[dict[str, Any]] = []
    focus_by_artboard: dict[str, dict[int, Mapping[str, Any]]] = {}
    contrast_checked = 0
    contrast_unknown = 0

    for row in document["objects"]:
        accessibility = dict(row.get("accessibility") or {})
        role = _effective_role(row)
        label = _effective_label(row, role)
        focus_order = int(accessibility.get("focus_order") or 0)

        if role in _LABELLED_ROLES and not label:
            issues.append(
                _issue(
                    "error",
                    "accessible_name",
                    row,
                    "Interactive or informative object has no accessible name.",
                    "Set an accessibility label or provide visible button text.",
                )
            )
        if focus_order > 0:
            focus_rows = focus_by_artboard.setdefault(str(row["artboard_id"]), {})
            previous = focus_rows.get(focus_order)
            if previous is not None:
                issues.append(
                    _issue(
                        "error",
                        "focus_order_unique",
                        row,
                        f"Focus order {focus_order} is already used by {previous['name']}.",
                        "Assign a unique positive focus order or use automatic order.",
                        related_object_id=str(previous["id"]),
                        focus_order=focus_order,
                    )
                )
            else:
                focus_rows[focus_order] = row
        if focus_order > 0 and (not row["visible"] or row["locked"]):
            issues.append(
                _issue(
                    "error",
                    "focus_target_available",
                    row,
                    "A hidden or locked object is included in explicit focus order.",
                    "Remove it from focus order or make the object available.",
                    focus_order=focus_order,
                )
            )
        if role in _INTERACTIVE_ROLES and row["visible"]:
            width = float(row.get("width") or 0.0)
            height = float(row.get("height") or 0.0)
            if width < MIN_TOUCH_TARGET_PX or height < MIN_TOUCH_TARGET_PX:
                issues.append(
                    _issue(
                        "warning",
                        "touch_target_size",
                        row,
                        f"Touch target is {width:g} x {height:g}px.",
                        f"Use at least {MIN_TOUCH_TARGET_PX:g} x {MIN_TOUCH_TARGET_PX:g}px.",
                        width=width,
                        height=height,
                        minimum=MIN_TOUCH_TARGET_PX,
                    )
                )

        if row["kind"] not in {"text", "button"} or not row["visible"]:
            continue
        style = dict(row.get("style") or {})
        foreground_text = str(style.get("text_color") or "").strip()
        if not foreground_text:
            foreground_text = "#111111"
        background_text, background_source = _background_color(
            row,
            objects=objects,
            artboards=artboards,
        )
        foreground = _parse_color(foreground_text)
        background = _parse_color(background_text)
        if foreground is None or background is None or min(foreground[3], background[3]) < 1.0:
            contrast_unknown += 1
            continue
        contrast_checked += 1
        ratio = _contrast_ratio(foreground, background)
        font_size = float(style.get("font_size") or 16.0)
        font_weight = int(float(style.get("font_weight") or 400))
        large_text = font_size >= 24.0 or (font_size >= 18.66 and font_weight >= 700)
        minimum_ratio = 3.0 if large_text else 4.5
        if ratio + 1e-9 < minimum_ratio:
            issues.append(
                _issue(
                    "error",
                    "text_contrast",
                    row,
                    f"Text contrast is {ratio:.2f}:1; required {minimum_ratio:.1f}:1.",
                    "Choose a higher-contrast text or background color.",
                    ratio=round(ratio, 3),
                    minimum_ratio=minimum_ratio,
                    foreground=foreground_text,
                    background=background_text,
                    background_source=background_source,
                )
            )

    for artboard_id, focus_rows in focus_by_artboard.items():
        ordered = [focus_rows[key] for key in sorted(focus_rows)]
        for previous, current in zip(ordered, ordered[1:]):
            previous_position = (
                float(previous.get("y") or 0.0),
                float(previous.get("x") or 0.0),
            )
            current_position = (
                float(current.get("y") or 0.0),
                float(current.get("x") or 0.0),
            )
            if current_position < previous_position and not math.isclose(
                current_position[0], previous_position[0], abs_tol=4.0
            ):
                issues.append(
                    _issue(
                        "warning",
                        "reading_order",
                        current,
                        "Explicit focus order moves backward in visual reading order.",
                        "Review the focus sequence against the artboard layout.",
                        related_object_id=str(previous["id"]),
                        artboard_id=artboard_id,
                    )
                )

    severity_counts = {
        severity: sum(1 for issue in issues if issue["severity"] == severity)
        for severity in ("error", "warning", "info")
    }
    return {
        "schema": ACCESSIBILITY_AUDIT_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "ok": severity_counts["error"] == 0,
        "severity_counts": severity_counts,
        "issues": issues,
        "coverage": {
            "object_count": len(document["objects"]),
            "contrast_checked": contrast_checked,
            "contrast_unknown": contrast_unknown,
            "artboard_count": len(document["artboards"]),
        },
    }


__all__ = [
    "ACCESSIBILITY_AUDIT_SCHEMA",
    "MIN_TOUCH_TARGET_PX",
    "audit_ui_accessibility",
]
