# Tiger Studio Motion Designer Architecture

상태: M0-M11 통합 구현 및 제품 출시 검증 완료  
기준 문서: `docs/MOTION_DESIGNER_PRODUCT_PLAN_KO.md`  
구현 순서: `docs/MOTION_DESIGNER_MILESTONES_KO.md`

## 1. 목적

Motion Designer는 Tiger Studio의 기존 미디어, 캐릭터, 3D, 오디오 기능을 다시
구현하는 도구가 아니다. 기존 기능을 시간 기반 레이어로 평가하고 메인 OpenGL
합성 경로로 전달하는 독립 저작 도구다.

초기 M0 계약을 유지하면서 schema, 독립 UI, 공유 render graph, 메인 타임라인
Motion Clip, 최종 영상 합성까지 연결됐다. 이후 기능도 별도 데이터 모델이나
프리뷰 전용 렌더 경로를 만들지 않고 이 계약을 확장한다.

## 2. 모듈 경계

```text
app/motion_designer/contracts.py
        ^
        |
schema / evaluator / keyframes / composition_service
        ^
        |
adapters / effect_adapter / rendering / project_io bridge
        ^
        |
Motion Designer UI / actions / main-editor workflow
```

의존성은 아래에서 위로 역류하지 않는다.

- core 계약과 schema/evaluator는 Qt와 OpenGL을 import하지 않는다.
- UI와 renderer는 core를 사용하지만 core는 UI와 renderer를 알지 못한다.
- `app/video_editor_window.py`는 계속 compatibility facade로 유지한다.
- 메인 편집기 연결은 `app/video_editor_motion_workflow.py`와 delegate에서 한다.
- Action/MCP adapter는 UI 위젯을 직접 조작하지 않고 composition service에
  `MotionCommand`를 전달한다.
- 기존 AR/PBR, Live2D, Spine, MMD, VRM renderer 내부를 Motion Designer core가
  직접 수정하지 않는다. 각 기능은 source adapter로 연결한다.

## 3. 공통 인터페이스

M0의 실행 가능한 계약은 `app/motion_designer/contracts.py`에 있다.

### 3.1 SourceFrame

```text
SourceAdapter.evaluate(time_ms, quality, viewport) -> SourceFrame

SourceFrame
  rgba                    CPU RGBA frame 또는 GPU texture/shared surface
  depth                   optional depth surface
  bounds                  source의 합성 경계
  premultiplied_alpha     내부 합성 표준은 true
  color_space             입력 색 공간
  cache_key               source revision을 포함한 선택적 캐시 키
  diagnostics             renderer와 fallback 상태
```

내부 합성은 premultiplied alpha를 표준으로 한다. source가 straight alpha를
반환하면 adapter 경계에서 변환하고 그 사실을 diagnostics에 기록한다.

### 3.2 MotionComposition

M1에서 실제 schema를 구현한다. 서비스와 renderer가 요구하는 최소 계약은 다음과
같다.

```text
id, name, duration_ms, fps, revision
```

저장 ID는 배열 index가 아니라 안정적인 문자열 ID다. 모든 변경은 revision을
올리며 Motion Clip과 renderer cache는 이 revision으로 무효화한다.

### 3.3 MotionCommand

UI와 AI/Action은 같은 명령 표면을 사용한다.

```text
id
operation
composition_id
params
expected_revision
transaction_id
```

`expected_revision`은 오래된 AI 요청이 새 편집 상태를 덮어쓰는 것을 막는다.
mutation은 향후 composition service의 validation과 undo transaction을 반드시
거친다.

## 4. 프로젝트 저장 경계

- 편집 원본은 별도 사설 파일이 아니라 `.tgp`의 `motion_compositions[]`에 둔다.
- 현재 포맷은 `FORMAT_VERSION = 1.2`다.
- 구버전 프로젝트를 읽을 때 빈 `motion_compositions`와 `motion_clips`를 제공한다.
- unknown metadata는 가능한 한 보존한다.
- 깨진 composition 하나가 전체 프로젝트 load를 막지 않게 항목별 validation
  결과를 제공한다.
- Motion Clip은 composition ID와 revision/cache 정보만 참조하며 원본 layer
  데이터를 복제하지 않는다.

## 5. 렌더 경계

- 제품 preview 기준은 `app/opengl_preview.py`의 `OpenGLPreviewWidget`이다.
- 실제 surface는 editor startup에서 미리 생성해 첫 미디어 drop 때 top-level
  window가 재생성되지 않게 한다.
- preview와 export는 같은 evaluated layer tree, alpha 규칙, color management,
  effect packet을 사용한다.
- `MotionPreviewWidget`은 persistent `QOpenGLWidget` presenter이며 preview와
  export가 `render_graph.py`의 evaluated layer tree와 premultiplied-alpha 규칙을
  공유한다.
- text/image/effect와 지원하지 않는 vector surface는 QImage 기반이다. 전체를
  shader-only compositor로 오인해 문서화하지 않으며 GPU 전환 중에도 동일한
  render graph 계약과 pixel parity 테스트를 유지한다.
- Vector geometry와 deterministic Bezier flattening은 Qt-free
  `vector_shapes.py`에 둔다. QPainterPath/Boolean/cache는
  `vector_tessellation.py`의 renderer 경계에 두며, UI가 별도 geometry
  구현을 만들지 않는다. `vector_gpu.py`는 이 최종 path를 GLU로 삼각분할해
  bounded mesh cache에 보관하고 `vector_gpu_renderer.py`는 raw OpenGL VAO/VBO로
  직접 그린다. 변환과 Repeater는 GPU uniform으로 평가하므로 같은 geometry의
  frame 갱신은 VBO를 재업로드하지 않는다.
- GPU vector packet은 `build_render_graph(..., include_vector_gpu=True)`를 호출한
  Preview에서만 생성한다. Export와 메인 합성은 패킷 생성 비용을 부담하지
  않는다. Radial gradient, effect, mask, matte, 비-vector layer가 섞이면 전체
  graph가 기존 QPainter 경로로 명시적으로 fallback한다.
- 다중 레이어 Boolean은 path 사본을 UI에 고정하지 않고 source의 안정적인
  `operand_layer_ids`를 저장한다. Qt-free `boolean_layers.py`가 각 operand의
  현재 local time, hierarchy world transform, anchor를 target local path로
  변환하며 preview/export와 Canvas가 같은 결과를 사용한다. 순환·누락·비-shape
  참조는 validation에서 차단한다.
- Typography selector, phase, stagger 계산은 Qt-free
  `typography_motion.py`에 두고 기존 `typo_animations.py` registry를
  재사용한다. 폰트 검색, variable axis, glyph path cache와 실제 painter
  배치는 Qt renderer 경계에 둔다. UI와 action은 모두 같은 source params를
  변경하며 별도 타이포 애니메이션 문서를 만들지 않는다.
- `typography_layout.py`는 Qt `QTextLayout`/`QGlyphRun`으로 문장 전체를 먼저
  셰이핑하고 glyph id, baseline, visual position, 원문 string index를 보존한다.
  Painter와 OpenGL atlas는 이 공통 결과를 사용하므로 Arabic 결합형과 mixed
  RTL/LTR text를 글자 단위 애니메이션 때문에 다시 고립형으로 분해하지 않는다.
- Text Inspector는 `text_path` 생성/해제와 normalized offset을 편집한다.
  `ui/canvas.py`는 선택된 text layer에 같은 Bezier path의 anchor/tangent와
  offset marker를 표시하고, 모든 drag를 document controller mutation으로
  돌려보낸다. Canvas만의 임시 path 상태는 두지 않는다.
- 기본 fill-only typography Preview는 `typography_gpu.py`의 bounded glyph
  atlas에 글리프를 한 번 래스터화하고 `typography_gpu_renderer.py`가 atlas
  texture와 글자별 transform/color/opacity uniform으로 그린다. atlas page
  revision이 같으면 texture를 다시 올리지 않는다. stroke, shadow, background,
  effect, mask, matte, 비지원 blend, atlas capacity 초과와 혼합 비-typography
  graph는 전체 Painter render graph로 명시적으로 fallback한다. Export는 계속
  공통 Painter 경로를 사용한다. GPU fragment shader도 로컬 text layer 크기로
  clip하여 고정 높이에서 줄바꿈이 넘칠 때 Preview와 Export 경계가 일치한다.
- 멀티모달 AI 요청·첨부·검토 제안은 Qt-free `ai_workspace.py`가 소유한다.
  `ui/ai_panel.py`는 텍스트/이미지 drag-and-drop과 검토 UI만 담당하고,
  실제 composition 변경은 같은 proposal을 사용하는 document controller 또는
  `motion.ai.apply` action을 거친다. AI 입력만으로 즉시 프로젝트를 수정하지 않는다.
- 마스크 경로와 feather/expansion/opacity 평가는 preview/export 공통
  `mask_adapter.py`에서 수행한다. point/planar 추적 샘플의 정렬·보간은 Qt-free
  `mask_tracking.py`가 소유하고, mask metadata의 `tracking_cache`만 renderer에
  전달한다. `tracking_provider.py`는 source video의 ROI를 Shi-Tomasi/LK optical
  flow와 forward-backward 검증으로 분석하고, planar 모드에서는 RANSAC partial
  affine을 누적해 같은 cache를 생성한다. 컷 전환은 낮은 신뢰도의 종료 sample로
  기록하고 잘못된 변환을 다음 shot으로 누적하지 않는다. UI는 전용 QThread에서
  provider를 실행하며 renderer는 프레임을 다시 추적하지 않는다.
- PPT animation 변환은 Qt-free `ppt_animation_bridge.py`가 소유한다.
  `AnimationSpec`의 유효 appear/fade/move/scale 효과를 하나의 Motion behavior로
  변환하며 start/duration, easing, trigger, click index와 원래 in/out slot을
  behavior metadata에 보존한다. `content_bridge.py`는 element 변환만 조정한다.
  반대 방향에서는 PPT 네이티브로 표현 가능한 단일 behavior만 복원하고 다중·비지원
  behavior, transform keyframe, native 범위 초과는 자동 삭제하지 않고 bake 경고로
  반환한다. PPTX writer는 entrance가 없는 out-only 효과도 timing XML에 기록한다.
- 오디오 FFT와 envelope 추출은 Qt-free `audio_analysis.py`가 소유한다. 분석 cache는
  source path/size/mtime/revision 서명을 가지며 amplitude, bass, mid, treble, onset과
  beat marker만 직렬화한다. `ui/audio_worker.py`가 이 작업을 background thread에서
  실행하고 evaluator와 renderer는 분석을 다시 실행하지 않는다.
- `audio_reactive.py`는 attack/release/smoothing/invert/clamp를 binding curve로
  선계산하고 composition time에서 transform에 적용한다. 따라서 OpenGL Preview,
  Painter export, 메인 영상 composite가 같은 값과 시각을 사용한다. Bake는 결과를
  일반 transform keyframe으로 바꾸고 runtime audio dependency를 제거한다.
- 구조화된 오디오 timing은 `composer_bridge.py`와 `voice_bridge.py`가 담당한다.
  Composer BPM/section/note event는 추정 beat보다 우선하며 Voice Lab의 sentence,
  word, phoneme event는 text reveal과 actor lip-sync cue가 같은 source ID를 참조한다.
  UI/MCP 연결은 각각 `ui/audio_panel.py`와
  `actions/editor_adapter_motion_audio.py`에 두며 기존 대형 adapter를 확장하지 않는다.
- AR/PBR의 직렬화·keyframe 평가는 Qt-free `ar_pbr_source.py`가 소유한다. 3D object,
  Camera, Light는 각각 Motion Layer이며 camera와 light는 render node를 만들지 않고
  같은 composition time에서 활성 3D source의 기존 AR/PBR track/settings로 평가된다.
- `adapters/ar_pbr.py`는 새 3D renderer를 만들지 않는다. 기존
  `full_model_view_gpu_export_service`에 투명 RGBA를 요청하고 결과를 premultiplied
  `QImage`로 바꿔 공통 render graph에 공급한다. cache key에는 asset stat/revision,
  source params, composition revision, time, quality, viewport가 포함된다.
- AR/PBR Auto Frame은 기본 켜짐이며 기존 model bounds 기반 OpenGL fit을 사용한다.
  Camera 회전은 현재 model-view 계약상 inverse object orbit로 대응하고, 조명 범위는
  단일 key light와 HDRI로 제한한다.
- depth group은 composition metadata와 각 3D layer의 stable group ID를 함께 저장한다.
  standalone 문서는 명시적 depth frame path를 사용하고, 메인 편집기에서는 video-depth
  composite bridge가 같은 occlusion helper에 depth를 공급한다.
- Live2D/Spine 공통 직렬화와 시간 평가는 Qt-free `actor_source.py`가 소유한다.
  `live2d_actor`와 `spine_actor`는 asset, playback, transform, opacity, catalog,
  parameter, Voice Lab lip-sync cue를 같은 schema에 저장한다.
- `adapters/live2d.py`는 기존 Cubism GPU clip을 감싸며 상태형 motion을 고정 FPS로
  reset/forward 평가한다. source stat/params/revision/time/viewport로 식별되는 canonical
  frame cache를 Preview와 Export가 공유해 같은 시점의 결과를 고정한다.
- `adapters/spine.py`는 기존 Spine actor clip을 감싸며 Motion Preview와 Export에서
  worker-safe CPU full renderer를 공통 사용한다. clip parse cache와 RGBA frame cache는
  제한 용량 LRU이며, 거의 빈 default skin은 actor renderer의 visual-bounds 비교로
  완전한 named skin에 복구된다.
- actor renderer는 공통 render graph에 premultiplied-alpha `QImage`를 공급한다.
  Actor Inspector와 `motion.live2d.add`, `motion.spine.add`, `motion.actor.update`,
  `motion.actor.lipsync.set`, `motion.actor.diagnostics` action은 같은 source params를 쓴다.
- MMD 직렬화와 시간 평가는 Qt-free `mmd_source.py`가 소유한다. model/motion,
  VMD camera 선택, bounds framing, toon light/shadow/bloom/material, IK/physics/GPU
  설정을 하나의 source params 계약으로 저장한다.
- `adapters/mmd.py`는 기존 `project_player_mmd_workflow`가 만드는 packet과
  `MMDOffscreenGLRenderer`를 재사용한다. 새 software MMD renderer는 두지 않으며,
  quality-neutral canonical RGBA cache로 같은 시점 Preview/Export parity를 고정한다.
- MMD Inspector와 `motion.mmd.add`, `motion.mmd.update`,
  `motion.mmd.motion.set`, `motion.mmd.diagnostics`는 같은 source 계약을 사용한다.
- VRM 상태와 시간 평가는 Qt-free `vrm_source.py`가 소유한다. VRM profile,
  explicit pose, source-exposure visibility policy, framing, MToon lighting과 cache
  quantization을 직렬화하며 UI나 방송 창을 import하지 않는다.
- `adapters/vrm.py`는 `internal_vrm_fallback.render_internal_vrm_fallback_frame()`과
  `vrm_mtoon_gpu`만 호출한다. bounded canonical RGBA cache가 같은 source/composition
  revision, viewport, quantized time의 Preview와 Export 결과를 공유한다.
- internal VRM fallback의 선택적 `motion_frame` 입력은 기존 CSV/idle 방송 호출을
  변경하지 않는다. direct pose가 있을 때만 head/upper-body animation curve와 face
  morph를 다시 만들고, 공통 alpha autofit이 bust-up/half/full-body와 bottom anchor를
  적용한다.
- VRM Inspector와 `motion.vrm.add`, `motion.vrm.update`, `motion.vrm.pose.set`,
  `motion.vrm.diagnostics`는 같은 source params 및 diagnostics를 사용한다.
- 구조화 표현식은 Qt-free `expressions.py`가 소유한다. operation tree만 허용하며
  Python/JavaScript 실행은 없다. dependency cycle과 operation/node/depth 제한을
  validation에서 차단하고, 최종 transform 결과를 일반 keyframe으로 bake할 수 있다.
- particle simulation은 Qt-free `particles.py` 한 곳에서 Preview, Export, action이
  공유한다. circle/square/triangle은 `particle_gpu.py`를 거쳐 기존 vector OpenGL
  renderer가 그린다. sprite는 현재 canonical premultiplied-alpha source surface이며
  GPU shape packet으로 오인하지 않고 diagnostics와 broadcast bake 요구에 표시한다.
- `templates.py`는 10종 built-in template, 지원 aspect variant, stable published
  control ID와 적용별 `template_instance_id`를 소유한다. UI와
  `motion.template.*` action은 같은 builder를 사용하고
  `tools/qa_motion_template_catalog.py`는 production export renderer로 실제 preview를
  생성한다.
- `broadcast_bridge.py`는 layer/type/particle/effect 비용으로 `realtime`, `cached`,
  `offline_only`를 계산한다. cached Program Output은 현재 composition revision,
  frame count, path, premultiplied alpha를 검증한 cache manifest가 필수다. live control
  변경은 revision을 올리고 stale cache를 제거한다.
- `ai_workspace.py`의 proposal은 Qt-free `ai_planner.py` 분석을 포함한다. 계획 단계에서
  생성 레이어, 누락 자산, renderer cost, bake/cache 요구와 projected validation을
  보여 주며 적용 전에는 composition을 변경하지 않는다.

### M12 declarative extension management

- `plugin_manifest.py`, `plugin_registry.py`, `template_pack.py`는 Qt-free다. 이 계층은
  plugin code를 import하지 않고 JSON manifest/descriptor와 Motion composition만 읽는다.
- plugin manifest v1은 id/version/vendor/API major, host capability, plugin dependency,
  contribution id, 안전한 상대 JSON descriptor를 로드 전에 검증한다. duplicate id는
  모두 무효 처리되며 활성 dependency를 먼저 끄는 변경도 차단한다.
- enable-state는 `%LOCALAPPDATA%/TigerCapture/MotionDesigner/plugin_state.json`에 원자적으로
  기록된다. `runtime_loaded=false`와 `restart_required=true`를 명시하므로 현재 구현이
  runtime plugin host인 것처럼 보이지 않는다.
- template-pack v1은 directory/manifest/ZIP을 지원한다. ZIP traversal, symbolic link,
  executable content, 크기/파일 수 초과를 차단하고 각 composition을
  `MotionComposition.from_dict()`와 `validate_composition()`으로 검증한 뒤에만 durable
  per-user storage에 staging/rename 방식으로 설치한다. `debugCapture`는 설치 위치로
  사용할 수 없다.
- `motion.plugin.list/inspect/validate/enable/disable`과
  `motion.template_pack.validate/install`은 editor owner 없이 Action/MCP에서 사용할 수
  있다. install은 `destructive` 및 `requires_review`이며 명시적 확인 없이는 실행되지
  않는다.
- source/effect/behavior/exporter contribution을 renderer에 실제 등록하는 runtime host,
  sandbox/failure isolation, uninstall/safe mode는 이 관리 기반 위에 추가할 M12 후속
  범위다.

## 6. 자산과 QA 경계

- 재생 가능한 기본 입력은 `qa_corpus/assets/qa_motion_720p.mp4`다.
- 제품 샘플과 사용자가 다시 필요로 하는 원본은 `sample_assets`, `qa_corpus`,
  또는 `external/assets`에 둔다.
- `debugCapture/motion_designer/baseline.json`은 재생성 가능한 보고서다.
- `debugCapture`의 파일을 source media, 모델, template 또는 프로젝트 기본값으로
  사용하지 않는다.

기준선 생성:

```powershell
.\.venv\Scripts\python.exe tools\qa_motion_baseline.py
.\.venv\Scripts\python.exe tools\qa_motion_tracking_provider.py
.\.venv\Scripts\python.exe tools\qa_motion_gpu_typography.py
.\.venv\Scripts\python.exe tools\qa_motion_audio_sync.py
.\.venv\Scripts\python.exe tools\qa_motion_ar_pbr.py
.\.venv\Scripts\python.exe tools\qa_motion_actors.py
.\.venv\Scripts\python.exe tools\qa_motion_mmd.py
.\.venv\Scripts\python.exe tools\qa_motion_vrm.py
.\.venv\Scripts\python.exe tools\qa_motion_gpu_particles.py
.\.venv\Scripts\python.exe tools\qa_motion_template_catalog.py
```

보고서는 다음을 기록한다.

- 현재 `.tgp` version과 save-load-save canonical round trip
- 내구성 QA 영상의 decoder backend, frame size, open/decode 시간
- OpenGL preview surface, startup prewarm, shared-context policy, GPU frame bridge
- 아직 `motion_compositions`가 저장되지 않는 M0 상태

## 7. 오류와 관측성

- adapter는 실패를 빈 프레임으로 숨기지 않고 diagnostics를 반환한다.
- renderer 준비 중에는 placeholder 또는 마지막 유효 frame을 유지한다.
- 캐시 키에는 source revision, composition revision, time, quality, viewport를
  포함한다.
- 성능 수치는 절대 합격 기준이 아니라 이전 보고서와 비교하는 회귀 기준이다.
- 지원하지 않는 출력은 자동 삭제하지 않고 bake, rasterize, unsupported로
  preflight에 표시한다.

## 8. 현재 구현 기준

- Qt-free core 계약을 import할 수 있다.
- `.tgp` save-load-save와 QA 영상 decode 기준선이 통과한다.
- 기존 OpenGL preview 구조 계약이 보고서에 기록된다.
- architecture guard가 `app/video_editor_window.py`와 Motion Designer core 경계를
  지킨다.
- durable input과 disposable output 경계가 자동 테스트된다.
- 기존 renderer를 사용하는 Live2D 3종과 Spine 3종이 비어 있지 않게 렌더되고,
  동일 시점 Preview/Export RGBA가 픽셀 단위로 일치한다.
- 실제 Actor Inspector UI capture가 dark-surface 검사와 함께 재생성된다.
- 실제 PMX/PMD/VMD 3종이 기존 MMD OpenGL renderer에서 렌더되고, 동일 시점
  Preview/Export RGBA가 픽셀 단위로 일치하며 MMD Inspector 증거가 재생성된다.
- durable Milica VRM0의 full-body 및 bust-up 포즈가 `vrm_mtoon_gpu`에서 렌더되고,
  눈깜박임/입/고개 변화, alpha visibility, bottom anchoring, 실제 dark VRM Inspector,
  동일 시점 Preview/Export RGBA 픽셀 일치가 재생성된다. 비캐시 render time과 cache
  hit time은 별도 보고하며 realtime claim을 만들지 않는다.
- deterministic GPU shape-particle QA와 10종 template production-render catalog가
  재생성되며 M10 expression/template/broadcast/AI 계약이 action/UI 테스트를 통과한다.
- M11 출력 계약은 명시적 SDR sRGB다. 새 composition은 `linear-srgb` 최종 합성과
  straight-alpha 파일 경계/premultiplied-alpha 내부 경계를 사용하고, 구버전 문서는
  외형 보존을 위해 display-sRGB legacy 모드로 읽는다. HDR, tone mapping, OCIO, project
  LUT는 Preview/Export parity가 없으면 preflight에서 차단한다.
- 표준 출력은 H.264/H.265, ProRes 4444 alpha, PNG RGBA/OpenEXR scene-linear sequence,
  PNG/JPEG/WebP still이다. PNG sequence만 유효 프레임 단위 resume을 지원하고 비디오
  취소는 `.partial` 제거 후 전체 retry를 사용한다. Lottie/SVG/OTIO/glTF는 문서화된
  제한 subset이며 손실 가능 상태를 bake 또는 block으로 판정한다.
- 프로젝트 relink는 기존 root 상대 경로와 유일 basename 후보만 사용하며 중복 후보를
  자동 선택하지 않는다. recovery는 원자적 replace, SHA-256 checksum, composition ID와
  revision 검증을 사용한다. UI autosave와 Action/MCP는 같은 recovery 계약을 호출한다.
- 제품 승인 집계는 30분 실제 OpenGL 번인, 1,000 layer, 10,000 keyframe, 500회
  edit/undo/redo와 recovery, export cancel/resume/retry, GPU context recreation,
  moved-project relink, 현재 소스의 Inno 설치본 smoke를 모두 실제 artifact로 요구한다.
- 2026-07-22 기준 실제 30분 OpenGL 번인은 `motion_vector_gpu`, 80,723 frame swap,
  평균 44.84 FPS, GL error 0, software renderer 0, 메모리 증가 8,896,512 bytes로
  통과했다. 최신 소스 Inno 설치본의 설치/실행/제거 smoke와 Motion 테스트 41개 파일
  215개도 통과했고 release evidence 누락은 0개다.

이 경계 위에 `schema.py`, evaluator, validation, composition service,
`motion_compositions[]`/`motion_clips[]` 저장, UI, action, main preview와 export
합성이 구현되어 있다. 구현 상세와 남은 항목은 마일스톤 문서를 기준으로 한다.
