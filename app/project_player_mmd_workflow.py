from __future__ import annotations

from pathlib import Path

import numpy as np

from app.mmd.physics import (
    SECONDARY_ROTATION_HINT_SCALE,
    SPRING_PHYSICS_RESPONSE,
    mmd_physics_backend_diagnostics,
)

MMD_PREVIEW_IK_ITERATIONS = 12
MMD_PLAYBACK_IK_ITERATIONS = 2
MMD_PHYSICS_UPDATE_INTERVAL_FRAMES = 2.0
MMD_PHYSICS_SMOOTHING_RESPONSE = 0.88
MMD_PHYSICS_ROTATION_HINT_SCALE = SECONDARY_ROTATION_HINT_SCALE
MMD_PHYSICS_SPRING_RESPONSE = SPRING_PHYSICS_RESPONSE
MMD_GPU_MORPH_SLOTS = 2

def mmd_diagnostics(
    self,
    *,
    pos_ms: int | None = None,
    include_materials: bool = True,
    animate: bool = False,
) -> dict:
    """Return timeline-side diagnostics for active MMD actor tracks."""
    position = int(self.position() if pos_ms is None else pos_ms)
    tracks = self.mmd_tracks()
    active = self._active_mmd_tracks(position)
    active_ids = {str(track.get("id") or "") for track in active if isinstance(track, dict)}
    items_by_track: dict[str, dict] = {}
    if include_materials and active:
        for item in self._mmd_overlay_items(position, animate=bool(animate)):
            track_id = str(item.get("track_id") or "")
            if track_id:
                items_by_track[track_id] = item

    rows: list[dict] = []
    for index, track in enumerate(tracks):
        if not isinstance(track, dict):
            continue
        track_id = str(track.get("id") or f"mmd_{index + 1:03d}")
        item = items_by_track.get(track_id)
        diagnostics = dict((item or {}).get("diagnostics") or {})
        rows.append(
            {
                "id": track_id,
                "active": track_id in active_ids,
                "model_path": str(track.get("model_path") or ""),
                "motion_path": str(track.get("motion_path") or ""),
                "start_ms": int(track.get("start_ms", 0) or 0),
                "end_ms": int(track.get("end_ms", 0) or 0),
                "duration_ms": int(track.get("duration_ms", 0) or 0),
                "playback": dict(track.get("playback") or {}),
                "render": dict(track.get("render") or {}),
                "diagnostics": diagnostics,
                "material_bucket_counts": dict(diagnostics.get("material_bucket_counts") or {}),
                "material_class_counts": dict(diagnostics.get("material_class_counts") or {}),
                "material_bucket_rows": list(diagnostics.get("material_bucket_rows") or []),
            }
        )

    previous_diagnostics = dict(getattr(self, "_mmd_last_diagnostics", {}) or {})
    last_error = previous_diagnostics if "error" in previous_diagnostics else {}
    result = {
        "position_ms": int(position),
        "track_count": int(len(rows)),
        "active_track_count": int(len(active_ids)),
        "include_materials": bool(include_materials),
        "animated_sample": bool(animate),
        "tracks": rows,
        "last_error": last_error,
    }
    self._mmd_last_diagnostics = result
    return result

def _active_mmd_tracks(self, pos_ms: int) -> list[dict]:
    tracks = list(getattr(self, "_mmd_tracks", []) or [])
    if not tracks:
        return []
    try:
        from app.mmd.schema import track_active_at
    except Exception:
        return [
            track for track in tracks
            if int(track.get("start_ms", 0) or 0) <= int(pos_ms) < int(track.get("end_ms", 0) or 0)
        ]
    return [track for track in tracks if track_active_at(track, int(pos_ms))]

def _mmd_model_for_path(self, path_text: str):
    key = str(path_text or "")
    if not key:
        return None
    if key not in self._mmd_model_cache:
        from app.mmd.loader import load_mmd_model

        self._mmd_model_cache[key] = load_mmd_model(Path(key))
    return self._mmd_model_cache.get(key)

def _mmd_motion_for_path(self, path_text: str):
    key = str(path_text or "")
    if not key:
        return None
    if key not in self._mmd_motion_cache:
        from app.mmd.vmd import load_vmd

        self._mmd_motion_cache[key] = load_vmd(Path(key))
    return self._mmd_motion_cache.get(key)

def _mmd_motion_duration_ms(motion) -> int:
    max_frame = int(getattr(motion, "max_frame", 0) or 0)
    return max(1, int(round((max(1, max_frame) / 30.0) * 1000.0)))

def _mmd_frame_for_track(self, track: dict, motion, pos_ms: int) -> float:
    playback = dict(track.get("playback") or {})
    local_ms = max(0, int(pos_ms) - int(track.get("start_ms", 0) or 0))
    local_ms += max(0, int(playback.get("motion_start_ms", 0) or 0))
    if motion is not None and bool(playback.get("loop", True)):
        duration_ms = self._mmd_motion_duration_ms(motion)
        local_ms %= duration_ms
    return float(local_ms) / 1000.0 * 30.0

def _mmd_physics_backend_for_track(
    self,
    track_id: str,
    frame: float,
    enabled: bool,
    prefer: str = "auto",
    *,
    update_interval_frames: float = MMD_PHYSICS_UPDATE_INTERVAL_FRAMES,
    smoothing_response: float = MMD_PHYSICS_SMOOTHING_RESPONSE,
    rotation_hint_scale: float = MMD_PHYSICS_ROTATION_HINT_SCALE,
    spring_response: float = MMD_PHYSICS_SPRING_RESPONSE,
):
    if not enabled:
        from app.mmd.physics import NoPhysicsBackend

        return NoPhysicsBackend()
    from app.mmd.physics import DecimatedPhysicsBackend, create_mmd_physics_backend

    cache = getattr(self, "_mmd_physics_cache", {})
    interval = max(1.0, min(6.0, float(update_interval_frames or MMD_PHYSICS_UPDATE_INTERVAL_FRAMES)))
    smoothing = max(0.0, min(1.0, float(smoothing_response)))
    rotation_scale = max(0.0, min(0.30, float(rotation_hint_scale)))
    spring = max(0.15, min(1.50, float(spring_response)))
    backend_key = (
        str(track_id),
        str(prefer or "auto").strip().casefold(),
        round(interval, 4),
        round(smoothing, 4),
        round(rotation_scale, 4),
        round(spring, 4),
    )
    backend = cache.get(backend_key)
    if backend is None:
        backend = DecimatedPhysicsBackend(
            create_mmd_physics_backend(
                prefer,
                spring_response=spring,
                secondary_rotation_scale=rotation_scale,
            ),
            update_interval_frames=interval,
            smoothing_response=smoothing,
        )
        cache[backend_key] = backend
    previous = getattr(self, "_mmd_last_frame_by_track", {}).get(track_id)
    if previous is not None and (float(frame) < float(previous) or abs(float(frame) - float(previous)) > 12.0):
        reset = getattr(backend, "reset", None)
        if callable(reset):
            reset()
    self._mmd_last_frame_by_track[track_id] = float(frame)
    return backend

def _mmd_overlay_items(self, pos_ms: int, animate: bool = True) -> list[dict]:
    active = self._active_mmd_tracks(pos_ms)
    if not active:
        return []
    from app.mmd.animation import evaluate_model_pose
    from app.mmd.gpu_preview import MMD_RENDER_TOON, build_mmd_render_item
    from app.mmd.vmd import camera_at, camera_to_view_controls

    items: list[dict] = []
    for index, track in enumerate(active):
        try:
            model = self._mmd_model_for_path(str(track.get("model_path") or ""))
            if model is None:
                continue
            motion = self._mmd_motion_for_path(str(track.get("motion_path") or ""))
            frame = self._mmd_frame_for_track(track, motion, pos_ms) if animate else 0.0
            playback = dict(track.get("playback") or {})
            render = dict(track.get("render") or {})
            view = dict(track.get("view") or {})
            has_sdef = bool(np.any(np.asarray(model.weights.weight_types) == 3))
            gpu_requested = bool(playback.get("gpu_skinning", True))
            gpu_fallback_reason = "sdef_cpu_skinning_required" if gpu_requested and has_sdef else ""
            gpu_morph_slots = max(0, min(MMD_GPU_MORPH_SLOTS, int(playback.get("gpu_morph_slots", MMD_GPU_MORPH_SLOTS) or 0)))
            use_gpu_skinning = bool(
                gpu_requested
                and not has_sdef
                and motion is not None
            )
            track_id = str(track.get("id") or f"mmd_{index + 1:03d}")
            physics_backend = self._mmd_physics_backend_for_track(
                track_id,
                frame,
                bool(playback.get("enable_physics", True)),
                str(playback.get("physics_backend") or "auto"),
                update_interval_frames=float(
                    playback.get("physics_update_interval_frames", MMD_PHYSICS_UPDATE_INTERVAL_FRAMES)
                    or MMD_PHYSICS_UPDATE_INTERVAL_FRAMES
                ),
                smoothing_response=float(
                    playback.get("physics_smoothing_response", MMD_PHYSICS_SMOOTHING_RESPONSE)
                    or MMD_PHYSICS_SMOOTHING_RESPONSE
                ),
                rotation_hint_scale=float(
                    playback.get("physics_rotation_hint_scale", MMD_PHYSICS_ROTATION_HINT_SCALE)
                    or MMD_PHYSICS_ROTATION_HINT_SCALE
                ),
                spring_response=float(
                    playback.get("physics_spring_response", MMD_PHYSICS_SPRING_RESPONSE)
                    or MMD_PHYSICS_SPRING_RESPONSE
                ),
            )
            pose = evaluate_model_pose(
                model,
                motion,
                frame,
                physics_backend=physics_backend,
                enable_ik=bool(playback.get("enable_ik", True)),
                enable_physics=bool(playback.get("enable_physics", True)),
                max_ik_iterations=MMD_PLAYBACK_IK_ITERATIONS if animate else MMD_PREVIEW_IK_ITERATIONS,
                foot_ik_reach_limit=float(playback.get("foot_ik_reach_limit", 0.985) or 0.985),
                skin_vertices=not use_gpu_skinning,
                gpu_morph_slots=gpu_morph_slots if use_gpu_skinning else 0,
            )
            camera_controls = camera_to_view_controls(
                camera_at(motion, frame),
                fallback_yaw=float(view.get("yaw", 0.0) or 0.0),
                fallback_pitch=float(view.get("pitch", -4.0) or -4.0),
                fallback_zoom=float(view.get("zoom", 0.72) or 0.72),
                fallback_offset_x=float(view.get("offset_x", 0.0) or 0.0),
                fallback_offset_y=float(view.get("offset_y", 0.02) or 0.02),
            )
            item = build_mmd_render_item(
                model,
                render_mode=MMD_RENDER_TOON,
                yaw=float(view.get("yaw", 0.0) or 0.0),
                pitch=float(view.get("pitch", -4.0) or -4.0),
                roll=float(view.get("roll", 0.0) or 0.0),
                zoom=float(view.get("zoom", 0.72) or 0.72),
                offset_x=float(view.get("offset_x", 0.0) or 0.0),
                offset_y=float(view.get("offset_y", 0.02) or 0.02),
                lighting_preset=str(render.get("lighting_preset") or "studio_soft"),
                lighting=render.get("lighting"),
                bloom_strength=float(render.get("bloom_strength", 0.30) or 0.0),
                material_tuning=render.get("material"),
                pose_geometry=pose,
                camera_controls=camera_controls,
            )
            item["track_id"] = track_id
            item["timeline_start_ms"] = int(track.get("start_ms", 0) or 0)
            item["timeline_end_ms"] = int(track.get("end_ms", 0) or 0)
            diagnostics = dict(item.get("diagnostics") or {})
            diagnostics.update(
                {
                    "track_gpu_skinning_requested": bool(gpu_requested),
                    "track_gpu_skinning_active": bool(use_gpu_skinning and item.get("gpu_skinning")),
                    "track_gpu_skinning_fallback_reason": gpu_fallback_reason,
                    "track_sdef_cpu_skinning_required": bool(has_sdef),
                    "track_gpu_morph_slots": int(gpu_morph_slots if use_gpu_skinning else 0),
                    "track_physics_update_interval_frames": float(
                        playback.get("physics_update_interval_frames", MMD_PHYSICS_UPDATE_INTERVAL_FRAMES)
                        or MMD_PHYSICS_UPDATE_INTERVAL_FRAMES
                    ),
                    "track_physics_smoothing_response": float(
                        playback.get("physics_smoothing_response", MMD_PHYSICS_SMOOTHING_RESPONSE)
                        or MMD_PHYSICS_SMOOTHING_RESPONSE
                    ),
                    "track_physics_rotation_hint_scale": float(
                        playback.get("physics_rotation_hint_scale", MMD_PHYSICS_ROTATION_HINT_SCALE)
                        or MMD_PHYSICS_ROTATION_HINT_SCALE
                    ),
                    "track_physics_spring_response": float(
                        playback.get("physics_spring_response", MMD_PHYSICS_SPRING_RESPONSE)
                        or MMD_PHYSICS_SPRING_RESPONSE
                    ),
                    **{
                        f"track_{key}": value
                        for key, value in mmd_physics_backend_diagnostics(physics_backend).items()
                    },
                    "track_physics_backend_requested": str(playback.get("physics_backend") or "auto"),
                    "track_playback_frame": float(frame),
                }
            )
            item["diagnostics"] = diagnostics
            items.append(item)
        except Exception as exc:
            self._mmd_last_diagnostics = {
                "error": f"{type(exc).__name__}: {exc}",
                "track_id": str(track.get("id") or ""),
            }
            continue
    return items

def _apply_or_defer_mmd_overlay(self, rgb: np.ndarray, pos_ms: int, animate: bool) -> tuple[np.ndarray, dict | None]:
    if not getattr(self, "_mmd_tracks", None):
        return rgb, None
    items = self._mmd_overlay_items(pos_ms, animate=animate)
    if not items:
        return rgb, None
    return rgb, {"mmd_items": items}

