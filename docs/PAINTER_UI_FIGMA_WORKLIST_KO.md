# Painter UI 전용 모드 작업 목록

Status: canonical implementation backlog; P0 complete

P0 implementation checkpoint (2026-07-26):

- UI document version 2 defines typed component, token, and interaction records.
- Stable IDs are preserved by update operations and assigned during v1 migration.
- Parent, component, token, interaction, alias, and cycle references are validated.
- Referenced component/token deletion is blocked unless explicit detachment is requested.
- Painter Actions expose CRUD for all three record types.
- Legacy `.tspaint` documents migrate through the shared normalization path and
  typed records survive save/open round trips.

관련 구현 현황:

- `docs/PLAN_PAINTER_UI_DESIGNER.md`
- `docs/PAINTER_UI_DESIGNER_MILESTONES_KO.md`
- `docs/SPEC_PAINTER_DOCUMENT_FORMAT.md`

## 목표와 소유권

Painter를 단순 도형 배치기가 아니라 Figma형 UI 제작 도구로 완성한다.
Painter는 정적 UI 구조, 컴포넌트, 레이아웃, 토큰, 프로토타입 연결을
소유하고 Motion Designer는 키프레임과 전환 애니메이션을 소유한다.

구현 우선순위:

1. P0 문서 모델
2. P1 편집 UX
3. P2 인스펙터
4. P3 Auto Layout
5. P4 컴포넌트
6. P7 Motion Designer 연결
7. P9 Unreal UMG

P5, P6, P8, P10은 위 기능의 기반과 전달 품질을 따라 병행한다.

## P0. 문서 모델 완성

1. `components`, `tokens`, `interactions`를 단순 JSON 배열이 아닌 정식
   타입과 CRUD로 구현
2. 모든 아트보드, 객체, 컴포넌트, 토큰에 변경되지 않는 stable ID 적용
3. 컴포넌트, 부모, 토큰, 인터랙션 참조 검증
4. 참조 순환, 삭제된 대상, 중복 ID 검출
5. 스키마 의미 변경 시 `tigerstudio.painter.ui.v1` 버전 갱신
6. 기존 `.tspaint` 문서 마이그레이션과 왕복 저장 테스트 추가

## P1. Figma형 편집 UX

1. 여러 아트보드를 한 캔버스에서 자유 배치
2. 캔버스 패닝, 휠 줌, Fit Selection, Fit Artboard
3. 다중 선택, 영역 선택, 부모 안으로 드래그
4. Layers 트리 드래그로 순서 변경과 재부모화
5. 잠금, 숨김, 이름 변경, 복제, 삭제
6. 정렬, 균등 분배, Smart Guide, 픽셀 스냅
7. 객체 크기 조절 시 비율 잠금과 중심 기준 조절
8. 실제 모바일과 데스크톱 화면 크기 프리셋 제공

현재 구현된 기반:

- 다중 선택, 그룹 이동, 정렬, 균등 분배
- Group/Ungroup과 자식 보존 이동
- Layers 순서 변경, 그룹 nesting, root 이동
- phone/desktop 아트보드 전환과 비율 보존

## P2. 인스펙터 확장

1. X/Y/W/H, 회전, 피벗, 불투명도
2. Fill, Stroke, Stroke Width, Radius, Shadow
3. 텍스트 내용, 폰트, 크기, 굵기, 정렬, 행간
4. Anchor와 좌우, 상하 Constraint
5. 최소, 권장, 최대 크기와 비율 잠금
6. 이미지 Fit/Fill/Stretch/Tile
7. 9-slice margin
8. 접근성 role, label, focus order
9. 선택 객체의 target별 `Native/Material/Baked/Blocked` 표시

## P3. Auto Layout와 반응형

1. Horizontal/Vertical Auto Layout
2. Padding, Gap, Alignment, Wrap
3. Hug Content, Fixed Size, Fill Container
4. Grid, Column, Guide, Safe Area
5. Breakpoint와 화면 방향별 override
6. Desktop, mobile, console, broadcast 프리셋
7. Light/Dark/High Contrast 테마 미리보기
8. 레이아웃 순환과 불가능한 Constraint 검출

## P4. 컴포넌트 시스템

1. 선택 객체를 Component Definition으로 변환
2. Component Instance 생성
3. Instance에서 텍스트, 이미지, 토큰 override
4. Variant와 property 정의
5. `Normal/Hover/Pressed/Focused/Disabled/Selected` 상태
6. 컴포넌트 원본 수정 시 인스턴스 갱신
7. 원본 연결 해제와 로컬 컴포넌트 변환
8. 컴포넌트 참조 순환 방지

## P5. 디자인 토큰

1. Color, Typography, Spacing, Radius, Border, Shadow, Opacity
2. 아이콘과 이미지 alias
3. 객체 속성에 값 복사가 아닌 token ID 연결
4. 토큰 수정 시 연결 객체 일괄 갱신
5. Light/Dark/High Contrast 테마 값
6. 사용 중인 토큰과 미사용 토큰 검사
7. 토큰 JSON 내보내기와 다시 가져오기

## P6. 프로토타입

1. Click, Double Click, Hover, Press, Focus, Keyboard 트리거
2. Navigate, Back, Open/Close Overlay
3. Change State/Variant
4. Play Animation, Play Sound
5. Set Visibility/Opacity/Material Scalar
6. 캔버스에서 연결선을 드래그해 대상 화면 지정
7. Preview에서 실제 포인터와 키보드 동작
8. 연결 대상이 삭제되면 명시적인 오류 표시

## P7. Motion Designer 연결

1. 선택 객체 또는 컴포넌트에 `Animate` 명령 제공
2. stable object ID를 유지한 채 Motion Designer 실행
3. Painter 객체를 Motion 문서에 복제하지 않고 `motion_clip_id`로 연결
4. Painter Preview에서 Motion 클립 재생
5. 상태별 전환 애니메이션 선택
6. Auto Layout 계산 후 Motion transform을 오프셋으로 적용
7. Motion 클립 누락, 깨진 참조, 지원하지 않는 속성을 preflight에서 검출
8. 애니메이션 변경 시 Painter에 즉시 반영

## P8. 에셋 및 전달

1. PNG/WebP/SVG와 @1x/@2x/@3x 내보내기
2. Slice와 Export Region
3. 투명 여백 제거와 deterministic 파일명
4. 9-slice 및 texture atlas metadata
5. 이미지, 폰트, 사운드 resource ID와 해시
6. `design_document.json`, `tokens.json`, `components.json`,
   `interactions.json`
7. 사람이 읽을 수 있는 inspection report
8. revision diff와 재생성 기록

## P9. Unreal UMG

1. 별도 Painter 플러그인을 만들지 않고 기존 `TigerStudioUMG` 사용
2. Painter에서 provider-neutral Tiger UMG adapter 구현
3. Frame/Group을 Canvas 또는 Panel로 변환
4. Auto Layout을 HorizontalBox/VerticalBox/Grid로 변환
5. Text/Image/Button/Progress를 네이티브 UMG로 변환
6. 단순 효과는 UI Material로 변환
7. 복잡한 Painter 표현은 deterministic bake
8. Motion 연결은 `UWidgetAnimation`으로 변환
9. 버튼 상태와 이벤트는 `UTigerStudioButton`으로 변환
10. Widget Blueprint 컴파일과 실제 Unreal 캡처까지 검증

## P10. Actions와 QA

1. 컴포넌트, 토큰, Auto Layout, 프로토타입, Motion 연결 Action 추가
2. UI와 Action이 동일한 mutation service 사용
3. 저장, 로드, Undo/Redo, 복사/붙여넣기 테스트
4. 다중 아트보드와 반응형 레이아웃 테스트
5. Painter Preview와 UMG 결과 비교
6. 폰트, 이미지, 사운드 누락 테스트
7. 실제 모바일과 데스크톱 화면 캡처
8. 모든 전달 결과를 `Native/Material/Baked/Blocked`로 보고

## 작업 경계

- Painter는 UI 구조, 레이아웃, 컴포넌트, 스타일, 토큰을 소유한다.
- Motion Designer는 키프레임과 전환 애니메이션을 소유한다.
- Unreal 출력은 공용 `TigerStudioUMG`만 사용한다.
- Painter 전용 Unreal 플러그인을 새로 만들지 않는다.
- Motion 데이터를 Painter 객체 내부에 중복 저장하지 않고 stable ID로
  연결한다.
- 기능을 조용히 누락하지 않고 반드시 preflight에서 경고하거나
  차단한다.
- 각 기능은 UI, Action, persistence, Undo/Redo, 검증 테스트가 같은
  mutation contract를 통과해야 완료로 간주한다.
