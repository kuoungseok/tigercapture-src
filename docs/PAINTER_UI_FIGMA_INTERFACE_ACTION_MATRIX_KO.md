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
| Object geometry and hierarchy | Canvas selection/marquee/resize, Layers reorder/reparent/group, ancestor breadcrumb, Alt-click overlap cycle, nested frame/group edit scope | `paint.ui.object.*`, `paint.ui.selection.set/parent/deep_select`, `paint.ui.selection.scope.inspect/enter/exit` |
| Constraints and Auto Layout | Inspector constraints, Horizontal/Vertical flow, padding/gap/wrap/Hug/Fill | `paint.ui.layout.set`, `paint.ui.layout.diagnostics`, `paint.ui.responsive.override.*` |
| Solid Fill, Stroke, Radius, Opacity | Inspector fields | `paint.ui.object.update` |
| Linear/Radial Gradient | Inspector `Appearance` dialog with type, angle/center/radius, ordered color stops | `paint.ui.appearance.inspect`, `paint.ui.appearance.gradient.set/remove` |
| Drop/Inner Shadow stack | Inspector `Appearance > Effects` with add/remove/reorder and geometry/blend controls | `paint.ui.appearance.effect.add/update/remove/reorder` |
| Layer/Background Blur | Inspector `Appearance > Effects` with isolated layer blur, backdrop sampling, radius, and stack order | `paint.ui.appearance.blur.add/update/remove/reorder` |
| Frame clipping | Frame Inspector `Clip child content`, rounded Canvas clipping and selected-frame boundary indicator | `paint.ui.clip.inspect`, `paint.ui.clip.set` |
| Masks | Layers `Use as Mask`, invert/outline controls, editable target order, canvas clipping and hit testing | `paint.ui.mask.create/update/remove/reorder/inspect` |
| Advanced appearance | Appearance blend selector, ordered Fill/Stroke stacks, per-corner radii, Inside/Center/Outside stroke | `paint.ui.appearance.blend.set`, `paint.ui.appearance.paint.*`, `paint.ui.appearance.corner.set`, `paint.ui.appearance.stroke.set` |
| Mixed text styles | Text-range Inspector controls and range-aware canvas rendering | `paint.ui.text.range.style.inspect/set/remove` |
| Remote component recovery | Relink, localize, replace controls with explicit missing-library state | `paint.ui.component.remote.inspect/relink/localize/replace` |
| Boolean vector editing | Union/Subtract/Intersect/Exclude operands with editable canvas result | `paint.ui.vector.boolean.inspect/set/release` |
| Figma sections and comments | Sections tab and object-anchored Painter Review mapping | `paint.ui.section.inspect/create/update/remove`, `paint.ui.review.*` |
| Components and Instances | Components library plus Inspector create/instance/Variant/switch/detach controls | `paint.ui.component.*` |
| Component properties | Typed document contract, instance property editing, nested instance swap | `paint.ui.component.property.*`, `paint.ui.component.instance.property.set` |
| Tokens and themes | Token library, bind/unbind, Light/Dark/High Contrast preview | `paint.ui.token.*`, `paint.ui.theme.*` |
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
