from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from app.mmd.actor_lane_row import MMDActorLaneRow

DEFAULT_PX_PER_SEC = 52.0


def _on_workbench_mmd_rotation_hint_changed(self, value: float) -> None:
    panel = getattr(self, "_workbench_panel", None)
    target = (
        panel.current_target()
        if panel is not None and hasattr(panel, "current_target")
        else None
    )
    if target is None or target[0] != "mmd":
        return
    self._set_mmd_track_playback_value(
        target[1],
        "physics_rotation_hint_scale",
        float(value),
    )


def _on_workbench_mmd_spring_response_changed(self, value: float) -> None:
    panel = getattr(self, "_workbench_panel", None)
    target = (
        panel.current_target()
        if panel is not None and hasattr(panel, "current_target")
        else None
    )
    if target is None or target[0] != "mmd":
        return
    self._set_mmd_track_playback_value(
        target[1],
        "physics_spring_response",
        float(value),
    )


def _mmd_media_pool_paths(self) -> tuple[list[Path], list[Path]]:
    try:
        from app.mmd.project_tracks import split_mmd_paths
    except Exception:
        return [], []
    pool = getattr(self, "_media_pool", None)
    items = []
    if pool is not None and hasattr(pool, "items"):
        try:
            items = list(pool.items())
        except Exception:
            items = []
    return split_mmd_paths(items)


def _default_mmd_motion_for_model(self, model_path: Path) -> Path | None:
    try:
        siblings = [p.resolve() for p in model_path.parent.glob("*.vmd") if p.is_file()]
        if len(siblings) == 1:
            return siblings[0]
    except Exception:
        pass
    _models, motions = self._mmd_media_pool_paths()
    return motions[0] if len(motions) == 1 else None


def _mmd_lane_for_track(self, track: dict) -> MMDActorLaneRow | None:
    track_id = str(track.get("id") or "") if isinstance(track, dict) else ""
    for row in getattr(self, "_mmd_lane_rows", []) or []:
        row_track = getattr(row, "track", {})
        if isinstance(row_track, dict) and str(row_track.get("id") or "") == track_id:
            return row
    return None


def _insert_mmd_actor_lane(self, track: dict) -> MMDActorLaneRow | None:
    if not isinstance(track, dict):
        return None
    existing = self._mmd_lane_for_track(track)
    if existing is not None:
        existing.set_track(track)
        existing.update()
        return existing
    if not hasattr(self, "_tracks_layout") or not hasattr(self, "_timeline_ruler"):
        return None
    row = MMDActorLaneRow(track)
    row.set_px_per_sec(getattr(self, "_px_per_sec", DEFAULT_PX_PER_SEC))
    row.set_lane_index(len(getattr(self, "_mmd_lane_rows", []) or []) + 1)
    row.track_selected.connect(self._select_mmd_track)
    row.track_changed.connect(self._on_mmd_lane_track_changed)
    row.track_change_committed.connect(
        lambda changed, label: self._refresh_mmd_track_after_editor_change(
            changed,
            register=True,
            label=label,
        )
    )
    row.track_double_clicked.connect(self._on_mmd_lane_double_clicked)
    row.track_duplicate_requested.connect(self._duplicate_mmd_track)
    row.track_delete_requested.connect(self._delete_mmd_track)
    row.motion_browse_requested.connect(self._browse_mmd_motion_for_track)
    row.physics_toggle_requested.connect(self._set_mmd_track_physics_enabled)
    row.model_dropped.connect(lambda paths, start_ms, target=track: self._on_mmd_lane_drop(target, paths, start_ms))
    self._mmd_lane_rows.append(row)
    ruler_idx = self._tracks_layout.indexOf(self._timeline_ruler)
    self._tracks_layout.insertWidget(ruler_idx + 1, row)
    self._tracks_layout.invalidate()
    self._tracks_layout.activate()
    return row


def _remove_mmd_actor_lane(self, track: dict) -> None:
    row = self._mmd_lane_for_track(track)
    if row is None:
        return
    try:
        self._tracks_layout.removeWidget(row)
    except Exception:
        pass
    try:
        self._mmd_lane_rows.remove(row)
    except ValueError:
        pass
    row.setParent(None)
    row.deleteLater()
    for idx, candidate in enumerate(getattr(self, "_mmd_lane_rows", []) or [], start=1):
        candidate.set_lane_index(idx)


def _set_mmd_row_selection(self, selected_track_id: str) -> None:
    selected_id = str(selected_track_id or "")
    for row in getattr(self, "_mmd_lane_rows", []) or []:
        row_track = getattr(row, "track", {})
        row_id = str(row_track.get("id") or "") if isinstance(row_track, dict) else ""
        setter = getattr(row, "set_selected", None)
        if callable(setter):
            setter(row_id == selected_id)


def _select_mmd_track(self, track: dict) -> None:
    if not isinstance(track, dict):
        return
    self._selected_mmd_track_id = str(track.get("id") or "")
    self._set_mmd_row_selection(self._selected_mmd_track_id)
    self._show_mmd_track_in_workbench(track)


def _rebuild_mmd_actor_lanes(self) -> None:
    for row in list(getattr(self, "_mmd_lane_rows", []) or []):
        try:
            self._tracks_layout.removeWidget(row)
        except Exception:
            pass
        row.setParent(None)
        row.deleteLater()
    self._mmd_lane_rows = []
    for track in getattr(self, "_mmd_tracks", []) or []:
        self._insert_mmd_actor_lane(track)
    if hasattr(self, "_tracks_host") and hasattr(self, "_timeline_ruler"):
        self._update_tracks_host_width()


def _on_mmd_lane_track_changed(self, track: dict) -> None:
    if not isinstance(track, dict):
        return
    self._select_mmd_track(track)
    self._sync_mmd_tracks_to_player()
    if hasattr(self, "_tracks_host") and hasattr(self, "_timeline_ruler"):
        self._update_tracks_host_width()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    self._autosave_dirty = True


def _on_mmd_lane_double_clicked(self, track: dict) -> None:
    if not isinstance(track, dict):
        return
    self._select_mmd_track(track)
    try:
        start = int(track.get("start_ms", 0) or 0)
        end = int(track.get("end_ms", start) or start)
        current = int(self._player.position())
        if end > start and not (start <= current < end):
            self._player.set_position(min(end - 1, start + max(1, min(120, (end - start) // 8))))
    except Exception:
        pass
    self._open_mmd_actor_editor(str(track.get("id") or ""))


def _delete_mmd_track(self, track: dict, *, register: bool = True) -> dict:
    if not isinstance(track, dict):
        return {"deleted": False, "reason": "invalid_track"}
    track_id = str(track.get("id") or "")
    target = self._find_mmd_track(track_id) if track_id else track
    if target is None:
        return {"deleted": False, "reason": "not_found", "track_id": track_id}
    try:
        self._mmd_tracks.remove(target)
    except ValueError:
        return {"deleted": False, "reason": "not_found", "track_id": track_id}
    self._remove_mmd_actor_lane(target)
    if str(getattr(self, "_selected_mmd_track_id", "") or "") == track_id:
        self._selected_mmd_track_id = ""
        next_track = (getattr(self, "_mmd_tracks", []) or [None])[-1]
        if isinstance(next_track, dict):
            self._select_mmd_track(next_track)
        else:
            panel = getattr(self, "_workbench_panel", None)
            if panel is not None and hasattr(panel, "clear"):
                try:
                    panel.clear()
                except Exception:
                    pass
            self._set_mmd_row_selection("")
    self._sync_mmd_tracks_to_player()
    self._refresh_player_tracks()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    if register:
        try:
            self._register_change("delete mmd actor")
        except Exception:
            pass
    return {"deleted": True, "track_id": track_id}


def _duplicate_mmd_track(
    self,
    track: dict,
    *,
    start_ms: int | None = None,
    track_id: str = "",
    register: bool = True,
) -> dict | None:
    if not isinstance(track, dict):
        return None
    try:
        from app.mmd.project_tracks import duplicate_mmd_track, next_mmd_track_id
    except Exception:
        return None
    new_id = str(track_id or next_mmd_track_id(getattr(self, "_mmd_tracks", []) or []))
    clone = duplicate_mmd_track(track, track_id=new_id, start_ms=start_ms)
    self._mmd_tracks.append(clone)
    self._insert_mmd_actor_lane(clone)
    self._select_mmd_track(clone)
    self._sync_mmd_tracks_to_player()
    self._refresh_player_tracks()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    if register:
        try:
            self._register_change("duplicate mmd actor")
        except Exception:
            pass
    return clone


def _browse_mmd_motion_for_track(self, track: dict) -> None:
    if not isinstance(track, dict):
        return
    start_dir = str(Path(str(track.get("model_path") or "")).parent)
    path, _filter = QFileDialog.getOpenFileName(self, "Change MMD Motion", start_dir, "VMD Motion (*.vmd)")
    if path:
        self._set_mmd_track_motion(track, Path(path))


def _set_mmd_track_physics_enabled(self, track: dict, enabled: bool, *, register: bool = True) -> dict:
    if not isinstance(track, dict):
        return {"updated": False, "reason": "invalid_track"}
    playback = dict(track.get("playback") if isinstance(track.get("playback"), dict) else {})
    playback["enable_physics"] = bool(enabled)
    try:
        from app.mmd.schema import normalize_playback

        track["playback"] = normalize_playback(playback)
    except Exception:
        track["playback"] = playback
    self._refresh_mmd_track_after_editor_change(
        track,
        register=register,
        label="toggle mmd physics",
    )
    return {"updated": True, "track_id": str(track.get("id") or ""), "enable_physics": bool(enabled)}


def _on_mmd_lane_drop(self, target_track: dict, paths: list[Path], start_ms: int) -> None:
    try:
        from app.mmd.project_tracks import split_mmd_paths
    except Exception:
        split_mmd_paths = None
    models, motions = split_mmd_paths(paths) if callable(split_mmd_paths) else ([], [])
    if motions and not models and isinstance(target_track, dict):
        self._set_mmd_track_motion(target_track, motions[0])
        if hasattr(self, "_flash_status"):
            self._flash_status(f"MMD motion dropped: {motions[0].name}")
        return
    self._add_mmd_asset_to_timeline(paths, start_ms=start_ms)


def _mmd_track_for_motion_attach(self, pos_ms: int) -> dict | None:
    tracks = list(getattr(self, "_mmd_tracks", []) or [])
    if not tracks:
        return None
    for track in reversed(tracks):
        try:
            start = int(track.get("start_ms", 0) or 0)
            end = int(track.get("end_ms", start) or start)
            if start <= int(pos_ms) < end:
                return track
        except Exception:
            continue
    return tracks[-1]


def _find_mmd_track(self, track_id: str) -> dict | None:
    if not track_id:
        return None
    for track in getattr(self, "_mmd_tracks", []) or []:
        if isinstance(track, dict) and str(track.get("id") or "") == str(track_id):
            return track
    return None


def _show_mmd_track_in_workbench(self, track: dict | None) -> None:
    if not isinstance(track, dict):
        return
    self._selected_mmd_track_id = str(track.get("id") or "")
    if hasattr(self, "_set_mmd_row_selection"):
        self._set_mmd_row_selection(self._selected_mmd_track_id)
    panel = getattr(self, "_workbench_panel", None)
    if panel is not None and hasattr(panel, "set_mmd_track"):
        try:
            panel.set_mmd_track(track)
        except Exception:
            pass
    self._node_grade_target = None
    if hasattr(self, "_sync_color_panel"):
        try:
            self._sync_color_panel()
        except Exception:
            pass
    row = self._mmd_lane_for_track(track) if hasattr(self, "_mmd_lane_for_track") else None
    if row is not None:
        row.update()


def _refresh_mmd_track_after_editor_change(self, track: dict, *, register: bool = False, label: str = "edit mmd actor") -> None:
    if not isinstance(track, dict):
        return
    self._selected_mmd_track_id = str(track.get("id") or "")
    self._insert_mmd_actor_lane(track)
    self._sync_mmd_tracks_to_player()
    self._show_mmd_track_in_workbench(track)
    row = self._mmd_lane_for_track(track)
    if row is not None:
        row.update()
    if hasattr(self, "_tracks_host") and hasattr(self, "_timeline_ruler"):
        self._update_tracks_host_width()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    try:
        self._drawing_canvas.update()
    except Exception:
        pass
    self._autosave_dirty = True
    if register:
        try:
            self._register_change(label)
        except Exception:
            pass


def _open_selected_mmd_actor_editor(self) -> None:
    panel = getattr(self, "_workbench_panel", None)
    target = panel.current_target() if panel is not None and hasattr(panel, "current_target") else None
    if target is not None and len(target) >= 2 and target[0] == "mmd" and isinstance(target[1], dict):
        self._open_mmd_actor_editor(str(target[1].get("id") or ""))
        return
    self._open_mmd_actor_editor(str(getattr(self, "_selected_mmd_track_id", "") or ""))


def _open_mmd_actor_editor(self, track_id: str = "") -> dict:
    track = self._find_mmd_track(str(track_id or getattr(self, "_selected_mmd_track_id", "") or ""))
    if track is None:
        tracks = list(getattr(self, "_mmd_tracks", []) or [])
        track = tracks[-1] if tracks else None
    if not isinstance(track, dict):
        if hasattr(self, "_flash_status"):
            self._flash_status("Select or place an MMD actor first")
        return {"opened": False, "reason": "no_mmd_track"}
    try:
        from app.mmd.actor_editor import MMDActorEditorDialog

        dialog = MMDActorEditorDialog(track, self)
        dirty = {"value": False}

        def _on_change(changed_track: dict) -> None:
            dirty["value"] = True
            self._refresh_mmd_track_after_editor_change(changed_track, register=False)

        dialog.track_changed.connect(_on_change)
        dialog.finished.connect(lambda _code: self._register_change("edit mmd actor") if dirty["value"] else None)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._mmd_actor_editor_dialog = dialog
        self._show_mmd_track_in_workbench(track)
        return {"opened": True, "track_id": str(track.get("id") or "")}
    except Exception as exc:
        QMessageBox.warning(self, "MMD Actor Editor", f"Could not open the MMD actor editor.\n\n{type(exc).__name__}: {exc}")
        return {"opened": False, "reason": str(exc)}


def _normalized_mmd_playback_with(track: dict, key: str, value: float) -> dict:
    playback = track.get("playback") if isinstance(track.get("playback"), dict) else {}
    next_playback = dict(playback or {})
    next_playback[str(key)] = float(value)
    try:
        from app.mmd.schema import normalize_playback

        return normalize_playback(next_playback)
    except Exception:
        if key == "physics_rotation_hint_scale":
            next_playback[key] = max(0.0, min(0.30, float(value)))
        elif key == "physics_spring_response":
            next_playback[key] = max(0.15, min(1.50, float(value)))
        return next_playback


def _set_mmd_track_playback_value(self, track: dict, key: str, value: float) -> None:
    if not isinstance(track, dict):
        return
    track["playback"] = self._normalized_mmd_playback_with(track, key, value)
    self._selected_mmd_track_id = str(track.get("id") or "")
    self._sync_mmd_tracks_to_player()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    try:
        self._drawing_canvas.update()
    except Exception:
        pass
    self._autosave_dirty = True


def _set_mmd_track_motion(self, track: dict, motion_path: Path) -> None:
    try:
        from app.mmd.project_tracks import mmd_motion_duration_ms
    except Exception:
        mmd_motion_duration_ms = None
    track["motion_path"] = str(motion_path.expanduser().resolve())
    if callable(mmd_motion_duration_ms):
        duration = int(mmd_motion_duration_ms(motion_path) or 0)
        if duration > 0:
            start_ms = int(track.get("start_ms", 0) or 0)
            track["end_ms"] = max(int(track.get("end_ms", start_ms) or start_ms), start_ms + duration)
            track["duration_ms"] = max(1, int(track["end_ms"]) - start_ms)
    self._insert_mmd_actor_lane(track)
    self._sync_mmd_tracks_to_player()
    self._refresh_player_tracks()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    self._show_mmd_track_in_workbench(track)
    try:
        self._register_change("assign mmd motion")
    except Exception:
        pass
    if hasattr(self, "_flash_status"):
        self._flash_status(f"MMD motion assigned: {motion_path.name}")


def _add_mmd_asset_to_timeline(
    self,
    path_or_paths,
    *,
    start_ms: int | None = None,
) -> dict | None:
    try:
        from app.mmd.project_tracks import (
            DEFAULT_MMD_CLIP_MS,
            create_preview_mmd_track,
            split_mmd_paths,
        )
    except Exception as exc:
        QMessageBox.warning(self, "MMD", f"MMD track support is not available.\n\n{type(exc).__name__}: {exc}")
        return None
    raw_paths = path_or_paths if isinstance(path_or_paths, (list, tuple, set)) else [path_or_paths]
    models, motions = split_mmd_paths(raw_paths)
    current_ms = int(start_ms) if start_ms is not None else int(self._player.position()) if hasattr(self, "_player") else 0
    if not models and motions:
        target = self._mmd_track_for_motion_attach(current_ms)
        if target is not None:
            self._set_mmd_track_motion(target, motions[0])
            return target
        pool_models, _pool_motions = self._mmd_media_pool_paths()
        if len(pool_models) == 1:
            models = [pool_models[0]]
        else:
            QMessageBox.information(
                self,
                "MMD Motion",
                "VMD motion needs an MMD model. Add or select one PMX/PMD model first.",
            )
            return None
    if not models:
        return None
    model_path = models[0]
    motion_path = motions[0] if motions else self._default_mmd_motion_for_model(model_path)
    if hasattr(self, "_media_pool"):
        try:
            self._media_pool.add_path(model_path)
            if motion_path is not None:
                self._media_pool.add_path(motion_path)
        except Exception:
            pass
    project_end = int(self._player.duration()) if hasattr(self, "_player") else 0
    duration_ms = (
        max(DEFAULT_MMD_CLIP_MS, project_end - current_ms)
        if project_end > current_ms
        else DEFAULT_MMD_CLIP_MS
    )
    next_id = int(getattr(self, "_next_mmd_id", 1) or 1)
    self._next_mmd_id = next_id + 1
    track = create_preview_mmd_track(
        model_path,
        track_id=f"mmd_{next_id:03d}",
        start_ms=max(0, int(current_ms)),
        duration_ms=duration_ms,
        motion_path=motion_path,
    )
    self._mmd_tracks.append(track)
    self._insert_mmd_actor_lane(track)
    self._show_mmd_track_in_workbench(track)
    self._sync_mmd_tracks_to_player()
    self._refresh_player_tracks()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    try:
        self._register_change("add mmd model")
    except Exception:
        pass
    if hasattr(self, "_flash_status"):
        motion_name = f" + {motion_path.name}" if motion_path is not None else ""
        self._flash_status(f"MMD model placed: {model_path.name}{motion_name}")
    return track


def _sync_mmd_tracks_to_player(self) -> None:
    player = getattr(self, "_player", None)
    if player is not None and hasattr(player, "set_mmd_tracks"):
        player.set_mmd_tracks(getattr(self, "_mmd_tracks", []) or [])
