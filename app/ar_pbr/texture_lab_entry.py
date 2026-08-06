"""Shared window entry for image-to-PBR Texture Lab surfaces."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def open_texture_lab_window(owner: Any, image_path: str | Path):
    path = Path(image_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(str(path))

    from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow

    windows = getattr(owner, "_ar_pbr_texture_lab_windows", None)
    if not isinstance(windows, list):
        windows = []
        setattr(owner, "_ar_pbr_texture_lab_windows", windows)
    for window in reversed(windows):
        try:
            existing = Path(str(window.image_path)).expanduser().resolve()
            if existing != path:
                continue
            window.show()
            window.raise_()
            window.activateWindow()
            return window
        except RuntimeError:
            continue

    window = ArPbrTextureMapLabWindow(path, owner)
    windows.append(window)

    def forget(*_args, target=window) -> None:
        current = getattr(owner, "_ar_pbr_texture_lab_windows", [])
        setattr(owner, "_ar_pbr_texture_lab_windows", [item for item in current if item is not target])

    window.destroyed.connect(forget)
    window.show()
    window.raise_()
    window.activateWindow()
    return window
