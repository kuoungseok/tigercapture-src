from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest_visual_report() -> Path | None:
    root = ROOT / "debugCapture"
    if not root.exists():
        return None
    rows = sorted(
        list(root.glob("**/visual_regression_report.json")) + list(root.glob("**/layout_report.json")),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    return rows[0] if rows else None


def run_ui_visual_baseline_refresh(
    *,
    baseline_audit_path: Path = ROOT / "debugCapture" / "visual_baseline_audit.json",
) -> dict[str, Any]:
    latest = _latest_visual_report()
    baseline = _load_json(baseline_audit_path)
    latest_payload = _load_json(latest) if latest is not None else {}
    failures = []
    if latest is None:
        failures.append("missing_latest_visual_report")
    if not baseline.get("ok"):
        failures.append("baseline_audit_not_ok")
    if latest_payload and latest_payload.get("ok") is False:
        failures.append("latest_visual_report_not_ok")
    approved_dir = ROOT / "debugCapture" / "visual_baseline" / "approved"
    approved_count = len(list(approved_dir.glob("*.png"))) if approved_dir.exists() else 0
    return {
        "ok": not failures,
        "summary": {
            "latest_visual_report": str(latest or ""),
            "baseline_audit": str(baseline_audit_path),
            "approved_screenshots": approved_count,
            "failures": len(failures),
        },
        "failures": failures,
        "baseline_audit": baseline,
        "latest_visual_summary": latest_payload.get("summary", latest_payload if latest_payload else {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize current UI visual/baseline readiness.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/ui_visual_baseline_refresh.json"))
    args = parser.parse_args()
    report = run_ui_visual_baseline_refresh()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {args.out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
