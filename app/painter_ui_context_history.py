"""Session-local ordering helpers for Painter UI context commands."""
from __future__ import annotations

from collections.abc import Iterable, Sequence


def record_context_action(
    history: Sequence[str] | None,
    action_id: str,
    *,
    limit: int = 8,
) -> list[str]:
    key = str(action_id or "").strip()
    rows = [
        str(item)
        for item in (history or [])
        if str(item) and str(item) != key
    ]
    if key:
        rows.insert(0, key)
    return rows[: max(1, int(limit))]


def recent_available_actions(
    history: Sequence[str] | None,
    available_action_ids: Iterable[str],
    *,
    limit: int = 3,
) -> list[str]:
    available = {str(item) for item in available_action_ids if str(item)}
    rows: list[str] = []
    for item in history or []:
        key = str(item)
        if key in available and key not in rows:
            rows.append(key)
        if len(rows) >= max(0, int(limit)):
            break
    return rows


__all__ = ["recent_available_actions", "record_context_action"]
