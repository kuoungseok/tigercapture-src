from __future__ import annotations

import subprocess


def test_actor_render_qa_combines_compatibility_and_render_failures(tmp_path):
    from tools.actor_render_qa import build_actor_render_qa_report

    def compat_builder(roots, **kwargs):
        return {
            "ok": True,
            "roots": [str(root) for root in roots],
            "summary": {"total": 3, "ok": 3, "failed": 0},
            "rows": [],
        }

    def spine_candidates(root):
        return [root / "hero.skel", root / "blank.skel"]

    def spine_runner(path, width, height):
        return {
            "path": str(path),
            "status": "pass" if path.name == "hero.skel" else "blank",
            "size": [width, height],
        }

    def live2d_discoverer(root):
        return [root / "model.model3.json"], [root / "raw.bundle"]

    def live2d_runner(path, width, height, timeout):
        return {
            "source": str(path),
            "runtime": str(path),
            "status": "pass",
            "size": [width, height],
            "timeout": timeout,
        }

    report = build_actor_render_qa_report(
        [tmp_path],
        compat_builder=compat_builder,
        spine_candidate_finder=spine_candidates,
        spine_runner=spine_runner,
        live2d_discoverer=live2d_discoverer,
        live2d_runner=live2d_runner,
        width=640,
        height=360,
        live2d_width=320,
        live2d_height=180,
        live2d_timeout=12,
    )

    assert report["ok"] is False
    assert report["summary"]["compatibility"]["failed"] == 0
    assert report["summary"]["render"]["failed"] == 1
    assert report["summary"]["render"]["by_kind"]["spine"] == {"blank": 1, "pass": 1}
    assert report["render"]["live2d"]["bundle_count"] == 1
    assert report["summary"]["render"]["top_failures"][0]["status"] == "blank"
    assert report["summary"]["render"]["top_failures"][0]["path"].endswith("blank.skel")
    assert "alpha pixels" in report["summary"]["render"]["top_failures"][0]["recommendation"]


def test_actor_render_qa_respects_global_render_limit_and_dedupes(tmp_path):
    from tools.actor_render_qa import build_actor_render_qa_report

    def compat_builder(roots, **kwargs):
        return {"ok": True, "summary": {}, "rows": []}

    first = tmp_path / "first.skel"
    second = tmp_path / "second.skel"

    def spine_candidates(root):
        return [first, first, second]

    calls = []

    def spine_runner(path, width, height):
        calls.append(path)
        return {"path": str(path), "status": "pass"}

    report = build_actor_render_qa_report(
        [tmp_path],
        compat_builder=compat_builder,
        spine_candidate_finder=spine_candidates,
        spine_runner=spine_runner,
        render_live2d=False,
        render_limit=1,
    )

    assert report["ok"] is True
    assert calls == [first]
    assert report["render"]["spine"]["total"] == 1


def test_actor_render_qa_records_live2d_timeout(tmp_path):
    from tools.actor_render_qa import build_actor_render_qa_report

    model = tmp_path / "slow.model3.json"

    def compat_builder(roots, **kwargs):
        return {"ok": True, "summary": {}, "rows": []}

    def live2d_discoverer(root):
        return [model], []

    def live2d_runner(path, width, height, timeout):
        raise subprocess.TimeoutExpired(["python", "-c", "..."], timeout, output="booting")

    report = build_actor_render_qa_report(
        [tmp_path],
        compat_builder=compat_builder,
        render_spine=False,
        live2d_discoverer=live2d_discoverer,
        live2d_runner=live2d_runner,
        live2d_timeout=7,
    )

    assert report["ok"] is False
    assert report["render"]["live2d"]["counts"] == {"timeout": 1}
    failure = report["summary"]["render"]["top_failures"][0]
    assert failure["status"] == "timeout"
    assert failure["path"] == str(model)
    assert "larger timeout" in failure["recommendation"]


def test_actor_render_qa_baseline_comparison_flags_regressions():
    from tools.actor_render_qa import compare_actor_render_qa_reports

    baseline = {
        "compatibility": {
            "rows": [{
                "kind": "live2d",
                "path": "models/hero.model3.json",
                "ok": True,
                "severity": "ok",
                "issue_codes": [],
            }]
        },
        "render": {
            "spine": {
                "results": [{
                    "path": "models/hero.skel",
                    "status": "pass",
                }]
            }
        },
    }
    current = {
        "compatibility": {
            "rows": [{
                "kind": "live2d",
                "path": "models/hero.model3.json",
                "ok": False,
                "severity": "high",
                "issue_codes": ["live2d_dependency_missing"],
                "recommendation": "Restore required model3 dependencies.",
            }]
        },
        "render": {
            "spine": {
                "results": [{
                    "path": "models/hero.skel",
                    "status": "blank",
                    "error": "no alpha pixels",
                }]
            }
        },
    }

    comparison = compare_actor_render_qa_reports(current, baseline)

    assert comparison["ok"] is False
    assert comparison["summary"]["regressions"] == 2
    assert {row["area"] for row in comparison["regressions"]} == {
        "compatibility",
        "render",
    }
    compat = next(row for row in comparison["regressions"] if row["area"] == "compatibility")
    render = next(row for row in comparison["regressions"] if row["area"] == "render")
    assert compat["after"]["issue_codes"] == ["live2d_dependency_missing"]
    assert render["before"]["status"] == "pass"
    assert render["after"]["status"] == "blank"
    assert "alpha pixels" in render["recommendation"]


def test_actor_render_qa_baseline_comparison_tracks_improvements_and_new_models():
    from tools.actor_render_qa import compare_actor_render_qa_reports

    baseline = {
        "compatibility": {
            "rows": [{
                "kind": "spine",
                "path": "models/old.skel",
                "ok": False,
                "severity": "high",
            }]
        },
        "render": {
            "live2d": {
                "results": [{
                    "source": "models/slow.model3.json",
                    "status": "timeout",
                }]
            }
        },
    }
    current = {
        "compatibility": {
            "rows": [
                {
                    "kind": "spine",
                    "path": "models/old.skel",
                    "ok": True,
                    "severity": "ok",
                },
                {
                    "kind": "spine",
                    "path": "models/new.skel",
                    "ok": True,
                    "severity": "ok",
                },
            ]
        },
        "render": {
            "live2d": {
                "results": [{
                    "source": "models/slow.model3.json",
                    "status": "pass",
                }]
            }
        },
    }

    comparison = compare_actor_render_qa_reports(current, baseline)

    assert comparison["ok"] is True
    assert comparison["summary"]["regressions"] == 0
    assert comparison["summary"]["improvements"] == 2
    assert comparison["summary"]["new_models"] == 1
    assert comparison["new_models"][0]["path"] == "models/new.skel"


def test_actor_render_qa_build_report_attaches_baseline_comparison(tmp_path):
    from tools.actor_render_qa import build_actor_render_qa_report

    baseline = {
        "compatibility": {
            "rows": [{
                "kind": "spine",
                "path": str(tmp_path / "hero.skel"),
                "ok": True,
            }]
        },
        "render": {},
    }

    def compat_builder(roots, **kwargs):
        return {
            "ok": False,
            "summary": {},
            "rows": [{
                "kind": "spine",
                "path": str(tmp_path / "hero.skel"),
                "ok": False,
                "issue_codes": ["spine_texture_missing"],
            }],
        }

    report = build_actor_render_qa_report(
        [tmp_path],
        compat_builder=compat_builder,
        render=False,
        baseline_report=baseline,
    )

    assert report["ok"] is False
    assert report["baseline_comparison"]["summary"]["regressions"] == 1


def test_actor_render_qa_promotes_compatibility_risk_summary(tmp_path):
    from tools.actor_render_qa import build_actor_render_qa_report

    def compat_builder(roots, **kwargs):
        return {
            "ok": True,
            "summary": {
                "risk_counts": {"spine_weighted_mesh": 1},
                "feature_counts": {"weighted_mesh": 1},
                "stress_tiers": {"stress": 1},
                "top_risks": [{
                    "kind": "spine",
                    "model_name": "stress",
                    "risk_score": 12,
                    "risk_codes": ["spine_weighted_mesh"],
                }],
            },
            "rows": [{
                "kind": "spine",
                "path": str(tmp_path / "stress.json"),
                "ok": True,
                "risk_score": 12,
                "risk_severity": "medium",
                "risk_codes": ["spine_weighted_mesh"],
                "stress_tier": "stress",
            }],
        }

    report = build_actor_render_qa_report(
        [tmp_path],
        compat_builder=compat_builder,
        render=False,
    )

    risk = report["summary"]["compatibility_risk"]
    assert risk["risk_model_count"] == 1
    assert risk["medium_risk_models"] == 1
    assert risk["risk_counts"]["spine_weighted_mesh"] == 1
    assert risk["feature_counts"]["weighted_mesh"] == 1
    assert risk["stress_tiers"]["stress"] == 1
    assert risk["top_risks"][0]["model_name"] == "stress"


def test_actor_render_qa_top_risk_sampling_sweep_and_golden(tmp_path):
    from tools.actor_render_qa import build_actor_render_qa_report

    stress = tmp_path / "stress.json"
    ordinary = tmp_path / "ordinary.json"
    stress.write_text("{}", encoding="utf-8")
    ordinary.write_text("{}", encoding="utf-8")

    def compat_builder(roots, **kwargs):
        return {
            "ok": True,
            "summary": {
                "top_risks": [{
                    "kind": "spine",
                    "model_name": "stress",
                    "path": str(stress),
                    "risk_score": 12,
                }],
                "risk_counts": {"spine_weighted_mesh": 1},
                "feature_counts": {"weighted_mesh": 1},
                "stress_tiers": {"stress": 1},
            },
            "rows": [
                {
                    "kind": "spine",
                    "path": str(stress),
                    "ok": True,
                    "risk_score": 12,
                    "risk_severity": "medium",
                    "stress_tier": "stress",
                },
                {
                    "kind": "spine",
                    "path": str(ordinary),
                    "ok": True,
                    "risk_score": 1,
                    "risk_severity": "low",
                    "stress_tier": "standard",
                },
            ],
        }

    calls = []

    def runner(path, width, height):
        calls.append(path)
        return {"path": str(path), "status": "pass"}

    def sweep_runner(path, width, height, *, samples):
        return {
            "path": str(path),
            "status": "pass",
            "sample_count": samples,
            "blank_frames": 0,
        }

    golden_calls = []

    def golden_evaluator(**kwargs):
        golden_calls.append(kwargs["path"])
        return {
            "status": "pass",
            "baseline": str(kwargs["golden_dir"] / "stress.png"),
            "diff": {"score": 0.0},
        }

    report = build_actor_render_qa_report(
        [tmp_path],
        compat_builder=compat_builder,
        render_top_risks=True,
        top_risk_limit=1,
        animation_sweep=True,
        sweep_samples=6,
        render_live2d=False,
        spine_runner=runner,
        spine_sweep_runner=sweep_runner,
        golden_dir=tmp_path / "golden",
        golden_evaluator=golden_evaluator,
    )

    assert report["ok"] is True
    assert calls == [stress]
    assert golden_calls == [stress]
    result = report["render"]["spine"]["results"][0]
    assert result["path"] == str(stress)
    assert result["animation_sweep"]["sample_count"] == 6
    assert result["golden"]["status"] == "pass"
    assert report["summary"]["golden"]["counts"]["pass"] == 1


def test_actor_render_qa_known_render_failure_quarantines_blank(tmp_path):
    from tools.actor_render_qa import build_actor_render_qa_report

    model = tmp_path / "blank.skel"
    model.write_bytes(b"skel")

    def compat_builder(roots, **kwargs):
        return {"ok": True, "summary": {}, "rows": []}

    def spine_candidates(root):
        return [model]

    def runner(path, width, height):
        return {"path": str(path), "status": "blank", "error": "no alpha pixels"}

    report = build_actor_render_qa_report(
        [tmp_path],
        compat_builder=compat_builder,
        spine_candidate_finder=spine_candidates,
        spine_runner=runner,
        render_live2d=False,
        known_failures=[{
            "id": "blank-spine-fixture",
            "area": "render",
            "kind": "spine",
            "path_suffix": "blank.skel",
            "status": "blank",
            "reason": "fixture intentionally renders blank",
        }],
    )

    result = report["render"]["spine"]["results"][0]
    assert report["ok"] is True
    assert result["quarantined"] is True
    assert result["known_failure"]["id"] == "blank-spine-fixture"
    assert report["summary"]["render"]["failed"] == 0
    assert report["summary"]["render"]["quarantined"] == 1


def test_actor_render_qa_treats_animation_sweep_blank_as_failure(tmp_path):
    from tools.actor_render_qa import build_actor_render_qa_report

    model = tmp_path / "hero.skel"
    model.write_bytes(b"skel")

    def compat_builder(roots, **kwargs):
        return {"ok": True, "summary": {}, "rows": []}

    def spine_candidates(root):
        return [model]

    def runner(path, width, height):
        return {"path": str(path), "status": "pass"}

    def sweep_runner(path, width, height, *, samples):
        return {
            "path": str(path),
            "status": "blank",
            "sample_count": samples,
            "blank_frames": 1,
        }

    report = build_actor_render_qa_report(
        [tmp_path],
        compat_builder=compat_builder,
        spine_candidate_finder=spine_candidates,
        spine_runner=runner,
        spine_sweep_runner=sweep_runner,
        render_live2d=False,
        animation_sweep=True,
        sweep_samples=4,
    )

    result = report["render"]["spine"]["results"][0]
    assert report["ok"] is False
    assert result["status"] == "pass"
    assert result["failure_category"] == "animation_sweep_blank"
    assert report["summary"]["render"]["failed"] == 1
    assert report["summary"]["render"]["failure_categories"]["animation_sweep_blank"] == 1
    assert "animation sweep" in report["summary"]["render"]["top_failures"][0]["recommendation"]


def test_actor_corpus_status_tracks_advisory_coverage_and_failures():
    from tools.actor_corpus_regression import actor_corpus_status

    report = {
        "ok": False,
        "summary": {
            "compatibility": {
                "total": 2,
                "failed": 0,
                "quarantined": 1,
                "by_kind": {
                    "spine": {"total": 2},
                    "live2d": {"total": 0},
                },
                "stress_tiers": {"stress": 1},
                "risk_counts": {"spine_weighted_mesh": 1},
            },
            "compatibility_risk": {"risk_model_count": 1},
            "render": {
                "failed": 1,
                "quarantined": 0,
                "failure_categories": {"blank_alpha": 1},
            },
            "golden": {"enabled": True, "ok": True, "counts": {"pass": 1}},
        },
    }

    status = actor_corpus_status(
        report,
        coverage_targets={
            "enforce": False,
            "min_total": 3,
            "min_live2d": 1,
            "required_risk_codes": ["spine_weighted_mesh", "live2d_many_motions"],
        },
    )

    assert status["ok"] is False
    assert status["coverage"]["spine"] == 2
    assert status["coverage"]["render_failure_categories"] == {"blank_alpha": 1}
    assert any(issue["code"] == "render_failures" for issue in status["issues"])
    assert any(
        issue["code"] == "missing_risk_code"
        and issue["risk_code"] == "live2d_many_motions"
        for issue in status["issues"]
    )
    assert status["coverage"]["model_status_counts"] == {}


def test_actor_corpus_status_includes_per_model_rows():
    from tools.actor_corpus_regression import actor_corpus_status

    report = {
        "ok": True,
        "compatibility": {
            "rows": [{
                "kind": "spine",
                "path": "models/hero.json",
                "ok": True,
                "risk_score": 6,
                "stress_tier": "watch",
                "risk_codes": ["spine_weighted_mesh"],
            }]
        },
        "render": {
            "spine": {
                "results": [{
                    "path": "models/hero.json",
                    "status": "pass",
                    "quality": {"ok": True, "category": "pass"},
                    "golden": {"status": "pass"},
                }]
            }
        },
        "summary": {
            "compatibility": {
                "total": 1,
                "failed": 0,
                "by_kind": {"spine": {"total": 1}},
            },
            "compatibility_risk": {"risk_model_count": 1},
            "render": {"failed": 0, "quarantined": 0, "failure_categories": {}},
            "golden": {"enabled": True, "ok": True, "counts": {"pass": 1}},
        },
    }

    status = actor_corpus_status(report)

    assert status["coverage"]["model_status_counts"] == {"risk": 1}
    assert status["models"][0]["path"] == "models/hero.json"
    assert status["models"][0]["status"] == "risk"
    assert status["models"][0]["golden_status"] == "pass"


def test_actor_qa_status_matches_paths_and_badges():
    from app.actor_qa_status import actor_status_badge, actor_status_for_path, actor_status_tooltip

    status = {
        "models": [{
            "kind": "spine",
            "path": "resources/spine/hero.json",
            "status": "quarantined",
            "stress_tier": "blocked",
            "known_failure": {"id": "fixture"},
        }]
    }

    row = actor_status_for_path(status, "E:/repo/resources/spine/hero.json")

    assert row["status"] == "quarantined"
    assert actor_status_badge(row) == ("Q", "#6d5fd1")
    assert "known=fixture" in actor_status_tooltip(row)


def test_actor_golden_manager_status_and_promote(tmp_path):
    from tools.actor_golden_manager import actor_golden_status, promote_actuals

    golden = tmp_path / "golden"
    actual = golden / "_actual"
    actual.mkdir(parents=True)
    (actual / "hero.png").write_bytes(b"actual")

    status = actor_golden_status(golden)
    assert status["baseline_count"] == 0
    assert status["actual_count"] == 1
    assert status["pending_promotion_count"] == 1
    assert status["needs_promotion"] is True
    assert status["missing_baselines"] == ["hero.png"]

    promoted = promote_actuals(golden)
    assert promoted["promoted"] == 1
    assert (golden / "hero.png").read_bytes() == b"actual"
    status = actor_golden_status(golden)
    assert status["matching_count"] == 1
    assert status["pending_promotion_count"] == 0
    assert status["needs_promotion"] is False


def test_live2d_metadata_coverage_and_motion_variants(tmp_path):
    from tools.test_live2d_resources import (
        live2d_expression_variants,
        live2d_metadata_coverage,
        live2d_motion_variants,
        live2d_render_variants,
    )

    model = tmp_path / "hero.model3.json"
    model.write_text(
        """
        {
          "FileReferences": {
            "Motions": {
              "Idle": [{"File": "idle_0.motion3.json"}, {"File": "idle_1.motion3.json"}],
              "Tap": [{"File": "tap_0.motion3.json"}]
            },
            "Expressions": [{"Name": "Smile", "File": "smile.exp3.json"}],
            "Physics": "hero.physics3.json",
            "Pose": "hero.pose3.json"
          },
          "HitAreas": [{"Id": "Head"}]
        }
        """,
        encoding="utf-8",
    )

    variants = live2d_motion_variants(model, max_motions=2)
    coverage = live2d_metadata_coverage(model)

    assert variants == [
        {"motion_group": "Idle", "motion_idx": 0, "label": "idle_0.motion3.json"},
        {"motion_group": "Idle", "motion_idx": 1, "label": "idle_1.motion3.json"},
    ]
    assert coverage["motion_count"] == 3
    assert coverage["expression_count"] == 1
    assert coverage["physics"] is True
    assert coverage["pose"] is True
    assert coverage["hit_area_count"] == 1
    assert live2d_expression_variants(model) == [
        {"expression_id": "Smile", "label": "smile.exp3.json"}
    ]
    render_variants = live2d_render_variants(model, max_motions=1, max_expressions=1)
    assert render_variants[0]["variant_kind"] == "motion"
    assert render_variants[1]["variant_kind"] == "expression"
    assert render_variants[1]["expression_id"] == "Smile"


def test_spine_skin_combination_helpers_merge_skins():
    from types import SimpleNamespace

    from tools.test_spine_resources import _merge_skin_combo, _skin_combinations, _skin_slot_summary

    skel = SimpleNamespace(
        slots=[
            SimpleNamespace(name="body", attachment="base"),
            SimpleNamespace(name="hair", attachment="blue"),
        ],
        skins={
            "default": {"body": {"base": object()}},
            "hair/blue": {"hair": {"blue": object()}},
            "clothes/dress": {"body": {"dress": object()}},
        },
    )

    combos = _skin_combinations(["default", "hair/blue", "clothes/dress"], max_combinations=4)
    combo_name = _merge_skin_combo(skel, combos[-1])
    summary = _skin_slot_summary(skel, combo_name)

    assert combos[-1] == ["hair/blue", "clothes/dress"]
    assert combo_name in skel.skins
    assert summary["attachment_count"] == 3


def test_live2d_run_one_returns_timeout_payload(monkeypatch, tmp_path):
    from tools import test_live2d_resources

    model = tmp_path / "slow.model3.json"
    model.write_text("{}", encoding="utf-8")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout"), output=b"starting")

    monkeypatch.setattr(test_live2d_resources.subprocess, "run", fake_run)

    result = test_live2d_resources.run_one(model, 320, 240, 3)

    assert result["status"] == "timeout"
    assert result["source"] == str(model)
    assert "3s" in result["error"]
    assert result["stdout_tail"] == "starting"
