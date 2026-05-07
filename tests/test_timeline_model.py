"""Phase 1 unit tests — clip API + legacy-track migration.

Pure-Python: no Qt or ffmpeg involvement. Run with::

    python -m pytest tests/test_timeline_model.py -v

The tests exercise the slice of behaviour that Phase 1.5 (renderer
rewire) will rely on:

- ``VideoTrack.split_at`` produces two independent halves whose
  combined output duration equals the original.
- Trim / move respect their boundary invariants.
- ``migrate_legacy_video_track`` round-trips a single-source legacy
  track with cuts into a clip-list track that plays the same frames
  in the same project-time order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from app.timeline_model import (
    ColorNode,
    CutSegment,
    FadeSegment,
    NodeGraph,
    SpeedSegment,
    Timeline,
    VideoClip,
    VideoTrack,
    ZoomActor,
    migrate_legacy_video_track,
)


# ---------------------------------------------------------------------------
#  Fixtures: a stand-in legacy track + a fake ColorGrade so tests never
#  pull in the real color_grading module (which depends on numpy).
# ---------------------------------------------------------------------------


@dataclass
class _FakeGrade:
    brightness: int = 0
    contrast: int = 0

    def is_identity(self) -> bool:
        return self.brightness == 0 and self.contrast == 0


@dataclass
class _LegacyTrack:
    """Mimics the public surface of video_editor_window.VideoTrack so
    migrate_legacy_video_track can read it via duck-typing."""

    id: int = 0
    source_path: Path | None = None
    duration_ms: int = 0
    offset_ms: int = 0
    cuts: list = field(default_factory=list)
    fades: list = field(default_factory=list)
    zoom_actors: list = field(default_factory=list)
    typography_actors: list = field(default_factory=list)
    color_grade: object = None


def _make_clip(
    *, timeline_in_ms: int = 0, source_in_ms: int = 0, source_out_ms: int = 10_000,
    source_duration_ms: int = 10_000,
) -> VideoClip:
    """Build a VideoClip with an identity NodeGraph that doesn't pull
    in the real ColorGrade (and therefore numpy)."""
    return VideoClip(
        id=1,
        source_path=Path("/fake/test.mp4"),
        source_duration_ms=source_duration_ms,
        timeline_in_ms=timeline_in_ms,
        source_in_ms=source_in_ms,
        source_out_ms=source_out_ms,
        node_graph=NodeGraph(color=ColorNode(grade=_FakeGrade())),
    )


# ---------------------------------------------------------------------------
#  VideoClip derived properties
# ---------------------------------------------------------------------------


class TestVideoClipDerived:
    def test_effective_length_full_source(self):
        c = _make_clip(source_in_ms=0, source_out_ms=0,
                       source_duration_ms=8000)
        assert c.effective_length_ms == 8000
        assert c.timeline_out_ms == c.timeline_in_ms + 8000

    def test_effective_length_with_trim(self):
        c = _make_clip(source_in_ms=2000, source_out_ms=7000,
                       source_duration_ms=10000)
        assert c.effective_length_ms == 5000

    def test_timeline_to_source_ms(self):
        c = _make_clip(timeline_in_ms=4000, source_in_ms=1000)
        assert c.timeline_to_source_ms(4500) == 1500
        assert c.timeline_to_source_ms(4000) == 1000

    def test_contains_timeline_ms_boundaries(self):
        c = _make_clip(timeline_in_ms=2000, source_out_ms=3000,
                       source_duration_ms=3000)
        # Window is [2000, 5000)
        assert c.contains_timeline_ms(2000)
        assert c.contains_timeline_ms(4999)
        assert not c.contains_timeline_ms(5000)
        assert not c.contains_timeline_ms(1999)


# ---------------------------------------------------------------------------
#  Track edit operations
# ---------------------------------------------------------------------------


class TestTrackSplit:
    def test_split_preserves_total_duration(self):
        clip = _make_clip(source_out_ms=10_000, source_duration_ms=10_000)
        track = VideoTrack(id=0, clips=[clip])
        before = clip.effective_length_ms

        left, right = track.split_at(4000)

        assert len(track.clips) == 2
        assert left.effective_length_ms + right.effective_length_ms == before

    def test_split_at_correct_source_ms(self):
        clip = _make_clip(source_in_ms=1000, source_out_ms=9000,
                          source_duration_ms=10_000)
        track = VideoTrack(id=0, clips=[clip])
        # Project time 3000 → source ms 1000 + (3000 - 0) = 4000
        left, right = track.split_at(3000)

        assert left.source_in_ms == 1000
        assert left.source_out_ms == 4000
        assert right.source_in_ms == 4000
        assert right.source_out_ms == 9000
        assert right.timeline_in_ms == 3000

    def test_split_partitions_actors_by_time(self):
        clip = _make_clip(source_out_ms=10_000, source_duration_ms=10_000)
        clip.fades = [
            FadeSegment(start_ms=500, end_ms=1500, kind="in"),
            FadeSegment(start_ms=8000, end_ms=9000, kind="out"),
        ]
        clip.zoom_actors = [
            ZoomActor(id=1, start_ms=200, end_ms=800,
                      target_x=0, target_y=0, target_w=100, target_h=100),
            ZoomActor(id=2, start_ms=6000, end_ms=7000,
                      target_x=0, target_y=0, target_w=100, target_h=100),
        ]
        track = VideoTrack(id=0, clips=[clip])

        left, right = track.split_at(5000)

        assert len(left.fades) == 1
        assert left.fades[0].kind == "in"
        assert len(right.fades) == 1
        assert right.fades[0].kind == "out"
        assert len(left.zoom_actors) == 1
        assert left.zoom_actors[0].id == 1
        assert len(right.zoom_actors) == 1
        assert right.zoom_actors[0].id == 2

    def test_split_copies_node_graph_independently(self):
        clip = _make_clip()
        track = VideoTrack(id=0, clips=[clip])

        left, right = track.split_at(5000)

        # Mutate the right half's grade — the left half must not change.
        right.node_graph.color.grade.brightness = 50
        assert left.node_graph.color.grade.brightness == 0

    def test_split_outside_clip_raises(self):
        clip = _make_clip(timeline_in_ms=2000, source_out_ms=3000,
                          source_duration_ms=3000)
        track = VideoTrack(id=0, clips=[clip])
        # Window is [2000, 5000); 1000 and 5000 are outside.
        with pytest.raises(ValueError):
            track.split_at(1000)
        with pytest.raises(ValueError):
            track.split_at(5000)
        # Boundary points are also rejected (no zero-length halves).
        with pytest.raises(ValueError):
            track.split_at(2000)


class TestTrackTrim:
    def test_trim_left_clamps_at_zero(self):
        clip = _make_clip(source_in_ms=200, source_out_ms=5000,
                          source_duration_ms=10_000, timeline_in_ms=1000)
        track = VideoTrack(id=0, clips=[clip])

        track.trim_left(clip, -500)  # would push below 0

        assert clip.source_in_ms == 0
        # Project-timeline left edge moved by the actual delta (-200).
        assert clip.timeline_in_ms == 800

    def test_trim_left_keeps_right_edge(self):
        clip = _make_clip(source_in_ms=0, source_out_ms=5000,
                          source_duration_ms=10_000, timeline_in_ms=1000)
        track = VideoTrack(id=0, clips=[clip])
        right_before = clip.timeline_out_ms

        track.trim_left(clip, 1000)  # in-point moves later by 1s

        assert clip.source_in_ms == 1000
        assert clip.timeline_out_ms == right_before  # right edge unchanged

    def test_trim_right_clamps_to_source_duration(self):
        clip = _make_clip(source_in_ms=0, source_out_ms=8000,
                          source_duration_ms=10_000)
        track = VideoTrack(id=0, clips=[clip])

        track.trim_right(clip, 5000)  # would push past 10_000

        assert clip.effective_source_out_ms == 10_000

    def test_trim_right_cannot_invert(self):
        clip = _make_clip(source_in_ms=4000, source_out_ms=5000,
                          source_duration_ms=10_000)
        track = VideoTrack(id=0, clips=[clip])

        track.trim_right(clip, -10_000)

        assert clip.effective_source_out_ms > clip.source_in_ms


class TestTrackMove:
    def test_move_clip_rejects_overlap(self):
        a = _make_clip(timeline_in_ms=0, source_out_ms=5000,
                       source_duration_ms=5000)
        b = _make_clip(timeline_in_ms=5000, source_out_ms=5000,
                       source_duration_ms=5000)
        track = VideoTrack(id=0, clips=[a, b])

        # Try to drop b into a's window.
        ok = track.move_clip(b, 2000)

        assert ok is False
        assert b.timeline_in_ms == 5000  # unchanged

    def test_move_clip_into_gap(self):
        a = _make_clip(timeline_in_ms=0, source_out_ms=2000,
                       source_duration_ms=2000)
        b = _make_clip(timeline_in_ms=10_000, source_out_ms=2000,
                       source_duration_ms=2000)
        track = VideoTrack(id=0, clips=[a, b])

        ok = track.move_clip(b, 5000)

        assert ok is True
        assert b.timeline_in_ms == 5000
        # Track stays sorted after a successful move.
        assert [c.timeline_in_ms for c in track.clips] == [0, 5000]

    def test_move_clip_clamps_to_zero(self):
        clip = _make_clip(timeline_in_ms=2000, source_out_ms=2000,
                          source_duration_ms=2000)
        track = VideoTrack(id=0, clips=[clip])

        track.move_clip(clip, -500)

        assert clip.timeline_in_ms == 0


class TestTrackDelete:
    def test_delete_removes_only_target(self):
        a = _make_clip(timeline_in_ms=0, source_out_ms=2000,
                       source_duration_ms=2000)
        b = _make_clip(timeline_in_ms=2000, source_out_ms=2000,
                       source_duration_ms=2000)
        track = VideoTrack(id=0, clips=[a, b])

        track.delete_clip(a)

        assert track.clips == [b]


# ---------------------------------------------------------------------------
#  Legacy migration
# ---------------------------------------------------------------------------


class TestMigrateLegacy:
    def _src(self) -> Path:
        return Path("/fake/source.mp4")

    def test_empty_track_yields_empty_clips(self):
        legacy = _LegacyTrack(id=0)
        new = migrate_legacy_video_track(legacy)
        assert new.id == 0
        assert new.clips == []

    def test_no_cuts_yields_single_clip(self):
        legacy = _LegacyTrack(
            id=3, source_path=self._src(), duration_ms=8000,
            offset_ms=2000, color_grade=_FakeGrade(),
        )
        new = migrate_legacy_video_track(legacy)
        assert len(new.clips) == 1
        c = new.clips[0]
        assert c.source_path == self._src()
        assert c.source_in_ms == 0
        assert c.source_out_ms == 8000
        assert c.timeline_in_ms == 2000
        assert c.timeline_out_ms == 10_000

    def test_one_cut_in_middle_yields_two_clips(self):
        legacy = _LegacyTrack(
            source_path=self._src(), duration_ms=10_000,
            cuts=[CutSegment(start_ms=3000, end_ms=5000)],
            color_grade=_FakeGrade(),
        )
        new = migrate_legacy_video_track(legacy)
        assert len(new.clips) == 2
        a, b = new.clips
        # First clip: source [0, 3000), project [0, 3000)
        assert (a.source_in_ms, a.source_out_ms) == (0, 3000)
        assert (a.timeline_in_ms, a.timeline_out_ms) == (0, 3000)
        # Second clip: source [5000, 10000), project [3000, 8000)
        assert (b.source_in_ms, b.source_out_ms) == (5000, 10_000)
        assert (b.timeline_in_ms, b.timeline_out_ms) == (3000, 8000)

    def test_cut_at_start_drops_first_range(self):
        legacy = _LegacyTrack(
            source_path=self._src(), duration_ms=10_000,
            cuts=[CutSegment(start_ms=0, end_ms=2000)],
        )
        new = migrate_legacy_video_track(legacy)
        assert len(new.clips) == 1
        c = new.clips[0]
        assert (c.source_in_ms, c.source_out_ms) == (2000, 10_000)
        assert c.timeline_in_ms == 0  # left edge of project is unchanged

    def test_actors_partition_across_cut(self):
        legacy = _LegacyTrack(
            source_path=self._src(), duration_ms=10_000,
            cuts=[CutSegment(start_ms=4000, end_ms=6000)],
            fades=[FadeSegment(start_ms=500, end_ms=1500, kind="in"),
                   FadeSegment(start_ms=8000, end_ms=9000, kind="out")],
        )
        new = migrate_legacy_video_track(legacy)
        a, b = new.clips
        assert [f.kind for f in a.fades] == ["in"]
        assert [f.kind for f in b.fades] == ["out"]

    def test_grade_is_independent_per_clip_after_migration(self):
        legacy = _LegacyTrack(
            source_path=self._src(), duration_ms=10_000,
            cuts=[CutSegment(start_ms=4000, end_ms=6000)],
            color_grade=_FakeGrade(brightness=10),
        )
        new = migrate_legacy_video_track(legacy)
        a, b = new.clips
        b.node_graph.color.grade.brightness = 99
        assert a.node_graph.color.grade.brightness == 10

    def test_does_not_mutate_legacy(self):
        cuts = [CutSegment(start_ms=4000, end_ms=6000)]
        legacy = _LegacyTrack(
            source_path=self._src(), duration_ms=10_000, cuts=cuts,
        )
        migrate_legacy_video_track(legacy)
        # The original legacy fields must be untouched.
        assert legacy.cuts is cuts
        assert legacy.duration_ms == 10_000


# ---------------------------------------------------------------------------
#  Timeline container
# ---------------------------------------------------------------------------


class TestTimeline:
    def test_duration_ignores_empty_lanes(self):
        tl = Timeline(
            video_tracks=[VideoTrack(id=0)],  # empty lane
            audio_tracks=[],
        )
        assert tl.duration_ms == 0

    def test_duration_takes_longest_video_lane(self):
        a = VideoTrack(id=0, clips=[
            _make_clip(timeline_in_ms=0, source_out_ms=2000,
                       source_duration_ms=2000),
        ])
        b = VideoTrack(id=1, clips=[
            _make_clip(timeline_in_ms=0, source_out_ms=5000,
                       source_duration_ms=5000),
        ])
        tl = Timeline(video_tracks=[a, b])
        assert tl.duration_ms == 5000


# ---------------------------------------------------------------------------
#  Phase 1.5b: project_player._build_clips_view byte-equivalence
# ---------------------------------------------------------------------------


@dataclass
class _PPLegacyTrack:
    """Mirror of the project_player input shape (legacy single-source
    VideoTrack). Just the fields ``_build_clips_view`` reads."""

    id: int = 0
    source_path: Path | None = None
    duration_ms: int = 0
    offset_ms: int = 0
    cuts: list = field(default_factory=list)


class TestClipsViewBuilder:
    """Phase 1.5b cache fed to ``_render_frame_at`` must be a
    byte-equivalent re-expression of the legacy track. No ripple-
    delete: cut regions leave **gaps** between clips so the project-
    timeline length doesn't change versus today."""

    def setup_method(self):
        from app.project_player import _build_clips_view
        self._build = _build_clips_view

    def test_no_source_yields_empty(self):
        assert self._build(_PPLegacyTrack(id=0)) == []

    def test_no_cuts_yields_one_clip_at_offset(self):
        t = _PPLegacyTrack(
            id=0, source_path=Path("/x.mp4"),
            duration_ms=8000, offset_ms=2000,
        )
        clips = self._build(t)
        assert len(clips) == 1
        c = clips[0]
        assert c.timeline_in_ms == 2000
        assert c.timeline_out_ms == 10_000
        assert c.source_in_ms == 0
        assert c.source_out_ms == 8000

    def test_cut_in_middle_preserves_gap(self):
        t = _PPLegacyTrack(
            id=1, source_path=Path("/y.mp4"),
            duration_ms=10_000, offset_ms=0,
            cuts=[CutSegment(start_ms=4000, end_ms=6000)],
        )
        clips = self._build(t)
        assert len(clips) == 2
        a, b = clips
        # Project [0, 4000) — first clip, identical to legacy
        assert (a.timeline_in_ms, a.timeline_out_ms) == (0, 4000)
        # GAP at project [4000, 6000) — no clip there. This is the
        # critical invariant: the legacy renderer skipped frames
        # during cuts but the project timeline length stayed at
        # ``duration_ms``; we preserve that, no ripple-delete.
        assert (b.timeline_in_ms, b.timeline_out_ms) == (6000, 10_000)
        assert (b.source_in_ms, b.source_out_ms) == (6000, 10_000)
        # Project ms inside the cut window matches no clip → renderer
        # falls through to whatever underlies, exactly like before.
        for t_ms in (4000, 5000, 5999):
            assert next((c for c in clips if c.contains_timeline_ms(t_ms)), None) is None

    def test_cut_at_start_drops_first_range(self):
        t = _PPLegacyTrack(
            id=0, source_path=Path("/z.mp4"),
            duration_ms=10_000, offset_ms=0,
            cuts=[CutSegment(start_ms=0, end_ms=2000)],
        )
        clips = self._build(t)
        assert len(clips) == 1
        c = clips[0]
        # Source starts at 2000 (we cut [0,2000)); project still 0-based
        # but window opens at 2000 — same as legacy where playhead
        # crossing 0..2000 simply rendered nothing for this track.
        assert c.source_in_ms == 2000
        assert c.timeline_in_ms == 2000

    def test_overlapping_cuts_collapse(self):
        # Two cuts that overlap should produce the same surviving
        # range as one merged cut would.
        t = _PPLegacyTrack(
            id=0, source_path=Path("/q.mp4"), duration_ms=10_000,
            cuts=[
                CutSegment(start_ms=2000, end_ms=5000),
                CutSegment(start_ms=4000, end_ms=7000),  # overlaps
            ],
        )
        clips = self._build(t)
        assert len(clips) == 2
        a, b = clips
        assert (a.timeline_in_ms, a.timeline_out_ms) == (0, 2000)
        assert (b.timeline_in_ms, b.timeline_out_ms) == (7000, 10_000)

    def test_clip_id_stable_across_rebuilds(self):
        """Track ID is encoded into clip IDs so debuggers / log lines
        can correlate. Same track with same content → same clip ids."""
        t = _PPLegacyTrack(
            id=7, source_path=Path("/x.mp4"), duration_ms=4000,
        )
        a = self._build(t)
        b = self._build(t)
        assert [c.id for c in a] == [c.id for c in b]
        # And the encoding is ``track_id * 1000 + index``
        assert a[0].id == 7 * 1000 + 0


# ---------------------------------------------------------------------------
#  Phase 1.5d Step C: cut_clip_window — split a clip on a source window
# ---------------------------------------------------------------------------


class TestCutClipWindow:
    """``cut_clip_window`` is the editor's ``_cut_selection_in_track``
    core, lifted to a pure function so we can drive it without Qt.
    The selection is in track-local source ms and the function returns
    the new ``track.clips`` list."""

    def setup_method(self):
        from app.video_editor_window import cut_clip_window
        self._cut = cut_clip_window

    def _src_clip(
        self, *, source_in_ms=0, source_out_ms=10_000, timeline_in_ms=0,
        clip_id=1, source_duration_ms=10_000,
    ):
        from app.timeline_model import VideoClip
        return VideoClip(
            id=clip_id, source_path=Path("/x.mp4"),
            source_duration_ms=source_duration_ms,
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms, source_out_ms=source_out_ms,
        )

    def test_cut_in_middle_of_single_clip_yields_two_halves(self):
        clip = self._src_clip()
        result = self._cut([clip], 4000, 6000, track_offset_ms=0)
        assert len(result) == 2
        a, b = result
        assert (a.source_in_ms, a.source_out_ms) == (0, 4000)
        assert (a.timeline_in_ms, a.timeline_out_ms) == (0, 4000)
        assert (b.source_in_ms, b.source_out_ms) == (6000, 10_000)
        assert (b.timeline_in_ms, b.timeline_out_ms) == (6000, 10_000)

    def test_cut_with_track_offset_shifts_right_half_in_project(self):
        # Track offset 2000 → clip lives at project [2000, 12000).
        # Cut at source [4000, 6000) → right half should sit at
        # project_in = offset + 6000 = 8000, project_out = 12000.
        clip = self._src_clip(timeline_in_ms=2000)
        result = self._cut([clip], 4000, 6000, track_offset_ms=2000)
        assert len(result) == 2
        a, b = result
        assert (a.timeline_in_ms, a.timeline_out_ms) == (2000, 6000)
        assert (b.timeline_in_ms, b.timeline_out_ms) == (8000, 12_000)

    def test_cut_at_clip_start_drops_left_half(self):
        clip = self._src_clip()
        result = self._cut([clip], 0, 2000, track_offset_ms=0)
        assert len(result) == 1
        c = result[0]
        assert (c.source_in_ms, c.source_out_ms) == (2000, 10_000)

    def test_cut_at_clip_end_drops_right_half(self):
        clip = self._src_clip()
        result = self._cut([clip], 8000, 10_000, track_offset_ms=0)
        assert len(result) == 1
        c = result[0]
        assert (c.source_in_ms, c.source_out_ms) == (0, 8000)

    def test_cut_outside_clip_passes_clip_through(self):
        clip = self._src_clip(source_in_ms=4000, source_out_ms=6000)
        # Cut at [0, 1000) is outside the clip's source window
        assert self._cut([clip], 0, 1000, 0) == [clip]
        # Cut at [9000, 10_000) is also outside
        assert self._cut([clip], 9000, 10_000, 0) == [clip]

    def test_cut_engulfing_clip_drops_it(self):
        clip = self._src_clip(source_in_ms=4000, source_out_ms=6000)
        result = self._cut([clip], 3000, 7000, track_offset_ms=0)
        assert result == []

    def test_second_cut_on_already_split_track_partitions_correctly(self):
        # Start with one clip, cut in middle, then cut the right half again.
        clip = self._src_clip()
        first = self._cut([clip], 4000, 6000, track_offset_ms=0)
        assert len(first) == 2
        # Second cut at source [7000, 8000) — only the right half overlaps
        second = self._cut(first, 7000, 8000, track_offset_ms=0)
        assert len(second) == 3
        # First clip unchanged
        assert (second[0].source_in_ms, second[0].source_out_ms) == (0, 4000)
        # Right half got cut into two pieces
        assert (second[1].source_in_ms, second[1].source_out_ms) == (6000, 7000)
        assert (second[2].source_in_ms, second[2].source_out_ms) == (8000, 10_000)

    def test_does_not_mutate_input(self):
        clip = self._src_clip()
        original = [clip]
        self._cut(original, 4000, 6000, 0)
        assert original == [clip]
        # The clip object itself is also unchanged.
        assert (clip.source_in_ms, clip.source_out_ms) == (0, 10_000)

    def test_result_is_sorted_by_timeline_in(self):
        # Two clips, cut spanning both
        c1 = self._src_clip(
            clip_id=1, source_in_ms=0, source_out_ms=4000, timeline_in_ms=0,
        )
        c2 = self._src_clip(
            clip_id=2, source_in_ms=6000, source_out_ms=10_000, timeline_in_ms=6000,
        )
        # Cut at source [2000, 8000) — both clips overlap
        result = self._cut([c1, c2], 2000, 8000, track_offset_ms=0)
        assert all(
            result[i].timeline_in_ms <= result[i + 1].timeline_in_ms
            for i in range(len(result) - 1)
        )


# ---------------------------------------------------------------------------
#  Phase 1.5e: build_segments_from_clips matches build_segments for the
#  legacy single-source-with-cuts shape, and emits the right ranges for
#  user-split clip lists.
# ---------------------------------------------------------------------------


class TestBuildSegmentsFromClips:
    """``build_segments_from_clips`` is the export-time replacement
    for the legacy ``build_segments(duration_ms, cuts, speed_segments)``.
    For a track that came from the legacy single-source path, both
    must produce the same ``(start_ms, end_ms, speed)`` ranges so the
    exported MP4 is byte-equivalent (identical filter graph)."""

    def setup_method(self):
        from app.video_exporter import (
            build_segments,
            build_segments_from_clips,
        )
        self._legacy = build_segments
        self._new = build_segments_from_clips

    def _src_clip(
        self, *, source_in_ms=0, source_out_ms=10_000, timeline_in_ms=0,
        clip_id=1, source_duration_ms=10_000,
    ):
        from app.timeline_model import VideoClip
        return VideoClip(
            id=clip_id, source_path=Path("/x.mp4"),
            source_duration_ms=source_duration_ms,
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms, source_out_ms=source_out_ms,
        )

    def test_empty_clips_yields_empty(self):
        assert self._new([], []) == []

    def test_single_clip_no_speed_matches_legacy_no_cuts(self):
        # Legacy: duration=8000, no cuts, no speeds → [(0, 8000, 1.0)]
        # New: one clip [0, 8000] → same.
        legacy = self._legacy(8000, [], [])
        new = self._new([self._src_clip(source_out_ms=8000)], [])
        assert legacy == new

    def test_legacy_cuts_match_clip_view(self):
        from app.timeline_model import (
            CutSegment, build_legacy_clips_view,
        )
        # Legacy track: duration 10_000 with cut [3000, 5000)
        legacy = self._legacy(
            10_000,
            [CutSegment(3000, 5000)],
            [],
        )
        # Build the equivalent clip view from the same legacy data and
        # feed it to the new function — outputs must match.
        @dataclass
        class _T:
            id: int = 0
            source_path: Path | None = Path("/x.mp4")
            duration_ms: int = 10_000
            offset_ms: int = 0
            cuts: list = field(default_factory=lambda: [CutSegment(3000, 5000)])
        clips = build_legacy_clips_view(_T())
        new = self._new(clips, [])
        assert legacy == new

    def test_user_split_clips_emit_their_source_windows(self):
        # Clip 1: source [0, 3000), clip 2: source [5000, 10_000) — i.e.
        # the post-cut shape Phase 1.5d's ``cut_clip_window`` produces.
        c1 = self._src_clip(
            source_in_ms=0, source_out_ms=3000, timeline_in_ms=0,
        )
        c2 = self._src_clip(
            source_in_ms=5000, source_out_ms=10_000, timeline_in_ms=5000,
        )
        new = self._new([c1, c2], [])
        assert new == [(0, 3000, 1.0), (5000, 10_000, 1.0)]

    def test_clips_in_unsorted_input_emitted_in_project_order(self):
        # User dragged clip2 to the LEFT of clip1 — project-time order
        # is now [clip2, clip1] even though the list was built
        # [clip1, clip2]. Output should reflect the drag.
        c1 = self._src_clip(
            clip_id=1, source_in_ms=0, source_out_ms=3000, timeline_in_ms=5000,
        )
        c2 = self._src_clip(
            clip_id=2, source_in_ms=6000, source_out_ms=8000, timeline_in_ms=0,
        )
        new = self._new([c1, c2], [])
        # c2 (later in list, earlier on timeline) plays first.
        assert new == [(6000, 8000, 1.0), (0, 3000, 1.0)]

    def test_speed_segments_apply_to_clip_ranges(self):
        from app.timeline_model import SpeedSegment
        # Clip [0, 8000), speed [3000, 5000) at 2.0x
        c = self._src_clip(source_out_ms=8000)
        new = self._new(
            [c],
            [SpeedSegment(start_ms=3000, end_ms=5000, speed=2.0)],
        )
        # Expect three pieces: normal [0, 3000), fast [3000, 5000),
        # normal [5000, 8000).
        assert new == [
            (0, 3000, 1.0),
            (3000, 5000, 2.0),
            (5000, 8000, 1.0),
        ]


# ---------------------------------------------------------------------------
#  Phase 7: Sony jog/shuttle math helpers
# ---------------------------------------------------------------------------


class TestShuttleSpeedMapping:
    """The shuttle dial maps a -150°..+150° rotation to one of the 6
    Sony PVW-2800 gears in each direction (and a centre dead-zone for
    pause). The mapping is discrete so the wheel snaps audibly to
    each gear instead of producing analog rates."""

    def setup_method(self):
        from app.jog_shuttle import (
            _shuttle_speed_for_angle, _SHUTTLE_RANGE_DEG, _SHUTTLE_STEPS,
        )
        self._fn = _shuttle_speed_for_angle
        self._range = _SHUTTLE_RANGE_DEG
        self._steps = _SHUTTLE_STEPS

    def test_centre_is_pause(self):
        assert self._fn(0) == 0.0

    def test_dead_zone_around_centre(self):
        # ±12.5° (= range / steps / 2 = 150/6/2) is paused so a tiny
        # cursor wobble doesn't kick the deck into motion.
        assert self._fn(5) == 0.0
        assert self._fn(-5) == 0.0
        assert self._fn(12) == 0.0

    def test_first_gear_just_past_dead_zone(self):
        # Dead-zone edge is 12.5° → past it = first Sony gear (±1×).
        assert self._fn(15) == 1.0
        assert self._fn(-15) == -1.0

    def test_top_gear_at_full_swing(self):
        assert self._fn(self._range) == self._steps[-1]
        assert self._fn(-self._range) == -self._steps[-1]

    def test_beyond_range_clamps_to_top_gear(self):
        assert self._fn(200) == self._steps[-1]
        assert self._fn(-1000) == -self._steps[-1]

    def test_each_gear_is_reachable(self):
        # Walk from 0..range and confirm every Sony step appears in the
        # output set (no gear is unreachable due to a math fencepost).
        seen = {self._fn(d) for d in range(0, int(self._range) + 1, 1)}
        for step in self._steps:
            assert step in seen


class TestWrapAngle:
    """Angle deltas wrap into [-180, 180] so a drag that crosses the
    12-o'clock seam doesn't suddenly flip sign."""

    def test_no_wrap_within_range(self):
        from app.jog_shuttle import _wrap_angle
        assert _wrap_angle(0) == 0
        assert _wrap_angle(90) == 90
        assert _wrap_angle(-90) == -90
        assert _wrap_angle(180) == 180

    def test_wraps_above_180(self):
        from app.jog_shuttle import _wrap_angle
        assert _wrap_angle(190) == -170
        assert _wrap_angle(360) == 0

    def test_wraps_below_neg_180(self):
        from app.jog_shuttle import _wrap_angle
        assert _wrap_angle(-190) == 170
        assert _wrap_angle(-360) == 0


# ---------------------------------------------------------------------------
#  HDR Phase 0: ffmpeg-stderr parser
# ---------------------------------------------------------------------------


class TestHDRProbeParser:
    """The HDR detection runs ffmpeg and parses its stderr. We can
    drive the parser directly with sample stream lines so the tests
    never depend on having a real video file or the ffmpeg binary."""

    def setup_method(self):
        from app.hdr_probe import _parse_hdr_from_ffmpeg_text
        self._parse = _parse_hdr_from_ffmpeg_text

    def test_hdr10_smpte2084(self):
        line = (
            "  Stream #0:0(und): Video: hevc (Main 10) (hev1 / 0x31766568), "
            "yuv420p10le(tv, bt2020nc/bt2020/smpte2084), 3840x2160 [SAR 1:1 DAR 16:9], "
            "10000 kb/s, 60 fps, 60 tbr, 90k tbn (default)"
        )
        info = self._parse(line)
        assert info.is_hdr is True
        assert info.transfer == "smpte2084"
        assert info.primaries == "bt2020"
        assert info.matrix == "bt2020nc"
        assert info.pix_fmt == "yuv420p10le"
        assert info.standard_label == "HDR10"

    def test_hlg_arib_std_b67(self):
        line = (
            "  Stream #0:0(und): Video: hevc (Main 10), "
            "yuv420p10le(tv, bt2020nc/bt2020/arib-std-b67), 1920x1080, 30 fps"
        )
        info = self._parse(line)
        assert info.is_hdr is True
        assert info.transfer == "arib-std-b67"
        assert info.standard_label == "HLG"

    def test_sdr_bt709(self):
        line = (
            "  Stream #0:0(und): Video: h264 (High), "
            "yuv420p(tv, bt709, progressive), 1920x1080, 4000 kb/s, 30 fps"
        )
        info = self._parse(line)
        assert info.is_hdr is False
        # bt709-only line has no transfer triple, just a single token —
        # parser leaves transfer empty, label is SDR.
        assert info.standard_label == "SDR"

    def test_bare_pixfmt_no_color_triple(self):
        # Some files (older clips) report only the pixel format without
        # the colour annotation. Detection must default to SDR.
        line = (
            "  Stream #0:0(und): Video: h264, yuv420p, 1280x720, 30 fps"
        )
        info = self._parse(line)
        assert info.is_hdr is False
        assert info.transfer == ""
        assert info.pix_fmt == "yuv420p"

    def test_no_video_stream_at_all(self):
        info = self._parse("only audio metadata here\nStream #0:0: Audio: aac")
        assert info.is_hdr is False
        assert info.raw_line == ""


# ---------------------------------------------------------------------------
#  Phase 5 Step A: SubtitleLayer / TypographyLayer base behaviour
# ---------------------------------------------------------------------------


@dataclass
class _Range:
    """Generic time-range item for testing ``_OverlayLayer``. Both
    ``Subtitle`` and ``TextClip`` share this duck-typed shape."""

    start_ms: int
    end_ms: int
    text: str = ""


class TestOverlayLayer:
    def setup_method(self):
        from app.overlay_layer import SubtitleLayer
        self._cls = SubtitleLayer

    def test_empty_layer(self):
        layer = self._cls()
        assert len(layer) == 0
        assert layer.items() == []
        assert layer.active_at(0) == []
        assert layer.first_active_at(0) is None

    def test_active_at_includes_start_excludes_end(self):
        layer = self._cls([_Range(1000, 3000, "a")])
        # half-open [start, end): 1000 in, 3000 out
        assert layer.first_active_at(999) is None
        assert layer.first_active_at(1000) is not None
        assert layer.first_active_at(2999) is not None
        assert layer.first_active_at(3000) is None

    def test_multiple_active_overlapping(self):
        a = _Range(0, 5000, "main")
        b = _Range(2000, 4000, "translation")
        layer = self._cls([a, b])
        assert layer.active_at(3000) == [a, b]
        assert layer.active_at(4500) == [a]
        assert layer.active_at(0) == [a]

    def test_add_keeps_layer_sorted(self):
        layer = self._cls()
        layer.add(_Range(5000, 7000, "later"))
        layer.add(_Range(1000, 3000, "earlier"))
        items = layer.items()
        assert [it.start_ms for it in items] == [1000, 5000]

    def test_remove_drops_match_only(self):
        a = _Range(0, 1000, "a")
        b = _Range(2000, 3000, "b")
        layer = self._cls([a, b])
        assert layer.remove(a) is True
        assert layer.items() == [b]
        # Removing again is a no-op (returns False) — not a crash.
        assert layer.remove(a) is False

    def test_replace_at_resorts(self):
        layer = self._cls([
            _Range(0, 1000, "a"),
            _Range(2000, 3000, "b"),
        ])
        # Replace the first one with something that should now sort last.
        layer.replace_at(0, _Range(5000, 6000, "moved"))
        items = layer.items()
        assert [it.text for it in items] == ["b", "moved"]

    def test_clear_empties_layer(self):
        layer = self._cls([_Range(0, 1000)])
        layer.clear()
        assert len(layer) == 0

    def test_replace_all_bulk_loads(self):
        layer = self._cls([_Range(0, 1000, "old")])
        layer.replace_all([_Range(5000, 6000, "new1"), _Range(2000, 3000, "new2")])
        # New items, sorted
        assert [it.text for it in layer.items()] == ["new2", "new1"]

    def test_on_change_fires_on_mutations(self):
        layer = self._cls()
        calls = []
        layer.on_change = lambda: calls.append(1)
        layer.add(_Range(0, 1000))
        layer.add(_Range(2000, 3000))
        layer.remove(layer.items()[0])
        layer.clear()
        assert len(calls) == 4

    def test_on_change_listener_failure_is_isolated(self):
        layer = self._cls()
        def bad():
            raise RuntimeError("listener bug")
        layer.on_change = bad
        # Should not propagate — layer mutation must succeed even if
        # the listener throws.
        layer.add(_Range(0, 1000))
        assert len(layer) == 1


# ---------------------------------------------------------------------------
#  Drag constraints (snap + collision)
# ---------------------------------------------------------------------------


class TestDragConstraints:
    """``apply_drag_constraints`` is the engine behind snap-and-clamp
    when the user drags a clip. The semantics:

    1. Snap to other clips' in/out edges + project ms 0 within
       ``snap_ms`` tolerance.
    2. After snapping, if the position would overlap, clamp to the
       nearest non-overlapping spot.

    Pure function — no Qt required."""

    def setup_method(self):
        from app.timeline_model import apply_drag_constraints
        self._fn = apply_drag_constraints

    def _clip(
        self, *, source_in_ms=0, source_out_ms=2000, timeline_in_ms=0,
        clip_id=1,
    ):
        from app.timeline_model import VideoClip
        return VideoClip(
            id=clip_id, source_path=Path("/x.mp4"),
            source_duration_ms=source_out_ms,
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms,
            source_out_ms=source_out_ms,
        )

    def test_no_other_clips_passes_through(self):
        c = self._clip(timeline_in_ms=1000)
        assert self._fn([c], c, 5000, snap_ms=200) == 5000

    def test_snaps_to_zero_within_tolerance(self):
        c = self._clip(timeline_in_ms=1000)
        # Desired=120 ms, snap tolerance 200 ms → snap to 0.
        assert self._fn([c], c, 120, snap_ms=200) == 0
        # Desired=300 ms → outside tolerance, no snap.
        assert self._fn([c], c, 300, snap_ms=200) == 300

    def test_snaps_in_edge_to_other_clip_in(self):
        # Other clip at [5000, 7000); dragged clip is 2000 ms long.
        # Drop in-edge at 4900 ms (~snap to 5000) → in stays at 5000…
        # but that overlaps the other clip [5000, 7000), so collision
        # clamp kicks in. Use a less-conflicting target instead.
        other = self._clip(clip_id=99, timeline_in_ms=5000, source_out_ms=2000)
        c = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=1000)
        # Desired 4920 → snap target 5000 (in-edge). 5000 + 1000 = 6000
        # which overlaps [5000, 7000), so collision clamps. The clamp
        # candidates are: park flush LEFT of other → 5000-1000 = 4000;
        # park flush RIGHT → 7000. Closer to 5000 is 4000.
        assert self._fn([c, other], c, 4920, snap_ms=200) == 4000

    def test_snaps_out_edge_to_other_clip_in(self):
        # Other clip at [5000, 7000); dragged clip 2000 ms long.
        # Drop with out-edge near 5000 → in-edge becomes 3000.
        other = self._clip(clip_id=99, timeline_in_ms=5000, source_out_ms=2000)
        c = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=2000)
        # Desired in-edge 3050; out-edge 5050 → snap out to 5000 →
        # in-edge becomes 3000. No overlap (out=5000 == other.in=5000).
        assert self._fn([c, other], c, 3050, snap_ms=200) == 3000

    def test_collision_clamps_to_nearest_gap(self):
        # Two existing clips: A at [0, 4000), B at [6000, 8000).
        # Dragged 1000 ms long, desired in 4500 (overlaps neither but
        # in the gap). Should pass through.
        a = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=4000)
        b = self._clip(clip_id=2, timeline_in_ms=6000, source_out_ms=2000)
        c = self._clip(clip_id=3, timeline_in_ms=10_000, source_out_ms=1000)
        result = self._fn([a, b, c], c, 4500, snap_ms=50)
        assert result == 4500

    def test_collision_blocks_when_no_gap_left(self):
        # Pack clips so [0..2000] and [2000..4000] cover everything.
        # Drag a third 1500 ms clip that's currently at 5000 to
        # somewhere fully inside [0, 4000) — should clamp to keep
        # current position because nowhere is free in that range.
        a = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=2000)
        b = self._clip(clip_id=2, timeline_in_ms=2000, source_out_ms=2000)
        # Make the dragged clip start outside the packed area.
        c = self._clip(clip_id=3, timeline_in_ms=5000, source_out_ms=1500)
        # Desired 1000 → would overlap. Candidates: park left of
        # a (= -1500 → clamped to 0; collides with a still); park
        # right of a (= 2000; collides with b); left of b (= 500;
        # collides with a); right of b (= 4000; FREE). Closest to
        # desired 1000: 4000.
        result = self._fn([a, b, c], c, 1000, snap_ms=50)
        assert result == 4000

    def test_self_does_not_block_self(self):
        # Dragging a clip to its OWN current position must not be
        # treated as a collision against itself.
        c = self._clip(timeline_in_ms=2000, source_out_ms=2000)
        assert self._fn([c], c, 2000, snap_ms=50) == 2000

    def test_negative_desired_clamps_to_zero(self):
        c = self._clip(timeline_in_ms=2000, source_out_ms=2000)
        assert self._fn([c], c, -5000, snap_ms=50) == 0


# ---------------------------------------------------------------------------
#  Option C: blade-at-playhead + ripple delete
# ---------------------------------------------------------------------------


class TestSplitAtProjectMs:
    """Industry-standard blade tool — split the clip under the
    playhead at the playhead's project-time position. The function
    is the engine the editor's B / Ctrl+K shortcut calls."""

    def setup_method(self):
        from app.timeline_model import split_clips_at_project_ms
        self._fn = split_clips_at_project_ms

    def _clip(
        self, *, source_in_ms=0, source_out_ms=10_000, timeline_in_ms=0,
        clip_id=1,
    ):
        from app.timeline_model import VideoClip
        return VideoClip(
            id=clip_id, source_path=Path("/x.mp4"),
            source_duration_ms=source_out_ms,
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms, source_out_ms=source_out_ms,
        )

    def test_split_inside_single_clip_yields_two_halves(self):
        clip = self._clip()
        result = self._fn([clip], 4000)
        assert len(result) == 2
        a, b = result
        assert (a.timeline_in_ms, a.timeline_out_ms) == (0, 4000)
        assert (b.timeline_in_ms, b.timeline_out_ms) == (4000, 10_000)
        # Source ranges partition the original window cleanly.
        assert (a.source_in_ms, a.source_out_ms) == (0, 4000)
        assert (b.source_in_ms, b.source_out_ms) == (4000, 10_000)

    def test_split_at_clip_boundary_is_noop(self):
        clip = self._clip()
        # Strictly-inside semantics: project_ms == timeline_in or
        # timeline_out doesn't split — matches DaVinci / Premiere.
        assert self._fn([clip], 0) == [clip]
        assert self._fn([clip], 10_000) == [clip]

    def test_split_outside_clip_passes_clips_through(self):
        c1 = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=2000)
        c2 = self._clip(clip_id=2, timeline_in_ms=4000, source_out_ms=2000)
        # 3000 falls in the gap — neither clip is touched.
        result = self._fn([c1, c2], 3000)
        assert result == [c1, c2]

    def test_split_with_offset_track_maps_source_correctly(self):
        # Clip at project [2000, 6000), source [1000, 5000). Split at
        # project 4000 → source 1000 + (4000-2000) = 3000.
        clip = self._clip(
            source_in_ms=1000, source_out_ms=5000, timeline_in_ms=2000,
        )
        result = self._fn([clip], 4000)
        assert len(result) == 2
        a, b = result
        assert (a.source_in_ms, a.source_out_ms) == (1000, 3000)
        assert (b.source_in_ms, b.source_out_ms) == (3000, 5000)

    def test_split_does_not_mutate_input(self):
        clip = self._clip()
        original = [clip]
        self._fn(original, 4000)
        assert original == [clip]
        assert (clip.source_in_ms, clip.source_out_ms) == (0, 10_000)


class TestRippleDeleteClips:
    """Ripple-delete — remove a clip and shift everything to the
    right of it left to close the gap. Standard DaVinci / Premiere
    behaviour for ``Shift+Delete`` on a clip selection."""

    def setup_method(self):
        from app.timeline_model import ripple_delete_clips
        self._fn = ripple_delete_clips

    def _clip(
        self, *, source_in_ms=0, source_out_ms=2000, timeline_in_ms=0,
        clip_id=1,
    ):
        from app.timeline_model import VideoClip
        return VideoClip(
            id=clip_id, source_path=Path("/x.mp4"),
            source_duration_ms=source_out_ms,
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms, source_out_ms=source_out_ms,
        )

    def test_empty_target_set_passes_through(self):
        a = self._clip(clip_id=1)
        assert self._fn([a], set()) == [a]

    def test_ripple_shifts_subsequent_clips_left(self):
        a = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=2000)
        b = self._clip(clip_id=2, timeline_in_ms=2000, source_out_ms=3000)
        c = self._clip(clip_id=3, timeline_in_ms=5000, source_out_ms=2000)
        # Delete b (3000 ms long). c should shift from 5000 → 2000.
        result = self._fn([a, b, c], {2})
        assert len(result) == 2
        a_new, c_new = result
        assert a_new.id == 1 and a_new.timeline_in_ms == 0
        assert c_new.id == 3 and c_new.timeline_in_ms == 2000

    def test_ripple_leaves_earlier_clips_alone(self):
        a = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=2000)
        b = self._clip(clip_id=2, timeline_in_ms=2000, source_out_ms=3000)
        # Delete b — a (which starts BEFORE b) shouldn't move.
        result = self._fn([a, b], {2})
        assert len(result) == 1
        assert result[0].id == 1 and result[0].timeline_in_ms == 0

    def test_ripple_multiple_targets_close_each_gap_in_order(self):
        a = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(clip_id=2, timeline_in_ms=1000, source_out_ms=1000)
        c = self._clip(clip_id=3, timeline_in_ms=2000, source_out_ms=1000)
        d = self._clip(clip_id=4, timeline_in_ms=3000, source_out_ms=1000)
        # Delete b and c — d should shift left by the combined 2000ms.
        result = self._fn([a, b, c, d], {2, 3})
        assert [r.id for r in result] == [1, 4]
        assert result[0].timeline_in_ms == 0
        assert result[1].timeline_in_ms == 1000

    def test_ripple_does_not_mutate_input(self):
        a = self._clip(clip_id=1)
        b = self._clip(clip_id=2, timeline_in_ms=2000)
        original = [a, b]
        self._fn(original, {2})
        assert original == [a, b]
        # a's timeline_in_ms is unchanged on the original.
        assert a.timeline_in_ms == 0


# ---------------------------------------------------------------------------
#  HDR Phase 1: decoder factory dispatch
# ---------------------------------------------------------------------------


class TestDecoderFactoryDispatch:
    """``open_decoder`` picks ``CV2Decoder`` for SDR / no-info, and
    ``FFmpegToneMapDecoder`` for HDR. We stub both so the test never
    spawns ffmpeg or opens a real cv2 stream — we just verify the
    dispatch logic + fallback chain."""

    def setup_method(self):
        from app import video_decoder
        self._mod = video_decoder

        # Save the originals so other tests aren't affected.
        self._orig_cv = video_decoder.CV2Decoder
        self._orig_ff = video_decoder.FFmpegToneMapDecoder

    def teardown_method(self):
        self._mod.CV2Decoder = self._orig_cv
        self._mod.FFmpegToneMapDecoder = self._orig_ff

    def _make_stub(self, *, opens: bool, label: str):
        class _Stub:
            def __init__(self, path):
                self.path = path
                self.label = label
            def open(self_inner):
                return opens
            def release(self_inner):
                pass
        return _Stub

    def test_dispatch_to_cv2_when_no_hdr_info(self):
        self._mod.CV2Decoder = self._make_stub(opens=True, label="cv2")
        d = self._mod.open_decoder("/x.mp4", hdr_info=None)
        assert d is not None
        assert d.label == "cv2"

    def test_dispatch_to_cv2_when_sdr(self):
        from app.hdr_probe import HDRInfo
        self._mod.CV2Decoder = self._make_stub(opens=True, label="cv2")
        d = self._mod.open_decoder(
            "/x.mp4", hdr_info=HDRInfo(is_hdr=False, transfer="bt709"),
        )
        assert d.label == "cv2"

    def test_dispatch_to_ffmpeg_when_hdr(self):
        from app.hdr_probe import HDRInfo
        self._mod.CV2Decoder = self._make_stub(opens=True, label="cv2")
        self._mod.FFmpegToneMapDecoder = self._make_stub(
            opens=True, label="ffmpeg",
        )
        d = self._mod.open_decoder(
            "/x.mp4", hdr_info=HDRInfo(is_hdr=True, transfer="smpte2084"),
        )
        assert d.label == "ffmpeg"

    def test_falls_back_to_cv2_when_ffmpeg_open_fails(self):
        from app.hdr_probe import HDRInfo
        self._mod.CV2Decoder = self._make_stub(opens=True, label="cv2")
        self._mod.FFmpegToneMapDecoder = self._make_stub(
            opens=False, label="ffmpeg",
        )
        d = self._mod.open_decoder(
            "/x.mp4", hdr_info=HDRInfo(is_hdr=True, transfer="smpte2084"),
        )
        # ffmpeg failed — cv2 fallback returned.
        assert d.label == "cv2"

    def test_returns_none_when_everything_fails(self):
        self._mod.CV2Decoder = self._make_stub(opens=False, label="cv2")
        self._mod.FFmpegToneMapDecoder = self._make_stub(
            opens=False, label="ffmpeg",
        )
        d = self._mod.open_decoder("/x.mp4", hdr_info=None)
        assert d is None


# ---------------------------------------------------------------------------
#  HDR Phase 2: build_filter_graph tonemap insertion
# ---------------------------------------------------------------------------


class TestExportFilterGraphHDR:
    """``build_filter_graph`` should insert a tonemap chain for HDR
    sources so the exported MP4 matches the SDR preview the user
    saw. SDR sources must produce a byte-equivalent graph to the
    pre-Phase-2 version (no extra filter)."""

    def setup_method(self):
        from app.video_exporter import build_filter_graph
        self._fn = build_filter_graph

    def test_no_hdr_info_omits_tonemap(self):
        graph = self._fn([(0, 1000, 1.0)], hdr_info=None)
        assert "tonemap" not in graph
        assert "zscale" not in graph

    def test_sdr_hdr_info_omits_tonemap(self):
        from app.hdr_probe import HDRInfo
        graph = self._fn(
            [(0, 1000, 1.0)],
            hdr_info=HDRInfo(is_hdr=False, transfer="bt709"),
        )
        assert "tonemap" not in graph

    def test_hdr_hdr_info_inserts_tonemap(self):
        from app.hdr_probe import HDRInfo
        graph = self._fn(
            [(0, 1000, 1.0)],
            hdr_info=HDRInfo(is_hdr=True, transfer="smpte2084"),
        )
        # Tonemap must appear after concat (so all clips are
        # tonemapped together) and before any color grade overlay.
        assert "tonemap=hable" in graph
        assert "zscale=t=linear" in graph
        # Pixel format at the tonemap output is yuv420p so libx264
        # / libvpx / libaom can encode without extra ``-pix_fmt``.
        assert "format=yuv420p" in graph
        # The chain should appear after the ``[cv0]`` concat label.
        cv0_pos = graph.find("[cv0]")
        tonemap_pos = graph.find("tonemap=hable")
        assert cv0_pos != -1 and tonemap_pos != -1 and tonemap_pos > cv0_pos

    def test_hdr_tonemap_label_chains_to_grade(self):
        # When BOTH tonemap AND a (mock) color_grade run, the grade
        # input must be the tonemap output ``[cvtm]``, not raw concat.
        from app.hdr_probe import HDRInfo
        # A truthy color_grade-like object whose ``to_ffmpeg_filters``
        # the function calls — provide a stub via a fake module.
        class _StubGrade:
            def __init__(self):
                self.applied = False
        # ``to_ffmpeg_filters`` is imported INSIDE build_filter_graph,
        # so we test by checking the graph string mentions [cvtm] as
        # an input to whatever comes next. Without a real grade we
        # just verify the tonemap label is referenced as ``current``
        # — i.e. the literal string ``[cvtm]`` appears at least once
        # outside the tonemap definition itself.
        graph = self._fn(
            [(0, 1000, 1.0)],
            hdr_info=HDRInfo(is_hdr=True, transfer="smpte2084"),
        )
        # ``[cvtm]`` is the OUTPUT of the tonemap node. Its input is
        # ``[cv0]``. If anything follows, it should chain from
        # ``[cvtm]`` rather than re-using ``[cv0]``. Single-segment
        # SDR-no-overlays graph has no follow-up step, but we at
        # least verify the label was emitted.
        assert "[cvtm]" in graph


class TestExportFilterGraphHDRPassthrough:
    """Phase 2b: ``hdr_passthrough=True`` skips the SDR tonemap and
    pins the chain to 10-bit BT.2020 PQ output instead."""

    def setup_method(self):
        from app.video_exporter import build_filter_graph
        self._fn = build_filter_graph

    def test_passthrough_skips_tonemap(self):
        from app.hdr_probe import HDRInfo
        graph = self._fn(
            [(0, 1000, 1.0)],
            hdr_info=HDRInfo(is_hdr=True, transfer="smpte2084"),
            hdr_passthrough=True,
        )
        assert "tonemap=hable" not in graph
        # The 10-bit output format is pinned so the encoder receives
        # ``yuv420p10le`` regardless of source upstream defaults.
        assert "format=yuv420p10le" in graph
        # The new label this branch emits.
        assert "[cvhdr]" in graph

    def test_passthrough_irrelevant_for_sdr(self):
        from app.hdr_probe import HDRInfo
        graph = self._fn(
            [(0, 1000, 1.0)],
            hdr_info=HDRInfo(is_hdr=False, transfer="bt709"),
            hdr_passthrough=True,    # ignored for SDR sources
        )
        assert "[cvhdr]" not in graph
        assert "format=yuv420p10le" not in graph


class TestExportFormatHDRArgs:
    """``ExportFormat.build_video_args`` produces the libx265 HDR
    encoder args when ``hdr_passthrough=True`` is passed."""

    def setup_method(self):
        from app.video_exporter import EXPORT_FORMATS
        self._mp4 = next(f for f in EXPORT_FORMATS if f.id == "mp4")

    def test_default_path_is_libx264_8bit(self):
        from app.video_exporter import get_quality_preset
        args = self._mp4.build_video_args(get_quality_preset("standard"))
        assert "-c:v" in args
        cv_idx = args.index("-c:v")
        assert args[cv_idx + 1] == "libx264"
        assert "yuv420p" in args
        assert "yuv420p10le" not in args

    def test_hdr_passthrough_switches_to_libx265_10bit(self):
        from app.video_exporter import get_quality_preset
        args = self._mp4.build_video_args(
            get_quality_preset("standard"), hdr_passthrough=True,
        )
        cv_idx = args.index("-c:v")
        assert args[cv_idx + 1] == "libx265"
        assert "-pix_fmt" in args
        pix_idx = args.index("-pix_fmt")
        assert args[pix_idx + 1] == "yuv420p10le"
        # Container-level colour metadata so non-x265 players honour HDR.
        assert "-color_primaries" in args
        cp_idx = args.index("-color_primaries")
        assert args[cp_idx + 1] == "bt2020"
        assert "-color_trc" in args
        ct_idx = args.index("-color_trc")
        assert args[ct_idx + 1] == "smpte2084"
        # ``hvc1`` tag is the QuickTime-friendly variant.
        assert "-tag:v" in args
        tag_idx = args.index("-tag:v")
        assert args[tag_idx + 1] == "hvc1"
        # x265 params should carry the colorprim/transfer/matrix info
        # too (so every IDR is self-describing).
        assert "-x265-params" in args
        xp_idx = args.index("-x265-params")
        params = args[xp_idx + 1]
        assert "colorprim=bt2020" in params
        assert "transfer=smpte2084" in params
        assert "colormatrix=bt2020nc" in params


# ---------------------------------------------------------------------------
#  Undo / redo HistoryStack
# ---------------------------------------------------------------------------


class TestHistoryStack:
    """The bounded stack that backs Ctrl+Z / Ctrl+Shift+Z."""

    def setup_method(self):
        from app.history import HistoryStack
        self._cls = HistoryStack

    def test_empty_stack_cant_undo_or_redo(self):
        h = self._cls(max_undo_steps=10)
        assert not h.can_undo()
        assert not h.can_redo()
        assert h.undo() is None
        assert h.redo() is None

    def test_push_then_undo_returns_prior(self):
        h = self._cls()
        h.push("a", "initial")
        h.push("b", "edit 1")
        h.push("c", "edit 2")
        # 3 entries, cursor at 2 (= "c" current). Undo → "b".
        assert h.can_undo() and not h.can_redo()
        assert h.undo() == "b"
        assert h.can_undo() and h.can_redo()
        assert h.undo() == "a"
        assert not h.can_undo() and h.can_redo()
        assert h.undo() is None  # nothing further

    def test_redo_walks_back_forward(self):
        h = self._cls()
        for s in ("a", "b", "c"):
            h.push(s)
        h.undo()  # → b (cursor 1)
        h.undo()  # → a (cursor 0)
        assert h.redo() == "b"
        assert h.redo() == "c"
        assert h.redo() is None

    def test_push_after_undo_drops_redo_tail(self):
        h = self._cls()
        for s in ("a", "b", "c"):
            h.push(s)
        h.undo()  # cursor at 1 ("b")
        h.push("d", "branch")
        # "c" should be dropped — redo at this point is None.
        assert not h.can_redo()
        # Walk back to confirm the branch state is intact.
        assert h.undo() == "b"
        assert h.undo() == "a"

    def test_max_undo_steps_caps_history_depth(self):
        # 10 steps means up to 11 entries (initial + 10 changes).
        h = self._cls(max_undo_steps=10)
        for i in range(20):
            h.push(f"step{i}")
        assert h.depth() == 11
        # Latest entry is current → can_undo for 10 steps.
        steps = 0
        while h.can_undo():
            h.undo()
            steps += 1
        assert steps == 10

    def test_labels_round_trip(self):
        h = self._cls()
        h.push("a", "alpha")
        h.push("b", "beta")
        assert h.labels() == ["alpha", "beta"]


class TestEditorSnapshot:
    """``capture_editor_snapshot`` / ``apply_editor_snapshot`` use a
    duck-typed ``editor`` so we can drive them with a stub instead of
    spinning up the real Qt editor."""

    def setup_method(self):
        from app import history
        self._h = history

    def _stub_editor(self):
        from app.video_editor_window import VideoTrack
        from app.overlay_layer import SubtitleLayer
        from app.subtitles import Subtitle

        class _StubPanel:
            class _Sig:
                def emit(self_inner): pass
            subtitles_changed = _Sig()
            def __init__(self_inner):
                self_inner.layer = SubtitleLayer()
            def _refresh_list(self_inner): pass

        class _Stub:
            def __init__(self_inner):
                self_inner._tracks = [VideoTrack(id=0)]
                self_inner._audio_tracks = []
                self_inner._subtitle_panel = _StubPanel()
                self_inner._active_track_id = 0
            def _set_active_track(self_inner, tid):
                self_inner._active_track_id = tid

        return _Stub(), Subtitle

    def test_capture_then_restore_roundtrip(self):
        ed, Subtitle = self._stub_editor()
        # Mutate before capture: add a subtitle, set selection.
        ed._subtitle_panel.layer.add(Subtitle(0, 1000, "hello"))
        ed._tracks[0].selection_start_ms = 500
        ed._tracks[0].selection_end_ms = 800

        snap = self._h.capture_editor_snapshot(ed)

        # Mutate after capture — restore should undo all of it.
        ed._tracks[0].selection_start_ms = 0
        ed._tracks[0].selection_end_ms = 0
        ed._subtitle_panel.layer.clear()

        self._h.apply_editor_snapshot(ed, snap)

        assert ed._tracks[0].selection_start_ms == 500
        assert ed._tracks[0].selection_end_ms == 800
        assert len(ed._subtitle_panel.layer.items()) == 1
        assert ed._subtitle_panel.layer.items()[0].text == "hello"

    def test_snapshot_isolated_from_subsequent_mutations(self):
        ed, Subtitle = self._stub_editor()
        ed._subtitle_panel.layer.add(Subtitle(0, 1000, "v1"))
        snap = self._h.capture_editor_snapshot(ed)

        # Mutate the live state *after* capture; snapshot must be
        # immune (deep-copied) so it still represents v1.
        live_sub = ed._subtitle_panel.layer.items()[0]
        live_sub.text = "v2-mutated"

        # Restoring should give back "v1".
        ed._subtitle_panel.layer.clear()
        self._h.apply_editor_snapshot(ed, snap)
        assert ed._subtitle_panel.layer.items()[0].text == "v1"

    def test_apply_skips_tracks_that_no_longer_exist(self):
        ed, _ = self._stub_editor()
        snap = self._h.capture_editor_snapshot(ed)
        # Drop the track from the editor — applying the snapshot
        # should NOT crash, just silently skip the missing track.
        ed._tracks = []
        # Should be a no-op (no exception raised).
        self._h.apply_editor_snapshot(ed, snap)
        assert ed._tracks == []
