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
        "label": "Place image...",
        "detail": "Choose an image for the active artboard",
        "keywords": "add photo picture media import",
        "operation": {"type": "place_image"},
    },
    {
        "id": "selection.image_fill",
        "label": "Set image fill...",
        "detail": "Choose or replace the selected shape image",
        "keywords": "photo picture media fill replace crop",
        "operation": {"type": "set_image_fill"},
        "requires": "image_fill_target",
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
        "id": "selection.same_kind",
        "label": "Select same object type",
        "detail": "Select matching objects on the active artboard",
        "keywords": "select similar same kind type",
        "operation": {"type": "select_similar", "criterion": "kind"},
        "requires": "selection",
    },
    {
        "id": "selection.same_fill",
        "label": "Select same fill",
        "detail": "Select matching objects on the active artboard",
        "keywords": "select similar same color fill",
        "operation": {"type": "select_similar", "criterion": "fill"},
        "requires": "selection",
    },
    {
        "id": "selection.same_component",
        "label": "Select same component",
        "detail": "Select matching instances on the active artboard",
        "keywords": "select similar same component instance",
        "operation": {
            "type": "select_similar",
            "criterion": "component",
        },
        "requires": "selection",
    },
    {
        "id": "document.find_replace",
        "label": "Find / Replace",
        "detail": "Preview text and linked references before changing the document.",
        "keywords": "find replace text component style variable font asset",
        "operation": {"type": "find_replace"},
    },
    {
        "id": "selection.batch_rename",
        "label": "Batch Rename",
        "detail": "Preview names for the selected UI objects before applying.",
        "keywords": "batch rename layers prefix suffix number replace",
        "operation": {"type": "batch_rename"},
        "requires": "selection",
    },
    {
        "id": "document.shortcut_map",
        "label": "Keyboard shortcuts",
        "detail": "Search commands and diagnose overlapping key bindings.",
        "keywords": "keyboard shortcut hotkey keymap conflict commands",
        "operation": {"type": "shortcut_map"},
    },
    {
        "id": "document.action_parity",
        "label": "UI / Action parity",
        "detail": "Audit Action coverage and orphan automation commands.",
        "keywords": "ui action parity audit orphan automation coverage",
        "operation": {"type": "action_parity"},
    },
    {
        "id": "document.locale_audit",
        "label": "Locale and font audit",
        "detail": "Check critical UI copy for clipping and missing glyphs.",
        "keywords": "locale language translation font glyph overflow clip",
        "operation": {"type": "locale_audit"},
    },
    {
        "id": "document.focus_audit",
        "label": "Keyboard focus audit",
        "detail": "Check visible controls for Tab access, labels, and focus rings.",
        "keywords": "keyboard focus tab accessibility ring navigation audit",
        "operation": {"type": "focus_audit"},
    },
    {
        "id": "document.release_corpus",
        "label": "UI release corpus",
        "detail": "Verify editable exchange and delivery packages.",
        "keywords": "release corpus round trip figma template handoff prototype review umg",
        "operation": {"type": "release_corpus"},
    },
    {
        "id": "document.performance_budget",
        "label": "Performance budget",
        "detail": "Inspect document scale against production warning and block limits.",
        "keywords": "performance budget objects artboards images components prototype scale",
        "operation": {"type": "performance_budget"},
    },
    {
        "id": "document.runtime_performance",
        "label": "Runtime performance",
        "detail": "Measure core Painter UI paths on this machine.",
        "keywords": "runtime benchmark timing normalize layout diagnostics quick actions",
        "operation": {"type": "runtime_performance"},
    },
    {
        "id": "selection.duplicate_next_artboard",
        "label": "Duplicate to next artboard",
        "detail": "Copy the selected hierarchy to the next screen",
        "keywords": "copy clone responsive screen page artboard",
        "operation": {"type": "duplicate_to_next_artboard"},
        "requires": "next_artboard",
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
    {
        "id": "inspector.auto_hide",
        "label": "Auto-hide inspector",
        "detail": "Show properties only when the selection needs them",
        "keywords": "inspector properties contextual overlay hide",
        "operation": {
            "type": "inspector_presentation",
            "mode": "auto_hide",
        },
    },
    {
        "id": "inspector.pin",
        "label": "Pin inspector",
        "detail": "Keep the contextual properties beside the canvas",
        "keywords": "inspector properties sidebar dock fixed",
        "operation": {
            "type": "inspector_presentation",
            "mode": "pinned",
        },
    },
    {
        "id": "inspector.float",
        "label": "Open inspector as window",
        "detail": "Move the contextual properties into a separate window",
        "keywords": "inspector properties detach floating window",
        "operation": {
            "type": "inspector_presentation",
            "mode": "floating",
        },
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
    if requirement == "image_fill_target":
        from app.painter_ui_image_assets import IMAGE_FILL_KINDS

        return (
            count == 1
            and str(context.get("selected_kind") or "") in IMAGE_FILL_KINDS
        )
    if requirement == "next_artboard":
        return bool(context.get("cross_artboard_duplicate_eligible"))
    return True


def _score(query: str, row: Mapping[str, Any]) -> int:
    needle = " ".join(str(query or "").casefold().split())
    if not needle:
        return 1
    label = str(row.get("label") or "").casefold()
    detail = str(row.get("detail") or "").casefold()
    keywords = str(row.get("keywords") or "").casefold()
    source_text = str(row.get("_search_source") or "").casefold()
    haystack = f"{label} {detail} {source_text} {keywords}"
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
    active_page_id = str(document.get("active_page_id") or "")
    for row in document.get("pages", []):
        active = str(row["id"]) == active_page_id
        rows.append(
            {
                "id": f"page_record.{row['id']}",
                "kind": "page",
                "label": str(row.get("name") or "Page"),
                "detail": (
                    f"{painter_text('Page')}"
                    + (" / Active" if active else "")
                ),
                "keywords": "page canvas document screen",
                "operation": {
                    "type": "activate_page",
                    "page_id": str(row["id"]),
                },
                "enabled": True,
            }
        )
    for row in document.get("artboards", []):
        active = str(row["id"]) == active_artboard_id
        rows.append(
            {
                "id": f"page.{row['id']}",
                "kind": "artboard",
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
    from app.painter_ui_cross_artboard import (
        inspect_cross_artboard_duplicate,
    )

    cross_artboard = inspect_cross_artboard_duplicate(document)
    context["cross_artboard_duplicate_eligible"] = bool(
        cross_artboard["eligible"]
    )
    context["next_artboard_id"] = str(
        cross_artboard["target_artboard_id"]
    )
    context["next_artboard_name"] = str(
        cross_artboard["target_artboard_name"]
    )
    candidates: list[dict[str, Any]] = []
    from app.painter_i18n import painter_text

    for index, command in enumerate(_COMMANDS):
        source_label = str(command["label"])
        source_detail = str(command["detail"])
        row = {
            **command,
            "label": painter_text(source_label),
            "detail": painter_text(source_detail),
            "_search_source": f"{source_label} {source_detail}",
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
