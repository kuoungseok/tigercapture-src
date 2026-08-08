"""Canonical alpha renderer for Motion Designer particle layers."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPolygonF, QTransform

from app.motion_designer.particles import simulate_particles
from app.motion_designer.schema import MotionLayer
from app.motion_designer.source_frame import transparent_image
from app.motion_designer.vector_shapes import evaluate_source_param


def _qcolor(value: tuple[float, float, float, float]) -> QColor:
    return QColor.fromRgbF(*[max(0.0, min(1.0, float(item))) for item in value])


def render_particle(layer: MotionLayer, time_ms: float = 0.0, **_kwargs) -> QImage:
    params = layer.source.params
    width = max(1, int(evaluate_source_param(params, "width", time_ms, 1280)))
    height = max(1, int(evaluate_source_param(params, "height", time_ms, 720)))
    image = transparent_image(width, height)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    particle = evaluate_source_param(params, "particle", time_ms, {})
    particle = particle if isinstance(particle, dict) else {}
    shape = str(particle.get("shape") or "circle").lower()
    sprite_uri = str(particle.get("sprite_uri") or "")
    sprite = QImage(sprite_uri) if shape == "sprite" and Path(sprite_uri).is_file() else QImage()
    if layer.blend_mode == "add":
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
    elif layer.blend_mode == "screen":
        painter.setCompositionMode(QPainter.CompositionMode_Screen)
    for state in simulate_particles(layer, time_ms):
        if state.size <= 0.0 or state.opacity <= 0.0:
            continue
        painter.save()
        painter.setOpacity(state.opacity)
        painter.setTransform(QTransform().translate(*state.position).rotate(state.rotation_deg), combine=True)
        half = state.size * 0.5
        if not sprite.isNull():
            painter.drawImage(QRectF(-half, -half, state.size, state.size), sprite)
        else:
            painter.setPen(QColor(0, 0, 0, 0))
            painter.setBrush(_qcolor(state.color))
            if shape == "square":
                painter.drawRect(QRectF(-half, -half, state.size, state.size))
            elif shape == "triangle":
                painter.drawPolygon(QPolygonF([QPointF(0.0, -half), QPointF(half, half), QPointF(-half, half)]))
            else:
                painter.drawEllipse(QRectF(-half, -half, state.size, state.size))
        painter.restore()
    painter.end()
    return image


__all__ = ["render_particle"]
