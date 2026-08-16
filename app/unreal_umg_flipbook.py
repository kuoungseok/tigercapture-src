"""Provider-neutral flipbook-atlas records for Tiger Studio UMG.

The contract deliberately describes only a bounded atlas frame selector.  It
does not accept document-provided HLSL: Unreal always builds the fixed
``tiger_ui_flipbook_atlas_custom_hlsl_v1`` graph from these validated fields.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence


TIGER_UMG_FLIPBOOK_SCHEMA = "tigerstudio.umg.flipbook.v1"
TIGER_UMG_FLIPBOOK_GENERATOR = "tiger_ui_flipbook_atlas_custom_hlsl_v1"
TIGER_UMG_FLIPBOOK_KIND = "FlipbookAtlas"
TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION = 12

FLIPBOOK_MAX_COLUMNS = 256
FLIPBOOK_MAX_ROWS = 256
FLIPBOOK_MAX_FRAMES = 4096
FLIPBOOK_MAX_FPS = 240.0


@dataclass(slots=True)
class UMGFlipbookConversion:
    """One Painter flipbook before its atlas resource is registered."""

    source_path: str
    record: dict[str, Any]
    block_reasons: list[str]

    def bind_asset(self, asset_id: str) -> dict[str, Any]:
        bound = dict(self.record)
        bound["AssetId"] = str(asset_id or "")
        return bound


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _finite_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    return result if math.isfinite(result) else float(default)


def _integer(value: object, default: int) -> int:
    return int(round(_number(value, float(default))))


def _is_integer(value: object) -> bool:
    return _finite_number(value) and float(value).is_integer()


def _value(source: Mapping[str, Any], *names: str, default: object) -> object:
    for name in names:
        if name in source:
            return source[name]
    return default


def normalize_umg_flipbook(value: object) -> dict[str, Any]:
    """Normalize aliases without admitting arbitrary shader source."""

    source = _mapping(value)
    return {
        "Schema": TIGER_UMG_FLIPBOOK_SCHEMA,
        "Generator": TIGER_UMG_FLIPBOOK_GENERATOR,
        "Kind": TIGER_UMG_FLIPBOOK_KIND,
        "CoordinateSpace": "LocalUV",
        "AssetId": str(_value(source, "AssetId", "asset_id", default="") or ""),
        "Columns": _integer(
            _value(source, "Columns", "columns", default=1),
            1,
        ),
        "Rows": _integer(_value(source, "Rows", "rows", default=1), 1),
        "FrameCount": _integer(
            _value(source, "FrameCount", "frame_count", default=1),
            1,
        ),
        "FramesPerSecond": _number(
            _value(
                source,
                "FramesPerSecond",
                "frames_per_second",
                "fps",
                default=12.0,
            ),
            12.0,
        ),
        "StartFrame": _integer(
            _value(source, "StartFrame", "start_frame", default=0),
            0,
        ),
        "Loop": bool(_value(source, "Loop", "loop", default=True)),
        "Phase": _number(_value(source, "Phase", "phase", default=0.0)),
        "StaticFrameOverride": _integer(
            _value(
                source,
                "StaticFrameOverride",
                "static_frame_override",
                "frame_override",
                default=-1,
            ),
            -1,
        ),
    }


def validate_umg_flipbook_record(
    value: object,
    *,
    layer_kind: str = "",
    document_schema_version: int | None = None,
    resource_ids: Sequence[str] | None = None,
) -> list[str]:
    """Validate the serialized record using the same limits as the plugin."""

    if not isinstance(value, Mapping) or not value:
        return []
    source = value
    reasons: list[str] = []
    if document_schema_version is not None:
        try:
            schema_version = int(document_schema_version)
        except (TypeError, ValueError):
            schema_version = 0
        if schema_version < TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION:
            reasons.append("flipbook_requires_schema_12")
    if str(source.get("Schema") or "") != TIGER_UMG_FLIPBOOK_SCHEMA:
        reasons.append("flipbook_schema_unsupported")
    if str(source.get("Generator") or "") != TIGER_UMG_FLIPBOOK_GENERATOR:
        reasons.append("flipbook_generator_unsupported")
    if str(source.get("Kind") or "") != TIGER_UMG_FLIPBOOK_KIND:
        reasons.append("flipbook_kind_unsupported")
    if str(source.get("CoordinateSpace") or "") != "LocalUV":
        reasons.append("flipbook_coordinate_space_unsupported")
    if layer_kind and str(layer_kind) not in {"Image", "Shape"}:
        reasons.append("flipbook_layer_kind_unsupported")

    asset_id = str(source.get("AssetId") or "")
    if not asset_id:
        reasons.append("flipbook_atlas_asset_id_missing")
    elif resource_ids is not None and asset_id not in set(resource_ids):
        reasons.append("flipbook_atlas_resource_missing")

    columns_value = source.get("Columns")
    rows_value = source.get("Rows")
    frame_count_value = source.get("FrameCount")
    columns = int(float(columns_value)) if _is_integer(columns_value) else 0
    rows = int(float(rows_value)) if _is_integer(rows_value) else 0
    frame_count = (
        int(float(frame_count_value)) if _is_integer(frame_count_value) else 0
    )
    if not 1 <= columns <= FLIPBOOK_MAX_COLUMNS:
        reasons.append("flipbook_columns_out_of_range")
    if not 1 <= rows <= FLIPBOOK_MAX_ROWS:
        reasons.append("flipbook_rows_out_of_range")
    capacity = columns * rows if columns > 0 and rows > 0 else 0
    if capacity > FLIPBOOK_MAX_FRAMES:
        reasons.append("flipbook_atlas_capacity_exceeded")
    if not 1 <= frame_count <= min(capacity, FLIPBOOK_MAX_FRAMES):
        reasons.append("flipbook_frame_count_out_of_range")

    fps = source.get("FramesPerSecond")
    if not _finite_number(fps) or not 0.0 <= float(fps) <= FLIPBOOK_MAX_FPS:
        reasons.append("flipbook_fps_out_of_range")
    start = source.get("StartFrame")
    if (
        not _is_integer(start)
        or frame_count <= 0
        or not 0 <= int(float(start)) < frame_count
    ):
        reasons.append("flipbook_start_frame_out_of_range")
    if not isinstance(source.get("Loop"), bool):
        reasons.append("flipbook_loop_invalid")
    phase = source.get("Phase")
    if not _finite_number(phase) or not 0.0 <= float(phase) <= 1.0:
        reasons.append("flipbook_phase_out_of_range")
    override = source.get("StaticFrameOverride")
    if (
        not _is_integer(override)
        or frame_count <= 0
        or not (
            int(float(override)) == -1
            or 0 <= int(float(override)) < frame_count
        )
    ):
        reasons.append("flipbook_static_frame_override_out_of_range")
    return sorted(set(reasons))


def _visible_image_paints(style: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    fills = style.get("fills")
    if not isinstance(fills, list):
        return []
    return [
        row
        for row in fills
        if isinstance(row, Mapping)
        and bool(row.get("visible", True))
        and str(row.get("type") or "").strip().casefold() == "image"
    ]


def painter_flipbook_conversion(
    row: Mapping[str, Any],
    style: Mapping[str, Any],
    content: Mapping[str, Any],
) -> UMGFlipbookConversion | None:
    """Convert ``content.flipbook`` into one bounded atlas material record."""

    raw = content.get("flipbook")
    if not isinstance(raw, Mapping) or not bool(raw.get("enabled", True)):
        return None
    source = dict(raw)
    record = normalize_umg_flipbook(source)
    # Asset IDs are assigned by the provider adapter after it hashes and
    # registers the source file.  Validate all authored fields here with a
    # temporary non-empty ID, then validate the bound record again in preflight.
    reasons = validate_umg_flipbook_record(
        {**record, "AssetId": "__pending_flipbook_atlas__"}
    )

    kind = str(row.get("kind") or "").strip().casefold()
    if kind not in {"image", "rectangle"}:
        reasons.append(f"flipbook_unsupported_object_kind:{kind or 'unknown'}")

    image_paints = _visible_image_paints(style)
    paint = image_paints[0] if image_paints else {}
    flipbook_path = str(
        source.get("source_path")
        or source.get("atlas_path")
        or source.get("path")
        or ""
    )
    content_path = str(content.get("source_path") or content.get("path") or "")
    paint_path = str(
        paint.get("source_path") or paint.get("path") or paint.get("uri") or ""
    )
    source_path = flipbook_path or content_path or paint_path
    nonempty_paths = {path for path in (flipbook_path, content_path, paint_path) if path}
    if not source_path:
        reasons.append("flipbook_atlas_source_path_missing")
    if len(nonempty_paths) > 1:
        reasons.append("flipbook_multiple_atlas_sources")
    if len(image_paints) > 1:
        reasons.append("flipbook_multiple_image_fills_unsupported")

    authored_mode = source.get(
        "image_fit",
        content.get("image_fit", paint.get("image_fit", paint.get("fit"))),
    )
    if authored_mode is not None and str(authored_mode).strip().casefold() not in {
        "stretch",
    }:
        reasons.append("flipbook_requires_full_atlas_stretch")
    if any(
        value not in (None, {}, [])
        for value in (
            source.get("crop"),
            source.get("image_crop"),
            content.get("crop"),
            content.get("image_crop"),
            content.get("image_transform"),
            paint.get("crop"),
            paint.get("image_crop"),
            paint.get("image_transform"),
        )
    ):
        reasons.append("flipbook_atlas_crop_unsupported")
    rotation = _number(
        source.get(
            "image_rotation",
            content.get("image_rotation", paint.get("image_rotation", 0.0)),
        ),
        0.0,
    )
    if abs(rotation) > 0.0001:
        reasons.append("flipbook_atlas_rotation_unsupported")
    if bool(
        source.get("nine_slice_enabled")
        or content.get("nine_slice_enabled")
        or paint.get("nine_slice_enabled")
    ):
        reasons.append("flipbook_nine_slice_unsupported")
    if abs(_number(style.get("radius"), 0.0)) > 0.0001 or any(
        abs(_number(value, 0.0)) > 0.0001
        for value in _mapping(style.get("corner_radii")).values()
    ):
        reasons.append("flipbook_rounded_clip_requires_ui_material_extension")
    if abs(_number(style.get("corner_smoothing"), 0.0)) > 0.0001:
        reasons.append("flipbook_corner_smoothing_unsupported")
    if str(style.get("blend_mode") or "normal").strip().casefold() not in {
        "normal",
        "pass_through",
    }:
        reasons.append("flipbook_blend_mode_unsupported")
    if str(paint.get("blend_mode") or "normal").strip().casefold() != "normal":
        reasons.append("flipbook_image_blend_mode_unsupported")

    return UMGFlipbookConversion(
        source_path=source_path,
        record=record,
        block_reasons=sorted(set(reasons)),
    )


def flipbook_frame_index(value: Mapping[str, Any], time_seconds: float) -> int:
    """Reference CPU selector used by tests and deterministic QA fixtures."""

    source = normalize_umg_flipbook(value)
    frame_count = max(1, int(source["FrameCount"]))
    static_override = int(source["StaticFrameOverride"])
    if static_override >= 0:
        offset = static_override
    else:
        offset = math.floor(float(source["Phase"]) * frame_count)
        offset += math.floor(
            max(0.0, float(time_seconds))
            * max(0.0, float(source["FramesPerSecond"]))
        )
    frame = int(source["StartFrame"]) + int(offset)
    if source["Loop"]:
        return frame % frame_count
    return min(max(0, frame), frame_count - 1)


def flipbook_custom_hlsl() -> str:
    """Return the fixed UV selector mirrored verbatim by TigerStudioUMG."""

    return "\n".join(
        [
            "// Tiger Flipbook Atlas / validated fixed Custom HLSL",
            "float SafeColumns = max(floor(Columns + 0.5), 1.0);",
            "float SafeRows = max(floor(Rows + 0.5), 1.0);",
            "float Capacity = SafeColumns * SafeRows;",
            "float SafeFrameCount = clamp(floor(FrameCount + 0.5), 1.0, Capacity);",
            "float SafeStartFrame = clamp(floor(StartFrame + 0.5), 0.0, SafeFrameCount - 1.0);",
            "float PhaseOffset = floor(saturate(Phase) * SafeFrameCount);",
            "float AnimatedOffset = floor(max(TimeSeconds, 0.0) * max(FramesPerSecond, 0.0));",
            "float FrameOffset = (StaticFrameOverride >= 0.0) ? floor(StaticFrameOverride + 0.5) : (PhaseOffset + AnimatedOffset);",
            "float RawFrame = SafeStartFrame + FrameOffset;",
            "float SelectedFrame = (Loop >= 0.5) ? fmod(RawFrame, SafeFrameCount) : min(RawFrame, SafeFrameCount - 1.0);",
            "float Column = fmod(SelectedFrame, SafeColumns);",
            "float Row = floor(SelectedFrame / SafeColumns);",
            "float2 CellUV = min(saturate(UV), float2(0.999999, 0.999999));",
            "return (CellUV + float2(Column, Row)) / float2(SafeColumns, SafeRows);",
        ]
    )


def flipbook_material_graph(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return an inspectable representation of the fixed UE material graph."""

    return {
        "schema": "tigerstudio.umg.flipbook_material_graph.v1",
        "flipbook": normalize_umg_flipbook(value),
        "nodes": [
            {"id": "uv", "type": "TextureCoordinate"},
            {"id": "time", "type": "Time"},
            {"id": "parameters", "type": "ValidatedScalarParameters"},
            {"id": "frame_uv", "type": "CustomHLSL"},
            {"id": "atlas", "type": "TextureSampleParameter2D"},
            {"id": "output", "type": "UIOutput"},
        ],
        "connections": [
            {"from": "uv", "to": "frame_uv", "port": "UV"},
            {"from": "time", "to": "frame_uv", "port": "TimeSeconds"},
            {"from": "parameters", "to": "frame_uv", "port": "Parameters"},
            {"from": "frame_uv", "to": "atlas", "port": "Coordinates"},
            {"from": "atlas", "to": "output", "port": "Color / Opacity"},
        ],
    }


__all__ = [
    "FLIPBOOK_MAX_COLUMNS",
    "FLIPBOOK_MAX_FPS",
    "FLIPBOOK_MAX_FRAMES",
    "FLIPBOOK_MAX_ROWS",
    "TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION",
    "TIGER_UMG_FLIPBOOK_GENERATOR",
    "TIGER_UMG_FLIPBOOK_KIND",
    "TIGER_UMG_FLIPBOOK_SCHEMA",
    "UMGFlipbookConversion",
    "flipbook_custom_hlsl",
    "flipbook_frame_index",
    "flipbook_material_graph",
    "normalize_umg_flipbook",
    "painter_flipbook_conversion",
    "validate_umg_flipbook_record",
]
