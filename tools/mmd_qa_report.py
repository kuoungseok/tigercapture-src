"""Print text-first QA diagnostics for MMD models and optional VMD motion."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.mmd.diagnostics import analyze_mmd_model, format_mmd_report
from app.mmd.regression_profiles import (
    evaluate_mmd_regression_profile,
    mmd_regression_profile_ids,
    mmd_regression_profile_model_path,
    mmd_regression_profile_motion_path,
)


def _format_profile_results(reports: list[dict]) -> str:
    lines: list[str] = []
    for report in reports:
        profile = report.get("regression_profile") if isinstance(report, dict) else None
        if not isinstance(profile, dict):
            continue
        failures = list(profile.get("failures") or [])
        lines.append(
            f"profile      : {profile.get('profile_id')} ok={bool(profile.get('ok'))} "
            f"checks={int(profile.get('check_count', 0) or 0)} failures={len(failures)}"
        )
        for failure in failures[:8]:
            lines.append(
                "  - "
                f"{failure.get('material')} {failure.get('field')}: "
                f"{failure.get('actual')!r} expected {failure.get('expected')!r}"
            )
    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Run MMD model/material/animation diagnostics")
    parser.add_argument("models", nargs="*", help="PMX/PMD/PBX JSON model paths")
    parser.add_argument("--motion", default="", help="Optional VMD motion path")
    parser.add_argument("--profile", choices=mmd_regression_profile_ids(), default="", help="Apply a known model regression profile")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text table")
    args = parser.parse_args()

    motion = Path(args.motion) if args.motion else None
    if args.profile and motion is None:
        motion = mmd_regression_profile_motion_path(args.profile)
    model_args = list(args.models)
    if args.profile and not model_args:
        model_args = [str(mmd_regression_profile_model_path(args.profile))]
    reports = []
    for raw in model_args:
        report = analyze_mmd_model(Path(raw), motion)
        if args.profile:
            report["regression_profile"] = evaluate_mmd_regression_profile(report, args.profile)
        reports.append(report)

    ok = all(bool(report.get("ok")) for report in reports)
    ok = ok and all(bool((report.get("regression_profile") or {"ok": True}).get("ok")) for report in reports)
    if args.json:
        print(json.dumps({"ok": ok, "reports": reports}, ensure_ascii=False, indent=2))
    else:
        print(format_mmd_report(reports))
        profile_text = _format_profile_results(reports)
        if profile_text:
            print("")
            print(profile_text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
