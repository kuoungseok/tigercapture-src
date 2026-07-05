"""Build a CapCut parity-next QA report."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _media_items(media_doc: dict[str, Any]) -> list[dict[str, Any]] | None:
    for key in ("media_items", "media", "assets"):
        value = media_doc.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build CapCut parity-next QA report.")
    parser.add_argument("--project", default="", help="Optional .tgp/JSON project document.")
    parser.add_argument("--media", default="", help="Optional media metadata JSON list/document.")
    parser.add_argument("--out", default="debugCapture/capcut_parity_next_qa.json")
    parser.add_argument("--exclude-cloud", action="store_true", help="Exclude cloud/mobile-sync parity and score local mobile templates instead.")
    args = parser.parse_args()

    project_doc = _load_json(Path(args.project)) if args.project else None
    media_doc = _load_json(Path(args.media)) if args.media else {}

    from app.capcut_parity import build_capcut_parity_next_report

    report = build_capcut_parity_next_report(project_doc, _media_items(media_doc), exclude_cloud=args.exclude_cloud)
    out_path = ROOT / args.out
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
