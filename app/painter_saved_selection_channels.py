"""Exact Alpha8 contracts for persistent saved-selection channels."""
from __future__ import annotations

from dataclasses import dataclass
import operator
import re
from collections.abc import Iterable

from PIL import Image, ImageChops, ImageOps
from PySide6.QtGui import QColor, QImage, qGray

from app.painter_selection_mask import (
    combine_selection_masks,
    invert_selection_mask,
    selection_mask_alpha8,
)


SAVED_SELECTION_SAVE_OPERATIONS = (
    "new",
    "replace",
    "add",
    "subtract",
    "intersect",
)
SAVED_SELECTION_LOAD_OPERATIONS = ("new", "add", "subtract", "intersect")
_CHANNEL_ID_PATTERN = re.compile(r"saved-selection-[1-9][0-9]*\Z")
SAVED_SELECTION_CHANNEL_DISPLAY_MODES = ("masked_areas", "selected_areas")
SAVED_SELECTION_CHANNEL_DEFAULT_OVERLAY_COLOR = "#ff0000"
SAVED_SELECTION_CHANNEL_DEFAULT_OVERLAY_OPACITY_PERCENT = 50


@dataclass(frozen=True)
class SavedSelectionChannel:
    channel_id: str
    name: str
    mask: QImage
    display_mode: str = "masked_areas"
    overlay_color: str = SAVED_SELECTION_CHANNEL_DEFAULT_OVERLAY_COLOR
    overlay_opacity_percent: int = (
        SAVED_SELECTION_CHANNEL_DEFAULT_OVERLAY_OPACITY_PERCENT
    )


def normalize_saved_selection_channel_display_mode(value: object) -> str:
    mode = str(value or "").strip().casefold()
    if mode not in SAVED_SELECTION_CHANNEL_DISPLAY_MODES:
        raise ValueError("Saved selection channel display mode is unsupported")
    return mode


def normalize_saved_selection_channel_overlay_color(value: object) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise TypeError("Saved selection channel overlay color must be a string")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError("Saved selection channel overlay color must be #RRGGBB")
    color = QColor(value)
    if not color.isValid():
        raise ValueError("Saved selection channel overlay color is invalid")
    return color.name(QColor.NameFormat.HexRgb)


def normalize_saved_selection_channel_overlay_opacity(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("Saved selection channel overlay opacity must be an integer")
    try:
        opacity = operator.index(value)
    except TypeError as exc:
        raise TypeError(
            "Saved selection channel overlay opacity must be an integer"
        ) from exc
    if not 0 <= opacity <= 100:
        raise ValueError(
            "Saved selection channel overlay opacity must be from 0 through 100"
        )
    return opacity


def _copy_saved_selection_channel(row: SavedSelectionChannel) -> SavedSelectionChannel:
    return SavedSelectionChannel(
        row.channel_id,
        row.name,
        QImage(row.mask),
        row.display_mode,
        row.overlay_color,
        row.overlay_opacity_percent,
    )


def normalize_saved_selection_name(value: object) -> str:
    name = str(value or "").strip()
    if not name:
        raise ValueError("Saved selection channel name must not be blank")
    return name


def normalize_saved_selection_channel_id(value: object) -> str:
    channel_id = str(value or "").strip()
    if not _CHANNEL_ID_PATTERN.fullmatch(channel_id):
        raise ValueError("Saved selection channel id is invalid")
    return channel_id


def normalize_saved_selection_operation(value: object, *, loading: bool) -> str:
    operation = str(value or "new").strip().casefold()
    allowed = (
        SAVED_SELECTION_LOAD_OPERATIONS
        if loading
        else SAVED_SELECTION_SAVE_OPERATIONS
    )
    if operation not in allowed:
        raise ValueError("Saved selection channel operation is unsupported")
    return operation


def copy_saved_selection_channels(
    rows: Iterable[SavedSelectionChannel],
) -> list[SavedSelectionChannel]:
    return [
        _copy_saved_selection_channel(row)
        for row in rows
    ]


def normalize_saved_selection_channels(
    rows: Iterable[SavedSelectionChannel],
    width: int,
    height: int,
) -> list[SavedSelectionChannel]:
    normalized: list[SavedSelectionChannel] = []
    ids: set[str] = set()
    names: set[str] = set()
    for row in rows:
        if not isinstance(row, SavedSelectionChannel):
            raise TypeError("Saved selection channel row is invalid")
        channel_id = normalize_saved_selection_channel_id(row.channel_id)
        name = normalize_saved_selection_name(row.name)
        folded_name = name.casefold()
        if channel_id in ids or folded_name in names:
            raise ValueError("Saved selection channel identity is duplicated")
        if not isinstance(row.mask, QImage) or row.mask.isNull():
            raise ValueError("Saved selection channel mask is missing")
        if row.mask.width() != width or row.mask.height() != height:
            raise ValueError(
                "Saved selection channel mask dimensions must match the document"
            )
        ids.add(channel_id)
        names.add(folded_name)
        normalized.append(SavedSelectionChannel(
            channel_id,
            name,
            selection_mask_alpha8(row.mask, width, height),
            normalize_saved_selection_channel_display_mode(row.display_mode),
            normalize_saved_selection_channel_overlay_color(row.overlay_color),
            normalize_saved_selection_channel_overlay_opacity(
                row.overlay_opacity_percent
            ),
        ))
    return normalized


def combine_saved_selection_mask(
    existing: QImage,
    incoming: QImage,
    operation: str,
) -> QImage:
    normalized = normalize_saved_selection_operation(operation, loading=False)
    mode = "new" if normalized == "replace" else normalized
    return combine_selection_masks(existing, incoming, mode)


def load_saved_selection_mask(
    current: QImage | None,
    saved: QImage,
    operation: str,
    *,
    invert: bool = False,
) -> QImage:
    normalized = normalize_saved_selection_operation(operation, loading=True)
    incoming = invert_selection_mask(saved) if bool(invert) else QImage(saved)
    return combine_selection_masks(current, incoming, normalized)


def saved_selection_channel_grayscale_value(color: QColor) -> int:
    """Return the documented grayscale intensity painted into an alpha channel."""
    if not isinstance(color, QColor) or not color.isValid():
        raise ValueError("Saved selection channel paint color must be valid")
    return qGray(color.rgb())


def apply_saved_selection_channel_coverage(
    mask: QImage,
    coverage: QImage,
    channel_value: int,
) -> QImage:
    """Composite a brush coverage raster toward one exact Alpha8 value."""
    from app.painter_quick_mask import apply_quick_mask_coverage

    return apply_quick_mask_coverage(mask, coverage, channel_value)


def saved_selection_channel_view_image(
    mask: QImage,
    width: int,
    height: int,
    *,
    composite_visible: bool,
    display_mode: str = "masked_areas",
    overlay_color: str = SAVED_SELECTION_CHANNEL_DEFAULT_OVERLAY_COLOR,
    overlay_opacity_percent: int = (
        SAVED_SELECTION_CHANNEL_DEFAULT_OVERLAY_OPACITY_PERCENT
    ),
) -> QImage:
    """Build the grayscale-alone or composite-overlay channel view."""
    prepared = selection_mask_alpha8(mask, width, height)
    mode = normalize_saved_selection_channel_display_mode(display_mode)
    color = QColor(normalize_saved_selection_channel_overlay_color(overlay_color))
    opacity = normalize_saved_selection_channel_overlay_opacity(
        overlay_opacity_percent
    )
    selected = Image.frombuffer(
        "L",
        (prepared.width(), prepared.height()),
        bytes(prepared.constBits()),
        "raw",
        "L",
        prepared.bytesPerLine(),
        1,
    ).copy()
    displayed = selected if mode == "masked_areas" else ImageOps.invert(selected)
    if not composite_visible:
        grayscale = Image.merge("RGBA", (displayed, displayed, displayed, Image.new("L", displayed.size, 255)))
        return QImage(
            grayscale.tobytes(),
            width,
            height,
            width * 4,
            QImage.Format.Format_RGBA8888,
        ).copy()
    overlay_area = ImageOps.invert(selected) if mode == "masked_areas" else selected
    maximum_alpha = int(round(255 * opacity / 100))
    overlay_alpha = ImageChops.multiply(
        overlay_area,
        Image.new("L", overlay_area.size, maximum_alpha),
    )
    overlay = Image.new("RGBA", overlay_area.size, (*color.getRgb()[:3], 0))
    overlay.putalpha(overlay_alpha)
    return QImage(
        overlay.tobytes(),
        width,
        height,
        width * 4,
        QImage.Format.Format_RGBA8888,
    ).copy()


def set_saved_selection_channel_options(
    rows: Iterable[SavedSelectionChannel],
    channel_id: str,
    *,
    display_mode: object,
    overlay_color: object,
    overlay_opacity_percent: object,
) -> list[SavedSelectionChannel]:
    target_id = normalize_saved_selection_channel_id(channel_id)
    mode = normalize_saved_selection_channel_display_mode(display_mode)
    color = normalize_saved_selection_channel_overlay_color(overlay_color)
    opacity = normalize_saved_selection_channel_overlay_opacity(
        overlay_opacity_percent
    )
    copied = copy_saved_selection_channels(rows)
    target = next((row for row in copied if row.channel_id == target_id), None)
    if target is None:
        raise ValueError("Saved selection channel does not exist")
    if (
        target.display_mode == mode
        and target.overlay_color == color
        and target.overlay_opacity_percent == opacity
    ):
        raise ValueError("Saved selection channel options would not change")
    return [
        SavedSelectionChannel(
            row.channel_id,
            row.name,
            QImage(row.mask),
            mode if row.channel_id == target_id else row.display_mode,
            color if row.channel_id == target_id else row.overlay_color,
            opacity if row.channel_id == target_id else row.overlay_opacity_percent,
        )
        for row in copied
    ]


def rename_saved_selection_channel(
    rows: Iterable[SavedSelectionChannel],
    channel_id: str,
    name: str,
) -> list[SavedSelectionChannel]:
    target_id = normalize_saved_selection_channel_id(channel_id)
    resolved_name = normalize_saved_selection_name(name)
    copied = copy_saved_selection_channels(rows)
    target = next((row for row in copied if row.channel_id == target_id), None)
    if target is None:
        raise ValueError("Saved selection channel does not exist")
    if any(
        row.channel_id != target_id
        and row.name.casefold() == resolved_name.casefold()
        for row in copied
    ):
        raise ValueError("Saved selection channel name already exists")
    if target.name == resolved_name:
        raise ValueError("Saved selection channel name would not change")
    return [
        SavedSelectionChannel(
            row.channel_id,
            resolved_name if row.channel_id == target_id else row.name,
            QImage(row.mask),
            row.display_mode,
            row.overlay_color,
            row.overlay_opacity_percent,
        )
        for row in copied
    ]


def duplicate_saved_selection_channel(
    rows: Iterable[SavedSelectionChannel],
    channel_id: str,
    new_channel_id: str,
    name: str,
    *,
    invert: bool = False,
) -> list[SavedSelectionChannel]:
    if not isinstance(invert, bool):
        raise TypeError("Saved selection channel invert must be a boolean")
    source_id = normalize_saved_selection_channel_id(channel_id)
    duplicate_id = normalize_saved_selection_channel_id(new_channel_id)
    resolved_name = normalize_saved_selection_name(name)
    copied = copy_saved_selection_channels(rows)
    source = next((row for row in copied if row.channel_id == source_id), None)
    if source is None:
        raise ValueError("Saved selection channel does not exist")
    if any(row.channel_id == duplicate_id for row in copied):
        raise ValueError("Saved selection channel id already exists")
    if any(row.name.casefold() == resolved_name.casefold() for row in copied):
        raise ValueError("Saved selection channel name already exists")
    mask = invert_selection_mask(source.mask) if invert else QImage(source.mask)
    copied.append(SavedSelectionChannel(
        duplicate_id,
        resolved_name,
        mask,
        source.display_mode,
        source.overlay_color,
        source.overlay_opacity_percent,
    ))
    return copied


def reorder_saved_selection_channel(
    rows: Iterable[SavedSelectionChannel],
    channel_id: str,
    target_channel_id: str,
    placement: str,
) -> list[SavedSelectionChannel]:
    source_id = normalize_saved_selection_channel_id(channel_id)
    target_id = normalize_saved_selection_channel_id(target_channel_id)
    if source_id == target_id:
        raise ValueError("Saved selection channel reorder requires two channels")
    resolved_placement = str(placement or "").strip().casefold()
    if resolved_placement not in {"before", "after"}:
        raise ValueError("Saved selection channel placement is unsupported")
    copied = copy_saved_selection_channels(rows)
    source = next((row for row in copied if row.channel_id == source_id), None)
    target = next((row for row in copied if row.channel_id == target_id), None)
    if source is None or target is None:
        raise ValueError("Saved selection channel does not exist")
    before_ids = [row.channel_id for row in copied]
    copied = [row for row in copied if row.channel_id != source_id]
    target_index = next(
        index for index, row in enumerate(copied) if row.channel_id == target_id
    )
    insert_index = target_index if resolved_placement == "before" else target_index + 1
    copied.insert(insert_index, source)
    if [row.channel_id for row in copied] == before_ids:
        raise ValueError("Saved selection channel order would not change")
    return copied


def delete_saved_selection_channel(
    rows: Iterable[SavedSelectionChannel],
    channel_id: str,
) -> tuple[list[SavedSelectionChannel], str]:
    target_id = normalize_saved_selection_channel_id(channel_id)
    copied = copy_saved_selection_channels(rows)
    target_index = next(
        (index for index, row in enumerate(copied) if row.channel_id == target_id),
        None,
    )
    if target_index is None:
        raise ValueError("Saved selection channel does not exist")
    del copied[target_index]
    if not copied:
        fallback = "RGB"
    else:
        fallback = copied[min(target_index, len(copied) - 1)].channel_id
    return copied, fallback


__all__ = [
    "SAVED_SELECTION_CHANNEL_DEFAULT_OVERLAY_COLOR",
    "SAVED_SELECTION_CHANNEL_DEFAULT_OVERLAY_OPACITY_PERCENT",
    "SAVED_SELECTION_CHANNEL_DISPLAY_MODES",
    "SAVED_SELECTION_LOAD_OPERATIONS",
    "SAVED_SELECTION_SAVE_OPERATIONS",
    "SavedSelectionChannel",
    "apply_saved_selection_channel_coverage",
    "combine_saved_selection_mask",
    "copy_saved_selection_channels",
    "delete_saved_selection_channel",
    "duplicate_saved_selection_channel",
    "load_saved_selection_mask",
    "normalize_saved_selection_channel_id",
    "normalize_saved_selection_channel_display_mode",
    "normalize_saved_selection_channel_overlay_color",
    "normalize_saved_selection_channel_overlay_opacity",
    "normalize_saved_selection_channels",
    "normalize_saved_selection_name",
    "normalize_saved_selection_operation",
    "rename_saved_selection_channel",
    "reorder_saved_selection_channel",
    "saved_selection_channel_grayscale_value",
    "saved_selection_channel_view_image",
    "set_saved_selection_channel_options",
]
