# Tiger Studio Painter Material Paint

Status: product implementation with Bristle Engine v2

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
The stroke stores normalized per-point `pressure`, `tilt`, `rotation`, and
paint `load`, plus bristle count, deterministic seed, and load depletion.
The engine builds independent strand paths perpendicular to the authored
stroke tangent instead of drawing decorative lines over one fixed-width body.

Color and material rasterization consume the same strand paths. Pressure
changes strand spread and width; load and depletion change deposition along
the stroke. Height, direction, roughness, normal, AO, and the visible color
therefore describe the same authored brush marks. Long interactive paths are
bounded to 256 lane samples to protect Painter responsiveness.

The interactive canvas uses a cached material-lighting overlay for immediate
feedback. The existing Texture Lab/OpenGL plane renderer remains the
authoritative PBR inspection surface and consumes the merged native maps.
Normal PNG export remains visually compatible; PBR map export can preserve the
native Height/Normal/AO/Roughness channels.

## UX

- Layer menu: `New Material Paint Layer`.
- Layers panel plus menu: standard or Material Paint creation.
- Material layers display an `M`/material status in their row and tooltip.
- Brush options: `Material` controls and a `PBR` preview toggle appear only
  for Material Paint layers.
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
- `paint.stroke.draw` accepts per-point `pressure`, `tilt`, `rotation`, and
  `load`, plus `engine_version`, `bristle_count`, `seed`, and
  `load_depletion`. AI strokes targeting Material Paint layers automatically
  receive the layer's material settings.
- `paint.view.zoom_area` magnifies and centers a normalized canvas rectangle.
- `paint.state` reports layer type, layer material settings, active brush
  material capability, active material controls, and preview state.

All mutations use the existing Painter undo stack.

## Compatibility And Performance

- Existing strokes and clipboard payloads default to standard color behavior.
- Existing `PaintLayer` data defaults to `layer_type=standard`.
- Native material maps are generated only when at least one visible Material
  Paint layer contains material-enabled strokes.
- Canvas material previews are cached by stroke/layer/settings/light signature.
- The feature must preserve QPainter and remote-session fallback behavior.

## Follow-up Work

- Persistent GPU Height/Roughness atlas and retained OpenGL material shader.
- Palette-knife height displacement and scrape/carve operations.
- Wet-paint advection, pigment mixing, drying time, and per-layer varnish.
- Parallax occlusion mapping and optional tessellated close-up preview.
- Material-channel painting/erasing and channel thumbnails.
