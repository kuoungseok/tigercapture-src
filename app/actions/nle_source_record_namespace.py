"""Source/Record workbench action registration helpers."""
from __future__ import annotations

from typing import Any

from app.actions.result import ok_result
from app.actions.schema import ActionSpec, schema_object


def register_source_record_actions(registry: Any) -> None:
    """Register Source/Record 3-point editing workbench actions."""

    adapter = registry.adapter
    registry.register(
        ActionSpec(
            "source_record.workbench",
            "Return UI-ready Source/Record monitor state, patching, command enablement, and edit navigation.",
            "source_record",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("source_record.workbench", adapter.source_record_workbench()),
    )
    registry.register(
        ActionSpec(
            "source_record.edit_decision_preview",
            "Return a reviewed 3-point insert/overwrite decision before mutating the timeline.",
            "source_record",
            params_schema=schema_object({"mode": {"type": "string", "enum": ["insert", "overwrite"]}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "source_record.edit_decision_preview",
            adapter.source_record_edit_decision_preview(mode=str(params.get("mode") or "insert")),
        ),
    )
    registry.register(
        ActionSpec(
            "source_record.patch_matrix",
            "Return Source/Record video/audio patch matrix and insert/overwrite command cards.",
            "source_record",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("source_record.patch_matrix", adapter.source_record_patch_matrix()),
    )
    registry.register(
        ActionSpec(
            "source_record.monitor_layout",
            "Return a product-facing Source/Record two-monitor layout with patch rows, edit cards, and transport hints.",
            "source_record",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("source_record.monitor_layout", adapter.source_record_monitor_layout()),
    )
    registry.register(
        ActionSpec(
            "source_record.apply_board",
            "Return a reviewed Source/Record insert/overwrite apply board with exact action payloads and destructive confirmation hints.",
            "source_record",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("source_record.apply_board", adapter.source_record_apply_board()),
    )
    registry.register(
        ActionSpec(
            "source_record.keyboard_overlay",
            "Return Source/Record keyboard and JKL transport overlay hints for a dedicated two-monitor UI.",
            "source_record",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("source_record.keyboard_overlay", adapter.source_record_keyboard_overlay()),
    )


__all__ = ["register_source_record_actions"]
