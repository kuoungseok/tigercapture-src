from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def default_save_dir() -> Path:
    """Captures live in ``~/Videos/TigerCapture``. Pre-rename users have
    their captures in ``~/Videos/Bitdam`` (the previous brand name); on
    first launch after the rename we move that folder over so no
    captures are orphaned. The migration runs once — once the new
    folder exists, the legacy name is no longer consulted."""
    base = Path.home() / "Videos" / "TigerCapture"
    if not base.exists():
        legacy = Path.home() / "Videos" / "Bitdam"
        if legacy.exists() and legacy.is_dir():
            try:
                legacy.rename(base)
            except OSError:
                # Fall back to creating the new folder; user can move
                # files manually if the rename failed (e.g. cross-drive).
                base.mkdir(parents=True, exist_ok=True)
        else:
            base.mkdir(parents=True, exist_ok=True)
    else:
        base.mkdir(parents=True, exist_ok=True)
    return base


def open_in_explorer(path: Path) -> None:
    """Open a location in the OS file explorer.

    - If ``path`` is a file: opens its containing folder and selects the file.
    - If ``path`` is a directory: opens that directory.
    - If ``path`` does not exist: creates parent folders and opens the parent.
    """
    if path.is_file():
        _reveal_file(path)
        return
    if path.is_dir():
        os.startfile(str(path))
        return
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    os.startfile(str(parent))


def _reveal_file(file_path: Path) -> None:
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["explorer", f"/select,{file_path}"],
                check=False,
            )
            return
        except Exception:
            pass
    os.startfile(str(file_path.parent))
