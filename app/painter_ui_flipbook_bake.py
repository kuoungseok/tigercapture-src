"""Deterministic Motion Designer composition to UMG flipbook-atlas bake.

This module is intentionally provider-neutral and file-only.  It renders the
same MotionComposition used by Motion Designer, packs exact cadence samples in
row-major order, and emits the bounded schema-12 flipbook record consumed by
TigerStudioUMG.  Authored shader source is never accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from PySide6.QtCore import QBuffer, QIODevice, QPoint
from PySide6.QtGui import QImage, QPainter

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import MotionComposition
from app.unreal_umg_flipbook import (
    FLIPBOOK_MAX_COLUMNS,
    FLIPBOOK_MAX_FPS,
    FLIPBOOK_MAX_FRAMES,
    FLIPBOOK_MAX_ROWS,
    TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION,
    TIGER_UMG_FLIPBOOK_GENERATOR,
    normalize_umg_flipbook,
    validate_umg_flipbook_record,
)


PAINTER_UI_FLIPBOOK_BAKE_SCHEMA = "tigerstudio.painter.motion_flipbook_bake.v1"
PAINTER_UI_FLIPBOOK_MAX_ATLAS_SIZE = 8192
PAINTER_UI_FLIPBOOK_TIME_ORIGIN = "global_time"

PLAYBACK_SCOPE_AMBIENT_LOOP = "ambient_loop"
PLAYBACK_SCOPE_EVENT_TRIGGERED = "event_triggered"

_EVENT_TIME_ORIGIN_BLOCKER = (
    "flipbook_trigger_requires_dynamic_material_time_origin"
)


class PainterUIFlipbookBakeError(RuntimeError):
    """A deterministic bake refusal with machine-readable blocker reasons."""

    def __init__(
        self,
        block_reasons: str | Sequence[str],
        *,
        detail: str = "",
    ) -> None:
        reasons = (
            [block_reasons]
            if isinstance(block_reasons, str)
            else [str(reason) for reason in block_reasons]
        )
        self.block_reasons = tuple(sorted(set(reasons)))
        self.detail = str(detail or "")
        message = ", ".join(self.block_reasons)
        if self.detail:
            message = f"{message}: {self.detail}"
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class PainterUIFlipbookBakeResult:
    atlas_path: Path
    manifest_path: Path
    manifest: dict[str, Any]
    flipbook_record: dict[str, Any]
    reused: bool
    material_ready: bool
    playback_scope: str
    time_origin: str
    block_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _BakePlan:
    fps: Fraction
    frame_count: int
    cell_width: int
    cell_height: int
    columns: int
    rows: int
    atlas_width: int
    atlas_height: int
    max_atlas_size: int
    playback_scope: str
    loop: bool
    block_reasons: tuple[str, ...]


def _canonical_json_bytes(value: object, *, newline: bool = False) -> bytes:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise PainterUIFlipbookBakeError(
            "motion_flipbook_composition_not_serializable",
            detail=f"{type(exc).__name__}:{exc}",
        ) from exc
    if newline:
        encoded += "\n"
    return encoded.encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _positive_bounded_integer(
    value: object,
    *,
    reason: str,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise PainterUIFlipbookBakeError(reason)
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PainterUIFlipbookBakeError(reason) from exc
    if not math.isfinite(number) or not number.is_integer():
        raise PainterUIFlipbookBakeError(reason)
    result = int(number)
    if not 1 <= result <= int(maximum):
        raise PainterUIFlipbookBakeError(reason)
    return result


def _nonnegative_integer(value: object, *, reason: str) -> int:
    if isinstance(value, bool):
        raise PainterUIFlipbookBakeError(reason)
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PainterUIFlipbookBakeError(reason) from exc
    if not math.isfinite(number) or not number.is_integer() or number < 0:
        raise PainterUIFlipbookBakeError(reason)
    return int(number)


def _fps_fraction(value: object) -> Fraction:
    if isinstance(value, bool):
        raise PainterUIFlipbookBakeError("motion_flipbook_fps_out_of_range")
    try:
        number = float(value)
        exact = Fraction(str(value))
    except (TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
        raise PainterUIFlipbookBakeError(
            "motion_flipbook_fps_out_of_range"
        ) from exc
    if (
        not math.isfinite(number)
        or exact <= 0
        or exact > Fraction(str(FLIPBOOK_MAX_FPS))
    ):
        raise PainterUIFlipbookBakeError("motion_flipbook_fps_out_of_range")
    return exact


def _normalize_playback_scope(value: object) -> str:
    normalized = str(value or PLAYBACK_SCOPE_AMBIENT_LOOP).strip().casefold()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    if normalized in {
        "ambient",
        "ambient_loop",
        "auto",
        "automatic",
        "automatic_loop",
        "auto_loop",
        "loop",
        "global",
    }:
        return PLAYBACK_SCOPE_AMBIENT_LOOP
    if normalized in {
        "event",
        "event_triggered",
        "interaction",
        "interactive",
        "click",
        "hover",
        "pressed",
    }:
        return PLAYBACK_SCOPE_EVENT_TRIGGERED
    raise PainterUIFlipbookBakeError(
        f"motion_flipbook_playback_scope_unsupported:{normalized or 'empty'}"
    )


def _choose_grid(
    frame_count: int,
    cell_width: int,
    cell_height: int,
    max_atlas_size: int,
) -> tuple[int, int]:
    max_columns = min(
        FLIPBOOK_MAX_COLUMNS,
        frame_count,
        max_atlas_size // cell_width,
    )
    max_rows = min(
        FLIPBOOK_MAX_ROWS,
        frame_count,
        max_atlas_size // cell_height,
    )
    candidates: list[tuple[tuple[int, int, int, int, int], int, int]] = []
    for columns in range(1, max_columns + 1):
        rows = (frame_count + columns - 1) // columns
        capacity = columns * rows
        if rows > max_rows or capacity > FLIPBOOK_MAX_FRAMES:
            continue
        atlas_width = columns * cell_width
        atlas_height = rows * cell_height
        key = (
            max(atlas_width, atlas_height),
            atlas_width * atlas_height,
            capacity - frame_count,
            abs(atlas_width - atlas_height),
            columns,
        )
        candidates.append((key, columns, rows))
    if not candidates:
        raise PainterUIFlipbookBakeError(
            "motion_flipbook_atlas_capacity_exceeded"
        )
    _, columns, rows = min(candidates)
    return columns, rows


def _build_plan(
    composition: MotionComposition,
    *,
    fps: float | None,
    frame_count: int | None,
    cell_width: int | None,
    cell_height: int | None,
    max_atlas_size: int,
    playback_scope: str | None,
    loop: bool,
) -> _BakePlan:
    if not isinstance(composition, MotionComposition):
        raise PainterUIFlipbookBakeError(
            "motion_flipbook_composition_invalid"
        )
    duration_ms = _nonnegative_integer(
        composition.duration_ms,
        reason="motion_flipbook_duration_out_of_range",
    )
    atlas_limit = _positive_bounded_integer(
        max_atlas_size,
        reason="motion_flipbook_atlas_size_out_of_range",
        maximum=PAINTER_UI_FLIPBOOK_MAX_ATLAS_SIZE,
    )
    cadence = _fps_fraction(composition.fps if fps is None else fps)
    if frame_count is None:
        duration_frames = Fraction(duration_ms, 1000) * cadence
        count = max(1, math.ceil(duration_frames))
        if count > FLIPBOOK_MAX_FRAMES:
            raise PainterUIFlipbookBakeError(
                "motion_flipbook_frame_count_out_of_range"
            )
    else:
        count = _positive_bounded_integer(
            frame_count,
            reason="motion_flipbook_frame_count_out_of_range",
            maximum=FLIPBOOK_MAX_FRAMES,
        )
    if duration_ms > 0:
        last_sample_ms = Fraction((count - 1) * 1000, 1) / cadence
        if last_sample_ms >= duration_ms:
            raise PainterUIFlipbookBakeError(
                "motion_flipbook_sample_exceeds_composition_duration"
            )
    width = _positive_bounded_integer(
        composition.width if cell_width is None else cell_width,
        reason="motion_flipbook_cell_size_out_of_range",
        maximum=atlas_limit,
    )
    height = _positive_bounded_integer(
        composition.height if cell_height is None else cell_height,
        reason="motion_flipbook_cell_size_out_of_range",
        maximum=atlas_limit,
    )
    columns, rows = _choose_grid(count, width, height, atlas_limit)
    scope_source = playback_scope
    if scope_source is None and isinstance(composition.metadata, Mapping):
        scope_source = composition.metadata.get("playback_scope")
    scope = _normalize_playback_scope(scope_source)
    if not isinstance(loop, bool):
        raise PainterUIFlipbookBakeError("motion_flipbook_loop_invalid")
    reasons = (
        (_EVENT_TIME_ORIGIN_BLOCKER,)
        if scope == PLAYBACK_SCOPE_EVENT_TRIGGERED
        else ()
    )
    return _BakePlan(
        fps=cadence,
        frame_count=count,
        cell_width=width,
        cell_height=height,
        columns=columns,
        rows=rows,
        atlas_width=columns * width,
        atlas_height=rows * height,
        max_atlas_size=atlas_limit,
        playback_scope=scope,
        loop=loop,
        block_reasons=reasons,
    )


def _png_bytes(image: QImage, *, reason: str) -> bytes:
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise PainterUIFlipbookBakeError(reason)
    try:
        if not image.save(buffer, "PNG"):
            raise PainterUIFlipbookBakeError(reason)
        return bytes(buffer.data())
    finally:
        buffer.close()


def _rgba_bytes(image: QImage) -> bytes:
    view = image.constBits()
    return bytes(view[: image.sizeInBytes()])


def _sample_manifest_time(sample_time: Fraction) -> dict[str, Any]:
    return {
        "time_ms": (
            sample_time.numerator
            if sample_time.denominator == 1
            else float(sample_time)
        ),
        "time_ms_fraction": {
            "numerator": sample_time.numerator,
            "denominator": sample_time.denominator,
        },
    }


def _safe_slug(composition: MotionComposition) -> str:
    source = str(composition.name or composition.id or "motion")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", source).strip("-._")
    if not slug:
        slug = "motion"
    return slug[:64]


def _existing_outputs_are_identical(
    expected: Mapping[Path, bytes],
) -> bool | None:
    existing = [path for path in expected if path.exists()]
    if not existing:
        return None
    if len(existing) != len(expected):
        return False
    for path, payload in expected.items():
        try:
            if not path.is_file() or path.read_bytes() != payload:
                return False
        except OSError:
            return False
    return True


def _write_new_outputs(expected: Mapping[Path, bytes]) -> None:
    for path, payload in expected.items():
        try:
            with path.open("xb") as stream:
                stream.write(payload)
        except FileExistsError as exc:
            raise PainterUIFlipbookBakeError(
                "motion_flipbook_output_collision",
                detail=str(path),
            ) from exc
        except OSError as exc:
            raise PainterUIFlipbookBakeError(
                "motion_flipbook_output_write_failed",
                detail=f"{path}:{type(exc).__name__}:{exc}",
            ) from exc


def bake_motion_composition_flipbook(
    composition: MotionComposition,
    output_dir: str | Path,
    *,
    fps: float | None = None,
    frame_count: int | None = None,
    cell_width: int | None = None,
    cell_height: int | None = None,
    max_atlas_size: int = PAINTER_UI_FLIPBOOK_MAX_ATLAS_SIZE,
    playback_scope: str | None = None,
    loop: bool = True,
    renderer: MotionExportRenderer | None = None,
) -> PainterUIFlipbookBakeResult:
    """Bake one MotionComposition into a deterministic transparent PNG atlas.

    Event-triggered compositions are still baked, but their manifest and
    result carry ``flipbook_trigger_requires_dynamic_material_time_origin``.
    The current Unreal material uses global time, so only ambient/automatic
    playback is reported as Material-ready.
    """

    plan = _build_plan(
        composition,
        fps=fps,
        frame_count=frame_count,
        cell_width=cell_width,
        cell_height=cell_height,
        max_atlas_size=max_atlas_size,
        playback_scope=playback_scope,
        loop=loop,
    )
    composition_payload = _canonical_json_bytes(composition.to_dict())
    composition_sha256 = _sha256(composition_payload)
    atlas = QImage(
        plan.atlas_width,
        plan.atlas_height,
        QImage.Format.Format_RGBA8888,
    )
    if atlas.isNull():
        raise PainterUIFlipbookBakeError(
            "motion_flipbook_atlas_allocation_failed"
        )
    atlas.fill(0)
    atlas_painter = QPainter(atlas)
    if not atlas_painter.isActive():
        raise PainterUIFlipbookBakeError(
            "motion_flipbook_atlas_painter_failed"
        )
    atlas_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)

    active_renderer = renderer or MotionExportRenderer()
    samples: list[dict[str, Any]] = []
    try:
        for index in range(plan.frame_count):
            sample_time = Fraction(index * 1000, 1) / plan.fps
            try:
                frame = active_renderer.render_frame(
                    composition,
                    float(sample_time),
                    width=plan.cell_width,
                    height=plan.cell_height,
                    use_cache=False,
                )
            except Exception as exc:
                raise PainterUIFlipbookBakeError(
                    f"motion_flipbook_frame_render_failed:{index}",
                    detail=f"{type(exc).__name__}:{exc}",
                ) from exc
            if not isinstance(frame, QImage) or frame.isNull():
                raise PainterUIFlipbookBakeError(
                    f"motion_flipbook_frame_render_failed:{index}"
                )
            if (
                frame.width() != plan.cell_width
                or frame.height() != plan.cell_height
            ):
                raise PainterUIFlipbookBakeError(
                    f"motion_flipbook_frame_size_mismatch:{index}"
                )
            rgba_frame = frame.convertToFormat(QImage.Format.Format_RGBA8888)
            frame_png = _png_bytes(
                rgba_frame,
                reason=f"motion_flipbook_frame_png_encode_failed:{index}",
            )
            column = index % plan.columns
            row = index // plan.columns
            x = column * plan.cell_width
            y = row * plan.cell_height
            atlas_painter.drawImage(QPoint(x, y), rgba_frame)
            samples.append(
                {
                    "index": index,
                    "column": column,
                    "row": row,
                    "atlas_rect": {
                        "x": x,
                        "y": y,
                        "width": plan.cell_width,
                        "height": plan.cell_height,
                    },
                    **_sample_manifest_time(sample_time),
                    "rgba_sha256": _sha256(_rgba_bytes(rgba_frame)),
                    "png_sha256": _sha256(frame_png),
                }
            )
    finally:
        atlas_painter.end()

    if _canonical_json_bytes(composition.to_dict()) != composition_payload:
        raise PainterUIFlipbookBakeError(
            "motion_flipbook_source_composition_mutated_during_bake"
        )

    atlas_png = _png_bytes(
        atlas,
        reason="motion_flipbook_atlas_png_encode_failed",
    )
    atlas_sha256 = _sha256(atlas_png)
    asset_id = f"motion_flipbook_{atlas_sha256[:32]}"
    record = normalize_umg_flipbook(
        {
            "AssetId": asset_id,
            "Columns": plan.columns,
            "Rows": plan.rows,
            "FrameCount": plan.frame_count,
            "FramesPerSecond": float(plan.fps),
            "StartFrame": 0,
            "Loop": plan.loop,
            "Phase": 0.0,
            "StaticFrameOverride": -1,
        }
    )
    record_reasons = validate_umg_flipbook_record(
        record,
        layer_kind="Image",
        document_schema_version=TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION,
        resource_ids=[asset_id],
    )
    if record_reasons:
        raise PainterUIFlipbookBakeError(
            [f"motion_flipbook_record_invalid:{reason}" for reason in record_reasons]
        )

    bake_identity = {
        "schema": PAINTER_UI_FLIPBOOK_BAKE_SCHEMA,
        "composition_sha256": composition_sha256,
        "composition_revision": int(composition.revision),
        "fps_fraction": [plan.fps.numerator, plan.fps.denominator],
        "frame_count": plan.frame_count,
        "cell_size": [plan.cell_width, plan.cell_height],
        "grid": [plan.columns, plan.rows],
        "max_atlas_size": plan.max_atlas_size,
        "playback_scope": plan.playback_scope,
        "time_origin": PAINTER_UI_FLIPBOOK_TIME_ORIGIN,
        "loop": plan.loop,
    }
    bake_sha256 = _sha256(_canonical_json_bytes(bake_identity))
    stem = (
        f"{_safe_slug(composition)}.r{int(composition.revision)}."
        f"{bake_sha256[:12]}.{atlas_sha256[:12]}.flipbook"
    )
    atlas_filename = f"{stem}.png"
    manifest_filename = f"{stem}.manifest.json"
    material_ready = not plan.block_reasons
    manifest: dict[str, Any] = {
        "schema": PAINTER_UI_FLIPBOOK_BAKE_SCHEMA,
        "document_schema_version": TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION,
        "source": {
            "kind": "MotionComposition",
            "composition_id": str(composition.id),
            "composition_name": str(composition.name),
            "composition_revision": int(composition.revision),
            "composition_schema_version": int(composition.schema_version),
            "composition_sha256": composition_sha256,
            "source_unchanged": True,
        },
        "bake_sha256": bake_sha256,
        "playback_scope": plan.playback_scope,
        "time_origin": PAINTER_UI_FLIPBOOK_TIME_ORIGIN,
        "material_ready": material_ready,
        "block_reasons": list(plan.block_reasons),
        "sampling": {
            "frames_per_second": float(plan.fps),
            "frames_per_second_fraction": {
                "numerator": plan.fps.numerator,
                "denominator": plan.fps.denominator,
            },
            "frame_count": plan.frame_count,
            "cadence": "index_times_1000_divided_by_fps",
            "samples": samples,
        },
        "atlas": {
            "filename": atlas_filename,
            "sha256": atlas_sha256,
            "mime_type": "image/png",
            "pixel_format": "RGBA8_straight_alpha",
            "packing": "row_major",
            "width": plan.atlas_width,
            "height": plan.atlas_height,
            "cell_width": plan.cell_width,
            "cell_height": plan.cell_height,
            "columns": plan.columns,
            "rows": plan.rows,
            "max_atlas_size": plan.max_atlas_size,
        },
        "umg": {
            "record": record,
            "playback_scope": plan.playback_scope,
            "time_origin": PAINTER_UI_FLIPBOOK_TIME_ORIGIN,
            "material_ready": material_ready,
            "block_reasons": list(plan.block_reasons),
        },
        "shader_policy": {
            "mode": "fixed_generator_only",
            "generator": TIGER_UMG_FLIPBOOK_GENERATOR,
            "arbitrary_hlsl": "forbidden",
        },
    }
    manifest_payload = _canonical_json_bytes(manifest, newline=True)
    directory = Path(output_dir)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PainterUIFlipbookBakeError(
            "motion_flipbook_output_directory_failed",
            detail=f"{directory}:{type(exc).__name__}:{exc}",
        ) from exc
    atlas_path = directory / atlas_filename
    manifest_path = directory / manifest_filename
    expected = {
        atlas_path: atlas_png,
        manifest_path: manifest_payload,
    }
    reuse_state = _existing_outputs_are_identical(expected)
    if reuse_state is False:
        raise PainterUIFlipbookBakeError(
            "motion_flipbook_output_collision",
            detail=f"{atlas_path};{manifest_path}",
        )
    reused = reuse_state is True
    if not reused:
        _write_new_outputs(expected)
    return PainterUIFlipbookBakeResult(
        atlas_path=atlas_path,
        manifest_path=manifest_path,
        manifest=manifest,
        flipbook_record=record,
        reused=reused,
        material_ready=material_ready,
        playback_scope=plan.playback_scope,
        time_origin=PAINTER_UI_FLIPBOOK_TIME_ORIGIN,
        block_reasons=plan.block_reasons,
    )


# Concise alias for callers that already deal in MotionComposition objects.
bake_motion_flipbook_atlas = bake_motion_composition_flipbook


__all__ = [
    "PAINTER_UI_FLIPBOOK_BAKE_SCHEMA",
    "PAINTER_UI_FLIPBOOK_MAX_ATLAS_SIZE",
    "PAINTER_UI_FLIPBOOK_TIME_ORIGIN",
    "PLAYBACK_SCOPE_AMBIENT_LOOP",
    "PLAYBACK_SCOPE_EVENT_TRIGGERED",
    "PainterUIFlipbookBakeError",
    "PainterUIFlipbookBakeResult",
    "bake_motion_composition_flipbook",
    "bake_motion_flipbook_atlas",
]
