"""Timeline row widget for Spine actor clips."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QMimeData, QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
    QPolygon,
)
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox, QWidget

from app.style import studio_chrome_qss
from app.actor_loading_status import actor_clip_badge, actor_clip_status
from app.spine_editor.actor_track import SpineActorClip, SpineActorTrack
from app.timeline_ruler import TimelineRuler
from app.studio_theme import (
    STUDIO_ACTION_HI,
    STUDIO_PLAYHEAD,
    paint_studio_clip_block,
    paint_studio_clip_label,
    paint_studio_playhead,
)


SPINE_ACTOR_MIME = "application/x-spine-actor-new"
SPINE_MODEL_MIME = "application/x-spine-model"
SPINE_EXTS = frozenset({".skel", ".json", ".atlas"})
DEFAULT_SPINE_CLIP_MS = 6000

_BG          = QColor("#101010")
_CLIP        = QColor(52, 56, 54, 126)
_CLIP_SEL    = QColor(76, 79, 73, 154)
_CLIP_BORDER = QColor(157, 160, 150, 112)
_TEXT        = QColor("#E8EAEE")
_PLAYHEAD    = STUDIO_PLAYHEAD
_DROP        = QColor("#B8C0CA")
_TIMELINE_MARGIN = int(TimelineRuler.MARGIN)
_LABEL_W     = _TIMELINE_MARGIN
_HEADER_W    = _TIMELINE_MARGIN


def _default_spine_dir() -> str:
    return os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "resources", "spine_samples"
    ))


def _looks_like_spine_json(path: Path) -> bool:
    if path.name.lower().endswith(".skel.json"):
        return True
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:65536]
    except Exception:
        return False
    return (
        '"bones"' in head
        and ('"slots"' in head or '"skins"' in head)
        and ('"animations"' in head or '"skeleton"' in head)
    )


def _is_spine_candidate(path: str) -> bool:
    if not path:
        return False
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".skel" or suffix == ".atlas":
        return True
    if suffix == ".json":
        return _looks_like_spine_json(p)
    return False


def _resolve_skel_path(path: str) -> Path:
    p = Path(path)
    if p.suffix.lower() != ".atlas":
        return p
    candidates = [
        p.with_suffix(".skel"),
        p.with_suffix(".json"),
        p.with_name(p.stem + ".skel.json"),
    ]
    try:
        candidates.extend(sorted(p.parent.glob("*.skel")))
        candidates.extend(sorted(p.parent.glob("*.json")))
    except Exception:
        pass
    for c in candidates:
        if c.is_file() and _is_spine_candidate(str(c)):
            return c
    return p


def _base_name_for_pairing(skel_path: Path) -> str:
    name = skel_path.name
    lower = name.lower()
    if lower.endswith(".skel.json"):
        return name[:-len(".skel.json")]
    return skel_path.stem


def _find_atlas_path(input_path: Path, skel_path: Path) -> str:
    if input_path.suffix.lower() == ".atlas" and input_path.is_file():
        return str(input_path)
    base = _base_name_for_pairing(skel_path)
    candidates = [
        skel_path.parent / f"{base}.atlas",
        skel_path.with_suffix(".atlas"),
    ]
    if skel_path.name.lower().endswith(".skel.json"):
        candidates.append(skel_path.with_name(f"{base}.skel.atlas"))
    try:
        candidates.extend(sorted(skel_path.parent.glob("*.atlas")))
    except Exception:
        pass
    seen: set[str] = set()
    for c in candidates:
        key = str(c)
        if key in seen:
            continue
        seen.add(key)
        if c.is_file():
            return key
    return ""


def _find_texture_path(skel_path: Path) -> str:
    base = _base_name_for_pairing(skel_path)
    for ext in (".png", ".webp", ".jpg", ".jpeg"):
        candidate = skel_path.parent / f"{base}{ext}"
        if candidate.is_file():
            return str(candidate)
    return ""


class SpineActorLaneRow(QWidget):
    """Single horizontal lane in the timeline showing Spine actor clips."""

    HEADER_W = _HEADER_W
    TIMELINE_MARGIN = _TIMELINE_MARGIN

    clip_changed = Signal()
    clip_double_clicked = Signal(object)   # SpineActorClip

    def __init__(self, track: SpineActorTrack, parent=None):
        super().__init__(parent)
        self._track = track
        self._px_per_sec: float = 100.0
        self._playhead_ms: int = 0
        self._selected: Optional[SpineActorClip] = None
        self._drag_clip: Optional[SpineActorClip] = None
        self._drag_start_x: int = 0
        self._drag_orig_start: int = 0
        self._lane_index: int = 1
        self._drop_x: Optional[int] = None

        self.setFixedHeight(28)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

    @property
    def track(self) -> SpineActorTrack:
        return self._track

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(1.0, px)
        self.update()

    def set_playhead(self, ms: int) -> None:
        self._playhead_ms = ms
        self.update()

    def set_lane_index(self, index: int) -> None:
        lane = max(1, int(index))
        if lane == self._lane_index:
            return
        self._lane_index = lane
        self.update()

    def _preferred_width(self) -> int:
        span_ms = max((c.end_ms for c in self._track.clips), default=0)
        return max(300, _TIMELINE_MARGIN + int(span_ms / 1000.0 * self._px_per_sec) + 80)

    def _ms_to_x(self, ms: int) -> int:
        return _TIMELINE_MARGIN + int(ms / 1000.0 * self._px_per_sec)

    def _x_to_ms(self, x: float) -> int:
        return max(0, int((x - _TIMELINE_MARGIN) / self._px_per_sec * 1000))

    def _paintEvent_legacy(self, _event):
        p = QPainter(self)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, _BG)
        p.fillRect(0, 0, _LABEL_W, h, QColor("#151515"))
        p.setPen(QColor("#2B2B2B"))
        p.drawLine(_LABEL_W - 1, 0, _LABEL_W - 1, h)
        p.setPen(_TEXT)
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(4, h - 8, self._track.label)

        for clip in self._track.clips:
            x1 = self._ms_to_x(clip.start_ms)
            x2 = self._ms_to_x(clip.end_ms)
            cw = max(4, x2 - x1)
            fill = _CLIP_SEL if clip is self._selected else _CLIP
            p.fillRect(x1, 2, cw, h - 4, fill)
            p.setPen(QPen(_CLIP_BORDER, 1))
            p.drawRect(x1, 2, cw, h - 4)
            badge = actor_clip_badge(clip)
            if badge and cw > 30:
                text, color = badge
                bw = 28 if len(text) <= 3 else 36
                br = QRect(max(x1 + 4, x2 - bw - 4), 5, min(bw, cw - 8), 14)
                p.fillRect(br, QColor(color))
                p.setPen(QColor("#FFFFFF"))
                p.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
                p.drawText(br, Qt.AlignmentFlag.AlignCenter, text)
                msg = actor_clip_status(clip).get("message", "")
                if msg:
                    self.setToolTip(msg)

            if clip.skel_path:
                name = os.path.splitext(os.path.basename(clip.skel_path))[0]
                lbl = f"{name} / {clip.anim_name}" if clip.anim_name else name
            else:
                lbl = "Spine (double-click to set)"
            p.setPen(_TEXT)
            p.setFont(QFont("Segoe UI", 8))
            p.setClipRect(x1 + 3, 0, max(1, cw - 6), h)
            p.drawText(x1 + 3, h - 8, lbl)
            p.setClipping(False)

        if self._drop_x is not None:
            p.setPen(QPen(_DROP, 2))
            p.drawLine(self._drop_x, 1, self._drop_x, h - 1)

        px = self._ms_to_x(self._playhead_ms)
        p.setPen(QPen(_PLAYHEAD, 1))
        p.drawLine(px, 0, px, h)
        p.end()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, _BG)
        lane_rect = QRect(0, 0, _LABEL_W, h)
        lane_grad = QLinearGradient(lane_rect.topLeft(), lane_rect.bottomLeft())
        lane_grad.setColorAt(0.0, QColor("#171819"))
        lane_grad.setColorAt(1.0, QColor("#101111"))
        p.fillRect(lane_rect, lane_grad)
        p.setPen(QColor("#242424"))
        p.drawLine(_LABEL_W - 1, 0, _LABEL_W - 1, h)
        p.setPen(QColor(255, 255, 255, 14))
        p.drawLine(0, 0, _LABEL_W - 1, 0)
        tab_rect = QRect(14, 5, 86, max(18, h - 10))
        tab_grad = QLinearGradient(tab_rect.topLeft(), tab_rect.bottomLeft())
        tab_grad.setColorAt(0.0, QColor(255, 255, 255, 7))
        tab_grad.setColorAt(1.0, QColor(0, 0, 0, 10))
        p.setPen(QPen(QColor(255, 255, 255, 15), 1))
        p.setBrush(QBrush(tab_grad))
        p.drawRoundedRect(tab_rect, 3, 3)
        p.setPen(QPen(QColor(0, 0, 0, 38), 1))
        p.drawLine(tab_rect.right(), tab_rect.top() + 5, tab_rect.right(), tab_rect.bottom() - 5)
        label_font = QFont("Segoe UI Variable", 12)
        label_font.setWeight(QFont.Weight.Medium)
        p.setFont(label_font)
        p.setPen(QColor("#D8DADD") if self._selected is not None else QColor("#9A9A9A"))
        lane_index = max(1, int(getattr(self, "_lane_index", 1) or 1))
        p.drawText(tab_rect, Qt.AlignmentFlag.AlignCenter, f"S{lane_index}")
        role_font = QFont("Segoe UI Variable", 10)
        role_font.setWeight(QFont.Weight.Normal)
        p.setFont(role_font)
        p.setPen(QColor("#7E7E7E"))
        p.drawText(
            QRect(112, 6, _LABEL_W - 126, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Spine",
        )

        for clip in self._track.clips:
            x1 = self._ms_to_x(clip.start_ms)
            x2 = self._ms_to_x(clip.end_ms)
            cw = max(4, x2 - x1)
            clip_rect = QRect(x1, 3, cw, h - 6)
            fill = _CLIP_SEL if clip is self._selected else _CLIP
            paint_studio_clip_block(
                p,
                clip_rect,
                selected=clip is self._selected,
                active=clip is self._selected,
                fill=fill,
                highlight=STUDIO_ACTION_HI,
                edge=_CLIP_BORDER,
            )

            badge = actor_clip_badge(clip)
            if badge and cw > 30:
                text, color = badge
                bw = 28 if len(text) <= 3 else 36
                br = QRect(max(x1 + 5, x2 - bw - 5), 6, min(bw, cw - 10), 13)
                badge_color = QColor(color)
                badge_color.setAlpha(170)
                p.setPen(QPen(QColor(255, 255, 255, 32), 1))
                p.setBrush(badge_color)
                p.drawRoundedRect(br, 3, 3)
                p.setPen(QColor("#FFFFFF"))
                p.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
                p.drawText(br, Qt.AlignmentFlag.AlignCenter, text)
                msg = actor_clip_status(clip).get("message", "")
                if msg:
                    self.setToolTip(msg)

            if clip.skel_path:
                name = os.path.splitext(os.path.basename(clip.skel_path))[0]
                lbl = f"{name} / {clip.anim_name}" if clip.anim_name else name
            else:
                lbl = "Spine (double-click to set)"
            paint_studio_clip_label(p, clip_rect.adjusted(-2, -8, 0, 0), lbl)

            atlas_path = str(getattr(clip, "atlas_path", "") or "")
            texture_path = str(getattr(clip, "texture_path", "") or "")
            diagnostics = [
                bool(getattr(clip, "skel_path", "") or ""),
                bool(atlas_path),
                bool(texture_path),
                bool(getattr(clip, "anim_name", "") or ""),
            ]
            rail_left = clip_rect.left() + 8
            rail_right = min(clip_rect.right() - 8, rail_left + 84)
            rail_y = clip_rect.bottom() - 6
            p.setPen(QPen(QColor(48, 48, 48, 130), 1))
            p.drawLine(rail_left, rail_y, rail_right, rail_y)
            for idx, ready in enumerate(diagnostics):
                x = rail_left + idx * 18
                color = QColor("#A8A28F") if ready else QColor("#565A60")
                color.setAlpha(176 if ready else 132)
                p.setBrush(color)
                p.setPen(QPen(QColor(8, 8, 8, 130), 0.8))
                p.drawPolygon(QPolygon([
                    QPoint(x, rail_y - 3),
                    QPoint(x + 3, rail_y),
                    QPoint(x, rail_y + 3),
                    QPoint(x - 3, rail_y),
                ]))

        if self._drop_x is not None:
            drop = QColor(_DROP)
            drop.setAlpha(150)
            p.setPen(QPen(drop, 1.2))
            p.drawLine(self._drop_x, 1, self._drop_x, h - 1)

        px = self._ms_to_x(self._playhead_ms)
        paint_studio_playhead(p, px, 0, h, show_handle=False)
        p.end()

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            clip = self._clip_at(e.position().x())
            if clip:
                self.clip_double_clicked.emit(clip)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            clip = self._clip_at(e.position().x())
            self._selected = clip
            if clip:
                self._drag_clip = clip
                self._drag_start_x = int(e.position().x())
                self._drag_orig_start = clip.start_ms
            self.update()
        elif e.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(
                e.globalPosition().toPoint(),
                self._clip_at(e.position().x()),
                int(e.position().x()),
            )

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_clip and e.buttons() & Qt.MouseButton.LeftButton:
            dx = int(e.position().x()) - self._drag_start_x
            delta_ms = int(dx / self._px_per_sec * 1000)
            self._drag_clip.start_ms = max(0, self._drag_orig_start + delta_ms)
            self.update()
            self.clip_changed.emit()

    def mouseReleaseEvent(self, _event):
        self._drag_clip = None

    def dragEnterEvent(self, e: QDragEnterEvent):
        if self._accepts(e.mimeData()):
            self._drop_x = int(e.position().x())
            self.update()
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._accepts(e.mimeData()):
            self._drop_x = int(e.position().x())
            self.update()
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragLeaveEvent(self, _event):
        self._drop_x = None
        self.update()

    def dropEvent(self, e: QDropEvent):
        self._drop_x = None
        start_ms = self._x_to_ms(e.position().x())
        if e.mimeData().hasFormat(SPINE_ACTOR_MIME):
            self._create_clip("", start_ms)
            e.acceptProposedAction()
        else:
            path = self._model_path_from_mime(e.mimeData())
            if path:
                self._create_clip(path, start_ms)
                e.acceptProposedAction()
            else:
                e.ignore()
        self.update()

    @staticmethod
    def _accepts(mime: QMimeData) -> bool:
        if mime.hasFormat(SPINE_ACTOR_MIME) or mime.hasFormat(SPINE_MODEL_MIME):
            return True
        if mime.hasUrls():
            return any(_is_spine_candidate(u.toLocalFile()) for u in mime.urls())
        return False

    @staticmethod
    def _model_path_from_mime(mime: QMimeData) -> str:
        if mime.hasFormat(SPINE_MODEL_MIME):
            return bytes(mime.data(SPINE_MODEL_MIME)).decode("utf-8", errors="ignore")
        if mime.hasUrls():
            for u in mime.urls():
                p = u.toLocalFile()
                if _is_spine_candidate(p):
                    return p
        return ""

    def _clip_at(self, x: float) -> Optional[SpineActorClip]:
        for clip in self._track.clips:
            x1 = self._ms_to_x(clip.start_ms)
            x2 = max(x1 + 4, self._ms_to_x(clip.end_ms))
            if x1 <= x <= x2:
                return clip
        return None

    def _show_context_menu(
        self,
        gpos: QPoint,
        clip: Optional[SpineActorClip],
        click_x: int,
    ) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(studio_chrome_qss(""))
        add_act = menu.addAction("Add Spine clip...")
        status_act = menu.addAction("Show loading/QA status") if clip else None
        probe_act = menu.addAction("Run isolated render probe") if clip else None
        prerender_act = menu.addAction("Build prerender cache") if clip else None
        quarantine_act = menu.addAction("Quarantine as known failure") if clip else None
        open_folder_act = menu.addAction("Open model folder") if clip else None
        del_act = menu.addAction("Delete clip") if clip else None
        if clip and not getattr(clip, "skel_path", ""):
            for action in (status_act, probe_act, prerender_act, quarantine_act, open_folder_act):
                if action is not None:
                    action.setEnabled(False)
        act = menu.exec(gpos)
        if act == add_act:
            self._import_clip(self._x_to_ms(click_x))
        elif status_act and act == status_act and clip:
            self._show_clip_diagnostics(clip)
        elif probe_act and act == probe_act and clip:
            self._probe_clip(clip)
        elif prerender_act and act == prerender_act and clip:
            self._prerender_clip(clip)
        elif quarantine_act and act == quarantine_act and clip:
            self._quarantine_clip(clip)
        elif open_folder_act and act == open_folder_act and clip:
            self._open_clip_folder(clip)
        elif del_act and act == del_act and clip:
            self._track.clips.remove(clip)
            if self._selected is clip:
                self._selected = None
            self.update()
            self.clip_changed.emit()

    def _show_clip_diagnostics(self, clip: SpineActorClip) -> None:
        try:
            import json
            from app.actor_loading_cache import actor_loading_cache_report
            status = actor_clip_status(clip)
            report = actor_loading_cache_report()
            rows = [
                row for row in report.get("entries", []) or []
                if str(row.get("path", "")) in {str(getattr(clip, "skel_path", "")), str(status.get("path", ""))}
            ][:3]
            QMessageBox.information(
                self,
                "Spine Actor Diagnostics",
                json.dumps({"clip_status": status, "recent_cache_entries": rows}, ensure_ascii=False, indent=2, default=str),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Spine", f"Diagnostics failed:\n{exc}")

    def _probe_clip(self, clip: SpineActorClip) -> None:
        try:
            from app.actor_preview_frame_server import default_actor_preview_frame_server, write_actor_probe_report
            payload = default_actor_preview_frame_server().probe_frame("spine", clip.skel_path, width=320, height=320)
            out = write_actor_probe_report(Path("debugCapture") / "actor_probe_spine_clip.json", payload)
            QMessageBox.information(self, "Spine Probe", f"{payload.get('status', 'unknown')}\n{out}")
        except Exception as exc:
            QMessageBox.warning(self, "Spine Probe", str(exc))

    def _prerender_clip(self, clip: SpineActorClip) -> None:
        try:
            from app.actor_preview_frame_server import default_actor_preview_frame_server
            payload = default_actor_preview_frame_server().prerender_preview(
                "spine",
                clip.skel_path,
                width=360,
                height=360,
                duration_ms=max(1000, int(getattr(clip, "duration_ms", 1000) or 1000)),
                limit_frames=12,
            )
            QMessageBox.information(self, "Spine Prerender", f"{payload.get('status', 'unknown')}\nframes={payload.get('frame_count', 0)}")
        except Exception as exc:
            QMessageBox.warning(self, "Spine Prerender", str(exc))

    def _quarantine_clip(self, clip: SpineActorClip) -> None:
        try:
            from app.actor_known_failures import add_actor_known_failure
            entry = add_actor_known_failure(kind="spine", path=clip.skel_path)
            QMessageBox.information(self, "Spine", f"Known failure updated:\n{entry.get('id')}")
        except Exception as exc:
            QMessageBox.warning(self, "Spine", str(exc))

    def _open_clip_folder(self, clip: SpineActorClip) -> None:
        try:
            os.startfile(str(Path(clip.skel_path).parent))
        except Exception:
            pass

    def _import_clip(self, start_ms: int) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Spine file",
            _default_spine_dir(),
            "Spine Files (*.json *.skel.json *.skel *.atlas);;All Files (*.*)",
        )
        if path:
            self._create_clip(path, start_ms)

    def _create_clip(self, path: str, start_ms: int) -> None:
        if not path:
            clip = SpineActorClip(start_ms=start_ms, duration_ms=DEFAULT_SPINE_CLIP_MS)
            self._track.clips.append(clip)
            self._selected = clip
            self.update()
            self.clip_changed.emit()
            return

        input_path = Path(path)
        skel_path = _resolve_skel_path(path)
        if not skel_path.is_file() or not _is_spine_candidate(str(skel_path)):
            QMessageBox.warning(self, "Spine", f"Unsupported Spine file:\n{path}")
            return

        try:
            from app.spine_editor.spine_json_parser import load_spine_file
            skel = load_spine_file(str(skel_path))
        except Exception as e:
            QMessageBox.warning(self, "Spine", f"Failed to load Spine skeleton:\n{e}")
            return

        anim_name = ""
        duration_ms = DEFAULT_SPINE_CLIP_MS
        if skel.animations:
            keys = sorted(skel.animations.keys())
            for pref in ("idle", "Idle", "action", "walk", "run"):
                if pref in skel.animations:
                    anim_name = pref
                    break
            if not anim_name:
                for key in keys:
                    if "idle" in key.lower():
                        anim_name = key
                        break
            if not anim_name:
                anim_name = keys[0]
            duration_ms = max(
                DEFAULT_SPINE_CLIP_MS,
                int(skel.animations[anim_name].duration * 1000) + 100,
            )

        clip = SpineActorClip(
            skel_path=str(skel_path),
            atlas_path=_find_atlas_path(input_path, skel_path),
            texture_path=_find_texture_path(skel_path),
            anim_name=anim_name,
            start_ms=start_ms,
            duration_ms=duration_ms,
        )
        self._track.clips.append(clip)
        self._selected = clip
        self.update()
        self.clip_changed.emit()
