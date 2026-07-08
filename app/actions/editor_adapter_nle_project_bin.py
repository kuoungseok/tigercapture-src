"""Project-bin adapter methods for Python Actions."""
from __future__ import annotations

from typing import Any


class NleProjectBinAdapterMixin:
    """Adapter methods for project-bin, conform, proxy, and relink workbench state."""

    def project_bin_workbench(self) -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_workbench

        return build_project_bin_workbench(self.snapshot(media_limit=1000))

    def project_bin_batch_plan(self, *, operation: str = "all") -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_batch_plan

        return build_project_bin_batch_plan(self.snapshot(media_limit=1000), operation=operation)

    def project_bin_conform_report(self) -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_conform_report

        return build_project_bin_conform_report(self.snapshot(media_limit=1000))

    def project_bin_proxy_plan(self, *, target: str = "timeline") -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_proxy_plan

        return build_project_bin_proxy_plan(self.snapshot(media_limit=1000), target=target)

    def project_bin_proxy_health(self, *, target: str = "timeline") -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_proxy_health_board

        return build_project_bin_proxy_health_board(self.snapshot(media_limit=1000), target=target)

    def project_bin_review_board(self) -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_review_board

        return build_project_bin_review_board(self.snapshot(media_limit=1000))

    def project_bin_offline_browser(self) -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_offline_browser

        return build_project_bin_offline_browser(self.snapshot(media_limit=1000))

    def project_bin_relink_candidate_board(self) -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_relink_candidate_board

        return build_project_bin_relink_candidate_board(self.snapshot(media_limit=1000))

    def project_bin_proxy_regeneration_board(self, *, target: str = "timeline") -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_proxy_regeneration_board

        return build_project_bin_proxy_regeneration_board(self.snapshot(media_limit=1000), target=target)

    def project_bin_proxy_conflict_board(self, *, target: str = "timeline") -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_proxy_conflict_board

        return build_project_bin_proxy_conflict_board(self.snapshot(media_limit=1000), target=target)

    def project_bin_search_filter_model(
        self,
        *,
        query: str = "",
        kind: str = "all",
        bin_name: str = "",
        proxy_state: str = "all",
        offline: str = "all",
    ) -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_search_filter_model

        return build_project_bin_search_filter_model(
            self.snapshot(media_limit=1000),
            query=query,
            kind=kind,
            bin_name=bin_name,
            proxy_state=proxy_state,
            offline=offline,
        )


__all__ = ["NleProjectBinAdapterMixin"]
