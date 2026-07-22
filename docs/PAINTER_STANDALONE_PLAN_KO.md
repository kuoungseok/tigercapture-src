# TigerCapture Standalone Painter 기획서

## 목적

TigerCapture Paint를 영상 프레임 위에 간단히 주석을 그리는 도구에서,
독립 실행 가능한 Photoshop형 2D Painter/이미지 편집 도구로 확장한다.

Video Paint는 계속 영상 위 주석, 말풍선, PNG 스티커, Editor Object, Cutout
같은 영상 보조 기능을 담당한다. Standalone Painter는 빈 캔버스, 레이어,
채널, 패스, 선택 영역, 브러시, 컬러/레벨 보정, PNG export를 중심으로 둔다.

## 조사 기준

- Adobe Photoshop: 선택 영역은 편집 범위를 격리하고, Layer Mask는 선택
  영역이나 투명도에서 만들 수 있다. Image 메뉴는 Crop, Canvas Size,
  Image Size, Flip 같은 문서 단위 조작을 제공한다.
- Krita: 브러시는 텍스트 목록보다 브러시 팁/프리셋 썸네일로 고르는 흐름이
  중요하며, 브러시 프리셋은 팁, 질감, 엔진 설정, 미리보기를 포함한다.
- GIMP: 기본 도구 상자는 선택, 페인트, 변형, 색상 선택, 줌, 패스, 크롭
  도구를 카테고리별로 제공한다. 사각/원형 선택과 패스 패널은 기본 편집
  흐름이다.
- Photopea: Channels 패널은 RGB, 단일 색 채널, 알파/마스크 채널을 눈
  아이콘으로 켜고 끄며, 선택 영역과 채널을 서로 변환하는 흐름을 제공한다.

참고 출처:

- Adobe Photoshop Layer Mask:
  https://helpx.adobe.com/photoshop/desktop/create-masks/layer-masks/add-layer-masks.html
- Adobe Photoshop Crop/Canvas:
  https://helpx.adobe.com/photoshop/desktop/crop-resize-transform/crop-straighten/resize-canvas-using-the-crop-tool.html
- Adobe Photoshop Canvas/Image operations:
  https://helpx.adobe.com/in/photoshop/using/adjusting-crop-rotation-canvas.html
- Krita Brush Tips:
  https://docs.krita.org/en/reference_manual/brushes/brush_settings/brush_tips.html
- Krita Brush Presets:
  https://docs.krita.org/en/reference_manual/resource_management/paintoppresets.html
- GIMP Tools:
  https://docs.gimp.org/3.0/en/gimp-tools.html
- GIMP Rectangle Select:
  https://docs.gimp.org/2.10/en_GB/gimp-tool-rect-select.html
- GIMP Selection Tools:
  https://docs.gimp.org/3.0/eo/gimp-tools-selection.html
- GIMP Copy/Paste design:
  https://developer.gimp.org/core/specifications/copy-paste/
- Photopea Channels:
  https://www.photopea.com/learn/channels

## UI 구조

Standalone Painter의 기본 레이아웃은 Photoshop에 익숙한 사용자를 기준으로 둔다.

- 상단: 메뉴바와 작업 옵션 바
- 왼쪽: 세로 아이콘 툴바
- 중앙: 캔버스, 투명 배경 체크패턴, marching ants 선택 영역
- 오른쪽 상단: Layers / Channels / Paths / History 탭
- 오른쪽 하단: Brush Presets / Color / Adjustments / Navigator 계열 보조 패널

왼쪽 툴바 기본 항목:

- Move / Select
- Pan / Hand
- Rectangular Marquee
- Elliptical Marquee
- Crop
- Mirror Drawing X/Y
- Brush / Pen
- Eraser
- Path / Pen Path
- Zoom

## 메뉴 구조

File:

- New Canvas
- Open Image
- Import Image as Layer
- Export PNG
- Export Transparent PNG
- Close

Edit:

- Undo / Redo
- Copy / Cut / Paste
- Clear / Delete
- Fill / Stroke
- Free Transform
- Preferences

Image:

- Image Size
- Canvas Size
- Crop To Selection
- Trim Transparent Pixels
- Flip Canvas Horizontal / Vertical
- Levels / Curves / Hue/Saturation / Brightness/Contrast

Layer:

- New / Duplicate / Rename / Delete
- Show/Hide
- Lock
- Opacity
- Blend Mode
- Add Mask From Selection
- Add Mask From Path
- Merge Down / Flatten Image

Select:

- Select All
- Deselect
- Invert
- Rectangular Marquee
- Elliptical Marquee
- Free / Square / 16:9 / 4:3 ratio
- Selection To Path
- Path To Selection
- Save Selection As Channel

Path:

- Work Path
- Save Path
- Delete Path
- Path To Selection
- Selection To Path
- Path To Layer Mask

Window:

- Layers
- Channels
- Paths
- History
- Brush Presets
- Color

## 2026-07-23 구현 상태

현재 구현된 핵심:

- Standalone Painter에서 영상 전용 말풍선/스티커/Editor Object/Cutout 버튼은
  숨기고, 독립 페인터에 필요한 세로 아이콘 툴바를 우선 배치한다.
- Brush Presets는 텍스트 행이 아니라 브러시 획 모양을 보여주는 아이콘
  그리드로 표시한다. 이름, 카테고리, 크기, 불투명도는 툴팁으로 제공한다.
- Rectangular / Elliptical Marquee 도구가 있고, 선택 비율은 Free, Square,
  16:9, 4:3을 지원한다.
- 선택 영역은 marching ants로 표시하고, Select All / Deselect / Invert /
  Selection To Path / Path To Selection을 지원한다.
- Path 패널은 Work Path, Selection Path, 저장된 Path 스택을 보여주며,
  선택한 Path를 Selection 또는 Layer Mask로 변환할 수 있다.
- Layer 패널은 Add / Duplicate / Rename / Delete / Visibility / Lock /
  Opacity / Blend Mode를 지원한다.
- Layer Mask는 선택 영역 또는 Path에서 생성할 수 있고, 캔버스 렌더 시 해당
  레이어 스트로크를 마스크 경계로 클리핑한다.
- Channels 패널은 RGB, Red, Green, Blue, Alpha 눈 아이콘 토글을 제공한다.
  선택 채널의 이미지 복사와 클립보드 이미지를 특정 채널로 붙여넣는 기능을
  제공한다.
- Image 메뉴는 Image Size, Canvas Size, Crop To Selection, Flip Canvas
  Horizontal / Vertical을 제공한다.
- Canvas right-click 메뉴는 Copy / Cut / Paste, Select All / Deselect,
  Crop To Selection, Zoom In / Out / Fit / Reset Pan을 제공한다.
- Pan, zoom, window resize, checkerboard transparent background를 지원한다.

## AI/Automation Action 계약

Painter 기능은 로컬 AI, Claude, MCP, review automation이 직접 조작할 수 있어야 한다.

구현된 action:

- `paint.state`
- `paint.document.new`
- `paint.document.export_png`
- `paint.view.zoom`
- `paint.view.pan`
- `paint.tool.set`
- `paint.window.show_panel`
- `paint.layer.add`
- `paint.layer.select`
- `paint.layer.rename`
- `paint.layer.duplicate`
- `paint.layer.delete`
- `paint.layer.set_visible`
- `paint.layer.set_locked`
- `paint.layer.set_opacity`
- `paint.layer.set_blend_mode`
- `paint.layer.mask_from_selection`
- `paint.layer.mask_from_path`
- `paint.channel.select`
- `paint.channel.set_visible`
- `paint.channel.copy_image`
- `paint.channel.paste_image`
- `paint.selection.select_all`
- `paint.selection.deselect`
- `paint.selection.invert`
- `paint.selection.rectangle`
- `paint.selection.ellipse`
- `paint.selection.set_aspect`
- `paint.selection.to_path`
- `paint.path.to_selection`
- `paint.path.create`
- `paint.path.delete`
- `paint.path.clear`
- `paint.path.commit`
- `paint.crop.to_selection`
- `paint.image.resize`
- `paint.canvas.resize`
- `paint.canvas.flip`
- `paint.mirror.set`
- `paint.clipboard.copy`
- `paint.clipboard.cut`
- `paint.clipboard.paste`

AI 적용 원칙:

- destructive edit는 바로 적용하지 않고 preview/report 또는 History entry를 남긴다.
- 선택/패스/마스크/채널을 명시적으로 action 상태에 노출한다.
- 실패 가능한 작업은 조용히 성공 처리하지 않고 실패 이유를 반환한다.

## 남은 구현 우선순위

1. 선택 영역 제한 브러시/지우개/Fill/Delete
2. Lasso, Polygonal Lasso, Magic Wand, Color Range
3. Crop overlay handles와 crop option bar
4. Layer thumbnail, drag reorder, group, merge down, flatten image
5. Levels, Curves, Hue/Saturation, Brightness/Contrast UI와 기존 Color Grade 모듈 재사용
6. Save Selection as Channel, Channel to Selection, Alpha mask round-trip
7. `.tpaint` 프로젝트 저장/재열기와 PSD/Photopea 호환 export 후보 조사
8. Brush engine 확장: texture brush, imported brush tip, pressure profile
9. Ruler, guide, snap, grid, navigator
10. Keyboard parity: M, Shift+M, B, E, C, P, V, H, Z

## QA 기준

필수 테스트:

- `tests/test_painter_new_canvas.py`
- `tests/test_painter_actions.py`
- `tests/test_drawing_editor_object_import.py`

필수 수동/시각 QA:

- 1100x640 small window
- 1300x880 desktop
- 2560x1440 large monitor
- transparent canvas checkerboard
- many layers / many paths
- right panel scroll state
- channel copy/paste
- path-to-mask and selection-to-mask clipping

## 구현 경계

- Painter 기능은 `app/drawing.py`와 `app/actions/paint_namespace.py`,
  `app/actions/editor_adapter_paint.py`에 둔다.
- `app/video_editor_window.py`에는 새 Painter 로직을 넣지 않는다.
- Video Paint의 영상 주석 기능과 Standalone Painter의 독립 이미지 편집 기능은
  UI 노출만 다르게 하고, 가능한 한 같은 데이터 구조와 export 경로를 공유한다.
