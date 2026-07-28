from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.export_pipeline import MotionExportCancelled, MotionProfileExporter
from app.motion_designer.export_profiles import (
    ffmpeg_capabilities,
    list_motion_export_profiles,
    preflight_motion_export,
)
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef


def _app():
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def _composition() -> MotionComposition:
    layer = MotionLayer(
        name="Alpha Red",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 12, "height": 12, "fill": "#ff0000", "stroke_width": 0,
        }),
        out_ms=100,
    )
    layer.transform.position.default = [8, 8]
    layer.transform.opacity.default = 0.5
    return MotionComposition(width=16, height=16, fps=10, duration_ms=100, layers=[layer])


def test_profile_catalog_and_installed_ffmpeg_capabilities() -> None:
    profiles = {row["id"] for row in list_motion_export_profiles()}
    assert profiles == {
        "h264_mp4", "h265_mp4", "prores_4444_mov", "png_sequence",
        "openexr_sequence", "png_still", "jpeg_still", "webp_still",
    }
    capabilities = ffmpeg_capabilities()
    assert capabilities["available"] is True
    for encoder in ("libx264", "libx265", "prores_ks", "exr"):
        assert capabilities["motion_encoders"][encoder] is True


def test_preflight_rejects_odd_420_and_legacy_scene_linear_exr(tmp_path: Path) -> None:
    odd = _composition()
    odd.width = 15
    report = preflight_motion_export(odd, "h264_mp4", output_path=tmp_path / "odd.mp4")
    assert report["ok"] is False
    assert any("even dimensions" in error for error in report["errors"])
    legacy = MotionComposition.from_dict(_composition().to_dict() | {"metadata": {}})
    report = preflight_motion_export(legacy, "openexr_sequence", output_path=tmp_path / "exr")
    assert report["ok"] is False
    assert any("scene-linear" in error for error in report["errors"])


def test_real_h264_prores_and_openexr_exports(tmp_path: Path) -> None:
    app = _app()
    exporter = MotionProfileExporter()
    composition = _composition()
    h264 = exporter.export(composition, "h264_mp4", tmp_path / "motion.mp4")
    prores = exporter.export(composition, "prores_4444_mov", tmp_path / "motion.mov")
    exr = exporter.export(composition, "openexr_sequence", tmp_path / "exr")
    assert h264["frame_count"] == 1 and Path(h264["output_path"]).stat().st_size > 0
    assert prores["alpha_contract"]["storage"] == "straight"
    assert Path(prores["output_path"]).stat().st_size > 0
    assert len(exr["paths"]) == 1 and Path(exr["paths"][0]).stat().st_size > 0
    assert Path(exr["manifest_path"]).is_file()
    app.processEvents()


def test_real_motion_hdr_h265_export_has_pq_metadata(tmp_path: Path) -> None:
    import subprocess

    from app.color_management import parse_ffmpeg_color_stream_text
    from app.motion_designer.export_profiles import find_ffmpeg_executable

    app = _app()
    composition = _composition()
    composition.width = 64
    composition.height = 64
    color = composition.metadata["color_management"]
    color["project"].update({
        "output_space": "rec2020",
        "output_transfer": "pq",
        "view_transform": "hdr-pq",
        "hdr_mode": True,
    })
    blocked = preflight_motion_export(
        composition,
        "h264_mp4",
        output_path=tmp_path / "blocked.mp4",
    )
    assert blocked["ok"] is False
    assert any("H.265" in error for error in blocked["errors"])

    output = tmp_path / "motion_hdr.mp4"
    result = MotionProfileExporter().export(
        composition,
        "h265_mp4",
        output,
    )
    assert result["frame_count"] == 1
    assert output.stat().st_size > 0
    inspected = subprocess.run(
        [find_ffmpeg_executable(), "-hide_banner", "-i", str(output)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    actual = parse_ffmpeg_color_stream_text(inspected.stderr)
    assert actual["color_primaries"] == "bt2020"
    assert actual["color_transfer"] == "smpte2084"
    app.processEvents()


def test_openexr_retry_removes_stale_sequence_frames(tmp_path: Path) -> None:
    app = _app()
    composition = _composition()
    output = tmp_path / "exr"
    output.mkdir()
    stale = output / "frame_999999.exr"
    stale.write_bytes(b"stale")
    (output / "manifest.json").write_text("{}", encoding="utf-8")

    result = MotionProfileExporter().export(composition, "openexr_sequence", output)

    assert result["frame_count"] == 1
    assert len(result["paths"]) == 1
    assert stale.exists() is False
    assert Path(result["manifest_path"]).is_file()
    app.processEvents()


def test_png_sequence_cancel_resume_and_manifest(tmp_path: Path) -> None:
    app = _app()
    composition = _composition()
    composition.duration_ms = 500
    calls = 0

    def cancelled() -> bool:
        nonlocal calls
        calls += 1
        return calls > 2

    output = tmp_path / "png"
    with pytest.raises(MotionExportCancelled):
        MotionProfileExporter(cancel_check=cancelled).export(
            composition, "png_sequence", output,
        )
    partial = sorted(output.glob("frame_*.png"))
    assert len(partial) == 2
    assert not (output / "manifest.json").exists()

    result = MotionProfileExporter().export(
        composition, "png_sequence", output, resume=True,
    )
    assert result["sequence_complete"] is True
    assert result["resumed_frame_count"] == 2
    assert result["rendered_frame_count"] == 3
    assert len(result["paths"]) == 5
    assert Path(result["manifest_path"]).is_file()
    app.processEvents()


def test_video_cancel_cleans_partial_and_retry_succeeds(tmp_path: Path) -> None:
    app = _app()
    composition = _composition()
    composition.duration_ms = 300
    calls = 0

    def cancelled() -> bool:
        nonlocal calls
        calls += 1
        return calls > 1

    output = tmp_path / "retry.mp4"
    with pytest.raises(MotionExportCancelled):
        MotionProfileExporter(cancel_check=cancelled).export(composition, "h264_mp4", output)
    assert not output.exists()
    assert not output.with_name(output.name + ".partial").exists()
    result = MotionProfileExporter().export(composition, "h264_mp4", output)
    assert result["frame_count"] == 3
    assert output.stat().st_size > 0
    app.processEvents()


class _Owner:
    def __init__(self, composition: MotionComposition) -> None:
        self._motion_compositions = {composition.id: composition}


def test_color_and_export_actions_are_registered(tmp_path: Path) -> None:
    composition = _composition()
    owner = _Owner(composition)
    registry = ActionRegistry(owner)
    listed = registry.execute("motion.export.profile.list", {})
    assert listed.ok and listed.result["count"] == 8
    color = registry.execute("motion.color.get", {"composition_id": composition.id})
    assert color.ok and color.result["report"]["ok"] is True
    output = tmp_path / "still.png"
    rendered = registry.execute("motion.export.profile.render", {
        "composition_id": composition.id, "profile_id": "png_still", "output_path": str(output),
        "resume": False,
    })
    assert rendered.ok and output.is_file()
