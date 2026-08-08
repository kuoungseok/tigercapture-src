# Tiger Studio Motion Designer 제품 기획서

작성일: 2026-07-21  
상태: 제품 설계 초안  
대상 제품: Tiger Studio  

구체적인 구현 순서와 완료 판정은
`docs/MOTION_DESIGNER_MILESTONES_KO.md`를 따른다.

프롬프트와 여러 참조 이미지에서 편집 가능한 Motion Composition을 생성하는 AI
확장 기획은 `docs/MOTION_AI_GENERATION_PRODUCT_PLAN_KO.md`를 따른다.
이미지 내부를 의미 레이어로 분해하고 각 레이어를 개별 연출하는 상세 계획은
`docs/MOTION_AI_LAYERED_IMAGE_PRODUCT_PLAN_KO.md`를 따른다.

## 1. 한 줄 정의

Tiger Studio Motion Designer는 영상, 타이포그래피, 도형, 이펙트,
AR/PBR 3D, Live2D, Spine, MMD, VRM, 음성, 음악을 하나의 시간 기반
컴포지션에서 움직이게 만들고, 그 결과를 메인 영상 타임라인과 PPT Maker,
방송 출력에서 다시 사용할 수 있는 GPU 기반 모션 그래픽 제작 도구다.

## 2. 제품 결정

### 2.1 별도 창으로 만든다

Motion Designer는 메인 영상 편집기의 작은 패널로 만들지 않는다.

- PPT Maker처럼 독립된 제작 창으로 연다.
- 메인 에디터의 Media Pool, Timeline, Typography, Actor 자산을 드래그해
  가져온다.
- 완성된 컴포지션은 메인 타임라인에 `Motion Clip`으로 배치한다.
- Motion Clip을 더블클릭하면 해당 컴포지션이 Motion Designer에서 열린다.
- `app/video_editor_window.py`에는 기능을 추가하지 않는다.

별도 창이 필요한 이유는 레이어 목록, 캔버스, 인스펙터, 도프 시트, 그래프
에디터를 동시에 보여줘야 하기 때문이다. 메인 편집기 안에 넣으면 영상 편집과
모션 제작 양쪽의 작업 공간이 모두 좁아진다.

### 2.2 별도 전용 파일을 주 포맷으로 만들지 않는다

편집 원본은 기존 Tiger Studio 프로젝트 `.tgp` 안에 저장한다. 다음은 현재
프로젝트 스키마가 아니라 Motion Designer 도입 후의 목표 구조다.

```text
TigerProject
  media_pool[]
  timelines[]
  motion_compositions[]
  shared_assets[]
```

- 새 `.tgmotion` 파일을 필수 원본 포맷으로 만들지 않는다.
- 컴포지션 복사와 외부 전달이 필요하면 나중에 선택적 패키지 내보내기를
  제공할 수 있지만, 제품의 기본 저장 단위는 `.tgp`다.
- PPT Maker의 편집 원본은 기존처럼 `.tgppt`로 유지하고 Motion Composition의
  poster/video derivative와 source metadata를 브리지로 전달한다.
- 표준 출력은 투명 영상, 이미지 시퀀스, Lottie/SVG 제한 변환, 3D 교환
  포맷으로 제공한다.

### 2.3 기존 OpenGL 렌더러를 기준으로 한다

- 제품 프리뷰와 최종 모션 렌더의 기준은 메인 에디터의 OpenGL 경로다.
- CPU는 프로젝트 해석, 키프레임 평가, 경로 계산, 오디오 분석에 사용한다.
- 제품 품질의 3D/이펙트 결과를 소프트웨어 렌더러로 대체하지 않는다.
- 백그라운드 내보내기는 지속형 OpenGL worker/context를 사용한다.
- 프리뷰와 내보내기가 서로 다른 효과 구현을 갖지 않도록 같은 평가 결과와
  셰이더 파라미터 패킷을 공유한다.

## 3. 제품 포지션

Motion Designer는 After Effects 전체를 복제하는 도구가 아니다. Tiger Studio가
이미 잘 다루는 미디어와 캐릭터를 빠르게 움직여 영상, 발표, 방송에 다시 넣는
도구다.

### 핵심 경쟁력

1. 영상 편집 타임라인과 모션 컴포지션이 같은 프로젝트에 있다.
2. AR/PBR 3D와 서브컬쳐 캐릭터 자산을 별도 변환 작업 없이 가져온다.
3. Voice Lab과 Composer 결과를 모션 타이밍과 바로 연결한다.
4. 완성된 모션을 영상, PPT, 방송 장면에서 재사용한다.
5. 모든 주요 편집 기능을 Python Action/MCP로 조작할 수 있다.

### 하지 않을 주장

- After Effects/Fusion 전체 대체
- 모든 AE 플러그인 또는 `.mogrt` 완전 호환
- 모든 Unity/게임 추출 Live2D/Spine 자산 완전 호환
- 모든 캐릭터 렌더러의 무캐시 실시간 재생
- 일반적인 3D DCC 또는 오프라인 렌더러 완전 대체

## 4. 목표 사용자

### 서브컬쳐 영상 제작자

- 캐릭터 인트로, 뮤직비디오 타이틀, 가사 모션, 방송 오버레이 제작
- MMD/Live2D/Spine/VRM과 영상·음악을 한 장면에 결합

### 영상 편집자

- 로고 리빌, 하단 자막, 콜아웃, 전환 스팅어, 제품 설명 그래픽 제작
- Motion Clip을 메인 타임라인에서 길이 조절하고 반복 사용

### 발표·교육 콘텐츠 제작자

- PPT Maker의 요소를 시간 기반 장면으로 확장
- 3D 제품 설명, 캐릭터 발표, 데이터 애니메이션을 MP4 또는 PPT에 삽입

### AI 자동화 사용자

- 자연어로 장면을 만들고 액션 계획을 검토한 뒤 적용
- 레이어, 키프레임, 카메라, 효과, 음악 큐를 구조화된 액션으로 수정

## 5. 대표 사용자 시나리오

### A. 영상 위에 모션 타이틀 만들기

1. 메인 타임라인에서 영상 구간을 선택한다.
2. `Create Motion Composition From Selection`을 실행한다.
3. 영상은 참조 배경 레이어로, 선택 구간 길이는 컴포지션 길이로 들어온다.
4. Typography 프리셋을 드래그하고 위치·크기·회전·불투명도 키를 찍는다.
5. 모션 블러와 글로우를 조절한다.
6. 저장하면 메인 타임라인에 Motion Clip이 생성된다.

### B. 3D 제품 리빌 만들기

1. Media Pool의 GLB/GLTF/FBX 자산을 캔버스로 드래그한다.
2. AR/PBR 조명, HDRI, 그림자, SSAO, clearcoat를 설정한다.
3. 카메라와 제품 회전에 키프레임을 준다.
4. 텍스트와 라이트 스윕을 추가한다.
5. 투명 ProRes 4444 또는 PNG/EXR 시퀀스로 내보낸다.

### C. 캐릭터 방송 스팅어 만들기

1. Live2D, Spine, MMD 또는 VRM 배우를 추가한다.
2. 캐릭터 모션과 표정 구간을 선택한다.
3. Composer의 짧은 음악 큐와 Sound Editor의 효과음을 넣는다.
4. 카메라 펀치인, 파티클, 타이포그래피를 비트에 맞춘다.
5. Broadcast Scene의 장면 전환 소스로 등록한다.

### D. 음성 기반 설명 모션 만들기

1. Voice Lab에서 TTS와 자막을 생성한다.
2. 문장·단어 타이밍을 Motion Designer로 가져온다.
3. 텍스트가 발화 타이밍에 맞춰 나타나고 캐릭터 립싱크가 적용된다.
4. 음량 또는 주파수 대역을 도형 크기, 글로우, 파형에 연결한다.

### E. AI로 초안 만들기

1. 사용자가 “8초짜리 사이버풍 캐릭터 소개, 이름은 왼쪽 아래, 3초에
   카메라 줌”이라고 요청한다.
2. AI는 사용할 자산, 레이어, 타이밍, 효과, 출력 요구를 계획으로 반환한다.
3. 사용자가 계획을 승인하면 액션 트랜잭션으로 적용한다.
4. 사용자는 캔버스와 그래프 에디터에서 직접 다듬는다.

## 6. 화면 구성

```text
┌────────────────────────────────────────────────────────────────────┐
│ Project  Undo/Redo | Select Text Shape Pen Mask | Camera Light | ▶ │
├───────────────┬──────────────────────────────────┬─────────────────┤
│ Assets        │                                  │ Inspector       │
│ Layers        │             Canvas               │ Transform       │
│ Templates     │        Safe area / guides        │ Appearance      │
│ Behaviors     │     Motion path / gizmos         │ Effects         │
│ Effects       │                                  │ Source          │
├───────────────┴──────────────────────────────────┴─────────────────┤
│ Layer timeline / Dope Sheet / Graph Editor / Audio waveform       │
└────────────────────────────────────────────────────────────────────┘
```

### 6.1 상단 도구줄

- 선택, 손 이동, 확대/축소
- 텍스트, 도형, 펜 경로, 마스크
- 2D/3D 전환, 카메라, 라이트
- 스냅, 가이드, 안전 영역
- 이전/다음 키프레임, 키프레임 추가
- 재생, 반복, 프리뷰 해상도, 캐시 상태
- Motion Clip 저장, 메인 타임라인 배치, 내보내기

텍스트가 들어간 큰 도구 버튼 대신 아이콘과 툴팁을 사용한다. 모드 선택은
세그먼트 컨트롤, 수치 설정은 슬라이더/스테퍼, 표시 여부는 토글을 사용한다.

### 6.2 왼쪽 영역

- `Assets`: 프로젝트 Media Pool과 현재 컴포지션 자산
- `Layers`: 부모/자식 계층, 잠금, 가시성, solo, 2D/3D, blend 상태
- `Templates`: 타이틀, 하단 자막, 로고, 스팅어, 캐릭터, 제품 리빌
- `Behaviors`: follow, spring, wiggle, look-at, path, audio-reactive
- `Effects`: 기존 효과/색보정/마스크/노드 프리셋 검색

### 6.3 캔버스

- 출력 화면 비율을 정확히 표시한다.
- 객체 선택 시에만 변형 기즈모와 모션 경로가 나타난다.
- 빈 공간을 누르면 선택과 기즈모가 해제된다.
- 2D 객체는 바운딩 박스, 3D 객체는 이동/회전/스케일 기즈모를 사용한다.
- 카메라 프레임, 타이틀/액션 안전 영역, 그리드, 가이드를 표시한다.
- 실제 합성 순서와 alpha를 프리뷰한다.

### 6.4 오른쪽 인스펙터

선택 레이어의 종류에 따라 다음 섹션만 표시한다.

- Source
- Transform
- Anchor/Pivot
- Crop/Corner
- Appearance/Material
- Mask
- Effects
- Animation
- Behaviors/Constraints
- Audio response
- Render/cache policy

애니메이션 가능한 각 속성 옆에는 다이아몬드 키 버튼을 둔다. 값이 현재
시간에 키를 갖는지, 다른 시간에 키가 있는지 색과 채움으로 구분한다.

### 6.5 하단 타임라인

보기 모드는 세 가지다.

1. `Layers`: 레이어 바, trim, in/out, marker, audio waveform
2. `Dope Sheet`: 속성별 키프레임 배치와 다중 선택
3. `Graph`: 값/속도 곡선과 Bezier 핸들

기본 조작:

- 휠: 시간축 확대/축소
- 가운데 버튼 또는 빈 영역 드래그: 패닝
- Shift: 다중 선택 보조에만 사용
- Alt+드래그: 키 복제
- 키 드래그: 시간 이동
- 영역 드래그: 키 다중 선택
- 그래프 핸들: ease와 overshoot 직접 조절

## 7. 컴포지션 데이터 모델

PPT의 `DeckSpec/SlideElement/AnimationSpec`은 좋은 출발점이지만,
Motion Designer의 source of truth로 직접 확장하지 않는다. PPT는 문서 객체,
Motion Designer는 시간에 따라 모든 속성이 변하는 레이어 컴포지션이기 때문이다.

### 7.1 MotionComposition

```text
MotionComposition
  id
  name
  width
  height
  fps
  duration_ms
  background_rgba
  color_space
  layers[]
  markers[]
  audio_refs[]
  camera_layer_id
  render_settings
  cache_revision
  metadata
```

### 7.2 MotionLayer

```text
MotionLayer
  id
  name
  kind
  parent_id
  start_ms
  end_ms
  source_in_ms
  time_scale
  z_index
  visible
  locked
  solo
  blend_mode
  matte_source_id
  transform
  properties{}
  animated_properties{}
  masks[]
  effects[]
  behaviors[]
  source_ref
  render_policy
  metadata
```

### 7.3 레이어 종류

P0:

- `video`, `image`, `text`, `shape`, `line`, `group`, `null`
- `adjustment`, `audio`, `mask`, `camera`, `light`

P1:

- `ar_pbr`, `live2d`, `spine`, `mmd`, `vrm`
- `ppt_element`, `timeline_reference`, `particle`, `paint`

### 7.4 AnimatedProperty와 Keyframe

```text
AnimatedProperty
  type
  base_value
  keyframes[]
  expression_or_behavior_ref

Keyframe
  id
  time_ms
  value
  interpolation       # hold, linear, bezier
  in_tangent
  out_tangent
  temporal_ease
  spatial_tangent
```

초기 키프레임 대상:

- position, anchor, scale, rotation, opacity
- crop, corner radius, fill, stroke
- mask path/feather/opacity/expansion
- effect parameters
- camera position/target/FOV/focus
- light transform/color/intensity/cone
- text reveal and per-glyph animation parameters
- actor transform, motion/expression selection and blend weight
- audio gain/pan and analysis-driven control value

### 7.5 평가 순서

프레임 평가는 항상 다음 순서를 따른다.

1. 레이어 로컬 시간과 time remap 계산
2. 기본 속성 로드
3. 키프레임 보간
4. behavior 계산
5. constraint와 parent transform 계산
6. source frame/actor pose 계산
7. mask와 matte 계산
8. layer effect와 node effect 계산
9. blend와 depth group 합성
10. global post effect와 color management

같은 입력 시간과 프로젝트 상태는 항상 같은 결과를 내야 AI 액션, undo,
캐시, 프리뷰/내보내기 비교가 가능하다.

## 8. 기존 Tiger Studio 자산 활용 계획

| 기존 자산 | 현재 강점 | Motion Designer에서의 사용 | 필요한 보완 |
| --- | --- | --- | --- |
| 메인 NLE 타임라인 | clip/track, trim, marker, transition, audio lane | 구간 참조, Motion Clip 배치, 길이/반복 | 컴포지션 clip schema와 live-link |
| PPT Maker | 독립 창, 캔버스, 객체, 타임라인, 기본 animation, MP4/PPTX | UI 패턴, shape/text, drag payload, animation seed | 범용 property keyframe과 Bezier core 분리 |
| Typography | TextStyle, IN/HOLD/OUT, per-glyph transform, 프리셋 | kinetic text와 가사 모션 | 공통 keyframe/curve와 GPU glyph cache 연결 |
| Preset/Asset packs | effect/title/transition/sticker/motion/template catalog | 모션 템플릿과 behavior/effect 검색 | 실제 animated thumbnail과 호환성 태그 |
| Video filters | sharpen, vignette, chroma, denoise 등 | 레이어 효과 | GPU 경로와 parameter animation 통일 |
| Color/Node graph | grade, curves, LUT, glow, masks, 노드 액션 | adjustment layer와 effect graph | Fusion급 범용 그래프로 과장하지 않고 GPU 노드 확대 |
| Mask/Tracking | power window, bitmap, qualifier, tracking correction | animated mask와 track-to-layer | path keyframe, feather GPU parity |
| Screen Studio polish | zoom actor, easing, motion blur 개념 | camera/viewport behavior preset | 일반화된 property curve로 변환 |
| AR/PBR | GLTF/GLB/FBX import, OpenGL PBR, HDRI, SSAO, shadow, depth | 3D 제품/배경/카메라/라이트 레이어 | persistent FBO와 preview/export parity 강화 |
| MMD | PMX/PMD/PBX, VMD, toon, 물리, 조명 | 캐릭터 모션 레이어 | 캐시와 재질/물리 호환성 gate 유지 |
| Live2D | actor track, performance source, motion storyboard | 대화/방송 캐릭터 레이어 | alpha frame adapter와 lip-sync timeline |
| Spine | JSON/SKEL/atlas, GL preview, animation/skin | 게임 캐릭터 레이어 | 지원 corpus 기준 호환성 표시와 cache |
| VRM/VTuber | MToon GPU, source framing, pose mapping, 방송 출력 | presenter/avatar 레이어 | 현재 first-frame/pose render 비용 때문에 선캐시 우선 |
| Sound Editor | waveform, effects, mixer, stem separation | 모션 audio lane과 analysis source | beat/onset/envelope cache |
| Composer | 구조화된 BPM/section/note, MIDI, stem render | beat grid, section marker, 자동 큐 | beat event를 motion marker로 노출 |
| Voice Lab/TTS | 음성, 자막, actor lip-sync | 대사 타이밍, word reveal, mouth cue | phoneme/word timing adapter |
| Broadcast Scene | Program Output와 scene payload | stinger, lower-third, live overlay | 실시간-safe 템플릿 등급과 preflight |
| Action/MCP | undoable action registry, dry-run, AI 계획 | 전체 모션 제작 자동화 | 전용 `motion.*` namespace |
| Render Queue | 작업 큐와 실패 진단 | alpha/sequence/video batch export | persistent GL worker job type |
| Review/QA 자동화 | 실제 UI/렌더 evidence와 report | 템플릿, parity, performance gate | Motion Designer 전용 golden scene |

`모두 활용`은 모든 기능을 한 프레임에 억지로 결합한다는 뜻이 아니다. 각 자산을
공통 레이어 계약으로 연결하고, 사용자가 필요한 것만 컴포지션에 넣는다는 뜻이다.

### 8.1 현재 강점과 실제 빈칸

Tiger Studio의 강점은 source breadth다. 영상, PPT, 3D, 여러 캐릭터 포맷,
음성, 음악, 방송 자산을 이미 가지고 있다. 반면 Motion Designer에 필요한
authoring depth는 아직 분산되어 있다.

- PPT animation은 appear/fade/move/scale 중심이다.
- Typography는 IN/HOLD/OUT 프리셋과 per-glyph 개념은 있지만 범용 property
  keyframe/curve의 source of truth가 아니다.
- Node graph와 clip effect는 존재하지만 범용 GPU compositor graph는 아니다.
- AR/PBR와 actor renderer는 강하지만 하나의 공통 layer/FBO/cache 계약으로
  묶이지 않았다.
- Timeline은 편집에는 강하지만 layer hierarchy, dope sheet, graph editor를
  제공하지 않는다.

따라서 다음 투자는 새 캐릭터 포맷이나 셰이더 수를 늘리는 것보다 공통 제작
기반을 만드는 데 우선한다.

### 8.2 P0 제품 기반 보강

1. **범용 속성 애니메이션 코어**
   - transform뿐 아니라 색, mask, effect, camera, light, actor parameter를
     같은 AnimatedProperty/Keyframe/Bezier 구조로 평가한다.
2. **전문 2D OpenGL compositor**
   - premultiplied alpha, layer FBO, matte, adjustment layer, blend mode,
     animated effect parameter를 제공한다.
3. **Layer hierarchy와 Graph Editor**
   - parent/null, anchor, motion path, dope sheet, value/speed graph를 제공한다.
4. **Motion Clip과 revision cache**
   - live-link, proxy/pre-render, cache invalidation, persistent worker를 제공한다.
5. **프로젝트 안전성**
   - migration, undo transaction, autosave/recovery, missing media relink를
     제품 완료 조건으로 둔다.

이 다섯 항목은 M0-M5의 release-blocking 범위다.

### 8.3 P1 창작 경쟁력 보강

1. **Vector Shape Engine**
   - Pen path, Bezier point, Boolean operation, Trim Path, Repeater,
     dashed stroke, animated gradient가 필요하다.
2. **고급 Typography**
   - character/word/line selector, stagger, text-on-path, variable font,
     CJK shaping/fallback, GPU glyph cache가 필요하다.
3. **Mask/Matte/Tracking**
   - alpha/luma matte, animated mask path, point/planar tracking,
     track-to-layer/camera/mask 연결이 필요하다.
4. **Behavior와 경량 표현식**
   - spring, wiggle, follow, look-at, loop, delay, stagger를 구조화된 node로
     제공하고 안전한 property-link/math expression subset을 추가한다.
5. **GPU Particle**
   - emitter, lifetime, velocity, gravity, turbulence, sprite, color/size over
     life를 제공한다.
6. **Audio Reactive**
   - beat/onset/amplitude/frequency와 Composer/Voice Lab의 구조화 타이밍을
     property에 연결한다.
7. **Template Published Controls**
   - text/media/color/duration/intensity/actor 교체 파라미터와 animated preview를
     제공한다.

### 8.4 P2 제품 확장 보강

1. **표준 출력 검증 계층**
   - ProRes 4444, PNG/OpenEXR sequence, Lottie/SVG subset, glTF/GLB subscene,
     OTIO reference를 preflight와 함께 제공한다.
2. **명시적 Color Management**
   - sRGB/linear, SDR/HDR, alpha/gamma 변환을 하나의 계약으로 만들고,
     필요하면 OpenColorIO 또는 동등한 검증된 backend를 도입한다.
3. **Plugin/Template SDK**
   - 외부 source adapter, effect, behavior, exporter, template pack을 본체 수정
     없이 등록한다. 이는 Motion Designer 1.0 이후 생태계 단계다.

### 8.5 보강 항목과 마일스톤 연결

| 보강 항목 | 담당 마일스톤 |
| --- | --- |
| schema, migration, undo, recovery | M0-M1, M3 |
| property keyframe, Bezier, behavior | M2 |
| layer UI, dope sheet, graph editor | M3 |
| OpenGL compositor, alpha, matte, blend | M4 |
| Motion Clip, proxy/cache, main export | M5 |
| vector, advanced type, mask/tracking, GPU effect | M6 |
| audio reactive, Composer, Voice Lab timing | M7 |
| AR/PBR camera/light/material animation | M8 |
| Live2D/Spine, MMD, VRM adapters | M9A-M9C |
| lightweight expression, particle, published template controls | M10 |
| color management, standard output, long-run QA | M11 |
| plugin/template SDK | M12 |

## 9. 렌더 구조

### 9.1 공통 source adapter

각 레이어 소스는 다음 계약 중 하나를 구현한다.

```text
evaluate(time, quality, viewport) -> SourceFrame

SourceFrame
  rgba_texture_or_frame
  optional_depth
  bounds
  premultiplied_alpha
  color_space
  cache_key
  diagnostics
```

어댑터 예시:

- `VideoSourceAdapter`
- `TypographySourceAdapter`
- `PptElementSourceAdapter`
- `ArPbrSourceAdapter`
- `Live2DSourceAdapter`
- `SpineSourceAdapter`
- `MmdSourceAdapter`
- `VrmSourceAdapter`

### 9.2 2D 합성

- premultiplied alpha를 내부 표준으로 사용한다.
- normal, add, screen, multiply, overlay 등 검증된 blend mode부터 제공한다.
- mask/matte/effect는 중간 FBO를 사용한다.
- motion blur는 변형 샘플 또는 velocity 기반으로 구현하고 프리뷰 품질에 따라
  sample 수를 낮출 수 있다.

### 9.3 3D와 캐릭터

- AR/PBR는 가능하면 같은 OpenGL graph에서 직접 합성한다.
- MMD/VRM/Live2D/Spine은 초기에는 alpha/depth SourceFrame으로 연결한다.
- 서로 다른 렌더러 사이의 완전한 3D depth 교차는 후속 단계다.
- expensive actor는 pose/frame cache를 사용하고 캐시 준비 상태를 UI에 표시한다.
- 캐시 미완료를 검은 화면이나 멈춘 UI로 보이지 않게 저해상도 프리뷰 또는
  명시적 준비 상태를 보여준다.

### 9.4 프리뷰 품질

- `Full`, `Half`, `Quarter`, `Auto` 해상도
- motion blur/SSAO/bloom sample quality 분리
- 선택 레이어만 solo preview
- 캐시 범위 지정과 background cache
- 재생 중에는 품질을 낮출 수 있지만 정지 시 full-quality frame으로 복구

### 9.5 프리뷰/내보내기 단일 계약

프리뷰와 최종 렌더는 같은 다음 데이터를 사용한다.

- evaluated layer tree
- effect/node parameter packet
- color management
- alpha convention
- camera/light state
- source asset revision

내보내기 전용 별도 효과 구현은 만들지 않는다. 품질 차이는 해상도와 sample 수만
허용한다.

### 9.6 Color Management 계약

- layer/source의 입력 color space를 명시한다.
- texture upload 전에 sRGB/linear 규칙을 통일한다.
- blend와 glow/bloom은 linear 공간에서 처리한다.
- preview display transform과 export output transform을 분리한다.
- SDR/HDR 변환과 premultiplied alpha 적용 순서를 고정한다.
- OpenEXR는 scene-linear intermediate로 취급한다.
- 외부 color-management backend는 선택 사항이지만, backend가 없어도 지원
  범위와 변환 경로를 report할 수 있어야 한다.

## 10. 모션 기능

### 10.1 기본 키프레임

- 모든 주요 수치/색/벡터 속성에 키프레임
- hold, linear, Bezier
- auto ease, ease in, ease out, ease both
- copy/paste, reverse, stagger, distribute
- 여러 속성의 시간/값 스케일
- 키프레임 velocity graph

### 10.2 경로와 부모 관계

- canvas motion path 편집
- path orient
- parent/child
- null/controller
- 2D/3D look-at
- align/distribute
- anchor/pivot 직접 이동

### 10.3 Behavior

Behavior는 키프레임을 파괴하지 않는 procedural layer다.

- fade/slide/scale/pop
- follow path
- spring/overshoot
- wiggle/noise
- orbit/rotate
- look-at/follow target
- type-on/per-word/per-glyph reveal
- audio amplitude/band response
- beat pulse
- loop/ping-pong/offset loop
- auto orient and camera focus

behavior 결과를 키프레임으로 bake할 수 있어야 한다.

### 10.4 템플릿 파라미터 공개

템플릿 제작자는 사용자가 바꿀 속성만 공개한다.

- text content/font/color
- logo/image/video replacement
- accent palette
- duration and timing scale
- animation intensity
- character/model replacement
- music/effect toggle

이 개념은 `.mogrt`의 장점을 참고하지만 Adobe 포맷을 내부 기반으로 사용하지 않는다.

### 10.5 Vector Shape Engine

- Pen/Bezier path 생성과 직접 점 편집
- rectangle, ellipse, polygon, star primitive
- union, subtract, intersect, exclude Boolean operation
- fill, stroke, dash, cap, join, gradient
- Trim Path와 Repeater
- path, point, gradient stop, trim, repeater parameter keyframe
- authoring path를 GPU tessellation/cache 결과와 분리

### 10.6 고급 Typography

- character, word, line selector
- stagger와 random order
- text-on-path
- per-glyph transform/color/opacity
- variable font axis와 font fallback
- 한글/CJK shaping 결과를 glyph index/position으로 안정적으로 cache

### 10.7 경량 표현식과 GPU Particle

첫 표현식 버전은 임의 코드 실행기가 아니다. property link, clamp, remap,
add/multiply, time, index, audio channel처럼 검증 가능한 node/expression subset만
제공한다.

Particle V1은 2D/2.5D GPU emitter다.

- point/box/circle/path emitter
- birth rate, burst, lifetime, velocity, gravity, turbulence
- sprite/shape particle
- color/size/opacity over life
- depth sort와 blend mode
- deterministic seed와 preview/export parity

## 11. 오디오와 음악 연동

### 기본 기능

- 컴포지션 audio lane과 waveform
- 메인 타임라인 오디오를 reference 또는 copy로 가져오기
- frame-accurate playback clock
- beat, onset, amplitude envelope, frequency band cache
- marker 자동 생성

### Audio Reactive

분석 채널을 임의 속성에 연결한다.

```text
input: amplitude | bass | mid | treble | beat | onset
mapping: min/max, smoothing, attack, release, invert
target: scale | rotation | opacity | color | glow | effect parameter
```

Composer의 BPM/section/note 데이터가 있으면 waveform 추측보다 구조화된 이벤트를
우선한다. Voice Lab 데이터가 있으면 문장, 단어, phoneme cue를 텍스트와 actor
lip-sync에 사용한다.

## 12. 메인 에디터 연결

### 12.1 진입점

- Workbench/Create 영역에 `Motion Designer` 진입 버튼
- Media Pool 또는 타임라인 우클릭: `Create Motion Composition`
- Motion Clip 더블클릭: 편집
- Command Palette: Motion Designer 열기/선택 구간에서 만들기

### 12.2 Motion Clip

```text
MotionClip
  id
  composition_id
  timeline_in_ms
  source_in_ms
  source_out_ms
  speed
  loop_mode
  opacity
  blend_mode
  transform
  cache_state
  poster_path
```

- 타임라인에서 trim, move, duplicate, split할 수 있다.
- 기본은 live composition 참조다.
- 무거운 컴포지션은 proxy/pre-render cache를 사용한다.
- 원본 컴포지션 수정 시 cache revision을 올려 자동 무효화한다.

### 12.3 PPT Maker 연결

- Motion Composition을 PPT의 `video_actor`로 드래그한다.
- 단순 text/shape/image/keyframe만 사용한 컴포지션은 향후 native PPT animation
  제한 변환을 시도할 수 있다.
- 캐릭터, 3D, 복잡한 효과는 poster + MP4 또는 alpha media로 삽입한다.
- PPT Maker의 단순 `AnimationSpec`은 유지하되, Motion Designer가 이를 공통
  keyframe core로 변환해 가져올 수 있게 한다.

### 12.4 Broadcast 연결

- 방송 안전 템플릿은 실시간 비용 등급을 가진다.
- `realtime`, `cached`, `offline_only`로 구분한다.
- stinger는 사전 렌더 alpha video를 기본으로 한다.
- lower-third처럼 가벼운 템플릿만 live parameter update를 허용한다.

## 13. 템플릿 전략

### 기본 팩

- Clean Lower Third
- Character Nameplate
- Subtitle Highlight
- Logo Reveal
- Product Callout
- Before/After Split
- Stream Stinger
- Music Beat Title
- Vertical Shorts Hook
- Chapter Opener

### 서브컬쳐 팩

- Anime Character Intro
- MMD Dance Title
- Live2D Dialogue Card
- Spine Game Skill Cut-in
- VRM Stream Starting/Ending
- Lyrics/Karaoke Motion
- Gacha/Result Reveal

### 3D 팩

- Turntable Product Reveal
- Exploded Detail Callout
- HDRI Studio Showcase
- Depth Occlusion Demo
- Metallic/Clearcoat Beauty Shot

### 템플릿 품질 규칙

- 썸네일은 정지 합성 이미지가 아니라 실제 짧은 animated preview다.
- 필요한 렌더러와 예상 비용을 표시한다.
- 누락 자산이 있어도 빈 화면이 아니라 교체 가능한 placeholder를 표시한다.
- 템플릿 기본 결과가 조정 없이도 사용할 수 있어야 한다.
- 16:9, 9:16, 1:1 safe layout variant를 제공한다.

## 14. AI와 Action/MCP

### 14.1 원칙

- UI와 AI가 같은 command/service를 사용한다.
- 모든 mutation은 undo transaction에 들어간다.
- `dry_run`은 실제 변경 없이 대상, 예상 결과, 비용과 경고를 반환한다.
- index 대신 안정적인 composition/layer/keyframe id를 사용한다.
- AI는 렌더러 내부 필드를 직접 변경하지 않는다.

### 14.2 제안 액션

프로젝트/컴포지션:

- `motion.editor.open`
- `motion.composition.list`
- `motion.composition.create`
- `motion.composition.create_from_timeline`
- `motion.composition.update`
- `motion.composition.duplicate`
- `motion.composition.delete`
- `motion.composition.validate`

레이어:

- `motion.layer.list`
- `motion.layer.add`
- `motion.layer.update`
- `motion.layer.delete`
- `motion.layer.duplicate`
- `motion.layer.reorder`
- `motion.layer.parent`
- `motion.layer.group`
- `motion.layer.set_source`

키프레임/곡선:

- `motion.keyframe.add`
- `motion.keyframe.update`
- `motion.keyframe.delete`
- `motion.keyframe.copy`
- `motion.keyframe.paste`
- `motion.keyframe.set_interpolation`
- `motion.curve.set_tangents`
- `motion.curve.retime`

효과/behavior:

- `motion.effect.add`
- `motion.effect.set_param`
- `motion.effect.bypass`
- `motion.mask.add`
- `motion.mask.track`
- `motion.behavior.add`
- `motion.behavior.set_param`
- `motion.behavior.bake`
- `motion.audio_reactive.bind`

3D/캐릭터:

- `motion.camera.add`
- `motion.light.add`
- `motion.ar_pbr.add`
- `motion.actor.add`
- `motion.actor.set_motion`
- `motion.actor.set_expression`
- `motion.actor.cache`

프리뷰/출력:

- `motion.preview.seek`
- `motion.preview.play`
- `motion.preview.cache_range`
- `motion.preview.capture`
- `motion.render.preflight`
- `motion.render.export`
- `motion.render.add_to_queue`
- `motion.timeline.place_clip`
- `motion.template.list`
- `motion.template.apply`
- `motion.template.publish`

## 15. 출력과 호환성

### 필수 출력

| 목적 | 출력 |
| --- | --- |
| 메인 에디터 재사용 | `.tgp` 내부 Motion Composition + Motion Clip |
| 일반 영상 | MP4 H.264/H.265 |
| 투명 합성 | MOV ProRes 4444 |
| 합성 중간 결과 | PNG sequence, OpenEXR sequence |
| 정지 결과 | PNG, JPEG, WebP |
| PPT 사용 | MP4/PNG/poster + source metadata |
| 방송 사용 | cached alpha video 또는 realtime scene source |

### 제한 변환

- Lottie JSON: 2D shape/text/transform/opacity/mask의 지원 subset
- SVG: 정지 vector 또는 제한된 animation
- glTF/GLB: 3D subscene와 지원 가능한 animation만
- OTIO: 컴포지션 전체가 아니라 편집 타이밍과 media reference 교환

### 초기 제외

- `.mogrt` 직접 생성/완전 import
- `.aep/.aepx` import/export
- Fusion `.comp` 호환
- 복잡한 PPT animation의 무손실 round trip

지원하지 않는 기능은 조용히 삭제하지 않고 preflight report에서 bake, rasterize,
unsupported 중 하나로 명확히 표시한다.

## 16. 제안 모듈 구조

```text
app/motion_designer/
  __init__.py
  schema.py
  project_io.py
  composition_service.py
  evaluator.py
  keyframes.py
  curves.py
  behaviors.py
  constraints.py
  expressions.py
  vector_shapes.py
  particles.py
  color_management.py
  source_frame.py
  source_adapters/
    video.py
    typography.py
    ppt.py
    ar_pbr.py
    live2d.py
    spine.py
    mmd.py
    vrm.py
  render_graph.py
  preview_renderer.py
  export_renderer.py
  cache.py
  asset_bridge.py
  timeline_bridge.py
  ppt_bridge.py
  broadcast_bridge.py
  templates.py
  plugin_registry.py
  validation.py
  qa.py
  ui/
    window.py
    canvas.py
    layer_panel.py
    inspector.py
    timeline.py
    dope_sheet.py
    graph_editor.py
    toolbar.py

app/actions/
  motion_namespace.py
  editor_adapter_motion.py

app/video_editor_motion_workflow.py
```

공통 수학 코어는 Qt를 import하지 않는다. UI, project service, renderer adapter를
분리해 테스트와 headless action 실행이 가능하게 한다.

## 17. 개발 단계와 완료 조건

### Phase 0. 공통 코어와 저장 계약

구현:

- MotionComposition/MotionLayer/AnimatedProperty schema
- keyframe evaluator와 Bezier curve
- `.tgp` persistence와 migration
- undo/redo/autosave command boundary
- `motion.composition.*`, `motion.layer.*`, `motion.keyframe.*` 기본 액션

완료 조건:

- 프로젝트 저장/재열기 후 모든 키와 계층이 동일하다.
- 같은 시간 평가가 deterministic하다.
- UI 없이 action으로 컴포지션을 생성하고 수정할 수 있다.

### Phase 1. 제품 가능한 2D Motion Designer

구현:

- 독립 창과 5영역 UI
- text/image/video/shape/group/null/adjustment layer
- transform/opacity/crop/mask/effect keyframe
- layer timeline, dope sheet, graph editor
- parent, motion path, basic behaviors
- OpenGL preview와 PNG/MP4/alpha sequence export

완료 조건:

- lower third, logo reveal, kinetic title을 UI와 액션 양쪽에서 제작한다.
- 1080p 기본 2D 장면이 지원 GPU에서 실시간에 가까운 프리뷰를 유지한다.
- 프리뷰와 export frame 비교 QA가 통과한다.
- undo/redo, autosave/recovery, missing media/relink가 동작한다.

이 시점부터 내부적으로 MVP가 아니라 `Motion Designer Beta`로 부를 수 있다.

### Phase 2. 메인 에디터·PPT·방송 연결

구현:

- Motion Clip lane과 live-link
- selected timeline range로 컴포지션 생성
- Media Pool/Timeline/Typography drag-and-drop
- PPT video/poster bridge
- Broadcast cached/realtime source bridge
- Render Queue job

완료 조건:

- Motion Clip이 메인 프리뷰와 최종 영상에 동일하게 합성된다.
- 컴포지션 수정 후 타임라인 cache가 정확히 무효화된다.
- PPT와 방송에서 동일 자산을 복사하지 않고 참조 또는 안정적 derivative로 사용한다.

### Phase 3. 3D와 캐릭터 레이어

구현:

- AR/PBR direct source adapter
- MMD/Live2D/Spine/VRM source adapter
- actor motion/expression/lip-sync timing
- camera/light animation
- depth-aware group와 actor pre-cache

완료 조건:

- 각 actor family마다 실제 지원 샘플로 preview/export evidence가 있다.
- VRM처럼 비싼 경로는 캐시 준비 상태와 예상 비용이 보인다.
- 호환되지 않는 모델은 실패 이유와 지원 범위를 표시한다.

### Phase 4. 오디오 반응·파티클·템플릿

구현:

- beat/onset/envelope 분석
- Composer/Voice Lab structured timing bridge
- GPU particle 기본 emitter
- 안전한 경량 property expression/link
- template parameter exposure와 animated preview
- 16:9/9:16/1:1 variant

완료 조건:

- 음악 비트 타이틀, TTS 캐릭터 설명, 방송 스팅어를 템플릿에서 만든다.
- 템플릿 교체 자산과 공개 파라미터가 action으로 제어된다.

### Phase 5. 제품화와 표준 출력

구현:

- ProRes 4444, PNG/EXR sequence 안정화
- Lottie/SVG 지원 subset exporter
- 명시적 SDR/HDR/linear color management와 alpha/gamma 검증
- render preflight와 compatibility report
- batch render, cancel/resume/failure diagnostics
- golden scene, 장시간 편집, GPU parity, package QA

완료 조건:

- 제품 설치본에서 샘플 자산 없이도 기본 템플릿을 만들고 내보낼 수 있다.
- 실제 외부 미디어/폰트 누락과 GPU context 실패를 복구 가능하게 안내한다.
- 호환성 보고서가 bake/unsupported 항목을 정확히 기록한다.

### Phase 6. 출시 후 생태계

구현:

- versioned plugin manifest
- source/effect/behavior/exporter extension point
- template pack validation과 dependency declaration
- plugin capability/permission declaration
- 설치·비활성화·호환성 진단

완료 조건:

- 외부 샘플 plugin이 본체 파일을 수정하지 않고 등록된다.
- 호환되지 않는 API version은 로드 전에 차단된다.
- plugin 오류가 core editor와 project open을 중단시키지 않는다.

## 18. QA와 품질 게이트

### 기능 QA

- keyframe interpolation golden values
- parent/constraint/time-remap determinism
- layer order, mask, matte, blend mode
- undo/redo transaction integrity
- save/load/migration/autosave/recovery
- drag-and-drop payload compatibility

### 렌더 QA

- preview/export pixel parity
- premultiplied alpha edge 검사
- color-space and gamma 검사
- transparent MOV와 PNG/EXR sequence 검사
- GPU context reuse와 worker 안정성
- 캐시 무효화와 stale frame 검사

### 자산 QA

- video/image/font
- AR/PBR golden GLB/GLTF/FBX corpus
- MMD QA corpus
- Live2D/Spine 지원 corpus
- VRM MToon GPU sample
- Voice Lab/Composer timing sample

### 성능 목표

- cached 2D 컴포지션 열기 P95 2초 이내
- 1080p 2D 프리뷰 목표 30 fps 이상
- 2D scrub 응답 P95 100 ms 이내
- 무거운 actor는 raw 실시간 수치를 숨기지 않고 cache-required로 분류
- 재생 중 UI event loop가 blocking render를 직접 수행하지 않음
- 지속형 OpenGL worker가 프레임마다 context나 전체 모델을 재생성하지 않음

### 제품 증거

- 실제 Motion Designer 창 스크린샷
- 실제 메인 타임라인의 Motion Clip
- 동일 시간의 Motion Designer, 메인 프리뷰, 최종 export 비교
- alpha checkerboard와 실제 영상 합성 비교
- action manifest와 dry-run/apply/undo 결과

## 19. 주요 리스크와 대응

### 범위 폭발

대응: 2D keyframe core와 메인 타임라인 합성을 먼저 제품화한다. 3D/캐릭터는
source adapter로 단계적으로 연결한다.

### 서로 다른 렌더러의 동기화

대응: 모든 adapter가 공통 시간과 SourceFrame 계약을 사용하고, 비싼 renderer는
frame/pose cache와 revision key를 사용한다.

### 프리뷰와 export 불일치

대응: 공통 evaluator와 shader packet을 사용한다. 별도 CPU export 효과를 만들지
않고 golden frame 비교를 release gate로 둔다.

### AI가 잘못된 내부 상태를 만드는 문제

대응: schema 검증, stable id, dry-run, transaction, preflight를 강제한다. AI는
UI widget이나 renderer private field를 직접 조작하지 않는다.

### 표준 포맷 손실

대응: `.tgp`가 완전한 편집 원본이다. Lottie/SVG/glTF/PPT는 지원 subset과 bake
정책을 보고서에 표시한다.

### 캐릭터 호환성 과장

대응: format 이름만 보고 지원을 선언하지 않는다. parser, renderer, motion,
preview, export를 실제 corpus로 통과한 범위만 표시한다.

## 20. 제품 출시 기준

다음 조건을 모두 만족해야 `Motion Designer 제품 품질`이라고 부른다.

1. 독립 창에서 2D 모션을 처음부터 끝까지 만들 수 있다.
2. 메인 타임라인 Motion Clip이 preview/export에서 동일하게 보인다.
3. text/image/video/shape/mask/effect의 임의 property keyframe과 Bezier 편집이 된다.
4. 투명 출력과 일반 영상 출력이 설치본에서 성공한다.
5. undo/redo, autosave/recovery, missing media relink가 있다.
6. AI가 주요 작업을 action으로 만들고 수정하고 되돌릴 수 있다.
7. AR/PBR와 최소 두 종류 이상의 character adapter가 실제 자산 QA를 통과한다.
8. preview/export parity와 alpha edge QA가 release gate에 포함된다.
9. unsupported export가 조용히 손실되지 않고 preflight에 나타난다.
10. 메인 에디터의 기본 영상 재생 성능을 Motion Designer 미사용 상태에서
    저하시키지 않는다.

## 21. 첫 구현 순서

1. `app/motion_designer/schema.py`와 Qt-free keyframe evaluator를 만든다.
2. PPT `AnimationSpec`과 Typography transform을 새 core로 변환하는 adapter를
   만든다. 기존 데이터 모델은 즉시 제거하지 않는다.
3. text/image/shape만으로 canvas, layer list, timeline, graph editor를 세운다.
4. OpenGL RGBA preview/export와 parity test를 먼저 통과시킨다.
5. `.tgp` 저장과 Motion Clip을 메인 타임라인에 연결한다.
6. video와 typography를 연결한다.
7. AR/PBR를 연결한다.
8. Live2D/Spine/MMD/VRM은 각각 독립 QA gate를 통과할 때 하나씩 연결한다.
9. audio reactive, template, AI action을 추가한다.
10. 표준 출력과 release acceptance를 마무리한다.

## 22. 최종 방향

Tiger Studio Motion Designer의 핵심은 새로운 섬을 하나 더 만드는 것이 아니다.
이미 있는 영상 편집, PPT, 타이포그래피, 캐릭터, 3D, 음성, 음악, 방송 기능을
공통 시간축과 레이어 계약으로 연결하는 것이다.

제품의 첫 승부처는 After Effects 기능 수가 아니라 다음 한 문장이다.

> Media Pool의 영상, 캐릭터, 3D, 타이포그래피와 음악을 드래그하고 움직인 뒤,
> 그 결과를 같은 프로젝트의 영상 타임라인, PPT, 방송에서 바로 사용한다.

이 흐름이 안정적으로 동작한 뒤에만 고급 파티클, 표현식, 더 넓은 교환 포맷을
추가한다.
