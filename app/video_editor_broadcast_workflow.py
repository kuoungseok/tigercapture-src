from __future__ import annotations

from pathlib import Path

from app.simple_video_player import PlayerState
from app.video_editor_popouts import (
    VTuberBroadcastStudioWindow,
    _BroadcastProjectAudioBusMixdownThread,
)


def _open_vtuber_broadcast_studio(self) -> None:
    studio = getattr(self, "_vtuber_studio_window", None)
    if studio is None:
        studio = VTuberBroadcastStudioWindow(self)
        studio.closed.connect(lambda: setattr(self, "_vtuber_studio_window", None))
        studio.apply_avatar_mapping_requested.connect(self._apply_performance_source_to_selected_avatar)
        studio.start_live_target_requested.connect(self._start_broadcast_live_target)
        studio.stop_live_target_requested.connect(self._stop_broadcast_live_target)
        self._vtuber_studio_window = studio
    studio.update_from_editor(self)
    studio.show()
    studio.raise_()
    studio.activateWindow()
    self._record_editor_action("vtuber.broadcast_studio.open")


def _broadcast_output_canvas(self, target_payload: dict[str, object] | None = None) -> dict[str, object]:
    width = 1920
    height = 1080
    try:
        size = getattr(self, "_preview_gl_frame_size", None)
        if isinstance(size, tuple) and len(size) >= 2 and int(size[0]) > 0 and int(size[1]) > 0:
            width, height = int(size[0]), int(size[1])
        else:
            export_res = getattr(self, "_export_resolution", None)
            if isinstance(export_res, tuple) and len(export_res) >= 2:
                width, height = int(export_res[0]), int(export_res[1])
    except Exception:
        width, height = 1920, 1080
    try:
        fps = float(getattr(self, "_export_fps", 30.0) or 30.0)
    except Exception:
        fps = 30.0
    base = {"width": max(1, width), "height": max(1, height), "fps": max(1.0, fps)}
    if isinstance(target_payload, dict) and target_payload:
        try:
            from app.broadcast_output import recommended_canvas_for_live_target

            return recommended_canvas_for_live_target(target_payload, base)
        except Exception:
            return base
    return base


def _broadcast_output_session_status(self) -> dict[str, object]:
    session = getattr(self, "_broadcast_output_session", None)
    if session is None:
        return {"schema": "tigerstudio.broadcast.output_session_status.v1", "state": "idle", "active": False}
    try:
        return dict(session.status())
    except Exception as exc:
        return {"schema": "tigerstudio.broadcast.output_session_status.v1", "state": "error", "active": False, "last_error": str(exc)}


def _start_broadcast_live_target(self, payload=None) -> dict[str, object]:
    target_payload = dict(payload or {})
    try:
        self._stop_broadcast_live_target(notify=False)
        from app.broadcast_output_session import BroadcastOutputSession

        settings = getattr(self, "_project_settings", {}) or {}
        broadcast = settings.get("broadcast_output") if isinstance(settings, dict) else {}
        live_settings = dict(broadcast.get("live_target") if isinstance(broadcast, dict) and isinstance(broadcast.get("live_target"), dict) else {})
        live_settings.update(target_payload)
        preparing_status = self._start_broadcast_audio_mixdown_if_needed(live_settings)
        if preparing_status is not None:
            return preparing_status
        live_settings = self._prepare_broadcast_live_target_audio(live_settings)
        session = BroadcastOutputSession(live_settings, self._broadcast_output_canvas(live_settings))
        status = session.start()
        self._broadcast_output_session = session
        self._broadcast_output_last_status_frame = 0
        self._broadcast_output_error_reported = False
        self._update_vtuber_studio_live_session_status(status)
        if status.get("state") == "running":
            self._flash_status("Live Target started; playback frames are feeding Program Output")
            try:
                if self._player.state() is not PlayerState.PLAYING:
                    self._player.play()
            except Exception:
                pass
        elif status.get("state") == "manual_output":
            self._flash_status("Live Target ready; share the Program Output window or virtual camera")
        else:
            self._flash_status(f"Live Target not ready: {status.get('last_error') or 'check settings'}")
        self._record_editor_action(
            "broadcast.live_target.start",
            target_id=str(live_settings.get("target_id") or ""),
            state=str(status.get("state") or ""),
            output_kind=str(status.get("output_kind") or ""),
        )
        return status
    except Exception as exc:
        status = {"schema": "tigerstudio.broadcast.output_session_status.v1", "state": "error", "active": False, "last_error": str(exc)}
        self._update_vtuber_studio_live_session_status(status)
        try:
            self._flash_status(f"Live Target failed: {exc}")
        except Exception:
            pass
        return status


def _start_broadcast_audio_mixdown_if_needed(self, live_settings: dict[str, object]) -> dict[str, object] | None:
    audio_kind = str(live_settings.get("audio_source_kind") or live_settings.get("source_kind") or "").strip()
    if audio_kind != "project_audio_bus" or bool(live_settings.get("_project_audio_bus_prepared")):
        return None
    thread = getattr(self, "_broadcast_audio_mixdown_thread", None)
    if thread is not None and thread.isRunning():
        status = {
            "schema": "tigerstudio.broadcast.output_session_status.v1",
            "state": "preparing_audio",
            "active": True,
            "last_error": "",
        }
        self._update_vtuber_studio_live_session_status(status)
        return status
    import copy
    import tempfile

    try:
        from app.broadcast_audio_mix import project_audio_bus_extent_ms

        tracks = copy.deepcopy(list(getattr(self, "_audio_tracks", []) or []))
        player = getattr(self, "_player", None)
        duration_ms = int(player.duration()) if player is not None and hasattr(player, "duration") else 0
        duration_ms = max(duration_ms, int(project_audio_bus_extent_ms(tracks)), 1000)
        out_path = Path(tempfile.gettempdir()) / "tigercapture_live_project_audio_bus.wav"
        pending = dict(live_settings)
        self._pending_broadcast_live_settings = pending
        mix_thread = _BroadcastProjectAudioBusMixdownThread(
            tracks=tracks,
            output_path=out_path,
            duration_ms=duration_ms,
            sample_rate=48000,
            channels=2,
            parent=self,
        )
        mix_thread.finished_with_diag.connect(self._on_broadcast_audio_mixdown_finished)
        mix_thread.progress_changed.connect(self._on_broadcast_audio_mixdown_progress)
        mix_thread.finished.connect(mix_thread.deleteLater)
        self._broadcast_audio_mixdown_thread = mix_thread
        mix_thread.start()
        status = {
            "schema": "tigerstudio.broadcast.output_session_status.v1",
            "state": "preparing_audio",
            "active": True,
            "target_id": str(live_settings.get("target_id") or ""),
            "output_kind": "",
            "last_error": "",
            "recovery_action": "preparing_project_audio_bus",
        }
        self._update_vtuber_studio_live_session_status(status)
        try:
            self._flash_status("Preparing project audio bus for Live Target...")
        except Exception:
            pass
        return status
    except Exception as exc:
        raise RuntimeError(f"Project audio bus mixdown failed: {exc}") from exc


def _on_broadcast_audio_mixdown_progress(self, progress_obj) -> None:
    progress = dict(progress_obj or {})
    self._broadcast_output_last_audio_mixdown_progress = progress
    percent = max(0.0, min(100.0, float(progress.get("progress") or 0.0) * 100.0))
    status = {
        "schema": "tigerstudio.broadcast.output_session_status.v1",
        "state": "preparing_audio",
        "active": True,
        "target_id": "",
        "output_kind": "",
        "audio_mixdown_progress": percent,
        "recovery_action": "preparing_project_audio_bus",
        "last_error": "",
    }
    self._update_vtuber_studio_live_session_status(status)


def _on_broadcast_audio_mixdown_finished(self, diag_obj) -> None:
    diag = dict(diag_obj or {})
    self._broadcast_output_last_audio_mixdown = diag
    self._broadcast_audio_mixdown_thread = None
    pending = getattr(self, "_pending_broadcast_live_settings", None)
    self._pending_broadcast_live_settings = None
    if not isinstance(pending, dict):
        return
    if not bool(diag.get("ok")):
        err = str(diag.get("error") or diag.get("stderr_tail") or "ffmpeg audio mixdown failed")
        status = {
            "schema": "tigerstudio.broadcast.output_session_status.v1",
            "state": "error",
            "active": False,
            "last_error": f"Project audio bus mixdown failed: {err}",
            "recovery_action": "check_project_audio_tracks",
        }
        self._update_vtuber_studio_live_session_status(status)
        try:
            self._flash_status(status["last_error"])
        except Exception:
            pass
        return
    audio_path = str(diag.get("output_path") or "")
    prepared = dict(pending)
    prepared["include_audio"] = True
    prepared["audio_source_kind"] = "project_audio_bus"
    prepared["audio_file"] = audio_path
    prepared["file_path"] = audio_path
    prepared["_project_audio_bus_prepared"] = True
    self._start_broadcast_live_target(prepared)


def _prepare_broadcast_live_target_audio(self, live_settings: dict[str, object]) -> dict[str, object]:
    """Materialize project timeline audio when the live target asks for it."""
    audio_kind = str(live_settings.get("audio_source_kind") or live_settings.get("source_kind") or "").strip()
    if audio_kind != "project_audio_bus" or bool(live_settings.get("_project_audio_bus_prepared")):
        return live_settings
    import tempfile

    prepared = dict(live_settings)
    try:
        from app.broadcast_audio_mix import (
            project_audio_bus_extent_ms,
            render_project_audio_bus_mixdown,
        )

        tracks = list(getattr(self, "_audio_tracks", []) or [])
        player = getattr(self, "_player", None)
        duration_ms = int(player.duration()) if player is not None and hasattr(player, "duration") else 0
        duration_ms = max(duration_ms, int(project_audio_bus_extent_ms(tracks)), 1000)
        out_path = Path(tempfile.gettempdir()) / "tigercapture_live_project_audio_bus.wav"
        try:
            self._flash_status("Preparing project audio bus for Live Target...")
        except Exception:
            pass
        diag = render_project_audio_bus_mixdown(
            tracks,
            out_path,
            duration_ms=duration_ms,
            sample_rate=48000,
            channels=2,
            timeout_s=180.0,
        )
        self._broadcast_output_last_audio_mixdown = diag
        if not bool(diag.get("ok")):
            err = str(diag.get("error") or diag.get("stderr_tail") or "ffmpeg audio mixdown failed")
            raise RuntimeError(err)
        prepared["include_audio"] = True
        prepared["audio_source_kind"] = "project_audio_bus"
        prepared["audio_file"] = str(out_path)
        prepared["file_path"] = str(out_path)
        return prepared
    except Exception as exc:
        raise RuntimeError(f"Project audio bus mixdown failed: {exc}") from exc


def _stop_broadcast_live_target(self, *, notify: bool = True) -> dict[str, object]:
    self._pending_broadcast_live_settings = None
    thread = getattr(self, "_broadcast_audio_mixdown_thread", None)
    if thread is not None and thread.isRunning():
        try:
            thread.requestInterruption()
        except Exception:
            pass
    session = getattr(self, "_broadcast_output_session", None)
    if session is None:
        status = {"schema": "tigerstudio.broadcast.output_session_status.v1", "state": "idle", "active": False}
    else:
        try:
            status = dict(session.stop())
        except Exception as exc:
            status = {"schema": "tigerstudio.broadcast.output_session_status.v1", "state": "error", "active": False, "last_error": str(exc)}
        self._broadcast_output_session = None
    self._update_vtuber_studio_live_session_status(status)
    if notify:
        try:
            frames = int(status.get("frames_written") or 0)
            self._flash_status(f"Live Target stopped ({frames} frames)")
        except Exception:
            pass
        self._record_editor_action("broadcast.live_target.stop", state=str(status.get("state") or ""))
    return status


def _feed_broadcast_output_frame(self, rgb) -> None:
    session = getattr(self, "_broadcast_output_session", None)
    if session is None:
        return
    try:
        status = session.status()
        if status.get("state") != "running":
            return
        status = session.write_frame(rgb)
        if status.get("state") == "error":
            self._update_vtuber_studio_live_session_status(status)
            if not getattr(self, "_broadcast_output_error_reported", False):
                self._broadcast_output_error_reported = True
                self._flash_status(f"Live Target error: {status.get('last_error') or 'frame write failed'}")
            return
        frame_count = int(status.get("frames_written") or 0)
        last = int(getattr(self, "_broadcast_output_last_status_frame", 0) or 0)
        if frame_count <= 1 or frame_count - last >= 30:
            self._broadcast_output_last_status_frame = frame_count
            self._update_vtuber_studio_live_session_status(status)
    except Exception as exc:
        if not getattr(self, "_broadcast_output_error_reported", False):
            self._broadcast_output_error_reported = True
            try:
                self._flash_status(f"Live Target error: {exc}")
            except Exception:
                pass


def _update_vtuber_studio_live_session_status(self, status: dict[str, object]) -> None:
    studio = getattr(self, "_vtuber_studio_window", None)
    if studio is not None and hasattr(studio, "update_live_session_status"):
        try:
            studio.update_live_session_status(status)
        except Exception:
            pass
