"""TigerCapture update-system primitives.

The app process should check, download, and stage updates. A separate updater
process should apply staged packages after the main app exits.
"""
from __future__ import annotations

from app.update.manifest import (
    UpdateArtifact,
    UpdateCheck,
    UpdateManifest,
    build_manifest,
    compare_versions,
    evaluate_manifest,
    manifest_from_json,
    manifest_to_json,
)
from app.update.current import APP_VERSION, current_app_version, current_update_channel
from app.update.runtime import default_manifest_source, default_updater_command
from app.update.workflow import prepare_update_from_default_manifest, prepare_update_from_manifest

__all__ = [
    "APP_VERSION",
    "UpdateArtifact",
    "UpdateCheck",
    "UpdateManifest",
    "build_manifest",
    "compare_versions",
    "current_app_version",
    "current_update_channel",
    "default_manifest_source",
    "default_updater_command",
    "evaluate_manifest",
    "manifest_from_json",
    "manifest_to_json",
    "prepare_update_from_default_manifest",
    "prepare_update_from_manifest",
]
