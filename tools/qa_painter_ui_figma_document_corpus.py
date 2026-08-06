from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import copy
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
from statistics import median
import sys
from time import get_clock_info, perf_counter_ns
from typing import Any, Callable, Iterable, Iterator, Mapping
import zipfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.fetch_painter_ui_figma_document_corpus import (  # noqa: E402
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT_ROOT,
    FigmaCorpusError,
    _read_manifest as _read_fetch_manifest,
    _safe_relative_path,
)


_NODE_FEATURES = {
    "BOOLEAN_OPERATION": "boolean_operation",
    "COMPONENT": "component",
    "COMPONENT_SET": "component_set",
    "ELLIPSE": "ellipse",
    "GROUP": "group",
    "INSTANCE": "instance",
    "LINE": "line",
    "REGULAR_POLYGON": "vector",
    "POLYGON": "vector",
    "SECTION": "section",
    "STAR": "vector",
    "TEXT": "text",
    "TEXT_PATH": "text",
    "VECTOR": "vector",
}
_PAINT_FEATURES = {
    "GRADIENT_ANGULAR": "gradient_angular",
    "GRADIENT_DIAMOND": "gradient_diamond",
    "GRADIENT_LINEAR": "gradient_linear",
    "GRADIENT_RADIAL": "gradient_radial",
    "IMAGE": "image_fill",
    "SOLID": "solid_fill",
}
_KNOWN_CONTAINER_TYPES = {
    "CANVAS",
    "DOCUMENT",
    "FRAME",
    "RECTANGLE",
    "SLICE",
    "SLOT",
}
_EXPLICITLY_BLOCKED_TYPES = {
    "CODE_BLOCK",
    "CONNECTOR",
    "EMBED",
    "HIGHLIGHT",
    "LINK_UNFURL",
    "MEDIA",
    "SHAPE_WITH_TEXT",
    "STAMP",
    "STICKY",
    "TABLE",
    "TABLE_CELL",
    "WASHI_TAPE",
    "WIDGET",
}

_QT_APPLICATION: Any = None
_MAX_ARTBOARD_RENDER_COUNT = 16
# Count both the actual and empty-baseline QImages.  The whole-document smoke
# consumes one pair; the remaining budget is available to focused artboards.
# This keeps an accidental 4096x4096 request from multiplying into hundreds of
# megapixels while leaving the normal 960x640/default-four run unconstrained.
_MAX_RENDER_PIXEL_WORK = 64 * 1024 * 1024
_RENDER_ATTEMPT_STATUSES = {"passed", "blank", "content_missing", "error"}
_VECTOR_GEOMETRY_NODE_TYPES = {
    "BOOLEAN_OPERATION",
    "LINE",
    "POLYGON",
    "REGULAR_POLYGON",
    "STAR",
    "VECTOR",
}
_PERFORMANCE_PHASES = (
    "load",
    "scan",
    "import",
    "roundtrip",
    "preflight",
    "package",
    "render",
)
_PERFORMANCE_CORE_PHASES = (
    "load",
    "scan",
    "import",
    "roundtrip",
    "preflight",
    "package",
)
_DEFAULT_MAX_PERFORMANCE_REGRESSION_PERCENT = 15.0
_PERFORMANCE_REGRESSION_ERROR = "performance_regression_exceeded"
_PERFORMANCE_NOT_COMPARABLE_ERROR = "performance_baseline_not_comparable"
_CORPUS_REPORT_SCHEMA = "tigercapture.painter.figma_document_corpus_report.v1"
_PERFORMANCE_SCHEMA = (
    "tigercapture.painter.figma_document_corpus_performance.v2"
)
_PERFORMANCE_PROFILE_SCHEMA = (
    "tigercapture.painter.figma_document_corpus_perf_profile.v2"
)
_PERFORMANCE_WORKLOAD_SCHEMA = (
    "tigercapture.painter.figma_document_corpus_perf_workload.v1"
)
_PERFORMANCE_METRIC_VERSION = "total_case_non_render_core_ns.v2"
_MAX_SELECTOR_IMAGE_REFS = 128
_MAX_SELECTOR_IMAGE_BYTES = 128 * 1024 * 1024


class _CasePhaseTimings:
    """Record monotonic phase durations while keeping failed phases visible."""

    def __init__(
        self,
        clock_ns: Callable[[], int],
        *,
        clock_name: str = "perf_counter_ns",
    ) -> None:
        self._clock_ns = clock_ns
        self._clock_name = str(clock_name)
        self._phases: dict[str, dict[str, Any]] = {
            phase: {
                "status": "not_applicable",
                "duration_ns": None,
                "invocation_count": 0,
            }
            for phase in _PERFORMANCE_PHASES
        }

    @contextmanager
    def measure(self, phase: str) -> Iterator[None]:
        started_ns = int(self._clock_ns())
        try:
            yield
        except Exception:
            self._finish(phase, started_ns, status="error")
            raise
        else:
            self._finish(phase, started_ns, status="measured")

    def _finish(self, phase: str, started_ns: int, *, status: str) -> None:
        elapsed_ns = max(0, int(self._clock_ns()) - int(started_ns))
        previous = self._phases[phase]
        previous_duration = previous.get("duration_ns")
        if previous_duration is not None:
            elapsed_ns += int(previous_duration)
        if previous.get("status") == "error":
            status = "error"
        self._phases[phase] = {
            "status": status,
            "duration_ns": elapsed_ns,
            "invocation_count": int(previous.get("invocation_count") or 0)
            + 1,
        }

    def report(self) -> dict[str, Any]:
        core_durations = [
            int(self._phases[phase]["duration_ns"])
            for phase in _PERFORMANCE_CORE_PHASES
            if self._phases[phase]["status"] == "measured"
        ]
        required = [
            phase
            for phase in _PERFORMANCE_CORE_PHASES
            if phase != "package"
            or self._phases[phase]["status"] != "not_applicable"
        ]
        core_complete = all(
            self._phases[phase]["status"] == "measured"
            for phase in required
        )
        return {
            "clock": self._clock_name,
            "phases": copy.deepcopy(self._phases),
            "non_render_core": {
                "status": "measured" if core_complete else "incomplete",
                "duration_ns": sum(core_durations) if core_complete else None,
                "included_phases": [
                    phase
                    for phase in _PERFORMANCE_CORE_PHASES
                    if self._phases[phase]["status"] == "measured"
                ],
                "excluded_phases": ["render"],
            },
        }


def _performance_profile(*, clock_name: str = "perf_counter_ns") -> dict[str, Any]:
    node = platform.node().strip().casefold()
    injected_clock = str(clock_name) != "perf_counter_ns"
    clock_info = None if injected_clock else get_clock_info("perf_counter")
    try:
        import PySide6
        from PySide6.QtCore import qVersion

        qt_profile = {
            "binding": "PySide6",
            "binding_version": str(PySide6.__version__),
            "qt_version": str(qVersion()),
        }
    except (ImportError, AttributeError):
        qt_profile = {"binding": "unavailable"}
    return {
        "schema": _PERFORMANCE_PROFILE_SCHEMA,
        "machine": {
            "node_sha256": hashlib.sha256(node.encode("utf-8")).hexdigest(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
        },
        "runtime": {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "qt": qt_profile,
        },
        "measurement": {
            "clock": str(clock_name),
            "clock_implementation": (
                "injected_callable"
                if injected_clock
                else clock_info.implementation
            ),
            "clock_resolution_ns": (
                None
                if injected_clock
                else int(clock_info.resolution * 1_000_000_000)
            ),
            "clock_monotonic": (
                None if injected_clock else bool(clock_info.monotonic)
            ),
            "clock_adjustable": (
                None if injected_clock else bool(clock_info.adjustable)
            ),
            "metric_version": _PERFORMANCE_METRIC_VERSION,
        },
    }


def _performance_workload_identity(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Fingerprint the exact licensed artifacts represented by a full report."""

    row_list = list(rows)
    if not row_list:
        raise FigmaCorpusError("Performance workload must contain cases")
    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(row_list):
        if not isinstance(row, Mapping):
            raise FigmaCorpusError(
                f"Performance workload case {index} must be an object"
            )
        case_id = str(row.get("id") or "").strip()
        if not case_id or case_id in seen_ids:
            raise FigmaCorpusError(
                "Performance workload case ids must be non-empty and unique"
            )
        seen_ids.add(case_id)
        artifact = row.get("artifact")
        artifact = artifact if isinstance(artifact, Mapping) else {}
        provenance = row.get("provenance")
        provenance = provenance if isinstance(provenance, Mapping) else {}
        selector = row.get("selector")
        selector = selector if isinstance(selector, Mapping) else {}
        cases.append(
            {
                "id": case_id,
                "format": str(row.get("format") or ""),
                "artifact_sha256": str(artifact.get("sha256") or ""),
                "artifact_bytes": artifact.get("bytes"),
                "source_commit": str(provenance.get("commit") or ""),
                "source_path": str(provenance.get("path") or ""),
                "selector_sha256": str(
                    selector.get("subtree_sha256") or ""
                ),
            }
        )
    payload = {
        "schema": _PERFORMANCE_WORKLOAD_SCHEMA,
        "cases": cases,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        "schema": _PERFORMANCE_WORKLOAD_SCHEMA,
        "case_count": len(cases),
        "fingerprint_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _aggregate_performance(
    rows: Iterable[Mapping[str, Any]],
    *,
    case_ids: list[str],
    options: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    row_list = list(rows)
    phase_aggregates: dict[str, dict[str, Any]] = {}
    for phase in _PERFORMANCE_PHASES:
        durations = [
            int(row["performance"]["phases"][phase]["duration_ns"])
            for row in row_list
            if row.get("performance", {})
            .get("phases", {})
            .get(phase, {})
            .get("status")
            in {"measured", "error"}
            and row["performance"]["phases"][phase].get("duration_ns")
            is not None
        ]
        phase_aggregates[phase] = {
            "sample_count": len(durations),
            "total_ns": sum(durations),
            "median_ns": median(durations) if durations else None,
        }

    core_durations = [
        int(row["performance"]["non_render_core"]["duration_ns"])
        for row in row_list
        if row.get("performance", {})
        .get("non_render_core", {})
        .get("status")
        == "measured"
    ]
    complete = bool(row_list) and len(core_durations) == len(row_list)
    return {
        "schema": _PERFORMANCE_SCHEMA,
        "measurement_status": "measured" if complete else "incomplete",
        "profile": copy.deepcopy(dict(profile)),
        "case_ids": list(case_ids),
        "workload": _performance_workload_identity(row_list),
        "options": copy.deepcopy(dict(options)),
        "phase_aggregates": phase_aggregates,
        "metric": {
            "name": "total_case_non_render_core_ns",
            "status": "measured" if complete else "unavailable",
            "value_ns": sum(core_durations) if complete else None,
            "sample_count": len(core_durations),
            "diagnostic_median_case_ns": (
                median(core_durations) if complete else None
            ),
            "rationale": (
                "Sum of like-for-like per-case load+scan+import+roundtrip"
                "+preflight+applicable-package time so a large-case regression "
                "cannot be hidden by a heterogeneous case median; the median "
                "is diagnostic only, and render is reported but excluded because "
                "Qt rasterization and PNG I/O are comparatively noisy."
            ),
        },
    }


def compare_performance_reports(
    current_report: Mapping[str, Any],
    baseline_report: Mapping[str, Any] | None,
    *,
    max_regression_percent: float = _DEFAULT_MAX_PERFORMANCE_REGRESSION_PERCENT,
) -> dict[str, Any]:
    """Compare like-for-like corpus timing reports without false passes."""
    limit = float(max_regression_percent)
    if not math.isfinite(limit) or limit < 0.0:
        raise FigmaCorpusError(
            "Maximum performance regression percent must be finite and non-negative"
        )
    if baseline_report is None:
        return {
            "status": "not_enforced",
            "reason": "performance_baseline_not_provided",
            "max_regression_percent": limit,
        }

    current = current_report.get("performance")
    baseline = baseline_report.get("performance")
    if not isinstance(current, Mapping) or not isinstance(baseline, Mapping):
        return {
            "status": "not_comparable",
            "reasons": ["performance_section_missing"],
            "max_regression_percent": limit,
        }

    reasons: list[str] = []
    if (
        current_report.get("schema") != _CORPUS_REPORT_SCHEMA
        or baseline_report.get("schema") != _CORPUS_REPORT_SCHEMA
    ):
        reasons.append("full_report_schema_mismatch")

    def _validated_cases(
        report: Mapping[str, Any],
        performance: Mapping[str, Any],
        label: str,
    ) -> tuple[list[Mapping[str, Any]], list[str], dict[str, Any] | None]:
        raw_cases = report.get("cases")
        if (
            not isinstance(raw_cases, list)
            or not raw_cases
            or any(not isinstance(row, Mapping) for row in raw_cases)
        ):
            reasons.append("corpus_cases_missing")
            reasons.append(f"{label}_corpus_cases_invalid")
            return [], [], None
        report_count = report.get("case_count")
        if (
            isinstance(report_count, bool)
            or not isinstance(report_count, int)
            or report_count != len(raw_cases)
        ):
            reasons.append(f"{label}_case_count_invalid")
        ids = [str(row.get("id") or "").strip() for row in raw_cases]
        if any(not case_id for case_id in ids) or len(set(ids)) != len(ids):
            reasons.append(f"{label}_case_ids_invalid")
        performance_ids = performance.get("case_ids")
        if (
            not isinstance(performance_ids, list)
            or not performance_ids
            or any(
                not isinstance(case_id, str) or not case_id.strip()
                for case_id in performance_ids
            )
            or len(set(performance_ids)) != len(performance_ids)
            or performance_ids != ids
        ):
            reasons.append(f"{label}_performance_case_ids_invalid")
        try:
            identity = _performance_workload_identity(raw_cases)
        except (FigmaCorpusError, TypeError, ValueError):
            reasons.append(f"{label}_workload_cases_invalid")
            identity = None
        if identity is not None and performance.get("workload") != identity:
            reasons.append(f"{label}_workload_identity_invalid")
        return raw_cases, ids, identity

    current_cases, current_ids, current_identity = _validated_cases(
        current_report, current, "current"
    )
    baseline_cases, baseline_ids, baseline_identity = _validated_cases(
        baseline_report, baseline, "baseline"
    )

    def _validated_case_duration_total(
        cases: list[Mapping[str, Any]],
        label: str,
    ) -> int | None:
        if not cases:
            return None
        total = 0
        valid = True
        for index, row in enumerate(cases):
            case_performance = row.get("performance")
            if not isinstance(case_performance, Mapping):
                reasons.append(f"{label}_case_performance_invalid")
                valid = False
                continue
            core = case_performance.get("non_render_core")
            if not isinstance(core, Mapping) or core.get("status") != "measured":
                reasons.append(f"{label}_case_non_render_core_invalid")
                valid = False
                continue
            core_duration = core.get("duration_ns")
            if (
                isinstance(core_duration, bool)
                or not isinstance(core_duration, int)
                or core_duration < 0
            ):
                reasons.append(f"{label}_case_non_render_core_invalid")
                valid = False
                continue
            phases = case_performance.get("phases")
            if not isinstance(phases, Mapping):
                reasons.append(f"{label}_case_core_phases_invalid")
                valid = False
                continue
            measured_phases: list[str] = []
            phase_total = 0
            phase_valid = True
            for phase in _PERFORMANCE_CORE_PHASES:
                phase_row = phases.get(phase)
                if not isinstance(phase_row, Mapping):
                    phase_valid = False
                    continue
                status = phase_row.get("status")
                duration = phase_row.get("duration_ns")
                allowed_statuses = (
                    {"measured", "not_applicable"}
                    if phase == "package"
                    else {"measured"}
                )
                if status not in allowed_statuses:
                    phase_valid = False
                    continue
                if status == "measured":
                    if (
                        isinstance(duration, bool)
                        or not isinstance(duration, int)
                        or duration < 0
                    ):
                        phase_valid = False
                        continue
                    measured_phases.append(phase)
                    phase_total += duration
                elif duration is not None:
                    phase_valid = False
            included_phases = core.get("included_phases")
            if included_phases != measured_phases:
                phase_valid = False
            if not phase_valid:
                reasons.append(f"{label}_case_core_phases_invalid")
                valid = False
                continue
            if phase_total != core_duration:
                reasons.append(f"{label}_case_core_duration_mismatch")
                valid = False
                continue
            total += core_duration
        return total if valid else None

    current_case_duration_total = _validated_case_duration_total(
        current_cases, "current"
    )
    baseline_case_duration_total = _validated_case_duration_total(
        baseline_cases, "baseline"
    )
    if (
        current_identity is not None
        and baseline_identity is not None
        and current_identity != baseline_identity
    ):
        reasons.append("workload_mismatch")
    if (
        current.get("schema") != _PERFORMANCE_SCHEMA
        or baseline.get("schema") != _PERFORMANCE_SCHEMA
    ):
        reasons.append("performance_schema_mismatch")
    if current.get("measurement_status") != "measured":
        reasons.append("current_measurement_status_invalid")
    if baseline.get("measurement_status") != "measured":
        reasons.append("baseline_measurement_status_invalid")
    if current_ids and baseline_ids and current_ids != baseline_ids:
        reasons.append("case_ids_mismatch")
    current_options = current.get("options")
    baseline_options = baseline.get("options")
    if not isinstance(current_options, Mapping) or not isinstance(
        baseline_options, Mapping
    ):
        reasons.append("options_invalid")
    elif current_options != baseline_options:
        reasons.append("options_mismatch")
    current_profile = current.get("profile")
    baseline_profile = baseline.get("profile")
    profiles_valid = True
    for label, profile in (
        ("current", current_profile),
        ("baseline", baseline_profile),
    ):
        if not isinstance(profile, Mapping):
            reasons.append(f"{label}_profile_invalid")
            profiles_valid = False
            continue
        if profile.get("schema") != _PERFORMANCE_PROFILE_SCHEMA:
            reasons.append(f"{label}_profile_schema_invalid")
            profiles_valid = False
        measurement = profile.get("measurement")
        if not isinstance(measurement, Mapping):
            reasons.append(f"{label}_profile_measurement_invalid")
            profiles_valid = False
        elif measurement.get("metric_version") != _PERFORMANCE_METRIC_VERSION:
            reasons.append(f"{label}_metric_version_invalid")
            profiles_valid = False
    if profiles_valid and current_profile != baseline_profile:
        reasons.append("profile_mismatch")
    current_metric = current.get("metric")
    baseline_metric = baseline.get("metric")
    if not isinstance(current_metric, Mapping) or not isinstance(
        baseline_metric, Mapping
    ):
        reasons.append("metric_missing")
    elif (
        current_metric.get("name") != "total_case_non_render_core_ns"
        or baseline_metric.get("name") != "total_case_non_render_core_ns"
    ):
        reasons.append("metric_mismatch")
    elif (
        current_metric.get("status") != "measured"
        or baseline_metric.get("status") != "measured"
        or current_metric.get("value_ns") is None
        or baseline_metric.get("value_ns") is None
    ):
        reasons.append("metric_unavailable")
    current_sample_count = (
        current_metric.get("sample_count")
        if isinstance(current_metric, Mapping)
        else None
    )
    baseline_sample_count = (
        baseline_metric.get("sample_count")
        if isinstance(baseline_metric, Mapping)
        else None
    )
    expected_current_samples = len(current_cases)
    expected_baseline_samples = len(baseline_cases)
    if (
        isinstance(current_sample_count, bool)
        or not isinstance(current_sample_count, int)
        or current_sample_count != expected_current_samples
        or isinstance(baseline_sample_count, bool)
        or not isinstance(baseline_sample_count, int)
        or baseline_sample_count != expected_baseline_samples
    ):
        reasons.append("metric_sample_count_mismatch")
    current_value = (
        current_metric.get("value_ns")
        if isinstance(current_metric, Mapping)
        else None
    )
    baseline_value = (
        baseline_metric.get("value_ns")
        if isinstance(baseline_metric, Mapping)
        else None
    )
    if (
        isinstance(current_value, bool)
        or not isinstance(current_value, int)
        or current_value < 0
        or isinstance(baseline_value, bool)
        or not isinstance(baseline_value, int)
        or baseline_value <= 0
    ):
        reasons.append("metric_value_invalid")
    if (
        current_case_duration_total is not None
        and isinstance(current_value, int)
        and not isinstance(current_value, bool)
        and current_case_duration_total != current_value
    ):
        reasons.append("current_case_metric_sum_mismatch")
    if (
        baseline_case_duration_total is not None
        and isinstance(baseline_value, int)
        and not isinstance(baseline_value, bool)
        and baseline_case_duration_total != baseline_value
    ):
        reasons.append("baseline_case_metric_sum_mismatch")
    reasons = list(dict.fromkeys(reasons))
    if reasons:
        return {
            "status": "not_comparable",
            "reasons": reasons,
            "max_regression_percent": limit,
        }

    current_ns = float(current_value)
    baseline_ns = float(baseline_value)
    regression_percent = ((current_ns / baseline_ns) - 1.0) * 100.0
    current_decimal = Decimal(current_value)
    baseline_decimal = Decimal(baseline_value)
    limit_decimal = Decimal(str(limit))
    allowed_decimal = baseline_decimal * (
        Decimal("1") + limit_decimal / Decimal("100")
    )
    exceeded = current_decimal > allowed_decimal
    return {
        "status": "failed" if exceeded else "passed",
        "metric": str(current_metric["name"]),
        "current_ns": current_ns,
        "baseline_ns": baseline_ns,
        "regression_percent": regression_percent,
        "max_regression_percent": limit,
        "error": _PERFORMANCE_REGRESSION_ERROR if exceeded else "",
    }


def _walk(value: object, *, parent_key: str = "") -> Iterable[tuple[Mapping[str, Any], str]]:
    if isinstance(value, Mapping):
        yield value, parent_key
        for key, child in value.items():
            yield from _walk(child, parent_key=str(key))
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child, parent_key=parent_key)


def _finite_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _valid_figma_size(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and _finite_number(value.get("x"))
        and _finite_number(value.get("y"))
    )


def _valid_figma_relative_transform(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(
            isinstance(axis, list)
            and len(axis) >= 3
            and all(_finite_number(component) for component in axis[:3])
            for axis in value
        )
    )


def _figma_geometry_paths(node: Mapping[str, Any]) -> list[str]:
    return [
        str(row.get("path") or "").strip()
        for field in ("fillGeometry", "strokeGeometry")
        for row in (
            node.get(field) if isinstance(node.get(field), list) else []
        )
        if isinstance(row, Mapping) and str(row.get("path") or "").strip()
    ]


def _figma_vector_is_render_relevant(node: Mapping[str, Any]) -> bool:
    try:
        node_opacity = float(node.get("opacity", 1.0) or 0.0)
    except (TypeError, ValueError):
        node_opacity = 0.0
    if node.get("visible") is False or node_opacity <= 0.0:
        return False
    for field in ("fills", "strokes"):
        paints = node.get(field)
        if not isinstance(paints, list):
            continue
        for paint in paints:
            if not isinstance(paint, Mapping) or paint.get("visible") is False:
                continue
            try:
                paint_opacity = float(paint.get("opacity", 1.0) or 0.0)
            except (TypeError, ValueError):
                paint_opacity = 0.0
            if paint_opacity > 0.0:
                return True
    return bool(node.get("isMask"))


def source_vector_geometry_inventory(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Separate real geometry=paths evidence from type-only REST placeholders."""
    node_type_counts: Counter[str] = Counter()
    complete_type_counts: Counter[str] = Counter()
    incomplete_type_counts: Counter[str] = Counter()
    incomplete_reason_counts: Counter[str] = Counter()
    incomplete_examples: list[dict[str, Any]] = []
    complete_count = 0
    incomplete_count = 0
    render_relevant_incomplete_count = 0
    for row, _parent_key in _walk(payload):
        type_name = str(row.get("type") or "").upper()
        if (
            type_name not in _VECTOR_GEOMETRY_NODE_TYPES
            or not str(row.get("id") or "")
        ):
            continue
        node_type_counts[type_name] += 1
        paths = _figma_geometry_paths(row)
        reasons: list[str] = []
        if not paths:
            reasons.append("missing_geometry_paths")
        if not _valid_figma_size(row.get("size")):
            reasons.append("missing_or_invalid_size")
        if not _valid_figma_relative_transform(row.get("relativeTransform")):
            reasons.append("missing_or_invalid_relative_transform")
        if not reasons:
            complete_count += 1
            complete_type_counts[type_name] += 1
            continue
        incomplete_count += 1
        incomplete_type_counts[type_name] += 1
        incomplete_reason_counts.update(reasons)
        render_relevant = _figma_vector_is_render_relevant(row)
        if render_relevant:
            render_relevant_incomplete_count += 1
        if len(incomplete_examples) < 24:
            incomplete_examples.append(
                {
                    "id": str(row.get("id") or ""),
                    "name": str(row.get("name") or ""),
                    "type": type_name,
                    "render_relevant": render_relevant,
                    "reasons": reasons,
                }
            )
    source_incomplete_blocker_count = render_relevant_incomplete_count
    if not complete_count and incomplete_count:
        # A type-only fixture with no real path evidence must not become a
        # successful compatibility sample merely because all paints are empty.
        source_incomplete_blocker_count = incomplete_count
    blockers = []
    if source_incomplete_blocker_count:
        blockers.append(
            {
                "reason": "source_incomplete_vector_geometry",
                "count": source_incomplete_blocker_count,
            }
        )
    return {
        "node_count": sum(node_type_counts.values()),
        "complete_count": complete_count,
        "source_incomplete_count": incomplete_count,
        "render_relevant_source_incomplete_count": (
            render_relevant_incomplete_count
        ),
        "source_incomplete_blocker_count": source_incomplete_blocker_count,
        "node_type_counts": dict(sorted(node_type_counts.items())),
        "complete_node_type_counts": dict(sorted(complete_type_counts.items())),
        "source_incomplete_node_type_counts": dict(
            sorted(incomplete_type_counts.items())
        ),
        "source_incomplete_reason_counts": dict(
            sorted(incomplete_reason_counts.items())
        ),
        "source_incomplete_examples": incomplete_examples,
        "blockers": blockers,
    }


def source_feature_inventory(payload: Mapping[str, Any]) -> dict[str, Any]:
    features: Counter[str] = Counter()
    node_types: Counter[str] = Counter()
    unknown_types: Counter[str] = Counter()
    paint_parents = {"fills", "strokes", "background", "backgrounds"}
    for row, parent_key in _walk(payload):
        type_name = str(row.get("type") or "").upper()
        if parent_key in paint_parents and type_name in _PAINT_FEATURES:
            features[_PAINT_FEATURES[type_name]] += 1
            if type_name == "IMAGE" and not str(row.get("imageRef") or ""):
                features["image_fill_missing_ref"] += 1
            continue
        if parent_key == "effects" and type_name:
            features["effects"] += 1
            features[f"effect_{type_name.casefold()}"] += 1
            continue
        is_scene_node = bool(str(row.get("id") or "")) and (
            "name" in row
            or "children" in row
            or "absoluteBoundingBox" in row
            or type_name in {"DOCUMENT", "CANVAS"}
        )
        if is_scene_node and type_name in _NODE_FEATURES:
            node_types[type_name] += 1
            features[_NODE_FEATURES[type_name]] += 1
        elif is_scene_node and type_name in _KNOWN_CONTAINER_TYPES:
            node_types[type_name] += 1
        elif is_scene_node and type_name in _EXPLICITLY_BLOCKED_TYPES:
            node_types[type_name] += 1
            features["explicitly_blocked_node"] += 1
        elif is_scene_node and type_name and parent_key not in {
            "actions",
            "prototypeDevice",
            "transition",
            "trigger",
        }:
            # Paint/effect enums are handled above. Other typed records are not
            # scene nodes and should not be treated as schema drift.
            if not (
                type_name in _PAINT_FEATURES
                or type_name.startswith("GRADIENT_")
                or type_name
                in {
                    "BACK",
                    "CHANGE_TO",
                    "CUSTOM",
                    "DISSOLVE",
                    "NODE",
                    "ON_CLICK",
                    "ON_HOVER",
                    "OVERLAY",
                    "SCALE",
                    "SMART_ANIMATE",
                    "URL",
                }
            ):
                unknown_types[type_name] += 1
        layout_mode = str(row.get("layoutMode") or "").upper()
        if layout_mode in {"HORIZONTAL", "VERTICAL"}:
            features["auto_layout"] += 1
        overrides = row.get("styleOverrideTable")
        if isinstance(overrides, Mapping) and overrides:
            features["text_ranges"] += 1
        if row.get("isMask"):
            features["mask"] += 1
        raw_reactions = row.get("reactions")
        if not isinstance(raw_reactions, list):
            raw_reactions = row.get("interactions")
        if isinstance(raw_reactions, list) and raw_reactions:
            features["prototype"] += 1
            for raw_reaction in raw_reactions:
                features["figma_reaction"] += 1
                if not isinstance(raw_reaction, Mapping):
                    features["figma_reaction_malformed"] += 1
                    continue
                raw_trigger = raw_reaction.get("trigger")
                if isinstance(raw_trigger, Mapping):
                    trigger_type = str(
                        raw_trigger.get("type") or "missing"
                    ).casefold()
                else:
                    trigger_type = "malformed"
                features[f"figma_reaction_trigger_{trigger_type}"] += 1
                raw_actions_value = raw_reaction.get("actions")
                if isinstance(raw_actions_value, list):
                    raw_actions = list(raw_actions_value)
                elif "action" in raw_reaction:
                    raw_actions = [raw_reaction.get("action")]
                elif "actions" in raw_reaction:
                    raw_actions = [raw_actions_value]
                else:
                    raw_actions = []
                features["figma_reaction_action"] += len(raw_actions)
                if not raw_actions:
                    features["figma_reaction_has_no_actions"] += 1
                for raw_action in raw_actions:
                    if not isinstance(raw_action, Mapping):
                        features["figma_reaction_action_malformed"] += 1
                        continue
                    action_type = str(
                        raw_action.get("type") or "missing"
                    ).casefold()
                    features[
                        f"figma_reaction_action_type_{action_type}"
                    ] += 1
                    navigation = str(
                        raw_action.get("navigation") or ""
                    ).casefold()
                    if navigation:
                        features[
                            f"figma_reaction_navigation_{navigation}"
                        ] += 1
        if isinstance(row.get("flowStartingPoints"), list) and row.get("flowStartingPoints"):
            features["prototype"] += len(row["flowStartingPoints"])
        bound_variables = row.get("boundVariables")
        if isinstance(bound_variables, Mapping) and bound_variables:
            # Keep the established node-level feature for manifest backwards
            # compatibility, but measure losslessness at Figma alias-slot
            # granularity. A scalar owns one slot even when malformed; a list
            # owns one slot per element, including null/malformed elements.
            features["variable_bindings"] += 1
            features["figma_variable_binding_alias"] += sum(
                len(value) if isinstance(value, list) else 1
                for value in bound_variables.values()
            )
        if isinstance(row.get("individualStrokeWeights"), Mapping):
            features["individual_stroke_weights"] += 1
        if isinstance(row.get("strokeGeometry"), list) and row.get("strokeGeometry"):
            features["stroke_geometry"] += 1
        if is_scene_node:
            definitions = row.get("componentPropertyDefinitions")
            if isinstance(definitions, Mapping) and definitions:
                features["component_property_definition"] += len(definitions)
                for definition in definitions.values():
                    if isinstance(definition, Mapping):
                        property_type = str(
                            definition.get("type") or "unknown"
                        ).casefold()
                        features[
                            f"component_property_definition_{property_type}"
                        ] += 1
            properties = row.get("componentProperties")
            if isinstance(properties, Mapping) and properties:
                features["component_property_value"] += len(properties)
            references = row.get("componentPropertyReferences")
            if isinstance(references, Mapping) and references:
                features["component_property_binding"] += len(references)
            variant_properties = row.get("variantProperties")
            if isinstance(variant_properties, Mapping) and variant_properties:
                features["variant_property_value"] += len(variant_properties)
            if type_name == "COMPONENT_SET":
                features["component_variant"] += sum(
                    1
                    for child in row.get("children", [])
                    if isinstance(child, Mapping)
                    and str(child.get("type") or "").upper() == "COMPONENT"
                )
        if (
            bool(row.get("remote"))
            and str(row.get("key") or "")
            and str(row.get("name") or "")
        ):
            features["remote_component_reference"] += 1
    vector_geometry = source_vector_geometry_inventory(payload)
    complete_types = vector_geometry["complete_node_type_counts"]
    features["path_geometry_complete"] += int(vector_geometry["complete_count"])
    features["boolean_geometry_complete"] += int(
        complete_types.get("BOOLEAN_OPERATION", 0)
    )
    features["vector_geometry_complete"] += sum(
        int(count)
        for node_type, count in complete_types.items()
        if node_type != "BOOLEAN_OPERATION"
    )
    features["source_incomplete_vector_geometry"] += int(
        vector_geometry["source_incomplete_count"]
    )
    features["source_incomplete_vector_geometry_render_relevant"] += int(
        vector_geometry["render_relevant_source_incomplete_count"]
    )
    features["source_incomplete_vector_geometry_blocker"] += int(
        vector_geometry["source_incomplete_blocker_count"]
    )
    return {
        "features": dict(
            sorted((key, value) for key, value in features.items() if value)
        ),
        "node_types": dict(sorted(node_types.items())),
        "unknown_node_types": dict(sorted(unknown_types.items())),
        "vector_geometry": vector_geometry,
    }


def _count_imported_figma_variable_aliases(
    features: Counter[str],
    records: object,
    *,
    location: str,
) -> None:
    if not isinstance(records, list):
        return
    features["figma_variable_binding_alias"] += len(records)
    features[f"figma_variable_binding_alias_{location}"] += len(records)
    for record in records:
        status = (
            str(record.get("status") or "").strip().casefold()
            if isinstance(record, Mapping)
            else ""
        )
        if status in {"native", "recovered", "unresolved", "blocked"}:
            features[f"figma_variable_binding_alias_{status}"] += 1
        else:
            features["figma_variable_binding_alias_unclassified"] += 1


def imported_feature_inventory(document: Mapping[str, Any]) -> dict[str, int]:
    features: Counter[str] = Counter()
    objects = [row for row in document.get("objects", []) if isinstance(row, Mapping)]
    for row in objects:
        kind = str(row.get("kind") or "")
        if kind:
            features[kind] += 1
        layout = row.get("layout")
        if isinstance(layout, Mapping) and layout.get("mode") in {"horizontal", "vertical"}:
            features["auto_layout"] += 1
        style = row.get("style")
        style = style if isinstance(style, Mapping) else {}
        if isinstance(style.get("individual_stroke_weights"), Mapping):
            features["individual_stroke_weights"] += 1
        if style.get("effects"):
            features["effects"] += 1
        gradient = style.get("fill_gradient")
        if isinstance(gradient, Mapping) and gradient.get("type"):
            features[f"gradient_{str(gradient['type']).casefold()}"] += 1
        content = row.get("content")
        content = content if isinstance(content, Mapping) else {}
        vector_paths = [
            str(value).strip()
            for value in content.get("vector_paths", [])
            if str(value or "").strip()
        ]
        if kind == "path" and vector_paths:
            features["path_geometry"] += 1
        if isinstance(content.get("figma_stroke_geometry"), Mapping):
            features["stroke_geometry"] += 1
        if kind == "image" or content.get("image_ref"):
            features["image_fill"] += 1
        if content.get("text_ranges"):
            features["text_ranges"] += 1
        for paint in content.get("figma_unsupported_paints", []):
            raw_type = str(paint.get("type") or "").upper()
            feature = _PAINT_FEATURES.get(raw_type)
            if feature:
                features[feature] += 1
                features["explicitly_blocked_feature"] += 1
        if (content.get("boolean") or {}).get("enabled"):
            features["boolean_operation"] += 1
            if vector_paths:
                features["boolean_path_geometry"] += 1
        if (row.get("mask") or {}).get("enabled"):
            features["mask"] += 1
        if row.get("component_role") == "definition":
            features["component"] += 1
        elif row.get("component_role") == "instance":
            features["instance"] += 1
        variable_alias_records = content.get("figma_variable_bindings")
        if row.get("token_bindings") or variable_alias_records:
            features["variable_bindings"] += 1
        _count_imported_figma_variable_aliases(
            features,
            variable_alias_records,
            location="object",
        )
        component_properties = row.get("component_properties")
        if isinstance(component_properties, Mapping) and component_properties:
            features["component_property_value"] += len(component_properties)
        property_bindings = row.get("component_property_bindings")
        active_property_binding_count = (
            len(property_bindings)
            if isinstance(property_bindings, Mapping)
            else 0
        )
        recovered_property_bindings = content.get(
            "figma_component_property_bindings"
        )
        recovered_property_binding_count = (
            len(recovered_property_bindings)
            if isinstance(recovered_property_bindings, Mapping)
            else 0
        )
        features["component_property_binding_active"] += (
            active_property_binding_count
        )
        features["component_property_binding_recovery"] += (
            recovered_property_binding_count
        )
        features["component_property_binding"] += (
            active_property_binding_count
            + recovered_property_binding_count
        )
        instance_overrides = row.get("instance_overrides")
        if isinstance(instance_overrides, Mapping) and instance_overrides:
            features["component_instance_override"] += len(instance_overrides)
        remote_component = content.get("remote_component")
        if isinstance(remote_component, Mapping) and remote_component:
            features["remote_component_reference"] += 1
    interactions = [
        row
        for row in document.get("interactions", [])
        if isinstance(row, Mapping)
    ]
    figma_link = document.get("linked_targets", {}).get("figma", {})
    figma_link = figma_link if isinstance(figma_link, Mapping) else {}
    reaction_recovery = [
        row
        for row in figma_link.get("reaction_recovery", [])
        if isinstance(row, Mapping)
    ]
    recovery_keys = {
        (
            str(row.get("source_kind") or ""),
            str(
                row.get("source_object_id")
                or row.get("source_artboard_id")
                or ""
            ),
            int(row.get("reaction_index") or 0),
        )
        for row in reaction_recovery
    }
    native_reaction_keys: set[tuple[str, str, int]] = set()
    for interaction in interactions:
        parameters = interaction.get("parameters")
        parameters = parameters if isinstance(parameters, Mapping) else {}
        metadata = parameters.get("figma_reaction")
        if not isinstance(metadata, Mapping):
            continue
        features["figma_reaction_native_action"] += 1
        features[
            "figma_reaction_native_action_"
            f"{str(interaction.get('action') or 'missing')}"
        ] += 1
        features[
            "figma_reaction_native_trigger_"
            f"{str(interaction.get('trigger') or 'missing')}"
        ] += 1
        native_reaction_keys.add(
            (
                str(metadata.get("source_kind") or ""),
                str(
                    metadata.get("source_object_id")
                    or metadata.get("source_artboard_id")
                    or ""
                ),
                int(metadata.get("reaction_index") or 0),
            )
        )
    features["figma_reaction_native"] += len(
        native_reaction_keys - recovery_keys
    )
    features["figma_reaction_recovery"] += len(reaction_recovery)
    features["figma_reaction_recovered_action"] += sum(
        len(row.get("blocked_actions", []))
        for row in reaction_recovery
    )
    features["prototype"] += len(interactions) + len(reaction_recovery)
    features["section"] += len(document.get("sections", []))
    components = [
        row
        for row in document.get("components", [])
        if isinstance(row, Mapping)
    ]
    features["component_record"] += len(components)
    variant_member_ids: set[str] = set()
    for component in components:
        variant_ids = {
            str(value)
            for value in component.get("variant_ids", [])
            if str(value or "")
        }
        if variant_ids:
            variant_member_ids.add(str(component.get("id") or ""))
            variant_member_ids.update(variant_ids)
        if str(component.get("base_component_id") or ""):
            variant_member_ids.add(str(component.get("id") or ""))
        definitions = component.get("property_definitions")
        if isinstance(definitions, Mapping) and definitions:
            features["component_property_definition"] += len(definitions)
    features["component_variant"] += len(
        {value for value in variant_member_ids if value}
    )
    features["token"] += len(document.get("tokens", []))
    artboard_variable_bindings = figma_link.get(
        "artboard_variable_bindings", []
    )
    artboard_binding_ids = {
        str(binding.get("artboard_id") or "")
        for binding in artboard_variable_bindings
        if isinstance(binding, Mapping) and binding.get("artboard_id")
    }
    features["variable_bindings"] += len(artboard_binding_ids)
    _count_imported_figma_variable_aliases(
        features,
        artboard_variable_bindings,
        location="artboard",
    )
    return dict(sorted((key, value) for key, value in features.items() if value))


def _load_manifest(path: Path) -> dict[str, Any]:
    return _read_fetch_manifest(path)


def _verify_case_artifact(
    source_path: Path,
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify the pinned artifact immediately before parsing it."""
    expected_bytes = int(artifact["bytes"])
    actual_bytes = source_path.stat().st_size
    if actual_bytes != expected_bytes:
        raise FigmaCorpusError(
            "artifact_size_mismatch:"
            f"expected={expected_bytes}:actual={actual_bytes}"
        )
    digest = hashlib.sha256()
    with source_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_sha256 = digest.hexdigest()
    expected_sha256 = str(artifact["sha256"]).casefold()
    if actual_sha256 != expected_sha256:
        raise FigmaCorpusError(
            "artifact_sha256_mismatch:"
            f"expected={expected_sha256}:actual={actual_sha256}"
        )
    return {"bytes": actual_bytes, "sha256": actual_sha256}


def _load_case_source(
    source_path: Path,
) -> tuple[Mapping[str, Any], dict[str, str], dict[str, Any]]:
    if source_path.suffix.lower() != ".zip":
        payload = json.loads(source_path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, Mapping):
            raise ValueError("snapshot root is not an object")
        return payload, {}, {"kind": "json", "extracted_image_count": 0}

    image_paths: dict[str, str] = {}
    extraction_root = source_path.parent / "extracted" / "images"
    with zipfile.ZipFile(source_path, "r") as archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        if sum(entry.file_size for entry in entries) > 512 * 1024 * 1024:
            raise ValueError("archive expands beyond the 512 MiB safety limit")
        document_entries = [
            entry
            for entry in entries
            if entry.filename.replace("\\", "/").endswith("/document.json")
            or entry.filename.replace("\\", "/") == "document.json"
        ]
        if len(document_entries) != 1:
            raise ValueError(
                f"archive must contain exactly one document.json, found {len(document_entries)}"
            )
        document_entry = document_entries[0]
        if document_entry.file_size > 128 * 1024 * 1024:
            raise ValueError("archive document.json is too large")
        payload = json.loads(archive.read(document_entry).decode("utf-8-sig"))
        if not isinstance(payload, Mapping):
            raise ValueError("archive document.json root is not an object")
        document_prefix = document_entry.filename.replace("\\", "/").rsplit("/", 1)[0]
        image_prefix = f"{document_prefix}/images/" if document_prefix else "images/"
        image_entries = [
            entry
            for entry in entries
            if entry.filename.replace("\\", "/").startswith(image_prefix)
        ]
        extractable_images: list[tuple[zipfile.ZipInfo, str, str]] = []
        seen_stems: dict[str, str] = {}
        for entry in image_entries:
            name = Path(entry.filename.replace("\\", "/")).name
            if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
                raise ValueError(f"unsafe archive image name: {name!r}")
            if Path(name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            if entry.file_size > 32 * 1024 * 1024:
                raise ValueError(f"archive image is too large: {name}")
            stem = Path(name).stem
            stem_key = stem.casefold()
            previous = seen_stems.get(stem_key)
            if previous is not None:
                raise ValueError(
                    "archive contains duplicate image stem: "
                    f"{stem!r} ({previous!r}, {entry.filename!r})"
                )
            seen_stems[stem_key] = entry.filename
            extractable_images.append((entry, name, stem))
        for entry, name, stem in extractable_images:
            target = extraction_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".part")
            try:
                temporary.write_bytes(archive.read(entry))
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            image_paths[stem] = str(target.resolve())
    return payload, image_paths, {
        "kind": "figma_rest_archive",
        "document_entry": document_entry.filename,
        "extracted_image_count": len(image_paths),
        "extraction_root": str(extraction_root.resolve()),
    }


def _selector_canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _selector_semantic_value(value: object) -> object:
    """Strip identity/placement only; retain visible and semantic content."""
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            if key in {
                "id",
                "componentId",
                "componentSetId",
                "prototypeStartNodeID",
                "styles",
                "boundVariables",
            }:
                continue
            if key in {"absoluteBoundingBox", "absoluteRenderBounds"} and isinstance(
                child, Mapping
            ):
                normalized[key] = {
                    str(inner_key): inner_value
                    for inner_key, inner_value in child.items()
                    if str(inner_key) not in {"x", "y"}
                }
                continue
            if (
                key in {"relativeTransform", "absoluteTransform"}
                and isinstance(child, list)
                and len(child) == 2
                and all(isinstance(row, list) and len(row) >= 2 for row in child)
            ):
                normalized[key] = [
                    [child[0][0], child[0][1], 0],
                    [child[1][0], child[1][1], 0],
                ]
                continue
            normalized[key] = _selector_semantic_value(child)
        return normalized
    if isinstance(value, list):
        return [_selector_semantic_value(child) for child in value]
    return value


def _walk_figma_nodes(
    node: Mapping[str, Any],
    *,
    ancestry: tuple[str, ...] = (),
    canvas: Mapping[str, Any] | None = None,
) -> Iterable[tuple[Mapping[str, Any], tuple[str, ...], Mapping[str, Any] | None]]:
    node_id = str(node.get("id") or "")
    path = (*ancestry, node_id)
    if str(node.get("type") or "") == "CANVAS":
        canvas = node
    yield node, path, canvas
    children = node.get("children")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, Mapping):
                yield from _walk_figma_nodes(
                    child,
                    ancestry=path,
                    canvas=canvas,
                )


def _selector_node_count(node: Mapping[str, Any]) -> int:
    return sum(1 for _node, _path, _canvas in _walk_figma_nodes(node))


def _selector_image_refs(node: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for row, _parent_key in _walk(node):
        image_ref = str(row.get("imageRef") or "").strip()
        if image_ref:
            refs.add(image_ref)
    return refs


def _parse_selector_archive(
    source_path: Path,
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    verified = _verify_case_artifact(source_path, artifact)
    with zipfile.ZipFile(source_path, "r") as archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        if sum(entry.file_size for entry in entries) > 512 * 1024 * 1024:
            raise ValueError("archive expands beyond the 512 MiB safety limit")
        document_entries = [
            entry
            for entry in entries
            if entry.filename.replace("\\", "/").endswith("/document.json")
            or entry.filename.replace("\\", "/") == "document.json"
        ]
        if len(document_entries) != 1:
            raise ValueError(
                f"archive must contain exactly one document.json, found {len(document_entries)}"
            )
        document_entry = document_entries[0]
        if document_entry.file_size > 128 * 1024 * 1024:
            raise ValueError("archive document.json is too large")
        payload = json.loads(archive.read(document_entry).decode("utf-8-sig"))
        if not isinstance(payload, Mapping):
            raise ValueError("archive document.json root is not an object")
        document = payload.get("document")
        if not isinstance(document, Mapping):
            raise ValueError("archive document.json has no document object")
        document_prefix = document_entry.filename.replace("\\", "/").rsplit("/", 1)[0]
        image_prefix = f"{document_prefix}/images/" if document_prefix else "images/"
        image_index: dict[str, dict[str, Any]] = {}
        for entry in entries:
            archive_name = entry.filename.replace("\\", "/")
            if not archive_name.startswith(image_prefix):
                continue
            name = Path(archive_name).name
            if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
                raise ValueError(f"unsafe archive image name: {name!r}")
            if Path(name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            if entry.file_size > 32 * 1024 * 1024:
                raise ValueError(f"archive image is too large: {name}")
            stem = Path(name).stem
            key = stem.casefold()
            if key in image_index:
                raise ValueError(f"archive contains duplicate image stem: {stem!r}")
            image_index[key] = {
                "stem": stem,
                "name": name,
                "archive_name": entry.filename,
                "bytes": int(entry.file_size),
            }

    node_index: dict[str, dict[str, Any]] = {}
    for node, ancestry, canvas in _walk_figma_nodes(document):
        node_id = str(node.get("id") or "")
        if not node_id:
            raise ValueError("Figma selector source contains an empty node id")
        if node_id in node_index:
            raise ValueError(f"Figma selector source contains duplicate node id: {node_id}")
        node_index[node_id] = {
            "node": node,
            "ancestry": ancestry,
            "canvas": canvas,
        }
    return {
        "payload": payload,
        "verified": verified,
        "document_entry": document_entry.filename,
        "image_index": image_index,
        "node_index": node_index,
        "extracted_images": {},
    }


def _load_selector_case_source(
    source_path: Path,
    artifact: Mapping[str, Any],
    selector: Mapping[str, Any],
    cache: dict[tuple[str, str], dict[str, Any]],
) -> tuple[Mapping[str, Any], dict[str, str], dict[str, Any], dict[str, Any]]:
    cache_key = (
        str(source_path.resolve()).casefold(),
        str(artifact.get("sha256") or "").casefold(),
    )
    cache_hit = cache_key in cache
    entry = cache.get(cache_key)
    if entry is None:
        entry = _parse_selector_archive(source_path, artifact)
        cache[cache_key] = entry

    node_id = str(selector.get("node_id") or "")
    indexed = entry["node_index"].get(node_id)
    if not isinstance(indexed, Mapping):
        raise FigmaCorpusError(f"selector_node_not_found:{node_id}")
    node = indexed["node"]
    canvas = indexed.get("canvas")
    if not isinstance(node, Mapping) or not isinstance(canvas, Mapping):
        raise FigmaCorpusError(f"selector_canvas_not_found:{node_id}")
    actual_ancestry = tuple(str(value) for value in indexed["ancestry"])
    expected_ancestry = tuple(str(value) for value in selector.get("ancestry", []))
    if actual_ancestry != expected_ancestry:
        raise FigmaCorpusError(
            f"selector_ancestry_mismatch:{node_id}:"
            f"expected={expected_ancestry}:actual={actual_ancestry}"
        )
    if str(canvas.get("id") or "") != str(selector.get("ancestor_canvas_id") or ""):
        raise FigmaCorpusError(f"selector_canvas_mismatch:{node_id}")
    if str(node.get("type") or "") != str(selector.get("expected_type") or ""):
        raise FigmaCorpusError(f"selector_type_mismatch:{node_id}")
    if str(node.get("name") or "") != str(selector.get("expected_name") or ""):
        raise FigmaCorpusError(f"selector_name_mismatch:{node_id}")
    bounds = node.get("absoluteBoundingBox")
    if not isinstance(bounds, Mapping) or not all(
        _finite_number(bounds.get(key)) and float(bounds[key]) > 0.0
        for key in ("width", "height")
    ):
        raise FigmaCorpusError(f"selector_bounds_invalid:{node_id}")

    canonical = _selector_canonical_bytes(node)
    observed_nodes = _selector_node_count(node)
    exact_sha = hashlib.sha256(canonical).hexdigest()
    semantic_sha = hashlib.sha256(
        _selector_canonical_bytes(_selector_semantic_value(node))
    ).hexdigest()
    expected_values = {
        "observed_nodes": observed_nodes,
        "observed_json_bytes": len(canonical),
        "subtree_sha256": exact_sha,
        "semantic_sha256": semantic_sha,
    }
    for key, actual in expected_values.items():
        expected = selector.get(key)
        if expected != actual:
            raise FigmaCorpusError(
                f"selector_{key}_mismatch:{node_id}:expected={expected}:actual={actual}"
            )

    image_refs = _selector_image_refs(node)
    if len(image_refs) > _MAX_SELECTOR_IMAGE_REFS:
        raise FigmaCorpusError(f"selector_image_ref_limit_exceeded:{node_id}")
    missing_refs = sorted(
        image_ref
        for image_ref in image_refs
        if image_ref.casefold() not in entry["image_index"]
    )
    if missing_refs:
        raise FigmaCorpusError(
            f"selector_image_assets_missing:{node_id}:{','.join(missing_refs)}"
        )
    selected_image_bytes = sum(
        int(entry["image_index"][image_ref.casefold()]["bytes"])
        for image_ref in image_refs
    )
    if selected_image_bytes > _MAX_SELECTOR_IMAGE_BYTES:
        raise FigmaCorpusError(f"selector_image_byte_limit_exceeded:{node_id}")
    extraction_root = source_path.parent / "extracted" / "images"
    unresolved = [
        image_ref
        for image_ref in sorted(image_refs)
        if image_ref.casefold() not in entry["extracted_images"]
    ]
    if unresolved:
        with zipfile.ZipFile(source_path, "r") as archive:
            for image_ref in unresolved:
                image = entry["image_index"][image_ref.casefold()]
                target = extraction_root / str(image["name"])
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + ".part")
                try:
                    temporary.write_bytes(archive.read(str(image["archive_name"])))
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
                entry["extracted_images"][image_ref.casefold()] = str(target.resolve())
    image_paths = {
        image_ref: str(entry["extracted_images"][image_ref.casefold()])
        for image_ref in image_refs
    }

    source_payload = entry["payload"]
    document = source_payload["document"]
    wrapper = {key: value for key, value in source_payload.items() if key != "document"}
    wrapped_document = {key: value for key, value in document.items() if key != "children"}
    wrapped_canvas = {key: value for key, value in canvas.items() if key != "children"}
    wrapped_canvas["children"] = [node]
    wrapped_document["children"] = [wrapped_canvas]
    wrapper["document"] = wrapped_document
    selector_details = {
        "kind": "node_subtree",
        "node_id": node_id,
        "ancestor_canvas_id": str(canvas.get("id") or ""),
        "ancestry": list(actual_ancestry),
        "root_type": str(node.get("type") or ""),
        "root_name": str(node.get("name") or ""),
        "observed_nodes": observed_nodes,
        "observed_json_bytes": len(canonical),
        "subtree_sha256": exact_sha,
        "semantic_sha256": semantic_sha,
        "image_ref_count": len(image_refs),
        "image_bytes": selected_image_bytes,
        "wrapper": "promote_to_original_canvas",
    }
    source_details = {
        "kind": "figma_rest_archive_selector",
        "document_entry": entry["document_entry"],
        "artifact_cache_hit": cache_hit,
        "archive_image_count": len(entry["image_index"]),
        "selected_image_ref_count": len(image_refs),
        "extracted_image_count": len(image_paths),
        "extraction_root": str(extraction_root.resolve()),
    }
    return wrapper, image_paths, source_details, {
        "artifact": dict(entry["verified"]),
        "selector": selector_details,
    }


def _case_expectation_errors(
    item: Mapping[str, Any],
    *,
    import_report: Mapping[str, Any],
    source_features: Mapping[str, int],
    imported_features: Mapping[str, int],
    unknown_node_types: Mapping[str, int],
) -> list[str]:
    expected = item.get("expectations")
    expected = expected if isinstance(expected, Mapping) else {}
    errors: list[str] = []
    resources = import_report.get("resources")
    resources = resources if isinstance(resources, Mapping) else {}
    missing_image_count = int(resources.get("missing_image_count") or 0)
    if missing_image_count:
        errors.append(f"source_image_assets_missing:{missing_image_count}")
    missing_image_ref_count = int(source_features.get("image_fill_missing_ref") or 0)
    if missing_image_ref_count:
        errors.append(f"source_image_refs_missing:{missing_image_ref_count}")
    if int(import_report.get("artboard_count") or 0) < int(expected.get("min_artboards") or 1):
        errors.append("artboard_count_below_expectation")
    if int(import_report.get("object_count") or 0) < int(expected.get("min_objects") or 1):
        errors.append("object_count_below_expectation")
    for feature in expected.get("required_source_features", []):
        if int(source_features.get(str(feature), 0)) <= 0:
            errors.append(f"required_source_feature_missing:{feature}")
    for feature in expected.get("preserve_features", []):
        if int(imported_features.get(str(feature), 0)) <= 0:
            errors.append(f"import_feature_not_preserved:{feature}")
    allowed_unknown = {str(value) for value in expected.get("allowed_unknown_node_types", [])}
    for node_type in unknown_node_types:
        if node_type not in allowed_unknown:
            errors.append(f"unknown_source_node_type:{node_type}")
    return errors


def _select_artboards_for_render(
    document: Mapping[str, Any],
    count: int,
) -> list[dict[str, Any]]:
    """Choose a deterministic, bounded cross-section of document artboards."""
    artboards = [
        row
        for row in document.get("artboards", [])
        if isinstance(row, Mapping) and str(row.get("id") or "")
    ]
    target_count = min(max(0, int(count)), len(artboards))
    if target_count <= 0:
        return []

    active_id = str(document.get("active_artboard_id") or "")
    active_index = next(
        (
            index
            for index, row in enumerate(artboards)
            if str(row.get("id") or "") == active_id
        ),
        0,
    )
    selected: list[int] = []
    reasons: dict[int, list[str]] = {}

    def add(index: int, reason: str) -> None:
        if index < 0 or index >= len(artboards):
            return
        reasons.setdefault(index, []).append(reason)
        if index not in selected and len(selected) < target_count:
            selected.append(index)

    # The default four communicate intent in the report and give useful
    # coverage even when the active artboard is not near either document edge.
    add(active_index, "active")
    add(0, "first")
    add(len(artboards) // 2, "middle")
    add(len(artboards) - 1, "last")

    # De-duplication can collapse the primary choices.  Fill the requested
    # count with evenly spaced positions, then sequential positions as a final
    # deterministic fallback for very small or unusually ordered documents.
    if len(selected) < target_count:
        denominator = max(1, target_count - 1)
        for slot in range(target_count):
            add(
                round(slot * (len(artboards) - 1) / denominator),
                "even_sample",
            )
    if len(selected) < target_count:
        for index in range(len(artboards)):
            add(index, "fill")

    result: list[dict[str, Any]] = []
    for index in selected:
        row = artboards[index]
        artboard_id = str(row.get("id") or "")
        result.append(
            {
                "artboard_id": artboard_id,
                "artboard_name": str(row.get("name") or artboard_id),
                "artboard_index": index,
                "active": artboard_id == active_id,
                "selection_reasons": reasons.get(index, ["fill"]),
            }
        )
    return result


def _focused_render_count(
    *,
    width: int,
    height: int,
    requested_count: int,
) -> int:
    """Apply the hard count and aggregate pixel-work limits."""
    requested_count = max(0, min(int(requested_count), _MAX_ARTBOARD_RENDER_COUNT))
    if requested_count <= 0:
        return 0
    pixels_per_smoke = int(width) * int(height) * 2
    remaining_pixels = max(0, _MAX_RENDER_PIXEL_WORK - pixels_per_smoke)
    pixel_limited_count = remaining_pixels // max(1, pixels_per_smoke)
    return min(requested_count, pixel_limited_count)


def _render_filename_component(value: object) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._")
    return (cleaned or "artboard")[:80]


def render_document_smoke(
    document: Mapping[str, Any],
    *,
    width: int = 960,
    height: int = 640,
    png_path: str | Path | None = None,
    fit_artboard_id: str = "",
) -> dict[str, Any]:
    """Render the real Painter canvas offscreen and return cheap image evidence.

    This intentionally exercises ``PainterUIDesignOverlay.paintEvent`` rather
    than a schema-only or mock renderer.  The sampled metrics keep corpus runs
    inexpensive while still detecting null, transparent, and uniform frames.
    """
    width = int(width)
    height = int(height)
    if width < 64 or height < 64:
        raise ValueError("render smoke dimensions must be at least 64x64")
    if width > 4096 or height > 4096 or width * height > 16_777_216:
        raise ValueError("render smoke dimensions exceed the 16 megapixel limit")

    # The tool must also work on GUI-less CI workers.  setdefault preserves an
    # explicitly selected platform in interactive/manual runs.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_workspace import PainterUIDesignOverlay

    global _QT_APPLICATION
    app = QApplication.instance()
    if app is None:
        _QT_APPLICATION = QApplication([])
        app = _QT_APPLICATION
    else:
        _QT_APPLICATION = app
    # Match normal TigerCapture startup.  Windows' offscreen Qt platform can
    # expose an incomplete system font database, otherwise both application
    # chrome and imported Figma text are captured as tofu boxes.
    from app.font_fallback import apply_ui_font

    apply_ui_font(app)

    fit_artboard_id = str(fit_artboard_id or "")
    if fit_artboard_id and fit_artboard_id not in {
        str(row.get("id") or "")
        for row in document.get("artboards", [])
        if isinstance(row, Mapping)
    }:
        raise ValueError(f"render smoke artboard not found: {fit_artboard_id}")

    def render_overlay(value: Mapping[str, Any]) -> QImage:
        overlay = PainterUIDesignOverlay()
        painter: QPainter | None = None
        try:
            overlay.resize(width, height)
            overlay.set_document(value)
            # Selection handles and canvas labels are editor chrome, not proof
            # that imported design content was painted.
            overlay.set_artboard_labels_visible(False)
            if fit_artboard_id:
                overlay.fit_artboard(fit_artboard_id)
            else:
                overlay.fit_all()
            app.processEvents()

            result = QImage(
                width,
                height,
                QImage.Format.Format_ARGB32_Premultiplied,
            )
            result.fill(0)
            painter = QPainter(result)
            overlay.render(painter, QPoint(0, 0))
            painter.end()
            painter = None
            return result.convertToFormat(QImage.Format.Format_RGBA8888)
        finally:
            if painter is not None and painter.isActive():
                painter.end()
            overlay.close()
            overlay.deleteLater()
            app.processEvents()

    render_document = copy.deepcopy(dict(document))
    render_document["selection"] = {"object_id": "", "object_ids": []}
    image = render_overlay(render_document)
    baseline_document = copy.deepcopy(render_document)
    baseline_document["objects"] = []
    baseline_image = render_overlay(baseline_document)
    try:
        if image.isNull():
            raise RuntimeError("Painter overlay produced a null QImage")
        if baseline_image.isNull():
            raise RuntimeError("Painter baseline overlay produced a null QImage")

        raw = bytes(image.constBits())
        baseline_raw = bytes(baseline_image.constBits())
        if not raw:
            raise RuntimeError("Painter overlay produced an empty pixel buffer")
        if len(raw) != len(baseline_raw):
            raise RuntimeError("Painter overlay and baseline sizes differ")
        digest = hashlib.sha256(raw).hexdigest()
        baseline_digest = hashlib.sha256(baseline_raw).hexdigest()
        bytes_per_line = int(image.bytesPerLine())
        total_pixels = width * height
        # Cap Python-side inspection at roughly 65k pixels per frame.
        sample_step = max(1, int((total_pixels / 65_536) ** 0.5))
        background = bytes(raw[0:4])
        unique_colors: set[bytes] = set()
        sampled_pixels = 0
        non_background_pixels = 0
        nontransparent_pixels = 0
        sampled_content_diff_pixels = 0
        for y in range(0, height, sample_step):
            row_offset = y * bytes_per_line
            for x in range(0, width, sample_step):
                offset = row_offset + x * 4
                rgba = bytes(raw[offset : offset + 4])
                if len(rgba) != 4:
                    continue
                sampled_pixels += 1
                unique_colors.add(rgba)
                if rgba != background:
                    non_background_pixels += 1
                if rgba[3] != 0:
                    nontransparent_pixels += 1
                baseline_rgba = bytes(baseline_raw[offset : offset + 4])
                if rgba != baseline_rgba:
                    sampled_content_diff_pixels += 1

        diff_pixel_count = 0
        diff_left = width
        diff_top = height
        diff_right = -1
        diff_bottom = -1
        actual_pixels = memoryview(raw).cast("I")
        baseline_pixels = memoryview(baseline_raw).cast("I")
        for index, (actual, baseline) in enumerate(
            zip(actual_pixels, baseline_pixels)
        ):
            if actual == baseline:
                continue
            diff_pixel_count += 1
            x = index % width
            y = index // width
            diff_left = min(diff_left, x)
            diff_top = min(diff_top, y)
            diff_right = max(diff_right, x)
            diff_bottom = max(diff_bottom, y)

        canvas_nonblank = (
            sampled_pixels > 0
            and len(unique_colors) > 1
            and non_background_pixels >= 8
            and nontransparent_pixels > 0
        )
        object_count = sum(
            1
            for row in document.get("objects", [])
            if isinstance(row, Mapping)
            and (
                not fit_artboard_id
                or str(row.get("artboard_id") or "") == fit_artboard_id
            )
        )
        minimum_content_diff_pixels = max(8, int(total_pixels * 0.00005))
        content_present = (
            object_count <= 0
            or diff_pixel_count >= minimum_content_diff_pixels
        )
        passed = bool(canvas_nonblank and content_present)
        if not canvas_nonblank:
            status = "blank"
        elif not content_present:
            status = "content_missing"
        else:
            status = "passed"
        saved_path = ""
        png_bytes = 0
        baseline_saved_path = ""
        baseline_png_bytes = 0
        if png_path is not None:
            target = Path(png_path).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            if not image.save(str(target), "PNG"):
                raise RuntimeError(f"Painter render PNG save failed: {target}")
            saved_path = str(target)
            png_bytes = target.stat().st_size
            baseline_target = target.with_name(
                f"{target.stem}.baseline{target.suffix}"
            )
            if not baseline_image.save(str(baseline_target), "PNG"):
                raise RuntimeError(
                    f"Painter baseline PNG save failed: {baseline_target}"
                )
            baseline_saved_path = str(baseline_target)
            baseline_png_bytes = baseline_target.stat().st_size

        return {
            "status": status,
            "passed": passed,
            "renderer": "PainterUIDesignOverlay.render(QImage)",
            "fit_mode": "artboard" if fit_artboard_id else "all",
            "artboard_id": fit_artboard_id,
            "width": width,
            "height": height,
            "object_count": object_count,
            "pixel_sha256": digest,
            "baseline_pixel_sha256": baseline_digest,
            "sample_step": sample_step,
            "sampled_pixel_count": sampled_pixels,
            "sampled_unique_color_count": len(unique_colors),
            "sampled_non_background_pixel_count": non_background_pixels,
            "sampled_non_background_ratio": round(
                non_background_pixels / max(1, sampled_pixels), 6
            ),
            "sampled_nontransparent_ratio": round(
                nontransparent_pixels / max(1, sampled_pixels), 6
            ),
            "sampled_content_diff_pixel_count": sampled_content_diff_pixels,
            "content_diff_pixel_count": diff_pixel_count,
            "content_diff_ratio": round(
                diff_pixel_count / max(1, total_pixels), 6
            ),
            "minimum_content_diff_pixels": minimum_content_diff_pixels,
            "content_diff_bounds": (
                {
                    "x": diff_left,
                    "y": diff_top,
                    "width": diff_right - diff_left + 1,
                    "height": diff_bottom - diff_top + 1,
                }
                if diff_pixel_count
                else None
            ),
            "background_rgba": list(background),
            "png_path": saved_path,
            "png_bytes": png_bytes,
            "baseline_png_path": baseline_saved_path,
            "baseline_png_bytes": baseline_png_bytes,
        }
    finally:
        # Keep the QApplication alive for the full corpus process; QImages own
        # their pixel data and need no explicit Qt cleanup here.
        app.processEvents()


def _release_coverage_report(
    manifest: Mapping[str, Any],
    rows: Iterable[Mapping[str, Any]],
    *,
    enforce: bool,
) -> dict[str, Any]:
    """Apply the audited release-corpus ratchets to a complete run."""

    coverage = manifest.get("coverage")
    if not isinstance(coverage, Mapping):
        return {"status": "not_configured", "errors": []}
    row_list = list(rows)
    selector_rows = [
        row for row in row_list if isinstance(row.get("selector"), Mapping)
    ]
    feature_case_counts: Counter[str] = Counter()
    source_keys: set[str] = set()
    selector_nodes = 0
    missing_images = 0
    for row in selector_rows:
        selector = row.get("selector")
        selector = selector if isinstance(selector, Mapping) else {}
        selector_nodes += int(selector.get("observed_nodes") or 0)
        features = row.get("source_features")
        features = features if isinstance(features, Mapping) else {}
        for feature, count in features.items():
            if int(count or 0) > 0:
                feature_case_counts[str(feature)] += 1
        provenance = row.get("provenance")
        provenance = provenance if isinstance(provenance, Mapping) else {}
        source_key = str(
            provenance.get("original_url")
            or provenance.get("repository")
            or provenance.get("url")
            or ""
        ).strip()
        if source_key:
            source_keys.add(source_key)
    for row in row_list:
        import_report = row.get("import")
        import_report = (
            import_report if isinstance(import_report, Mapping) else {}
        )
        resources = import_report.get("resources")
        resources = resources if isinstance(resources, Mapping) else {}
        missing_images += int(resources.get("missing_image_count") or 0)

    expected_case_count = int(coverage.get("expected_case_count") or 0)
    expected_selector_count = int(
        coverage.get("expected_selector_case_count") or 0
    )
    min_sources = int(coverage.get("min_selector_original_sources") or 0)
    min_nodes = int(coverage.get("min_selector_nodes") or 0)
    max_missing = int(coverage.get("max_missing_image_count") or 0)
    feature_minima = coverage.get("selector_min_source_feature_cases")
    feature_minima = (
        feature_minima if isinstance(feature_minima, Mapping) else {}
    )
    errors: list[str] = []
    if enforce:
        checks = (
            (len(row_list) == expected_case_count, "case_count"),
            (
                len(selector_rows) == expected_selector_count,
                "selector_case_count",
            ),
            (len(source_keys) >= min_sources, "selector_original_sources"),
            (selector_nodes >= min_nodes, "selector_nodes"),
            (missing_images <= max_missing, "missing_images"),
        )
        errors.extend(
            f"release_coverage_failed:{name}"
            for passed, name in checks
            if not passed
        )
        for feature, minimum in feature_minima.items():
            if feature_case_counts[str(feature)] < int(minimum):
                errors.append(
                    f"release_coverage_failed:source_feature:{feature}"
                )
    return {
        "status": (
            "passed"
            if enforce and not errors
            else "failed"
            if enforce
            else "not_enforced_partial_selection"
        ),
        "expected_case_count": expected_case_count,
        "actual_case_count": len(row_list),
        "expected_selector_case_count": expected_selector_count,
        "actual_selector_case_count": len(selector_rows),
        "min_selector_original_sources": min_sources,
        "actual_selector_original_sources": len(source_keys),
        "min_selector_nodes": min_nodes,
        "actual_selector_nodes": selector_nodes,
        "max_missing_image_count": max_missing,
        "actual_missing_image_count": missing_images,
        "selector_min_source_feature_cases": dict(feature_minima),
        "selector_actual_source_feature_cases": dict(
            sorted(feature_case_counts.items())
        ),
        "errors": errors,
    }


def run_corpus(
    manifest_path: str | Path,
    assets_root: str | Path,
    output: str | Path,
    *,
    write_packages: bool = False,
    require_umg_clean: bool = False,
    case_ids: set[str] | None = None,
    render_smoke: bool = False,
    render_smoke_width: int = 960,
    render_smoke_height: int = 640,
    render_smoke_max_objects: int = 0,
    render_smoke_artboard_count: int = 4,
    write_render_pngs: bool = True,
    performance_baseline: str | Path | Mapping[str, Any] | None = None,
    max_performance_regression_percent: float = (
        _DEFAULT_MAX_PERFORMANCE_REGRESSION_PERCENT
    ),
    clock_ns: Callable[[], int] | None = None,
) -> dict[str, Any]:
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_figma import (
        export_figma_plugin_package,
        import_figma_payload,
        inspect_figma_compatibility,
    )
    from app.painter_ui_umg_adapter import PainterUMGConversionSession

    manifest_path = Path(manifest_path).expanduser().resolve()
    assets_root = Path(assets_root).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    render_smoke_width = int(render_smoke_width)
    render_smoke_height = int(render_smoke_height)
    render_smoke_max_objects = max(0, int(render_smoke_max_objects))
    render_smoke_artboard_count = int(render_smoke_artboard_count)
    max_performance_regression_percent = float(
        max_performance_regression_percent
    )
    if (
        not math.isfinite(max_performance_regression_percent)
        or max_performance_regression_percent < 0.0
    ):
        raise FigmaCorpusError(
            "Maximum performance regression percent must be finite and non-negative"
        )
    timing_clock = clock_ns or perf_counter_ns
    timing_clock_name = (
        "injected_test_clock" if clock_ns is not None else "perf_counter_ns"
    )
    if render_smoke and (
        render_smoke_width < 64
        or render_smoke_height < 64
        or render_smoke_width > 4096
        or render_smoke_height > 4096
        or render_smoke_width * render_smoke_height > 16_777_216
    ):
        raise FigmaCorpusError(
            "Render smoke size must be between 64x64 and 4096x4096 "
            "and at most 16 megapixels"
        )
    if render_smoke and not (
        0 <= render_smoke_artboard_count <= _MAX_ARTBOARD_RENDER_COUNT
    ):
        raise FigmaCorpusError(
            "Render artboard count must be between 0 and "
            f"{_MAX_ARTBOARD_RENDER_COUNT}"
        )
    manifest = _load_manifest(manifest_path)
    selected = set(case_ids or ())
    known = {str(item["id"]) for item in manifest["cases"]}
    if selected - known:
        raise FigmaCorpusError(
            f"Unknown corpus case ids: {', '.join(sorted(selected - known))}"
        )
    rows: list[dict[str, Any]] = []
    aggregate_source: Counter[str] = Counter()
    aggregate_imported: Counter[str] = Counter()
    aggregate_import_report_variable_binding_count = 0
    aggregate_umg: Counter[str] = Counter()
    aggregate_blockers: Counter[str] = Counter()
    aggregate_source_blockers: Counter[str] = Counter()
    selector_artifact_cache: dict[tuple[str, str], dict[str, Any]] = {}
    for item in manifest["cases"]:
        case_id = str(item["id"])
        if selected and case_id not in selected:
            continue
        artifact = item["artifact"]
        source = item["source"]
        source_path = (
            assets_root / _safe_relative_path(artifact["relative_path"])
        ).resolve()
        phase_timings = _CasePhaseTimings(
            timing_clock,
            clock_name=timing_clock_name,
        )
        case_errors: list[str] = []
        case_result: dict[str, Any] = {
            "id": case_id,
            "title": str(item.get("title") or case_id),
            "format": str(item.get("format") or ""),
            "source_path": str(source_path),
            "license": str(source["license"]),
            "provenance": {
                key: str(source.get(key) or "")
                for key in (
                    "repository",
                    "commit",
                    "path",
                    "url",
                    "html_url",
                    "license",
                    "license_url",
                    "attribution",
                    "creator",
                    "original_url",
                    "license_evidence_url",
                    "license_scope",
                    "modifications",
                )
            },
        }
        if item.get("artifact_ref"):
            case_result["artifact_ref"] = str(item["artifact_ref"])
        if not source_path.is_file():
            case_result.update(
                {
                    "passed": False,
                    "errors": ["artifact_missing"],
                    "source_features": {},
                    "imported_features": {},
                }
            )
            case_result["performance"] = phase_timings.report()
            rows.append(case_result)
            continue
        try:
            with phase_timings.measure("load"):
                selector = item.get("selector")
                if isinstance(selector, Mapping):
                    (
                        payload,
                        image_paths,
                        source_details,
                        selector_load,
                    ) = _load_selector_case_source(
                        source_path,
                        artifact,
                        selector,
                        selector_artifact_cache,
                    )
                    case_result["artifact"] = selector_load["artifact"]
                    case_result["selector"] = selector_load["selector"]
                else:
                    case_result["artifact"] = _verify_case_artifact(
                        source_path,
                        artifact,
                    )
                    payload, image_paths, source_details = _load_case_source(
                        source_path
                    )
            with phase_timings.measure("scan"):
                source_inventory = source_feature_inventory(payload)
                source_features = source_inventory["features"]
                aggregate_source.update(source_features)
                source_geometry = source_inventory["vector_geometry"]
                source_blockers = list(source_geometry.get("blockers", []))
                for blocker in source_blockers:
                    aggregate_source_blockers[
                        str(blocker.get("reason") or "source_incomplete")
                    ] += int(blocker.get("count") or 0)
            with phase_timings.measure("import"):
                document, import_report = import_figma_payload(
                    payload,
                    source=str(source_path),
                    image_paths=image_paths,
                )
                imported_features = imported_feature_inventory(document)
                aggregate_imported.update(imported_features)
                aggregate_import_report_variable_binding_count += int(
                    import_report.get("variable_binding_count") or 0
                )
                compatibility = inspect_figma_compatibility(document)
            source_reaction_count = int(
                source_features.get("figma_reaction") or 0
            )
            source_reaction_action_count = int(
                source_features.get("figma_reaction_action") or 0
            )
            native_reaction_count = int(
                import_report.get("native_reaction_count") or 0
            )
            native_reaction_action_count = int(
                import_report.get("native_reaction_action_count") or 0
            )
            recovered_reaction_count = int(
                import_report.get("blocked_recovery_reaction_count") or 0
            )
            recovered_reaction_action_count = int(
                import_report.get("blocked_recovery_action_count") or 0
            )
            reaction_count_conserved = (
                source_reaction_count
                == native_reaction_count + recovered_reaction_count
                == int(import_report.get("source_reaction_count") or 0)
            )
            reaction_action_count_conserved = (
                source_reaction_action_count
                == native_reaction_action_count
                + recovered_reaction_action_count
                == int(
                    import_report.get("source_reaction_action_count") or 0
                )
            )
            reaction_evidence = {
                "status": (
                    "passed"
                    if reaction_count_conserved
                    and reaction_action_count_conserved
                    else "conservation_failed"
                ),
                "source_reaction_count": source_reaction_count,
                "native_reaction_count": native_reaction_count,
                "recovered_reaction_count": recovered_reaction_count,
                "source_action_count": source_reaction_action_count,
                "native_action_count": native_reaction_action_count,
                "recovered_action_count": recovered_reaction_action_count,
            }
            if not reaction_count_conserved:
                case_errors.append("figma_reaction_count_not_conserved")
            if not reaction_action_count_conserved:
                case_errors.append("figma_reaction_action_count_not_conserved")
            source_component_property_binding_count = int(
                source_features.get("component_property_binding") or 0
            )
            active_component_property_binding_count = int(
                imported_features.get(
                    "component_property_binding_active"
                )
                or 0
            )
            recovered_component_property_binding_count = int(
                imported_features.get(
                    "component_property_binding_recovery"
                )
                or 0
            )
            component_property_binding_count_conserved = (
                source_component_property_binding_count
                == active_component_property_binding_count
                + recovered_component_property_binding_count
                == int(
                    imported_features.get("component_property_binding") or 0
                )
                == int(
                    import_report.get(
                        "source_component_property_binding_count"
                    )
                    or 0
                )
            )
            component_property_binding_evidence = {
                "status": (
                    "passed"
                    if component_property_binding_count_conserved
                    else "conservation_failed"
                ),
                "source_count": source_component_property_binding_count,
                "active_count": active_component_property_binding_count,
                "recovered_count": (
                    recovered_component_property_binding_count
                ),
            }
            if not component_property_binding_count_conserved:
                case_errors.append(
                    "figma_component_property_binding_count_not_conserved"
                )
            source_variable_binding_alias_count = int(
                source_features.get("figma_variable_binding_alias") or 0
            )
            imported_variable_binding_alias_count = int(
                imported_features.get("figma_variable_binding_alias") or 0
            )
            import_report_variable_binding_count = int(
                import_report.get("variable_binding_count") or 0
            )
            object_variable_binding_alias_count = int(
                imported_features.get(
                    "figma_variable_binding_alias_object"
                )
                or 0
            )
            artboard_variable_binding_alias_count = int(
                imported_features.get(
                    "figma_variable_binding_alias_artboard"
                )
                or 0
            )
            variable_binding_alias_status_counts = {
                status: int(
                    imported_features.get(
                        f"figma_variable_binding_alias_{status}"
                    )
                    or 0
                )
                for status in (
                    "native",
                    "recovered",
                    "unresolved",
                    "blocked",
                )
            }
            unclassified_variable_binding_alias_count = int(
                imported_features.get(
                    "figma_variable_binding_alias_unclassified"
                )
                or 0
            )
            variable_binding_alias_count_conserved = (
                source_variable_binding_alias_count
                == imported_variable_binding_alias_count
                == import_report_variable_binding_count
                == object_variable_binding_alias_count
                + artboard_variable_binding_alias_count
                == sum(variable_binding_alias_status_counts.values())
                and unclassified_variable_binding_alias_count == 0
            )
            variable_binding_alias_evidence = {
                "status": (
                    "passed"
                    if variable_binding_alias_count_conserved
                    else "conservation_failed"
                ),
                "source_count": source_variable_binding_alias_count,
                "imported_count": imported_variable_binding_alias_count,
                "import_report_count": import_report_variable_binding_count,
                "object_count": object_variable_binding_alias_count,
                "artboard_count": artboard_variable_binding_alias_count,
                "native_count": variable_binding_alias_status_counts[
                    "native"
                ],
                "recovered_count": variable_binding_alias_status_counts[
                    "recovered"
                ],
                "unresolved_count": variable_binding_alias_status_counts[
                    "unresolved"
                ],
                "blocked_count": variable_binding_alias_status_counts[
                    "blocked"
                ],
                "unclassified_count": (
                    unclassified_variable_binding_alias_count
                ),
            }
            if not variable_binding_alias_count_conserved:
                case_errors.append(
                    "figma_variable_binding_alias_count_not_conserved"
                )
            source_geometry_complete_count = int(
                source_geometry.get("complete_count") or 0
            )
            imported_path_geometry_count = int(
                imported_features.get("path_geometry") or 0
            )
            if source_geometry_complete_count <= 0:
                vector_evidence_status = (
                    "source_incomplete"
                    if int(source_geometry.get("node_count") or 0) > 0
                    else "not_applicable"
                )
            elif int(
                source_geometry.get("render_relevant_source_incomplete_count")
                or 0
            ):
                vector_evidence_status = "passed_with_source_incomplete"
            elif imported_path_geometry_count > 0:
                vector_evidence_status = "passed"
            else:
                vector_evidence_status = "import_geometry_missing"
            # Commit source/import evidence before render and UMG checks so a
            # downstream exception cannot erase the corpus-quality diagnosis.
            case_result.update(
                {
                    "source_features": source_features,
                    "source_node_types": source_inventory["node_types"],
                    "unknown_source_node_types": source_inventory[
                        "unknown_node_types"
                    ],
                    "source_geometry": source_geometry,
                    "source_quality": {
                        "clean": not source_blockers,
                        "blockers": source_blockers,
                    },
                    "feature_evidence": {
                        "figma_variable_binding_aliases": (
                            variable_binding_alias_evidence
                        ),
                        "figma_component_property_bindings": (
                            component_property_binding_evidence
                        ),
                        "figma_reactions": reaction_evidence,
                        "vector_geometry": {
                            "status": vector_evidence_status,
                            "source_complete_count": (
                                source_geometry_complete_count
                            ),
                            "source_incomplete_count": int(
                                source_geometry.get("source_incomplete_count")
                                or 0
                            ),
                            "imported_path_geometry_count": (
                                imported_path_geometry_count
                            ),
                        }
                    },
                    "source_details": source_details,
                    "imported_features": imported_features,
                    "import": import_report,
                    "figma_export_compatibility": compatibility,
                }
            )

            render_result: dict[str, Any] = {
                "status": "disabled",
                "passed": None,
            }
            object_count = len(document.get("objects", []))
            if render_smoke:
                if (
                    render_smoke_max_objects > 0
                    and object_count > render_smoke_max_objects
                ):
                    render_result = {
                        "status": "skipped",
                        "passed": None,
                        "reason": "object_limit_exceeded",
                        "object_count": object_count,
                        "max_objects": render_smoke_max_objects,
                        "artboard_selection": {
                            "status": "skipped",
                            "reason": "object_limit_exceeded",
                            "requested_count": render_smoke_artboard_count,
                            "selected_count": 0,
                            "available_count": len(document.get("artboards", [])),
                        },
                        "artboards": [],
                    }
                else:
                    png_path = (
                        output / "renders" / f"{case_id}.png"
                        if write_render_pngs
                        else None
                    )
                    try:
                        with phase_timings.measure("render"):
                            render_result = render_document_smoke(
                                document,
                                width=render_smoke_width,
                                height=render_smoke_height,
                                png_path=png_path,
                            )
                    except Exception as exc:
                        render_result = {
                            "status": "error",
                            "passed": False,
                            "renderer": "PainterUIDesignOverlay.render(QImage)",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                        case_errors.append("painter_render_smoke_error")
                    else:
                        if not render_result["passed"]:
                            case_errors.append(
                                "painter_render_smoke_content_missing"
                                if render_result.get("status") == "content_missing"
                                else "painter_render_smoke_blank"
                            )

                    effective_artboard_count = _focused_render_count(
                        width=render_smoke_width,
                        height=render_smoke_height,
                        requested_count=render_smoke_artboard_count,
                    )
                    selected_artboards = _select_artboards_for_render(
                        document,
                        effective_artboard_count,
                    )
                    pixels_per_smoke = (
                        render_smoke_width * render_smoke_height * 2
                    )
                    render_result["artboard_selection"] = {
                        "status": (
                            "disabled"
                            if render_smoke_artboard_count == 0
                            else "selected"
                        ),
                        "policy": "active_first_middle_last_then_even_sample",
                        "requested_count": render_smoke_artboard_count,
                        "effective_count_limit": effective_artboard_count,
                        "selected_count": len(selected_artboards),
                        "available_count": len(document.get("artboards", [])),
                        "hard_max_count": _MAX_ARTBOARD_RENDER_COUNT,
                        "pixel_work_limit": _MAX_RENDER_PIXEL_WORK,
                        "estimated_pixel_work": pixels_per_smoke
                        * (1 + len(selected_artboards)),
                        "budget_limited": (
                            effective_artboard_count
                            < render_smoke_artboard_count
                        ),
                    }
                    artboard_results: list[dict[str, Any]] = []
                    for artboard in selected_artboards:
                        artboard_id = str(artboard["artboard_id"])
                        artboard_png_path = (
                            output
                            / "renders"
                            / f"{case_id}.artboards"
                            / (
                                f"{int(artboard['artboard_index']):04d}-"
                                f"{_render_filename_component(artboard_id)}.png"
                            )
                            if write_render_pngs
                            else None
                        )
                        try:
                            with phase_timings.measure("render"):
                                artboard_result = render_document_smoke(
                                    document,
                                    width=render_smoke_width,
                                    height=render_smoke_height,
                                    png_path=artboard_png_path,
                                    fit_artboard_id=artboard_id,
                                )
                        except Exception as exc:
                            artboard_result = {
                                "status": "error",
                                "passed": False,
                                "renderer": (
                                    "PainterUIDesignOverlay.render(QImage)"
                                ),
                                "fit_mode": "artboard",
                                "artboard_id": artboard_id,
                                "error": f"{type(exc).__name__}: {exc}",
                            }
                            if "painter_artboard_render_smoke_error" not in case_errors:
                                case_errors.append(
                                    "painter_artboard_render_smoke_error"
                                )
                        else:
                            if not artboard_result["passed"]:
                                error = (
                                    "painter_artboard_render_smoke_content_missing"
                                    if artboard_result.get("status")
                                    == "content_missing"
                                    else "painter_artboard_render_smoke_blank"
                                )
                                if error not in case_errors:
                                    case_errors.append(error)
                        artboard_result.update(artboard)
                        artboard_results.append(artboard_result)
                    render_result["artboards"] = artboard_results

            with phase_timings.measure("roundtrip"):
                serialized = json.loads(json.dumps(document, ensure_ascii=False))
                roundtrip_document = normalize_ui_document(serialized)
                roundtrip_equal = roundtrip_document == normalize_ui_document(
                    document
                )
            if not roundtrip_equal:
                case_errors.append("document_json_roundtrip_mismatch")

            package_result: dict[str, Any] = {}
            if write_packages:
                with phase_timings.measure("package"):
                    package_result = export_figma_plugin_package(
                        document, output / "packages" / case_id
                    )
                    exchange = json.loads(
                        Path(package_result["exchange_path"]).read_text(
                            encoding="utf-8"
                        )
                    )
                    exported_document = normalize_ui_document(
                        exchange["document"]
                    )
                    if exported_document != normalize_ui_document(document):
                        case_errors.append("figma_exchange_roundtrip_mismatch")

            umg_counts: Counter[str] = Counter()
            blocker_reasons: Counter[str] = Counter()
            umg_errors: list[str] = []
            with phase_timings.measure("preflight"):
                umg_session = PainterUMGConversionSession(document)
                for artboard in document.get("artboards", []):
                    try:
                        preflight = umg_session.preflight(
                            artboard_id=str(artboard["id"])
                        )
                        umg_counts.update(preflight.get("counts", {}))
                        for blocker in preflight.get("blockers", []):
                            blocker_reasons.update(
                                str(reason)
                                for reason in blocker.get("reasons", [])
                            )
                    except Exception as exc:  # Keep every per-artboard failure.
                        umg_errors.append(
                            f"{artboard.get('id')}: {type(exc).__name__}: {exc}"
                        )
            if umg_errors:
                case_errors.append("umg_preflight_error")
            if require_umg_clean and blocker_reasons:
                case_errors.append("umg_preflight_has_blockers")
            aggregate_umg.update(umg_counts)
            aggregate_blockers.update(blocker_reasons)
            case_errors.extend(
                _case_expectation_errors(
                    item,
                    import_report=import_report,
                    source_features=source_features,
                    imported_features=imported_features,
                    unknown_node_types=source_inventory["unknown_node_types"],
                )
            )
            case_result.update(
                {
                    "passed": not case_errors,
                    "errors": case_errors,
                    "source_features": source_features,
                    "source_node_types": source_inventory["node_types"],
                    "unknown_source_node_types": source_inventory["unknown_node_types"],
                    "source_geometry": source_geometry,
                    "source_quality": {
                        "clean": not source_blockers,
                        "blockers": source_blockers,
                    },
                    "feature_evidence": {
                        "figma_variable_binding_aliases": (
                            variable_binding_alias_evidence
                        ),
                        "figma_component_property_bindings": (
                            component_property_binding_evidence
                        ),
                        "figma_reactions": reaction_evidence,
                        "vector_geometry": {
                            "status": vector_evidence_status,
                            "source_complete_count": (
                                source_geometry_complete_count
                            ),
                            "source_incomplete_count": int(
                                source_geometry.get("source_incomplete_count")
                                or 0
                            ),
                            "imported_path_geometry_count": (
                                imported_path_geometry_count
                            ),
                        }
                    },
                    "source_details": source_details,
                    "imported_features": imported_features,
                    "import": import_report,
                    "figma_export_compatibility": compatibility,
                    "render_smoke": render_result,
                    "roundtrip_equal": roundtrip_equal,
                    "package": package_result,
                    "umg": {
                        "clean": not blocker_reasons and not umg_errors,
                        "counts": dict(sorted(umg_counts.items())),
                        "blocker_reasons": dict(sorted(blocker_reasons.items())),
                        "errors": umg_errors,
                    },
                }
            )
        except Exception as exc:
            case_result.update(
                {
                    "passed": False,
                    "errors": [f"{type(exc).__name__}: {exc}"],
                }
            )
            case_result.setdefault("source_features", {})
            case_result.setdefault("imported_features", {})
        case_result["performance"] = phase_timings.report()
        rows.append(case_result)
    report_options = {
        "write_packages": bool(write_packages),
        "require_umg_clean": bool(require_umg_clean),
        "render_smoke": bool(render_smoke),
        "render_smoke_width": render_smoke_width,
        "render_smoke_height": render_smoke_height,
        "render_smoke_max_objects": render_smoke_max_objects,
        "render_smoke_artboard_count": render_smoke_artboard_count,
        "write_render_pngs": bool(write_render_pngs),
    }
    report = {
        "schema": _CORPUS_REPORT_SCHEMA,
        "manifest": str(manifest_path),
        "assets_root": str(assets_root),
        "options": report_options,
        "case_count": len(rows),
        "passed_count": sum(bool(row["passed"]) for row in rows),
        "umg_clean_count": sum(bool(row.get("umg", {}).get("clean")) for row in rows),
        "render_smoke_attempted_count": sum(
            row.get("render_smoke", {}).get("status") in _RENDER_ATTEMPT_STATUSES
            for row in rows
        ),
        "render_smoke_passed_count": sum(
            row.get("render_smoke", {}).get("status") == "passed" for row in rows
        ),
        "render_smoke_skipped_count": sum(
            row.get("render_smoke", {}).get("status") == "skipped" for row in rows
        ),
        "render_artboard_smoke_attempted_count": sum(
            artboard.get("status") in _RENDER_ATTEMPT_STATUSES
            for row in rows
            for artboard in row.get("render_smoke", {}).get("artboards", [])
        ),
        "render_artboard_smoke_passed_count": sum(
            artboard.get("status") == "passed"
            for row in rows
            for artboard in row.get("render_smoke", {}).get("artboards", [])
        ),
        "render_artboard_smoke_failed_count": sum(
            artboard.get("status") in _RENDER_ATTEMPT_STATUSES
            and artboard.get("status") != "passed"
            for row in rows
            for artboard in row.get("render_smoke", {}).get("artboards", [])
        ),
        "passed": bool(rows) and all(bool(row["passed"]) for row in rows),
        "source_quality_clean_count": sum(
            bool(row.get("source_quality", {}).get("clean")) for row in rows
        ),
        "source_incomplete_vector_geometry_case_count": sum(
            int(
                row.get("source_geometry", {}).get("source_incomplete_count")
                or 0
            )
            > 0
            for row in rows
        ),
        "source_incomplete_vector_geometry_blocked_case_count": sum(
            int(
                row.get("source_geometry", {}).get(
                    "source_incomplete_blocker_count"
                )
                or 0
            )
            > 0
            for row in rows
        ),
        "vector_geometry_evidence_passed_count": sum(
            row.get("feature_evidence", {})
            .get("vector_geometry", {})
            .get("status")
            in {"passed", "passed_with_source_incomplete"}
            for row in rows
        ),
        "figma_reaction_conservation": {
            "status": (
                "passed"
                if (
                    int(aggregate_source["figma_reaction"])
                    == int(aggregate_imported["figma_reaction_native"])
                    + int(aggregate_imported["figma_reaction_recovery"])
                    and int(aggregate_source["figma_reaction_action"])
                    == int(
                        aggregate_imported["figma_reaction_native_action"]
                    )
                    + int(
                        aggregate_imported[
                            "figma_reaction_recovered_action"
                        ]
                    )
                )
                else "conservation_failed"
            ),
            "source_reaction_count": int(
                aggregate_source["figma_reaction"]
            ),
            "native_reaction_count": int(
                aggregate_imported["figma_reaction_native"]
            ),
            "recovered_reaction_count": int(
                aggregate_imported["figma_reaction_recovery"]
            ),
            "source_action_count": int(
                aggregate_source["figma_reaction_action"]
            ),
            "native_action_count": int(
                aggregate_imported["figma_reaction_native_action"]
            ),
            "recovered_action_count": int(
                aggregate_imported["figma_reaction_recovered_action"]
            ),
        },
        "figma_component_property_binding_conservation": {
            "status": (
                "passed"
                if int(aggregate_source["component_property_binding"])
                == int(
                    aggregate_imported[
                        "component_property_binding_active"
                    ]
                )
                + int(
                    aggregate_imported[
                        "component_property_binding_recovery"
                    ]
                )
                == int(
                    aggregate_imported["component_property_binding"]
                )
                else "conservation_failed"
            ),
            "source_count": int(
                aggregate_source["component_property_binding"]
            ),
            "active_count": int(
                aggregate_imported["component_property_binding_active"]
            ),
            "recovered_count": int(
                aggregate_imported["component_property_binding_recovery"]
            ),
        },
        "figma_variable_binding_alias_conservation": {
            "status": (
                "passed"
                if int(
                    aggregate_source["figma_variable_binding_alias"]
                )
                == int(
                    aggregate_imported["figma_variable_binding_alias"]
                )
                == int(aggregate_import_report_variable_binding_count)
                == int(
                    aggregate_imported[
                        "figma_variable_binding_alias_object"
                    ]
                )
                + int(
                    aggregate_imported[
                        "figma_variable_binding_alias_artboard"
                    ]
                )
                == sum(
                    int(
                        aggregate_imported[
                            f"figma_variable_binding_alias_{status}"
                        ]
                    )
                    for status in (
                        "native",
                        "recovered",
                        "unresolved",
                        "blocked",
                    )
                )
                and int(
                    aggregate_imported[
                        "figma_variable_binding_alias_unclassified"
                    ]
                )
                == 0
                else "conservation_failed"
            ),
            "source_count": int(
                aggregate_source["figma_variable_binding_alias"]
            ),
            "imported_count": int(
                aggregate_imported["figma_variable_binding_alias"]
            ),
            "import_report_count": int(
                aggregate_import_report_variable_binding_count
            ),
            "object_count": int(
                aggregate_imported[
                    "figma_variable_binding_alias_object"
                ]
            ),
            "artboard_count": int(
                aggregate_imported[
                    "figma_variable_binding_alias_artboard"
                ]
            ),
            "native_count": int(
                aggregate_imported[
                    "figma_variable_binding_alias_native"
                ]
            ),
            "recovered_count": int(
                aggregate_imported[
                    "figma_variable_binding_alias_recovered"
                ]
            ),
            "unresolved_count": int(
                aggregate_imported[
                    "figma_variable_binding_alias_unresolved"
                ]
            ),
            "blocked_count": int(
                aggregate_imported[
                    "figma_variable_binding_alias_blocked"
                ]
            ),
            "unclassified_count": int(
                aggregate_imported[
                    "figma_variable_binding_alias_unclassified"
                ]
            ),
        },
        "source_feature_totals": dict(sorted(aggregate_source.items())),
        "imported_feature_totals": dict(sorted(aggregate_imported.items())),
        "source_blocker_reason_totals": dict(
            sorted(aggregate_source_blockers.items())
        ),
        "umg_disposition_totals": dict(sorted(aggregate_umg.items())),
        "umg_blocker_reason_totals": dict(sorted(aggregate_blockers.items())),
        "cases": rows,
    }
    report["performance"] = _aggregate_performance(
        rows,
        case_ids=[str(row["id"]) for row in rows],
        options=report_options,
        profile=_performance_profile(clock_name=timing_clock_name),
    )
    report["coverage"] = _release_coverage_report(
        manifest,
        rows,
        enforce=not selected,
    )
    baseline_report: Mapping[str, Any] | None
    if performance_baseline is None:
        baseline_report = None
    elif isinstance(performance_baseline, Mapping):
        baseline_report = performance_baseline
    else:
        baseline_path = Path(performance_baseline).expanduser().resolve()
        loaded_baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        if not isinstance(loaded_baseline, Mapping):
            raise FigmaCorpusError(
                "Performance baseline report must contain an object"
            )
        baseline_report = loaded_baseline
    performance_comparison = compare_performance_reports(
        report,
        baseline_report,
        max_regression_percent=max_performance_regression_percent,
    )
    report["performance"]["comparison"] = performance_comparison
    report["errors"] = []
    if report["coverage"]["errors"]:
        report["errors"].extend(report["coverage"]["errors"])
        report["passed"] = False
    if performance_comparison["status"] == "failed":
        report["errors"].append(_PERFORMANCE_REGRESSION_ERROR)
        report["passed"] = False
    elif performance_comparison["status"] == "not_comparable":
        report["errors"].append(_PERFORMANCE_NOT_COMPARABLE_ERROR)
        report["passed"] = False
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import, round-trip, and UMG-preflight the public Figma corpus."
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--assets-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument(
        "--output",
        default=str(ROOT / "debugCapture" / "painter_ui_figma_document_corpus"),
    )
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--write-packages", action="store_true")
    parser.add_argument("--require-umg-clean", action="store_true")
    parser.add_argument(
        "--render-smoke",
        action="store_true",
        help="Render each imported document through PainterUIDesignOverlay offscreen.",
    )
    parser.add_argument("--render-width", type=int, default=960)
    parser.add_argument("--render-height", type=int, default=640)
    parser.add_argument(
        "--render-max-objects",
        type=int,
        default=0,
        help="Skip render smoke above this object count (0 means unlimited).",
    )
    parser.add_argument(
        "--render-artboard-count",
        type=int,
        default=4,
        help=(
            "Render this many focused artboards in addition to the whole document "
            f"(0 disables, maximum {_MAX_ARTBOARD_RENDER_COUNT})."
        ),
    )
    parser.add_argument(
        "--no-render-pngs",
        action="store_true",
        help="Keep render metrics but do not write PNG evidence.",
    )
    parser.add_argument(
        "--performance-baseline",
        type=Path,
        default=None,
        help=(
            "Opt in to the performance ratchet by comparing against this "
            "previous corpus report.json."
        ),
    )
    parser.add_argument(
        "--max-performance-regression-percent",
        type=float,
        default=_DEFAULT_MAX_PERFORMANCE_REGRESSION_PERCENT,
        help=(
            "Maximum comparable non-render core regression (default: 15). "
            "This is the only override for the threshold."
        ),
    )
    args = parser.parse_args()
    try:
        report = run_corpus(
            args.manifest,
            args.assets_root,
            args.output,
            write_packages=args.write_packages,
            require_umg_clean=args.require_umg_clean,
            case_ids=set(args.case),
            render_smoke=args.render_smoke,
            render_smoke_width=args.render_width,
            render_smoke_height=args.render_height,
            render_smoke_max_objects=args.render_max_objects,
            render_smoke_artboard_count=args.render_artboard_count,
            write_render_pngs=not args.no_render_pngs,
            performance_baseline=args.performance_baseline,
            max_performance_regression_percent=(
                args.max_performance_regression_percent
            ),
        )
    except (FigmaCorpusError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    summary = {
        "ok": report["passed"],
        "case_count": report["case_count"],
        "passed_count": report["passed_count"],
        "source_quality_clean_count": report["source_quality_clean_count"],
        "source_incomplete_vector_geometry_case_count": report[
            "source_incomplete_vector_geometry_case_count"
        ],
        "source_incomplete_vector_geometry_blocked_case_count": report[
            "source_incomplete_vector_geometry_blocked_case_count"
        ],
        "vector_geometry_evidence_passed_count": report[
            "vector_geometry_evidence_passed_count"
        ],
        "figma_reaction_conservation": report[
            "figma_reaction_conservation"
        ],
        "figma_component_property_binding_conservation": report[
            "figma_component_property_binding_conservation"
        ],
        "figma_variable_binding_alias_conservation": report[
            "figma_variable_binding_alias_conservation"
        ],
        "source_blocker_reason_totals": report[
            "source_blocker_reason_totals"
        ],
        "umg_clean_count": report["umg_clean_count"],
        "render_smoke_attempted_count": report["render_smoke_attempted_count"],
        "render_smoke_passed_count": report["render_smoke_passed_count"],
        "render_smoke_skipped_count": report["render_smoke_skipped_count"],
        "render_artboard_smoke_attempted_count": report[
            "render_artboard_smoke_attempted_count"
        ],
        "render_artboard_smoke_passed_count": report[
            "render_artboard_smoke_passed_count"
        ],
        "render_artboard_smoke_failed_count": report[
            "render_artboard_smoke_failed_count"
        ],
        "umg_disposition_totals": report["umg_disposition_totals"],
        "performance": {
            "measurement_status": report["performance"][
                "measurement_status"
            ],
            "metric": report["performance"]["metric"],
            "comparison": report["performance"]["comparison"],
        },
        "top_umg_blockers": sorted(
            report["umg_blocker_reason_totals"].items(),
            key=lambda item: (-item[1], item[0]),
        )[:10],
        "report": str(Path(args.output).expanduser().resolve() / "report.json"),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
