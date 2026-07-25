"""Build a portable TigerCapture update zip and optional update manifest."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.update.manifest import build_manifest, manifest_to_json
from app.update.verifier import sha256_file


def _iter_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def build_portable_zip(
    *,
    dist_dir: Path,
    output: Path,
    root_name: str = "TigerCapture",
    require_updater: bool = True,
) -> Path:
    dist_dir = dist_dir.expanduser().resolve()
    if not dist_dir.is_dir():
        raise FileNotFoundError(f"dist dir not found: {dist_dir}")
    required = ["TigerCapture.exe", "TigerStudio.exe"]
    if require_updater:
        required.append("TigerCaptureUpdater.exe")
    for name in required:
        if not (dist_dir / name).is_file():
            raise FileNotFoundError(f"required packaged file missing: {dist_dir / name}")
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in _iter_files(dist_dir):
            arcname = Path(root_name) / path.relative_to(dist_dir)
            zf.write(path, arcname.as_posix())
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build portable TigerCapture update package.")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist" / "TigerCapture")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--root-name", default="TigerCapture")
    parser.add_argument("--no-require-updater", action="store_true")
    parser.add_argument("--manifest-output", type=Path, default=None)
    parser.add_argument("--artifact-url", default="")
    parser.add_argument("--channel", default="stable")
    parser.add_argument("--minimum-app-version", default="0.0.0")
    parser.add_argument("--release-notes-url", default="")
    args = parser.parse_args()

    output = args.output or ROOT / "installer_output" / f"TigerCapture-Portable-{args.version}.zip"
    package = build_portable_zip(
        dist_dir=args.dist_dir,
        output=output,
        root_name=args.root_name,
        require_updater=not bool(args.no_require_updater),
    )
    print(package)
    if args.manifest_output is not None:
        artifact_url = args.artifact_url or package.name
        manifest = build_manifest(
            version=args.version,
            channel=args.channel,
            platform="windows-x64",
            kind="portable_zip",
            artifact_url=artifact_url,
            sha256=sha256_file(package),
            size=package.stat().st_size,
            filename=package.name,
            published_at=dt.datetime.now(dt.UTC).isoformat(),
            minimum_app_version=args.minimum_app_version,
            release_notes_url=args.release_notes_url,
        )
        args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_output.write_text(manifest_to_json(manifest), encoding="utf-8")
        print(args.manifest_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
