"""Process-isolated actor preview/probe service facade."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class ActorPreviewFrameServer:
    """Small facade for actor frame requests that should not risk the editor process."""

    def probe_frame(
        self,
        kind: str,
        path: str,
        *,
        width: int = 320,
        height: int = 320,
        pos_ms: int = 0,
        timeout_ms: int = 25_000,
    ) -> dict[str, Any]:
        from app.actor_process_probe import run_isolated_actor_probe

        return run_isolated_actor_probe(
            kind,
            path,
            width=width,
            height=height,
            pos_ms=pos_ms,
            timeout_ms=timeout_ms,
        )

    def prerender_preview(
        self,
        kind: str,
        path: str,
        *,
        width: int = 360,
        height: int = 360,
        fps: int = 12,
        duration_ms: int = 1000,
        limit_frames: int | None = 12,
    ) -> dict[str, Any]:
        from app.actor_prerender_cache import prerender_actor_preview

        return prerender_actor_preview(
            kind,
            path,
            width=width,
            height=height,
            fps=fps,
            duration_ms=duration_ms,
            limit_frames=limit_frames,
        )

    def cached_frame(
        self,
        kind: str,
        path: str,
        *,
        width: int,
        height: int,
        local_ms: int = 0,
        duration_ms: int = 1000,
    ):
        from app.actor_prerender_cache import cached_actor_preview_frame

        return cached_actor_preview_frame(
            kind,
            path,
            width=width,
            height=height,
            local_ms=local_ms,
            duration_ms=duration_ms,
        )


def default_actor_preview_frame_server() -> ActorPreviewFrameServer:
    return ActorPreviewFrameServer()


def write_actor_probe_report(path: str | Path, payload: dict[str, Any]) -> Path:
    import json

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return out
