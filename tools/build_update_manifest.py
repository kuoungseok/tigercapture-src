"""Build a TigerCapture update manifest for a signed release artifact."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.update.manifest import DEFAULT_KIND, DEFAULT_PLATFORM, build_manifest, manifest_to_json
from app.update.verifier import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Build TigerCapture update manifest JSON.")
    parser.add_argument("--artifact", required=True, type=Path, help="Installer or portable update package.")
    parser.add_argument("--version", required=True, help="Target app version, e.g. 1.4.3.")
    parser.add_argument("--channel", default="stable", help="Release channel.")
    parser.add_argument("--platform", default=DEFAULT_PLATFORM)
    parser.add_argument("--kind", default=DEFAULT_KIND, help="installer, portable_zip, or future package kind.")
    parser.add_argument("--artifact-url", default="", help="Public HTTPS URL. Defaults to the artifact filename.")
    parser.add_argument("--minimum-app-version", default="0.0.0")
    parser.add_argument("--release-notes-url", default="")
    parser.add_argument("--published-at", default="")
    parser.add_argument("--signature", default="")
    parser.add_argument("--signature-url", default="")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    artifact = args.artifact.expanduser().resolve()
    if not artifact.is_file():
        raise SystemExit(f"artifact not found: {artifact}")
    published_at = args.published_at or dt.datetime.now(dt.UTC).isoformat()
    artifact_url = args.artifact_url or artifact.name
    manifest = build_manifest(
        version=args.version,
        channel=args.channel,
        platform=args.platform,
        kind=args.kind,
        artifact_url=artifact_url,
        sha256=sha256_file(artifact),
        size=artifact.stat().st_size,
        filename=artifact.name,
        published_at=published_at,
        minimum_app_version=args.minimum_app_version,
        release_notes_url=args.release_notes_url,
        signature=args.signature,
        signature_url=args.signature_url,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(manifest_to_json(manifest), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
