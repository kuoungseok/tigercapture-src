from __future__ import annotations

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


SRT_SAMPLE = """1
00:00:01,000 --> 00:00:03,000
Um today we explain materials.

2
00:00:04,000 --> 00:00:06,000
어 이제 base color를 연결합니다.
"""


class _Player:
    def position(self) -> int:
        return 1500


class _AutomationOwner:
    def __init__(self, *, locked: bool = False) -> None:
        from app.audio_tracks import AudioClip, AudioTrack
        from app.timeline_model import VideoClip, VideoTrack

        self._tracks = [
            VideoTrack(
                id=1,
                locked=locked,
                clips=[
                    VideoClip(
                        id=10,
                        source_duration_ms=10_000,
                        timeline_in_ms=0,
                        source_in_ms=0,
                        source_out_ms=10_000,
                    )
                ],
            )
        ]
        self._audio_tracks = [
            AudioTrack(
                id=2,
                clips=[AudioClip(id=20, duration_ms=10_000, offset_ms=0, trim_start_ms=0, trim_end_ms=10_000)],
            )
        ]
        self._timeline_markers = []
        self._selected_clips = [(1, 10)]
        self._project_settings = {"screenstudio_mode": True}
        self._player = _Player()
        self.subtitles: list[dict] = []
        self.preview_payloads: list[dict] = []
        self.stored_payloads: list[tuple[dict, dict]] = []
        self.changes: list[str] = []
        self.statuses: list[str] = []
        self.marker_sync_count = 0
        self.refresh_count = 0

    def _sync_markers_to_ruler(self) -> None:
        self.marker_sync_count += 1

    def _apply_ai_script_subtitles(self, rows) -> int:
        self.subtitles.extend(dict(row) for row in rows)
        return len(rows)

    def _apply_ai_script_markers(self, rows) -> int:
        self._timeline_markers.extend(dict(row) for row in rows)
        return len(rows)

    def _stage_ai_script_render_jobs(self, payload):
        return {"added": len(payload.get("render_queue_jobs") or []), "skipped": 0}

    def _apply_ai_script_auto_suggestions(self, payload) -> int:
        return len([row for row in payload.get("sidecars") or [] if row.get("type") == "add_auto_zoom"])

    def _sync_ai_script_preview_markers(self, payload) -> int:
        self.preview_payloads.append(dict(payload or {}))
        return len(payload.get("cut_intents") or []) + len(payload.get("short_candidates") or [])

    def _sync_ai_script_applied_cut_markers(self, result) -> int:
        self._timeline_markers.append({"ms": 0, "label": "applied", "result": dict(result or {})})
        return 1

    def _store_ai_script_edit_payload(self, payload, result=None) -> None:
        self.stored_payloads.append((dict(payload or {}), dict(result or {})))

    def _refresh_player_tracks(self) -> None:
        self.refresh_count += 1

    def _register_change(self, label: str = "") -> None:
        self.changes.append(label)

    def _flash_status(self, message: str) -> None:
        self.statuses.append(message)


def _clean_plan():
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel()
    model.import_transcript_text(SRT_SAMPLE, source_format="srt")
    model.set_silence_intervals([{"start_ms": 3000, "end_ms": 4200}])
    return model.generate_plan("clean_tutorial", style_preset_id="caption-tutorial-compact")


def test_automation_registry_exposes_safe_command_specs():
    from app.automation_commands import build_default_automation_registry

    registry = build_default_automation_registry(_AutomationOwner())
    specs = registry.specs()
    names = {row["name"] for row in specs}

    assert {
        "get_app_status",
        "get_ai_provider_status",
        "get_project_snapshot",
        "generate_edit_plan",
        "preview_generated_plan",
        "validate_edit_plan",
        "preview_edit_plan",
        "apply_edit_plan",
        "apply_reviewed_cuts",
        "add_marker",
    } <= names
    assert all("params_schema" in row for row in specs)
    assert next(row for row in specs if row["name"] == "apply_reviewed_cuts")["destructive"] is True


def test_automation_generates_edit_plan_from_transcript_and_project_subtitles():
    from app.automation_commands import build_default_automation_registry

    owner = _AutomationOwner()
    registry = build_default_automation_registry(owner)
    generated = registry.execute(
        "generate_edit_plan",
        {
            "transcript_text": SRT_SAMPLE,
            "source_format": "srt",
            "prompt": "튜토리얼을 보기 좋게 정리하고 자막도 만들어줘",
            "silence_intervals": [{"start_ms": 3000, "end_ms": 4200}],
        },
    ).to_dict()

    assert generated["ok"] is True
    assert generated["result"]["plan"]["provider"] == "rule_based"
    assert generated["result"]["preview"]["operation_counts"]["create_subtitles"] == 1
    assert generated["result"]["payload_counts"]["subtitle_rows"] == 2

    preview = registry.execute("preview_generated_plan", {"plan": generated["result"]["plan"]}).to_dict()
    assert preview["ok"] is True
    assert preview["result"]["plan_id"] == generated["result"]["plan"]["id"]

    owner.subtitles = [
        {"start_ms": 1000, "end_ms": 2000, "text": "hello"},
        {"start_ms": 2400, "end_ms": 3200, "text": "world"},
    ]
    from_project = registry.execute("generate_edit_plan", {"action": "transcript_to_captions"}).to_dict()
    assert from_project["ok"] is True
    assert from_project["result"]["transcript_source"] == "project_subtitles"
    assert len(from_project["result"]["document"]["segments"]) == 2


def test_automation_snapshot_and_read_only_queries():
    from app.automation_commands import build_default_automation_registry

    registry = build_default_automation_registry(_AutomationOwner())
    status = registry.execute("get_app_status").to_dict()
    providers = registry.execute("get_ai_provider_status").to_dict()
    snapshot = registry.execute("get_project_snapshot").to_dict()
    timeline = registry.execute("get_timeline_summary").to_dict()
    selected = registry.execute("get_selected_clip").to_dict()

    assert status["ok"] is True
    assert status["result"]["automation"]["arbitrary_python"] is False
    assert providers["result"]["automation_mcp"]["registered_commands_only"] is True
    assert snapshot["result"]["summary"]["video_clip_count"] == 1
    assert timeline["result"]["tracks"][0]["clip_count"] == 1
    assert selected["result"]["selected"]["id"] == 10


def test_automation_validates_previews_and_applies_safe_plan():
    from app.automation_commands import build_default_automation_registry

    owner = _AutomationOwner()
    registry = build_default_automation_registry(owner)
    plan = _clean_plan()

    validation = registry.execute("validate_edit_plan", {"plan": plan.to_dict()}).to_dict()
    preview_dry = registry.execute("preview_edit_plan", {"plan": plan.to_dict()}, dry_run=True).to_dict()
    assert preview_dry["dry_run"] is True
    assert owner.preview_payloads == []

    preview = registry.execute("preview_edit_plan", {"plan": plan.to_dict()}).to_dict()
    apply_dry = registry.execute("apply_edit_plan", {"plan": plan.to_dict()}, dry_run=True).to_dict()
    applied = registry.execute("apply_edit_plan", {"plan": plan.to_dict()}).to_dict()

    assert validation["ok"] is True
    assert "destructive_operations_are_review_only" in validation["warnings"]
    assert preview["ok"] is True
    assert preview["result"]["preview_markers"] >= 1
    assert apply_dry["result"]["applied"] == {}
    assert applied["ok"] is True
    assert applied["result"]["applied"]["subtitle_rows"] == 2
    assert len(owner.subtitles) == 2
    assert owner.stored_payloads
    assert owner.changes


def test_automation_reviewed_cuts_respect_locks_and_materialize_when_unlocked():
    from app.automation_commands import build_default_automation_registry

    plan = _clean_plan()
    locked = _AutomationOwner(locked=True)
    blocked = build_default_automation_registry(locked).execute("apply_reviewed_cuts", {"plan": plan.to_dict()}).to_dict()

    assert blocked["ok"] is False
    assert "locked_video_tracks:" in blocked["error"]

    owner = _AutomationOwner(locked=False)
    result = build_default_automation_registry(owner).execute("apply_reviewed_cuts", {"plan": plan.to_dict()}).to_dict()

    assert result["ok"] is True
    assert result["result"]["cut_materialize_result"]["removed_ms"] > 0
    assert owner._tracks[0].clips[-1].timeline_out_ms < 10_000
    assert owner.refresh_count == 1
    assert owner.changes


def test_automation_add_marker_supports_dry_run_and_apply():
    from app.automation_commands import build_default_automation_registry

    owner = _AutomationOwner()
    registry = build_default_automation_registry(owner)
    dry = registry.execute("add_marker", {"ms": 1234, "label": "Check"}, dry_run=True).to_dict()
    assert dry["dry_run"] is True
    assert owner._timeline_markers == []

    applied = registry.execute("add_marker", {"ms": 1234, "label": "Check"}).to_dict()
    assert applied["ok"] is True
    assert owner._timeline_markers[0]["label"] == "Check"
    assert owner.marker_sync_count == 1
