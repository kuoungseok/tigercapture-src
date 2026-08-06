from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from PIL import Image


def _write_png(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (320, 180), color).save(path)


def _successful_runner(
    template: Mapping[str, Any],
    sample_dir: Path,
    timeout_seconds: int,
    capture_ui: bool,
    artboard_id: str,
) -> dict[str, Any]:
    renderer = sample_dir / "painter_umg_fwidget_renderer.png"
    editor = sample_dir / "painter_umg_unreal_editor.png"
    seed = sum(
        ord(character)
        for character in f"{template['id']}:{artboard_id}"
    )
    _write_png(renderer, (40 + seed % 80, 75, 130))
    if capture_ui:
        _write_png(editor, (30, 90 + seed % 80, 70))
    report = {
        "schema": "tigerstudio.painter.ui.unreal_umg_qa.v1",
        "ok": True,
        "template": {
            "id": str(template["id"]),
            "active_artboard_id": artboard_id,
        },
        "summary": {
            "generation_status": "passed",
            "reopen_status": "passed",
            "fwidget_renderer_status": "passed",
            "expected_layer_count": 8,
            "expected_widget_count": 8,
            "actual_generated_widget_count": 8,
            "blocked_layers": [],
        },
        "widget_render": {
            "ok": True,
            "output_path": str(renderer),
            "width": 320,
            "height": 180,
            "pixel_evidence": {"visible_content": True},
        },
        "visual_capture": (
            {
                "ok": True,
                "status": "captured",
                "path": str(editor),
                "backend": "wgc_window",
            }
            if capture_ui
            else {
                "ok": False,
                "status": "not_run",
                "reason": "capture_not_requested",
            }
        ),
    }
    report_path = sample_dir / "qa_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "returncode": 0,
        "duration_seconds": 0.25,
        "command": ["python", "tools/qa_painter_ui_unreal_umg.py"],
        "stdout_tail": "",
        "stderr_tail": "",
        "report_path": str(report_path),
        "report": report,
        "resumed": False,
    }


def test_batch_discovers_every_builtin_in_catalog_order() -> None:
    from app.painter_ui_templates import list_ui_templates
    from tools.qa_painter_ui_unreal_umg_batch import (
        discover_builtin_samples,
    )

    expected = [row["id"] for row in list_ui_templates()]

    assert [row["id"] for row in discover_builtin_samples()] == expected
    assert [
        row["id"]
        for row in discover_builtin_samples(
            [expected[2], expected[0], expected[2]]
        )
    ] == [expected[2], expected[0]]


def test_batch_discovers_all_21_builtin_artboard_targets() -> None:
    from tools.qa_painter_ui_unreal_umg_batch import (
        discover_builtin_sample_targets,
    )

    targets = discover_builtin_sample_targets(all_artboards=True)

    assert len(targets) == 21
    assert sum(bool(row["artboard"]["is_default"]) for row in targets) == 12
    assert targets[0]["template"]["id"] == "mobile_onboarding"
    assert [
        row["artboard"]["id"]
        for row in targets
        if row["template"]["id"] == "mobile_onboarding"
    ] == ["artboard-1", "artboard-2", "artboard-3"]


def test_batch_writes_per_sample_reports_index_and_contact_sheet(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_unreal_umg_batch import (
        discover_builtin_samples,
        run_batch_qa,
    )

    template_ids = [
        row["id"] for row in discover_builtin_samples()[:2]
    ]
    report = run_batch_qa(
        tmp_path / "batch",
        timeout_seconds=77,
        capture_ui=True,
        template_ids=template_ids,
        runner=_successful_runner,
    )

    assert report["ok"] is True
    assert report["summary"] == {
        "total": 2,
        "template_count": 2,
        "screen_count": 2,
        "passed": 2,
        "failed": 0,
        "renderer_captures": 2,
        "editor_screenshots": 2,
        "duration_seconds": report["summary"]["duration_seconds"],
    }
    assert report["contact_sheet"]["ok"] is True
    assert report["contact_sheet"]["screen_count"] == 2
    assert report["contact_sheet"]["cell_count"] == 4
    assert report["contact_sheet"]["source_image_count"] == 4
    for key in ("report", "index", "contact_sheet"):
        assert Path(report["paths"][key]).is_file()
    assert len({row["sample_dir"] for row in report["samples"]}) == 2
    for row in report["samples"]:
        sample_dir = Path(row["sample_dir"])
        assert sample_dir.parent.name == "samples"
        assert (sample_dir / "qa_report.json").is_file()
        assert (sample_dir / "batch_sample.json").is_file()
        assert Path(row["renderer"]["path"]).is_file()
        assert Path(row["editor_screenshot"]["path"]).is_file()
    markdown = Path(report["paths"]["index"]).read_text(encoding="utf-8")
    assert "FWidgetRenderer" not in markdown
    assert all(template_id in markdown for template_id in template_ids)
    assert "[render](samples/" in markdown
    assert "[editor](samples/" in markdown


def test_batch_continues_after_failure_and_keeps_contact_placeholder(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_unreal_umg_batch import (
        discover_builtin_samples,
        run_batch_qa,
    )

    templates = discover_builtin_samples()[:2]
    calls: list[str] = []

    def mixed_runner(
        template: Mapping[str, Any],
        sample_dir: Path,
        timeout_seconds: int,
        capture_ui: bool,
        artboard_id: str,
    ) -> dict[str, Any]:
        calls.append(str(template["id"]))
        if len(calls) == 2:
            return _successful_runner(
                template,
                sample_dir,
                timeout_seconds,
                capture_ui,
                artboard_id,
            )
        report = {
            "ok": False,
            "summary": {
                "generation_status": "failed",
                "reopen_status": "not_run",
                "fwidget_renderer_status": "not_run",
            },
            "widget_render": {
                "ok": False,
                "message": "generation_failed_before_render",
            },
            "visual_capture": {
                "ok": False,
                "status": "not_run",
                "reason": "reopen_failed_before_capture",
            },
        }
        report_path = sample_dir / "qa_report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return {
            "returncode": 1,
            "duration_seconds": 0.1,
            "report_path": str(report_path),
            "report": report,
        }

    report = run_batch_qa(
        tmp_path / "batch",
        capture_ui=True,
        template_ids=[row["id"] for row in templates],
        runner=mixed_runner,
    )

    assert calls == [row["id"] for row in templates]
    assert report["ok"] is False
    assert report["summary"]["passed"] == 1
    assert report["summary"]["failed"] == 1
    assert report["contact_sheet"]["ok"] is True
    assert report["contact_sheet"]["cell_count"] == 4
    assert report["contact_sheet"]["placeholder_count"] == 2


def test_failed_run_does_not_count_stale_capture_files(tmp_path: Path) -> None:
    from tools.qa_painter_ui_unreal_umg_batch import (
        discover_builtin_samples,
        run_batch_qa,
    )

    template_id = str(discover_builtin_samples()[0]["id"])

    def failed_runner(
        template: Mapping[str, Any],
        sample_dir: Path,
        timeout_seconds: int,
        capture_ui: bool,
        artboard_id: str,
    ) -> dict[str, Any]:
        _write_png(sample_dir / "painter_umg_fwidget_renderer.png", (1, 2, 3))
        _write_png(sample_dir / "painter_umg_unreal_editor.png", (4, 5, 6))
        report = {
            "ok": False,
            "summary": {
                "generation_status": "passed",
                "reopen_status": "passed",
                "fwidget_renderer_status": "failed",
            },
            "widget_render": {"ok": False},
            "visual_capture": {
                "ok": False,
                "status": "failed",
                "reason": "unreal_asset_editor_did_not_signal_ready",
            },
        }
        report_path = sample_dir / "qa_report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return {
            "returncode": 1,
            "duration_seconds": 0.1,
            "report_path": str(report_path),
            "report": report,
        }

    report = run_batch_qa(
        tmp_path / "batch",
        capture_ui=True,
        template_ids=[template_id],
        runner=failed_runner,
    )

    assert report["summary"]["renderer_captures"] == 0
    assert report["summary"]["editor_screenshots"] == 0
    assert report["contact_sheet"]["source_image_count"] == 0
    assert report["contact_sheet"]["placeholder_count"] == 2
    sample = report["samples"][0]
    assert sample["renderer"]["exists"] is False
    assert sample["editor_screenshot"]["exists"] is False


def test_all_artboards_resume_reuses_legacy_active_directories(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_unreal_umg_batch import (
        discover_builtin_samples,
        run_batch_qa,
    )

    template_ids = [
        row["id"] for row in discover_builtin_samples()[:2]
    ]
    workspace = tmp_path / "batch"
    initial = run_batch_qa(
        workspace,
        capture_ui=False,
        template_ids=template_ids,
        runner=_successful_runner,
    )
    assert initial["summary"]["screen_count"] == 2

    added_calls: list[tuple[str, str]] = []

    def added_runner(
        template: Mapping[str, Any],
        sample_dir: Path,
        timeout_seconds: int,
        capture_ui: bool,
        artboard_id: str,
    ) -> dict[str, Any]:
        added_calls.append((str(template["id"]), artboard_id))
        return _successful_runner(
            template,
            sample_dir,
            timeout_seconds,
            capture_ui,
            artboard_id,
        )

    expanded = run_batch_qa(
        workspace,
        capture_ui=False,
        template_ids=template_ids,
        all_artboards=True,
        resume=True,
        runner=added_runner,
    )

    assert expanded["summary"]["template_count"] == 2
    assert expanded["summary"]["screen_count"] == 5
    assert added_calls == [
        ("mobile_onboarding", "artboard-2"),
        ("mobile_onboarding", "artboard-3"),
        ("mobile_finance", "artboard-2"),
    ]
    active_rows = [
        row for row in expanded["samples"] if row["artboard"]["is_default"]
    ]
    assert len(active_rows) == 2
    assert all(row["execution"]["resumed"] for row in active_rows)
    assert Path(active_rows[0]["sample_dir"]).name == "01_mobile_onboarding"
    assert {
        Path(row["sample_dir"]).name
        for row in expanded["samples"]
        if not row["artboard"]["is_default"]
    } == {
        "01_mobile_onboarding__artboard-2",
        "01_mobile_onboarding__artboard-3",
        "02_mobile_finance__artboard-2",
    }


def test_resume_reruns_when_editor_capture_is_now_required(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_unreal_umg_batch import (
        discover_builtin_samples,
        run_batch_qa,
    )

    template_id = str(discover_builtin_samples()[0]["id"])
    workspace = tmp_path / "batch"
    initial = run_batch_qa(
        workspace,
        capture_ui=False,
        template_ids=[template_id],
        runner=_successful_runner,
    )
    assert initial["ok"] is True
    assert initial["summary"]["editor_screenshots"] == 0

    calls: list[str] = []

    def capture_runner(
        template: Mapping[str, Any],
        sample_dir: Path,
        timeout_seconds: int,
        capture_ui: bool,
        artboard_id: str,
    ) -> dict[str, Any]:
        calls.append(str(template["id"]))
        return _successful_runner(
            template,
            sample_dir,
            timeout_seconds,
            capture_ui,
            artboard_id,
        )

    captured = run_batch_qa(
        workspace,
        capture_ui=True,
        template_ids=[template_id],
        resume=True,
        runner=capture_runner,
    )

    assert calls == [template_id]
    assert captured["ok"] is True
    assert captured["summary"]["editor_screenshots"] == 1
    assert captured["samples"][0]["execution"]["resumed"] is False
