from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, Qt
import pytest

from app.motion_designer.schema import (
    AnimatedProperty, MotionComposition, MotionEffectRef, MotionLayer,
    MotionMaskRef, SourceRef,
)
from app.motion_designer.tracking_workflow import normalize_track_asset
from app.motion_designer.ui.window import MotionDesignerWindow
from app.motion_designer.audio_analysis import AudioAnalysisCache, AudioEnvelopeSample
from app.motion_designer.evaluator import evaluate_composition


@pytest.fixture(autouse=True)
def _stable_motion_ui_language():
    from app.i18n import current_language, set_language

    previous = current_language()
    set_language("en")
    yield
    set_language(previous)


def test_motion_designer_window_uses_controller_for_layer_and_undo() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=1280, height=720, duration_ms=3000))
    window._add_layer("shape")
    assert len(window.controller.composition.layers) == 1
    assert window.left_tabs.currentWidget() is window.inspector_tabs
    assert window.inspector_tabs.currentWidget() is window.vector
    assert window.timeline.slider.maximum() == 3000
    assert window.canvas.scene() is not None
    assert window.left_tabs.count() == 3
    assert window.umg.generate_button.text() == "Generate Widget Blueprint"
    assert window.unreal_link_dialog.windowTitle() == "Unreal Link"
    assert window.toolbar.unreal_link_button.text() == "Unreal Link"
    assert not window.toolbar.unreal_link_button.icon().isNull()
    assert window.toolbar.templates_button.text() == "Templates"
    assert window.project_tabs.count() == 3
    assert window.inspector_tabs.count() == 20
    assert window.inspector_tabs.indexOf(window.tracking) >= 0
    assert window.inspector_tabs.indexOf(window.puppet) >= 0
    assert window.inspector_tabs.indexOf(window.rig) >= 0
    assert window.inspector_tabs.tabText(1) == "Motion"
    assert window.inspector_tabs.tabText(2) == "Generator"
    assert window.inspector_tabs.tabText(3) == "Replicator"
    assert window.inspector_tabs.tabText(4) == "Image"
    assert window.inspector_tabs.tabText(13) == "VRM"
    assert window.inspector_tabs.tabText(14) == "Particles"
    assert window.inspector_tabs.tabText(15) == "Button"
    assert window.inspector_tabs.indexOf(window.ar_pbr) >= 0
    assert window.inspector_tabs.indexOf(window.actor) >= 0
    assert window.inspector_tabs.indexOf(window.mmd) >= 0
    assert not window.ai_dock.isVisibleTo(window)
    assert not window.toolbar.ai_action.isChecked()
    assert window.left_tabs.tabText(window.left_tabs.indexOf(window.library)) == "Add"
    assert window.library.templates_button.text() == "Templates"
    assert window.library.ai_button.text() == "Create with AI"
    assert window.library.apply_button.text() == "Add Text"
    assert "Animated titles" in window.library.items.item(0).text()
    assert window.timeline.graph_editor.isVisibleTo(window.timeline)
    source_id = window.controller.composition.layers[0].id
    window._select_layer(source_id)
    window.left_tabs.setCurrentWidget(window.library)
    window._select_layer(source_id)
    assert window.left_tabs.currentWidget() is window.inspector_tabs
    assert window.inspector_tabs.currentWidget() is window.vector
    window._add_behavior("spring")
    window._add_effect("glow")
    window._add_mask("ellipse")
    edited = window.controller.composition.layers[0]
    assert edited.behaviors[0].kind == "spring"
    assert edited.effects[0].kind == "glow"
    assert edited.masks[0].kind == "ellipse"
    duplicate_id = window.controller.duplicate_layer(source_id)
    assert duplicate_id != source_id
    assert len(window.controller.composition.layers) == 2
    window._select_layer(duplicate_id)
    window._delete_selected()
    assert [layer.id for layer in window.controller.composition.layers] == [source_id]
    window.controller.undo()
    assert len(window.controller.composition.layers) == 2
    window.controller.undo()
    assert len(window.controller.composition.layers) == 1
    window.controller.undo()
    assert len(window.controller.composition.layers[0].masks) == 0
    window.controller.undo()
    assert len(window.controller.composition.layers[0].effects) == 0
    window.controller.undo()
    assert len(window.controller.composition.layers[0].behaviors) == 0
    window.controller.undo()
    assert window.controller.composition.layers == []
    window.close()


def test_motion_designer_language_switch_retranslates_open_window() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(
        MotionComposition(width=960, height=540, duration_ms=1000),
    )

    assert window.toolbar.language_button.text() == "Language"
    assert window.inspector_tabs.tabText(0) == "Properties"
    assert len(window.toolbar.language_button.menu().actions()) == 6

    window.set_ui_language("ko", persist=False)
    assert window.windowTitle().startswith("모션 디자이너 -")
    assert window.toolbar.templates_button.text() == "템플릿"
    assert window.toolbar.unreal_link_button.text() == "언리얼 링크"
    assert window.toolbar.language_button.text() == "언어"
    assert window.inspector_tabs.tabText(0) == "속성"
    assert window.left_tabs.tabText(0) == "추가"
    assert window.library.templates_button.text() == "템플릿"

    window.set_ui_language("ja", persist=False)
    assert window.windowTitle().startswith("モーションデザイナー -")
    assert window.toolbar.templates_button.text() == "テンプレート"
    assert window.inspector_tabs.tabText(0) == "プロパティ"
    window.close()
    app.processEvents()


def test_filter_and_mask_parameter_diamonds_edit_current_local_keyframe() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    layer = MotionLayer(
        id="animated-layer",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={"width": 320, "height": 180},
        ),
        in_ms=200,
        out_ms=2000,
        effects=[
            MotionEffectRef(
                id="glow",
                kind="glow",
                params={"intensity": AnimatedProperty(default=0.7)},
            ),
        ],
        masks=[
            MotionMaskRef(
                id="mask",
                kind="ellipse",
                params={"feather": AnimatedProperty(default=0.0)},
            ),
        ],
    )
    window = MotionDesignerWindow(MotionComposition(
        width=640,
        height=360,
        duration_ms=2200,
        layers=[layer],
    ))
    window._select_layer(layer.id)
    window._set_time(700)

    effect_button = window.effects.keyframe_button("glow", "intensity")
    mask_button = window.masks.keyframe_button("mask", "feather")
    assert effect_button is not None
    assert mask_button is not None
    assert effect_button.isChecked() is False
    effect_button.click()
    mask_button = window.masks.keyframe_button("mask", "feather")
    assert mask_button is not None
    mask_button.click()
    app.processEvents()

    stored = window.controller.composition.layers[0]
    assert stored.effects[0].params["intensity"].keyframes[0].time_ms == 500
    assert stored.masks[0].params["feather"].keyframes[0].time_ms == 500
    assert window.effects.keyframe_button("glow", "intensity").isChecked()

    effect_control = window.effects.parameter_control("glow", "intensity")
    assert effect_control is not None
    effect_control.setValue(1.25)
    app.processEvents()
    stored = window.controller.composition.layers[0]
    assert stored.effects[0].params["intensity"].keyframes[0].value == 1.25
    assert len(stored.effects[0].params["intensity"].keyframes) == 1

    window.effects.keyframe_button("glow", "intensity").click()
    app.processEvents()
    assert (
        window.controller.composition.layers[0]
        .effects[0].params["intensity"].keyframes
        == []
    )
    window.close()
    app.processEvents()


def test_motion_effect_library_exposes_light_noise_and_stylize_controls() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(
        width=640,
        height=360,
        duration_ms=1000,
    ))
    window._add_layer("shape")
    layer_id = window.controller.composition.layers[0].id
    window._select_layer(layer_id)

    kinds = {
        window.effects.kind.itemText(index)
        for index in range(window.effects.kind.count())
    }
    assert {"drop_shadow", "light_sweep", "fractal_noise", "posterize", "craft_style"} <= kinds

    window._add_effect("fractal_noise")
    app.processEvents()
    effect = window.controller.composition.layers[0].effects[0]
    assert effect.kind == "fractal_noise"
    assert effect.params["octaves"].default == 4.0
    assert window.effects.parameter_control(effect.id, "amount") is not None
    assert window.effects.parameter_control(effect.id, "evolution") is not None

    window.close()
    app.processEvents()


def test_adjustment_layer_scope_controls_persist_selected_lower_layer() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    background = MotionLayer(
        id="background",
        name="Background",
        layer_type="shape",
        out_ms=1000,
    )
    adjustment = MotionLayer(
        id="grade",
        name="Grade",
        layer_type="adjustment",
        out_ms=1000,
    )
    window = MotionDesignerWindow(MotionComposition(
        duration_ms=1000,
        layers=[background, adjustment],
    ))
    window._select_layer(adjustment.id)
    assert not window.effects.scope_host.isHidden()
    mode_index = window.effects.scope_mode.findData("selected_layers_below")
    window.effects.scope_mode.setCurrentIndex(mode_index)
    app.processEvents()
    assert window.effects.scope_layers.count() == 1
    window.effects.scope_layers.item(0).setCheckState(Qt.Checked)
    app.processEvents()
    scope = window.controller.composition.layers[1].metadata["adjustment_scope"]
    assert scope == {
        "mode": "selected_layers_below",
        "layer_ids": ["background"],
    }
    window.close()
    app.processEvents()


def test_effect_group_scope_controls_persist_selected_descendant() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    child = MotionLayer(
        id="child",
        name="Child",
        layer_type="shape",
        parent_id="group",
        out_ms=1000,
    )
    outside = MotionLayer(
        id="outside",
        name="Outside",
        layer_type="shape",
        out_ms=1000,
    )
    group = MotionLayer(
        id="group",
        name="Effect Group",
        layer_type="group",
        out_ms=1000,
    )
    window = MotionDesignerWindow(MotionComposition(
        duration_ms=1000,
        layers=[child, outside, group],
    ))
    window._select_layer(group.id)
    assert not window.effects.scope_host.isHidden()
    mode_index = window.effects.scope_mode.findData("selected_descendants")
    window.effects.scope_mode.setCurrentIndex(mode_index)
    app.processEvents()
    assert window.effects.scope_layers.count() == 1
    window.effects.scope_layers.item(0).setCheckState(Qt.Checked)
    app.processEvents()
    scope = window.controller.composition.layers[2].metadata["effect_group"]
    assert scope == {
        "enabled": True,
        "mode": "selected_descendants",
        "layer_ids": ["child"],
    }
    window.close()
    app.processEvents()


def test_tracking_panel_applies_planar_track_to_corner_pin() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    layer = MotionLayer(
        id="screen",
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri="screen.png",
            params={"width": 201, "height": 101},
        ),
        effects=[MotionEffectRef(id="pin", kind="corner_pin")],
        out_ms=1000,
    )
    track = normalize_track_asset({
        "id": "planar",
        "kind": "planar",
        "origin": [100, 50],
        "samples": [
            {"time_ms": 0},
            {"time_ms": 1000, "translate": [10, 5], "scale": [1.1, 1.1]},
        ],
        "metadata": {"motion_outlier_frames": 2},
    })
    composition = MotionComposition(
        width=201,
        height=101,
        duration_ms=1000,
        layers=[layer],
        metadata={"tracking_assets": [track]},
    )
    window = MotionDesignerWindow(composition)
    window._select_layer(layer.id)
    window.tracking.set_context(window.controller.composition, layer)
    assert window.tracking.corner_pin.isEnabled()
    assert window.tracking.outliers.text() == "2"
    window.tracking.corner_pin.click()
    app.processEvents()
    stored_effect = window.controller.composition.layers[0].effects[0]
    assert stored_effect.params["bottom_right"].keyframes[-1].value == pytest.approx(
        [20, 10],
    )
    window.close()
    app.processEvents()


def test_motion_designer_independent_project_save_and_recovery(tmp_path) -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    from app.motion_designer.project_io import load_motion_project

    app = QApplication.instance() or QApplication([])
    project = tmp_path / "tutorial.tgmotion"
    window = MotionDesignerWindow(
        MotionComposition(name="Tutorial", width=960, height=540, duration_ms=2000),
        project_path=project,
        standalone_document=True,
    )
    assert window.toolbar.open_action.shortcut().toString() == "Ctrl+O"
    assert window.toolbar.save_action.shortcut().toString() == "Ctrl+S"
    window._add_layer("shape")
    assert window._document_dirty is True
    assert window.windowTitle().endswith("*")
    assert window._save_motion_project() is True
    assert project.is_file()
    assert load_motion_project(project).layers[0].layer_type == "shape"
    assert window._document_dirty is False

    window._add_layer("text")
    window._autosave_document()
    recovery = window._document_recovery_path()
    assert recovery.is_file()
    assert window._save_motion_project() is True
    assert not recovery.exists()
    window.close()
    app.processEvents()


def test_motion_template_gallery_renders_cards_and_normalizes_variant() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    from app.motion_designer.ui.template_gallery import MotionTemplateGalleryDialog

    app = QApplication.instance() or QApplication([])
    dialog = MotionTemplateGalleryDialog(variant="16:9")
    assert dialog.items.count() >= 14
    assert not dialog.items.item(0).icon().isNull()
    tutorial = next(
        dialog.items.item(index)
        for index in range(dialog.items.count())
        if dialog.items.item(index).data(Qt.ItemDataRole.UserRole)
        == "learn_keyframes_graph"
    )
    dialog.items.setCurrentItem(tutorial)
    assert "Keyframes" in dialog.guide_title.text()
    assert "Graph Editor" in dialog.guide_features.text()
    assert "Select Focus Card" in dialog.guide_steps.text()
    vertical = next(
        dialog.items.item(index)
        for index in range(dialog.items.count())
        if dialog.items.item(index).data(Qt.ItemDataRole.UserRole)
        == "vertical_shorts_hook"
    )
    dialog.items.setCurrentItem(vertical)
    assert dialog.selected_variant in {"9:16", "1:1"}
    dialog.close()
    app.processEvents()


def test_motion_actor_inspector_updates_playback_and_keeps_dark_surface() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    from app.motion_designer.actor_source import LIVE2D_SOURCE_KIND, create_actor_layer

    app = QApplication.instance() or QApplication([])
    source = Path(
        "resources/live2d_samples/CubismWebSamples/Samples/Resources/Hiyori/Hiyori.model3.json"
    ).resolve()
    layer = create_actor_layer(LIVE2D_SOURCE_KIND, source, width=640, height=360, duration_ms=1000)
    window = MotionDesignerWindow(MotionComposition(width=640, height=360, duration_ms=1000))
    window.controller.add_layer(layer)
    window._select_layer(layer.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.actor)
    window.actor.rate.setValue(1.35)
    window.actor.scale.setValue(1.2)
    changed = window.controller.composition.layers[0]
    assert changed.source.params["playback"]["rate"] == 1.35
    assert changed.source.params["actor"]["scale"] == 1.2
    window.resize(1000, 720)
    window.show()
    app.processEvents()
    image = window.actor.scroll.viewport().grab().toImage()
    assert not image.isNull()
    assert image.pixelColor(2, 2).lightness() < 80
    window.close()
    app.processEvents()


def test_motion_audio_tab_binds_bakes_and_keeps_dark_surface() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    cache = AudioAnalysisCache(
        id="audio_fixture", source_path="C:/fixture.wav", source_signature="fixture",
        duration_ms=500, hop_ms=100,
        samples=[AudioEnvelopeSample(time, amplitude=value) for time, value in (
            (0, 0.0), (100, 0.5), (200, 1.0), (300, 0.5), (400, 0.0),
        )], beat_markers=[200],
    )
    layer = MotionLayer(name="Pulse", layer_type="shape", source=SourceRef(kind="shape"), out_ms=500)
    composition = MotionComposition(
        width=960, height=540, fps=10, duration_ms=500, layers=[layer],
        metadata={"audio_analysis": {cache.id: cache.to_dict()}},
    )
    window = MotionDesignerWindow(composition)
    window._select_layer(layer.id)
    window.project_tabs.setCurrentWidget(window.audio)
    window._bind_audio_reactive({
        "analysis_id": cache.id, "channel": "amplitude", "property_name": "scale",
        "mode": "multiply", "output_min": 1.0, "output_max": 1.5,
        "smoothing_ms": 0, "attack_ms": 0, "release_ms": 0,
    })
    assert window.audio.bindings.count() == 1
    assert evaluate_composition(window.controller.composition, 200)[0].scale == [1.5, 1.5]
    window._bake_audio_reactive(10)
    assert window.audio.bindings.count() == 0
    window.resize(1100, 720)
    window.show()
    app.processEvents()
    image = window.audio.grab().toImage()
    assert not image.isNull()
    samples = [image.pixelColor(1, 1), image.pixelColor(max(1, image.width() - 2), max(1, image.height() - 2))]
    assert all(color.red() < 80 and color.green() < 80 and color.blue() < 80 for color in samples)
    window.close()
    app.processEvents()


def test_motion_mask_inspector_exposes_path_softness_and_tracking_state() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    window._add_layer("shape")
    layer_id = window.controller.composition.layers[0].id
    window._select_layer(layer_id)
    assert window.masks.kind.findText("path") >= 0
    window._add_mask("path")
    mask = window.controller.composition.layers[0].masks[0]
    assert mask.kind == "path" and mask.params["path"].value_type == "path"
    assert {"feather", "expansion", "opacity"} <= set(mask.params)
    window._set_mask_item(mask.id, "tracking_mode", "planar")
    tracking = window.controller.composition.layers[0].masks[0].metadata["tracking_cache"]
    assert tracking["mode"] == "planar" and tracking["enabled"] is True
    assert window.masks._tracking_buttons[mask.id].text() == "Track Video..."
    assert window.masks._tracking_buttons[mask.id].isEnabled()
    window.masks.set_tracking_progress(mask.id, 3, 10)
    assert window.masks._tracking_status_labels[mask.id].text() == "Tracking... 30%"
    window._set_mask_item(mask.id, "tracking_mode", "none")
    assert "tracking_cache" not in window.controller.composition.layers[0].masks[0].metadata
    window.close()
    app.processEvents()


def test_motion_mask_inspector_tracks_video_without_blocking_ui(tmp_path) -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    import cv2
    import numpy as np

    app = QApplication.instance() or QApplication([])
    video = tmp_path / "ui-track.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 20.0, (160, 120))
    assert writer.isOpened()
    rng = np.random.default_rng(91)
    patch = rng.integers(0, 255, size=(55, 65, 3), dtype=np.uint8)
    for index in range(21):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        x, y = 35 + index, 30 + index // 2
        frame[y:y + 55, x:x + 65] = patch
        writer.write(frame)
    writer.release()
    mask = MotionMaskRef(kind="rectangle", params={
        "x": AnimatedProperty(default=30), "y": AnimatedProperty(default=25),
        "width": AnimatedProperty(default=80), "height": AnimatedProperty(default=70),
    }, metadata={"tracking_cache": {"mode": "point", "enabled": True, "samples": []}})
    layer = MotionLayer(
        name="Tracked",
        layer_type="shape",
        source=SourceRef(kind="shape", uri=str(video), params={
            "width": 160, "height": 120, "fill": "#28627a",
        }),
        out_ms=1000,
        masks=[mask],
    )
    window = MotionDesignerWindow(MotionComposition(
        width=160, height=120, duration_ms=1000, layers=[layer],
    ))
    window._select_layer(layer.id)
    window._start_mask_tracking(mask.id, {"video_path": str(video), "mode": "point"})
    assert mask.id in window._tracking_jobs
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(10)
    poll.timeout.connect(lambda: loop.quit() if mask.id not in window._tracking_jobs else None)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    poll.start()
    timeout.start(5000)
    loop.exec()
    poll.stop()
    assert mask.id not in window._tracking_jobs
    stored = window.controller.composition.layers[0].masks[0].metadata["tracking_cache"]
    assert stored["metadata"]["provider"] == "opencv_lk_ransac_v1"
    assert len(stored["samples"]) >= 5
    window.close()
    app.processEvents()


def test_tracking_panel_analyzes_selected_video_without_blocking_ui(tmp_path) -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    import cv2
    import numpy as np

    app = QApplication.instance() or QApplication([])
    video = tmp_path / "composition-track.avi"
    writer = cv2.VideoWriter(
        str(video),
        cv2.VideoWriter_fourcc(*"MJPG"),
        20.0,
        (160, 120),
    )
    assert writer.isOpened()
    rng = np.random.default_rng(701)
    patch = rng.integers(0, 255, size=(55, 65, 3), dtype=np.uint8)
    for index in range(21):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[30:85, 35 + index:100 + index] = patch
        writer.write(frame)
    writer.release()
    layer = MotionLayer(
        name="Tracked Video",
        layer_type="video",
        source=SourceRef(
            kind="video",
            uri=str(video),
            params={"width": 160, "height": 120},
        ),
        out_ms=1000,
    )
    window = MotionDesignerWindow(MotionComposition(
        width=160,
        height=120,
        duration_ms=1000,
        layers=[layer],
    ))
    window._select_layer(layer.id)
    window._start_composition_tracking("point")
    assert window._composition_tracking_job is not None
    assert not window.tracking.analyze.isEnabled()
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(10)
    poll.timeout.connect(
        lambda: loop.quit()
        if window._composition_tracking_job is None else None
    )
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    poll.start()
    timeout.start(5000)
    loop.exec()
    poll.stop()
    assert window._composition_tracking_job is None
    assets = window.controller.composition.metadata["tracking_assets"]
    assert len(assets) == 1
    assert assets[0]["kind"] == "point"
    assert len(assets[0]["cache"]["samples"]) >= 5
    assert window.tracking.analyze.isEnabled()
    window.close()
    app.processEvents()


def test_motion_ai_panel_builds_reviewable_multimodal_draft_and_undoes(tmp_path) -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtGui import QColor, QImage, QPainter

    app = QApplication.instance() or QApplication([])
    image_path = tmp_path / "reference.png"
    image = QImage(320, 180, QImage.Format_RGBA8888)
    image.fill(QColor("#e2e8ee"))
    painter = QPainter(image)
    painter.setBrush(QColor("#d96a43"))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(96, 30, 128, 140)
    painter.end()
    assert image.save(str(image_path))
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    assert window.ai.decompose_images.isChecked()
    image_mime = QMimeData()
    image_mime.setUrls([QUrl.fromLocalFile(str(image_path))])
    window.ai.prompt.insertFromMimeData(image_mime)
    assert window.ai.references.count() == 1
    text_mime = QMimeData()
    text_mime.setText('배경을 페이드 인하고 "MOTION AI" 제목을 추가')
    window.ai.prompt.insertFromMimeData(text_mime)
    assert "MOTION AI" in window.ai.prompt.toPlainText()
    window.ai.advanced_button.setChecked(True)
    window.ai.extraction.segmentation.setCurrentIndex(
        window.ai.extraction.segmentation.findData("basic")
    )
    window.ai.extraction.auto_detect.setChecked(False)
    window.ai.request_plan()
    assert window.ai._proposal is None
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(10)
    poll.timeout.connect(lambda: loop.quit() if window.ai._proposal is not None else None)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    poll.start()
    timeout.start(5000)
    loop.exec()
    poll.stop()
    assert window.ai._proposal is not None
    assert window.ai.candidate_selector.count() == 3
    assert window.ai.candidate_strip.count() == 3
    assert window.ai.candidate_strip.isVisibleTo(window.ai)
    assert window.ai.apply_button.isEnabled()
    assert len(window.ai._proposal["layers"]) >= 2
    assert "Preflight:" in window.ai.result.toPlainText()
    assert "Render: realtime" in window.ai.result.toPlainText()
    assert "Layer extraction:" in window.ai.result.toPlainText()
    from app.motion_designer.image_decomposition_edits import set_decomposition_lock

    decomposition = window.ai._proposal["analysis"]["image_decompositions"][0]
    visual_id = next(
        item["id"] for item in decomposition["elements"] if item["role"] != "text"
    )
    repaired = set_decomposition_lock(
        decomposition,
        [visual_id],
        locked=True,
    ).to_dict()
    repaired.update({
        "reference_id": decomposition["reference_id"],
        "beat_id": decomposition["beat_id"],
    })
    window._repair_ai_decomposition(repaired)
    repaired_report = window.ai._proposal["analysis"]["image_decompositions"][0]
    repaired_element = next(
        item for item in repaired_report["elements"] if item["id"] == visual_id
    )
    assert repaired_element["metadata"]["motion_lock_to_background"] is True
    window.ai.apply_proposal()
    applied_count = len(window.controller.composition.layers)
    assert applied_count >= 2
    assert window.ai.status.text() == f"Applied {applied_count}"
    window.controller.undo()
    assert window.controller.composition.layers == []
    window.ai_dock.close()
    assert not window.toolbar.ai_action.isChecked()
    window.close()
    app.processEvents()


def test_motion_mask_refine_canvas_adds_and_removes_brush_strokes() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QColor, QImage

    from app.motion_designer.ui.mask_refine_canvas import MaskRefineCanvas

    app = QApplication.instance() or QApplication([])
    source = QImage(80, 60, QImage.Format_RGBA8888)
    source.fill(QColor("#35404d"))
    mask = QImage(80, 60, QImage.Format_Grayscale8)
    mask.fill(0)
    canvas = MaskRefineCanvas()
    canvas.set_images(source, mask)
    canvas.set_brush_radius(4)
    canvas.set_mode("add")
    canvas._paint_mask(QPoint(10, 20), QPoint(50, 20))
    assert canvas.mask_image().pixelColor(30, 20).red() > 240
    canvas.set_mode("remove")
    canvas._paint_mask(QPoint(28, 20), QPoint(32, 20))
    assert canvas.mask_image().pixelColor(30, 20).red() < 16
    canvas.close()
    app.processEvents()


def test_layer_extraction_dialog_keeps_dark_surface_and_edit_controls(tmp_path) -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    from PIL import Image, ImageDraw

    from app.motion_designer.image_decomposition import decompose_image
    from app.motion_designer.ui.layer_extraction_dialog import (
        LayerExtractionDialog,
    )
    from app.motion_designer.ui.style import MOTION_DESIGNER_QSS

    app = QApplication.instance() or QApplication([])
    source = Image.new("RGB", (240, 160), (226, 232, 238))
    ImageDraw.Draw(source).ellipse((65, 20, 180, 150), fill=(220, 70, 55))
    source_path = tmp_path / "dialog_source.png"
    source.save(source_path)
    decomposition = decompose_image(
        source_path,
        width=240,
        height=160,
        cache_root=tmp_path / "cache",
        include_depth=False,
        force=True,
    )
    dialog = LayerExtractionDialog(decomposition.to_dict())
    dialog.setStyleSheet(MOTION_DESIGNER_QSS)
    dialog.show()
    app.processEvents()
    assert dialog.layers.count() >= 1
    assert dialog.parent_button.text() == "Set Parent"
    image = dialog.grab().toImage()
    assert image.pixelColor(2, 2).lightness() < 80
    dialog.close()
    app.processEvents()


def test_motion_transport_supports_forward_reverse_stop_and_loop() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=1000))
    timeline = window.timeline
    assert all(button.isVisibleTo(timeline) for button in (
        timeline.to_start, timeline.reverse_button, timeline.stop_button,
        timeline.play_button, timeline.loop_button, timeline.to_end,
    ))

    timeline.reverse_button.click()
    assert window._play_direction == -1
    assert window._time_ms == 1000
    assert timeline.reverse_button.isChecked()
    timeline.stop_button.click()
    assert window._play_direction == 0
    assert not timeline.reverse_button.isChecked()

    timeline.loop_button.click()
    assert window._loop_playback is True
    window._set_time(990)
    window._set_playback_direction(1)
    window._advance_playback(25)
    assert window._time_ms == 15
    assert timeline.play_button.isChecked()

    window._set_time(10)
    window._set_playback_direction(-1)
    window._advance_playback(25)
    assert window._time_ms == 985
    assert timeline.reverse_button.isChecked()

    timeline.loop_button.click()
    window._set_time(990)
    window._set_playback_direction(1)
    window._advance_playback(25)
    assert window._time_ms == 1000
    assert window._play_direction == 0
    assert not timeline.play_button.isChecked()
    window.close()
    app.processEvents()


def test_motion_playback_preserves_fractional_timer_elapsed_time() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=20000))
    window._set_playback_direction(1)
    for _ in range(600):
        window._advance_playback_elapsed(1000.0 / 60.0)
    window._set_playback_direction(0)
    assert abs(window._time_ms - 10000) <= 1
    assert 0.0 <= window._playback_fractional_ms < 1.0
    window.close()
    app.processEvents()


def test_template_change_restarts_active_playback_from_zero() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(
        MotionComposition(width=960, height=540, duration_ms=20000)
    )
    window._set_time(8750)
    window.timeline.set_time(8750)
    window._set_playback_direction(1)
    window._playback_fractional_ms = .75

    window._apply_library_item("template", "clean_lower_third")

    assert window._time_ms == 0
    assert window.timeline.slider.value() == 0
    assert window._play_direction == 1
    assert window._play_timer.isActive()
    assert window._playback_fractional_ms == 0.0
    assert window.timeline.play_button.isChecked()
    window._set_playback_direction(0)
    window.close()
    app.processEvents()


def test_motion_message_box_uses_readable_dark_surface() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(
        MotionComposition(width=960, height=540, duration_ms=1000)
    )
    dialog = QMessageBox(
        QMessageBox.Icon.Question,
        "Unsaved Motion Project",
        "Save changes to the current Motion project?",
        QMessageBox.StandardButton.Save
        | QMessageBox.StandardButton.Discard
        | QMessageBox.StandardButton.Cancel,
        window,
    )
    dialog.show()
    app.processEvents()
    message = next(
        label
        for label in dialog.findChildren(QLabel)
        if "Save changes" in label.text()
    )
    assert message.palette().color(message.foregroundRole()).lightness() > 150
    surface = dialog.grab().toImage()
    assert surface.pixelColor(12, min(45, surface.height() - 1)).lightness() < 90
    dialog.close()
    window.close()
    app.processEvents()


def test_motion_timeline_trim_and_library_apply_use_document_controller() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=5000))
    window._apply_library_item("object", "shape")
    layer = window.controller.composition.layers[0]
    window._set_layer_timing(layer.id, 500, 4200)
    changed = window.controller.composition.layers[0]
    assert (changed.in_ms, changed.out_ms) == (500, 4200)
    window._apply_library_item("behavior", "wiggle")
    window._apply_library_item("effect", "vignette")
    changed = window.controller.composition.layers[0]
    assert changed.behaviors[0].kind == "wiggle"
    assert changed.effects[0].kind == "vignette"
    assert window.left_tabs.currentWidget() is window.inspector_tabs
    window.close()
    app.processEvents()


def test_motion_graph_property_selection_and_keyframe_drag_update_document() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    window._add_layer("shape")
    layer_id = window.controller.composition.layers[0].id
    window.controller.set_keyframe(layer_id, "position", [100.0, 200.0], 0)
    window.controller.set_keyframe(layer_id, "position", [500.0, 260.0], 2000)
    window._select_layer(layer_id)
    prop = window.controller.composition.layers[0].transform.position
    keyframe_id = prop.keyframes[1].id
    window.timeline.graph_editor.keyframe_changed.emit(
        keyframe_id, 1500, [440.0, 240.0],
    )
    changed = window.controller.composition.layers[0].transform.position.keyframes
    moved = next(item for item in changed if item.id == keyframe_id)
    assert moved.time_ms == 1500
    assert moved.value == [440.0, 240.0]
    window.timeline.graph_properties.setCurrentRow(2)
    assert window.timeline.graph_editor.property is window.controller.composition.layers[0].transform.rotation
    window.close()
    app.processEvents()


def test_vector_inspector_and_canvas_path_handles_update_shared_document() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    from PySide6.QtCore import QPointF

    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    window._add_layer("path")
    layer = window.controller.composition.layers[0]
    handles = [item for item in window.canvas.scene().items() if item.data(1) == "vector_handle"]
    assert len(handles) >= len(layer.source.params["path"]["points"])
    window.vector.repeat_count.setValue(3)
    window.vector.repeat_x.setValue(24)
    window.vector.trim_end.setValue(.5)
    changed = window.controller.composition.layers[0]
    assert changed.source.params["repeater"]["count"] == 3
    assert changed.source.params["repeater"]["offset"][0] == 24
    assert changed.source.params["trim"]["end"] == .5
    window.canvas._move_vector_handle(changed, 0, "position", QPointF(-100, 0), 520, 280)
    moved = window.controller.composition.layers[0].source.params["path"]["points"][0]["position"]
    assert moved == [160.0, 140.0]
    path_item = next(
        item for item in window.canvas.scene().items()
        if item.data(0) == layer.id and item.data(1) != "vector_handle" and item.parentItem() is None
    )
    before = len(window.controller.composition.layers[0].source.params["path"]["points"])
    window.canvas._add_vector_point(layer.id, path_item.mapToScene(QPointF(0, 0)))
    assert len(window.controller.composition.layers[0].source.params["path"]["points"]) == before + 1
    window.canvas._delete_vector_component(layer.id, 1, "position")
    assert len(window.controller.composition.layers[0].source.params["path"]["points"]) == before
    window.canvas._delete_vector_component(layer.id, 0, "out")
    assert window.controller.composition.layers[0].source.params["path"]["points"][0]["out"] == [0.0, 0.0]
    window.close()
    app.processEvents()


def test_vector_inspector_links_shape_layers_as_boolean_operands() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    window._add_layer("shape")
    target_id = window.controller.composition.layers[0].id
    window._add_layer("ellipse")
    operand_id = window.controller.composition.layers[1].id
    window._select_layer(target_id)
    assert window.vector.boolean_operands.count() == 1
    assert window.vector.boolean_operands.item(0).data(Qt.UserRole) == operand_id
    window.vector.boolean_operation.setCurrentText("subtract")
    window.vector.boolean_operands.item(0).setCheckState(Qt.Checked)
    boolean = window.controller.composition.layers[0].source.params["boolean"]
    assert boolean["operation"] == "subtract"
    assert boolean["operand_layer_ids"] == [operand_id]
    assert boolean["hide_operands"] is True
    canvas_items = [
        item for item in window.canvas.scene().items()
        if item.data(0) == target_id and item.parentItem() is None
    ]
    assert canvas_items and canvas_items[0].shape().contains(canvas_items[0].boundingRect().center()) is False
    window._select_layer(operand_id)
    assert window.vector.boolean_operands.count() == 0
    window.close()
    app.processEvents()


def test_vector_inspector_scroll_surface_never_renders_white() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    window._add_layer("shape")
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.vector)
    window.resize(1000, 720)
    window.show()
    app.processEvents()

    viewport = window.vector.scroll.viewport()
    image = viewport.grab().toImage()
    assert not image.isNull()
    samples = [
        image.pixelColor(1, 1),
        image.pixelColor(max(1, image.width() - 2), max(1, image.height() - 2)),
    ]
    assert all(color.lightness() < 80 for color in samples)
    window.close()


def test_typography_text_editor_never_uses_a_white_surface() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    window._add_layer("text")
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.typography)
    window.show()
    app.processEvents()
    image = window.typography.text.viewport().grab().toImage()
    assert not image.isNull()
    assert image.pixelColor(2, 2).lightness() < 80
    window.close()
    app.processEvents()
    app.processEvents()


def test_output_panel_is_dark_and_toolbar_opens_it() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    window.show()
    window.toolbar.output_requested.emit()
    app.processEvents()
    assert window.left_tabs.currentWidget() is window.output
    assert window.output.profile.count() == 8
    image = window.output.grab().toImage()
    assert not image.isNull()
    assert image.pixelColor(2, 2).lightness() < 80
    window.close()
    app.processEvents()


def test_output_panel_changes_explicit_blend_space() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    before = window.controller.composition.revision
    window.output.blend_space.setCurrentIndex(window.output.blend_space.findData("display-srgb"))
    app.processEvents()
    settings = window.controller.composition.metadata["color_management"]
    assert settings["blend_space"] == "display-srgb"
    assert settings["alpha"]["premultiply_space"] == "display"
    assert window.controller.composition.revision > before
    window.close()
    app.processEvents()


def test_output_panel_only_requests_resume_for_png_sequence(tmp_path: Path) -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    requests: list[dict] = []
    window.output.export_requested.connect(requests.append)
    window.output.resume_sequence.setChecked(True)
    window.output.profile.setCurrentIndex(window.output.profile.findData("h264_mp4"))
    window.output.output_path.setText(str(tmp_path / "motion.mp4"))

    window.output._export_or_cancel()

    assert requests and requests[0]["profile_id"] == "h264_mp4"
    assert requests[0]["resume"] is False
    window.close()
    app.processEvents()


def test_typography_inspector_updates_text_style_and_selector_animation() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    window._add_layer("text")
    layer_id = window.controller.composition.layers[0].id
    window.typography.text.setPlainText("Tiger Typography")
    window.typography.in_animation.setCurrentText("typewriter-in")
    window.typography.unit.setCurrentText("word")
    window.typography.stagger.setValue(90)
    changed = window.controller.composition.layers[0]
    assert changed.id == layer_id
    assert changed.source.params["text"] == "Tiger Typography"
    assert changed.source.params["text_animation"]["in"] == "typewriter-in"
    assert changed.source.params["text_animation"]["unit"] == "word"
    assert changed.source.params["text_animation"]["stagger_ms"] == 90
    window.close()
    app.processEvents()


def test_typography_visual_path_picker_updates_canvas_path_and_offset() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    from PySide6.QtCore import QPointF

    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(width=960, height=540, duration_ms=3000))
    window._add_layer("text")
    layer_id = window.controller.composition.layers[0].id
    window.typography.follow_path.setChecked(True)

    layer = window.controller.composition.layers[0]
    assert layer.source.params["text_path"]["closed"] is False
    assert layer.source.params["width"] == 640.0
    handles = [
        item for item in window.canvas.scene().items()
        if item.data(1) == "typography_path_handle"
    ]
    offsets = [
        item for item in window.canvas.scene().items()
        if item.data(1) == "typography_path_offset"
    ]
    assert len(handles) >= len(layer.source.params["text_path"]["points"])
    assert len(offsets) == 1

    window.canvas._move_typography_path_handle(
        layer, 0, "position", QPointF(-100.0, 0.0), 640.0, 240.0,
    )
    moved = window.controller.composition.layers[0].source.params["text_path"]["points"][0]
    assert moved["position"] == [220.0, 120.0]

    layer = window.controller.composition.layers[0]
    window.canvas._move_typography_path_offset(
        layer, QPointF(160.0, 0.0), [(0.0, 120.0), (640.0, 120.0)], 640.0, 240.0,
    )
    assert window.controller.composition.layers[0].source.params["text_path_offset"] == pytest.approx(.75)
    assert window.typography.path_offset.value() == pytest.approx(.75)

    window.typography.follow_path.setChecked(False)
    assert window.controller.composition.layers[0].source.params["text_path"] is None
    assert not any(
        item.data(1) == "typography_path_handle" for item in window.canvas.scene().items()
    )
    window.close()
    app.processEvents()
