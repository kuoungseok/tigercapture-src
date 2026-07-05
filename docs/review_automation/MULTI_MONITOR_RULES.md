# Multi-Monitor Catalog Rules

Last updated: 2026-07-03

This file is the compact multi-monitor rule for review automation. The expanded
layout discussion remains in:

```text
docs/MULTI_MONITOR_REVIEW_SCENARIO_RULES.md
```

## Purpose

The multi-monitor template is a product-catalog device. It should make the
TigerCapture/Tiger Studio work environment feel believable and high-end.

It is not a QA dashboard frame.

## Template Contract

The outer monitor frame may be staged or generated. The screen content inside
the monitors must be real TigerCapture captures.

Template sources must live in:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates
```

Never store original monitor templates or screen-map JSON under `debugCapture`;
that folder is disposable generated evidence.

Selected multi-monitor template assets:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_catalog_template.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_catalog_template.screen-map.json
```

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

Use the `_clean` version for PPT/catalog generation. The non-clean version is
only kept as a calibration source.

Monitor silhouette lock:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\monitor_shape_lock_reference.png
```

All generated or staged monitor layouts must stay in this shape language:
thin black rounded bezel, broad landscape screen, slim lower metal base/shelf,
soft shadow, premium laptop/monitor product-catalog feel. Do not use bulky
desktop stands, thick gaming bezels, floating tablet frames, colorful shells, or
alternate hardware silhouettes.

Distortion lock:

- Do not distort, stretch, squeeze, crop, skew, perspective-warp, or rescale the
  monitor bodies independently from the template.
- Preserve the template image aspect ratio and hardware geometry exactly.
- Replace only the declared screen regions from the screen-map JSON.
- If the template does not fit a slide, change the slide layout around the
  template instead of distorting the template.

Selected screen regions use template pixel coordinates. The side monitors are
angled and therefore must use four-point perspective quads, not flat rectangular
paste:

```text
left_monitor   quad=(586,315) (856,327) (856,546) (586,555)
center_monitor rect=908,344,278,196
right_monitor  quad=(1250,327) (1514,315) (1514,555) (1250,546)
```

Quad corner order is top-left, top-right, bottom-right, bottom-left. The
review-only compositor must perspective-warp each side capture into its quad so
the slight vanishing point of the physical monitor template is preserved. Only
the captured screen content is warped; the monitor bodies, bezels, and stands
must remain untouched.

If the angled side monitors make captures look like flat paper pasted onto the
template, use the front-facing replacement candidate instead. Its screen-map is
rectangular and replaces the full LCD face:

```text
left_monitor   rect=542,327,339,236
center_monitor rect=886,327,333,236
right_monitor  rect=1225,327,348,236
```

Do not combine the front-facing template with the angled template screen-map,
and do not crop inward to only the inner preview/content panel.

White panel rejection rule:

- The monitor template must not expose a visible white or gray rectangular
  staging panel around the monitor hardware.
- If the monitor group reads like screenshots pasted onto a separate sheet of
  paper, reject the composition and rebuild the template/crop.
- Monitor bodies, shadows, and the catalog page background may remain visible;
  a hard rectangular backing plate around the three monitors may not.
- Screen replacement must still use only the declared screen regions from the
  screen-map JSON.

If these assets are missing, do not silently synthesize replacement product
evidence. Mark the multi-monitor catalog image as pending until the selected
template source is restored or the user explicitly selects a new template.

## Recommended Layout

Center monitor:

- large Viewer,
- active timeline,
- real media,
- AI command surface if relevant.

Right monitor:

- node graph,
- color/audio/sound editor,
- inspector/workbench controls.

Left monitor:

- Live2D/actor workspace,
- 3D/AR/PBR/MMD support views or controls,
- media pool/project bin/supporting panels.

Video Preview Viewer rule:

- The main video preview Viewer belongs only on the center monitor.
- A real video frame from the edit timeline belongs only on the center monitor.
- Left and right monitors must not show the main editor video Viewer, Preview
  popout, or large timeline-video preview frame.
- Feature-specific viewers are allowed outside the center monitor when they are
  the correct tool surface: Live2D Viewer, MMD Player, AR/PBR asset preview,
  VTuber Studio, Spine editor, 3D object viewer, and similar specialized
  windows.
- If a left/right monitor slot contains the main timeline video preview or a
  large imported-video frame, reject the multi-monitor image and regenerate it.

## Window Placement Rule

The first serious multi-monitor catalog image must use this composition unless
the user explicitly chooses a different variant.

### Center Monitor: Main Edit Bay

Purpose: this is the creator's primary working screen.

Required contents:

- Main editor capture, not a fake composite.
- Viewer in the upper/dominant area.
- Timeline across the lower width.
- AI Command as a compact bottom/right dock or rail.
- Real media visible in Viewer.
- For the first multi-monitor studio hero, the center Viewer must use the
  Lamborghini YouTube Imports clip, not a macro human eye/face/body close-up.
  If the Lamborghini clip is unavailable, stop and report the missing media
  instead of silently replacing it with unrelated footage.
- Long, multi-track timeline with video plus at least one companion lane:
  audio, effect, color, text, actor, node, marker, or transition.

Placement guidance:

- Viewer should take the main upper read.
- Timeline must be readable enough to prove editing is happening.
- AI Command is visible but secondary; it must not cover the Viewer or hide the
  Timeline.
- Do not make the center monitor only a full-screen preview.

### Right Monitor: Node And Sound Bench

Purpose: this is the technical finishing surface.

Required contents:

- Node Graph should dominate the right monitor.
- Connected nodes must be readable.
- At least one selected node or parameter surface should be visible.
- The node story must communicate real effect families, not just abstract boxes:
  color/grade nodes, blur/soft-pass nodes, look/VFX nodes, mask/tracking nodes,
  LUT nodes, and SDR -> HDR prep. Use actual implemented labels such as White
  Balance, Curves, Levels, Channel Mixer, LUT, Glow, Vignette, Film Grain,
  Unsharp Mask, Pixelate, Blur, Mask, and SDR -> HDR EXR.
- Sound Editor, audio mixer, waveform, spectrum, EQ, dynamics, or level meters
  should occupy the lower/secondary area when available.

Placement guidance:

- Node Graph first, sound/audio second.
- If there is not enough room, keep Node Graph readable and reduce Sound Editor
  to a secondary dock.
- Color/scopes may appear here only when they do not make the Node Graph tiny.
- Do not use a generic Workbench inspector as a substitute for a real node or
  audio scene.
- Do not use a generic or fake node graph where the viewer cannot tell what the
  nodes do.

### Left Monitor: Actor, 3D, And Asset Bench

Purpose: this is the character, 3D, and asset production surface.

Required contents:

- Live2D editor/viewer, actor lane/workbench controls, actor library, or
  parameter editor.
- AR/PBR asset preview or workbench/inspector controls using a real approved
  GLTF/GLB asset from `E:\ClaudeCodeApp\3d`, when capture-ready.
- For the first multi-monitor studio hero, include a real 3D viewer/AR-PBR
  preview surface on the left monitor. AR/PBR workbench controls alone are not
  enough for this page.
- MMD Player, MMD Actor Editor controls, diagnostics, timeline, or
  material/physics panel, when capture-ready.
- Media Pool, Actor Library, Effect Library, or preset support strip may fill
  the remaining area.

Placement guidance:

- Do not place the main video preview Viewer, Preview popout, or imported-video
  frame on the left monitor. Specialized feature viewers such as Live2D, MMD,
  AR/PBR, VTuber, Spine, and 3D object viewers are allowed here when they match
  the story.
- For the general overview hero, do not let a single Live2D actor/viewer fill
  the whole left monitor. It makes the monitor read as a Live2D feature page
  instead of a specialist support bench.
- Live2D or actor work gets the largest cell only when actor workflow is the
  slide story.
- AR/PBR 3D asset preview should be the strongest or co-strongest cell for the
  general overview, with Live2D and MMD as supporting real tool surfaces.
- Do not always use the Poly Haven camera scene. It is an approved fallback and
  useful for camera-specific pages, but repeated camera-only 3D evidence makes
  the catalog feel monotonous.
- For overview and general AR/PBR pages, prefer a more visually readable
  approved GLTF such as:

```text
E:\ClaudeCodeApp\3d\Nexus_RX-19491522\gltf\converted\nexus_rx_gltf_extracted\scene.gltf
E:\ClaudeCodeApp\3d\Police_car-009451b7\gltf\converted\police_car_gltf_extracted\scene.gltf
E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene\models\Camera_01\Camera_01_1k.gltf
```

- Use the camera model only when the slide specifically benefits from a camera
  object or when the other approved assets fail to render.
- For every 3D viewer / AR-PBR capture, hide the HDR/cubemap environment
  background with the viewer background toggle before taking the screenshot.
  Environment lighting may remain active, but the visible background must be a
  neutral viewer surface so the model reads first.
- MMD appears as a real tool surface, not a decorative label.
- Do not use Spine/NIKKE in the first public composition unless the render is
  visually correct.

### Fallback Rule

If a target surface is not real-capture ready, replace it with the nearest real
implemented surface in the same family and record the skipped target as pending.
Never synthesize missing windows inside monitor screens.

## Capture Safety

Viewer/GPU/OpenGL surfaces can turn black if captured while hidden. For review
automation, show the target window briefly, capture it, then hide or replace it.
Do not rely on grabbing hidden GPU preview widgets.
