"""NodeGraph design tokens (Phase 2A).

Color/size/font tokens lifted directly from the Workbench Node Graph
spec section 9. Centralised here so painting code in items/ and the
view's grid can read the same values without re-deriving them.
"""
from __future__ import annotations


# All values match section 9.1 of the spec verbatim. The TigerCapture
# elevation system maps L2/L3/L4/L5/L6 to the same hex codes.
NODE_GRAPH_COLORS = {
    # Canvas
    "canvas_bg":            "#121212",   # L2
    "grid_minor":           "#181818",
    "grid_major":           "#1e1e1e",   # L3

    # Node body
    "node_bg_normal":       "#2E2E2E",   # L5
    "node_bg_hover":        "#383838",   # L6
    "node_bg_selected":     "#383838",
    "node_bg_disabled":     "#1E1E1E",
    "node_header_bg":       "#242424",   # L4

    "node_border_normal":   "#333333",
    "node_border_hover":    "#424242",
    "node_border_selected": "#D85A30",   # Tiger Orange — signature
    "node_border_disabled": "#2A2A2A",

    "node_id_color":        "#D85A30",
    "node_label_color":     "#ffffff",

    # IN / OUT special nodes
    "io_node_bg":           "#121212",
    "io_node_border":       "#D85A30",

    # Status bar / toolbar
    "toolbar_bg":           "#242424",
    "statusbar_bg":         "#1E1E1E",
    "statusbar_text":       "#8A8A8A",
}


NODE_GRAPH_SIZES = {
    "node_width":            200,
    "node_height":           140,
    "node_border_radius":    8,
    "node_header_height":    24,

    "thumbnail_width":       160,
    "thumbnail_height":      90,    # 16:9

    "io_width":              130,
    "io_height":             100,
    "io_thumbnail_width":    112,
    "io_thumbnail_height":   63,

    "grid_minor_spacing":    10,
    "grid_major_spacing":    50,

    "canvas_size":           10000,
    "min_zoom":              0.1,
    "max_zoom":              5.0,
    "zoom_step":             1.15,
}
