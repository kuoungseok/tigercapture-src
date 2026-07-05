from __future__ import annotations

import subprocess
from pathlib import Path


def _write_video(path: Path) -> None:
    from imageio_ffmpeg import get_ffmpeg_exe

    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            get_ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x180:rate=10:duration=1",
            "-t",
            "1",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def test_default_review_sample_manifest_has_required_media_contracts(tmp_path):
    from app.review_automation.sample_resources import (
        build_default_review_sample_manifest,
        iter_review_sample_resources,
        review_sample_resource_report,
        write_review_sample_manifest,
    )

    root = tmp_path / "review_demos"
    manifest = build_default_review_sample_manifest(root)
    resources = list(iter_review_sample_resources(manifest))
    roles = {row.role for row in resources}
    ids = {row.id for row in resources}

    assert manifest["kind"] == "tigercapture_review_sample_resources"
    assert {"overview", "screenstudio_auto_polish", "ai_script_edit", "audio_voice"} <= roles
    assert "screenstudio_cursor_demo" in ids
    assert any(row.sidecars for row in resources if row.id == "screenstudio_cursor_demo")

    path = write_review_sample_manifest(root / "manifest.json", sample_root=root)
    assert path.exists()

    report = review_sample_resource_report(path)
    assert report["resource_count"] >= 5
    assert report["missing_required_count"] >= 1
    assert report["prepare_command"].endswith("tools\\prepare_review_sample_resources.py")


def test_prepare_review_sample_resources_prefers_imported_videos(tmp_path):
    from tools.prepare_review_sample_resources import prepare_review_sample_resources

    source_dir = tmp_path / "YouTube Imports"
    _write_video(source_dir / "editor-demo-a.mp4")
    _write_video(source_dir / "editor-demo-b.mp4")

    out_root = tmp_path / "review_demos"
    report = prepare_review_sample_resources(
        out_root,
        force=True,
        video_source_dir=source_dir,
    )

    assert report["ok"] is True
    assert report["video_source_mode"] == "youtube_imports"
    assert set(report["video_source_files"]) == {"overview_screen_demo", "screenstudio_cursor_demo"}
    assert (out_root / "media" / "overview_screen_demo.mp4").exists()
    assert (out_root / "media" / "screenstudio_cursor_demo.mp4").exists()
    video_rows = {
        row["id"]: row
        for row in report["resources"]
        if row.get("kind") == "video"
    }
    assert video_rows["overview_screen_demo"]["source_mode"] == "youtube_imports"
    assert video_rows["overview_screen_demo"]["source_ready"] is True


def test_prepare_review_sample_resources_rejects_missing_imported_videos(tmp_path):
    from tools.prepare_review_sample_resources import prepare_review_sample_resources

    out_root = tmp_path / "review_demos"
    report = prepare_review_sample_resources(
        out_root,
        force=True,
        video_source_dir=tmp_path / "missing YouTube Imports",
    )

    assert report["ok"] is False
    assert report["video_source_mode"] == "missing_youtube_imports"
    assert set(report["missing_youtube_import_source_ids"]) == {"overview_screen_demo", "screenstudio_cursor_demo"}
    assert not (out_root / "media" / "overview_screen_demo.mp4").exists()
    assert not (out_root / "media" / "screenstudio_cursor_demo.mp4").exists()


def test_review_sample_resources_are_exposed_in_qa_dashboard():
    from app.qa_dashboard import QADashboardDialog, REPORT_SPECS, _report_spec_path, _summary_for
    from app.review_automation.paths import (
        DEFAULT_REVIEW_QA_REPORT,
        DEFAULT_REVIEW_REPORT,
        DEFAULT_REVIEW_SAMPLE_REPORT,
        DEFAULT_REVIEW_SAMPLE_ROOT,
    )

    specs = {kind: (label, path) for label, path, kind in REPORT_SPECS}
    assert specs["review_sample_resources"] == (
        "Review Sample Resources",
        _report_spec_path(DEFAULT_REVIEW_SAMPLE_REPORT),
    )
    assert specs["review_automation"] == (
        "Review Automation",
        _report_spec_path(DEFAULT_REVIEW_REPORT),
    )
    assert specs["review_automation_qa"] == (
        "Review Automation QA",
        _report_spec_path(DEFAULT_REVIEW_QA_REPORT),
    )

    ok, summary, lines = _summary_for(
        "review_sample_resources",
        {
            "ok": True,
            "manifest_exists": True,
            "resource_count": 2,
            "ready_count": 1,
            "missing_required_count": 1,
            "resources": [
                {
                    "id": "overview_screen_demo",
                    "kind": "video",
                    "role": "overview",
                    "path": "qa_corpus/review_demos/media/overview_screen_demo.mp4",
                    "ready": True,
                },
                {
                    "id": "screenstudio_cursor_demo",
                    "kind": "video",
                    "role": "screenstudio_auto_polish",
                    "path": "qa_corpus/review_demos/media/screenstudio_cursor_demo.mp4",
                    "ready": False,
                    "sidecars": [
                        {
                            "path": "qa_corpus/review_demos/media/screenstudio_cursor_demo.mp4.cursor.json",
                            "exists": False,
                        }
                    ],
                },
            ],
        },
    )

    assert ok is True
    assert "1/2 ready" in summary
    assert any("missing sidecar" in line for line in lines)

    cmd = QADashboardDialog._command_for_row(
        {
            "kind": "review_sample_resources",
            "path": str(DEFAULT_REVIEW_SAMPLE_REPORT),
        }
    )
    assert cmd is not None
    assert cmd[1:5] == [
        "tools/prepare_review_sample_resources.py",
        "--out-root",
        str(DEFAULT_REVIEW_SAMPLE_ROOT),
        "--report-out",
    ]
    assert Path(cmd[5]).as_posix() == Path(DEFAULT_REVIEW_SAMPLE_REPORT).as_posix()

    qa_cmd = QADashboardDialog._command_for_row(
        {
            "kind": "review_automation_qa",
            "path": str(DEFAULT_REVIEW_QA_REPORT),
        }
    )
    assert qa_cmd is not None
    assert qa_cmd[1:5] == ["tools/qa_review_automation.py", "--report", str(DEFAULT_REVIEW_REPORT), "--out"]
    assert Path(qa_cmd[5]).as_posix() == Path(DEFAULT_REVIEW_QA_REPORT).as_posix()
