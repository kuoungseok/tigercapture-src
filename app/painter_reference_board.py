"""Painter reference-board data model.

The board is a non-destructive production-art aid: references can be pinned over
the canvas for tracing/value comparison, but they are not exported or merged
into paint layers until the user explicitly bakes one.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any


REFERENCE_SAMPLE_DEFAULT_COORDINATE = 0.5
REFERENCE_POSITION_MIN_NORM = 0.0
REFERENCE_POSITION_MAX_NORM = 1.0
REFERENCE_SIZE_MIN_NORM = 0.02
REFERENCE_SIZE_MAX_NORM = 1.0
REFERENCE_OPACITY_MIN = 0.05
REFERENCE_OPACITY_MAX = 1.0
REFERENCE_ROTATION_MIN_DEGREES = -180.0
REFERENCE_ROTATION_MAX_DEGREES = 180.0
REFERENCE_NAME_MAX_CHARACTERS = 80
REFERENCE_TARGET_ID_MIN_CHARACTERS = 1
REFERENCE_TARGET_ID_MIN_CHARACTERS = 1
REFERENCE_DEFAULT_X_NORM = 0.04
REFERENCE_DEFAULT_Y_NORM = 0.04
REFERENCE_DEFAULT_WIDTH_NORM = 0.34
REFERENCE_DEFAULT_HEIGHT_NORM = 0.34
REFERENCE_DEFAULT_OPACITY = 0.58
REFERENCE_DEFAULT_ROTATION_DEGREES = 0.0
REFERENCE_DUPLICATE_OFFSET_NORM = 0.04
REFERENCE_DUPLICATE_MAX_POSITION_NORM = REFERENCE_POSITION_MAX_NORM - REFERENCE_SIZE_MIN_NORM


@dataclass(frozen=True)
class PainterReferenceImage:
    id: str
    path: str
    name: str = ""
    x_norm: float = REFERENCE_DEFAULT_X_NORM
    y_norm: float = REFERENCE_DEFAULT_Y_NORM
    width_norm: float = REFERENCE_DEFAULT_WIDTH_NORM
    height_norm: float = REFERENCE_DEFAULT_HEIGHT_NORM
    opacity: float = REFERENCE_DEFAULT_OPACITY
    rotation_deg: float = REFERENCE_DEFAULT_ROTATION_DEGREES
    visible: bool = True
    locked: bool = False

    def normalized(self) -> "PainterReferenceImage":
        path = str(self.path or "").strip()
        name = str(self.name or "").strip() or Path(path).name or "Reference"
        return PainterReferenceImage(
            id=str(self.id or "").strip() or "reference:1",
            path=path,
            name=name[:REFERENCE_NAME_MAX_CHARACTERS],
            x_norm=_clamp(float(self.x_norm), REFERENCE_POSITION_MIN_NORM, REFERENCE_POSITION_MAX_NORM),
            y_norm=_clamp(float(self.y_norm), REFERENCE_POSITION_MIN_NORM, REFERENCE_POSITION_MAX_NORM),
            width_norm=_clamp(float(self.width_norm), REFERENCE_SIZE_MIN_NORM, REFERENCE_SIZE_MAX_NORM),
            height_norm=_clamp(float(self.height_norm), REFERENCE_SIZE_MIN_NORM, REFERENCE_SIZE_MAX_NORM),
            opacity=_clamp(float(self.opacity), REFERENCE_OPACITY_MIN, REFERENCE_OPACITY_MAX),
            rotation_deg=_normalize_rotation(self.rotation_deg),
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
            "rotation_deg": round(row.rotation_deg, 4),
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
                x_norm=_restored_reference_real(row.get("x_norm"), REFERENCE_DEFAULT_X_NORM),
                y_norm=_restored_reference_real(row.get("y_norm"), REFERENCE_DEFAULT_Y_NORM),
                width_norm=_restored_reference_real(row.get("width_norm"), REFERENCE_DEFAULT_WIDTH_NORM),
                height_norm=_restored_reference_real(row.get("height_norm"), REFERENCE_DEFAULT_HEIGHT_NORM),
                opacity=_restored_reference_real(row.get("opacity"), REFERENCE_DEFAULT_OPACITY),
                rotation_deg=_restored_reference_real(row.get("rotation_deg"), REFERENCE_DEFAULT_ROTATION_DEGREES),
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
        x_norm=float(params.get("x_norm", REFERENCE_DEFAULT_X_NORM)),
        y_norm=float(params.get("y_norm", REFERENCE_DEFAULT_Y_NORM)),
        width_norm=float(params.get("width_norm", REFERENCE_DEFAULT_WIDTH_NORM)),
        height_norm=float(params.get("height_norm", REFERENCE_DEFAULT_HEIGHT_NORM)),
        opacity=float(params.get("opacity", REFERENCE_DEFAULT_OPACITY)),
        rotation_deg=float(params.get("rotation_deg", REFERENCE_DEFAULT_ROTATION_DEGREES)),
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
        for key in (
            "path",
            "name",
            "x_norm",
            "y_norm",
            "width_norm",
            "height_norm",
            "opacity",
            "rotation_deg",
            "visible",
            "locked",
        ):
            if key in params and params[key] is not None:
                row[key] = params[key]
        updated.append(
            PainterReferenceImage(
                id=ref.id,
                path=str(row.get("path") or ""),
                name=str(row.get("name") or ""),
                x_norm=float(row.get("x_norm", REFERENCE_DEFAULT_X_NORM)),
                y_norm=float(row.get("y_norm", REFERENCE_DEFAULT_Y_NORM)),
                width_norm=float(row.get("width_norm", REFERENCE_DEFAULT_WIDTH_NORM)),
                height_norm=float(row.get("height_norm", REFERENCE_DEFAULT_HEIGHT_NORM)),
                opacity=float(row.get("opacity", REFERENCE_DEFAULT_OPACITY)),
                rotation_deg=float(row.get("rotation_deg", REFERENCE_DEFAULT_ROTATION_DEGREES)),
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
    offset_x: float = REFERENCE_DUPLICATE_OFFSET_NORM,
    offset_y: float = REFERENCE_DUPLICATE_OFFSET_NORM,
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
        x_norm=min(REFERENCE_DUPLICATE_MAX_POSITION_NORM, source.x_norm + float(offset_x or 0.0)),
        y_norm=min(REFERENCE_DUPLICATE_MAX_POSITION_NORM, source.y_norm + float(offset_y or 0.0)),
        width_norm=source.width_norm,
        height_norm=source.height_norm,
        opacity=source.opacity,
        rotation_deg=source.rotation_deg,
        visible=source.visible,
        locked=source.locked,
    ).normalized()
    return PainterReferenceBoard(
        references=(*base.references, ref),
        next_index=max(base.next_index + 1, _reference_index(ref.id) + 1),
    ).normalized()


def sample_reference_color(
    path: str,
    *,
    x_norm: float = REFERENCE_SAMPLE_DEFAULT_COORDINATE,
    y_norm: float = REFERENCE_SAMPLE_DEFAULT_COORDINATE,
) -> dict[str, Any]:
    from PySide6.QtGui import QImage
    from app.painter_action_inputs import validate_reference_sample_action

    _reference_id, resolved_x, resolved_y, _apply = validate_reference_sample_action(
        reference_id="",
        x_norm=x_norm,
        y_norm=y_norm,
        apply=True,
    )

    image = QImage(str(path or ""))
    if image.isNull():
        raise ValueError("reference image could not be loaded")
    x = int(round(resolved_x * max(0, image.width() - 1)))
    y = int(round(resolved_y * max(0, image.height() - 1)))
    color = image.pixelColor(x, y)
    return {
        "schema": "tigerstudio.painter.reference_board.sample_color.v1",
        "path": str(path or ""),
        "x_norm": resolved_x,
        "y_norm": resolved_y,
        "rgb": [int(color.red()), int(color.green()), int(color.blue())],
        "hex": "#{:02X}{:02X}{:02X}".format(int(color.red()), int(color.green()), int(color.blue())),
        "alpha": int(color.alpha()),
    }


def extract_reference_palette(path: str, *, max_colors: int = 6) -> dict[str, Any]:
    from collections import Counter

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    from app.painter_action_inputs import validate_reference_palette_action

    _reference_id, limit, _apply = validate_reference_palette_action(
        reference_id="",
        max_colors=max_colors,
        apply=True,
    )

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
            if color.alpha() <= 0:
                continue
            bucket = (
                int(round(color.red() / 24.0) * 24),
                int(round(color.green() / 24.0) * 24),
                int(round(color.blue() / 24.0) * 24),
            )
            counts[tuple(max(0, min(255, channel)) for channel in bucket)] += 1
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
    except (IndexError, ValueError):
        return 0


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _restored_reference_real(value: Any, default: float) -> float:
    try:
        if value is None or isinstance(value, bool):
            raise TypeError("missing or boolean reference scalar")
        resolved = float(value)
        if not math.isfinite(resolved):
            raise ValueError("reference scalar must be finite")
        return resolved
    except (TypeError, ValueError, OverflowError):
        return float(default)


def _normalize_rotation(value: Any) -> float:
    try:
        if isinstance(value, bool):
            raise TypeError("boolean is not a rotation")
        degrees = float(value)
        if not math.isfinite(degrees):
            raise ValueError("rotation must be finite")
    except (TypeError, ValueError, OverflowError):
        degrees = 0.0
    degrees = degrees % 360.0
    if degrees > 180.0:
        degrees -= 360.0
    return degrees


__all__ = [
    "REFERENCE_DEFAULT_HEIGHT_NORM",
    "REFERENCE_DEFAULT_OPACITY",
    "REFERENCE_DEFAULT_ROTATION_DEGREES",
    "REFERENCE_DEFAULT_WIDTH_NORM",
    "REFERENCE_DEFAULT_X_NORM",
    "REFERENCE_DEFAULT_Y_NORM",
    "REFERENCE_DUPLICATE_MAX_POSITION_NORM",
    "REFERENCE_DUPLICATE_OFFSET_NORM",
    "REFERENCE_NAME_MAX_CHARACTERS",
    "REFERENCE_OPACITY_MAX",
    "REFERENCE_OPACITY_MIN",
    "REFERENCE_POSITION_MAX_NORM",
    "REFERENCE_POSITION_MIN_NORM",
    "REFERENCE_ROTATION_MAX_DEGREES",
    "REFERENCE_ROTATION_MIN_DEGREES",
    "REFERENCE_SAMPLE_DEFAULT_COORDINATE",
    "REFERENCE_SIZE_MAX_NORM",
    "REFERENCE_SIZE_MIN_NORM",
    "REFERENCE_TARGET_ID_MIN_CHARACTERS",
    "REFERENCE_TARGET_ID_MIN_CHARACTERS",
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
