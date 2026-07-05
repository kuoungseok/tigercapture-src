"""Helpers for appending actor known-failure quarantine entries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KNOWN_FAILURES = ROOT / "qa_corpus" / "actor_known_failures.json"


def _load(path: Path = DEFAULT_KNOWN_FAILURES) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    rows = payload.get("known_failures")
    if not isinstance(rows, list):
        payload["known_failures"] = []
    return payload


def add_actor_known_failure(
    *,
    kind: str,
    path: str,
    area: str = "loading",
    reason: str = "Quarantined from Actor Loading Manager.",
    issue_codes: list[str] | None = None,
    known_failure_path: Path = DEFAULT_KNOWN_FAILURES,
) -> dict[str, Any]:
    payload = _load(known_failure_path)
    rows = list(payload.get("known_failures", []) or [])
    suffix = str(path).replace("\\", "/")
    root = str(ROOT).replace("\\", "/")
    if suffix.startswith(root):
        suffix = suffix[len(root):].lstrip("/")
    entry_id = f"manager-{str(kind).lower()}-{abs(hash((kind, suffix))) % 1_000_000:06d}"
    entry = {
        "id": entry_id,
        "area": str(area),
        "kind": str(kind).lower(),
        "path_suffix": suffix,
        "issue_codes": list(issue_codes or ["actor_loading_manager_quarantine"]),
        "reason": str(reason),
    }
    for row in rows:
        if isinstance(row, dict) and row.get("kind") == entry["kind"] and row.get("path_suffix") == suffix:
            row.update(entry)
            break
    else:
        rows.append(entry)
    payload["known_failures"] = rows
    known_failure_path.parent.mkdir(parents=True, exist_ok=True)
    known_failure_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return entry
