from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRUE_VALUES = {"1", "true", "yes", "on", "dev", "developer"}
DEV_ENV_VARS = (
    "TIGERCAPTURE_REVIEW_AUTOMATION",
    "TIGERCAPTURE_DEV_TOOLS",
    "TIGERCAPTURE_DEVELOPER",
)


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUE_VALUES


def review_automation_dev_enabled(project_root: str | Path = ROOT) -> bool:
    if any(_truthy_env(name) for name in DEV_ENV_VARS):
        return True
    if getattr(sys, "frozen", False):
        return False
    root = Path(project_root)
    return (root / ".git").exists() and (root / "tools" / "review_automation_launcher.py").exists()


def require_review_automation_dev(project_root: str | Path = ROOT) -> None:
    if review_automation_dev_enabled(project_root):
        return
    raise PermissionError(
        "Review automation is a developer-only tool. "
        "Run it from the source checkout or set TIGERCAPTURE_REVIEW_AUTOMATION=1."
    )

