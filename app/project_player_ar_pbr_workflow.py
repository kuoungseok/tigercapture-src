from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from app.simple_video_player import PlayerState


AR_PBR_PREVIEW_TRIANGLE_LIMIT = 120_000
AR_PBR_PLAYBACK_TRIANGLE_LIMIT = 1_000
AR_PBR_RUNTIME_ANCHOR_CACHE_MS = 160


def _ar_pbr_pending_descriptor_for_path(path: Path, *, state: str = "loading") -> dict:
    from app.ar_pbr.asset_support import placeholder_asset_support, public_asset_support

    ext = path.suffix.lower()
    support = placeholder_asset_support(path, state=state)
    return {
        "id": f"pending_{path.stem or 'asset'}",
        "type": "ar_pbr_asset",
        "source_path": str(path),
        "source_ext": ext,
        "source_format": ext.lstrip("."),
        "runtime_format": "ar_scene_descriptor",
        "preferred_runtime_format": "glb",
        "requires_runtime_conversion": ext == ".fbx",
        "import_state": state,
        "backend": "background_import",
        "mesh_count": 0,
        "material_count": 0,
        "animation_count": 0,
        "bounds": {
            "center": [0.0, 0.0, 0.0],
            "size": [1.0, 1.0, 1.0],
        },
        "geometries": [],
        "models": [],
        "materials": [],
        "connections": [],
        "warnings": ["3D asset is still loading"],
        "support": support,
        "support_ui": public_asset_support(support, asset_path=str(path)),
    }

def _ar_pbr_prepare_descriptor_support(
    descriptor: Mapping[str, Any] | None,
    *,
    asset_path: str = "",
    track_id: str = "",
    diagnostics: Mapping[str, Any] | None = None,
) -> dict:
    from app.ar_pbr.asset_support import classify_asset_support, public_asset_support

    data = dict(descriptor or {})
    support = data.get("support")
    if not isinstance(support, dict):
        imported = bool(data.get("geometries")) or str(data.get("import_state") or "") == "ready"
        support = classify_asset_support(
            data,
            diagnostics or {"imported": imported, "fallback": False},
        )
        data["support"] = support
    data["support_ui"] = public_asset_support(
        support,
        asset_path=asset_path or str(data.get("source_path") or ""),
        track_id=track_id,
    )
    return data

def _ar_pbr_import_asset_descriptor(path: Path) -> tuple[dict, dict]:
    from app.ar_pbr.importer import import_asset

    return import_asset(
        path,
        settings={
            "placeholder_on_error": True,
            "max_triangles_per_geometry": AR_PBR_PREVIEW_TRIANGLE_LIMIT,
        },
    )

def _ar_pbr_start_asset_import(self, cache_key: str, path: Path) -> None:
    futures = getattr(self, "_ar_pbr_asset_import_futures", None)
    if not isinstance(futures, dict):
        futures = {}
        self._ar_pbr_asset_import_futures = futures
    if cache_key in futures:
        return
    try:
        executor = getattr(self, "_ar_pbr_asset_import_executor", None)
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ar-pbr-import")
            self._ar_pbr_asset_import_executor = executor
        future = executor.submit(self._ar_pbr_import_asset_descriptor, path)
        futures[cache_key] = future
        future.add_done_callback(
            lambda _future, key=cache_key: self.ar_pbr_asset_import_ready.emit(key)
        )
    except Exception as exc:
        self._ar_pbr_asset_error_cache[cache_key] = f"{type(exc).__name__}: {exc}"

def _ar_pbr_prewarm_asset_imports(self, tracks: list[dict]) -> None:
    """Start 3D descriptor imports before their timeline in-point."""
    for track in list(tracks or []):
        if not isinstance(track, dict):
            continue
        path_text = str(track.get("asset_path") or "")
        if not path_text:
            continue
        try:
            path = Path(path_text).expanduser().resolve()
        except Exception:
            path = Path(path_text)
        key = str(path)
        cache_key = f"{key}|triangles:{AR_PBR_PREVIEW_TRIANGLE_LIMIT}"
        if (
            key in self._ar_pbr_asset_descriptor_cache
            or cache_key in self._ar_pbr_asset_descriptor_cache
            or cache_key in getattr(self, "_ar_pbr_asset_import_futures", {})
            or cache_key in self._ar_pbr_asset_error_cache
        ):
            continue
        self._ar_pbr_start_asset_import(cache_key, path)

def _ar_pbr_collect_asset_import(self, cache_key: str) -> bool:
    futures = getattr(self, "_ar_pbr_asset_import_futures", None)
    if not isinstance(futures, dict):
        return False
    future = futures.get(cache_key)
    if future is None or not future.done():
        return False
    futures.pop(cache_key, None)
    try:
        descriptor, diagnostics = future.result()
        if diagnostics.get("ok") is False:
            self._ar_pbr_asset_error_cache[cache_key] = "; ".join(
                diagnostics.get("errors") or ["import failed"]
            )
            return False
        asset_path = cache_key.split("|triangles:", 1)[0]
        descriptor = self._ar_pbr_prepare_descriptor_support(
            descriptor,
            asset_path=asset_path,
            diagnostics=diagnostics,
        )
        self._ar_pbr_asset_descriptor_cache[cache_key] = descriptor
        self._ar_pbr_asset_descriptor_cache[asset_path] = descriptor
        self._last_preview_frame_cache = None
        self._ar_pbr_gpu_packet_cache.clear()
        return True
    except Exception as exc:
        self._ar_pbr_asset_error_cache[cache_key] = f"{type(exc).__name__}: {exc}"
        return False

def _ar_pbr_descriptor_for_track(self, track: dict) -> tuple[str, dict | None]:
    path_text = str((track or {}).get("asset_path") or "")
    if not path_text:
        return "", None
    try:
        path = Path(path_text).expanduser().resolve()
    except Exception:
        path = Path(path_text)
    key = str(path)
    cache_key = f"{key}|triangles:{AR_PBR_PREVIEW_TRIANGLE_LIMIT}"
    if key in self._ar_pbr_asset_descriptor_cache:
        descriptor = self._ar_pbr_prepare_descriptor_support(
            self._ar_pbr_asset_descriptor_cache[key],
            asset_path=key,
            track_id=str(track.get("id") or ""),
        )
        self._ar_pbr_asset_descriptor_cache[key] = descriptor
        return key, descriptor
    if cache_key in self._ar_pbr_asset_descriptor_cache:
        descriptor = self._ar_pbr_prepare_descriptor_support(
            self._ar_pbr_asset_descriptor_cache[cache_key],
            asset_path=key,
            track_id=str(track.get("id") or ""),
        )
        self._ar_pbr_asset_descriptor_cache[cache_key] = descriptor
        self._ar_pbr_asset_descriptor_cache[key] = descriptor
        return key, descriptor
    if cache_key in getattr(self, "_ar_pbr_asset_import_futures", {}):
        self._ar_pbr_collect_asset_import(cache_key)
        if cache_key in self._ar_pbr_asset_descriptor_cache:
            descriptor = self._ar_pbr_prepare_descriptor_support(
                self._ar_pbr_asset_descriptor_cache[cache_key],
                asset_path=key,
                track_id=str(track.get("id") or ""),
            )
            self._ar_pbr_asset_descriptor_cache[cache_key] = descriptor
            self._ar_pbr_asset_descriptor_cache[key] = descriptor
            return key, descriptor
    if cache_key in self._ar_pbr_asset_error_cache:
        return key, self._ar_pbr_pending_descriptor_for_path(path, state="error")
    self._ar_pbr_start_asset_import(cache_key, path)
    return key, self._ar_pbr_pending_descriptor_for_path(path)

def _ar_pbr_asset_descriptors(self, tracks: list[dict]) -> dict[str, dict]:
    descriptors: dict[str, dict] = {}
    for track in tracks:
        key, descriptor = self._ar_pbr_descriptor_for_track(track)
        if descriptor is None:
            continue
        track_id = str(track.get("id") or "")
        asset_path = str(track.get("asset_path") or key)
        if track_id:
            descriptors[track_id] = descriptor
        if asset_path:
            descriptors[asset_path] = descriptor
        if key:
            descriptors[key] = descriptor
    return descriptors

def _ar_pbr_public_asset_support_rows(tracks: list[dict], descriptors: Mapping[str, dict]) -> list[dict]:
    from app.ar_pbr.asset_support import public_asset_support

    rows: list[dict] = []
    seen: set[str] = set()
    for track in tracks:
        if not isinstance(track, dict):
            continue
        track_id = str(track.get("id") or "")
        asset_path = str(track.get("asset_path") or "")
        descriptor = None
        for key in (track_id, asset_path):
            candidate = descriptors.get(key) if isinstance(descriptors, Mapping) else None
            if isinstance(candidate, dict):
                descriptor = candidate
                break
        if descriptor is None:
            continue
        support_ui = descriptor.get("support_ui")
        if isinstance(support_ui, dict):
            row = dict(support_ui)
            if not row.get("track_id"):
                row["track_id"] = track_id
            if not row.get("asset_path"):
                row["asset_path"] = asset_path
        else:
            row = public_asset_support(
                descriptor.get("support") if isinstance(descriptor.get("support"), dict) else None,
                asset_path=asset_path,
                track_id=track_id,
            )
        dedupe_key = track_id or asset_path or row.get("asset_path") or row.get("label") or ""
        if dedupe_key and dedupe_key in seen:
            continue
        if dedupe_key:
            seen.add(str(dedupe_key))
        rows.append(row)
    return rows

def _ar_pbr_runtime_anchor_signature(track: dict) -> tuple:
    placement = track.get("placement") if isinstance(track, dict) else {}
    placement = placement if isinstance(placement, dict) else {}
    transform = track.get("transform") if isinstance(track, dict) else {}
    transform = transform if isinstance(transform, dict) else {}
    tracking = placement.get("tracking") if isinstance(placement, dict) else {}
    tracking = tracking if isinstance(tracking, dict) else {}

    def _rounded_pair(values) -> tuple[float, float] | tuple:
        if isinstance(values, (list, tuple)) and len(values) >= 2:
            try:
                return (round(float(values[0]), 5), round(float(values[1]), 5))
            except Exception:
                return ()
        return ()

    return (
        str(track.get("id") or ""),
        str(track.get("asset_path") or ""),
        str(track.get("camera_solution_id") or ""),
        str(track.get("depth_source_id") or ""),
        str(placement.get("mode") or ""),
        _rounded_pair(placement.get("image_point")),
        _rounded_pair(tracking.get("image_point")),
        int(len((tracking or {}).get("template_luma") or [])) if isinstance(tracking, dict) else 0,
        str(transform.get("position") or ""),
    )

def _ar_pbr_track_cache_key(track: dict, index: int) -> str:
    if isinstance(track, dict):
        track_id = str(track.get("id") or "")
        if track_id:
            return f"id:{track_id}"
        asset_path = str(track.get("asset_path") or "")
        if asset_path:
            return f"asset:{asset_path}:{index}"
    return f"track:{index}"

def _ar_pbr_apply_cached_runtime_anchor(track: dict, cache_row: dict, pos_ms: int) -> tuple[dict, object | None, dict | None, dict]:
    updated = deepcopy(dict(track))
    cached_placement = cache_row.get("placement")
    if isinstance(cached_placement, dict):
        placement = dict(updated.get("placement") if isinstance(updated.get("placement"), dict) else {})
        placement.update(deepcopy(cached_placement))
        updated["placement"] = placement
    solution = cache_row.get("camera_solution")
    if isinstance(solution, dict):
        updated["camera_solution"] = deepcopy(solution)
        updated["camera_solution_id"] = str(solution.get("id") or updated.get("camera_solution_id") or "")
    diag = deepcopy(cache_row.get("diagnostics") or {})
    diag["cached"] = True
    try:
        diag["cache_age_ms"] = max(0, int(pos_ms) - int(cache_row.get("time_ms", pos_ms)))
    except Exception:
        diag["cache_age_ms"] = 0
    return updated, cache_row.get("depth"), solution if isinstance(solution, dict) else None, diag

def _ar_pbr_runtime_tracks_for_frame(self, tracks: list[dict], rgb: np.ndarray, pos_ms: int) -> tuple[list[dict], object | None, dict | None, list[dict]]:
    runtime_tracks: list[dict] = []
    depth_frame = None
    camera_solution = None
    diagnostics: list[dict] = []
    frame_size = tuple(int(v) for v in rgb.shape[:2])
    allow_runtime_anchor = self._ar_pbr_realtime_scene_anchor_enabled()
    cache = getattr(self, "_ar_pbr_runtime_anchor_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        self._ar_pbr_runtime_anchor_cache = cache
    live_cache_keys: set[str] = set()
    for index, track in enumerate(tracks):
        placement = track.get("placement") if isinstance(track, dict) else {}
        mode = str((placement or {}).get("mode") or "manual").casefold() if isinstance(placement, dict) else "manual"
        if mode not in {"road_plane_anchor", "plane_anchor", "screen_plane", "scene_anchor"}:
            runtime_tracks.append(track)
            continue
        cache_key = self._ar_pbr_track_cache_key(track, index)
        live_cache_keys.add(cache_key)
        signature = self._ar_pbr_runtime_anchor_signature(track)
        if not allow_runtime_anchor:
            runtime_tracks.append(track)
            diagnostics.append({
                "ok": True,
                "track_id": str(track.get("id") or ""),
                "mode": mode,
                "skipped_during_playback": True,
                "reason": "runtime scene-anchor update disabled during playback",
            })
            solution = track.get("camera_solution") if isinstance(track.get("camera_solution"), dict) else None
            if camera_solution is None and isinstance(solution, dict):
                camera_solution = solution
            continue
        cached = cache.get(cache_key)
        if (
            isinstance(cached, dict)
            and cached.get("signature") == signature
            and cached.get("frame_size") == frame_size
            and abs(int(pos_ms) - int(cached.get("time_ms", -10_000_000))) < AR_PBR_RUNTIME_ANCHOR_CACHE_MS
        ):
            updated, depth, solution, diag = self._ar_pbr_apply_cached_runtime_anchor(track, cached, pos_ms)
            runtime_tracks.append(updated)
            diagnostics.append(diag)
            if depth_frame is None and depth is not None:
                depth_frame = depth
            if camera_solution is None and isinstance(solution, dict):
                camera_solution = solution
            continue
        try:
            from app.ar_pbr.scene_anchor import update_scene_anchor_for_frame

            updated, depth, solution, diag = update_scene_anchor_for_frame(
                track,
                rgb,
                time_ms=int(pos_ms),
                source_id=str(track.get("asset_path") or track.get("id") or "preview"),
            )
            runtime_tracks.append(updated)
            diagnostics.append(diag)
            if depth_frame is None and depth is not None:
                depth_frame = depth
            if camera_solution is None and isinstance(solution, dict):
                camera_solution = solution
            cache[cache_key] = {
                "time_ms": int(pos_ms),
                "signature": signature,
                "frame_size": frame_size,
                "placement": deepcopy(updated.get("placement") if isinstance(updated, dict) else {}),
                "camera_solution": deepcopy(solution) if isinstance(solution, dict) else None,
                "depth": depth,
                "diagnostics": deepcopy(diag),
            }
        except Exception as exc:
            runtime_tracks.append(track)
            diagnostics.append({
                "ok": False,
                "track_id": str(track.get("id") or ""),
                "reason": f"{type(exc).__name__}: {exc}",
            })
    for stale_key in list(cache.keys()):
        if stale_key not in live_cache_keys:
            cache.pop(stale_key, None)
    return runtime_tracks, depth_frame, camera_solution, diagnostics

def _ar_pbr_camera_solution_for_tracks(self, width: int, height: int, active: list[dict]) -> dict:
    for track in active:
        solution = track.get("camera_solution") if isinstance(track, dict) else None
        if isinstance(solution, dict) and solution.get("plane"):
            return solution
        solution_id = str(track.get("camera_solution_id") or "") if isinstance(track, dict) else ""
        if solution_id:
            try:
                from app.camera_solve.cache import load_camera_solution

                loaded = load_camera_solution(solution_id)
                if isinstance(loaded, dict) and loaded.get("plane"):
                    return loaded
            except Exception:
                pass
    return self._default_ar_pbr_camera_solution(width, height)

def _ar_pbr_depth_frame_for_tracks(self, rgb: np.ndarray, pos_ms: int, active: list[dict]):
    depth_view_enabled = self._ar_pbr_depth_view_mode() != "off"
    wants_occlusion = any(
        bool(track.get("occlusion"))
        for track in active
        if isinstance(track, dict)
    )
    if self._state is PlayerState.PLAYING and not wants_occlusion and not depth_view_enabled:
        return None
    for track in active:
        source_id = str(track.get("depth_source_id") or "") if isinstance(track, dict) else ""
        if not source_id:
            continue
        try:
            from app.depth.cache import load_depth_frame

            depth = load_depth_frame(source_id, int(pos_ms), allow_nearest_ms=80)
            if depth is not None:
                return depth
        except Exception:
            pass
    wants_depth = depth_view_enabled or any(
        bool(track.get("occlusion"))
        or str(((track.get("placement") or {}) if isinstance(track, dict) else {}).get("mode") or "").casefold()
        in {"road_plane_anchor", "plane_anchor", "screen_plane", "scene_anchor"}
        for track in active
        if isinstance(track, dict)
    )
    if not wants_depth:
        return None
    if self._state is PlayerState.PLAYING and not self._ar_pbr_realtime_depth_enabled() and not depth_view_enabled:
        return None
    try:
        from app.depth.estimator import estimate_depth

        depth, _diag = estimate_depth(rgb, source_id="preview_runtime", time_ms=int(pos_ms))
        return depth
    except Exception:
        return None

def _ar_pbr_depth_view_context_for_frame(self, rgb: np.ndarray, pos_ms: int) -> dict | None:
    if self._ar_pbr_depth_view_mode() == "off":
        return None
    try:
        h, w = rgb.shape[:2]
    except Exception:
        return None
    depth_frame = self._ar_pbr_depth_frame_for_tracks(rgb, pos_ms, [])
    return {
        "tracks": [],
        "active_tracks": [],
        "camera_solution": None,
        "depth_frame": depth_frame,
        "runtime_diagnostics": [],
        "width": int(w),
        "height": int(h),
    }

def _ar_pbr_gpu_preview_enabled() -> bool:
    try:
        from app.ar_pbr.preview_pipeline import gpu_preview_enabled

        return gpu_preview_enabled()
    except Exception:
        return True

def _ar_pbr_preview_renderer_mode() -> str:
    try:
        from app.ar_pbr.preview_pipeline import preview_renderer_mode_from_env

        return preview_renderer_mode_from_env()
    except Exception:
        return "auto"

def _ar_pbr_depth_view_mode(self) -> str:
    from app.ar_pbr.depth_view import normalize_depth_view_mode

    value = getattr(self, "_ar_pbr_depth_view_mode_value", None)
    if value is None:
        try:
            import os

            value = os.environ.get("TIGERCAPTURE_AR_PBR_DEPTH_VIEW", "")
        except Exception:
            value = ""
    return normalize_depth_view_mode(value)

def set_ar_pbr_depth_view_mode(self, mode: str = "off") -> str:
    from app.ar_pbr.depth_view import normalize_depth_view_mode

    canonical = normalize_depth_view_mode(mode)
    self._ar_pbr_depth_view_mode_value = canonical
    self._last_preview_frame_cache = None
    return canonical

def ar_pbr_depth_view_mode(self) -> str:
    return self._ar_pbr_depth_view_mode()

def _ar_pbr_should_use_full_gpu_preview(self) -> bool:
    from app.ar_pbr.preview_pipeline import should_use_full_gpu_preview

    return should_use_full_gpu_preview(
        self._ar_pbr_preview_renderer_mode(),
        playing=self._state is PlayerState.PLAYING,
    )

def _ar_pbr_realtime_scene_anchor_enabled(self) -> bool:
    try:
        from app.ar_pbr.preview_pipeline import realtime_scene_anchor_enabled

        return realtime_scene_anchor_enabled(playing=self._state is PlayerState.PLAYING)
    except Exception:
        return False

def _ar_pbr_realtime_depth_enabled(self) -> bool:
    try:
        from app.ar_pbr.preview_pipeline import realtime_depth_enabled

        return realtime_depth_enabled(playing=self._state is PlayerState.PLAYING)
    except Exception:
        return False

def _ar_pbr_gpu_preview_triangle_limit(self) -> int:
    from app.ar_pbr.preview_pipeline import gpu_preview_triangle_limit

    return gpu_preview_triangle_limit(
        playing=self._state is PlayerState.PLAYING,
        preview_limit=AR_PBR_PREVIEW_TRIANGLE_LIMIT,
        playback_limit=AR_PBR_PLAYBACK_TRIANGLE_LIMIT,
    )

def _ar_pbr_preview_context(self, rgb: np.ndarray, pos_ms: int) -> dict | None:
    tracks = list(getattr(self, "_ar_pbr_tracks", []) or [])
    if not tracks:
        return None
    try:
        from app.ar_pbr.schema import track_active_at

        active = [track for track in tracks if track_active_at(track, int(pos_ms))]
        if not active:
            return None
        h, w = rgb.shape[:2]
        runtime_tracks, runtime_depth, runtime_solution, runtime_diags = self._ar_pbr_runtime_tracks_for_frame(tracks, rgb, pos_ms)
        active_runtime = [track for track in runtime_tracks if track_active_at(track, int(pos_ms))]
        camera_solution = runtime_solution or self._ar_pbr_camera_solution_for_tracks(w, h, active_runtime)
        depth_frame = runtime_depth if runtime_depth is not None else self._ar_pbr_depth_frame_for_tracks(rgb, pos_ms, active_runtime)
        return {
            "tracks": runtime_tracks,
            "active_tracks": active_runtime,
            "camera_solution": camera_solution,
            "depth_frame": depth_frame,
            "runtime_diagnostics": runtime_diags,
            "width": int(w),
            "height": int(h),
        }
    except Exception as exc:
        self._ar_pbr_last_diagnostics = {
            "ok": False,
            "fallback": True,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
        return None

def _ar_pbr_depth_view_frame(self, rgb: np.ndarray, context: Mapping, pos_ms: int) -> np.ndarray | None:
    mode = self._ar_pbr_depth_view_mode()
    if mode == "off":
        return None
    try:
        from app.ar_pbr.depth_view import depth_frame_to_rgb

        depth_rgb, diagnostics = depth_frame_to_rgb(
            context.get("depth_frame"),
            int(context.get("width") or rgb.shape[1]),
            int(context.get("height") or rgb.shape[0]),
            mode=mode,
        )
        merged = {
            "ok": bool(diagnostics.get("ok")),
            "mode": "depth_view",
            "preview_renderer_selected": "depth_map_only",
            "depth_view": diagnostics,
            "active_track_count": len(list(context.get("active_tracks") or [])),
        }
        runtime_diags = list(context.get("runtime_diagnostics") or [])
        if runtime_diags:
            merged["runtime_scene_anchor"] = runtime_diags
        if depth_rgb is None:
            merged["fallback"] = True
            merged["errors"] = [str(diagnostics.get("reason") or "depth frame unavailable")]
            self._ar_pbr_last_diagnostics = merged
            return rgb
        merged["fallback"] = False
        self._ar_pbr_last_diagnostics = merged
        return depth_rgb
    except Exception as exc:
        self._ar_pbr_last_diagnostics = {
            "ok": False,
            "fallback": True,
            "mode": "depth_view",
            "preview_renderer_selected": "depth_map_only",
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
        return rgb

def _ar_pbr_software_settings(self, active_tracks: list[dict], renderer: str = "software_pbr") -> dict:
    descriptors = self._ar_pbr_asset_descriptors(active_tracks)
    renderer_name = str(renderer or "software_pbr")
    settings = {
        "renderer": renderer_name,
        "asset_descriptors": descriptors,
        "asset_support": self._ar_pbr_public_asset_support_rows(active_tracks, descriptors),
        "camera_z": 3.25,
        "shadow_blur": 3.0,
    }
    if renderer_name in {"full_gpu", "offscreen_gpu", "model_view_gpu", "native_gpu"}:
        settings["enable_shadow_map"] = True
    return settings

def _ar_pbr_cache_digest(value: object) -> str:
    from app.ar_pbr.preview_pipeline import cache_digest

    return cache_digest(value)

def _ar_pbr_descriptor_fingerprint(descriptor: Mapping | None) -> tuple:
    from app.ar_pbr.preview_pipeline import descriptor_fingerprint

    return descriptor_fingerprint(descriptor)

def _ar_pbr_descriptor_has_playing_animation(track: Mapping, descriptor: Mapping | None) -> bool:
    from app.ar_pbr.preview_pipeline import descriptor_has_playing_animation

    return descriptor_has_playing_animation(track, descriptor)

def _ar_pbr_gpu_packet_cache_key(
    self,
    context: Mapping,
    active_tracks: list[dict],
    settings: Mapping,
    triangle_limit: int,
) -> tuple | None:
    from app.ar_pbr.preview_pipeline import gpu_packet_cache_key

    return gpu_packet_cache_key(
        playing=self._state is PlayerState.PLAYING,
        context=context,
        active_tracks=active_tracks,
        settings=settings,
        triangle_limit=triangle_limit,
    )

def _ar_pbr_tag_gpu_packet_items(items: list[dict], cache_key: tuple | None) -> str:
    if cache_key is None or len(cache_key) < 2:
        return ""
    token = str(cache_key[1] or "")
    if not token:
        return ""
    for item in items:
        if isinstance(item, dict):
            item["packet_cache_id"] = token
    return token

def _composite_ar_pbr_tracks(
    self,
    rgb: np.ndarray,
    pos_ms: int,
    *,
    context: dict | None = None,
    renderer: str = "software_pbr",
) -> np.ndarray:
    context = context or self._ar_pbr_preview_context(rgb, pos_ms)
    if context is None:
        return rgb
    try:
        from app.ar_pbr.compositor import composite_preview_frame

        active_runtime = list(context.get("active_tracks") or [])
        settings = self._ar_pbr_software_settings(active_runtime, renderer=renderer)
        out, diagnostics = composite_preview_frame(
            rgb,
            time_ms=int(pos_ms),
            ar_tracks=list(context.get("tracks") or []),
            camera_solution=context.get("camera_solution"),
            depth_frame=context.get("depth_frame"),
            settings=settings,
        )
        runtime_diags = list(context.get("runtime_diagnostics") or [])
        if runtime_diags:
            diagnostics["runtime_scene_anchor"] = runtime_diags
        if settings.get("asset_support"):
            diagnostics["asset_support"] = list(settings.get("asset_support") or [])
        self._ar_pbr_last_diagnostics = diagnostics
        return np.ascontiguousarray(out) if out is not rgb else rgb
    except Exception as exc:
        self._ar_pbr_last_diagnostics = {
            "ok": False,
            "fallback": True,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
        return rgb

def _apply_or_defer_ar_pbr_overlay(self, rgb: np.ndarray, pos_ms: int) -> tuple[np.ndarray, dict | None]:
    context = self._ar_pbr_preview_context(rgb, pos_ms)
    if context is None:
        depth_context = self._ar_pbr_depth_view_context_for_frame(rgb, pos_ms)
        if depth_context is not None:
            depth_view_rgb = self._ar_pbr_depth_view_frame(rgb, depth_context, pos_ms)
            if depth_view_rgb is not None:
                return depth_view_rgb, None
        return rgb, None
    depth_view_rgb = self._ar_pbr_depth_view_frame(rgb, context, pos_ms)
    if depth_view_rgb is not None:
        return depth_view_rgb, None
    active_runtime = list(context.get("active_tracks") or [])
    preview_renderer = self._ar_pbr_preview_renderer_mode()
    if preview_renderer == "off":
        return rgb, None

    def _try_gpu_packet_overlay() -> tuple[np.ndarray, dict | None] | None:
        if not (
            self._ar_pbr_gpu_preview_enabled()
            and active_runtime
            and preview_renderer in {"auto", "packet", "full_gpu"}
        ):
            return None
        try:
            from app.ar_pbr.gpu_preview import build_gpu_preview_items

            triangle_limit = self._ar_pbr_gpu_preview_triangle_limit()
            settings = {
                **self._ar_pbr_software_settings(active_runtime),
                "gpu_triangle_limit": triangle_limit,
            }
            cache_key = self._ar_pbr_gpu_packet_cache_key(
                context,
                active_runtime,
                settings,
                triangle_limit,
            )
            if cache_key is not None:
                cached = self._ar_pbr_gpu_packet_cache.get(cache_key)
                if cached is not None:
                    items, cached_diagnostics = cached
                    diagnostics = dict(cached_diagnostics or {})
                    runtime_diags = list(context.get("runtime_diagnostics") or [])
                    if runtime_diags:
                        diagnostics["runtime_scene_anchor"] = runtime_diags
                    diagnostics["packet_cache_hit"] = True
                    diagnostics["playback_optimized"] = self._state is PlayerState.PLAYING
                    cache_token = self._ar_pbr_tag_gpu_packet_items(items, cache_key)
                    if cache_token:
                        diagnostics["packet_cache_id"] = cache_token
                    self._ar_pbr_last_diagnostics = diagnostics
                    if items:
                        return rgb, {"ar_pbr_items": items}
            items, diagnostics = build_gpu_preview_items(
                frame_size=(int(context.get("width") or rgb.shape[1]), int(context.get("height") or rgb.shape[0])),
                time_ms=int(pos_ms),
                ar_tracks=list(context.get("tracks") or []),
                camera_solution=context.get("camera_solution"),
                depth_frame=context.get("depth_frame"),
                settings=settings,
            )
            runtime_diags = list(context.get("runtime_diagnostics") or [])
            if runtime_diags:
                diagnostics["runtime_scene_anchor"] = runtime_diags
            if settings.get("asset_support"):
                diagnostics["asset_support"] = list(settings.get("asset_support") or [])
            diagnostics["playback_optimized"] = self._state is PlayerState.PLAYING
            diagnostics["packet_cache_hit"] = False
            cache_token = self._ar_pbr_tag_gpu_packet_items(items, cache_key)
            if cache_token:
                diagnostics["packet_cache_id"] = cache_token
            self._ar_pbr_last_diagnostics = diagnostics
            if items:
                if cache_key is not None:
                    self._ar_pbr_gpu_packet_cache[cache_key] = (items, dict(diagnostics))
                    self._ar_pbr_gpu_packet_cache.move_to_end(cache_key)
                    while len(self._ar_pbr_gpu_packet_cache) > 8:
                        self._ar_pbr_gpu_packet_cache.popitem(last=False)
                return rgb, {"ar_pbr_items": items}
        except Exception as exc:
            self._ar_pbr_last_diagnostics = {
                "ok": False,
                "fallback": True,
                "mode": "gpu_preview",
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
        return None

    if active_runtime and self._ar_pbr_should_use_full_gpu_preview():
        full_gpu_rgb = self._composite_ar_pbr_tracks(
            rgb,
            pos_ms,
            context=context,
            renderer="full_gpu",
        )
        full_gpu_diag = dict(getattr(self, "_ar_pbr_last_diagnostics", {}) or {})
        full_gpu_ok = bool(full_gpu_diag.get("ok", True)) and not bool(full_gpu_diag.get("fallback"))
        if full_gpu_ok:
            full_gpu_diag["preview_renderer_selected"] = "full_gpu"
            full_gpu_diag["packet_preview_skipped"] = True
            self._ar_pbr_last_diagnostics = full_gpu_diag
            return full_gpu_rgb, None
        packet_fallback = _try_gpu_packet_overlay()
        if packet_fallback is not None:
            fallback_diag = dict(getattr(self, "_ar_pbr_last_diagnostics", {}) or {})
            fallback_diag["preview_renderer_selected"] = "packet_fallback_after_full_gpu"
            fallback_diag["full_gpu_preview_failed"] = full_gpu_diag
            self._ar_pbr_last_diagnostics = fallback_diag
            return packet_fallback
        return full_gpu_rgb, None

    packet_result = _try_gpu_packet_overlay()
    if packet_result is not None:
        return packet_result
    if (
        self._ar_pbr_gpu_preview_enabled()
        and active_runtime
        and preview_renderer in {"auto", "packet", "full_gpu"}
        and self._state is PlayerState.PLAYING
    ):
        diagnostics = dict(getattr(self, "_ar_pbr_last_diagnostics", {}) or {})
        diagnostics.setdefault("ok", True)
        diagnostics.setdefault("mode", "gpu_preview")
        diagnostics["fallback"] = False
        diagnostics["software_fallback_skipped"] = True
        warnings = diagnostics.get("warnings")
        if not isinstance(warnings, list):
            warnings = []
        warnings.append("software ar/pbr fallback skipped during playback")
        diagnostics["warnings"] = warnings
        self._ar_pbr_last_diagnostics = diagnostics
        return rgb, None
    fallback_renderer = "software_pbr" if preview_renderer in {"auto", "software_pbr"} else preview_renderer
    return self._composite_ar_pbr_tracks(
        rgb,
        pos_ms,
        context=context,
        renderer=fallback_renderer,
    ), None
