"""Intake helpers for real Screen Studio cursor sidecars.

The real-recording corpus must not be faked: videos only become
interaction-ready when a matching ``.cursor.json`` contains real cursor,
click, drag, hotkey, and auto-zoomable events.  This module creates
human-fillable templates and a missing-evidence report without writing a
counted sidecar by default.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping


def _safe_stem(path: str | Path, *, fallback: str) -> str:
    text = str(path or "").strip()
    stem = Path(text).name if text else fallback
    stem = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", stem).strip("._-")
    return stem[:90] or fallback


def _target_sidecar_path(video_path: str | Path) -> Path:
    return Path(str(video_path) + ".cursor.json")


def _template_path_for_row(
    row: Mapping[str, Any],
    *,
    template_dir: str | Path,
    next_to_media: bool = False,
) -> Path:
    video = Path(str(row.get("path") or "recording.mp4"))
    if next_to_media:
        return Path(str(video) + ".cursor.template.json")
    slot = str(row.get("slot_id") or "").strip()
    prefix = f"{slot}_" if slot else ""
    return Path(template_dir) / f"{prefix}{_safe_stem(video, fallback='recording')}.cursor.template.json"


def _from_template_command(template_path: str | Path) -> str:
    return (
        "python tools/record_screenstudio_cursor_sidecar.py "
        f"--from-template {json.dumps(str(template_path), ensure_ascii=False)} "
        "--register"
    )


def _missing_requirements(row: Mapping[str, Any]) -> list[str]:
    raw = row.get("missing_interaction_requirements")
    if isinstance(raw, list):
        missing = [str(item) for item in raw if str(item).strip()]
    else:
        missing = []
    if "cursor_sidecar" not in missing and not row.get("cursor_sidecar_ok"):
        missing.append("cursor_sidecar")
    if "click" not in missing and int(row.get("click_event_count", 0) or 0) <= 0:
        missing.append("click")
    if "drag" not in missing and int(row.get("drag_event_count", 0) or 0) <= 0:
        missing.append("drag")
    if "hotkey" not in missing and int(row.get("hotkey_event_count", 0) or 0) <= 0:
        missing.append("hotkey")
    if "auto_zoom" not in missing and int(row.get("auto_zoom_count", 0) or 0) <= 0:
        missing.append("auto_zoom")
    return list(dict.fromkeys(missing))


def _example_events(duration_ms: int) -> list[dict[str, Any]]:
    duration = max(4000, int(duration_ms or 0))
    points = [
        (0.12, 0.28, 0.30, "move", ""),
        (0.18, 0.28, 0.30, "click", ""),
        (0.28, 0.36, 0.36, "drag", ""),
        (0.36, 0.52, 0.48, "release", ""),
        (0.52, 0.70, 0.55, "drag", ""),
        (0.68, 0.78, 0.22, "hotkey", "Ctrl+K"),
    ]
    out = []
    for ratio, x_norm, y_norm, kind, label in points:
        row: dict[str, Any] = {
            "t_ms": int(duration * ratio),
            "x_norm": round(float(x_norm), 4),
            "y_norm": round(float(y_norm), 4),
            "kind": kind,
        }
        if label:
            row["label"] = label
        out.append(row)
    return out


def sidecar_template_for_recording(row: Mapping[str, Any], *, template_path: str | Path | None = None) -> dict[str, Any]:
    """Return a non-counted template for filling a real cursor sidecar."""
    path = str(row.get("path") or "")
    target = _target_sidecar_path(path)
    missing = _missing_requirements(row)
    duration_ms = int(row.get("duration_ms", 0) or 0)
    capture_command = _from_template_command(template_path or "<this-template.cursor.template.json>")
    return {
        "version": 1,
        "kind": "screenstudio_cursor_sidecar_template",
        "source_path": path,
        "slot_id": str(row.get("slot_id") or ""),
        "target_sidecar_path": str(target),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": duration_ms,
        "frame_w": int(row.get("frame_w", 1920) or 1920),
        "frame_h": int(row.get("frame_h", 1080) or 1080),
        "qa_safe": True,
        "counts_for_qa": False,
        "why_not_counted": "This template is not named .cursor.json and contains no events. Fill real captured events, then save as target_sidecar_path.",
        "missing_requirements": missing,
        "required_event_kinds": ["move", "click", "drag", "release", "hotkey"],
        "sidecar_capture_command": capture_command,
        "events": [],
        "example_events": _example_events(duration_ms),
        "instructions": [
            "Do not rename this template as-is.",
            "Fill events with real cursor timestamps and normalized 0..1 coordinates from the recording.",
            "Run sidecar_capture_command after filling events to write a counted .cursor.json.",
            "Alternatively save the completed file exactly as target_sidecar_path after replacing example data with real captured events.",
            "Run tools/qa_screenstudio_real_recording_corpus.py after filling sidecars.",
        ],
    }


def build_screenstudio_sidecar_intake_report(
    *,
    real_corpus_report: Mapping[str, Any] | None = None,
    real_manifest_path: str | Path = "qa_corpus/screenstudio_real_recordings/manifest.json",
    template_dir: str | Path = "debugCapture/screenstudio_sidecar_templates",
    write_templates: bool = False,
    next_to_media: bool = False,
    overwrite: bool = False,
    max_templates: int = 0,
) -> dict[str, Any]:
    """Build a missing-sidecar checklist and optionally write safe templates."""
    if real_corpus_report is None:
        from app.screenstudio_parity import screenstudio_real_recording_corpus_report

        real_corpus_report = screenstudio_real_recording_corpus_report(
            real_manifest_path=real_manifest_path,
            deep_probe=False,
        )
    rows = [dict(row) for row in list((real_corpus_report or {}).get("rows") or []) if isinstance(row, Mapping)]
    out_rows: list[dict[str, Any]] = []
    templates_written = 0
    templates_skipped_existing = 0
    template_limit = max(0, int(max_templates or 0))
    for idx, row in enumerate(rows, start=1):
        missing = _missing_requirements(row)
        needs_work = bool(missing)
        target_sidecar = _target_sidecar_path(str(row.get("path") or ""))
        template_path = _template_path_for_row(row, template_dir=template_dir, next_to_media=next_to_media)
        write_result = "not_requested"
        if write_templates and needs_work and (template_limit <= 0 or templates_written < template_limit):
            try:
                if template_path.exists() and not overwrite:
                    templates_skipped_existing += 1
                    write_result = "exists"
                else:
                    template_path.parent.mkdir(parents=True, exist_ok=True)
                    template_path.write_text(
                        json.dumps(sidecar_template_for_recording(row, template_path=template_path), ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    templates_written += 1
                    write_result = "written"
            except Exception as exc:
                write_result = f"failed:{exc}"
        out_rows.append(
            {
                "index": idx,
                "path": str(row.get("path") or ""),
                "slot_id": str(row.get("slot_id") or ""),
                "state": str(row.get("interaction_quality_state") or ("ready" if not missing else "needs_sidecar")),
                "ready": not missing,
                "missing_requirements": missing,
                "duration_ms": int(row.get("duration_ms", 0) or 0),
                "frame_w": int(row.get("frame_w", 1920) or 1920),
                "frame_h": int(row.get("frame_h", 1080) or 1080),
                "target_sidecar_path": str(target_sidecar),
                "template_path": str(template_path),
                "template_write": write_result,
                "sidecar_capture_command": _from_template_command(template_path),
                "cursor_event_count": int(row.get("cursor_event_count", 0) or 0),
                "click_event_count": int(row.get("click_event_count", 0) or 0),
                "drag_event_count": int(row.get("drag_event_count", 0) or 0),
                "hotkey_event_count": int(row.get("hotkey_event_count", 0) or 0),
                "auto_zoom_count": int(row.get("auto_zoom_count", 0) or 0),
                "warnings": list(row.get("warnings") or [])[:6],
            }
        )
    needs_sidecar = sum(1 for row in out_rows if "cursor_sidecar" in row["missing_requirements"])
    needs_click = sum(1 for row in out_rows if "click" in row["missing_requirements"])
    needs_drag = sum(1 for row in out_rows if "drag" in row["missing_requirements"])
    needs_hotkey = sum(1 for row in out_rows if "hotkey" in row["missing_requirements"])
    needs_auto_zoom = sum(1 for row in out_rows if "auto_zoom" in row["missing_requirements"])
    ready = sum(1 for row in out_rows if row.get("ready"))
    summary = dict((real_corpus_report or {}).get("summary") or {})
    target_min = int(summary.get("target_min", 20) or 20)
    return {
        "ok": True,
        "kind": "screenstudio_sidecar_intake",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "write_templates": bool(write_templates),
        "template_dir": str(template_dir),
        "next_to_media": bool(next_to_media),
        "replacement_claim_unblocked_by_templates": False,
        "summary": {
            "recordings": len(out_rows),
            "ready": ready,
            "needs_work": len(out_rows) - ready,
            "needs_sidecar": needs_sidecar,
            "needs_click": needs_click,
            "needs_drag": needs_drag,
            "needs_hotkey": needs_hotkey,
            "needs_auto_zoom": needs_auto_zoom,
            "templates_written": templates_written,
            "templates_skipped_existing": templates_skipped_existing,
            "target_min": target_min,
            "interaction_ready": int(summary.get("interaction_ready", 0) or 0),
            "cursor_sidecar_ready": int(summary.get("cursor_sidecar_ready", 0) or 0),
            "click_ready": int(summary.get("click_ready", 0) or 0),
            "drag_ready": int(summary.get("drag_ready", 0) or 0),
            "hotkey_ready": int(summary.get("hotkey_ready", 0) or 0),
            "auto_zoom_ready": int(summary.get("auto_zoom_ready", 0) or 0),
        },
        "rows": out_rows,
        "next_actions": [
            "Fill template events with real captured cursor data; do not use example_events as evidence.",
            "Run the row sidecar_capture_command after filling each template to write counted .cursor.json sidecars.",
            "Save completed sidecars using the exact target_sidecar_path values if generating them manually.",
            "Run tools/qa_screenstudio_real_recording_corpus.py after filling sidecars.",
        ],
    }
