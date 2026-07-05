"""Thin UI helpers for timeline actor editor workspaces.

This module only wires editor windows and timeline lane rows together. Rendering,
export, mocap, and performance-source behavior stays in the owning editor window
and actor runtime modules.
"""
from __future__ import annotations

from typing import Any

from app.live2d.actor_lane_row import Live2DActorLaneRow
from app.spine_editor.actor_lane_row import SpineActorLaneRow


def _insert_row_after_ruler(owner: Any, row: Any) -> None:
    layout = owner._tracks_layout
    ruler_idx = layout.indexOf(owner._timeline_ruler)
    layout.insertWidget(ruler_idx + 1, row)
    layout.invalidate()
    layout.activate()


def _lane_row_for_clip(rows: list[Any], clip: Any) -> Any | None:
    for row in rows:
        try:
            if clip in getattr(row.track, "clips", []):
                return row
        except Exception:
            continue
    return None


def _show_editor(editor: Any, clip: Any, lane_row: Any, path: str, loader_name: str) -> None:
    editor.set_target_clip(clip, lane_row)
    editor.show()
    editor.raise_()
    editor.activateWindow()
    if path:
        loader = getattr(editor, loader_name, None)
        if callable(loader):
            loader(path, delay_ms=120)


def insert_spine_actor_lane(owner: Any, track: Any) -> SpineActorLaneRow:
    row = SpineActorLaneRow(track)
    row.set_px_per_sec(owner._px_per_sec)
    row.set_lane_index(len(getattr(owner, "_actor_lane_rows", []) or []) + 1)
    row.clip_changed.connect(owner._on_actor_clip_changed)
    row.clip_double_clicked.connect(owner._on_spine_clip_dclick)
    owner._actor_lane_rows.append(row)
    _insert_row_after_ruler(owner, row)
    return row


def insert_live2d_actor_lane(owner: Any, track: Any) -> Live2DActorLaneRow:
    row = Live2DActorLaneRow(track)
    row.set_px_per_sec(owner._px_per_sec)
    row.set_lane_index(len(getattr(owner, "_live2d_lane_rows", []) or []) + 1)
    row.clip_changed.connect(owner._on_live2d_clip_changed)
    row.clip_double_clicked.connect(owner._on_live2d_clip_dclick)
    row.video_mocap_requested.connect(owner._on_live2d_clip_video_mocap_requested)
    row.motion_storyboard_requested.connect(owner._on_live2d_clip_storyboard_requested)
    row.performance_source_mapping_requested.connect(
        owner._on_live2d_clip_performance_source_mapping_requested
    )
    owner._live2d_lane_rows.append(row)
    _insert_row_after_ruler(owner, row)
    return row


def clear_actor_lane_rows(owner: Any, rows_attr: str) -> None:
    for row in list(getattr(owner, rows_attr, []) or []):
        try:
            owner._tracks_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        except Exception:
            pass
    setattr(owner, rows_attr, [])


def rebuild_spine_actor_lanes(owner: Any) -> None:
    clear_actor_lane_rows(owner, "_actor_lane_rows")
    for track in getattr(owner, "_spine_actor_tracks", []):
        insert_spine_actor_lane(owner, track)


def rebuild_live2d_actor_lanes(owner: Any) -> None:
    clear_actor_lane_rows(owner, "_live2d_lane_rows")
    for track in getattr(owner, "_live2d_actor_tracks", []):
        insert_live2d_actor_lane(owner, track)


def open_spine_clip_editor(owner: Any, clip: Any) -> None:
    """Open the existing Spine editor workflow for a timeline actor clip."""
    from app.spine_editor.editor_window import SpineEditorWindow

    owner._record_editor_action(
        "actor.open_spine_editor",
        skel_path=getattr(clip, "skel_path", ""),
        start_ms=getattr(clip, "start_ms", None),
        end_ms=getattr(clip, "end_ms", None),
    )
    focus = getattr(owner, "_focus_actor_clip_for_edit", None)
    if callable(focus):
        focus(clip, refresh=False)
    if not getattr(owner, "_spine_editor", None):
        owner._spine_editor = SpineEditorWindow(owner, autoload_sample=False)
        owner._spine_editor.destroyed.connect(
            lambda: setattr(owner, "_spine_editor", None)
        )
    lane_row = _lane_row_for_clip(getattr(owner, "_actor_lane_rows", []) or [], clip)
    _show_editor(
        owner._spine_editor,
        clip,
        lane_row,
        str(getattr(clip, "skel_path", "") or ""),
        "load_character_deferred",
    )


def open_live2d_clip_editor(owner: Any, clip: Any) -> None:
    """Open the existing Live2D editor workflow for a timeline actor clip."""
    from app.live2d.live2d_viewer import Live2DEditorWindow

    select_clip = getattr(owner, "_select_live2d_clip_in_lane", None)
    if callable(select_clip):
        select_clip(clip)
    owner._record_editor_action(
        "actor.open_live2d_editor",
        model_path=getattr(clip, "model_path", ""),
        start_ms=getattr(clip, "start_ms", None),
        end_ms=getattr(clip, "end_ms", None),
    )
    focus = getattr(owner, "_focus_actor_clip_for_edit", None)
    if callable(focus):
        focus(clip, refresh=False)
    if not getattr(owner, "_live2d_editor", None):
        owner._live2d_editor = Live2DEditorWindow(owner, autoload_sample=False)
        owner._live2d_editor.destroyed.connect(
            lambda: setattr(owner, "_live2d_editor", None)
        )
    lane_row = _lane_row_for_clip(getattr(owner, "_live2d_lane_rows", []) or [], clip)
    _show_editor(
        owner._live2d_editor,
        clip,
        lane_row,
        str(getattr(clip, "model_path", "") or ""),
        "load_model_deferred",
    )
