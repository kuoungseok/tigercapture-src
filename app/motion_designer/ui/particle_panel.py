from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QLineEdit, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
)

from app.motion_designer.particles import PARTICLE_SOURCE_KIND
from app.motion_designer.schema import MotionLayer


class ParticlePanel(QWidget):
    source_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionParticlePanel")
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("MotionParticleScroll")
        self.scroll.setWidgetResizable(True)
        content = QWidget(self.scroll)
        content.setObjectName("MotionParticleContent")
        self.form = QFormLayout(content)
        self.form.setContentsMargins(8, 8, 8, 8)
        self.form.setSpacing(6)

        self.emitter_kind = self._combo(("point", "box", "circle", "path"))
        self.birth_rate = self._double(0, 2000, 1)
        self.burst_count = self._int(0, 20000)
        self.lifetime = self._double(1, 60000, 25)
        self.max_particles = self._int(0, 20000)
        self.speed = self._double(-5000, 5000, 5)
        self.spread = self._double(0, 360, 1)
        self.gravity_y = self._double(-5000, 5000, 5)
        self.turbulence = self._double(0, 2000, 1)
        self.shape = self._combo(("circle", "square", "triangle", "sprite"))
        self.size_start = self._double(0, 2000, 1)
        self.size_end = self._double(0, 2000, 1)
        self.opacity_start = self._double(0, 1, .05)
        self.opacity_end = self._double(0, 1, .05)
        self.color_start = QLineEdit(content)
        self.color_end = QLineEdit(content)
        self.seed = self._int(-2147483647, 2147483647)
        self.blend = self._combo(("normal", "add", "screen"))
        for label, control in (
            ("Emitter", self.emitter_kind), ("Birth / sec", self.birth_rate),
            ("Burst", self.burst_count), ("Lifetime (ms)", self.lifetime),
            ("Particle Limit", self.max_particles), ("Speed", self.speed),
            ("Spread", self.spread), ("Gravity Y", self.gravity_y),
            ("Turbulence", self.turbulence), ("Shape", self.shape),
            ("Start Size", self.size_start), ("End Size", self.size_end),
            ("Start Opacity", self.opacity_start), ("End Opacity", self.opacity_end),
            ("Start Color", self.color_start), ("End Color", self.color_end),
            ("Seed", self.seed), ("Blend", self.blend),
        ):
            self.form.addRow(label, control)
        self.scroll.setWidget(content)
        root.addWidget(self.scroll)

        for combo in (self.emitter_kind, self.shape, self.blend):
            combo.currentTextChanged.connect(self._emit)
        for spin in (
            self.birth_rate, self.burst_count, self.lifetime, self.max_particles,
            self.speed, self.spread, self.gravity_y, self.turbulence,
            self.size_start, self.size_end, self.opacity_start, self.opacity_end, self.seed,
        ):
            spin.valueChanged.connect(self._emit)
        self.color_start.editingFinished.connect(self._emit)
        self.color_end.editingFinished.connect(self._emit)
        self.setEnabled(False)

    def _combo(self, items) -> QComboBox:
        control = QComboBox(self)
        control.addItems(items)
        return control

    def _double(self, minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox(self)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(3)
        return control

    def _int(self, minimum: int, maximum: int) -> QSpinBox:
        control = QSpinBox(self)
        control.setRange(minimum, maximum)
        return control

    @staticmethod
    def _mapping(value) -> dict:
        return dict(value) if isinstance(value, dict) else {}

    def set_layer(self, layer: MotionLayer | None) -> None:
        active = bool(layer and layer.layer_type == PARTICLE_SOURCE_KIND)
        self.setEnabled(active)
        if not active or layer is None:
            return
        self._loading = True
        params = layer.source.params
        emitter = self._mapping(params.get("emitter"))
        velocity = self._mapping(params.get("velocity"))
        gravity = list(params.get("gravity") or [0.0, 0.0])
        turbulence = self._mapping(params.get("turbulence"))
        particle = self._mapping(params.get("particle"))
        bursts = list(params.get("bursts") or [])
        first_burst = self._mapping(bursts[0]) if bursts else {}
        values = {
            self.emitter_kind: str(emitter.get("kind") or "point"),
            self.birth_rate: float(params.get("birth_rate", 0.0)),
            self.burst_count: int(first_burst.get("count", 0) or 0),
            self.lifetime: float(params.get("lifetime_ms", 1000.0)),
            self.max_particles: int(params.get("max_particles", 2000) or 0),
            self.speed: float(velocity.get("speed", 0.0)),
            self.spread: float(velocity.get("spread_deg", 0.0)),
            self.gravity_y: float(gravity[1] if len(gravity) > 1 else 0.0),
            self.turbulence: float(turbulence.get("strength", 0.0)),
            self.shape: str(particle.get("shape") or "circle"),
            self.size_start: float(particle.get("size_start", 16.0)),
            self.size_end: float(particle.get("size_end", 0.0)),
            self.opacity_start: float(particle.get("opacity_start", 1.0)),
            self.opacity_end: float(particle.get("opacity_end", 0.0)),
            self.seed: int(params.get("seed", 0) or 0),
            self.blend: layer.blend_mode,
        }
        for control, value in values.items():
            if isinstance(control, QComboBox):
                control.setCurrentText(str(value))
            else:
                control.setValue(value)
        self.color_start.setText(str(particle.get("color_start") or "#ffffff"))
        self.color_end.setText(str(particle.get("color_end") or "#ffffff00"))
        self._loading = False

    def _emit(self, *_args) -> None:
        if self._loading or not self.isEnabled():
            return
        self.source_changed.emit({
            "emitter": {"kind": self.emitter_kind.currentText()},
            "birth_rate": self.birth_rate.value(),
            "bursts": [{"time_ms": 0, "count": self.burst_count.value()}],
            "lifetime_ms": self.lifetime.value(),
            "max_particles": self.max_particles.value(),
            "velocity": {"speed": self.speed.value(), "spread_deg": self.spread.value()},
            "gravity": [0.0, self.gravity_y.value()],
            "turbulence": {"strength": self.turbulence.value()},
            "particle": {
                "shape": self.shape.currentText(), "size_start": self.size_start.value(),
                "size_end": self.size_end.value(), "opacity_start": self.opacity_start.value(),
                "opacity_end": self.opacity_end.value(), "color_start": self.color_start.text().strip(),
                "color_end": self.color_end.text().strip(),
            },
            "__blend_mode": self.blend.currentText(),
        })


__all__ = ["ParticlePanel"]
