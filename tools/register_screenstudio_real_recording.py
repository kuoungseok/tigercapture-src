from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Register real Screen Studio-style recordings for TigerCapture QA.")
    parser.add_argument("--source", type=Path, help="Path to a real screen recording.")
    parser.add_argument("--scan-root", action="append", type=Path, default=[], help="Folder to scan for real recordings.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum new recordings to register when scanning folders.")
    parser.add_argument("--slot-id", default="", help="Recording slot id, for example screenstudio-real-01.")
    parser.add_argument("--manifest", default="qa_corpus/screenstudio_real_recordings/manifest.json", type=Path)
    parser.add_argument("--label", default="", help="Optional human-readable label.")
    parser.add_argument("--notes", default="", help="Optional QA note.")
    parser.add_argument(
        "--require-sidecar",
        action="store_true",
        help="Only register recordings that already have a matching .cursor.json sidecar.",
    )
    parser.add_argument(
        "--repair-slots",
        action="store_true",
        help="Repair duplicate or blank slot ids in the manifest without registering new recordings.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview --repair-slots changes without writing.")
    args = parser.parse_args()

    if not args.source and not args.scan_root and not args.repair_slots:
        parser.error("provide --source or at least one --scan-root")

    from app.screenstudio_parity import (
        screenstudio_register_real_recording,
        screenstudio_register_real_recordings_from_roots,
        screenstudio_repair_real_recording_manifest_slots,
    )

    if args.repair_slots:
        report = screenstudio_repair_real_recording_manifest_slots(
            args.manifest,
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0 if report.get("ok") else 1

    metadata = {
        key: value
        for key, value in {
            "label": args.label,
            "notes": args.notes,
        }.items()
        if value
    }

    if args.scan_root:
        report = screenstudio_register_real_recordings_from_roots(
            args.scan_root,
            manifest_path=args.manifest,
            limit=args.limit,
            metadata=metadata,
            require_sidecar=args.require_sidecar,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0 if report.get("ok") else 1

    report = screenstudio_register_real_recording(
        args.source,
        manifest_path=args.manifest,
        slot_id=args.slot_id,
        metadata=metadata,
        require_sidecar=args.require_sidecar,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
