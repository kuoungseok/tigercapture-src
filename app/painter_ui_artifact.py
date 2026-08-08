"""Validated desktop opening for generated Painter UI artifacts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


ARTIFACT_SCHEMA = "tigerstudio.painter.ui.delivery_artifact.v1"


def resolve_painter_ui_artifact(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise ValueError(f"Painter UI delivery artifact not found: {path}")
    if target.is_file() and target.suffix.casefold() not in {
        ".html",
        ".json",
        ".png",
        ".webp",
        ".svg",
        ".txt",
    }:
        raise ValueError(
            f"Unsupported Painter UI delivery artifact type: {target.suffix}"
        )
    return {
        "schema": ARTIFACT_SCHEMA,
        "path": str(target),
        "kind": (
            "directory"
            if target.is_dir()
            else target.suffix.casefold().lstrip(".")
        ),
        "bytes": target.stat().st_size if target.is_file() else 0,
        "url": QUrl.fromLocalFile(str(target)).toString(),
    }


def open_painter_ui_artifact(path: str | Path) -> dict[str, Any]:
    report = resolve_painter_ui_artifact(path)
    launched = bool(
        QDesktopServices.openUrl(QUrl.fromLocalFile(report["path"]))
    )
    return {**report, "launched": launched}


__all__ = [
    "ARTIFACT_SCHEMA",
    "open_painter_ui_artifact",
    "resolve_painter_ui_artifact",
]
