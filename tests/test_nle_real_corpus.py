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
    from app.nle_real_corpus import (
        build_nle_real_project_corpus_report,
        register_nle_real_project_validation_evidence,
        register_real_project,
    )

    manifest = tmp_path / "manifest.json"
    checks = {
        "open_reopen": "passed",
        "scrub_sampling": "passed",
        "proxy_relink_health": "passed",
        "undo_recovery": "passed",
        "short_export": "passed",
    }
    for index in range(3):
        project = tmp_path / f"user_project_{index + 1}.tgp"
        _write_realish_project(project, index=index + 1)
        result = register_real_project(project, manifest_path=manifest, label=f"User Project {index + 1}")
        assert result["ok"] is True
        evidence = register_nle_real_project_validation_evidence(
            project_path=project,
            manifest_path=manifest,
            checks=checks,
            operator="qa",
        )
        assert evidence["ok"] is True

    report = build_nle_real_project_corpus_report(manifest_path=manifest)

    assert report["claim_ready"] is True
    assert report["real_world_corpus"] is True
    assert report["summary"]["valid_project_count"] == 3
    assert report["summary"]["preflight_ready_count"] == 3
    assert report["summary"]["preflight_blocked_count"] == 0
    assert report["summary"]["validation_ready_count"] == 3
    assert report["summary"]["duration_ms"] >= 30 * 60_000
    assert report["summary"]["video_clips"] >= 90
    assert report["summary"]["audio_clips"] >= 20
    assert report["blockers"] == []


def test_nle_real_project_corpus_metric_only_does_not_clear_release_claim_by_default(tmp_path):
    from app.nle_real_corpus import build_nle_real_project_corpus_report, register_real_project

    manifest = tmp_path / "manifest.json"
    for index in range(3):
        project = tmp_path / f"user_project_metric_only_{index + 1}.tgp"
        _write_realish_project(project, index=index + 1)
        assert register_real_project(project, manifest_path=manifest)["ok"] is True

    strict = build_nle_real_project_corpus_report(manifest_path=manifest)
    metric_only = build_nle_real_project_corpus_report(
        manifest_path=manifest,
        require_validation_evidence=False,
    )

    assert strict["claim_ready"] is False
    assert "validation_evidence" in strict["blockers"]
    assert strict["summary"]["preflight_ready_count"] == 3
    assert strict["summary"]["validation_ready_count"] == 0
    assert metric_only["claim_ready"] is True


def test_nle_real_project_discovery_finds_registerable_candidates(tmp_path):
    from app.nle_real_corpus import discover_nle_real_project_candidates

    manifest = tmp_path / "manifest.json"
    project = tmp_path / "user_project_1.tgp"
    _write_realish_project(project, index=1)

    discovery = discover_nle_real_project_candidates([tmp_path], manifest_path=manifest)

    assert discovery["schema"] == "tigerstudio.nle.real_project_corpus.discovery.v1"
    assert discovery["candidate_count"] == 1
    assert discovery["registerable_count"] == 1
    candidate = discovery["candidates"][0]
    assert candidate["path"] == str(project.resolve())
    assert candidate["valid_for_corpus"] is True
    assert candidate["would_register"] is True
    assert candidate["metrics"]["video_clips"] == 30
    assert candidate["metrics"]["audio_clips"] == 8


def test_nle_real_project_discovery_rejects_generated_fixtures_by_default(tmp_path):
    from app.nle_real_corpus import discover_nle_real_project_candidates

    project = tmp_path / "synthetic_long_project.tgp"
    _write_realish_project(project, index=1)

    discovery = discover_nle_real_project_candidates([tmp_path], manifest_path=tmp_path / "manifest.json")

    assert discovery["candidate_count"] == 1
    candidate = discovery["candidates"][0]
    assert candidate["valid_for_corpus"] is False
    assert candidate["would_register"] is False
    assert "generated_fixture_rejected" in candidate["warnings"]


def test_nle_real_project_discovery_explains_too_few_clips(tmp_path):
    from app.nle_real_corpus import discover_nle_real_project_candidates

    project = tmp_path / "short_clip_count_project.tgp"
    _write_realish_project(project, index=1, video_clips=2, audio_clips=0)

    discovery = discover_nle_real_project_candidates([tmp_path], manifest_path=tmp_path / "manifest.json")

    candidate = discovery["candidates"][0]
    assert candidate["valid_for_corpus"] is False
    assert "too_few_clips" in candidate["warnings"]


def test_nle_real_project_discovery_marks_already_registered_candidates(tmp_path):
    from app.nle_real_corpus import discover_nle_real_project_candidates, register_real_project

    manifest = tmp_path / "manifest.json"
    project = tmp_path / "user_project_registered.tgp"
    _write_realish_project(project, index=1)
    result = register_real_project(project, manifest_path=manifest)
    assert result["ok"] is True

    discovery = discover_nle_real_project_candidates([tmp_path], manifest_path=manifest)

    assert discovery["candidate_count"] == 1
    candidate = discovery["candidates"][0]
    assert candidate["already_registered"] is True
    assert candidate["valid_for_corpus"] is True
    assert candidate["would_register"] is False
    assert "already_registered" in candidate["warnings"]


def test_nle_real_project_intake_board_groups_registerable_and_rejected_projects(tmp_path):
    from app.nle_real_corpus import build_nle_real_project_intake_board

    good = tmp_path / "user_project_good.tgp"
    short = tmp_path / "user_project_short.tgp"
    _write_realish_project(good, index=1)
    _write_realish_project(short, index=2, video_clips=2, audio_clips=0)

    board = build_nle_real_project_intake_board(
        [tmp_path],
        manifest_path=tmp_path / "manifest.json",
        max_results=10,
    )

    assert board["schema"] == "tigerstudio.nle.real_project_corpus.intake_board.v1"
    assert board["ready"] is True
    assert board["claim_ready"] is False
    assert board["registerable_count"] == 1
    sections = {section["id"]: section for section in board["sections"]}
    assert sections["claim_gate"]["status"] == "blocked"
    assert any(row["id"] == "validation_projects" for row in sections["claim_gate"]["rows"])
    assert sections["registerable_projects"]["rows"][0]["path"] == str(good.resolve())
    assert sections["registerable_projects"]["rows"][0]["primary_action"]["id"] == "nle.real_corpus.register"
    rejected = sections["rejected_candidates"]["rows"]
    assert any(row["path"] == str(short.resolve()) and "too_few_clips" in row["warnings"] for row in rejected)
    assert board["commands"]["register_selected_enabled"] is True


def test_nle_real_project_validation_evidence_report_tracks_registered_checks(tmp_path):
    from app.nle_real_corpus import (
        build_nle_real_project_validation_report,
        preview_nle_real_project_validation_evidence,
        register_nle_real_project_validation_evidence,
        register_real_project,
    )

    manifest = tmp_path / "manifest.json"
    project = tmp_path / "user_project_validation.tgp"
    _write_realish_project(project, index=1)
    registered = register_real_project(project, manifest_path=manifest, label="Validation Project")
    assert registered["ok"] is True

    before = build_nle_real_project_validation_report(manifest_path=manifest)
    assert before["schema"] == "tigerstudio.nle.real_project_corpus.validation_report.v1"
    assert before["summary"]["validation_ready_count"] == 0
    assert "validation_evidence_count" in before["blockers"]

    checks = {
        "open_reopen": "passed",
        "scrub_sampling": "passed",
        "proxy_relink_health": "passed",
        "undo_recovery": "passed",
        "short_export": "passed",
    }
    preview = preview_nle_real_project_validation_evidence(
        project_path=project,
        manifest_path=manifest,
        checks=checks,
        operator="qa",
    )
    assert preview["ok"] is True
    assert preview["would_write"]["summary"]["all_required_passed"] is True

    written = register_nle_real_project_validation_evidence(
        project_path=project,
        manifest_path=manifest,
        checks=checks,
        operator="qa",
    )
    after = build_nle_real_project_validation_report(manifest_path=manifest, min_projects=1)

    assert written["ok"] is True
    assert written["validation_evidence"]["status"] == "passed"
    assert after["summary"]["validation_ready_count"] == 1
    assert after["projects"][0]["validation_ready"] is True
    assert after["projects"][0]["summary"]["all_required_passed"] is True


def test_register_nle_real_project_validation_cli_writes_evidence(tmp_path, capsys):
    from app.nle_real_corpus import build_nle_real_project_validation_report, register_real_project
    from tools.register_nle_real_project_validation import main as validation_main

    manifest = tmp_path / "manifest.json"
    project = tmp_path / "user_project_validation_cli.tgp"
    _write_realish_project(project, index=1)
    assert register_real_project(project, manifest_path=manifest, label="Validation CLI Project")["ok"] is True

    code = validation_main(
        [
            "--project",
            str(project),
            "--manifest",
            str(manifest),
            "--all-passed",
            "--operator",
            "qa",
        ]
    )
    captured = capsys.readouterr()
    report = build_nle_real_project_validation_report(manifest_path=manifest, min_projects=1)

    assert code == 0
    assert '"ok": true' in captured.out
    assert report["summary"]["validation_ready_count"] == 1
    assert report["projects"][0]["validation_ready"] is True


def test_nle_real_project_collection_kit_exposes_validation_cli_examples(tmp_path):
    from app.nle_real_corpus import build_nle_real_project_collection_kit, register_real_project

    manifest = tmp_path / "manifest.json"
    project = tmp_path / "user_project_collection_cli.tgp"
    _write_realish_project(project, index=1)
    assert register_real_project(project, manifest_path=manifest, label="Collection CLI Project")["ok"] is True

    kit = build_nle_real_project_collection_kit(
        search_roots=[tmp_path],
        manifest_path=manifest,
    )

    examples = kit["validation"]["cli_examples"]
    assert examples
    assert examples[0]["label"] == "Collection CLI Project"
    assert "tools\\register_nle_real_project_validation.py" in examples[0]["command"]
    assert "--all-passed" in examples[0]["command"]


def test_nle_real_project_gate_board_explains_claim_blockers_and_next_actions(tmp_path):
    from app.nle_real_corpus import build_nle_real_project_gate_board, register_real_project

    manifest = tmp_path / "manifest.json"
    project = tmp_path / "user_project_gate_board.tgp"
    _write_realish_project(project, index=1)
    assert register_real_project(project, manifest_path=manifest, label="Gate Board Project")["ok"] is True

    board = build_nle_real_project_gate_board(
        search_roots=[tmp_path],
        manifest_path=manifest,
        max_results=10,
    )

    assert board["schema"] == "tigerstudio.nle.real_project_corpus.gate_board.v1"
    assert board["ready"] is True
    assert board["claim_ready"] is False
    assert board["professional_nle_claim_blocked"] is True
    assert board["readiness"]["gate_board_ready"] is True
    assert board["readiness"]["registration_workflow_ready"] is True
    assert board["readiness"]["validation_workflow_ready"] is True
    sections = {section["id"]: section for section in board["sections"]}
    assert sections["claim_gate"]["status"] == "blocked"
    assert any(row["id"] == "real_project_count" for row in sections["blocked_requirements"]["rows"])
    assert sections["validation_missing"]["status"] == "warning"
    assert sections["workflow"]["rows"][-1]["id"] == "rerun"
    assert board["commands"]["register_validation_evidence_enabled"] is True
    assert "real_project_count" in board["current_corpus"]["blockers"]


def test_nle_real_project_validation_packet_guides_operator_evidence(tmp_path):
    from app.nle_real_corpus import build_nle_real_project_validation_packet, register_real_project

    manifest = tmp_path / "manifest.json"
    project = tmp_path / "user_project_packet.tgp"
    _write_realish_project(project, index=1)
    registered = register_real_project(project, manifest_path=manifest, label="Packet Project")
    assert registered["ok"] is True

    packet = build_nle_real_project_validation_packet(
        project_path=project,
        manifest_path=manifest,
    )

    assert packet["schema"] == "tigerstudio.nle.real_project_corpus.validation_packet.v1"
    assert packet["ready"] is True
    assert packet["project"]["label"] == "Packet Project"
    assert packet["project"]["valid_for_corpus"] is True
    assert packet["summary"]["all_required_passed"] is False
    assert set(packet["summary"]["pending_required_ids"]) >= {
        "open_reopen",
        "scrub_sampling",
        "proxy_relink_health",
        "undo_recovery",
        "short_export",
    }
    sections = {section["id"]: section for section in packet["sections"]}
    assert sections["required_checks"]["status"] == "ready"
    assert sections["redaction_rules"]["status"] == "required"
    assert packet["commands"]["register_validation_evidence_enabled"] is True
    assert packet["action_template"]["id"] == "nle.real_corpus.validation_evidence.register"
    assert packet["action_template"]["requires_operator_review"] is True
    assert packet["cli_template"]["requires_operator_review"] is True
    assert "tools\\register_nle_real_project_validation.py" in packet["cli_template"]["command"]
    assert {row["status"] for row in packet["action_template"]["params"]["checks"]} == {"pending"}


def test_nle_real_project_validation_preflight_separates_machine_and_operator_checks(tmp_path):
    from app.nle_real_corpus import build_nle_real_project_validation_preflight, register_real_project

    manifest = tmp_path / "manifest.json"
    project = tmp_path / "user_project_preflight.tgp"
    _write_realish_project(project, index=2)
    registered = register_real_project(project, manifest_path=manifest, label="Preflight Project")
    assert registered["ok"] is True

    preflight = build_nle_real_project_validation_preflight(
        project_path=project,
        manifest_path=manifest,
    )

    assert preflight["schema"] == "tigerstudio.nle.real_project_corpus.validation_preflight.v1"
    assert preflight["ready"] is True
    assert preflight["summary"]["machine_preflight_passed"] is True
    assert preflight["summary"]["operator_evidence_required"] is True
    assert preflight["readiness"]["safe_to_register_after_operator_review"] is True
    assert {row["status"] for row in preflight["suggested_validation_checks"]} == {"pending"}
    machine = {row["id"]: row for row in preflight["machine_checks"]}
    assert machine["project_exists"]["status"] == "pass"
    assert machine["no_missing_media"]["status"] == "pass"
    operator = {row["id"]: row for row in preflight["operator_checks"]}
    assert operator["open_reopen"]["status"] == "ready_for_operator"
    assert operator["short_export"]["status"] == "ready_for_operator"
    assert preflight["action_template"]["id"] == "nle.real_corpus.validation_evidence.register"
    assert preflight["action_template"]["requires_operator_review"] is True


def test_nle_real_project_validation_preflight_reports_missing_manifest(tmp_path):
    from app.nle_real_corpus import build_nle_real_project_validation_preflight

    preflight = build_nle_real_project_validation_preflight(manifest_path=tmp_path / "missing_manifest.json")

    assert preflight["ready"] is False
    assert preflight["reason"] == "no_registered_project"
    assert preflight["readiness"]["machine_preflight_passed"] is False


def test_nle_real_project_preflight_qa_reports_registered_projects(tmp_path):
    from app.nle_real_corpus import register_real_project
    from tools.qa_nle_real_project_preflight import run_nle_real_project_preflight_qa

    manifest = tmp_path / "manifest.json"
    project = tmp_path / "user_project_preflight_qa.tgp"
    _write_realish_project(project, index=3)
    assert register_real_project(project, manifest_path=manifest, label="Preflight QA")["ok"] is True

    report = run_nle_real_project_preflight_qa(manifest_path=manifest)

    assert report["schema"] == "tigerstudio.nle.real_project_corpus.preflight_qa.v1"
    assert report["ready"] is True
    assert report["summary"]["registered_project_count"] == 1
    assert report["summary"]["machine_preflight_passed_count"] == 1
    assert report["projects"][0]["machine_preflight_passed"] is True
    assert report["projects"][0]["operator_evidence_required"] is True


def test_nle_real_project_workbench_guides_next_action(tmp_path):
    from app.nle_real_corpus_workbench import build_nle_real_project_workbench

    manifest = tmp_path / "manifest.json"
    project = tmp_path / "user_project_workbench.tgp"
    _write_realish_project(project, index=4)

    board = build_nle_real_project_workbench(
        search_roots=[tmp_path],
        manifest_path=manifest,
        max_results=5,
    )

    assert board["schema"] == "tigerstudio.nle.real_project_corpus.workbench.v1"
    assert board["ready"] is True
    assert board["claim_ready"] is False
    assert board["primary_step"]["id"] == "register_candidates"
    assert board["commands"]["register_candidates_enabled"] is True
    sections = {section["id"]: section for section in board["sections"]}
    assert sections["registerable_candidates"]["status"] == "ready"
    assert sections["registerable_candidates"]["rows"][0]["path"] == str(project.resolve())
    assert board["summary"]["valid_project_count"] == 0
    assert "nle.real_corpus.validation_preflight" in {row["id"] for row in board["action_sequence"]}
