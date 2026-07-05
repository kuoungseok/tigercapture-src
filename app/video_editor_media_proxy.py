from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal


def _proxy_path_for(path: Path) -> Path:
    source = Path(path)
    return source.parent / "proxies" / f"{source.stem}_proxy.mp4"


def _proxy_state_for(path: Path) -> str:
    """Return missing, ready, or stale for ``path``'s sibling proxy."""
    source = Path(path)
    proxy = _proxy_path_for(source)
    if not proxy.exists():
        return "missing"
    try:
        if proxy.stat().st_mtime_ns < source.stat().st_mtime_ns:
            return "stale"
    except Exception:
        pass
    return "ready"


def _delete_proxy_for_source(path: Path) -> bool:
    """Delete only the computed sibling proxy for ``path``."""
    source = Path(path)
    proxy = _proxy_path_for(source)
    try:
        proxy_dir = (source.parent / "proxies").resolve()
        resolved = proxy.resolve()
        if resolved.parent != proxy_dir or not resolved.name.endswith("_proxy.mp4"):
            return False
        if resolved.exists():
            resolved.unlink()
            return True
    except Exception:
        return False
    return False


def _generate_proxy(path: Path, force: bool = False) -> "Path | None":
    """Generate a 540p proxy for the given video. Returns proxy path or None on failure."""
    from app.subprocess_utils import hidden_subprocess_kwargs
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        ffmpeg = get_ffmpeg_exe()
    except Exception:
        return None
    proxy_dir = path.parent / "proxies"
    try:
        proxy_dir.mkdir(exist_ok=True)
    except Exception:
        return None
    proxy_path = _proxy_path_for(path)
    if proxy_path.exists():
        if not force and _proxy_state_for(path) == "ready":
            return proxy_path
        if force:
            try:
                if not _delete_proxy_for_source(path):
                    return None
            except Exception:
                return None
    cmd = [
        ffmpeg, "-nostdin", "-v", "error", "-i", str(path),
        "-vf", "scale=-2:540",
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "aac", "-y", str(proxy_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            **hidden_subprocess_kwargs(),
        )
        return proxy_path if result.returncode == 0 else None
    except Exception:
        return None


def _is_high_resolution(path: Path) -> bool:
    """Return True if the video is high-resolution (>1920x1080 or >500 MB)."""
    try:
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > 500:
            return True
    except Exception:
        pass
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        from app.native_worker import native_media_probe

        probe = native_media_probe(path, ffmpeg_path=get_ffmpeg_exe())
        if probe is not None and probe.has_video:
            return probe.width > 1920 or probe.height > 1080
    except Exception:
        pass
    try:
        import cv2 as _cv2
        cap = _cv2.VideoCapture(str(path))
        if cap.isOpened():
            w = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            if w > 1920 or h > 1080:
                return True
    except Exception:
        pass
    return False


def _probe_video_dimensions(path: Path) -> tuple:
    """Return (width, height) of the video, or (0, 0) on failure."""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        from app.native_worker import native_media_probe

        probe = native_media_probe(path, ffmpeg_path=get_ffmpeg_exe())
        if probe is not None and probe.has_video and probe.width > 0 and probe.height > 0:
            return (int(probe.width), int(probe.height))
    except Exception:
        pass
    try:
        import cv2 as _cv2
        cap = _cv2.VideoCapture(str(path))
        if cap.isOpened():
            w = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            return (w, h)
    except Exception:
        pass
    return (0, 0)


class ProxyGeneratorThread(QThread):
    """Background thread: generates a 540p proxy for a video file."""

    done = Signal(str, str)    # original_path, proxy_path
    failed = Signal(str, str)  # original_path, reason
    progress = Signal(int)     # 0-100 (coarse; 10 = started, 100 = done)

    def __init__(self, path: Path, force: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._path = Path(path)
        self._force = bool(force)

    def run(self) -> None:
        self.progress.emit(10)
        proxy = _generate_proxy(self._path, force=self._force)
        if proxy is not None:
            self.progress.emit(100)
            self.done.emit(str(self._path), str(proxy))
        else:
            self.failed.emit(str(self._path), "ffmpeg proxy generation failed")
