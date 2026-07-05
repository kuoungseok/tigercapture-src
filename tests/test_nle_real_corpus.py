from __future__ import annotations

import json
from pathlib import Path


def _write_realish_project(path: Path, *, index: int, video_clips: int = 30, audio_clips: int = 8) -> None:
    media_dir = path.parent / f"media_{index}"
    media_dir.mkdir(parents=True, exist_ok=True)
    video = media_dir / "source.mp4"
    audio = media_dir / "source.wav"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    video_rows = []
    for clip_index in range(video_clips):
        start = clip_index * 20_000
        video_rows.append(
            {
                "id": f"v{index}_{clip_index}",
                "source_path": str(video),
                "timeline_in_ms": start,
                "duration_ms": 20_000,
                "camera_id": f"cam_{clip_index % 3}",
            }
        )
    audio_rows = []
    for clip_index in range(audio_clips):
        start = clip_index * 75_000
        audio_rows.append(
            {
                "id": f"a{index}_{clip_index}",
                "source_path": str(audio),
                "timeline_in_ms": start,
                "duration_ms": 75_000,
            }
        )
    payload = {
        "name": f"Realish Project {index}",
        "duration_ms": 600_000,
        "media_pool": [
            {"id": f"mv{index}", "path": str(video), "kind": "video", "proxy_state": "ready"},
            {"id": f"ma{index}", "path": str(audio), "kind": "audio", "proxy_state": "ready"},
        ],
        "video_tracks": [{"id": 1, "clips": video_rows}],
        "audio_tracks": [{"id": 1, "clips": audio_rows}],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_nle_real_project_corpus_report_requires_registered_real_projects(tmp_path):
    from app.nle_real_corpus import build_nle_real_project_corpus_report

    report = build_nle_real_project_corpus_report(manifest_path=tmp_path / "missing_manifest.json")

    assert report["schema"] == "tigerstudio.nle.real_project_corpus.v1"
    assert report["claim_ready"] is False
    assert "manifest_exists" in report["blockers"]
    assert "real_project_count" in report["blockers"]


def test_nle_real_project_registration_rejects_generated_fixtures_by_default(tmp_path):
    from app.nle_real_corpus import register_real_project

    project = tmp_path / "synthetic_long_project.tgp"
    _write_realish_project(project, index=1)

    result = register_real_project(project, manifest_path=tmp_path / "manifest.json")

    assert result["ok"] is False
    assert result["reason"] == "generated_fixture_rejected"


def test_nle_real_project_corpus_can_be_claim_ready_with_three_real_projects(tmp_path):
    from app.nle_real_corpus import build_nle_real_project_corpus_report, register_real_project

    manifest = tmp_path / "manifest.json"
    for index in range(3):
        project = tmp_path / f"user_project_{index + 1}.tgp"
        _write_realish_project(project, index=index + 1)
        result = register_real_project(project, manifest_path=manifest, label=f"User Project {index + 1}")
        assert result["ok"] is True

    report = build_nle_real_project_corpus_report(manifest_path=manifest)

    assert report["claim_ready"] is True
    assert report["real_world_corpus"] is True
    assert report["summary"]["valid_project_count"] == 3
    assert report["summary"]["duration_ms"] >= 30 * 60_000
    assert report["summary"]["video_clips"] >= 90
    assert report["summary"]["audio_clips"] >= 20
    assert report["blockers"] == []
