"""Write a conservative professional NLE readiness QA report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.nle_readiness import build_nle_readiness_report, format_nle_readiness_summary


def _real_corpus_claim_ready(report: dict[str, Any] | None) -> bool:
    report = report if isinstance(report, dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    thresholds = report.get("thresholds") if isinstance(report.get("thresholds"), dict) else {}
    require_validation = bool(thresholds.get("require_validation_evidence", True))
    min_projects = int(thresholds.get("min_projects") or 3)
    validation_ready = (
        not require_validation
        or (
            int(summary.get("validation_ready_count") or 0) >= max(1, min_projects)
            and int(summary.get("validation_failed_required_check_count") or 0) == 0
        )
    )
    return bool((report.get("claim_ready") or report.get("real_world_corpus")) and validation_ready)


def run_nle_readiness_qa(
    *,
    snapshot: dict[str, Any] | None = None,
    synthetic_contract_corpus: bool = True,
    long_project_stress_report: dict[str, Any] | None = None,
    real_project_corpus_report: dict[str, Any] | None = None,
    timeline_fuzzer_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the QA payload used by CLI tests and dashboard collection."""
    try:
        from app.actions import build_default_action_registry

        action_specs = build_default_action_registry(None).specs()
        action_count = len(action_specs)
        action_ids = [str(row.get("id") or "") for row in action_specs]
    except Exception:
        action_count = 0
        action_ids = []
    if long_project_stress_report is None:
        stress_path = ROOT / "debugCapture" / "long_project_stress_qa.json"
        try:
            payload = json.loads(stress_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                long_project_stress_report = payload
        except Exception:
            long_project_stress_report = {}
    if real_project_corpus_report is None:
        real_corpus_path = ROOT / "debugCapture" / "nle_real_project_corpus_qa.json"
        try:
            payload = json.loads(real_corpus_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                real_project_corpus_report = payload
        except Exception:
            real_project_corpus_report = {}
    if timeline_fuzzer_report is None:
        fuzzer_path = ROOT / "debugCapture" / "timeline_fuzzer_qa.json"
        try:
            payload = json.loads(fuzzer_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                timeline_fuzzer_report = payload
        except Exception:
            timeline_fuzzer_report = {}
    if snapshot is None and synthetic_contract_corpus:
        from app.nle_evidence import build_synthetic_nle_validation_snapshot

        snapshot = build_synthetic_nle_validation_snapshot(action_ids=action_ids)
    stress_attached = False
    if snapshot is not None and isinstance(long_project_stress_report, dict) and long_project_stress_report:
        snapshot = dict(snapshot)
        snapshot["long_project_stress"] = long_project_stress_report
        stress_attached = True
    real_corpus_attached = False
    if snapshot is not None and isinstance(real_project_corpus_report, dict) and real_project_corpus_report:
        snapshot = dict(snapshot)
        snapshot["nle_real_project_corpus"] = real_project_corpus_report
        real_corpus_attached = True
    fuzzer_attached = False
    if snapshot is not None and isinstance(timeline_fuzzer_report, dict) and timeline_fuzzer_report:
        from app.nle_timeline_stress import build_nle_timeline_stress_report

        snapshot = dict(snapshot)
        snapshot["nle_timeline_stress"] = build_nle_timeline_stress_report(timeline_fuzzer_report)
        fuzzer_attached = True
    if snapshot is not None and ("nle_evidence" not in snapshot or stress_attached or real_corpus_attached or fuzzer_attached):
        from app.nle_evidence import build_nle_evidence_report

        snapshot = dict(snapshot)
        previous_evidence = snapshot.get("nle_evidence") if isinstance(snapshot.get("nle_evidence"), dict) else {}
        evidence_level = str(previous_evidence.get("evidence_level") or "project_snapshot")
        if isinstance(real_project_corpus_report, dict) and _real_corpus_claim_ready(real_project_corpus_report):
            evidence_level = "real_project_corpus"
        snapshot["nle_evidence"] = build_nle_evidence_report(
            snapshot,
            action_ids=action_ids,
            evidence_level=evidence_level,
        )
    report = build_nle_readiness_report(snapshot or {}, action_count=action_count)
    return {
        "kind": "nle_readiness",
        "ok": bool(report.get("schema") == "tigerstudio.nle_readiness.v1" and report.get("rows")),
        "release_claim_gate_ok": bool(report.get("professional_nle_claim_ok")),
        "summary": format_nle_readiness_summary(report),
        "report": report,
        "synthetic_contract_corpus": bool(synthetic_contract_corpus and snapshot is not None),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/nle_readiness_qa.json"))
    parser.add_argument(
        "--no-synthetic-corpus",
        action="store_true",
        help="Use an empty/default snapshot instead of the synthetic NLE contract corpus.",
    )
    parser.add_argument(
        "--long-project-stress",
        type=Path,
        default=Path("debugCapture/long_project_stress_qa.json"),
        help="Optional long-project stress report to attach as NLE validation evidence.",
    )
    parser.add_argument(
        "--real-project-corpus",
        type=Path,
        default=Path("debugCapture/nle_real_project_corpus_qa.json"),
        help="Optional real-project corpus QA report to attach as NLE release evidence.",
    )
    parser.add_argument(
        "--timeline-fuzzer",
        type=Path,
        default=Path("debugCapture/timeline_fuzzer_qa.json"),
        help="Optional timeline fuzzer QA report to attach as undo/edge-case evidence.",
    )
    args = parser.parse_args(argv)
    stress_payload: dict[str, Any] | None = None
    stress_path = args.long_project_stress
    if not stress_path.is_absolute():
        stress_path = ROOT / stress_path
    try:
        loaded = json.loads(stress_path.read_text(encoding="utf-8"))
        stress_payload = loaded if isinstance(loaded, dict) else {}
    except Exception:
        stress_payload = {}
    real_corpus_payload: dict[str, Any] | None = None
    real_corpus_path = args.real_project_corpus
    if not real_corpus_path.is_absolute():
        real_corpus_path = ROOT / real_corpus_path
    try:
        loaded = json.loads(real_corpus_path.read_text(encoding="utf-8"))
        real_corpus_payload = loaded if isinstance(loaded, dict) else {}
    except Exception:
        real_corpus_payload = {}
    fuzzer_payload: dict[str, Any] | None = None
    fuzzer_path = args.timeline_fuzzer
    if not fuzzer_path.is_absolute():
        fuzzer_path = ROOT / fuzzer_path
    try:
        loaded = json.loads(fuzzer_path.read_text(encoding="utf-8"))
        fuzzer_payload = loaded if isinstance(loaded, dict) else {}
    except Exception:
        fuzzer_payload = {}
    payload = run_nle_readiness_qa(
        synthetic_contract_corpus=not bool(args.no_synthetic_corpus),
        long_project_stress_report=stress_payload,
        real_project_corpus_report=real_corpus_payload,
        timeline_fuzzer_report=fuzzer_payload,
    )
    out = args.out
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(payload["summary"])
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
