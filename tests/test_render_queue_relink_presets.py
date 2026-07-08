from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import MethodType, SimpleNamespace


def test_render_queue_store_persists_status(tmp_path):
    from app.render_queue import RenderQueueJob, RenderQueueStore

    queue_path = tmp_path / "render_queue.json"
    store = RenderQueueStore(queue_path)
    job_id = store.add(
        RenderQueueJob.create(
            label="Segment 1",
            out_path=str(tmp_path / "out.mp4"),
            in_ms=0,
            out_ms=1000,
        )
    )
    store.update_status(job_id, "done")

    loaded = RenderQueueStore(queue_path)

    assert loaded.summary()["done"] == 1
    assert loaded.jobs[0].label == "Segment 1"


def test_render_queue_store_retries_and_removes_jobs(tmp_path):
    from app.render_queue import RenderQueueJob, RenderQueueStore

    queue_path = tmp_path / "render_queue.json"
    store = RenderQueueStore(queue_path)
    failed_id = store.add(
        RenderQueueJob.create(
            label="Failed",
            out_path=str(tmp_path / "failed.mp4"),
            in_ms=0,
            out_ms=1000,
        )
    )
    done_id = store.add(
        RenderQueueJob.create(
            label="Done",
            out_path=str(tmp_path / "done.mp4"),
            in_ms=1000,
            out_ms=2000,
        )
    )
    store.update_status(failed_id, "error", error="encoder failed")
    store.update_status(done_id, "done")

    assert store.retry_failed() == 1
    assert store.summary()["pending"] == 1
    assert store.jobs[0].error == ""

    assert store.remove_jobs([done_id]) == 1
    loaded = RenderQueueStore(queue_path)
    assert [job.id for job in loaded.jobs] == [failed_id]


def test_render_queue_store_prunes_old_terminal_history(tmp_path):
    from app.render_queue import RenderQueueJob, RenderQueueStore

    queue_path = tmp_path / "render_queue.json"
    store = RenderQueueStore(queue_path)
    now = int(time.time())
    old = now - 45 * 24 * 60 * 60

    old_done = RenderQueueJob.create(
        label="Old Done",
        out_path=str(tmp_path / "old_done.mp4"),
        in_ms=0,
        out_ms=1000,
    )
    old_done.status = "done"
    old_done.created_at = old
    old_done.updated_at = old
    old_done.finished_at = old
    old_error = RenderQueueJob.create(
        label="Old Error",
        out_path=str(tmp_path / "old_error.mp4"),
        in_ms=0,
        out_ms=1000,
    )
    old_error.status = "error"
    old_error.created_at = old
    old_error.updated_at = old
    old_error.finished_at = old
    recent_done = RenderQueueJob.create(
        label="Recent Done",
        out_path=str(tmp_path / "recent.mp4"),
        in_ms=0,
        out_ms=1000,
    )
    recent_done.status = "done"
    recent_done.finished_at = now
    pending = RenderQueueJob.create(
        label="Pending",
        out_path=str(tmp_path / "pending.mp4"),
        in_ms=0,
        out_ms=1000,
    )
    store.replace([old_done, old_error, recent_done, pending])

    assert store.prune_terminal_history(older_than_days=30, keep_latest=200) == 2

    loaded = RenderQueueStore(queue_path)
    labels = [job.label for job in loaded.jobs]
    assert labels == ["Recent Done", "Pending"]


def test_render_queue_store_prunes_terminal_history_to_latest_cap(tmp_path):
    from app.render_queue import RenderQueueJob, RenderQueueStore

    queue_path = tmp_path / "render_queue.json"
    store = RenderQueueStore(queue_path)
    now = int(time.time())
    jobs = []
    for idx in range(3):
        job = RenderQueueJob.create(
            label=f"Done {idx}",
            out_path=str(tmp_path / f"done_{idx}.mp4"),
            in_ms=0,
            out_ms=1000,
        )
        job.status = "done"
        job.created_at = now - idx
        job.updated_at = now - idx
        job.finished_at = now - idx
        jobs.append(job)
    store.replace(jobs)

    assert store.prune_terminal_history(older_than_days=30, keep_latest=1) == 2

    loaded = RenderQueueStore(queue_path)
    assert [job.label for job in loaded.jobs] == ["Done 0"]


def test_render_queue_store_pause_resume_progress_and_diagnostics(tmp_path):
    from app.render_queue import RenderQueueJob, RenderQueueStore

    queue_path = tmp_path / "render_queue.json"
    store = RenderQueueStore(queue_path)
    job_id = store.add(
        RenderQueueJob.create(
            label="Queued",
            out_path=str(tmp_path / "queued.mp4"),
            in_ms=0,
            out_ms=1000,
            format_id="mp4",
            quality_id="high",
        )
    )

    assert store.pause_pending() == 1
    assert store.jobs[0].status == "paused"
    assert store.resume_paused() == 1
    assert store.jobs[0].status == "pending"

    store.update_status(job_id, "running", diagnostics="encoder started")
    store.update_progress(job_id, 42, diagnostics="frame 42")
    store.update_status(job_id, "done", diagnostics="encoder completed")

    loaded = RenderQueueStore(queue_path)
    job = loaded.jobs[0]
    assert job.status == "done"
    assert job.progress == 100
    assert job.started_at > 0
    assert job.finished_at >= job.started_at
    assert job.diagnostics == "encoder completed"


def test_render_queue_panel_appends_export_color_qa_diagnostics(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.render_queue import RenderQueueStore
    from app.render_queue_panel import RenderQueuePanel

    QApplication.instance() or QApplication([])
    queue_path = tmp_path / "render_queue.json"
    panel = RenderQueuePanel(store=RenderQueueStore(queue_path))
    monkeypatch.setattr(
        "app.color_management.probe_export_color_metadata",
        lambda _path, settings: {
            "diagnostics": f"Color QA: OK ({settings['color_management']['output_space']})",
        },
    )
    item = SimpleNamespace(
        label="Segment",
        out_path=str(tmp_path / "out.mp4"),
        in_ms=0,
        out_ms=1000,
        status="pending",
        error="",
    )

    ids = panel.queue_items(
        [item],
        lambda *_args, **_kwargs: None,
        project_settings={"color_management": {"output_space": "Rec.709"}},
    )
    panel._current_job_id = ids[0]
    panel._on_success(tmp_path / "out.mp4", 2048)
    panel._on_done()

    loaded = RenderQueueStore(queue_path)
    assert loaded.jobs[0].status == "done"
    assert "Color QA: OK (Rec.709)" in loaded.jobs[0].diagnostics
    panel.deleteLater()


def test_render_queue_panel_writes_screenstudio_completion_manifest(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.render_queue import RenderQueueStore
    from app.render_queue_panel import RenderQueuePanel, render_preflight_card_detail_text

    QApplication.instance() or QApplication([])
    queue_path = tmp_path / "render_queue.json"
    panel = RenderQueuePanel(store=RenderQueueStore(queue_path))
    out = tmp_path / "screen_demo.mp4"
    out.write_bytes(b"fake export")
    item = SimpleNamespace(
        label="Screen Demo",
        out_path=str(out),
        in_ms=0,
        out_ms=1000,
        status="pending",
        error="",
    )

    ids = panel.queue_items(
        [item],
        lambda *_args, **_kwargs: None,
        format_id="mp4",
        quality_id="high",
        project_settings={
            "starter_template_id": "screen-recording-demo",
            "canvas_width": 1920,
            "canvas_height": 1080,
            "fps": 60.0,
        },
    )
    panel._current_job_id = ids[0]
    panel._on_success(out, out.stat().st_size)
    panel._on_done()

    manifest = out.with_name(out.name + ".share.json")
    loaded = RenderQueueStore(queue_path)
    job = loaded.jobs[0]
    detail = panel._diagnostics_text_for_job(job)

    assert manifest.exists()
    assert job.status == "done"
    assert "Screen Studio completion" in job.diagnostics
    assert "Export Completion:" in detail
    assert "Share Manifest:" in detail
    assert "Reveal output" in detail
    panel.deleteLater()


def test_render_queue_panel_preserves_readiness_preflight_diagnostics(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.render_queue import RenderQueueStore
    from app.render_queue_panel import RenderQueuePanel, render_preflight_card_detail_text

    QApplication.instance() or QApplication([])
    queue_path = tmp_path / "render_queue.json"
    panel = RenderQueuePanel(store=RenderQueueStore(queue_path))
    item = SimpleNamespace(
        label="Segment",
        out_path=str(tmp_path / "out.mp4"),
        in_ms=0,
        out_ms=1000,
        status="pending",
        error="",
    )
    preflight = (
        "Professional Readiness: Review score=72 high=1 medium=2 low=0\n"
        "Readiness Actions:\n"
        "- Assign dialogue and music buses."
    )

    ids = panel.queue_items(
        [item],
        lambda *_args, **_kwargs: None,
        format_id="mp4",
        quality_id="high",
        preflight_diagnostics=preflight,
    )
    loaded = RenderQueueStore(queue_path)
    assert "Professional Readiness" in loaded.jobs[0].diagnostics

    job = panel._job_by_id(ids[0])
    diagnostics = panel._diagnostics_for_job(job, "Encoder started")

    assert "Encoder started" in diagnostics
    assert "format=mp4" in diagnostics
    assert "Professional Readiness: Review" in diagnostics
    assert "Assign dialogue and music buses" in diagnostics
    assert len(panel._preflight_card_buttons) == 1
    assert panel._preflight_card_buttons[0].property("preflightCard") == "true"
    assert panel._preflight_card_buttons[0].property("preflightState") == "review"
    detail = render_preflight_card_detail_text(
        {"id": "readiness", "label": "Professional Readiness", "state_label": "Review", "summary": "score=72", "detail": preflight.splitlines()[0]},
        preflight,
    )
    assert "Related:" in detail
    assert "Assign dialogue and music buses" in detail
    panel.deleteLater()


def test_render_queue_preflight_card_parser_summarizes_export_qa():
    from app.render_queue_panel import (
        render_preflight_card_action_specs,
        render_preflight_card_detail_text,
        render_preflight_card_summary_text,
        render_preflight_cards_from_text,
    )

    text = (
        "Professional Readiness: Review score=72 high=1 medium=2 low=0\n"
        "Color Scope QA: OK | waveform Δ=0.01 vectorscope Δ=0.02\n"
        "Audio Delivery QA: Review | target=shortform | LUFS=-10.0/-14.0\n"
        "VFX Graph QA: OK | graphs=1 nodes=5"
    )

    cards = render_preflight_cards_from_text(text)
    summary = render_preflight_card_summary_text(text)

    assert [card["id"] for card in cards] == [
        "readiness",
        "color_scope",
        "audio_delivery",
        "vfx_graph",
    ]
    assert cards[0]["state"] == "review"
    assert cards[1]["state"] == "ok"
    assert cards[2]["state"] == "review"
    assert "Professional Readiness: Review" in summary
    assert "Color Scope QA: OK" in summary
    detail = render_preflight_card_detail_text(cards[2], text)
    assert "Audio Delivery QA" in detail
    assert "Status: Review" in detail
    assert [row["id"] for row in render_preflight_card_action_specs(cards[0])] == ["health", "qa_dashboard"]
    assert [row["id"] for row in render_preflight_card_action_specs(cards[1])] == ["color_page", "qa_dashboard"]
    assert [row["id"] for row in render_preflight_card_action_specs(cards[2])] == ["audio_mixer", "qa_dashboard"]


def test_render_queue_preflight_card_actions_route_to_editor_slots(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QWidget

    from app.render_queue import RenderQueueStore
    from app.render_queue_panel import RenderQueuePanel

    QApplication.instance() or QApplication([])

    class Host(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def _open_color_page(self):
            self.calls.append("color")

        def _on_audio_mixer_toggled(self, checked):
            self.calls.append(("audio", bool(checked)))

        def _show_media_health(self):
            self.calls.append("health")

        def _open_qa_dashboard(self):
            self.calls.append("qa")

        def _show_preset_application_corpus_report(self):
            self.calls.append("preset")

    host = Host()
    panel = RenderQueuePanel(host, store=RenderQueueStore(tmp_path / "render_queue.json"))

    assert panel._run_preflight_card_action("color_page") is True
    assert panel._run_preflight_card_action("audio_mixer") is True
    assert panel._run_preflight_card_action("health") is True
    assert panel._run_preflight_card_action("qa_dashboard") is True
    assert panel._run_preflight_card_action("preset_qa") is True
    assert host.calls == ["color", ("audio", True), "health", "qa", "preset"]
    panel.deleteLater()
    host.deleteLater()


def test_audio_delivery_preflight_text_for_render_queue_tracks():
    from app.render_queue_panel import audio_delivery_preflight_text_for_tracks

    text = audio_delivery_preflight_text_for_tracks(
        [
            SimpleNamespace(id=1, label="Voice", role="dialogue", bus_id="dialogue"),
            SimpleNamespace(id=2, label="Music", role="music", bus_id="music"),
        ],
        measured={"integrated_lufs": -14.2, "true_peak_db": -1.1, "lra": 8.0},
        target="shortform",
    )

    assert "Audio Delivery QA: OK" in text
    assert "routes=2" in text
    assert "buses=4" in text


def test_render_failure_diagnostics_classifies_common_ffmpeg_errors():
    from app.render_diagnostics import (
        diagnose_render_failure,
        format_render_failure_diagnostics,
        format_render_failure_message,
    )

    locked = diagnose_render_failure(
        "Could not overwrite 'out.mp4': another app may be holding the file open.",
        SimpleNamespace(out_path="C:/tmp/out.mp4", source_path="C:/tmp/in.mp4", format_id="mp4", quality_id="high", in_ms=0, out_ms=2000),
    )
    assert locked.category == "output_locked"
    assert any("Close any media player" in action for action in locked.actions)
    assert "Output: out.mp4" in locked.context

    missing = diagnose_render_failure("FFmpeg exit 1: Error opening input: No such file or directory")
    assert missing.category == "missing_media"

    filters = format_render_failure_diagnostics("Error initializing complex filters. No such filter: lut3d")
    assert "Effect/filter graph failed" in filters
    assert "LUT" in filters

    message = format_render_failure_message("No space left on device")
    assert "Not enough disk space" in message
    assert "Export to another drive" in message


def test_render_queue_panel_persists_structured_failure_diagnostics(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.render_queue import RenderQueueStore
    from app.render_queue_panel import RenderQueuePanel

    QApplication.instance() or QApplication([])
    queue_path = tmp_path / "render_queue.json"
    panel = RenderQueuePanel(store=RenderQueueStore(queue_path))
    item = SimpleNamespace(
        label="Segment",
        out_path=str(tmp_path / "out.mp4"),
        in_ms=0,
        out_ms=1000,
        status="pending",
        error="",
    )
    ids = panel.queue_items(
        [item],
        lambda *_args, **_kwargs: None,
        source_path=str(tmp_path / "source.mp4"),
        format_id="mp4",
        quality_id="high",
    )

    panel._current_job_id = ids[0]
    panel._on_error("Could not overwrite 'out.mp4': another app may be holding the file open.")

    loaded = RenderQueueStore(queue_path)
    job = loaded.jobs[0]
    assert job.status == "error"
    assert "Output file is locked" in job.diagnostics
    assert "Close any media player" in job.diagnostics
    detail = panel._detail.toPlainText()
    assert "Render Queue Diagnostics" in detail
    assert "Output file is locked" in detail
    assert "Quality: high" in detail
    panel.copy_selected_diagnostics()
    assert "Output file is locked" in QApplication.clipboard().text()
    panel.deleteLater()


def test_render_queue_store_cancels_pending_and_paused_jobs(tmp_path):
    from app.render_queue import RenderQueueJob, RenderQueueStore

    queue_path = tmp_path / "render_queue.json"
    store = RenderQueueStore(queue_path)
    pending_id = store.add(
        RenderQueueJob.create(
            label="Pending",
            out_path=str(tmp_path / "pending.mp4"),
            in_ms=0,
            out_ms=1000,
        )
    )
    paused_id = store.add(
        RenderQueueJob.create(
            label="Paused",
            out_path=str(tmp_path / "paused.mp4"),
            in_ms=1000,
            out_ms=2000,
        )
    )
    store.update_status(paused_id, "paused")

    assert store.cancel_pending() == 2

    loaded = RenderQueueStore(queue_path)
    statuses = {job.id: job.status for job in loaded.jobs}
    assert statuses[pending_id] == "canceled"
    assert statuses[paused_id] == "canceled"
    assert all(job.finished_at > 0 for job in loaded.jobs)


def test_render_queue_retry_range_helpers_use_failure_progress(tmp_path):
    from app.render_queue import (
        RenderQueueJob,
        create_diagnostic_retry_job,
        diagnostic_retry_output_path,
        suggest_retry_range,
    )

    job = RenderQueueJob.create(
        label="Long",
        out_path=str(tmp_path / "long.mp4"),
        in_ms=0,
        out_ms=20000,
        source_path=str(tmp_path / "source.mp4"),
        format_id="mp4",
        quality_id="high",
    )
    job.status = "error"
    job.progress = 60

    assert suggest_retry_range(job) == (9500, 14500)
    assert diagnostic_retry_output_path(job.out_path, 9500, 14500).endswith(
        "long_retry_9-14.mp4"
    )
    retry = create_diagnostic_retry_job(job)
    assert retry.status == "pending"
    assert retry.in_ms == 9500
    assert retry.out_ms == 14500
    assert retry.source_path == job.source_path
    assert retry.format_id == "mp4"
    assert "Diagnostic retry range" in retry.diagnostics


def test_render_queue_panel_queues_short_retry_range_for_failed_runtime_job(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.render_queue import RenderQueueStore
    from app.render_queue_panel import RenderQueuePanel

    QApplication.instance() or QApplication([])
    queue_path = tmp_path / "render_queue.json"
    panel = RenderQueuePanel(store=RenderQueueStore(queue_path))
    item = SimpleNamespace(
        label="Full",
        out_path=str(tmp_path / "full.mp4"),
        in_ms=0,
        out_ms=20000,
        status="pending",
        error="",
    )
    export_fn = lambda *_args, **_kwargs: None
    ids = panel.queue_items(
        [item],
        export_fn,
        source_path=str(tmp_path / "source.mp4"),
        format_id="mp4",
        quality_id="high",
    )
    panel._store.update_progress(ids[0], 60)
    panel.refresh_from_store()
    panel._current_job_id = ids[0]
    panel._on_error("FFmpeg exit 1: Error initializing complex filters")

    retry_id = panel.queue_selected_retry_range()

    loaded = RenderQueueStore(queue_path)
    retry = next(job for job in loaded.jobs if job.id == retry_id)
    assert retry.status == "pending"
    assert retry.in_ms == 9500
    assert retry.out_ms == 14500
    assert retry.out_path.endswith("full_retry_9-14.mp4")
    assert retry_id in panel._runtime_exports
    assert panel._runtime_exports[retry_id] is export_fn
    assert "Diagnostic retry range" in panel._detail.toPlainText()
    panel.deleteLater()


def test_render_queue_panel_filters_search_and_clears_old_history(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.render_queue import RenderQueueJob, RenderQueueStore
    from app.render_queue_panel import RenderQueuePanel

    QApplication.instance() or QApplication([])
    queue_path = tmp_path / "render_queue.json"
    store = RenderQueueStore(queue_path)
    now = int(time.time())
    old = now - 45 * 24 * 60 * 60

    failed = RenderQueueJob.create(
        label="Bad Key",
        out_path=str(tmp_path / "bad_key.mp4"),
        in_ms=0,
        out_ms=1000,
        source_path=str(tmp_path / "source.mp4"),
        format_id="mp4",
    )
    failed.status = "error"
    failed.error = "lut3d missing"
    failed.diagnostics = "Effect/filter graph failed: lut3d missing"
    failed.finished_at = now
    old_done = RenderQueueJob.create(
        label="Old Done",
        out_path=str(tmp_path / "old.mp4"),
        in_ms=0,
        out_ms=1000,
    )
    old_done.status = "done"
    old_done.created_at = old
    old_done.updated_at = old
    old_done.finished_at = old
    pending = RenderQueueJob.create(
        label="Proxy Pending",
        out_path=str(tmp_path / "pending.mp4"),
        in_ms=0,
        out_ms=1000,
    )
    store.replace([failed, old_done, pending])
    panel = RenderQueuePanel(store=store)

    panel._status_filter.setCurrentIndex(panel._status_filter.findData("error"))
    assert panel._table.rowCount() == 1
    assert "Bad Key" in panel._table.item(0, 1).text()
    panel._search_edit.setText("lut3d")
    assert panel._table.rowCount() == 1
    assert "Effect/filter graph failed" in panel._detail.toPlainText()
    panel._search_edit.setText("pending")
    assert panel._table.rowCount() == 0
    panel._status_filter.setCurrentIndex(panel._status_filter.findData(""))
    assert panel._table.rowCount() == 1
    assert "Proxy Pending" in panel._table.item(0, 1).text()

    panel.clear_old_history()

    loaded = RenderQueueStore(queue_path)
    labels = [job.label for job in loaded.jobs]
    assert labels == ["Bad Key", "Proxy Pending"]
    assert "Removed 1 old history job" in panel._summary.text()
    panel.deleteLater()


def test_media_relink_replaces_missing_paths_by_filename(tmp_path):
    from app.media_relink import missing_relinkable_paths, relink_project_doc

    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    missing = old_root / "clip.mp4"
    replacement = new_root / "clip.mp4"
    replacement.write_bytes(b"video")
    doc = {
        "media_pool": [str(missing)],
        "video_tracks": [{
            "clips": [{"source_path": str(missing)}],
        }],
    }

    new_doc, report = relink_project_doc(doc, [new_root])

    assert report["changed"] == 2
    assert missing_relinkable_paths(doc) == [str(missing)]
    assert new_doc["media_pool"] == [str(replacement.resolve())]
    assert new_doc["video_tracks"][0]["clips"][0]["source_path"] == str(
        replacement.resolve()
    )


def test_media_relink_project_file_writes_copy_and_reports_missing(tmp_path):
    from app.media_relink import relink_project_file

    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    missing = old_root / "voice.wav"
    replacement = new_root / "voice.wav"
    replacement.write_bytes(b"audio")
    project = tmp_path / "edit.tgp"
    project.write_text(
        json.dumps({
            "media_pool": [str(missing)],
            "audio_tracks": [{"clips": [{"source_path": str(missing)}]}],
        }),
        encoding="utf-8",
    )

    out, report = relink_project_file(project, [new_root])
    repaired = json.loads(out.read_text(encoding="utf-8"))
    original = json.loads(project.read_text(encoding="utf-8"))

    assert out.name == "edit.relinked.tgp"
    assert report["changed"] == 2
    assert report["missing_before"] == [str(missing)]
    assert report["missing_after"] == []
    assert original["media_pool"] == [str(missing)]
    assert repaired["audio_tracks"][0]["clips"][0]["source_path"] == str(
        replacement.resolve()
    )


def test_media_relink_plan_reports_conflicts_and_uses_user_choice(tmp_path):
    from app.media_relink import build_relink_plan, relink_project_doc

    old_root = tmp_path / "old"
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    old_root.mkdir()
    root_a.mkdir()
    root_b.mkdir()
    missing = old_root / "same.mp4"
    candidate_a = root_a / "same.mp4"
    candidate_b = root_b / "same.mp4"
    candidate_a.write_bytes(b"a")
    candidate_b.write_bytes(b"b")
    doc = {"media_pool": [str(missing)]}

    plan = build_relink_plan(doc, [root_a, root_b])

    assert plan["conflict_count"] == 1
    assert plan["rows"][0]["status"] == "conflict"
    assert set(plan["rows"][0]["candidates"]) == {
        str(candidate_a.resolve()),
        str(candidate_b.resolve()),
    }

    new_doc, report = relink_project_doc(
        doc,
        [root_a, root_b],
        choices={str(missing): str(candidate_b)},
    )

    assert new_doc["media_pool"] == [str(candidate_b.resolve())]
    assert report["changes"][0]["reason"] == "user choice"


def test_media_health_report_flags_relink_conflict_and_proxy_stale(tmp_path):
    from app.media_relink import build_media_health_report

    media_dir = tmp_path / "media"
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    media_dir.mkdir()
    root_a.mkdir()
    root_b.mkdir()

    stale_source = media_dir / "stale_clip.mp4"
    stale_source.write_bytes(b"video")
    stale_proxy = media_dir / "proxies" / "stale_clip_proxy.mp4"
    stale_proxy.parent.mkdir()
    stale_proxy.write_bytes(b"proxy")
    now = time.time()
    os.utime(stale_source, (now, now))
    os.utime(stale_proxy, (now - 60, now - 60))

    missing = tmp_path / "old" / "choice.mp4"
    candidate_a = root_a / "choice.mp4"
    candidate_b = root_b / "choice.mp4"
    candidate_a.write_bytes(b"a")
    candidate_b.write_bytes(b"b")
    doc = {
        "media_pool": [str(stale_source), str(missing)],
        "video_tracks": [{"clips": [{"source_path": str(stale_source)}]}],
    }

    report = build_media_health_report(doc, [root_a, root_b])

    rows_by_name = {row["filename"]: row for row in report["rows"]}
    assert report["ok"] is False
    assert rows_by_name["stale_clip.mp4"]["status"] == "proxy_stale"
    assert rows_by_name["stale_clip.mp4"]["proxy_state"] == "stale"
    assert rows_by_name["choice.mp4"]["status"] == "relink_conflict"
    assert rows_by_name["choice.mp4"]["candidate_count"] == 2
    assert report["proxy_counts"]["stale"] == 1


def test_media_health_dialog_rows_explain_proxy_and_relink_actions(tmp_path):
    from app.media_health_dialog import media_health_rows
    from app.media_relink import build_media_health_report

    media_dir = tmp_path / "media"
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    media_dir.mkdir()
    root_a.mkdir()
    root_b.mkdir()
    source_without_proxy = media_dir / "no_proxy.mp4"
    source_without_proxy.write_bytes(b"video")
    missing = tmp_path / "old" / "choice.mp4"
    (root_a / "choice.mp4").write_bytes(b"a")
    (root_b / "choice.mp4").write_bytes(b"b")

    report = build_media_health_report(
        {"media_pool": [str(source_without_proxy), str(missing)]},
        [root_a, root_b],
    )
    rows = {row["filename"]: row for row in media_health_rows(report)}

    assert rows["no_proxy.mp4"]["status_label"] == "Proxy Missing"
    assert "proxy" in rows["no_proxy.mp4"]["action"].lower()
    assert rows["choice.mp4"]["status_label"] == "Relink Conflict"
    assert rows["choice.mp4"]["candidate_count"] == 2
    assert "Relink" in rows["choice.mp4"]["action"]


def test_editor_media_health_doc_collects_current_session_paths(tmp_path):
    from app.media_health_dialog import (
        build_editor_media_health_doc,
        suggest_media_health_roots,
    )
    from app.media_relink import collect_relinkable_paths

    video = tmp_path / "clip.mp4"
    nested = tmp_path / "nested.mov"
    audio = tmp_path / "voice.wav"
    skel = tmp_path / "hero.skel"
    atlas = tmp_path / "hero.atlas"
    model = tmp_path / "model.model3.json"
    for path in (video, nested, audio, skel, atlas, model):
        path.write_bytes(b"x")

    pool = SimpleNamespace(items=lambda: [str(video)])
    editor = SimpleNamespace(
        _project_settings={"fps": 30.0, "color_management": {"output_space": "Rec.709"}},
        _media_pool=pool,
        _tracks=[
            SimpleNamespace(
                id=1,
                source_path=video,
                offset_ms=0,
                node_item_chain=[(
                    SimpleNamespace(
                        vfx_repair_plan={"clean_plate": {"enabled": True}},
                        vfx_node_graph={
                            "nodes": [
                                {"id": "media_in", "kind": "media_in"},
                                {"id": "out", "kind": "output", "inputs": ["media_in"]},
                            ],
                            "output_node": "out",
                        },
                    ),
                    [],
                )],
                clips=[
                    SimpleNamespace(
                        id=7,
                        source_path=video,
                        source_duration_ms=5000,
                        timeline_in_ms=1000,
                        source_in_ms=0,
                        source_out_ms=3000,
                        linked_audio_id=12,
                        video_filters=SimpleNamespace(to_dict=lambda: {"enabled": True}),
                        masks=[],
                        nested_child_tracks=[[SimpleNamespace(source_path=nested)]],
                        nested_audio_tracks=[[SimpleNamespace(source_path=audio)]],
                    )
                ],
            )
        ],
        _audio_tracks=[SimpleNamespace(
            id=2,
            bus_id="dialogue",
            automation_points=[(0.0, 1.0)],
            clips=[SimpleNamespace(
                id=12,
                source_path=audio,
                duration_ms=2000,
                offset_ms=1000,
                effects={"loudness": {"enabled": True}},
            )],
        )],
        _spine_actor_tracks=[SimpleNamespace(clips=[SimpleNamespace(skel_path=skel, atlas_path=atlas)])],
        _live2d_actor_tracks=[SimpleNamespace(clips=[SimpleNamespace(model_path=model)])],
    )

    doc = build_editor_media_health_doc(editor)
    paths = set(collect_relinkable_paths(doc))

    assert {str(video), str(nested), str(audio), str(skel), str(atlas), str(model)} <= paths
    assert doc["project_settings"]["color_management"]["output_space"] == "Rec.709"
    clip_doc = doc["video_tracks"][0]["clips"][0]
    assert clip_doc["timeline_in_ms"] == 1000
    assert clip_doc["source_out_ms"] == 3000
    assert clip_doc["linked_audio_id"] == 12
    assert clip_doc["video_filters"]["enabled"] is True
    assert doc["vfx_repair_plans"][0]["clean_plate"]["enabled"] is True
    assert doc["vfx_node_graphs"][0]["output_node"] == "out"
    audio_doc = doc["audio_tracks"][0]
    assert audio_doc["bus_id"] == "dialogue"
    assert audio_doc["automation_points"] == [(0.0, 1.0)]
    assert audio_doc["clips"][0]["effects"]["loudness"]["enabled"] is True
    assert tmp_path.resolve() in suggest_media_health_roots(doc)


def test_preset_library_loads_builtin_and_external_presets(tmp_path):
    from app.preset_library import load_editor_presets, presets_by_kind

    extra = tmp_path / "presets.json"
    extra.write_text(
        json.dumps({
            "presets": [{
                "id": "transition-custom-fast",
                "kind": "transition",
                "name": "Custom Fast",
                "payload": {"transition_out_type": "dissolve", "transition_out_ms": 120},
            }]
        }),
        encoding="utf-8",
    )

    all_presets = load_editor_presets([extra])
    transitions = presets_by_kind("transition", [extra])

    assert len(presets_by_kind("effect")) >= 47
    assert len(presets_by_kind("title")) >= 30
    assert len(transitions) >= 40
    assert len(presets_by_kind("audio")) >= 11
    assert len(presets_by_kind("color")) >= 6
    assert len(presets_by_kind("template")) >= 31
    assert len(presets_by_kind("caption_style")) >= 14
    assert len(presets_by_kind("sticker")) >= 17
    assert len(presets_by_kind("motion")) >= 11
    assert len(presets_by_kind("actor")) >= 2
    assert any(p.id == "effect-punchy-gameplay" for p in all_presets)
    assert any(p.id == "transition-custom-fast" for p in transitions)


def test_preset_library_search_and_summary_cover_expanded_pack():
    from app.preset_library import (
        one_click_preset_plan,
        preset_ecosystem_report,
        preset_library_summary,
        search_presets,
    )

    summary = preset_library_summary()
    ecosystem = preset_ecosystem_report()
    keying = search_presets("screen", kind="effect", tags=["keying"])
    live2d = search_presets(kind="title", tags=["live2d"])
    dialogue = search_presets(kind="audio", tags=["dialogue"])
    shortform_templates = search_presets(kind="template", tags=["short-form"])
    tutorial_templates = search_presets("step", kind="template", tags=["tutorial"])
    product_templates = search_presets(kind="template", tags=["product"])
    social_captions = search_presets(kind="caption_style", tags=["vertical"])
    news_templates = search_presets(kind="template", tags=["news"])
    hotkey_templates = search_presets("hotkey", kind="template", tags=["tutorial"])
    ranking_templates = search_presets(kind="template", tags=["ranking"])
    anime_effects = search_presets(kind="effect", tags=["anime"])
    broll_templates = search_presets("b roll", kind="template")
    patch_templates = search_presets("patch note", kind="template")
    review_templates = search_presets("product review", kind="template")
    procon_stickers = search_presets("pro con", kind="sticker")
    korean_shorts = search_presets("쇼츠", kind="template")
    korean_dialogue = search_presets("대사 선명", kind="audio")
    nikke_actor = search_presets("니케", kind="template")

    assert summary["by_kind"]["effect"] >= 47
    assert summary["by_kind"]["transition"] >= 40
    assert summary["by_kind"]["audio"] >= 11
    assert summary["by_kind"]["caption_style"] >= 14
    assert summary["by_kind"]["template"] >= 31
    assert summary["by_kind"]["actor"] >= 2
    assert ecosystem["ok"] is True
    assert ecosystem["score"] == 100
    assert ecosystem["template_reference_issues"] == []
    assert ecosystem["kind_targets"]["template"]["ok"] is True
    assert ecosystem["topic_coverage"]["news"]["ok"] is True
    assert ecosystem["topic_coverage"]["patch-note"]["ok"] is True
    assert ecosystem["topic_coverage"]["spine"]["ok"] is True
    assert "template-news-brief" in ecosystem["one_click_plans"]["news"]
    assert "template-patch-note-update" in ecosystem["one_click_plans"]["patch-note"]
    assert "template-spine-actor-action" in ecosystem["one_click_plans"]["spine"]
    assert any(p.id == "effect-blue-screen-clean" for p in keying)
    assert any(p.id == "title-live2d-nameplate" for p in live2d)
    assert any(p.id == "audio-dialogue-cleanup-strong" for p in dialogue)
    assert any(p.id == "template-shortform-hook-caption" for p in shortform_templates)
    assert any(p.id == "template-screenstudio-cursor-demo" for p in search_presets("screenstudio cursor", kind="template"))
    assert any(p.id == "template-capcut-hook-stack" for p in search_presets("capcut hook", kind="template"))
    assert any(p.id == "transition-cursor-pop-cut" for p in search_presets("cursor pop", kind="transition"))
    assert any(p.id == "template-screenstudio-hotkey-demo" for p in search_presets("hotkey demo", kind="template"))
    assert any(p.id == "sticker-click-ring" for p in search_presets("click ring", kind="sticker"))
    assert any(p.id == "template-product-launch-clean" for p in search_presets("product launch", kind="template"))
    assert any(p.id == "template-screenstudio-record-edit-export" for p in search_presets("record edit export", kind="template"))
    assert any(p.id == "template-screenstudio-product-walkthrough" for p in search_presets("product walkthrough", kind="template"))
    assert any(p.id == "template-screenstudio-wallpaper-demo" for p in search_presets("wallpaper demo", kind="template"))
    assert any(p.id == "template-screenstudio-short-export" for p in search_presets("short export", kind="template"))
    assert any(p.id == "template-gaming-highlight-screen" for p in search_presets("gaming highlight", kind="template"))
    assert any(p.id == "template-tutorial-step-by-step" for p in tutorial_templates)
    assert any(p.id == "template-product-demo-clean" for p in product_templates)
    assert any(p.id == "caption-vertical-safe" for p in social_captions)
    assert any(p.id == "template-news-brief" for p in news_templates)
    assert any(p.id == "template-hotkey-tutorial" for p in hotkey_templates)
    assert any(p.id == "template-ranking-short" for p in ranking_templates)
    assert any(p.id == "effect-anime-cleanline" for p in anime_effects)
    assert any(p.id == "template-broll-story-insert" for p in broll_templates)
    assert any(p.id == "template-patch-note-update" for p in patch_templates)
    assert any(p.id == "template-product-review-verdict" for p in review_templates)
    assert any(p.id == "sticker-pro-con-pill" for p in procon_stickers)
    assert any(p.id == "template-shortform-hook-caption" for p in korean_shorts)
    assert any(p.id == "audio-dialogue-cleanup-strong" for p in korean_dialogue)
    assert any(p.id in {"template-spine-actor-action", "template-anime-reaction-clean"} for p in nikke_actor)
    tutorial_plan = [p.id for p in one_click_preset_plan({"tutorial": True, "screen_recording": True})]
    product_plan = [p.id for p in one_click_preset_plan({"product": True, "demo": True})]
    short_plan = [p.id for p in one_click_preset_plan({"shortform": True, "duration_s": 45})]
    assert "template-screenstudio-record-edit-export" in tutorial_plan
    assert "template-screenstudio-click-to-cut" in tutorial_plan
    assert "template-screenstudio-product-walkthrough" in product_plan
    assert "template-screenstudio-short-export" in short_plan


def test_preset_pack_inspection_reports_conflicts_and_missing_refs(tmp_path):
    from app.preset_library import inspect_preset_pack

    pack = tmp_path / "mixed_pack.json"
    pack.write_text(json.dumps({
        "schema": 1,
        "presets": [
            {
                "id": "effect-punchy-gameplay",
                "kind": "effect",
                "name": "Conflicts With Builtin",
                "payload": {"video_filters": {"sharpen": 0.2}},
            },
            {
                "id": "custom-effect",
                "kind": "effect",
                "name": "Custom",
                "payload": {"video_filters": {"vignette": 0.2}},
            },
            {
                "id": "custom-effect",
                "kind": "effect",
                "name": "Duplicate",
                "payload": {"video_filters": {"vignette": 0.4}},
            },
            {
                "id": "template-broken",
                "kind": "template",
                "name": "Broken Template",
                "payload": {"sequence": [
                    {"kind": "title", "preset_id": "missing-title", "at_ms": 0},
                ]},
            },
            "invalid row",
        ],
    }), encoding="utf-8")

    report = inspect_preset_pack(pack)

    assert report["invalid_count"] == 1
    assert "custom-effect" in report["duplicate_ids"]
    assert "effect-punchy-gameplay" in report["builtin_conflicts"]
    assert report["missing_refs"][0]["preset_id"] == "missing-title"
    assert set(report["issues"]) >= {
        "invalid_rows",
        "duplicate_ids",
        "builtin_id_conflicts",
        "missing_template_refs",
    }


def test_preset_pack_repair_writes_backup_and_removes_broken_rows(tmp_path, monkeypatch):
    monkeypatch.setattr("app.paths.default_save_dir", lambda: tmp_path)
    from app.preset_library import inspect_preset_pack, repair_user_preset_pack, user_preset_dir

    root = user_preset_dir()
    pack = root / "needs_repair.json"
    pack.write_text(json.dumps({
        "schema": 1,
        "presets": [
            {
                "id": "custom-effect",
                "kind": "effect",
                "name": "Custom",
                "payload": {"video_filters": {"vignette": 0.2}},
            },
            {
                "id": "custom-effect",
                "kind": "effect",
                "name": "Duplicate",
                "payload": {"video_filters": {"vignette": 0.4}},
            },
            {
                "id": "template-broken",
                "kind": "template",
                "name": "Broken Template",
                "payload": {"sequence": [
                    {"kind": "effect", "preset_id": "custom-effect", "at_ms": 0},
                    {"kind": "title", "preset_id": "missing-title", "at_ms": 200},
                ]},
            },
            None,
        ],
    }), encoding="utf-8")

    result = repair_user_preset_pack(pack)
    report = inspect_preset_pack(pack)
    repaired = json.loads(pack.read_text(encoding="utf-8"))
    template = next(row for row in repaired["presets"] if row["id"] == "template-broken")

    assert result["invalid_removed"] == 1
    assert result["duplicates_removed"] == 1
    assert result["missing_refs_removed"] == 1
    assert result["count"] == 2
    assert os.path.exists(result["backup"])
    assert report["ok"]
    assert template["payload"]["sequence"] == [
        {"kind": "effect", "preset_id": "custom-effect", "at_ms": 0}
    ]


def test_preset_pack_marketplace_report_summarizes_enabled_and_issues(tmp_path, monkeypatch):
    monkeypatch.setattr("app.paths.default_save_dir", lambda: tmp_path)
    from app.preset_library import preset_pack_marketplace_report, user_preset_dir

    root = user_preset_dir()
    (root / "ready.json").write_text(json.dumps({
        "schema": 1,
        "presets": [
            {
                "id": "custom-title",
                "kind": "title",
                "name": "Custom Title",
                "tags": ["creator", "shortform"],
                "payload": {"text": "HELLO"},
            },
        ],
    }), encoding="utf-8")
    (root / "broken.json").write_text(json.dumps({
        "schema": 1,
        "presets": [
            {
                "id": "template-broken",
                "kind": "template",
                "name": "Broken",
                "payload": {"sequence": [{"kind": "effect", "preset_id": "missing-effect"}]},
            },
        ],
    }), encoding="utf-8")

    report = preset_pack_marketplace_report()

    assert report["total_packs"] == 2
    assert report["enabled_packs"] == 2
    assert report["issue_packs"] == 1
    assert report["kind_counts"]["title"] == 1
    assert report["top_tags"]["creator"] == 1
    assert any(card["missing_refs"] for card in report["packs"])
    assert any("Repair" in action for action in report["recommendations"])


def test_effect_preset_payload_applies_to_clip_filters():
    from app.preset_library import apply_effect_preset_to_clip, presets_by_kind

    preset = next(p for p in presets_by_kind("effect") if p.id == "effect-punchy-gameplay")
    clip = SimpleNamespace(video_filters=None, chroma_key=None)

    assert apply_effect_preset_to_clip(clip, preset)
    assert clip.video_filters is not None
    assert clip.video_filters.enabled is True
    assert clip.video_filters.sharpen == 0.35
    assert clip.video_filters.vignette == 0.18
    assert clip.video_filters.preset_meta["id"] == "effect-punchy-gameplay"
    assert clip.video_filters.preset_meta["name"] == "Punchy Gameplay"


def test_timeline_effect_strip_entries_use_preset_metadata():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.preset_library import apply_effect_preset_to_clip, presets_by_kind
    from app.video_editor_window import TrackRow

    QApplication.instance() or QApplication([])
    preset = next(p for p in presets_by_kind("effect") if p.id == "effect-readable-screen-text")
    clip = SimpleNamespace(
        id=7,
        timeline_in_ms=0,
        timeline_out_ms=3000,
        video_filters=None,
        chroma_key=None,
        bg_removal=None,
        transition_out_type="fade_white",
        transition_out_ms=120,
        color_grade=None,
        node_graph=None,
        is_nested_sequence=False,
        compound_group_id=None,
    )
    assert apply_effect_preset_to_clip(clip, preset)
    track = SimpleNamespace(
        id=1,
        duration_ms=3000,
        offset_ms=0,
        clips=[clip],
        source_path=None,
        thumbnails=[],
        speed_segments=[],
        fades=[],
        cuts=[],
        typography_actors=[],
        zoom_actors=[],
        display_name="Track 1",
    )
    row = TrackRow(track)
    try:
        entries = row._clip_effect_strip_entries(clip)
        assert entries[0][0] == "FX"
        assert "Readable Screen Text" in entries[0][1]
        assert any(entry[0] == "TR" and entry[1] == "Fade White" for entry in entries)
    finally:
        row.deleteLater()


def test_transition_preset_metadata_roundtrips_and_labels_strip():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.project_io import _video_clip_from_dict, _video_clip_to_dict
    from app.timeline_model import VideoClip
    from app.video_editor_window import TrackRow

    QApplication.instance() or QApplication([])
    clip = VideoClip(id=14, source_duration_ms=3000, timeline_in_ms=0)
    clip.transition_out_type = "zoom_in"
    clip.transition_out_ms = 450
    clip.transition_preset_meta = {
        "id": "transition-soft-zoom-bridge",
        "name": "Soft Zoom Bridge",
        "kind": "transition",
    }

    data = _video_clip_to_dict(clip)
    restored = _video_clip_from_dict(data, None)

    assert restored.transition_preset_meta["id"] == "transition-soft-zoom-bridge"
    assert restored.transition_preset_meta["name"] == "Soft Zoom Bridge"

    track = SimpleNamespace(
        id=1,
        duration_ms=3000,
        offset_ms=0,
        clips=[restored],
        source_path=None,
        thumbnails=[],
        speed_segments=[],
        fades=[],
        cuts=[],
        typography_actors=[],
        zoom_actors=[],
        display_name="Track 1",
    )
    row = TrackRow(track)
    try:
        entries = row._clip_effect_strip_entries(restored)
        assert any(entry[0] == "TR" and entry[1] == "Soft Zoom Bridge" for entry in entries)
        assert row._clip_effect_strip_display_text("TR", "Soft Zoom Bridge", 48) == "TR"
        assert row._clip_effect_strip_display_text("TR", "Soft Zoom Bridge", 120) == "TR Soft Zoom Bridge"
        assert "Soft Zoom Bridge" in row._clip_effect_tooltip(restored)
    finally:
        row.deleteLater()


def test_trackrow_drag_validator_reason_surfaces_in_feedback_chip():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.i18n import initialize, set_language
    from app.video_editor_window import TrackRow

    QApplication.instance() or QApplication([])
    initialize()
    set_language("en")
    track = SimpleNamespace(
        id=1,
        duration_ms=3000,
        offset_ms=0,
        clips=[],
        source_path=None,
        thumbnails=[],
        speed_segments=[],
        fades=[],
        cuts=[],
        typography_actors=[],
        zoom_actors=[],
        display_name="Track 1",
    )
    row = TrackRow(track)
    try:
        row.set_clip_drag_validator(
            lambda _track_id, _clip_ids, _delta: {
                "ok": False,
                "reason": "audio_collision",
                "message": "Drag blocked by linked audio",
            }
        )

        assert row._can_apply_clip_drag_delta({4}, 250) is False
        assert row._drag_block_reason == "audio_collision"
        assert row._blocked_drag_feedback_text() == "Move blocked: linked audio would overlap"
    finally:
        row.deleteLater()


def test_creator_effect_transition_expansion_pack_has_real_payloads():
    from app.preset_library import (
        apply_effect_preset_to_clip,
        presets_by_kind,
        transition_drag_payload,
    )

    effects = {p.id: p for p in presets_by_kind("effect")}
    transitions = {p.id: p for p in presets_by_kind("transition")}

    for preset_id in {
        "effect-readable-screen-text",
        "effect-cursor-focus-vignette",
        "effect-retro-glitch-lite",
        "effect-anime-overlay-crisp",
    }:
        assert preset_id in effects

    for preset_id in {
        "transition-cursor-click-flash",
        "transition-soft-zoom-bridge",
        "transition-shortform-white-hit",
        "transition-demo-step-dissolve",
    }:
        assert preset_id in transitions

    clip = SimpleNamespace(video_filters=None, chroma_key=None)
    assert apply_effect_preset_to_clip(clip, effects["effect-readable-screen-text"])
    assert clip.video_filters is not None
    assert clip.video_filters.enabled is True
    assert clip.video_filters.sharpen == 0.28
    assert clip.video_filters.denoise == 0.08

    payload = transition_drag_payload(transitions["transition-cursor-click-flash"])
    assert payload["type"] == "fade_white"
    assert payload["ms"] == 110
    assert payload["preset_id"] == "transition-cursor-click-flash"


def test_video_editor_language_menu_translation_keys_exist():
    import app.i18n as i18n

    i18n.initialize()
    required = {
        "settings.language",
        "veditor.language.changed",
        "veditor.export.resolution.tooltip",
        "veditor.export.fps.tooltip",
        "veditor.effect_preset.drop_label",
        "veditor.effect_preset.drop_blocked",
        "veditor.clip_badge.menu.focus",
        "veditor.clip_badge.menu.clear_fx",
        "veditor.clip_badge.status.no_fx",
    }

    try:
        for code in i18n.SUPPORTED_LANGUAGES:
            assert required <= set(i18n._translations[code])
            i18n.set_language(code)
            assert "{" not in i18n.tr(
                "veditor.language.changed",
                language=i18n._translations[code]["settings.language"],
            )
    finally:
        i18n.set_language("en")


def test_effect_preset_card_click_activates_without_drag():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from app.preset_library import presets_by_kind
    from app import i18n
    from app.video_editor_window import EffectPresetCard

    QApplication.instance() or QApplication([])
    i18n.initialize()
    i18n.set_language("en")
    preset = next(p for p in presets_by_kind("effect") if p.id == "effect-punchy-gameplay")
    card = EffectPresetCard(preset)
    activated = []
    card.activated.connect(lambda p: activated.append(p.id))
    try:
        card.show()
        QTest.mouseClick(card, Qt.MouseButton.LeftButton)
        assert activated == ["effect-punchy-gameplay"]
        assert "Click: apply" in card.toolTip()
        assert "drag onto clip" in card._drag_hint.casefold()
    finally:
        card.deleteLater()


def test_left_effect_preset_click_reports_target_hint_when_blocked():
    from app.preset_library import presets_by_kind
    from app import i18n
    from app.video_editor_window import VideoEditorWindow

    i18n.initialize()
    i18n.set_language("en")
    preset = next(p for p in presets_by_kind("effect") if p.id == "effect-punchy-gameplay")
    messages = []
    editor = SimpleNamespace()
    editor._apply_effect_preset_from_left_panel = MethodType(
        VideoEditorWindow._apply_effect_preset_from_left_panel,
        editor,
    )
    editor._apply_editor_preset_object = lambda _preset, depth=0: False
    editor._preset_apply_failure_reason = lambda _preset: "비디오 클립 선택 또는 활성 타임라인 위치가 필요합니다"
    editor._flash_status = messages.append

    editor._apply_effect_preset_from_left_panel(preset)

    assert messages
    assert "Select a clip or drag the card onto one" in messages[-1]


def test_effect_preset_drag_target_tracks_clip_and_label():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QMimeData
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import EFFECT_PRESET_MIME_TYPE, TrackRow

    QApplication.instance() or QApplication([])
    clip = SimpleNamespace(
        id=7,
        timeline_in_ms=0,
        timeline_out_ms=3000,
        source_in_ms=0,
        source_duration_ms=3000,
        effective_source_out_ms=3000,
        video_filters=None,
        chroma_key=None,
        bg_removal=None,
        transition_out_type="",
        is_nested_sequence=False,
        compound_group_id=None,
    )
    track = SimpleNamespace(
        id=1,
        duration_ms=3000,
        offset_ms=0,
        clips=[clip],
        typography_actors=[],
        zoom_actors=[],
        fades=[],
        speed_segments=[],
    )
    row = TrackRow(track)
    md = QMimeData()
    md.setData(
        EFFECT_PRESET_MIME_TYPE,
        json.dumps(
            {
                "__preset_meta": {"id": "effect-punchy-gameplay", "name": "Punchy Gameplay"},
                "video_filters": {"enabled": True},
            }
        ).encode("utf-8"),
    )

    try:
        row._update_effect_drop_target(row._clip_rect(clip).center(), md)

        assert row._effect_drop_target_clip_id == 7
        assert row._effect_drop_target_label == "Punchy Gameplay"
        assert row._effect_drop_blocked_label == ""

        row._update_effect_drop_target(row._clip_rect(clip).translated(420, 0).center(), md)

        assert row._effect_drop_target_clip_id is None
        assert row._effect_drop_target_label == "Punchy Gameplay"
        assert row._effect_drop_blocked_label == "Punchy Gameplay"
        assert row._effect_drop_blocked_x is not None

        row._clear_effect_drop_target()

        assert row._effect_drop_target_clip_id is None
        assert row._effect_drop_target_label == ""
        assert row._effect_drop_blocked_label == ""
        assert row._effect_drop_blocked_x is None
    finally:
        row.deleteLater()


def test_chroma_key_effect_preset_applies_to_clip():
    from app.preset_library import apply_effect_preset_to_clip, presets_by_kind

    preset = next(p for p in presets_by_kind("effect") if p.id == "effect-green-screen-clean")
    clip = SimpleNamespace(video_filters=None, chroma_key=None)

    assert apply_effect_preset_to_clip(clip, preset)
    assert clip.chroma_key is not None
    assert clip.chroma_key.enabled is True
    assert clip.chroma_key.key_hue == 60


def test_professional_preset_helpers_return_one_click_plan():
    from app.color_grading import ColorGrade
    from app.preset_library import (
        apply_audio_preset_to_clip,
        apply_color_preset_to_grade,
        one_click_preset_plan,
        preset_by_id,
        presets_by_kind,
        template_sequence,
    )

    audio_preset = next(p for p in presets_by_kind("audio") if p.id == "audio-loudness-shortform")
    clip = SimpleNamespace(effects={})
    assert apply_audio_preset_to_clip(clip, audio_preset)
    assert clip.effects["loudness"]["target_id"] == "shortform"

    color_preset = next(p for p in presets_by_kind("color") if p.id == "color-window-face-focus")
    workflow = apply_color_preset_to_grade(ColorGrade(), color_preset)
    assert workflow["window"]["track_object"] is True

    advanced_grade = ColorGrade()
    advanced_preset = next(p for p in presets_by_kind("color") if p.id == "color-hdr-zone-product-pop")
    assert apply_color_preset_to_grade(advanced_grade, advanced_preset) == {}
    assert advanced_grade.advanced_color_toolset["hdr_zones"]["enabled"] is True

    plan = one_click_preset_plan({
        "shortform": True,
        "dialogue": True,
        "gameplay": True,
        "tutorial": True,
        "product": True,
        "reaction": True,
        "news": True,
        "ranking": True,
        "anime": True,
        "mobile": True,
        "food": True,
        "podcast": True,
        "review": True,
        "broll": True,
        "patch_note": True,
        "spine": True,
    })
    ids = [preset.id for preset in plan]
    assert "template-shortform-hook-caption" in ids
    assert "template-social-listicle" in ids
    assert "audio-dialogue-cleanup-strong" in ids
    assert "effect-esports-crisp" in ids
    assert "template-tutorial-step-by-step" in ids
    assert "template-product-demo-clean" in ids
    assert "template-reaction-punch-pack" in ids
    assert "template-news-brief" in ids
    assert "template-ranking-short" in ids
    assert "template-anime-reaction-clean" in ids
    assert "template-hotkey-tutorial" in ids
    assert "template-product-food-gloss" in ids
    assert "template-podcast-chapter" in ids
    assert "template-product-review-verdict" in ids
    assert "template-broll-story-insert" in ids
    assert "template-patch-note-update" in ids
    assert "template-spine-actor-action" in ids
    assert "actor-spine-placeholder" in ids

    template = preset_by_id("template-gameplay-highlight")
    assert template is not None
    sequence = template_sequence(template)
    assert [item["preset_id"] for item in sequence[:2]] == [
        "effect-esports-crisp",
        "title-score-callout",
    ]
    assert all(item["kind"] and item["preset_id"] for item in sequence)

    tutorial_template = preset_by_id("template-tutorial-step-by-step")
    assert tutorial_template is not None
    tutorial_ids = [item["preset_id"] for item in template_sequence(tutorial_template)]
    assert tutorial_ids[:3] == [
        "effect-tutorial-cursor-clarity",
        "title-tutorial-step",
        "caption-tutorial-compact",
    ]


def test_workflow_drop_target_overrides_selected_clip():
    from app.video_editor_window import VideoEditorWindow

    selected_clip = SimpleNamespace(id=1, timeline_in_ms=0, timeline_out_ms=1000)
    dropped_clip = SimpleNamespace(id=2, timeline_in_ms=1000, timeline_out_ms=2000)
    selected_track = SimpleNamespace(id=10, clips=[selected_clip])
    dropped_track = SimpleNamespace(id=20, clips=[dropped_clip])
    tracks = {10: selected_track, 20: dropped_track}
    editor = SimpleNamespace(
        _selected_clips=[(10, 1)],
        _workflow_forced_track_id=20,
        _workflow_forced_ms=1250,
        _player=SimpleNamespace(position=lambda: 0),
    )
    editor._find_track = lambda track_id: tracks.get(int(track_id))
    editor._active_track = lambda: selected_track
    editor._selected_video_clip = lambda: (selected_track, selected_clip)

    track, clip = VideoEditorWindow._workflow_target_video_clip(editor)

    assert track is dropped_track
    assert clip is dropped_clip

    editor._workflow_forced_ms = 3000
    track, clip = VideoEditorWindow._workflow_target_video_clip(editor)

    assert track is dropped_track
    assert clip is None


def test_workflow_template_entry_time_is_relative_to_target_start():
    from app.preset_library import EditorPreset
    from app.video_editor_window import VideoEditorWindow

    calls = []
    editor = SimpleNamespace()
    editor._apply_editor_preset_object = MethodType(
        VideoEditorWindow._apply_editor_preset_object,
        editor,
    )
    editor._workflow_target_video_clip = lambda: (None, None)
    editor._workflow_start_ms = lambda track=None, clip=None, explicit_ms=None: 5000
    editor._add_title_workflow_actor = (
        lambda payload, at_ms=None: calls.append(int(at_ms)) or True
    )

    template = EditorPreset(
        id="template-test-relative-time",
        kind="template",
        name="Relative Time",
        payload={
            "sequence": [
                {"kind": "title", "preset_id": "title-beat-stamp", "at_ms": 250},
            ],
        },
    )

    assert editor._apply_editor_preset_object(template, depth=0)
    assert calls == [5250]

    calls.clear()
    assert editor._apply_editor_preset_object(template, depth=0, at_ms=12000)
    assert calls == [12250]


def test_workflow_template_skips_unmatched_condition_and_keeps_target_mode():
    from app.preset_library import EditorPreset
    from app.video_editor_window import VideoEditorWindow

    calls = []
    editor = SimpleNamespace(_audio_tracks=[], _tracks=[])
    editor._apply_editor_preset_object = MethodType(
        VideoEditorWindow._apply_editor_preset_object,
        editor,
    )
    editor._workflow_target_video_clip = lambda: (None, None)
    editor._workflow_start_ms = lambda track=None, clip=None, explicit_ms=None: 4000
    editor._add_title_workflow_actor = (
        lambda payload, at_ms=None: calls.append((int(at_ms), getattr(editor, "_workflow_target_mode", "auto"))) or True
    )

    template = EditorPreset(
        id="template-test-condition-target",
        kind="template",
        name="Condition Target",
        payload={
            "sequence": [
                {"kind": "title", "preset_id": "title-beat-stamp", "at_ms": 100, "condition": "if_audio"},
                {"kind": "title", "preset_id": "title-beat-stamp", "at_ms": 500, "target": "selected_clip"},
            ],
        },
    )

    assert editor._apply_editor_preset_object(template, depth=0)
    assert calls == [(4500, "selected_clip")]
    assert not hasattr(editor, "_workflow_target_mode")


def test_workflow_target_mode_selected_clip_overrides_forced_drop_target():
    from app.video_editor_window import VideoEditorWindow

    selected_clip = SimpleNamespace(id=1, timeline_in_ms=0, timeline_out_ms=1000)
    forced_clip = SimpleNamespace(id=2, timeline_in_ms=1000, timeline_out_ms=2000)
    selected_track = SimpleNamespace(id=10, clips=[selected_clip])
    forced_track = SimpleNamespace(id=20, clips=[forced_clip])
    tracks = {10: selected_track, 20: forced_track}
    editor = SimpleNamespace(
        _workflow_target_mode="selected_clip",
        _workflow_forced_track_id=20,
        _workflow_forced_ms=1250,
        _player=SimpleNamespace(position=lambda: 0),
    )
    editor._find_track = lambda track_id: tracks.get(int(track_id))
    editor._selected_video_clip = lambda: (selected_track, selected_clip)
    editor._active_track = lambda: forced_track

    track, clip = VideoEditorWindow._workflow_target_video_clip(editor)

    assert track is selected_track
    assert clip is selected_clip


def test_preset_failure_reason_reports_missing_targets():
    from app.preset_library import presets_by_kind
    from app.video_editor_window import VideoEditorWindow

    editor = SimpleNamespace(_selected_clips=[], _tracks=[], _audio_tracks=[])
    editor._preset_apply_failure_reason = MethodType(
        VideoEditorWindow._preset_apply_failure_reason,
        editor,
    )
    editor._workflow_target_video_clip = MethodType(
        VideoEditorWindow._workflow_target_video_clip,
        editor,
    )
    editor._selected_video_clip = lambda: (None, None)
    editor._active_track = lambda: None
    editor._find_track = lambda _track_id: None
    editor._audio_workspace_candidate = lambda: None
    editor._active_color_grade = lambda: None
    editor._player = SimpleNamespace(position=lambda: 0)

    effect = next(p for p in presets_by_kind("effect") if p.id == "effect-punchy-gameplay")
    audio = next(p for p in presets_by_kind("audio") if p.id == "audio-loudness-shortform")

    assert "비디오 클립" in editor._preset_apply_failure_reason(effect)
    assert "오디오" in editor._preset_apply_failure_reason(audio)


def test_preset_application_plan_reports_actor_steps():
    from app.preset_library import preset_by_id
    from app.video_editor_window import VideoEditorWindow

    editor = SimpleNamespace(
        _tracks=[],
        _audio_tracks=[],
        _spine_actor_tracks=[],
        _live2d_actor_tracks=[],
        _player=SimpleNamespace(position=lambda: 700),
    )
    editor._preset_application_plan_rows = MethodType(
        VideoEditorWindow._preset_application_plan_rows,
        editor,
    )
    editor._preset_apply_failure_reason = MethodType(
        VideoEditorWindow._preset_apply_failure_reason,
        editor,
    )
    editor._template_entry_condition_ok = MethodType(
        VideoEditorWindow._template_entry_condition_ok,
        editor,
    )
    editor._project_summary_for_presets = lambda: {"spine": True, "video_count": 0, "has_audio": False}
    editor._workflow_target_video_clip = lambda: (None, None)
    editor._workflow_start_ms = lambda track=None, clip=None, explicit_ms=None: int(explicit_ms if explicit_ms is not None else 700)
    editor._selected_video_clip = lambda: (None, None)
    editor._active_track = lambda: None
    editor._find_track = lambda _track_id: None
    editor._audio_workspace_candidate = lambda: None

    preset = preset_by_id("template-spine-actor-action")
    rows = editor._preset_application_plan_rows(preset)

    assert rows[0]["status"] == "template"
    assert any(row["kind"] == "actor" and row["status"] == "will_apply" for row in rows)
    assert any(row["status"] == "skipped" and "Condition not met" in row["reason"] for row in rows)


def test_preset_application_corpus_summarizes_project_and_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("app.paths.default_save_dir", lambda: tmp_path)
    from app.preset_library import one_click_preset_plan
    from tools.qa_preset_application_corpus import (
        build_report,
        discover_project_files,
        preset_plan_export_parity,
        project_summary_from_file,
    )

    project = tmp_path / "vertical_gameplay_voice.tgp"
    project.write_text(json.dumps({
        "media": [
            str(tmp_path / "capture_gameplay.mp4"),
            str(tmp_path / "voice_dialogue.wav"),
        ],
        "duration_ms": 45000,
    }), encoding="utf-8")

    summary = project_summary_from_file(project)
    report = build_report([project])

    assert summary["shortform"] is True
    assert summary["gameplay"] is True
    assert summary["dialogue"] is True
    assert report["projects"][0]["plan_ids"]
    assert report["projects"][0]["template_first"] is True
    assert report["projects"][0]["export_parity"]["ok"] is True
    assert "video_filter" in report["projects"][0]["export_parity"]["bake_targets"]

    discovered = discover_project_files(tmp_path)
    assert project in discovered

    parity = preset_plan_export_parity(one_click_preset_plan({"spine": True, "live2d": True}))
    assert parity["ok"] is True
    assert "actor_overlay" in parity["bake_targets"]


def test_fixed_preset_application_corpus_samples_are_discoverable():
    from tools.qa_preset_application_corpus import build_report, discover_project_files

    root = Path("qa_corpus") / "preset_application_samples"
    discovered = discover_project_files(root, limit=10)
    report = build_report(discovered)

    assert len(discovered) >= 4
    assert report["ok"] is True
    assert any("actor_spine_live2d" in str(path) for path in discovered)
    assert any("actor_overlay" in row["export_parity"]["bake_targets"] for row in report["projects"])


def test_command_palette_preset_query_score_ranks_exact_terms():
    from app.video_editor_window import _preset_query_score

    high = _preset_query_score("template shortform hook caption vertical social", "shortform caption")
    low = _preset_query_score("audio dialogue cleanup voice podcast", "shortform caption")

    assert high > 0
    assert low == 0


def test_actor_model_candidate_uses_media_pool_spine_asset(tmp_path):
    from app.video_editor_window import VideoEditorWindow

    spine_json = tmp_path / "hero.json"
    spine_json.write_text(
        json.dumps({"bones": [{"name": "root"}], "slots": [], "skins": {}, "animations": {}}),
        encoding="utf-8",
    )
    editor = SimpleNamespace(_media_pool=SimpleNamespace(items=lambda: [str(spine_json)]))
    editor._first_media_pool_path = MethodType(VideoEditorWindow._first_media_pool_path, editor)

    assert VideoEditorWindow._actor_model_candidate(editor, "spine") == str(spine_json)


def test_actor_asset_audit_follows_spine_and_live2d_dependencies(tmp_path):
    from tools.qa_project_audit import _actor_asset_audit

    spine_dir = tmp_path / "spine"
    spine_dir.mkdir()
    skel = spine_dir / "hero.skel"
    atlas = spine_dir / "hero.atlas"
    texture = spine_dir / "hero.png"
    skel.write_bytes(b"skel")
    texture.write_bytes(b"png")
    atlas.write_text(
        "hero.png\nsize: 64,64\nformat: RGBA8888\nfilter: Linear,Linear\n",
        encoding="utf-8",
    )

    live2d_dir = tmp_path / "live2d"
    live2d_dir.mkdir()
    model = live2d_dir / "model3.json"
    moc = live2d_dir / "model.moc3"
    tex_dir = live2d_dir / "textures"
    tex_dir.mkdir()
    tex = tex_dir / "tex_00.png"
    moc.write_bytes(b"moc")
    tex.write_bytes(b"png")
    model.write_text(
        json.dumps({
            "FileReferences": {
                "Moc": "model.moc3",
                "Textures": ["textures/tex_00.png"],
                "Motions": {"Idle": [{"File": "motions/missing.motion3.json"}]},
            }
        }),
        encoding="utf-8",
    )
    doc = {
        "spine_actor_tracks": [{
            "id": 1,
            "clips": [{
                "skel_path": str(skel),
                "atlas_path": str(atlas),
                "anim_name": "idle",
                "duration_ms": 1000,
            }],
        }],
        "live2d_actor_tracks": [{
            "id": 2,
            "clips": [{
                "model_path": str(model),
                "duration_ms": 1000,
            }],
        }],
    }

    rows = _actor_asset_audit(doc)

    spine_row = next(row for row in rows if row["kind"] == "spine")
    live2d_row = next(row for row in rows if row["kind"] == "live2d")
    assert spine_row["ok"] is True
    assert any(dep["path"] == str(texture.resolve()) for dep in spine_row["dependencies"])
    assert live2d_row["ok"] is False
    assert any("missing.motion3.json" in dep["path"] for dep in live2d_row["dependencies"])


def test_export_risk_summary_flags_cpu_actor_and_hires_paths():
    from tools.qa_project_audit import _export_risk_summary

    doc = {
        "video_tracks": [{
            "clips": [{
                "video_filters": {"enabled": True},
                "chroma_key": {"enabled": True},
                "masks": [{"track_object": True}],
                "nested_sequence_id": "nested-1",
            }],
        }],
        "spine_actor_tracks": [{"clips": [{"duration_ms": 1000}]}],
    }
    media_probe = [{"width": 3840, "height": 2160}]
    actor_assets = [{"ok": False}]

    risks = _export_risk_summary(doc, media_probe, actor_assets)
    areas = {risk["area"] for risk in risks}

    assert "preview/export CPU fallback" in areas
    assert "Live2D/Spine actor baking" in areas
    assert "decode/proxy" in areas
    assert "nested timeline export" in areas


def test_render_queue_product_diagnostics_suggests_action_for_preset_failures(tmp_path):
    from app.render_queue import RenderQueueJob, render_queue_product_diagnostics

    job = RenderQueueJob.create(
        label="Preset Export",
        out_path=str(tmp_path / "out.mp4"),
        in_ms=0,
        out_ms=1000,
        format_id="mp4",
        quality_id="high",
    )
    job.status = "error"
    job.error = "ffmpeg encoder failed"
    job.diagnostics = "Preset export parity mismatch: template overlay target missing"

    diag = render_queue_product_diagnostics(job)

    assert "ffmpeg encoder failed" in diag["summary"]
    assert diag["parity"] == "reported"
    assert any("Preset Application Corpus" in action for action in diag["actions"])
    assert any("encoder log" in action for action in diag["actions"])


def test_qa_dashboard_exposes_safe_runners():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.qa_dashboard import QADashboardDialog, _render_dashboard_trend

    QApplication.instance() or QApplication([])

    rows = {
        "productization": {"kind": "productization", "path": "debugCapture/productization_loop_qa.json"},
        "creator_polish_coverage": {"kind": "creator_polish_coverage", "path": "debugCapture/creator_polish_coverage_qa.json"},
        "commercial_expansion": {"kind": "commercial_expansion", "path": "debugCapture/commercial_expansion_qa.json"},
        "broadcast_release_readiness": {"kind": "broadcast_release_readiness", "path": "debugCapture/broadcast_release_readiness_qa.json"},
        "broadcast_platform_e2e": {"kind": "broadcast_platform_e2e", "path": "debugCapture/broadcast_platform_e2e_qa.json"},
        "public_positioning": {"kind": "public_positioning", "path": "debugCapture/public_positioning_qa.json"},
        "capcut_creator_workflow": {"kind": "capcut_creator_workflow", "path": "debugCapture/capcut_creator_workflow_qa.json"},
        "capcut_parity_next": {"kind": "capcut_parity_next", "path": "debugCapture/capcut_parity_next_qa.json"},
        "capcut_publish_review": {"kind": "capcut_publish_review", "path": "debugCapture/capcut_publish_review_qa.json"},
        "capcut_quick_result": {"kind": "capcut_quick_result", "path": "debugCapture/capcut_quick_result_qa.json"},
        "capcut_voice_workflow": {"kind": "capcut_voice_workflow", "path": "debugCapture/capcut_voice_workflow_qa.json"},
        "capcut_prompt_edit": {"kind": "capcut_prompt_edit", "path": "debugCapture/capcut_prompt_edit_qa.json"},
        "capcut_collab_handoff": {"kind": "capcut_collab_handoff", "path": "debugCapture/capcut_collab_handoff_qa.json"},
        "capcut_cloud_handoff": {"kind": "capcut_cloud_handoff", "path": "debugCapture/capcut_cloud_handoff_qa.json"},
        "creator_asset_packs": {"kind": "creator_asset_packs", "path": "debugCapture/creator_asset_packs_qa.json"},
        "local_ml_backend": {"kind": "local_ml_backend", "path": "debugCapture/local_ml_backend_qa.json"},
        "ai_edit_corpus_quality": {"kind": "ai_edit_corpus_quality", "path": "debugCapture/ai_edit_corpus_quality_qa.json"},
        "ai_edit_corpus_intake": {"kind": "ai_edit_corpus_intake", "path": "debugCapture/ai_edit_corpus_intake_qa.json"},
        "timeline_fuzzer": {"kind": "timeline_fuzzer", "path": "debugCapture/timeline_fuzzer_qa.json"},
        "timeline_alignment": {"kind": "timeline_alignment", "path": "debugCapture/timeline_alignment_qa.json"},
        "timeline_visual_alignment": {"kind": "timeline_visual_alignment", "path": "debugCapture/timeline_visual_alignment_qa/timeline_visual_alignment_report.json"},
        "timeline_preset_visibility": {"kind": "timeline_preset_visibility", "path": "debugCapture/timeline_preset_visibility_qa/timeline_preset_visibility_report.json"},
        "long_project_stress": {"kind": "long_project_stress", "path": "debugCapture/long_project_stress_qa.json"},
        "actor_workflow": {"kind": "actor_workflow", "path": "debugCapture/actor_lane_workflow_qa.json"},
        "actor_loading_ux": {"kind": "actor_loading_ux", "path": "debugCapture/actor_loading_ux_qa.json"},
        "node_graph_fuzzer": {"kind": "node_graph_fuzzer", "path": "debugCapture/node_graph_fuzzer_qa.json"},
        "node_graph_ui_fuzzer": {"kind": "node_graph_ui_fuzzer", "path": "debugCapture/node_graph_ui_fuzzer_qa.json"},
        "color_audio": {"kind": "color_audio", "path": "debugCapture/color_audio_accuracy_qa.json"},
        "preset_application": {"kind": "preset_application", "path": "debugCapture/preset_application_corpus_ui.json"},
        "editor_e2e_smoke": {"kind": "editor_e2e_smoke", "path": "debugCapture/editor_e2e_smoke_report.json"},
        "editor_export_bake": {"kind": "editor_export_bake", "path": "debugCapture/editor_export_bake_qa.json"},
        "gpu_preview_pixel_collision": {"kind": "gpu_preview_pixel_collision", "path": "debugCapture/gpu_preview_pixel_collision_qa.json"},
        "ar_pbr_attachment_stability": {"kind": "ar_pbr_attachment_stability", "path": "debugCapture/ar_pbr_attachment_stability_qa.json"},
        "visual": {"kind": "visual", "path": "debugCapture/visual_regression/visual_regression_report.json"},
        "visual_baseline": {"kind": "visual_baseline", "path": "debugCapture/visual_baseline_audit.json"},
        "micro_interactions": {"kind": "micro_interactions", "path": "debugCapture/micro_interactions_qa.json"},
        "screenstudio_export_handoff": {"kind": "screenstudio_export_handoff", "path": "debugCapture/screenstudio_export_handoff_qa.json"},
        "screenstudio_parity_gap": {"kind": "screenstudio_parity_gap", "path": "debugCapture/screenstudio_parity_gap_qa.json"},
        "screenstudio_real_corpus": {"kind": "screenstudio_real_corpus", "path": "debugCapture/screenstudio_real_recording_corpus_qa.json"},
        "screenstudio_sidecar_intake": {"kind": "screenstudio_sidecar_intake", "path": "debugCapture/screenstudio_sidecar_intake_qa.json"},
        "screenstudio_productization_next": {"kind": "screenstudio_productization_next", "path": "debugCapture/screenstudio_productization_next_qa.json"},
        "screenstudio_manual_zoom": {"kind": "screenstudio_manual_zoom", "path": "debugCapture/screenstudio_manual_zoom_qa.json"},
        "actor_mass_compat": {"kind": "actor_mass_compat", "path": "debugCapture/actor_mass_compat_qa.json"},
    }

    assert "qa_productization_loop.py" in " ".join(QADashboardDialog._command_for_row(rows["productization"]))
    assert "qa_creator_polish_coverage.py" in " ".join(QADashboardDialog._command_for_row(rows["creator_polish_coverage"]))
    assert "qa_commercial_expansion.py" in " ".join(QADashboardDialog._command_for_row(rows["commercial_expansion"]))
    assert "qa_broadcast_release_readiness.py" in " ".join(QADashboardDialog._command_for_row(rows["broadcast_release_readiness"]))
    assert "--allow-not-ready" in " ".join(QADashboardDialog._command_for_row(rows["broadcast_release_readiness"]))
    assert "qa_broadcast_platform_e2e.py" in " ".join(QADashboardDialog._command_for_row(rows["broadcast_platform_e2e"]))
    assert "--allow-pending-platform" in " ".join(QADashboardDialog._command_for_row(rows["broadcast_platform_e2e"]))
    assert "qa_public_positioning.py" in " ".join(QADashboardDialog._command_for_row(rows["public_positioning"]))
    assert "qa_capcut_creator_workflow.py" in " ".join(QADashboardDialog._command_for_row(rows["capcut_creator_workflow"]))
    assert "qa_capcut_parity_next.py" in " ".join(QADashboardDialog._command_for_row(rows["capcut_parity_next"]))
    assert "qa_capcut_publish_review.py" in " ".join(QADashboardDialog._command_for_row(rows["capcut_publish_review"]))
    assert "qa_capcut_quick_result.py" in " ".join(QADashboardDialog._command_for_row(rows["capcut_quick_result"]))
    assert "qa_capcut_voice_workflow.py" in " ".join(QADashboardDialog._command_for_row(rows["capcut_voice_workflow"]))
    assert "qa_capcut_prompt_edit.py" in " ".join(QADashboardDialog._command_for_row(rows["capcut_prompt_edit"]))
    assert "qa_capcut_collab_handoff.py" in " ".join(QADashboardDialog._command_for_row(rows["capcut_collab_handoff"]))
    assert "qa_capcut_cloud_handoff.py" in " ".join(QADashboardDialog._command_for_row(rows["capcut_cloud_handoff"]))
    assert "qa_creator_asset_packs.py" in " ".join(QADashboardDialog._command_for_row(rows["creator_asset_packs"]))
    assert "qa_local_ml_backend.py" in " ".join(QADashboardDialog._command_for_row(rows["local_ml_backend"]))
    ai_quality_cmd = " ".join(QADashboardDialog._command_for_row(rows["ai_edit_corpus_quality"]))
    assert "qa_ai_edit_corpus_quality.py" in ai_quality_cmd
    assert "--use-provider" not in ai_quality_cmd
    ai_intake_cmd = " ".join(QADashboardDialog._command_for_row(rows["ai_edit_corpus_intake"]))
    assert "prepare_ai_edit_corpus_intake.py" in ai_intake_cmd
    assert "--write-templates" in ai_intake_cmd
    assert "qa_timeline_fuzzer.py" in " ".join(QADashboardDialog._command_for_row(rows["timeline_fuzzer"]))
    assert "qa_timeline_alignment.py" in " ".join(QADashboardDialog._command_for_row(rows["timeline_alignment"]))
    assert "qa_timeline_visual_alignment.py" in " ".join(QADashboardDialog._command_for_row(rows["timeline_visual_alignment"]))
    assert "qa_timeline_preset_visibility.py" in " ".join(QADashboardDialog._command_for_row(rows["timeline_preset_visibility"]))
    assert "qa_long_project_stress.py" in " ".join(QADashboardDialog._command_for_row(rows["long_project_stress"]))
    assert "qa_actor_lane_workflow.py" in " ".join(QADashboardDialog._command_for_row(rows["actor_workflow"]))
    assert "--include-samples" in " ".join(QADashboardDialog._command_for_row(rows["actor_workflow"]))
    assert "qa_actor_loading_ux.py" in " ".join(QADashboardDialog._command_for_row(rows["actor_loading_ux"]))
    assert "qa_node_graph_fuzzer.py" in " ".join(QADashboardDialog._command_for_row(rows["node_graph_fuzzer"]))
    assert "qa_node_graph_ui_fuzzer.py" in " ".join(QADashboardDialog._command_for_row(rows["node_graph_ui_fuzzer"]))
    assert "qa_color_audio_accuracy.py" in " ".join(QADashboardDialog._command_for_row(rows["color_audio"]))
    assert "qa_preset_application_corpus.py" in " ".join(QADashboardDialog._command_for_row(rows["preset_application"]))
    assert "qa_editor_e2e_smoke.py" in " ".join(QADashboardDialog._command_for_row(rows["editor_e2e_smoke"]))
    assert "qa_editor_export_bake.py" in " ".join(QADashboardDialog._command_for_row(rows["editor_export_bake"]))
    assert "qa_gpu_preview_pixel_collision.py" in " ".join(QADashboardDialog._command_for_row(rows["gpu_preview_pixel_collision"]))
    assert "qa_ar_pbr_attachment_stability.py" in " ".join(QADashboardDialog._command_for_row(rows["ar_pbr_attachment_stability"]))
    assert "qa_visual_regression.py" in " ".join(QADashboardDialog._command_for_row(rows["visual"]))
    assert "qa_visual_baseline_audit.py" in " ".join(QADashboardDialog._command_for_row(rows["visual_baseline"]))
    assert "qa_micro_interactions.py" in " ".join(QADashboardDialog._command_for_row(rows["micro_interactions"]))
    assert "qa_screenstudio_export_handoff.py" in " ".join(QADashboardDialog._command_for_row(rows["screenstudio_export_handoff"]))
    assert "qa_screenstudio_parity_gap.py" in " ".join(QADashboardDialog._command_for_row(rows["screenstudio_parity_gap"]))
    assert "qa_screenstudio_real_recording_corpus.py" in " ".join(QADashboardDialog._command_for_row(rows["screenstudio_real_corpus"]))
    sidecar_cmd = " ".join(QADashboardDialog._command_for_row(rows["screenstudio_sidecar_intake"]))
    assert "prepare_screenstudio_sidecar_intake.py" in sidecar_cmd
    assert "--write-templates" in sidecar_cmd
    assert "qa_screenstudio_productization_next.py" in " ".join(QADashboardDialog._command_for_row(rows["screenstudio_productization_next"]))
    assert "qa_screenstudio_manual_zoom.py" in " ".join(QADashboardDialog._command_for_row(rows["screenstudio_manual_zoom"]))
    assert "qa_actor_mass_compat.py" in " ".join(QADashboardDialog._command_for_row(rows["actor_mass_compat"]))
    assert QADashboardDialog._fast_qa_commands()
    assert "build_qa_corpus.py" in " ".join(QADashboardDialog._fast_qa_commands()[0])
    pix = _render_dashboard_trend([
        {"exists": True, "ok": True},
        {"exists": True, "ok": False},
        {"exists": False, "ok": False},
    ])
    assert not pix.isNull()


def test_actor_qa_browser_discovers_baseline_and_actual_images(tmp_path):
    from app.actor_qa_browser import _image_candidates

    baseline = tmp_path / "baseline.png"
    actual = tmp_path / "actual.png"
    baseline.write_bytes(b"png")
    actual.write_bytes(b"png")

    row = {
        "golden": {"baseline": str(baseline)},
        "render": {"actual": str(actual)},
    }

    assert _image_candidates(row) == (baseline, actual)


def test_productization_loop_covers_all_commercial_polish_areas():
    from tools.qa_productization_loop import AREAS, build_productization_report

    report = build_productization_report()
    ids = {row["id"] for row in report["areas"]}

    assert len(report["areas"]) == len(AREAS)
    assert ids == {area_id for area_id, _label, _evidence in AREAS}
    assert "creator_polish_coverage" in ids
    assert "commercial_expansion_package" in ids
    assert "professional_runtime_parity" in ids
    assert "score" in report
    assert report["summary"]["areas"] == len(AREAS)


def test_new_project_dialog_exposes_starter_templates():
    from PySide6.QtWidgets import QApplication

    from app.new_project_dialog import NewProjectDialog

    QApplication.instance() or QApplication([])
    dlg = NewProjectDialog()
    try:
        assert dlg._starter_combo.count() >= 6
        assert dlg._starter_combo.currentData()["id"] == "screen-recording-demo"
        dlg._starter_combo.setCurrentIndex(2)
        dlg._on_create()
        assert dlg.result_settings is not None
        assert dlg.result_settings.starter_template_id == "vertical-shorts"
        assert dlg.result_settings.starter_template_label == "Vertical Shorts"
        assert dlg.result_settings.fps == 60.0
        assert dlg.result_settings.width == 1080
        assert dlg.result_settings.height == 1920
    finally:
        dlg.close()


def test_live2d_actor_lane_double_click_uses_timeline_ruler_coordinates():
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    from app.live2d.actor_lane_row import Live2DActorLaneRow
    from app.live2d.actor_track import Live2DActorTrack
    from app.timeline_ruler import TimelineRuler

    QApplication.instance() or QApplication([])
    track = Live2DActorTrack(id=1, label="Live2D 1")
    row = Live2DActorLaneRow(track)
    try:
        row.set_px_per_sec(100)
        row._create_clip("", 1000)
        clip = track.clips[0]
        clicked = []
        row.clip_double_clicked.connect(clicked.append)

        x = row._ms_to_x(clip.start_ms) + 8
        event = QMouseEvent(
            QEvent.Type.MouseButtonDblClick,
            QPointF(float(x), 14.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        row.mouseDoubleClickEvent(event)

        assert row._ms_to_x(0) == TimelineRuler.MARGIN
        assert row._clip_at(x) is clip
        assert clicked == [clip]
    finally:
        row.close()


def test_live2d_editor_bottom_bar_builds_without_layout_shadowing():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.live2d.live2d_viewer import Live2DEditorWindow

    QApplication.instance() or QApplication([])
    win = Live2DEditorWindow(autoload_sample=False)
    try:
        assert win._status_lbl is not None
        assert win._motion_label is not None
        assert win._loading_bar is not None
        assert not win._loading_bar.isVisible()
    finally:
        win.close()
        win.deleteLater()


def test_live2d_editor_loading_bar_lasts_until_first_frame():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.live2d.live2d_viewer import Live2DEditorWindow

    QApplication.instance() or QApplication([])
    win = Live2DEditorWindow(autoload_sample=False)
    try:
        win.show()
        win._set_loading(True, "첫 프레임 렌더링 중…")
        assert win._loading_bar.isVisible()
        assert "렌더링" in win._status_lbl.text()

        win._pending_loaded_name = "hero"
        win._on_first_frame_ready()
        assert not win._loading_bar.isVisible()
        assert win._status_lbl.text() == "✓ hero"
    finally:
        win.close()
        win.deleteLater()


def test_live2d_editor_deferred_load_cancels_stale_autoload():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.live2d.live2d_viewer import Live2DEditorWindow

    app = QApplication.instance() or QApplication([])
    win = Live2DEditorWindow(autoload_sample=False)
    calls = []

    def fake_load(path, *, _from_deferred=False):
        calls.append((path, _from_deferred))

    win._load_model = fake_load
    try:
        win.show()
        win.load_model_deferred("sample.model3.json", delay_ms=50)
        win.load_model_deferred("timeline.model3.json", delay_ms=0)
        deadline = time.time() + 0.15
        while time.time() < deadline:
            app.processEvents()
            time.sleep(0.005)

        assert calls == [("timeline.model3.json", True)]
    finally:
        win.close()
        win.deleteLater()


def test_live2d_clip_double_click_uses_deferred_timeline_load(monkeypatch):
    from app.video_editor_window import VideoEditorWindow

    created = []

    class _Destroyed:
        def connect(self, _cb):
            pass

    class FakeLive2DEditor:
        def __init__(self, parent=None, *, autoload_sample=True):
            self.parent = parent
            self.autoload_sample = autoload_sample
            self.destroyed = _Destroyed()
            self.calls = []
            created.append(self)

        def set_target_clip(self, clip, lane_row):
            self.calls.append(("target", clip, lane_row))

        def show(self):
            self.calls.append(("show",))

        def raise_(self):
            self.calls.append(("raise",))

        def activateWindow(self):
            self.calls.append(("activate",))

        def load_model_deferred(self, path, delay_ms=120):
            self.calls.append(("deferred", path, delay_ms))

        def _load_model(self, path):
            raise AssertionError(f"Live2D clip open should defer model loading: {path}")

    monkeypatch.setattr(
        "app.live2d.live2d_viewer.Live2DEditorWindow",
        FakeLive2DEditor,
    )
    clip = SimpleNamespace(model_path="hero.model3.json", start_ms=100, end_ms=200)
    lane_row = SimpleNamespace(track=SimpleNamespace(clips=[clip]))
    editor = SimpleNamespace(
        _live2d_editor=None,
        _live2d_lane_rows=[lane_row],
        _record_editor_action=lambda *args, **kwargs: None,
    )

    VideoEditorWindow._on_live2d_clip_dclick(editor, clip)

    fake = created[0]
    assert fake.autoload_sample is False
    assert ("target", clip, lane_row) in fake.calls
    assert ("show",) in fake.calls
    assert fake.calls[-1] == ("deferred", "hero.model3.json", 120)


def test_actor_clip_double_click_moves_playhead_into_clip(monkeypatch):
    from app.video_editor_window import VideoEditorWindow

    class _Destroyed:
        def connect(self, _cb):
            pass

    class FakeLive2DEditor:
        destroyed = _Destroyed()

        def __init__(self, parent=None, *, autoload_sample=True):
            self.destroyed = _Destroyed()

        def set_target_clip(self, clip, lane_row):
            pass

        def show(self):
            pass

        def raise_(self):
            pass

        def activateWindow(self):
            pass

        def load_model_deferred(self, path, delay_ms=120):
            pass

    class FakePlayer:
        def __init__(self):
            self._pos = 0
            self.seeked = []

        def position(self):
            return self._pos

        def set_position(self, ms):
            self._pos = int(ms)
            self.seeked.append(int(ms))

        def refresh_current_frame(self):
            pass

    monkeypatch.setattr(
        "app.live2d.live2d_viewer.Live2DEditorWindow",
        FakeLive2DEditor,
    )
    clip = SimpleNamespace(model_path="hero.model3.json", start_ms=1000, end_ms=2200)
    lane_row = SimpleNamespace(track=SimpleNamespace(clips=[clip]))
    player = FakePlayer()
    visible = []
    editor = SimpleNamespace(
        _live2d_editor=None,
        _live2d_lane_rows=[lane_row],
        _player=player,
        _ensure_playhead_visible=lambda: visible.append(True),
        _record_editor_action=lambda *args, **kwargs: None,
    )
    editor._focus_actor_clip_for_edit = (
        lambda target_clip, refresh=True:
        VideoEditorWindow._focus_actor_clip_for_edit(
            editor,
            target_clip,
            refresh=refresh,
        )
    )

    VideoEditorWindow._on_live2d_clip_dclick(editor, clip)

    assert player.seeked
    assert 1000 <= player.seeked[-1] < 2200
    assert visible == [True]


def test_live2d_performance_source_mapping_uses_active_source(monkeypatch, tmp_path):
    from app.video_editor_window import VideoEditorWindow
    import app.actions as actions

    source = tmp_path / "face.mp4"
    source.write_bytes(b"placeholder")
    clip = SimpleNamespace(model_path="avatar.model3.json", start_ms=0, end_ms=2000)
    owner = SimpleNamespace(id=42, clips=[clip])
    perf_clip = SimpleNamespace(
        performance_source=True,
        source_path=str(source),
        start_ms=0,
        end_ms=2000,
    )
    perf_track = SimpleNamespace(
        track_type="vtuber_performance_source",
        label="Performance Source",
        clips=[perf_clip],
    )

    executed: list[tuple[str, dict]] = []

    class _Result:
        def to_dict(self):
            return {
                "ok": True,
                "result": {
                    "source_path": str(source),
                    "subject_type": "upper_body",
                    "mocap": {"sample_count": 12},
                    "program_output": False,
                },
            }

    class _Registry:
        def execute(self, action_id, params):
            executed.append((action_id, dict(params)))
            return _Result()

    monkeypatch.setattr(
        actions,
        "build_default_action_registry",
        lambda _editor: _Registry(),
    )

    selected = []
    focused = []
    changed = []
    recorded = []
    statuses = []
    editor = SimpleNamespace(
        _tracks=[perf_track],
        _player=SimpleNamespace(position=lambda: 500),
        _select_live2d_clip_in_lane=lambda target: selected.append(target),
        _focus_actor_clip_for_edit=lambda target, refresh=True: focused.append((target, refresh)),
        _live2d_owner_track_for_clip=lambda target: owner if target is clip else None,
        _on_live2d_clip_changed=lambda: changed.append(True),
        _record_editor_action=lambda event, **data: recorded.append((event, data)),
        _flash_status=lambda message: statuses.append(message),
    )

    VideoEditorWindow._on_live2d_clip_performance_source_mapping_requested(editor, clip)

    assert executed == [
        (
            "actor.live2d.apply_performance_source",
            {
                "track_id": 42,
                "clip_index": 0,
                "time_ms": 500,
                "analyze_video": True,
                "sample_fps": 10.0,
                "max_samples": 900,
                "apply_mocap": True,
                "apply_framing": True,
                "replace_transform": True,
            },
        )
    ]
    assert selected == [clip, clip]
    assert focused == [(clip, False)]
    assert changed == [True]
    assert recorded[0][0] == "actor.live2d.performance_source_mapping.apply"
    assert recorded[0][1]["program_output"] is False
    assert recorded[0][1]["subject_type"] == "upper_body"
    assert "upper_body" in statuses[-1]


def test_live2d_editor_applies_current_model_without_apply_button():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.live2d.live2d_viewer import Live2DEditorWindow

    class _Signal:
        def __init__(self):
            self.count = 0

        def emit(self):
            self.count += 1

    class _Clip(SimpleNamespace):
        def reset(self):
            self.reset_count = getattr(self, "reset_count", 0) + 1

    QApplication.instance() or QApplication([])
    win = Live2DEditorWindow(autoload_sample=False)
    clip = _Clip(
        model_path="",
        motion_group="",
        motion_idx=-1,
        pos_x=0.5,
        pos_y=0.5,
        scale=1.0,
        opacity=1.0,
    )
    signal = _Signal()
    row = SimpleNamespace(update=lambda: None, clip_changed=signal)
    try:
        win._ensure_model_supported = lambda _path: True
        win.set_target_clip(clip, row)
        win._current_model_path = "hero.model3.json"
        win._motions = [("Idle", 0, "idle")]
        win._current_motion_idx = 0

        win._apply_current_model_to_target()

        assert clip.model_path == "hero.model3.json"
        assert clip.motion_group == "Idle"
        assert clip.motion_idx == 0
        assert signal.count == 1
    finally:
        win.close()
        win.deleteLater()


def test_live2d_editor_performance_source_mapping_button_calls_parent_handler():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QWidget

    from app.live2d.live2d_viewer import Live2DEditorWindow

    QApplication.instance() or QApplication([])
    parent = QWidget()
    calls = []
    focused = []
    parent._on_live2d_clip_performance_source_mapping_requested = lambda clip: calls.append(clip)
    parent._focus_actor_clip_for_edit = lambda clip, refresh=True: focused.append((clip, refresh))
    win = Live2DEditorWindow(parent, autoload_sample=False)
    clip = SimpleNamespace(pos_x=0.5, pos_y=0.5, scale=1.0, opacity=1.0)
    try:
        win.set_target_clip(clip, SimpleNamespace())

        assert win._performance_source_mapping_btn.isEnabled()
        win._performance_source_mapping_btn.click()

        assert calls == [clip]
        assert focused == [(clip, True), (clip, True)]
    finally:
        win.close()
        win.deleteLater()
        parent.deleteLater()


def test_actor_loading_status_badges():
    from app.actor_loading_status import actor_clip_badge, set_actor_clip_status

    clip = SimpleNamespace()
    for status, text in {
        "loading": "LOAD",
        "ready": "OK",
        "error": "ERR",
        "timeout": "TIME",
        "cancelled": "STOP",
    }.items():
        set_actor_clip_status(clip, status, f"{status} message")
        assert actor_clip_badge(clip)[0] == text


def test_spine_editor_loading_bar_lasts_until_first_frame():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.spine_editor.editor_window import SpineEditorWindow

    QApplication.instance() or QApplication([])
    win = SpineEditorWindow(autoload_sample=False)
    try:
        win.show()
        win._set_loading(True, "첫 프레임 렌더링 중…")
        assert win._loading_bar.isVisible()
        assert win._cancel_load_btn.isVisible()
        win._pending_loaded_name = "hero  1뼈 1애님"
        win._on_first_frame_ready()
        assert not win._loading_bar.isVisible()
        assert win._info_lbl.text() == "✓ hero  1뼈 1애님"
    finally:
        win.close()
        win.deleteLater()


def test_live2d_editor_loading_panel_lasts_until_first_frame():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QProgressBar, QPushButton

    from app.live2d.live2d_viewer import Live2DEditorWindow

    QApplication.instance() or QApplication([])
    ctx = SimpleNamespace(
        _loading_active=False,
        _loading_bar=QProgressBar(),
        _loading_panel=QFrame(),
        _loading_panel_bar=QProgressBar(),
        _loading_panel_label=QLabel(),
        _cancel_load_btn=QPushButton(),
        _status_lbl=QLabel(),
        _load_timeout_timer=QTimer(),
        _append_load_log=lambda text: None,
    )

    Live2DEditorWindow._set_loading(
        ctx,
        True,
        "첫 프레임 렌더링 중…",
        progress=90,
        stage="first_frame",
    )
    assert ctx._loading_bar.isVisible()
    assert ctx._loading_panel.isVisible()
    assert ctx._loading_panel_bar.value() == 90
    assert "첫 프레임" in ctx._loading_panel_label.text()

    Live2DEditorWindow._set_loading(ctx, False, "✓ hero", progress=100, stage="ready")
    assert not ctx._loading_bar.isVisible()
    assert not ctx._loading_panel.isVisible()


def test_preset_ab_preview_draws_animated_cursor_phase():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import _render_preset_ab_application_preview

    QApplication.instance() or QApplication([])
    a = _render_preset_ab_application_preview(
        preset_id="qa-cursor",
        kind="transition",
        label="QA Cursor",
        payload={"type": "wipe"},
        tags=("screen-studio",),
        sample_pixmap=None,
        phase=0.0,
    )
    b = _render_preset_ab_application_preview(
        preset_id="qa-cursor",
        kind="transition",
        label="QA Cursor",
        payload={"type": "wipe"},
        tags=("screen-studio",),
        sample_pixmap=None,
        phase=0.45,
    )

    assert not a.isNull()
    assert not b.isNull()
    assert a.toImage() != b.toImage()


def test_template_ab_preview_varies_by_sequence_phase():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import _render_preset_ab_application_preview

    QApplication.instance() or QApplication([])
    payload = {
        "sequence": [
            {"kind": "effect", "preset_id": "effect-a", "at_ms": 0, "duration_ms": 1000},
            {"kind": "title", "preset_id": "title-a", "at_ms": 400, "duration_ms": 1200},
            {"kind": "audio", "preset_id": "audio-a", "at_ms": 700, "duration_ms": 800},
            {"kind": "color", "preset_id": "color-a", "at_ms": 1000, "duration_ms": 900},
        ]
    }
    a = _render_preset_ab_application_preview(
        preset_id="qa-template",
        kind="template",
        label="QA Template",
        payload=payload,
        tags=("template", "screen-studio"),
        sample_pixmap=None,
        phase=0.05,
    )
    b = _render_preset_ab_application_preview(
        preset_id="qa-template",
        kind="template",
        label="QA Template",
        payload=payload,
        tags=("template", "screen-studio"),
        sample_pixmap=None,
        phase=0.62,
    )

    assert not a.isNull()
    assert not b.isNull()
    assert a.toImage() != b.toImage()


def test_preset_application_preview_varies_by_effect_payload():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import _render_preset_application_frame_preview

    QApplication.instance() or QApplication([])
    soft = _render_preset_application_frame_preview(
        preset_id="qa-soft",
        kind="effect",
        label="Soft Denoise",
        payload={"video_filters": {"enabled": True, "blur": True, "denoise": True}},
        tags=("denoise",),
        sample_pixmap=None,
    )
    key = _render_preset_application_frame_preview(
        preset_id="qa-key",
        kind="effect",
        label="Key Matte",
        payload={"chroma_key": {"enabled": True}, "video_filters": {"enabled": True, "glitch": True}},
        tags=("keying", "glitch"),
        sample_pixmap=None,
    )

    assert not soft.isNull()
    assert not key.isNull()
    assert soft.toImage() != key.toImage()


def test_preset_overlay_preview_supports_effect_and_transition():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QWidget

    from app.video_editor_window import VideoEditorWindow

    QApplication.instance() or QApplication([])
    canvas = QWidget()
    canvas.resize(640, 360)
    editor = SimpleNamespace(
        _drawing_canvas=canvas,
        _preset_preview_overlay=None,
        _preset_preview_overlay_payload=None,
    )
    editor._clear_preset_overlay_preview = MethodType(
        VideoEditorWindow._clear_preset_overlay_preview,
        editor,
    )

    VideoEditorWindow._show_preset_overlay_preview(
        editor,
        "effect",
        {"video_filters": {"glitch": 0.75}, "chroma_key": {"enabled": True}},
        "Glitch Key",
    )

    label = editor._preset_preview_overlay
    assert label is not None
    assert not label.isHidden()
    assert label.property("presetOverlayKind") == "effect"
    assert label.property("presetOverlayFrameMarker") is True
    assert "FX PREVIEW" in label.text()
    assert "FX ON FRAME" in label.text()
    assert "Glitch Key" in label.text()
    assert "Chroma Key" in label.text()

    VideoEditorWindow._show_preset_overlay_preview(
        editor,
        "transition",
        {"type": "wipe", "transition_out_ms": 450},
        "Wipe Pop",
    )

    label = editor._preset_preview_overlay
    assert label is not None
    assert label.property("presetOverlayKind") == "transition"
    assert "TRANSITION" in label.text()
    assert "CUT MARKER" in label.text()
    assert "Wipe Pop" in label.text()
    assert "450ms" in label.text()


def test_effect_live_preview_shows_frame_overlay_without_target_clip():
    from app.video_editor_window import VideoEditorWindow

    calls: list[tuple[str, str, str] | str] = []
    editor = SimpleNamespace(
        _clear_preset_live_preview=lambda: calls.append("clear"),
        _show_preset_overlay_preview=lambda kind, payload, label: calls.append(
            ("overlay", kind, label)
        ),
        _workflow_target_video_clip=lambda: (None, None),
    )

    VideoEditorWindow._begin_preset_live_preview(
        editor,
        "effect",
        {"video_filters": {"vignette": 0.6}},
        "Vignette",
    )

    assert calls == ["clear", ("overlay", "effect", "Vignette")]


def test_workflow_preview_focus_seeks_target_position():
    from app.video_editor_window import VideoEditorWindow

    calls: list[tuple[str, int] | tuple[str, int | None]] = []

    class Player:
        def set_position(self, ms: int) -> None:
            calls.append(("seek", int(ms)))

    editor = SimpleNamespace(
        _active_track_id=1,
        _player=Player(),
        _set_active_track=lambda track_id: calls.append(("active", int(track_id))),
        _refresh_preview_soft=lambda track=None: calls.append(("refresh", getattr(track, "id", None))),
    )

    VideoEditorWindow._focus_preview_at_workflow_ms(
        editor,
        1234,
        track=SimpleNamespace(id=2),
    )

    assert calls == [("active", 2), ("seek", 1234), ("refresh", 2)]


def test_timeline_clip_status_badges_report_applied_presets():
    from app.video_editor_window import TrackRow
    from app.color_grading import ColorGrade

    clip = SimpleNamespace(
        timeline_in_ms=1000,
        timeline_out_ms=3000,
        video_filters={"enabled": True},
        chroma_key={"enabled": True},
        bg_removal=None,
        transition_out_type="wipe_left",
        color_grade=ColorGrade(brightness=12),
        is_nested_sequence=False,
        compound_group_id=None,
    )
    row = SimpleNamespace(
        track=SimpleNamespace(
            typography_actors=[SimpleNamespace(start_ms=1200, end_ms=1800)],
            zoom_actors=[SimpleNamespace(start_ms=1500, end_ms=2600)],
        ),
        _effect_param_active=TrackRow._effect_param_active,
        _ranges_overlap=TrackRow._ranges_overlap,
    )

    labels = [badge[0] for badge in TrackRow._clip_status_badges(row, clip)]

    assert labels == ["FX", "Key", "TR", "COL", "T", "Mot"]


def test_timeline_effect_strip_includes_title_motion_and_nested_context():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import TrackRow

    QApplication.instance() or QApplication([])
    clip = SimpleNamespace(
        id=8,
        timeline_in_ms=1000,
        timeline_out_ms=5000,
        video_filters=None,
        chroma_key=None,
        bg_removal=None,
        transition_out_type="",
        color_grade=None,
        node_graph=None,
        screenstudio_polish={"auto_zoom_actor_ids": [1]},
        is_nested_sequence=True,
        compound_group_id=None,
    )
    track = SimpleNamespace(
        id=2,
        duration_ms=6000,
        offset_ms=0,
        clips=[clip],
        typography_actors=[SimpleNamespace(start_ms=1200, end_ms=1800, text="Intro Caption")],
        zoom_actors=[SimpleNamespace(start_ms=2000, end_ms=4200, label="Cursor Zoom")],
    )
    row = TrackRow(track)
    try:
        entries = row._clip_effect_strip_entries(clip)
        tags = [entry[0] for entry in entries]
        tooltip = row._clip_effect_tooltip(clip)
        assert tags == ["AP", "T", "Mot", "Nest"]
        assert "Intro Caption" in tooltip
        assert "Cursor Zoom" in tooltip
        assert "Nested" in tooltip
    finally:
        row.deleteLater()


def test_audio_clip_status_badge_detects_effect_chain():
    from app.video_editor_window import AudioTrackRow

    clean = SimpleNamespace(effects={"eq": {"enabled": False}})
    processed = SimpleNamespace(
        effects={
            "eq": {"enabled": True, "mid": {"gain": 3.0}},
            "ai_master": {"preset": "Custom"},
        }
    )
    ai = SimpleNamespace(effects={"ai_master": {"preset": "Dialogue Polish"}})

    assert not AudioTrackRow._audio_clip_effects_active(clean)
    assert AudioTrackRow._audio_clip_effects_active(processed)
    assert AudioTrackRow._audio_clip_effects_active(ai)


def test_workflow_apply_summary_text_counts_template_steps():
    from app.preset_library import EditorPreset
    from app.video_editor_window import VideoEditorWindow

    preset = EditorPreset(id="template-summary", kind="template", name="Summary Template")
    text = VideoEditorWindow._workflow_apply_summary_text(
        preset,
        [
            {"kind": "template", "status": "template"},
            {"kind": "effect", "status": "will_apply"},
            {"kind": "title", "status": "will_apply"},
            {"kind": "audio", "status": "will_apply"},
            {"kind": "effect", "status": "will_apply"},
            {"kind": "color", "status": "blocked"},
        ],
    )

    assert "Summary Template" in text
    assert "4 step(s)" in text
    assert "FX 2" in text
    assert "Title" in text
    assert "Audio" in text
    assert "Color" not in text


def test_workflow_apply_summary_text_supports_non_template_feedback():
    from app.preset_library import EditorPreset
    from app.video_editor_window import VideoEditorWindow

    preset = EditorPreset(id="effect-feedback", kind="effect", name="Readable Text")
    text = VideoEditorWindow._workflow_apply_summary_text(
        preset,
        [{"kind": "effect", "status": "will_apply"}],
    )
    empty = VideoEditorWindow._workflow_apply_summary_text(preset, [])

    assert "Preset applied" in text
    assert "FX" in text
    assert "Effect applied" in empty
    assert "Template applied" not in empty


def test_preset_feedback_models_are_ui_ready():
    from app.preset_feedback import (
        preset_application_feedback_model,
        preset_discoverability_cards,
        preset_drop_feedback_model,
    )
    from app.preset_library import EditorPreset, preset_by_id

    preset = EditorPreset(id="fx-feedback", kind="effect", name="Readable Text")
    model = preset_application_feedback_model(
        preset,
        [{"kind": "effect", "status": "will_apply", "duration_ms": 1400}],
        focus_ms=2200,
        track_label="Track 1",
    )
    drop = preset_drop_feedback_model(
        preset,
        can_drop=False,
        reason="Select a video clip",
        project_ms=2200,
        track_label="Track 1",
    )
    cards = preset_discoverability_cards()

    assert model["badge"] == "FX"
    assert model["duration_ms"] == 1400
    assert "Track 1" in model["where"]
    assert drop["state"] == "blocked"
    assert "Select a video clip" in drop["detail"]
    assert {card["id"] for card in cards} >= {"drag_to_clip", "right_click_badge", "quick_create"}
    assert preset_by_id("template-screenstudio-quick-tutorial") is not None
    assert preset_by_id("template-product-demo-quick-result") is not None


def test_workflow_preset_panel_filters_template_browser(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    _ = app

    import app.preset_library as preset_library
    from app.preset_library import EditorPreset
    from app.video_editor_window import WorkflowPresetCard, WorkflowPresetPanel

    template = EditorPreset(
        id="template-browser-only",
        kind="template",
        name="Template Browser Only",
        payload={"sequence": []},
    )
    sticker = EditorPreset(
        id="sticker-not-template",
        kind="sticker",
        name="Sticker Not Template",
    )
    monkeypatch.setattr(preset_library, "load_editor_presets", lambda: [template, sticker])

    panel = WorkflowPresetPanel(kinds={"template"}, max_height=120, placeholder="Search templates")
    try:
        cards = panel.findChildren(WorkflowPresetCard)
        assert len(cards) == 1
        assert cards[0]._preset.id == "template-browser-only"
    finally:
        panel.deleteLater()


def test_timeline_clip_status_badge_hit_returns_action():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import TrackRow

    QApplication.instance() or QApplication([])
    clip = SimpleNamespace(
        id=4,
        timeline_in_ms=0,
        timeline_out_ms=3000,
        video_filters={"enabled": True},
        chroma_key=None,
        bg_removal=None,
        transition_out_type="",
        source_in_ms=0,
        source_duration_ms=3000,
        effective_source_out_ms=3000,
        is_nested_sequence=False,
        compound_group_id=None,
    )
    track = SimpleNamespace(
        id=1,
        duration_ms=3000,
        offset_ms=0,
        clips=[clip],
        typography_actors=[],
        zoom_actors=[],
    )
    row = TrackRow(track)
    rect = row._clip_rect(clip)
    badge_rects = row._clip_status_badge_rects(clip, rect)

    fx_rect = next(rect for label, action, rect in badge_rects if label == "FX" and action == "fx")
    assert row._clip_status_action_at(clip, fx_rect.center()) == "fx"


def test_workbench_fx_summary_lists_selected_clip_stack():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.workbench_panel import WorkbenchPanel

    QApplication.instance() or QApplication([])
    panel = WorkbenchPanel()
    clip = SimpleNamespace(
        timeline_in_ms=1000,
        timeline_out_ms=3000,
        video_filters={"enabled": True},
        chroma_key={"enabled": True},
        transition_out_type="dissolve",
        transition_out_ms=450,
    )
    track = SimpleNamespace(
        id=1,
        source_path="clip.mp4",
        duration_ms=5000,
        offset_ms=0,
        speed_segments=[],
        fades=[],
        typography_actors=[SimpleNamespace(start_ms=1200, end_ms=1600)],
        zoom_actors=[SimpleNamespace(start_ms=1700, end_ms=2500)],
    )

    panel.set_video_track(track, selected_clip=clip)

    text = panel._fx_summary_body.text()
    assert "FX: video filter preset" in text
    assert "Key: chroma/alpha preset" in text
    assert "TR: Dissolve 450ms" in text
    assert "TXT:" in text
    assert "Mot: 1" in text
    assert panel._fx_edit_clip_btn.isEnabled()
    assert panel._fx_toggle_clip_btn.isEnabled()
    assert panel._fx_toggle_clip_btn.text() == ""
    assert panel._fx_toggle_clip_btn.accessibleName() == "Disable clip FX"
    assert panel._fx_clear_clip_btn.isEnabled()
    assert panel._fx_clear_transition_btn.isEnabled()


def test_workbench_fx_summary_reports_disabled_clip_fx():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.workbench_panel import WorkbenchPanel

    QApplication.instance() or QApplication([])
    panel = WorkbenchPanel()
    clip = SimpleNamespace(
        timeline_in_ms=0,
        timeline_out_ms=1000,
        video_filters=None,
        chroma_key=None,
        bg_removal=None,
        disabled_video_filters={"enabled": True},
        disabled_chroma_key=None,
        disabled_bg_removal=None,
        transition_out_type="",
        transition_out_ms=0,
    )
    track = SimpleNamespace(
        id=1,
        source_path="clip.mp4",
        duration_ms=1000,
        offset_ms=0,
        speed_segments=[],
        fades=[],
        typography_actors=[],
        zoom_actors=[],
    )

    panel.set_video_track(track, selected_clip=clip)

    assert "Disabled: FX stored" in panel._fx_summary_body.text()
    assert panel._fx_toggle_clip_btn.text() == ""
    assert panel._fx_toggle_clip_btn.accessibleName() == "Enable clip FX"
    assert panel._fx_toggle_clip_btn.isEnabled()
    assert panel._fx_clear_clip_btn.isEnabled()
    panel.deleteLater()


def test_workbench_live2d_clip_surface_exposes_viewer_mapping_and_studio_actions():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.workbench_panel import WorkbenchPanel

    QApplication.instance() or QApplication([])
    panel = WorkbenchPanel()
    track = SimpleNamespace(label="Live2D")
    clip = SimpleNamespace(
        model_path="E:/models/avatar.model3.json",
        motion_group="Idle",
        duration_ms=4200,
        start_ms=1200,
        performance_source_path="E:/media/face_source.mp4",
        performance_source_subject_type="face_only",
    )

    seen = {"viewer": 0, "mapping": 0, "studio": 0}
    panel.open_live2d_editor_requested.connect(lambda: seen.__setitem__("viewer", seen["viewer"] + 1))
    panel.apply_live2d_performance_source_requested.connect(lambda: seen.__setitem__("mapping", seen["mapping"] + 1))
    panel.open_vtuber_studio_requested.connect(lambda: seen.__setitem__("studio", seen["studio"] + 1))

    panel.set_live2d_clip(track, clip)

    assert panel.current_target() == ("live2d", track, clip)
    assert not panel._live2d_mapping_host.isHidden()
    assert "Mapped source: face_source.mp4" in panel._live2d_mapping_body.text()
    assert "subject: face_only" in panel._live2d_mapping_body.text()

    panel._live2d_open_editor_btn.click()
    panel._live2d_apply_perf_btn.click()
    panel._live2d_studio_btn.click()

    assert seen == {"viewer": 1, "mapping": 1, "studio": 1}
    panel.deleteLater()


def test_vtuber_studio_reports_vrm_target_without_live2d_exclusivity():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import VTuberBroadcastStudioWindow

    QApplication.instance() or QApplication([])

    class _Player:
        def position(self):
            return 0

    class _Editor:
        _player = _Player()
        _tracks = []
        _project_settings = {"vseeface_bridge": {"avatar_vrm": "E:/avatars/Milica.vrm"}}

        def _selected_live2d_clip_for_mapping(self):
            return None

    win = VTuberBroadcastStudioWindow()
    win.update_from_editor(_Editor())

    assert win._target_combo.count() == 1
    assert win._target_combo.currentData() == "vrm:vseeface_bridge"
    assert "pose stream" in win._target_status.text()
    assert "VRM / VSeeFace bridge" in win._mapping_body.text()
    assert "Milica.vrm" in win._mapping_body.text()
    assert "Pose stream:" in win._mapping_body.text()
    assert "VRM/VSeeFace targets" in win._map_btn.toolTip()
    assert not win._map_btn.isEnabled()
    win.deleteLater()


def test_vtuber_studio_shows_visual_preview_paths(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import VTuberBroadcastStudioWindow

    QApplication.instance() or QApplication([])
    program = tmp_path / "program.png"
    source = tmp_path / "source.png"
    avatar = tmp_path / "avatar.png"
    for path, color in (
        (program, QColor("#285F3D")),
        (source, QColor("#5A6EA8")),
        (avatar, QColor("#7A5A8B")),
    ):
        image = QImage(64, 36, QImage.Format.Format_RGB32)
        image.fill(color)
        assert image.save(str(path))

    class _Player:
        def position(self):
            return 0

    class _Editor:
        _player = _Player()
        _tracks = []
        _project_settings = {
            "vseeface_bridge": {"avatar_vrm": "E:/avatars/Milica.vrm"},
            "vtuber_studio": {
                "preview": {
                    "program_preview_image": str(program),
                    "source_preview_image": str(source),
                    "avatar_preview_image": str(avatar),
                }
            },
        }

        def _selected_live2d_clip_for_mapping(self):
            return None

    win = VTuberBroadcastStudioWindow()
    win.update_from_editor(_Editor())

    assert win._program_preview.pixmap() is not None
    assert not win._program_preview.pixmap().isNull()
    assert win._source_preview.pixmap() is not None
    assert not win._source_preview.pixmap().isNull()
    assert win._mapping_preview.pixmap() is not None
    assert not win._mapping_preview.pixmap().isNull()
    win.deleteLater()


def test_broadcast_frame_feeds_open_vtuber_studio_without_session():
    import numpy as np

    from app.video_editor_broadcast_workflow import _feed_broadcast_output_frame

    class _Studio:
        def __init__(self):
            self.frame = None

        def update_program_output_frame(self, frame):
            self.frame = frame

    studio = _Studio()
    owner = SimpleNamespace(_vtuber_studio_window=studio, _broadcast_output_session=None)
    frame = np.zeros((9, 16, 3), dtype=np.uint8)
    frame[:, :] = [10, 80, 120]

    _feed_broadcast_output_frame(owner, frame)

    assert owner._latest_program_output_rgb is frame
    assert studio.frame is frame


def test_vtuber_studio_avatar_target_selector_keeps_single_window_for_vrm_and_live2d():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.video_editor_window import VTuberBroadcastStudioWindow

    QApplication.instance() or QApplication([])

    class _Player:
        def position(self):
            return 0

    live_clip = SimpleNamespace(model_path="E:/models/live.model3.json", start_ms=0, duration_ms=1000)
    live_track = SimpleNamespace(label="Live2D", clips=[live_clip])

    class _Editor:
        _player = _Player()
        _tracks = []
        _live2d_actor_tracks = [live_track]
        _project_settings = {
            "vseeface_bridge": {"avatar_vrm": "E:/avatars/Milica.vrm"},
            "vtuber_studio": {"avatar_target_id": "vrm:vseeface_bridge"},
        }

        def _selected_live2d_clip_for_mapping(self):
            return live_clip

        def _register_change(self, _label):
            pass

    win = VTuberBroadcastStudioWindow()
    editor = _Editor()
    win.update_from_editor(editor)

    labels = [win._target_combo.itemText(i) for i in range(win._target_combo.count())]
    assert any("VRM / VSeeFace Bridge" in label for label in labels)
    assert any("Live2D" in label for label in labels)
    assert win._target_combo.currentData() == "vrm:vseeface_bridge"
    assert "VRM / VSeeFace bridge" in win._mapping_body.text()

    live_index = win._target_combo.findData("live2d:0:0")
    win._target_combo.setCurrentIndex(live_index)

    assert editor._project_settings["vtuber_studio"]["avatar_target_id"] == "live2d:0:0"
    assert "Type: Live2D actor clip" in win._mapping_body.text()
    assert win._map_btn.isEnabled()
    win.deleteLater()


def test_vtuber_studio_registers_redacted_broadcast_evidence_payload(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.broadcast_platform_e2e import build_broadcast_platform_e2e_report
    from app.video_editor_window import VTuberBroadcastStudioWindow

    QApplication.instance() or QApplication([])
    report = build_broadcast_platform_e2e_report(
        tmp_path,
        record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
        live2d_record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
    )
    artifact = tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json"
    artifact.parent.mkdir()
    artifact.write_text(json.dumps(report), encoding="utf-8")

    win = VTuberBroadcastStudioWindow()
    result = win._register_broadcast_evidence_payload(
        {
            "root": str(tmp_path),
            "check_id": "youtube_unlisted_viewer_playback",
            "platform": "YouTube",
            "notes": "Private YouTube preview played Program Output; stream key, URL, account and chat redacted.",
            "confirm_redacted": True,
        }
    )
    updated = json.loads(artifact.read_text(encoding="utf-8"))
    checks = {row["id"]: row for row in updated["checks"]}

    assert hasattr(win, "_evidence_register_rtmp_btn")
    assert hasattr(win, "_evidence_register_youtube_view_btn")
    assert hasattr(win, "_evidence_guide_btn")
    assert hasattr(win, "_evidence_youtube_studio_btn")
    assert result["registered"] is True
    assert checks["youtube_unlisted_viewer_playback"]["kind"] == "real_platform"
    assert checks["youtube_unlisted_viewer_playback"]["ok"] is True
    assert checks["youtube_unlisted_viewer_playback"]["evidence"]["redacted"] is True
    win.deleteLater()


def test_workbench_fx_summary_bridges_vfx_node_graph_payload():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QPushButton

    from app.post_pipeline_workflow import build_mini_vfx_node_graph, build_vfx_repair_plan
    from app.workbench_panel import (
        WorkbenchPanel,
        vfx_node_graph_detail_text_for_track,
        vfx_node_graph_overview_for_track,
    )

    QApplication.instance() or QApplication([])
    panel = WorkbenchPanel()
    plan = build_vfx_repair_plan([
        {"x": 0.2, "y": 0.2, "feather": 0.04},
        {"x": 0.8, "y": 0.2, "feather": 0.04},
        {"x": 0.8, "y": 0.7, "feather": 0.08},
    ])
    graph = build_mini_vfx_node_graph(plan, include_keyer=True).to_dict()
    node = SimpleNamespace(vfx_node_graph=graph)
    track = SimpleNamespace(
        id=1,
        source_path="clip.mp4",
        duration_ms=1000,
        offset_ms=0,
        speed_segments=[],
        fades=[],
        typography_actors=[],
        zoom_actors=[],
        node_item_chain=[(node, [])],
    )

    panel.set_video_track(track)

    payload = panel.vfx_node_graph_qa_payload()
    assert payload["ok"] is True
    assert payload["graph_count"] == 1
    assert "VFX graph: OK" in panel._fx_summary_body.text()
    assert "chroma_key" in panel.vfx_node_graph_summary_text()
    overview = vfx_node_graph_overview_for_track(track)
    assert [row["label"] for row in overview[:4]] == ["Media", "Keyer", "Roto", "Clean"]
    assert not panel._vfx_graph_strip_host.isHidden()
    assert panel._fx_vfx_graph_btn.isEnabled()
    assert not panel._fx_vfx_graph_btn.isHidden()
    detail_text = vfx_node_graph_detail_text_for_track(track)
    assert "VFX Graph" in detail_text
    assert "QA Gates:" in detail_text
    assert "- keyer: chroma_key <- media_in" in detail_text
    visible_labels = [
        button.text()
        for button in panel._vfx_graph_strip_host.findChildren(QPushButton)
        if button.property("VfxGraphNode") == "true"
    ]
    assert {"Media", "Keyer", "Clean", "Out"} <= set(visible_labels)
    assert all(
        button.cursor().shape() == Qt.CursorShape.PointingHandCursor
        for button in panel._vfx_graph_strip_host.findChildren(QPushButton)
        if button.property("VfxGraphNode") == "true"
    )
    panel.deleteLater()


def test_clear_selected_clip_fx_and_transition_register_undo():
    from app.video_editor_window import VideoEditorWindow

    calls: list[tuple[str, object]] = []
    clip = SimpleNamespace(
        video_filters=object(),
        chroma_key={"enabled": True},
        bg_removal=object(),
        transition_out_type="wipe_left",
        transition_out_ms=400,
    )
    track = SimpleNamespace(id=7)
    editor = SimpleNamespace(
        _selected_video_clip=lambda: (track, clip),
        _workflow_target_video_clip=lambda: (track, clip),
        _track_rows={7: SimpleNamespace(update=lambda: calls.append(("row", 7)))},
        _refresh_player_tracks=lambda: calls.append(("player", None)),
        _refresh_preview_soft=lambda tr=None: calls.append(("preview", getattr(tr, "id", None))),
        _refresh_workbench=lambda: calls.append(("workbench", None)),
        _register_change=lambda label: calls.append(("undo", label)),
        _flash_status=lambda msg: calls.append(("status", msg)),
    )

    VideoEditorWindow._clear_selected_clip_fx(editor)

    assert clip.video_filters is None
    assert clip.chroma_key is None
    assert clip.bg_removal is None
    assert ("undo", "clear clip FX") in calls

    VideoEditorWindow._clear_selected_clip_transition(editor)

    assert clip.transition_out_type == ""
    assert clip.transition_out_ms == 0
    assert ("undo", "clear clip transition") in calls


def test_clip_badge_menu_model_and_commands_manage_fx_and_transition():
    from app.video_editor_window import VideoEditorWindow

    calls: list[tuple[str, object]] = []
    clip = SimpleNamespace(
        id=9,
        video_filters={"enabled": True, "sharpen": 0.4},
        chroma_key=None,
        bg_removal=None,
        disabled_video_filters=None,
        disabled_chroma_key=None,
        disabled_bg_removal=None,
        transition_out_type="dissolve",
        transition_out_ms=300,
        transition_preset_meta={"id": "transition-demo"},
    )
    track = SimpleNamespace(id=4)
    editor = SimpleNamespace(
        _track_rows={4: SimpleNamespace(update=lambda: calls.append(("row", 4)))},
        _refresh_player_tracks=lambda: calls.append(("player", None)),
        _refresh_preview_soft=lambda tr=None: calls.append(("preview", getattr(tr, "id", None))),
        _refresh_workbench=lambda: calls.append(("workbench", None)),
        _register_change=lambda label: calls.append(("undo", label)),
        _flash_status=lambda msg: calls.append(("status", msg)),
        _on_clip_badge_action_requested=lambda tid, cid, action: calls.append(("focus", action)),
    )
    editor._clip_has_active_fx = MethodType(VideoEditorWindow._clip_has_active_fx, editor)
    editor._clip_has_disabled_fx = MethodType(VideoEditorWindow._clip_has_disabled_fx, editor)
    editor._set_clip_fx_enabled = MethodType(VideoEditorWindow._set_clip_fx_enabled, editor)
    editor._clear_clip_fx = MethodType(VideoEditorWindow._clear_clip_fx, editor)
    editor._clear_clip_transition = MethodType(VideoEditorWindow._clear_clip_transition, editor)
    editor._clip_badge_menu_model = MethodType(VideoEditorWindow._clip_badge_menu_model, editor)
    editor._run_clip_badge_menu_action = MethodType(VideoEditorWindow._run_clip_badge_menu_action, editor)

    fx_rows = editor._clip_badge_menu_model(clip, "fx")
    assert [row["id"] for row in fx_rows] == ["focus", "toggle_fx", "clear_fx"]
    assert fx_rows[1]["label"] == "Disable FX"

    assert editor._run_clip_badge_menu_action(track, clip, "fx", "toggle_fx") is True
    assert clip.video_filters is None
    assert clip.disabled_video_filters == {"enabled": True, "sharpen": 0.4}

    fx_rows = editor._clip_badge_menu_model(clip, "fx")
    assert fx_rows[1]["label"] == "Enable FX"

    assert editor._run_clip_badge_menu_action(track, clip, "fx", "clear_fx") is True
    assert clip.disabled_video_filters is None
    assert ("undo", "clear clip FX") in calls

    tr_rows = editor._clip_badge_menu_model(clip, "transition")
    assert [row["id"] for row in tr_rows] == ["focus", "clear_transition"]
    assert editor._run_clip_badge_menu_action(track, clip, "transition", "clear_transition") is True
    assert clip.transition_out_type == ""
    assert ("undo", "clear clip transition") in calls


def test_toggle_clip_fx_enabled_preserves_and_restores_stack():
    from app.video_editor_window import VideoEditorWindow

    calls: list[tuple[str, object]] = []
    clip = SimpleNamespace(
        video_filters={"enabled": True, "sharpen": True},
        chroma_key=None,
        bg_removal=None,
        disabled_video_filters=None,
        disabled_chroma_key=None,
        disabled_bg_removal=None,
    )
    track = SimpleNamespace(id=3)
    editor = SimpleNamespace(
        _track_rows={3: SimpleNamespace(update=lambda: calls.append(("row", 3)))},
        _refresh_player_tracks=lambda: calls.append(("player", None)),
        _refresh_preview_soft=lambda tr=None: calls.append(("preview", getattr(tr, "id", None))),
        _refresh_workbench=lambda: calls.append(("workbench", None)),
        _register_change=lambda label: calls.append(("undo", label)),
        _flash_status=lambda msg: calls.append(("status", msg)),
    )

    assert VideoEditorWindow._set_clip_fx_enabled(editor, track, clip, False)
    assert clip.video_filters is None
    assert clip.disabled_video_filters == {"enabled": True, "sharpen": True}
    assert ("undo", "disable clip FX") in calls

    assert VideoEditorWindow._set_clip_fx_enabled(editor, track, clip, True)
    assert clip.video_filters == {"enabled": True, "sharpen": True}
    assert clip.disabled_video_filters is None
    assert ("undo", "enable clip FX") in calls


def test_project_io_persists_disabled_clip_fx_stack():
    from app.project_io import _video_clip_from_dict, _video_clip_to_dict
    from app.timeline_model import VideoClip
    from app.video_filters import VideoFilterParams

    clip = VideoClip(id=9, source_duration_ms=1000, timeline_in_ms=0)
    clip.disabled_video_filters = VideoFilterParams(sharpen=1.25)
    clip.cursor_events = [{"t_ms": 120, "x_norm": 0.3, "y_norm": 0.4, "kind": "click"}]
    clip.screenstudio_polish = {
        "source": "screenstudio_auto_polish",
        "auto_zoom_actor_ids": [4],
    }

    data = _video_clip_to_dict(clip)
    restored = _video_clip_from_dict(data, None)

    assert data["disabled_video_filters"]["sharpen"] == 1.25
    assert restored.video_filters is None
    assert restored.disabled_video_filters is not None
    assert restored.disabled_video_filters.sharpen == 1.25
    assert restored.cursor_events[0]["kind"] == "click"
    assert restored.screenstudio_polish["auto_zoom_actor_ids"] == [4]


def test_screenstudio_polish_forces_export_prerender(tmp_path):
    from app.timeline_model import VideoClip
    from app.video_exporter import VideoExportThread

    clip = VideoClip(id=12, source_duration_ms=1000, timeline_in_ms=0)
    clip.cursor_events = [{"t_ms": 120, "x_norm": 0.3, "y_norm": 0.4, "kind": "click"}]

    assert VideoExportThread._clip_effects_need_prerender([clip])

    exporter = VideoExportThread(
        tmp_path / "in.mp4",
        tmp_path / "out.mp4",
        [(0, 1000, 1.0)],
        project_settings={"screenstudio_polish": {"screen": {"padding_px": 48}}},
    )
    assert exporter._screenstudio_fx_need_prerender()

    track_exporter = VideoExportThread(
        tmp_path / "in.mp4",
        tmp_path / "out.mp4",
        [(0, 1000, 1.0)],
        render_clip_tracks=[[clip]],
    )
    assert track_exporter._screenstudio_fx_need_prerender()


def test_spine_clip_double_click_uses_deferred_timeline_load(monkeypatch):
    from app.video_editor_window import VideoEditorWindow

    created = []

    class _Destroyed:
        def connect(self, _cb):
            pass

    class FakeSpineEditor:
        def __init__(self, parent=None, *, autoload_sample=True):
            self.autoload_sample = autoload_sample
            self.destroyed = _Destroyed()
            self.calls = []
            created.append(self)

        def set_target_clip(self, clip, lane_row):
            self.calls.append(("target", clip, lane_row))

        def show(self):
            self.calls.append(("show",))

        def raise_(self):
            self.calls.append(("raise",))

        def activateWindow(self):
            self.calls.append(("activate",))

        def load_character_deferred(self, path, delay_ms=120):
            self.calls.append(("deferred", path, delay_ms))

        def _load_character(self, path):
            raise AssertionError(f"Spine clip open should defer model loading: {path}")

    monkeypatch.setattr(
        "app.spine_editor.editor_window.SpineEditorWindow",
        FakeSpineEditor,
    )
    clip = SimpleNamespace(skel_path="hero.json", start_ms=100, end_ms=200)
    lane_row = SimpleNamespace(track=SimpleNamespace(clips=[clip]))
    editor = SimpleNamespace(
        _spine_editor=None,
        _actor_lane_rows=[lane_row],
        _record_editor_action=lambda *args, **kwargs: None,
    )

    VideoEditorWindow._on_spine_clip_dclick(editor, clip)

    fake = created[0]
    assert fake.autoload_sample is False
    assert ("target", clip, lane_row) in fake.calls
    assert fake.calls[-1] == ("deferred", "hero.json", 120)


def test_actor_loading_ux_qa_script_smoke():
    from tools.qa_actor_loading_ux import run_actor_loading_ux_qa

    report = run_actor_loading_ux_qa()

    assert report["ok"] is True
    assert report["issues"] == []


def test_actor_loading_cache_records_staged_progress(tmp_path):
    from app.actor_loading_cache import actor_loading_cache_report, clear_actor_loading_cache, record_actor_load

    cache_path = tmp_path / "actor_loading_cache.json"
    clear_actor_loading_cache(cache_path)
    row = record_actor_load(
        "live2d",
        str(tmp_path / "hero.model3.json"),
        status="loading",
        stage="first_frame",
        message="rendering",
        elapsed_ms=123,
        cache_path=cache_path,
    )
    report = actor_loading_cache_report(cache_path)

    assert row["progress"] == 90
    assert report["summary"]["entries"] == 1
    assert report["summary"]["status_counts"]["loading"] == 1


def test_actor_compat_repair_resolves_spine_atlas_to_json(tmp_path):
    from app.actor_compat_repair import repair_actor_model_path

    skel = tmp_path / "hero.json"
    skel.write_text(
        json.dumps({
            "skeleton": {"spine": "4.1"},
            "bones": [{"name": "root"}],
            "slots": [],
            "skins": {},
            "animations": {},
        }),
        encoding="utf-8",
    )
    atlas = tmp_path / "hero.atlas"
    atlas.write_text("hero.png\nsize: 8,8\nformat: RGBA8888\n\nbody\n  xy: 0, 0\n  size: 8, 8\n", encoding="utf-8")
    (tmp_path / "hero.png").write_bytes(b"png")

    report = repair_actor_model_path("spine", str(atlas))

    assert report["path"] == str(skel)
    assert report["metadata"]["atlas_path"] == str(atlas)
    assert report["warnings"] == []


def test_actor_prerender_cache_report_reads_manifests(tmp_path):
    from app.actor_prerender_cache import actor_prerender_cache_report

    folder = tmp_path / "cache" / "abc"
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(
        json.dumps({"status": "pass", "frame_count": 3}),
        encoding="utf-8",
    )

    report = actor_prerender_cache_report(tmp_path / "cache")

    assert report["summary"]["entries"] == 1
    assert report["summary"]["frames"] == 3


def test_cached_actor_preview_frame_reads_exact_manifest(monkeypatch, tmp_path):
    from PIL import Image

    import app.actor_prerender_cache as cache

    root = tmp_path / "cache"
    folder = root / "abc"
    folder.mkdir(parents=True)
    frame = folder / "frame_0000.png"
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(frame)
    (folder / "manifest.json").write_text(
        json.dumps({
            "status": "pass",
            "kind": "spine",
            "source_path": str(tmp_path / "hero.json"),
            "load_path": str(tmp_path / "hero.json"),
            "width": 16,
            "height": 16,
            "duration_ms": 1000,
            "frame_count": 1,
            "frames": [{"pos_ms": 0, "path": str(frame), "nonblank": True}],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(cache, "actor_prerender_root", lambda: root)

    img = cache.cached_actor_preview_frame(
        "spine",
        str(tmp_path / "hero.json"),
        width=16,
        height=16,
        local_ms=0,
        duration_ms=1000,
    )

    assert img is not None
    assert img.size == (16, 16)


def test_actor_known_failure_quarantine_writer(tmp_path):
    from app.actor_known_failures import add_actor_known_failure

    out = tmp_path / "known.json"
    row = add_actor_known_failure(
        kind="spine",
        path="resources/spine_samples/hero.json",
        known_failure_path=out,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert row["kind"] == "spine"
    assert payload["known_failures"][0]["path_suffix"].endswith("hero.json")


def test_actor_loading_manager_exposes_probe_and_prerender_buttons():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.actor_loading_manager import ActorLoadingManagerDialog

    QApplication.instance() or QApplication([])
    dlg = ActorLoadingManagerDialog()
    try:
        assert hasattr(dlg, "_probe_btn")
        assert hasattr(dlg, "_prerender_btn")
        assert hasattr(dlg, "_overnight_plan_btn")
        assert hasattr(dlg, "_overnight_render_btn")
    finally:
        dlg.close()
        dlg.deleteLater()


def test_screenstudio_animated_icon_presets_are_registered():
    from app.preset_library import preset_by_id, presets_by_tags

    assert preset_by_id("sticker-cursor-scissor-snip") is not None
    assert preset_by_id("template-screenstudio-blade-explain") is not None
    assert any(p.id == "template-wallpaper-palette-switch" for p in presets_by_tags(["screen-studio", "wallpaper"]))


def test_actor_isolated_probe_reports_invalid_spine_without_crashing(tmp_path):
    from tools.actor_isolated_probe import run_probe

    missing = tmp_path / "missing.json"

    report = run_probe("spine", str(missing), width=64, height=64)

    assert report["status"] in {"fail", "crash", "render_none", "unsupported"}
    assert report["kind"] == "spine"


def test_actor_overnight_qa_plans_from_manifest(tmp_path):
    from tools.qa_actor_overnight import run_actor_overnight_qa

    manifest = tmp_path / "manifest.json"
    status = tmp_path / "status.json"
    manifest.write_text(
        json.dumps({"actors": [{"kind": "spine", "path": "hero.json"}]}),
        encoding="utf-8",
    )
    status.write_text(json.dumps({"entries": []}), encoding="utf-8")

    report = run_actor_overnight_qa(
        render=False,
        limit=10,
        manifest_path=manifest,
        status_path=status,
    )

    assert report["ok"]
    assert report["summary"]["planned_candidates"] == 1


def test_spine_actor_lane_hit_test_uses_visible_clip_width():
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    from app.spine_editor.actor_lane_row import SpineActorLaneRow
    from app.spine_editor.actor_track import SpineActorClip, SpineActorTrack
    from app.timeline_ruler import TimelineRuler

    QApplication.instance() or QApplication([])
    track = SpineActorTrack(id=1, label="Spine 1")
    clip = SpineActorClip(start_ms=1000, duration_ms=1)
    track.clips.append(clip)
    row = SpineActorLaneRow(track)
    try:
        row.set_px_per_sec(100)
        clicked = []
        row.clip_double_clicked.connect(clicked.append)

        x = row._ms_to_x(clip.start_ms) + 3
        event = QMouseEvent(
            QEvent.Type.MouseButtonDblClick,
            QPointF(float(x), 14.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        row.mouseDoubleClickEvent(event)

        assert row._ms_to_x(0) == TimelineRuler.MARGIN
        assert row._clip_at(x) is clip
        assert clicked == [clip]
    finally:
        row.close()


def test_actor_lane_playheads_align_with_timeline_ruler_margin():
    from PySide6.QtWidgets import QApplication

    from app.live2d.actor_lane_row import Live2DActorLaneRow
    from app.live2d.actor_track import Live2DActorTrack
    from app.spine_editor.actor_lane_row import SpineActorLaneRow
    from app.spine_editor.actor_track import SpineActorTrack
    from app.timeline_ruler import TimelineRuler

    QApplication.instance() or QApplication([])
    live_row = Live2DActorLaneRow(Live2DActorTrack(id=1, label="Live2D 1"))
    spine_row = SpineActorLaneRow(SpineActorTrack(id=1, label="Spine 1"))
    try:
        for row in (live_row, spine_row):
            row.set_px_per_sec(100)
            assert row._ms_to_x(0) == TimelineRuler.MARGIN
            assert row._ms_to_x(2500) == TimelineRuler.MARGIN + 250
            assert row._x_to_ms(TimelineRuler.MARGIN + 250) == 2500
    finally:
        live_row.close()
        spine_row.close()


def test_timeline_fuzzer_stays_valid_for_seeded_random_edits():
    from tools.qa_timeline_fuzzer import run_fuzzer

    report = run_fuzzer(iterations=160, seed=7)

    assert report["ok"] is True
    assert report["summary"]["iterations"] == 160
    assert report["failures"] == []


def test_actor_qa_status_detail_lines_include_broken_assets():
    from app.actor_qa_status import actor_status_detail_lines, actor_status_tooltip

    row = {
        "kind": "live2d",
        "status": "fail",
        "moc_missing": ["hero.moc3"],
        "motions_missing": ["idle.motion3.json"],
        "golden_status": "regressed",
        "recommendation": "Restore missing model dependencies.",
    }

    lines = actor_status_detail_lines(row)

    assert "Actor QA: fail" in lines
    assert "moc: hero.moc3" in lines
    assert "motions: idle.motion3.json" in lines
    assert "baseline: regressed" in lines
    assert "next: Restore missing model dependencies." in lines
    assert "hero.moc3" in actor_status_tooltip(row)


def test_preset_timeline_preview_and_interaction_models_are_ui_ready():
    from app.preset_feedback import (
        preset_preview_ab_model,
        preset_timeline_strip_rows,
        timeline_interaction_feedback_model,
    )
    from app.preset_library import EditorPreset

    preset = EditorPreset(id="effect-test-strip", kind="effect", name="Test Strip")
    strips = preset_timeline_strip_rows(
        preset,
        [{"kind": "effect", "status": "applied", "start_ms": 1200, "duration_ms": 1800}],
        clip_start_ms=1000,
        clip_end_ms=5000,
    )
    preview = preset_preview_ab_model(preset, before_signature="before", after_signature="after")
    feedback = timeline_interaction_feedback_model(
        "snap",
        snap_ms=1000,
        target_ms=2000,
        mode="trim",
        selected_count=1,
    )

    assert strips[0]["badge"] == "FX"
    assert strips[0]["visible"] is True
    assert strips[0]["start_ms"] == 1200
    assert preview["changed"] is True
    assert preview["split_mode"] == "wipe_ab"
    assert feedback["chip"] == "Snapped"
    assert "snap" in feedback["detail"]
