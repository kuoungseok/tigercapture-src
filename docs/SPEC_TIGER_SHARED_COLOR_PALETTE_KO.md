# Tiger Studio 공용 컬러 팔레트 기획서

상태: **제품 기획 / 구현 전 기준 문서**

문서 버전: `v0.1`

작성일: 2026-07-31

대상:

- Painter 페인팅 모드
- Painter UI Design 모드
- Motion Designer
- 향후 Tiger Studio의 색상을 사용하는 모든 제작 도구

## 1. 한 줄 정의

Tiger Color Library는 하나의 공용 색상 자산을 여러 프로그램이 공유하되,
각 프로그램은 작업 목적에 맞는 팔레트 UI와 상호작용만 노출하는 시스템이다.

```text
                         Tiger Color Core
        색상 ID · 저장 · 색공간 · 연결 · 팩 · 검색 · 이력 · 변환
                                  |
              +-------------------+-------------------+
              |                   |                   |
       Painting Adapter     UI Design Adapter    Motion Adapter
              |                   |                   |
       Quick Palette         Token/Theme UI      Timeline Palette
```

공용화의 대상은 UI 모양이 아니라 **데이터와 의미**다.

## 2. 배경과 문제

현재 Painter에는 최근색, 고정색, 문서색, 색상 하모니, 이미지 팔레트 추출,
퀵 팔레트가 있다. Painter UI Design에는 컬렉션, 모드, 별칭, 스코프를 갖는
UI 토큰이 있다. Motion Designer에는 별도의 프로젝트 색상 및
SDR/HDR/ACES·OCIO 출력 관리가 있다.

각 기능은 유용하지만 다음 문제가 남아 있다.

- 같은 브랜드색을 Painter와 Motion Designer에 반복 입력해야 한다.
- Painter 페인팅 색상과 Painter UI 토큰이 서로 다른 자산처럼 취급된다.
- 색을 수정했을 때 연결된 UI 오브젝트와 모션 레이어를 함께 갱신할 수 없다.
- 판매·공유되는 Procreate식 팔레트 팩을 프로젝트 공용 자산으로 다룰
  표준 형식이 없다.
- 작가용 색상 선택과 UI 디자이너용 의미 토큰이 한 패널에 섞이면
  양쪽 모두 사용성이 나빠진다.
- 팔레트 저장이나 동기화가 페인팅 입력 경로에 들어가면 붓질 지연을
  유발할 수 있다.

## 3. 제품 목표

### 3.1 필수 목표

1. Painter, Painter UI Design, Motion Designer가 동일한 색상 ID와
   팔레트 팩을 공유한다.
2. 프로그램과 작업 모드에 따라 서로 다른 UI를 제공한다.
3. 사용자는 색상을 **연결해서 사용**하거나 **독립 복사해서 사용**할 수 있다.
4. 전역, 프로젝트, 문서 범위를 명확히 구분한다.
5. 일반 Palette Pack과 역할 기반 Smart Palette Pack을 모두 지원한다.
6. Painter에서는 브러시와 팔레트를 안전하게 연동할 수 있다.
7. 페인팅 스트로크 입력과 디스크·네트워크·팔레트 계산을 분리한다.
8. Light, Dark, High Contrast, SDR, HDR, Print 같은 모드별 값을
   한 색상 자산 아래에서 관리할 수 있다.
9. 색역, 대비, 출력 조건의 문제를 적용 전에 설명한다.
10. 기존 Painter 팔레트와 Painter UI 토큰을 손실 없이 이행한다.

### 3.2 성공 경험

사용자가 전역 라이브러리의 `Tiger Blue`를 프로젝트에 연결하고
`action.primary` 역할로 사용하면 다음이 가능해야 한다.

- Painter에서는 일반 파란색 스와치처럼 빠르게 선택한다.
- Painter UI Design에서는 버튼, 선택 탭, 포커스 링에 연결된
  의미 토큰으로 표시한다.
- Motion Designer에서는 Fill, Stroke, Text, Glow 색상에 연결하고
  키프레임 가능 상태를 표시한다.
- 원본을 수정하면 연결을 유지한 대상만 갱신된다.
- 독립 복사한 대상과 절대 색상 키프레임은 변경되지 않는다.

## 4. 비목표

초기 버전은 다음을 목표로 하지 않는다.

- 하나의 거대한 컬러 패널을 모든 프로그램에 강제한다.
- 외부 팔레트 마켓이나 결제 시스템을 즉시 구축한다.
- 색상 이름만으로 완성된 그림이나 UI를 자동 생성한다.
- 모든 Painter 픽셀을 즉시 wide-gamut/ACES 네이티브 저장으로 전환한다.
- 클라우드가 없으면 팔레트를 사용할 수 없게 만든다.
- 브러시를 선택할 때마다 사용자의 현재색을 강제로 변경한다.
- 지원하지 않는 출력 색을 조용히 근사하거나 누락한다.

## 5. 우수 사례와 채택 원칙

### 5.1 Adobe Creative Cloud Libraries

참고:
<https://helpx.adobe.com/in/creative-cloud/apps/create-and-manage-libraries/create-and-organize-libraries/libraries-overview.html>

채택:

- 여러 제작 프로그램이 하나의 프로젝트·브랜드 라이브러리를 공유한다.
- 팔레트, 그래픽, 스타일을 프로젝트 단위로 관리한다.

개선:

- Tiger에서는 색을 단순 열람하는 수준을 넘어 안정적인 색상 ID로 연결한다.

### 5.2 Figma Variables

참고:
<https://help.figma.com/hc/en-us/articles/14506821864087-Overview-of-variables-collections-and-modes>

채택:

- Primitive와 Semantic 색상을 분리한다.
- 컬렉션, 그룹, 모드, 별칭, 적용 스코프를 제공한다.
- Light/Dark 같은 상황별 값을 하나의 논리적 토큰으로 관리한다.

### 5.3 Krita Pop-up Palette

참고:
<https://docs.krita.org/en/reference_manual/popup-palette.html>

채택:

- 펜 위치에서 색상, 최근색, 브러시에 접근한다.
- 캔버스와 시선을 떠나지 않는 입력 흐름을 우선한다.

개선:

- 색상과 브러시 선택을 기본 링에 유지하고 회전·확대 같은 Canvas Pose
  조작은 혼잡하지 않도록 보조 링 또는 별도 제스처로 분리한다.

### 5.4 Procreate

참고:
<https://help.procreate.com/procreate/handbook/5.0/colors/colors-harmony>

채택:

- 현재색과 이전색을 즉시 비교한다.
- 터치하기 쉬운 크기와 단순한 탭 구조를 사용한다.
- 색상 하모니와 팔레트 저장 진입을 짧게 만든다.

### 5.5 Clip Studio Paint

참고:
<https://help.clip-studio.com/en-us/manual_en/300_color/Color_Set_palette.htm>

채택:

- Color Set, History, Intermediate, Approximate, Mixing을 목적별로 나눈다.
- 스포이드 색 자동 등록과 팔레트 파일 교환을 지원한다.
- 타일 크기와 열 수를 작업 환경에 맞게 조절한다.

### 5.6 Affinity Global Colours

참고:
<https://s3-eu-west-1.amazonaws.com/affinity-docs/help/designer/English.lproj/pages/Panels/swatchesPanel.html>

채택:

- Document, Application 범위를 구분한다.
- Global Colour 수정이 연결된 오브젝트에 전파된다.
- 일반색, 전역 연결색, 별색을 시각적으로 구분한다.

### 5.7 Radix Colors와 IBM Carbon

참고:

- <https://www.radix-ui.com/colors/docs/palette-composition/scales>
- <https://carbondesignsystem.com/elements/themes/overview/>

채택:

- 명도 단계와 Light/Dark/Alpha 변형을 체계화한다.
- 실제 색상값과 `text.primary`, `surface.raised`, `action.primary` 같은
  역할 토큰을 분리한다.
- 테마가 바뀌어도 역할 이름은 유지한다.

## 6. 핵심 개념

### 6.1 Color Asset

재사용 가능한 하나의 논리적 색상이다.

필수 속성:

- 안정적인 `color_id`
- 표시 이름
- 원본 색상값과 색공간
- sRGB 안전 미리보기 값
- 태그와 그룹
- 색상 역할
- 모드별 값
- 별칭 대상
- 제작자 및 출처
- 라이선스와 버전

### 6.2 Primitive Color

실제 색상값에 가까운 기초 색상이다.

예:

```text
blue.050
blue.500
blue.700
neutral.900
```

### 6.3 Semantic Color

사용 목적을 나타내며 Primitive 또는 다른 Semantic Color를 참조한다.

예:

```text
action.primary    -> blue.600
text.primary      -> neutral.950
surface.canvas    -> neutral.050
status.danger     -> red.600
```

Semantic Color를 이용해야 테마와 브랜드를 교체해도 오브젝트의 의미가
유지된다.

### 6.4 Palette

작업자가 선택하기 좋게 배열한 색상 모음이다. 순서, 그룹, 타일 크기,
표시 이름을 가질 수 있지만 반드시 역할 토큰일 필요는 없다.

### 6.5 Palette Pack

설치·공유·내보내기가 가능한 색상 패키지다.

두 종류를 제공한다.

#### General Palette Pack

- 자유롭게 선택하는 색상 타일 집합
- Painting에서 기본적으로 독립 복사
- 예: Skin Tones, Autumn Forest, Pastel, Retro Film, Neon

#### Smart Palette Pack

- 색상마다 역할과 관계가 정의됨
- 기준색 변경, 명도 단계, 테마 변형, 대비 검사가 가능
- UI 토큰과 Motion 속성에 연결 가능
- 예: Brand System, Webtoon Character, Cinematic Night, Broadcast Package

### 6.6 Brush Kit

Painter에서 브러시, 팔레트, 혼합 동작을 하나의 작업 세트로 묶은 자산이다.

```text
Webtoon Skin Kit
  Brushes
    Base Fill
    Soft Shadow
    Blush
  Palette
    Highlight
    Base
    Warm Shadow
    Cool Shadow
    Blush
  Behavior
    recommended
```

## 7. 범위 모델

색상 자산은 세 범위를 가진다.

| 범위 | 설명 | 대표 사례 |
|---|---|---|
| Global | 여러 프로젝트에서 사용하는 개인·브랜드 라이브러리 | 회사 브랜드색, 즐겨찾는 작가 팔레트 |
| Project | Painter와 Motion이 함께 사용하는 현재 프로젝트 색상 | 프로그램 패키지, 캐릭터·장면 색 |
| Document | 특정 `.tspaint`, UI 문서, `.tgmotion`에만 저장 | 작품 중간색, 임시 장면색 |

범위 이동은 항상 두 가지 명령을 구분한다.

- `Link`: 원본 ID와 연결을 유지한다.
- `Copy`: 현재 값을 복제하고 원본과 분리한다.

드래그 앤 드롭 시 기본 정책:

- General Palette Pack에서 Painting으로 드롭: `Copy`
- Smart Palette/Brand 색을 UI 또는 Motion에 드롭: `Link`
- 다른 범위로 이동할 때 사용자가 Link/Copy 기본값을 바꿀 수 있음
- 연결 여부는 체인 아이콘과 툴팁으로 항상 확인 가능

## 8. 공용 데이터 계약

예시 개념 모델:

```json
{
  "schema": "tigerstudio.color-library.v1",
  "library_id": "library-tiger-brand",
  "revision": 12,
  "colors": [
    {
      "color_id": "color-brand-primary",
      "name": "Tiger Blue",
      "kind": "semantic",
      "group": "Brand/Action",
      "tags": ["brand", "action"],
      "source": {
        "space": "srgb",
        "components": [0.20, 0.34, 0.96, 1.0]
      },
      "fallback_srgb": "#3357F5",
      "alias_color_id": "color-blue-600",
      "role": "action.primary",
      "scope": ["fill", "stroke", "text", "glow"],
      "mode_values": {
        "light": {"alias_color_id": "color-blue-600"},
        "dark": {"alias_color_id": "color-blue-400"},
        "high_contrast": {"value": "#1747FF"}
      }
    }
  ],
  "palettes": [],
  "packs": [],
  "brush_kits": []
}
```

### 8.1 안정성 규칙

- `color_id`는 이름 변경이나 그룹 이동으로 바뀌지 않는다.
- 별칭 순환은 저장 전에 차단한다.
- 삭제 전 참조 수와 영향을 보여준다.
- 연결된 색 삭제는 Replace, Detach, Cancel 중 하나를 요구한다.
- 색공간이 다른 값을 단순 RGB 숫자로 재해석하지 않는다.
- 읽을 수 없는 미래 스키마는 조용히 덮어쓰지 않는다.
- 모든 변경은 revision과 수정 시간을 갖는다.

## 9. 프로그램별 UI

## 9.1 Painter 페인팅 모드

목표: **붓질을 멈추지 않고 색을 선택한다.**

기본 노출:

- 전경색과 배경색
- 전경/배경 교환
- 현재색과 이전색 비교
- 최근색
- 고정색
- 현재 문서 팔레트
- 선택된 Palette Pack
- 색상 휠
- Shade/Tint와 하모니
- 스포이드

고급 Color Studio:

- Picker
- Harmony
- Intermediate/Approximate Color
- Mixing
- Library
- 이미지 팔레트 추출
- 색상값과 색공간

온캔버스 Quick Palette:

- `F6`, 우클릭 또는 펜 배럴 입력으로 포인터 위치에 연다.
- 중앙은 현재 색상 선택에 집중한다.
- 가까운 링에는 최근색·고정색을 둔다.
- 브러시 즐겨찾기는 색상과 시각적으로 구분한다.
- 연결색은 작은 체인 배지로 표시하되 선택 면적을 줄이지 않는다.
- 메뉴를 닫으면 포커스가 캔버스로 즉시 돌아간다.
- Quick Palette 호출은 스트로크를 생성하지 않는다.

Painting에서는 기본적으로 기술적인 토큰 이름을 숨긴다. 사용자가
연결 정보나 Smart Palette의 역할을 펼쳤을 때만 표시한다.

## 9.2 Painter UI Design 모드

목표: **색상의 역할, 테마, 연결 영향을 관리한다.**

기본 노출:

- Primitive와 Semantic 전환
- Variable Collection과 Mode
- Color Style
- 이름과 역할
- Fill, Stroke, Text, Effect 스코프
- 별칭 관계
- 현재 모드 값
- 연결 오브젝트 수
- 대비와 색역 경고
- Replace/Detach

대표 계층:

```text
Foundation
  blue.050 ... blue.950
  neutral.000 ... neutral.1000

Semantic
  surface.canvas
  surface.raised
  text.primary
  text.muted
  action.primary
  status.danger
```

Painter UI의 기존 Variable Collection, Mode, Alias, Scope 계약을
대체하지 않는다. Tiger Color Core가 공유 원본을 제공하고 Painter UI
토큰은 문서 안의 안정적인 바인딩을 소유한다.

## 9.3 Motion Designer

목표: **색상을 시간, 장면, 레이어, 출력 조건과 함께 제어한다.**

기본 노출:

- Project/Brand Palette
- 선택 레이어에서 사용 중인 색
- Fill, Stroke, Text, Glow, Material Parameter 대상
- 연결 상태와 참조 수
- 키프레임 가능 표시
- 팔레트 간 전환
- SDR/HDR/출력 색역 미리보기
- 영상·이미지에서 팔레트 추출

표시 예:

```text
Tiger Blue        [linked] [keyframe]
#3357F5
Used by 14 layers
Mode: SDR / Light
```

### 9.3.1 모션 색상 키프레임 규칙

두 종류를 구분한다.

- Absolute Keyframe: 키프레임에 실제 색상값을 저장한다.
- Linked Keyframe: `color_id`와 선택적인 색상 변형을 저장한다.

Linked Keyframe의 변형은 가능한 경우 OKLCH 기준의 명도·채도·색상
오프셋으로 표현한다. 원본 팔레트가 변경되면 참조 기반 키프레임만
새 기준색을 따른다. 사용자는 언제든 `Detach to Absolute`를 실행할 수 있다.

Motion Designer의 working/output color management는 계속 Motion이 소유한다.
공용 라이브러리의 색상은 적용 시 해당 프로젝트의 작업 색공간으로
명시적으로 변환하고, Preview와 Export가 같은 변환 계약을 사용한다.

## 9.4 2026-07-31 공용 피커 UI 1차 구현

공용 Color Core 전체 구현에 앞서 보드별 색상 선택 진입을 일관되게 만드는
첫 UI 슬라이스를 구현했다.

- `app/color_picker_widget.py`가 알파를 포함하는 공용 스와치 피커와
  기존 색상 입력 필드 결합 helper를 제공한다.
- Painter Painting은 기존 전경/배경 스와치와 고급 피커를 계속 사용한다.
- Painter UI Design은 단일·다중 선택의 Fill/Stroke, 텍스트 범위,
  Appearance의 Paint/Gradient Stop/Effect 색상에 피커를 제공한다.
- Painter UI Design의 선택 요약 바로 아래에는 항상 보이는 공용 스와치
  팔레트와 Fill/Stroke 적용 대상 선택을 제공한다.
- Motion Canvas와 Preview가 공유하는 Viewer Header에 항상 같은 위치의
  공용 스와치 팔레트와 상세 피커를 제공한다.
- Motion 피커는 선택한 Shape의 Fill 또는 Text의 Fill에 적용되며,
  색상을 직접 적용할 대상이 아닌 레이어에서는 비활성화된다.
- 색상과 무관한 보드에 가짜 색상 속성을 생성하지 않는다.

이 구현은 프로그램별 색상 선택 UI의 공통 조작 기반이며, 아직
Global/Project/Document 공유 라이브러리나 Link/Copy/Detach를 완료했다는
의미는 아니다.

검증:

```text
tests/test_shared_color_picker_boards.py
tests/test_painter_ui_inspector_properties.py
tests/test_painter_ui_inspector_multi_properties.py
tests/test_painter_ui_appearance.py
tests/test_motion_designer_ui.py
tests/test_painter_stroke_latency_guards.py
tests/test_editor_architecture_rules.py
```

## 10. 브러시와 팔레트 연동

브러시 프리셋은 다음 연결 정책 중 하나를 선택할 수 있다.

| 정책 | 동작 |
|---|---|
| None | 현재색만 사용 |
| Recommend | 관련 팔레트를 전면에 표시하고 현재색은 유지 |
| Remember | 이 브러시에서 마지막으로 사용한 색을 기억 |
| Fixed | 명시적으로 지정된 색 또는 팔레트로 전환 |
| Derived | 현재색을 기준으로 명도·채도·색상 변형 |
| Multi-slot | 여러 역할 색을 스트로크 중 선택 또는 혼합 |

기본 정책은 `Recommend`다.

`Fixed`는 스탬프, 패턴, 픽셀 브러시처럼 사용자가 결과를 예측할 수 있는
프리셋에만 명시적으로 사용한다.

### 10.1 다중 색상 슬롯

예:

```text
Leaf Brush
  A: Highlight
  B: Base
  C: Shadow
  D: Dry Leaf
```

선택 방식:

- 압력
- 진행 거리
- 텍스처 마스크
- 결정적 난수
- 명시적 슬롯 선택

같은 입력 스트로크와 seed는 같은 색상 선택 결과를 만들어야 한다.

### 10.2 현재색 파생

파생색은 가능한 경우 OKLCH에서 계산하고 화면 sRGB 범위를 벗어나면
chroma를 줄여 표시 가능한 값으로 매핑한다.

예:

```text
lightness: ±0.08
chroma: ±0.03
hue: ±4 degrees
```

현재 Painter의 스트로크/문서 색상 저장은 8-bit sRGB다. 공용 팔레트
도입만으로 Painter가 wide-gamut 픽셀 편집기가 되었다고 주장하지 않는다.

## 11. Palette Pack 분류와 탐색

기본 분류:

```text
My Palettes
Project Palettes
Installed Packs
  People
  Nature
  Materials
  Mood
  Cinematic
  Illustration
  Webtoon & Animation
  UI & Brand
  Print & Accessibility
Generated
Recent
Favorites
```

대표 팩:

- 피부, 머리카락, 눈동자
- 하늘, 바다, 숲, 사계절
- 금속, 목재, 석재, 천
- 파스텔, 뮤트, 빈티지, 레트로
- 네온, 사이버펑크, 판타지, 공포
- 웹툰 인물·배경 채색
- 픽셀아트 제한 팔레트
- 시네마틱 낮·밤·일몰
- 방송 그래픽과 브랜드
- UI Light/Dark/High Contrast
- CMYK/인쇄 확인용
- 색각 다양성 안전 팔레트

검색은 이름뿐 아니라 태그, 색상 근사치, 역할, 제작자, 색공간,
설치 범위를 지원한다.

## 12. 미리보기

Palette Pack 미리보기는 두 단계를 제공한다.

1. 빠른 스와치 그리드
2. 선택적인 적용 예시

적용 예시는 팩 종류에 맞게 다르게 표시한다.

- Painting: 인물, 풍경, 재질 샘플
- UI: 버튼, 텍스트, 표면, 상태 샘플
- Motion: 타이틀 카드, 그래프, 발광, 배경 프레임

예시는 실제 결과물 증거와 구분되는 명확한 `Preview` 표시를 갖는다.

## 13. 색상 관리와 출력

### 13.1 저장과 표시

- Color Asset은 원본 색공간을 명시한다.
- 모든 자산은 UI 탐색을 위한 sRGB fallback을 가질 수 있다.
- fallback은 원본을 대체하지 않는다.
- 적용 대상 프로그램이 지원하지 않는 색공간은 변환 결과와 손실을
  사전에 보여준다.

### 13.2 모드

초기 표준 모드:

- Light
- Dark
- High Contrast
- SDR
- HDR
- Print

모드는 단순 자동 필터가 아니라 동일한 논리적 색상에 대한 명시적 값이다.
필요한 값이 없을 때는 상속 규칙과 fallback 출처를 보여준다.

### 13.3 검사

- UI 텍스트/배경 대비
- 색각 다양성 시뮬레이션
- sRGB/P3/출력 색역 이탈
- HDR 밝기 범위
- 인쇄용 프로파일 미확정
- 투명색과 배경 합성 후 대비

검사는 편집을 차단하는 오류와 권고 경고를 구분한다.

## 14. 가져오기와 내보내기

우선 검토 형식:

- Tiger `.tspalette` / `.tspalettepack`
- Adobe ASE
- Photoshop ACO
- GIMP GPL
- CSS 색상과 CSS Variables
- Figma 변수 JSON 교환
- 일반 JSON/CSV
- Procreate palette 호환 가능성 조사

형식별로 이름, 그룹, 별칭, 모드, 색공간을 모두 보존할 수 있는 것은 아니다.
가져오기 전 preflight에서 보존·변환·누락 항목을 보고한다.

외부 파일을 가져와도 원본을 `debugCapture`에 의존시키지 않는다.
설치된 팩과 필요한 자산은 내구성 있는 Tiger Studio 사용자 라이브러리에
복사하고 manifest와 해시를 저장한다.

## 15. 성능 계약

Painter의 붓질 감각은 다른 모든 팔레트 편의 기능보다 우선한다.

### 15.1 금지 사항

다음 작업은 tablet sample, mouse move, dab 생성 경로에서 실행하면 안 된다.

- JSON 읽기·쓰기
- 파일 해시 계산
- 네트워크 동기화
- 전체 라이브러리 검색
- 토큰 참조 그래프 재계산
- 색상 썸네일 재렌더링
- 대비 검사
- 이미지 팔레트 추출

### 15.2 허용 경로

- 브러시 선택 시 필요한 색상 슬롯을 미리 해석한다.
- 스트로크 시작 전에 작은 불변 메모리 배열과 LUT를 준비한다.
- dab 경로는 캐시된 값과 단순 수치 연산만 사용한다.
- 최근색 등록은 스트로크 종료 시 큐에 넣는다.
- 디스크 저장은 debounce한다.
- 동기화와 참조 전파는 스트로크 종료 후 coalesce한다.
- 썸네일과 검사 결과는 revision 기반 캐시를 사용한다.
- 활성 스트로크 중 외부 변경은 적용 대기 상태로 두고 종료 후 반영한다.

### 15.3 실패 격리

- 라이브러리 저장 실패가 스트로크를 중단하면 안 된다.
- 네트워크가 없어도 로컬 팔레트가 완전히 동작해야 한다.
- 손상된 팩 하나 때문에 전체 라이브러리가 열리지 않는 구조를 금지한다.
- 동기화 충돌은 새 revision으로 보존하고 사용자에게 병합 선택을 제공한다.

## 16. 기존 기능 이행

### 16.1 Painter

현재 `tigerstudio.painter.palette-library.v1`의 다음 값은 보존한다.

- recent colors
- pinned colors
- favorite/recent/custom brushes
- touch target preference
- harmony mode

이행 원칙:

- 기존 파일은 그대로 읽을 수 있다.
- 최초 공용 라이브러리 생성 시 색상과 브러시 데이터를 복사·매핑한다.
- 성공적으로 저장되기 전 기존 파일을 삭제하거나 덮어쓰지 않는다.
- 롤백 시 기존 Painter 동작을 복구할 수 있다.

### 16.2 Painter UI Design

기존 stable-ID 토큰, Variable Collection, Mode, Alias, Scope를 유지한다.
공용 Color Asset을 참조하는 선택적 `shared_color_id` 바인딩을 추가하는
방향으로 이행한다.

### 16.3 Motion Designer

기존 프로젝트 색상과 레이어의 절대 색상값은 변경하지 않는다.
사용자가 명시적으로 연결할 때만 `shared_color_id` 또는 Linked Keyframe을
생성한다.

## 17. 권장 모듈 경계

구현 시 다음과 같이 분리한다.

```text
app/color_library/
  schema.py
  store.py
  resolver.py
  scopes.py
  packs.py
  import_export.py
  color_spaces.py
  search.py
  migration.py

app/painter_color_adapter.py
app/painter_brush_color_binding.py
app/painter_ui_color_adapter.py
app/motion_designer/color_library_adapter.py
```

`app/color_management.py`는 프로젝트 working/output 색상 관리의 공용
기반으로 남는다. 새 라이브러리가 별도의 경쟁 색상 관리 파이프라인을
만들어서는 안 된다.

Painter UI 문서 변경이 Unreal UI 출력의 의미를 바꾸는 경우
provider-neutral Tiger UMG 계약과 `TigerStudioUMG` 변환 경로도 같은
변경에서 갱신해야 한다.

## 18. Action/API 초안

공용 읽기:

```text
color.library.list
color.library.inspect
color.palette.list
color.palette.search
color.color.inspect
color.reference.inspect
color.pack.preflight
```

공용 변경:

```text
color.palette.create
color.palette.update
color.palette.install
color.palette.uninstall
color.color.add
color.color.update
color.color.link
color.color.copy
color.color.detach
color.reference.replace
```

프로그램별 적용:

```text
paint.color.apply
paint.brush.color_binding.set
paint.brush_kit.apply
paint.ui.color.bind
motion.color.bind
motion.color.keyframe.set
```

변경 Action은 dry-run 또는 영향 보고를 제공하고 프로그램의 기존 Undo
경계를 재사용한다. 색상을 적용하기 위해 별도의 숨은 문서 mutation
경로를 만들지 않는다.

## 19. 구현 단계

### P0 — 공용 기반

- 공용 schema, 안정적인 ID, revision
- Global/Project/Document 범위
- Link/Copy/Detach
- 로컬 저장소와 손상 격리
- 기존 Painter 팔레트 읽기 및 무손실 이행
- 공용 검색과 최근/고정색 어댑터

완료 기준:

- Painter와 Motion이 같은 Project Palette를 읽는다.
- 한쪽에서 연결색을 수정하면 다른 쪽의 캐시가 스트로크 외부에서 갱신된다.
- 기존 `.tspaint` 문서가 동일하게 열린다.

### P1 — 프로그램별 UI

- Painting Compact/Quick/Color Studio
- Painter UI Primitive/Semantic/Mode UI
- Motion Project Palette와 사용 대상 표시
- 연결 배지, 참조 수, Replace/Detach
- 태블릿 터치 크기와 키보드 탐색

### P2 — Palette Pack과 Brush 연동

- `.tspalettepack`
- General/Smart Pack
- 태그, 검색, 미리보기
- Brush Recommend/Remember/Derived
- Brush Kit
- 결정적인 Multi-slot 색상

### P3 — 고급 색상과 교환

- Light/Dark/High Contrast/SDR/HDR/Print mode
- 대비·색역 preflight
- ASE/ACO/GPL/CSS/Figma 교환
- Linked Motion Keyframe
- 이미지·영상 팔레트 추출
- 선택적 공유/동기화

## 20. 테스트와 검증

### 데이터

- ID 안정성
- 별칭 순환 차단
- revision 충돌
- 손상된 팩 격리
- Link/Copy/Detach 의미
- 범위 승격과 문서 이식성

### Painter

- 퀵 팔레트 호출이 스트로크를 만들지 않음
- 스트로크 도중 파일 I/O가 없음
- 최근색 저장 실패가 페인팅을 중단하지 않음
- 다중 슬롯이 같은 seed에서 결정적임
- 펜 압력·tilt 경로의 기존 latency guard 유지

### Painter UI

- Collection/Mode/Alias/Scope 호환
- 연결색 변경이 한 Undo 단위로 반영
- 대비 결과가 실제 active mode를 사용
- Unreal UMG 출력의 지원/베이크/차단 결과가 명시적임

### Motion

- Absolute와 Linked Keyframe 분리
- Preview/Export 색상 변환 일치
- SDR/HDR mode fallback 출처 표시
- 링크가 끊긴 색상의 relink 진단

### 접근성

- 키보드만으로 색상 탐색·선택 가능
- 색상 타일에 이름과 값이 제공됨
- 색만으로 Link/Warning/Keyframe 상태를 구분하지 않음
- 터치 타깃 기본값 36 px 이상

## 21. 제품 승인 기준

다음 조건을 만족하기 전 “전 프로그램 공용 컬러 팔레트 완료”라고
표현하지 않는다.

1. 동일한 Project Palette가 Painter, Painter UI, Motion에서 실제로 열린다.
2. 각 프로그램이 서로 다른 전용 UI를 사용한다.
3. Link와 Copy 결과가 저장·재실행 후에도 구분된다.
4. 원본 변경의 영향 대상을 적용 전에 확인할 수 있다.
5. Painter latency guard와 태블릿 입력 검증을 통과한다.
6. Painter UI token mode와 Motion output color management를 손상시키지 않는다.
7. 최소 하나의 General Pack과 Smart Pack이 설치·사용·내보내기 된다.
8. 최소 하나의 Brush Kit이 추천 팔레트와 함께 동작한다.
9. 실제 Painter 캡처, UI Design 캡처, Motion 캡처로 같은 색상 ID의
   프로그램별 표현을 증명한다.
10. unsupported 색공간·출력·UMG 기능이 조용히 누락되지 않는다.

## 22. 최종 제품 원칙

> 하나의 색상 원본, 세 가지 작업 경험.

- Painter는 색을 **빠르게 고른다**.
- Painter UI는 색의 **의미와 시스템을 관리한다**.
- Motion Designer는 색을 **시간과 출력 안에서 움직인다**.
- Tiger Color Core는 세 프로그램이 같은 색을 말하고 있다는 사실을
  안정적으로 보장한다.
