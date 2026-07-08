"""Discover Tiger Studio projects that can feed the real NLE corpus gate."""
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
    parser.add_argument(
        "roots",
        nargs="*",
        type=Path,
        help="Optional folders or project files to scan. Defaults to common Tiger Studio project folders.",
    )
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/nle_real_projects/manifest.json"))
    parser.add_argument("--out", type=Path, default=Path("debugCapture/nle_real_project_discovery.json"))
    parser.add_argument("--max-results", type=int, default=40)
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument(
        "--allow-generated",
        action="store_true",
        help="Include generated fixtures as registerable candidates. Do not use this for release claims.",
    )
    args = parser.parse_args(argv)

    from app.nle_real_corpus import discover_nle_real_project_candidates

    report = discover_nle_real_project_candidates(
        args.roots or None,
        manifest_path=args.manifest,
        max_results=max(1, int(args.max_results)),
        max_depth=max(0, int(args.max_depth)),
        allow_generated=bool(args.allow_generated),
    )
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"NLE real-project discovery wrote {out_path}")
    print(
        "scanned={scanned} candidates={candidates} registerable={registerable} needed={needed}".format(
            scanned=report.get("scanned_files", 0),
            candidates=report.get("candidate_count", 0),
            registerable=report.get("registerable_count", 0),
            needed=report.get("needed_for_claim", {}),
        )
    )
    for row in list(report.get("candidates") or [])[:10]:
        warnings = ",".join(row.get("warnings") or []) or "ok"
        print(
            "- {label}: register={register} warnings={warnings} path={path}".format(
                label=row.get("label") or "Project",
                register=bool(row.get("would_register")),
                warnings=warnings,
                path=row.get("path") or "",
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
