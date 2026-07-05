"""Deterministic timeline interaction fuzzer.

This exercises the edit invariants behind select/blade/ripple/roll/linked move,
nested placeholders, actor-lane extents, and undo snapshots without opening Qt.
It is not a renderer test; it catches model-level edge cases before UI gestures
reach export/preview.
"""
from __future__ import annotations

import argparse
import copy
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FuzzClip:
    id: int
    start_ms: int
    end_ms: int
    source_in_ms: int = 0
    source_out_ms: int = 0
    linked_audio_id: int | None = None
    nested_sequence_id: str = ""

    def __post_init__(self) -> None:
        if self.source_out_ms <= self.source_in_ms:
            self.source_out_ms = self.source_in_ms + max(1, self.end_ms - self.start_ms)

    @property
    def duration_ms(self) -> int:
        return int(self.end_ms - self.start_ms)


@dataclass
class FuzzTrack:
    id: int
    clips: list[FuzzClip] = field(default_factory=list)


@dataclass
class FuzzProject:
    video_tracks: list[FuzzTrack] = field(default_factory=list)
    audio_tracks: list[FuzzTrack] = field(default_factory=list)
    spine_actor_tracks: list[FuzzTrack] = field(default_factory=list)
    live2d_actor_tracks: list[FuzzTrack] = field(default_factory=list)
    next_clip_id: int = 1


def _new_clip(project: FuzzProject, start: int, duration: int, *, linked_audio_id=None, nested="") -> FuzzClip:
    clip = FuzzClip(
        id=project.next_clip_id,
        start_ms=max(0, int(start)),
        end_ms=max(0, int(start)) + max(120, int(duration)),
        linked_audio_id=linked_audio_id,
        nested_sequence_id=nested,
    )
    project.next_clip_id += 1
    return clip


def make_seed_project(seed: int) -> FuzzProject:
    rng = random.Random(seed)
    project = FuzzProject()
    for tid in range(2):
        track = FuzzTrack(id=tid + 1)
        start = 0
        for _ in range(4):
            dur = rng.randint(500, 2200)
            gap = rng.randint(0, 160)
            track.clips.append(_new_clip(project, start + gap, dur))
            start += gap + dur + rng.randint(0, 180)
        project.video_tracks.append(track)
    audio = FuzzTrack(id=100)
    for clip in project.video_tracks[0].clips[:3]:
        a = _new_clip(project, clip.start_ms, clip.duration_ms, linked_audio_id=clip.id)
        clip.linked_audio_id = a.id
        audio.clips.append(a)
    project.audio_tracks.append(audio)
    project.spine_actor_tracks.append(FuzzTrack(id=200, clips=[_new_clip(project, 400, 1800)]))
    project.live2d_actor_tracks.append(FuzzTrack(id=300, clips=[_new_clip(project, 1900, 2200)]))
    project.video_tracks[0].clips[0].nested_sequence_id = "nested-1"
    return project


def _all_tracks(project: FuzzProject) -> list[FuzzTrack]:
    return (
        list(project.video_tracks)
        + list(project.audio_tracks)
        + list(project.spine_actor_tracks)
        + list(project.live2d_actor_tracks)
    )


def _sort(project: FuzzProject) -> None:
    for track in _all_tracks(project):
        track.clips.sort(key=lambda clip: (clip.start_ms, clip.id))


def _clip_delta_bounds(track: FuzzTrack, clip: FuzzClip) -> tuple[int, int]:
    ordered = sorted(track.clips, key=lambda c: (c.start_ms, c.id))
    idx = ordered.index(clip)
    lower = -clip.start_ms
    upper = 10_000_000
    if idx > 0:
        prev_clip = ordered[idx - 1]
        lower = max(lower, prev_clip.end_ms - clip.start_ms)
    if idx < len(ordered) - 1:
        next_clip = ordered[idx + 1]
        upper = min(upper, next_clip.start_ms - clip.end_ms)
    return int(lower), int(upper)


def blade(track: FuzzTrack, clip: FuzzClip, at_ms: int, project: FuzzProject) -> bool:
    if not (clip.start_ms + 80 < at_ms < clip.end_ms - 80):
        return False
    right = copy.deepcopy(clip)
    right.id = project.next_clip_id
    project.next_clip_id += 1
    right.start_ms = int(at_ms)
    right.source_in_ms += at_ms - clip.start_ms
    clip.end_ms = int(at_ms)
    clip.source_out_ms = clip.source_in_ms + clip.duration_ms
    right.source_out_ms = right.source_in_ms + right.duration_ms
    track.clips.append(right)
    _sort(project)
    return True


def move_linked(project: FuzzProject, clip_id: int, delta_ms: int) -> None:
    linked_ids = {clip_id}
    for track in _all_tracks(project):
        for clip in track.clips:
            if clip.id == clip_id and clip.linked_audio_id is not None:
                linked_ids.add(int(clip.linked_audio_id))
            if clip.linked_audio_id == clip_id:
                linked_ids.add(int(clip.id))
    linked_clips: list[tuple[FuzzTrack, FuzzClip]] = []
    for track in _all_tracks(project):
        for clip in track.clips:
            if clip.id in linked_ids:
                linked_clips.append((track, clip))
    lower = -10_000_000
    upper = 10_000_000
    for track, clip in linked_clips:
        lo, hi = _clip_delta_bounds(track, clip)
        lower = max(lower, lo)
        upper = min(upper, hi)
    shift = max(lower, min(upper, int(delta_ms)))
    for _track, clip in linked_clips:
        clip.start_ms += shift
        clip.end_ms += shift
    _sort(project)


def ripple_trim(track: FuzzTrack, clip: FuzzClip, delta_ms: int) -> None:
    old_end = clip.end_ms
    clip.end_ms = max(clip.start_ms + 120, clip.end_ms + int(delta_ms))
    diff = clip.end_ms - old_end
    for other in track.clips:
        if other.id != clip.id and other.start_ms >= old_end:
            other.start_ms += diff
            other.end_ms += diff
    clip.source_out_ms = clip.source_in_ms + clip.duration_ms


def roll_edit(track: FuzzTrack, left: FuzzClip, right: FuzzClip, delta_ms: int) -> None:
    if left.end_ms != right.start_ms:
        return
    next_cut = max(left.start_ms + 120, min(right.end_ms - 120, left.end_ms + int(delta_ms)))
    left.end_ms = next_cut
    right.start_ms = next_cut
    left.source_out_ms = left.source_in_ms + left.duration_ms
    right.source_out_ms = right.source_in_ms + right.duration_ms


def slip_clip(clip: FuzzClip, delta_ms: int) -> None:
    duration = clip.duration_ms
    clip.source_in_ms = max(0, clip.source_in_ms + int(delta_ms))
    clip.source_out_ms = clip.source_in_ms + duration


def slide_clip(track: FuzzTrack, clip: FuzzClip, delta_ms: int) -> None:
    idx = track.clips.index(clip)
    if idx <= 0 or idx >= len(track.clips) - 1:
        return
    prev_clip = track.clips[idx - 1]
    next_clip = track.clips[idx + 1]
    min_start = prev_clip.start_ms + 120
    max_end = next_clip.end_ms - 120
    dur = clip.duration_ms
    new_start = max(min_start, min(max_end - dur, clip.start_ms + int(delta_ms)))
    diff = new_start - clip.start_ms
    prev_clip.end_ms += diff
    clip.start_ms += diff
    clip.end_ms += diff
    next_clip.start_ms += diff


def validate_project(project: FuzzProject) -> list[str]:
    issues: list[str] = []
    seen_ids: set[int] = set()
    for track in _all_tracks(project):
        last_end = -1
        for clip in sorted(track.clips, key=lambda c: c.start_ms):
            if clip.id in seen_ids:
                issues.append(f"duplicate clip id {clip.id}")
            seen_ids.add(clip.id)
            if clip.start_ms < 0:
                issues.append(f"negative start clip {clip.id}")
            if clip.end_ms <= clip.start_ms:
                issues.append(f"non-positive duration clip {clip.id}")
            if clip.source_out_ms <= clip.source_in_ms:
                issues.append(f"non-positive source window clip {clip.id}")
            if clip.start_ms < last_end:
                issues.append(f"overlap on track {track.id} at clip {clip.id}")
            last_end = max(last_end, clip.end_ms)
    linked_audio_ids = {
        clip.id
        for track in project.audio_tracks
        for clip in track.clips
    }
    for track in project.video_tracks:
        for clip in track.clips:
            if clip.linked_audio_id is not None and clip.linked_audio_id not in linked_audio_ids:
                issues.append(f"missing linked audio clip {clip.linked_audio_id}")
    return issues


def run_fuzzer(*, iterations: int = 200, seed: int = 42) -> dict[str, Any]:
    rng = random.Random(seed)
    project = make_seed_project(seed)
    undo_stack: list[FuzzProject] = [copy.deepcopy(project)]
    failures: list[str] = []
    op_counts: dict[str, int] = {}
    for step in range(int(iterations)):
        op = rng.choice(["blade", "move", "ripple", "roll", "slip", "slide", "undo"])
        op_counts[op] = op_counts.get(op, 0) + 1
        try:
            if op == "undo" and len(undo_stack) > 1:
                project = copy.deepcopy(undo_stack[-2])
                undo_stack.pop()
            else:
                track = rng.choice(project.video_tracks)
                if not track.clips:
                    continue
                clip = rng.choice(track.clips)
                if op == "blade":
                    blade(track, clip, rng.randint(clip.start_ms + 1, max(clip.start_ms + 2, clip.end_ms - 1)), project)
                elif op == "move":
                    move_linked(project, clip.id, rng.randint(-420, 520))
                elif op == "ripple":
                    ripple_trim(track, clip, rng.randint(-220, 360))
                elif op == "roll" and len(track.clips) >= 2:
                    _sort(project)
                    for left, right in zip(track.clips, track.clips[1:]):
                        if left.end_ms == right.start_ms:
                            roll_edit(track, left, right, rng.randint(-180, 180))
                            break
                elif op == "slip":
                    slip_clip(clip, rng.randint(-160, 260))
                elif op == "slide" and len(track.clips) >= 3:
                    _sort(project)
                    slide_clip(track, track.clips[min(len(track.clips) - 2, max(1, rng.randrange(len(track.clips))))], rng.randint(-180, 180))
                _sort(project)
                undo_stack.append(copy.deepcopy(project))
                undo_stack = undo_stack[-20:]
            issues = validate_project(project)
            if issues:
                failures.append(f"step {step} {op}: " + "; ".join(issues[:4]))
                break
        except Exception as exc:
            failures.append(f"step {step} {op}: exception {exc}")
            break
    return {
        "ok": not failures,
        "summary": {
            "iterations": int(iterations),
            "seed": int(seed),
            "failures": len(failures),
            "operations": op_counts,
            "undo_depth": len(undo_stack),
            "video_tracks": len(project.video_tracks),
            "audio_tracks": len(project.audio_tracks),
            "actor_tracks": len(project.spine_actor_tracks) + len(project.live2d_actor_tracks),
        },
        "failures": failures,
        "final_project": {
            "video_tracks": [[asdict(clip) for clip in track.clips] for track in project.video_tracks],
            "audio_tracks": [[asdict(clip) for clip in track.clips] for track in project.audio_tracks],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic timeline edit fuzzer.")
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/timeline_fuzzer_qa.json"))
    args = parser.parse_args()
    report = run_fuzzer(iterations=args.iterations, seed=args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
