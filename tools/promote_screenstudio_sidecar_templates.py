"""Promote filled Screen Studio cursor sidecar templates in bulk."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _iter_templates(template_dir: Path, pattern: str, recursive: bool) -> list[Path]:
    if not template_dir.exists():
        return []
    iterator = template_dir.rglob(pattern) if recursive else template_dir.glob(pattern)
    return sorted(path for path in iterator if path.is_file())


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Promote filled .cursor.template.json files into counted sidecars.")
    parser.add_argument("--template-dir", type=Path, default=Path("debugCapture/screenstudio_sidecar_templates"))
    parser.add_argument("--pattern", default="*.cursor.template.json")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--register", action="store_true", help="Register videos after writing sidecars.")
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/screenstudio_real_recordings/manifest.json"))
    parser.add_argument("--allow-not-ready", action="store_true", help="Keep written sidecars even if they do not pass QA.")
    args = parser.parse_args()

    from app.screenstudio_parity import screenstudio_register_real_recording
    from app.screenstudio_sidecar_capture import load_sidecar_template, write_cursor_sidecar_from_template

    rows: list[dict[str, Any]] = []
    for template_path in _iter_templates(args.template_dir, args.pattern, bool(args.recursive)):
        try:
            template = load_sidecar_template(template_path)
            events = template.get("events")
            if not isinstance(events, list) or not events:
                rows.append(
                    {
                        "template_path": str(template_path),
                        "state": "skipped_empty",
                        "written": False,
                        "registered": False,
                    }
                )
                continue
            sidecar_path, payload = write_cursor_sidecar_from_template(template_path)
            counts_for_qa = bool(payload.get("counts_for_qa"))
            if not counts_for_qa and not args.allow_not_ready:
                try:
                    sidecar_path.unlink()
                except Exception:
                    pass
                rows.append(
                    {
                        "template_path": str(template_path),
                        "state": "not_ready",
                        "written": False,
                        "registered": False,
                        "sidecar_path": str(sidecar_path),
                        "qa": payload.get("qa", {}),
                    }
                )
                continue
            registration = None
            if args.register:
                registration = screenstudio_register_real_recording(
                    Path(str(payload.get("video_path") or template.get("source_path") or "")),
                    manifest_path=args.manifest,
                    slot_id=str(template.get("slot_id") or ""),
                    require_sidecar=True,
                    metadata={"sidecar_capture_source": f"template_batch:{template_path}"},
                )
            rows.append(
                {
                    "template_path": str(template_path),
                    "state": "ready" if counts_for_qa else "written_not_ready",
                    "written": True,
                    "registered": bool(registration and registration.get("registered")),
                    "sidecar_ready": bool(registration and registration.get("sidecar_ready")),
                    "sidecar_path": str(sidecar_path),
                    "event_count": len(payload.get("events") or []),
                    "counts_for_qa": counts_for_qa,
                    "qa": payload.get("qa", {}),
                    "registration": registration,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "template_path": str(template_path),
                    "state": "failed",
                    "written": False,
                    "registered": False,
                    "error": str(exc),
                }
            )

    summary = {
        "templates": len(rows),
        "written": sum(1 for row in rows if row.get("written")),
        "registered": sum(1 for row in rows if row.get("registered")),
        "ready": sum(1 for row in rows if row.get("counts_for_qa")),
        "skipped_empty": sum(1 for row in rows if row.get("state") == "skipped_empty"),
        "not_ready": sum(1 for row in rows if row.get("state") == "not_ready"),
        "failed": sum(1 for row in rows if row.get("state") == "failed"),
    }
    result = {
        "ok": summary["failed"] == 0,
        "kind": "screenstudio_sidecar_template_promotion",
        "template_dir": str(args.template_dir),
        "summary": summary,
        "rows": rows,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
