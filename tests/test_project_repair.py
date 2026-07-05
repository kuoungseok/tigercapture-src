from __future__ import annotations

import json
import os
import time

from tools.repair_project import repair_project_doc


def test_repair_project_doc_fills_defaults_and_reports_missing(tmp_path):
    missing = tmp_path / "missing.mp4"
    raw = {
        "video_tracks": [{
            "id": 1,
            "clips": [{
                "id": 7,
                "source_path": str(missing),
                "source_in_ms": 10,
                "source_out_ms": 0,
            }],
        }],
    }

    doc, report = repair_project_doc(raw)

    assert doc["app"] == "TigerCapture"
    assert "audio_tracks" in doc
    clip = doc["video_tracks"][0]["clips"][0]
    assert clip["source_out_ms"] > clip["source_in_ms"]
    assert clip["fades"] == []
    assert report["ok"] is False
    assert "video" in report["missing"]
    assert report["repair_guidance"]["missing_count"] == 1
    assert "Relink" in report["repair_guidance"]["actions"][0]


def test_audit_recovery_candidates_picks_newest_readable_autosave(tmp_path):
    from tools.repair_project import audit_recovery_candidates

    old_path = tmp_path / "project~autosave.tgp"
    new_path = tmp_path / ".tigercapture_recovery" / "project_20260614_timer.tgp"
    bad_path = tmp_path / ".tigercapture_recovery" / "broken.tgp"
    new_path.parent.mkdir()

    doc = {
        "video_tracks": [],
        "audio_tracks": [],
        "media_pool": [],
    }
    old_path.write_text(json.dumps(doc), encoding="utf-8")
    new_path.write_text(json.dumps(doc), encoding="utf-8")
    bad_path.write_text("{broken", encoding="utf-8")

    now = time.time()
    os.utime(old_path, (now - 20, now - 20))
    os.utime(new_path, (now, now))
    os.utime(bad_path, (now + 20, now + 20))

    report = audit_recovery_candidates([old_path, new_path, bad_path])

    assert report["ok"] is True
    assert report["best"]["path"] == str(new_path)
    assert any(row["readable"] is False for row in report["candidates"])
    assert report["product_summary"]["best_path"] == str(new_path)
    assert report["product_summary"]["best_health"]["level"] == "open_safe"


def test_recovery_product_summary_recommends_relink_for_missing_media(tmp_path):
    from tools.repair_project import audit_recovery_candidates

    recovery_path = tmp_path / ".tigercapture_recovery" / "missing_autosave.tgp"
    recovery_path.parent.mkdir()
    missing = tmp_path / "missing.mp4"
    recovery_path.write_text(
        json.dumps({
            "video_tracks": [{
                "clips": [{
                    "id": 1,
                    "source_path": str(missing),
                    "source_duration_ms": 1000,
                    "source_in_ms": 0,
                    "source_out_ms": 1000,
                }]
            }],
            "media_pool": [str(missing)],
        }),
        encoding="utf-8",
    )

    report = audit_recovery_candidates([recovery_path])

    health = report["product_summary"]["best_health"]
    candidate = report["product_summary"]["candidates"][0]
    assert health["level"] == "needs_relink"
    assert "Relink" in health["recommended_action"]
    assert candidate["missing_by_kind"]["media_pool"] == 1
    assert candidate["missing_by_kind"]["video"] == 1
    assert any(item["path"] == str(missing) for item in candidate["missing_preview"])
    assert any("Relink" in action for action in candidate["guidance_actions"])


def test_recovery_candidate_rows_are_ui_ready(tmp_path):
    from app.recovery_dialog import recovery_candidate_rows
    from tools.repair_project import audit_recovery_candidates

    recovery_path = tmp_path / ".tigercapture_recovery" / "missing_autosave.tgp"
    broken_path = tmp_path / ".tigercapture_recovery" / "broken.tgp"
    recovery_path.parent.mkdir()
    missing = tmp_path / "missing.mp4"
    recovery_path.write_text(
        json.dumps({
            "video_tracks": [{
                "clips": [{
                    "id": 1,
                    "source_path": str(missing),
                    "source_duration_ms": 1000,
                    "source_in_ms": 0,
                    "source_out_ms": 1000,
                }]
            }],
        }),
        encoding="utf-8",
    )
    broken_path.write_text("{broken", encoding="utf-8")
    now = time.time()
    os.utime(recovery_path, (now, now))
    os.utime(broken_path, (now + 10, now + 10))

    report = audit_recovery_candidates([recovery_path, broken_path])
    rows = recovery_candidate_rows(report)

    by_name = {row["filename"]: row for row in rows}
    assert by_name["missing_autosave.tgp"]["status_label"] == "Needs Relink"
    assert by_name["missing_autosave.tgp"]["missing_count"] == 1
    assert by_name["missing_autosave.tgp"]["score"] < 100
    assert by_name["missing_autosave.tgp"]["mtime_text"]
    assert by_name["missing_autosave.tgp"]["missing_by_kind"]["video"] == 1
    assert by_name["missing_autosave.tgp"]["missing_preview"]
    assert by_name["missing_autosave.tgp"]["changes_preview"]
    assert by_name["missing_autosave.tgp"]["guidance_actions"]
    assert "relink" in by_name["missing_autosave.tgp"]["user_action_label"].casefold()
    assert by_name["broken.tgp"]["status_label"] == "Broken"
    assert by_name["broken.tgp"]["readable"] is False


def test_recovery_dialog_detail_shows_problem_preview(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from app.recovery_dialog import RecoveryCandidatesDialog
    from tools.repair_project import audit_recovery_candidates

    recovery_path = tmp_path / ".tigercapture_recovery" / "actor_missing_autosave.tgp"
    recovery_path.parent.mkdir()
    missing_video = tmp_path / "missing.mp4"
    missing_skel = tmp_path / "missing.skel"
    missing_atlas = tmp_path / "missing.atlas"
    recovery_path.write_text(
        json.dumps({
            "video_tracks": [{
                "clips": [{
                    "id": 1,
                    "source_path": str(missing_video),
                    "source_duration_ms": 1000,
                    "source_in_ms": 0,
                    "source_out_ms": 1000,
                }]
            }],
            "spine_actor_tracks": [{
                "id": 9,
                "clips": [{
                    "skel_path": str(missing_skel),
                    "atlas_path": str(missing_atlas),
                    "anim_name": "idle",
                    "start_ms": 0,
                    "duration_ms": 1000,
                }],
            }],
        }),
        encoding="utf-8",
    )

    app = QApplication.instance() or QApplication([])
    report = audit_recovery_candidates([recovery_path])
    dialog = RecoveryCandidatesDialog(report)
    try:
        text = dialog._detail.toPlainText()
        assert "Suggested steps" in text
        assert "User action" in text
        assert "Missing by kind" in text
        assert "Missing path preview" in text
        assert str(missing_video) in text
        assert "Schema repair preview" in text
        assert "Actor asset preview" in text
        assert "missing.skel" in text
    finally:
        dialog.deleteLater()
        app.processEvents()
