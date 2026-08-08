from __future__ import annotations

import copy
import time
import zlib
from pathlib import Path
from typing import Any

from app.audio_tracks import AudioClip, default_effects_state


class SoundEditStateStore:
    """Keeps media-pool sound-edit states separate from timeline clips."""

    def __init__(self) -> None:
        self._media_clips: dict[str, AudioClip] = {}
        self._recent_keys: list[str] = []

    @staticmethod
    def media_key(path: Path | str) -> str:
        try:
            return f"media:{Path(path).expanduser().resolve()}"
        except Exception:
            return f"media:{path}"

    @staticmethod
    def timeline_key(track: Any, clip: Any) -> str:
        return f"timeline:{getattr(track, 'id', 'none')}:{getattr(clip, 'id', 'none')}"

    def touch(self, key: str) -> None:
        if not key:
            return
        try:
            self._recent_keys.remove(key)
        except ValueError:
            pass
        self._recent_keys.insert(0, key)
        del self._recent_keys[64:]

    def media_clip(self, path: Path | str, duration_ms: int = 0) -> AudioClip:
        key = self.media_key(path)
        clip = self._media_clips.get(key)
        if clip is None:
            source = Path(path).expanduser().resolve()
            crc = zlib.crc32(str(source).encode("utf-8", errors="replace")) & 0x7FFFFFFF
            clip = AudioClip(
                id=crc or int(time.time() * 1000) & 0x7FFFFFFF,
                source_path=source,
                duration_ms=max(0, int(duration_ms or 0)),
                trim_start_ms=0,
                trim_end_ms=max(0, int(duration_ms or 0)),
                effects=copy.deepcopy(default_effects_state()),
            )
            self._media_clips[key] = clip
        elif duration_ms and not int(getattr(clip, "duration_ms", 0) or 0):
            clip.duration_ms = max(0, int(duration_ms))
            clip.trim_end_ms = max(0, int(duration_ms))
        self.touch(key)
        return clip

    def recent_keys(self) -> list[str]:
        return list(self._recent_keys)
