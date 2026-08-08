from __future__ import annotations

import os


_TRUTHY = {"1", "true", "yes", "on", "enabled", "allow"}


def _env_truthy(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    return str(value).strip().lower() in _TRUTHY


def capture_to_studio_enabled() -> bool:
    """Whether the lightweight capture launcher may open Tiger Studio.

    The product default is a separated capture app: it can be bundled with
    Studio, but it should not route users into Studio unless the bundle/QA
    process explicitly opts in.
    """
    for name in (
        "TIGERCAPTURE_CAPTURE_TO_STUDIO",
        "TIGERCAPTURE_ALLOW_STUDIO_ENTRY",
        "TIGERSTUDIO_BUNDLED_STUDIO_ENTRY",
    ):
        enabled = _env_truthy(name)
        if enabled is not None:
            return enabled
    return False


def capture_to_studio_policy() -> dict[str, object]:
    return {
        "capture_to_studio_enabled": capture_to_studio_enabled(),
        "default": "blocked",
        "env": [
            "TIGERCAPTURE_CAPTURE_TO_STUDIO",
            "TIGERCAPTURE_ALLOW_STUDIO_ENTRY",
            "TIGERSTUDIO_BUNDLED_STUDIO_ENTRY",
        ],
    }
