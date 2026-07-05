from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .artifacts import build_input_snapshot, collect_review_artifacts, relpath
from .deck_modes import build_deck_plan, normalize_deck_mode
from .evidence_graph import write_review_evidence_graph
from .feature_action_scenarios import build_feature_action_scenario_report
from .html_export import write_review_site
from .paths import DEFAULT_REVIEW_OUTPUT_DIR, DEFAULT_REVIEW_REPORT, DEFAULT_REVIEW_SAMPLE_REPORT
from .ppt_export import write_review_pptx
from .registry import default_review_features, evaluate_review_features
from .sample_resources import DEFAULT_REVIEW_SAMPLE_MANIFEST, review_sample_resource_report
from .scenario_manifest import default_review_scenarios, evaluate_review_scenarios


ROOT = Path(__file__).resolve().parents[2]


INPUT_FINGERPRINT_PATHS: tuple[str, ...] = (
    "SPEC.md",
    "README.md",
    "TODO.md",
    "docs/RELEASE_POSITIONING.md",
    "docs/SPEC_REVIEW_AUTOMATION.md",
    DEFAULT_REVIEW_SAMPLE_MANIFEST,
    DEFAULT_REVIEW_SAMPLE_REPORT,
    "docs/review_reference_featpaper_style.md",
    "docs/UI_RENEWAL_EVIDENCE_INDEX.md",
    "docs/SPEC_AI_TEXT_EDITING.md",
    "docs/SPEC_AR_PBR_COMPOSITOR.md",
    "docs/SPEC_BROADCAST_SCENE.md",
    "docs/SPEC_EXPORT_PARITY_AND_QA.md",
    "docs/SPEC_LOCAL_AI_PROVIDERS.md",
    "docs/SPEC_NATIVE_WORKER.md",
    "docs/SPEC_PYTHON_ACTION_SYSTEM.md",
    "docs/SPEC_VSEEFACE_BRIDGE.md",
    "app/actions/registry.py",
    "app/actions/editor_adapter.py",
    "debugCapture/editor_e2e_smoke_report.json",
    "debugCapture/screenstudio_auto_polish_qa.json",
    "debugCapture/ai_edit_corpus_quality_qa.json",
    "debugCapture/color_audio_accuracy_qa.json",
)


def _load_prior_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(
    features: list[Mapping[str, Any]],
    artifacts: list[Mapping[str, Any]],
    sample_report: Mapping[str, Any],
    scenarios: list[Mapping[str, Any]] | None = None,
    feature_action_scenarios: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    statuses = [str(row.get("status") or "unknown") for row in features]
    scenario_statuses = [str(row.get("status") or "unknown") for row in list(scenarios or [])]
    feature_action_statuses = [
        str(row.get("status") or "unknown")
        for row in list(feature_action_scenarios or [])
        if isinstance(row, Mapping)
    ]
    return {
        "features": len(features),
        "evidence_ready": statuses.count("evidence_ready"),
        "implemented": statuses.count("implemented"),
        "blocked": statuses.count("blocked"),
        "planned": statuses.count("planned"),
        "scenarios": len(scenario_statuses),
        "scenario_ready": sum(1 for status in scenario_statuses if status in {"captured", "action_ready", "evidence_ready"}),
        "scenario_pending": scenario_statuses.count("pending_evidence"),
        "feature_action_scenarios": len(feature_action_statuses),
        "feature_action_ready": sum(
            1
            for status in feature_action_statuses
            if status in {"action_plan_ready", "captured", "live_captured", "evidence_ready"}
        ),
        "feature_action_pending": feature_action_statuses.count("pending_evidence"),
        "artifacts": len(artifacts),
        "ready_artifacts": sum(1 for row in artifacts if row.get("exists")),
        "sample_resources": int(sample_report.get("resource_count", 0) or 0),
        "sample_resources_ready": int(sample_report.get("ready_count", 0) or 0),
        "missing_required_samples": int(sample_report.get("missing_required_count", 0) or 0),
    }


def build_review_automation_report(
    *,
    project_root: str | Path = ROOT,
    out_dir: str | Path = DEFAULT_REVIEW_OUTPUT_DIR,
    report_path: str | Path = DEFAULT_REVIEW_REPORT,
    sample_manifest: str | Path = DEFAULT_REVIEW_SAMPLE_MANIFEST,
    write_html: bool = True,
    write_ppt: bool = True,
    deck_mode: str = "summary",
    force: bool = False,
) -> dict[str, Any]:
    root = Path(project_root)
    out = Path(out_dir)
    report_file = Path(report_path)
    out.mkdir(parents=True, exist_ok=True)

    sample_report = review_sample_resource_report(sample_manifest, root=root, create_default_if_missing=False)
    features = evaluate_review_features(
        default_review_features(),
        sample_report=sample_report,
        project_root=root,
    )
    normalized_deck_mode = normalize_deck_mode(deck_mode)
    deck_plan = build_deck_plan(
        mode=normalized_deck_mode,
        project_root=root,
        review_features=features,
    )
    artifacts, warnings = collect_review_artifacts(
        project_root=root,
        out_dir=out,
        sample_report=sample_report,
        force=force,
    )
    feature_action_report, feature_action_artifact = build_feature_action_scenario_report(
        project_root=root,
        out_dir=out,
        sample_report=sample_report,
        artifacts=artifacts,
        force=force,
    )
    feature_action_scenarios = [
        row
        for row in list(feature_action_report.get("scenarios", []) or [])
        if isinstance(row, Mapping)
    ]
    artifacts.append(feature_action_artifact)
    warnings.extend(str(row) for row in list(feature_action_report.get("warnings", []) or []))
    scenarios = evaluate_review_scenarios(
        default_review_scenarios(),
        sample_report=sample_report,
        artifacts=artifacts,
        features=features,
    )
    input_snapshot = build_input_snapshot(INPUT_FINGERPRINT_PATHS, root=root)
    prior = _load_prior_report(report_file)
    previous_digest = (
        ((prior.get("input_snapshot") or {}).get("digest"))
        if isinstance(prior.get("input_snapshot"), Mapping)
        else None
    )
    stale_before_run = bool(previous_digest and previous_digest != input_snapshot.get("digest"))
    blocking_artifact_warnings = [
        str(row)
        for row in warnings
        if str(row).startswith("failed to build public catalog")
    ]
    report: dict[str, Any] = {
        "kind": "review_automation_report",
        "ok": bool(
            sample_report.get("ok")
            and feature_action_report.get("ok")
            and warnings.count("failed to build review contact sheet") == 0
            and not blocking_artifact_warnings
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_path": relpath(report_file, root=root),
        "output_dir": relpath(out, root=root),
        "summary": _summary(features, artifacts, sample_report, scenarios, feature_action_scenarios),
        "deck_mode": normalized_deck_mode,
        "deck_plan": deck_plan,
        "sample_report": sample_report,
        "features": features,
        "scenarios": scenarios,
        "feature_action_scenarios": feature_action_scenarios,
        "artifacts": artifacts,
        "warnings": warnings,
        "input_snapshot": input_snapshot,
        "previous_input_digest": previous_digest,
        "stale_before_run": stale_before_run,
        "stale": False,
        "outputs": {},
    }
    report["outputs"]["feature_action_scenarios"] = feature_action_artifact["output_path"]
    evidence_graph, evidence_graph_artifact = write_review_evidence_graph(
        report,
        out / "evidence_graph.json",
        project_root=root,
    )
    report["evidence_graph"] = evidence_graph
    report["outputs"]["evidence_graph"] = evidence_graph_artifact["output_path"]
    artifacts.append(evidence_graph_artifact)

    if write_html:
        html_path, feature_pages = write_review_site(report, out / "site", project_root=root)
        report["outputs"]["html"] = relpath(html_path, root=root)
        report["outputs"]["feature_pages"] = [str(row.get("output_path")) for row in feature_pages]
        artifacts.append(
            {
                "id": "review_site",
                "title": "Review automation HTML site",
                "kind": "html",
                "source_path": "",
                "output_path": relpath(html_path, root=root),
                "exists": html_path.exists(),
                "size": int(html_path.stat().st_size) if html_path.exists() else 0,
            }
        )
        artifacts.extend(feature_pages)
    if write_ppt:
        suffix = "" if normalized_deck_mode == "summary" else f"_{normalized_deck_mode.replace('-', '_')}"
        ppt_path = out / f"TigerCapture_Review_Automation{suffix}.pptx"
        try:
            write_review_pptx(report, ppt_path, project_root=root, deck_mode=normalized_deck_mode)
            report["outputs"]["pptx"] = relpath(ppt_path, root=root)
            artifacts.append(
                {
                    "id": "review_deck",
                    "title": "Review automation PowerPoint deck",
                    "kind": "pptx",
                    "source_path": "",
                    "output_path": relpath(ppt_path, root=root),
                    "exists": ppt_path.exists(),
                    "size": int(ppt_path.stat().st_size) if ppt_path.exists() else 0,
                }
            )
        except Exception as exc:
            warnings.append(f"failed to build PPTX: {exc!r}")
            report["ok"] = False

    report["artifacts"] = artifacts
    report["warnings"] = warnings
    scenarios = evaluate_review_scenarios(
        default_review_scenarios(),
        sample_report=sample_report,
        artifacts=artifacts,
        features=features,
    )
    report["scenarios"] = scenarios
    evidence_graph, evidence_graph_artifact = write_review_evidence_graph(
        report,
        out / "evidence_graph.json",
        project_root=root,
    )
    report["evidence_graph"] = evidence_graph
    report["outputs"]["evidence_graph"] = evidence_graph_artifact["output_path"]
    for index, row in enumerate(artifacts):
        if row.get("id") == "evidence_graph":
            artifacts[index] = evidence_graph_artifact
            break
    else:
        artifacts.append(evidence_graph_artifact)
    report["summary"] = _summary(features, artifacts, sample_report, scenarios, feature_action_scenarios)
    final_blocking_warnings = [
        str(row)
        for row in warnings
        if str(row).startswith("failed to build public catalog")
    ]
    report["ok"] = bool(
        sample_report.get("ok")
        and feature_action_report.get("ok")
        and warnings.count("failed to build review contact sheet") == 0
        and not final_blocking_warnings
    )
    if write_html and report["outputs"].get("html"):
        # Rewrite once so output links and artifact counts are reflected in the site.
        _, feature_pages = write_review_site(report, out / "site", project_root=root)
        for row in feature_pages:
            if not any(existing.get("id") == row.get("id") for existing in artifacts):
                artifacts.append(row)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
