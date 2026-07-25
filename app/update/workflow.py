"""App-facing update preparation workflow."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.update.apply_plan import build_apply_plan, updater_command, write_apply_plan
from app.update.checker import read_manifest_source
from app.update.current import current_app_version, current_update_channel
from app.update.downloader import download_artifact
from app.update.manifest import DEFAULT_KIND, DEFAULT_PLATFORM, evaluate_manifest, manifest_from_json
from app.update.runtime import default_manifest_source, default_updater_command
from app.update.verifier import verify_artifact_file


def prepare_update_from_manifest(
    source: str | Path,
    *,
    current_version: str | None = None,
    channel: str | None = None,
    platform: str = DEFAULT_PLATFORM,
    kind: str | None = DEFAULT_KIND,
    install_dir: str | Path | None = None,
    app_exe: str = "TigerCapture.exe",
    cache_dir: str | Path | None = None,
    plan_path: str | Path | None = None,
    updater_exe: str | Path | None = None,
    restart_args: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    manifest = manifest_from_json(read_manifest_source(source))
    check = evaluate_manifest(
        manifest,
        current_version=current_version or current_app_version(),
        channel=channel or current_update_channel(),
        platform=platform,
        kind=kind,
    )
    if not check.available or check.artifact is None:
        return {"ok": False, "stage": "check", "check": check.to_dict()}
    download = download_artifact(check.artifact, cache_dir=cache_dir)
    integrity = verify_artifact_file(download.path, check.artifact)
    if not bool(integrity["ok"]):
        return {
            "ok": False,
            "stage": "verify",
            "check": check.to_dict(),
            "download": download.to_dict(),
            "integrity": integrity,
        }
    plan = build_apply_plan(
        artifact_path=download.path,
        manifest=manifest,
        artifact=check.artifact,
        install_dir=install_dir,
        app_exe=app_exe,
        current_version=current_version or current_app_version(),
        restart_args=restart_args,
    )
    written_plan = write_apply_plan(plan, plan_path)
    command = (
        updater_command(updater_exe, written_plan, pid=os.getpid())
        if updater_exe is not None
        else default_updater_command(written_plan, pid=os.getpid())
    )
    return {
        "ok": True,
        "stage": "prepared",
        "check": check.to_dict(),
        "download": download.to_dict(),
        "integrity": integrity,
        "plan_path": str(written_plan),
        "updater_command": command,
    }


def prepare_update_from_default_manifest(**kwargs: Any) -> dict[str, Any]:
    """Prepare an update using the packaged default manifest URL."""
    return prepare_update_from_manifest(default_manifest_source(), **kwargs)
