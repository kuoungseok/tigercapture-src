from __future__ import annotations

import math
import numbers
import operator
import re

from app.painter_output import PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT
from app.painter_action_contract import (
    PAINT_ACTION_BLOCKOUT_PREVIEW_MAX_PX,
    PAINT_ACTION_BLOCKOUT_PREVIEW_MIN_PX,
    PAINT_ACTION_MAX_REFERENCE_COLORS,
    PAINT_ACTION_BRUSH_STYLES,
    PAINT_ACTION_MAX_BRUSH_WIDTH_PX,
    PAINT_ACTION_MAX_POINTS_PER_STROKE,
    PAINT_ACTION_PATH_MIN_POINTS,
    PAINT_ACTION_PATH_SELECTION_MIN_POINTS,
    PAINT_ACTION_PATH_INDEX_MIN,
    PAINT_ACTION_MAX_STROKES_PER_REQUEST,
    PAINT_ACTION_STROKE_BRISTLE_COUNT_MAX,
    PAINT_ACTION_STROKE_BRISTLE_COUNT_MIN,
    PAINT_ACTION_STROKE_ENGINE_VERSION_MAX,
    PAINT_ACTION_STROKE_ENGINE_VERSION_MIN,
    PAINT_ACTION_STROKE_MIN_WIDTH_PX,
    PAINT_ACTION_STROKE_OPACITY_MAX_PERCENT,
    PAINT_ACTION_STROKE_OPACITY_MIN_PERCENT,
    PAINT_ACTION_STROKE_SEED_MAX,
    PAINT_ACTION_STROKE_SEED_MIN,
    PAINT_ACTION_STROKE_DEFAULT_COLOR,
    PAINT_ACTION_STROKE_DEFAULT_LOAD_DEPLETION,
    PAINT_ACTION_STROKE_DEFAULT_PATH_MODE,
    PAINT_ACTION_STROKE_DEFAULT_POINT_CHANNELS,
    PAINT_ACTION_STROKE_DEFAULT_STYLE,
    PAINT_ACTION_STROKE_DEFAULT_WIDTH_PX,
    PAINT_ACTION_EDITOR_OBJECT_DEFAULT_LIMIT,
    PAINT_ACTION_EDITOR_OBJECT_MAX_POSITION_NORM,
    PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM,
    PAINT_ACTION_BRUSH_OPACITY_MAX_PERCENT,
    PAINT_ACTION_BRUSH_OPACITY_MIN_PERCENT,
    PAINT_ACTION_QPOINT_COORDINATE_MAX,
    PAINT_ACTION_QPOINT_COORDINATE_MIN,
)
from app.painter_brush_domains import (
    BRUSH_ANGLE_RANGE,
    BRUSH_DETAIL_DEFAULTS,
    BRUSH_HARDNESS_RANGE,
    BRUSH_ROUNDNESS_RANGE,
    BRUSH_SPACING_RANGE,
    BRUSH_WIDTH_RANGE_PX,
)
from app.painter_material_paint import (
    MATERIAL_PREVIEW_AZIMUTH_MAX_DEGREES,
    MATERIAL_PREVIEW_AZIMUTH_MIN_DEGREES,
    MATERIAL_PREVIEW_ELEVATION_MAX_DEGREES,
    MATERIAL_PREVIEW_ELEVATION_MIN_DEGREES,
)
from app.painter_layer_compositor import BLEND_MODES
from app.painter_layer_contract import (
    PAINTER_LAYER_COLOR_LABEL_IDS,
    PAINTER_LAYER_NAME_MAX_CHARACTERS,
    PAINTER_LAYER_TYPES,
)
from app.painter_channel_contract import PAINTER_CHANNEL_IDS
from app.painter_reference_board import (
    REFERENCE_DEFAULT_HEIGHT_NORM,
    REFERENCE_DEFAULT_OPACITY,
    REFERENCE_DEFAULT_ROTATION_DEGREES,
    REFERENCE_DEFAULT_WIDTH_NORM,
    REFERENCE_DEFAULT_X_NORM,
    REFERENCE_DEFAULT_Y_NORM,
    REFERENCE_DUPLICATE_OFFSET_NORM,
    REFERENCE_NAME_MAX_CHARACTERS,
    REFERENCE_OPACITY_MAX,
    REFERENCE_OPACITY_MIN,
    REFERENCE_POSITION_MAX_NORM,
    REFERENCE_POSITION_MIN_NORM,
    REFERENCE_ROTATION_MAX_DEGREES,
    REFERENCE_ROTATION_MIN_DEGREES,
    REFERENCE_SIZE_MAX_NORM,
    REFERENCE_SIZE_MIN_NORM,
)
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
    BLOCKOUT_CAMERA_PRESETS,
    BLOCKOUT_LIGHT_PITCH_MAX_DEGREES,
    BLOCKOUT_LIGHT_PITCH_MIN_DEGREES,
    BLOCKOUT_LIGHT_YAW_MAX_DEGREES,
    BLOCKOUT_LIGHT_YAW_MIN_DEGREES,
    BLOCKOUT_PRIMITIVE_OPACITY_MAX,
    BLOCKOUT_PRIMITIVE_OPACITY_MIN,
    BLOCKOUT_PRIMITIVE_POSITION_MAX,
    BLOCKOUT_PRIMITIVE_POSITION_MIN,
    BLOCKOUT_PRIMITIVE_ROTATION_MAX_DEGREES,
    BLOCKOUT_PRIMITIVE_ROTATION_MIN_DEGREES,
    BLOCKOUT_PRIMITIVE_SCALE_MAX,
    BLOCKOUT_PRIMITIVE_SCALE_MIN,
    SUPPORTED_PRIMITIVES,
)

PAINTER_SELECTION_ASPECTS = ("free", "square", "16:9", "4:3")
PAINTER_SELECTION_MODES = ("new", "add", "subtract", "intersect")
PAINTER_COLOR_SELECTION_PHASES = ("preview", "commit", "cancel")
PAINTER_SELECTION_MODIFY_OPERATIONS = ("feather", "expand", "contract", "border")
PAINTER_SELECTION_TRANSFORM_PHASES = ("preview", "commit", "cancel")
PAINTER_SELECTION_TRANSFORM_TARGETS = (
    "selected_pixels", "raster", "strokes", "layer_mask", "layer_all",
)
PAINTER_SELECTION_SKEW_MIN_DEGREES = -90.0
PAINTER_SELECTION_SKEW_MAX_DEGREES = 90.0
PAINTER_LAYER_OPACITY_MIN_PERCENT = 0
PAINTER_LAYER_OPACITY_MAX_PERCENT = 100
PAINTER_LAYER_MASK_ALPHA_MIN = 0
PAINTER_LAYER_MASK_ALPHA_MAX = 255
PAINTER_LAYER_MASK_RADIUS_MIN_PX = 0.5
PAINTER_DOCUMENT_EXPORT_FORMATS = ("png", "jpeg", "webp", "tiff", "psd")
PAINTER_DOCUMENT_EXPORT_BIT_DEPTHS = (8, 16)
PAINTER_DOCUMENT_RENDERING_INTENT_MIN = 0
PAINTER_DOCUMENT_RENDERING_INTENT_MAX = 3
PAINTER_DOCUMENT_EXPORT_QUALITY_MIN = 1
PAINTER_DOCUMENT_EXPORT_QUALITY_MAX = 100
PAINTER_PERSPECTIVE_MODE_MIN = 1
PAINTER_PERSPECTIVE_MODE_MAX = 3
PAINTER_SYMMETRY_AXES = ("vertical", "horizontal")
PAINTER_CANVAS_FLIP_AXES = ("horizontal", "vertical")
PAINTER_LAYER_MASK_SOURCE_TYPES = (
    "selection",
    "path",
    "channel",
    "alpha",
    "layer_alpha",
    "white",
    "reveal_all",
)
PAINTER_ACTION_INPUT_UNSET = object()

_BLOCKOUT_CAMERA_ALIASES = {
    "yaw_degrees": ("yaw",),
    "pitch_degrees": ("pitch",),
    "distance": ("zoom_distance", "camera_distance"),
    "target_x": ("tx", "pan_x"),
    "target_y": ("ty", "pan_y"),
    "target_z": ("tz", "pan_z"),
    "fov_degrees": ("fov",),
}

_STROKE_FIELDS = {
    "points", "color", "opacity", "width", "style", "hardness", "spacing",
    "angle", "roundness", "closed", "layer_id", "engine_version",
    "bristle_count", "seed", "load_depletion", "path_mode",
}
_STROKE_POINT_FIELDS = {
    "x", "y", "pressure", "tilt", "tilt_x", "tilt_y", "rotation",
    "tangential_pressure", "load",
}


def validate_paint_stroke_request(strokes: object) -> list[dict[str, object]]:
    """Validate the complete atomic stroke batch before resolving the Painter owner."""

    if not isinstance(strokes, list):
        raise TypeError("strokes must be an array")
    if not strokes:
        raise ValueError("strokes must contain at least one stroke")
    if len(strokes) > PAINT_ACTION_MAX_STROKES_PER_REQUEST:
        raise ValueError(
            f"strokes cannot contain more than {PAINT_ACTION_MAX_STROKES_PER_REQUEST} entries"
        )
    resolved_rows: list[dict[str, object]] = []
    for index, source in enumerate(strokes):
        if not isinstance(source, dict):
            raise TypeError(f"stroke {index} must be an object")
        unknown = sorted(set(source) - _STROKE_FIELDS)
        if unknown:
            raise ValueError(f"stroke {index} has unknown fields: {', '.join(unknown)}")
        raw_points = source.get("points")
        if not isinstance(raw_points, list):
            raise TypeError(f"stroke {index} points must be an array")
        if not 2 <= len(raw_points) <= PAINT_ACTION_MAX_POINTS_PER_STROKE:
            raise ValueError(f"stroke {index} point count is outside the Action request bounds")
        points: list[dict[str, float]] = []
        for point_index, point in enumerate(raw_points):
            if not isinstance(point, dict):
                raise TypeError(f"stroke {index} point {point_index} must be an object")
            unknown_point = sorted(set(point) - _STROKE_POINT_FIELDS)
            if unknown_point:
                raise ValueError(
                    f"stroke {index} point {point_index} has unknown fields: {', '.join(unknown_point)}"
                )
            if "x" not in point or "y" not in point:
                raise ValueError(f"stroke {index} point {point_index} requires x and y")
            resolved_point: dict[str, float] = {
                "x": _strict_normalized_real(point["x"], field="x"),
                "y": _strict_normalized_real(point["y"], field="y"),
            }
            for field in ("pressure", "tilt", "rotation", "load"):
                resolved_point[field] = _strict_normalized_real(
                    point.get(field, PAINT_ACTION_STROKE_DEFAULT_POINT_CHANNELS[field]),
                    field=field,
                )
            for field in ("tilt_x", "tilt_y", "tangential_pressure"):
                number = _strict_finite_real(
                    point.get(field, PAINT_ACTION_STROKE_DEFAULT_POINT_CHANNELS[field]),
                    field=field,
                )
                if not -1.0 <= number <= 1.0:
                    raise ValueError(f"Painter action {field} must be between -1 and 1")
                resolved_point[field] = number
            points.append(resolved_point)
        row: dict[str, object] = dict(source)
        row["points"] = points
        row.setdefault("color", PAINT_ACTION_STROKE_DEFAULT_COLOR)
        row.setdefault("opacity", PAINT_ACTION_STROKE_OPACITY_MAX_PERCENT)
        row.setdefault("width", PAINT_ACTION_STROKE_DEFAULT_WIDTH_PX)
        row.setdefault("style", PAINT_ACTION_STROKE_DEFAULT_STYLE)
        row.setdefault("hardness", BRUSH_DETAIL_DEFAULTS["hardness"])
        row.setdefault("spacing", BRUSH_DETAIL_DEFAULTS["spacing"])
        row.setdefault("angle", BRUSH_DETAIL_DEFAULTS["angle"])
        row.setdefault("roundness", BRUSH_DETAIL_DEFAULTS["roundness"])
        row.setdefault("closed", False)
        row.setdefault("bristle_count", PAINT_ACTION_STROKE_BRISTLE_COUNT_MIN)
        row.setdefault("load_depletion", PAINT_ACTION_STROKE_DEFAULT_LOAD_DEPLETION)
        row.setdefault("path_mode", PAINT_ACTION_STROKE_DEFAULT_PATH_MODE)
        if "color" in row:
            color = row["color"]
            if not isinstance(color, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", color) is None:
                raise ValueError(f"stroke {index} color must be #RRGGBB")
        integer_domains = {
            "opacity": (PAINT_ACTION_STROKE_OPACITY_MIN_PERCENT, PAINT_ACTION_STROKE_OPACITY_MAX_PERCENT),
            "hardness": BRUSH_HARDNESS_RANGE,
            "spacing": BRUSH_SPACING_RANGE,
            "angle": BRUSH_ANGLE_RANGE,
            "roundness": BRUSH_ROUNDNESS_RANGE,
            "engine_version": (PAINT_ACTION_STROKE_ENGINE_VERSION_MIN, PAINT_ACTION_STROKE_ENGINE_VERSION_MAX),
            "bristle_count": (PAINT_ACTION_STROKE_BRISTLE_COUNT_MIN, PAINT_ACTION_STROKE_BRISTLE_COUNT_MAX),
        }
        for field, (minimum, maximum) in integer_domains.items():
            if field in row:
                row[field] = validate_action_integer_domain(
                    row[field], field=field, minimum=minimum, maximum=maximum
                )
        if "seed" in row:
            row["seed"] = validate_action_integer_domain(
                row["seed"],
                field="seed",
                minimum=PAINT_ACTION_STROKE_SEED_MIN,
                maximum=PAINT_ACTION_STROKE_SEED_MAX,
            )
        for field, minimum, maximum in (
            ("width", PAINT_ACTION_STROKE_MIN_WIDTH_PX, PAINT_ACTION_MAX_BRUSH_WIDTH_PX),
            ("load_depletion", 0.0, 1.0),
        ):
            if field in row:
                number = _strict_finite_real(row[field], field=field)
                if not minimum <= number <= maximum:
                    raise ValueError(f"Painter action {field} must be between {minimum} and {maximum}")
                row[field] = number
        if "style" in row:
            if not isinstance(row["style"], str) or row["style"] not in PAINT_ACTION_BRUSH_STYLES:
                raise ValueError(f"stroke {index} has invalid style")
        if "path_mode" in row:
            if not isinstance(row["path_mode"], str) or row["path_mode"] not in {"smooth", "polyline"}:
                raise ValueError(f"stroke {index} has invalid path_mode")
        for field in ("closed",):
            if field in row and not isinstance(row[field], bool):
                raise TypeError(f"stroke {index} {field} must be a boolean")
        if "layer_id" in row:
            if not isinstance(row["layer_id"], str):
                raise TypeError(f"stroke {index} layer_id must be a string")
            row["layer_id"] = row["layer_id"].strip()
            if not row["layer_id"]:
                raise ValueError(f"stroke {index} layer_id must not be blank")
        resolved_rows.append(row)
    return resolved_rows


def validate_editor_objects_list_action(
    *, time_ms: object = None, include_inactive: object = True, limit: object = PAINT_ACTION_EDITOR_OBJECT_DEFAULT_LIMIT
) -> tuple[int | None, bool, int]:
    if not isinstance(include_inactive, bool):
        raise TypeError("Painter editor objects include_inactive must be a boolean")
    resolved_time = None if time_ms is None else normalize_paint_time_ms(time_ms)
    resolved_limit = _strict_integer(limit, field="limit")
    if resolved_limit < 0:
        raise ValueError("Painter editor objects limit must be nonnegative")
    return resolved_time, include_inactive, resolved_limit


def validate_brush_set_action(
    *,
    preset: object = "",
    style: object = "",
    width: object = None,
    opacity: object = None,
    hardness: object = None,
    spacing: object = None,
    angle: object = None,
    roundness: object = None,
    flip_x: object = None,
    flip_y: object = None,
    dynamics: object = None,
) -> dict[str, object]:
    if not isinstance(preset, str) or not isinstance(style, str):
        raise TypeError("Painter action preset and style must be strings")
    resolved_preset = preset.strip()
    resolved_style = style
    if preset and not resolved_preset:
        raise ValueError("Painter brush preset must not be blank")
    if style and resolved_style not in PAINT_ACTION_BRUSH_STYLES:
        raise ValueError("Painter brush style is outside the published action enum")
    resolved: dict[str, object] = {
        "preset": resolved_preset,
        "style": resolved_style,
        "width": None,
        "opacity": None,
        "hardness": None,
        "spacing": None,
        "angle": None,
        "roundness": None,
        "flip_x": None,
        "flip_y": None,
        "dynamics": None,
    }
    domains = {
        "width": (int(BRUSH_WIDTH_RANGE_PX[0]), int(BRUSH_WIDTH_RANGE_PX[1]), width),
        "opacity": (PAINT_ACTION_BRUSH_OPACITY_MIN_PERCENT, PAINT_ACTION_BRUSH_OPACITY_MAX_PERCENT, opacity),
        "hardness": (*BRUSH_HARDNESS_RANGE, hardness),
        "spacing": (*BRUSH_SPACING_RANGE, spacing),
        "angle": (*BRUSH_ANGLE_RANGE, angle),
        "roundness": (*BRUSH_ROUNDNESS_RANGE, roundness),
    }
    for field, (minimum, maximum, supplied) in domains.items():
        if supplied is not None:
            resolved[field] = validate_action_integer_domain(
                supplied, field=field, minimum=minimum, maximum=maximum
            )
    for field, supplied in (("flip_x", flip_x), ("flip_y", flip_y)):
        if supplied is not None and not isinstance(supplied, bool):
            raise TypeError(f"Painter action {field} must be boolean")
        resolved[field] = supplied
    if dynamics is not None:
        if not isinstance(dynamics, dict):
            raise TypeError("Painter action dynamics must be an object")
        resolved["dynamics"] = dict(dynamics)
    if not resolved_preset and not resolved_style and all(
        resolved[field] is None
        for field in (
            "width", "opacity", "hardness", "spacing", "angle", "roundness",
            "flip_x", "flip_y", "dynamics",
        )
    ):
        raise ValueError("Painter brush set requires at least one authored field")
    return resolved


def validate_view_pan_action(
    *,
    x: object = PAINTER_ACTION_INPUT_UNSET,
    y: object = PAINTER_ACTION_INPUT_UNSET,
    dx: object = PAINTER_ACTION_INPUT_UNSET,
    dy: object = PAINTER_ACTION_INPUT_UNSET,
    reset: object = PAINTER_ACTION_INPUT_UNSET,
) -> tuple[str, int | None, int | None]:
    """Validate one exact QPoint-backed pan operation before owner lookup."""
    resolved_reset = (
        None
        if reset is PAINTER_ACTION_INPUT_UNSET
        else validate_optional_action_boolean(reset, field="reset")
    )
    if reset is not PAINTER_ACTION_INPUT_UNSET and reset is None:
        raise TypeError("Painter action reset must be a boolean")
    resolved_coordinates: dict[str, int | None] = {}
    for field, value in (("x", x), ("y", y), ("dx", dx), ("dy", dy)):
        resolved_coordinates[field] = (
            None
            if value is PAINTER_ACTION_INPUT_UNSET
            else validate_action_integer_domain(
                value,
                field=field,
                minimum=PAINT_ACTION_QPOINT_COORDINATE_MIN,
                maximum=PAINT_ACTION_QPOINT_COORDINATE_MAX,
            )
        )

    has_absolute = x is not PAINTER_ACTION_INPUT_UNSET or y is not PAINTER_ACTION_INPUT_UNSET
    has_relative = dx is not PAINTER_ACTION_INPUT_UNSET or dy is not PAINTER_ACTION_INPUT_UNSET
    if resolved_reset is not None:
        if not resolved_reset or has_absolute or has_relative:
            raise ValueError("Painter pan reset must be the sole operation and true")
        return "reset", None, None
    if has_absolute == has_relative:
        raise ValueError("Painter pan requires exactly one absolute or relative operation")
    if has_absolute:
        return "absolute", resolved_coordinates["x"], resolved_coordinates["y"]
    resolved_dx = resolved_coordinates["dx"]
    resolved_dy = resolved_coordinates["dy"]
    if (resolved_dx or 0) == 0 and (resolved_dy or 0) == 0:
        raise ValueError("Painter relative pan must move by at least one pixel")
    return "relative", resolved_dx, resolved_dy


def validate_view_pan_result_coordinate(value: object, *, field: str) -> int:
    """Reject QPoint addition overflow before a pan mutation is committed."""
    return validate_action_integer_domain(
        value,
        field=field,
        minimum=PAINT_ACTION_QPOINT_COORDINATE_MIN,
        maximum=PAINT_ACTION_QPOINT_COORDINATE_MAX,
    )


def _validate_layer_mask_target(layer_id: object) -> str:
    if not isinstance(layer_id, str):
        raise TypeError("Painter layer mask layer_id must be a string")
    resolved = layer_id.strip()
    if layer_id and not resolved:
        raise ValueError("Painter layer mask layer_id must not be blank")
    return resolved


def validate_layer_mask_state_action(
    *,
    layer_id: object = "",
    enabled: object = PAINTER_ACTION_INPUT_UNSET,
    linked: object = PAINTER_ACTION_INPUT_UNSET,
    delete: object = PAINTER_ACTION_INPUT_UNSET,
) -> tuple[str, bool | None, bool | None, bool]:
    resolved_layer_id = _validate_layer_mask_target(layer_id)
    resolved: dict[str, bool | None] = {}
    for field, value in (("enabled", enabled), ("linked", linked), ("delete", delete)):
        if value is PAINTER_ACTION_INPUT_UNSET:
            resolved[field] = None
        elif not isinstance(value, bool):
            raise TypeError(f"Painter layer mask {field} must be a boolean")
        else:
            resolved[field] = value
    resolved_enabled = resolved["enabled"]
    resolved_linked = resolved["linked"]
    resolved_delete = resolved["delete"]
    if delete is not PAINTER_ACTION_INPUT_UNSET:
        if not resolved_delete or resolved_enabled is not None or resolved_linked is not None:
            raise ValueError("Painter layer mask delete must be the sole state operation and true")
        return resolved_layer_id, None, None, True
    if enabled is PAINTER_ACTION_INPUT_UNSET and linked is PAINTER_ACTION_INPUT_UNSET:
        raise ValueError("Painter layer mask state requires enabled, linked, or delete=true")
    return resolved_layer_id, resolved_enabled, resolved_linked, False


def validate_layer_mask_paint_action(
    *,
    layer_id: object = "",
    x: object,
    y: object,
    radius_px: object,
    value: object,
) -> tuple[str, float, float, float, int]:
    resolved_layer_id = _validate_layer_mask_target(layer_id)
    resolved_x = _strict_normalized_real(x, field="x")
    resolved_y = _strict_normalized_real(y, field="y")
    if isinstance(radius_px, bool) or not isinstance(radius_px, numbers.Real):
        raise TypeError("Painter layer mask radius_px must be a real number, not bool")
    resolved_radius = float(radius_px)
    if not math.isfinite(resolved_radius):
        raise ValueError("Painter layer mask radius_px must be finite")
    if resolved_radius < PAINTER_LAYER_MASK_RADIUS_MIN_PX:
        raise ValueError(
            f"Painter layer mask radius_px must be at least {PAINTER_LAYER_MASK_RADIUS_MIN_PX}"
        )
    resolved_value = validate_action_integer_domain(
        value,
        field="value",
        minimum=PAINTER_LAYER_MASK_ALPHA_MIN,
        maximum=PAINTER_LAYER_MASK_ALPHA_MAX,
    )
    return resolved_layer_id, resolved_x, resolved_y, resolved_radius, resolved_value


def _validate_layer_mask_gradient_point(value: object, *, field: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise TypeError(f"Painter layer mask {field} must be an exact x,y pair")
    return (
        _strict_normalized_real(value[0], field=f"{field}[0]"),
        _strict_normalized_real(value[1], field=f"{field}[1]"),
    )


def validate_layer_mask_gradient_action(
    *,
    layer_id: object = "",
    start: object,
    end: object,
    start_value: object = PAINTER_LAYER_MASK_ALPHA_MIN,
    end_value: object = PAINTER_LAYER_MASK_ALPHA_MAX,
) -> tuple[str, tuple[float, float], tuple[float, float], int, int]:
    resolved_layer_id = _validate_layer_mask_target(layer_id)
    resolved_start = _validate_layer_mask_gradient_point(start, field="start")
    resolved_end = _validate_layer_mask_gradient_point(end, field="end")
    if resolved_start == resolved_end:
        raise ValueError("Painter layer mask gradient requires distinct endpoints")
    resolved_start_value = validate_action_integer_domain(
        start_value,
        field="start_value",
        minimum=PAINTER_LAYER_MASK_ALPHA_MIN,
        maximum=PAINTER_LAYER_MASK_ALPHA_MAX,
    )
    resolved_end_value = validate_action_integer_domain(
        end_value,
        field="end_value",
        minimum=PAINTER_LAYER_MASK_ALPHA_MIN,
        maximum=PAINTER_LAYER_MASK_ALPHA_MAX,
    )
    return (
        resolved_layer_id,
        resolved_start,
        resolved_end,
        resolved_start_value,
        resolved_end_value,
    )


def validate_editor_object_locator_action(
    *,
    object_id: object = "",
    kind: object = "",
    time_ms: object = None,
    include_inactive: object = True,
    output_dir: object = "",
    force: object = False,
) -> dict[str, object]:
    for field, value in (("object_id", object_id), ("kind", kind), ("output_dir", output_dir)):
        if not isinstance(value, str):
            raise TypeError(f"Painter editor object {field} must be a string")
    if not isinstance(include_inactive, bool):
        raise TypeError("Painter editor object include_inactive must be a boolean")
    if not isinstance(force, bool):
        raise TypeError("Painter editor object force must be a boolean")
    resolved_id = object_id.strip()
    resolved_kind = kind.strip()
    if resolved_id and resolved_kind:
        raise ValueError("Painter editor object locator is ambiguous")
    return {
        "object_id": resolved_id,
        "kind": resolved_kind,
        "time_ms": None if time_ms is None else normalize_paint_time_ms(time_ms),
        "include_inactive": include_inactive,
        "output_dir": output_dir,
        "force": force,
    }


def validate_editor_object_import_geometry_action(
    *,
    x_norm: object = None,
    y_norm: object = None,
    width_norm: object = None,
    height_norm: object = None,
) -> dict[str, float | None]:
    resolved: dict[str, float | None] = {
        "x_norm": None, "y_norm": None, "width_norm": None, "height_norm": None,
    }
    for field, value in (
        ("x_norm", x_norm), ("y_norm", y_norm),
        ("width_norm", width_norm), ("height_norm", height_norm),
    ):
        if value is None:
            continue
        number = _strict_finite_real(value, field=field)
        minimum, maximum = (
            (PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM, 1.0)
            if field in {"width_norm", "height_norm"}
            else (0.0, PAINT_ACTION_EDITOR_OBJECT_MAX_POSITION_NORM)
        )
        if not minimum <= number <= maximum:
            raise ValueError(f"Painter editor object {field} must be between {minimum} and {maximum}")
        resolved[field] = number
    for position_field, size_field in (
        ("x_norm", "width_norm"), ("y_norm", "height_norm")
    ):
        position = resolved[position_field]
        size = resolved[size_field]
        if position is not None and size is not None and position + size > 1.0:
            raise ValueError(f"Painter editor object {position_field} plus {size_field} must fit the canvas")
    return resolved

_BLOCKOUT_PRIMITIVE_FIELDS = {
    "primitive_id", "kind", "name", "x", "y", "z", "rx", "ry", "rz",
    "sx", "sy", "sz", "color", "opacity", "wireframe", "locked",
}


def validate_blockout_primitive_action(
    params: object,
    *,
    require_authored_field: bool,
) -> dict[str, object]:
    """Validate primitive edits against the actual Painter transform controls."""

    if not isinstance(params, dict):
        raise TypeError("Painter blockout primitive parameters must be an object")
    unknown = sorted(set(params) - _BLOCKOUT_PRIMITIVE_FIELDS)
    if unknown:
        raise ValueError(f"Unknown Painter blockout primitive fields: {', '.join(unknown)}")
    if require_authored_field and not params:
        raise ValueError("Painter blockout primitive update requires a primitive field")
    resolved: dict[str, object] = {}
    for field, value in params.items():
        if field == "primitive_id":
            if not isinstance(value, str):
                raise TypeError("Painter blockout primitive_id must be a string")
            resolved[field] = value
            continue
        if field == "kind":
            if not isinstance(value, str):
                raise TypeError("Painter blockout primitive kind must be a string")
            kind = value.strip().lower()
            if kind not in SUPPORTED_PRIMITIVES:
                raise ValueError(f"Unsupported Painter blockout primitive kind: {value}")
            resolved[field] = kind
            continue
        if field == "name":
            if not isinstance(value, str):
                raise TypeError("Painter blockout primitive name must be a string")
            resolved[field] = value
            continue
        if field == "color":
            if not isinstance(value, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", value.strip()) is None:
                raise ValueError("Painter blockout primitive color must be #RRGGBB")
            resolved[field] = value.strip().upper()
            continue
        if field in {"wireframe", "locked"}:
            if not isinstance(value, bool):
                raise TypeError(f"Painter blockout primitive {field} must be a boolean")
            resolved[field] = value
            continue
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError(f"Painter blockout primitive {field} must be a real number, not bool")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Painter blockout primitive {field} must be finite")
        if field in {"x", "y", "z"}:
            minimum, maximum = BLOCKOUT_PRIMITIVE_POSITION_MIN, BLOCKOUT_PRIMITIVE_POSITION_MAX
        elif field in {"rx", "ry", "rz"}:
            minimum, maximum = (
                BLOCKOUT_PRIMITIVE_ROTATION_MIN_DEGREES,
                BLOCKOUT_PRIMITIVE_ROTATION_MAX_DEGREES,
            )
        elif field in {"sx", "sy", "sz"}:
            minimum, maximum = BLOCKOUT_PRIMITIVE_SCALE_MIN, BLOCKOUT_PRIMITIVE_SCALE_MAX
        else:
            minimum, maximum = BLOCKOUT_PRIMITIVE_OPACITY_MIN, BLOCKOUT_PRIMITIVE_OPACITY_MAX
        if not minimum <= number <= maximum:
            raise ValueError(
                f"Painter blockout primitive {field} must be between {minimum} and {maximum}"
            )
        resolved[field] = number
    return resolved


def validate_blockout_material_preview_action(
    params: object,
) -> dict[str, bool | float]:
    if not isinstance(params, dict):
        raise TypeError("Painter blockout material preview parameters must be an object")
    allowed = {
        "material_lit", "show_floor", "show_shadows", "show_fog", "show_depth",
        "light_yaw_degrees", "light_pitch_degrees",
    }
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise ValueError(f"Unknown Painter blockout material preview fields: {', '.join(unknown)}")
    if not params:
        raise ValueError("Painter blockout material preview update requires a setting")
    resolved: dict[str, bool | float] = {}
    for field, value in params.items():
        if field.startswith("show_") or field == "material_lit":
            if not isinstance(value, bool):
                raise TypeError(f"Painter blockout material preview {field} must be a boolean")
            resolved[field] = value
            continue
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError(f"Painter blockout material preview {field} must be a real number, not bool")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Painter blockout material preview {field} must be finite")
        minimum, maximum = (
            (BLOCKOUT_LIGHT_YAW_MIN_DEGREES, BLOCKOUT_LIGHT_YAW_MAX_DEGREES)
            if field == "light_yaw_degrees"
            else (BLOCKOUT_LIGHT_PITCH_MIN_DEGREES, BLOCKOUT_LIGHT_PITCH_MAX_DEGREES)
        )
        if not minimum <= number <= maximum:
            raise ValueError(f"Painter blockout material preview {field} must be between {minimum} and {maximum}")
        resolved[field] = number
    return resolved


def validate_blockout_camera_preset_action(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Painter blockout camera preset must be a string")
    preset = value.strip().lower()
    if preset not in BLOCKOUT_CAMERA_PRESETS:
        raise ValueError(f"Unsupported Painter blockout camera preset: {value}")
    return preset


def validate_blockout_duplicate_offset_action(*values: object) -> tuple[float, float, float]:
    resolved: list[float] = []
    for field, value in zip(("offset_x", "offset_y", "offset_z"), values):
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError(f"Painter blockout {field} must be a real number, not bool")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Painter blockout {field} must be finite")
        resolved.append(number)
    return (resolved[0], resolved[1], resolved[2])


def validate_blockout_primitive_id_action(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Painter blockout primitive_id must be a string")
    primitive_id = value.strip()
    if not primitive_id:
        raise ValueError("Painter blockout primitive_id must not be empty")
    return primitive_id


def validate_blockout_snap_action(
    *, enabled: object = None, primitive_id: object = ""
) -> tuple[bool | None, str]:
    if enabled is not None and not isinstance(enabled, bool):
        raise TypeError("Painter blockout snap enabled must be a boolean")
    if not isinstance(primitive_id, str):
        raise TypeError("Painter blockout snap primitive_id must be a string")
    resolved_id = primitive_id.strip()
    if enabled is None and not resolved_id:
        raise ValueError("Painter blockout snap requires enabled or primitive_id")
    return enabled, resolved_id


def validate_blockout_grid_step(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError("Painter blockout grid_size must be a real number, not bool")
    step = float(value)
    if not math.isfinite(step):
        raise ValueError("Painter blockout grid_size must be finite")
    if step < 0.05:
        raise ValueError("Painter blockout grid_size must be at least 0.05")
    return step


def validate_blockout_camera_action(
    params: object,
    *,
    allow_aliases: bool = False,
) -> dict[str, float]:
    if not isinstance(params, dict):
        raise TypeError("Painter blockout camera parameters must be an object")
    allowed = set(_BLOCKOUT_CAMERA_ALIASES)
    if allow_aliases:
        allowed.update(
            alias for aliases in _BLOCKOUT_CAMERA_ALIASES.values() for alias in aliases
        )
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise ValueError(f"Unknown Painter blockout camera fields: {', '.join(unknown)}")
    resolved: dict[str, float] = {}
    for field, aliases in _BLOCKOUT_CAMERA_ALIASES.items():
        candidates = (field, *aliases) if allow_aliases else (field,)
        authored = [candidate for candidate in candidates if candidate in params]
        if len(authored) > 1:
            raise ValueError(f"Painter blockout camera field {field} is ambiguous")
        if not authored:
            continue
        value = params[authored[0]]
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError(f"Painter blockout camera {field} must be a real number, not bool")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Painter blockout camera {field} must be finite")
        if field == "distance" and number < BLOCKOUT_CAMERA_MIN_DISTANCE:
            raise ValueError(
                f"Painter blockout camera distance must be at least {BLOCKOUT_CAMERA_MIN_DISTANCE}"
            )
        if field == "distance" and number > BLOCKOUT_CAMERA_MAX_DISTANCE:
            raise ValueError(f"Painter blockout camera distance must be at most {BLOCKOUT_CAMERA_MAX_DISTANCE}")
        if field == "yaw_degrees" and not (
            BLOCKOUT_CAMERA_YAW_MIN_DEGREES <= number <= BLOCKOUT_CAMERA_YAW_MAX_DEGREES
        ):
            raise ValueError("Painter blockout camera yaw_degrees is outside the product control range")
        if field == "pitch_degrees" and not (
            BLOCKOUT_CAMERA_PITCH_MIN_DEGREES <= number <= BLOCKOUT_CAMERA_PITCH_MAX_DEGREES
        ):
            raise ValueError("Painter blockout camera pitch_degrees is outside the product control range")
        if field in {"target_x", "target_y", "target_z"} and not (
            BLOCKOUT_CAMERA_TARGET_MIN <= number <= BLOCKOUT_CAMERA_TARGET_MAX
        ):
            raise ValueError(f"Painter blockout camera {field} is outside the product pan range")
        if field == "fov_degrees" and not (
            BLOCKOUT_CAMERA_FOV_MIN_DEGREES
            <= number
            <= BLOCKOUT_CAMERA_FOV_MAX_DEGREES
        ):
            raise ValueError(
                "Painter blockout camera fov_degrees must be between "
                f"{BLOCKOUT_CAMERA_FOV_MIN_DEGREES} and "
                f"{BLOCKOUT_CAMERA_FOV_MAX_DEGREES}"
            )
        resolved[field] = number
    if not resolved:
        raise ValueError("Painter blockout camera update requires a camera field")
    return resolved


def validate_blockout_preview_action(
    preview_width: object,
    preview_height: object,
) -> tuple[int, int]:
    """Validate the authored Action response viewport before owner access."""

    return (
        validate_action_integer_domain(
            preview_width,
            field="preview_width",
            minimum=PAINT_ACTION_BLOCKOUT_PREVIEW_MIN_PX,
            maximum=PAINT_ACTION_BLOCKOUT_PREVIEW_MAX_PX,
        ),
        validate_action_integer_domain(
            preview_height,
            field="preview_height",
            minimum=PAINT_ACTION_BLOCKOUT_PREVIEW_MIN_PX,
            maximum=PAINT_ACTION_BLOCKOUT_PREVIEW_MAX_PX,
        ),
    )


def validate_material_preview_action(
    *,
    enabled: object = None,
    azimuth_deg: object = None,
    elevation_deg: object = None,
    require_authored_field: bool = False,
) -> dict[str, bool | float | None]:
    resolved_enabled = validate_optional_action_boolean(enabled, field="enabled")
    resolved: dict[str, bool | float | None] = {
        "enabled": resolved_enabled,
        "azimuth_deg": None,
        "elevation_deg": None,
    }
    for field, value, minimum, maximum in (
        (
            "azimuth_deg",
            azimuth_deg,
            MATERIAL_PREVIEW_AZIMUTH_MIN_DEGREES,
            MATERIAL_PREVIEW_AZIMUTH_MAX_DEGREES,
        ),
        (
            "elevation_deg",
            elevation_deg,
            MATERIAL_PREVIEW_ELEVATION_MIN_DEGREES,
            MATERIAL_PREVIEW_ELEVATION_MAX_DEGREES,
        ),
    ):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError(f"Painter action {field} must be a real number, not bool")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Painter action {field} must be finite")
        if not minimum <= number <= maximum:
            raise ValueError(
                f"Painter action {field} must be between {minimum} and {maximum}"
            )
        resolved[field] = number
    if require_authored_field and not any(value is not None for value in resolved.values()):
        raise ValueError("Material preview update must include a setting")
    return resolved


def validate_reference_sample_action(
    *,
    reference_id: object,
    x_norm: object,
    y_norm: object,
    apply: object,
) -> tuple[str, float, float, bool]:
    if not isinstance(reference_id, str):
        raise TypeError("Painter action reference_id must be a string")
    if not isinstance(apply, bool):
        raise TypeError("Painter action apply must be a boolean")
    return (
        reference_id,
        _strict_normalized_real(x_norm, field="x_norm"),
        _strict_normalized_real(y_norm, field="y_norm"),
        apply,
    )


def validate_reference_palette_action(
    *,
    reference_id: object,
    max_colors: object,
    apply: object,
) -> tuple[str, int, bool]:
    if not isinstance(reference_id, str):
        raise TypeError("Painter action reference_id must be a string")
    if not isinstance(apply, bool):
        raise TypeError("Painter action apply must be a boolean")
    return (
        reference_id,
        validate_action_integer_domain(
            max_colors,
            field="max_colors",
            minimum=1,
            maximum=PAINT_ACTION_MAX_REFERENCE_COLORS,
        ),
        apply,
    )


def _strict_reference_text(value: object, *, field: str, allow_empty: bool) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Painter reference {field} must be a string")
    resolved = value.strip()
    if field == "reference_id" and value and not resolved:
        raise ValueError("Painter reference reference_id must not be blank")
    if not allow_empty and not resolved:
        raise ValueError(f"Painter reference {field} must not be blank")
    if field == "name" and len(resolved) > REFERENCE_NAME_MAX_CHARACTERS:
        raise ValueError(
            f"Painter reference name exceeds {REFERENCE_NAME_MAX_CHARACTERS} characters"
        )
    return resolved


def _strict_reference_real(
    value: object,
    *,
    field: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"Painter reference {field} must be a real number, not bool")
    resolved = float(value)
    if not math.isfinite(resolved):
        raise ValueError(f"Painter reference {field} must be finite")
    if minimum is not None and resolved < minimum:
        raise ValueError(f"Painter reference {field} is below {minimum}")
    if maximum is not None and resolved > maximum:
        raise ValueError(f"Painter reference {field} exceeds {maximum}")
    return resolved


def validate_reference_add_action(
    *,
    path: object,
    name: object = "",
    x_norm: object = REFERENCE_DEFAULT_X_NORM,
    y_norm: object = REFERENCE_DEFAULT_Y_NORM,
    width_norm: object = REFERENCE_DEFAULT_WIDTH_NORM,
    height_norm: object = REFERENCE_DEFAULT_HEIGHT_NORM,
    opacity: object = REFERENCE_DEFAULT_OPACITY,
    rotation_deg: object = REFERENCE_DEFAULT_ROTATION_DEGREES,
    visible: object = True,
    locked: object = False,
) -> dict[str, object]:
    if not isinstance(visible, bool) or not isinstance(locked, bool):
        raise TypeError("Painter reference visible and locked must be booleans")
    return {
        "path": _strict_reference_text(path, field="path", allow_empty=False),
        "name": _strict_reference_text(name, field="name", allow_empty=True),
        "x_norm": _strict_reference_real(x_norm, field="x_norm", minimum=REFERENCE_POSITION_MIN_NORM, maximum=REFERENCE_POSITION_MAX_NORM),
        "y_norm": _strict_reference_real(y_norm, field="y_norm", minimum=REFERENCE_POSITION_MIN_NORM, maximum=REFERENCE_POSITION_MAX_NORM),
        "width_norm": _strict_reference_real(width_norm, field="width_norm", minimum=REFERENCE_SIZE_MIN_NORM, maximum=REFERENCE_SIZE_MAX_NORM),
        "height_norm": _strict_reference_real(height_norm, field="height_norm", minimum=REFERENCE_SIZE_MIN_NORM, maximum=REFERENCE_SIZE_MAX_NORM),
        "opacity": _strict_reference_real(opacity, field="opacity", minimum=REFERENCE_OPACITY_MIN, maximum=REFERENCE_OPACITY_MAX),
        "rotation_deg": _strict_reference_real(rotation_deg, field="rotation_deg", minimum=REFERENCE_ROTATION_MIN_DEGREES, maximum=REFERENCE_ROTATION_MAX_DEGREES),
        "visible": visible,
        "locked": locked,
    }


def validate_reference_update_action(
    *,
    reference_id: object = PAINTER_ACTION_INPUT_UNSET,
    name: object = PAINTER_ACTION_INPUT_UNSET,
    x_norm: object = PAINTER_ACTION_INPUT_UNSET,
    y_norm: object = PAINTER_ACTION_INPUT_UNSET,
    width_norm: object = PAINTER_ACTION_INPUT_UNSET,
    height_norm: object = PAINTER_ACTION_INPUT_UNSET,
    opacity: object = PAINTER_ACTION_INPUT_UNSET,
    rotation_deg: object = PAINTER_ACTION_INPUT_UNSET,
    visible: object = PAINTER_ACTION_INPUT_UNSET,
    locked: object = PAINTER_ACTION_INPUT_UNSET,
) -> tuple[str, dict[str, object]]:
    if reference_id is PAINTER_ACTION_INPUT_UNSET:
        raise ValueError("Painter reference update requires reference_id")
    resolved_id = _strict_reference_text(reference_id, field="reference_id", allow_empty=False)
    supplied = {
        "name": name,
        "x_norm": x_norm,
        "y_norm": y_norm,
        "width_norm": width_norm,
        "height_norm": height_norm,
        "opacity": opacity,
        "rotation_deg": rotation_deg,
        "visible": visible,
        "locked": locked,
    }
    if all(value is PAINTER_ACTION_INPUT_UNSET for value in supplied.values()):
        raise ValueError("Painter reference update requires at least one authored field")
    resolved: dict[str, object] = {}
    for field, value in supplied.items():
        if value is PAINTER_ACTION_INPUT_UNSET:
            continue
        if field == "name":
            resolved[field] = _strict_reference_text(value, field=field, allow_empty=True)
        elif field in {"visible", "locked"}:
            if not isinstance(value, bool):
                raise TypeError(f"Painter reference {field} must be a boolean")
            resolved[field] = value
        else:
            domains = {
                "x_norm": (REFERENCE_POSITION_MIN_NORM, REFERENCE_POSITION_MAX_NORM),
                "y_norm": (REFERENCE_POSITION_MIN_NORM, REFERENCE_POSITION_MAX_NORM),
                "width_norm": (REFERENCE_SIZE_MIN_NORM, REFERENCE_SIZE_MAX_NORM),
                "height_norm": (REFERENCE_SIZE_MIN_NORM, REFERENCE_SIZE_MAX_NORM),
                "opacity": (REFERENCE_OPACITY_MIN, REFERENCE_OPACITY_MAX),
                "rotation_deg": (REFERENCE_ROTATION_MIN_DEGREES, REFERENCE_ROTATION_MAX_DEGREES),
            }
            minimum, maximum = domains[field]
            resolved[field] = _strict_reference_real(
                value, field=field, minimum=minimum, maximum=maximum
            )
    return resolved_id, resolved


def validate_reference_id_action(reference_id: object, *, allow_empty: bool = True) -> str:
    if reference_id is PAINTER_ACTION_INPUT_UNSET:
        raise ValueError("Painter reference operation requires reference_id")
    return _strict_reference_text(
        reference_id, field="reference_id", allow_empty=allow_empty
    )


def validate_reference_duplicate_action(
    *,
    reference_id: object = PAINTER_ACTION_INPUT_UNSET,
    offset_x: object = REFERENCE_DUPLICATE_OFFSET_NORM,
    offset_y: object = REFERENCE_DUPLICATE_OFFSET_NORM,
) -> tuple[str, float, float]:
    return (
        validate_reference_id_action(reference_id, allow_empty=False),
        _strict_reference_real(offset_x, field="offset_x"),
        _strict_reference_real(offset_y, field="offset_y"),
    )


def validate_path_id_action(path_id: object) -> str:
    if not isinstance(path_id, str):
        raise TypeError("Painter path_id must be a string")
    if path_id and not path_id.strip():
        raise ValueError("Painter path_id must not be whitespace-only")
    return path_id.strip()


def _strict_path_point(point: object, *, index: int) -> tuple[float, float]:
    if isinstance(point, dict):
        keys = set(point)
        if keys == {"x", "y"}:
            raw_x, raw_y = point["x"], point["y"]
        elif keys == {"x_norm", "y_norm"}:
            raw_x, raw_y = point["x_norm"], point["y_norm"]
        else:
            raise ValueError(
                f"Painter path point {index} must contain exactly one coordinate pair"
            )
    elif isinstance(point, (list, tuple)):
        if len(point) != PAINT_ACTION_PATH_MIN_POINTS:
            raise ValueError(f"Painter path point {index} must contain exactly two values")
        raw_x, raw_y = point
    else:
        raise TypeError(f"Painter path point {index} must be an object or pair")
    return (
        _strict_normalized_real(raw_x, field=f"points[{index}].x"),
        _strict_normalized_real(raw_y, field=f"points[{index}].y"),
    )


def validate_path_create_action(
    *,
    points: object,
    closed: object,
    make_selection: object,
) -> tuple[list[tuple[float, float]], bool, bool]:
    if not isinstance(points, list):
        raise TypeError("Painter path points must be an array")
    if not PAINT_ACTION_PATH_MIN_POINTS <= len(points) <= PAINT_ACTION_MAX_POINTS_PER_STROKE:
        raise ValueError(
            "Painter path point count must fit the single-stroke Action resource contract"
        )
    if not isinstance(closed, bool) or not isinstance(make_selection, bool):
        raise TypeError("Painter path closed and make_selection must be booleans")
    if make_selection and len(points) < PAINT_ACTION_PATH_SELECTION_MIN_POINTS:
        raise ValueError("Painter path selection requires at least three points")
    return (
        [_strict_path_point(point, index=index) for index, point in enumerate(points)],
        closed,
        make_selection,
    )


def _strict_path_pair(
    value: object,
    *,
    field: str,
    normalized: bool,
) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != PAINT_ACTION_PATH_MIN_POINTS:
        raise ValueError(f"Painter path {field} must contain exactly two values")
    validator = _strict_normalized_real if normalized else _strict_finite_real
    first, second = value
    return (
        validator(first, field=f"{field}.x"),
        validator(second, field=f"{field}.y"),
    )


def validate_path_anchor_action(
    *,
    path_id: object,
    index: object,
    operation: object,
    point: object,
    in_handle: object,
    out_handle: object,
) -> tuple[str, int, str, tuple[float, float] | None, tuple[float, float] | None, tuple[float, float] | None]:
    resolved_id = validate_path_id_action(path_id)
    resolved_index = _strict_integer(index, field="index")
    if resolved_index < PAINT_ACTION_PATH_INDEX_MIN:
        raise ValueError("Painter path anchor index must be nonnegative")
    resolved_operation = _strict_selection_string(
        operation,
        field="operation",
        allowed=("add", "delete", "move", "corner", "smooth"),
    )
    if resolved_operation in {"add", "move"} and point is None:
        raise ValueError(f"Painter path anchor {resolved_operation} requires point")
    if resolved_operation in {"add", "delete"} and (
        in_handle is not None or out_handle is not None
    ):
        raise ValueError(
            f"Painter path anchor {resolved_operation} does not accept handles"
        )
    if resolved_operation == "delete" and point is not None:
        raise ValueError("Painter path anchor delete does not accept point")
    if resolved_operation == "corner" and (
        in_handle is not None or out_handle is not None
    ):
        raise ValueError("Painter path anchor corner does not accept handles")
    return (
        resolved_id,
        resolved_index,
        resolved_operation,
        None if point is None else _strict_path_pair(point, field="point", normalized=True),
        None if in_handle is None else _strict_path_pair(in_handle, field="in_handle", normalized=False),
        None if out_handle is None else _strict_path_pair(out_handle, field="out_handle", normalized=False),
    )


def validate_path_name_action(name: object) -> str:
    if not isinstance(name, str):
        raise TypeError("Painter path name must be a string")
    resolved = name.strip()
    if not resolved:
        raise ValueError("Painter path name must not be empty")
    return resolved


def validate_path_reorder_action(index: object) -> int:
    resolved = _strict_integer(index, field="index")
    if resolved < PAINT_ACTION_PATH_INDEX_MIN:
        raise ValueError("Painter path reorder index must be nonnegative")
    return resolved


def validate_optional_path_color_action(color: object) -> str:
    if not isinstance(color, str):
        raise TypeError("Painter path color must be a string")
    resolved = color.strip()
    if color and not resolved:
        raise ValueError("Painter path color must not be whitespace-only")
    if not resolved:
        return ""
    from PySide6.QtGui import QColor

    if not QColor(resolved).isValid():
        raise ValueError("Painter path color must be a valid Qt color")
    return resolved


def validate_path_stroke_action(
    *,
    color: object,
    width_px: object,
) -> tuple[str, float | None]:
    resolved_color = validate_optional_path_color_action(color)
    if width_px is None:
        return resolved_color, None
    resolved_width = _strict_finite_real(width_px, field="width_px")
    if not PAINT_ACTION_STROKE_MIN_WIDTH_PX <= resolved_width <= PAINT_ACTION_MAX_BRUSH_WIDTH_PX:
        raise ValueError("Painter path stroke width is outside the Action brush-width domain")
    return resolved_color, resolved_width


def normalize_paint_time_ms(value: object) -> int:
    milliseconds = _strict_integer(value, field="time_ms")
    if milliseconds < 0:
        raise ValueError("Painter action time_ms must be nonnegative")
    return milliseconds


def optional_paint_export_size(
    width: object,
    height: object,
) -> tuple[int, int] | None:
    resolved_width = _strict_integer(width, field="width")
    resolved_height = _strict_integer(height, field="height")
    if resolved_width == 0 and resolved_height == 0:
        return None
    if resolved_width <= 0 or resolved_height <= 0:
        raise ValueError(
            "Painter export width and height must both be positive or both be zero"
        )
    if (
        resolved_width > PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT
        or resolved_height > PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT
    ):
        raise ValueError(
            "Painter export dimensions exceed the current canvas capacity"
        )
    return resolved_width, resolved_height


def _strict_integer(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"Painter action {field} must be an integer, not bool")
    try:
        return operator.index(value)
    except TypeError as exc:
        raise TypeError(f"Painter action {field} must be an integer") from exc


def validate_action_integer_domain(
    value: object,
    *,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    integer = _strict_integer(value, field=field)
    if not minimum <= integer <= maximum:
        raise ValueError(
            f"Painter action {field} must be between {minimum} and {maximum}"
        )
    return integer


def validate_optional_action_boolean(
    value: object,
    *,
    field: str,
) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise TypeError(f"Painter action {field} must be a boolean")
    return value


def validate_pressure_calibration_action(
    *,
    device_id: object,
    minimum: object,
    maximum: object,
    curve: object,
) -> tuple[str, float, float, list[list[float]] | None]:
    if not isinstance(device_id, str):
        raise TypeError("Painter action device_id must be a string")
    resolved_device_id = device_id.strip()
    if not resolved_device_id:
        raise ValueError("Painter action device_id must not be empty")
    resolved_minimum = _strict_normalized_real(minimum, field="minimum")
    resolved_maximum = _strict_normalized_real(maximum, field="maximum")
    if resolved_minimum >= resolved_maximum:
        raise ValueError("Painter action minimum must be less than maximum")
    if curve is None:
        return resolved_device_id, resolved_minimum, resolved_maximum, None
    if not isinstance(curve, list):
        raise TypeError("Painter action curve must be an array")
    resolved_curve: list[list[float]] = []
    previous_x: float | None = None
    for index, row in enumerate(curve):
        if not isinstance(row, list) or len(row) != 2:
            raise TypeError(
                f"Painter action curve[{index}] must contain exactly two numbers"
            )
        x = _strict_normalized_real(row[0], field=f"curve[{index}][0]")
        y = _strict_normalized_real(row[1], field=f"curve[{index}][1]")
        if previous_x is not None and x <= previous_x:
            raise ValueError("Painter action curve x values must be strictly increasing")
        resolved_curve.append([x, y])
        previous_x = x
    return resolved_device_id, resolved_minimum, resolved_maximum, resolved_curve


def _strict_normalized_real(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"Painter action {field} must be a real number, not bool")
    resolved = float(value)
    if not math.isfinite(resolved):
        raise ValueError(f"Painter action {field} must be finite")
    if not 0.0 <= resolved <= 1.0:
        raise ValueError(f"Painter action {field} must be between 0 and 1")
    return resolved


def validate_selection_bounds_action(
    *,
    x1: object,
    y1: object,
    x2: object,
    y2: object,
    aspect: object,
    mode: object,
) -> tuple[float, float, float, float, str, str]:
    return (
        _strict_normalized_real(x1, field="x1"),
        _strict_normalized_real(y1, field="y1"),
        _strict_normalized_real(x2, field="x2"),
        _strict_normalized_real(y2, field="y2"),
        _strict_selection_string(
            aspect,
            field="aspect",
            allowed=PAINTER_SELECTION_ASPECTS,
        ),
        _strict_selection_string(
            mode,
            field="mode",
            allowed=PAINTER_SELECTION_MODES,
        ),
    )


def validate_selection_lasso_action(
    *,
    points: object,
    mode: object,
    polygonal: object,
) -> tuple[list[list[float]], str, bool]:
    if not isinstance(points, list):
        raise TypeError("Painter action points must be an array")
    if len(points) < 3:
        raise ValueError("Painter action lasso requires at least three points")
    resolved_points: list[list[float]] = []
    for index, row in enumerate(points):
        if not isinstance(row, list) or len(row) != 2:
            raise TypeError(
                f"Painter action points[{index}] must contain exactly two numbers"
            )
        resolved_points.append(
            [
                _strict_normalized_real(row[0], field=f"points[{index}][0]"),
                _strict_normalized_real(row[1], field=f"points[{index}][1]"),
            ]
        )
    resolved_mode = _strict_selection_string(
        mode,
        field="mode",
        allowed=PAINTER_SELECTION_MODES,
    )
    if not isinstance(polygonal, bool):
        raise TypeError("Painter action polygonal must be a boolean")
    return resolved_points, resolved_mode, polygonal


def _strict_selection_string(
    value: object,
    *,
    field: str,
    allowed: tuple[str, ...],
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Painter action {field} must be a string")
    if value not in allowed:
        raise ValueError(f"Painter action {field} is not supported: {value}")
    return value


def validate_selection_aspect_action(aspect: object) -> str:
    return _strict_selection_string(
        aspect,
        field="aspect",
        allowed=PAINTER_SELECTION_ASPECTS,
    )


def validate_selection_mode_action(mode: object) -> str:
    return _strict_selection_string(
        mode,
        field="mode",
        allowed=PAINTER_SELECTION_MODES,
    )


def validate_crop_preview_action(
    *,
    x1: object = PAINTER_ACTION_INPUT_UNSET,
    y1: object = PAINTER_ACTION_INPUT_UNSET,
    x2: object = PAINTER_ACTION_INPUT_UNSET,
    y2: object = PAINTER_ACTION_INPUT_UNSET,
    straighten_degrees: object,
) -> tuple[tuple[float, float, float, float] | None, float]:
    coordinates = (x1, y1, x2, y2)
    authored = tuple(value is not PAINTER_ACTION_INPUT_UNSET for value in coordinates)
    if any(authored) and not all(authored):
        raise ValueError("Painter crop bounds require x1, y1, x2, and y2 together")
    bounds = None
    if all(authored):
        left = _strict_normalized_real(x1, field="x1")
        top = _strict_normalized_real(y1, field="y1")
        right = _strict_normalized_real(x2, field="x2")
        bottom = _strict_normalized_real(y2, field="y2")
        if left >= right or top >= bottom:
            raise ValueError("Painter crop bounds must have positive width and height")
        bounds = (left, top, right, bottom)
    angle = _strict_finite_real(straighten_degrees, field="straighten_degrees")
    return bounds, angle


def validate_canvas_flip_action(axis: object) -> str:
    return _strict_selection_string(
        axis,
        field="axis",
        allowed=PAINTER_CANVAS_FLIP_AXES,
    )


def validate_fill_color_action(color: object, *, field: str) -> str:
    if not isinstance(color, str):
        raise TypeError(f"Painter action {field} must be a string")
    resolved = color.strip()
    if not resolved:
        raise ValueError(f"Painter action {field} must not be empty")
    from PySide6.QtGui import QColor

    if not QColor(resolved).isValid():
        raise ValueError(f"Painter action {field} must be a valid Qt color")
    return resolved


def validate_fill_color_pair_action(
    *,
    color1: object,
    color2: object,
) -> tuple[str, str]:
    return (
        validate_fill_color_action(color1, field="color1"),
        validate_fill_color_action(color2, field="color2"),
    )


def validate_mirror_action(
    *,
    x: object = PAINTER_ACTION_INPUT_UNSET,
    y: object = PAINTER_ACTION_INPUT_UNSET,
) -> tuple[bool | None, bool | None]:
    if x is PAINTER_ACTION_INPUT_UNSET and y is PAINTER_ACTION_INPUT_UNSET:
        raise ValueError("Painter mirror action requires x and/or y")
    resolved: list[bool | None] = []
    for field, value in (("x", x), ("y", y)):
        if value is PAINTER_ACTION_INPUT_UNSET:
            resolved.append(None)
        elif not isinstance(value, bool):
            raise TypeError(f"Painter action mirror {field} must be a boolean")
        else:
            resolved.append(value)
    return resolved[0], resolved[1]


def validate_layer_mask_source_action(
    *,
    layer_id: object,
    mask_type: object,
) -> tuple[str, str]:
    return (
        validate_optional_layer_id_action(layer_id),
        _strict_selection_string(
            mask_type,
            field="mask_type",
            allowed=PAINTER_LAYER_MASK_SOURCE_TYPES,
        ),
    )


def validate_color_selection_action(
    *,
    x: object,
    y: object,
    tolerance: object,
    contiguous: object,
    phase: object,
) -> tuple[float, float, int | None, bool, str]:
    from app.painter_selection_mask import (
        PAINTER_COLOR_SELECTION_TOLERANCE_MAX,
        PAINTER_COLOR_SELECTION_TOLERANCE_MIN,
    )

    resolved_tolerance = (
        None
        if tolerance is None
        else validate_action_integer_domain(
            tolerance,
            field="tolerance",
            minimum=PAINTER_COLOR_SELECTION_TOLERANCE_MIN,
            maximum=PAINTER_COLOR_SELECTION_TOLERANCE_MAX,
        )
    )
    if not isinstance(contiguous, bool):
        raise TypeError("Painter action contiguous must be a boolean")
    return (
        _strict_normalized_real(x, field="x"),
        _strict_normalized_real(y, field="y"),
        resolved_tolerance,
        contiguous,
        _strict_selection_string(
            phase,
            field="phase",
            allowed=PAINTER_COLOR_SELECTION_PHASES,
        ),
    )


def validate_zoom_area_action(
    *,
    x: object,
    y: object,
    width: object,
    height: object,
) -> tuple[float, float, float, float]:
    resolved_x = _strict_normalized_real(x, field="x")
    resolved_y = _strict_normalized_real(y, field="y")
    resolved_width = _strict_positive_unit_real(width, field="width")
    resolved_height = _strict_positive_unit_real(height, field="height")
    if resolved_x + resolved_width > 1.0:
        raise ValueError("Painter action zoom area exceeds normalized canvas width")
    if resolved_y + resolved_height > 1.0:
        raise ValueError("Painter action zoom area exceeds normalized canvas height")
    return resolved_x, resolved_y, resolved_width, resolved_height


def _strict_positive_unit_real(value: object, *, field: str) -> float:
    resolved = _strict_normalized_real(value, field=field)
    if resolved == 0.0:
        raise ValueError(f"Painter action {field} must be positive")
    return resolved


def validate_layer_opacity_action(opacity: object) -> int:
    return validate_action_integer_domain(
        opacity,
        field="opacity",
        minimum=PAINTER_LAYER_OPACITY_MIN_PERCENT,
        maximum=PAINTER_LAYER_OPACITY_MAX_PERCENT,
    )


def validate_optional_layer_id_action(layer_id: object) -> str:
    if not isinstance(layer_id, str):
        raise TypeError("Painter action layer_id must be a string")
    if layer_id and not layer_id.strip():
        raise ValueError("Painter action layer_id must not be whitespace-only")
    return layer_id.strip()


def validate_required_layer_id_action(layer_id: object) -> str:
    resolved = validate_optional_layer_id_action(layer_id)
    if not resolved:
        raise ValueError("Painter action requires a nonblank layer_id")
    return resolved


def validate_layer_name_action(name: object, *, allow_empty: bool) -> str:
    if not isinstance(name, str):
        raise TypeError("Painter layer name must be a string")
    resolved = name.strip()
    if not allow_empty and not resolved:
        raise ValueError("Painter layer name must not be empty")
    if len(resolved) > PAINTER_LAYER_NAME_MAX_CHARACTERS:
        raise ValueError("Painter layer name exceeds the serialized model capacity")
    return resolved


def validate_layer_type_action(layer_type: object) -> str:
    return _strict_selection_string(
        layer_type,
        field="layer_type",
        allowed=PAINTER_LAYER_TYPES,
    )


def validate_layer_boolean_action(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"Painter layer {field} must be a boolean")
    return value


def validate_layer_ids_action(layer_ids: object) -> list[str]:
    if layer_ids is None:
        return []
    if not isinstance(layer_ids, list):
        raise TypeError("Painter layer_ids must be an array")
    resolved = [validate_required_layer_id_action(value) for value in layer_ids]
    if len(set(resolved)) != len(resolved):
        raise ValueError("Painter layer_ids must not contain duplicates")
    return resolved


def validate_layer_locks_action(
    *,
    pixels: object = PAINTER_ACTION_INPUT_UNSET,
    transparency: object = PAINTER_ACTION_INPUT_UNSET,
    position: object = PAINTER_ACTION_INPUT_UNSET,
    all_locked: object = PAINTER_ACTION_INPUT_UNSET,
) -> dict[str, bool]:
    supplied = {
        key: value
        for key, value in {
            "pixels": pixels,
            "transparency": transparency,
            "position": position,
            "all_locked": all_locked,
        }.items()
        if value is not PAINTER_ACTION_INPUT_UNSET
    }
    if not supplied:
        raise ValueError("Painter layer locks require at least one authored field")
    return {
        key: validate_layer_boolean_action(value, field=key)
        for key, value in supplied.items()
    }


def validate_layer_blend_mode_action(blend_mode: object) -> str:
    return _strict_selection_string(
        blend_mode,
        field="blend_mode",
        allowed=tuple(BLEND_MODES),
    )


def validate_layer_color_label_action(color_label: object) -> str:
    return _strict_selection_string(
        color_label,
        field="color_label",
        allowed=PAINTER_LAYER_COLOR_LABEL_IDS,
    )


def validate_painter_channel_action(channel: object, *, allow_empty: bool) -> str:
    if not isinstance(channel, str):
        raise TypeError("Painter channel must be a string")
    if not channel:
        if allow_empty:
            return ""
        raise ValueError("Painter channel must not be empty")
    if not channel.strip():
        raise ValueError("Painter channel must not be whitespace-only")
    return _strict_selection_string(
        channel,
        field="channel",
        allowed=PAINTER_CHANNEL_IDS,
    )


def validate_selection_modify_action(
    *,
    operation: object,
    radius_px: object,
) -> tuple[str, float | int]:
    resolved_operation = _strict_selection_string(
        operation,
        field="operation",
        allowed=PAINTER_SELECTION_MODIFY_OPERATIONS,
    )
    if resolved_operation == "feather":
        if isinstance(radius_px, bool) or not isinstance(radius_px, numbers.Real):
            raise TypeError("Painter action radius_px must be a real number, not bool")
        resolved_radius = float(radius_px)
        if not math.isfinite(resolved_radius):
            raise ValueError("Painter action radius_px must be finite")
        if not 0.0 < resolved_radius <= PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT:
            raise ValueError(
                "Painter action radius_px must be positive and within canvas capacity"
            )
        return resolved_operation, resolved_radius
    resolved_radius = validate_action_integer_domain(
        radius_px,
        field="radius_px",
        minimum=1,
        maximum=PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT,
    )
    return resolved_operation, resolved_radius


def validate_selection_transform_action(
    *,
    translate_x: object,
    translate_y: object,
    scale_x: object,
    scale_y: object,
    rotation_degrees: object,
    skew_x_degrees: object,
    skew_y_degrees: object,
    pivot_x: object,
    pivot_y: object,
    flip_x: object,
    flip_y: object,
    phase: object,
    target: object,
) -> tuple[dict[str, float | bool], str, str]:
    resolved_scale_x = _strict_finite_real(scale_x, field="scale_x")
    resolved_scale_y = _strict_finite_real(scale_y, field="scale_y")
    if resolved_scale_x == 0.0 or resolved_scale_y == 0.0:
        raise ValueError("Painter action transform scale cannot be zero")
    resolved_skew_x = _strict_finite_real(skew_x_degrees, field="skew_x_degrees")
    resolved_skew_y = _strict_finite_real(skew_y_degrees, field="skew_y_degrees")
    for field, value in (
        ("skew_x_degrees", resolved_skew_x),
        ("skew_y_degrees", resolved_skew_y),
    ):
        if not PAINTER_SELECTION_SKEW_MIN_DEGREES < value < PAINTER_SELECTION_SKEW_MAX_DEGREES:
            raise ValueError(f"Painter action {field} must be strictly between -90 and 90")
    if not isinstance(flip_x, bool) or not isinstance(flip_y, bool):
        raise TypeError("Painter action transform flips must be booleans")
    settings: dict[str, float | bool] = {
        "translate_x": _strict_finite_real(translate_x, field="translate_x"),
        "translate_y": _strict_finite_real(translate_y, field="translate_y"),
        "scale_x": resolved_scale_x,
        "scale_y": resolved_scale_y,
        "rotation_degrees": _strict_finite_real(
            rotation_degrees, field="rotation_degrees"
        ),
        "skew_x_degrees": resolved_skew_x,
        "skew_y_degrees": resolved_skew_y,
        "pivot_x": _strict_normalized_real(pivot_x, field="pivot_x"),
        "pivot_y": _strict_normalized_real(pivot_y, field="pivot_y"),
        "flip_x": flip_x,
        "flip_y": flip_y,
    }
    return (
        settings,
        _strict_selection_string(
            phase, field="phase", allowed=PAINTER_SELECTION_TRANSFORM_PHASES
        ),
        _strict_selection_string(
            target, field="target", allowed=PAINTER_SELECTION_TRANSFORM_TARGETS
        ),
    )


def validate_document_export_action(
    *,
    path: object,
    format_name: object,
    include_background: object,
    bit_depth: object,
    bake_unsupported: object,
    quality: object,
    source_icc: object,
    output_icc: object,
    rendering_intent: object,
) -> dict[str, object]:
    if not isinstance(path, str):
        raise TypeError("Painter action export path must be a string")
    if not path.strip():
        raise ValueError("Painter action export path must not be empty")
    resolved_format = _strict_selection_string(
        format_name,
        field="format",
        allowed=PAINTER_DOCUMENT_EXPORT_FORMATS,
    )
    resolved_bit_depth = _strict_integer(bit_depth, field="bit_depth")
    if resolved_bit_depth not in PAINTER_DOCUMENT_EXPORT_BIT_DEPTHS:
        raise ValueError("Painter action bit_depth must be 8 or 16")
    if resolved_bit_depth == 16 and resolved_format not in {"png", "tiff"}:
        raise ValueError(
            f"Painter action {resolved_format} export does not support 16-bit output"
        )
    if not isinstance(include_background, bool):
        raise TypeError("Painter action include_background must be a boolean")
    if not isinstance(bake_unsupported, bool):
        raise TypeError("Painter action bake_unsupported must be a boolean")
    resolved_quality = validate_action_integer_domain(
        quality,
        field="quality",
        minimum=PAINTER_DOCUMENT_EXPORT_QUALITY_MIN,
        maximum=PAINTER_DOCUMENT_EXPORT_QUALITY_MAX,
    )
    if not isinstance(source_icc, str) or not isinstance(output_icc, str):
        raise TypeError("Painter action ICC paths must be strings")
    resolved_intent = validate_action_integer_domain(
        rendering_intent,
        field="rendering_intent",
        minimum=PAINTER_DOCUMENT_RENDERING_INTENT_MIN,
        maximum=PAINTER_DOCUMENT_RENDERING_INTENT_MAX,
    )
    return {
        "path": path,
        "format_name": resolved_format,
        "include_background": include_background,
        "bit_depth": resolved_bit_depth,
        "bake_unsupported": bake_unsupported,
        "quality": resolved_quality,
        "source_icc": source_icc or None,
        "output_icc": output_icc or None,
        "rendering_intent": resolved_intent,
    }


def validate_perspective_guide_action(
    *,
    enabled: object,
    horizon: object,
    left_x: object,
    left_y: object,
    right_x: object,
    right_y: object,
    center_x: object,
    center_y: object,
    vertical_x: object,
    vertical_y: object,
    mode: object,
    snap: object,
) -> dict[str, object]:
    resolved: dict[str, object] = {
        "enabled": validate_optional_action_boolean(enabled, field="enabled"),
        "snap": validate_optional_action_boolean(snap, field="snap"),
        "mode": (
            None
            if mode is None
            else validate_action_integer_domain(
                mode,
                field="mode",
                minimum=PAINTER_PERSPECTIVE_MODE_MIN,
                maximum=PAINTER_PERSPECTIVE_MODE_MAX,
            )
        ),
        "horizon": (
            None
            if horizon is None
            else _strict_normalized_real(horizon, field="horizon")
        ),
    }
    for field, value in (
        ("left_x", left_x),
        ("left_y", left_y),
        ("right_x", right_x),
        ("right_y", right_y),
        ("center_x", center_x),
        ("center_y", center_y),
        ("vertical_x", vertical_x),
        ("vertical_y", vertical_y),
    ):
        resolved[field] = (
            None if value is None else _strict_finite_real(value, field=field)
        )
    return resolved


def validate_symmetry_guide_action(
    *,
    enabled: object,
    axis: object,
    position: object,
) -> tuple[bool | None, str | None, float | None]:
    return (
        validate_optional_action_boolean(enabled, field="enabled"),
        None
        if axis is None
        else _strict_selection_string(
            axis,
            field="axis",
            allowed=PAINTER_SYMMETRY_AXES,
        ),
        None
        if position is None
        else _strict_normalized_real(position, field="position"),
    )


def _strict_finite_real(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"Painter action {field} must be a real number, not bool")
    resolved = float(value)
    if not math.isfinite(resolved):
        raise ValueError(f"Painter action {field} must be finite")
    return resolved
