from __future__ import annotations


def test_project_qa_baseline_comparison_flags_asset_and_export_regressions():
    from tools.qa_project_audit import compare_project_qa_reports

    baseline = {
        "projects": [{
            "project": "E:/qa/shared.tgp",
            "ok": True,
            "missing": {},
            "actor_asset_summary": {"failed": 0},
            "export_risks": [{
                "area": "preview/export CPU fallback",
                "severity": "medium",
                "count": 1,
            }],
        }],
        "synthetic_export_parity": {"ok": True},
    }
    current = {
        "projects": [{
            "project": "E:/qa/shared.tgp",
            "ok": False,
            "missing": {
                "video": ["E:/missing/clip.mp4"],
                "spine": ["E:/missing/actor.skel"],
            },
            "actor_asset_summary": {"failed": 2},
            "export_risks": [{
                "area": "preview/export CPU fallback",
                "severity": "high",
                "count": 3,
                "reason": "More CPU baking paths are active.",
            }, {
                "area": "Live2D/Spine actor baking",
                "severity": "high",
                "count": 1,
                "failed_assets": 2,
            }],
        }],
        "synthetic_export_parity": {"ok": False},
    }

    result = compare_project_qa_reports(current, baseline)

    assert result["ok"] is False
    kinds = {row["kind"] for row in result["regressions"]}
    assert "project_status" in kinds
    assert "missing_media" in kinds
    assert "actor_assets" in kinds
    assert "export_risk" in kinds
    assert "synthetic_export_parity" in kinds
    missing = next(row for row in result["regressions"] if row["kind"] == "missing_media")
    assert missing["missing_by_kind"] == {"spine": 1, "video": 1}


def test_project_qa_baseline_comparison_delegates_preview_regressions():
    from tools.qa_project_audit import compare_project_qa_reports

    baseline = {
        "projects": [
            {
                "project": "E:/qa/shared.tgp",
                "ok": True,
                "missing": {},
                "actor_asset_summary": {"failed": 0},
                "export_risks": [],
                "preview_render": {
                    "project": "E:/qa/shared.tgp",
                    "frame_summary": {"avg_ms": 20.0, "p95_ms": 25.0, "max_ms": 30.0},
                    "stage_summary": [{
                        "label": "preview.stage.decode",
                        "avg_ms": 10.0,
                        "p95_ms": 12.0,
                    }],
                },
            },
            {
                "project": "E:/qa/missing_now.tgp",
                "ok": True,
                "missing": {},
                "actor_asset_summary": {"failed": 0},
                "export_risks": [],
            },
        ],
    }
    current = {
        "projects": [
            {
                "project": "E:/qa/shared.tgp",
                "ok": True,
                "missing": {},
                "actor_asset_summary": {"failed": 0},
                "export_risks": [],
                "preview_render": {
                    "project": "E:/qa/shared.tgp",
                    "frame_summary": {"avg_ms": 34.0, "p95_ms": 50.0, "max_ms": 70.0},
                    "stage_summary": [{
                        "label": "preview.stage.decode",
                        "avg_ms": 20.0,
                        "p95_ms": 30.0,
                    }],
                },
            },
            {
                "project": "E:/qa/new_now.tgp",
                "ok": True,
                "missing": {},
                "actor_asset_summary": {"failed": 0},
                "export_risks": [],
            },
        ],
    }

    result = compare_project_qa_reports(current, baseline)

    assert result["ok"] is False
    assert result["summary"]["regressions"] == 0
    assert result["summary"]["preview_regressions"] >= 1
    assert result["new_projects"] == ["new_now.tgp"]
    assert result["missing_projects"] == ["missing_now.tgp"]
    preview = result["preview_performance"]
    assert preview["ok"] is False
    assert any(
        row.get("label") == "preview.stage.decode"
        for row in preview["regressions"]
    )
