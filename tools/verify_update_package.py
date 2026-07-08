"""Verify a TigerCapture update manifest and local artifact before publishing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.update.manifest import DEFAULT_KIND, DEFAULT_PLATFORM, choose_artifact, evaluate_manifest, manifest_from_json
from app.update.verifier import verify_artifact_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify update manifest/artifact integrity.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--current-version", default="0.0.0")
    parser.add_argument("--channel", default="stable")
    parser.add_argument("--platform", default=DEFAULT_PLATFORM)
    parser.add_argument("--kind", default=DEFAULT_KIND)
    args = parser.parse_args()

    manifest = manifest_from_json(args.manifest.read_text(encoding="utf-8"))
    artifact = choose_artifact(manifest, platform=args.platform, kind=args.kind)
    if artifact is None:
        raise SystemExit("no matching artifact in manifest")
    integrity = verify_artifact_file(args.artifact, artifact)
    check = evaluate_manifest(
        manifest,
        current_version=args.current_version,
        channel=args.channel,
        platform=args.platform,
        kind=args.kind,
    )
    report = {"ok": bool(integrity["ok"] and not check.blocked), "integrity": integrity, "check": check.to_dict()}
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
