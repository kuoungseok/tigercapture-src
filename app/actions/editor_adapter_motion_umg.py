"""Motion Designer to Unreal UMG action adapter."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.unreal_umg_document import package_motion_composition_for_umg
from app.unreal_umg_plugin import install_project_plugin, plugin_status
from app.unreal_umg_workflow import preflight_umg_project, run_unreal_umg_generation


class MotionUMGAdapterMixin:
    def motion_umg_preflight(
        self,
        *,
        composition_id: str,
        project_path: str,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        result = preflight_umg_project(project_path)
        result["composition_id"] = composition.id
        result["composition_revision"] = composition.revision
        return result

    def motion_umg_package(
        self,
        *,
        composition_id: str,
        output_dir: str,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return package_motion_composition_for_umg(composition, output_dir)

    def motion_umg_plugin_status(self, *, project_path: str) -> dict[str, Any]:
        return plugin_status(project_path).to_dict()

    def motion_umg_plugin_install(self, *, project_path: str) -> dict[str, Any]:
        return install_project_plugin(project_path).to_dict()

    def motion_umg_generate(
        self,
        *,
        composition_id: str,
        project_path: str,
        output_dir: str = "",
        destination_root: str = "/Game/TigerStudio/Generated",
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        packet_root = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else Path(project_path).expanduser().resolve().parent
            / "TigerStudioSourceAssets"
            / composition.id
        )
        packet = package_motion_composition_for_umg(composition, packet_root)
        if not packet["ok"]:
            return packet
        result = run_unreal_umg_generation(
            project_path,
            packet["document_path"],
            destination_root=destination_root,
            timeout_seconds=timeout_seconds,
        )
        result["packet"] = {
            "document_path": packet["document_path"],
            "asset_count": packet["asset_count"],
            "missing": packet["missing"],
        }
        return result


__all__ = ["MotionUMGAdapterMixin"]
