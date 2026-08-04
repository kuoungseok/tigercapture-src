# Motion Designer 레퍼런스 정합성 교정 마일스톤

작성일: 2026-08-04
상태: 계획 승인, 구현 전
소유 범위: Motion Designer evaluator, Graph Editor, Typography, Render Graph,
Behavior, Repeater, Puppet 및 관련 UI/Action/MCP/문서

## 1. 목적

이 트랙은 기능 수를 늘리는 계획이 아니다. 외부 제품에서 익숙한 이름을 사용하지만
현재 Tiger 구현의 의미가 더 좁거나 다른 항목을 공식 레퍼런스에 맞춰 교정한다.

내부 Preview/Export가 동일하다는 사실은 구현의 결정성을 증명하지만 Adobe After
Effects 또는 Apple Motion과 같은 의미를 증명하지 않는다. 이 문서에서 완료는 다음
두 증거를 모두 요구한다.

- `internal parity`: Preview, Main Editor Motion Clip, Export가 같은 결과를 낸다.
- `reference alignment`: 공식 정의에서 요구한 조작과 수치 또는 시각 결과가 외부
  reference scene의 허용 오차 안에 들어온다.

완전한 `.aep`, Apple Motion 프로젝트, Adobe Puppet 엔진 호환은 목표가 아니다.
지원하지 않는 의미는 Tiger 전용 이름과 진단으로 정직하게 구분한다.

기초 감사 문서:

- `docs/MOTION_DESIGNER_REFERENCE_AUDIT_KO.md`

## 2. 공식 레퍼런스

구현과 QA는 블로그·템플릿 판매 페이지·추정 동작이 아니라 아래 1차 자료를 기준으로
한다.

- Adobe Keyframe Interpolation:
  https://helpx.adobe.com/after-effects/using/keyframe-interpolation.html
- Apple Motion Keyframe Editor:
  https://support.apple.com/guide/motion/keyframe-editor-controls-motn147486cf/mac
- Adobe Text Animation and Selectors:
  https://helpx.adobe.com/after-effects/using/animating-text.html
- Unicode Text Segmentation, UAX #29:
  https://unicode.org/reports/tr29/
- Qt `QTextBoundaryFinder`:
  https://doc.qt.io/qt-6/qtextboundaryfinder.html
- Adobe After Effects Motion Blur reference:
  https://helpx.adobe.com/pdf/after_effects_reference.pdf
- Apple Motion Behaviors:
  https://support.apple.com/guide/motion/intro-to-behaviors-motn13748883/mac
- Apple Motion Parameter Behaviors:
  https://support.apple.com/guide/motion/add-or-remove-a-parameter-behavior-motn137441ab/mac
- Apple Motion Replicator Controls:
  https://support.apple.com/guide/motion/replicator-controls-motn15320179/mac
- Apple Motion Sequence Replicator Controls:
  https://support.apple.com/guide/motion/sequence-replicator-controls-motn1531eacd/mac
- Adobe Puppet Tools:
  https://helpx.adobe.com/after-effects/desktop/animate-in-after-effects/animate-with-puppet-tools/animating-puppet-tools.html

공식 문서가 수식이나 픽셀 결과를 규정하지 않는 항목은 이름과 조작 모델만 맞추고,
Tiger의 수식은 별도 공개 계약과 golden scene으로 고정한다.

## 3. 전체 순서

| 단계 | 목적 | 우선순위 | 상태 | 선행 |
| --- | --- | --- | --- | --- |
| RA0 | 주장·용어·기준선 교정 | P0 | In Progress | 없음 |
| RA1 | Unicode grapheme 경계 | P0 | In Progress | RA0 |
| RA2 | Text Range Selector 의미 교정 | P0 | Planned | RA1 |
| RA3 | Temporal Auto/Continuous tangent | P0 | Planned | RA0 |
| RA4 | Position spatial Bezier와 motion path | P0 | Planned | RA3 |
| RA5 | Shutter 기반 temporal motion blur | P0 | Planned | RA3, RA4 |
| RA6 | Tiger Behavior 계약과 고급 동작 | P1 | Planned | RA0 |
| RA7 | Repeater/Sequence Repeater 확장 | P1 | Planned | RA0, RA3 |
| RA8 | Puppet 의미·안정성 교정 | P1 | Planned | RA0 |
| RA9 | 외부 reference acceptance gate | P0 | Planned | RA1-RA8 |

권장 실행 순서:

```text
RA0 -> RA1 -> RA2
RA0 -> RA3 -> RA4 -> RA5
RA0 -> RA6
RA0 -> RA7
RA0 -> RA8
RA2 + RA5 + RA6 + RA7 + RA8 -> RA9
```

## 4. 공통 완료 규칙

각 단계는 다음을 모두 만족해야 완료다.

- 공식 레퍼런스의 어떤 의미를 구현했는지 acceptance 문서에 인용한다.
- `.tgmotion` 저장 의미가 달라지면 schema version과 migration을 추가한다.
- 기존 프로젝트의 외형 또는 기존 Action payload를 조용히 바꾸지 않는다.
- UI, Action/MCP, evaluator, Preview, Export가 같은 public contract를 사용한다.
- unsupported와 Tiger approximation을 preflight에서 구분한다.
- 새 mutation은 한 단계 Undo/Redo와 round trip을 보장한다.
- 내부 parity와 외부 reference alignment를 서로 다른 테스트로 기록한다.
- 실제 UI 캡처, reference scene, 렌더 artifact, 오차 보고서가 있다.
- 기능이 UMG 문서에 들어갈 수 있으면 같은 변경에서 native, UI Material, bake,
  blocked 중 하나로 `TigerStudioUMG`에 매핑한다.
- 설치본에서 같은 QA를 재현할 수 있다.

## 5. RA0 - 주장·용어·기준선 교정

목표: 구현보다 넓은 이름을 먼저 제거해 이후 작업 중에도 제품이 과장되지 않게 한다.

작업:

- Graph Editor의 현재 곡선을 `Temporal Bezier`로 표기한다.
- 진짜 자동 접선이 구현되기 전의 `Auto`는 `Tiger Smooth`로 migration 표시한다.
- 기존 `shutter` 저장 키는 호환성을 위해 유지하되 UI를 `Blur Length`로 바꾸고
  단위를 배율로 표시한다.
- 현재 Text Selector를 `Tiger Selector`로 표시하고 Offset/Smoothness 도움말에 실제
  원형 순환·시간 smoothstep 의미를 적는다.
- `Replicator`는 RA7 전까지 `Tiger Repeater`로 표시한다.
- Puppet UI에 `Tiger Cutout Mesh` 진단을 추가하고 Adobe compatibility 문구를 금지한다.
- 존재하지 않는 `tests/test_motion_behaviors.py`를 완료 증거에서 제거하고 실제 테스트
  목록으로 교체한다.
- 공개 문서와 `SPEC.md`의 spatial interpolation, shutter angle/phase, Range Selector,
  Behavior, Replicator, Puppet 완료 표현을 감사 결과에 맞춘다.

호환 규칙:

- 저장 키와 Action key는 RA1-RA8 migration이 준비되기 전까지 삭제하지 않는다.
- 구버전 파일을 열면 legacy 의미를 유지하고 Inspector에 `Legacy Tiger semantics`를
  표시한다.
- 새 문서만 새 의미를 기본값으로 사용한다.

완료 증거:

- 전체 문서 claim scan에서 금지 표현 0건
- 구버전 fixture의 렌더 hash 변화 0건
- UI label과 Action inspect 결과의 의미 불일치 0건

예정 파일:

- `app/motion_designer/graph_editing.py`
- `app/motion_designer/typography_motion.py`
- `app/motion_designer/render_graph.py`
- 관련 Inspector와 Action namespace
- `tests/test_motion_reference_claims.py`
- `tests/test_motion_legacy_semantics.py`

### 2026-08-04 구현 기록

- 구현: Graph Editor의 고정 handle `Auto`를 UI에서 `Tiger Smooth`로 표시하고
  keyframe metadata에 `legacy_tiger_smooth_temporal_bezier_v1` 계약을 기록한다.
- 구현: 현재 이동 smear를 `Fast Translation Vector Blur`, 기존 `shutter` 입력을
  `Blur Length`로 표시한다. Action과 신규 metadata는
  `fast_translation_vector_blur_v1` 및 `blur_length_multiplier` 의미를 반환한다.
- 구현: 일반 layer 복제를 `Tiger Repeater`로 표시하고 신규 metadata에
  `tiger_repeater_v1` 계약을 기록한다. 내부 키 `replicator`와 기존 Action ID는
  파일/자동화 호환을 위해 유지한다.
- 구현: 기존 selector의 Offset과 Smoothness를 각각 `Legacy Order Offset`,
  `Animation Smoothing`으로 표시하고 표준 Range Selector 의미가 아니라는 도움말을
  제공한다.
- 구현: `SPEC.md`, 템플릿, 라이브러리, validation의 사용자 노출 표현을 현재
  subset 의미에 맞췄다.
- 남음: 전체 공개 문서 claim scan, 구버전 fixture hash bundle, 설치본 UI 캡처와
  machine-readable reference claim gate. 이 때문에 RA0은 아직 `In Progress`다.

## 6. RA1 - Unicode Grapheme Boundary

목표: 텍스트 애니메이션의 `Character`가 사용자에게 보이는 문자 단위와 일치하게 한다.

기준:

- Unicode UAX #29 extended grapheme cluster
- Qt `QTextBoundaryFinder(QTextBoundaryFinder.Grapheme)`

작업:

- Qt-free evaluator에서 사용할 `TextBoundaryProvider` 계약을 만든다.
- 데스크톱 기본 provider는 Qt grapheme boundary를 사용한다.
- headless/export worker는 동일한 Unicode 결과를 내는 provider를 사용하며, provider가
  없다고 code point 분할로 조용히 강등하지 않는다.
- grapheme, word, line 경계를 한 캐시에서 관리하고 text/font/language 변경 시에만
  무효화한다.
- regional indicator flag, emoji modifier, ZWJ family, combining mark, Hangul Jamo,
  CRLF, Indic conjunct fixture를 추가한다.

완료 기준:

- Unicode conformance fixture의 grapheme boundary 불일치 0건
- `🇰🇷`, `👍🏽`, family ZWJ가 각각 한 Character unit
- Preview/headless/export selector span 동일
- 10,000자 텍스트의 boundary cache 재사용과 bounded memory 증명

예정 파일:

- `app/motion_designer/text_boundaries.py`
- `app/motion_designer/typography_motion.py`
- `tests/test_motion_unicode_graphemes.py`
- `tools/qa_motion_unicode_boundaries.py`

### 2026-08-04 구현 기록

- 구현: `text_boundaries.py`에 Qt `QTextBoundaryFinder(Grapheme)` 기반 provider와
  512-entry LRU cache를 추가했다.
- 구현: Qt의 UTF-16 boundary offset을 Python code-point offset으로 변환해 emoji
  이후 문자열의 slice 위치가 어긋나지 않게 했다.
- 구현: 기존 typography character selector가 더 이상 자체 combining/ZWJ 근사를
  사용하지 않고 공용 provider를 사용한다.
- 검증: 한국 국기, 피부색 modifier, family ZWJ, combining mark, Hangul Jamo와
  UTF-16/Python offset fixture가 통과했다.
- 남음: Unicode 버전을 고정한 전체 GraphemeBreakTest conformance corpus,
  Preview/headless/export 대형 다국어 장면, 설치본 증거. 이 때문에 RA1은 아직
  `Complete`가 아니라 `In Progress`다.

## 7. RA2 - Text Range Selector 의미 교정

목표: Start, End, Offset, Units, Based On, Shape, Smoothness가 공식 Range Selector와
같은 조작 의미를 갖게 한다.

작업:

- Units에 Percentage와 Index를 추가한다.
- Based On에 Characters, Characters Excluding Spaces, Words, Lines를 제공한다.
- Offset은 선택 단위 배열 회전이 아니라 Start/End range를 같은 selector domain에서
  이동시킨다.
- Square Smoothness는 range 경계의 전이 폭을 제어하고 애니메이션 시간 진행률과
  분리한다.
- Amount, Ease High, Ease Low를 selector weight 계산에 추가한다.
- 여러 selector의 Add, Subtract, Intersect 결합 모드를 구현한다.
- Ramp Up, Ramp Down, Triangle, Round, Smooth shape를 독립 golden으로 고정한다.
- Wiggly/Expression Selector는 같은 단계에서 흉내 내지 않고 명시적 후속 capability로
  남기거나 실제 구현 후에만 노출한다.

Migration:

- legacy `selector_offset`과 `smoothness`는 기존 결과를 유지하는 legacy mode로 읽는다.
- 사용자가 `Convert to Standard Range Selector`를 실행할 때만 새 의미로 변환한다.
- 변환 preview와 one-step Undo를 제공한다.

완료 기준:

- Character/Word/Line과 spaces 제외 reference grid의 weight 오차 `<= 1e-6`
- selector 결합 truth table 전 항목 통과
- 한글, emoji, 다국어 line wrap 장면에서 깨진 glyph/부분 선택 0건
- legacy fixture 렌더 hash 보존

예정 파일:

- `app/motion_designer/text_selectors.py`
- `app/motion_designer/typography_motion.py`
- Typography Inspector와 Timeline channel adapter
- `tests/test_motion_text_selector_reference.py`
- `tools/qa_motion_text_selector_reference.py`

## 8. RA3 - Temporal Auto/Continuous Tangent

목표: 고정 preset handle을 실제 이웃 키프레임 기반 temporal tangent로 교체한다.

작업:

- keyframe마다 incoming/outgoing temporal tangent와 influence를 분리 저장한다.
- `Auto`는 앞·뒤 구간의 시간과 값 기울기로 접선을 계산하고 overshoot 방지 정책을
  명시한다.
- `Continuous`는 양쪽 접선 방향을 결합하되 influence 길이는 독립 조절 가능하게 한다.
- `Broken`은 양쪽 접선을 독립 편집한다.
- Value Graph와 Speed Graph가 같은 underlying tangent를 편집하게 한다.
- Roving keyframe은 공간 경로 완료 전 노출하지 않거나 지원 범위를 명확히 제한한다.

완료 기준:

- irregular key time, plateau, sign change, duplicate value fixture에서 NaN/시간 역행 0건
- Continuous key에서 좌우 도함수 방향 불연속 `<= 1e-6`
- Auto monotonic fixture의 의도치 않은 overshoot 0건
- Value Graph/Speed Graph 편집 왕복 오차 `<= 1e-6`

예정 파일:

- `app/motion_designer/keyframes.py`
- `app/motion_designer/graph_editing.py`
- Graph Editor UI
- `tests/test_motion_temporal_tangent_reference.py`
- `tools/qa_motion_graph_reference.py`

## 9. RA4 - Position Spatial Bezier와 Motion Path

목표: Position의 시간 easing과 화면상의 이동 경로를 분리하고 실제 spatial path를
편집하게 한다.

작업:

- Position keyframe에 2D/2.5D spatial in/out tangent를 추가한다.
- cubic Bezier path 위치와 1차 도함수, arc-length lookup table을 구현한다.
- Canvas에서 path와 tangent handle을 직접 편집한다.
- Temporal speed와 Spatial curve를 독립 저장·평가한다.
- Auto Orient는 path tangent 방향을 사용하고 zero-length 구간은 이전 유효 방향을
  안정적으로 유지한다.
- Roving keyframe은 고정 spatial path 위 구간 속도 평활화로 구현한다.

완료 기준:

- 직선 tangent는 기존 linear position 결과와 오차 `<= 1e-6`
- 시작/끝점과 handle reference fixture의 위치 오차 `<= 0.25 px`
- arc-length 일정 속도 장면의 구간별 이동 편차 `<= 2%`
- Canvas path, Preview, Export의 sample 좌표 동일

예정 파일:

- `app/motion_designer/spatial_paths.py`
- `app/motion_designer/keyframes.py`
- Canvas/Graph Editor path UI
- `tests/test_motion_spatial_bezier.py`
- `tools/qa_motion_spatial_path_reference.py`

## 10. RA5 - Shutter 기반 Temporal Motion Blur

목표: 단일 translation vector smear를 실제 프레임 시간 샘플 기반 blur로 확장한다.

작업:

- Composition에 shutter angle과 shutter phase를 명시적 단위로 저장한다.
- 샘플 시간 창을 현재 프레임 기준으로 계산한다.
- Position, rotation, scale, opacity, spatial path, puppet deformation을 각 시간 sample에서
  평가한다.
- sample count와 adaptive sampling 상한을 품질 preset으로 제공한다.
- alpha는 premultiplied linear space에서 누적한다.
- 기존 translation smear는 `Fast Vector Blur`로 유지하고 새 shutter blur와 구분한다.
- GPU temporal accumulation을 기본으로 하고 지원하지 않는 효과는 사전 진단 후
  bounded CPU 또는 Fast Vector Blur로 명시적으로 fallback한다.

완료 기준:

- 정지 장면에서 원본과 최대 byte 오차 0
- 순수 이동 장면의 blur centroid 오차 `<= 0.5 px`
- 180도 shutter의 노출 시간은 frame duration의 0.5배
- phase 변경 시 sample window가 수치 reference와 일치
- 회전·스케일·puppet 장면에서 translation-only fallback이 조용히 사용되지 않음
- Preview 저품질과 Export 최종 품질이 같은 시간 창을 사용

예정 파일:

- `app/motion_designer/temporal_sampling.py`
- `app/motion_designer/render_graph.py`
- Preview/Export renderer backend
- `tests/test_motion_shutter_sampling.py`
- `tools/qa_motion_blur_reference.py`

## 11. RA6 - Tiger Behavior 계약과 고급 동작

목표: 경험식 preset을 공식 제품 이름과 혼동하지 않게 하면서 재사용 가능한 Behavior
시스템으로 만든다.

작업:

- Fade, Slide, Pop, Impact는 `Tiger Preset Behavior`로 분류한다.
- Spring은 감쇠 조화 진동자의 frequency/damping/initial velocity 단위를 정의하거나
  기존 식을 `Tiger Bounce`로 유지한다.
- Wiggle은 단일 sine 대신 seeded band-limited noise와 dimensions correlation을 제공한다.
- Follow Path, Align to Motion, Look At, Orbit는 constraint metadata를 Behavior UI와
  연결하되 기존 별도 evaluator를 중복 구현하지 않는다.
- Apply, Bake to Keyframes, Remove가 같은 평가 결과를 유지한다.
- 여러 Behavior의 order와 blend mode를 명시한다.

완료 기준:

- 같은 seed/document/time에서 결과 hash가 항상 동일
- frame rate 24/30/60 변경 후 같은 절대 시간의 값 오차 `<= 1e-6`
- Spring energy가 damping > 0에서 장기적으로 증가하지 않음
- Apply/Bake 결과의 sample 오차 `<= 1e-5`
- 실제 존재하는 behavior test와 UI/Action evidence 확보

예정 파일:

- `app/motion_designer/behaviors.py`
- `app/motion_designer/constraints.py`
- Behavior Inspector/Action namespace
- `tests/test_motion_behaviors.py`
- `tools/qa_motion_behavior_reference.py`

## 12. RA7 - Repeater와 Sequence Repeater

목표: 현재 line/grid/radial 복제를 명확한 Tiger Repeater로 고정하고 제작에 필요한
배치·순차 애니메이션을 추가한다.

작업:

- V1 `Tiger Repeater`: line, grid, radial의 origin, spacing, count, transform increment,
  deterministic random seed를 문서화한다.
- rectangle, circle, image-mask pattern을 추가한다.
- outline, tile fill, random fill과 build order를 추가한다.
- Cell Controls에 anchor, scale, rotation, opacity, color increment를 제공한다.
- Sequence Repeater에 parameter, start/end, spread, traversal, sequencing behavior를
  추가한다.
- box/sphere 등 실제 3D replicator는 2.5D card 범위와 혼동하지 않도록 별도 capability로
  차단한다.

완료 기준:

- 패턴별 copy 위치 golden 오차 `<= 0.25 px`
- 같은 seed에서 random 배치 hash 동일
- count 10,000 stress에서 cache 무한 증가와 UI 장기 block 없음
- Sequence traversal의 first/middle/last cell weight가 reference table과 일치
- UMG 출력은 native panel, generated children, bake, blocked 중 하나를 명시

예정 파일:

- `app/motion_designer/repeater.py`
- `app/motion_designer/advanced_motion.py`
- Repeater Inspector/Timeline/Action namespace
- `tests/test_motion_repeater_reference.py`
- `tools/qa_motion_repeater_reference.py`

## 13. RA8 - Puppet 의미·안정성 교정

목표: Adobe pin 이름을 그대로 빌린 경험식 변형을 Tiger Cutout Mesh의 명확하고
검증 가능한 계약으로 바꾼다.

작업:

- 기존 Position/Bend/Starch/Overlap 필드의 실제 영향식을 사용자 문서에 공개한다.
- 경험 상수 `0.15`, `6.0`, 50% rest repair를 named policy와 versioned preset으로 옮긴다.
- pin type별 단위, falloff, 우선순위와 overlap ordering을 schema에 명시한다.
- mesh density 변화에 대한 변형 안정성을 테스트한다.
- triangle flip, stretch, self-intersection을 frame별 진단하고 자동 repair 여부를
  Inspector에서 보여준다.
- `Adobe Puppet compatible` 표현은 금지하고, Adobe 문서를 조작 모델 참고 자료로만
  사용한다.
- 향후 물리 기반 solver는 같은 이름으로 조용히 교체하지 않고 별도 solver version으로
  추가한다.

완료 기준:

- 기존 fixture의 legacy solver 렌더 hash 보존
- 동일 pin pose에서 mesh density별 silhouette IoU `>= 0.98`
- non-finite, degenerate triangle, unreported flip 0건
- alpha edge spill과 tear repair 수치가 QA report에 기록됨
- 10분 반복 평가에서 solver/cache memory가 설정 예산 이내

예정 파일:

- `app/motion_designer/puppet_mesh.py`
- Puppet Inspector/diagnostics
- `tests/test_motion_puppet_reference.py`
- `tools/qa_motion_puppet_reference.py`

## 14. RA9 - 외부 Reference Acceptance Gate

목표: 내부 테스트가 통과했다는 이유만으로 외부 의미 정합성을 완료 처리하지 못하게
한다.

Reference pack:

- `unicode_grapheme_grid`
- `text_selector_weight_grid`
- `temporal_tangent_irregular_keys`
- `spatial_bezier_path`
- `motion_blur_translation_rotation_scale`
- `behavior_seed_and_bake`
- `repeater_pattern_sequence`
- `puppet_density_and_edge`

작업:

- 각 scene에 source, expected numeric table, expected image/video, tolerance, 공식 문서 URL,
  생성 도구 version을 manifest로 기록한다.
- 외부 제품에서 수치 export가 불가능하면 동일 입력의 화면 캡처와 수동 측정 절차를
  기록하고 Tiger golden과 구분한다.
- `tools/qa_motion_reference_acceptance.py`가 단계별 결과와 전체 release gate를 만든다.
- 내부 parity, reference alignment, performance, installer 결과를 별도 필드로 보고한다.
- 하나라도 누락되면 `reference_aligned=false`이며 제품 문구를 자동 승격하지 않는다.

완료 기준:

- RA1-RA8 필수 fixture와 provenance 누락 0건
- 지원 주장별 tolerance 통과
- 설치본에서 reference pack 재실행 성공
- 문서 상태와 machine-readable acceptance 상태 일치

예정 파일:

- `sample_assets/motion_reference/`
- `tools/qa_motion_reference_acceptance.py`
- `tests/test_motion_reference_acceptance.py`
- `docs/evidence/motion_reference/`

## 15. 구현 시 지켜야 할 제품 표현

RA9 전에도 사용 가능한 표현:

- `Temporal Bezier`
- `Fast Translation Vector Blur`
- `Tiger Selector`
- `Tiger Preset Behavior`
- `Tiger Repeater`
- `Tiger Cutout Mesh`
- `2.5D card camera`

RA9에서 해당 항목이 통과한 뒤에만 사용할 표현:

- `Unicode grapheme-aware text animation`
- `Range Selector with percentage/index and selector combination modes`
- `temporal Auto/Continuous tangents`
- `spatial Bezier motion paths`
- `shutter angle/phase temporal motion blur`

계속 금지되는 표현:

- `After Effects compatible`
- `Apple Motion compatible`
- `Adobe Puppet compatible`
- `.aep visual playback compatible`
- 외부 프로젝트와의 픽셀 동일성 또는 모든 효과 호환

## 16. 첫 실행 백로그

1. RA0 문서·UI claim inventory와 legacy fixture 고정
2. `TextBoundaryProvider`와 Unicode conformance fixture
3. Standard Range Selector schema/migration
4. selector weight evaluator와 Inspector
5. temporal tangent data model과 Auto/Continuous evaluator
6. spatial path data model과 Canvas handle
7. temporal sampling contract와 Fast/Final blur 분리
8. Behavior와 Repeater public contract
9. Puppet solver policy versioning
10. RA9 reference pack과 설치본 acceptance

새 기능을 한꺼번에 구현하지 않는다. 각 단계는 이전 단계의 legacy fixture를 계속
통과시켜야 하며, 외부 reference가 준비되지 않은 항목은 `Implemented`가 아니라
`Internal parity only`로 기록한다.
