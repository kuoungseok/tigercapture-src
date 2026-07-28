"""Project color-management actions shared by UI and automation."""
from __future__ import annotations

from typing import Any, Mapping

from app.color_management import (
    ColorManagementSettings,
    default_color_management,
    validate_color_management,
)
from app.color_ocio import build_ocio_plan, preferred_aces_ocio_uri


class ColorManagementAdapterMixin:
    def project_color_management_get(self) -> dict[str, Any]:
        owner = self.owner
        settings = getattr(owner, "_project_settings", {}) if owner is not None else {}
        cm = ColorManagementSettings.from_dict(
            settings.get("color_management") if isinstance(settings, dict) else None
        )
        return {
            "settings": cm.to_dict(),
            "validation": validate_color_management(cm),
            "ocio": build_ocio_plan(cm).to_dict(),
        }

    def project_color_management_set(
        self,
        *,
        settings: Mapping[str, Any],
        merge: bool = True,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("editor owner is unavailable")
        project = getattr(owner, "_project_settings", None)
        if not isinstance(project, dict):
            project = {}
            owner._project_settings = project
        current = ColorManagementSettings.from_dict(
            project.get("color_management")
        )
        payload = current.to_dict() if merge else default_color_management().to_dict()
        payload.update(dict(settings))
        if (
            not str(payload.get("ocio_config_path", "") or "")
            and (
                str(payload.get("working_space", "")) in {"acescg", "acescct"}
                or str(payload.get("view_transform", "")) in {"aces", "aces-1.3"}
            )
        ):
            payload["ocio_config_path"] = preferred_aces_ocio_uri()
        cm = ColorManagementSettings.from_dict(payload)
        validation = validate_color_management(cm)
        if validation["errors"]:
            raise ValueError("; ".join(validation["errors"]))
        project["color_management"] = cm.to_dict()
        player = getattr(owner, "_player", None)
        if player is not None and hasattr(player, "set_project_settings"):
            player.set_project_settings(project)
        if player is not None and hasattr(player, "refresh_current_frame"):
            player.refresh_current_frame()
        register = getattr(owner, "_register_change", None)
        if callable(register):
            register("project color management")
        return {
            "changed": cm.to_dict() != current.to_dict(),
            "settings": cm.to_dict(),
            "validation": validation,
            "ocio": build_ocio_plan(cm).to_dict(),
        }


__all__ = ["ColorManagementAdapterMixin"]
