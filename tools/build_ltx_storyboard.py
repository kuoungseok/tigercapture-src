"""Generate a local LTX-style storyboard report from a prompt."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_json(path: str) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _media_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("media_items", "media", "assets"):
        value = payload.get(key)
        if isinstance(value, list):
            return [dict(row) for row in value if isinstance(row, dict)]
    return []


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build a local LTX-style shot-card storyboard.")
    parser.add_argument("prompt", nargs="?", default="Create a polished creator edit with shot cards.")
    parser.add_argument("--project", default="", help="Optional project summary JSON.")
    parser.add_argument("--media", default="", help="Optional media metadata JSON.")
    parser.add_argument("--aspect-ratio", default="9:16")
    parser.add_argument("--duration-ms", type=int, default=0)
    parser.add_argument("--out", default="debugCapture/ltx_storyboard_report.json")
    args = parser.parse_args(argv)

    project = _load_json(args.project)
    media_payload = _load_json(args.media)
    media = _media_items(media_payload) or _media_items(project)

    from app.ltx_storyboard import ltx_storyboard_report

    report = ltx_storyboard_report(
        args.prompt,
        project,
        media,
        aspect_ratio=args.aspect_ratio,
        target_duration_ms=args.duration_ms or None,
    )
    out_path = ROOT / args.out
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
