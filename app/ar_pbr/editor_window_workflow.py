from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QMessageBox

from app.ar_pbr import editor_bridge as _ar_pbr_editor_bridge
from app.ar_pbr import editor_gizmo_bridge as _ar_pbr_editor_gizmo_bridge
from app.ar_pbr.actor_lane_row import ArPbrActorLaneRow
from app.media_asset_routing import (
    ar_pbr_paths_from_mime as _shared_ar_pbr_paths_from_mime,
    mmd_paths_from_mime as _shared_mmd_paths_from_mime,
    vrm_avatar_paths_from_mime as _shared_vrm_avatar_paths_from_mime,
)


def _open_vrm_media_in_vtuber_studio(self, path: str) -> None:
    self._use_vrm_media_as_avatar_target(path)
    self._open_vtuber_broadcast_studio()


def _qt_object_valid(self, obj) -> bool:
    if obj is None:
        return False
    try:
        from shiboken6 import isValid

        return bool(isValid(obj))
    except Exception:
        return True


def _remember_ar_pbr_preview_window(self, key: str, preview) -> None:
    _ar_pbr_editor_bridge.remember_preview_window(self, key, preview)


def _schedule_ar_pbr_descriptor_prewarm(self, path: str | Path) -> None:
    try:
        import threading

        key = str(Path(path).expanduser().resolve())
        pending = getattr(self, "_ar_pbr_prewarm_pending", None)
        if not isinstance(pending, set):
            pending = set()
            self._ar_pbr_prewarm_pending = pending
        if key in pending:
            return
        pending.add(key)

        def _run() -> None:
            try:
                from app.preview_acceleration import prewarm_ar_pbr_asset_descriptor

                prewarm_ar_pbr_asset_descriptor(key, max_triangles=120_000)
            finally:
                try:
                    pending.discard(key)
                except Exception:
                    pass

        threading.Thread(target=_run, name="TigerArPbrPrewarm", daemon=True).start()
    except Exception:
        pass


def _open_ar_pbr_asset_preview(self, path: str) -> None:
    try:
        from app.ar_pbr.preview_window import ArPbrAssetPreviewWindow

        asset_path = Path(path).expanduser().resolve()
        key = f"asset:{asset_path}"
        if self._reuse_ar_pbr_preview_window(key) is not None:
            self._flash_status(f"3D preview reused: {asset_path.name}")
            return
        self._schedule_ar_pbr_descriptor_prewarm(asset_path)
        preview = ArPbrAssetPreviewWindow(asset_path, self, max_triangles=120_000)
        self._remember_ar_pbr_preview_window(key, preview)
        preview.show()
        self._flash_status(f"3D preview opened: {asset_path.name}")
    except Exception as exc:
        QMessageBox.warning(
            self,
            "3D Preview",
            f"Could not open the 3D preview.\n\n{type(exc).__name__}: {exc}",
        )


def _ar_pbr_track_lighting_settings(self, track: dict) -> dict:
    return _ar_pbr_editor_bridge.track_lighting_settings(track)


def _apply_ar_pbr_lighting_settings_to_track(self, track: dict, settings: dict) -> None:
    _ar_pbr_editor_bridge.apply_lighting_settings_to_track(track, settings)


def _open_ar_pbr_track_model_view(self, track: dict) -> None:
    try:
        from app.ar_pbr.preview_window import ArPbrAssetPreviewWindow

        asset_path = Path(str(track.get("asset_path") or "")).expanduser().resolve()
        if not asset_path.exists():
            QMessageBox.warning(self, "3D Preview", f"3D asset not found.\n\n{asset_path}")
            return
        track_id = str(track.get("id") or "")
        key = f"track:{track_id}:{asset_path}"
        if self._reuse_ar_pbr_preview_window(key) is not None:
            self._flash_status(f"3D model lighting reused: {asset_path.name}")
            return
        self._schedule_ar_pbr_descriptor_prewarm(asset_path)
        preview = ArPbrAssetPreviewWindow(
            asset_path,
            self,
            initial_lighting=self._ar_pbr_track_lighting_settings(track),
            track_label=track_id,
            max_triangles=120_000,
        )
        self._remember_ar_pbr_preview_window(key, preview)
        dirty_registered = {"value": False}

        def _find_track() -> dict | None:
            for candidate in getattr(self, "_ar_pbr_tracks", []) or []:
                if str(candidate.get("id") or "") == track_id:
                    return candidate
            return None

        def _apply_lighting(settings) -> None:
            current = _find_track()
            if current is None:
                return
            self._apply_ar_pbr_lighting_settings_to_track(current, dict(settings or {}))
            self._selected_ar_pbr_track_id = track_id
            self._sync_ar_pbr_tracks_to_player()
            try:
                self._player.refresh_current_frame()
            except Exception:
                pass
            try:
                self._drawing_canvas.update()
            except Exception:
                pass
            self._autosave_dirty = True
            if not dirty_registered["value"]:
                dirty_registered["value"] = True
                try:
                    self._register_change("adjust ar/pbr lighting")
                except Exception:
                    pass

        preview.settings_changed.connect(_apply_lighting)
        preview.show()
        preview.raise_()
        preview.activateWindow()
        self._flash_status(f"3D model lighting opened: {asset_path.name}")
    except Exception as exc:
        QMessageBox.warning(
            self,
            "3D Preview",
            f"Could not open the placed 3D model view.\n\n{type(exc).__name__}: {exc}",
        )


def _ar_pbr_paths_from_mime(self, mime: QMimeData) -> list[Path]:
    return _shared_ar_pbr_paths_from_mime(mime)


def _vrm_avatar_paths_from_mime(self, mime: QMimeData) -> list[Path]:
    return _shared_vrm_avatar_paths_from_mime(mime)


def _mmd_paths_from_mime(self, mime: QMimeData) -> list[Path]:
    return _shared_mmd_paths_from_mime(mime)


def _ar_pbr_lane_for_track(self, track: dict) -> ArPbrActorLaneRow | None:
    track_id = str(track.get("id") or "") if isinstance(track, dict) else ""
    for row in getattr(self, "_ar_pbr_lane_rows", []) or []:
        row_track = getattr(row, "track", {})
        if isinstance(row_track, dict) and str(row_track.get("id") or "") == track_id:
            return row
    return None


def _insert_ar_pbr_actor_lane(self, track: dict) -> ArPbrActorLaneRow | None:
    if not isinstance(track, dict):
        return None
    existing = self._ar_pbr_lane_for_track(track)
    if existing is not None:
        existing.set_track(track)
        existing.update()
        return existing
    if not hasattr(self, "_tracks_layout") or not hasattr(self, "_timeline_ruler"):
        return None
    row = ArPbrActorLaneRow(track)
    try:
        row.installEventFilter(self)
    except RuntimeError:
        # Unit tests sometimes exercise the workflow against a duck-typed
        # VideoEditorWindow allocated with __new__ rather than QWidget init.
        pass
    row.set_px_per_sec(getattr(self, "_px_per_sec", 52.0))
    row.set_lane_index(len(getattr(self, "_ar_pbr_lane_rows", []) or []) + 1)
    row.track_selected.connect(self._select_ar_pbr_track)
    row.track_changed.connect(self._on_ar_pbr_lane_track_changed)
    row.track_change_committed.connect(
        lambda changed, label: self._refresh_ar_pbr_track_after_lane_change(
            changed,
            register=True,
            label=label,
        )
    )
    row.track_double_clicked.connect(self._open_ar_pbr_track_model_view)
    row.track_delete_requested.connect(self._delete_ar_pbr_track)
    self._ar_pbr_lane_rows.append(row)
    ruler_idx = self._tracks_layout.indexOf(self._timeline_ruler)
    self._tracks_layout.insertWidget(ruler_idx + 1, row)
    self._tracks_layout.invalidate()
    self._tracks_layout.activate()
    return row


def _remove_ar_pbr_actor_lane(self, track: dict) -> None:
    row = self._ar_pbr_lane_for_track(track)
    if row is None:
        return
    try:
        self._tracks_layout.removeWidget(row)
    except Exception:
        pass
    try:
        self._ar_pbr_lane_rows.remove(row)
    except ValueError:
        pass
    row.setParent(None)
    row.deleteLater()
    for idx, candidate in enumerate(getattr(self, "_ar_pbr_lane_rows", []) or [], start=1):
        candidate.set_lane_index(idx)


def _set_ar_pbr_row_selection(self, selected_track_id: str) -> None:
    selected_id = str(selected_track_id or "")
    for row in getattr(self, "_ar_pbr_lane_rows", []) or []:
        row_track = getattr(row, "track", {})
        row_id = str(row_track.get("id") or "") if isinstance(row_track, dict) else ""
        setter = getattr(row, "set_selected", None)
        if callable(setter):
            setter(row_id == selected_id)


def _select_ar_pbr_track(self, track: dict) -> None:
    if not isinstance(track, dict):
        return
    self._selected_ar_pbr_track_id = str(track.get("id") or "")
    self._ar_pbr_gizmo_visible_track_id = ""
    self._end_ar_pbr_depth_interaction_cue()
    self._ar_pbr_gizmo_drag = None
    self._set_ar_pbr_row_selection(self._selected_ar_pbr_track_id)
    try:
        self._drawing_canvas.update()
    except Exception:
        pass
    popout = getattr(self, "_preview_popout", None)
    if popout is not None:
        try:
            popout.overlay_canvas().update()
        except Exception:
            pass
    panel = getattr(self, "_workbench_panel", None)
    if panel is not None and hasattr(panel, "set_ar_pbr_track"):
        try:
            panel.set_ar_pbr_track(track)
        except Exception:
            pass


def _rebuild_ar_pbr_actor_lanes(self) -> None:
    for row in list(getattr(self, "_ar_pbr_lane_rows", []) or []):
        try:
            self._tracks_layout.removeWidget(row)
        except Exception:
            pass
        row.setParent(None)
        row.deleteLater()
    self._ar_pbr_lane_rows = []
    for track in getattr(self, "_ar_pbr_tracks", []) or []:
        self._insert_ar_pbr_actor_lane(track)
    if hasattr(self, "_tracks_host") and hasattr(self, "_timeline_ruler"):
        self._update_tracks_host_width()


def _on_ar_pbr_lane_track_changed(self, track: dict) -> None:
    if not isinstance(track, dict):
        return
    self._select_ar_pbr_track(track)
    self._sync_ar_pbr_tracks_to_player()
    if hasattr(self, "_tracks_host") and hasattr(self, "_timeline_ruler"):
        self._update_tracks_host_width()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    self._autosave_dirty = True


def _refresh_ar_pbr_track_after_lane_change(
    self,
    track: dict,
    *,
    register: bool = False,
    label: str = "edit 3d object",
) -> None:
    if not isinstance(track, dict):
        return
    self._sync_ar_pbr_tracks_to_player()
    self._refresh_player_tracks()
    row = self._ar_pbr_lane_for_track(track)
    if row is not None:
        row.update()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    if register:
        self._register_change(label)


def _delete_ar_pbr_track(self, track: dict) -> None:
    if not isinstance(track, dict):
        return
    track_id = str(track.get("id") or "")
    self._ar_pbr_tracks = [
        row for row in getattr(self, "_ar_pbr_tracks", []) or []
        if str(row.get("id") or "") != track_id
    ]
    if str(getattr(self, "_selected_ar_pbr_track_id", "") or "") == track_id:
        self._selected_ar_pbr_track_id = ""
    if str(getattr(self, "_ar_pbr_gizmo_visible_track_id", "") or "") == track_id:
        self._ar_pbr_gizmo_visible_track_id = ""
        self._ar_pbr_gizmo_drag = None
    restore = getattr(self, "_ar_pbr_depth_cue_restore", None)
    if isinstance(restore, dict):
        restore.pop(track_id, None)
    self._remove_ar_pbr_actor_lane(track)
    self._sync_ar_pbr_tracks_to_player()
    self._refresh_player_tracks()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass
    self._register_change("delete 3d object")


def _refresh_preview_canvas_interaction_hook(self) -> None:
    canvas = getattr(self, "_drawing_canvas", None)
    if canvas is None:
        return
    ar_tracks = getattr(self, "_ar_pbr_tracks", []) or []
    if not ar_tracks:
        self._selected_ar_pbr_track_id = ""
        self._ar_pbr_gizmo_visible_track_id = ""
        self._ar_pbr_gizmo_drag = None
        self._ar_pbr_depth_cue_restore = {}
    dlg = getattr(self, "_screenstudio_polish_dialog", None)
    screenstudio_active = dlg is not None
    wants_hook = bool(ar_tracks) or screenstudio_active
    try:
        canvas.set_interaction_hook(self._preview_canvas_interaction if wants_hook else None)
    except Exception:
        pass
    self._refresh_preview_popout_overlay_hooks()


def _refresh_preview_popout_overlay_hooks(self) -> None:
    popout = getattr(self, "_preview_popout", None)
    if popout is None:
        return
    wants_ar = bool(getattr(self, "_ar_pbr_tracks", []) or [])
    try:
        popout.set_overlay_hooks(
            self._paint_ar_pbr_gizmo_overlay if wants_ar else None,
            self._preview_popout_canvas_interaction if wants_ar else None,
        )
    except Exception:
        pass


def _preview_canvas_interaction(self, phase: str, nx: float, ny: float, event: QMouseEvent) -> bool:
    if self._ar_pbr_gizmo_interaction(phase, nx, ny, event):
        return True
    try:
        return bool(self._screenstudio_candidate_interaction(phase, nx, ny, event))
    except Exception:
        return False


def _preview_popout_canvas_interaction(self, phase: str, nx: float, ny: float, event: QMouseEvent) -> bool:
    popout = getattr(self, "_preview_popout", None)
    if popout is None:
        return False
    try:
        canvas = popout.overlay_canvas()
    except Exception:
        canvas = None
    return self._ar_pbr_gizmo_interaction_for_canvas(canvas, phase, nx, ny, event)


def _paint_preview_canvas_overlay(self, painter: QPainter, canvas_w: int, canvas_h: int) -> None:
    try:
        self._paint_comparison_canvas_overlay(painter, canvas_w, canvas_h)
    except Exception:
        pass
    try:
        self._paint_screenstudio_candidate_canvas_overlay(painter, canvas_w, canvas_h)
    except Exception:
        pass
    try:
        self._paint_ar_pbr_gizmo_overlay(painter, canvas_w, canvas_h)
    except Exception:
        pass


def _paint_comparison_canvas_overlay(self, painter: QPainter, canvas_w: int, canvas_h: int) -> None:
    track = self._active_track() if hasattr(self, "_active_track") else None
    mode = str(getattr(track, "preview_color_compare_mode", "") or "").casefold()
    if mode not in {"before", "split"}:
        return
    w = max(1, int(canvas_w))
    h = max(1, int(canvas_h))
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if mode == "split":
        split_x = w // 2
        painter.setPen(QPen(QColor(255, 255, 255, 210), 1.35))
        painter.drawLine(split_x, 10, split_x, h - 10)

    labels_enabled = bool(getattr(track, "preview_compare_labels_enabled", True))
    if labels_enabled:
        label_font = QFont("Segoe UI Variable", 9)
        label_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(label_font)

        def _badge(text: str, x: int, y: int) -> None:
            fm = QFontMetrics(label_font)
            bw = max(64, fm.horizontalAdvance(text) + 18)
            bh = 22
            rect = QRect(max(8, int(x)), max(8, int(y)), bw, bh)
            painter.setPen(QPen(QColor(255, 255, 255, 46), 1))
            painter.setBrush(QColor(7, 9, 13, 205))
            painter.drawRoundedRect(rect, 6, 6)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        if mode == "split":
            _badge("Before", 12, 12)
            _badge("After", w // 2 + 12, 12)
        else:
            _badge("Before", 12, 12)
    painter.restore()


def _refresh_ar_pbr_preview_after_gizmo_change(self) -> None:
    _ar_pbr_editor_gizmo_bridge.refresh_preview_after_gizmo_change(self)


def _begin_ar_pbr_depth_interaction_cue(self, track: dict) -> None:
    _ar_pbr_editor_gizmo_bridge.begin_depth_interaction_cue(self, track)


def _end_ar_pbr_depth_interaction_cue(self, track_id: str = "") -> None:
    _ar_pbr_editor_gizmo_bridge.end_depth_interaction_cue(self, track_id)


def _ar_pbr_gizmo_interaction(self, phase: str, nx: float, ny: float, event: QMouseEvent) -> bool:
    return self._ar_pbr_gizmo_interaction_for_canvas(
        getattr(self, "_drawing_canvas", None),
        phase,
        nx,
        ny,
        event,
    )


def _paint_ar_pbr_gizmo_overlay(self, painter: QPainter, canvas_w: int, canvas_h: int) -> None:
    _ar_pbr_editor_gizmo_bridge.paint_gizmo_overlay(self, painter, canvas_w, canvas_h)


def _add_ar_pbr_asset_to_preview(
    self,
    path: str | Path,
    *,
    image_point: tuple[float, float] | None = None,
    start_ms: int | None = None,
) -> dict | None:
    try:
        from app.ar_pbr.project_tracks import create_preview_ar_track, is_ar_pbr_asset_path

        asset_path = Path(path).expanduser().resolve()
        if asset_path.suffix.lower() == ".vrm":
            self._open_vrm_media_in_vtuber_studio(str(asset_path))
            return None
        if not is_ar_pbr_asset_path(asset_path):
            return None
        if hasattr(self, "_media_pool"):
            try:
                self._media_pool.add_path(asset_path)
            except Exception:
                pass
        placement_start_ms = (
            max(0, int(start_ms))
            if start_ms is not None
            else int(self._player.position()) if hasattr(self, "_player") else 0
        )
        project_end = int(self._player.duration()) if hasattr(self, "_player") else 0
        duration_ms = (
            max(10_000, project_end - placement_start_ms)
            if project_end > placement_start_ms
            else 10_000
        )
        next_id = int(getattr(self, "_next_ar_pbr_id", 1) or 1)
        self._next_ar_pbr_id = next_id + 1
        track = create_preview_ar_track(
            asset_path,
            track_id=f"ar_pbr_{next_id:03d}",
            start_ms=placement_start_ms,
            duration_ms=duration_ms,
            image_point=image_point,
        )
        self._ar_pbr_tracks.append(track)
        self._selected_ar_pbr_track_id = str(track.get("id") or "")
        self._ar_pbr_gizmo_visible_track_id = ""
        self._insert_ar_pbr_actor_lane(track)
        self._set_ar_pbr_row_selection(self._selected_ar_pbr_track_id)
        panel = getattr(self, "_workbench_panel", None)
        if panel is not None and hasattr(panel, "set_ar_pbr_track"):
            try:
                panel.set_ar_pbr_track(track)
            except Exception:
                pass
        self._promote_ar_pbr_track_to_scene_anchor(track, reason="add")
        self._sync_ar_pbr_tracks_to_player()
        self._refresh_preview_canvas_interaction_hook()
        self._refresh_player_tracks()
        if hasattr(self, "_player"):
            self._player.refresh_current_frame()
        try:
            self._drawing_canvas.update()
        except Exception:
            pass
        self._register_change("add ar/pbr asset")
        self._flash_status(f"3D model placed in preview: {asset_path.name}")
        return track
    except Exception as exc:
        QMessageBox.warning(
            self,
            "3D Placement",
            f"Could not place the 3D model in the preview.\n\n{type(exc).__name__}: {exc}",
        )
        return None
