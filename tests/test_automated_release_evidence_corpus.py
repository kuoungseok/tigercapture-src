from __future__ import annotations

import importlib.util


def test_build_automated_release_evidence_corpus_registers_temp_manifests(tmp_path):
    if importlib.util.find_spec("cv2") is None:
        import pytest

        pytest.skip("opencv is required for synthetic MP4 generation")

    from app.ai_edit_corpus_quality import build_ai_edit_corpus_quality_report
    from app.screenstudio_parity import screenstudio_real_recording_corpus_report
    from tools.build_automated_release_evidence_corpus import build_automated_release_evidence_corpus

    screen_manifest = tmp_path / "screenstudio" / "manifest.json"
    ai_manifest = tmp_path / "ai" / "manifest.json"
    out_dir = tmp_path / "generated"

    report = build_automated_release_evidence_corpus(
        out_dir=out_dir,
        screenstudio_count=1,
        ai_count=1,
        screenstudio_manifest=screen_manifest,
        ai_manifest=ai_manifest,
        overwrite=True,
    )

    assert report["ok"] is True
    assert report["provenance"] == "automation_generated"
    assert report["counts_as_human_user_evidence"] is False
    assert report["summary"]["screenstudio_ok"] == 1
    assert report["summary"]["ai_ok"] == 1

    screen_report = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty_roots"],
        real_manifest_path=screen_manifest,
        deep_probe=True,
    )
    assert screen_report["summary"]["valid_files"] == 1
    assert screen_report["summary"]["cursor_sidecar_ready"] == 1
    assert screen_report["summary"]["interaction_ready"] == 1

    ai_report = build_ai_edit_corpus_quality_report(
        manifest_path=ai_manifest,
        use_provider=False,
        env={},
    )
    assert ai_report["summary"]["cases"] == 1
    assert ai_report["summary"]["real_cases"] == 1
    assert ai_report["failures"] == []
