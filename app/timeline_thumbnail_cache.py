from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtGui import QImage, QPixmap


DEFAULT_THUMB_H = 48
MIN_THUMBS = 2


def timeline_thumb_cache_root() -> Path:
    try:
        from app.paths import default_save_dir

        root = default_save_dir() / ".cache" / "timeline_thumbs"
    except Exception:
        root = Path.home() / ".tigercapture" / "timeline_thumbs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def timeline_thumb_cache_dir(path: Path | str, thumb_h: int = DEFAULT_THUMB_H) -> Path | None:
    try:
        p = Path(path)
        st = p.stat()
        material = f"{p.resolve()}|{st.st_mtime_ns}|{st.st_size}|{thumb_h}|v5-frame-tiles"
        key = hashlib.sha1(material.encode("utf-8", "replace")).hexdigest()
        return timeline_thumb_cache_root() / key
    except Exception:
        return None


def load_timeline_thumb_cache(path: Path | str, thumb_h: int = DEFAULT_THUMB_H) -> list[QPixmap] | None:
    cache_dir = timeline_thumb_cache_dir(path, thumb_h)
    if cache_dir is None:
        return None
    try:
        count_file = cache_dir / "count.txt"
        if count_file.exists():
            files = [
                cache_dir / f"{idx:04d}.png"
                for idx in range(
                    int(count_file.read_text(encoding="utf-8").strip())
                )
            ]
        else:
            files = sorted(cache_dir.glob("[0-9][0-9][0-9][0-9].png"))
            if len(files) >= MIN_THUMBS:
                count_file.write_text(str(len(files)), encoding="utf-8")
        if not files:
            return None
        pixmaps: list[QPixmap] = []
        for file_path in files:
            pm = QPixmap(str(file_path))
            if pm.isNull():
                return None
            pixmaps.append(pm)
        return pixmaps
    except Exception:
        return None


def prepare_timeline_thumb_cache(
    path: Path | str, count: int, thumb_h: int = DEFAULT_THUMB_H
) -> None:
    cache_dir = timeline_thumb_cache_dir(path, thumb_h)
    if cache_dir is None:
        return
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "count.txt").write_text(str(int(count)), encoding="utf-8")
    except Exception:
        pass


def store_timeline_thumb_cache(
    path: Path | str, idx: int, image, thumb_h: int = DEFAULT_THUMB_H
) -> None:
    cache_dir = timeline_thumb_cache_dir(path, thumb_h)
    if cache_dir is None:
        return
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        out = str(cache_dir / f"{int(idx):04d}.png")
        if isinstance(image, QImage):
            image.save(out, "PNG")
        elif isinstance(image, QPixmap):
            image.save(out, "PNG")
    except Exception:
        pass


__all__ = [
    "timeline_thumb_cache_root",
    "timeline_thumb_cache_dir",
    "load_timeline_thumb_cache",
    "prepare_timeline_thumb_cache",
    "store_timeline_thumb_cache",
]
