from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.release_evidence_sprint import (
    build_release_evidence_sprint,
    release_evidence_action_targets,
    release_evidence_next_ai_case_target,
    release_evidence_next_items,
    release_evidence_next_screenstudio_capture_target,
    release_evidence_progress,
)


ROOT = Path(__file__).resolve().parents[1]


def test_release_evidence_sprint_reports_both_blocking_evidence_streams(tmp_path: Path) -> None:
    report = build_release_evidence_sprint(
        ROOT,
        out_dir=tmp_path / "sprint",
        write_files=False,
        max_screenstudio=3,
        max_ai=3,
    )

    assert report["kind"] == "release_evidence_sprint"
    assert report["ok"] is True
    assert report["claim_unblocked_by_sprint"] is False
    assert "screenstudio_selected" in report["summary"]
    assert "ai_missing_real_cases" in report["summary"]
    assert report["screenstudio"]["selected_rows"] is not None
    assert report["ai"]["selected_rows"] is not None
    assert report["broadcast"]["selected_rows"] is not None
    assert report["progress"]["ready"] is False
    assert "screenstudio" in report["progress"]
    assert "ai" in report["progress"]
    assert "broadcast" in report["progress"]
    assert "work_queue" in report
    assert isinstance(report["work_queue"], list)


def test_release_evidence_sprint_can_defer_ai_collection(tmp_path: Path) -> None:
    report = build_release_evidence_sprint(
        ROOT,
        out_dir=tmp_path / "sprint",
        write_files=False,
        max_screenstudio=3,
        max_ai=0,
    )

    assert report["ai_deferred"] is True
    assert report["summary"]["ai_selected"] == 0
    assert report["summary"]["ai_missing_real_cases"] == 0
    assert report["ai"]["selected_rows"] == []
    assert report["progress"]["ai"]["deferred"] is True
    assert not any("real_ai_edit_cases" in blocker for blocker in report["progress"]["blockers"])


def test_release_evidence_sprint_writes_scripts_without_counted_sidecars(tmp_path: Path) -> None:
    out_dir = tmp_path / "sprint"
    report = build_release_evidence_sprint(
        ROOT,
        out_dir=out_dir,
        write_files=True,
        max_screenstudio=2,
        max_ai=2,
        capture_duration_ms=5000,
    )

    screen_script = Path(report["scripts"]["screenstudio_sidecar_capture"])
    ai_script = Path(report["scripts"]["ai_real_case_registration"])
    broadcast_script = Path(report["scripts"]["broadcast_platform_registration"])
    playbook = Path(report["playbook"])

    assert screen_script.exists()
    assert ai_script.exists()
    assert broadcast_script.exists()
    assert playbook.exists()
    assert "--capture-hotkeys" in screen_script.read_text(encoding="utf-8")
    assert "register_ai_edit_corpus_case.py" in ai_script.read_text(encoding="utf-8")
    assert "register_broadcast_platform_evidence.py" in broadcast_script.read_text(encoding="utf-8")
    assert not list(out_dir.rglob("*.cursor.json"))

    targets = release_evidence_action_targets(report, root=ROOT)
    assert targets["screenstudio_sidecar_capture"]["exists"] is True
    assert targets["screenstudio_sidecar_capture"]["kind"] == "powershell"
    assert targets["ai_real_case_registration"]["exists"] is True
    assert targets["broadcast_platform_registration"]["exists"] is True
    assert targets["playbook"]["exists"] is True
    assert targets["folder"]["exists"] is True


def test_release_evidence_progress_requires_real_interactions_and_cases() -> None:
    report = {
        "summary": {
            "screenstudio_selected": 20,
            "screenstudio_ready": 20,
            "ai_selected": 20,
            "ai_real_cases": 12,
        },
        "screenstudio": {
            "summary": {
                "target_min": 20,
                "cursor_sidecar_ready": 20,
                "interaction_ready": 7,
            }
        },
        "ai": {"summary": {"target_min": 20, "ready_real_cases": 12}},
        "broadcast": {"summary": {"target": 2, "ready": 1, "pending": 1}},
    }

    progress = release_evidence_progress(report)

    assert progress["screenstudio"]["sidecar_ready"] == 20
    assert progress["screenstudio"]["interaction_ready"] == 7
    assert progress["screenstudio"]["needed"] == 13
    assert progress["screenstudio"]["requirements"]["auto_zoom"]["needed"] == 20
    assert progress["ai"]["needed"] == 8
    assert progress["broadcast"]["needed"] == 1
    assert progress["ready"] is False


def test_release_evidence_next_items_prioritizes_real_cursor_sidecars() -> None:
    report = {
        "screenstudio": {
            "selected_rows": [
                {
                    "index": 1,
                    "slot_id": "screenstudio-real-01",
                    "path": "clip01.mp4",
                    "state": "needs_sidecar",
                    "missing_requirements": ["cursor_sidecar", "click", "drag", "hotkey", "auto_zoom"],
                    "sidecar_capture_command": "python tools/record_screenstudio_cursor_sidecar.py --video clip01.mp4",
                },
                {
                    "index": 2,
                    "slot_id": "screenstudio-real-02",
                    "path": "clip02.mp4",
                    "state": "needs_auto_zoom",
                    "missing_requirements": ["auto_zoom"],
                },
            ],
        },
        "ai": {
            "selected_rows": [
                {
                    "index": 1,
                    "case_id": "real_case_001",
                    "state": "needs_real_case",
                    "template_path": "template.json",
                }
            ],
        },
        "broadcast": {
            "selected_rows": [
                {
                    "check_id": "private_rtmp_ingest",
                    "label": "Private/unlisted RTMP ingest test",
                    "state": "needs_real_platform_evidence",
                    "ready": False,
                }
            ],
        },
    }

    queue = release_evidence_next_items(report, limit=4)

    assert queue[0]["kind"] == "screenstudio_interaction_evidence"
    assert queue[0]["slot_id"] == "screenstudio-real-01"
    assert "Cursor sidecar" in queue[0]["summary"]
    assert "real .cursor.json" in queue[0]["next_actions"][0]
    assert queue[1]["slot_id"] == "screenstudio-real-02"
    assert queue[2]["kind"] == "ai_real_edit_case"
    assert queue[3]["kind"] == "broadcast_platform_evidence"


def test_screenstudio_rows_prioritizes_required_twenty_slots() -> None:
    from app.release_evidence_sprint import _screenstudio_rows

    rows = [
        {"index": 1, "slot_id": "screenstudio-real-52", "missing_requirements": ["cursor_sidecar"]},
        {"index": 50, "slot_id": "screenstudio-real-02", "missing_requirements": ["cursor_sidecar"]},
        {"index": 2, "slot_id": "screenstudio-real-21", "missing_requirements": ["cursor_sidecar"]},
    ]

    selected = _screenstudio_rows({"rows": rows}, limit=2)

    assert [row["slot_id"] for row in selected] == ["screenstudio-real-02", "screenstudio-real-21"]


def test_release_evidence_next_screenstudio_capture_target_writes_one_slot_script(tmp_path: Path) -> None:
    report = {
        "out_dir": str(tmp_path / "sprint"),
        "screenstudio": {
            "selected_rows": [
                {
                    "index": 1,
                    "slot_id": "screenstudio-real-01",
                    "path": str(tmp_path / "clip01.mp4"),
                    "duration_ms": 12_000,
                    "frame_w": 1280,
                    "frame_h": 720,
                    "state": "needs_sidecar",
                    "missing_requirements": ["cursor_sidecar", "click", "drag", "hotkey", "auto_zoom"],
                }
            ],
        },
        "ai": {"selected_rows": []},
    }

    target = release_evidence_next_screenstudio_capture_target(report, root=ROOT, write_file=True)
    script = Path(target["path"])
    text = script.read_text(encoding="utf-8-sig")

    assert target["ok"] is True
    assert target["slot_id"] == "screenstudio-real-01"
    assert target["duration_ms"] == 12_000
    assert target["frame_w"] == 1280
    assert target["frame_h"] == 720
    assert script.exists()
    assert "record_screenstudio_cursor_sidecar.py" in text
    assert "--capture-hotkeys" in text
    assert "--slot-id $Slot" in text
    assert "Capture finished" in text


def test_release_evidence_next_ai_case_target_writes_one_case_script(tmp_path: Path) -> None:
    template = tmp_path / "sprint" / "ai_edit_templates" / "ai-edit-real-01.template.json"
    template.parent.mkdir(parents=True)
    template.write_text("{}", encoding="utf-8")
    report = {
        "out_dir": str(tmp_path / "sprint"),
        "screenstudio": {"selected_rows": []},
        "ai": {
            "selected_rows": [
                {
                    "index": 1,
                    "case_id": "ai-edit-real-01",
                    "state": "template_needed",
                    "template_path": str(template),
                    "ready": False,
                }
            ],
        },
    }

    target = release_evidence_next_ai_case_target(report, root=ROOT, write_file=True)
    script = Path(target["path"])
    text = script.read_text(encoding="utf-8-sig")

    assert target["ok"] is True
    assert target["case_id"] == "ai-edit-real-01"
    assert target["template_path"] == str(template)
    assert script.exists()
    assert "register_ai_edit_corpus_case.py" in text
    assert "--from-template $Template --overwrite" in text
    assert "Real transcript path" in text
    assert "Natural-language edit request" in text
    assert "Type YES to confirm" in text
    assert "ConvertTo-Json -Depth 20" in text


def test_qa_dashboard_evidence_refresh_runs_source_reports_before_gate() -> None:
    from app.qa_dashboard import EVIDENCE_REFRESH_KINDS, QADashboardDialog

    rows = [
        {
            "kind": "final_product_readiness",
            "label": "Final Product Readiness",
            "path": "debugCapture/final_product_readiness_qa.json",
        },
        {
            "kind": "broadcast_release_readiness",
            "label": "Broadcast Release Readiness",
            "path": "debugCapture/broadcast_release_readiness_qa.json",
        },
        {
            "kind": "broadcast_platform_e2e",
            "label": "Broadcast Platform E2E",
            "path": "debugCapture/broadcast_platform_e2e_qa.json",
        },
        {"kind": "release_gap_closure", "label": "Release Gap Closure", "path": "debugCapture/release_gap_closure_qa.json"},
        {
            "kind": "release_evidence_sprint",
            "label": "Release Evidence Sprint",
            "path": "debugCapture/release_evidence_sprint_qa.json",
        },
        {
            "kind": "ai_edit_corpus_quality",
            "label": "AI Edit Corpus Quality",
            "path": "debugCapture/ai_edit_corpus_quality_qa.json",
        },
        {
            "kind": "screenstudio_real_corpus",
            "label": "Screen Studio Real Corpus",
            "path": "debugCapture/screenstudio_real_recording_corpus_qa.json",
        },
    ]

    commands = QADashboardDialog._evidence_refresh_commands(rows)

    assert [kind for kind, _label, _cmd in commands] == list(EVIDENCE_REFRESH_KINDS)
    assert commands[2][0] == "broadcast_platform_e2e"
    assert commands[3][0] == "broadcast_release_readiness"
    assert commands[-1][0] == "final_product_readiness"
    assert all(cmd for _kind, _label, cmd in commands)


def test_prepare_release_evidence_sprint_cli(tmp_path: Path) -> None:
    out_path = tmp_path / "release_evidence_sprint_qa.json"
    work_dir = tmp_path / "work"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "prepare_release_evidence_sprint.py"),
            "--root",
            str(ROOT),
            "--out",
            str(out_path),
            "--work-dir",
            str(work_dir),
            "--write-files",
            "--max-screenstudio",
            "1",
            "--max-ai",
            "1",
            "--capture-duration-ms",
            "5000",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "release_evidence_sprint"
    assert payload["progress"]["overall_percent"] >= 0
    assert Path(payload["playbook"]).exists()
