# Painter UI 도형 세로 슬라이스 설계

Status: active implementation spec  
Date: 2026-08-02  
Scope: 도형 생성, 프레임 계층, 레이어 표시, 선택 문맥형 Inspector, Motion 진입

## 1. 제품 기준

도형은 캔버스에 그려진 장식 픽셀이 아니라 편집 가능한 UI 레이어다.

- 캔버스는 최상위 프레임과 섹션을 배치하는 무한 작업공간이다.
- 프레임은 도형, 텍스트, 이미지와 중첩 프레임을 소유하는 작업면이다.
- 프레임 안에서 생성한 도형은 자동으로 해당 프레임의 자식이 된다.
- 프레임 밖에서 생성한 도형은 캔버스 최상위 레이어로 남는다.
- 레이어 패널은 `Frame > Rectangle`처럼 실제 부모/자식 관계를 들여쓰기로 표시한다.
- 선택된 레이어 종류가 바뀌면 오른쪽 Inspector의 내용 페이지가 교체된다.

## 2. Figma 조사 결과

Figma의 기본 Shape 도구는 Rectangle, Line, Arrow, Ellipse, Polygon, Star다.
Shift는 정비율, Alt는 중심 기준 생성/리사이즈에 사용된다. 도형 선택 시 캔버스에는
바운딩 박스, 리사이즈 핸들, 크기 배지가 표시된다.

프레임은 컨테이너 레이어다. 프레임 안에서 생성한 레이어는 child가 되고, 중첩
프레임은 parent이면서 child가 된다. 최상위 프레임만 캔버스에 이름을 표시한다.

오른쪽 Properties panel은 하나의 고정 폼이 아니다. 선택 없음, 프레임, 도형,
텍스트, 컴포넌트, 다중 선택 문맥에 따라 위치/크기, 레이아웃, 외형, 채우기,
외곽선, 효과, 내보내기 같은 관련 섹션만 노출한다.

공식 기준:

- [Shape tools](https://help.figma.com/hc/en-us/articles/360040450133-Basic-shape-tools-in-Figma-design)
- [Frames in Figma Design](https://help.figma.com/hc/en-us/articles/360041539473-Frames-in-Figma-Design)
- [Add layers to a frame](https://help.figma.com/hc/en-us/articles/30954388121495-FD4B-Add-your-layers-to-a-frame)
- [Properties panel](https://help.figma.com/hc/en-us/articles/360039832014-Design-Prototype-and-view-Code-in-the-Properties-Panel)
- [Stroke properties](https://help.figma.com/hc/en-us/articles/360049283914-Apply-and-adjust-stroke-properties)

## 3. Inspector 아키텍처

Inspector는 지속되는 shell과 교체되는 content page로 나눈다.

```text
InspectorShell
├─ Header: Design / Prototype / Zoom
└─ SelectionContentStack
   ├─ PagePropertiesPage
   ├─ FramePresetPage
   ├─ FrameSelectionPage
   ├─ ShapeSelectionPage
   ├─ GenericObjectPage
   └─ MultiSelectionPage (후속 분리)
```

선택 변경은 canonical document selection만 변경한다. Inspector가 별도 선택 상태나
별도 속성 모델을 소유하면 안 된다. 각 content page는 동일한
`geometry_changed`, `properties_changed`, `arrange_requested` mutation 경로를 사용한다.

### ShapeSelectionPage

- 헤더: 실제 도형 종류와 부모 프레임 정보
- 위치: 정렬, X, Y, 회전
- 크기: W, H, 비율 잠금
- 도형 파라미터: Polygon points, Star points/inner radius,
  Arc start/sweep/inner radius
- 외형: opacity, rectangle radius
- Fill stack, Stroke stack, Effect/advanced appearance, Export
- Line/Arrow는 Fill을 숨기고 Stroke 중심으로 노출

## 4. 생성과 계층 규칙

1. 드래그 결과를 현재 아트보드 좌표로 변환한다.
2. 새 객체 중심점을 포함하는 visible frame 후보를 찾는다.
3. 후보 중 가장 깊은 중첩 프레임, 같은 깊이면 가장 위 z-order를 부모로 정한다.
4. Slice는 export region이므로 자동 parent 대상에서 제외한다.
5. 프레임 preset은 항상 top-level frame으로 생성한다.
6. 새 도형은 종류별 `Rectangle 1`, `Ellipse 1`, `Star 1` 이름을 사용한다.
7. 도형 도구는 생성 후 유지되어 연속 생성할 수 있어야 한다.

현재 Painter 문서의 child geometry는 artboard 절대 좌표를 유지한다. `parent_id`는
계층, clipping, constraints, auto layout ownership을 정하며 생성 시 좌표를 다시
빼는 별도 로컬 좌표 모델을 만들지 않는다.

## 5. Motion의 의미와 Tiger Studio 경계

Figma Motion은 2026-06-24 공개된 open beta 별도 모드다. 선택한 프레임을 Motion
mode로 전환하면 같은 캔버스에 timeline이 나타난다. 위치, scale, rotation,
opacity keyframe, auto-keyframing, fade/move/scale animation style, 동시/순차
stacking, 시간 기반 comment와 Dev Mode handoff를 제공한다.

- [Figma Motion announcement](https://www.figma.com/blog/introducing-figma-motion/)
- [Figma Motion](https://www.figma.com/motion/)
- [Motion Plugin API](https://developers.figma.com/docs/plugins/api/Motion/)

Tiger Studio에서는 Painter가 정적 UI 구조를 소유하고 Motion Designer가 animation
timeline을 소유한다. 따라서 Painter Inspector 안에 두 번째 timeline 모델을 만들지
않는다. 선택한 Frame/Component를 Motion mode로 열면 stable object ID 기반 binding을
만들고 Motion Designer timeline을 같은 작업 문맥으로 표시한다. 결과는 다시 Painter
preview와 공유 TigerStudioUMG delivery contract로 돌아와야 한다.

## 6. 테마와 프레임 표면

- Figma의 UI 테마와 문서 표면 색은 서로 다른 상태다.
- 새 파일의 페이지 캔버스는 라이트 테마에서 `#F5F5F5`, 다크 테마에서
  `#1E1E1E`가 기본이지만, 프레임은 자체 Fill을 가진 디자인 레이어다.
- 따라서 다크 UI에서도 새 프레임의 기본 작업면은 흰색으로 유지하고,
  사용자가 Fill을 바꾼 경우에만 프레임 색을 변경한다.
- 선택 윤곽과 이름은 테마 대비에 맞춰 렌더링하되 문서 Fill을 덮어쓰지 않는다.

## 7. 구현 체크포인트

- [x] 도형 종류별 실제 canvas renderer와 hit testing
- [x] 생성 위치에서 가장 깊은 부모 프레임 자동 판정
- [x] 부모 프레임이 레이어 계층에 반영되는 canonical `parent_id`
- [x] 종류별 순차 기본 이름
- [x] Inspector shell의 selection content stack
- [x] ShapeSelectionPage 기본 위치/크기/외형/도형 파라미터
- [ ] Shift 정비율 생성과 Alt 중심 생성
- [ ] Rectangle 네 모서리 독립 radius canvas handle
- [ ] Ellipse arc direct-manipulation handle
- [ ] Polygon/Star point 및 inner-radius canvas handle
- [ ] Line/Arrow endpoint와 cap/join/dash 전용 편집
- [ ] Effect stack의 shape page 직접 편집
- [ ] MultiSelectionPage 별도 content page 분리
- [ ] 선택 프레임에서 Motion timeline 진입의 통합 UI

## 8. 완료 판정

도형 하나를 프레임 안에 생성했을 때 다음이 모두 증명되어야 한다.

1. 캔버스에 올바른 형태와 선택 표시가 보인다.
2. Layers에서 부모 프레임 아래에 들여쓰기 된다.
3. Shape Inspector가 다른 종류의 고정 필드를 남기지 않고 교체된다.
4. Inspector 변경이 canvas, document, Undo, save/load에 같은 값으로 반영된다.
5. 도형을 프레임 밖으로 reparent하면 계층과 clipping이 즉시 갱신된다.
6. Motion 진입은 별도 복제 객체가 아니라 같은 stable object ID를 사용한다.
