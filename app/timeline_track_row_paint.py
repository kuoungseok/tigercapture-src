from __future__ import annotations

import time

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from app.i18n import tr
from app.qt_pixmap_painting import draw_pixmap_cover as _draw_pixmap_cover
from app.studio_theme import (
    STUDIO_ACTION,
    STUDIO_ACTION_EDGE,
    STUDIO_CUT,
    paint_scissors_marker,
    paint_studio_clip_block,
    paint_studio_clip_label,
    paint_studio_playhead,
    paint_timeline_burst,
)
from app.style import COLOR_ACCENT_ORANGE
from app.timeline_striped_host import StripedHost
from app.timeline_track_row_lane_paint import paint_timeline_lane_header
from app.timeline_nle_visual_overlay import (
    build_clip_anchor_cue,
    build_drag_preview_visual_cue,
    build_role_focus_cue,
    paint_clip_anchor_cue,
    paint_drag_preview_guides,
    paint_role_focus_dim,
)


_TIMELINE_THUMB_BASE_SOFTEN = 1.0
_TIMELINE_PLAYHEAD_DETAIL_SCALE = 1.48
_TIMELINE_PLAYHEAD_BLEND_SCALE = 1.62
_TIMELINE_PLAYHEAD_DETAIL_BOOST = 0.88
_TIMELINE_ACTIVE_THUMB_SOFTEN = _TIMELINE_THUMB_BASE_SOFTEN * 0.70
_TIMELINE_INACTIVE_THUMB_SOFTEN = _TIMELINE_THUMB_BASE_SOFTEN


def _scaled_timeline_thumb_blur(tile: QPixmap, scale_down: float) -> QPixmap:
    if tile.isNull() or tile.width() <= 0 or tile.height() <= 0:
        return tile
    scale_down = max(1.0, float(scale_down))
    if scale_down <= 1.01:
        return tile.copy()
    low_w = max(1, int(round(tile.width() / scale_down)))
    low_h = max(1, int(round(tile.height() / scale_down)))
    low = tile.scaled(
        low_w,
        low_h,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return low.scaled(
        tile.width(),
        tile.height(),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _timeline_softened_thumb_tile(tile: QPixmap, soften: float) -> QPixmap:
    softness = max(0.0, min(1.0, float(soften)))
    if softness <= 0.0 or tile.isNull():
        return tile
    wide = _scaled_timeline_thumb_blur(tile, 2.8 + softness * 4.2)
    close = _scaled_timeline_thumb_blur(tile, 1.8 + softness * 2.2)
    result = QPixmap(tile.width(), tile.height())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.setOpacity(1.0)
    painter.drawPixmap(0, 0, wide)
    painter.setOpacity(0.34)
    painter.drawPixmap(0, 0, close)
    painter.setOpacity(0.08)
    painter.drawPixmap(0, 0, tile)
    painter.end()
    return result


def _timeline_thumb_tile_left_fade(tile: QPixmap, crossfade_w: int) -> QPixmap:
    if tile.isNull() or tile.width() <= 0 or tile.height() <= 0:
        return tile
    crossfade_w = max(0, min(int(crossfade_w), tile.width() - 1))
    if crossfade_w <= 0:
        return tile

    faded = QPixmap(tile.width(), tile.height())
    faded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(faded)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.drawPixmap(0, 0, tile)

    mask = QPixmap(tile.width(), tile.height())
    mask.fill(Qt.GlobalColor.transparent)
    mask_painter = QPainter(mask)
    gradient = QLinearGradient(0.0, 0.0, float(crossfade_w), 0.0)
    gradient.setColorAt(0.0, QColor(255, 255, 255, 0))
    gradient.setColorAt(1.0, QColor(255, 255, 255, 255))
    mask_painter.fillRect(QRect(0, 0, crossfade_w, tile.height()), QBrush(gradient))
    if crossfade_w < tile.width():
        mask_painter.fillRect(
            QRect(crossfade_w, 0, tile.width() - crossfade_w, tile.height()),
            QColor(255, 255, 255, 255),
        )
    mask_painter.end()

    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.drawPixmap(0, 0, mask)
    painter.end()
    return faded


def _timeline_track_focus_values(active: bool) -> tuple[float, float, float]:
    if active:
        return _TIMELINE_ACTIVE_THUMB_SOFTEN, 0.76, 1.0
    return _TIMELINE_INACTIVE_THUMB_SOFTEN, 0.64, 1.0


def _paint_clip_track_identity_strip(
    painter: QPainter,
    clip_rect: QRect,
    edge: QColor,
    *,
    active: bool,
    selected: bool,
) -> None:
    if clip_rect.width() <= 10 or clip_rect.height() <= 12:
        return
    color = QColor(edge)
    color.setAlpha(230 if active or selected else 138)
    glow = QColor(edge)
    glow.setAlpha(34 if active or selected else 16)
    strip_w = 5 if active or selected else 4
    strip = QRect(
        clip_rect.left() + 4,
        clip_rect.top() + 8,
        strip_w,
        max(4, clip_rect.height() - 16),
    )
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(glow)
    painter.drawRoundedRect(strip.adjusted(-2, -1, 3, 1), 3, 3)
    painter.setBrush(color)
    painter.drawRoundedRect(strip, 2, 2)
    painter.restore()


def _paint_active_track_context_outline(
    painter: QPainter,
    row_rect: QRect,
    edge: QColor,
    *,
    margin_left: int,
) -> None:
    if row_rect.width() <= 0 or row_rect.height() <= 0:
        return
    color = QColor(edge)
    color.setAlpha(188)
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawRoundedRect(QRect(0, 1, 3, row_rect.height() - 2), 2, 2)
    painter.restore()


def _with_alpha(color: QColor, alpha: int) -> QColor:
    out = QColor(color)
    out.setAlpha(max(0, min(255, int(alpha))))
    return out


def _paint_track_row_background_wash(
    painter: QPainter,
    rect: QRect,
    fill: QColor,
    highlight: QColor,
    edge: QColor,
    *,
    active: bool,
) -> None:
    """Keep each timeline row visibly tied to its track color, including gaps."""
    if rect.width() <= 0 or rect.height() <= 0:
        return
    fill = QColor(fill)
    highlight = QColor(highlight)
    edge = QColor(edge)
    painter.save()
    wash = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
    wash.setColorAt(0.0, _with_alpha(highlight.lighter(106), 46 if active else 34))
    wash.setColorAt(0.52, _with_alpha(fill, 36 if active else 28))
    wash.setColorAt(1.0, _with_alpha(edge.darker(112), 32 if active else 24))
    painter.fillRect(rect, QBrush(wash))
    painter.fillRect(rect.adjusted(0, 3, 0, -3), _with_alpha(fill.darker(135), 12 if active else 8))
    painter.setPen(QPen(_with_alpha(edge, 56 if active else 36), 1))
    painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
    painter.setPen(QPen(_with_alpha(edge.darker(125), 42 if active else 28), 1))
    painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
    painter.restore()


def _timeline_thumb_blend_width(tile_w: int, thumb_h: int) -> int:
    tile_w = max(1, int(tile_w))
    thumb_h = max(1, int(thumb_h))
    wanted = max(32, int(tile_w * 0.42), int(thumb_h * 1.15))
    return max(0, min(tile_w - 1, wanted))


def _timeline_thumb_tile_rects(
    preview_rect: QRect,
    tile_w: int,
    blend_w: int,
) -> list[QRect]:
    if not preview_rect.isValid() or preview_rect.width() <= 0 or preview_rect.height() <= 0:
        return []
    tile_w = max(1, int(tile_w))
    blend_w = max(0, min(tile_w - 1, int(blend_w)))
    step = max(1, tile_w - blend_w)
    rects: list[QRect] = []
    max_tiles = min(160, max(1, preview_rect.width() // step + 4))
    x = int(preview_rect.left())
    for _ in range(max_tiles):
        if x > preview_rect.right():
            break
        rects.append(QRect(x, preview_rect.top(), tile_w, preview_rect.height()))
        x += step
    if rects and rects[-1].right() < preview_rect.right():
        rects.append(
            QRect(
                preview_rect.right() - tile_w + 1,
                preview_rect.top(),
                tile_w,
                preview_rect.height(),
            )
        )
    return rects


def _timeline_thumb_tile(owner, pixmap, tile_w: int, thumb_h: int, soften: float) -> QPixmap:
    tile_w = max(1, int(tile_w))
    thumb_h = max(1, int(thumb_h))
    soften = max(0.0, min(1.0, float(soften)))
    soften_key = int(round(soften * 100.0))
    cache_key = None
    try:
        cache_key = (int(pixmap.cacheKey()), tile_w, thumb_h, soften_key)
    except Exception:
        cache_key = None
    cache = getattr(owner, "_timeline_soft_thumb_tile_cache", None) if owner is not None else None
    if owner is not None and not isinstance(cache, dict):
        cache = {}
        setattr(owner, "_timeline_soft_thumb_tile_cache", cache)
    if cache_key is not None and isinstance(cache, dict) and cache_key in cache:
        return cache[cache_key]

    base = QPixmap(tile_w, thumb_h)
    base.fill(Qt.GlobalColor.transparent)
    tile_painter = QPainter(base)
    tile_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    _draw_pixmap_cover(
        tile_painter,
        QRect(0, 0, tile_w, thumb_h),
        pixmap,
        0.0,
        opacity=1.0,
        soften=0.0,
    )
    tile_painter.end()
    tile = _timeline_softened_thumb_tile(base, soften) if soften > 0.0 else base
    if cache_key is not None and isinstance(cache, dict):
        if len(cache) > 384:
            cache.clear()
        cache[cache_key] = tile
    return tile


def _timeline_soft_thumb_tile(owner, pixmap, tile_w: int, thumb_h: int) -> QPixmap:
    return _timeline_thumb_tile(
        owner,
        pixmap,
        tile_w,
        thumb_h,
        _TIMELINE_THUMB_BASE_SOFTEN,
    )


def _timeline_playhead_detail_boost(
    layer: QPixmap,
    amount: float = _TIMELINE_PLAYHEAD_DETAIL_BOOST,
) -> QPixmap:
    if layer.isNull() or layer.width() <= 0 or layer.height() <= 0:
        return layer
    amount = max(0.0, min(1.0, float(amount)))
    if amount <= 0.001:
        return layer

    boosted = QPixmap(layer.size())
    boosted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(boosted)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.drawPixmap(0, 0, layer)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Overlay)
    painter.setOpacity(amount)
    painter.drawPixmap(0, 0, layer)
    painter.end()
    return boosted


def _build_timeline_thumb_tile_layer(
    owner,
    preview_rect: QRect,
    tile_rects: list[QRect],
    blend_w: int,
    pixmap_for_rect,
    *,
    soften: float,
) -> QPixmap:
    empty = QPixmap(max(1, preview_rect.width()), max(1, preview_rect.height()))
    empty.fill(Qt.GlobalColor.transparent)
    if not tile_rects or preview_rect.width() <= 0 or preview_rect.height() <= 0:
        return empty
    layer = QPixmap(preview_rect.width(), preview_rect.height())
    layer.fill(Qt.GlobalColor.transparent)
    layer_painter = QPainter(layer)
    layer_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    blend_w = max(0, int(blend_w))
    for tile_index, tile_rect in enumerate(tile_rects):
        pixmap = pixmap_for_rect(tile_rect)
        if pixmap is None:
            continue
        tile = _timeline_thumb_tile(
            owner,
            pixmap,
            tile_rect.width(),
            preview_rect.height(),
            soften,
        )
        local_x = int(tile_rect.left() - preview_rect.left())
        if tile_index == 0 or blend_w <= 0:
            target = QRect(local_x, 0, tile_rect.width(), preview_rect.height())
            source = QRect(0, 0, tile_rect.width(), preview_rect.height())
            layer_painter.setOpacity(1.0)
            layer_painter.drawPixmap(target, tile, source)
            continue

        crossfade_w = min(blend_w, tile_rect.width() - 1)
        layer_painter.setOpacity(1.0)
        faded_tile = _timeline_thumb_tile_left_fade(tile, crossfade_w)
        layer_painter.drawPixmap(
            QRect(local_x, 0, tile_rect.width(), preview_rect.height()),
            faded_tile,
            QRect(0, 0, tile_rect.width(), preview_rect.height()),
        )
    layer_painter.end()
    return layer


def _paint_timeline_thumb_tile_layer(
    owner,
    painter: QPainter,
    preview_rect: QRect,
    tile_rects: list[QRect],
    blend_w: int,
    opacity: float,
    pixmap_for_rect,
    *,
    soften: float = _TIMELINE_THUMB_BASE_SOFTEN,
) -> None:
    if not tile_rects or preview_rect.width() <= 0 or preview_rect.height() <= 0:
        return
    layer = _build_timeline_thumb_tile_layer(
        owner,
        preview_rect,
        tile_rects,
        blend_w,
        pixmap_for_rect,
        soften=soften,
    )

    painter.save()
    clip_path = QPainterPath()
    clip_path.addRoundedRect(QRectF(preview_rect), 5.0, 5.0)
    painter.setClipPath(clip_path, Qt.ClipOperation.IntersectClip)
    painter.setOpacity(max(0.0, min(1.0, float(opacity))))
    painter.drawPixmap(preview_rect, layer)
    painter.restore()


def _paint_timeline_playhead_sharp_thumb_window(
    owner,
    painter: QPainter,
    preview_rect: QRect,
    tile_rects: list[QRect],
    blend_w: int,
    pixmap_for_rect,
    playhead_x: int,
    *,
    strength: float = 1.0,
) -> None:
    if (
        not tile_rects
        or preview_rect.width() <= 0
        or preview_rect.height() <= 0
        or playhead_x < preview_rect.left()
        or playhead_x > preview_rect.right()
    ):
        return

    metrics = _timeline_playhead_sharp_window_metrics(owner, preview_rect, playhead_x)
    if metrics is None:
        return
    left, right, sharp_half, feather = metrics
    if right <= left:
        return

    layer = _build_timeline_thumb_tile_layer(
        owner,
        preview_rect,
        tile_rects,
        blend_w,
        pixmap_for_rect,
        soften=0.0,
    )
    if layer.isNull():
        return
    layer = _timeline_playhead_detail_boost(layer)

    painter.save()
    clip_path = QPainterPath()
    clip_path.addRoundedRect(QRectF(preview_rect), 5.0, 5.0)
    painter.setClipPath(clip_path, Qt.ClipOperation.IntersectClip)
    width = max(1, right - left + 1)
    slices = min(80, max(24, width // 4))
    for slice_index in range(slices):
        x0 = int(round(left + slice_index * width / slices))
        x1 = int(round(left + (slice_index + 1) * width / slices))
        if x1 <= x0:
            continue
        center = (x0 + x1) * 0.5
        distance = abs(center - playhead_x)
        if distance <= sharp_half:
            alpha = 1.0
        else:
            alpha = 1.0 - (distance - sharp_half) / max(1.0, float(feather))
            alpha = max(0.0, min(1.0, alpha))
            alpha = alpha * alpha * (3.0 - 2.0 * alpha)
        alpha *= max(0.0, min(1.0, float(strength)))
        if alpha <= 0.01:
            continue
        painter.setOpacity(alpha)
        source = QRect(
            int(x0 - preview_rect.left()),
            0,
            int(x1 - x0),
            preview_rect.height(),
        )
        painter.drawPixmap(
            QRect(int(x0), preview_rect.top(), int(x1 - x0), preview_rect.height()),
            layer,
            source,
        )
    painter.restore()


def _timeline_playhead_sharp_window_metrics(
    owner,
    preview_rect: QRect,
    playhead_x: int,
) -> tuple[int, int, int, int] | None:
    if (
        preview_rect.width() <= 0
        or preview_rect.height() <= 0
        or playhead_x < preview_rect.left()
        or playhead_x > preview_rect.right()
    ):
        return None
    px_per_sec = float(getattr(owner, "_px_per_sec", 80.0) or 80.0)
    base_sharp_half = max(28.0, min(120.0, px_per_sec * 0.78))
    base_feather = max(36.0, min(144.0, px_per_sec * 0.90, base_sharp_half * 2.0))
    sharp_half = int(max(34.0, min(144.0, base_sharp_half * _TIMELINE_PLAYHEAD_DETAIL_SCALE)))
    feather = int(max(54.0, min(216.0, base_feather * _TIMELINE_PLAYHEAD_BLEND_SCALE)))
    left = max(preview_rect.left(), int(playhead_x - sharp_half - feather))
    right = min(preview_rect.right(), int(playhead_x + sharp_half + feather))
    return left, right, sharp_half, feather


def paintEvent(self, event) -> None:
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    is_perf_track = self._is_performance_source_track()
    clip_fill, clip_hi, clip_edge = self._track_palette_for_role()

    paint_timeline_lane_header(self, painter, is_perf_track=is_perf_track)

    rect = self._timeline_rect()
    row_body_rect = QRect(
        self.MARGIN,
        self.LABEL_H,
        max(0, self.width() - self.MARGIN),
        self.TIMELINE_H,
    )
    # Multi-source tracks (source_path=None, clips=[??) must fall
    # through to the clip-rendering else-branch below.  Only a truly
    # empty slot (no source AND no clips) shows the "no source" placeholder.
    _has_clips = bool(getattr(self.track, "clips", None))
    if self.track.source_path is None and not _has_clips:
        # Empty slot: BRIGHTER diagonal stripes than the host background,
        # with a dashed border ??matches the 3-level hierarchy
        # (timeline host = darkest, loaded clip = middle, empty = lightest).
        self._paint_empty_slot_pattern(painter, row_body_rect)
        _paint_track_row_background_wash(
            painter,
            row_body_rect,
            clip_fill,
            clip_hi,
            clip_edge,
            active=self._is_active,
        )
        # Large watermark icon, drawn directly so it is font-independent.
        painter.save()
        wm_size = min(48, max(24, self.TIMELINE_H - 8))
        wm_x = self.width() - wm_size - 18
        wm_y = self.LABEL_H + (self.TIMELINE_H - wm_size) / 2
        wm_path = QPainterPath()
        wm_path.moveTo(wm_x, wm_y)
        wm_path.lineTo(wm_x, wm_y + wm_size)
        wm_path.lineTo(wm_x + wm_size * 0.78, wm_y + wm_size / 2)
        wm_path.closeSubpath()
        painter.fillPath(wm_path, QColor(180, 180, 220, 45))
        painter.restore()
        painter.setPen(QColor("#898989"))
        font = painter.font()
        font.setPixelSize(12)
        painter.setFont(font)
        painter.drawText(
            rect, Qt.AlignmentFlag.AlignCenter,
            tr("veditor.track.no_source"),
        )
    else:
        # Loaded clip ??Phase 1.5c paints each clip's body
        # separately so cut regions naturally show as gaps. For
        # single-clip tracks (the legacy default) this collapses
        # to one rect identical to before; for tracks with cuts
        # the cut overlay below paints over the gap to keep the
        # visual cue users expect.
        #
        # Robustness: if ``track.clips`` is momentarily empty
        # (source loaded, ``_ensure_video_clips`` hasn't run yet,
        # or a paint event slipped between the two), fall back to
        # painting the legacy ``_timeline_rect`` so the row is
        # never blank. Without this, a paint event that fires in
        # the gap leaves the user staring at an empty track row.
        clips_list = list(getattr(self.track, "clips", ()) or ())
        # 1) 80% stripes across full widget width
        full_strip = row_body_rect
        StripedHost._draw_stripes(
            painter, full_strip,
            StripedHost.BG_80, StripedHost.STRIPE_80,
        )
        painter.fillRect(
            full_strip.adjusted(0, 3, 0, -3),
            QColor(255, 255, 255, 2),
        )
        _paint_track_row_background_wash(
            painter,
            full_strip,
            clip_fill,
            clip_hi,
            clip_edge,
            active=self._is_active,
        )
        painter.save()
        painter.setPen(QColor(255, 255, 255, 7))
        grid_step = max(24, int(round(self._px_per_sec * 2.0)))
        x = self.MARGIN
        while x < self.width():
            painter.drawLine(x, full_strip.top(), x, full_strip.bottom())
            x += grid_step
        painter.restore()
        # Faint watermark play mark centred in the full track width.
        painter.save()
        wm_size = min(48, max(24, self.TIMELINE_H - 8))
        wm_x = self.width() - wm_size - 18
        wm_y = self.LABEL_H + (self.TIMELINE_H - wm_size) / 2
        wm_path = QPainterPath()
        wm_path.moveTo(wm_x, wm_y)
        wm_path.lineTo(wm_x, wm_y + wm_size)
        wm_path.lineTo(wm_x + wm_size * 0.78, wm_y + wm_size / 2)
        wm_path.closeSubpath()
        painter.fillPath(wm_path, QColor(180, 180, 220, 30))
        painter.restore()
        # 2) 50% darkness over the clip's timeline extent ??always,
        #    regardless of whether per-clip objects are ready.
        #    _timeline_rect() is robust: falls back to duration_ms when
        #    clips list is empty, so the dark area appears on first paint.
        if rect.width() > 0:
            painter.fillRect(rect, QColor(32, 32, 32, 52))
        if not clips_list and rect.width() > 0:
            paint_studio_clip_block(
                painter,
                rect,
                active=self._is_active,
                fill=clip_fill,
                highlight=clip_hi,
                edge=clip_edge,
                vertical_inset=0,
            )
        # Render each clip with a 2 px gap on its right edge when
        # another clip starts immediately after ??the gap is the
        # visible blade-cut indicator. Without it, two clips that
        # touch at a split point look like one continuous block
        # and users think Blade did nothing.
        sorted_clips = sorted(
            clips_list, key=lambda c: int(c.timeline_in_ms),
        )
        BLADE_GAP_PX = 2
        for i, clip in enumerate(sorted_clips):
            clip_rect = self._clip_rect(clip)
            if clip_rect.width() <= 0:
                continue
            # Trim the right edge if the next clip butts directly
            # against this one (boundary within 1 ms ??split, not
            # a real gap the user authored).
            if i + 1 < len(sorted_clips):
                nxt = sorted_clips[i + 1]
                if int(nxt.timeline_in_ms) - int(clip.timeline_out_ms) <= 1:
                    new_w = max(1, clip_rect.width() - BLADE_GAP_PX)
                    clip_rect = QRect(
                        clip_rect.x(), clip_rect.y(),
                        new_w, clip_rect.height(),
                    )
            # Clip body ??50% brightness solid (thumbnails on top)
            # 50% of StripedHost.BG (#373744) = #1b1b22
            paint_studio_clip_block(
                painter,
                clip_rect,
                selected=int(getattr(clip, "id", -1)) in self._selected_clip_ids,
                active=self._is_active,
                fill=clip_fill,
                highlight=clip_hi,
                edge=clip_edge,
                vertical_inset=0,
            )
            if clip_rect.width() > 16 and clip_rect.height() > 10:
                wash_rect = clip_rect.adjusted(3, 3, -3, -3)
                if wash_rect.width() > 0 and wash_rect.height() > 0:
                    wash = QLinearGradient(
                        wash_rect.left(),
                        wash_rect.top(),
                        wash_rect.right(),
                        wash_rect.bottom(),
                    )
                    wash_hi = QColor(clip_hi)
                    wash_base = QColor(clip_fill)
                    wash_hi.setAlpha(42 if self._is_active else 32)
                    wash_base.setAlpha(30 if self._is_active else 22)
                    wash.setColorAt(0.0, wash_hi)
                    wash.setColorAt(1.0, wash_base)
                    painter.fillRect(wash_rect, QBrush(wash))
            if bool(getattr(clip, "is_nested_sequence", False)):
                painter.fillRect(clip_rect.adjusted(2, 2, -2, -2), QColor(42, 62, 88, 190))
                painter.setPen(QColor("#e8f2ff"))
                f = painter.font()
                f.setPixelSize(10)
                f.setBold(True)
                painter.setFont(f)
                painter.drawText(
                    clip_rect.adjusted(6, 0, -6, 0),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    getattr(clip, "nested_sequence_name", "") or "Nested sequence",
                )
            if is_perf_track or self._is_performance_source_clip(clip):
                self._paint_performance_source_badge(painter, clip_rect)
            # Selection border moved to the END of paintEvent so
            # thumbnails / actors / blade markers no longer paint
            # over it (was the cause of "I clicked but nothing
            # turned orange" reports).

        # Thumbnails are tiled across each visible clip so clip length remains
        # readable even with the modern blurred-thumbnail treatment.
        has_any_thumbs = bool(self.track.thumbnails) or any(
            getattr(c, "thumbnails", None) for c in sorted_clips
        )
        has_thumb_duration = self.track.duration_ms > 0 or any(
            int(getattr(c, "source_duration_ms", 0) or 0) > 0
            for c in sorted_clips
        )
        if has_any_thumbs and has_thumb_duration:
            track_thumbs = self.track.thumbnails
            n_track = len(track_thumbs)
            track_h = max(1, rect.height())
            thumb_h = max(22, track_h)
            src_dur = max(1, int(self.track.duration_ms))
            painter.save()
            visible_rect = event.rect().intersected(
                QRect(0, self.LABEL_H, self.width(), self.TIMELINE_H)
            )
            visible_left = max(
                rect.left(),
                visible_rect.left() if visible_rect.isValid() else rect.left(),
            )
            visible_right = visible_rect.right() if visible_rect.isValid() else rect.right()
            for clip in sorted_clips:
                if bool(getattr(clip, "is_nested_sequence", False)):
                    continue
                clip_rect = self._clip_rect(clip)
                if clip_rect.width() <= 0 or clip_rect.right() < visible_left:
                    continue
                if clip_rect.left() > visible_right:
                    break
                src_in = int(clip.source_in_ms)
                src_out = int(clip.effective_source_out_ms)
                if src_out <= src_in:
                    continue
                clip_thumbs = getattr(clip, "thumbnails", None) or []
                if clip_thumbs:
                    thumb_list = clip_thumbs
                    n = len(clip_thumbs)
                    clip_src_dur = max(1, int(
                        getattr(clip, "source_duration_ms", src_dur) or src_dur
                    ))
                else:
                    thumb_list = track_thumbs
                    n = n_track
                    clip_src_dur = src_dur
                if n <= 0:
                    continue
                has_valid_thumb = False
                for candidate_pm in thumb_list:
                    if candidate_pm is not None and not candidate_pm.isNull():
                        has_valid_thumb = True
                        break
                if not has_valid_thumb:
                    continue
                visible_clip_left = max(clip_rect.left() + 8, visible_left + 8)
                visible_clip_right = min(clip_rect.right() - 8, visible_right - 8)
                if visible_clip_right <= visible_clip_left:
                    continue
                y = clip_rect.top() + max(0, (clip_rect.height() - thumb_h) // 2)
                preview_rect = QRect(
                    int(visible_clip_left),
                    int(y),
                    int(visible_clip_right - visible_clip_left),
                    int(thumb_h),
                )
                safe_tile_w = int(max(220, min(340, thumb_h * 6.4)))
                min_tile_w = int(max(96, min(170, thumb_h * 3.1)))
                source_tile_w = int(round(
                    (max(1, clip_src_dur) / max(1, n) / 1000.0)
                    * max(1.0, float(self._px_per_sec))
                ))
                tile_w = max(min_tile_w, min(safe_tile_w, source_tile_w))
                tile_w = max(24, min(tile_w, max(24, preview_rect.width())))
                blend_w = _timeline_thumb_blend_width(tile_w, thumb_h)
                tile_rects = _timeline_thumb_tile_rects(preview_rect, tile_w, blend_w)

                def _valid_thumb_at(index: int):
                    if not thumb_list:
                        return None
                    index = max(0, min(len(thumb_list) - 1, int(index)))
                    pm = thumb_list[index]
                    if pm is not None and not pm.isNull():
                        return pm
                    search_limit = min(len(thumb_list), 8)
                    for delta in range(1, search_limit):
                        for candidate in (index - delta, index + delta):
                            if 0 <= candidate < len(thumb_list):
                                pm = thumb_list[candidate]
                                if pm is not None and not pm.isNull():
                                    return pm
                    return None

                def _thumb_index_for_x(sample_x: float) -> int:
                    sample_project_ms = max(
                        int(clip.timeline_in_ms),
                        min(
                            int(clip.timeline_out_ms) - 1,
                            int(self._x_to_project_ms(sample_x)),
                        ),
                    )
                    sample_src_ms = src_in + max(
                        0,
                        sample_project_ms - int(clip.timeline_in_ms),
                    )
                    sample_src_ms = max(0, min(clip_src_dur - 1, sample_src_ms))
                    return max(
                        0,
                        min(n - 1, int(sample_src_ms / max(1, clip_src_dur) * n)),
                    )

                def _pixmap_for_tile(tile_rect: QRect):
                    return _valid_thumb_at(_thumb_index_for_x(tile_rect.center().x()))

                painter.save()
                painter.setClipRect(clip_rect.adjusted(5, 0, -5, 0))
                thumb_soften, thumb_opacity, playhead_detail_strength = _timeline_track_focus_values(
                    self._is_active
                )
                _paint_timeline_thumb_tile_layer(
                    self,
                    painter,
                    preview_rect,
                    tile_rects,
                    blend_w,
                    thumb_opacity,
                    _pixmap_for_tile,
                    soften=thumb_soften,
                )
                playhead_x = self._project_ms_to_x(int(getattr(self, "_position_ms", 0) or 0))
                if clip_rect.left() <= playhead_x <= clip_rect.right():
                    _paint_timeline_playhead_sharp_thumb_window(
                        self,
                        painter,
                        preview_rect,
                        tile_rects,
                        blend_w,
                        _pixmap_for_tile,
                        playhead_x,
                        strength=playhead_detail_strength,
                    )
                painter.restore()
            painter.restore()
        else:
            pass

        for i, clip in enumerate(sorted_clips):
            clip_rect = self._clip_rect(clip)
            if clip_rect.width() <= 0:
                continue
            if i + 1 < len(sorted_clips):
                nxt = sorted_clips[i + 1]
                if int(nxt.timeline_in_ms) - int(clip.timeline_out_ms) <= 1:
                    clip_rect = QRect(
                        clip_rect.x(),
                        clip_rect.y(),
                        max(1, clip_rect.width() - BLADE_GAP_PX),
                        clip_rect.height(),
                    )
            selected = int(getattr(clip, "id", -1)) in self._selected_clip_ids
            self._paint_clip_length_chrome(
                painter,
                clip_rect,
                clip=clip,
                selected=selected,
                active=self._is_active,
                fill=clip_fill,
                highlight=clip_hi,
                edge=clip_edge,
            )
            _paint_clip_track_identity_strip(
                painter,
                clip_rect,
                clip_edge,
                active=self._is_active,
                selected=selected,
            )
            self._paint_clip_nle_role_chrome(painter, clip, clip_rect)
            paint_clip_anchor_cue(
                painter,
                clip_rect,
                build_clip_anchor_cue(self.track, clip, selected=selected),
            )
            dur_ms = max(
                0,
                int(getattr(clip, "timeline_out_ms", 0))
                - int(getattr(clip, "timeline_in_ms", 0)),
            )
            if dur_ms <= 0:
                dur_ms = max(0, int(getattr(clip, "effective_length_ms", 0) or 0))
            seconds = max(1, int(round(dur_ms / 1000.0))) if dur_ms > 0 else 0
            label = ""
            if is_perf_track or self._is_performance_source_clip(clip):
                label = f"PERF  {seconds}s input" if seconds else "PERF input"
            if bool(getattr(clip, "is_nested_sequence", False)):
                label = "Nested"
            if label:
                paint_studio_clip_label(painter, clip_rect, label)

    # Speed segments overlay
    for seg in self.track.speed_segments:
        x1 = self._ms_to_x(seg.start_ms)
        x2 = self._ms_to_x(seg.end_ms)
        seg_w = max(1, x2 - x1)
        color = self._color_for_speed(seg.speed)
        painter.fillRect(x1, rect.top(), seg_w, rect.height(), color)
        self._draw_speed_label(
            painter, seg.speed, x1, rect.top(), seg_w, rect.height(),
            frame_blend=getattr(seg, "frame_blend", False),
        )
        # Edge trim handles (blue ??matches the SpeedCard accent).
        is_hover = self._hover_speed_seg is seg
        is_drag = self._speed_drag_seg is seg
        self._paint_edge_handles(
            painter,
            rect_top=rect.top(),
            rect_h=rect.height(),
            x_left=x1,
            x_right=x2,
            left_hot=(is_hover and self._hover_speed_side == "left")
                or (is_drag and self._speed_drag_mode == "resize_l"),
            right_hot=(is_hover and self._hover_speed_side == "right")
                or (is_drag and self._speed_drag_mode == "resize_r"),
            dragging=is_drag,
            base_color=QColor(216, 90, 48, 220),
            accent_color=QColor("#ff7a4a"),
        )

    # Cut segments (dark overlay)
    for cut in self.track.cuts:
        x1 = self._ms_to_x(cut.start_ms)
        x2 = self._ms_to_x(cut.end_ms)
        cut_rect = QRect(x1, rect.top(), max(1, x2 - x1), rect.height())
        painter.fillRect(cut_rect, _with_alpha(clip_fill.darker(145), 126))
        painter.fillRect(cut_rect.adjusted(0, 3, 0, -3), QColor(0, 0, 0, 78))
        painter.setPen(QPen(_with_alpha(clip_edge, 82), 1))
        painter.drawLine(cut_rect.left(), cut_rect.top(), cut_rect.left(), cut_rect.bottom())
        painter.drawLine(cut_rect.right(), cut_rect.top(), cut_rect.right(), cut_rect.bottom())
        if x2 - x1 > 24:
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                QRect(x1, rect.top(), x2 - x1, rect.height()),
                Qt.AlignmentFlag.AlignCenter,
                tr("veditor.cut_label"),
            )

    # Fade segments ??orange gradient "actors", resizable via edge drag.
    for fade in self.track.fades:
        self._paint_fade_segment(painter, fade, rect)

    # Typography actors ??orange?萸쫒nk gradient chips at the top of the
    # track strip. Draw AFTER fades so they always read on top.
    for actor in getattr(self.track, "typography_actors", []):
        self._paint_typography_actor(painter, actor, rect)

    # Zoom actors - blue tinted strip. Drawn last so
    # they read on top of fades and speed but below selection / cuts.
    for zactor in getattr(self.track, "zoom_actors", []):
        self._paint_zoom_actor(painter, zactor, rect)

    # Blade-cut markers ??drawn AFTER thumbnails / actors so they
    # always read on top. Static white + Tiger Orange line with a
    # small white triangle notch at the top so the cut is obvious
    # even in screenshots. The marching-ants animation remains in
    # _tick_blade_dash + _blade_dash_offset on the editor for
    # future selection-region overlays.
    clips_for_marks = list(getattr(self.track, "clips", ()) or ())
    if len(clips_for_marks) >= 2:
        painter.save()
        sorted_for_marks = sorted(
            clips_for_marks, key=lambda c: int(c.timeline_in_ms),
        )
        for i in range(len(sorted_for_marks) - 1):
            left_clip = sorted_for_marks[i]
            right_clip = sorted_for_marks[i + 1]
            gap_ms = (
                int(right_clip.timeline_in_ms)
                - int(left_clip.timeline_out_ms)
            )
            if gap_ms > 1:
                continue
            cut_x = self._project_ms_to_x(int(left_clip.timeline_out_ms))

            # 3 px wide marker: white outer pixels + Tiger Orange
            # core. High contrast against any thumbnail underneath
            # so the cut is unmistakable.
            paint_scissors_marker(painter, cut_x, rect, progress=1.0)

            # White triangle notch at the very top ??static
            # affordance for "this was cut here", complements the
            # vertical line below.
        painter.restore()

    # CapCut-style transition blocks ??drawn after blade markers, before
    # selection borders. Each clip with transition_out_type != "" shows a
    # dark rectangular block centred on the clip boundary, spanning half
    # the transition width into each adjacent clip. The block has:
    #   ??semi-transparent dark background (#1a1a2e, alpha 200)
    #   ??centred ??label with the transition name
    #   ??left + right edge handle bars (vertical lines)
    #   ??orange border when being dragged
    from PySide6.QtGui import QPolygon as _QPolygonT
    sorted_clips_for_tr = sorted(
        (getattr(self.track, "clips", None) or []),
        key=lambda c: int(c.timeline_in_ms),
    )
    for idx_t, clip in enumerate(sorted_clips_for_tr):
        ttype = getattr(clip, "transition_out_type", "")
        if not ttype:
            continue
        t_ms = max(100, int(getattr(clip, "transition_out_ms", 500)))
        t_rect = self._transition_rect(clip, sorted_clips_for_tr)
        if t_rect is None or t_rect.width() < 4:
            continue
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Background block
        is_dragging = (self._drag_transition_clip is clip and self._dragging_transition)
        bg_color = QColor(STUDIO_ACTION)
        bg_color.setAlpha(82)
        painter.fillRect(t_rect, bg_color)

        # Border ??orange when dragging, else subdued blue-grey
        border_pen = QPen(
            STUDIO_CUT if is_dragging else STUDIO_ACTION_EDGE,
            1,
        )
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(t_rect.adjusted(1, 1, -1, -1))

        # Centre label: transition type abbreviation
        label_text = {
            "dissolve": "Cross",
            "fade_black": "Black",
            "fade_white": "White",
            "slide_left": "Slide",
            "wipe_left": "Wipe",
            "zoom_in": "Zoom In",
            "zoom_out": "Zoom Out",
            "dip_white": "Dip",
        }.get(ttype, str(ttype))
        lbl_font = painter.font()
        lbl_font.setPixelSize(7)
        painter.setFont(lbl_font)
        painter.setPen(QColor(214, 217, 224, 168))
        painter.drawText(t_rect, Qt.AlignmentFlag.AlignCenter, label_text)

        # Left and right edge handle bars (resize affordance)
        handle_w = 2
        handle_color = QColor(STUDIO_ACTION_EDGE) if not is_dragging else QColor(STUDIO_CUT)
        handle_color.setAlpha(120 if not is_dragging else 180)
        painter.fillRect(
            t_rect.left(), t_rect.top(), handle_w, t_rect.height(), handle_color,
        )
        painter.fillRect(
            t_rect.right() - handle_w + 1, t_rect.top(), handle_w, t_rect.height(), handle_color,
        )

        painter.restore()

    # Transition drop-target indicator ??bright orange vertical line at
    # the right edge of the target clip during a TransitionCard drag.
    if self._drop_target_clip_id is not None:
        for clip in (getattr(self.track, "clips", None) or []):
            if int(clip.id) != self._drop_target_clip_id:
                continue
            cr = self._clip_rect(clip)
            if cr.width() <= 0:
                break
            drop_x = cr.right()
            painter.save()
            # Thin neutral drop line at the clip boundary.
            painter.fillRect(drop_x - 1, cr.top(), 3, cr.height(),
                             QColor(235, 232, 220, 64))
            painter.fillRect(drop_x, cr.top(), 2, cr.height(),
                             QColor(206, 196, 166, 168))
            painter.restore()
            break

    if self._effect_drop_target_clip_id is not None:
        for clip in (getattr(self.track, "clips", None) or []):
            if int(getattr(clip, "id", -1)) != int(self._effect_drop_target_clip_id):
                continue
            cr = self._clip_rect(clip)
            if cr.width() <= 0:
                break
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            target = cr.adjusted(2, 3, -2, -3)
            glow = target.adjusted(-4, -4, 4, 4)
            glow_grad = QLinearGradient(glow.topLeft(), glow.bottomRight())
            glow_grad.setColorAt(0.0, QColor(214, 205, 182, 52))
            glow_grad.setColorAt(0.55, QColor(116, 124, 130, 42))
            glow_grad.setColorAt(1.0, QColor(85, 92, 96, 34))
            painter.setPen(QPen(QColor(245, 242, 232, 58), 1))
            painter.setBrush(QBrush(glow_grad))
            painter.drawRoundedRect(glow, 4, 4)

            pen = QPen(QColor(226, 220, 203, 150), 1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(target, 3, 3)

            label = str(getattr(self, "_effect_drop_target_label", "") or tr("veditor.effect_preset.default"))
            text = tr("veditor.effect_preset.drop_label", name=label)
            font = painter.font()
            font.setPixelSize(9)
            font.setBold(True)
            painter.setFont(font)
            available_w = max(34, target.width() - 10)
            text_w = min(max(60, painter.fontMetrics().horizontalAdvance(text) + 18), available_w)
            cap = QRect(target.left() + 7, target.top() + 7, text_w, 18)
            painter.setPen(QPen(QColor(245, 242, 232, 58), 1))
            cap_grad = QLinearGradient(cap.topLeft(), cap.bottomRight())
            cap_grad.setColorAt(0.0, QColor(71, 72, 70, 238))
            cap_grad.setColorAt(1.0, QColor(45, 47, 50, 226))
            painter.setBrush(QBrush(cap_grad))
            painter.drawRoundedRect(cap, 5, 5)
            painter.setPen(QColor("#EEEAE0"))
            painter.drawText(
                cap.adjusted(8, 0, -8, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, cap.width() - 14),
            )
            painter.restore()
            break
    elif self._effect_drop_blocked_label:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        label = str(getattr(self, "_effect_drop_blocked_label", "") or "")
        font = painter.font()
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        text = tr("veditor.effect_preset.drop_blocked", name=label)
        metrics = painter.fontMetrics()
        chip_w = min(max(136, metrics.horizontalAdvance(text) + 22), max(136, self.width() - 16))
        anchor_x = int(getattr(self, "_effect_drop_blocked_x", None) or self.width() // 2)
        x = max(8, min(self.width() - chip_w - 8, anchor_x - chip_w // 2))
        y = self.LABEL_H + 7
        cap = QRect(x, y, chip_w, 20)
        grad = QLinearGradient(cap.topLeft(), cap.bottomRight())
        grad.setColorAt(0.0, QColor(98, 84, 74, 218))
        grad.setColorAt(1.0, QColor(68, 61, 59, 206))
        painter.setPen(QPen(QColor(232, 222, 204, 108), 1))
        painter.setBrush(QBrush(grad))
        painter.drawRoundedRect(cap, 5, 5)
        painter.setPen(QColor("#EEEAE0"))
        painter.drawText(
            cap.adjusted(9, 0, -9, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            metrics.elidedText(text, Qt.TextElideMode.ElideRight, cap.width() - 16),
        )
        painter.restore()

    # Clip selection ??marching ants (only when video owns the selection)
    if self._drop_guide_x is not None:
        gx = int(self._drop_guide_x)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width_px = max(0, int(getattr(self, "_drop_guide_width_px", 0) or 0))
        if width_px > 12:
            block = QRect(
                gx,
                self.LABEL_H + 7,
                min(width_px, max(12, self.width() - gx - self.MARGIN)),
                max(18, self.TIMELINE_H - 14),
            )
            grad = QLinearGradient(block.topLeft(), block.bottomRight())
            grad.setColorAt(0.0, QColor(78, 84, 92, 136))
            grad.setColorAt(0.54, QColor(56, 63, 73, 122))
            grad.setColorAt(1.0, QColor(40, 46, 53, 108))
            painter.setPen(QPen(QColor(225, 231, 240, 68), 1))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(block, 7, 7)
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
            painter.drawLine(block.left() + 9, block.top() + 6, block.right() - 9, block.top() + 6)
            segments = list(getattr(self, "_drop_guide_segments", []) or [])
            if segments:
                max_end = max(
                    (
                        int(seg.get("start_ms", 0) or 0)
                        + int(seg.get("duration_ms", 900) or 900)
                    )
                    for seg in segments
                )
                max_end = max(1, max_end)
                strip = block.adjusted(8, block.height() // 2 - 4, -8, -8)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 34))
                painter.drawRoundedRect(strip, 5, 5)
                for seg in segments:
                    start = max(0, int(seg.get("start_ms", 0) or 0))
                    dur = max(120, int(seg.get("duration_ms", 900) or 900))
                    sx = strip.left() + int(strip.width() * start / max_end)
                    sw = max(8, int(strip.width() * dur / max_end))
                    sr = QRect(sx, strip.top() + 1, min(sw, strip.right() - sx + 1), strip.height() - 2)
                    if sr.width() <= 0:
                        continue
                    seg_color = QColor(str(seg.get("color", "#7E8794")))
                    seg_color.setAlpha(154)
                    painter.setBrush(seg_color)
                    painter.drawRoundedRect(sr, 4, 4)
                    if sr.width() > 38:
                        painter.setPen(QColor(242, 245, 248, 210))
                        sf = painter.font()
                        sf.setPixelSize(7)
                        sf.setBold(False)
                        painter.setFont(sf)
                        text = painter.fontMetrics().elidedText(
                            str(seg.get("label", "")),
                            Qt.TextElideMode.ElideRight,
                            sr.width() - 6,
                        )
                        painter.drawText(sr.adjusted(3, 0, -3, 0), Qt.AlignmentFlag.AlignCenter, text)
                        painter.setPen(Qt.PenStyle.NoPen)
        painter.setPen(QPen(QColor(206, 216, 230, 160), 1))
        painter.drawLine(gx, self.LABEL_H - 2, gx, self.LABEL_H + self.TIMELINE_H + 4)
        cap = QRect(gx - 31, self.LABEL_H + 4, 62, 18)
        cap = cap.intersected(QRect(4, self.LABEL_H, self.width() - 8, self.TIMELINE_H))
        painter.setPen(QPen(QColor(229, 235, 244, 62), 1))
        painter.setBrush(QColor(20, 23, 29, 226))
        painter.drawRoundedRect(cap, 7, 7)
        painter.setPen(QColor("#F2F5FA"))
        f = painter.font()
        f.setPixelSize(9)
        f.setBold(False)
        painter.setFont(f)
        painter.drawText(cap, Qt.AlignmentFlag.AlignCenter, self._drop_guide_label or "Drop")
        detail = str(getattr(self, "_drop_guide_detail", "") or "")
        if detail and width_px > 72:
            detail_w = min(max(92, painter.fontMetrics().horizontalAdvance(detail) + 16), max(96, self.width() - 12))
            detail_rect = QRect(gx + 8, cap.bottom() + 3, detail_w, 16)
            detail_rect = detail_rect.intersected(QRect(4, self.LABEL_H, self.width() - 8, self.TIMELINE_H))
            if detail_rect.width() > 50 and detail_rect.height() > 10:
                painter.setPen(QPen(QColor(229, 235, 244, 38), 1))
                painter.setBrush(QColor(20, 23, 29, 202))
                painter.drawRoundedRect(detail_rect, 7, 7)
                painter.setPen(QColor("#BFC8D6"))
                df = painter.font()
                df.setPixelSize(8)
                df.setBold(False)
                painter.setFont(df)
                painter.drawText(
                    detail_rect.adjusted(6, 0, -6, 0),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    painter.fontMetrics().elidedText(detail, Qt.TextElideMode.ElideRight, detail_rect.width() - 12),
                )
        painter.restore()

    for clip in (getattr(self.track, "clips", None) or []):
        cr = self._clip_rect(clip)
        if cr.width() <= 0:
            continue
        self._paint_color_grade_layer(painter, clip, cr)
        self._paint_clip_effect_strips(painter, clip, cr)
        self._paint_clip_status_badges(painter, clip, cr)
        paint_role_focus_dim(
            painter,
            cr,
            build_role_focus_cue(
                self.track,
                clip,
                getattr(self, "_focused_clip_role", ""),
            ),
        )

    self._paint_tracking_status_overlay(painter, rect)

    from app.timeline_track_row import _ANTS_OWNER, _draw_marching_ants

    if self._selected_clip_ids and _ANTS_OWNER == "video":
        painter.save()
        march_off = getattr(self, "_march_offset", 0)
        for clip in (getattr(self.track, "clips", None) or []):
            if int(clip.id) not in self._selected_clip_ids:
                continue
            cr = self._clip_rect(clip)
            if cr.width() <= 0:
                continue
            _draw_marching_ants(painter, cr, march_off, clip_edge)
        painter.restore()

    # Active track: same track hue as the Workbench/clip identity color.
    if self._is_active:
        _paint_active_track_context_outline(
            painter,
            QRect(0, 0, self.width(), self.height()),
            clip_edge,
            margin_left=self.MARGIN,
        )

    # Playhead ??orange, drawn on every track at project time.
    if self._drag_snap_x is not None:
        snap_pen = QPen(QColor(STUDIO_ACTION_EDGE))
        snap_pen.setWidth(1)
        painter.setPen(snap_pen)
        painter.drawLine(
            int(self._drag_snap_x),
            self.LABEL_H,
            int(self._drag_snap_x),
            self.LABEL_H + self.TIMELINE_H,
        )

    if self._drag_preview_start_ms is not None and self._drag_preview_end_ms is not None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        x1 = self._project_ms_to_x(int(self._drag_preview_start_ms))
        x2 = self._project_ms_to_x(int(self._drag_preview_end_ms))
        ghost = QRect(
            min(x1, x2),
            self.LABEL_H + 5,
            max(2, abs(x2 - x1)),
            max(10, self.TIMELINE_H - 10),
        )
        tone = str(getattr(self, "_drag_preview_tone", "") or "move")
        preview_cue = build_drag_preview_visual_cue(tone)
        fill = QColor(str(preview_cue.get("fill") or "#FFFFFF"))
        if not fill.isValid():
            fill = QColor("#FFFFFF")
        fill.setAlpha(max(0, min(255, int(preview_cue.get("alpha") or 30))))
        edge = QColor(str(preview_cue.get("accent") or "#E6EBFF"))
        if not edge.isValid():
            edge = QColor("#E6EBFF")
        edge.setAlpha(max(0, min(255, int(preview_cue.get("edge_alpha") or 170))))
        pen = QPen(
            edge,
            2 if str(preview_cue.get("tone") or "") in {"blocked", "snap", "push"} else 1,
            Qt.PenStyle.DashLine,
        )
        age = time.monotonic() - float(getattr(self, "_drag_preview_started_at", 0.0) or 0.0)
        pop = max(0.0, 1.0 - min(1.0, age / 0.16))
        if pop > 0:
            fill.setAlpha(min(160, fill.alpha() + int(34 * pop)))
            pen.setWidthF(float(pen.widthF() or pen.width()) + 0.8 * pop)
        painter.setBrush(fill)
        painter.setPen(pen)
        painter.drawRoundedRect(ghost, 7, 7)
        paint_drag_preview_guides(painter, ghost, preview_cue, pop=pop)
        painter.restore()

    if self._drag_feedback_text:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        font = QFont(painter.font())
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        text = str(self._drag_feedback_text)
        chip_w = min(max(112, metrics.horizontalAdvance(text) + 24), max(112, self.width() - 16))
        anchor_x = self._drag_feedback_x
        if anchor_x is None:
            anchor_x = self._project_ms_to_x(self._position_ms)
        x = max(8, min(self.width() - chip_w - 8, int(anchor_x) - chip_w // 2))
        age = time.monotonic() - float(getattr(self, "_drag_feedback_started_at", 0.0) or 0.0)
        pop = max(0.0, 1.0 - min(1.0, age / 0.16))
        y = max(2, self.LABEL_H - 22 - int(3 * pop))
        r = QRect(x, y, chip_w, 19)
        tone = str(getattr(self, "_drag_feedback_tone", "") or "move")
        if tone == "snap":
            fill_a = QColor(118, 98, 255, 232)
            fill_b = QColor(86, 206, 255, 220)
            border = QColor(190, 210, 255, 180)
        elif tone == "blocked":
            fill_a = QColor(255, 112, 67, 235)
            fill_b = QColor(255, 74, 118, 220)
            border = QColor(255, 220, 190, 185)
        else:
            fill_a = QColor(42, 48, 72, 232)
            fill_b = QColor(31, 36, 56, 220)
            border = QColor(160, 170, 210, 130)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, fill_a)
        grad.setColorAt(1.0, fill_b)
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(r, 9, 9)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(
            r.adjusted(10, 0, -10, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            metrics.elidedText(text, Qt.TextElideMode.ElideRight, r.width() - 18),
        )
        painter.restore()

    if self._hover_hint_text and not self._dragging_offset:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        font = QFont(painter.font())
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        text = str(self._hover_hint_text)
        chip_w = min(max(96, metrics.horizontalAdvance(text) + 20), max(96, self.width() - 16))
        anchor_x = self._hover_hint_x if self._hover_hint_x is not None else self._project_ms_to_x(self._position_ms)
        x = max(8, min(self.width() - chip_w - 8, int(anchor_x) - chip_w // 2))
        age = time.monotonic() - float(getattr(self, "_hover_hint_started_at", 0.0) or 0.0)
        pop = max(0.0, 1.0 - min(1.0, age / 0.14))
        y = self.LABEL_H + 4 - int(2 * pop)
        r = QRect(x, y, chip_w, 17)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, QColor(31, 36, 56, 220))
        grad.setColorAt(1.0, QColor(46, 51, 78, 210))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor(160, 170, 210, 120), 1))
        painter.drawRoundedRect(r, 8, 8)
        painter.setPen(QColor("#E7EAFF"))
        painter.drawText(
            r.adjusted(8, 0, -8, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            metrics.elidedText(text, Qt.TextElideMode.ElideRight, r.width() - 14),
        )
        painter.restore()

    px = self._project_ms_to_x(self._position_ms)
    paint_studio_playhead(
        painter,
        px,
        self.LABEL_H - 2,
        self.LABEL_H + self.TIMELINE_H + 2,
    )

    now = time.monotonic()
    alive_bursts: list[dict] = []
    for burst in self._timeline_bursts:
        duration = max(0.05, float(burst.get("duration", 0.28)))
        progress = (now - float(burst.get("started", now))) / duration
        if progress <= 1.0:
            bx = self._project_ms_to_x(int(burst.get("project_ms", 0)))
            by = self.LABEL_H + self.TIMELINE_H // 2
            paint_timeline_burst(painter, str(burst.get("kind", "edit")), bx, by, progress)
            alive_bursts.append(burst)
    self._timeline_bursts = alive_bursts

    # Proxy badge ??small "P" pill in the top-right corner of the label
    # area when the track is currently playing a proxy file.
    _sp = self.track.source_path
    if _sp is not None and str(_sp).endswith("_proxy.mp4"):
        painter.save()
        badge_font = painter.font()
        badge_font.setPixelSize(9)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        badge_text = "P"
        badge_w, badge_h = 14, 12
        badge_x = self.width() - self.MARGIN - badge_w
        badge_y = 0
        painter.setBrush(QColor(COLOR_ACCENT_ORANGE))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge_x, badge_y, badge_w, badge_h, 3, 3)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            QRect(badge_x, badge_y, badge_w, badge_h),
            Qt.AlignmentFlag.AlignCenter,
            badge_text,
        )
        painter.restore()

    # PIP badge ??small "PIP" pill when the track has pip_enabled=True.
    if getattr(self.track, "pip_enabled", False):
        painter.save()
        pip_badge_font = painter.font()
        pip_badge_font.setPixelSize(8)
        pip_badge_font.setBold(True)
        painter.setFont(pip_badge_font)
        _proxy_offset = 18 if (_sp is not None and str(_sp).endswith("_proxy.mp4")) else 0
        pip_badge_w, pip_badge_h = 24, 12
        pip_badge_x = self.width() - self.MARGIN - pip_badge_w - _proxy_offset
        pip_badge_y = 0
        painter.setBrush(QColor("#3a7bd5"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(pip_badge_x, pip_badge_y, pip_badge_w, pip_badge_h, 3, 3)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            QRect(pip_badge_x, pip_badge_y, pip_badge_w, pip_badge_h),
            Qt.AlignmentFlag.AlignCenter,
            "PIP",
        )
        painter.restore()

        # Linked-audio badge on clips that have linked_audio_id set
        for clip in (getattr(self.track, "clips", None) or []):
            if getattr(clip, "linked_audio_id", None) is not None:
                cr = self._clip_rect(clip)
                if cr.width() > 14:
                    painter.save()
                    lf = painter.font(); lf.setPixelSize(9); painter.setFont(lf)
                    painter.setPen(QColor("#66aaff"))
                    painter.drawText(
                        QRect(cr.x() + 2, self.LABEL_H + 2, 14, 11),
                        Qt.AlignmentFlag.AlignCenter, "A",
                    )
                    painter.restore()

        # PIP keyframe markers: small neutral diamonds at each keyframe position.
        kfs = getattr(self.track, "pip_keyframes", [])
        if kfs:
            painter.save()
            kf_y = self.LABEL_H + self.TIMELINE_H // 2
            for kf in kfs:
                kf_ms = int(kf.get("ms", 0))
                kf_x = self._project_ms_to_x(kf_ms)
                # Diamond shape
                from PySide6.QtGui import QPolygon as _QPolygon
                from PySide6.QtCore import QPoint as _QPoint
                d = 4
                diamond = _QPolygon([
                    _QPoint(kf_x, kf_y - d),
                    _QPoint(kf_x + d, kf_y),
                    _QPoint(kf_x, kf_y + d),
                    _QPoint(kf_x - d, kf_y),
                ])
                painter.setBrush(QColor(224, 222, 212, 186))
                painter.setPen(QPen(QColor(12, 14, 16, 128), 1))
                painter.drawPolygon(diamond)
            painter.restore()

    # Separator between track rows ??dark groove against the bright host
    # stripes so adjacent tracks read as distinct lanes.
    pen = QPen(QColor("#0f0f14"))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.drawLine(
        0, self.height() - 1, self.width(), self.height() - 1,
    )
