"""Read-only AEP inspection actions for Motion Designer."""
from __future__ import annotations

from typing import Any

from app.motion_designer.aep import inspect_aep_file


class MotionAepAdapterMixin:
    def motion_aep_inspect(self, *, path: str, include_tree: bool = False) -> dict[str, Any]:
        return inspect_aep_file(path, include_tree=bool(include_tree))


__all__ = ["MotionAepAdapterMixin"]
