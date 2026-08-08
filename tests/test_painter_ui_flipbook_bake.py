from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication
import pytest

from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
    SourceRef,
)
from app.painter_ui_flipbook_bake import (
    PAINTER_UI_FLIPBOOK_BAKE_SCHEMA,
    PAINTER_UI_FLIPBOOK_TIME_ORIGIN,
    PainterUIFlipbookBakeError,
    bake_motion_composition_flipbook,
)
from app.unreal_umg_flipbook import (
    TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION,
    TIGER_UMG_FLIPBOOK_GENERATOR,
    flipbook_frame_index,
    validate_umg_flipbook_record,
)


def _app() -> QApplication:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def _four_frame_composition() -> MotionComposition:
    fill = AnimatedProperty(
        value_type="color",
        default="#ff0000",
        keyframes=[
            Keyframe(
                id=f"fill_{index}",
                time_ms=time_ms,
                value=color,
                interpolation="linear",
            )
            for index, (time_ms, color) in enumerate(
                (
                    (0, "#ff0000"),
                    (250, "#00ff00"),
                    (500, "#0000ff"),
                    (750, "#ffff00"),
                )
            )
        ],
    )
    layer = MotionLayer(
        id="color_card",
        name="Color Card",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "shape": "rectangle",
                "width": 8,
                "height": 8,
                "fill": fill.to_dict(),
                "stroke": "transparent",
                "stroke_width": 0,
            },
        ),
        out_ms=1000,
    )
    layer.transform.position.default = [6, 6]
    return MotionComposition(
        id="four_color_composition",
        name="Four Color",
        width=12,
        height=12,
        fps=4.0,
        duration_ms=1000,
        revision=7,
        layers=[layer],
        metadata={"playback_scope": "ambient_loop"},
    )


def _center_color(image: QImage, column: int, row: int) -> QColor:
    return image.pixelColor(column * 12 + 6, row * 12 + 6)


def test_real_motion_renderer_bakes_row_major_rgba_atlas_deterministically(
    tmp_path: Path,
) -> None:
    app = _app()
    composition = _four_frame_composition()
    before = composition.to_dict()

    first = bake_motion_composition_flipbook(composition, tmp_path)
    atlas_bytes = first.atlas_path.read_bytes()
    atlas = QImage(str(first.atlas_path)).convertToFormat(
        QImage.Format.Format_RGBA8888
    )

    assert first.reused is False
    assert first.material_ready is True
    assert first.block_reasons == ()
    assert first.playback_scope == "ambient_loop"
    assert first.time_origin == "global_time"
    assert composition.to_dict() == before
    assert (atlas.width(), atlas.height()) == (24, 24)
    assert atlas.hasAlphaChannel()
    expected = [
        QColor("#ff0000"),
        QColor("#00ff00"),
        QColor("#0000ff"),
        QColor("#ffff00"),
    ]
    for index, color in enumerate(expected):
        column, row = index % 2, index // 2
        actual = _center_color(atlas, column, row)
        assert actual.red() == color.red()
        assert actual.green() == color.green()
        assert actual.blue() == color.blue()
        assert actual.alpha() == 255
        assert atlas.pixelColor(column * 12, row * 12).alpha() == 0

    manifest = first.manifest
    assert manifest["schema"] == PAINTER_UI_FLIPBOOK_BAKE_SCHEMA
    assert (
        manifest["document_schema_version"]
        == TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION
    )
    assert manifest["source"]["composition_revision"] == 7
    assert manifest["source"]["source_unchanged"] is True
    assert manifest["atlas"]["packing"] == "row_major"
    assert manifest["atlas"]["sha256"] == hashlib.sha256(atlas_bytes).hexdigest()
    assert manifest["atlas"]["pixel_format"] == "RGBA8_straight_alpha"
    assert manifest["sampling"]["frame_count"] == 4
    assert [
        sample["time_ms_fraction"]
        for sample in manifest["sampling"]["samples"]
    ] == [
        {"numerator": 0, "denominator": 1},
        {"numerator": 250, "denominator": 1},
        {"numerator": 500, "denominator": 1},
        {"numerator": 750, "denominator": 1},
    ]
    assert len(
        {
            sample["png_sha256"]
            for sample in manifest["sampling"]["samples"]
        }
    ) == 4
    assert json.loads(first.manifest_path.read_text(encoding="utf-8")) == manifest

    record = first.flipbook_record
    assert record["Generator"] == TIGER_UMG_FLIPBOOK_GENERATOR
    assert record["Columns"] == 2
    assert record["Rows"] == 2
    assert record["FrameCount"] == 4
    assert validate_umg_flipbook_record(
        record,
        layer_kind="Image",
        document_schema_version=TIGER_UMG_FLIPBOOK_DOCUMENT_SCHEMA_VERSION,
        resource_ids=[record["AssetId"]],
    ) == []
    assert [flipbook_frame_index(record, time) for time in (0, .25, .5, .75)] == [
        0,
        1,
        2,
        3,
    ]
    assert "CustomHLSL" not in record
    assert "HLSLSource" not in record
    assert manifest["shader_policy"]["arbitrary_hlsl"] == "forbidden"

    repeated = bake_motion_composition_flipbook(composition, tmp_path)
    assert repeated.reused is True
    assert repeated.atlas_path == first.atlas_path
    assert repeated.manifest_path == first.manifest_path
    assert repeated.atlas_path.read_bytes() == atlas_bytes
    assert repeated.manifest == manifest
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(
        [first.atlas_path.name, first.manifest_path.name]
    )
    app.processEvents()


def test_event_triggered_bake_is_generated_but_not_material_ready(
    tmp_path: Path,
) -> None:
    _app()
    result = bake_motion_composition_flipbook(
        _four_frame_composition(),
        tmp_path,
        playback_scope="hover",
    )

    reason = "flipbook_trigger_requires_dynamic_material_time_origin"
    assert result.atlas_path.is_file()
    assert result.playback_scope == "event_triggered"
    assert result.time_origin == PAINTER_UI_FLIPBOOK_TIME_ORIGIN
    assert result.material_ready is False
    assert result.block_reasons == (reason,)
    assert result.manifest["playback_scope"] == "event_triggered"
    assert result.manifest["time_origin"] == "global_time"
    assert result.manifest["block_reasons"] == [reason]
    assert result.manifest["umg"]["material_ready"] is False
    assert result.manifest["umg"]["block_reasons"] == [reason]


def test_fractional_fps_sample_time_is_recorded_exactly(tmp_path: Path) -> None:
    _app()
    result = bake_motion_composition_flipbook(
        _four_frame_composition(),
        tmp_path,
        fps=29.97,
        frame_count=2,
    )

    sampling = result.manifest["sampling"]
    assert sampling["frames_per_second_fraction"] == {
        "numerator": 2997,
        "denominator": 100,
    }
    assert sampling["samples"][1]["time_ms_fraction"] == {
        "numerator": 100000,
        "denominator": 2997,
    }
    assert sampling["samples"][1]["time_ms"] == pytest.approx(100000 / 2997)


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"fps": 241}, "motion_flipbook_fps_out_of_range"),
        ({"frame_count": 4097}, "motion_flipbook_frame_count_out_of_range"),
        (
            {"frame_count": 5},
            "motion_flipbook_sample_exceeds_composition_duration",
        ),
        (
            {"max_atlas_size": 8193},
            "motion_flipbook_atlas_size_out_of_range",
        ),
        (
            {"cell_width": 13, "max_atlas_size": 12},
            "motion_flipbook_cell_size_out_of_range",
        ),
        (
            {"frame_count": 2, "max_atlas_size": 12},
            "motion_flipbook_atlas_capacity_exceeded",
        ),
    ],
)
def test_bake_limits_fail_with_explicit_blocker(
    tmp_path: Path,
    kwargs: dict[str, object],
    reason: str,
) -> None:
    with pytest.raises(PainterUIFlipbookBakeError) as caught:
        bake_motion_composition_flipbook(
            _four_frame_composition(),
            tmp_path,
            **kwargs,
        )

    assert reason in caught.value.block_reasons
    assert not tmp_path.exists() or list(tmp_path.iterdir()) == []


def test_existing_different_output_is_never_overwritten(tmp_path: Path) -> None:
    _app()
    composition = _four_frame_composition()
    first = bake_motion_composition_flipbook(composition, tmp_path)
    first.atlas_path.write_bytes(b"different-existing-content")

    with pytest.raises(PainterUIFlipbookBakeError) as caught:
        bake_motion_composition_flipbook(composition, tmp_path)

    assert caught.value.block_reasons == ("motion_flipbook_output_collision",)
    assert first.atlas_path.read_bytes() == b"different-existing-content"
