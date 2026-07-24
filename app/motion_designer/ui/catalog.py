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
    ("3D Object", "ar_pbr"),
    ("Live2D Actor", "live2d_actor"),
    ("Spine Actor", "spine_actor"),
    ("MMD Actor", "mmd_actor"),
    ("VRM Avatar", "vrm_actor"),
    ("Particle Emitter", "particle"),
    ("Camera", "camera"),
    ("Light", "light"),
)

BEHAVIOR_ITEMS = (
    ("Fade", "fade"),
    ("Slide", "slide"),
    ("Pop", "pop"),
    ("Spring", "spring"),
    ("Wiggle", "wiggle"),
    ("Impact", "impact"),
)

FILTER_ITEMS = (
    ("Glow", "glow"),
    ("Gaussian Blur", "gaussian_blur"),
    ("Brightness / Contrast", "brightness_contrast"),
    ("Saturation", "saturation"),
    ("Vignette", "vignette"),
    ("Unsharp Mask", "unsharp_mask"),
    ("Directional Blur", "directional_blur"),
    ("Displacement", "displacement"),
    ("Corner Pin", "corner_pin"),
    ("Mesh Warp", "mesh_warp"),
    ("Paper Fold", "paper_fold"),
)

CATALOG = {
    "Objects": tuple((label, "object", kind) for label, kind in OBJECT_ITEMS),
    "Behaviors": tuple((label, "behavior", kind) for label, kind in BEHAVIOR_ITEMS),
    "Filters": tuple((label, "effect", kind) for label, kind in FILTER_ITEMS),
    "Templates": (
        ("Clean Lower Third", "template", "clean_lower_third"),
        ("Character Nameplate", "template", "character_nameplate"),
        ("Logo Reveal", "template", "logo_reveal"),
        ("Product Callout", "template", "product_callout"),
        ("Stream Stinger", "template", "stream_stinger"),
        ("Music Beat Title", "template", "music_beat_title"),
        ("Vertical Shorts Hook", "template", "vertical_shorts_hook"),
        ("Anime Character Intro", "template", "anime_character_intro"),
        ("MMD Dance Title", "template", "mmd_dance_title"),
        ("VRM Stream Starting / Ending", "template", "vrm_stream_starting_ending"),
    ),
    "Direction Presets": (
        ("Headline Slam", "advanced_preset", "headline_slam"),
        ("Paper Rip Reveal", "advanced_preset", "paper_rip_reveal"),
        ("Cutout Collage", "advanced_preset", "cutout_collage"),
        ("Editorial Camera Push", "advanced_preset", "editorial_camera_push"),
        ("Beat-Synced Montage", "advanced_preset", "beat_synced_montage"),
    ),
}
