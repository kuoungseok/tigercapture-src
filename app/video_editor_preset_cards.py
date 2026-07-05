from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDrag,
    QFont,
    QImage,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.video_editor_preset_browser_style import PRESET_TILE as _PRESET_TILE
from app.video_editor_preset_browser_widgets import (
    PresetBrowser as _PresetBrowser,
    PresetPreviewSwatch as _PresetPreviewSwatch,
)

TRANSITION_MIME_TYPE = "application/x-tigercapture-clip-transition"
TITLE_PRESET_MIME_TYPE = "application/x-tigercapture-title-preset"
EFFECT_PRESET_MIME_TYPE = "application/x-tigercapture-effect-preset"
EDITOR_PRESET_MIME_TYPE = "application/x-tigercapture-editor-preset"

TITLE_PRESETS = [
    {"id": "lower_third", "name": "Lower Third", "icon": "LT", "text": "Lower third text", "font_size": 42, "color": "#ffffff", "bg_color": "#1a1a1aaa", "x_norm": 0.05, "y_norm": 0.82, "preset_id_in": "slide-right-in", "preset_id_out": "slide-left-out", "duration_ms": 3000, "desc": "Lower third slide in"},
    {"id": "main_title", "name": "Main Title", "icon": "T", "text": "Main Title", "font_size": 72, "color": "#ffffff", "bg_color": "", "x_norm": 0.5, "y_norm": 0.45, "preset_id_in": "fade-in", "preset_id_out": "fade-out", "duration_ms": 4000, "desc": "Centered title"},
    {"id": "subtitle", "name": "Subtitle", "icon": "CC", "text": "Subtitle text", "font_size": 36, "color": "#fffde7", "bg_color": "#00000088", "x_norm": 0.5, "y_norm": 0.88, "preset_id_in": "fade-in", "preset_id_out": "fade-out", "duration_ms": 2500, "desc": "Centered bottom subtitle"},
    {"id": "kinetic", "name": "Kinetic", "icon": "K", "text": "Kinetic Text", "font_size": 56, "color": "#ffeb3b", "bg_color": "", "x_norm": 0.5, "y_norm": 0.5, "preset_id_in": "bounce-in", "preset_id_out": "zoom-out", "duration_ms": 3000, "desc": "Bounce text effect"},
    {"id": "corner_tag", "name": "Corner Tag", "icon": "TAG", "text": "Tag", "font_size": 28, "color": "#ffffff", "bg_color": "#e53935cc", "x_norm": 0.88, "y_norm": 0.05, "preset_id_in": "pop-in", "preset_id_out": "pop-out", "duration_ms": 2000, "desc": "Corner tag"},
    {"id": "typewriter", "name": "Typewriter", "icon": "|_", "text": "Typewriter effect", "font_size": 48, "color": "#e8f5e9", "bg_color": "", "x_norm": 0.5, "y_norm": 0.5, "preset_id_in": "typewriter-in", "preset_id_out": "fade-out", "duration_ms": 4000, "desc": "Typing effect"},
]
# ---------------------------------------------------------------------------
#  Effect preset cards (drag-source for clip-level effects)
# ---------------------------------------------------------------------------

def _hash_palette(seed: str) -> tuple[str, str, str]:
    palettes = (
        ("#FF8057", "#E84E78", "#6F5CFF"),
        ("#5CC8FF", "#6F5CFF", "#101421"),
        ("#60E6C5", "#2D8DFF", "#111421"),
        ("#FFBD59", "#FF8057", "#251F3E"),
        ("#B56CFF", "#6F5CFF", "#26345F"),
        ("#78F29B", "#33B7FF", "#15251F"),
    )
    idx = int(hashlib.sha1(str(seed).encode("utf-8", "ignore")).hexdigest()[:2], 16)
    return palettes[idx % len(palettes)]


def _tile_badge(label: str, fallback: str = "FX") -> str:
    parts = ["".join(ch for ch in part if ch.isalnum()) for part in str(label or "").split()]
    parts = [part for part in parts if part]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if parts:
        text = parts[0].upper()
        return text[:2] if len(text) > 1 else text
    return fallback


def _normalize_preset_query(value: object) -> str:
    text = str(value or "").casefold()
    for ch in ("-", "_", "/", "\\", ":", "|", "(", ")", "[", "]", "{", "}", ".", ","):
        text = text.replace(ch, " ")
    return " ".join(text.split())


_PRESET_NATURAL_QUERY_ALIASES: dict[str, tuple[str, ...]] = {
    "숏폼": ("short form", "shortform", "vertical", "social", "reel", "caption"),
    "쇼츠": ("short form", "shortform", "vertical", "social", "reel", "caption"),
    "릴스": ("short form", "vertical", "reel", "social"),
    "틱톡": ("short form", "vertical", "tiktok", "social"),
    "게임": ("gameplay", "game", "esports", "stream", "capture"),
    "튜토리얼": ("tutorial", "how to", "hotkey", "step", "screen"),
    "강좌": ("tutorial", "how to", "step", "screen"),
    "voice": ("dialogue", "voice", "podcast", "talking head"),
    "보정": ("dialogue", "voice", "vocal"),
    "선명": ("clean", "clarity", "cleanup", "sharp", "readable"),
    "noise": ("noise", "denoise", "cleanup", "dialogue"),
    "자막": ("caption", "subtitle"),
    "상품": ("product", "demo", "commercial", "review"),
    "리뷰": ("review", "product", "comparison", "verdict"),
    "브이로그": ("b roll", "b-roll", "cutaway", "documentary", "story"),
    "뉴스": ("news", "documentary", "editorial"),
    "순위": ("ranking", "listicle", "countdown"),
    "스파인": ("spine", "anime", "character", "actor", "reaction"),
    "spine_actor": ("spine", "actor", "character"),
    "라이브2d": ("live2d", "actor", "character"),
    "라이브디": ("live2d", "actor", "character"),
    "character": ("character", "actor", "live2d", "spine"),
}


def _preset_query_groups(value: object) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    for term in _normalize_preset_query(value).split():
        aliases = _PRESET_NATURAL_QUERY_ALIASES.get(term, ())
        normalized = [_normalize_preset_query(term)]
        normalized.extend(_normalize_preset_query(alias) for alias in aliases)
        group = tuple(item for item in dict.fromkeys(normalized) if item)
        if group:
            groups.append(group)
    return groups


def _preset_query_matches(haystack: str, query: object) -> bool:
    groups = _preset_query_groups(query)
    if not groups:
        return True
    hay = _normalize_preset_query(haystack)
    return all(any(term in hay for term in group) for group in groups)


def _preset_query_score(haystack: str, query: object) -> int:
    groups = _preset_query_groups(query)
    if not groups:
        return 0
    hay = _normalize_preset_query(haystack)
    score = 0
    for group in groups:
        matched = False
        for idx, term in enumerate(group):
            if not term:
                continue
            pos = hay.find(term)
            if pos < 0:
                continue
            score += max(2, 24 - idx * 3)
            if pos == 0:
                score += 8
            elif f" {term}" in hay:
                score += 4
            matched = True
            break
        if not matched:
            return 0
    return score


def _preset_alias_text(
    label: str,
    category: str,
    kind: str,
    tags: tuple[str, ...],
    payload: dict | None,
) -> str:
    text = _normalize_preset_query(" ".join((label, category, kind, " ".join(tags))))
    payload = dict(payload or {})
    aliases: list[str] = []
    if "chroma_key" in payload or "green" in text or "screen" in text or "key" in text:
        aliases.append("green screen chroma key alpha remove background 그린스크린 크로마키 배경 제거 투명")
    if "title" in text or "caption" in text or "subtitle" in text:
        aliases.append("title text caption subtitle typography")
    if "transition" in text or "dissolve" in text or "wipe" in text or "fade" in text:
        aliases.append("transition dissolve fade wipe slide cut")
    if "noise" in text or "denoise" in text or "clean" in text:
        aliases.append("denoise noise cleanup clarity 노이즈 제거 잡음 정리 선명")
    if "sharpen" in text or "sharp" in text:
        aliases.append("sharpen clarity detail")
    if "glitch" in text or "stream" in text:
        aliases.append("glitch stream shake chromatic")
    if "vignette" in text or "focus" in text:
        aliases.append("vignette focus dark edge")
    if "template" in text or "workflow" in text:
        aliases.append("template workflow one click automation 템플릿 워크플로우 원클릭 자동")
    if "product" in text or "review" in text:
        aliases.append("product review commerce")
    if "game" in text or "capture" in text or "tutorial" in text:
        aliases.append("game capture tutorial hotkey")
    return " ".join(aliases)


def _preset_payload_with_intensity(payload: dict | None, intensity: float) -> dict:
    """Return a preview/apply payload scaled by an intensity slider."""
    out = dict(payload or {})
    try:
        strength = max(0.0, min(1.5, float(intensity)))
    except Exception:
        strength = 1.0
    out["preset_intensity"] = strength
    vf = out.get("video_filters")
    if isinstance(vf, dict):
        scaled = dict(vf)
        for key in ("sharpen", "vignette", "denoise", "chroma_aberration", "glitch"):
            if key in scaled:
                try:
                    scaled[key] = float(scaled[key]) * strength
                except Exception:
                    pass
        out["video_filters"] = scaled
    chroma = out.get("chroma_key")
    if isinstance(chroma, dict):
        scaled = dict(chroma)
        if "spill_suppress" in scaled:
            try:
                scaled["spill_suppress"] = float(scaled["spill_suppress"]) * strength
            except Exception:
                pass
        out["chroma_key"] = scaled
    return out


def _preset_preview_badges(kind: str, payload: dict | None, tags: tuple[str, ...]) -> list[str]:
    kind_text = str(kind or "").casefold()
    payload = dict(payload or {})
    tags_text = " ".join(str(tag).casefold() for tag in tags)
    badges: list[str] = []
    if "title" in kind_text or "caption" in kind_text:
        badges.append("Text")
    elif "transition" in kind_text:
        badges.append("Cut")
    elif "template" in kind_text or "workflow" in tags_text:
        badges.append("Timeline")
    else:
        badges.append("Clip")
    if isinstance(payload.get("chroma_key"), dict):
        badges.append("Alpha")
    if any(word in tags_text for word in ("gpu", "shader", "native")):
        badges.append("GPU")
    elif any(word in tags_text for word in ("denoise", "noise", "tracking", "mask")):
        badges.append("Heavy")
    else:
        badges.append("Fast")
    if "preset_intensity" in payload or "effect" in kind_text:
        badges.append("A/B")
    return badges[:4]


def _preset_preview_details(kind: str, payload: dict | None, tags: tuple[str, ...]) -> list[str]:
    payload = dict(payload or {})
    tags_text = ", ".join(str(tag) for tag in tags[:5])
    details: list[str] = []
    vf = payload.get("video_filters")
    if isinstance(vf, dict):
        active = [
            key.replace("_", " ")
            for key in ("sharpen", "vignette", "denoise", "chroma_aberration", "glitch")
            if float(vf.get(key, 0) or 0) > 0
        ]
        if active:
            details.append("Filters: " + ", ".join(active[:4]))
    if isinstance(payload.get("chroma_key"), dict):
        details.append("Key: HSV alpha mask")
    if "transition" in str(kind or "").casefold() or "transition_out_type" in payload:
        details.append(f"Duration: {int(payload.get('transition_out_ms') or payload.get('ms') or 500)} ms")
    if payload.get("sequence"):
        details.append(f"Steps: {len(payload.get('sequence') or [])}")
    if tags_text:
        details.append("Tags: " + tags_text)
    return details[:4]


def _preset_preview_cache_root() -> Path:
    try:
        from app.paths import default_save_dir

        root = default_save_dir() / ".cache" / "preset_previews"
    except Exception:
        root = Path.home() / ".tigercapture" / "preset_previews"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _preset_preview_cache_path(preset_id: str, payload: dict | None, kind: str, size: QSize) -> Path:
    material = json.dumps(
        {
            "id": str(preset_id or ""),
            "kind": str(kind or ""),
            "payload": payload or {},
            "w": int(size.width()),
            "h": int(size.height()),
            "v": 2,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    key = hashlib.sha1(material.encode("utf-8", "replace")).hexdigest()
    return _preset_preview_cache_root() / f"{key}.png"


def _render_static_preset_preview(
    *,
    colors: tuple[str, str, str],
    kind: str,
    label: str,
    payload: dict | None,
    tags: tuple[str, ...],
    category: str,
    preset_id: str,
    size: QSize = QSize(240, 86),
) -> QPixmap:
    path = _preset_preview_cache_path(preset_id, payload, kind, size)
    if path.exists():
        cached = QPixmap(str(path))
        if not cached.isNull():
            return cached
    swatch = _PresetPreviewSwatch(
        colors,
        kind=kind,
        label=label,
        payload=payload,
        tags=tags,
        category=category,
        payload_with_intensity=_preset_payload_with_intensity,
    )
    swatch.resize(size)
    pix = swatch.grab()
    try:
        pix.save(str(path), "PNG")
    except Exception:
        pass
    return pix


def _sample_pixmap_digest(sample: QPixmap | None) -> str:
    if sample is None or sample.isNull():
        return "none"
    try:
        image = sample.scaled(
            QSize(48, 27),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.FastTransformation,
        ).toImage().convertToFormat(QImage.Format.Format_RGB888)
        return hashlib.sha1(bytes(image.constBits())).hexdigest()[:16]
    except Exception:
        return "sample"


def _preset_preview_safe_label(label: str, kind: str, preset_id: str) -> str:
    """Keep offscreen preview labels readable even when CJK fonts are unavailable."""
    raw = str(label or "").encode("ascii", "ignore").decode("ascii").strip()
    if raw:
        return raw
    fallback = str(preset_id or kind or "preset").replace("_", " ").replace("-", " ").strip()
    parts = [part for part in fallback.split() if part and not part.isdigit()]
    return " ".join(parts[:3]).title() or str(kind or "Preset").title()


def _preset_preview_font(point_size: int = 9, *, bold: bool = False) -> QFont:
    font = QFont("Arial")
    font.setPointSize(point_size)
    font.setBold(bold)
    return font


def _render_contextual_preset_preview(
    *,
    colors: tuple[str, str, str],
    kind: str,
    label: str,
    payload: dict | None,
    tags: tuple[str, ...],
    category: str,
    preset_id: str,
    sample_pixmap: QPixmap | None,
    size: QSize = QSize(240, 86),
) -> QPixmap:
    path = _preset_preview_cache_path(
        f"context:{preset_id}:{_sample_pixmap_digest(sample_pixmap)}",
        payload,
        kind,
        size,
    )
    if path.exists():
        cached = QPixmap(str(path))
        if not cached.isNull():
            return cached
    swatch = _PresetPreviewSwatch(
        colors,
        kind=kind,
        label=label,
        payload=payload,
        tags=tags,
        category=category,
        sample_pixmap=sample_pixmap,
        payload_with_intensity=_preset_payload_with_intensity,
    )
    swatch.resize(size)
    pix = swatch.grab()
    try:
        pix.save(str(path), "PNG")
    except Exception:
        pass
    return pix


def _render_preset_application_frame_preview(
    *,
    preset_id: str,
    kind: str,
    label: str,
    payload: dict | None,
    tags: tuple[str, ...],
    sample_pixmap: QPixmap | None,
    size: QSize = QSize(360, 202),
) -> QPixmap:
    """Render a compact current-frame simulation for Preview Apply."""
    payload = dict(payload or {})
    path = _preset_preview_cache_path(
        f"apply-v5:{preset_id}:{_sample_pixmap_digest(sample_pixmap)}",
        payload,
        kind,
        size,
    )
    if path.exists():
        cached = QPixmap(str(path))
        if not cached.isNull():
            return cached

    pix = QPixmap(size)
    pix.fill(QColor("#0A0D16"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setFont(_preset_preview_font(9))
    rect = pix.rect()
    if sample_pixmap is not None and not sample_pixmap.isNull():
        scaled = sample_pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        sx = max(0, (scaled.width() - size.width()) // 2)
        sy = max(0, (scaled.height() - size.height()) // 2)
        painter.drawPixmap(rect, scaled, QRect(sx, sy, size.width(), size.height()))
    else:
        grad = QLinearGradient(0, 0, size.width(), size.height())
        colors = _hash_palette(f"apply:{preset_id}:{label}")
        grad.setColorAt(0.0, QColor(colors[0]))
        grad.setColorAt(0.55, QColor(colors[1]))
        grad.setColorAt(1.0, QColor(colors[2]))
        painter.fillRect(rect, grad)

    painter.fillRect(rect, QColor(6, 8, 16, 76))
    kind_text = str(kind or "").casefold()
    tags_text = " ".join(str(tag).casefold() for tag in tags)
    vf = payload.get("video_filters") if isinstance(payload.get("video_filters"), dict) else {}

    if kind_text == "effect" or vf or isinstance(payload.get("chroma_key"), dict):
        effect_chips: list[tuple[str, str]] = []
        if vf.get("blur") or vf.get("denoise") or "blur" in tags_text or "denoise" in tags_text:
            effect_chips.append(("SOFT", "#63D7FF"))
            painter.setPen(Qt.PenStyle.NoPen)
            for idx, color in enumerate((QColor(112, 170, 255, 42), QColor(255, 126, 92, 34), QColor(138, 124, 255, 38))):
                painter.setBrush(color)
                painter.drawEllipse(QRect(34 + idx * 82, 44 + (idx % 2) * 18, 94, 68))
            painter.fillRect(rect, QColor(180, 210, 255, 22))
        if vf.get("sharpen"):
            effect_chips.append(("EDGE", "#FFFFFF"))
            painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
            for y in range(18, size.height(), 22):
                painter.drawLine(16, y, size.width() - 16, y + 5)
            painter.setPen(QPen(QColor(255, 255, 255, 115), 2))
            painter.drawRoundedRect(QRect(44, 42, size.width() - 88, size.height() - 88), 10, 10)
        if vf.get("vignette"):
            effect_chips.append(("VIGNETTE", "#FF7A59"))
            painter.setPen(QPen(QColor(0, 0, 0, 110), 12))
            painter.drawRoundedRect(rect.adjusted(8, 8, -8, -8), 18, 18)
        if vf.get("glitch") or "glitch" in tags_text:
            effect_chips.append(("GLITCH", "#FF5C8A"))
            for idx, color in enumerate((QColor(255, 90, 90, 130), QColor(90, 170, 255, 120))):
                painter.fillRect(QRect(20 + idx * 8, 46 + idx * 22, size.width() - 60, 10), color)
            painter.setPen(QPen(QColor(255, 255, 255, 92), 1))
            for y in range(28, size.height() - 36, 28):
                painter.drawLine(26, y, size.width() - 28, y)
        if vf.get("lut") or vf.get("color") or "lut" in tags_text or "grade" in tags_text:
            effect_chips.append(("LUT", "#FFD36A"))
            strip = QRect(32, size.height() - 62, size.width() - 64, 18)
            grad = QLinearGradient(strip.topLeft(), strip.topRight())
            for stop, color in (
                (0.0, "#FF7043"),
                (0.34, "#FFD36A"),
                (0.67, "#63D7FF"),
                (1.0, "#8A7CFF"),
            ):
                grad.setColorAt(stop, QColor(color))
            painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(strip, 8, 8)
        if isinstance(payload.get("chroma_key"), dict) or "keying" in tags_text:
            effect_chips.append(("KEY", "#63FF89"))
            tile = 12
            matte_rect = QRect(size.width() // 2, 0, size.width() // 2, size.height())
            for yy in range(matte_rect.top(), matte_rect.bottom(), tile):
                for xx in range(matte_rect.left(), matte_rect.right(), tile):
                    checker = QColor(255, 255, 255, 34) if ((xx // tile + yy // tile) % 2) else QColor(0, 0, 0, 34)
                    painter.fillRect(QRect(xx, yy, tile, tile), checker)
            painter.setBrush(QColor(63, 255, 137, 72))
            painter.setPen(QPen(QColor(63, 255, 137, 180), 2))
            painter.drawRoundedRect(QRect(28, 34, size.width() - 56, size.height() - 70), 18, 18)
            painter.drawText(QRect(36, 42, size.width() - 72, 32), Qt.AlignmentFlag.AlignLeft, "KEY MATTE")
        if effect_chips:
            chip_x = 22
            for chip, color in effect_chips[:4]:
                chip_rect = QRect(chip_x, size.height() - 31, max(42, len(chip) * 7 + 16), 18)
                painter.setBrush(QColor(8, 10, 18, 190))
                painter.setPen(QPen(QColor(color), 1))
                painter.drawRoundedRect(chip_rect, 8, 8)
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, chip)
                chip_x = chip_rect.right() + 6
    elif kind_text in {"title", "caption_style", "sticker"}:
        text = str(payload.get("text", "") or label or "TITLE")
        painter.setBrush(QColor(10, 13, 24, 178))
        painter.setPen(QPen(QColor(255, 255, 255, 52), 1))
        pill = QRect(34, size.height() - 70, size.width() - 68, 44)
        painter.drawRoundedRect(pill, 18, 18)
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(15 if kind_text != "caption_style" else 12)
        painter.setFont(font)
        painter.drawText(pill.adjusted(14, 0, -14, 0), Qt.AlignmentFlag.AlignCenter, text[:36])
    elif kind_text == "transition":
        ttype = str(payload.get("transition_out_type", payload.get("type", "transition")) or "transition")
        mid = size.width() // 2
        painter.fillRect(QRect(mid, 0, size.width() - mid, size.height()), QColor(255, 96, 56, 82))
        painter.setPen(QPen(QColor("#FFFFFF"), 3))
        painter.drawLine(mid, 20, mid, size.height() - 20)
        painter.drawText(QRect(0, size.height() - 44, size.width(), 26), Qt.AlignmentFlag.AlignCenter, ttype.upper())
    elif kind_text == "motion":
        painter.setPen(QPen(QColor("#8A7CFF"), 3))
        painter.setBrush(QColor(138, 124, 255, 42))
        painter.drawRoundedRect(QRect(76, 34, size.width() - 152, size.height() - 68), 14, 14)
        painter.drawText(QRect(0, size.height() - 42, size.width(), 24), Qt.AlignmentFlag.AlignCenter, "ZOOM / MOTION")
    elif kind_text == "audio":
        painter.setPen(QPen(QColor("#63D7FF"), 3))
        center = size.height() // 2
        for x in range(24, size.width() - 24, 12):
            h = 12 + int(28 * abs(math.sin(x * 0.055)))
            painter.drawLine(x, center - h, x, center + h)
        painter.drawText(QRect(0, size.height() - 42, size.width(), 24), Qt.AlignmentFlag.AlignCenter, "AUDIO CHAIN")
    elif kind_text == "color":
        painter.fillRect(rect, QColor(255, 150, 80, 56))
        for idx, color in enumerate(("#FF6A35", "#8A7CFF", "#63D7FF")):
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(38 + idx * 48, 34, 34, 34))
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QRect(0, size.height() - 42, size.width(), 24), Qt.AlignmentFlag.AlignCenter, "GRADE PREVIEW")
    elif kind_text == "actor":
        actor_kind = str(payload.get("actor_kind", "") or "actor").upper()
        painter.setBrush(QColor(138, 124, 255, 92))
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        body = QRect(size.width() // 2 - 28, 54, 56, 82)
        painter.drawEllipse(QRect(size.width() // 2 - 18, 28, 36, 36))
        painter.drawRoundedRect(body, 20, 20)
        painter.drawText(QRect(0, size.height() - 42, size.width(), 24), Qt.AlignmentFlag.AlignCenter, f"{actor_kind} ACTOR")
    elif kind_text == "template":
        sequence = payload.get("sequence") if isinstance(payload.get("sequence"), list) else []
        colors = _hash_palette(f"template:{preset_id}:{label}")
        template_bg = QLinearGradient(0, 0, size.width(), size.height())
        template_bg.setColorAt(0.0, QColor("#121727"))
        template_bg.setColorAt(0.45, QColor("#15112A"))
        template_bg.setColorAt(1.0, QColor("#22132E"))
        painter.fillRect(rect, template_bg)
        tile_colors = (
            "#FF7043", "#FFD36A", "#63D7FF", "#8A7CFF",
            "#FF5C8A", "#57E5B2", "#55A6FF", "#FF9E52",
            "#D4A8FF", "#33D3E6", "#7D61FF", "#FFCC66",
        )
        tile_size = 24
        tile_gap = 7
        start_x = 18
        start_y = 24
        for idx, color in enumerate(tile_colors):
            col = idx % 6
            row = idx // 6
            tile = QRect(start_x + col * (tile_size + tile_gap), start_y + row * (tile_size + tile_gap), tile_size, tile_size)
            tile_grad = QLinearGradient(tile.topLeft(), tile.bottomRight())
            tile_grad.setColorAt(0.0, QColor(color).lighter(125))
            tile_grad.setColorAt(1.0, QColor(color).darker(112))
            painter.setBrush(QBrush(tile_grad))
            painter.setPen(QPen(QColor(255, 255, 255, 68), 1))
            painter.drawRoundedRect(tile, 7, 7)
        painter.setBrush(QColor(255, 255, 255, 34))
        painter.setPen(QPen(QColor(255, 255, 255, 58), 1))
        painter.drawRoundedRect(QRect(size.width() - 126, 30, 92, 50), 18, 18)
        painter.setBrush(QColor(8, 10, 18, 160))
        painter.setPen(QPen(QColor(255, 255, 255, 54), 1))
        painter.drawRoundedRect(QRect(22, 104, size.width() - 44, 26), 13, 13)
        kind_colors = {
            "effect": "#63D7FF",
            "transition": "#FFD36A",
            "title": "#FF7A59",
            "caption_style": "#D4A8FF",
            "sticker": "#FFB629",
            "motion": "#8A7CFF",
            "audio": "#78F29B",
            "color": "#FF8A50",
            "actor": "#B18CFF",
        }
        kind_labels = {
            "effect": "FX",
            "transition": "TR",
            "title": "T",
            "caption_style": "CC",
            "sticker": "ST",
            "motion": "M",
            "audio": "AU",
            "color": "COL",
            "actor": "ACT",
        }
        rail = QRect(32, size.height() - 66, size.width() - 64, 18)
        painter.setPen(QPen(QColor(255, 255, 255, 52), 1))
        painter.setBrush(QColor(8, 10, 18, 172))
        painter.drawRoundedRect(rail, 9, 9)
        x = 28
        y = 88
        span_ms = max(
            1000,
            max(
                (
                    int(entry.get("at_ms", 0) or 0)
                    + max(260, int(entry.get("duration_ms", 0) or 0))
                    for entry in sequence
                    if isinstance(entry, dict)
                ),
                default=1000,
            ),
        )
        for idx, entry in enumerate(sequence[:7]):
            if not isinstance(entry, dict):
                continue
            kind_name = str(entry.get("kind", "preset") or "preset")
            color = QColor(kind_colors.get(kind_name, colors[idx % len(colors)]))
            label_text = kind_labels.get(kind_name, kind_name[:3].upper())
            w = 34
            box = QRect(x, y + (idx % 2) * 33, w, 26)
            painter.setBrush(color)
            painter.setPen(QPen(QColor(255, 255, 255, 76), 1))
            painter.drawRoundedRect(box, 10, 10)
            painter.setPen(QPen(QColor(255, 255, 255, 210), 2))
            icon = box.adjusted(8, 7, -8, -7)
            if label_text == "TR":
                painter.drawLine(icon.left(), icon.center().y(), icon.right() - 5, icon.center().y())
                painter.drawLine(icon.right() - 5, icon.top(), icon.right(), icon.center().y())
                painter.drawLine(icon.right() - 5, icon.bottom(), icon.right(), icon.center().y())
            elif label_text in {"T", "CC"}:
                painter.drawLine(icon.left(), icon.top(), icon.right(), icon.top())
                painter.drawLine(icon.center().x(), icon.top(), icon.center().x(), icon.bottom())
            elif label_text == "AU":
                painter.drawLine(icon.left(), icon.center().y(), icon.left() + 4, icon.center().y())
                painter.drawLine(icon.left() + 5, icon.top() + 2, icon.left() + 5, icon.bottom() - 2)
                painter.drawArc(icon.adjusted(2, 0, 4, 0), -40 * 16, 80 * 16)
            elif label_text == "COL":
                painter.setBrush(QColor(255, 255, 255, 210))
                painter.drawEllipse(icon.center(), 4, 4)
            else:
                painter.drawLine(icon.left(), icon.bottom(), icon.center().x(), icon.top())
                painter.drawLine(icon.center().x(), icon.top(), icon.right(), icon.bottom())
            at_ms = max(0, int(entry.get("at_ms", 0) or 0))
            dur_ms = max(260, int(entry.get("duration_ms", 0) or 0))
            tx = rail.left() + int(at_ms / span_ms * rail.width())
            tw = max(10, int(dur_ms / span_ms * rail.width()))
            tw = min(tw, rail.right() - tx)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRect(tx, rail.top() + 4, max(5, tw), 10), 4, 4)
            x += w + 8
        if len(sequence) > 7:
            more = QRect(x, y + 16, 36, 24)
            painter.setBrush(QColor(8, 10, 18, 190))
            painter.setPen(QPen(QColor(255, 255, 255, 56), 1))
            painter.drawRoundedRect(more, 10, 10)
            painter.setPen(QPen(QColor("#DDE2FF"), 2))
            cy = more.center().y()
            for dot in range(3):
                painter.drawPoint(more.left() + 13 + dot * 6, cy)
        step_dots = min(8, max(1, len(sequence)))
        painter.setPen(Qt.PenStyle.NoPen)
        for dot in range(step_dots):
            painter.setBrush(QColor(tile_colors[dot % len(tile_colors)]))
            painter.drawEllipse(QPoint(size.width() - 30 - dot * 10, 97), 3, 3)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(9, 11, 20, 190))
    title_rect = QRect(10, 10, min(size.width() - 20, 190), 28)
    painter.drawRoundedRect(title_rect, 12, 12)
    if kind_text == "template":
        colors = ("#FF7043", "#FFD36A", "#63D7FF", "#8A7CFF", "#57E5B2")
        for idx, color in enumerate(colors):
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRect(title_rect.left() + 13 + idx * 16, title_rect.top() + 8, 10, 12), 4, 4)
    else:
        painter.setPen(QColor("#DDE2FF"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(
            QRect(22, 10, min(size.width() - 44, 168), 28),
            Qt.AlignmentFlag.AlignVCenter,
            _preset_preview_safe_label(label, kind, preset_id)[:28],
        )
    painter.end()
    try:
        pix.save(str(path), "PNG")
    except Exception:
        pass
    return pix


def _render_preset_ab_application_preview(
    *,
    preset_id: str,
    kind: str,
    label: str,
    payload: dict | None,
    tags: tuple[str, ...],
    sample_pixmap: QPixmap | None,
    size: QSize = QSize(360, 202),
    phase: float = 0.0,
) -> QPixmap:
    """Render an A/B preset preview using the active frame when possible."""
    payload = dict(payload or {})
    phase = float(phase or 0.0) % 1.0
    path = _preset_preview_cache_path(
        f"apply-ab-v5:{preset_id}:{_sample_pixmap_digest(sample_pixmap)}",
        payload,
        kind,
        size,
    )
    use_cache = phase <= 0.0001
    if use_cache and path.exists():
        cached = QPixmap(str(path))
        if not cached.isNull():
            return cached

    before = QPixmap(size)
    before.fill(QColor("#090C15"))
    painter = QPainter(before)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setFont(_preset_preview_font(9))
    rect = before.rect()
    if sample_pixmap is not None and not sample_pixmap.isNull():
        scaled = sample_pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        sx = max(0, (scaled.width() - size.width()) // 2)
        sy = max(0, (scaled.height() - size.height()) // 2)
        painter.drawPixmap(rect, scaled, QRect(sx, sy, size.width(), size.height()))
    else:
        grad = QLinearGradient(0, 0, size.width(), size.height())
        colors = _hash_palette(f"before:{preset_id}:{label}")
        grad.setColorAt(0.0, QColor(colors[0]).darker(125))
        grad.setColorAt(0.6, QColor(colors[1]).darker(140))
        grad.setColorAt(1.0, QColor(colors[2]).darker(125))
        painter.fillRect(rect, grad)
    painter.fillRect(rect, QColor(4, 6, 14, 82))
    painter.end()

    after = _render_preset_application_frame_preview(
        preset_id=preset_id,
        kind=kind,
        label=label,
        payload=payload,
        tags=tags,
        sample_pixmap=sample_pixmap,
        size=size,
    )

    pix = QPixmap(size)
    pix.fill(QColor("#080B14"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setFont(_preset_preview_font(9))
    kind_text = str(kind or "").casefold()
    tags_text = " ".join(str(tag).casefold() for tag in tags)
    split_base = size.width() // 2
    if kind_text in {"transition", "motion", "template", "effect", "color"}:
        split_base = int(size.width() * (0.38 + 0.24 * (0.5 + 0.5 * math.sin(phase * math.tau))))
    split = max(72, min(size.width() - 72, split_base))
    painter.drawPixmap(QRect(0, 0, split, size.height()), before, QRect(0, 0, split, size.height()))
    if kind_text == "template":
        painter.drawPixmap(
            QRect(split, 0, size.width() - split, size.height()),
            after,
            QRect(0, 0, size.width(), size.height()),
        )
    else:
        painter.drawPixmap(
            QRect(split, 0, size.width() - split, size.height()),
            after,
            QRect(split, 0, size.width() - split, size.height()),
        )
    painter.setPen(QPen(QColor("#FFFFFF"), 2))
    painter.drawLine(split, 10, split, size.height() - 10)
    cursor_x = int(18 + (size.width() - 36) * phase)
    accent = QColor("#8A7CFF")
    if kind_text == "transition":
        accent = QColor("#FF7A59")
    elif kind_text in {"title", "caption_style", "sticker"}:
        accent = QColor("#FFD36A")
    elif kind_text == "audio":
        accent = QColor("#63D7FF")
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 38))
    painter.drawRoundedRect(QRect(18, size.height() - 16, size.width() - 36, 5), 2, 2)
    painter.setBrush(accent)
    painter.drawRoundedRect(QRect(18, size.height() - 16, max(4, cursor_x - 18), 5), 2, 2)
    painter.setPen(QPen(QColor("#FFFFFF"), 1.4))
    painter.drawLine(cursor_x, size.height() - 22, cursor_x, size.height() - 8)
    pointer = QPainterPath()
    pointer.moveTo(cursor_x - 7, size.height() - 40)
    pointer.lineTo(cursor_x + 8, size.height() - 31)
    pointer.lineTo(cursor_x + 1, size.height() - 29)
    pointer.lineTo(cursor_x + 7, size.height() - 19)
    pointer.lineTo(cursor_x + 2, size.height() - 17)
    pointer.lineTo(cursor_x - 4, size.height() - 27)
    pointer.lineTo(cursor_x - 9, size.height() - 22)
    pointer.closeSubpath()
    painter.setPen(QPen(QColor(8, 10, 18, 210), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawPath(pointer)
    painter.setPen(QPen(accent, 1.6))
    painter.drawPath(pointer)
    pulse_r = int(10 + 5 * (0.5 + 0.5 * math.sin(phase * math.tau)))
    painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 90), 1.6))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPoint(cursor_x, size.height() - 29), pulse_r, pulse_r)
    if kind_text in {"title", "caption_style", "sticker"}:
        painter.setBrush(QColor(255, 211, 106, 80 + int(80 * math.sin(phase * math.tau) ** 2)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(cursor_x, size.height() - 24), 7, 7)
    elif kind_text == "transition":
        ttype = str(payload.get("transition_out_type", payload.get("type", "transition")) or "transition").casefold()
        painter.setBrush(QColor(255, 122, 89, 70))
        painter.setPen(Qt.PenStyle.NoPen)
        if "slide" in ttype:
            panel_w = 82
            offset = int(34 * math.sin(phase * math.tau))
            painter.drawRoundedRect(QRect(cursor_x - panel_w + offset, 34, panel_w, size.height() - 70), 15, 15)
            painter.setBrush(QColor(99, 215, 255, 68))
            painter.drawRoundedRect(QRect(cursor_x + offset, 42, panel_w, size.height() - 86), 15, 15)
        elif "wipe" in ttype:
            band_w = 42
            painter.drawRoundedRect(QRect(max(0, cursor_x - band_w // 2), 24, band_w, size.height() - 58), 12, 12)
            painter.setBrush(QColor(255, 255, 255, 62))
            painter.drawRoundedRect(QRect(max(0, cursor_x - 5), 24, 10, size.height() - 58), 4, 4)
        elif "zoom" in ttype:
            z = int(44 + 22 * (0.5 + 0.5 * math.sin(phase * math.tau)))
            painter.setBrush(QColor(255, 122, 89, 54))
            painter.drawRoundedRect(QRect(cursor_x - z, size.height() // 2 - z // 2, z * 2, z), 16, 16)
        elif "fade" in ttype or "dissolve" in ttype:
            alpha = 35 + int(70 * (0.5 + 0.5 * math.sin(phase * math.tau)))
            fade_color = QColor(255, 255, 255, alpha) if "white" in ttype else QColor(0, 0, 0, alpha)
            painter.fillRect(pix.rect(), fade_color)
            painter.setBrush(QColor(255, 122, 89, 70))
            painter.drawRoundedRect(QRect(max(0, cursor_x - 28), 30, 56, size.height() - 64), 16, 16)
        else:
            painter.drawRoundedRect(QRect(max(0, cursor_x - 28), 30, 56, size.height() - 64), 16, 16)
        painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
        painter.drawLine(QPointF(cursor_x - 10, 48), QPointF(cursor_x + 10, 48))
        painter.drawLine(QPointF(cursor_x, 38), QPointF(cursor_x, 58))
    elif kind_text == "motion":
        painter.setPen(QPen(QColor("#8A7CFF"), 2.4))
        zoom = 34 + int(18 * (0.5 + 0.5 * math.sin(phase * math.tau)))
        center = QPoint(size.width() - 78, 76)
        painter.drawRoundedRect(QRect(center.x() - zoom, center.y() - zoom // 2, zoom * 2, zoom), 13, 13)
        painter.drawLine(center.x() - 24, center.y(), center.x() + 24, center.y())
    elif kind_text == "effect":
        painter.setPen(QPen(accent, 2.2))
        scan_y = 42 + int((size.height() - 88) * phase)
        painter.drawLine(26, scan_y, size.width() - 26, scan_y)
        if "key" in tags_text or isinstance(payload.get("chroma_key"), dict):
            painter.setBrush(QColor(99, 255, 137, 58))
            painter.setPen(QPen(QColor(99, 255, 137, 150), 2))
            painter.drawRoundedRect(QRect(split + 18, 40, max(30, size.width() - split - 42), size.height() - 86), 14, 14)
        elif "glitch" in tags_text:
            painter.setBrush(QColor(255, 92, 138, 70))
            painter.setPen(Qt.PenStyle.NoPen)
            for idx in range(3):
                painter.drawRoundedRect(QRect(28 + idx * 18, 44 + idx * 24, size.width() - 72, 9), 4, 4)
    elif kind_text == "template":
        sequence = payload.get("sequence") if isinstance(payload.get("sequence"), list) else []
        if sequence:
            active_idx = int(phase * max(1, len(sequence))) % len(sequence)
            entry = sequence[active_idx] if isinstance(sequence[active_idx], dict) else {}
            painter.setBrush(QColor(8, 10, 18, 198))
            painter.setPen(QPen(QColor("#8A7CFF"), 1.6))
            callout = QRect(max(14, cursor_x - 58), 38, 116, 34)
            painter.drawRoundedRect(callout, 14, 14)
            kind_colors = {
                "effect": "#63D7FF",
                "transition": "#FFD36A",
                "title": "#FF7A59",
                "caption_style": "#D4A8FF",
                "sticker": "#FFB629",
                "motion": "#8A7CFF",
                "audio": "#78F29B",
                "color": "#FF8A50",
                "actor": "#B18CFF",
            }
            active_color = QColor(kind_colors.get(str(entry.get("kind", "effect") or "effect"), "#8A7CFF"))
            painter.setPen(Qt.PenStyle.NoPen)
            for dot in range(min(5, len(sequence))):
                painter.setBrush(active_color if dot == active_idx % 5 else QColor(255, 255, 255, 72))
                painter.drawEllipse(QPoint(callout.left() + 22 + dot * 18, callout.center().y()), 5, 5)
    if kind_text in {"title", "caption_style"}:
        text = str(payload.get("text") or label or "TITLE")[:18]
        ease = 0.5 - 0.5 * math.cos(phase * math.tau)
        y = int(size.height() * 0.70 - 24 * ease)
        pill = QRect(size.width() // 2 - 84, y, 168, 32)
        painter.setBrush(QColor(11, 14, 24, 190))
        painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
        painter.drawRoundedRect(pill, 14, 14)
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(pill.adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignCenter, text)
    elif kind_text == "sticker":
        ease = 0.5 - 0.5 * math.cos(phase * math.tau)
        radius = int(13 + 9 * ease)
        center = QPoint(size.width() - 74, 64)
        painter.setBrush(QColor("#FFD36A"))
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawEllipse(center, radius, radius)
        painter.setPen(QColor("#151827"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(QRect(center.x() - radius, center.y() - radius, radius * 2, radius * 2), Qt.AlignmentFlag.AlignCenter, str(payload.get("text") or "*")[:4])
    painter.setPen(Qt.PenStyle.NoPen)
    if kind_text == "template":
        for x, color in ((12, QColor(7, 10, 18, 190)), (split + 12, QColor(255, 96, 56, 205))):
            badge = QRect(x, 12, 58, 24)
            painter.setBrush(color)
            painter.drawRoundedRect(badge, 10, 10)
            for idx, dot_color in enumerate(("#FF7043", "#FFD36A", "#63D7FF")):
                painter.setBrush(QColor(dot_color))
                painter.drawEllipse(QPoint(badge.left() + 17 + idx * 12, badge.center().y()), 4, 4)
    else:
        for x, text, color in (
            (12, "BEFORE", QColor(7, 10, 18, 190)),
            (split + 12, "AFTER", QColor(255, 96, 56, 205)),
        ):
            badge = QRect(x, 12, 62, 24)
            painter.setBrush(color)
            painter.drawRoundedRect(badge, 10, 10)
            painter.setPen(QColor("#FFFFFF"))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)
            painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(255, 255, 255, 42), 1))
    painter.drawRoundedRect(pix.rect().adjusted(1, 1, -2, -2), 14, 14)
    painter.end()
    if use_cache:
        try:
            pix.save(str(path), "PNG")
        except Exception:
            pass
    return pix


def _render_template_timeline_preview(rows: list[dict], *, size: QSize = QSize(360, 86)) -> QPixmap:
    """Render the concrete template application plan as a compact timeline."""
    pix = QPixmap(size)
    pix.fill(QColor("#090B13"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rect = pix.rect().adjusted(1, 1, -2, -2)
    painter.setPen(QPen(QColor(255, 255, 255, 38), 1))
    painter.setBrush(QColor(13, 16, 29, 245))
    painter.drawRoundedRect(rect, 13, 13)
    usable = rect.adjusted(14, 26, -14, -14)
    painter.setPen(QColor("#A7ADC2"))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(8)
    painter.setFont(font)
    painter.drawText(QRect(rect.left() + 14, rect.top() + 7, rect.width() - 28, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "TEMPLATE TIMELINE PREVIEW")
    plan = [row for row in rows if str(row.get("status")) != "template"]
    if not plan:
        painter.setPen(QColor("#7B8299"))
        painter.drawText(usable, Qt.AlignmentFlag.AlignCenter, "No template steps")
        painter.end()
        return pix
    min_ms = min(int(row.get("at_ms", 0) or 0) for row in plan)
    max_ms = max(int(row.get("at_ms", 0) or 0) + max(220, int(row.get("duration_ms", 0) or 0)) for row in plan)
    span = max(500, max_ms - min_ms)
    colors = {
        "effect": "#63D7FF",
        "title": "#FF7A59",
        "transition": "#FFD36A",
        "audio": "#78F29B",
        "color": "#8A7CFF",
        "caption_style": "#D4A8FF",
        "sticker": "#FFB629",
        "motion": "#67D8FF",
        "actor": "#B18CFF",
    }
    lanes = ["effect", "title", "caption_style", "sticker", "motion", "transition", "audio", "color", "actor"]
    for idx, row in enumerate(plan[:14]):
        kind = str(row.get("kind") or "preset")
        lane = lanes.index(kind) if kind in lanes else idx % 4
        y = usable.top() + (lane % 4) * 12
        at = int(row.get("at_ms", 0) or 0)
        dur = max(220, int(row.get("duration_ms", 0) or 0))
        x = usable.left() + int((at - min_ms) / span * usable.width())
        w = max(22, int(dur / span * usable.width()))
        if x > usable.right():
            continue
        block_w = max(6, min(w, usable.right() - x))
        if str(row.get("status")) == "blocked":
            color = QColor("#A24545")
        elif str(row.get("status")) == "skipped":
            color = QColor("#4B5269")
        else:
            color = QColor(colors.get(kind, "#8A7CFF"))
        painter.setPen(QPen(QColor(255, 255, 255, 55), 1))
        painter.setBrush(color)
        painter.drawRoundedRect(QRect(x, y, block_w, 10), 4, 4)
    painter.setPen(QColor("#7B8299"))
    painter.drawText(QRect(usable.left(), usable.bottom() - 8, usable.width(), 12), Qt.AlignmentFlag.AlignRight, f"{span / 1000:.1f}s plan")
    painter.end()
    return pix


def _preset_quality_badge(kind: str, payload: dict | None) -> tuple[str, str]:
    payload = dict(payload or {})
    if not payload:
        return "WARN", "Empty payload"
    if "effect" in str(kind or "").casefold():
        if not any(key in payload for key in ("video_filters", "chroma_key", "blur", "color_grade")):
            return "WARN", "Effect has no known effect payload"
    if "transition" in str(kind or "").casefold():
        if not (payload.get("transition_out_type") or payload.get("type")):
            return "WARN", "Transition type is missing"
    if isinstance(payload.get("sequence"), list):
        return "QA", f"{len(payload.get('sequence') or [])} step template"
    return "OK", "Preset payload looks valid"


def _preset_visual_role(
    kind: str,
    category: str,
    tags: tuple[str, ...],
    payload: dict | None,
    label: str,
) -> str:
    """Choose a semantic icon role for tiny preset tiles.

    The left dock is intentionally icon-first, so the icon should explain the
    operation instead of rotating through decorative random shapes.
    """
    payload = dict(payload or {})
    text = " ".join(
        (
            str(kind or ""),
            str(category or ""),
            " ".join(str(tag) for tag in tags),
            " ".join(str(key) for key in payload.keys()),
            str(label or ""),
        )
    ).casefold()
    if payload.get("transition_out_type") or payload.get("type") or "transition" in text:
        return "transition"
    if any(word in text for word in ("title", "caption", "subtitle", "typography", "text")) or any(
        key in payload for key in ("text", "font_size", "preset_id_in", "preset_id_out")
    ):
        return "title"
    if payload.get("sequence") or payload.get("steps") or any(
        word in text for word in ("template", "workflow", "one click", "automation")
    ):
        return "workflow"
    if any(word in text for word in ("sticker", "emoji", "label")):
        return "sticker"
    if any(word in text for word in ("live2d", "spine", "actor", "character", "avatar")):
        return "actor"
    if any(word in text for word in ("audio", "voice", "dialogue", "denoise", "noise", "sound")):
        return "audio"
    if isinstance(payload.get("chroma_key"), dict) or any(word in text for word in ("key", "alpha", "green screen")):
        return "key"
    if any(word in text for word in ("node", "graph", "composite", "mask")):
        return "node"
    if payload.get("color_grade") or any(word in text for word in ("color", "grade", "lut", "curves", "wheel")):
        return "color"
    if any(word in text for word in ("speed", "time", "remap", "slow", "fast")):
        return "speed"
    if payload.get("blur") or "blur" in text:
        return "blur"
    if "motion" in text:
        return "motion"
    if "clip" in text:
        return "clip"
    return "effect"


class _StudioPresetTile(QFrame):
    """Compact painted preset tile.

    Child labels inside tiny cards are fragile in the left rail. Painting the
    tile keeps icons aligned and shows the text only as a hover overlay.
    """

    def __init__(
        self,
        label: str,
        badge: str,
        *,
        palette_seed: str,
        tooltip: str,
        description: str = "",
        category: str = "",
        tags: tuple[str, ...] = (),
        drag_hint: str = "",
        preset_id: str = "",
        pack: str = "",
        preview_kind: str = "",
        preview_payload: dict | None = None,
        preview_provider=None,
        live_preview_callback=None,
        live_preview_clear_callback=None,
    ) -> None:
        super().__init__()
        self._label = str(label or "")
        self._badge = str(badge or "")[:4]
        self._description = str(description or "")
        self._category = str(category or "").strip() or "General"
        self._pack = str(pack or "").strip() or "Studio"
        self._preset_id = str(preset_id or palette_seed or self._label)
        self._tags = tuple(str(tag) for tag in (tags or ()) if str(tag).strip())
        self._drag_hint = str(drag_hint or "")
        self._preview_kind = str(preview_kind or category or "").strip().casefold()
        self._preview_payload = dict(preview_payload or {})
        self._preview_provider = preview_provider
        self._payload_with_intensity_fn = _preset_payload_with_intensity
        self._live_preview_callback = live_preview_callback
        self._live_preview_clear_callback = live_preview_clear_callback
        self._live_preview_active = False
        self._preview_intensity = 1.0
        self._preview_badges = _preset_preview_badges(self._preview_kind, self._preview_payload, self._tags)
        self._quality_badge, self._quality_detail = _preset_quality_badge(self._preview_kind, self._preview_payload)
        self._colors = _hash_palette(palette_seed or self._label)
        self._shape = int(hashlib.sha1(str(palette_seed or self._label).encode("utf-8", "ignore")).hexdigest()[2:4], 16) % 6
        self._visual_role = _preset_visual_role(
            self._preview_kind,
            self._category,
            self._tags,
            self._preview_payload,
            self._label,
        )
        self._hovered = False
        self._favorite = False
        self._recent_rank = 0
        self._browser = None
        self._anim_phase = 0.0
        self._window_move_suspended = False
        self._preview_popup: QFrame | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(260)
        self._preview_timer.timeout.connect(self._show_preview_popup)
        self._live_preview_timer = QTimer(self)
        self._live_preview_timer.setSingleShot(True)
        self._live_preview_timer.setInterval(180)
        self._live_preview_timer.timeout.connect(self._begin_live_preview)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(70)
        self._anim_timer.timeout.connect(self._tick_preview_animation)
        self._search_blob = _normalize_preset_query(" ".join(
            (
                self._label,
                self._description,
                self._category,
                self._pack,
                self._badge,
                " ".join(self._tags),
                _preset_alias_text(
                    self._label,
                    self._category,
                    self._preview_kind,
                    self._tags,
                    self._preview_payload,
                ),
            )
        ))
        self.setFixedSize(_PRESET_TILE, _PRESET_TILE)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMouseTracking(True)
        self.setToolTip(tooltip)
        self.setStyleSheet("background: transparent; border: none;")

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._anim_timer.start()
        self.update()
        browser = getattr(self, "_browser", None)
        if browser is not None and hasattr(browser, "_inspect_card"):
            browser._inspect_card(self)
        if not bool(getattr(browser, "_uses_integrated_preview", False)):
            self._preview_timer.start()
        if callable(getattr(self, "_live_preview_callback", None)):
            self._live_preview_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._preview_timer.stop()
        self._live_preview_timer.stop()
        self._end_live_preview()
        self._anim_timer.stop()
        self._anim_phase = 0.0
        self._close_preview_popup()
        self.update()
        super().leaveEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        label = "Remove from Favorites" if self._favorite else "Add to Favorites"
        favorite_action = menu.addAction(label)
        chosen = menu.exec(event.globalPos())
        if chosen is favorite_action:
            browser = getattr(self, "_browser", None)
            if browser is not None and hasattr(browser, "_toggle_favorite"):
                browser._toggle_favorite(self)
            event.accept()
            return
        super().contextMenuEvent(event)

    @property
    def category(self) -> str:
        return self._category

    @property
    def pack(self) -> str:
        return self._pack

    @property
    def preset_id(self) -> str:
        return self._preset_id

    @property
    def is_favorite(self) -> bool:
        return self._favorite

    @property
    def is_recent(self) -> bool:
        return self._recent_rank > 0

    def set_library_state(self, *, favorite: bool = False, recent_rank: int = 0) -> None:
        self._favorite = bool(favorite)
        self._recent_rank = int(recent_rank or 0)
        self.update()

    def _notify_preset_used(self) -> None:
        browser = getattr(self, "_browser", None)
        if browser is not None and hasattr(browser, "_mark_recent"):
            browser._mark_recent(self)

    def _tick_preview_animation(self) -> None:
        self._anim_phase = (self._anim_phase + 0.075) % 1.0
        self.update()

    def set_window_move_suspended(self, suspended: bool) -> None:
        suspended = bool(suspended)
        if suspended == self._window_move_suspended:
            return
        self._window_move_suspended = suspended
        if suspended:
            self._preview_timer.stop()
            self._live_preview_timer.stop()
            self._end_live_preview()
            self._anim_timer.stop()
            self._close_preview_popup()
            return
        if self._hovered:
            self._anim_timer.start()

    def _begin_live_preview(self) -> None:
        if self._window_move_suspended or not self._hovered or self._live_preview_active:
            return
        callback = getattr(self, "_live_preview_callback", None)
        if not callable(callback):
            return
        try:
            callback(
                self._preview_kind,
                _preset_payload_with_intensity(self._preview_payload, self._preview_intensity),
                self._label,
            )
            self._live_preview_active = True
        except Exception:
            self._live_preview_active = False

    def _end_live_preview(self) -> None:
        if not self._live_preview_active:
            return
        callback = getattr(self, "_live_preview_clear_callback", None)
        if callable(callback):
            try:
                callback()
            except Exception:
                pass
        self._live_preview_active = False

    def matches_filter(self, query: str, category: str) -> bool:
        cat = str(category or "All")
        if cat == "Favorites" and not self._favorite:
            return False
        if cat == "Recent" and not self.is_recent:
            return False
        if cat not in {"All", "Favorites", "Recent"} and self._category != cat:
            return False
        return _preset_query_matches(self._search_blob, query)

    def _close_preview_popup(self) -> None:
        popup = self._preview_popup
        self._preview_popup = None
        if popup is not None:
            popup.close()
            popup.deleteLater()

    def _preview_sample_pixmap(self) -> QPixmap | None:
        provider = getattr(self, "_preview_provider", None)
        if not callable(provider):
            return None
        try:
            pix = provider()
        except Exception:
            return None
        if isinstance(pix, QPixmap) and not pix.isNull():
            return pix
        return None

    def _show_preview_popup(self) -> None:
        if not self._hovered or not self.isVisible():
            return
        self._close_preview_popup()
        popup = QFrame(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        popup.setObjectName("PresetHoverPreview")
        popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        popup.setStyleSheet(
            "QFrame#PresetHoverPreview{background:#111421;border:1px solid #4F5B7C;border-radius:14px;}"
            "QLabel{background:transparent;color:#E8EAF4;}"
            "QLabel#PresetPreviewTitle{font-size:12px;font-weight:800;color:#FFFFFF;}"
            "QLabel#PresetPreviewMeta{font-size:10px;color:#A7ADC2;}"
            "QLabel#PresetPreviewDesc{font-size:10px;color:#D7DAE7;}"
        )
        lay = QVBoxLayout(popup)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        sample_pixmap = self._preview_sample_pixmap()
        swatch = None
        if sample_pixmap is None:
            cached = _render_static_preset_preview(
                colors=self._colors,
                kind=self._preview_kind,
                label=self._label,
                payload=self._preview_payload,
                tags=self._tags,
                category=self._category,
                preset_id=self._preset_id,
            )
            cached_label = QLabel()
            cached_label.setPixmap(cached)
            lay.addWidget(cached_label)
        else:
            swatch = _PresetPreviewSwatch(
                self._colors,
                kind=self._preview_kind,
                label=self._label,
                payload=self._preview_payload,
                tags=self._tags,
                category=self._category,
                sample_pixmap=sample_pixmap,
                intensity=self._preview_intensity,
                payload_with_intensity=_preset_payload_with_intensity,
            )
            lay.addWidget(swatch)
        title = QLabel(self._label)
        title.setObjectName("PresetPreviewTitle")
        title.setWordWrap(True)
        lay.addWidget(title)
        meta = QLabel(" / ".join(part for part in (self._pack, self._category, ", ".join(self._tags[:3])) if part))
        meta.setObjectName("PresetPreviewMeta")
        meta.setWordWrap(True)
        lay.addWidget(meta)
        if self._preview_badges:
            badges = QLabel("  ".join([*self._preview_badges, self._quality_badge]))
            badges.setObjectName("PresetPreviewMeta")
            badges.setStyleSheet("color:#DDE2FF;font-size:10px;font-weight:800;")
            badges.setWordWrap(True)
            lay.addWidget(badges)
        detail_lines = _preset_preview_details(self._preview_kind, self._preview_payload, self._tags)
        if detail_lines:
            details = QLabel("\n".join(detail_lines))
            details.setObjectName("PresetPreviewMeta")
            details.setWordWrap(True)
            lay.addWidget(details)
        if swatch is not None and (
            "effect" in self._preview_kind
            or "title" in self._preview_kind
            or "transition" in self._preview_kind
        ):
            intensity_row = QWidget()
            intensity_lay = QHBoxLayout(intensity_row)
            intensity_lay.setContentsMargins(0, 2, 0, 0)
            intensity_lay.setSpacing(6)
            intensity_label = QLabel(f"{int(self._preview_intensity * 100)}%")
            intensity_label.setObjectName("PresetPreviewMeta")
            intensity_label.setMinimumWidth(34)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 125)
            slider.setValue(int(round(self._preview_intensity * 100)))
            slider.setFixedHeight(18)
            slider.setToolTip("Preview/apply intensity")

            def _set_intensity(value: int) -> None:
                self._preview_intensity = max(0.0, min(1.25, float(value) / 100.0))
                intensity_label.setText(f"{int(self._preview_intensity * 100)}%")
                swatch.set_intensity(self._preview_intensity)

            slider.valueChanged.connect(_set_intensity)
            intensity_lay.addWidget(QLabel("Intensity"))
            intensity_lay.addWidget(slider, 1)
            intensity_lay.addWidget(intensity_label)
            lay.addWidget(intensity_row)
        if self._description:
            desc = QLabel(self._description)
            desc.setObjectName("PresetPreviewDesc")
            desc.setWordWrap(True)
            desc.setMaximumWidth(240)
            lay.addWidget(desc)
        if self._drag_hint:
            hint = QLabel(self._drag_hint)
            hint.setObjectName("PresetPreviewMeta")
            hint.setWordWrap(True)
            lay.addWidget(hint)
        popup.adjustSize()
        pos = self.mapToGlobal(QPoint(self.width() + 10, -4))
        popup.move(pos)
        popup.show()
        self._preview_popup = popup

    def _drag_pixmap(self) -> QPixmap:
        pix = QPixmap(190, 66)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRect(0, 0, pix.width() - 1, pix.height() - 1)
        painter.setPen(QPen(QColor(255, 255, 255, 72), 1))
        painter.setBrush(QColor(17, 20, 33, 226))
        painter.drawRoundedRect(rect, 16, 16)

        tile = self.grab()
        painter.drawPixmap(8, 8, tile)
        font = QFont(painter.font())
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        title_rect = QRect(68, 11, 112, 18)
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(self._label, Qt.TextElideMode.ElideRight, title_rect.width()),
        )
        font.setPixelSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#A7ADC2"))
        badge_text = " ".join(getattr(self, "_preview_badges", [])[:2]) or self._category
        painter.drawText(QRect(68, 32, 112, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, badge_text)
        if self._drag_hint:
            painter.drawText(
                QRect(68, 46, 112, 14),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(self._drag_hint, Qt.TextElideMode.ElideRight, 112),
            )
        if self._quality_badge:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#60E6C5") if self._quality_badge == "OK" else QColor("#FFB85B"))
            painter.drawRoundedRect(QRect(10, 46, 26, 12), 6, 6)
            font.setPixelSize(7)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("#101421"))
            painter.drawText(QRect(10, 46, 26, 12), Qt.AlignmentFlag.AlignCenter, self._quality_badge)
        painter.end()
        return pix

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(1, 1, -1, -1)
        radius = 7
        browser = getattr(self, "_browser", None)
        inspected = str(getattr(browser, "_inspected_preset_id", "") or "") == str(self._preset_id)
        active = bool(self._hovered or inspected)

        base = QLinearGradient(r.topLeft(), r.bottomRight())
        if active:
            base.setColorAt(0.0, QColor("#464B52"))
            base.setColorAt(0.50, QColor("#343940"))
            base.setColorAt(1.0, QColor("#24282E"))
        else:
            base.setColorAt(0.0, QColor("#373C43"))
            base.setColorAt(0.52, QColor("#2B3036"))
            base.setColorAt(1.0, QColor("#202328"))
        painter.setPen(QPen(QColor(224, 229, 238, 116 if active else 54), 1))
        painter.setBrush(QBrush(base))
        painter.drawRoundedRect(r, radius, radius)

        shade = QLinearGradient(0, r.top(), 0, r.bottom())
        shade.setColorAt(0.0, QColor(255, 255, 255, 34 if active else 18))
        shade.setColorAt(0.28, QColor(255, 255, 255, 5 if active else 2))
        shade.setColorAt(1.0, QColor(0, 0, 0, 50 if active else 62))
        painter.setBrush(QBrush(shade))
        painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
        if active:
            accent = QLinearGradient(r.topLeft(), r.topRight())
            accent.setColorAt(0.0, QColor(185, 198, 214, 16))
            accent.setColorAt(0.45, QColor(213, 221, 232, 82))
            accent.setColorAt(1.0, QColor(185, 198, 214, 18))
            painter.setPen(QPen(QBrush(accent), 1.0))
            painter.drawLine(r.left() + 6, r.top() + 2, r.right() - 6, r.top() + 2)
            painter.setPen(QPen(QColor(174, 187, 204, 78), 1.0))
            painter.drawRoundedRect(r.adjusted(2, 2, -2, -2), radius - 2, radius - 2)

        painter.setPen(QPen(QColor(0, 0, 0, 92 if active else 82), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx = r.center().x() + 1
        cy = r.center().y() + 1
        s = min(r.width(), r.height())
        self._paint_preset_tile_shape(painter, cx, cy, s)

        icon_color = QColor("#F2F5FA") if active else QColor("#D8DDE5")
        painter.setPen(QPen(icon_color, 1.85 if active else 1.55, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        cx = r.center().x()
        cy = r.center().y()
        self._paint_preset_tile_shape(painter, cx, cy, s)

        if self._favorite or self._recent_rank > 0:
            badge_rect = QRect(r.right() - 10, r.top() + 4, 6, 6)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(245, 245, 245, 210) if self._favorite else QColor(165, 170, 180, 185))
            painter.drawEllipse(badge_rect)

        painter.end()

    def _paint_preset_tile_shape(self, painter: QPainter, cx: int, cy: int, s: int) -> None:
        role = str(getattr(self, "_visual_role", "") or "")
        payload = dict(getattr(self, "_preview_payload", {}) or {})
        label_text = " ".join(
            (
                str(getattr(self, "_label", "") or ""),
                str(getattr(self, "_preview_kind", "") or ""),
                str(getattr(self, "_category", "") or ""),
                " ".join(str(tag) for tag in getattr(self, "_tags", ()) or ()),
            )
        ).casefold()
        u = max(18, int(s * 0.62))
        left = cx - u // 2
        top = cy - u // 2
        box = QRect(left, top, u, u)

        if role == "title":
            try:
                x_norm = float(payload.get("x_norm", 0.5) or 0.5)
                y_norm = float(payload.get("y_norm", 0.5) or 0.5)
            except Exception:
                x_norm, y_norm = 0.5, 0.5
            title_frame = box.adjusted(2, 4, -2, -4)
            painter.drawRoundedRect(title_frame, 4, 4)
            if "lower" in label_text or y_norm > 0.72:
                bar = QRect(title_frame.left() + 3, title_frame.bottom() - int(u * .24), int(u * .64), int(u * .16))
                painter.drawRoundedRect(bar, 3, 3)
                painter.drawLine(QPoint(bar.left(), bar.top() - 3), QPoint(bar.right() + 4, bar.top() - 3))
            elif "corner" in label_text or "tag" in label_text or x_norm > 0.72 or x_norm < 0.25:
                tag = QRect(title_frame.right() - int(u * .36), title_frame.top() + 3, int(u * .30), int(u * .22))
                if x_norm < 0.25:
                    tag.moveLeft(title_frame.left() + 3)
                painter.drawRoundedRect(tag, 3, 3)
            elif "type" in label_text:
                painter.drawLine(QPoint(cx + int(u * .18), top + 6), QPoint(cx + int(u * .18), top + u - 6))
            elif any(word in label_text for word in ("kinetic", "beat", "pop")):
                painter.drawLine(QPoint(cx - int(u * .30), cy), QPoint(cx - int(u * .18), cy))
                painter.drawLine(QPoint(cx + int(u * .18), cy), QPoint(cx + int(u * .30), cy))
            font = painter.font()
            font.setPixelSize(max(12, int(s * 0.28)))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, "T")
        elif role == "transition":
            ttype = str(
                payload.get("transition_out_type")
                or payload.get("type")
                or getattr(self, "_label", "")
                or ""
            ).casefold()
            if "zoom" in ttype:
                painter.drawEllipse(QPoint(cx, cy), int(u * .30), int(u * .30))
                painter.drawEllipse(QPoint(cx, cy), int(u * .15), int(u * .15))
                painter.drawLine(QPoint(cx + int(u * .21), cy + int(u * .21)), QPoint(cx + int(u * .36), cy + int(u * .36)))
            elif "slide" in ttype or "wipe" in ttype:
                painter.drawRoundedRect(QRect(left + 1, cy - int(u * .22), int(u * .40), int(u * .44)), 4, 4)
                painter.drawRoundedRect(QRect(cx, cy - int(u * .22), int(u * .40), int(u * .44)), 4, 4)
                sweep = cx - int(u * .05)
                painter.drawLine(QPoint(sweep, cy - int(u * .32)), QPoint(sweep, cy + int(u * .32)))
                painter.drawLine(QPoint(left + int(u * .18), cy), QPoint(left + int(u * .72), cy))
                painter.drawLine(QPoint(left + int(u * .62), cy - 5), QPoint(left + int(u * .72), cy))
                painter.drawLine(QPoint(left + int(u * .62), cy + 5), QPoint(left + int(u * .72), cy))
            elif any(word in ttype for word in ("black", "white", "dip", "fade")):
                painter.drawRoundedRect(QRect(left + 2, cy - int(u * .24), int(u * .38), int(u * .48)), 4, 4)
                painter.drawRoundedRect(QRect(cx + int(u * .03), cy - int(u * .24), int(u * .38), int(u * .48)), 4, 4)
                painter.drawRoundedRect(QRect(cx - int(u * .10), cy - int(u * .28), int(u * .20), int(u * .56)), 4, 4)
                painter.drawLine(QPoint(cx - int(u * .24), cy - int(u * .22)), QPoint(cx + int(u * .24), cy + int(u * .22)))
                painter.drawLine(QPoint(cx - int(u * .24), cy + int(u * .22)), QPoint(cx + int(u * .24), cy - int(u * .22)))
            else:
                a = QRect(left, cy - int(u * .22), int(u * .44), int(u * .44))
                b = QRect(cx + int(u * .02), cy - int(u * .22), int(u * .44), int(u * .44))
                painter.drawRoundedRect(a, 4, 4)
                painter.drawRoundedRect(b, 4, 4)
                painter.drawLine(QPoint(cx, cy - int(u * .32)), QPoint(cx, cy + int(u * .32)))
                painter.drawLine(QPoint(cx - int(u * .18), cy), QPoint(cx + int(u * .18), cy))
        elif role == "workflow":
            for idx, width in enumerate((0.72, 0.52, 0.64)):
                y = top + 4 + idx * int(u * .26)
                x = left + 3 + idx * 3
                painter.drawRoundedRect(QRect(x, y, int(u * width), max(4, int(u * .14))), 3, 3)
            painter.drawLine(QPoint(cx + int(u * .25), top + 2), QPoint(cx + int(u * .25), top + u - 3))
        elif role == "sticker":
            bubble = QPainterPath()
            bubble.addRoundedRect(QRectF(box.adjusted(2, 5, -2, -9)), 7, 7)
            bubble.moveTo(cx - 4, top + u - 10)
            bubble.lineTo(cx - 9, top + u - 2)
            bubble.lineTo(cx + 4, top + u - 9)
            painter.drawPath(bubble)
        elif role == "actor":
            painter.drawEllipse(QPoint(cx, top + int(u * .32)), int(u * .16), int(u * .16))
            painter.drawRoundedRect(QRect(cx - int(u * .24), cy, int(u * .48), int(u * .30)), 7, 7)
        elif role == "audio":
            path = QPainterPath()
            path.moveTo(left + 2, cy)
            for idx in range(1, 7):
                x = left + 2 + idx * int((u - 4) / 6)
                amp = int(u * (0.16 if idx % 2 else 0.28))
                path.lineTo(x, cy - amp)
                path.lineTo(x + int((u - 4) / 12), cy + amp)
            painter.drawPath(path)
        elif role == "key":
            diamond = QPolygon([
                QPoint(cx, top + 2),
                QPoint(left + u - 2, cy),
                QPoint(cx, top + u - 2),
                QPoint(left + 2, cy),
            ])
            painter.drawPolygon(diamond)
            painter.drawRoundedRect(QRect(cx - int(u * .13), cy - int(u * .13), int(u * .26), int(u * .26)), 3, 3)
        elif role == "node":
            points = [
                QPoint(left + int(u * .22), top + int(u * .26)),
                QPoint(left + int(u * .76), top + int(u * .30)),
                QPoint(left + int(u * .38), top + int(u * .74)),
            ]
            painter.drawLine(points[0], points[1])
            painter.drawLine(points[0], points[2])
            painter.drawLine(points[1], points[2])
            for point in points:
                painter.drawEllipse(point, max(2, int(u * .08)), max(2, int(u * .08)))
        elif role == "color":
            painter.drawEllipse(QPoint(cx, cy), int(u * .27), int(u * .27))
            for angle in (0, 120, 240):
                rad = math.radians(angle)
                point = QPoint(cx + int(math.cos(rad) * u * .16), cy + int(math.sin(rad) * u * .16))
                painter.drawEllipse(point, max(2, int(u * .055)), max(2, int(u * .055)))
        elif role == "speed":
            for idx in (0, 1):
                x = left + int(u * (.25 + idx * .22))
                painter.drawLine(QPoint(x, top + int(u * .24)), QPoint(x + int(u * .18), cy))
                painter.drawLine(QPoint(x + int(u * .18), cy), QPoint(x, top + int(u * .76)))
        elif role == "blur":
            painter.drawRoundedRect(box.adjusted(2, 6, -8, -6), 5, 5)
            painter.drawRoundedRect(box.adjusted(8, 4, -2, -8), 5, 5)
            painter.drawEllipse(QPoint(cx, cy), int(u * .18), int(u * .18))
        elif role == "motion":
            path = QPainterPath()
            path.moveTo(left + 2, top + u - 4)
            path.cubicTo(left + int(u * .30), top + 1, left + int(u * .62), top + u - 7, left + u - 2, top + 5)
            painter.drawPath(path)
            painter.drawEllipse(QPoint(left + 2, top + u - 4), 2, 2)
            painter.drawEllipse(QPoint(left + u - 2, top + 5), 2, 2)
        elif role == "clip":
            painter.drawRoundedRect(box.adjusted(2, 5, -2, -5), 4, 4)
            painter.drawLine(QPoint(left + 2, cy), QPoint(left + u - 2, cy))
            painter.drawLine(QPoint(cx, top + 5), QPoint(cx, top + u - 5))
        else:
            for off in (-0.18, 0.0, 0.18):
                x = cx + int(s * off)
                painter.drawLine(QPoint(x, cy - int(s * .22)), QPoint(x, cy + int(s * .22)))
                painter.drawEllipse(QPoint(x, cy + int(s * (off * .7))), int(s * .055), int(s * .055))


def _preset_category_from_tags(tags, fallback: str) -> str:
    text = " ".join(str(tag).casefold() for tag in (tags or ()))
    if any(word in text for word in ("screen", "capture", "tutorial", "hotkey", "ui")):
        return "Screen"
    if any(word in text for word in ("character", "anime", "live2d", "actor")):
        return "Character"
    if any(word in text for word in ("product", "food", "review", "commerce")):
        return "Product"
    if any(word in text for word in ("short", "social", "meme", "stream", "ranking")):
        return "Social"
    if any(word in text for word in ("clean", "denoise", "noise", "dialogue", "podcast")):
        return "Cleanup"
    if "motion" in text:
        return "Motion"
    if "caption" in text or "subtitle" in text:
        return "Caption"
    return fallback


def _preset_pack_from_tags(tags, fallback: str = "Studio") -> str:
    text = " ".join(str(tag).casefold() for tag in (tags or ()))
    if any(word in text for word in ("game", "screen", "capture", "tutorial", "hotkey", "ui")):
        return "Game Capture"
    if any(word in text for word in ("short", "social", "meme", "stream", "ranking", "creator")):
        return "Creator"
    if any(word in text for word in ("product", "food", "review", "commerce", "demo")):
        return "Product"
    if any(word in text for word in ("clean", "denoise", "noise", "dialogue", "podcast", "audio")):
        return "Cleanup"
    if any(word in text for word in ("anime", "actor", "character", "live2d", "spine")):
        return "Actor"
    return fallback



class EffectPresetCard(_StudioPresetTile):
    """Compact draggable card backed by app.preset_library effect presets."""

    activated = Signal(object)

    def __init__(
        self,
        preset,
        *,
        preview_provider=None,
        live_preview_callback=None,
        live_preview_clear_callback=None,
    ) -> None:
        self._preset = preset
        self._press_pos: QPoint | None = None
        self._dragging = False
        tags = tuple(getattr(preset, "tags", ()) or ())
        description = str(getattr(preset, "description", "") or "")
        default_effect_label = tr("veditor.effect_preset.default")
        category = _preset_category_from_tags(tags, default_effect_label)
        tag_text = ", ".join(tags[:3])
        tip = f"{preset.name}\n{description}"
        if tag_text:
            tip += f"\n{tag_text}"
        tip += (
            f"\n{tr('veditor.effect_preset.tooltip.click')}"
            f"\n{tr('veditor.effect_preset.tooltip.drag')}"
        )
        super().__init__(
            str(preset.name),
            _tile_badge(str(preset.name), "FX"),
            palette_seed=f"effect:{getattr(preset, 'id', preset.name)}",
            tooltip=tip,
            description=description,
            category=category,
            tags=tags,
            drag_hint=tr("veditor.effect_preset.drag_hint"),
            preset_id=f"effect:{getattr(preset, 'id', preset.name)}",
            pack=_preset_pack_from_tags(tags, "Studio FX"),
            preview_kind="effect",
            preview_payload=dict(getattr(preset, "payload", {}) or {}),
            preview_provider=preview_provider,
            live_preview_callback=live_preview_callback,
            live_preview_clear_callback=live_preview_clear_callback,
        )

    def _start_drag(self) -> None:
        self._end_live_preview()
        import json
        drag_payload = _preset_payload_with_intensity(
            dict(getattr(self._preset, "payload", {}) or {}),
            getattr(self, "_preview_intensity", 1.0),
        )
        drag_payload["__preset_meta"] = {
            "id": str(getattr(self._preset, "id", "") or ""),
            "name": str(getattr(self._preset, "name", "") or "Effect"),
            "kind": "effect",
        }
        payload = json.dumps(drag_payload, ensure_ascii=False)
        mime = QMimeData()
        mime.setData(EFFECT_PRESET_MIME_TYPE, payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self._drag_pixmap())
        drag.setHotSpot(QPoint(_PRESET_TILE // 2, _PRESET_TILE // 2))
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self._notify_preset_used()
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._press_pos = event.position().toPoint()
        self._dragging = False
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_pos is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        distance = (event.position().toPoint() - self._press_pos).manhattanLength()
        if distance >= max(4, QApplication.startDragDistance()):
            self._dragging = True
            self._start_drag()
            self._press_pos = None
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None and not self._dragging:
            self._notify_preset_used()
            self.activated.emit(self._preset)
            self._press_pos = None
            event.accept()
            return
        self._press_pos = None
        self._dragging = False
        super().mouseReleaseEvent(event)


class EffectsPresetPanel(QWidget):
    """Visible library surface for reusable clip-level effect presets."""

    preset_activated = Signal(object)

    def __init__(
        self,
        *,
        preview_provider=None,
        live_preview_callback=None,
        live_preview_clear_callback=None,
        save_current_callback=None,
        import_pack_callback=None,
        export_pack_callback=None,
        manage_pack_callback=None,
        qa_callback=None,
        auto_template_callback=None,
        template_composer_callback=None,
        cache_callback=None,
        visual_qa_callback=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._preview_provider = preview_provider
        self._live_preview_callback = live_preview_callback
        self._live_preview_clear_callback = live_preview_clear_callback
        self._save_current_callback = save_current_callback
        self._import_pack_callback = import_pack_callback
        self._export_pack_callback = export_pack_callback
        self._manage_pack_callback = manage_pack_callback
        self._qa_callback = qa_callback
        self._auto_template_callback = auto_template_callback
        self._template_composer_callback = template_composer_callback
        self._cache_callback = cache_callback
        self._visual_qa_callback = visual_qa_callback
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(5)
        self.refresh_library()

    def _clear(self) -> None:
        while self._root.count():
            item = self._root.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _make_action_button(self, icon_name: str, text: str, callback) -> QToolButton:
        btn = QToolButton(self)
        btn.setFixedSize(34, 30)
        btn.setIcon(app_icon(icon_name))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            "QToolButton{background:#15181D;border:1px solid #30363D;border-radius:6px;color:#E8EAF4;}"
            "QToolButton:hover{background:#20252B;border-color:#68717E;}"
            "QToolButton:pressed{background:#111316;border-color:#E1E5EC;}"
        )
        if callback is not None:
            btn.clicked.connect(callback)
        return btn

    def _make_actions_menu_button(self, actions: list[tuple[str, str, object]]) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("PresetToolsMenuButton")
        btn.setFixedSize(28, 26)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setText("")
        btn.setAccessibleName("Preset tools")
        btn.setToolTip("Preset tools")
        btn.setIcon(app_icon("layers", size=13, color="#E5E8EF"))
        btn.setIconSize(icon_size(13))
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setStyleSheet(
            "QToolButton#PresetToolsMenuButton{background:#15181D;border:1px solid #30363D;border-radius:6px;color:#F1F3F7;padding:0px;}"
            "QToolButton#PresetToolsMenuButton:hover{background:#20252B;border-color:#68717E;}"
            "QToolButton#PresetToolsMenuButton::menu-indicator{image:none;width:0px;}"
        )
        menu = QMenu(btn)
        menu.setStyleSheet(
            "QMenu{background:#111316;border:1px solid #30363D;border-radius:7px;color:#F1F3F7;padding:5px;}"
            "QMenu::item{padding:6px 24px 6px 8px;border-radius:5px;}"
            "QMenu::item:selected{background:#20252B;color:#FFFFFF;}"
        )
        for icon_name, text, callback in actions:
            action = menu.addAction(app_icon(icon_name, size=14, color="#F1F3F7"), text)
            if callback is not None:
                action.triggered.connect(callback)
        btn.setMenu(menu)
        return btn

    def refresh_library(self) -> None:
        self._clear()
        tool_actions: list[tuple[str, str, object]] = []
        if self._save_current_callback is not None:
            tool_actions.append(("save", "Save selected clip as effect preset", self._save_current_callback))
        if self._import_pack_callback is not None:
            tool_actions.append(("folder", "Import preset pack", self._import_pack_callback))
        if self._export_pack_callback is not None:
            tool_actions.append(("export", "Export user preset pack", self._export_pack_callback))
        if self._manage_pack_callback is not None:
            tool_actions.append(("layers", "Manage preset packs", self._manage_pack_callback))
        if self._qa_callback is not None:
            tool_actions.append(("scope", "Run preset QA report", self._qa_callback))
        if self._auto_template_callback is not None:
            tool_actions.append(("spark", "Apply one-click preset plan", self._auto_template_callback))
        if self._template_composer_callback is not None:
            tool_actions.append(("nest", "Open Template Composer", self._template_composer_callback))
        if self._cache_callback is not None:
            tool_actions.append(("proxy", "Manage preset preview cache", self._cache_callback))
        if self._visual_qa_callback is not None:
            tool_actions.append(("camera", "Open visual QA viewer", self._visual_qa_callback))
        extra_controls: list[QWidget] = []
        if tool_actions:
            extra_controls.append(self._make_actions_menu_button(tool_actions))

        try:
            from app.preset_library import presets_by_kind
            presets = presets_by_kind("effect")
        except Exception:
            presets = []
        cards: list[QWidget] = []
        for idx, preset in enumerate(presets):
            card = EffectPresetCard(
                preset,
                preview_provider=self._preview_provider,
                live_preview_callback=self._live_preview_callback,
                live_preview_clear_callback=self._live_preview_clear_callback,
            )
            card.activated.connect(self.preset_activated.emit)
            cards.append(card)
        if not presets:
            empty = QLabel("No effect presets", self)
            empty.setStyleSheet("color:#777; font-size:10px;")
            cards.append(empty)
        self._root.addWidget(_PresetBrowser(
            cards,
            max_height=226,
            placeholder=tr("veditor.preset.search.effects"),
            extra_controls=extra_controls,
            details_builder=_preset_preview_details,
            parent=self,
        ))


class WorkflowPresetCard(_StudioPresetTile):
    """Compact card for template/caption/sticker/motion library presets."""

    activated = Signal(object)

    def __init__(
        self,
        preset,
        *,
        preview_provider=None,
        live_preview_callback=None,
        live_preview_clear_callback=None,
    ) -> None:
        self._preset = preset
        self._press_pos: QPoint | None = None
        self._dragging = False
        tags = tuple(getattr(preset, "tags", ()) or ())
        description = str(getattr(preset, "description", "") or "")
        tag_text = ", ".join(tags[:3])
        tip = f"{preset.name}\n{description}"
        if tag_text:
            tip += f"\n{tag_text}"
        kind = str(getattr(preset, "kind", "preset")).replace("_", " ").upper()
        badge = {
            "TEMPLATE": "TMP",
            "CAPTION STYLE": "CAP",
            "STICKER": "STK",
            "MOTION": "MOT",
        }.get(kind, kind[:3] or "PRE")
        super().__init__(
            str(preset.name),
            badge,
            palette_seed=f"workflow:{getattr(preset, 'id', preset.name)}",
            tooltip=tip,
            description=description,
            category=_preset_category_from_tags(tags, kind.title()),
            tags=tags,
            drag_hint="Click or drag to timeline",
            preset_id=f"workflow:{getattr(preset, 'id', preset.name)}",
            pack=_preset_pack_from_tags(tags, "Workflow"),
            preview_kind=str(getattr(preset, "kind", "template") or "template"),
            preview_payload=dict(getattr(preset, "payload", {}) or {}),
            preview_provider=preview_provider,
            live_preview_callback=live_preview_callback,
            live_preview_clear_callback=live_preview_clear_callback,
        )

    def _start_drag(self, event: QMouseEvent) -> None:
        import json

        payload = json.dumps(self._preset.to_dict(), ensure_ascii=False)
        mime = QMimeData()
        mime.setData(EDITOR_PRESET_MIME_TYPE, payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self._drag_pixmap())
        drag.setHotSpot(QPoint(_PRESET_TILE // 2, _PRESET_TILE // 2))
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self._notify_preset_used()
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._press_pos = event.position().toPoint()
        self._dragging = False
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self._press_pos is None:
            return
        dist = (event.position().toPoint() - self._press_pos).manhattanLength()
        if dist < QApplication.startDragDistance():
            return
        self._dragging = True
        self._start_drag(event)
        self._press_pos = None
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if not self._dragging:
            self._notify_preset_used()
            self.activated.emit(self._preset)
        self._press_pos = None
        self._dragging = False
        event.accept()


class WorkflowPresetPanel(QWidget):
    """Visible surface for one-click templates and motion/caption assets."""

    preset_activated = Signal(object)

    def __init__(
        self,
        *,
        preview_provider=None,
        live_preview_callback=None,
        live_preview_clear_callback=None,
        kinds: set[str] | None = None,
        max_height: int = 226,
        placeholder: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._preview_provider = preview_provider
        self._live_preview_callback = live_preview_callback
        self._live_preview_clear_callback = live_preview_clear_callback
        self._kinds = set(kinds or {"template", "caption_style", "sticker", "motion"})
        self._max_height = int(max_height)
        self._placeholder = str(placeholder or tr("veditor.preset.search.workflows"))
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)
        self.refresh_library()

    def _clear(self) -> None:
        while self._root.count():
            item = self._root.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def refresh_library(self) -> None:
        self._clear()
        try:
            from app.preset_library import load_editor_presets
            presets = [
                p for p in load_editor_presets()
                if p.kind in self._kinds
            ]
        except Exception:
            presets = []
        cards: list[QWidget] = []
        for idx, preset in enumerate(presets[:32]):
            card = WorkflowPresetCard(
                preset,
                preview_provider=self._preview_provider,
                live_preview_callback=self._live_preview_callback,
                live_preview_clear_callback=self._live_preview_clear_callback,
            )
            card.activated.connect(self.preset_activated.emit)
            cards.append(card)
        if not presets:
            empty = QLabel("No workflow presets", self)
            empty.setStyleSheet("color:#777; font-size:10px;")
            cards.append(empty)
        self._root.addWidget(_PresetBrowser(
            cards,
            max_height=self._max_height,
            placeholder=self._placeholder,
            details_builder=_preset_preview_details,
            parent=self,
        ))


# ---------------------------------------------------------------------------
#  Title animation preset cards (drag-source for typography lane)
# ---------------------------------------------------------------------------


class TitlePresetCard(_StudioPresetTile):
    """Draggable 130횞80 px card for a single title animation preset.

    Dragging onto a TrackRow (or TextLaneRow) and dropping creates a
    TextClip with the preset's text, style, and animation settings baked in.
    MIME type: ``TITLE_PRESET_MIME_TYPE``.
    """

    def __init__(
        self,
        preset: dict,
        *,
        preview_provider=None,
        live_preview_callback=None,
        live_preview_clear_callback=None,
    ) -> None:
        self._preset = preset
        tags = tuple(str(tag) for tag in preset.get("tags", ()) if str(tag).strip())
        description = str(preset.get("desc", "") or "")
        super().__init__(
            str(preset["name"]),
            "Aa",
            palette_seed=f"title:{preset.get('id', preset['name'])}",
            tooltip=f"{preset['name']}\n{preset['desc']}\nDrag onto timeline to add",
            description=description,
            category="Title",
            tags=tags,
            drag_hint="Drag onto timeline",
            preset_id=f"title:{preset.get('id', preset['name'])}",
            pack=_preset_pack_from_tags(tags, "Titles"),
            preview_kind="title",
            preview_payload=dict(preset or {}),
            preview_provider=preview_provider,
            live_preview_callback=live_preview_callback,
            live_preview_clear_callback=live_preview_clear_callback,
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._end_live_preview()
        import json
        payload = json.dumps(self._preset)
        mime = QMimeData()
        mime.setData(TITLE_PRESET_MIME_TYPE, payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self._drag_pixmap())
        drag.setHotSpot(QPoint(_PRESET_TILE // 2, _PRESET_TILE // 2))
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self._notify_preset_used()
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class TitlePresetsPanel(QWidget):
    """Left-dock panel showing a 2-column grid of TitlePresetCards."""

    def __init__(
        self,
        *,
        preview_provider=None,
        live_preview_callback=None,
        live_preview_clear_callback=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._preview_provider = preview_provider
        self._live_preview_callback = live_preview_callback
        self._live_preview_clear_callback = live_preview_clear_callback

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)
        self.refresh_library()

    def _clear(self) -> None:
        while self._root.count():
            item = self._root.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def refresh_library(self) -> None:
        self._clear()
        presets = list(TITLE_PRESETS)
        try:
            from app.preset_library import presets_by_kind, title_drag_payload
            presets.extend(
                title_drag_payload(preset)
                for preset in presets_by_kind("title")
            )
        except Exception:
            pass
        cards: list[QWidget] = []
        for idx, preset in enumerate(presets):
            cards.append(TitlePresetCard(
                preset,
                preview_provider=self._preview_provider,
                live_preview_callback=self._live_preview_callback,
                live_preview_clear_callback=self._live_preview_clear_callback,
            ))
        self._root.addWidget(_PresetBrowser(
            cards,
            max_height=180,
            placeholder=tr("veditor.preset.search.titles"),
            details_builder=_preset_preview_details,
            parent=self,
        ))


# ---------------------------------------------------------------------------
#  DaVinci-style Transition cards
# ---------------------------------------------------------------------------


class TransitionCard(_StudioPresetTile):
    """Draggable 90횞70 px card for a single clip-boundary transition type.

    Dragging the card onto a TrackRow and releasing near a clip's right
    edge sets ``clip.transition_out_type`` and ``clip.transition_out_ms``
    via the ``TRANSITION_MIME_TYPE`` MIME type.

    ``ttype`` is one of: ``"dissolve"``, ``"fade_black"``, ``"fade_white"``,
    ``"dip_white"``.
    """

    _NAMES = {
        "dissolve":   "Cross Dissolve",
        "fade_black": "Fade to Black",
        "fade_white": "Fade to White",
        "dip_white":  "Dip to White",
        "slide_left": "Slide Left",
        "wipe_left":  "Wipe Left",
        "zoom_in":    "Zoom In",
        "zoom_out":   "Zoom Out",
    }

    _SHORT_NAMES = {
        "dissolve":   "Cross",
        "fade_black": "Black",
        "fade_white": "White",
        "dip_white":  "Dip",
        "slide_left": "Slide",
        "wipe_left":  "Wipe",
        "zoom_in":    "Zoom In",
        "zoom_out":   "Zoom Out",
    }

    def __init__(
        self,
        ttype: str,
        default_ms: int = 500,
        *,
        preview_provider=None,
        live_preview_callback=None,
        live_preview_clear_callback=None,
    ) -> None:
        self._ttype = ttype
        self._default_ms = default_ms
        badge = {
            "dissolve": "X",
            "fade_black": "BLK",
            "fade_white": "WHT",
            "dip_white": "DIP",
            "slide_left": "SLD",
            "wipe_left": "WIP",
            "zoom_in": "Z+",
            "zoom_out": "Z-",
        }.get(ttype, "TR")
        super().__init__(
            self._SHORT_NAMES.get(ttype, ttype),
            badge,
            palette_seed=f"transition:{ttype}",
            tooltip=(
                f"{self._NAMES.get(ttype, ttype)}\n"
                "Drag onto a clip's right edge to apply"
            ),
            description=f"{self._NAMES.get(ttype, ttype)} transition for clip boundaries.",
            category="Transition",
            tags=(ttype.replace("_", " "),),
            drag_hint="Drag to clip edge",
            preset_id=f"transition:{ttype}",
            pack="Transitions",
            preview_kind="transition",
            preview_payload={"transition_out_type": ttype, "transition_out_ms": default_ms},
            preview_provider=preview_provider,
            live_preview_callback=live_preview_callback,
            live_preview_clear_callback=live_preview_clear_callback,
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._end_live_preview()
        import json
        payload = json.dumps({"type": self._ttype, "ms": self._default_ms})
        mime = QMimeData()
        mime.setData(TRANSITION_MIME_TYPE, payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self._drag_pixmap())
        drag.setHotSpot(QPoint(_PRESET_TILE // 2, _PRESET_TILE // 2))
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self._notify_preset_used()
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class _TransitionSwatch(QWidget):
    """Mini visual preview drawn for each transition type."""

    def __init__(self, ttype: str) -> None:
        super().__init__()
        self._ttype = ttype

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QBrush, QLinearGradient
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor("#141418"))

        ttype = self._ttype
        if ttype == "dissolve":
            # Left clip (blue-grey), right clip (blue-grey) with overlap gradient
            p.fillRect(0, 0, w // 2, h, QColor("#2a3a4a"))
            p.fillRect(w // 2, 0, w - w // 2, h, QColor("#2a3a4a"))
            # Overlap dissolve gradient centre
            g = QLinearGradient(w // 4, 0, 3 * w // 4, 0)
            g.setColorAt(0.0, QColor(42, 58, 74, 0))
            g.setColorAt(0.5, QColor(180, 180, 220, 160))
            g.setColorAt(1.0, QColor(42, 58, 74, 0))
            p.fillRect(w // 4, 0, w // 2, h, QBrush(g))
            # Centre line
            pen = QPen(QColor(180, 180, 220, 200), 1)
            p.setPen(pen)
            p.drawLine(w // 2, 0, w // 2, h)

        elif ttype == "fade_black":
            p.fillRect(0, 0, w // 2, h, QColor("#2a3a4a"))
            g = QLinearGradient(w // 4, 0, w, 0)
            g.setColorAt(0.0, QColor(0, 0, 0, 0))
            g.setColorAt(1.0, QColor(0, 0, 0, 255))
            p.fillRect(0, 0, w, h, QBrush(g))

        elif ttype in ("fade_white", "dip_white"):
            p.fillRect(0, 0, w // 2, h, QColor("#2a3a4a"))
            g = QLinearGradient(w // 4, 0, w, 0)
            g.setColorAt(0.0, QColor(255, 255, 255, 0))
            g.setColorAt(1.0, QColor(255, 255, 255, 255))
            p.fillRect(0, 0, w, h, QBrush(g))

        # Border
        pen = QPen(QColor("#3a3a4a"), 1)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, w - 1, h - 1)


class TransitionsPanel(QWidget):
    """Left-dock panel showing a grid of TransitionCards + a duration slider.

    The duration slider sets the default duration that gets baked into the
    MIME payload when a card is dragged. The current value is shown in the
    label "Default length: 500ms".
    """

    _CARD_TYPES = [
        ("dissolve",   "Cross Dissolve"),
        ("fade_black", "Fade to Black"),
        ("fade_white", "Fade to White"),
        ("dip_white",  "Dip to White"),
        ("slide_left", "Slide Left"),
        ("wipe_left",  "Wipe Left"),
        ("zoom_in",    "Zoom In"),
        ("zoom_out",   "Zoom Out"),
    ]

    def __init__(
        self,
        *,
        preview_provider=None,
        live_preview_callback=None,
        live_preview_clear_callback=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._default_ms = 500
        self._preview_provider = preview_provider
        self._live_preview_callback = live_preview_callback
        self._live_preview_clear_callback = live_preview_clear_callback

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 6)
        root.setSpacing(4)

        # Card grid ??2 columns
        self._cards: list[TransitionCard] = []
        for idx, (ttype, _label) in enumerate(self._CARD_TYPES):
            card = TransitionCard(
                ttype,
                self._default_ms,
                preview_provider=self._preview_provider,
                live_preview_callback=self._live_preview_callback,
                live_preview_clear_callback=self._live_preview_clear_callback,
            )
            self._cards.append(card)
        root.addWidget(_PresetBrowser(
            list(self._cards),
            max_height=126,
            placeholder=tr("veditor.preset.search.transitions"),
            details_builder=_preset_preview_details,
            parent=self,
        ))

        # Duration slider
        dur_row = QHBoxLayout()
        dur_row.setContentsMargins(8, 0, 8, 0)
        dur_row.setSpacing(4)
        self._dur_label = QLabel(tr("veditor.transition.default_duration", ms=self._default_ms), self)
        self._dur_label.setStyleSheet("color: #9a9aa8; font-size: 9px;")
        dur_row.addWidget(self._dur_label)
        root.addLayout(dur_row)

        self._dur_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._dur_slider.setRange(100, 3000)
        self._dur_slider.setSingleStep(50)
        self._dur_slider.setPageStep(100)
        self._dur_slider.setValue(self._default_ms)
        self._dur_slider.setToolTip(tr("veditor.transition.default_duration.tooltip"))
        self._dur_slider.valueChanged.connect(self._on_duration_changed)
        self._dur_slider.setStyleSheet("margin-left:8px;margin-right:8px;")
        root.addWidget(self._dur_slider)

    def _on_duration_changed(self, value: int) -> None:
        # Round to nearest 50 ms for readability
        snapped = round(value / 50) * 50
        self._default_ms = snapped
        self._dur_label.setText(tr("veditor.transition.default_duration", ms=snapped))
        for card in self._cards:
            card._default_ms = snapped
            card._preview_payload["transition_out_ms"] = snapped
