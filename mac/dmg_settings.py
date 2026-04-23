"""dmgbuild settings for GifCam.

Produces a drag-to-Applications DMG whose background is a simple dark
canvas matching the app's chrome. Invoked from mac/build.sh as:

    dmgbuild -s mac/dmg_settings.py -D app=/path/to/GifCam.app \\
        "GifCam 1.3.0" dist/GifCam-1.3.0.dmg
"""
from __future__ import annotations

import os.path

# ``defines`` comes from ``-D app=...`` on the dmgbuild command line.
application = defines.get("app", "dist/GifCam.app")  # type: ignore[name-defined]  # noqa: F821
appname = os.path.basename(application)

# --- disk image ---------------------------------------------------------
format = "UDZO"              # compressed read-only; standard for releases
size = None                  # auto-size to contents

# --- content ------------------------------------------------------------
files = [application]
symlinks = {"Applications": "/Applications"}

# --- window + icon layout ----------------------------------------------
window_rect = ((200, 200), (540, 360))
icon_size = 96
text_size = 13

icon_locations = {
    appname: (150, 160),
    "Applications": (390, 160),
}

# --- optional background (leave unset for default blank) ---------------
# background = "mac/resources/dmg_background.png"
background = "#111315"

# --- Finder niceties ----------------------------------------------------
default_view = "icon-view"
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
show_icon_preview = False
show_item_info = False
arrange_by = None
grid_offset = (0, 0)
grid_spacing = 100
label_pos = "bottom"
