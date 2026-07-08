"""Project-bin action registration helpers."""
from __future__ import annotations

from typing import Any

from app.actions.result import ok_result
from app.actions.schema import ActionSpec, schema_object


def register_project_bin_actions(registry: Any) -> None:
    """Register project-bin, conform, proxy, offline-media, and relink actions."""

    adapter = registry.adapter
    registry.register(
        ActionSpec(
            "project_bin.workbench",
            "Return project-bin, conform, proxy, offline-media, and relink readiness state.",
            "project_bin",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("project_bin.workbench", adapter.project_bin_workbench()),
    )
    registry.register(
        ActionSpec(
            "project_bin.batch_plan",
            "Return a read-only batch plan for relink, proxy refresh, and conform checks.",
            "project_bin",
            params_schema=schema_object(
                {
                    "operation": {
                        "type": "string",
                        "enum": ["all", "relink", "offline", "proxy", "proxy_refresh", "conform", "duplicates"],
                    }
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "project_bin.batch_plan",
            adapter.project_bin_batch_plan(operation=str(params.get("operation") or "all")),
        ),
    )
    registry.register(
        ActionSpec(
            "project_bin.conform_report",
            "Return timeline-to-media-pool conform diagnostics for clip source matching and relink review.",
            "project_bin",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("project_bin.conform_report", adapter.project_bin_conform_report()),
    )
    registry.register(
        ActionSpec(
            "project_bin.proxy_plan",
            "Return proxy readiness, preview policy, usable proxies, and regeneration queue.",
            "project_bin",
            params_schema=schema_object(
                {"target": {"type": "string", "enum": ["timeline", "preview", "export", "all"]}},
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "project_bin.proxy_plan",
            adapter.project_bin_proxy_plan(target=str(params.get("target") or "timeline")),
        ),
    )
    registry.register(
        ActionSpec(
            "project_bin.proxy_health",
            "Return product-facing proxy health cards, queue status, and safe regeneration command state.",
            "project_bin",
            params_schema=schema_object(
                {"target": {"type": "string", "enum": ["timeline", "preview", "export", "all"]}},
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "project_bin.proxy_health",
            adapter.project_bin_proxy_health(target=str(params.get("target") or "timeline")),
        ),
    )
    registry.register(
        ActionSpec(
            "project_bin.review_board",
            "Return a UI-ready project-bin review board combining bins, conform issues, proxy queue, and batch operations.",
            "project_bin",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("project_bin.review_board", adapter.project_bin_review_board()),
    )
    registry.register(
        ActionSpec(
            "project_bin.offline_browser",
            "Return a UI-ready offline/missing media browser with relink queue, ambiguous matches, and manual review commands.",
            "project_bin",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("project_bin.offline_browser", adapter.project_bin_offline_browser()),
    )
    registry.register(
        ActionSpec(
            "project_bin.relink_candidate_board",
            "Return file-by-file relink candidate choices for exact, name-only, ambiguous, missing, and offline sources.",
            "project_bin",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "project_bin.relink_candidate_board",
            adapter.project_bin_relink_candidate_board(),
        ),
    )
    registry.register(
        ActionSpec(
            "project_bin.proxy_regeneration_board",
            "Return a reviewed proxy regeneration board with safe background jobs, blocked offline items, and preview policy.",
            "project_bin",
            params_schema=schema_object(
                {"target": {"type": "string", "enum": ["timeline", "preview", "export", "all"]}},
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "project_bin.proxy_regeneration_board",
            adapter.project_bin_proxy_regeneration_board(target=str(params.get("target") or "timeline")),
        ),
    )
    registry.register(
        ActionSpec(
            "project_bin.proxy_conflict_board",
            "Return proxy regeneration conflicts, duplicate media paths, offline blockers, and safe background job controls.",
            "project_bin",
            params_schema=schema_object(
                {"target": {"type": "string", "enum": ["timeline", "preview", "export", "all"]}},
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "project_bin.proxy_conflict_board",
            adapter.project_bin_proxy_conflict_board(target=str(params.get("target") or "timeline")),
        ),
    )
    registry.register(
        ActionSpec(
            "project_bin.search_filter_model",
            "Return a UI-ready Media Pool search/filter/metadata-column model for large project bins.",
            "project_bin",
            params_schema=schema_object(
                {
                    "query": {"type": "string"},
                    "kind": {"type": "string"},
                    "bin_name": {"type": "string"},
                    "proxy_state": {"type": "string"},
                    "offline": {"type": "string", "enum": ["all", "online", "offline"]},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "project_bin.search_filter_model",
            adapter.project_bin_search_filter_model(
                query=str(params.get("query") or ""),
                kind=str(params.get("kind") or "all"),
                bin_name=str(params.get("bin_name") or ""),
                proxy_state=str(params.get("proxy_state") or "all"),
                offline=str(params.get("offline") or "all"),
            ),
        ),
    )


__all__ = ["register_project_bin_actions"]
