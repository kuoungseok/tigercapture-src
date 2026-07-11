"""Shared capture, owner, media import, and editor UI helper methods."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import tempfile
import time
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


class _ScreenGrabTarget:
    """Small grab()-compatible adapter for full-screen capture actions."""

    def __init__(self, *, screen_index: int = 0) -> None:
        self._screen_index = max(0, _int(screen_index, 0))

    def grab(self) -> Any:
        from PySide6.QtGui import QGuiApplication

        screens = list(QGuiApplication.screens() or [])
        screen = screens[min(self._screen_index, len(screens) - 1)] if screens else QGuiApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("no screen is available for capture")
        return screen.grabWindow(0)


class CoreHelperMixin:
    """Private helpers shared by action adapter domain mixins."""

    def _capture_target_widget(self, owner: Any, target: str = "editor") -> Any:
        target_text = str(target or "editor").strip().lower().replace("-", "_").replace(" ", "_")
        if target_text in {"", "editor", "root", "window", "main", "studio", "tiger_studio"}:
            return owner
        if target_text in {"screen", "display", "desktop", "monitor", "full_screen", "fullscreen"}:
            return _ScreenGrabTarget()

        aliases: dict[str, tuple[str, ...]] = {
            "viewer": (
                "_preview_gl",
                "_preview_label",
                "_viewer_column",
                "_preview_panel",
                "_preview_container",
            ),
            "preview": (
                "_preview_gl",
                "_preview_label",
                "_viewer_column",
                "_preview_panel",
                "_preview_container",
            ),
            "program": (
                "_preview_gl",
                "_preview_label",
                "_viewer_column",
                "_preview_panel",
                "_preview_container",
            ),
            "program_output": (
                "_preview_gl",
                "_preview_label",
                "_viewer_column",
                "_preview_panel",
                "_preview_container",
            ),
            "timeline": (
                "_timeline_section_host",
                "_timeline_scroll",
                "_tracks_host",
                "_timeline_ruler",
            ),
            "tracks": (
                "_tracks_host",
                "_timeline_section_host",
                "_timeline_scroll",
            ),
            "media": (
                "_media_pool",
                "_left_dock_host",
            ),
            "media_pool": (
                "_media_pool",
                "_left_dock_host",
            ),
            "project_bin": (
                "_media_pool",
                "_left_dock_host",
            ),
            "workbench": (
                "_workbench_panel",
                "_right_dock_host",
            ),
            "inspector": (
                "_workbench_panel",
                "_right_dock_host",
            ),
            "right_dock": (
                "_right_dock_host",
                "_workbench_panel",
            ),
            "left_dock": (
                "_left_dock_host",
                "_media_pool",
            ),
            "color": (
                "_color_workbench_panel",
                "_compact_color_dock",
                "_workbench_panel",
            ),
            "color_grading": (
                "_color_workbench_panel",
                "_compact_color_dock",
                "_workbench_panel",
            ),
            "audio": (
                "_audio_workspace_panel",
                "_audio_mixer_panel",
                "_workbench_panel",
            ),
            "sound_editor": (
                "_audio_workspace_panel",
                "_audio_mixer_panel",
                "_workbench_panel",
            ),
            "ai": (
                "_ai_command_dock",
                "_ai_command_chat_log",
                "_ai_command_input",
            ),
            "render": (
                "_render_queue_section_host",
                "_right_dock_host",
            ),
            "render_queue": (
                "_render_queue_section_host",
                "_right_dock_host",
            ),
        }

        names = aliases.get(target_text, ())
        if not names:
            names = (target_text, f"_{target_text}")
        for name in names:
            candidate = getattr(owner, name, None)
            grab = getattr(candidate, "grab", None)
            if candidate is not None and callable(grab):
                return candidate
        direct = getattr(owner, target_text, None)
        if direct is not None and callable(getattr(direct, "grab", None)):
            return direct
        return owner

    def capture_target_catalog(self) -> dict[str, Any]:
        owner = self.owner
        targets = [
            {"target": "editor", "description": "Full Tiger Studio editor window."},
            {"target": "viewer", "description": "Current Program/Viewer preview surface."},
            {"target": "timeline", "description": "Timeline ruler, tracks, and clip area."},
            {"target": "media_pool", "description": "Left Media Pool and project-bin surface."},
            {"target": "workbench", "description": "Right Workbench or inspector surface."},
            {"target": "color", "description": "Color grading workbench surface."},
            {"target": "audio", "description": "Audio or Sound Editor workbench surface."},
            {"target": "screen", "description": "Current desktop display for diagnostics."},
        ]
        if owner is not None:
            for row in targets:
                try:
                    widget = self._capture_target_widget(owner, str(row["target"]))
                    row["available"] = callable(getattr(widget, "grab", None))
                    row["resolved_type"] = type(widget).__name__
                except Exception:
                    row["available"] = False
                    row["resolved_type"] = ""
        return {
            "schema": "tigerstudio.capture.targets.v1",
            "ui_added": False,
            "mcp_ready": True,
            "targets": targets,
        }


    def _broadcast_selection(self) -> None:
        owner = self.owner
        method = getattr(owner, "_broadcast_clip_selection", None) if owner is not None else None
        if callable(method):
            try:
                method()
            except Exception:
                pass

    def _capture_gif_from_widget(self, *, path: str = "", target: str = "editor", duration_ms: int = 3000, fps: int = 8) -> dict[str, Any]:
        owner = self._require_owner()
        widget = self._capture_target_widget(owner, target)
        grab = getattr(widget, "grab", None)
        if not callable(grab):
            raise RuntimeError("capture.gif requires a live capture backend or Qt widget with grab()")
        out = Path(str(path or "debugCapture/action_capture.gif")).expanduser()
        if out.suffix.lower() != ".gif":
            out = out.with_suffix(".gif")
        out.parent.mkdir(parents=True, exist_ok=True)
        fps_value = max(1, min(30, _int(fps, 8)))
        duration_value = max(1, _int(duration_ms, 3000))
        frame_delay_ms = max(20, int(round(1000 / fps_value)))
        frame_count = max(1, min(180, int(round((duration_value / 1000.0) * fps_value))))
        try:
            from PIL import Image
        except Exception as exc:
            raise RuntimeError("capture.gif fallback requires Pillow") from exc
        frames: list[Any] = []
        with tempfile.TemporaryDirectory(prefix="tigercapture_action_gif_") as tmp:
            tmpdir = Path(tmp)
            for index in range(frame_count):
                pixmap = grab()
                frame_path = tmpdir / f"frame_{index:04d}.png"
                if not pixmap.save(str(frame_path)):
                    raise RuntimeError(f"failed to save GIF frame: {index}")
                with Image.open(frame_path) as img:
                    frames.append(img.convert("P", palette=Image.ADAPTIVE).copy())
                if index + 1 < frame_count:
                    self._process_capture_events()
                    time.sleep(frame_delay_ms / 1000.0)
        if not frames:
            raise RuntimeError("capture.gif produced no frames")
        frames[0].save(
            out,
            save_all=True,
            append_images=frames[1:],
            duration=frame_delay_ms,
            loop=0,
        )
        return {
            "path": str(out.resolve()),
            "target": str(target or "editor"),
            "duration_ms": duration_value,
            "fps": fps_value,
            "frames": len(frames),
            "backend": "qt_grab_fallback",
        }

    def _process_capture_events(self) -> None:
        try:
            from PySide6.QtCore import QCoreApplication

            app = QCoreApplication.instance()
            if app is not None:
                app.processEvents()
        except Exception:
            pass

    def _require_owner(self) -> Any:
        if self.owner is None:
            raise RuntimeError("no editor owner")
        return self.owner

    def _register_media_path(self, media_path: Path) -> bool:
        owner = self._require_owner()
        pool = getattr(owner, "_media_pool", None)
        if pool is not None and hasattr(pool, "add_path"):
            return bool(pool.add_path(media_path))
        imported = list(getattr(owner, "_action_imported_media", []) or [])
        text = str(media_path.resolve())
        if text not in imported:
            imported.append(text)
            setattr(owner, "_action_imported_media", imported)
            return True
        return False

    def _performance_source_clip_count(self) -> int:
        try:
            from app.vtuber.performance_source import is_performance_source_track
        except Exception:
            is_performance_source_track = lambda track: bool(getattr(track, "performance_source", False))
        total = 0
        for track in getattr(self.owner, "_tracks", []) or []:
            if is_performance_source_track(track):
                total += len(getattr(track, "clips", []) or [])
        return total

    def _owner_uses_legacy_video_editor_tracks(self) -> bool:
        owner = self.owner
        return bool(
            owner is not None
            and callable(getattr(owner, "_insert_track_widget", None))
            and hasattr(owner, "_track_rows")
        )

    def _next_editor_track_id(self, tracks: Sequence[Any]) -> int:
        owner = self._require_owner()
        current = _int(getattr(owner, "_next_track_id", 0), 0)
        used = {_int(getattr(track, "id", -1), -1) for track in tracks}
        if current <= 0 or current in used:
            current = self._next_track_id(tracks)
        try:
            setattr(owner, "_next_track_id", max(current + 1, _int(getattr(owner, "_next_track_id", 0), 0)))
        except Exception:
            pass
        return current

    def _create_editor_video_track_from_media(
        self,
        media_path: Path,
        *,
        start_ms: int,
        duration_ms: int,
    ) -> tuple[Any, Any | None]:
        """Create a real VideoEditorWindow track for live UI captures.

        The headless action model uses ``timeline_model.VideoTrack``.  The
        interactive editor still has a legacy ``video_track_legacy.VideoTrack``
        surface with widgets, thumbnails, and several direct ``source_path``
        reads.  Review automation must use that real surface so screenshots
        show an actual imported timeline instead of a detached data-only track.
        """
        owner = self._require_owner()
        from app.video_track_legacy import VideoTrack, _ensure_video_clips

        tracks = list(getattr(owner, "_tracks", []) or [])
        new_id = self._next_editor_track_id(tracks)
        track = VideoTrack(
            id=new_id,
            source_path=media_path.resolve(),
            duration_ms=max(1, _int(duration_ms, 1)),
            offset_ms=max(0, _int(start_ms, 0)),
        )
        _ensure_video_clips(track, force=True)
        tracks.append(track)
        setattr(owner, "_tracks", tracks)

        insert = getattr(owner, "_insert_track_widget", None)
        if callable(insert):
            insert(track)
        thumb = getattr(owner, "_start_thumbnail_extraction", None)
        if callable(thumb):
            try:
                thumb(track)
            except Exception:
                pass
        set_active = getattr(owner, "_set_active_track", None)
        if callable(set_active):
            try:
                set_active(new_id)
            except Exception:
                pass
        refresh = getattr(owner, "_refresh_player_tracks", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass
        row = getattr(owner, "_track_rows", {}).get(new_id) if hasattr(owner, "_track_rows") else None
        if row is not None and hasattr(row, "update"):
            row.update()
        clips = list(getattr(track, "clips", []) or [])
        return track, clips[0] if clips else None

    def _resolve_video_clip_for_audio_extract(
        self,
        *,
        track_id: int | None = None,
        clip_id: int | None = None,
    ) -> tuple[Any, Any]:
        owner = self._require_owner()
        if track_id is not None and clip_id is not None:
            return self._video_track_and_clip(_int(track_id), _int(clip_id))
        if track_id is not None:
            track = self._video_track(_int(track_id))
            clips = list(getattr(track, "clips", []) or [])
            if clip_id is not None:
                for clip in clips:
                    if _int(getattr(clip, "id", -1), -1) == _int(clip_id):
                        return track, clip
                raise ValueError(f"clip not found: {_int(clip_id)}")
            if clips:
                return track, clips[0]
            if getattr(track, "source_path", None) is not None:
                return track, track
            raise ValueError(f"video track has no clip to extract: {_int(track_id)}")

        for row in self._normalized_selection_entries():
            if str(row.get("track_kind") or "video") != "video":
                continue
            try:
                return self._video_track_and_clip(_int(row.get("track_id")), _int(row.get("clip_id")))
            except Exception:
                continue

        tracks = list(getattr(owner, "_tracks", []) or [])
        for track in tracks:
            clips = list(getattr(track, "clips", []) or [])
            if clips:
                return track, clips[0]
            if getattr(track, "source_path", None) is not None:
                return track, track
        raise ValueError("no video clip is selected")

    @staticmethod
    def _video_audio_source_path(track: Any, clip: Any) -> Path | None:
        source = getattr(clip, "source_path", None)
        if source is None:
            source = getattr(track, "source_path", None)
        if source in (None, ""):
            return None
        return Path(source)

    def _advance_owner_next_track_id(self, used_id: int) -> None:
        owner = self._require_owner()
        if not hasattr(owner, "_next_track_id"):
            return
        try:
            owner._next_track_id = max(_int(getattr(owner, "_next_track_id", 0)), _int(used_id) + 1)
        except Exception:
            pass

    def _sync_audio_track_ui(self, track: Any, *, created: bool, clip: Any | None = None) -> None:
        owner = self._require_owner()
        if created:
            insert = getattr(owner, "_insert_audio_track_widget", None)
            if callable(insert):
                try:
                    insert(track)
                except Exception:
                    pass
            mixer = getattr(owner, "_audio_mixer", None)
            add_track = getattr(mixer, "add_track", None)
            if callable(add_track):
                try:
                    add_track(track)
                except Exception:
                    pass
        else:
            row = getattr(owner, "_audio_rows", {}).get(_int(getattr(track, "id", 0))) if hasattr(owner, "_audio_rows") else None
            refresh = getattr(row, "refresh_from_track", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception:
                    pass
            elif row is not None and hasattr(row, "update"):
                row.update()
            self._update_audio_track(track)

        waveform = getattr(owner, "_start_waveform_extraction", None)
        if callable(waveform) and clip is not None:
            try:
                waveform(clip)
            except Exception:
                pass
        panel = getattr(owner, "_audio_mixer_panel", None)
        is_visible = getattr(panel, "isVisible", None)
        rebuild = getattr(panel, "rebuild", None)
        if callable(is_visible) and is_visible() and callable(rebuild):
            try:
                rebuild(getattr(owner, "_audio_tracks", []) or [])
            except Exception:
                pass
