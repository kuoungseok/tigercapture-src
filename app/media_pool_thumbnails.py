"""Thumbnail, badge, and lightweight probe helpers for MediaPool."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.style import FONT_FAMILY
from app.media_pool_kinds import (
    AUDIO_EXTS,
    THUMB_SIZE,
    LIST_THUMB_H,
    LIST_THUMB_W,
    VIDEO_EXTS,
    VRM_EXTS,
    _DURATION_CACHE,
    _VIDEO_THUMB_CACHE,
    _badge_label_for_path,
    _cache_get,
    _cache_put,
    _file_cache_key,
    _kind_for_path,
)


def _probe_duration_ms(path: Path) -> int | None:
    """Best-effort duration probe. Returns None on failure."""
    key = _file_cache_key(path)
    cached = _cache_get(_DURATION_CACHE, key)
    if cached is not None or key in _DURATION_CACHE:
        return cached
    # Keep Media Pool ingest UI-only by default. Spawning ffmpeg/native
    # probes for every project media item made Windows flash small
    # console title bars during launcher -> editor startup.
    if path.suffix.lower() not in VIDEO_EXTS:
        _cache_put(_DURATION_CACHE, key, None)
        return None
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            _cache_put(_DURATION_CACHE, key, None)
            return None
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            n_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
            if fps <= 0 or n_frames <= 0:
                _cache_put(_DURATION_CACHE, key, None)
                return None
            duration = int(round((n_frames / fps) * 1000.0))
            _cache_put(_DURATION_CACHE, key, duration)
            return duration
        finally:
            cap.release()
    except Exception:
        _cache_put(_DURATION_CACHE, key, None)
        return None


def _media_pool_hdr_probe_enabled() -> bool:
    return str(os.environ.get("TIGERCAPTURE_MEDIA_POOL_HDR_PROBE", "")).strip().lower() in {
        "1", "true", "yes", "on",
    }


def _make_video_thumbnail(path: Path, size: int = THUMB_SIZE) -> QPixmap | None:
    """Extract the first frame of a video or GIF into a square pixmap."""
    key = (*_file_cache_key(path), int(size))
    cached = _cache_get(_VIDEO_THUMB_CACHE, key)
    if cached is not None:
        return cached
    """Extract the first frame of a video / GIF and letterbox it onto
    a square ``size`` × ``size`` pixmap. Returns None on any failure
    so the caller can fall back to a generic placeholder."""
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None
        try:
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            ret = False
            bgr = None
            sample_ratios = (0.08, 0.18, 0.32, 0.0)
            for ratio in sample_ratios:
                if frame_count > 1:
                    frame_idx = max(0, min(frame_count - 1, int(round((frame_count - 1) * ratio))))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, bgr = cap.read()
                if ret and bgr is not None and float(np.mean(bgr)) > 5.0:
                    break
        finally:
            cap.release()
        if not ret or bgr is None:
            return None
        h, w = bgr.shape[:2]
        if w <= 0 or h <= 0:
            return None
        # OpenCV gives BGR; flip to RGB once for the QImage view.
        rgb = bgr[:, :, ::-1]
        scale = size / max(w, h)
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        rgb_resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((size, size, 3), dtype=np.uint8)
        ox = (size - nw) // 2
        oy = (size - nh) // 2
        canvas[oy:oy + nh, ox:ox + nw] = rgb_resized
        canvas = np.ascontiguousarray(canvas)
        qimg = QImage(
            canvas.data, size, size, size * 3, QImage.Format.Format_RGB888,
        ).copy()
        pix = QPixmap.fromImage(qimg)
        _cache_put(_VIDEO_THUMB_CACHE, key, pix)
        return pix
    except Exception:
        return None


def _make_video_list_thumbnail(
    path: Path,
    width: int = LIST_THUMB_W,
    height: int = LIST_THUMB_H,
) -> QPixmap | None:
    """Extract a 16:9-ish thumbnail for compact list rows."""
    key = (*_file_cache_key(path), int(width), int(height))
    cached = _cache_get(_VIDEO_THUMB_CACHE, key)
    if cached is not None:
        return cached
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None
        try:
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            ret = False
            bgr = None
            sample_ratios = (0.08, 0.18, 0.32, 0.0)
            for ratio in sample_ratios:
                if frame_count > 1:
                    frame_idx = max(0, min(frame_count - 1, int(round((frame_count - 1) * ratio))))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, bgr = cap.read()
                if ret and bgr is not None and float(np.mean(bgr)) > 5.0:
                    break
        finally:
            cap.release()
        if not ret or bgr is None:
            return None
        h, w = bgr.shape[:2]
        if w <= 0 or h <= 0:
            return None
        rgb = bgr[:, :, ::-1]
        scale = max(width / max(1, w), height / max(1, h))
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        rgb_resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        ox = max(0, (nw - width) // 2)
        oy = max(0, (nh - height) // 2)
        cropped = rgb_resized[oy:oy + height, ox:ox + width]
        cropped = np.ascontiguousarray(cropped)
        qimg = QImage(
            cropped.data, width, height, width * 3, QImage.Format.Format_RGB888,
        ).copy()
        pix = QPixmap.fromImage(qimg)
        _cache_put(_VIDEO_THUMB_CACHE, key, pix)
        return pix
    except Exception:
        return None


def _make_video_thumbnail_at(path: Path, ratio: float, size: int = THUMB_SIZE) -> QPixmap | None:
    """Extract a frame near ``ratio`` of the source duration for hover scrub."""
    ratio = max(0.0, min(1.0, float(ratio or 0.0)))
    sample_key = int(round(ratio * 40))
    key = (*_file_cache_key(path), int(size), sample_key)
    cached = _cache_get(_VIDEO_THUMB_CACHE, key)
    if cached is not None:
        return cached
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None
        try:
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
            if frame_count > 1:
                frame_idx = max(0, min(int(frame_count) - 1, int(round((frame_count - 1) * ratio))))
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, bgr = cap.read()
        finally:
            cap.release()
        if not ret or bgr is None:
            return None
        h, w = bgr.shape[:2]
        if w <= 0 or h <= 0:
            return None
        rgb = bgr[:, :, ::-1]
        scale = size / max(w, h)
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        rgb_resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((size, size, 3), dtype=np.uint8)
        ox = (size - nw) // 2
        oy = (size - nh) // 2
        canvas[oy:oy + nh, ox:ox + nw] = rgb_resized
        canvas = np.ascontiguousarray(canvas)
        qimg = QImage(canvas.data, size, size, size * 3, QImage.Format.Format_RGB888).copy()
        pix = QPixmap.fromImage(qimg)
        _cache_put(_VIDEO_THUMB_CACHE, key, pix)
        return pix
    except Exception:
        return None


def _make_audio_thumbnail(path: Path, size: int = THUMB_SIZE) -> QPixmap:
    """Stylised vertical-bar 'waveform' for audio files. The bar
    heights are seeded by the file size so two different audio files
    produce distinct-looking thumbnails without paying for an actual
    decoded waveform extraction at pool-add time."""
    pm = QPixmap(size, size)
    pm.fill(QColor("#1a1a1a"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    n_bars = 11
    cell = size // (n_bars + 2)
    bar_w = max(2, cell - 1)
    cy = size // 2
    seed = 0
    try:
        seed = int(path.stat().st_size) & 0xFFFFFFFF
    except OSError:
        seed = abs(hash(str(path))) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)
    heights = rng.uniform(0.30, 0.95, n_bars)
    bar_color = QColor("#9a9a9a")
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bar_color)
    total_w = n_bars * bar_w + (n_bars - 1) * (cell - bar_w)
    x = (size - total_w) // 2
    for h in heights:
        h_px = max(2, int(size * 0.7 * float(h)))
        p.drawRect(QRect(x, cy - h_px // 2, bar_w, h_px))
        x += cell
    # Subtle baseline so even quiet bars sit on a visible line.
    p.setPen(QPen(QColor("#444"), 1))
    p.drawLine(8, cy, size - 8, cy)
    p.end()
    return pm


def _draw_kind_badge(pm: QPixmap, kind: str, label: str | None = None) -> QPixmap:
    """Overlay a small ``V`` / ``A`` badge in the bottom-right corner
    of a thumbnail so users can tell media types apart at a glance.
    Single-accent grey badge — text alone differentiates."""
    if kind not in ("V", "A", "S", "3", "R", "M"):
        return pm
    colors = {
        "V": "#E85D35",
        "A": "#5DCAA5",
        "S": "#7A63FF",
        "3": "#5B8CFF",
        "R": "#B06BFF",
        "M": "#FF6FAE",
    }
    out = QPixmap(pm)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    label = str(label or _badge_label_for_path(kind))
    f = QFont(p.font())
    f.setPointSize(7)
    f.setBold(True)
    p.setFont(f)
    badge_w, badge_h = max(20, p.fontMetrics().horizontalAdvance(label) + 8), 14
    pad = 4
    x = out.width() - badge_w - pad
    y = out.height() - badge_h - pad
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 72))
    p.drawRoundedRect(2, 2, out.width() - 4, out.height() - 4, 10, 10)
    p.setBrush(QColor(colors.get(kind, "#E85D35")))
    p.drawRoundedRect(x, y, badge_w, badge_h, 5, 5)
    p.setPen(QPen(QColor("#ffffff"), 1))
    p.drawText(QRect(x, y, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, label)
    p.end()
    return out


def _make_spine_thumbnail(size: int = THUMB_SIZE) -> QPixmap:
    """Small rig-style placeholder for Spine skeleton/atlas files."""
    pm = QPixmap(size, size)
    pm.fill(QColor("#1d1a25"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(QPen(QColor("#f0a060"), 3))
    cx = size // 2
    head_y = size // 3
    body_y = size // 2
    foot_y = size - 24
    p.drawEllipse(cx - 10, head_y - 10, 20, 20)
    p.drawLine(cx, head_y + 10, cx, body_y)
    p.drawLine(cx, body_y, cx - 26, body_y - 8)
    p.drawLine(cx, body_y, cx + 26, body_y - 8)
    p.drawLine(cx, body_y, cx - 20, foot_y)
    p.drawLine(cx, body_y, cx + 20, foot_y)
    p.setPen(QPen(QColor("#7a4aaa"), 1))
    p.drawRect(0, 0, size - 1, size - 1)
    p.end()
    return pm


def _make_ar_pbr_thumbnail(size: int = THUMB_SIZE) -> QPixmap:
    """Compact 3D-asset placeholder for FBX/GLB files."""
    pm = QPixmap(size, size)
    pm.fill(QColor("#111726"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(QPen(QColor("#6E8DFF"), 2))
    p.setBrush(QColor(70, 92, 170, 76))
    front = QRect(size // 2 - 14, size // 2 - 10, 28, 26)
    p.drawRoundedRect(front, 3, 3)
    p.drawLine(front.topLeft(), QPoint(front.left() + 10, front.top() - 10))
    p.drawLine(front.topRight(), QPoint(front.right() + 10, front.top() - 10))
    p.drawLine(QPoint(front.left() + 10, front.top() - 10), QPoint(front.right() + 10, front.top() - 10))
    p.drawLine(front.bottomRight(), QPoint(front.right() + 10, front.bottom() - 10))
    p.drawLine(QPoint(front.right() + 10, front.top() - 10), QPoint(front.right() + 10, front.bottom() - 10))
    p.setPen(QPen(QColor("#B8C5FF"), 1))
    p.drawText(QRect(0, size - 20, size, 16), Qt.AlignmentFlag.AlignCenter, "PBR")
    p.end()
    return pm


def _make_vrm_avatar_thumbnail(size: int = THUMB_SIZE) -> QPixmap:
    """Avatar-target placeholder for VRM assets.

    VRM files are not normal Program Output media. They are selected as the
    VTuber Studio Avatar Target and driven by Performance Source tracking.
    """
    pm = QPixmap(size, size)
    pm.fill(QColor("#19172A"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#2B244A"))
    p.drawRoundedRect(5, 5, size - 10, size - 10, 12, 12)
    p.setBrush(QColor("#B06BFF"))
    p.drawEllipse(size // 2 - 13, 14, 26, 26)
    p.setBrush(QColor("#49D5FF"))
    p.drawRoundedRect(size // 2 - 19, 42, 38, 14, 7, 7)
    p.setPen(QPen(QColor("#FFFFFF"), 2))
    p.drawLine(size // 2, 40, size // 2, 54)
    p.setPen(QPen(QColor("#F5F7FF"), 1))
    f = QFont(p.font())
    f.setPointSize(7)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRect(0, size - 20, size, 14), Qt.AlignmentFlag.AlignCenter, "AVATAR")
    p.end()
    return pm


def _make_mmd_thumbnail(size: int = THUMB_SIZE) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(QColor("#241721"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#3A2135"))
    p.drawRoundedRect(5, 5, size - 10, size - 10, 10, 10)
    p.setBrush(QColor("#FF6FAE"))
    p.drawEllipse(size // 2 - 12, 13, 24, 24)
    p.setBrush(QColor("#F8D7E6"))
    p.drawRoundedRect(size // 2 - 18, 41, 36, 24, 9, 9)
    p.setBrush(QColor("#6FE7FF"))
    p.drawRoundedRect(size // 2 - 24, 51, 48, 10, 5, 5)
    p.setPen(QPen(QColor("#FFFFFF"), 1))
    f = QFont(p.font())
    f.setPointSize(7)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRect(0, size - 20, size, 14), Qt.AlignmentFlag.AlignCenter, "MMD")
    p.end()
    return pm


def _draw_hdr_badge(pm: QPixmap, label: str) -> QPixmap:
    """HDR Phase 0: stamp a Tiger Orange pill in the TOP-right corner
    when a video is HDR (HDR10 / HLG / generic HDR). The pill is the
    only place a non-grey accent appears in the pool, so it reads
    immediately as "this clip needs special handling". Bottom-right
    stays reserved for the V/A kind badge."""
    if not label:
        return pm
    out = QPixmap(pm)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    f = QFont(p.font())
    f.setPointSize(7)
    f.setBold(True)
    p.setFont(f)
    fm = p.fontMetrics()
    text_w = fm.horizontalAdvance(label) + 10
    text_h = 14
    pad = 4
    x = out.width() - text_w - pad
    y = pad
    # Tiger Orange fill, white text — reuses the brand accent.
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#D85A30"))
    p.drawRoundedRect(x, y, text_w, text_h, 3, 3)
    p.setPen(QPen(QColor("#ffffff")))
    p.drawText(
        QRect(x, y, text_w, text_h),
        Qt.AlignmentFlag.AlignCenter, label,
    )
    p.end()
    return out


def _proxy_state_for_video(path: Path) -> str:
    if path.suffix.lower() not in VIDEO_EXTS or path.stem.endswith("_proxy"):
        return ""
    proxy = path.parent / "proxies" / f"{path.stem}_proxy.mp4"
    try:
        if not proxy.is_file():
            return ""
        if proxy.stat().st_mtime_ns < path.stat().st_mtime_ns:
            return "stale"
        return "ready"
    except Exception:
        return ""


def _auto_polish_report_for_video(path: Path, duration_ms: int = 0) -> dict:
    if path.suffix.lower() not in VIDEO_EXTS:
        return {}
    try:
        from app.screenstudio_polish import screenstudio_sidecar_report
        return screenstudio_sidecar_report(
            path,
            duration_ms=max(0, int(duration_ms or 0)),
            include_parity=False,
        )
    except Exception:
        return {}


def _draw_proxy_badge(pm: QPixmap, state: str) -> QPixmap:
    if state not in {"ready", "stale"}:
        return pm
    label = "P" if state == "ready" else "STALE"
    out = QPixmap(pm)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    f = QFont(p.font())
    f.setPointSize(7)
    f.setBold(True)
    p.setFont(f)
    fm = p.fontMetrics()
    text_w = max(16, fm.horizontalAdvance(label) + 8)
    text_h = 14
    pad = 4
    x = pad
    y = pad
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#d85a30" if state == "ready" else "#8a6a26"))
    p.drawRoundedRect(x, y, text_w, text_h, 3, 3)
    p.setPen(QPen(QColor("#ffffff")))
    p.drawText(QRect(x, y, text_w, text_h), Qt.AlignmentFlag.AlignCenter, label)
    p.end()
    return out


def _draw_auto_polish_badge(pm: QPixmap, report: dict | None) -> QPixmap:
    if not isinstance(report, dict) or int(report.get("event_count", 0) or 0) <= 0:
        return pm
    ready = int(report.get("readiness", 0) or 0)
    label = "AP" if ready >= 82 else "AP?"
    out = QPixmap(pm)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    f = QFont(p.font())
    f.setPointSize(7)
    f.setBold(True)
    p.setFont(f)
    fm = p.fontMetrics()
    text_w = max(20, fm.horizontalAdvance(label) + 8)
    text_h = 14
    pad = 4
    x = pad
    y = out.height() - text_h - pad
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#32C7E8" if ready >= 82 else "#9A7DFF"))
    p.drawRoundedRect(x, y, text_w, text_h, 3, 3)
    p.setPen(QPen(QColor("#ffffff")))
    p.drawText(QRect(x, y, text_w, text_h), Qt.AlignmentFlag.AlignCenter, label)
    p.end()
    return out


def _draw_performance_source_badge(pm: QPixmap, enabled: bool) -> QPixmap:
    if not enabled:
        return pm
    label = "PERF"
    out = QPixmap(pm)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    f = QFont(p.font())
    f.setPointSize(7)
    f.setBold(True)
    p.setFont(f)
    fm = p.fontMetrics()
    text_w = max(28, fm.horizontalAdvance(label) + 8)
    text_h = 14
    pad = 4
    x = pad
    y = pad
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#7A63FF"))
    p.drawRoundedRect(x, y, text_w, text_h, 4, 4)
    p.setPen(QPen(QColor("#ffffff")))
    p.drawText(QRect(x, y, text_w, text_h), Qt.AlignmentFlag.AlignCenter, label)
    p.end()
    return out


def _draw_actor_qa_badge(pm: QPixmap, label: str, color: str) -> QPixmap:
    if not label:
        return pm
    out = QPixmap(pm)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    f = QFont(p.font())
    f.setPointSize(7)
    f.setBold(True)
    p.setFont(f)
    fm = p.fontMetrics()
    text_w = max(16, fm.horizontalAdvance(label) + 8)
    text_h = 14
    pad = 4
    x = pad
    y = pad
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(x, y, text_w, text_h, 3, 3)
    p.setPen(QPen(QColor("#ffffff")))
    p.drawText(QRect(x, y, text_w, text_h), Qt.AlignmentFlag.AlignCenter, label)
    p.end()
    return out


def _decorate_media_thumb(
    pm: QPixmap,
    kind: str,
    path: Path,
    hdr_info=None,
    auto_polish_report=None,
    performance_source: bool = False,
) -> QPixmap:
    thumb = _draw_kind_badge(pm, kind, _badge_label_for_path(kind, path))
    thumb = _draw_performance_source_badge(thumb, performance_source)
    if hdr_info is not None and getattr(hdr_info, "is_hdr", False):
        thumb = _draw_hdr_badge(thumb, getattr(hdr_info, "standard_label", "HDR"))
    if kind == "V":
        thumb = _draw_proxy_badge(thumb, _proxy_state_for_video(path))
        thumb = _draw_auto_polish_badge(thumb, auto_polish_report)
    if kind == "S":
        try:
            from app.actor_qa_status import actor_status_badge, actor_status_for_path, load_actor_qa_status

            row = actor_status_for_path(load_actor_qa_status(), path)
            label, color = actor_status_badge(row)
            thumb = _draw_actor_qa_badge(thumb, label, color)
        except Exception:
            pass
    return thumb


def _placeholder_pixmap(size: int = THUMB_SIZE) -> QPixmap:
    """Solid neutral-grey placeholder for files we couldn't decode."""
    pm = QPixmap(size, size)
    pm.fill(QColor("#222"))
    p = QPainter(pm)
    p.setPen(QColor("#666"))
    p.drawRect(0, 0, size - 1, size - 1)
    p.end()
    return pm

