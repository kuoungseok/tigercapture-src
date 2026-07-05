"""QA report for the safe automation command registry."""
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


class _Player:
    def position(self) -> int:
        return 1000


class _Owner:
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
        self._timeline_markers: list[dict[str, Any]] = []
        self._selected_clips = [(1, 10)]
        self._project_settings = {"screenstudio_mode": True}
        self._player = _Player()
        self.subtitles: list[dict[str, Any]] = []
        self.preview_count = 0
        self.change_count = 0
        self.refresh_count = 0

    def _apply_ai_script_subtitles(self, rows) -> int:
        self.subtitles.extend(dict(row) for row in rows)
        return len(rows)

    def _apply_ai_script_markers(self, rows) -> int:
        self._timeline_markers.extend(dict(row) for row in rows)
        return len(rows)

    def _apply_ai_script_auto_suggestions(self, payload) -> int:
        return len([row for row in payload.get("sidecars") or [] if row.get("type") == "add_auto_zoom"])

    def _stage_ai_script_render_jobs(self, payload) -> dict[str, int]:
        return {"added": len(payload.get("render_queue_jobs") or []), "skipped": 0}

    def _sync_ai_script_preview_markers(self, payload) -> int:
        count = len(payload.get("cut_intents") or []) + len(payload.get("short_candidates") or [])
        self.preview_count += count
        return count

    def _sync_ai_script_applied_cut_markers(self, result) -> int:
        self._timeline_markers.append({"ms": 0, "label": "applied cut"})
        return 1

    def _store_ai_script_edit_payload(self, payload, result=None) -> None:
        self._last_ai_payload = dict(payload or {})
        self._last_ai_result = dict(result or {})

    def _sync_markers_to_ruler(self) -> None:
        pass

    def _refresh_player_tracks(self) -> None:
        self.refresh_count += 1

    def _register_change(self, label: str = "") -> None:
        self.change_count += 1

    def _flash_status(self, message: str) -> None:
        self._last_status = str(message)


def _plan():
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel()
    model.import_transcript_text(SRT_SAMPLE, source_format="srt")
    model.set_silence_intervals([{"start_ms": 3000, "end_ms": 4200}])
    return model.generate_plan("clean_tutorial", style_preset_id="caption-tutorial-compact")


def build_automation_commands_report() -> dict[str, Any]:
    from app.automation_commands import build_default_automation_registry

    plan = _plan()
    owner = _Owner()
    registry = build_default_automation_registry(owner)
    specs = registry.specs()
    status = registry.execute("get_app_status").to_dict()
    providers = registry.execute("get_ai_provider_status").to_dict()
    snapshot = registry.execute("get_project_snapshot").to_dict()
    selected = registry.execute("get_selected_clip").to_dict()
    generated = registry.execute(
        "generate_edit_plan",
        {
            "transcript_text": SRT_SAMPLE,
            "source_format": "srt",
            "prompt": "튜토리얼을 보기 좋게 정리하고 자막도 만들어줘",
            "silence_intervals": [{"start_ms": 3000, "end_ms": 4200}],
        },
    ).to_dict()
    generated_preview = registry.execute(
        "preview_generated_plan",
        {"plan": generated.get("result", {}).get("plan", {})},
    ).to_dict()
    validation = registry.execute("validate_edit_plan", {"plan": plan.to_dict()}).to_dict()
    preview = registry.execute("preview_edit_plan", {"plan": plan.to_dict()}).to_dict()
    apply_dry = registry.execute("apply_edit_plan", {"plan": plan.to_dict()}, dry_run=True).to_dict()
    apply_safe = registry.execute("apply_edit_plan", {"plan": plan.to_dict()}).to_dict()
    cut_owner = _Owner()
    cut_result = build_default_automation_registry(cut_owner).execute("apply_reviewed_cuts", {"plan": plan.to_dict()}).to_dict()
    locked_result = build_default_automation_registry(_Owner(locked=True)).execute(
        "apply_reviewed_cuts",
        {"plan": plan.to_dict()},
    ).to_dict()
    marker = registry.execute("add_marker", {"ms": 1500, "label": "QA marker"}).to_dict()

    command_names = {row.get("name") for row in specs}
    checks = {
        "has_required_commands": {
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
        }
        <= command_names,
        "status_is_safe": status.get("ok") is True
        and status.get("result", {}).get("automation", {}).get("arbitrary_python") is False,
        "snapshot_has_timeline": snapshot.get("result", {}).get("summary", {}).get("video_clip_count") == 1,
        "selected_clip": selected.get("result", {}).get("selected", {}).get("id") == 10,
        "provider_status": providers.get("result", {}).get("automation_mcp", {}).get("registered_commands_only") is True,
        "generate_plan": generated.get("ok") is True
        and generated.get("result", {}).get("plan", {}).get("provider") == "rule_based"
        and generated.get("result", {}).get("payload_counts", {}).get("subtitle_rows") == 2,
        "preview_generated_plan": generated_preview.get("ok") is True
        and generated_preview.get("result", {}).get("plan_id") == generated.get("result", {}).get("plan", {}).get("id"),
        "validation_ok": validation.get("ok") is True,
        "preview_markers": preview.get("result", {}).get("preview_markers", 0) >= 1,
        "dry_run_no_apply": apply_dry.get("dry_run") is True and apply_dry.get("result", {}).get("applied") == {},
        "safe_apply": apply_safe.get("result", {}).get("applied", {}).get("subtitle_rows") == 2,
        "cut_apply": cut_result.get("ok") is True
        and cut_result.get("result", {}).get("cut_materialize_result", {}).get("removed_ms", 0) > 0,
        "locked_cut_blocked": locked_result.get("ok") is False and "locked_video_tracks:" in locked_result.get("error", ""),
        "marker_apply": marker.get("ok") is True and marker.get("result", {}).get("marker", {}).get("label") == "QA marker",
    }
    failures = [name for name, ok in checks.items() if not ok]
    return {
        "ok": not failures,
        "score": int(round(100 * (len(checks) - len(failures)) / max(1, len(checks)))),
        "checks": checks,
        "failures": failures,
        "summary": {
            "command_count": len(specs),
            "generated_operations": len(generated.get("result", {}).get("plan", {}).get("operations", []) or []),
            "preview_markers": preview.get("result", {}).get("preview_markers", 0),
            "safe_subtitles": len(owner.subtitles),
            "cut_removed_ms": cut_result.get("result", {}).get("cut_materialize_result", {}).get("removed_ms", 0),
        },
        "specs": specs,
        "status": status,
        "providers": providers,
        "snapshot": snapshot.get("result"),
        "generated": generated,
        "generated_preview": generated_preview,
        "validation": validation,
        "preview": preview,
        "safe_apply": apply_safe,
        "cut_apply": cut_result,
        "locked_cut": locked_result,
        "marker": marker,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build TigerCapture automation command QA report.")
    parser.add_argument("--out", default="debugCapture/automation_commands_qa.json")
    args = parser.parse_args()
    report = build_automation_commands_report()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
