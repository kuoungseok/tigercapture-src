from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFileDialog

from app.audio_tracks import AUDIO_EXTS, VIDEO_EXTS, is_audio_path, is_video_path
from app.image_media import IMAGE_EXTS, is_image_path
from app.icons import app_icon, icon_size
from app.style import COLOR_TEXT_TERTIARY


def _blank_preview_backing_pixmap(self) -> QPixmap:
        """Opaque backing used behind the GL preview.

        The OpenGL preview widget only covers the fitted video rectangle.  If
        the backing QLabel is merely cleared to a null pixmap, some Windows/Qt
        repaint paths can leave the old "Start your edit" card visible around
        a newly-loaded frame.  Paint a neutral dark backing instead so content
        transitions always erase stale placeholder pixels.
        """
        label = getattr(self, "_preview_label", None)
        try:
            w = max(1, int(label.width()))
            h = max(1, int(label.height()))
        except Exception:
            w, h = 1, 1
        pixmap_factory = None
        try:
            import app.video_editor_window as video_editor_window

            pixmap_factory = getattr(video_editor_window, "QPixmap", None)
        except Exception:
            pixmap_factory = None
        try:
            pm = pixmap_factory(w, h) if pixmap_factory is not None else QPixmap(w, h)
        except TypeError:
            pm = pixmap_factory() if pixmap_factory is not None else QPixmap()
        except Exception:
            pm = QPixmap(w, h)
        try:
            pm.fill(QColor("#07080F"))
        except Exception:
            pass
        return pm


def _draw_preview_placeholder(self, kind: str = "empty") -> QPixmap:
        size = self._preview_label.size()
        w = max(360, int(size.width() or 720))
        h = max(220, int(size.height() or 360))
        pm = QPixmap(w, h)
        pm.fill(Qt.GlobalColor.transparent)

        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0.0, QColor("#11121C"))
        bg.setColorAt(0.55, QColor("#06070C"))
        bg.setColorAt(1.0, QColor("#171321"))
        p.fillRect(0, 0, w, h, bg)

        card_w = min(660, max(420, int(w * 0.52)))
        card_h = 148
        card = QRect((w - card_w) // 2, (h - card_h) // 2, card_w, card_h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawRoundedRect(card.adjusted(-10, -8, 10, 12).translated(0, 10), 22, 22)
        p.setBrush(QColor(18, 20, 30, 218))
        p.drawRoundedRect(card, 18, 18)
        p.setPen(QPen(QColor("#34394B"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(card.adjusted(0, 0, -1, -1), 18, 18)

        accent = QColor("#5DCAA5") if kind == "audio" else (QColor("#7E6BFF") if kind == "template" else QColor("#E85D35"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(accent)
        icon_box = QRect(card.left() + 26, card.top() + 42, 58, 58)
        p.drawRoundedRect(icon_box, 16, 16)
        icon_name = "audio" if kind == "audio" else ("spark" if kind == "template" else "video")
        icon_pix = app_icon(icon_name, size=30, color="#FFFFFF").pixmap(icon_size(30))
        p.drawPixmap(
            icon_box.center().x() - icon_pix.width() // 2,
            icon_box.center().y() - icon_pix.height() // 2,
            icon_pix,
        )

        if kind == "audio":
            title = "Audio project loaded"
            body = "Audio can be edited now. Add video or actor media for preview."
        elif kind == "template":
            template_name = str(getattr(self, "_startup_template_name", "") or "Template")
            title = "Template ready"
            body = f"{template_name}\nImport media, then apply matching presets from the workflow library."
        else:
            title = "Start your edit"
            body = "Click here to import media, or drop video, audio, Spine, and Live2D assets."
        title_font = QFont("Noto Sans KR")
        if not title_font.exactMatch():
            title_font = QFont("Arial")
        title_font.setPixelSize(18)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QColor("#F2F0EA"))
        text_rect = card.adjusted(104, 34, -28, -78)
        title = QFontMetrics(title_font).elidedText(
            title,
            Qt.TextElideMode.ElideRight,
            max(80, text_rect.width()),
        )
        p.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

        body_font = QFont("Noto Sans KR")
        if not body_font.exactMatch():
            body_font = QFont("Arial")
        body_font.setPixelSize(11)
        body_font.setBold(False)
        p.setFont(body_font)
        p.setPen(QColor("#9AA0B5"))
        p.drawText(
            card.adjusted(104, 76, -28, -26),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            body,
        )

        chip_font = QFont(body_font)
        chip_font.setPixelSize(10)
        chip_font.setBold(True)
        p.setFont(chip_font)
        chips = ["Import Media", "Drop Files", "Media Pool"] if kind != "audio" else ["Add Video", "Open Mixer", "Export Audio"]
        x = card.left() + 104
        y = card.bottom() - 34
        for chip in chips:
            metrics = QFontMetrics(chip_font)
            chip_w = metrics.horizontalAdvance(chip) + 22
            chip_rect = QRect(x, y, chip_w, 22)
            p.setPen(QPen(QColor(255, 255, 255, 34), 1))
            p.setBrush(QColor(255, 255, 255, 18))
            p.drawRoundedRect(chip_rect, 11, 11)
            p.setPen(QColor("#E8EAF4"))
            p.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, chip)
            x += chip_w + 7
        p.end()
        return pm


def _set_preview_placeholder(self, kind: str = "empty") -> None:
        self._preview_placeholder_kind = kind
        self._preview_pixmap = None
        self._latest_preview_rgb = None
        self._preview_gl_frame_size = (0, 0)
        gl = getattr(self, "_preview_gl", None)
        if gl is not None and gl.isVisible():
            try:
                gl.hide()
            except Exception:
                pass
        self._preview_label.setText("")
        self._preview_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        self._preview_label.setPixmap(self._draw_preview_placeholder(kind))


def _clear_preview_placeholder(self) -> None:
        if not hasattr(self, "_preview_label"):
            return
        if getattr(self, "_preview_placeholder_kind", "") != "content":
            self._preview_placeholder_kind = "content"
        try:
            self._preview_label.setText("")
            self._preview_label.setPixmap(_blank_preview_backing_pixmap(self))
            self._preview_label.setStyleSheet(
                f"background-color: #07080F; color: {COLOR_TEXT_TERTIARY};"
            )
            self._preview_label.update()
            # The GL preview only covers the fitted video rect. Force the
            # backing QLabel to repaint immediately so an older placeholder
            # card cannot remain visible behind the smaller GL surface.
            self._preview_label.repaint()
        except Exception:
            pass


def _preview_has_visual_content(self) -> bool:
        return any(
            getattr(track, "source_path", None) is not None
            or bool(getattr(track, "clips", None) or [])
            for track in getattr(self, "_tracks", []) or []
        ) or any(
            bool(getattr(track, "clips", None) or [])
            for track in getattr(self, "_live2d_actor_tracks", []) or []
        ) or any(
            bool(getattr(track, "clips", None) or [])
            for track in getattr(self, "_spine_actor_tracks", []) or []
        ) or bool(
            getattr(self, "_ar_pbr_tracks", []) or []
        ) or bool(
            getattr(self, "_mmd_tracks", []) or []
        )


def _refresh_visual_preview_after_timeline_change(self) -> None:
        """Clear stale empty-preview art and show the current frame after visual media changes."""
        if not self._preview_has_visual_content():
            try:
                self._update_preview_placeholder()
            except Exception:
                pass
            return
        try:
            self._clear_preview_placeholder()
        except Exception:
            pass
        try:
            self._player.refresh_current_frame()
        except Exception:
            pass
        try:
            gl = getattr(self, "_preview_gl", None)
            if gl is not None:
                gl.show()
        except Exception:
            pass


def _update_preview_placeholder(self) -> None:
        """Flip preview between visual frame, sound-only hint, and empty hint."""
        has_visual = self._preview_has_visual_content()
        has_audio = any(track.is_loaded for track in self._audio_tracks)
        if has_visual:
            self._clear_preview_placeholder()
            return
        if has_audio:
            self._set_preview_placeholder("audio")
        elif getattr(self, "_startup_template_id", ""):
            self._set_preview_placeholder("template")
        else:
            self._set_preview_placeholder("empty")


def _import_media_from_empty_preview(self) -> None:
        all_exts = sorted(set(VIDEO_EXTS) | set(AUDIO_EXTS) | set(IMAGE_EXTS))
        filter_exts = " ".join(f"*{ext}" for ext in all_exts)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import media",
            str(Path.home() / "Videos"),
            f"Media files ({filter_exts});;All files (*.*)",
        )
        if not path:
            return
        media_path = Path(path)
        if hasattr(self, "_media_pool"):
            try:
                self._media_pool.add_path(media_path)
            except Exception:
                pass
        template_status_expected = (
            bool(getattr(self, "_startup_template_id", "") or "")
            and not bool(getattr(self, "_startup_template_applied", False))
        )
        if is_video_path(media_path):
            self._add_track_with_source(media_path)
            if not template_status_expected:
                self._flash_status(f"Imported video: {media_path.name}")
            return
        if is_image_path(media_path):
            try:
                from app.video_editor_media_import_controller import add_image_track_with_source

                add_image_track_with_source(self, media_path)
            except Exception:
                self._add_track_with_source(media_path)
            if not template_status_expected:
                self._flash_status(f"Imported image: {media_path.name}")
            return
        if is_audio_path(media_path):
            self._add_audio_track_with_source(media_path, open_editor=True)
            if not template_status_expected:
                self._flash_status(f"Imported audio: {media_path.name}")


def _active_renderable_clip_at_current_position(self) -> bool:
        try:
            pos = int(self._player.position()) if hasattr(self, "_player") else 0
        except Exception:
            pos = 0
        for track in getattr(self, "_tracks", []) or []:
            for clip in getattr(track, "clips", []) or []:
                if getattr(clip, "source_path", None) is None:
                    continue
                start = int(getattr(clip, "timeline_in_ms", 0) or 0)
                end = int(getattr(clip, "timeline_out_ms", 0) or 0)
                if start <= pos <= end:
                    return True
            if getattr(track, "source_path", None) is not None:
                start = int(getattr(track, "offset_ms", 0) or 0)
                end = start + int(getattr(track, "duration_ms", 0) or 0)
                if start <= pos <= end:
                    return True
        for collection_name in ("_live2d_actor_tracks", "_spine_actor_tracks"):
            for track in getattr(self, collection_name, []) or []:
                for clip in getattr(track, "clips", []) or []:
                    start = int(getattr(clip, "start_ms", 0) or 0)
                    duration = int(getattr(clip, "duration_ms", 0) or 0)
                    if duration <= 0:
                        end = int(getattr(clip, "end_ms", start) or start)
                    else:
                        end = start + duration
                    if start <= pos <= end:
                        return True
        return False
