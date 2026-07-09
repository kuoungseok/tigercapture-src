from types import SimpleNamespace

import numpy as np


def test_color_curves_apply_master_lut():
    from app.color_workflow import ColorCurve, CurveSet, apply_curves

    rgb = np.array([[[0, 64, 255], [128, 192, 255]]], dtype=np.uint8)
    curves = CurveSet(master=ColorCurve(((0, 0), (255, 128))))

    out = apply_curves(rgb, curves)

    assert out[0, 0, 0] == 0
    assert out[0, 0, 2] == 128
    assert out[0, 1, 0] < rgb[0, 1, 0]


def test_advanced_color_toolset_applies_hdr_log_hue_and_warper_controls():
    from app.color_workflow import (
        AdvancedColorToolset,
        ColorWarperPoint,
        HDRZoneControl,
        HueCurveSet,
        LogWheelSet,
        advanced_color_product_capabilities,
        apply_advanced_color_toolset,
    )

    rgb = np.array([[[220, 40, 40], [40, 180, 40], [40, 40, 220]]], dtype=np.uint8)
    toolset = AdvancedColorToolset(
        hdr_zones=HDRZoneControl(enabled=True, shadow=10, highlight=-8),
        log_wheels=LogWheelSet(shadows=(0.02, 0.0, 0.0), highlights=(0.0, 0.0, -0.02)),
        hue_curves=HueCurveSet(hue_vs_sat=((0, 0.25), (120, -0.1), (240, 0.0))),
        warper_points=(ColorWarperPoint(hue=0, saturation=0.8, hue_shift=10, sat_scale=1.05),),
    )

    out = apply_advanced_color_toolset(rgb, toolset)
    caps = advanced_color_product_capabilities()

    assert out.shape == rgb.shape
    assert not np.array_equal(out, rgb)
    assert caps["float_processing_bits"] == 32
    assert caps["hdr_wheels"] is True
    assert caps["color_warper"] is True
    assert caps["raw_sidecar_model"] is True
    assert caps["hdr_metadata_model"] is True
    assert caps["node_grading_model"] is True
    assert caps["scope_accuracy_qa"] is True


def test_scope_accuracy_report_uses_synthetic_chart_gates():
    from app.color_workflow import build_scope_accuracy_sample, scope_accuracy_report

    sample = build_scope_accuracy_sample(64, 32)
    report = scope_accuracy_report(sample)

    assert sample.shape == (32, 64, 3)
    assert report["ok"] is True
    assert report["luma_span"] >= 0.80
    assert "waveform luma span >= 0.80" in report["qa_gates"]


def test_color_scope_renderers_produce_workbench_graphs():
    from app.color_scopes import render_scope
    from app.color_workflow import build_scope_accuracy_sample

    sample = build_scope_accuracy_sample(96, 54)

    for kind in ("waveform", "histogram", "parade", "vectorscope"):
        graph = render_scope(kind, sample, 80, 40)

        assert graph.shape == (40, 80, 3)
        assert graph.dtype == np.uint8
        assert int(graph.max()) > 20
        assert int(graph.mean()) > 5


def test_color_grade_advanced_toolset_roundtrip_and_apply_to_rgb():
    from app.color_grading import ColorGrade, apply_to_rgb

    rgb = np.array([[[232, 64, 48], [42, 190, 60], [48, 60, 225]]], dtype=np.uint8)
    grade = ColorGrade()
    grade.advanced_color_toolset = {
        "enabled": True,
        "processing_bits": 32,
        "yrgb": True,
        "hdr_zones": {"enabled": True, "shadow": 12, "highlight": -18, "pivot": 0.55},
        "log_wheels": {"shadows": [0.02, 0.0, 0.0], "highlights": [0.0, 0.0, -0.025]},
        "hue_curves": {"hue_vs_sat": [[0, 0.2], [120, -0.08], [240, 0.02]]},
        "warper_points": [{"hue": 0, "saturation": 0.75, "hue_shift": 12, "sat_scale": 1.08}],
    }

    restored = ColorGrade.from_dict(grade.to_dict())
    out = apply_to_rgb(rgb, restored)

    assert restored.advanced_color_toolset["hdr_zones"]["enabled"] is True
    assert not restored.is_identity()
    assert out.shape == rgb.shape
    assert not np.array_equal(out, rgb)


def test_advanced_color_preset_applies_to_grade_and_readiness_counts_it():
    from app.color_grading import ColorGrade, apply_to_rgb
    from app.preset_library import apply_color_preset_to_grade, preset_by_id
    from app.professional_readiness import audit_color_workflow_depth, audit_gpu_preview_export_consistency

    preset = preset_by_id("color-hdr-zone-product-pop")
    grade = ColorGrade()
    workflow = apply_color_preset_to_grade(grade, preset)
    rgb = np.array([[[235, 210, 170], [45, 80, 180]]], dtype=np.uint8)
    out = apply_to_rgb(rgb, grade)
    doc = {
        "project_settings": {
            "color_management": {
                "output_space": "Rec.709",
                "output_transfer": "bt709",
                "preview_transform_enabled": True,
            },
        },
        "video_tracks": [{"clips": [{"id": 1, "color_grade": grade.to_dict()}]}],
    }

    color = audit_color_workflow_depth(doc)
    gpu = audit_gpu_preview_export_consistency(doc)

    assert workflow == {}
    assert grade.advanced_color_toolset["hdr_zones"]["enabled"] is True
    assert not np.array_equal(out, rgb)
    assert color["counts"]["hdr_zone_controls"] == 1
    assert color["counts"]["log_wheels"] == 1
    assert color["counts"]["color_warper_points"] == 1
    assert gpu["color_parity_features"]["advanced_color_toolset"] >= 1


def test_color_qualifier_limits_node_grade_to_selected_hue():
    from app.color_grading import ColorGrade
    from app.color_workflow import ColorNodeWorkflow, ColorQualifier, apply_color_node_workflow

    rgb = np.zeros((6, 6, 3), dtype=np.uint8)
    rgb[:, :] = [220, 0, 0]
    rgb[2:4, 2:4] = [0, 180, 0]
    node = ColorNodeWorkflow(
        qualifier=ColorQualifier(
            enabled=True,
            hue_center=120.0,
            hue_width=12.0,
            sat_min=0.2,
            val_min=0.05,
            softness=0.05,
        )
    )

    out = apply_color_node_workflow(rgb, ColorGrade(brightness=45), node)

    assert int(out[2, 2, 1]) > int(rgb[2, 2, 1])
    assert np.allclose(out[0, 0], rgb[0, 0], atol=1)


def test_color_grade_workflow_roundtrip_and_masked_apply_to_rgb():
    from app.color_grading import ColorGrade, apply_to_rgb

    rgb = np.zeros((6, 6, 3), dtype=np.uint8)
    rgb[:, :] = [200, 0, 0]
    rgb[2:4, 2:4] = [0, 170, 0]
    grade = ColorGrade(brightness=35)
    grade.color_workflow = {
        "enabled": True,
        "qualifier": {
            "enabled": True,
            "hue_center": 120.0,
            "hue_width": 12.0,
            "sat_min": 0.2,
            "val_min": 0.05,
            "softness": 0.05,
        },
    }

    restored = ColorGrade.from_dict(grade.to_dict())
    out = apply_to_rgb(rgb, restored)

    assert restored.color_workflow["qualifier"]["enabled"] is True
    assert int(out[2, 2, 1]) > int(rgb[2, 2, 1])
    assert np.allclose(out[0, 0], rgb[0, 0], atol=1)


def test_tracking_window_mask_and_scope_diagnostics():
    from app.color_workflow import TrackingWindow, scope_diagnostics, window_mask

    mask = window_mask((20, 20), TrackingWindow(enabled=True, x=0.5, y=0.5, w=0.4, h=0.4, feather=0.1))
    assert mask[10, 10] > 0.9
    assert mask[0, 0] < 0.1

    clipped = np.zeros((4, 4, 3), dtype=np.uint8)
    clipped[:2] = 255
    diag = scope_diagnostics(clipped)
    assert diag["shadow_clip_ratio"] == 0.5
    assert diag["highlight_clip_ratio"] == 0.5


def test_tracking_window_ui_drag_helpers_clamp_edges_and_handles():
    from app.color_workflow import TrackingWindow, edit_tracking_window, normalize_tracking_window

    window = TrackingWindow(enabled=True, x=0.5, y=0.5, w=0.4, h=0.4)

    moved = edit_tracking_window(window, "move", 0.8, 0.8)
    assert moved.x <= 0.8
    assert moved.y <= 0.8
    assert moved.x + moved.w * 0.5 <= 1.0
    assert moved.y + moved.h * 0.5 <= 1.0

    resized = edit_tracking_window(window, "top_left", 0.18, 0.15)
    assert resized.w < window.w
    assert resized.h < window.h
    assert resized.x > window.x
    assert resized.y > window.y

    tiny = edit_tracking_window(window, "right", -0.9, 0.0)
    assert tiny.w >= 0.02

    normalized = normalize_tracking_window({
        "enabled": True,
        "shape": "RECTANGLE",
        "x": 1.3,
        "y": -0.2,
        "w": 3.0,
        "h": 0.0,
        "feather": 2.0,
        "opacity": -1.0,
    })
    assert normalized.shape == "rectangle"
    assert 0.0 <= normalized.x <= 1.0
    assert 0.0 <= normalized.y <= 1.0
    assert normalized.w == 1.0
    assert normalized.h >= 0.01
    assert normalized.feather == 1.0
    assert normalized.opacity == 0.0


def test_color_node_workflow_to_dict_preserves_qualifier_and_window_controls():
    from app.color_workflow import ColorNodeWorkflow, ColorQualifier, TrackingWindow

    workflow = ColorNodeWorkflow(
        enabled=True,
        qualifier=ColorQualifier(
            enabled=True,
            hue_center=210.0,
            hue_width=22.0,
            sat_min=0.1,
            sat_max=0.8,
            val_min=0.2,
            val_max=0.9,
            softness=0.12,
            clean_black=0.25,
            clean_white=0.35,
            denoise_radius=5,
            invert=True,
        ),
        window=TrackingWindow(
            enabled=True,
            shape="rectangle",
            x=0.4,
            y=0.6,
            w=0.3,
            h=0.2,
            feather=0.15,
            opacity=0.75,
            track_object=True,
            tracking_status="tracking",
            tracker_id="win-1",
        ),
    )

    restored = ColorNodeWorkflow.from_dict(workflow.to_dict())

    assert restored.qualifier.clean_black == 0.25
    assert restored.qualifier.clean_white == 0.35
    assert restored.qualifier.denoise_radius == 5
    assert restored.qualifier.invert is True
    assert restored.window.shape == "rectangle"
    assert restored.window.track_object is True
    assert restored.window.tracker_id == "win-1"
    assert restored.window.opacity == 0.75


def test_color_management_roundtrip_export_metadata_and_validation():
    from app.color_management import (
        ColorManagementSettings,
        append_lut_filter_graph,
        compare_ffprobe_color_metadata,
        ffmpeg_color_args,
        validate_export_color_consistency,
        validate_color_management,
    )

    settings = ColorManagementSettings.from_dict({
        "input_space": "sRGB",
        "working_space": "ACEScg",
        "output_space": "Rec.2020",
        "output_transfer": "PQ",
        "view_transform": "ACES",
        "creative_lut": {"path": "look.cube", "strength": 0.45},
    })

    restored = ColorManagementSettings.from_dict(settings.to_dict())
    assert restored.input_space == "srgb"
    assert restored.working_space == "acescg"
    assert restored.output_space == "rec2020"
    assert restored.output_transfer == "pq"
    assert restored.is_hdr()

    args = ffmpeg_color_args(restored)
    assert "-color_primaries" in args
    assert args[args.index("-color_primaries") + 1] == "bt2020"
    assert args[args.index("-color_trc") + 1] == "smpte2084"
    assert "yuv420p10le" in args

    report = validate_color_management(restored)
    assert report["ok"]
    assert "creative" in report["active_luts"]
    assert any("ACES" in warning for warning in report["warnings"])

    consistency = validate_export_color_consistency(
        {"color_management": settings.to_dict()},
        {"color_management": {"output_space": "Rec.709", "output_transfer": "bt709"}},
    )
    assert any("differs from project" in warning for warning in consistency["warnings"])

    graph, out_label = append_lut_filter_graph("nullsrc[outv]", "outv", settings)
    assert out_label == "outv_lut0"
    assert "lut3d=file='look.cube':interp=tetrahedral" in graph
    assert "blend=all_mode=normal:all_opacity=0.4500" in graph

    probe_ok = compare_ffprobe_color_metadata(
        {"color_management": settings.to_dict()},
        {"color_space": "bt2020nc", "color_primaries": "bt2020", "color_transfer": "smpte2084"},
    )
    assert probe_ok["ok"]
    probe_bad = compare_ffprobe_color_metadata(
        {"color_management": settings.to_dict()},
        {"color_space": "bt709", "color_primaries": "bt709", "color_transfer": "bt709"},
    )
    assert not probe_bad["ok"]
    assert probe_bad["mismatches"]


def test_export_color_probe_parses_ffmpeg_text_and_formats_diagnostics(tmp_path, monkeypatch):
    from app import color_management as cm

    text = (
        "Stream #0:0: Video: h264, yuv420p(tv, bt709/bt709/bt709, "
        "progressive), 1920x1080"
    )
    stream = cm.parse_ffmpeg_color_stream_text(text)
    assert stream["color_space"] == "bt709"
    assert stream["color_primaries"] == "bt709"
    assert stream["color_transfer"] == "bt709"
    compact_stream = cm.parse_ffmpeg_color_stream_text(
        "Stream #0:0: Video: h264, yuv420p(tv, bt709, progressive), 1280x720"
    )
    assert compact_stream["color_space"] == "bt709"
    assert compact_stream["color_primaries"] == "bt709"
    assert compact_stream["color_transfer"] == "bt709"

    out = tmp_path / "out.mp4"
    out.write_bytes(b"fake")
    monkeypatch.setattr(cm, "_probe_color_with_ffprobe", lambda _p, _t: (stream, "ffprobe"))

    report = cm.probe_export_color_metadata(
        out,
        {"color_management": {"output_space": "Rec.709", "output_transfer": "bt709"}},
    )

    assert report["ok"]
    assert report["probed"]
    assert "Color QA: OK" in report["diagnostics"]

    mismatch = cm.probe_export_color_metadata(
        out,
        {"color_management": {"output_space": "Rec.2020", "output_transfer": "PQ"}},
    )
    assert not mismatch["ok"]
    assert "mismatch" in mismatch["diagnostics"]
    assert "expected bt2020" in mismatch["diagnostics"]


def test_ocio_plan_reports_unavailable_or_unconfigured_without_mutating_frame():
    from app.color_ocio import apply_ocio_transform_rgb, build_ocio_plan

    settings = {
        "input_space": "Rec.709",
        "working_space": "ACEScg",
        "ocio_config_path": "",
    }
    plan = build_ocio_plan(settings)
    rgb = np.full((2, 2, 3), 128, dtype=np.uint8)
    out, report = apply_ocio_transform_rgb(rgb, settings)

    assert plan.enabled is False
    assert report["applied"] is False
    assert np.array_equal(out, rgb)


def test_scope_quality_diagnostics_flags_clipping_and_hdr_peak():
    from app.color_scopes import scope_quality_diagnostics

    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    rgb[:2] = 255
    diag = scope_quality_diagnostics(
        rgb,
        {"output_space": "Rec.2020", "output_transfer": "PQ", "hdr_mode": True},
    )

    assert "shadow clipping" in diag["warnings"]
    assert "highlight clipping" in diag["warnings"]
    assert diag["nits_p99"] > 900


def test_qualifier_clean_black_white_and_denoise_mask():
    from app.color_workflow import ColorQualifier, qualifier_mask

    rgb = np.zeros((5, 5, 3), dtype=np.uint8)
    rgb[:, :] = [255, 0, 0]
    rgb[:, :2] = [255, 220, 220]
    q = ColorQualifier(
        enabled=True,
        hue_center=0.0,
        hue_width=8.0,
        sat_min=0.2,
        softness=0.02,
        clean_black=0.4,
        clean_white=0.2,
        denoise_radius=3,
    )

    restored = ColorQualifier.from_dict({
        "enabled": True,
        "hue_center": 0,
        "hue_width": 8,
        "clean_black": 0.4,
        "clean_white": 0.2,
        "denoise_radius": 3,
    })
    mask = qualifier_mask(rgb, q)

    assert restored.clean_black == 0.4
    assert restored.clean_white == 0.2
    assert restored.denoise_radius == 3
    assert float(mask[2, 2]) > 0.95
    assert float(mask[2, 0]) < 0.2


def test_color_grade_lut_slots_roundtrip_and_apply(tmp_path):
    from app.color_grading import ColorGrade, apply_to_rgb

    lut_path = tmp_path / "red.cube"
    lut_path.write_text(
        "LUT_3D_SIZE 2\n" + "\n".join(["1 0 0"] * 8) + "\n",
        encoding="utf-8",
    )
    grade = ColorGrade(creative_lut_path=str(lut_path), creative_lut_strength=1.0)
    restored = ColorGrade.from_dict(grade.to_dict())
    rgb = np.zeros((2, 2, 3), dtype=np.uint8)

    out = apply_to_rgb(rgb, restored)

    assert restored.creative_lut_path == str(lut_path)
    assert out[0, 0, 0] > 240
    assert out[0, 0, 1] < 5


def test_grade_stack_and_shot_match_adjustment():
    from app.color_grading import ColorGrade, apply_grade_stack, suggest_shot_match_grade

    rgb = np.full((4, 4, 3), 80, dtype=np.uint8)
    out = apply_grade_stack(rgb, [ColorGrade(brightness=10), {"contrast": 20}])
    assert int(out[0, 0, 0]) > int(rgb[0, 0, 0])

    reference = np.full((8, 8, 3), 180, dtype=np.uint8)
    target = np.full((8, 8, 3), 80, dtype=np.uint8)
    grade = suggest_shot_match_grade(reference, target)
    assert grade.preset_id == "shot_match"
    assert grade.brightness > 0


def test_color_grade_icon_is_vector_and_nonblank():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app.icons import app_icon, icon_size

    QApplication.instance() or QApplication([])
    pix = app_icon("grading", size=32).pixmap(icon_size(32))
    assert not pix.isNull()
    img = pix.toImage()
    nonblank = 0
    colorful = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() > 0:
                nonblank += 1
                if max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue()) > 20:
                    colorful += 1
    assert nonblank > 80
    assert colorful > 20


def test_color_page_uses_studio_grading_chrome():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel, QWidget
    from app.color_page_window import ColorPageWindow

    QApplication.instance() or QApplication([])
    win = ColorPageWindow()
    try:
        assert win.findChild(QWidget, "ColorTopBar") is not None
        assert win.findChild(QWidget, "ColorRoleStrip") is not None
        assert win.findChild(QWidget, "ColorPipelineBar") is not None
        assert win.findChild(QWidget, "ColorScopesPanel") is not None
        assert win.findChild(QWidget, "ColorQualifierPanel") is not None
        labels = [label.text() for label in win.findChild(QWidget, "ColorTopBar").findChildren(QLabel)]
        assert "Color Grade" in labels
    finally:
        win.close()


def test_color_page_switch_uses_embedded_dock_by_default():
    from types import SimpleNamespace

    from app.video_editor_window import VideoEditorWindow

    class _Button:
        def __init__(self):
            self.checked = None

        def setChecked(self, value):
            self.checked = bool(value)

    calls = []
    editor = SimpleNamespace(
        _page_edit_btn=_Button(),
        _page_color_btn=_Button(),
        _show_color_dock_page=lambda: calls.append("dock"),
        _close_color_page=lambda: calls.append("close"),
        _update_color_dock_visibility=lambda node: calls.append(("dock_visible", node)),
    )

    VideoEditorWindow._switch_page(editor, "color")

    assert editor._page_edit_btn.checked is False
    assert editor._page_color_btn.checked is True
    assert calls == ["dock"]


def test_video_clip_extract_audio_helper_targets_clicked_clip():
    from app.video_editor_window import VideoEditorWindow

    calls = []
    statuses = []

    class _Result:
        def to_dict(self):
            return {"ok": True, "result": {"audio_track_id": 42}}

    class _Registry:
        def execute(self, action_id, params):
            calls.append((action_id, dict(params)))
            return _Result()

    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    editor._ensure_python_action_registry = lambda: _Registry()
    editor._flash_status = lambda text: statuses.append(text)
    track = SimpleNamespace(id=7)
    clip = SimpleNamespace(id=11)

    VideoEditorWindow._extract_audio_from_video_selection(editor, track, clip)

    assert calls == [
        (
            "audio.extract_from_video",
            {"track_id": 7, "clip_id": 11, "link": True, "name": "Extracted Audio"},
        )
    ]
    assert statuses == ["Audio extracted to track 42"]


def test_embedded_color_dock_uses_compact_palette_controls():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLabel, QPushButton

    from app.color_grading import ColorGrade
    from app.video_editor_window import VideoEditorWindow

    QApplication.instance() or QApplication([])
    grade = ColorGrade()
    editor = SimpleNamespace(
        _active_color_grade=lambda: grade,
        _load_lut_file=lambda: None,
        _on_lut_strength_changed=lambda value: None,
        _on_color_reset=lambda: None,
        _on_color_luma_changed=lambda region, value: None,
        _on_color_wheel_changed=lambda region, x, y: None,
        _on_color_slider_changed=lambda key, value: None,
        _update_wheel_readouts=lambda region, x, y: None,
        _sync_color_power_window_overlay=lambda: None,
    )
    editor._refresh_color_preset_btn_label = (
        lambda: VideoEditorWindow._refresh_color_preset_btn_label(editor)
    )
    editor._build_color_preset_menu = (
        lambda: VideoEditorWindow._build_color_preset_menu(editor)
    )
    editor._sync_color_panel = (
        lambda: VideoEditorWindow._sync_color_panel(editor)
    )

    panel = VideoEditorWindow._build_color_compact_palette_panel(editor)
    try:
        assert panel.maximumHeight() <= 240
        assert panel.minimumWidth() == 0
        assert panel.sizeHint().width() >= 900
        assert len(editor._color_wheels) == 4
        assert len(editor._color_lumas) == 4
        assert len(editor._color_sliders) == 3
        assert len(editor._color_palette_cards) >= 5
        assert any(btn.text() == "Page" for btn in panel.findChildren(QPushButton))
        assert panel.findChild(QLabel, "ColorTargetBadge") is not None
        assert panel.findChildren(QDoubleSpinBox) == []
    finally:
        panel.close()


def test_embedded_color_dock_shows_active_node_target_badge():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel

    from app.color_grading import ColorGrade
    from app.video_editor_window import VideoEditorWindow

    QApplication.instance() or QApplication([])
    grade = ColorGrade()
    node = SimpleNamespace(label="Node 1", node_id="N1", color_grade=grade)
    editor = SimpleNamespace(
        _active_track=lambda: SimpleNamespace(id=2, display_name="Clip Track"),
        _active_color_grade=lambda: grade,
        _node_grade_target=node,
        _load_lut_file=lambda: None,
        _on_lut_strength_changed=lambda value: None,
        _on_color_reset=lambda: None,
        _on_color_luma_changed=lambda region, value: None,
        _on_color_wheel_changed=lambda region, x, y: None,
        _on_color_slider_changed=lambda key, value: None,
        _update_wheel_readouts=lambda region, x, y: None,
        _sync_color_power_window_overlay=lambda: None,
    )
    editor._refresh_color_target_badge = (
        lambda: VideoEditorWindow._refresh_color_target_badge(editor)
    )
    editor._refresh_color_preset_btn_label = (
        lambda: VideoEditorWindow._refresh_color_preset_btn_label(editor)
    )
    editor._build_color_preset_menu = (
        lambda: VideoEditorWindow._build_color_preset_menu(editor)
    )
    editor._sync_color_panel = (
        lambda: VideoEditorWindow._sync_color_panel(editor)
    )

    panel = VideoEditorWindow._build_color_compact_palette_panel(editor)
    try:
        badge = panel.findChild(QLabel, "ColorTargetBadge")

        assert badge is not None
        assert "Node 1" in badge.text()
        assert "N1" in badge.text()
    finally:
        panel.close()


def test_compact_color_slider_refreshes_current_preview_frame():
    from app.color_grading import ColorGrade
    from app.video_editor_window import VideoEditorWindow

    grade = ColorGrade()
    calls = []

    class _Player:
        def clear_preview_prerender_cache(self):
            calls.append("clear_cache")

        def refresh_current_frame(self):
            calls.append("refresh")

        def position(self):
            return 0

        def set_position(self, _pos):
            calls.append("seek")

    track = SimpleNamespace(color_grade=grade, node_item_chain=None)
    editor = SimpleNamespace(
        _player=_Player(),
        _active_track=lambda: track,
        _active_color_grade=lambda: grade,
        _node_grade_target=None,
        _refresh_color_preset_btn_label=lambda: calls.append("label"),
    )
    editor._commit_color_preview_edit = (
        lambda rebuild_chain=False: VideoEditorWindow._commit_color_preview_edit(
            editor,
            rebuild_chain=rebuild_chain,
        )
    )

    VideoEditorWindow._on_color_slider_changed(editor, "contrast", 72)

    assert grade.contrast == 72
    assert calls == ["label", "clear_cache", "refresh"]


def test_color_edit_rebuilds_when_bound_node_is_missing_from_preview_chain():
    from app.color_grading import ColorGrade
    from app.video_editor_window import VideoEditorWindow

    grade = ColorGrade()
    target = SimpleNamespace(color_grade=grade)
    other = SimpleNamespace(color_grade=ColorGrade())
    calls = []

    class _Player:
        def clear_preview_prerender_cache(self):
            calls.append("clear_cache")

        def refresh_current_frame(self):
            calls.append("refresh")

    track = SimpleNamespace(color_grade=grade, node_item_chain=[(other, [])])
    editor = SimpleNamespace(
        _player=_Player(),
        _active_track=lambda: track,
        _active_color_grade=lambda: grade,
        _node_grade_target=target,
        _refresh_color_preset_btn_label=lambda: calls.append("label"),
        _rebuild_active_chain=lambda: calls.append("rebuild"),
    )
    editor._commit_color_preview_edit = (
        lambda rebuild_chain=False: VideoEditorWindow._commit_color_preview_edit(
            editor,
            rebuild_chain=rebuild_chain,
        )
    )

    VideoEditorWindow._on_color_slider_changed(editor, "brightness", 25)

    assert grade.brightness == 25
    assert calls == ["label", "rebuild", "clear_cache", "refresh"]
    assert track.node_item_chain[0][0] is target


def test_color_page_fallback_active_track_grade_and_primary_slider_emit():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.color_grading import ColorGrade
    from app.color_page_window import ColorPageWindow

    QApplication.instance() or QApplication([])

    grade = ColorGrade()
    track = SimpleNamespace(color_grade=grade)
    editor = SimpleNamespace(_active_track=lambda: track)
    win = ColorPageWindow(editor=editor)
    emitted = []
    win.grade_changed.connect(lambda g: emitted.append(g))
    try:
        win._on_primary_slider("saturation", 44)

        assert grade.saturation == 44
        assert emitted[-1] is grade
    finally:
        win.close()


def test_default_color_node_is_wired_into_preview_chain():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.workbench.node_graph.widget import NodeGraphWidget

    QApplication.instance() or QApplication([])

    widget = NodeGraphWidget()
    track = SimpleNamespace(node_graph_view_data=None)
    widget.set_track(track)

    try:
        scene = widget.scene
        node = scene._serial_nodes[0]
        chain = scene.evaluate_chain_nodes_to(scene._out_node)

        assert node in chain
    finally:
        widget.close()


def test_unwired_legacy_color_node_chain_is_repaired():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.workbench.node_graph.scene import NodeGraphScene

    QApplication.instance() or QApplication([])

    scene = NodeGraphScene()
    scene.load_from_data({
        "nodes": [
            {
                "id": "N1",
                "kind": "serial",
                "label": "Node 1",
                "x": -200,
                "y": -45,
            }
        ],
        "connections": [],
        "next_id": 2,
    })

    assert scene.evaluate_chain_nodes_to(scene._out_node) == []
    assert scene.ensure_default_chain() is True
    assert [getattr(n, "node_id", "") for n in scene.evaluate_chain_nodes_to(scene._out_node)] == ["N1"]


def test_workbench_set_track_repairs_and_persists_unwired_color_graph():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.workbench.node_graph.widget import NodeGraphWidget

    QApplication.instance() or QApplication([])

    track = SimpleNamespace(
        node_graph_view_data={
            "nodes": [
                {
                    "id": "N1",
                    "kind": "serial",
                    "label": "Node 1",
                    "x": -200,
                    "y": -45,
                }
            ],
            "connections": [],
            "next_id": 2,
        }
    )
    widget = NodeGraphWidget()
    try:
        widget.set_track(track)

        saved = track.node_graph_view_data
        assert len(saved["connections"]) == 2
        assert [getattr(n, "node_id", "") for n in widget.scene.evaluate_chain_nodes_to(widget.scene._out_node)] == ["N1"]
    finally:
        widget.close()


def test_color_node_preview_export_cpu_parity(tmp_path):
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.color_grading import ColorGrade
    from app.project_player import _apply_node_effect_player
    from app.video_exporter import VideoExportThread
    from app.workbench.node_graph.items.node_item import NodeItem

    QApplication.instance() or QApplication([])

    rgb = np.array(
        [
            [[20, 40, 60], [180, 160, 140]],
            [[80, 90, 100], [220, 200, 180]],
        ],
        dtype=np.uint8,
    )
    node = NodeItem("N1", "Node 1")
    node.color_grade = ColorGrade(brightness=25, contrast=20, saturation=30)

    preview = _apply_node_effect_player(node, rgb.copy(), [], 0)
    exporter = VideoExportThread(
        tmp_path / "source.mp4",
        tmp_path / "out.mp4",
        [(0, 1000, 1.0)],
        node_item_chain=[(node, [])],
    )
    try:
        exported = exporter._apply_node_chain_cpu(rgb.copy(), 0)

        np.testing.assert_array_equal(exported, preview)
    finally:
        exporter.deleteLater()


def test_color_preview_compare_before_and_split_are_preview_only():
    from app.color_grading import ColorGrade
    from app.project_player import _apply_node_chain_preview_compare, _apply_node_effect_player
    from app.workbench.node_graph.items.node_item import NodeItem

    rgb = np.array(
        [
            [[20, 40, 60], [180, 160, 140], [80, 90, 100], [220, 200, 180]],
            [[30, 50, 70], [170, 150, 130], [70, 80, 90], [210, 190, 170]],
        ],
        dtype=np.uint8,
    )
    node = NodeItem("N1", "Node 1")
    node.color_grade = ColorGrade(brightness=35, contrast=20, saturation=20)
    after = _apply_node_effect_player(node, rgb.copy(), [], 0)

    before = _apply_node_chain_preview_compare(rgb.copy(), [(node, [])], 0, "before")
    split = _apply_node_chain_preview_compare(rgb.copy(), [(node, [])], 0, "split")

    np.testing.assert_array_equal(before, rgb)
    assert split is not None
    np.testing.assert_array_equal(split[:, :2], rgb[:, :2])
    assert not np.array_equal(split[:, 2:], rgb[:, 2:])
    assert not np.any(np.all(split == np.array([255, 128, 87], dtype=np.uint8), axis=-1))
    assert not np.array_equal(after, rgb)


def test_color_split_compare_preserves_encoded_letterbox_matte():
    from app.color_grading import ColorGrade
    from app.project_player import _apply_node_chain_preview_compare
    from app.workbench.node_graph.items.node_item import NodeItem

    rgb = np.full((8, 10, 3), 5, dtype=np.uint8)
    rgb[2:6, 2:8] = np.array([80, 92, 104], dtype=np.uint8)
    node = NodeItem("N1", "Node 1")
    node.color_grade = ColorGrade(brightness=45, contrast=15, saturation=20)

    split = _apply_node_chain_preview_compare(rgb.copy(), [(node, [])], 0, "split")

    assert split is not None
    np.testing.assert_array_equal(split[:2], rgb[:2])
    np.testing.assert_array_equal(split[6:], rgb[6:])
    np.testing.assert_array_equal(split[:, :2], rgb[:, :2])
    np.testing.assert_array_equal(split[:, 8:], rgb[:, 8:])
    np.testing.assert_array_equal(split[2:6, 2:5], rgb[2:6, 2:5])
    assert not np.array_equal(split[2:6, 5:8], rgb[2:6, 5:8])


def test_color_workbench_selection_does_not_force_split_compare():
    from app.video_editor_window import VideoEditorWindow

    class _Widget:
        def __init__(self):
            self.visible = True

        def show(self):
            self.visible = True

        def hide(self):
            self.visible = False

        def setVisible(self, visible):
            self.visible = bool(visible)

        def setMinimumHeight(self, _value):
            pass

        def setMaximumHeight(self, _value):
            pass

        def updateGeometry(self):
            pass

    class _Stack:
        def __init__(self):
            self.current = None

        def setCurrentWidget(self, widget):
            self.current = widget

    track = SimpleNamespace()
    color_page = _Widget()
    edit_page = _Widget()
    editor = SimpleNamespace(
        _color_popout=None,
        _color_header_widget=_Widget(),
        _color_row_host=_Widget(),
        _workbench_stack=_Stack(),
        _color_workbench_panel=color_page,
        _workbench_panel=edit_page,
        _set_color_reference_workspace_ratio=lambda _active: None,
        _active_track=lambda: track,
    )

    VideoEditorWindow._update_color_dock_visibility(
        editor,
        SimpleNamespace(color_grade=object()),
    )

    assert editor._workbench_stack.current is color_page
    assert not hasattr(track, "preview_color_compare_mode")


def test_color_split_compare_overlay_uses_white_before_after_labels():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import VideoEditorWindow

    QApplication.instance() or QApplication([])

    class _Painter:
        def __init__(self):
            self.lines = []
            self.texts = []
            self.pens = []

        def save(self):
            pass

        def restore(self):
            pass

        def setRenderHint(self, *_args):
            pass

        def setPen(self, pen):
            self.pens.append(pen)

        def setBrush(self, *_args):
            pass

        def setFont(self, *_args):
            pass

        def drawLine(self, *args):
            self.lines.append(args)

        def drawRoundedRect(self, *_args):
            pass

        def drawText(self, _rect, _flags, text):
            self.texts.append(text)

    track = SimpleNamespace(preview_color_compare_mode="split")
    editor = SimpleNamespace(_active_track=lambda: track)
    painter = _Painter()

    VideoEditorWindow._paint_comparison_canvas_overlay(editor, painter, 320, 180)

    assert painter.lines == [(160, 10, 160, 170)]
    assert painter.texts == ["Before", "After"]


def test_color_compare_mode_sets_runtime_track_flag_only():
    from app.video_editor_window import VideoEditorWindow

    calls = []
    track = SimpleNamespace()

    class _Player:
        def clear_preview_prerender_cache(self):
            calls.append("clear")

        def refresh_current_frame(self):
            calls.append("refresh")

    editor = SimpleNamespace(
        _active_track=lambda: track,
        _player=_Player(),
        _sync_color_compare_buttons=lambda: calls.append("sync"),
        _flash_status=lambda text: calls.append(text),
    )

    VideoEditorWindow._set_color_preview_compare_mode(editor, "before")
    assert track.preview_color_compare_mode == "before"
    assert calls[:3] == ["sync", "clear", "refresh"]

    VideoEditorWindow._set_color_preview_compare_mode(editor, "before")
    assert track.preview_color_compare_mode == ""
    assert "Color compare off" in calls


def test_color_preview_parity_qa_script_smoke():
    from tools.qa_color_preview_parity import run_color_preview_parity_qa

    report = run_color_preview_parity_qa()

    assert report["ok"] is True
    assert {row["check"] for row in report["checks"]} >= {
        "default_node_wired",
        "legacy_graph_repaired",
        "preview_export_parity",
        "preview_compare_modes",
    }


def test_color_tab_switch_does_not_force_node_graph_selection():
    import inspect

    from app.video_editor_window import VideoEditorWindow

    source = inspect.getsource(VideoEditorWindow._show_color_dock_page)

    assert "clearSelection" not in source
    assert "setSelected" not in source


def test_color_workspace_ratio_keeps_viewer_visible():
    from app.video_editor_layout_specs import (
        VIEWER_TOP_STRETCH,
        WORKBENCH_SLOT_MIN_WIDTH,
        WORKBENCH_TOP_STRETCH,
    )
    from app.video_editor_window import VideoEditorWindow

    class _Widget:
        def __init__(self):
            self.minimum_width = None
            self.updated = False

        def setMinimumWidth(self, value):
            self.minimum_width = int(value)

        def updateGeometry(self):
            self.updated = True

    class _Layout:
        def __init__(self, viewer, workbench):
            self._items = [viewer, workbench]
            self.stretches = {}

        def indexOf(self, widget):
            return self._items.index(widget) if widget in self._items else -1

        def setStretch(self, index, value):
            self.stretches[int(index)] = int(value)

    viewer = _Widget()
    workbench = _Widget()
    top = _Widget()
    layout = _Layout(viewer, workbench)
    editor = SimpleNamespace(
        _top_work_layout=layout,
        _viewer_column=viewer,
        _top_workbench_slot=workbench,
        _top_work_area=top,
    )

    VideoEditorWindow._set_color_reference_workspace_ratio(editor, True)

    assert workbench.minimum_width == WORKBENCH_SLOT_MIN_WIDTH
    assert layout.stretches[0] == VIEWER_TOP_STRETCH
    assert layout.stretches[1] == WORKBENCH_TOP_STRETCH
    assert viewer.updated is True
    assert workbench.updated is True


def test_color_tab_preview_guard_restores_last_good_frame():
    import os
    import time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor, QPixmap
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import VideoEditorWindow

    QApplication.instance() or QApplication([])

    good = QPixmap(96, 54)
    good.fill(QColor("#FF8057"))
    blank = QPixmap(16, 9)
    blank.fill(QColor("#000000"))
    calls = []

    class _Player:
        def position(self):
            return 500

    clip = SimpleNamespace(
        source_path="clip.mp4",
        timeline_in_ms=0,
        timeline_out_ms=1000,
    )
    editor = SimpleNamespace(
        _preview_pixmap=blank,
        _last_good_preview_pixmap=good,
        _preview_tab_guard_until_ms=time.monotonic() * 1000.0 + 1000.0,
        _player=_Player(),
        _tracks=[SimpleNamespace(clips=[clip])],
        _scale_preview_to_fit=lambda: calls.append("scale"),
        _preview_popout=None,
    )
    editor._preview_tab_guard_active = (
        lambda: VideoEditorWindow._preview_tab_guard_active(editor)
    )
    editor._active_renderable_clip_at_current_position = (
        lambda: VideoEditorWindow._active_renderable_clip_at_current_position(editor)
    )
    editor._pixmap_looks_like_blank_preview = (
        VideoEditorWindow._pixmap_looks_like_blank_preview
    )

    restored = VideoEditorWindow._restore_preview_if_tab_switch_blank(editor)

    assert restored is True
    assert editor._preview_pixmap.width() == 96
    assert editor._preview_pixmap.height() == 54
    assert calls == ["scale"]


def test_color_tab_preview_guard_does_not_replace_large_dark_frame():
    import os
    import time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor, QPixmap
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import VideoEditorWindow

    QApplication.instance() or QApplication([])

    dark = QPixmap(1280, 720)
    dark.fill(QColor("#000000"))
    good = QPixmap(96, 54)
    good.fill(QColor("#FF8057"))

    class _Player:
        def position(self):
            return 500

    clip = SimpleNamespace(
        source_path="clip.mp4",
        timeline_in_ms=0,
        timeline_out_ms=1000,
    )
    editor = SimpleNamespace(
        _preview_pixmap=dark,
        _last_good_preview_pixmap=good,
        _preview_tab_guard_until_ms=time.monotonic() * 1000.0 + 1000.0,
        _player=_Player(),
        _tracks=[SimpleNamespace(clips=[clip])],
        _scale_preview_to_fit=lambda: None,
        _preview_popout=None,
    )
    editor._preview_tab_guard_active = (
        lambda: VideoEditorWindow._preview_tab_guard_active(editor)
    )
    editor._active_renderable_clip_at_current_position = (
        lambda: VideoEditorWindow._active_renderable_clip_at_current_position(editor)
    )
    editor._pixmap_looks_like_blank_preview = (
        VideoEditorWindow._pixmap_looks_like_blank_preview
    )

    restored = VideoEditorWindow._restore_preview_if_tab_switch_blank(editor)

    assert restored is False
    assert editor._preview_pixmap.width() == 1280
    assert editor._preview_pixmap.height() == 720


def test_color_black_recovery_replaces_transient_large_black_frame():
    import os
    import time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor, QPixmap
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import VideoEditorWindow

    QApplication.instance() or QApplication([])

    dark = QPixmap(1280, 720)
    dark.fill(QColor("#000000"))
    good = QPixmap(96, 54)
    good.fill(QColor("#FF8057"))

    class _Player:
        def position(self):
            return 500

    clip = SimpleNamespace(
        source_path="clip.mp4",
        timeline_in_ms=0,
        timeline_out_ms=1000,
    )
    now = time.monotonic() * 1000.0
    editor = SimpleNamespace(
        _preview_pixmap=dark,
        _last_good_preview_pixmap=good,
        _preview_tab_guard_until_ms=now + 1000.0,
        _preview_black_recovery_until_ms=now + 1000.0,
        _player=_Player(),
        _tracks=[SimpleNamespace(clips=[clip])],
        _scale_preview_to_fit=lambda: None,
        _preview_popout=None,
    )
    editor._preview_tab_guard_active = (
        lambda: VideoEditorWindow._preview_tab_guard_active(editor)
    )
    editor._preview_black_recovery_active = (
        lambda: VideoEditorWindow._preview_black_recovery_active(editor)
    )
    editor._active_renderable_clip_at_current_position = (
        lambda: VideoEditorWindow._active_renderable_clip_at_current_position(editor)
    )
    editor._pixmap_looks_like_blank_preview = (
        VideoEditorWindow._pixmap_looks_like_blank_preview
    )
    editor._pixmap_looks_like_black_frame = (
        VideoEditorWindow._pixmap_looks_like_black_frame
    )

    restored = VideoEditorWindow._restore_preview_if_tab_switch_blank(editor)

    assert restored is True
    assert editor._preview_pixmap.width() == 96
    assert editor._preview_pixmap.height() == 54


def test_preview_renderable_content_includes_actor_only_tracks():
    from app.video_editor_window import VideoEditorWindow

    class _Player:
        def position(self):
            return 500

    live2d_clip = SimpleNamespace(start_ms=250, duration_ms=1000)
    editor = SimpleNamespace(
        _player=_Player(),
        _tracks=[],
        _live2d_actor_tracks=[SimpleNamespace(clips=[live2d_clip])],
        _spine_actor_tracks=[],
        _audio_tracks=[],
    )

    assert VideoEditorWindow._active_renderable_clip_at_current_position(editor)
    assert VideoEditorWindow._preview_has_renderable_content(editor)

    editor._live2d_actor_tracks = []
    editor._spine_actor_tracks = [
        SimpleNamespace(clips=[SimpleNamespace(start_ms=0, duration_ms=700)])
    ]

    assert VideoEditorWindow._active_renderable_clip_at_current_position(editor)
    assert VideoEditorWindow._preview_has_renderable_content(editor)


def test_preview_rgb_to_qimage_owns_actor_frame_copy():
    from app.video_editor_window import VideoEditorWindow

    rgb = np.zeros((4, 6, 3), dtype=np.uint8)
    rgb[:, :, 0] = 255

    qimg = VideoEditorWindow._qimage_from_preview_rgb(rgb)

    assert qimg is not None
    assert qimg.width() == 6
    assert qimg.height() == 4
    rgb[:, :, :] = 0
    assert qimg.pixelColor(0, 0).red() == 255


def test_knob_widget_grab_is_nonblank_with_glass_tile():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app.knob_widget import KnobWidget

    QApplication.instance() or QApplication([])
    knob = KnobWidget(label="Sat", value=25, minimum=-100, maximum=100, default=0, color="green", bipolar=True)
    pix = knob.grab()
    try:
        assert not pix.isNull()
        img = pix.toImage()
        nonblank = 0
        for y in range(img.height()):
            for x in range(img.width()):
                if img.pixelColor(x, y).alpha() > 0:
                    nonblank += 1
        assert nonblank > 500
    finally:
        knob.close()


def test_dialogue_cleanup_and_loudness_build_ffmpeg_chain():
    from app.audio_tracks import _build_effect_chain, default_effects_state
    from app.audio_workflow import dialogue_cleanup_effects, loudness_target

    effects = default_effects_state()
    effects.update(dialogue_cleanup_effects(strength=0.8, hum_remove=True, de_reverb=0.3))
    effects["loudness"] = loudness_target("podcast").to_effect_payload()

    chain = _build_effect_chain(effects)

    assert "highpass=f=" in chain
    assert "afftdn=nr=" in chain
    assert "equalizer=f=60" in chain
    assert "dynaudnorm" in chain
    assert "loudnorm=I=-16.00" in chain


def test_audio_workflow_presets_apply_clip_and_track_mix():
    from app.audio_workflow import apply_track_mix_preset
    from app.preset_library import apply_audio_preset_to_clip, presets_by_kind

    preset = next(p for p in presets_by_kind("audio") if p.id == "audio-dialogue-cleanup-strong")
    clip = SimpleNamespace(effects={}, gain=1.0, volume_points=[])

    assert apply_audio_preset_to_clip(clip, preset)
    assert clip.effects["dialogue_cleanup"]["enabled"] is True
    assert clip.effects["deesser"]["enabled"] is True

    track = SimpleNamespace(volume=1.0, pan=0.0)
    changed = apply_track_mix_preset(
        track,
        {"bus_id": "dialogue", "label": "Voice", "volume": 0.82, "pan": -0.1, "automation_points": [(0.0, 1.0), (1.0, 0.7)]},
    )
    assert changed
    assert track.bus_id == "dialogue"
    assert track.label == "Voice"
    assert track.automation_points[-1] == (1.0, 0.7)


def test_fairlight_routing_matrix_and_loudness_delivery_report():
    from app.audio_workflow import (
        audio_delivery_qa_gate,
        build_default_routing_matrix,
        fairlight_product_capabilities,
        loudness_delivery_report,
    )

    matrix = build_default_routing_matrix([
        {"id": 1, "role": "dialogue"},
        {"id": 2, "role": "music"},
        {"id": 3, "role": "sfx"},
    ])
    report = loudness_delivery_report(
        {"integrated_lufs": -14.4, "true_peak_db": -1.2, "lra": 8.0},
        "shortform",
    )
    gate = audio_delivery_qa_gate(
        {"integrated_lufs": -14.4, "true_peak_db": -1.2, "lra": 8.0},
        target="shortform",
        routing=matrix,
    )
    caps = fairlight_product_capabilities()

    assert matrix.track_routes == {"1": "dialogue", "2": "music", "3": "sfx"}
    assert matrix.validation_warnings() == []
    assert report["ok"] is True
    assert gate["ok"] is True
    assert gate["route_count"] == 3
    assert "true peak below delivery limit" in gate["qa_gates"]
    assert caps["routing_matrix"] is True
    assert caps["loudness_monitoring"] is True
    assert caps["adr_cue_model"] is True
    assert caps["immersive_audio_model"] is True
    assert caps["plugin_host_model"] is True


def test_professional_color_pipeline_payload_and_report_are_valid():
    from app.color_workflow import (
        build_professional_color_pipeline_payload,
        professional_color_pipeline_report,
    )

    payload = build_professional_color_pipeline_payload(
        hdr_metadata={"standard": "dolby_vision", "dynamic_metadata": True},
        restoration={
            "temporal_nr": 0.3,
            "spatial_nr": 0.2,
            "film_grain": 0.15,
            "deflicker": True,
            "dead_pixel_repair": True,
            "dust_dirt_removal": True,
        },
    )
    report = professional_color_pipeline_report(payload)

    assert report["ok"] is True
    assert report["checks"]["float_scene_linear"] is True
    assert report["checks"]["raw_sidecar"] is True
    assert report["checks"]["hdr_metadata_valid"] is True
    assert report["checks"]["advanced_toolset"] is True
    assert report["checks"]["secondary_tracking"] is True
    assert report["checks"]["beauty_repair"] is True
    assert report["summary"]["hdr_standard"] == "dolby_vision"
    assert report["summary"]["hue_curve_sets"] == 3
    assert report["summary"]["warper_points"] == 2
    assert report["summary"]["beauty_repair_tools"] == 4
    assert payload["product_capabilities"]["color"]["raw_controls"] is True
    assert payload["product_capabilities"]["color"]["log_wheels"] is True
    assert payload["product_capabilities"]["color"]["color_warper"] is True
    assert payload["product_capabilities"]["color"]["object_removal"] is True
    assert payload["product_capabilities"]["color"]["hdr10plus_metadata"] is True
    assert payload["color_workflow"]["qualifier"]["denoise_radius"] == 2
    assert payload["color_workflow"]["window"]["track_object"] is True


def test_fairlight_engine_report_models_realtime_graph_adr_and_sfx():
    from app.audio_workflow import (
        ADRCue,
        ElasticAudioRetime,
        SFXLibraryItem,
        build_default_routing_matrix,
        fairlight_engine_report,
        fairlight_mixer_stress_report,
        fairlight_product_capabilities,
    )

    matrix = build_default_routing_matrix([
        {"id": 1, "role": "dialogue"},
        {"id": 2, "role": "music"},
        {"id": 3, "role": "sfx"},
    ])
    report = fairlight_engine_report(
        matrix,
        adr_cues=[ADRCue("cue_1", 1000, 2000, "Line", take_count=1)],
        retimes=[ElasticAudioRetime("clip_1", 1000, 1200)],
        sfx_items=[SFXLibraryItem("click", "sfx/click.wav", ("ui",))],
    )
    caps = fairlight_product_capabilities()

    assert report["ok"] is True
    assert report["checks"]["realtime_graph"] is True
    assert report["checks"]["latency_compensation"] is True
    assert report["checks"]["hundreds_track_stress_contract"] is True
    assert report["summary"]["nodes"] >= 8
    stress = fairlight_mixer_stress_report(virtual_tracks=512, channel_layout="5.1")
    assert stress["ok"] is True
    assert stress["virtual_tracks"] == 512
    assert stress["checks"]["surround_block_size"] is True
    large_stress = fairlight_mixer_stress_report(virtual_tracks=2000, channel_layout="5.1")
    assert large_stress["ok"] is True
    assert large_stress["checks"]["declared_limit_covers_stress"] is True
    assert caps["max_tracks"] >= 512
    assert caps["adr_cues"] is True
    assert caps["elastic_wave"] is True
    assert caps["foley_library"] is True


def test_post_pipeline_vfx_ingest_deliver_and_cache_models(tmp_path):
    from app.post_pipeline_workflow import (
        ProxyRenderCachePolicy,
        build_mini_vfx_node_graph,
        build_vfx_repair_plan,
        deliver_page_matrix,
        ingest_clone_manifest,
        post_pipeline_product_capabilities,
        vfx_node_graph_qa_report,
    )

    media = tmp_path / "clip.mov"
    media.write_bytes(b"abc")
    plan = build_vfx_repair_plan([
        {"x": 0.2, "y": 0.2, "feather": 0.05},
        {"x": 0.8, "y": 0.2, "feather": 0.05},
        {"x": 0.8, "y": 0.7, "feather": 0.08},
    ], source_frame_ms=1200)
    manifest = ingest_clone_manifest([media])
    delivery = deliver_page_matrix()
    cache = ProxyRenderCachePolicy(proxy_resolution="720p").to_dict()
    graph = build_mini_vfx_node_graph(plan, include_keyer=True, include_title_merge=True)
    graph_qa = vfx_node_graph_qa_report([graph])
    caps = post_pipeline_product_capabilities()

    assert plan.clean_plate.target_rect["w"] > 0.5
    assert plan.planar_tracker["enabled"] is True
    assert graph.validation_warnings() == []
    assert {"media_in", "chroma_key", "b_spline_roto", "clean_plate", "merge", "output"} <= graph.kinds()
    assert graph.to_dict()["cache_policy"] == "preview_export_locked"
    assert graph_qa["ok"] is True
    assert graph_qa["graph_count"] == 1
    assert graph_qa["kind_counts"]["clean_plate"] == 1
    assert manifest["verified_clone"] is True
    assert manifest["items"][0]["checksum_sha256"]
    assert any(row["id"] == "uhd_hdr" for row in delivery)
    assert cache["render_cache"] is True
    assert caps["vfx"]["clean_plate"] is True
    assert caps["vfx"]["fusion_graph_model"] is True
    assert caps["vfx"]["mini_node_compositor"] is True
    assert caps["vfx"]["true_3d_workspace_model"] is True
    assert caps["performance"]["render_cache"] is True
    assert caps["post_pipeline"]["deliver_page"] is True
    assert caps["hardware"]["color_panel_mapping_model"] is True


def test_professional_fusion_graph_and_deliver_codec_matrix_are_valid():
    from app.post_pipeline_workflow import (
        build_professional_fusion_compositor_graph,
        collaboration_readiness_report,
        local_ml_readiness_report,
        professional_deliver_codec_matrix,
        professional_post_pipeline_report,
        studio_hardware_readiness_report,
        vfx_node_graph_qa_report,
    )

    graph = build_professional_fusion_compositor_graph()
    qa = vfx_node_graph_qa_report([graph])
    codecs = professional_deliver_codec_matrix()
    report = professional_post_pipeline_report()
    local_ml = local_ml_readiness_report()
    collaboration = collaboration_readiness_report()
    hardware = studio_hardware_readiness_report()

    assert qa["ok"] is True
    assert {"camera_3d", "light_3d", "particles_3d", "fbx_import", "alembic_import"} <= graph.kinds()
    assert {row["codec"] for row in codecs} >= {"prores_4444_xq", "dnxhr_hqx", "openexr", "dpx_10bit_log"}
    assert all(row["bit_depth"] >= 10 for row in codecs)
    assert local_ml["ok"] is True
    assert local_ml["checks"]["no_cloud_dependency"] is True
    assert collaboration["ok"] is True
    assert collaboration["checks"]["cloud_handoff_hooks"] is True
    assert hardware["ok"] is True
    assert hardware["checks"]["external_monitoring"] is True
    assert report["ok"] is True
    assert report["summary"]["codec_jobs"] == 4
    assert report["summary"]["local_ml_features"] >= 6
    assert report["summary"]["hardware_devices"] >= 8


def test_professional_workflow_payload_builder_attaches_audio_ingest_deliver_and_cache(tmp_path):
    from app.professional_readiness import audit_resolve_post_pipeline_parity
    from app.professional_workflow_payloads import attach_professional_workflow_payloads

    media = tmp_path / "capture.mp4"
    media.write_bytes(b"capture")
    doc = {
        "project_settings": {"proxy_resolution": "720p"},
        "media_pool": [{"path": str(media)}],
        "audio_tracks": [
            {"id": 1, "role": "dialogue", "clips": []},
            {"id": 2, "role": "music", "clips": []},
        ],
    }

    enriched = attach_professional_workflow_payloads(doc, deliver_profile_ids=["web_1080p", "uhd_hdr"])
    report = audit_resolve_post_pipeline_parity(enriched)

    assert "audio_routing_matrix" not in doc
    assert enriched["audio_routing_matrix"]["track_routes"] == {"1": "dialogue", "2": "music"}
    assert enriched["proxy_render_cache"]["proxy_resolution"] == "720p"
    assert [job["id"] for job in enriched["deliver_jobs"]] == ["web_1080p", "uhd_hdr"]
    assert enriched["ingest_clone_manifest"]["item_count"] == 1
    assert enriched["project_settings"]["post_pipeline_workflows"]["deliver_jobs"] == 2

    def status(category: str, feature_id: str) -> str:
        for feature in report["categories"][category]["features"]:
            if feature["id"] == feature_id:
                return feature["status"]
        raise AssertionError(feature_id)

    assert status("audio", "flexbus_routing") == "supported"
    assert status("post_pipeline", "deliver_page") == "supported"
    assert enriched["color_pipeline_payload"]["color_processing_pipeline"]["processing_bits"] == 32
    assert enriched["fairlight_engine_payload"]["checks"]["realtime_graph"] is True
    assert enriched["professional_deliver_jobs"][0]["bit_depth"] >= 10
    assert enriched["vfx_node_graphs"][0]["validation_warnings"] == []
    assert enriched["local_ml_status"]["ok"] is True
    assert enriched["audio_mixer_stress"]["virtual_tracks"] == 2000
    assert enriched["collaboration_status"]["ok"] is True
    assert enriched["hardware_status"]["ok"] is True
    assert enriched["performance_capabilities"]["smart_reframe"] is True
    assert enriched["post_pipeline"]["timeline_locking"] is True
    assert enriched["hardware_capabilities"]["decklink"] is True


def test_professional_pipeline_next_qa_tool_writes_report(tmp_path, monkeypatch):
    import json

    from app.qa_dashboard import QADashboardDialog
    from tools import qa_professional_pipeline_next

    out = tmp_path / "professional_pipeline_next_qa.json"
    command = QADashboardDialog._command_for_row({
        "kind": "professional_pipeline_next",
        "path": str(out),
    })
    monkeypatch.setattr(
        "sys.argv",
        ["qa_professional_pipeline_next.py", "--out", str(out)],
    )

    assert command is not None
    assert "qa_professional_pipeline_next.py" in " ".join(command)
    assert qa_professional_pipeline_next.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["summary"]["color_score"] >= 70
    assert payload["summary"]["audio_score"] >= 70
    assert payload["summary"]["vfx_score"] >= 70
    assert payload["summary"]["local_ml_features"] >= 6
    assert payload["summary"]["audio_stress_tracks"] == 2000
    assert payload["summary"]["hardware_devices"] >= 8


def test_professional_runtime_verification_executes_synthetic_paths(tmp_path, monkeypatch):
    import json

    from app.professional_runtime import (
        build_vfx_runtime_execution_plan,
        professional_runtime_verification_report,
        run_professional_color_runtime_sample,
        run_local_ml_runtime_probe,
    )
    from app.qa_dashboard import QADashboardDialog
    from tools import qa_professional_runtime_next

    color = run_professional_color_runtime_sample()
    vfx = build_vfx_runtime_execution_plan()
    ml = run_local_ml_runtime_probe(tmp_path)
    report = professional_runtime_verification_report(out_dir=tmp_path)
    out = tmp_path / "professional_runtime_next_qa.json"
    command = QADashboardDialog._command_for_row({
        "kind": "professional_runtime_next",
        "path": str(out),
    })
    monkeypatch.setattr(
        "sys.argv",
        ["qa_professional_runtime_next.py", "--out", str(out)],
    )

    assert color["ok"] is True
    assert color["checks"]["preview_export_same"] is True
    assert color["mean_abs_delta"] >= 1.0
    assert vfx["ok"] is True
    assert vfx["execution_order"][-1] == "out"
    assert vfx["cache_boundaries"]
    assert ml["ok"] is True
    assert ml["checks"]["local_only"] is True
    assert report["ok"] is True
    assert report["summary"]["audio_stress_tracks"] == 2000
    assert command is not None
    assert "qa_professional_runtime_next.py" in " ".join(command)
    assert qa_professional_runtime_next.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["checks"]["color_runtime"] is True
    assert payload["checks"]["local_ml_probe"] is True


def test_color_page_advanced_controls_emit_grade_payload():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.color_grading import ColorGrade, apply_to_rgb
    from app.color_page_window import ColorPageWindow

    QApplication.instance() or QApplication([])
    grade = ColorGrade()
    track = SimpleNamespace(color_grade=grade)
    editor = SimpleNamespace(_active_track=lambda: track)
    win = ColorPageWindow(editor=editor)
    emitted = []
    win.grade_changed.connect(lambda g: emitted.append(g))
    try:
        rgb = np.array([[[220, 60, 45], [40, 180, 60]]], dtype=np.uint8)
        win._adv_enabled.setChecked(True)
        win._adv_hdr_shadow.setValue(12)
        win._adv_hdr_highlight.setValue(-18)
        win._adv_log_shadow_r.setValue(20)
        win._adv_hue_sat_skin.setValue(15)
        win._adv_warper_skin.setValue(8)
        win.update_frame(rgb, grade)

        out = apply_to_rgb(rgb, grade)

        assert emitted[-1] is grade
        assert grade.advanced_color_toolset["hdr_zones"]["shadow"] == 12
        assert grade.advanced_color_toolset["warper_points"][0]["hue_shift"] == 8.0
        assert not np.array_equal(out, rgb)
        assert win._adv_split_preview._before_pixmap is not None
        assert win._adv_split_preview._after_pixmap is not None
        assert win._advanced_status.text()
        assert "Scope QA:" in win._scope_warning_status.toolTip()

        win._adv_bypass.setChecked(True)
        assert grade.advanced_color_toolset["enabled"] is False
        assert np.array_equal(apply_to_rgb(rgb, grade), rgb)

        win._reset_advanced_color_controls()
        assert grade.advanced_color_toolset == {}
    finally:
        win.close()


def test_preview_popout_uses_viewer_controls_and_dock_signal():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

    from app.video_editor_window import PreviewPopoutWindow

    QApplication.instance() or QApplication([])
    win = PreviewPopoutWindow()
    seen = []
    try:
        win.dock_requested.connect(lambda: seen.append("dock"))
        win.stop_requested.connect(lambda: seen.append("stop"))
        win.prev_frame_requested.connect(lambda: seen.append("prev"))
        win.next_frame_requested.connect(lambda: seen.append("next"))
        win.mark_in_requested.connect(lambda: seen.append("mark_in"))
        win.mark_out_requested.connect(lambda: seen.append("mark_out"))
        win.clear_range_requested.connect(lambda: seen.append("clear"))
        win.marker_requested.connect(lambda: seen.append("marker"))
        win.fit_requested.connect(lambda: seen.append("fit"))

        win.set_time_text("0:03 / 0:10")
        win.set_speed_label(2.0)
        win.update_frame(QImage(320, 180, QImage.Format.Format_RGB32))
        win.fit_to_view()

        assert win.findChild(QWidget, "PlayBar") is win._controls_host
        assert win.layout().indexOf(win._controls_host) >= 0
        assert win.findChild(QPushButton, "PreviewPopoutDockButton") is not None
        assert win.findChild(QPushButton, "ViewerDropdownButton") is win._fit_btn
        assert win.findChild(QPushButton, "PlayButton") is win._play_btn
        assert win.findChild(QLabel, "TimeLabel").text() == "0:03 / 0:10"
        assert win.findChild(QLabel, "SpeedLabel").text() == "2x"
        assert win._mark_in_btn.isHidden() is True
        assert win._mark_out_btn.isHidden() is True
        assert win._clear_btn.isHidden() is True
        assert win._marker_btn.isHidden() is True
        assert win._fit_btn.isHidden() is False

        win._dock_btn.click()
        win._stop_btn.click()
        win._prev_btn.click()
        win._next_btn.click()
        win._mark_in_btn.click()
        win._mark_out_btn.click()
        win._clear_btn.click()
        win._marker_btn.click()
        win._fit_btn.click()

        assert seen == [
            "dock",
            "stop",
            "prev",
            "next",
            "mark_in",
            "mark_out",
            "clear",
            "marker",
            "fit",
        ]
    finally:
        win.close()


def test_preview_header_keeps_viewer_popout_button_visible():
    import inspect

    from app.video_editor_window import VideoEditorWindow

    source = inspect.getsource(VideoEditorWindow._build_ui)
    add_idx = source.index("pheader_layout.addWidget(self.popout_btn)")
    show_idx = source.index("self.popout_btn.show()", add_idx)
    next_section_idx = source.index("viewer_column_layout.addWidget(preview_header)", add_idx)

    assert add_idx < show_idx < next_section_idx
    assert "self.popout_btn.hide()" not in source[add_idx:next_section_idx]


def test_audio_mixer_exposes_routing_and_loudness_payloads():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.audio_mixer_panel import AudioMixerPanel

    QApplication.instance() or QApplication([])
    panel = AudioMixerPanel()
    try:
        tracks = [
            SimpleNamespace(id=1, label="Voice", role="dialogue", bus_id="dialogue", volume=1.0, pan=0.0),
            SimpleNamespace(id=2, label="Music", role="music", bus_id="music", volume=0.8, pan=0.0),
        ]
        panel.refresh_tracks(tracks)
        routing = panel.routing_matrix_payload(tracks)
        loudness = panel.loudness_delivery_payload(
            {"integrated_lufs": -14.2, "true_peak_db": -1.1, "lra": 8.0},
            target="shortform",
        )

        assert routing["track_routes"] == {"1": "dialogue", "2": "music"}
        assert len(routing["sends"]) >= 2
        assert loudness["ok"] is True
        assert loudness["route_count"] == 2
        assert loudness["loudness"]["target_id"] == "shortform"
        assert "all track routes and sends resolve" in loudness["qa_gates"][-1]
        assert "2 tracks" in panel._routing_summary.text()
        assert panel._routing_btn.text() == "Routing"
        assert panel._loudness_btn.text() == "Loudness"
    finally:
        panel.close()


def test_render_queue_panel_exposes_deliver_jobs_payload():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.render_queue_panel import RenderQueuePanel

    QApplication.instance() or QApplication([])
    panel = RenderQueuePanel()
    try:
        jobs = panel.deliver_jobs_payload(["uhd_hdr"])

        assert [job["id"] for job in jobs] == ["uhd_hdr"]
        assert jobs[0]["color_space"] == "Rec.2020 PQ"
        assert "HDR 1" in panel.deliver_preset_summary_text(["uhd_hdr"])
    finally:
        panel.close()


def test_media_pool_exposes_ingest_manifest_and_proxy_metadata(tmp_path):
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.media_pool import MediaPool

    QApplication.instance() or QApplication([])
    media = tmp_path / "capture.mp4"
    media.write_bytes(b"media")
    pool = MediaPool()
    try:
        assert pool.add_path(media)
        item = pool._list.item(0)
        pool._list.setCurrentItem(item)
        manifest = pool.ingest_manifest_payload(selected_only=True)
        meta = pool._item_metadata_text(item)
        health = pool.media_health_payload()
        summary = pool.media_health_summary_text()

        assert manifest["item_count"] == 1
        assert manifest["items"][0]["checksum_sha256"]
        assert health["proxy_counts"]["missing"] == 1
        assert "proxy missing 1" in summary
        assert "Ingest: verified" in meta
        assert "Proxy:" in meta
    finally:
        pool.close()


def test_mask_editor_exports_vfx_repair_payload_from_polygon():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.mask_editor_window import MaskEditorWindow

    QApplication.instance() or QApplication([])
    rgb = np.zeros((32, 32, 3), dtype=np.uint8)
    node = SimpleNamespace(masks=[], update=lambda: None)
    win = MaskEditorWindow(rgb, node, frame_idx=1200)
    try:
        win._canvas.set_polygon_points([(0.2, 0.2), (0.8, 0.2), (0.8, 0.7), (0.2, 0.7)])
        payload = win.vfx_repair_payload()
        graph = win.vfx_node_graph_payload()
        summary = win.vfx_repair_summary_text()
        graph_summary = win.vfx_node_graph_summary_text()

        assert payload["roto"]["interpolation"] == "b_spline"
        assert payload["clean_plate"]["source_frame_ms"] == 1200
        assert payload["planar_tracker"]["enabled"] is True
        assert graph["output_node"] == "out"
        assert graph["validation_warnings"] == []
        assert any(node["kind"] == "clean_plate" for node in graph["nodes"])
        assert "planar tracker on" in summary
        assert "VFX node graph:" in graph_summary
        assert "ready" in graph_summary
        assert win._vfx_graph_btn.text() == "VFX Graph"
        win._accept()
        assert node.vfx_repair_plan["clean_plate"]["source_frame_ms"] == 1200
        assert node.vfx_node_graph["output_node"] == "out"
    finally:
        win.close()


def test_preset_preview_storyboard_describes_real_bake_targets():
    from app.preset_library import preset_by_id, preset_preview_storyboard

    effect = preset_preview_storyboard(preset_by_id("effect-punchy-gameplay"))
    color = preset_preview_storyboard(preset_by_id("color-hdr-zone-product-pop"))
    transition = preset_preview_storyboard(preset_by_id("transition-dip-white"))

    assert "clip_filter" in effect["bake_targets"]
    assert "detail" in effect["cues"]
    assert "color_grade" in color["bake_targets"]
    assert "advanced" in color["cues"]
    assert "transition" in transition["bake_targets"]
