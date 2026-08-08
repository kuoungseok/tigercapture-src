"""Measured runtime performance gate for core Painter UI document paths."""
from __future__ import annotations

import copy
import platform
import statistics
import sys
import time
from collections.abc import Callable
from typing import Any


SCHEMA = "tigerstudio.painter.ui.runtime_performance.v1"

_CASES: tuple[tuple[str, str, float, float], ...] = (
    ("normalize", "Normalize document", 100.0, 220.0),
    ("responsive", "Resolve responsive layout", 35.0, 90.0),
    ("layout_diagnostics", "Diagnose layout", 350.0, 750.0),
    ("quick_actions", "Search Quick Actions", 250.0, 550.0),
)

_INTERACTION_CASES: tuple[tuple[str, str, float, float], ...] = (
    ("canvas_initial_load", "Open canvas document", 400.0, 900.0),
    ("pan_zoom", "Pan and zoom canvas", 150.0, 350.0),
    ("selection_refresh", "Refresh selection", 220.0, 500.0),
    ("viewport_resize", "Resize viewport", 180.0, 400.0),
)


def classify_runtime_measurement(
    median_ms: float,
    warning_ms: float,
    block_ms: float,
) -> str:
    if float(median_ms) >= float(block_ms):
        return "blocked"
    if float(median_ms) >= float(warning_ms):
        return "warning"
    return "covered"


def _build_document(object_count: int) -> dict[str, Any]:
    from app.painter_ui_document import create_ui_document

    document = create_ui_document(1440, 900, name="Runtime QA")
    document["objects"] = [
        {
            "id": f"ui-object-{index + 1}",
            "kind": "rectangle",
            "name": f"Object {index + 1}",
            "artboard_id": "artboard-1",
            "parent_id": "",
            "x": float(index % 100) * 18.0,
            "y": float(index // 100) * 18.0,
            "width": 16.0,
            "height": 16.0,
        }
        for index in range(max(1, int(object_count)))
    ]
    return document


def _measure(
    callback: Callable[[], Any],
    *,
    iterations: int,
) -> dict[str, Any]:
    callback()
    samples: list[float] = []
    for _index in range(max(1, int(iterations))):
        started = time.perf_counter()
        callback()
        samples.append((time.perf_counter() - started) * 1000.0)
    return {
        "median_ms": round(float(statistics.median(samples)), 3),
        "minimum_ms": round(float(min(samples)), 3),
        "maximum_ms": round(float(max(samples)), 3),
        "samples_ms": [round(float(sample), 3) for sample in samples],
    }


def run_painter_ui_runtime_performance(
    *,
    object_count: int = 1000,
    iterations: int = 3,
) -> dict[str, Any]:
    """Measure real core calls and classify their median wall-clock time."""

    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_layout_diagnostics import diagnose_ui_layout
    from app.painter_ui_quick_actions import (
        search_painter_ui_quick_actions,
    )
    from app.painter_ui_responsive import resolve_ui_responsive_document

    count = max(1, min(5000, int(object_count)))
    repeat = max(1, min(9, int(iterations)))
    document = _build_document(count)
    callbacks: dict[str, Callable[[], Any]] = {
        "normalize": lambda: normalize_ui_document(document),
        "responsive": lambda: resolve_ui_responsive_document(document),
        "layout_diagnostics": lambda: diagnose_ui_layout(document),
        "quick_actions": lambda: search_painter_ui_quick_actions(
            document,
            "object",
            limit=30,
        ),
    }
    cases: list[dict[str, Any]] = []
    for case_id, label, warning_ms, block_ms in _CASES:
        measurement = _measure(callbacks[case_id], iterations=repeat)
        status = classify_runtime_measurement(
            measurement["median_ms"],
            warning_ms,
            block_ms,
        )
        cases.append(
            {
                "id": case_id,
                "label": label,
                "status": status,
                "warning_ms": warning_ms,
                "block_ms": block_ms,
                **measurement,
            }
        )
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_workspace import PainterUIDesignOverlay

    app = QApplication.instance()
    if app is None:
        raise RuntimeError(
            "Painter UI interaction benchmark requires QApplication"
        )

    def canvas_initial_load() -> None:
        candidate = PainterUIDesignOverlay()
        candidate.resize(1000, 700)
        candidate.set_document(document)
        candidate.show()
        app.processEvents()
        candidate.close()
        candidate.deleteLater()
        app.processEvents()

    overlay = PainterUIDesignOverlay()
    overlay.resize(1000, 700)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    selected_documents: list[dict[str, Any]] = []
    for index in range(2):
        selected = copy.deepcopy(document)
        object_id = f"ui-object-{index + 1}"
        selected["selection"] = {
            "object_id": object_id,
            "object_ids": [object_id],
        }
        selected_documents.append(selected)

    def pan_zoom() -> None:
        overlay.set_view_state(
            {"zoom_percent": 100.0, "offset_x": 0.0, "offset_y": 0.0},
            emit=False,
        )
        for index in range(8):
            overlay.set_zoom_percent(
                90.0 + float(index * 5),
                anchor=QPointF(500.0, 350.0),
            )
            overlay.pan_view(dx=3.0, dy=-2.0)
        app.processEvents()

    selection_index = 0

    def selection_refresh() -> None:
        nonlocal selection_index
        overlay.set_document(selected_documents[selection_index % 2])
        selection_index += 1
        app.processEvents()

    resize_index = 0

    def viewport_resize() -> None:
        nonlocal resize_index
        for index in range(8):
            if (resize_index + index) % 2:
                overlay.resize(920, 640)
            else:
                overlay.resize(1000, 700)
        resize_index += 1
        app.processEvents()

    interaction_callbacks: dict[str, Callable[[], Any]] = {
        "canvas_initial_load": canvas_initial_load,
        "pan_zoom": pan_zoom,
        "selection_refresh": selection_refresh,
        "viewport_resize": viewport_resize,
    }
    try:
        for case_id, label, warning_ms, block_ms in _INTERACTION_CASES:
            measurement = _measure(
                interaction_callbacks[case_id],
                iterations=repeat,
            )
            status = classify_runtime_measurement(
                measurement["median_ms"],
                warning_ms,
                block_ms,
            )
            cases.append(
                {
                    "id": case_id,
                    "label": label,
                    "status": status,
                    "warning_ms": warning_ms,
                    "block_ms": block_ms,
                    **measurement,
                }
            )
    finally:
        overlay.close()
        overlay.deleteLater()
        app.processEvents()
    warning_count = sum(row["status"] == "warning" for row in cases)
    blocked_count = sum(row["status"] == "blocked" for row in cases)
    status = (
        "blocked"
        if blocked_count
        else "warning"
        if warning_count
        else "covered"
    )
    return {
        "schema": SCHEMA,
        "ok": blocked_count == 0,
        "status": status,
        "object_count": count,
        "iterations": repeat,
        "case_count": len(cases),
        "covered_count": sum(row["status"] == "covered" for row in cases),
        "warning_count": warning_count,
        "blocked_count": blocked_count,
        "cases": cases,
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "executable": sys.executable,
        },
        "measurement_policy": {
            "clock": "time.perf_counter",
            "aggregate": "median",
            "warmup_runs": 1,
            "claim_scope": "local_machine_runtime_only",
        },
    }


__all__ = [
    "SCHEMA",
    "classify_runtime_measurement",
    "run_painter_ui_runtime_performance",
]
