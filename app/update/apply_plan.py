"""Build update apply plans for a separate updater process."""
from __future__ import annotations

from dataclasses import dataclass, field
import datetime as _dt
import json
import os
from pathlib import Path
import sys
from typing import Any

from app.paths import runtime_data_dir
from app.update.manifest import UpdateArtifact, UpdateManifest


SCHEMA = "tigerstudio.update_apply_plan.v1"


@dataclass(frozen=True)
class UpdateApplyPlan:
    artifact_path: str
    artifact_sha256: str
    artifact_kind: str
    install_dir: str
    app_exe: str
    target_version: str
    current_version: str = ""
    backup_dir: str = ""
    restart_args: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = field(default_factory=lambda: _dt.datetime.now(_dt.UTC).isoformat())
    schema: str = SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "created_at": self.created_at,
            "artifact_path": self.artifact_path,
            "artifact_sha256": self.artifact_sha256,
            "artifact_kind": self.artifact_kind,
            "install_dir": self.install_dir,
            "app_exe": self.app_exe,
            "target_version": self.target_version,
            "current_version": self.current_version,
            "backup_dir": self.backup_dir,
            "restart_args": list(self.restart_args),
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "UpdateApplyPlan":
        if str(data.get("schema") or "") != SCHEMA:
            raise ValueError("unsupported update apply plan schema")
        return cls(
            artifact_path=str(data.get("artifact_path") or ""),
            artifact_sha256=str(data.get("artifact_sha256") or ""),
            artifact_kind=str(data.get("artifact_kind") or ""),
            install_dir=str(data.get("install_dir") or ""),
            app_exe=str(data.get("app_exe") or "TigerCapture.exe"),
            target_version=str(data.get("target_version") or ""),
            current_version=str(data.get("current_version") or ""),
            backup_dir=str(data.get("backup_dir") or ""),
            restart_args=tuple(str(arg) for arg in data.get("restart_args") or []),
            created_at=str(data.get("created_at") or ""),
            schema=str(data.get("schema") or SCHEMA),
        )


def update_staging_dir() -> Path:
    path = runtime_data_dir() / "updates" / "staging"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def build_apply_plan(
    *,
    artifact_path: str | Path,
    manifest: UpdateManifest,
    artifact: UpdateArtifact,
    install_dir: str | Path | None = None,
    app_exe: str = "TigerCapture.exe",
    current_version: str = "",
    restart_args: list[str] | tuple[str, ...] | None = None,
) -> UpdateApplyPlan:
    target_install_dir = Path(install_dir).resolve() if install_dir is not None else default_install_dir()
    backup_root = update_staging_dir() / "backup"
    backup_dir = backup_root / f"{manifest.version.replace('.', '_')}_{os.getpid()}"
    return UpdateApplyPlan(
        artifact_path=str(Path(artifact_path).resolve()),
        artifact_sha256=artifact.sha256,
        artifact_kind=artifact.kind,
        install_dir=str(target_install_dir),
        app_exe=str(app_exe or "TigerCapture.exe"),
        target_version=manifest.version,
        current_version=str(current_version or ""),
        backup_dir=str(backup_dir),
        restart_args=tuple(str(arg) for arg in (restart_args or [])),
    )


def write_apply_plan(plan: UpdateApplyPlan, path: str | Path | None = None) -> Path:
    target = Path(path) if path is not None else update_staging_dir() / "apply-plan.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def read_apply_plan(path: str | Path) -> UpdateApplyPlan:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("update apply plan JSON must contain an object")
    return UpdateApplyPlan.from_mapping(data)


def updater_command(updater_exe: str | Path, plan_path: str | Path, *, pid: int | None = None) -> list[str]:
    command = [str(updater_exe), "--plan", str(plan_path)]
    if pid is not None and int(pid) > 0:
        command.extend(["--wait-pid", str(int(pid))])
    return command
