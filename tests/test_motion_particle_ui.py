from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest

from app.motion_designer.particles import create_particle_layer
from app.motion_designer.ui.particle_panel import ParticlePanel


def test_particle_panel_edits_the_same_source_contract() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    layer = create_particle_layer(width=640, height=360)
    panel = ParticlePanel()
    panel.set_layer(layer)
    received = []
    panel.source_changed.connect(received.append)
    panel.emitter_kind.setCurrentText("box")
    panel.birth_rate.setValue(72)
    panel.shape.setCurrentText("triangle")
    assert received
    latest = received[-1]
    assert latest["emitter"]["kind"] == "box"
    assert latest["birth_rate"] == 72
    assert latest["particle"]["shape"] == "triangle"
    panel.close()
    app.processEvents()
