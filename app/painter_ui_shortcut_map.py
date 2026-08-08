"""Searchable, scope-aware shortcut catalog for Painter UI Design."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from PySide6.QtGui import QKeySequence


SCHEMA = "tigerstudio.painter.ui.shortcut_map.v1"


def _row(
    row_id: str,
    label: str,
    shortcut: str,
    scope: str,
    *,
    source: str,
) -> dict[str, Any]:
    return {
        "id": row_id,
        "label": label,
        "shortcut": shortcut,
        "scope": scope,
        "source": source,
    }


def default_painter_shortcuts() -> list[dict[str, Any]]:
    """Return the canonical Painter shortcut catalog.

    UI Design entries describe commands actually handled by the UI overlay or
    its mode-specific menu. Paint and 3D entries remain discoverable but are
    inactive while UI Design owns keyboard focus.
    """

    return [
        _row("file.new", "New Canvas", "Ctrl+N", "global", source="File"),
        _row("file.open", "Open", "Ctrl+O", "global", source="File"),
        _row("file.save", "Save", "Ctrl+S", "global", source="File"),
        _row(
            "file.save_as",
            "Save As",
            "Ctrl+Shift+S",
            "global",
            source="File",
        ),
        _row("ui.undo", "Undo", "Ctrl+Z", "ui_design", source="UI"),
        _row("ui.redo", "Redo", "Ctrl+Y", "ui_design", source="UI"),
        _row(
            "ui.duplicate",
            "Duplicate selection",
            "Ctrl+D",
            "ui_design",
            source="UI",
        ),
        _row(
            "ui.delete",
            "Delete selection",
            "Delete",
            "ui_design",
            source="UI",
        ),
        _row(
            "ui.find_replace",
            "Find / Replace",
            "Ctrl+F",
            "ui_design",
            source="UI",
        ),
        _row(
            "ui.scale_tool",
            "Scale tool",
            "K",
            "ui_design",
            source="Canvas",
        ),
        _row(
            "ui.nudge",
            "Nudge selection",
            "Arrow keys",
            "ui_design",
            source="Canvas",
        ),
        _row(
            "ui.nudge_coarse",
            "Nudge selection 10 px",
            "Shift+Arrow keys",
            "ui_design",
            source="Canvas",
        ),
        _row(
            "ui.pan",
            "Pan canvas",
            "Space+Drag",
            "ui_design",
            source="Canvas",
        ),
        _row(
            "ui.measure",
            "Show measurements",
            "Alt",
            "ui_design",
            source="Canvas",
        ),
        _row(
            "ui.exit_scope",
            "Exit edit scope",
            "Esc",
            "ui_design",
            source="Canvas",
        ),
        _row("paint.select", "Move tool", "V", "paint", source="Tools"),
        _row("paint.brush", "Brush tool", "B", "paint", source="Tools"),
        _row("paint.eraser", "Eraser tool", "E", "paint", source="Tools"),
        _row("paint.fill", "Fill tool", "G", "paint", source="Tools"),
        _row("paint.path", "Path tool", "P", "paint", source="Tools"),
        _row("paint.zoom", "Zoom tool", "Z", "paint", source="Tools"),
        _row("paint.copy", "Copy layer", "Ctrl+C", "paint", source="Edit"),
        _row("paint.cut", "Cut layer", "Ctrl+X", "paint", source="Edit"),
        _row("paint.paste", "Paste layer", "Ctrl+V", "paint", source="Edit"),
        _row(
            "paint.deselect",
            "Deselect",
            "Ctrl+D",
            "paint",
            source="Select",
        ),
        _row(
            "paint.delete",
            "Delete layer",
            "Delete",
            "paint",
            source="Layer",
        ),
        _row(
            "place.camera",
            "Move 3D camera",
            "W / A / S / D",
            "3d_place",
            source="3D Place",
        ),
    ]


def _portable_shortcut(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "Arrow keys" in text or "+Drag" in text or " / " in text:
        return " ".join(text.casefold().split())
    sequence = QKeySequence(text)
    portable = sequence.toString(QKeySequence.SequenceFormat.PortableText)
    return (portable or text).casefold()


def _scopes_overlap(left: str, right: str) -> bool:
    return left == right or "global" in {left, right}


def inspect_painter_shortcuts(
    rows: Iterable[Mapping[str, Any]] | None = None,
    *,
    query: str = "",
    conflicts_only: bool = False,
    active_scope: str = "ui_design",
) -> dict[str, Any]:
    """Build a filtered shortcut map with overlap-aware conflict diagnostics."""

    scope = str(active_scope or "ui_design").strip() or "ui_design"
    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, source_row in enumerate(
        rows if rows is not None else default_painter_shortcuts()
    ):
        row = dict(source_row)
        row_id = str(row.get("id") or f"shortcut-{index}")
        if row_id in ids:
            raise ValueError(f"duplicate shortcut id: {row_id}")
        ids.add(row_id)
        row_scope = str(row.get("scope") or "global")
        shortcut = str(row.get("shortcut") or "").strip()
        normalized.append(
            {
                "id": row_id,
                "label": str(row.get("label") or row_id),
                "shortcut": shortcut,
                "scope": row_scope,
                "source": str(row.get("source") or ""),
                "active": row_scope in {"global", scope},
                "conflict": False,
                "conflicts_with": [],
                "_key": _portable_shortcut(shortcut),
            }
        )

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        if row["_key"]:
            groups[row["_key"]].append(row)
    conflict_pairs = 0
    for candidates in groups.values():
        for left_index, left in enumerate(candidates):
            for right in candidates[left_index + 1 :]:
                if not _scopes_overlap(left["scope"], right["scope"]):
                    continue
                left["conflict"] = True
                right["conflict"] = True
                left["conflicts_with"].append(right["id"])
                right["conflicts_with"].append(left["id"])
                conflict_pairs += 1

    needle = str(query or "").strip().casefold()
    visible: list[dict[str, Any]] = []
    for row in normalized:
        if conflicts_only and not row["conflict"]:
            continue
        haystack = " ".join(
            (
                row["label"],
                row["shortcut"],
                row["scope"],
                row["source"],
            )
        ).casefold()
        if needle and needle not in haystack:
            continue
        visible.append({key: value for key, value in row.items() if key != "_key"})

    return {
        "schema": SCHEMA,
        "active_scope": scope,
        "query": str(query or ""),
        "conflicts_only": bool(conflicts_only),
        "row_count": len(normalized),
        "visible_count": len(visible),
        "active_count": sum(1 for row in normalized if row["active"]),
        "conflict_count": sum(1 for row in normalized if row["conflict"]),
        "conflict_pair_count": conflict_pairs,
        "rows": visible,
    }


__all__ = [
    "SCHEMA",
    "default_painter_shortcuts",
    "inspect_painter_shortcuts",
]
