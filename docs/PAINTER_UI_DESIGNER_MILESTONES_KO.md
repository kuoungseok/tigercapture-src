# Painter General UI Designer Milestones

Status: active implementation

Canonical product plan:
`docs/PLAN_PAINTER_UI_DESIGNER.md`

Canonical P0-P10 worklist:
`docs/PAINTER_UI_FIGMA_WORKLIST_KO.md`

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

Status: core interactive editing implemented

현재 구현:

- Canvas mode: `Paint | UI Design | 3D Place`
- `paint.ui.workspace.set`
- UI Design 전용 canvas overlay
- Select/Frame/Rectangle/Ellipse/Line/Text/Image/Button/Progress 도구
- canvas drag-to-create
- 객체 선택과 드래그 이동
- 선택 외곽선, 네 모서리 resize handle, 회전 handle
- rotation-aware draw/hit test와 Inspect rotation 편집
- 선택적으로 켜는 8 px 위치·크기 snap과 15도 회전 snap
- 우측 UI 전용 `Layers | Inspect` panel
- Inspect의 name/type/X/Y/W/H/opacity/visible/locked 편집
- Fill/Stroke/Stroke Width/Radius/Shadow 편집과 Undo
- 텍스트 내용, 크기, 굵기, 정렬, 행간 편집
- 캔버스의 배율 연동 스타일, 그림자, 줄바꿈, typography 렌더링
- artboard 선택기와 `paint.ui.artboard.activate`
- artboard 기준 left/hcenter/right/top/vcenter/bottom 정렬
- Ctrl/Shift 캔버스 선택과 Layers 패널 다중 선택
- 다중 선택 객체의 그룹 이동과 단일 Undo
- 선택 경계 기준 정렬과 수평/수직 균등 분배
- `paint.ui.selection.set`, `paint.ui.object.arrange` 자동화 계약
- 휴대폰/데스크톱 아트보드 비율 보존 전환
- Group/Ungroup, 자식 보존 그룹 이동, 계층 들여쓰기
- 레이어 앞/뒤 순서 변경과 `paint.ui.object.group/ungroup/reorder`
- 그룹 중앙 드롭 nesting, 항목 위·아래 sibling reorder, 빈 영역 root 이동
- `paint.ui.object.reparent`와 동일한 Layers 드래그/드롭 Undo 계약
- keyboard 1 px 이동, Shift+방향키 10 px 이동, Delete, Ctrl+D
- UI 객체 duplicate/delete와 Undo/Redo
- Action으로 만든 객체가 화면에 즉시 반영
- 자유 배치형 multi-artboard overview, pan/zoom/Fit
- marquee selection, Smart Guide, 비율/중심 resize
- 아트보드 제목 드래그 이동과 mobile/desktop/console/broadcast 프리셋
- 피벗 X/Y, 좌우·상하 Constraint, 최소/권장/최대 크기, 비율 잠금
- 아트보드/부모 크기 변경에 대한 deterministic constraint 해석
- 피벗 기준 회전·hit test와 constraint-aware 캔버스 resize
- 실제 이미지 파일 미리보기와 Fit/Fill/Stretch/Tile 배치
- source-pixel L/T/R/B 여백을 사용하는 deterministic 9-slice
- 접근성 role, label, focus order 편집과 Action/Undo 왕복
- 접근성 라벨 누락과 아트보드별 명시 focus order 중복 경고
- 선택 객체의 대상별 `Native/Material/Baked/Blocked` 상태와 판정 이유
- phone Layers/Inspect 및 desktop 다중 선택 화면 캡처

후속 검증:

- 실제 mobile 및 여러 desktop 크기의 지속적인 screenshot QA
- target adapter 출력과 캔버스 스타일의 parity
- 이미지 리소스 임베딩·해시·density 전달은 P8 후속 범위

## M2: Responsive Layout and Design System

Status: responsive Auto Layout, artboard guides, diagnostics, breakpoint/orientation overrides, and theme-token preview implemented

- anchors and constraints (implemented foundation)
- horizontal/vertical auto layout (implemented)
- padding, gap, main/cross alignment (implemented)
- absolute child positioning escape (implemented)
- wrap, Hug/Fill sizing (implemented)
- uniform grid, columns, custom guides, and safe area (implemented)
- layout cycle/impossible constraint diagnostics (implemented)
- breakpoint/orientation object override (implemented)
- portrait/landscape preview
- light/dark/high-contrast theme (implemented preview and resolution)
- color/typography/spacing/radius/border/shadow/opacity/icon/image tokens
  (typed CRUD, themed resolution, searchable library, usage/unused reporting,
  aliases, stable-ID Bind/Unbind UI/Actions, and deterministic JSON
  import/export with explicit conflict policies implemented)
- component definition/instance/variant
- instance override

P4 component checkpoint:

- Component Definition conversion and Instance subtree creation implemented
- Definition property and direct-child topology synchronization implemented
- stable source object IDs and local dotted-path Instance overrides implemented
- Inspector Create/Instance commands and Action/Undo parity implemented
- typed component properties and Normal/Hover/Pressed/Focused/Disabled/Selected
  state override authoring implemented
- Instance state preview and Action/Undo parity implemented
- linked Variant topology and stable-ID Instance switching implemented
- Detach to local objects and Localize to an independent component implemented
- dedicated searchable Components library tab, usage counts, Definition
  selection, Instance placement, Variant creation, rename, and Action inspect
  implemented

완료 기준:

- mobile/desktop sample을 같은 component/token 원본으로 제작
- resize 시 constraint와 auto layout 결과가 deterministic
- save/open/undo/action parity

## M2A: 템플릿·라이브러리·디자인 시스템

상태: 로컬·오프라인 제품 범위 구현

구현 체크포인트:

- 11개 카테고리의 오리지널 완성 문서 템플릿 12개
- 검색, 카테고리 필터, 실제 문서 기반 썸네일을 제공하는 시각적 갤러리
- 각 템플릿에 artboard, object, token, Component Definition, interaction 포함
- source, author, version, tag, difficulty, license manifest
- `.tspaint`에 `linked_targets.template_source` provenance 영속 저장
- UI와 `paint.ui.template.catalog.inspect/apply` Action이 같은 생성 서비스 사용

추가 구현 체크포인트:

- license, dependency, document hash를 포함하는 `.tstemplate` 입출력
- 패키지 검증·설치, 사용자 템플릿 저장, 최근 항목과 즐겨찾기
- 버전·dependency·document hash 선택적 업데이트 검토
- 내장/설치 템플릿을 함께 보여주는 시각 갤러리

남은 콘텐츠 작업은 카탈로그 규모 확대와 지속적인 실제 화면 시각 QA다.
이는 기능 차단 항목이 아니라 기본 라이브러리 콘텐츠 확장 범위다.

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

상태: 로컬·오프라인 리뷰 범위 구현

구현 체크포인트:

- stable object/artboard anchor, 작성자, reply, resolve 상태의 댓글
- `.tspaint`에 댓글과 이름 있는 체크포인트 영속 저장
- stable ID 기준 artboard/object/component/token/interaction revision diff
- 읽기 전용 HTML 리뷰 패키지와 JSON 개발자 Inspect 보고서
- UI `Publish | Review`와 `paint.ui.review.*` Action 공유
- 클라우드 서비스 없이 완전한 로컬 리뷰

실시간 다중 사용자 동기화와 원격 팀 전송은 선택적 서비스 후속 범위다.

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

Status: implemented local prototype scope

Implementation checkpoint:

- click/double click/hover/press/focus/keyboard runtime
- navigate/back/open-close overlay/state/visibility/opacity/material scalar
- animation/sound event dispatch
- pointer/keyboard 동작이 포함된 self-contained HTML prototype
- 원본 문서·manifest·validation을 함께 내보내는 offline artifact
- `paint.ui.prototype.inspect/trigger/export`

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

Status: implemented

Implementation checkpoint:

- PNG/WebP/SVG와 @1x/@2x/@3x/custom density
- artboard와 object slice, padding, transparent trim
- unsupported vector 표현을 누락하지 않는 embedded PNG SVG bake
- deterministic name, SHA-256, sRGB/alpha metadata
- 9-slice metadata, texture atlas image/JSON
- image/font/sound resource ID, 존재 여부, 크기, hash
- `paint.ui.assets.export`

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

Status: Painter adapter implemented; real UE compile/generation verified

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

2026-07-27 verification:

- Painter artboard를 provider=`painter` 공용 Tiger UMG 문서로 변환
- `Native/Material/Baked/Blocked` preflight와 명시적 blocker
- `paint.ui.umg.preflight/package/generate`
- `D:\UE_5.8\Engine` BuildPlugin Win64 Development/Shipping 성공
- `accessible_checkout`로 Widget Blueprint 생성
- generated widget 8, generated asset load 성공, errors 0
- 실제 Unreal 화면 캡처는 release evidence 갱신 시 추가한다.

## M6: AI Co-design and Production QA

Status: safe local co-design foundation implemented

Implementation checkpoint:

- 자연어 요구를 완성형 템플릿과 editable operation plan으로 변환
- 적용 전 preview document와 stable-ID revision diff
- required operation과 selected partial apply
- stale revision과 다른 document plan 차단
- accessibility, localization, object/image budget, delivery audit
- UI `Publish | AI`와 `paint.ui.ai.plan/apply/audit`
- AI provider는 직접 문서를 쓰지 않고 등록 Action만 사용

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
