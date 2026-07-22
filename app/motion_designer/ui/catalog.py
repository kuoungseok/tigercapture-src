from __future__ import annotations


OBJECT_ITEMS = (
    ("Text", "text"),
    ("Image", "image"),
    ("Shape", "shape"),
    ("Polygon", "polygon"),
    ("Star", "star"),
    ("Path", "path"),
    ("Line", "line"),
    ("Group", "group"),
    ("Null", "null"),
    ("Adjustment", "adjustment"),
)

BEHAVIOR_ITEMS = (
    ("Fade", "fade"),
    ("Slide", "slide"),
    ("Pop", "pop"),
    ("Spring", "spring"),
    ("Wiggle", "wiggle"),
)

FILTER_ITEMS = (
    ("Glow", "glow"),
    ("Gaussian Blur", "gaussian_blur"),
    ("Brightness / Contrast", "brightness_contrast"),
    ("Saturation", "saturation"),
    ("Vignette", "vignette"),
    ("Unsharp Mask", "unsharp_mask"),
)

CATALOG = {
    "Objects": tuple((label, "object", kind) for label, kind in OBJECT_ITEMS),
    "Behaviors": tuple((label, "behavior", kind) for label, kind in BEHAVIOR_ITEMS),
    "Filters": tuple((label, "effect", kind) for label, kind in FILTER_ITEMS),
}
