from __future__ import annotations

from pathlib import Path

from app.audio_tracks import is_audio_path, is_video_path
from app.media_asset_routing import motion_project_paths_from_mime
from app.video_editor_media_import_controller import (
    TARGET_WINDOW,
    dispatch_import_decision,
    route_mime_drop,
)

MIN_TRACK_WIDTH = 300


def dropEvent(self, event: QDropEvent) -> None:
    md = event.mimeData()
    vrm_paths = self._vrm_avatar_paths_from_mime(md)
    if vrm_paths:
        avatar = vrm_paths[0]
        if hasattr(self, "_media_pool"):
            try:
                self._media_pool.add_path(avatar)
            except Exception:
                pass
        self._open_vrm_media_in_vtuber_studio(str(avatar))
        event.acceptProposedAction()
        return
    mmd_paths = self._mmd_paths_from_mime(md)
    if mmd_paths:
        self._add_mmd_asset_to_timeline(mmd_paths)
        event.acceptProposedAction()
        return
    motion_paths = motion_project_paths_from_mime(md)
    if motion_paths:
        self._import_motion_actor_from_path(
            motion_paths[0],
            start_ms=int(getattr(self._player, "position", lambda: 0)()),
        )
        event.acceptProposedAction()
        return
    if not md.hasUrls():
        try:
            start_ms = int(getattr(self._player, "position", lambda: 0)())
        except Exception:
            start_ms = 0
        decision = route_mime_drop(
            self,
            md,
            target=TARGET_WINDOW,
            start_ms=start_ms,
            image_point=(0.5, 0.62),
            open_audio_editor=True,
        )
        if decision.handled and dispatch_import_decision(self, decision):
            event.acceptProposedAction()
            return
        event.ignore()
        return
    ar_paths = self._ar_pbr_paths_from_mime(md)
    for u in md.urls():
        p = Path(u.toLocalFile())
        if is_video_path(p) or is_audio_path(p):
            # Pool registration first ??a drop on the empty
            # editor area still goes through the same DaVinci-
            # style path: pool ??timeline.
            if hasattr(self, "_media_pool"):
                self._media_pool.add_path(p)
        if is_video_path(p):
            if self._performance_source_paths_from_mime(md):
                self._add_performance_source_clip(
                    p,
                    int(getattr(self._player, "position", lambda: 0)()),
                )
                event.acceptProposedAction()
                return
            self._add_track_with_source(p)
            event.acceptProposedAction()
            return
        if is_audio_path(p):
            # OS file-drop opens the sound editor straight away ??
            # the user explicitly asked for a per-clip drop = edit
            # flow. Programmatic adds (project load, append) still
            # use the default open_editor=False.
            self._add_audio_track_with_source(p, open_editor=True)
            event.acceptProposedAction()
            return
        if ar_paths:
            self._add_ar_pbr_asset_to_preview(ar_paths[0], image_point=(0.5, 0.62))
            event.acceptProposedAction()
            return
    event.ignore()


def _update_tracks_host_width(self) -> None:
    # Start with baseline (ruler) and each track's own preferred width.
    max_w = max(MIN_TRACK_WIDTH, self._timeline_ruler.desired_width())
    # Consider each row's natural duration-driven width.
    for row in self._track_rows.values():
        row_pref = max(MIN_TRACK_WIDTH, row._preferred_width())
        max_w = max(max_w, row_pref)
    for row in self._audio_rows.values():
        row_pref = max(MIN_TRACK_WIDTH, row._preferred_width())
        max_w = max(max_w, row_pref)
    for row in getattr(self, "_actor_lane_rows", []):
        pref_fn = getattr(row, "_preferred_width", None)
        row_pref = pref_fn() if callable(pref_fn) else MIN_TRACK_WIDTH
        max_w = max(max_w, max(MIN_TRACK_WIDTH, row_pref))
    for row in getattr(self, "_live2d_lane_rows", []):
        pref_fn = getattr(row, "_preferred_width", None)
        if callable(pref_fn):
            row_pref = pref_fn()
        else:
            span_ms = max((c.end_ms for c in row.track.clips), default=0)
            row_pref = int(span_ms / 1000.0 * self._px_per_sec) + 160
        max_w = max(max_w, max(MIN_TRACK_WIDTH, row_pref))
    for row in getattr(self, "_ar_pbr_lane_rows", []):
        pref_fn = getattr(row, "_preferred_width", None)
        row_pref = pref_fn() if callable(pref_fn) else MIN_TRACK_WIDTH
        max_w = max(max_w, max(MIN_TRACK_WIDTH, row_pref))
    for row in getattr(self, "_mmd_lane_rows", []):
        pref_fn = getattr(row, "_preferred_width", None)
        row_pref = pref_fn() if callable(pref_fn) else MIN_TRACK_WIDTH
        max_w = max(max_w, max(MIN_TRACK_WIDTH, row_pref))
    for row in getattr(self, "_motion_lane_rows", []):
        pref_fn = getattr(row, "_preferred_width", None)
        row_pref = pref_fn() if callable(pref_fn) else MIN_TRACK_WIDTH
        max_w = max(max_w, max(MIN_TRACK_WIDTH, row_pref))
    # Also honor the viewport width so the divider / stripes can extend
    # the full visible area even when clips are short.
    vp_w = self._tracks_scroll.viewport().width() if hasattr(self, "_tracks_scroll") else 0
    max_w = max(max_w, vp_w)
    # Stretch every row + the ruler to the same width so the bottom
    # separator runs edge-to-edge regardless of clip length.
    self._timeline_ruler.setFixedWidth(max_w)
    for row in self._track_rows.values():
        row.setFixedWidth(max_w)
    for row in self._audio_rows.values():
        row.setFixedWidth(max_w)
    for row in getattr(self, "_actor_lane_rows", []):
        row.setFixedWidth(max_w)
    for row in getattr(self, "_live2d_lane_rows", []):
        row.setFixedWidth(max_w)
    for row in getattr(self, "_ar_pbr_lane_rows", []):
        row.setFixedWidth(max_w)
    for row in getattr(self, "_mmd_lane_rows", []):
        row.setFixedWidth(max_w)
    for row in getattr(self, "_motion_lane_rows", []):
        row.setFixedWidth(max_w)
    # Subtitle lane must match so its background fills the full timeline.
    if hasattr(self, "_subtitle_lane"):
        self._subtitle_lane.setFixedWidth(max_w)
    self._tracks_host.setMinimumWidth(max_w)


def _refresh_timeline_mixer_geometry(self, mixer_visible: bool | None = None) -> None:
    """Give the timeline enough vertical room when the mixer is open."""
    host = getattr(self, "_timeline_section_host", None)
    if host is None:
        return
    panel = getattr(self, "_audio_mixer_panel", None)
    visible = (
        bool(mixer_visible)
        if mixer_visible is not None
        else bool(panel is not None and panel.isVisible())
    )
    tracks_scroll = getattr(self, "_tracks_scroll", None)
    if visible:
        host.setMinimumHeight(int(getattr(self, "_timeline_mixer_min_height", 430)))
        host.setMaximumHeight(int(getattr(self, "_timeline_mixer_max_height", 560)))
        if tracks_scroll is not None:
            tracks_scroll.setMinimumHeight(145)
    else:
        if tracks_scroll is not None:
            tracks_scroll.setMinimumHeight(170)
        host.setMinimumHeight(int(getattr(self, "_timeline_compact_min_height", 210)))
        host.setMaximumHeight(int(getattr(self, "_timeline_compact_max_height", 310)))

    splitter = getattr(self, "_color_timeline_splitter", None)
    if splitter is not None:
        timeline_idx = splitter.indexOf(host)
        if timeline_idx >= 0:
            sizes = list(splitter.sizes())
            if timeline_idx < len(sizes):
                color_container = getattr(self, "_color_container", None)
                color_idx = (
                    splitter.indexOf(color_container)
                    if color_container is not None
                    else -1
                )
                if visible:
                    sizes[timeline_idx] = max(
                        sizes[timeline_idx],
                        int(getattr(self, "_timeline_mixer_min_height", 430)),
                    )
                    if 0 <= color_idx < len(sizes) and not color_container.isVisible():
                        sizes[color_idx] = 0
                else:
                    sizes[timeline_idx] = max(sizes[timeline_idx], 260)
                splitter.setSizes(sizes)
                splitter.updateGeometry()
    if tracks_scroll is not None:
        tracks_scroll.updateGeometry()
    host.updateGeometry()
    self.updateGeometry()
