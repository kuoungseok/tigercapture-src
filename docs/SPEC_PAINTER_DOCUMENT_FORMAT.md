# Tiger Studio Painter Native Document

Status: implemented v1

## Purpose

`.tspaint` is the editable, standalone Tiger Studio Painter document format.
PNG is a flattened delivery format and is not a substitute for project
persistence. A saved Painter document must restore both the painting and the
non-destructive construction state used to continue the work.

## Container

- Extension: `.tspaint`
- Schema: `tigerstudio.painter.document.v1`
- Current format version: `1`
- Container: ZIP with `document.json` plus embedded assets
- Save: atomic temporary-file replacement
- Load: version/schema validation, safe archive paths, asset size limits, and
  SHA-256 verification

Background pixels, clipboard/sticker images, Painter references, and a PBR
source image are embedded when their source files are available. Loading
extracts those assets to a disposable runtime cache; the `.tspaint` file
remains the durable source.

## Persisted Editing State

- canvas dimensions, background pixels/presence/color, and Painter time
- ordered layers, names, visibility, opacity, lock, blend mode, color labels
- layer masks and mask enabled state
- standard and Material Paint layer types and settings
- complete editable strokes, including brush style, pressure, X/Y tilt,
  rotation, tangential pressure, load, bristle seed/count, and material values
- Wet Canvas enabled state, Mix, Bleed, Pickup, dry duration, and elapsed time
- selection geometry/inversion/mode, Quick Mask, channels, and Work Path
- active/selected layer, selected channel/path, grid, mirror, zoom, and pan
- active brush and material-light preview settings
- PBR Texture Lab settings and source
- non-destructive reference board with embedded reference images
- speech bubbles/stickers when present for compatibility

## 3D Blockout Persistence

The underdrawing 3D scene is part of the Painter document, not a disposable
preview. The format preserves:

- primitive kind/name/ID
- position, rotation, scale, color, opacity, wireframe, and lock state
- selected primitive and 3D layer
- Z-up camera target, yaw, pitch, distance, and FOV
- floor/grid, world-aligned checker behavior, Lit mode, shadows, fog, depth
  preview, light yaw/pitch, and snapping
- current Paint/3D workspace and Move/Rotate/Scale mode
- provider-neutral `tigerstudio.painter.ui.v1` UI document, including
  artboards, UI objects, hierarchy, style/content, constraints, selection,
  delivery profiles, and revision
- current Paint/UI Design/3D Place workspace
- UI workspace tool selection is transient, while every drag-created object,
  move, resize, duplicate, delete, visibility, lock, style, and geometry edit
  updates the provider-neutral UI document and participates in Painter
  Undo/Redo
- the UI workspace exposes Select, Frame, Rectangle, Ellipse, Line, Text,
  Image, Button, and Progress tools plus a dedicated `Layers | Inspect` panel
- Inspect edits name, type-readable geometry, opacity, fill, visibility, and
  lock state without converting UI objects into Paint layers
- Image-object content preserves `source_path`, `image_fit`
  (`fit/fill/stretch/tile`), `tile_scale`, `nine_slice_enabled`, and
  source-pixel `nine_slice` left/top/right/bottom margins. These values survive
  `.tspaint` round trips through the provider-neutral UI document.
- Current image preview references the source file and uses an in-memory
  modification-aware cache. Missing files render an explicit placeholder.
  Embedding UI image bytes, hashes, and density variants in the native
  container is future asset-delivery work and is not claimed by this slice.
- Every UI object normalizes an `accessibility` record with `role`, `label`,
  and `focus_order`. Focus order `0` follows document order; positive values
  are explicit. Validation warns about missing labels for semantic interactive
  roles and duplicate positive focus orders within an artboard.
- Inspect edits accessibility through the same undoable
  `paint.ui.object.update` mutation used by UI and Actions. It also presents
  read-only per-target `Native`, `Material`, `Baked`, or `Blocked` status and
  the classifier reason for Asset Export, Design Handoff, Review Prototype,
  and Unreal UMG. Delivery preflight v2 uses these same four dispositions.
- UI document version 7 normalizes each object's `layout` record. Containers
  support `none`, `horizontal`, or `vertical` mode; independent L/T/R/B
  padding; non-negative gap; main-axis `start/center/end/space_between`; and
  cross-axis `start/center/end/stretch`. Child `positioning=absolute` bypasses
  the parent's flow. Each axis supports `fixed`, `hug`, or `fill`, and fixed
  containers may wrap children into stable rows or columns. Constraint geometry
  resolves first, nested Hug sizes measure bottom-up, and placement resolves
  outer-to-inner in stable z/document order.
- Inspector edits this contract through the normal object mutation and
  Undo/Redo path. Automation uses `paint.ui.layout.set`, which delegates to
  the same `paint.ui.object.update` service rather than storing private layout
  state.
- Every artboard persists a normalized `theme` context. `light`, `dark`, and
  `high_contrast` are the built-in preview modes. Tokens preserve a default
  `value`, per-theme `theme_values`, and an optional stable
  `alias_token_id`. Object `token_bindings` use provider-neutral dotted paths
  such as `style.fill`, `style.text_color`, `layout.gap`, or `opacity`.
- Theme resolution applies responsive object overrides first, then resolves
  token aliases and themed values without changing stable object/token IDs.
  Canvas, Inspector, and layout diagnostics use this effective preview
  document. The authored base document remains unchanged.
- Inspector theme selection uses the normal artboard mutation and Undo path.
  Automation uses `paint.ui.theme.set/inspect` and
  `paint.ui.token.theme.set/remove`. A dedicated visual token library and
  binding picker remain P5 work.
- Every artboard normalizes a provider-neutral `layout_grid` record with
  `none`, `grid`, or `columns` mode, plus custom horizontal/vertical `guides`
  and safe-area insets. `safe_area_visible` controls the authoring overlay only.
  Painter renders these records clipped to the artboard, and automation edits
  them through `paint.ui.artboard.layout.set`.
- Validation v2 embeds `layout_diagnostics.v1`. Hug/Fill sizing cycles,
  inverted min/max bounds, collapsed column grids, and collapsed safe areas are
  blocking errors. Ignored Wrap and fixed-content overflow are warnings.
  `paint.ui.layout.diagnostics` exposes the same report used by delivery
  preflight and Inspector status.
- Every object owns a normalized `responsive_overrides` list. Each record has a
  stable ID, breakpoint, orientation, and a bounded `changes` map. Wildcard
  records resolve before exact context records. Base object IDs and hierarchy
  remain unchanged, and `paint.ui.responsive.override.set/remove` use the same
  object mutation and Undo path as Inspector editing.

Opening a `.tspaint` restores the editable 3D scene. Baking the blockout to 2D
is optional and does not replace the saved scene.

## UI And Automation

File menu:

- `Open...` (`Ctrl+O`)
- `Save` (`Ctrl+S`)
- `Save As...` (`Ctrl+Shift+S`)
- PNG export remains a separate command

Actions:

- `paint.document.save`
- `paint.document.open`
- `paint.ui.document.inspect`
- `paint.ui.artboard.add/update/remove`
- `paint.ui.artboard.activate`
- `paint.ui.object.add/update/remove`
- `paint.ui.selection.set`
- `paint.ui.object.arrange`
- `paint.ui.object.group/ungroup/reorder`
- `paint.ui.object.reparent`
- `paint.ui.delivery.profiles/preflight`
- `paint.ui.handoff.export`
- `paint.state` reports the native format, current path, dirty state, and 3D
  persistence capability, plus the current UI document validation and
  workspace mode

## Compatibility Boundary

The video editor `.tgp` format still owns timeline overlays. `.tspaint` is the
authoritative format for standalone Painter documents and their full 2D/3D
construction and general UI design state. Do not claim that PNG, a generated
handoff package, Unreal UMG, or the legacy stroke-only `.tgp` overlay fields
can replace `.tspaint`.
