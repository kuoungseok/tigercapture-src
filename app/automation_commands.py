"""Safe automation command registry for AI/MCP agent control.

The registry is the boundary between external assistants and TigerCapture. It
does not execute arbitrary Python, shell commands, or project-file mutations.
Every command is named, schema-described, validated, and optionally dry-run
before the editor performs normal application code paths.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import json
from typing import Any

from app.ai_action_log import append_ai_action_log
from app.ai_edit_apply import (
    apply_ai_script_cut_intents_to_tracks,
    build_ai_script_apply_payload,
)
from app.ai_edit_plan import EditPlan, edit_plan_from_dict, validate_edit_plan_json
from app.ai_plan_validation import validate_edit_plan_for_snapshot
from app.ai_project_snapshot import build_project_snapshot_from_editor, minimal_project_snapshot
from app.ai_providers import provider_snapshot


AUTOMATION_COMMAND_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AutomationCommandSpec:
    name: str
    description: str
    mutates: bool = False
    requires_review: bool = False
    destructive: bool = False
    params_schema: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "mutates": bool(self.mutates),
            "requires_review": bool(self.requires_review),
            "destructive": bool(self.destructive),
            "params_schema": dict(self.params_schema),
        }


@dataclass(frozen=True)
class AutomationCommandResult:
    ok: bool
    command: str
    result: Mapping[str, Any] = field(default_factory=dict)
    error: str = ""
    warnings: Sequence[str] = field(default_factory=tuple)
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "command": self.command,
            "result": dict(self.result or {}),
            "error": self.error,
            "warnings": list(self.warnings or ()),
            "dry_run": bool(self.dry_run),
        }


CommandHandler = Callable[[Mapping[str, Any], bool], AutomationCommandResult]


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _parse_plan(value: Any) -> EditPlan:
    if isinstance(value, EditPlan):
        return value
    if isinstance(value, Mapping):
        return edit_plan_from_dict(value)
    if isinstance(value, str):
        return validate_edit_plan_json(value)
    raise ValueError("plan must be an EditPlan, dict, or JSON string")


def _snapshot_for_owner(owner: Any) -> dict[str, Any]:
    if owner is None:
        return minimal_project_snapshot()
    method = getattr(owner, "_ai_project_snapshot", None)
    if callable(method):
        return dict(method() or {})
    return build_project_snapshot_from_editor(owner)


def _track_clip_lookup(snapshot: Mapping[str, Any], track_key: str, clip_id: int) -> dict[str, Any] | None:
    for track in snapshot.get(track_key) or []:
        for clip in track.get("clips") or []:
            if int(clip.get("id", -1) or -1) == int(clip_id):
                row = dict(clip)
                row["track_id"] = int(track.get("id", 0) or 0)
                row["track_index"] = int(track.get("index", 0) or 0)
                return row
    return None


def _format_srt_ms(ms: int | None) -> str:
    value = max(0, int(ms or 0))
    seconds, millis = divmod(value, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{sec:02d},{millis:03d}"


def _snapshot_subtitles_to_srt_text(snapshot: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for idx, row in enumerate(snapshot.get("subtitles") or [], start=1):
        text = " ".join(str(row.get("text") or "").split())
        if not text:
            continue
        start_ms = max(0, int(row.get("start_ms", 0) or 0))
        end_ms = max(start_ms + 1, int(row.get("end_ms", start_ms + 1000) or start_ms + 1000))
        rows.append(f"{idx}\n{_format_srt_ms(start_ms)} --> {_format_srt_ms(end_ms)}\n{text}")
    return "\n\n".join(rows)


def _owner_subtitles_to_srt_text(owner: Any) -> str:
    rows = getattr(owner, "subtitles", None)
    if callable(rows):
        try:
            rows = rows()
        except Exception:
            rows = []
    return _snapshot_subtitles_to_srt_text({"subtitles": rows or []})


def _parse_silence_intervals(value: Any) -> list[dict[str, int]]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        intervals = []
        for row in value:
            if not isinstance(row, Mapping):
                continue
            try:
                start_ms = max(0, int(row.get("start_ms", 0) or 0))
                end_ms = max(start_ms + 1, int(row.get("end_ms", start_ms + 1) or start_ms + 1))
            except Exception:
                continue
            intervals.append({"start_ms": start_ms, "end_ms": end_ms})
        return intervals
    intervals = []
    for raw_line in str(value or "").replace(";", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for sep in ("-->", "-", ","):
            if sep in line:
                left, right = [part.strip() for part in line.split(sep, 1)]
                break
        else:
            continue
        try:
            start_ms = int(round(float(left)))
            end_ms = int(round(float(right)))
        except Exception:
            continue
        if end_ms > start_ms >= 0:
            intervals.append({"start_ms": start_ms, "end_ms": end_ms})
    return intervals


class AutomationCommandRegistry:
    """Registry of commands safe for future MCP exposure."""

    def __init__(self, owner: Any | None = None) -> None:
        self.owner = owner
        self._handlers: dict[str, tuple[AutomationCommandSpec, CommandHandler]] = {}
        self._register_defaults()

    def register(self, spec: AutomationCommandSpec, handler: CommandHandler) -> None:
        if not spec.name:
            raise ValueError("automation command name is required")
        self._handlers[spec.name] = (spec, handler)

    def specs(self) -> list[dict[str, Any]]:
        return [spec.to_dict() for spec, _handler in self._handlers.values()]

    def execute(
        self,
        command: str,
        params: Mapping[str, Any] | None = None,
        *,
        dry_run: bool = False,
    ) -> AutomationCommandResult:
        name = str(command or "").strip()
        if name not in self._handlers:
            result = AutomationCommandResult(False, name, error=f"unknown command: {name}", dry_run=dry_run)
            self._log(name, params or {}, result)
            return result
        spec, handler = self._handlers[name]
        if dry_run and not spec.mutates:
            dry_run = False
        try:
            result = handler(dict(params or {}), bool(dry_run))
        except Exception as exc:
            result = AutomationCommandResult(False, name, error=str(exc), dry_run=dry_run)
        self._log(name, params or {}, result)
        return result

    def _log(self, command: str, params: Mapping[str, Any], result: AutomationCommandResult) -> None:
        append_ai_action_log(
            "automation_command",
            {
                "command": command,
                "params": dict(params or {}),
                "ok": bool(result.ok),
                "error": result.error,
                "dry_run": bool(result.dry_run),
            },
        )

    def _register_defaults(self) -> None:
        self.register(
            AutomationCommandSpec(
                "get_app_status",
                "Return automation, provider, and project status.",
            ),
            self._cmd_get_app_status,
        )
        self.register(
            AutomationCommandSpec(
                "get_ai_provider_status",
                "Return AI provider and MCP bridge readiness metadata.",
            ),
            self._cmd_get_ai_provider_status,
        )
        self.register(
            AutomationCommandSpec(
                "get_project_snapshot",
                "Return read-only project state for AI planning.",
                params_schema={"media_limit": "optional int"},
            ),
            self._cmd_get_project_snapshot,
        )
        self.register(
            AutomationCommandSpec(
                "get_timeline_summary",
                "Return compact timeline counts and track ranges.",
            ),
            self._cmd_get_timeline_summary,
        )
        self.register(
            AutomationCommandSpec(
                "get_selected_clip",
                "Return the currently selected clip, if any.",
            ),
            self._cmd_get_selected_clip,
        )
        self.register(
            AutomationCommandSpec(
                "get_media_pool_summary",
                "Return media pool items and kind counts.",
            ),
            self._cmd_get_media_pool_summary,
        )
        self.register(
            AutomationCommandSpec(
                "get_transcript_summary",
                "Return subtitle/transcript rows visible to AI planning.",
            ),
            self._cmd_get_transcript_summary,
        )
        self.register(
            AutomationCommandSpec(
                "validate_edit_plan",
                "Validate an EditPlan against the current project snapshot.",
                params_schema={
                    "plan": "EditPlan dict or JSON string",
                    "operation_ids": "optional list[str]",
                    "destructive_apply": "optional bool",
                },
            ),
            self._cmd_validate_edit_plan,
        )
        self.register(
            AutomationCommandSpec(
                "generate_edit_plan",
                "Generate a deterministic Script Edit plan from transcript text, project subtitles, or prompt.",
                params_schema={
                    "transcript_text": "optional SRT/WebVTT text; falls back to project subtitles",
                    "source_format": "optional auto|srt|vtt",
                    "prompt": "optional natural-language local recipe prompt",
                    "action": "optional transcript_to_captions|clean_tutorial|shorts|product_demo|remove_filler_words|remove_silences|text_range_cut",
                    "style_preset_id": "optional caption style id",
                    "silence_intervals": "optional list[{start_ms,end_ms}] or text",
                },
            ),
            self._cmd_generate_edit_plan,
        )
        self.register(
            AutomationCommandSpec(
                "preview_generated_plan",
                "Return human-readable review cards and operation preview for an EditPlan without mutating the timeline.",
                params_schema={"plan": "EditPlan dict or JSON string"},
            ),
            self._cmd_preview_generated_plan,
        )
        self.register(
            AutomationCommandSpec(
                "preview_edit_plan",
                "Validate and stage a non-destructive visual preview of an EditPlan.",
                mutates=True,
                requires_review=True,
                params_schema={"plan": "EditPlan dict or JSON string", "operation_ids": "optional list[str]"},
            ),
            self._cmd_preview_edit_plan,
        )
        self.register(
            AutomationCommandSpec(
                "apply_edit_plan",
                "Apply only safe, reviewable EditPlan payload sections through editor APIs.",
                mutates=True,
                requires_review=True,
                params_schema={"plan": "EditPlan dict or JSON string", "operation_ids": "optional list[str]"},
            ),
            self._cmd_apply_edit_plan,
        )
        self.register(
            AutomationCommandSpec(
                "apply_reviewed_cuts",
                "Materialize reviewed AI cut ranges as global ripple deletes.",
                mutates=True,
                requires_review=True,
                destructive=True,
                params_schema={"plan": "EditPlan dict or JSON string", "operation_ids": "optional list[str]"},
            ),
            self._cmd_apply_reviewed_cuts,
        )
        self.register(
            AutomationCommandSpec(
                "add_marker",
                "Add a timeline marker at a project time.",
                mutates=True,
                params_schema={"ms": "int", "label": "str", "color": "optional str"},
            ),
            self._cmd_add_marker,
        )

    def _cmd_get_app_status(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        snapshot = _snapshot_for_owner(self.owner)
        return AutomationCommandResult(
            True,
            "get_app_status",
            {
                "schema_version": AUTOMATION_COMMAND_SCHEMA_VERSION,
                "app": "TigerCapture",
                "automation": {
                    "command_count": len(self._handlers),
                    "arbitrary_python": False,
                    "arbitrary_shell": False,
                },
                "providers": provider_snapshot(),
                "snapshot_hash": snapshot.get("snapshot_hash", ""),
                "project_summary": snapshot.get("summary", {}),
            },
        )

    def _cmd_get_ai_provider_status(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        return AutomationCommandResult(True, "get_ai_provider_status", provider_snapshot())

    def _cmd_get_project_snapshot(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        snapshot = _snapshot_for_owner(self.owner)
        return AutomationCommandResult(True, "get_project_snapshot", snapshot)

    def _cmd_get_timeline_summary(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        snapshot = _snapshot_for_owner(self.owner)
        tracks = []
        for kind, key in (("video", "video_tracks"), ("audio", "audio_tracks")):
            for track in snapshot.get(key) or []:
                starts: list[int] = []
                ends: list[int] = []
                for clip in track.get("clips") or []:
                    starts.append(int(clip.get("timeline_in_ms", clip.get("offset_ms", 0)) or 0))
                    ends.append(int(clip.get("timeline_out_ms", clip.get("end_ms", 0)) or 0))
                tracks.append(
                    {
                        "kind": kind,
                        "id": track.get("id"),
                        "locked": bool(track.get("locked")),
                        "clip_count": len(track.get("clips") or []),
                        "start_ms": min(starts) if starts else 0,
                        "end_ms": max(ends) if ends else 0,
                    }
                )
        return AutomationCommandResult(
            True,
            "get_timeline_summary",
            {
                "duration_ms": int(snapshot.get("duration_ms", 0) or 0),
                "summary": snapshot.get("summary", {}),
                "tracks": tracks,
                "snapshot_hash": snapshot.get("snapshot_hash", ""),
            },
        )

    def _cmd_get_selected_clip(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        snapshot = _snapshot_for_owner(self.owner)
        selected = list(snapshot.get("selected_clips") or [])
        if not selected:
            return AutomationCommandResult(True, "get_selected_clip", {"selected": None})
        first = selected[0]
        clip = _track_clip_lookup(snapshot, "video_tracks", int(first.get("clip_id", -1) or -1))
        if clip is None:
            clip = _track_clip_lookup(snapshot, "audio_tracks", int(first.get("clip_id", -1) or -1))
        return AutomationCommandResult(True, "get_selected_clip", {"selected": clip, "selection": first})

    def _cmd_get_media_pool_summary(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        snapshot = _snapshot_for_owner(self.owner)
        counts: dict[str, int] = {}
        items = list(snapshot.get("media_pool") or [])
        for item in items:
            kind = str(item.get("kind") or "unknown")
            counts[kind] = counts.get(kind, 0) + 1
        return AutomationCommandResult(
            True,
            "get_media_pool_summary",
            {"count": len(items), "kind_counts": counts, "items": items, "snapshot_hash": snapshot.get("snapshot_hash", "")},
        )

    def _cmd_get_transcript_summary(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        snapshot = _snapshot_for_owner(self.owner)
        rows = list(snapshot.get("subtitles") or [])
        text_chars = sum(len(str(row.get("text") or "")) for row in rows)
        return AutomationCommandResult(
            True,
            "get_transcript_summary",
            {
                "count": len(rows),
                "text_chars": text_chars,
                "rows": rows[: int(params.get("limit", 200) or 200)],
                "snapshot_hash": snapshot.get("snapshot_hash", ""),
            },
        )

    def _cmd_validate_edit_plan(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        plan = _parse_plan(params.get("plan") or params.get("plan_json"))
        operation_ids = [str(item) for item in _as_list(params.get("operation_ids"))] if "operation_ids" in params else None
        snapshot = _snapshot_for_owner(self.owner)
        validation = validate_edit_plan_for_snapshot(
            plan,
            snapshot,
            operation_ids=operation_ids,
            destructive_apply=bool(params.get("destructive_apply", False)),
        )
        return AutomationCommandResult(
            bool(validation.ok),
            "validate_edit_plan",
            {"plan_id": plan.id, "validation": validation.to_dict(), "snapshot_hash": snapshot.get("snapshot_hash", "")},
            error="" if validation.ok else ", ".join(validation.blocked),
            warnings=validation.warnings,
        )

    def _cmd_generate_edit_plan(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        from app.ai_script_edit_panel import ScriptEditPanelModel, edit_plan_preview

        snapshot = _snapshot_for_owner(self.owner)
        transcript_text = str(params.get("transcript_text") or params.get("transcript") or "").strip()
        source_format = str(params.get("source_format") or "auto").strip() or "auto"
        transcript_source = "params"
        if not transcript_text:
            transcript_text = _snapshot_subtitles_to_srt_text(snapshot)
            source_format = "srt"
            transcript_source = "project_subtitles"
        if not transcript_text and self.owner is not None:
            transcript_text = _owner_subtitles_to_srt_text(self.owner)
            source_format = "srt"
            transcript_source = "project_subtitles"
        if not transcript_text:
            return AutomationCommandResult(
                False,
                "generate_edit_plan",
                {
                    "reason": "transcript_text is required when the project has no subtitles",
                    "snapshot_hash": snapshot.get("snapshot_hash", ""),
                },
                error="missing_transcript",
            )

        model = ScriptEditPanelModel(
            source_media_id=str(params.get("source_media_id") or "media_001"),
            language=str(params.get("language") or snapshot.get("settings", {}).get("language") or "und"),
        )
        document = model.import_transcript_text(
            transcript_text,
            source_format=source_format,
            document_id=str(params.get("document_id") or "automation_transcript"),
            source_media_id=str(params.get("source_media_id") or "media_001"),
            language=str(params.get("language") or snapshot.get("settings", {}).get("language") or "und"),
        )
        silences = _parse_silence_intervals(params.get("silence_intervals") or params.get("silence_intervals_text"))
        if silences:
            model.set_silence_intervals(silences)

        kwargs = {
            "style_preset_id": params.get("style_preset_id"),
            "min_duration_ms": params.get("min_duration_ms", 700),
            "target_duration_ms": params.get("target_duration_ms", 45_000),
            "segment_id": params.get("segment_id"),
            "start_char": params.get("start_char", 0),
            "end_char": params.get("end_char", 0),
        }
        prompt = str(params.get("prompt") or "").strip()
        action = str(params.get("action") or "").strip()
        if prompt:
            plan = model.generate_plan_from_prompt(prompt, **kwargs)
        else:
            plan = model.generate_plan(action or "clean_tutorial", **kwargs)

        validation = validate_edit_plan_for_snapshot(plan, snapshot, destructive_apply=False)
        payload_result = build_ai_script_apply_payload(plan)
        preview = edit_plan_preview(plan)
        return AutomationCommandResult(
            bool(validation.ok),
            "generate_edit_plan",
            {
                "plan": plan.to_dict(),
                "preview": preview,
                "validation": validation.to_dict(),
                "payload_counts": dict(payload_result.counts),
                "document": document.to_dict(),
                "transcript_source": transcript_source,
                "snapshot_hash": snapshot.get("snapshot_hash", ""),
            },
            error="" if validation.ok else ", ".join(validation.blocked),
            warnings=validation.warnings + payload_result.warnings,
            dry_run=dry_run,
        )

    def _cmd_preview_generated_plan(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        from app.ai_script_edit_panel import edit_plan_preview

        plan = _parse_plan(params.get("plan") or params.get("plan_json"))
        payload_result = build_ai_script_apply_payload(plan)
        return AutomationCommandResult(
            True,
            "preview_generated_plan",
            {
                "plan_id": plan.id,
                "preview": edit_plan_preview(plan),
                "payload": payload_result.to_dict(),
            },
            warnings=payload_result.warnings,
        )

    def _cmd_preview_edit_plan(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        plan = _parse_plan(params.get("plan") or params.get("plan_json"))
        operation_ids = [str(item) for item in _as_list(params.get("operation_ids"))] if "operation_ids" in params else None
        snapshot = _snapshot_for_owner(self.owner)
        validation = validate_edit_plan_for_snapshot(plan, snapshot, operation_ids=operation_ids, destructive_apply=False)
        payload_result = build_ai_script_apply_payload(plan, operation_ids=operation_ids)
        marker_count = 0
        if validation.ok and not dry_run and self.owner is not None:
            method = getattr(self.owner, "_sync_ai_script_preview_markers", None)
            if callable(method):
                marker_count = int(method(dict(payload_result.payload or {})) or 0)
        return AutomationCommandResult(
            bool(validation.ok),
            "preview_edit_plan",
            {
                "plan_id": plan.id,
                "payload": payload_result.to_dict(),
                "validation": validation.to_dict(),
                "preview_markers": marker_count,
                "snapshot_hash": snapshot.get("snapshot_hash", ""),
            },
            error="" if validation.ok else ", ".join(validation.blocked),
            warnings=validation.warnings + payload_result.warnings,
            dry_run=dry_run,
        )

    def _cmd_apply_edit_plan(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        plan = _parse_plan(params.get("plan") or params.get("plan_json"))
        operation_ids = [str(item) for item in _as_list(params.get("operation_ids"))] if "operation_ids" in params else None
        snapshot = _snapshot_for_owner(self.owner)
        validation = validate_edit_plan_for_snapshot(plan, snapshot, operation_ids=operation_ids, destructive_apply=False)
        payload_result = build_ai_script_apply_payload(plan, operation_ids=operation_ids)
        if not validation.ok or dry_run:
            return AutomationCommandResult(
                bool(validation.ok),
                "apply_edit_plan",
                {
                    "plan_id": plan.id,
                    "payload": payload_result.to_dict(),
                    "validation": validation.to_dict(),
                    "applied": {},
                },
                error="" if validation.ok else ", ".join(validation.blocked),
                warnings=validation.warnings + payload_result.warnings,
                dry_run=dry_run,
            )
        applied = self._apply_safe_payload(payload_result.payload)
        return AutomationCommandResult(
            True,
            "apply_edit_plan",
            {
                "plan_id": plan.id,
                "payload": payload_result.to_dict(),
                "validation": validation.to_dict(),
                "applied": applied,
            },
            warnings=validation.warnings + payload_result.warnings,
        )

    def _apply_safe_payload(self, payload: Mapping[str, Any]) -> dict[str, int]:
        owner = self.owner
        if owner is None:
            return {}
        applied = {
            "subtitle_rows": 0,
            "timeline_markers": 0,
            "render_queue_jobs": 0,
            "auto_zoom": 0,
            "preview_markers": 0,
        }
        calls = (
            ("subtitle_rows", "_apply_ai_script_subtitles"),
            ("timeline_markers", "_apply_ai_script_markers"),
        )
        for key, method_name in calls:
            rows = list(payload.get(key) or [])
            method = getattr(owner, method_name, None)
            if rows and callable(method):
                applied[key] = int(method(rows) or 0)
        if payload.get("render_queue_jobs"):
            method = getattr(owner, "_stage_ai_script_render_jobs", None)
            if callable(method):
                result = method(dict(payload or {})) or {}
                applied["render_queue_jobs"] = int(result.get("added", 0) or 0)
        method = getattr(owner, "_apply_ai_script_auto_suggestions", None)
        if callable(method):
            applied["auto_zoom"] = int(method(dict(payload or {})) or 0)
        method = getattr(owner, "_sync_ai_script_preview_markers", None)
        if callable(method):
            applied["preview_markers"] = int(method(dict(payload or {})) or 0)
        method = getattr(owner, "_store_ai_script_edit_payload", None)
        if callable(method):
            method(dict(payload or {}), {"source": "automation_command_registry", "applied": applied})
        register = getattr(owner, "_register_change", None)
        if callable(register) and any(applied.values()):
            register("Automation AI edit plan apply")
        flash = getattr(owner, "_flash_status", None)
        if callable(flash):
            flash(
                "Automation apply: "
                f"subtitles {applied['subtitle_rows']}, markers {applied['timeline_markers']}, "
                f"queue {applied['render_queue_jobs']}, auto zoom {applied['auto_zoom']}"
            )
        return applied

    def _cmd_apply_reviewed_cuts(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        plan = _parse_plan(params.get("plan") or params.get("plan_json"))
        operation_ids = [str(item) for item in _as_list(params.get("operation_ids"))] if "operation_ids" in params else None
        snapshot = _snapshot_for_owner(self.owner)
        validation = validate_edit_plan_for_snapshot(plan, snapshot, operation_ids=operation_ids, destructive_apply=True)
        payload_result = build_ai_script_apply_payload(plan, operation_ids=operation_ids)
        cut_intents = list(payload_result.payload.get("cut_intents") or [])
        if not validation.ok or dry_run:
            return AutomationCommandResult(
                bool(validation.ok),
                "apply_reviewed_cuts",
                {
                    "plan_id": plan.id,
                    "cut_intents": cut_intents,
                    "validation": validation.to_dict(),
                    "cut_materialize_result": {},
                },
                error="" if validation.ok else ", ".join(validation.blocked),
                warnings=validation.warnings + payload_result.warnings,
                dry_run=dry_run,
            )
        owner = self.owner
        result = apply_ai_script_cut_intents_to_tracks(
            getattr(owner, "_tracks", []) or [],
            getattr(owner, "_audio_tracks", []) or [],
            cut_intents,
        )
        if owner is not None:
            sync = getattr(owner, "_sync_ai_script_applied_cut_markers", None)
            if callable(sync):
                sync(result)
            store = getattr(owner, "_store_ai_script_edit_payload", None)
            if callable(store):
                store(dict(payload_result.payload or {}), {**payload_result.to_dict(), "cut_materialize_result": dict(result)})
            refresh = getattr(owner, "_refresh_player_tracks", None)
            if callable(refresh):
                refresh()
            register = getattr(owner, "_register_change", None)
            if callable(register) and result.get("ok"):
                register("Automation reviewed ripple cuts")
            flash = getattr(owner, "_flash_status", None)
            if callable(flash):
                flash(f"Automation cuts: {len(result.get('applied_ranges') or [])} range(s)")
        return AutomationCommandResult(
            bool(result.get("ok")),
            "apply_reviewed_cuts",
            {
                "plan_id": plan.id,
                "validation": validation.to_dict(),
                "cut_materialize_result": dict(result),
            },
            error="" if result.get("ok") else "no cut range applied",
            warnings=validation.warnings + payload_result.warnings + list(result.get("warnings") or []),
        )

    def _cmd_add_marker(self, params: Mapping[str, Any], dry_run: bool) -> AutomationCommandResult:
        ms = max(0, int(params.get("ms", 0) or 0))
        label = str(params.get("label") or "Agent marker").strip() or "Agent marker"
        marker = {
            "ms": ms,
            "label": label,
            "color": str(params.get("color") or "#8A7CFF"),
            "source": "automation_command",
            "id": str(params.get("id") or f"agent-marker-{ms}-{abs(hash(label)) % 10000}"),
        }
        if dry_run:
            return AutomationCommandResult(True, "add_marker", {"marker": marker}, dry_run=True)
        owner = self.owner
        if owner is None:
            return AutomationCommandResult(False, "add_marker", {"marker": marker}, error="no editor owner")
        markers = list(getattr(owner, "_timeline_markers", []) or [])
        markers.append(marker)
        owner._timeline_markers = sorted(markers, key=lambda row: int(row.get("ms", 0) or 0))
        sync = getattr(owner, "_sync_markers_to_ruler", None)
        if callable(sync):
            sync()
        register = getattr(owner, "_register_change", None)
        if callable(register):
            register("Automation add marker")
        return AutomationCommandResult(True, "add_marker", {"marker": marker})


def build_default_automation_registry(owner: Any | None = None) -> AutomationCommandRegistry:
    return AutomationCommandRegistry(owner)


def automation_command_specs(owner: Any | None = None) -> list[dict[str, Any]]:
    return build_default_automation_registry(owner).specs()


def execute_automation_command(
    owner: Any | None,
    command: str,
    params: Mapping[str, Any] | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    return build_default_automation_registry(owner).execute(command, params, dry_run=dry_run).to_dict()


def automation_command_specs_json(owner: Any | None = None) -> str:
    return json.dumps(automation_command_specs(owner), ensure_ascii=False, sort_keys=True)
