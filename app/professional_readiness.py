"""Professional-readiness diagnostics for long-form editing projects.

The checks in this module are intentionally Qt-free.  They inspect a saved
project document and produce product-facing diagnostics for the areas where a
commercial NLE/audio/color workflow usually fails first: long-project
stability, preview/export parity, timeline edit integrity, color workflow
depth, and audio mix readiness.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _enabled(value: Any) -> bool:
    if not isinstance(value, dict):
        return bool(value)
    return bool(value.get("enabled", True))


def _clip_start(clip: dict[str, Any]) -> int:
    try:
        return int(clip.get("timeline_in_ms", clip.get("offset_ms", 0)) or 0)
    except Exception:
        return 0


def _video_clip_duration(clip: dict[str, Any]) -> int:
    try:
        source_in = int(clip.get("source_in_ms", 0) or 0)
        source_out = int(clip.get("source_out_ms", 0) or 0)
        if source_out > source_in:
            return source_out - source_in
        return max(0, int(clip.get("source_duration_ms", 0) or 0))
    except Exception:
        return 0


def _audio_clip_duration(clip: dict[str, Any]) -> int:
    try:
        trim_start = int(clip.get("trim_start_ms", 0) or 0)
        trim_end = int(clip.get("trim_end_ms", 0) or 0)
        duration = int(clip.get("duration_ms", 0) or 0)
        if trim_end > trim_start:
            return trim_end - trim_start
        return max(0, duration - trim_start)
    except Exception:
        return 0


def _issue(area: str, severity: str, message: str, action: str, **extra: Any) -> dict[str, Any]:
    row = {
        "area": area,
        "severity": severity,
        "message": message,
        "action": action,
    }
    row.update(extra)
    return row


def _score_from_issues(issues: Iterable[dict[str, Any]]) -> int:
    score = 100
    for issue in issues:
        severity = str(issue.get("severity") or "")
        if severity == "high":
            score -= 18
        elif severity == "medium":
            score -= 8
        elif severity == "low":
            score -= 3
    return max(0, min(100, score))


def _video_clips(doc: dict[str, Any]) -> list[tuple[int, dict[str, Any], int]]:
    rows: list[tuple[int, dict[str, Any], int]] = []

    def walk(clips: list[Any], track_idx: int, depth: int) -> None:
        for raw in clips:
            if not isinstance(raw, dict):
                continue
            rows.append((track_idx, raw, depth))
            for child in _as_list(raw.get("nested_child_clips")):
                walk([child], track_idx, depth + 1)
            for child_track in _as_list(raw.get("nested_child_tracks")):
                walk(_as_list(child_track), track_idx, depth + 1)

    for track_idx, track in enumerate(_as_list(doc.get("video_tracks"))):
        if isinstance(track, dict):
            walk(_as_list(track.get("clips")), track_idx, 0)
    return rows


def _audio_clips(doc: dict[str, Any]) -> list[tuple[int, dict[str, Any], int]]:
    rows: list[tuple[int, dict[str, Any], int]] = []
    for track_idx, track in enumerate(_as_list(doc.get("audio_tracks"))):
        if not isinstance(track, dict):
            continue
        for clip in _as_list(track.get("clips")):
            if isinstance(clip, dict):
                rows.append((track_idx, clip, 0))
    for _track_idx, clip, _depth in _video_clips(doc):
        for lane_idx, lane in enumerate(_as_list(clip.get("nested_audio_tracks"))):
            for child in _as_list(lane):
                if isinstance(child, dict):
                    rows.append((lane_idx, child, 1))
    return rows


def _actor_clip_count(doc: dict[str, Any]) -> int:
    count = 0
    for key in ("spine_actor_tracks", "live2d_actor_tracks"):
        for track in _as_list(doc.get(key)):
            count += len(_as_list(_as_dict(track).get("clips")))
    for _track_idx, clip, _depth in _video_clips(doc):
        for key in ("nested_spine_actor_tracks", "nested_live2d_actor_tracks"):
            for track in _as_list(clip.get(key)):
                count += len(_as_list(_as_dict(track).get("clips")))
    return count


def _project_duration_ms(doc: dict[str, Any]) -> int:
    end_ms = 0
    for _track_idx, clip, _depth in _video_clips(doc):
        end_ms = max(end_ms, _clip_start(clip) + _video_clip_duration(clip))
    for _track_idx, clip, _depth in _audio_clips(doc):
        end_ms = max(end_ms, _clip_start(clip) + _audio_clip_duration(clip))
    for key in ("spine_actor_tracks", "live2d_actor_tracks"):
        for track in _as_list(doc.get(key)):
            for clip in _as_list(_as_dict(track).get("clips")):
                if isinstance(clip, dict):
                    end_ms = max(
                        end_ms,
                        int(clip.get("start_ms", 0) or 0) + int(clip.get("duration_ms", 0) or 0),
                    )
    return end_ms


def _actor_corpus_status(doc: dict[str, Any]) -> dict[str, Any]:
    """Return optional actor corpus QA status embedded by Health/QA tooling."""
    project_settings = _as_dict(doc.get("project_settings"))
    status = doc.get("actor_corpus_status") or doc.get("actor_qa_status")
    if not isinstance(status, dict):
        status = project_settings.get("actor_corpus_status") or project_settings.get("actor_qa_status")
    return _as_dict(status)


def _clip_effect_counts(doc: dict[str, Any]) -> Counter:
    counts: Counter = Counter()
    for _track_idx, clip, _depth in _video_clips(doc):
        if _enabled(clip.get("video_filters")):
            counts["video_filters"] += 1
        if _enabled(clip.get("chroma_key")):
            counts["chroma_key"] += 1
        if _enabled(clip.get("bg_removal")):
            counts["background_removal"] += 1
        if _enabled(clip.get("stabilizer")):
            counts["stabilizer"] += 1
        masks = _as_list(clip.get("masks"))
        counts["masks"] += len(masks)
        counts["tracked_masks"] += sum(1 for mask in masks if _as_dict(mask).get("track_object"))
        if clip.get("node_graph"):
            counts["node_graph"] += 1
        if clip.get("nested_sequence_id") or clip.get("nested_child_tracks"):
            counts["nested_sequence"] += 1
    counts["actor_clips"] = _actor_clip_count(doc)
    return counts


def _is_active_lut_slot(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if not value.get("path"):
        return False
    try:
        strength = float(value.get("strength", 1.0) or 0.0)
    except Exception:
        strength = 0.0
    return _enabled(value) and strength > 0.0


def _payload_has_active_lut(payload: dict[str, Any]) -> bool:
    for name in ("input", "creative", "output"):
        if _is_active_lut_slot(payload.get(f"{name}_lut")):
            return True
        path = str(payload.get(f"{name}_lut_path", "") or "")
        if not path:
            continue
        try:
            strength = float(payload.get(f"{name}_lut_strength", 1.0) or 0.0)
        except Exception:
            strength = 0.0
        if strength > 0.0:
            return True
    return False


def _payload_has_primary_grade(payload: dict[str, Any]) -> bool:
    for key in (
        "brightness",
        "contrast",
        "saturation",
        "shadows_x",
        "shadows_y",
        "midtones_x",
        "midtones_y",
        "highlights_x",
        "highlights_y",
        "offset_x",
        "offset_y",
        "shadows_l",
        "midtones_l",
        "highlights_l",
        "offset_l",
    ):
        try:
            if abs(float(payload.get(key, 0) or 0.0)) > 0.001:
                return True
        except Exception:
            continue
    return False


def _color_management_summary(doc: dict[str, Any]) -> dict[str, Any]:
    settings = _as_dict(doc.get("project_settings"))
    payload = _as_dict(settings.get("color_management"))
    if not payload:
        return {
            "explicit": False,
            "input_space": "",
            "working_space": "",
            "output_space": "",
            "output_transfer": "",
            "view_transform": "",
            "hdr": False,
            "ocio_config": "",
            "preview_transform_enabled": False,
            "active_luts": {},
            "warnings": [],
            "errors": [],
        }
    try:
        from app.color_management import ColorManagementSettings, validate_color_management

        cm = ColorManagementSettings.from_dict(payload)
        validation = validate_color_management(cm)
        active_luts = {
            name: {
                "path": slot.path,
                "strength": float(slot.strength),
            }
            for name, slot in cm.active_luts()
        }
        return {
            "explicit": True,
            "input_space": cm.input_space,
            "input_transfer": cm.input_transfer,
            "working_space": cm.working_space,
            "output_space": cm.output_space,
            "output_transfer": cm.output_transfer,
            "view_transform": cm.view_transform,
            "hdr": bool(cm.is_hdr()),
            "ocio_config": cm.ocio_config_path,
            "preview_transform_enabled": bool(cm.preview_transform_enabled),
            "active_luts": active_luts,
            "warnings": list(validation.get("warnings", []) or []),
            "errors": list(validation.get("errors", []) or []),
        }
    except Exception:
        active_luts = {
            name: _as_dict(payload.get(f"{name}_lut"))
            for name in ("input", "creative", "output")
            if _is_active_lut_slot(payload.get(f"{name}_lut"))
        }
        output_transfer = str(payload.get("output_transfer", "") or "").lower()
        output_space = str(payload.get("output_space", "") or "").lower()
        return {
            "explicit": True,
            "input_space": str(payload.get("input_space", "") or ""),
            "input_transfer": str(payload.get("input_transfer", "") or ""),
            "working_space": str(payload.get("working_space", "") or ""),
            "output_space": str(payload.get("output_space", "") or ""),
            "output_transfer": str(payload.get("output_transfer", "") or ""),
            "view_transform": str(payload.get("view_transform", "") or ""),
            "hdr": bool(payload.get("hdr_mode")) or output_transfer in {"pq", "hlg"} or "2020" in output_space,
            "ocio_config": str(payload.get("ocio_config_path", "") or ""),
            "preview_transform_enabled": bool(payload.get("preview_transform_enabled", True)),
            "active_luts": active_luts,
            "warnings": [],
            "errors": [],
        }


def audit_long_project_stability(doc: dict[str, Any]) -> dict[str, Any]:
    video_count = len(_video_clips(doc))
    audio_count = len(_audio_clips(doc))
    actor_count = _actor_clip_count(doc)
    duration_ms = _project_duration_ms(doc)
    effects = _clip_effect_counts(doc)
    heavy_features = sum(
        int(effects.get(key, 0))
        for key in (
            "video_filters",
            "chroma_key",
            "background_removal",
            "stabilizer",
            "masks",
            "node_graph",
            "nested_sequence",
            "actor_clips",
        )
    )
    issues: list[dict[str, Any]] = []
    if duration_ms >= 60 * 60 * 1000:
        issues.append(_issue(
            "long_project_stability",
            "high",
            "Project duration is over one hour.",
            "Use QA baseline comparison, autosave recovery, proxy readiness, and segmented export checks before delivery.",
            duration_ms=duration_ms,
        ))
    elif duration_ms >= 20 * 60 * 1000:
        issues.append(_issue(
            "long_project_stability",
            "medium",
            "Project duration is long enough to expose cache and autosave edge cases.",
            "Run project QA with a previous baseline and keep recovery candidates before major edits.",
            duration_ms=duration_ms,
        ))
    if video_count + audio_count >= 500:
        issues.append(_issue(
            "long_project_stability",
            "high",
            "Timeline contains hundreds of clips.",
            "Keep thumbnail/proxy caches warm and run project repair/relink QA before export.",
            clip_count=video_count + audio_count,
        ))
    elif video_count + audio_count >= 150:
        issues.append(_issue(
            "long_project_stability",
            "medium",
            "Timeline is dense.",
            "Use timeline QA and baseline performance checks after large edit operations.",
            clip_count=video_count + audio_count,
        ))
    if heavy_features >= 80:
        issues.append(_issue(
            "long_project_stability",
            "high",
            "Many clips require expensive preview/export processing.",
            "Prefer proxies and pre-render heavy sections before final export.",
            heavy_feature_count=heavy_features,
        ))
    elif heavy_features >= 25:
        issues.append(_issue(
            "long_project_stability",
            "medium",
            "Project has enough heavy effects to stress preview caches.",
            "Run preview perf QA and watch decode/filter/actor stages.",
            heavy_feature_count=heavy_features,
        ))
    return {
        "score": _score_from_issues(issues),
        "duration_ms": duration_ms,
        "video_clips": video_count,
        "audio_clips": audio_count,
        "actor_clips": actor_count,
        "heavy_feature_count": heavy_features,
        "effect_counts": dict(effects),
        "issues": issues,
    }


def audit_gpu_preview_export_consistency(doc: dict[str, Any]) -> dict[str, Any]:
    effects = _clip_effect_counts(doc)
    actor_status = _actor_corpus_status(doc)
    color = audit_color_workflow_depth(doc)
    audio = audit_audio_mix_readiness(doc)
    color_counts = Counter(_as_dict(color.get("counts")))
    audio_counts = Counter(_as_dict(audio.get("counts")))
    color_management = _as_dict(color.get("color_management"))
    color_parity_features: dict[str, int] = {}
    if color_management.get("explicit"):
        color_parity_features["color_management"] = 1
    if color_management.get("hdr"):
        color_parity_features["hdr_metadata"] = 1
    if color_management.get("ocio_config") or str(color_management.get("working_space", "")).lower().startswith("aces"):
        color_parity_features["ocio_or_aces_transform"] = 1
    project_lut_count = int(color_counts.get("project_luts", 0))
    if project_lut_count:
        color_parity_features["project_luts"] = project_lut_count
    grade_lut_count = int(color_counts.get("grade_luts", 0))
    if grade_lut_count:
        color_parity_features["grade_luts"] = grade_lut_count
    secondary_count = int(color_counts.get("qualifiers", 0)) + int(color_counts.get("power_windows", 0))
    if secondary_count:
        color_parity_features["secondary_grades"] = secondary_count
    advanced_color_count = (
        int(color_counts.get("hdr_zone_controls", 0))
        + int(color_counts.get("log_wheels", 0))
        + int(color_counts.get("hue_curves", 0))
        + int(color_counts.get("color_warper_points", 0))
    )
    if advanced_color_count:
        color_parity_features["advanced_color_toolset"] = advanced_color_count

    audio_parity_features: dict[str, int] = {}
    audio_effect_count = sum(
        int(audio_counts.get(key, 0))
        for key in (
            "dialogue_cleanup",
            "loudness",
            "eq",
            "compression",
            "gate",
            "deesser",
            "ai_master",
        )
    )
    if audio_effect_count:
        audio_parity_features["audio_effect_graph"] = audio_effect_count
    automation_count = int(audio_counts.get("clip_automation", 0)) + int(audio_counts.get("track_automation", 0))
    if automation_count:
        audio_parity_features["audio_automation"] = automation_count
    routed_bus_count = sum(
        1
        for _name, count in _as_dict(audio.get("bus_counts")).items()
        if int(count or 0) > 0
    )
    if routed_bus_count > 1:
        audio_parity_features["audio_bus_mixdown"] = routed_bus_count

    cpu_or_raw = {
        "background_removal": int(effects.get("background_removal", 0)),
        "stabilizer": int(effects.get("stabilizer", 0)),
        "tracked_masks": int(effects.get("tracked_masks", 0)),
        "node_graph": int(effects.get("node_graph", 0)),
        "nested_sequence": int(effects.get("nested_sequence", 0)),
        "actor_clips": int(effects.get("actor_clips", 0)),
    }
    shader_safe = {
        "video_filters": int(effects.get("video_filters", 0)),
        "chroma_key": int(effects.get("chroma_key", 0)),
    }
    issues: list[dict[str, Any]] = []
    raw_count = sum(cpu_or_raw.values())
    shader_count = sum(shader_safe.values())
    if raw_count:
        issues.append(_issue(
            "gpu_preview_export_consistency",
            "medium" if raw_count < 12 else "high",
            "Project uses features that still need preview/export parity checks outside the simple shader path.",
            "Run synthetic export parity plus project QA baseline before final delivery.",
            raw_or_cpu_feature_count=raw_count,
        ))
    if int(effects.get("actor_clips", 0) or 0):
        if actor_status:
            actor_coverage = _as_dict(actor_status.get("coverage"))
            actor_issues = _as_list(actor_status.get("issues"))
            if not actor_status.get("ok", False):
                issues.append(_issue(
                    "gpu_preview_export_consistency",
                    "high",
                    "Live2D/Spine corpus QA status is not passing.",
                    "Open actor_corpus_status and fix render failures, golden mismatches, or missing corpus coverage before delivery.",
                    actor_corpus_issues=len(actor_issues),
                    actor_corpus_coverage=actor_coverage,
                ))
            else:
                parity_checks_actor = int(actor_coverage.get("total", 0) or 0)
                if parity_checks_actor:
                    cpu_or_raw["actor_corpus_models"] = parity_checks_actor
        else:
            issues.append(_issue(
                "gpu_preview_export_consistency",
                "low",
                "Project uses actor clips without an attached actor corpus QA status.",
                "Run tools/actor_corpus_regression.py and attach the status artifact for release QA.",
                actor_clip_count=int(effects.get("actor_clips", 0) or 0),
            ))
    if raw_count and shader_count:
        issues.append(_issue(
            "gpu_preview_export_consistency",
            "medium",
            "GPU-friendly filters are mixed with CPU/raw pre-render sections.",
            "Compare preview and export on representative frames around those clips.",
            shader_feature_count=shader_count,
            raw_or_cpu_feature_count=raw_count,
        ))
    if color_management.get("hdr") or project_lut_count or grade_lut_count or color_management.get("ocio_config"):
        issues.append(_issue(
            "gpu_preview_export_consistency",
            "medium",
            "Project color pipeline needs explicit preview/export parity validation.",
            "Sample preview and export frames for LUT, HDR metadata, and display-transform agreement.",
            color_parity_feature_count=sum(color_parity_features.values()),
        ))
    parity_checks = []
    for name, count in {**shader_safe, **cpu_or_raw}.items():
        if count:
            parity_checks.append({
                "feature": name,
                "count": count,
                "check": "preview/export frame sample",
            })
    for name, count in color_parity_features.items():
        if count:
            check = "preview/export frame sample"
            if name in {"project_luts", "grade_luts"}:
                check = "preview/export LUT bake sample"
            elif name in {"hdr_metadata", "ocio_or_aces_transform", "color_management"}:
                check = "preview display/export metadata sample"
            elif name == "advanced_color_toolset":
                check = "preview/export advanced color bake sample"
            parity_checks.append({
                "feature": name,
                "count": count,
                "check": check,
            })
    for name, count in audio_parity_features.items():
        if count:
            check = "preview/export audio sample"
            if name == "audio_automation":
                check = "preview/export envelope sample"
            elif name == "audio_bus_mixdown":
                check = "export mixdown bus-routing sample"
            parity_checks.append({
                "feature": name,
                "count": count,
                "check": check,
            })
    return {
        "score": _score_from_issues(issues),
        "shader_safe_features": shader_safe,
        "raw_or_cpu_features": cpu_or_raw,
        "color_parity_features": color_parity_features,
        "audio_parity_features": audio_parity_features,
        "actor_corpus_status": actor_status,
        "parity_checks": parity_checks,
        "issues": issues,
    }


def audit_timeline_edit_integrity(doc: dict[str, Any], *, frame_ms: int | None = None) -> dict[str, Any]:
    fps = float(_as_dict(_as_dict(doc.get("project_settings")).get("color_management")).get("fps", 0.0) or 0.0)
    if frame_ms is None:
        project_fps = float(_as_dict(doc.get("project_settings")).get("fps", 30.0) or 30.0)
        frame_ms = max(1, int(round(1000.0 / max(1.0, project_fps))))
    issues: list[dict[str, Any]] = []
    overlaps = 0
    micro_gaps = 0
    micro_overlaps = 0
    by_track: dict[int, list[tuple[int, int, dict[str, Any]]]] = defaultdict(list)
    for track_idx, clip, depth in _video_clips(doc):
        if depth:
            continue
        start = _clip_start(clip)
        end = start + _video_clip_duration(clip)
        by_track[track_idx].append((start, end, clip))
    for track_idx, rows in by_track.items():
        rows.sort(key=lambda row: row[0])
        previous_end: int | None = None
        for start, end, _clip in rows:
            if previous_end is not None:
                if start < previous_end:
                    if previous_end - start <= frame_ms:
                        micro_overlaps += 1
                    else:
                        overlaps += 1
                elif 0 < start - previous_end <= frame_ms:
                    micro_gaps += 1
            previous_end = max(previous_end or 0, end)
    audio_ids = Counter()
    for _track_idx, clip, _depth in _audio_clips(doc):
        try:
            audio_ids[int(clip.get("id"))] += 1
        except Exception:
            pass
    linked_ids = Counter()
    missing_links = 0
    for _track_idx, clip, _depth in _video_clips(doc):
        linked = clip.get("linked_audio_id")
        if linked is None:
            continue
        try:
            linked_id = int(linked)
        except Exception:
            missing_links += 1
            continue
        linked_ids[linked_id] += 1
        if linked_id not in audio_ids:
            missing_links += 1
    shared_links = sum(1 for _linked, count in linked_ids.items() if count > 1)
    if overlaps:
        issues.append(_issue(
            "timeline_edit_integrity",
            "high",
            "Timeline contains overlapping clips on the same lane.",
            "Resolve overlaps before ripple/roll/slide edits or export QA.",
            overlap_count=overlaps,
        ))
    if micro_gaps:
        issues.append(_issue(
            "timeline_edit_integrity",
            "medium",
            "Timeline contains sub-frame or one-frame gaps.",
            "Use Health's timeline edge cleanup or snapping to remove accidental gaps.",
            micro_gap_count=micro_gaps,
        ))
    if micro_overlaps:
        issues.append(_issue(
            "timeline_edit_integrity",
            "medium",
            "Timeline contains sub-frame or one-frame overlaps.",
            "Use Health's timeline edge cleanup to trim accidental micro-overlaps before detailed trim work.",
            micro_overlap_count=micro_overlaps,
        ))
    if missing_links:
        issues.append(_issue(
            "timeline_edit_integrity",
            "high",
            "Some linked video clips point to missing audio clips.",
            "Relink or unlink corrupted audio links before grouped editing.",
            missing_link_count=missing_links,
        ))
    if shared_links:
        issues.append(_issue(
            "timeline_edit_integrity",
            "medium",
            "Multiple video clips share the same linked audio id.",
            "Split or duplicate audio links so linked clip moves are deterministic.",
            shared_link_count=shared_links,
        ))
    return {
        "score": _score_from_issues(issues),
        "overlap_count": overlaps,
        "micro_gap_count": micro_gaps,
        "micro_overlap_count": micro_overlaps,
        "auto_fixable_edge_count": micro_gaps + micro_overlaps,
        "missing_link_count": missing_links,
        "shared_link_count": shared_links,
        "frame_ms": int(frame_ms),
        "issues": issues,
    }


def _color_payloads(doc: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    settings = _as_dict(doc.get("project_settings"))
    for key in ("color_pipeline_payload", "advanced_color_toolset", "color_workflow"):
        value = doc.get(key)
        if isinstance(value, dict):
            payloads.append(value)
        value = settings.get(key)
        if isinstance(value, dict):
            payloads.append(value)
    for _track_idx, clip, _depth in _video_clips(doc):
        for key in ("color_grade", "color_workflow", "advanced_color_toolset"):
            value = clip.get(key)
            if isinstance(value, dict):
                payloads.append(value)
        node = _as_dict(clip.get("node_graph"))
        color = _as_dict(node.get("color"))
        grade = color.get("grade")
        if isinstance(grade, dict):
            payloads.append(grade)
    for key in ("clip_grade", "group_grade", "timeline_grade"):
        value = doc.get(key)
        if isinstance(value, dict):
            payloads.append(value)
        elif isinstance(value, list):
            payloads.extend(v for v in value if isinstance(v, dict))
    return payloads


def audit_color_workflow_depth(doc: dict[str, Any]) -> dict[str, Any]:
    settings = _as_dict(doc.get("project_settings"))
    color_management = _color_management_summary(doc)
    payloads = _color_payloads(doc)
    counts = Counter()
    scope_accuracy: dict[str, Any] = {}
    try:
        from app.color_workflow import scope_accuracy_report

        scope_accuracy = scope_accuracy_report()
    except Exception as exc:
        scope_accuracy = {
            "ok": False,
            "sample": "unavailable",
            "warnings": [f"scope accuracy QA unavailable: {exc}"],
            "qa_gates": [],
        }
    if color_management.get("explicit"):
        counts["color_management"] += 1
    if color_management.get("hdr"):
        counts["hdr_color_management"] += 1
    if color_management.get("ocio_config"):
        counts["ocio_configs"] += 1
    project_luts = _as_dict(color_management.get("active_luts"))
    if project_luts:
        counts["project_luts"] += len(project_luts)
    if color_management.get("preview_transform_enabled"):
        counts["preview_transforms"] += 1
    for payload in payloads:
        workflow = _as_dict(payload.get("color_workflow") or payload)
        advanced = _as_dict(payload.get("advanced_color_toolset"))
        if not advanced and any(key in payload for key in ("hdr_zones", "log_wheels", "hue_curves", "warper_points")):
            advanced = payload
        qualifier = _as_dict(workflow.get("qualifier"))
        window = _as_dict(workflow.get("window"))
        curves = _as_dict(workflow.get("curves"))
        if _payload_has_primary_grade(payload):
            counts["primary_grades"] += 1
        if qualifier.get("enabled"):
            counts["qualifiers"] += 1
            if qualifier.get("clean_black") or qualifier.get("clean_white") or qualifier.get("denoise_radius"):
                counts["qualified_cleanup"] += 1
            if qualifier.get("softness") not in (None, "", 0, 0.0):
                counts["qualifier_softness"] += 1
        if window.get("enabled"):
            counts["power_windows"] += 1
            if window.get("track_object"):
                counts["tracked_windows"] += 1
        if curves:
            counts["curves"] += 1
        if payload.get("hue_vs_hue"):
            counts["hue_curves"] += 1
        if advanced and advanced.get("enabled", True):
            hdr_zones = _as_dict(advanced.get("hdr_zones"))
            log_wheels = _as_dict(advanced.get("log_wheels"))
            hue_curves = _as_dict(advanced.get("hue_curves"))
            warper_points = _as_list(advanced.get("warper_points"))

            def _nonzero(raw: Any) -> bool:
                try:
                    return abs(float(raw or 0.0)) > 0.001
                except Exception:
                    return False

            if hdr_zones.get("enabled") or any(_nonzero(hdr_zones.get(key)) for key in ("black", "shadow", "dark", "light", "highlight", "specular")):
                counts["hdr_zone_controls"] += 1
            if log_wheels:
                counts["log_wheels"] += 1
            if hue_curves:
                counts["hue_curves"] += 1
            if warper_points:
                counts["color_warper_points"] += len(warper_points)
            if advanced.get("gallery_stills") or advanced.get("shot_match_reference"):
                counts["gallery_shot_match"] += 1
        if _payload_has_active_lut(payload):
            counts["grade_luts"] += 1
    for key in ("clip_grade", "group_grade", "timeline_grade"):
        if doc.get(key):
            counts[f"{key}_layers"] += 1
    issues: list[dict[str, Any]] = []
    if not color_management.get("explicit"):
        issues.append(_issue(
            "color_workflow_depth",
            "high",
            "Project has no explicit color-management payload.",
            "Set Rec.709/sRGB/HDR/ACES project color management before serious grading.",
        ))
    validation_messages = list(color_management.get("errors", []) or []) + list(color_management.get("warnings", []) or [])
    if validation_messages:
        severe = any(
            token in message.lower()
            for message in validation_messages
            for token in ("aces", "hdr", "ocio", "missing")
        )
        issues.append(_issue(
            "color_workflow_depth",
            "medium" if severe else "low",
            "Color-management validation has warnings.",
            "Resolve OCIO, HDR metadata, and LUT path warnings before delivery.",
            warning_count=len(validation_messages),
            warnings=validation_messages[:4],
        ))
    if payloads and not counts["qualifiers"] and not counts["power_windows"]:
        issues.append(_issue(
            "color_workflow_depth",
            "medium",
            "Grades exist but no qualifier or power-window isolation is used.",
            "Use HSL qualifiers or power windows for secondary corrections.",
            grade_count=len(payloads),
        ))
    if counts["power_windows"] and not counts["tracked_windows"]:
        issues.append(_issue(
            "color_workflow_depth",
            "low",
            "Power windows are static.",
            "Enable tracking for moving subjects when doing localized grades.",
            power_window_count=counts["power_windows"],
        ))
    if counts["qualifiers"] and counts["qualified_cleanup"] < counts["qualifiers"]:
        issues.append(_issue(
            "color_workflow_depth",
            "low",
            "Some HSL qualifiers have no clean black/white or denoise cleanup.",
            "Tune qualifier softness and cleanup controls before shot matching.",
            qualifier_count=counts["qualifiers"],
            cleaned_qualifier_count=counts["qualified_cleanup"],
        ))
    if project_luts and not color_management.get("preview_transform_enabled"):
        issues.append(_issue(
            "color_workflow_depth",
            "medium",
            "Project LUTs are active while preview transform is bypassed.",
            "Enable preview transform or verify the bypass against export samples.",
            project_lut_count=len(project_luts),
        ))
    return {
        "score": _score_from_issues(issues),
        "counts": dict(counts),
        "grade_payloads": len(payloads),
        "color_management": color_management,
        "scope_accuracy": scope_accuracy,
        "output_space": str(color_management.get("output_space") or ""),
        "output_transfer": str(color_management.get("output_transfer") or ""),
        "issues": issues,
    }


def audit_audio_mix_readiness(doc: dict[str, Any]) -> dict[str, Any]:
    tracks = [_as_dict(track) for track in _as_list(doc.get("audio_tracks")) if isinstance(track, dict)]
    clips = _audio_clips(doc)
    counts = Counter()
    bus_counts = Counter(str(track.get("bus_id") or "master") for track in tracks)
    role_counts = Counter()
    for track in tracks:
        raw_role = str(track.get("role") or track.get("bus_role") or track.get("bus_id") or track.get("label") or "").lower()
        if "dialogue" in raw_role or "voice" in raw_role or raw_role in {"dlg", "vo"}:
            role_counts["dialogue"] += 1
        elif "music" in raw_role or "bgm" in raw_role:
            role_counts["music"] += 1
        elif "sfx" in raw_role or "effect" in raw_role or "sound" in raw_role:
            role_counts["sfx"] += 1
        else:
            role_counts["mix"] += 1
        effects = _as_dict(track.get("effects"))
        for key, count_key in (
            ("eq", "track_eq"),
            ("comp", "track_compression"),
            ("gate", "track_gate"),
            ("ai_master", "track_ai_master"),
            ("loudness", "track_loudness"),
        ):
            if _as_dict(effects.get(key)).get("enabled"):
                counts[count_key] += 1
        try:
            if abs(float(track.get("volume", 1.0) or 1.0) - 1.0) > 0.001:
                counts["track_gain"] += 1
        except Exception:
            pass
        try:
            if abs(float(track.get("pan", 0.0) or 0.0)) > 0.001:
                counts["track_pan"] += 1
        except Exception:
            pass
    for _track_idx, clip, _depth in clips:
        effects = _as_dict(clip.get("effects"))
        if _as_dict(effects.get("dialogue_cleanup")).get("enabled"):
            counts["dialogue_cleanup"] += 1
        if _as_dict(effects.get("loudness")).get("enabled"):
            counts["loudness"] += 1
        if _as_dict(effects.get("eq")).get("enabled"):
            counts["eq"] += 1
        if _as_dict(effects.get("comp")).get("enabled"):
            counts["compression"] += 1
        if _as_dict(effects.get("gate")).get("enabled"):
            counts["gate"] += 1
        if _as_dict(effects.get("deesser")).get("enabled"):
            counts["deesser"] += 1
        if _as_dict(effects.get("ai_master")).get("enabled"):
            counts["ai_master"] += 1
        if clip.get("volume_points"):
            counts["clip_automation"] += 1
        try:
            if abs(float(clip.get("gain", 1.0) or 1.0) - 1.0) > 0.001:
                counts["clip_gain"] += 1
        except Exception:
            pass
    track_automation = sum(1 for track in tracks if track.get("automation_points"))
    counts["track_automation"] = track_automation
    issues: list[dict[str, Any]] = []
    if len(tracks) >= 2 and len(bus_counts) <= 1:
        issues.append(_issue(
            "audio_mix_readiness",
            "medium",
            "Multiple audio tracks route to one bus.",
            "Assign dialogue, music, and SFX buses before final mixing.",
            audio_tracks=len(tracks),
        ))
    if clips and not counts["loudness"]:
        issues.append(_issue(
            "audio_mix_readiness",
            "medium",
            "No clip has a loudness target.",
            "Apply a podcast, short-form, broadcast, or music loudness target before export.",
            audio_clips=len(clips),
        ))
    if clips and not counts["dialogue_cleanup"] and bus_counts.get("dialogue", 0):
        issues.append(_issue(
            "audio_mix_readiness",
            "low",
            "Dialogue bus exists but no dialogue cleanup chain is active.",
            "Apply dialogue cleanup or verify the source is already clean.",
        ))
    if len(tracks) >= 2 and not counts["track_automation"] and not counts["clip_automation"]:
        issues.append(_issue(
            "audio_mix_readiness",
            "low",
            "No track or clip automation is present on a multi-track mix.",
            "Add volume automation for dialogue rides, music ducks, or SFX transitions.",
            audio_tracks=len(tracks),
        ))
    if role_counts.get("music", 0) and not (
        counts["compression"]
        or counts["eq"]
        or counts["ai_master"]
        or counts["track_compression"]
        or counts["track_eq"]
        or counts["track_ai_master"]
    ):
        issues.append(_issue(
            "audio_mix_readiness",
            "low",
            "Music tracks have no EQ, compression, or mastering chain.",
            "Apply a music/mastering preset or verify the source is already mastered.",
            music_tracks=role_counts.get("music", 0),
        ))
    if role_counts.get("dialogue", 0) and counts["dialogue_cleanup"] and not counts["deesser"]:
        issues.append(_issue(
            "audio_mix_readiness",
            "low",
            "Dialogue cleanup is active without a de-esser.",
            "Add de-essing or confirm sibilance is already controlled.",
            dialogue_tracks=role_counts.get("dialogue", 0),
        ))
    return {
        "score": _score_from_issues(issues),
        "audio_tracks": len(tracks),
        "audio_clips": len(clips),
        "bus_counts": dict(bus_counts),
        "role_counts": dict(role_counts),
        "counts": dict(counts),
        "issues": issues,
    }


def audit_preset_template_ecosystem(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from app.preset_library import preset_ecosystem_report

        report = preset_ecosystem_report()
    except Exception as exc:
        issues = [_issue(
            "preset_template_ecosystem",
            "high",
            "Preset ecosystem diagnostics failed.",
            "Fix preset library loading before relying on one-click templates or workflow packs.",
            error=str(exc),
        )]
        return {
            "score": _score_from_issues(issues),
            "summary": {},
            "kind_targets": {},
            "topic_coverage": {},
            "template_reference_issues": [],
            "one_click_plans": {},
            "issues": issues,
        }
    issues: list[dict[str, Any]] = []
    for source in _as_list(report.get("issues")):
        source = _as_dict(source)
        extra = {
            key: value
            for key, value in source.items()
            if key not in {"area", "severity", "message", "action"}
        }
        issues.append(_issue(
            "preset_template_ecosystem",
            str(source.get("severity") or "low"),
            str(source.get("message") or "Preset ecosystem needs review."),
            str(source.get("action") or "Review preset ecosystem coverage."),
            **extra,
        ))
    return {
        "score": int(report.get("score", _score_from_issues(issues)) or 0),
        "summary": _as_dict(report.get("summary")),
        "kind_targets": _as_dict(report.get("kind_targets")),
        "topic_coverage": _as_dict(report.get("topic_coverage")),
        "template_reference_issues": _as_list(report.get("template_reference_issues")),
        "one_click_plans": _as_dict(report.get("one_click_plans")),
        "issues": issues,
    }


def _nested_payload(*values: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        if isinstance(value, dict):
            merged = _deep_merge_dicts(merged, value)
    return merged


def _deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge_dicts(dict(out[key]), value)
        else:
            out[key] = value
    return out


def _builtin_product_capabilities() -> dict[str, Any]:
    caps: dict[str, Any] = {}
    try:
        from app.color_workflow import advanced_color_product_capabilities

        caps["color"] = advanced_color_product_capabilities()
    except Exception:
        pass
    try:
        from app.audio_workflow import fairlight_product_capabilities

        caps["audio"] = fairlight_product_capabilities()
    except Exception:
        pass
    try:
        from app.post_pipeline_workflow import post_pipeline_product_capabilities

        caps = _deep_merge_dicts(caps, post_pipeline_product_capabilities())
    except Exception:
        pass
    return caps


def _has_truthy_key(payload: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            if value.strip():
                return True
        elif value:
            return True
    return False


def _capability(
    feature_id: str,
    label: str,
    *,
    supported: bool = False,
    partial: bool = False,
    evidence: str = "",
    action: str = "",
) -> dict[str, Any]:
    if supported:
        status = "supported"
    elif partial:
        status = "partial"
    else:
        status = "missing"
    return {
        "id": feature_id,
        "label": label,
        "status": status,
        "evidence": evidence,
        "action": action,
    }


def _capability_category_score(features: list[dict[str, Any]]) -> int:
    if not features:
        return 100
    points = 0.0
    for feature in features:
        status = str(feature.get("status") or "")
        if status == "supported":
            points += 1.0
        elif status == "partial":
            points += 0.5
    return int(round((points / len(features)) * 100))


def _feature_rows_by_status(features: list[dict[str, Any]], *statuses: str) -> list[dict[str, Any]]:
    wanted = {str(status) for status in statuses}
    return [
        _as_dict(feature)
        for feature in features
        if str(_as_dict(feature).get("status") or "") in wanted
    ]


def _professional_maturity_level(score: int) -> str:
    if score >= 90:
        return "validated professional workflow"
    if score >= 70:
        return "productized professional workflow"
    if score >= 45:
        return "partial professional workflow"
    return "foundation / gap-tracking workflow"


def _professional_depth_cards(categories: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize the Resolve/Fairlight/Fusion gap as product roadmap cards."""
    specs: dict[str, dict[str, Any]] = {
        "color": {
            "id": "resolve_color_depth",
            "competitor": "DaVinci Resolve Color",
            "target": "Deep color page: RAW/HDR/ACES, node grading, scopes, panel/monitoring, and shot-match validation.",
            "tiger_fit": "Keep creator-first defaults, but make advanced color non-destructive and preview/export-verified.",
            "phases": [
                {
                    "id": "engine",
                    "label": "Engine depth",
                    "items": [
                        "32-bit float/YRGB/wide-gamut metadata and transform QA",
                        "RAW sidecar controls for WB/ISO/tint/debayer/highlight recovery",
                        "HDR10+/Dolby Vision metadata model with ST.2084/HLG export checks",
                    ],
                    "qa_gate": "Color corpus compares preview/export pixels across Rec.709, sRGB, ACES, PQ, and HLG samples.",
                },
                {
                    "id": "grading",
                    "label": "Grading workspace",
                    "items": [
                        "Serial/parallel/layer/shared node topology",
                        "Qualifier cleanup, tracked power windows, secondary grade repair",
                        "Gallery stills, split-screen, lightbox, and shot-match surfaces",
                    ],
                    "qa_gate": "Shot-match and qualifier masks have stable scope deltas and no black-preview regressions.",
                },
                {
                    "id": "monitoring",
                    "label": "Monitoring/control",
                    "items": [
                        "Waveform/parade/vectorscope/histogram accuracy baselines",
                        "Color panel mapping model and external monitoring status",
                    ],
                    "qa_gate": "Scopes match known synthetic charts and panel mappings round-trip without touching grades.",
                },
            ],
            "daily_use_checks": [
                {
                    "id": "scene_linear_float",
                    "label": "Scene-linear/32-bit float preview-export path",
                    "feature_ids": ["float_yrgb_wide_gamut", "resolve_color_management_aces"],
                },
                {
                    "id": "raw_hdr_delivery",
                    "label": "RAW controls, HDR wheels, and HDR metadata delivery",
                    "feature_ids": ["camera_raw_non_destructive", "hdr_grading_tonemap", "hdr_metadata_delivery"],
                },
                {
                    "id": "node_secondary_order",
                    "label": "Node render order plus secondary tracking/qualifier work",
                    "feature_ids": ["node_grading", "secondary_tracking"],
                },
                {
                    "id": "match_restore_monitor",
                    "label": "Shot match, scopes, restoration, and gallery review",
                    "feature_ids": ["matching_scopes_gallery", "restoration_fx", "beauty_repair"],
                },
            ],
        },
        "audio": {
            "id": "fairlight_audio_depth",
            "competitor": "DaVinci Resolve Fairlight",
            "target": "DAW-class audio page: large mixer, ADR, automation, immersive routing, loudness, plugins, and consoles.",
            "tiger_fit": "Prioritize creator cleanup, buses, and loudness first; grow toward DAW depth without hiding video-edit speed.",
            "phases": [
                {
                    "id": "mixer",
                    "label": "Mixer graph",
                    "items": [
                        "Virtualized track/bus/sends mixer with realtime EQ/dynamics latency reporting",
                        "Sample-accurate clip edits, sync scroller, automation lanes, and take layers",
                    ],
                    "qa_gate": "Long audio corpus validates gain, automation, bus routing, and loudness parity after export.",
                },
                {
                    "id": "recording",
                    "label": "Recording/ADR",
                    "items": [
                        "VO/multitrack record-arm flow, ADR cues, countdown, review lanes",
                        "Pitch-preserving Elastic Wave retime for dialogue and effects",
                    ],
                    "qa_gate": "ADR samples keep cue timing and exported takes sample-aligned with the source timeline.",
                },
                {
                    "id": "delivery",
                    "label": "Delivery ecosystem",
                    "items": [
                        "Stereo/surround/immersive beds, ambisonics metadata, live loudness meters",
                        "VST/AU/plugin-host reporting and control-surface/audio-interface registry",
                    ],
                    "qa_gate": "Broadcast and creator loudness presets pass integrated LUFS/true-peak checks in render queue.",
                },
            ],
            "daily_use_checks": [
                {
                    "id": "mixer_routing_latency",
                    "label": "Realtime mixer graph with bus routing and latency reporting",
                    "feature_ids": ["daw_scale", "flexbus_routing", "realtime_eq_dynamics"],
                },
                {
                    "id": "sample_edit_automation",
                    "label": "Sample-accurate editing, sync scroller, automation, and take layers",
                    "feature_ids": ["sample_accurate_editing", "elastic_retime_layers"],
                },
                {
                    "id": "adr_recording_flow",
                    "label": "VO/ADR cue, record-arm, countdown, take review",
                    "feature_ids": ["recording_adr"],
                },
                {
                    "id": "delivery_plugins_immersive",
                    "label": "Loudness, SFX/Foley, immersive audio, and plugin host",
                    "feature_ids": ["loudness_delivery", "foley_library", "immersive_audio", "ai_audio_effects_plugins"],
                },
            ],
        },
        "vfx_fusion": {
            "id": "fusion_vfx_depth",
            "competitor": "DaVinci Resolve Fusion",
            "target": "Node compositing page: 2D/3D graph, trackers, keying/roto/paint, particles, imports, and macros.",
            "tiger_fit": "Use TigerCapture masks, actor layers, and repair payloads as the bridge into a focused compositor.",
            "phases": [
                {
                    "id": "graph",
                    "label": "Compositor graph",
                    "items": [
                        "2D/3D node domains with explicit cache boundaries",
                        "Merge/keyer/paint/repair/mask nodes reusable from Edit presets",
                        "Macro/template packaging back into workflow presets",
                    ],
                    "qa_gate": "Node graph samples render identically in preview/export and survive undo, save, and reload.",
                },
                {
                    "id": "tracking_roto",
                    "label": "Tracking/roto",
                    "items": [
                        "Planar tracker correction UI plus 3D camera tracker model",
                        "Bezier/B-spline roto, point feathering, clean plate, fringe tuning",
                    ],
                    "qa_gate": "Tracked masks keep object coverage across real screen/gameplay corpus clips.",
                },
                {
                    "id": "3d_particles",
                    "label": "3D/particles",
                    "items": [
                        "Camera/lights/3D text/image planes/materials viewport",
                        "FBX/Alembic scene import, particles, volumetric generators",
                    ],
                    "qa_gate": "3D scene samples load, relink, cache, and export without software fallback surprises.",
                },
            ],
            "daily_use_checks": [
                {
                    "id": "graph_cache",
                    "label": "2D/3D compositor graph execution with preview/export cache parity",
                    "feature_ids": ["node_2d_3d_compositing"],
                },
                {
                    "id": "tracking_roto_key",
                    "label": "Planar/3D tracking, keying, roto, clean plate, and feathering",
                    "feature_ids": ["tracking", "keying_roto"],
                },
                {
                    "id": "paint_particles",
                    "label": "Paint/clone repair, particles, and volumetric generators",
                    "feature_ids": ["paint_repair_particles"],
                },
                {
                    "id": "macro_expressions",
                    "label": "Spline editor, expressions, modifiers, and reusable Fusion macros",
                    "feature_ids": ["spline_expressions_macros"],
                },
            ],
        },
    }
    cards: list[dict[str, Any]] = []
    for key, spec in specs.items():
        category = _as_dict(categories.get(key))
        features = [_as_dict(feature) for feature in _as_list(category.get("features")) if isinstance(feature, dict)]
        score = int(category.get("score", _capability_category_score(features)) or 0)
        missing = _feature_rows_by_status(features, "missing")
        partial = _feature_rows_by_status(features, "partial")
        supported = _feature_rows_by_status(features, "supported")
        feature_by_id = {str(feature.get("id") or ""): feature for feature in features}
        daily_checks: list[dict[str, Any]] = []
        for raw_check in list(spec.get("daily_use_checks") or []):
            check = dict(raw_check)
            feature_ids = [str(item) for item in list(check.get("feature_ids") or [])]
            statuses = [
                str(_as_dict(feature_by_id.get(feature_id)).get("status") or "missing")
                for feature_id in feature_ids
            ]
            if statuses and all(status == "supported" for status in statuses):
                status = "ready"
            elif any(status in {"supported", "partial"} for status in statuses):
                status = "partial"
            else:
                status = "missing"
            actions = [
                str(_as_dict(feature_by_id.get(feature_id)).get("action") or "")
                for feature_id in feature_ids
            ]
            check["status"] = status
            check["blocking_feature_ids"] = [
                feature_id
                for feature_id in feature_ids
                if str(_as_dict(feature_by_id.get(feature_id)).get("status") or "missing") != "supported"
            ]
            check["next_action"] = next((action for action in actions if action), "")
            daily_checks.append(check)
        ready_checks = [check for check in daily_checks if check.get("status") == "ready"]
        partial_checks = [check for check in daily_checks if check.get("status") == "partial"]
        missing_checks = [check for check in daily_checks if check.get("status") == "missing"]
        blockers = missing[:4] + partial[:3]
        next_actions = [
            str(feature.get("action"))
            for feature in blockers
            if str(feature.get("action") or "")
        ]
        next_depth_action = next(
            (str(check.get("next_action") or "") for check in missing_checks + partial_checks if str(check.get("next_action") or "")),
            "",
        )
        cards.append({
            "id": spec["id"],
            "category": key,
            "category_label": str(category.get("label") or key),
            "competitor": spec["competitor"],
            "score": score,
            "current_level": _professional_maturity_level(score),
            "target": spec["target"],
            "tiger_fit": spec["tiger_fit"],
            "supported_count": len(supported),
            "partial_count": len(partial),
            "missing_count": len(missing),
            "why_not_100": [
                str(feature.get("label") or feature.get("id"))
                for feature in blockers
                if str(feature.get("label") or feature.get("id") or "")
            ],
            "next_actions": next_actions[:6],
            "daily_use_checks": daily_checks,
            "daily_use_ready_count": len(ready_checks),
            "daily_use_partial_count": len(partial_checks),
            "daily_use_missing_count": len(missing_checks),
            "daily_use_blocking_count": len(partial_checks) + len(missing_checks),
            "next_depth_action": next_depth_action,
            "phases": list(spec["phases"]),
        })
    return cards


def audit_resolve_post_pipeline_parity(doc: dict[str, Any]) -> dict[str, Any]:
    """Advisory DaVinci Resolve/Fairlight/Fusion parity matrix.

    This is product capability telemetry, not a per-project pass/fail gate.
    Missing Dolby Vision hardware, 2,000-track DAW scale, or Fusion 3D tools
    should be visible to Health/QA without making a small editor project fail
    its normal export-readiness score.
    """
    settings = _as_dict(doc.get("project_settings"))
    product = _deep_merge_dicts(
        _builtin_product_capabilities(),
        _nested_payload(doc.get("product_capabilities"), settings.get("product_capabilities")),
    )
    color_caps = _nested_payload(product.get("color"), doc.get("color_capabilities"), settings.get("color_capabilities"))
    audio_caps = _nested_payload(product.get("audio"), doc.get("audio_capabilities"), settings.get("audio_capabilities"))
    vfx_caps = _nested_payload(product.get("vfx"), doc.get("vfx_capabilities"), settings.get("vfx_capabilities"))
    performance_caps = _nested_payload(product.get("performance"), doc.get("performance_capabilities"), settings.get("performance_capabilities"))
    post_caps = _nested_payload(product.get("post_pipeline"), doc.get("post_pipeline"), settings.get("post_pipeline"))
    hardware_caps = _nested_payload(product.get("hardware"), doc.get("hardware_capabilities"), settings.get("hardware_capabilities"))

    if _as_dict(doc.get("audio_routing_matrix")) or _as_dict(settings.get("audio_routing_matrix")):
        audio_caps = _deep_merge_dicts(audio_caps, {
            "routing_matrix": True,
            "flexbus": True,
            "realtime_mixer": True,
            "sample_accurate_editing": True,
        })
    if _as_list(doc.get("vfx_repair_plans")) or _as_list(settings.get("vfx_repair_plans")):
        vfx_caps = _deep_merge_dicts(vfx_caps, {
            "planar_tracker": True,
            "clean_plate": True,
            "b_spline_roto": True,
            "point_feathering": True,
            "vector_paint": True,
        })
    if _as_dict(doc.get("proxy_render_cache")) or _as_dict(settings.get("proxy_render_cache")):
        performance_caps = _deep_merge_dicts(performance_caps, {
            "render_cache": True,
            "optimized_media": True,
            "preview_export_parity": True,
        })
    if (
        _as_list(doc.get("deliver_jobs"))
        or _as_list(settings.get("deliver_jobs"))
        or _as_list(doc.get("deliver_page_matrix"))
        or _as_list(doc.get("professional_deliver_jobs"))
        or _as_list(settings.get("professional_deliver_jobs"))
    ):
        performance_caps = _deep_merge_dicts(performance_caps, {
            "render_provider_model": True,
        })
        post_caps = _deep_merge_dicts(post_caps, {
            "deliver_page": True,
            "encoding_matrix": True,
        })
    if _as_dict(doc.get("ingest_clone_manifest")) or _as_dict(settings.get("ingest_clone_manifest")):
        post_caps = _deep_merge_dicts(post_caps, {
            "media_ingest": True,
            "camera_card_clone": True,
            "smart_metadata": True,
        })

    color = audit_color_workflow_depth(doc)
    audio = audit_audio_mix_readiness(doc)
    effects = _clip_effect_counts(doc)
    color_counts = Counter(_as_dict(color.get("counts")))
    audio_counts = Counter(_as_dict(audio.get("counts")))
    cm = _as_dict(color.get("color_management"))
    video_clips = _video_clips(doc)
    audio_tracks = [_as_dict(track) for track in _as_list(doc.get("audio_tracks")) if isinstance(track, dict)]

    float_bits = 0
    for raw in (
        color_caps.get("float_processing_bits"),
        color_caps.get("processing_bits"),
        settings.get("float_processing_bits"),
        _as_dict(settings.get("color_management")).get("processing_bits"),
    ):
        try:
            float_bits = max(float_bits, int(raw or 0))
        except Exception:
            continue
    node_graph_count = int(effects.get("node_graph", 0))
    vfx_node_graphs = [
        row for row in (
            _as_list(doc.get("vfx_node_graphs"))
            + _as_list(settings.get("vfx_node_graphs"))
            + _as_list(doc.get("mini_vfx_node_graphs"))
            + _as_list(settings.get("mini_vfx_node_graphs"))
        )
        if isinstance(row, dict)
    ]
    vfx_node_graph_count = len(vfx_node_graphs)
    vfx_graph_qa: dict[str, Any] = {
        "ok": False,
        "graph_count": vfx_node_graph_count,
        "node_count": 0,
        "warnings": [],
    }
    if vfx_node_graphs:
        try:
            from app.post_pipeline_workflow import vfx_node_graph_qa_report

            vfx_graph_qa = vfx_node_graph_qa_report(vfx_node_graphs)
        except Exception as exc:
            vfx_graph_qa = {
                "ok": False,
                "graph_count": vfx_node_graph_count,
                "node_count": 0,
                "warnings": [f"VFX graph QA unavailable: {exc}"],
            }
    if vfx_node_graph_count:
        vfx_kind_counts = Counter(_as_dict(vfx_graph_qa.get("kind_counts")))
        if vfx_kind_counts.get("delta_keyer") or vfx_kind_counts.get("chroma_key"):
            effects["chroma_key"] = max(int(effects.get("chroma_key", 0) or 0), int(vfx_kind_counts.get("delta_keyer", 0) or 0), int(vfx_kind_counts.get("chroma_key", 0) or 0))
        if vfx_kind_counts.get("b_spline_roto") or vfx_kind_counts.get("paint_clone"):
            effects["masks"] = max(int(effects.get("masks", 0) or 0), int(vfx_kind_counts.get("b_spline_roto", 0) or 0), int(vfx_kind_counts.get("paint_clone", 0) or 0))
        vfx_caps = _deep_merge_dicts(vfx_caps, {
            "fusion_graph_model": True,
            "mini_node_compositor": True,
            "node_count": max(int(vfx_caps.get("node_count") or 0), int(vfx_graph_qa.get("node_count", 0) or vfx_node_graph_count)),
        })
    fusion_nodes = int(vfx_caps.get("fusion_node_count") or vfx_caps.get("node_count") or 0)
    render_queue_jobs = (
        len(_as_list(doc.get("render_queue_jobs")))
        or len(_as_list(doc.get("deliver_jobs")))
        or len(_as_list(doc.get("professional_deliver_jobs")))
        or len(_as_list(doc.get("deliver_page_matrix")))
        or int(performance_caps.get("render_queue_jobs") or 0)
    )
    proxy_count = sum(1 for _track, clip, _depth in video_clips if clip.get("proxy_path") or clip.get("optimized_media_path"))
    bus_count = len([bus for bus, count in _as_dict(audio.get("bus_counts")).items() if int(count or 0) > 0])
    max_audio_tracks = 0
    try:
        max_audio_tracks = int(audio_caps.get("max_tracks") or len(audio_tracks))
    except Exception:
        max_audio_tracks = len(audio_tracks)

    categories: dict[str, dict[str, Any]] = {
        "color": {
            "label": "Color / 색보정",
            "features": [
                _capability(
                    "float_yrgb_wide_gamut",
                    "32-bit float, YRGB, wide-gamut/HDR processing",
                    supported=float_bits >= 32 or _has_truthy_key(color_caps, "yrgb", "wide_gamut", "float_pipeline"),
                    partial=bool(cm.get("explicit")),
                    evidence=f"processing_bits={float_bits or 'unknown'}, working={cm.get('working_space') or '-'}",
                    action="Add explicit 32-bit float/YRGB processing metadata and wide-gamut transform QA.",
                ),
                _capability(
                    "hdr_grading_tonemap",
                    "HDR wheels, zone tone controls, ST.2084/HLG tone mapping",
                    supported=_has_truthy_key(color_caps, "hdr_wheels", "zone_tone_controls", "st2084_tonemap", "hlg_tonemap"),
                    partial=bool(cm.get("hdr")),
                    evidence=f"hdr={bool(cm.get('hdr'))}, transfer={cm.get('output_transfer') or '-'}",
                    action="Implement HDR wheels/zone controls and ST.2084/HLG preview/export parity samples.",
                ),
                _capability(
                    "hdr_metadata_delivery",
                    "Dolby Vision / HDR10+ metadata",
                    supported=_has_truthy_key(color_caps, "dolby_vision_metadata", "hdr10plus_metadata"),
                    partial=_has_truthy_key(color_caps, "hdr_metadata_model") or _has_truthy_key(settings, "hdr10_metadata", "mastering_display_metadata"),
                    action="Add HDR10+/Dolby Vision metadata model, validation, and deliver-page handoff.",
                ),
                _capability(
                    "resolve_color_management_aces",
                    "Resolve Color Management, ACES, OCIO",
                    supported=bool(cm.get("ocio_config")) or str(cm.get("working_space", "")).lower().startswith("aces"),
                    partial=bool(cm.get("explicit")),
                    evidence=f"ocio={bool(cm.get('ocio_config'))}, working={cm.get('working_space') or '-'}",
                    action="Finish ACES/OCIO transform QA and input/output color-space consistency checks.",
                ),
                _capability(
                    "camera_raw_non_destructive",
                    "Camera RAW non-destructive controls",
                    supported=_has_truthy_key(color_caps, "camera_raw", "raw_controls") or any(_as_dict(clip.get("camera_raw")).get("enabled") for _t, clip, _d in video_clips),
                    partial=_has_truthy_key(color_caps, "raw_sidecar_model"),
                    action="Add RAW sidecar controls for ISO, WB, tint, decode quality, highlight recovery, and debayer mode.",
                ),
                _capability(
                    "primary_log_hdr_wheels",
                    "Primary, Log, HDR, Offset/Lift/Gamma/Gain wheels",
                    supported=_has_truthy_key(color_caps, "log_wheels", "hdr_wheels") and (
                        color_counts.get("primary_grades", 0) > 0
                        or color_counts.get("log_wheels", 0) > 0
                        or color_counts.get("hdr_zone_controls", 0) > 0
                    ),
                    partial=(
                        color_counts.get("primary_grades", 0) > 0
                        or color_counts.get("log_wheels", 0) > 0
                        or color_counts.get("hdr_zone_controls", 0) > 0
                    ),
                    evidence=f"primary_grades={color_counts.get('primary_grades', 0)}, log_wheels={color_counts.get('log_wheels', 0)}, hdr_zones={color_counts.get('hdr_zone_controls', 0)}",
                    action="Add Log/HDR wheel parameter groups beside existing primary wheel payloads.",
                ),
                _capability(
                    "advanced_curves_warper",
                    "Custom curves, Hue vs Hue/Sat/Luma, Color Warper",
                    supported=_has_truthy_key(color_caps, "color_warper") and (
                        color_counts.get("curves", 0) > 0
                        or color_counts.get("hue_curves", 0) > 0
                        or color_counts.get("color_warper_points", 0) > 0
                    ),
                    partial=(
                        color_counts.get("curves", 0) > 0
                        or color_counts.get("hue_curves", 0) > 0
                        or color_counts.get("color_warper_points", 0) > 0
                        or _has_truthy_key(color_caps, "hue_vs_hue", "hue_vs_sat", "hue_vs_luma", "color_warper")
                    ),
                    evidence=f"curves={color_counts.get('curves', 0)}, hue_curves={color_counts.get('hue_curves', 0)}, warper_points={color_counts.get('color_warper_points', 0)}",
                    action="Add Hue vs Sat/Luma and Color Warper UI/data with scope-backed QA samples.",
                ),
                _capability(
                    "node_grading",
                    "Serial/parallel/layer/shared node grading",
                    supported=_has_truthy_key(color_caps, "parallel_nodes", "layer_nodes", "shared_nodes"),
                    partial=node_graph_count > 0 or _has_truthy_key(color_caps, "serial_nodes", "node_grading_model"),
                    evidence=f"node_graph_clips={node_graph_count}",
                    action="Add explicit serial/parallel/layer/shared color node topology and render-order tests.",
                ),
                _capability(
                    "secondary_tracking",
                    "Power Windows, qualifier, tracking, secondary grading",
                    supported=color_counts.get("qualifiers", 0) > 0 and color_counts.get("tracked_windows", 0) > 0,
                    partial=color_counts.get("qualifiers", 0) > 0 or color_counts.get("power_windows", 0) > 0 or _has_truthy_key(color_caps, "secondary_grading_model", "tracking_window_model"),
                    evidence=f"qualifiers={color_counts.get('qualifiers', 0)}, tracked_windows={color_counts.get('tracked_windows', 0)}",
                    action="Expand secondary grading with better tracker correction UI and qualifier cleanup QA.",
                ),
                _capability(
                    "beauty_repair",
                    "Face refinement, beauty, skin retouching, object removal, patch replacer",
                    supported=_has_truthy_key(color_caps, "face_refinement", "object_removal", "patch_replacer"),
                    partial=bool(effects.get("background_removal") or effects.get("tracked_masks")) or _has_truthy_key(color_caps, "beauty_repair_model", "object_repair_model"),
                    action="Add face/skin/object repair tools backed by local ML and patch-replace masks.",
                ),
                _capability(
                    "restoration_fx",
                    "Temporal/spatial NR, film grain, deflicker, dead pixel, dust/dirt removal",
                    supported=_has_truthy_key(color_caps, "temporal_nr", "spatial_nr", "film_grain", "deflicker", "dust_dirt_removal"),
                    partial=any(_as_dict(clip.get("video_filters")).get("denoise") for _t, clip, _d in video_clips) or _has_truthy_key(color_caps, "restoration_fx_model"),
                    action="Add temporal/spatial NR, grain, deflicker, dead-pixel, and dust/dirt filters with GPU parity QA.",
                ),
                _capability(
                    "matching_scopes_gallery",
                    "Gallery stills, shot match, split screen, lightbox, waveform/parade/vectorscope/histogram",
                    supported=_has_truthy_key(color_caps, "gallery_stills", "shot_match", "split_screen", "lightbox") and _has_truthy_key(color_caps, "waveform", "parade", "vectorscope", "histogram"),
                    partial=_has_truthy_key(settings, "scopes_enabled") or _has_truthy_key(color_caps, "waveform", "parade", "vectorscope", "histogram", "gallery_stills", "shot_match"),
                    action="Productize gallery stills, shot matching, split-screen/lightbox, and scope accuracy QA.",
                ),
            ],
        },
        "audio": {
            "label": "Audio / Fairlight",
            "features": [
                _capability(
                    "daw_scale",
                    "Fairlight-style DAW scale up to 2,000 tracks",
                    supported=max_audio_tracks >= 2000,
                    partial=len(audio_tracks) >= 8 or max_audio_tracks >= 64,
                    evidence=f"tracks={len(audio_tracks)}, declared_max={max_audio_tracks}",
                    action="Stress test audio model/mixer virtualization toward hundreds of tracks before claiming DAW scale.",
                ),
                _capability(
                    "flexbus_routing",
                    "FlexBus-style routing and bussing",
                    supported=_has_truthy_key(audio_caps, "flexbus", "routing_matrix"),
                    partial=bus_count > 1,
                    evidence=f"bus_count={bus_count}",
                    action="Add routing matrix, sends/returns, submixes, and bus freeze/solo-safe semantics.",
                ),
                _capability(
                    "realtime_eq_dynamics",
                    "Realtime EQ, dynamics, effects",
                    supported=_has_truthy_key(audio_caps, "realtime_mixer") or (audio_counts.get("track_eq", 0) > 0 and audio_counts.get("track_compression", 0) > 0),
                    partial=audio_counts.get("eq", 0) > 0 or audio_counts.get("compression", 0) > 0 or _has_truthy_key(audio_caps, "routing_matrix"),
                    evidence=f"eq={audio_counts.get('eq', 0)}, comp={audio_counts.get('compression', 0)}",
                    action="Move clip/track EQ and dynamics into a realtime mixer graph with latency reporting.",
                ),
                _capability(
                    "sample_accurate_editing",
                    "Sample-accurate editing and sync scroller",
                    supported=_has_truthy_key(audio_caps, "sample_accurate_editing", "sync_scroller"),
                    partial=bool(_as_dict(settings.get("audio")).get("sample_rate")),
                    action="Add sample-domain edit positions, sync scroller, and waveform sample cursor tests.",
                ),
                _capability(
                    "recording_adr",
                    "VO/multitrack recording and ADR cue workflow",
                    supported=_has_truthy_key(audio_caps, "vo_recording", "adr_cues", "multitrack_recording"),
                    partial=_has_truthy_key(audio_caps, "adr_cue_model", "multitrack_recording_model"),
                    action="Add record-arm, cue list, take naming, countdown, and ADR review lanes.",
                ),
                _capability(
                    "elastic_retime_layers",
                    "Elastic Wave retiming and non-destructive take layers",
                    supported=_has_truthy_key(audio_caps, "elastic_wave", "track_layers"),
                    partial=_has_truthy_key(audio_caps, "elastic_wave_model", "track_layers_model") or audio_counts.get("clip_automation", 0) > 0,
                    action="Add pitch-preserving clip retime plus layered take comping.",
                ),
                _capability(
                    "foley_library",
                    "Foley and sound-effect library",
                    supported=_has_truthy_key(audio_caps, "foley_library", "sfx_library") or bool(doc.get("sfx_library")),
                    partial=_has_truthy_key(audio_caps, "foley_library_model", "sfx_library_model"),
                    action="Add indexed SFX/Foley browser with tags, auditioning, and drag-to-timeline.",
                ),
                _capability(
                    "loudness_delivery",
                    "Broadcast loudness monitoring and delivery",
                    supported=_has_truthy_key(audio_caps, "loudness_monitoring") or audio_counts.get("track_loudness", 0) > 0,
                    partial=audio_counts.get("loudness", 0) > 0,
                    evidence=f"clip_loudness={audio_counts.get('loudness', 0)}, track_loudness={audio_counts.get('track_loudness', 0)}",
                    action="Add live loudness meter, true-peak warnings, and delivery preset validation.",
                ),
                _capability(
                    "immersive_audio",
                    "Stereo, 5.1, 7.1, 22.2, immersive 3D audio, ambisonics",
                    supported=_has_truthy_key(audio_caps, "surround_5_1", "surround_7_1", "immersive_3d", "ambisonics"),
                    partial=str(_as_dict(settings.get("audio")).get("channel_layout", "")).lower() not in {"", "stereo", "2.0"} or _has_truthy_key(audio_caps, "immersive_audio_model"),
                    action="Add channel-bed routing, panners, ambisonic metadata, and surround export checks.",
                ),
                _capability(
                    "ai_audio_effects_plugins",
                    "Voice Isolation, Music Remixer, Fairlight FX, VST/AU plugins",
                    supported=_has_truthy_key(audio_caps, "voice_isolation", "music_remixer", "vst_plugins", "au_plugins"),
                    partial=audio_counts.get("dialogue_cleanup", 0) > 0 or audio_counts.get("ai_master", 0) > 0 or _has_truthy_key(audio_caps, "plugin_host_model", "music_remixer_model"),
                    action="Add local voice isolation/music remixers and plugin host capability reporting.",
                ),
            ],
        },
        "vfx_fusion": {
            "label": "VFX / Fusion",
            "features": [
                _capability(
                    "node_2d_3d_compositing",
                    "Node-based 2D/3D compositing",
                    supported=_has_truthy_key(vfx_caps, "true_3d_workspace", "fusion_graph"),
                    partial=node_graph_count > 0 or fusion_nodes > 0 or vfx_node_graph_count > 0 or _has_truthy_key(vfx_caps, "spline_editor", "macros", "fusion_graph_model", "mini_node_compositor"),
                    evidence=f"node_graph_clips={node_graph_count}, vfx_graphs={vfx_node_graph_count}, fusion_nodes={fusion_nodes}",
                    action="Create a Fusion-like compositor graph with 2D/3D node domains and explicit cache boundaries.",
                ),
                _capability(
                    "true_3d_workspace",
                    "Camera, lights, 3D text, particles, image planes, materials",
                    supported=_has_truthy_key(vfx_caps, "camera_3d", "lights_3d", "particles_3d", "materials_3d"),
                    partial=_has_truthy_key(vfx_caps, "true_3d_workspace_model", "particles_model"),
                    action="Add 3D scene nodes and viewport tooling before claiming Fusion-style 3D.",
                ),
                _capability(
                    "scene_import",
                    "FBX/Alembic 3D scene import",
                    supported=_has_truthy_key(vfx_caps, "fbx_import", "alembic_import"),
                    partial=_has_truthy_key(vfx_caps, "scene_import_model"),
                    action="Add FBX/Alembic import adapters and asset relink/preview support.",
                ),
                _capability(
                    "tracking",
                    "2D tracker, planar tracker, 3D camera tracker",
                    supported=_has_truthy_key(vfx_caps, "planar_tracker", "camera_tracker_3d"),
                    partial=effects.get("tracked_masks", 0) > 0,
                    evidence=f"tracked_masks={effects.get('tracked_masks', 0)}",
                    action="Extend OpenCV tracking into planar/camera-track workflows with correction UI.",
                ),
                _capability(
                    "keying_roto",
                    "Green/blue keying, clean plate, B-spline roto, point feathering",
                    supported=_has_truthy_key(vfx_caps, "clean_plate", "b_spline_roto", "point_feathering") and effects.get("chroma_key", 0) > 0,
                    partial=effects.get("chroma_key", 0) > 0 or effects.get("masks", 0) > 0 or _has_truthy_key(vfx_caps, "keying_roto_model"),
                    evidence=f"chroma_key={effects.get('chroma_key', 0)}, masks={effects.get('masks', 0)}",
                    action="Add clean-plate/fringe tuning and Bezier/B-spline roto with per-point feathering.",
                ),
                _capability(
                    "paint_repair_particles",
                    "Vector paint/clone, object paint-out, particles, volumetric effects",
                    supported=_has_truthy_key(vfx_caps, "vector_paint", "clone_paint", "particles_3d", "volumetric_fx"),
                    partial=bool(effects.get("background_removal")) or _has_truthy_key(vfx_caps, "vector_paint"),
                    action="Add paint/clone repair nodes and particle/volumetric generators.",
                ),
                _capability(
                    "spline_expressions_macros",
                    "Spline/keyframe editor, expressions, modifiers, Fusion macros/templates",
                    supported=_has_truthy_key(vfx_caps, "spline_editor", "expressions", "macros"),
                    partial=bool(doc.get("workflow_presets") or doc.get("template_presets")),
                    action="Add expression/modifier graph metadata and reusable compositor macros.",
                ),
            ],
        },
        "performance": {
            "label": "Performance / 대형 프로젝트 처리",
            "features": [
                _capability(
                    "gpu_cpu_resolve_fx",
                    "GPU/CPU accelerated FX with preview/export parity",
                    supported=_has_truthy_key(performance_caps, "gpu_fx", "native_fx", "preview_export_parity"),
                    partial=bool(settings.get("preview_engine") or settings.get("preview_export_parity_lock")),
                    action="Keep moving heavy filters/keying/Spine meshes to native/GPU with parity tests.",
                ),
                _capability(
                    "neural_engine",
                    "Object detection, face recognition, smart reframe, speed warp, super scale, auto color/match",
                    supported=_has_truthy_key(performance_caps, "object_detection", "face_recognition", "smart_reframe", "speed_warp", "super_scale", "auto_color"),
                    partial=_has_truthy_key(settings, "local_ml_enabled") or bool(doc.get("local_ml_status")),
                    action="Wire local ML models into object/face/smart-reframe/super-scale QA without cloud dependency.",
                ),
                _capability(
                    "studio_delivery_limits",
                    "10-bit, 120fps, 4K+ delivery and advanced FX/AI gates",
                    supported=_has_truthy_key(performance_caps, "ten_bit_export", "fps_120", "above_4k_export"),
                    partial=float(settings.get("fps", 0) or 0) >= 60,
                    action="Add 10-bit/120fps/4K+ export validation and visible feature gates.",
                ),
                _capability(
                    "proxy_render_cache",
                    "Proxy editing, optimized media, render cache",
                    supported=_has_truthy_key(performance_caps, "render_cache", "optimized_media"),
                    partial=proxy_count > 0 or bool(settings.get("proxy_mode")),
                    evidence=f"proxy_clips={proxy_count}",
                    action="Productize stale proxy detection, render cache status, and cache invalidation UI.",
                ),
                _capability(
                    "render_queue_remote",
                    "Render Queue, remote rendering, multiple delivery jobs",
                    supported=_has_truthy_key(performance_caps, "remote_render") and (render_queue_jobs > 0 or _has_truthy_key(performance_caps, "render_provider_model")),
                    partial=render_queue_jobs > 0 or bool(doc.get("render_queue")),
                    evidence=f"render_queue_jobs={render_queue_jobs}",
                    action="Add remote render/provider abstraction and richer failure/retry diagnostics.",
                ),
                _capability(
                    "io_plugin_storage_ecosystem",
                    "DeckLink I/O, control panels, NAS/SAN, OpenFX/audio plugin/API ecosystem",
                    supported=_has_truthy_key(performance_caps, "decklink", "nas_san", "openfx", "workflow_api") or _has_truthy_key(hardware_caps, "decklink", "control_panel"),
                    action="Add external monitoring/plugin/storage capability registry and device diagnostics.",
                ),
            ],
        },
        "post_pipeline": {
            "label": "전문 후반작업 / Post Pipeline",
            "features": [
                _capability(
                    "media_ingest_clone",
                    "Media ingest, bins, metadata, camera-card clone/backup",
                    supported=_has_truthy_key(post_caps, "camera_card_clone", "media_ingest"),
                    partial=bool(doc.get("media_bins") or doc.get("media_pool")),
                    action="Add verified camera-card clone/backup, checksum, and metadata ingest reports.",
                ),
                _capability(
                    "av_sync_metadata",
                    "Automatic A/V sync and smart metadata",
                    supported=_has_truthy_key(post_caps, "auto_av_sync", "smart_metadata"),
                    partial=any(_as_dict(clip).get("linked_audio_id") for _t, clip, _d in video_clips),
                    action="Add waveform/timecode A/V sync plus searchable metadata fields.",
                ),
                _capability(
                    "longform_edit_tools",
                    "Trimming, multicam, dual timeline, source tape",
                    supported=_has_truthy_key(post_caps, "multicam", "dual_timeline", "source_tape"),
                    partial=bool(doc.get("nested_sequences") or doc.get("timeline_edit_tools")),
                    action="Finish multicam/source-tape/dual-timeline workflows and undo stress QA.",
                ),
                _capability(
                    "page_integration",
                    "Edit, Color, Fusion, Fairlight, Deliver connected in one project",
                    supported=_has_truthy_key(post_caps, "page_integration", "deliver_page"),
                    partial=bool(color_counts or audio_counts or node_graph_count),
                    action="Expose page-level handoff state from Edit to Color/VFX/Audio/Deliver.",
                ),
                _capability(
                    "multi_user_collaboration",
                    "Multi-user collaboration, bin/timeline locking, markers, chat, cloud",
                    supported=_has_truthy_key(post_caps, "multi_user", "timeline_locking", "shared_markers", "cloud_collaboration"),
                    partial=bool(doc.get("markers") or doc.get("shared_markers")),
                    action="Add collaboration model, locks, shared markers, conflict reporting, and cloud handoff hooks.",
                ),
                _capability(
                    "deliver_page",
                    "Deliver page with detailed encoding and multi-job queue",
                    supported=_has_truthy_key(post_caps, "deliver_page", "encoding_matrix"),
                    partial=render_queue_jobs > 0,
                    action="Expand delivery presets into a full Deliver page with codec matrix and batch manifests.",
                ),
            ],
        },
        "hardware_ecosystem": {
            "label": "Hardware / Studio ecosystem",
            "features": [
                _capability(
                    "color_panels",
                    "Micro/Mini/Advanced color panels",
                    supported=_has_truthy_key(hardware_caps, "micro_panel", "mini_panel", "advanced_panel"),
                    partial=_has_truthy_key(hardware_caps, "color_panel_mapping_model"),
                    action="Add color-panel MIDI/HID mapping abstraction and device-status UI.",
                ),
                _capability(
                    "fairlight_console",
                    "Fairlight console, PCIe accelerator, MADI/audio interfaces",
                    supported=_has_truthy_key(hardware_caps, "fairlight_console", "audio_accelerator", "madi_interface"),
                    partial=_has_truthy_key(hardware_caps, "fairlight_console_mapping_model", "audio_interface_model"),
                    action="Add external mixer/control-surface and audio-interface capability registry.",
                ),
                _capability(
                    "decklink_monitoring",
                    "DeckLink-style monitoring and external I/O",
                    supported=_has_truthy_key(hardware_caps, "decklink", "external_monitoring"),
                    partial=_has_truthy_key(hardware_caps, "external_monitoring_model"),
                    action="Add external monitoring/output-device abstraction and calibration checks.",
                ),
            ],
        },
    }

    issues: list[dict[str, Any]] = []
    category_scores: dict[str, int] = {}
    missing_by_category: dict[str, list[str]] = {}
    partial_by_category: dict[str, list[str]] = {}
    implementation_backlog: list[dict[str, Any]] = []
    supported_highlights: list[dict[str, Any]] = []
    for key, category in categories.items():
        features = _as_list(category.get("features"))
        score = _capability_category_score([f for f in features if isinstance(f, dict)])
        category["score"] = score
        category["supported"] = sum(1 for f in features if _as_dict(f).get("status") == "supported")
        category["partial"] = sum(1 for f in features if _as_dict(f).get("status") == "partial")
        category["missing"] = sum(1 for f in features if _as_dict(f).get("status") == "missing")
        category_scores[key] = score
        missing_by_category[key] = [str(f.get("id")) for f in features if _as_dict(f).get("status") == "missing"]
        partial_by_category[key] = [str(f.get("id")) for f in features if _as_dict(f).get("status") == "partial"]
        for feature in features:
            feature = _as_dict(feature)
            status = str(feature.get("status") or "")
            row = {
                "category": key,
                "category_label": str(category.get("label") or key),
                "feature": str(feature.get("id") or ""),
                "label": str(feature.get("label") or feature.get("id") or ""),
                "status": status,
                "action": str(feature.get("action") or ""),
            }
            if status == "supported":
                supported_highlights.append(row)
            elif status in {"missing", "partial"} and row["action"]:
                implementation_backlog.append(row)
        if score < 40:
            first_missing = next((f for f in features if _as_dict(f).get("status") == "missing"), {})
            issues.append(_issue(
                "resolve_post_pipeline_parity",
                "low",
                f"{category.get('label', key)} is far below Resolve/Fairlight/Fusion depth.",
                str(_as_dict(first_missing).get("action") or "Use this parity matrix to prioritize the next product tranche."),
                category=key,
                score=score,
            ))
    if vfx_node_graphs and not bool(vfx_graph_qa.get("ok")):
        issues.append(_issue(
            "resolve_post_pipeline_parity",
            "low",
            "Mini VFX node graph validation has warnings.",
            "Open Mask Editor > VFX Graph and fix missing outputs or node inputs before relying on the compositor payload.",
            category="vfx_fusion",
            warning_count=len(_as_list(vfx_graph_qa.get("warnings"))),
            warnings=_as_list(vfx_graph_qa.get("warnings"))[:4],
        ))
    overall = int(round(sum(category_scores.values()) / max(1, len(category_scores))))
    implementation_backlog.sort(key=lambda row: (0 if row.get("status") == "missing" else 1, int(category_scores.get(str(row.get("category")), 100))))
    professional_depth_cards = _professional_depth_cards(categories)
    professional_depth_actions: list[str] = []
    for card in professional_depth_cards:
        for action in _as_list(card.get("next_actions")) + [card.get("next_depth_action")]:
            text = str(action)
            if text and text not in professional_depth_actions:
                professional_depth_actions.append(text)
    return {
        "advisory": True,
        "score": overall,
        "categories": categories,
        "category_scores": category_scores,
        "missing_by_category": missing_by_category,
        "partial_by_category": partial_by_category,
        "implementation_backlog": implementation_backlog,
        "top_actions": [str(row.get("action")) for row in implementation_backlog[:12] if str(row.get("action") or "")],
        "supported_highlights": supported_highlights[:12],
        "professional_depth_cards": professional_depth_cards,
        "professional_depth_actions": professional_depth_actions[:12],
        "vfx_graph_qa": vfx_graph_qa,
        "issues": issues,
    }


def build_professional_readiness_report(doc: dict[str, Any]) -> dict[str, Any]:
    sections = {
        "long_project_stability": audit_long_project_stability(doc),
        "gpu_preview_export_consistency": audit_gpu_preview_export_consistency(doc),
        "timeline_edit_integrity": audit_timeline_edit_integrity(doc),
        "color_workflow_depth": audit_color_workflow_depth(doc),
        "audio_mix_readiness": audit_audio_mix_readiness(doc),
        "preset_template_ecosystem": audit_preset_template_ecosystem(doc),
        "resolve_post_pipeline_parity": audit_resolve_post_pipeline_parity(doc),
    }
    scored_sections = [
        section
        for section in sections.values()
        if not bool(section.get("advisory"))
    ]
    scores = [int(section.get("score", 0) or 0) for section in scored_sections]
    score = int(round(sum(scores) / max(1, len(scores))))
    issues = [
        issue
        for section in scored_sections
        for issue in section.get("issues", []) or []
    ]
    advisory_issues = [
        issue
        for section in sections.values()
        if bool(section.get("advisory"))
        for issue in section.get("issues", []) or []
    ]
    high_count = sum(1 for issue in issues if issue.get("severity") == "high")
    medium_count = sum(1 for issue in issues if issue.get("severity") == "medium")
    return {
        "ok": score >= 80 and high_count == 0,
        "score": score,
        "issue_summary": {
            "total": len(issues),
            "high": high_count,
            "medium": medium_count,
            "low": sum(1 for issue in issues if issue.get("severity") == "low"),
        },
        "advisory_issue_summary": {
            "total": len(advisory_issues),
            "high": sum(1 for issue in advisory_issues if issue.get("severity") == "high"),
            "medium": sum(1 for issue in advisory_issues if issue.get("severity") == "medium"),
            "low": sum(1 for issue in advisory_issues if issue.get("severity") == "low"),
        },
        "sections": sections,
        "top_actions": [str(issue.get("action") or "") for issue in issues[:8]],
        "advisory_actions": [str(issue.get("action") or "") for issue in advisory_issues[:8]],
    }


def format_professional_readiness_diagnostics(
    report: dict[str, Any] | None,
    *,
    max_actions: int = 5,
) -> str:
    """Return a compact export/render-queue diagnostic string."""
    if not isinstance(report, dict):
        return ""
    issue_summary = _as_dict(report.get("issue_summary"))
    high = int(issue_summary.get("high", 0) or 0)
    medium = int(issue_summary.get("medium", 0) or 0)
    low = int(issue_summary.get("low", 0) or 0)
    score = int(report.get("score", 0) or 0)
    state = "OK" if report.get("ok", False) else "Review"
    lines = [
        f"Professional Readiness: {state} score={score} high={high} medium={medium} low={low}",
    ]
    sections = _as_dict(report.get("sections"))
    section_bits = []
    for key in (
        "long_project_stability",
        "gpu_preview_export_consistency",
        "timeline_edit_integrity",
        "color_workflow_depth",
        "audio_mix_readiness",
        "preset_template_ecosystem",
        "resolve_post_pipeline_parity",
    ):
        section = _as_dict(sections.get(key))
        if section:
            suffix = " advisory" if section.get("advisory") else ""
            section_bits.append(f"{key}={int(section.get('score', 0) or 0)}{suffix}")
    if section_bits:
        lines.append("Readiness Sections: " + ", ".join(section_bits))
    color = _as_dict(sections.get("color_workflow_depth"))
    scope = _as_dict(color.get("scope_accuracy"))
    if scope:
        lines.append(
            "Color Scope QA: "
            f"{'OK' if scope.get('ok') else 'Review'} "
            f"luma_span={float(scope.get('luma_span', 0.0) or 0.0):.2f} "
            f"sat={float(scope.get('saturation_mean', 0.0) or 0.0):.2f}"
        )
    parity = _as_dict(sections.get("resolve_post_pipeline_parity"))
    vfx_graph_qa = _as_dict(parity.get("vfx_graph_qa"))
    if vfx_graph_qa:
        lines.append(
            "VFX Graph QA: "
            f"{'OK' if vfx_graph_qa.get('ok') else 'Review'} "
            f"graphs={int(vfx_graph_qa.get('graph_count', 0) or 0)} "
            f"nodes={int(vfx_graph_qa.get('node_count', 0) or 0)} "
            f"warnings={len(_as_list(vfx_graph_qa.get('warnings')))}"
        )
    else:
        vfx = _as_dict(_as_dict(parity.get("categories")).get("vfx_fusion"))
        for feature in _as_list(vfx.get("features")):
            row = _as_dict(feature)
            if row.get("id") == "node_2d_3d_compositing":
                lines.append(
                    "VFX Graph QA: "
                    f"{row.get('status', 'missing')} | {row.get('evidence', '')}"
                )
                break
    actions = [str(action) for action in report.get("top_actions", []) or [] if str(action)]
    if actions:
        lines.append("Readiness Actions:")
        lines.extend(f"- {action}" for action in actions[:max(0, int(max_actions))])
    return "\n".join(lines)
