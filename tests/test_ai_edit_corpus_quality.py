from __future__ import annotations

import json
from pathlib import Path


def test_builtin_ai_edit_corpus_scores_mvp_but_blocks_smart_claim(tmp_path):
    from app.ai_edit_corpus_quality import build_ai_edit_corpus_quality_report

    report = build_ai_edit_corpus_quality_report(
        manifest_path=tmp_path / "missing_manifest.json",
        env={"TIGERCAPTURE_AI_PROVIDER": "rule_based"},
    )

    assert report["ok"] is True
    assert report["safe_mvp_ready"] is True
    assert report["smart_edit_claim_ready"] is False
    assert report["summary"]["cases"] >= 5
    assert report["summary"]["fixture_cases"] >= 5
    assert report["summary"]["real_cases"] == 0
    assert report["category_requirements"]["korean"] is True
    assert report["category_requirements"]["english"] is True
    assert report["category_requirements"]["shortform"] is True
    assert report["category_requirements"]["long"] is True
    assert "provider_executor_not_wired" in report["claim_blockers"]
    assert "real_user_corpus_below_min" in report["claim_blockers"]


def test_manifest_ai_edit_corpus_cases_can_be_loaded(tmp_path):
    from app.ai_edit_corpus_quality import build_ai_edit_corpus_quality_report, load_ai_edit_corpus_cases

    srt = tmp_path / "case.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nUm show the product.\n\n"
        "2\n00:00:03,000 --> 00:00:05,000\nNow add captions.\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "min_real_cases": 1,
                "cases": [
                    {
                        "id": "real_product_demo",
                        "language": "en",
                        "scenario": "product",
                        "fixture": False,
                        "prompt": "Make a product demo with captions and callouts",
                        "source_format": "srt",
                        "transcript_path": "case.srt",
                        "expected_intent": "product_demo",
                        "required_operations": ["apply_preset", "add_callout", "add_auto_zoom", "create_subtitles"],
                        "min_segments": 2,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases, meta = load_ai_edit_corpus_cases(manifest)
    assert meta["found"] is True
    assert cases[0]["transcript"].startswith("1\n")

    report = build_ai_edit_corpus_quality_report(
        manifest_path=manifest,
        env={"TIGERCAPTURE_AI_PROVIDER": "rule_based"},
    )
    assert report["summary"]["real_cases"] == 1
    assert report["cases"][0]["ok"] is True
    assert report["smart_edit_claim_ready"] is False
    assert "provider_executor_not_wired" in report["claim_blockers"]


def test_ai_edit_corpus_quality_tool_writes_report(tmp_path, monkeypatch):
    from tools import qa_ai_edit_corpus_quality

    out = tmp_path / "ai_edit_corpus_quality_qa.json"
    monkeypatch.setattr("sys.argv", ["qa_ai_edit_corpus_quality.py", "--out", str(out)])

    assert qa_ai_edit_corpus_quality.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["safe_mvp_ready"] is True
    assert report["smart_edit_claim_ready"] is False


def test_ai_edit_corpus_quality_tool_can_auto_start_qwen(tmp_path, monkeypatch):
    from tools import qa_ai_edit_corpus_quality

    out = tmp_path / "ai_edit_corpus_quality_qa.json"
    calls = []

    class FakeEnsure:
        def to_dict(self):
            return {
                "ok": True,
                "endpoint": "http://127.0.0.1:8080/v1",
                "models_url": "http://127.0.0.1:8080/v1/models",
                "already_running": False,
                "process_started": True,
                "command": "fake-qwen",
                "pid": 123,
                "error": "",
                "waited_seconds": 0.1,
            }

    def fake_ensure(**kwargs):
        calls.append(kwargs)
        return FakeEnsure()

    monkeypatch.setattr("app.ai_qwen_server.ensure_qwen_server", fake_ensure)
    monkeypatch.setattr(
        "sys.argv",
        [
            "qa_ai_edit_corpus_quality.py",
            "--out",
            str(out),
            "--provider",
            "qwen_local",
            "--auto-start-qwen",
        ],
    )

    assert qa_ai_edit_corpus_quality.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))

    assert calls
    assert calls[0]["env"]["TIGERCAPTURE_AI_PROVIDER"] == "qwen_local"
    assert report["provider"]["selected"] == "qwen_local"
    assert report["provider"]["qwen_auto_start"]["process_started"] is True


def test_ai_edit_corpus_provider_result_uses_current_result_contract(monkeypatch):
    import app.ai_providers as providers
    from app.ai_edit_corpus_quality import build_ai_edit_corpus_quality_report

    def fake_generate(_prompt, base_plan, **_kwargs):
        return providers.AIProviderPlanResult(
            ok=True,
            provider="local_llm",
            plan=base_plan,
            metadata={"provider_executor": "test_provider"},
        )

    monkeypatch.setattr(providers, "generate_selected_provider_plan", fake_generate)

    report = build_ai_edit_corpus_quality_report(
        use_provider=True,
        env={"TIGERCAPTURE_AI_PROVIDER": "rule_based"},
    )

    assert report["summary"]["failures"] == 0
    first_provider = report["cases"][0]["metrics"]["provider_result"]
    assert first_provider["used"] is True
    assert first_provider["fallback_used"] is False
    assert first_provider["metadata"]["provider_executor"] == "test_provider"


def test_ai_edit_corpus_reports_provider_fallbacks_separately(monkeypatch):
    import app.ai_providers as providers
    from app.ai_edit_corpus_quality import build_ai_edit_corpus_quality_report

    def fake_generate(_prompt, _base_plan, **_kwargs):
        return providers.AIProviderPlanResult(
            ok=False,
            provider="local_llm",
            reason="provider timed out",
        )

    monkeypatch.setattr(providers, "generate_selected_provider_plan", fake_generate)

    report = build_ai_edit_corpus_quality_report(
        use_provider=True,
        env={"TIGERCAPTURE_AI_PROVIDER": "local_llm", "TIGERCAPTURE_LOCAL_LLM_COMMAND": "python"},
    )

    assert "provider_execution_failed_on_corpus" in report["claim_blockers"]
    assert "provider_executor_not_wired" not in report["claim_blockers"]
    assert report["provider"]["corpus_attempts"] == report["summary"]["cases"]
    assert report["provider"]["corpus_direct_successes"] == 0
    assert report["provider"]["corpus_fallbacks"] == report["summary"]["cases"]


def test_ai_edit_corpus_provider_retry_can_recover_case(monkeypatch):
    import app.ai_providers as providers
    from app.ai_edit_corpus_quality import build_ai_edit_corpus_quality_report

    attempts = {"count": 0}

    def fake_generate(_prompt, base_plan, **kwargs):
        attempts["count"] += 1
        assert kwargs.get("timeout_seconds") == 240
        if attempts["count"] % 2 == 1:
            return providers.AIProviderPlanResult(
                ok=False,
                provider="claude_mcp",
                reason="provider timed out",
            )
        return providers.AIProviderPlanResult(
            ok=True,
            provider="claude_mcp",
            plan=base_plan,
            metadata={"provider_executor": "retry_test"},
        )

    monkeypatch.setattr(providers, "generate_selected_provider_plan", fake_generate)

    report = build_ai_edit_corpus_quality_report(
        use_provider=True,
        env={"TIGERCAPTURE_AI_PROVIDER": "claude_mcp"},
        provider_timeout_seconds=240,
        provider_retries=1,
    )

    assert "provider_execution_fallbacks_present" not in report["claim_blockers"]
    assert report["provider"]["corpus_direct_successes"] == report["summary"]["cases"]
    assert report["provider"]["corpus_fallbacks"] == 0
    assert report["provider"]["corpus_provider_calls"] == report["summary"]["cases"] * 2
    assert report["provider"]["provider_timeout_seconds"] == 240
    assert report["provider"]["provider_retries"] == 1


def test_ai_edit_corpus_intake_writes_safe_templates_without_unblocking_claim(tmp_path):
    from app.ai_edit_corpus_intake import build_ai_edit_corpus_intake_report

    template_dir = tmp_path / "templates"
    report = build_ai_edit_corpus_intake_report(
        manifest_path=tmp_path / "missing_manifest.json",
        target_min=4,
        template_dir=template_dir,
        write_templates=True,
    )

    assert report["ok"] is False
    assert report["claim_unblocked_by_templates"] is False
    assert report["summary"]["real_cases"] == 0
    assert report["summary"]["templates_written"] == 4
    first_template = Path(report["rows"][0]["template_path"])
    payload = json.loads(first_template.read_text(encoding="utf-8"))
    assert payload["kind"] == "ai_edit_real_case_template"
    assert payload["counts_for_ai_claim"] is False
    assert payload["manifest_case"]["fixture"] is False
    assert payload["manifest_case"]["prompt"] == ""
    assert "register_ai_edit_corpus_case.py" in payload["registration_command"]
    assert "--from-template" in payload["registration_command"]
    assert "register_ai_edit_corpus_case.py" in report["rows"][0]["registration_command"]
    assert "--from-template" in report["rows"][0]["registration_command"]
    assert payload["acceptance_checklist"]["real_user_project"] is False


def test_prepare_ai_edit_corpus_intake_cli_writes_report_and_templates(tmp_path, monkeypatch):
    from tools import prepare_ai_edit_corpus_intake

    out = tmp_path / "ai_edit_corpus_intake_qa.json"
    template_dir = tmp_path / "templates"
    monkeypatch.setattr(
        "sys.argv",
        [
            "prepare_ai_edit_corpus_intake.py",
            "--out",
            str(out),
                "--template-dir",
                str(template_dir),
                "--manifest",
                str(tmp_path / "missing_manifest.json"),
                "--target-min",
                "3",
            "--write-templates",
        ],
    )

    assert prepare_ai_edit_corpus_intake.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["summary"]["target_min"] == 3
    assert report["summary"]["templates_written"] == 3
    assert template_dir.joinpath("ai-edit-real-01.template.json").is_file()
    assert any("register_ai_edit_corpus_case.py" in action for action in report["next_actions"])


def test_register_ai_edit_corpus_case_cli_adds_real_manifest_case(tmp_path, monkeypatch, capsys):
    from app.ai_edit_corpus_quality import build_ai_edit_corpus_quality_report, load_ai_edit_corpus_cases
    from tools import register_ai_edit_corpus_case

    transcript = tmp_path / "product.srt"
    transcript.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nShow the product dashboard.\n\n"
        "2\n00:00:02,500 --> 00:00:05,000\nAdd a callout to export queue.\n\n"
        "3\n00:00:05,500 --> 00:00:08,000\nEnd with captions and zoom.\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "min_real_cases": 1, "cases": []}), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "register_ai_edit_corpus_case.py",
            "--manifest",
            str(manifest),
            "--transcript",
            str(transcript),
            "--case-id",
            "real-product-demo",
            "--prompt",
            "Turn this real product recording into a clean launch demo with captions and callouts",
            "--language",
            "en",
            "--scenario",
            "product",
            "--expected-intent",
            "product_demo",
            "--required-operations",
            "apply_preset,add_callout,add_auto_zoom,create_subtitles",
            "--min-segments",
            "3",
        ],
    )

    assert register_ai_edit_corpus_case.main() == 0
    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    cases, meta = load_ai_edit_corpus_cases(manifest)
    report = build_ai_edit_corpus_quality_report(
        manifest_path=manifest,
        env={"TIGERCAPTURE_AI_PROVIDER": "rule_based"},
    )

    assert stdout["registered"] is True
    assert stdout["validation"]["ok"] is True
    assert payload["cases"][0]["fixture"] is False
    assert payload["cases"][0]["transcript_path"] == "transcripts/real-product-demo.srt"
    assert (tmp_path / "transcripts" / "real-product-demo.srt").is_file()
    assert meta["found"] is True
    assert cases[0]["id"] == "real-product-demo"
    assert cases[0]["transcript"].startswith("1\n")
    assert report["summary"]["real_cases"] == 1
    assert report["summary"]["fixture_cases"] == 0
    assert report["cases"][0]["ok"] is True


def test_register_ai_edit_corpus_case_cli_adds_filled_template(tmp_path, monkeypatch, capsys):
    from app.ai_edit_corpus_quality import build_ai_edit_corpus_quality_report
    from app.ai_edit_corpus_intake import ai_edit_case_template
    from tools import register_ai_edit_corpus_case

    transcript = tmp_path / "template-case.srt"
    transcript.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nOpen the project.\n\n"
        "2\n00:00:07,000 --> 00:00:09,000\nCut the waiting part.\n\n"
        "3\n00:00:12,000 --> 00:00:15,000\nAdd captions and zoom.\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "min_real_cases": 1, "cases": []}), encoding="utf-8")
    template_path = tmp_path / "ai-edit-real-04.template.json"
    template = ai_edit_case_template(4, template_path=template_path)
    template["manifest_case"]["transcript_path"] = str(transcript)
    template["manifest_case"]["prompt"] = "Turn this real product recording into a clean launch demo with captions and callouts"
    template_path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "register_ai_edit_corpus_case.py",
            "--manifest",
            str(manifest),
            "--from-template",
            str(template_path),
        ],
    )

    assert register_ai_edit_corpus_case.main() == 0
    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    report = build_ai_edit_corpus_quality_report(
        manifest_path=manifest,
        env={"TIGERCAPTURE_AI_PROVIDER": "rule_based"},
    )

    assert stdout["registered"] is True
    assert stdout["template_path"] == str(template_path)
    assert payload["cases"][0]["id"] == "ai-edit-real-04"
    assert payload["cases"][0]["fixture"] is False
    assert report["summary"]["real_cases"] == 1
    assert report["cases"][0]["ok"] is True


def test_register_ai_edit_corpus_templates_cli_batches_filled_templates(tmp_path, monkeypatch, capsys):
    from app.ai_edit_corpus_intake import ai_edit_case_template
    from app.ai_edit_corpus_quality import build_ai_edit_corpus_quality_report
    from tools import register_ai_edit_corpus_templates

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    transcript = tmp_path / "product.srt"
    transcript.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nShow the product dashboard.\n\n"
        "2\n00:00:02,500 --> 00:00:05,000\nAdd a callout to export queue.\n\n"
        "3\n00:00:05,500 --> 00:00:08,000\nEnd with captions and zoom.\n",
        encoding="utf-8",
    )
    filled_path = template_dir / "ai-edit-real-04.template.json"
    filled = ai_edit_case_template(4, template_path=filled_path)
    filled["manifest_case"]["transcript_path"] = str(transcript)
    filled["manifest_case"]["prompt"] = "Turn this real product recording into a clean launch demo with captions and callouts"
    filled_path.write_text(json.dumps(filled, ensure_ascii=False), encoding="utf-8")
    empty_path = template_dir / "ai-edit-real-05.template.json"
    empty_path.write_text(json.dumps(ai_edit_case_template(5, template_path=empty_path), ensure_ascii=False), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "min_real_cases": 1, "cases": []}), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "register_ai_edit_corpus_templates.py",
            "--template-dir",
            str(template_dir),
            "--manifest",
            str(manifest),
        ],
    )

    assert register_ai_edit_corpus_templates.main() == 0
    stdout = json.loads(capsys.readouterr().out)
    report = build_ai_edit_corpus_quality_report(
        manifest_path=manifest,
        env={"TIGERCAPTURE_AI_PROVIDER": "rule_based"},
    )

    assert stdout["summary"]["templates"] == 2
    assert stdout["summary"]["registered"] == 1
    assert stdout["summary"]["skipped_placeholder"] == 1
    assert report["summary"]["real_cases"] == 1
    assert report["cases"][0]["ok"] is True


def test_register_ai_edit_corpus_case_rejects_placeholder_prompt(tmp_path):
    from app.ai_edit_corpus_registration import register_ai_edit_corpus_case

    transcript = tmp_path / "case.srt"
    transcript.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nOne.\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nTwo.\n\n"
        "3\n00:00:02,000 --> 00:00:03,000\nThree.\n",
        encoding="utf-8",
    )

    report = register_ai_edit_corpus_case(
        manifest_path=tmp_path / "manifest.json",
        transcript_path=transcript,
        prompt="cut",
        language="en",
        scenario="tutorial",
        expected_intent="clean_tutorial",
        required_operations=["delete_time_range"],
        min_segments=3,
    )

    assert report["registered"] is False
    assert "natural_language_prompt" in report["missing"]
    assert not (tmp_path / "manifest.json").exists()
