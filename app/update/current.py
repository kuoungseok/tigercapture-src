"""Current app version/channel helpers for update checks."""
from __future__ import annotations

import os


APP_VERSION = "1.4.2"
DEFAULT_UPDATE_CHANNEL = "stable"


def current_app_version() -> str:
    return str(os.environ.get("TIGERCAPTURE_VERSION") or APP_VERSION).strip() or APP_VERSION


def current_update_channel() -> str:
    return str(os.environ.get("TIGERCAPTURE_UPDATE_CHANNEL") or DEFAULT_UPDATE_CHANNEL).strip() or DEFAULT_UPDATE_CHANNEL
