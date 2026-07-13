import json


def test_release_positioning_audit_passes_public_copy():
    from app.release_positioning import build_release_positioning_report

    report = build_release_positioning_report(".")

    assert report["ok"] is True
    assert report["release_copy_claim_ready"] is True
    assert report["summary"]["files_scanned"] >= 4
    assert report["summary"]["blocking_findings"] == 0
    assert report["checks"]["safe_screenstudio_language_present"] is True
    assert report["checks"]["safe_capcut_language_present"] is True
    assert report["checks"]["safe_voice_lab_language_present"] is True
    assert report["checks"]["replacement_caveat_present"] is True
    assert report["checks"]["public_surface_coverage"] is True


def test_release_positioning_blocks_overstrong_competitor_claims():
    from app.release_positioning import scan_release_positioning_text

    findings = scan_release_positioning_text(
        "Tiger Studio is a full Screen Studio parity, CapCut replacement, CapCut template scale, Resolve-grade editor, and Premiere-grade NLE.",
        path="website.md",
    )

    assert {row.rule_id for row in findings} >= {
        "screenstudio_replacement_claim",
        "capcut_ecosystem_claim",
        "capcut_trend_template_claim",
        "professional_suite_grade_claim",
        "professional_nle_replacement_claim",
    }


def test_release_positioning_blocks_overstrong_tts_claims():
    from app.release_positioning import scan_release_positioning_text

    findings = scan_release_positioning_text(
        "TigerCapture includes a hosted TTS platform with universal voice cloning and bundled Style-Bert-VITS2.",
        path="landing.md",
    )

    assert {row.rule_id for row in findings} == {"tts_hosted_or_universal_voice_claim"}


def test_release_positioning_allows_guardrail_context():
    from app.release_positioning import scan_release_positioning_text

    findings = scan_release_positioning_text(
        "Do not claim full Screen Studio parity until the real recording corpus passes.",
        path="docs/RELEASE_POSITIONING.md",
    )

    assert findings == []


def test_qa_public_positioning_cli_writes_report(tmp_path, monkeypatch, capsys):
    from tools import qa_public_positioning

    out = tmp_path / "public_positioning.json"
    monkeypatch.setattr("sys.argv", ["qa_public_positioning.py", "--out", str(out)])

    assert qa_public_positioning.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert stdout["ok"] is True
    assert payload["summary"]["blocking_findings"] == 0
