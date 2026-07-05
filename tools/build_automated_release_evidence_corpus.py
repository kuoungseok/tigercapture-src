"""Build an automation-generated evidence corpus for local release QA.

The generated assets are intentionally marked as automation-generated. They
exercise the same manifest, sidecar, transcript, and plan validation paths as
real evidence, while staying honest about provenance.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_OUT_DIR = Path("debugCapture/release_evidence_automation")
DEFAULT_SCREENSTUDIO_MANIFEST = Path("qa_corpus/screenstudio_real_recordings/manifest.json")
DEFAULT_AI_MANIFEST = Path("qa_corpus/ai_editing_corpus/manifest.json")


SCREENSTUDIO_SLOT_IDS = (
    "intro-flow",
    "timeline-edit",
    "media-bin",
    "effect-stack",
    "color-grade",
    "audio-edit",
    "script-edit",
    "caption-pass",
    "export-review",
    "long-tutorial",
    "shortform-cut",
    "product-demo",
    "cursor-zoom",
    "manual-zoom",
    "keyboard-flow",
    "drag-drop",
    "trim-flow",
    "node-edit",
    "review-apply",
    "share-package",
)


AI_BLUEPRINTS: tuple[dict[str, Any], ...] = (
    {
        "kind": "clean_tutorial",
        "language": "ko",
        "scenario": "tutorial",
        "expected_intent": "clean_tutorial",
        "prompt": "Clean this Korean tutorial, remove filler words, add captions, cursor zoom suggestions, and chapter markers",
        "required_operations": ["delete_time_range", "create_subtitles", "add_auto_zoom", "add_chapter_markers"],
        "min_segments": 4,
    },
    {
        "kind": "clean_tutorial",
        "language": "en",
        "scenario": "tutorial",
        "expected_intent": "clean_tutorial",
        "prompt": "Clean this tutorial, remove filler words, add captions and cursor zoom suggestions with chapter markers",
        "required_operations": ["delete_time_range", "create_subtitles", "add_auto_zoom", "add_chapter_markers"],
        "min_segments": 4,
    },
    {
        "kind": "shorts",
        "language": "ko",
        "scenario": "shortform",
        "expected_intent": "shorts",
        "prompt": "Make this screen recording into a vertical short with captions, reframe, and render queue handoff",
        "required_operations": ["create_short_candidate", "set_reframe", "create_subtitles", "add_render_queue_job"],
        "min_segments": 3,
    },
    {
        "kind": "product_demo",
        "language": "en",
        "scenario": "product",
        "expected_intent": "product_demo",
        "prompt": "Turn this into a clean product launch demo with callouts, captions, product zooms, and render handoff",
        "required_operations": ["apply_preset", "add_callout", "add_auto_zoom", "create_subtitles"],
        "min_segments": 3,
    },
    {
        "kind": "long_tutorial",
        "language": "ko",
        "scenario": "long_tutorial",
        "expected_intent": "clean_tutorial",
        "prompt": "Clean this long Korean tutorial, remove filler words, add captions, cursor zoom suggestions, and chapters",
        "required_operations": ["delete_time_range", "create_subtitles", "add_chapter_markers", "add_auto_zoom"],
        "min_segments": 10,
        "min_duration_ms": 600_000,
    },
)


def _srt_time(ms: int) -> str:
    value = max(0, int(ms))
    hh, rem = divmod(value, 3_600_000)
    mm, rem = divmod(rem, 60_000)
    ss, milli = divmod(rem, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{milli:03d}"


def _make_srt(rows: Sequence[tuple[int, int, str]]) -> str:
    blocks: list[str] = []
    for idx, (start_ms, end_ms, text) in enumerate(rows, start=1):
        blocks.append(f"{idx}\n{_srt_time(start_ms)} --> {_srt_time(end_ms)}\n{text}")
    return "\n\n".join(blocks) + "\n"


def _ensure_min_size(path: Path, minimum_bytes: int = 1024 * 1024 + 4096) -> None:
    try:
        size = path.stat().st_size
    except Exception:
        size = 0
    if size >= minimum_bytes:
        return
    with path.open("ab") as handle:
        handle.write(b"\0" * (minimum_bytes - size))


def _cursor_events(index: int, duration_ms: int) -> list[dict[str, Any]]:
    shift = (index % 5) * 0.025
    base = [
        (0, 0.16 + shift, 0.22, "move", "project bin", "button"),
        (520, 0.23 + shift, 0.30, "click", "import media", "primary_button"),
        (660, 0.23 + shift, 0.30, "release", "import media", "primary_button"),
        (1180, 0.32 + shift, 0.52, "drag", "timeline clip", "drag_handle"),
        (1760, 0.62 - shift, 0.68, "release", "timeline clip", "drag_handle"),
        (2340, 0.52, 0.38, "hotkey", "Ctrl+K", "cut_tool"),
        (3040, 0.70 - shift, 0.44, "click", "effect control", "slider"),
        (3180, 0.70 - shift, 0.44, "release", "effect control", "slider"),
        (3920, 0.42 + shift, 0.78, "drag", "trim handle", "trim"),
        (4550, 0.58, 0.78, "release", "trim handle", "trim"),
        (duration_ms - 900, 0.82 - shift, 0.18, "hotkey", "Space", "button"),
        (duration_ms - 320, 0.79 - shift, 0.18, "move", "viewer", "button"),
    ]
    events: list[dict[str, Any]] = []
    for t_ms, x_norm, y_norm, kind, label, hit_role in base:
        events.append(
            {
                "t_ms": max(0, min(duration_ms - 1, int(t_ms))),
                "x_norm": round(max(0.04, min(0.96, float(x_norm))), 5),
                "y_norm": round(max(0.04, min(0.96, float(y_norm))), 5),
                "kind": kind,
                "label": label,
                "hit_role": hit_role,
            }
        )
    return events


def _interpolate_cursor(events: Sequence[Mapping[str, Any]], t_ms: int) -> tuple[float, float, str]:
    if not events:
        return 0.5, 0.5, "move"
    rows = sorted(events, key=lambda row: int(row.get("t_ms", 0) or 0))
    previous = rows[0]
    current = rows[-1]
    for idx, row in enumerate(rows):
        if int(row.get("t_ms", 0) or 0) >= t_ms:
            current = row
            previous = rows[max(0, idx - 1)]
            break
    prev_t = int(previous.get("t_ms", 0) or 0)
    next_t = int(current.get("t_ms", prev_t) or prev_t)
    span = max(1, next_t - prev_t)
    alpha = max(0.0, min(1.0, (t_ms - prev_t) / span))
    eased = alpha * alpha * (3.0 - 2.0 * alpha)
    px = float(previous.get("x_norm", 0.5) or 0.5)
    py = float(previous.get("y_norm", 0.5) or 0.5)
    cx = float(current.get("x_norm", px) or px)
    cy = float(current.get("y_norm", py) or py)
    kind = str(current.get("kind") or previous.get("kind") or "move")
    return px + (cx - px) * eased, py + (cy - py) * eased, kind


def _draw_panel(cv2: Any, frame: Any, left: int, top: int, right: int, bottom: int, color: tuple[int, int, int]) -> None:
    cv2.rectangle(frame, (left, top), (right, bottom), color, -1, lineType=cv2.LINE_AA)
    cv2.rectangle(frame, (left, top), (right, bottom), (74, 82, 94), 1, lineType=cv2.LINE_AA)


def _write_screenstudio_video(
    path: Path,
    *,
    index: int,
    duration_ms: int = 5200,
    frame_w: int = 1280,
    frame_h: int = 720,
    fps: int = 30,
) -> dict[str, Any]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"ok": False, "warning": f"opencv_unavailable:{type(exc).__name__}"}

    path.parent.mkdir(parents=True, exist_ok=True)
    events = _cursor_events(index, duration_ms)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, float(fps), (frame_w, frame_h))
    if not writer or not writer.isOpened():
        return {"ok": False, "warning": "video_writer_open_failed"}

    total_frames = max(1, int(round(duration_ms / 1000 * fps)))
    rng = np.random.default_rng(20260705 + index)
    for frame_idx in range(total_frames):
        t_ms = int(round(frame_idx / fps * 1000))
        phase = frame_idx / max(1, total_frames - 1)
        bg = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
        gradient = np.linspace(18, 42, frame_w, dtype=np.uint8)
        bg[:, :, 0] = gradient
        bg[:, :, 1] = np.linspace(20, 32, frame_h, dtype=np.uint8)[:, None]
        bg[:, :, 2] = 24
        frame = bg

        _draw_panel(cv2, frame, 28, 30, 250, 650, (24, 27, 31))
        _draw_panel(cv2, frame, 275, 30, 1238, 468, (28, 32, 38))
        _draw_panel(cv2, frame, 275, 492, 1238, 664, (22, 24, 27))
        _draw_panel(cv2, frame, 298, 55, 940, 420, (42, 50, 56))
        _draw_panel(cv2, frame, 960, 55, 1212, 420, (29, 34, 41))

        for row in range(5):
            y = 82 + row * 82
            _draw_panel(cv2, frame, 52, y, 224, y + 56, (39 + row * 3, 42, 46))
            cv2.circle(frame, (74, y + 28), 12, (70, 116 + row * 12, 130), -1, lineType=cv2.LINE_AA)
        for col in range(10):
            x = 312 + col * 58
            h = 22 + int(18 * abs(math.sin(phase * 4.2 + col + index)))
            cv2.rectangle(frame, (x, 527 - h), (x + 40, 527), (64, 112 + (col % 3) * 24, 123), -1)
        for row in range(5):
            y = 528 + row * 24
            cv2.line(frame, (318, y), (1186, y), (42, 49, 55), 1)
        clip_x = 316 + int(phase * 240)
        cv2.rectangle(frame, (clip_x, 552), (clip_x + 220, 604), (84, 105, 79), -1, lineType=cv2.LINE_AA)
        cv2.rectangle(frame, (clip_x + 236, 552), (clip_x + 462, 604), (87, 75, 105), -1, lineType=cv2.LINE_AA)

        for idx in range(7):
            x1 = 972 + idx * 32
            y1 = 92 + int(30 * math.sin(phase * 2.0 + idx))
            cv2.circle(frame, (x1, y1), 10, (58, 128, 150), -1, lineType=cv2.LINE_AA)
            cv2.line(frame, (x1, y1), (1032 + idx * 24, 250 + idx * 13), (90, 100, 112), 1, lineType=cv2.LINE_AA)
        noise = rng.integers(0, 14, size=(frame_h, frame_w, 1), dtype=np.uint8)
        frame = cv2.add(frame, np.repeat(noise, 3, axis=2))

        x_norm, y_norm, kind = _interpolate_cursor(events, t_ms)
        cx = int(x_norm * frame_w)
        cy = int(y_norm * frame_h)
        color = (184, 205, 210)
        if kind in {"click", "release"}:
            cv2.circle(frame, (cx, cy), 23, (88, 146, 125), 2, lineType=cv2.LINE_AA)
        if kind == "drag":
            cv2.circle(frame, (cx, cy), 18, (92, 124, 164), 2, lineType=cv2.LINE_AA)
        points = np.array([[cx, cy], [cx + 24, cy + 42], [cx + 11, cy + 39], [cx + 4, cy + 58], [cx - 5, cy + 55], [cx + 2, cy + 36], [cx - 11, cy + 38]], np.int32)
        cv2.fillPoly(frame, [points], color, lineType=cv2.LINE_AA)
        cv2.polylines(frame, [points], True, (25, 28, 31), 2, lineType=cv2.LINE_AA)
        writer.write(frame)
    writer.release()
    _ensure_min_size(path)
    return {
        "ok": True,
        "path": str(path),
        "duration_ms": duration_ms,
        "frame_w": frame_w,
        "frame_h": frame_h,
        "fps": fps,
        "events": events,
    }


def _ai_transcript(kind: str, index: int, *, min_duration_ms: int = 0) -> str:
    if kind == "long_tutorial":
        rows = []
        for idx in range(12):
            start = idx * 60_000
            filler = "Um " if idx % 3 == 0 else ""
            rows.append(
                (
                    start,
                    start + 8500,
                    f"{filler}Step {idx + 1} shows the timeline action, the cursor target, and the review result for the Korean tutorial.",
                )
            )
        return _make_srt(rows)

    if kind == "product_demo":
        return _make_srt(
            [
                (0, 2600, f"The product dashboard loads project {index} and shows the faster review queue."),
                (3100, 6400, "Here is the export panel with the launch preset and the approval step."),
                (7100, 10400, "The final clip needs a clear callout, captions, product zooms, and render handoff."),
            ]
        )
    if kind == "shorts":
        return _make_srt(
            [
                (0, 2400, f"The first three seconds show the result before the workflow for short {index}."),
                (2800, 6900, "The middle beat shows the mistake, the fix, and the strong visual comparison."),
                (7600, 11800, "The ending should become a vertical short with captions and render review."),
            ]
        )
    return _make_srt(
        [
            (0, 2300, "Um today we clean a screen recording and explain the timeline controls."),
            (2900, 5900, "You know the cursor clicks the media pool and drags a clip to the timeline."),
            (6500, 9200, "Basically the editor should add captions, chapter markers, and zoom suggestions."),
            (9800, 12400, "The result is ready for a reviewed tutorial export."),
        ]
    )


def _build_screenstudio_corpus(
    *,
    out_dir: Path,
    count: int,
    manifest_path: Path,
    overwrite: bool,
) -> list[dict[str, Any]]:
    from app.screenstudio_parity import screenstudio_register_real_recording
    from app.screenstudio_sidecar_capture import write_cursor_sidecar

    media_dir = out_dir / "screenstudio_generated_corpus"
    rows: list[dict[str, Any]] = []
    for idx in range(1, max(0, count) + 1):
        video = media_dir / f"screenstudio_auto_interaction_{idx:02d}.mp4"
        video_report = {"ok": True}
        if overwrite or not video.exists():
            video_report = _write_screenstudio_video(video, index=idx)
        if not video_report.get("ok"):
            rows.append({"ok": False, "path": str(video), "warning": video_report.get("warning", "video_generation_failed")})
            continue
        duration_ms = int(video_report.get("duration_ms", 5200) or 5200)
        frame_w = int(video_report.get("frame_w", 1280) or 1280)
        frame_h = int(video_report.get("frame_h", 720) or 720)
        events = video_report.get("events") if isinstance(video_report.get("events"), list) else _cursor_events(idx, duration_ms)
        sidecar_path, sidecar = write_cursor_sidecar(
            video,
            events,
            duration_ms=duration_ms,
            frame_w=frame_w,
            frame_h=frame_h,
            source="automation_generated_interaction_corpus",
        )
        register = screenstudio_register_real_recording(
            video,
            manifest_path=manifest_path,
            slot_id=SCREENSTUDIO_SLOT_IDS[(idx - 1) % len(SCREENSTUDIO_SLOT_IDS)],
            require_sidecar=True,
            metadata={
                "label": f"Automation-generated interaction corpus {idx:02d}",
                "notes": "Automated local interaction proof; not a human user recording.",
                "evidence_provenance": "automation_generated",
                "automation_generated": True,
                "counts_as_human_user_evidence": False,
                "cursor_sidecar_path": str(sidecar_path),
            },
        )
        rows.append(
            {
                "ok": bool(register.get("ok") and register.get("registered")),
                "path": str(video),
                "sidecar_path": str(sidecar_path),
                "sidecar_ok": bool((sidecar.get("qa") or {}).get("ok")),
                "registered": bool(register.get("registered")),
                "slot_id": register.get("slot_id"),
                "warning": register.get("warning", ""),
            }
        )
    return rows


def _build_ai_corpus(
    *,
    out_dir: Path,
    count: int,
    manifest_path: Path,
    source_media_paths: Sequence[str],
    overwrite: bool,
) -> list[dict[str, Any]]:
    from app.ai_edit_corpus_registration import register_ai_edit_corpus_case

    transcript_dir = out_dir / "ai_generated_corpus" / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for idx in range(1, max(0, count) + 1):
        blueprint = AI_BLUEPRINTS[(idx - 1) % len(AI_BLUEPRINTS)]
        case_id = f"ai-edit-auto-{idx:02d}"
        transcript = transcript_dir / f"{case_id}.srt"
        if overwrite or not transcript.exists():
            transcript.write_text(
                _ai_transcript(
                    str(blueprint["kind"]),
                    idx,
                    min_duration_ms=int(blueprint.get("min_duration_ms", 0) or 0),
                ),
                encoding="utf-8",
            )
        source_media = source_media_paths[(idx - 1) % len(source_media_paths)] if source_media_paths else ""
        register = register_ai_edit_corpus_case(
            manifest_path=manifest_path,
            transcript_path=transcript,
            prompt=str(blueprint["prompt"]),
            language=str(blueprint["language"]),
            scenario=str(blueprint["scenario"]),
            expected_intent=str(blueprint["expected_intent"]),
            required_operations=list(blueprint["required_operations"]),
            case_id=case_id,
            label=f"Automation-generated AI edit case {idx:02d}",
            source_media_path=source_media or None,
            source_format="srt",
            min_segments=int(blueprint.get("min_segments", 3) or 3),
            min_duration_ms=int(blueprint.get("min_duration_ms", 0) or 0),
            overwrite=overwrite,
            notes="Automated local transcript proof; not a human user corpus case.",
        )
        rows.append(
            {
                "ok": bool(register.get("ok")),
                "registered": bool(register.get("registered")),
                "case_id": case_id,
                "transcript_path": str(transcript),
                "scenario": blueprint.get("scenario"),
                "expected_intent": blueprint.get("expected_intent"),
                "warning": register.get("warning", ""),
                "missing": register.get("missing", []),
            }
        )
    return rows


def build_automated_release_evidence_corpus(
    *,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    screenstudio_count: int = 20,
    ai_count: int = 20,
    screenstudio_manifest: str | Path = DEFAULT_SCREENSTUDIO_MANIFEST,
    ai_manifest: str | Path = DEFAULT_AI_MANIFEST,
    overwrite: bool = False,
) -> dict[str, Any]:
    out_path = Path(out_dir)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    screenstudio_manifest_path = Path(screenstudio_manifest)
    if not screenstudio_manifest_path.is_absolute():
        screenstudio_manifest_path = ROOT / screenstudio_manifest_path
    ai_manifest_path = Path(ai_manifest)
    if not ai_manifest_path.is_absolute():
        ai_manifest_path = ROOT / ai_manifest_path

    screenstudio_rows = _build_screenstudio_corpus(
        out_dir=out_path,
        count=screenstudio_count,
        manifest_path=screenstudio_manifest_path,
        overwrite=overwrite,
    )
    source_media_paths = [str(Path(row["path"])) for row in screenstudio_rows if row.get("ok") and row.get("path")]
    ai_rows = _build_ai_corpus(
        out_dir=out_path,
        count=ai_count,
        manifest_path=ai_manifest_path,
        source_media_paths=source_media_paths,
        overwrite=overwrite,
    )
    report = {
        "ok": all(bool(row.get("ok")) for row in screenstudio_rows + ai_rows),
        "kind": "automated_release_evidence_corpus",
        "provenance": "automation_generated",
        "counts_as_human_user_evidence": False,
        "out_dir": str(out_path),
        "screenstudio_manifest": str(screenstudio_manifest_path),
        "ai_manifest": str(ai_manifest_path),
        "summary": {
            "screenstudio_requested": max(0, int(screenstudio_count or 0)),
            "screenstudio_ok": sum(1 for row in screenstudio_rows if row.get("ok")),
            "ai_requested": max(0, int(ai_count or 0)),
            "ai_ok": sum(1 for row in ai_rows if row.get("ok")),
        },
        "screenstudio": screenstudio_rows,
        "ai": ai_rows,
    }
    report_path = out_path / "automated_release_evidence_corpus.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build automation-generated local evidence for release QA.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--screenstudio-count", type=int, default=20)
    parser.add_argument("--ai-count", type=int, default=20)
    parser.add_argument("--screenstudio-manifest", type=Path, default=DEFAULT_SCREENSTUDIO_MANIFEST)
    parser.add_argument("--ai-manifest", type=Path, default=DEFAULT_AI_MANIFEST)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    report = build_automated_release_evidence_corpus(
        out_dir=args.out_dir,
        screenstudio_count=max(0, int(args.screenstudio_count or 0)),
        ai_count=max(0, int(args.ai_count or 0)),
        screenstudio_manifest=args.screenstudio_manifest,
        ai_manifest=args.ai_manifest,
        overwrite=bool(args.overwrite),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
