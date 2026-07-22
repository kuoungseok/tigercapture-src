# TigerCapture Standalone Painter 기획서

## 목적

TigerCapture Paint를 영상 프레임 위에 간단히 그리는 주석 도구에서, 독립 실행 가능한 2D 페인터/이미지 편집 앱으로 확장한다. 기존 Video Paint는 빠른 프레임 주석, 말풍선, PNG 스티커, Editor Object, Cutout을 유지한다. Standalone Painter는 빈 캔버스, 레이어, 선택 영역, 패스, 채널, 컬러 보정, PNG export를 중심으로 둔다.

목표 사용자는 Photoshop에 익숙한 사용자다. 따라서 기본 배치는 왼쪽 세로 툴바, 상단 옵션/메뉴, 중앙 캔버스, 오른쪽 `Layers / Channels / Paths / History` 패널을 따른다. 단, UI 톤은 TigerCapture 리뉴얼 테마를 유지하고, AI/자동화가 조작 가능한 action 표면을 처음부터 같이 설계한다.

## 참고 구조

- Photoshop: Layers panel은 레이어 선택, 표시/숨김, 정렬, 불투명도, 이름 변경의 중심이다. Channels panel은 RGB composite과 Red/Green/Blue/Alpha/Mask 채널을 표시한다. Paths panel은 path를 selection으로 변환하거나 selection을 path로 저장한다.
- GIMP: Layers, Channels, Paths를 이미지 구조 관련 dockable dialog로 묶고, Paths dialog에서 path 저장, 삭제, selection 변환을 제공한다.
- Krita: Layers docker는 layer stack, controls, operation bar로 나뉘며, selection/path 도구는 벡터 기반 선택 영역을 만든다.
- Photopea: Photoshop과 유사하게 오른쪽 Layers/Channels 패널을 핵심 작업면으로 둔다.

참고 출처:

- Adobe Photoshop Layers: https://helpx.adobe.com/photoshop/desktop/create-manage-layers/get-started-layers/work-with-the-layers-panel.html
- Adobe Photoshop Channels: https://helpx.adobe.com/photoshop/using/channel-basics.html
- Adobe Photoshop Paths/Selections: https://helpx.adobe.com/photoshop/using/converting-paths-selection-borders.html
- GIMP Layers/Channels/Paths: https://docs.gimp.org/3.2/en/gimp-dialogs-structure.html
- GIMP Paths Dialog: https://docs.gimp.org/2.10/en/gimp-path-dialog.html
- Krita Layers Docker: https://docs.krita.org/en/reference_manual/dockers/layers.html
- Photopea Layers: https://www.photopea.com/learn/layers
- Photopea Channels: https://www.photopea.com/learn/channels

## 모드 분리

### Video Paint

- 영상 프레임을 배경으로 사용한다.
- 말풍선, PNG 스티커, Editor Object, Cutout을 유지한다.
- 짧은 주석, 썸네일 표시, 리뷰용 캡처 보정이 목적이다.
- 복잡한 레이어/패스/채널 편집은 우선 노출하지 않는다.

### Standalone Painter

- 빈 캔버스 또는 이미지 파일을 작업 문서로 연다.
- 영상 전용 기능인 말풍선/스티커/Editor Object/Cutout은 숨긴다.
- 레이어, 채널, 패스, 선택 영역, 브러시, 컬러 편집, export를 중심으로 둔다.
- 향후 PSD 호환은 목표가 될 수 있지만 1차 MVP 범위에는 넣지 않는다.

## 전체 UI 레이아웃

### 상단 메뉴바

1. File
2. Edit
3. View
4. Image
5. Layer
6. Select
7. Path
8. Filter
9. Window
10. Help

### 상단 옵션바

선택한 도구별 옵션을 보여준다.

- Move: Auto Select, Transform Controls
- Selection: Mode, Feather, Anti-alias
- Brush: Size, Opacity, Flow, Blend, Brush Preset
- Eraser: Size, Opacity, Mode
- Fill/Gradient: Type, Tolerance, Sample All Layers
- Path/Pen: Shape/Path/Selection mode, Close Path, Make Selection
- Text: Font, Size, Weight, Align, Color
- Crop: Ratio, Reset, Apply

### 왼쪽 툴바

Photoshop에 익숙한 사용자를 기준으로 세로 아이콘 툴바를 둔다.

- Move
- Rectangular Marquee
- Lasso
- Magic Wand / Select Similar Color
- Crop
- Eyedropper
- Brush
- Pencil
- Eraser
- Fill Bucket
- Gradient
- Pen / Path
- Shape
- Text
- Hand / Pan
- Zoom
- Foreground / Background Color

### 중앙 캔버스

- 빈 캔버스, 이미지, 투명 배경 checkerboard를 지원한다.
- 줌, 팬, Fit, 100%, 우클릭 메뉴를 지원한다.
- 선택 영역은 marching ants로 표시한다.
- 패스는 anchor/control point와 stroke preview를 표시한다.
- 캔버스 주변에는 rulers/guides/grid를 선택적으로 표시한다.

### 오른쪽 패널

기본 탭:

- Layers
- Channels
- Paths
- History

보조 탭:

- Brush Presets
- Color / Swatches
- Adjustments
- Navigator

## 메뉴 상세

### File

- New
- Open Image
- Import Image as Layer
- Save Project
- Save As
- Export PNG
- Export Transparent PNG
- Export Selection PNG
- Close

1차 구현은 `New`, `Open Image`, `Export PNG`, `Export Transparent PNG`를 우선한다.

### Edit

- Undo
- Redo
- Cut
- Copy
- Paste
- Clear
- Fill
- Stroke
- Free Transform
- Transform Selection
- Preferences

캔버스 우클릭 메뉴에는 `Cut / Copy / Paste / Zoom In / Zoom Out / Fit / Reset Pan`을 기본으로 둔다. 선택 영역이 있을 때는 `Deselect / Invert / Fill / Stroke / Transform Selection`을 추가한다.

### View

- Zoom In
- Zoom Out
- Fit on Screen
- Actual Size
- Pan
- Show Grid
- Show Guides
- Show Rulers
- Show Checkerboard
- Snap

### Image

- Image Size
- Canvas Size
- Crop
- Trim Transparent Pixels
- Rotate 90 CW/CCW
- Flip Horizontal/Vertical
- Levels
- Curves
- Brightness/Contrast
- Hue/Saturation
- Color Balance

Image/Color 보정은 기존 Color Grading 모듈과 최대한 재사용한다.

### Layer

- New Layer
- Duplicate Layer
- Rename Layer
- Delete Layer
- Show/Hide Layer
- Lock Layer
- Layer Opacity
- Blend Mode
- Merge Down
- Merge Visible
- Flatten Image
- Group Layers
- Add Layer Mask
- Apply Layer Mask

1차 구현은 `New / Duplicate / Rename / Delete / Show/Hide / Lock / Opacity / Blend Mode`까지다.

### Select

- Select All
- Deselect
- Reselect
- Invert
- Feather
- Expand
- Contract
- Grow Similar
- Transform Selection
- Save Selection as Channel
- Selection to Path

선택 영역은 실제 픽셀 편집 범위를 제한해야 한다. 브러시, 지우개, Fill, Stroke, Color Adjustment가 모두 선택 영역을 존중해야 한다.

### Path

- New Work Path
- Save Work Path
- Delete Path
- Duplicate Path
- Rename Path
- Path to Selection
- Selection to Path
- Stroke Path
- Fill Path
- Close Path

Paths 패널에서는 선택된 path가 stack으로 보이고, 선택한 path를 selection으로 변환할 수 있어야 한다.

### Filter

초기에는 최소 범위로 둔다.

- Blur
- Sharpen
- Noise
- Pixelate
- Stylize

1차 구현 범위에서는 UI placeholder와 action 설계만 둔다. 실제 필터 엔진은 색 보정/레이어 안정화 이후 진행한다.

### Window

- Layers
- Channels
- Paths
- History
- Brush Presets
- Color
- Swatches
- Adjustments
- Navigator
- Reset Workspace

우리가 독/분리 독립이 가능한 구조를 갖고 있으므로, 각 패널은 향후 dock/popout이 가능해야 한다.

## 패널 상세

### Layers 패널

필수 기능:

- 눈 아이콘으로 표시/숨김
- lock 아이콘
- layer thumbnail
- layer name
- opacity
- blend mode
- double-click rename
- drag reorder
- context menu
- background layer 삭제 시 checkerboard 표시

하단 operation bar:

- New Layer
- Duplicate
- Add Mask
- Adjustment Layer
- Delete

### Channels 패널

필수 기능:

- RGB composite
- Red
- Green
- Blue
- Alpha
- Mask / Saved Selection
- 각 채널 앞 눈 아이콘
- 단일 채널 grayscale preview
- channel to selection
- selection to channel

1차는 눈 아이콘 토글과 RGB/Alpha 표시 제어까지다. 2차에서 saved selection channel을 추가한다.

### Paths 패널

필수 기능:

- Work Path
- Saved Path stack
- Selection Path
- path thumbnail 또는 간단한 curve icon
- double-click rename
- Path to Selection
- Selection to Path
- Stroke Path
- Fill Path
- Delete Path

### History 패널

필수 기능:

- Undo stack 표시
- 사용자가 과거 상태를 클릭해 되돌아갈 수 있음
- 중요한 action 이름 표시
- AI가 만든 변경은 `AI: ...` prefix로 표시

## 데이터 모델

### Document

- canvas width/height
- background mode: white, dark, transparent, imported image
- layers
- channels
- paths
- history
- selection
- metadata

### Layer

- id
- name
- type: pixel, adjustment, text, shape, group
- visible
- locked
- opacity
- blend mode
- pixel buffer or stroke list
- mask

### Selection

- type: none, raster mask, vector path
- polygon/path points
- feather
- bounds
- marching ants phase

### Path

- id
- name
- points
- closed
- visible
- selected

## AI/Automation Action 설계

Painter 기능은 로컬 AI, Claude, MCP, review automation이 조작할 수 있어야 한다.

필수 action:

- `paint.document.new`
- `paint.document.open_image`
- `paint.document.export_png`
- `paint.view.zoom`
- `paint.view.pan`
- `paint.layer.add`
- `paint.layer.rename`
- `paint.layer.delete`
- `paint.layer.duplicate`
- `paint.layer.set_visible`
- `paint.layer.set_locked`
- `paint.layer.set_opacity`
- `paint.layer.set_blend_mode`
- `paint.selection.select_all`
- `paint.selection.deselect`
- `paint.selection.invert`
- `paint.selection.feather`
- `paint.selection.fill`
- `paint.selection.stroke`
- `paint.selection.to_path`
- `paint.path.create`
- `paint.path.rename`
- `paint.path.delete`
- `paint.path.to_selection`
- `paint.channel.set_visible`
- `paint.channel.selection_to_alpha`
- `paint.adjust.levels`
- `paint.adjust.curves`
- `paint.adjust.hue_saturation`

AI 적용 방식:

- AI는 바로 destructive edit를 하지 않는다.
- 먼저 preview/report를 만든다.
- 사용자는 전체 적용, 부분 적용, 취소를 선택한다.
- History에는 AI 변경 목록이 남아야 한다.

## 구현 우선순위

### Phase 1: Photoshop식 기본 조작 안정화

- 상단 메뉴바 추가
- 캔버스 pan/zoom/context menu 안정화
- 레이어 double-click rename
- Layers/Channels/Paths/History 탭 정리
- 오른쪽 패널 겹침 방지
- 창 resize 대응

완료 기준:

- 1100x640부터 4K 대형 화면까지 UI 요소가 겹치지 않는다.
- 레이어/채널/패스 기본 조작이 테스트된다.
- screenshot QA를 남길 수 있다.

### Phase 2: Select/Path 실사용화

- Select 메뉴 추가
- Deselect/Invert/Feather/Expand/Contract
- Path to Selection
- Selection to Path
- Stroke Path
- Fill Path
- 선택 영역 기반 Delete/Fill/Brush 제한

완료 기준:

- 선택 영역 안에서만 brush/fill/delete가 적용된다.
- path stack에서 선택한 path를 selection으로 변환할 수 있다.

### Phase 3: Layer 편집 강화

- drag reorder
- blend mode
- layer mask
- group layer
- merge down
- flatten image
- layer thumbnail

완료 기준:

- Photoshop 사용자 기준으로 레이어 패널이 기본 작업을 막지 않는다.

### Phase 4: Color / Adjustment

- Levels
- Curves
- Hue/Saturation
- Brightness/Contrast
- Color Balance
- adjustment 적용 범위: selection / layer / document

완료 기준:

- 기존 Color Grading 모듈의 시각 언어와 계산 로직을 재사용한다.
- preview와 apply가 분리된다.

### Phase 5: Export / Project 저장

- PNG export
- transparent PNG export
- selection PNG export
- `.tpaint` project 저장
- reopen

완료 기준:

- 작업을 닫았다 열어도 layer/path/selection/history가 보존된다.

### Phase 6: AI Painter

- 자연어 편집: "배경 투명하게", "이 레이어만 밝게", "선택 영역 색 바꿔"
- preview/report
- 부분 적용
- action history

완료 기준:

- AI가 paint action만 사용해 조작하고, 사용자가 변경 목록을 검토할 수 있다.

## 테스트 / QA

필수 테스트:

- `tests/test_painter_new_canvas.py`
- resize overlap test
- channel eye toggle test
- path to selection test
- layer rename test
- canvas context menu test
- export transparent PNG test

필수 시각 QA:

- small window: 1100x640
- desktop: 1300x880
- large monitor: 2560x1440
- transparent canvas checkerboard
- many layers / many paths
- right panel scroll state

## 현재 상태 메모

이미 들어온 것:

- Standalone Painter 진입
- New Canvas 템플릿
- 말풍선/스티커/Editor Object/Cutout 숨김
- Photoshop식 왼쪽 툴바 방향
- Layers/Channels/Paths 탭
- Background 삭제 시 checkerboard
- path double-click selection
- marching ants
- pan tool
- canvas right-click `Copy / Cut / Paste / Zoom`
- layer double-click rename
- channel eye toggle
- selected path to selection
- window resize 가능
- 오른쪽 인스펙터 overlap 방지

다음 작업 후보:

1. 상단 메뉴바 추가
2. History 탭 추가
3. Select 메뉴와 선택 영역 기반 Fill/Delete
4. Path 메뉴와 Stroke/Fill Path
5. Layer thumbnail / drag reorder
6. Levels/Curves UI 연결
