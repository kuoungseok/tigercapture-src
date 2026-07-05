"""Utilities for approving and auditing UI visual baselines."""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "debugCapture" / "visual_baseline" / "baseline.json"


def _latest_snapshot(root: Path | None = None) -> Path | None:
    search_root = root or (ROOT / "debugCapture")
    if not search_root.exists():
        return None
    snapshots = sorted(
        search_root.glob("**/current_snapshot.json"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    return snapshots[0] if snapshots else None


def approve_latest_visual_baseline(
    *,
    snapshot_path: str | Path | None = None,
    baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(snapshot_path) if snapshot_path is not None else _latest_snapshot()
    target = Path(baseline_path) if baseline_path is not None else BASELINE
    if source is None or not source.exists():
        return {"ok": False, "error": "No current visual snapshot found."}
    try:
        snapshot = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"Snapshot unreadable: {exc}"}
    if not isinstance(snapshot, dict) or not snapshot.get("screenshots"):
        return {"ok": False, "error": "Snapshot has no screenshot hashes."}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    archive = target.parent / "approved"
    archive.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for image_name in (snapshot.get("screenshots") or {}).keys():
        image_path = source.parent / image_name
        if image_path.exists():
            dst = archive / image_name
            shutil.copy2(image_path, dst)
            copied.append(str(dst))
    manifest = {
        "approved_at": datetime.now().isoformat(timespec="seconds"),
        "source_snapshot": str(source),
        "baseline": str(target),
        "copied_images": copied,
        "screenshot_count": len(snapshot.get("screenshots") or {}),
    }
    (archive / "baseline_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"ok": True, **manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve latest visual QA snapshot as baseline.")
    parser.add_argument("--snapshot", default="")
    parser.add_argument("--baseline", default=str(BASELINE))
    args = parser.parse_args()
    report = approve_latest_visual_baseline(
        snapshot_path=args.snapshot or None,
        baseline_path=args.baseline,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
