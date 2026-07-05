"""Record or build a Screen Studio-style cursor sidecar for a video."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_rect(value: str) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    parts = [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("screen rect must be x,y,w,h")
    try:
        x, y, w, h = [int(float(part)) for part in parts]
    except Exception as exc:
        raise argparse.ArgumentTypeError("screen rect must use numbers: x,y,w,h") from exc
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("screen rect width/height must be positive")
    return x, y, w, h


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Record or build a cursor sidecar next to a video.")
    parser.add_argument("--video", type=Path, help="Video path that will own the .cursor.json sidecar.")
    parser.add_argument("--out", type=Path, default=None, help="Optional output sidecar path. Defaults to <video>.cursor.json.")
    parser.add_argument("--from-events", type=Path, default=None, help="Build from a JSON events file instead of live capture.")
    parser.add_argument("--from-template", type=Path, default=None, help="Build from a filled .cursor.template.json file.")
    parser.add_argument("--duration-ms", type=int, default=10_000, help="Live capture duration or sidecar duration.")
    parser.add_argument("--screen-rect", type=_parse_rect, default=None, help="Live capture screen rect as x,y,w,h.")
    parser.add_argument("--sample-ms", type=int, default=33, help="Live cursor polling interval.")
    parser.add_argument(
        "--capture-hotkeys",
        action="store_true",
        help="Record modifier hotkeys such as Ctrl+K during live capture. Typed text is not captured.",
    )
    parser.add_argument("--frame-w", type=int, default=1920)
    parser.add_argument("--frame-h", type=int, default=1080)
    parser.add_argument("--register", action="store_true", help="Register the video in the real Screen Studio corpus after writing.")
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/screenstudio_real_recordings/manifest.json"))
    parser.add_argument("--slot-id", default="", help="Optional corpus slot id when --register is used.")
    parser.add_argument("--allow-empty-template", action="store_true", help="Write a non-ready sidecar even when a template has no events.")
    args = parser.parse_args()

    from app.screenstudio_sidecar_capture import (
        capture_windows_cursor_sidecar_events,
        load_event_file,
        load_sidecar_template,
        write_cursor_sidecar,
        write_cursor_sidecar_from_template,
    )

    if args.from_template and args.from_events:
        parser.error("--from-template and --from-events cannot be used together")
    if args.from_template:
        template = load_sidecar_template(args.from_template)
        events = template.get("events")
        if not isinstance(events, list):
            raise ValueError("sidecar template events must be an array")
        if not events and not args.allow_empty_template:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "reason": "template_events_empty",
                        "message": "Fill the template events array with real cursor/click/drag/hotkey data before creating a counted sidecar.",
                        "template_path": str(args.from_template),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
        sidecar_path, payload = write_cursor_sidecar_from_template(
            args.from_template,
            out_path=args.out,
            duration_ms=max(0, int(args.duration_ms or 0)),
            frame_w=max(1, int(args.frame_w or 1920)),
            frame_h=max(1, int(args.frame_h or 1080)),
        )
        video_path = Path(str(payload.get("video_path") or template.get("source_path") or args.video or ""))
        source = f"template:{args.from_template}"
    else:
        if not args.video:
            parser.error("--video is required unless --from-template is used")
        video_path = args.video
        if args.from_events:
            events = load_event_file(args.from_events)
            source = f"events_file:{args.from_events}"
        else:
            print(
                f"Recording cursor sidecar for {max(1, int(args.duration_ms or 0))} ms. "
                "Replay the target video and perform the cursor actions now...",
                flush=True,
            )
            events = capture_windows_cursor_sidecar_events(
                duration_ms=max(1, int(args.duration_ms or 0)),
                screen_rect=args.screen_rect,
                sample_ms=max(10, int(args.sample_ms or 33)),
                capture_hotkeys=bool(args.capture_hotkeys),
            )
            source = "windows_live_capture_hotkeys" if args.capture_hotkeys else "windows_live_capture"

        sidecar_path, payload = write_cursor_sidecar(
            video_path,
            events,
            out_path=args.out,
            duration_ms=max(0, int(args.duration_ms or 0)),
            frame_w=max(1, int(args.frame_w or 1920)),
            frame_h=max(1, int(args.frame_h or 1080)),
            source=source,
        )

    result = {
        "ok": True,
        "video": str(video_path),
        "sidecar_path": str(sidecar_path),
        "event_count": len(payload.get("events") or []),
        "counts_for_qa": bool(payload.get("counts_for_qa")),
        "qa": payload.get("qa", {}),
    }

    if args.register:
        from app.screenstudio_parity import screenstudio_register_real_recording

        result["registration"] = screenstudio_register_real_recording(
            video_path,
            manifest_path=args.manifest,
            slot_id=args.slot_id,
            require_sidecar=True,
            metadata={"sidecar_capture_source": source},
        )

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
