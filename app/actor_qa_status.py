"""Small helpers for surfacing actor corpus QA status in UI panels."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STATUS_PATH = Path("debugCapture/actor_corpus_status.json")


def _norm(value: Any) -> str:
    return str(value or "").replace("\\", "/").lower()


def load_actor_qa_status(path: Path | str | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_STATUS_PATH)
    if not source.exists():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def actor_status_for_path(status: dict[str, Any] | None, path: Path | str) -> dict[str, Any]:
    if not isinstance(status, dict):
        return {}
    target = _norm(path)
    target_name = Path(str(path)).name.lower()
    best: dict[str, Any] = {}
    for row in status.get("models", []) or []:
        if not isinstance(row, dict):
            continue
        row_path = _norm(row.get("path"))
        if not row_path:
            continue
        if target == row_path or target.endswith(row_path) or row_path.endswith(target):
            return row
        if target_name and Path(row_path).name.lower() == target_name:
            best = row
    return best


def actor_status_badge(row: dict[str, Any] | None) -> tuple[str, str]:
    if not isinstance(row, dict) or not row:
        return "", ""
    status = str(row.get("status") or "").lower()
    if status == "pass":
        return "QA", "#2f8f5b"
    if status == "risk":
        return "RISK", "#9b7a24"
    if status == "quarantined":
        return "Q", "#6d5fd1"
    if status == "fail":
        return "FAIL", "#b0433f"
    return "", ""


def _compact_list(value: Any, *, limit: int = 5) -> str:
    if isinstance(value, (list, tuple, set)):
        rows = [str(item) for item in value if str(item)]
    elif isinstance(value, dict):
        rows = [f"{key}={val}" for key, val in value.items()]
    elif value:
        rows = [str(value)]
    else:
        rows = []
    if not rows:
        return ""
    shown = rows[:limit]
    suffix = f", +{len(rows) - limit}" if len(rows) > limit else ""
    return ", ".join(shown) + suffix


def actor_status_detail_lines(row: dict[str, Any] | None) -> list[str]:
    """Return readable per-model QA lines for Media Pool metadata."""
    if not isinstance(row, dict) or not row:
        return []
    lines = [f"Actor QA: {str(row.get('status') or 'unknown')}"]
    for key, label in (
        ("kind", "kind"),
        ("model_name", "model"),
        ("stress_tier", "stress"),
        ("risk_score", "risk_score"),
        ("risk_severity", "risk"),
        ("render_status", "render"),
        ("failure_category", "failure"),
        ("golden_status", "baseline"),
    ):
        value = row.get(key)
        if value not in (None, "", [], {}):
            lines.append(f"{label}: {value}")
    for key, label in (
        ("issue_codes", "issues"),
        ("risk_codes", "risks"),
        ("missing_files", "missing"),
        ("missing_dependencies", "missing"),
        ("broken_dependencies", "broken"),
        ("motions_missing", "motions"),
        ("atlas_missing", "atlas"),
        ("moc_missing", "moc"),
    ):
        text = _compact_list(row.get(key))
        if text:
            lines.append(f"{label}: {text}")
    known = row.get("known_failure") if isinstance(row.get("known_failure"), dict) else {}
    if known.get("id"):
        reason = f" ({known.get('reason')})" if known.get("reason") else ""
        lines.append(f"known failure: {known.get('id')}{reason}")
    recommendation = str(row.get("recommendation") or "").strip()
    if recommendation:
        lines.append(f"next: {recommendation}")
    return lines


def actor_status_tooltip(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict) or not row:
        return ""
    lines = actor_status_detail_lines(row)
    known = row.get("known_failure") if isinstance(row.get("known_failure"), dict) else {}
    if known.get("id"):
        lines.append(f"known={known.get('id')}")
    return " | ".join(lines)
