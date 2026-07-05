from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Screen Studio real-recording QA corpus.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/screenstudio_real_recording_corpus_qa.json"))
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/screenstudio_auto_polish/manifest.json"))
    parser.add_argument("--real-manifest", type=Path, default=Path("qa_corpus/screenstudio_real_recordings/manifest.json"))
    parser.add_argument("--root", action="append", type=Path, default=[])
    parser.add_argument("--no-probe", action="store_true")
    args = parser.parse_args()

    from app.screenstudio_parity import screenstudio_real_recording_corpus_report

    report = screenstudio_real_recording_corpus_report(
        args.manifest,
        real_roots=args.root or None,
        real_manifest_path=args.real_manifest,
        deep_probe=not args.no_probe,
    )
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": report.get("ok"), "real_world_ready": report.get("real_world_ready"), "out": str(out)}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
