# Painter UI Figma 다중 출처 기능·배치 조사

Status: 2026-07-31 UX 조사 및 배치 계약

Scope: Tiger Studio Painter의 `UI 디자인` 모드

Companion:
[PAINTER_UI_FIGMA_UI3_COMPLETE_AUDIT_KO.md](PAINTER_UI_FIGMA_UI3_COMPLETE_AUDIT_KO.md)

## 1. 목적과 결론

이 문서는 Figma의 외형을 복제하기 위한 문서가 아니다. Figma 공식 문서,
공개 편집기 구현, 사용자 그룹과 튜터리얼을 교차 조사해 Tiger Studio의
기능 연결과 배치를 결정한다.

핵심 결론:

> Figma UI3는 모든 기능을 항상 보여 주는 3열 편집기가 아니다.
> 캔버스를 중심에 두고 현재 모드, 도구, 선택 종류에 따라 Navigation,
> Toolbar, Properties의 내용과 노출을 바꾸는 편집기다.

Tiger Studio도 이 원칙을 따르되 UI3에서 반복 지적되는 속성 위치 이동,
과도한 숨김, 작은 클릭 영역은 개선해야 한다.

## 2. 조사 기준

| 등급 | 출처 | 사용 방식 |
|---|---|---|
| A | Figma Help Center와 공식 제품 문서 | 기능 존재, 명칭, 현재 진입점의 기준 |
| B | 공식 GitHub와 공개 편집기 소스 | 캔버스·입력·성능 구현의 근거 |
| C | Figma Forum, 여러 사용자 글, 반복 튜토리얼 | 작업 순서와 발견성 문제의 보조 근거 |
| D | 단일 게시물 또는 구형 영상 | 일반화하지 않고 참고만 함 |

UI2는 상단 중앙에 긴 도구막대가 있는 경우가 많고 UI3는 하단 중앙
floating toolbar와 선택 기반 Properties가 핵심이다. 새 Navigation Bar는
계정별로 순차 배포될 수 있어 같은 UI3도 화면 차이가 날 수 있다.

## 3. UI3 전역 셸

| 영역 | 기본 상태 | 표시 조건과 연결 | Tiger Studio 계약 |
|---|---|---|---|
| 왼쪽 Navigation | `File/Layers`, `Assets` | 페이지, 계층, 컴포넌트 탐색 | `Pages/Layers/Assets` 중 한 탭 |
| 중앙 Canvas | 항상 최우선 | artboard, 선택, 변형, 연결선 | 가장 넓은 영역 보장 |
| 하단 Toolbar | 작고 floating | Move, Frame, Shape, Pen, Text, Hand, Actions | 상단/하단 위치 선택 가능 |
| 오른쪽 Properties | 선택 기반 | Design/Prototype, 선택별 섹션 | 핵심 필드 위치 고정 |
| 상단 | 전역 명령 | File/Edit/View, Preview, mode | 객체 속성 중복 금지 |
| Dev Mode | 별도 mode | inspect, code, ready-for-dev | 상시 Inspector 탭 금지 |
| Minimize UI | 사용자 명령 | 좌우 패널과 도구 접기 | 선택 시 Properties 임시 복귀 |

### 3.1 폭에 따른 레이아웃

| 가용 폭 | Navigation | Properties | Toolbar |
|---|---|---|---|
| 넓음 | resize 가능한 dock | resize 가능한 dock | floating |
| 중간 | compact/auto-hide | 선택 시 overlay | 축약 floating |
| 좁음/원격 | overlay drawer | overlay drawer | 한 줄/group popover |

Collapse, Auto-hide, Floating 상태와 사용자가 조절한 폭은 문서가 아니라
사용자 환경에 영속화한다.

## 4. 기능별 진입점과 배치

### 4.1 탐색과 보기

| 기능 | 진입점 | 캔버스 동작 | 배치 |
|---|---|---|---|
| Select/Move | Toolbar `V` | 클릭, 영역 선택, deep select | 기본 Toolbar |
| Hand/Pan | Hand `H`, `Space+Drag` | 캔버스 이동 | Move group + 임시 입력 |
| Zoom | View/zoom, `Z`, 휠 | 커서 중심 확대/축소 | 오른쪽 상단 zoom menu |
| Fit | Zoom/View | 전체/선택 맞춤 | Zoom popover |
| Rulers | View | 캔버스 좌표에 고정 | View menu |
| Guides | ruler drag | 이동, 삭제, lock | Canvas overlay |
| Minimize UI | View | 캔버스 최대화 | View + 단축키 |

팬은 Hand 도구와 `Space+Drag`를 모두 제공하고 활성 시 손바닥 커서를
사용한다.

### 4.2 문서 구조

| 기능 | 진입점 | 선택 시 표시 | 배치 |
|---|---|---|---|
| Page | 왼쪽 | 현재 page와 artboard | Pages |
| Frame | Region `F` | Layout, Position, Clip, Grid | Toolbar + Properties |
| Section | Region popover | 이름과 상태 | Region popover |
| Group | 다중 선택 | 공통 transform | 우클릭/Actions |
| Slice | Region/Export | export 영역 | 저빈도 popover |
| Layer tree | Layers | hide, lock, rename, parent | Layers |
| Reparent/order | tree/canvas drag | 삽입 위치 feedback | Layers + Canvas |

Frame, Section, Slice를 상시 버튼으로 나열하지 않는다. `Region` 그룹에서
선택하고 마지막 사용 도구를 대표 아이콘으로 유지한다.

### 4.3 제작 도구

| 기능군 | 기본 진입 | 하위 항목 | 속성 위치 |
|---|---|---|---|
| Shape | Shape popover | Rectangle, Ellipse, Line, Arrow, Polygon, Star | Appearance |
| Pen/Vector | Pen | node, segment, join, cap | Vector/Stroke |
| Text | Text `T` | point/area text | Typography |
| Image | Place image/Actions | fit, fill, crop, tile | Fill/Image |
| Boolean | 다중 vector 선택 | union, subtract, intersect, exclude | selection header/More |
| Mask | 다중 선택 | use/release/edit | selection action/우클릭 |
| Effects | 객체 선택 | shadow, inner shadow, blur | Appearance |
| Opacity/Blend | 객체 선택 | opacity, blend mode | Appearance |
| Export | 객체/frame 선택 | format, scale, suffix | Properties 하단 |

Boolean과 Mask는 적용 가능한 선택에서만 나타나야 한다.

### 4.4 선택과 변형

| 선택 상태 | Canvas | Properties |
|---|---|---|
| 없음 | artboard와 guide | 문서/artboard 설정 |
| 단일 객체 | bounds, handles, pivot | X/Y/W/H, rotation, appearance |
| 다중 선택 | union bounds, spacing | align, distribute, tidy |
| vector edit | nodes, handles, path | vector와 stroke |
| instance | instance badge | property, variant, swap, override |
| Auto Layout | padding/gap handles | direction, wrap, padding, gap |
| Prototype | node와 connection | trigger, action, transition |

X/Y/W/H와 Position/Layout은 선택 종류가 바뀌어도 오른쪽 상단의 고정
위치를 유지한다.

### 4.5 Auto Layout와 반응형

| 기능 | 진입점 | Canvas | Properties |
|---|---|---|---|
| 생성 | `Shift+A`, 우클릭, Layout | container 변환 | flow |
| Direction | Layout | flow preview | horizontal/vertical/grid |
| Gap | Layout | gap handle | numeric/auto |
| Padding | Layout | edge handles | linked/individual |
| Alignment | Layout | alignment preview | 3x3 control |
| Wrap | Layout | resize feedback | toggle |
| Sizing | child/container | resize 결과 | Hug/Fill/Fixed |
| Min/Max | 고급 sizing | 경계 feedback | 고급 펼침 |
| Absolute | child | flow 제외 badge | Position |
| Constraints | Frame child | resize 결과 | Position |
| Layout Grid | Frame | overlay | Grid/Column/Row |

`Hug/Fill/Fixed`, X/Y/W/H, Clip content는 깊은 메뉴에 숨기지 않는다.
min/max 같은 저빈도 값만 고급 펼침에 둔다.

### 4.6 컴포넌트와 디자인 시스템

| 기능 | 진입점 | 표시 위치 | 원칙 |
|---|---|---|---|
| Component | selection action | 선택 header | 적용 가능할 때만 |
| Instance | Assets drag | Canvas | 검색/category |
| Variant | component/set | Component Properties | State/Size/Type 분리 |
| Component property | main component | Properties | Boolean/Text/Swap/Slot |
| Instance override | instance | Properties 상단 | 계층 탐색 불필요 |
| Style | 값 옆 picker | Fill/Text/Effect/Grid | 값과 token 연결 구분 |
| Variable | binding picker | 속성 | stable ID 연결 |
| Collection/Mode | manager | 별도 manager | Light/Dark/HC/device |
| Library | Assets | 검색/update | 오른쪽 상시 탭 금지 |

실제 작업은 primitive variable을 semantic alias로 연결하고 mode를 적용한
뒤 객체 속성에 binding하는 순서다.

### 4.7 Prototype

| 기능 | 진입점 | Canvas | 오른쪽 |
|---|---|---|---|
| 연결 | Prototype mode | node를 frame으로 drag | interaction |
| Trigger | interaction | source | click, hover, press, drag, key, delay |
| Action | interaction | target | navigate, back, overlay, scroll, URL, variable |
| Transition | connection | preview | instant, dissolve, move, smart |
| Overlay | action | 위치 | close/background/position |
| Scroll | Frame | bounds | overflow/fixed/sticky |
| Preview | Preview | 실제 입력 | device/presentation |

Prototype은 Design Inspector에 섞지 않는다. 연결선과 node는 Canvas
overlay로 그리고 세부 설정만 오른쪽에 표시한다.

### 4.8 Dev, 전달, Export

| 기능 | mode | 왼쪽 | 오른쪽 |
|---|---|---|---|
| Inspect | Dev | ready-for-dev | layout, spacing, color, type |
| Code | Dev | target | Web/App/UMG 결과 |
| Variable trace | Dev | token 검색 | alias/mode/resource ID |
| Component playground | Dev | component | property/mode 조합 |
| Compare changes | Dev | revision | diff |
| Export | Design/Dev | asset | PNG/WebP/SVG, scale, suffix |
| Preflight | Deliver | target/filter | Native/Effect/Material/Baked/Blocked |

Web UI, 일반 App UI, Unreal UMG 결과를 분리하고 지원하지 않는 기능은
조용히 누락하지 않는다.

## 5. 인접 제품과 Painter 경계

| Figma 기능/제품 | 관계 | Tiger Studio 처리 |
|---|---|---|
| Figma Draw | Design 안 별도 mode | 기존 Paint/Draw mode로 분리 |
| Figma AI | Design Actions | AI Action, 적용 전 diff/preview |
| Figma Make | 별도 prompt-to-app | UI document 생성 Action의 장기 범위 |
| Figma Sites | 별도 web publishing | Web delivery 장기 범위 |
| Figma Slides | 별도 presentation | PPT Maker와 연결 |
| Figma Buzz | brand/template | Template/Brand asset 장기 범위 |
| FigJam | whiteboard | 현재 범위 제외 |
| Collaboration | 제품 횡단 | 사용자 요청에 따라 milestone 제외 |
| Plugin marketplace | 확장 생태계 | 현재 범위 제외 |

모든 제품을 UI Design Toolbar에 넣지 않는다. 직접 필요한 것은 Draw mode,
AI Actions, Web/App/UMG delivery 진입점이다.

## 6. 실제 사용자 여정

### 6.1 초보자

1. Frame preset을 선택한다.
2. Shape, Text, Image로 첫 화면을 만든다.
3. Layers에서 이름과 부모를 확인한다.
4. 작은 버튼에 Auto Layout을 적용한다.
5. Component와 Instance를 만든다.
6. Frame을 Prototype으로 연결한다.
7. Preview에서 클릭과 스크롤을 확인한다.

### 6.2 실무 디자이너

1. Page와 Section으로 범위를 나눈다.
2. Assets에서 library component를 배치한다.
3. nested Auto Layout과 Hug/Fill/Fixed로 반응형 구조를 만든다.
4. semantic token과 theme mode를 연결한다.
5. Component state와 override를 정의한다.
6. Desktop/Mobile artboard를 resize하며 검증한다.
7. Prototype과 Motion clip을 연결한다.
8. Dev/Deliver에서 대상별 preflight를 확인한다.

## 7. 반복 사용자 문제

| 반복 문제 | Tiger Studio 방지 규칙 |
|---|---|
| 하단 Toolbar가 Canvas를 가림 | 상단/하단 선택, compact/auto-collapse |
| 핵심 값이 하위 메뉴에 숨음 | Position, Size, Sizing, Clip 고정 노출 |
| 선택에 따라 필드 위치가 이동 | 섹션 순서와 anchor 고정 |
| 패널이 Canvas를 과도하게 점유 | resize/collapse/auto-hide/floating |
| Assets 계층 문맥이 약함 | category tree와 current page 유지 |
| 튜토리얼과 실제 UI 위치가 다름 | Command Search에 현재 위치 표시 |
| 작은 disabled icon이 많음 | 적용 가능한 action만 노출 |

단일 게시물의 취향은 제품 원칙으로 일반화하지 않는다.

## 8. 공개 구현에서 가져올 구조

| 프로젝트 | 가져올 것 | 가져오지 않을 것 |
|---|---|---|
| Penpot | Pages/Layers/Assets, contextual Properties, layout handle | 기능 복제 |
| Lunacy | left tools, context toolbar, UI scale | stock asset 상시 노출 |
| tldraw | state machine, overlay, snap/spatial manager | 얕은 whiteboard inspector |
| Excalidraw | command palette, 필요할 때 여는 island | 정밀 계층 없는 구조 |
| Polotno | panel slot, selection tooltip | 고정 page timeline |
| Konva | Transformer, snapping, drag layer | demo UI |
| Fabric.js | scene/viewport 좌표 분리 | 이벤트의 문서 직접 변경 |
| draw.io | Classic/Compact/Focus preset | 거대한 shape panel |

## 9. 캔버스 구현 계약

1. 정적 document content와 interaction overlay를 분리한다.
2. bounds, handles, guides, distance, Auto Layout handle, Prototype
   connection은 하나의 overlay 계층에서 관리한다.
3. drag 중에는 선택 객체와 overlay의 dirty region만 갱신한다.
4. scene 좌표와 viewport 좌표를 API에서 구분한다.
5. pointer 입력은 tool state machine으로 통합한다.
6. 화면 밖 object는 spatial index로 culling한다.
7. 한 동작은 하나의 mutation batch와 undo step이 된다.
8. GPU와 fallback 경로의 기능 차이를 숨기지 않는다.

## 10. 최종 노출 등급

| 등급 | 기능 |
|---|---|
| 상시 | Select, Region, Shape, Pen, Text, Hand, Actions, zoom |
| 선택 시 | X/Y/W/H, rotation, Fill/Stroke, Typography, Layout |
| Canvas | transform, spacing, guides, prototype node |
| Popover | shape subtype, color, swap, variable, zoom/view |
| 우클릭/Actions | boolean, mask, select similar, rename, outline, export |
| 별도 mode | Prototype, Motion, Dev/Deliver, Paint/Draw, 3D Place |
| 제외 | Collaboration, marketplace runtime, FigJam 복제 |

## 11. 목표 레이아웃

```text
+--------------------------------------------------------------------+
| File  Edit  View       Document / Page              Preview  Dev   |
+----------+---------------------------------------------+-----------+
| Pages    |                                             | Design    |
| Layers   |              Infinite Canvas                | Prototype |
| Assets   |                                             |           |
|          |        Artboard / Section / Overlay         | Contextual|
| resize   |                                             | resize    |
+----------+------------------+--------------------------+-----------+
|                         floating toolbar                           |
+--------------------------------------------------------------------+
```

좁은 화면에서는 양쪽을 drawer로 전환하고 Toolbar는 한 줄을 넘기지 않는다.

## 12. 구현 우선순위

### P0: 셸과 노출

1. Toolbar를 핵심 도구만 남기고 위치 선택을 지원한다.
2. Navigation/Properties의 resize, collapse, auto-hide, floating을 통일한다.
3. 폭에 따라 dock를 drawer로 바꾼다.
4. 선택 종류별 Properties section registry를 만든다.
5. X/Y/W/H와 Layout/Position의 고정 위치를 보장한다.

### P1: 직접 조작

1. Hand, `Space+Drag`, 커서 중심 zoom을 완성한다.
2. rulers/guides, snapping, distance를 overlay로 통합한다.
3. selection, transform, smart selection을 같은 좌표 계약으로 묶는다.
4. Auto Layout padding/gap을 Canvas에서 조절한다.
5. Command Palette와 contextual menu를 연결한다.

### P2: 시스템과 Prototype

1. Assets의 component/library/variable 계층을 정리한다.
2. instance override를 Properties 상단에 배치한다.
3. variable collection/mode/alias manager를 제공한다.
4. Prototype connection과 detail panel을 연결한다.
5. Preview에서 pointer, keyboard, scroll, overlay를 검증한다.

### P3: 성능과 workspace

1. static/interactive/new-object render 계층을 분리한다.
2. spatial index, culling, dirty region, drag layer를 적용한다.
3. Classic/Compact/Focus preset을 제공한다.
4. 사용자별 dock 상태를 영속화한다.

### P4: Dev와 전달

1. Design/Dev mode 전환을 명확히 한다.
2. ready-for-dev, inspect, code, token trace를 연결한다.
3. Web/App/UMG 판정과 blocker를 표시한다.
4. target capture와 revision diff를 검증한다.

## 13. 완료 조건

1. 관련 없는 Inspector 탭을 순회하지 않고 기능을 찾는다.
2. 선택하지 않은 객체 기능은 보이지 않는다.
3. Position/Layout 필드는 선택이 바뀌어도 같은 위치다.
4. 패널을 줄이거나 분리해도 Canvas 상태가 보존된다.
5. 좁은 화면에서 dock가 Canvas를 밀어내지 않는다.
6. Hand, zoom, ruler, guide가 표준 입력으로 동작한다.
7. Auto Layout과 Prototype을 Canvas에서 직접 조절한다.
8. Command Search가 현재 위치와 단축키를 알려 준다.
9. 한국어와 영어에서 control이 겹치지 않는다.
10. desktop, compact, remote screenshot QA를 통과한다.

## 14. 주요 출처

### Figma 공식

- [Navigating UI3](https://help.figma.com/hc/en-us/articles/23954856027159-Navigating-UI3)
- [Design toolbar](https://help.figma.com/hc/en-us/articles/360041064174-Access-design-tools-from-the-toolbar)
- [Explore design files](https://help.figma.com/hc/en-us/articles/15297425105303-Explore-design-files)
- [Auto Layout](https://help.figma.com/hc/en-us/articles/360040451373-Explore-auto-layout-properties)
- [Variants](https://help.figma.com/hc/en-us/articles/360056440594-Create-and-use-variants)
- [Variables](https://help.figma.com/hc/en-us/articles/15339657135383-Guide-to-variables-in-Figma)
- [Prototype](https://help.figma.com/hc/en-us/articles/360040315773-Create-interactions)
- [Dev Mode](https://help.figma.com/hc/en-us/articles/15023124644247-Guide-to-Dev-Mode)
- [Figma Draw](https://help.figma.com/hc/en-us/articles/31440394517143-Explore-Figma-Draw)
- [Figma AI](https://help.figma.com/hc/en-us/articles/23870272542231-Use-AI-tools-in-Figma-Design)
- [Figma Make](https://help.figma.com/hc/en-us/articles/31304412302231-Explore-Figma-Make)
- [Figma Sites](https://help.figma.com/hc/en-us/articles/31230436657815-Explore-Figma-Sites)
- [Figma Slides](https://help.figma.com/hc/en-us/articles/24170630629911-Explore-Figma-Slides)

### 공개 구현

- [Penpot interface](https://help.penpot.app/user-guide/first-steps/the-interface/)
- [Penpot workspace source](https://github.com/penpot/penpot/tree/develop/frontend/src/app/main/ui/workspace)
- [Lunacy interface](https://lunacy.docs.icons8.com/interface/)
- [tldraw UI](https://tldraw.dev/docs/user-interface)
- [tldraw source](https://github.com/tldraw/tldraw)
- [Excalidraw components](https://github.com/excalidraw/excalidraw/tree/master/packages/excalidraw/components)
- [Polotno workspace](https://polotno.com/docs/workspace)
- [Konva transform](https://konvajs.org/docs/select_and_transform/Basic_demo.html)
- [Fabric.js events](https://fabricjs.com/docs/events/)
- [draw.io panels](https://www.drawio.com/docs/manual/editor/panels/)
- [Figma Code Connect](https://github.com/figma/code-connect)
- [Figma SDS](https://github.com/figma/sds)

### 사용자와 튜터리얼

- [Figma Design for beginners](https://help.figma.com/hc/en-us/articles/30848209492887-Course-overview-Figma-Design-for-beginners-2025)
- [Auto Layout fundamentals](https://help.figma.com/hc/en-us/articles/31351261703063-FD4B-Auto-layout-fundamentals)
- [UI3 efficiency feedback](https://forum.figma.com/share-your-feedback-26/ui3-ruins-efficiency-spoken-from-a-long-time-user-39446)
- [Position field feedback](https://forum.figma.com/ask-the-community-7/ui3-any-way-to-prevent-position-sizing-attribute-fields-from-changing-position-based-on-selection-22649)
- [Panel minimization feedback](https://forum.figma.com/suggest-a-feature-11/ui3-autonomously-minimize-toolbar-properties-panel-25953)
- [Left navigation feedback](https://forum.figma.com/share-your-feedback-26/left-hand-navigation-ui3-is-terrible-40978)

## 15. 문서 사용 규칙

- 공식 사실과 사용자 의견을 같은 수준으로 쓰지 않는다.
- UI2 튜토리얼의 위치를 현재 UI3 계약으로 복사하지 않는다.
- 새 기능은 `상시/선택/Canvas/Popover/Actions/별도 mode` 중 하나에
  반드시 배정한다.
- 새 상시 Inspector 탭보다 contextual section이나 별도 mode를 우선한다.
- 지원하지 않는 delivery 기능은 조용히 생략하지 않는다.
