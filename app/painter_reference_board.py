"""Painter reference-board data model.

The board is a non-destructive production-art aid: references can be pinned over
the canvas for tracing/value comparison, but they are not exported or merged
into paint layers until the user explicitly bakes one.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PainterReferenceImage:
    id: str
    path: str
    name: str = ""
    x_norm: float = 0.04
    y_norm: float = 0.04
    width_norm: float = 0.34
    height_norm: float = 0.34
    opacity: float = 0.58
    visible: bool = True
    locked: bool = False

    def normalized(self) -> "PainterReferenceImage":
        path = str(self.path or "").strip()
        name = str(self.name or "").strip() or Path(path).name or "Reference"
        return PainterReferenceImage(
            id=str(self.id or "").strip() or "reference:1",
            path=path,
            name=name[:80],
            x_norm=_clamp(float(self.x_norm), 0.0, 1.0),
            y_norm=_clamp(float(self.y_norm), 0.0, 1.0),
            width_norm=_clamp(float(self.width_norm), 0.02, 1.0),
            height_norm=_clamp(float(self.height_norm), 0.02, 1.0),
            opacity=_clamp(float(self.opacity), 0.05, 1.0),
            visible=bool(self.visible),
            locked=bool(self.locked),
        )

    def to_dict(self) -> dict[str, Any]:
        row = self.normalized()
        return {
            "id": row.id,
            "path": row.path,
            "name": row.name,
            "x_norm": round(row.x_norm, 5),
            "y_norm": round(row.y_norm, 5),
            "width_norm": round(row.width_norm, 5),
            "height_norm": round(row.height_norm, 5),
            "opacity": round(row.opacity, 4),
            "visible": row.visible,
            "locked": row.locked,
        }


@dataclass(frozen=True)
class PainterReferenceBoard:
    schema: str = "tigerstudio.painter.reference_board.v1"
    references: tuple[PainterReferenceImage, ...] = ()
    next_index: int = 1

    def normalized(self) -> "PainterReferenceBoard":
        refs = tuple(ref.normalized() for ref in self.references if str(ref.path or "").strip())
        used = {_reference_index(ref.id) for ref in refs}
        next_index = max([int(self.next_index or 1), *[idx + 1 for idx in used if idx > 0]], default=1)
        return PainterReferenceBoard(references=refs, next_index=max(1, next_index))

    def to_dict(self) -> dict[str, Any]:
        board = self.normalized()
        return {
            "schema": board.schema,
            "references": [ref.to_dict() for ref in board.references],
            "reference_count": len(board.references),
            "next_index": int(board.next_index),
            "non_destructive": True,
            "exported_by_default": False,
        }


def default_reference_board() -> PainterReferenceBoard:
    return PainterReferenceBoard()


def reference_board_from_dict(payload: Any) -> PainterReferenceBoard:
    if isinstance(payload, PainterReferenceBoard):
        return payload.normalized()
    if not isinstance(payload, dict):
        return default_reference_board()
    refs: list[PainterReferenceImage] = []
    for row in payload.get("references", []) or []:
        if not isinstance(row, dict):
            continue
        refs.append(
            PainterReferenceImage(
                id=str(row.get("id") or ""),
                path=str(row.get("path") or ""),
                name=str(row.get("name") or ""),
                x_norm=float(row.get("x_norm", 0.04) or 0.04),
                y_norm=float(row.get("y_norm", 0.04) or 0.04),
                width_norm=float(row.get("width_norm", 0.34) or 0.34),
                height_norm=float(row.get("height_norm", 0.34) or 0.34),
                opacity=float(row.get("opacity", 0.58) or 0.58),
                visible=bool(row.get("visible", True)),
                locked=bool(row.get("locked", False)),
            )
        )
    return PainterReferenceBoard(
        references=tuple(refs),
        next_index=int(payload.get("next_index", 1) or 1),
    ).normalized()


def add_reference_image(board: PainterReferenceBoard | dict[str, Any] | None, **params: Any) -> PainterReferenceBoard:
    base = reference_board_from_dict(board)
    reference_id = str(params.get("reference_id") or "").strip() or f"reference:{base.next_index}"
    if any(ref.id == reference_id for ref in base.references):
        raise ValueError(f"Painter reference already exists: {reference_id}")
    path = str(params.get("path") or "").strip()
    if not path:
        raise ValueError("Painter reference requires an image path")
    ref = PainterReferenceImage(
        id=reference_id,
        path=path,
        name=str(params.get("name") or ""),
        x_norm=float(params.get("x_norm", 0.04) or 0.04),
        y_norm=float(params.get("y_norm", 0.04) or 0.04),
        width_norm=float(params.get("width_norm", 0.34) or 0.34),
        height_norm=float(params.get("height_norm", 0.34) or 0.34),
        opacity=float(params.get("opacity", 0.58) or 0.58),
        visible=bool(params.get("visible", True)),
        locked=bool(params.get("locked", False)),
    ).normalized()
    return PainterReferenceBoard(
        references=(*base.references, ref),
        next_index=max(base.next_index + 1, _reference_index(reference_id) + 1),
    ).normalized()


def update_reference_image(
    board: PainterReferenceBoard | dict[str, Any],
    reference_id: str,
    **params: Any,
) -> PainterReferenceBoard:
    base = reference_board_from_dict(board)
    wanted = str(reference_id or "").strip()
    updated: list[PainterReferenceImage] = []
    found = False
    for ref in base.references:
        if ref.id != wanted:
            updated.append(ref)
            continue
        found = True
        row = ref.to_dict()
        for key in ("path", "name", "x_norm", "y_norm", "width_norm", "height_norm", "opacity", "visible", "locked"):
            if key in params and params[key] is not None:
                row[key] = params[key]
        updated.append(
            PainterReferenceImage(
                id=ref.id,
                path=str(row.get("path") or ""),
                name=str(row.get("name") or ""),
                x_norm=float(row.get("x_norm", 0.04) or 0.04),
                y_norm=float(row.get("y_norm", 0.04) or 0.04),
                width_norm=float(row.get("width_norm", 0.34) or 0.34),
                height_norm=float(row.get("height_norm", 0.34) or 0.34),
                opacity=float(row.get("opacity", 0.58) or 0.58),
                visible=bool(row.get("visible", True)),
                locked=bool(row.get("locked", False)),
            ).normalized()
        )
    if not found:
        raise ValueError(f"Painter reference not found: {wanted}")
    return PainterReferenceBoard(references=tuple(updated), next_index=base.next_index).normalized()


def delete_reference_image(board: PainterReferenceBoard | dict[str, Any], reference_id: str) -> PainterReferenceBoard:
    base = reference_board_from_dict(board)
    wanted = str(reference_id or "").strip()
    remaining = tuple(ref for ref in base.references if ref.id != wanted)
    if len(remaining) == len(base.references):
        raise ValueError(f"Painter reference not found: {wanted}")
    return PainterReferenceBoard(references=remaining, next_index=base.next_index).normalized()


def duplicate_reference_image(
    board: PainterReferenceBoard | dict[str, Any],
    reference_id: str,
    *,
    offset_x: float = 0.04,
    offset_y: float = 0.04,
) -> PainterReferenceBoard:
    base = reference_board_from_dict(board)
    wanted = str(reference_id or "").strip()
    source = next((ref for ref in base.references if ref.id == wanted), None)
    if source is None:
        raise ValueError(f"Painter reference not found: {wanted}")
    ref = PainterReferenceImage(
        id=f"reference:{base.next_index}",
        path=source.path,
        name=f"{source.name} Copy",
        x_norm=min(0.98, source.x_norm + float(offset_x or 0.0)),
        y_norm=min(0.98, source.y_norm + float(offset_y or 0.0)),
        width_norm=source.width_norm,
        height_norm=source.height_norm,
        opacity=source.opacity,
        visible=source.visible,
        locked=source.locked,
    ).normalized()
    return PainterReferenceBoard(
        references=(*base.references, ref),
        next_index=max(base.next_index + 1, _reference_index(ref.id) + 1),
    ).normalized()


def sample_reference_color(path: str, *, x_norm: float = 0.5, y_norm: float = 0.5) -> dict[str, Any]:
    from PySide6.QtGui import QImage

    image = QImage(str(path or ""))
    if image.isNull():
        raise ValueError("reference image could not be loaded")
    x = int(round(_clamp(float(x_norm), 0.0, 1.0) * max(0, image.width() - 1)))
    y = int(round(_clamp(float(y_norm), 0.0, 1.0) * max(0, image.height() - 1)))
    color = image.pixelColor(x, y)
    return {
        "schema": "tigerstudio.painter.reference_board.sample_color.v1",
        "path": str(path or ""),
        "x_norm": round(_clamp(float(x_norm), 0.0, 1.0), 5),
        "y_norm": round(_clamp(float(y_norm), 0.0, 1.0), 5),
        "rgb": [int(color.red()), int(color.green()), int(color.blue())],
        "hex": "#{:02X}{:02X}{:02X}".format(int(color.red()), int(color.green()), int(color.blue())),
        "alpha": int(color.alpha()),
    }


def extract_reference_palette(path: str, *, max_colors: int = 6) -> dict[str, Any]:
    from collections import Counter

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    image = QImage(str(path or ""))
    if image.isNull():
        raise ValueError("reference image could not be loaded")
    sample = image.scaled(
        96,
        96,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    ).convertToFormat(QImage.Format.Format_ARGB32)
    counts: Counter[tuple[int, int, int]] = Counter()
    for y in range(sample.height()):
        for x in range(sample.width()):
            color = sample.pixelColor(x, y)
            if color.alpha() < 16:
                continue
            bucket = (
                int(round(color.red() / 24.0) * 24),
                int(round(color.green() / 24.0) * 24),
                int(round(color.blue() / 24.0) * 24),
            )
            counts[tuple(max(0, min(255, channel)) for channel in bucket)] += 1
    limit = max(1, min(12, int(max_colors or 6)))
    palette = []
    total = max(1, sum(counts.values()))
    for rgb, count in counts.most_common(limit):
        palette.append(
            {
                "rgb": [int(rgb[0]), int(rgb[1]), int(rgb[2])],
                "hex": "#{:02X}{:02X}{:02X}".format(*rgb),
                "weight": round(float(count) / float(total), 5),
            }
        )
    return {
        "schema": "tigerstudio.painter.reference_board.palette.v1",
        "path": str(path or ""),
        "colors": palette,
        "color_count": len(palette),
    }


def _reference_index(reference_id: str) -> int:
    try:
        return int(str(reference_id or "").split(":", 1)[1])
    except Exception:
        return 0


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


__all__ = [
    "PainterReferenceBoard",
    "PainterReferenceImage",
    "add_reference_image",
    "default_reference_board",
    "delete_reference_image",
    "duplicate_reference_image",
    "extract_reference_palette",
    "reference_board_from_dict",
    "sample_reference_color",
    "update_reference_image",
]
