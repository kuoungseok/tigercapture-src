# Tiger Painter Production Art Workspace Plan

## Purpose

Tiger Painter is a primary drawing workspace for game concept artists. It is
not a video annotation helper. The product target is a Photoshop / Clip Studio
Paint / Corel Painter style workspace for character, prop, background,
environment, and texture artists.

Typography, 3D, PBR, and video paint-over are supporting options. They must not
take over the first screen or make the drawing workflow feel like the video
editor.

## User Profile

- Character concept artist painting line art, values, color, and finish passes.
- Background concept artist blocking a scene with simple 3D forms, then painting
  over it.
- Prop and material artist creating texture ideas, icon sheets, or PBR source
  maps.
- Illustrator using references, layers, masks, selections, and brush presets for
  long drawing sessions.

## Product North Star

A user should be able to open Painter, create a canvas, pick a brush, arrange
references, sketch, block values, paint details, manage layers, and optionally
use simple 3D blockout without touching the video timeline.

First impression:

- Large canvas dominates.
- Brush/color/layer surfaces are obvious.
- Tool options are near the top and change with the active tool.
- 3D/PBR/Typography are visible as optional workspaces, not primary content.

## UX Reference Map

The maintained Photoshop parity matrix is
`docs/PAINTER_PHOTOSHOP_PARITY_AUDIT.md`. Agents must use that matrix instead of
waiting for the user to identify individual mismatches.

Tiger Painter does not clone one application. Each reference owns a role:

| Reference | Tiger Painter adopts | Tiger Painter rejects |
| --- | --- | --- |
| Photoshop | Tool rail, top tool options, Layers/Channels/Paths, masks, selections, shortcuts | Overloaded legacy dialogs and hidden mode traps |
| Clip Studio Paint | Concept-art flow, perspective rulers, 3D reference materials, line/paint workflow | Manga-only assumptions and complex asset stores |
| Corel Painter | Natural-media brush feel, stroke-preview expectation, oil/dry/knife media | Dense old-style panels and deep simulation before basic UX is stable |
| Krita | Inspectable brush engine, preset resources, popup palette behavior | Making every brush parameter equally prominent |
| Procreate | Fast canvas interaction, low-friction drawing, direct feel | Touch-only assumptions and hidden desktop controls |
| PureRef | Reference board, pinned images, zoom/pan references | Replacing the main canvas with a board UI |
| SketchUp | Simple box-based blockout and camera framing for artists | Full CAD or mesh-modeling depth |
| Blender gizmo basics | Familiar move/rotate/scale manipulators | Blender-level workspace complexity |
| Clip Studio 3D Material | 3D as draw-over reference | 3D becoming the main authoring surface |

## Workspace Layout Contract

Default layout:

- New standalone Painter windows open clean at 100% zoom with no sample strokes,
  guides, or demo marks. 400-800% zoom is reserved for pixel/dot work.
- New documents and newly added paint layers are pixel-empty until the user
  paints, pastes, or runs Fill. Transparent documents show Photoshop-style
  neutral-gray checkerboard tiles in the canvas and layer thumbnail UI only;
  the checkerboard is never stored in document pixels or exported.
- `New Canvas` defaults to `Transparent`. White and dark page backgrounds remain
  explicit user choices and are the only presets that create a Background
  layer at document creation time.
- Center: large canvas with checkerboard support, navigator framing, zoom/pan,
  and optional pixel grid at high zoom.
- Left: compact single-column tool rail with tool groups and long-press/right
  click subtool popups.
  Its fixed Photoshop-familiar order is Move; rectangular/elliptical marquee,
  Magic Select, Crop; Brush, Eraser, Fill, Pen/Path; Hand, Fit, Quick Mask;
  Mirror X/Y and 3D Blockout. Destructive Clear stays isolated at the bottom.
  Move, Magic Select, Fill, Quick Mask, Fit, and Pen/Path use distinct
  tool-shaped icons rather than generic cursor, target, palette, or marquee
  symbols. Brush is an explicit exception: its rail icon selects the tool only;
  brush presets belong to the dedicated top tool-options button and must not
  reuse or anchor to the rail icon. Tooltips include the active keyboard
  shortcut where one exists.
  The rail itself follows the Photoshop reference: a flat neutral `#535353`
  surface, compact white monochrome glyphs, no rounded button boxes, no purple
  selection accent, no red destructive accent, and only a darker neutral hover
  or checked cell. Foreground/background swatches remain square and unframed.
- Top: active tool options only. This area should not become a permanent
  command strip for unrelated features.
- The top options bar exposes Photoshop-style contextual controls: Brush/Eraser
  size and opacity; marquee New/Add/Subtract/Intersect plus style; Magic Select
  tolerance; Crop apply/mask/deselect; and Fill mode. Non-active tool controls
  are hidden rather than disabled clutter.
- Undo/Redo belong in Edit plus keyboard shortcuts, and PNG export belongs in
  File. They must not occupy a permanent quick-control row above the canvas.
  The area below the menu is reserved for contextual controls of the active
  tool. Zoom does not belong in the title/options bar; it lives in the View
  menu, shortcuts, canvas context menu, status bar, and toolbar affordances.
- Right upper: Navigator and Reference controls.
- Right middle: Color and Brush.
- Right lower: Layers / Channels / Paths as a dedicated pinned tab dock.
- Optional lower or popout panels: Brush Presets, History, 3D Blockout,
  Typography, PBR Texture Lab.
- In the clean default workspace, detailed Brush, Reference, and 3D panels are
  closed. Color plus Layers/Channels/Paths remain visible; optional panels show
  only after the user chooses their Window/toolbar entry.
- A compact bottom status bar owns zoom and document-size feedback. Zoom does
  not return to the title or options bar.

Responsive behavior:

- At laptop widths, panels must scroll or collapse instead of overlapping.
- The right inspector is a capped side dock. It must not become wider than the
  central canvas in normal small-window or remote-work layouts.
- Moving the top-level Painter window must pause widget updates during the drag
  and perform one geometry sync/repaint after movement idles. Remote desktop
  sessions must not pay continuous full-UI refresh cost while the window is
  being moved.
- Color wheel, brush settings, and Layers/Channels/Paths must never occupy the
  same visual space.
- The default Color panel should prefer a compact current-color row, swatch
  matrix, and H/S/V sliders. A large decorative hue wheel must not be the
  default right-inspector surface.
- Layers / Channels / Paths are high-frequency production panels. They may
  resize or scroll, but they must not be hidden behind optional 3D, PBR,
  Typography, History, or helper panels in the default drawing workspace.
  Tabs should be flat and Photoshop-like. Debug counters, stroke totals, and
  export-note copy do not belong in this dock.
- The Layers tab follows the Photoshop mental model: kind filter icons,
  blend/opacity/lock/fill controls, visible layer rows with eye icons, subtle
  layer color labels, and a compact bottom icon row for new, duplicate, copy,
  paste, and delete. Large text action buttons do not belong in the default dock.
- The Channels tab lists RGB, Red, Green, Blue, and Alpha with eye-icon
  visibility toggles and channel copy/paste. Selecting a row changes the active
  channel; visibility changes through the eye hit area or automation.
- The Paths tab exposes Work Path, Selection Path, and saved paths, with direct
  make-selection and make-mask commands. Pen creates paths, Path Selection moves
  whole paths, Direct Selection edits points, and saved paths round-trip through
  selection and mask operations.
- The default right dock follows the Photoshop panel reference rather than the
  general Tiger Studio card theme. It uses a neutral flat gray surface, compact
  `Color / Swatches / Gradients / Patterns` tabs, an interactive horizontal
  saturation/value field with a vertical hue strip, and thin
  `Layers / Channels / Paths` tabs. Layer and channel rows include an eye hit
  area plus a real thumbnail; channel thumbnails visualize RGB, Red, Green,
  Blue, and Alpha independently. Purple sliders, rounded cards, and oversized
  tab buttons do not belong in this dock.
- Canvas must initialize to the available screen area without requiring window
  resize.
- All persistent panels need a recoverable Window menu entry.

## Tool Rail Contract

Primary tools:

- Move
- Marquee selection
- Lasso / polygon lasso
- Magic wand / color select
- Crop
- Eyedropper
- Brush / pencil
- Eraser
- Smudge / blur / sharpen group
- Fill / gradient
- Pen / path
- Type
- Shape
- Hand / pan
- Zoom
- Foreground/background swatches with swap
- Quick mask

Rules:

- Tool rail labels live in tooltips and accessibility names, not permanent text.
- Unsupported tools should not appear as fake buttons.
- Long-press/right-click subtool popups are required for brush-like and
  selection-like groups.
- Active tool should expose a clear selected state and update the top options.

## Canvas Interaction Contract

Required interactions:

- `B` brush, `E` eraser, `V` move, `H` hand, `Z` zoom, `I` eyedropper.
- `[` and `]` adjust brush size.
- `Space + drag` pans.
- `Ctrl + wheel` zooms.
- `Alt + click` samples color.
- Fit / 100% / 200% / 400% / 800% zoom targets.
- At maximum or high zoom, show a pixel grid suitable for dot work.
- Pixel brush mode must use nearest-neighbor display and no antialiasing.
- Flip canvas and grayscale/value check must be one gesture away.

## Brush Engine Requirements

Brushes are the product core. Minimum production-art brush families:

- Hard Round
- Soft Round
- Sketch Pencil
- Clean Ink
- Blocking Brush
- Loaded Oil
- Impasto Oil
- Dry Brush
- Palette Knife
- Smudge Paint
- Marker
- Chalk
- Airbrush
- Pixel Brush
- Hair Strand
- Skin Soft
- Metal Highlight
- Cloud / Smoke
- Rock / Ground
- Fabric / Grunge Texture

Implemented professional oil subset (2026-07-25):

- Filbert Portrait: rounded, overlapping loaded-paint deposits.
- Hog Flat No. 12: square edge with individual stiff-bristle grooves.
- Fan Foliage: separated, broken fan lanes for foliage and hair masses.
- Rigger Long Line: narrow continuous core with subtle pigment lanes.
- Dry Scumble: broken canvas-revealing deposits.
- Stipple Bloom: clustered irregular oil dots.
- Knife Scrape: sharp low body with raised broken deposits.
- These are renderer-level styles, not names over one generic brush. The Qt
  canvas and PIL/MP4 export paths share the same style contract, preset
  thumbnails use actual stroke rendering, and Painter actions can select or
  draw every style.

Implemented designer catalog subset (2026-07-25):

- Basic: hard/soft round, hard/soft flat, and pixel-square tips.
- Drawing and Ink: graphite, vine/block charcoal, technical pen, expressive ink.
- Water Media: transparent watercolor wash/edge and opaque gouache/acrylic.
- Airbrush and Concept: soft airbrush, skin blender, hair, foliage, cloud/smoke.
- Texture and FX: rock/ground, fabric/grunge, and paint splatter.
- Each family has a renderer profile with distinct deposition behavior in Qt
  preview and PIL/MP4 export. Presets carry real size, opacity, hardness,
  spacing, angle, and roundness values.
- The dedicated top `Brush Preset` popup uses rendered tip thumbnails with
  `All Brushes` and category filtering; the left-rail Brush icon remains a
  fixed tool selector. Both popup and inspector use compact `53x25` thumbnails
  and proportionally reduced cells. The full inspector keeps Brush/Brush
  Presets and the familiar Photoshop-style parameter-section layout.

## Corel Painter Brush Workspace Reference

Official layout references:

- Brush Selector full/compact view and component map:
  <https://product.corel.com/help/Painter/540111155/Corel-Painter-en/Corel-Painter-Brush-selector.html>
- Favorites and multi-filter behavior:
  <https://product.corel.com/help/Painter/540111162/Corel-Painter-en/Corel-Painter-Filtering-brushes.html>
- Captured dab libraries and PNG/JPEG dab import:
  <https://product.corel.com/help/Painter/540111162/Corel-Painter-en/Corel-Painter-Capturing-brush-dabs.html>
- Advanced brush controls:
  <https://product.corel.com/help/Painter/540111155/Corel-Painter-en/Corel-Painter-Exploring-Brush-controls.html>

Implemented Painter 2023 layout contract (2026-07-25):

- `Brush Selector` is a real stacked page with a restrained icon header,
  library selector, favorite toggle, search, simultaneous checkable
  Favorites/Painter Masters/Stamps/Watercolor/Thick Paint filters, and an
  empty-state-aware recent strip.
- The full view uses compact categories on the left and named stroke-preview
  rows on the right. Compact mode hides library/category/recent chrome while
  preserving search and brush variants. The selected-brush footer is shallow
  and reports compatible Default, Watercolor, and Thick Paint layer types.
- `Advanced Brush Controls` is a separate page with engine sections and
  current-brush controls. Small selector/control icons switch actual pages
  without a large decorative tab row.
- The Brush tool options bar labels the former preset entry point `Brush
  Selector` and focuses the full selector directly. Brush and other ordinary
  Painter numeric controls use the shared `StudioSlider`; HSV channel sliders
  retain their functional color gradients.
- `paint.state` reports library/search/filter-list/compact/favorite/recent state.
  `paint.brush.library.view` and `paint.brush.favorite.set` expose the same
  workflow to Claude and local automation.
- Tiger Studio uses its own renderer profiles and thumbnails. Corel's
  proprietary default brushes and commercial packs are references only and
  are not bundled or presented as installed resources.

Brush parameter contract:

- Size
- Opacity
- Flow
- Hardness
- Spacing
- Angle
- Roundness
- Texture
- Scatter
- Smoothing / stabilization
- Pressure curve
- Optional tilt/rotation hooks
- Wet/smudge/mixer behavior for later passes

Preset UX:

- Presets must show actual stroke thumbnails, not text-only rows.
- Brush popup should be image-first with compact labels on hover.
- The right Brush panel can expose deeper parameter tabs.
- Selecting a preset must update the active tool, size, opacity, style, and
  preview consistently.

## Layer / Channel / Path Contract

Layers:

- Thumbnail
- Rename
- Visibility toggle
- Lock toggle
- Lock transparent pixels
- Opacity and fill
- Blend mode
- Duplicate
- Delete
- Merge down
- Flatten
- Drag reorder
- Group/folder plan
- Clipping mask
- Layer mask
- Color label

Channels:

- RGB, Red, Green, Blue, Alpha rows.
- Eye icons are toggles, not text buttons.
- Clicking a row selects the channel only.
- Copy/paste channel image data must work through the system clipboard.

Paths:

- Work Path
- Save path
- Delete path
- Path to selection
- Selection to path
- Stroke path
- Fill path
- Path to layer mask

Layer/Channel/Path must be a real lower-right dock, not squeezed under the color
wheel where controls overlap.

## Selection And Transform Contract

Selection tools:

- Rectangular marquee
- Elliptical marquee
- Lasso
- Polygon lasso
- Magic wand / similar color
- Color range

Selection operations:

- Select all
- Deselect
- Invert
- Feather
- Expand / contract
- Save selection as channel
- Selection to mask
- Selection to path

Transform operations:

- Move selection
- Transform selection
- Free transform
- Rotate
- Scale
- Skew
- Flip

Destructive operations must have undo transactions and action dry-run/review
support before they are exposed to AI/MCP workflows.

## Reference Workflow Contract

Reference features:

- PureRef-like reference board.
- Add image from file, clipboard, or media pool.
- Pin, scale, rotate, arrange, lock, and hide references.
- Per-reference opacity.
- Sample color from reference.
- Extract palette from reference.
- Navigator thumbnail.
- Flip canvas without modifying pixels.
- Value check / grayscale view.
- Silhouette check.
- Perspective guides, ruler guides, and symmetry drawing.

References are not paint layers unless explicitly imported or baked.

2026-07-24 first slice:

- `REFERENCE` inspector panel above optional 3D blockout.
- Add reference images from file or clipboard.
- Keep references as non-destructive canvas overlays; they are not exported by
  default and do not become paint layers automatically.
- Per-selected-reference position, size, opacity, and visibility controls.
- Duplicate/delete and explicit bake-to-sticker for cases where the reference
  should become exportable artwork.
- `Window > Reference Board` and `paint.reference.state/add/update/delete/
  duplicate/bake` action coverage.

2026-07-24 second slice:

- Per-reference rotation is stored, previewed, baked to sticker rotation, and
  exposed through `paint.reference.add/update`.
- Reference lock UI prevents accidental panel edits while keeping visibility
  and unlock controls available.
- Reference color sampling and palette extraction are available from the
  `REFERENCE` panel and through `paint.reference.sample_color` and
  `paint.reference.extract_palette`.

2026-07-24 third slice:

- Perspective ruler overlay is available on the canvas and through
  `paint.guide.perspective`, with horizon and left/right vanishing point
  controls stored in `paint.state.guides`.
- Symmetry guide overlay is available on the canvas and through
  `paint.guide.symmetry`, with vertical/horizontal axis and normalized position
  stored in `paint.state.guides`.
- These guides are QPainter overlays for remote reliability today; they are
  intentionally separate from the stroke engine so future mirrored-stroke and
  perspective-ruler snapping can reuse the same state.

Remaining:

- Media Pool add.
- Navigator thumbnail.
- Value/silhouette check.
- Perspective snapping and true mirrored stroke drawing.

## 3D Blockout Contract

3D blockout exists for background and environment concept artists who block a
room, street, building, or prop massing before painting. It is not a Blender
replacement.

Primitive set:

- Cube
- Sphere
- Cylinder
- Cone
- Plane
- Arch, only as a simple doorway/window/opening helper

Cube remains the primary massing primitive. The compact Unreal-style Shapes
palette may be clicked for a focus-point placement or dragged onto the canvas;
drop placement uses screen-to-world unprojection against the Z-up ground plane.

Interaction:

- Canvas mode toggle: Paint / 3D Place.
- Unreal-style X-red/Y-green/Z-blue move / rotate / scale gizmo; Z is up.
- Grid snap.
- Duplicate.
- Align to ground.
- Camera orbit / pan / W-A-S-D travel / wheel zoom.
- Camera FOV control.
- Simple camera presets: front, side, top, perspective.
- Horizon line and vanishing point overlays.

Draw-over modes:

- Opaque white Lit material by default.
- Configurable directional light, defaulting to 45 degrees horizontally and
  vertically.
- Independent Lit and Shadow toggles; shadows default on.
- Wireframe.
- Transparent overlay.
- Silhouette.
- Independent fog and grayscale depth diagnostic toggles.
- Shadow guide.
- Line extraction.
- Value snapshot.
- Bake to paint layer.

Rules:

- 3D blockout data stays separate from raster strokes, but appears as a bottom
  `3D Blockout` reference layer with normal visibility and opacity controls.
- Paint strokes must composite above the 3D reference.
- Paint mode uses a retained 2D snapshot cache for the current 3D guide; edits
  in 3D Place invalidate it.
- It must be reachable from optional panel/menu/action surfaces.
- 3D should help composition and perspective, not dominate the drawing UI.
- Keep the interaction closer to a standard 3D transform gizmo than to a
  modeling package: move, rotate, scale, camera orbit/pan/zoom, and FOV only.
- AI/MCP may control the same material preview through
  `paint.3d_blockout.material_preview`.

### Future Figure Pose Mode

Painter should later add a separate `Figure` placement mode for character
sketch reference. It reuses the canvas camera, Z-up gizmo, depth/fog preview,
and bottom reference-layer composition, but must not turn the basic Shapes
palette into a character editor.

- Use a GitHub-hosted rigged human mannequin only after its redistribution and
  commercial-use license is verified; keep durable models under
  `external/assets`, never `debugCapture`.
- Provide bone selection and local joint rotation, root move/rotate/scale,
  mirrored pose, reset pose, and saved pose presets.
- Offer proportion presets and readable silhouette/value/depth views for
  drawing reference rather than skinning, animation, or character production.
- Expose pose state and joint edits through dedicated actions so local AI can
  construct a pose without hard-coded screen coordinates.
- Keep the mannequin scene editable while Paint mode consumes a retained 2D
  guide cache, matching the 3D Blockout paint-over contract.

## Typography / PBR / Video Boundary

Typography:

- Optional for callouts, title concepts, UI mockups, and graphic layout.
- It must not occupy the default Painter right dock.

PBR:

- Optional texture artist workflow.
- Existing Texture Lab entry points must be preserved. `PBR Texture Lab...`,
  PBR preview/export actions, and the shared Texture Lab backend remain valid
  doorways even while Painter is re-centered around drawing.
- Texture Lab and material preview are separate panels or popouts.
- Texture Lab must not displace the pinned Layers / Channels / Paths dock.
- PBR actions may use Painter output as source, but the painting canvas stays
  the authoring center.

## GPU / Performance Direction

Painter is expected to lean heavily on GPU-backed paths as the workspace grows.
Large canvases, high-zoom pixel work, natural-media brush preview, 3D blockout,
Texture Lab/PBR previews, material map generation, and optional video paint-over
must be designed so CPU fallbacks are safe but not treated as the final quality
or performance target.

Rules:

- New 3D/PBR/preview surfaces should define their data contract so a GPU
  renderer can consume it without rewriting the Painter UI.
- CPU/QPainter implementations are acceptable as first-pass visual contracts,
  but they must not block later OpenGL/Vulkan/Rust/C++ acceleration.
- Remote-work safety is mandatory. OpenGL paths must be preferred when a valid
  desktop/context exists, but Remote Desktop, headless Qt, and disabled-GPU
  sessions must fall back to a maintained QPainter path instead of showing a
  black surface or crashing.
- Any feature that claims parity with export must document preview/export GPU
  parity expectations and test coverage.
- GPU-heavy optional panels must not make the default 2D drawing workspace slow
  to open or use.

2026-07-24 OpenGL first pass:

- `app.painter_opengl` owns the optional Painter OpenGL helpers instead of
  importing PyOpenGL from the main drawing dialog at startup.
- 3D blockout preview/overlay render through an offscreen OpenGL FBO when Qt
  and PyOpenGL can create a context; otherwise the same projection renders
  through the existing QPainter path.
- The active Painter canvas has a first-pass OpenGL stroke-layer path for
  basic round/marker/highlighter strokes. It renders those supported strokes
  through an offscreen FBO and caches the result per stroke signature, then
  falls back to the maintained QPainter stroke loop for masks, textured oil/
  chalk/knife brushes, custom tip dynamics, unavailable GL, or remote/headless
  failures.
- The active Painter canvas now wraps that FBO renderer in a session-local
  persistent stroke atlas cache. The widget still blits the cached image through
  QPainter, but OpenGL readback is limited to stroke-signature changes and the
  renderer reports `painter_canvas_opengl_persistent_stroke_atlas_v1` when that
  path is active.
- `paint.state` and `paint.gpu.status` report the texture-brush GPU parity
  target (`dab_atlas_noise_texture_brush_stamp_shader`), layer/mask shader plan
  (`per_layer_fbo_opacity_blend_mask_shader`), and high-zoom dirty-region
  contract so review automation and local AI do not infer unsupported parity.
- `paint.gpu.status` exposes OpenGL dependency readiness, the last blockout
  renderer, the last canvas renderer, and the remote-safe fallback contract for
  AI/MCP automation.
- The next canvas GPU pass is retained GL texture display plus textured-brush
  stamp/noise shaders. Do not replace the whole canvas with a `QOpenGLWidget`
  until remote/RDP fallback and parity QA are proven.

Video:

- Video paint-over is a supporting workflow.
- The default Painter product must remain usable with no timeline or media clip.

## Python Action Parity

Every production Painter feature intended for AI/MCP must have action coverage.
Use registered `paint.*` actions only; do not expose private widget methods.

Required action families:

- `paint.state`
- `paint.document.*`
- `paint.view.*`
- `paint.guide.*`
- `paint.tool.*`
- `paint.brush.*`
- `paint.layer.*`
- `paint.channel.*`
- `paint.path.*`
- `paint.selection.*`
- `paint.transform.*`
- `paint.clipboard.*`
- `paint.reference.*`
- `paint.3d_blockout.*`
- `paint.pbr.*`

Action rules:

- Dry-run/preview first for destructive operations.
- Undo transaction required for mutations.
- Stable IDs required for layers, references, paths, selections, and 3D
  blockout items.
- Tests must cover action schema, preview, execute, and sequence behavior.

## QA Gates

Minimum QA matrix before claiming production-art readiness:

- Small laptop window around 760x560.
- 1080p desktop.
- High-DPI Windows scaling.
- Empty canvas startup fit.
- Heavy brush stroke performance.
- Oil/dry/ink/pixel preset visual snapshots.
- 800% pixel grid and pixel brush behavior.
- Copy / cut / paste with internal payload and system image clipboard.
- Layer visibility, lock, opacity, blend mode, duplicate, delete, merge.
- Channel eye toggle and channel copy/paste.
- Path to selection and selection to path.
- Selection feather/expand/contract.
- Transform selection and free transform.
- Reference board add/pin/opacity/sample.
- 3D blockout box/arch scene with wire/value/bake.
- PNG export.
- PSD compatibility plan or explicit limitation.
- Action registry parity tests.

## Milestones

M0: Planning and claim cleanup

- This document is the source of truth for Painter production-art scope.
- SPEC/TODO should link here instead of duplicating large prose.

M1: Drawing-first layout

- Rebalance the Painter window around canvas, tool options, Color/Brush,
  Navigator/Reference, and Layers/Channels/Paths.
- Move Typography/PBR/3D into optional panels.

M2: Brush UX and engine pass

- Stroke-thumbnail preset library.
- Production-art brush families.
- Flow/hardness/spacing/angle/roundness/texture/smoothing wiring.

M3: Layers, masks, selections, transforms

- Layer workflow polish.
- Selection and transform completeness.
- Clipboard and mask reliability.

M4: Reference board

- PureRef-like reference placement.
- Palette extraction, value check, flip canvas, navigator, symmetry/rulers.

M5: 3D blockout

- Box/arch placement, standard transform gizmo, camera/FOV controls,
  wire/value/transparent views, bake to paint layer, action coverage.

M6: Production-art QA and docs

- Snapshot tests, action tests, manual QA checklist, honest readiness status.

## Implementation Guardrails For Agent B

- Do not add Painter feature logic to `app/video_editor_window.py`.
- Keep code changes in focused modules where possible.
- Preserve existing `paint.*` action IDs.
- Add new actions only when the UI feature can also be driven by AI/MCP.
- Keep the first implementation pass below the requested line budget.
- Do not claim Photoshop, Clip Studio, or Corel Painter parity until QA gates
  pass with real screenshots and action evidence.
