# Review Template Asset Manifest

Last updated: 2026-07-03

This manifest lists presentation template assets used by review automation.
Generated PPT/PNG/HTML outputs do not belong here; this file only describes
source templates and where the pipeline expects to find them.

## Canonical Source Root

Template and reference sources must live outside `debugCapture`.

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates
```

Do not store original laptop/device frames, multi-monitor templates, screen-map
JSON, or design reference images under `debugCapture`. That folder is disposable
debug evidence and can be deleted during capture cleanup.

## Canonical Template Classes

### Laptop / Device Catalog Frame

Purpose:

- show one focused editor workspace with spatial depth,
- present a feature page like a product catalog image,
- keep the screen content real.

Status:

- Required for catalog pages.
- Selected canonical laptop template:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\laptop_catalog_template.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\laptop_catalog_template.screen-map.json
```

- This is the chosen laptop catalog frame. Do not replace it with earlier
  generated variants unless the user explicitly chooses a new canonical
  template.
- The screen region must be replaced with real TigerCapture captures in final
  product pages.
- Do not distort, stretch, squeeze, crop, skew, perspective-warp, or rescale the
  laptop body independently from the template. Preserve the template image
  aspect ratio and hardware geometry exactly; replace only the declared screen
  region.
- The baked sample copy in the template is style reference only; visible PPT
  page copy should be editable and feature-specific.
- Supporting reference sources:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\laptop_color_grading_reference.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\laptop_node_graph_reference.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\minimal_laptop_video_reference.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\monitor_shape_lock_reference.png
```

- These files are visual references for the catalog frame style. Screen content
  inserted into product pages must still be real TigerCapture captures.

Shape lock:

- Monitor/laptop frames must stay within the silhouette of
  `monitor_shape_lock_reference.png`.
- Keep the thin black rounded bezel, broad landscape screen, slim lower metal
  base/shelf, and soft grounded shadow.
- Do not switch to a bulky desktop monitor stand, thick gaming bezel, floating
  tablet frame, colorful device shell, or futuristic hardware shape.
- Generated outer frames are allowed only when they follow this silhouette.
  Screen contents remain real TigerCapture captures.

### Multi-Monitor Catalog Frame

Purpose:

- explain a multi-monitor creator workspace,
- show center video-preview Viewer/timeline, right node/audio/workbench, left
  actor/3D/support surfaces,
- make detached docks and workbench surfaces visually understandable.

Selected canonical multi-monitor template:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_catalog_template.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_catalog_template.screen-map.json
```

Layout rule:

```text
three monitors tightly attached
shared horizontal baseline
center monitor subtly recessed
left/right monitors gently angled inward
thin bezels, including the lower bezel
restrained aluminum display hardware
```

The selected template was chosen by the user on 2026-07-03. Do not replace it
with earlier Dell/monitor variants unless the user explicitly selects a new
canonical multi-monitor template.

Do not distort, stretch, squeeze, crop, skew, perspective-warp, or rescale the
monitor bodies independently from the template. Preserve the template image
aspect ratio and hardware geometry exactly; replace only the declared monitor
screen regions.

Side monitor screen content is allowed and required to be perspective-warped
inside the declared screen quads. This does not violate the distortion lock
because only the inserted capture is warped; the monitor body, bezel, stand,
paper, and shadow remain untouched. Use the `quad` entries from
`multi_monitor_catalog_template.screen-map.json` for the left and right
monitors.

Front-facing replacement candidate:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_front_facing_catalog_template_v1.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_front_facing_catalog_template_v1.screen-map.json
```

Current calibrated front-facing production template:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_front_facing_catalog_template_v2_tight.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_front_facing_catalog_template_v2_tight.screen-map.json
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_front_facing_catalog_template_v2_tight_clean.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_front_facing_catalog_template_v2_tight_clean.screen-map.json
```

Use the `_clean` version for production catalog pages. The non-clean version is
kept only as the calibration source; it contains a visible staging panel and
must not be used directly in PPT output.

Use this candidate when angled side monitors make inserted screenshots look like
flat paper pasted onto the template. All three screens are front-facing and must
use rectangular full-LCD replacement regions:

```text
left_monitor   rect=542,327,339,236
center_monitor rect=886,327,333,236
right_monitor  rect=1225,327,348,236
```

Do not combine this front-facing template with the angled canonical
multi-monitor screen-map. The front-facing map covers the full LCD face while
preserving the physical bezel, stand, paper, and shadow.

White panel rejection rule:

- The three-monitor image must not include a visible white or gray rectangular
  backing panel around the hardware.
- If the outer monitor group looks like a paper cutout placed on top of the
  catalog page, remove that backing panel or regenerate the template before
  building PPT pages.
- Only monitor hardware, screen content, natural shadow, and the catalog page
  background should remain visible.

### AR/PBR Catalog Capture Asset

Purpose:

- provide a visually credible PBR object for AR/PBR Viewer and Workbench
  captures,
- avoid reusing old motorcycle debug evidence,
- show a real textured model with material and lighting context.

Approved source folders:

```text
E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene
E:\ClaudeCodeApp\3d\Nexus_RX-19491522
E:\ClaudeCodeApp\3d\Police_car-009451b7
E:\ClaudeCodeApp\3d\Space_Station_Modules-431ca84e
```

Preferred model inputs:

Stable capture presets:

```text
E:\ClaudeCodeApp\GifCam\docs\review_automation\AR_PBR_CAPTURE_PRESETS.md
E:\ClaudeCodeApp\GifCam\docs\review_automation\presets\ar_pbr_nexus_rx_car.json
E:\ClaudeCodeApp\GifCam\docs\review_automation\presets\ar_pbr_space_station_modules.json
```

The Nexus RX car preset records the current catalog vehicle setup. After manual
3D Preview framing, read back the exact view state with
`ar_pbr.preview.view.get` or `review.ar_pbr.preview.view.get` and update the
JSON preset. A complete view preset must include `pitch`, `yaw`, `roll`,
`zoom` or `zoom_factor`, `camera_z`, `pan_x`, `pan_y`, and `pan_z`.
For standalone preview processes, launch with `--view-state-out <path>` and
close the window after manual adjustment; the saved JSON contains both `view`
and `scene_settings`.
The Space Station Modules preset is approved for hard-surface non-camera
variety. HDRI files must resolve from the editor-wide `resources/ar_pbr` folder,
not from a specific scene folder.

```text
E:\ClaudeCodeApp\3d\Nexus_RX-19491522\gltf\converted\nexus_rx_gltf_extracted\scene.gltf
E:\ClaudeCodeApp\3d\Police_car-009451b7\gltf\converted\police_car_gltf_extracted\scene.gltf
E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene\models\Camera_01\Camera_01_1k.gltf
E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene\models\Camera_01\Camera_01_1k.fbx
E:\ClaudeCodeApp\3d\Space_Station_Modules-431ca84e\gltf\converted\space_station_modules_gl_extracted\scene.gltf
E:\ClaudeCodeApp\3d\Somewhat_Recognizable-668ed982\gltf\converted\somewhat_recognizable_gl_extracted\scene.gltf
E:\ClaudeCodeApp\3d\AKS_Tactical_Upgrade-587e3f02\gltf\converted\akriflefbx_gltf_extracted\scene.gltf
```

Preferred lighting/material context:

```text
E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene\hdris\wooden_studio_17
E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene\materials\concrete_floor
E:\ClaudeCodeApp\GifCam\resources\ar_pbr\hdri
```

Catalog rule:

- AR/PBR screenshots should use a visually readable approved GLTF/GLB asset.
- Do not use the camera scene on every AR/PBR page. Use the camera model for
  camera-specific pages or as a fallback when the other approved GLTF assets
  fail to render cleanly.
- Use the AKS Tactical Upgrade preset only where a technical hard-surface
  material-detail page makes sense; prefer neutral assets for broad public hero
  pages.
- Do not substitute the old motorcycle debug asset for product-catalog evidence.
- Do not use rejected 3D candidates for catalog evidence. Current rejected
  assets:
  `E:\ClaudeCodeApp\3d\Schwerin_Castle-dff1ffb4\fbx\schwerin-castle_extracted\source\Schwerin_extracted\Schwerin.fbx`.
  `E:\ClaudeCodeApp\3d\Bicycle_Collection_Free-0dd4f277\gltf\converted\bicycle_collection_free__extracted\scene.gltf`.
  `E:\ClaudeCodeApp\3d\Ancient_Corinth-69d97182\gltf\converted\ancient_corinth_gltf_extracted\scene.gltf`.
  `E:\ClaudeCodeApp\3d\Spaceship_4-f2bb6a86\gltf\converted\spaceship_4_gltf_extracted\scene.gltf`.
  `E:\ClaudeCodeApp\3d\AK_47_-_F_Modern-1353e155\gltf\converted\source_gltf_extracted\scene.gltf` because textures did not render.
  `E:\ClaudeCodeApp\3d\Police_car-009451b7\gltf\converted\police_car_gltf_extracted\scene.gltf` because wheels did not render correctly.
- If none of the approved 3D assets can be loaded or rendered, mark the AR/PBR
  page pending rather than showing unrelated placeholder 3D evidence.

## Asset Rules

- Never use `debugCapture` as the source of truth for templates or design
  references. It may contain regenerated captures only.
- Outer frames/templates can be generated or staged.
- Do not introduce additional decorative/generated imagery into catalog pages
  beyond the approved laptop and multi-monitor template frames. Once a template
  is selected, it is the only permitted non-editor presentation image for that
  class.
- Generated/staged monitor frames must follow
  `E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\monitor_shape_lock_reference.png`.
- Template images must be placed with locked aspect ratio. Do not stretch,
  squeeze, crop, skew, or perspective-warp laptop/monitor hardware to fit a
  slide. If the template does not fit, change the slide layout around the
  template instead of distorting the template.
- Screen contents inserted into frames must be real TigerCapture captures.
- Editor captures placed inside laptop or monitor frames should preferably show
  a multi-track timeline: source video plus audio/effect/color/text/actor/node
  lanes where relevant.
- Real captures should use visually strong footage when possible, especially
  city scenery, night skylines, drone/aerial scenes, car racing, motorsport,
  driving, or cinematic HDR/OLED demo clips from
  `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`.
- Do not put generated editor UI, color bars, empty panels, or fake labels into
  screen replacement regions.
- When a template file is moved to a stable source location, update this
  manifest first.
