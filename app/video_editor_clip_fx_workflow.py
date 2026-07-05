from __future__ import annotations

from app.i18n import tr
from app.timeline_track_row import TrackRow


_ACTIVE_FX_ATTRS = ("video_filters", "chroma_key", "bg_removal")
_DISABLED_FX_ATTRS = (
    "disabled_video_filters",
    "disabled_chroma_key",
    "disabled_bg_removal",
)
_FX_ATTR_PAIRS = tuple(zip(_ACTIVE_FX_ATTRS, _DISABLED_FX_ATTRS))


def _clip_param_active(value) -> bool:
    return TrackRow._effect_param_active(value)


def _clip_has_active_fx(self, clip) -> bool:
    return any(_clip_param_active(getattr(clip, attr, None)) for attr in _ACTIVE_FX_ATTRS)


def _clip_has_disabled_fx(self, clip) -> bool:
    return any(_clip_param_active(getattr(clip, attr, None)) for attr in _DISABLED_FX_ATTRS)


def _refresh_clip_fx_ui(self, track) -> None:
    row = getattr(self, "_track_rows", {}).get(getattr(track, "id", None))
    if row is not None:
        row.update()
    self._refresh_player_tracks()
    self._refresh_preview_soft(track)
    self._refresh_workbench()


def _clear_clip_fx(self, track, clip, *, register: bool = True) -> bool:
    if track is None or clip is None:
        return False
    changed = False
    for attr in (*_ACTIVE_FX_ATTRS, *_DISABLED_FX_ATTRS):
        if getattr(clip, attr, None) is not None:
            setattr(clip, attr, None)
            changed = True
    if not changed:
        return False
    _refresh_clip_fx_ui(self, track)
    if register:
        self._register_change("clear clip FX")
    return True


def _set_clip_fx_enabled(self, track, clip, enabled: bool, *, register: bool = True) -> bool:
    if track is None or clip is None:
        return False
    changed = False
    if enabled:
        for active_attr, disabled_attr in _FX_ATTR_PAIRS:
            disabled_value = getattr(clip, disabled_attr, None)
            if disabled_value is not None and getattr(clip, active_attr, None) is None:
                setattr(clip, active_attr, disabled_value)
                setattr(clip, disabled_attr, None)
                changed = True
    else:
        for active_attr, disabled_attr in _FX_ATTR_PAIRS:
            active_value = getattr(clip, active_attr, None)
            if active_value is not None:
                setattr(clip, disabled_attr, active_value)
                setattr(clip, active_attr, None)
                changed = True
    if not changed:
        return False

    _refresh_clip_fx_ui(self, track)
    if register:
        self._register_change("enable clip FX" if enabled else "disable clip FX")
    self._flash_status(
        tr("veditor.clip_badge.status.fx_enabled")
        if enabled
        else tr("veditor.clip_badge.status.fx_disabled")
    )
    return True


def _target_clip_for_fx_action(self):
    track, clip = self._selected_video_clip()
    if clip is None:
        track, clip = self._workflow_target_video_clip()
    return track, clip


def _clear_selected_clip_fx(self) -> None:
    track, clip = _target_clip_for_fx_action(self)
    if track is None or clip is None:
        self._flash_status(tr("veditor.clip_badge.status.select_fx_clip"))
        return
    if not _clear_clip_fx(self, track, clip):
        self._flash_status(tr("veditor.clip_badge.status.no_fx_clear"))
        return
    self._flash_status(tr("veditor.clip_badge.status.cleared_fx"))


def _toggle_selected_clip_fx_enabled(self) -> None:
    track, clip = _target_clip_for_fx_action(self)
    if track is None or clip is None:
        self._flash_status(tr("veditor.clip_badge.status.select_fx_clip"))
        return
    if _clip_has_active_fx(self, clip):
        _set_clip_fx_enabled(self, track, clip, False)
        return
    if _clip_has_disabled_fx(self, clip):
        _set_clip_fx_enabled(self, track, clip, True)
        return
    self._flash_status(tr("veditor.clip_badge.status.no_fx"))


def _open_selected_clip_fx(self) -> None:
    track, clip = _target_clip_for_fx_action(self)
    if track is None or clip is None:
        self._flash_status(tr("veditor.clip_badge.status.select_clip"))
        return
    self._open_clip_effects(track, clip)


def _effect_payload_from_clip(self, clip) -> dict:
    payload: dict = {}
    vf = getattr(clip, "video_filters", None)
    try:
        if isinstance(vf, dict):
            payload["video_filters"] = dict(vf)
        elif vf is not None and (not hasattr(vf, "is_identity") or not vf.is_identity()):
            payload["video_filters"] = vf.to_dict() if hasattr(vf, "to_dict") else dict(vf)
    except Exception:
        pass
    chroma = getattr(clip, "chroma_key", None)
    try:
        if isinstance(chroma, dict):
            if chroma.get("enabled", False):
                payload["chroma_key"] = dict(chroma)
        elif chroma is not None and (not hasattr(chroma, "is_identity") or not chroma.is_identity()):
            payload["chroma_key"] = chroma.to_dict() if hasattr(chroma, "to_dict") else dict(chroma)
    except Exception:
        pass
    return payload
