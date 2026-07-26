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
