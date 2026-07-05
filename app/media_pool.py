"""DaVinci-style media pool.

Drop video files (or GIFs) from the OS into this panel to register
them as importable clips. Drag a clip from the pool onto a track row
to add it to the timeline — the drag carries ``text/uri-list`` so
the existing track drop handler picks it up the same way it would an
OS file drop.

Phase A1 (this file): flat list view with filename + duration; no
thumbnails yet. Phase A2 will add a grid mode with first-frame
thumbnails extracted via cv2.
"""
from __future__ import annotations

import os
from collections import OrderedDict
from pathlib import Path

import numpy as np
from PySide6.QtCore import QEasingCurve, QMimeData, QPoint, QSize, Qt, QThread, QTimer, QUrl, QVariantAnimation, Signal
from PySide6.QtCore import QRect
from PySide6.QtGui import (
    QColor,
    QDrag,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.mmd.project_tracks import MMD_MIME_TYPE
from app.style import FONT_FAMILY, editor_scrollbar_qss
from app.ux_feedback import apply_state_to_label, media_pool_empty_state
from app.vtuber.performance_source import PERFORMANCE_SOURCE_MIME_TYPE


# Pool item visuals — square thumbnails in an icon-mode grid. The
# letterbox border keeps frames with a non-square source from being
# squished. Grid cell hugs the icon tightly so the click target is
# (almost) the icon itself — wide cell padding tends to land mouse
# clicks in empty space, which IconMode interprets as rubber-band
# selection rather than a drag-out.
THUMB_SIZE = 64
FEATURED_THUMB_W = 164
FEATURED_THUMB_H = 92
LIST_THUMB_W = 48
LIST_THUMB_H = 27
LIST_ROW_H = 40
GRID_W = 84
GRID_H = 106
ROLE_PERFORMANCE_SOURCE = Qt.ItemDataRole.UserRole + 9
ROLE_MMD_BADGE = Qt.ItemDataRole.UserRole + 10
VRM_AVATAR_MIME_TYPE = "application/x-tigerstudio-vrm-avatar"
_CACHE_LIMIT = 96
_DURATION_CACHE: "OrderedDict[tuple[str, int, int], int | None]" = OrderedDict()
_VIDEO_THUMB_CACHE: "OrderedDict[tuple[str, int, int, int], QPixmap]" = OrderedDict()


def _file_cache_key(path: Path) -> tuple[str, int, int]:
    try:
        st = path.stat()
        return str(path.resolve()), int(st.st_mtime_ns), int(st.st_size)
    except Exception:
        return str(path), 0, 0


def _cache_get(cache: OrderedDict, key):
    if key not in cache:
        return None
    value = cache.pop(key)
    cache[key] = value
    return value


def _cache_put(cache: OrderedDict, key, value) -> None:
    cache[key] = value
    while len(cache) > _CACHE_LIMIT:
        cache.popitem(last=False)


# Extensions we treat as importable media. Mirrors the editor's track
# drop filter so pool ↔ track behaviour is consistent. The pool now
# accepts audio too — DaVinci treats every media kind through the
# same pool.
VIDEO_EXTS = frozenset({
    ".mp4", ".mov", ".mkv", ".avi", ".webm",
    ".m4v", ".mpg", ".mpeg", ".wmv", ".gif",
})
AUDIO_EXTS = frozenset({
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp2", ".wma",
})
SPINE_EXTS = frozenset({
    ".skel", ".json", ".atlas",
})
VRM_EXTS = frozenset({
    ".vrm",
})
try:
    from app.ar_pbr.schema import SUPPORTED_ASSET_EXTS as _AR_PBR_SUPPORTED_ASSET_EXTS
except Exception:
    _AR_PBR_SUPPORTED_ASSET_EXTS = frozenset({
        ".fbx", ".glb", ".gltf", ".obj", ".usd", ".usdz", ".vrm",
    })
AR_PBR_EXTS = frozenset(str(ext).casefold() for ext in _AR_PBR_SUPPORTED_ASSET_EXTS) - VRM_EXTS
MMD_MODEL_EXTS = frozenset({
    ".pmx", ".pmd",
})
MMD_MOTION_EXTS = frozenset({
    ".vmd",
})
MMD_EXTS = MMD_MODEL_EXTS
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS | SPINE_EXTS | AR_PBR_EXTS | VRM_EXTS | MMD_EXTS
THREE_D_IMPORT_FILTER = (
    "3D / MMD Assets (*.fbx *.glb *.gltf *.obj *.usd *.usdz *.vrm *.pmx *.pmd *.pbx.json);;"
    "AR/PBR 3D Assets (*.fbx *.glb *.gltf *.obj *.usd *.usdz);;"
    "MMD Models (*.pmx *.pmd *.pbx.json);;"
    "VRM Avatars (*.vrm);;"
    "All Files (*)"
)


def _is_mmd_package_path(path: Path) -> bool:
    return path.name.casefold().endswith(".pbx.json")


def _is_3d_import_path(path: Path) -> bool:
    suffix = path.suffix.casefold()
    return (
        suffix in AR_PBR_EXTS
        or suffix in VRM_EXTS
        or suffix in MMD_MODEL_EXTS
        or _is_mmd_package_path(path)
    )


def _mmd_badge_label_for_path(path: Path) -> str:
    return "MMD"


def _mmd_kind_name_for_path(path: Path) -> str:
    return "MMD Motion" if path.suffix.casefold() == ".vmd" else "MMD Model"


def _badge_label_for_path(kind: str, path: Path | None = None) -> str:
    if kind == "M" and path is not None:
        return _mmd_badge_label_for_path(path)
    return {
        "R": "VRM",
        "M": "MMD",
    }.get(kind, kind)


def _kind_for_path(p: Path) -> str:
    suf = p.suffix.lower()
    if suf in VIDEO_EXTS:
        return "V"
    if suf in AUDIO_EXTS:
        return "A"
    if _is_mmd_package_path(p):
        return "M"
    if suf in SPINE_EXTS:
        return "S"
    if suf in VRM_EXTS:
        return "R"
    if suf in MMD_EXTS:
        return "M"
    if suf in AR_PBR_EXTS:
        return "3"
    return "?"


def _format_duration(ms: int | None) -> str:
    if ms is None or ms <= 0:
        return ""
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _clean_item_stem(path: Path) -> str:
    name = (path.stem or path.name).replace("\uFF5C", "|").replace("\u3000", " ")
    return " ".join(name.split()) or path.name


def _middle_ellipsis(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 5:
        return f"{text[:max(1, max_chars - 3)]}..."
    tail = max(3, min(6, max_chars // 3))
    head = max(4, max_chars - tail - 3)
    return f"{text[:head]}...{text[-tail:]}"


def _compact_item_name(path: Path, max_chars: int = 11, *, include_suffix: bool = True) -> str:
    """Short display label; full path remains in tooltip."""
    name = _middle_ellipsis(_clean_item_stem(path), max_chars)
    suffix = path.suffix
    if include_suffix and suffix and len(name) + len(suffix) <= max_chars + 4:
        return f"{name}{suffix}"
    return name


def _media_pool_item_text(path: Path, duration: str, view_mode: str) -> str:
    if view_mode == "list":
        display_name = _compact_item_name(path, max_chars=24, include_suffix=False)
    else:
        display_name = _compact_item_name(path, max_chars=11)
    return f"{display_name}\n{duration}" if duration else display_name


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


class _MediaPoolList(QListWidget):
    """``QListWidget`` subclass that exposes pool items as
    ``text/uri-list`` drags so any drop target which accepts OS file
    drops (the editor's track rows) receives them too.

    Drag initiation is wired directly from ``mousePressEvent`` /
    ``mouseMoveEvent`` because Qt's IconMode default startDrag path
    on PySide6 6.11 tends to swallow the gesture into rubber-band
    selection — items end up being selected instead of dragged.
    Owning the threshold + ``QDrag.exec()`` ourselves makes the
    behaviour deterministic regardless of view mode.
    """

    # Right-click landed on empty list space (no item under cursor).
    # The parent ``MediaPool`` listens and pops a "Load video..."
    # menu so the user has a discoverable alternative to drag-drop.
    empty_context_menu = Signal(QPoint)
    item_context_menu = Signal(object, QPoint)
    item_scrubbed = Signal(object, float)
    auto_polish_item_requested = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._press_pos: QPoint | None = None
        self._press_item: QListWidgetItem | None = None

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:  # type: ignore[override]
        md = QMimeData()
        urls: list[QUrl] = []
        performance_source = False
        vrm_avatar_paths: list[str] = []
        mmd_paths: list[str] = []
        for item in items:
            path = item.data(Qt.ItemDataRole.UserRole)
            kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "")
            if isinstance(path, str) and path:
                if kind == "R":
                    vrm_avatar_paths.append(path)
                elif kind == "M":
                    mmd_paths.append(path)
                    urls.append(QUrl.fromLocalFile(path))
                else:
                    urls.append(QUrl.fromLocalFile(path))
            if bool(item.data(ROLE_PERFORMANCE_SOURCE)):
                performance_source = True
        if urls:
            md.setUrls(urls)
        if vrm_avatar_paths:
            md.setData(VRM_AVATAR_MIME_TYPE, "\n".join(vrm_avatar_paths).encode("utf-8"))
        if mmd_paths:
            md.setData(MMD_MIME_TYPE, "\n".join(mmd_paths).encode("utf-8"))
        if performance_source:
            md.setData(PERFORMANCE_SOURCE_MIME_TYPE, b"1")
        return md

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self._press_pos = pos
            self._press_item = self.itemAt(pos)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        # Manual drag-threshold check. The instant the cursor moves
        # past Qt's drag-distance from the press point AND the press
        # was on a real item, we hand off to ``_begin_drag``. After
        # that we eat the move event so the view doesn't also start
        # a rubber-band sweep from the same gesture.
        if (
            self._press_pos is not None
            and self._press_item is not None
            and (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            from PySide6.QtWidgets import QApplication
            delta = (event.position().toPoint() - self._press_pos)
            if delta.manhattanLength() >= QApplication.startDragDistance():
                item = self._press_item
                self._press_pos = None
                self._press_item = None
                self._begin_drag(item)
                event.accept()
                return
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            pos = event.position().toPoint()
            item = self.itemAt(pos)
            if item is not None:
                rect = self.visualItemRect(item)
                if rect.width() > 4:
                    ratio = (pos.x() - rect.left()) / max(1, rect.width())
                    self.item_scrubbed.emit(item, max(0.0, min(1.0, float(ratio))))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._press_item is not None
            and self._press_pos is not None
        ):
            pos = event.position().toPoint()
            item = self._press_item
            from PySide6.QtWidgets import QApplication
            if (
                item is self.itemAt(pos)
                and (pos - self._press_pos).manhattanLength() < QApplication.startDragDistance()
                and self._auto_polish_badge_hit(item, pos)
            ):
                self._press_pos = None
                self._press_item = None
                self.auto_polish_item_requested.emit(item)
                event.accept()
                return
        self._press_pos = None
        self._press_item = None
        super().mouseReleaseEvent(event)

    def _auto_polish_badge_hit(self, item: QListWidgetItem | None, pos: QPoint) -> bool:
        if item is None:
            return False
        report = item.data(Qt.ItemDataRole.UserRole + 6)
        if not isinstance(report, dict) or int(report.get("event_count", 0) or 0) <= 0:
            return False
        rect = self.visualItemRect(item)
        if not rect.isValid():
            return False
        if self.viewMode() == QListWidget.ViewMode.IconMode:
            icon_x = rect.left() + max(0, (rect.width() - THUMB_SIZE) // 2)
            icon_y = rect.top() + 2
        else:
            icon_x = rect.left() + 5
            icon_y = rect.top() + max(0, (rect.height() - THUMB_SIZE) // 2)
        badge = QRect(icon_x + 3, icon_y + THUMB_SIZE - 19, 34, 18)
        return badge.adjusted(-3, -3, 5, 4).contains(pos)

    def _begin_drag(self, item: QListWidgetItem) -> bool:
        path = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(path, str) or not path:
            return False
        md = self.mimeData([item])
        if not md.formats():
            return False
        drag = QDrag(self)
        drag.setMimeData(md)
        pm = item.icon().pixmap(THUMB_SIZE, THUMB_SIZE)
        if pm.isNull() or pm.width() == 0 or pm.height() == 0:
            pm = _placeholder_pixmap(THUMB_SIZE)
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(pm.width() // 2, pm.height() // 2))
        drag.exec(Qt.DropAction.CopyAction)
        return True

    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        if item is None:
            self.empty_context_menu.emit(event.globalPos())
            event.accept()
            return
        self.setCurrentItem(item)
        self.item_context_menu.emit(item, event.globalPos())
        event.accept()


class _YouTubeImportThread(QThread):
    progress = Signal(int, str)
    done = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        url: str,
        out_root: Path | str,
        quality: str | int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._url = str(url or "")
        self._out_root = str(out_root)
        self._quality = quality

    def run(self) -> None:
        try:
            from app.youtube_import import download_youtube_to_mp4

            path = download_youtube_to_mp4(
                self._url,
                self._out_root,
                quality=self._quality,
                progress_cb=lambda pct, label: self.progress.emit(int(pct), str(label)),
            )
            self.done.emit(str(path))
        except Exception as exc:
            self.failed.emit(str(exc))


class MediaPool(QWidget):
    """Imported-media list. Drop OS files in to register, drag items
    out to drop them on a track."""

    item_added = Signal(str)        # absolute file path
    item_removed = Signal(str)      # absolute file path
    popout_requested = Signal()
    auto_polish_requested = Signal(str)
    asset_preview_requested = Signal(str)
    avatar_target_requested = Signal(str)
    vtuber_studio_requested = Signal(str)
    mmd_asset_requested = Signal(str)
    selection_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MediaPool")
        self.setStyleSheet(
            f"QWidget#MediaPool {{ background:transparent; font-family:{FONT_FAMILY}; }}"
            "QWidget#MediaPool[dropState=\"active\"] { background:rgba(255,255,255,5); }"
            "QWidget#MediaPool[dropState=\"blocked\"] { background:rgba(255,120,90,5); }"
            "QLabel#MediaPoolTitle {"
            "color:#ECEEF4; font-size:12px; font-weight:560;"
            "}"
            "QLineEdit#MediaPoolSearch {"
            "background:#121416; color:#D8DCE6; border:1px solid rgba(220,225,238,18);"
            "border-radius:7px; padding:4px 9px; min-height:21px; font-size:10px;"
            "}"
            "QLineEdit#MediaPoolSearch:focus { border-color:rgba(230,235,245,82); background:#171A1E; }"
            "QPushButton#MediaPoolIconButton {"
            "background:rgba(255,255,255,4); color:#D8DCE6; border:1px solid rgba(220,225,238,20);"
            "border-radius:7px; padding:0px; min-width:23px; min-height:23px; font-size:0px;"
            "}"
            "QPushButton#MediaPoolIconButton:hover { background:rgba(255,255,255,12); border-color:rgba(230,235,245,78); }"
            "QPushButton#MediaPoolIconButton:pressed { background:rgba(255,255,255,17); border-color:rgba(238,242,250,116); }"
            "QPushButton#MediaPoolFilterButton, QPushButton#MediaPoolViewButton {"
            "background:rgba(255,255,255,4); color:#D8DCE6; border:1px solid rgba(220,225,238,20);"
            "border-radius:7px; padding:0px; min-width:24px; min-height:23px; font-size:0px;"
            "}"
            "QPushButton#MediaPoolFilterButton:hover, QPushButton#MediaPoolViewButton:hover {"
            "background:rgba(255,255,255,12); color:#FFFFFF; border-color:rgba(230,235,245,78);"
            "}"
            "QPushButton#MediaPoolFilterButton:checked, QPushButton#MediaPoolViewButton:checked {"
            "background:#2A2F36;"
            "color:#FFFFFF; border-color:rgba(238,242,250,92);"
            "}"
            "QComboBox {"
            "background:#121416; color:#D8DCE6; border:1px solid rgba(220,225,238,18);"
            "border-radius:7px; padding:4px 20px 4px 8px; font-size:10px; min-height:20px;"
            "}"
            "QComboBox:hover { background:#171A1E; border-color:rgba(230,235,245,78); color:#FFFFFF; }"
            "QComboBox::drop-down { border:none; width:20px; }"
            "QLabel#MediaPoolPreview {"
            "background:#0E1012; border:1px solid rgba(220,225,238,18); border-radius:7px;"
            "padding:4px;"
            "}"
            "QLabel#MediaPoolMeta {"
            "color:#C7CBD5; background:#101214; border:1px solid rgba(220,225,238,18);"
            "border-radius:7px; padding:6px; font-size:10px;"
            "}"
            "QLabel#MediaPoolStatus {"
            "color:#9CA2AD; font-size:10px; padding:2px 3px;"
            "background:rgba(255,255,255,4); border:1px solid rgba(220,225,238,12);"
            "border-radius:6px;"
            "}"
            "QWidget#MediaPoolFeatured {"
            "background:#101010; border:1px solid rgba(220,225,238,16);"
            "border-radius:8px;"
            "}"
            "QLabel#MediaPoolFeaturedThumb {"
            "background:#090909; border:1px solid rgba(220,225,238,22);"
            "border-radius:6px; padding:0px;"
            "}"
            "QLabel#MediaPoolFeaturedTitle {"
            "color:#F0F3F7; font-size:10px; font-weight:560; background:transparent;"
            "border:none; padding:0px;"
            "}"
            "QLabel#MediaPoolFeaturedMeta {"
            "color:#9AA4B2; font-size:9px; background:transparent;"
            "border:none; padding:0px;"
            "}"
            "QLabel#MediaPoolEmpty {"
            "color:#AEB4C0; background:#121212; border:1px dashed #353535;"
            "border-radius:10px; padding:16px; font-size:10px;"
            "}"
            "QLabel#MediaPoolEmpty[tone=\"active\"] { border-color:#A7ADB8; background:#171717; color:#F0F2F6; }"
            "QLabel#MediaPoolEmpty[tone=\"warning\"] { color:#E0B45C; border-color:#9B7240; }"
            "QPushButton#MediaPoolImportButton {"
            "background:rgba(255,255,255,4); color:#D8DCE6;"
            "border:1px solid rgba(220,225,238,20); border-radius:6px;"
            "padding:5px 8px; min-height:23px; font-size:10px; font-weight:500;"
            "}"
            "QPushButton#MediaPoolImportButton:hover {"
            "background:rgba(255,255,255,12); border-color:rgba(220,225,238,74); color:#FFFFFF;"
            "}"
            "QListWidget {"
            "background:transparent; color:#D7DAE7; border:none;"
            "border-radius:0px; padding:1px 0px; outline:none;"
            "}"
            "QListWidget::item { border-radius:6px; padding:3px 2px; }"
            "QListWidget::item:hover { background:rgba(255,255,255,6); }"
            "QListWidget::item:selected { background:rgba(220,225,238,18); color:#FFFFFF; }"
            + editor_scrollbar_qss("QWidget#MediaPool")
        )
        self.setAcceptDrops(True)
        self.setProperty("dropState", "")
        # Set of absolute paths already registered, so a second drop of
        # the same file is a no-op (no duplicates in the pool).
        self._registered: set[str] = set()
        self._filter_kind: str = "all"
        self._bin_kind: str = "all"
        self._view_mode: str = "list"
        self._sort_mode: str = "name"
        self._youtube_import_thread: _YouTubeImportThread | None = None
        self._youtube_import_progress: QProgressDialog | None = None
        self._actor_qa_status: dict = {}
        self._featured_path: str = ""
        self._featured_press_global: QPoint | None = None
        try:
            from app.actor_qa_status import load_actor_qa_status

            self._actor_qa_status = load_actor_qa_status()
        except Exception:
            self._actor_qa_status = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 4, 5)
        root.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(4)
        self._title_label = QLabel(tr("media_pool.title"), self)
        self._title_label.setObjectName("MediaPoolTitle")
        self._title_label.setStyleSheet(
            "font-family:'Segoe UI Variable','Noto Sans KR','Segoe UI';"
            "font-size:12px; font-weight:620; color:#ECEEF4;"
        )
        header.addWidget(self._title_label)
        self._title_label.hide()

        self._url_import_btn = QPushButton("", self)
        self._url_import_btn.setObjectName("MediaPoolIconButton")
        self._url_import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._url_import_btn.setToolTip("Import YouTube URL as MP4")
        self._url_import_btn.setFixedSize(24, 24)
        self._url_import_btn.setIcon(app_icon("download", size=12))
        self._url_import_btn.setIconSize(icon_size(12))
        self._install_icon_pulse(self._url_import_btn)
        self._url_import_btn.clicked.connect(self._open_youtube_url_dialog)
        header.addWidget(self._url_import_btn)

        self._remove_btn = QPushButton("", self)
        self._remove_btn.setObjectName("MediaPoolIconButton")
        self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_btn.setToolTip(tr("media_pool.btn.remove"))
        self._remove_btn.setFixedSize(24, 24)
        self._remove_btn.setIcon(app_icon("trash", size=12))
        self._remove_btn.setIconSize(icon_size(12))
        self._install_icon_pulse(self._remove_btn)
        self._remove_btn.clicked.connect(self._on_remove_selected)
        header.addWidget(self._remove_btn)

        self._popout_btn = QPushButton("", self)
        self._popout_btn.setObjectName("MediaPoolIconButton")
        self._popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._popout_btn.setToolTip(tr("media_pool.popout.tooltip"))
        self._popout_btn.setFixedSize(24, 24)
        self._popout_btn.setText("")
        self._popout_btn.setIcon(app_icon("popout", size=12))
        self._popout_btn.setIconSize(icon_size(12))
        self._install_icon_pulse(self._popout_btn, peak=21)
        self._popout_btn.clicked.connect(self.popout_requested.emit)
        header.addWidget(self._popout_btn)
        header.addStretch(1)
        root.addLayout(header)

        self._search_edit = QLineEdit(self)
        self._search_edit.setObjectName("MediaPoolSearch")
        self._search_edit.setPlaceholderText("Search media")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._apply_filter)
        root.addWidget(self._search_edit)
        self._search_edit.hide()

        bin_row = QHBoxLayout()
        bin_row.setSpacing(4)
        self._bin_combo = QComboBox(self)
        self._bin_combo.setObjectName("MediaPoolBinCombo")
        self._bin_combo.addItem("All Media", "all")
        self._bin_combo.addItem("Video Bin", "V")
        self._bin_combo.addItem("Audio Bin", "A")
        self._bin_combo.addItem("Actor Bin", "S")
        self._bin_combo.addItem("VRM Avatars", "R")
        self._bin_combo.addItem("MMD Models", "M")
        self._bin_combo.addItem("3D Assets", "3")
        self._bin_combo.addItem("Proxy Missing", "proxy_missing")
        self._bin_combo.addItem("Proxy Stale", "proxy_stale")
        self._bin_combo.addItem("Duplicate Name", "duplicate_name")
        self._bin_combo.currentIndexChanged.connect(self._set_bin_kind_from_combo)
        bin_row.addWidget(self._bin_combo, stretch=1)
        root.addLayout(bin_row)
        self._bin_combo.hide()

        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)
        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(True)
        for kind, label in (
            ("all", "All"),
            ("V", "Video"),
            ("A", "Audio"),
            ("S", "Actor"),
            ("R", "Avatar"),
            ("M", "MMD"),
            ("3", "3D"),
        ):
            btn = QPushButton("", self)
            btn.setObjectName("MediaPoolFilterButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(label)
            btn.setIcon(app_icon({
                "all": "grid",
                "V": "video",
                "A": "audio",
                "S": "actors",
                "R": "actors",
                "M": "actors",
                "3": "layers",
            }.get(kind, "grid"), size=16))
            btn.setIconSize(icon_size(15))
            btn.setFixedSize(26, 24)
            self._install_icon_pulse(btn)
            btn.clicked.connect(lambda _checked=False, k=kind: self._set_filter_kind(k))
            if kind == "all":
                btn.setChecked(True)
            self._filter_group.addButton(btn)
            filter_row.addWidget(btn)
            btn.hide()
        filter_row.addStretch(1)
        root.addLayout(filter_row)

        view_row = QHBoxLayout()
        view_row.setSpacing(4)
        self._view_group = QButtonGroup(self)
        self._view_group.setExclusive(True)
        for mode, label in (("grid", "Grid"), ("list", "List")):
            btn = QPushButton("", self)
            btn.setObjectName("MediaPoolViewButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(label)
            btn.setIcon(app_icon(mode, size=16))
            btn.setIconSize(icon_size(15))
            btn.setFixedSize(26, 24)
            self._install_icon_pulse(btn)
            btn.clicked.connect(lambda _checked=False, m=mode: self._set_view_mode(m))
            if mode == "list":
                btn.setChecked(True)
            self._view_group.addButton(btn)
            view_row.addWidget(btn)
            btn.hide()
        view_row.addStretch(1)
        self._sort_combo = QComboBox(self)
        self._sort_combo.setObjectName("MediaPoolSortCombo")
        self._sort_combo.addItem("Name", "name")
        self._sort_combo.addItem("Type", "type")
        self._sort_combo.addItem("Duration", "duration")
        self._sort_combo.currentIndexChanged.connect(self._set_sort_mode_from_combo)
        view_row.addWidget(self._sort_combo)
        root.addLayout(view_row)
        self._sort_combo.hide()

        self._list = _MediaPoolList(self)
        self._list.empty_context_menu.connect(self._show_context_menu)
        self._list.item_context_menu.connect(self._show_item_context_menu)
        self._list.auto_polish_item_requested.connect(self._on_auto_polish_item_requested)
        self._list.setMinimumHeight(220)
        # Drag OUT only — pool items go to tracks, but tracks don't
        # send anything back, and we don't allow rearranging inside
        # the pool either. Without ``DragOnly`` the default
        # ``NoDragDrop`` mode swallows the drag-start gesture so
        # mouse-down on an item just changes selection.
        self._list.setDragEnabled(True)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self._list.setDefaultDropAction(Qt.DropAction.CopyAction)
        # SingleSelection avoids the IconMode rubber-band that
        # competes with drag-out — clicking on or near an item
        # immediately selects it, no rectangular sweep.
        self._list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection,
        )
        self._list.setSelectionRectVisible(False)
        # Grid / icon mode — square thumbnails over a wrapped
        # filename. ``Static`` movement disables drag-rearranging
        # within the pool itself; the only drag we want is the one
        # OUT to a track.
        self._list.setViewMode(QListWidget.ViewMode.ListMode)
        self._list.setIconSize(QSize(LIST_THUMB_W, LIST_THUMB_H))
        self._list.setGridSize(QSize())
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setUniformItemSizes(False)
        self._list.setSpacing(4)
        self._list.setWordWrap(False)
        self._list.setMouseTracking(True)
        self._list.viewport().setMouseTracking(True)
        self._list.itemEntered.connect(self._on_item_hovered)
        self._list.item_scrubbed.connect(self._on_item_scrubbed)
        self._list.itemSelectionChanged.connect(self._refresh_metadata_panel)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self._list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        # Empty-state hint visible until the first file lands.
        self._empty_label = QLabel(tr("media_pool.empty_hint"), self)
        self._empty_label.setObjectName("MediaPoolEmpty")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        root.addWidget(self._empty_label)

        self._featured_host = QWidget(self)
        self._featured_host.setObjectName("MediaPoolFeatured")
        featured_row = QVBoxLayout(self._featured_host)
        featured_row.setContentsMargins(7, 6, 7, 7)
        featured_row.setSpacing(5)
        self._featured_thumb = QLabel(self._featured_host)
        self._featured_thumb.setObjectName("MediaPoolFeaturedThumb")
        self._featured_thumb.setFixedSize(FEATURED_THUMB_W, FEATURED_THUMB_H)
        self._featured_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        featured_row.addWidget(self._featured_thumb, 0, Qt.AlignmentFlag.AlignLeft)
        featured_text = QVBoxLayout()
        featured_text.setContentsMargins(0, 0, 0, 0)
        featured_text.setSpacing(2)
        self._featured_title = QLabel("", self._featured_host)
        self._featured_title.setObjectName("MediaPoolFeaturedTitle")
        self._featured_title.setWordWrap(False)
        self._featured_title.setMinimumWidth(FEATURED_THUMB_W)
        self._featured_title.setMaximumWidth(FEATURED_THUMB_W)
        self._featured_meta = QLabel("", self._featured_host)
        self._featured_meta.setObjectName("MediaPoolFeaturedMeta")
        self._featured_meta.setMinimumWidth(FEATURED_THUMB_W)
        self._featured_meta.setMaximumWidth(FEATURED_THUMB_W)
        featured_text.addWidget(self._featured_title)
        featured_text.addWidget(self._featured_meta)
        featured_row.addLayout(featured_text)
        for drag_widget in (
            self._featured_host,
            self._featured_thumb,
            self._featured_title,
            self._featured_meta,
        ):
            drag_widget.setCursor(Qt.CursorShape.OpenHandCursor)
            drag_widget.installEventFilter(self)
        root.addWidget(self._featured_host)
        self._featured_host.hide()

        root.addWidget(self._list, stretch=1)
        self._list.hide()

        self._import_btn = QPushButton("+ Import Media", self)
        self._import_btn.setObjectName("MediaPoolImportButton")
        self._import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._import_btn.clicked.connect(self._open_file_dialog)
        root.addWidget(self._import_btn)

        self._preview_label = QLabel("No preview", self)
        self._preview_label.setObjectName("MediaPoolPreview")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setFixedHeight(58)
        self._preview_label.hide()
        root.addWidget(self._preview_label)

        self._metadata_label = QLabel("No media selected", self)
        self._metadata_label.setObjectName("MediaPoolMeta")
        self._metadata_label.setWordWrap(True)
        self._metadata_label.hide()
        root.addWidget(self._metadata_label)

        self._status_label = QLabel("Ready", self)
        self._status_label.setObjectName("MediaPoolStatus")
        root.addWidget(self._status_label)
        self._status_label.hide()
        self._refresh_empty_state()

    def _install_icon_pulse(self, button, *, base: int = 16, peak: int = 21) -> None:
        if button is None or bool(button.property("_iconPulseInstalled")):
            return
        button.setProperty("_iconPulseInstalled", True)
        if not hasattr(self, "_icon_pulse_animations"):
            self._icon_pulse_animations = []

        def _pulse() -> None:
            anim = QVariantAnimation(button)
            anim.setDuration(165)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(base)
            anim.setKeyValueAt(0.45, peak)
            anim.setEndValue(base)
            anim.valueChanged.connect(lambda value: button.setIconSize(icon_size(int(value))))
            anim.finished.connect(lambda: self._icon_pulse_animations.remove(anim) if anim in self._icon_pulse_animations else None)
            self._icon_pulse_animations.append(anim)
            anim.start()

        try:
            button.pressed.connect(_pulse)
        except Exception:
            pass

    # ---- public API ----

    def items(self) -> list[str]:
        """All registered file paths in pool order."""
        return [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
        ]

    def is_performance_source_path(self, path: Path | str) -> bool:
        """Return whether a pool item is marked as avatar-tracking input."""
        item = self._find_item_for_path(path)
        return bool(item is not None and item.data(ROLE_PERFORMANCE_SOURCE))

    def set_performance_source_path(self, path: Path | str, enabled: bool) -> bool:
        """Set the Performance Source flag for a registered video item."""
        item = self._find_item_for_path(path)
        if item is None:
            return False
        before = bool(item.data(ROLE_PERFORMANCE_SOURCE))
        self._set_item_performance_source(item, bool(enabled))
        after = bool(item.data(ROLE_PERFORMANCE_SOURCE))
        return before != after

    def performance_source_paths(self) -> list[str]:
        """All registered media paths marked as input-only performance sources."""
        rows: list[str] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None or not bool(item.data(ROLE_PERFORMANCE_SOURCE)):
                continue
            path = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if path:
                rows.append(path)
        return rows

    def media_pool_metadata(self) -> list[dict]:
        """Serializable media-pool rows, separate from the legacy path list."""
        rows: list[dict] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None:
                continue
            path = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if not path:
                continue
            rows.append(
                {
                    "path": path,
                    "kind": str(item.data(Qt.ItemDataRole.UserRole + 2) or ""),
                    "performance_source": bool(item.data(ROLE_PERFORMANCE_SOURCE)),
                    "avatar_target": str(item.data(Qt.ItemDataRole.UserRole + 2) or "") == "R",
                    "vrm_avatar": str(item.data(Qt.ItemDataRole.UserRole + 2) or "") == "R",
                    "mmd_asset": str(item.data(Qt.ItemDataRole.UserRole + 2) or "") == "M",
                    "mmd_badge": str(item.data(ROLE_MMD_BADGE) or ""),
                }
            )
        return rows

    def select_path(self, path: Path | str) -> bool:
        """Select a pool item and promote it to the featured slot."""
        return self._select_path(path)

    def _find_item_for_path(self, path: Path | str) -> QListWidgetItem | None:
        try:
            key = str(Path(path).expanduser().resolve())
        except Exception:
            key = str(path or "")
        if not key:
            return None
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is not None and str(item.data(Qt.ItemDataRole.UserRole) or "") == key:
                return item
        return None


    def _set_featured_item(self, item: QListWidgetItem | None) -> None:
        if item is None:
            self._featured_path = ""
            self._featured_host.hide()
            self._apply_filter()
            return
        path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        if not str(path):
            self._featured_path = ""
            self._featured_host.hide()
            self._apply_filter()
            return
        self._featured_path = str(path)
        self._featured_thumb.setPixmap(self._featured_pixmap_for_item(item))
        self._featured_title.setText(_compact_item_name(path, max_chars=27, include_suffix=False))
        self._featured_title.setToolTip(str(path))
        duration = _format_duration(int(item.data(Qt.ItemDataRole.UserRole + 3) or 0))
        kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "?")
        kind_label = {"V": "Video", "A": "Audio", "S": "Actor", "R": "VRM Avatar", "M": "MMD", "3": "3D"}.get(kind, "Media")
        if bool(item.data(ROLE_PERFORMANCE_SOURCE)):
            kind_label = "Performance Source"
        self._featured_meta.setText(duration or kind_label)
        self._featured_host.show()
        self._apply_filter()

    def _event_global_pos(self, event) -> QPoint:
        global_pos = getattr(event, "globalPosition", None)
        if callable(global_pos):
            try:
                return global_pos().toPoint()
            except Exception:
                pass
        global_pos = getattr(event, "globalPos", None)
        if callable(global_pos):
            try:
                return global_pos()
            except Exception:
                pass
        pos = getattr(event, "pos", None)
        if callable(pos):
            try:
                return pos()
            except Exception:
                pass
        return QPoint()

    def _begin_featured_drag(self) -> bool:
        path = str(getattr(self, "_featured_path", "") or "")
        if not path:
            return False
        item = self._find_item_for_path(path)
        if item is None:
            return False
        return bool(self._list._begin_drag(item))

    def _activate_featured_item(self) -> bool:
        path = str(getattr(self, "_featured_path", "") or "")
        if not path:
            return False
        item = self._find_item_for_path(path)
        if item is None:
            return False
        self._list.setCurrentItem(item)
        self._on_item_double_clicked(item)
        return True


    def clear(self) -> None:
        """Wipe every item — used by project-load before re-populating
        from the .tgp snapshot."""
        self._list.clear()
        self._registered.clear()
        self._featured_path = ""
        self._featured_host.hide()
        self._preview_label.hide()
        self._metadata_label.hide()
        self._status_label.setText("Pool cleared")
        self._refresh_empty_state()



    def _set_item_performance_source(self, item: QListWidgetItem, enabled: bool) -> None:
        if item is None:
            return
        kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "?")
        if kind != "V":
            self._status_label.setText("Only video clips can be performance sources")
            return
        item.setData(ROLE_PERFORMANCE_SOURCE, bool(enabled))
        self._refresh_item_thumbnail(item)
        path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        base_tip = str(path)
        if bool(enabled):
            item.setToolTip(
                f"{base_tip}\nPERF: Performance Source\n"
                "Used for avatar tracking only. This clip is not used as Program Output background."
            )
            self._status_label.setText(f"Marked as Performance Source: {path.name}")
        else:
            item.setToolTip(base_tip)
            self._status_label.setText(f"Cleared Performance Source: {path.name}")
        if str(getattr(self, "_featured_path", "") or "") == str(path):
            self._set_featured_item(item)


    def remove_path(self, path: str) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self._list.takeItem(i)
                self._registered.discard(path)
                if str(getattr(self, "_featured_path", "") or "") == str(path):
                    self._featured_path = ""
                    self._featured_host.hide()
                    replacement = self._list.item(0) if self._list.count() else None
                    if replacement is not None:
                        self._list.setCurrentItem(replacement)
                        self._set_featured_item(replacement)
                self._refresh_empty_state()
                self._status_label.setText("Media removed")
                self.item_removed.emit(path)
                return


    def ingest_manifest_payload(self, *, selected_only: bool = False) -> dict:
        """Return a checksum ingest manifest for all or selected pool media."""
        if selected_only:
            items = self._list.selectedItems()
        else:
            items = [self._list.item(i) for i in range(self._list.count())]
        paths = [
            str(item.data(Qt.ItemDataRole.UserRole) or "")
            for item in items
            if item is not None and str(item.data(Qt.ItemDataRole.UserRole) or "")
        ]
        from app.professional_workflow_payloads import build_ingest_clone_payload

        return build_ingest_clone_payload(paths)


    def media_health_summary_text(self) -> str:
        """Compact health text for status bars and QA dashboard cards."""
        try:
            report = self.media_health_payload()
        except Exception:
            return "Media health unavailable"
        status_counts = report.get("status_counts", {}) if isinstance(report, dict) else {}
        proxy_counts = report.get("proxy_counts", {}) if isinstance(report, dict) else {}
        missing = int(status_counts.get("missing", 0) or 0) + int(status_counts.get("relink_conflict", 0) or 0)
        stale = int(proxy_counts.get("stale", 0) or 0)
        proxy_missing = int(proxy_counts.get("missing", 0) or 0)
        total = int(report.get("total_paths", 0) or 0)
        return (
            f"Media health: {total} item(s) | missing {missing} | "
            f"proxy missing {proxy_missing} | stale {stale}"
        )

    def _on_auto_polish_item_requested(self, item: QListWidgetItem) -> None:
        path = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not path:
            return
        report = item.data(Qt.ItemDataRole.UserRole + 6)
        if isinstance(report, dict):
            self._status_label.setText(
                f"Auto Polish: {int(report.get('readiness', 0) or 0)}% ready"
            )
        self._list.setCurrentItem(item)
        self._refresh_metadata_panel()
        self.auto_polish_requested.emit(path)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        if item is None:
            return
        kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "?")
        path = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not path:
            return
        if kind == "R":
            self._status_label.setText(f"Using VRM avatar target: {Path(path).name}")
            self.avatar_target_requested.emit(path)
            self.vtuber_studio_requested.emit(path)
            return
        if kind == "M":
            self._status_label.setText(f"Placing MMD asset: {Path(path).name}")
            self.mmd_asset_requested.emit(path)
            return
        if kind != "3":
            return
        self._status_label.setText(f"Opening 3D preview: {Path(path).name}")
        self.asset_preview_requested.emit(path)


    def retranslate(self) -> None:
        self._title_label.setText(tr("media_pool.title"))
        self._url_import_btn.setToolTip("Import YouTube URL as MP4")
        self._remove_btn.setText("")
        self._remove_btn.setToolTip(tr("media_pool.btn.remove"))
        self._popout_btn.setToolTip(tr("media_pool.popout.tooltip"))
        self._search_edit.setPlaceholderText("Search media")
        self._refresh_empty_state()

    # ---- DnD: accept OS file drops ----

    def _set_drop_state(self, state: str) -> None:
        state = state if state in {"active", "blocked"} else ""
        if self.property("dropState") == state:
            return
        self.setProperty("dropState", state)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _set_status_message(self, text: str, *, transient_ms: int = 0) -> None:
        self._status_label.setText(text)
        self._status_label.show()
        if transient_ms > 0:
            QTimer.singleShot(transient_ms, self._status_label.hide)

    def _accepted_drop_count(self, event) -> int:
        md = event.mimeData()
        if not md.hasUrls():
            return 0
        accepted = 0
        for url in md.urls():
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in MEDIA_EXTS:
                accepted += 1
        return accepted

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        accepted = self._accepted_drop_count(event)
        if accepted:
            self._set_drop_state("active")
            self._set_status_message(f"Drop to import {accepted} media file(s)")
            event.acceptProposedAction()
            return
        self._set_drop_state("blocked")
        self._set_status_message("Unsupported drop: use video, audio, or actor files")
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        # Same predicate as enter — keeps the drop cursor consistent
        # while hovering over the list.
        self.dragEnterEvent(event)

    def dragLeaveEvent(self, event) -> None:
        self._set_drop_state("")
        self._status_label.hide()
        event.accept()


    # ---- context menu / file dialog ----

    def contextMenuEvent(self, event) -> None:
        """Right-click on the panel itself (placeholder area when the
        pool is empty, or padding around the list). Forwards to the
        same handler the list uses for its empty-area right-clicks."""
        self._show_context_menu(event.globalPos())
        event.accept()

    def _show_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        act_load = menu.addAction(tr("media_pool.menu.load_files"))
        act_youtube = menu.addAction("Import YouTube URL as MP4")
        act_import_3d = menu.addAction("Import 3D / MMD Asset...")
        chosen = menu.exec(global_pos)
        if chosen is act_load:
            self._open_file_dialog()
        elif chosen is act_youtube:
            self._open_youtube_url_dialog()
        elif chosen is act_import_3d:
            self._open_3d_import_dialog()


    def _open_file_dialog(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(MEDIA_EXTS))
        filter_str = f"{tr('media_pool.dialog.filter')} ({exts})"
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr("media_pool.dialog.title"), "", filter_str,
        )
        for p in paths:
            self.add_path(p)

    def _open_3d_import_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import 3D / MMD Asset",
            "",
            THREE_D_IMPORT_FILTER,
        )
        self.import_3d_paths(paths)


    def _on_youtube_import_progress(self, pct: int, label: str) -> None:
        if self._youtube_import_progress is not None:
            self._youtube_import_progress.setValue(max(0, min(100, int(pct))))
            self._youtube_import_progress.setLabelText(f"{label}...")
        self._status_label.setText(f"YouTube import: {label} {int(pct)}%")

    def _select_path(self, path: Path | str) -> bool:
        item = self._find_item_for_path(path)
        if item is None:
            return False
        self._list.setCurrentItem(item)
        self._set_featured_item(item)
        try:
            self._list.scrollToItem(item)
        except Exception:
            pass
        self._refresh_metadata_panel()
        return True

    def _on_youtube_import_done(self, path: str) -> None:
        if self._youtube_import_progress is not None:
            self._youtube_import_progress.setValue(100)
            self._youtube_import_progress.close()
            self._youtube_import_progress = None
        added = self.add_path(path)
        self._select_path(path)
        name = Path(path).name
        self._status_label.setText(
            f"YouTube MP4 imported: {name}" if added else f"YouTube MP4 already in pool: {name}"
        )

    def _on_youtube_import_failed(self, reason: str) -> None:
        if self._youtube_import_progress is not None:
            self._youtube_import_progress.close()
            self._youtube_import_progress = None
        self._status_label.setText("YouTube import failed")
        QMessageBox.warning(self, "Import YouTube URL", str(reason or "Import failed"))

    def _cleanup_youtube_import_thread(self) -> None:
        thread = self._youtube_import_thread
        self._youtube_import_thread = None
        if thread is not None:
            thread.deleteLater()

    # ---- internal ----

    def _on_remove_selected(self) -> None:
        for item in self._list.selectedItems():
            path = item.data(Qt.ItemDataRole.UserRole)
            row = self._list.row(item)
            self._list.takeItem(row)
            if isinstance(path, str):
                self._registered.discard(path)
                if str(getattr(self, "_featured_path", "") or "") == path:
                    self._featured_path = ""
                    self._featured_host.hide()
                self.item_removed.emit(path)
        if not self._featured_path and self._list.count():
            item = self._list.item(0)
            if item is not None:
                self._list.setCurrentItem(item)
                self._set_featured_item(item)
        self._status_label.setText("Selected media removed")
        self._refresh_empty_state()

    def _set_bin_kind_from_combo(self) -> None:
        self._bin_kind = str(self._bin_combo.currentData() or "all")
        self._apply_filter()

    def _set_filter_kind(self, kind: str) -> None:
        self._filter_kind = kind or "all"
        if self._bin_kind != "all":
            self._bin_kind = "all"
            self._bin_combo.blockSignals(True)
            self._bin_combo.setCurrentIndex(0)
            self._bin_combo.blockSignals(False)
        self._apply_filter()


    def _set_sort_mode_from_combo(self) -> None:
        self._sort_mode = str(self._sort_combo.currentData() or "name")
        self._sort_items()
        self._apply_filter()



    def _matches_smart_bin(
        self,
        item: QListWidgetItem,
        active_kind: str,
        basename_counts: dict[str, int],
    ) -> bool:
        path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        kind = str(item.data(Qt.ItemDataRole.UserRole + 2) or "")
        if active_kind == "proxy_stale":
            return kind == "V" and _proxy_state_for_video(path) == "stale"
        if active_kind == "proxy_missing":
            return kind == "V" and path.exists() and path.suffix.lower() in VIDEO_EXTS and _proxy_state_for_video(path) == ""
        if active_kind == "duplicate_name":
            return bool(path.name) and basename_counts.get(path.name.casefold(), 0) > 1
        return True

    def _refresh_empty_state(self) -> None:
        total = self._list.count()
        visible = sum(
            1 for i in range(total)
            if not self._list.item(i).isHidden()
        )
        is_empty = total == 0
        no_match = total > 0 and visible == 0
        apply_state_to_label(
            self._empty_label,
            self._media_pool_state(total=total, visible=visible),
        )
        has_featured = bool(getattr(self, "_featured_path", "") or "")
        self._empty_label.setVisible(is_empty or (no_match and not has_featured))
        self._list.setVisible(total > 0 and visible > 0)

    def _media_pool_state(self, *, total: int, visible: int):
        active_kind = self._bin_kind if self._bin_kind != "all" else self._filter_kind
        kind_label = {
            "all": "All",
            "V": "Video",
            "A": "Audio",
            "S": "Actor",
            "R": "VRM Avatar",
            "M": "MMD",
            "3": "3D",
            "proxy_missing": "Proxy Missing",
            "proxy_stale": "Proxy Stale",
            "duplicate_name": "Duplicate Name",
        }.get(active_kind, "All")
        return media_pool_empty_state(
            total=total,
            visible=visible,
            query=self._search_edit.text(),
            kind_label=kind_label,
        )


    def _set_preview_for_item(self, item: QListWidgetItem | None) -> None:
        if item is None:
            self._preview_label.hide()
            return
        pm = item.icon().pixmap(QSize(52, 52))
        if pm.isNull():
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText("No preview")
        else:
            self._preview_label.setText("")
            self._preview_label.setPixmap(pm)
        self._preview_label.show()


    def _refresh_metadata_panel(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            self._set_featured_item(item)
            self.selection_changed.emit(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        else:
            self.selection_changed.emit("")
        self._metadata_label.hide()
        self._preview_label.hide()

    def _on_item_hovered(self, item: QListWidgetItem) -> None:
        if item is None:
            return
        self._metadata_label.hide()
        self._preview_label.hide()

    def _on_item_scrubbed(self, item: QListWidgetItem, ratio: float) -> None:
        if item is None:
            return
        self._metadata_label.hide()
        self._preview_label.hide()


from app import media_pool_visual_workflow as _media_pool_visual_workflow

MediaPool._item_metadata_text = _media_pool_visual_workflow._item_metadata_text
MediaPool._featured_pixmap_for_item = _media_pool_visual_workflow._featured_pixmap_for_item
MediaPool._refresh_item_thumbnail = _media_pool_visual_workflow._refresh_item_thumbnail
MediaPool._set_scrub_preview_for_item = _media_pool_visual_workflow._set_scrub_preview_for_item
MediaPool.refresh_proxy_statuses = _media_pool_visual_workflow.refresh_proxy_statuses
MediaPool.refresh_actor_qa_status = _media_pool_visual_workflow.refresh_actor_qa_status
MediaPool.media_health_payload = _media_pool_visual_workflow.media_health_payload


from app import media_pool_import_workflow as _media_pool_import_workflow

MediaPool.eventFilter = _media_pool_import_workflow.eventFilter
MediaPool.add_path = _media_pool_import_workflow.add_path
MediaPool.import_3d_paths = _media_pool_import_workflow.import_3d_paths
MediaPool.dropEvent = _media_pool_import_workflow.dropEvent
MediaPool._show_item_context_menu = _media_pool_import_workflow._show_item_context_menu
MediaPool._open_youtube_url_dialog = _media_pool_import_workflow._open_youtube_url_dialog
MediaPool._set_view_mode = _media_pool_import_workflow._set_view_mode
MediaPool._sort_items = _media_pool_import_workflow._sort_items
MediaPool._apply_filter = _media_pool_import_workflow._apply_filter
