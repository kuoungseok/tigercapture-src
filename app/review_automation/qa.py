from __future__ import annotations

import json
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .artifacts import feature_editor_surface_artifact_id, feature_editor_surface_specs
from .feature_action_scenarios import default_feature_action_scenarios
from .paths import DEFAULT_REVIEW_REPORT


ROOT = Path(__file__).resolve().parents[2]


class _LocalReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_names = ("href", "src", "poster")
        for name, value in attrs:
            if name in attr_names and value:
                self.refs.append(value)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve(root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _check_html_refs(path: Path) -> tuple[list[str], int]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"html unreadable: {path} {exc!r}"], 0
    parser = _LocalReferenceParser()
    parser.feed(text)
    failures: list[str] = []
    checked = 0
    for ref in parser.refs:
        if "://" in ref or ref.startswith("#") or ref.startswith("mailto:"):
            continue
        checked += 1
        target = (path.parent / ref).resolve()
        if not target.exists():
            failures.append(f"missing html reference: {path.name} -> {ref}")
    return failures, checked


def _check_pptx(path: Path) -> tuple[list[str], dict[str, int]]:
    metrics = {"slides": 0, "media": 0}
    if not path.exists():
        return [f"missing pptx: {path}"], metrics
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
    except Exception as exc:
        return [f"pptx unreadable: {path} {exc!r}"], metrics
    required = {
        "[Content_Types].xml",
        "ppt/presentation.xml",
        "ppt/slides/slide1.xml",
    }
    failures = [f"pptx missing entry: {name}" for name in sorted(required - names)]
    metrics["slides"] = len([name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")])
    metrics["media"] = len([name for name in names if name.startswith("ppt/media/")])
    if metrics["slides"] < 1:
        failures.append("pptx has no slides")
    return failures, metrics


def _check_visual_artifact(path: Path) -> tuple[list[str], list[str], dict[str, int]]:
    metrics = {"checked": 0, "flat": 0, "small": 0}
    failures: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return failures, warnings, metrics
    try:
        from PIL import Image, ImageStat

        with Image.open(path) as image:
            frame = image.convert("RGB")
            width, height = frame.size
            metrics["checked"] = 1
            if width < 32 or height < 32:
                metrics["small"] = 1
                failures.append(f"visual artifact too small: {path} ({width}x{height})")
            elif width < 96 or height < 96:
                metrics["small"] = 1
                warnings.append(f"visual artifact is a small crop: {path} ({width}x{height})")
            gray = frame.convert("L")
            stat = ImageStat.Stat(gray)
            extrema = stat.extrema[0] if stat.extrema else (0, 0)
            if int(extrema[1]) - int(extrema[0]) < 3:
                metrics["flat"] = 1
                warnings.append(f"visual artifact appears flat: {path}")
    except Exception as exc:
        failures.append(f"visual artifact unreadable: {path} {exc!r}")
    return failures, warnings, metrics


def validate_review_automation_report(
    report_path: str | Path = DEFAULT_REVIEW_REPORT,
    *,
    project_root: str | Path = ROOT,
) -> dict[str, Any]:
    root = Path(project_root)
    report_file = _resolve(root, report_path)
    report = _load_json(report_file)
    failures: list[str] = []
    warnings: list[str] = []
    if not report:
        failures.append(f"missing or unreadable report: {report_file}")
        return {
            "kind": "review_automation_qa",
            "ok": False,
            "report_path": str(report_file),
            "summary": {"features": 0, "artifacts": 0, "html_refs": 0, "slides": 0},
            "failures": failures,
            "warnings": warnings,
        }
    if report.get("kind") != "review_automation_report":
        failures.append(f"unexpected report kind: {report.get('kind')}")
    if not report.get("ok"):
        failures.append("review automation report ok=false")
    if report.get("stale"):
        failures.append("review automation report is stale")
    scenarios = [row for row in list(report.get("scenarios", []) or []) if isinstance(row, dict)]
    if not scenarios:
        failures.append("review scenario manifest is missing")
    graph = report.get("evidence_graph") if isinstance(report.get("evidence_graph"), dict) else {}
    if not graph:
        failures.append("review evidence graph is missing")

    artifacts = [row for row in list(report.get("artifacts", []) or []) if isinstance(row, dict)]
    missing_artifacts = [
        str(row.get("output_path") or row.get("id") or "artifact")
        for row in artifacts
        if row.get("output_path") and not _resolve(root, str(row.get("output_path"))).exists()
    ]
    failures.extend(f"missing artifact: {path}" for path in missing_artifacts[:20])
    catalog_required = {"catalog_editor_surface", "catalog_timeline_detail"}
    artifact_ids = {str(row.get("id") or "") for row in artifacts}
    for artifact_id in sorted(catalog_required - artifact_ids):
        failures.append(f"missing catalog artifact required by no-empty-editor rule: {artifact_id}")
    catalog_active = 0
    for row in artifacts:
        artifact_id = str(row.get("id") or "")
        if artifact_id not in catalog_required:
            continue
        if row.get("active_editor") is True and row.get("catalog_rule") == "no_empty_editor":
            catalog_active += 1
        else:
            failures.append(f"catalog artifact violates no-empty-editor rule: {artifact_id}")
        source_path = str(row.get("source_path") or "").lower()
        if "editor_empty" in source_path:
            failures.append(f"catalog artifact uses empty editor source: {artifact_id}")
    feature_surface_ids = {
        feature_editor_surface_artifact_id(str(spec.get("id") or ""))
        for spec in feature_editor_surface_specs()
        if spec.get("id")
    }
    feature_editor_artifacts = 0
    for artifact_id in sorted(feature_surface_ids - artifact_ids):
        failures.append(f"missing feature editor screenshot artifact: {artifact_id}")
    for row in artifacts:
        artifact_id = str(row.get("id") or "")
        if artifact_id not in feature_surface_ids:
            continue
        if row.get("feature_editor") is True and row.get("exists"):
            feature_editor_artifacts += 1
        else:
            failures.append(f"feature editor screenshot artifact is not ready: {artifact_id}")
        if str(row.get("capture_method") or "") != "live_editor_action_capture":
            failures.append(f"feature editor screenshot is not a live action capture: {artifact_id}")

    feature_action_scenarios = [
        row
        for row in list(report.get("feature_action_scenarios", []) or [])
        if isinstance(row, dict)
    ]
    feature_action_required = {scenario.id for scenario in default_feature_action_scenarios()}
    feature_action_by_id = {
        str(row.get("id") or ""): row
        for row in feature_action_scenarios
        if row.get("id")
    }
    feature_action_ready_statuses = {"action_plan_ready", "captured", "live_captured", "evidence_ready"}
    feature_action_ready = 0
    for scenario_id in sorted(feature_action_required - set(feature_action_by_id)):
        failures.append(f"missing feature action scenario: {scenario_id}")
    for scenario_id in sorted(feature_action_required & set(feature_action_by_id)):
        row = feature_action_by_id[scenario_id]
        status = str(row.get("status") or "")
        artifact_id = str(row.get("artifact_id") or "")
        action_ids = [str(action_id) for action_id in list(row.get("action_ids", []) or [])]
        if status in feature_action_ready_statuses and row.get("dry_run_ok") is True:
            feature_action_ready += 1
        else:
            failures.append(f"feature action scenario is not ready: {scenario_id} ({status or 'unknown'})")
        if artifact_id not in artifact_ids:
            failures.append(f"feature action scenario references missing artifact: {scenario_id} -> {artifact_id}")
        if "capture.screenshot" not in action_ids:
            failures.append(f"feature action scenario lacks screenshot capture action: {scenario_id}")
    visual_metrics = {"checked": 0, "flat": 0, "small": 0}
    for row in artifacts:
        kind = str(row.get("kind") or "").lower()
        output_path = str(row.get("output_path") or "")
        if not output_path or kind not in {"screenshot", "image", "contact_sheet", "gif"}:
            continue
        visual_failures, visual_warnings, metrics = _check_visual_artifact(_resolve(root, output_path))
        failures.extend(visual_failures[:8])
        warnings.extend(visual_warnings[:8])
        for key in visual_metrics:
            visual_metrics[key] += int(metrics.get(key, 0) or 0)

    features = [row for row in list(report.get("features", []) or []) if isinstance(row, dict)]
    feature_pages = list((report.get("outputs", {}) or {}).get("feature_pages", []) or [])
    if features and len(feature_pages) < len(features):
        failures.append(f"feature pages incomplete: {len(feature_pages)}/{len(features)}")

    html_refs_checked = 0
    html_paths: list[Path] = []
    html_output = (report.get("outputs", {}) or {}).get("html")
    if html_output:
        html_paths.append(_resolve(root, str(html_output)))
    for page in feature_pages:
        html_paths.append(_resolve(root, str(page)))
    for path in html_paths:
        if not path.exists():
            failures.append(f"missing html page: {path}")
            continue
        ref_failures, checked = _check_html_refs(path)
        html_refs_checked += checked
        failures.extend(ref_failures[:20])

    ppt_metrics = {"slides": 0, "media": 0}
    ppt_output = (report.get("outputs", {}) or {}).get("pptx")
    if ppt_output:
        ppt_failures, ppt_metrics = _check_pptx(_resolve(root, str(ppt_output)))
        failures.extend(ppt_failures)
    else:
        warnings.append("pptx output not declared")

    blocked_features = [row.get("id") for row in features if row.get("status") == "blocked"]
    summary = {
        "features": len(features),
        "scenarios": len(scenarios),
        "blocked_features": len(blocked_features),
        "artifacts": len(artifacts),
        "missing_artifacts": len(missing_artifacts),
        "html_pages": len(html_paths),
        "html_refs": html_refs_checked,
        "slides": int(ppt_metrics.get("slides", 0) or 0),
        "ppt_media": int(ppt_metrics.get("media", 0) or 0),
        "visual_artifacts_checked": int(visual_metrics.get("checked", 0) or 0),
        "flat_visual_artifacts": int(visual_metrics.get("flat", 0) or 0),
        "small_visual_artifacts": int(visual_metrics.get("small", 0) or 0),
        "catalog_active_editor_artifacts": catalog_active,
        "feature_editor_artifacts": feature_editor_artifacts,
        "feature_editor_artifacts_required": len(feature_surface_ids),
        "feature_action_scenarios": len(feature_action_scenarios),
        "feature_action_scenarios_required": len(feature_action_required),
        "feature_action_ready": feature_action_ready,
    }
    if blocked_features:
        warnings.append("blocked features: " + ", ".join(str(item) for item in blocked_features[:8]))
    return {
        "kind": "review_automation_qa",
        "ok": not failures,
        "report_path": str(report_file),
        "summary": summary,
        "failures": failures,
        "warnings": warnings,
    }
