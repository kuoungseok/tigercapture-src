from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


SUPPORTED_SUFFIXES: set[str] = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webp"}


@dataclass(frozen=True)
class RecentCapture:
    path: Path
    size_bytes: int
    mtime: float

    @property
    def kind(self) -> str:
        s = self.path.suffix.lower()
        if s == ".gif":
            return "gif"
        if s in {".mp4", ".webm", ".mov"}:
            return "video"
        return "image"


def list_recent(folder: Path, limit: int = 24) -> list[RecentCapture]:
    if not folder.exists():
        return []
    entries: list[RecentCapture] = []
    for child in folder.iterdir():
        if not child.is_file():
            continue
        if child.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            stat = child.stat()
        except OSError:
            continue
        entries.append(RecentCapture(child, stat.st_size, stat.st_mtime))
    entries.sort(key=lambda e: e.mtime, reverse=True)
    return entries[:limit]


def load_thumbnail(capture: RecentCapture, size: tuple[int, int]) -> Image.Image | None:
    """Load a thumbnail for the given capture.

    - image/gif: use PIL (for gif, returns first frame)
    - video: returns None (caller shows placeholder)
    """
    try:
        if capture.kind == "video":
            return None
        with Image.open(capture.path) as src:
            if capture.kind == "gif":
                try:
                    src.seek(0)
                except EOFError:
                    pass
            img = src.convert("RGB")
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return img.copy()
    except Exception:
        return None


def format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"
