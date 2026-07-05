"""Inspect and maintain actor golden-image baselines."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def actor_golden_status(golden_dir: Path | str) -> dict[str, Any]:
    root = Path(golden_dir)
    actual_dir = root / "_actual"
    baselines = sorted(path for path in root.glob("*.png") if path.is_file())
    actuals = sorted(path for path in actual_dir.glob("*.png") if path.is_file()) if actual_dir.exists() else []
    baseline_names = {path.name for path in baselines}
    actual_names = {path.name for path in actuals}
    matching = sorted(baseline_names & actual_names)
    missing = sorted(actual_names - baseline_names)
    stale = sorted(baseline_names - actual_names)
    return {
        "golden_dir": str(root),
        "baseline_count": len(baselines),
        "actual_count": len(actuals),
        "matching_count": len(matching),
        "pending_promotion_count": len(missing),
        "stale_count": len(stale),
        "missing_baselines": missing,
        "stale_baselines": stale,
        "matching_baselines": matching[:50],
        "ready_for_compare": len(baselines) > 0,
        "needs_promotion": bool(missing),
    }


def promote_actuals(golden_dir: Path | str, *, names: list[str] | None = None) -> dict[str, Any]:
    root = Path(golden_dir)
    actual_dir = root / "_actual"
    if not actual_dir.exists():
        return {"promoted": 0, "files": [], "error": "actual directory does not exist"}
    allowed = {name for name in names or [] if name}
    promoted: list[str] = []
    for actual in sorted(actual_dir.glob("*.png")):
        if allowed and actual.name not in allowed:
            continue
        dest = root / actual.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(actual, dest)
        promoted.append(actual.name)
    skipped = sorted(allowed - set(promoted)) if allowed else []
    result: dict[str, Any] = {"promoted": len(promoted), "files": promoted}
    if skipped:
        result["skipped_missing_actuals"] = skipped
    return result


def load_manifest_golden_dir(manifest: Path | None) -> Path:
    if manifest is None or not manifest.exists():
        return ROOT / "qa_corpus" / "actor_golden"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return ROOT / "qa_corpus" / "actor_golden"
    golden = str(data.get("golden_dir") or "qa_corpus/actor_golden")
    path = Path(golden)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Inspect/promote actor golden baselines.")
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/actor_corpus_manifest.json"))
    parser.add_argument("--golden-dir", type=Path, default=None)
    parser.add_argument("--promote-actual", action="store_true")
    parser.add_argument("--name", action="append", default=[], help="Promote only this PNG name. Repeatable.")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    golden_dir = args.golden_dir or load_manifest_golden_dir(args.manifest)
    result: dict[str, Any] = {"status": actor_golden_status(golden_dir)}
    if args.promote_actual:
        result["promotion"] = promote_actuals(golden_dir, names=args.name)
        result["status"] = actor_golden_status(golden_dir)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
