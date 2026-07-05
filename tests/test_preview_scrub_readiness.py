from __future__ import annotations

import json


def _project(
    name: str,
    *,
    seek_avg: float,
    seek_p95: float,
    seek_max: float = 70.0,
    playback_avg: float = 5.0,
    playback_p95: float = 8.0,
    summary: dict | None = None,
    duration_ms: int = 10_000,
) -> dict:
    summary = dict(summary or {"video_clips": 1})
    return {
        "project": name,
        "ok": True,
        "duration_ms": duration_ms,
        "summary": summary,
        "frame_summary": {"count": 8, "avg_ms": seek_avg, "p95_ms": seek_p95, "max_ms": seek_max},
        "playback_frame_summary": {
            "count": 18,
            "avg_ms": playback_avg,
            "p95_ms": playback_p95,
            "max_ms": max(playback_p95, playback_avg),
        },
        "stage_summary_by_context": {
            "seek": [
                {"label": "preview.seek.render", "count": 8, "avg_ms": seek_avg, "p95_ms": seek_p95, "max_ms": seek_max},
                {"label": "preview.stage.decode", "count": 8, "avg_ms": seek_avg - 5, "p95_ms": seek_p95 - 8, "max_ms": seek_max - 10},
            ],
            "playback": [
                {
                    "label": "preview.tick.render",
                    "count": 18,
                    "avg_ms": playback_avg,
                    "p95_ms": playback_p95,
                    "max_ms": max(playback_p95, playback_avg),
                }
            ],
        },
    }


def test_preview_scrub_readiness_separates_current_and_release_claims():
    from app.preview_scrub_readiness import build_preview_scrub_readiness_report

    perf = {
        "ok": True,
        "preview_render": [
            _project("basic.tgp", seek_avg=12, seek_p95=24),
            _project(
                "mask.tgp",
                seek_avg=24,
                seek_p95=45,
                summary={"video_clips": 1, "clip_filters": 1, "tracked_masks": 1},
            ),
            _project("nested.tgp", seek_avg=18, seek_p95=34, summary={"video_clips": 2, "nested_video_clips": 1}),
            _project("actor.tgp", seek_avg=26, seek_p95=50, summary={"video_clips": 1, "spine_tracks": 1, "live2d_tracks": 1}),
            _project("audio.tgp", seek_avg=20, seek_p95=38, summary={"video_clips": 1, "audio_tracks": 2, "audio_clips": 2}),
            _project("long.tgp", seek_avg=16, seek_p95=30, summary={"video_clips": 80}, duration_ms=600_000),
        ],
    }

    report = build_preview_scrub_readiness_report(perf)

    assert report["ok"] is True
    assert report["current_corpus_scrub_ready"] is True
    assert report["release_scrub_claim_ready"] is False
    assert report["coverage"]["hires_4k"] is False
    assert report["summary"]["missing_release_coverage"] == ["hires_4k"]
    assert "release_coverage_missing" in report["release_blockers"]


def test_preview_scrub_readiness_blocks_slow_seek_p95():
    from app.preview_scrub_readiness import build_preview_scrub_readiness_report

    report = build_preview_scrub_readiness_report(
        {
            "preview_render": [
                _project("slow_4k.tgp", seek_avg=55, seek_p95=110, seek_max=140, summary={"video_clips": 1}),
            ]
        }
    )

    assert report["ok"] is False
    assert report["current_corpus_scrub_ready"] is False
    assert "scrub_blockers_present" in report["release_blockers"]
    assert report["projects"][0]["blockers"] == ["scrub_p95_above_target", "scrub_max_stutter"]


def test_preview_scrub_readiness_keeps_tiny_p95_overage_as_warning():
    from app.preview_scrub_readiness import build_preview_scrub_readiness_report

    report = build_preview_scrub_readiness_report(
        {
            "preview_render": [
                _project("basic_4k.tgp", seek_avg=30, seek_p95=66.4, seek_max=90, summary={"video_clips": 1}),
            ]
        }
    )

    assert report["ok"] is True
    assert report["current_corpus_scrub_ready"] is True
    assert report["projects"][0]["blockers"] == []
    assert "scrub_p95_near_target" in report["projects"][0]["warnings"]


def test_preview_scrub_readiness_tool_writes_report(tmp_path, monkeypatch):
    from tools import qa_preview_scrub_readiness

    perf_path = tmp_path / "preview_perf.json"
    out = tmp_path / "scrub.json"
    perf_path.write_text(
        json.dumps({"preview_render": [_project("basic_4k.tgp", seek_avg=12, seek_p95=24)]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["qa_preview_scrub_readiness.py", "--perf-report", str(perf_path), "--out", str(out)],
    )

    assert qa_preview_scrub_readiness.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["current_corpus_scrub_ready"] is True


def test_preview_scrub_readiness_tool_auto_hires_reruns_missing_4k(tmp_path, monkeypatch):
    from tools import qa_preview_scrub_readiness

    perf_path = tmp_path / "preview_perf.json"
    hires_path = tmp_path / "preview_perf_hires.json"
    out = tmp_path / "scrub.json"
    perf_path.write_text(
        json.dumps({"preview_render": [_project("basic.tgp", seek_avg=12, seek_p95=24)]}, ensure_ascii=False),
        encoding="utf-8",
    )

    calls = []

    def fake_run_hires_preview_perf(*, manifest, out, clean, render_samples):
        calls.append(
            {
                "manifest": str(manifest),
                "out": str(out),
                "clean": clean,
                "render_samples": render_samples,
            }
        )
        payload = {
            "preview_render": [
                _project("basic.tgp", seek_avg=12, seek_p95=24),
                _project("basic_4k.tgp", seek_avg=18, seek_p95=31),
            ]
        }
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        return payload

    monkeypatch.setattr(qa_preview_scrub_readiness, "_run_hires_preview_perf", fake_run_hires_preview_perf)
    monkeypatch.setattr(
        "sys.argv",
        [
            "qa_preview_scrub_readiness.py",
            "--perf-report",
            str(perf_path),
            "--out",
            str(out),
            "--auto-hires",
            "--hires-perf-report",
            str(hires_path),
            "--render-samples",
            "3",
        ],
    )

    assert qa_preview_scrub_readiness.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert calls and calls[0]["render_samples"] == 3
    assert report["auto_hires"]["ran"] is True
    assert report["coverage"]["hires_4k"] is True


def test_hires_preview_perf_proxy_option_creates_sibling_proxy(tmp_path, monkeypatch):
    from tools import qa_preview_perf

    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    calls = []

    def fake_run_quiet(cmd):
        calls.append(cmd)
        proxy = tmp_path / "proxies" / "source_proxy.mp4"
        proxy.parent.mkdir(exist_ok=True)
        proxy.write_bytes(b"proxy")

    monkeypatch.setattr(qa_preview_perf, "_run_quiet", fake_run_quiet)

    proxy = qa_preview_perf._make_preview_proxy(source, ffmpeg_path="ffmpeg", height=540)

    assert proxy == tmp_path / "proxies" / "source_proxy.mp4"
    assert proxy.exists()
    assert calls and "-vf" in calls[0]
    assert "scale=-2:540" in calls[0]
