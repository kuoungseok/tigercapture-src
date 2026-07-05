"""Persistent loading and preview-start performance telemetry.

The editor has several expensive first-use paths: Live2D runtime creation,
Spine atlas parsing, AR/PBR mesh import, HDRI upload, and decoder selection.
This module keeps those timings in a small JSONL file so product QA can answer
"what was slow?" without asking users to run a profiler.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def loading_log_path() -> Path:
    raw = os.environ.get("TIGERCAPTURE_LOADING_PERF_LOG", "").strip()
    if raw:
        return Path(raw)
    return ROOT / "debugCapture" / "loading_performance.jsonl"


def _env_enabled() -> bool:
    value = os.environ.get("TIGERCAPTURE_DISABLE_LOADING_PERF", "").strip().lower()
    return value not in {"1", "true", "yes", "on"}


def _stat_payload(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(str(path))
    try:
        st = p.stat()
        return {
            "path_exists": True,
            "source_size": int(st.st_size),
            "source_mtime_ns": int(st.st_mtime_ns),
        }
    except Exception:
        return {"path_exists": False}


def record_loading_event(
    area: str,
    stage: str,
    *,
    path: str | Path | None = None,
    status: str = "ok",
    elapsed_ms: float | int | None = None,
    detail: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one loading-stage event and return the serialized row."""
    row: dict[str, Any] = {
        "ts": time.time(),
        "ts_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "area": str(area or "unknown"),
        "stage": str(stage or "unknown"),
        "status": str(status or "ok"),
        "path": str(path or ""),
        "detail": str(detail or ""),
    }
    if elapsed_ms is not None:
        row["elapsed_ms"] = round(float(elapsed_ms), 2)
    row.update(_stat_payload(path))
    if metadata:
        row["metadata"] = dict(metadata)
    if not _env_enabled():
        return row
    try:
        target = loading_log_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
    return row


class LoadingTimer:
    """Stage timer that records elapsed and delta timings."""

    def __init__(self, area: str, path: str | Path | None = None) -> None:
        self.area = str(area or "unknown")
        self.path = str(path or "")
        self.started_at = time.perf_counter()
        self.last_at = self.started_at

    def mark(
        self,
        stage: str,
        *,
        status: str = "ok",
        detail: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = time.perf_counter()
        row = record_loading_event(
            self.area,
            stage,
            path=self.path,
            status=status,
            elapsed_ms=(now - self.started_at) * 1000.0,
            detail=detail,
            metadata={
                "delta_ms": round((now - self.last_at) * 1000.0, 2),
                **(metadata or {}),
            },
        )
        self.last_at = now
        return row


def loading_performance_report(
    *,
    path: str | Path | None = None,
    limit: int = 300,
    slow_ms: float = 500.0,
) -> dict[str, Any]:
    source = Path(path) if path is not None else loading_log_path()
    rows: list[dict[str, Any]] = []
    if source.exists():
        try:
            lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            lines = []
        for line in lines[-max(1, int(limit)):]:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    by_area = Counter(str(row.get("area") or "unknown") for row in rows)
    by_status = Counter(str(row.get("status") or "unknown") for row in rows)
    elapsed_by_area: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        try:
            elapsed_by_area[str(row.get("area") or "unknown")].append(float(row.get("elapsed_ms") or 0.0))
        except Exception:
            pass
    area_summary = {}
    for area, values in elapsed_by_area.items():
        values = sorted(values)
        if not values:
            continue
        area_summary[area] = {
            "count": len(values),
            "avg_ms": round(sum(values) / len(values), 2),
            "p95_ms": round(values[min(len(values) - 1, int(len(values) * 0.95))], 2),
            "max_ms": round(values[-1], 2),
        }
    slow = [
        row for row in rows
        if float(row.get("elapsed_ms") or 0.0) >= float(slow_ms)
    ]
    slow.sort(key=lambda row: float(row.get("elapsed_ms") or 0.0), reverse=True)
    return {
        "ok": True,
        "path": str(source),
        "event_count": len(rows),
        "by_area": dict(sorted(by_area.items())),
        "by_status": dict(sorted(by_status.items())),
        "area_summary": area_summary,
        "slow_count": len(slow),
        "slowest": slow[:20],
    }
