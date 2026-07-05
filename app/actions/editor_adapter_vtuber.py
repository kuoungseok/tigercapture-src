"""VTuber, broadcast, and VSeeFace adapter methods for Python Actions."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _none_avatar_target() -> dict[str, Any]:
    return {
        "id": "none",
        "kind": "none",
        "label": "No Avatar Target",
        "name": "Avatar Target",
        "path": "",
        "program_output": False,
        "direct_key_baking": False,
        "pose_stream": False,
    }


def _vrm_pose_sample_summary(motion_csv: str = "") -> dict[str, Any]:
    path_text = str(motion_csv or "").strip()
    if not path_text:
        return {
            "available": False,
            "source": "",
            "reason": "no_motion_csv",
        }
    path = Path(path_text)
    if not path.is_file():
        return {
            "available": False,
            "source": path_text,
            "reason": "motion_csv_missing",
        }
    try:
        from app.vtuber.openseeface_motion import load_openseeface_motion_csv
        from app.vtuber.vrm_pose_driver import build_vrm_pose_frames, summarize_vrm_pose_frames

        motion = load_openseeface_motion_csv(path)
        pose_frames = build_vrm_pose_frames(motion)
        summary = summarize_vrm_pose_frames(pose_frames)
        summary.update({"available": True, "source": str(path)})
        return summary
    except Exception as exc:
        return {
            "available": False,
            "source": path_text,
            "reason": f"{type(exc).__name__}:{exc}",
        }

class VtuberBroadcastAdapterMixin:
    """Performance source, VTuber Studio, broadcast, and VSeeFace adapter methods."""

    def performance_source_summary(self, *, time_ms: int | None = None) -> dict[str, Any]:
        """Return VTuber performance-source state and Program Output rules."""
        from app.vtuber.performance_source import (
            PERFORMANCE_SOURCE_BADGE,
            PERFORMANCE_SOURCE_LABEL,
            PERFORMANCE_SOURCE_SCHEMA,
            is_performance_source_track,
            performance_source_ui_contract,
            program_output_contract,
        )

        owner = self.owner
        tracks = list(getattr(owner, "_tracks", []) or []) if owner is not None else []
        target_ms = max(0, _int(time_ms)) if time_ms is not None else (self._current_playhead_ms() if owner is not None else 0)
        pool_paths: list[str] = []
        pool = getattr(owner, "_media_pool", None) if owner is not None else None
        getter = getattr(pool, "performance_source_paths", None)
        if callable(getter):
            try:
                pool_paths = [str(row) for row in list(getter() or []) if str(row or "")]
            except Exception:
                pool_paths = []

        track_rows: list[dict[str, Any]] = []
        for track in tracks:
            if not is_performance_source_track(track):
                continue
            clips = list(getattr(track, "clips", []) or [])
            track_rows.append(
                {
                    "track_id": _int(getattr(track, "id", 0)),
                    "label": str(getattr(track, "label", "") or getattr(track, "name", "") or PERFORMANCE_SOURCE_LABEL),
                    "clip_count": len(clips),
                    "program_output": False,
                    "badge": PERFORMANCE_SOURCE_BADGE,
                }
            )

        return {
            "schema": PERFORMANCE_SOURCE_SCHEMA,
            "label": PERFORMANCE_SOURCE_LABEL,
            "badge": PERFORMANCE_SOURCE_BADGE,
            "time_ms": target_ms,
            "media_pool_paths": pool_paths,
            "performance_tracks": track_rows,
            "performance_track_count": len(track_rows),
            "program_output_contract": program_output_contract(tracks, target_ms),
            "ui_contract": performance_source_ui_contract(),
        }

    def program_output_contract(self, *, time_ms: int | None = None) -> dict[str, Any]:
        """Return the VTuber Program Output background contract at a timeline time."""
        from app.vtuber.performance_source import program_output_contract

        owner = self._require_owner()
        target_ms = max(0, _int(time_ms)) if time_ms is not None else self._current_playhead_ms()
        return program_output_contract(getattr(owner, "_tracks", []) or [], target_ms)

    def mark_performance_source_media(
        self,
        *,
        path: str,
        enabled: bool = True,
        add_to_pool: bool = True,
    ) -> dict[str, Any]:
        """Mark a Media Pool item as input-only avatar tracking media."""
        from app.vtuber.performance_source import PERFORMANCE_SOURCE_BADGE, PERFORMANCE_SOURCE_SCHEMA

        owner = self._require_owner()
        media_path = Path(str(path or "")).expanduser()
        if not media_path.is_file():
            raise ValueError(f"media path does not exist: {media_path}")
        pool = getattr(owner, "_media_pool", None)
        added = False
        if bool(add_to_pool):
            added = bool(self._register_media_path(media_path))
        setter = getattr(pool, "set_performance_source_path", None)
        changed = False
        if callable(setter):
            changed = bool(setter(media_path, bool(enabled)))
        else:
            flags = dict(getattr(owner, "_action_performance_source_media", {}) or {})
            key = str(media_path.resolve())
            before = bool(flags.get(key, False))
            if bool(enabled):
                flags[key] = True
            else:
                flags.pop(key, None)
            changed = before != bool(flags.get(key, False))
            setattr(owner, "_action_performance_source_media", flags)
        self._register_change("Mark Performance Source media")
        return {
            "schema": PERFORMANCE_SOURCE_SCHEMA,
            "path": str(media_path.resolve()),
            "enabled": bool(enabled),
            "added_to_pool": bool(added),
            "changed": bool(changed),
            "badge": PERFORMANCE_SOURCE_BADGE,
            "program_output": False,
        }

    def add_performance_source_clip(
        self,
        *,
        path: str,
        start_ms: int | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        """Place media on a dedicated Performance Source track for avatar tracking."""
        from app.vtuber.performance_source import (
            PERFORMANCE_SOURCE_BADGE,
            PERFORMANCE_SOURCE_LABEL,
            PERFORMANCE_SOURCE_SCHEMA,
            is_performance_source_track,
            mark_performance_source_object,
            program_output_contract,
        )

        owner = self._require_owner()
        media_path = Path(str(path or "")).expanduser()
        if not media_path.is_file():
            raise ValueError(f"media path does not exist: {media_path}")
        start = max(0, _int(start_ms)) if start_ms is not None else self._current_playhead_ms()
        duration = max(0, _int(duration_ms, 0))
        if duration <= 0:
            try:
                from app.video_editor_window import probe_video_duration_ms

                duration = _int(probe_video_duration_ms(media_path), 0)
            except Exception:
                duration = 0
        duration = max(1, duration or 30_000)

        live_add = getattr(owner, "_add_performance_source_clip", None)
        if callable(live_add):
            before = self._performance_source_clip_count()
            live_add(media_path, start)
            after = self._performance_source_clip_count()
            return {
                "schema": PERFORMANCE_SOURCE_SCHEMA,
                "path": str(media_path.resolve()),
                "timeline_in_ms": start,
                "duration_ms": duration,
                "added_by_owner": True,
                "clip_count_before": before,
                "clip_count_after": after,
                "badge": PERFORMANCE_SOURCE_BADGE,
                "program_output": False,
                "program_output_contract": program_output_contract(getattr(owner, "_tracks", []) or [], start),
            }

        self.mark_performance_source_media(path=str(media_path), enabled=True, add_to_pool=True)
        tracks = list(getattr(owner, "_tracks", []) or [])
        track = next((row for row in tracks if is_performance_source_track(row)), None)
        if track is None:
            try:
                from app.timeline_model import VideoTrack

                track = VideoTrack(id=self._next_track_id(tracks))
            except Exception:
                from types import SimpleNamespace

                track = SimpleNamespace(id=self._next_track_id(tracks), clips=[])
            mark_performance_source_object(track)
            try:
                setattr(track, "label", PERFORMANCE_SOURCE_LABEL)
            except Exception:
                pass
            tracks.append(track)
            setattr(owner, "_tracks", tracks)

        clips = getattr(track, "clips", None)
        if not isinstance(clips, list):
            track.clips = []
            clips = track.clips
        from app.timeline_model import NodeGraph, VideoClip

        clip = VideoClip(
            id=self._next_clip_id(track),
            source_path=media_path.resolve(),
            source_duration_ms=duration,
            timeline_in_ms=start,
            source_in_ms=0,
            source_out_ms=duration,
            node_graph=NodeGraph.default(),
        )
        mark_performance_source_object(clip)
        clips.append(clip)
        clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
        self._after_timeline_mutation("Add Performance Source clip")
        return {
            "schema": PERFORMANCE_SOURCE_SCHEMA,
            "path": str(media_path.resolve()),
            "track_id": _int(getattr(track, "id", 0)),
            "clip_id": _int(getattr(clip, "id", 0)),
            "timeline_in_ms": start,
            "duration_ms": duration,
            "added_by_owner": False,
            "badge": PERFORMANCE_SOURCE_BADGE,
            "program_output": False,
            "program_output_contract": program_output_contract(getattr(owner, "_tracks", []) or [], start),
        }

    def vseeface_input_sources(
        self,
        *,
        camera_devices: list[dict[str, Any]] | None = None,
        input_diagnostics: Mapping[str, Any] | None = None,
        media_limit: int = 200,
    ) -> dict[str, Any]:
        """Return UI-ready VSeeFace tracking input choices for this project."""
        from app.vtuber.vseeface_bridge import (
            VSeeFaceBridgeConfig,
            build_vseeface_input_source_options,
        )

        config = VSeeFaceBridgeConfig.from_mapping(self._vseeface_bridge_settings())
        snapshot = self.snapshot(media_limit=max(0, int(media_limit or 200)))
        input_sources = build_vseeface_input_source_options(
            project_snapshot=snapshot,
            camera_devices=camera_devices or [],
            selected=config.input_source,
            input_diagnostics=input_diagnostics if isinstance(input_diagnostics, Mapping) else None,
        )
        return {
            "schema": "tigerstudio.actions.vseeface_input_sources.v1",
            "project_settings_key": "vseeface_bridge",
            "input_sources": input_sources,
            "selected_input": dict((input_sources.get("selected") or {}).get("input") or config.input_source.to_dict()),
            "snapshot_hash": snapshot.get("snapshot_hash", ""),
        }

    def vseeface_bridge_status(
        self,
        *,
        camera_devices: list[dict[str, Any]] | None = None,
        capture_diagnostics: Mapping[str, Any] | None = None,
        input_diagnostics: Mapping[str, Any] | None = None,
        media_limit: int = 200,
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
    ) -> dict[str, Any]:
        """Return the UI-facing VSeeFace bridge status for this project."""
        from app.vtuber.vseeface_bridge import (
            VSeeFaceBridgeConfig,
            build_vseeface_bridge_status,
        )

        config = VSeeFaceBridgeConfig.from_mapping(self._vseeface_bridge_settings())
        snapshot = self.snapshot(media_limit=max(0, int(media_limit or 200)))
        status = build_vseeface_bridge_status(
            config,
            capture_diagnostics=capture_diagnostics if isinstance(capture_diagnostics, Mapping) else None,
            input_diagnostics=input_diagnostics if isinstance(input_diagnostics, Mapping) else None,
            project_snapshot=snapshot,
            camera_devices=camera_devices or [],
            width=max(1, int(width or 1920)),
            height=max(1, int(height or 1080)),
            fps=max(1.0, float(fps or 30.0)),
        )
        return {
            "schema": "tigerstudio.actions.vseeface_bridge_status.v1",
            "project_settings_key": "vseeface_bridge",
            "status": status,
            "view": status.get("view", {}),
            "input_sources": status.get("input_sources", {}),
            "snapshot_hash": snapshot.get("snapshot_hash", ""),
        }

    def avatar_target_summary(self, *, target_id: str = "", media_limit: int = 200) -> dict[str, Any]:
        """Return VTuber Studio avatar targets without assuming Live2D only."""
        options = self._avatar_target_options()
        selected_id = str(target_id or self._selected_vtuber_avatar_target_id() or "").strip()
        if not selected_id:
            selected_id = self._default_avatar_target_id(options)
        selected = next((item for item in options if str(item.get("id") or "") == selected_id), None)
        if selected is None and options:
            selected = options[0]
            selected_id = str(selected.get("id") or "")
        snapshot = self.snapshot(media_limit=max(0, int(media_limit or 200)))
        return {
            "schema": "tigerstudio.actions.vtuber_avatar_target_summary.v1",
            "label": "Avatar Target",
            "project_settings_key": "vtuber_studio.avatar_target_id",
            "selected_id": selected_id,
            "selected": dict(selected or _none_avatar_target()),
            "options": options or [_none_avatar_target()],
            "counts": {
                "vrm_vseeface_bridge": sum(1 for item in options if item.get("kind") == "vrm_vseeface_bridge"),
                "live2d_actor_clip": sum(1 for item in options if item.get("kind") == "live2d_actor_clip"),
            },
            "terms": {
                "input": "Performance Source",
                "output": "Program Output",
                "target": "Avatar Target",
                "vrm_bridge": "VRM / VSeeFace Bridge",
            },
            "snapshot_hash": snapshot.get("snapshot_hash", ""),
        }

    def open_vtuber_studio(self, *, avatar_target_id: str = "") -> dict[str, Any]:
        """Open the shared VTuber Studio window through the editor, if present."""
        if self.owner is None:
            raise ValueError("no editor owner")
        selected = None
        if str(avatar_target_id or "").strip():
            selected = self.select_vtuber_avatar_target(target_id=str(avatar_target_id or "").strip()).get("selected")
        opener = getattr(self.owner, "_open_vtuber_broadcast_studio", None)
        opened = False
        if callable(opener):
            opener()
            opened = True
        summary = self.avatar_target_summary(target_id=str(avatar_target_id or "").strip())
        return {
            "schema": "tigerstudio.actions.vtuber_studio_open.v1",
            "window": "VTuberBroadcastStudioWindow",
            "shared_studio": True,
            "opened": opened,
            "selected": selected or summary.get("selected", {}),
            "entrypoint": "vtuber.studio.open",
        }

    def select_vtuber_avatar_target(self, *, target_id: str = "") -> dict[str, Any]:
        """Persist the selected VTuber Studio avatar target."""
        if self.owner is None:
            raise ValueError("no editor owner")
        selected_id = str(target_id or "").strip()
        if not selected_id:
            raise ValueError("target_id is required")
        summary = self.avatar_target_summary(target_id=selected_id)
        selected = summary.get("selected") if isinstance(summary.get("selected"), Mapping) else {}
        if str(selected.get("kind") or "") == "none":
            raise ValueError(f"Avatar target not found: {selected_id}")
        settings = dict(getattr(self.owner, "_project_settings", {}) or {})
        studio = dict(settings.get("vtuber_studio") if isinstance(settings.get("vtuber_studio"), Mapping) else {})
        studio["avatar_target_id"] = selected_id
        settings["vtuber_studio"] = studio
        setattr(self.owner, "_project_settings", settings)
        player = getattr(self.owner, "_player", None)
        if player is not None and hasattr(player, "set_project_settings"):
            player.set_project_settings(settings)
        self._register_change("Select VTuber avatar target")
        return {
            "schema": "tigerstudio.actions.vtuber_avatar_target_select.v1",
            "project_settings_key": "vtuber_studio.avatar_target_id",
            "selected_id": selected_id,
            "selected": dict(selected),
            "settings": studio,
        }

    def broadcast_live_target_summary(
        self,
        *,
        target_id: str = "",
        server_url: str = "",
        stream_key: str = "",
        output_path: str = "",
        video_bitrate_kbps: int = 0,
        include_audio: bool = False,
        audio_source_kind: str = "",
        audio_device_name: str = "",
        audio_file: str = "",
        auto_reconnect: bool | None = None,
        max_retries: int = -1,
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
    ) -> dict[str, Any]:
        """Return Live Target presets and preflight without exposing stream keys."""
        from app.broadcast_output import (
            LiveTargetProfile,
            live_target_preflight,
            live_target_presets,
        )

        settings = self._broadcast_output_settings()
        live_target = dict(settings.get("live_target") if isinstance(settings.get("live_target"), Mapping) else {})
        if target_id:
            live_target["target_id"] = str(target_id)
        if server_url:
            live_target["server_url"] = str(server_url)
        if output_path:
            live_target["output_path"] = str(output_path)
        if int(video_bitrate_kbps or 0) > 0:
            live_target["video_bitrate_kbps"] = int(video_bitrate_kbps)
        if include_audio or audio_source_kind:
            live_target["include_audio"] = bool(include_audio or audio_source_kind)
            live_target["audio_source_kind"] = str(audio_source_kind or "none")
            live_target["audio_device_name"] = str(audio_device_name or "")
            live_target["audio_file"] = str(audio_file or "")
        if auto_reconnect is not None:
            live_target["auto_reconnect"] = bool(auto_reconnect)
        if max_retries is not None and int(max_retries) >= 0:
            live_target["max_retries"] = int(max_retries)
        if stream_key:
            live_target["stream_key"] = str(stream_key)
        profile = LiveTargetProfile.from_mapping(live_target)
        canvas = {"width": int(width or 1920), "height": int(height or 1080), "fps": float(fps or 30.0)}
        preflight = live_target_preflight(profile, canvas)
        return {
            "schema": "tigerstudio.actions.broadcast_live_target_summary.v1",
            "project_settings_key": "broadcast_output.live_target",
            "selected_id": profile.target_id,
            "selected": profile.to_dict(redact_secret=True),
            "presets": live_target_presets(),
            "preflight": preflight,
            "terms": {
                "target": "Live Target",
                "output": "Program Output",
                "secret": "Stream key is session-only and must not be saved in the project file.",
            },
        }

    def select_broadcast_live_target(
        self,
        *,
        target_id: str = "",
        server_url: str = "",
        stream_key: str = "",
        output_path: str = "",
        video_bitrate_kbps: int = 0,
        include_audio: bool = False,
        audio_source_kind: str = "",
        audio_device_name: str = "",
        audio_file: str = "",
        auto_reconnect: bool | None = None,
        max_retries: int = -1,
    ) -> dict[str, Any]:
        """Persist the selected Live Target, excluding any raw stream key."""
        if self.owner is None:
            raise ValueError("no editor owner")
        from app.broadcast_output import LiveTargetProfile

        current = self._broadcast_output_settings()
        live_target = dict(current.get("live_target") if isinstance(current.get("live_target"), Mapping) else {})
        if target_id:
            live_target["target_id"] = str(target_id)
        if server_url:
            live_target["server_url"] = str(server_url)
        if output_path:
            live_target["output_path"] = str(output_path)
        if int(video_bitrate_kbps or 0) > 0:
            live_target["video_bitrate_kbps"] = int(video_bitrate_kbps)
        if include_audio or audio_source_kind:
            live_target["include_audio"] = bool(include_audio or audio_source_kind)
            live_target["audio_source_kind"] = str(audio_source_kind or "none")
            live_target["audio_device_name"] = str(audio_device_name or "")
            live_target["audio_file"] = str(audio_file or "")
        if auto_reconnect is not None:
            live_target["auto_reconnect"] = bool(auto_reconnect)
        if max_retries is not None and int(max_retries) >= 0:
            live_target["max_retries"] = int(max_retries)
        if stream_key:
            live_target["stream_key"] = str(stream_key)
        profile = LiveTargetProfile.from_mapping(live_target)
        settings = dict(getattr(self.owner, "_project_settings", {}) or {})
        broadcast = dict(settings.get("broadcast_output") if isinstance(settings.get("broadcast_output"), Mapping) else {})
        broadcast["live_target"] = profile.to_project_settings()
        settings["broadcast_output"] = broadcast
        setattr(self.owner, "_project_settings", settings)
        player = getattr(self.owner, "_player", None)
        if player is not None and hasattr(player, "set_project_settings"):
            player.set_project_settings(settings)
        self._register_change("Select broadcast live target")
        return {
            "schema": "tigerstudio.actions.broadcast_live_target_select.v1",
            "project_settings_key": "broadcast_output.live_target",
            "selected_id": profile.target_id,
            "selected": profile.to_dict(redact_secret=True),
            "settings": broadcast["live_target"],
        }

    def broadcast_live_target_troubleshooting(
        self,
        *,
        target_id: str = "",
        platform_error_kind: str = "",
        platform_error_message: str = "",
        last_error: str = "",
        stderr_tail: str = "",
        state: str = "error",
    ) -> dict[str, Any]:
        """Return platform-specific Live Target troubleshooting guidance."""
        from app.broadcast_output import LiveTargetProfile
        from app.broadcast_troubleshooting import build_live_target_troubleshooting

        current = self._broadcast_output_settings()
        live_target = dict(current.get("live_target") if isinstance(current.get("live_target"), Mapping) else {})
        if target_id:
            live_target["target_id"] = str(target_id)
        profile = LiveTargetProfile.from_mapping(live_target)
        status = {
            "state": str(state or "error"),
            "platform_error_kind": str(platform_error_kind or ""),
            "platform_error_message": str(platform_error_message or ""),
            "last_error": str(last_error or ""),
            "stderr_tail": str(stderr_tail or ""),
        }
        plan = build_live_target_troubleshooting(profile, status)
        return {
            "schema": "tigerstudio.actions.broadcast_live_target_troubleshooting.v1",
            "project_settings_key": "broadcast_output.live_target",
            "selected_id": profile.target_id,
            "troubleshooting": plan,
        }

    def broadcast_virtual_camera_plan(
        self,
        *,
        backend: str = "",
        preferred_backend: str = "",
        discover: bool = True,
        installed_backends: Mapping[str, Any] | None = None,
        obs_executable: str = "",
        obs_path: str = "",
        program_window_title: str = "",
        scene_name: str = "",
        source_name: str = "",
        websocket_enabled: bool = False,
        use_websocket: bool = False,
        websocket_host: str = "",
        websocket_port: int = 0,
        websocket_password_present: bool = False,
    ) -> dict[str, Any]:
        """Return the Discord/video-call virtual-camera output plan."""
        from app.broadcast_virtual_camera import (
            discover_installed_virtual_camera_backends,
            virtual_camera_output_plan,
        )

        payload: dict[str, Any] = {
            "backend": str(backend or ""),
            "preferred_backend": str(preferred_backend or ""),
            "discover": bool(discover),
            "obs_executable": str(obs_executable or obs_path or ""),
            "program_window_title": str(program_window_title or ""),
            "scene_name": str(scene_name or ""),
            "source_name": str(source_name or ""),
            "websocket_enabled": bool(websocket_enabled or use_websocket),
            "use_websocket": bool(websocket_enabled or use_websocket),
            "websocket_host": str(websocket_host or ""),
            "websocket_port": int(websocket_port or 0),
            "websocket_password_present": bool(websocket_password_present),
        }
        explicit_installed = dict(installed_backends) if isinstance(installed_backends, Mapping) else None
        discovery = None
        if explicit_installed is None and discover:
            discovery = discover_installed_virtual_camera_backends(payload)
            explicit_installed = dict(discovery.get("installed_backends") or {})
            payload["discover"] = False
        plan = virtual_camera_output_plan(payload, installed_backends=explicit_installed)
        if discovery is not None:
            plan["discovery"] = discovery
        return {
            "schema": "tigerstudio.actions.broadcast_virtual_camera_plan.v1",
            "project_settings_key": "broadcast_output.virtual_camera",
            "plan": plan,
            "selected_backend": plan.get("selected_backend", ""),
            "terms": {
                "output": "Program Output",
                "performance_source": "Performance Source must not be sent directly to the call.",
                "install_policy": "Virtual-camera driver/backend installs require user approval.",
            },
        }

    def broadcast_obs_virtual_camera_bridge_plan(
        self,
        *,
        discover: bool = True,
        installed_backends: Mapping[str, Any] | None = None,
        obs_executable: str = "",
        obs_path: str = "",
        program_window_title: str = "",
        scene_name: str = "",
        source_name: str = "",
        websocket_enabled: bool = False,
        use_websocket: bool = False,
        websocket_host: str = "",
        websocket_port: int = 0,
        websocket_password_present: bool = False,
    ) -> dict[str, Any]:
        """Return the OBS Window Capture plus Virtual Camera bridge plan."""
        from app.broadcast_virtual_camera import (
            discover_installed_virtual_camera_backends,
            obs_virtual_camera_bridge_plan,
        )

        payload: dict[str, Any] = {
            "discover": bool(discover),
            "obs_executable": str(obs_executable or obs_path or ""),
            "program_window_title": str(program_window_title or ""),
            "scene_name": str(scene_name or ""),
            "source_name": str(source_name or ""),
            "websocket_enabled": bool(websocket_enabled or use_websocket),
            "use_websocket": bool(websocket_enabled or use_websocket),
            "websocket_host": str(websocket_host or ""),
            "websocket_port": int(websocket_port or 0),
            "websocket_password_present": bool(websocket_password_present),
        }
        explicit_installed = dict(installed_backends) if isinstance(installed_backends, Mapping) else None
        discovery = None
        if explicit_installed is None and discover:
            discovery = discover_installed_virtual_camera_backends(payload)
            explicit_installed = dict(discovery.get("installed_backends") or {})
            payload["discover"] = False
        plan = obs_virtual_camera_bridge_plan(payload, installed_backends=explicit_installed)
        if discovery is not None:
            plan["discovery"] = discovery
        return {
            "schema": "tigerstudio.actions.broadcast_obs_virtual_camera_bridge_plan.v1",
            "project_settings_key": "broadcast_output.virtual_camera.obs_bridge",
            "plan": plan,
            "available": bool(plan.get("available", False)),
            "terms": {
                "output": "Program Output",
                "backend": "OBS Virtual Camera",
                "install_policy": "User approved only; no bundled driver install is attempted.",
            },
        }

    def broadcast_obs_virtual_camera_bridge_execution_gate(
        self,
        *,
        confirm: bool = False,
        discover: bool = True,
        installed_backends: Mapping[str, Any] | None = None,
        obs_executable: str = "",
        obs_path: str = "",
        program_window_title: str = "",
        scene_name: str = "",
        source_name: str = "",
        websocket_enabled: bool = False,
        use_websocket: bool = False,
        websocket_host: str = "",
        websocket_port: int = 0,
        websocket_password_present: bool = False,
        obsws_available: bool | None = None,
    ) -> dict[str, Any]:
        """Return the confirmed OBS automation execution gate."""
        from app.broadcast_virtual_camera import obs_virtual_camera_bridge_execution_gate

        payload = self._obs_bridge_payload(
            confirm=confirm,
            discover=discover,
            obs_executable=obs_executable,
            obs_path=obs_path,
            program_window_title=program_window_title,
            scene_name=scene_name,
            source_name=source_name,
            websocket_enabled=websocket_enabled,
            use_websocket=use_websocket,
            websocket_host=websocket_host,
            websocket_port=websocket_port,
            websocket_password_present=websocket_password_present,
            obsws_available=obsws_available,
        )
        plan = obs_virtual_camera_bridge_execution_gate(
            payload,
            installed_backends=dict(installed_backends) if isinstance(installed_backends, Mapping) else None,
        )
        return {
            "schema": "tigerstudio.actions.broadcast_obs_virtual_camera_bridge_execution_gate.v1",
            "gate": plan,
            "can_execute": bool(plan.get("can_execute", False)),
        }

    def broadcast_obs_virtual_camera_bridge_dry_run(
        self,
        *,
        confirm: bool = False,
        discover: bool = True,
        installed_backends: Mapping[str, Any] | None = None,
        obs_executable: str = "",
        obs_path: str = "",
        program_window_title: str = "",
        scene_name: str = "",
        source_name: str = "",
        websocket_enabled: bool = False,
        use_websocket: bool = False,
        websocket_host: str = "",
        websocket_port: int = 0,
        websocket_password_present: bool = False,
        obsws_available: bool | None = None,
    ) -> dict[str, Any]:
        """Return OBS bridge WebSocket operations without controlling OBS."""
        from app.broadcast_virtual_camera import obs_virtual_camera_bridge_executor_dry_run

        payload = self._obs_bridge_payload(
            confirm=confirm,
            discover=discover,
            obs_executable=obs_executable,
            obs_path=obs_path,
            program_window_title=program_window_title,
            scene_name=scene_name,
            source_name=source_name,
            websocket_enabled=websocket_enabled,
            use_websocket=use_websocket,
            websocket_host=websocket_host,
            websocket_port=websocket_port,
            websocket_password_present=websocket_password_present,
            obsws_available=obsws_available,
        )
        plan = obs_virtual_camera_bridge_executor_dry_run(
            payload,
            installed_backends=dict(installed_backends) if isinstance(installed_backends, Mapping) else None,
        )
        return {
            "schema": "tigerstudio.actions.broadcast_obs_virtual_camera_bridge_dry_run.v1",
            "dry_run": plan,
            "operations": plan.get("operations", []),
        }

    def broadcast_obs_virtual_camera_bridge_execute(
        self,
        *,
        confirm: bool = False,
        discover: bool = True,
        installed_backends: Mapping[str, Any] | None = None,
        obs_executable: str = "",
        obs_path: str = "",
        program_window_title: str = "",
        scene_name: str = "",
        source_name: str = "",
        websocket_enabled: bool = False,
        use_websocket: bool = False,
        websocket_host: str = "",
        websocket_port: int = 0,
        websocket_password: str = "",
        websocket_password_present: bool = False,
        obsws_available: bool | None = None,
    ) -> dict[str, Any]:
        """Execute confirmed OBS bridge setup through OBS WebSocket."""
        from app.broadcast_virtual_camera import execute_obs_virtual_camera_bridge

        payload = self._obs_bridge_payload(
            confirm=confirm,
            discover=discover,
            obs_executable=obs_executable,
            obs_path=obs_path,
            program_window_title=program_window_title,
            scene_name=scene_name,
            source_name=source_name,
            websocket_enabled=websocket_enabled,
            use_websocket=use_websocket,
            websocket_host=websocket_host,
            websocket_port=websocket_port,
            websocket_password_present=websocket_password_present or bool(websocket_password),
            obsws_available=obsws_available,
        )
        if websocket_password:
            payload["websocket_password"] = str(websocket_password)
        result = execute_obs_virtual_camera_bridge(
            payload,
            installed_backends=dict(installed_backends) if isinstance(installed_backends, Mapping) else None,
        )
        return {
            "schema": "tigerstudio.actions.broadcast_obs_virtual_camera_bridge_execute.v1",
            "result": result,
            "executed": bool(result.get("executed", False)),
        }

    @staticmethod
    def _obs_bridge_payload(
        *,
        confirm: bool = False,
        discover: bool = True,
        obs_executable: str = "",
        obs_path: str = "",
        program_window_title: str = "",
        scene_name: str = "",
        source_name: str = "",
        websocket_enabled: bool = False,
        use_websocket: bool = False,
        websocket_host: str = "",
        websocket_port: int = 0,
        websocket_password_present: bool = False,
        obsws_available: bool | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "confirm": bool(confirm),
            "discover": bool(discover),
            "obs_executable": str(obs_executable or obs_path or ""),
            "program_window_title": str(program_window_title or ""),
            "scene_name": str(scene_name or ""),
            "source_name": str(source_name or ""),
            "websocket_enabled": bool(websocket_enabled or use_websocket),
            "use_websocket": bool(websocket_enabled or use_websocket),
            "websocket_host": str(websocket_host or ""),
            "websocket_port": int(websocket_port or 0),
            "websocket_password_present": bool(websocket_password_present),
        }
        if obsws_available is not None:
            payload["obsws_available"] = bool(obsws_available)
        return payload

    def broadcast_release_readiness(self, *, root: str = "") -> dict[str, Any]:
        """Return VTuber/broadcast commercial-readiness diagnostics."""
        from app.broadcast_release_readiness import (
            build_broadcast_release_readiness_report,
            format_broadcast_release_readiness_summary,
        )

        report = build_broadcast_release_readiness_report(root or ".")
        report["summary_text"] = format_broadcast_release_readiness_summary(report)
        return report

    def broadcast_platform_evidence_checklist(self, *, root: str = "") -> dict[str, Any]:
        """Return the remaining broadcast platform evidence checklist."""
        from app.broadcast_platform_e2e import build_broadcast_platform_evidence_checklist

        return build_broadcast_platform_evidence_checklist(root or ".")

    def register_broadcast_platform_evidence(
        self,
        *,
        check_id: str,
        platform: str,
        evidence_path: str = "",
        notes: str = "",
        confirm_redacted: bool = False,
        root: str = "",
        artifact_path: str = "debugCapture/broadcast_platform_e2e_qa.json",
    ) -> dict[str, Any]:
        """Register redacted broadcast platform evidence after a real check."""
        from app.broadcast_platform_e2e import register_manual_platform_evidence

        return register_manual_platform_evidence(
            root or ".",
            check_id=check_id,
            platform=platform,
            evidence_path=evidence_path,
            notes=notes,
            confirm_redacted=bool(confirm_redacted),
            artifact_path=artifact_path,
        )

    def vrm_bridge_status(
        self,
        *,
        camera_devices: list[dict[str, Any]] | None = None,
        capture_diagnostics: Mapping[str, Any] | None = None,
        input_diagnostics: Mapping[str, Any] | None = None,
        media_limit: int = 200,
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
    ) -> dict[str, Any]:
        """Return VRM / VSeeFace bridge status scoped as an Avatar Target."""
        target = self.avatar_target_summary(target_id="vrm:vseeface_bridge", media_limit=media_limit)
        bridge = self.vseeface_bridge_status(
            camera_devices=camera_devices or [],
            capture_diagnostics=capture_diagnostics if isinstance(capture_diagnostics, Mapping) else None,
            input_diagnostics=input_diagnostics if isinstance(input_diagnostics, Mapping) else None,
            media_limit=media_limit,
            width=width,
            height=height,
            fps=fps,
        )
        return {
            "schema": "tigerstudio.actions.vtuber_vrm_bridge_status.v1",
            "avatar_target": target.get("selected", {}),
            "bridge": bridge.get("status", {}),
            "view": bridge.get("view", {}),
            "input_sources": bridge.get("input_sources", {}),
            "snapshot_hash": bridge.get("snapshot_hash", ""),
        }

    def vrm_pose_stream_preview(
        self,
        *,
        motion_csv: str = "",
        camera_devices: list[dict[str, Any]] | None = None,
        capture_diagnostics: Mapping[str, Any] | None = None,
        input_diagnostics: Mapping[str, Any] | None = None,
        media_limit: int = 200,
    ) -> dict[str, Any]:
        """Preview the VRM pose-stream route without baking Live2D keys."""
        bridge_payload = self.vrm_bridge_status(
            camera_devices=camera_devices or [],
            capture_diagnostics=capture_diagnostics if isinstance(capture_diagnostics, Mapping) else None,
            input_diagnostics=input_diagnostics if isinstance(input_diagnostics, Mapping) else None,
            media_limit=media_limit,
        )
        bridge = bridge_payload.get("bridge") if isinstance(bridge_payload.get("bridge"), Mapping) else {}
        preflight = bridge.get("preflight") if isinstance(bridge.get("preflight"), Mapping) else {}
        tracking = preflight.get("tracking") if isinstance(preflight.get("tracking"), Mapping) else {}
        view = bridge_payload.get("view") if isinstance(bridge_payload.get("view"), Mapping) else {}
        input_source = view.get("input_source") if isinstance(view.get("input_source"), Mapping) else {}
        sample = _vrm_pose_sample_summary(motion_csv)
        pose_ready = bool(preflight.get("ok")) and str(input_source.get("status") or "") not in {"unavailable", "black_frame"}
        return {
            "schema": "tigerstudio.actions.vtuber_vrm_pose_stream_preview.v1",
            "avatar_target": bridge_payload.get("avatar_target", {}),
            "pose_stream": {
                "ready": pose_ready,
                "route": "Performance Source -> OpenSeeFace -> VMC/pose stream -> VRM / VSeeFace Bridge",
                "direct_key_baking": False,
                "live2d_key_baking": False,
                "capture_required_for_pose": False,
                "protocol": str(tracking.get("protocol") or "vmc_osc"),
                "host": str(tracking.get("target_host") or "127.0.0.1"),
                "receive_port": tracking.get("receive_port"),
                "send_port": tracking.get("send_port"),
                "selected_input": dict(input_source),
            },
            "sample": sample,
            "bridge_state": str(bridge.get("state") or ""),
            "capture_status": str((bridge.get("capture") or {}).get("status") or ""),
            "warnings": [] if pose_ready else ["pose_stream_needs_tracking_input_or_bridge_setup"],
        }

    def preview_vseeface_bridge_action(
        self,
        *,
        action_id: str = "",
        allow_admin: bool = False,
        camera_devices: list[dict[str, Any]] | None = None,
        capture_diagnostics: Mapping[str, Any] | None = None,
        media_limit: int = 200,
    ) -> dict[str, Any]:
        """Preview a declarative VSeeFace bridge action without executing it."""
        from app.vtuber.vseeface_action_plan import build_vseeface_action_preview

        status_payload = self.vseeface_bridge_status(
            camera_devices=camera_devices or [],
            capture_diagnostics=capture_diagnostics if isinstance(capture_diagnostics, Mapping) else None,
            media_limit=media_limit,
        )
        preview = build_vseeface_action_preview(
            status_payload.get("status", {}),
            action_id=str(action_id or "") or None,
            allow_admin=bool(allow_admin),
        )
        return {
            "schema": "tigerstudio.actions.vseeface_bridge_action_preview.v1",
            "project_settings_key": "vseeface_bridge",
            "preview": preview,
            "status_state": str((status_payload.get("status") or {}).get("state") or ""),
            "snapshot_hash": status_payload.get("snapshot_hash", ""),
        }

    def vseeface_start_probe_plan(
        self,
        *,
        camera_devices: list[dict[str, Any]] | None = None,
        capture_diagnostics: Mapping[str, Any] | None = None,
        input_diagnostics: Mapping[str, Any] | None = None,
        media_limit: int = 200,
    ) -> dict[str, Any]:
        """Return the explicit plan for launching VSeeFace and probing capture."""
        from app.vtuber.vseeface_bridge import ACTION_START_AND_PROBE_VSEEFACE

        status_payload = self.vseeface_bridge_status(
            camera_devices=camera_devices or [],
            capture_diagnostics=capture_diagnostics if isinstance(capture_diagnostics, Mapping) else None,
            input_diagnostics=input_diagnostics if isinstance(input_diagnostics, Mapping) else None,
            media_limit=media_limit,
        )
        status = status_payload.get("status") if isinstance(status_payload.get("status"), Mapping) else {}
        action = next(
            (
                item
                for item in status.get("actions", [])
                if isinstance(item, Mapping) and str(item.get("id") or "") == ACTION_START_AND_PROBE_VSEEFACE
            ),
            None,
        )
        plan = action.get("plan") if isinstance(action, Mapping) and isinstance(action.get("plan"), Mapping) else {}
        return {
            "schema": "tigerstudio.actions.vseeface_start_probe_plan.v1",
            "project_settings_key": "vseeface_bridge",
            "status_state": str(status.get("state") or ""),
            "plan": dict(plan),
            "action": dict(action) if isinstance(action, Mapping) else None,
        }

    def vseeface_start_probe_execution_gate(
        self,
        *,
        camera_devices: list[dict[str, Any]] | None = None,
        capture_diagnostics: Mapping[str, Any] | None = None,
        input_diagnostics: Mapping[str, Any] | None = None,
        media_limit: int = 200,
        confirm: bool = False,
        allow_admin: bool = False,
    ) -> dict[str, Any]:
        """Validate whether the start/probe plan can execute, without executing it."""
        from app.vtuber.vseeface_action_plan import build_vseeface_execution_gate

        payload = self.vseeface_start_probe_plan(
            camera_devices=camera_devices or [],
            capture_diagnostics=capture_diagnostics,
            input_diagnostics=input_diagnostics,
            media_limit=media_limit,
        )
        plan = payload.get("plan") if isinstance(payload.get("plan"), Mapping) else {}
        gate = build_vseeface_execution_gate(plan, confirm=bool(confirm), allow_admin=bool(allow_admin))
        return {
            "schema": "tigerstudio.actions.vseeface_start_probe_execution_gate.v1",
            "project_settings_key": "vseeface_bridge",
            "plan": plan,
            "gate": gate,
        }

    def vseeface_start_probe_executor_dry_run(
        self,
        *,
        camera_devices: list[dict[str, Any]] | None = None,
        capture_diagnostics: Mapping[str, Any] | None = None,
        input_diagnostics: Mapping[str, Any] | None = None,
        media_limit: int = 200,
        confirm: bool = False,
        allow_admin: bool = False,
    ) -> dict[str, Any]:
        """Return the start/probe executor dry-run report without running tools."""
        from app.vtuber.vseeface_plan_executor import execute_vseeface_plan

        payload = self.vseeface_start_probe_plan(
            camera_devices=camera_devices or [],
            capture_diagnostics=capture_diagnostics,
            input_diagnostics=input_diagnostics,
            media_limit=media_limit,
        )
        plan = payload.get("plan") if isinstance(payload.get("plan"), Mapping) else {}
        executor = execute_vseeface_plan(
            plan,
            confirm=bool(confirm),
            allow_admin=bool(allow_admin),
            execute=False,
        )
        return {
            "schema": "tigerstudio.actions.vseeface_start_probe_executor_dry_run.v1",
            "project_settings_key": "vseeface_bridge",
            "plan": plan,
            "executor": executor,
        }

    def vseeface_start_probe_execute(
        self,
        *,
        camera_devices: list[dict[str, Any]] | None = None,
        capture_diagnostics: Mapping[str, Any] | None = None,
        input_diagnostics: Mapping[str, Any] | None = None,
        media_limit: int = 200,
        confirm: bool = False,
        allow_admin: bool = False,
        timeout_s: float = 180.0,
    ) -> dict[str, Any]:
        """Launch VSeeFace and run capture probes only after explicit confirmation."""
        from app.vtuber.vseeface_plan_executor import execute_vseeface_plan

        payload = self.vseeface_start_probe_plan(
            camera_devices=camera_devices or [],
            capture_diagnostics=capture_diagnostics,
            input_diagnostics=input_diagnostics,
            media_limit=media_limit,
        )
        plan = payload.get("plan") if isinstance(payload.get("plan"), Mapping) else {}
        executor = execute_vseeface_plan(
            plan,
            confirm=bool(confirm),
            allow_admin=bool(allow_admin),
            execute=True,
            timeout_s=max(1.0, float(timeout_s or 180.0)),
        )
        return {
            "schema": "tigerstudio.actions.vseeface_start_probe_execute.v1",
            "project_settings_key": "vseeface_bridge",
            "plan": plan,
            "executor": executor,
        }

    def vseeface_sidecar_settings_preview(self, *, settings_path: str = "") -> dict[str, Any]:
        """Return the VSeeFace settings.ini payload that would be written."""
        from app.vtuber.vseeface_bridge import (
            VSeeFaceBridgeConfig,
            build_vseeface_sidecar_settings_preview,
        )

        config = VSeeFaceBridgeConfig.from_mapping(self._vseeface_bridge_settings())
        preview = build_vseeface_sidecar_settings_preview(
            config,
            settings_path=str(settings_path or "") or None,
        )
        return {
            "schema": "tigerstudio.actions.vseeface_sidecar_settings_preview.v1",
            "project_settings_key": "vseeface_bridge",
            "preview": preview,
        }

    def vseeface_sidecar_apply_plan(self, *, settings_path: str = "", out_path: str = "") -> dict[str, Any]:
        """Return a non-auto-run plan for writing VSeeFace sidecar settings."""
        from app.vtuber.vseeface_bridge import (
            VSeeFaceBridgeConfig,
            build_vseeface_sidecar_apply_plan,
        )

        config = VSeeFaceBridgeConfig.from_mapping(self._vseeface_bridge_settings())
        plan = build_vseeface_sidecar_apply_plan(
            config,
            settings_path=str(settings_path or "") or None,
            out_path=str(out_path or "") or "debugCapture\\vseeface_sidecar_config_report.json",
        )
        return {
            "schema": "tigerstudio.actions.vseeface_sidecar_apply_plan.v1",
            "project_settings_key": "vseeface_bridge",
            "plan": plan,
        }

    def vseeface_sidecar_execution_gate(
        self,
        *,
        settings_path: str = "",
        out_path: str = "",
        confirm: bool = False,
        allow_admin: bool = False,
    ) -> dict[str, Any]:
        """Return the sidecar settings execution gate without running it."""
        from app.vtuber.vseeface_action_plan import build_vseeface_execution_gate

        payload = self.vseeface_sidecar_apply_plan(settings_path=settings_path, out_path=out_path)
        plan = payload.get("plan") if isinstance(payload.get("plan"), Mapping) else {}
        gate = build_vseeface_execution_gate(
            plan,
            confirm=bool(confirm),
            allow_admin=bool(allow_admin),
        )
        return {
            "schema": "tigerstudio.actions.vseeface_sidecar_execution_gate.v1",
            "project_settings_key": "vseeface_bridge",
            "plan": plan,
            "gate": gate,
        }

    def vseeface_sidecar_executor_dry_run(
        self,
        *,
        settings_path: str = "",
        out_path: str = "",
        confirm: bool = False,
        allow_admin: bool = False,
    ) -> dict[str, Any]:
        """Return the sidecar executor dry-run report without running tools."""
        from app.vtuber.vseeface_plan_executor import execute_vseeface_plan

        payload = self.vseeface_sidecar_apply_plan(settings_path=settings_path, out_path=out_path)
        plan = payload.get("plan") if isinstance(payload.get("plan"), Mapping) else {}
        executor = execute_vseeface_plan(
            plan,
            confirm=bool(confirm),
            allow_admin=bool(allow_admin),
            execute=False,
        )
        return {
            "schema": "tigerstudio.actions.vseeface_sidecar_executor_dry_run.v1",
            "project_settings_key": "vseeface_bridge",
            "plan": plan,
            "executor": executor,
        }

    def vseeface_sidecar_workflow(
        self,
        *,
        settings_path: str = "",
        out_path: str = "",
        confirm: bool = False,
        allow_admin: bool = False,
    ) -> dict[str, Any]:
        """Return the full read-only sidecar settings workflow for UI."""
        from app.vtuber.vseeface_bridge import (
            VSeeFaceBridgeConfig,
            build_vseeface_sidecar_workflow,
        )

        config = VSeeFaceBridgeConfig.from_mapping(self._vseeface_bridge_settings())
        workflow = build_vseeface_sidecar_workflow(
            config,
            settings_path=str(settings_path or "") or None,
            out_path=str(out_path or "") or "debugCapture\\vseeface_sidecar_config_report.json",
            confirm=bool(confirm),
            allow_admin=bool(allow_admin),
        )
        return {
            "schema": "tigerstudio.actions.vseeface_sidecar_workflow.v1",
            "project_settings_key": "vseeface_bridge",
            "workflow": workflow,
            "view": workflow.get("view", {}),
        }

    def vseeface_install_plan(
        self,
        *,
        source_zip: str = "",
        download_url: str = "",
        install_dir: str = "",
        out_path: str = "",
    ) -> dict[str, Any]:
        """Return a non-auto-run plan for installing the external VSeeFace sidecar."""
        from app.vtuber.vseeface_bridge import (
            VSeeFaceBridgeConfig,
            build_vseeface_install_plan,
        )

        config = VSeeFaceBridgeConfig.from_mapping(self._vseeface_bridge_settings())
        plan = build_vseeface_install_plan(
            config,
            source_zip=str(source_zip or "") or None,
            download_url=str(download_url or ""),
            install_dir=str(install_dir or "") or None,
            out_path=str(out_path or "") or "debugCapture\\vseeface_install_report.json",
        )
        return {
            "schema": "tigerstudio.actions.vseeface_install_plan.v1",
            "project_settings_key": "vseeface_bridge",
            "plan": plan,
        }

    def vseeface_install_execution_gate(
        self,
        *,
        source_zip: str = "",
        download_url: str = "",
        install_dir: str = "",
        out_path: str = "",
        confirm: bool = False,
        allow_admin: bool = False,
    ) -> dict[str, Any]:
        """Validate whether the install plan can execute, without executing it."""
        from app.vtuber.vseeface_action_plan import build_vseeface_execution_gate

        payload = self.vseeface_install_plan(
            source_zip=source_zip,
            download_url=download_url,
            install_dir=install_dir,
            out_path=out_path,
        )
        plan = payload.get("plan") if isinstance(payload.get("plan"), Mapping) else {}
        gate = build_vseeface_execution_gate(plan, confirm=bool(confirm), allow_admin=bool(allow_admin))
        return {
            "schema": "tigerstudio.actions.vseeface_install_execution_gate.v1",
            "project_settings_key": "vseeface_bridge",
            "plan": plan,
            "gate": gate,
        }

    def vseeface_install_executor_dry_run(
        self,
        *,
        source_zip: str = "",
        download_url: str = "",
        install_dir: str = "",
        out_path: str = "",
        confirm: bool = False,
        allow_admin: bool = False,
    ) -> dict[str, Any]:
        """Return the install executor dry-run report without running tools."""
        from app.vtuber.vseeface_plan_executor import execute_vseeface_plan

        payload = self.vseeface_install_plan(
            source_zip=source_zip,
            download_url=download_url,
            install_dir=install_dir,
            out_path=out_path,
        )
        plan = payload.get("plan") if isinstance(payload.get("plan"), Mapping) else {}
        executor = execute_vseeface_plan(
            plan,
            confirm=bool(confirm),
            allow_admin=bool(allow_admin),
            execute=False,
        )
        return {
            "schema": "tigerstudio.actions.vseeface_install_executor_dry_run.v1",
            "project_settings_key": "vseeface_bridge",
            "plan": plan,
            "executor": executor,
        }

    def vseeface_install_execute(
        self,
        *,
        source_zip: str = "",
        download_url: str = "",
        install_dir: str = "",
        out_path: str = "",
        confirm: bool = False,
        allow_admin: bool = False,
        timeout_s: float = 120.0,
    ) -> dict[str, Any]:
        """Execute the VSeeFace sidecar install plan only after confirmation."""
        from app.vtuber.vseeface_plan_executor import execute_vseeface_plan

        payload = self.vseeface_install_plan(
            source_zip=source_zip,
            download_url=download_url,
            install_dir=install_dir,
            out_path=out_path,
        )
        plan = payload.get("plan") if isinstance(payload.get("plan"), Mapping) else {}
        executor = execute_vseeface_plan(
            plan,
            confirm=bool(confirm),
            allow_admin=bool(allow_admin),
            execute=True,
            timeout_s=max(1.0, float(timeout_s or 120.0)),
        )
        return {
            "schema": "tigerstudio.actions.vseeface_install_execute.v1",
            "project_settings_key": "vseeface_bridge",
            "plan": plan,
            "executor": executor,
        }

    def connect_installed_vseeface_sidecar(self, *, path: str = "", vseeface_exe: str = "") -> dict[str, Any]:
        """Persist the installed sidecar VSeeFace.exe path."""
        from app.vtuber.vseeface_bridge import default_vseeface_exe

        selected = str(path or vseeface_exe or "") or str(default_vseeface_exe())
        result = self.select_vseeface_exe(path=selected)
        result["schema"] = "tigerstudio.actions.vseeface_connect_installed_sidecar.v1"
        result["connected"] = True
        return result

    def select_vseeface_exe(self, *, path: str = "", vseeface_exe: str = "") -> dict[str, Any]:
        """Persist the external VSeeFace executable path."""
        if self.owner is None:
            raise ValueError("no editor owner")
        selected = str(path or vseeface_exe or "").strip()
        if not selected:
            raise ValueError("vseeface_exe path is required")
        exe = Path(selected)
        if not exe.is_file():
            raise ValueError(f"VSeeFace executable not found: {selected}")
        settings = self._updated_vseeface_bridge_settings({"vseeface_exe": str(exe)}, "Select VSeeFace executable")
        return {
            "schema": "tigerstudio.actions.vseeface_select_exe.v1",
            "project_settings_key": "vseeface_bridge",
            "vseeface_exe": str(exe),
            "exists": True,
            "settings": settings.get("vseeface_bridge", {}),
        }

    def select_vseeface_vrm0_avatar(self, *, path: str = "", avatar_vrm: str = "", vrm: str = "") -> dict[str, Any]:
        """Persist a VSeeFace-compatible VRM0 avatar path."""
        if self.owner is None:
            raise ValueError("no editor owner")
        selected = str(path or avatar_vrm or vrm or "").strip()
        if not selected:
            raise ValueError("avatar_vrm path is required")
        avatar = Path(selected)
        if not avatar.is_file():
            raise ValueError(f"VRM avatar not found: {selected}")
        from app.vtuber.vrm_profile import inspect_vrm_profile

        profile = inspect_vrm_profile(avatar)
        if not bool(profile.get("ok")):
            raise ValueError("VRM avatar is invalid")
        if not bool(profile.get("vseeface_compatible")):
            raise ValueError("Avatar must be VRM0 for VSeeFace")
        settings = self._updated_vseeface_bridge_settings({"avatar_vrm": str(avatar)}, "Select VSeeFace VRM0 avatar")
        studio = dict(settings.get("vtuber_studio") if isinstance(settings.get("vtuber_studio"), Mapping) else {})
        studio["avatar_target_id"] = "vrm:vseeface_bridge"
        settings["vtuber_studio"] = studio
        setattr(self.owner, "_project_settings", settings)
        player = getattr(self.owner, "_player", None)
        if player is not None and hasattr(player, "set_project_settings"):
            player.set_project_settings(settings)
        return {
            "schema": "tigerstudio.actions.vseeface_select_vrm0_avatar.v1",
            "project_settings_key": "vseeface_bridge",
            "avatar_target_key": "vtuber_studio.avatar_target_id",
            "selected_avatar_target_id": "vrm:vseeface_bridge",
            "avatar_vrm": str(avatar),
            "vrm": profile,
            "settings": settings.get("vseeface_bridge", {}),
            "vtuber_studio": studio,
        }

    def select_vseeface_capture_backend(
        self,
        *,
        method: str = "",
        window_title_hint: str = "",
        virtual_camera_name: str = "",
        spout_sender_name: str = "",
        framing_preset: str = "",
    ) -> dict[str, Any]:
        """Persist the selected VSeeFace output capture backend."""
        if self.owner is None:
            raise ValueError("no editor owner")
        from app.vtuber.vseeface_bridge import VSeeFaceCaptureConfig

        current = self._vseeface_bridge_settings()
        capture = dict(current.get("capture") if isinstance(current.get("capture"), Mapping) else {})
        if method:
            capture["method"] = str(method)
        if window_title_hint:
            capture["window_title_hint"] = str(window_title_hint)
        if virtual_camera_name:
            capture["virtual_camera_name"] = str(virtual_camera_name)
        if spout_sender_name:
            capture["spout_sender_name"] = str(spout_sender_name)
        if framing_preset:
            capture["framing_preset"] = str(framing_preset)
        normalized = VSeeFaceCaptureConfig.from_mapping(capture).to_dict()
        settings = self._updated_vseeface_bridge_settings({"capture": normalized}, "Select VSeeFace capture backend")
        return {
            "schema": "tigerstudio.actions.vseeface_select_capture_backend.v1",
            "project_settings_key": "vseeface_bridge",
            "capture": normalized,
            "settings": settings.get("vseeface_bridge", {}),
        }

    def select_vseeface_framing(self, *, framing_preset: str = "", framing: str = "") -> dict[str, Any]:
        """Persist the intended VSeeFace broadcast framing preset."""
        if self.owner is None:
            raise ValueError("no editor owner")
        from app.vtuber.vseeface_bridge import VSeeFaceCaptureConfig

        current = self._vseeface_bridge_settings()
        capture = dict(current.get("capture") if isinstance(current.get("capture"), Mapping) else {})
        capture["framing_preset"] = str(framing_preset or framing or "")
        normalized = VSeeFaceCaptureConfig.from_mapping(capture).to_dict()
        settings = self._updated_vseeface_bridge_settings({"capture": normalized}, "Select VSeeFace framing")
        return {
            "schema": "tigerstudio.actions.vseeface_select_framing.v1",
            "project_settings_key": "vseeface_bridge",
            "framing_preset": normalized["framing_preset"],
            "camera": normalized["camera"],
            "capture": normalized,
            "settings": settings.get("vseeface_bridge", {}),
        }

    def select_vseeface_input_source(
        self,
        *,
        source_id: str = "",
        input: Mapping[str, Any] | None = None,
        camera_devices: list[dict[str, Any]] | None = None,
        media_limit: int = 200,
    ) -> dict[str, Any]:
        """Persist the selected VSeeFace/OpenSeeFace tracking input."""
        if self.owner is None:
            raise ValueError("no editor owner")
        sources = self.vseeface_input_sources(
            camera_devices=camera_devices or [],
            media_limit=media_limit,
        )
        selected = None
        input_payload: Mapping[str, Any] | None = input if isinstance(input, Mapping) else None
        if input_payload is None:
            wanted_id = str(source_id or "").strip()
            if not wanted_id:
                raise ValueError("source_id or input is required")
            for option in (sources.get("input_sources") or {}).get("options") or []:
                if isinstance(option, Mapping) and str(option.get("id") or "") == wanted_id:
                    selected = dict(option)
                    candidate = option.get("input")
                    if isinstance(candidate, Mapping):
                        input_payload = candidate
                    break
            if input_payload is None:
                raise ValueError(f"VSeeFace tracking input source not found: {wanted_id}")

        from app.vtuber.vseeface_bridge import VSeeFaceInputConfig

        normalized_input = VSeeFaceInputConfig.from_mapping(input_payload).to_dict()
        settings = dict(getattr(self.owner, "_project_settings", {}) or {})
        bridge_settings = dict(settings.get("vseeface_bridge") if isinstance(settings.get("vseeface_bridge"), Mapping) else {})
        bridge_settings["input"] = normalized_input
        settings["vseeface_bridge"] = bridge_settings
        setattr(self.owner, "_project_settings", settings)
        player = getattr(self.owner, "_player", None)
        if player is not None and hasattr(player, "set_project_settings"):
            player.set_project_settings(settings)
        self._register_change("Select VSeeFace tracking input")
        return {
            "schema": "tigerstudio.actions.vseeface_select_input_source.v1",
            "project_settings_key": "vseeface_bridge",
            "selected_id": str(source_id or normalized_input.get("source_id") or ""),
            "selected": selected or {"id": normalized_input.get("source_id", ""), "input": normalized_input},
            "input": normalized_input,
        }

    def _vseeface_bridge_settings(self) -> dict[str, Any]:
        settings = getattr(self.owner, "_project_settings", {}) if self.owner is not None else {}
        if not isinstance(settings, Mapping):
            return {}
        bridge = settings.get("vseeface_bridge")
        return dict(bridge) if isinstance(bridge, Mapping) else {}

    def _broadcast_output_settings(self) -> dict[str, Any]:
        settings = getattr(self.owner, "_project_settings", {}) if self.owner is not None else {}
        if not isinstance(settings, Mapping):
            return {}
        output = settings.get("broadcast_output")
        return dict(output) if isinstance(output, Mapping) else {}

    def _selected_vtuber_avatar_target_id(self) -> str:
        settings = getattr(self.owner, "_project_settings", {}) if self.owner is not None else {}
        if not isinstance(settings, Mapping):
            return ""
        studio = settings.get("vtuber_studio")
        if isinstance(studio, Mapping):
            return str(studio.get("avatar_target_id") or "")
        return ""

    def _avatar_target_options(self) -> list[dict[str, Any]]:
        options: list[dict[str, Any]] = []
        bridge = self._vseeface_bridge_settings()
        avatar_vrm = str(bridge.get("avatar_vrm") or bridge.get("vrm") or "").strip()
        if avatar_vrm:
            options.append(
                {
                    "id": "vrm:vseeface_bridge",
                    "kind": "vrm_vseeface_bridge",
                    "label": f"VRM / VSeeFace Bridge - {Path(avatar_vrm).name}",
                    "name": Path(avatar_vrm).name,
                    "path": avatar_vrm,
                    "program_output": True,
                    "direct_key_baking": False,
                    "pose_stream": True,
                }
            )
        for track_index, track in enumerate(getattr(self.owner, "_live2d_actor_tracks", []) or []):
            for clip_index, clip in enumerate(getattr(track, "clips", []) or []):
                model_path = str(getattr(clip, "model_path", "") or "")
                name = Path(model_path).name if model_path else f"Live2D Actor {clip_index + 1}"
                options.append(
                    {
                        "id": f"live2d:{track_index}:{clip_index}",
                        "kind": "live2d_actor_clip",
                        "label": f"Live2D - {name}",
                        "name": name,
                        "path": model_path,
                        "track_label": str(getattr(track, "label", "") or f"Live2D {track_index + 1}"),
                        "start_ms": int(getattr(clip, "start_ms", 0) or 0),
                        "end_ms": int(getattr(clip, "end_ms", getattr(clip, "duration_ms", 0)) or 0),
                        "program_output": True,
                        "direct_key_baking": True,
                        "pose_stream": False,
                    }
                )
        return options

    def _default_avatar_target_id(self, options: list[dict[str, Any]]) -> str:
        selected_clip = None
        getter = getattr(self.owner, "_selected_live2d_clip_for_mapping", None)
        if callable(getter):
            try:
                selected_clip = getter()
            except Exception:
                selected_clip = None
        if selected_clip is not None:
            for track_index, track in enumerate(getattr(self.owner, "_live2d_actor_tracks", []) or []):
                for clip_index, clip in enumerate(getattr(track, "clips", []) or []):
                    if clip is selected_clip:
                        return f"live2d:{track_index}:{clip_index}"
        if options:
            return str(options[0].get("id") or "")
        return "none"

    def _updated_vseeface_bridge_settings(self, patch: Mapping[str, Any], label: str) -> dict[str, Any]:
        settings = dict(getattr(self.owner, "_project_settings", {}) or {})
        bridge_settings = dict(settings.get("vseeface_bridge") if isinstance(settings.get("vseeface_bridge"), Mapping) else {})
        bridge_settings.update(dict(patch or {}))
        settings["vseeface_bridge"] = bridge_settings
        setattr(self.owner, "_project_settings", settings)
        player = getattr(self.owner, "_player", None)
        if player is not None and hasattr(player, "set_project_settings"):
            player.set_project_settings(settings)
        self._register_change(label)
        return settings
