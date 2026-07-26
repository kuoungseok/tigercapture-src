# Tiger Studio Painter General UI Designer Plan

Status: active implementation

Primary scope: general UI authoring, prototyping, asset delivery, and handoff

Canonical P0-P10 implementation backlog:
`docs/PAINTER_UI_FIGMA_WORKLIST_KO.md`

First native runtime adapter: Motion Designer Unreal Link and TigerStudioUMG

Unreal target engine: `D:\UE_5.8\Engine`

Implementation checkpoint:

- P0 document model is at UI document version 7: components, tokens,
  interactions, and Auto Layout are typed records with stable-ID CRUD,
  reference/cycle validation, explicit referenced-delete handling, Action
  coverage, migration, and `.tspaint` save/open round-trip tests.
- M0 general UI document, validation, `.tspaint` persistence, Action/MCP,
  delivery preflight, and Design Handoff package are implemented.
- M1 interactive editing now includes `Paint | UI Design | 3D Place`,
  nine select/draw tools, drag creation, move/resize handles, keyboard
  move/duplicate/delete, rotation-aware transforms, optional 8 px/15 degree
  snapping, artboard activation, artboard alignment, and a dedicated UI
  `Layers | Inspect` panel.
- M1 now also includes Ctrl/Shift and Layers-panel multi-selection, group move
  with one-step Undo, selection-bound alignment, horizontal/vertical
  distribution, automation actions for selection/arrangement, and
  aspect-preserving phone/desktop artboard transitions with desktop QA proof.
- M1 hierarchy editing now includes editable Group/Ungroup, child-preserving
  group movement, hierarchy indentation, layer forward/backward reordering,
  drag/drop nesting and root extraction, Undo, Actions, and screenshot proof.
- M1 canvas navigation now renders freeform multi-artboard document space,
  auto-places new artboards without overlap, supports middle-button pan and
  cursor-anchored wheel zoom, activates clicked artboards, and exposes
  all/artboard/selection Fit controls through both toolbar icons and Actions.
- M1 canvas manipulation now includes marquee selection with additive/toggle
  modifiers, Shift aspect-locked resize, Alt center-based resize, and visible
  edge/center Smart Guides integrated with the existing snap control.
- M1 artboard authoring now includes title-drag freeform positioning with Undo
  and Inspector creation presets for mobile, desktop, console, and broadcast
  targets.
- M1's core P1 editing scope is complete. Broader responsive screenshot QA
  continues as cross-milestone validation rather than blocking canvas editing.
- M2/P2 Inspector work has started with editable Fill, Stroke, Stroke Width,
  Radius, structured Shadow, text content, font size/weight, alignment, and
  line height. These changes use the shared UI document mutation and Undo path.
- The UI canvas renders those visual styles with document-space scaling,
  feathered geometry shadows, CSS RGBA colors, font weight/alignment, explicit
  line breaks, word wrapping, and line height. Box shadow and text shadow stay
  separate so button labels do not inherit the button surface shadow.
- M2/P2 now also includes editable pivot X/Y, horizontal/vertical
  left/center/right/stretch/scale constraints, minimum/preferred/maximum size,
  and aspect locking. Constraint anchors are recaptured after geometry edits,
  resolve deterministically against resized artboards or parents, drive the
  canvas pivot/handles, and use the shared Undo/Action mutation path.
- M2/P2 image objects now render real referenced files with Fit, Fill, Stretch,
  Tile, bounded tile scale, and source-pixel 9-slice margins. The Inspector,
  canvas, persistence, Undo, and generic object Action share one content
  contract; missing sources remain visibly diagnosed.
- M2/P2 now normalizes and edits accessibility role, label, and focus order,
  warns about missing labels and duplicate explicit focus order, and shows the
  selected object's per-target `Native/Material/Baked/Blocked` status with a
  reason from the shared delivery preflight classifier.
- M2/P3 Auto Layout foundation supports Horizontal/Vertical flow, independent
  L/T/R/B padding, gap, main-axis Start/Center/End/Space Between, cross-axis
  Start/Center/End/Stretch, absolute-positioned child escape, Wrap, and
  per-axis Fixed/Hug Content/Fill Container sizing. Constraint resolution feeds
  bottom-up Hug measurement and deterministic outer-to-inner placement shared
  by canvas, Inspector, persistence, Undo, and `paint.ui.layout.set`.
- M2/P3 artboards now persist Uniform Grid or Columns, custom horizontal and
  vertical guides, and visible safe-area insets. These authoring overlays are
  clipped per artboard and share Inspector, Undo, save/open, and
  `paint.ui.artboard.layout.set` Action contracts.
- M2/P3 validation now reports layout cycles and impossible constraints through
  one structured diagnostic contract. Inspector, Actions, document validation,
  and delivery preflight agree on blocking errors and non-blocking warnings.
- M2/P3 objects now support stable-ID breakpoint/orientation overrides.
  Wildcard and exact contexts compose deterministically, and the active artboard
  context feeds Canvas, Constraint, Auto Layout, Motion geometry, Inspector,
  Actions, persistence, and Undo.
- M2/P3 artboards now select Light, Dark, or High Contrast preview themes.
  Object `token_bindings` resolve typed token defaults, theme values, and alias
  chains into Canvas and Inspector properties without replacing stable object
  or token IDs. UI and automation share artboard/token mutation and Undo;
  automation uses `paint.ui.theme.set/inspect` and
  `paint.ui.token.theme.set/remove`.
- Image-resource embedding/hashing and adapter-output parity remain in M2/P8.
  M3-M6 remain milestone work.
- Product-adoption work is now explicit in M2A/M2B: editable template gallery,
  reusable component/variant libraries, Auto Layout presets, design tokens,
  versioned library updates, comments, revision history, reviewer mode, and
  developer inspection. Template count alone is not a completion metric.
- Detailed status: `docs/PAINTER_UI_DESIGNER_MILESTONES_KO.md`

## 1. Product Goal

Painter에 원화 제작과 별개로 `UI Design` 작업 공간을 추가한다. 사용자는
그림, 브러시 텍스처, 벡터 도형, 텍스트를 한 문서에서 조합하고 모바일 앱,
데스크톱 앱, 웹 서비스, 영상 인터페이스, 게임 HUD의 화면과 컴포넌트를
설계할 수 있어야 한다.

UI 문서는 특정 런타임에 종속되지 않는다. 같은 원본에서 디자인 리뷰,
에셋 번들, 개발 핸드오프, 클릭 가능한 프로토타입, Unreal Widget Blueprint
같은 대상별 결과를 만들 수 있어야 한다.

이 기능은 Figma 전체를 복제하거나 Painter를 웹 전용 도구로 바꾸는 작업이
아니다. 목표는 다음 네 영역을 자연스럽게 연결하는 것이다.

1. Painter의 래스터/벡터/Material Paint 자산 제작
2. 범용 UI의 화면, 레이아웃, 상태, 제약 조건, 컴포넌트 설계
3. 디자인 토큰, 반응형 규칙, 프로토타입, 개발 핸드오프
4. UMG를 포함한 검증 가능한 대상별 출력

핵심 제품 문장은 다음과 같다.

> Painter에서 UI를 설계하고, 화면·컴포넌트·상태·디자인 토큰을 하나의
> 원본으로 관리한 뒤 필요한 플랫폼에 검증된 결과를 전달한다.

## 2. General Core and Motion Designer Reference

General UI Designer가 제품의 중심이며 UMG는 첫 번째 native runtime
adapter다. UI 문서가 UMG 구조를 그대로 저장해서는 안 되고, UMG adapter가
중립 UI 문서를 Unreal 구조로 변환해야 한다.

Painter는 Motion Designer의 UMG 기능을 새로 복제하지 않는다. 다음 구현을
공유 기반으로 사용한다.

- provider-neutral 문서와 자산 패키징:
  `app/unreal_umg_document.py`
- 프로젝트 플러그인 확인/설치:
  `app/unreal_umg_plugin.py`
- Unreal 실행, 생성, 컴파일, 검증:
  `app/unreal_umg_workflow.py`
- 공유 Unreal 플러그인:
  `resources/unreal_plugins/UMG/TigerStudioUMG`
- Motion Designer의 사용자 흐름 참고:
  `app/motion_designer/ui/umg_panel.py`
- Motion Designer의 Action/MCP 패턴 참고:
  `app/actions/editor_adapter_motion_umg.py`
  및 `app/actions/motion_namespace.py`

Motion Designer의 현재 작업 흐름을 Painter에서도 유지한다.

```text
authoring document
  -> Tiger UMG document + durable resource packet
  -> project-local TigerStudioUMG install/update
  -> Unreal Editor command execution
  -> Widget Blueprint generation
  -> Kismet compile and package save
  -> reopen/load validation
  -> real Unreal result report and capture
```

사용자는 플러그인을 수동 복사하거나, Unreal에서 JSON을 해석하거나,
Blueprint 노드를 조립하거나, Widget Blueprint를 직접 컴파일할 필요가 없다.

## 3. Shared Backend Boundary

### 3.1 General UI core

다음은 어떤 출력 대상과도 독립적인 Painter 기능이다.

- artboard/page와 responsive breakpoint
- UI object, layer, group, component, instance, variant
- constraints, anchors, auto layout, grid
- design token과 theme/mode
- prototype state, trigger, transition, navigation
- accessibility와 localization 검사
- export region, slice, density variant
- 개발 handoff와 object inspection
- undo/redo, `.tspaint` persistence, Action/MCP

### 3.2 UMG에서 반드시 공유할 것

- `TigerStudioUMG` runtime/editor 모듈
- Tiger UMG 문서의 schema version
- 리소스 ID, stable source ID, content hash 정책
- 프로젝트 로컬 플러그인 설치와 업데이트
- Unreal 실행, 생성, 컴파일, 저장, 재검증
- 생성 자산의 Tiger 소유 영역과 사용자 소유 영역 분리
- 공개 설치본용 source-free 플러그인 번들

### 3.3 Painter에만 둘 것

- `.tspaint`에서 UI Design 데이터를 읽고 쓰는 provider adapter
- Painter 객체를 Tiger UMG 객체로 분류하는 preflight
- 브러시/레이어 결과를 UI texture로 결정적으로 bake하는 과정
- Painter 캔버스의 UI Design 작업 공간과 도구
- Painter 전용 Action namespace

### 3.4 Output adapter boundary

모든 출력은 공통 `UIOutputAdapter` 계약을 사용한다.

- capability manifest
- preflight
- package/build
- validate
- artifact list
- warning/blocker report
- optional launch/open/capture

초기 adapter:

- `Asset Export`: PNG/WebP/SVG와 density variants
- `Design Handoff`: object spec, token, asset manifest
- `Review Prototype`: 로컬에서 열 수 있는 클릭형 리뷰 패키지
- `Unreal UMG`: 편집 가능한 Widget Blueprint

새 플랫폼을 추가할 때 Painter 문서 모델에 플랫폼 전용 필드를 퍼뜨리지
않는다. adapter 설정은 namespaced profile로 분리한다.

### 3.5 금지

- `PainterUMG` 같은 별도 Unreal 플러그인 생성
- Motion Designer UMG 코드를 복사한 Painter 전용 workflow 생성
- 지원하지 않는 Painter 효과를 조용히 누락
- `.tspaint` 전체를 PNG 한 장으로만 평탄화하여 UMG라고 표시
- 생성 과정에서 사용자가 만든 Blueprint 그래프를 덮어쓰기
- 범용 UI 객체 이름을 `UCanvasPanel`, `UButton` 같은 UMG class로 저장
- 특정 출력 adapter의 한계 때문에 원본 문서 기능을 전역으로 제한

## 4. Primary User Scenarios

### 4.1 모바일/데스크톱 제품 화면

1. `New > UI Document`에서 Phone, Tablet, Desktop preset을 선택한다.
2. 로그인, 홈, 상세, 설정 artboard를 만든다.
3. 공통 header, button, input을 component로 만들고 instance를 배치한다.
4. spacing, color, typography를 token으로 연결한다.
5. compact/regular breakpoint와 light/dark theme를 확인한다.
6. 클릭 가능한 화면 전환을 연결해 리뷰 프로토타입을 만든다.
7. 개발자에게 spec, token, asset bundle을 전달한다.

### 4.2 UI asset와 디자인 시스템 제작

1. Painter brush와 Material Paint로 장식 frame과 icon을 만든다.
2. 장식은 export region과 9-slice 규칙을 지정한다.
3. Button, Card, Dialog, Navigation component를 variant로 구성한다.
4. token 변경으로 전체 화면의 색과 간격을 함께 검토한다.
5. @1x/@2x/@3x asset과 component inventory를 출력한다.

### 4.3 프로토타입과 개발 핸드오프

1. artboard 사이의 tap/click/hover/focus/navigation을 연결한다.
2. Tiger Studio 안에서 desktop/mobile viewport로 preview한다.
3. 공유 가능한 local review package를 생성한다.
4. 개발자는 object를 선택해 geometry, token, typography, asset 이름,
   state, 접근성 메모를 확인한다.
5. 변경된 object와 asset만 revision diff로 전달한다.

### 4.4 게임 HUD와 Unreal UMG

1. Painter에서 `New > UI Document > 1920 x 1080`을 선택한다.
2. Safe Area와 화면 기준선을 표시한다.
3. HP 바, 아이콘, 텍스트, 버튼을 배치한다.
4. 버튼의 Normal/Hover/Pressed/Disabled/Focused 상태를 만든다.
5. `Unreal Link`를 누르고 `.uproject`를 선택한다.
6. preflight 결과를 확인하고 `Generate Widget Blueprint`를 실행한다.
7. Unreal에서 컴파일된 WBP와 가져온 texture/font/material을 연다.

### 4.5 Painter 자산을 사용하는 Unreal 메뉴 화면

1. Material Paint 또는 일반 레이어에서 배경과 장식 프레임을 그린다.
2. 장식 레이어를 `UI Texture`로 지정하고 9-slice 여백을 설정한다.
3. 텍스트와 버튼은 네이티브 UI 객체로 유지한다.
4. preflight는 장식을 deterministic bake, 텍스트/버튼을 native로 표시한다.
5. 생성된 WBP는 해상도 변경 시 텍스트와 버튼을 다시 배치하며, 장식 texture는
   9-slice 규칙으로 늘어난다.

### 4.6 AI에게 UI 생성 지시

사용자는 다음처럼 요청할 수 있어야 한다.

> 모바일 쇼핑 앱의 홈, 검색, 상품 상세 화면을 만들고 공통 카드와 버튼을
> 컴포넌트로 묶어. compact 화면을 먼저 보여주고, handoff를 만들기 전에
> 변경 목록과 접근성 검사를 보여줘.

AI는 등록된 `paint.ui.*`와 대상별 delivery Action만 사용한다. 결과를
외부 대상에 즉시 쓰지 않고, 먼저 문서 변경과 output preflight를 보여준 뒤
사용자가 승인한 범위만 적용한다.

### 4.7 대상별 재생성

1. Painter에서 색, 크기, 배치, 상태를 수정한다.
2. 같은 delivery profile로 `Regenerate`를 실행한다.
3. stable source ID가 같은 object와 asset은 갱신한다.
4. 제거된 Tiger object만 생성 영역에서 정리한다.
5. handoff는 revision diff를 기록한다.
6. Unreal adapter는 사용자 소유 graph와 수동 추가 widget을 보존한다.

## 5. Painter Workspace UX

### 5.1 Workspace mode

캔버스 상단 모드는 다음처럼 구성한다.

```text
Paint | UI Design | 3D Place
```

`UI Design`은 별도 작은 팝업 프로그램이 아니라 Painter 캔버스 작업
공간이다. Paint 레이어와 UI 객체를 같은 `.tspaint` 안에서 함께 관리한다.

### 5.2 Top tool options

선택한 도구와 객체에 따라 필요한 항목만 표시한다.

- Frame preset, canvas size, DPI, safe area
- X/Y/W/H, rotation, pivot, opacity
- anchor, alignment, constraint
- auto layout direction, padding, gap, wrap
- fill, stroke, radius, shadow
- typography and localization preview
- 9-slice margins
- component/state selector
- breakpoint and theme selector
- prototype connection and transition

현재 Painter에서 지적된 불필요한 고정 Zoom control을 되살리지 않는다.
Zoom은 메뉴, 단축키, 상태 표시줄, 확대경 도구의 역할로 유지한다.

### 5.3 Left toolbar

기존 Photoshop 계열 도구 순서를 해치지 않고 UI Design 모드에서 다음
도구를 제공한다.

- Move/Select
- Frame/Artboard
- Rectangle
- Ellipse
- Line
- Pen/Path
- Text
- Image
- Component
- Slice/Export region
- Hand
- Zoom

아이콘은 Tiger Studio의 통일된 벡터 아이콘을 사용하고, 문서용 emoji나
임시 문자를 사용하지 않는다.

### 5.4 Right dock

Photoshop식 도킹 문법을 유지하면서 다음 패널을 제공한다.

- `Layers`: Paint, vector, UI object, group, component instance
- `Components`: local reusable components and variants
- `Tokens`: color, typography, spacing, radius, effect tokens
- `Prototype`: states, triggers, navigation, named events
- `Inspect`: geometry, constraints, accessibility, delivery capability

기존 `Layers | Channels | Paths`는 Painter 작업의 핵심이므로 없애지 않는다.
UI Design 패널은 같은 dock system에서 탭 그룹으로 전환하며 중첩되거나
캔버스를 과도하게 침범하지 않아야 한다.

### 5.5 Preview and Deliver

상단 `Preview`는 현재 문서를 대상과 무관하게 실행한다.

- artboard presentation
- desktop/mobile viewport
- breakpoint and orientation
- light/dark theme
- keyboard focus order
- prototype navigation
- overflow and safe-area visualization

`Deliver`는 modal/dedicated window에서 output profile을 선택한다.

- Asset Export
- Design Handoff
- Review Prototype
- Unreal UMG

각 profile은 마지막 revision, preflight, artifact, warning을 보여준다.
Layers나 Inspector에 긴 export 설정을 밀어 넣지 않는다.

### 5.6 Unreal Link

Motion Designer와 동일하게 상단의 독립된 Unreal 로고 버튼으로 연다.
Inspector, Library, Layers, Output 탭 안에 끼워 넣지 않는다.

Painter용 Unreal Link dialog는 다음만 보여준다.

- Unreal project
- destination content root
- document/provider/revision
- plugin installed/update-required status
- native/material/baked/blocked summary
- blocker와 해결 방법
- Generate/Regenerate/Cancel
- generated asset path와 Unreal에서 열기
- 실제 결과 capture

## 6. UI Object Model

### 6.1 Document and artboards

- 하나의 `.tspaint`에 여러 artboard/frame 허용
- artboard마다 width, height, DPI, safe area, orientation 저장
- desktop, mobile, console, broadcast preset 제공
- breakpoint별 width class와 orientation preview
- artboard 간 prototype navigation
- adapter는 artboard를 screen/page/widget target으로 해석
- UMG adapter는 하나의 artboard를 root Widget Blueprint로 생성

### 6.2 Primitive objects

- Frame/Group
- Rectangle/Ellipse/Line/Path
- Text
- Image/UI Texture
- Spacer
- Progress
- Button
- Toggle/Checkbox
- Slider
- Text Input
- Scroll/List item

초기 구현은 Frame, Shape, Text, Image, Button, Progress에 집중한다.
나머지는 문서 schema가 허용하되 preflight에서 단계별 지원 상태를 밝힌다.

### 6.3 Layout

- absolute canvas placement
- anchors and alignment
- left/right/top/bottom constraints
- horizontal/vertical auto layout
- padding, gap, wrap
- minimum/preferred/maximum size
- aspect ratio lock
- content-size and fill-container
- safe-area constraints
- responsive breakpoint override
- reusable layout grid and guide

레이아웃은 단순 preview hint가 아니라 저장되고 Action으로 조작되는 문서
데이터여야 한다.

### 6.4 Components and states

- component definition and instance
- instance property override
- text/image/token override
- variants
- Normal, Hover, Pressed, Disabled, Focused, Selected
- named events
- play animation, play sound, set visibility, set opacity, set material scalar
- transition duration and easing

Motion Designer의 interactive button 계약을 일반화하되, Painter 컴포넌트가
Motion composition 객체를 직접 의존하지 않게 한다.

### 6.5 Design tokens

- color
- typography
- spacing
- radius
- border
- shadow/effect
- opacity
- icon and asset alias
- light/dark/high-contrast theme mode

token은 이름과 stable ID를 갖는다. 화면과 component는 token 값을 복사하지
않고 참조한다. output adapter는 지원 대상에 맞게 JSON token, CSS variable,
generated data, material parameter 또는 상수 asset으로 변환한다.

### 6.6 Prototype and interaction

- click/tap/double-click
- hover/pressed/focus/keyboard activation
- change state/variant
- open overlay/close overlay
- navigate/back
- scroll to object
- play transition/sound
- named event

General preview는 이 계약을 직접 실행한다. Runtime adapter가 지원하지 않는
trigger나 action은 preflight에서 명시하고 조용히 제거하지 않는다.

### 6.7 Developer inspection

선택한 object에서 다음 정보를 복사하거나 내보낼 수 있다.

- stable ID와 semantic name
- bounds, spacing, constraint, z-order
- token references와 resolved value
- typography
- fill/stroke/effect
- asset path, format, density, 9-slice
- component/variant/state
- accessibility role, label, focus order
- prototype interaction
- adapter별 disposition

## 7. `.tspaint` Persistence

`.tspaint`는 계속 Painter의 원본 문서다. 다음 `ui_document` 영역을 버전
관리되는 형태로 추가한다.

```json
{
  "ui_document": {
    "schema": "tigerstudio.painter.ui.v1",
    "artboards": [],
    "objects": [],
    "components": [],
    "tokens": [],
    "prototype": {},
    "delivery_profiles": [],
    "linked_targets": {
      "unreal_umg": {
        "destination_root": "/Game/TigerStudio/Generated",
        "last_generated_revision": 0
      }
    }
  }
}
```

`.tspaint`에는 Unreal 프로젝트의 절대 경로를 필수 데이터로 고정하지 않는다.
사용자 로컬 연결 정보와 최근 프로젝트는 app setting에 저장하고, 문서에는
portable destination과 source metadata만 둔다.

3D Blockout은 계속 밑그림용 편집 데이터로 저장한다. 기본적으로 UMG runtime
객체가 아니며, 사용자가 명시적으로 캡처한 배경 또는 depth/material asset만
UI 자산으로 변환한다.

## 8. General Output and Handoff Contract

`.tspaint`의 `ui_document`가 유일한 authoring source다. 모든 delivery
adapter는 동일한 normalized snapshot과 stable ID를 입력으로 받는다.

### 8.1 Asset Export

- PNG/WebP raster
- SVG for supported vector/text content
- @1x/@2x/@3x 또는 custom density
- export regions and slices
- transparent padding trim
- optional texture atlas
- 9-slice metadata
- color space and alpha report
- deterministic filenames from semantic name and stable ID

SVG로 충실히 표현할 수 없는 Painter 효과는 raster asset으로 분리하며,
SVG 안에 의미 없이 거대한 bitmap을 숨겨 넣지 않는다.

### 8.2 Design Handoff

handoff package:

- `design_document.json`
- `tokens.json`
- `components.json`
- `interactions.json`
- `assets/`
- `manifest.json`
- human-readable inspection pages
- revision diff

개발자는 Painter 설치 없이 geometry, layout, token, component state,
accessibility, asset 정보를 확인할 수 있어야 한다.

### 8.3 Review Prototype

초기 prototype은 배포용 웹 애플리케이션 codegen이 아니다. 로컬 또는
정적 hosting에서 열 수 있는 self-contained review artifact다.

- artboard navigation
- overlay
- component state
- breakpoint/theme switch
- pointer and keyboard interaction
- comment anchor를 위한 stable object ID

prototype renderer와 Painter preview는 같은 normalized interaction 계약을
사용해 동작 차이를 줄인다.

### 8.4 Output capability report

모든 adapter는 object별로 다음 중 하나를 반환한다.

- `Native`
- `Converted`
- `Baked`
- `Blocked`

report에는 대상, 원인, 품질 손실, 수정 방법, 생성 artifact를 포함한다.
이 공통 report 위에 UMG의 `UI Material` 같은 대상별 세부 disposition을
추가한다.

## 9. Tiger UMG Document Contract

Painter provider는 `Provider: "painter"`를 사용한다. provider-neutral Tiger
UMG 문서는 Motion Designer와 같은 schema 및 plugin을 사용한다.

필요한 계약 확장은 한 번에 공유 영역에 반영한다.

- artboard/root metadata
- panel/layout kind
- constraints and anchors
- 9-slice brush margins
- component definition/instance metadata
- style states and transitions
- design token references
- accessibility metadata
- bake report and source region

serialized meaning이 달라지면 `TIGER_UMG_SCHEMA_VERSION`과 Unreal C++ type 및
conversion을 같은 변경에서 올린다. Python만 먼저 바꾸거나 plugin이 모르는
필드를 `PayloadJson`에 넣고 지원된다고 주장하지 않는다.

## 10. UMG Conversion Matrix

| Painter object/feature | UMG disposition | Target |
| --- | --- | --- |
| Artboard | Native | `UUserWidget` root + `UCanvasPanel` |
| Frame/absolute group | Native | `UCanvasPanel` |
| Horizontal auto layout | Native | `UHorizontalBox` |
| Vertical auto layout | Native | `UVerticalBox` |
| Uniform grid | Native | `UUniformGridPanel` |
| Text | Native | `UTextBlock` with imported font |
| Image/UI Texture | Native | `UImage`/Slate Brush |
| Rectangle/simple shape | Native or Material | brush/color or shared UI Material |
| Button | Native | `UTigerStudioButton`/`UButton` |
| Progress | Native | `UProgressBar` |
| 9-slice panel | Native | Box Brush margins |
| Simple opacity/transform animation | Native | `UWidgetAnimation` |
| Named interaction/sound | Native | Tiger action records |
| Gradient/simple procedural fill | UI Material | generated/shared UI Material |
| Layer mask with supported semantics | UI Material | mask texture/material parameter |
| Painted layer or complex vector group | Baked | deterministic texture |
| Material Paint relief | Baked/Material | color + optional normal/height UI Material |
| Unsupported blend/effect | Baked or Blocked | explicit preflight result |
| 3D Blockout scene | Blocked by default | optional explicit background bake |
| Arbitrary script/code | Blocked | no silent execution |

`Baked`는 실패가 아니다. 다만 preflight와 결과 보고서에 다음을 표시한다.

- source object IDs
- bake resolution and color space
- alpha mode
- texture count and estimated memory
- 9-slice/tiling policy
- regeneration ownership
- 확대 시 품질 위험

## 11. Delivery Preflight

모든 delivery 전에 객체별 판정을 보여준다. UMG 예시는 다음과 같다.

```text
Native     18
Material    3
Baked       5
Blocked     1
Warnings    4
```

blocker 예:

- 누락된 font/image
- font license 또는 embedding 정책 미확인
- 지원되지 않는 layout cycle
- component reference cycle
- 상태에 필요한 source object 없음
- bake target이 최대 texture 크기 초과
- Unreal project/plugin/engine 호환성 실패
- 사용자 소유 generated boundary 충돌
- 선택한 adapter가 interaction/layout 기능을 지원하지 않음

경고 예:

- 작은 터치 target
- 낮은 text contrast
- 번역 문자열 overflow
- 지나치게 큰 texture memory
- Material Paint parallax를 정적 texture로 bake
- SVG 대상에서 raster-only effect 사용
- prototype과 runtime target의 navigation 의미 차이

## 12. Action / AI Contract

### 12.1 UI authoring

- `paint.ui.document.inspect`
- `paint.ui.artboard.add/update/remove`
- `paint.ui.object.add/update/remove/reorder`
- `paint.ui.layout.set`
- `paint.ui.constraint.set`
- `paint.ui.component.create/instantiate/update`
- `paint.ui.state.set`
- `paint.ui.token.create/update/apply`
- `paint.ui.asset.mark`
- `paint.ui.accessibility.audit`
- `paint.ui.prototype.link/set/remove`
- `paint.ui.preview.set`

### 12.2 General delivery

- `paint.ui.delivery.profiles`
- `paint.ui.delivery.preflight`
- `paint.ui.delivery.package`
- `paint.ui.delivery.validate`
- `paint.ui.delivery.artifacts`
- `paint.ui.asset.export`
- `paint.ui.handoff.export`
- `paint.ui.prototype.export`

### 12.3 Unreal delivery

- `paint.umg.plugin.status`
- `paint.umg.plugin.install`
- `paint.umg.preflight`
- `paint.umg.package`
- `paint.umg.generate`
- `paint.umg.regenerate`
- `paint.umg.result.inspect`

`paint.umg.*`는 Painter adapter 이름일 뿐이다. 내부 workflow와 plugin은
Motion Designer와 공유한다.

모든 문서 mutation은 Painter undo stack에 들어간다. Unreal 프로젝트에
파일을 쓰는 Action은 dry-run 설명과 변경 대상을 제공하며, AI는 preflight
결과를 확인하지 않고 blocked 항목을 강제 진행하지 않는다.

## 13. Accessibility and Design QA

- text/background contrast 검사
- keyboard focus state 존재 여부
- button/toggle disabled 상태 존재 여부
- 최소 pointer/touch target
- text scale 및 localization overflow
- safe area 침범
- anchor/constraint 모순
- off-canvas object
- pixel snapping과 1 px line 흔들림
- 9-slice margin 역전
- transparent click target
- duplicate component/state ID

QA는 캔버스 preview만 보지 않는다. handoff/prototype artifact를 다시 열어
검사하며, UMG는 생성된 Widget Blueprint를 실제 Unreal viewport에서 열고
capture하여 비교한다.

## 14. Performance and Rendering

- UI 객체는 retained scene으로 유지하고 매 frame 전체 문서를 다시 rasterize
  하지 않는다.
- Painter layer texture는 dirty region만 갱신한다.
- 반복 component asset은 texture atlas 후보로 분석한다.
- high zoom은 canvas texture display와 viewport overlay를 분리한다.
- remote session에서는 OpenGL 실패 시 기존 CPU fallback을 유지한다.
- preflight는 예상 texture memory, draw count, material count를 보고한다.
- Material Paint의 normal/height는 요청한 UI Material profile에서만
  패키징하며 기본 HUD를 불필요하게 무겁게 만들지 않는다.

## 15. Implementation Phases

### Phase 0: Contract and document foundation

- `.tspaint` `ui_document` schema
- artboard and primitive object model
- stable IDs, undo/redo, save/load round trip
- output adapter interface and capability manifest
- native/converted/baked/blocked classifier
- UMG contract extension proposal는 이 중립 계약 위에서 작성

Exit:

- UI document save-load-save가 canonical하게 일치
- unsupported feature가 silent omission 없이 분류됨
- UMG class 이름 없이 general UI sample을 저장할 수 있음

### Phase 1: Painter UI Design workspace

- `Paint | UI Design | 3D Place`
- Frame, Shape, Text, Image, Button
- Layers integration
- geometry, anchors, constraints
- auto layout basics
- 9-slice
- component states
- breakpoint/theme preview

Exit:

- mobile app 화면과 16:9 HUD를 마우스와 Action 양쪽으로 제작
- 창 크기 변경과 원격 환경에서 패널 중첩 없음

### Phase 2: General Preview and Deliver

- general prototype preview
- Asset Export profile
- Design Handoff profile
- Review Prototype profile
- object inspection
- common delivery preflight and artifact report

Exit:

- mobile/desktop UI sample이 Painter 없이 review 가능
- @1x/@2x/@3x asset, token, component, interaction manifest 생성
- export artifact를 다시 읽어 stable ID와 revision 검증

### Phase 3: Components, tokens, prototype

- component definitions/instances/variants
- token library and theme modes
- interactions and named events
- progress/toggle/slider/input/list
- responsive and localization preview

Exit:

- 하나의 component 수정이 모든 instance에 일관되게 반영
- light/dark와 compact/regular mode가 같은 원본을 사용
- pointer와 keyboard prototype이 general preview에서 동작

### Phase 4: Shared Unreal Link

- Painter provider adapter
- Painter Unreal Link dialog
- `paint.umg.*` Actions
- shared plugin schema/conversion update
- project-local plugin install/update
- Generate/Regenerate

Exit:

- UE 5.8에서 WBP 생성, compile, save, reopen 성공
- Painter 재생성이 사용자 소유 Blueprint 영역을 보존

### Phase 5: Painter-specific visual assets

- deterministic layer/group bake
- alpha/color-space validation
- 9-slice texture authoring
- supported UI Material generator
- optional Material Paint normal/height presentation

Exit:

- native와 bake 결과가 preflight 보고와 일치
- general prototype과 실제 Unreal capture에서 확대/축소 및 state 전환 검증

### Phase 6: AI co-design and production QA

- 자연어 UI 생성/수정
- 변경 계획, 부분 적용, undo
- accessibility audit
- performance budget
- target별 artifact navigation and evidence capture

Exit:

- AI가 등록 Action만으로 mobile app과 샘플 HUD를 생성
- delivery 전 변경 목록과 capability/disposition을 설명
- handoff, prototype, 실제 Unreal 결과 증거가 자동 수집됨

## 16. File Placement Plan

예상 Python 모듈:

- `app/painter_ui_document.py`
- `app/painter_ui_layout.py`
- `app/painter_ui_components.py`
- `app/painter_ui_prototype.py`
- `app/painter_ui_delivery.py`
- `app/painter_ui_preflight.py`
- `app/painter_umg_adapter.py`
- `app/painter_ui_workspace.py`
- `app/painter_ui_delivery_dialog.py`
- `app/painter_unreal_link_dialog.py`
- `app/actions/editor_adapter_painter_ui.py`
- `app/actions/editor_adapter_painter_umg.py`

공유 변경:

- `app/unreal_umg_document.py`
- `app/unreal_umg_workflow.py`
- `resources/unreal_plugins/UMG/TigerStudioUMG`

테스트:

- `tests/test_painter_ui_document.py`
- `tests/test_painter_ui_layout.py`
- `tests/test_painter_ui_components.py`
- `tests/test_painter_ui_prototype.py`
- `tests/test_painter_ui_delivery.py`
- `tests/test_painter_umg_adapter.py`
- `tests/test_painter_ui_actions.py`
- shared `tests/test_unreal_umg_document.py`
- shared `tests/test_unreal_umg_plugin.py`

`app/video_editor_window.py`에는 어떤 UI Designer 또는 UMG 기능도 추가하지
않는다.

## 17. Verification Gates

기능 완료 주장은 다음을 모두 통과한 뒤에만 한다.

1. `.tspaint` UI document round trip
2. object/layout/component Action tests
3. breakpoint/theme/prototype interaction tests
4. Asset Export density, alpha, naming, 9-slice tests
5. Handoff package schema and revision-diff tests
6. self-contained Review Prototype reopen/navigation tests
7. accessibility and localization overflow tests
8. common adapter capability and blocked-preflight tests
9. Painter and Motion Designer UMG provider compatibility tests
10. `tools/build_unreal_umg_plugin.py` plugin rebuild
11. canonical `D:\UE_5.8\Engine` compile
12. real UE 5.8 Widget Blueprint generation
13. Kismet compile, save, reload validation
14. regenerate while preserving user-owned additions
15. real Unreal viewport capture and pixel/content review
16. public installer contains only source-free UMG bundle
17. architecture and debug-capture boundary guards

Disposable captures and reports may use `debugCapture`, but source art,
templates, fonts, SDKs, plugins, and required test assets must use durable
project locations.

## 18. Initial Release Scope

첫 출시에서 반드시 제공:

- one/multiple artboards
- Frame, Shape, Text, Image, Button
- Layers, geometry, anchors, constraints
- horizontal/vertical auto layout
- responsive breakpoint and light/dark theme preview
- 9-slice
- component, instance, variant, button states
- design token
- basic prototype navigation and overlay
- Asset Export with density variants
- Design Handoff package
- local Review Prototype
- accessibility and localization checks
- common native/converted/baked/blocked preflight
- Painter Unreal Link
- Generate/Regenerate
- Action/MCP parity
- real UE 5.8 proof

첫 출시에서 제외:

- Figma 수준의 실시간 다중 사용자 협업
- production-ready HTML/CSS/React/Flutter/Swift code generation
- cloud comment server and organization workspace
- arbitrary Blueprint graph authoring
- Painter 3D Blockout 전체를 Unreal runtime scene으로 변환
- 모든 Photoshop/Painter blend mode의 실시간 UMG 재현
- 지원되지 않는 효과의 묵시적 손실 변환

이 경계로 시작하면 Painter의 강점인 직접 만든 시각 자산을 살리면서
모바일, 데스크톱, 웹, 영상, 게임 UI를 하나의 중립 문서에서 설계할 수 있다.
Motion Designer가 이미 만든 Unreal 전달 구조는 그 위에 놓이는 첫 번째
native runtime adapter로 중복 없이 확장된다.
