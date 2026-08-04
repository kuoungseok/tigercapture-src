# Painter UI 제품 완성 마일스톤

Status: canonical product-execution gates

기준일: 2026-08-03

이 문서는 Painter UI를 Figma의 외형만 닮은 편집기가 아니라 실제 문서를
끝까지 만들 수 있는 제품으로 완성하기 위한 실행 순서다. 기존
`PAINTER_UI_DESIGNER_MILESTONES_KO.md`의 `implemented` 표시는 코드와 Action
기반이 존재한다는 뜻으로만 해석한다. 실제 UI 완료 판정은 이 문서의
작업 시나리오와 증거 Gate를 통과해야 한다.

## 1. 상태와 완료 판정

모든 항목은 다음 상태만 사용한다.

- `B0 발견`: 코드·UI·문서에 흔적이 있으나 실제 작업 검증 전
- `B1 연결`: UI 입력, 문서 mutation, Undo, Inspector가 연결됨
- `B2 검증`: 자동화 테스트와 저장·열기 왕복 통과
- `B3 작업 통과`: 기준 샘플을 처음부터 끝까지 만들고 시각 증거 통과
- `완료`: B3 증거가 저장되고 P0 회귀가 없음

`B1` 또는 단위 테스트만으로 “완료”라고 말하지 않는다.

## 2. 모든 마일스톤에 적용하는 공통 Gate

각 마일스톤은 아래 조건을 모두 만족해야 다음 단계로 넘어간다.

1. UI와 `paint.ui.*` Action이 같은 문서 mutation 서비스를 사용한다.
2. 생성·편집·삭제가 한 단계 Undo/Redo로 정확히 왕복한다.
3. `.tspaint` 저장·열기 후 ID, hierarchy, geometry, style이 동일하다.
4. 1440×900 및 1920×1080 화면에서 컨트롤 겹침·잘림이 없다.
5. Light/Dark UI에서 캔버스 결과와 선택 표시 의미가 같다.
6. 실제 창 스크린샷을 `debugCapture` 증거로 만들되 제품 의존 파일로 쓰지
   않는다.
7. 입력 중 p95 캔버스 갱신은 33 ms 이하를 목표로 하고, 100개 객체 기준
   100 ms 이상의 UI 멈춤이 반복되지 않는다.
8. 관련 단위/통합 테스트와 `tests/test_editor_architecture_rules.py`가
   통과한다.
9. 알려진 누락은 UI에서 `미지원` 또는 `Blocked`로 보이며 조용히 생략하지
   않는다.
10. 재현 절차, 기대 결과, 실제 결과, 증거 파일을 마일스톤 기록에 남긴다.

## 3. 고정 기준 문서 세트

모든 Gate는 서로 다른 임시 예제가 아니라 아래 세 문서를 누적 제작하며
검증한다.

### A. Mobile Checkout

- 3개 화면: 상품, 장바구니, 결제 완료
- 모바일 Frame, 이미지, 텍스트, 버튼, 카드, 아이콘
- Auto Layout, 스크롤, 컴포넌트 상태, Prototype 연결

### B. Desktop Dashboard

- Sidebar, Header, Card grid, Table, Chart placeholder
- 1440 desktop와 1024 tablet 반응형
- 중첩 Frame, Constraints, Grid/Auto Layout, mixed selection

### C. Design System Playground

- 색상·타이포·간격·반경 토큰
- Button/Input/Card 컴포넌트
- Normal/Hover/Pressed/Disabled 및 Size variants
- Instance override와 library update 검토

각 마일스톤은 이 세 문서 중 지정된 결과를 실제로 만들어야 한다.

## M0. 기준선과 검증 장치 고정

목적: 이후 작업이 다시 주먹구구가 되지 않도록 동일한 검사 환경을 만든다.

범위:

- 위 세 문서의 빈 fixture와 기대 결과 manifest
- 실제 Painter 창의 자동 캡처 경로
- Light/Dark, 100%/50%, normal/focus mode 캡처 조합
- 입력 지연, paint 시간, object count 측정
- 저장·열기·Undo·Action parity 공통 검사 도우미

완료 시나리오:

1. 빈 Mobile Checkout 문서를 연다.
2. Frame 하나를 만들고 저장·닫기·다시 열기 한다.
3. 같은 ID와 geometry가 복원되고 기준 캡처가 생성된다.

증거:

- fixture 3개
- smoke test 1개
- Light/Dark 캡처 각 1장
- 성능 baseline JSON

## M1. 선택·변형·레이어 조작

목적: 모든 후속 제작 기능이 의존하는 편집 핵심을 안정화한다.

범위:

- 클릭, Shift 다중 선택, marquee, Ctrl deep select
- parent 우선 선택, double-click/Enter child 진입, Esc parent/해제
- 이동, 8방향 resize, 중심/비율 resize, 회전, Scale
- Smart Guide: edge, center, baseline, equal gap
- 정렬, 분배, Tidy up/Smart selection
- 복사, 붙여넣기, duplicate, delete
- Group/Frame hierarchy, reparent, layer reorder
- 잠금·숨김·이름 변경과 우클릭 Select layer 메뉴

완료 시나리오:

1. Desktop Dashboard에 12개 객체를 만들고 3단계 hierarchy로 정리한다.
2. marquee와 deep select로 정확한 객체를 선택한다.
3. 정렬·분배 후 그룹 이동과 layer reparent를 수행한다.
4. Undo로 모든 단계를 역순 복원하고 Redo로 재적용한다.

완료 기준:

- 캔버스와 레이어 선택이 항상 동일한 object ID를 가리킨다.
- Frame 이동 시 자식이 이중 이동하지 않는다.
- locked/hidden 객체의 hit test 규칙이 Figma 규칙과 일치한다.
- 100개 객체 이동·marquee에서 반복 멈춤이 없다.

## M2. Frame·도형·벡터 직접 조작

목적: 화면과 기본 그래픽을 캔버스에서 끊김 없이 만든다.

범위:

- Frame preset/자유 생성, Section, Slice
- Rectangle, Ellipse/Arc/Ring, Polygon, Star, Line, Arrow
- 드래그 중 실제 shape preview
- Radius, point count, inner radius, smoothing, arc sweep/ratio gizmo
- Pen node/segment/handle 편집, Pencil smoothing
- Boolean, Mask, Flatten/Outline의 명시적 결과
- 생성 직후 새 도형을 만들기 전까지 선택·gizmo 조작 가능

완료 시나리오:

1. Mobile Checkout의 세 Frame을 preset과 자유 Frame으로 만든다.
2. 카드, 아이콘, 별 배지, 원형 진행 표시를 gizmo만으로 만든다.
3. Line/Arrow로 연결 표식을 만들고 Boolean 아이콘 하나를 완성한다.

완료 기준:

- Frame에는 shape 전용 gizmo가 나타나지 않는다.
- 도형은 생성 중 preview와 생성 후 결과가 동일하다.
- 도형이 Frame 내부에 생성되며 hierarchy가 즉시 레이어에 나타난다.
- Inspector 수치와 캔버스 gizmo가 양방향 동기화된다.

## M3. 외형·텍스트·이미지

목적: 회색 박스가 아니라 완성된 정적 UI 화면을 만든다.

범위:

- 공용 Fill picker: solid, gradient, image, video, pattern
- Stroke 위치·두께·dash, opacity, blend, radius, effects
- 공용 컨트롤의 Figma형 slider/input/swatch 품질
- Text Auto width/height/fixed, font/weight/size/line/letter spacing
- inline text edit, mixed text, overflow, alignment
- Image Fit/Fill/Crop/Tile, focal point, exposure/contrast/saturation 등
- Style 생성·적용·분리

완료 시나리오:

1. Mobile Checkout 상품 화면을 이미지와 실제 문구로 완성한다.
2. Card에 gradient, border, radius, shadow를 적용한다.
3. Text와 Image를 교체하고 저장·열기 후 픽셀 결과를 비교한다.

완료 기준:

- 선택 타입에 맞는 Inspector만 보이고 다른 타입 필드는 보이지 않는다.
- 색상 swatch와 색상 값 어느 쪽을 눌러도 같은 picker가 열린다.
- 100% zoom 캡처에서 reference와 control density가 현저히 다르지 않다.

## M4. Auto Layout·Constraints·반응형

목적: 고정 좌표 그림을 유지 가능한 UI 구조로 바꾼다.

범위:

- Shift+A로 선택을 Auto Layout Frame으로 변환
- horizontal, vertical, wrap, grid
- padding, gap, alignment의 캔버스 handle과 Inspector
- Hug, Fill, Fixed, min/max, aspect ratio
- absolute child와 z-order
- Constraints와 layout guide/safe area
- desktop/tablet/mobile resize preview

완료 시나리오:

1. 텍스트 길이에 따라 늘어나는 Button을 만든다.
2. Dashboard card grid를 1440→1024로 줄인다.
3. Mobile Checkout 목록에 항목을 추가·삭제하고 자동 reflow를 확인한다.

완료 기준:

- content 변경 후 수동 위치 보정이 필요 없다.
- canvas handle과 Inspector 값이 동일한 layout 결과를 만든다.
- 저장·열기와 Action 실행 결과가 결정론적이다.

## M5. 컴포넌트·Variants·토큰·Assets

목적: 화면 복사가 아니라 재사용 가능한 디자인 시스템을 만든다.

범위:

- selection→Component, Instance 생성, main component 이동
- nested instance와 text/image/boolean/instance-swap property
- Component set과 Variant property/value
- Normal/Hover/Pressed/Focused/Disabled 상태
- local styles와 variable collection/mode/alias
- Assets 검색·삽입·instance swap
- 원본 변경 영향 미리보기, detach/localize

완료 시나리오:

1. Design System Playground에서 Button/Input/Card를 만든다.
2. Mobile과 Desktop 문서에 Instance를 배치한다.
3. 토큰과 main component를 변경해 모든 Instance를 갱신한다.

완료 기준:

- Instance override가 hierarchy를 탐색하지 않고 Inspector 첫 영역에 보인다.
- Variant 전환이 override를 보존한다.
- Assets 삽입 결과가 저장·열기·handoff에서 같은 component identity를 가진다.

## M6. Prototype·댓글·검토

목적: 제작된 화면을 실제 흐름으로 검토할 수 있게 한다.

범위:

- click/hover/press/focus/keyboard trigger
- navigate/back/overlay/scroll/change-to
- interactive component와 transition
- Presentation/Preview의 실제 frame 재생
- 댓글 핀·영역·답글·이동·해결·검색
- revision checkpoint와 diff

완료 시나리오:

1. Mobile Checkout 세 화면을 버튼으로 연결한다.
2. Hover/Pressed Button variant를 Preview에서 재생한다.
3. 객체 댓글과 영역 댓글을 남기고 객체 이동 후 anchor를 확인한다.

완료 기준:

- 편집기 없이 review artifact에서 전체 흐름을 재생한다.
- 댓글 모드는 객체 geometry를 변경하지 않는다.
- Prototype과 Motion 연결 실패가 명시적 fallback/Blocked로 보인다.

## M7. 전달·교환·성능·출시 Gate

목적: Painter 내부 데모가 아니라 외부 제작 파이프라인에 전달한다.

범위:

- PNG/WebP/SVG slice와 density
- Figma Plugin package import/export round trip
- HTML prototype와 developer inspect
- shared TigerStudioUMG preflight/generation
- font/image/license/hash manifest
- 1,000 object 문서 성능과 오류 복구
- 접근성, keyboard, 한국어/영어 clipping audit

완료 시나리오:

1. 기준 문서 세 개를 모든 지원 target으로 preflight한다.
2. 지원 경로는 실제 artifact를 생성·재열기 한다.
3. 미지원 경로는 이유와 대안을 표시한다.

완료 기준:

- 지원된 target에서 객체·텍스트·이미지 누락이 없다.
- UMG는 실제 UE 5.8 Widget Blueprint compile과 capture를 통과한다.
- Figma exchange는 editable object와 stable mapping 보고서를 남긴다.
- 1,000 object 저장·열기 각각 2초 목표, 비정상 종료 없음.

## 4. 현재 실행 순서

현재 다음 작업은 `M0 → M1`이다. 기존 M2~M7 코드가 있더라도 M1의
선택·변형·hierarchy Gate가 실패하면 상위 기능을 완료로 판정하지 않는다.

첫 세로 슬라이스:

1. M0 fixture와 캡처/성능 harness 고정
2. M1의 parent/deep/multi/marquee 선택 규칙
3. move/resize/rotate와 Inspector 동기화
4. hierarchy reparent/reorder와 Undo
5. alignment/distribution/Tidy up
6. Desktop Dashboard 12-object 작업 통과 증거

## 5. 공식 기능 기준

- [Explore design files](https://help.figma.com/hc/en-us/articles/15297425105303-Explore-design-files)
- [Select layers and objects](https://help.figma.com/hc/en-us/articles/360040449873-Select-layers-and-objects)
- [Work with layers](https://help.figma.com/hc/en-us/sections/15330116720791-Work-with-layers)
- [Arrange layers with Smart selection](https://help.figma.com/hc/en-us/articles/360040450233-Arrange-layers-with-Smart-selection)
- [Guide to Auto Layout](https://help.figma.com/hc/en-us/articles/360040451373-Explore-auto-layout-properties)
- [Components collection](https://help.figma.com/hc/en-us/articles/39719619313047-Components-collection-Overview)
- [Create and use variants](https://help.figma.com/hc/en-us/articles/360056440594-Create-and-use-variants)
- [Interactive components](https://help.figma.com/hc/en-us/articles/360061175334-Create-interactive-components-with-variants)

