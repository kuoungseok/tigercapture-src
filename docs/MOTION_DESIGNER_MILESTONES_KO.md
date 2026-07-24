# Tiger Studio Motion Designer 구현 마일스톤

작성일: 2026-07-22  
기준 기획서: `docs/MOTION_DESIGNER_PRODUCT_PLAN_KO.md`  
상태: 구현 계획 및 실제 진행 기록  

현재 구현 상태: **M0-M11 통합 구현 및 제품 출시 검증 완료**. M6의 기본 Vector Shape
Engine, selector/stagger 기반 per-glyph typography, layer effect/mask,
adjustment layer, alpha/luma track matte, animated path mask와 point/planar
tracking cache 연결, GPU-resident vector mesh Preview, 제한적 PPT 왕복 브리지는
구현됐다. source video 기반 자동 추적 샘플 생성, GPU glyph atlas, Arabic 등
문맥형 문자의 공통 셰이핑, Canvas visual text-path picker도 구현됐다. PPT가
네이티브로 지원하는 appear/fade/move/scale animation은 trigger, click index,
timing, easing을 보존해 Motion behavior와 왕복하고, 비지원 모션만 bake 경고를 낸다.
M7은 WAV/FFmpeg source 분석, amplitude/bass/mid/treble/onset envelope와 beat cache,
attack/release/smoothing 기반 transform binding, 일반 keyframe bake, Composer의 정확한
BPM/section/note event, Voice Lab sentence/word/phoneme timing을 공통 composition에
연결했다. 10분 30fps QA fixture에서 preview/export 공유 평가 시각 drift는 0 frame이다.
M8은 기존 AR/PBR OpenGL renderer를 object/camera/light/depth layer로 연결했고,
M9A는 기존 Cubism GPU Live2D와 Spine renderer를 공통 actor source 계약으로 연결했다.
Live2D 3종과 Spine 3종의 실제 모델에서 비어 있지 않은 렌더와 동일 시점
preview/export 픽셀 일치를 확인했다. M9B는 기존 MMD PMX/PMD/VMD parser,
GPU skinning, IK, 물리, Toon OpenGL renderer를 Motion source로 연결했다. Cantarella,
Alice, Miku 실제 모델에서 투명 재질, 셀프 섀도, bloom, VMD camera, 시점 변화와
동일 시점 preview/export RGBA 완전 일치를 검증했다. M9C는 기존 VTuber
`vrm_mtoon_gpu` 경로를 VRM Motion source로 연결하고, 전신/바스트 프레이밍,
고개·눈깜박임·입 포즈, source exposure 정책, 동일 시점 canonical frame cache를
Milica VRM0 실제 GPU 렌더로 검증했다.
M10은 안전한 구조화 표현식과 keyframe bake, deterministic particle simulation,
GPU shape particle Preview, alpha media bake, 10종 built-in template와 stable published
controls, 방송 비용 등급·alpha cache·Program Output preflight, AI dry-run 비용/자산/
bake 분석을 구현했다. Motion 전체 테스트 35개 파일, 177개 테스트를 독립 프로세스로
실행해 통과했다.

## 1. 운영 원칙

이 문서는 기능 목록이 아니라 구현 순서와 완료 판정을 정의한다. 각 마일스톤은
코드 작성만으로 끝나지 않으며 자동 테스트, 실제 UI/렌더 증거, 문서 갱신까지
통과해야 완료된다.

### 기본 규칙

- `app/video_editor_window.py`에는 새 기능 로직을 추가하지 않는다.
- Motion Designer 코어는 `app/motion_designer/`에 둔다.
- 메인 에디터 연결은 `app/video_editor_motion_workflow.py`와 delegate로 한다.
- 편집 원본은 `.tgp`의 `motion_compositions[]`에 저장한다.
- 제품 프리뷰와 내보내기는 기존 OpenGL 경로를 기준으로 한다.
- UI와 AI는 같은 service/command/action을 사용한다.
- 캐릭터 renderer는 하나의 마일스톤으로 묶지 않고 각각 실제 자산으로 검증한다.
- 기존 기능 회귀를 막기 위해 각 마일스톤에서 architecture guard와 관련 회귀
  테스트를 실행한다.

### 공수 표기

`예상 공수`는 한 명이 구현, 테스트, QA 증거까지 수행하는 대략적인 개발일이다.
AI 병렬 작업을 해도 공통 schema, renderer, project I/O처럼 순차 의존성이 있는
구간은 단순히 인원수만큼 단축되지 않는다.

## 2. 전체 일정표

| 순서 | 마일스톤 | 예상 공수 | 결과물 | 제품 단계 |
| --- | --- | ---: | --- | --- |
| M0 | 기준선과 아키텍처 계약 | 2-3일 | 변경 전 QA 기준선과 모듈 계약 | 준비 |
| M1 | 컴포지션 schema와 프로젝트 저장 | 5-7일 | `.tgp`에 저장되는 MotionComposition | Core |
| M2 | 키프레임·Bezier·Behavior 평가 코어 | 7-10일 | Qt-free deterministic evaluator | Core |
| M3 | 독립 2D 제작 UI | 10-15일 | 레이어·캔버스·타임라인·그래프 편집 | Alpha UI |
| M4 | OpenGL 2D 합성과 출력 parity | 8-12일 | RGBA preview/export와 alpha 출력 | Alpha |
| M5 | 메인 타임라인 Motion Clip 통합 | 8-12일 | live-link Motion Clip | Beta |
| M6 | Vector·Typography·Effect·Mask·PPT 브리지 | 12-18일 | 2D 창작 기반과 기존 기능 재사용 | Beta+ |
| M7 | Sound Editor·Composer·Voice Lab 연동 | 6-9일 | audio reactive와 대사 타이밍 | Beta+ |
| M8 | AR/PBR 3D 레이어 | 9-14일 | 3D 카메라·라이트·재질 모션 | Rich Media |
| M9A | Live2D·Spine 레이어 | 8-12일 | 2D 캐릭터 모션 레이어 | Character |
| M9B | MMD 레이어 | 6-10일 | VMD/물리 캐릭터 모션 레이어 | Character |
| M9C | VRM 레이어와 캐시 | 8-12일 | MToon GPU avatar 레이어 | Character |
| M10 | Behavior·표현식·Particle·템플릿·방송·AI | 13-20일 | 절차적 모션과 제작 자동화 | RC 후보 |
| M11 | 색 관리·표준 출력·장시간 QA·설치본 검증 | 12-18일 | 제품 release gate | Product |
| M12 | Plugin·Template SDK | 8-12일 | 외부 확장 생태계 | Post-1.0 |

제품 출시 범위 M0-M11의 예상 공수는 약 114-172 개발일이다. 출시 후 M12까지
포함하면 약 122-184 개발일이다. M6과 M7, M8과 M9A/M9B/M9C의 adapter 작업은
공통 계약이 고정된 후 일부 병렬화할 수 있다.

### 보강 항목 책임표

| 보강 항목 | 책임 마일스톤 | 출시 차단 여부 |
| --- | --- | --- |
| 범용 속성 애니메이션 코어 | M1-M2 | 차단 |
| 전문 2D OpenGL compositor | M4 | 차단 |
| Layer hierarchy와 Graph Editor | M3 | 차단 |
| Motion Clip과 revision cache | M5 | 차단 |
| 프로젝트 migration/undo/recovery/relink | M1, M3, M5 | 차단 |
| Vector Shape Engine | M6 | 차단 |
| 고급 Typography | M6 | 차단 |
| Mask/Matte/Tracking | M6 | 차단 |
| Behavior와 경량 표현식 | M2, M10 | 차단 |
| GPU Particle | M10 | RC 차단 |
| Audio Reactive | M7 | Rich Media 차단 |
| Template Published Controls | M10 | RC 차단 |
| 명시적 Color Management | M11 | 출시 차단 |
| 표준 출력/호환성 preflight | M11 | 출시 차단 |
| Plugin/Template SDK | M12 | 비차단, Post-1.0 |

## 3. 제품 게이트

### Gate A: Core Ready

M0-M2 완료 시점이다.

- UI 없이 action과 unit test로 컴포지션을 만들고 평가한다.
- save/load 결과가 동일하다.
- keyframe/curve 결과가 deterministic하다.

### Gate B: Motion Designer Alpha

M3-M4 완료 시점이다.

- 독립 창에서 text/image/shape 기반 모션을 제작한다.
- OpenGL 프리뷰와 파일 출력이 동일하다.
- 투명 alpha 결과를 검증한다.

### Gate C: Motion Designer Beta

M5 완료 시점이다.

- 메인 타임라인에 Motion Clip을 놓고 편집·재생·최종 출력한다.
- Motion Designer를 사용하지 않는 프로젝트의 재생 성능이 저하되지 않는다.
- 이 시점부터 사용자가 실제 영상 제작에 사용할 수 있다.

### Gate D: Rich Media Beta

M6-M9 중 AR/PBR와 최소 두 종류의 character adapter가 완료된 시점이다.

- 기존 Tiger Studio 자산이 Motion Layer로 들어온다.
- 각 renderer는 실제 지원 샘플의 preview/export 증거를 가진다.

### Gate E: Product Release

M10-M11 완료 시점이다.

- 기본 템플릿, AI 액션, 표준 출력, 설치본 QA가 통과한다.
- unsupported/bake 항목을 preflight에서 누락 없이 알린다.

### Gate F: Extension SDK Ready

M12 완료 시점이며 Motion Designer 1.0 출시를 막는 gate는 아니다.

- 외부 plugin/template pack이 본체 파일을 수정하지 않고 등록된다.
- API version, capability, dependency, failure isolation이 검증된다.

## 4. M0 - 기준선과 아키텍처 계약

구현 상태: **완료 (2026-07-22)**

- Qt-free 공통 계약: `app/motion_designer/contracts.py`
- 아키텍처 ADR: `docs/MOTION_DESIGNER_ARCHITECTURE.md`
- 재생 가능한 기준선 도구: `tools/qa_motion_baseline.py`
- 생성 보고서: `debugCapture/motion_designer/baseline.json`
- 자동 경계 검사: `tests/test_motion_architecture_rules.py`

### 목표

기존 편집기 성능과 기능을 측정하고 Motion Designer가 따라야 할 경계를 코드
수정 전에 고정한다.

### 작업

1. 현재 `.tgp` 저장/불러오기 round-trip 기준선을 기록한다.
2. 빈 에디터와 일반 영상 프로젝트의 startup/playback 기준선을 기록한다.
3. OpenGL preview/export parity 기존 보고서를 수집한다.
4. Motion Designer의 package dependency 방향을 확정한다.
5. `SourceFrame`, `MotionComposition`, `MotionCommand` 인터페이스를 ADR에 기록한다.
6. durable sample과 disposable `debugCapture` 경계를 확정한다.

### 산출물

- `docs/MOTION_DESIGNER_ARCHITECTURE.md`
- `debugCapture/motion_designer/baseline.json`
- `tools/qa_motion_baseline.py`
- `tests/test_motion_architecture_rules.py`

`debugCapture` 보고서는 재생성 가능해야 하며 원본 자산은 `sample_assets` 또는
`external/assets`에 둔다.

### 완료 조건

- 현재 프로젝트 저장, 영상 재생, OpenGL 프리뷰 기준 수치가 기록된다.
- `app/video_editor_window.py` 금지 규칙이 motion 모듈에도 적용된다.
- 앞으로 만들 모든 모듈의 import 방향이 문서화된다.
- 테스트 실패 없이 기준선 report가 생성된다.

### 제외

- UI 구현
- 프로젝트 format 변경
- renderer 기능 추가

## 5. M1 - 컴포지션 Schema와 프로젝트 저장

### 목표

Motion Designer 데이터가 UI와 renderer 없이도 생성, 검증, 저장, 복원되게 한다.

### 구현 파일

- `app/motion_designer/__init__.py`
- `app/motion_designer/schema.py`
- `app/motion_designer/validation.py`
- `app/motion_designer/composition_service.py`
- `app/motion_designer/project_io.py`
- `app/actions/motion_namespace.py`
- `app/actions/editor_adapter_motion.py`

### 데이터 범위

- `MotionComposition`
- `MotionLayer`
- `MotionTransform`
- `AnimatedProperty`
- `Keyframe`
- `MotionEffectRef`
- `MotionMaskRef`
- `MotionBehaviorRef`
- `SourceRef`

### 프로젝트 I/O

- 현재 `FORMAT_VERSION = 1.2`이며 `motion_compositions`와 `motion_clips`를 저장한다.
- 구현 시점의 latest version을 1단계 올리고 이전 파일을 읽는 migration을 둔다.
- 저장 키는 `motion_compositions`다.
- 빈 프로젝트에는 빈 배열을 명시한다.
- unknown layer/property metadata는 가능한 한 보존한다.
- 깨진 composition 하나 때문에 전체 `.tgp`가 열리지 않는 구조를 피한다.

### 초기 액션

- `motion.composition.list`
- `motion.composition.create`
- `motion.composition.update`
- `motion.composition.duplicate`
- `motion.composition.delete`
- `motion.composition.validate`
- `motion.layer.list`
- `motion.layer.add`
- `motion.layer.update`
- `motion.layer.delete`
- `motion.layer.reorder`
- `motion.layer.parent`

### 테스트

- `tests/test_motion_schema.py`
- `tests/test_motion_validation.py`
- `tests/test_motion_project_io.py`
- `tests/test_motion_actions.py`
- 기존 `tests/test_project_io*.py`
- `tests/test_editor_architecture_rules.py`

### 완료 조건

- 100개 layer와 1,000개 keyframe을 가진 sample이 JSON round-trip한다.
- save-load-save 결과가 정규화 후 동일하다.
- 구버전 `.tgp`를 열면 빈 `motion_compositions`가 생성된다.
- 모든 mutation action이 `dry_run`, validation, undo label을 제공한다.
- cycle parent와 duplicate id가 validation에서 차단된다.

## 6. M2 - 키프레임, Bezier, Behavior 평가 코어

### 목표

모든 UI와 renderer가 공유하는 시간 평가 코어를 완성한다.

### 구현 파일

- `app/motion_designer/evaluator.py`
- `app/motion_designer/keyframes.py`
- `app/motion_designer/curves.py`
- `app/motion_designer/behaviors.py`
- `app/motion_designer/constraints.py`
- `app/motion_designer/commands.py`

### 기능

- hold, linear, cubic Bezier 보간
- scalar, vector2, vector3, color, bool, enum 값
- transform parent hierarchy
- anchor/pivot
- spatial motion path
- auto/ease-in/ease-out/ease-both tangent
- loop, ping-pong, offset loop
- fade, slide, scale, pop, spring, wiggle, follow path, look-at behavior
- behavior bake-to-keyframes
- time scale, source in, trim, reverse

### 액션

- `motion.keyframe.add`
- `motion.keyframe.update`
- `motion.keyframe.delete`
- `motion.keyframe.copy`
- `motion.keyframe.paste`
- `motion.keyframe.set_interpolation`
- `motion.curve.set_tangents`
- `motion.curve.retime`
- `motion.behavior.add`
- `motion.behavior.set_param`
- `motion.behavior.bake`

### 테스트

- `tests/test_motion_keyframes.py`
- `tests/test_motion_curves.py`
- `tests/test_motion_behaviors.py`
- `tests/test_motion_constraints.py`
- `tests/test_motion_evaluator_determinism.py`

### 수치 기준

- golden interpolation 오차 `1e-6` 이하
- 같은 입력의 반복 평가 결과가 byte-stable한 직렬화 결과를 가짐
- parent cycle은 평가 전에 실패
- 10분 타임라인의 끝 시간에서도 time rounding drift가 1 frame 미만
- behavior bake 전후 sampled transform 차이가 허용 오차 이내

### 완료 조건

- lower-third, logo reveal, spring title을 UI 없이 evaluator로 생성한다.
- PPT `AnimationSpec`과 Typography transform을 읽는 변환 adapter prototype이
  통과한다.
- Qt import 없이 전체 core test가 실행된다.

## 7. M3 - 독립 2D 제작 UI

### 목표

사용자가 독립 창에서 기본 모션 장면을 직접 만들 수 있게 한다.

### 구현 파일

- `app/motion_designer/ui/window.py`
- `app/motion_designer/ui/toolbar.py`
- `app/motion_designer/ui/canvas.py`
- `app/motion_designer/ui/layer_panel.py`
- `app/motion_designer/ui/inspector.py`
- `app/motion_designer/ui/timeline.py`
- `app/motion_designer/ui/dope_sheet.py`
- `app/motion_designer/ui/graph_editor.py`
- `app/motion_designer/ui/style.py`

### UI 범위

- text, image, shape, line, group, null, adjustment layer
- 선택, 이동, 회전, 스케일, anchor 이동
- layer visibility, lock, solo, parent, reorder
- timeline trim과 playhead
- keyframe 표시, 추가, 삭제, 다중 선택, 복사/붙여넣기
- dope sheet와 value/speed graph
- canvas guide, grid, safe area, zoom/pan
- inspector의 animated-property diamond
- undo/redo, autosave/recovery

### 상호작용 기준

- 객체 선택 시에만 기즈모가 보인다.
- 빈 캔버스를 클릭하면 선택과 기즈모가 사라진다.
- canvas 크기 조절은 화면 비율을 유지하고 객체 transform을 바꾸지 않는다.
- timeline wheel은 zoom, 빈 영역/가운데 버튼 drag는 pan이다.
- 긴 레이어 이름과 한글 폰트가 영역을 넘지 않는다.
- 타임코드 왼쪽 transport에는 처음, 역재생, 정지, 재생, 반복, 끝 버튼이
  항상 보이며 `J/K/L`과 `Ctrl+L` 단축키를 제공한다.

### 테스트와 증거

- `tests/test_motion_window_interactions.py`
- `tests/test_motion_canvas_selection.py`
- `tests/test_motion_timeline_ui.py`
- `tests/test_motion_graph_editor.py`
- `tools/qa_motion_ui.py`
- desktop 1920x1080, compact 1280x720 screenshot

### 완료 조건

- UI에서 5초 lower-third와 logo reveal을 저장하고 다시 연다.
- graph tangent drag 결과가 core keyframe에 반영된다.
- 모든 UI mutation이 command service와 undo stack을 사용한다.
- 모달 오류 없이 빈 composition, missing asset, 긴 composition을 연다.

### 제외

- video decode
- AR/PBR와 character renderer
- 최종 OpenGL 합성

## 8. M4 - OpenGL 2D 합성과 출력 Parity

### 목표

Motion Designer Alpha의 실제 픽셀 출력 경로를 만든다.

### 구현 파일

- `app/motion_designer/source_frame.py`
- `app/motion_designer/render_graph.py`
- `app/motion_designer/preview_renderer.py`
- `app/motion_designer/export_renderer.py`
- `app/motion_designer/cache.py`
- `app/motion_designer/source_adapters/image.py`
- `app/motion_designer/source_adapters/shape.py`
- `app/motion_designer/source_adapters/typography.py`

### 렌더 범위

- premultiplied RGBA
- normal, add, screen, multiply blend
- transform, crop, rounded corner, opacity
- fill, stroke, gradient
- mask와 track matte 기초
- layer FBO와 adjustment layer
- Full/Half/Quarter/Auto preview
- persistent OpenGL export worker

### 출력

- PNG still
- PNG alpha sequence
- MP4 H.264
- alpha-capable intermediate smoke output

ProRes 4444와 EXR의 최종 제품화는 M11에서 수행한다.

### 테스트와 QA

- `tests/test_motion_opengl_compositor.py`
- `tests/test_motion_alpha.py`
- `tests/test_motion_blend_modes.py`
- `tests/test_motion_preview_export_parity.py`
- `tests/test_motion_gpu_worker.py`
- `tools/qa_motion_parity.py`

### 품질 기준

- 정지 장면 preview/export RGB 평균 오차 `2/255` 이하
- alpha edge의 premultiplied color fringe 검출 0건
- 같은 frame을 반복 요청할 때 GPU context 재생성 0회
- cached 1080p 2D sample 목표 30 fps 이상
- scrub P95 100 ms 이내

### 완료 조건

- lower-third, logo reveal, kinetic title golden scenes가 통과한다.
- Alpha checkerboard와 실제 영상 배경 위 합성 증거가 생성된다.
- software renderer fallback이 제품 성공으로 보고되지 않는다.
- UI thread에서 blocking export를 실행하지 않는다.

## 9. M5 - 메인 타임라인 Motion Clip 통합

### 목표

Motion Designer 결과를 Tiger Studio 영상 편집에 실제로 사용한다.

### 구현 파일

- `app/motion_designer/timeline_bridge.py`
- `app/video_editor_motion_workflow.py`
- `app/video_editor_delegates_motion.py`
- `app/project_player_motion_workflow.py`
- `app/video_exporter_motion_workflow.py`
- `app/video_editor_motion_lane_row.py`

### 기능

- Media Pool/선택 구간에서 composition 생성
- `MotionClip` 생성, trim, move, split, duplicate, loop
- Motion Clip 더블클릭 편집
- live composition revision과 cache invalidation
- main preview RGBA 합성
- 최종 video export 합성
- clip badge, cache status, missing-source status
- Render Queue pre-cache

### 액션

- `motion.composition.create_from_timeline`
- `motion.timeline.place_clip`
- `motion.timeline.update_clip`
- `motion.timeline.remove_clip`
- `motion.preview.cache_range`
- `motion.preview.capture`

### 테스트와 증거

- `tests/test_motion_timeline_bridge.py`
- `tests/test_motion_clip_editing.py`
- `tests/test_motion_player_composite.py`
- `tests/test_motion_video_export.py`
- `tests/test_motion_cache_invalidation.py`
- `tools/qa_motion_editor_integration.py`

실제 증거에는 영상 track, Motion Clip, main preview, export frame이 한 세트로
포함되어야 한다.

### 성능 회귀 기준

- Motion Clip이 없는 프로젝트의 재생 성능 저하 5% 이내
- 비활성 Motion Clip 때문에 renderer나 depth 추정이 실행되지 않음
- Motion Clip 시작 시점에서 회색 화면, 새 창, UI stall이 발생하지 않음
- 동일한 cached frame을 main preview와 export가 공유 가능

### 완료 조건

- 실제 동영상 위에 Motion Clip을 놓고 재생·seek·export한다.
- composition 수정 후 stale cache가 남지 않는다.
- 프로젝트 저장/재열기 후 Motion Clip과 source 연결이 유지된다.
- 이 마일스톤 완료 시 `Motion Designer Beta`로 전환한다.

## 10. M6 - Vector, Typography, Effect, Mask, PPT 브리지

### 현재 구현 상태 (2026-07-22)

- 완료: 기존 `TextClip` 및 PPT `SlideElement`를 MotionLayer로 가져오는 제한적
  브리지, 지원 text/image/shape의 PPT native element 역변환과 bake 경고
- 완료: multiline/wrap/alignment/line-height/letter-spacing/font style 기반
  typography 렌더
- 완료: brightness/contrast, saturation, Gaussian blur, glow, unsharp mask,
  vignette의 preview/export 공통 렌더와 parameter keyframe action
- 완료: rectangle/ellipse mask, alpha/luma track matte, adjustment layer,
  effect/mask Inspector UI와 AI action
- 완료: animated Bezier path mask, feather/expansion/opacity keyframe,
  point/planar tracking sample cache 보간과 preview/export 공통 적용,
  Inspector 상태 표시와 `motion.mask.*` action
- 완료: source video와 현재 mask ROI를 사용하는 OpenCV point/planar tracking
  provider, forward-backward feature 검증, RANSAC affine 누적, shot-cut 중단,
  비동기 Inspector 실행/취소와 `motion.mask.tracking.generate` action
- 완료: Pen/Bezier anchor·tangent 편집, rectangle/ellipse/polygon/star,
  Boolean path 코어와 action, fill/stroke/gradient, Trim Path, Repeater,
  source parameter keyframe action, preview/export 공통 vector 렌더와
  QPainterPath tessellation cache
- 완료: Vector Inspector에서 여러 shape layer를 live Boolean operand로 연결,
  union/subtract/intersect/exclude 선택, operand 원본 표시 전환, transform/time
  평가 후 preview/export/Canvas 공통 합성, 누락·순환 참조 validation과
  `motion.vector.boolean.layers.set` action
- 완료: 최종 QPainterPath의 fill/stroke/Boolean/Trim 결과를 GLU 삼각형 mesh로
  캐시하고, transform/anchor/Repeater/opacity를 GPU uniform으로 평가하는
  OpenGL VAO/VBO 직접 Preview 경로. Preview 명시 opt-in, 동일 geometry VBO
  재사용, 지원하지 않는 radial/effect/mask/matte graph의 Painter fallback,
  실제 Windows OpenGL 캡처와 Painter 평균 RGB 오차 `2/255` 이하 QA
- 완료: 기존 typography animation registry 기반 IN/HOLD/OUT, 문자/단어/줄
  selector, 범위/reverse/stagger, per-glyph transform/color/opacity,
  grapheme-aware 한글/CJK 처리, text-on-Bezier-path, variable font axis,
  font fallback/preflight, Text Inspector와 AI action
- 완료: fill-only typography의 bounded glyph atlas와 OpenGL texture cache,
  글자별 transform/color/opacity GPU Preview, atlas revision 재사용,
  용량 초과 및 stroke/shadow/background/effect/mask의 명시적 Painter fallback,
  실제 Windows GL 캡처와 Painter 평균 RGB 오차 `0.2/255` 이하 QA
- 완료: `QTextLayout`/`QGlyphRun` 기반 Arabic 문맥형 glyph, ligature/source-index,
  mixed RTL/LTR 배치를 공통 layout으로 보존하고 Painter, text-on-path, GPU
  atlas가 같은 shaped glyph를 사용
- 완료: Text Inspector의 path 생성/해제/offset, Canvas의 Bezier guide,
  anchor/tangent/offset drag, point 추가·삭제, undoable document mutation,
  AI/MCP path set/clear/offset action
- 완료: `AnimationSpec`의 appear/fade in/fade out/move/scale, start/duration,
  trigger/click index/easing을 Motion behavior로 가져오고 다시 native PPT animation으로
  내보내는 무손실 왕복. 시작 전 숨김과 종료 상태 유지, out-only animation OOXML,
  비지원·다중 behavior 및 native 범위 초과의 명시적 bake 경고

### 목표

기존 창작 기능을 복제하지 않고 Motion Layer로 재사용한다.

### 작업 묶음

#### Vector Shape Engine

- Pen/Bezier path와 canvas point editing
- rectangle, ellipse, polygon, star primitive
- union, subtract, intersect, exclude Boolean operation
- fill, stroke, dash, cap, join, animated gradient
- Trim Path와 Repeater
- path/point/gradient/trim/repeater property keyframe
- authoring path와 OpenGL tessellation cache 분리

#### Typography

- `TextStyle`, IN/HOLD/OUT, per-glyph transform adapter
- typo preset을 animated text layer로 변환
- character/word/line selector와 stagger
- text-on-path와 per-glyph transform/color/opacity
- variable font axis와 한글/CJK shaping/fallback
- GPU glyph cache와 font revision invalidation
- font fallback과 missing font preflight
- 간단한 Motion text를 PPT native text로 되돌리는 제한 변환

#### Effect/Color/Node

- `VideoFilterParams`와 node params를 layer effect로 연결
- curves, levels, LUT, glow, vignette, unsharp mask 우선
- effect parameter keyframe
- adjustment layer와 bypass

#### Mask/Tracking

- bitmap/power window mask adapter
- alpha/luma track matte
- animated mask path
- feather, expansion, opacity keyframe
- point/planar tracking cache를 layer transform, camera 또는 mask path에 연결
- source video에서 mask ROI의 point/planar sample 자동 생성과 shot-cut 진단

#### PPT

- `.tgppt`의 element를 Motion Layer로 가져오기
- 지원 PPT animation을 Motion preview behavior로 가져오고 native animation으로 되돌리기
- 효과, 마스크, 다중 behavior, transform keyframe과 범위 초과 값을 bake 대상으로 진단
- Motion Composition poster/MP4를 PPT video actor로 보내기
- PPT 편집 원본은 `.tgppt`로 유지

### 구현 파일

- `app/motion_designer/adapters/typography.py`
- `app/motion_designer/typography_layout.py`
- `app/motion_designer/typography_gpu.py`
- `app/motion_designer/typography_gpu_renderer.py`
- `app/motion_designer/vector_shapes.py`
- `app/motion_designer/vector_tessellation.py`
- `app/motion_designer/effect_adapter.py`
- `app/motion_designer/mask_adapter.py`
- `app/motion_designer/tracking_provider.py`
- `app/motion_designer/content_bridge.py`
- `app/motion_designer/ppt_animation_bridge.py`

### 테스트

- `tests/test_motion_vector_shapes.py`
- `tests/test_motion_vector_tessellation.py`
- `tests/test_motion_typography_adapter.py`
- `tests/test_motion_typography_gpu.py`
- `tests/test_motion_typography_shaping.py`
- `tests/test_motion_effect_adapter.py`
- `tests/test_motion_mask_tracking.py`
- `tests/test_motion_content_bridge.py`
- 기존 `tests/test_pptgen_*.py`

### 완료 조건

- Pen path, Boolean, Trim Path, Repeater golden scene이 preview/export에서 일치한다.
- 긴 한글/CJK 문장과 mixed-font 문장이 글자 손실 없이 움직인다.
- typography preset 5종이 실제 움직임을 유지한다.
- 지원 effect의 preview/export parameter 값이 동일하다.
- tracked mask가 seek와 export에서 같은 위치에 있다.
- 지원 PPT animation이 UI 없는 action 경로에서도 timing/trigger/easing 손실 없이 왕복한다.
- PPT 왕복 시 지원되지 않는 효과는 bake 경고를 낸다.

## 11. M7 - Sound Editor, Composer, Voice Lab 연동

상태: **완료 (2026-07-22)**

### 목표

모션을 오디오 파형 추측만이 아니라 Tiger Studio의 구조화된 음악·음성 데이터와
연결한다.

### 구현 파일

- `app/motion_designer/audio_analysis.py`
- `app/motion_designer/audio_reactive.py`
- `app/motion_designer/composer_bridge.py`
- `app/motion_designer/voice_bridge.py`
- `app/motion_designer/ui/audio_panel.py`
- `app/motion_designer/ui/audio_worker.py`
- `app/actions/editor_adapter_motion_audio.py`

### 기능

- composition audio lane과 waveform
- amplitude, bass, mid, treble envelope
- onset/beat marker
- smoothing, attack, release, clamp, invert mapping
- Composer BPM/section/note event 우선 사용
- Voice Lab sentence/word/phoneme timing
- text reveal과 actor lip-sync cue
- Sound Editor processed clip reference

### 구현 결과

- Audio 탭에서 오디오/영상 파일을 선택하면 별도 worker thread가 mono envelope를
  분석하며 UI thread와 프레임 evaluator에서는 FFT를 실행하지 않는다.
- 분석 cache는 source 절대 경로, 파일 크기, 수정시각, 명시적 source revision을
  포함한 SHA-256 서명을 가진다. 액션 바인딩은 stale cache를 거부한다.
- audio reactive curve는 composition time 기준으로 미리 컴파일되어 reverse/loop
  layer local time과 분리된다. preview, main composite, export가 같은 evaluator를
  사용한다.
- Bake는 현재 audio reactive와 behavior 결과를 Position/Scale/Rotation/Opacity/
  Anchor의 일반 keyframe으로 고정하고 실시간 binding과 behavior를 제거한다.
- Composer timing은 추정 beat보다 높은 priority를 가지며 BPM beat, section 강도,
  MIDI note-on/off를 보존한다.
- Voice timing은 명시적 word/phoneme 구간을 보존하고, word 구간이 없으면 문장 안에서
  결정적으로 분배한다. text reveal과 actor lip-sync cue를 같은 timing source ID로
  연결한다.

### 액션

- `motion.audio.analyze`
- `motion.audio_reactive.bind`
- `motion.audio_reactive.update`
- `motion.audio_reactive.bake`
- `motion.composer.import_timing`
- `motion.voice.import_timing`

### 테스트와 QA

- `tests/test_motion_audio_analysis.py`
- `tests/test_motion_audio_reactive.py`
- `tests/test_motion_composer_bridge.py`
- `tests/test_motion_voice_bridge.py`
- `tools/qa_motion_audio_sync.py`

### 완료 조건

- beat title, spectrum-like scale motion, TTS word reveal sample을 생성한다.
- preview와 export의 audio sync drift가 10분 기준 1 frame 미만이다.
- Composer event가 있으면 추정 beat보다 우선한다.
- audio 분석 cache가 source revision 변경 시 무효화된다.

완료 증거:

- `tests/test_motion_audio_analysis.py`, `tests/test_motion_audio_reactive.py`,
  `tests/test_motion_composer_bridge.py`, `tests/test_motion_voice_bridge.py`
- action/UI 회귀: `tests/test_motion_actions.py`, `tests/test_motion_designer_ui.py`
- `tools/qa_motion_audio_sync.py`가 600,000ms, 30fps, 1,200 beat에서
  `max_sync_drift_frames=0.0`과 evaluator/render-graph/export parity를 기록한다.
- 실제 UI 캡처와 보고서는 재생성 가능한
  `debugCapture/motion_designer/motion_designer_audio_1600x900.png`,
  `debugCapture/motion_designer/audio_sync_qa.json`에 둔다.

## 12. M8 - AR/PBR 3D 레이어

상태: **완료 (2026-07-22)**

### 목표

기존 AR/PBR 렌더러를 Motion Designer의 3D source로 연결한다.

### 구현 파일

- `app/motion_designer/ar_pbr_source.py`
- `app/motion_designer/adapters/ar_pbr.py`
- `app/motion_designer/ui/ar_pbr_panel.py`
- `app/actions/editor_adapter_motion_ar_pbr.py`
- 기존 `app/ar_pbr/compositor.py`와 외부 OpenGL helper

### 기능

- GLB/GLTF/FBX Media Pool drag-and-drop
- object transform keyframe
- camera transform, target, FOV, focus keyframe
- light transform, color, intensity keyframe
- HDRI 선택과 exposure
- PBR surface, metallic, roughness, clearcoat
- shadow, SSAO, bloom, depth of field 품질 설정
- optional depth SourceFrame
- 3D gizmo와 auto framing

### 액션

- `motion.ar_pbr.add`
- `motion.ar_pbr.set_material`
- `motion.camera.add`
- `motion.camera.update`
- `motion.light.add`
- `motion.light.update`
- `motion.depth_group.set`
- `motion.ar_pbr.diagnostics`

### 테스트와 증거

- `tests/test_motion_ar_pbr.py`
- `tests/test_motion_actions.py`
- `tests/test_motion_architecture_rules.py`
- `tests/test_motion_designer_ui.py`
- 기존 AR/PBR golden sample과 `tests/test_ar_pbr_*.py`
- `tools/qa_motion_ar_pbr.py`

### 완료 조건

- 실제 GLB와 GLTF로 turntable/product reveal을 만든다.
- UV, material, light, shadow가 기존 AR/PBR viewer와 합리적으로 일치한다.
- Motion Designer가 별도 software 3D renderer로 우회하지 않는다.
- 3D가 없는 composition은 AR/PBR pipeline을 초기화하지 않는다.

### 구현 결과

- AR/PBR object, Camera, Light를 독립 Motion Layer로 저장하며 object transform,
  camera target/FOV/focus, key-light color/intensity와 PBR surface 값을 같은 keyframe
  evaluator로 평가한다.
- 3D Inspector는 선택 종류에 따라 object/camera/light 제어만 표시한다. Auto Frame은
  기본 켜짐이며 명시적으로 끌 수 있어, 모델별 bounds 차이로 기본 화면에서 지나치게
  작아지는 문제를 막는다.
- source adapter는 기존 `full_model_view_gpu_export_service`만 사용한다. 실패 시
  diagnostics에 fallback/error를 남기며 M8 제품 증거에서는 fallback을 허용하지 않는다.
- Camera 회전은 현재 model-view renderer에서 inverse object orbit로 변환된다. 조명은
  HDRI와 단일 key light까지 지원하며 다중 light rig를 지원한다고 주장하지 않는다.
- depth group은 여러 AR/PBR layer가 명시적 depth source/path를 공유하게 한다. 메인
  에디터의 영상 depth는 composite bridge가 공급하고, standalone Motion 문서는 depth
  frame path가 있어야 occlusion을 적용한다.

완료 증거:

- durable GLTF `sample_assets/pbr_blender_scenes/polyhaven/models/Camera_01/Camera_01_1k.gltf`
  를 640x360 Motion composition으로 실제 OpenGL 렌더했다.
- `tools/qa_motion_ar_pbr.py`는 texture map 12개, missing texture 0, shadow-map PCF,
  auto framing, camera/light keyframe 변화와 depth occlusion을 확인한다.
- 동일 시점 Preview/Export RGBA는 `max_abs_channel_error=0`,
  `different_pixel_count=0`이었다.
- 재생성 가능한 보고서와 실렌더 이미지는
  `debugCapture/motion_designer/ar_pbr/report.json`과
  `debugCapture/motion_designer/ar_pbr/evidence.png`에 둔다.

## 13. M9A - Live2D와 Spine 레이어

구현 상태: **완료 (2026-07-22)**

### 목표

2D 캐릭터 renderer 두 종류를 공통 actor source 계약으로 연결한다.

### 기능

- Live2D model/motion/expression/parameter timing
- Spine skeleton/skin/animation/mix timing
- actor transform, opacity, crop, matte
- Voice Lab lip-sync cue
- performance source 선택 연결
- alpha frame cache와 status

### 구현 경계

- Qt-free 공통 source schema와 시간 평가는 `app/motion_designer/actor_source.py`가
  담당한다. `live2d_actor`와 `spine_actor`는 같은 transform/opacity/playback/
  Voice cue 계약을 직렬화한다.
- `app/motion_designer/adapters/live2d.py`는 기존 Cubism GPU renderer를 재사용한다.
  상태형 Cubism motion은 고정 FPS reset/forward seek로 임의 시점을 평가하고,
  같은 timeline frame의 Preview와 Export는 품질 중립 canonical frame cache를 공유한다.
  Motion 전용 clip은 결정성을 위해 자동 blink/breath를 끄며 사용자가 지정한 motion,
  expression, parameter와 lip-sync cue를 우선한다.
- `app/motion_designer/adapters/spine.py`는 기존 Spine actor renderer를 재사용한다.
  현재 Motion 경로는 worker-safe CPU full renderer 하나를 Preview와 Export가 공유해
  픽셀 parity를 보장한다. 기본 Spine skin이 시각적으로 거의 비어 있으면
  `app/spine_editor/actor_track.py`가 가장 완전한 named skin으로 복구한다.
- Actor Inspector는 Live2D motion group/index/expression과 Spine animation/skin,
  loop/rate/position/scale/opacity를 편집한다. UI와 AI는 같은 source params를 쓴다.
- Action ID는 `motion.live2d.add`, `motion.spine.add`, `motion.actor.update`,
  `motion.actor.lipsync.set`, `motion.actor.diagnostics`다.

### 테스트와 증거

- `tests/test_motion_actor_sources.py`
- `tests/test_motion_actions.py`
- `tests/test_motion_designer_ui.py`
- `tests/test_spine_actor_qa.py`
- 기존 Live2D/Spine corpus QA
- `tools/qa_motion_actors.py`

### 완료 조건

- 각각 최소 3개 실제 지원 모델로 preview/export를 검증한다.
- Live2D와 Spine의 지원 범위를 별도로 표시한다.
- raw/암호화 Unity AssetBundle을 자동 지원한다고 주장하지 않는다.
- actor-only composition도 빈 화면으로 오판하지 않는다.

### 실제 완료 증거

- Live2D: Hiyori, Haru, Mao를 기존 Cubism GPU renderer로 실제 렌더했다.
- Spine: celestial-circus, chibi-stickers, mix-and-match를 기존 Spine renderer로
  실제 렌더했다.
- QA는 알파 존재뿐 아니라 어두운 matte 합성 후 RGB 표준편차를 검사해 거의 빈
  guide/effect skin을 통과시키지 않는다.
- 6종 모두 동일 시점 Preview/Export에서 `max_abs_channel_error=0`이었다.
- 재생성 명령은 `tools/qa_motion_actors.py`이며 보고서와 contact sheet는
  `debugCapture/motion_designer/actors/report.json`과 `evidence.png`에 생성된다.
- 같은 도구가 실제 Motion Designer 창에서 Hiyori layer와 Actor Inspector를 선택한
  `debugCapture/motion_designer/actors/actor_inspector.png`를 만들고 dark surface를
  자동 검사한다.

### 명시적 한계

- raw 또는 암호화 Unity AssetBundle에서 Live2D/Spine 파일을 자동 추출한다고
  주장하지 않는다. 지원되는 model/skeleton/atlas/texture 세트가 입력이어야 한다.
- Spine lip-sync cue timing은 저장·평가되지만 rig마다 다른 mouth slot/attachment를
  자동 추론해 구동하는 범용 mapping은 아직 없다.
- Spine Motion Preview의 현재 parity 경로는 CPU full renderer다. 기존 독립 Spine
  편집기의 GL preview를 제거한 것이 아니며, Motion에서 GL pre-render를 도입할 때도
  canonical frame parity를 유지해야 한다.

## 14. M9B - MMD 레이어

구현 상태: **완료 (2026-07-22)**

### 목표

기존 MMD player의 PMX/PMD/PBX/VMD 결과를 Motion Designer에서 사용한다.

### 기능

- model/motion 선택과 timing
- VMD camera가 있으면 camera source 선택
- camera가 없으면 bounds 기반 자동 framing
- toon light, shadow, bloom, material 설정
- motion/physics cache
- actor transform과 layer alpha

### 구현

- Qt-free source 계약과 시간 평가는 `app/motion_designer/mmd_source.py`가 소유한다.
- `app/motion_designer/adapters/mmd.py`는 별도 소프트웨어 renderer를 만들지 않고
  기존 `project_player_mmd_workflow`의 render packet과
  `MMDOffscreenGLRenderer`를 재사용한다.
- 같은 source revision, composition revision, viewport, quantized time은 Preview와
  Export가 품질 중립 canonical RGBA frame cache를 공유한다.
- MMD Inspector는 VMD 교체, loop/rate, VMD camera, IK, 물리, GPU skinning,
  spring response, view framing, bloom, light, shadow, 피부/머리/눈/입술/matcap/
  emissive 설정과 cache/backend 상태를 표시한다.
- Motion composition의 기본 MMD framing zoom은 standalone viewer보다 크게 잡아
  전신이 캔버스 높이를 거의 채우되 head/toe 안전 여백을 유지한다.
- action surface는 `motion.mmd.add`, `motion.mmd.update`,
  `motion.mmd.motion.set`, `motion.mmd.diagnostics`를 제공한다.
- VMD camera가 없으면 bounds 기반 framing을 유지하고 preflight에 정보로 기록한다.
  VMD가 없으면 정적 pose warning을 기록하며, SDEF가 있으면 precision CPU deformation
  경로와 일반 vertex의 GPU skinning 혼합을 명시한다.

### 테스트와 증거

- `tests/test_motion_mmd.py`
- `tests/test_motion_architecture_rules.py`
- 기존 MMD QA corpus와 render queue QA
- `tools/qa_motion_mmd.py`

### 완료 조건

- 춤, IK, 물리, 투명 재질을 포함한 지원 샘플을 검증한다.
- preview/export 같은 프레임에서 pose와 material이 일치한다.
- 캐시 미완료와 호환성 제한을 UI/preflight에 표시한다.

### 실제 검증

- Cantarella + Wavefile: GPU skinning, active IK 4, spring physics body 381,
  cutout 2, transparent 2, self-shadow receiver 14, bloom group 1을 확인했다.
- Alice + Wavefile: transparent group 10, face/hair ordering, self-shadow receiver 7,
  bloom group 2와 missing texture 0을 확인했다.
- Miku + camera VMD: 실제 camera frame 사용과 두 시점 화면 변화를 확인했다.
- 세 샘플 모두 실제 OpenGL renderer만 사용했고 동일 시점 Preview/Export의
  differing channel은 0이다.
- 증거: `debugCapture/motion_designer/mmd/evidence.png`,
  `debugCapture/motion_designer/mmd/mmd_inspector.png`,
  `debugCapture/motion_designer/mmd/report.json`.

### 명시적 한계

- `auto` 물리는 설치된 backend에 따라 PyBullet 또는 spring으로 결정된다. 현재 M9B
  증거는 spring backend를 사용했으며 Bullet 완전 재현이라고 주장하지 않는다.
- SDEF 경로는 기존 MMD corpus에서 지원하지만 이번 Motion 3종 증거에는 SDEF 모델이
  포함되지 않았다. SDEF vertex가 있으면 GPU-only라고 표시하지 않는다.
- 카메라 전용 VMD는 모델 bone motion을 만들지 않는다. camera VMD와 dance VMD를
  동시에 병합하는 별도 multi-VMD authoring UI는 현재 범위가 아니다.

## 15. M9C - VRM 레이어와 캐시

### 목표

MToon GPU VRM을 Motion Layer로 연결하되 현재 first-frame 비용을 숨기지 않는다.

### 기능

- VRM/MToon source adapter
- bust-up/half/full-body framing
- pose, head, blink, expression, lip-sync timing
- source-person visibility policy 재사용
- persistent renderer worker
- pose/frame pre-cache
- cache-required/realtime-ready 상태

### 테스트와 증거

- `tests/test_motion_vrm.py`
- 기존 VTuber source framing/motion quality test
- `tools/qa_motion_vrm.py`

### 완료 조건

- MToon GPU renderer가 명시되고 software VRM 증거를 제품 성공으로 쓰지 않는다.
- blink, head pitch/yaw, expression이 실제 animation frame에서 보인다.
- 작은/floating avatar가 아닌 source exposure에 맞는 framing을 사용한다.
- 캐시 후 재생 성능과 캐시 전 준비 시간을 각각 보고한다.

### 현재 구현 완료 (2026-07-22)

- Qt-free `app/motion_designer/vrm_source.py`가 VRM0/VRM1 profile, 명시적 pose,
  source exposure, bust-up/half/full-body framing, MToon lighting, loop/rate와
  cache FPS를 하나의 직렬화 가능한 source params 계약으로 관리한다.
- `app/motion_designer/adapters/vrm.py`는 방송의 internal VRM fallback과
  `vrm_mtoon_gpu`만 재사용한다. software VRM 및 generic AR/PBR/Marmoset 경로는
  Motion VRM 제품 경로로 선택하지 않는다.
- `app/vtuber/internal_vrm_fallback.py`는 기존 CSV/idle 방송 호출을 보존하면서
  선택적 `motion_frame` 입력을 받아 head yaw/pitch/roll, shoulder, mouth, blink를
  같은 MToon GPU descriptor에 적용한다.
- full-body 기본 자세는 T-pose로 남지 않도록 relaxed standing arm curve를 적용한다.
  최종 RGBA는 alpha bounds를 자른 뒤 선택한 framing 크기와 bottom safe line에 맞춘다.
- VRM Inspector와 `motion.vrm.add`, `motion.vrm.update`,
  `motion.vrm.pose.set`, `motion.vrm.diagnostics`가 같은 source 계약을 사용한다.
- `tools/qa_motion_vrm.py`는 durable Milica VRM0에서 full-body 두 포즈와 bust-up
  open/blink/speak 두 포즈를 실제 GPU로 렌더한다. 현재 증거는 software renderer 0,
  동일 시점 Preview/Export 완전 일치, 전신/얼굴 시점 변화 50,622 pixel,
  visible alpha와 하단 고정을 기록한다.
- 증거: `debugCapture/motion_designer/vrm/evidence.png`,
  `debugCapture/motion_designer/vrm/vrm_inspector.png`,
  `debugCapture/motion_designer/vrm/report.json`.

### 명시적 한계

- 현재 Windows QA의 첫 비캐시 320x320 frame은 약 15.6초, 이후 새 pose는
  약 3.2-5.2초였다. 같은 시점 cache hit는 약 0.0005초지만 실시간 VRM 렌더라고
  주장하지 않는다. authoring playback은 pre-cache가 필요한 상태다.
- 현재 제품 증거는 durable Milica VRM0 한 종이다. 모든 제3자 VRM humanoid node,
  expression bind, spring bone 호환을 검증했다고 주장하지 않는다.
- Motion VRM의 explicit pose는 head/upper-body와 face morph 범위다. full-body mocap,
  손가락, locomotion, spring-bone simulation authoring은 M9C 완료 주장에 포함하지 않는다.

## 16. M10 - Behavior, 경량 표현식, GPU Particle, 템플릿, 방송, AI

구현 상태: **완료 (2026-07-22)**

### 목표

사용자가 빈 화면에서 시작하지 않고, 사람과 AI가 같은 기능으로 결과를 만든다.

### Behavior와 경량 표현식

- spring, wiggle, follow, look-at, loop, delay, stagger 보강
- property link, time, index, add/multiply, clamp, remap
- audio/beat channel reference
- dependency cycle detection
- expression result bake-to-keyframes
- 임의 Python/JavaScript 실행은 허용하지 않음

### GPU Particle V1

- point/box/circle/path emitter
- continuous birth와 burst
- lifetime, velocity, gravity, turbulence
- sprite/shape particle
- color/size/opacity over life
- deterministic seed
- normal/add/screen blend와 기본 depth sort

### 템플릿 1차 목표

- Clean Lower Third
- Character Nameplate
- Logo Reveal
- Product Callout
- Stream Stinger
- Music Beat Title
- Vertical Shorts Hook
- Anime Character Intro
- MMD Dance Title
- VRM Stream Starting/Ending

각 템플릿은 16:9, 9:16, 1:1 중 해당 가능한 variant와 실제 animated preview를
가진다.

### 방송 연동

- `realtime`, `cached`, `offline_only` 등급
- lower-third live parameter update
- stinger alpha pre-render
- Program Output preflight

### AI 기능

- 자연어 요청에서 composition plan 생성
- 계획 preview와 user confirmation
- action transaction 적용
- 전체 transaction undo
- asset missing, renderer cost, bake requirement 설명

### 실제 구현 (2026-07-22)

- 완료: 오른쪽 dock형 AI Workspace, 텍스트/이미지 파일 drag-and-drop,
  클립보드 이미지 저장, 첨부 썸네일/삭제, prompt와 proposal 검토
- 완료: Qt-free `MotionAIRequest`/`MotionAIProposal`, 로컬 레이아웃 fallback,
  Apply 전 무변경, Apply 전체를 한 번의 UI undo로 처리
- 완료: `motion.ai.plan`과 `motion.ai.apply` action으로 동일한 멀티모달
  요청/제안 계약을 AI·MCP에 노출
- 완료: `expressions.py`의 JSON operation tree가 property/time/index/audio/beat 참조,
  산술·clamp·remap·삼각함수·vector 조합을 평가하며 dependency cycle과 깊이/노드
  한도를 차단한다. 임의 Python/JavaScript 문자열은 실행하지 않는다.
- 완료: expression, behavior, audio-reactive transform을 일반 keyframe으로 bake해
  런타임 중복 적용을 제거한다.
- 완료: `particles.py`가 point/box/circle/path emitter, continuous/burst birth,
  lifetime/variance, velocity/gravity/turbulence, deterministic seed, shape/sprite,
  over-life color/size/opacity와 normal/add/screen을 공통 평가한다.
- 완료: circle/square/triangle particle은 실제 OpenGL VBO/uniform 경로를 사용한다.
  sprite particle은 현재 canonical premultiplied-alpha renderer를 사용하며 GPU
  packet으로 가장하지 않는다. 방송에서는 alpha media bake를 권장한다.
- 완료: Particle Inspector와 `motion.particle.add/update/diagnostics/bake`가 같은
  params 계약을 사용한다. bake는 호출자가 지정한 durable output에 alpha PNG
  sequence와 manifest를 만든다.
- 완료: 10종 built-in template, 16:9/9:16/1:1 지원 variant, stable control ID
  `headline`, `subtitle`, `accent_color`, `surface_color`, `duration_ms`, 실제 animated
  preview와 action/UI 적용 경로를 구현했다.
- 완료: `broadcast_bridge.py`가 `realtime`, `cached`, `offline_only` 비용 등급을
  계산한다. cached composition은 현재 composition revision과 일치하는
  premultiplied-alpha cache manifest가 없으면 Program Output preflight에서 차단된다.
- 완료: `motion.broadcast.live_control.set`은 stable control ID만 갱신하고 기존
  broadcast cache를 무효화한다. `motion.broadcast.stinger.render`는 실제 RGBA PNG
  sequence를 렌더하고 revision-bound manifest를 등록한다.
- 완료: Qt-free `ai_planner.py`가 AI dry-run의 생성 레이어 수, projected total,
  renderer cost grade, 누락 자산, 명시적 font file 문제, broadcast bake/cache 요구,
  composition validation을 반환한다. AI Workspace에도 같은 Preflight가 표시된다.
- 범위 밖: 외부 vision-language provider의 실제 이미지 의미 분석, 여러 제안 비교,
  provider 응답 streaming은 M10 완료 주장에 포함하지 않는다. 현재 built-in provider는
  deterministic local layout fallback이다.

### 구현 파일

- `app/motion_designer/templates.py`
- `app/motion_designer/expressions.py`
- `app/motion_designer/particles.py`
- `app/motion_designer/template_preview.py`
- `app/motion_designer/broadcast_bridge.py`
- `app/motion_designer/ai_planner.py`
- `app/motion_designer/ai_workspace.py`
- `app/motion_designer/ui/ai_panel.py`
- `app/actions/motion_namespace.py` 전체 확장

### 테스트와 QA

- `tests/test_motion_expressions.py`
- `tests/test_motion_expression_cycles.py`
- `tests/test_motion_particles.py`
- `tests/test_motion_particle_parity.py`
- `tests/test_motion_templates.py`
- `tests/test_motion_template_variants.py`
- `tests/test_motion_broadcast_bridge.py`
- `tests/test_motion_ai_actions.py`
- `tests/test_motion_ai_workspace.py`
- `tests/test_motion_actions.py`
- `tests/test_motion_designer_ui.py`
- `tools/qa_motion_template_catalog.py`
- `tools/qa_motion_gpu_particles.py`

### 완료 조건

- expression dependency cycle과 invalid operation이 안전하게 차단된다.
- particle golden scene이 같은 seed에서 preview/export 동일 결과를 낸다.
- behavior/expression/particle 결과를 keyframe 또는 alpha media로 bake할 수 있다.
- UI와 action으로 같은 템플릿 결과를 만든다.
- 모든 공개 template parameter가 stable id를 갖는다.
- AI dry-run 결과가 생성할 레이어, 렌더 비용, 경고를 보여준다.
- 방송용 template이 실시간 비용 등급을 위반하면 preflight에서 막힌다.

### 실제 완료 증거

- `tools/qa_motion_gpu_particles.py`: 실제 Windows OpenGL context, software renderer 0,
  particle 80개, draw 80, vertex 480, VBO upload 1, GL error 0, Painter reference 대비
  mean RGB absolute error 약 0.095/255와 12 초과 pixel 약 0.21%를 기록했다.
- `tools/qa_motion_template_catalog.py`: 10종 template 모두 validation 통과,
  animated frame 변화 검출, stable published control 5종 일치를 기록했다.
- Motion 테스트 35개 파일은 native Qt teardown 충돌을 피하기 위해 파일별 독립
  프로세스로 실행했고 총 177개가 통과했다.
- 방송 alpha cache 테스트는 실제 PNG frame과 manifest를 만들고 현재 revision에서
  preflight 통과, stale/missing cache에서 차단됨을 확인한다.

## 17. M11 - 색 관리, 표준 출력, 장시간 QA, 설치본 검증

구현 상태: **완료 (2026-07-22)**

### 목표

Motion Designer를 개발 환경이 아니라 배포 가능한 제품 기능으로 마무리한다.

### Color Management

- source별 sRGB/linear/HDR 입력 선언
- texture upload와 shader sampling 변환 규칙
- linear-space blend, glow, bloom
- preview display transform과 export output transform 분리
- SDR/HDR tone mapping
- premultiplied alpha와 gamma 적용 순서 고정
- OpenEXR scene-linear intermediate
- OpenColorIO 또는 동등 backend 도입 여부를 실제 설치 크기와 parity로 결정

### 출력

- MP4 H.264/H.265
- MOV ProRes 4444 alpha
- PNG sequence
- OpenEXR sequence
- PNG/JPEG/WebP still
- Lottie JSON 지원 subset
- SVG 정지/지원 subset
- glTF/GLB 3D subscene 제한 출력
- OTIO media/timing reference 제한 출력

### Preflight

- missing media/font
- unsupported effect/layer
- bake required
- alpha codec availability
- GPU/context/VRAM readiness
- stale cache
- color space mismatch
- untagged source와 unsupported HDR transfer
- character compatibility scope

### 장시간 QA

- 30분 composition
- 1,000 layer stress project
- 10,000 keyframe stress project
- 반복 undo/redo/autosave/recovery
- render queue cancel/resume/retry
- GPU context loss/recovery
- project relink와 이동

### 구현 파일

- `app/motion_designer/export_profiles.py`
- `app/motion_designer/export_pipeline.py`
- `app/motion_designer/color_management.py`
- `app/motion_designer/interchange.py`
- `app/motion_designer/relink.py`
- `app/motion_designer/recovery.py`
- `app/motion_designer/release_acceptance.py`
- `app/motion_designer/ui/export_panel.py`
- `app/motion_designer/ui/export_worker.py`
- `tools/qa_motion_gpu_context_recovery.py`
- `tools/qa_motion_installer_smoke.py`
- `tools/qa_motion_long_run.py`
- `tools/qa_motion_release_acceptance.py`

### Release Gate

- `tests/test_motion_release_acceptance.py`
- `tests/test_motion_color_management.py`
- `tests/test_motion_export_profiles.py`
- `tests/test_motion_interchange.py`
- `tests/test_motion_relink.py`
- `tests/test_motion_recovery.py`
- `tests/test_editor_architecture_rules.py`
- `tests/test_debug_capture_boundary.py`
- 설치본 smoke test
- 실제 UI와 실제 export evidence bundle

### 구현 결과와 명시적 범위

- 새 composition은 `linear-srgb` 합성 계약과 straight-alpha 저장,
  premultiplied-alpha 내부 합성 계약을 명시한다. 구버전 metadata 없는 composition은
  외형 보존을 위해 `display-srgb` legacy 모드로 읽는다.
- 영상 위 Motion 최종 합성은 encoded sRGB를 unpremultiply한 뒤 linear decode,
  linear premultiply/composite, sRGB encode 순서를 사용한다. 현재 Qt render graph 내부의
  복수 Motion layer blend는 display-space이므로 Output preflight에 경고를 남긴다.
- HDR project output, tone mapping, OCIO config, project LUT는 Preview/Export parity가
  구현되기 전까지 조용히 무시하지 않고 preflight에서 차단한다. 현재 제품 출력 범위는
  명시적 SDR sRGB다.
- H.264, H.265, ProRes 4444, PNG RGBA sequence, OpenEXR scene-linear sequence,
  PNG/JPEG/WebP still을 실제 FFmpeg/Qt renderer로 출력한다. PNG sequence는 정상 완료
  프레임만 재사용해 취소 후 재개하고, 완료 전에는 manifest를 쓰지 않는다. 비디오
  취소 시 `.partial` 파일을 제거하고 전체 재시도한다.
- Lottie/SVG는 shape/text 제한 subset, OTIO는 외부 media timing reference subset,
  glTF/GLB는 단일 AR/PBR source passthrough subset이다. effect/mask/비표준 blend 등
  손실 가능한 항목은 export 전에 block 또는 bake-required로 보고한다.
- 프로젝트 이동은 기존 root 기준 상대 경로를 우선하고, 실패할 때 새 root의 유일한
  동일 basename만 자동 후보로 사용한다. 중복 basename은 자동 선택하지 않는다.
  MMD model/motion, actor/AR-PBR source, font file, particle sprite를 같은 계약으로 처리한다.
- Motion autosave는 원자적 replace와 SHA-256 checksum을 사용한다. 다른 composition,
  현재 revision보다 오래된 recovery, 손상된 payload는 명시적 override 없이는 적용하지 않는다.
- `release_acceptance.py`는 render-ready와 product-release-ready를 분리하고 실제 artifact가
  있는 표준 출력, 색/alpha, GPU parity/context recovery, 30분, stress, undo/recovery,
  queue recovery, relink, 설치본 smoke 증거를 모두 요구한다.

### 실제 완료 증거

- 표준 출력 8종과 Lottie/SVG 2종, 총 10개 실제 산출물을 생성했다.
- 1,000 layer와 10,000 keyframe stress, 500회 edit/undo/redo 및 checksum recovery,
  PNG cancel/resume와 H.264 cancel/retry, moved-project relink가 통과했다.
- Windows desktop OpenGL에서 vector, typography, particle Preview를 출력 reference와
  픽셀 비교했고 software renderer 0, GL error 0을 확인했다.
- `tools/qa_motion_gpu_context_recovery.py`는 QOpenGLWidget context destroy 신호를 두 번
  받고 새 context에서 동일 프레임을 다시 그려 mean/max RGBA error 0을 기록했다.
- 현재 소스로 PyInstaller와 Inno Setup 1.4.2를 다시 만들고 임시 OS 경로에 무인 설치했다.
  설치 파일 516개, 두 실행 파일, 실제 `Tiger Studio` 창 핸들, 정상 제거를 확인했다.
  설치본 SHA-256은 `996ca2fa045268fd914bad4b9cc4cb609bc7b40f6410cfc14829969e7bc9a8d3`이며,
  최신 패키징 입력보다 새로 생성됐다는 provenance gate도 통과했다.
- 전체 Motion 테스트 41개 파일은 Qt teardown 충돌을 피하도록 파일별 프로세스로 실행했고
  총 215개가 통과했다.
- 30분 실제 벽시계 OpenGL 번인은 1,800.24초 동안 80,723회 frame swap,
  평균 44.84 FPS, 최종 timeline 1,799.790초, 메모리 증가 8,896,512 bytes를 기록했다.
  backend는 `motion_vector_gpu`, context valid, GL error 0, software renderer 0이다.
- `tools/qa_motion_release_acceptance.py` 최종 집계는 표준 출력 10개와 필수 증거 전부를
  확인해 `remaining_release_evidence=[]`, `product_release_ready=true`를 기록했다.
- PyInstaller는 optional `glfw3.dll`과 PyOpenGL의 legacy VC9 helper DLL에 대한 경고를
  남긴다. Motion의 Qt desktop OpenGL 경로와 설치본 실행 smoke는 통과했지만, 이 결과를
  optional GLFW/freeglut 경로까지 검증했다는 주장으로 확대하지 않는다.

### 완료 조건

- 지원 출력이 설치본에서 성공한다.
- sRGB/linear/SDR/HDR golden chart가 preview/export 기준을 통과한다.
- unsupported 기능이 조용히 손실되지 않는다.
- 2D golden scene과 선택된 AR/PBR/character scene이 parity gate를 통과한다.
- 장시간 편집에서 undo/autosave/cache가 메모리 누수나 UI freeze를 만들지 않는다.
- Motion Designer 미사용 프로젝트의 성능 회귀가 허용 범위 안이다.
- `Motion Designer Product` 상태로 전환한다.

## 18. M12 - Plugin과 Template SDK

구현 상태: **관리 Action/MCP 기반 완료 (2026-07-22), runtime contribution loading 진행 전**

현재 완료된 범위는 versioned manifest 검증, 검색과 enable-state 저장, dependency
검사, declarative template-pack 검증/안전 설치, 그리고 아래 7개 Action/MCP
endpoint다. 플러그인의 Python/JavaScript/native 코드는 import하거나 실행하지 않으며,
활성 상태와 template 설치 결과는 재시작 후 적용 대상으로만 기록한다.

source/effect/behavior/exporter contribution을 실제 renderer와 inspector에 등록하는
runtime host, `plugin_sandbox.py`, 예외 격리, uninstall/safe-mode UI는 아직 M12의 남은
범위다. 따라서 이 단계는 M12 전체 완료나 외부 plugin 실행 호환을 주장하지 않는다.

### 목표

Motion Designer 1.0 이후 source, effect, behavior, exporter, template pack을 본체
수정 없이 확장할 수 있는 제한된 SDK를 제공한다.

### SDK 범위

- versioned plugin manifest
- plugin id/version/vendor/API compatibility
- source adapter registration
- GPU effect descriptor와 shader resource registration
- structured behavior registration
- exporter registration
- template pack과 published control schema
- dependency/capability declaration
- enable/disable/uninstall과 safe mode

V1 SDK는 임의 editor widget 주입이나 core project object 직접 mutation을 허용하지
않는다. UI 확장은 declarative inspector schema와 command/action 등록으로 제한한다.

### 구현 파일

- `app/motion_designer/plugin_registry.py`
- `app/motion_designer/plugin_manifest.py`
- `app/motion_designer/plugin_sandbox.py`
- `app/motion_designer/template_pack.py`
- `app/actions/motion_plugin_namespace.py`

### 액션

- `motion.plugin.list`
- `motion.plugin.inspect`
- `motion.plugin.enable`
- `motion.plugin.disable`
- `motion.plugin.validate`
- `motion.template_pack.install`
- `motion.template_pack.validate`

### 테스트와 QA

- `tests/test_motion_plugin_manifest.py`
- `tests/test_motion_plugin_registry.py`
- `tests/test_motion_template_pack.py`
- `tests/test_motion_architecture_rules.py`

현재 테스트는 API/경로/descriptor 차단, duplicate id, dependency enable/disable 순서,
enable-state persistence, ZIP traversal와 symlink/executable 차단, composition schema,
published control, 원자적 설치/교체, Action 등록과 destructive confirmation을 검증한다.
`tests/test_motion_plugin_failure_isolation.py`와 `tools/qa_motion_sdk_sample.py`는 runtime
host 구현 시 추가할 남은 QA다.

### 완료 조건

- sample source/effect/behavior/exporter plugin이 본체 파일 수정 없이 등록된다.
- 잘못된 API version과 dependency가 로드 전에 차단된다.
- plugin 예외가 project open, preview, export queue를 중단시키지 않는다.
- plugin을 비활성화해도 project가 placeholder와 진단 정보로 열린다.
- template pack이 published control, preview, license metadata를 검증한다.

## 18.1 고급 에디토리얼 모션 확장

2026-07-25 기준으로 M6의 기존 Track Matte, Typography selector/stagger,
Vector Repeater, parent hierarchy와 Cut Paper 기반 위에 다음 제품 기능을
추가했다.

- 일반 2D 레이어에 명시적으로 적용되는 2.5D Camera와 `depth_z` 패럴랙스
- 이미지·텍스트·벡터·캐릭터 레이어 공통 Replicator
- 레이어 이동량 기반 bounded motion blur
- directional blur, displacement, corner pin, mesh warp, paper fold 효과
- tape, staple, contact shadow, fold와 impact를 포함한 Paper Paste rig
- Headline Slam, Paper Rip Reveal, Cutout Collage, Editorial Camera Push,
  Beat-Synced Montage 연출 프리셋
- 동일 기능의 Inspector와 `motion.*` Action/MCP 표면

AR/PBR Camera의 기존 동작을 보존하기 위해 2D 투영은 `apply_to_2d=false`가
기본이다. 현재 범위는 편집 가능한 2.5D 에디토리얼 모션이며 완전한 3D scene
graph, 임의 동영상 displacement map, cloth simulation 또는 After Effects
plugin 호환을 의미하지 않는다.

## 19. 병렬 작업 계획

### 순차로 해야 하는 작업

```text
M0 -> M1 -> M2 -> M3 -> M4 -> M5
```

schema, evaluator, OpenGL SourceFrame, Motion Clip 계약은 먼저 고정해야 한다.

### M5 이후 병렬화

```text
Track A: M6 Vector/Typography/Effect/Mask/PPT
Track B: M7 Audio/Composer/Voice
Track C: M8 AR/PBR
Track D: M9A Live2D/Spine
Track E: M9B MMD
Track F: M9C VRM
```

각 track은 공통 `SourceFrame`과 cache interface만 사용하고 다른 renderer 내부를
수정하지 않는다. 통합 담당자는 adapter contract와 parity QA만 관리한다.

M10은 M6/M7과 최소 M8 또는 character adapter 하나가 끝난 뒤 시작할 수 있다.
M11 QA는 M4부터 누적 실행하되 최종 완료는 모든 release 대상 adapter가 고정된
후 판정한다. M12는 M11의 public schema와 renderer extension boundary가 고정된
후 시작한다.

## 20. 마일스톤 공통 완료 체크리스트

각 마일스톤은 다음 항목이 모두 체크되어야 닫는다.

- [ ] 기획 범위의 코드가 focused module에 있다.
- [ ] `video_editor_window.py` facade에 기능 로직을 추가하지 않았다.
- [ ] public schema와 migration이 문서화됐다.
- [ ] mutation에 undo/redo가 있다.
- [ ] action에 schema, dry-run, error result가 있다.
- [ ] unit/integration test가 통과한다.
- [ ] 실제 자산이 필요한 기능은 실제 자산 QA를 통과한다.
- [ ] preview/export parity를 확인했다.
- [ ] 성능 수치를 이전 기준선과 비교했다.
- [ ] 사용자에게 보이는 실패 상태와 복구 경로가 있다.
- [ ] `SPEC.md`와 Motion Designer 문서를 실제 구현 상태에 맞게 갱신했다.
- [ ] 실제 UI/렌더 evidence를 저장했다.

## 21. 첫 착수 백로그

M0-M1의 첫 작업 순서는 다음과 같다.

1. `tools/qa_motion_baseline.py` 작성
2. `docs/MOTION_DESIGNER_ARCHITECTURE.md` 작성
3. `app/motion_designer/schema.py` 작성
4. schema validation과 cycle 검사
5. composition service와 stable id 정책
6. `.tgp` save/load 연결과 migration
7. history snapshot에 `motion_compositions` 추가
8. `motion.composition.*` action 등록
9. M1 unit/integration test 작성
10. save/load/action QA report 생성

이 목록을 완료한 뒤에만 캔버스나 Graph Editor UI 작업을 시작한다. UI부터 만들면
PPT animation, Typography keyframe, 메인 timeline이 서로 다른 데이터 모델을 갖게
되어 다시 분리해야 한다.
