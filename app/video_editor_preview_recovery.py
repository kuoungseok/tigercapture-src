"""Duck-typed preview recovery helpers for ``VideoEditorWindow``.

The helpers intentionally avoid importing Qt at module import time.  Callers
pass the owner object, and wrappers can inject ``QPixmap``/``QTimer`` factories
from the UI layer.
"""

from __future__ import annotations

import time
from typing import Any, Callable


BLANK_PREVIEW_MAX_WIDTH = 32
BLANK_PREVIEW_MAX_HEIGHT = 32
BLACK_FRAME_SAMPLE_SIZE = 16
BLACK_FRAME_MEAN_THRESHOLD = 1.0
BLACK_FRAME_MAX_THRESHOLD = 3.0

PixmapFactory = Callable[[Any], Any]
SingleShot = Callable[[int, Callable[[], None]], None]


def _call_attr(obj: Any, name: str, default: Any = None) -> Any:
    value = getattr(obj, name, default)
    if callable(value):
        return value()
    return value


def _int_attr(obj: Any, name: str, default: int = 0) -> int:
    try:
        return int(_call_attr(obj, name, default))
    except Exception:
        return int(default)


def _pixmap_is_null(pixmap: Any) -> bool:
    if pixmap is None:
        return True
    is_null = getattr(pixmap, "isNull", None)
    if not callable(is_null):
        return False
    try:
        return bool(is_null())
    except Exception:
        return True


def _clone_pixmap(pixmap: Any, pixmap_factory: PixmapFactory | None = None) -> Any:
    if pixmap is None:
        return None
    if pixmap_factory is not None:
        return pixmap_factory(pixmap)
    try:
        return pixmap.__class__(pixmap)
    except Exception:
        copy = getattr(pixmap, "copy", None)
        if callable(copy):
            try:
                return copy()
            except Exception:
                pass
    return pixmap


def pixmap_looks_like_blank_preview(pixmap: Any) -> bool:
    """Return whether ``pixmap`` is the editor's tiny no-video placeholder.

    Large black frames are deliberately not blank.  The recovery path can only
    replace them while an explicit black-frame transition guard is active.
    """

    if _pixmap_is_null(pixmap):
        return True
    width = _int_attr(pixmap, "width", -1)
    height = _int_attr(pixmap, "height", -1)
    if width < 0 or height < 0:
        return False
    return width <= BLANK_PREVIEW_MAX_WIDTH and height <= BLANK_PREVIEW_MAX_HEIGHT


def rgb_looks_like_blank_preview(rgb: Any) -> bool:
    try:
        height, width = rgb.shape[:2]
    except Exception:
        return False
    return (
        int(width) <= BLANK_PREVIEW_MAX_WIDTH
        and int(height) <= BLANK_PREVIEW_MAX_HEIGHT
    )


def _qt_rgb888_format() -> Any:
    try:
        from PySide6.QtGui import QImage

        return QImage.Format.Format_RGB888
    except Exception:
        return "RGB888"


def _qt_fast_scale_args() -> tuple[Any, Any]:
    try:
        from PySide6.QtCore import Qt

        return (
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
    except Exception:
        return ()


def _convert_image_to_rgb888(image: Any) -> Any:
    convert = getattr(image, "convertToFormat", None)
    if not callable(convert):
        return image
    for fmt in (_qt_rgb888_format(), "RGB888"):
        try:
            return convert(fmt)
        except Exception:
            pass
    return image


def _scale_image_for_black_sample(image: Any) -> Any:
    scaled = getattr(image, "scaled", None)
    if not callable(scaled):
        return image
    width = BLACK_FRAME_SAMPLE_SIZE
    height = BLACK_FRAME_SAMPLE_SIZE
    scale_args = _qt_fast_scale_args()
    if scale_args:
        try:
            return scaled(width, height, *scale_args)
        except Exception:
            pass
    try:
        return scaled(width, height)
    except Exception:
        return image


def _image_bits_bytes(image: Any, byte_count: int) -> bytes | None:
    bits = getattr(image, "bits", None)
    if not callable(bits):
        return None
    try:
        raw = bytes(bits())
    except Exception:
        return None
    if len(raw) < byte_count:
        return None
    return raw[:byte_count]


def _rgb_image_channel_stats(image: Any) -> tuple[float, int] | None:
    width = _int_attr(image, "width", 0)
    height = _int_attr(image, "height", 0)
    if width <= 0 or height <= 0:
        return 0.0, 0
    bytes_per_line = _int_attr(image, "bytesPerLine", width * 3)
    if bytes_per_line < width * 3:
        return None
    raw = _image_bits_bytes(image, bytes_per_line * height)
    if raw is None:
        return None

    total = 0
    count = 0
    max_value = 0
    row_width = width * 3
    for row in range(height):
        start = row * bytes_per_line
        for value in raw[start : start + row_width]:
            total += value
            count += 1
            if value > max_value:
                max_value = value
    if count <= 0:
        return 0.0, 0
    return float(total) / float(count), max_value


def pixmap_looks_like_black_frame(pixmap: Any) -> bool:
    if pixmap_looks_like_blank_preview(pixmap):
        return True
    try:
        image = pixmap.toImage()
        image = _convert_image_to_rgb888(image)
        image = _scale_image_for_black_sample(image)
        stats = _rgb_image_channel_stats(image)
        if stats is None:
            return False
        mean_value, max_value = stats
        return (
            mean_value < BLACK_FRAME_MEAN_THRESHOLD
            and max_value <= BLACK_FRAME_MAX_THRESHOLD
        )
    except Exception:
        return False


def preview_tab_guard_active(owner: Any, *, now_ms: float | None = None) -> bool:
    if now_ms is None:
        now_ms = time.monotonic() * 1000.0
    try:
        deadline = float(getattr(owner, "_preview_tab_guard_until_ms", 0.0) or 0.0)
    except Exception:
        deadline = 0.0
    return float(now_ms) <= deadline


def preview_black_recovery_active(owner: Any, *, now_ms: float | None = None) -> bool:
    if now_ms is None:
        now_ms = time.monotonic() * 1000.0
    try:
        deadline = float(
            getattr(owner, "_preview_black_recovery_until_ms", 0.0) or 0.0
        )
    except Exception:
        deadline = 0.0
    return float(now_ms) <= deadline


def _owner_bool(owner: Any, method_name: str, fallback: Callable[[], bool]) -> bool:
    method = getattr(owner, method_name, None)
    if callable(method):
        try:
            return bool(method())
        except Exception:
            return False
    try:
        return bool(fallback())
    except Exception:
        return False


def _owner_preview_tab_guard_active(owner: Any) -> bool:
    return _owner_bool(owner, "_preview_tab_guard_active", lambda: preview_tab_guard_active(owner))


def _owner_black_recovery_active(owner: Any) -> bool:
    return _owner_bool(
        owner,
        "_preview_black_recovery_active",
        lambda: preview_black_recovery_active(owner),
    )


def _owner_active_renderable_clip(owner: Any) -> bool:
    return _owner_bool(owner, "_active_renderable_clip_at_current_position", lambda: False)


def preview_recovery_source(
    owner: Any,
    *,
    pixmap_factory: PixmapFactory | None = None,
) -> Any:
    current = getattr(owner, "_preview_pixmap", None)
    if not pixmap_looks_like_blank_preview(current):
        return _clone_pixmap(current, pixmap_factory)
    last_good = getattr(owner, "_last_good_preview_pixmap", None)
    if not pixmap_looks_like_blank_preview(last_good):
        return _clone_pixmap(last_good, pixmap_factory)
    return None


def preview_recovery_rgb(owner: Any) -> Any:
    rgb = getattr(owner, "_last_good_preview_rgb", None)
    if rgb is None or rgb_looks_like_blank_preview(rgb):
        return None
    try:
        import numpy as _np

        return _np.ascontiguousarray(rgb).copy()
    except Exception:
        return rgb


def remember_good_preview_pixmap(
    owner: Any,
    *,
    pixmap_factory: PixmapFactory | None = None,
) -> bool:
    pixmap = getattr(owner, "_preview_pixmap", None)
    if pixmap_looks_like_blank_preview(pixmap):
        return False
    if not _owner_active_renderable_clip(owner):
        return False
    owner._last_good_preview_pixmap = _clone_pixmap(pixmap, pixmap_factory)
    return True


def restore_preview_if_tab_switch_blank(
    owner: Any,
    backup: Any = None,
    *,
    pixmap_factory: PixmapFactory | None = None,
) -> bool:
    if not _owner_preview_tab_guard_active(owner):
        return False
    if not _owner_active_renderable_clip(owner):
        return False

    current = getattr(owner, "_preview_pixmap", None)
    current_is_blank = pixmap_looks_like_blank_preview(current)
    may_recover_black = (
        _owner_black_recovery_active(owner)
        and pixmap_looks_like_black_frame(current)
    )
    if not current_is_blank and not may_recover_black:
        return False

    source = backup
    if pixmap_looks_like_blank_preview(source):
        source = getattr(owner, "_last_good_preview_pixmap", None)
    if pixmap_looks_like_blank_preview(source):
        return False

    owner._preview_pixmap = _clone_pixmap(source, pixmap_factory)
    scale = getattr(owner, "_scale_preview_to_fit", None)
    if callable(scale):
        try:
            scale()
        except Exception:
            pass

    popout = getattr(owner, "_preview_popout", None)
    if popout is not None:
        try:
            popout.update_frame(owner._preview_pixmap.toImage())
        except Exception:
            pass
    return True


def start_preview_transition_guard(
    owner: Any,
    duration_ms: int = 650,
    *,
    recover_black: bool = False,
    now_ms: float | None = None,
    pixmap_factory: PixmapFactory | None = None,
) -> Any:
    backup = preview_recovery_source(owner, pixmap_factory=pixmap_factory)
    if now_ms is None:
        now_ms = time.monotonic() * 1000.0
    deadline = float(now_ms) + max(120, int(duration_ms))
    owner._preview_tab_guard_until_ms = deadline
    if recover_black:
        owner._preview_black_recovery_until_ms = deadline
    return backup


def schedule_preview_transition_restore(
    owner: Any,
    backup: Any = None,
    *,
    single_shot: SingleShot | None = None,
    pixmap_factory: PixmapFactory | None = None,
) -> None:
    restore_preview_if_tab_switch_blank(
        owner,
        backup,
        pixmap_factory=pixmap_factory,
    )
    if single_shot is None:
        return
    try:
        single_shot(
            0,
            lambda b=backup: restore_preview_if_tab_switch_blank(
                owner,
                b,
                pixmap_factory=pixmap_factory,
            ),
        )
        single_shot(
            120,
            lambda b=backup: restore_preview_if_tab_switch_blank(
                owner,
                b,
                pixmap_factory=pixmap_factory,
            ),
        )
    except Exception:
        pass


def refresh_preview_after_color_toggle(
    owner: Any,
    *,
    pixmap_factory: PixmapFactory | None = None,
    schedule_restore: Callable[[Any], None] | None = None,
) -> Any:
    backup = start_preview_transition_guard(
        owner,
        650,
        recover_black=True,
        pixmap_factory=pixmap_factory,
    )
    player = getattr(owner, "_player", None)
    try:
        if player is not None:
            player.refresh_current_frame()
    except Exception:
        try:
            if player is not None:
                player.set_position(player.position())
        except Exception:
            pass
    if schedule_restore is not None:
        schedule_restore(backup)
    else:
        schedule_preview_transition_restore(
            owner,
            backup,
            pixmap_factory=pixmap_factory,
        )
    return backup
