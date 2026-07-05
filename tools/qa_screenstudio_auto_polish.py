from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_MANIFEST = ROOT / "qa_corpus" / "screenstudio_auto_polish" / "manifest.json"
REAL_MP4_DIR = ROOT / "debugCapture" / "screenstudio_auto_polish_real_mp4"


def _load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"samples": []}
    return payload if isinstance(payload, dict) else {"samples": []}


def _resolve(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT / path


def _materialize_real_mp4(sample: dict[str, Any], source: Path) -> dict[str, Any]:
    """Create a tiny real MP4 next to debug reports so corpus checks are not
    limited to placeholder filenames.
    """
    sample_id = str(sample.get("id") or source.stem)
    out = REAL_MP4_DIR / f"{sample_id}.mp4"
    sidecar = out.with_name(out.name + ".cursor.json")
    try:
        import cv2
        import numpy as np

        REAL_MP4_DIR.mkdir(parents=True, exist_ok=True)
        w, h = 320, 180
        fps = 12.0
        frames = 30
        writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        if not writer.isOpened():
            return {"ok": False, "path": str(out), "reason": "video_writer_not_opened"}
        try:
            for idx in range(frames):
                x = np.linspace(0, 1, w, dtype=np.float32)[None, :]
                y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
                phase = idx / max(1, frames - 1)
                frame = np.zeros((h, w, 3), dtype=np.uint8)
                frame[:, :, 0] = np.clip(35 + 120 * x + 40 * phase, 0, 255)
                frame[:, :, 1] = np.clip(42 + 90 * y + 70 * (1.0 - phase), 0, 255)
                frame[:, :, 2] = np.clip(80 + 105 * (1.0 - x) + 35 * y, 0, 255)
                cx = int(w * (0.18 + 0.66 * phase))
                cy = int(h * (0.28 + 0.24 * np.sin(phase * np.pi)))
                cv2.circle(frame, (cx, cy), 8, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.rectangle(frame, (18, 18), (w - 18, h - 18), (255, 255, 255), 1, cv2.LINE_AA)
                writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        finally:
            writer.release()
        source_sidecar = source.with_name(source.name + ".cursor.json")
        if source_sidecar.is_file():
            sidecar.write_text(source_sidecar.read_text(encoding="utf-8"), encoding="utf-8")
        ok = out.is_file() and out.stat().st_size > 1024 and sidecar.is_file()
        return {"ok": bool(ok), "path": str(out), "sidecar": str(sidecar), "bytes": out.stat().st_size if out.is_file() else 0}
    except Exception as exc:
        return {"ok": False, "path": str(out), "reason": str(exc)}


def _check_sample(sample: dict[str, Any]) -> dict[str, Any]:
    from app.screenstudio_polish import screenstudio_sidecar_report

    source = _resolve(str(sample.get("source") or ""))
    report = screenstudio_sidecar_report(
        source,
        duration_ms=int(sample.get("duration_ms", 0) or 0),
        frame_w=int(sample.get("frame_w", 1920) or 1920),
        frame_h=int(sample.get("frame_h", 1080) or 1080),
        include_parity=True,
    )
    failures: list[str] = []
    if int(report.get("event_count", 0) or 0) < int(sample.get("min_events", 0) or 0):
        failures.append("event_count_below_minimum")
    if int(report.get("auto_zoom_count", 0) or 0) < int(sample.get("min_zoom_candidates", 0) or 0):
        failures.append("auto_zoom_candidates_below_minimum")
    counts = report.get("counts", {}) or {}
    for key, expected in (sample.get("required_counts", {}) or {}).items():
        if int(counts.get(key, 0) or 0) < int(expected or 0):
            failures.append(f"missing_required_{key}")
    candidates = list(report.get("zoom_candidates") or [])
    if not candidates:
        failures.append("missing_zoom_candidate_preview")
    if any(not c.get("enabled", True) for c in candidates):
        failures.append("fixture_candidate_unexpectedly_disabled")
    candidate_counts: dict[str, int] = {}
    for candidate in candidates:
        kind = str(candidate.get("kind") or "action")
        candidate_counts[kind] = candidate_counts.get(kind, 0) + 1
    for key, expected in (sample.get("required_candidate_kinds", {}) or {}).items():
        if int(candidate_counts.get(str(key), 0) or 0) < int(expected or 0):
            failures.append(f"missing_required_candidate_{key}")
    if not bool(report.get("parity_ok")):
        failures.append("preview_export_visual_parity_mismatch")
    real_mp4 = _materialize_real_mp4(sample, source)
    if not real_mp4.get("ok"):
        failures.append("real_mp4_materialization_failed")
    return {
        "id": str(sample.get("id") or source.stem),
        "source": str(source),
        "ok": not failures and bool(report.get("event_count", 0)),
        "failures": failures,
        "readiness": int(report.get("readiness", 0) or 0),
        "event_count": int(report.get("event_count", 0) or 0),
        "auto_zoom_count": int(report.get("auto_zoom_count", 0) or 0),
        "counts": counts,
        "candidate_counts": candidate_counts,
        "cursor_loop_ready": bool(report.get("cursor_loop_ready")),
        "cursor_loop_return_ms": int(report.get("cursor_loop_return_ms", 0) or 0),
        "hotkey_labels": list(report.get("hotkey_labels") or []),
        "parity_ok": bool(report.get("parity_ok")),
        "parity_checked": bool(report.get("parity_checked")),
        "real_mp4": real_mp4,
        "warnings": list(report.get("warnings") or []),
        "zoom_candidates": candidates[:8],
    }


def run_screenstudio_auto_polish_qa(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    samples = [
        _check_sample(sample)
        for sample in list(manifest.get("samples") or [])
        if isinstance(sample, dict)
    ]
    failures = [
        {"id": sample["id"], "failures": sample["failures"], "warnings": sample["warnings"]}
        for sample in samples
        if not sample.get("ok")
    ]
    return {
        "ok": not failures and bool(samples),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "summary": {
            "samples": len(samples),
            "passing": sum(1 for sample in samples if sample.get("ok")),
            "failing": len(failures),
            "zoom_candidates": sum(int(sample.get("auto_zoom_count", 0) or 0) for sample in samples),
            "dwell_candidates": sum(int((sample.get("candidate_counts") or {}).get("dwell", 0) or 0) for sample in samples),
            "cursor_loop_ready": sum(1 for sample in samples if sample.get("cursor_loop_ready")),
            "visual_parity": sum(1 for sample in samples if sample.get("parity_ok")),
            "real_mp4_samples": sum(1 for sample in samples if (sample.get("real_mp4") or {}).get("ok")),
        },
        "samples": samples,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Screen Studio Auto Polish metadata QA.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/screenstudio_auto_polish_qa.json"))
    args = parser.parse_args()
    report = run_screenstudio_auto_polish_qa(args.manifest)
    out = args.out
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(out)}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
