# Painter UI 개인용 Figma Design 90% 대체 마일스톤

상태: `Active / 계획 기준선`  
대상: AI, Community, 실시간 협업, 클라우드 권한·브랜치를 제외한 1인 UI 디자인 작업

## 1. 목표

이 로드맵의 90%는 Figma의 메뉴 개수나 내부 API 개수를 뜻하지 않는다. 사용자가
앱·웹·게임 UI 문서를 만들고, 저장하고, 다시 열고, 수정하고, 프로토타입으로 확인한
뒤 SVG·PNG·Tiger UMG로 전달하는 일반적인 1인 작업의 90%를 뜻한다.

다음은 완료로 계산하지 않는다.

- 버튼, Inspector 행 또는 직렬화 필드만 존재하는 상태
- 작은 단위 예제만 통과하고 중첩 조합이 깨지는 상태
- 저장 후 참조 또는 화면 결과가 달라지는 상태
- 지원하지 않는 속성을 경고 없이 버리는 상태
- 자동화 테스트만 있고 실제 Painter UI 캡처가 없는 상태

## 2. 고정 제품 검증 문서

모든 마일스톤은 아래 문서를 같은 데이터로 계속 확장한다. 마일스톤마다 편한 새
샘플을 만드는 방식은 금지한다.

1. `Mobile Checkout`: 상품 목록, 상세, 장바구니, 결제 완료, overlay
2. `Responsive Landing`: desktop/tablet/mobile, 중첩 Auto Layout, 이미지와 SVG
3. `Desktop Dashboard`: 3,000개 이상의 Layer, table, chart, scroll container
4. `Design System`: Button/Input/Card/Nav의 Component Set, Variant, property, token
5. `Interactive Prototype`: overlay, scroll, variable, conditional, Smart Animate
6. `Scale Corpus`: 1천/5천/1만 Layer와 깊이 20 이상의 중첩 문서

각 문서는 light/dark, 100%/150% DPI, 저장 전/재실행 후 결과를 보관한다.

## 3. 공통 완료 Gate

모든 마일스톤은 다음을 모두 만족해야 `Complete`다.

1. 공식 Figma 문서 또는 실제 제품 증거로 동작 계약을 기록한다.
2. Canvas, Layers, Inspector가 하나의 선택과 mutation 결과를 표시한다.
3. 모든 변경이 동일한 Undo/Redo command 경로를 사용한다.
4. 저장 → 프로세스 종료 → 재실행 → 재저장 round-trip을 통과한다.
5. 지원하지 않는 조합은 안정된 reason code와 사용자 메시지로 차단한다.
6. 단위·통합·실제 Qt pointer task test와 제품 캡처를 남긴다.
7. 관련 TigerStudioUMG 속성은 Native/Material/Bake/Blocked 중 하나로 판정한다.
8. 이전 고정 검증 문서에 회귀가 없다.

## 4. 90% 필수 구간

### S0. 측정 기준선과 재현 가능한 Corpus

상태: `Pending`

- 여섯 고정 문서의 seed, 예상 hierarchy, reference render를 버전 관리한다.
- 문서 semantic hash, render diff, frame timing, peak memory, command history를
  동일한 runner에서 측정한다.
- 정상/compact/150% DPI와 light/dark 캡처 규격을 고정한다.
- 기능별 `Supported / Partial / Blocked` capability manifest를 생성한다.

완료 Gate:

- 깨진 seed를 자동으로 검출하고 모든 후속 마일스톤이 같은 corpus를 사용한다.
- 측정 머신, viewport, font, DPI, color profile을 evidence manifest에 기록한다.

### S1. 결정론적 저장·재실행·참조 보존

상태: `Pending`

- Page, Frame, Section, Layer hierarchy와 stable object ID를 보존한다.
- Component/Instance/Variant, Variable alias, Style, prototype target, asset 참조를
  ID 기반으로 복원한다.
- 같은 문서를 반복 저장해도 의미 없는 diff가 생기지 않게 canonicalize한다.
- schema migration, missing font/image/library 진단과 복구 UI를 제공한다.
- Undo history는 정상 종료 시 선택적으로 복원하고, 복원 불가능한 command는
  history boundary를 명시한다.

완료 Gate:

- 고정 문서 각각 100회 round-trip에서 semantic hash와 참조 graph가 동일하다.
- 저장 전/재실행 후 geometry와 style render diff가 허용 오차 안에 있다.
- 손상 파일을 부분 로드해 조용히 덮어쓰지 않고 recovery copy를 만든다.

### S2. 중첩 Auto Layout × Component × Variant × Override

상태: `Pending`

- Horizontal/Vertical/Wrap/Grid, Fixed/Hug/Fill, min/max, absolute child를 중첩한다.
- Component Set의 다차원 Variant와 Boolean/Text/Instance Swap/Slot property를
  지원한다.
- nested Instance의 override 보존, reset, detach, Change-to, main update 전파를
  하나의 reference/override resolver로 처리한다.
- reparent, reorder, duplicate, paste, delete 후 dangling reference를 제거한다.

필수 조합 Matrix:

- Auto Layout 깊이 1/5/10 × Instance 깊이 1/5/10
- Variant 1/2/4차원 × local/nested override × light/dark mode
- Slot 비움/삽입/교체 × Change-to × Undo/Redo × 저장 round-trip

완료 Gate:

- Design System 문서의 모든 상태와 override 조합을 한 Instance 흐름으로 실행한다.
- 지원 조합은 값 손실이 없고, 불가능한 cycle·소유권 위반은 명시적으로 차단한다.

### S3. 실무 텍스트 조판과 혼합 스타일

상태: `Pending`

- auto width/height/fixed box, overflow, truncate, paragraph spacing과 baseline을
  동일한 shaping/layout 결과로 계산한다.
- range별 font family/style/size/color/decoration/link와 mixed Inspector 상태를
  보존한다.
- 한글·영문·숫자·이모지·CJK 혼합, fallback chain, missing glyph 표시를 지원한다.
- font load/substitution 결과를 저장하고 export/UMG preflight에 노출한다.

완료 Gate:

- 고정 문자열 corpus의 line break, glyph bounds, baseline이 reference 허용 오차를
  통과한다.
- 글꼴 누락 시 자동으로 조용히 바꾸지 않고 대체 글꼴과 영향 범위를 표시한다.
- mixed range 편집 → Undo → 재실행 후 range boundary와 속성이 동일하다.

### S4. 벡터·마스크·외형 정확성

상태: `Pending`

- vector network의 node/segment/handle, open/close/join/split, winding을 보존한다.
- Boolean, Flatten, Outline Stroke, mask/clip의 비파괴 원본과 결과를 관리한다.
- multiple fill/stroke, gradient, stroke align/cap/join/dash, independent corner,
  shadow/blur/blend를 공용 appearance stack으로 통합한다.
- SVG path/transform/viewBox/clipPath/mask/gradient/use/text 처리 범위를 명시한다.

완료 Gate:

- 복합 SVG corpus를 import → edit → export → reimport해 geometry graph를 보존한다.
- 미지원 filter, text shaping 또는 paint server를 누락하지 않고 preflight한다.
- mask/Boolean/appearance 순서 변경과 Undo/Redo가 render와 hierarchy에서 일치한다.

### S5. 고급 Prototype와 Smart Animate

상태: `Pending`

- click/hover/press/drag/key/delay trigger와 navigate/back/overlay/scroll/variable
  action을 순서대로 실행한다.
- 조건식, 여러 action, interactive Component, scroll position, overlay lifecycle을
  같은 runtime state machine으로 처리한다.
- Smart Animate는 stable identity, hierarchy, transform, opacity, corner, fill과
  지원 가능한 vector property를 매칭한다.
- 매칭 불가 속성은 dissolve 등으로 조용히 바꾸지 않고 fallback report를 남긴다.

완료 Gate:

- Mobile Checkout과 Interactive Prototype을 편집기 Preview와 export Preview에서
  같은 입력 replay로 실행해 동일한 state trace를 얻는다.
- 중간 프레임 캡처와 최종 상태의 시각 diff가 허용 오차를 통과한다.

### S6. SVG·PNG·UMG 전달 정확성

상태: `Pending`

- PNG/SVG export의 frame bounds, scale, transparency, color와 clipping을 고정한다.
- SVG는 편집 가능한 구조와 flatten/bake 결과를 구분한다.
- TigerStudioUMG 변환은 모든 속성을 Native/Material/Bake/Blocked로 분류한다.
- Blocked 속성, missing asset/font와 예상 시각 차이를 export 전에 보고한다.

완료 Gate:

- 고정 문서의 PNG reference diff를 정해진 threshold로 자동 판정한다.
- SVG round-trip 결과와 Painter render가 geometry/style 허용 오차를 통과한다.
- 지원 주장마다 실제 UE 5.8 Widget Blueprint compile과 capture가 존재한다.
- 결과가 다르면 성공 파일을 내보내며 경고만 하지 않고 명시적으로 차단한다.

### S7. 5천~1만 Layer 성능과 메모리

상태: `Pending`

- viewport culling, spatial index, incremental layout, geometry/style cache를 적용한다.
- Layers와 Inspector를 virtualization하고 selection 변경 시 전체 문서를 다시
  계산하지 않는다.
- asset decode와 thumbnail 생성은 UI thread를 막지 않는다.
- 성능 측정은 warm/cold 상태와 1천/5천/1만 Layer를 분리한다.

초기 성능 Budget:

- 1만 Layer pan/zoom frame time p95 `<= 33 ms`
- hit test p95 `<= 50 ms`, 선택 후 Inspector 갱신 p95 `<= 100 ms`
- 1만 Layer 저장과 열기 각각 `<= 10 s`
- corpus peak working set `<= 2 GB`

완료 Gate:

- 측정 머신에서 10분 연속 pan/zoom/select 동안 budget을 유지한다.
- cache 비활성 기준 결과와 geometry/render가 동일하다.
- budget을 넘기면 release report가 실패하고 느린 구간 trace를 저장한다.

### S8. 자동 저장·충돌 복구·장시간 Undo 안정성

상태: `Pending`

- atomic save, journal, autosave generation, clean shutdown marker를 사용한다.
- crash 후 원본/자동 저장본/복구본을 구분하고 사용자가 선택할 수 있게 한다.
- Undo command coalescing, memory budget, history checkpoint와 asset lifetime을
  명시한다.
- background 작업 완료 순서가 Undo 이후 문서를 되살리지 못하게 generation을
  검증한다.

완료 Gate:

- autosave RPO는 기본 설정에서 `<= 30초`이며 원본을 자동 덮어쓰지 않는다.
- 저장·asset load·prototype 실행 도중 강제 종료 fault injection을 모두 복구한다.
- 4시간/5천 command replay 뒤 semantic hash, render, reference graph가 기준과 같다.
- Undo/Redo 전체 왕복 후 시작/종료 상태가 각각 정확히 복원된다.

### S9. 개인용 Figma Design 90% Release Gate

상태: `Pending`

- 다섯 실제 작업 문서를 빈 파일에서 제작하고 수정 요청까지 완료한다.
- 모든 문서를 저장·종료·재실행한 뒤 Prototype과 export를 다시 검증한다.
- 신규 사용자가 문서 안내 없이 핵심 task를 수행하는 task-completion QA를 한다.
- P0 데이터 손실·crash·silent omission은 0건이어야 한다.

90% 판정:

- S0~S8이 모두 Complete이고 고정 문서의 필수 task가 90% 이상 통과한다.
- capability manifest의 일반 작업 필수 항목이 `Supported`이며 `Partial` 항목은
  결과 차이와 우회 방법이 표시된다.
- 이 Gate 전에는 제품 UI나 문서에서 “Figma 90% 호환”을 주장하지 않는다.

## 5. 마지막 10~15% 확장 구간

### X1. 고급 Typography

상태: `Pending after S9`

- variable font axis, OpenType feature, bidi/RTL, vertical text, locale line break,
  complex script shaping과 font embedding 정책을 완성한다.
- 플랫폼별 raster 차이와 layout 차이를 분리해 검사한다.

### X2. 고급 Vector와 복합 Effect

상태: `Pending after S9`

- 고급 vector network 교차, variable stroke, 복잡한 dash/outline, compound mask,
  filter graph와 blend isolation을 지원한다.
- GPU/CPU/UMG 경로의 허용 오차와 deterministic bake를 검증한다.

### X3. 대규모 Variables·Design System 운영

상태: `Pending after S9`

- 수천 token, alias graph, 여러 collection/mode, package update/relink/rollback과
  breaking-change diff를 처리한다.
- 대규모 Component library의 검색, swap, deprecation, migration을 제공한다.

### X4. Dev 전달·코드 생성·접근성·플랫폼 Matrix

상태: `Pending after S9`

- 측정, token, interaction, asset, generated code의 원본 추적성을 제공한다.
- keyboard-only, screen reader, contrast/focus audit를 완료한다.
- Windows 정상/compact/100%/150%/200% DPI와 지원 플랫폼의 입력·렌더 차이를
  release matrix로 관리한다.

### X5. Figma 원본 상호 호환성

상태: `Research / native .fig guarantee blocked`

- 공개 Figma Plugin API와 명시적인 exchange package를 우선 사용한다.
- import/export마다 보존·근사·bake·blocked 속성을 machine-readable report로
  제공한다.
- 비공개 native `.fig` 형식의 완전한 읽기/쓰기는 공식 계약이나 안정된 공개
  specification 없이는 지원한다고 주장하지 않는다.
- 실제 Figma Desktop round-trip corpus로 지원 가능한 부분 호환 등급을 측정한다.

## 6. 고정 실행 순서

`S0 → S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9` 순서로 진행한다.

S9 이후에는 제품 요구에 따라 `X1~X4`를 병렬화할 수 있지만, X5는 별도의 호환성
트랙으로 유지한다. 상위 기능을 먼저 구현해야 하더라도 선행 Gate의 데이터 보존,
Undo, 실제 제품 캡처가 닫히기 전에는 완료 상태를 올리지 않는다.

## 7. 현재 구현의 편입 원칙

기존 M1 Core Authoring과 M2 Auto Layout의 `Complete v1` 구현은 버리지 않는다.
각 구현을 이 문서의 고정 corpus와 조합 Matrix에 다시 통과시킨다. 기존 Action,
backend contract 또는 단위 테스트가 있다는 사실은 시작점이며 S 단계 완료 증거는
아니다.
