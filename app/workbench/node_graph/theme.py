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
    "canvas_bg":            "#0F1011",
    "grid_minor":           "#171717",
    "grid_major":           "#242424",

    # Node body
    "node_bg_normal":       "#202123",
    "node_bg_hover":        "#25272A",
    "node_bg_selected":     "#2A2D31",
    "node_bg_disabled":     "#151515",
    "node_header_bg":       "#2D2F32",

    "node_border_normal":   "#3A3C40",
    "node_border_hover":    "#686D75",
    "node_border_selected": "#B7BDC5",
    "node_border_disabled": "#252525",

    "node_id_color":        "#AEB7C4",
    "node_label_color":     "#F0F3F7",

    # IN / OUT special nodes
    "io_node_bg":           "#1A1B1D",
    "io_node_border":       "#3E4247",

    # Status bar / toolbar
    "toolbar_bg":           "#111111",
    "statusbar_bg":         "#111111",
    "statusbar_text":       "#9AA0A8",
}


NODE_GRAPH_SIZES = {
    "node_width":            118,
    "node_height":           56,
    "node_border_radius":    5,
    "node_header_height":    17,

    "thumbnail_width":       84,
    "thumbnail_height":      18,

    "io_width":              60,
    "io_height":             26,
    "io_thumbnail_width":    0,
    "io_thumbnail_height":   0,

    "grid_minor_spacing":    12,
    "grid_major_spacing":    60,

    "canvas_size":           10000,
    "min_zoom":              0.1,
    "max_zoom":              5.0,
    "zoom_step":             1.15,
}
