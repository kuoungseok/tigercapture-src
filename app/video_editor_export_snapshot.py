from __future__ import annotations

import copy
from types import SimpleNamespace


def snapshot_node_item_chain_for_export(track) -> list | None:
    """Clone the active preview node chain into worker-safe objects."""
    chain = getattr(track, "node_item_chain", None)
    if not chain:
        return None

    def clone_mask(mask):
        try:
            if hasattr(mask, "to_dict"):
                from app.node_mask import mask_from_dict

                return mask_from_dict(mask.to_dict())
        except Exception:
            pass
        try:
            return copy.deepcopy(mask)
        except Exception:
            return mask

    def clone_color_grade(grade):
        if grade is None:
            return None
        try:
            from app.color_grading import ColorGrade

            return ColorGrade.from_dict(grade.to_dict())
        except Exception:
            try:
                return copy.deepcopy(grade)
            except Exception:
                return grade

    def clone_blur_params(params):
        if params is None:
            return None
        try:
            from app.blur_params import BlurParams

            return BlurParams.from_dict(params.to_dict())
        except Exception:
            try:
                return copy.deepcopy(params)
            except Exception:
                return params

    def clone_effect_params(params):
        if params is None:
            return None
        try:
            from app.effect_node_params import params_from_dict

            return params_from_dict(params.to_dict())
        except Exception:
            try:
                return copy.deepcopy(params)
            except Exception:
                return params

    snapshot = []
    for node_item, masks in chain:
        node_snapshot = SimpleNamespace(
            NODE_KIND=getattr(node_item, "NODE_KIND", "serial"),
            bypassed=bool(getattr(node_item, "bypassed", False)),
            blur_params=clone_blur_params(getattr(node_item, "blur_params", None)),
            blur_invert_mask=bool(getattr(node_item, "blur_invert_mask", True)),
            effect_params=clone_effect_params(getattr(node_item, "effect_params", None)),
            color_grade=clone_color_grade(getattr(node_item, "color_grade", None)),
        )
        snapshot.append((node_snapshot, [clone_mask(m) for m in (masks or [])]))
    return snapshot or None


def snapshot_clip_effects_for_export(track) -> list | None:
    """Return clip-effect snapshots aligned with export segments."""
    clips = list(getattr(track, "clips", []) or [])
    try:
        from app.timeline_model import expanded_timeline_clips

        clips = expanded_timeline_clips(clips)
    except Exception:
        pass
    if not clips:
        return None

    def clone_param(params, module_name: str, class_name: str):
        if params is None:
            return None
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            return cls.from_dict(params.to_dict())
        except Exception:
            try:
                return copy.deepcopy(params)
            except Exception:
                return params

    def clone_effects(clip):
        clip_events = list(getattr(clip, "cursor_events", []) or [])
        track_events = list(getattr(track, "cursor_events", []) or [])
        clip_polish = dict(getattr(clip, "screenstudio_polish", {}) or {})
        track_polish = dict(getattr(track, "screenstudio_polish", {}) or {})
        return SimpleNamespace(
            video_filters=clone_param(
                getattr(clip, "video_filters", None),
                "app.video_filters",
                "VideoFilterParams",
            ),
            chroma_key=clone_param(
                getattr(clip, "chroma_key", None),
                "app.chroma_key",
                "ChromaKeyParams",
            ),
            bg_removal=clone_param(
                getattr(clip, "bg_removal", None),
                "app.background_removal",
                "BackgroundRemovalParams",
            ),
            stabilizer=clone_param(
                getattr(clip, "stabilizer", None),
                "app.video_stabilizer",
                "StabilizerParams",
            ),
            cursor_events=clip_events or track_events,
            screenstudio_polish=clip_polish or track_polish,
        )

    ranges: list[tuple[int, int, object]] = []
    for clip in sorted(clips, key=lambda c: int(c.timeline_in_ms)):
        s = int(getattr(clip, "source_in_ms", 0))
        e = int(getattr(clip, "effective_source_out_ms", 0))
        if e > s:
            ranges.append((s, e, clone_effects(clip)))

    for seg in getattr(track, "speed_segments", []) or []:
        new_ranges: list[tuple[int, int, object]] = []
        for s, e, effect in ranges:
            if e <= seg.start_ms or s >= seg.end_ms:
                new_ranges.append((s, e, effect))
                continue
            if s < seg.start_ms:
                new_ranges.append((s, seg.start_ms, effect))
            ovl_s = max(s, seg.start_ms)
            ovl_e = min(e, seg.end_ms)
            new_ranges.append((ovl_s, ovl_e, effect))
            if e > seg.end_ms:
                new_ranges.append((seg.end_ms, e, effect))
        ranges = new_ranges

    return [effect for s, e, effect in ranges if e > s] or None
