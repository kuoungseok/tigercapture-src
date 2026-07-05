from __future__ import annotations

import json


def test_commercial_expansion_builds_ten_area_report():
    from app.commercial_expansion import COMMERCIAL_EXPANSION_AREAS, build_commercial_expansion_report

    report = build_commercial_expansion_report()
    ids = {row["id"] for row in report["areas"]}

    assert report["summary"]["areas"] == 10
    assert ids == {area.id for area in COMMERCIAL_EXPANSION_AREAS}
    assert "score" in report
    assert all("user_value" in row for row in report["areas"])


def test_project_snapshot_and_beta_feedback_bundle(tmp_path):
    from app.commercial_expansion import (
        create_project_snapshot,
        export_beta_feedback_bundle,
        list_project_snapshots,
    )

    project = tmp_path / "sample.tgp"
    project.write_text(json.dumps({"video_tracks": []}), encoding="utf-8")
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "recent_actions.jsonl").write_text('{"event":"test"}\n', encoding="utf-8")

    snapshot = create_project_snapshot(project, root=tmp_path, label="before-export")
    snapshots = list_project_snapshots(root=tmp_path)
    bundle = export_beta_feedback_bundle(project_path=project, root=tmp_path)

    assert snapshot["ok"] is True
    assert snapshot["sha256"]
    assert snapshots[-1]["label"] == "before-export"
    assert bundle["ok"] is True
    assert bundle["artifact_count"] >= 2
    assert bundle["project"]["sha256"] == snapshot["sha256"]


def test_plugin_manifest_validation_and_discovery(tmp_path):
    from app.commercial_expansion import discover_plugins, validate_plugin_manifest

    plugin_dir = tmp_path / "plugins" / "sample"
    plugin_dir.mkdir(parents=True)
    manifest = {
        "id": "sample.tools",
        "name": "Sample Tools",
        "version": "1.0.0",
        "hooks": [{"kind": "timeline_command", "entry": "sample:run", "label": "Run"}],
    }
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")

    valid = validate_plugin_manifest(manifest)
    discovered = discover_plugins(root=tmp_path)

    assert valid["ok"] is True
    assert discovered["ok"] is True
    assert discovered["plugin_count"] == 1
    assert discovered["plugins"][0]["id"] == "sample.tools"


def test_parity_lock_and_one_click_plan_are_product_surfaces():
    from app.commercial_expansion import (
        apply_gpu_parity_lock_settings,
        build_ai_one_click_edit_plan,
        gpu_parity_lock_status,
    )

    doc = {"project_settings": {}, "video_tracks": [], "audio_tracks": []}
    lock = apply_gpu_parity_lock_settings(doc)
    status = gpu_parity_lock_status(doc)
    plan = build_ai_one_click_edit_plan({"shortform": True, "tutorial": True, "dialogue": True})

    assert lock["enabled"] is True
    assert doc["project_settings"]["preview_export_parity_lock"]["mode"] == "strict-preview-export"
    assert status["ok"] is True
    assert plan["ok"] is True
    assert plan["step_count"] >= 5
    assert plan["first_template"]["kind"] == "template"
