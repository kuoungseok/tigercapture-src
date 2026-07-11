"""TTS setup action adapter methods."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


class TtsAdapterMixin:
    """Expose local TTS provider setup/status to actions."""

    def tts_provider_status(self) -> dict[str, Any]:
        from app.tts_setup import tts_provider_status

        return tts_provider_status()

    def tts_setup_instructions(self) -> dict[str, Any]:
        from app.tts_setup import tts_setup_instructions

        return tts_setup_instructions()

    def tts_setup_view(self) -> dict[str, Any]:
        from app.tts_setup import tts_setup_view_model

        return tts_setup_view_model()

    def tts_install_plan(self, *, install_root: str = "") -> dict[str, Any]:
        from app.tts_setup import tts_install_plan

        return tts_install_plan(install_root or None)

    def tts_install_execution_gate(self, *, install_root: str = "") -> dict[str, Any]:
        from app.tts_setup import tts_install_execution_gate

        return tts_install_execution_gate(install_root or None)

    def tts_server_start_plan(self) -> dict[str, Any]:
        from app.tts_setup import tts_server_start_plan

        return tts_server_start_plan()

    def tts_server_ensure_running(
        self,
        *,
        auto_start: bool = True,
        wait_timeout_s: float = 90.0,
    ) -> dict[str, Any]:
        from app.tts_sidecar_runtime import ensure_tts_sidecar_running

        return ensure_tts_sidecar_running(
            auto_start=auto_start,
            wait_timeout_s=wait_timeout_s,
        )

    def tts_connect_installed_sidecar(
        self,
        *,
        root_path: str,
        endpoint: str = "http://127.0.0.1:5000",
        auto_start: bool = False,
    ) -> dict[str, Any]:
        from app.tts_setup import connect_installed_tts

        return connect_installed_tts(root_path, endpoint=endpoint, auto_start=auto_start)

    def tts_voice_list(self) -> dict[str, Any]:
        from app.tts_setup import tts_provider_status
        from app.tts_subtitle_workflow import preferred_model_name

        status = tts_provider_status()
        model_names = list((status.get("root") or {}).get("model_names", []) or [])
        return {
            "ready": bool(status.get("available")),
            "endpoint": str(status.get("endpoint") or ""),
            "models": model_names,
            "default_model": preferred_model_name(status, "zoe"),
        }

    def tts_subtitle_plan(
        self,
        *,
        model_name: str = "",
        subtitle_indices: list[int] | tuple[int, ...] | None = None,
        output_dir: str = "",
        track_id: int | None = None,
        track_name: str = "",
    ) -> dict[str, Any]:
        from app.tts_subtitle_workflow import TTS_DIALOGUE_TRACK_NAME, build_subtitle_tts_plan

        return build_subtitle_tts_plan(
            self._require_owner(),
            model_name=model_name,
            subtitle_indices=subtitle_indices,
            output_dir=output_dir or None,
            track_id=track_id,
            track_name=track_name or TTS_DIALOGUE_TRACK_NAME,
        )

    def tts_generate_subtitle_track(
        self,
        *,
        model_name: str = "",
        subtitle_indices: list[int] | tuple[int, ...] | None = None,
        output_dir: str = "",
        track_id: int | None = None,
        track_name: str = "",
        replace_existing: bool = True,
        language: str = "",
        style: str = "",
        style_weight: float | None = None,
        sdp_ratio: float | None = None,
        noise: float | None = None,
        noisew: float | None = None,
        length: float | None = None,
        timeout_s: float = 120.0,
        auto_start_server: bool = True,
        server_wait_timeout_s: float = 90.0,
        apply_actor_lipsync: bool = False,
        actor_track_id: int | None = None,
        actor_clip_index: int = 0,
        lipsync_param_id: str = "ParamMouthOpenY",
        lipsync_form_param_id: str = "ParamMouthForm",
        lipsync_open_value: float = 0.82,
    ) -> dict[str, Any]:
        from app.audio_tracks import AudioClip, AudioTrack
        from app.tts_subtitle_workflow import (
            TTS_DIALOGUE_TRACK_NAME,
            build_subtitle_tts_plan,
            synthesize_subtitle_rows,
        )

        owner = self._require_owner()
        plan = build_subtitle_tts_plan(
            owner,
            model_name=model_name,
            subtitle_indices=subtitle_indices,
            output_dir=output_dir or None,
            track_id=track_id,
            track_name=track_name or TTS_DIALOGUE_TRACK_NAME,
        )
        if not bool(plan.get("ready")):
            from app.tts_sidecar_runtime import format_tts_sidecar_guidance

            raise RuntimeError(
                format_tts_sidecar_guidance(
                    plan.get("guidance") if isinstance(plan.get("guidance"), dict) else None,
                    fallback="TTS provider is not ready. Start or connect the Style-Bert-VITS2 sidecar first.",
                )
            )
        rows = list(plan.get("rows") or [])
        if not rows:
            raise ValueError("No subtitles are available for TTS generation.")
        selected_model = str(plan.get("model_name") or model_name or "")
        if not selected_model:
            raise ValueError("No TTS voice model is available.")

        server = {"ready": False, "started": False, "message": "TTS server was not checked."}
        if auto_start_server:
            from app.tts_sidecar_runtime import ensure_tts_sidecar_running

            server = ensure_tts_sidecar_running(
                auto_start=True,
                wait_timeout_s=server_wait_timeout_s,
            )
            if not bool(server.get("ready")):
                from app.tts_sidecar_runtime import format_tts_sidecar_guidance

                raise RuntimeError(
                    format_tts_sidecar_guidance(
                        server.get("guidance") if isinstance(server.get("guidance"), dict) else None,
                        fallback=str(server.get("message") or server.get("error") or "TTS server is not ready."),
                    )
                )

        generated = synthesize_subtitle_rows(
            rows,
            endpoint=str(plan.get("endpoint") or ""),
            model_name=selected_model,
            output_dir=output_dir or None,
            batch_id=str(plan.get("batch_id") or ""),
            language=language,
            style=style,
            style_weight=style_weight,
            sdp_ratio=sdp_ratio,
            noise=noise,
            noisew=noisew,
            length=length,
            timeout_s=timeout_s,
        )

        tracks = list(getattr(owner, "_audio_tracks", []) or [])
        created_track = False
        if track_id is not None:
            audio_track = self._audio_track(int(track_id))
        else:
            wanted_label = str(track_name or TTS_DIALOGUE_TRACK_NAME)
            audio_track = next(
                (
                    track
                    for track in tracks
                    if str(getattr(track, "label", "") or getattr(track, "display_name", "")).casefold()
                    == wanted_label.casefold()
                ),
                None,
            )
            if audio_track is None:
                audio_track = AudioTrack(id=self._next_track_id(tracks), label=wanted_label)
                tracks.append(audio_track)
                setattr(owner, "_audio_tracks", tracks)
                self._advance_owner_next_track_id(int(getattr(audio_track, "id", 0) or 0))
                created_track = True
        try:
            setattr(audio_track, "track_type", "dialogue")
            setattr(audio_track, "bus_id", "dialogue")
        except Exception:
            pass

        clips = getattr(audio_track, "clips", None)
        if not isinstance(clips, list):
            audio_track.clips = []
            clips = audio_track.clips
        if replace_existing:
            output_root = Path(str(plan.get("output_dir") or output_dir or "")).resolve()

            def _keep_clip(clip: Any) -> bool:
                if bool(getattr(clip, "_tts_generated", False)):
                    return False
                source_path = getattr(clip, "source_path", None)
                if source_path is None:
                    return True
                try:
                    resolved = Path(source_path).resolve()
                    if resolved.is_relative_to(output_root):
                        return False
                except Exception:
                    pass
                return True

            audio_track.clips = [clip for clip in clips if _keep_clip(clip)]
            clips = audio_track.clips

        added: list[dict[str, Any]] = []
        first_sync = True
        for row in generated:
            media_path = Path(str(row.get("path") or "")).expanduser()
            if not media_path.is_file():
                raise RuntimeError(f"Generated TTS file is missing: {media_path}")
            duration = max(1, int(row.get("generated_duration_ms") or row.get("duration_ms") or 1))
            clip = AudioClip(
                id=self._next_audio_clip_id(),
                source_path=media_path.resolve(),
                duration_ms=duration,
                offset_ms=max(0, int(row.get("start_ms") or 0)),
                trim_start_ms=0,
                trim_end_ms=duration,
            )
            setattr(clip, "_tts_generated", True)
            setattr(clip, "_tts_subtitle_index", int(row.get("index") or 0))
            setattr(clip, "_tts_subtitle_text", str(row.get("text") or ""))
            setattr(clip, "_tts_model_name", selected_model)
            clips.append(clip)
            self._register_media_path(media_path)
            self._sync_audio_track_ui(audio_track, created=created_track and first_sync, clip=clip)
            first_sync = False
            added.append(
                {
                    "subtitle_index": int(row.get("index") or 0),
                    "text": str(row.get("text") or ""),
                    "path": str(media_path.resolve()),
                    "track_id": int(getattr(audio_track, "id", 0) or 0),
                    "clip_id": int(getattr(clip, "id", 0) or 0),
                    "timeline_in_ms": int(getattr(clip, "offset_ms", 0) or 0),
                    "duration_ms": duration,
                }
            )
        clips.sort(key=lambda item: int(getattr(item, "offset_ms", 0) or 0))
        if created_track and first_sync:
            self._sync_audio_track_ui(audio_track, created=True, clip=None)
        actor_lipsync: dict[str, Any] = {"applied": False, "reason": "not_requested"}
        if bool(apply_actor_lipsync):
            if actor_track_id is None:
                actor_lipsync = {"applied": False, "reason": "missing_actor_track_id"}
            else:
                actor_lipsync = self.tts_apply_actor_lipsync(
                    actor_track_id=int(actor_track_id),
                    actor_clip_index=int(actor_clip_index or 0),
                    rows=added,
                    replace_existing=True,
                    mouth_param_id=lipsync_param_id,
                    mouth_form_param_id=lipsync_form_param_id,
                    open_value=lipsync_open_value,
                )
        self._after_timeline_mutation("Generate TTS subtitle track")
        return {
            "provider_id": plan.get("provider_id"),
            "model_name": selected_model,
            "track_id": int(getattr(audio_track, "id", 0) or 0),
            "track_name": str(getattr(audio_track, "label", "") or track_name or TTS_DIALOGUE_TRACK_NAME),
            "clip_count": len(added),
            "replace_existing": bool(replace_existing),
            "output_dir": str(plan.get("output_dir") or ""),
            "batch_id": str(plan.get("batch_id") or ""),
            "server": server,
            "clips": added,
            "actor_lipsync": actor_lipsync,
        }

    def tts_apply_actor_lipsync(
        self,
        *,
        actor_track_id: int,
        actor_clip_index: int = 0,
        rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
        replace_existing: bool = True,
        use_generated_clips: bool = True,
        mouth_param_id: str = "ParamMouthOpenY",
        mouth_form_param_id: str = "ParamMouthForm",
        open_value: float = 0.82,
    ) -> dict[str, Any]:
        """Bake TTS/subtitle timing into a Live2D actor mouth parameter track."""
        _track, clip = self._actor_track_and_clip("live2d", int(actor_track_id), int(actor_clip_index or 0))
        source_rows = [dict(row) for row in (rows or []) if isinstance(row, Mapping)]
        source = "provided_rows"
        if not source_rows:
            source_rows = self._tts_lipsync_rows_from_owner(use_generated_clips=bool(use_generated_clips))
            source = "generated_tts_clips" if source_rows and bool(use_generated_clips) else "subtitles"
        if not source_rows:
            raise ValueError("No TTS clips or subtitle rows are available for actor lip-sync.")

        from app.tts_actor_lipsync import build_tts_actor_lipsync_payload

        payload = build_tts_actor_lipsync_payload(
            source_rows,
            actor_start_ms=int(getattr(clip, "start_ms", 0) or 0),
            actor_duration_ms=int(getattr(clip, "duration_ms", 0) or 0),
            mouth_param_id=mouth_param_id,
            mouth_form_param_id=mouth_form_param_id,
            open_value=float(open_value),
        )
        if not bool(payload.get("ok")):
            raise ValueError("TTS lip-sync produced no actor keyframes.")

        existing = dict(getattr(clip, "parameter_keyframes", {}) or {})
        generated_tracks = dict(payload.get("parameter_keyframes") or {})
        if bool(replace_existing):
            for param_id in generated_tracks:
                existing.pop(str(param_id), None)
        for param_id, keys in generated_tracks.items():
            current = [] if bool(replace_existing) else list(existing.get(param_id) or [])
            current.extend(list(keys or []))
            current.sort(key=lambda row: int(row.get("time_ms", 0) or 0) if isinstance(row, Mapping) else 0)
            existing[str(param_id)] = current
        clip.parameter_keyframes = existing
        clip.tts_lipsync_payload = dict(payload)
        clip.tts_lipsync_source = source
        self._sync_actor_tracks("live2d")
        self._after_timeline_mutation("Apply TTS actor lip-sync")
        return {
            "applied": True,
            "schema": payload.get("schema"),
            "actor_track_id": int(actor_track_id),
            "actor_clip_index": int(actor_clip_index or 0),
            "source": source,
            "row_count": int(payload.get("row_count", 0) or 0),
            "parameter_tracks": list(generated_tracks.keys()),
            "keyframe_count": sum(len(list(keys or [])) for keys in generated_tracks.values()),
        }

    def _tts_lipsync_rows_from_owner(self, *, use_generated_clips: bool = True) -> list[dict[str, Any]]:
        owner = self._require_owner()
        rows: list[dict[str, Any]] = []
        if bool(use_generated_clips):
            for audio_track in getattr(owner, "_audio_tracks", []) or []:
                for clip in getattr(audio_track, "clips", []) or []:
                    if not bool(getattr(clip, "_tts_generated", False)):
                        continue
                    start_ms = max(0, int(getattr(clip, "offset_ms", 0) or 0))
                    duration_ms = max(
                        1,
                        int(
                            getattr(clip, "trim_end_ms", 0)
                            or getattr(clip, "duration_ms", 0)
                            or 1
                        ),
                    )
                    rows.append(
                        {
                            "subtitle_index": int(getattr(clip, "_tts_subtitle_index", len(rows)) or 0),
                            "timeline_in_ms": start_ms,
                            "duration_ms": duration_ms,
                            "text": str(getattr(clip, "_tts_subtitle_text", "") or ""),
                            "clip_id": int(getattr(clip, "id", 0) or 0),
                            "audio_track_id": int(getattr(audio_track, "id", 0) or 0),
                        }
                    )
            rows.sort(key=lambda row: (int(row.get("timeline_in_ms", 0) or 0), int(row.get("subtitle_index", 0) or 0)))
            if rows:
                return rows
        try:
            from app.tts_subtitle_workflow import subtitle_rows_from_owner

            return subtitle_rows_from_owner(owner)
        except Exception:
            return []
