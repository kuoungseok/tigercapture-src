"""Live2D runtime warm-up helpers."""
from __future__ import annotations

from typing import Callable


def warm_live2d_runtime() -> tuple[bool, str]:
    try:
        from app.live2d.actor_track import _OffscreenRenderer

        ok = bool(_OffscreenRenderer.instance()._ensure_gl(64, 64))
        return ok, "Live2D runtime ready" if ok else "Live2D GL init returned false"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def schedule_live2d_runtime_warmup(
    delay_ms: int = 900,
    callback: Callable[[bool, str], None] | None = None,
) -> None:
    try:
        from PySide6.QtCore import QTimer
    except Exception:
        ok, message = warm_live2d_runtime()
        if callback:
            callback(ok, message)
        return

    def _run() -> None:
        ok, message = warm_live2d_runtime()
        if callback:
            callback(ok, message)

    QTimer.singleShot(max(0, int(delay_ms)), _run)
