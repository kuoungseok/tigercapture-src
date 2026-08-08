"""Runtime defaults for TigerCapture update checks and updater launch."""
from __future__ import annotations

import os
from pathlib import Path
import sys


DEFAULT_STABLE_MANIFEST_URL = (
    "https://github.com/kuoungseok/tigercapture/releases/latest/download/latest.json"
)
UPDATE_MANIFEST_URL_ENV = "TIGERCAPTURE_UPDATE_MANIFEST_URL"
UPDATER_EXE_NAME = "TigerCaptureUpdater.exe"


def default_manifest_source() -> str:
    """Return the manifest source used by packaged builds unless overridden."""
    return (
        str(os.environ.get(UPDATE_MANIFEST_URL_ENV) or "").strip()
        or DEFAULT_STABLE_MANIFEST_URL
    )


def source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def source_updater_script() -> Path:
    return source_root() / "tools" / "tigercapture_updater.py"


def bundled_updater_path() -> Path:
    """Find the updater next to the frozen app, or in local build output."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().with_name(UPDATER_EXE_NAME))
    candidates.extend(
        [
            Path.cwd().resolve() / UPDATER_EXE_NAME,
            source_root() / "dist" / "TigerCapture" / UPDATER_EXE_NAME,
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0] if candidates else source_root() / UPDATER_EXE_NAME


def default_updater_command(plan_path: str | Path, *, pid: int | None = None) -> list[str]:
    """Build a command for the packaged updater, falling back to source Python."""
    updater = bundled_updater_path()
    if updater.is_file():
        command = [str(updater), "--plan", str(plan_path)]
    else:
        command = [sys.executable, str(source_updater_script()), "--plan", str(plan_path)]
    if pid is not None and int(pid) > 0:
        command.extend(["--wait-pid", str(int(pid))])
    return command
