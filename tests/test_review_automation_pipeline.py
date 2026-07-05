from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path


def _write_png(path: Path, color: tuple[int, int, int] = (32, 64, 120)) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 360), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((32, 32, 608, 328), outline=(220, 235, 255), width=4)
    draw.text((56, 56), path.stem, fill=(245, 248, 255))
    image.save(path)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _make_fake_project(root: Path) -> Path:
    from app.review_automation.artifacts import feature_editor_surface_artifact_id, feature_editor_surface_specs

    for name in ("SPEC.md", "README.md", "TODO.md"):
        (root / name).write_text(f"# {name}\n", encoding="utf-8")
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/RELEASE_POSITIONING.md").write_text("safe claims only\n", encoding="utf-8")
    (root / "docs/SPEC_REVIEW_AUTOMATION.md").write_text("review automation\n", encoding="utf-8")

    for name in ("editor_imported", "editor_empty", "editor_actor_project", "preview_popout"):
        _write_png(root / "debugCapture/editor_e2e_smoke" / f"{name}.png")
    _write_png(root / "debugCapture/editor_e2e_smoke/editor_e2e_smoke_contact_sheet.png", (44, 88, 72))
    _write_json(root / "debugCapture/editor_e2e_smoke_report.json", {"ok": True, "summary": {"screenshots": 5}})
    for spec in feature_editor_surface_specs():
        _write_png(
            root / "debugCapture/review_automation/assets" / f"{feature_editor_surface_artifact_id(str(spec.get('id')))}.png",
            (54, 76, 112),
        )

    media = root / "qa_corpus/review_demos/media"
    media.mkdir(parents=True, exist_ok=True)
    _write_png(media / "review_overview_poster.png", (18, 24, 44))
    _write_video(media / "overview_screen_demo.mp4")
    _write_video(media / "screenstudio_cursor_demo.mp4")
    (media / "dialogue_cleanup_demo.wav").write_bytes(b"fake")
    (media / "screenstudio_cursor_demo.mp4.cursor.json").write_text("{}", encoding="utf-8")
    (media / "ai_script_transcript_demo.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "kind": "tigercapture_review_sample_resources",
        "sample_root": "qa_corpus/review_demos",
        "media_root": "qa_corpus/review_demos/media",
        "resources": [
            {
                "id": "overview_screen_demo",
                "kind": "video",
                "path": "qa_corpus/review_demos/media/overview_screen_demo.mp4",
                "role": "overview",
                "title": "Overview video",
                "required": True,
                "metadata": {
                    "requires_youtube_import_source": True,
                    "source_mode": "youtube_imports",
                    "source_path": "YouTube Imports/editor-demo-a.mp4",
                },
            },
            {
                "id": "screenstudio_cursor_demo",
                "kind": "video",
                "path": "qa_corpus/review_demos/media/screenstudio_cursor_demo.mp4",
                "role": "screenstudio_auto_polish",
                "title": "Cursor video",
                "required": True,
                "sidecars": ["qa_corpus/review_demos/media/screenstudio_cursor_demo.mp4.cursor.json"],
                "metadata": {
                    "requires_youtube_import_source": True,
                    "source_mode": "youtube_imports",
                    "source_path": "YouTube Imports/editor-demo-b.mp4",
                },
            },
            {
                "id": "dialogue_cleanup_demo",
                "kind": "audio",
                "path": "qa_corpus/review_demos/media/dialogue_cleanup_demo.wav",
                "role": "audio_voice",
                "title": "Audio",
                "required": True,
            },
            {
                "id": "ai_script_transcript_demo",
                "kind": "transcript",
                "path": "qa_corpus/review_demos/media/ai_script_transcript_demo.srt",
                "role": "ai_script_edit",
                "title": "Transcript",
                "required": True,
            },
            {
                "id": "review_overview_poster",
                "kind": "image",
                "path": "qa_corpus/review_demos/media/review_overview_poster.png",
                "role": "html_deck",
                "title": "Poster",
                "required": True,
            },
        ],
    }
    manifest_path = root / "qa_corpus/review_demos/manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def test_review_automation_generates_report_html_and_pptx(tmp_path):
    from app.review_automation.runner import build_review_automation_report
    from app.review_automation.qa import validate_review_automation_report

    manifest_path = _make_fake_project(tmp_path)
    report_path = tmp_path / "debugCapture/review_automation/review_report.json"
    report = build_review_automation_report(
        project_root=tmp_path,
        out_dir=tmp_path / "debugCapture/review_automation",
        report_path=report_path,
        sample_manifest=manifest_path,
        write_html=True,
        write_ppt=True,
        force=True,
    )

    assert report["ok"] is True
    assert report["summary"]["features"] >= 6
    assert report["summary"]["scenarios"] >= 6
    assert report["summary"]["scenario_ready"] >= 1
    assert report["summary"]["feature_action_scenarios"] >= 10
    assert report["summary"]["feature_action_ready"] >= 10
    assert report["summary"]["sample_resources_ready"] == 5
    assert report["scenarios"]
    assert report["feature_action_scenarios"]
    assert report["evidence_graph"]["summary"]["nodes"] >= report["summary"]["features"]
    assert report["evidence_graph"]["summary"]["feature_action_scenarios"] >= 10
    assert report_path.exists()
    artifacts = {str(row.get("id")): row for row in report["artifacts"]}
    assert artifacts["catalog_editor_surface"]["exists"] is True
    assert artifacts["catalog_editor_surface"]["public"] is True
    assert artifacts["catalog_editor_surface"]["active_editor"] is True
    assert artifacts["catalog_editor_surface"]["catalog_rule"] == "no_empty_editor"
    assert "editor_empty" not in str(artifacts["catalog_editor_surface"]["source_path"])
    assert artifacts["catalog_timeline_detail"]["exists"] is True
    assert artifacts["catalog_timeline_detail"]["active_editor"] is True
    assert artifacts["catalog_timeline_detail"]["catalog_rule"] == "no_empty_editor"
    feature_editor_artifacts = [
        row for row in artifacts.values() if row.get("feature_editor") is True
    ]
    assert len(feature_editor_artifacts) >= 10
    assert artifacts["feature_timeline_editing_editor_surface"]["exists"] is True
    assert artifacts["feature_color_audio_vfx_editor_surface"]["exists"] is True
    assert artifacts["feature_action_scenarios"]["exists"] is True
    assert artifacts["evidence_graph"]["exists"] is True
    feature_actions = {str(row.get("topic_id")): row for row in report["feature_action_scenarios"]}
    assert feature_actions["timeline_editing"]["status"] == "action_plan_ready"
    assert feature_actions["timeline_editing"]["dry_run_ok"] is True
    assert "timeline.split" in feature_actions["timeline_editing"]["action_ids"]
    assert "capture.screenshot" in feature_actions["timeline_editing"]["action_ids"]
    assert feature_actions["color_audio_vfx"]["artifact_id"] == "feature_color_audio_vfx_editor_surface"

    html_path = tmp_path / report["outputs"]["html"]
    ppt_path = tmp_path / report["outputs"]["pptx"]
    assert html_path.exists()
    html_text = html_path.read_text(encoding="utf-8")
    assert "TigerCapture Review Automation" in html_text
    assert "Automation Scenarios" in html_text
    feature_pages = report["outputs"]["feature_pages"]
    assert len(feature_pages) == report["summary"]["features"]
    first_feature_page = tmp_path / feature_pages[0]
    assert first_feature_page.exists()
    first_feature_text = first_feature_page.read_text(encoding="utf-8")
    assert "Evidence Media" in first_feature_text
    assert "Automation Scenarios" in first_feature_text
    assert ppt_path.exists()
    with zipfile.ZipFile(ppt_path) as zf:
        names = set(zf.namelist())
    assert "ppt/presentation.xml" in names
    assert "ppt/slides/slide1.xml" in names

    qa = validate_review_automation_report(report_path, project_root=tmp_path)
    assert qa["failures"] == []
    assert qa["ok"] is True
    assert qa["summary"]["html_pages"] == report["summary"]["features"] + 1
    assert qa["summary"]["scenarios"] == report["summary"]["scenarios"]
    assert qa["summary"]["visual_artifacts_checked"] >= 1
    assert qa["summary"]["slides"] >= 1
    assert qa["summary"]["catalog_active_editor_artifacts"] == 2
    assert qa["summary"]["feature_editor_artifacts"] >= 10
    assert qa["summary"]["feature_editor_artifacts_required"] >= 10
    assert qa["summary"]["feature_action_scenarios"] >= 10
    assert qa["summary"]["feature_action_scenarios_required"] >= 10
    assert qa["summary"]["feature_action_ready"] >= 10


def test_review_action_scenario_generates_evidence_and_report_artifacts(tmp_path):
    from app.review_automation.action_scenarios import run_action_review_scenario
    from app.review_automation.runner import build_review_automation_report

    manifest_path = _make_fake_project(tmp_path)
    out_dir = tmp_path / "debugCapture/review_automation"
    scenario = run_action_review_scenario(
        project_root=tmp_path,
        out_dir=out_dir,
        sample_manifest=manifest_path,
        scenario="action-demo",
        force=True,
    )

    assert scenario["ok"] is True
    assert scenario["actions_executed"] >= 10
    assert (tmp_path / scenario["evidence_path"]).exists()
    assert (tmp_path / scenario["storyboard_path"]).exists()

    report = build_review_automation_report(
        project_root=tmp_path,
        out_dir=out_dir,
        report_path=out_dir / "review_report.json",
        sample_manifest=manifest_path,
        write_html=False,
        write_ppt=False,
        force=True,
    )
    artifacts = {str(row.get("id")): row for row in report["artifacts"]}
    assert artifacts["action_scenario_timeline"]["exists"] is True
    assert artifacts["action_scenario_report"]["exists"] is True
    assert artifacts["action_scenario_youtube_frame"]["exists"] is True
    assert artifacts["evidence_graph"]["exists"] is True


class _LiveReviewPixmap:
    def save(self, path: str) -> bool:
        _write_png(Path(path), (64, 48, 108))
        return True


class _LiveReviewOwner:
    def __init__(self) -> None:
        self._tracks = []
        self._audio_tracks = []
        self._timeline_markers = []
        self._selected_clips = []
        self._project_settings = {}
        self.changes: list[str] = []
        self.refresh_count = 0
        self.width_count = 0
        self.marker_sync_count = 0

    def _register_change(self, label: str = "") -> None:
        self.changes.append(str(label or ""))

    def _refresh_player_tracks(self) -> None:
        self.refresh_count += 1

    def _update_tracks_host_width(self) -> None:
        self.width_count += 1

    def _sync_markers_to_ruler(self) -> None:
        self.marker_sync_count += 1

    def grab(self) -> _LiveReviewPixmap:
        return _LiveReviewPixmap()


def test_live_feature_action_runner_executes_owner_actions_and_overlays_report(tmp_path):
    from app.review_automation.live_runner import run_live_review_scenario
    from app.review_automation.runner import build_review_automation_report

    manifest_path = _make_fake_project(tmp_path)
    out_dir = tmp_path / "debugCapture/review_automation"
    owner = _LiveReviewOwner()
    live = run_live_review_scenario(
        owner,
        "timeline_editing",
        {
            "project_root": str(tmp_path),
            "out_dir": str(out_dir),
            "sample_manifest": str(manifest_path),
        },
    )

    assert live["ok"] is True
    assert live["live_capture_count"] == 1
    assert owner.changes
    assert owner.refresh_count >= 1
    live_row = live["scenarios"][0]
    assert live_row["status"] == "live_captured"
    assert (tmp_path / live_row["artifact_path"]).exists()
    assert any(row["action"] == "capture.screenshot" and row["ok"] for row in live_row["live_result"]["results"])

    report = build_review_automation_report(
        project_root=tmp_path,
        out_dir=out_dir,
        report_path=out_dir / "review_report.json",
        sample_manifest=manifest_path,
        write_html=False,
        write_ppt=False,
        force=True,
    )
    feature_actions = {str(row.get("topic_id")): row for row in report["feature_action_scenarios"]}
    assert feature_actions["timeline_editing"]["status"] == "live_captured"
    assert feature_actions["timeline_editing"]["live_capture"] is True


def test_review_automation_deck_modes_generate_different_depths(tmp_path):
    from app.review_automation.runner import build_review_automation_report

    manifest_path = _make_fake_project(tmp_path)
    expected_minimums = {
        "summary": 4,
        "detailed": 20,
        "evidence-full": 70,
    }
    slide_counts: dict[str, int] = {}
    for mode, minimum in expected_minimums.items():
        report = build_review_automation_report(
            project_root=tmp_path,
            out_dir=tmp_path / "debugCapture/review_automation",
            report_path=tmp_path / "debugCapture/review_automation" / f"review_report_{mode}.json",
            sample_manifest=manifest_path,
            write_html=False,
            write_ppt=True,
            deck_mode=mode,
            force=True,
        )
        assert report["deck_mode"] == mode
        ppt_path = tmp_path / report["outputs"]["pptx"]
        assert ppt_path.exists()
        with zipfile.ZipFile(ppt_path) as zf:
            slide_count = len(
                [
                    name
                    for name in zf.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                ]
            )
        slide_counts[mode] = slide_count
        assert slide_count >= minimum

    assert slide_counts["summary"] < slide_counts["detailed"] < slide_counts["evidence-full"]
