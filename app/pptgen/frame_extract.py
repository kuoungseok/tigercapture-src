"""Video frame extraction helpers for PPT still-image imports."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.paths import runtime_data_dir


def _safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._")
    return stem or "clip"


def extract_video_still(
    source_path: str | Path,
    *,
    source_ms: int = 0,
    output_dir: str | Path | None = None,
) -> Path:
    """Extract one source-frame as a PNG and return the cached still path."""
    path = Path(source_path)
    if not path.exists():
        raise RuntimeError(f"Video file not found: {path}")

    try:
        import cv2  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local runtime packaging
        raise RuntimeError("OpenCV is required to extract a video still image") from exc

    at_ms = max(0, int(source_ms or 0))
    out_dir = Path(output_dir) if output_dir is not None else runtime_data_dir() / "pptgen" / "stills"
    out_dir.mkdir(parents=True, exist_ok=True)

    stat = path.stat()
    key = hashlib.sha1(f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|{at_ms}".encode("utf-8")).hexdigest()[:16]
    out_path = out_dir / f"{_safe_stem(path)}_{at_ms}ms_{key}.png"
    if out_path.exists():
        return out_path

    cap = cv2.VideoCapture(str(path))
    try:
        opened = getattr(cap, "isOpened", lambda: True)()
        if not opened:
            raise RuntimeError(f"Could not open video file: {path}")

        cap.set(getattr(cv2, "CAP_PROP_POS_MSEC", 0), float(at_ms))
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.set(getattr(cv2, "CAP_PROP_POS_FRAMES", 1), 0)
            ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError(f"Could not read a frame from video: {path}")

        if not cv2.imwrite(str(out_path), frame):
            raise RuntimeError(f"Could not write still image: {out_path}")
    finally:
        release = getattr(cap, "release", None)
        if callable(release):
            release()

    return out_path


__all__ = ["extract_video_still"]
