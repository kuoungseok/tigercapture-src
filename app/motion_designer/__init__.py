"""Qt-free public contracts for Tiger Studio Motion Designer."""

from .contracts import (
    Bounds,
    MotionCommand,
    MotionCompositionLike,
    PreviewQuality,
    SourceAdapter,
    SourceFrame,
    Viewport,
)
from .schema import AnimatedProperty, Keyframe, MotionComposition, MotionLayer, MotionTransform, SourceRef

__all__ = [
    "Bounds",
    "MotionCommand",
    "MotionCompositionLike",
    "PreviewQuality",
    "SourceAdapter",
    "SourceFrame",
    "Viewport",
    "AnimatedProperty",
    "Keyframe",
    "MotionComposition",
    "MotionLayer",
    "MotionTransform",
    "SourceRef",
]
