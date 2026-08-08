"""Compact actor evidence widgets for the renewed editor Workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPolygon
from PySide6.QtWidgets import QSizePolicy, QWidget


def _clip_name(path: str) -> str:
    if not path:
        return "Live2D clip"
    try:
        return Path(path).name.replace(".model3.json", "")
    except Exception:
        return str(path)[-28:]


def _keys(value: Any) -> list[Any]:
    try:
        return list(value or [])
    except Exception:
        return []


class Live2DActorEvidenceCard(QWidget):
    """Real-state Live2D actor summary for catalog and QA screenshots."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._track: Any = None
        self._clip: Any = None
        self.setObjectName("Live2DActorEvidenceCard")
        self.setMinimumHeight(144)
        self.setMaximumHeight(164)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_clip(self, track: Any, clip: Any) -> None:
        self._track = track
        self._clip = clip
        self.update()

    def _key_rows(self) -> list[tuple[str, list[Any], QColor]]:
        clip = self._clip
        if clip is None:
            return []
        return [
            ("X", _keys(getattr(clip, "kf_pos_x", [])), QColor("#8FA0B4")),
            ("Y", _keys(getattr(clip, "kf_pos_y", [])), QColor("#839986")),
            ("Scale", _keys(getattr(clip, "kf_scale", [])), QColor("#A8967D")),
            ("Opacity", _keys(getattr(clip, "kf_opacity", [])), QColor("#9A8FA8")),
        ]

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(rect, QColor(255, 255, 255, 3))
        painter.setPen(QPen(QColor(178, 186, 202, 20), 1))
        painter.drawLine(rect.left() + 6, rect.top(), rect.right() - 6, rect.top())

        clip = self._clip
        track = self._track
        title_font = QFont("Segoe UI")
        title_font.setPixelSize(10)
        title_font.setWeight(QFont.Weight.DemiBold)
        body_font = QFont("Segoe UI")
        body_font.setPixelSize(8)
        body_font.setWeight(QFont.Weight.Medium)
        mono_font = QFont("Cascadia Mono")
        mono_font.setPixelSize(8)

        x = 11
        y = 15
        painter.setFont(title_font)
        painter.setPen(QColor("#DDE2EA"))
        painter.drawText(x, y, "Live2D actor keys")

        if clip is None:
            painter.setFont(body_font)
            painter.setPen(QColor("#88909B"))
            painter.drawText(x, y + 18, "No actor clip selected.")
            painter.end()
            return

        model_path = str(getattr(clip, "model_path", "") or "")
        track_label = str(getattr(track, "label", "") or "Live2D")
        try:
            from app.actor_loading_status import actor_clip_status, actor_loading_diagnostic_card

            status = actor_clip_status(clip)
            if str(status.get("status") or "") in {"error", "timeout", "cancelled"}:
                card = actor_loading_diagnostic_card(
                    "live2d",
                    str(status.get("path") or model_path),
                    status=str(status.get("status") or ""),
                    stage=str(status.get("status") or ""),
                    message=str(status.get("message") or ""),
                )
                painter.setFont(body_font)
                painter.setPen(QColor("#AEB5BF"))
                painter.drawText(x, y + 18, str(card.get("title") or "Live2D load diagnostic"))
                summary_rect = QRect(x, y + 29, max(120, rect.width() - 24), 34)
                painter.setPen(QColor("#D2B78A") if card.get("tone") == "warning" else QColor("#E08A96"))
                painter.drawText(summary_rect, Qt.TextFlag.TextWordWrap, str(card.get("summary") or "Actor load did not complete."))
                actions = [str(row) for row in list(card.get("actions") or []) if str(row)]
                painter.setPen(QColor("#8A929D"))
                action_y = y + 76
                for row in actions[:3]:
                    painter.drawText(QRect(x, action_y, max(120, rect.width() - 24), 18), Qt.TextFlag.TextWordWrap, f"- {row}")
                    action_y += 18
                painter.end()
                return
        except Exception:
            pass
        start_ms = int(getattr(clip, "start_ms", 0) or 0)
        duration_ms = max(1, int(getattr(clip, "duration_ms", 1) or 1))
        pos_x = float(getattr(clip, "pos_x", 0.5) or 0.0)
        pos_y = float(getattr(clip, "pos_y", 0.5) or 0.0)
        scale = float(getattr(clip, "scale", 1.0) or 1.0)
        opacity = float(getattr(clip, "opacity", 1.0) or 1.0)

        painter.setFont(body_font)
        painter.setPen(QColor("#AEB5BF"))
        painter.drawText(x, y + 18, f"{track_label} / {_clip_name(model_path)}")
        painter.drawText(x, y + 32, f"start {start_ms / 1000.0:.1f}s  duration {duration_ms / 1000.0:.1f}s")

        # Mini viewport marker uses the actual transform values without
        # pretending to render the model.
        viewport = QRect(rect.right() - 90, 14, 74, 52)
        painter.setPen(QPen(QColor(178, 186, 202, 22), 1))
        bg = QLinearGradient(viewport.topLeft(), viewport.bottomRight())
        bg.setColorAt(0.0, QColor("#17191D"))
        bg.setColorAt(1.0, QColor("#101114"))
        painter.setBrush(bg)
        painter.drawRoundedRect(viewport, 5, 5)
        actor_w = max(14, min(46, int(22 * scale)))
        actor_h = max(18, min(50, int(32 * scale)))
        ax = viewport.left() + 8 + int((viewport.width() - 16 - actor_w) * max(0.0, min(1.0, pos_x)))
        ay = viewport.top() + 5 + int((viewport.height() - 10 - actor_h) * max(0.0, min(1.0, pos_y)))
        painter.setBrush(QColor(158, 166, 178, int(62 + 130 * max(0.0, min(1.0, opacity)))))
        painter.setPen(QPen(QColor("#C8CDD5"), 1))
        painter.drawRoundedRect(QRect(ax, ay, actor_w, actor_h), 7, 7)
        painter.setPen(QColor("#767E89"))
        painter.setFont(mono_font)
        painter.drawText(viewport.adjusted(6, viewport.height() - 13, -6, -2), Qt.AlignmentFlag.AlignLeft, "transform")

        rail_left = x
        rail_top = 64
        rail_w = max(80, rect.width() - 128)
        rail_gap = 14
        painter.setFont(mono_font)
        for index, (label, keys, color) in enumerate(self._key_rows()):
            row_y = rail_top + index * rail_gap
            painter.setPen(QColor("#89919B"))
            painter.drawText(rail_left, row_y + 4, label)
            track_x = rail_left + 48
            painter.setPen(QPen(QColor(178, 186, 202, 28), 1))
            painter.drawLine(track_x, row_y, track_x + rail_w, row_y)
            painter.setPen(QPen(color, 1))
            painter.setBrush(color)
            for key in keys:
                try:
                    key_ms = int(getattr(key, "time_ms", 0) if not isinstance(key, dict) else key.get("time_ms", key.get("ms", 0)))
                except Exception:
                    key_ms = 0
                px = track_x + int(max(0.0, min(1.0, key_ms / duration_ms)) * rail_w)
                diamond = QPolygon([
                    QPoint(px, row_y - 4),
                    QPoint(px + 4, row_y),
                    QPoint(px, row_y + 4),
                    QPoint(px - 4, row_y),
                ])
                painter.drawPolygon(diamond)

        param_tracks = getattr(clip, "parameter_keyframes", None)
        param_count = len(param_tracks or {}) if isinstance(param_tracks, dict) else 0
        action_payload = getattr(clip, "action_keyframes", None)
        payload_count = len(action_payload or {}) if isinstance(action_payload, dict) else 0
        painter.setFont(body_font)
        painter.setPen(QColor("#8A929D"))
        painter.drawText(
            x,
            rect.bottom() - 10,
            f"keys {sum(len(keys) for _, keys, _ in self._key_rows())} / params {param_count} / payload {payload_count}",
        )
        painter.end()


class ArPbrEvidenceCard(QWidget):
    """Real-state AR/PBR placement summary for the Workbench."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._track: dict[str, Any] | None = None
        self.setObjectName("ArPbrEvidenceCard")
        self.setMinimumHeight(152)
        self.setMaximumHeight(182)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_track(self, track: dict[str, Any] | None) -> None:
        self._track = track if isinstance(track, dict) else None
        self.update()

    @staticmethod
    def _values(track: dict[str, Any]) -> tuple[list[float], list[float], list[float], list[float]]:
        transform = track.get("transform") if isinstance(track.get("transform"), dict) else {}
        placement = track.get("placement") if isinstance(track.get("placement"), dict) else {}
        position = list(transform.get("position") or [0.0, 0.0, 0.0])
        rotation = list(transform.get("rotation") or [0.0, 0.0, 0.0])
        scale = list(transform.get("scale") or [1.0, 1.0, 1.0])
        image_point = list(placement.get("image_point") or [0.5, 0.62])
        while len(position) < 3:
            position.append(0.0)
        while len(rotation) < 3:
            rotation.append(0.0)
        while len(scale) < 3:
            scale.append(scale[-1] if scale else 1.0)
        while len(image_point) < 2:
            image_point.append(0.5)
        return position[:3], rotation[:3], scale[:3], image_point[:2]

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(QPen(QColor(178, 186, 202, 22), 1))
        painter.setBrush(QColor(255, 255, 255, 6))
        painter.drawRoundedRect(rect, 7, 7)

        title_font = QFont("Segoe UI")
        title_font.setPixelSize(10)
        title_font.setWeight(QFont.Weight.DemiBold)
        body_font = QFont("Segoe UI")
        body_font.setPixelSize(8)
        body_font.setWeight(QFont.Weight.Medium)
        mono_font = QFont("Cascadia Mono")
        mono_font.setPixelSize(8)

        x = 11
        y = 17
        painter.setFont(title_font)
        painter.setPen(QColor("#EEF0F4"))
        painter.drawText(x, y, "3D / AR-PBR workspace")

        track = self._track
        if not track:
            painter.setFont(body_font)
            painter.setPen(QColor("#88909B"))
            painter.drawText(x, y + 18, "No 3D object selected.")
            painter.end()
            return

        asset_path = str(track.get("asset_path") or "")
        name = _clip_name(asset_path)
        position, rotation, scale, image_point = self._values(track)
        render = track.get("render") if isinstance(track.get("render"), dict) else {}
        lighting = render.get("lighting") if isinstance(render.get("lighting"), dict) else {}
        placement = track.get("placement") if isinstance(track.get("placement"), dict) else {}

        painter.setFont(body_font)
        painter.setPen(QColor("#AEB5BF"))
        painter.drawText(x, y + 18, name)
        painter.drawText(
            x,
            y + 32,
            f"{placement.get('mode', 'manual')} / {image_point[0]:.2f}, {image_point[1]:.2f}",
        )

        viewport = QRect(rect.right() - 100, 16, 84, 64)
        painter.setPen(QPen(QColor(178, 186, 202, 30), 1))
        bg = QLinearGradient(viewport.topLeft(), viewport.bottomRight())
        bg.setColorAt(0.0, QColor("#181A1E"))
        bg.setColorAt(1.0, QColor("#0F1013"))
        painter.setBrush(bg)
        painter.drawRoundedRect(viewport, 6, 6)
        cx = viewport.left() + int(max(0.0, min(1.0, image_point[0])) * viewport.width())
        cy = viewport.top() + int(max(0.0, min(1.0, image_point[1])) * viewport.height())
        radius = max(9, min(24, int(12 * max(0.4, min(2.4, sum(scale) / 3.0)))))
        painter.setPen(QPen(QColor("#C4CAD2"), 1))
        painter.setBrush(QColor(151, 158, 166, 126))
        painter.drawRoundedRect(QRect(cx - radius, cy - radius, radius * 2, radius * 2), 5, 5)
        painter.setPen(QPen(QColor("#9BA3AD"), 1))
        painter.drawLine(cx, cy, min(viewport.right() - 5, cx + radius + 16), cy - 9)
        painter.drawLine(cx, cy, max(viewport.left() + 5, cx - radius - 14), cy + 8)
        painter.setFont(mono_font)
        painter.setPen(QColor("#777F8A"))
        painter.drawText(viewport.adjusted(6, viewport.height() - 13, -6, -2), Qt.AlignmentFlag.AlignLeft, "gizmo")

        row_y = 70
        rows = [
            ("pos", position, QColor("#8FA0B4")),
            ("rot", rotation, QColor("#A8967D")),
            ("scale", scale, QColor("#839986")),
            (
                "light",
                [
                    float(lighting.get("ibl_exposure", 1.0) or 1.0),
                    float(lighting.get("direct_strength", 0.0) or 0.0),
                    float(lighting.get("shadow_strength", 0.0) or 0.0),
                ],
                QColor("#9A8FA8"),
            ),
        ]
        painter.setFont(mono_font)
        for idx, (label, values, color) in enumerate(rows):
            y_pos = row_y + idx * 17
            painter.setPen(QColor("#89919B"))
            painter.drawText(x, y_pos + 4, label)
            rail_x = x + 50
            rail_w = max(80, rect.width() - 146)
            painter.setPen(QPen(QColor(178, 186, 202, 28), 1))
            painter.drawLine(rail_x, y_pos, rail_x + rail_w, y_pos)
            painter.setBrush(color)
            painter.setPen(QPen(color, 1))
            for value_idx, value in enumerate(values[:3]):
                try:
                    v = float(value)
                except Exception:
                    v = 0.0
                normalized = 0.5 + max(-1.0, min(1.0, v / (360.0 if label == "rot" else 4.0))) * 0.44
                if label == "scale":
                    normalized = max(0.05, min(0.95, v / 4.0))
                px = rail_x + int(max(0.05, min(0.95, normalized)) * rail_w)
                painter.drawEllipse(px - 3, y_pos - 3, 6, 6)

        painter.setFont(body_font)
        painter.setPen(QColor("#8A929D"))
        painter.drawText(
            x,
            rect.bottom() - 12,
            f"{track.get('id', 'ar_pbr')} / shadow {bool(track.get('shadow_catcher', False))} / occlusion {bool(track.get('occlusion', False))}",
        )
        painter.end()
