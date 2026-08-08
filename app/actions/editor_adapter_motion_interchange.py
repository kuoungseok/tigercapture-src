"""Limited, preflighted Motion interchange actions."""
from __future__ import annotations

from typing import Any

from app.motion_designer.interchange import (
    export_interchange, list_interchange_formats, preflight_interchange,
)


class MotionInterchangeAdapterMixin:
    def motion_interchange_list(self) -> dict[str, Any]:
        rows = list_interchange_formats()
        return {"count": len(rows), "formats": rows}

    def motion_interchange_preflight(self, *, composition_id: str, format_id: str,
                                     time_ms: float = 0.0) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return preflight_interchange(composition, format_id, time_ms=time_ms)

    def motion_interchange_export(self, *, composition_id: str, format_id: str,
                                  output_path: str, time_ms: float = 0.0) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return export_interchange(composition, format_id, output_path, time_ms=time_ms)


__all__ = ["MotionInterchangeAdapterMixin"]
