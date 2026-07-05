"""Append-only AI action audit log."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


AI_ACTION_LOG_SCHEMA_VERSION = 1


def _default_log_path() -> Path:
    return Path.cwd() / "debugCapture" / "ai_action_log.jsonl"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, child in value.items():
            lowered = str(key).casefold()
            if any(token in lowered for token in ("token", "secret", "password", "api_key", "apikey")):
                out[str(key)] = "<redacted>"
            else:
                out[str(key)] = _redact(child)
        return out
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def append_ai_action_log(
    action: str,
    payload: dict[str, Any] | None = None,
    *,
    log_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(log_path) if log_path is not None else _default_log_path()
    entry = {
        "schema_version": AI_ACTION_LOG_SCHEMA_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": str(action or "unknown"),
        "payload": _redact(dict(payload or {})),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception as exc:
        entry["log_error"] = str(exc)
    return entry


def read_ai_action_log_tail(log_path: str | Path | None = None, limit: int = 50) -> list[dict[str, Any]]:
    path = Path(log_path) if log_path is not None else _default_log_path()
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, int(limit)) :]
    except Exception:
        return []
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows
