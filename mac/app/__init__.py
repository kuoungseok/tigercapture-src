"""macOS overlay of the `app` package.

This file turns `mac/app/` into a namespace-package overlay: Python
resolves names against `mac/app/` first, then falls through to the
original `app/` at the repository root. Only Windows-specific modules
(`recorder`, `foreground_tracker`, `quick_paste`, `cursor_overlay`,
`paths`) are shadowed here; everything else — `controller`,
`main_window`, `gif_editor_window`, etc. — continues to load from the
shared cross-platform codebase.

Entry point: `mac/main.py` prepends `mac/` to `sys.path` so that
`import app` picks up this package.
"""
from __future__ import annotations

import os

_here = os.path.dirname(os.path.abspath(__file__))
_root_app = os.path.normpath(os.path.join(_here, "..", "..", "app"))

if os.path.isdir(_root_app) and _root_app not in __path__:
    __path__.append(_root_app)
