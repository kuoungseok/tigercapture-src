# Painter UI M3 Component Tutorial Evidence

상태: `Active / Variant·Change-to·Slot vertical slice 구현, capture gate 잔여`  
기준일: `2026-08-04`

## 공식 자료

- [Create and use variants](https://help.figma.com/hc/en-us/articles/360056440594-Create-and-use-variants)
- [Explore component properties](https://help.figma.com/hc/en-us/articles/5579474826519-Explore-component-properties)
- [Edit instances with component properties](https://help.figma.com/hc/en-us/articles/8883757553943-Edit-instances-with-component-properties)
- [Interactive components](https://help.figma.com/hc/en-us/articles/360061175334-Create-interactive-components-with-variants)
- [Prototype actions](https://help.figma.com/hc/en-us/articles/360040035874-Prototype-actions)
- [Use slots](https://help.figma.com/hc/en-us/articles/38231200344599-Use-slots-to-build-flexible-components-in-Figma)
- [SlotSettings API](https://developers.figma.com/docs/plugins/api/SlotSettings/)
- [SlotNode API](https://developers.figma.com/docs/plugins/api/SlotNode/)

## T1. Component와 Instance

구현됨:

- subtree를 Component로 변환하고 stable source ID를 가진 Instance를 생성한다.
- main Component 수정 전파, local override 보존, 개별/전체 Reset, Detach, Undo가 있다.
- Inspector는 Definition과 Instance를 구분하고 typed property control을 만든다.

잔여:

- Go to main component의 완전한 Canvas 이동 UX.
- Component Set의 dashed-purple Canvas container.

## T2. Component Set과 Variant

공식 규칙:

1. Component Set은 Component만 포함한다.
2. 모든 Variant는 같은 property 집합을 공유한다.
3. 각 Variant는 `State=Default, Size=Small` 같은 고유 조합을 가진다.
4. 중복 조합은 데이터 손실 없이 conflict로 진단한다.
5. Instance Inspector에서 property별 dropdown으로 조합을 선택한다.

구현됨:

- `metadata.variant_properties` 기반 다차원 Variant model과 conflict report.
- property 정의/값 변경, 조합 전환, local override 보존.
- Inspector의 property별 독립 ComboBox.
- Figma `componentPropertyDefinitions`와 `variantProperties` import/export.
- 다중 선택된 독립 main Component를 `Combine as variants`로 결합한다. 기존 Canvas
  좌표와 간격을 유지하고, slash 이름이 있으면 공식 규칙대로 `Variant`,
  `Property 2` 속성/값을 만든다. 좌상단 Component가 default family가 된다.
- Canvas는 no-fill, dashed `#9747FF` virtual Component Set container를 그린다.
- Inspector의 Combine 버튼과 canonical `paint.ui.component.variants.combine` action은
  같은 mutation/Undo 경로를 사용한다.

잔여:

- Default/Hover/Pressed/Disabled × Small/Large 8개 실제 task capture.

## T3. Component Property

공식 Property 종류는 Boolean, Text, Instance Swap, Variant, Slot이다.

구현됨:

- Boolean, Text, Number, enum/Variant, Instance Swap 정의와 binding.
- Instance Inspector의 toggle, text, number, dropdown control.
- preferred Instance values는 스키마 v30에서 추가됐으며 추천 목록을 우선 표시하되
  다른 Component 선택을 제한하지 않는다. Figma `preferredValues`를 왕복한다.
- main Component의 Instance Swap property에는 `Preferred instances…` 편집 진입점이
  표시된다. 전용 modal에서 체크박스로 추가/제거하고 drag 또는 Up/Down으로 순서를
  바꾸며, 검색 결과에는 preferred가 아닌 local Component도 계속 남는다.
- Slot은 스키마 v31의 독립 계약이다. 단순 Frame 별칭이 아니다.
- Slot 정의는 직접 자식 Frame, 설명, preferred values와 다음 설정을 보존한다:
  `stretch_child_on_insert`, `display_empty_by_default`, `min_children`,
  `max_children`, `allow_preferred_values_only`.
- Instance Slot에 Layer/Instance를 넣어도 Detach되지 않으며 main sync와 JSON reload 뒤
  Slot-local hierarchy가 유지된다. Reset은 main Component의 Slot 콘텐츠로 복원한다.
- 자식 수와 preferred-only 위반은 편집을 막지 않고 `below_min`, `above_max`,
  `has_non_preferred` 진단으로 보고한다.
- Inspector는 Slot child count/violation과 Reset을 표시한다.
- Canvas에서 Layer를 Instance Slot 위로 끌면 detach 없이 Slot child가 된다.
  horizontal/vertical Auto Layout Slot은 드롭 중심점으로 삽입 순서를 계산하고,
  Layers panel의 inside/before/after drop도 동일한 Slot service를 사용한다.
- canonical action은 `slot.define`, `slot.inspect`, `slot.insert`, `slot.reset`이다.
- Figma import는 `SLOT`, `slotSettings`, preferred keys를 내부 stable ID로 옮긴다.
  export plugin은 실제 `createSlot()`과 `editComponentProperty(...slotSettings)`를 사용한다.
- TigerStudioUMG는 authored Slot 콘텐츠를 native panel의 정적 hierarchy로 변환하고
  `runtime_mutable=false`를 명시한다. 런타임 Slot mutation을 지원한다고 가장하지 않는다.

잔여:

- 실제 제품 캡처에서 preferred-values modal의 add/remove/reorder/search를 확인.
- 실제 제품 캡처에서 Canvas/Layer Slot drop과 재배치를 확인.
- rich text property의 부분 formatting 보존 task.

## T4. Interactive Component

구현됨:

- 같은 Component Set의 다른 Variant에만 `Change to` 연결 가능.
- inherited definition interaction, same-trigger Instance interaction 우선순위.
- override 보존, state memorization, family state sharing.
- 연속 interaction은 runtime의 현재 Variant 정의를 다음 trigger source로 사용한다.
- HTML prototype도 Instance subtree의 geometry/fill/stroke/radius/text를 대상 Variant로
  교체하고 preferred local override와 runtime opacity/visibility를 다시 적용한다.
- Navigation 계열 interaction에는 공식 State Management의
  `Reset component state` control이 있으며 Python/HTML runtime 상태를 초기화한다.
- 실제 nested Toggle Instance가 Settings Card Instance 안에서
  `Off → On → Off`로 연속 Change-to 된다. 이때 바깥 Card link, nested object ID와
  parent, local opacity override가 유지된다.
- Figma `CHANGE_TO` import/export.
- UMG 미지원은 `interactive_component_change_to_runtime_unsupported` Blocked preflight.

잔여:

- Hover/Pressed/Default 실제 pointer capture와 transition 시각 diff.
- nested Instance Change-to 실제 task와 capture.

## 현재 검증

- Slot model/service tests: sync, reload, reset, non-blocking limit violations.
- Slot Inspector test: child count, violation label, canonical Reset signal.
- Preferred Instance modal test: checkbox add/remove, order, search와 전체 후보 유지.
- nested Instance Swap task: preferred 순서, nested source 교체, local override,
  main sync와 JSON reload 보존.
- Slot direct manipulation test: Canvas drop, Auto Layout 축 순서, 단일 Undo.
- Figma tests: native SLOT/SlotSettings import와 createSlot export code.
- UMG test: native static panel mapping과 명시적 `runtime_mutable=false`.
- 전체 object subtree Copy/Paste는 object/interaction ID를 새로 만들고 내부 parent와
  reference를 remap한다. 같은 문서의 linked Instance는 component link와 override를
  유지하며 붙여넣기 전체가 단일 Undo다.
- normal 360×900, compact 300×650, 150% DPI Inspector와 Preferred instances
  modal, Canvas를 실제 Qt 제품 위젯으로 띄운 자동 캡처가 통과했다. 150%에서
  DPR 1.5, Inspector 540×1350, modal 780×930, Canvas 1350×975 픽셀 결과와
  Label/Boolean/Instance Swap control의 viewport 내부 배치를 JSON으로 검증한다.
- 같은 캡처 도구가 실제 Canvas pointer event를 보내 Default Instance에
  `mouse_enter → hover → press → focus`를 발생시킨다. runtime component ID가
  `Default → Hover → Pressed`로 바뀌고 세 단계 PNG의 Instance fill도
  `#0D99FF → #0B85DD → #086DB8`로 달라지는 시각 증거를 남긴다.
- 전체 subtree Copy/Paste 결과를 실제 `.tspaint` v3 archive로 저장하고 다시 읽어
  linked component ID, root/child hierarchy, local opacity override, 새 interaction ID와
  source object ID가 그대로 유지되는 round-trip test가 통과한다.
- Component 기반 Frame/Shape는 일반 compact 인스펙터가 아니라 component-aware
  Inspector로 라우팅되며 Variant/Definition/Instance property/Override 행이 실제로
  표시된다. 긴 form size hint는 scroll viewport 너비에 맞춰 축소된다.
- 현재 M3 집중 회귀: `178 passed`.
- Component Set Canvas render `9 passed`에 dashed-purple pixel evidence가 포함된다.

## M3 완료 게이트

아래가 모두 끝나기 전에는 M3 Complete로 표시하지 않는다.

1. 8-Variant Button 실제 task. (자동화 완료, 제품 캡처 잔여)
2. preferred-values 편집 modal과 nested Instance Swap task. (자동화 완료, 제품 캡처 잔여)
3. Canvas Slot drag/drop·재배치 task와 capture. (실제 Qt pointer 자동 캡처 완료)
4. Hover/Pressed/Default Preview와 trigger precedence 실제 capture.
   (실제 Qt pointer event, 단계별 PNG, nested Change-to 캡처 완료)
5. Undo/Redo, `.tspaint`, Copy/Paste, Figma stable-ID round trip.
   (동일 문서 전체 subtree Copy/Paste, JSON reload, `.tspaint` 자동화 완료;
   live Figma plugin 재반입 캡처 잔여)
6. normal/compact/150% DPI Inspector/Canvas capture.
   (Inspector/Preferred modal/Canvas 자동 캡처 완료)
7. Web/App/UMG 지원·변환·Blocked 항목의 사용자 가시성.

## 2026-08-04 Canvas Slot 실제 포인터 캡처 완료

- `tools/qa_painter_ui_m3_slot_capture.py`가 실제 Painter 창에서 선택된 원을
  Instance Slot으로 드래그한다. 서비스 함수를 직접 호출한 모의 검증이 아니다.
- 전, 드래그 중 Slot 하이라이트, 배치 후, Undo 후 PNG와
  `tigerstudio.painter.ui.m3_slot_pointer_capture.v1` JSON을 저장한다.
- 게이트는 `move` 상호작용, Slot preview ID, 최종 parent ID, Slot child ID,
  화면상 Slot 내부 포함, 단일 Undo와 원래 부모 복원을 모두 검사한다.
- 축소된 원의 고정 크기 Arc/Resize 판정이 이동 영역을 덮던 문제를 수정했다.
  손잡이 위치와 판정 크기는 표시 크기에 비례하고 정확한 손잡이는 계속 동작한다.
- 재부모화 시 새 부모 기준으로 constraints를 다시 캡처한다. 따라서 레이어 계층만
  맞고 화면에서 객체가 Slot 밖으로 튀는 상태도 실패로 판정한다.
- 지속 증거: `debugCapture/painter_ui_m3_slot/`의 before, drag-preview, after,
  undo PNG와 JSON 보고서. 이번 변경 영향 범위의 고유 회귀 135개와 아키텍처
  가드가 통과했다.
- M3의 Canvas Slot 직접 조작 캡처 항목은 완료다. 남은 외부 증거는 live Figma
  plugin 왕복이다.

## 2026-08-04 nested Change-to 제품 캡처 완료

- `tools/qa_painter_ui_m3_nested_change_to_capture.py`가 Card Instance 안의
  Toggle Instance를 실제 Canvas click으로 Off → On → Off 전환한다.
- 기존에는 runtime component ID만 바뀌고 PaintDialog 화면은 이전 Variant를
  그리는 결함이 있었다. Preview state 변경 시 effective Variant subtree, theme,
  constraints와 render index를 다시 계산하도록 수정했다.
- 게이트는 회색 `#8A8F98` → 초록 `#47C58E` → 회색 fill 변화와 서로 다른 PNG,
  바깥 Card component ID, nested parent ID, 로컬 opacity 0.7 보존을 검사한다.
- 지속 증거: `debugCapture/painter_ui_m3_nested_change_to/`의 off, on,
  off-again PNG와 `nested_change_to_capture.json`.
- 따라서 nested Change-to 제품 시각 캡처 항목도 완료다. 현재 남은 M3 외부
  왕복 증거는 live Figma plugin 재반입이다.

## 2026-08-04 live Figma 왕복 사전 게이트 보강

- 공식 절차는 Figma Desktop의 `Plugins > Development > Import plugin from
  manifest` 또는 Canvas 우클릭의 같은 경로를 사용한다.
  - https://help.figma.com/hc/en-us/articles/360042786733-Create-a-plugin-for-development
  - https://help.figma.com/hc/en-us/articles/38457121114263-Create-a-Figma-Design-plugin-with-the-Figma-MCP-server-and-agentic-tools
- 실제 package를 만들고 Figma가 생성한 현재 Page를 REST 형태 JSON으로 다시
  clipboard에 내보내는 `tools/qa_painter_ui_m3_figma_live_roundtrip.py`를 추가했다.
- 준비 과정에서 export가 `stable_id`를 쓰지만 import가 이를 무시하던 결함을
  발견했다. object, component, instance, Slot의 shared plugin data를 가져오기
  ID로 사용하도록 수정했다.
- 부모가 있는 레이어의 Figma 좌표는 부모-local 좌표로 변환한다. 기존 코드는
  artboard 좌표를 그대로 자식 `x/y`에 써서 중첩 레이어가 두 번 밀렸다.
- Instance 생성 뒤 복제된 sublayer를 `component_source_object_id`로 대응시키고,
  Instance Slot 안의 local child를 실제 `SlotNode.appendChild` 경로로 만든다.
  가져오기도 Instance에서 순회를 중단하지 않고 Slot hierarchy와 stable ID를
  복구한다. 이 동작은 Figma SlotNode 공식 `appendChild`/`insertChild` 계약을
  따른다: https://developers.figma.com/docs/plugins/api/SlotNode/
- package JS는 `node --check`를 통과했고, Figma/Component/Slot/Architecture 집중
  회귀 84개가 통과했다.
- 현재 실행 세션은 Windows interactive foreground handle이 `0`으로 반환되어
  Figma native manifest picker에 입력을 전달하거나 제품 화면을 캡처할 수 없다.
  따라서 이 항목을 Complete로 올리지 않는다. 실제 Figma에서 manifest 등록,
  plugin 실행, clipboard snapshot 재반입, Figma 화면 캡처가 모두 생겨야 닫는다.
- 실제 실행에는 Figma가 발급한 개발 플러그인 ID를 `--plugin-id`로 전달해야
  한다. 기본 placeholder ID는 package/문법 QA용이며 `live_execution_ready`를
  참으로 만들지 않는다.
