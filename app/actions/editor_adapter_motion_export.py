"""Motion color-management and profile export actions."""
from __future__ import annotations

from typing import Any, Mapping

from app.color_ocio import preferred_aces_ocio_uri
from app.motion_designer.color_management import (
    MOTION_COLOR_METADATA_KEY,
    MotionColorSettings,
    settings_from_composition_metadata,
    validate_motion_color_settings,
)
from app.motion_designer.export_pipeline import MotionProfileExporter
from app.motion_designer.export_profiles import (
    ffmpeg_capabilities,
    list_motion_export_profiles,
    preflight_motion_export,
)
from app.motion_designer.schema import MotionComposition


class MotionExportAdapterMixin:
    def motion_color_get(self, *, composition_id: str) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        settings = settings_from_composition_metadata(composition.metadata)
        return {
            "composition_id": composition.id,
            "composition_revision": composition.revision,
            "legacy": MOTION_COLOR_METADATA_KEY not in composition.metadata,
            "report": validate_motion_color_settings(settings),
        }

    def motion_color_set(self, *, composition_id: str, settings: Mapping[str, Any]) -> dict[str, Any]:
        store = self._motion_store()
        composition = store.get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        payload = dict(settings)
        project = dict(payload.get("project") or {})
        if (
            not str(project.get("ocio_config_path", "") or "")
            and (
                str(project.get("working_space", "")) in {"acescg", "acescct"}
                or str(project.get("view_transform", "")) in {"aces", "aces-1.3"}
            )
        ):
            project["ocio_config_path"] = preferred_aces_ocio_uri()
            payload["project"] = project
        color = MotionColorSettings.from_dict(payload)
        report = validate_motion_color_settings(color)
        if not report["ok"]:
            raise ValueError("invalid Motion color settings: " + "; ".join(report["errors"]))
        candidate = MotionComposition.from_dict(composition.to_dict())
        candidate.metadata[MOTION_COLOR_METADATA_KEY] = color.to_dict()
        candidate.metadata.pop("broadcast_cache", None)
        candidate.revision += 1
        store[composition_id] = candidate
        self._motion_sync_owner()
        return {
            "changed": candidate.to_dict() != composition.to_dict(),
            "undo_label": "Set Motion Color Management",
            "composition_id": candidate.id,
            "composition_revision": candidate.revision,
            "cache_invalidated": "broadcast_cache" not in candidate.metadata,
            "report": report,
        }

    def motion_export_profile_list(self) -> dict[str, Any]:
        profiles = list_motion_export_profiles()
        return {"count": len(profiles), "profiles": profiles, "ffmpeg": ffmpeg_capabilities()}

    def motion_export_profile_preflight(self, *, composition_id: str, profile_id: str,
                                        output_path: str = "", fps: float | None = None) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return preflight_motion_export(composition, profile_id, output_path=output_path, fps=fps)

    def motion_export_profile_render(self, *, composition_id: str, profile_id: str,
                                     output_path: str, fps: float | None = None,
                                     time_ms: float = 0.0,
                                     resume: bool = False) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return MotionProfileExporter().export(
            composition, profile_id, output_path, fps=fps, time_ms=time_ms, resume=resume,
        )


__all__ = ["MotionExportAdapterMixin"]
