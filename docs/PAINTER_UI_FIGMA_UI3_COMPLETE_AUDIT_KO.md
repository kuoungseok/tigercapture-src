# Painter UI와 Figma UI3 전체 UX 감사

Status: 2026-07-31 기준 UX 기준 문서  
Scope: Tiger Studio Painter의 `UI 디자인` 모드  
Reference: Figma Design UI3의 공식 Help Center와 현재 Tiger Studio 소스  
Non-goal: Figma의 브랜드, 색상, 아이콘을 복제하거나 협업 서비스를 구현하는 것

> 공식 문서, 공개 구현, 사용자 그룹과 튜터리얼을 교차 조사한 기능별
> 진입점·표시 조건·배치 계약은
> [PAINTER_UI_FIGMA_MULTISOURCE_LAYOUT_RESEARCH_KO.md](PAINTER_UI_FIGMA_MULTISOURCE_LAYOUT_RESEARCH_KO.md)를
> 함께 따른다.

## 1. 결론

Tiger Studio Painter UI는 기능 기반이 빈약한 상태가 아니다.

- UI 문서 모델은 `tigerstudio.painter.ui.v1`, version `22`다.
- `paint.ui.*` Action은 현재 `267`개이며, Action family 감사 기준
  `15/15`가 covered다.
- `test_painter_ui_*.py`에는 현재 `486`개의 테스트 함수가 있다.
- 내장 템플릿은 `12`개다.
- Frames, objects, Auto Layout, components, variants, variables, prototype,
  Motion 연결, Figma exchange, Web/PPT/UMG delivery 계약이 존재한다.

그러나 현재 UI는 Figma UI3의 실제 사용 경험과 다르다.

가장 큰 차이는 기능 수가 아니라 **정보 구조와 노출 시점**이다.

1. Figma는 캔버스를 우선하고 기능을 선택 문맥에 따라 늦게 노출한다.
2. Tiger Studio는 구현된 기능을 여러 탭과 버튼에 먼저 노출한다.
3. Figma의 오른쪽 패널은 `Design / Prototype` 두 문맥이 중심이다.
4. Tiger Studio의 오른쪽 패널은 Design, Prototype, Inspect, Motion,
   Publish, Libraries 등 서로 다른 작업 단계를 한곳에 겹쳐 놓는다.
5. Figma의 하단 툴바는 객체 생성과 탐색에 집중한다.
6. Tiger Studio의 하단 툴바는 Motion, 패널 토글, Snap, Guide, Zoom까지
   함께 보여 도구의 우선순위가 흐려진다.
7. Figma의 Templates/Assets는 필요할 때 탐색한다.
8. Tiger Studio의 템플릿 스트립은 캔버스 공간을 상시 소비한다.

따라서 다음 단계는 기능 추가가 아니라 **UI3식 점진 노출과 작업 공간
재구성**이어야 한다.

## 2. 조사 기준

### 2.1 Figma 버전 기준

Figma는 UI3와 새 Navigation Bar를 순차 배포하고 있다. 계정, 배포 시점,
튜토리얼 제작 시기에 따라 다음 화면이 섞여 보일 수 있다.

- UI2: 상단 중심 툴바와 이전 패널 구조
- 초기 UI3: 하단 툴바, 왼쪽 Navigation, 오른쪽 Properties
- 새 Navigation Bar 배포판: File/Assets/Variables/Find 진입점 재배치

이 문서는 2026-07-31에 확인 가능한 공식 UI3 설명을 기준으로 한다.
튜토리얼의 픽셀 배치를 그대로 복제하지 않고, 여러 버전에서 유지되는
핵심 UX 원칙을 기준으로 삼는다.

### 2.2 완료 판정 기준

이 감사에서는 Action이나 JSON 필드가 존재하는 것만으로 UI 기능이
완료됐다고 보지 않는다.

| 상태 | 의미 |
|---|---|
| `UX 완료` | 사용자가 자연스럽게 발견하고 캔버스에서 결과를 확인할 수 있다 |
| `부분 UX` | UI가 있지만 위치, 문맥, 피드백 또는 조작성에 문제가 있다 |
| `계약 완료` | 문서 모델, 서비스 또는 Action은 있으나 UI가 충분하지 않다 |
| `미구현` | 핵심 데이터 또는 동작이 없다 |
| `의도적 제외` | 협업, 플러그인 시장 등 현재 제품 범위에서 제외했다 |

### 2.3 Tiger Studio 증거 기준

주요 구현 근거:

- `app/painter_ui_document.py`: canonical UI 문서 모델
- `app/painter_ui_workspace.py`: 캔버스, 선택, 변형, ruler/guide, prototype
- `app/painter_ui_toolbar.py`: 하단 floating toolbar
- `app/painter_ui_navigator.py`: Pages/Layers/Assets
- `app/painter_ui_inspector.py`: Design/Prototype/Inspect 및 리소스 패널
- `app/painter_ui_auto_layout.py`: Auto Layout resolver
- `app/painter_ui_components.py`: component/instance/variant
- `app/painter_ui_variables.py`: variable collection/mode
- `app/painter_ui_figma.py`: REST import와 plugin export
- `app/painter_ui_dev_handoff.py`: Inspect/Dev handoff
- `app/painter_ui_delivery.py`: target delivery disposition
- `app/painter_ui_action_parity.py`: UI/Action family 감사
- `app/drawing.py`: Painter shell과 각 UI surface 연결

## 3. Figma UI3의 전체 화면 구조

Figma Design은 네 개의 상호작용 영역을 중심으로 동작한다.

1. 왼쪽 Navigation panel
2. 중앙 scrollable infinite canvas
3. 하단 floating toolbar
4. 오른쪽 Properties panel

각 영역은 독립된 기능 창이 아니라 선택과 모드에 따라 함께 변한다.

### 3.1 전역 상단 영역

Figma의 상단은 파일 위치, 문서 상태, 공유/프레젠테이션, 모드 전환처럼
전역 작업만 담당한다. 객체 생성 도구를 상단에 반복 배치하지 않는다.

Tiger Studio 목표:

- 유지: File/Edit/View 같은 데스크톱 메뉴, 문서 이름, 저장 상태
- 유지: Preview/Present, Dev/Inspect 전환
- 제거: UI 모드에서 사용할 수 없는 Paint/3D 메뉴
- 제거: 하단 툴바와 중복되는 객체 생성 버튼
- 원칙: 전역 상태와 선택 객체 명령을 같은 줄에 섞지 않는다

현재 판정: `부분 UX`

### 3.2 왼쪽 Navigation

Figma:

- `File`과 `Assets`가 핵심 문맥이다.
- File에서 Pages와 Layers hierarchy를 본다.
- Assets에서 local/library components를 검색하고 드래그한다.
- 패널 폭을 조절할 수 있다.
- Minimize UI로 좌우 패널을 함께 줄일 수 있다.
- 패널을 최소화한 상태에서도 객체 선택 시 오른쪽 Properties가 임시로
  다시 열린다.

Tiger Studio:

- Pages, Layers, Assets의 기반이 있다.
- 검색, page add/remove/rename, layer drag/reparent가 있다.
- 패널은 폭 조절, 접기, floating을 지원한다.
- 기본 폭은 168px로 표시된다.
- 좌우 패널 최소화가 하나의 workspace command로 묶여 있지 않다.
- File/Assets보다 내부 기능 탭의 수가 많아질 가능성이 있다.

목표 구조:

```text
Navigator
├─ File
│  ├─ Pages
│  └─ Layers
└─ Assets
   ├─ Local components
   ├─ Libraries
   ├─ Styles / Variables
   └─ Templates
```

판정: `부분 UX`

### 3.3 중앙 Canvas

Figma:

- 페이지마다 넓은 canvas를 제공한다.
- 여러 top-level frame을 자유롭게 배치한다.
- frame 바깥도 정상적인 작업 공간이다.
- 선택, hover outline, handles, smart guide, spacing handle이 canvas 위에
  직접 나타난다.
- canvas 조작은 패널 조작보다 우선한다.

Tiger Studio:

- 여러 artboard, object selection, resize, rotate, reparent가 있다.
- rulers, guides, smart snapping, Auto Layout canvas controls가 있다.
- prototype connection과 Motion preview overlay가 있다.
- canvas가 템플릿 strip과 넓은 Inspector에 눌릴 수 있다.
- Paint/3D/UI mode의 shell 요소가 일부 공유돼 시각적 잡음이 남는다.

판정: 기능은 `UX 완료`에 가깝지만 shell은 `부분 UX`

### 3.4 오른쪽 Properties

Figma 편집 권한 기준:

- 최상위 문맥은 `Design / Prototype`이다.
- 아무것도 선택하지 않으면 canvas background, local styles/variables,
  page export처럼 문서 수준 속성을 보여준다.
- 객체 선택 시 객체 종류에 맞는 속성만 보여준다.
- 자주 쓰지 않는 기능은 section, More, popup에 숨긴다.
- Properties panel의 폭을 조절할 수 있다.

Tiger Studio:

- 선택별 geometry/style/content 속성 편집 기반이 있다.
- Prototype, Motion, Publish, Dev, Libraries, Tokens 등 많은 기능이
  Inspector 내부 icon tab으로 모여 있다.
- icon-only tab은 의미를 학습하기 어렵고 현재 작업 단계를 흐린다.
- 선택과 무관한 전달/생산 기능이 객체 속성과 같은 위계에 있다.

목표 구조:

```text
Properties
├─ Design
│  ├─ Selection header/actions
│  ├─ Component properties (해당할 때만)
│  ├─ Layout / Auto layout
│  ├─ Position / Constraints
│  ├─ Appearance
│  ├─ Typography 또는 Image
│  ├─ Effects
│  └─ Export
└─ Prototype
   ├─ Interactions
   ├─ Overflow behavior
   ├─ Flow starting point
   └─ Preview
```

다음 항목은 Properties의 상시 탭이 아니어야 한다.

- Templates: Assets 또는 Actions
- Components/Libraries/Tokens: 왼쪽 Assets
- Motion: 선택 객체의 `Animate` 명령과 Motion summary
- Publish: 전역 Deliver command 또는 별도 mode
- Dev: 별도 Dev/Inspect mode
- Figma import/export: File 메뉴

현재 판정: `부분 UX`, 재구성 최우선

### 3.5 하단 Floating Toolbar

Figma UI3 toolbar:

- Move group: Move, Hand, Scale
- Region group: Frame, Section, Slice
- Shape group: Rectangle, Line, Arrow, Ellipse, Polygon, Star, Image
- Creation: Pen, Pencil
- Text
- Comments
- Actions
- Mode 전환

협업을 제외한 Tiger Studio 목표:

```text
[Move ▼] [Frame ▼] [Shape ▼] [Pen ▼] [Text] [Actions]
```

세부 그룹:

- Move: Select/Move, Hand, Scale
- Frame: Frame, Section, Slice/Export Region
- Shape: Rectangle, Line, Arrow, Ellipse, Polygon, Star, Image
- Pen: Pen/Vector, Pencil/Draw
- Actions: 검색, commands, components, templates, AI

Toolbar에서 제거할 항목:

- Navigator toggle
- Inspector toggle
- Motion Actor
- Animate
- Motion Play
- 상시 Snap button
- 상시 Guide button
- 상시 Zoom button

제거된 항목의 위치:

- 패널 토글: View 또는 Minimize UI
- Snap/guide/ruler: View/Zoom menu와 canvas ruler
- Zoom: 오른쪽 상단 zoom/view menu, shortcut, wheel
- Animate: 선택 action 또는 Prototype
- Motion Actor: Insert/Assets

현재 판정: `부분 UX`

## 4. 탐색과 Canvas 조작

| 요소 | Figma UX | Tiger Studio 현재 | 판정 | 목표 |
|---|---|---|---|---|
| 기본 도구 | Move가 기본 | Select가 기본 | UX 완료 | 유지 |
| 일시 Pan | Space hold | Hand/Pan과 canvas pan 존재 | 부분 UX | Space hold 우선 |
| Hand tool | Move menu 안 | toolbar에 독립 표시 | 부분 UX | Move group 안으로 |
| Scale tool | Move menu 안 | toolbar에 독립 표시 | 부분 UX | Move group 안으로 |
| Wheel pan | canvas 이동 | 구현 있음 | UX 완료 | trackpad QA |
| Zoom | wheel/modifier, shortcut, zoom menu | wheel, shortcut, popover | 부분 UX | view menu 위치 정리 |
| Zoom to fit | 기본 진입과 menu | fit all/artboard/selection | UX 완료 | 명칭 통일 |
| Zoom 범위 | tab 단위 상태 | 3-800% | UX 완료 | 문서별 view state 유지 |
| Rulers | View에서 켜고 canvas edge에 표시 | 구현 있음 | UX 완료 | toolbar 상시 버튼 제거 |
| Guide 생성 | ruler에서 drag | 구현 있음 | UX 완료 | hover/drag feedback 강화 |
| Guide 삭제 | ruler로 되돌리기, Delete, context | 일부 구현 | 부분 UX | 세 방법 모두 제공 |
| Ruler origin | corner에서 조절/reset | 구현 있음 | 부분 UX | origin drag affordance QA |
| Pixel grid | zoom/view options | 일부 grid/snap 존재 | 부분 UX | view option으로 분리 |
| Layout guides | frame 속성 | artboard grid/guide 존재 | 부분 UX | frame selection에만 노출 |
| Smart guides | 이동 중 자동 표시 | 구현 있음 | UX 완료 | 색/거리 label QA |
| Distance measure | Alt hover redline | measurement 기반 존재 | 부분 UX | Alt-hover 직접 UX |
| Hide UI | 전체 chrome 숨김 | 개별 panel 접기 | 계약 미흡 | 하나의 command 추가 |
| Minimize UI | 좌우 panel 축소, 선택 시 우측 임시 | 독립 auto-hide | 부분 UX | 연동 상태기계 필요 |

## 5. 문서, Page, Frame, Section

| 요소 | Figma 의미 | Tiger Studio 현재 | 판정 |
|---|---|---|---|
| Page | 독립 canvas | canonical page 존재 | UX 완료 |
| Page add/delete/rename | 왼쪽 File | 구현 있음 | UX 완료 |
| Page reorder | drag | 계약 일부 | 부분 UX |
| Frame | 명시적 크기의 container | object kind와 artboard 존재 | UX 완료 |
| Top-level frame | 화면/출력 단위 | artboard로 분리 | UX 완료 |
| Nested frame | layout/clip container | frame object 지원 | UX 완료 |
| Group | child bounds를 따르는 묶음 | group 지원 | UX 완료 |
| Frame/Group 차이 | size/layout/clip 의미가 다름 | 모델은 다르나 UI 설명 약함 | 부분 UX |
| Section | canvas 영역 조직/개발 준비 | section model/panel 존재 | 계약 완료 |
| Section tool | Region menu에서 canvas 생성 | toolbar 직접 진입 부족 | 부분 UX |
| Slice | export region | Figma import에서 blocked, asset export 존재 | 미구현 UX |
| Frame preset | device/social presets | artboard presets 존재 | 부분 UX |
| 여러 artboard | 한 canvas 자유 배치 | 구현 있음 | UX 완료 |
| Artboard label | canvas 위 label | 구현 있음 | UX 완료 |

## 6. 생성 도구

| 도구 | Figma | Tiger Studio | 판정 |
|---|---|---|---|
| Rectangle | shape menu | 지원 | UX 완료 |
| Ellipse | shape menu | 지원 | UX 완료 |
| Line | shape menu | 지원 | UX 완료 |
| Arrow | shape menu | 별도 kind 없음 | 미구현 |
| Polygon | shape menu | 지원 | UX 완료 |
| Star | shape menu | 지원 | UX 완료 |
| Arc | ellipse editing/shape | 별도 arc 지원 | UX 완료 |
| Image/video | shape menu의 Place image | image 지원, video는 UI object 아님 | 부분 UX |
| Pen | vector network | editable vector network 지원 | UX 완료 |
| Pencil | freehand vector | Paint 도구는 있으나 UI vector 문맥 통합 약함 | 부분 UX |
| Text | click auto width, drag fixed box | text 지원/inline edit | 부분 UX |
| Button/Progress | Figma에서는 component로 만드는 패턴 | 전용 object kind | Tiger 확장 |
| Motion Actor | Figma 기본 도구 아님 | 지원 | Assets/Insert로 이동 |

## 7. 선택, 변형, 정렬

| 요소 | 현재 판정 | 감사 메모 |
|---|---|---|
| click selection | UX 완료 | canvas와 Layers 동기화 |
| marquee selection | UX 완료 | empty canvas drag 기준 유지 |
| Shift multi-select | UX 완료 | mixed property 상태 확인 필요 |
| deep select | 부분 UX | Ctrl/click, double-click, hierarchy UX 통일 필요 |
| selection breadcrumb | 부분 UX | 필요할 때만 표시 |
| move | UX 완료 | snap/smart guide 연동 |
| resize handles | UX 완료 | modifier 동작 QA 필요 |
| rotate handle | UX 완료 | 각도 label과 snap QA |
| scale | UX 완료 | Move group으로 재배치 |
| aspect lock | 계약 완료 | Inspector와 canvas affordance 동기화 |
| center resize | 부분 UX | Alt modifier 명시 |
| duplicate drag | 부분 UX | Alt-drag UX 검증 |
| align | 계약 완료 | selection action row에 노출 |
| distribute | 계약 완료 | selection action row에 노출 |
| tidy up | smart selection 기반 존재 | canvas handle 발견성 부족 |
| smart selection handles | 구현 있음 | Figma식 spacing/reorder feedback QA |
| group/ungroup | UX 완료 | context menu와 shortcut 유지 |
| reorder Z | UX 완료 | Layers drag와 canvas command 동일 mutation |
| reparent | UX 완료 | canvas/Layers 양쪽 지원 |
| lock/hide | UX 완료 | icon hover 노출과 mixed state 개선 |
| copy/cut/paste | UX 완료 | cross-artboard 좌표 계약 유지 |
| select similar | 계약/대화상자 존재 | context menu 진입 단순화 |
| batch rename | 계약/대화상자 존재 | Layers context에서 진입 |
| find/replace | 계약/대화상자 존재 | Actions가 기본 진입 |

## 8. Appearance와 콘텐츠 속성

### 8.1 공통 Appearance

| 요소 | Tiger Studio | 판정 |
|---|---|---|
| opacity | 지원 | UX 완료 |
| blend mode | 지원 | 부분 UX |
| multiple fills | 모델 지원 | 부분 UX |
| solid fill | 지원 | UX 완료 |
| gradient fill | 지원 | 부분 UX |
| image fill | 지원 | UX 완료 |
| multiple strokes | 모델 지원 | 부분 UX |
| stroke width | 지원 | UX 완료 |
| individual stroke | 일부 계약 | 부분 UX |
| stroke align | 지원 | 부분 UX |
| corner radius | 지원 | UX 완료 |
| independent corners | 지원 | 부분 UX |
| drop shadow | 지원 | UX 완료 |
| inner shadow | 지원 | 부분 UX |
| layer blur | 지원 | 부분 UX |
| background blur | 지원 | 부분 UX |
| noise/texture | Painter/Tiger 확장 | target별 delivery 판정 필요 |
| mask | non-destructive model/UX 존재 | 부분 UX |
| boolean operations | non-destructive group 존재 | UX 완료 |

문제:

- advanced appearance가 별도 dialog에 모이면 Figma식 빠른 반복 편집이 깨진다.
- 기본 속성은 오른쪽 section 안에서 직접 편집해야 한다.
- 다중 fill/stroke처럼 복잡한 값만 상세 popup을 사용해야 한다.
- unsupported target은 숨기지 말고 Native/Material/Baked/Blocked를 표시한다.

### 8.2 Typography

지원 또는 계약이 있는 항목:

- text content
- font family
- size
- weight
- alignment
- line height
- letter spacing
- variable font axes
- text ranges
- inline editing

부족한 UX:

- click text와 fixed text box의 생성 차이가 명확하지 않다.
- mixed text range selection의 canvas editing이 충분히 검증되지 않았다.
- paragraph spacing, indent, list 등 편집 UX가 Figma 수준이 아니다.
- font missing/replacement workflow가 Properties 안에서 자연스럽지 않다.

판정: `부분 UX`

### 8.3 Image

지원:

- image object
- Fit/Fill/Stretch/Tile
- focal point editing
- resource/path metadata
- export와 hash 계약

부족:

- crop mode의 직접 조작
- image/video place 흐름 통합
- replace image와 restore crop의 빠른 action
- missing image recovery UX

판정: `부분 UX`

## 9. Auto Layout와 반응형

Figma Auto Layout 핵심:

- Vertical, Horizontal, Grid
- Padding
- Gap
- Alignment
- Wrap
- Hug contents
- Fill container
- Fixed
- Min/Max size
- nested Auto Layout
- absolute positioning
- canvas spacing handles

Tiger Studio 현재:

- Horizontal/Vertical/Grid resolver
- padding/gap/alignment/wrap
- Hug/Fill/Fixed
- min/max
- nested layout
- positioning
- canvas Auto Layout controls
- breakpoint/orientation overrides
- theme preview

판정:

- 문서 계약과 resolver: `계약 완료`
- 오른쪽 Inspector: `부분 UX`
- canvas direct manipulation: `부분 UX`
- 복잡한 nested layout의 실제 결과: 추가 QA 필요

목표 노출 규칙:

1. 일반 객체에는 `Layout`만 보인다.
2. Frame에서 Add Auto Layout을 누르면 section 이름이 `Auto layout`으로
   바뀐다.
3. child는 parent가 Auto Layout일 때만 Hug/Fill/Absolute를 본다.
4. canvas에는 현재 조절 가능한 padding/gap handle만 나타난다.
5. 불가능한 순환이나 constraint는 즉시 inline warning으로 표시한다.

## 10. Components, Variants, Styles, Variables

### 10.1 Components와 Instances

Tiger Studio 지원:

- selection을 component definition으로 변환
- instance 생성
- definition 수정 후 instance sync
- detach
- nested component metadata
- component property binding
- component playground

판정: backend `계약 완료`, authoring UX `부분 UX`

Figma식 목표:

- component는 selection action 또는 context menu에서 생성
- instance 선택 시 오른쪽 상단에 main component link
- intended override만 Properties 상단에 모아 표시
- instance swap은 Assets picker를 사용
- detach/reset은 More에 둔다

### 10.2 Variants

Tiger Studio 지원:

- component family
- variant 생성과 switch
- state overrides
- Normal/Hover/Pressed/Focused/Disabled/Selected 상태

부족:

- component set를 canvas에서 한눈에 편집하는 UX
- property/value 조합을 표 형태로 관리하는 UX
- 중복 조합 검증의 즉시 feedback

판정: `부분 UX`

### 10.3 Component properties

Figma의 주요 property:

- Boolean
- Text
- Instance swap
- Slot
- Variant

Tiger Studio:

- enum/boolean/text/instance swap 중심
- slot authoring UX는 부족
- Properties에서 instance override를 우선 노출하는 구조가 약함

판정: `부분 UX`

### 10.4 Styles와 Variables

Figma:

- Styles는 여러 값을 묶은 composite source of truth다.
- Variables는 color/number/string/boolean raw value다.
- Collection과 Mode가 있다.
- 같은 type variable끼리 alias할 수 있다.
- mode는 light/dark, locale, desktop/mobile 같은 context를 바꾼다.

Tiger Studio:

- color, typography, spacing, radius, border, shadow, opacity, icon, image token
- variable collection/mode
- token binding
- style library
- import/export

차이:

- token과 variable의 사용자 개념이 섞여 있다.
- 왼쪽 Assets 안에서 Styles/Variables의 관계가 명확히 보여야 한다.
- raw variable와 composite style을 구분해야 한다.
- alias chain과 사용처 탐색 UX가 더 필요하다.

판정: 계약 `완료`, UX `부분`

## 11. Prototype

Figma Prototype 구성:

1. Trigger
2. Action
3. Destination
4. Animation/transition

Canvas에서는 hotspot의 handle을 destination frame으로 drag해 connection을
만든다. 오른쪽 Prototype에서 세부 값을 편집한다.

Tiger Studio trigger:

- click
- double click
- hover
- press
- focus
- keyboard
- delay
- mouse enter/leave
- drag
- gamepad

Tiger Studio action:

- navigate/back
- open/close/swap overlay
- change state/variant
- play animation/sound
- visibility/opacity/material scalar
- scroll to
- set variable/mode
- conditional branch

지원 또는 계약:

- canvas connection
- flow
- inline preview
- overlay
- overflow/scroll 계약
- Smart Animate property matching과 fallback report
- component state transition
- Motion binding

UX 격차:

- Prototype가 오른쪽 최상위 두 탭 중 하나로 단순하게 보이지 않는다.
- Motion binding/delivery가 기본 interaction보다 먼저 시선을 끈다.
- connection detail이 canvas 작업을 가리는 경우가 있다.
- preview/present 진입이 전역 command로 명확하지 않다.
- Smart Animate fallback 이유가 authoring 중 즉시 보이지 않는다.

판정: 기능 계약 `완료`, authoring UX `부분`

## 12. Motion Designer 경계

합의된 소유권:

- Painter: 정적 UI 구조, layout, component state, interaction
- Motion: 시간 변화, keyframe, interpolation, timeline
- Painter object의 resolved layout 뒤에 motion offset을 적용
- canonical binding 하나를 사용
- Motion Actor는 UI animation과 별도 삽입 자산

Figma식 노출:

- 기본 toolbar에서 Motion Actor/Animate/Play를 제거한다.
- 객체 선택 action의 `Animate` 또는 Prototype transition에서 진입한다.
- 오른쪽에는 clip/binding summary와 status만 보여준다.
- timeline/graph는 Motion Designer에서만 보여준다.

현재 판정: 계약은 강하지만 toolbar 노출은 `재배치 필요`

## 13. Templates, Assets, Libraries

Figma의 강점은 많은 Community/library 자산을 검색하고 복제해 시작하는
생산 루프다. Tiger Studio에서 협업과 Marketplace를 제외하더라도 다음은
필요하다.

현재:

- 12개 내장 template
- template catalog/store/package
- component library
- local library package install/update/rollback
- image/icon asset
- search/filter 기반 패널

문제:

- template strip이 상시 캔버스 공간을 차지한다.
- 12개는 “풍부한 템플릿”으로 인식되기 어렵다.
- 템플릿 preview의 시각 품질과 실제 편집 가능성 차이를 표시해야 한다.
- component, template, library, token이 여러 탭에 흩어져 있다.

목표:

- Templates는 왼쪽 Assets 또는 Actions overlay에서 연다.
- 최근 사용, Favorites, Installed, Built-in을 구분한다.
- category와 target(Web/App/UMG/PPT)을 함께 검색한다.
- template 적용 전 preview와 생성될 pages/artboards/components를 표시한다.
- 적용은 새 page, 새 document, selection 삽입을 구분한다.

판정: 계약 `완료`, product UX `부분`

## 14. Dev Mode와 Delivery

Figma Dev Mode:

- Design mode와 분리된 mode다.
- ready-for-dev design 탐색
- selected layer inspect
- layout/spacing/colors/typography/variables/interactions
- CSS/iOS/Android code snippets
- measurements와 annotations
- export
- change comparison

Tiger Studio:

- Inspect/Dev panel
- ready status
- annotations
- revision compare
- component playground
- code/list snippets
- asset export
- Web/PPT/UMG target
- Native/Material/Baked/Blocked preflight

UX 격차:

- Dev가 Properties의 여러 내부 탭 중 하나라 mode 전환 느낌이 약하다.
- Painter 제작용 control과 developer 정보가 한 패널에 섞인다.
- target selector와 code/list 전환이 더 명확해야 한다.
- selected object와 whole document delivery 결과의 위계를 분리해야 한다.

목표:

- 하단 또는 상단의 `Design / Dev` mode switch
- Dev mode에서 편집 도구를 줄이고 측정/inspect/export를 우선
- 왼쪽은 ready frame/section 탐색
- 오른쪽은 selected layer inspect
- 전체 package/preflight는 전역 Deliver command

판정: 계약 `완료`, Dev Mode UX `부분`

## 15. Import와 Export

### 15.1 Figma Import

현재 방식:

- Figma REST API file import
- local Figma JSON fixture import
- geometry paths와 shared plugin data 사용
- pages, top-level frames, nodes, components, variables, reactions 변환

명시적 제한:

- `SLICE`, `CONNECTOR`, `WIDGET`, `EMBED`, `LINK_UNFURL`은 blocked
- geometry가 없는 vector는 blocked warning
- image asset을 찾지 못하면 blocked warning
- 모든 Figma 효과와 plugin node를 보존하는 native `.fig` reader가 아니다

### 15.2 Figma Export

현재 방식:

- editable Figma node를 생성하는 development plugin package
- `manifest.json`, `code.js`, 사용 안내 생성
- native `.fig` 파일 writer가 아니다

호환성:

- frame/group/rectangle/ellipse/line/path/text/image/button/progress는
  editable mapping 대상
- motion actor는 poster-frame bake
- unsupported kind는 blocked
- mask/boolean/text ranges는 native mapping 목표
- variable font axes 등 일부는 shared plugin data로 보존
- Figma plugin은 file comment를 만들 수 없어 review comment는 metadata 보존

판정: `부분 호환`. UI에서 “Figma file export”라고만 표시하면 안 되며
`Figma Plugin Package`라고 정확히 표시해야 한다.

### 15.3 Tiger Studio Target Delivery

대상별 판정은 다음을 유지한다.

- Web: Native / Vector / Platform Effect / Baked / Blocked
- App: Native / Vector / Platform Effect / Baked / Blocked
- Unreal UMG: Native / UI Material / Baked / Actor Only / Blocked

지원되지 않는 기능은 조용히 누락하지 않는다.

## 16. Productivity와 접근성

| 기능 | 현재 | 목표 |
|---|---|---|
| Actions/command search | 있음 | 하단 toolbar의 단일 Actions 진입 |
| shortcut map | 있음 | hover tooltip과 shortcut panel 동기화 |
| context menu | 있음 | selection type별 정리 |
| Find/Replace | 있음 | Actions와 Edit 메뉴 |
| Batch rename | 있음 | Layers context |
| Select similar | 있음 | context와 Actions |
| Multi-edit | mutation 기반 존재 | Properties mixed state 개선 |
| property clipboard | 있음 | Copy/Paste properties context |
| Undo/Redo | 있음 | 모든 UI/Action mutation 동일 stack |
| accessibility role/label/order | 있음 | Design section과 audit 연결 |
| contrast audit | 있음 | canvas overlay와 fix action 연결 |
| locale audit | 있음 | text overflow preview 연결 |
| performance budget | 있음 | release preflight와 연결 |

## 17. 의도적으로 제외하는 Figma 영역

사용자 결정에 따라 다음은 이 마일스톤에서 제외한다.

- real-time multiplayer editing
- multiplayer cursors
- comments collaboration service
- voice chat/spotlight
- branching/merging service
- team cloud permissions
- Community marketplace 운영
- third-party plugin/widget runtime

단, local review comment metadata, local library package, AI Action, import/export
contract는 Tiger Studio의 독립 제작 workflow를 위해 유지한다.

## 18. 현재 UI의 구체적인 구조 문제

### P0 문제

1. 오른쪽 Inspector가 `Design / Prototype` 중심이 아니다.
2. Motion, Publish, Dev, Libraries가 object properties와 같은 위계다.
3. 하단 toolbar에 도구가 아닌 panel/motion/view command가 많다.
4. template strip이 canvas를 상시 줄인다.
5. Minimize UI가 좌우 panel을 하나의 command로 제어하지 않는다.
6. 아무것도 선택하지 않은 상태의 Properties가 과도하다.

### P1 문제

1. Region tool에 Section/Slice가 자연스럽게 묶이지 않는다.
2. Hand/Scale이 Move group이 아니라 독립 버튼이다.
3. Arrow와 UI vector pencil 흐름이 부족하다.
4. Auto Layout의 canvas handles가 발견하기 어렵다.
5. Alt-distance, smart selection, direct selection의 feedback이 약하다.
6. Properties의 labels, mixed values, popup hierarchy가 일관적이지 않다.

### P2 문제

1. Components/Variables/Styles가 Assets 중심 workflow로 통합되지 않았다.
2. Prototype detail과 Motion detail이 섞인다.
3. Dev Mode가 제작 mode와 충분히 분리되지 않았다.
4. Template 품질과 양이 product strength로 보이지 않는다.
5. Figma exchange 명칭이 native `.fig` 호환으로 오해될 수 있다.

## 19. 목표 UI 상태 규칙

### 19.1 선택 없음

왼쪽:

- Pages/Layers 또는 Assets

오른쪽 Design:

- Canvas background
- Local variables/styles entry
- Page export

Canvas:

- artboards와 sections
- object-specific controls 없음

### 19.2 Artboard 선택

오른쪽 Design:

- frame preset/name
- X/Y/W/H
- Auto Layout 또는 Layout
- layout guides
- clip content
- background
- variable mode
- prototype flow starting point는 Prototype 탭

### 19.3 일반 Shape 선택

- selection actions
- Layout
- Position
- Appearance
- Fill
- Stroke
- Effects
- Export

### 19.4 Text 선택

- Layout
- Position
- Typography
- Fill/Stroke
- Effects
- Export

### 19.5 Image 선택

- Layout
- Position
- Image fill/crop
- Appearance
- Effects
- Export

### 19.6 Component Definition 선택

- component name/link
- properties
- variants
- Layout
- Appearance
- Export

### 19.7 Component Instance 선택

- main component link
- intended overrides
- variant/property controls
- reset/detach in More
- common Layout/Appearance

### 19.8 다중 선택

- align/distribute/tidy
- common properties
- mixed value 표시
- unsupported combined edits는 disabled 이유 표시

### 19.9 Prototype 탭

- selected hotspot interactions
- trigger/action/destination/transition
- canvas connection handle
- flow preview
- Motion은 transition의 상세 선택일 때만 summary 노출

### 19.10 Dev Mode

- editing toolbar 축소
- ready frames/sections 탐색
- measurements
- selected layer inspect
- code/list
- asset export
- target preflight

## 20. 재설계 실행 순서

### UI3-P0: Shell 정리

1. 오른쪽 최상위 탭을 `Design / Prototype`로 단순화
2. Dev를 별도 mode로 분리
3. Templates/Libraries/Tokens/Components를 왼쪽 Assets로 이동
4. template strip 기본 제거
5. 하단 toolbar를 Move/Region/Shape/Pen/Text/Actions로 축소
6. Motion Actor/Animate/Play를 toolbar에서 제거
7. Minimize UI command로 좌우 panel 연동
8. 선택 없음/선택 있음 Properties 상태 분리

### UI3-P1: Canvas 직접 조작

1. Move menu에 Hand/Scale
2. Region menu에 Frame/Section/Slice
3. Shape menu에 Arrow/Image
4. ruler/guide drag와 삭제 feedback 완성
5. Alt-hover measurement
6. smart selection spacing/reorder handles
7. Auto Layout padding/gap canvas handles
8. mixed selection과 direct select feedback

### UI3-P2: Design System 흐름

1. Assets 검색과 local/library 구분
2. component instance override 우선 Properties
3. component set/variant canvas authoring
4. variables collection/mode/alias UX
5. Styles와 Variables의 역할 구분
6. template preview/apply destination UX

### UI3-P3: Prototype와 Motion

1. canvas noodle와 Prototype detail 단순화
2. flow/overlay/scroll preview
3. Smart Animate fallback inline report
4. selected object `Animate` 진입
5. Motion binding summary만 Painter에 유지

### UI3-P4: Dev와 Delivery

1. Design/Dev mode switch
2. ready-for-dev navigation
3. inspect code/list
4. measurements/annotations
5. target selector
6. Native/Material/Baked/Actor Only/Blocked preflight
7. Figma Plugin Package 명칭 교정

## 21. 완료 조건

다음 조건을 모두 만족해야 “Figma형 UX 완료”라고 말할 수 있다.

1. 1440x900에서 canvas가 주 작업 공간으로 보인다.
2. 390x844 remote viewport에서도 panel이 canvas를 덮지 않는다.
3. 아무것도 선택하지 않으면 object control이 보이지 않는다.
4. 객체 종류에 맞지 않는 property가 보이지 않는다.
5. toolbar에는 현재 작업의 핵심 생성/탐색 도구만 보인다.
6. Templates/Library/Dev/Publish가 Properties의 상시 탭이 아니다.
7. Hand, zoom, rulers, guides가 Figma와 유사한 입력 규칙을 가진다.
8. Auto Layout을 canvas와 Properties 양쪽에서 조절할 수 있다.
9. component instance override가 hierarchy 탐색 없이 보인다.
10. prototype connection을 canvas에서 만들고 오른쪽에서 편집할 수 있다.
11. 모든 UI mutation과 Action이 같은 service와 undo stack을 사용한다.
12. 지원하지 않는 delivery는 명시적으로 Blocked로 보인다.
13. 한국어/영어에서 label과 control이 겹치지 않는다.
14. 실제 desktop/mobile screenshot QA가 통과한다.
15. Action coverage가 아니라 task completion test로 완료를 증명한다.

## 22. 공식 조사 자료

- [Navigating UI3](https://help.figma.com/hc/en-us/articles/23954856027159-Navigating-UI3-Figma-s-new-UI)
- [Access design tools from the toolbar](https://help.figma.com/hc/en-us/articles/360041064174-Access-design-tools-from-the-toolbar)
- [View layers and pages in the navigation panel](https://help.figma.com/hc/en-us/articles/360039831974-View-layers-and-assets-in-the-Layers-Panel)
- [Design and Prototype properties panel](https://help.figma.com/hc/en-us/articles/360039832014-Design-Prototype-and-view-Code-in-the-Properties-Panel)
- [Explore design files](https://help.figma.com/hc/en-us/articles/15297425105303-Explore-design-files)
- [Adjust zoom and view options](https://help.figma.com/hc/en-us/articles/360041065034-Adjust-your-zoom-and-view-options)
- [Add guides to the canvas or frames](https://help.figma.com/hc/en-us/articles/360040449713-Add-guides-to-the-canvas-or-frames)
- [Shape tools](https://help.figma.com/hc/en-us/articles/360040450133-Basic-shape-tools-in-Figma-design)
- [Frames in Figma Design](https://help.figma.com/hc/en-us/articles/360041539473-Frames-in-Figma-Design)
- [Frames and groups](https://help.figma.com/hc/en-us/articles/360039832054-The-difference-between-frames-and-groups)
- [Boolean operations](https://help.figma.com/hc/en-us/articles/360039957534-Boolean-operations)
- [Masks](https://help.figma.com/hc/en-us/articles/360040450253-Masks)
- [Alignment, distribution, and tidy up](https://help.figma.com/hc/en-us/articles/360039956914)
- [Smart selection](https://help.figma.com/hc/en-us/articles/360040450233-Arrange-layers-with-Smart-selection)
- [Guide to Auto Layout](https://help.figma.com/hc/en-us/articles/360040451373-Explore-auto-layout-properties)
- [Grid Auto Layout](https://help.figma.com/hc/en-us/articles/31289469907863-Use-the-grid-auto-layout-flow)
- [Component property fundamentals](https://help.figma.com/hc/en-us/articles/39636407507735-Components-collection-Component-property-fundamentals)
- [Create and use variants](https://help.figma.com/hc/en-us/articles/360056440594-Create-and-use-variants)
- [Variables, collections, and modes](https://help.figma.com/hc/en-us/articles/14506821864087-Overview-of-variables-collections-and-modes)
- [Variables and styles](https://help.figma.com/hc/en-us/articles/15871097384471)
- [Connect a prototype](https://help.figma.com/hc/en-us/articles/360040315773-Create-interactions)
- [Prototype triggers](https://help.figma.com/hc/en-us/articles/360040035834-Prototype-triggers)
- [Prototype actions](https://help.figma.com/hc/en-us/articles/360040035874-Prototype-actions)
- [Prototype scroll and overflow](https://help.figma.com/hc/en-us/articles/360039818734-Prototype-scroll-and-overflow-behavior)
- [Smart Animate](https://help.figma.com/hc/en-us/articles/360039818874-Smart-animate-layers-between-frames)
- [Prototype overlays](https://help.figma.com/hc/en-us/articles/360039818254-Create-Overlays-in-your-Prototypes)
- [Guide to Dev Mode](https://help.figma.com/hc/en-us/articles/15023124644247-Guide-to-Dev-Mode)
- [Guide to inspecting](https://help.figma.com/hc/en-us/articles/22012921621015-Guide-)
- [Export formats and settings](https://help.figma.com/hc/en-us/articles/13402894554519-Export-formats-and-settings)
- [Keyboard navigation](https://help.figma.com/hc/en-us/articles/360040328653-Use-Figma-products-with-a-keyboard)

## 23. 문서 사용 규칙

- 이 문서는 UI3 shell과 노출 규칙의 기준이다.
- 기존 milestone의 “implemented”는 backend/Action 완료일 수 있다.
- 실제 UI 완료 여부는 이 문서의 상태와 완료 조건으로 다시 판정한다.
- Figma의 공식 UI가 변경되면 조사 날짜와 source를 갱신한다.
- Tiger Studio 고유 기능은 Figma toolbar에 억지로 넣지 않고 해당 workflow의
  Assets, Actions, Prototype, Dev, Deliver surface에 배치한다.
