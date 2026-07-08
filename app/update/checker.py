"""Load and evaluate update manifests from local paths or HTTPS URLs."""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

from app.update.manifest import DEFAULT_KIND, DEFAULT_PLATFORM, UpdateCheck, evaluate_manifest, manifest_from_json


def read_manifest_source(source: str | Path, *, timeout: float = 15.0) -> str:
    raw = str(source)
    parsed = urlparse(raw)
    if len(parsed.scheme) == 1 and parsed.path:
        return Path(raw).expanduser().read_text(encoding="utf-8")
    if parsed.scheme in {"http", "https"}:
        with urlopen(raw, timeout=float(timeout)) as response:
            return response.read().decode("utf-8")
    if parsed.scheme == "file":
        return _path_from_file_url(parsed.path).read_text(encoding="utf-8")
    return Path(raw).expanduser().read_text(encoding="utf-8")


def _path_from_file_url(path: str) -> Path:
    text = unquote(path)
    if sys.platform == "win32" and len(text) >= 3 and text[0] == "/" and text[2] == ":":
        text = text[1:]
    return Path(text)


def check_for_update(
    source: str | Path,
    *,
    current_version: str,
    channel: str = "stable",
    platform: str = DEFAULT_PLATFORM,
    kind: str | None = DEFAULT_KIND,
    timeout: float = 15.0,
) -> UpdateCheck:
    manifest = manifest_from_json(read_manifest_source(source, timeout=timeout))
    return evaluate_manifest(
        manifest,
        current_version=current_version,
        channel=channel,
        platform=platform,
        kind=kind,
    )


def check_for_update_report(source: str | Path, **kwargs: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "check": check_for_update(source, **kwargs).to_dict()}
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "source": str(source),
        }
