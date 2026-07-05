from __future__ import annotations

from typing import Any


VIDEO_TARGET_REQUIRED_MESSAGE = "비디오 미디어를 먼저 타임라인에 배치해야 합니다"
AUDIO_TARGET_REQUIRED_MESSAGE = "오디오 미디어를 먼저 타임라인에 배치해야 합니다"


def _call_if_available(owner: object, name: str, *args: Any, **kwargs: Any) -> Any:
    fn = getattr(owner, name, None)
    if callable(fn):
        return fn(*args, **kwargs)
    return None


def _flash_status(owner: object, message: str) -> None:
    try:
        _call_if_available(owner, "_flash_status", message)
    except Exception:
        pass


def _refresh_startup_template_ui_via_owner(owner: object) -> None:
    refresh = getattr(owner, "_refresh_startup_template_ui", None)
    if callable(refresh):
        refresh()
    else:
        _refresh_startup_template_ui(owner)


def _capcut_feature_disabled(owner: object, feature_id: str) -> bool:
    fn = getattr(owner, "_capcut_feature_disabled", None)
    if callable(fn):
        try:
            return bool(fn(feature_id))
        except Exception:
            return True
    try:
        from app.capcut_features import capcut_feature_disabled

        return bool(capcut_feature_disabled(feature_id))
    except Exception:
        return True


def _capcut_disabled_reason(owner: object, feature_id: str) -> str:
    fn = getattr(owner, "_capcut_disabled_reason", None)
    if callable(fn):
        try:
            return str(fn(feature_id))
        except Exception:
            pass
    try:
        from app.capcut_features import capcut_disabled_reason

        return str(capcut_disabled_reason(feature_id))
    except Exception:
        return f"{feature_id} is temporarily sealed."


def _startup_template_status(self) -> dict[str, object]:
    template_id = str(getattr(self, "_startup_template_id", "") or "")
    template_name = str(getattr(self, "_startup_template_name", "") or "Template")
    pending = bool(template_id and getattr(self, "_startup_template_pending", False))
    applied = bool(getattr(self, "_startup_template_applied", False))
    last_failure = str(getattr(self, "_startup_template_last_failure", "") or "")
    if applied:
        state = "applied"
    elif pending and last_failure:
        state = "waiting"
    elif pending:
        state = "ready"
    elif template_id:
        state = "inactive"
    else:
        state = "none"
    return {
        "id": template_id,
        "name": template_name,
        "pending": pending,
        "applied": applied,
        "last_failure": last_failure,
        "state": state,
        "preview_placeholder": str(getattr(self, "_preview_placeholder_kind", "") or ""),
    }


def _refresh_startup_template_ui(self) -> None:
    btn = getattr(self, "template_browser_btn", None)
    if btn is None:
        return
    status_fn = getattr(self, "_startup_template_status", None)
    if callable(status_fn):
        status = status_fn()
    else:
        status = _startup_template_status(self)
    pending = bool(status.get("pending"))
    if hasattr(btn, "setProperty"):
        btn.setProperty("startupTemplate", pending)
    if hasattr(btn, "setToolTip"):
        if pending:
            name = str(status.get("name") or "Template")
            failure = str(status.get("last_failure") or "")
            suffix = f"\nWaiting: {failure}" if failure else "\nImport media to auto-apply this template."
            btn.setToolTip(f"Template ready: {name}{suffix}")
        elif bool(status.get("applied")):
            btn.setToolTip(f"Template applied: {status.get('name') or 'Template'}")
        else:
            btn.setToolTip("Templates: browse one-click editing templates")
    try:
        style = btn.style()
        style.unpolish(btn)
        style.polish(btn)
    except Exception:
        pass
    update = getattr(btn, "update", None)
    if callable(update):
        update()


def show_startup_template_hint(self, template_id: str, template_name: str) -> None:
    self._startup_template_id = str(template_id or "")
    self._startup_template_name = str(template_name or "Template")
    self._startup_template_pending = bool(self._startup_template_id)
    self._startup_template_applied = False
    self._startup_template_last_failure = ""
    _call_if_available(self, "_set_preview_placeholder", "template")
    _refresh_startup_template_ui_via_owner(self)
    _flash_status(self, f"Template ready: {self._startup_template_name}")


def _startup_template_has_media_target(self) -> bool:
    has_video, has_audio = _startup_template_target_state(self)
    return has_video or has_audio


def _startup_template_target_state(self) -> tuple[bool, bool]:
    has_video = False
    for track in getattr(self, "_tracks", []) or []:
        if getattr(track, "source_path", None) is not None:
            has_video = True
            break
        if bool(getattr(track, "clips", None) or []):
            has_video = True
            break
    if not has_video:
        for track in getattr(self, "_live2d_actor_tracks", []) or []:
            if bool(getattr(track, "clips", None) or []):
                has_video = True
                break
    if not has_video:
        for track in getattr(self, "_spine_actor_tracks", []) or []:
            if bool(getattr(track, "clips", None) or []):
                has_video = True
                break

    has_audio = False
    for track in getattr(self, "_audio_tracks", []) or []:
        if bool(getattr(track, "is_loaded", False)):
            has_audio = True
            break
        if bool(getattr(track, "clips", None) or []):
            has_audio = True
            break
    return has_video, has_audio


def _startup_template_required_target_gap(self, preset, *, depth: int = 0) -> str:
    if preset is None or depth > 8:
        return ""
    kind = str(getattr(preset, "kind", "") or "")
    target_state = getattr(self, "_startup_template_target_state", None)
    if callable(target_state):
        has_video, has_audio = target_state()
    else:
        has_video, has_audio = _startup_template_target_state(self)
    if kind == "template":
        try:
            from app.preset_library import preset_by_id, template_sequence
        except Exception:
            return ""
        for entry in template_sequence(preset):
            entry = dict(entry or {})
            condition = str(entry.get("condition", "always") or "always")
            if condition == "if_video" and not has_video:
                continue
            if condition == "if_audio" and not has_audio:
                continue
            if condition not in {"", "always", "if_video", "if_audio"}:
                condition_ok = getattr(self, "_template_entry_condition_ok", None)
                if callable(condition_ok) and not condition_ok(entry):
                    continue
            child = preset_by_id(entry.get("preset_id", ""))
            if child is None:
                continue
            gap_fn = getattr(self, "_startup_template_required_target_gap", None)
            if callable(gap_fn):
                gap = gap_fn(child, depth=depth + 1)
            else:
                gap = _startup_template_required_target_gap(self, child, depth=depth + 1)
            if gap:
                return gap
        return ""
    if kind in {"effect", "transition", "title", "caption_style", "sticker", "motion", "color"}:
        if not has_video:
            return VIDEO_TARGET_REQUIRED_MESSAGE
    if kind == "audio" and not has_audio:
        return AUDIO_TARGET_REQUIRED_MESSAGE
    return ""


def _startup_template_preset(self):
    template_id = str(getattr(self, "_startup_template_id", "") or "")
    if not template_id:
        return None
    try:
        from app.preset_library import preset_by_id

        return preset_by_id(template_id)
    except Exception:
        return None


def _try_apply_startup_template_if_ready(self, reason: str = "media import") -> bool:
    if _capcut_feature_disabled(self, "template_auto_apply"):
        template_id_for_gate = str(getattr(self, "_startup_template_id", "") or "")
        if template_id_for_gate:
            self._startup_template_pending = False
            self._startup_template_last_failure = _capcut_disabled_reason(self, "template_auto_apply")
            _refresh_startup_template_ui_via_owner(self)
            _flash_status(self, "Template auto-apply is temporarily sealed")
        return False
    template_id = str(getattr(self, "_startup_template_id", "") or "")
    if not template_id:
        return False
    if bool(getattr(self, "_startup_template_applied", False)):
        return False
    if not bool(getattr(self, "_startup_template_pending", True)):
        return False
    has_media_target = getattr(self, "_startup_template_has_media_target", None)
    if callable(has_media_target):
        ready = bool(has_media_target())
    else:
        ready = _startup_template_has_media_target(self)
    if not ready:
        return False

    preset_fn = getattr(self, "_startup_template_preset", None)
    preset = preset_fn() if callable(preset_fn) else _startup_template_preset(self)
    if preset is None:
        self._startup_template_pending = False
        self._startup_template_last_failure = "missing preset"
        _refresh_startup_template_ui_via_owner(self)
        _flash_status(self, f"Template unavailable: {template_id}")
        return False

    gap_fn = getattr(self, "_startup_template_required_target_gap", None)
    target_gap = gap_fn(preset) if callable(gap_fn) else _startup_template_required_target_gap(self, preset)
    if target_gap:
        self._startup_template_last_failure = target_gap
        _refresh_startup_template_ui_via_owner(self)
        _flash_status(self, f"Template waiting: {target_gap}")
        return False

    failure_reason = ""
    failure_fn = getattr(self, "_preset_apply_failure_reason", None)
    if callable(failure_fn):
        try:
            failure_reason = str(failure_fn(preset) or "")
        except Exception as exc:
            failure_reason = str(exc)
    if failure_reason:
        self._startup_template_last_failure = failure_reason
        _refresh_startup_template_ui_via_owner(self)
        _flash_status(self, f"Template waiting: {failure_reason}")
        return False

    summary_fn = getattr(self, "_workflow_apply_summary_rows", None)
    summary_rows = summary_fn(preset) if callable(summary_fn) else []
    try:
        changed = bool(self._apply_editor_preset_object(preset, depth=0))
    except Exception as exc:
        self._startup_template_last_failure = str(exc)
        _refresh_startup_template_ui_via_owner(self)
        _flash_status(self, f"Template apply failed: {exc}")
        return False

    if not changed:
        self._startup_template_last_failure = reason
        _refresh_startup_template_ui_via_owner(self)
        _flash_status(self, "Template waiting: compatible preset target was not found")
        return False

    self._startup_template_pending = False
    self._startup_template_applied = True
    self._startup_template_last_failure = ""
    _refresh_startup_template_ui_via_owner(self)
    self._pending_workflow_apply_summary_rows = summary_rows
    finish = getattr(self, "_finish_workflow_preset_application", None)
    if callable(finish):
        finish(
            preset,
            undo_context="startup template",
            status_prefix="Template applied",
        )
    return True

