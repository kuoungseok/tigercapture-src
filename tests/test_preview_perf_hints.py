from __future__ import annotations


def test_preview_bottleneck_hints_names_native_candidates():
    from tools.qa_preview_perf import _preview_bottleneck_hints

    hints = _preview_bottleneck_hints([
        {
            "project": "actors.tgp",
            "frame_summary": {"avg_ms": 70.0},
            "stage_summary": [
                {
                    "label": "preview.stage.spine_overlay",
                    "avg_ms": 42.0,
                    "p95_ms": 95.0,
                },
                {
                    "label": "preview.stage.qimage",
                    "avg_ms": 0.3,
                    "p95_ms": 0.5,
                },
            ],
        }
    ])

    assert hints
    assert hints[0]["label"] == "preview.stage.spine_overlay"
    assert "Spine" in hints[0]["candidate"]


def test_preview_sample_positions_include_actor_active_midpoint():
    from tools.qa_preview_perf import _sample_positions_for_project

    doc = {
        "video_tracks": [{
            "clips": [{
                "timeline_in_ms": 0,
                "source_in_ms": 0,
                "source_out_ms": 5000,
            }],
        }],
        "spine_actor_tracks": [{
            "clips": [{
                "start_ms": 1200,
                "duration_ms": 2000,
            }],
        }],
    }

    positions = _sample_positions_for_project(doc, 5000, 2)

    assert 0 in positions
    assert 4999 in positions
    assert 2200 in positions


def test_preview_engine_status_reports_qimage_mode(monkeypatch):
    from app.preview_engine_status import preview_engine_status

    monkeypatch.setenv("TIGERCAPTURE_PREVIEW_QIMAGE", "0")
    monkeypatch.delenv("TIGERCAPTURE_SHADER_CLIP_FX", raising=False)

    status = preview_engine_status()

    assert status["qimage_mode"] == "0"
    assert status["shader_clip_fx"] == "1"
    assert status["spine_zero_readback"] == "1"
    assert status["spine_direct_with_live2d"] == "1"
    assert status["spine_preview_scale"] == "0.5"
    assert status["spine_playback_preview_scale"] == "0.375"
    assert status["spine_complex_preview_scale"] == "0.25"
    assert status["spine_complex_preview_fps"] == "12"
    assert status["spine_complex_threshold"] == "900"


def test_preview_perf_qa_defaults_to_gpu_preview_mode(monkeypatch):
    from tools.qa_preview_perf import _qa_preview_gpu_mode_enabled

    monkeypatch.delenv("TIGERCAPTURE_QA_PREVIEW_MODE", raising=False)
    assert _qa_preview_gpu_mode_enabled() is True

    monkeypatch.setenv("TIGERCAPTURE_QA_PREVIEW_MODE", "qimage")
    assert _qa_preview_gpu_mode_enabled() is False


def test_preview_bottleneck_hints_names_spine_state_candidate():
    from tools.qa_preview_perf import _preview_bottleneck_hints

    hints = _preview_bottleneck_hints([
        {
            "project": "actors.tgp",
            "frame_summary": {"avg_ms": 40.0},
            "stage_summary": [{
                "label": "preview.stage.spine_overlay_state",
                "avg_ms": 12.0,
                "p95_ms": 30.0,
            }],
        }
    ])

    assert hints
    assert "Spine" in hints[0]["candidate"]


def test_preview_bottleneck_hints_prefers_playback_context_when_available():
    from tools.qa_preview_perf import _preview_bottleneck_hints

    hints = _preview_bottleneck_hints([
        {
            "project": "seek-heavy.tgp",
            "frame_summary": {"avg_ms": 80.0},
            "playback_frame_summary": {"avg_ms": 9.0},
            "stage_summary": [{
                "label": "preview.stage.decode",
                "avg_ms": 50.0,
                "p95_ms": 90.0,
            }],
            "stage_summary_by_context": {
                "seek": [{
                    "label": "preview.stage.decode",
                    "avg_ms": 50.0,
                    "p95_ms": 90.0,
                }],
                "playback": [{
                    "label": "preview.stage.decode",
                    "avg_ms": 4.0,
                    "p95_ms": 8.0,
                }],
            },
        }
    ])

    assert hints == []


def test_preview_bottleneck_hints_names_shader_clip_fx_candidate():
    from tools.qa_preview_perf import _preview_bottleneck_hints

    hints = _preview_bottleneck_hints([
        {
            "project": "mask.tgp",
            "frame_summary": {"avg_ms": 40.0},
            "stage_summary": [{
                "label": "preview.stage.shader_clip_fx_state",
                "avg_ms": 8.0,
                "p95_ms": 16.0,
            }],
        }
    ])

    assert hints
    assert "shader" in hints[0]["candidate"].lower()


def test_preview_perf_baseline_comparison_flags_stage_regression():
    from tools.qa_preview_perf import compare_preview_perf_reports

    baseline = {
        "batch_media_probe_elapsed_ms": 40.0,
        "timeline_thumbnails": [{
            "path": "E:/media/clip.mp4",
            "elapsed_ms": 100.0,
        }],
        "preview_render": [{
            "project": "E:/projects/actors.tgp",
            "frame_summary": {"avg_ms": 20.0, "p95_ms": 25.0, "max_ms": 30.0},
            "stage_summary": [{
                "label": "preview.stage.decode",
                "avg_ms": 10.0,
                "p95_ms": 14.0,
            }],
        }],
    }
    current = {
        "batch_media_probe_elapsed_ms": 52.0,
        "timeline_thumbnails": [{
            "path": "E:/media/clip.mp4",
            "elapsed_ms": 140.0,
        }],
        "preview_render": [{
            "project": "E:/projects/actors.tgp",
            "frame_summary": {"avg_ms": 32.0, "p95_ms": 45.0, "max_ms": 60.0},
            "stage_summary": [{
                "label": "preview.stage.decode",
                "avg_ms": 19.0,
                "p95_ms": 30.0,
            }],
        }],
    }

    result = compare_preview_perf_reports(
        current,
        baseline,
        abs_threshold_ms=5.0,
        rel_threshold=0.25,
    )

    assert result["ok"] is False
    assert result["summary"]["regressions"] >= 4
    stage_rows = [
        row for row in result["regressions"]
        if row["kind"] == "preview_stage"
    ]
    assert stage_rows
    assert stage_rows[0]["label"] == "preview.stage.decode"
    assert "decode" in stage_rows[0]["candidate"].lower()


def test_preview_perf_baseline_comparison_tracks_improvements_and_project_set():
    from tools.qa_preview_perf import compare_preview_perf_reports

    baseline = {
        "batch_media_probe_elapsed_ms": 40.0,
        "preview_render": [
            {
                "project": "E:/projects/shared.tgp",
                "frame_summary": {"avg_ms": 40.0, "p95_ms": 80.0, "max_ms": 100.0},
                "stage_summary": [{
                    "label": "preview.stage.chroma_key",
                    "avg_ms": 24.0,
                    "p95_ms": 40.0,
                }],
            },
            {
                "project": "E:/projects/missing_now.tgp",
                "frame_summary": {"avg_ms": 20.0, "p95_ms": 30.0, "max_ms": 40.0},
                "stage_summary": [],
            },
        ],
    }
    current = {
        "batch_media_probe_elapsed_ms": 42.0,
        "preview_render": [
            {
                "project": "E:/projects/shared.tgp",
                "frame_summary": {"avg_ms": 28.0, "p95_ms": 50.0, "max_ms": 70.0},
                "stage_summary": [{
                    "label": "preview.stage.chroma_key",
                    "avg_ms": 12.0,
                    "p95_ms": 22.0,
                }],
            },
            {
                "project": "E:/projects/new_now.tgp",
                "frame_summary": {"avg_ms": 20.0, "p95_ms": 30.0, "max_ms": 40.0},
                "stage_summary": [],
            },
        ],
    }

    result = compare_preview_perf_reports(
        current,
        baseline,
        abs_threshold_ms=5.0,
        rel_threshold=0.25,
    )

    assert result["ok"] is True
    assert result["summary"]["regressions"] == 0
    assert result["summary"]["improvements"] >= 2
    assert result["new_projects"] == ["new_now.tgp"]
    assert result["missing_projects"] == ["missing_now.tgp"]


def test_preview_perf_baseline_comparison_keeps_refresh_render_advisory():
    from tools.qa_preview_perf import compare_preview_perf_reports

    baseline = {
        "preview_render": [{
            "project": "E:/projects/shared.tgp",
            "frame_summary": {"avg_ms": 20.0, "p95_ms": 25.0, "max_ms": 30.0},
            "stage_summary": [{
                "label": "preview.refresh.render",
                "avg_ms": 100.0,
                "p95_ms": 100.0,
            }],
        }],
    }
    current = {
        "preview_render": [{
            "project": "E:/projects/shared.tgp",
            "frame_summary": {"avg_ms": 20.0, "p95_ms": 25.0, "max_ms": 30.0},
            "stage_summary": [{
                "label": "preview.refresh.render",
                "avg_ms": 400.0,
                "p95_ms": 400.0,
            }],
        }],
    }

    result = compare_preview_perf_reports(
        current,
        baseline,
        abs_threshold_ms=5.0,
        rel_threshold=0.25,
    )

    assert result["ok"] is True
    assert result["summary"]["regressions"] == 0
    assert result["summary"]["advisory_regressions"] == 2
    assert {
        row["advisory_reason"]
        for row in result["advisory_regressions"]
    } == {"warmup_or_project_refresh_sample"}


def test_preview_perf_baseline_comparison_keeps_p95_only_stage_spike_advisory():
    from tools.qa_preview_perf import compare_preview_perf_reports

    baseline = {
        "preview_render": [{
            "project": "E:/projects/mask.tgp",
            "frame_summary": {"avg_ms": 40.0, "p95_ms": 80.0, "max_ms": 100.0},
            "stage_summary": [{
                "label": "preview.stage.filter_chroma_batch",
                "avg_ms": 10.0,
                "p95_ms": 12.0,
            }],
        }],
    }
    current = {
        "preview_render": [{
            "project": "E:/projects/mask.tgp",
            "frame_summary": {"avg_ms": 40.0, "p95_ms": 80.0, "max_ms": 100.0},
            "stage_summary": [{
                "label": "preview.stage.filter_chroma_batch",
                "avg_ms": 7.0,
                "p95_ms": 19.5,
            }],
        }],
    }

    result = compare_preview_perf_reports(
        current,
        baseline,
        abs_threshold_ms=5.0,
        rel_threshold=0.25,
    )

    assert result["ok"] is True
    assert result["summary"]["regressions"] == 0
    assert result["summary"]["advisory_regressions"] == 1
    assert result["advisory_regressions"][0]["advisory_reason"] == (
        "p95_stage_spike_without_sustained_avg_regression"
    )


def test_preview_perf_baseline_comparison_keeps_sample_plan_stage_regression_advisory():
    from tools.qa_preview_perf import compare_preview_perf_reports

    baseline = {
        "preview_render": [{
            "project": "E:/projects/actors.tgp",
            "sample_count": 8,
            "frame_summary": {"avg_ms": 70.0, "p95_ms": 120.0, "max_ms": 130.0},
            "stage_summary": [{
                "label": "preview.stage.spine_overlay",
                "avg_ms": 40.0,
                "p95_ms": 90.0,
            }],
        }],
    }
    current = {
        "preview_render": [{
            "project": "E:/projects/actors.tgp",
            "sample_count": 15,
            "frame_summary": {"avg_ms": 65.0, "p95_ms": 100.0, "max_ms": 115.0},
            "stage_summary": [{
                "label": "preview.stage.spine_overlay",
                "avg_ms": 60.0,
                "p95_ms": 96.0,
            }],
        }],
    }

    result = compare_preview_perf_reports(
        current,
        baseline,
        abs_threshold_ms=5.0,
        rel_threshold=0.25,
    )

    assert result["ok"] is True
    assert result["summary"]["regressions"] == 0
    assert result["summary"]["advisory_regressions"] == 1
    assert result["advisory_regressions"][0]["advisory_reason"] == (
        "sample_plan_changed_stage_not_directly_comparable"
    )
