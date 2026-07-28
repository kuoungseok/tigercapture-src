"""Context-aware Quick Actions catalog for Painter UI Design."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_COMMANDS: tuple[dict[str, Any], ...] = (
    {
        "id": "tool.select",
        "label": "Select tool",
        "detail": "Move and select objects",
        "keywords": "move cursor pointer v",
        "shortcut": "V",
        "operation": {"type": "tool", "tool": "select"},
    },
    {
        "id": "tool.frame",
        "label": "Frame tool",
        "detail": "Draw an artboard container",
        "keywords": "frame container artboard f",
        "operation": {"type": "tool", "tool": "frame"},
    },
    {
        "id": "create.rectangle",
        "label": "Add rectangle",
        "detail": "Create on the active artboard",
        "keywords": "shape box square",
        "shortcut": "R",
        "operation": {"type": "create", "kind": "rectangle"},
    },
    {
        "id": "create.ellipse",
        "label": "Add ellipse",
        "detail": "Create on the active artboard",
        "keywords": "shape circle oval o",
        "shortcut": "O",
        "operation": {"type": "create", "kind": "ellipse"},
    },
    {
        "id": "create.text",
        "label": "Add text",
        "detail": "Create editable text",
        "keywords": "type label typography",
        "shortcut": "T",
        "operation": {"type": "create", "kind": "text"},
    },
    {
        "id": "create.image",
        "label": "Add image",
        "detail": "Create an image placeholder",
        "keywords": "photo picture media",
        "operation": {"type": "create", "kind": "image"},
    },
    {
        "id": "view.fit_all",
        "label": "Fit all artboards",
        "detail": "Frame the whole UI document",
        "keywords": "zoom view canvas all",
        "operation": {"type": "fit", "mode": "all"},
    },
    {
        "id": "view.fit_artboard",
        "label": "Fit active artboard",
        "detail": "Frame the current page",
        "keywords": "zoom view canvas page",
        "operation": {"type": "fit", "mode": "artboard"},
    },
    {
        "id": "view.fit_selection",
        "label": "Fit selection",
        "detail": "Frame selected objects",
        "keywords": "zoom view focus object",
        "operation": {"type": "fit", "mode": "selection"},
        "requires": "selection",
    },
    {
        "id": "selection.scale",
        "label": "Scale selection",
        "detail": "Scale bounds and visual metrics",
        "keywords": "scale resize proportional percentage k",
        "shortcut": "K",
        "operation": {"type": "scale_selection"},
        "requires": "selection",
    },
    {
        "id": "selection.duplicate",
        "label": "Duplicate selection",
        "detail": "Duplicate the primary object",
        "keywords": "copy clone object",
        "shortcut": "Ctrl+D",
        "operation": {"type": "duplicate_selection"},
        "requires": "selection",
    },
    {
        "id": "selection.delete",
        "label": "Delete selection",
        "detail": "Remove the selected object hierarchy",
        "keywords": "remove trash object",
        "shortcut": "Delete",
        "operation": {"type": "delete_selection"},
        "requires": "selection",
    },
    {
        "id": "selection.group",
        "label": "Group selection",
        "detail": "Create one editable group",
        "keywords": "combine nest objects",
        "shortcut": "Ctrl+G",
        "operation": {"type": "group_selection"},
        "requires": "multi_selection",
    },
    {
        "id": "selection.ungroup",
        "label": "Ungroup selection",
        "detail": "Release the selected group",
        "keywords": "release separate group",
        "shortcut": "Ctrl+Shift+G",
        "operation": {"type": "ungroup_selection"},
        "requires": "group",
    },
    {
        "id": "motion.open",
        "label": "Animate in Motion Designer",
        "detail": "Open the selected stable-ID object",
        "keywords": "motion animation timeline hover",
        "operation": {"type": "animate_selection"},
        "requires": "selection",
    },
)


def _enabled(requirement: str, context: Mapping[str, Any]) -> bool:
    count = int(context.get("selection_count") or 0)
    if requirement == "selection":
        return count > 0
    if requirement == "multi_selection":
        return count > 1
    if requirement == "group":
        return count == 1 and str(context.get("selected_kind") or "") == "group"
    return True


def _score(query: str, row: Mapping[str, Any]) -> int:
    needle = " ".join(str(query or "").casefold().split())
    if not needle:
        return 1
    label = str(row.get("label") or "").casefold()
    detail = str(row.get("detail") or "").casefold()
    keywords = str(row.get("keywords") or "").casefold()
    haystack = f"{label} {detail} {keywords}"
    words = needle.split()
    if not all(word in haystack for word in words):
        return 0
    score = 100
    if label.startswith(needle):
        score += 300
    elif needle in label:
        score += 220
    if any(token.startswith(needle) for token in label.split()):
        score += 80
    score += max(0, 40 - haystack.find(words[0]))
    return score


def _dynamic_rows(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    from app.painter_i18n import painter_text

    active_artboard_id = str(document.get("active_artboard_id") or "")
    rows: list[dict[str, Any]] = []
    for row in document.get("objects", []):
        if str(row.get("artboard_id") or "") != active_artboard_id:
            continue
        rows.append(
            {
                "id": f"layer.{row['id']}",
                "kind": "layer",
                "label": str(row.get("name") or row.get("kind") or "Layer"),
                "detail": (
                    f"{painter_text('Layer')} · "
                    f"{str(row.get('kind') or '').title()}"
                ),
                "keywords": f"layer object {row.get('kind', '')}",
                "operation": {
                    "type": "select_object",
                    "object_id": str(row["id"]),
                },
                "enabled": bool(row.get("visible", True)),
            }
        )
    for row in document.get("artboards", []):
        active = str(row["id"]) == active_artboard_id
        rows.append(
            {
                "id": f"page.{row['id']}",
                "kind": "page",
                "label": str(row.get("name") or "Artboard"),
                "detail": (
                    f"{painter_text('Page')} · "
                    f"{int(row.get('width') or 0)} x "
                    f"{int(row.get('height') or 0)}"
                    + (" · Active" if active else "")
                ),
                "keywords": "page artboard screen frame",
                "operation": {
                    "type": "activate_artboard",
                    "artboard_id": str(row["id"]),
                },
                "enabled": True,
            }
        )
    for row in document.get("components", []):
        rows.append(
            {
                "id": f"component.{row['id']}",
                "kind": "component",
                "label": str(row.get("name") or "Component"),
                "detail": (
                    f"{painter_text('Component')} · "
                    f"{painter_text('Insert instance')}"
                ),
                "keywords": "component instance asset variant",
                "operation": {
                    "type": "instantiate_component",
                    "component_id": str(row["id"]),
                },
                "enabled": True,
            }
        )
    for row in document.get("tokens", []):
        rows.append(
            {
                "id": f"token.{row['id']}",
                "kind": "token",
                "label": str(row.get("name") or "Token"),
                "detail": (
                    f"{painter_text('Variable')} · "
                    f"{str(row.get('kind') or '').title()}"
                ),
                "keywords": "token variable style design system",
                "operation": {
                    "type": "reveal_token",
                    "token_id": str(row["id"]),
                },
                "enabled": True,
            }
        )
    return rows


def search_painter_ui_quick_actions(
    value: Mapping[str, Any],
    query: str = "",
    *,
    limit: int = 30,
) -> dict[str, Any]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    selected_ids = list(document["selection"]["object_ids"])
    selected = next(
        (
            row
            for row in document["objects"]
            if row["id"] == document["selection"]["object_id"]
        ),
        None,
    )
    context = {
        "selection_count": len(selected_ids),
        "selected_kind": str((selected or {}).get("kind") or ""),
        "active_artboard_id": document["active_artboard_id"],
    }
    candidates: list[dict[str, Any]] = []
    from app.painter_i18n import painter_text

    for index, command in enumerate(_COMMANDS):
        row = {
            **command,
            "label": painter_text(str(command["label"])),
            "detail": painter_text(str(command["detail"])),
            "kind": "command",
            "enabled": _enabled(str(command.get("requires") or ""), context),
            "_rank": index,
        }
        candidates.append(row)
    for index, row in enumerate(_dynamic_rows(document), start=len(candidates)):
        candidates.append({**row, "_rank": index})
    matches: list[dict[str, Any]] = []
    for row in candidates:
        score = _score(query, row)
        if score <= 0:
            continue
        matches.append(
            {
                key: value
                for key, value in {**row, "score": score}.items()
                if not key.startswith("_")
            }
            | {"_rank": int(row["_rank"])}
        )
    matches.sort(
        key=lambda row: (
            not bool(row["enabled"]),
            -int(row["score"]),
            int(row["_rank"]),
            str(row["label"]).casefold(),
        )
    )
    result_rows = [
        {key: value for key, value in row.items() if key != "_rank"}
        for row in matches[: max(1, min(100, int(limit)))]
    ]
    return {
        "schema": "tigerstudio.painter.ui.quick_actions.v1",
        "query": str(query),
        "context": context,
        "results": result_rows,
        "result_count": len(result_rows),
    }


__all__ = ["search_painter_ui_quick_actions"]
