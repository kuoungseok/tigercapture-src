"""Register redacted manual broadcast platform evidence."""
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
    parser = argparse.ArgumentParser(description="Register redacted broadcast platform evidence.")
    parser.add_argument(
        "--check-id",
        required=True,
        choices=["private_rtmp_ingest", "youtube_unlisted_viewer_playback", "discord_window_share"],
    )
    parser.add_argument("--platform", required=True)
    parser.add_argument("--evidence-path", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--artifact", default="debugCapture/broadcast_platform_e2e_qa.json")
    parser.add_argument("--confirm-redacted", action="store_true", help="Confirm screenshots/logs do not contain stream keys or tokens.")
    args = parser.parse_args()

    from app.broadcast_evidence_ui import (
        broadcast_evidence_registration_warning,
        build_broadcast_evidence_registration_payload,
    )
    from app.broadcast_platform_e2e import register_manual_platform_evidence

    payload = build_broadcast_evidence_registration_payload(
        check_id=args.check_id,
        platform=args.platform,
        evidence_path=args.evidence_path,
        notes=args.notes,
        confirm_redacted=bool(args.confirm_redacted),
    )
    warning = broadcast_evidence_registration_warning(payload)
    if warning:
        print(f"Evidence registration blocked: {warning}", file=sys.stderr)
        return 2

    result = register_manual_platform_evidence(
        ROOT,
        **payload,
        artifact_path=args.artifact,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(f"report: {result['artifact']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
