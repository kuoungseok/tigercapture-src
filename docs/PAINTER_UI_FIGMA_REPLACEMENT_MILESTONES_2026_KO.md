# Painter UI Figma 대체 실행 마일스톤

상태: `Active`  
기준일: `2026-08-04`

## 1. 목표와 범위

목표는 Painter UI를 단순한 Figma 모양의 화면이 아니라, 단일 사용자가 실제
제품 UI 문서를 제작하고 Prototype과 개발 전달까지 끝낼 수 있는 편집기로 만드는
것이다.

이번 로드맵에 포함한다.

- Page, Frame, Section, Layer hierarchy
- Shape, Vector, Text, Image authoring
- Auto Layout, responsive sizing, layout grid
- Component, Instance, Variant, Component Property
- Variable, Mode, Alias, Style, local library
- Prototype, Interactive Component, preview
- Inspect/Dev handoff와 Web/App/Unreal UMG preflight
- Figma plugin exchange와 Tiger Studio 문서 round trip

사용자 결정에 따라 이번 로드맵에서 제외한다.

- third-party Plugin runtime
- Widget runtime
- Community marketplace 운영
- real-time multiplayer cursor/editing
- cloud branch/merge와 조직 권한 서비스

Local review comment, local version evidence, package export는 유지한다.

## 2. 증거 규칙

각 마일스톤은 다음 순서의 증거만 사용한다.

1. Figma 공식 Help Center와 공식 tutorial
2. 현재 Figma 앱에서 공식 tutorial을 재현한 실제 화면과 입력 결과
3. 사용자가 제공한 screenshot은 공식 자료로 확인되지 않는 부분의 보충 증거
4. Painter의 document schema, mutation service, Undo/Redo, delivery contract
5. 자동 테스트와 정상/compact/high-DPI 실제 캡처

화면이 비슷하거나 버튼이 존재하는 것만으로 완료하지 않는다. Canvas, Layers,
Inspector, 저장 결과가 동시에 일치하고 실제 작업을 끝낼 수 있어야 한다.

## 3. 공통 완료 게이트

모든 마일스톤은 다음을 모두 만족해야 `Complete`다.

- 공식 tutorial의 시작 상태부터 최종 상태까지 재현
- UI와 Action이 같은 mutation service 사용
- 한 단계 Undo와 Redo
- `.tspaint` 저장/재로드 round trip
- Copy/Paste/Duplicate와 부모 hierarchy 무결성
- Canvas, Layers, Inspector 동기화
- keyboard, focus, accessible name 검증
- 1440×900, 900×650 compact, 150% DPI 캡처
- 관련 Painter UI 회귀와 architecture guard 통과
- Figma/Web/App/UMG 전달 결과를 Native/Converted/Material/Baked/Blocked로 보고
- 지원하지 않는 속성을 조용히 누락하지 않음

## 4. 실행 순서

### M0. 기준선과 조사 하네스

상태: `Complete baseline / 지속 갱신`

목적은 추측성 구현을 막고 이후 변경의 회귀를 검출하는 것이다.

산출물:

- 공식 문서 URL, Figma 재현 단계, 캡처, 관찰 결과를 한 기능 단위로 연결
- 선택 없음/Frame/Shape/Text/Component/Instance 상태별 Inspector snapshot
- 내부 schema와 실제 UI 상태의 capability matrix
- 전체 `test_painter_ui_*.py` 파일별 격리 회귀
- release corpus와 architecture guard

현재 증거:

- Painter UI 테스트 파일 `106/106` 통과
- 집중 Boolean/Figma/menu/release/architecture `63 passed`
- normal/150% DPI Boolean 캡처 통과

다음 단계 진입 조건:

- 새 기능마다 공식 reference와 task-completion test 이름을 먼저 기록할 수 있음

### M1. Core Authoring 완결

상태: `Complete v1 / M8 scale hardening pending`

사용자가 Frame 안에 Shape/Text/Image를 만들고 선택·편집·정렬·삭제하는 기본 흐름을
더 이상 우회 없이 끝낼 수 있게 한다.

구현 범위:

- Move/Hand/Scale과 deep select 입력 규칙
- Frame/Section/Slice 생성과 올바른 hierarchy
- Rectangle/Line/Arrow/Ellipse/Polygon/Star/Image/Pen/Pencil/Text
- 생성 중 live preview와 생성 직후 edit 상태
- Rectangle radius, Ellipse arc/ring, Polygon/Star count/radius/smoothing gizmo
- open vector path, node/handle, join/split/close, stroke outline
- Text auto width/fixed box, mixed range, font fallback, baseline
- smart guide, Alt distance, equal gap, ruler/guide
- Fill/Stroke/Effect/Export 공용 Inspector section
- Boolean/Outline/Flatten/Mask의 non-destructive/edit/release 흐름

완료 기준:

- Frame은 visual shape와 구분되고 Shape gizmo가 생기지 않음
- Line/Arrow는 bounding box 도형이 아니라 두 endpoint로 편집됨
- 각 도형의 생성·편집 tutorial을 Canvas/Layers/Inspector까지 재현
- 현재 공개 도구의 task-completion 회귀와 normal/high-DPI 캡처 통과
- 대형 장면 성능과 전체 theme matrix는 기능 재개가 아니라 M8 release gate에서 관리

공식 기준:

- [Shape tools](https://help.figma.com/hc/en-us/articles/360040450133-Shape-tools)
- [Arc tool](https://help.figma.com/hc/en-us/articles/360040450173-Arc-tool-create-arcs-semi-circles-and-rings)
- [Guide to text](https://help.figma.com/hc/en-us/articles/360039956434-Guide-to-text-in-Figma-Design)
- [Boolean operations](https://help.figma.com/hc/en-us/articles/360039957534-Boolean-operations)

### M2. Layout와 Responsive

상태: `Complete v1 / bounded official workflows`

구현 범위:

- Auto Layout 생성/해제와 Horizontal/Vertical/Wrap
- Padding, item gap, row gap, main/cross/baseline alignment
- Fixed/Hug/Fill, Min/Max size, aspect ratio
- Absolute child와 in-flow child 전환
- nested Auto Layout의 안정적 Hug/Fill 계산
- Grid Auto Layout, row/column span, cell alignment
- Layout Grid와 responsive constraint
- Canvas padding/gap handle과 drag reorder
- Figma Auto Layout을 UMG flow/grid/stretch로 명시적 변환

완료 기준:

- 공식 Auto Layout tutorial 문서를 같은 hierarchy와 크기로 재현
- Inspector 입력과 Canvas handle이 같은 값과 Undo command를 사용
- Web/App/UMG 결과의 layout diff가 허용 오차 안에 있음

### M3. Component, Instance, Variant

상태: `Active / multidimensional Variant, Change-to, Slot vertical slices implemented`

구현 범위:

- main Component와 Instance
- Component Set과 Variant property/value 조합
- Boolean, Text, Instance Swap, Variant, Slot property
- preferred Instance와 nested Instance swap
- Instance override 보존, reset, detach
- main Component 수정 전파와 충돌 규칙
- interactive Component의 Variant transition
- Assets 검색과 Canvas/Layers/Inspector 통합

완료 기준:

- Button을 Default/Hover/Pressed/Disabled Variant로 만들고 Instance 하나로 실행
- Text/Visibility/Swap override가 Variant 전환과 재로드 후 유지
- 삭제·이름 변경·중첩 Component에서 dangling reference가 없음

공식 기준:

- [Create and use variants](https://help.figma.com/hc/en-us/articles/360056440594-Create-and-use-variants)
- [Component properties](https://help.figma.com/hc/en-us/articles/5579474826519-Explore-component-properties)
- [Interactive components](https://help.figma.com/hc/en-us/articles/360061175334-Create-interactive-components-with-variants)

### M4. Variables, Modes, Styles, Local Library

상태: `Schema foundation implemented / full binding pending`

구현 범위:

- Color/Number/String/Boolean Variable
- Collection, Group, Mode
- same-type Alias와 cycle 검출
- Fill/Stroke/Text/Visibility/Spacing/Radius/Typography/Variant property binding
- Page/Frame/Component/Instance별 Mode override와 Auto inheritance
- Light/Dark, locale, device size Mode 전환
- composite Style과 raw Variable 역할 분리
- local library publish/update/relink와 변경 diff
- Figma exchange에서 variable identity와 binding 보존

완료 기준:

- 한 Collection의 Mode 전환으로 theme, 언어, spacing이 동시에 바뀜
- Alias와 local library 업데이트가 Instance override를 파괴하지 않음
- unresolved/cyclic Variable은 명시적 진단을 제공

공식 기준:

- [Variables, collections, and modes](https://help.figma.com/hc/en-us/articles/14506821864087-Overview-of-variables-collections-and-modes)
- [Guide to variables](https://help.figma.com/hc/en-us/articles/15339657135383-Guide-to-variables-in-Figma)

### M5. Prototype와 Interactive Runtime

상태: `Basic navigation implemented / advanced runtime pending`

구현 범위:

- Trigger: click/tap, hover, press, drag, key, delay
- Action: navigate, back, open/swap/close overlay, scroll, set variable/mode
- 여러 Action의 순서 실행
- if/else, boolean/string/number expression
- overlay position, background, close behavior
- scroll container와 scroll position preserve/reset
- Smart Animate 지원 속성과 fallback report
- flow starting point, device presentation, preview history
- Interactive Component와 Variable runtime

완료 기준:

- 공식 checkout/quiz 유형의 변수·조건 prototype을 실행
- Preview와 exported prototype의 결과가 동일
- 지원하지 않는 transition은 조용히 dissolve하지 않고 fallback을 표시

### M6. Assets와 Design System 운영

상태: `Partial`

구현 범위:

- Layers/Assets 전환과 검색
- local Component/Style/Variable/Template 분류
- thumbnail, property summary, 사용 위치 찾기
- library package publish/update/disable/relink
- missing library recovery와 update review
- batch rename, select similar, style cleanup
- template 적용 위치와 충돌 preview

완료 기준:

- 여러 Page의 중형 디자인 시스템에서 원하는 Component를 검색·배치·교체
- library 변경 적용 전후 diff와 되돌리기 가능

### M7. Inspect, Dev Handoff, Delivery

상태: `Contract implemented / product UX pending`

구현 범위:

- Design과 분리된 Dev mode
- ready-for-dev Frame/Section 탐색
- measurement, annotation, asset export
- typography/color/spacing/token/interaction inspect
- Web/App 코드 snippet과 component mapping
- Target별 Native/Vector/Platform Effect/Material/Baked/Actor Only/Blocked
- UMG Widget Blueprint compile와 실제 Unreal capture
- Figma plugin exchange라는 정확한 제품 명칭

완료 기준:

- 개발자가 원본을 편집하지 않고 선택 Layer의 모든 구현 정보를 획득
- 전달에서 누락되는 속성이 0개이거나 명시적 Blocked
- Unreal 지원 주장에는 실제 Blueprint compile/capture 증거가 존재

### M8. Scale, Reliability, Release

상태: `Pending`

구현 범위:

- 10,000+ Layer와 대형 Vector/Boolean 성능
- viewport culling, geometry/style cache, incremental recompute
- autosave, crash recovery, schema migration
- missing font/image/library recovery
- keyboard-only, screen-reader, locale audit
- long-session memory와 Undo history budget
- editable SVG/PNG/prototype/Figma exchange/UMG release corpus

완료 기준:

- 명시한 대형 문서 budget을 모두 통과
- 정상/compact/150% DPI와 지원 theme 실제 캡처
- 전체 Painter UI 회귀, architecture, release corpus가 모두 통과
- 모든 공개 기능의 지원 수준이 SPEC과 UI에 동일하게 표시

## 5. 실행 규칙

순서는 `M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8`로 고정한다.

- 한 마일스톤의 model contract가 없으면 다음 UI를 먼저 만들지 않는다.
- 다음 마일스톤의 기반 작업이 필요해도 현재 단계의 완료 증거를 먼저 닫는다.
- Figma 화면을 닮은 placeholder는 구현으로 계산하지 않는다.
- 공식 자료에서 확인되지 않는 동작은 `Unverified`로 기록하고 임의 구현하지 않는다.
- 사용자가 별도 결정을 내리지 않아도 공식 자료와 이 순서에 따라 계속 진행한다.
- 공식 자료가 없거나 서로 충돌할 때만 사용자에게 증거와 선택지를 제시한다.

## 6. 현재 다음 작업

현재 실행 위치는 `M3 Component, Instance, Variant`다. M2.1~M2.8은
`PAINTER_UI_M2_AUTO_LAYOUT_TUTORIAL_EVIDENCE_KO.md`의 제한된 공식 workflow와
실제 UE 5.8 Widget Blueprint 증거까지 Complete v1이다.
M3의 공식 관찰 단계와 task gate는
`PAINTER_UI_M3_COMPONENT_TUTORIAL_EVIDENCE_KO.md`를 우선 기준으로 사용한다.

다음 순서:

1. preferred Instance values 편집 modal과 nested Instance Swap 실제 task
   (자동화 완료, 실제 제품 캡처 잔여)
2. Canvas Slot drag/drop·재배치 직접 조작 UX와 실제 캡처
   (실제 Qt pointer 기반 전·드래그 중·배치 후·Undo 후 캡처 완료)
3. 8-Variant Button tutorial task와 Hover→Pressed→Default 실제 캡처
   (실제 Qt pointer event 기반 Default→Hover→Pressed 단계별 캡처 완료)
4. nested Change-to 실제 task
   (실제 Qt click Off→On→Off 제품 캡처까지 완료)
5. `.tspaint`/Copy-Paste/Figma stable-ID round trip과 150% DPI gate
   (전체 subtree Copy/Paste, `.tspaint`, normal/compact/150% Inspector·Preferred
   modal·Canvas 자동 캡처 완료; live Figma plugin 재반입 캡처 잔여)
6. M3 완료 증거를 닫은 뒤 M4로 이동

### 2026-08-04 M3 Slot 직접 조작 증거

- 실제 Canvas pointer drag로 외부 Layer를 Instance Slot에 넣는 흐름 완료.
- 드래그 하이라이트, 최종 계층, 화면상 포함, 단일 Undo를 자동 캡처로 고정.
- 작은 Ellipse의 Arc/Resize 기즈모가 이동을 가로채는 축소 줌 결함 수정.
- 일반 컨테이너와 Slot 재부모화 모두 새 부모 기준 constraints를 재작성하여
  보이는 위치를 보존한다.
- 증거 도구: `tools/qa_painter_ui_m3_slot_capture.py`
- 지속 캡처: `debugCapture/painter_ui_m3_slot/`
- 다음 M3 증거: live Figma plugin 재반입 왕복.

### 2026-08-04 nested Change-to 제품 증거

- Card Instance 안 Toggle Instance의 실제 click 전환을 Off→On→Off PNG로 고정.
- 상태 ID만 바뀌고 화면 스타일이 갱신되지 않던 Preview effective-document
  재해석 결함을 수정.
- 외부 Card Instance, nested parent, 로컬 opacity override 보존을 함께 검사.
- 증거 도구: `tools/qa_painter_ui_m3_nested_change_to_capture.py`
- 지속 캡처: `debugCapture/painter_ui_m3_nested_change_to/`

### 2026-08-04 live Figma 왕복 준비 상태

- `tools/qa_painter_ui_m3_figma_live_roundtrip.py`가 실제 export package, live Page
  serializer, clipboard/stdin 재반입, stable-ID 전수 비교 report를 만든다.
- 왕복 준비 중 stable object/component/instance/Slot ID 보존, nested parent-local
  좌표, Instance Slot sublayer 매핑과 Slot-local child export/import 누락을 수정했다.
- 생성된 `code.js`는 Node syntax check를 통과했고 집중 회귀 84개가 통과했다.
- 실제 실행은 Figma가 발급한 개발 플러그인 ID를 `--plugin-id`로 받아야 하며,
  placeholder manifest ID 상태는 live 실행 준비 완료로 판정하지 않는다.
- 현 세션은 interactive Windows desktop foreground가 없어 Figma native file
  picker를 조작할 수 없다. live 제품 실행과 화면 캡처가 생기기 전까지 M3는
  Active이며 M4로 이동하지 않는다.
