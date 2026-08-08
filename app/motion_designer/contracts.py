"""Stable, renderer-neutral contracts for Motion Designer.

This module deliberately has no Qt, OpenGL, editor-window, or project-I/O
dependency. UI, source adapters, and renderers may depend on these contracts;
the contracts must never depend on those layers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Hashable, Mapping, Protocol, runtime_checkable


class PreviewQuality(str, Enum):
    AUTO = "auto"
    FULL = "full"
    HALF = "half"
    QUARTER = "quarter"


@dataclass(frozen=True, slots=True)
class Viewport:
    width: int
    height: int
    pixel_ratio: float = 1.0

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("viewport dimensions must be positive")
        if self.pixel_ratio <= 0:
            raise ValueError("viewport pixel_ratio must be positive")


@dataclass(frozen=True, slots=True)
class Bounds:
    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError("bounds dimensions cannot be negative")


@dataclass(frozen=True, slots=True)
class SourceFrame:
    """One evaluated layer source ready for the compositor.

    ``rgba`` and ``depth`` remain opaque so adapters can hand over a CPU frame,
    a texture handle, or a future shared-surface object without changing the
    evaluator contract.
    """

    rgba: Any
    depth: Any | None = None
    bounds: Bounds = field(default_factory=Bounds)
    premultiplied_alpha: bool = True
    color_space: str = "srgb"
    cache_key: Hashable | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.color_space or "").strip():
            raise ValueError("SourceFrame color_space is required")
        object.__setattr__(self, "diagnostics", dict(self.diagnostics or {}))


@runtime_checkable
class SourceAdapter(Protocol):
    """Evaluate one source at a deterministic composition time."""

    def evaluate(
        self,
        time_ms: int,
        quality: PreviewQuality,
        viewport: Viewport,
    ) -> SourceFrame: ...


@runtime_checkable
class MotionCompositionLike(Protocol):
    """Minimum composition surface shared by services and renderers."""

    id: str
    name: str
    duration_ms: int
    fps: float
    revision: int


@dataclass(frozen=True, slots=True)
class MotionCommand:
    """Stable mutation request used by both UI and automation adapters."""

    id: str
    operation: str
    composition_id: str
    params: Mapping[str, Any] = field(default_factory=dict)
    expected_revision: int | None = None
    transaction_id: str = ""

    def __post_init__(self) -> None:
        if not str(self.id or "").strip():
            raise ValueError("MotionCommand id is required")
        if not str(self.operation or "").strip():
            raise ValueError("MotionCommand operation is required")
        if not str(self.composition_id or "").strip():
            raise ValueError("MotionCommand composition_id is required")
        if self.expected_revision is not None and self.expected_revision < 0:
            raise ValueError("expected_revision cannot be negative")
        object.__setattr__(self, "params", dict(self.params or {}))
