"""CapCut-style creator workflow helpers.

The heavy parts of a CapCut-like product, such as speech recognition and object
segmentation, need optional model/runtime backends.  This module keeps the
product contract Qt-free and deterministic: it turns project/media metadata
into caption, shorts, search, reframe, voice, background-removal, social export,
and one-click recommendation plans that the editor UI and QA can consume.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class CapCutCreatorArea:
    id: str
    label: str
    user_value: str
    evidence: str


CAPCUT_CREATOR_AREAS: tuple[CapCutCreatorArea, ...] = (
    CapCutCreatorArea(
        "auto_captions",
        "Auto captions + caption templates",
        "Speech-to-caption output can immediately inherit readable short-form styles.",
        "capcut_auto_caption_plan",
    ),
    CapCutCreatorArea(
        "long_to_shorts",
        "Long video to Shorts",
        "Long recordings get ranked short segments with hook/caption/social-export defaults.",
        "capcut_long_to_shorts_plan",
    ),
    CapCutCreatorArea(
        "smart_media_search",
        "Smart media search",
        "Media can be searched by object tags, dialogue words, people, file metadata, and type.",
        "capcut_smart_media_index + capcut_smart_media_search",
    ),
    CapCutCreatorArea(
        "template_ecosystem",
        "Creator template ecosystem",
        "CapCut-like hook/caption/reframe/publish templates appear in preset search and one-click plans.",
        "app.preset_library.CAPCUT_CREATOR_WORKFLOW_PRESETS",
    ),
    CapCutCreatorArea(
        "subject_reframe",
        "Subject-aware vertical reframe",
        "9:16/1:1 outputs keep the main object near the safe center instead of blind center-cropping.",
        "capcut_subject_reframe_plan",
    ),
    CapCutCreatorArea(
        "keyframe_graphs",
        "Easy keyframes + graph curves",
        "Non-technical users get a small set of motion graphs instead of raw timeline keyframe editing.",
        "capcut_keyframe_graph_plan",
    ),
    CapCutCreatorArea(
        "voice_tools",
        "AI voice and cleanup workflow",
        "Voice enhance, noise reduction, TTS/custom voice placeholders, stem separation, and loudness are planned together.",
        "capcut_voice_tool_plan",
    ),
    CapCutCreatorArea(
        "background_removal",
        "Background removal / green screen UX",
        "Users get a clear route through object segmentation, chroma key, and manual mask fallback.",
        "capcut_background_removal_plan",
    ),
    CapCutCreatorArea(
        "social_exports",
        "Social export presets",
        "TikTok/Reels/Shorts exports get vertical size, captions, safe margins, loop defaults, and delivery metadata.",
        "capcut_social_export_plan",
    ),
    CapCutCreatorArea(
        "ai_recommendations",
        "AI recommended edit flow",
        "The app can explain and apply a template-first plan for a project without making users pick every tool.",
        "capcut_ai_recommendation_plan",
    ),
)


SOCIAL_EXPORT_PROFILES: dict[str, dict[str, Any]] = {
    "tiktok": {
        "label": "TikTok",
        "canvas_width": 1080,
        "canvas_height": 1920,
        "fps": 60.0,
        "max_duration_s": 180,
        "caption_safe_y": (0.14, 0.82),
        "loop_friendly": True,
    },
    "reels": {
        "label": "Instagram Reels",
        "canvas_width": 1080,
        "canvas_height": 1920,
        "fps": 60.0,
        "max_duration_s": 90,
        "caption_safe_y": (0.14, 0.80),
        "loop_friendly": True,
    },
    "shorts": {
        "label": "YouTube Shorts",
        "canvas_width": 1080,
        "canvas_height": 1920,
        "fps": 60.0,
        "max_duration_s": 60,
        "caption_safe_y": (0.16, 0.78),
        "loop_friendly": True,
    },
    "web": {
        "label": "Web Demo",
        "canvas_width": 1920,
        "canvas_height": 1080,
        "fps": 60.0,
        "max_duration_s": 600,
        "caption_safe_y": (0.08, 0.88),
        "loop_friendly": False,
    },
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clip_duration_ms(clip: Mapping[str, Any]) -> int:
    for key in ("duration_ms", "duration", "length_ms", "length"):
        if key in clip:
            try:
                value = float(clip.get(key) or 0)
            except Exception:
                value = 0
            if key in {"duration", "length"} and value < 10000:
                value *= 1000.0
            return max(0, int(round(value)))
    try:
        src_in = float(clip.get("source_in_ms", 0) or 0)
        src_out = float(clip.get("source_out_ms", src_in) or src_in)
        return max(0, int(round(src_out - src_in)))
    except Exception:
        return 0


def _project_duration_s(project: Mapping[str, Any]) -> float:
    explicit = project.get("duration_s")
    if explicit is not None:
        try:
            return max(0.0, float(explicit))
        except Exception:
            pass
    explicit_ms = project.get("duration_ms")
    if explicit_ms is not None:
        try:
            return max(0.0, float(explicit_ms) / 1000.0)
        except Exception:
            pass
    end_ms = 0
    for track_key in ("video_tracks", "audio_tracks", "tracks"):
        for track in _as_list(project.get(track_key)):
            track_data = _as_dict(track)
            for clip in _as_list(track_data.get("clips")):
                clip_data = _as_dict(clip)
                try:
                    start = int(float(clip_data.get("timeline_in_ms", clip_data.get("offset_ms", 0)) or 0))
                except Exception:
                    start = 0
                end_ms = max(end_ms, start + _clip_duration_ms(clip_data))
    return end_ms / 1000.0


def normalize_project_summary(project_summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Derive a compact creator summary from either a project doc or summary."""
    source = dict(project_summary or {})
    duration_s = _project_duration_s(source)
    video_tracks = _as_list(source.get("video_tracks"))
    audio_tracks = _as_list(source.get("audio_tracks"))
    subtitles = _as_list(source.get("subtitles") or source.get("captions"))
    media_items = _as_list(source.get("media_items") or source.get("media") or source.get("assets"))

    video_count = int(source.get("video_count") or 0)
    if not video_count:
        video_count = sum(len(_as_list(_as_dict(track).get("clips"))) for track in video_tracks)
    audio_count = int(source.get("audio_count") or 0)
    if not audio_count:
        audio_count = sum(len(_as_list(_as_dict(track).get("clips"))) for track in audio_tracks)

    has_audio = bool(source.get("has_audio", False) or audio_count or source.get("dialogue") or source.get("voice"))
    shortform = bool(source.get("shortform") or source.get("vertical") or (duration_s and duration_s <= 90))
    screen_recording = bool(source.get("screen_recording") or source.get("tutorial") or source.get("howto"))
    dialogue = bool(source.get("dialogue") or source.get("voice") or source.get("podcast") or has_audio)

    summary = {
        **source,
        "duration_s": duration_s,
        "video_count": video_count,
        "audio_count": audio_count,
        "has_audio": has_audio,
        "caption_count": len(subtitles),
        "has_captions": bool(subtitles),
        "media_count": len(media_items),
        "shortform": shortform,
        "screen_recording": screen_recording,
        "dialogue": dialogue,
        "needs_shorts": bool(duration_s and duration_s > 90),
        "media_items": media_items,
    }
    return summary


def _safe_preset_ids(ids: Iterable[str]) -> list[str]:
    try:
        from app.preset_library import preset_by_id
    except Exception:
        return list(dict.fromkeys(str(item) for item in ids if item))
    out: list[str] = []
    for preset_id in ids:
        if preset_by_id(str(preset_id)) is not None:
            out.append(str(preset_id))
    return list(dict.fromkeys(out))


def capcut_auto_caption_plan(
    project_summary: Mapping[str, Any] | None = None,
    transcript_segments: Iterable[Mapping[str, Any]] | None = None,
    *,
    language: str = "auto",
) -> dict[str, Any]:
    summary = normalize_project_summary(project_summary)
    segments = [dict(row) for row in transcript_segments or _as_list(summary.get("transcript_segments"))]
    has_audio = bool(summary.get("has_audio"))
    preset_ids = _safe_preset_ids([
        "caption-capcut-word-pop",
        "caption-capcut-karaoke-fast",
        "caption-auto-bold-pop",
        "caption-vertical-safe",
        "template-capcut-auto-caption-shorts",
    ])
    ready = has_audio or bool(segments) or bool(summary.get("has_captions"))
    return {
        "ok": True,
        "ready_for_apply": ready,
        "mode": "transcript_ready" if segments else ("caption_style_ready" if has_audio else "needs_audio_or_transcript"),
        "language": language,
        "segments": segments,
        "segment_count": len(segments),
        "style_preset_ids": preset_ids,
        "default_style_id": preset_ids[0] if preset_ids else "",
        "actions": [] if ready else ["Import audio/video or paste transcript segments before auto-caption generation."],
    }


def _score_transcript_segment(segment: Mapping[str, Any], index: int) -> float:
    text = str(segment.get("text", "") or "").lower()
    score = 1.0
    for term in ("?", "how", "why", "best", "secret", "tip", "first", "watch", "wow", "fail", "win"):
        if term in text:
            score += 0.6
    score += max(0.0, 1.0 - index * 0.08)
    try:
        duration = float(segment.get("end_ms", 0) or 0) - float(segment.get("start_ms", 0) or 0)
        if 5000 <= duration <= 45000:
            score += 0.35
    except Exception:
        pass
    return round(score, 3)


def capcut_long_to_shorts_plan(project_summary: Mapping[str, Any] | None = None, *, target_count: int = 3) -> dict[str, Any]:
    summary = normalize_project_summary(project_summary)
    duration_s = float(summary.get("duration_s", 0.0) or 0.0)
    transcript = [dict(row) for row in _as_list(summary.get("transcript_segments"))]
    candidates: list[dict[str, Any]] = []
    if transcript:
        scored = sorted(
            (
                (_score_transcript_segment(segment, idx), segment)
                for idx, segment in enumerate(transcript)
                if int(segment.get("end_ms", 0) or 0) > int(segment.get("start_ms", 0) or 0)
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        for score, segment in scored[:max(1, target_count)]:
            start_ms = max(0, int(segment.get("start_ms", 0) or 0) - 1200)
            end_ms = min(int(duration_s * 1000) if duration_s else int(segment.get("end_ms", 0) or 0) + 1200, int(segment.get("end_ms", 0) or 0) + 1200)
            candidates.append({
                "start_ms": start_ms,
                "end_ms": max(start_ms + 1000, end_ms),
                "score": score,
                "reason": "dialogue_hook",
                "hook_text": str(segment.get("text", "") or "")[:96],
            })
    else:
        total_ms = max(15000, int(round(duration_s * 1000))) if duration_s else 45000
        window_ms = 30000 if total_ms >= 90000 else min(30000, total_ms)
        spacing = max(window_ms, total_ms // max(1, target_count + 1))
        for idx in range(max(1, target_count)):
            center = min(total_ms - window_ms // 2, max(window_ms // 2, spacing * (idx + 1)))
            start_ms = max(0, center - window_ms // 2)
            candidates.append({
                "start_ms": start_ms,
                "end_ms": min(total_ms, start_ms + window_ms),
                "score": round(1.0 - idx * 0.08, 3),
                "reason": "even_energy_window",
                "hook_text": f"Short candidate {idx + 1}",
            })
    preset_ids = _safe_preset_ids([
        "template-capcut-long-to-shorts",
        "template-capcut-auto-caption-shorts",
        "template-capcut-social-publish-kit",
        "template-screenstudio-short-export",
    ])
    return {
        "ok": True,
        "needs_shorts": bool(summary.get("needs_shorts")),
        "source_duration_s": duration_s,
        "target_count": max(1, target_count),
        "candidates": candidates,
        "template_ids": preset_ids,
        "recommended_template_id": preset_ids[0] if preset_ids else "",
    }


def capcut_hook_score_plan(
    project_summary: Mapping[str, Any] | None = None,
    *,
    target_count: int = 5,
) -> dict[str, Any]:
    """Rank hook candidates for short-form edits.

    This is intentionally deterministic.  Real ML/sentiment scoring can feed the
    same shape later, while current QA and UI can still show useful suggestions.
    """
    summary = normalize_project_summary(project_summary)
    transcript = [dict(row) for row in _as_list(summary.get("transcript_segments"))]
    hooks: list[dict[str, Any]] = []
    for idx, segment in enumerate(transcript):
        try:
            start_ms = int(segment.get("start_ms", segment.get("start", 0)) or 0)
            end_ms = int(segment.get("end_ms", segment.get("end", start_ms + 1800)) or start_ms + 1800)
        except Exception:
            continue
        if end_ms < 10000 and start_ms < 10000 and ("start_ms" not in segment and "end_ms" not in segment):
            start_ms *= 1000
            end_ms *= 1000
        text = " ".join(str(segment.get("text") or segment.get("caption") or "").split())
        if not text:
            continue
        lower = text.casefold()
        reason = "strong_statement"
        if "?" in text:
            reason = "question_hook"
        elif any(term in lower for term in ("how", "why", "secret", "tip")):
            reason = "how_to_hook"
        elif any(term in lower for term in ("best", "win", "wow", "fail")):
            reason = "payoff_hook"
        score = _score_transcript_segment({"start_ms": start_ms, "end_ms": end_ms, "text": text}, idx)
        hooks.append(
            {
                "rank": 0,
                "start_ms": max(0, start_ms - 800),
                "end_ms": max(start_ms + 1000, end_ms + 900),
                "score": score,
                "reason": reason,
                "hook_text": _trim_caption_text(text, max_chars=64),
                "thumbnail_text": _trim_caption_text(text, max_chars=28),
            }
        )
    if not hooks:
        for idx, candidate in enumerate(_as_list(capcut_long_to_shorts_plan(summary, target_count=target_count).get("candidates"))):
            hooks.append(
                {
                    "rank": 0,
                    "start_ms": int(candidate.get("start_ms", 0) or 0),
                    "end_ms": int(candidate.get("end_ms", 1000) or 1000),
                    "score": float(candidate.get("score", 0.0) or 0.0),
                    "reason": str(candidate.get("reason") or "timeline_candidate"),
                    "hook_text": _trim_caption_text(candidate.get("hook_text"), max_chars=64),
                    "thumbnail_text": _trim_caption_text(candidate.get("hook_text"), max_chars=28),
                }
            )
    hooks = sorted(hooks, key=lambda row: (-float(row.get("score", 0.0) or 0.0), int(row.get("start_ms", 0) or 0)))[: max(1, target_count)]
    for idx, row in enumerate(hooks, start=1):
        row["rank"] = idx
    return {
        "ok": True,
        "ready": bool(hooks),
        "target_count": max(1, target_count),
        "hooks": hooks,
        "top_hook": hooks[0] if hooks else None,
        "recommended_title": hooks[0]["hook_text"] if hooks else "",
    }


def capcut_smart_media_index(media_items: Iterable[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for idx, item in enumerate(media_items or []):
        row = dict(item)
        path = str(row.get("path") or row.get("file") or row.get("name") or "")
        name = str(row.get("name") or Path(path).name or f"media-{idx + 1}")
        kind = str(row.get("kind") or row.get("type") or Path(path).suffix.lstrip(".") or "media").lower()
        object_tags = [str(tag).lower() for tag in _as_list(row.get("object_tags") or row.get("objects"))]
        people = [str(tag).lower() for tag in _as_list(row.get("people") or row.get("persons"))]
        dialogue = " ".join(str(part) for part in _as_list(row.get("dialogue") or row.get("transcript")) if part)
        labels = [str(tag).lower() for tag in _as_list(row.get("tags") or row.get("labels"))]
        searchable = " ".join([name, path, kind, dialogue, " ".join(object_tags), " ".join(people), " ".join(labels)]).lower()
        records.append({
            "id": str(row.get("id") or f"media-{idx + 1}"),
            "name": name,
            "path": path,
            "kind": kind,
            "duration_s": float(row.get("duration_s", 0.0) or 0.0),
            "object_tags": object_tags,
            "people": people,
            "tags": labels,
            "dialogue": dialogue,
            "searchable_text": " ".join(searchable.split()),
        })
    return records


def capcut_smart_media_search(
    index: Iterable[Mapping[str, Any]],
    query: str = "",
    *,
    kind: str | None = None,
    min_score: int = 1,
) -> list[dict[str, Any]]:
    terms = [term for term in str(query or "").lower().split() if term]
    results: list[tuple[int, dict[str, Any]]] = []
    for record in index:
        row = dict(record)
        if kind and str(row.get("kind") or "").lower() != kind.lower():
            continue
        haystack = str(row.get("searchable_text") or "").lower()
        score = 0
        if not terms:
            score = 1
        for term in terms:
            if term in haystack:
                score += 8
            if term in row.get("object_tags", []):
                score += 5
            if term in row.get("people", []):
                score += 5
            if term and str(row.get("name") or "").lower().startswith(term):
                score += 3
        if score >= min_score:
            row["score"] = score
            results.append((score, row))
    return [row for _score, row in sorted(results, key=lambda item: (-item[0], item[1].get("name", "")))]


def capcut_subject_reframe_plan(
    project_summary: Mapping[str, Any] | None = None,
    detections: Iterable[Mapping[str, Any]] | None = None,
    *,
    target_aspect: str = "9:16",
) -> dict[str, Any]:
    summary = normalize_project_summary(project_summary)
    rows = [dict(row) for row in detections or _as_list(summary.get("subject_detections"))]
    keyframes: list[dict[str, Any]] = []
    for row in rows:
        try:
            t_ms = int(row.get("t_ms", row.get("ms", 0)) or 0)
            x = max(0.0, min(1.0, float(row.get("x_norm", row.get("x", 0.5)) or 0.5)))
            y = max(0.0, min(1.0, float(row.get("y_norm", row.get("y", 0.5)) or 0.5)))
            confidence = max(0.0, min(1.0, float(row.get("confidence", 1.0) or 1.0)))
        except Exception:
            continue
        if confidence < 0.2:
            continue
        keyframes.append({
            "t_ms": t_ms,
            "x_norm": round(x, 4),
            "y_norm": round(y, 4),
            "scale": 1.12 if target_aspect in {"9:16", "4:5"} else 1.04,
            "confidence": round(confidence, 3),
        })
    if not keyframes:
        duration_s = float(summary.get("duration_s", 0.0) or 0.0)
        end_ms = max(1000, int(min(duration_s, 45.0) * 1000)) if duration_s else 30000
        keyframes = [
            {"t_ms": 0, "x_norm": 0.5, "y_norm": 0.48, "scale": 1.08, "confidence": 0.55},
            {"t_ms": end_ms, "x_norm": 0.5, "y_norm": 0.50, "scale": 1.08, "confidence": 0.55},
        ]
    return {
        "ok": True,
        "target_aspect": target_aspect,
        "mode": "subject_aware" if rows else "center_safe_fallback",
        "keep_main_object_in_frame": True,
        "safe_margin": 0.12,
        "keyframes": keyframes,
        "preset_ids": _safe_preset_ids(["motion-subject-keep-reframe", "template-capcut-subject-reframe"]),
    }


def capcut_keyframe_graph_plan(intent: str = "hook") -> dict[str, Any]:
    intent_key = str(intent or "hook").lower()
    if intent_key in {"smooth", "product", "demo"}:
        graph = "ease_in_out"
        keyframes = [{"t": 0.0, "scale": 1.0}, {"t": 1.0, "scale": 1.08}]
    elif intent_key in {"punch", "impact", "gameplay"}:
        graph = "ease_out_back"
        keyframes = [{"t": 0.0, "scale": 1.0}, {"t": 0.22, "scale": 1.22}, {"t": 1.0, "scale": 1.08}]
    else:
        graph = "fast_hook_pop"
        keyframes = [{"t": 0.0, "scale": 1.0}, {"t": 0.18, "scale": 1.16}, {"t": 1.0, "scale": 1.06}]
    return {
        "ok": True,
        "intent": intent_key,
        "graph": graph,
        "keyframes": keyframes,
        "preset_ids": _safe_preset_ids(["motion-hook-bounce-in", "motion-subject-keep-reframe", "motion-camera-punch-in"]),
    }


def capcut_voice_tool_plan(project_summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    summary = normalize_project_summary(project_summary)
    has_audio = bool(summary.get("has_audio"))
    tools = [
        {"id": "enhance_voice", "ready": has_audio, "preset_id": "audio-capcut-voice-enhance"},
        {"id": "reduce_noise", "ready": has_audio, "preset_id": "audio-dialogue-cleanup-strong"},
        {"id": "loudness_shortform", "ready": has_audio, "preset_id": "audio-loudness-shortform"},
        {"id": "stem_separation", "ready": has_audio, "preset_id": "audio-vocal-music-separation"},
        {"id": "text_to_speech", "ready": True, "preset_id": ""},
        {"id": "custom_voice_placeholder", "ready": True, "preset_id": ""},
    ]
    return {
        "ok": True,
        "has_audio": has_audio,
        "tools": tools,
        "preset_ids": _safe_preset_ids([row["preset_id"] for row in tools if row.get("preset_id")]),
        "actions": [] if has_audio else ["Import audio/video before applying voice cleanup and separation."],
    }


def capcut_background_removal_plan(project_summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    summary = normalize_project_summary(project_summary)
    return {
        "ok": True,
        "video_count": int(summary.get("video_count", 0) or 0),
        "routes": [
            {"id": "object_segmentation", "label": "Auto object/person cutout", "backend": "optional-ai", "ready": True},
            {"id": "chroma_key", "label": "Green/blue screen key", "backend": "native-preview-export", "ready": True},
            {"id": "manual_mask", "label": "Manual mask + tracker fallback", "backend": "opencv-tracker", "ready": True},
        ],
        "preset_ids": _safe_preset_ids(["effect-ai-background-cutout-pop", "effect-green-screen-clean", "effect-blue-screen-clean"]),
        "recommended_route": "object_segmentation",
    }


def capcut_social_export_plan(
    project_summary: Mapping[str, Any] | None = None,
    *,
    platform: str = "shorts",
) -> dict[str, Any]:
    summary = normalize_project_summary(project_summary)
    key = str(platform or "shorts").lower()
    profile = dict(SOCIAL_EXPORT_PROFILES.get(key) or SOCIAL_EXPORT_PROFILES["shorts"])
    duration_s = float(summary.get("duration_s", 0.0) or 0.0)
    over_limit = bool(duration_s and duration_s > float(profile["max_duration_s"]))
    return {
        "ok": True,
        "platform": key if key in SOCIAL_EXPORT_PROFILES else "shorts",
        "profile": profile,
        "export_settings": {
            "format_id": "mp4",
            "quality_id": "high",
            "canvas_width": profile["canvas_width"],
            "canvas_height": profile["canvas_height"],
            "fps": profile["fps"],
            "burn_captions": True,
            "safe_margin": 0.10,
        },
        "duration_over_limit": over_limit,
        "actions": ["Use long-to-shorts candidates before upload."] if over_limit else [],
        "preset_ids": _safe_preset_ids(["template-capcut-social-publish-kit", "template-screenstudio-short-export"]),
    }


def _clean_filename_token(value: Any, *, fallback: str = "short") -> str:
    text = str(value or "").strip().lower()
    keep: list[str] = []
    for ch in text:
        if ch.isalnum():
            keep.append(ch)
        elif ch in {" ", "-", "_"}:
            keep.append("-")
    out = "".join(keep).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return (out or fallback)[:48]


def _trim_caption_text(value: Any, *, max_chars: int = 42) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max(8, max_chars - 1)].rstrip() + "..."


def capcut_caption_timeline_rows(
    project_summary: Mapping[str, Any] | None = None,
    transcript_segments: Iterable[Mapping[str, Any]] | None = None,
    *,
    style_preset_id: str = "caption-capcut-word-pop",
) -> list[dict[str, Any]]:
    """Return Subtitle-compatible rows with caption style metadata.

    `app.subtitles.Subtitle` only needs start/end/text/show_box.  The extra
    style fields are intentionally sidecar-safe so the UI can use them without
    breaking older project files that ignore unknown keys.
    """
    summary = normalize_project_summary(project_summary)
    rows = [dict(row) for row in transcript_segments or _as_list(summary.get("transcript_segments"))]
    if not rows:
        rows = [dict(row) for row in _as_list(summary.get("subtitles") or summary.get("captions"))]
    out: list[dict[str, Any]] = []
    last_end = 0
    for idx, row in enumerate(rows):
        try:
            start_ms = int(row.get("start_ms", row.get("start", 0)) or 0)
            end_ms = int(row.get("end_ms", row.get("end", start_ms + 1800)) or start_ms + 1800)
        except Exception:
            continue
        if end_ms < 10000 and start_ms < 10000 and ("start_ms" not in row and "end_ms" not in row):
            start_ms *= 1000
            end_ms *= 1000
        start_ms = max(last_end, max(0, start_ms))
        end_ms = max(start_ms + 500, end_ms)
        text = _trim_caption_text(row.get("text", row.get("caption", "")))
        if not text:
            continue
        out.append({
            "start_ms": start_ms,
            "end_ms": end_ms,
            "text": text,
            "show_box": True,
            "style_preset_id": style_preset_id,
            "source": "capcut_auto_caption",
            "word_highlight": "karaoke" in style_preset_id or "word" in style_preset_id,
            "index": idx + 1,
        })
        last_end = end_ms
    return out


def capcut_caption_beat_plan(
    project_summary: Mapping[str, Any] | None = None,
    transcript_segments: Iterable[Mapping[str, Any]] | None = None,
    *,
    max_beats: int = 8,
) -> dict[str, Any]:
    """Plan CapCut-like caption beats for word-pop/karaoke styling."""
    summary = normalize_project_summary(project_summary)
    rows = capcut_caption_timeline_rows(summary, transcript_segments)
    beats: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[: max(1, max_beats)]):
        words = [word.strip(".,!?;:()[]{}\"'").lower() for word in str(row.get("text") or "").split()]
        emphasis = [
            word
            for word in words
            if len(word) >= 5 or word in {"why", "how", "best", "tip", "win", "wow"}
        ][:4]
        beat_type = "caption"
        if idx == 0 or any(word in {"why", "how"} for word in words):
            beat_type = "hook"
        elif any(word in {"export", "follow", "subscribe", "watch"} for word in words):
            beat_type = "cta"
        beats.append(
            {
                "index": idx + 1,
                "start_ms": int(row.get("start_ms", 0) or 0),
                "end_ms": int(row.get("end_ms", 0) or 0),
                "text": row.get("text", ""),
                "beat_type": beat_type,
                "style_preset_id": row.get("style_preset_id", "caption-capcut-word-pop"),
                "emphasis_terms": emphasis,
                "animation": "word_pop" if beat_type != "cta" else "cta_pulse",
            }
        )
    return {
        "ok": True,
        "ready": bool(beats),
        "beat_count": len(beats),
        "beats": beats,
        "default_style_id": rows[0]["style_preset_id"] if rows else "caption-capcut-word-pop",
    }


def capcut_caption_short_quality_model(
    project_summary: Mapping[str, Any] | None = None,
    *,
    platform: str = "shorts",
    target_count: int = 3,
) -> dict[str, Any]:
    """Return a product-facing quality gate for captions and short candidates."""
    summary = normalize_project_summary(project_summary)
    rows = capcut_caption_timeline_rows(summary)
    beats = capcut_caption_beat_plan(summary)
    shorts = capcut_long_to_shorts_plan(summary, target_count=target_count)
    publish = capcut_publish_package_plan(summary, platform=platform, target_count=target_count)
    profile = _as_dict(capcut_social_export_plan(summary, platform=platform).get("profile"))
    no_long_lines = all(len(str(row.get("text") or "")) <= 46 for row in rows) if rows else False
    monotonic = True
    last_end = -1
    for row in rows:
        start = int(row.get("start_ms", 0) or 0)
        end = int(row.get("end_ms", 0) or 0)
        if start < last_end or end <= start:
            monotonic = False
            break
        last_end = end
    checks = {
        "caption_rows": bool(rows),
        "caption_text_readable": bool(no_long_lines),
        "caption_timing_monotonic": bool(monotonic),
        "caption_beats": int(beats.get("beat_count", 0) or 0) >= min(3, max(1, len(rows))),
        "short_candidates": len(_as_list(shorts.get("candidates"))) >= max(1, target_count),
        "safe_area_defined": bool(profile.get("caption_safe_y")),
        "publish_ready": bool(publish.get("ready")),
    }
    passing = sum(1 for value in checks.values() if value)
    score = int(round(passing / max(1, len(checks)) * 100))
    return {
        "ok": all(checks.values()),
        "score": score,
        "platform": str(platform or "shorts"),
        "checks": checks,
        "summary": {
            "caption_rows": len(rows),
            "caption_beats": int(beats.get("beat_count", 0) or 0),
            "short_candidates": len(_as_list(shorts.get("candidates"))),
            "safe_area": profile.get("caption_safe_y"),
            "publish_ready": bool(publish.get("ready")),
        },
        "next_actions": [] if all(checks.values()) else [
            "Add transcript segments or subtitles before using one-click short creation.",
            "Keep caption lines under 46 characters and within vertical safe margins.",
        ],
    }


def _capcut_hashtag_tokens(project_summary: Mapping[str, Any], media_items: Iterable[Mapping[str, Any]] | None = None) -> list[str]:
    tokens: list[str] = ["#shorts", "#tutorial"]
    summary = normalize_project_summary(project_summary)
    if summary.get("screen_recording"):
        tokens.append("#screencapture")
    if summary.get("dialogue"):
        tokens.append("#voiceover")
    if summary.get("shortform") or summary.get("needs_shorts"):
        tokens.append("#capcutstyle")
    for item in media_items or _as_list(summary.get("media_items")):
        row = _as_dict(item)
        for tag in _as_list(row.get("object_tags") or row.get("tags") or row.get("labels")):
            clean = "".join(ch for ch in str(tag).lower() if ch.isalnum())
            if clean:
                tokens.append(f"#{clean}")
    return list(dict.fromkeys(tokens))[:10]


def capcut_publish_package_plan(
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
    *,
    platform: str = "shorts",
    target_count: int = 3,
) -> dict[str, Any]:
    """Build a creator-facing publish package for Shorts/Reels/TikTok output."""
    summary = normalize_project_summary(project_summary)
    export = capcut_social_export_plan(summary, platform=platform)
    hooks = capcut_hook_score_plan(summary, target_count=max(target_count, 3))
    captions = capcut_caption_beat_plan(summary)
    short_plan = capcut_long_to_shorts_plan(summary, target_count=target_count)
    profile = _as_dict(export.get("profile"))
    top_hook = _as_dict(hooks.get("top_hook"))
    title_seed = str(top_hook.get("hook_text") or "Quick creator edit")
    thumbnail_frames = []
    for idx, row in enumerate(_as_list(short_plan.get("candidates"))[: max(1, target_count)], start=1):
        start_ms = int(row.get("start_ms", 0) or 0)
        end_ms = int(row.get("end_ms", start_ms + 1000) or start_ms + 1000)
        thumbnail_frames.append(
            {
                "candidate_id": f"short-{idx:02d}",
                "ms": start_ms + max(0, end_ms - start_ms) // 3,
                "text": _trim_caption_text(row.get("hook_text") or title_seed, max_chars=28),
                "safe_area": profile.get("caption_safe_y"),
            }
        )
    checklist = [
        {"id": "vertical_canvas", "label": "Vertical 1080x1920 canvas", "ok": int(profile.get("canvas_height", 0) or 0) >= 1920},
        {"id": "burned_captions", "label": "Burn readable captions", "ok": bool(captions.get("ready"))},
        {"id": "duration_limit", "label": "Respect platform duration limit", "ok": not bool(export.get("duration_over_limit")) or bool(short_plan.get("candidates"))},
        {"id": "safe_margins", "label": "Caption and CTA safe margins", "ok": bool(profile.get("caption_safe_y"))},
        {"id": "render_jobs", "label": "Short export jobs can be staged", "ok": bool(short_plan.get("candidates"))},
    ]
    return {
        "ok": True,
        "ready": all(bool(row.get("ok")) for row in checklist),
        "platform": export.get("platform"),
        "title_suggestions": [
            _trim_caption_text(title_seed, max_chars=58),
            f"{_trim_caption_text(title_seed, max_chars=42)} | quick edit",
            f"Watch this in {int(profile.get('fps', 60) or 60)}fps",
        ],
        "description_template": "{title}\n\nEdited with creator captions, auto reframe, and short-form export defaults.",
        "hashtags": _capcut_hashtag_tokens(summary, media_items),
        "thumbnail_frames": thumbnail_frames,
        "checklist": checklist,
        "hook_score_plan": hooks,
        "caption_beat_plan": captions,
    }


def capcut_multi_platform_publish_plan(
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
    *,
    platforms: Iterable[str] | None = None,
    target_count: int = 3,
) -> dict[str, Any]:
    """Build Shorts/Reels/TikTok publish variants from the same creator plan."""
    summary = normalize_project_summary(project_summary)
    requested = list(platforms or ("shorts", "tiktok", "reels"))
    variants: list[dict[str, Any]] = []
    for raw_platform in requested:
        platform = str(raw_platform or "shorts").casefold()
        export = capcut_social_export_plan(summary, platform=platform)
        package = capcut_publish_package_plan(
            summary,
            media_items,
            platform=str(export.get("platform") or platform),
            target_count=target_count,
        )
        profile = _as_dict(export.get("profile"))
        checklist = _as_list(package.get("checklist"))
        failing = [dict(row) for row in checklist if not _as_dict(row).get("ok")]
        variants.append(
            {
                "platform": str(export.get("platform") or platform),
                "label": str(profile.get("label") or platform.title()),
                "ready": bool(package.get("ready")),
                "duration_over_limit": bool(export.get("duration_over_limit")),
                "export_settings": dict(_as_dict(export.get("export_settings"))),
                "title": (_as_list(package.get("title_suggestions")) or [""])[0],
                "hashtags": list(_as_list(package.get("hashtags"))),
                "thumbnail_frame": (_as_list(package.get("thumbnail_frames")) or [{}])[0],
                "checklist": checklist,
                "failing_checks": failing,
            }
        )
    ready_variants = [row for row in variants if row.get("ready")]
    recommended = ready_variants[0] if ready_variants else (variants[0] if variants else {})
    return {
        "ok": True,
        "ready": bool(ready_variants),
        "variant_count": len(variants),
        "platforms": [str(row.get("platform") or "") for row in variants],
        "recommended_platform": str(recommended.get("platform") or ""),
        "variants": variants,
        "next_actions": [] if ready_variants else ["Use long-to-shorts ranges before cross-post export."],
    }


def capcut_creator_edit_recipe(
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
    *,
    platform: str = "shorts",
    target_count: int = 3,
) -> dict[str, Any]:
    """Explain the one-click creator edit as a reviewable edit recipe."""
    summary = normalize_project_summary(project_summary)
    shorts = capcut_long_to_shorts_plan(summary, target_count=target_count)
    hooks = capcut_hook_score_plan(summary, target_count=max(target_count, 3))
    captions = capcut_caption_beat_plan(summary)
    reframe = capcut_subject_reframe_plan(summary)
    voice = capcut_voice_tool_plan(summary)
    background = capcut_background_removal_plan(summary)
    export = capcut_social_export_plan(summary, platform=platform)
    publish = capcut_publish_package_plan(summary, media_items, platform=platform, target_count=target_count)
    candidates = _as_list(shorts.get("candidates"))
    top_candidate = _as_dict(candidates[0]) if candidates else _as_dict(hooks.get("top_hook"))
    top_score = float(top_candidate.get("score", 0.0) or 0.0)
    confidence = round(max(0.35, min(1.0, top_score / 3.0)), 3)
    start_ms = int(top_candidate.get("start_ms", 0) or 0)
    end_ms = int(top_candidate.get("end_ms", start_ms + 15_000) or start_ms + 15_000)
    steps: list[dict[str, Any]] = [
        {
            "id": "select_hook_range",
            "type": "trim",
            "label": "Pick the strongest hook range",
            "start_ms": start_ms,
            "end_ms": max(start_ms + 1000, end_ms),
            "reason": str(top_candidate.get("reason") or "best_available_hook"),
            "confidence": confidence,
        },
        {
            "id": "apply_caption_style",
            "type": "caption",
            "label": "Apply word-pop captions",
            "style_preset_id": str(captions.get("default_style_id") or "caption-capcut-word-pop"),
            "beat_count": int(captions.get("beat_count", 0) or 0),
            "reason": "short_form_readability",
            "confidence": 1.0 if captions.get("ready") else 0.45,
        },
        {
            "id": "subject_reframe",
            "type": "reframe",
            "label": "Keep the main subject in vertical safe center",
            "target_aspect": str(reframe.get("target_aspect") or "9:16"),
            "keyframe_count": len(_as_list(reframe.get("keyframes"))),
            "reason": str(reframe.get("mode") or "center_safe_fallback"),
            "confidence": 0.92 if str(reframe.get("mode") or "") == "subject_aware" else 0.62,
        },
        {
            "id": "voice_cleanup",
            "type": "audio",
            "label": "Enhance voice and short-form loudness",
            "preset_ids": list(_as_list(voice.get("preset_ids"))),
            "reason": "creator_voice_clarity",
            "confidence": 0.9 if voice.get("has_audio") else 0.35,
        },
        {
            "id": "background_route",
            "type": "effect",
            "label": "Prepare cutout/chroma/manual mask fallback",
            "recommended_route": str(background.get("recommended_route") or ""),
            "preset_ids": list(_as_list(background.get("preset_ids"))),
            "reason": "fast_subject_cleanup",
            "confidence": 0.72,
        },
        {
            "id": "publish_package",
            "type": "delivery",
            "label": "Prepare title, hashtags, thumbnail, and export",
            "platform": str(export.get("platform") or platform),
            "checklist_ok": bool(publish.get("ready")),
            "reason": "one_click_creator_delivery",
            "confidence": 1.0 if publish.get("ready") else 0.62,
        },
    ]
    missing_inputs: list[str] = []
    if not captions.get("ready"):
        missing_inputs.append("transcript_or_subtitles")
    if not voice.get("has_audio"):
        missing_inputs.append("audio")
    if not candidates:
        missing_inputs.append("short_candidates")
    review_points = [
        {
            "id": "hook_review",
            "ms": start_ms,
            "label": _trim_caption_text(top_candidate.get("hook_text") or "Hook", max_chars=42),
        },
        {
            "id": "thumbnail_review",
            "ms": int((_as_list(publish.get("thumbnail_frames")) or [{"ms": start_ms}])[0].get("ms", start_ms) or start_ms),
            "label": "Thumbnail frame",
        },
        {
            "id": "caption_safe_area",
            "ms": start_ms,
            "label": "Caption safe area",
        },
    ]
    return {
        "ok": True,
        "ready": not missing_inputs,
        "platform": str(export.get("platform") or platform),
        "step_count": len(steps),
        "steps": steps,
        "review_points": review_points,
        "missing_inputs": missing_inputs,
        "recommended_template_id": str(shorts.get("recommended_template_id") or ""),
        "top_hook": dict(top_candidate),
    }


def capcut_timeline_marker_rows(
    project_summary: Mapping[str, Any] | None = None,
    *,
    target_count: int = 3,
) -> list[dict[str, Any]]:
    """Return timeline marker rows for long-to-shorts candidate ranges."""
    plan = capcut_long_to_shorts_plan(project_summary, target_count=target_count)
    markers: list[dict[str, Any]] = []
    for idx, candidate in enumerate(_as_list(plan.get("candidates")), start=1):
        start_ms = int(candidate.get("start_ms", 0) or 0)
        end_ms = int(candidate.get("end_ms", start_ms + 1000) or start_ms + 1000)
        markers.append({
            "id": f"capcut-short-{idx:02d}",
            "label": f"Short {idx}",
            "start_ms": start_ms,
            "end_ms": max(start_ms + 1000, end_ms),
            "color": "#FF6F61",
            "reason": str(candidate.get("reason") or "candidate"),
            "score": float(candidate.get("score", 0.0) or 0.0),
        })
    return markers


def capcut_short_export_jobs(
    project_summary: Mapping[str, Any] | None = None,
    *,
    source_path: str | Path = "",
    project_path: str | Path = "",
    output_dir: str | Path = "",
    platform: str = "shorts",
    target_count: int = 3,
) -> list[dict[str, Any]]:
    """Return RenderQueueJob.create-compatible payloads for Shorts candidates."""
    summary = normalize_project_summary(project_summary)
    short_plan = capcut_long_to_shorts_plan(summary, target_count=target_count)
    export_plan = capcut_social_export_plan(summary, platform=platform)
    settings = _as_dict(export_plan.get("export_settings"))
    profile = _as_dict(export_plan.get("profile"))
    out_root = Path(output_dir) if output_dir else Path("exports") / "capcut_shorts"
    source_name = Path(str(source_path or project_path or "project")).stem or "project"
    jobs: list[dict[str, Any]] = []
    for idx, candidate in enumerate(_as_list(short_plan.get("candidates")), start=1):
        start_ms = int(candidate.get("start_ms", 0) or 0)
        end_ms = int(candidate.get("end_ms", start_ms + 1000) or start_ms + 1000)
        hook = _clean_filename_token(candidate.get("hook_text"), fallback=f"short-{idx:02d}")
        out_path = out_root / f"{_clean_filename_token(source_name, fallback='project')}_{idx:02d}_{hook}.mp4"
        create_kwargs = {
            "label": f"{profile.get('label', 'Shorts')} {idx:02d}: {_trim_caption_text(candidate.get('hook_text'), max_chars=36)}",
            "out_path": str(out_path),
            "in_ms": start_ms,
            "out_ms": max(start_ms + 1000, end_ms),
            "project_path": str(project_path or ""),
            "source_path": str(source_path or ""),
            "format_id": str(settings.get("format_id") or "mp4"),
            "quality_id": str(settings.get("quality_id") or "high"),
        }
        jobs.append({
            **create_kwargs,
            "label": f"{profile.get('label', 'Shorts')} {idx:02d}: {_trim_caption_text(candidate.get('hook_text'), max_chars=36)}",
            "out_path": str(out_path),
            "in_ms": start_ms,
            "out_ms": max(start_ms + 1000, end_ms),
            "project_path": str(project_path or ""),
            "source_path": str(source_path or ""),
            "format_id": str(settings.get("format_id") or "mp4"),
            "quality_id": str(settings.get("quality_id") or "high"),
            "create_kwargs": create_kwargs,
            "diagnostics": (
                f"CapCut short candidate score={candidate.get('score', 0)} "
                f"reason={candidate.get('reason', 'candidate')} "
                f"canvas={settings.get('canvas_width')}x{settings.get('canvas_height')} fps={settings.get('fps')}"
            ),
            "capcut": {
                "platform": export_plan.get("platform"),
                "candidate": candidate,
                "export_settings": settings,
            },
        })
    return jobs


def capcut_creator_apply_bundle(
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
    *,
    platform: str = "shorts",
    target_count: int = 3,
    include_review_panel: bool = True,
) -> dict[str, Any]:
    """Return one payload that the editor can apply as a CapCut-style command."""
    summary = normalize_project_summary(project_summary)
    media = list(media_items if media_items is not None else _as_list(summary.get("media_items")))
    index = capcut_smart_media_index(media)
    recommendation = capcut_ai_recommendation_plan(summary)
    captions = capcut_caption_timeline_rows(summary)
    caption_beats = capcut_caption_beat_plan(summary)
    hook_scores = capcut_hook_score_plan(summary, target_count=max(target_count, 3))
    export = capcut_social_export_plan(summary, platform=platform)
    reframe = capcut_subject_reframe_plan(summary)
    publish_package = capcut_publish_package_plan(summary, media, platform=platform, target_count=target_count)
    edit_recipe = capcut_creator_edit_recipe(summary, media, platform=platform, target_count=target_count)
    try:
        from app.ltx_storyboard import (
            build_ltx_storyboard_plan,
            build_ltx_storyboard_variations,
            storyboard_effect_materialization_payload,
            storyboard_apply_payload,
            storyboard_template_recommendations,
            storyboard_to_edit_plan,
        )

        storyboard_prompt = str(
            summary.get("creator_prompt")
            or summary.get("prompt")
            or "Plan this edit as polished shot cards with captions, zooms, transitions, and a publish-ready ending."
        )
        ltx_storyboard_plan = build_ltx_storyboard_plan(
            storyboard_prompt,
            summary,
            media,
            aspect_ratio="9:16" if platform in {"shorts", "tiktok", "reels"} else "16:9",
        )
        ltx_storyboard = ltx_storyboard_plan.to_dict()
        ltx_storyboard_edit_plan_obj = storyboard_to_edit_plan(ltx_storyboard_plan)
        ltx_storyboard_edit_plan = ltx_storyboard_edit_plan_obj.to_dict()
        ltx_storyboard_apply_payload = storyboard_apply_payload(ltx_storyboard_plan)
        ltx_storyboard_effect_materialization = storyboard_effect_materialization_payload(
            ltx_storyboard_plan,
            ltx_storyboard_apply_payload,
        )
        ltx_storyboard_variations = build_ltx_storyboard_variations(ltx_storyboard_plan)
        ltx_storyboard_template_recommendations = storyboard_template_recommendations(ltx_storyboard_plan)
    except Exception as exc:
        ltx_storyboard = {
            "ready": False,
            "shot_count": 0,
            "error": str(exc),
            "claim_level": "ltx_inspired_local_shot_cards_not_ltx_cloud_parity",
        }
        ltx_storyboard_edit_plan = {"operations": [], "review_cards": [], "error": str(exc)}
        ltx_storyboard_apply_payload = {"timeline_markers": [], "sidecars": [], "render_queue_jobs": [], "error": str(exc)}
        ltx_storyboard_effect_materialization = {"ready": False, "zoom_windows": [], "callouts": [], "template_links": [], "error": str(exc)}
        ltx_storyboard_variations = {"ready": False, "variation_count": 0, "variations": [], "error": str(exc)}
        ltx_storyboard_template_recommendations = {"ready": False, "card_count": 0, "cards": [], "error": str(exc)}
    publish_variants = capcut_multi_platform_publish_plan(summary, media, target_count=target_count)
    markers = capcut_timeline_marker_rows(summary, target_count=target_count)
    ltx_markers = [
        dict(row)
        for row in _as_list(_as_dict(ltx_storyboard_apply_payload).get("timeline_markers"))
        if isinstance(row, Mapping)
    ]
    marker_seen = {
        (
            int(_as_dict(row).get("start_ms", _as_dict(row).get("ms", 0)) or 0),
            str(_as_dict(row).get("label") or _as_dict(row).get("id") or ""),
        )
        for row in markers
    }
    for marker in ltx_markers:
        key = (
            int(marker.get("start_ms", marker.get("ms", 0)) or 0),
            str(marker.get("label") or marker.get("id") or ""),
        )
        if key in marker_seen:
            continue
        marker.setdefault("color", "#8A7CFF")
        marker["source"] = "ltx_storyboard"
        marker["storyboard_marker"] = True
        markers.append(marker)
        marker_seen.add(key)
    jobs = capcut_short_export_jobs(
        summary,
        source_path=str(summary.get("source_path") or ""),
        project_path=str(summary.get("project_path") or ""),
        output_dir=str(summary.get("output_dir") or ""),
        platform=platform,
        target_count=target_count,
    )
    template_ids = [
        str(row.get("id"))
        for row in _as_list(recommendation.get("steps"))
        if str(row.get("kind") or "") == "template"
    ][:8]
    search_chips = []
    for record in index[:8]:
        for tag in _as_list(record.get("object_tags")) + _as_list(record.get("people")) + _as_list(record.get("tags")):
            if tag and tag not in search_chips:
                search_chips.append(str(tag))
    project_settings_patch = {
        "canvas_width": export["export_settings"]["canvas_width"],
        "canvas_height": export["export_settings"]["canvas_height"],
        "fps": export["export_settings"]["fps"],
        "starter_template_id": "vertical-shorts" if platform in {"shorts", "tiktok", "reels"} else "screen-recording-demo",
        "capcut_creator_workflow": {
            "enabled": True,
            "platform": export.get("platform"),
            "template_ids": template_ids,
            "caption_style_id": captions[0]["style_preset_id"] if captions else "caption-capcut-word-pop",
            "subject_reframe": reframe,
            "publish_package_ready": bool(publish_package.get("ready")),
            "edit_recipe_ready": bool(edit_recipe.get("ready")),
            "ltx_storyboard_ready": bool(ltx_storyboard.get("ready")),
            "ltx_storyboard_shots": int(ltx_storyboard.get("shot_count", 0) or 0),
            "ltx_storyboard_zoom_windows": int(_as_dict(_as_dict(ltx_storyboard_effect_materialization).get("counts")).get("zoom_windows", 0) or 0),
            "ltx_storyboard_callouts": int(_as_dict(_as_dict(ltx_storyboard_effect_materialization).get("counts")).get("callouts", 0) or 0),
            "ltx_storyboard_variations": int(_as_dict(ltx_storyboard_variations).get("variation_count", 0) or 0),
            "ltx_storyboard_template_recommendations": int(_as_dict(ltx_storyboard_template_recommendations).get("card_count", 0) or 0),
            "publish_variants": list(publish_variants.get("platforms") or []),
        },
    }
    bundle = {
        "ok": bool(template_ids or captions or jobs),
        "summary": summary,
        "project_settings_patch": project_settings_patch,
        "workflow_preset_ids": [str(row.get("id")) for row in _as_list(recommendation.get("steps"))[:16]],
        "subtitle_rows": captions,
        "caption_beat_plan": caption_beats,
        "hook_score_plan": hook_scores,
        "timeline_markers": markers,
        "render_queue_jobs": jobs,
        "smart_media_index": index,
        "search_chips": search_chips[:12],
        "export_settings": export.get("export_settings"),
        "publish_package": publish_package,
        "edit_recipe": edit_recipe,
        "ltx_storyboard": ltx_storyboard,
        "ltx_storyboard_edit_plan": ltx_storyboard_edit_plan,
        "ltx_storyboard_apply_payload": ltx_storyboard_apply_payload,
        "ltx_storyboard_effect_materialization": ltx_storyboard_effect_materialization,
        "ltx_storyboard_variations": ltx_storyboard_variations,
        "ltx_storyboard_template_recommendations": ltx_storyboard_template_recommendations,
        "publish_variants": publish_variants,
        "notes": [
            "subtitle_rows are compatible with app.subtitles.Subtitle plus style sidecar fields",
            "render_queue_jobs[*].create_kwargs can be passed directly to RenderQueueJob.create",
            "publish_package contains title/hashtag/thumbnail/checklist suggestions for creator delivery",
            "edit_recipe explains the one-click recommendation as reviewable edit steps",
            "ltx_storyboard contains local-first shot cards inspired by LTX Studio; it is not LTX cloud parity",
        ],
    }
    bundle["publish_handoff"] = capcut_publish_handoff_plan(bundle)
    if include_review_panel:
        bundle["review_panel"] = capcut_creator_review_panel_model(bundle)
    return bundle


def capcut_publish_handoff_plan(bundle_or_package: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return UI-ready copy/export handoff actions for CapCut publish metadata."""
    payload = _as_dict(bundle_or_package)
    package = _as_dict(payload.get("publish_package")) if "publish_package" in payload else payload
    variants = _as_dict(payload.get("publish_variants"))
    title = str((_as_list(package.get("title_suggestions")) or [""])[0] or "")
    hashtags = [str(item) for item in _as_list(package.get("hashtags")) if str(item).strip()]
    description_template = str(package.get("description_template") or "{title}\n\n{hashtags}")
    description = description_template.replace("{title}", title).replace("{hashtags}", " ".join(hashtags))
    thumbnail = _as_dict((_as_list(package.get("thumbnail_frames")) or [{}])[0])
    variant_rows = _as_list(variants.get("variants"))
    platforms = [str(row.get("platform") or "") for row in variant_rows if isinstance(row, Mapping)]
    if not platforms and package.get("platform"):
        platforms = [str(package.get("platform"))]
    clipboard_payloads = {
        "title": title,
        "description": description,
        "hashtags": " ".join(hashtags),
        "thumbnail_ms": int(thumbnail.get("ms", 0) or 0),
    }
    actions = [
        {"id": "copy_title", "label": "Copy title", "enabled": bool(title), "payload_key": "title"},
        {"id": "copy_description", "label": "Copy description", "enabled": bool(description.strip()), "payload_key": "description"},
        {"id": "copy_hashtags", "label": "Copy hashtags", "enabled": bool(hashtags), "payload_key": "hashtags"},
        {"id": "jump_thumbnail", "label": "Jump to thumbnail frame", "enabled": bool(thumbnail.get("ms") is not None), "ms": int(thumbnail.get("ms", 0) or 0)},
        {"id": "queue_short_exports", "label": "Queue short exports", "enabled": True, "platforms": platforms},
    ]
    return {
        "ok": True,
        "ready": bool(title and hashtags and package.get("ready")),
        "platforms": platforms,
        "clipboard_payloads": clipboard_payloads,
        "actions": actions,
        "action_count": len(actions),
        "thumbnail_frame": thumbnail,
        "missing": [key for key, value in clipboard_payloads.items() if key != "thumbnail_ms" and not str(value).strip()],
    }


def capcut_creator_review_panel_model(
    bundle_or_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
    *,
    platform: str = "shorts",
    target_count: int = 3,
) -> dict[str, Any]:
    """Build the data model for a CapCut-style creator review panel."""
    source = _as_dict(bundle_or_summary)
    if any(key in source for key in ("project_settings_patch", "edit_recipe", "publish_package", "render_queue_jobs")):
        bundle = source
    else:
        bundle = capcut_creator_apply_bundle(source, media_items, platform=platform, target_count=target_count)
    summary = _as_dict(bundle.get("summary"))
    recipe = _as_dict(bundle.get("edit_recipe"))
    publish = _as_dict(bundle.get("publish_package"))
    variants = _as_dict(bundle.get("publish_variants"))
    hooks = _as_dict(bundle.get("hook_score_plan"))
    captions = _as_dict(bundle.get("caption_beat_plan"))
    ltx_storyboard = _as_dict(bundle.get("ltx_storyboard"))
    ltx_storyboard_effect_materialization = _as_dict(bundle.get("ltx_storyboard_effect_materialization"))
    ltx_storyboard_variations = _as_dict(bundle.get("ltx_storyboard_variations"))
    ltx_storyboard_template_recommendations = _as_dict(bundle.get("ltx_storyboard_template_recommendations"))
    markers = _as_list(bundle.get("timeline_markers"))
    jobs = _as_list(bundle.get("render_queue_jobs"))
    media_index = _as_list(bundle.get("smart_media_index"))
    search_chips = [str(item) for item in _as_list(bundle.get("search_chips"))]
    handoff = capcut_publish_handoff_plan(bundle)
    try:
        from app.capcut_publish import capcut_publish_review_model

        publish_review = capcut_publish_review_model({**dict(bundle), "publish_handoff": handoff})
    except Exception as exc:
        publish_review = {
            "ok": False,
            "ready": False,
            "error": str(exc),
            "summary": {},
            "cards": [],
            "providers": [],
        }
    try:
        from app.capcut_quick_result import capcut_quick_result_model

        quick_result = capcut_quick_result_model({**dict(bundle), "publish_handoff": handoff})
    except Exception as exc:
        quick_result = {
            "ok": False,
            "ready": False,
            "score": 0,
            "error": str(exc),
            "cards": [],
            "summary": {},
        }
    try:
        from app.capcut_voice import capcut_voice_workflow_model

        voice_workflow = capcut_voice_workflow_model({**dict(bundle), "publish_handoff": handoff})
    except Exception as exc:
        voice_workflow = {
            "ok": False,
            "ready": False,
            "score": 0,
            "error": str(exc),
            "cards": [],
            "summary": {},
            "providers": [],
        }
    try:
        from app.capcut_prompt_edit import capcut_prompt_to_edit_plan

        prompt_edit = capcut_prompt_to_edit_plan(
            str(summary.get("creator_prompt") or "Make this into a polished CapCut-style short with captions and publish handoff."),
            summary,
            media_index,
        )
    except Exception as exc:
        prompt_edit = {
            "ok": False,
            "operation_count": 0,
            "ready_operation_count": 0,
            "operations": [],
            "explainability": [],
            "error": str(exc),
        }
    try:
        from app.capcut_collaboration import capcut_collab_review_model

        collab_handoff = capcut_collab_review_model({**dict(bundle), "publish_handoff": handoff}, media_index)
    except Exception as exc:
        collab_handoff = {
            "ok": False,
            "ready": False,
            "score": 0,
            "error": str(exc),
            "cards": [],
            "summary": {},
            "providers": [],
        }
    try:
        from app.ltx_storyboard import storyboard_review_panel_model

        ltx_storyboard_review = storyboard_review_panel_model(ltx_storyboard)
    except Exception as exc:
        ltx_storyboard_review = {
            "ok": False,
            "ready": False,
            "error": str(exc),
            "cards": [],
            "card_count": 0,
            "actions": [],
        }
    cards = [
        {
            "id": "overview",
            "kind": "hero",
            "label": "Creator plan",
            "ready": bool(bundle.get("ok")),
            "accent": "#FF6F61",
            "summary": f"{int(recipe.get('step_count', 0) or 0)} steps, {len(markers)} short range(s), {len(jobs)} export job(s)",
            "primary_action": "apply_creator_recipe",
        },
        {
            "id": "quick_result",
            "kind": "quick_result",
            "label": "Quick result",
            "ready": bool(quick_result.get("ready")),
            "accent": "#FFDD55",
            "summary": (
                f"{quick_result.get('score', 0)} quality, "
                f"{_as_dict(quick_result.get('summary')).get('ready_actions', 0)} ready action(s)"
            ),
            "rows": list(_as_list(quick_result.get("cards"))),
            "recommendation": _as_dict(quick_result.get("recommendation")),
        },
        {
            "id": "recipe",
            "kind": "steps",
            "label": "Edit recipe",
            "ready": bool(recipe.get("ready")),
            "accent": "#7B61FF",
            "summary": f"{int(recipe.get('step_count', 0) or 0)} explained step(s)",
            "rows": list(_as_list(recipe.get("steps"))),
        },
        {
            "id": "shorts",
            "kind": "timeline",
            "label": "Short candidates",
            "ready": bool(markers),
            "accent": "#FFB84D",
            "summary": f"{len(markers)} candidate range(s)",
            "rows": markers,
        },
        {
            "id": "captions",
            "kind": "caption_beats",
            "label": "Caption beats",
            "ready": bool(captions.get("ready")),
            "accent": "#5BE7C4",
            "summary": f"{int(captions.get('beat_count', 0) or 0)} beat(s), {captions.get('default_style_id', '')}",
            "rows": list(_as_list(captions.get("beats"))),
        },
        {
            "id": "voice_workflow",
            "kind": "voice_workflow",
            "label": "Voice workflow",
            "ready": bool(voice_workflow.get("ready")),
            "accent": "#5BE7C4",
            "summary": (
                f"{int(_as_dict(voice_workflow.get('summary')).get('subtitle_rows', 0) or 0)} caption row(s), "
                f"{int(_as_dict(voice_workflow.get('summary')).get('configured_provider_count', 0) or 0)} local provider(s)"
            ),
            "rows": list(_as_list(voice_workflow.get("cards"))),
            "actions": list(_as_list(voice_workflow.get("actions"))),
        },
        {
            "id": "prompt_edit",
            "kind": "prompt_edit",
            "label": "Prompt Edit",
            "ready": bool(prompt_edit.get("ok")),
            "accent": "#5BE7D1",
            "summary": (
                f"{int(prompt_edit.get('ready_operation_count', 0) or 0)}/"
                f"{int(prompt_edit.get('operation_count', 0) or 0)} operation(s) ready"
            ),
            "rows": list(_as_list(prompt_edit.get("explainability"))),
            "actions": [
                {"id": "preview_prompt_edit", "label": "Preview prompt plan", "enabled": bool(prompt_edit.get("operations"))},
                {"id": "apply_prompt_edit_review", "label": "Review apply", "enabled": bool(prompt_edit.get("ok"))},
            ],
        },
        {
            "id": "ltx_storyboard",
            "kind": "ltx_storyboard",
            "label": "샷카드",
            "ready": bool(ltx_storyboard_review.get("ready")),
            "accent": "#8A7CFF",
            "summary": (
                f"{int(ltx_storyboard_review.get('card_count', 0) or 0)}개 샷카드 준비 · "
                f"줌 {int(_as_dict(ltx_storyboard_effect_materialization.get('counts')).get('zoom_windows', 0) or 0)}개 · "
                f"콜아웃 {int(_as_dict(ltx_storyboard_effect_materialization.get('counts')).get('callouts', 0) or 0)}개 · "
                f"리테이크 {int(ltx_storyboard_variations.get('variation_count', 0) or 0)}개 · "
                f"템플릿 {int(ltx_storyboard_template_recommendations.get('card_count', 0) or 0)}개"
            ),
            "rows": list(_as_list(ltx_storyboard_review.get("cards"))),
            "actions": [
                *list(_as_list(ltx_storyboard_review.get("actions"))),
                {
                    "id": "apply_ltx_storyboard_effects",
                    "label": "줌/콜아웃 적용 준비",
                    "enabled": bool(ltx_storyboard_effect_materialization.get("ready")),
                    "zoom_windows": int(_as_dict(ltx_storyboard_effect_materialization.get("counts")).get("zoom_windows", 0) or 0),
                    "callouts": int(_as_dict(ltx_storyboard_effect_materialization.get("counts")).get("callouts", 0) or 0),
                },
                {"id": "apply_ltx_storyboard_camera", "label": "카메라/줌 사이드카 준비", "enabled": bool(_as_list(_as_dict(bundle.get("ltx_storyboard_apply_payload")).get("sidecars")))},
                {"id": "open_ltx_template_recommendations", "label": "추천 템플릿 확인", "enabled": bool(ltx_storyboard_template_recommendations.get("ready"))},
            ],
            "claim_level": ltx_storyboard.get("claim_level", "ltx_inspired_local_shot_cards_not_ltx_cloud_parity"),
            "effect_materialization": ltx_storyboard_effect_materialization,
            "variations": list(_as_list(ltx_storyboard_variations.get("variations"))),
            "template_recommendations": list(_as_list(ltx_storyboard_template_recommendations.get("cards"))),
        },
        {
            "id": "hooks",
            "kind": "ranking",
            "label": "Hook ranking",
            "ready": bool(hooks.get("ready")),
            "accent": "#FFDD55",
            "summary": f"{len(_as_list(hooks.get('hooks')))} hook candidate(s)",
            "rows": list(_as_list(hooks.get("hooks"))),
        },
        {
            "id": "publish",
            "kind": "delivery",
            "label": "Publish variants",
            "ready": bool(variants.get("ready")),
            "accent": "#6EA8FF",
            "summary": f"{int(variants.get('variant_count', 0) or 0)} platform variant(s)",
            "rows": list(_as_list(variants.get("variants"))),
            "handoff": handoff,
        },
        {
            "id": "publish_review",
            "kind": "publish_review",
            "label": "Publish review",
            "ready": bool(publish_review.get("ready")),
            "accent": "#FF6F61",
            "summary": (
                f"{int(_as_dict(publish_review.get('summary')).get('ready_platforms', 0) or 0)} ready platform(s), "
                f"{int(publish_review.get('configured_provider_count', 0) or 0)} provider(s)"
            ),
            "rows": list(_as_list(publish_review.get("cards"))),
            "providers": list(_as_list(publish_review.get("providers"))),
            "warnings": list(_as_list(publish_review.get("warnings"))),
        },
        {
            "id": "collab_handoff",
            "kind": "collab_handoff",
            "label": "Collab handoff",
            "ready": bool(collab_handoff.get("ready")),
            "accent": "#8A7CFF",
            "summary": (
                f"{int(_as_dict(collab_handoff.get('summary')).get('media_count', 0) or 0)} media item(s), "
                f"{int(_as_dict(collab_handoff.get('summary')).get('configured_provider_count', 0) or 0)} local provider(s)"
            ),
            "rows": list(_as_list(collab_handoff.get("cards"))),
            "actions": list(_as_list(collab_handoff.get("actions"))),
        },
        {
            "id": "media_search",
            "kind": "search",
            "label": "Smart media",
            "ready": bool(media_index or search_chips),
            "accent": "#B46CFF",
            "summary": f"{len(media_index)} indexed item(s), {len(search_chips)} chip(s)",
            "rows": media_index[:8],
            "chips": search_chips[:12],
        },
    ]
    ready_cards = [card for card in cards if card.get("ready")]
    actions = [
        {"id": "apply_creator_recipe", "label": "Apply creator plan", "enabled": bool(bundle.get("ok") and recipe.get("ready")), "primary": True},
        {"id": "preview_best_short", "label": "Preview best short", "enabled": bool(markers), "ms": int(_as_dict(markers[0] if markers else {}).get("start_ms", 0) or 0)},
        {"id": "queue_render_jobs", "label": "Queue render jobs", "enabled": bool(jobs), "count": len(jobs)},
        {"id": "copy_publish_copy", "label": "Copy publish copy", "enabled": bool(handoff.get("ready")), "payload_keys": list(_as_dict(handoff.get("clipboard_payloads")).keys())},
        {"id": "open_template_browser", "label": "Open matching templates", "enabled": bool(bundle.get("workflow_preset_ids")), "count": len(_as_list(bundle.get("workflow_preset_ids")))},
    ]
    missing_inputs = list(_as_list(recipe.get("missing_inputs")))
    return {
        "ok": True,
        "ready": len(ready_cards) >= 5 and not missing_inputs,
        "card_count": len(cards),
        "ready_card_count": len(ready_cards),
        "cards": cards,
        "actions": actions,
        "primary_action": actions[0],
        "review_points": list(_as_list(recipe.get("review_points"))),
        "publish_handoff": handoff,
        "publish_review": publish_review,
        "quick_result": quick_result,
        "voice_workflow": voice_workflow,
        "prompt_edit": prompt_edit,
        "ltx_storyboard": ltx_storyboard_review,
        "collab_handoff": collab_handoff,
        "missing_inputs": missing_inputs,
        "counts": {
            "recipe_steps": int(recipe.get("step_count", 0) or 0),
            "short_candidates": len(markers),
            "caption_beats": int(captions.get("beat_count", 0) or 0),
            "hook_candidates": len(_as_list(hooks.get("hooks"))),
            "publish_variants": int(variants.get("variant_count", 0) or 0),
            "publish_review_cards": int(publish_review.get("card_count", 0) or 0),
            "publish_providers": int(publish_review.get("provider_count", 0) or 0),
            "quick_result_cards": int(quick_result.get("card_count", 0) or 0),
            "quick_result_score": float(quick_result.get("score", 0) or 0),
            "voice_workflow_cards": int(voice_workflow.get("card_count", 0) or 0),
            "voice_workflow_score": float(voice_workflow.get("score", 0) or 0),
            "voice_providers": int(voice_workflow.get("provider_count", 0) or 0),
            "prompt_edit_operations": int(prompt_edit.get("operation_count", 0) or 0),
            "prompt_edit_ready_operations": int(prompt_edit.get("ready_operation_count", 0) or 0),
            "ltx_storyboard_shots": int(ltx_storyboard_review.get("card_count", 0) or 0),
            "ltx_storyboard_ready": 1 if bool(ltx_storyboard_review.get("ready")) else 0,
            "ltx_storyboard_zoom_windows": int(_as_dict(ltx_storyboard_effect_materialization.get("counts")).get("zoom_windows", 0) or 0),
            "ltx_storyboard_callouts": int(_as_dict(ltx_storyboard_effect_materialization.get("counts")).get("callouts", 0) or 0),
            "ltx_storyboard_variations": int(ltx_storyboard_variations.get("variation_count", 0) or 0),
            "ltx_storyboard_template_recommendations": int(ltx_storyboard_template_recommendations.get("card_count", 0) or 0),
            "collab_handoff_cards": int(collab_handoff.get("card_count", 0) or 0),
            "collab_handoff_score": float(collab_handoff.get("score", 0) or 0),
            "collab_providers": int(collab_handoff.get("provider_count", 0) or 0),
            "render_jobs": len(jobs),
            "smart_media_items": len(media_index),
        },
    }


def capcut_quick_create_button_model(bundle: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Summarize the one-click creator flow exposed inside the editor panel."""
    data = dict(bundle or {})
    panel = _as_dict(data.get("review_panel"))
    counts = _as_dict(panel.get("counts"))
    subtitle_count = len(_as_list(data.get("subtitle_rows")))
    marker_count = len(_as_list(data.get("timeline_markers")))
    queue_count = len(_as_list(data.get("render_queue_jobs")))
    handoff = _as_dict(data.get("publish_handoff"))
    settings_ready = bool(_as_dict(data.get("project_settings_patch")) or _as_dict(data.get("export_settings")))
    copy_ready = bool(_as_dict(handoff.get("clipboard_payloads")).get("title"))
    quick_result = _as_dict(panel.get("quick_result") or data.get("quick_result"))
    quick_quality_score = float(
        quick_result.get("score")
        or _as_dict(quick_result.get("summary")).get("quality_score")
        or counts.get("quick_result_score")
        or 0
    )
    steps = [
        {
            "id": "analyze",
            "label": "Analyze project/media",
            "ready": bool(data.get("ok") or panel.get("ready")),
            "summary": f"{int(counts.get('recipe_steps', 0) or 0)} recipe step(s)",
        },
        {
            "id": "apply_edit",
            "label": "Apply captions, shorts, and output settings",
            "ready": bool(subtitle_count or marker_count or settings_ready),
            "summary": f"{subtitle_count} subtitle(s), {marker_count} marker(s)",
        },
        {
            "id": "queue_exports",
            "label": "Queue social exports",
            "ready": bool(queue_count),
            "summary": f"{queue_count} render job(s)",
        },
        {
            "id": "publish_copy",
            "label": "Prepare publish copy",
            "ready": copy_ready,
            "summary": "title/description/hashtags" if copy_ready else "publish copy pending",
        },
    ]
    enabled = bool(data.get("ok") and steps[1]["ready"])
    return {
        "ok": True,
        "enabled": enabled,
        "label": "Quick Create",
        "description": "Analyze, apply creator edits, queue exports, and prepare publish copy from the current editor state.",
        "primary_action": {
            "id": "quick_create",
            "label": "Quick Create",
            "enabled": enabled,
        },
        "options": {
            "subtitles": subtitle_count > 0,
            "markers": marker_count > 0,
            "settings": settings_ready,
            "queue_exports": queue_count > 0,
            "publish_copy": copy_ready,
        },
        "steps": steps,
        "summary": {
            "subtitles": subtitle_count,
            "markers": marker_count,
            "render_jobs": queue_count,
            "settings_ready": settings_ready,
            "publish_copy_ready": copy_ready,
            "quick_result_score": quick_quality_score,
            "ready_steps": sum(1 for step in steps if step.get("ready")),
        },
    }


def capcut_creator_bundle_from_local_media(
    media_path: str | Path,
    *,
    platform: str = "shorts",
    target_count: int = 3,
    include_transcript: bool = False,
    sample_count: int = 8,
) -> dict[str, Any]:
    """Analyze a local media file and return a CapCut-style apply bundle.

    This is the local-ML bridge: it uses ``app.local_ml`` to create the same
    project/media summary shape that the deterministic CapCut planners already
    understand.  Optional heavyweight models are never downloaded here.
    """
    from app.capcut_features import capcut_disabled_reason, capcut_feature_disabled
    from app.local_ml import local_ml_capcut_project_summary

    if capcut_feature_disabled("local_ml"):
        return {
            "ok": False,
            "disabled": True,
            "reason": capcut_disabled_reason("local_ml"),
            "source_path": str(Path(media_path)),
            "local_ml_analysis": {
                "ok": False,
                "disabled": True,
                "reason": "local_ml_feature_gate_disabled",
                "cloud_enabled": False,
            },
            "local_ml_backend_status": {
                "ok": True,
                "mode": "disabled",
                "disabled": True,
                "cloud_enabled": False,
                "api_required": False,
            },
            "notes": [capcut_disabled_reason("local_ml")],
            "project_settings_patch": {},
            "workflow_preset_ids": [],
            "search_chips": [],
        }

    summary = local_ml_capcut_project_summary(
        media_path,
        include_transcript=include_transcript,
        sample_count=sample_count,
    )
    media = _as_list(summary.get("media_items"))
    bundle = capcut_creator_apply_bundle(
        summary,
        media,
        platform=platform,
        target_count=target_count,
    )
    notes = list(_as_list(bundle.get("notes")))
    notes.append("local_ml_analysis is local-only; no cloud API or model download is used.")
    bundle.update(
        {
            "local_ml_analysis": _as_dict(summary.get("local_ml_analysis")),
            "local_ml_backend_status": _as_dict(summary.get("local_ml_backend_status")),
            "notes": notes,
        }
    )
    return bundle


def capcut_ai_recommendation_plan(project_summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    summary = normalize_project_summary(project_summary)
    try:
        from app.preset_library import one_click_preset_plan
    except Exception:
        plan_presets = []
    else:
        plan_presets = one_click_preset_plan({
            **summary,
            "capcut": True,
            "shortform": True if summary.get("shortform") or summary.get("needs_shorts") else summary.get("shortform", False),
            "dialogue": summary.get("dialogue", False),
            "screen_recording": summary.get("screen_recording", False),
        })
    steps = [
        {"id": preset.id, "kind": preset.kind, "name": preset.name, "tags": list(preset.tags)}
        for preset in plan_presets
    ]
    return {
        "ok": bool(steps),
        "summary": summary,
        "steps": steps,
        "step_count": len(steps),
        "first_template": next((row for row in steps if row["kind"] == "template"), None),
        "caption": capcut_auto_caption_plan(summary),
        "shorts": capcut_long_to_shorts_plan(summary),
        "reframe": capcut_subject_reframe_plan(summary),
        "voice": capcut_voice_tool_plan(summary),
        "background": capcut_background_removal_plan(summary),
        "export": capcut_social_export_plan(summary, platform="shorts"),
        "publish_package": capcut_publish_package_plan(summary, platform="shorts"),
        "edit_recipe": capcut_creator_edit_recipe(summary, platform="shorts"),
        "publish_variants": capcut_multi_platform_publish_plan(summary),
    }


def capcut_creator_workflow_report(
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    summary = normalize_project_summary(project_summary)
    media = list(media_items if media_items is not None else _as_list(summary.get("media_items")))
    index = capcut_smart_media_index(media)
    sample_hits = capcut_smart_media_search(index, "cursor gameplay")[:3]
    if not sample_hits:
        sample_hits = [dict(row, score=0) for row in index[:3]]
    recommendation = capcut_ai_recommendation_plan(summary)
    apply_bundle = capcut_creator_apply_bundle(summary, media)
    publish_package = capcut_publish_package_plan(summary, media)
    review_panel = capcut_creator_review_panel_model(apply_bundle)
    publish_handoff = capcut_publish_handoff_plan(apply_bundle)
    quick_create = capcut_quick_create_button_model(
        {
            **dict(apply_bundle),
            "review_panel": review_panel,
            "publish_handoff": publish_handoff,
        }
    )
    apply_simulation: dict[str, Any] = {}
    try:
        from app.capcut_apply import (
            capcut_apply_bundle_to_project,
            capcut_apply_preview,
            capcut_render_queue_jobs_from_payload,
        )

        base_doc = {
            "project_settings": dict(_as_dict(summary.get("project_settings"))),
            "video_tracks": list(_as_list(summary.get("video_tracks"))),
            "audio_tracks": list(_as_list(summary.get("audio_tracks"))),
            "subtitles": list(_as_list(summary.get("subtitles") or summary.get("captions"))),
            "timeline_markers": list(_as_list(summary.get("timeline_markers"))),
        }
        preview = capcut_apply_preview(base_doc, apply_bundle)
        applied = capcut_apply_bundle_to_project(base_doc, apply_bundle)
        queue_jobs = capcut_render_queue_jobs_from_payload(applied.project_doc)
        apply_simulation = {
            "ok": bool(applied.ok),
            "preview": preview,
            "counts": dict(applied.counts),
            "operations": list(applied.operations),
            "warnings": list(applied.warnings),
            "materialized_render_queue_jobs": len(queue_jobs),
        }
    except Exception as exc:
        apply_simulation = {
            "ok": False,
            "error": str(exc),
        }
    checks: dict[str, dict[str, Any]] = {
        "auto_captions": capcut_auto_caption_plan(summary),
        "long_to_shorts": capcut_long_to_shorts_plan(summary),
        "smart_media_search": {
            "ok": True,
            "indexed": len(index),
            "sample_hits": sample_hits,
        },
        "template_ecosystem": {
            "ok": bool(recommendation.get("steps")),
            "step_count": int(recommendation.get("step_count", 0) or 0),
            "first_template": recommendation.get("first_template"),
        },
        "subject_reframe": capcut_subject_reframe_plan(summary),
        "keyframe_graphs": capcut_keyframe_graph_plan("hook"),
        "voice_tools": capcut_voice_tool_plan(summary),
        "background_removal": capcut_background_removal_plan(summary),
        "social_exports": capcut_social_export_plan(summary),
        "ai_recommendations": recommendation,
    }
    areas: list[dict[str, Any]] = []
    score = 0
    for area in CAPCUT_CREATOR_AREAS:
        check = checks.get(area.id, {})
        ok = bool(check.get("ok", False))
        area_score = 100 if ok else 65
        if area.id == "smart_media_search" and int(check.get("indexed", 0) or 0) == 0:
            area_score = 90
        if area.id == "auto_captions" and not bool(check.get("ready_for_apply", True)):
            area_score = 88
        score += area_score
        areas.append({
            "id": area.id,
            "label": area.label,
            "ok": ok,
            "score": area_score,
            "user_value": area.user_value,
            "evidence": area.evidence,
            "detail": check,
        })
    average = round(score / max(1, len(CAPCUT_CREATOR_AREAS)), 2)
    return {
        "ok": average >= 85 and bool(recommendation.get("steps")),
        "score": average,
        "summary": {
            "areas": len(CAPCUT_CREATOR_AREAS),
            "duration_s": summary.get("duration_s", 0.0),
            "media_count": len(media),
            "recommendation_steps": recommendation.get("step_count", 0),
            "subtitle_rows": len(apply_bundle.get("subtitle_rows", []) or []),
            "render_queue_jobs": len(apply_bundle.get("render_queue_jobs", []) or []),
            "timeline_markers": len(apply_bundle.get("timeline_markers", []) or []),
            "hook_candidates": len(_as_list(apply_bundle.get("hook_score_plan", {}).get("hooks") if isinstance(apply_bundle.get("hook_score_plan"), dict) else [])),
            "caption_beats": int(_as_dict(apply_bundle.get("caption_beat_plan")).get("beat_count", 0) or 0),
            "publish_package_ready": bool(_as_dict(apply_bundle.get("publish_package")).get("ready")),
            "publish_checklist_items": len(_as_list(_as_dict(apply_bundle.get("publish_package")).get("checklist"))),
            "edit_recipe_steps": int(_as_dict(apply_bundle.get("edit_recipe")).get("step_count", 0) or 0),
            "publish_variants": int(_as_dict(apply_bundle.get("publish_variants")).get("variant_count", 0) or 0),
            "review_panel_cards": int(review_panel.get("card_count", 0) or 0),
            "review_panel_actions": len(_as_list(review_panel.get("actions"))),
            "review_panel_ready": bool(review_panel.get("ready")),
            "publish_review_cards": int(_as_dict(_as_dict(review_panel.get("counts"))).get("publish_review_cards", 0) or 0),
            "publish_providers": int(_as_dict(_as_dict(review_panel.get("counts"))).get("publish_providers", 0) or 0),
            "quick_result_cards": int(_as_dict(_as_dict(review_panel.get("counts"))).get("quick_result_cards", 0) or 0),
            "quick_result_score": float(_as_dict(_as_dict(review_panel.get("counts"))).get("quick_result_score", 0) or 0),
            "voice_workflow_cards": int(_as_dict(_as_dict(review_panel.get("counts"))).get("voice_workflow_cards", 0) or 0),
            "voice_workflow_score": float(_as_dict(_as_dict(review_panel.get("counts"))).get("voice_workflow_score", 0) or 0),
            "voice_providers": int(_as_dict(_as_dict(review_panel.get("counts"))).get("voice_providers", 0) or 0),
            "prompt_edit_operations": int(_as_dict(_as_dict(review_panel.get("counts"))).get("prompt_edit_operations", 0) or 0),
            "prompt_edit_ready_operations": int(_as_dict(_as_dict(review_panel.get("counts"))).get("prompt_edit_ready_operations", 0) or 0),
            "ltx_storyboard_shots": int(_as_dict(_as_dict(review_panel.get("counts"))).get("ltx_storyboard_shots", 0) or 0),
            "ltx_storyboard_ready": bool(_as_dict(_as_dict(review_panel.get("counts"))).get("ltx_storyboard_ready", 0) or 0),
            "ltx_storyboard_zoom_windows": int(_as_dict(_as_dict(review_panel.get("counts"))).get("ltx_storyboard_zoom_windows", 0) or 0),
            "ltx_storyboard_callouts": int(_as_dict(_as_dict(review_panel.get("counts"))).get("ltx_storyboard_callouts", 0) or 0),
            "ltx_storyboard_variations": int(_as_dict(_as_dict(review_panel.get("counts"))).get("ltx_storyboard_variations", 0) or 0),
            "ltx_storyboard_template_recommendations": int(_as_dict(_as_dict(review_panel.get("counts"))).get("ltx_storyboard_template_recommendations", 0) or 0),
            "collab_handoff_cards": int(_as_dict(_as_dict(review_panel.get("counts"))).get("collab_handoff_cards", 0) or 0),
            "collab_handoff_score": float(_as_dict(_as_dict(review_panel.get("counts"))).get("collab_handoff_score", 0) or 0),
            "collab_providers": int(_as_dict(_as_dict(review_panel.get("counts"))).get("collab_providers", 0) or 0),
            "publish_handoff_actions": int(publish_handoff.get("action_count", 0) or 0),
            "publish_handoff_ready": bool(publish_handoff.get("ready")),
            "quick_create_ready": bool(quick_create.get("enabled")),
            "quick_create_steps": int(_as_dict(quick_create.get("summary")).get("ready_steps", 0) or 0),
            "applied_subtitles": int(_as_dict(apply_simulation.get("counts")).get("subtitles_added", 0) or 0),
            "applied_render_jobs": int(_as_dict(apply_simulation.get("counts")).get("render_queue_jobs_added", 0) or 0),
            "materialized_render_queue_jobs": int(apply_simulation.get("materialized_render_queue_jobs", 0) or 0),
        },
        "areas": areas,
        "smart_media_index": index,
        "apply_bundle": {
            "ok": apply_bundle.get("ok"),
            "summary": apply_bundle.get("summary") or summary,
            "project_settings_patch": apply_bundle.get("project_settings_patch"),
            "workflow_preset_ids": apply_bundle.get("workflow_preset_ids"),
            "subtitle_rows": apply_bundle.get("subtitle_rows"),
            "timeline_markers": apply_bundle.get("timeline_markers"),
            "render_queue_jobs": apply_bundle.get("render_queue_jobs"),
            "search_chips": apply_bundle.get("search_chips"),
            "export_settings": apply_bundle.get("export_settings"),
            "hook_score_plan": apply_bundle.get("hook_score_plan"),
            "caption_beat_plan": apply_bundle.get("caption_beat_plan"),
            "publish_package": apply_bundle.get("publish_package"),
            "edit_recipe": apply_bundle.get("edit_recipe"),
            "ltx_storyboard": apply_bundle.get("ltx_storyboard"),
            "ltx_storyboard_edit_plan": apply_bundle.get("ltx_storyboard_edit_plan"),
            "ltx_storyboard_apply_payload": apply_bundle.get("ltx_storyboard_apply_payload"),
            "ltx_storyboard_effect_materialization": apply_bundle.get("ltx_storyboard_effect_materialization"),
            "ltx_storyboard_variations": apply_bundle.get("ltx_storyboard_variations"),
            "ltx_storyboard_template_recommendations": apply_bundle.get("ltx_storyboard_template_recommendations"),
            "publish_variants": apply_bundle.get("publish_variants"),
            "review_panel": review_panel,
            "publish_handoff": publish_handoff,
            "quick_create": quick_create,
        },
        "apply_simulation": apply_simulation,
        "publish_package": publish_package,
        "review_panel": review_panel,
        "publish_handoff": publish_handoff,
        "quick_create": quick_create,
    }
