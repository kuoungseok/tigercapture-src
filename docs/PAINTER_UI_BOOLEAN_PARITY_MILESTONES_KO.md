# Painter UI Boolean Figma Parity Milestones

상태: `Implemented / parity completion gates pending`  
소유 범위: Painter UI Design의 도형/벡터 Boolean 작성, 편집, 출력  
선행 기반: Painter UI schema 18 비파괴 Boolean 그룹

## 1. 기준 자료와 주장 경계

구현 순서와 완료 판정은 다음 Figma 공식 문서의 공개 동작만 기준으로 한다.

- Boolean operations:
  <https://help.figma.com/hc/en-us/articles/360039957534-Boolean-operations>
- Edit vector layers:
  <https://help.figma.com/hc/en-us/articles/360039957634-Edit-vector-layers>
- Flatten layers:
  <https://help.figma.com/hc/en-us/articles/30101373312279-Flatten-layers>
- View layer outlines:
  <https://help.figma.com/hc/en-us/articles/5724448965527-View-layer-outlines-in-Figma-Design>

공개 문서에 없는 내부 계산 규칙은 Figma와 동일하다고 주장하지 않는다. Qt 경로
엔진을 사용하는 Painter의 결정론적 규칙으로 문서화한다. 각 단계는 실제 데스크톱
UI 캡처, 문서 round-trip, Undo/Redo, Canvas/PNG/SVG 결과가 모두 통과하기 전에는
`Complete`로 표시하지 않는다.

## 2. 현재 기준선

현재 구현은 Union, Subtract, Intersect, Exclude, 안정적인 operand ID, 비파괴
Release, 선택 근처의 임시 Boolean 바, Action API, Canvas/PNG/SVG 공유 경로를
제공한다.

남은 핵심 차이는 다음과 같다.

- Text operand가 없고 Frame operand를 허용해 Figma의 지원 대상과 다르다.
- Fill 경계 중심이며 stroke width/alignment를 Boolean 입력 형상에 포함하지 않는다.
- 모든 연산이 최상단 operand 스타일을 계승한다. Subtract는 최하단 스타일이어야 한다.
- compose는 Polygon/Star/Arc를 허용하지만 기존 그룹의 set 경로는 허용 집합이 달라
  연산 변경이 실패할 수 있다.
- operand가 실제 Boolean 그룹의 편집 가능한 자식 계층이 아니라 sibling ID 참조다.
- nested Boolean, 전용 단축키, Outline 편집, Flatten이 Figma 수준이 아니다.
- TigerStudioUMG는 Boolean을 명시적으로 Blocked 처리한다.

## 3. 실행 마일스톤

### M1B.1 Operand 및 스타일 정확성

목표:

- 지원 대상을 Shape, Vector Path, Text로 맞춘다.
- Frame과 Section은 Boolean operand에서 제외한다.
- Union/Intersect/Exclude는 최상단 operand, Subtract는 최하단 operand의 Fill,
  Stroke, Effect를 그룹 스타일로 계승한다.
- compose/set/inspect의 operand kind 검증을 하나의 공유 함수로 통합한다.
- Polygon/Star/Arc 그룹의 연산 변경 회귀를 닫는다.

완료 조건:

- 각 지원/비지원 kind의 UI와 Action 결과가 동일하다.
- 네 연산의 style-source golden test가 통과한다.
- 기존 schema 18 문서가 손실 없이 migration/round-trip 된다.

### M1B.2 Full Geometry Boolean

목표:

- Fill과 visible Stroke를 모두 Boolean 입력 형상으로 계산한다.
- Inside/Center/Outside stroke alignment와 width를 반영한다.
- 열린 Vector Path, 독립 corner radii, Arc/Star/Polygon 형상을 동일 resolver로 처리한다.
- Boolean 결과의 outer/inner edge에 그룹 Stroke와 Effect가 적용되게 한다.

완료 조건:

- stroke alignment별 Union/Subtract/Intersect/Exclude golden scene이 있다.
- Canvas, PNG, editable SVG의 bounds와 구멍 수가 일치한다.
- 빈 Intersect는 정상적인 빈 결과이며 operand를 손상하지 않는다.

### M1B.3 Boolean 그룹 내부 직접 편집

목표:

- Layers에 Boolean 그룹 아래 operand를 실제 자식 계층으로 표시한다.
- 더블클릭/Enter로 그룹 범위에 진입하고 Canvas 또는 Layers에서 operand를 선택한다.
- 내부 operand의 위치, 크기, 회전, corner radius를 직접 수정하면 결과가 즉시 갱신된다.
- 그룹 내부 operand의 Fill, Stroke, Effect, Opacity는 Figma 공식 동작처럼 비활성화한다.
- Esc는 한 단계씩 편집 범위를 빠져나온다.

완료 조건:

- 그룹 진입, 내부 선택, 직접 조작, Esc 복귀가 각각 한 번의 예상 가능한 상태 전이를 가진다.
- 수정과 Release가 안정 ID, z-order, relative transform을 보존한다.
- 각 직접 조작은 한 번의 Undo 단위다.

### M1B.4 명령, 단축키 및 메뉴 UX

목표:

- Boolean 메뉴, 임시 선택 바, 우클릭 메뉴, Quick Actions가 같은 mutation service를 쓴다.
- Windows 기준 `Alt+Shift+U/S/I/E`를 제공한다.
- 선택한 Boolean 그룹에는 현재 연산, 연산 변경, Release/Ungroup가 표시된다.
- 적용할 수 없는 선택에는 명령을 숨기거나 구체적인 비활성 사유를 제공한다.

완료 조건:

- 네 진입면의 결과 문서와 Undo label이 동일하다.
- 단축키 충돌 검사가 통과한다.
- compact/desktop UI에서 메뉴가 잘리거나 고정 패널 폭을 차지하지 않는다.

### M1B.5 Nested Boolean 및 복합 경로 안정성

목표:

- Boolean 그룹을 다른 Boolean 그룹의 operand로 사용할 수 있다.
- 순환 참조와 자기/자손 참조를 차단한다.
- self-intersection, coincident edge, tangent contact, disjoint island, hole을 결정론적으로 처리한다.
- 결과와 hit testing, selection bounds, Smart Guide bounds가 같은 geometry cache를 쓴다.

완료 조건:

- 2단계와 4단계 nested Boolean round-trip 및 Release 테스트가 통과한다.
- 100/1,000 node 복합 경로에서 결과 hash가 반복 실행 간 동일하다.
- 잘못된 참조는 문서를 손상하지 않고 명시적 오류를 반환한다.

### M1B.6 Outline 및 Flatten

목표:

- Outline 모드에서 숨겨진 operand, bounds, stroke geometry를 표시하고 선택할 수 있다.
- Flatten은 Boolean 그룹을 하나의 editable Vector Network로 변환한다.
- Flatten은 파괴적이지만 한 번의 Undo로 원본 그룹을 복원한다.
- Flatten 후 Fill/Stroke/Effect와 visual bounds가 유지된다.

완료 조건:

- Outline on/off가 문서를 변경하지 않는다.
- Flatten 결과는 원본 operand ID에 의존하지 않는다.
- Canvas/PNG/SVG 전후 visual-diff 허용치를 문서화하고 통과한다.

### M1B.7 Import, Export 및 UMG 전달

목표:

- Figma import/export가 Boolean operation, operand order, nested hierarchy를 가능한 범위에서
  editable node로 보존한다.
- SVG는 editable compound path를 내보내며 raster fallback을 조용히 사용하지 않는다.
- TigerStudioUMG는 Native, Material, deterministic Bake, Blocked 중 하나를 명시한다.
- UMG Bake를 구현할 경우 authored bounds와 DPI에서 안정적인 자산을 생성한다.

완료 조건:

- Figma fixture round-trip에서 operation/order/hierarchy 손실이 없다.
- SVG 재가져오기 visual-diff가 허용치 이내다.
- UMG는 실제 Widget Blueprint compile/capture 증거 없이는 지원으로 표시하지 않는다.

### M1B.8 성능, 접근성 및 완료 게이트

목표:

- operand/path revision 기반 geometry cache로 불필요한 전체 재계산을 제거한다.
- 키보드 focus, accessible name, high-contrast selection/outline 표현을 제공한다.
- 복잡한 Boolean 편집 중 UI thread stall과 생성 지연을 측정한다.

완료 조건:

- 100개 operand, 10,000개 path node 문서의 선택/이동/연산 변경 benchmark를 기록한다.
- desktop/compact/high-DPI/dark/light 실제 캡처 QA가 통과한다.
- focused tests, 전체 `test_painter_ui_*`, architecture guard가 모두 통과한다.
- 위 M1B.1~M1B.8 증거 링크가 채워진 뒤에만 `Boolean Parity Complete v1`로 표시한다.

## 4. 실행 순서

`M1B.1 → M1B.2 → M1B.3 → M1B.4 → M1B.5 → M1B.6 → M1B.7 → M1B.8`

M1B.1과 M1B.2는 정확성 게이트다. 이 두 단계가 끝나기 전에 외형만 닮은 메뉴나
UMG 지원을 먼저 확장하지 않는다.

## 5. 2026-08-04 구현 및 검증 현황

| 단계 | 상태 | 검증된 범위 |
| --- | --- | --- |
| M1B.1 | 구현됨 | Text 포함, Frame 제외, 연산별 style source, Polygon/Star/Arc |
| M1B.2 | 구현됨 | Fill+visible Stroke, inside/center/outside, Canvas/PNG/editable SVG |
| M1B.3 | 구현됨 | 실제 자식 계층, Boolean edit scope, operand 외형 속성 잠금 |
| M1B.4 | 구현됨 | 메뉴/컨텍스트 바/Action, `Alt+Shift+U/S/I/E`, Ungroup |
| M1B.5 | 구현됨 | 2/4단계 중첩, 순환 거부, 중첩 Release 부모 참조 복구 |
| M1B.6 | 구현됨 | Outline 옵션, `Ctrl+Shift+O`, Flatten `Alt+Shift+F`, 참조 정리 |
| M1B.7 | 부분 완료 | Figma 중첩 hierarchy/order와 editable SVG 재렌더 diff 완료. UMG는 bake 미구현으로 명시적 `Blocked` |
| M1B.8 | 진행 중 | revision cache, 접근성 계약, benchmark, 150% high-DPI 캡처와 전체 106-file 회귀 완료. light 캡처/대규모 성능 게이트 미완료 |

검증 명령과 결과:

- 집중 회귀, 릴리스 코퍼스 및 아키텍처 가드:
  `python -m pytest tests/test_painter_ui_boolean_authoring.py tests/test_painter_ui_figma_completion.py tests/test_painter_ui_main_menu.py tests/test_painter_ui_release_corpus.py tests/test_editor_architecture_rules.py -q`
  → `63 passed`.
- 실제 Painter UI 캡처:
  `python tools/qa_painter_ui_boolean_authoring.py` → `ok: true`.
- 150% high-DPI 캡처:
  `QT_SCALE_FACTOR=1.5 python tools/qa_painter_ui_boolean_authoring.py --output-dir debugCapture/painter_ui_boolean_m1_hidpi`
  → `ok: true`.
- editable SVG는 Qt SVG로 다시 렌더하여 Canvas PNG와 채널 차이 24 초과 픽셀의
  비율이 2% 미만인지 검사한다. SVG 색 알파는 SVG 1.1 호환 RGB와 개별
  `fill-opacity`/`stroke-opacity`로 기록하며 배경 크기는 숫자 viewport로 기록한다.
- 성능/결정론 측정:
  `python tools/qa_painter_ui_boolean_performance.py` → `ok: true`.
  100 operand compose `27.774 ms`, resolve median `22.438 ms`, 한 operand 이동
  `54.414 ms`, 연산 변경 `61.412 ms`, 10,000 node resolve `161.675 ms`였다.
  동일 장면 5회 결과 hash는 모두 같았다. 이 수치는 현재 장비의 단일 측정이며
  Figma와 동등한 성능을 뜻하지 않는다.
- 재생성 가능한 QA 보고서는
  `debugCapture/painter_ui_boolean_m1/boolean_authoring_report.json`과
  `debugCapture/painter_ui_boolean_m1/boolean_performance_report.json`에 남긴다.
  `debugCapture`는 삭제 가능한 증거 공간이므로 완료 판정의 영구 근거는 위 테스트와
  이 문서의 계약이다.

현재 완료 게이트:

- 전체 `test_painter_ui_*.py` 106개 파일을 파일별 격리 실행하여 `106/106`이
  통과했다. Native `.tspaint`, Figma exchange, template, handoff, prototype,
  review, provider-neutral UMG contract의 릴리스 코퍼스도 `7/7` 통과했다.
- 회귀/코퍼스 게이트는 닫혔지만 아래 실성능·시각·Unreal 증거가 남아 있으므로
  Boolean 완전 동등성 표시는 보류한다.
- 10,000 node resolve가 `161.675 ms`로 실시간 한 프레임 예산을 넘는다.
- 제품 전체 light UI 실제 캡처가 아직 없다. 150% high-DPI dark UI 캡처는 통과했다.
- UMG Boolean deterministic bake와 실제 Widget Blueprint compile/capture가 없다.

따라서 현재 상태를 `Boolean Parity Complete v1`로 표시하지 않는다.
