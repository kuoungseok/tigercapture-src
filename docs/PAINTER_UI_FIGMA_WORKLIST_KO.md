# Painter UI 전용 모드 작업 목록

Status: canonical implementation backlog; P0-P10 local production foundation complete

M1 Page checkpoint (2026-07-29):

- Painter UI document schema is version 22. Version 19 Page documents migrate
  with stable-ID Theme Variable Collection/Mode records, and version 20
  documents gain empty named-Style collections without changing object IDs.
- M3 named Color/Text/Effect Styles and existing Layout Grid Styles share one
  compact Assets library and `paint.ui.style.*` mutation contract.
- M3 `.tsuilib` local packages and the compact Libraries Assets tab implement
  hash/license validation, version review, accept, defer, and rollback.
  Active package versions expose component definitions that can be inserted
  into another document with namespaced dependencies, durable extracted
  resources, one Undo, and `paint.ui.library.component.insert` parity.
- M4 now has stable Flow starting points, expanded trigger/action enums,
  validated transitions, a selection-driven compact Prototype panel, and
  `paint.ui.prototype.flow.*` / `transition.set` Action parity.
  Selected objects also expose a contextual canvas connection node with
  drag-to-artboard authoring, and HTML Preview mirrors the expanded interaction
  runtime without adding a fixed timeline.
- M4 inline Preview starts at the active Flow, keeps document data unchanged,
  routes pointer/keyboard triggers on the canvas, and exposes compact runtime
  state plus Reset. Authoring chrome is hidden only while Preview is active,
  and delay interactions are timer-scoped to the current artboard/overlays.
- M4 Smart Animate now matches component descendants by canonical source-object
  ID and reports the exact supported and fallback properties for each pair.
  HTML Preview interpolates transform, opacity, solid fill/stroke, and corner
  radius; text/image replacement, kind changes, and blend modes remain
  explicit fallback behavior. Browser QA records real mid-transition
  animations and zero runtime errors.
- M5 template discovery now uses one search/preview service for Gallery and
  `paint.ui.template.search/preview`. Query, category, complexity, platform,
  favorites, recent, and installed views share the same facets and manifests;
  Preview is read-only and reports editable document contents plus source and
  license. Gallery and `paint.ui.template.insert` also share New Document,
  Page, Component Set, and Theme modes. Page/Component modes namespace stable
  references; Theme preserves matching target token IDs; every insert is one
  validated Undoable mutation.
- M5 installed library Assets now list/search Component, Style, Token, Image,
  and Font records through `paint.ui.library.asset.search`. UI and
  `paint.ui.library.asset.insert` share Add-to-canvas versus
  Apply-to-selection behavior, durable extraction, source-link reuse, and one
  Undo.
- Stable-ID `pages[]`, `active_page_id`, and artboard `page_id` are canonical;
  version 18 documents migrate into `Page 1`.
- Page CRUD, Navigator inline rename/add/delete, Undo, `.tspaint` round trip,
  and `paint.ui.page.add/update/activate/remove` are implemented.
- Canvas rendering is scoped to the active Page. Each Page remembers its last
  active artboard, and existing per-artboard viewport persistence restores the
  corresponding view.
- Quick Actions distinguish Page activation from Artboard activation.
- Figma CANVAS records import as real Tiger Studio Pages.
- Reproducible desktop/compact QA lives under the disposable
  `debugCapture/painter_ui_pages_m1` report path.
- Large-document QA covers 4 Pages, 20 artboards, and 500 objects. Auto-hidden
  no-selection Inspector work is deferred until selection or explicit
  Properties/Pin/Floating use, reducing measured Page switching from 1224 ms
  median to 318 ms without changing the canonical Inspector.

P0-P2 completion checkpoint (2026-07-28):

- Painter UI document schema is version 18.
- Schema 18 adds explicit non-destructive Boolean groups, transient
  multi-selection authoring, editable operand release, and shared
  Canvas/PNG/SVG result geometry.
- Schema 17 adds typed stable-ID Vector Networks shared by canvas, vector
  editing, Action, PNG, and editable SVG output.
- Vector Edit includes transient Reverse, conservative Simplify, and editable
  Outline Stroke commands with matching
  `paint.ui.vector.path.reverse/simplify/outline` Actions. These commands do
  not create permanent side-panel chrome.
- Schema 16 added normalized Polygon/Star/Arc parameters shared by canvas,
  Inspector, Action, PNG, and SVG paths.
- Schema 15 introduced ordered per-artboard `layout_grids[]` with legacy
  `layout_grid` compatibility. Uniform, Columns, and Rows can render together;
  Columns/Rows support Stretch and Center alignment. Reusable named grid styles
  include stable-ID CRUD, Inspector controls, Action parity, and linked-artboard
  propagation.
- Masks, object blend modes, ordered Fill/Stroke stacks, independent corner
  radii, and stroke alignment have persistent contracts, Inspector controls,
  canvas behavior, Actions, and Figma round-trip coverage.
- Mixed text ranges render on the Painter canvas and preserve Figma character
  style overrides.
- Missing remote components remain recoverable through relink, localize, and
  replace operations instead of being silently discarded.
- Editable Boolean operands and Figma Sections are persisted with stable IDs.
  Boolean authoring no longer requires users to type operand IDs.
- Figma comments map to the existing object-anchored Painter Review contract.
- Shared TigerStudioUMG preflight explicitly blocks advanced Painter
  appearance that has no real native/material/bake generation path yet.

P0 implementation checkpoint (2026-07-26):

- UI document version 9 defines typed component, token, interaction, and
  deterministic Auto Layout records.
- Stable IDs are preserved by update operations and assigned during v1 migration.
- Parent, component, token, interaction, alias, and cycle references are validated.
- Referenced component/token deletion is blocked unless explicit detachment is requested.
- Painter Actions expose CRUD for all three record types.
- Legacy `.tspaint` documents migrate through the shared normalization path and
  typed records survive save/open round trips.
- Component definitions expose typed properties and state overrides for
  Normal, Hover, Pressed, Focused, Disabled, and Selected. Instance state
  preview, Canvas resolution, Inspector editing, Actions, Undo, and validation
  share one stable-ID contract.
- Linked Variant Definitions, stable-ID Instance switching, local override
  preservation, and Detach/Localize are implemented through shared Inspector,
  Action, Undo, validation, and persistence services.
- The dedicated Components tab provides searchable family/Variant hierarchy,
  Instance usage, Definition selection, Instance placement, Variant creation,
  rename, and read-only Action inspection.
- M2A template foundation provides a visual gallery with 12 complete editable
  documents across 11 categories. Every template includes typed tokens, a
  Component Definition, an interaction, source/version/license provenance, and
  shared `paint.ui.template.catalog.inspect/apply` Actions.

P1 implementation checkpoint (2026-07-26, navigation slice):

- New artboards receive deterministic freeform document positions instead of
  overlapping the active artboard.
- The UI canvas renders all artboards in one document-space overview.
- Space/left-drag or middle-button drag pans; wheel pans vertically,
  Shift+wheel pans horizontally, and Ctrl+wheel zooms around the pointer.
- A transient Zoom popover and `paint.ui.view.focus/pan/zoom/fit` provide
  percentage zoom and all-artboards, active-artboard, selection, or object
  framing without permanent Fit buttons.
- The right Inspector defaults to Auto-hide and reuses one canonical widget for
  selection overlay, pinned, and floating presentations. UI and automation
  share `paint.ui.inspector.presentation`.
- Navigator, canvas, and pinned Inspector now use a native horizontal splitter
  instead of equal min/max width locks. Both side widths remain bounded,
  divider movement is persisted with a debounce, and the canvas takes all
  remaining space across resize and workspace-mode changes.
- Inspector content is adaptive rather than fixed: no selection owns artboard
  controls, single selection exposes object Design/Prototype/Inspect, and
  multiple selection removes the irrelevant Prototype surface without
  resetting panel presentation.
- Clicking another artboard or one of its objects activates that artboard.
- Nested selections expose a compact ancestor breadcrumb. Alt-click cycles the
  deterministic overlap stack, while `paint.ui.selection.parent/deep_select`
  provide the same navigation to automation without document mutation.
- Double-click/Escape and `paint.ui.selection.scope.inspect/enter/exit` share a
  nested frame/group edit scope; outside objects are dimmed and excluded from
  hit testing.
- Text objects support direct double-click editing over their resolved canvas
  bounds. Escape cancels, focus-out or Ctrl/Cmd+Enter commits one Undo step,
  and `paint.ui.text.content.set` provides Action parity.
- Dragging empty canvas space creates a marquee selection; Shift adds and Ctrl
  toggles intersecting objects on the active artboard.
- Corner resize supports Shift aspect lock and Alt center-based scaling.
- Grid snapping also evaluates peer edges and centers, snaps within a
  screen-space tolerance, and paints visible Smart Guides while moving.
- A selected Frame/Group now exposes transient H/V, main/cross alignment, gap,
  and four-edge padding controls directly on the canvas. Children of an active
  Auto Layout container expose Flow/Absolute positioning. These controls reuse
  the normalized object `layout`, Undo, persistence, Inspector, and
  `paint.ui.layout.set` paths rather than creating canvas-only state.
- Inspector sizing now uses compact per-axis Fixed/Hug/Fill segments and shows
  selection-local layout diagnostics with recovery guidance. Automation reads
  and resets the same normalized property through
  `paint.ui.property.inspect/reset`.
- A selection-local Content Test control and
  `paint.ui.layout.stress_preview` now share non-destructive long Korean,
  long English, large-type, missing-image, and empty-list previews. The
  canonical document, revision, persistence, and Undo stack are invariant.
- A contextual Suggested Tokens row appears only for exact, type-safe,
  unbound raw-value matches after active-theme and alias resolution.
  `paint.ui.token.suggest` shares the pure planner without mutation; accepting
  a suggestion reuses the existing token bind, persistence, and one-step Undo
  path.
- Text and Button Inspector contexts expose opt-in `wght`, `wdth`, and `opsz`
  variable-font axes. The same normalized `style.font_axes` contract is used
  by Actions, canvas/asset rendering, Figma shared plugin metadata, save/load,
  and explicit UMG blocked-until-bake preflight.
- Artboard title dragging moves frames in document space and persists the new
  position through the same undoable artboard mutation service.
- Inspector presets add iPhone, Android, desktop, console, and broadcast
  artboards with deterministic non-overlapping placement.

P2 implementation checkpoint (2026-07-26, visual style slice):

- Inspect edits Fill, Stroke, Stroke Width, Radius, and a structured shadow
  (`x/y/blur/spread/color`) through the shared UI document mutation path.
- Text and button objects expose editable content, font size, font weight,
  alignment, and line height; non-text selections disable these controls.
- Inspector payloads preserve unrelated style/content fields and participate in
  the existing PaintDialog Undo path.
- Canvas preview now renders scaled stroke/radius, feathered shape shadows,
  CSS-style `#RRGGBBAA` colors, font family/size/weight, left/center/right
  alignment, explicit line breaks, word wrapping, and line height.
- General `shadow` applies to object geometry. Text uses explicit
  `text_shadow`; text objects inherit their general shadow as a text shadow,
  while button labels do not duplicate the button's box shadow.
- Figma linear/radial gradient fills preserve normalized handles, stop colors,
  alpha, and paint opacity. Ordinary shapes and imported SVG paths render from
  the same contract, and Figma plugin export restores editable gradient paints.
- Ordered Figma Drop Shadow and Inner Shadow stacks preserve color alpha,
  offset, blur, signed spread, and blend mode. Painter renders outer and inner
  effects in separate geometry passes and Figma plugin export restores editable
  effect records.
- Inspector `Appearance` now authors the same Gradient and Effect contracts:
  ordered color stops, linear angle, radial center/radius, Drop/Inner add,
  remove, reorder, offset, blur, spread, and blend. Dedicated
  `paint.ui.appearance.*` Actions provide AI/MCP parity. The canonical
  interface/action completion matrix is
  `docs/PAINTER_UI_FIGMA_INTERFACE_ACTION_MATRIX_KO.md`.

P2 implementation checkpoint (2026-07-26, responsive constraint slice):

- Inspect exposes normalized pivot X/Y, horizontal and vertical constraints,
  minimum/preferred/maximum size, and aspect-ratio locking.
- Constraint capture records stable parent dimensions, edge margins, and center
  offsets. Left/center/right/stretch/scale and
  top/center/bottom/stretch/scale resolve deterministically when an artboard or
  parent changes size.
- Canvas rotation, hit testing, the rotation handle, and its visible pivot
  marker use the authored pivot rather than an implicit object center.
- Canvas and Inspector resizing share the same minimum/maximum/aspect rules;
  Shift temporarily locks the current ratio and Alt preserves center resizing.
- Geometry edits recapture the active constraint anchors through the shared
  document mutation path, so refresh, Undo/Redo, UI controls, and Actions do
  not make constrained objects jump back to stale margins.

P2 implementation checkpoint (2026-07-26, image layout slice):

- Image objects load PNG, WebP, JPEG, or BMP source files through a bounded
  modification-aware preview cache instead of always drawing a placeholder.
- Inspect exposes Fit (contain), Fill (center crop), Stretch, and Tile with a
  bounded tile scale. Missing or invalid files keep the explicit crossed
  placeholder rather than silently disappearing.
- Optional 9-slice stores left/top/right/bottom source-pixel margins and renders
  nine deterministic regions. Corners retain their source size where possible;
  margins proportionally contract when the destination is smaller than the
  combined fixed edges.
- Image settings preserve unrelated content metadata and use the same document
  update, Undo/Redo, persistence, and `paint.ui.object.update` Action path.
- Embedding referenced image bytes, resource hashes, density variants, and
  delivery packaging remains P8 asset-delivery work.

M1 implementation checkpoint (2026-07-29, contextual image controls):

- Image fit modes, Replace, and original-size restore are available from a
  transient canvas-local bar instead of permanently occupying Inspector space.
- Fill mode exposes a direct focal target on the selected image. Selection
  changes clear stale focal-edit state.
- Replace preserves fit, focal, and tile settings; UI, Undo, `.tspaint`, and
  `paint.ui.image.fill.set` remain on the shared mutation contract.
- Desktop/compact QA lives only in the disposable
  `debugCapture/painter_ui_image_context_m1` evidence folder.

M1 implementation checkpoint (2026-07-29, Paste in Place):

- Copy/Paste in Place now clones the complete selected hierarchy at zero
  offset through the same stable-ID remapping service as Duplicate.
- The context menu and `paint.ui.object.paste_in_place` share one mutation,
  Undo, validation, interaction remap, and persistence contract.
- Desktop/compact evidence is regenerated by
  `tools/qa_painter_ui_paste_in_place.py`.

M1 implementation checkpoint (2026-07-29, contextual menu ordering):

- Selection-invalid canvas commands are hidden instead of shown as disabled
  clutter.
- Three valid recent commands are promoted under a localized heading and
  replay the original QAction rather than duplicating mutation logic.
- Ordering remains session-local view state; desktop/compact QMenu evidence is
  regenerated by `tools/qa_painter_ui_context_menu.py`.

M1 implementation checkpoint (2026-07-29, hierarchy drop preview):

- Canvas move previews now update effective/resolved geometry live instead of
  leaving the object painted at its pre-drag position.
- Frame/Group targets receive a localized inside highlight; one drop mutation
  applies geometry, parent, recaptured constraints, and deterministic order.
- Layers show explicit before/inside/after previews, and
  `paint.ui.object.reparent` shares the Frame/Group hierarchy contract.
- Desktop/compact evidence is regenerated by
  `tools/qa_painter_ui_reparent_preview.py`.

M1 implementation checkpoint (2026-07-29, equal-size Smart Guides):

- Single-object resize now snaps to visible peer width/height using resolved
  responsive geometry and zoom-adjusted tolerance.
- Localized equal-width/equal-height labels show exact pixel values; resize
  preview updates resolved geometry live.
- UI and read-only `paint.ui.smart_guide.inspect(operation=resize)` share
  `plan_ui_resize_guides`; desktop/compact evidence is regenerated by
  `tools/qa_painter_ui_equal_size_guides.py`.

M1 implementation checkpoint (2026-07-29, remembered viewport):

- Each artboard-backed Page now keeps its own zoom and world-space center.
  Canvas selection, Navigator activation, and
  `paint.ui.artboard.activate` restore the same view.
- The state is workspace-only rather than document revision/Undo data, but it
  round-trips in `.tspaint` as `workspace.ui_artboard_viewports`.
- UI pan/zoom/fit and `paint.ui.view.*` Actions share one overlay signal path.
- Native trackpad pinch/pan uses the same signal path, preserves cursor focus
  and subpixel movement, and shares a minimum-visible-edge clamp with mouse
  and Action navigation.
- Window resizing preserves the remembered world center instead of replaying
  stale widget-pixel offsets.
- Desktop/compact viewport and native gesture/clamp QA is regenerated by
  `tools/qa_painter_ui_page_viewports.py`.

P6-P10 implementation checkpoint (2026-07-27):

- Object-anchored comments, replies, resolve state, checkpoints, revision diff,
  developer Inspect, and offline review packages are implemented.
- Prototype runtime and self-contained pointer/keyboard HTML export support all
  declared interaction triggers and actions.
- Production export provides PNG/WebP/SVG, density variants, object slices,
  trim/padding, 9-slice, atlas, resource hashes, and explicit bake metadata.
- Painter uses the shared `TigerStudioUMG` adapter and plugin. UE 5.8 produced
  and loaded an 8-widget Widget Blueprint from the checkout sample.
- AI co-design uses an explicit plan/preview/diff/partial-apply contract plus
  accessibility, localization, budget, and delivery audits.

관련 구현 현황:

- `docs/PLAN_PAINTER_UI_DESIGNER.md`
- `docs/PAINTER_UI_DESIGNER_MILESTONES_KO.md`
- `docs/SPEC_PAINTER_DOCUMENT_FORMAT.md`

## 목표와 소유권

Painter를 단순 도형 배치기가 아니라 Figma형 UI 제작 도구로 완성한다.
Painter는 정적 UI 구조, 컴포넌트, 레이아웃, 토큰, 프로토타입 연결을
소유하고 Motion Designer는 키프레임과 전환 애니메이션을 소유한다.

구현 우선순위:

1. P0 문서 모델
2. P1 편집 UX
3. P2 인스펙터
4. P3 Auto Layout
5. P4 컴포넌트
6. P7 Motion Designer 연결
7. P9 Unreal UMG

P5, P6, P8, P10은 위 기능의 기반과 전달 품질을 따라 병행한다.

## P0. 문서 모델 완성

1. `components`, `tokens`, `interactions`를 단순 JSON 배열이 아닌 정식
   타입과 CRUD로 구현
2. 모든 아트보드, 객체, 컴포넌트, 토큰에 변경되지 않는 stable ID 적용
3. 컴포넌트, 부모, 토큰, 인터랙션 참조 검증
4. 참조 순환, 삭제된 대상, 중복 ID 검출
5. 스키마 의미 변경 시 `tigerstudio.painter.ui.v1` 버전 갱신
6. 기존 `.tspaint` 문서 마이그레이션과 왕복 저장 테스트 추가

## P1. Figma형 편집 UX

1. 여러 아트보드를 한 캔버스에서 자유 배치
2. 캔버스 패닝, 휠 줌, Fit Selection, Fit Artboard
3. 다중 선택, 영역 선택, 부모 안으로 드래그
4. Layers 트리 드래그로 순서 변경과 재부모화
5. 잠금, 숨김, 이름 변경, 복제, 삭제
6. 정렬, 균등 분배, Smart Guide, 픽셀 스냅
7. 객체 크기 조절 시 비율 잠금과 중심 기준 조절
8. 실제 모바일과 데스크톱 화면 크기 프리셋 제공

현재 구현된 기반:

- 다중 선택, 그룹 이동, 정렬, 균등 분배
- 동일 Artboard의 잠금 해제 객체를 위한 공통 selection bounds와 비례 resize
- 다중 resize의 Shift 비율 잠금, Alt 중심 기준 조절, 단일 batch Undo
- UI와 `paint.ui.property.batch_set` Action의 constraint-aware mutation 공유
- 선택할 때만 나타나는 다중 선택 Common Inspector와 `—` mixed-value 표시
- 공통 Opacity/Fill/Stroke/Width/Radius/Visible/Locked 일괄 편집
- 변경한 속성 외의 객체별 style/content 보존
- Auto/Horizontal/Vertical Smart Selection 간격 분석과 mixed gap `—`
- 명시적 px 또는 현재 범위 평균 간격을 쓰는 `paint.ui.selection.tidy`
- 잠금, cross-Artboard, cross-parent 선택의 명시적 Tidy Up 차단
- Group/Ungroup과 자식 보존 이동
- Layers 순서 변경, 그룹 nesting, root 이동
- 전체 아트보드 자유 배치, 화면 이동과 줌, Fit 명령
- marquee 선택, Smart Guide, 비율/중심 기준 resize
- 모바일, 데스크톱, 콘솔, 방송 아트보드 프리셋

- UI context-menu Copy/Paste Properties and Paste to Replace preserve stable
  IDs, hierarchy, position, and z-order and share
  `paint.ui.object.properties.copy/paste` /
  `paint.ui.object.paste_replace` mutation contracts.
- Selection-local Scale uses a transient percentage prompt and a dedicated
  bottom-toolbar `K` tool rather than a fixed panel. Corner drag is
  proportional by default, commits one Undo step on release, persists through
  `.tspaint`, and shares `paint.ui.object.scale` for geometry and visual
  metrics. Mixed parent coordinate spaces do not expose a misleading common
  transform.
- Quick Actions is a transient `Ctrl+/` / bottom-toolbar overlay that searches
  commands, layers, pages, components, and variables without reserving
  workspace width. `paint.ui.quick_action.search` exposes the same ranked
  catalog to automation.
- Cross-artboard duplication is available from the contextual canvas menu and
  Quick Actions without adding fixed chrome. It copies complete selected
  hierarchies plus Boolean/Mask dependencies and owned interactions, remaps
  stable references, turns copied component definitions into linked instances,
  reports focus-order conflict resets, and shares
  `paint.ui.object.duplicate_to_artboard` with the UI mutation.
- Alt-held selection measurements are canvas-only and transient. The same
  resolved Auto Layout/Constraint geometry is available without mutation
  through `paint.ui.dev.measurement.inspect`; nearest overlapping objects are
  preferred and artboard edges are the directional fallback.
- Ctrl+D and Alt-drag now duplicate the complete selected hierarchy rather
  than rebuilding one shallow object. Object/nested IDs, Boolean and Mask
  dependencies, owned interactions, component links, and focus-order conflict
  reporting share `app/painter_ui_duplicate.py` with
  `paint.ui.object.duplicate`. Alt-drag movement continues the initial
  duplicate mutation so one Undo removes both the copy and its move.
- Move-time Smart Guides use resolved responsive, Constraint, and Auto Layout
  geometry rather than stale source `x/y`. Edge/center snapping is extended
  with text baseline, parent padding, and two-sided equal-gap candidates.
  Context labels remain canvas-only, and `paint.ui.smart_guide.inspect`
  exposes the same non-mutating plan.

## P2. 인스펙터 확장

1. X/Y/W/H, 회전, 피벗, 불투명도
2. Fill, Stroke, Stroke Width, Radius, Shadow
3. 텍스트 내용, 폰트, 크기, 굵기, 정렬, 행간
4. Anchor와 좌우, 상하 Constraint
5. 최소, 권장, 최대 크기와 비율 잠금
6. 이미지 Fit/Fill/Stretch/Tile
7. 9-slice margin
8. 접근성 role, label, focus order
9. 선택 객체의 target별 `Native/Material/Baked/Blocked` 표시

현재 구현된 숫자 입력 기반:

- 모든 Painter UI drag-spin field의 안전한 `+ - * /`, 괄호, 상대 계산
- px 필드의 percentage scaling과 의미 있는 필드의 우클릭 Reset
- 일반 속성 commit 신호를 재사용하는 Undo/Action mutation parity

현재 구현된 기반:

- X/Y/W/H, 회전, 불투명도, 표시, 잠금
- 피벗, 좌우·상하 Constraint, 최소/권장/최대 크기, 비율 잠금
- 이미지 Fit/Fill/Stretch/Tile, 타일 배율, 9-slice 여백
- Fill, Stroke, Stroke Width, Radius, 구조화된 Shadow 편집과 저장
- 텍스트 내용, 크기, 굵기, 정렬, 행간 편집과 저장
- 접근성 role, label, focus order 편집과 문서 정규화
- 대상별 `Native/Material/Baked/Blocked` 상태와 판정 이유 표시
- 접근성 라벨 누락과 아트보드별 명시 focus order 중복 검사
- UI와 Action이 공유하는 문서 mutation 및 Undo 경로

남은 범위:

- target adapter 출력과 캔버스 스타일 렌더링 parity 검증

## P3. Auto Layout와 반응형

1. Horizontal/Vertical Auto Layout
2. Padding, Gap, Alignment, Wrap
3. Hug Content, Fixed Size, Fill Container
4. Grid, Column, Guide, Safe Area
5. Breakpoint와 화면 방향별 override
6. Desktop, mobile, console, broadcast 프리셋
7. Light/Dark/High Contrast 테마 미리보기
8. 레이아웃 순환과 불가능한 Constraint 검출

현재 구현된 기반:

- Horizontal/Vertical Auto Layout과 고정 크기 자식 흐름
- L/T/R/B Padding, Gap, main Start/Center/End/Space Between
- cross Start/Center/End/Stretch
- `positioning=absolute` 자식의 자동 흐름 제외
- Wrap과 축별 Fixed/Hug Content/Fill Container 크기 정책
- Hug의 안쪽부터 바깥쪽 측정과 Fill의 잔여 공간 결정적 분배
- 중첩 컨테이너의 바깥쪽부터 안쪽 순서로 결정적 배치
- Inspector, `.tspaint`, Undo/Redo, `paint.ui.layout.set` Action 공유 계약
- 아트보드별 Uniform Grid/Columns, custom Guide, Safe Area 표시와 저장
- `paint.ui.artboard.layout.set` Action 및 아트보드 mutation/Undo 공유
- Hug/Fill cycle, min/max 역전, collapsed grid/safe area 차단 진단
- Wrap 무시와 fixed-content overflow 경고
- Inspector, validation, delivery preflight, `paint.ui.layout.diagnostics` 공유
- stable-ID breakpoint/orientation override와 wildcard→exact 계층 합성
- Canvas, Constraint, Auto Layout, Motion geometry 반응형 context 공유
- Inspector override 편집/삭제와 `paint.ui.responsive.override.set/remove`
- Light/Dark/High Contrast artboard preview and token alias/theme resolution
- `paint.ui.theme.set/inspect` and `paint.ui.token.theme.set/remove` Action parity

남은 범위:

- dedicated P5 token-library and token-binding authoring UX (implemented:
  searchable typed library, theme/alias editing, usage and unused inspection,
  stable-ID Bind/Unbind UI and Actions, deterministic JSON import/export with
  update/skip/regenerate conflict policies)

## P4. 컴포넌트 시스템

1. 선택 객체를 Component Definition으로 변환
2. Component Instance 생성
3. Instance에서 텍스트, 이미지, 토큰 override
4. Variant와 property 정의
5. `Normal/Hover/Pressed/Focused/Disabled/Selected` 상태
6. 컴포넌트 원본 수정 시 인스턴스 갱신
7. 원본 연결 해제와 로컬 컴포넌트 변환
8. 컴포넌트 참조 순환 방지

현재 구현 기반:

- 선택 subtree를 Component Definition으로 변환
- 새 stable object ID와 source stable ID를 가진 Instance subtree 생성
- Definition 속성 및 직접 자식 추가/삭제를 모든 Instance에 동기화
- Instance 로컬 편집을 dotted-path override로 보존
- Inspector Create/Instance 명령과
  `paint.ui.component.create/instantiate/sync` Action parity

남은 범위:

- Variant/property와 상태 세트
- Instance detach 및 local component 변환
- 전용 Components 패널과 override property editor

## P5. 디자인 토큰

1. Color, Typography, Spacing, Radius, Border, Shadow, Opacity
2. 아이콘과 이미지 alias
3. 객체 속성에 값 복사가 아닌 token ID 연결
4. 토큰 수정 시 연결 객체 일괄 갱신
5. Light/Dark/High Contrast 테마 값
6. 사용 중인 토큰과 미사용 토큰 검사
7. 토큰 JSON 내보내기와 다시 가져오기

## P6. 프로토타입

1. Click, Double Click, Hover, Press, Focus, Keyboard 트리거
2. Navigate, Back, Open/Close Overlay
3. Change State/Variant
4. Play Animation, Play Sound
5. Set Visibility/Opacity/Material Scalar
6. 캔버스에서 연결선을 드래그해 대상 화면 지정
7. Preview에서 실제 포인터와 키보드 동작
8. 연결 대상이 삭제되면 명시적인 오류 표시

## P7. Motion Designer 연결

1. 선택 객체 또는 컴포넌트에 `Animate` 명령 제공
2. stable object ID를 유지한 채 Motion Designer 실행
3. Painter 객체를 Motion 문서에 복제하지 않고 canonical
   `UIMotionBinding.binding_id`와 composition revision으로 연결
4. Painter Preview에서 Motion 클립 재생
5. 상태별 전환 애니메이션 선택
6. Auto Layout 계산 후 Motion transform을 오프셋으로 적용
7. Motion 클립 누락, 깨진 참조, 지원하지 않는 속성을 preflight에서 검출
8. 애니메이션 변경 시 Painter에 즉시 반영

구현 순서와 소유권, 최소 왕복 계약, Painter UX, UMG 전달 분류는
`docs/MOTION_PAINTER_INTEGRATION_TODO_KO.md`를 canonical 기준으로 사용한다.

## P8. 에셋 및 전달

1. PNG/WebP/SVG와 @1x/@2x/@3x 내보내기
2. Slice와 Export Region
3. 투명 여백 제거와 deterministic 파일명
4. 9-slice 및 texture atlas metadata
5. 이미지, 폰트, 사운드 resource ID와 해시
6. `design_document.json`, `tokens.json`, `components.json`,
   `interactions.json`
7. 사람이 읽을 수 있는 inspection report
8. revision diff와 재생성 기록
9. Figma URL/REST JSON을 editable Painter UI로 가져오고, 공식 Plugin API용
   로컬 개발 플러그인 번들로 내보내기. 네이티브 `.fig` 직접 생성은 범위 밖

## P9. Unreal UMG

1. 별도 Painter 플러그인을 만들지 않고 기존 `TigerStudioUMG` 사용
2. Painter에서 provider-neutral Tiger UMG adapter 구현
3. Frame/Group을 Canvas 또는 Panel로 변환
4. Auto Layout을 HorizontalBox/VerticalBox/Grid로 변환
5. Text/Image/Button/Progress를 네이티브 UMG로 변환
6. 단순 효과는 UI Material로 변환
7. 복잡한 Painter 표현은 deterministic bake
8. Motion 연결은 `UWidgetAnimation`으로 변환
9. 버튼 상태와 이벤트는 `UTigerStudioButton`으로 변환
10. Widget Blueprint 컴파일과 실제 Unreal 캡처까지 검증

## P10. Actions와 QA

1. 컴포넌트, 토큰, Auto Layout, 프로토타입, Motion 연결 Action 추가
2. UI와 Action이 동일한 mutation service 사용
3. 저장, 로드, Undo/Redo, 복사/붙여넣기 테스트
4. 다중 아트보드와 반응형 레이아웃 테스트
5. Painter Preview와 UMG 결과 비교
6. 폰트, 이미지, 사운드 누락 테스트
7. 실제 모바일과 데스크톱 화면 캡처
8. 모든 전달 결과를 `Native/Material/Baked/Blocked`로 보고

## 작업 경계

- Painter는 UI 구조, 레이아웃, 컴포넌트, 스타일, 토큰을 소유한다.
- Motion Designer는 키프레임과 전환 애니메이션을 소유한다.
- Unreal 출력은 공용 `TigerStudioUMG`만 사용한다.
- Painter 전용 Unreal 플러그인을 새로 만들지 않는다.
- Motion 데이터를 Painter 객체 내부에 중복 저장하지 않고 stable ID로
  연결한다.
- 기능을 조용히 누락하지 않고 반드시 preflight에서 경고하거나
  차단한다.
- 각 기능은 UI, Action, persistence, Undo/Redo, 검증 테스트가 같은
  mutation contract를 통과해야 완료로 간주한다.
