"""Render one annotated face-tracking preview frame."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.video_face_driver import FaceMotionTuning, VideoFaceMotionExtractor, apply_motion_tuning


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render an annotated VTuber face-driver preview PNG.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "vtuber_face_preview.png"))
    parser.add_argument("--backend", choices=["auto", "mediapipe_tasks", "mediapipe", "opencv"], default="auto")
    parser.add_argument("--max-width", type=int, default=1280)
    args = parser.parse_args(argv)

    import cv2

    result = VideoFaceMotionExtractor(max_fps=15, backend=args.backend).extract(args.video, max_frames=1)
    frames = apply_motion_tuning(result.frames, FaceMotionTuning())
    cap = cv2.VideoCapture(args.video)
    ok, image = cap.read()
    cap.release()
    if not ok or not frames:
        print({"ok": False, "errors": result.diagnostics.get("errors") or ["frame_read_failed"]})
        return 2

    frame = frames[0]
    if frame.face_box:
        x, y, w, h = frame.face_box
        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 220, 255), 3)
    text = (
        f"{frame.source} yaw={frame.yaw_deg:.2f} pitch={frame.pitch_deg:.2f} "
        f"mouth={frame.mouth_open:.2f} blink=({frame.blink_l:.2f},{frame.blink_r:.2f})"
    )
    cv2.rectangle(image, (20, 20), (min(image.shape[1] - 20, 1160), 78), (0, 0, 0), -1)
    cv2.putText(image, text, (32, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (255, 255, 255), 2, cv2.LINE_AA)
    scale = min(1.0, float(args.max_width) / max(1, image.shape[1]))
    if scale < 1.0:
        image = cv2.resize(image, (int(image.shape[1] * scale), int(image.shape[0] * scale)), interpolation=cv2.INTER_AREA)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), image)
    print({"ok": True, "out": str(out), "selected_backend": result.diagnostics.get("selected_backend")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
