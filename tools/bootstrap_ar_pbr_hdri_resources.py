"""Download the local HDRI preset bundle used by AR/PBR preview lighting.

The HDRI files live under resources/ar_pbr/ so they are editor-wide lighting
assets, not per-scene files and not disposable debug evidence.  The script also
writes the manifest that app.ar_pbr.hdri_presets reads at runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = ROOT / "resources" / "ar_pbr"
HDRI_DIR = RESOURCE_ROOT / "hdri"
MANIFEST = RESOURCE_ROOT / "manifest.json"
DOWNLOAD_BASE = "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k"


PRESETS = [
    ("wide_street_01", "Wide Street", "default outdoor street IBL"),
    ("studio_small_09", "Studio Small 09", "neutral product studio IBL"),
    ("wooden_studio_17", "Wooden Studio 17", "warm studio IBL for product materials"),
    ("abandoned_parking", "Abandoned Parking", "urban interior/exterior IBL"),
    ("cayley_interior", "Cayley Interior", "soft indoor IBL"),
    ("autumn_forest_01", "Autumn Forest 01", "warm natural IBL"),
    ("belfast_sunset", "Belfast Sunset", "low sun exterior IBL"),
    ("cobblestone_street_night", "Cobblestone Street Night", "night street IBL"),
    ("brown_photostudio_03", "Brown Photostudio 03", "glossy studio IBL"),
]


def _download(url: str, target: Path, *, timeout: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    request = urllib.request.Request(url, headers={"User-Agent": "TigerCapture AR/PBR HDRI bootstrap"})
    try:
        with urllib.request.urlopen(request, timeout=max(1, int(timeout))) as response:
            temp.write_bytes(response.read())
    except urllib.error.URLError:
        if temp.exists():
            temp.unlink()
        raise
    temp.replace(target)


def _manifest_rows() -> list[dict[str, str]]:
    rows = []
    for preset_id, label, purpose in PRESETS:
        filename = f"{preset_id}_1k.hdr"
        rows.append({
            "id": preset_id,
            "label": label,
            "path": f"resources/ar_pbr/hdri/{filename}",
            "source_url": f"https://polyhaven.com/a/{preset_id}",
            "download_url": f"{DOWNLOAD_BASE}/{filename}",
            "license": "CC0",
            "purpose": purpose,
        })
    return rows


def write_manifest() -> Path:
    RESOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "tigerstudio.ar_pbr.resources.v1",
        "source": "Poly Haven",
        "license": "CC0",
        "hdri": _manifest_rows(),
    }
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return MANIFEST


def bootstrap(*, force: bool = False, timeout: int = 60, manifest_only: bool = False) -> dict[str, object]:
    HDRI_DIR.mkdir(parents=True, exist_ok=True)
    manifest = write_manifest()
    downloaded: list[str] = []
    skipped: list[str] = []
    errors: list[dict[str, str]] = []
    if not manifest_only:
        for row in _manifest_rows():
            preset_id = row["id"]
            target = ROOT / row["path"]
            if target.exists() and not force:
                skipped.append(preset_id)
                continue
            try:
                _download(row["download_url"], target, timeout=timeout)
                downloaded.append(preset_id)
            except Exception as exc:
                errors.append({"id": preset_id, "error": f"{type(exc).__name__}: {exc}"})
    return {
        "ok": not errors,
        "manifest": str(manifest),
        "hdri_dir": str(HDRI_DIR),
        "downloaded": downloaded,
        "skipped": skipped,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap local AR/PBR HDRI resources.")
    parser.add_argument("--force", action="store_true", help="Re-download existing HDRI files.")
    parser.add_argument("--manifest-only", action="store_true", help="Write the manifest without downloading HDRIs.")
    parser.add_argument("--timeout", type=int, default=60, help="Per-file download timeout in seconds.")
    args = parser.parse_args()
    result = bootstrap(force=bool(args.force), timeout=int(args.timeout), manifest_only=bool(args.manifest_only))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
