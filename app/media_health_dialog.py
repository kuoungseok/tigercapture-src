"""Project media health browser for long editing sessions."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from app.media_relink import collect_relinkable_paths


def _pathish(value: Any) -> str | None:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return value
    return None


def _append_path(out: list[str], value: Any) -> None:
    text = _pathish(value)
    if text:
        out.append(text)


def _append_object_paths(out: list[str], obj: Any, attrs: tuple[str, ...]) -> None:
    for attr in attrs:
        _append_path(out, getattr(obj, attr, None))


def _plain_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    if value is None:
        return None
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            data = to_dict()
            return dict(data) if isinstance(data, dict) else None
        except Exception:
            return None
    return None


def _append_vfx_payloads(obj: Any, repair_plans: list[dict[str, Any]], node_graphs: list[dict[str, Any]]) -> None:
    repair = _plain_dict(getattr(obj, "vfx_repair_plan", None))
    if repair is not None:
        repair_plans.append(repair)
    graph = _plain_dict(getattr(obj, "vfx_node_graph", None))
    if graph is None:
        graph = _plain_dict(getattr(obj, "mini_vfx_node_graph", None))
    if graph is not None:
        node_graphs.append(graph)


def _audio_clip_doc(clip: Any) -> dict[str, Any]:
    return {
        "id": int(getattr(clip, "id", 0) or 0),
        "source_path": str(getattr(clip, "source_path", "") or ""),
        "duration_ms": int(getattr(clip, "duration_ms", 0) or 0),
        "offset_ms": int(getattr(clip, "offset_ms", 0) or 0),
        "trim_start_ms": int(getattr(clip, "trim_start_ms", 0) or 0),
        "trim_end_ms": int(getattr(clip, "trim_end_ms", 0) or 0),
        "gain": float(getattr(clip, "gain", 1.0) or 1.0),
        "volume_points": list(getattr(clip, "volume_points", None) or []),
        "effects": dict(getattr(clip, "effects", None) or {}),
    }


def _actor_clip_doc(clip: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": int(getattr(clip, "id", 0) or 0),
        "start_ms": int(getattr(clip, "start_ms", 0) or 0),
        "duration_ms": int(getattr(clip, "duration_ms", 0) or 0),
        "anim_name": str(getattr(clip, "anim_name", "") or ""),
    }
    for attr in (
        "skel_path",
        "atlas_path",
        "texture_path",
        "json_path",
        "model_path",
        "motion_path",
        "moc_path",
    ):
        value = getattr(clip, attr, None)
        if value:
            data[attr] = str(value)
    return data


def _actor_track_doc(track: Any) -> dict[str, Any]:
    return {
        "id": int(getattr(track, "id", 0) or 0),
        "clips": [_actor_clip_doc(clip) for clip in getattr(track, "clips", []) or []],
    }


def _video_clip_doc(clip: Any) -> dict[str, Any]:
    paths: list[str] = []
    _append_path(paths, getattr(clip, "source_path", None))
    data: dict[str, Any] = {
        "id": int(getattr(clip, "id", 0) or 0),
        "source_path": str(getattr(clip, "source_path", "") or ""),
        "source_paths": paths,
        "source_duration_ms": int(getattr(clip, "source_duration_ms", 0) or 0),
        "timeline_in_ms": int(getattr(clip, "timeline_in_ms", 0) or 0),
        "source_in_ms": int(getattr(clip, "source_in_ms", 0) or 0),
        "source_out_ms": int(getattr(clip, "source_out_ms", 0) or 0),
        "linked_audio_id": getattr(clip, "linked_audio_id", None),
        "compound_group_id": getattr(clip, "compound_group_id", None),
        "nested_sequence_id": getattr(clip, "nested_sequence_id", None),
    }
    for attr in ("video_filters", "chroma_key", "stabilizer", "bg_removal", "color_grade"):
        payload = _plain_dict(getattr(clip, attr, None))
        if payload is not None:
            data[attr] = payload
    for attr in ("vfx_repair_plan", "vfx_node_graph", "mini_vfx_node_graph"):
        payload = _plain_dict(getattr(clip, attr, None))
        if payload is not None:
            data[attr] = payload
    masks = []
    for mask in getattr(clip, "masks", []) or []:
        payload = _plain_dict(mask)
        if payload is not None:
            masks.append(payload)
    data["masks"] = masks
    node_graph = getattr(clip, "node_graph", None)
    if node_graph is not None:
        node_data: dict[str, Any] = {}
        try:
            grade = getattr(getattr(node_graph, "color", None), "grade", None)
            grade_payload = _plain_dict(grade)
            if grade_payload is not None:
                node_data["color"] = {"grade": grade_payload}
        except Exception:
            pass
        if node_data:
            data["node_graph"] = node_data
    data["nested_child_clips"] = [
        _video_clip_doc(child)
        for child in getattr(clip, "nested_child_clips", []) or []
    ]
    data["nested_child_tracks"] = [
        [_video_clip_doc(child) for child in nested or []]
        for nested in getattr(clip, "nested_child_tracks", []) or []
    ]
    data["nested_audio_tracks"] = [
        [_audio_clip_doc(child) for child in nested or []]
        for nested in getattr(clip, "nested_audio_tracks", []) or []
    ]
    data["nested_spine_actor_tracks"] = [
        _actor_track_doc(track)
        for track in getattr(clip, "nested_spine_actor_tracks", []) or []
    ]
    data["nested_live2d_actor_tracks"] = [
        _actor_track_doc(track)
        for track in getattr(clip, "nested_live2d_actor_tracks", []) or []
    ]
    return data


def build_editor_media_health_doc(editor: Any) -> dict[str, Any]:
    """Return a lightweight project doc containing every media/model path.

    The relink helpers only need path strings, but the professional-readiness
    audit also needs timeline/effect/audio metadata.  Keep this serializer
    smaller than full project save, while preserving enough current-session
    state to audit without forcing an autosave.
    """
    media_pool: list[str] = []
    video_tracks: list[dict[str, Any]] = []
    audio_tracks: list[dict[str, Any]] = []
    spine_actor_tracks: list[dict[str, Any]] = []
    live2d_actor_tracks: list[dict[str, Any]] = []
    vfx_repair_plans: list[dict[str, Any]] = []
    vfx_node_graphs: list[dict[str, Any]] = []

    pool = getattr(editor, "_media_pool", None)
    if pool is not None and hasattr(pool, "items"):
        try:
            media_pool.extend(str(path) for path in pool.items() if path)
        except Exception:
            pass

    for track in getattr(editor, "_tracks", []) or []:
        track_paths: list[str] = []
        _append_path(track_paths, getattr(track, "source_path", None))
        clip_rows: list[dict[str, Any]] = []
        for clip in getattr(track, "clips", []) or []:
            _append_vfx_payloads(clip, vfx_repair_plans, vfx_node_graphs)
            clip_rows.append(_video_clip_doc(clip))
        for node_item, _masks in list(getattr(track, "node_item_chain", None) or []):
            _append_vfx_payloads(node_item, vfx_repair_plans, vfx_node_graphs)
        video_tracks.append({
            "id": int(getattr(track, "id", len(video_tracks) + 1) or len(video_tracks) + 1),
            "source_path": str(getattr(track, "source_path", "") or ""),
            "source_paths": track_paths,
            "offset_ms": int(getattr(track, "offset_ms", 0) or 0),
            "clips": clip_rows,
        })

    for track in getattr(editor, "_audio_tracks", []) or []:
        audio_tracks.append({
            "id": int(getattr(track, "id", len(audio_tracks) + 1) or len(audio_tracks) + 1),
            "volume": float(getattr(track, "volume", 1.0) or 1.0),
            "pan": float(getattr(track, "pan", 0.0) or 0.0),
            "label": str(getattr(track, "label", "") or ""),
            "bus_id": str(getattr(track, "bus_id", "master") or "master"),
            "automation_points": list(getattr(track, "automation_points", None) or []),
            "clips": [_audio_clip_doc(clip) for clip in getattr(track, "clips", []) or []],
        })

    for track in getattr(editor, "_spine_actor_tracks", []) or []:
        spine_actor_tracks.append(_actor_track_doc(track))

    for track in getattr(editor, "_live2d_actor_tracks", []) or []:
        live2d_actor_tracks.append(_actor_track_doc(track))

    project_settings = dict(getattr(editor, "_project_settings", {}) or {})

    return {
        "project_settings": project_settings,
        "media_pool": media_pool,
        "video_tracks": video_tracks,
        "audio_tracks": audio_tracks,
        "spine_actor_tracks": spine_actor_tracks,
        "live2d_actor_tracks": live2d_actor_tracks,
        "vfx_repair_plans": vfx_repair_plans,
        "vfx_node_graphs": vfx_node_graphs,
    }


def suggest_media_health_roots(
    doc: dict[str, Any],
    project_path: Path | str | None = None,
) -> list[Path]:
    roots: list[Path] = []

    def _add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if resolved not in roots:
            roots.append(resolved)

    if project_path:
        try:
            _add(Path(project_path).parent)
        except Exception:
            pass
    for text in collect_relinkable_paths(doc):
        try:
            p = Path(text)
            if p.exists():
                _add(p.parent)
        except Exception:
            pass
    return roots


def media_health_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in report.get("rows", []) or []:
        row = dict(source)
        status = str(row.get("status", "ok") or "ok")
        proxy_state = str(row.get("proxy_state", "") or "")
        candidate_count = int(row.get("candidate_count", 0) or 0)
        action = {
            "ok": "No action needed.",
            "proxy_missing": "Generate a proxy for smoother preview.",
            "proxy_stale": "Refresh the proxy before editing/export QA.",
            "missing": "Open Relink and choose a replacement.",
            "relink_conflict": "Open Relink and choose one candidate.",
            "filename_collision": "Review duplicate filename references.",
        }.get(status, "Review this media reference.")
        label = {
            "ok": "OK",
            "proxy_missing": "Proxy Missing",
            "proxy_stale": "Proxy Stale",
            "missing": "Missing",
            "relink_conflict": "Relink Conflict",
            "filename_collision": "Duplicate Name",
        }.get(status, status.replace("_", " ").title())
        rows.append({
            "filename": str(row.get("filename", "") or Path(str(row.get("path", ""))).name),
            "path": str(row.get("path", "") or ""),
            "status": status,
            "status_label": label,
            "proxy_state": proxy_state,
            "proxy_path": str(row.get("proxy_path", "") or ""),
            "occurrences": int(row.get("occurrences", 0) or 0),
            "candidate_count": candidate_count,
            "candidates": list(row.get("candidates", []) or []),
            "action": action,
            "raw": row,
        })
    return rows


def professional_readiness_summary_text(report: dict[str, Any]) -> str:
    readiness = report.get("professional_readiness")
    if not isinstance(readiness, dict):
        return ""
    issue_summary = readiness.get("issue_summary", {}) or {}
    return (
        f"readiness {int(readiness.get('score', 0) or 0)} | "
        f"pro issues H{int(issue_summary.get('high', 0) or 0)} "
        f"M{int(issue_summary.get('medium', 0) or 0)}"
    )


def resolve_post_pipeline_parity_detail_lines(readiness: dict[str, Any]) -> list[str]:
    """Return compact Health text for Resolve/Fairlight/Fusion parity gaps."""
    if not isinstance(readiness, dict):
        return []
    sections = readiness.get("sections", {}) or {}
    parity = sections.get("resolve_post_pipeline_parity") if isinstance(sections, dict) else None
    if not isinstance(parity, dict):
        return []
    lines = [
        "",
        "Resolve / Fairlight / Fusion parity (advisory):",
        f"Overall parity score: {int(parity.get('score', 0) or 0)}",
    ]
    categories = parity.get("categories", {}) or {}
    if isinstance(categories, dict):
        for key in (
            "color",
            "audio",
            "vfx_fusion",
            "performance",
            "post_pipeline",
            "hardware_ecosystem",
        ):
            category = categories.get(key)
            if not isinstance(category, dict):
                continue
            lines.append(
                f"- {category.get('label', key)}: "
                f"{int(category.get('score', 0) or 0)} "
                f"(supported {int(category.get('supported', 0) or 0)}, "
                f"partial {int(category.get('partial', 0) or 0)}, "
                f"missing {int(category.get('missing', 0) or 0)})"
            )
    vfx_graph_qa = parity.get("vfx_graph_qa")
    if isinstance(vfx_graph_qa, dict):
        state = "OK" if vfx_graph_qa.get("ok") else "Review"
        lines.append(
            f"VFX graph QA: {state} | "
            f"graphs {int(vfx_graph_qa.get('graph_count', 0) or 0)} | "
            f"nodes {int(vfx_graph_qa.get('node_count', 0) or 0)} | "
            f"warnings {len(list(vfx_graph_qa.get('warnings', []) or []))}"
        )
        warnings = [str(v) for v in list(vfx_graph_qa.get("warnings", []) or []) if str(v)]
        if warnings:
            lines.append("VFX graph warnings: " + "; ".join(warnings[:3]))
    cards = [
        row for row in list(parity.get("professional_depth_cards", []) or [])
        if isinstance(row, dict)
    ]
    if cards:
        lines.append("Professional depth cards:")
        for card in cards[:3]:
            competitor = str(card.get("competitor") or card.get("id") or "")
            level = str(card.get("current_level") or "")
            score = int(card.get("score", 0) or 0)
            lines.append(f"- {competitor}: {score} | {level}")
            blockers = [str(v) for v in list(card.get("why_not_100", []) or []) if str(v)]
            if blockers:
                lines.append(f"  gap: {', '.join(blockers[:3])}")
            actions = [str(v) for v in list(card.get("next_actions", []) or []) if str(v)]
            if actions:
                lines.append(f"  next: {actions[0]}")
            phases = [row for row in list(card.get("phases", []) or []) if isinstance(row, dict)]
            if phases:
                gate = str(phases[0].get("qa_gate") or "")
                if gate:
                    lines.append(f"  QA: {gate}")
    backlog = [
        row for row in list(parity.get("implementation_backlog", []) or [])
        if isinstance(row, dict) and str(row.get("action") or "").strip()
    ]
    if backlog:
        lines.append("Next implementation actions:")
        for row in backlog[:8]:
            status = str(row.get("status") or "")
            label = str(row.get("label") or row.get("feature") or "")
            category = str(row.get("category_label") or row.get("category") or "")
            action = str(row.get("action") or "")
            lines.append(f"- [{status}] {category} / {label}: {action}")
    highlights = [
        row for row in list(parity.get("supported_highlights", []) or [])
        if isinstance(row, dict)
    ]
    if highlights:
        lines.append("Supported highlights:")
        for row in highlights[:6]:
            lines.append(f"- {row.get('category_label', row.get('category'))}: {row.get('label', row.get('feature'))}")
    return lines


def timeline_edge_cleanup_summary_text(report: dict[str, Any]) -> str:
    cleanup = report.get("timeline_edge_cleanup")
    if not isinstance(cleanup, dict):
        return ""
    auto_count = int(cleanup.get("auto_fixable_count", 0) or 0)
    issue_count = int(cleanup.get("issue_count", 0) or 0)
    if issue_count <= 0:
        return "timeline edges clean"
    return f"timeline edges {auto_count} auto-fixable/{issue_count}"


def preset_pack_summary_text(report: dict[str, Any]) -> str:
    packs = report.get("preset_pack_marketplace")
    if not isinstance(packs, dict):
        return ""
    return (
        f"preset packs {int(packs.get('enabled_packs', 0) or 0)}/"
        f"{int(packs.get('total_packs', 0) or 0)} enabled | "
        f"issues {int(packs.get('issue_packs', 0) or 0)}"
    )


def timeline_edge_cleanup_actionable_count(report: dict[str, Any]) -> int:
    cleanup = report.get("timeline_edge_cleanup")
    if not isinstance(cleanup, dict):
        return 0
    tracks = cleanup.get("tracks", []) or []
    if not tracks:
        return int(cleanup.get("auto_fixable_count", 0) or 0)
    total = 0
    for track in tracks:
        if int(track.get("locked", 0) or 0):
            continue
        if "auto_fixable_count" in track:
            total += int(track.get("auto_fixable_count", 0) or 0)
        else:
            total += int(track.get("micro_gap_count", 0) or 0)
            total += int(track.get("micro_overlap_count", 0) or 0)
    return total


def timeline_edge_cleanup_locked_auto_count(report: dict[str, Any]) -> int:
    cleanup = report.get("timeline_edge_cleanup")
    if not isinstance(cleanup, dict):
        return 0
    total = 0
    for track in cleanup.get("tracks", []) or []:
        if not int(track.get("locked", 0) or 0):
            continue
        if "auto_fixable_count" in track:
            total += int(track.get("auto_fixable_count", 0) or 0)
        else:
            total += int(track.get("micro_gap_count", 0) or 0)
            total += int(track.get("micro_overlap_count", 0) or 0)
    return total


def timeline_edge_cleanup_button_text(report: dict[str, Any]) -> str:
    count = timeline_edge_cleanup_actionable_count(report)
    if count <= 0:
        return "Clean Timeline Edges"
    unit = "Edge" if count == 1 else "Edges"
    return f"Clean {count} Timeline {unit}"


def _format_edge_issue(issue: dict[str, Any]) -> str:
    kind = str(issue.get("kind", "edge") or "edge").replace("_", " ")
    left = int(issue.get("left_clip_id", 0) or 0)
    right = int(issue.get("right_clip_id", 0) or 0)
    duration = int(issue.get("duration_ms", 0) or 0)
    start = int(issue.get("start_ms", 0) or 0)
    end = int(issue.get("end_ms", 0) or 0)
    auto = "auto" if int(issue.get("auto_fixable", 0) or 0) else "manual"
    return f"{kind} {duration} ms ({auto}) clips {left}->{right} at {start}-{end} ms"


def timeline_edge_cleanup_detail_lines(report: dict[str, Any]) -> list[str]:
    cleanup = report.get("timeline_edge_cleanup")
    if not isinstance(cleanup, dict):
        return []
    tracks = cleanup.get("tracks", []) or []
    if not tracks and int(cleanup.get("issue_count", 0) or 0) <= 0:
        return ["", "Timeline micro-edge cleanup:", "No same-lane gaps or overlaps detected."]
    lines = [
        "",
        "Timeline micro-edge cleanup:",
        (
            f"Auto-fixable: {int(cleanup.get('auto_fixable_count', 0) or 0)}  |  "
            f"Issues: {int(cleanup.get('issue_count', 0) or 0)}  |  "
            f"Frame: {int(cleanup.get('frame_ms', 0) or 0)} ms"
        ),
    ]
    actionable = timeline_edge_cleanup_actionable_count(report)
    locked_auto = timeline_edge_cleanup_locked_auto_count(report)
    if actionable > 0:
        lines.append(f"Action: {timeline_edge_cleanup_button_text(report)} on unlocked tracks.")
    elif locked_auto > 0:
        lines.append(f"Action: unlock tracks to clean {locked_auto} auto-fixable edge(s).")
    else:
        lines.append("Action: review large gaps/overlaps manually if they are not intentional.")
    for track in tracks[:8]:
        locked = " locked" if int(track.get("locked", 0) or 0) else ""
        lines.append(
            f"- Track {int(track.get('track_id', 0) or 0)}{locked}: "
            f"micro gaps {int(track.get('micro_gap_count', 0) or 0)}, "
            f"micro overlaps {int(track.get('micro_overlap_count', 0) or 0)}, "
            f"large gaps {int(track.get('gap_count', 0) or 0)}, "
            f"large overlaps {int(track.get('overlap_count', 0) or 0)}"
        )
        issue_preview = [
            _format_edge_issue(issue)
            for issue in (track.get("issues", []) or [])[:3]
            if isinstance(issue, dict)
        ]
        lines.extend(f"  - {line}" for line in issue_preview)
    if len(tracks) > 8:
        lines.append(f"- {len(tracks) - 8} more track(s)")
    return lines


def professional_readiness_detail_lines(report: dict[str, Any]) -> list[str]:
    readiness = report.get("professional_readiness")
    if not isinstance(readiness, dict):
        return []
    issue_summary = readiness.get("issue_summary", {}) or {}
    lines = [
        "",
        "Professional readiness:",
        (
            f"Score: {int(readiness.get('score', 0) or 0)}  |  "
            f"High: {int(issue_summary.get('high', 0) or 0)}  |  "
            f"Medium: {int(issue_summary.get('medium', 0) or 0)}  |  "
            f"Low: {int(issue_summary.get('low', 0) or 0)}"
        ),
    ]
    sections = readiness.get("sections", {}) or {}
    if isinstance(sections, dict) and sections:
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
            section = sections.get(key)
            if not isinstance(section, dict):
                continue
            label = key.replace("_", " ")
            suffix = " advisory" if section.get("advisory") else ""
            section_bits.append(f"{label}: {int(section.get('score', 0) or 0)}{suffix}")
        if section_bits:
            lines.append("Sections: " + " | ".join(section_bits))
        color = sections.get("color_workflow_depth")
        if isinstance(color, dict):
            scope = color.get("scope_accuracy")
            if isinstance(scope, dict):
                state = "OK" if scope.get("ok") else "Review"
                lines.append(
                    f"Color scope QA: {state} | "
                    f"luma span {float(scope.get('luma_span', 0.0) or 0.0):.2f} | "
                    f"sat {float(scope.get('saturation_mean', 0.0) or 0.0):.2f}"
                )
                warnings = [str(v) for v in list(scope.get("warnings", []) or []) if str(v)]
                if warnings:
                    lines.append("Color scope warnings: " + "; ".join(warnings[:3]))
    actions = [str(action) for action in readiness.get("top_actions", []) or [] if str(action)]
    if actions:
        lines.append("Top actions:")
        lines.extend(f"- {action}" for action in actions[:6])
    lines.extend(resolve_post_pipeline_parity_detail_lines(readiness))
    return lines


def preset_pack_detail_lines(report: dict[str, Any]) -> list[str]:
    packs = report.get("preset_pack_marketplace")
    if not isinstance(packs, dict):
        return []
    lines = [
        "",
        "Preset pack marketplace:",
        (
            f"Enabled: {int(packs.get('enabled_packs', 0) or 0)}/"
            f"{int(packs.get('total_packs', 0) or 0)}  |  "
            f"Enabled presets: {int(packs.get('enabled_presets', 0) or 0)}  |  "
            f"Issue packs: {int(packs.get('issue_packs', 0) or 0)}"
        ),
    ]
    kind_counts = packs.get("kind_counts", {}) or {}
    if isinstance(kind_counts, dict) and kind_counts:
        lines.append("Kinds: " + ", ".join(f"{k}:{v}" for k, v in list(kind_counts.items())[:8]))
    for action in list(packs.get("recommendations", []) or [])[:4]:
        lines.append(f"- {action}")
    for card in list(packs.get("packs", []) or [])[:5]:
        if not isinstance(card, dict):
            continue
        lines.append(
            f"- {card.get('name', 'pack')}: score {int(card.get('score', 0) or 0)}, "
            f"{card.get('coverage', 'empty')} | {card.get('recommendation', '')}"
        )
    return lines


class MediaHealthDialog(QDialog):
    """Read-only media/proxy health table with an optional Relink shortcut."""

    def __init__(self, report: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Media Health")
        self.setMinimumSize(980, 560)
        self._report = report
        self._rows = media_health_rows(report)
        self._open_relink = False
        self._clean_timeline_edges = False
        self._open_preset_packs = False
        self._open_preset_qa = False
        self._open_preset_corpus = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        counts = report.get("status_counts", {}) or {}
        proxy_counts = report.get("proxy_counts", {}) or {}
        readiness_summary = professional_readiness_summary_text(report)
        edge_summary = timeline_edge_cleanup_summary_text(report)
        pack_summary = preset_pack_summary_text(report)
        health_bits = [bit for bit in (readiness_summary, edge_summary, pack_summary) if bit]
        readiness_suffix = f" | {' | '.join(health_bits)}" if health_bits else ""
        self._summary = QLabel(
            f"Media paths {int(report.get('total_paths', 0) or 0)} | "
            f"issues {sum(v for k, v in counts.items() if k != 'ok')} | "
            f"missing {counts.get('missing', 0) + counts.get('relink_conflict', 0)} | "
            f"stale proxy {proxy_counts.get('stale', 0)}"
            f"{readiness_suffix}"
        )
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Status",
            "File",
            "Proxy",
            "Refs",
            "Candidates",
            "Path",
        ])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.itemSelectionChanged.connect(self._refresh_detail)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self._table, 1)

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMinimumHeight(116)
        root.addWidget(self._detail)

        buttons = QDialogButtonBox()
        self._relink_btn = QPushButton("Open Relink...")
        self._relink_btn.clicked.connect(self._accept_relink)
        buttons.addButton(self._relink_btn, QDialogButtonBox.ButtonRole.ActionRole)
        self._cleanup_edges_btn = QPushButton("Clean Timeline Edges")
        self._cleanup_edges_btn.setToolTip(
            "Close one-frame gaps and trim one-frame overlaps on unlocked video tracks."
        )
        self._cleanup_edges_btn.clicked.connect(self._accept_timeline_cleanup)
        buttons.addButton(self._cleanup_edges_btn, QDialogButtonBox.ButtonRole.ActionRole)
        self._preset_packs_btn = QPushButton("Preset Packs")
        self._preset_packs_btn.setToolTip("Open the preset pack marketplace and conflict manager.")
        self._preset_packs_btn.clicked.connect(self._accept_preset_packs)
        buttons.addButton(self._preset_packs_btn, QDialogButtonBox.ButtonRole.ActionRole)
        self._preset_qa_btn = QPushButton("Preset QA")
        self._preset_qa_btn.setToolTip("Run the preset ecosystem coverage and reference QA report.")
        self._preset_qa_btn.clicked.connect(self._accept_preset_qa)
        buttons.addButton(self._preset_qa_btn, QDialogButtonBox.ButtonRole.ActionRole)
        self._preset_corpus_btn = QPushButton("Corpus QA")
        self._preset_corpus_btn.setToolTip("Run preset application QA against real project fixtures.")
        self._preset_corpus_btn.clicked.connect(self._accept_preset_corpus)
        buttons.addButton(self._preset_corpus_btn, QDialogButtonBox.ButtonRole.ActionRole)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        buttons.addButton(close_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(buttons)

        self._populate()

    def wants_relink(self) -> bool:
        return bool(self._open_relink)

    def wants_timeline_cleanup(self) -> bool:
        return bool(self._clean_timeline_edges)

    def wants_preset_packs(self) -> bool:
        return bool(self._open_preset_packs)

    def wants_preset_qa(self) -> bool:
        return bool(self._open_preset_qa)

    def wants_preset_corpus(self) -> bool:
        return bool(self._open_preset_corpus)

    def _selected_row_index(self) -> int | None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return None
        return int(selected[0].row())

    def _populate(self) -> None:
        self._table.setRowCount(len(self._rows))
        for row_idx, row in enumerate(self._rows):
            values = [
                row["status_label"],
                row["filename"],
                row["proxy_state"],
                str(row["occurrences"]),
                str(row["candidate_count"]),
                row["path"],
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, row_idx)
                if col in (3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._apply_item_color(item, row)
                self._table.setItem(row_idx, col, item)
        if self._rows:
            self._table.selectRow(0)
        self._table.resizeRowsToContents()
        has_relink_issue = any(row["status"] in {"missing", "relink_conflict"} for row in self._rows)
        self._relink_btn.setEnabled(has_relink_issue)
        edge_count = timeline_edge_cleanup_actionable_count(self._report)
        locked_edge_count = timeline_edge_cleanup_locked_auto_count(self._report)
        self._cleanup_edges_btn.setText(timeline_edge_cleanup_button_text(self._report))
        self._cleanup_edges_btn.setEnabled(edge_count > 0)
        if edge_count > 0:
            self._cleanup_edges_btn.setToolTip(
                f"Close or trim {edge_count} one-frame timeline edge(s) on unlocked video tracks."
            )
        elif locked_edge_count > 0:
            self._cleanup_edges_btn.setToolTip(
                f"{locked_edge_count} auto-fixable edge(s) are on locked tracks."
            )
        self._refresh_detail()

    def _apply_item_color(self, item: QTableWidgetItem, row: dict[str, Any]) -> None:
        color = {
            "ok": "#6ecf80",
            "proxy_missing": "#7ab8ff",
            "proxy_stale": "#d8a030",
            "missing": "#d35f5f",
            "relink_conflict": "#d8a030",
            "filename_collision": "#d8a030",
        }.get(str(row.get("status", "")), "")
        if color:
            item.setForeground(QColor(color))

    def _refresh_detail(self) -> None:
        idx = self._selected_row_index()
        if idx is None or not (0 <= idx < len(self._rows)):
            self._detail.setPlainText("No media row selected.")
            return
        row = self._rows[idx]
        lines = [
            f"Status: {row['status_label']}",
            f"Action: {row['action']}",
            f"References: {row['occurrences']}  |  Candidates: {row['candidate_count']}",
            f"Path: {row['path']}",
        ]
        if row.get("proxy_path"):
            lines.append(f"Proxy: {row['proxy_state']}  |  {row['proxy_path']}")
        if row.get("candidates"):
            preview = "\n".join(str(path) for path in row["candidates"][:8])
            lines.append(f"Candidates:\n{preview}")
        lines.extend(timeline_edge_cleanup_detail_lines(self._report))
        lines.extend(professional_readiness_detail_lines(self._report))
        lines.extend(preset_pack_detail_lines(self._report))
        self._detail.setPlainText("\n".join(lines))

    def _accept_relink(self) -> None:
        self._open_relink = True
        self.accept()

    def _accept_timeline_cleanup(self) -> None:
        self._clean_timeline_edges = True
        self.accept()

    def _accept_preset_packs(self) -> None:
        self._open_preset_packs = True
        self.accept()

    def _accept_preset_qa(self) -> None:
        self._open_preset_qa = True
        self.accept()

    def _accept_preset_corpus(self) -> None:
        self._open_preset_corpus = True
        self.accept()
