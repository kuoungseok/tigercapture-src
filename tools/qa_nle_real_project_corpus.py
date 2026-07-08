"""Validate the real-project corpus used by conservative NLE readiness."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/nle_real_projects/manifest.json"))
    parser.add_argument("--out", type=Path, default=Path("debugCapture/nle_real_project_corpus_qa.json"))
    parser.add_argument("--min-projects", type=int, default=3)
    parser.add_argument("--min-duration-ms", type=int, default=30 * 60_000)
    parser.add_argument("--min-video-clips", type=int, default=90)
    parser.add_argument("--min-audio-clips", type=int, default=20)
    parser.add_argument(
        "--metric-only",
        action="store_true",
        help="Do not require per-project validation evidence. Use only for diagnostics, not release claims.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the real-project corpus is not claim-ready.",
    )
    args = parser.parse_args(argv)

    from app.nle_real_corpus import build_nle_real_project_corpus_report

    report = build_nle_real_project_corpus_report(
        manifest_path=args.manifest,
        min_projects=args.min_projects,
        min_duration_ms=args.min_duration_ms,
        min_total_video_clips=args.min_video_clips,
        min_total_audio_clips=args.min_audio_clips,
        require_validation_evidence=not bool(args.metric_only),
    )
    out = args.out
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "NLE real corpus: "
        f"{'ready' if report.get('claim_ready') else 'not ready'}; "
        f"valid_projects={(report.get('summary') or {}).get('valid_project_count', 0)}; "
        f"preflight_ready={(report.get('summary') or {}).get('preflight_ready_count', 0)}; "
        f"validation_ready={(report.get('summary') or {}).get('validation_ready_count', 0)}; "
        f"blockers={', '.join(report.get('blockers') or []) or 'none'}"
    )
    print(f"report: {out}")
    return 1 if args.strict and not report.get("claim_ready") else 0


if __name__ == "__main__":
    raise SystemExit(main())
