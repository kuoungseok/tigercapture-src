"""Shared media/drop asset classification helpers.

Keep QMimeData path parsing and asset-family routing out of the large editor
window so Media Pool, timeline rows, and automation can share one contract.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.audio_tracks import is_audio_path, is_video_path
from app.image_media import is_image_path


VRM_AVATAR_MIME_TYPE = "application/x-tigerstudio-vrm-avatar"
MEDIA_POOL_ITEM_MIME_TYPE = "application/x-tigercapture-media-pool-item"


def mime_url_paths(mime: Any) -> list[Path]:
    if mime is None:
        return []
    paths: list[Path] = []
    try:
        if mime.hasFormat(MEDIA_POOL_ITEM_MIME_TYPE):
            raw = bytes(mime.data(MEDIA_POOL_ITEM_MIME_TYPE)).decode("utf-8", errors="ignore")
            for line in raw.splitlines():
                path = Path(line.strip())
                if str(path):
                    paths.append(path)
    except Exception:
        pass
    try:
        if not mime.hasUrls():
            return paths
    except Exception:
        return paths
    try:
        urls = list(mime.urls())
    except Exception:
        return paths
    for url in urls:
        try:
            path = Path(url.toLocalFile())
        except Exception:
            continue
        if str(path):
            paths.append(path)
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path)
        if key and key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def ar_pbr_paths_from_mime(mime: Any) -> list[Path]:
    try:
        from app.ar_pbr.project_tracks import is_ar_pbr_asset_path
    except Exception:
        return []
    paths: list[Path] = []
    for path in mime_url_paths(mime):
        if path.suffix.casefold() == ".vrm":
            continue
        if is_ar_pbr_asset_path(path):
            paths.append(path)
    return paths


def vrm_avatar_paths_from_mime(mime: Any) -> list[Path]:
    if mime is None:
        return []
    paths: list[Path] = []
    try:
        if mime.hasFormat(VRM_AVATAR_MIME_TYPE):
            raw = bytes(mime.data(VRM_AVATAR_MIME_TYPE)).decode("utf-8", errors="ignore")
            for line in raw.splitlines():
                path = Path(line.strip())
                if str(path) and path.suffix.casefold() == ".vrm":
                    paths.append(path)
    except Exception:
        pass
    for path in mime_url_paths(mime):
        if path.suffix.casefold() == ".vrm":
            paths.append(path)
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path)
        if key and key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def mmd_paths_from_mime(mime: Any) -> list[Path]:
    try:
        from app.mmd.project_tracks import mmd_paths_from_mime as _mmd_paths_from_mime
    except Exception:
        return []
    return _mmd_paths_from_mime(mime)


def timeline_media_paths_from_mime(mime: Any) -> list[Path]:
    return [
        path for path in mime_url_paths(mime)
        if is_video_path(path) or is_audio_path(path) or is_image_path(path)
    ]


def performance_source_paths_from_mime(
    mime: Any,
    marks_performance_source: Callable[[Path], bool] | None = None,
) -> list[Path]:
    if mime is None:
        return []
    try:
        from app.vtuber.performance_source import PERFORMANCE_SOURCE_MIME_TYPE

        mime_marks_perf = mime.hasFormat(PERFORMANCE_SOURCE_MIME_TYPE)
    except Exception:
        mime_marks_perf = False
    paths: list[Path] = []
    for path in mime_url_paths(mime):
        if not is_video_path(path):
            continue
        pool_marks_perf = False
        if marks_performance_source is not None:
            try:
                pool_marks_perf = bool(marks_performance_source(path))
            except Exception:
                pool_marks_perf = False
        if mime_marks_perf or pool_marks_perf:
            paths.append(path)
    return paths
