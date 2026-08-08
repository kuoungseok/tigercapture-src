# Painter UI Auto Layout → UMG 변환 계약

## Schema v10 native ScrollBox update (2026-08-03)

- Painter document v29의 Horizontal, Vertical, Both overflow를 provider-neutral
  `ScrollOverflow`로 기록하고 TigerStudioUMG v0.9.0/schema v10이 실제
  `UScrollBox`로 생성한다.
- Both는 Vertical과 Horizontal `UScrollBox`를 중첩한다.
- Scroll Frame은 `UOverlay` 아래에 ScrollBox와 Fixed `UCanvasPanel`을 함께 두어
  `ScrollPosition=Fixed` 자식을 스크롤 콘텐츠와 분리한다.
- Sticky는 프레임별 런타임 스크롤 위치 바인딩이 필요하므로
  `prototype_sticky_requires_umg_runtime_binding` blocker로 유지한다.
- UE 5.8 실제 QA에서 Both ScrollBox, Overlay, Fixed Canvas를 생성·컴파일·재로드했다.

## Schema v9 Grid update (2026-08-03)

- Shared plugin version: `0.8.0`; provider-neutral document schema: `9`.
- Grid Auto Layout maps to native `UGridPanel`.
- Child Row/Column/RowSpan/ColumnSpan map to native `UGridSlot`.
- UE 5.8 Editor/Development/Shipping build and source-free bundle generation pass.
- Real QA generates, compiles, reopens, and captures a Widget Blueprint containing
  both `HorizontalBox` and `GridPanel`; the Grid sample includes a two-column span.
- Evidence: `debugCapture/painter_ui_designer/unreal_umg/qa_report.json`.

현재 상태: `Tiger UMG schema v10 / plugin 0.9.0`

Schema v10 실증은 UE 5.8 Editor/Development/Shipping 빌드와 source-free bundle,
17-widget Widget Blueprint 생성·컴파일·재로드를 통과했다. 생성 클래스 맵에서
scroll Frame은 `Overlay`, `#scroll`과 `#scroll_horizontal`은 `ScrollBox`,
`#fixed`는 `CanvasPanel`로 확인되며 shader compile error는 0이다.

Painter의 Auto Layout과 Unreal UMG 변환은 서로 다른 단계다. Painter 문서는
편집 의미를 보존하고, `app/painter_ui_umg_auto_layout.py`가 UMG에 전달 가능한
부분만 별도 계약으로 분류한다. Painter 전용 Unreal 플러그인은 만들지 않으며
공용 `TigerStudioUMG`만 사용한다.

## 네이티브 변환

- Auto Layout이 없는 Frame/Group → `UCanvasPanel`
- Horizontal Auto Layout → `UHorizontalBox`
- Vertical Auto Layout → `UVerticalBox`
- Grid Auto Layout → `UGridPanel`
- Horizontal/Vertical overflow → 해당 축 `UScrollBox`
- Both overflow → 중첩 Vertical/Horizontal `UScrollBox`
- Fixed child → Scroll Frame의 고정 `UCanvasPanel`
- 부모 padding과 gap → 각 자식 Box Slot의 `Padding`
- 교차축 Start/Center/End/Stretch → Box Slot 정렬
- 자식 주축 Fixed/Hug → `Auto`, Fill → `Fill`
- 자식의 고정 W/H → 내부 `USizeBox` 크기

Tiger UMG schema v7은 레이어마다 `PanelKind`와 `FlowSlot`을 기록한다. 이
레코드는 Motion Designer와 Painter가 함께 쓰는 provider-neutral 계약이다.

## 명시적 차단

현재 네이티브 의미가 일치하지 않는 항목은 변환 중 생략하지 않는다.

- Wrap → `auto_layout_wrap_requires_umg_wrap_panel`
- 주축 Center/End/Space Between →
  `auto_layout_main_alignment_unsupported:<alignment>`
- 흐름 안의 Absolute 자식 →
  `auto_layout_absolute_child_unsupported:<object_id>`

위 항목은 전용 Wrap/Spacer/Overlay 변환 또는 결정적 bake가 추가되기 전까지
프리플라이트에서 `Blocked`다.

Rounded Card v2 머터리얼은 현재 고정 크기 레이어만 지원한다. Stretch/Scale
앵커 또는 Horizontal/Vertical/Grid 흐름이 런타임 크기를 배정하는 경우에는
`rounded_card_runtime_resize_requires_dynamic_size_binding`으로 차단한다. 고정
`CardSize`를 조용히 늘려 코너와 그림자 두께를 왜곡하지 않기 위한 경계다.

## 검증 기준

- Python 계약 및 회귀 테스트:
  `tests/test_painter_ui_umg_auto_layout.py`
- 공용 플러그인 정적 계약:
  `tests/test_unreal_umg_plugin.py`
- 실제 UE 5.8 빌드:
  `tools/build_unreal_umg_plugin.py`
- 실제 Widget Blueprint 생성·재오픈 및 `HorizontalBox` 클래스 확인:
  `tools/qa_painter_ui_unreal_umg.py`

## Schema v7 도입 당시 UE 5.8 증거

- 공용 플러그인 `0.6.1`의 Editor/Development/Shipping 빌드 성공
- source-free Win64 bundle 재생성 성공
- Painter QA 문서에서 11개 위젯 생성, Widget Blueprint load/reopen 성공
- 생성 클래스 맵에서 Auto Layout 레이어 `ui-object-1`이 실제
  `HorizontalBox`로 기록됨
- 같은 맵에서 일반 프레임은 `CanvasPanel`, 자식은
  `TigerStudioButton`으로 기록됨
- 재현 가능한 임시 보고서:
  `debugCapture/painter_ui_designer/unreal_umg/qa_report.json`

`debugCapture` 보고서는 폐기 가능한 증거이며, 제품 계약과 테스트는 이 문서,
소스, 테스트에 남는다.

## Schema v8 Rounded Card / 현재 v9 통합 증거

- 공용 플러그인 `0.8.0`의 UE 5.8 Editor/Development/Shipping 빌드 성공
- source-free Win64 bundle 재생성 성공
- schema v9 Painter QA에서 `Native 13 / Material 1 / Blocked 0`, 총 14개
  논리 위젯 생성 및 Widget Blueprint compile/save/reopen 성공
- Rounded Card는 stable `CanvasPanel` host와 `_Visual` `UImage` 자식으로 생성
- 생성된 `MD_UI` Material에서 단일 `MaterialExpressionCustom` 확인
- 재오픈한 Widget Blueprint package의 Material 직렬화 참조 확인
- 에디터 캡처 로그에서 해당 Material shader compile 오류 0건
- 재현 가능한 임시 보고서와 화면:
  `debugCapture/painter_ui_designer/unreal_umg/qa_report.json`,
  `debugCapture/painter_ui_designer/unreal_umg/painter_umg_unreal_editor.png`

이 문서는 Auto Layout 전체 호환을 주장하지 않는다. 위 네이티브 범위와
차단 범위를 합친 것이 현재의 정확한 UMG 전달 범위다.
