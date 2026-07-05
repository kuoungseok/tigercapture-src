from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtGui import QPixmap

from app.i18n import tr
from app.timeline_model import (
    CutSegment,
    FadeSegment,
    NodeGraph,
    SpeedSegment,
    ZoomActor,
    build_legacy_clips_view,
)


def _new_node_graph():
    """Default factory for the legacy editor track node graph."""
    return NodeGraph.default()


def _ensure_video_clips(track, *, force: bool = False) -> None:
    """First-time sync of ``track.clips`` from the legacy fields."""
    if track.clips and not force:
        track.clips_explicit = True
        return
    track.clips = build_legacy_clips_view(track)
    track.clips_explicit = True


@dataclass
class VideoTrack:
    id: int
    source_path: Path | None = None
    label: str = ""
    track_type: str = "video"
    performance_source: bool = False
    vtuber_performance_source: bool = False
    program_output: bool = True
    _original_source_path: Path | None = None
    duration_ms: int = 0
    offset_ms: int = 0
    speed_segments: list[SpeedSegment] = field(default_factory=list)
    cuts: list[CutSegment] = field(default_factory=list)
    fades: list[FadeSegment] = field(default_factory=list)
    thumbnails: list[QPixmap] = field(default_factory=list)
    selection_start_ms: int = -1
    selection_end_ms: int = -1
    typography_actors: list = field(default_factory=list)
    node_graph: object = field(default_factory=_new_node_graph)
    zoom_actors: list[ZoomActor] = field(default_factory=list)
    cursor_events: list[dict] = field(default_factory=list)
    screenstudio_polish: dict = field(default_factory=dict)
    clips: list = field(default_factory=list)
    clips_explicit: bool = False
    node_graph_view_data: dict | None = None
    pip_enabled: bool = False
    pip_x: float = 0.5
    pip_y: float = 0.5
    pip_scale: float = 0.3
    pip_opacity: float = 1.0
    pip_keyframes: list = field(default_factory=list)
    preview_color_compare_mode: str = ""
    preview_compare_labels_enabled: bool = True

    @property
    def display_name(self) -> str:
        custom = str(getattr(self, "label", "") or getattr(self, "name", "") or "")
        if custom:
            return custom
        if self.source_path is None:
            clip_paths = {
                c.source_path for c in self.clips
                if getattr(c, "source_path", None) is not None
            }
            if not clip_paths:
                return tr("veditor.track.empty")
            if len(clip_paths) == 1:
                return next(iter(clip_paths)).name
            return f"{len(self.clips)} clips"
        return self.source_path.name

    @property
    def color_grade(self):
        ng = self.node_graph
        if ng is None:
            return None
        return getattr(ng, "color", None) and ng.color.grade

    @color_grade.setter
    def color_grade(self, value) -> None:
        from app.timeline_model import ColorNode

        ng = self.node_graph
        if ng is None or getattr(ng, "color", None) is None:
            self.node_graph = NodeGraph(color=ColorNode(grade=value))
        else:
            ng.color.grade = value


__all__ = ["VideoTrack", "_ensure_video_clips", "_new_node_graph"]
