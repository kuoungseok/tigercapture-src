from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.qa_screenstudio_auto_polish import (  # noqa: E402
    DEFAULT_MANIFEST,
    _load_manifest,
    _materialize_real_mp4,
    _resolve,
)

DEFAULT_OUT_DIR = ROOT / "debugCapture" / "screenstudio_app_flow"


class _DummyPlayer:
    def __init__(self) -> None:
        self.project_settings: dict[str, Any] = {}

    def set_project_settings(self, settings: dict[str, Any]) -> None:
        self.project_settings = dict(settings or {})


def _make_editor_stub(frame_size: tuple[int, int]) -> SimpleNamespace:
    from app.screenstudio_polish import screenstudio_starter_defaults

    settings = {
        "starter_template_id": "screen-recording-demo",
        "screenstudio_polish": screenstudio_starter_defaults("screen-recording-demo"),
        "canvas_width": int(frame_size[0]),
        "canvas_height": int(frame_size[1]),
        "fps": 60.0,
    }
    dummy = SimpleNamespace(
        _project_settings=settings,
        _player=_DummyPlayer(),
        _clip_preview_frame_size=lambda _track, _clip: frame_size,
    )
    dummy._screenstudio_default_polish_payload = lambda: dict(settings["screenstudio_polish"])
    return dummy


def _source_frame(path: Path, *, source_ms: int, frame_size: tuple[int, int]):
    import cv2
    import numpy as np

    w, h = frame_size
    cap = cv2.VideoCapture(str(path))
    try:
        if cap.isOpened():
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 12.0)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            frame_idx = max(0, int(round(max(0, source_ms) / 1000.0 * fps)))
            if total > 0:
                frame_idx = min(total - 1, frame_idx)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, bgr = cap.read()
            if ok and bgr is not None:
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                if rgb.shape[1] != w or rgb.shape[0] != h:
                    rgb = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_LINEAR)
                return rgb
    finally:
        cap.release()
    return np.zeros((h, w, 3), dtype=np.uint8)


def _write_png(path: Path, rgb) -> None:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def _sample_ms_from_clip(clip, duration_ms: int) -> int:
    actors = sorted(getattr(clip, "zoom_actors", []) or [], key=lambda z: int(getattr(z, "start_ms", 0) or 0))
    if actors:
        actor = actors[0]
        point_ms = int(getattr(actor, "screenstudio_point_ms", getattr(actor, "start_ms", 0)) or 0)
        start_ms = int(getattr(actor, "start_ms", 0) or 0)
        end_ms = int(getattr(actor, "end_ms", 0) or 0)
        if start_ms < end_ms:
            return max(start_ms, min(end_ms - 1, point_ms))
        return max(0, point_ms)
    return max(0, int(duration_ms * 0.42))


def _label_row(before, after, *, sample_id: str, sample_ms: int, changed_ratio: float):
    import cv2
    import numpy as np

    def shrink(img):
        h, w = img.shape[:2]
        max_h = 300
        if h <= max_h:
            return img
        nw = max(2, int(round(w * max_h / h)))
        return cv2.resize(img, (nw, max_h), interpolation=cv2.INTER_AREA)

    def label(img, text):
        h, w = img.shape[:2]
        bar_h = 30
        out = np.zeros((h + bar_h, w, 3), dtype=np.uint8)
        out[:bar_h, :, :] = (13, 16, 29)
        out[bar_h:, :, :] = img
        cv2.putText(out, text[:90], (12, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (245, 248, 255), 1, cv2.LINE_AA)
        return out

    left = label(shrink(before), f"{sample_id} import source t={sample_ms}ms")
    right = label(shrink(after), f"timeline/export flow changed={changed_ratio:.1%}")
    if left.shape[0] != right.shape[0]:
        target_h = max(left.shape[0], right.shape[0])
        def pad(img):
            if img.shape[0] == target_h:
                return img
            pad_h = target_h - img.shape[0]
            filler = np.zeros((pad_h, img.shape[1], 3), dtype=np.uint8)
            filler[:, :, :] = (7, 9, 18)
            return np.vstack([img, filler])
        left = pad(left)
        right = pad(right)
    gap = np.zeros((left.shape[0], 12, 3), dtype=np.uint8)
    gap[:, :, :] = (7, 9, 18)
    return np.hstack([left, gap, right])


def _sheet(rows: list, out_path: Path) -> None:
    import numpy as np

    if not rows:
        return
    width = max(row.shape[1] for row in rows)
    padded = []
    for row in rows:
        if row.shape[1] < width:
            pad = np.zeros((row.shape[0], width - row.shape[1], 3), dtype=np.uint8)
            pad[:, :, :] = (7, 9, 18)
            row = np.hstack([row, pad])
        padded.append(row)
        gap = np.zeros((12, width, 3), dtype=np.uint8)
        gap[:, :, :] = (7, 9, 18)
        padded.append(gap)
    _write_png(out_path, np.vstack(padded[:-1]))


def _run_sample(sample: dict[str, Any], out_dir: Path) -> tuple[dict[str, Any], Any | None]:
    import numpy as np

    from app.timeline_model import NodeGraph, VideoClip, VideoTrack
    from app.video_editor_window import VideoEditorWindow
    from app.video_exporter import VideoExportThread

    sample_id = str(sample.get("id") or "sample")
    source = _resolve(str(sample.get("source") or ""))
    duration_ms = int(sample.get("duration_ms", 0) or 0)
    frame_size = (
        int(sample.get("frame_w", 1920) or 1920),
        int(sample.get("frame_h", 1080) or 1080),
    )
    real = _materialize_real_mp4(sample, source)
    real_path = Path(str(real.get("path") or ""))
    clip = VideoClip(
        id=1,
        source_path=real_path,
        source_duration_ms=duration_ms,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=duration_ms,
        node_graph=NodeGraph.default(),
    )
    track = VideoTrack(id=1, clips=[clip])
    editor = _make_editor_stub(frame_size)
    event_count = VideoEditorWindow._load_screenstudio_cursor_sidecar_for_clip(clip)
    added = VideoEditorWindow._maybe_apply_default_screenstudio_polish_to_clip(
        editor,
        track,
        clip,
        reason="app flow qa",
    )
    sample_ms = _sample_ms_from_clip(clip, duration_ms)
    exporter = VideoExportThread(
        real_path,
        out_dir / f"{sample_id}.mp4",
        [(0, duration_ms, 1.0)],
        zoom_actors=VideoEditorWindow._export_track_zoom_actors_only(track),
        render_clip_tracks=[[clip]],
        force_prerender_base=True,
        project_settings=editor._project_settings,
        target_width=frame_size[0],
        target_height=frame_size[1],
        target_fps=60.0,
    )
    caps: dict = {}
    try:
        source_before = _source_frame(real_path, source_ms=sample_ms, frame_size=frame_size)
        rendered = exporter._render_clip_tracks_rgb(
            [[clip]],
            sample_ms,
            caps,
            src_w=frame_size[0],
            src_h=frame_size[1],
        )
        rendered = exporter._apply_zoom_cpu(rendered, sample_ms)
        rendered = exporter._apply_screen_frame_style_cpu(rendered)
    finally:
        for cap, _fps in caps.values():
            try:
                cap.release()
            except Exception:
                pass

    if rendered.shape != source_before.shape:
        import cv2
        rendered_compare = cv2.resize(rendered, (source_before.shape[1], source_before.shape[0]), interpolation=cv2.INTER_AREA)
    else:
        rendered_compare = rendered
    diff = np.abs(rendered_compare.astype(np.int16) - source_before.astype(np.int16))
    changed_ratio = float(np.mean(np.any(diff > 4, axis=2)))
    mean_delta = float(np.mean(diff))
    row = _label_row(source_before, rendered, sample_id=sample_id, sample_ms=sample_ms, changed_ratio=changed_ratio)
    after_path = out_dir / f"{sample_id}_app_flow.png"
    _write_png(after_path, row)

    failures: list[str] = []
    if not real.get("ok"):
        failures.append("real_mp4_missing")
    if event_count <= 0:
        failures.append("cursor_sidecar_not_loaded")
    if added <= 0:
        failures.append("auto_polish_not_applied")
    if not getattr(clip, "zoom_actors", None):
        failures.append("clip_zoom_not_generated")
    if not (getattr(clip, "screenstudio_polish", {}) or {}).get("auto_zoom_actor_ids"):
        failures.append("clip_polish_payload_missing")
    if not (editor._project_settings or {}).get("screenstudio_polish"):
        failures.append("project_polish_default_missing")
    if changed_ratio < 0.18:
        failures.append("render_flow_too_similar_to_source")
    return {
        "id": sample_id,
        "ok": not failures,
        "failures": failures,
        "source": str(source),
        "real_mp4": real,
        "event_count": int(event_count),
        "auto_zoom_added": int(added),
        "clip_zoom_count": len(getattr(clip, "zoom_actors", []) or []),
        "export_track_zoom_count": len(VideoEditorWindow._export_track_zoom_actors_only(track)),
        "sample_ms": int(sample_ms),
        "changed_ratio": round(changed_ratio, 5),
        "mean_delta": round(mean_delta, 3),
        "image": str(after_path),
    }, row


def run_screenstudio_app_flow_qa(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    out_dir = out_dir if out_dir.is_absolute() else ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(manifest_path)
    rows = []
    samples = []
    for sample in list(manifest.get("samples") or []):
        if not isinstance(sample, dict):
            continue
        sample_report, row = _run_sample(sample, out_dir)
        samples.append(sample_report)
        if row is not None:
            rows.append(row)
    contact_sheet = out_dir / "screenstudio_app_flow_contact_sheet.png"
    _sheet(rows, contact_sheet)
    failures = [
        {"id": sample.get("id"), "failures": sample.get("failures", [])}
        for sample in samples
        if not sample.get("ok")
    ]
    changed = [float(sample.get("changed_ratio", 0.0) or 0.0) for sample in samples]
    report = {
        "ok": not failures and bool(samples) and contact_sheet.is_file(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "contact_sheet": str(contact_sheet),
        "summary": {
            "samples": len(samples),
            "passing": sum(1 for sample in samples if sample.get("ok")),
            "failing": len(failures),
            "avg_changed_ratio": round(sum(changed) / max(1, len(changed)), 5),
            "events": sum(int(sample.get("event_count", 0) or 0) for sample in samples),
            "auto_zoom_added": sum(int(sample.get("auto_zoom_added", 0) or 0) for sample in samples),
            "clip_zoom": sum(int(sample.get("clip_zoom_count", 0) or 0) for sample in samples),
            "track_zoom_export": sum(int(sample.get("export_track_zoom_count", 0) or 0) for sample in samples),
        },
        "samples": samples,
        "failures": failures,
    }
    (out_dir / "screenstudio_app_flow_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Screen Studio import/timeline/export app-flow QA.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    report = run_screenstudio_app_flow_qa(args.manifest, out_dir=args.out_dir)
    if args.report is not None:
        report_path = args.report if args.report.is_absolute() else ROOT / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        report_path = Path(str(report["contact_sheet"])).parent / "screenstudio_app_flow_report.json"
    print(json.dumps({"ok": report["ok"], "out": str(report_path), "contact_sheet": report["contact_sheet"]}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
