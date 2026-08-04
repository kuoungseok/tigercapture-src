# Painter UI M2 Auto Layout 튜터리얼 증거

## M2.8 M2 마감 검증 (Complete v2, 2026-08-03)

- M2/ScrollBox/UMG 변경 경로 회귀: 89 passed, 2 unrelated PaintDialog tests deselected.
- TigerStudioUMG 문서/플러그인/재료/레이아웃 회귀가 이 집합에 포함된다.
- Editor architecture guard: 4 passed.
- UE 5.8 실제 QA: Widget Blueprint 생성 및 로드, 17 widgets, `HorizontalBox`,
  `GridPanel`, Both축 `ScrollBox`, Fixed `CanvasPanel`, generated class 로드,
  visual capture, shader compile error 0을 확인했다.
- 실증 보고서: `debugCapture/painter_ui_designer/unreal_umg/qa_report.json`
- 실증 캡처: `debugCapture/painter_ui_designer/unreal_umg/painter_umg_unreal_editor.png`
- 전체 Painter UI 테스트를 한 Qt 프로세스로 실행하면 현재 작업트리의 기존 focus audit 3건과
  PySide 종료 충돌이 남는다. M2 지원 범위를 과장하지 않으며, 해당 문제는 M2 Auto Layout
  계약의 통과 증거와 분리한다.

M2.1~M2.8의 공식 문서 기반 범위는 `Complete v2`이다. 이는 Figma 전체 호환 선언이 아니다.

## M2.7 Scroll, overflow, fixed, sticky (Complete v1, 2026-08-03)

공식 근거:

- [Prototype scroll and overflow behavior](https://help.figma.com/hc/en-us/articles/360039818734-Prototype-scroll-and-overflow-behavior)
  - 오버플로 스크롤은 Frame에 설정하며 Horizontal, Vertical, Both directions를 제공한다.
  - 콘텐츠가 Frame 경계를 넘어야 실제 스크롤이 발생하고, Layout의 Clip content가 함께 필요하다.
  - 스크롤 Frame의 자식은 Scroll with parent, Fixed, Sticky 위치 동작을 가진다.
  - Auto Layout 안의 Fixed 자식은 Ignore auto layout이어야 하며 Sticky는 세로 스크롤이 필요하다.

구현 및 검증:

- Painter UI document version 29에 `scroll.overflow`, `scroll.position`,
  `scroll.preserve_position`을 안정적으로 직렬화한다.
- Inspector는 Frame 선택 때 Overflow, 스크롤 Frame 자식 선택 때 Scroll position만 문맥적으로 표시한다.
  스크롤을 켜면 Clip content도 함께 켜 invalid 중간 상태를 만들지 않는다.
- layout diagnostics는 Frame/Clip/부모 스크롤/Sticky 세로축/Fixed Ignore 조건과 실제 overflow content를 검사한다.
- HTML prototype은 부모-자식 DOM hierarchy와 축별 overflow CSS를 생성하고 Fixed 자식의 스크롤 보정을 실행한다.
- Tiger UMG schema v10/plugin 0.9.0은 Horizontal/Vertical/Both overflow를
  실제 `UScrollBox`로 생성하고 Fixed 자식을 Overlay의 고정 Canvas로 분리한다.
- Sticky만 `prototype_sticky_requires_umg_runtime_binding` blocker로 유지한다.

다음 단계는 M2.8 전체 회귀, 스펙 정합성, Unreal 실캡처 마감이다.

## M2.5 Grid Auto Layout (Complete v1, 2026-08-03)

공식 근거:

- [Use the grid auto layout flow](https://help.figma.com/hc/en-us/articles/31289469907863-Use-the-grid-auto-layout-flow)
  - Grid는 행과 열로 자식을 자동 배치하고 한 자식이 여러 행/열을 span할 수 있다.
  - 자식은 셀 내부에서 개별 정렬할 수 있으며 Grid는 Wrap과 다른 독립 flow다.
- [Explore auto layout properties](https://help.figma.com/hc/en-us/articles/360040451373-Explore-auto-layout-properties)
  - Grid도 padding, 두 축 gap, Fixed/Hug/Fill 계약을 공유한다.

구현 및 검증:

- Inspector는 Grid container에 Columns, Grid 자식에 Column/Row span을 문맥적으로
  노출한다. resolver는 안정적인 셀 점유, span, Hug/Fill/stretch, 셀 정렬을 계산한다.
- Painter UI document version 28과 Tiger UMG schema v9/plugin 0.8.0이 Grid 의미를
  저장하고 실제 `UGridPanel`/`UGridSlot`으로 변환한다.
- UE 5.8 Editor/Development/Shipping 빌드가 성공했다. 실제 Grid와 2-column span을
  포함한 Widget Blueprint 생성·컴파일·재오픈 및 `GridPanel` 클래스 확인도 통과했다.
  재생성 보고서는 `debugCapture/painter_ui_designer/unreal_umg/qa_report.json`이다.

다음 단계는 M2.6 nested Auto Layout과 Absolute child 상호작용이다.

## M2.6 Nested Auto Layout and Ignore auto layout (Complete v1, 2026-08-03)

공식 근거:

- [Combine vertical, horizontal, and grid auto layout flows](https://help.figma.com/hc/en-us/articles/31441443713047-Combine-vertical-horizontal-and-grid-auto-layout-flows)
  - nested Auto Layout frame은 부모의 child sizing과 자신의 container flow를 동시에 가진다.
- [Guide to auto layout](https://help.figma.com/hc/en-us/articles/360040451373-Explore-auto-layout-properties)
  - `Ignore auto layout`은 과거 Absolute position 이름이며 부모 flow에서 제외된다.
  - flow를 무시하는 자식은 일반 frame처럼 constraints로 부모 resize에 반응한다.

구현 및 검증:

- Inspector와 canvas 용어를 `In flow`/`Ignore auto layout`로 맞췄다.
- nested Horizontal/Vertical/Grid container는 부모 child sizing과 자신의 flow controls를
  함께 유지한다.
- constraint → Auto Layout 순서 뒤 부모가 이동한 경우 Ignore 자식을 최종 부모 geometry로
  다시 계산하고, 그 안의 nested flow를 재배치하는 수렴 pass를 추가했다.
- local nested geometry, final-parent constraints, canvas toggle, native nested UMG panels의
  focused tests가 통과했다.
- UMG에서 nested flow panels는 native 변환한다. Ignore child는 overlay semantics가
  추가되기 전까지 기존의 명시적 blocker
  `auto_layout_absolute_child_unsupported:<object_id>`를 유지하며 절대 누락하지 않는다.

다음 단계는 M2.7 responsive resizing, clipping, overflow, scroll behavior다.

상태: `M2.1 Auto Layout 진입 Complete v1`

이 문서는 Painter UI의 Auto Layout 작업을 Figma 공식 도움말의 공개 동작과
Painter 내부의 결정적 구현으로 나누어 기록한다. 공식 문서에서 확인되지 않은
Figma 내부 휴리스틱을 동일하다고 주장하지 않는다.

## 공식 근거

- [Toggle on auto layout in designs](https://help.figma.com/hc/en-us/articles/5731482952599-Toggle-on-auto-layout-in-designs)
  - 하나 이상의 레이어를 선택하고 `Shift+A`, 오른쪽 사이드바의
    `Add auto layout`, 또는 우클릭 메뉴의 `Add auto layout`으로 진입한다.
  - Auto Layout은 프레임에 적용된다. 일반 레이어 선택에 적용하면 선택을
    둘러싼 Auto Layout 프레임을 만든다.
  - Windows에서 제거 단축키는 `Alt+Shift+A`이며 프레임 자체를 삭제하지 않는다.
- [Guide to auto layout](https://help.figma.com/hc/en-us/articles/360040451373-Explore-auto-layout-properties)
  - Figma는 선택 배치를 보고 Vertical/Horizontal/Grid 흐름을 추정하며 사용자는
    이후 흐름을 바꿀 수 있다.
  - Grid는 별도 흐름이고 M2.1의 Horizontal/Vertical 진입 범위에 포함하지 않는다.
- [FD4B: Auto layout fundamentals](https://help.figma.com/hc/en-us/articles/31351261703063-FD4B-Auto-layout-fundamentals)
  - 선택에 Auto Layout을 적용하면 선택 레이어를 부모 Auto Layout 프레임에 넣는
    기본 구조를 확인한다.

## M2.1 외부 동작

1. 선택 없음: 명령을 실행하지 않고 이유를 반환한다.
2. 일반 레이어 한 개 또는 같은 부모의 형제 레이어 여러 개:
   - 선택 bounds 크기의 투명 `Frame N`을 만든다.
   - 선택 레이어를 그 프레임의 자식으로 옮긴다.
   - 프레임 하나를 선택한다.
3. 프레임 한 개 선택:
   - 새 프레임을 중복 생성하지 않고 선택 프레임에 Auto Layout을 적용한다.
4. 제거:
   - `layout.mode=none`으로 전환한다.
   - 프레임과 자식 hierarchy는 유지한다.
5. 세 진입 표면은 같은 mutation을 호출한다.
   - 캔버스 `Shift+A` / `Alt+Shift+A`
   - 우클릭 `Add auto layout` / `Remove auto layout`
   - Inspector `Add auto layout` / `Remove`
6. 추가 또는 제거 한 번은 Undo 한 단계다.

## Painter 내부 결정 규칙

Figma가 흐름을 "추정한다"는 공개 동작만 문서화하고 정확한 내부 알고리즘은
공개하지 않는다. Painter는 재현 가능한 결과를 위해 다음 규칙을 사용한다.

- 선택 중심점의 X 범위가 Y 범위 이상이면 Horizontal, 아니면 Vertical.
- 흐름 축의 공간 순서로 자식 `z_index`를 정한다.
- 최초 gap은 인접 선택 사이의 음수가 아닌 최소 간격이다.
- 최초 padding은 0, sizing은 Fixed, 정렬은 Start다.
- 서로 다른 artboard, 서로 다른 부모, 부모와 자식을 함께 선택한 경우에는
  구조를 임의로 바꾸지 않고 명시적으로 차단한다.

이 규칙은 Painter의 결정적 내부 매핑이며 Figma 비공개 휴리스틱과 동일하다는
주장이 아니다.

## 구현 위치

- 선택 수준 mutation: `app/painter_ui_auto_layout_entry.py`
- 단축키: `app/painter_ui_workspace.py`
- Inspector 진입 버튼: `app/painter_ui_inspector.py`
- 우클릭/Undo 통합: `app/drawing.py`
- 회귀: `tests/test_painter_ui_auto_layout.py`,
  `tests/test_painter_ui_context_history.py`

## 수용 증거

- 일반 선택을 프레임으로 감싸고 hierarchy/flow/gap/선택을 검증한다.
- 기존 프레임 직접 적용과 제거 후 프레임/자식 보존을 검증한다.
- 두 키보드 단축키가 canonical command를 내는지 검증한다.
- Inspector 버튼과 우클릭 메뉴가 같은 명령에 연결되는지 검증한다.
- Dialog mutation을 Undo 한 번으로 원상 복구하는지 검증한다.

## 다음 순서

`M2.2 Horizontal/Vertical flow 편집`:

- 공식 흐름 전환 UI
- 레이어 추가/제거/재정렬
- 캔버스의 배치 순서 표시
- Inspector와 캔버스가 동일한 document mutation을 사용하는지 검증

Padding, gap, alignment의 세부 조작은 M2.3에서 별도 증거로 닫는다.

## M2.2 Horizontal/Vertical flow 편집 (Complete v1, 2026-08-03)

공식 근거:

- [Use the horizontal and vertical flows in auto layout](https://help.figma.com/hc/en-us/articles/31289464393751-Use-the-horizontal-and-vertical-flows-in-auto-layout)
  - Vertical flow의 자식은 y축, Horizontal flow의 자식은 x축을 따른다.
  - 레이어 추가·제거·재정렬은 해당 축을 따라 일어난다.
  - 자식은 방향키 또는 클릭 드래그로 새 위치로 재정렬할 수 있다.
  - Instance 내부 객체는 재정렬할 수 없으며 main component 변경 또는 detach가 필요하다.
  - Auto Layout 방향은 언제든 Horizontal/Vertical로 전환할 수 있다.
- [Explore auto layout properties](https://help.figma.com/hc/en-us/articles/360040451373-Explore-auto-layout-properties)
  - 방향, gap, padding, alignment는 서로 구분된 속성이다.

구현 계약:

- `app/painter_ui_auto_layout_flow.py`가 부모/자식 eligibility, 축, 형제 순서,
  instance/absolute 차단, 순서 mutation을 단일 계약으로 소유한다.
- 순서 변경은 자식의 임의 X/Y를 쓰지 않는다. 기존 형제 `z_index` 슬롯에 새
  순서를 할당해 Auto Layout resolver와 Layers 순서를 함께 유지한다.
- 캔버스 드래그는 축 중심점을 기준으로 목표 index를 계산하고 파란 삽입선을
  표시한다. mouse release에서 한 번만 canonical mutation/Undo를 수행한다.
- 가로 흐름의 Left/Right와 세로 흐름의 Up/Down은 한 칸 재정렬한다. 흐름의
  직교 방향키는 resolver가 버릴 X/Y를 기록하지 않는다.
- Inspector는 숨겨진 combo를 데이터 source로 유지하되 `→`/`↓` segmented
  buttons로 즉시 방향을 전환한다.
- Instance parent와 `positioning=absolute` 자식은 재정렬하지 않고 명시적 blocker를
  반환한다.

검증:

- `tests/test_painter_ui_auto_layout_flow.py`: 순서/z-slot/X/Y 보존, 경계 no-op,
  instance/absolute 차단, 방향 전환 geometry, 캔버스 drag signal을 검증한다.
- `tests/test_painter_ui_auto_layout.py`: Inspector 방향 버튼과 기존 Auto Layout
  property payload 회귀를 검증한다.

다음 단계는 M2.3 Padding/Gap/Alignment/Wrap 조작의 공식 스크린샷 순서 감사다.

## M2.3 Padding/Gap/Alignment/Wrap (Complete v1, 2026-08-03)

공식 근거:

- [Use the horizontal and vertical flows in auto layout](https://help.figma.com/hc/en-us/articles/31289464393751-Use-the-horizontal-and-vertical-flows-in-auto-layout)
  - 고정 Gap과 가능한 최대 간격을 쓰는 Auto Gap을 구분한다.
  - 고정 Gap에서는 3×3 정렬 위치를 사용한다.
  - Wrap은 Horizontal flow에서만 제공되며 가로/세로 두 Gap을 가진다.
  - Padding은 개별 네 변, 반대편 두 변, 전체 변을 조절할 수 있다.
  - Canvas handle 드래그 중 Shift는 big nudge, Alt는 반대편, Alt+Shift는
    전체 패딩에 적용한다.

구현 결과:

- Inspector는 3×3 alignment control과 Auto Gap 토글을 제공한다.
- Wrap 및 두 번째 Row Gap은 Horizontal+Wrap 문맥에서만 나타난다.
- Vertical로 전환하면 지원하지 않는 Wrap을 끄고 직렬화 payload도 `false`로
  기록한다.
- Canvas Gap은 Horizontal에서 x축, Vertical에서 y축을 따른다.
- Shift big nudge, Alt opposite padding, Alt+Shift all-sides padding이 동일한
  `apply_auto_layout_canvas_drag` 계약을 사용한다.
- 기존 `main_alignment=space_between`을 Auto Gap의 canonical 의미로 사용하므로
  문서 schema와 TigerStudioUMG 계약 변경은 필요하지 않다.

검증은 `tests/test_painter_ui_auto_layout.py`가 축별 Gap, modifier padding,
Wrap disclosure, cross gap, 3×3 alignment, Auto Gap payload를 담당한다.

다음 단계는 M2.4 Fixed/Hug/Fill 및 min/max 크기 정책이다.

## M2.4 Fixed/Hug/Fill 및 min/max (Complete v1, 2026-08-03)

공식 근거는 [Guide to auto layout](https://help.figma.com/hc/en-us/articles/360040451373-Explore-auto-layout-properties)의 Resizing 절이다.

- Fixed는 모든 레이어에 사용할 수 있다.
- Hug contents는 Auto Layout 프레임이 자식과 spacing을 감싸는 최소 크기다.
- Fill container는 Auto Layout 부모의 자식에만 사용할 수 있고 top-level에는
  사용할 수 없다.
- Fill 자식이 있는 축을 부모가 Hug하면 순환 의존이므로 유효하지 않다.
- min/max width/height는 Hug와 Fill의 계산 결과를 제한한다.

구현 결과:

- `PainterUISizingControl`은 Fixed/Hug/Fill 옵션별 enable 상태를 제공한다.
- Inspector는 Auto Layout container에만 Hug, in-flow child에만 Fill을 허용하며
  Absolute child와 top-level의 Fill을 차단한다.
- 여러 Fill 자식이 min/max에 걸리면 `resolve_ui_auto_layout`이 제한된 자식을
  먼저 확정하고 남은 공간을 다른 Fill 자식에 반복 재분배한다.
- 기존 layout diagnostics의 Hug↔Fill cycle, min>max, fixed overflow 경고를
  같은 계약으로 유지한다.

다음 단계는 M2.5 Grid Auto Layout과 TigerStudioUMG Grid 변환이다.
