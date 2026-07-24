from __future__ import annotations

import os
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_segmentation_setup_reports_missing_models_without_downloading(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TIGERSTUDIO_SEGMENTATION_MODEL_ROOT", str(tmp_path))
    from app.motion_designer.segmentation_setup import (
        BIREFNET_PROVIDER_ID,
        segmentation_install_plan,
        segmentation_provider_status,
        segmentation_setup_status,
    )

    status = segmentation_setup_status()
    birefnet = segmentation_provider_status(BIREFNET_PROVIDER_ID)
    plan = segmentation_install_plan()

    assert status["available"] is False
    assert birefnet["setup_needed"] is True
    assert birefnet["model_path"].startswith(str(tmp_path))
    assert plan["requires_user_consent"] is True
    assert plan["command"]
    assert plan["target_root"] == str(tmp_path)
    assert not list(tmp_path.glob("**/*"))


def test_auto_segmentation_marks_legacy_fallback_when_ai_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TIGERSTUDIO_SEGMENTATION_MODEL_ROOT", str(tmp_path))
    from app.motion_designer.semantic_segmentation import segment_image

    rgb = np.full((80, 120, 3), 18, dtype=np.uint8)
    rgb[15:70, 35:90] = (220, 80, 45)
    alpha = np.full((80, 120), 255, dtype=np.uint8)

    result = segment_image(rgb, alpha, mode="auto", max_elements=2)

    assert result.diagnostics["legacy_fallback"] is True
    assert result.diagnostics["warnings"]
    assert result.provider in {"grabcut_border_seed", "border_color_distance"}


def test_layer_extraction_panel_exposes_install_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TIGERSTUDIO_SEGMENTATION_MODEL_ROOT", str(tmp_path))
    from PySide6.QtWidgets import QApplication

    from app.motion_designer.ui.layer_extraction_panel import LayerExtractionPanel

    app = QApplication.instance() or QApplication([])
    panel = LayerExtractionPanel()

    assert panel.segmentation.currentData() == "auto"
    assert "not installed" in panel.segmentation.currentText().lower()
    assert panel.install_button.isHidden() is False
    assert panel.options()["segmentation_setup_ready"] is False
    assert "Legacy Basic" in panel.segmentation.itemText(3)
    panel.close()
    app.processEvents()
