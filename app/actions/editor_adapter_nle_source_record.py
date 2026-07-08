"""Source/Record workbench adapter methods for Python Actions."""
from __future__ import annotations

from typing import Any


class NleSourceRecordAdapterMixin:
    """Adapter methods for Source/Record 3-point editing workbench state."""

    def source_record_workbench(self) -> dict[str, Any]:
        from app.nle_source_record import build_source_record_workbench

        try:
            edit_points_payload = self.edit_points(track_kind="video", include_markers=True)
            edit_points = list(edit_points_payload.get("points") or edit_points_payload.get("edit_points") or [])
        except Exception:
            edit_points = []
        return build_source_record_workbench(
            source_monitor=self.source_monitor_state(),
            record_monitor=self.record_monitor_state(),
            track_targets=self.track_targets(),
            playhead_ms=self._current_playhead_ms(),
            edit_points=edit_points,
        )

    def source_record_edit_decision_preview(self, *, mode: str = "insert") -> dict[str, Any]:
        from app.nle_source_record import build_source_record_edit_decision_preview

        return build_source_record_edit_decision_preview(
            source_monitor=self.source_monitor_state(),
            record_monitor=self.record_monitor_state(),
            track_targets=self.track_targets(),
            playhead_ms=self._current_playhead_ms(),
            mode=mode,
        )

    def source_record_patch_matrix(self) -> dict[str, Any]:
        from app.nle_source_record import build_source_record_patch_matrix

        try:
            edit_points_payload = self.edit_points(track_kind="video", include_markers=True)
            edit_points = list(edit_points_payload.get("points") or edit_points_payload.get("edit_points") or [])
        except Exception:
            edit_points = []
        return build_source_record_patch_matrix(
            source_monitor=self.source_monitor_state(),
            record_monitor=self.record_monitor_state(),
            track_targets=self.track_targets(),
            playhead_ms=self._current_playhead_ms(),
            edit_points=edit_points,
        )

    def source_record_monitor_layout(self) -> dict[str, Any]:
        from app.nle_source_record import build_source_record_monitor_layout

        try:
            edit_points_payload = self.edit_points(track_kind="video", include_markers=True)
            edit_points = list(edit_points_payload.get("points") or edit_points_payload.get("edit_points") or [])
        except Exception:
            edit_points = []
        return build_source_record_monitor_layout(
            source_monitor=self.source_monitor_state(),
            record_monitor=self.record_monitor_state(),
            track_targets=self.track_targets(),
            playhead_ms=self._current_playhead_ms(),
            edit_points=edit_points,
        )

    def source_record_apply_board(self) -> dict[str, Any]:
        from app.nle_source_record import build_source_record_apply_board

        try:
            edit_points_payload = self.edit_points(track_kind="video", include_markers=True)
            edit_points = list(edit_points_payload.get("points") or edit_points_payload.get("edit_points") or [])
        except Exception:
            edit_points = []
        return build_source_record_apply_board(
            source_monitor=self.source_monitor_state(),
            record_monitor=self.record_monitor_state(),
            track_targets=self.track_targets(),
            playhead_ms=self._current_playhead_ms(),
            edit_points=edit_points,
        )

    def source_record_keyboard_overlay(self) -> dict[str, Any]:
        from app.nle_source_record import build_source_record_keyboard_overlay

        try:
            edit_points_payload = self.edit_points(track_kind="video", include_markers=True)
            edit_points = list(edit_points_payload.get("points") or edit_points_payload.get("edit_points") or [])
        except Exception:
            edit_points = []
        return build_source_record_keyboard_overlay(
            source_monitor=self.source_monitor_state(),
            record_monitor=self.record_monitor_state(),
            track_targets=self.track_targets(),
            playhead_ms=self._current_playhead_ms(),
            edit_points=edit_points,
        )


__all__ = ["NleSourceRecordAdapterMixin"]
