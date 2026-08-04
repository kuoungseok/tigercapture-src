"""Registered Python actions for safe editor automation."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.actions.editor_adapter import EditorAdapter
from app.actions.result import ActionResult, error_result, ok_result
from app.actions.schema import ActionSpec


ActionHandler = Callable[[Mapping[str, Any], bool], ActionResult]


class ActionRegistry:
    """Stable action surface for AI, MCP, QA, and developer automation."""

    def __init__(self, owner: Any | None = None, *, adapter: EditorAdapter | None = None) -> None:
        self.owner = owner
        self.adapter = adapter or EditorAdapter(owner)
        self._handlers: dict[str, tuple[ActionSpec, ActionHandler]] = {}
        self._register_defaults()

    def register(self, spec: ActionSpec, handler: ActionHandler) -> None:
        action_id = str(spec.id or "").strip()
        if not action_id:
            raise ValueError("action id is required")
        if action_id in self._handlers:
            raise ValueError(f"duplicate action id: {action_id}")
        self._handlers[action_id] = (spec, handler)

    def register_adapter_action(
        self,
        action_id: str,
        title: str,
        namespace: str,
        adapter_method: str,
        *,
        params_schema: Mapping[str, Any] | None = None,
        required: Sequence[str] = (),
        mutating: bool = True,
        destructive: bool = False,
        requires_review: bool = False,
        requires_owner: bool = True,
        undo_label: str = "",
        async_kind: str = "",
        dry_summary: str = "",
        changed: bool | None = None,
    ) -> None:
        spec = ActionSpec(
            action_id,
            title,
            namespace,
            params_schema=params_schema or {},
            mutating=mutating,
            destructive=destructive,
            requires_owner=bool(requires_owner),
            requires_review=requires_review,
            undo_label=undo_label,
            async_kind=async_kind,
        )

        def _handler(params: Mapping[str, Any], dry_run: bool) -> ActionResult:
            missing = [key for key in required if key not in params]
            if missing:
                return error_result(action_id, f"missing params: {', '.join(missing)}", dry_run=dry_run)
            if dry_run:
                return self._dry_result(action_id, params, dry_summary or f"{action_id} would run")
            method = getattr(self.adapter, adapter_method)
            result = method(**dict(params))
            return ok_result(action_id, result, changed=bool(mutating if changed is None else changed))

        self.register(spec, _handler)

    def list_actions(self) -> list[dict[str, Any]]:
        return [spec.to_dict() for spec, _handler in self._handlers.values()]

    def specs(self) -> list[dict[str, Any]]:
        return self.list_actions()

    def get_action_schema(self, action: str) -> dict[str, Any]:
        action_id = str(action or "").strip()
        row = self._handlers.get(action_id)
        if row is None:
            raise KeyError(f"unknown action: {action_id}")
        return row[0].to_dict()

    def preview_action(self, action: str, params: Mapping[str, Any] | None = None) -> ActionResult:
        action_id = str(action or "").strip()
        row = self._handlers.get(action_id)
        if row is None:
            return error_result(action_id, f"unknown action: {action_id}", preview=True, dry_run=True)
        spec, _handler = row
        return self.execute_action(action_id, params, dry_run=bool(spec.supports_dry_run), preview=True)

    def execute_action(
        self,
        action: str,
        params: Mapping[str, Any] | None = None,
        *,
        dry_run: bool = False,
        confirm_destructive: bool = False,
        preview: bool = False,
    ) -> ActionResult:
        action_id = str(action or "").strip()
        row = self._handlers.get(action_id)
        if row is None:
            return error_result(action_id, f"unknown action: {action_id}", dry_run=dry_run, preview=preview)
        spec, handler = row
        if spec.requires_owner and self.owner is None and not dry_run:
            return error_result(action_id, "no editor owner", dry_run=dry_run, preview=preview)
        if spec.destructive and not confirm_destructive and not dry_run:
            return error_result(
                action_id,
                "destructive action requires confirm_destructive=true",
                dry_run=dry_run,
                preview=preview,
            )
        if dry_run and not spec.supports_dry_run:
            return error_result(action_id, "action does not support dry_run", dry_run=True, preview=preview)
        try:
            result = handler(dict(params or {}), bool(dry_run))
        except Exception as exc:
            return error_result(action_id, str(exc), dry_run=dry_run, preview=preview)
        if preview and result.ok:
            return ok_result(action_id, result.result, warnings=result.warnings, dry_run=True, preview=True, changed=False)
        return result

    def execute(
        self,
        action: str,
        params: Mapping[str, Any] | None = None,
        *,
        dry_run: bool = False,
        confirm_destructive: bool = False,
    ) -> ActionResult:
        return self.execute_action(
            action,
            params,
            dry_run=dry_run,
            confirm_destructive=confirm_destructive,
        )

    def execute_sequence(
        self,
        steps: Sequence[Mapping[str, Any]],
        *,
        dry_run: bool = False,
        confirm_destructive: bool = False,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for index, step in enumerate(list(steps or [])):
            if not isinstance(step, Mapping):
                result = error_result("", f"step {index} must be an object", dry_run=dry_run).to_dict()
            else:
                result = self.execute_action(
                    str(step.get("action") or ""),
                    step.get("params") if isinstance(step.get("params"), Mapping) else {},
                    dry_run=bool(step.get("dry_run", dry_run)),
                    confirm_destructive=bool(step.get("confirm_destructive", confirm_destructive)),
                ).to_dict()
            results.append({"index": index, **result})
            if not result.get("ok"):
                return {"ok": False, "failed_index": index, "results": results}
        return {"ok": True, "failed_index": -1, "results": results}

    def _register_defaults(self) -> None:
        from app.actions.readonly_namespace import register_readonly_actions

        register_readonly_actions(self)
        from app.actions.nle_namespace import register_project_bin_actions

        register_project_bin_actions(self)
        from app.actions.vtuber_namespace import register_vseeface_bridge_actions, register_vtuber_studio_actions

        register_vseeface_bridge_actions(self)
        register_vtuber_studio_actions(self)
        from app.actions.nle_namespace import register_nle_readiness_actions

        register_nle_readiness_actions(self)
        from app.actions.nle_namespace import register_multicam_actions

        register_multicam_actions(self)
        from app.actions.creative_namespace import register_creative_readiness_actions

        register_creative_readiness_actions(self)
        from app.actions.unreal_link_namespace import register_unreal_link_actions

        register_unreal_link_actions(self)
        from app.actions.source_record_monitor_namespace import register_source_record_monitor_actions

        register_source_record_monitor_actions(self)
        from app.actions.nle_namespace import register_source_record_actions

        register_source_record_actions(self)
        from app.actions.creative_namespace import register_preset_catalog_actions

        register_preset_catalog_actions(self)
        from app.actions.media_track_namespace import register_media_track_actions

        register_media_track_actions(self)
        from app.actions.timeline_core_namespace import register_timeline_core_actions

        register_timeline_core_actions(self)
        from app.actions.marker_namespace import register_marker_actions

        register_marker_actions(self)
        from app.actions.clip_edit_namespace import register_clip_edit_actions

        register_clip_edit_actions(self)
        self._register_extended_actions()

    def _register_extended_actions(self) -> None:
        from app.actions.broadcast_namespace import register_broadcast_actions

        register_broadcast_actions(self)
        from app.actions.audio_namespace import register_audio_actions

        register_audio_actions(self)
        from app.actions.music_namespace import register_music_actions

        register_music_actions(self)
        from app.actions.tts_namespace import register_tts_actions

        register_tts_actions(self)
        from app.actions.track_selection_namespace import register_track_selection_actions

        register_track_selection_actions(self)
        from app.actions.selection_movement_namespace import register_selection_movement_actions

        register_selection_movement_actions(self)
        from app.actions.creative_namespace import register_creative_clip_actions

        register_creative_clip_actions(self)
        from app.actions.color_namespace import register_color_management_actions

        register_color_management_actions(self)
        from app.actions.actor_namespace import register_actor_actions

        register_actor_actions(self)
        from app.actions.character_template_namespace import register_character_template_actions

        register_character_template_actions(self)
        from app.actions.mmd_namespace import register_mmd_actions

        register_mmd_actions(self)
        from app.actions.ar_pbr_namespace import register_ar_pbr_actions

        register_ar_pbr_actions(self)
        from app.actions.ui_namespace import register_ui_actions

        register_ui_actions(self)
        from app.actions.ppt_namespace import register_ppt_actions

        register_ppt_actions(self)
        from app.actions.paint_namespace import register_paint_actions

        register_paint_actions(self)
        from app.actions.motion_namespace import register_motion_actions

        register_motion_actions(self)
        from app.actions.motion_aep_namespace import register_motion_aep_actions

        register_motion_aep_actions(self)
        from app.actions.motion_tracking_namespace import (
            register_motion_tracking_actions,
        )

        register_motion_tracking_actions(self)
        from app.actions.motion_lookdev_namespace import (
            register_motion_lookdev_actions,
        )

        register_motion_lookdev_actions(self)
        from app.actions.motion_plugin_namespace import register_motion_plugin_actions

        register_motion_plugin_actions(self)
        from app.actions.motion_ai_generation_namespace import register_motion_ai_generation_actions

        register_motion_ai_generation_actions(self)
        from app.actions.evidence_namespace import register_evidence_actions

        register_evidence_actions(self)

    def _dry_result(self, action: str, params: Mapping[str, Any], summary: str) -> ActionResult:
        return ok_result(
            action,
            {"would_apply": True, "summary": summary, "params": dict(params)},
            dry_run=True,
            changed=False,
        )

def build_default_action_registry(owner: Any | None = None) -> ActionRegistry:
    return ActionRegistry(owner)
