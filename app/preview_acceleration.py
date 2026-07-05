"""Default preview acceleration policy and editor prewarm helpers."""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Callable


def _set_default_env(key: str, value: str) -> None:
    if not os.environ.get(key, "").strip():
        os.environ[key] = str(value)


def configure_preview_acceleration_defaults() -> dict[str, str]:
    """Apply conservative fast-path defaults unless the user overrides them."""
    defaults = {
        "TIGERCAPTURE_PREVIEW_DECODER_AUTO": "1",
        "TIGERCAPTURE_PREVIEW_FRAME_SERVER": "auto",
        "TIGERCAPTURE_CV2_FORWARD_SEEK_WINDOW": "24",
        "TIGERCAPTURE_FRAME_CACHE_LIMIT": "36",
        "TIGERCAPTURE_SPINE_PREVIEW_RENDERER": "gl",
        "TIGERCAPTURE_SPINE_GL_COMPOSITOR": "1",
        "TIGERCAPTURE_SPINE_ZERO_READBACK": "1",
        "TIGERCAPTURE_SPINE_DIRECT_WITH_LIVE2D": "1",
        "TIGERCAPTURE_AR_PBR_GPU_PREVIEW": "1",
    }
    for key, value in defaults.items():
        _set_default_env(key, value)
    return {key: os.environ.get(key, "") for key in defaults}


def _record(stage: str, *, status: str = "ready", detail: str = "", metadata: dict[str, Any] | None = None) -> None:
    try:
        from app.loading_performance import record_loading_event

        record_loading_event(
            "editor.prewarm",
            stage,
            status=status,
            detail=detail,
            metadata=metadata or {},
        )
    except Exception:
        pass


def _prewarm_background() -> None:
    """Import/parser warm-up that is safe outside the Qt GUI thread."""
    _record("background_start", detail="background prewarm started")
    try:
        from app.ar_pbr.hdri_presets import hdri_presets
        from app.ar_pbr.importer import importer_backend_status
        from app.preview_engine_status import preview_engine_status
        from app.spine_editor import spine_json_parser  # noqa: F401

        presets = hdri_presets()
        status = importer_backend_status()
        preview = preview_engine_status()
        _record(
            "background_ready",
            detail="parser/importer/preview status warmed",
            metadata={
                "hdri_count": len(presets),
                "ar_pbr_backends": status.get("available_backends", {}),
                "preview_engine": preview,
            },
        )
    except Exception as exc:
        _record("background_error", status="error", detail=f"{type(exc).__name__}: {exc}")


def schedule_editor_runtime_prewarm(
    *,
    delay_ms: int = 900,
    status_callback: Callable[[str], None] | None = None,
) -> None:
    """Prewarm expensive runtime paths after the editor is visible."""
    configure_preview_acceleration_defaults()
    try:
        from PySide6.QtCore import QTimer
    except Exception:
        _prewarm_background()
        return

    def _start_background() -> None:
        thread = threading.Thread(target=_prewarm_background, name="TigerPreviewPrewarm", daemon=True)
        thread.start()

    def _warm_live2d() -> None:
        try:
            from app.live2d.warmup import warm_live2d_runtime

            ok, msg = warm_live2d_runtime()
            _record("live2d_runtime", status="ready" if ok else "error", detail=msg)
            if status_callback and not ok:
                status_callback(f"Live2D warm-up failed: {msg}")
        except Exception as exc:
            _record("live2d_runtime", status="error", detail=f"{type(exc).__name__}: {exc}")
            if status_callback:
                status_callback(f"Live2D warm-up failed: {exc}")

    QTimer.singleShot(max(0, int(delay_ms)), _start_background)
    QTimer.singleShot(max(0, int(delay_ms) + 250), _warm_live2d)


def prewarm_ar_pbr_asset_descriptor(path: str | Path, *, max_triangles: int = 120_000) -> dict[str, Any]:
    """Warm the persistent 3D descriptor cache for a model path."""
    try:
        from app.ar_pbr.importer import import_asset
        from app.loading_performance import LoadingTimer

        timer = LoadingTimer("ar_pbr.prewarm", path)
        descriptor, diagnostics = import_asset(
            path,
            settings={"max_triangles_per_geometry": max(100, int(max_triangles))},
        )
        timer.mark(
            "descriptor_ready",
            status="ready" if bool(diagnostics.get("ok", True)) else "error",
            detail=str(diagnostics.get("backend") or ""),
            metadata={
                "cached": bool(diagnostics.get("cached")),
                "asset_id": descriptor.get("id"),
            },
        )
        return {"ok": bool(diagnostics.get("ok", True)), "descriptor": descriptor, "diagnostics": diagnostics}
    except Exception as exc:
        _record("ar_pbr_prewarm_error", status="error", detail=f"{type(exc).__name__}: {exc}")
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
