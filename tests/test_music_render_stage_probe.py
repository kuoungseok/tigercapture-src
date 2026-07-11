from __future__ import annotations

from pathlib import Path


def test_music_render_stage_probe_writes_incremental_stage_reports(tmp_path: Path) -> None:
    from tools.music_render_stage_probe import ABLATION_ORDER, STAGE_ORDER, render_sample_production_stages

    summary = render_sample_production_stages(
        output_dir=tmp_path,
        prompt="short diagnostic music cue",
        duration_ms=4000,
        genre="melodic EDM",
        mood="bright",
        bpm=120,
        key="A minor",
    )

    stages = summary["stages"]
    assert [row["stage"] for row in stages] == STAGE_ORDER
    ablations = summary["ablations"]
    assert [row["stage"] for row in ablations] == ABLATION_ORDER
    assert Path(summary["summary_path"]).exists()
    for row in stages + ablations:
        assert Path(row["wav"]).exists()
        assert Path(row["playback_safe_wav"]).exists()
        assert Path(row["report"]).exists()
        assert "glitch_score" in row["metrics"]
        assert "beat_peak_to_peak_db" in row["metrics"]
