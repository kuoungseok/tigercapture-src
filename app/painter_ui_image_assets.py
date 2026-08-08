"""Stable-ID image placement and fill mutations for Painter UI Design."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PySide6.QtGui import QImageReader

from app.painter_ui_document import (
    PainterUIDocumentError,
    add_ui_object,
    normalize_ui_document,
    update_ui_object,
)
from app.painter_ui_image_renderer import normalize_ui_image_content


SUPPORTED_UI_IMAGE_SUFFIXES = {
    ".bmp",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
IMAGE_FILL_KINDS = {
    "button",
    "ellipse",
    "frame",
    "image",
    "rectangle",
}


def inspect_ui_image_source(source_path: str | Path) -> dict[str, Any]:
    path = Path(source_path).expanduser()
    if path.suffix.casefold() not in SUPPORTED_UI_IMAGE_SUFFIXES:
        raise PainterUIDocumentError(
            f"Unsupported Painter UI image type: {path.suffix or '(none)'}"
        )
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise PainterUIDocumentError(
            f"Painter UI image does not exist: {path}"
        ) from exc
    if not resolved.is_file():
        raise PainterUIDocumentError(
            f"Painter UI image is not a file: {resolved}"
        )
    reader = QImageReader(str(resolved))
    size = reader.size()
    if not size.isValid() or size.width() <= 0 or size.height() <= 0:
        raise PainterUIDocumentError(
            f"Painter UI image could not be decoded: {resolved}"
        )
    return {
        "source_path": str(resolved),
        "name": resolved.stem or "Image",
        "width": int(size.width()),
        "height": int(size.height()),
    }


def default_ui_image_size(
    value: Mapping[str, Any],
    source_path: str | Path,
    *,
    artboard_id: str = "",
    parent_id: str = "",
) -> tuple[float, float]:
    document = normalize_ui_document(value)
    source = inspect_ui_image_source(source_path)
    target_artboard_id = str(
        artboard_id or document["active_artboard_id"]
    )
    artboard = next(
        (
            row
            for row in document["artboards"]
            if row["id"] == target_artboard_id
        ),
        None,
    )
    if artboard is None:
        raise PainterUIDocumentError(
            f"UI artboard not found: {target_artboard_id}"
        )
    parent = next(
        (
            row
            for row in document["objects"]
            if row["id"] == str(parent_id or "")
        ),
        None,
    )
    container_width = float(
        (parent or artboard).get("width") or source["width"]
    )
    container_height = float(
        (parent or artboard).get("height") or source["height"]
    )
    scale = min(
        1.0,
        max(1.0, container_width * 0.72) / float(source["width"]),
        max(1.0, container_height * 0.72) / float(source["height"]),
    )
    return (
        max(1.0, float(source["width"]) * scale),
        max(1.0, float(source["height"]) * scale),
    )


def place_ui_image(
    value: Mapping[str, Any],
    source_path: str | Path,
    *,
    artboard_id: str = "",
    parent_id: str = "",
    x: float | None = None,
    y: float | None = None,
    width: float | None = None,
    height: float | None = None,
    image_fit: str = "fit",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    source = inspect_ui_image_source(source_path)
    target_artboard_id = str(
        artboard_id or document["active_artboard_id"]
    )
    artboard = next(
        (
            row
            for row in document["artboards"]
            if row["id"] == target_artboard_id
        ),
        None,
    )
    if artboard is None:
        raise PainterUIDocumentError(
            f"UI artboard not found: {target_artboard_id}"
        )
    parent = next(
        (
            row
            for row in document["objects"]
            if row["id"] == str(parent_id or "")
        ),
        None,
    )
    if parent_id and parent is None:
        raise PainterUIDocumentError(
            f"UI parent object not found: {parent_id}"
        )
    default_width, default_height = default_ui_image_size(
        document,
        source["source_path"],
        artboard_id=target_artboard_id,
        parent_id=str(parent_id or ""),
    )
    target_width = max(
        1.0,
        float(default_width if width is None else width),
    )
    target_height = max(
        1.0,
        float(default_height if height is None else height),
    )
    container = parent or artboard
    target_x = (
        max(0.0, (float(container["width"]) - target_width) * 0.5)
        if x is None
        else float(x)
    )
    target_y = (
        max(0.0, (float(container["height"]) - target_height) * 0.5)
        if y is None
        else float(y)
    )
    content = normalize_ui_image_content(
        {
            "source_path": source["source_path"],
            "image_fit": image_fit,
            "focal_x": 0.5,
            "focal_y": 0.5,
            "original_width": source["width"],
            "original_height": source["height"],
        }
    )
    document, row = add_ui_object(
        document,
        kind="image",
        name=source["name"],
        artboard_id=target_artboard_id,
        parent_id=str(parent_id or ""),
        x=target_x,
        y=target_y,
        width=target_width,
        height=target_height,
        style={"fill": "#202A37", "stroke": "#71839B"},
        content=content,
    )
    return document, row, {
        "schema": "tigerstudio.painter.ui.image.place.v1",
        "object_id": row["id"],
        "artboard_id": target_artboard_id,
        "source_path": source["source_path"],
        "source_size": [source["width"], source["height"]],
        "placed_size": [target_width, target_height],
        "image_fit": content["image_fit"],
    }


def set_ui_image_fill(
    value: Mapping[str, Any],
    object_id: str,
    source_path: str | Path,
    *,
    image_fit: str = "fill",
    focal_x: float = 0.5,
    focal_y: float = 0.5,
    tile_scale: float = 1.0,
    restore_original_size: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    target = next(
        (
            row
            for row in document["objects"]
            if row["id"] == str(object_id or "")
        ),
        None,
    )
    if target is None:
        raise PainterUIDocumentError(
            f"UI object not found: {object_id}"
        )
    if target["kind"] not in IMAGE_FILL_KINDS:
        raise PainterUIDocumentError(
            f"{target['kind']} does not support an image fill"
        )
    source = inspect_ui_image_source(source_path)
    content = normalize_ui_image_content(
        {
            **dict(target.get("content") or {}),
            "source_path": source["source_path"],
            "image_fit": image_fit,
            "focal_x": focal_x,
            "focal_y": focal_y,
            "tile_scale": tile_scale,
            "original_width": source["width"],
            "original_height": source["height"],
        }
    )
    changes: dict[str, Any] = {"content": content}
    if restore_original_size:
        changes.update(
            {
                "width": float(source["width"]),
                "height": float(source["height"]),
            }
        )
    document, row = update_ui_object(
        document,
        str(object_id),
        changes,
    )
    return document, row, {
        "schema": "tigerstudio.painter.ui.image.fill.v1",
        "object_id": row["id"],
        "object_kind": row["kind"],
        "source_path": source["source_path"],
        "source_size": [source["width"], source["height"]],
        "image_fit": content["image_fit"],
        "focal_point": [content["focal_x"], content["focal_y"]],
        "restored_original_size": bool(restore_original_size),
    }


__all__ = [
    "IMAGE_FILL_KINDS",
    "SUPPORTED_UI_IMAGE_SUFFIXES",
    "default_ui_image_size",
    "inspect_ui_image_source",
    "place_ui_image",
    "set_ui_image_fill",
]
