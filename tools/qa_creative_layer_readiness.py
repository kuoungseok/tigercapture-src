"""Write a conservative creative-layer readiness QA report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.creative_layer_readiness import (
    build_creative_layer_readiness_report,
    format_creative_layer_readiness_summary,
)


def run_creative_layer_readiness_qa(*, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the QA payload used by CLI tests and dashboard collection."""
    try:
        from app.actions import build_default_action_registry

        action_ids = [row.get("id", "") for row in build_default_action_registry(None).specs()]
    except Exception:
        action_ids = []
    try:
        from app.preset_library import preset_library_summary

        presets = preset_library_summary()
    except Exception:
        presets = {}
    ar_pbr_full_gpu_report: dict[str, Any] = {}
    ar_pbr_report_path = ROOT / "debugCapture" / "ar_pbr_full_gpu_export_service_qa.json"
    try:
        if ar_pbr_report_path.is_file():
            data = json.loads(ar_pbr_report_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                ar_pbr_full_gpu_report = data
    except Exception:
        ar_pbr_full_gpu_report = {}
    report = build_creative_layer_readiness_report(
        snapshot or {},
        action_ids=action_ids,
        preset_summary=presets,
        ar_pbr_full_gpu_report=ar_pbr_full_gpu_report,
    )
    return {
        "kind": "creative_layer_readiness",
        "ok": bool(report.get("schema") == "tigerstudio.creative_layer_readiness.v1" and report.get("rows")),
        "release_claim_gate_ok": bool(report.get("full_creative_suite_claim_ok")),
        "summary": format_creative_layer_readiness_summary(report),
        "report": report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/creative_layer_readiness_qa.json"))
    args = parser.parse_args(argv)
    payload = run_creative_layer_readiness_qa()
    out = args.out
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(payload["summary"])
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
