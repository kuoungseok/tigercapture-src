# Motion Designer - Painter UI 연동 작업 목록

상태: **양쪽 제작 세션 협의 완료, P0 계약 통합부터 진행**

협의 기준:

- Motion 세션: 현재 작업 세션
- Painter 제작 세션: `019f1c1c-039f-71a3-a776-b8334175150f`
- 기준 소스: `996bc050`
- 협의일: 2026-07-28

이 문서는 Painter UI Design 모드가 Motion Designer의 기능을 가져오는
canonical 작업 목록이다. Painter 안에 Motion Designer 전체 타임라인을 복제하지
않는다. Painter는 UI의 정적 구조와 최종 상태를 소유하고, Motion Designer는
시간에 따라 변하는 값과 재생 구간을 소유한다.

## 1. 합의된 소유권

### Painter가 소유

- Artboard, Frame, Group 계층
- Auto Layout, Constraint, breakpoint와 반응형 계산
- Component Definition, Instance, Variant
- Normal, Hover, Pressed, Focused, Disabled, Selected의 최종 정적 상태
- Fill, Stroke, Text, Image, Token과 접근성 정보
- Interaction의 trigger와 논리적 action
- UMG 위젯 구조와 정적 리소스 참조

### Motion Designer가 소유

- 키프레임, 보간, 그래프와 easing
- 시간축, 시작/종료 구간, 속도, 반복
- 상태 사이의 전환 경로
- Entrance, Exit, Loop 애니메이션
- Transform, Opacity, Material 값의 시간 변화
- 마스크, 모션 이펙트와 복잡한 타이밍
- `play_animation`이 실행할 Motion Clip 본문

### 공통 규칙

- 좌표는 `resolved layout + motion offset`으로 합성한다.
- Motion이 Painter 객체의 절대 레이아웃을 소유하지 않는다.
- Painter에는 키프레임을 복제 저장하지 않는다.
- Stable ID와 발행된 Motion composition revision으로 연결한다.
- Painter의 정적 상태와 Motion의 시간 변화 중 어느 것도 조용히 덮어쓰지 않는다.

## 2. 현재 재사용할 구현

### 핵심 재사용

- `app/painter_ui_motion_bridge.py`
  - Painter stable object ID와 Motion layer 매핑
  - Auto Layout/반응형 결과 해석
  - Painter 배치 변경 후 Motion offset rebase
  - Painter 캔버스용 Motion 상태 평가
- `app/motion_designer/ui_motion_binding.py`
  - scope, trigger, from/to state, animation name
  - 대상 layer/property와 delivery policy
  - UMG trigger와 property preflight
- `app/painter_ui_motion_actor.py`
  - 독립 `.tgmotion` composition을 Painter Canvas 객체로 배치
  - 일반 UI 상태 전환과 합치지 않고 별도 Actor 계약으로 유지
- `app/unreal_umg_document.py`
  - Motion binding을 UWidgetAnimation 후보로 변환
- `app/actions/editor_adapter_paint.py`, `app/actions/paint_namespace.py`
  - attach/open/preview/inspect/import/list Action 기반

### 통합이 필요한 중복 계약

- Painter object의 `motion_clip_id`
- `linked_targets.motion_designer.object_bindings`
- Motion metadata의 `ui_motion_bindings`

세 경로를 하나의 canonical `binding_id` 기반 계약으로 통합한다.

## 3. Painter가 우선 가져올 Motion 기능

1. **Component State Transition**
   - `Normal -> Hover`
   - `Hover -> Pressed`
   - `Pressed -> Normal`
   - 첫 제품 수직 기능은 `Normal -> Hover` 하나를 끝까지 완성한다.
2. **Entrance / Exit / Loop 프리셋**
   - Fade, Slide, Scale, Pop, Pulse, Shimmer
   - 객체에 드롭한 뒤 범위와 속도만 Painter에서 조절한다.
3. **Transform / Opacity 캔버스 프리뷰**
   - Painter에서 재생·정지·상태 선택·짧은 scrub을 제공한다.
   - 키프레임 편집은 Motion Designer에서 수행한다.
4. **Interaction의 Play Animation**
   - Prototype Interaction 행에 Motion Clip을 연결한다.
   - click, hover, unhover, pressed, released trigger를 우선 지원한다.
5. **Material Parameter Motion**
   - Fill, Stroke, Corner Radius, Progress
   - 실제 UI Material 생성 경로와 함께 제공할 때만 지원으로 표시한다.
6. **Text Reveal**
   - 제목, 온보딩, HUD 메시지를 우선 대상으로 한다.
   - 글리프 단위 애니메이션은 기본적으로 bake 대상이다.
7. **Motion Actor**
   - 배너, 교육 애니메이션, 광고 composition 같은 독립 콘텐츠용이다.
   - 일반 버튼/컴포넌트 상태 애니메이션에는 사용하지 않는다.

Path Morph, Puppet, Tracking, Particle, 3D, 오디오 반응은 일반 UI 제작의
P0/P1 범위에 넣지 않는다.

## 4. 최소 왕복 계약

Painter는 다음 연결 정보만 저장한다.

```json
{
  "binding_id": "ui-motion-binding-42",
  "source_document_id": "painter-doc-1",
  "source_object_id": "ui-object-17",
  "source_component_id": "ui-component-3",
  "interaction_id": "ui-interaction-8",
  "motion_composition_id": "motion-comp-9",
  "motion_revision": 12,
  "scope": "transition",
  "trigger": "pointer_enter",
  "from_state": "normal",
  "to_state": "hover",
  "animation_name": "ButtonHover",
  "property_names": ["position", "scale", "opacity"],
  "layout_policy": "resolved_layout_plus_motion_offset",
  "delivery_policy": "native_preferred"
}
```

Motion에서 Painter로 돌아오는 값:

- composition ID와 revision/hash
- duration과 loop 가능 여부
- 애니메이션되는 property 목록
- 썸네일 또는 poster frame
- Preview/UMG preflight 결과
- 누락 리소스와 relink 진단

키프레임, 그래프, 마스크, 이펙트 본문은 `.tgmotion`이 소유한다.

## 5. Painter UI/UX 목록

### 명령과 Inspector

- 상단 `Animate` 아이콘 버튼
- 우클릭 `Animate in Motion Designer`
- Inspector의 접이식 `Motion` 섹션
- 연결 상태, duration, revision, delivery 상태 배지
- `Reload`, `Keep Current`, `Relink`, `Detach` 명령

### Component와 Prototype

- Components 패널 상태 행의 Motion 배지
- `Normal -> Hover` 등 상태 전환 목록
- Prototype Interaction 행의 `Play Animation` 선택기
- Motion Clip을 Interaction 행에 드롭해 `play_animation` 생성

### Assets와 Drag & Drop

- Assets 패널에서 `Motion Clips`와 `Motion Actors`를 구분
- `.tgmotion` 썸네일, 길이, loop, revision 표시
- Motion Clip을 UI 객체에 드롭하면
  `Entrance / Exit / Loop / State Transition` 선택 팝업
- `.tgmotion`을 빈 Canvas에 드롭하면 `motion_actor` 생성

### 캔버스 Transport

- Play, Stop
- Component state 선택
- 짧은 scrub
- 여러 Motion Actor의 독립 playhead/offset/loop는 P2
- 전체 Timeline/Graph Editor는 Painter에 넣지 않는다.

## 6. Unreal UMG 전달 분류

### Native

- Position, Scale, Rotation, Opacity
- 기본 버튼 이벤트
- 단순 Text/Image

### Material

- Fill, Stroke, Corner Radius, Progress 애니메이션
- 지원 범위의 gradient/mask

### Baked

- Path Morph
- 복잡한 mask, blur, effect
- 글리프 애니메이션
- Particle, 3D, Motion Actor

### Blocked

- 누락 리소스
- 깨진 stable ID 또는 revision 충돌
- 지원하지 않는 trigger
- `native_only` 정책과 Material/Bake 요구의 충돌
- bake가 금지된 고급 효과

`Material`과 `Baked`는 실제 생성 경로와 Unreal 캡처 증거가 생기기 전까지
지원 완료로 표시하지 않고 shared preflight에서 `Blocked`로 유지한다.

## 7. 실행 우선순위

## P0. 계약 통합

- [ ] `UIMotionBinding`을 Painter/Motion 공용 canonical 계약으로 확정
- [ ] `motion_clip_id`와 `linked_targets`를 binding ID 기반으로 마이그레이션
- [ ] Painter state/interaction과 Motion binding의 양방향 참조 검증
- [ ] composition revision/hash, missing/relink, orphan cleanup
- [ ] `resolved layout + motion offset` 합성 규칙 테스트 고정
- [ ] 삭제, 복제, Detach, Localize, Variant 변경 시 binding 정책
- [ ] 양쪽 Undo 경계와 동시 수정 충돌 보고
- [ ] Painter/Motion/Tiger UMG 공통 preflight
- [ ] Action/MCP inspect/migrate/relink/detach 제공

완료 기준:

- 저장/로드 후 binding ID와 revision이 유지된다.
- Auto Layout 또는 breakpoint 변경 후 Motion offset이 보존된다.
- 삭제·복제·Detach가 고아 composition이나 중복 binding을 만들지 않는다.

## P1. 첫 제작 수직 기능

- [ ] `Normal -> Hover` Component State Transition 생성
- [ ] Painter `Animate`와 Motion Inspector 섹션
- [ ] Motion Clip Assets 목록과 객체 drag-and-drop
- [ ] Fade/Slide/Scale/Pop/Pulse/Shimmer 프리셋
- [ ] Painter transform/opacity 실시간 프리뷰
- [ ] Interaction `Play Animation` 편집
- [ ] Motion 변경 감지와 `Reload / Keep Current` 충돌 UI
- [ ] 모든 기능의 Action/MCP parity

완료 기준:

- Painter에서 버튼을 만들고 Hover Motion을 연결·미리보기·수정·저장한다.
- 프로젝트 재실행 후 같은 상태 전환이 복원된다.
- UI, Action, 저장/로드, Undo/Redo, 재연결, Painter Preview가 동일 binding
  계약을 통과한다.
- UMG preflight가 같은 binding과 delivery policy를 판정한다.
- 생성된 UMG Widget Blueprint에서 Hover 이벤트와 UWidgetAnimation이 실행된다.

## P2. 전달과 고급 기능

- [ ] Painter 구조와 Motion animation을 하나의 Tiger UMG 문서로 병합
- [ ] Fill/Stroke/Corner/Progress용 실제 UI Material 생성
- [ ] deterministic raster/flipbook/video bake
- [ ] Motion Actor GPU 프레임 공유
- [ ] 여러 Actor의 독립 playhead, 시작 offset, loop 구간
- [ ] 자산 collect/relink/hash와 `.tspaint` 패키징
- [ ] responsive breakpoint별 Motion 검사
- [ ] Painter Preview/Motion Export/Unreal UMG 픽셀 비교 QA
- [ ] 15초·30초·60초 UI/광고/교육 템플릿 성능 QA

## 8. 주요 위험

- Painter 정적 속성을 Motion에 복제해 생기는 drift
- Component state를 양쪽에서 수정하는 중복 소유
- Auto Layout 변경 뒤 절대 위치 키프레임이 깨지는 문제
- Painter document와 Motion composition의 revision 충돌
- Instance/Variant 교체 시 stable ID와 binding 손실
- Material/Baked 미구현 상태를 지원 완료로 표시하는 문제
- CPU 프레임 생성으로 Painter 프리뷰가 느려지는 문제

따라서 구현 순서는 **P0 계약 통합 -> `Normal -> Hover` 수직 기능 ->
Tiger UMG 실제 생성/캡처**로 고정한다.
