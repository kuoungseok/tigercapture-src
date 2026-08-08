# Motion Designer 레퍼런스 정합성 감사

작성일: 2026-08-04
범위: Motion Designer의 공개 용어, 문서 주장, 평가기와 렌더러 구현
판정 기준: Apple Motion 및 Adobe After Effects 공식 문서, Unicode/Qt 공식 규격,
코드와 테스트가 실제로 증명하는 범위

## 결론

> 2026-08-04 후속 구현 알림: 아래 감사 본문의 "실제 구현" 설명은 감사 당시의
> 기준선이다. 이후 RA 작업으로 Unicode grapheme, Standard Range Selector v1,
> 이웃 키 기반 temporal Auto/Continuous, Position spatial Bezier 평가,
> angle/phase 기반 temporal shutter sampling, Tiger Behavior 계약, Tiger Repeater
> v2, Puppet 안정성 진단, reference image gate와 portable runtime package가
> 추가되었다. 현재의 정확한 지원/제한 표는
> `docs/MOTION_DESIGNER_REFERENCE_IMPLEMENTATION_STATUS_2026-08-04.md`를 따른다.
> 이 후속 구현도 Adobe/Apple 프로젝트 호환이나 픽셀 동일성을 주장하지 않는다.

Motion Designer 전체가 상식이나 추측만으로 구현된 것은 아니다. 분석적 2-bone
IK, OpenCV 기반 트래킹, OCIO/ACES 경계, 결정론적 렌더 계약처럼 명확한 기술
근거가 있는 영역이 있다. 그러나 외부 제품에서 익숙한 이름을 사용하면서 실제
의미는 Tiger 전용 간소화 수식인 영역도 있다. 특히 Graph Editor, Motion Blur,
Text Selector, Behavior, Replicator, Puppet pin은 현재 문서의 완료 표현보다 구현
범위가 좁다.

테스트 다수는 Preview/Export 동일성, 저장 왕복, 결정론을 증명한다. Apple Motion
또는 After Effects와의 수치·시각 비교를 증명하지는 않는다. 따라서 내부 parity와
외부 reference parity를 같은 의미로 사용하면 안 된다.

마일스톤 문서가 M2 증거로 적은 `tests/test_motion_behaviors.py`는 현재 저장소에
존재하지 않는다. 관련 evaluator, time-remap, typography, frame-blending 테스트
21개는 2026-08-04에 통과했지만, 이 결과도 외부 제품 parity 증거는 아니다.

## P0 - 공개 의미가 실제 구현보다 넓은 항목

### 1. Spatial interpolation과 Auto/Continuous tangent

- 문서 주장:
  `MOTION_DESIGNER_AE_GAP_MILESTONES_KO.md`는 temporal/spatial interpolation,
  broken/continuous/auto tangent를 구현 범위로 적는다.
- 실제 구현:
  `keyframes.py`는 한 구간에 하나의 정규화된 cubic Bezier 진행률을 계산한 뒤
  vector 각 성분에 동일하게 적용한다. Position의 별도 spatial tangent나 곡선
  motion path 계산은 없다.
- `graph_editing.py`의 Auto는 이웃 키프레임 기울기를 계산하지 않고 고정값
  `(0.667, 1.0)`과 `(0.333, 0.0)`을 넣는다. Continuous tangent 결합 규칙도 없다.
- 판정: Temporal cubic easing subset은 구현됨. Spatial Bezier, 진짜 Auto,
  Continuous는 미구현이다.
- 조치: UI와 문서에서 현재 모드를 `Tiger Bezier` 또는 `Temporal Bezier`로
  한정하고, spatial tangent와 자동 기울기 계산을 별도 마일스톤으로 둔다.

공식 기준:

- Adobe Keyframe Interpolation:
  https://helpx.adobe.com/after-effects/using/keyframe-interpolation.html
- Apple Motion Keyframe Editor:
  https://support.apple.com/guide/motion/keyframe-editor-controls-motn147486cf/mac

### 2. Motion Blur의 Shutter 표현

- 실제 구현은 `render_graph.py`에서 이전 프레임과 현재 프레임의 X/Y 이동량만
  구하고, `_apply_motion_blur`가 그 직선을 여러 장 평행 이동해 평균낸다.
- 회전, 스케일, 변형, 프레임 내 실제 시간 샘플링은 반영하지 않는다.
- UI의 `Shutter`는 0~2 배율이며 도 단위 shutter angle이 아니다. shutter phase
  데이터와 계산도 없다.
- 판정: Translation vector blur subset이다. 문서의 `shutter angle/phase` 주장은
  현재 구현과 맞지 않는다.
- 조치: UI를 `Blur Length`로 바꾸거나 실제 angle/phase 기반 시간 샘플러를
  구현하기 전까지 Shutter 호환 표현을 사용하지 않는다.

공식 기준:

- Adobe After Effects Reference의 Motion Blur settings:
  https://helpx.adobe.com/pdf/after_effects_reference.pdf

### 3. Text Range Selector 의미

- `typography_motion.py`는 character/word/line, start/end, 순서 변경과 기본 shape
  가중치를 제공한다.
- 그러나 grapheme 분리는 파일 스스로 `approximate`라고 명시한 자체 규칙이다.
  Unicode grapheme 전체 규칙을 구현하지 않아 flag, modifier, 일부 emoji sequence와
  복잡 문자를 잘못 나눌 수 있다.
- 실제 probe에서 한국 국기 `U+1F1F0 U+1F1F7`과 피부색 modifier가 붙은 엄지
  `U+1F44D U+1F3FD`를 각각 두 단위로 잘못 분리했다. ZWJ family와 완성형 한글은
  해당 probe에서 한 단위로 유지됐다.
- Offset은 selector range 이동이 아니라 선택된 단위 리스트의 원형 회전이다.
- Smoothness는 Square selector 경계가 아니라 개별 애니메이션 시간 진행률에
  smoothstep을 섞는다.
- Add/Subtract/Intersect selector mode, Wiggly/Expression selector, Ease High/Low,
  index 단위와 spaces 제외 기준은 없다.
- 판정: Tiger typography selector subset이다. AE Range Selector parity가 아니다.
- 조치: Qt의 `QTextBoundaryFinder(Grapheme)`를 사용하고, 기존 Offset/Smoothness는
  이름 또는 계산을 고친 뒤 selector mode를 명시적으로 추가한다.

공식 기준:

- Adobe Text Selectors:
  https://helpx.adobe.com/after-effects/using/animating-text.html
- Unicode Text Segmentation UAX #29:
  https://unicode.org/reports/tr29/
- Qt QTextBoundaryFinder:
  https://doc.qt.io/qt-6/qtextboundaryfinder.html

## P1 - Tiger 전용 근사임을 명시해야 하는 항목

### 4. Behavior

- `behaviors.py`의 Spring은 감쇠 사인파, Wiggle은 단일 사인파다. noise 기반
  wiggle이나 물리 spring solver가 아니다.
- Impact의 `0.45`, frequency offset `0.5` 등은 Tiger 룩을 위한 경험값이다.
- UI에서 실제 추가 가능한 종류는 Fade, Slide, Pop, Spring, Wiggle, Impact다.
  오래된 문서의 follow path, look-at, orbit, delay, stagger 완성 주장은 Behavior
  목록과 맞지 않는다. 일부 follow/look-at은 별도 constraint metadata 경로다.
- 판정: 의도적인 Tiger preset으로는 유효하다. Apple Motion Behavior 또는 AE
  expression과 같은 의미로 홍보하면 안 된다.

공식 기준:

- Apple Motion Intro to Behaviors:
  https://support.apple.com/guide/motion/intro-to-behaviors-motn13748883/mac
- Apple Motion Parameter Behaviors:
  https://support.apple.com/guide/motion/add-or-remove-a-parameter-behavior-motn137441ab/mac

### 5. Replicator

- `advanced_motion.py`는 line/grid/radial 세 배치와 deterministic sine jitter를
  계산한다.
- Apple Motion Replicator의 rectangle/circle/image/box/sphere, outline/tile/random
  fill, cell controls, build style와 Sequence Replicator 의미는 구현하지 않는다.
- 판정: `Tiger Repeater`에 가까운 subset이다. 현재 `Replicator` 명칭에는 범위
  설명이 필요하다.

공식 기준:

- Apple Motion Replicator Controls:
  https://support.apple.com/guide/motion/replicator-controls-motn15320179/mac
- Apple Motion Sequence Replicator:
  https://support.apple.com/guide/motion/sequence-replicator-controls-motn1531eacd/mac

### 6. Puppet Position/Bend/Starch/Overlap

- 2-bone IK는 코사인 법칙 기반 분석 해법이라 근거가 명확하다.
- 반면 `puppet_mesh.py`의 pin deformation은 Gaussian 거리 가중치, damping
  상수 `0.15`, edge stretch 기본값 `6.0`, 50% rest-pose 복귀를 조합한 Tiger
  전용 piecewise-affine 안정화다.
- Adobe와 같은 pin 이름은 사용하지만 Adobe Puppet engine과 같은 물리·mesh
  의미를 재현한 것은 아니다.
- 판정: 안정적인 Tiger cutout deformation으로 설명해야 한다. Adobe Puppet
  호환 또는 동일 결과 주장은 금지한다.

### 7. Particle turbulence와 2.5D camera

- Particle의 birth/lifetime/ballistic gravity와 결정론적 seed는 기술적으로
  타당하다. Turbulence는 noise field가 아니라 X/Y 사인파이며 Y 주파수의 `0.73`은
  룩을 위한 경험값이다.
- 2.5D camera는 실제 3D projection matrix가 아니라 card depth에 따른 scale,
  parallax, cos 기반 X/Y 축 축소다.
- 판정: 둘 다 Tiger-native effect로는 정상이다. 범용 particle simulation 또는
  full 3D camera로 부르면 과장이다.

## P2 - 미완성을 이미 명시하고 있어 허용 가능한 항목

- Optical Flow는 선택 가능하지만 vector warp가 없어 Frame Mix로 대체된다.
  코드, 경고 UI, preflight가 이를 명시하므로 조용한 오동작은 아니다. 다만 메뉴는
  `Optical Flow (requires backend)`처럼 상태를 먼저 보여주는 편이 낫다.
- BiRefNet/SAM2가 없을 때 GrabCut·OpenCV 분해를 쓰는 경로는 confidence와
  fallback 상태를 노출한다. 임계값은 경험값이지만 제품이 이를 AI-quality로
  가장하지 않는 한 허용 가능하다.
- Liquid Glass, paper crumple, collage, craft/imperfection, painterly look은
  Tiger 스타일 효과다. 공식 호환을 주장하지 않는다는 문서 경계가 이미 있다.
- AEP 검사는 알려진 문자열과 RIFX 구조를 이용한 보수적 preflight다. 시각 재생
  호환 판정기가 아니며, 이 제한을 유지해야 한다.

## 근거가 비교적 충분한 영역

- 2-bone IK: 분석적 geometry와 joint clamp
- Tracking: OpenCV feature/flow/affine/RANSAC 계열 backend
- Color: 명시적 OCIO config와 ACES-fitted fallback 경계
- Mask rasterization: QPainter path, morphology, Gaussian feather의 공통
  Preview/Export 경로
- Render contract: premultiplied alpha, deterministic fallback, GPU/CPU 진단
- Project schema: stable ID, migration, undo/redo, validation, recovery

이 영역도 외부 제품과의 픽셀 동일성을 뜻하지는 않지만, 적어도 구현 근거와
실패 경계가 코드에 드러난다.

## 수정 순서

아래 순서는 `docs/MOTION_DESIGNER_REFERENCE_ALIGNMENT_MILESTONES_KO.md`의
RA0-RA9로 구체화한다. 구현 상태와 외부 reference evidence는 해당 문서에서
관리한다.

1. 완료 문서에서 spatial interpolation, true Auto/Continuous tangent,
   shutter angle/phase를 `미구현`으로 정정한다.
2. UI의 `Shutter`를 `Blur Length`로 변경하고 Tiger vector blur임을 표시한다.
3. grapheme 분리를 Unicode/Qt 표준 구현으로 교체한다.
4. Text Selector Offset/Smoothness를 공식 의미로 고치고 selector mode를 추가한다.
5. Graph Editor에 spatial tangent와 이웃 기울기 기반 Auto/Continuous를 구현한다.
6. Behavior와 Replicator에 `Tiger` subset 계약을 만들고 공식 제품 이름과 범위를
   구분한다.
7. 각 항목에 외부 reference scene 또는 수치 golden을 추가한다. 내부
   Preview/Export parity 테스트만으로 reference parity 완료 판정을 내리지 않는다.

## 릴리스 표현 규칙

- 사용 가능: `Tiger deterministic spring`, `Tiger repeater`, `translation vector blur`,
  `typography selector subset`, `2.5D card camera`
- 사용 금지: `Apple Motion compatible`, `After Effects Range Selector compatible`,
  `spatial Bezier complete`, `shutter angle/phase supported`, `Adobe Puppet compatible`
- 외부 레퍼런스와 비교하지 않은 효과는 `Tiger-native`, `stylized`, `approximation`,
  `subset` 중 하나를 제품 진단 또는 문서에 명시한다.
