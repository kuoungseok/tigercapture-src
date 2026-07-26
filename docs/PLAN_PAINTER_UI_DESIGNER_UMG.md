# Tiger Studio Painter UI Designer / Unreal UMG Plan

Status: proposed  
Reference implementation: Motion Designer Unreal Link and TigerStudioUMG  
Target engine: `D:\UE_5.8\Engine`

## 1. Product Goal

Painter에 원화 제작과 별개로 `UI Design` 작업 공간을 추가한다. 사용자는
그림, 브러시 텍스처, 벡터 도형, 텍스트를 한 문서에서 조합하고, 게임 UI의
레이아웃과 상태를 설계한 뒤 Unreal Widget Blueprint로 보낼 수 있어야 한다.

이 기능은 Figma 전체를 복제하거나 Painter를 범용 웹 디자인 도구로 바꾸는
작업이 아니다. 목표는 다음 세 영역을 자연스럽게 연결하는 것이다.

1. Painter의 래스터/벡터/Material Paint 자산 제작
2. 게임 UI의 구조, 상태, 제약 조건, 컴포넌트 설계
3. Tiger Studio가 통제하는 Unreal UMG 생성과 재생성

핵심 제품 문장은 다음과 같다.

> Painter에서 보이는 UI를 만들고, Tiger Studio가 편집 가능한 Unreal UMG로
> 생성한다.

## 2. Motion Designer에서 재사용할 기준

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

### 3.1 반드시 공유할 것

- `TigerStudioUMG` runtime/editor 모듈
- Tiger UMG 문서의 schema version
- 리소스 ID, stable source ID, content hash 정책
- 프로젝트 로컬 플러그인 설치와 업데이트
- Unreal 실행, 생성, 컴파일, 저장, 재검증
- 생성 자산의 Tiger 소유 영역과 사용자 소유 영역 분리
- 공개 설치본용 source-free 플러그인 번들

### 3.2 Painter에만 둘 것

- `.tspaint`에서 UI Design 데이터를 읽고 쓰는 provider adapter
- Painter 객체를 Tiger UMG 객체로 분류하는 preflight
- 브러시/레이어 결과를 UI texture로 결정적으로 bake하는 과정
- Painter 캔버스의 UI Design 작업 공간과 도구
- Painter 전용 Action namespace

### 3.3 금지

- `PainterUMG` 같은 별도 Unreal 플러그인 생성
- Motion Designer UMG 코드를 복사한 Painter 전용 workflow 생성
- 지원하지 않는 Painter 효과를 조용히 누락
- `.tspaint` 전체를 PNG 한 장으로만 평탄화하여 UMG라고 표시
- 생성 과정에서 사용자가 만든 Blueprint 그래프를 덮어쓰기

## 4. Primary User Scenarios

### 4.1 게임 HUD 제작

1. Painter에서 `New > UI Document > 1920 x 1080`을 선택한다.
2. Safe Area와 화면 기준선을 표시한다.
3. HP 바, 아이콘, 텍스트, 버튼을 배치한다.
4. 버튼의 Normal/Hover/Pressed/Disabled/Focused 상태를 만든다.
5. `Unreal Link`를 누르고 `.uproject`를 선택한다.
6. preflight 결과를 확인하고 `Generate Widget Blueprint`를 실행한다.
7. Unreal에서 컴파일된 WBP와 가져온 texture/font/material을 연다.

### 4.2 Painter 자산을 사용하는 메뉴 화면

1. Material Paint 또는 일반 레이어에서 배경과 장식 프레임을 그린다.
2. 장식 레이어를 `UI Texture`로 지정하고 9-slice 여백을 설정한다.
3. 텍스트와 버튼은 네이티브 UI 객체로 유지한다.
4. preflight는 장식을 deterministic bake, 텍스트/버튼을 native로 표시한다.
5. 생성된 WBP는 해상도 변경 시 텍스트와 버튼을 다시 배치하며, 장식 texture는
   9-slice 규칙으로 늘어난다.

### 4.3 AI에게 UI 생성 지시

사용자는 다음처럼 요청할 수 있어야 한다.

> 16:9 액션 게임 HUD를 만들고 왼쪽 아래에 체력과 스태미나, 오른쪽 위에
> 미니맵, 중앙 아래에 아이템 슬롯을 배치해. Unreal UMG로 생성하기 전
> 변경 목록과 preflight를 보여줘.

AI는 등록된 `paint.ui.*`와 `paint.umg.*` Action만 사용한다. 결과를 즉시
Unreal에 쓰지 않고, 먼저 문서 변경과 UMG 변환 계획을 보여준 뒤 사용자가
승인한 범위만 적용한다.

### 4.4 재생성

1. Unreal에서 생성 WBP 바깥의 사용자 소유 로직을 추가한다.
2. Painter에서 색, 크기, 배치, 상태를 수정한다.
3. `Regenerate`를 실행한다.
4. stable source ID가 같은 위젯과 animation binding은 갱신한다.
5. 제거된 Tiger 객체만 생성 영역에서 정리한다.
6. 사용자 소유 그래프와 수동 추가 위젯은 보존한다.

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
- `Inspect`: geometry, constraints, accessibility, UMG disposition

기존 `Layers | Channels | Paths`는 Painter 작업의 핵심이므로 없애지 않는다.
UI Design 패널은 같은 dock system에서 탭 그룹으로 전환하며 중첩되거나
캔버스를 과도하게 침범하지 않아야 한다.

### 5.5 Unreal Link

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
- 하나의 artboard를 UMG root Widget Blueprint로 생성
- 여러 artboard는 각각 생성하거나 component library로 묶을 수 있음

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

token은 이름과 stable ID를 갖는다. UMG에서 직접 표현 가능한 값은 native로,
런타임 변경이 필요한 값은 generated data/material parameter로 연결한다.

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
    "export_profiles": [],
    "unreal_link": {
      "destination_root": "/Game/TigerStudio/Generated",
      "last_generated_revision": 0
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

## 8. Tiger UMG Document Contract

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

## 9. Conversion Matrix

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

## 10. Preflight

Generate 전에 객체별 판정을 보여준다.

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

경고 예:

- 작은 터치 target
- 낮은 text contrast
- 번역 문자열 overflow
- 지나치게 큰 texture memory
- Material Paint parallax를 정적 texture로 bake

## 11. Action / AI Contract

### 11.1 UI authoring

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

### 11.2 Unreal delivery

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

## 12. Accessibility and Design QA

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

QA는 캔버스 preview만 보지 않는다. 생성된 Widget Blueprint를 실제 Unreal
viewport에서 열고 capture하여 비교한다.

## 13. Performance and Rendering

- UI 객체는 retained scene으로 유지하고 매 frame 전체 문서를 다시 rasterize
  하지 않는다.
- Painter layer texture는 dirty region만 갱신한다.
- 반복 component asset은 texture atlas 후보로 분석한다.
- high zoom은 canvas texture display와 viewport overlay를 분리한다.
- remote session에서는 OpenGL 실패 시 기존 CPU fallback을 유지한다.
- preflight는 예상 texture memory, draw count, material count를 보고한다.
- Material Paint의 normal/height는 요청한 UI Material profile에서만
  패키징하며 기본 HUD를 불필요하게 무겁게 만들지 않는다.

## 14. Implementation Phases

### Phase 0: Contract and document foundation

- `.tspaint` `ui_document` schema
- artboard and primitive object model
- stable IDs, undo/redo, save/load round trip
- provider-neutral Tiger UMG contract extension proposal
- native/material/baked/blocked classifier

Exit:

- UI document save-load-save가 canonical하게 일치
- unsupported feature가 silent omission 없이 분류됨

### Phase 1: Painter UI Design workspace

- `Paint | UI Design | 3D Place`
- Frame, Shape, Text, Image, Button
- Layers integration
- geometry, anchors, constraints
- auto layout basics
- 9-slice
- component states

Exit:

- 16:9 HUD를 마우스와 Action 양쪽으로 제작
- 창 크기 변경과 원격 환경에서 패널 중첩 없음

### Phase 2: Shared Unreal Link

- Painter provider adapter
- Painter Unreal Link dialog
- `paint.umg.*` Actions
- shared plugin schema/conversion update
- project-local plugin install/update
- Generate/Regenerate

Exit:

- UE 5.8에서 WBP 생성, compile, save, reopen 성공
- Painter 재생성이 사용자 소유 Blueprint 영역을 보존

### Phase 3: Components, tokens, prototype

- component definitions/instances/variants
- token library
- interactions and named events
- progress/toggle/slider
- responsive preview and localization preview

Exit:

- 하나의 component 수정이 모든 instance에 일관되게 반영
- state와 event가 Unreal runtime에서 동작

### Phase 4: Painter-specific visual assets

- deterministic layer/group bake
- alpha/color-space validation
- 9-slice texture authoring
- supported UI Material generator
- optional Material Paint normal/height presentation

Exit:

- native와 bake 결과가 preflight 보고와 일치
- 확대/축소 및 state 전환의 실제 Unreal capture 통과

### Phase 5: AI co-design and production QA

- 자연어 UI 생성/수정
- 변경 계획, 부분 적용, undo
- accessibility audit
- performance budget
- generated asset navigation and evidence capture

Exit:

- AI가 등록 Action만으로 샘플 HUD를 생성
- generate 전 변경 목록과 disposition을 설명
- 실제 Unreal 결과 증거가 자동 수집됨

## 15. File Placement Plan

예상 Python 모듈:

- `app/painter_ui_document.py`
- `app/painter_ui_layout.py`
- `app/painter_ui_components.py`
- `app/painter_ui_preflight.py`
- `app/painter_umg_adapter.py`
- `app/painter_ui_workspace.py`
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
- `tests/test_painter_umg_adapter.py`
- `tests/test_painter_ui_actions.py`
- shared `tests/test_unreal_umg_document.py`
- shared `tests/test_unreal_umg_plugin.py`

`app/video_editor_window.py`에는 어떤 UI Designer 또는 UMG 기능도 추가하지
않는다.

## 16. Verification Gates

기능 완료 주장은 다음을 모두 통과한 뒤에만 한다.

1. `.tspaint` UI document round trip
2. object/layout/component Action tests
3. native/material/baked/blocked preflight tests
4. Painter and Motion Designer provider compatibility tests
5. `tools/build_unreal_umg_plugin.py` plugin rebuild
6. canonical `D:\UE_5.8\Engine` compile
7. real UE 5.8 Widget Blueprint generation
8. Kismet compile, save, reload validation
9. regenerate while preserving user-owned additions
10. real Unreal viewport capture and pixel/content review
11. public installer contains only source-free UMG bundle
12. architecture and debug-capture boundary guards

Disposable captures and reports may use `debugCapture`, but source art,
templates, fonts, SDKs, plugins, and required test assets must use durable
project locations.

## 17. Initial Release Scope

첫 출시에서 반드시 제공:

- one/multiple artboards
- Frame, Shape, Text, Image, Button
- Layers, geometry, anchors, constraints
- horizontal/vertical auto layout
- 9-slice
- component button states
- native/baked preflight
- Painter Unreal Link
- Generate/Regenerate
- Action/MCP parity
- real UE 5.8 proof

첫 출시에서 제외:

- Figma 수준의 실시간 다중 사용자 협업
- 범용 HTML/CSS/React export
- arbitrary Blueprint graph authoring
- Painter 3D Blockout 전체를 Unreal runtime scene으로 변환
- 모든 Photoshop/Painter blend mode의 실시간 UMG 재현
- 지원되지 않는 효과의 묵시적 손실 변환

이 경계로 시작하면 Painter의 강점인 직접 만든 시각 자산을 살리면서도,
Motion Designer가 이미 만든 Unreal 전달 구조를 중복 없이 확장할 수 있다.
