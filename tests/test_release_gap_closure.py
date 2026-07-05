from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.release_gap_closure import AREA_ORDER, build_release_gap_closure_report


ROOT = Path(__file__).resolve().parents[1]


def test_release_gap_closure_has_the_six_requested_areas() -> None:
    report = build_release_gap_closure_report(ROOT)

    assert report["ok"] is True
    assert isinstance(report["release_ready"], bool)
    assert [row["id"] for row in report["areas"]] == list(AREA_ORDER)
    assert report["summary"]["areas"] == 6


def test_release_gap_closure_keeps_marketing_claims_honest() -> None:
    report = build_release_gap_closure_report(ROOT)
    areas = {row["id"]: row for row in report["areas"]}

    ai = areas["generative_ai_one_click"]
    assert "smart_edit_claim_ready" in ai["evidence"]
    if not ai["evidence"]["smart_edit_claim_ready"]:
        assert any("smart" in action.lower() or "provider" in action.lower() for action in ai["actions"])

    screenstudio = areas["screenstudio_real_recording_corpus"]
    assert "replacement_claim_ready" in screenstudio["evidence"]
    assert "cursor_sidecar_ready" in screenstudio["evidence"]["summary"]

    scrub = areas["preview_scrub_seek"]
    assert "release_scrub_claim_ready" in scrub["evidence"]
    assert "top_seek_hotspots" in scrub["evidence"]

    actor = areas["actor_model_compatibility"]
    assert actor["evidence"]["total"] >= 0
    assert "golden_pass" in actor["evidence"]


def test_release_gap_closure_does_not_touch_ar_pbr_scope() -> None:
    report = build_release_gap_closure_report(ROOT)
    text = json.dumps(report, ensure_ascii=False).casefold()

    assert "app/ar_pbr" not in text
    assert "camera_solve" not in text
    assert "docs/spec_ar_pbr_compositor" not in text


def test_release_gap_closure_cli_writes_report(tmp_path: Path) -> None:
    out_path = tmp_path / "release_gap_closure_qa.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "qa_release_gap_closure.py"),
            "--root",
            str(ROOT),
            "--out",
            str(out_path),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "release_gap_closure"
    assert [row["id"] for row in payload["areas"]] == list(AREA_ORDER)

