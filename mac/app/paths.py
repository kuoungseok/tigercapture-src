"""macOS version of app.paths.

Overrides the Windows-only ``os.startfile`` / ``explorer /select,`` logic
with equivalents built on the ``open`` command:

- reveal a file  →  ``open -R <file>``
- open a dir     →  ``open <dir>``
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def default_save_dir() -> Path:
    """Save captures under ~/Movies/TigerCapture on macOS.

    ``~/Videos`` is the Windows convention; ``~/Movies`` is the standard
    user media folder on macOS (it's the one Finder shows in the
    sidebar).
    """
    base = Path.home() / "Movies" / "TigerCapture"
    base.mkdir(parents=True, exist_ok=True)
    return base


def open_in_explorer(path: Path) -> None:
    """Reveal / open a path in Finder.

    - file: opens its containing folder with the file selected
    - directory: opens that directory
    - missing: creates parent folders and opens the parent
    """
    if path.is_file():
        _reveal_file(path)
        return
    if path.is_dir():
        subprocess.run(["open", str(path)], check=False)
        return
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["open", str(parent)], check=False)


def _reveal_file(file_path: Path) -> None:
    try:
        subprocess.run(["open", "-R", str(file_path)], check=False)
    except Exception:
        subprocess.run(["open", str(file_path.parent)], check=False)
