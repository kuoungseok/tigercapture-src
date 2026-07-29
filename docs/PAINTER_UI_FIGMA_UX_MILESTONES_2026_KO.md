# Painter UI Figma UX Development Milestones

Status: active roadmap; M0 shell and the M1 Page/navigation foundation implemented

Date: 2026-07-29

## 2026-07-29 M1 Page Checkpoint

Completed in the Page/navigation slice:

- UI document schema 19 adds stable-ID `pages[]`, `active_page_id`, and
  per-artboard `page_id`; version 18 documents migrate into `Page 1`.
- UI document schema 21 adds stable-ID Variable Collections/Modes and
  per-artboard active mode selection while preserving schema 19 Pages.
- Page add, rename, activate, and delete use the canonical document mutation
  service with one-step Undo, `.tspaint` persistence, and matching
  `paint.ui.page.*` Actions.
- Every Page owns at least one artboard and remembers its most recently active
  artboard. Returning to a Page restores that artboard and its saved viewport.
- The canvas renders only the active Page while the Navigator and Inspector
  retain the complete document model.
- The left Navigator exposes compact icon commands for Page add/delete and
  inline Page rename without adding permanent canvas chrome.
- Quick Actions search real Pages separately from Artboards.
- Figma import preserves each CANVAS as a Tiger Studio Page instead of
  flattening all imported frames into one Page.
- Desktop and compact screenshot QA verifies two Pages, page-scoped artboards,
  Auto-hide width, Page controls, and responsive canvas behavior.

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
- remaining M1 direct-manipulation polish and M2 through M8 implementation

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
- `paint.ui.vector.node.add/update/remove`
- `paint.ui.vector.segment.set/split`
- `paint.ui.vector.path.closed.set/join`
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

Implemented checkpoint (2026-07-29, editable Vector Network slice):

- Painter UI schema 17 persists normalized object-local Vector Networks with
  stable node and segment IDs. Invalid/dangling segment references are removed
  during normalization without changing valid IDs.
- The bottom toolbar has a dedicated Pen/Vector tool. Double-clicking an
  unlocked path enters Vector Edit; Escape exits without mutating the document.
- Vector Edit supports node and segment selection, node and Bezier-handle drag,
  straight/Bezier conversion, segment split, node removal/join, and open/closed
  paths.
- A compact canvas-local contextual bar appears only in Vector Edit. It stays
  above the responsive bottom toolbar at desktop and compact sizes and does not
  turn either side panel into permanent chrome.
- Canvas rendering, hit testing, PNG rendering, and editable SVG export resolve
  the same typed network.
- `paint.ui.vector.node.add/update/remove`,
  `paint.ui.vector.segment.set/split`, and
  `paint.ui.vector.path.closed.set/join/reverse/simplify/outline` call the same
  pure mutation services as the UI and preserve one-step Undo plus `.tspaint`
  round-trip semantics.
- Reverse preserves stable node/segment IDs and swaps Bezier handle direction.
  Simplify removes only redundant straight anchors and never flattens a Bezier
  segment. Outline Stroke creates closed editable fill geometry, adopts the
  source stroke color, and rebases object bounds in one Undo step.
- Focused tests, the full `test_painter_ui_*` suite, the architecture guard, and
  real 1360x900 / 900x650 screenshot QA pass. Evidence is regenerated by
  `tools/qa_painter_ui_vector_network.py`.
- Expanded non-destructive Boolean authoring is implemented in schema 18:
  compatible sibling multi-selection exposes a transient icon bar; composing
  creates an editable group that retains stable operand IDs; Release removes
  only the generated group and restores operand selection.
- Canvas, PNG, and editable SVG output share
  `app/painter_ui_boolean_geometry.py`, including real Vector Network operands
  and a deterministic Exclude implementation.

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

Implemented checkpoint (2026-07-29, contextual image editing slice):

- A single selected image fill exposes Fit, Fill, Stretch, Tile, focal-point
  editing, original-size restore, and Replace in a transient canvas-local bar.
  It disappears for unrelated selections and does not become a fixed Inspector
  section.
- Fill focal position is edited with a direct on-canvas target handle. The
  handle follows selection changes and commits through the existing image-fill
  mutation service as one Undo step.
- Replace preserves the current fit mode, focal coordinates, and tile scale.
  `.tspaint` save/load retains the resulting values.
- The UI continues to share `paint.ui.image.place` and
  `paint.ui.image.fill.set`; no parallel image document contract was added.
- Desktop and compact evidence is regenerated at
  `debugCapture/painter_ui_image_context_m1`.

Implemented checkpoint (2026-07-29, Paste in Place slice):

- The selection context menu enables localized Paste in Place after Copy.
- UI and `paint.ui.object.paste_in_place` reuse complete-hierarchy
  duplication with zero offset. Descendants, stable nested IDs, component
  links, masks/Boolean dependencies, and owned interactions follow the same
  remapping contract as ordinary duplicate.
- Source coordinates and hierarchy are preserved while every copied identity
  is regenerated. The operation creates one Undo step and persists through the
  existing `.tspaint` document path.
- Desktop/compact QA first asserts exact coordinate equality, then offsets only
  the evidence copy so both hierarchies remain visible in the screenshot at
  `debugCapture/painter_ui_paste_in_place_m1`.

Implemented checkpoint (2026-07-29, contextual menu ordering slice):

- The canvas menu no longer displays disabled selection-only commands. Image,
  hierarchy, clipboard, scale, and fit rows appear only when the current
  selection can execute them.
- Up to three session-local commands are promoted under the localized Recent
  Actions heading only when they remain valid in the new context.
- Promoted rows trigger their canonical QAction, so command behavior, Actions,
  mutation, and Undo do not fork. Recent ordering does not mutate the document
  or create history entries.
- The actual product QMenu is rendered at desktop and compact sizes by
  `tools/qa_painter_ui_context_menu.py`; evidence is regenerated under
  `debugCapture/painter_ui_context_menu_m1`.

Implemented checkpoint (2026-07-29, hierarchy drop preview slice):

- Canvas dragging over a valid Frame or Group displays a localized green
  inside-target outline while the moving objects remain live under the
  pointer. Self/descendant targets are excluded to prevent cycles.
- Dropping commits geometry, parent, new-parent constraint capture, and
  deterministic z-order as one Undo step. The existing
  `paint.ui.object.reparent` service now accepts both Figma-style Frames and
  Groups.
- Layers drag replaces the ambiguous Qt indicator with explicit before/after
  lines and an inside-area highlight.
- `tools/qa_painter_ui_reparent_preview.py` verifies live desktop/compact
  rendering, resulting parent ID, order, zero-width panels, and evidence under
  `debugCapture/painter_ui_reparent_preview_m1`.

Implemented checkpoint (2026-07-29, equal-size Smart Guide slice):

- Single-object resize compares resolved visible peers on the active artboard
  and snaps width and height independently within the zoom-adjusted tolerance.
- The canvas keeps resize geometry live and displays localized Equal Width /
  Equal Height labels with exact pixel values and magenta guide axes.
- `paint.ui.smart_guide.inspect` accepts `operation=resize`, width, and height
  while remaining read-only; move inspection remains backward compatible.
- `tools/qa_painter_ui_equal_size_guides.py` verifies desktop/compact labels,
  resulting `180 x 120` document geometry, and zero-width side panels under
  `debugCapture/painter_ui_equal_size_guides_m1`.

Implemented checkpoint (2026-07-29, remembered viewport slice):

- The current artboard-backed Page list remembers an independent zoom and
  canvas center for every artboard. Switching through the canvas, Navigator,
  or `paint.ui.artboard.activate` restores the same view.
- View state stores a world-space center rather than a raw widget-pixel offset,
  so resizing the Painter window does not move the remembered design focus.
- Pan, zoom, fit, pointer navigation, and `paint.ui.view.*` Actions all pass
  through the overlay's shared `view_changed` contract.
- Native trackpad Pan/Zoom gestures use that same contract. Pinch keeps the
  world point below the cursor stable, two-finger movement preserves subpixel
  offsets, and Smart Zoom focuses the selection or active artboard.
- Mouse, trackpad, and Action panning share a minimum-visible-edge clamp, so
  every artboard cannot be pushed completely beyond recovery.
- Viewport changes remain non-document, non-Undo workspace state, while
  `.tspaint` saves and restores them under
  `workspace.ui_artboard_viewports`.
- `tools/qa_painter_ui_page_viewports.py` verifies independent Phone/Desktop
  restoration plus native gesture/clamp behavior at desktop and compact sizes
  with zero-width Auto-hide panels.
  Regenerable evidence stays under
  `debugCapture/painter_ui_page_viewports_m1`.

Implemented checkpoint (2026-07-29, large-document interaction slice):

- A reproducible 4-Page, 20-artboard, 500-object product QA now measures
  normalization, first UI synchronization, repeated Page switching, and real
  widget painting instead of inferring responsiveness from small fixtures.
- Collapsed Auto-hide Inspector content is synchronized lazily. Selecting an
  object, opening the temporary Properties popover, Pinning, or Floating still
  refreshes the canonical Inspector immediately.
- Hidden no-selection refreshes no longer rebuild Components, Tokens,
  Production, Figma resources, Motion delivery, and layer widgets.
- Vector and Boolean contextual state is evaluated once per refresh; an empty
  or single ordinary selection bypasses expensive Boolean document
  normalization.
- On the reference QA machine, initial synchronization improved from
  6382 ms to 1255 ms and median Page switching from 1224 ms to 318 ms.
  Canvas capture remained about 53 ms.
- `tools/qa_painter_ui_large_document.py` enforces generous interaction
  ceilings and writes regenerable evidence under
  `debugCapture/painter_ui_large_document_m1`.

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

Implemented checkpoint (2026-07-29, cross-artboard duplication slice):

- The UI canvas context menu and transient Quick Actions expose `Duplicate to
  next artboard`; no fixed panel or permanent toolbar control is added.
- The operation copies selected roots, their descendants, and referenced
  Boolean operands or mask targets while preserving relative hierarchy and
  artboard-local geometry.
- Object, responsive-override, Vector Network, Boolean, Mask, and owned
  interaction references receive deterministic fresh stable IDs. Internal
  prototype targets are remapped to the copied hierarchy.
- A copied component definition becomes a linked component instance instead of
  creating a second invalid definition. Existing instances retain their
  canonical definition links.
- Accessibility focus order is preserved when available and reset to `0` with
  an explicit report when the target artboard already owns that order.
- UI and `paint.ui.object.duplicate_to_artboard` share
  `app/painter_ui_cross_artboard.py`, one-step Undo, `.tspaint` persistence,
  and the same validation path.
- Desktop and 900x650 proof plus a machine-readable report regenerate through
  `tools/qa_painter_ui_cross_artboard.py`.

Implemented checkpoint (2026-07-29, transient measurement slice):

- Holding Alt draws four temporary dimension lines from the current selection
  without opening or pinning either side panel.
- Left/right/top/bottom choose the nearest same-artboard visible object whose
  perpendicular span overlaps the selection; the artboard edge is the explicit
  fallback.
- Measurements use resolved Auto Layout, responsive, and Constraint geometry,
  remain read-only, and disappear on Alt release or focus loss.
- UI and `paint.ui.dev.measurement.inspect` share
  `app/painter_ui_measurements.py`.
- Desktop and 900x650 proof plus a machine-readable report regenerate through
  `tools/qa_painter_ui_measurements.py`.

Implemented checkpoint (2026-07-29, Alt-drag duplicate slice):

- Alt press preserves overlap-cycle behavior when released without movement;
  crossing the drag threshold duplicates the current selected roots instead.
- Ctrl+D, Alt-drag, and `paint.ui.object.duplicate` use
  `app/painter_ui_duplicate.py` to copy descendants, Boolean/Mask
  dependencies, nested stable IDs, owned interactions, and component links.
- Copied component definitions become linked instances and conflicting
  accessibility focus orders reset explicitly instead of duplicating invalid
  definitions or focus positions.
- The copy and its drag coordinate commit form one Undo step. Moving a copied
  hierarchy does not add descendants to the visible selection.
- Desktop and 900x650 proof plus a machine-readable report regenerate through
  `tools/qa_painter_ui_alt_duplicate.py`; both side panels remain Auto-hide.

Implemented checkpoint (2026-07-29, resolved Smart Guide slice):

- Move snapping now reads resolved responsive, Constraint, and Auto Layout
  geometry instead of raw object coordinates.
- Existing edge and center candidates are joined by text baseline, parent
  padding, and two-sided equal-gap candidates with explicit canvas labels.
- The transient label and guide lines do not open or pin either side panel.
- UI and read-only `paint.ui.smart_guide.inspect` share
  `app/painter_ui_smart_guides.py`.
- Desktop and 900x650 proof plus a machine-readable report regenerate through
  `tools/qa_painter_ui_smart_guides.py`.

Implemented checkpoint (2026-07-29, Figma-style Scale slice):

- Scale is selection-local and appears both as a transient context command and
  as a dedicated bottom-toolbar `Scale (K)` tool; it does not add another
  fixed Inspector section.
- One percentage input scales a selection around its common center. Automation
  may additionally choose separate X/Y factors and a center or corner pivot.
- In the `K` tool, corner-handle drag is proportional by default; Alt switches
  to center-origin scaling. Preview geometry stays local until release.
- Geometry, typography, corner radii, stroke width, shadow/blur geometry, and
  9-slice margins scale together instead of changing only outer bounds.
- Objects from different parent coordinate spaces are explicitly blocked
  rather than displaying an inoperative common transform or moving with
  ambiguous local coordinates.
- UI and `paint.ui.object.scale` share
  `app/painter_ui_object_scale.py`, constraint-aware batch mutation, and one
  `Scale UI objects` Undo step.
- `.tspaint` round-trip and desktop/900x650 zero-width Auto-hide evidence
  regenerate through `tools/qa_painter_ui_scale_tool.py`.

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
- The artboard bar now opens a transient Responsive Preview Matrix instead of
  reserving another fixed Inspector section. It renders Desktop, Tablet, and
  Mobile in Portrait and Landscape simultaneously through the production
  Painter canvas renderer.
- All six previews are isolated documents with cleared selection and unchanged
  canonical revision, Undo history, active artboard, and authored values.
  Responsive overrides and themes still resolve through the normal preview
  pipeline. AI inspection uses
  `paint.ui.responsive.preview_matrix.inspect`.
- Reproducible visual evidence is generated by
  `tools/qa_painter_ui_responsive_preview.py` as
  `painter_ui_designer_m2_responsive_preview_matrix.png`.

Required Actions:

- `paint.ui.property.inspect`
- `paint.ui.property.reset`
- `paint.ui.property.batch_set`
- `paint.ui.layout.stress_preview`
- `paint.ui.selection.tidy`
- `paint.ui.typography.variable_axis.set/reset`
- `paint.ui.layout_grid.style.*`
- `paint.ui.token.suggest`
- `paint.ui.responsive.preview_matrix.inspect`

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

Implemented checkpoint (2026-07-29):

- The compact Component section now lists every explicit property and nested
  object override for the selected Instance without adding another permanent
  panel.
- `Reset` restores only the selected dotted-path value; `Reset All` restores
  component-property defaults and all member values while preserving the
  linked Instance, stable object IDs, selection, and one-step Undo.
- UI commands and `paint.ui.component.override.reset/reset_all` use the same
  validated document services. Inspector counts include the whole Instance
  subtree instead of only the selected child.
- Component selections now expose a contextual play icon that opens a
  transient Component Playground; no fixed panel reduces the canvas.
- Text, boolean, number, enum/state, and instance-swap properties rebuild an
  isolated materialized preview through the production canvas renderer.
  Source definitions, Instances, selection, canonical revision, persistence,
  and Undo history are unchanged.
- `paint.ui.component.playground.inspect` returns the same validated property
  combination report to automation. Reproducible visual evidence is generated
  by `tools/qa_painter_ui_component_playground.py` as
  `painter_ui_designer_m3_component_playground.png`.
- UI schema 21 now persists stable-ID Variable Collections, stable-ID Modes,
  per-artboard active mode maps, explicit color/number/string/boolean variable
  types, mode values, aliases, and optional binding scopes. Schema 19
  Light/Dark/High Contrast tokens migrate without changing token IDs.
- The compact Tokens/Variables Assets surface shows one Collection and active
  Mode at a time instead of reserving permanent Inspector space for every
  mode. Collection and Mode add/rename/remove, current-mode value editing,
  alias-chain/usage inspection, and artboard mode switching share the same
  document services as automation.
- `paint.ui.variable.collection.inspect/add/update/remove` and
  `paint.ui.variable.mode.add/update/remove/set` provide Action parity and
  one-step Undo. Token-library JSON v2 carries Collection/Mode records and
  remains backward compatible with v1 and legacy arrays.
- `tools/qa_painter_ui_variable_collections.py` regenerates compact-panel
  evidence as `painter_ui_designer_m3_variable_collections.png`.
- UI schema 21 now persists stable-ID Color, Text, and Effect Styles and
  per-object `style_ids`. The existing Layout Grid Style service is presented
  in the same compact `Styles` Assets library rather than duplicated.
- Creating from the current selection, applying, updating linked targets,
  detaching while preserving materialized values, referenced-delete blocking,
  token scope validation, usage counts, Undo, and automation all share
  `app/painter_ui_styles.py`.
- `paint.ui.style.library.inspect` and
  `paint.ui.style.add/update/remove/apply/unlink` provide Action parity.
  `tools/qa_painter_ui_styles.py` regenerates
  `painter_ui_designer_m3_named_styles.png`.
- Versioned `.tsuilib` packages now preserve component Definition subtrees,
  named and Layout Grid Styles, Variable Collections/Modes, tokens, explicit
  license metadata, and hashed image/font resources. Package and embedded
  resource hashes are validated before installation.
- The compact `Libraries` Assets surface lists installed and active versions,
  expands active versions into reusable component definitions, reviews
  candidate counts/hashes, and exposes Add to Canvas, Accept, Defer, and
  Rollback without adding a fixed panel. Automation uses
  `paint.ui.library.package.export/install`,
  `paint.ui.library.store.inspect`, `paint.ui.library.component.insert`,
  `paint.ui.library.update.inspect/apply`,
  `paint.ui.library.update.defer`, and `paint.ui.library.rollback`.
- Cross-document insertion namespaces component/object/style/token/variable
  IDs, extracts hashed resources into the durable local store, reuses an
  already imported definition from the same package version, and creates one
  editable instance with one Undo step. Package installation still does not
  silently mutate the current document.
- `tools/qa_painter_ui_library_component_insert.py` regenerates desktop and
  compact evidence under
  `debugCapture/painter_ui_designer/library_component_insert`.

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

Implemented checkpoint (2026-07-29):

- UI schema 22 adds stable Flow starting points and normalized Instant,
  Dissolve, Move In/Out, Push, Slide, and Smart Animate transition metadata.
- The selection-sensitive Prototype tab now starts with a compact connection
  list, trigger/action target controls, Flow selector, and transition duration
  control. Motion binding/delivery remains below it rather than being copied.
- Trigger/action coverage includes delay, mouse enter/leave, drag, bounded
  gamepad, overlay swap, scroll, variable/mode mutation, conditional branch,
  and variant change. Preview state records these events instead of reporting
  authored records as unsupported.
- UI and automation share `paint.ui.prototype.authoring.inspect`,
  `paint.ui.prototype.flow.add/update/remove/activate`, and
  `paint.ui.prototype.transition.set`. Evidence is regenerated by
  `tools/qa_painter_ui_prototype_panel.py`.
- The canvas exposes a prototype node only for the selected unlocked object.
  Dragging it to another artboard shows a curved live connection and target
  highlight, then creates the same Undoable click/navigate interaction used by
  the Inspector and Actions. Existing selected-source connections are rendered
  without occupying permanent panel space.
- Self-contained HTML Preview mirrors the expanded trigger/action surface,
  including overlay swap, component state/variant, variables and modes,
  scroll, delayed/mouse/drag/gamepad triggers, and transition timing.
  Smart Animate matches component descendants by canonical source-object ID
  and interpolates position, size, rotation, opacity, solid fill/stroke, and
  corner radius in HTML Preview. Text/image content replacement, object-kind
  changes, and blend-mode changes remain explicit discrete/crossfade fallback
  properties rather than silently claiming interpolation. The authoring report
  exposes `supported`, `partial`, or `fallback` with per-pair properties and
  concrete reasons in the compact connection list and Action result.
- `tools/qa_painter_ui_smart_animate.py` regenerates the browser runtime proof
  under `debugCapture/painter_ui_designer/smart_animate_runtime`. The current
  Playwright run observes two active property animations mid-transition, zero
  active animations after settling, and no page errors.
- Ordered interactions can be moved earlier or later from the compact
  Prototype list with icon controls. UI and automation share
  `paint.ui.prototype.connection.reorder`, so execution order, Undo, save, and
  AI authoring use the same document mutation.
- The compact Prototype panel now provides an inline, non-mutating Play/Reset
  preview debugger. It starts from the active Flow artboard, routes pointer and
  keyboard input through the authored runtime, and reports the current
  artboard, variable count, and latest event without adding a timeline.
  Preview suppresses artboard labels, grids, rulers, measurements, sections,
  selections, and edit handles so the canvas reads as the delivered UI.
  Per-interaction delay timers are scoped to the current artboard and overlays;
  Reset or navigation invalidates stale timers before scheduling the new scope.
  Actual sound/Motion playback remains explicit follow-up work rather than
  being silently claimed.

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

Implemented checkpoint (2026-07-29, shared search/preview slice):

- The full gallery and automation now share
  `app.painter_ui_template_store.search_ui_templates`; query, category,
  complexity, platform, and All/Favorites/Recent/Installed views cannot drift
  into separate UI-only filtering rules.
- `paint.ui.template.search` returns matching editable manifests plus category,
  difficulty, and inferred platform facets. `paint.ui.template.preview`
  reports pages, screens, objects, components, tokens, interactions, themes,
  source, and license without mutating the active document or recent history.
- Gallery search owns the first compact row and filters own the second, so a
  small window never collapses the query field. Selection details use an
  explicit Tiger Studio dark surface and retain readable contrast outside the
  main Painter parent window.
- Desktop and compact evidence regenerates through
  `tools/qa_painter_ui_template_search.py` under
  `debugCapture/painter_ui_designer/template_search`.
- Gallery use mode and `paint.ui.template.insert` share New Document, Insert
  Pages, Insert Component Set, and Apply Theme. Page insertion namespaces Page,
  Artboard, object, component, style, variable/mode, token, interaction,
  section, and grid-style IDs and remaps their references. Repeated insertion
  remains valid and moves imported artboards beside existing work.
- Component Set imports Definition subtrees and their design-system
  dependencies into the active artboard. Theme preserves matching target token
  stable IDs while updating values/modes so existing bindings change rather
  than becoming disconnected copies. Every mode validates before commit and
  lands as one Undo.
- Active `.tsuilib` packages now expose Component, Style, Token, Image, and
  Font rows through one `paint.ui.library.asset.search` service shared by the
  Libraries Assets tab. Search matches library and asset names and returns
  explicit kind/license/version metadata.
- `paint.ui.library.asset.insert` and the Assets button share contextual
  behavior: Component/Image add editable canvas objects; Style/Token/Font apply
  only to a compatible selection. Durable resources extract into the library
  store, imported design-system IDs are reused through
  `linked_targets.library_assets`, and each mutation is one Undo.
- Library asset panel evidence regenerates through
  `tools/qa_painter_ui_library_assets.py` under
  `debugCapture/painter_ui_designer/library_assets`.

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
- `paint.ui.dev.snippet.inspect`
- `paint.ui.dev.annotation.*`
- `paint.ui.dev.measurement.inspect`
- `paint.ui.dev.revision.compare`
- `paint.ui.delivery.feature.inspect`
- `paint.ui.delivery.artifact.open`

Implemented checkpoint (2026-07-29, Dev handoff vertical slice):

- Inspect mode now owns a compact `Inspect / Dev` surface instead of adding a
  fourth top-level workspace mode. Design, Prototype, and Inspect remain the
  only top-level modes.
- `linked_targets.dev_handoff` stores stable-ID readiness and pinned developer
  annotations without duplicating object geometry or style data.
- The shared inspection service reports resolved geometry, Auto Layout,
  typography, token bindings and alias chains, accessibility, interactions,
  nearest measurements, annotations, validation, and per-target delivery.
- UI and Actions call the same mutation service. Ready and annotation changes
  create one Undo entry and survive `.tspaint` document normalization.
- The required M6 Action surface is registered:
  `paint.ui.dev.ready.set`, `paint.ui.dev.inspect`,
  `paint.ui.dev.annotation.add/update/remove`,
  `paint.ui.dev.measurement.inspect`, `paint.ui.dev.revision.compare`,
  `paint.ui.delivery.feature.inspect`, and
  `paint.ui.delivery.artifact.open`.
- Inspector minimum-size pressure was removed. The real Inspector was captured
  at 340 px desktop and 244 px compact widths with no content overlap.
- Evidence:
  `debugCapture/painter_ui_designer/dev_handoff/dev_handoff_desktop.png`,
  `dev_handoff_compact.png`, and `report.json`.
- Verification: 389 Painter UI tests and 20 architecture/i18n guards pass.

Implemented checkpoint (2026-07-29, adapter-owned developer values):

- The selected object's variable detail now resolves its collection, active
  artboard mode, terminal alias token, resolved value, scope, alias chain, and
  alias-cycle status. Inspect does not confuse a token's base value with the
  value active on the current artboard.
- `tigerstudio.painter.ui.web_css.v1` is the first explicit Web adapter. It
  emits stable-ID CSS for supported geometry, appearance, typography, and Auto
  Layout properties and lists unsupported masks, boolean geometry, rich text,
  variable font axes, multi-fill/stroke, and blend behavior.
- App handoff exposes provider-neutral `Tiger JSON`; it is not labeled as
  SwiftUI, Compose, or another native framework adapter.
- Unreal snippets are selected directly from the real
  `painter_ui_to_umg_document()` layer output, preserving the object stable ID,
  disposition, payload, and blocker reasons.
- At this historical checkpoint iOS and Android remained visible but
  unavailable with `adapter_not_implemented`; the native-adapter checkpoint
  below supersedes that limitation.
- `paint.ui.dev.snippet.inspect` exposes the same read-only report to AI and
  automation. The compact Inspector provides adapter selection, copy, variable
  drill-down, and an internal vertical scroll surface so cards are not
  compressed at remote-work widths.
- Evidence:
  `debugCapture/painter_ui_designer/dev_handoff/dev_handoff_desktop.png`,
  `dev_handoff_compact.png`, `dev_handoff_compact_snippets.png`, and
  `report.json`.
- Verification: 393 Painter UI tests and 20 architecture/i18n guards pass.

Implemented checkpoint (2026-07-29, native developer adapters):

- `tigerstudio.painter.ui.dev_snippets.v2` adds explicit
  `tigerstudio.painter.ui.swiftui.v1` and
  `tigerstudio.painter.ui.compose.v1` adapters without relabeling the
  provider-neutral App contract.
- Inspect now emits a complete named `SwiftUI View` and Compose
  `@Composable` component skeleton for the selected object. Resolved bounds,
  opacity, rotation, solid fill, stroke, radius, text metrics, simple shadow,
  and Auto Layout direction/gap are mapped where the target owns an equivalent.
- Platform color values, SwiftUI font weights, and Android drawable names are
  normalized deterministically. Unsupported masks, Boolean geometry, mixed
  text, variable axes, multiple paints, non-solid fills, blend behavior, and
  custom Compose shadows remain visible in `unsupported`.
- `paint.ui.dev.snippet.inspect` and the existing compact Inspect selector use
  the same read-only report. SwiftUI and Compose are selectable and copyable at
  244 px without another fixed panel.
- Regenerable evidence:
  `debugCapture/painter_ui_designer/dev_handoff/dev_handoff_compact_swiftui.png`,
  `dev_handoff_compact_compose.png`, and `report.json`.
- Verification: 490 Painter UI tests pass; focused Dev/architecture tests pass
  15/15. This Windows workstation has no `swiftc` or `kotlinc`, therefore
  native compilation and device/runtime captures are explicitly `not_run`.

Implemented checkpoint (2026-07-29, Inspect component playground entry):

- Inspect reuses the existing non-destructive component playground instead of
  creating a second preview engine.
- A selected definition or instance exposes its family, active variant,
  property definitions, resolved property values, and authored states in the
  Dev surface. `Open Playground` forwards the stable component ID to the
  existing preview-only property playground.
- The existing `paint.ui.component.playground.inspect` Action and the UI both
  use `build_ui_component_playground`; preview changes do not mutate the source
  document or create Undo entries.
- Component rows remain contextual and disappear for ordinary objects. The
  compact evidence includes the component table, playground command, and
  themed code viewer without card compression.
- Verification: 394 Painter UI tests and 20 architecture/i18n guards pass.

Implemented checkpoint (2026-07-29, pinned annotation completion):

- The Dev surface now supports `Note` and `Measurement` annotations with Add,
  Update, and Delete controls. Compact widths use a two-row editor so the text
  field remains usable.
- UI mutations reuse `add_ui_dev_annotation`,
  `update_ui_dev_annotation`, and `remove_ui_dev_annotation`, matching the
  existing Actions. Each UI mutation creates exactly one Undo entry, marks the
  document dirty, and survives normal document persistence.
- `tigerstudio.painter.ui.dev.inspect.v2` adds deterministic
  `measurement_overlays`. Each measurement annotation exports its stable
  annotation/target IDs, text, and calculated object bounds/spacing report.
- Offline review packages now include `dev_handoff.json`; `inspection.json`
  embeds the same Dev report, so handoff annotations are no longer silently
  omitted from export.
- Verification: 396 Painter UI tests and 20 architecture/i18n guards pass.

Implemented checkpoint (2026-07-29, explicit desktop artifact opening):

- Review and prototype exports register their generated entrypoint as the last
  artifact. `Open Last Artifact` remains disabled until a valid export exists
  and launches only after an explicit desktop UI click.
- `resolve_painter_ui_artifact` is the shared validation boundary for UI and
  Actions. It accepts generated handoff formats and directories while blocking
  executable/unknown file types.
- The existing `paint.ui.delivery.artifact.open` Action remains read-only: it
  resolves and validates the artifact, returns
  `launch_policy=explicit_desktop_ui_only`, and never launches the shell.
  `open_painter_ui_artifact` is reserved for the explicit desktop command and
  uses `QDesktopServices`.
- Verification: 400 Painter UI tests and 20 architecture/i18n guards pass.

Implemented checkpoint (2026-07-30, real Painter UMG generation evidence):

- `tools/qa_painter_ui_unreal_umg.py` instantiates the built-in
  `mobile_onboarding` template, selects its active `390 x 844` artboard, and
  sends all eight objects through `painter_ui_to_umg_document()` and the shared
  `TigerStudioUMG` plugin. It does not create a Painter-specific Unreal plugin.
- UE 5.8 generated eight widgets, compiled and saved the Widget Blueprint, and
  returned the real asset path with no generation warning or error.
- A second `UnrealEditor-Cmd` process reopened the saved asset and its
  GeneratedClass. UE 5.8 does not expose `WidgetBlueprint.WidgetTree` through
  Python reflection after reopen, so widget count is asserted at generation
  while reopen asserts the persisted Blueprint and GeneratedClass explicitly.
- Optional `--capture-ui` launches a disposable QA project, opens the generated
  Widget Blueprint through `AssetEditorSubsystem`, captures the real Unreal
  window with WGC, and removes its one-time startup script before terminating
  only the launched QA editor.
- Evidence:
  `debugCapture/painter_ui_designer/unreal_umg/qa_report.json` and
  `painter_umg_unreal_editor.png`. The capture shows the compiled Designer
  asset with parent class `Tiger Studio Generated Widget`.

Remaining M6 validation scope:

- compile the generated SwiftUI and Compose skeletons with their native
  toolchains and capture one real target runtime for each before making
  platform-build claims;

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

Implemented checkpoint (2026-07-29, accessibility audit slice):

- `app/painter_ui_accessibility_audit.py` is the deterministic read-only audit
  owner for accessible names, duplicate or unavailable focus targets, 44 px
  touch targets, text contrast, and visual-versus-explicit reading order.
- Contrast resolves the active artboard theme and token aliases before
  inspection. Non-solid or transparent backgrounds are reported as unknown
  coverage instead of being guessed or silently passed.
- Existing `paint.ui.ai.audit` remains the canonical Action entry and now
  includes the versioned
  `tigerstudio.painter.ui.accessibility_audit.v1` report. The Product QA button
  calls the same service and does not mutate the document or create Undo.
- Publish > AI displays a compact Studio-themed result list with severity,
  stable object identity, localized rule labels, coverage, and remediation
  tooltips. Empty and successful states are explicit.
- Desktop and 244 px compact evidence plus the machine-readable report are
  regenerated by `tools/qa_painter_ui_accessibility.py` under
  `debugCapture/painter_ui_designer/accessibility`.
- Focused tests, the complete Painter UI suite, architecture guard, and Painter
  i18n guard pass. Remaining accessibility work in M7 includes keyboard focus
  visibility and locale-overflow/font-fallback corpus auditing.

Implemented checkpoint (2026-07-29, Select Similar slice):

- UI > Select Same exposes Object Type, Fill, Stroke, Text Style, Component,
  Variant, Variable, Effect, and Interaction only as an on-demand submenu.
  It does not reserve canvas or Inspector space.
- Each meaningful criterion previews its active-artboard match count. Missing
  component, variant, token, effect, or interaction values disable that row
  explicitly instead of treating empty defaults as a match.
- `app/painter_ui_select_similar.py` owns stable comparison and selection.
  UI, Quick Actions, `paint.ui.selection.similar.inspect`, and
  `paint.ui.selection.similar.select` share it.
- Selection is transient: document revision, dirty state, save payload, and
  Undo history do not change. Cross-artboard selection is not claimed until
  the canonical selection model supports it.
- Korean and supported-language labels are available through Painter i18n.
  Desktop and compact evidence plus a machine-readable report regenerate via
  `tools/qa_painter_ui_select_similar.py` under
  `debugCapture/painter_ui_designer/select_similar`.

Implemented checkpoint (2026-07-29, Find/Replace slice):

- UI > Find / Replace and Quick Actions open a transient, modeless dialog;
  no fixed Navigator, canvas, or Inspector space is reserved.
- `app/painter_ui_find_replace.py` owns deterministic preview and selective
  apply for text, font, style, variable, component, and asset categories.
  Stable match IDs let UI users or AI apply only reviewed rows.
- Style and variable references resolve exact IDs or unique names. Missing or
  ambiguous targets are blocked with a reason. Component instance references
  remain blocked here and direct users to the existing Instance Swap contract.
- UI, `paint.ui.find_replace.inspect`, and `paint.ui.find_replace.apply` share
  the service. Preview is read-only; a successful selective apply creates one
  document revision, dirty transition, and Undo step.
- Korean and supported-language labels, friendly empty states, desktop and
  compact Studio-theme screenshots, and a machine-readable QA report are
  covered. Evidence regenerates via `tools/qa_painter_ui_find_replace.py`
  under `debugCapture/painter_ui_designer/find_replace`.

Implemented checkpoint (2026-07-29, Batch Rename slice):

- UI > Batch Rename and Quick Actions open an on-demand dialog for the current
  UI selection; no fixed canvas or Inspector space is consumed.
- `app/painter_ui_batch_rename.py` previews find/replace, prefix, suffix, and
  deterministic numbering while preserving stable object IDs and hierarchy.
- Every preview row has a stable match ID and can be excluded before apply.
  No-op rows are omitted, and invalid or missing object targets fail
  explicitly.
- UI, `paint.ui.batch_rename.inspect`, and
  `paint.ui.batch_rename.apply` share the same service. Apply creates one
  document revision, dirty transition, and Undo step.
- Korean and supported-language copy plus desktop and compact evidence are
  covered. `tools/qa_painter_ui_batch_rename.py` regenerates evidence under
  `debugCapture/painter_ui_designer/batch_rename`.

Implemented checkpoint (2026-07-29, shortcut map slice):

- UI > Keyboard Shortcuts and Quick Actions open a transient, searchable
  Studio-themed dialog. It does not become another fixed Inspector panel.
- `app/painter_ui_shortcut_map.py` owns the canonical UI Design, Paint, 3D
  Place, and global catalog, search, active-mode status, and overlap-aware
  conflict diagnostics. Identical keys in mutually exclusive modes are not
  reported as false conflicts.
- UI Design mode now disables Paint-only `QShortcut` objects explicitly;
  hidden menus no longer leave Ctrl+D or Delete competing with UI commands.
- `paint.ui.shortcut.inspect` exposes the same read-only report without
  changing the document, dirty state, revision, or Undo history.
- Korean and supported-language labels, friendly empty search results, focused
  tests, and desktop/compact evidence are covered.
  `tools/qa_painter_ui_shortcut_map.py` regenerates evidence under
  `debugCapture/painter_ui_designer/shortcuts`.

Implemented checkpoint (2026-07-29, UI/Action parity slice):

- `app/painter_ui_action_parity.py` audits the live Registry instead of a
  copied Action count. It maps every `paint.ui.*` Action to one of 15 declared
  contextual UI families, verifies each family's required vertical actions,
  and reports unclassified orphan candidates separately.
- Low-level automation Actions are covered by their owning contextual surface;
  the audit does not encourage 248 permanent buttons or another fixed panel.
- UI > UI / Action Parity and Quick Actions open an on-demand read-only dialog.
  `paint.ui.action_parity.inspect` returns the same report.
- The checkpoint Registry evidence covers 257 Painter UI Actions, 15/15 surfaces,
  zero missing required Actions, and zero orphan candidates.
- Korean and supported-language labels plus desktop/compact evidence regenerate
  through `tools/qa_painter_ui_action_parity.py` under
  `debugCapture/painter_ui_designer/action_parity`.

Implemented checkpoint (2026-07-29, locale/font release corpus slice):

- `app/painter_ui_locale_audit.py` renders critical UI tabs, commands, status
  labels, and contextual copy in all six supported languages using the active
  application fallback font.
- The report separates fixed-control overflow, explicitly allowed elision,
  missing glyphs, and corrupt replacement text. Only the first, missing glyph,
  and corruption categories block release.
- UI > Locale and Font Audit and Quick Actions open a transient read-only
  report; `paint.ui.locale_audit.inspect` exposes identical evidence.
- The initial release corpus covers 11 critical strings across six languages
  with zero blocking issues. It is representative release evidence, not a
  claim that every legacy Painter sentence has been visually audited.
- Desktop and compact evidence regenerate with
  `tools/qa_painter_ui_locale_audit.py` under
  `debugCapture/painter_ui_designer/locale_audit`.

Implemented checkpoint (2026-07-29, crash-safe recovery slice):

- `app/painter_autosave.py` owns atomic `.tspaint` recovery snapshots, compact
  JSON manifests, content-hash rewrite suppression, retention pruning, and the
  single background writer.
- Dirty documents autosave every 60 seconds. File > Save Recovery Snapshot Now
  and File > Recover Autosave provide explicit on-demand access without adding
  another fixed Navigator or Inspector panel.
- Recovery data uses the durable Tiger Studio runtime data directory and never
  relies on disposable `debugCapture`.
- Restore reloads the complete Painter document payload as dirty work while
  retaining the original source path. Explicit Save clears the current session
  recovery snapshot.
- `paint.ui.recovery.inspect/create/restore/discard` provide Action parity;
  discard is explicitly destructive. Korean and all supported-language recovery
  labels are included in Painter i18n.

Implemented checkpoint (2026-07-29, keyboard focus visibility slice):

- UI Design now applies a high-contrast focus ring to buttons, tool buttons,
  inputs, checkboxes, sliders, tabs, lists, and trees. ID-specific selectors
  override the previous hover/checked styling so icon controls show a real ring.
- `app/painter_ui_focus_audit.py` inspects the visible runtime widget tree for
  Tab reachability, accessible text, and focus-ring coverage while excluding
  internal spin-box editors and scrollbars from command counts.
- UI > Keyboard Focus Audit and Quick Actions open a transient responsive
  report. `paint.ui.focus_audit.inspect` exposes the same read-only evidence.
- The desktop release surface covers 30/30 visible controls with zero issues;
  the compact surface covers 24/24 with zero issues. Actual focused-control and
  report screenshots regenerate through `tools/qa_painter_ui_focus.py` under
  `debugCapture/painter_ui_designer/focus`.
- The locale release corpus now includes the focus-audit command, and accessible
  names participate in runtime Painter localization.

Implemented checkpoint (2026-07-29, release round-trip corpus slice):

- `app/painter_ui_release_corpus.py` exercises one deterministic editable UI
  fixture through seven delivery paths: `.tspaint`, Figma plugin exchange,
  `.tstemplate`, design handoff, interactive prototype, offline review, and the
  provider-neutral Tiger UMG contract.
- The first six paths compare normalized document fingerprints after reload.
  UMG validates the provider-neutral package exactly and records Unreal compile
  and real capture as `not_run` inside the fast corpus itself. The separate
  `tools/qa_painter_ui_unreal_umg.py --capture-ui` gate now owns the real UE 5.8
  compile, reopen, and capture evidence.
- UI > UI Release Corpus and searchable Quick Actions expose a transient,
  responsive report. Desktop shows package, status, timing, and scope; compact
  layout hides timing and scope without clipping the result.
- `paint.ui.release_corpus.run` is non-mutating and returns the same report.
  Regenerable evidence and desktop/compact screenshots are produced by
  `tools/qa_painter_ui_release_corpus.py` under
  `debugCapture/painter_ui_designer/release_corpus`.
- All visible report copy participates in the six-language Painter localization
  table. The report explicitly avoids native `.fig` and Unreal runtime claims.

Implemented checkpoint (2026-07-29, document-scale performance budget slice):

- `app/painter_ui_performance_budget.py` defines versioned warning and block
  limits for objects, artboards, images, components, prototype transitions, and
  hierarchy depth. Hierarchy cycles are always release-blocking.
- The inspector normalizes a copy and never mutates the source document. It
  reports covered, warning, and blocked counts with stable metric IDs.
- UI > Performance Budget and Quick Actions open a transient responsive report;
  `paint.ui.performance_budget.inspect` exposes the same read-only contract.
- Desktop shows current, warning, and block values. Compact layout preserves
  metric/current/status and hides threshold columns without clipping.
- `tools/qa_painter_ui_performance_budget.py` regenerates Korean desktop and
  compact evidence under
  `debugCapture/painter_ui_designer/performance_budget`.
- The scale contract explicitly records `wall_clock_claim: not_measured`.
  Runtime render timing is a separate QA gate and is not inferred from counts.

Implemented checkpoint (2026-07-29, measured runtime performance slice):

- `app/painter_ui_runtime_performance.py` measures real normalization,
  responsive-resolution, layout-diagnostic, and Quick Actions calls against a
  deterministic 1,000-object document. The same run exercises real overlay
  initial display, pan/zoom, selection refresh, and viewport resize paths.
- One warmup is excluded. Three measured samples report median, minimum,
  maximum, and raw `time.perf_counter` values with explicit warning and block
  limits.
- `PainterUIDesignOverlay` keeps resolved geometry across selection-only
  refreshes, while a selection-free document fingerprint invalidates that
  cache for any render-affecting content change. Object, mask-target, parent,
  and Boolean-operand indexes remove the previous repeated full-list scans.
- Component, responsive, theme, and geometry resolvers retain defensive
  normalization by default. The canvas explicitly marks its normalized and
  already-responsive path so first display no longer normalizes the same
  1,000-object document four times.
- UI > Runtime Performance and Quick Actions open a transient responsive
  report. `paint.ui.runtime_performance.run` exposes the same non-mutating
  benchmark with bounded parameters.
- The 2026-07-29 local QA run covered 8/8 paths: normalize 39.5 ms, responsive
  resolve 6.5 ms, layout diagnostics 179.8 ms, Quick Actions 125.8 ms, initial
  canvas display 261.1 ms, pan/zoom 41.3 ms, selection refresh 88.9 ms, and
  viewport resize 38.3 ms. These values describe this machine only.
- Korean desktop/compact evidence and the machine-readable environment report
  regenerate through `tools/qa_painter_ui_runtime_performance.py` under
  `debugCapture/painter_ui_designer/runtime_performance`.

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

Implemented checkpoint (2026-07-29, M8 AI Prototype Build slice):

- `app/painter_ui_ai_prototype.py` composes the existing editable AI design
  planner with canonical Hover/Click interactions. It preserves stable object
  IDs in the reviewed preview and does not create a private prototype runtime.
- Plan is read-only and requires explicit apply. Apply validates document ID
  and source revision, requires the editable design operation, commits through
  the normal Painter UI document, and produces one Undo step.
- The Publish AI surface switches between Screen Design and Interactive
  Prototype without adding fixed canvas chrome. Its plan summary includes
  compact Web/App/UMG readiness.
- `app/painter_ui_advanced_delivery.py` classifies every object for Web, App,
  and UMG as Native, Vector, Platform Effect, Material, Baked, Actor Only, or
  Blocked. This is a capability preflight, not a generated-artifact claim.
- UI and automation share `paint.ui.ai.prototype.plan/apply` and
  `paint.ui.advanced_delivery.inspect`.
- `tools/qa_painter_ui_ai_prototype.py` regenerates Korean desktop/compact
  evidence and a machine-readable report under
  `debugCapture/painter_ui_designer/ai_prototype`.
- M8 required Paint/Vector conversion is implemented below with real artifacts,
  stable IDs, Action parity, Undo, and `.tspaint` round-trip evidence.

Implemented checkpoint (2026-07-29, M8 executable Web delivery slice):

- `app/painter_ui_web_delivery.py` adds a real responsive package rather than a
  capability-only claim. It reuses the existing prototype runtime and writes
  HTML, resolved CSS, responsive runtime, canonical design JSON, preflight, and
  a hashed manifest.
- Desktop/tablet/mobile breakpoint artboards are selected by viewport until
  the first user interaction; prototype navigation then remains authoritative.
- Token-bound colors and typography are resolved for rendering without
  replacing the canonical token references in the Painter document.
- UI and automation share `paint.ui.web.preflight/package`. Both are
  non-mutating, so exporting does not create an Undo entry or revision change.
- `tools/qa_painter_ui_web_delivery.py` loads the artifact in Qt WebEngine and
  proves nonblank desktop and 390 px compact output. Hosting remains explicitly
  out of scope.

Implemented checkpoint (2026-07-29, M8 Painter-to-PPT slice):

- `app/painter_ui_ppt_bridge.py` targets the existing shared PPT `DeckSpec` and
  `PptGeneratorWindow`; no parallel presentation model was introduced.
- Active or all artboards become slides. Text, buttons, rectangular shapes,
  lines, and valid images remain editable; unsupported exact geometry is
  individually baked and reported instead of silently simplified.
- Source aspect ratios are fitted into the 16:9 deck without stretching, and
  stable Painter artboard/object IDs survive in PPT metadata.
- Publish > Deliver and automation share `paint.ui.ppt.inspect/send`. Painter
  revision and Undo history remain unchanged because the receiving PPT deck is
  the mutated document.
- `tools/qa_painter_ui_ppt_bridge.py` captures the real PPT Maker with desktop
  and mobile slides and writes a real PPTX artifact for QA.

Implemented checkpoint (2026-07-29, M8 Paint/Vector conversion slice):

- `app/painter_ui_mode_conversion.py` provides explicit inspection and shared
  conversion services. Mode switching and export never flatten UI implicitly.
- Convert to Paint resolves layout/theme, renders the selected single-artboard
  hierarchy into a cropped transparent PNG, adds it as a durable Paint image
  layer, preserves the UI source, and creates one Undo step.
- Convert to Vector preserves the stable source object ID and style while
  replacing compatible shape geometry with editable Vector Network nodes.
  Semantic text/image/component content and locked objects are reported as
  blocked rather than silently degraded.
- UI menu, context menu, Quick Actions, and automation share
  `paint.ui.convert.inspect/to_paint/to_vector`.
- `tools/qa_painter_ui_mode_conversion.py` captures the real vector-node and
  Paint-layer results and proves `.tspaint` save/load with the converted image
  embedded.

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

## 4.2 2026-07-29 M1 Parametric Shape Checkpoint

- The grouped Shape flyout now creates Rectangle, Ellipse, Line, Polygon,
  Star, and Arc objects without adding permanent toolbar chrome.
- Polygon and Star expose point count; Star and Arc expose inner radius;
  Polygon/Star expose rotation offset; Arc exposes start and sweep angles.
- Shape controls are contextual Inspector rows and disappear for unrelated
  selections.
- `app/painter_ui_parametric_shapes.py` is the shared geometry owner for
  canvas drawing, shape-aware hit testing/masks, PNG rendering, and SVG paths.
- Painter UI document schema version 16 normalizes and round-trips the
  parametric shape content while preserving stable IDs.
- Manual UI edits and AI automation use the same `paint.ui.object.add/update`
  mutations and existing Undo/Redo path. No parallel canvas-only shape state
  is allowed.
- Focused geometry/Inspector/export tests, the full Painter UI suite, the
  architecture guard, and real desktop/compact screenshot QA cover this slice.

## 4.3 2026-07-29 M1 Editable Vector Network Checkpoint

- Schema 17 adds typed stable-ID nodes, segments, node continuity, in/out
  handles, straight/cubic segment kinds, and open/closed path state.
- `app/painter_ui_vector_network.py` is the shared mutation and path-conversion
  contract. Canvas commands and `paint.ui.vector.*` Actions must not maintain a
  second private vector model.
- `app/painter_ui_vector_context_bar.py` owns temporary Vector Edit commands
  above the bottom toolbar. It is contextual, not a fixed Inspector section.
- Desktop evidence:
  `debugCapture/painter_ui_designer_m1/painter_ui_designer_m1_vector_network.png`
- Compact evidence:
  `debugCapture/painter_ui_designer_m1/painter_ui_designer_m1_vector_network_compact.png`
- Regenerable report:
  `debugCapture/painter_ui_designer_m1/vector_network_report.json`

## 4.4 2026-07-29 M1 Non-Destructive Boolean Checkpoint

- Schema 18 adds the explicit `content.boolean.group` meaning while preserving
  legacy Boolean hosts during migration.
- `app/painter_ui_boolean.py` owns selection eligibility, compose, operation
  update, inspect, and non-destructive release.
- `app/painter_ui_boolean_context_bar.py` appears only for a compatible
  multi-selection or selected Boolean group. It never reserves side-panel
  width and replaces the old operand-ID editing workflow.
- UI and automation share
  `paint.ui.vector.boolean.compose/set/release/inspect`.
- Canvas, PNG, and SVG use one geometry resolver and hide operands only while
  their Boolean group is active.
- Desktop/compact evidence and report regenerate through
  `tools/qa_painter_ui_boolean_authoring.py`.

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
