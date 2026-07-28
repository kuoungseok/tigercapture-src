"""Non-destructive content stress previews for Painter UI documents."""
from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from app.painter_ui_document import normalize_ui_document


STRESS_PREVIEW_SCHEMA = "tigerstudio.painter.ui.stress_preview.v1"
STRESS_PREVIEW_PRESETS = (
    "none",
    "long_ko",
    "long_en",
    "large_type",
    "missing_image",
    "empty_list",
)

_LONG_KOREAN = (
    "결제 수단을 확인하고 배송 주소와 개인정보 처리 내용을 검토한 뒤 "
    "주문을 완료해 주세요. 예상보다 긴 한국어 문장에서도 버튼과 카드의 "
    "간격, 줄바꿈, 최소 크기가 안정적으로 유지되어야 합니다."
)
_LONG_ENGLISH = (
    "Review the payment method, delivery address, and privacy details before "
    "completing this unusually long action label. The layout should remain "
    "readable without clipping, overlap, or an unexpected size collapse."
)
_MISSING_IMAGE_PATH = "__tigerstudio_content_stress_missing_image__.png"


class PainterUIStressPreviewError(ValueError):
    """Raised when a stress preview request cannot be resolved."""


def _target_scope(
    objects: list[dict[str, Any]],
    object_id: str,
) -> list[dict[str, Any]]:
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for row in objects:
        by_parent.setdefault(str(row.get("parent_id") or ""), []).append(row)
    result: list[dict[str, Any]] = []
    pending = [str(object_id)]
    seen: set[str] = set()
    by_id = {str(row["id"]): row for row in objects}
    while pending:
        current = pending.pop(0)
        if current in seen:
            continue
        seen.add(current)
        row = by_id.get(current)
        if row is None:
            continue
        result.append(row)
        pending.extend(
            str(child["id"])
            for child in by_parent.get(current, [])
        )
    return result


def build_ui_stress_preview(
    value: Mapping[str, Any] | None,
    object_id: str = "",
    preset: str = "none",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return an ephemeral preview document and a compact inspection report."""
    canonical = normalize_ui_document(value)
    requested = str(preset or "none").strip().casefold()
    if requested not in STRESS_PREVIEW_PRESETS:
        raise PainterUIStressPreviewError(
            f"Unsupported Painter UI stress preset: {preset}"
        )
    target_id = str(
        object_id
        or canonical.get("selection", {}).get("object_id")
        or ""
    )
    if requested == "none":
        return canonical, {
            "schema": STRESS_PREVIEW_SCHEMA,
            "active": False,
            "preset": "none",
            "target_object_id": target_id,
            "target_name": "",
            "affected_object_ids": [],
            "affected_count": 0,
            "canonical_revision": int(canonical["revision"]),
            "preview_only": True,
            "message": "Content stress preview is off.",
        }
    target = next(
        (
            row
            for row in canonical["objects"]
            if str(row["id"]) == target_id
        ),
        None,
    )
    if target is None:
        raise PainterUIStressPreviewError(
            f"Painter UI stress target not found: {target_id or '<selection>'}"
        )

    preview = copy.deepcopy(canonical)
    scope = _target_scope(preview["objects"], target_id)
    affected: list[str] = []
    direct_children = [
        row
        for row in scope
        if str(row.get("parent_id") or "") == target_id
    ]

    for row in scope:
        kind = str(row.get("kind") or "")
        content = dict(row.get("content") or {})
        style = dict(row.get("style") or {})
        changed = False
        if requested in {"long_ko", "long_en"} and kind in {
            "text",
            "button",
        }:
            content["text"] = (
                _LONG_KOREAN if requested == "long_ko" else _LONG_ENGLISH
            )
            content["text_ranges"] = []
            changed = True
        elif requested == "large_type" and kind in {"text", "button"}:
            current = float(style.get("font_size") or 14.0)
            style["font_size"] = max(24.0, round(current * 1.75, 2))
            changed = True
        elif requested == "missing_image" and kind == "image":
            content["source_path"] = _MISSING_IMAGE_PATH
            content["path"] = _MISSING_IMAGE_PATH
            content["image_ref"] = "stress-preview-missing"
            changed = True
        if changed:
            row["content"] = content
            row["style"] = style
            affected.append(str(row["id"]))

    if requested == "empty_list":
        if direct_children:
            for row in direct_children:
                row["visible"] = False
                affected.append(str(row["id"]))
        else:
            row = scope[0]
            content = dict(row.get("content") or {})
            if str(row.get("kind") or "") in {"text", "button"}:
                content["text"] = ""
                content["text_ranges"] = []
            elif str(row.get("kind") or "") == "image":
                content["source_path"] = ""
                content["path"] = ""
                content["image_ref"] = ""
            row["content"] = content
            affected.append(str(row["id"]))

    affected = list(dict.fromkeys(affected))
    message = (
        f"{requested.replace('_', ' ')} preview affects "
        f"{len(affected)} object(s)."
    )
    return normalize_ui_document(preview), {
        "schema": STRESS_PREVIEW_SCHEMA,
        "active": True,
        "preset": requested,
        "target_object_id": target_id,
        "target_name": str(target.get("name") or target_id),
        "affected_object_ids": affected,
        "affected_count": len(affected),
        "canonical_revision": int(canonical["revision"]),
        "preview_only": True,
        "message": message,
    }


__all__ = [
    "PainterUIStressPreviewError",
    "STRESS_PREVIEW_PRESETS",
    "STRESS_PREVIEW_SCHEMA",
    "build_ui_stress_preview",
]
