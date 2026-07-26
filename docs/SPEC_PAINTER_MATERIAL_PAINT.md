# Tiger Studio Painter Material Paint

Status: product implementation with Bristle Engine v2 and Wet Canvas v1

## Goal

Material Paint makes thick oil and acrylic strokes retain authored surface
information instead of estimating all relief from the finished RGB image.
Normal Painter layers remain fast color/alpha layers. Material Paint layers
add the channels needed to preview and export impasto:

- base color and alpha from the existing stroke renderer
- paint load and deposited thickness
- wetness and gloss
- surface roughness
- stroke direction, derived from the authored path
- height-derived tangent-space normal and ambient occlusion

The feature is intended for paintings whose brush ridges must react to light.
It is not a claim of full fluid simulation, pigment chemistry, or volumetric
mesh displacement.

## Product Model

Painter keeps one brush library. Brushes declare material compatibility rather
than appearing in a duplicate library.

- `standard` layer: existing Color/Alpha stroke storage and rendering.
- `material` layer: Color/Alpha plus native material stroke channels.
- Thick-oil, bristle, wet-oil, scumble, and palette-knife presets are material
  compatible. Other brushes remain usable but deposit a simple round relief.
- Selecting a Material Paint layer exposes Material controls in the Brush tool
  options. Selecting a standard layer hides those controls.

The initial controls are:

- `Load`: amount of paint carried by the brush.
- `Thickness`: height deposited by a stroke.
- `Wetness`: softness and reduced roughness of fresh paint.
- `Gloss`: specular smoothness.
- `Roughness`: authored surface roughness before wetness/gloss response.

Material layers can additionally enable `Wet Canvas`. This state belongs to
the layer rather than the selected brush:

- `Mix`: sequential color exchange where fresh strokes overlap existing wet
  paint.
- `Bleed`: bounded soft diffusion around paint that is still wet.
- `Pickup`: how strongly the incoming stroke takes color from the wet layer.
- `Dry Time`: deterministic saved drying duration.
- `Dry Now`: marks the layer dry without flattening or deleting editable
  strokes.

Wet Canvas v1 uses deterministic RGB exchange. It is an editable artistic
model, not spectral pigment chemistry, conservative fluid transport, or a
physical claim about real paint.

## Rendering

`app/painter_material_paint.py` owns the Qt-independent material contract and
stroke-channel rasterization.

1. Stroke paths are rasterized at the requested preview/export resolution.
2. Height accumulates where strokes overlap, so repeated paint visibly builds.
3. Bristle and impasto profiles add directional ridge variation.
4. Tangent-space normals are derived from authored height, not RGB luminance.
5. AO is derived from local heightfield concavity.
6. Roughness uses the stroke values and wetness/gloss response.
7. A directional heightfield shadow pass makes raised paint cast a soft local
   shadow in the interactive material preview.
8. Painter's PBR generation path merges these native channels over the
   image-derived fallback maps.

### Bristle Engine v2

Material-compatible oil and acrylic strokes can use `brush_engine_version=2`.
The stroke stores normalized per-point `pressure`, scalar `tilt`, signed
`tilt_x`/`tilt_y`, barrel `rotation`, `tangential_pressure`, and paint `load`,
plus bristle count, deterministic seed, and load depletion.
The engine builds independent strand paths perpendicular to the authored
stroke tangent instead of drawing decorative lines over one fixed-width body.

Color and material rasterization consume the same strand paths. Pressure
changes strand spread and width; signed X/Y tilt shifts and fans the contact
patch in the physical pen direction; load and depletion change deposition
along the stroke. Height, direction, roughness, normal, AO, and the visible
color therefore describe the same authored brush marks. Long interactive
paths are bounded to 256 lane samples to protect Painter responsiveness.

### Tablet input

Painter consumes native Qt tablet press/move/release events. Each accepted
sample retains pressure, X/Y tilt, rotation, and tangential barrel pressure
through live preview, the editable `Stroke`, Undo/Redo, clipboard payloads,
project save/load, GPU-canvas signatures, and PNG/PBR rendering. Mouse strokes
use full pressure and zero tilt so existing mouse-authored artwork keeps its
previous width. Basic GPU strokes use per-segment widths; unsupported complex
brushes continue through the maintained QPainter/material renderer.

The interactive canvas uses a cached material-lighting overlay for immediate
feedback. The existing Texture Lab/OpenGL plane renderer remains the
authoritative PBR inspection surface and consumes the merged native maps.
Normal PNG export remains visually compatible; PBR map export can preserve the
native Height/Normal/AO/Roughness channels.

### Wet Canvas v1

`app/painter_wet_canvas.py` owns normalized layer state, explicit drying
advance, cache signatures, and the shared Qt/PNG wet-layer renderer. Strokes
remain the source of truth and are rendered sequentially into one temporary
layer surface. Existing wet coverage influences the next stroke's RGB at
overlaps; an optional bounded Gaussian pass provides shallow bleed.

Drying is not tied to wall-clock time. The document stores `drying_seconds`
and `elapsed_seconds`, while UI and automation explicitly advance or finish
the state. This keeps Undo/Redo, scripted review, reopening, and PNG export
deterministic. Adding a new stroke to an enabled material layer makes that
layer fresh again.

The editable wet renderer currently uses the maintained QPainter path. The
canvas reports an explicit OpenGL fallback reason while wet exchange is active;
dry material layers continue through the existing renderer paths. Native
Height/Normal/AO/Roughness still come from Material Paint deposition and are
not synthesized from the wet RGB result.

## UX

- Layer menu: `New Material Paint Layer`.
- Layers panel plus menu: standard or Material Paint creation.
- Material layers display an `M`/material status in their row and tooltip.
- Brush options: `Material` controls and a `PBR` preview toggle appear only
  for Material Paint layers.
- The Material menu exposes a compact Wet Canvas section only for Material
  Paint layers. Enabling it does not flatten the layer.
- The left toolbar uses a magnifier tool. A short click activates the current
  zoom mode; press-and-hold opens Zoom In, Zoom Out, Zoom Area, and Fit Canvas.
- Active Zoom In and Zoom Out modes use magnifier cursors with an in-lens `+`
  or `-` mark, so the click behavior is visible before the user acts.
- Zoom Area magnifies and centers the dragged canvas rectangle without
  creating or changing a selection.
- Choosing a material-compatible brush on a normal layer does not silently
  change the document. The brush remains a color brush until the user creates
  or converts a Material Paint layer.

## Automation

- `paint.layer.add` accepts `layer_type=standard|material`.
- `paint.layer.set_type` changes an existing paint layer type.
- `paint.material.settings.set` changes Load, Thickness, Wetness, Gloss, and
  Roughness.
- `paint.material.preview.set` enables/disables the canvas material preview and
  controls light azimuth/elevation.
- `paint.wet_canvas.settings.set` controls enabled state, Mix, Bleed, Pickup,
  and Dry Time on a material layer.
- `paint.wet_canvas.advance` advances saved drying state by an explicit number
  of seconds.
- `paint.wet_canvas.dry` dries the selected material layer without flattening
  its strokes.
- `paint.stroke.draw` accepts per-point `pressure`, scalar `tilt`, signed
  `tilt_x`/`tilt_y`, `rotation`, `tangential_pressure`, and `load`, plus
  `engine_version`, `bristle_count`, `seed`, and `load_depletion`. AI strokes
  targeting Material Paint layers automatically receive the layer's material
  settings.
- `paint.view.zoom_area` magnifies and centers a normalized canvas rectangle.
- `paint.state` reports layer type, layer material and Wet Canvas settings,
  active brush material capability, active material controls, and preview
  state.
- `paint.study.analyze_reference/segment_regions/build_underpaint/
  trace_contours/generate_strokes/compare_render/refine_region/quality_report`
  provide one provider-neutral path for Claude, OpenAI, and local AI. The
  pipeline creates stable standard/material layers and editable Engine v2
  strokes; it never bakes the approved reference into final pixels.
- AI study refinement uses measured render error and semantic focus regions
  supplied as normalized boxes. Completion requires
  `paint.study.quality_report.status=ready`.

All mutations use the existing Painter undo stack.

## Native Document Persistence

Standalone Painter work is saved as a versioned `.tspaint` document rather
than relying on flattened PNG output. The native document retains layer and
mask structure, editable strokes, tablet channels, Material Paint, Wet Canvas
drying state, selections, Work Paths, references, embedded bitmap assets, and
the complete underdrawing 3D Blockout scene. File-menu Open/Save/Save As and
`paint.document.open/save` use the same contract. See
`docs/SPEC_PAINTER_DOCUMENT_FORMAT.md`.

## Compatibility And Performance

- Existing strokes and clipboard payloads default to standard color behavior.
- Existing `PaintLayer` data defaults to `layer_type=standard`.
- Existing material layers default to Wet Canvas disabled.
- Native material maps are generated only when at least one visible Material
  Paint layer contains material-enabled strokes.
- Canvas material previews are cached by stroke/layer/settings/light signature.
- Wet color output is cached by stroke/layer/wet-state signature and is shared
  by interactive canvas rendering and PNG export.
- View zoom does not change retained stroke, Material Height/Normal, reference,
  3D Blockout, or background cache resolution. Those surfaces stay at the
  unzoomed canvas resolution and are scaled only for display; selection,
  guides, pixel grid, and the live stroke remain viewport-native overlays.
- The feature must preserve QPainter and remote-session fallback behavior.

## Follow-up Work

- Persistent GPU Height/Roughness atlas and retained OpenGL material shader.
- Palette-knife height displacement and scrape/carve operations.
- Persistent GPU wet atlas, conservative paint-volume advection, bidirectional
  physical brush/canvas pigment storage, spectral/validated pigment mixing,
  and per-layer varnish.
- Pressure curves/device calibration and brush-specific barrel-pressure
  mappings.
- ABR/captured-dab import.
- Parallax occlusion mapping and optional tessellated close-up preview.
- Material-channel painting/erasing and channel thumbnails.
