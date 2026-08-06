"""Contextual design-token suggestions for Painter UI properties."""
from __future__ import annotations

import copy
import json
import math
from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.painter_i18n import painter_text
from app.painter_ui_document import normalize_ui_document
from app.painter_ui_themes import resolve_ui_theme_object, ui_theme_for_artboard


TOKEN_SUGGESTION_PATH_KINDS: dict[str, tuple[str, ...]] = {
    "style.fill": ("color",),
    "style.stroke": ("color",),
    "style.text_color": ("color",),
    "style.stroke_width": ("border",),
    "style.radius": ("radius",),
    "style.shadow": ("shadow",),
    "style.font_size": ("typography",),
    "layout.gap": ("spacing",),
    "layout.cross_gap": ("spacing",),
    "layout.padding.left": ("spacing",),
    "layout.padding.top": ("spacing",),
    "layout.padding.right": ("spacing",),
    "layout.padding.bottom": ("spacing",),
    "opacity": ("opacity",),
    "content.source": ("image", "icon"),
}

TOKEN_SUGGESTION_PATH_LABELS = {
    "style.fill": "Fill",
    "style.stroke": "Stroke",
    "style.text_color": "Text color",
    "style.stroke_width": "Stroke width",
    "style.radius": "Radius",
    "style.shadow": "Shadow",
    "style.font_size": "Font size",
    "layout.gap": "Gap",
    "layout.cross_gap": "Cross gap",
    "layout.padding.left": "Padding left",
    "layout.padding.top": "Padding top",
    "layout.padding.right": "Padding right",
    "layout.padding.bottom": "Padding bottom",
    "opacity": "Opacity",
    "content.source": "Image",
}


class PainterUITokenSuggestionError(ValueError):
    """Raised when a token suggestion target or path is invalid."""


def _path_value(row: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    value: Any = row
    for part in str(path).split("."):
        if not isinstance(value, Mapping) or part not in value:
            return False, None
        value = value[part]
    return True, copy.deepcopy(value)


def _canonical_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("#"):
            return text.upper()
        return text
    if isinstance(value, Mapping):
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
    if isinstance(value, (list, tuple)):
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
    return value


def _values_match(raw_value: Any, token_value: Any) -> bool:
    raw = _canonical_value(raw_value)
    token = _canonical_value(token_value)
    if isinstance(raw, float) and isinstance(token, float):
        return math.isclose(raw, token, rel_tol=1e-9, abs_tol=1e-6)
    return raw == token


def suggest_ui_tokens(
    value: Mapping[str, Any] | None,
    *,
    object_id: str = "",
    property_path: str = "",
    normalize: bool = True,
) -> dict[str, Any]:
    """Return exact, type-safe token matches without mutating the document."""

    # Read-only: callers holding a canonical document skip the defensive
    # copy, which dominates click latency on large imported files.
    document = normalize_ui_document(value) if normalize else value
    selected_id = str(
        object_id or document.get("selection", {}).get("object_id") or ""
    )
    row = next(
        (item for item in document["objects"] if item["id"] == selected_id),
        None,
    )
    if row is None:
        if selected_id:
            raise PainterUITokenSuggestionError(
                f"UI object not found: {selected_id}"
            )
        return {
            "schema": "tigerstudio.painter.ui.token_suggestions.v1",
            "selected_object_id": "",
            "artboard_id": "",
            "theme": "",
            "suggestion_count": 0,
            "suggestions": [],
            "message": "Select one object to inspect matching design tokens.",
        }

    requested_path = str(property_path or "").strip()
    if requested_path and requested_path not in TOKEN_SUGGESTION_PATH_KINDS:
        raise PainterUITokenSuggestionError(
            f"Unsupported UI token suggestion path: {requested_path}"
        )
    paths = (
        (requested_path,)
        if requested_path
        else tuple(TOKEN_SUGGESTION_PATH_KINDS)
    )
    artboard = next(
        (
            item
            for item in document["artboards"]
            if item["id"] == row["artboard_id"]
        ),
        None,
    )
    theme = ui_theme_for_artboard(artboard)
    tokens = {item["id"]: item for item in document["tokens"]}
    bindings = dict(row.get("token_bindings") or {})
    suggestions: list[dict[str, Any]] = []

    for path in paths:
        if str(bindings.get(path) or ""):
            continue
        exists, raw_value = _path_value(row, path)
        if not exists or raw_value is None or raw_value == "":
            continue
        accepted_kinds = TOKEN_SUGGESTION_PATH_KINDS[path]
        for token in document["tokens"]:
            if str(token["kind"]) not in accepted_kinds:
                continue
            probe = copy.deepcopy(row)
            probe["token_bindings"] = {path: str(token["id"])}
            resolved = resolve_ui_theme_object(
                probe,
                theme=theme,
                tokens=tokens,
            )
            resolved_binding = dict(
                resolved.get("resolved_tokens", {}).get(path) or {}
            )
            if not resolved_binding or not _values_match(
                raw_value,
                resolved_binding.get("value"),
            ):
                continue
            suggestions.append(
                {
                    "object_id": str(row["id"]),
                    "object_name": str(row["name"]),
                    "property_path": path,
                    "property_label": TOKEN_SUGGESTION_PATH_LABELS[path],
                    "raw_value": copy.deepcopy(raw_value),
                    "token_id": str(token["id"]),
                    "token_name": str(token["name"]),
                    "token_kind": str(token["kind"]),
                    "scope": "document",
                    "theme": theme,
                    "resolved_value": copy.deepcopy(
                        resolved_binding.get("value")
                    ),
                    "alias_chain": list(
                        resolved_binding.get("alias_chain") or []
                    ),
                    "reason": "exact_scoped_value_match",
                }
            )

    path_order = {
        path: index for index, path in enumerate(TOKEN_SUGGESTION_PATH_KINDS)
    }
    suggestions.sort(
        key=lambda item: (
            path_order.get(str(item["property_path"]), 999),
            str(item["token_name"]).casefold(),
            str(item["token_id"]),
        )
    )
    return {
        "schema": "tigerstudio.painter.ui.token_suggestions.v1",
        "selected_object_id": str(row["id"]),
        "artboard_id": str(row["artboard_id"]),
        "theme": theme,
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
        "message": (
            "Matching tokens are suggestions only; the document is unchanged."
            if suggestions
            else "No matching unbound design tokens."
        ),
    }


class PainterUITokenSuggestionPanel(QWidget):
    """Compact Inspector affordance for accepting one exact token match."""

    binding_requested = Signal(str, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._report: dict[str, Any] = {}
        self.setObjectName("PainterUITokenSuggestionPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        self.suggestion_combo = QComboBox()
        self.suggestion_combo.setObjectName("PainterUITokenSuggestionCombo")
        self.suggestion_combo.currentIndexChanged.connect(
            self._sync_selection
        )
        self.bind_button = QPushButton()
        self.bind_button.setObjectName("PainterUIIconButton")
        self.bind_button.setFixedSize(24, 24)
        self.bind_button.setIcon(
            app_icon("relink", size=11, color="#9BC4FF")
        )
        self.bind_button.setIconSize(icon_size(11))
        self.bind_button.setToolTip(painter_text("Bind suggested token"))
        self.bind_button.clicked.connect(self._emit_binding)
        row.addWidget(self.suggestion_combo, 1)
        row.addWidget(self.bind_button)
        layout.addLayout(row)
        self.status_label = QLabel()
        self.status_label.setObjectName("PaintMuted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.set_report(None)

    def set_report(self, value: Mapping[str, Any] | None) -> None:
        self._report = copy.deepcopy(dict(value or {}))
        suggestions = list(self._report.get("suggestions") or [])
        self.suggestion_combo.clear()
        for item in suggestions:
            label = (
                f"{painter_text(str(item.get('property_label') or 'Property'))}"
                f"  ·  {item.get('token_name') or item.get('token_id')}"
            )
            self.suggestion_combo.addItem(label, dict(item))
        self.bind_button.setEnabled(bool(suggestions))
        self.suggestion_combo.setEnabled(bool(suggestions))
        self.setVisible(bool(suggestions))
        self._sync_selection()

    def report(self) -> dict[str, Any]:
        return copy.deepcopy(self._report)

    def _selected_suggestion(self) -> dict[str, Any]:
        value = self.suggestion_combo.currentData()
        return dict(value) if isinstance(value, Mapping) else {}

    def _sync_selection(self, _index: int = -1) -> None:
        item = self._selected_suggestion()
        if not item:
            self.status_label.clear()
            self.bind_button.setToolTip(painter_text("Bind suggested token"))
            return
        theme = str(item.get("theme") or "light")
        self.status_label.setText(
            painter_text("Exact value match")
            + f"  ·  {painter_text(theme.replace('_', ' ').title())}"
        )
        self.status_label.setToolTip(
            f"{item.get('property_path')} = {item.get('resolved_value')!r}"
        )
        self.bind_button.setToolTip(
            painter_text("Bind suggested token")
            + f": {item.get('token_name') or item.get('token_id')}"
        )

    def _emit_binding(self) -> None:
        item = self._selected_suggestion()
        if not item:
            return
        self.binding_requested.emit(
            str(item.get("object_id") or ""),
            str(item.get("property_path") or ""),
            str(item.get("token_id") or ""),
        )


__all__ = [
    "PainterUITokenSuggestionError",
    "PainterUITokenSuggestionPanel",
    "TOKEN_SUGGESTION_PATH_KINDS",
    "TOKEN_SUGGESTION_PATH_LABELS",
    "suggest_ui_tokens",
]
