# Color / Node Compare Presets

Last updated: 2026-07-11

Use these presets when review automation captures Color Grading, Node Graph, or
Node Effects catalog pages. The goal is not subtle finishing; the goal is a
clear product-catalog comparison where the before/after difference is obvious
inside the real TigerCapture Viewer.

## Research Basis

For the default color comparison, use a strong cinematic teal-orange look.
Reference material consistently describes this look as pushing cool teal/cyan
into shadows while steering midtones/highlights toward orange/amber, with
increased contrast and saturation.

Reference URLs to record in capture contracts:

- https://petapixel.com/2017/02/23/orange-teal-look-popular-hollywood/
- https://www.storyblocks.com/resources/tutorials/davinci-resolve-color-grading
- https://pixflow.net/blog/teal-and-orange-color-grading/
- https://kevinraposo.com/a-guide-to-the-orange-and-teal-look/

## Color Grading: Cinematic Teal Orange Strong Compare

Use this preset when the page needs an obvious compare result. Values are
TigerCapture review-capture targets; adapt only if the current UI exposes a
different scale, and record the adapted scale in the source report.

```json
{
  "preset_name": "cinematic_teal_orange_strong_compare_v1",
  "temperature": 10.0,
  "tint": 6.0,
  "exposure": -0.03,
  "contrast": 1.22,
  "pivot": 0.50,
  "saturation": 1.55,
  "highlights": 45,
  "midtones": 18,
  "shadows": -22,
  "whites": 30,
  "blacks": -12,
  "soft_clip": -20,
  "lift_rgb": [-0.04, 0.02, 0.08],
  "gamma_rgb": [0.05, 0.02, -0.03],
  "gain_rgb": [0.10, 0.04, -0.04],
  "offset_rgb": [0.00, 0.00, 0.00]
}
```

Required capture report fields:

```json
{
  "checks": {
    "strong_researched_color_preset_applied": true,
    "cinematic_teal_orange_preset_applied": true,
    "compare_viewer_and_controls_same_frame": true,
    "color_controls_visible": true
  },
  "preset_name": "cinematic_teal_orange_strong_compare_v1",
  "preset_source_urls": [
    "https://petapixel.com/2017/02/23/orange-teal-look-popular-hollywood/",
    "https://www.storyblocks.com/resources/tutorials/davinci-resolve-color-grading",
    "https://pixflow.net/blog/teal-and-orange-color-grading/",
    "https://kevinraposo.com/a-guide-to-the-orange-and-teal-look/"
  ]
}
```

Reject color captures where the grade is technically non-neutral but visually
too subtle. The Viewer must show a clear split/before-after difference.

## Node / Effect: Gaussian Blur Strong Compare

For Node Graph and Node Effects Library pages, default to a real Gaussian Blur
node/effect unless another implemented node produces a stronger and cleaner
comparison.

Minimum target:

```json
{
  "node_or_effect": "Gaussian Blur",
  "blur_radius_px": 24,
  "horizontal_px": 24,
  "vertical_px": 24,
  "clamp_edges": true
}
```

Acceptable lower bound:

```json
{
  "blur_radius_px_min": 18,
  "horizontal_px_min": 18,
  "vertical_px_min": 18
}
```

Required capture report fields:

```json
{
  "checks": {
    "strong_blur_effect_applied": true,
    "compare_viewer_and_node_controls_same_frame": true,
    "node_or_effect_controls_visible": true
  },
  "node_or_effect": "Gaussian Blur",
  "blur_radius_px": 24
}
```

Reject node/effect captures where the blur radius is tiny, the Viewer does not
show the affected media, or the controls are not visible in the same full
editor/window capture.
