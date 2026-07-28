# Painter UI Figma UX Development Milestones

Status: active roadmap; M0 shell, contextual inspector, and M1 ruler-guide lifecycle implemented

Date: 2026-07-29

## 2026-07-28 M0 Checkpoint

Completed in the first shell slice:

- bottom floating UI Design toolbar; it no longer reserves a full-width row
- responsive toolbar density for compact and remote displays
- left `Layers / Assets` navigation with zero-width Auto-hide, explicit Pin,
  and detachable Floating presentation
- Sections, Components, and Tokens moved into Assets
- right `Design / Prototype / Inspect` modes
- both side panels default to zero-width Auto-hide rather than permanently
  reserving canvas width
- fluid left navigator with a compact 168 px default, a usable 112 px minimum,
  no fixed expanded-width ceiling, and a persistent thin vertical scrollbar
- fluid right inspector with a compact 268 px default, a usable 180 px minimum,
  no fixed expanded-width ceiling, detachable floating-window, and automatic
  re-dock when leaving UI Design
- native horizontal workspace splitter for navigator/canvas/inspector; expanded
  side panels have no arbitrary maximum width, both dividers are directly
  draggable, and the center canvas owns the remaining space
- debounced persistence of splitter-selected navigator/inspector widths with
  correct restoration after collapse, Auto-hide, floating, and mode changes
- restart-safe persistence for user-adjusted navigator/inspector width and
  presentation; both panels now default to Auto-hide instead of permanently
  taxing canvas width
- Auto-hide now consumes zero fixed width; selecting an object opens the
  canonical Inspector as a temporary canvas popover, while Pin and Floating
  remain explicit user choices
- selection-triggered temporary Properties overlay when the right inspector is
  collapsed; it reuses the canonical inspector widget and returns it to the
  dock on close, expand, detach, or workspace change
- shared `paint.ui.inspector.presentation` Action selects `auto_hide`,
  `pinned`, or `floating` using the same canonical inspector widget
- shared `paint.ui.navigator.presentation` Action selects `auto_hide`,
  `pinned`, or `floating` using the same canonical Layers/Assets widget
- bottom-toolbar Layers/Assets and Properties buttons open temporary,
  canvas-local overlays; only explicit Pin makes a panel part of the splitter
- transient Zoom popover replaces three permanently visible Fit buttons and
  provides percentage input, Fit All, Fit Artboard, and Fit Selection
- canvas-first navigation: Space/left-drag or middle-drag pan, wheel vertical
  pan, Shift+wheel horizontal pan, and Ctrl+wheel pointer-centered zoom
- shared non-document-mutating `paint.ui.view.focus/pan/zoom/fit` Actions
- zoom-adaptive top/left rulers and ruler-drag guide creation
- shared `paint.ui.guide.create/remove/clear` and
  `paint.ui.ruler.visibility.set` automation
- grouped Shape/Content tool flyouts
- direct guide move and drag-back-to-ruler delete
- persistent guide visibility/locking and per-artboard ruler origins
- shared `paint.ui.guide.update/visibility.set/lock.set` and
  `paint.ui.ruler.origin.set/reset` automation
- Korean and supported-language shell label coverage
- selection-driven Design inspector for artboard, single object type, and
  multiple selection
- advanced disclosure for constraints, accessibility, delivery, text ranges,
  9-slice, boolean, and remote-component controls
- focused tests, architecture guard, and screenshot QA

Not complete yet:

- mode-specific Paint/3D floating-toolbar variants
- prototype interaction authoring surface and on-canvas connection editing
- M1 through M8 implementation

Related documents:

- `docs/PAINTER_UI_FIGMA_INTERFACE_SPEC_KO.md`
- `docs/PAINTER_UI_DESIGNER_MILESTONES_KO.md`
- `docs/PAINTER_UI_FIGMA_WORKLIST_KO.md`
- `docs/PAINTER_UI_FIGMA_INTERFACE_ACTION_MATRIX_KO.md`
- `docs/PAINTER_UI_TEMPLATE_RESEARCH.md`
- `docs/SPEC_PAINTER_DOCUMENT_FORMAT.md`

## 1. Research Interpretation

`ytx-readings/design-ui-ux` is not a Figma implementation repository. It is a
curated index of books about Figma, UI patterns, design systems, color, UX
psychology, prototyping, graphic design, and handoff. It should be used as a
product-principle reference, not copied as a code or UI source.

The useful product themes are:

1. Fast direct manipulation with low visual noise.
2. Reusable components, variants, variables, and libraries.
3. Responsive layout that survives content and device changes.
4. Prototype behavior attached to the same editable design objects.
5. Clear designer-to-developer inspection and delivery.
6. Templates that remain editable systems, not flattened examples.
7. Discoverability, predictable hierarchy, and reversible operations.

The current Tiger Studio foundation already covers document persistence,
multi-artboards, Auto Layout, components, variants, tokens, prototype actions,
Figma exchange, Motion links, asset delivery, and shared UMG output. The next
roadmap therefore prioritizes production UX and workflow coherence instead of
adding more disconnected controls.

## 2. Product Boundary

Painter owns:

- pages, sections, artboards, layers, and static object hierarchy
- geometry, constraints, Auto Layout, responsive overrides, and themes
- components, variants, instance overrides, tokens, and accessibility
- prototype triggers and semantic actions
- template and library authoring
- delivery inspection and target-neutral source data

Motion Designer owns:

- keyframes, easing, timing, loops, and transition choreography
- temporal transform, opacity, material, mask, and text animation
- animation clips and Motion Actor content

Output adapters own:

- Web: DOM/CSS/SVG/Canvas classification and artifacts
- App: framework-neutral native/effect/bake classification and artifacts
- Unreal: shared `TigerStudioUMG` Native/Material/Baked/Blocked output

## 3. Definition of Done

A milestone is complete only when all applicable layers exist:

1. Persistent provider-neutral document contract.
2. User-facing Painter UI.
3. Equivalent `paint.ui.*` Action/MCP surface.
4. Shared undoable mutation service.
5. Save/load and copy/paste round trip.
6. Keyboard and pointer workflow.
7. Empty, loading, error, and unsupported states.
8. Desktop, compact, and remote-screen screenshot QA.
9. Delivery classification with no silent omission.
10. Focused tests plus architecture guard.

## M0. Workspace Coherence

Goal: make UI Design feel like one finished authoring application.

Reference layout:

- The center canvas is the dominant surface, matching the supplied Figma UI3
  reference rather than the current inspector-heavy Painter layout.
- A thin left navigation panel contains Pages/Sections and the layer tree.
- A thin right contextual panel contains only the selected object's properties.
- The top edge of the canvas carries the horizontal ruler; the left canvas edge
  carries the vertical ruler.
- A compact floating toolbar is centered near the bottom of the canvas.
- The canvas continues visually behind the floating toolbar; the toolbar must
  not reserve a full-width permanent row.
- Panel sections are collapsed by default unless they contain the primary
  controls for the current selection.

Scope:

- Establish the permanent three-column workspace:
  `Pages/Layers | Canvas | Design/Prototype/Inspect`.
- Give the canvas visual priority. Side panels float over or reserve only the
  width they actually need; they must not permanently squeeze the artboard.
- Move the primary creation tools into a compact bottom toolbar:
  Move/Hand, Frame/Section/Slice, Shape, Pen, Text, Comment, Resources,
  Actions, Prototype Preview, and mode switching.
- Change the bottom toolbar contents by workspace:
  - UI Design: Move/Hand, Frame/Section/Slice, Shape, Pen, Text, Comment,
    Resources, Actions, Preview.
  - Paint: Move/Hand, Brush, Pencil, Eraser, Fill, Selection, Text, Color.
  - 3D Place: Select, Move, Rotate, Scale, Place Actor, Camera, Light.
  Tools from inactive workspaces must not remain visible.
- When a grouped tool is active, show its small flyout above the toolbar.
  Brush, Pen, Shape, and Frame variants must not expand into a permanent side
  panel merely because the tool was selected.
- Group related tools behind press/hold or flyout menus instead of exposing
  every variant as a permanent button.
- Keep the top chrome minimal: file identity, undo/redo, mode, preview, and
  delivery commands only.
- Replace developer-facing tab names and raw IDs with user-facing labels,
  icons, status badges, and tooltips.
- Apply progressive disclosure:
  - no selection: page/artboard, variables, canvas, and export settings
  - object selected: only properties supported by that object
  - component instance selected: exposed component properties first
  - Prototype mode: interactions and flow controls
  - Inspect mode: read-only handoff and delivery data
- Do not keep empty Motion, Tokens, Sections, Components, Publish, and delivery
  panels open as equal permanent tabs. Surface them through Resources, Actions,
  Prototype, Inspect, or the selected object's contextual sections.
- Add resizable, collapsible, and temporarily hidden side panels with persisted
  widths. `Minimize UI` must collapse both side panels and leave the bottom
  toolbar available.
- Use practical desktop width targets rather than equal columns:
  left panel 220-280 px, right panel 240-320 px, and all remaining width for
  the canvas. On compact windows, one side panel becomes an overlay drawer
  instead of reducing the canvas below its usable minimum.
- When UI is minimized, selecting an object may open a compact temporary
  properties popover. It closes when the selection is cleared or the user
  returns to the canvas.
- Provide compact mode for small and remote displays.
- Normalize empty states, disabled states, destructive confirmation, and
  inline validation.
- Ensure Korean/English/localized strings fit without clipping.
- Hide Paint and 3D commands that cannot operate in UI Design mode.

Exit criteria:

- A first-time user can create an artboard, add a button, edit it, and preview
  it without opening unrelated panels.
- At the default desktop window size, the canvas receives the clear majority
  of usable width and height; tool chrome must not visually dominate it.
- With no selection, no object-specific property controls are visible.
- Selecting Shape, Text, Image, Component Instance, and Prototype Connection
  produces five distinct, relevant Inspector states.
- The complete object-creation surface remains reachable from the bottom
  toolbar without keeping a tall tool strip or template panel open.
- Switching Paint, UI Design, and 3D Place changes the bottom toolbar without
  moving the canvas viewport or widening either side panel.
- No Inspector overlap, clipped text, horizontal panel scrolling, or orphaned
  controls at 1280x720, 1600x900, and 4K scaled layouts.
- Mode switching never loses selection, viewport, or panel state.

## M1. Figma-Class Canvas Editing

Goal: make object manipulation faster than Inspector-first editing.

Scope:

- Space-drag pan, cursor-centered wheel zoom, zoom-to-selection, fit artboard,
  fit all, and remembered viewport per page.
- Add optional horizontal and vertical canvas rulers. Tick density and labels
  adapt to zoom, remain aligned with the world canvas while panning, and use
  the active document unit.
- Drag from either ruler to create horizontal or vertical guides. Guides snap
  to object edges, centers, baselines, and artboard bounds; dragging a guide
  back to its ruler removes it.
- Provide ruler-origin drag/reset, guide lock, guide visibility, clear guides,
  and per-page guide persistence.
- Keep navigation canvas-first:
  - Space + drag or middle-button drag pans temporarily.
  - Mouse wheel pans vertically; Shift + wheel pans horizontally.
  - Ctrl + wheel zooms around the pointer without changing the world point
    under the cursor.
  - Trackpad pinch zooms and two-finger movement pans.
  - Hand tool is available from the Move flyout but is not required for
    temporary navigation.
- Show a compact zoom indicator only while zooming or when explicitly opened.
  It offers percentage input, Fit All, Fit Selection, and Fit Artboard without
  occupying a permanent slider-sized area.
- Clamp navigation safely, preserve subpixel viewport precision, and avoid
  rerendering unrelated panels while panning or zooming.
- Deep select, select parent, enter/exit group, and selection breadcrumb.
- Double-click text editing and direct canvas text bounds.
- Multi-select resize with individual and group bounds.
- Alt-drag duplicate and modifier-based center/proportional resize.
- Smart guides for edge, center, baseline, gap, padding, and equal size.
- Distance measurement overlay while holding the configured modifier.
- Quick Actions search for commands, layers, components, tokens, and pages.
- Context menu ordered by selection type and recent actions.
- Paste in place, paste to replace, copy/paste properties, and duplicate to
  next artboard.
- Deterministic z-order and reparent previews during Layers/canvas drag.
- Complete the frequently used creation set with Polygon, Star, Arc, and
  editable corner-count/inner-radius controls.
- Add a real Vector Network editor: node/segment selection, open/closed paths,
  straight/Bezier conversion, handle editing, join/split, outline stroke, and
  non-destructive Boolean release.
- Add a dedicated Scale tool with the `K` shortcut. It proportionally scales
  geometry, typography, corner radii, strokes, effects, layout gaps, and nested
  content instead of only resizing outer bounds.
- Add image-place and image-fill canvas controls for crop, fit, fill, tile,
  focal point, replace, and restore original dimensions.

Required Actions:

- `paint.ui.view.focus`
- `paint.ui.view.pan`
- `paint.ui.view.zoom`
- `paint.ui.view.fit`
- `paint.ui.ruler.visibility.set`
- `paint.ui.ruler.origin.set/reset`
- `paint.ui.guide.create/update/remove/clear`
- `paint.ui.guide.visibility.set`
- `paint.ui.guide.lock.set`
- `paint.ui.selection.parent`
- `paint.ui.selection.deep_select`
- `paint.ui.object.properties.copy`
- `paint.ui.object.properties.paste`
- `paint.ui.object.paste_replace`
- `paint.ui.vector.node.*`
- `paint.ui.vector.segment.*`
- `paint.ui.vector.path.join/split`
- `paint.ui.object.scale`
- `paint.ui.image.place`
- `paint.ui.image.fill.set`
- `paint.ui.quick_action.search`

Implemented checkpoint (2026-07-29, hierarchy navigation slice):

- `paint.ui.selection.parent` selects the immediate stable-ID parent and keeps
  a root selection unchanged when no parent exists.
- `paint.ui.selection.deep_select` selects the deepest topmost child or cycles
  the deterministic hit stack when canvas coordinates are supplied.
- Alt-click cycles overlapping objects through the same canvas hit-test stack.
- A compact canvas breadcrumb appears only for nested selections and lets the
  user jump to any visible ancestor without mutating document history.
- The UI context menu, breadcrumb, and Actions share the same selection service.
- Double-click enters a frame/group editing scope and Escape exits one level.
  Nested scopes use a stack, dim and exclude outside objects from canvas hit
  testing, and keep the active scope outlined without changing document
  revision or undo history.
- `paint.ui.selection.scope.inspect/enter/exit` expose the same group scope to
  automation.

Implemented checkpoint (2026-07-29, adaptive Inspector slice):

- The right Inspector is not a fixed set of controls. The artboard selector is
  visible only in the no-selection document context.
- Single selection changes the header to the selected object kind and exposes
  Design, Prototype, and Inspect; no selection and multiple selection hide the
  irrelevant Prototype surface.
- Context changes preserve the user's pinned, Auto-hide, resized, or detached
  presentation and fall back to Design only when the active tab becomes
  unavailable.

Implemented checkpoint (2026-07-29, real image Place/Fill slice):

- `Place image...` is available from Quick Actions, the UI context menu, and
  an OS file chooser; local image files can also be dropped directly on any
  visible artboard at the mapped canvas position.
- `Set image fill...` replaces the selected Image, Rectangle, Frame, Ellipse,
  or Button image while preserving its stable object ID.
- The contextual Image Inspector provides fit/fill/stretch/tile, tile scale,
  normalized focal X/Y, replacement source, and original-dimension restore.
- Canvas preview and PNG/SVG-bake asset delivery use the same image draw plan.
  Shape fills preserve rounded/ellipse clipping instead of leaking through a
  rectangular fallback.
- `paint.ui.image.place` and `paint.ui.image.fill.set` use the same mutation
  service as the UI and create one reversible Undo step.
- `.tspaint` packages embed external UI image sources under `assets/ui-images`
  and restore extracted paths during load, so the design does not depend on
  the original import location.
- Quick Actions retain English source terms in their search index while
  displaying the active Painter language, including the new image and
  Inspector presentation commands.
- Automated desktop and 900x650 compact captures verify the real image fill,
  translated command palette, zero-width Auto-hide, temporary Properties
  popover, and resizable/detachable Inspector states.

Implemented checkpoint (2026-07-29, inline text editing slice):

- Double-clicking an unlocked text object opens a canvas-native plain-text
  editor over the resolved object bounds instead of sending the user to the
  Inspector.
- `Ctrl/Cmd+Enter` or focus-out commits one `Edit UI text` undo step; Escape
  cancels without document mutation.
- The original rendered label is suppressed while editing, and the editor
  follows pan/zoom and resolved responsive geometry.
- `paint.ui.text.content.set` uses the same stable object/content contract for
  automation and rejects non-text objects explicitly.

Implemented checkpoint (2026-07-29, multi-selection resize slice):

- Two or more visible, unlocked objects on one artboard use one common
  selection boundary with four corner handles.
- Dragging a common handle preserves each object's position and size relative
  to the original group bounds instead of collapsing objects onto one edge.
- Shift preserves the common selection aspect ratio and Alt resizes from its
  center, matching the single-object canvas modifiers.
- Cross-artboard or locked selections remain visibly selected but do not expose
  a misleading common resize handle.
- Canvas resize commits one batch mutation and one Undo step.
  `paint.ui.property.batch_set` uses the same constraint-aware mutation service
  for automation.

Implemented checkpoint (2026-07-29, multi-selection Inspector slice):

- The Inspector remains selection-driven: its compact Common section exists
  only when two or more objects are selected.
- Opacity, Fill, Stroke, Stroke Width, Radius, Visible, and Locked show their
  shared value or a `—`/partial-check mixed state.
- Editing one common property updates only that property on every selected
  object, preserving each object's unrelated style and content.
- UI batch edits and `paint.ui.property.batch_set` use the same mutation
  service, constraint recapture, and one-step `Edit UI objects` Undo contract.
- The compact Korean surface and mixed-value states are covered by offscreen
  screenshot QA instead of relying only on widget tests.

Implemented checkpoint (2026-07-29, Smart Selection spacing slice):

- Multi-selection Common properties include a compact Auto/Horizontal/Vertical
  spacing selector, numeric gap field, and Tidy Up command.
- Auto chooses the dominant center-axis; a uniform gap shows its px value and
  mixed spacing shows `—`.
- Tidy Up preserves stable visual order and the first object's position while
  applying an explicit gap or an average gap that preserves the selected span.
- Locked, cross-artboard, and cross-parent selections are disabled with an
  explicit reason instead of partially moving objects.
- UI and `paint.ui.selection.tidy` share the same spacing planner,
  constraint-aware batch mutation, and one-step Undo.

Implemented checkpoint (2026-07-29, arithmetic numeric fields slice):

- Every Painter UI drag-spin field accepts absolute numbers, safe `+ - * /`
  arithmetic, leading `+/*` relative operations, parentheses, and percentage
  scaling without evaluating arbitrary code.
- The edit-start value is retained while typing, so `*1.5` and `/2` are
  deterministic even before the property is committed.
- Geometry, pivot, Auto Layout spacing/padding, opacity, stroke width, radius,
  image tile scale, typography, and line height expose a localized Reset
  command where a meaningful default exists.
- Arithmetic entry and Reset emit the field's normal commit signal, so the
  existing UI property mutation, Action parity, and one-step Undo remain the
  only document-changing path.

Implemented checkpoint (2026-07-29, object property clipboard slice):

- The UI Design canvas context menu exposes Copy Object, Copy Properties,
  Paste Properties, and Paste to Replace only when the current selection and
  clipboard make each command valid.
- Property paste copies normalized Appearance, Auto Layout, opacity, clipping,
  and kind-compatible image layout options without replacing stable ID,
  geometry, hierarchy, text, or source assets.
- Paste to Replace may change kind, size, presentation, and content while
  preserving the target stable ID, artboard, parent, position, name, and
  z-order so prototype and Motion references remain valid.
- UI and `paint.ui.object.properties.copy/paste` /
  `paint.ui.object.paste_replace` use `app/painter_ui_property_clipboard.py`,
  one-step Undo, and the same normalized batch mutation service.

Implemented checkpoint (2026-07-29, Figma-style Scale slice):

- Scale is selection-local and appears in the canvas context menu only when an
  object selection exists; it does not add another fixed Inspector section.
- One percentage input scales a selection around its common center. Automation
  may additionally choose separate X/Y factors and a center or corner pivot.
- Geometry, typography, corner radii, stroke width, shadow/blur geometry, and
  9-slice margins scale together instead of changing only outer bounds.
- Objects from different parent coordinate spaces are explicitly blocked
  rather than moved with ambiguous local coordinates.
- UI and `paint.ui.object.scale` share
  `app/painter_ui_object_scale.py`, constraint-aware batch mutation, and one
  `Scale UI objects` Undo step.

Implemented checkpoint (2026-07-29, Quick Actions slice):

- The bottom floating toolbar exposes one search icon and `Ctrl+/` opens the
  same transient canvas overlay; no fixed command panel reduces canvas width.
- One ranked search combines contextual commands, active-artboard layers,
  pages/artboards, component assets, and design-token variables.
- Selection-only commands remain visible but disabled when invalid, making the
  current context explicit without allowing partial mutations.
- Layer and page results navigate directly, component results insert through
  the existing stable-ID component service, and token results reveal the
  existing Assets library rather than duplicating another token UI.
- Static labels and search terms use Painter localization. Desktop and compact
  overlays clamp to canvas bounds, elide long rows, and avoid horizontal
  scrolling.
- UI search and `paint.ui.quick_action.search` share
  `app/painter_ui_quick_actions.py`; mutating results call their existing
  focused services and retain their established Undo contracts.
- Quick Actions also exposes Inspector `Auto-hide`, `Pin`, and `Open as
  window`. These presentation-only commands and
  `paint.ui.inspector.presentation` call the same workspace service; no fixed
  settings panel or document mutation is introduced.

Exit criteria:

- Common object editing is possible without repeatedly moving to Inspector.
- Canvas and Layers selection always agree.
- Ruler ticks, guide positions, snapping, and object coordinates remain aligned
  at 25%, 100%, 400%, and 800% zoom.
- Pointer-centered zoom keeps the same canvas point under the pointer, and
  repeated zoom/pan does not accumulate visible drift.
- Pan and zoom do not rebuild the Inspector, template browser, or layer model.
- One undo reverses one visible user intention.
- 500-object and 20-artboard documents remain interactively usable.

## M2. Contextual Inspector and Auto Layout

Goal: turn the Inspector into a compact decision surface.

Scope:

- Context sections: Position, Layout, Appearance, Typography, Content,
  Component, Prototype, Accessibility, Delivery.
- Mixed-value display and batch editing for multi-selection.
- Scrubbable numeric fields, arithmetic input, reset, bind-token, and
  per-property copy/paste.
- On-canvas Auto Layout handles for direction, padding, gap, alignment, and
  absolute positioning.
- Visual Hug/Fill/Fixed controls and clear conflict diagnostics.
- Min/max size, wrap, clipping, overflow, and scroll-container behavior.
- Responsive preview matrix for desktop/tablet/mobile and portrait/landscape.
- Content stress presets: long Korean, long English, large type, missing image,
  and empty list.
- Suggested-token affordance when a raw value matches an existing scoped token.
- Add variable-font axis controls and preserve named OpenType axis values in
  `.tspaint`, Figma exchange, canvas preview, and delivery preflight.
- Add Smart Selection/Tidy Up handles for list and grid selections, including
  uniform gap editing and stable reordering.
- Extend layout grids from the existing uniform/column foundation to rows,
  multiple grid definitions, stretch/center alignment, and reusable grid
  styles.

Implementation checkpoint (2026-07-29):

- Direction, main/cross alignment, item gap, four-edge padding, and child
  flow/absolute positioning now have transient on-canvas controls.
- Gap and padding are direct-manipulation drags; click controls commit through
  the existing normalized Auto Layout object mutation and one-step Undo path.
- The same data remains available to `paint.ui.layout.set`; no canvas-only
  shadow state or new document schema was introduced.
- Reproducible proof is generated by `tools/qa_painter_ui_designer.py` as
  `painter_ui_designer_m2_auto_layout_canvas.png`.
- Width/height `Fixed / Hug / Fill` are now direct segmented controls rather
  than opaque combo boxes. Selection-local errors/warnings include recovery
  guidance in the same Layout section.
- `paint.ui.property.inspect` and `paint.ui.property.reset` now share
  normalized defaults, token binding inspection, layout diagnostics, object
  update, persistence, and one-step Undo.
- QA proves a permitted Fixed-overflow warning without bypassing the validator
  in `painter_ui_designer_m2_sizing_diagnostics.png`.
- Content Test now offers long Korean, long English, large type, missing image,
  and empty-list presets for the selected stable object subtree. Only the
  canvas Overlay receives the generated preview document; Inspector, Layers,
  save data, canonical revision, and Undo history remain unchanged.
- The Inspector and `paint.ui.layout.stress_preview` call the same presentation
  entry point. The pure planner lives in
  `app/painter_ui_stress_preview.py`, and `preset: none` clears the preview.
- Desktop and compact proof are generated as
  `painter_ui_designer_m2_content_stress.png` and
  `painter_ui_designer_m2_content_stress_compact.png`.
- Raw Fill, Stroke, Radius, typography, spacing/padding, opacity, shadow, and
  image values now receive a compact suggested-token affordance only when an
  unbound, type-compatible token resolves to the exact same value in the
  active artboard theme. Alias chains are resolved before comparison.
- `paint.ui.token.suggest` calls the same pure planner and never changes the
  document, revision, persistence, or Undo history. Accepting a suggestion
  reuses the existing stable-ID token-binding mutation and one-step Undo path.
- Desktop and compact proof are generated as
  `painter_ui_designer_m2_token_suggestions.png` and
  `painter_ui_designer_m2_token_suggestions_compact.png`.
- Text and Button contexts now expose opt-in `wght`, `wdth`, and `opsz`
  controls. Only enabled four-character OpenType tags are persisted in
  `style.font_axes`; normalization rejects malformed or non-finite values.
- `paint.ui.typography.variable_axis.set/reset` and the Inspector use the same
  focused mutation service, stable object IDs, persistence, and one-step Undo.
- Canvas, inline text editing, and deterministic asset rendering apply axes
  through the local Qt variable-font API. Figma plugin exchange preserves axes
  in Tiger Studio shared plugin metadata.
- Shared UMG delivery does not silently flatten variable axes: affected text is
  classified `Blocked` with
  `variable_font_axes_require_unavailable_text_bake` until a real
  deterministic text-bake generator exists.
- Desktop and compact proof are generated as
  `painter_ui_designer_m2_variable_font_axes.png` and
  `painter_ui_designer_m2_variable_font_axes_compact.png`.
- Document schema 15 adds ordered `layout_grids[]` while retaining
  `layout_grid` as the first-definition compatibility view. Uniform, Columns,
  and Rows definitions can coexist on one artboard.
- Columns and Rows support Stretch or Center alignment; centered definitions
  use explicit cell size and the canvas renders every visible definition.
- `paint.ui.artboard.layout.set` accepts the same ordered definitions. Proof is
  generated as `painter_ui_designer_m2_multiple_layout_grids.png`.
- Reusable named grid styles now have stable IDs, Inspector
  save/apply/update/remove controls, linked-artboard propagation, reference-safe
  removal, Undo/Redo, and `paint.ui.layout_grid.style.*` Action parity.

Required Actions:

- `paint.ui.property.inspect`
- `paint.ui.property.reset`
- `paint.ui.property.batch_set`
- `paint.ui.layout.stress_preview`
- `paint.ui.selection.tidy`
- `paint.ui.typography.variable_axis.set/reset`
- `paint.ui.layout_grid.style.*`
- `paint.ui.token.suggest`

Exit criteria:

- A card component responds correctly to text, image, and viewport changes.
- Impossible constraints identify the exact objects and recovery actions.
- Raw values that duplicate tokens are discoverable without blocking work.

## M3. Component and Variable Workflow

Goal: make reuse and state authoring the default workflow.

Scope:

- Component set canvas with visible variant axes and property controls.
- Component property types: text, boolean, instance swap, variant, number, and
  exposed nested property.
- Instance override panel with reset per property and reset all.
- Nested-instance swap and preferred-value lists.
- Component playground that changes properties and variable modes without
  altering the source document.
- Variable collections with color, number, string, and boolean types.
- Modes for theme, density, locale, platform, and product brand.
- Alias-chain viewer, scope validation, usage graph, and safe rename.
- Publish/update review for local libraries with affected-instance preview.
- Missing-library recovery that offers relink, localize, replace, or preserve.
- Add named Color, Text, Effect, and Layout Grid Styles as a user-facing layer
  above raw tokens. Styles may reference token IDs but retain a stable style ID,
  description, usage count, and update history.
- Add local library packages for components, styles, variables, and assets with
  explicit install, update review, accept, defer, and rollback.

Required Actions:

- `paint.ui.component.playground.inspect`
- `paint.ui.component.override.reset`
- `paint.ui.component.override.reset_all`
- `paint.ui.variable.collection.*`
- `paint.ui.variable.mode.*`
- `paint.ui.style.*`
- `paint.ui.library.package.export/install`
- `paint.ui.library.update.inspect`
- `paint.ui.library.update.apply`

Exit criteria:

- One component family supports size, state, icon, label, and theme variation
  without duplicated manual frames.
- Library updates show a reviewable diff before changing instances.
- Alias cycles, stale instances, and missing sources cannot fail silently.

## M4. Prototype as a First-Class Mode

Goal: let designers validate behavior without turning Painter into a timeline
editor.

Scope:

- Design/Prototype switch in the right panel.
- Canvas prototype nodes and draggable connections.
- Triggers: click, double-click, hover, press, focus, keyboard, delay, mouse
  enter/leave, drag, and bounded gamepad input.
- Actions: navigate, back, open/close/swap overlay, scroll to, change variant,
  set variable, set variable mode, conditional branch, play sound, and play
  Motion clip.
- Transitions: Instant, Dissolve, Move In/Out, Push, Slide, and Smart Animate.
  Smart Animate matches stable object IDs and compatible component descendants;
  unmatched or unsupported properties receive an explicit fallback report.
- Multiple ordered actions on one trigger.
- Overlay placement, background dismissal, modal focus trap, and restoration.
- Scrollable frames support horizontal/vertical/both overflow, fixed/sticky
  children, initial scroll position, and nested-scroll conflict diagnostics.
- Flow starting points and device preview.
- Interactive component inheritance and instance-level additive interactions.
- Broken-link diagnostics and visible recovery.
- Preview inspector showing current variables, active state, focus, and event
  log.

Required Actions:

- `paint.ui.prototype.connection.create/update/remove`
- `paint.ui.prototype.flow.*`
- `paint.ui.prototype.variable.set`
- `paint.ui.prototype.condition.*`
- `paint.ui.prototype.transition.set`
- `paint.ui.prototype.scroll.set`
- `paint.ui.prototype.debug.inspect`

Exit criteria:

- A multi-screen checkout flow works with keyboard and pointer input.
- Button hover/pressed states work through component inheritance.
- Light/dark mode and localized content can change inside Preview.
- Motion remains linked by canonical binding; no keyframes are duplicated into
  Painter.

## M5. Template and Library Product Loop

Goal: turn templates into the main acceleration advantage.

Scope:

- Full-width template browser below the application menu, separate from the
  property Inspector.
- Search, category, platform, industry, complexity, theme, accessibility, and
  delivery-target filters.
- Large visual thumbnails with desktop/mobile paired previews.
- Favorites, recent, installed, update available, and authored-by-me views.
- Preview-before-use with pages, components, tokens, interactions, fonts,
  dependencies, license, and target compatibility.
- Insert Page, Insert Component Set, Apply Theme, or Create New Document.
- Original Tiger templates for mobile, web, desktop app, broadcast, game HUD,
  presentation, commerce, dashboard, forms, and design systems.
- Template package validation, deterministic thumbnails, versioning, migration,
  attribution, and license preservation.
- Starter design-system kits with tokens, primitives, controls, patterns, and
  accessibility states.
- AI template selection must use the same catalog and return an editable plan,
  not flattened generated imagery.

Required Actions:

- `paint.ui.template.search`
- `paint.ui.template.preview`
- `paint.ui.template.insert`
- `paint.ui.template.favorite.set`
- `paint.ui.template.update.inspect/apply`
- `paint.ui.library.asset.search/insert`

Exit criteria:

- A user can produce a coherent responsive app flow without rebuilding common
  controls.
- Every installed template remains editable and carries source/license data.
- Catalog quality is measured by completed workflows and visual QA, not only
  item count.

## M6. Dev Mode and Delivery

Goal: make handoff explicit, inspectable, and target-aware.

Scope:

- Separate Design and Inspect/Dev modes.
- Ready-for-development status on sections, frames, components, and instances.
- Selection inspection for bounds, spacing, Auto Layout, typography, colors,
  variables, assets, accessibility, and interactions.
- Annotations and measurements can be pinned to stable objects, exported in
  handoff reports, and hidden from normal design editing.
- Variable detail view with collection, mode, resolved value, alias chain, and
  scope.
- Component playground and variant/property table in Inspect mode.
- Revision comparison and changed-property summary.
- Copyable target-neutral values plus adapter-generated CSS/Web, iOS, Android,
  App, and UMG snippets only where a real adapter owns them. Generated snippets
  must identify the adapter and unsupported properties.
- Resource export, checksums, density variants, 9-slice, and atlas metadata.
- Per-feature delivery disposition:
  `Native`, `Vector/Platform Effect/Material`, `Baked`, `Actor Only`, `Blocked`.
- Blocker reason and remediation beside the affected property.

Required Actions:

- `paint.ui.dev.ready.set`
- `paint.ui.dev.inspect`
- `paint.ui.dev.annotation.*`
- `paint.ui.dev.measurement.inspect`
- `paint.ui.dev.revision.compare`
- `paint.ui.delivery.feature.inspect`
- `paint.ui.delivery.artifact.open`

Exit criteria:

- A developer can reconstruct supported layout without asking for hidden
  spacing or token values.
- Web, App, and UMG never share a misleading generic support flag.
- UMG support is claimed only after shared TigerStudioUMG generation, compile,
  reopen, and real capture validation.

## M7. Performance, Accessibility, and Release QA

Goal: make the workflow reliable enough for daily production.

Scope:

- Retained canvas rendering, dirty-region updates, thumbnail virtualization,
  and background asset decoding.
- Performance budgets for object count, artboards, images, components, and
  prototype transitions.
- Keyboard navigation, focus visibility, contrast, touch-target, semantic
  label, and reading-order audit.
- Locale overflow and font fallback audit.
- Crash-safe autosave and recoverable document snapshots.
- Find/Replace for text, component, style, variable, font, and asset references
  with preview and selective apply.
- Select Similar/Select All With Same for kind, fill, stroke, text style,
  component, variant, token, effect, and interaction.
- Multi-edit across compatible components and artboards, plus pattern-based
  batch layer rename with preview.
- A searchable keyboard-shortcut map and command conflict diagnostics.
- Deterministic screenshot scenarios for desktop, compact, remote, and mobile
  review.
- Round-trip corpus for `.tspaint`, Figma exchange, template packages, handoff,
  Review Prototype, and UMG.
- Action/UI parity report and orphan Action detection.

Exit criteria:

- Pan, zoom, selection, and resize stay responsive under the release corpus.
- Automated QA catches clipping, overlap, blank canvas, stale references,
  unsupported delivery, and mojibake.
- Release evidence includes real authoring UI, prototype behavior, exported
  artifacts, and target runtime captures.

## M8. Advanced Tiger Studio Integration

Goal: translate useful advanced Figma product directions into Tiger Studio
capabilities without duplicating existing applications.

Scope:

- Figma AI/Agent equivalent uses registered `paint.ui.*` Actions to generate a
  reviewable design plan, editable objects, components, variables, and
  interactions. It cannot directly mutate private document JSON.
- Figma Make equivalent becomes AI Prototype Build: prompt to editable Painter
  UI plus bounded prototype logic, followed by Web/App/UMG preflight.
- Figma Motion remains the existing canonical Painter-Motion Designer bridge;
  Painter does not gain a duplicate timeline.
- 3D transformations reuse Painter 3D Place and Motion Designer 2.5D/3D
  composition through stable bindings instead of flattening the source.
- Figma Sites equivalent is a Web delivery adapter with responsive HTML/CSS/
  SVG/Canvas classification, preview, and publish package. Hosting is a
  separate optional provider.
- Figma Slides equivalent delegates presentation authoring to Tiger Studio PPT
  Maker while preserving shared components, tokens, and assets.
- Figma Draw equivalent combines the existing Painter brush engine with the
  new UI Vector Network tools through explicit Convert to Paint/Vector actions.
- Shaders and Materials reuse Painter Material Paint, Texture Lab, Motion
  effects, and UMG UI Materials. Every target reports Native, Platform Effect/
  Material, Baked, Actor Only, or Blocked.
- Plugins and arbitrary third-party widgets are intentionally excluded from
  this roadmap. A future extension API must be separately sandboxed and
  versioned.

Required Actions:

- `paint.ui.ai.prototype.plan/apply`
- `paint.ui.web.preflight/package`
- `paint.ui.ppt.send`
- `paint.ui.convert.to_paint/to_vector`
- `paint.ui.advanced_delivery.inspect`

Exit criteria:

- AI output remains editable and passes the same Action, Undo, validation, and
  delivery contracts as manual work.
- Cross-application links preserve stable IDs and do not duplicate canonical
  Motion, PPT, 3D, or material data.
- No advanced feature is claimed from a mock preview without a real artifact.

## 4. Recommended Execution Order

1. M0 Workspace Coherence
2. M1 Figma-Class Canvas Editing
3. M2 Contextual Inspector and Auto Layout
4. M3 Component and Variable Workflow
5. M4 Prototype as a First-Class Mode
6. M5 Template and Library Product Loop
7. M6 Dev Mode and Delivery
8. M7 Performance, Accessibility, and Release QA
9. M8 Advanced Tiger Studio Integration

M0-M2 should be treated as the next product-quality release. M3-M5 form the
design-system and template release. M6-M7 form the production handoff release.
M8 integrates existing Tiger Studio applications only after the core design
workflow is production-ready.

## 4.1 2026-07-28 UI-P0 Checkpoint

- The UI Design shell now uses an icon-first floating creation toolbar with
  grouped Shape and Content flyouts.
- The template strip is fixed to a compact 34 px band with smaller preview
  targets; the full gallery remains available from the leading grid button.
- The right inspector defaults to a 36 px Auto-hide rail in the standalone
  Painter window, so the canvas receives the width until properties are needed.
  Its temporary overlay uses compact labels, tabs, fields, buttons, and rows.
- The left navigator defaults to 168 px, can be resized from 136-320 px, and
  keeps Pages/Layers/Assets reachable through a thin vertical scrollbar.
- The right inspector can be resized from 240-420 px or detached into a
  floating window; leaving UI Design re-docks the canonical inspector widget.
- These are flexible splitter ranges, not fixed slots. The left navigator,
  canvas, and pinned Inspector share one horizontal splitter; dragging either
  boundary reallocates canvas space immediately and saves the resulting width
  after the interaction settles.
- Design contents are not a fixed property dump. Artboard settings appear only
  without object selection; text, image, frame/group/button, component, and
  multiple-selection contexts expose only relevant rows.
- Advanced properties keep constraints, responsive limits, accessibility,
  delivery, text-range, 9-slice, boolean, and remote-link controls available
  without occupying the default authoring surface.
- Collapsing the right inspector leaves only a 36 px rail. Selecting a new
  object opens the same canonical Design inspector as a temporary canvas
  overlay; closing it suppresses repeat opening for that selection and a new
  selection may open it again.
- Pinning restores the remembered 240-420 px resizable panel; Floating moves
  the same widget to its detachable window. `paint.ui.inspector.presentation`
  exposes all three states without creating parallel property editors.
- Rulers and persistent artboard guides remain visible without consuming
  inspector space.
- Zoom controls are temporary rather than fixed chrome. A single toolbar icon
  opens percentage and fit commands, while wheel zoom shows a short-lived
  percentage indicator. UI and automation use the same view methods.
- Compactness is covered by widget geometry tests and real offscreen screenshot
  QA; controls may not overlap or silently disappear at the compact width.

## 5. Main Risks

- Feature breadth can hide weak day-to-day UX. Measure task completion, not
  control count.
- Figma import parity does not guarantee native Painter editability.
- Components, variables, and responsive layout can create reference cycles and
  stale derived state.
- Prototype variables and conditions can become a second application runtime;
  keep the expression surface bounded and deterministic.
- Template volume without visual quality, licensing, and update handling will
  make the product feel cheaper rather than richer.
- Generated Web/App/UMG claims must follow actual adapter artifacts and tests.
- Painter must not absorb Motion Designer's timeline and keyframe ownership.
- Large documents require virtualization and retained rendering before adding
  more authoring metadata.

## 6. Research Sources

- `ytx-readings/design-ui-ux` repository index:
  https://github.com/ytx-readings/design-ui-ux
- Figma Auto Layout:
  https://help.figma.com/hc/en-us/articles/360040451373-Explore-auto-layout-properties
- Figma variables:
  https://help.figma.com/hc/en-us/articles/15339657135383-Guide-to-variables-in-Figma
- Figma interactive components:
  https://help.figma.com/hc/en-us/articles/360061175334-Create-interactive-components-with-variants
- Figma overlays:
  https://help.figma.com/hc/en-us/articles/360039818254-Create-Overlays-in-your-Prototypes
- Figma Dev Mode:
  https://help.figma.com/hc/en-us/articles/15023124644247-Guide-to-Dev-Mode
