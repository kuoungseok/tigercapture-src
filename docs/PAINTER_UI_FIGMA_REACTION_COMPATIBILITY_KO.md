# Painter UI Figma Reaction 호환성

## 목표

Figma REST 및 REST archive의 `reactions`/`interactions`를 가져올 때 원본
반응과 액션 슬롯을 하나도 조용히 버리지 않는다. 지원되는 의미는 Painter
Interaction으로 변환하고, 변환할 수 없는 의미는 원본 JSON을 포함한 복구
레코드와 명시적 Figma/UMG blocker로 남긴다.

다음 보존식은 import report와 public corpus QA에서 강제한다.

```text
source reaction = fully native reaction + recovery reaction
source action slot = native action + recovered blocked action slot
```

빈 `actions: []`는 액션 슬롯 수가 0이지만 reaction recovery에는
`figma_reaction_has_no_actions`로 남는다.

## Native 변환

주요 trigger 매핑은 다음과 같다.

- `ON_CLICK` -> `click`
- `ON_HOVER` -> `hover`
- `MOUSE_ENTER` / `MOUSE_LEAVE` -> `mouse_enter` / `mouse_leave`
- `MOUSE_DOWN` / `ON_PRESS` -> `press`
- `ON_DRAG` -> `drag`
- `ON_KEY_DOWN` -> `keyboard`
- `AFTER_TIMEOUT` -> `delay`

`NODE` action의 `NAVIGATE`, `OVERLAY`, `SWAP`, `CHANGE_TO`, `SCROLL_TO`는
각각 `navigate`, `open_overlay`, `swap_overlay`, `change_variant`,
`scroll_to`로 변환한다. `BACK`, `CLOSE`도 Painter의 대응 action으로
변환한다. `SCROLL_TO`는 object 목적지가 실제로 해석될 때만 Native다.

Native Interaction의 `parameters.figma_reaction`에는 source 종류와 ID,
reaction/action index, `raw_reaction`, `raw_trigger`, `raw_action`을 보존한다.
따라서 JSON 저장과 Figma plugin exchange를 거쳐도 원본 trigger/action
필드를 복구할 수 있다.

Figma plugin export는 같은 source의 여러 reaction과 같은 reaction의 여러
action을 모아 `setReactionsAsync`를 source당 한 번 호출한다. 원본 trigger와
action을 우선 사용하고 생성된 목적지 node ID만 치환한다. source/target 누락,
지원하지 않는 trigger/action, Plugin API 실패는 더 이상 무시하지 않고 ID가
포함된 오류로 중단한다.

## Lossless recovery와 blocker

변환하지 못한 reaction은 `linked_targets.figma.reaction_recovery`에 저장한다.
각 레코드는 다음 정보를 가진다.

- source object/artboard/Figma node ID와 artboard ID
- reaction index, 상태(`blocked` 또는 `partial`), reason 목록
- Native로 변환된 action index
- 차단된 action별 index, type, navigation, destination, reason, raw action
- 원본 `raw_reaction`

대표 reason은 다음과 같다.

- `figma_reaction_artboard_source_unsupported`
- `figma_reaction_trigger_unsupported`
- `figma_reaction_action_malformed`
- `figma_reaction_has_no_actions`
- `figma_scroll_to_missing_destination`
- `figma_reaction_destination_unresolved`
- `figma_prototype_url_action_requires_runtime_policy`

각 recovery 레코드는 Figma compatibility에서 한 개의 `blocked` row가 되고,
선택 artboard의 TigerStudioUMG `PainterSource.FigmaReactionRecovery`에도
전달된다. UMG preflight 역시 recovery 레코드마다 blocker를 만든다.

현재 TigerStudioUMG runtime이 실행하지 않는 navigation, overlay,
`SCROLL_TO`, `CHANGE_TO`는 문서에서 누락하지 않고 Interaction으로 직렬화한
뒤 각각 screen router, overlay runtime, ScrollBox binding, variant runtime
blocker로 보고한다. Painter의 click/hover/enter/leave/press trigger는 UMG의
`clicked`/`hovered`/`unhovered`/`pressed` event 이름으로 변환한다.

## 실제 corpus 증거

2026-08-05 고정 public corpus 결과는 다음과 같다.

- fast 20 cases: source reaction/action 18/18 = Native 15/15 + recovery 3/3
- nightly 4 cases: source reaction/action 1/1 = Native 0/0 + recovery 1/1
- 합계: source reaction/action 19/19 = Native 15/15 + recovery 4/4

Fast corpus의 top-level `INSTANCE` 화면도 artboard로 가져오므로 해당 화면의
expanded descendant reaction이 더 이상 import 범위 밖에서 사라지지 않는다.
Nightly archive의 URL action은 raw JSON과 전용 runtime-policy blocker로
보존된다.

재현 보고서:

```text
debugCapture/painter_ui_figma_m3_reactions_fast20/report.json
debugCapture/painter_ui_figma_m3_reactions_nightly4/report.json
```

핵심 회귀 테스트:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\test_painter_ui_figma.py `
  tests\test_painter_ui_figma_document_corpus.py `
  tests\test_unreal_umg_layout.py -q
```
