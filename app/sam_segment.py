"""Segment Anything (SAM) integration for click-to-mask rotoscope.

Loads Meta's Segment Anything model on first use; subsequent calls
reuse the cached predictor. SAM is a pip-optional dependency — when
either ``segment_anything`` or the checkpoint file isn't available,
``is_sam_available`` returns False and callers fall back to GrabCut.

Default model: ``vit_b`` (~375 MB). Smallest of the three official
checkpoints, runs on CPU at ~1-2 s/click on a typical desktop. The
heavier ``vit_l`` / ``vit_h`` need GPU to feel snappy.

Checkpoint location: ``<userdata>/sam_vit_b.pth``. Falls back to a
``models/`` directory next to the app for portable installs.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np


_SAM_CHECKPOINT_NAME = "sam_vit_b_01ec64.pth"
_SAM_MODEL_TYPE = "vit_b"

# Module-level cache so we don't re-load the 375 MB checkpoint on
# every click.
_sam_predictor = None
_sam_attempt_failed = False


def _candidate_checkpoint_paths() -> list[Path]:
    """Where to look for the SAM checkpoint. The first existing path
    wins. Order: ``<cwd>/models/``, ``<exe>/models/``, then the
    user-data directory used by the rest of the app."""
    candidates: list[Path] = []
    candidates.append(Path.cwd() / "models" / _SAM_CHECKPOINT_NAME)
    try:
        import sys
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "models" / _SAM_CHECKPOINT_NAME)
        candidates.append(Path(sys.argv[0]).resolve().parent / "models" / _SAM_CHECKPOINT_NAME)
    except Exception:
        pass
    try:
        from app.paths import default_save_dir
        candidates.append(Path(default_save_dir()).parent / "sam" / _SAM_CHECKPOINT_NAME)
    except Exception:
        pass
    return candidates


def is_sam_available() -> bool:
    """Quick probe used by the toolbar fallback path. Returns True
    only when both the ``segment_anything`` module and a usable
    checkpoint are reachable. Side-effect free — no model load."""
    global _sam_attempt_failed
    if _sam_attempt_failed:
        return False
    try:
        import segment_anything  # noqa: F401
    except ImportError:
        return False
    return any(p.is_file() for p in _candidate_checkpoint_paths())


def _get_predictor():
    """Return a singleton ``SamPredictor`` or None when the model
    can't be loaded. The result is cached at module level."""
    global _sam_predictor, _sam_attempt_failed
    if _sam_predictor is not None:
        return _sam_predictor
    if _sam_attempt_failed:
        return None
    try:
        from segment_anything import SamPredictor, sam_model_registry
    except ImportError:
        _sam_attempt_failed = True
        return None
    ckpt: Path | None = None
    for p in _candidate_checkpoint_paths():
        if p.is_file():
            ckpt = p
            break
    if ckpt is None:
        _sam_attempt_failed = True
        return None
    try:
        sam = sam_model_registry[_SAM_MODEL_TYPE](checkpoint=str(ckpt))
        # Pick a device — prefer CUDA when torch reports it, fall
        # back to CPU. Most users on TigerCapture are on Win + CPU
        # so this is the realistic path.
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
        sam.to(device=device)
        _sam_predictor = SamPredictor(sam)
    except Exception:
        _sam_attempt_failed = True
        return None
    return _sam_predictor


def sam_mask_from_point(rgb, nx: float, ny: float):
    """Run SAM with a single foreground click at normalised
    coordinates ``(nx, ny)``. Returns a uint8 H×W mask (255 =
    subject, 0 = background) or ``None`` when SAM isn't ready.

    The predictor is cached, so the *first* click triggers the
    model load (slow — several seconds on CPU); subsequent clicks
    on the same frame reuse the cached image embedding inside
    ``SamPredictor.set_image``. Different frames pay the embedding
    cost again.
    """
    predictor = _get_predictor()
    if predictor is None:
        return None
    h, w = rgb.shape[:2]
    if w <= 0 or h <= 0:
        return None
    try:
        predictor.set_image(rgb)
        x = int(round(max(0.0, min(1.0, nx)) * (w - 1)))
        y = int(round(max(0.0, min(1.0, ny)) * (h - 1)))
        point_coords = np.array([[x, y]])
        point_labels = np.array([1])  # 1 = foreground
        masks, scores, _ = predictor.predict(
            point_coords=point_coords,
            point_labels=point_labels,
            multimask_output=True,
        )
    except Exception:
        return None
    if masks is None or len(masks) == 0:
        return None
    # ``multimask_output=True`` gives 3 candidate masks. Pick the
    # one with the highest IoU score — that's the one SAM is most
    # confident about.
    best_idx = int(np.argmax(scores))
    best = masks[best_idx]
    out = np.where(best, 255, 0).astype(np.uint8)
    return out
