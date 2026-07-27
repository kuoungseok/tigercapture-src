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
| Artboards and viewport | Artboard preset/add/activate, free placement, pan/zoom, fit all/artboard/selection | `paint.ui.artboard.*`, `paint.ui.view.fit`, `paint.ui.workspace.set` |
| Object geometry and hierarchy | Canvas selection/marquee/resize, Layers reorder/reparent/group | `paint.ui.object.*`, `paint.ui.selection.set` |
| Constraints and Auto Layout | Inspector constraints, Horizontal/Vertical flow, padding/gap/wrap/Hug/Fill | `paint.ui.layout.set`, `paint.ui.layout.diagnostics`, `paint.ui.responsive.override.*` |
| Solid Fill, Stroke, Radius, Opacity | Inspector fields | `paint.ui.object.update` |
| Linear/Radial Gradient | Inspector `Appearance` dialog with type, angle/center/radius, ordered color stops | `paint.ui.appearance.inspect`, `paint.ui.appearance.gradient.set/remove` |
| Drop/Inner Shadow stack | Inspector `Appearance > Effects` with add/remove/reorder and geometry/blend controls | `paint.ui.appearance.effect.add/update/remove/reorder` |
| Components and Instances | Components library plus Inspector create/instance/Variant/switch/detach controls | `paint.ui.component.*` |
| Component properties | Typed document contract, instance property editing, nested instance swap | `paint.ui.component.property.*`, `paint.ui.component.instance.property.set` |
| Tokens and themes | Token library, bind/unbind, Light/Dark/High Contrast preview | `paint.ui.token.*`, `paint.ui.theme.*` |
| Prototype interactions | Prototype authoring/preview and production panel | `paint.ui.interaction.*` |
| Motion link | Inspector Animate/Preview and Motion Actor placement | `paint.ui.motion.*`, `paint.ui.motion_actor.*` |
| Delivery/UMG | Production preflight/export and shared TigerStudioUMG flow | `paint.ui.delivery.*`, `paint.ui.handoff.export` |

## Required Next

These items are not complete until both the interface and the listed Action
family exist.

| Priority | Feature | Required interface | Planned Action family |
| --- | --- | --- | --- |
| P0 | Layer Blur / Background Blur | Appearance Effects entries with radius, visibility, order, and fallback badge | `paint.ui.appearance.blur.add/update/remove/reorder` |
| P0 | Frame clipping | Frame Inspector `Clip content` toggle and Canvas clipping indicator | `paint.ui.clip.set`, `paint.ui.clip.inspect` |
| P0 | Masks | Layers mask row, Use as Mask, release mask, invert, outline | `paint.ui.mask.create/update/remove/reorder/inspect` |
| P1 | Object blend mode | Appearance blend selector with compatibility badge | `paint.ui.appearance.blend.set` |
| P1 | Multiple fill/stroke paints | Ordered Fill and Stroke stacks with visibility and reorder | `paint.ui.appearance.paint.add/update/remove/reorder` |
| P1 | Per-corner radius and stroke align | Four-corner radius linkage and Inside/Center/Outside stroke control | `paint.ui.appearance.corner.set`, `paint.ui.appearance.stroke.set` |
| P1 | Mixed text styles | Text range selection and span style Inspector | `paint.ui.text.range.style.set/remove` |
| P1 | Remote component recovery | Missing-library panel with relink/localize/replace commands | `paint.ui.component.remote.inspect/relink/localize` |
| P2 | Boolean vector editing | Union/Subtract/Intersect/Exclude toolbar and editable operands | `paint.ui.vector.boolean.set/release` |
| P2 | Figma sections and comments | Section Inspector and review-comment mapping | `paint.ui.section.*`, existing `paint.ui.review.*` bridge |

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
