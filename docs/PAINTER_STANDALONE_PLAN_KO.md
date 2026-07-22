# Standalone Painter Product Plan

## 목표

TigerCapture Paint를 영상 프레임 주석 도구에서 독립 제작 앱으로 확장한다. 영상 Paint 모드는 빠른 말풍선/스티커/프레임 주석에 남기고, Standalone Painter는 빈 캔버스, 선택 영역, 드로잉 레이어, 포토샵식 컬러 편집을 중심으로 둔다.

## 모드 분리

- Video Paint: 현재 영상 프레임 위에 그리기, 말풍선, PNG 스티커, Editor Object, Cutout 유지.
- Standalone Painter: 빈 캔버스 기반. 말풍선/스티커/Editor Object/Cutout은 숨김. 레이어, 선택 영역, 브러시, 컬러 편집, PNG export 중심.

## New Canvas

- `New`를 누르면 캔버스 템플릿 다이얼로그를 먼저 띄운다.
- 기본 템플릿:
  - Full HD 16:9 `1920x1080`
  - HD 16:9 `1280x720`
  - 4K UHD `3840x2160`
  - Square `1080x1080`
  - Vertical `1080x1920`
  - A4 Portrait `2480x3508`
  - A4 Landscape `3508x2480`
- Custom width/height 입력을 지원한다.
- 배경은 White, Transparent, Dark 중 선택한다.

## Path Selection

- Standalone Painter의 `Path`는 `Path / Selection`으로 동작한다.
- 클릭으로 포인트를 찍고 더블클릭하면 닫힌 선택 영역으로 변환한다.
- 완료된 선택 영역은 Photoshop식 marching ants 애니메이션으로 표시한다.
- 선택 영역 UI는 export PNG에 포함하지 않는다.
- 단축키:
  - `Esc`: 작성 중인 path 취소
  - `Ctrl+D`: 선택 해제
  - `Delete`: 선택 영역 내부 삭제

## Layers

- Painter에서는 레이어가 핵심 기능이다.
- 1차는 기존 stroke 묶음을 `Drawing Layer 1`로 표시한다.
- 이후 단계에서 다중 드로잉 레이어를 지원한다.
- 각 레이어는 표시/숨김, 잠금, 불투명도, 이름 변경, 위/아래 이동을 갖는다.
- Video Paint의 말풍선/스티커 레이어는 Standalone Painter에는 노출하지 않는다.

## Color Editing

- 색 변경은 단순 컬러 피커로 끝내지 않는다.
- 기존 Color Grading 모듈을 재사용 가능한 `Painter Color Adjustments`로 연결한다.
- Painter 기본 색 보정:
  - Levels: Input Black, Gamma, Input White, Output Black, Output White
  - Curves: RGB curve, channel curve
  - Exposure / Contrast / Saturation / Temperature / Tint
  - Hue/Saturation
  - LUT 적용과 강도 조절
- 적용 단위:
  - 선택 영역
  - 현재 레이어
  - 전체 캔버스
- UI는 `Adjustments` 탭으로 분리하고, 기존 Color workspace의 스코프/그래프 시각 언어를 재사용한다.

## Icon Direction

- 현재 작은 도구 설명형 아이콘은 문서 생성용 임시 아이콘처럼 보인다.
- 프로그램 탭에서 사용한 앱 아이콘 스타일을 Painter에도 적용한다.
- 방향:
  - 둥근 컬러 타일
  - 흰색 심볼
  - 적은 색 수와 낮은 채도
  - 도구별로 형태가 명확한 실루엣
- 툴 버튼은 텍스트보다 아이콘이 먼저 읽히게 하고, 텍스트는 보조 라벨로 둔다.

## 구현 순서

1. Standalone Painter 진입점과 New Canvas 다이얼로그.
2. Standalone 모드에서 말풍선/스티커/Editor Object/Cutout 숨김.
3. Path double-click selection과 marching ants overlay.
4. 레이어 패널을 Painter용 Drawing Layer 중심으로 개편.
5. Levels / 기본 color adjustment 적용.
6. 기존 Color Grading UI/engine 재사용.
7. Painter 전용 앱 아이콘 세트 적용.

## AI/Automation 대응

- `paint.new_canvas`
- `paint.selection.path_commit`
- `paint.selection.clear`
- `paint.selection.delete_inside`
- `paint.layer.add`
- `paint.layer.set_opacity`
- `paint.layer.move`
- `paint.adjust.levels`
- `paint.adjust.color_grade`

AI는 변경을 바로 적용하지 않고 preview/report를 제공한 뒤 적용하도록 한다.
