"""TTS setup action adapter methods."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping


class TtsAdapterMixin:
    """Expose local TTS provider setup/status to actions."""

    def tts_provider_status(self, *, provider_id: str = "") -> dict[str, Any]:
        from app.tts_setup import tts_provider_status

        return tts_provider_status(provider_id=provider_id) if provider_id else tts_provider_status()

    def tts_select_provider(self, *, provider_id: str) -> dict[str, Any]:
        from app.tts_setup import save_tts_selected_provider, tts_provider_status

        saved = save_tts_selected_provider(provider_id)
        status = tts_provider_status(provider_id=provider_id) if provider_id else tts_provider_status()
        return {
            "ok": bool(saved),
            "saved": bool(saved),
            "provider_id": status.get("provider_id", provider_id),
            "status": status,
        }

    def tts_setup_instructions(self, *, provider_id: str = "") -> dict[str, Any]:
        from app.tts_setup import tts_setup_instructions

        return tts_setup_instructions(provider_id=provider_id) if provider_id else tts_setup_instructions()

    def tts_setup_view(self, *, provider_id: str = "") -> dict[str, Any]:
        from app.tts_setup import tts_setup_view_model

        return tts_setup_view_model(provider_id=provider_id) if provider_id else tts_setup_view_model()

    def tts_voice_library_catalog(self) -> dict[str, Any]:
        from app.tts_setup import tts_voice_library_catalog

        return tts_voice_library_catalog()

    def tts_install_plan(self, *, install_root: str = "", provider_id: str = "") -> dict[str, Any]:
        from app.tts_setup import tts_install_plan

        return tts_install_plan(install_root or None, provider_id=provider_id)

    def tts_install_execution_gate(self, *, install_root: str = "", provider_id: str = "") -> dict[str, Any]:
        from app.tts_setup import tts_install_execution_gate

        return tts_install_execution_gate(install_root or None, provider_id=provider_id)

    def tts_server_start_plan(self, *, provider_id: str = "") -> dict[str, Any]:
        from app.tts_setup import tts_server_start_plan

        return tts_server_start_plan(provider_id=provider_id)

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
        provider_id: str = "",
        endpoint: str = "http://127.0.0.1:5000",
        auto_start: bool = False,
    ) -> dict[str, Any]:
        from app.tts_setup import connect_installed_tts_provider

        return connect_installed_tts_provider(root_path, provider_id=provider_id, endpoint=endpoint, auto_start=auto_start)

    def tts_model_training_plan(
        self,
        *,
        model_name: str = "",
        source_audio_dir: str = "",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        from app.tts_model_training import tts_model_training_plan

        return tts_model_training_plan(model_name=model_name, source_audio_dir=source_audio_dir)

    def tts_model_training_execution_gate(
        self,
        *,
        model_name: str = "",
        source_audio_dir: str = "",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        from app.tts_model_training import tts_model_training_execution_gate

        return tts_model_training_execution_gate(model_name=model_name, source_audio_dir=source_audio_dir)

    def tts_model_training_prepare_workspace(
        self,
        *,
        model_name: str,
        source_audio_dir: str = "",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        from app.tts_model_training import tts_model_training_prepare_workspace

        return tts_model_training_prepare_workspace(
            model_name=model_name,
            source_audio_dir=source_audio_dir,
            overwrite=overwrite,
        )

    def tts_model_training_launch_dataset(
        self,
        *,
        model_name: str = "",
        source_audio_dir: str = "",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        from app.tts_model_training import tts_model_training_launch_tool

        return tts_model_training_launch_tool(tool="dataset", model_name=model_name, source_audio_dir=source_audio_dir)

    def tts_model_training_launch_train(
        self,
        *,
        model_name: str = "",
        source_audio_dir: str = "",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        from app.tts_model_training import tts_model_training_launch_tool

        return tts_model_training_launch_tool(tool="train", model_name=model_name, source_audio_dir=source_audio_dir)

    def tts_model_training_register_result(
        self,
        *,
        model_name: str,
    ) -> dict[str, Any]:
        from app.tts_model_training import tts_model_training_register_result

        return tts_model_training_register_result(model_name=model_name)

    def tts_voice_list(self, *, provider_id: str = "") -> dict[str, Any]:
        from app.tts_setup import tts_provider_status
        from app.tts_subtitle_workflow import preferred_model_name

        status = tts_provider_status(provider_id=provider_id) if provider_id else tts_provider_status()
        model_names = list((status.get("root") or {}).get("model_names", []) or [])
        return {
            "ready": bool(status.get("available")),
            "provider_id": status.get("provider_id", provider_id),
            "endpoint": str(status.get("endpoint") or ""),
            "models": model_names,
            "default_model": preferred_model_name(status, "koharune-ami"),
        }

    def tts_subtitle_plan(
        self,
        *,
        provider_id: str = "",
        model_name: str = "",
        subtitle_indices: list[int] | tuple[int, ...] | None = None,
        output_dir: str = "",
        track_id: int | None = None,
        track_name: str = "",
    ) -> dict[str, Any]:
        from app.tts_subtitle_workflow import TTS_DIALOGUE_TRACK_NAME, build_subtitle_tts_plan

        return build_subtitle_tts_plan(
            self._require_owner(),
            provider_id=provider_id,
            model_name=model_name,
            subtitle_indices=subtitle_indices,
            output_dir=output_dir or None,
            track_id=track_id,
            track_name=track_name or TTS_DIALOGUE_TRACK_NAME,
        )

    def tts_dialogue_plan_actor_take(
        self,
        *,
        provider_id: str = "",
        dialogue_text: str = "",
        lines: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
        start_ms: int = 0,
        default_duration_ms: int = 1800,
        gap_ms: int = 160,
        chars_per_second: float = 12.0,
    ) -> dict[str, Any]:
        """Return selectable choices for a one-shot AI dialogue take."""
        from app.live2d.dialogue_placement import placement_preset_options, size_preset_options
        from app.tts_setup import tts_provider_status
        from app.tts_subtitle_workflow import preferred_dialogue_model_name

        rows = self._tts_dialogue_rows(
            dialogue_text=dialogue_text,
            lines=lines,
            start_ms=start_ms,
            default_duration_ms=default_duration_ms,
            gap_ms=gap_ms,
            chars_per_second=chars_per_second,
        )
        status = tts_provider_status(provider_id=provider_id) if provider_id else tts_provider_status()
        model_names = list((status.get("root") or {}).get("model_names", []) or [])
        default_model = preferred_dialogue_model_name(status, rows)
        tts_models = [
            {
                "id": str(name),
                "label": str(name),
                "ready": bool(status.get("available")),
                "recommended": str(name) == default_model,
            }
            for name in model_names
        ]
        live2d_targets = self._tts_live2d_target_options()
        default_target = next((row for row in live2d_targets if row.get("recommended")), live2d_targets[0] if live2d_targets else {})
        placement_presets = placement_preset_options()
        size_presets = size_preset_options()
        return {
            "schema": "tigerstudio.tts.dialogue_actor_take_plan.v1",
            "dialogue": {
                "line_count": len(rows),
                "start_ms": min((int(row.get("start_ms", 0) or 0) for row in rows), default=max(0, int(start_ms or 0))),
                "end_ms": max((int(row.get("end_ms", 0) or 0) for row in rows), default=max(0, int(start_ms or 0))),
                "estimated_duration_ms": self._tts_dialogue_take_duration(rows),
                "rows": rows,
            },
            "live2d_targets": live2d_targets,
            "tts_models": tts_models,
            "placement_presets": placement_presets,
            "size_presets": size_presets,
            "recommended": {
                "actor_target_id": str(default_target.get("id") or ""),
                "model_name": default_model,
                "placement_preset": "bottom_right",
                "size_preset": "auto_fit",
                "create_subtitles": True,
                "generate_tts": True,
                "apply_actor_lipsync": True,
                "apply_actor_placement": True,
                "apply_actor_motion": True,
                "actor_motion_style": "natural_dialogue",
                "fit_avatar_to_bottom_edge": True,
            },
            "diagnostics": {
                "tts_ready": bool(status.get("available")),
                "tts_provider_id": str(status.get("provider_id") or ""),
                "tts_endpoint": str(status.get("endpoint") or ""),
                "live2d_target_count": len(live2d_targets),
                "tts_model_count": len(tts_models),
            },
        }

    def tts_generate_subtitle_track(
        self,
        *,
        provider_id: str = "",
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
        lipsync_include_blink: bool = True,
        lipsync_blink_left_param_id: str = "ParamEyeLOpen",
        lipsync_blink_right_param_id: str = "ParamEyeROpen",
        lipsync_blink_interval_ms: int = 3100,
        lipsync_blink_duration_ms: int = 140,
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
            provider_id=provider_id,
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

        requires_server = bool(plan.get("requires_server", True))
        server = {
            "ready": not requires_server,
            "started": False,
            "message": "TTS provider runs in-process; no server was needed." if not requires_server else "TTS server was not checked.",
        }
        if auto_start_server and requires_server:
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
            provider_id=str(plan.get("provider_id") or provider_id or ""),
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
            setattr(clip, "_tts_subtitle_text", str(row.get("tts_text") or row.get("text") or ""))
            setattr(clip, "_tts_spoken_text", str(row.get("tts_text") or row.get("text") or ""))
            setattr(clip, "_tts_display_text", str(row.get("subtitle_text") or row.get("display_text") or row.get("text") or ""))
            setattr(clip, "_tts_model_name", selected_model)
            clips.append(clip)
            self._register_media_path(media_path)
            self._sync_audio_track_ui(audio_track, created=created_track and first_sync, clip=clip)
            first_sync = False
            spoken_text = str(row.get("tts_text") or row.get("text") or "")
            display_text = str(row.get("subtitle_text") or row.get("display_text") or spoken_text)
            added.append(
                {
                    "subtitle_index": int(row.get("index") or 0),
                    "text": spoken_text,
                    "tts_text": spoken_text,
                    "subtitle_text": display_text,
                    "display_text": display_text,
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
                    include_blink=lipsync_include_blink,
                    blink_left_param_id=lipsync_blink_left_param_id,
                    blink_right_param_id=lipsync_blink_right_param_id,
                    blink_interval_ms=lipsync_blink_interval_ms,
                    blink_duration_ms=lipsync_blink_duration_ms,
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
        include_blink: bool = True,
        blink_left_param_id: str = "ParamEyeLOpen",
        blink_right_param_id: str = "ParamEyeROpen",
        blink_interval_ms: int = 3100,
        blink_duration_ms: int = 140,
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
            include_blink=bool(include_blink),
            blink_left_param_id=blink_left_param_id,
            blink_right_param_id=blink_right_param_id,
            blink_interval_ms=int(blink_interval_ms or 3100),
            blink_duration_ms=int(blink_duration_ms or 140),
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
            "blink_count": int(payload.get("blink_count", 0) or 0),
        }

    def tts_dialogue_generate_actor_take(
        self,
        *,
        dialogue_text: str = "",
        lines: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
        start_ms: int = 0,
        default_duration_ms: int = 1800,
        gap_ms: int = 160,
        chars_per_second: float = 12.0,
        create_subtitles: bool = True,
        provider_id: str = "",
        model_name: str = "",
        output_dir: str = "",
        track_id: int | None = None,
        track_name: str = "TTS Dialogue",
        replace_existing: bool = False,
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
        apply_actor_lipsync: bool = True,
        actor_target_id: str = "",
        actor_track_id: int | None = None,
        actor_clip_index: int = 0,
        apply_actor_placement: bool = True,
        apply_actor_motion: bool = True,
        actor_motion_style: str = "natural_dialogue",
        actor_motion_interval_ms: int = 700,
        placement_preset: str = "bottom_right",
        size_preset: str = "auto_fit",
        canvas_width: int = 1920,
        canvas_height: int = 1080,
        placement_sample_ms: int = 0,
        placement_replace_transform_keyframes: bool = True,
        lipsync_param_id: str = "ParamMouthOpenY",
        lipsync_form_param_id: str = "ParamMouthForm",
        lipsync_open_value: float = 0.82,
        lipsync_include_blink: bool = True,
        lipsync_blink_left_param_id: str = "ParamEyeLOpen",
        lipsync_blink_right_param_id: str = "ParamEyeROpen",
        lipsync_blink_interval_ms: int = 3100,
        lipsync_blink_duration_ms: int = 140,
    ) -> dict[str, Any]:
        """Create subtitles, TTS audio, Live2D placement, and natural acting keys."""
        owner = self._require_owner()
        rows = self._tts_dialogue_rows(
            dialogue_text=dialogue_text,
            lines=lines,
            start_ms=start_ms,
            default_duration_ms=default_duration_ms,
            gap_ms=gap_ms,
            chars_per_second=chars_per_second,
        )
        if not rows:
            raise ValueError("No dialogue text is available.")

        subtitle_indices: list[int] | None = None
        subtitle_result: dict[str, Any] = {"created": False, "count": 0, "indices": []}
        if bool(create_subtitles):
            subtitle_result = self._tts_append_subtitle_rows(rows)
            subtitle_indices = [int(index) for index in subtitle_result.get("indices", [])]
        else:
            subtitle_indices = [int(row.get("index", idx) or idx) for idx, row in enumerate(rows)]

        target = {"found": False, "track_id": actor_track_id, "clip_index": int(actor_clip_index or 0)}
        if bool(apply_actor_lipsync) or bool(apply_actor_placement) or bool(apply_actor_motion):
            target = self._tts_resolve_live2d_actor_target(
                actor_target_id=actor_target_id,
                actor_track_id=actor_track_id,
                actor_clip_index=actor_clip_index,
                start_ms=max(0, int(start_ms or 0)),
                duration_ms=self._tts_dialogue_take_duration(rows),
            )
            actor_track_id = target.get("track_id") if target.get("found") else None
            actor_clip_index = int(target.get("clip_index", actor_clip_index) or 0)

        selected_model_name = str(model_name or "").strip()
        if not selected_model_name:
            from app.tts_setup import tts_provider_status
            from app.tts_subtitle_workflow import preferred_dialogue_model_name

            selected_model_name = preferred_dialogue_model_name(
                tts_provider_status(provider_id=provider_id) if provider_id else tts_provider_status(),
                rows,
                language=language,
            )

        placement_result: dict[str, Any] = {"applied": False, "reason": "not_requested"}
        if bool(apply_actor_placement) and actor_track_id is not None:
            placement_result = self._tts_apply_live2d_dialogue_placement(
                actor_track_id=int(actor_track_id),
                actor_clip_index=int(actor_clip_index or 0),
                placement_preset=placement_preset,
                size_preset=size_preset,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                sample_ms=placement_sample_ms,
                replace_transform_keyframes=placement_replace_transform_keyframes,
            )

        motion_result: dict[str, Any] = {"applied": False, "reason": "not_requested"}
        if bool(apply_actor_motion) and actor_track_id is not None:
            motion_result = self._tts_apply_live2d_dialogue_motion(
                actor_track_id=int(actor_track_id),
                actor_clip_index=int(actor_clip_index or 0),
                rows=rows,
                style=actor_motion_style,
                interval_ms=actor_motion_interval_ms,
            )

        tts_result = self.tts_generate_subtitle_track(
            provider_id=provider_id,
            model_name=selected_model_name,
            subtitle_indices=subtitle_indices,
            output_dir=output_dir,
            track_id=track_id,
            track_name=track_name,
            replace_existing=replace_existing,
            language=language,
            style=style,
            style_weight=style_weight,
            sdp_ratio=sdp_ratio,
            noise=noise,
            noisew=noisew,
            length=length,
            timeout_s=timeout_s,
            auto_start_server=auto_start_server,
            server_wait_timeout_s=server_wait_timeout_s,
            apply_actor_lipsync=bool(apply_actor_lipsync and actor_track_id is not None),
            actor_track_id=int(actor_track_id) if actor_track_id is not None else None,
            actor_clip_index=int(actor_clip_index or 0),
            lipsync_param_id=lipsync_param_id,
            lipsync_form_param_id=lipsync_form_param_id,
            lipsync_open_value=lipsync_open_value,
            lipsync_include_blink=lipsync_include_blink,
            lipsync_blink_left_param_id=lipsync_blink_left_param_id,
            lipsync_blink_right_param_id=lipsync_blink_right_param_id,
            lipsync_blink_interval_ms=lipsync_blink_interval_ms,
            lipsync_blink_duration_ms=lipsync_blink_duration_ms,
        )
        if bool(apply_actor_lipsync) and actor_track_id is None:
            tts_result["actor_lipsync"] = {"applied": False, "reason": "no_live2d_actor"}
        authored_storyboard_result: dict[str, Any] = {"applied": False, "reason": "not_requested"}
        if bool(apply_actor_motion) and actor_track_id is not None:
            try:
                actor_track, actor_clip = self._actor_track_and_clip(
                    "live2d",
                    int(actor_track_id),
                    int(actor_clip_index or 0),
                )
                from app.live2d.dialogue_motion import apply_authored_dialogue_motion_storyboard_to_track

                authored_storyboard_result = apply_authored_dialogue_motion_storyboard_to_track(
                    actor_track,
                    actor_clip,
                    rows=rows,
                )
                if bool(authored_storyboard_result.get("applied")):
                    self._sync_actor_tracks("live2d")
            except Exception as exc:
                authored_storyboard_result = {"applied": False, "reason": str(exc)}
        if bool(apply_actor_motion):
            motion_result["authored_storyboard"] = authored_storyboard_result
        return {
            "schema": "tigercapture.tts_dialogue_actor_take.v1",
            "dialogue_line_count": len(rows),
            "subtitles": subtitle_result,
            "actor_target": target,
            "placement": placement_result,
            "actor_motion": motion_result,
            "tts": tts_result,
            "actor_lipsync": dict(tts_result.get("actor_lipsync") or {}),
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
                    spoken_text = str(
                        getattr(clip, "_tts_spoken_text", None)
                        or getattr(clip, "_tts_subtitle_text", "")
                        or ""
                    )
                    display_text = str(
                        getattr(clip, "_tts_display_text", None)
                        or getattr(clip, "_tts_subtitle_text", "")
                        or spoken_text
                    )
                    rows.append(
                        {
                            "subtitle_index": int(getattr(clip, "_tts_subtitle_index", len(rows)) or 0),
                            "timeline_in_ms": start_ms,
                            "duration_ms": duration_ms,
                            "text": spoken_text,
                            "tts_text": spoken_text,
                            "subtitle_text": display_text,
                            "display_text": display_text,
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

    def _tts_dialogue_rows(
        self,
        *,
        dialogue_text: str = "",
        lines: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
        start_ms: int = 0,
        default_duration_ms: int = 1800,
        gap_ms: int = 160,
        chars_per_second: float = 12.0,
    ) -> list[dict[str, Any]]:
        cursor = max(0, int(start_ms or 0))
        gap = max(0, int(gap_ms or 0))
        default_duration = max(300, int(default_duration_ms or 1800))
        cps = max(4.0, float(chars_per_second or 12.0))
        source_lines: list[Mapping[str, Any]]
        if lines:
            source_lines = [dict(row) for row in lines if isinstance(row, Mapping)]
        else:
            source_lines = [
                self._tts_dialogue_line_mapping(text.strip())
                for text in str(dialogue_text or "").splitlines()
                if text.strip()
            ]

        rows: list[dict[str, Any]] = []
        from app.tts_subtitle_workflow import split_subtitle_tts_text

        for index, raw in enumerate(source_lines):
            style = dict(raw.get("style") or {})
            base_text = str(
                raw.get("text")
                or raw.get("dialogue")
                or raw.get("tts_text")
                or raw.get("spoken_text")
                or raw.get("subtitle_text")
                or raw.get("display_text")
                or ""
            ).strip()
            display_text, tts_text = split_subtitle_tts_text(base_text, style=style, row=raw)
            if not display_text and not tts_text:
                continue
            row_start = int(raw.get("start_ms", raw.get("timeline_in_ms", cursor)) or cursor)
            if "end_ms" in raw:
                row_end = max(row_start + 1, int(raw.get("end_ms") or row_start + default_duration))
                duration = row_end - row_start
            else:
                estimated = int(round(len(tts_text or display_text) / cps * 1000.0)) + 450
                duration = max(700, min(6200, int(raw.get("duration_ms", estimated) or estimated)))
                if "duration_ms" not in raw:
                    duration = max(duration, min(3200, default_duration))
                row_end = row_start + duration
            rows.append(
                {
                    "index": index,
                    "start_ms": max(0, row_start),
                    "end_ms": max(row_start + 1, row_end),
                    "duration_ms": max(1, duration),
                    "text": tts_text,
                    "tts_text": tts_text,
                    "subtitle_text": display_text,
                    "display_text": display_text,
                    "style": style,
                }
            )
            cursor = max(cursor, row_end + gap)
        return rows

    @staticmethod
    def _tts_dialogue_line_mapping(text: str) -> dict[str, str]:
        raw = str(text or "").strip()
        for separator in ("=>", "->", "||", "\t"):
            if separator not in raw:
                continue
            spoken, display = raw.split(separator, 1)
            spoken = spoken.strip()
            display = display.strip()
            if spoken and display:
                return {"tts_text": spoken, "subtitle_text": display}
        return {"text": raw}

    def _tts_dialogue_take_duration(self, rows: list[Mapping[str, Any]]) -> int:
        if not rows:
            return 3000
        start = min(max(0, int(row.get("start_ms", 0) or 0)) for row in rows)
        end = max(max(start + 1, int(row.get("end_ms", start + 1) or start + 1)) for row in rows)
        return max(1, end - start)

    def _tts_path_is_live2d_model(self, path: str) -> bool:
        name = Path(str(path or "")).name.casefold()
        return bool(name.endswith(".model3.json"))

    def _tts_media_pool_live2d_paths(self) -> list[str]:
        owner = self._require_owner()
        pool = getattr(owner, "_media_pool", None)
        rows: list[str] = []
        metadata = getattr(pool, "media_pool_metadata", None)
        if callable(metadata):
            try:
                for item in metadata() or []:
                    path = str(item.get("path") or "") if isinstance(item, Mapping) else ""
                    if path and self._tts_path_is_live2d_model(path):
                        rows.append(path)
            except Exception:
                pass
        for attr in ("_media_paths", "_project_media_paths", "_imported_media_paths"):
            for raw in getattr(owner, attr, []) or []:
                path = str(raw or "")
                if path and self._tts_path_is_live2d_model(path):
                    rows.append(path)
        deduped: list[str] = []
        seen: set[str] = set()
        for path in rows:
            key = str(Path(path).expanduser()).casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(path)
        return deduped

    def _tts_live2d_target_options(self) -> list[dict[str, Any]]:
        owner = self._require_owner()
        selected_clip = None
        getter = getattr(owner, "_selected_live2d_clip_for_mapping", None)
        if callable(getter):
            try:
                selected_clip = getter()
            except Exception:
                selected_clip = None
        options: list[dict[str, Any]] = []
        for track_index, track in enumerate(getattr(owner, "_live2d_actor_tracks", []) or []):
            track_id = int(getattr(track, "id", track_index) or track_index)
            for clip_index, clip in enumerate(getattr(track, "clips", []) or []):
                model_path = str(getattr(clip, "model_path", "") or "")
                name = Path(model_path).name if model_path else f"Live2D Actor {clip_index + 1}"
                options.append(
                    {
                        "id": f"live2d:{track_id}:{clip_index}",
                        "kind": "live2d_actor_clip",
                        "label": f"Live2D - {name}",
                        "name": name,
                        "path": model_path,
                        "track_id": track_id,
                        "track_index": track_index,
                        "clip_index": clip_index,
                        "track_label": str(getattr(track, "label", "") or f"Live2D {track_index + 1}"),
                        "start_ms": int(getattr(clip, "start_ms", 0) or 0),
                        "end_ms": int(getattr(clip, "end_ms", getattr(clip, "duration_ms", 0)) or 0),
                        "ready": bool(model_path),
                        "source": "timeline",
                        "direct_key_baking": True,
                        "recommended": clip is selected_clip,
                    }
                )
        if options and not any(row.get("recommended") for row in options):
            options[0]["recommended"] = True
        for index, path in enumerate(self._tts_media_pool_live2d_paths()):
            options.append(
                {
                    "id": f"media_live2d:{index}",
                    "kind": "live2d_model_asset",
                    "label": f"Live2D Asset - {Path(path).name}",
                    "name": Path(path).name,
                    "path": path,
                    "source": "media_pool",
                    "ready": Path(path).expanduser().is_file(),
                    "direct_key_baking": False,
                    "will_create_actor_clip": True,
                    "recommended": False,
                }
            )
        return options

    def _tts_resolve_live2d_actor_target(
        self,
        *,
        actor_target_id: str = "",
        actor_track_id: int | None = None,
        actor_clip_index: int = 0,
        start_ms: int = 0,
        duration_ms: int = 3000,
    ) -> dict[str, Any]:
        if actor_track_id is not None:
            _track, clip = self._actor_track_and_clip("live2d", int(actor_track_id), int(actor_clip_index or 0))
            return {
                "found": True,
                "id": f"live2d:{int(actor_track_id)}:{int(actor_clip_index or 0)}",
                "track_id": int(actor_track_id),
                "clip_index": int(actor_clip_index or 0),
                "path": str(getattr(clip, "model_path", "") or ""),
                "source": "explicit_track",
            }

        target_id = str(actor_target_id or "").strip()
        if target_id.startswith("live2d:"):
            parts = target_id.split(":")
            if len(parts) >= 3:
                raw_track = int(parts[1])
                raw_clip = int(parts[2])
                try:
                    _track, clip = self._actor_track_and_clip("live2d", raw_track, raw_clip)
                    return {
                        "found": True,
                        "id": target_id,
                        "track_id": raw_track,
                        "clip_index": raw_clip,
                        "path": str(getattr(clip, "model_path", "") or ""),
                        "source": "timeline",
                    }
                except Exception:
                    tracks = list(getattr(self._require_owner(), "_live2d_actor_tracks", []) or [])
                    if 0 <= raw_track < len(tracks):
                        track = tracks[raw_track]
                        clips = list(getattr(track, "clips", []) or [])
                        if 0 <= raw_clip < len(clips):
                            return {
                                "found": True,
                                "id": target_id,
                                "track_id": int(getattr(track, "id", raw_track) or raw_track),
                                "clip_index": raw_clip,
                                "path": str(getattr(clips[raw_clip], "model_path", "") or ""),
                                "source": "timeline_index_fallback",
                            }
                    raise
        if target_id.startswith("media_live2d:"):
            index = int(target_id.split(":", 1)[1] or 0)
            paths = self._tts_media_pool_live2d_paths()
            if 0 <= index < len(paths):
                add = getattr(self, "add_actor", None)
                if not callable(add):
                    return {"found": False, "reason": "add_actor_unavailable", "id": target_id}
                created = add(
                    kind="live2d",
                    path=paths[index],
                    start_ms=max(0, int(start_ms or 0)),
                    duration_ms=max(1, int(duration_ms or 3000)),
                    pos_x=0.5,
                    pos_y=0.5,
                    scale=1.0,
                    opacity=1.0,
                    label="Live2D Dialogue",
                )
                return {
                    "found": True,
                    "id": target_id,
                    "track_id": int(created.get("track_id", 0) or 0),
                    "clip_index": int(created.get("clip_index", 0) or 0),
                    "path": paths[index],
                    "source": "media_pool_created_actor",
                    "created_actor": created,
                }
            return {"found": False, "reason": "media_live2d_target_not_found", "id": target_id}

        return self._tts_first_live2d_actor_target()

    def _tts_apply_live2d_dialogue_placement(
        self,
        *,
        actor_track_id: int,
        actor_clip_index: int = 0,
        placement_preset: str = "bottom_right",
        size_preset: str = "auto_fit",
        canvas_width: int = 1920,
        canvas_height: int = 1080,
        sample_ms: int = 0,
        replace_transform_keyframes: bool = True,
    ) -> dict[str, Any]:
        _track, clip = self._actor_track_and_clip("live2d", int(actor_track_id), int(actor_clip_index or 0))
        from app.live2d.dialogue_placement import apply_dialogue_placement_to_clip

        placement = apply_dialogue_placement_to_clip(
            clip,
            preset=placement_preset,
            size_preset=size_preset,
            canvas_width=int(canvas_width or 1920),
            canvas_height=int(canvas_height or 1080),
            sample_ms=int(sample_ms or 0),
            replace_transform_keyframes=bool(replace_transform_keyframes),
        )
        self._sync_actor_tracks("live2d")
        self._after_timeline_mutation("Apply Live2D dialogue placement")
        return {
            "applied": True,
            "actor_track_id": int(actor_track_id),
            "actor_clip_index": int(actor_clip_index or 0),
            **placement,
        }

    def _tts_apply_live2d_dialogue_motion(
        self,
        *,
        actor_track_id: int,
        actor_clip_index: int = 0,
        rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
        style: str = "natural_dialogue",
        interval_ms: int = 700,
    ) -> dict[str, Any]:
        _track, clip = self._actor_track_and_clip("live2d", int(actor_track_id), int(actor_clip_index or 0))
        from app.live2d.dialogue_motion import apply_natural_dialogue_motion_to_clip

        motion = apply_natural_dialogue_motion_to_clip(
            clip,
            rows=rows,
            replace_existing=True,
            prefer_authored_motion=True,
            interval_ms=int(interval_ms or 700),
            style=style,
        )
        self._sync_actor_tracks("live2d")
        self._after_timeline_mutation("Apply Live2D dialogue motion")
        return {
            "applied": True,
            "actor_track_id": int(actor_track_id),
            "actor_clip_index": int(actor_clip_index or 0),
            "schema": motion.get("schema"),
            "style": motion.get("style"),
            "parameter_tracks": list(motion.get("parameter_tracks") or []),
            "keyframe_count": sum(len(list(keys or [])) for keys in dict(motion.get("parameter_keyframes") or {}).values()),
            "authored_motion": dict(motion.get("authored_motion") or {}),
        }

    def _tts_append_subtitle_rows(self, rows: list[Mapping[str, Any]]) -> dict[str, Any]:
        owner = self._require_owner()
        panel = getattr(owner, "_subtitle_panel", None)
        if panel is None:
            raise ValueError("No subtitle panel is available for dialogue subtitles.")

        created = []
        created_items = []
        try:
            from app.subtitles import Subtitle
        except Exception:
            Subtitle = None  # type: ignore[assignment]

        for offset, row in enumerate(rows):
            start_ms = max(0, int(row.get("start_ms", 0) or 0))
            end_ms = max(start_ms + 1, int(row.get("end_ms", start_ms + 1) or start_ms + 1))
            spoken_text = str(row.get("tts_text") or row.get("text") or "").strip()
            display_text = str(row.get("subtitle_text") or row.get("display_text") or spoken_text).strip()
            style = dict(row.get("style") or {})
            if spoken_text and spoken_text != display_text:
                style.setdefault("tts_text", spoken_text)
                style.setdefault("spoken_text", spoken_text)
                style.setdefault("subtitle_text", display_text)
                style.setdefault("display_text", display_text)
            if Subtitle is not None:
                item = Subtitle(start_ms=start_ms, end_ms=end_ms, text=display_text, style=style)
            else:
                item = SimpleNamespace(start_ms=start_ms, end_ms=end_ms, text=display_text, style=style)
            layer = getattr(panel, "layer", None)
            add = getattr(layer, "add", None)
            if callable(add):
                add(item)
            elif isinstance(getattr(panel, "_rows", None), list):
                panel._rows.append(item)
            elif isinstance(getattr(panel, "_subtitles", None), list):
                panel._subtitles.append(item)
            else:
                raise ValueError("Subtitle panel does not expose an appendable subtitle list.")
            created_items.append(item)
            created.append(
                {
                    "index": offset,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "text": spoken_text,
                    "tts_text": spoken_text,
                    "subtitle_text": display_text,
                    "display_text": display_text,
                }
            )

        refresh = getattr(panel, "_refresh_list", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass
        signal = getattr(panel, "subtitles_changed", None)
        emit = getattr(signal, "emit", None)
        if callable(emit):
            try:
                emit()
            except Exception:
                pass
        changed = getattr(owner, "_on_subtitles_changed", None)
        if callable(changed):
            try:
                changed()
            except Exception:
                pass
        current = []
        subtitles = getattr(panel, "subtitles", None)
        if callable(subtitles):
            try:
                current = list(subtitles() or [])
            except Exception:
                current = []
        if current:
            indices = []
            for item in created_items:
                try:
                    indices.append(next(idx for idx, current_item in enumerate(current) if current_item is item))
                except StopIteration:
                    indices.append(len(current) - len(created_items) + len(indices))
            for row, index in zip(created, indices):
                row["index"] = max(0, int(index))
        return {"created": True, "count": len(created), "indices": [row["index"] for row in created], "rows": created}

    def _tts_first_live2d_actor_target(self) -> dict[str, Any]:
        owner = self._require_owner()
        for track in getattr(owner, "_live2d_actor_tracks", []) or []:
            clips = list(getattr(track, "clips", []) or [])
            if clips:
                track_id = int(getattr(track, "id", 0) or 0)
                return {
                    "found": True,
                    "id": f"live2d:{track_id}:0",
                    "track_id": track_id,
                    "clip_index": 0,
                    "clip_count": len(clips),
                    "path": str(getattr(clips[0], "model_path", "") or ""),
                    "source": "timeline_default",
                }
        return {"found": False, "reason": "no_live2d_actor"}
