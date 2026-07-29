# Painter UI Figma Interface / Action Matrix

Status: active implementation contract

Painter의 Figma 대응 기능은 다음 네 조건을 모두 만족해야 `Done`이다.

1. `.tspaint`에 provider-neutral 데이터가 저장된다.
2. Painter UI에서 직접 생성, 수정, 삭제할 수 있다.
3. 같은 mutation을 Action/MCP로 실행할 수 있다.
4. Import, Canvas, Export, Undo/Redo 테스트가 있다.

Import 후 보이기만 하거나 JSON에만 남는 기능은 `Data only`이며 완료로
표시하지 않는다.

## Implemented

| Feature | Painter interface | Action surface |
| --- | --- | --- |
| Figma REST import/export | `Publish > Figma` URL/token, JSON import, compatibility report, plugin bundle export | `paint.ui.figma.compatibility.inspect`, `paint.ui.figma.import`, `paint.ui.figma.export` |
| Artboards and viewport | Artboard preset/add/activate, free placement, pointer-centered zoom, wheel/Space pan, fit all/artboard/selection | `paint.ui.artboard.*`, `paint.ui.view.focus/pan/zoom/fit`, `paint.ui.workspace.set` |
| Inspector presentation | Auto-hide selection overlay, pinned resizable panel, detachable floating window | `paint.ui.inspector.presentation` |
| Numeric property editing | Drag, absolute/arithmetic/relative input, percentage scale, localized Reset | Existing focused property Actions and `paint.ui.object.update` |
| Object geometry and hierarchy | Canvas selection/marquee/resize, Layers reorder/reparent/group, ancestor breadcrumb, Alt-click overlap cycle, nested frame/group edit scope | `paint.ui.object.*`, `paint.ui.selection.set/parent/deep_select`, `paint.ui.selection.scope.inspect/enter/exit` |
| Hierarchy drop preview | Canvas Frame/Group inside highlight plus Layers before/inside/after indicators; drop commits geometry, parent, constraints, and z-order together | `paint.ui.object.reparent` plus existing geometry mutation service |
| Same-artboard duplicate | Ctrl+D or Alt-drag copies selected roots, descendants, Boolean/Mask dependencies, nested stable IDs, and owned interactions; Alt-drag copy plus movement is one Undo step | `paint.ui.object.duplicate` |
| Multi-selection editing | Common bounds, proportional resize, mixed-value Common properties, partial state checks, one-step Undo | `paint.ui.property.batch_set` |
| Smart Selection spacing | Auto/H/V spacing analysis, mixed gap, explicit px Tidy Up, eligibility reason | `paint.ui.selection.tidy` |
| Resolved Smart Guides | Move-time edge/center, text baseline, parent padding, and equal-gap snap labels computed from responsive/Auto Layout/Constraint geometry | `paint.ui.smart_guide.inspect` |
| Object property clipboard | Context-menu Copy/Paste Properties and Paste to Replace; stable IDs, hierarchy, position, and z-order preserved | `paint.ui.object.properties.copy/paste`, `paint.ui.object.paste_replace` |
| Paste in place | Context-menu Copy then Paste in Place duplicates the complete source hierarchy at exact coordinates with fresh stable IDs | `paint.ui.object.paste_in_place` |
| Cross-artboard duplicate | Context-menu and Quick Actions command copies selected roots, descendants, Boolean/Mask dependencies, component-instance links, and owned interactions to the next or named artboard; conflicting focus order is reset explicitly | `paint.ui.object.duplicate_to_artboard` |
| Transient distance measurement | Hold Alt to draw nearest left/right/top/bottom gaps from the current selection to overlapping objects or artboard bounds; no panel width is reserved | `paint.ui.dev.measurement.inspect` |
| Figma-style Scale | Dedicated bottom-toolbar `Scale (K)` plus selection context command; proportional corner drag and shared-pivot geometry plus typography, corner, stroke, shadow, blur, and 9-slice scaling; mixed parent spaces blocked | `paint.ui.object.scale` |
| Quick Actions | Transient bottom-toolbar / `Ctrl+/` search over contextual commands, active-page layers, artboards, components, and variables; compact overlay does not reserve canvas space | `paint.ui.quick_action.search` plus existing focused mutation Actions |
| Context menu ordering | Hide invalid rows and promote three session-local valid recent commands; promoted rows trigger canonical QAction | Existing command-specific `paint.ui.*` Actions; ordering is non-mutating UI state |
| Contextual image editing | Selection-local bar for Fit/Fill/Stretch/Tile, direct focal handle, original size, and Replace; no fixed Inspector width | `paint.ui.image.place`, `paint.ui.image.fill.set` |
| Inline text | Double-click canvas editing, Escape cancel, focus-out or Ctrl/Cmd+Enter commit, one-step Undo | `paint.ui.text.content.set` |
| Constraints and Auto Layout | Inspector constraints, Horizontal/Vertical flow, padding/gap/wrap/Hug/Fill, non-destructive content stress preview | `paint.ui.layout.set`, `paint.ui.layout.diagnostics`, `paint.ui.layout.stress_preview`, `paint.ui.responsive.override.*` |
| Artboard layout grids | Uniform/Columns/Rows, ordered simultaneous definitions, Stretch/Center alignment | `paint.ui.artboard.layout.set` |
| Named layout-grid styles | Inspector save/apply/update/remove, stable references, linked-artboard propagation | `paint.ui.layout_grid.style.add/update/apply/remove` |
| Solid Fill, Stroke, Radius, Opacity | Inspector fields | `paint.ui.object.update` |
| Polygon/Star/Arc create and parameters | Shape flyout + contextual Shape rows | `paint.ui.object.add` / `paint.ui.object.update` |
| Editable Vector Network | Pen/Vector tool, double-click Vector Edit, node/segment/Bezier handles, transient contextual bar, open/close/join/split, Reverse, Simplify, Outline Stroke | `paint.ui.vector.node.add/update/remove`, `paint.ui.vector.segment.set/split`, `paint.ui.vector.path.closed.set/join/reverse/simplify/outline` |
| Linear/Radial Gradient | Inspector `Appearance` dialog with type, angle/center/radius, ordered color stops | `paint.ui.appearance.inspect`, `paint.ui.appearance.gradient.set/remove` |
| Drop/Inner Shadow stack | Inspector `Appearance > Effects` with add/remove/reorder and geometry/blend controls | `paint.ui.appearance.effect.add/update/remove/reorder` |
| Layer/Background Blur | Inspector `Appearance > Effects` with isolated layer blur, backdrop sampling, radius, and stack order | `paint.ui.appearance.blur.add/update/remove/reorder` |
| Frame clipping | Frame Inspector `Clip child content`, rounded Canvas clipping and selected-frame boundary indicator | `paint.ui.clip.inspect`, `paint.ui.clip.set` |
| Masks | Layers `Use as Mask`, invert/outline controls, editable target order, canvas clipping and hit testing | `paint.ui.mask.create/update/remove/reorder/inspect` |
| Advanced appearance | Appearance blend selector, ordered Fill/Stroke stacks, per-corner radii, Inside/Center/Outside stroke | `paint.ui.appearance.blend.set`, `paint.ui.appearance.paint.*`, `paint.ui.appearance.corner.set`, `paint.ui.appearance.stroke.set` |
| Mixed text styles | Text-range Inspector controls and range-aware canvas rendering | `paint.ui.text.range.style.inspect/set/remove` |
| Variable fonts | Contextual `wght/wdth/opsz` controls, QFont canvas/export application, Figma metadata preservation, explicit UMG blocked-until-bake status | `paint.ui.typography.variable_axis.set/reset` |
| Remote component recovery | Relink, localize, replace controls with explicit missing-library state | `paint.ui.component.remote.inspect/relink/localize/replace` |
| Boolean vector editing | Compatible multi-selection transient bar; Union/Subtract/Intersect/Exclude; editable operand release; Canvas/PNG/SVG parity | `paint.ui.vector.boolean.inspect/compose/set/release` |
| Figma sections and comments | Sections tab and object-anchored Painter Review mapping | `paint.ui.section.inspect/create/update/remove`, `paint.ui.review.*` |
| Components and Instances | Components library plus Inspector create/instance/Variant/switch/detach controls | `paint.ui.component.*` |
| Component properties | Typed document contract, instance property editing, nested instance swap | `paint.ui.component.property.*`, `paint.ui.component.instance.property.set` |
| Tokens and themes | Token library, exact scoped-value suggestions, bind/unbind, Light/Dark/High Contrast preview | `paint.ui.token.suggest`, `paint.ui.token.*`, `paint.ui.theme.*` |
| Prototype interactions | Prototype authoring/preview and production panel | `paint.ui.interaction.*` |
| Motion link | Inspector Animate/Preview and Motion Actor placement | `paint.ui.motion.*`, `paint.ui.motion_actor.*` |
| Delivery/UMG | Production preflight/export and shared TigerStudioUMG flow | `paint.ui.delivery.*`, `paint.ui.handoff.export` |

## Required Next

No item from the 2026-07-28 P0-P2 completion list remains in this section.
New gaps must satisfy the same interface, Action, persistence, round-trip, and
Undo/Redo completion rule before moving to Implemented.

## Implementation Rule

- UI controls and Actions must call the same focused service.
- Generic `paint.ui.object.update` remains available, but it does not replace a
  dedicated Action for a user-visible Figma workflow.
- Unsupported Figma data must be reported as `Native`, `Converted`, `Baked`, or
  `Blocked`; it must not disappear silently.
- The normal Painter raster command `paint.fill.gradient` is unrelated to UI
  Design gradient fills and must not be presented as the same function.
- New Action families are added in `app/actions/paint_namespace.py`; editor
  implementations stay in focused Painter modules or
  `app/actions/editor_adapter_paint.py`.
## Ruler And Guides

| UI gesture | Action | Persistent | Undo |
| --- | --- | --- | --- |
| Drag horizontal ruler | `paint.ui.guide.create` (`horizontal`) | artboard `guides.horizontal` | yes |
| Drag vertical ruler | `paint.ui.guide.create` (`vertical`) | artboard `guides.vertical` | yes |
| Drag existing guide | `paint.ui.guide.update` | artboard guides | yes |
| Drag guide back to ruler | `paint.ui.guide.remove` | artboard guides | yes |
| Remove guide | `paint.ui.guide.remove` | artboard guides | yes |
| Clear guides | `paint.ui.guide.clear` | artboard guides | yes |
| Show/hide guides | `paint.ui.guide.visibility.set` | artboard `guides.visible` | yes |
| Lock/unlock guides | `paint.ui.guide.lock.set` | artboard `guides.locked` | yes |
| Drag ruler corner | `paint.ui.ruler.origin.set` | artboard `guides.origin` | yes |
| Double-click ruler corner | `paint.ui.ruler.origin.reset` | artboard `guides.origin` | yes |
| Show/hide rulers | `paint.ui.ruler.visibility.set` | workspace session | no |
