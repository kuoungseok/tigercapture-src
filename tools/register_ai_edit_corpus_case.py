"""Register a real AI Script Edit corpus case."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").replace(";", ",").split(",") if part.strip()]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Register one real AI edit corpus case.")
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/ai_editing_corpus/manifest.json"))
    parser.add_argument("--from-template", type=Path, default=None, help="Register from a filled ai_edit_real_case_template JSON file.")
    parser.add_argument("--transcript", type=Path, help="Real SRT/VTT/plain transcript path.")
    parser.add_argument("--prompt", help="Natural-language edit request.")
    parser.add_argument("--language", help="Language code, e.g. ko or en.")
    parser.add_argument("--scenario", help="Scenario, e.g. tutorial, shortform, product, long_tutorial.")
    parser.add_argument("--expected-intent", help="Expected EditPlan intent.")
    parser.add_argument(
        "--required-operations",
        help="Comma-separated operation types expected from the plan.",
    )
    parser.add_argument("--case-id", default="")
    parser.add_argument("--label", default="")
    parser.add_argument("--source-media", type=Path, default=None)
    parser.add_argument("--source-format", default="srt")
    parser.add_argument("--min-segments", type=int, default=3)
    parser.add_argument("--min-duration-ms", type=int, default=0)
    parser.add_argument("--no-copy-transcript", action="store_true", help="Reference transcript in place instead of copying into corpus/transcripts.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    from app.ai_edit_corpus_registration import register_ai_edit_corpus_case, register_ai_edit_corpus_case_from_template

    if args.from_template:
        report = register_ai_edit_corpus_case_from_template(
            args.from_template,
            manifest_path=args.manifest,
            copy_transcript=not bool(args.no_copy_transcript),
            overwrite=bool(args.overwrite),
        )
    else:
        missing = [
            name
            for name, value in {
                "--transcript": args.transcript,
                "--prompt": args.prompt,
                "--language": args.language,
                "--scenario": args.scenario,
                "--expected-intent": args.expected_intent,
                "--required-operations": args.required_operations,
            }.items()
            if not value
        ]
        if missing:
            parser.error("missing required arguments: " + ", ".join(missing))
        report = register_ai_edit_corpus_case(
            manifest_path=args.manifest,
            transcript_path=args.transcript,
            prompt=args.prompt or "",
            language=args.language or "",
            scenario=args.scenario or "",
            expected_intent=args.expected_intent or "",
            required_operations=_split_csv(args.required_operations or ""),
            case_id=args.case_id,
            label=args.label,
            source_media_path=args.source_media,
            source_format=args.source_format,
            min_segments=max(1, int(args.min_segments or 1)),
            min_duration_ms=max(0, int(args.min_duration_ms or 0)),
            copy_transcript=not bool(args.no_copy_transcript),
            overwrite=bool(args.overwrite),
            notes=args.notes,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("ok") and report.get("registered") else 1


if __name__ == "__main__":
    raise SystemExit(main())
