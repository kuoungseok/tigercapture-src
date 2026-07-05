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

DEFAULT_OUT_DIR = ROOT / "debugCapture" / "screenstudio_visual_polish"


def _read_frame_rgb(path: Path, *, source_ms: int, target_size: tuple[int, int]) -> Any:
    import cv2
    import numpy as np

    out_w, out_h = max(16, int(target_size[0])), max(16, int(target_size[1]))
    try:
        cap = cv2.VideoCapture(str(path))
        if cap.isOpened():
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 12.0)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            frame_idx = max(0, int(round(max(0, source_ms) / 1000.0 * fps)))
            if total > 0:
                frame_idx = min(total - 1, frame_idx)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, bgr = cap.read()
            cap.release()
            if ok and bgr is not None:
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                if rgb.shape[1] != out_w or rgb.shape[0] != out_h:
                    rgb = cv2.resize(rgb, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
                return np.ascontiguousarray(rgb)
    except Exception:
        pass

    x = np.linspace(0, 1, out_w, dtype=np.float32)[None, :]
    y = np.linspace(0, 1, out_h, dtype=np.float32)[:, None]
    frame = np.zeros((out_h, out_w, 3), dtype=np.uint8)
    frame[:, :, 0] = np.clip(24 + 122 * x + 48 * y, 0, 255)
    frame[:, :, 1] = np.clip(34 + 90 * y + 65 * (1.0 - x), 0, 255)
    frame[:, :, 2] = np.clip(78 + 118 * (1.0 - x) + 28 * y, 0, 255)
    cv2.rectangle(frame, (28, 28), (out_w - 28, out_h - 28), (255, 255, 255), 3, cv2.LINE_AA)
    return frame


def _candidate_sample_ms(report: dict[str, Any], duration_ms: int) -> int:
    candidates = [c for c in list(report.get("zoom_candidates") or []) if isinstance(c, dict) and c.get("enabled", True)]
    if candidates:
        best = sorted(
            candidates,
            key=lambda c: (
                {"click": 0, "down": 0, "hotkey": 1, "key": 1, "release": 2}.get(str(c.get("kind") or ""), 3),
                int(c.get("point_ms", c.get("start_ms", 0)) or 0),
            ),
        )[0]
        point_ms = int(best.get("point_ms", best.get("start_ms", 0)) or 0)
        start_ms = int(best.get("start_ms", 0) or 0)
        end_ms = int(best.get("end_ms", 0) or 0)
        if start_ms < end_ms:
            return max(start_ms, min(end_ms - 1, point_ms))
        return max(0, point_ms)
    return max(0, int(duration_ms * 0.42))


def _zoom_candidate_at(report: dict[str, Any], sample_ms: int) -> dict[str, Any] | None:
    candidates = [
        c
        for c in list(report.get("zoom_candidates") or [])
        if isinstance(c, dict) and c.get("enabled", True)
    ]
    active = [
        c
        for c in candidates
        if int(c.get("start_ms", 0) or 0) <= sample_ms < int(c.get("end_ms", 0) or 0)
    ]
    if active:
        return active[0]
    return candidates[0] if candidates else None


def _apply_zoom_candidate(rgb: Any, candidate: dict[str, Any] | None, sample_ms: int) -> Any:
    if not candidate:
        return rgb
    try:
        import cv2
        from app.timeline_model import ZoomActor, zoom_motion_blur_amount, zoom_window_at

        h, w = rgb.shape[:2]
        frame_w = max(1, int(candidate.get("frame_w", w) or w))
        frame_h = max(1, int(candidate.get("frame_h", h) or h))
        sx = w / frame_w
        sy = h / frame_h
        actor = ZoomActor(
            id=1,
            start_ms=int(candidate.get("start_ms", 0) or 0),
            end_ms=int(candidate.get("end_ms", 0) or 0),
            target_x=int(round(float(candidate.get("target_x", 0) or 0) * sx)),
            target_y=int(round(float(candidate.get("target_y", 0) or 0) * sy)),
            target_w=max(2, int(round(float(candidate.get("target_w", w) or w) * sx))),
            target_h=max(2, int(round(float(candidate.get("target_h", h) or h) * sy))),
            easing=str(candidate.get("easing", "smooth_pop") or "smooth_pop"),
            motion_blur=float(candidate.get("motion_blur", 0.0) or 0.0),
        )
        window = zoom_window_at(actor, int(sample_ms), w, h)
        if window is None:
            return rgb
        cx, cy, cw, ch = window
        cx_i = max(0, min(w - 1, int(round(cx))))
        cy_i = max(0, min(h - 1, int(round(cy))))
        cw_i = max(2, min(w - cx_i, int(round(cw))))
        ch_i = max(2, min(h - cy_i, int(round(ch))))
        cropped = rgb[cy_i:cy_i + ch_i, cx_i:cx_i + cw_i]
        out = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
        blur_amount = float(zoom_motion_blur_amount(actor, int(sample_ms)))
        if blur_amount > 0.001:
            kernel = max(3, int(round(3 + blur_amount * 12)))
            if kernel % 2 == 0:
                kernel += 1
            blurred = cv2.GaussianBlur(out, (kernel, kernel), 0)
            out = cv2.addWeighted(out, max(0.0, 1.0 - blur_amount * 0.38), blurred, min(1.0, blur_amount * 0.38), 0)
        return out
    except Exception:
        return rgb


def _cursor_focus_metrics(before: Any, after: Any, owner: SimpleNamespace, sample_ms: int, payload: dict[str, Any]) -> dict[str, Any]:
    import numpy as np

    from app.screenstudio_polish import cursor_state_at

    events = list(getattr(owner, "cursor_events", []) or [])
    cursor = dict((payload.get("cursor") or {}) if isinstance(payload, dict) else {})
    state = cursor_state_at(
        events,
        int(sample_ms),
        smoothing=float(cursor.get("cursor_smoothing", 0.72) or 0.72),
        motion_easing=str(cursor.get("motion_easing", "smooth") or "smooth"),
        hide_after_ms=int(cursor.get("hide_static_after_ms", 900) or 900),
        click_ring_ms=int(cursor.get("click_ring_ms", 420) or 420),
        click_hold_ms=int(cursor.get("click_hold_ms", 110) or 110),
        drag_trail_ms=int(cursor.get("drag_trail_ms", 620) or 620),
        duration_ms=max(int(sample_ms) + 1000, max((int(e.get("t_ms", 0) or 0) for e in events), default=0) + 1000),
        loop_cursor=bool(cursor.get("loop_cursor", False)),
        loop_return_ms=int(cursor.get("loop_return_ms", 900) or 900),
    )
    if not state:
        return {"ok": False, "reason": "no_cursor_state"}
    focus = state.get("click") or state.get("key") or state
    h, w = before.shape[:2]
    cx = int(round(float(focus.get("x_norm", 0.5) or 0.5) * w))
    cy = int(round(float(focus.get("y_norm", 0.5) or 0.5) * h))
    radius = max(8, int(round(min(w, h) * 0.055)))
    x0 = max(0, cx - radius)
    x1 = min(w, cx + radius + 1)
    y0 = max(0, cy - radius)
    y1 = min(h, cy + radius + 1)
    if x1 <= x0 or y1 <= y0:
        return {"ok": False, "reason": "empty_focus_patch"}
    patch_diff = np.abs(after[y0:y1, x0:x1].astype(np.int16) - before[y0:y1, x0:x1].astype(np.int16))
    frame_diff = np.abs(after.astype(np.int16) - before.astype(np.int16))
    focus_delta = float(np.mean(patch_diff))
    frame_delta = float(np.mean(frame_diff))
    local_changed = float(np.mean(np.any(patch_diff > 8, axis=2)))
    return {
        "ok": bool(focus_delta >= 9.0 and local_changed >= 0.10),
        "kind": str((focus or {}).get("kind") or state.get("kind") or "cursor"),
        "focus_delta": round(focus_delta, 3),
        "frame_delta": round(frame_delta, 3),
        "local_changed_ratio": round(local_changed, 5),
        "x_norm": round(float(focus.get("x_norm", 0.5) or 0.5), 4),
        "y_norm": round(float(focus.get("y_norm", 0.5) or 0.5), 4),
    }


def _owner_for(real_mp4: Path, payload: dict[str, Any]) -> SimpleNamespace:
    from app.screenstudio_polish import load_cursor_sidecar

    events = load_cursor_sidecar(real_mp4)
    return SimpleNamespace(
        source_path=str(real_mp4),
        cursor_events=[event.to_dict() for event in events],
        screenstudio_polish=payload,
    )


def _label_bar(rgb: Any, label: str) -> Any:
    import cv2
    import numpy as np

    h, w = rgb.shape[:2]
    bar_h = max(28, int(round(h * 0.075)))
    out = np.zeros((h + bar_h, w, 3), dtype=np.uint8)
    out[:bar_h, :, :] = (14, 17, 30)
    out[bar_h:, :, :] = rgb
    cv2.putText(
        out,
        label[:90],
        (14, int(bar_h * 0.68)),
        cv2.FONT_HERSHEY_SIMPLEX,
        max(0.45, bar_h / 54.0),
        (245, 248, 255),
        1,
        cv2.LINE_AA,
    )
    return out


def _to_sheet_row(before: Any, after: Any, *, sample_id: str, sample_ms: int, changed_ratio: float) -> Any:
    import cv2
    import numpy as np

    max_h = 360
    def scale(img: Any) -> Any:
        h, w = img.shape[:2]
        if h <= max_h:
            return img
        out_w = max(2, int(round(w * max_h / h)))
        return cv2.resize(img, (out_w, max_h), interpolation=cv2.INTER_AREA)

    left = _label_bar(scale(before), f"{sample_id} BEFORE  t={sample_ms}ms")
    right = _label_bar(scale(after), f"AFTER  changed={changed_ratio:.1%}")
    if left.shape[0] != right.shape[0]:
        target_h = max(left.shape[0], right.shape[0])
        def pad_h(img: Any) -> Any:
            if img.shape[0] == target_h:
                return img
            pad = np.zeros((target_h - img.shape[0], img.shape[1], 3), dtype=np.uint8)
            pad[:, :, :] = (7, 9, 18)
            return np.vstack([img, pad])
        left = pad_h(left)
        right = pad_h(right)
    gutter = np.zeros((left.shape[0], 14, 3), dtype=np.uint8)
    gutter[:, :, :] = (7, 9, 18)
    return np.hstack([left, gutter, right])


def _write_png(path: Path, rgb: Any) -> None:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def _visual_sample(sample: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    import cv2
    import numpy as np

    from app.screenstudio_polish import (
        apply_cursor_fx_rgb,
        apply_screen_frame_style_rgb,
        screenstudio_sidecar_report,
        screenstudio_starter_defaults,
    )

    source = _resolve(str(sample.get("source") or ""))
    duration_ms = int(sample.get("duration_ms", 0) or 0)
    frame_size = (int(sample.get("frame_w", 1920) or 1920), int(sample.get("frame_h", 1080) or 1080))
    sample_id = str(sample.get("id") or source.stem)
    report = screenstudio_sidecar_report(
        source,
        duration_ms=duration_ms,
        frame_w=frame_size[0],
        frame_h=frame_size[1],
        include_parity=True,
    )
    real = _materialize_real_mp4(sample, source)
    real_path = Path(str(real.get("path") or ""))
    sample_ms = _candidate_sample_ms(report, duration_ms)
    decode_ms = min(sample_ms, 2300)
    before = _read_frame_rgb(real_path, source_ms=decode_ms, target_size=frame_size)
    payload = screenstudio_starter_defaults("screen-recording-demo")
    owner = _owner_for(real_path, payload)
    zoom_candidate = _zoom_candidate_at(report, sample_ms)
    zoomed = _apply_zoom_candidate(before.copy(), zoom_candidate, sample_ms)
    cursor_only = apply_cursor_fx_rgb(
        zoomed,
        sample_ms,
        owner=owner,
        project_settings={"screenstudio_polish": payload},
    )
    cursor_focus = _cursor_focus_metrics(zoomed, cursor_only, owner, sample_ms, payload)
    after = apply_screen_frame_style_rgb(
        cursor_only,
        owner=owner,
        project_settings={"screenstudio_polish": payload},
        target_size=frame_size,
    )
    if after.shape != before.shape:
        after_compare = cv2.resize(after, (before.shape[1], before.shape[0]), interpolation=cv2.INTER_AREA)
    else:
        after_compare = after
    diff = np.abs(after_compare.astype(np.int16) - before.astype(np.int16))
    changed = np.any(diff > 4, axis=2)
    changed_ratio = float(np.mean(changed))
    mean_delta = float(np.mean(diff))
    contact = _to_sheet_row(before, after, sample_id=sample_id, sample_ms=sample_ms, changed_ratio=changed_ratio)

    before_path = out_dir / f"{sample_id}_before.png"
    after_path = out_dir / f"{sample_id}_after.png"
    contact_path = out_dir / f"{sample_id}_contact.png"
    _write_png(before_path, before)
    _write_png(after_path, after)
    _write_png(contact_path, contact)

    failures: list[str] = []
    if not real.get("ok"):
        failures.append("real_mp4_missing")
    if not report.get("parity_ok"):
        failures.append("preview_export_parity_mismatch")
    if int(report.get("auto_zoom_count", 0) or 0) <= 0:
        failures.append("missing_auto_zoom_candidate")
    if changed_ratio < 0.18:
        failures.append("after_frame_too_similar_to_before")
    if not cursor_focus.get("ok"):
        failures.append("cursor_fx_focus_too_weak")
    return {
        "id": sample_id,
        "ok": not failures,
        "failures": failures,
        "source": str(source),
        "real_mp4": real,
        "sample_ms": int(sample_ms),
        "decode_ms": int(decode_ms),
        "event_count": int(report.get("event_count", 0) or 0),
        "auto_zoom_count": int(report.get("auto_zoom_count", 0) or 0),
        "parity_ok": bool(report.get("parity_ok")),
        "changed_ratio": round(changed_ratio, 5),
        "mean_delta": round(mean_delta, 3),
        "cursor_focus": cursor_focus,
        "zoom_kind": str((zoom_candidate or {}).get("kind", "")),
        "images": {
            "before": str(before_path),
            "after": str(after_path),
            "contact": str(contact_path),
        },
        "warnings": list(report.get("warnings") or []),
    }


def _write_contact_sheet(samples: list[dict[str, Any]], out_path: Path) -> None:
    import cv2
    import numpy as np

    rows = []
    for sample in samples:
        path = Path(str((sample.get("images") or {}).get("contact") or ""))
        if not path.is_file():
            continue
        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if bgr is None:
            continue
        rows.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    if not rows:
        return
    max_w = max(row.shape[1] for row in rows)
    padded = []
    for row in rows:
        if row.shape[1] < max_w:
            pad = np.zeros((row.shape[0], max_w - row.shape[1], 3), dtype=np.uint8)
            pad[:, :, :] = (7, 9, 18)
            row = np.hstack([row, pad])
        padded.append(row)
        gap = np.zeros((12, max_w, 3), dtype=np.uint8)
        gap[:, :, :] = (7, 9, 18)
        padded.append(gap)
    sheet = np.vstack(padded[:-1])
    _write_png(out_path, sheet)


def run_screenstudio_visual_polish_qa(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    out_dir = out_dir if out_dir.is_absolute() else ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(manifest_path)
    samples = [
        _visual_sample(sample, out_dir)
        for sample in list(manifest.get("samples") or [])
        if isinstance(sample, dict)
    ]
    contact_sheet = out_dir / "screenstudio_visual_contact_sheet.png"
    _write_contact_sheet(samples, contact_sheet)
    failures = [
        {"id": sample.get("id"), "failures": sample.get("failures", [])}
        for sample in samples
        if not sample.get("ok")
    ]
    changed = [float(sample.get("changed_ratio", 0.0) or 0.0) for sample in samples]
    focus = [float((sample.get("cursor_focus") or {}).get("focus_delta", 0.0) or 0.0) for sample in samples]
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
            "avg_cursor_focus_delta": round(sum(focus) / max(1, len(focus)), 3),
            "cursor_focus": sum(1 for sample in samples if (sample.get("cursor_focus") or {}).get("ok")),
            "visual_samples": sum(1 for sample in samples if Path(str((sample.get("images") or {}).get("after") or "")).is_file()),
            "auto_zoom_candidates": sum(int(sample.get("auto_zoom_count", 0) or 0) for sample in samples),
            "parity": sum(1 for sample in samples if sample.get("parity_ok")),
        },
        "samples": samples,
        "failures": failures,
    }
    report_path = out_dir / "screenstudio_visual_polish_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Render before/after Screen Studio Auto Polish visual QA sheets.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    report = run_screenstudio_visual_polish_qa(args.manifest, out_dir=args.out_dir)
    report_path = args.report
    if report_path is not None:
        report_path = report_path if report_path.is_absolute() else ROOT / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(report_path or (Path(report["contact_sheet"]).parent / "screenstudio_visual_polish_report.json")), "contact_sheet": report["contact_sheet"]}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
