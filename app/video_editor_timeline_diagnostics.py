from __future__ import annotations

from app.video_editor_transport_workflow import _timeline_frame_ms


def _timeline_edge_proxy_clips(clips) -> list:
    from app.timeline_model import VideoClip

    proxies = []
    for clip in clips or []:
        try:
            clip_id = int(getattr(clip, "id"))
            start = int(getattr(clip, "timeline_in_ms", 0) or 0)
            source_in = int(getattr(clip, "source_in_ms", 0) or 0)
            source_out = int(getattr(clip, "source_out_ms", 0) or 0)
            source_duration = int(getattr(clip, "source_duration_ms", 0) or 0)
            timeline_out = int(getattr(clip, "timeline_out_ms", start) or start)
        except Exception:
            continue
        if source_out <= source_in:
            length = max(0, timeline_out - start)
            if length > 0:
                source_out = source_in + length
        source_duration = max(source_duration, source_out, source_in)
        proxies.append(VideoClip(
            id=clip_id,
            source_path=getattr(clip, "source_path", None),
            source_duration_ms=source_duration,
            timeline_in_ms=start,
            source_in_ms=source_in,
            source_out_ms=source_out,
        ))
    return proxies


def _timeline_edge_issue_summary(
    video_tracks=None,
    settings: dict | None = None,
    *,
    track_id: int | None = None,
) -> dict:
    from app.timeline_model import detect_timeline_edge_issues

    frame_ms = _timeline_frame_ms(settings)
    totals = {
        "frame_ms": frame_ms,
        "issue_count": 0,
        "auto_fixable_count": 0,
        "micro_gap_count": 0,
        "micro_overlap_count": 0,
        "gap_count": 0,
        "overlap_count": 0,
        "tracks": [],
    }
    for track in video_tracks or []:
        try:
            tid = int(getattr(track, "id"))
        except Exception:
            continue
        if track_id is not None and tid != int(track_id):
            continue
        issues = detect_timeline_edge_issues(
            _timeline_edge_proxy_clips(getattr(track, "clips", []) or []),
            frame_ms=frame_ms,
        )
        if not issues:
            continue
        counts = {
            "track_id": tid,
            "locked": int(bool(getattr(track, "locked", False))),
            "issue_count": len(issues),
            "auto_fixable_count": sum(int(i.get("auto_fixable", 0) or 0) for i in issues),
            "micro_gap_count": sum(1 for i in issues if i.get("kind") == "micro_gap"),
            "micro_overlap_count": sum(1 for i in issues if i.get("kind") == "micro_overlap"),
            "gap_count": sum(1 for i in issues if i.get("kind") == "gap"),
            "overlap_count": sum(1 for i in issues if i.get("kind") == "overlap"),
            "issues": issues[:8],
        }
        totals["tracks"].append(counts)
        for key in (
            "issue_count",
            "auto_fixable_count",
            "micro_gap_count",
            "micro_overlap_count",
            "gap_count",
            "overlap_count",
        ):
            totals[key] += int(counts[key])
    return totals

