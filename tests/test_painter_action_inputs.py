from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest
from types import SimpleNamespace


def test_numeric_color_overlay_and_pbr_preview_action_resource_contracts() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog
    from app.painter_action_contract import (
        PAINT_ACTION_PBR_PREVIEW_DEFAULT_PX,
        PAINT_ACTION_PBR_PREVIEW_MAX_PX,
        PAINT_ACTION_PBR_PREVIEW_MIN_PX,
        PAINT_ACTION_PBR_PREVIEW_RESOURCE_CONTRACT,
        PAINT_ACTION_PBR_RETAINED_ARRAY_BUDGET_BYTES,
        normalize_painter_pbr_preview_width,
    )

    registry = ActionRegistry(owner=None)
    color = registry.get_action_schema("paint.color.numeric.set")["params_schema"]
    color_values = color["properties"]["values"]
    assert color_values["minItems"] == color_values["maxItems"] == 3

    channel = registry.get_action_schema(
        "paint.selection.channel.options.set"
    )["params_schema"]
    opacity = channel["properties"]["overlay_opacity_percent"]
    assert opacity == {"type": "integer", "minimum": 0, "maximum": 100}

    pbr = registry.get_action_schema("paint.pbr.preview")["params_schema"]
    width = pbr["properties"]["width"]
    assert width == {
        "type": "integer",
        "minimum": PAINT_ACTION_PBR_PREVIEW_MIN_PX,
        "maximum": PAINT_ACTION_PBR_PREVIEW_MAX_PX,
    }
    assert PAINT_ACTION_PBR_PREVIEW_RESOURCE_CONTRACT == {
        "schema": "tigerstudio.painter.pbr_preview_resource_policy.v1",
        "source": "tiger_authored_measured_cpu_preview_resource_policy",
        "minimum_px": PAINT_ACTION_PBR_PREVIEW_MIN_PX,
        "maximum_px": PAINT_ACTION_PBR_PREVIEW_MAX_PX,
        "default_px": PAINT_ACTION_PBR_PREVIEW_DEFAULT_PX,
        "retained_array_budget_bytes": PAINT_ACTION_PBR_RETAINED_ARRAY_BUDGET_BYTES,
        "measured_backend": "cpu",
        "universal_latency_or_memory_safety_claim": False,
        "gpu_parity_claim": False,
        "visual_quality_threshold_claim": False,
    }
    for valid in (
        PAINT_ACTION_PBR_PREVIEW_MIN_PX,
        PAINT_ACTION_PBR_PREVIEW_DEFAULT_PX,
        PAINT_ACTION_PBR_PREVIEW_MAX_PX,
    ):
        assert normalize_painter_pbr_preview_width(valid) == valid
    for invalid in (True, 64.0, "64", None):
        with pytest.raises(TypeError):
            normalize_painter_pbr_preview_width(invalid)
    for invalid in (
        PAINT_ACTION_PBR_PREVIEW_MIN_PX - 1,
        PAINT_ACTION_PBR_PREVIEW_MAX_PX + 1,
    ):
        with pytest.raises(ValueError):
            normalize_painter_pbr_preview_width(invalid)

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid Action input reached owner resolution")

    with pytest.raises(ValueError):
        Adapter().paint_pbr_preview(width=PAINT_ACTION_PBR_PREVIEW_MAX_PX + 1)
    for invalid in ([1, 2], [1, 2, 3, 4], [True, 2, 3], ["1", 2, 3]):
        with pytest.raises((TypeError, ValueError)):
            Adapter().paint_color_numeric_set(space="rgb", values=invalid)
    with pytest.raises(TypeError):
        PaintDialog.preview_pbr_map_to_path(object(), "unused.png", width=True)


def test_alpha_channel_file_import_validates_before_owner_and_matches_schema(
    tmp_path: Path,
) -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid alpha-channel import reached owner resolution")

    adapter = Adapter()
    for invalid in (None, True, 1, "", " ", " source.psd", "source.psd "):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_selection_channels_import_file(path=invalid)
    for invalid in (tmp_path / "source.png", tmp_path / "missing.psd"):
        with pytest.raises(ValueError):
            adapter.paint_selection_channels_import_file(path=str(invalid))

    schema = ActionRegistry(owner=None).get_action_schema(
        "paint.selection.channels.import_file"
    )["params_schema"]
    assert schema["required"] == ["path"]
    assert schema["properties"]["path"]["minLength"] == 5
    assert "[Pp][Ss][Dd]" in schema["properties"]["path"]["pattern"]


def test_action_time_is_strict_nonnegative_integer() -> None:
    from app.painter_action_inputs import normalize_paint_time_ms

    assert normalize_paint_time_ms(0) == 0
    assert normalize_paint_time_ms(1234) == 1234
    with pytest.raises(ValueError, match="nonnegative"):
        normalize_paint_time_ms(-1)
    for invalid in (True, 1.0, "1", None):
        with pytest.raises(TypeError):
            normalize_paint_time_ms(invalid)


def test_optional_export_size_requires_zero_pair_or_positive_pair() -> None:
    from app.painter_action_inputs import optional_paint_export_size
    from app.painter_output import PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT

    assert optional_paint_export_size(0, 0) is None
    assert optional_paint_export_size(1920, 1080) == (1920, 1080)
    for invalid in ((1920, 0), (0, 1080), (-1, 1080), (1920, -1)):
        with pytest.raises(ValueError, match="both"):
            optional_paint_export_size(*invalid)
    with pytest.raises(ValueError, match="capacity"):
        optional_paint_export_size(PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT + 1, 1)
    for invalid in ((True, 1), (1.0, 1), ("1", 1), (None, 1)):
        with pytest.raises(TypeError):
            optional_paint_export_size(*invalid)


def test_flip_fill_and_mirror_actions_validate_before_owner_and_match_schema() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_inputs import (
        validate_canvas_flip_action,
        validate_fill_color_action,
        validate_fill_color_pair_action,
        validate_mirror_action,
    )

    assert validate_canvas_flip_action("horizontal") == "horizontal"
    assert validate_canvas_flip_action("vertical") == "vertical"
    assert validate_fill_color_action("  #102030  ", field="color") == "#102030"
    assert validate_fill_color_pair_action(
        color1="#000000",
        color2="#FFFFFF",
    ) == ("#000000", "#FFFFFF")
    assert validate_mirror_action(x=True) == (True, None)
    assert validate_mirror_action(y=False) == (None, False)

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid flip/fill/mirror input reached owner resolution")

    adapter = Adapter()
    for axis in (None, True, "", "x", "Horizontal", " horizontal "):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_canvas_flip(axis=axis)
    for color in (None, True, "", "   ", "not-a-color"):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_fill_solid(color=color)
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_fill_gradient(color1=color, color2="#FFFFFF")
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_fill_pattern(color1="#000000", color2=color)
    for params in ({}, {"x": None}, {"y": 0}, {"x": "true"}):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_mirror_set(**params)

    registry = ActionRegistry(owner=None)
    flip_schema = registry.get_action_schema("paint.canvas.flip")["params_schema"]
    solid_schema = registry.get_action_schema("paint.fill.solid")["params_schema"]
    gradient_schema = registry.get_action_schema("paint.fill.gradient")["params_schema"]
    pattern_schema = registry.get_action_schema("paint.fill.pattern")["params_schema"]
    mirror_schema = registry.get_action_schema("paint.mirror.set")["params_schema"]
    assert flip_schema["required"] == ["axis"]
    assert flip_schema["properties"]["axis"]["enum"] == ["horizontal", "vertical"]
    assert solid_schema["required"] == ["color"]
    assert gradient_schema["required"] == ["color1", "color2"]
    assert pattern_schema["required"] == ["color1", "color2"]
    assert mirror_schema["anyOf"] == [{"required": ["x"]}, {"required": ["y"]}]


def test_layer_mask_source_and_apply_actions_validate_before_owner_and_match_schema() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_inputs import validate_layer_mask_source_action

    assert validate_layer_mask_source_action(
        layer_id=" layer:1 ",
        mask_type="selection",
    ) == ("layer:1", "selection")

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid layer-mask input reached owner resolution")

    adapter = Adapter()
    for layer_id in (None, True, "   "):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_layer_mask_from_selection(layer_id=layer_id)
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_layer_mask_apply(layer_id=layer_id)
    for path_id in (None, True, "", "   "):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_layer_mask_from_path(path_id=path_id)
    for mask_type in (None, True, "", "Selection", "from_path", "all"):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_layer_mask_create(mask_type=mask_type)

    registry = ActionRegistry(owner=None)
    selection_schema = registry.get_action_schema(
        "paint.layer.mask_from_selection"
    )["params_schema"]
    path_schema = registry.get_action_schema("paint.layer.mask_from_path")[
        "params_schema"
    ]
    create_schema = registry.get_action_schema("paint.layer.mask_create")[
        "params_schema"
    ]
    apply_schema = registry.get_action_schema("paint.layer.mask.apply")[
        "params_schema"
    ]
    assert selection_schema["properties"]["layer_id"]["pattern"] == r"^(?:$|.*\S.*)$"
    assert path_schema["required"] == ["path_id"]
    assert path_schema["properties"]["path_id"]["pattern"] == r".*\S.*"
    assert create_schema["required"] == ["mask_type"]
    assert create_schema["properties"]["mask_type"]["enum"] == [
        "selection", "path", "channel", "alpha", "layer_alpha", "white", "reveal_all",
    ]
    assert apply_schema["properties"]["layer_id"]["pattern"] == r"^(?:$|.*\S.*)$"


def test_export_schema_declares_omitted_zero_pair_or_positive_pair() -> None:
    from app.actions.paint_namespace import _paint_optional_export_size_schema

    schema = _paint_optional_export_size_schema(
        {
            "width": {"type": "integer", "minimum": 0, "maximum": 16384},
            "height": {"type": "integer", "minimum": 0, "maximum": 16384},
        }
    )
    assert schema["oneOf"] == [
        {
            "not": {
                "anyOf": [
                    {"required": ["width"]},
                    {"required": ["height"]},
                ]
            }
        },
        {
            "required": ["width", "height"],
            "properties": {
                "width": {"const": 0},
                "height": {"const": 0},
            },
        },
        {
            "required": ["width", "height"],
            "properties": {
                "width": {"minimum": 1},
                "height": {"minimum": 1},
            },
        },
    ]
def test_adapter_rejects_fabricated_time_and_partial_export_size(monkeypatch) -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin

    class Adapter(PaintAdapterMixin):
        def __init__(self):
            self.owner = SimpleNamespace(_time_ms=25, _preview_pixmap=None)

        def _require_owner(self):
            return self.owner

        def _paint_dialog_owner(self):
            raise AssertionError("partial size must fail before resolving the dialog")

    adapter = Adapter()
    with pytest.raises(TypeError, match="time_ms"):
        adapter._paint_action_time_ms("bad")
    adapter.owner._time_ms = -1
    with pytest.raises(ValueError, match="nonnegative"):
        adapter._paint_action_time_ms(None)
    with pytest.raises(ValueError, match="both"):
        adapter.paint_document_export_png(path="unused.png", width=10, height=0)
    with pytest.raises(ValueError, match="both"):
        adapter.paint_export_png(path="unused.png", time_ms=0, width=10, height=0)
    monkeypatch.setattr(
        "app.paths.default_save_dir",
        lambda: (_ for _ in ()).throw(AssertionError("output path was touched")),
    )
    with pytest.raises(ValueError, match="both"):
        adapter.paint_document_export_png(path="", width=10, height=0)
    with pytest.raises(ValueError, match="both"):
        adapter.paint_export_png(path="", time_ms=0, width=10, height=0)


def test_paint_export_preserves_the_exact_document_to_output_width_scale(monkeypatch) -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin

    captured = {}

    class Adapter(PaintAdapterMixin):
        def __init__(self):
            self.owner = SimpleNamespace(
                _time_ms=0,
                _preview_pixmap=None,
                _canvas_document_size=(1_000_000, 1),
                _strokes=[],
                _bubbles=[],
                _stickers=[],
                _paint_layers=[],
                _paint_layer_rasters={},
            )

        def _require_owner(self):
            return self.owner

    def fake_export(_path, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr("app.drawing.export_paint_png", fake_export)
    report = Adapter().paint_export_png(
        path="unused.png",
        time_ms=0,
        width=1,
        height=1,
    )

    assert report == {"ok": True}
    assert captured["stroke_width_scale"] == pytest.approx(0.000001)


def test_brush_action_validates_complete_payload_before_owner_mutation() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_contract import (
        PAINT_ACTION_BRUSH_OPACITY_MAX_PERCENT,
        PAINT_ACTION_BRUSH_OPACITY_MIN_PERCENT,
        PAINT_ACTION_MAX_BRUSH_WIDTH_PX,
    )
    from app.painter_action_inputs import validate_brush_set_action
    from app.painter_brush_domains import (
        BRUSH_ANGLE_RANGE,
        BRUSH_HARDNESS_RANGE,
        BRUSH_ROUNDNESS_RANGE,
        BRUSH_SPACING_RANGE,
        BRUSH_WIDTH_RANGE_PX,
    )

    endpoint = validate_brush_set_action(
        width=int(BRUSH_WIDTH_RANGE_PX[0]),
        opacity=PAINT_ACTION_BRUSH_OPACITY_MAX_PERCENT,
        hardness=BRUSH_HARDNESS_RANGE[1],
        spacing=BRUSH_SPACING_RANGE[1],
        angle=BRUSH_ANGLE_RANGE[0],
        roundness=BRUSH_ROUNDNESS_RANGE[0],
        flip_x=False,
        dynamics={},
    )
    assert endpoint["width"] == int(BRUSH_WIDTH_RANGE_PX[0])
    assert endpoint["dynamics"] == {}

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid brush payload must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        {},
        {"width": 0},
        {"opacity": 0},
        {"hardness": 1.5},
        {"spacing": True},
        {"flip_x": 1},
        {"dynamics": []},
        {"style": "not_a_style"},
        {"style": "oil"},
        {"style": "loaded-oil"},
        {"style": " Loaded_Oil"},
        {"style": "LOADED_OIL"},
        {"style": "   "},
        {"preset": "   "},
        {"preset": "missing-preset"},
        {"preset": 123},
    )
    for payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_brush_set(**payload)

    schema = ActionRegistry(owner=None).get_action_schema("paint.brush.set")["params_schema"]
    properties = schema["properties"]
    assert len(schema["anyOf"]) == 11
    assert properties["width"] == {
        "type": "integer",
        "minimum": int(BRUSH_WIDTH_RANGE_PX[0]),
        "maximum": PAINT_ACTION_MAX_BRUSH_WIDTH_PX,
    }
    assert properties["opacity"] == {
        "type": "integer",
        "minimum": PAINT_ACTION_BRUSH_OPACITY_MIN_PERCENT,
        "maximum": PAINT_ACTION_BRUSH_OPACITY_MAX_PERCENT,
    }
    assert properties["hardness"]["minimum"] == BRUSH_HARDNESS_RANGE[0]
    assert properties["spacing"]["maximum"] == BRUSH_SPACING_RANGE[1]
    assert properties["angle"]["minimum"] == BRUSH_ANGLE_RANGE[0]
    assert properties["roundness"]["minimum"] == BRUSH_ROUNDNESS_RANGE[0]


def test_view_pan_uses_exact_qpoint_domain_and_one_operation_before_mutation() -> None:
    from PySide6.QtCore import QPoint

    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_contract import (
        PAINT_ACTION_QPOINT_COORDINATE_MAX,
        PAINT_ACTION_QPOINT_COORDINATE_MIN,
    )
    from app.painter_action_inputs import validate_view_pan_action

    assert validate_view_pan_action(x=PAINT_ACTION_QPOINT_COORDINATE_MIN) == (
        "absolute", PAINT_ACTION_QPOINT_COORDINATE_MIN, None
    )
    assert validate_view_pan_action(dy=PAINT_ACTION_QPOINT_COORDINATE_MAX) == (
        "relative", None, PAINT_ACTION_QPOINT_COORDINATE_MAX
    )
    assert validate_view_pan_action(reset=True) == ("reset", None, None)

    class InvalidAdapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid pan payload must fail before owner resolution")

    invalid_calls = (
        {},
        {"dx": 0},
        {"dy": 0},
        {"reset": False},
        {"reset": True, "x": 0},
        {"x": 0, "dx": 1},
        {"dx": 1, "reset": None},
        {"dy": 1, "x": None},
        {"x": 1, "dy": None},
        {"dx": 1.5},
        {"dx": "1"},
        {"dx": True},
        {"x": PAINT_ACTION_QPOINT_COORDINATE_MAX + 1},
        {"y": PAINT_ACTION_QPOINT_COORDINATE_MIN - 1},
    )
    for payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            InvalidAdapter().paint_view_pan(**payload)

    class OverflowDialog:
        _canvas_pan = QPoint(PAINT_ACTION_QPOINT_COORDINATE_MAX, 0)

        def _set_canvas_pan(self, _pan):
            raise AssertionError("overflow must fail before pan mutation")

    class OverflowAdapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            return OverflowDialog()

    with pytest.raises(ValueError, match="result x"):
        OverflowAdapter().paint_view_pan(dx=1)

    schema = ActionRegistry(owner=None).get_action_schema("paint.view.pan")["params_schema"]
    assert len(schema["oneOf"]) == 3
    for field in ("x", "y", "dx", "dy"):
        assert schema["properties"][field] == {
            "type": "integer",
            "minimum": PAINT_ACTION_QPOINT_COORDINATE_MIN,
            "maximum": PAINT_ACTION_QPOINT_COORDINATE_MAX,
        }


def test_layer_mask_actions_validate_normalized_alpha8_payload_before_owner() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_inputs import (
        PAINTER_LAYER_MASK_ALPHA_MAX,
        PAINTER_LAYER_MASK_ALPHA_MIN,
        PAINTER_LAYER_MASK_RADIUS_MIN_PX,
        validate_layer_mask_gradient_action,
        validate_layer_mask_paint_action,
        validate_layer_mask_state_action,
    )

    assert validate_layer_mask_state_action(enabled=False) == ("", False, None, False)
    assert validate_layer_mask_state_action(delete=True) == ("", None, None, True)
    assert validate_layer_mask_paint_action(
        x=0.0,
        y=1.0,
        radius_px=PAINTER_LAYER_MASK_RADIUS_MIN_PX,
        value=PAINTER_LAYER_MASK_ALPHA_MAX,
    ) == ("", 0.0, 1.0, PAINTER_LAYER_MASK_RADIUS_MIN_PX, PAINTER_LAYER_MASK_ALPHA_MAX)
    assert validate_layer_mask_gradient_action(
        start=[0.0, 0.0],
        end=[1.0, 1.0],
        start_value=PAINTER_LAYER_MASK_ALPHA_MIN,
        end_value=PAINTER_LAYER_MASK_ALPHA_MAX,
    )[1:] == ((0.0, 0.0), (1.0, 1.0), 0, 255)

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid layer mask payload must fail before owner resolution")

    invalid_calls = (
        ("paint_layer_mask_state_set", {}),
        ("paint_layer_mask_state_set", {"delete": False}),
        ("paint_layer_mask_state_set", {"delete": True, "enabled": False}),
        ("paint_layer_mask_state_set", {"enabled": None, "linked": True}),
        ("paint_layer_mask_state_set", {"linked": None, "enabled": True}),
        ("paint_layer_mask_state_set", {"delete": None}),
        ("paint_layer_mask_state_set", {"enabled": 1}),
        ("paint_layer_mask_state_set", {"layer_id": "   ", "linked": True}),
        ("paint_layer_mask_paint", {"x": -0.01, "y": 0.5, "radius_px": 1.0, "value": 255}),
        ("paint_layer_mask_paint", {"x": True, "y": 0.5, "radius_px": 1.0, "value": 255}),
        ("paint_layer_mask_paint", {"x": 0.5, "y": 0.5, "radius_px": 0.49, "value": 255}),
        ("paint_layer_mask_paint", {"x": 0.5, "y": 0.5, "radius_px": float("inf"), "value": 255}),
        ("paint_layer_mask_paint", {"x": 0.5, "y": 0.5, "radius_px": 1.0, "value": 256}),
        ("paint_layer_mask_paint", {"x": 0.5, "y": 0.5, "radius_px": 1.0, "value": True}),
        ("paint_layer_mask_gradient", {"start": None, "end": [1.0, 1.0]}),
        ("paint_layer_mask_gradient", {"start": [0.0], "end": [1.0, 1.0]}),
        ("paint_layer_mask_gradient", {"start": [0.0, 0.0, 0.0], "end": [1.0, 1.0]}),
        ("paint_layer_mask_gradient", {"start": [0.0, 0.0], "end": [0.0, 0.0]}),
        ("paint_layer_mask_gradient", {"start": [0.0, float("nan")], "end": [1.0, 1.0]}),
        ("paint_layer_mask_gradient", {"start": [0.0, 0.0], "end": [1.0, 1.0], "start_value": -1}),
    )
    adapter = Adapter()
    for method_name, payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            getattr(adapter, method_name)(**payload)

    registry = ActionRegistry(owner=None)
    state_schema = registry.get_action_schema("paint.layer.mask_state.set")["params_schema"]
    assert len(state_schema["oneOf"]) == 2
    paint_schema = registry.get_action_schema("paint.layer.mask.paint")["params_schema"]["properties"]
    assert paint_schema["radius_px"]["minimum"] == PAINTER_LAYER_MASK_RADIUS_MIN_PX
    assert paint_schema["value"]["minimum"] == PAINTER_LAYER_MASK_ALPHA_MIN
    assert paint_schema["value"]["maximum"] == PAINTER_LAYER_MASK_ALPHA_MAX
    gradient_schema = registry.get_action_schema("paint.layer.mask.gradient")["params_schema"]["properties"]
    assert gradient_schema["start"]["minItems"] == gradient_schema["start"]["maxItems"] == 2
    assert gradient_schema["end_value"]["maximum"] == PAINTER_LAYER_MASK_ALPHA_MAX


def test_canvas_size_fallback_requires_exact_positive_integral_extents() -> None:
    from types import SimpleNamespace

    from app.actions.editor_adapter_paint import PaintAdapterMixin

    class Adapter(PaintAdapterMixin):
        def __init__(self, owner):
            self.owner = owner

        def _require_owner(self):
            return self.owner

    widget = SimpleNamespace(width=lambda: 640, height=lambda: 360)
    owner = SimpleNamespace(
        _canvas_document_size=["1920", 1080],
        _drawing_canvas=widget,
        _preview_label=None,
        _preview_widget=None,
        _preview_pixmap=None,
    )
    adapter = Adapter(owner)
    assert adapter._paint_canvas_size() == (640, 360)

    owner._canvas_document_size = [1920, 1080]
    assert adapter._paint_canvas_size() == (1920, 1080)
    owner._canvas_document_size = [1920, 1080, 1]
    assert adapter._paint_canvas_size() == (640, 360)
    owner._canvas_document_size = [True, 1080]
    assert adapter._paint_canvas_size() == (640, 360)

    owner._drawing_canvas = SimpleNamespace(width=lambda: 0, height=lambda: 360)
    owner._preview_pixmap = SimpleNamespace(width=lambda: 320, height=lambda: 180)
    assert adapter._paint_canvas_size() == (320, 180)
    assert adapter._paint_export_size_for_owner(
        SimpleNamespace(width=lambda: 1.5, height=lambda: 180)
    ) == (320, 180)

    owner._preview_pixmap = None
    with pytest.raises(ValueError, match="dimensions are unavailable"):
        adapter._paint_canvas_size()


def test_reference_board_mutations_validate_complete_payload_before_owner() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_inputs import (
        validate_reference_add_action,
        validate_reference_duplicate_action,
        validate_reference_update_action,
    )
    from app.painter_reference_board import (
        REFERENCE_NAME_MAX_CHARACTERS,
        REFERENCE_OPACITY_MIN,
        REFERENCE_ROTATION_MAX_DEGREES,
        REFERENCE_SIZE_MIN_NORM,
        REFERENCE_TARGET_ID_MIN_CHARACTERS,
    )

    added = validate_reference_add_action(
        path=" image.png ",
        width_norm=REFERENCE_SIZE_MIN_NORM,
        opacity=REFERENCE_OPACITY_MIN,
        rotation_deg=REFERENCE_ROTATION_MAX_DEGREES,
    )
    assert added["path"] == "image.png"
    assert added["width_norm"] == REFERENCE_SIZE_MIN_NORM
    assert validate_reference_update_action(reference_id="reference:1", visible=False) == (
        "reference:1", {"visible": False}
    )
    assert validate_reference_duplicate_action(
        reference_id="reference:1", offset_x=-1.25, offset_y=2.5
    ) == ("reference:1", -1.25, 2.5)

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid reference payload must fail before owner resolution")

    invalid_calls = (
        ("paint_reference_add", {}),
        ("paint_reference_add", {"path": "   "}),
        ("paint_reference_add", {"path": 1}),
        ("paint_reference_add", {"path": "x.png", "name": "x" * (REFERENCE_NAME_MAX_CHARACTERS + 1)}),
        ("paint_reference_add", {"path": "x.png", "x_norm": True}),
        ("paint_reference_add", {"path": "x.png", "width_norm": 0.0}),
        ("paint_reference_add", {"path": "x.png", "opacity": float("nan")}),
        ("paint_reference_add", {"path": "x.png", "rotation_deg": 181.0}),
        ("paint_reference_add", {"path": "x.png", "visible": 1}),
        ("paint_reference_update", {"reference_id": "reference:1"}),
        ("paint_reference_update", {"visible": True}),
        ("paint_reference_update", {"reference_id": "", "visible": True}),
        ("paint_reference_update", {"reference_id": "reference:1", "name": None}),
        ("paint_reference_update", {"reference_id": "reference:1", "locked": None}),
        ("paint_reference_update", {"reference_id": "reference:1", "height_norm": 1.1}),
        ("paint_reference_update", {"reference_id": "   ", "visible": True}),
        ("paint_reference_delete", {}),
        ("paint_reference_delete", {"reference_id": ""}),
        ("paint_reference_delete", {"reference_id": None}),
        ("paint_reference_delete", {"reference_id": "   "}),
        ("paint_reference_duplicate", {}),
        ("paint_reference_duplicate", {"reference_id": ""}),
        ("paint_reference_duplicate", {"reference_id": None}),
        ("paint_reference_duplicate", {"reference_id": "reference:1", "offset_x": True}),
        ("paint_reference_duplicate", {"reference_id": "reference:1", "offset_y": float("inf")}),
        ("paint_reference_bake", {"reference_id": None}),
        ("paint_reference_bake", {"reference_id": "   "}),
    )
    adapter = Adapter()
    for method_name, payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            getattr(adapter, method_name)(**payload)

    registry = ActionRegistry(owner=None)
    add_schema = registry.get_action_schema("paint.reference.add")["params_schema"]
    assert "reference_id" not in add_schema["properties"]
    assert add_schema["properties"]["name"]["maxLength"] == REFERENCE_NAME_MAX_CHARACTERS
    assert add_schema["properties"]["width_norm"]["minimum"] == REFERENCE_SIZE_MIN_NORM
    assert add_schema["properties"]["opacity"]["minimum"] == REFERENCE_OPACITY_MIN
    update_schema = registry.get_action_schema("paint.reference.update")["params_schema"]
    assert "path" not in update_schema["properties"]
    assert update_schema["properties"]["reference_id"]["minLength"] == REFERENCE_TARGET_ID_MIN_CHARACTERS
    assert len(update_schema["anyOf"]) == 9
    delete_schema = registry.get_action_schema("paint.reference.delete")["params_schema"]
    duplicate_schema = registry.get_action_schema("paint.reference.duplicate")["params_schema"]
    bake_schema = registry.get_action_schema("paint.reference.bake")["params_schema"]
    assert delete_schema["properties"]["reference_id"]["minLength"] == REFERENCE_TARGET_ID_MIN_CHARACTERS
    assert duplicate_schema["properties"]["reference_id"]["minLength"] == REFERENCE_TARGET_ID_MIN_CHARACTERS
    assert "minLength" not in bake_schema["properties"]["reference_id"]


def test_path_create_action_rejects_coercion_clamping_and_unfulfilled_selection_before_owner() -> None:
    import app.painter_action_contract as action_contract_module
    import app.painter_action_inputs as action_inputs_module
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_contract import (
        PAINT_ACTION_MAX_POINTS_PER_STROKE,
        PAINT_ACTION_PATH_MIN_POINTS,
        PAINT_ACTION_PATH_SELECTION_MIN_POINTS,
    )
    from app.painter_action_inputs import validate_path_create_action

    contract_source = inspect.getsource(action_contract_module)
    inputs_source = inspect.getsource(action_inputs_module)
    for constant in (
        "PAINT_ACTION_PATH_MIN_POINTS",
        "PAINT_ACTION_PATH_SELECTION_MIN_POINTS",
        "PAINT_ACTION_PATH_COORDINATE_MIN_NORM",
        "PAINT_ACTION_PATH_COORDINATE_MAX_NORM",
        "PAINT_ACTION_PATH_INDEX_MIN",
        "PAINT_ACTION_PATH_NAME_MIN_CHARACTERS",
    ):
        assert len(re.findall(rf"(?m)^{constant}\s*=", contract_source)) == 1
    for function_name in (
        "validate_path_id_action",
        "_strict_path_point",
        "validate_path_create_action",
    ):
        assert len(re.findall(rf"(?m)^def {function_name}\(", inputs_source)) == 1

    assert validate_path_create_action(
        points=[{"x": 0.0, "y": 1.0}, [1.0, 0.0]],
        closed=False,
        make_selection=False,
    ) == ([(0.0, 1.0), (1.0, 0.0)], False, False)

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid path payload must fail before owner resolution")

    adapter = Adapter()
    invalid_payloads = (
        {"points": None},
        {"points": []},
        {"points": [[0.0, 0.0]]},
        {"points": [[0.0, 0.0], [1.0, 1.0]], "make_selection": True},
        {"points": [[-0.001, 0.0], [1.0, 1.0]]},
        {"points": [[0.0, 0.0], [1.001, 1.0]]},
        {"points": [[0.0, 0.0, 1.0], [1.0, 1.0]]},
        {"points": [{"x": 0.0}, {"x": 1.0, "y": 1.0}]},
        {"points": [{"x": 0.0, "y": 0.0, "x_norm": 0.0}, {"x": 1.0, "y": 1.0}]},
        {"points": [[True, 0.0], [1.0, 1.0]]},
        {"points": [[float("nan"), 0.0], [1.0, 1.0]]},
        {"points": [[0.0, 0.0], [1.0, 1.0]], "closed": 1},
        {"points": [[0.0, 0.0], [1.0, 1.0]], "make_selection": 0},
        {"points": [[0.0, 0.0]] * (PAINT_ACTION_MAX_POINTS_PER_STROKE + 1)},
    )
    for payload in invalid_payloads:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_path_create(**payload)
    for invalid_id in (None, 1, "   "):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_path_to_selection(path_id=invalid_id)
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_path_delete(path_id=invalid_id)
    with pytest.raises(TypeError):
        adapter.paint_path_commit(closed=1)

    schema = ActionRegistry(owner=None).get_action_schema("paint.path.create")["params_schema"]
    points_schema = schema["properties"]["points"]
    assert points_schema["minItems"] == PAINT_ACTION_PATH_MIN_POINTS
    assert points_schema["maxItems"] == PAINT_ACTION_MAX_POINTS_PER_STROKE
    assert schema["allOf"][0]["then"]["properties"]["points"]["minItems"] == PAINT_ACTION_PATH_SELECTION_MIN_POINTS


def test_saved_path_mutations_validate_semantics_color_and_width_before_owner() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_contract import (
        PAINT_ACTION_MAX_BRUSH_WIDTH_PX,
        PAINT_ACTION_STROKE_MIN_WIDTH_PX,
    )
    from app.painter_action_inputs import (
        validate_path_anchor_action,
        validate_path_stroke_action,
    )

    assert validate_path_anchor_action(
        path_id="path:0",
        index=0,
        operation="move",
        point=[0.0, 1.0],
        in_handle=[-2.0, 3.0],
        out_handle=[4.0, -5.0],
    ) == ("path:0", 0, "move", (0.0, 1.0), (-2.0, 3.0), (4.0, -5.0))
    assert validate_path_stroke_action(
        color="#112233",
        width_px=PAINT_ACTION_STROKE_MIN_WIDTH_PX,
    ) == ("#112233", PAINT_ACTION_STROKE_MIN_WIDTH_PX)

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid saved-path payload must fail before owner resolution")

    adapter = Adapter()
    invalid_anchor_payloads = (
        {"index": True, "operation": "delete"},
        {"index": -1, "operation": "delete"},
        {"index": 0, "operation": "MOVE", "point": [0.5, 0.5]},
        {"index": 0, "operation": "add"},
        {"index": 0, "operation": "move"},
        {"index": 0, "operation": "delete", "point": [0.5, 0.5]},
        {"index": 0, "operation": "add", "point": [0.5, 0.5], "in_handle": [0.0, 0.0]},
        {"index": 0, "operation": "corner", "out_handle": [0.0, 0.0]},
        {"index": 0, "operation": "move", "point": [-0.001, 0.5]},
        {"index": 0, "operation": "move", "point": [0.5, float("inf")]},
        {"index": 0, "operation": "smooth", "in_handle": [0.0]},
        {"index": 0, "operation": "smooth", "out_handle": [True, 0.0]},
    )
    for payload in invalid_anchor_payloads:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_path_anchor_edit(**payload)
    for method_name, payload in (
        ("paint_path_duplicate", {"path_id": "   "}),
        ("paint_path_rename", {"name": "   "}),
        ("paint_path_rename", {"name": 1}),
        ("paint_path_reorder", {"index": True}),
        ("paint_path_reorder", {"index": -1}),
        ("paint_path_fill", {"color": None}),
        ("paint_path_fill", {"color": "   "}),
        ("paint_path_fill", {"color": "not-a-qt-color"}),
        ("paint_path_stroke", {"color": "   "}),
        ("paint_path_stroke", {"width_px": True}),
        ("paint_path_stroke", {"width_px": float("nan")}),
        ("paint_path_stroke", {"width_px": PAINT_ACTION_STROKE_MIN_WIDTH_PX - 0.001}),
        ("paint_path_stroke", {"width_px": PAINT_ACTION_MAX_BRUSH_WIDTH_PX + 0.001}),
    ):
        with pytest.raises((TypeError, ValueError)):
            getattr(adapter, method_name)(**payload)

    registry = ActionRegistry(owner=None)
    for action_id in ("paint.path.to_selection", "paint.path.delete"):
        id_schema = registry.get_action_schema(action_id)["params_schema"]["properties"]["path_id"]
        assert id_schema["pattern"] == r"^(?:$|.*\S.*)$"
    anchor_schema = registry.get_action_schema("paint.path.anchor.edit")["params_schema"]
    assert len(anchor_schema["allOf"]) == 3
    stroke_schema = registry.get_action_schema("paint.path.stroke")["params_schema"]
    assert stroke_schema["properties"]["width_px"] == {
        "type": "number",
        "minimum": PAINT_ACTION_STROKE_MIN_WIDTH_PX,
        "maximum": PAINT_ACTION_MAX_BRUSH_WIDTH_PX,
    }


def test_layer_actions_reject_coercion_fallback_and_silent_truncation_before_owner() -> None:
    import app.painter_layer_contract as layer_contract_module
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_layer_contract import (
        PAINTER_LAYER_COLOR_LABEL_IDS,
        PAINTER_LAYER_ID_MIN_CHARACTERS,
        PAINTER_LAYER_NAME_MAX_CHARACTERS,
        PAINTER_LAYER_TYPES,
    )

    layer_contract_source = inspect.getsource(layer_contract_module)
    for constant in (
        "PAINTER_LAYER_ID_MIN_CHARACTERS",
        "PAINTER_LAYER_NAME_MAX_CHARACTERS",
        "PAINTER_LAYER_TYPES",
        "PAINTER_LAYER_COLOR_LABEL_IDS",
    ):
        assert len(re.findall(rf"(?m)^{constant}\s*=", layer_contract_source)) == 1

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid layer payload must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        ("paint_layer_add", {"name": True}),
        ("paint_layer_add", {"name": "x" * (PAINTER_LAYER_NAME_MAX_CHARACTERS + 1)}),
        ("paint_layer_add", {"layer_type": "STANDARD"}),
        ("paint_layer_add", {"layer_type": ""}),
        ("paint_layer_import_image", {"path": "   "}),
        ("paint_layer_import_image", {"path": 1}),
        ("paint_layer_group_create", {"layer_ids": ("paint-layer-1",)}),
        ("paint_layer_group_create", {"layer_ids": ["paint-layer-1", "paint-layer-1"]}),
        ("paint_layer_group_create", {"layer_ids": ["   "]}),
        ("paint_layer_set_clipping", {"clipping": 1}),
        ("paint_layer_set_clipping", {"layer_id": "   ", "clipping": True}),
        ("paint_layer_group_set_expanded", {"layer_id": "", "expanded": True}),
        ("paint_layer_group_set_expanded", {"layer_id": "paint-layer-1", "expanded": 1}),
        ("paint_layer_set_locks", {}),
        ("paint_layer_set_locks", {"pixels": None}),
        ("paint_layer_set_locks", {"transparency": 0}),
        ("paint_layer_merge_down", {"layer_id": "   "}),
        ("paint_layer_set_type", {"layer_type": "Material"}),
        ("paint_layer_select", {"layer_id": ""}),
        ("paint_layer_select", {"layer_id": "   "}),
        ("paint_layer_rename", {"name": ""}),
        ("paint_layer_rename", {"name": "x" * (PAINTER_LAYER_NAME_MAX_CHARACTERS + 1)}),
        ("paint_layer_duplicate", {"layer_id": "   "}),
        ("paint_layer_delete", {"layer_id": "   "}),
        ("paint_layer_set_visible", {"visible": 1}),
        ("paint_layer_set_locked", {"locked": 0}),
        ("paint_layer_set_blend_mode", {"blend_mode": "NORMAL"}),
        ("paint_layer_set_blend_mode", {"blend_mode": "unknown"}),
        ("paint_layer_set_color", {"color_label": "purple"}),
    )
    for method_name, payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            getattr(adapter, method_name)(**payload)

    registry = ActionRegistry(owner=None)
    add_schema = registry.get_action_schema("paint.layer.add")["params_schema"]
    assert add_schema["properties"]["name"]["maxLength"] == PAINTER_LAYER_NAME_MAX_CHARACTERS
    assert add_schema["properties"]["layer_type"]["enum"] == list(PAINTER_LAYER_TYPES)
    locks_schema = registry.get_action_schema("paint.layer.set_locks")["params_schema"]
    assert len(locks_schema["anyOf"]) == 4
    assert registry.get_action_schema("paint.layer.merge_visible")["params_schema"]["properties"] == {}
    assert registry.get_action_schema("paint.layer.flatten")["params_schema"]["properties"] == {}
    select_id = registry.get_action_schema("paint.layer.select")["params_schema"]["properties"]["layer_id"]
    assert select_id["minLength"] == PAINTER_LAYER_ID_MIN_CHARACTERS
    optional_id = registry.get_action_schema("paint.layer.duplicate")["params_schema"]["properties"]["layer_id"]
    assert optional_id["pattern"] == r"^(?:$|.*\S.*)$"
    color_schema = registry.get_action_schema("paint.layer.set_color")["params_schema"]
    assert color_schema["properties"]["color_label"]["enum"] == list(PAINTER_LAYER_COLOR_LABEL_IDS)


def test_channel_and_quick_mask_actions_reject_coercion_and_fallback_before_owner() -> None:
    import app.painter_channel_contract as channel_contract_module
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_channel_contract import PAINTER_CHANNEL_IDS

    source = inspect.getsource(channel_contract_module)
    assert len(re.findall(r"(?m)^PAINTER_CHANNEL_IDS\s*=", source)) == 1
    assert len(re.findall(r"(?m)^PAINTER_RGB_COMPONENT_CHANNEL_IDS\s*=", source)) == 1

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid channel payload must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        ("paint_quick_mask_set", {"enabled": 1}),
        ("paint_channel_set_visible", {"channel": "red", "visible": True}),
        ("paint_channel_set_visible", {"channel": "Red", "visible": 1}),
        ("paint_channel_select", {"channel": ""}),
        ("paint_channel_select", {"channel": "   "}),
        ("paint_channel_copy_image", {"channel": "blue"}),
        ("paint_channel_copy_image", {"channel": "   "}),
        ("paint_channel_paste_image", {"channel": None}),
        ("paint_selection_save_channel", {"name": "   ", "operation": "new"}),
        (
            "paint_selection_save_channel",
            {
                "name": "Edges",
                "channel_id": "saved-selection-1",
                "operation": "new",
            },
        ),
        (
            "paint_selection_save_channel",
            {"channel_id": "bad", "operation": "replace"},
        ),
        (
            "paint_selection_save_channel",
            {
                "name": "Ignored rename",
                "channel_id": "saved-selection-1",
                "operation": "replace",
            },
        ),
        (
            "paint_selection_load_channel",
            {"channel_id": "bad", "operation": "new"},
        ),
        (
            "paint_selection_load_channel",
            {"channel_id": " saved-selection-1 ", "operation": "new"},
        ),
        (
            "paint_selection_channel_rename",
            {"channel_id": "bad", "name": "Edges"},
        ),
        (
            "paint_selection_channel_rename",
            {"channel_id": "saved-selection-1", "name": "   "},
        ),
        (
            "paint_selection_channel_duplicate",
            {"channel_id": "saved-selection-1", "name": "Copy", "invert": 1},
        ),
        (
            "paint_selection_channel_reorder",
            {
                "channel_id": "saved-selection-1",
                "target_channel_id": "saved-selection-1",
                "placement": "before",
            },
        ),
        (
            "paint_selection_channel_reorder",
            {
                "channel_id": "saved-selection-1",
                "target_channel_id": "saved-selection-2",
                "placement": "middle",
            },
        ),
        (
            "paint_selection_channel_delete",
            {"channel_id": "saved-selection-0"},
        ),
        (
            "paint_selection_channel_options_set",
            {
                "channel_id": "saved-selection-1",
                "display_mode": "unknown",
                "overlay_color": "#ff0000",
                "overlay_opacity_percent": 50,
            },
        ),
        (
            "paint_selection_channel_options_set",
            {
                "channel_id": "saved-selection-1",
                "display_mode": "masked_areas",
                "overlay_color": "red garbage",
                "overlay_opacity_percent": 50,
            },
        ),
        (
            "paint_selection_channel_options_set",
            {
                "channel_id": "saved-selection-1",
                "display_mode": "masked_areas",
                "overlay_color": "#ff0000",
                "overlay_opacity_percent": True,
            },
        ),
        (
            "paint_selection_save_channel_to_document",
            {
                "destination_document_id": "bad-document",
                "name": "Edges",
                "operation": "new",
            },
        ),
        (
            "paint_selection_save_channel_to_document",
            {
                "destination_document_id": "painter-document-" + "a" * 32,
                "name": "   ",
                "operation": "new",
            },
        ),
        (
            "paint_selection_load_channel_from_document",
            {
                "source_document_id": "bad-document",
                "channel_id": "saved-selection-1",
            },
        ),
        (
            "paint_selection_load_channel_from_document",
            {
                "source_document_id": "painter-document-" + "a" * 32,
                "channel_id": "saved-selection-0",
            },
        ),
        (
            "paint_selection_load_channel_from_document",
            {
                "source_document_id": "painter-document-" + "a" * 32,
                "channel_id": "saved-selection-1",
                "invert": 1,
            },
        ),
    )
    for method_name, payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            getattr(adapter, method_name)(**payload)
    with pytest.raises(TypeError):
        adapter.paint_channel_select()
    with pytest.raises(TypeError):
        adapter.paint_channel_set_visible()
    with pytest.raises(TypeError):
        adapter.paint_channel_set_visible(channel="RGB")

    registry = ActionRegistry(owner=None)
    visibility_channel_schema = registry.get_action_schema(
        "paint.channel.set_visible"
    )["params_schema"]["properties"]["channel"]
    assert visibility_channel_schema["oneOf"] == [
        {"enum": list(PAINTER_CHANNEL_IDS)},
        {"pattern": r"^saved-selection-[1-9][0-9]*$"},
    ]
    selection_channel_schema = registry.get_action_schema(
        "paint.channel.select"
    )["params_schema"]["properties"]["channel"]
    assert selection_channel_schema == {"type": "string", "minLength": 1}
    for action_id in ("paint.channel.copy_image", "paint.channel.paste_image"):
        channel_schema = registry.get_action_schema(action_id)["params_schema"]["properties"]["channel"]
        assert channel_schema == {"type": "string"}
    save_schema = registry.get_action_schema(
        "paint.selection.save_channel"
    )["params_schema"]
    assert save_schema["oneOf"][0]["properties"]["name"]["pattern"] == r".*\S.*"
    assert save_schema["oneOf"][0]["properties"]["channel_id"]["maxLength"] == 0
    assert save_schema["oneOf"][1]["properties"]["channel_id"]["pattern"] == (
        r"^saved-selection-[1-9][0-9]*$"
    )
    assert save_schema["oneOf"][1]["required"] == ["channel_id", "operation"]
    cross_save_schema = registry.get_action_schema(
        "paint.selection.save_channel_to_document"
    )["params_schema"]
    assert cross_save_schema["properties"]["destination_document_id"]["pattern"] == (
        r"^painter-document-[0-9a-f]{32}$"
    )
    assert cross_save_schema["oneOf"] == save_schema["oneOf"]
    cross_load_schema = registry.get_action_schema(
        "paint.selection.load_channel_from_document"
    )["params_schema"]
    assert cross_load_schema["properties"]["source_document_id"]["pattern"] == (
        r"^painter-document-[0-9a-f]{32}$"
    )
    for action_id in (
        "paint.selection.channel.rename",
        "paint.selection.channel.duplicate",
        "paint.selection.channel.reorder",
        "paint.selection.channel.delete",
    ):
        lifecycle_schema = registry.get_action_schema(action_id)["params_schema"]
        assert lifecycle_schema["properties"]["channel_id"]["pattern"] == (
            r"^saved-selection-[1-9][0-9]*$"
        )


def test_view_actions_reject_invalid_domains_before_owner_mutation() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid view payload must fail before owner resolution")

    adapter = Adapter()
    for percent in (0, 801, True, 100.0, "100"):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_view_zoom(percent=percent)
    for payload in (
        {"visible": 1},
        {"snap": 0},
        {"size_px": 3},
        {"size_px": 513},
        {"size_px": True},
        {"size_px": 64.0},
    ):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_view_grid(**payload)


def test_pressure_calibration_action_is_strict_before_owner_mutation() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.painter_action_inputs import validate_pressure_calibration_action

    assert validate_pressure_calibration_action(
        device_id=" pen-1 ",
        minimum=0.1,
        maximum=0.9,
        curve=[[0.0, 0.0], [0.5, 0.7], [1.0, 1.0]],
    ) == (
        "pen-1",
        0.1,
        0.9,
        [[0.0, 0.0], [0.5, 0.7], [1.0, 1.0]],
    )
    assert validate_pressure_calibration_action(
        device_id="pen-1",
        minimum=0.995,
        maximum=1.0,
        curve=None,
    )[1:3] == (0.995, 1.0)
    assert validate_pressure_calibration_action(
        device_id="pen-1",
        minimum=0.0,
        maximum=0.005,
        curve=None,
    )[1:3] == (0.0, 0.005)

    class SchemaRegistry:
        def __init__(self):
            self.schemas = {}

        def register_adapter_action(self, action_id, *_args, **kwargs):
            self.schemas[action_id] = kwargs.get("params_schema", {})

    from app.actions.paint_namespace import register_paint_actions

    schema_registry = SchemaRegistry()
    register_paint_actions(schema_registry)
    calibration_properties = schema_registry.schemas[
        "paint.brush.calibration.set"
    ]["properties"]
    assert calibration_properties["device_id"]["pattern"] == r".*\S.*"
    for field in ("minimum", "maximum"):
        assert calibration_properties[field]["minimum"] == 0.0
        assert calibration_properties[field]["maximum"] == 1.0

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid calibration must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        {"device_id": ""},
        {"device_id": "   "},
        {"device_id": 1},
        {"minimum": True},
        {"minimum": float("nan")},
        {"minimum": -0.1},
        {"maximum": 1.1},
        {"minimum": 0.8, "maximum": 0.8},
        {"minimum": 0.9, "maximum": 0.8},
        {"curve": ()},
        {"curve": [[0.0]]},
        {"curve": [[0.0, True]]},
        {"curve": [[0.0, 0.0], [0.0, 1.0]]},
        {"curve": [[0.5, 0.5], [0.4, 0.6]]},
        {"curve": [[0.0, 0.0], [1.1, 1.0]]},
    )
    for payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_brush_calibration_set(**payload)


def test_performance_action_rejects_invalid_resources_before_owner_mutation() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.painter_large_canvas import (
        DEFAULT_TILE_BUDGET_MB,
        DEFAULT_TILE_SIZE,
        DEFAULT_UNDO_BUDGET_MB,
        MAX_TILE_BUDGET_MB,
        MAX_TILE_SIZE,
        MAX_UNDO_BUDGET_MB,
        MIN_TILE_BUDGET_MB,
        MIN_TILE_SIZE,
        MIN_UNDO_BUDGET_MB,
        validate_large_canvas_configuration,
    )

    assert validate_large_canvas_configuration(
        tile_size=DEFAULT_TILE_SIZE,
        tile_budget_mb=DEFAULT_TILE_BUDGET_MB,
        undo_budget_mb=DEFAULT_UNDO_BUDGET_MB,
    ) == (DEFAULT_TILE_SIZE, DEFAULT_TILE_BUDGET_MB, DEFAULT_UNDO_BUDGET_MB)

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid resource config must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        {"tile_size": MIN_TILE_SIZE - 1},
        {"tile_size": MAX_TILE_SIZE + 1},
        {"tile_size": True},
        {"tile_size": float(DEFAULT_TILE_SIZE)},
        {"tile_budget_mb": MIN_TILE_BUDGET_MB - 1},
        {"tile_budget_mb": MAX_TILE_BUDGET_MB + 1},
        {"undo_budget_mb": MIN_UNDO_BUDGET_MB - 1},
        {"undo_budget_mb": MAX_UNDO_BUDGET_MB + 1},
    )
    for payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_performance_configure(**payload)

    from app.drawing import PaintDialog

    closed = []
    fake_dialog = SimpleNamespace(
        _painter_large_canvas_runtime=SimpleNamespace(
            close=lambda: closed.append(True),
        )
    )
    with pytest.raises(ValueError):
        PaintDialog.configure_painter_large_canvas(
            fake_dialog,
            tile_size=MIN_TILE_SIZE - 1,
            tile_budget_mb=DEFAULT_TILE_BUDGET_MB,
            undo_budget_mb=DEFAULT_UNDO_BUDGET_MB,
        )
    assert closed == []


def test_new_document_action_validates_before_owner_mutation() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.painter_output import PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid document input must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        {"width": 63},
        {"height": 63},
        {"width": PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT + 1},
        {"height": PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT + 1},
        {"width": True},
        {"width": 1920.0},
        {"width": "1920"},
        {"background": 0},
        {"background": "not-a-color"},
    )
    for payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_document_new(**payload)

    from app.drawing import PaintDialog

    undo_calls = []
    fake_dialog = SimpleNamespace(
        _push_undo_state=lambda label: undo_calls.append(label),
    )
    for invalid_background in (0, "", "not-a-color"):
        with pytest.raises((TypeError, ValueError)):
            PaintDialog._replace_canvas_document(
                fake_dialog,
                640,
                360,
                invalid_background,
            )
    assert undo_calls == []


def test_selection_geometry_actions_validate_before_owner_mutation() -> None:
    import app.painter_action_inputs as action_inputs_module
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_inputs import (
        PAINTER_SELECTION_ASPECTS,
        PAINTER_SELECTION_MODES,
        validate_selection_bounds_action,
        validate_selection_lasso_action,
    )

    source = inspect.getsource(action_inputs_module)
    for validator_name in (
        "validate_selection_aspect_action",
        "validate_selection_mode_action",
        "validate_crop_preview_action",
    ):
        assert len(re.findall(rf"(?m)^def {validator_name}\(", source)) == 1

    assert validate_selection_bounds_action(
        x1=0.0, y1=0.1, x2=0.9, y2=1.0, aspect="free", mode="new",
    ) == (0.0, 0.1, 0.9, 1.0, "free", "new")
    assert validate_selection_lasso_action(
        points=[[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
        mode="add",
        polygonal=True,
    ) == (
        [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
        "add",
        True,
    )

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid selection must fail before owner resolution")

    adapter = Adapter()
    invalid_bounds = (
        {"x1": True},
        {"x1": float("nan")},
        {"x1": -0.1},
        {"y2": 1.1},
        {"aspect": "custom"},
        {"aspect": 1},
        {"mode": "replace"},
    )
    for method in (adapter.paint_selection_rectangle, adapter.paint_selection_ellipse):
        for payload in invalid_bounds:
            with pytest.raises((TypeError, ValueError)):
                method(**payload)

    invalid_lasso = (
        {"points": None},
        {"points": ()},
        {"points": [[0.0, 0.0], [1.0, 1.0]]},
        {"points": [[0.0, 0.0], [1.0, 0.0], [0.5]]},
        {"points": [[0.0, 0.0], [1.0, 0.0], [0.5, True]]},
        {"points": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.1]]},
        {"points": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]], "mode": "replace"},
        {"points": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]], "polygonal": 1},
    )
    for payload in invalid_lasso:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_selection_lasso(**payload)

    for value in ("custom", "FREE", "", 1, None):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_selection_set_aspect(aspect=value)
    for value in ("replace", "NEW", "", 1, None):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_selection_set_mode(mode=value)
    with pytest.raises(TypeError):
        adapter.paint_selection_set_aspect()
    with pytest.raises(TypeError):
        adapter.paint_selection_set_mode()

    registry = ActionRegistry(owner=None)
    aspect_schema = registry.get_action_schema("paint.selection.set_aspect")["params_schema"]
    mode_schema = registry.get_action_schema("paint.selection.set_mode")["params_schema"]
    assert aspect_schema["properties"]["aspect"]["enum"] == list(PAINTER_SELECTION_ASPECTS)
    assert mode_schema["properties"]["mode"]["enum"] == list(PAINTER_SELECTION_MODES)


def test_color_selection_action_validates_before_owner_mutation() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.painter_action_inputs import validate_color_selection_action

    assert validate_color_selection_action(
        x=0.0,
        y=1.0,
        tolerance=255,
        contiguous=False,
        phase="preview",
    ) == (0.0, 1.0, 255, False, "preview")


def test_crop_preview_action_rejects_partial_coercible_and_nonfinite_payloads() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_inputs import validate_crop_preview_action

    assert validate_crop_preview_action(
        x1=0.1,
        y1=0.2,
        x2=0.9,
        y2=0.8,
        straighten_degrees=90.0,
    ) == ((0.1, 0.2, 0.9, 0.8), 90.0)

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid crop payload must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        {"x1": 0.1},
        {"x1": None, "y1": 0.1, "x2": 0.9, "y2": 0.9},
        {"x1": True, "y1": 0.1, "x2": 0.9, "y2": 0.9},
        {"x1": float("nan"), "y1": 0.1, "x2": 0.9, "y2": 0.9},
        {"x1": 0.9, "y1": 0.1, "x2": 0.1, "y2": 0.9},
        {"x1": 0.1, "y1": 0.9, "x2": 0.9, "y2": 0.1},
        {"straighten_degrees": True},
        {"straighten_degrees": float("inf")},
        {"straighten_degrees": "5"},
    )
    for payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_crop_preview(**payload)

    schema = ActionRegistry(owner=None).get_action_schema("paint.crop.preview")["params_schema"]
    assert len(schema["oneOf"]) == 2
    explicit = schema["oneOf"][1]
    assert set(explicit["required"]) == {"x1", "y1", "x2", "y2"}
    assert explicit["properties"]["straighten_degrees"] == {"type": "number"}

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid color selection must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        {"x": True},
        {"x": float("nan")},
        {"x": -0.1},
        {"y": 1.1},
        {"tolerance": -1},
        {"tolerance": 256},
        {"tolerance": True},
        {"tolerance": 32.0},
        {"contiguous": 1},
        {"phase": "apply"},
        {"phase": 1},
    )
    for payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_selection_select_by_color(**payload)


def test_zoom_area_action_uses_exact_positive_contained_geometry() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.painter_action_inputs import validate_zoom_area_action

    assert validate_zoom_area_action(
        x=0.0,
        y=0.5,
        width=1e-12,
        height=0.5,
    ) == (0.0, 0.5, 1e-12, 0.5)

    from app.drawing import PaintDialog

    zoom_targets = []
    tiny_dialog = SimpleNamespace(
        _canvas_zoom=1.0,
        _set_zoom_percent=lambda value: zoom_targets.append(value),
    )
    PaintDialog._handle_canvas_zoom_request(
        tiny_dialog,
        "zoom_area",
        0.0,
        0.0,
        1e-320,
        1e-320,
    )
    assert zoom_targets == [800]

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid zoom area must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        {"x": True, "y": 0.0, "width": 0.5, "height": 0.5},
        {"x": float("nan"), "y": 0.0, "width": 0.5, "height": 0.5},
        {"x": -0.1, "y": 0.0, "width": 0.5, "height": 0.5},
        {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.5},
        {"x": 0.0, "y": 0.0, "width": 1.1, "height": 0.5},
        {"x": 0.8, "y": 0.0, "width": 0.3, "height": 0.5},
        {"x": 0.0, "y": 0.8, "width": 0.5, "height": 0.3},
    )
    for payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_view_zoom_area(**payload)


def test_layer_opacity_action_is_strict_before_owner_resolution() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.painter_action_inputs import validate_layer_opacity_action

    assert validate_layer_opacity_action(0) == 0
    assert validate_layer_opacity_action(100) == 100

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid opacity must fail before owner resolution")

    adapter = Adapter()
    for invalid in (True, -1, 101, 42.5, "42", None):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_layer_set_opacity(opacity=invalid)
    with pytest.raises(TypeError):
        adapter.paint_layer_set_opacity(layer_id=123, opacity=42)


def test_selection_modify_action_has_operation_specific_pixel_domain() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.painter_action_inputs import validate_selection_modify_action
    from app.painter_output import PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT

    assert validate_selection_modify_action(
        operation="feather", radius_px=1e-320
    ) == ("feather", 1e-320)
    assert validate_selection_modify_action(
        operation="expand", radius_px=1
    ) == ("expand", 1)

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid selection modify must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        {"operation": "grow", "radius_px": 1},
        {"operation": 1, "radius_px": 1},
        {"operation": "feather", "radius_px": True},
        {"operation": "feather", "radius_px": float("nan")},
        {"operation": "feather", "radius_px": 0.0},
        {
            "operation": "feather",
            "radius_px": PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT + 1,
        },
        {"operation": "expand", "radius_px": 1.5},
        {"operation": "contract", "radius_px": "1"},
        {"operation": "border", "radius_px": 0},
    )
    for payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_selection_modify(**payload)


def test_selection_transform_action_rejects_nonfinite_and_singular_inputs_before_owner() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.painter_action_inputs import validate_selection_transform_action

    identity, identity_phase, identity_target = validate_selection_transform_action(
        translate_x=0.0,
        translate_y=0.0,
        scale_x=1.0,
        scale_y=1.0,
        rotation_degrees=0.0,
        skew_x_degrees=0.0,
        skew_y_degrees=0.0,
        pivot_x=0.5,
        pivot_y=0.5,
        flip_x=False,
        flip_y=False,
        phase="commit",
        target="selected_pixels",
    )
    assert identity == {
        "translate_x": 0.0,
        "translate_y": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "rotation_degrees": 0.0,
        "skew_x_degrees": 0.0,
        "skew_y_degrees": 0.0,
        "pivot_x": 0.5,
        "pivot_y": 0.5,
        "flip_x": False,
        "flip_y": False,
    }
    assert (identity_phase, identity_target) == ("commit", "selected_pixels")

    settings, phase, target = validate_selection_transform_action(
        translate_x=0.0,
        translate_y=-12.5,
        scale_x=-1.0,
        scale_y=1.0,
        rotation_degrees=720.0,
        skew_x_degrees=-89.999,
        skew_y_degrees=89.999,
        pivot_x=0.0,
        pivot_y=1.0,
        flip_x=False,
        flip_y=True,
        phase="preview",
        target="layer_all",
    )
    assert settings["scale_x"] == -1.0
    assert (phase, target) == ("preview", "layer_all")

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid transform must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        {"translate_x": True},
        {"translate_y": float("nan")},
        {"scale_x": 0.0},
        {"scale_y": float("inf")},
        {"rotation_degrees": "90"},
        {"skew_x_degrees": -90.0},
        {"skew_y_degrees": 90.0},
        {"pivot_x": -0.001},
        {"pivot_y": 1.001},
        {"flip_x": 1},
        {"flip_y": 0},
        {"phase": "apply"},
        {"target": "pixels"},
    )
    for payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_selection_transform(**payload)

    from app.drawing import PaintDialog

    cancel_calls = []
    preview_marker = {"existing": True}
    direct_dialog = SimpleNamespace(
        _pixel_transform_preview=preview_marker,
        _cancel_selection_transform=lambda: cancel_calls.append(True),
    )
    with pytest.raises(ValueError, match="scale"):
        PaintDialog._preview_selection_transform(direct_dialog, scale_x=0.0)
    assert cancel_calls == []
    assert direct_dialog._pixel_transform_preview is preview_marker


def test_resize_actions_validate_dimensions_and_background_before_owner() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.painter_output import PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid resize must fail before owner resolution")

    adapter = Adapter()
    for invalid in (True, 63, 16384.5, "1024", None):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_image_resize(width=invalid, height=1024)
    with pytest.raises(ValueError):
        adapter.paint_image_resize(
            width=PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT + 1,
            height=1024,
        )
    for background in (None, 123, "not-a-color"):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_canvas_resize(
                width=1024,
                height=1024,
                background=background,
            )

    from app.drawing import PaintDialog

    undo_calls = []
    direct_dialog = SimpleNamespace(
        _canvas_document_size=(512, 512),
        _push_undo_state=lambda label: undo_calls.append(label),
    )
    with pytest.raises(ValueError, match="invalid Painter canvas color"):
        PaintDialog._resize_canvas_document(
            direct_dialog,
            1024,
            1024,
            background="not-a-color",
        )
    assert undo_calls == []


def test_document_export_action_validates_complete_payload_before_owner() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.painter_action_inputs import validate_document_export_action

    assert validate_document_export_action(
        path="output.png",
        format_name="png",
        include_background=False,
        bit_depth=16,
        bake_unsupported=True,
        quality=100,
        source_icc="",
        output_icc="profile.icc",
        rendering_intent=3,
    ) == {
        "path": "output.png",
        "format_name": "png",
        "include_background": False,
        "bit_depth": 16,
        "bake_unsupported": True,
        "quality": 100,
        "source_icc": None,
        "output_icc": "profile.icc",
        "rendering_intent": 3,
    }
    preserved = validate_document_export_action(
        path="  folder/name.png  ",
        format_name="png",
        include_background=True,
        bit_depth=8,
        bake_unsupported=False,
        quality=95,
        source_icc="",
        output_icc="",
        rendering_intent=1,
    )
    assert preserved["path"] == "  folder/name.png  "

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid export must fail before owner resolution")

    adapter = Adapter()
    invalid_calls = (
        {"path": "", "format": "png"},
        {"path": "   ", "format": "png"},
        {"path": 123, "format": "png"},
        {"path": "x.png", "format": "jpg"},
        {"path": "x.png", "format": ""},
        {"path": "x.png", "format": "png", "include_background": 1},
        {"path": "x.png", "format": "png", "bit_depth": True},
        {"path": "x.png", "format": "png", "bit_depth": 32},
        {"path": "x.webp", "format": "webp", "bit_depth": 16},
        {"path": "x.psd", "format": "psd", "bit_depth": 16},
        {"path": "x.png", "format": "png", "bake_unsupported": 0},
        {"path": "x.png", "format": "png", "quality": 0},
        {"path": "x.png", "format": "png", "quality": 95.5},
        {"path": "x.png", "format": "png", "source_icc": None},
        {"path": "x.png", "format": "png", "output_icc": 1},
        {"path": "x.png", "format": "png", "rendering_intent": 4},
        {"path": "x.png", "format": "png", "rendering_intent": True},
    )
    for payload in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_document_export(**payload)


def test_guide_actions_use_exact_normalized_and_finite_domains() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.drawing import DrawingCanvas
    from app.painter_action_inputs import (
        validate_perspective_guide_action,
        validate_symmetry_guide_action,
    )

    perspective = validate_perspective_guide_action(
        enabled=True,
        horizon=0.0,
        left_x=-2.0,
        left_y=3.0,
        right_x=4.0,
        right_y=-5.0,
        center_x=None,
        center_y=None,
        vertical_x=None,
        vertical_y=None,
        mode=3,
        snap=False,
    )
    assert perspective["horizon"] == 0.0
    assert perspective["left_x"] == -2.0
    assert validate_symmetry_guide_action(
        enabled=False,
        axis="horizontal",
        position=1.0,
    ) == (False, "horizontal", 1.0)

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid guide input must fail before owner resolution")

    adapter = Adapter()
    invalid_perspective = (
        {"enabled": 1},
        {"snap": 0},
        {"mode": True},
        {"mode": 0},
        {"mode": 4},
        {"horizon": -0.001},
        {"horizon": 1.001},
        {"left_x": True},
        {"right_y": float("nan")},
        {"vertical_y": float("inf")},
    )
    for payload in invalid_perspective:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_guide_perspective(**payload)
    for payload in (
        {"enabled": 1},
        {"axis": "x"},
        {"axis": 1},
        {"position": -0.001},
        {"position": 1.001},
        {"position": float("nan")},
    ):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_guide_symmetry(**payload)

    canvas = SimpleNamespace(
        _perspective_guides_enabled=False,
        _perspective_horizon_norm=0.5,
        _perspective_mode=2,
        _perspective_snap_enabled=False,
        _perspective_left_vp=(0.0, 0.5),
        _perspective_right_vp=(1.0, 0.5),
        _perspective_center_vp=(0.5, 0.5),
        _perspective_vertical_vp=(0.5, -1.0),
        update=lambda: None,
    )
    DrawingCanvas.set_perspective_guides(canvas, enabled=True, horizon=1.0, mode=1)
    assert canvas._perspective_horizon_norm == 1.0
    DrawingCanvas.set_symmetry_guide(canvas, position=0.0, axis="vertical")
    assert canvas._symmetry_guide_position_norm == 0.0
    assert DrawingCanvas.perspective_guide_state(canvas)["horizon"] == 1.0
    assert DrawingCanvas.symmetry_guide_state(canvas)["position"] == 0.0

    class PainterSpy:
        def __init__(self):
            self.lines = []

        def save(self):
            return None

        def restore(self):
            return None

        def setPen(self, value):
            return None

        def setBrush(self, value):
            return None

        def drawLine(self, start, end):
            self.lines.append((start, end))

        def drawEllipse(self, *args):
            return None

    perspective_painter = PainterSpy()
    DrawingCanvas._paint_perspective_guides(canvas, perspective_painter, 200, 100)
    assert perspective_painter.lines[0][0].y() == 100.0
    DrawingCanvas.set_perspective_guides(canvas, horizon=0.0)
    assert DrawingCanvas.perspective_guide_state(canvas)["horizon"] == 0.0
    top_painter = PainterSpy()
    DrawingCanvas._paint_perspective_guides(canvas, top_painter, 200, 100)
    assert top_painter.lines[0][0].y() == 0.0
    canvas._symmetry_guide_enabled = True
    canvas._symmetry_guide_axis = "vertical"
    symmetry_painter = PainterSpy()
    DrawingCanvas._paint_symmetry_guide(canvas, symmetry_painter, 200, 100)
    assert all(line[0].x() == 0.0 for line in symmetry_painter.lines[:2])


def test_material_preview_action_uses_declared_finite_light_domain() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog
    from app.painter_action_inputs import validate_material_preview_action

    assert validate_material_preview_action(
        enabled=True,
        azimuth_deg=-180.0,
        elevation_deg=85.0,
        require_authored_field=True,
    ) == {
        "enabled": True,
        "azimuth_deg": -180.0,
        "elevation_deg": 85.0,
    }
    assert validate_material_preview_action(
        azimuth_deg=180.0,
        elevation_deg=5.0,
        require_authored_field=True,
    ) == {
        "enabled": None,
        "azimuth_deg": 180.0,
        "elevation_deg": 5.0,
    }

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid material preview input reached owner resolution")

    adapter = Adapter()
    invalid_payloads = (
        {},
        {"enabled": None},
        {"enabled": 1},
        {"azimuth_deg": True},
        {"azimuth_deg": -180.001},
        {"azimuth_deg": 180.001},
        {"azimuth_deg": float("nan")},
        {"elevation_deg": 4.999},
        {"elevation_deg": 85.001},
        {"elevation_deg": float("inf")},
    )
    for payload in invalid_payloads:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_material_preview_set(**payload)

    direct = SimpleNamespace(
        _material_preview_enabled=False,
        _material_preview_light_azimuth_deg=-38.0,
        _material_preview_light_elevation_deg=48.0,
    )
    before = dict(vars(direct))
    with pytest.raises(ValueError):
        PaintDialog._set_material_preview(direct)
    assert vars(direct) == before
    for payload in invalid_payloads[2:]:
        with pytest.raises((TypeError, ValueError)):
            PaintDialog._set_material_preview(direct, **payload)
        assert vars(direct) == before
    with pytest.raises(TypeError):
        PaintDialog._set_material_preview(
            direct,
            enabled=True,
            azimuth_deg=None,
        )
    assert vars(direct) == before

    from app.painter_material_paint import normalize_material_preview_light_angles

    assert normalize_material_preview_light_angles(0.0, 85.0) == (0.0, 85.0)
    assert normalize_material_preview_light_angles(-999.0, 999.0) == (-180.0, 85.0)
    assert normalize_material_preview_light_angles(float("nan"), float("inf")) == (
        -38.0,
        48.0,
    )

    schema = ActionRegistry(owner=None).get_action_schema(
        "paint.material.preview.set"
    )["params_schema"]
    assert schema["properties"]["azimuth_deg"] == {
        "type": "number",
        "minimum": -180.0,
        "maximum": 180.0,
    }
    assert schema["properties"]["elevation_deg"] == {
        "type": "number",
        "minimum": 5.0,
        "maximum": 85.0,
    }
    assert schema["anyOf"] == [
        {"required": ["enabled"]},
        {"required": ["azimuth_deg"]},
        {"required": ["elevation_deg"]},
    ]


def test_reference_sample_and_palette_actions_reject_coercion_before_owner() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.painter_action_inputs import (
        validate_reference_palette_action,
        validate_reference_sample_action,
    )
    from app.painter_reference_board import (
        extract_reference_palette,
        sample_reference_color,
    )

    assert validate_reference_sample_action(
        reference_id="reference:1",
        x_norm=0.0,
        y_norm=1.0,
        apply=False,
    ) == ("reference:1", 0.0, 1.0, False)
    assert validate_reference_palette_action(
        reference_id="",
        max_colors=12,
        apply=True,
    ) == ("", 12, True)

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid reference input reached owner resolution")

    adapter = Adapter()
    for payload in (
        {"reference_id": None},
        {"x_norm": True},
        {"x_norm": -0.001},
        {"x_norm": 1.001},
        {"y_norm": float("nan")},
        {"y_norm": float("inf")},
        {"apply": 1},
        {"apply": None},
    ):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_reference_sample_color(**payload)
    for payload in (
        {"reference_id": None},
        {"max_colors": True},
        {"max_colors": 0},
        {"max_colors": 13},
        {"max_colors": 4.0},
        {"max_colors": "4"},
        {"apply": 1},
        {"apply": None},
    ):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_reference_extract_palette(**payload)

    with pytest.raises(ValueError, match="x_norm"):
        sample_reference_color("missing.png", x_norm=-0.1)
    with pytest.raises(TypeError, match="max_colors"):
        extract_reference_palette("missing.png", max_colors=True)


def test_blockout_preview_actions_share_strict_resource_bounds_before_owner() -> None:
    import inspect

    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_contract import (
        PAINT_ACTION_BLOCKOUT_PREVIEW_MAX_PX,
        PAINT_ACTION_BLOCKOUT_PREVIEW_MIN_PX,
        PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
        PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        PAINT_ACTION_REQUEST_RESOURCE_CONTRACT,
    )
    from app.painter_action_inputs import validate_blockout_preview_action

    assert validate_blockout_preview_action(
        PAINT_ACTION_BLOCKOUT_PREVIEW_MIN_PX,
        PAINT_ACTION_BLOCKOUT_PREVIEW_MAX_PX,
    ) == (
        PAINT_ACTION_BLOCKOUT_PREVIEW_MIN_PX,
        PAINT_ACTION_BLOCKOUT_PREVIEW_MAX_PX,
    )

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid blockout preview reached owner resolution")

    adapter = Adapter()
    endpoints = (
        adapter.paint_3d_blockout_state,
        adapter.paint_3d_blockout_add,
        adapter.paint_3d_blockout_update,
        adapter.paint_3d_blockout_delete,
        adapter.paint_3d_blockout_duplicate,
        adapter.paint_3d_blockout_align_ground,
        adapter.paint_3d_blockout_snap,
        adapter.paint_3d_blockout_camera,
        adapter.paint_3d_blockout_material_preview,
        adapter.paint_3d_blockout_camera_preset,
        adapter.paint_3d_blockout_bake,
    )
    invalid_values = (
        True,
        63,
        8193,
        640.0,
        "640",
        None,
    )
    for endpoint in endpoints:
        signature = inspect.signature(endpoint)
        assert signature.parameters["preview_width"].default == (
            PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX
        )
        assert signature.parameters["preview_height"].default == (
            PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX
        )
        for value in invalid_values:
            with pytest.raises((TypeError, ValueError)):
                endpoint(preview_width=value)
            with pytest.raises((TypeError, ValueError)):
                endpoint(preview_height=value)

    with pytest.raises(TypeError, match="preview_width"):
        adapter._paint_3d_blockout_payload(None, preview_width=True)

    schemas = ActionRegistry(owner=None).list_actions()
    blockout_actions = [
        row for row in schemas if row["id"].startswith("paint.3d_blockout.")
    ]
    assert len(blockout_actions) == len(endpoints)
    for action in blockout_actions:
        properties = action["params_schema"]["properties"]
        assert properties["preview_width"] == {
            "type": "integer",
            "minimum": PAINT_ACTION_BLOCKOUT_PREVIEW_MIN_PX,
            "maximum": PAINT_ACTION_BLOCKOUT_PREVIEW_MAX_PX,
        }
        assert properties["preview_height"] == properties["preview_width"]
    assert PAINT_ACTION_REQUEST_RESOURCE_CONTRACT[
        "blockout_preview_default_width_px"
    ] == PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX
    assert PAINT_ACTION_REQUEST_RESOURCE_CONTRACT[
        "blockout_preview_default_height_px"
    ] == PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX


def test_blockout_projection_viewport_measurement_producer_is_reproducible() -> None:
    from tools.qa_painter_blockout_projection_viewport import _percentile_95, build_report

    assert _percentile_95([float(value) for value in range(1, 26)]) == 24.0
    report = build_report(iterations=2)
    assert report["result"] == "pass"
    assert len(report["scene_sha256"]) == 64
    assert [row["geometry"] for row in report["measurements"]] == [
        {"faces": 145, "edges": 515, "floor_tiles": 685},
    ] * 3


def test_blockout_camera_action_rejects_nonfinite_coercion_and_empty_before_owner() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_3d_blockout import (
        BLOCKOUT_CAMERA_FOV_MAX_DEGREES,
        BLOCKOUT_CAMERA_FOV_MIN_DEGREES,
        BLOCKOUT_CAMERA_MAX_DISTANCE,
        BLOCKOUT_CAMERA_MIN_DISTANCE,
        BLOCKOUT_CAMERA_PITCH_MAX_DEGREES,
        BLOCKOUT_CAMERA_PITCH_MIN_DEGREES,
        BLOCKOUT_CAMERA_TARGET_MAX,
        BLOCKOUT_CAMERA_TARGET_MIN,
        BLOCKOUT_CAMERA_YAW_MAX_DEGREES,
        BLOCKOUT_CAMERA_YAW_MIN_DEGREES,
    )
    from app.painter_action_inputs import validate_blockout_camera_action

    assert validate_blockout_camera_action(
        {
            "yaw_degrees": 0,
            "pitch_degrees": BLOCKOUT_CAMERA_PITCH_MIN_DEGREES,
            "distance": BLOCKOUT_CAMERA_MIN_DISTANCE,
            "target_x": 0,
            "target_y": 0,
            "target_z": 0,
            "fov_degrees": BLOCKOUT_CAMERA_FOV_MAX_DEGREES,
        }
    ) == {
        "yaw_degrees": 0.0,
        "pitch_degrees": BLOCKOUT_CAMERA_PITCH_MIN_DEGREES,
        "distance": BLOCKOUT_CAMERA_MIN_DISTANCE,
        "target_x": 0.0,
        "target_y": 0.0,
        "target_z": 0.0,
        "fov_degrees": BLOCKOUT_CAMERA_FOV_MAX_DEGREES,
    }
    assert validate_blockout_camera_action(
        {"fov": BLOCKOUT_CAMERA_FOV_MIN_DEGREES}, allow_aliases=True
    ) == {"fov_degrees": BLOCKOUT_CAMERA_FOV_MIN_DEGREES}

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid blockout camera input reached owner resolution")

    adapter = Adapter()
    for payload in (
        {},
        {"yaw_degrees": True},
        {"yaw_degrees": "1"},
        {"pitch_degrees": float("nan")},
        {"distance": float("inf")},
        {"distance": BLOCKOUT_CAMERA_MIN_DISTANCE - 0.001},
        {"target_x": float("-inf")},
        {"yaw_degrees": BLOCKOUT_CAMERA_YAW_MAX_DEGREES + 0.001},
        {"pitch_degrees": BLOCKOUT_CAMERA_PITCH_MIN_DEGREES - 0.001},
        {"target_x": BLOCKOUT_CAMERA_TARGET_MAX + 0.001},
        {"distance": BLOCKOUT_CAMERA_MAX_DISTANCE + 0.001},
        {"fov_degrees": BLOCKOUT_CAMERA_FOV_MIN_DEGREES - 0.001},
        {"fov_degrees": BLOCKOUT_CAMERA_FOV_MAX_DEGREES + 0.001},
        {"unknown": 1.0},
    ):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_3d_blockout_camera(**payload)

    schema = ActionRegistry(owner=None).get_action_schema(
        "paint.3d_blockout.camera"
    )["params_schema"]
    assert schema["properties"]["distance"]["minimum"] == BLOCKOUT_CAMERA_MIN_DISTANCE
    assert schema["properties"]["distance"]["maximum"] == BLOCKOUT_CAMERA_MAX_DISTANCE
    assert schema["properties"]["yaw_degrees"]["minimum"] == BLOCKOUT_CAMERA_YAW_MIN_DEGREES
    assert schema["properties"]["yaw_degrees"]["maximum"] == BLOCKOUT_CAMERA_YAW_MAX_DEGREES
    assert schema["properties"]["pitch_degrees"]["minimum"] == BLOCKOUT_CAMERA_PITCH_MIN_DEGREES
    assert schema["properties"]["pitch_degrees"]["maximum"] == BLOCKOUT_CAMERA_PITCH_MAX_DEGREES
    for field in ("target_x", "target_y", "target_z"):
        assert schema["properties"][field]["minimum"] == BLOCKOUT_CAMERA_TARGET_MIN
        assert schema["properties"][field]["maximum"] == BLOCKOUT_CAMERA_TARGET_MAX
    assert schema["properties"]["fov_degrees"] == {
        "type": "number",
        "minimum": BLOCKOUT_CAMERA_FOV_MIN_DEGREES,
        "maximum": BLOCKOUT_CAMERA_FOV_MAX_DEGREES,
    }
    assert schema["anyOf"] == [
        {"required": [field]}
        for field in (
            "yaw_degrees",
            "pitch_degrees",
            "distance",
            "target_x",
            "target_y",
            "target_z",
            "fov_degrees",
        )
    ]


def test_blockout_primitive_material_and_preset_inputs_use_product_controls_before_owner() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_3d_blockout import (
        BLOCKOUT_LIGHT_PITCH_MAX_DEGREES,
        BLOCKOUT_LIGHT_YAW_MIN_DEGREES,
        BLOCKOUT_PRIMITIVE_POSITION_MAX,
        BLOCKOUT_PRIMITIVE_POSITION_MIN,
        BLOCKOUT_PRIMITIVE_ROTATION_MAX_DEGREES,
        BLOCKOUT_PRIMITIVE_ROTATION_MIN_DEGREES,
        BLOCKOUT_PRIMITIVE_SCALE_MAX,
        BLOCKOUT_PRIMITIVE_SCALE_MIN,
    )
    from app.painter_action_inputs import validate_blockout_primitive_action

    endpoints = validate_blockout_primitive_action(
        {
            "x": BLOCKOUT_PRIMITIVE_POSITION_MIN,
            "y": BLOCKOUT_PRIMITIVE_POSITION_MAX,
            "rx": BLOCKOUT_PRIMITIVE_ROTATION_MIN_DEGREES,
            "ry": BLOCKOUT_PRIMITIVE_ROTATION_MAX_DEGREES,
            "sx": BLOCKOUT_PRIMITIVE_SCALE_MIN,
            "sy": BLOCKOUT_PRIMITIVE_SCALE_MAX,
            "opacity": 0.05,
            "color": "#a0B1c2",
            "wireframe": False,
        },
        require_authored_field=True,
    )
    assert endpoints["color"] == "#A0B1C2"

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid blockout product input reached owner resolution")

    adapter = Adapter()
    for payload in (
        {"x": True}, {"x": float("nan")}, {"x": 5.001}, {"rx": 180.001},
        {"sx": 0.099}, {"sx": 8.001}, {"color": "red"}, {"kind": "torus"},
        {"wireframe": 1}, {"unknown": 1},
    ):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_3d_blockout_add(**payload)
    with pytest.raises(ValueError, match="requires a primitive field"):
        adapter.paint_3d_blockout_update(primitive_id="blockout:1")
    with pytest.raises(ValueError, match="requires a setting"):
        adapter.paint_3d_blockout_material_preview()
    for payload in (
        {"material_lit": 1},
        {"light_yaw_degrees": float("inf")},
        {"light_yaw_degrees": 180.001},
        {"light_pitch_degrees": 4.999},
    ):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_3d_blockout_material_preview(**payload)
    with pytest.raises(ValueError, match="Unsupported"):
        adapter.paint_3d_blockout_camera_preset(preset="right")
    with pytest.raises(ValueError, match="finite"):
        adapter.paint_3d_blockout_duplicate(primitive_id="blockout:1", offset_x=float("nan"))
    for endpoint in (
        adapter.paint_3d_blockout_update,
        adapter.paint_3d_blockout_delete,
        adapter.paint_3d_blockout_duplicate,
        adapter.paint_3d_blockout_align_ground,
    ):
        with pytest.raises((TypeError, ValueError)):
            endpoint(primitive_id="")
    with pytest.raises(ValueError, match="requires enabled or primitive_id"):
        adapter.paint_3d_blockout_snap()
    with pytest.raises(TypeError, match="boolean"):
        adapter.paint_3d_blockout_snap(enabled=1)

    registry = ActionRegistry(owner=None)
    add_schema = registry.get_action_schema("paint.3d_blockout.add")["params_schema"]["properties"]
    assert add_schema["x"] == {
        "type": "number", "minimum": BLOCKOUT_PRIMITIVE_POSITION_MIN,
        "maximum": BLOCKOUT_PRIMITIVE_POSITION_MAX,
    }
    assert add_schema["rx"]["minimum"] == BLOCKOUT_PRIMITIVE_ROTATION_MIN_DEGREES
    assert add_schema["rx"]["maximum"] == BLOCKOUT_PRIMITIVE_ROTATION_MAX_DEGREES
    assert add_schema["sx"]["minimum"] == BLOCKOUT_PRIMITIVE_SCALE_MIN
    assert add_schema["sx"]["maximum"] == BLOCKOUT_PRIMITIVE_SCALE_MAX
    material_schema = registry.get_action_schema(
        "paint.3d_blockout.material_preview"
    )["params_schema"]
    assert len(material_schema["anyOf"]) == 7
    material_properties = material_schema["properties"]
    assert material_properties["light_yaw_degrees"]["minimum"] == BLOCKOUT_LIGHT_YAW_MIN_DEGREES
    assert material_properties["light_pitch_degrees"]["maximum"] == BLOCKOUT_LIGHT_PITCH_MAX_DEGREES
    snap_schema = registry.get_action_schema("paint.3d_blockout.snap")["params_schema"]
    assert snap_schema["properties"]["primitive_id"]["minLength"] == 1
    assert snap_schema["anyOf"] == [
        {"required": ["enabled"]}, {"required": ["primitive_id"]}
    ]


def test_stroke_request_matches_published_schema_before_owner() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_contract import (
        PAINT_ACTION_STROKE_BRISTLE_COUNT_MAX,
        PAINT_ACTION_STROKE_ENGINE_VERSION_MAX,
        PAINT_ACTION_STROKE_MIN_WIDTH_PX,
        PAINT_ACTION_STROKE_OPACITY_MAX_PERCENT,
        PAINT_ACTION_STROKE_SEED_MAX,
        PAINT_ACTION_STROKE_SEED_MIN,
    )
    from app.painter_action_inputs import validate_paint_stroke_request

    points = [{"x": 0.0, "y": 1.0}, {"x": 1.0, "y": 0.0}]
    endpoint_row = validate_paint_stroke_request(
        [{
            "points": [
                {"x": 0.0, "y": 1.0, "pressure": 0.0, "tilt_x": -1.0},
                {"x": 1.0, "y": 0.0, "pressure": 1.0, "tilt_x": 1.0},
            ],
            "opacity": PAINT_ACTION_STROKE_OPACITY_MAX_PERCENT,
            "width": PAINT_ACTION_STROKE_MIN_WIDTH_PX,
            "engine_version": PAINT_ACTION_STROKE_ENGINE_VERSION_MAX,
            "bristle_count": PAINT_ACTION_STROKE_BRISTLE_COUNT_MAX,
            "style": "round",
            "closed": False,
            "load_depletion": 0.0,
            "seed": PAINT_ACTION_STROKE_SEED_MAX,
        }]
    )[0]
    assert endpoint_row["width"] == PAINT_ACTION_STROKE_MIN_WIDTH_PX
    assert endpoint_row["bristle_count"] == PAINT_ACTION_STROKE_BRISTLE_COUNT_MAX

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid stroke request reached owner resolution")

    adapter = Adapter()
    invalid_strokes = (
        None,
        (),
        [],
        [{"points": points, "unknown": 1}],
        [{"points": [{"x": True, "y": 0.0}, points[1]]}],
        [{"points": [{"x": -0.001, "y": 0.0}, points[1]]}],
        [{"points": [{"x": 0.0, "y": 0.0, "pressure": 1.001}, points[1]]}],
        [{"points": [{"x": 0.0, "y": 0.0, "tilt_x": float("nan")}, points[1]]}],
        [{"points": points, "opacity": True}],
        [{"points": points, "opacity": 0}],
        [{"points": points, "width": float("inf")}],
        [{"points": points, "width": PAINT_ACTION_STROKE_MIN_WIDTH_PX - 0.001}],
        [{"points": points, "hardness": 50.0}],
        [{"points": points, "style": "unknown"}],
        [{"points": points, "closed": 1}],
        [{"points": points, "layer_id": 1}],
        [{"points": points, "layer_id": "   "}],
        [{"points": points, "seed": True}],
        [{"points": points, "seed": PAINT_ACTION_STROKE_SEED_MIN - 1}],
        [{"points": points, "seed": PAINT_ACTION_STROKE_SEED_MAX + 1}],
        [{"points": points, "load_depletion": 1.001}],
        [{"points": points, "path_mode": "curve"}],
    )
    for strokes in invalid_strokes:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_stroke_draw(strokes=strokes)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="undo_label"):
        adapter.paint_stroke_draw(strokes=[{"points": points}], undo_label=1)  # type: ignore[arg-type]

    schema = ActionRegistry(owner=None).get_action_schema("paint.stroke.draw")["params_schema"]
    stroke = schema["properties"]["strokes"]["items"]
    assert stroke["properties"]["width"]["minimum"] == PAINT_ACTION_STROKE_MIN_WIDTH_PX
    assert stroke["properties"]["opacity"]["maximum"] == PAINT_ACTION_STROKE_OPACITY_MAX_PERCENT
    assert stroke["properties"]["engine_version"]["maximum"] == PAINT_ACTION_STROKE_ENGINE_VERSION_MAX
    assert stroke["properties"]["bristle_count"]["maximum"] == PAINT_ACTION_STROKE_BRISTLE_COUNT_MAX
    assert stroke["properties"]["seed"] == {
        "type": "integer",
        "minimum": PAINT_ACTION_STROKE_SEED_MIN,
        "maximum": PAINT_ACTION_STROKE_SEED_MAX,
    }


def test_brush_style_lookup_failure_precedes_brush_mutation() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin

    class MissingStyleCombo:
        def findData(self, _value):
            return -1

    dialog = SimpleNamespace(brush_style_combo=MissingStyleCombo())

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            return dialog

    with pytest.raises(ValueError, match="missing from the active style control"):
        Adapter().paint_brush_set(style="round")
    assert not hasattr(dialog, "_pen_style")


def test_editor_object_actions_validate_before_owner_and_match_geometry_schema() -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry
    from app.painter_action_contract import (
        PAINT_ACTION_EDITOR_OBJECT_DEFAULT_LIMIT,
        PAINT_ACTION_EDITOR_OBJECT_MAX_POSITION_NORM,
        PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM,
    )
    from app.painter_action_inputs import (
        validate_editor_object_import_geometry_action,
        validate_editor_object_locator_action,
        validate_editor_objects_list_action,
    )

    assert validate_editor_objects_list_action(limit=0) == (None, True, 0)
    assert validate_editor_object_locator_action(object_id="  object:1  ")["object_id"] == "object:1"
    assert validate_editor_object_import_geometry_action(
        x_norm=0.0,
        y_norm=PAINT_ACTION_EDITOR_OBJECT_MAX_POSITION_NORM,
        width_norm=1.0,
        height_norm=PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM,
    ) == {
        "x_norm": 0.0,
        "y_norm": PAINT_ACTION_EDITOR_OBJECT_MAX_POSITION_NORM,
        "width_norm": 1.0,
        "height_norm": PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM,
    }

    class Adapter(PaintAdapterMixin):
        def _require_owner(self):
            raise AssertionError("invalid editor object input reached owner resolution")

    adapter = Adapter()
    for params in (
        {"include_inactive": 1},
        {"limit": True},
        {"limit": -1},
        {"limit": 1.5},
        {"limit": "1"},
        {"time_ms": True},
        {"time_ms": -1},
    ):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_editor_objects_list(**params)

    invalid_locators = (
        {"object_id": 1},
        {"kind": 1},
        {"object_id": "object:1", "kind": "type"},
        {"include_inactive": 1},
        {"output_dir": 1},
        {"force": 1},
        {"time_ms": True},
        {"time_ms": -1},
    )
    for endpoint in (adapter.paint_editor_object_render, adapter.paint_editor_object_import):
        for params in invalid_locators:
            with pytest.raises((TypeError, ValueError)):
                endpoint(**params)

    invalid_geometry = (
        {"x_norm": True},
        {"y_norm": "0.5"},
        {"width_norm": float("nan")},
        {"height_norm": float("inf")},
        {"x_norm": -0.001},
        {"x_norm": PAINT_ACTION_EDITOR_OBJECT_MAX_POSITION_NORM + 0.001},
        {"width_norm": PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM - 0.001},
        {"x_norm": 0.8, "width_norm": 0.3},
        {"y_norm": 0.8, "height_norm": 0.3},
    )
    for params in invalid_geometry:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_editor_object_import(**params)

    registry = ActionRegistry(owner=None)
    list_schema = registry.get_action_schema("paint.editor_objects.list")["params_schema"]
    render_schema = registry.get_action_schema("paint.editor_object.render")["params_schema"]
    import_schema = registry.get_action_schema("paint.editor_object.import")["params_schema"]
    assert list_schema["properties"]["limit"] == {"type": "integer", "minimum": 0}
    expected_locator_guard = {
        "not": {
            "allOf": [
                {
                    "required": ["object_id"],
                    "properties": {"object_id": {"pattern": r".*\S.*"}},
                },
                {
                    "required": ["kind"],
                    "properties": {"kind": {"pattern": r".*\S.*"}},
                },
            ]
        }
    }
    assert render_schema["not"] == expected_locator_guard["not"]
    assert import_schema["not"] == expected_locator_guard["not"]

    def schema_rejects_locator(schema, payload):
        return all(
            all(field in payload for field in clause.get("required", []))
            and all(
                re.search(rule["pattern"], payload[field]) is not None
                for field, rule in clause.get("properties", {}).items()
            )
            for clause in schema["not"]["allOf"]
        )

    for payload in (
        {},
        {"object_id": "", "kind": ""},
        {"object_id": "   ", "kind": "type"},
        {"object_id": "object:1", "kind": "   "},
    ):
        assert schema_rejects_locator(render_schema, payload) is False
    assert schema_rejects_locator(
        render_schema, {"object_id": "object:1", "kind": "type"}
    ) is True
    assert import_schema["properties"]["x_norm"]["maximum"] == PAINT_ACTION_EDITOR_OBJECT_MAX_POSITION_NORM
    assert import_schema["properties"]["width_norm"]["minimum"] == PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM
    assert "metadata" not in import_schema["properties"]
    assert (
        inspect.signature(PaintAdapterMixin.paint_editor_objects_list)
        .parameters["limit"]
        .default
        == PAINT_ACTION_EDITOR_OBJECT_DEFAULT_LIMIT
    )
