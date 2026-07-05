from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QProgressDialog


def _target_live2d_clip_for_mocap(self):
    """Pick the Live2D clip that should receive offline video mocap."""
    for row in getattr(self, "_live2d_lane_rows", []) or []:
        clip = getattr(row, "_selected", None)
        if clip is not None:
            return clip
    pos_ms = 0
    try:
        pos_ms = int(self._player.position())
    except Exception:
        pos_ms = int(getattr(getattr(self, "_player", None), "_position_ms", 0) or 0)
    for track in getattr(self, "_live2d_actor_tracks", []) or []:
        for clip in getattr(track, "clips", []) or []:
            start = int(getattr(clip, "start_ms", 0) or 0)
            end = int(getattr(clip, "end_ms", start) or start)
            if start <= pos_ms < end:
                return clip
    for track in getattr(self, "_live2d_actor_tracks", []) or []:
        clips = list(getattr(track, "clips", []) or [])
        if clips:
            return clips[0]
    return None


def _selected_live2d_clip_for_mapping(self):
    """Return the Live2D clip currently targeted by VTuber mapping UI."""
    return self._target_live2d_clip_for_mocap()


def _refresh_live2d_workbench_selection(self, clip=None) -> None:
    panel = getattr(self, "_workbench_panel", None)
    if panel is None:
        return
    target = clip if clip is not None else self._selected_live2d_clip_for_mapping()
    if target is None:
        return
    owner = self._live2d_owner_track_for_clip(target)
    try:
        panel.set_live2d_clip(owner, target)
    except Exception:
        pass


def _select_live2d_clip_in_lane(self, clip) -> None:
    for row in getattr(self, "_live2d_lane_rows", []) or []:
        if clip in list(getattr(getattr(row, "track", None), "clips", []) or []):
            try:
                self._selected_clips.clear()
                self._broadcast_clip_selection()
            except Exception:
                pass
            try:
                for other in getattr(self, "_live2d_lane_rows", []) or []:
                    if other is not row and getattr(other, "_selected", None) is not None:
                        other._selected = None
                        other.update()
            except Exception:
                pass
            try:
                row._selected = clip
                row.update()
            except Exception:
                pass
            self._refresh_live2d_workbench_selection(clip)
            return


def _open_selected_live2d_editor(self) -> None:
    clip = self._selected_live2d_clip_for_mapping()
    if clip is None:
        self._flash_status("Select a Live2D actor clip first")
        return
    self._on_live2d_clip_dclick(clip)


def _apply_performance_source_to_selected_live2d(self) -> None:
    clip = self._selected_live2d_clip_for_mapping()
    if clip is None:
        self._flash_status("Select a Live2D actor clip first")
        return
    self._on_live2d_clip_performance_source_mapping_requested(clip)
    self._refresh_live2d_workbench_selection(clip)
    studio = getattr(self, "_vtuber_studio_window", None)
    if studio is not None and studio.isVisible():
        studio.update_from_editor(self)


def _live2d_owner_track_for_clip(self, clip):
    for track in getattr(self, "_live2d_actor_tracks", []) or []:
        if clip in list(getattr(track, "clips", []) or []):
            return track
    return None


def _active_video_clips_for_storyboard(self) -> list:
    track = None
    try:
        track = self._active_track()
    except Exception:
        track = None
    clips = list(getattr(track, "clips", []) or []) if track is not None else []
    if clips:
        return clips
    for candidate in getattr(self, "_tracks", []) or []:
        clips = list(getattr(candidate, "clips", []) or [])
        if clips:
            return clips
    return []


def _apply_live2d_motion_storyboard_to_clip(
    self,
    clip,
    *,
    notify: bool = True,
    register_change: bool = True,
    action_source: str = "manual",
) -> dict:
    """Apply cut-aligned authored motions to one Live2D clip."""
    if clip is None:
        if notify:
            self._flash_status("Select a Live2D clip first")
            QMessageBox.information(
                self,
                "Live2D motion storyboard",
                "??꾨씪?몄뿉??Live2D ?대┰???좏깮?????ㅼ떆 ?ㅽ뻾?섏꽭??",
            )
        return {"ok": False, "reason": "missing_clip"}
    if not str(getattr(clip, "model_path", "") or ""):
        if notify:
            self._flash_status("The selected Live2D clip has no model")
            QMessageBox.information(
                self,
                "Live2D motion storyboard",
                "?좏깮??Live2D ?대┰??紐⑤뜽??癒쇱? 吏?뺥븯?몄슂.",
            )
        return {"ok": False, "reason": "missing_model"}
    owner = self._live2d_owner_track_for_clip(clip)
    if owner is None:
        if notify:
            self._flash_status("Live2D ?대┰???몃옓??李얠쓣 ???놁뒿?덈떎")
        return {"ok": False, "reason": "missing_track"}
    try:
        from app.live2d_motion_storyboard import apply_motion_storyboard_to_track

        result = apply_motion_storyboard_to_track(
            owner,
            clip,
            video_clips=self._active_video_clips_for_storyboard(),
        )
    except Exception as exc:
        if notify:
            self._flash_status(f"Live2D motion storyboard failed: {exc}")
            QMessageBox.warning(self, "Live2D motion storyboard", str(exc))
        return {"ok": False, "reason": str(exc)}
    if not bool(result.get("ok")):
        reason = str(result.get("reason") or "failed")
        if notify:
            self._flash_status(f"Live2D motion storyboard failed: {reason}")
            QMessageBox.warning(
                self,
                "Live2D motion storyboard",
                "紐⑤뜽?먯꽌 ?ъ슜?????덈뒗 motion3 紐⑥뀡??李얠? 紐삵뻽?듬땲??\n\n"
                f"?먯씤: {reason}",
            )
        result["ok"] = False
        result["reason"] = reason
        return result
    first = list(getattr(owner, "clips", []) or [None])[0]
    if first is not None:
        self._select_live2d_clip_in_lane(first)
    self._on_live2d_clip_changed()
    self._update_tracks_host_width()
    if hasattr(self, "_player"):
        self._player.refresh_current_frame()
    if register_change:
        self._register_change("Live2D motion storyboard")
    self._record_editor_action(
        "actor.live2d_motion_storyboard.apply",
        created=result.get("created", 0),
        motion_count=result.get("motion_count", 0),
        unique_motions_used=result.get("unique_motions_used", 0),
        source=action_source,
    )
    if notify:
        self._flash_status(
            f"Live2D storyboard: {result.get('created', 0)} clip(s), "
            f"{result.get('unique_motions_used', 0)}/{result.get('motion_count', 0)} motion(s)"
        )
    result["selected_clip"] = first
    return result


def _apply_live2d_motion_storyboard(self) -> None:
    """Split one Live2D clip into video-cut ranges and assign model motions."""
    self._apply_live2d_motion_storyboard_to_clip(
        self._target_live2d_clip_for_mocap(),
        notify=True,
        register_change=True,
        action_source="manual",
    )


def _apply_video_mocap_to_live2d(self) -> None:
    """Analyze a video file and bake its face motion into a Live2D clip."""
    clip = self._target_live2d_clip_for_mocap()
    if clip is None:
        self._flash_status("Select a Live2D clip first or add one to the timeline")
        QMessageBox.information(
            self,
            "Live2D video motion",
            "癒쇱? Live2D ?대┰????꾨씪?몄뿉 ?щ┛ ???대떦 ?대┰???좏깮?섍퀬 ?ㅼ떆 ?ㅽ뻾?섏꽭??",
        )
        return
    path, _ = QFileDialog.getOpenFileName(
        self,
        "Motion source video",
        "",
        "Video Files (*.mp4 *.mov *.mkv *.webm *.avi);;All Files (*)",
    )
    if not path:
        return
    progress_dlg = QProgressDialog("?곸긽?먯꽌 ?쇨뎬 ?吏곸엫??遺꾩꽍?섎뒗 以?..", "Cancel", 0, 100, self)
    progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
    progress_dlg.setMinimumDuration(250)
    progress_dlg.setValue(0)

    def _progress(done: int, total: int) -> None:
        if progress_dlg.wasCanceled():
            raise RuntimeError("cancelled")
        pct = int(max(0, min(100, round(float(done) / max(1.0, float(total)) * 100.0))))
        progress_dlg.setValue(pct)
        QApplication.processEvents()

    try:
        from app.actor_mocap import (
            analyze_video_file_for_live2d_mocap,
            apply_live2d_mocap_payload_to_clip,
            live2d_mocap_user_summary,
        )

        payload = analyze_video_file_for_live2d_mocap(path, progress=_progress)
        mocap_summary = live2d_mocap_user_summary(payload)
        progress_dlg.setValue(100)
        if not bool(payload.get("ok")):
            reason = str(payload.get("warning") or "analysis_failed")
            self._flash_status(f"Live2D motion analysis failed: {reason}")
            QMessageBox.warning(
                self,
                "Live2D video motion",
                f"?곸긽?먯꽌 ?곸슜 媛?ν븳 ?쇨뎬 ?吏곸엫??李얠? 紐삵뻽?듬땲??\n\n?먯씤: {reason}",
            )
            return
        result = apply_live2d_mocap_payload_to_clip(clip, payload)
        if not bool(result.get("ok")):
            reason = str(result.get("reason") or "apply_failed")
            self._flash_status(f"Live2D motion apply failed: {reason}")
            return
        storyboard_result = self._apply_live2d_motion_storyboard_to_clip(
            clip,
            notify=False,
            register_change=False,
            action_source="video_mocap_auto",
        )
        selected_clip = storyboard_result.get("selected_clip") if bool(storyboard_result.get("ok")) else clip
        self._select_live2d_clip_in_lane(selected_clip)
        focus = getattr(self, "_focus_actor_clip_for_edit", None)
        if callable(focus):
            focus(selected_clip, refresh=False)
        if not bool(storyboard_result.get("ok")):
            self._on_live2d_clip_changed()
            self._update_tracks_host_width()
            if hasattr(self, "_player"):
                self._player.refresh_current_frame()
        self._register_change(
            "Live2D video mocap + storyboard"
            if bool(storyboard_result.get("ok"))
            else "Live2D video mocap"
        )
        self._record_editor_action(
            "actor.live2d_video_mocap.apply",
            source_path=path,
            sample_count=result.get("sample_count", 0),
            pos_keys=result.get("pos_keys", 0),
            scale_keys=result.get("scale_keys", 0),
            shot_profile=result.get("shot_profile", "unknown"),
            actor_transform_locked=bool(result.get("actor_transform_locked")),
            auto_storyboard=bool(storyboard_result.get("ok")),
            storyboard_created=storyboard_result.get("created", 0),
            storyboard_motions=storyboard_result.get("unique_motions_used", 0),
        )
        _shot_label = str(result.get("shot_profile") or "unknown")
        _lock_note = " locked transform" if bool(result.get("actor_transform_locked")) else ""
        _mocap_status = str(mocap_summary.get("status_line") or f"{_shot_label}{_lock_note}")
        if bool(storyboard_result.get("ok")):
            self._flash_status(
                f"Live2D motion + storyboard: {result.get('sample_count', 0)} samples, "
                f"{storyboard_result.get('created', 0)} clip(s), "
                f"{storyboard_result.get('unique_motions_used', 0)}/{storyboard_result.get('motion_count', 0)} motion(s), "
                f"{_mocap_status}"
            )
        else:
            self._flash_status(
                f"Live2D motion applied: {result.get('sample_count', 0)} samples, "
                f"{result.get('pos_keys', 0)} position keys, {_mocap_status}; export will bake it"
            )
    except RuntimeError as exc:
        if str(exc) == "cancelled":
            self._flash_status("Live2D motion analysis cancelled")
        else:
            self._flash_status(f"Live2D motion analysis failed: {exc}")
    except Exception as exc:
        self._flash_status(f"Live2D motion analysis failed: {exc}")
        QMessageBox.warning(self, "Live2D video motion", str(exc))
    finally:
        progress_dlg.close()


def _on_live2d_clip_video_mocap_requested(self, clip) -> None:
    self._select_live2d_clip_in_lane(clip)
    focus = getattr(self, "_focus_actor_clip_for_edit", None)
    if callable(focus):
        focus(clip, refresh=False)
    self._apply_video_mocap_to_live2d()


def _on_live2d_clip_storyboard_requested(self, clip) -> None:
    self._select_live2d_clip_in_lane(clip)
    focus = getattr(self, "_focus_actor_clip_for_edit", None)
    if callable(focus):
        focus(clip, refresh=False)
    self._apply_live2d_motion_storyboard_to_clip(
        clip,
        notify=True,
        register_change=True,
        action_source="context_menu",
    )


def _on_live2d_clip_performance_source_mapping_requested(self, clip) -> None:
    """Apply the active input-only Performance Source to a Live2D clip."""
    if clip is None:
        return
    self._select_live2d_clip_in_lane(clip)
    focus = getattr(self, "_focus_actor_clip_for_edit", None)
    if callable(focus):
        focus(clip, refresh=False)
    owner = self._live2d_owner_track_for_clip(clip)
    if owner is None:
        self._flash_status("Live2D clip track not found")
        return
    try:
        clip_index = list(getattr(owner, "clips", []) or []).index(clip)
    except ValueError:
        self._flash_status("Live2D clip is not in its track")
        return
    try:
        target_ms = int(self._player.position())
    except Exception:
        target_ms = int(getattr(clip, "start_ms", 0) or 0)
    try:
        from app.vtuber.performance_source import active_performance_source_at

        active_source = active_performance_source_at(getattr(self, "_tracks", []) or [], target_ms)
    except Exception:
        active_source = {"active": False}
    if not bool(active_source.get("active")):
        self._flash_status("No active Performance Source at this time")
        try:
            QMessageBox.information(
                self,
                "Performance Source Mapping",
                "Add a Performance Source clip at the current timeline time first.",
            )
        except Exception:
            pass
        return
    try:
        from app.actions import build_default_action_registry

        registry = build_default_action_registry(self)
        action = registry.execute(
            "actor.live2d.apply_performance_source",
            {
                "track_id": int(getattr(owner, "id", 0) or 0),
                "clip_index": int(clip_index),
                "time_ms": int(target_ms),
                "analyze_video": True,
                "sample_fps": 10.0,
                "max_samples": 900,
                "apply_mocap": True,
                "apply_framing": True,
                "replace_transform": True,
            },
        ).to_dict()
    except Exception as exc:
        self._flash_status(f"Performance Source mapping failed: {exc}")
        try:
            QMessageBox.warning(self, "Performance Source Mapping", str(exc))
        except Exception:
            pass
        return
    if not bool(action.get("ok")):
        reason = str(action.get("error") or action.get("message") or "mapping failed")
        self._flash_status(f"Performance Source mapping failed: {reason}")
        try:
            QMessageBox.warning(self, "Performance Source Mapping", reason)
        except Exception:
            pass
        return
    result = dict(action.get("result") or {})
    self._select_live2d_clip_in_lane(clip)
    self._on_live2d_clip_changed()
    self._record_editor_action(
        "actor.live2d.performance_source_mapping.apply",
        track_id=int(getattr(owner, "id", 0) or 0),
        clip_index=int(clip_index),
        time_ms=int(target_ms),
        source_path=str(result.get("source_path") or active_source.get("source_path") or ""),
        subject_type=str(result.get("subject_type") or "unknown"),
        program_output=False,
    )
    subject = str(result.get("subject_type") or "unknown")
    mocap = dict(result.get("mocap") or {})
    sample_count = int(mocap.get("sample_count", 0) or 0)
    self._flash_status(
        f"Performance Source mapped to Live2D: {subject}, {sample_count} sample(s)"
    )
