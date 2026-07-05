"""Visual regression wrapper for the main editor chrome.

This runs the existing layout screenshot QA, then compares screenshot hashes
against a stored baseline. Use --update-baseline after an intentional UI pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "debugCapture" / "visual_baseline" / "baseline.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _image_diff(current: Path, baseline: Path) -> dict:
    try:
        import cv2
        import numpy as np

        cur = cv2.imread(str(current), cv2.IMREAD_UNCHANGED)
        old = cv2.imread(str(baseline), cv2.IMREAD_UNCHANGED)
        if cur is None or old is None:
            return {"ok": False, "error": "image unreadable"}
        if cur.shape != old.shape:
            return {"ok": False, "shape_changed": True, "current_shape": list(cur.shape), "baseline_shape": list(old.shape)}
        diff = np.abs(cur.astype(np.int16) - old.astype(np.int16))
        per_pixel = diff.max(axis=2) if diff.ndim == 3 else diff
        changed = per_pixel > 2
        changed_ratio = float(changed.mean()) if changed.size else 0.0
        mean_abs = float(diff.mean()) if diff.size else 0.0
        max_abs = int(diff.max()) if diff.size else 0
        return {
            "ok": True,
            "changed_ratio": changed_ratio,
            "mean_abs": mean_abs,
            "max_abs": max_abs,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _run_layout_qa(out_dir: Path) -> list[dict]:
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = Path(sys.executable)
    cmd = [str(py), str(ROOT / "tools" / "qa_ui_layout.py"), "--out", str(out_dir)]
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True, capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)
    report = out_dir / "layout_report.json"
    return json.loads(report.read_text(encoding="utf-8"))


def _snapshot(results: list[dict]) -> dict:
    shots = {}
    metrics = []
    for item in results:
        path = ROOT / str(item["screenshot"])
        if not path.exists():
            path = Path(str(item["screenshot"]))
        shots[path.name] = _sha256(path)
        metrics.append({
            "size": item.get("size"),
            "media_width": item.get("media_width"),
            "center_width": item.get("center_width"),
            "right_width": item.get("right_width"),
            "workbench_height": item.get("workbench_height"),
            "timeline_height": item.get("timeline_height"),
            "ok": bool(item.get("ok")),
        })
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "screenshot_count": len(shots),
        "screenshots": shots,
        "metrics": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="debugCapture/visual_regression", help="Output directory.")
    parser.add_argument("--baseline", default=str(BASELINE), help="Baseline JSON path.")
    parser.add_argument("--update-baseline", action="store_true", help="Write current snapshot as baseline.")
    args = parser.parse_args()

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    results = _run_layout_qa(out_dir)
    current = _snapshot(results)
    (out_dir / "current_snapshot.json").write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    baseline_path = Path(args.baseline)

    if args.update_baseline or not baseline_path.exists():
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"updated_baseline": str(baseline_path), **current}, ensure_ascii=False, indent=2))
        return 0

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    changed = {}
    tolerated = {}
    for name, old in (baseline.get("screenshots") or {}).items():
        cur_hash = current["screenshots"].get(name)
        if cur_hash == old:
            continue
        current_image = out_dir / name
        baseline_image = baseline_path.parent / "approved" / name
        diff = _image_diff(current_image, baseline_image) if baseline_image.exists() else {"ok": False, "error": "approved baseline image missing"}
        changed_ratio = float(diff.get("changed_ratio", 1.0)) if diff.get("changed_ratio") is not None else 1.0
        mean_abs = float(diff.get("mean_abs", 255.0)) if diff.get("mean_abs") is not None else 255.0
        diff_ok = bool(diff.get("ok")) and changed_ratio <= 0.005 and mean_abs <= 1.5
        row = {"baseline": old, "current": cur_hash, "diff": diff}
        if diff_ok:
            tolerated[name] = row
        else:
            changed[name] = row
    missing = [
        name for name in (baseline.get("screenshots") or {})
        if name not in current["screenshots"]
    ]
    metrics_ok = all(bool(item.get("ok")) for item in current.get("metrics", []))
    report = {
        "ok": metrics_ok and not changed and not missing,
        "changed_screenshots": changed,
        "tolerated_screenshot_diffs": tolerated,
        "missing_screenshots": missing,
        "metrics": current["metrics"],
        "current_snapshot": str(out_dir / "current_snapshot.json"),
        "baseline": str(baseline_path),
    }
    (out_dir / "visual_regression_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
