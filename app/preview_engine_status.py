"""Preview engine capability/status snapshot."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def preview_engine_status() -> dict[str, Any]:
    """Return a compact, serializable preview-engine status report."""
    try:
        from app.preview_acceleration import configure_preview_acceleration_defaults

        acceleration_defaults = configure_preview_acceleration_defaults()
    except Exception:
        acceleration_defaults = {}
    status: dict[str, Any] = {
        "acceleration_defaults": acceleration_defaults,
        "preview_height": os.environ.get("TIGERCAPTURE_PREVIEW_HEIGHT", "auto"),
        "decoder_auto": os.environ.get("TIGERCAPTURE_PREVIEW_DECODER_AUTO", ""),
        "frame_server": os.environ.get("TIGERCAPTURE_PREVIEW_FRAME_SERVER", ""),
        "qimage_mode": os.environ.get("TIGERCAPTURE_PREVIEW_QIMAGE", "auto"),
        "hw_decode": os.environ.get("TIGERCAPTURE_ENABLE_HW_DECODE", ""),
        "cv2_forward_seek_window": os.environ.get("TIGERCAPTURE_CV2_FORWARD_SEEK_WINDOW", "0"),
        "frame_cache_limit": os.environ.get("TIGERCAPTURE_FRAME_CACHE_LIMIT", "24"),
        "ar_pbr_gpu_preview": os.environ.get("TIGERCAPTURE_AR_PBR_GPU_PREVIEW", "1"),
        "filter_chroma_batch": (
            os.environ.get("TIGERCAPTURE_DISABLE_FILTER_CHROMA_BATCH", "").strip().lower()
            not in {"1", "true", "yes", "on"}
        ),
        "shader_clip_fx": os.environ.get("TIGERCAPTURE_SHADER_CLIP_FX", "1"),
        "spine_renderer": os.environ.get("TIGERCAPTURE_SPINE_PREVIEW_RENDERER", "gl"),
        "spine_gl_compositor": os.environ.get("TIGERCAPTURE_SPINE_GL_COMPOSITOR", "1"),
        "spine_array_compositor": os.environ.get("TIGERCAPTURE_SPINE_ARRAY_COMPOSITOR", ""),
        "spine_zero_readback": os.environ.get("TIGERCAPTURE_SPINE_ZERO_READBACK", "1"),
        "spine_direct_with_live2d": os.environ.get("TIGERCAPTURE_SPINE_DIRECT_WITH_LIVE2D", "1"),
        "spine_preview_scale": os.environ.get("TIGERCAPTURE_SPINE_PREVIEW_SCALE", "0.5"),
        "spine_playback_preview_scale": os.environ.get("TIGERCAPTURE_SPINE_PLAYBACK_PREVIEW_SCALE", "0.375"),
        "spine_complex_preview_scale": os.environ.get("TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_SCALE", "0.25"),
        "spine_preview_fps": os.environ.get("TIGERCAPTURE_SPINE_PREVIEW_FPS", "24"),
        "spine_complex_preview_fps": os.environ.get("TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_FPS", "12"),
        "spine_complex_threshold": os.environ.get("TIGERCAPTURE_SPINE_COMPLEX_THRESHOLD", "900"),
    }
    try:
        from app.native_worker import get_native_worker_capabilities

        caps = get_native_worker_capabilities()
        status["native_worker"] = caps.__dict__ if caps is not None else None
    except Exception as exc:
        status["native_worker"] = {"error": type(exc).__name__}
    try:
        from app.video_decoder import (
            _decoder_choice_cache_path,
            _frame_server_preview_height_hint,
            _preview_performance_policy_enabled,
        )

        cache_path = _decoder_choice_cache_path()
        status["decoder_choice_cache"] = str(cache_path) if cache_path else ""
        status["decoder_choice_cache_exists"] = bool(
            cache_path and Path(cache_path).exists()
        )
        status["frame_server_preview_height_hint"] = _frame_server_preview_height_hint(None)
        status["preview_performance_policy"] = {
            "schema": "tigercapture.preview.performance_policy.v1",
            "enabled": _preview_performance_policy_enabled(),
            "disable_env": os.environ.get("TIGERCAPTURE_DISABLE_PREVIEW_PERFORMANCE_POLICY", ""),
            "quality_modes": ["auto", "performance", "quality"],
            "auto_proxy_generation": (
                os.environ.get("TIGERCAPTURE_DISABLE_AUTO_PROXY_GENERATION", "").strip().lower()
                not in {"1", "true", "yes", "on"}
            ),
        }
    except Exception:
        status["decoder_choice_cache"] = ""
        status["decoder_choice_cache_exists"] = False
        status["frame_server_preview_height_hint"] = None
        status["preview_performance_policy"] = {
            "schema": "tigercapture.preview.performance_policy.v1",
            "enabled": False,
            "error": "unavailable",
        }
    return status
