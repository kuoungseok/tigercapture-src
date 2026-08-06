"""Open Painter document identity and cross-document Alpha8 transfer."""
from __future__ import annotations

import re
import operator
import uuid
from typing import Any

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication


_RUNTIME_DOCUMENT_ID_PATTERN = re.compile(
    r"painter-document-[0-9a-f]{32}\Z"
)


def new_painter_runtime_document_id() -> str:
    """Return an opaque identity for one open document instance."""
    return f"painter-document-{uuid.uuid4().hex}"


def normalize_painter_runtime_document_id(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Painter runtime document id must be a string")
    if value != value.strip() or not _RUNTIME_DOCUMENT_ID_PATTERN.fullmatch(value):
        raise ValueError("Painter runtime document id is invalid")
    return value


def _document_size(dialog: Any) -> tuple[int, int]:
    raw = getattr(dialog, "_canvas_document_size", None)
    if (
        not isinstance(raw, tuple)
        or len(raw) != 2
        or isinstance(raw[0], bool)
        or isinstance(raw[1], bool)
    ):
        raise ValueError("Painter document pixel dimensions are invalid")
    try:
        width = operator.index(raw[0])
        height = operator.index(raw[1])
    except TypeError as exc:
        raise ValueError("Painter document pixel dimensions are invalid") from exc
    if width <= 0 or height <= 0:
        raise ValueError("Painter document pixel dimensions are invalid")
    return width, height


def painter_open_document_descriptor(dialog: Any) -> dict[str, object]:
    document_id = normalize_painter_runtime_document_id(
        getattr(dialog, "_painter_runtime_document_id", "")
    )
    width, height = _document_size(dialog)
    path = str(getattr(dialog, "_painter_document_path", "") or "")
    title_getter = getattr(dialog, "windowTitle", None)
    title = str(title_getter() if callable(title_getter) else "").strip()
    if not title:
        title = "Untitled Painter Document"
    return {
        "document_id": document_id,
        "title": title,
        "path": path,
        "width": width,
        "height": height,
        "saved_selection_channel_count": len(
            list(getattr(dialog, "_saved_selection_channels", []) or [])
        ),
    }


def open_painter_documents() -> list[Any]:
    """Enumerate live top-level Painter dialogs known to QApplication."""
    app = QApplication.instance()
    if app is None:
        return []
    rows = [
        widget
        for widget in QApplication.topLevelWidgets()
        if hasattr(widget, "_painter_runtime_document_id")
        and bool(getattr(widget, "_standalone", False))
        and widget.isVisible()
    ]
    rows.sort(
        key=lambda row: str(getattr(row, "_painter_runtime_document_id", ""))
    )
    return rows


def inspect_open_painter_documents() -> dict[str, object]:
    rows = [painter_open_document_descriptor(row) for row in open_painter_documents()]
    return {
        "schema": "tigerstudio.painter.open-documents.v1",
        "documents": rows,
        "count": len(rows),
    }


def refresh_other_painter_document_channel_controls(changed: Any) -> None:
    """Refresh cross-document load eligibility after a channel-list change."""
    for dialog in open_painter_documents():
        if dialog is changed:
            continue
        refresh = getattr(dialog, "_sync_saved_selection_channel_controls", None)
        if callable(refresh):
            refresh(str(getattr(dialog, "_selected_channel", "RGB") or "RGB"))


def resolve_open_painter_document(
    document_id: object,
    *,
    exclude: Any | None = None,
) -> Any:
    target_id = normalize_painter_runtime_document_id(document_id)
    for dialog in open_painter_documents():
        if dialog is exclude:
            continue
        if getattr(dialog, "_painter_runtime_document_id", "") == target_id:
            return dialog
    raise ValueError("Open Painter document does not exist")


def require_open_painter_document_instance(dialog: Any) -> Any:
    """Reject hidden, closed, embedded, or otherwise stale dialog objects."""
    if not any(candidate is dialog for candidate in open_painter_documents()):
        raise ValueError("Painter document is not an open standalone document")
    painter_open_document_descriptor(dialog)
    return dialog


def require_matching_painter_document_dimensions(
    source: Any,
    destination: Any,
) -> tuple[int, int]:
    source_size = _document_size(source)
    destination_size = _document_size(destination)
    if source_size != destination_size:
        raise ValueError(
            "Cross-document selections require identical pixel dimensions"
        )
    return source_size


def save_selection_to_open_painter_document(
    source: Any,
    destination: Any,
    *,
    name: str = "",
    channel_id: str = "",
    operation: str = "new",
) -> str:
    require_open_painter_document_instance(source)
    require_open_painter_document_instance(destination)
    if source is destination:
        raise ValueError("Cross-document save requires another open document")
    width, height = require_matching_painter_document_dimensions(
        source,
        destination,
    )
    active_mask = getattr(source, "_selection_pixel_mask", None)
    if isinstance(active_mask, QImage) and not active_mask.isNull():
        if active_mask.width() != width or active_mask.height() != height:
            raise ValueError(
                "Active selection mask must match its document pixel dimensions"
            )
        incoming = QImage(active_mask)
    else:
        incoming = source._selection_mask_for_document(width, height)
    if not isinstance(incoming, QImage) or incoming.isNull():
        raise ValueError("No active selection to save")
    return destination._save_selection_mask_to_channel(
        QImage(incoming),
        name=name,
        channel_id=channel_id,
        operation=operation,
        undo_label="Save selection from another document",
    )


def load_selection_from_open_painter_document(
    destination: Any,
    source: Any,
    *,
    channel_id: str,
    operation: str = "new",
    invert: bool = False,
) -> bool:
    require_open_painter_document_instance(destination)
    require_open_painter_document_instance(source)
    if source is destination:
        raise ValueError("Cross-document load requires another open document")
    require_matching_painter_document_dimensions(source, destination)
    target = source._saved_selection_channel_by_id(channel_id)
    if target is None:
        raise ValueError("Saved selection channel does not exist in source document")
    return destination._load_selection_mask_into_document(
        QImage(target.mask),
        operation=operation,
        invert=invert,
        undo_label="Load selection from another document",
        selected_channel_id=None,
    )


__all__ = [
    "inspect_open_painter_documents",
    "load_selection_from_open_painter_document",
    "new_painter_runtime_document_id",
    "normalize_painter_runtime_document_id",
    "open_painter_documents",
    "painter_open_document_descriptor",
    "refresh_other_painter_document_channel_controls",
    "require_open_painter_document_instance",
    "require_matching_painter_document_dimensions",
    "resolve_open_painter_document",
    "save_selection_to_open_painter_document",
]
