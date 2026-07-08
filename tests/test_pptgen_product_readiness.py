from __future__ import annotations

from pathlib import Path


def test_product_readiness_qa_covers_core_authoring_scenarios(tmp_path):
    from app.pptgen.product_readiness import run_ppt_product_readiness_qa

    manifest = run_ppt_product_readiness_qa(tmp_path, export_video=False, width=480, height=270)

    assert manifest["schema"] == "tigercapture.ppt.product_readiness.v1"
    assert manifest["ok"] is True
    assert manifest["checks"]["scenario_count"] >= 5
    assert manifest["checks"]["scenario_ok_count"] == manifest["checks"]["scenario_count"]
    assert {row["name"] for row in manifest["scenarios"]} >= {
        "template_authoring",
        "document_tools",
        "prompt_deck",
        "media_and_actors",
        "animation_timeline",
    }

    for scenario in manifest["scenarios"]:
        assert scenario["validation"]["error_count"] == 0
        assert Path(scenario["artifacts"]["project"]).is_file()
        assert Path(scenario["artifacts"]["pptx"]).is_file()
        assert Path(scenario["artifacts"]["contact_sheet"]).is_file()
        assert Path(scenario["artifacts"]["slides_dir"]).is_dir()

    assert Path(manifest["manifest_path"]).is_file()
