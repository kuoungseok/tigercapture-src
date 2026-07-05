from __future__ import annotations

import json
from pathlib import Path


def test_release_evidence_automation_writes_safe_scripts(tmp_path: Path):
    from app.release_evidence_automation import build_release_evidence_automation_report

    debug = tmp_path / "debugCapture"
    debug.mkdir()
    (debug / "final_product_readiness_qa.json").write_text(
        json.dumps({"score": 92, "release_ready": False}),
        encoding="utf-8",
    )
    (debug / "screenstudio_real_recording_corpus_qa.json").write_text(
        json.dumps({"summary": {"valid_files": 20, "interaction_ready": 0, "target_min": 20}}),
        encoding="utf-8",
    )
    (debug / "ai_edit_corpus_quality_qa.json").write_text(
        json.dumps({"summary": {"real_cases": 0, "min_real_cases": 20}}),
        encoding="utf-8",
    )
    (debug / "broadcast_release_readiness_qa.json").write_text(
        json.dumps({"commercial_ready": False, "summary": {"sale_blocking": 1}}),
        encoding="utf-8",
    )
    sprint = debug / "release_evidence_sprint"
    sidecars = sprint / "screenstudio_sidecar_templates"
    ai = sprint / "ai_edit_templates"
    sidecars.mkdir(parents=True)
    ai.mkdir()
    (debug / "release_evidence_sprint_qa.json").write_text(
        json.dumps({"out_dir": str(sprint)}),
        encoding="utf-8",
    )
    (sidecars / "slot.cursor.template.json").write_text(
        json.dumps(
            {
                "kind": "screenstudio_cursor_sidecar_template",
                "events": [{"t_ms": 0, "x_norm": 0.5, "y_norm": 0.5, "kind": "move"}],
            }
        ),
        encoding="utf-8",
    )
    (ai / "case.template.json").write_text(
        json.dumps(
            {
                "kind": "ai_edit_real_case_template",
                "manifest_case": {"prompt": "make a clean tutorial", "transcript_path": "real.srt"},
            }
        ),
        encoding="utf-8",
    )

    report = build_release_evidence_automation_report(tmp_path, write_files=True)

    assert report["ok"] is True
    assert report["automation_ready"] is True
    assert report["promotion_ready_now"] is True
    assert report["claim_unblocked_by_automation"] is False
    assert report["summary"]["sidecar_templates_filled"] == 1
    assert report["summary"]["ai_templates_filled"] == 1
    promote = Path(report["scripts"]["promote_filled_release_evidence"])
    refresh = Path(report["scripts"]["refresh_release_evidence_status"])
    assert promote.is_file()
    assert refresh.is_file()
    text = promote.read_text(encoding="utf-8-sig")
    assert "promote_screenstudio_sidecar_templates.py" in text
    assert "register_ai_edit_corpus_templates.py" in text
    assert "qa_final_product_readiness.py" in text
    assert "example template events" not in text


def test_release_evidence_automation_reports_unfilled_inputs(tmp_path: Path):
    from app.release_evidence_automation import build_release_evidence_automation_report

    debug = tmp_path / "debugCapture"
    sprint = debug / "release_evidence_sprint"
    (sprint / "screenstudio_sidecar_templates").mkdir(parents=True)
    (sprint / "ai_edit_templates").mkdir()
    (debug / "release_evidence_sprint_qa.json").write_text(
        json.dumps({"out_dir": str(sprint)}),
        encoding="utf-8",
    )
    (sprint / "screenstudio_sidecar_templates" / "empty.cursor.template.json").write_text(
        json.dumps({"kind": "screenstudio_cursor_sidecar_template", "events": []}),
        encoding="utf-8",
    )
    (sprint / "ai_edit_templates" / "empty.template.json").write_text(
        json.dumps({"kind": "ai_edit_real_case_template", "manifest_case": {"prompt": "", "transcript_path": ""}}),
        encoding="utf-8",
    )

    report = build_release_evidence_automation_report(tmp_path)

    assert report["ok"] is True
    assert report["promotion_ready_now"] is False
    assert "needs_filled_real_cursor_sidecar_templates_or_live_capture" in report["blockers"]
    assert "needs_filled_real_ai_case_templates" in report["blockers"]
