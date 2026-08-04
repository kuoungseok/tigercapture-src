# Tiger Studio Painter Native Document

Status: implemented v3; v1/v2 migration supported

## Purpose

`.tspaint` is the editable, standalone Tiger Studio Painter document format.
PNG is a flattened delivery format and is not a substitute for project
persistence. A saved Painter document must restore both the painting and the
non-destructive construction state used to continue the work.

## Container

- Extension: `.tspaint`
- Schema: `tigerstudio.painter.document.v3` (v1/v2 documents migrate on open)
- Current format version: `3`
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
- document-sized 8-bit raster layer-mask PNG assets, enabled state, and
  linked/unlinked transform state; v2 polygon masks rasterize on open
- standard and Material Paint layer types and settings
- complete editable strokes, including brush style, pressure, X/Y tilt,
  rotation, tangential pressure, load, bristle seed/count, and material values
- Wet Canvas enabled state, Mix, Bleed, Pickup, dry duration, and elapsed time
- selection geometry/inversion/mode, Quick Mask, channels, and Work Path
- active/selected layer, selected channel/path, grid, mirror, zoom, and pan
- editable 1/2/3-point perspective ruler state, off-canvas vanishing points,
  and the separate brush-snap toggle
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
- UI document version 9 normalizes each object's `layout` record. Containers
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
- Effective preview resolves component state and local Instance overrides,
  then responsive object overrides, then token aliases and themed values
  without changing stable object/token IDs.
  Canvas, Inspector, and layout diagnostics use this effective preview
  document. The authored base document remains unchanged.
- Inspector theme selection uses the normal artboard mutation and Undo path.
  Automation uses `paint.ui.theme.set/inspect` and
  `paint.ui.token.theme.set/remove`.
- The dedicated `Tokens` Inspector tab groups all typed token kinds, edits
  default and Light/Dark/High Contrast values, assigns aliases, reports direct
  bindings and alias references, and identifies unused tokens. Its binding
  picker writes stable token IDs to supported provider-neutral object paths.
  Automation uses the equivalent read-only
  `paint.ui.token.library.inspect` and undoable
  `paint.ui.token.bind/unbind` Actions.
- Token-library JSON uses
  `tigerstudio.painter.ui.token_library.v2` with source document metadata,
  stable Variable Collection/Mode records, and normalized token records.
  Import also accepts v1 and the legacy handoff token-array form. ID conflicts
  require `update`, `skip`, or `regenerate`; regenerate rewrites imported
  alias references to the corresponding new stable IDs.
  `paint.ui.token.library.import/export` and the Tokens tab share this service.
- Component Definitions and Instances remain ordinary UI object subtrees.
  Objects persist `component_role` (`none`, `definition`, or `instance`),
  stable `component_source_object_id`, and dotted-path `instance_overrides`.
  Instance objects receive new stable object IDs while their source IDs retain
  deterministic Definition correspondence.
- Definition property edits and direct child additions/removals synchronize to
  all Instances. Local Instance edits are recorded as overrides and reapplied
  after Definition synchronization. Inspector uses Create/Instance commands;
  automation uses `paint.ui.component.create`,
  `paint.ui.component.instantiate`, and `paint.ui.component.sync`.
- Component property definitions are typed and include a default `state` enum:
  Normal, Hover, Pressed, Focused, Disabled, and Selected. State visual
  overrides are stored per Definition source-object ID. Instance roots persist
  `component_properties`; Inspector State preview and Actions
  `paint.ui.component.property.define`,
  `paint.ui.component.state.override.set`, and
  `paint.ui.component.instance.property.set` use the shared undoable mutation
  path.
- Variants are separate Definition subtrees connected by
  `base_component_id`/`variant_ids`. Their metadata stores deterministic
  canonical-to-Variant source correspondence. Switching an Instance preserves
  stable object IDs and compatible dotted-path overrides. Detach materializes
  the effective component state as ordinary local objects; Localize converts
  that result into a new independent component. Inspector and Actions
  `paint.ui.component.variant.create`,
  `paint.ui.component.instance.variant.set`, and
  `paint.ui.component.instance.detach` use the shared Undo path.
- The Inspector `Components` tab derives a searchable family/Variant tree and
  Instance counts from the normalized document; it stores no private library
  state. Definition selection, Instance placement, Variant creation, and
  component rename use stable IDs and shared mutations.
  `paint.ui.component.library.inspect` exposes the same read-only report.
- Complete-document templates use
  `tigerstudio.painter.ui.template_package.v1` manifests. A manifest includes
  stable template ID, version, category, tags, artboard presets, feature list,
  author, source, and explicit license terms. Applying a built-in template
  creates a normal current-version UI document (version 27 at this checkpoint)
  and stores immutable source provenance in `linked_targets.template_source`;
  all template contents remain ordinary editable artboards, objects, tokens,
  components, and interactions.
  `paint.ui.template.catalog.inspect/apply` use the same instantiate service as
  the visual Template Gallery.
- Reusable design-system libraries use the separate versioned `.tsuilib`
  archive contract `tigerstudio.painter.ui.library_package.v1`. It packages
  component Definition subtrees, Color/Text/Effect and Layout Grid Styles,
  Variable Collections/Modes, tokens, explicit license metadata, and hashed
  image/font resources. Install/update state is external workspace state, not
  `.tspaint` document revision or Undo data.
- UI schema 21 adds stable-ID named Color, Text, and Effect Style records plus
  per-object `style_ids`. A Style stores only supported appearance properties,
  optional token-ID bindings, name, and description. Updating a Style
  materializes its values into every linked object; detaching preserves those
  values. Existing Layout Grid Styles remain artboard-owned internally but are
  exposed in the same `Styles` Assets library and Action namespace.
- UI schema 22 normalizes prototype Flow starting points under
  `linked_targets.prototype` and transition metadata under each Interaction's
  parameters. Flow and Transition changes are document revisions with one-step
  Undo; Motion clips remain stable-ID links and no keyframes are duplicated.
- UI schema 27 adds provider-neutral continuous Canvas anchors. An object may
  use `custom` independently on either constraint axis and then persists
  normalized `anchor_min_*`/`anchor_max_*` values plus UMG-compatible
  `anchor_offset_*` values. Point and stretched anchors both preserve the
  current rectangle when authored; parent resizing resolves with the same
  `SConstraintCanvas` formulas used by Unreal UMG. Older left/center/right,
  top/center/bottom, stretch, and scale records retain their prior meaning.
- Every artboard normalizes a provider-neutral `layout_grid` record with
  `none`, `grid`, or `columns` mode, plus custom horizontal/vertical `guides`,
  guide visibility/locking, and a per-artboard ruler origin
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
- `paint.ui.vector.node.add/update/remove`
- `paint.ui.vector.segment.set/split`
- `paint.ui.vector.path.closed.set/join/reverse/simplify/outline`
- `paint.ui.vector.boolean.inspect/compose/set/release`
- `paint.ui.object.duplicate`
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
