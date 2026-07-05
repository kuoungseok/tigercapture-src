"""Build preview scrub/seek readiness report from qa_preview_perf output."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _run_hires_preview_perf(
    *,
    manifest: str | Path,
    out: str | Path,
    clean: bool,
    render_samples: int,
) -> dict:
    from tools.qa_preview_perf import run_perf

    return run_perf(
        _resolve_path(manifest),
        _resolve_path(out),
        clean=bool(clean),
        render_samples=int(render_samples),
        skip_render=False,
        include_hires=True,
        include_hires_proxy=True,
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build preview scrub readiness report.")
    parser.add_argument("--perf-report", default="debugCapture/preview_perf_report.json")
    parser.add_argument("--out", default="debugCapture/preview_scrub_readiness_qa.json")
    parser.add_argument("--scrub-p95-ms", type=float, default=None)
    parser.add_argument("--scrub-avg-ms", type=float, default=None)
    parser.add_argument(
        "--auto-hires",
        action="store_true",
        help="If 4K coverage is missing, run qa_preview_perf with generated 1080p/4K fixtures first.",
    )
    parser.add_argument("--manifest", default="qa_corpus/qa_corpus_manifest.json")
    parser.add_argument("--hires-perf-report", default="debugCapture/preview_perf_report_hires.json")
    parser.add_argument("--render-samples", type=int, default=8)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    from app.preview_scrub_readiness import build_preview_scrub_readiness_report

    thresholds = {}
    if args.scrub_p95_ms is not None:
        thresholds["scrub_p95_ms"] = float(args.scrub_p95_ms)
    if args.scrub_avg_ms is not None:
        thresholds["scrub_avg_ms"] = float(args.scrub_avg_ms)

    source_perf_report = _resolve_path(args.perf_report)
    report = build_preview_scrub_readiness_report(source_perf_report, thresholds=thresholds)
    auto_hires = {
        "requested": bool(args.auto_hires),
        "ran": False,
        "reason": "",
        "perf_report": "",
    }
    missing = set((report.get("summary") or {}).get("missing_release_coverage") or [])
    if args.auto_hires and "hires_4k" in missing:
        hires_path = _resolve_path(args.hires_perf_report)
        _run_hires_preview_perf(
            manifest=args.manifest,
            out=hires_path,
            clean=bool(args.clean),
            render_samples=int(args.render_samples),
        )
        report = build_preview_scrub_readiness_report(hires_path, thresholds=thresholds)
        auto_hires.update(
            {
                "ran": True,
                "reason": "hires_4k coverage was missing",
                "perf_report": str(hires_path),
            }
        )
    elif args.auto_hires:
        auto_hires["reason"] = "hires_4k coverage already present"
        auto_hires["perf_report"] = str(source_perf_report)
    report["auto_hires"] = auto_hires

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
