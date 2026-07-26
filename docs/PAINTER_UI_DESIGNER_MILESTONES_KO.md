# Painter General UI Designer Milestones

Status: active implementation

Canonical product plan:
`docs/PLAN_PAINTER_UI_DESIGNER.md`

## 원칙

- General UI document가 원본이고 UMG는 output adapter다.
- UI document에는 Unreal, HTML, Flutter 같은 target runtime class를
  저장하지 않는다.
- Painter의 기존 Paint/3D 기능, Undo/Redo, `.tspaint` 영속성을 공유한다.
- 지원하지 않는 출력은 `native`, `converted`, `baked`, `blocked` 중 하나로
  명시하며 조용히 누락하지 않는다.
- 각 마일스톤은 UI, Action, persistence, test가 함께 통과해야 완료다.

## M0: General UI Document Foundation

Status: implemented

사용 가능한 결과:

- `tigerstudio.painter.ui.v1` 중립 문서
- 여러 Artboard
- Frame/Group/Shape/Text/Image/Button/Progress 객체
- stable ID, parent hierarchy, geometry, style, content, constraint 필드
- duplicate ID, missing parent/artboard, parent cycle 검증
- revision 증가
- object hierarchy 삭제
- `.tspaint` save/open round trip
- Painter Undo/Redo snapshot
- general delivery profile 조회와 target preflight
- Design Handoff JSON package와 checksum manifest

Action:

- `paint.ui.document.inspect`
- `paint.ui.artboard.add/update/remove`
- `paint.ui.object.add/update/remove`
- `paint.ui.delivery.profiles`
- `paint.ui.delivery.preflight`
- `paint.ui.handoff.export`

완료 기준:

- pure document CRUD/validation/handoff test
- Qt Action/Undo/Redo/save/open test
- 기존 Painter document/action regression

## M1: First Usable UI Design Workspace

Status: foundation implemented, completion pending

현재 구현:

- Canvas mode: `Paint | UI Design | 3D Place`
- `paint.ui.workspace.set`
- UI Design 전용 canvas overlay
- Frame/Text/Button 직접 추가
- 객체 선택과 드래그 이동
- 선택 외곽선과 handle 표시
- Action으로 만든 객체가 화면에 즉시 반영

남은 완료 조건:

- Rectangle/Ellipse/Line/Image/Progress 도구
- canvas drag-to-create
- resize/rotate handle
- align/distribute/snap
- multi-artboard canvas 배치와 전환
- 우측 Inspect panel의 X/Y/W/H, fill, text, constraint
- Layers panel의 UI object hierarchy
- keyboard move/delete/duplicate
- 실제 desktop/mobile screenshot QA

## M2: Responsive Layout and Design System

Status: pending

- anchors and constraints
- horizontal/vertical auto layout
- padding, gap, wrap
- layout grid and safe area
- compact/regular breakpoint
- portrait/landscape preview
- light/dark/high-contrast theme
- color/typography/spacing/radius/effect tokens
- component definition/instance/variant
- instance override

완료 기준:

- mobile/desktop sample을 같은 component/token 원본으로 제작
- resize 시 constraint와 auto layout 결과가 deterministic
- save/open/undo/action parity

## M2A: 템플릿·라이브러리·디자인 시스템

상태: 대기

이 마일스톤은 화면 하나를 그리는 기능을 넘어 UI 제작 도구를 계속 사용할
이유를 만든다. 템플릿을 열 수 있다는 것만으로 완료하지 않으며, 템플릿은
편집 가능하고 재사용 가능하며 반응형이고 개발 전달까지 이어져야 한다.

- 모바일, 데스크톱, 웹, 게임 HUD, 방송, 프레젠테이션과 공용 컴포넌트용
  첫 실행 템플릿 갤러리
- 컴포넌트, Variant, 아이콘, 스타일, 디자인 토큰을 담는 로컬 팀 라이브러리
- 의존 버전, 변경 요약, 인스턴스 갱신 검토를 포함한 라이브러리
  게시·업데이트 흐름
- 크기, 상태, 테마, 플랫폼, 콘텐츠용 컴포넌트 속성과 Variant
- 템플릿에 포함되는 Auto Layout 프리셋과 반응형 제약 조건
- 재사용 가능한 색상, 타이포그래피, 간격, 반경, 그림자, 모션 토큰
- 템플릿 검색, 카테고리, 미리보기, 최근 항목, 즐겨찾기, 복제,
  템플릿에서 새 문서 만들기
- manifest, 라이선스·출처, 썸네일, 스키마 버전, 의존성 검증을 포함한
  템플릿·라이브러리 패키지 입출력
- 계정이나 네트워크 없이도 사용할 수 있는 기본 라이브러리
- 사람과 AI가 같은 템플릿, 라이브러리, 토큰, 컴포넌트를 사용하는
  `paint.ui.*` 생성 액션

완료 기준:

- 사용자가 공용 컨트롤을 다시 만들지 않고 템플릿으로 일관된 다중 화면
  데스크톱 또는 모바일 디자인을 만들 수 있다.
- 원본 컴포넌트나 토큰을 수정하면 영향받는 모든 인스턴스의 업데이트
  미리보기가 명시적으로 제공된다.
- 데스크톱과 모바일 Variant가 컴포넌트와 토큰을 공유하면서도
  결정론적인 Auto Layout 결과를 만든다.
- 저장·열기·Undo·Redo와 `paint.ui.*` 액션이 템플릿 및 라이브러리
  정체성을 보존한다.
- handoff가 템플릿 출처, 컴포넌트 버전, 토큰 참조, override,
  연결 해제된 인스턴스를 식별한다.
- 기본 제공 콘텐츠는 시각 QA를 통과하고 제3자 재배포 권리가 불명확한
  자료를 포함하지 않는다.

우선순위 원칙:

풍부한 템플릿은 시작을 빠르게 하지만 문서를 유지 가능하게 만드는 것은
재사용 컴포넌트, Auto Layout, 토큰, 안전한 라이브러리 업데이트다.
따라서 템플릿 개수만으로 이 마일스톤의 완료를 판단하지 않는다.

## M2B: 협업과 리뷰 운영

상태: 대기

- 객체에 고정되는 댓글과 리뷰 스레드
- 작성자, 시각, 해결 상태, stable object reference
- 이름 있는 체크포인트와 시각·문서 diff를 포함한 revision history
- 로컬 공유 리뷰 패키지를 우선 구현하고 클라우드·팀 전송은 선택적으로 추가
- 편집 도구 없이 댓글만 제공하는 리뷰어 전용 프로토타입 모드
- geometry, asset, token, 접근성, 플랫폼 매핑을 보는 개발자 Inspect 모드
- 충돌을 방지하는 라이브러리·컴포넌트 업데이트 검토
- 내보낼 수 있는 리뷰 보고서와 AI 리뷰어용 Action/MCP 접근

완료 기준:

- 객체를 이동하거나 문서를 저장·열기·내보내도 댓글 연결이 유지된다.
- 리뷰어가 디자인 문서를 수정하지 않고 검사하고 댓글을 남길 수 있다.
- 디자이너가 revision을 비교하고 컴포넌트·라이브러리 업데이트를 선택적으로
  수락할 수 있다.
- 협업 서비스가 설정되지 않아도 로컬·오프라인 작업을 온전히 사용할 수 있다.

## M3: Prototype and Developer Handoff

Status: pending

- click/tap/hover/focus/keyboard trigger
- state/variant transition
- navigation, back, overlay, scroll target
- Painter internal prototype preview
- breakpoint/theme/localization preview
- object inspection
- revision diff
- self-contained local Review Prototype

완료 기준:

- Painter가 없는 환경에서 review artifact 실행
- keyboard focus와 주요 interaction 재생
- stable object ID 기반 inspection/revision diff

## M4: Production Asset Delivery

Status: pending

- PNG/WebP/SVG capability-aware export
- export region and slice
- @1x/@2x/@3x/custom density
- transparent trim and padding
- 9-slice metadata
- texture atlas option
- alpha/color-space validation
- deterministic painted-layer bake

완료 기준:

- artifact 재실행으로 manifest/hash 검증
- unsupported SVG/Painter effect가 명시적으로 raster/baked 분류
- output pixel and metadata QA

## M5: Unreal UMG Adapter

Status: shared Motion Designer backend exists; Painter adapter pending

- Painter provider adapter
- shared Tiger UMG schema extension
- Painter Unreal Link dialog
- `paint.umg.*` Action
- project-local TigerStudioUMG install/update
- Generate/Regenerate
- user-owned Blueprint region preservation
- real UE 5.8 compile/save/reopen/capture

공유 backend:

- `app/unreal_umg_document.py`
- `app/unreal_umg_plugin.py`
- `app/unreal_umg_workflow.py`
- `resources/unreal_plugins/UMG/TigerStudioUMG`

Painter 전용 Unreal plugin은 만들지 않는다.

## M6: AI Co-design and Production QA

Status: pending

- 자연어 screen/component 생성
- 변경 계획과 부분 적용
- accessibility/localization audit
- performance/memory budget
- target preflight 설명
- artifact와 실제 runtime evidence 자동 수집

완료 기준:

- AI가 등록 Action만 사용
- 변경 전 preview/diff 제공
- mobile app sample과 game HUD sample을 같은 일반 UI 계약으로 생성

## 현재 검증 명령

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\test_painter_ui_document.py `
  tests\test_painter_ui_actions.py `
  tests\test_painter_document_io.py `
  tests\test_painter_actions.py `
  tests\test_editor_architecture_rules.py -q
```
