from __future__ import annotations

from pathlib import Path


def _on_blur_params_changed(self) -> None:
    self._rebuild_active_chain()


def _on_effect_params_changed(self) -> None:
    self._rebuild_active_chain()


def _rebuild_active_chain(self) -> None:
    """Build ``track.color_grade_chain`` for the active track.
    During active playback the chain references are updated
    immediately (the next timer tick will pick them up) but we
    skip the expensive ``refresh_current_frame()`` call to avoid
    blocking the GUI thread mid-playback ??clicking nodes while
    playing would otherwise queue up multiple full decodes and
    freeze the interface.
    DaVinci-style "main viewer follows the selected node":

      - Selected node X ??chain = IN?萸?(so the main preview shows
        the cumulative result *up to and including* X)
      - No selection / OUT selected ??chain = full IN?萸UT
      - IN node selected ??chain = empty (raw source frame)

    Called on:
      - track switch (set_active_track ??set_video_track)
      - graph mutation (node added/removed/connected)
      - node selection change (so the preview updates instantly)

    Slider edits *don't* trigger this ??they mutate ColorGrade /
    mask objects in place, and the chain references stay valid.
    """
    track = self._active_track()
    if track is None:
        return
    wb = getattr(self, "_workbench_panel", None)
    ngw = wb.expose_node_graph_widget() if wb is not None else None
    if ngw is None:
        track.color_grade_chain = None
        track.node_mask_chain = None
        return
    target_node = self._select_view_target_node(ngw.scene)
    try:
        grades, masks = self._evaluate_node_chain_with_masks(
            ngw.scene, target_node,
        )
    except Exception:
        grades = []
        masks = []
    # Empty chain when the user selected the IN node (raw source
    # is the right preview). For other "no chain" cases (audio
    # clip, project just loaded) leave None so ProjectPlayer
    # falls back to the legacy single ``track.color_grade``.
    if target_node is not None and getattr(target_node, "kind", "") == "IN":
        track.color_grade_chain = []
        track.node_mask_chain = []
        track.node_item_chain = []
    else:
        track.color_grade_chain = grades or None
        track.node_mask_chain = masks or None
        # Build unified node_item_chain for the new render path.
        # Walks the same IN?萸챏rget path and collects (node, masks) pairs
        # so that BlurNode items are applied in the correct sequence.
        try:
            ni_chain = self._build_node_item_chain(ngw.scene, target_node)
        except Exception:
            ni_chain = None
        track.node_item_chain = ni_chain or None
    self._prewarm_tracking_caches_for_track(track)
    generation = self._player.clear_preview_prerender_cache() if hasattr(self, "_player") else 0
    self._start_preview_prerender_for_track(track, generation)
    # Only force a frame refresh when paused/stopped.
    from app.simple_video_player import PlayerState
    if (hasattr(self, "_player")
            and self._player.state() is not PlayerState.PLAYING):
        self._player.refresh_current_frame()
    # Also force a thumbnail update so nodes reflect the new
    # chain immediately (otherwise the 100 ms throttle leaves
    # them showing stale/black thumbnails after connecting).
    # Guard: only update when there is an active clip at the current
    # position so a Delete or track-switch doesn't wipe thumbnails black.
    _pos = self._player.position() if hasattr(self, "_player") else 0
    _has_active_now = any(
        int(c.timeline_in_ms) <= _pos <= int(c.timeline_out_ms)
        for t in self._tracks
        for c in getattr(t, "clips", [])
        if getattr(c, "source_path", None) is not None
    )
    if (_has_active_now
            and hasattr(self, "_preview_pixmap")
            and self._preview_pixmap is not None
            and not self._preview_pixmap.isNull()):
        wb = getattr(self, "_workbench_panel", None)
        if wb is not None:
            try:
                wb.set_node_thumbnail(self._preview_pixmap)
                self._last_node_thumb_ms = 0.0  # reset throttle
            except Exception:
                pass


def _tracking_cache_source_for_track(self, track) -> Path | None:
    source = getattr(track, "source_path", None)
    if source is not None:
        return Path(source)
    pos = self._player.position() if hasattr(self, "_player") else 0
    clips = list(getattr(track, "clips", []) or [])
    for clip in clips:
        sp = getattr(clip, "source_path", None)
        if sp is None:
            continue
        start = int(getattr(clip, "timeline_in_ms", getattr(clip, "offset_ms", 0)) or 0)
        end = int(
            getattr(
                clip,
                "timeline_out_ms",
                start + int(getattr(clip, "effective_length_ms", 0) or 0),
            )
            or 0
        )
        if start <= pos <= end:
            return Path(sp)
    for clip in clips:
        sp = getattr(clip, "source_path", None)
        if sp is not None:
            return Path(sp)
    return None


def _prewarm_tracking_caches_for_track(self, track) -> None:
    source = self._tracking_cache_source_for_track(track)
    if source is None:
        return
    try:
        from app.node_mask import BitmapMask
        from app.tracking_cache_worker import ObjectTrackingCacheWorker
    except Exception:
        return
    jobs = getattr(self, "_tracking_cache_jobs", None)
    if jobs is None:
        jobs = {}
        self._tracking_cache_jobs = jobs
    chain = list(getattr(track, "node_item_chain", None) or [])
    for _node_item, masks in chain:
        for mask in list(masks or []):
            if not isinstance(mask, BitmapMask) or not getattr(mask, "track_object", False):
                continue
            if not getattr(mask, "encoded_png", ""):
                continue
            if len(getattr(mask, "tracking_cache_bboxes", {}) or {}) >= 120:
                continue
            key = (id(mask), str(source), int(getattr(mask, "init_frame", 0) or 0))
            if key in jobs:
                continue
            worker = ObjectTrackingCacheWorker(
                source,
                mask.to_dict(),
                start_frame=int(getattr(mask, "init_frame", 0) or 0),
                max_frames=600,
            )
            jobs[key] = worker
            worker.ready.connect(
                lambda bboxes, failed, _mask=mask, _key=key: (
                    self._on_tracking_cache_ready(_mask, _key, bboxes, failed)
                )
            )
            worker.failed.connect(
                lambda reason, _key=key: self._on_tracking_cache_failed(_key, reason)
            )
            worker.finished.connect(
                lambda _key=key, _worker=worker: self._retire_tracking_cache_worker(
                    _key, _worker
                )
            )
            worker.start()


def _on_tracking_cache_ready(self, mask, key, bboxes, failed_frames) -> None:
    try:
        normalized = {
            int(frame): tuple(float(v) for v in box)
            for frame, box in dict(bboxes or {}).items()
            if box is not None and len(box) == 4
        }
        mask.tracking_cache_bboxes.update(normalized)
        mask.tracking_failed_frames.update(int(v) for v in (failed_frames or []))
        mask._track_cache = None
        mask._failed_frames = None
        mask._tracking_message = f"prewarmed {len(normalized)} frames"
    except Exception:
        pass


def _on_tracking_cache_failed(self, key, reason: str) -> None:
    try:
        print(f"[tracking-cache] failed {key}: {str(reason)[:160]}")
    except Exception:
        pass


def _retire_tracking_cache_worker(self, key, worker) -> None:
    jobs = getattr(self, "_tracking_cache_jobs", {})
    if jobs.get(key) is worker:
        jobs.pop(key, None)
    try:
        worker.deleteLater()
    except Exception:
        pass


def _start_preview_prerender_for_track(self, track, generation: int) -> None:
    self._cancel_preview_prerender_jobs()
    source = self._tracking_cache_source_for_track(track)
    if source is None:
        return
    chain = getattr(track, "node_item_chain", None)
    if not chain:
        return
    for node_item, _masks in chain:
        grade = getattr(node_item, "color_grade", None)
        if grade is not None and not grade.is_identity():
            return
    try:
        snapshot = self._snapshot_node_item_chain_for_export(track)
        if not snapshot:
            return
        from app.preview_prerender_worker import PreviewPrerenderWorker
    except Exception:
        return
    try:
        start_frame = max(0, int(self._current_preview_frame_idx()) + 1)
    except Exception:
        start_frame = int(getattr(self._player, "_last_rendered_frame_idx", 0) or 0)
    worker = PreviewPrerenderWorker(
        source,
        snapshot,
        start_frame=start_frame,
        frame_count=60,
    )
    key = (int(getattr(track, "id", 0) or 0), str(source), int(generation))
    jobs = getattr(self, "_preview_prerender_jobs", None)
    if jobs is None:
        jobs = {}
        self._preview_prerender_jobs = jobs
    jobs[key] = worker
    worker.frame_ready.connect(
        lambda frame_idx, rgb, _tid=track.id, _source=source, _gen=generation: (
            self._player.put_preview_prerender_frame(
                _tid, _source, frame_idx, _gen, rgb
            )
        )
    )
    worker.failed.connect(
        lambda reason, _key=key: print(
            f"[preview-prerender] failed {_key}: {str(reason)[:160]}"
        )
    )
    worker.finished.connect(
        lambda _key=key, _worker=worker: self._retire_preview_prerender_worker(
            _key, _worker
        )
    )
    worker.start()


def _cancel_preview_prerender_jobs(self) -> None:
    jobs = getattr(self, "_preview_prerender_jobs", None)
    if not jobs:
        self._preview_prerender_jobs = {}
        return
    retired = getattr(self, "_retired_preview_prerender_jobs", None)
    if retired is None:
        retired = []
        self._retired_preview_prerender_jobs = retired
    for worker in list(jobs.values()):
        try:
            worker.requestInterruption()
        except Exception:
            pass
        retired.append(worker)
    jobs.clear()


def _retire_preview_prerender_worker(self, key, worker) -> None:
    jobs = getattr(self, "_preview_prerender_jobs", {})
    if jobs.get(key) is worker:
        jobs.pop(key, None)
    retired = getattr(self, "_retired_preview_prerender_jobs", [])
    try:
        if worker in retired:
            retired.remove(worker)
    except Exception:
        pass
    try:
        worker.deleteLater()
    except Exception:
        pass


def _export_zoom_actors_for_track(track) -> list:
    actors = list(getattr(track, "zoom_actors", []) or [])
    clips = list(getattr(track, "clips", []) or [])
    if not clips:
        return actors
    source_paths = {
        str(getattr(c, "source_path", "") or "")
        for c in clips
        if getattr(c, "source_path", None) is not None
    }
    track_source = str(getattr(track, "source_path", "") or "")
    can_merge_clip_zooms = len(source_paths) <= 1 and (
        not track_source or not source_paths or track_source in source_paths
    )
    if not can_merge_clip_zooms:
        return actors
    seen = {
        (
            int(getattr(z, "start_ms", 0) or 0),
            int(getattr(z, "end_ms", 0) or 0),
            int(getattr(z, "target_x", 0) or 0),
            int(getattr(z, "target_y", 0) or 0),
            int(getattr(z, "target_w", 0) or 0),
            int(getattr(z, "target_h", 0) or 0),
            str(getattr(z, "easing", "smooth_pop") or "smooth_pop"),
            round(float(getattr(z, "motion_blur", 0.0) or 0.0), 3),
        )
        for z in actors
    }
    for clip in clips:
        for z in getattr(clip, "zoom_actors", []) or []:
            key = (
                int(getattr(z, "start_ms", 0) or 0),
                int(getattr(z, "end_ms", 0) or 0),
                int(getattr(z, "target_x", 0) or 0),
                int(getattr(z, "target_y", 0) or 0),
                int(getattr(z, "target_w", 0) or 0),
                int(getattr(z, "target_h", 0) or 0),
                str(getattr(z, "easing", "smooth_pop") or "smooth_pop"),
                round(float(getattr(z, "motion_blur", 0.0) or 0.0), 3),
            )
            if key in seen:
                continue
            actors.append(z)
            seen.add(key)
    actors.sort(key=lambda z: int(getattr(z, "start_ms", 0) or 0))
    return actors

