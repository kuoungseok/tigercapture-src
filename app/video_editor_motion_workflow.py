"""Main editor workflow for Motion Designer compositions and clips."""
from __future__ import annotations

from app.motion_designer.recovery import (
    default_motion_recovery_root, motion_recovery_path, write_motion_recovery,
)
from app.motion_designer.clip import MotionClip
from app.motion_designer.schema import MotionComposition
from app.motion_designer.timeline_bridge import duplicate_motion_clip
from app.video_editor_motion_lane_row import MotionLaneRow


def _sync_motion_state_to_player(self) -> None:
    player = getattr(self, "_player", None)
    if player is not None and hasattr(player, "set_motion_state"):
        player.set_motion_state(getattr(self, "_motion_compositions", {}) or {},
                                getattr(self, "_motion_clips", []) or [])


def _motion_lane_for_clip(self, clip: dict):
    clip_id = str(clip.get("id") or "")
    return next((row for row in getattr(self, "_motion_lane_rows", []) or []
                 if str(row.clip.get("id") or "") == clip_id), None)


def _insert_motion_lane(self, clip: dict):
    if not hasattr(self, "_tracks_layout") or not hasattr(self, "_timeline_ruler"):
        return None
    existing = self._motion_lane_for_clip(clip)
    if existing is not None:
        existing.clip = clip
        existing.update()
        return existing
    row = MotionLaneRow(clip, self)
    row.set_px_per_sec(getattr(self, "_px_per_sec", 52.0))
    row.clip_changed.connect(self._on_motion_lane_changed)
    row.clip_change_committed.connect(lambda _clip, label: self._register_change(label) if hasattr(self, "_register_change") else None)
    row.clip_double_clicked.connect(self._on_motion_lane_double_clicked)
    row.duplicate_requested.connect(self._duplicate_motion_clip)
    row.delete_requested.connect(self._delete_motion_clip)
    self._motion_lane_rows.append(row)
    ruler_index = self._tracks_layout.indexOf(self._timeline_ruler)
    self._tracks_layout.insertWidget(ruler_index + 1, row)
    return row


def _rebuild_motion_lanes(self) -> None:
    for row in list(getattr(self, "_motion_lane_rows", []) or []):
        try:
            self._tracks_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        except Exception:
            pass
    self._motion_lane_rows = []
    for clip in getattr(self, "_motion_clips", []) or []:
        self._insert_motion_lane(clip)
    if hasattr(self, "_update_tracks_host_width"):
        self._update_tracks_host_width()


def _on_motion_lane_changed(self, clip: dict) -> None:
    self._sync_motion_state_to_player()
    if hasattr(self, "_update_tracks_host_width"):
        self._update_tracks_host_width()
    player = getattr(self, "_player", None)
    if player is not None and hasattr(player, "refresh_current_frame"):
        player.refresh_current_frame()
    self._autosave_dirty = True


def _open_motion_designer(self, composition_id: str):
    store = getattr(self, "_motion_compositions", {}) or {}
    composition = store.get(str(composition_id or ""))
    if composition is None:
        raise ValueError(f"Motion composition not found: {composition_id}")
    from app.motion_designer.ui import MotionDesignerWindow

    current = getattr(self, "_motion_designer_window", None)
    if current is not None:
        current.close()
    window = MotionDesignerWindow(composition, self)
    window.composition_changed.connect(self._on_motion_composition_changed)
    window.autosave_requested.connect(self._on_motion_autosave_requested)
    self._motion_designer_window = window
    window.show()
    window.raise_()
    return window


def _on_motion_autosave_requested(self, composition: MotionComposition) -> dict:
    project_path = getattr(self, "_project_path", None)
    root = default_motion_recovery_root(project_path)
    return write_motion_recovery(
        composition, motion_recovery_path(root, composition.id), project_path=project_path,
    )


def _open_motion_designer_entry(self):
    settings = getattr(self, "_project_settings", {}) or {}
    composition = MotionComposition(
        name="Motion Composition",
        width=int(settings.get("canvas_width", 1920) or 1920),
        height=int(settings.get("canvas_height", 1080) or 1080),
        fps=float(settings.get("fps", 30.0) or 30.0),
        duration_ms=5000,
    )
    self._motion_compositions[composition.id] = composition
    self._place_motion_clip(composition.id)
    return self._open_motion_designer(composition.id)


def _on_motion_composition_changed(self, composition: MotionComposition) -> None:
    self._motion_compositions[composition.id] = composition
    self._sync_motion_state_to_player()
    player = getattr(self, "_player", None)
    if player is not None and hasattr(player, "refresh_current_frame"):
        player.refresh_current_frame()
    self._autosave_dirty = True


def _on_motion_lane_double_clicked(self, clip: dict) -> None:
    self._open_motion_designer(str(clip.get("composition_id") or ""))


def _place_motion_clip(self, composition_id: str, start_ms: int | None = None, duration_ms: int | None = None) -> dict:
    composition = getattr(self, "_motion_compositions", {}).get(str(composition_id or ""))
    if composition is None:
        raise ValueError(f"Motion composition not found: {composition_id}")
    start = int(self._player.position()) if start_ms is None else max(0, int(start_ms))
    clip = MotionClip(composition_id=composition.id, name=composition.name, start_ms=start,
                      duration_ms=max(100, int(duration_ms or composition.duration_ms))).to_dict()
    self._motion_clips.append(clip)
    self._insert_motion_lane(clip)
    self._refresh_player_tracks()
    return clip


def _duplicate_motion_clip(self, clip: dict) -> dict:
    duplicate = duplicate_motion_clip(MotionClip.from_dict(clip)).to_dict()
    self._motion_clips.append(duplicate)
    self._insert_motion_lane(duplicate)
    self._refresh_player_tracks()
    return duplicate


def _delete_motion_clip(self, clip: dict) -> None:
    clip_id = str(clip.get("id") or "")
    self._motion_clips = [item for item in self._motion_clips if str(item.get("id") or "") != clip_id]
    self._rebuild_motion_lanes()
    self._refresh_player_tracks()
