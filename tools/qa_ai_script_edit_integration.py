"""Deterministic QA for AI Script Edit panel and safe apply helpers."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


SRT_SAMPLE = """1
00:00:01,000 --> 00:00:03,000
Um today we explain materials.

2
00:00:04,000 --> 00:00:06,000
어 이제 base color를 연결합니다.
"""


class _QAAdapter:
    def __init__(self) -> None:
        self.subtitle_rows: list[dict[str, Any]] = []
        self.timeline_markers: list[dict[str, Any]] = []
        self.cut_intents: list[dict[str, Any]] = []
        self.render_queue_jobs: list[dict[str, Any]] = []
        self.sidecar: dict[str, Any] = {}

    def add_subtitle_rows(self, rows) -> int:
        self.subtitle_rows.extend(dict(row) for row in rows)
        return len(rows)

    def add_timeline_markers(self, rows) -> int:
        self.timeline_markers.extend(dict(row) for row in rows)
        return len(rows)

    def stage_cut_intents(self, rows) -> int:
        self.cut_intents.extend(dict(row) for row in rows)
        return len(rows)

    def stage_render_queue_jobs(self, rows) -> int:
        self.render_queue_jobs.extend(dict(row) for row in rows)
        return len(rows)

    def store_ai_script_sidecar(self, payload) -> None:
        self.sidecar = dict(payload or {})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def build_ai_script_edit_integration_report() -> dict[str, Any]:
    previous_provider = os.environ.get("TIGERCAPTURE_AI_PROVIDER")
    os.environ["TIGERCAPTURE_AI_PROVIDER"] = "rule_based"

    from PySide6.QtWidgets import QApplication

    from app.ai_edit_apply import (
        apply_ai_script_cut_intents_to_tracks,
        apply_ai_script_plan_to_adapter,
        build_ai_script_apply_payload,
    )
    from app.ai_action_log import append_ai_action_log
    from app.ai_plan_validation import validate_edit_plan_for_snapshot
    from app.ai_project_snapshot import build_project_snapshot_from_editor
    from app.ai_providers import provider_snapshot
    from app.ai_script_edit_panel import ScriptEditPanel, edit_plan_preview
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    app = QApplication.instance() or QApplication([])
    panel = ScriptEditPanel()
    panel._transcript_input.setPlainText(SRT_SAMPLE)
    document = panel.import_transcript_from_text()
    panel.set_silence_intervals([{"start_ms": 3000, "end_ms": 4200}])

    panel._prompt_input.setPlainText("군더더기 빼고 보기 좋은 자막까지 만들어줘")
    prompt_plan = panel.generate_from_prompt()
    caption_plan = panel.model.generate_plan("transcript_to_captions")
    caption_payload = build_ai_script_apply_payload(caption_plan)

    clean_plan = panel.model.generate_plan("clean_tutorial", style_preset_id="caption-tutorial-compact")
    panel.set_plan(clean_plan)
    clean_selected_ids = panel.selected_operation_ids()
    clean_payload = build_ai_script_apply_payload(clean_plan, operation_ids=clean_selected_ids)

    shorts_plan = panel.model.generate_plan("shorts")
    shorts_payload = build_ai_script_apply_payload(shorts_plan)

    adapter = _QAAdapter()
    adapter_result = apply_ai_script_plan_to_adapter(clean_plan, adapter, operation_ids=clean_selected_ids)
    video_track = VideoTrack(
        id=1,
        clips=[VideoClip(id=10, source_duration_ms=10_000, timeline_in_ms=0, source_in_ms=0, source_out_ms=10_000)],
    )
    audio_track = AudioTrack(
        id=2,
        clips=[AudioClip(id=20, duration_ms=10_000, offset_ms=0, trim_start_ms=0, trim_end_ms=10_000)],
    )
    materialized_cuts = apply_ai_script_cut_intents_to_tracks(
        [video_track],
        [audio_track],
        clean_payload.payload["cut_intents"],
    )
    class Player:
        def position(self):
            return 1500

    class Editor:
        pass

    editor = Editor()
    editor._tracks = [video_track]
    editor._audio_tracks = [audio_track]
    editor._timeline_markers = [{"ms": 1000, "label": "intro"}]
    editor._selected_clips = [(1, 10)]
    editor._player = Player()
    editor._project_settings = {"screenstudio_mode": True}
    snapshot = build_project_snapshot_from_editor(editor)
    validation = validate_edit_plan_for_snapshot(clean_plan, snapshot, operation_ids=clean_selected_ids)
    providers = provider_snapshot()
    audit_entry = append_ai_action_log(
        "qa_ai_script_edit_integration",
        {
            "plan_id": clean_plan.id,
            "snapshot_hash": snapshot.get("snapshot_hash"),
            "validation": validation.to_dict(),
        },
        log_path=ROOT / "debugCapture" / "ai_script_edit_integration_agent_log.jsonl",
    )

    checks = {
        "qt_app_available": app is not None,
        "transcript_import": len(document.segments) == 2 and document.segments[0].start_ms == 1000,
        "panel_generated_plan": prompt_plan.operations and prompt_plan.intent == "clean_tutorial",
        "prompt_rule_mode": prompt_plan.metadata.get("prompt_mode") == "local_rule_based"
        and prompt_plan.metadata.get("local_llm_required") is False,
        "selection_exposes_operation_ids": bool(clean_selected_ids)
        and set(clean_selected_ids) <= {operation.id for operation in clean_plan.operations},
        "subtitle_payload": bool(clean_payload.payload["subtitle_rows"]),
        "review_cut_intents": bool(clean_payload.payload["cut_intents"])
        and all(row.get("requires_review") is True for row in clean_payload.payload["cut_intents"]),
        "short_candidate_payload": bool(shorts_payload.payload["short_candidates"])
        and bool(shorts_payload.payload["timeline_markers"]),
        "render_job_sidecar": bool(shorts_payload.payload["render_queue_jobs"]),
        "adapter_safe_apply": adapter_result.applied["subtitle_rows"] == len(adapter.subtitle_rows)
        and adapter_result.applied["cut_intents"] == len(adapter.cut_intents)
        and bool(adapter.sidecar),
        "review_cut_materialize": materialized_cuts.get("ok") is True
        and int(materialized_cuts.get("removed_ms", 0) or 0) > 0
        and video_track.clips[-1].timeline_out_ms < 10_000
        and audio_track.clips[-1].offset_ms + audio_track.clips[-1].effective_length_ms < 10_000,
        "schema_v1_provider": clean_plan.to_dict().get("schema_version") == 1
        and clean_plan.to_dict().get("provider") == "rule_based",
        "provider_registry": providers.get("cloud_required") is False
        and set(providers.get("providers") or {}) >= {"rule_based", "local_llm", "codex_mcp", "claude_mcp", "manual_json"},
        "snapshot_builder": snapshot.get("schema_version") == 1
        and bool(snapshot.get("snapshot_hash"))
        and int((snapshot.get("summary") or {}).get("video_clip_count", 0) or 0) >= 1,
        "plan_validation": validation.ok is True
        and validation.dry_run.get("payload_counts", {}).get("subtitle_rows", 0) >= 1,
        "audit_log": audit_entry.get("action") == "qa_ai_script_edit_integration"
        and audit_entry.get("payload", {}).get("plan_id") == clean_plan.id,
    }
    failures = [name for name, passed in checks.items() if not passed]
    score = int(round(100 * (len(checks) - len(failures)) / max(1, len(checks))))
    report = {
        "ok": not failures,
        "score": score,
        "checks": checks,
        "failures": failures,
        "summary": {
            "transcript_segments": len(document.segments),
            "prompt_operations": len(prompt_plan.operations),
            "caption_operations": len(caption_plan.operations),
            "clean_operations": len(clean_plan.operations),
            "selected_operations": len(clean_selected_ids),
            "subtitle_rows": len(clean_payload.payload["subtitle_rows"]),
            "timeline_markers": len(shorts_payload.payload["timeline_markers"]),
            "short_candidates": len(shorts_payload.payload["short_candidates"]),
            "review_cut_intents": len(clean_payload.payload["cut_intents"]),
            "render_queue_jobs": len(shorts_payload.payload["render_queue_jobs"]),
            "warnings": len(clean_payload.warnings) + len(shorts_payload.warnings),
            "materialized_cut_ranges": len(materialized_cuts.get("applied_ranges") or []),
            "materialized_removed_ms": int(materialized_cuts.get("removed_ms", 0) or 0),
            "provider_count": len(providers.get("providers") or {}),
            "snapshot_hash": snapshot.get("snapshot_hash"),
        },
        "transcript": document.to_dict(),
        "plans": {
            "prompt": prompt_plan.to_dict(),
            "captions": caption_plan.to_dict(),
            "clean_tutorial": clean_plan.to_dict(),
            "shorts": shorts_plan.to_dict(),
        },
        "previews": {
            "clean_tutorial": edit_plan_preview(clean_plan),
            "shorts": edit_plan_preview(shorts_plan),
        },
        "payloads": {
            "captions": caption_payload.to_dict(),
            "clean_tutorial": clean_payload.to_dict(),
            "shorts": shorts_payload.to_dict(),
        },
        "adapter_result": adapter_result.to_dict(),
        "materialized_cuts": materialized_cuts,
        "provider_snapshot": providers,
        "project_snapshot": snapshot,
        "validation": validation.to_dict(),
        "audit_entry": audit_entry,
    }
    if previous_provider is None:
        os.environ.pop("TIGERCAPTURE_AI_PROVIDER", None)
    else:
        os.environ["TIGERCAPTURE_AI_PROVIDER"] = previous_provider
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build AI Script Edit integration QA report.")
    parser.add_argument("--out", default="debugCapture/ai_script_edit_integration_qa.json")
    args = parser.parse_args()

    report = build_ai_script_edit_integration_report()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
