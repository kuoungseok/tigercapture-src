"""AR/PBR action adapter helpers.

The public mixin stays here for legacy imports; implementation lives in focused
modules so preview/depth/gizmo changes do not pile back into one adapter file.
"""
from __future__ import annotations

from app.actions.editor_adapter_ar_pbr_depth import ArPbrDepthAdapterMixin
from app.actions.editor_adapter_ar_pbr_gizmo import ArPbrGizmoAdapterMixin
from app.actions.editor_adapter_ar_pbr_preview import ArPbrPreviewAdapterMixin
from app.actions.editor_adapter_ar_pbr_settings import ArPbrSettingsAdapterMixin


class ArPbrAdapterMixin(
    ArPbrDepthAdapterMixin,
    ArPbrPreviewAdapterMixin,
    ArPbrSettingsAdapterMixin,
    ArPbrGizmoAdapterMixin,
):
    """Facade for AR/PBR action adapter methods."""

    pass
