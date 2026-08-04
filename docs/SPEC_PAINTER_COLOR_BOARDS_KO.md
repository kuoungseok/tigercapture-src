# Painter Painting Color Boards

상태: 2026-07-31 구현 및 로컬 캡처 검증 완료

상위 공용 색상 기획은 `SPEC_TIGER_SHARED_COLOR_PALETTE_KO.md`를 따른다.
이 문서는 Painter의 **Painting 모드 표현 방식**만 정의한다.

## 1. 참조 이미지 해석

- 사진 1: 기본 `Color Control`
  - 큰 원형 컬러 휠
  - Harmony, 최근 색상, 고정/문서 색상
  - 정밀 SV/Hue 필드와 현재 색상 값
- 사진 2: Motion Designer 등에서 사용하는 포트레이트형 색상 선택 UI
  - 따뜻한 흰색 카드 안에 컬러 소재를 표시
  - 이미지가 아니라 직접 선택 가능한 Qt 버튼으로 렌더링
- 사진 3: `Presets`
  - Skin Tone에 한정하지 않는 팔레트 팩 목록
  - 이름, 용도, 색상 그리드를 한눈에 선택
- 사진 4: `Brush Texture`
  - 실제 물감처럼 두께와 능선이 읽히는 붓질 미리보기
  - 현재 브러시 스타일과 Hardness를 반영

사진 3과 사진 4의 역할을 뒤바꾸지 않는다.

## 2. 정보 구조

탭 노출 순서는 다음과 같다.

1. `Presets`
2. `Color Control`

앱이 처음 표시할 기본 탭은 `Color Control`이다. 순서는 탐색 구조이고,
기본 탭은 가장 자주 쓰는 직접 색상 조작을 우선한다.

## 3. 프로그램별 포트레이트 표현

- `Depth Preview` 탭은 제공하지 않는다.
- Painting은 `Presets`와 `Color Control`을 사용한다.
- Motion Designer처럼 작은 색상 칩만 제공하던 도구는 흰 포트레이트 카드
  안에 실제 색상 소재가 들어간 선택 버튼을 사용한다.
- 포트레이트 카드는 Qt가 직접 그리며 선택, hover, 현재색 동기화를 지원한다.
- 생성 이미지, 미리 렌더링한 PNG 또는 AI 이미지 파일을 UI에 붙이지 않는다.

## 4. Presets

초기 내장 팩:

- Oil Colour Studies — 30색, 3열×10행, Material Paint 연동
- Skin Tones — 30색, 6열×5행
- Vibrant Contrast
- Botanical Study
- Cinematic Night

각 팩은 따뜻한 흰색 바탕의 독립 카드로 표현한다. 카드 안에는 제목,
색상 수와 용도, 색상 순서가 함께 들어간다. Skin Tones의 색상은 참고 이미지처럼
둥글고 약간 불규칙한 물감 자국 형태로 표시하되, 이미지 파일이 아니라
직접 클릭할 수 있는 Qt 버튼으로 그린다. 좁은 인스펙터에서는 한 카드가 가로폭에
맞고, 여러 카드는 세로로 스크롤한다.

`Oil Colour Studies`는 사진 4의 두꺼운 유화 물감 배열을 재질 카드로 구현한다.
색상 버튼 자체에는 높이감이 읽히는 하이라이트와 능선을 그리며, 버튼을 선택하면
단순 RGB 선택에 그치지 않고 `Material Paint` 레이어, `Palette Knife` 브러시,
Load/Thickness/Wetness/Gloss/Roughness 프로필을 함께 활성화한다. 실제 캔버스의
질감은 이미지에 구운 가짜 효과가 아니라 스트로크에서 생성되는 Height·Normal·
Roughness·AO 채널을 사용한다. PBR 조명 미리보기와 PBR 맵 내보내기에서도 동일한
네이티브 채널을 사용해야 한다.

`Palette Knife`는 일반 브러시에서 재질 카드로 처음 진입할 때 사용하는 기본값일
뿐이다. 사용자가 Impasto, Loaded Oil, Bristle, Wet Oil, Dry Oil 등 Material
호환 브러시를 선택한 뒤 카드의 다른 색을 고르면 현재 브러시 스타일을 유지하고
색상과 재질 프로필만 갱신한다. 색상 선택이 매번 브러시를 Palette Knife로
되돌려서는 안 된다.

Normal과 AO는 Painter 전용 중복 알고리즘을 만들지 않고 기존 AR/PBR Texture Lab의
공용 Height→Normal/AO 단계를 사용한다. 재질 붓은 선택한 DirectX/OpenGL 포맷과
Normal 강도·반경·필터를 따라야 하며, 이미지 Height와 붓 Height를 합친 뒤 최종
Normal을 다시 생성한다. 라이브 붓질과 펜을 뗀 확정본은 같은 Brush Engine v2와
같은 결정적 시드를 사용해야 한다.

팩 헤더는 팔레트 묶음을 선택하고, 개별 스와치 선택은 Painter의 현재
브러시 색상에 즉시 적용한다. Gradient/Pattern 채우기 기능은
제거하지 않고 Presets 하단의 `Canvas Fill` 도구로 유지한다.

## 5. Color Control

- 사진 1과 같은 큰 `PainterColorDisc`를 주 조작기로 사용한다.
- 빨강은 오른쪽, 초록은 위쪽, 청록은 왼쪽, 보라/핑크는 아래쪽에 둔다.
- 기존 링+삼각형 및 사각 SV/Hue 필드는 기본 화면에서 노출하지 않는다.
- 상단 현재/이전 색상 2칸, Harmony 선택, 디스크, 흑백 밝기 슬라이더,
  History/Clear, 이름 있는 10×2 팔레트 순서를 유지한다.
- Harmony 파생색, Recent Colors, Pinned/Document, Pin Current,
  Touch Targets를 같은 화면에서 제공한다.
- 색 선택은 기존 `_apply_pen_color` 경로를 사용하여 캔버스, 툴바,
  최근 색상과 동기화한다.

## 6. 붓 성능 계약

- 태블릿의 `tabletEvent`, 스트로크 샘플, GPU/CPU 스탬프 루프에는 팔레트
  또는 프리뷰 계산을 추가하지 않는다.
- 포트레이트 카드 갱신은 색상/선택 상태가 바뀔 때만 발생한다.
- 스트로크 중 파일 I/O, 팔레트 저장, 이미지 생성, AI 호출은 금지한다.
- `tests/test_painter_stroke_latency_guards.py`를 계속 통과해야 한다.

## 7. 구현 및 증거

- UI: `app/painter_color_boards.py`
- 연결: `app/drawing.py`
- 계약 테스트: `tests/test_painter_color_boards.py`
- 회귀/성능 테스트:
  - `tests/test_painter_palette_workflow.py`
  - `tests/test_painter_stroke_latency_guards.py`
- 캡처: `tools/qa_painter_color_boards.py`
- 재생성 산출물:
  `debugCapture/painter_color_boards/painter_color_boards.png`
