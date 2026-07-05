"""Apply CapCut-style creator workflow bundles to project documents.

The workflow planner in :mod:`app.capcut_workflow` produces deterministic
handoff bundles.  This module keeps the next step equally deterministic: merge
that bundle into a project dict without requiring Qt widgets or mutating the
original object.  The editor UI can call the same functions before saving a
project or before handing jobs to the render queue.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping


CAPCUT_SOURCE = "capcut_creator_workflow"


@dataclass
class CapCutApplyResult:
    ok: bool
    project_doc: dict[str, Any]
    operations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "project_doc": self.project_doc,
            "operations": list(self.operations),
            "warnings": list(self.warnings),
            "counts": dict(self.counts),
        }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _deep_merge(base: dict[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in dict(patch or {}).items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = deepcopy(value)
    return base


def _int_ms(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(round(float(value))))
    except Exception:
        return max(0, int(fallback))


def _subtitle_key(row: Mapping[str, Any]) -> tuple[int, int, str, str]:
    style = _as_dict(row.get("style"))
    return (
        _int_ms(row.get("start_ms")),
        _int_ms(row.get("end_ms")),
        " ".join(str(row.get("text", "") or "").split()).casefold(),
        str(row.get("style_preset_id") or style.get("preset_id") or ""),
    )


def _normalize_subtitle_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    text = " ".join(str(row.get("text", "") or "").split())
    if not text:
        return None
    start_ms = _int_ms(row.get("start_ms"))
    end_ms = max(start_ms + 500, _int_ms(row.get("end_ms"), start_ms + 1800))
    style_preset_id = str(row.get("style_preset_id") or _as_dict(row.get("style")).get("preset_id") or "")
    style = dict(_as_dict(row.get("style")))
    if style_preset_id:
        style["preset_id"] = style_preset_id
    style.setdefault("source", CAPCUT_SOURCE)
    style.setdefault("word_highlight", bool(row.get("word_highlight")))
    return {
        "text": text,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "show_box": bool(row.get("show_box", True)),
        "style": style,
        "source": str(row.get("source") or CAPCUT_SOURCE),
    }


def _marker_key(row: Mapping[str, Any]) -> tuple[int, str]:
    return (_int_ms(row.get("ms", row.get("start_ms"))), str(row.get("id") or row.get("label") or ""))


def _normalize_marker_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    start_ms = _int_ms(row.get("start_ms", row.get("ms")))
    label = str(row.get("label") or row.get("id") or "Short").strip()
    if not label:
        return None
    marker = {
        "ms": start_ms,
        "color": str(row.get("color") or "#FF6F61"),
        "label": label,
        "id": str(row.get("id") or f"capcut-marker-{start_ms}"),
        "source": CAPCUT_SOURCE,
    }
    if row.get("end_ms") is not None:
        marker["end_ms"] = max(start_ms + 1, _int_ms(row.get("end_ms"), start_ms + 1000))
    if row.get("score") is not None:
        try:
            marker["score"] = float(row.get("score") or 0.0)
        except Exception:
            marker["score"] = 0.0
    if row.get("reason"):
        marker["reason"] = str(row.get("reason"))
    return marker


def _render_job_key(row: Mapping[str, Any]) -> tuple[str, int, int]:
    kwargs = _as_dict(row.get("create_kwargs")) or row
    return (
        str(kwargs.get("out_path") or row.get("out_path") or ""),
        _int_ms(kwargs.get("in_ms", row.get("in_ms"))),
        _int_ms(kwargs.get("out_ms", row.get("out_ms"))),
    )


def _capcut_generated_subtitle(row: Mapping[str, Any]) -> bool:
    style = _as_dict(row.get("style"))
    return str(row.get("source") or style.get("source") or "").casefold() in {
        CAPCUT_SOURCE,
        "capcut_auto_caption",
    }


def _capcut_generated_marker(row: Mapping[str, Any]) -> bool:
    source = str(row.get("source") or "").casefold()
    marker_id = str(row.get("id") or "").casefold()
    return source == CAPCUT_SOURCE or marker_id.startswith("capcut-")


def capcut_apply_preview(project_doc: Mapping[str, Any] | None, bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a cheap, side-effect-free summary of what applying will add."""
    project = _as_dict(project_doc)
    payload = _as_dict(bundle)
    subtitle_rows = [_normalize_subtitle_row(_as_dict(row)) for row in _as_list(payload.get("subtitle_rows"))]
    marker_rows = [_normalize_marker_row(_as_dict(row)) for row in _as_list(payload.get("timeline_markers"))]
    render_jobs = [_as_dict(row) for row in _as_list(payload.get("render_queue_jobs"))]
    settings_patch = _as_dict(payload.get("project_settings_patch"))
    has_creator_package = any(isinstance(payload.get(key), Mapping) for key in ("hook_score_plan", "caption_beat_plan", "publish_package"))
    warnings: list[str] = []
    if not subtitle_rows:
        warnings.append("No caption rows in bundle; auto-caption apply will only change project settings.")
    if not marker_rows:
        warnings.append("No short-candidate markers in bundle.")
    if not render_jobs:
        warnings.append("No render queue jobs in bundle.")
    if not settings_patch:
        warnings.append("No project settings patch in bundle.")
    return {
        "ok": bool(settings_patch or subtitle_rows or marker_rows or render_jobs),
        "existing": {
            "subtitles": len(_as_list(project.get("subtitles"))),
            "timeline_markers": len(_as_list(project.get("timeline_markers"))),
            "render_queue_jobs": len(_as_list(project.get("render_queue_jobs"))),
        },
        "adds": {
            "subtitles": len([row for row in subtitle_rows if row]),
            "timeline_markers": len([row for row in marker_rows if row]),
            "render_queue_jobs": len(render_jobs),
            "project_settings": 1 if settings_patch else 0,
            "creator_package": 1 if has_creator_package else 0,
        },
        "warnings": warnings,
    }


def capcut_apply_bundle_to_project(
    project_doc: Mapping[str, Any] | None,
    bundle: Mapping[str, Any] | None,
    *,
    replace_existing: bool = False,
) -> CapCutApplyResult:
    """Merge a CapCut creator bundle into a project document.

    The function is intentionally conservative: it preserves user-authored
    subtitles/markers, deduplicates repeated applies, and stores CapCut-specific
    rich metadata as sidecars so older loaders can ignore it.
    """
    project: dict[str, Any] = deepcopy(dict(project_doc or {}))
    payload = _as_dict(bundle)
    operations: list[str] = []
    warnings = list(capcut_apply_preview(project, payload).get("warnings", []))
    counts = {
        "settings_updated": 0,
        "subtitles_added": 0,
        "caption_style_runs_added": 0,
        "markers_added": 0,
        "short_ranges_added": 0,
        "render_queue_jobs_added": 0,
        "creator_package_updated": 0,
    }

    settings = project.setdefault("project_settings", {})
    if not isinstance(settings, dict):
        settings = {}
        project["project_settings"] = settings

    settings_patch = _as_dict(payload.get("project_settings_patch"))
    if settings_patch:
        _deep_merge(settings, settings_patch)
        operations.append("merged project_settings_patch")
        counts["settings_updated"] = 1

    export_settings = _as_dict(payload.get("export_settings"))
    if export_settings:
        export = project.setdefault("export", {})
        if not isinstance(export, dict):
            export = {}
            project["export"] = export
        if export_settings.get("format_id"):
            export["format_id"] = str(export_settings.get("format_id"))
        if export_settings.get("quality_id"):
            export["quality_id"] = str(export_settings.get("quality_id"))
        if export_settings.get("canvas_width") and export_settings.get("canvas_height"):
            export["resolution"] = [int(export_settings["canvas_width"]), int(export_settings["canvas_height"])]
        if export_settings.get("fps"):
            export["fps"] = float(export_settings["fps"])
        export["burn_captions"] = bool(export_settings.get("burn_captions", export.get("burn_captions", True)))
        operations.append("updated export defaults")

    workflow_meta = settings.setdefault("capcut_creator_workflow", {})
    if not isinstance(workflow_meta, dict):
        workflow_meta = {}
        settings["capcut_creator_workflow"] = workflow_meta
    workflow_meta.setdefault("source", CAPCUT_SOURCE)
    workflow_meta["last_platform"] = str(_as_dict(settings_patch.get("capcut_creator_workflow")).get("platform") or workflow_meta.get("platform") or "shorts")

    subtitles = project.setdefault("subtitles", [])
    if not isinstance(subtitles, list):
        subtitles = []
        project["subtitles"] = subtitles
    if replace_existing:
        before = len(subtitles)
        subtitles[:] = [row for row in subtitles if not _capcut_generated_subtitle(_as_dict(row))]
        if before != len(subtitles):
            operations.append(f"removed {before - len(subtitles)} existing CapCut subtitle(s)")
    existing_subtitle_keys = {_subtitle_key(_as_dict(row)) for row in subtitles}
    style_runs = workflow_meta.setdefault("caption_style_runs", [])
    if not isinstance(style_runs, list):
        style_runs = []
        workflow_meta["caption_style_runs"] = style_runs
    if replace_existing:
        style_runs[:] = [row for row in style_runs if str(_as_dict(row).get("source") or "") != CAPCUT_SOURCE]
    existing_style_keys = {
        (_int_ms(_as_dict(row).get("start_ms")), _int_ms(_as_dict(row).get("end_ms")), str(_as_dict(row).get("style_preset_id") or ""))
        for row in style_runs
    }
    for raw in _as_list(payload.get("subtitle_rows")):
        row = _normalize_subtitle_row(_as_dict(raw))
        if row is None:
            continue
        key = _subtitle_key(row)
        if key in existing_subtitle_keys:
            continue
        subtitles.append(row)
        existing_subtitle_keys.add(key)
        counts["subtitles_added"] += 1
        style_preset_id = str(_as_dict(row.get("style")).get("preset_id") or "")
        style_key = (int(row["start_ms"]), int(row["end_ms"]), style_preset_id)
        if style_key not in existing_style_keys:
            style_runs.append({
                "start_ms": int(row["start_ms"]),
                "end_ms": int(row["end_ms"]),
                "style_preset_id": style_preset_id,
                "source": CAPCUT_SOURCE,
                "subtitle_text": row["text"],
            })
            existing_style_keys.add(style_key)
            counts["caption_style_runs_added"] += 1
    if counts["subtitles_added"]:
        operations.append(f"added {counts['subtitles_added']} styled subtitle row(s)")

    markers = project.setdefault("timeline_markers", [])
    if not isinstance(markers, list):
        markers = []
        project["timeline_markers"] = markers
    if replace_existing:
        before = len(markers)
        markers[:] = [row for row in markers if not _capcut_generated_marker(_as_dict(row))]
        if before != len(markers):
            operations.append(f"removed {before - len(markers)} existing CapCut marker(s)")
    existing_marker_keys = {_marker_key(_as_dict(row)) for row in markers}
    for raw in _as_list(payload.get("timeline_markers")):
        marker = _normalize_marker_row(_as_dict(raw))
        if marker is None:
            continue
        key = _marker_key(marker)
        if key in existing_marker_keys:
            continue
        markers.append(marker)
        existing_marker_keys.add(key)
        counts["markers_added"] += 1
    markers.sort(key=lambda row: _int_ms(_as_dict(row).get("ms", 0)))
    if counts["markers_added"]:
        operations.append(f"added {counts['markers_added']} short candidate marker(s)")

    short_ranges = project.setdefault("capcut_short_ranges", [])
    if not isinstance(short_ranges, list):
        short_ranges = []
        project["capcut_short_ranges"] = short_ranges
    if replace_existing:
        short_ranges[:] = [row for row in short_ranges if str(_as_dict(row).get("source") or "") != CAPCUT_SOURCE]
    existing_ranges = {
        (str(_as_dict(row).get("id") or ""), _int_ms(_as_dict(row).get("start_ms")), _int_ms(_as_dict(row).get("end_ms")))
        for row in short_ranges
    }
    for raw in _as_list(payload.get("timeline_markers")):
        row = _as_dict(raw)
        if str(row.get("source") or "").casefold() == "ltx_storyboard" or bool(row.get("storyboard_marker")):
            continue
        if row.get("end_ms") is None:
            continue
        start_ms = _int_ms(row.get("start_ms", row.get("ms")))
        end_ms = max(start_ms + 1, _int_ms(row.get("end_ms"), start_ms + 1000))
        out = {
            "id": str(row.get("id") or f"capcut-short-{len(short_ranges) + 1:02d}"),
            "label": str(row.get("label") or "Short"),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "source": CAPCUT_SOURCE,
            "score": float(row.get("score", 0.0) or 0.0),
            "reason": str(row.get("reason") or "candidate"),
        }
        range_key = (out["id"], start_ms, end_ms)
        if range_key in existing_ranges:
            continue
        short_ranges.append(out)
        existing_ranges.add(range_key)
        counts["short_ranges_added"] += 1
    if counts["short_ranges_added"]:
        operations.append(f"added {counts['short_ranges_added']} short range sidecar(s)")

    render_jobs = project.setdefault("render_queue_jobs", [])
    if not isinstance(render_jobs, list):
        render_jobs = []
        project["render_queue_jobs"] = render_jobs
    if replace_existing:
        render_jobs[:] = [
            row for row in render_jobs
            if str(_as_dict(row).get("source") or _as_dict(_as_dict(row).get("capcut")).get("source") or "") != CAPCUT_SOURCE
        ]
    existing_jobs = {_render_job_key(_as_dict(row)) for row in render_jobs}
    for raw in _as_list(payload.get("render_queue_jobs")):
        row = deepcopy(_as_dict(raw))
        if not row:
            continue
        row.setdefault("source", CAPCUT_SOURCE)
        capcut_meta = row.setdefault("capcut", {})
        if isinstance(capcut_meta, dict):
            capcut_meta.setdefault("source", CAPCUT_SOURCE)
        key = _render_job_key(row)
        if key in existing_jobs:
            continue
        render_jobs.append(row)
        existing_jobs.add(key)
        counts["render_queue_jobs_added"] += 1
    if counts["render_queue_jobs_added"]:
        operations.append(f"staged {counts['render_queue_jobs_added']} render queue job(s)")

    creator_package = {}
    for key in (
        "hook_score_plan",
        "caption_beat_plan",
        "publish_package",
        "edit_recipe",
        "publish_variants",
        "review_panel",
        "publish_handoff",
        "ltx_storyboard",
        "ltx_storyboard_edit_plan",
        "ltx_storyboard_apply_payload",
        "ltx_storyboard_effect_materialization",
        "ltx_storyboard_variations",
        "ltx_storyboard_template_recommendations",
    ):
        value = payload.get(key)
        if isinstance(value, Mapping):
            creator_package[key] = deepcopy(dict(value))
    if creator_package:
        creator_package.setdefault("source", CAPCUT_SOURCE)
        project["capcut_creator_package"] = creator_package
        workflow_meta["creator_package_ready"] = bool(_as_dict(creator_package.get("publish_package")).get("ready"))
        workflow_meta["edit_recipe_ready"] = bool(_as_dict(creator_package.get("edit_recipe")).get("ready"))
        workflow_meta["publish_variants"] = list(_as_dict(creator_package.get("publish_variants")).get("platforms") or [])
        workflow_meta["review_panel_ready"] = bool(_as_dict(creator_package.get("review_panel")).get("ready"))
        workflow_meta["publish_handoff_ready"] = bool(_as_dict(creator_package.get("publish_handoff")).get("ready"))
        workflow_meta["ltx_storyboard_ready"] = bool(_as_dict(creator_package.get("ltx_storyboard")).get("ready"))
        workflow_meta["ltx_storyboard_shots"] = int(_as_dict(creator_package.get("ltx_storyboard")).get("shot_count", 0) or 0)
        workflow_meta["ltx_storyboard_zoom_windows"] = int(_as_dict(_as_dict(creator_package.get("ltx_storyboard_effect_materialization")).get("counts")).get("zoom_windows", 0) or 0)
        workflow_meta["ltx_storyboard_callouts"] = int(_as_dict(_as_dict(creator_package.get("ltx_storyboard_effect_materialization")).get("counts")).get("callouts", 0) or 0)
        workflow_meta["ltx_storyboard_variations"] = int(_as_dict(creator_package.get("ltx_storyboard_variations")).get("variation_count", 0) or 0)
        workflow_meta["ltx_storyboard_template_recommendations"] = int(_as_dict(creator_package.get("ltx_storyboard_template_recommendations")).get("card_count", 0) or 0)
        counts["creator_package_updated"] = 1
        operations.append("updated CapCut creator package sidecar")

    workflow_meta["last_apply_counts"] = dict(counts)
    workflow_meta["workflow_preset_ids"] = list(payload.get("workflow_preset_ids") or [])
    workflow_meta["search_chips"] = list(payload.get("search_chips") or [])
    project["project_settings"] = settings

    ok = bool(operations) or any(value > 0 for value in counts.values())
    return CapCutApplyResult(
        ok=ok,
        project_doc=project,
        operations=operations,
        warnings=warnings,
        counts=counts,
    )


def _render_job_rows_from_payload(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    data = _as_dict(payload)
    if isinstance(data.get("render_queue_jobs"), list):
        return [deepcopy(_as_dict(row)) for row in data.get("render_queue_jobs", []) if isinstance(row, dict)]
    bundle = _as_dict(data.get("apply_bundle"))
    if isinstance(bundle.get("render_queue_jobs"), list):
        return [deepcopy(_as_dict(row)) for row in bundle.get("render_queue_jobs", []) if isinstance(row, dict)]
    return []


def capcut_render_queue_jobs_from_payload(payload: Mapping[str, Any] | None) -> list[Any]:
    """Materialize staged CapCut render jobs as ``RenderQueueJob`` objects."""
    from app.render_queue import RenderQueueJob

    jobs = []
    for row in _render_job_rows_from_payload(payload):
        kwargs = dict(_as_dict(row.get("create_kwargs")) or {
            "label": row.get("label"),
            "out_path": row.get("out_path"),
            "in_ms": row.get("in_ms"),
            "out_ms": row.get("out_ms"),
            "project_path": row.get("project_path", ""),
            "source_path": row.get("source_path", ""),
            "format_id": row.get("format_id", ""),
            "quality_id": row.get("quality_id", ""),
        })
        try:
            kwargs["label"] = str(kwargs.get("label") or "CapCut Short")
            kwargs["out_path"] = str(kwargs.get("out_path") or "")
            kwargs["in_ms"] = _int_ms(kwargs.get("in_ms"))
            kwargs["out_ms"] = max(kwargs["in_ms"] + 1, _int_ms(kwargs.get("out_ms"), kwargs["in_ms"] + 1000))
            kwargs["project_path"] = str(kwargs.get("project_path") or "")
            kwargs["source_path"] = str(kwargs.get("source_path") or "")
            kwargs["format_id"] = str(kwargs.get("format_id") or "mp4")
            kwargs["quality_id"] = str(kwargs.get("quality_id") or "high")
            if not kwargs["out_path"]:
                continue
            job = RenderQueueJob.create(**kwargs)
            diagnostics = str(row.get("diagnostics") or "")
            if diagnostics:
                job.diagnostics = diagnostics
            else:
                job.diagnostics = "CapCut creator workflow staged render job."
            jobs.append(job)
        except Exception:
            continue
    return jobs


def capcut_add_render_jobs_to_store(
    store: Any,
    payload: Mapping[str, Any] | None,
    *,
    dedupe: bool = True,
) -> dict[str, Any]:
    """Append staged CapCut render jobs to a ``RenderQueueStore``-like object."""
    if hasattr(store, "load"):
        try:
            store.load()
        except Exception:
            pass
    existing = set()
    if dedupe:
        for job in getattr(store, "jobs", []) or []:
            existing.add((str(getattr(job, "out_path", "")), _int_ms(getattr(job, "in_ms", 0)), _int_ms(getattr(job, "out_ms", 0))))
    added_ids: list[str] = []
    skipped = 0
    warnings: list[str] = []
    for job in capcut_render_queue_jobs_from_payload(payload):
        key = (str(getattr(job, "out_path", "")), _int_ms(getattr(job, "in_ms", 0)), _int_ms(getattr(job, "out_ms", 0)))
        if dedupe and key in existing:
            skipped += 1
            continue
        try:
            added_ids.append(str(store.add(job)))
            existing.add(key)
        except Exception as exc:
            warnings.append(str(exc))
    return {
        "ok": bool(added_ids) and not warnings,
        "added": len(added_ids),
        "skipped": skipped,
        "job_ids": added_ids,
        "warnings": warnings,
    }
