# Painter UI Figma-Class Interface Specification

Status: active UX contract; UI-P0 shell and M1 ruler-guide lifecycle implemented

Date: 2026-07-29

## Implementation Checkpoint (2026-07-28)

Implemented:

- canvas-local bottom floating toolbar with responsive density
- left `Layers / Assets` navigation; Sections, Components, and Tokens now live
  under Assets instead of permanent right-side tabs
- right contextual `Design / Prototype / Inspect` modes
- collapsible navigator and properties panels
- automatic navigator compaction when the usable canvas becomes too narrow
- zoom-adaptive horizontal and vertical canvas rulers
- ruler drag to create persistent, undoable artboard guides
- shared UI/Action guide mutations with create/remove/clear automation
- grouped Shape/Content flyouts in the compact bottom toolbar
- direct guide move and drag-back-to-ruler deletion
- persistent guide visibility, lock state, and per-artboard ruler origin
- ruler-corner drag to set origin and double-click/menu reset
- localized shell labels through the Painter i18n surface
- focused UI tests and reproducible screenshot QA

Still required by this contract:

- the complete Polygon/Star/Arc creation set and vector-network editing
- selection-kind-specific Inspector sections
- temporary compact properties popover when both panels are minimized
- persisted panel widths and minimized state
- full M1+ interaction and delivery work tracked by the milestone document

Related roadmap:

- `docs/PAINTER_UI_FIGMA_UX_MILESTONES_2026_KO.md`
- `docs/PAINTER_UI_FIGMA_INTERFACE_ACTION_MATRIX_KO.md`
- `docs/SPEC_PAINTER_DOCUMENT_FORMAT.md`

## 1. 목적

이 문서는 Painter UI Design 기능을 단순히 나열하지 않고 다음 질문에
답하는 UI 계약이다.

1. 사용자는 어디에서 기능을 발견하는가?
2. 무엇을 선택했을 때 기능이 나타나는가?
3. 캔버스에서 직접 조작하는 부분과 Inspector에서 수치로 조절하는
   부분은 무엇인가?
4. 기능이 필요하지 않을 때 무엇을 숨기는가?
5. 같은 작업을 Action/MCP에서는 어떻게 호출하는가?

협업, 플러그인, FigJam, 음성 채팅은 이 명세 범위에서 제외한다.

## 2. 조사 결과

Figma UI3가 작업 공간을 넓게 유지하는 방식은 다음과 같다.

- 왼쪽은 Navigation, 중앙은 Canvas, 오른쪽은 Properties다.
- 제작 도구는 캔버스 하단의 작은 툴바에 있다.
- Properties는 선택한 레이어와 현재 모드에 따라 내용이 바뀐다.
- UI를 최소화하면 양쪽 패널을 접고, 객체를 선택한 순간에만 작은
  Properties 패널을 임시로 다시 보여준다.
- Selection Actions는 Mask, Component, Boolean처럼 현재 선택에서 가능한
  명령만 노출한다.
- Components와 Assets는 왼쪽 Assets에서 검색하고 캔버스로 드래그한다.
- Prototype은 오른쪽 모드와 캔버스 연결선을 함께 사용한다.

현재 Painter UI Design은 다음 문제가 있다.

- Select, Frame, Rectangle, Ellipse, Line, Text, Image, Button, Progress,
  Snap, Fit, Motion 명령이 상단 고정 행에 동시에 노출된다.
- 오른쪽에 Layers, Sections, Components, Tokens, Motion, Publish, Inspect가
  동급 탭으로 항상 존재한다.
- Artboard 설정과 선택 객체 설정이 같은 세로 공간을 경쟁한다.
- 데이터 모델은 넓지만 기능 발견 구조가 구현 모듈 구조를 그대로
  드러낸다.

새 UI는 코드 모듈별 탭이 아니라 사용자의 작업 단계별 표면으로 바꾼다.

## 3. 전체 화면 구조

### 3.1 상단 바

항상 표시:

- 메인 메뉴
- 문서 이름과 저장 상태
- Undo / Redo
- Paint / UI Design / 3D Place 모드
- Preview
- Export

조건부 표시:

- 저장 또는 전달 오류
- 누락 폰트/에셋
- 문서 진단 경고

상단에서 제거:

- 개별 도형 도구
- Fit 명령 여러 개
- Motion Actor, Animate, Motion Preview의 상시 버튼
- Template 목록

### 3.2 왼쪽 Navigation

상단 아이콘 탭:

- `Layers`
- `Assets`

Layers:

- Pages
- Sections
- 현재 Page의 계층형 Layers
- 검색
- visibility / lock
- drag reorder / reparent
- 하단의 New Page, New Section, New Layer, Delete

Assets:

- Components
- Local Libraries
- Styles
- Variables
- Templates
- Images / Icons
- Motion Clips / Motion Actors

Assets는 검색 결과를 List/Grid로 바꿀 수 있고 캔버스로 드래그한다.
Templates는 Inspector 탭이 아니라 Assets 내부의 넓은 Gallery/Drawer로
연다.

### 3.3 중앙 Canvas

- 무한 캔버스
- 여러 Artboard 자유 배치
- 상단/왼쪽 Ruler
- Ruler에서 끌어내는 Guide
- Smart Guide, 거리, gap, padding 표시
- 선택 경계, resize/rotate handle
- Auto Layout on-canvas handle
- Prototype connection node
- 하단 중앙 floating toolbar
- 일시적으로 나타나는 zoom popover

### 3.4 오른쪽 Properties

상단 모드:

- `Design`
- `Prototype`
- `Inspect`

별도 고정 탭으로 두지 않는 항목:

- Layers: 왼쪽 Navigation
- Sections: 왼쪽 Pages/Layers
- Components/Tokens: 왼쪽 Assets와 선택 기반 Design
- Motion: Prototype 또는 선택 객체의 Motion 섹션
- Publish: 상단 Export 및 Inspect Delivery

## 4. 하단 Floating Toolbar

기본 UI Design 툴바:

| 그룹 | 기본 아이콘 | 길게 누르기 / Flyout |
| --- | --- | --- |
| Move | Move | Hand, Scale |
| Region | Frame | Frame, Section, Slice |
| Shape | Rectangle | Rectangle, Ellipse, Line, Arrow, Polygon, Star |
| Vector | Pen | Pen, Pencil, Vector Edit |
| Text | Text | Horizontal Text, Area Text |
| Resources | Grid | Components, Templates, Styles, Variables, Images |
| Actions | Spark/Search | Quick Actions와 명령 검색 |
| Preview | Play | 현재 Flow 재생 |

규칙:

- 마지막으로 사용한 하위 도구가 그룹의 대표 아이콘이 된다.
- Flyout은 툴바 위로 열고 선택 후 닫힌다.
- 툴바는 캔버스 레이아웃 공간을 차지하지 않는다.
- 활성 도구만 강조하고 도구명은 tooltip과 접근성 이름으로 제공한다.
- `Esc`는 Select로 돌아간다.
- Paint와 3D Place에서는 같은 위치에 해당 모드 전용 툴바를 표시한다.

## 5. 선택별 Design Inspector

### 5.1 선택 없음

표시:

- Page 배경
- Ruler / Grid / Guide
- Local Styles
- Local Variables
- Export Page

숨김:

- X/Y/W/H
- Fill/Stroke
- Component
- Motion
- Prototype Interaction

### 5.2 Artboard 선택

표시 순서:

1. Artboard 이름과 preset
2. W/H, 방향, breakpoint
3. Layout Grid와 Safe Area
4. Background와 Clip Content
5. Prototype Flow Starting Point
6. Theme/Variable Mode
7. Export

Canvas 직접 조작:

- 제목 드래그로 이동
- 모서리 resize
- preset 변경 시 resize preview
- Ruler/Guide

### 5.3 Frame 또는 Group 선택

표시 순서:

1. Selection Actions: Component, Mask, Boolean, More
2. Layout: X/Y/W/H, rotation, constraints
3. Auto Layout
4. Appearance
5. Clip / Overflow
6. Accessibility
7. Export

Auto Layout를 켜면 일반 Layout 섹션이 `Auto Layout`로 바뀌며 direction,
padding, gap, alignment, wrap, Hug/Fill/Fixed를 표시한다.

### 5.4 Shape 선택

표시 순서:

1. Selection Actions: Boolean, Mask, Component
2. Position / Size / Rotation
3. Shape-specific properties
4. Fill stack
5. Stroke stack
6. Effects
7. Opacity / Blend
8. Export

Shape-specific:

- Rectangle: independent radius
- Ellipse: Arc start/end/inner ratio
- Polygon: sides
- Star: points/inner ratio
- Line/Arrow: cap, join, arrow head

Canvas 직접 조작:

- radius handle
- arc handle
- polygon/star count와 inner ratio handle
- gradient handle

### 5.5 Path / Vector 선택

Normal selection:

- Position
- Fill / Stroke / Effects
- Boolean / Mask

Enter 또는 double click로 Vector Edit:

- node 선택
- segment 선택
- straight/Bezier 변환
- handle 이동
- join / split / close / reverse
- outline stroke
- simplify

Vector 명령은 캔버스 위 작은 contextual bar 또는 우클릭 메뉴에 나타나고
오른쪽에는 정밀 수치만 둔다.

### 5.6 Text 선택

표시 순서:

1. Text content
2. Font family / style / variable axes
3. Size / line height / letter spacing
4. Alignment / paragraph
5. Auto width / Auto height / Fixed box
6. Fill / Stroke / Effects
7. Text Style / Variable binding
8. Accessibility / Export

Canvas 직접 조작:

- double click inline edit
- text box resize
- mixed range selection
- overflow indicator

### 5.7 Image 선택

표시:

- Replace
- Fit / Fill / Crop / Tile
- focal point
- image transform
- nine-slice
- opacity / blend / effects
- resource status
- export

Canvas 직접 조작:

- crop mode
- focal point
- image reposition
- restore original ratio

### 5.8 Component Definition 선택

표시:

- Component name / description
- Add property
- Boolean / Text / Instance Swap / Slot / Variant properties
- State and Variant axes
- Documentation link
- Instance count
- Local Library package status

Canvas:

- component-set 경계
- Add Variant affordance
- Variant property label
- conflicting combination warning

### 5.9 Component Instance 선택

가장 위에 표시:

- Main Component
- Variant dropdowns
- Text properties
- Boolean toggles
- Instance swap
- Slot content
- Reset property / Reset all

그 아래:

- Instance-local geometry
- 허용된 override
- Prototype
- Delivery

내부 레이어를 먼저 찾게 만들지 않고 제작자가 노출한 Component Properties를
우선한다.

### 5.10 다중 선택

표시:

- mixed value 표시 `—`
- Align / Distribute
- Tidy Up / gap
- group / frame selection
- common Fill/Stroke/Text/Effects
- copy/paste properties
- select matching

서로 호환되지 않는 속성은 숨기고 비활성 필드를 줄 세우지 않는다.

## 6. Prototype UI

진입:

- 오른쪽 `Prototype`
- 선택 객체 오른쪽의 connection node drag
- Quick Actions의 `Add interaction`

선택 없음:

- Flow 목록
- device
- background
- orientation
- presentation options

객체 선택:

- Trigger
- ordered Actions
- Destination
- Transition
- easing / duration / direction

Frame 선택:

- Overflow: None / Horizontal / Vertical / Both
- fixed/sticky child 설정
- initial scroll position

Component/Instance 선택:

- Change Variant
- interactive component inheritance
- Normal/Hover/Pressed/Focused/Disabled transitions

Advanced:

- Set Variable
- Set Variable Mode
- Condition
- Multiple actions
- Play Sound
- Play Motion Clip

Motion 편집 원칙:

- Painter는 animation name, trigger, states, duration summary, binding status를
  표시한다.
- 키프레임, graph, easing curve 본문은 Motion Designer가 소유한다.
- `Animate in Motion Designer`는 선택 객체의 Prototype/Motion 섹션과
  우클릭 메뉴에서만 제공한다.
- 빈 Motion 링크를 상시 Inspector 탭으로 보여주지 않는다.

## 7. Inspect / Delivery UI

선택 없음:

- document summary
- variables
- assets
- preflight
- revision

객체 선택:

- geometry와 spacing
- layout와 constraints
- typography
- colors/styles/variables
- component properties
- prototype interactions
- accessibility
- export configurations
- target delivery

Delivery target switch:

- Web
- App
- Unreal UMG

각 feature 행:

- Requested
- Resolved disposition
- Reason
- Artifact

Disposition:

- Native
- Vector / Platform Effect / Material
- Baked
- Actor Only
- Blocked

코드 스니펫은 실제 adapter가 생성한 경우에만 표시한다. Painter가 지원하지
않는 CSS/iOS/Android/UMG 코드를 임의로 만들어 보여주지 않는다.

## 8. Resources UI

하단 Resources 또는 왼쪽 Assets에서 연다.

### Components

- 검색
- local package
- family / variant
- list/grid
- preview
- drag instance to canvas

### Styles

- Color
- Text
- Effect
- Layout Grid
- 검색과 usage count
- 선택 property에 apply

### Variables

- Collection 목록
- mode column
- type icon
- alias chain
- scope
- usage
- create/edit는 modal 또는 넓은 drawer

작은 Inspector 안에 변수 표 전체를 넣지 않는다.

### Templates

- category, platform, theme, target filters
- desktop/mobile paired thumbnail
- pages/components/variables/interactions/dependencies/license preview
- Create New Document
- Insert Page
- Insert Component Set
- Apply Theme

### Images / Icons

- thumbnail grid
- search/tag
- place as image
- apply as fill
- replace selected

## 9. Productivity UI

Quick Actions:

- `Ctrl+/` 또는 Actions 아이콘
- 명령, layer, page, component, style, variable, asset 통합 검색
- 결과에 shortcut과 실행 대상 표시

Find/Replace:

- Text
- Font
- Style
- Variable
- Component
- Asset
- 변경 preview와 선택 적용

Select Similar:

- kind
- fill/stroke
- text style
- component/variant
- token
- effect
- interaction

Batch Rename:

- Layers 선택 후 Rename
- prefix/suffix/number/replace pattern
- 적용 전 결과 preview

Shortcut:

- 메뉴와 tooltip에 shortcut 표시
- 검색 가능한 shortcut map
- 충돌 경고

## 10. 기존 기능 재배치 표

| 기존 기능 | 현재 위치 | 새 위치 |
| --- | --- | --- |
| Artboard preset/add/delete | 오른쪽 상단 고정 | 왼쪽 Pages `+`, Artboard Design |
| Layers | 오른쪽 Inspector 탭 | 왼쪽 Layers |
| Sections | 오른쪽 Inspector 탭 | 왼쪽 Pages/Sections |
| Components | 오른쪽 Inspector 탭 | 왼쪽 Assets, 선택 Instance Design |
| Tokens | 오른쪽 Inspector 탭 | 왼쪽 Assets/Variables, property binding picker |
| Motion Binding/Delivery | 오른쪽 Inspector 탭 | 선택 객체 Prototype/Motion, Inspect Delivery |
| Publish/Production | 오른쪽 Inspector 탭 | 상단 Export, Inspect Delivery |
| Template gallery | 캔버스 위 고정 strip | Resources Gallery/Drawer |
| Select/Frame/Shape/Text | 상단 고정 행 | 하단 floating toolbar |
| Fit All/Artboard/Selection | 상단 버튼 3개 | zoom popover, Quick Actions |
| Snap | 상단 고정 버튼 | View options popover와 shortcut |
| Fill/Stroke/Effects | 긴 Inspect form | contextual Design sections |
| Auto Layout | 긴 Inspect form | Layout 섹션 + on-canvas handles |
| Prototype | Production 중심 | 오른쪽 Prototype + canvas connections |
| Figma import/export | Publish 탭 | File/Import, Export/Exchange |
| UMG | Publish 탭 | Inspect Delivery > Unreal UMG |
| AI Design | Publish 탭 | Actions > AI Design |
| Review comments | Production 탭 | 기존 로컬 Review artifact만 호환 유지, UI Design 핵심 표면에서는 제외 |

## 11. 기능별 Action 연결 원칙

- UI와 Action은 같은 mutation service를 호출한다.
- Canvas handle 조작도 마지막에는 전용 `paint.ui.*` mutation이 된다.
- popup/drawer는 데이터를 소유하지 않는다.
- Inspector가 닫혀 있어도 Action 결과가 Canvas와 Layers에 즉시 반영된다.
- selection-dependent Action은 명시적인 object ID를 받는다.
- 여러 객체 작업은 partial success를 허용하지 않고 전체 preview 후 하나의
  Undo 단위로 적용한다.
- destructive 명령은 대상 count와 결과를 먼저 표시한다.

## 12. 반응형 UI 규칙

1600 px 이상:

- 왼쪽 240 px
- 오른쪽 288 px
- Canvas 나머지

1280-1599 px:

- 왼쪽 220 px
- 오른쪽 260 px
- section label 축약 가능

1280 px 미만:

- 한쪽 panel만 고정
- 다른 panel은 overlay drawer
- floating toolbar는 두 행이 아니라 group flyout 사용

Minimize UI:

- 양쪽 panel 숨김
- floating toolbar 유지
- 객체 선택 시 compact temporary Properties

패널 너비는 사용자가 조절하고 저장할 수 있으나 Canvas 최소 너비를 침범하면
overlay mode로 전환한다.

## 13. 구현 순서

### UI-P0 Shell

- bottom floating toolbar
- left Layers/Assets
- right Design/Prototype/Inspect
- panel collapse/resize/minimize
- 기존 Inspector 탭 재배치

### UI-P1 Context Inspector

- selection type router
- no-selection/artboard/frame/shape/text/image/multi states
- Selection Actions
- mixed value와 progressive disclosure

### UI-P2 Canvas Direct Manipulation

- ruler/guide
- Smart Guide/measurement
- on-canvas Auto Layout
- vector/shape handles
- zoom/pan popover

### UI-P3 Components and Resources

- Assets browser
- Component property-first instance UI
- Styles/Variables drawers
- Template Gallery

### UI-P4 Prototype and Motion

- Prototype mode
- connection node
- overflow/transition/variables/condition
- canonical Motion binding UI

### UI-P5 Inspect and Delivery

- Dev inspection
- target switch
- feature disposition
- adapter-owned snippets/artifacts

### UI-P6 Productivity and QA

- Quick Actions
- Find/Replace
- Select Similar
- Batch Rename
- shortcut map
- desktop/compact/minimized screenshot QA

## 14. 완료 기준

- 기능이 구현되어도 진입점이 없으면 완료가 아니다.
- 선택과 무관한 control이 오른쪽에 남으면 완료가 아니다.
- Canvas 직접 조작과 수치 Inspector가 같은 결과를 만들지 않으면 완료가 아니다.
- UI와 Action이 다른 mutation을 사용하면 완료가 아니다.
- 좁은 화면에서 Canvas 대신 panel이 화면 대부분을 차지하면 완료가 아니다.
- 영어/한국어에서 label이 잘리거나 control이 겹치면 완료가 아니다.
- 실제 adapter artifact 없이 delivery 지원으로 표시하면 완료가 아니다.

## 15. 조사 자료

- Figma UI3:
  https://help.figma.com/hc/en-us/articles/23954856027159-Navigating-UI3-Figma-s-new-UI
- Figma Properties:
  https://help.figma.com/hc/en-us/articles/360039832014-Design-Prototype-and-view-Code-in-the-Properties-Panel
- Figma toolbar:
  https://help.figma.com/hc/en-us/articles/360041064174-Access-design-tools-from-the-toolbar
- Figma component properties:
  https://help.figma.com/hc/en-us/articles/5579474826519-Explore-component-properties
- Figma variants:
  https://help.figma.com/hc/en-us/articles/360056440594-Create-and-use-variants
- Figma variables:
  https://help.figma.com/hc/en-us/articles/15343107263511-Apply-variables-to-designs
- Figma prototype guide:
  https://help.figma.com/hc/en-us/articles/360040314193-Guide-to-prototyping-in-Figma
- Figma scroll/overflow:
  https://help.figma.com/hc/en-us/articles/360039818734-Prototype-scroll-and-overflow-behavior
- Figma Smart Animate:
  https://help.figma.com/hc/en-us/articles/360039818874-Smart-animate-layers-between-frames

## 16. UI Design Compact Shell Contract

- The always-visible template access band is 34 px high. Larger template
  browsing belongs in the gallery, not in permanent canvas chrome.
- The standalone right inspector uses a 252-268 px width envelope. Embedded
  use may expand only to 280 px.
- Inspector typography and controls use compact density while preserving
  readable Korean and English labels, keyboard focus, and tooltips.
- Shape and content creation commands are grouped under icon-first flyouts so
  secondary tools do not permanently reduce canvas space.
- Compact mode must preserve the same document mutations and Actions as the
  expanded UI. Density changes are presentation-only.
