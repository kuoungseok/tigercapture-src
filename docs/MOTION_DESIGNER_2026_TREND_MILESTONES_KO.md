# Motion Designer 2026 Trend Gap and Implementation Milestones

## Machine-readable capability audit

`tigerstudio.motion.trend_capability_audit.v1` and the read-only
`motion.trend.capabilities.inspect` action bind all ten 2026 trend categories
to concrete contracts, registered Action/MCP IDs, QA tools, and explicit claim
limitations. The action verifies the declaration against its live
`ActionRegistry` and repository evidence paths at call time.
`tools/qa_motion_trend_capabilities.py` writes the same check as durable QA
evidence.

Current verified result: 10 categories, 8 `supported_v1`, 2 `limited_v1`,
0 unavailable, 0 missing actions, and 0 missing QA files. The limited scopes
remain existing roadmap follow-ups rather than new milestones: M24 material-ID
painterly overrides and M25 physical clay deformation, miniature volumetric
lighting, and automatic frame sculpting. These limits must remain visible
until implementation and visual evidence exist.

작성일: 2026-07-29  
상태: M21-M28 Complete v1; M24 재질-ID 세분화는 후속 범위
대상: Tiger Studio Motion Designer

## 1. 목적

이 문서는 2026년 모션그래픽 경향을 유행어로만 기록하지 않고, 현재
Motion Designer가 실제로 만들 수 있는 결과와 부족한 제작 기능을 구분한다.

핵심 방향은 다음과 같다.

> AI로 반복 작업을 줄이고, 사람이 선택한 텍스처, 불완전함, 타이밍,
> 캐릭터와 이야기로 결과를 차별화한다.

Adobe의 2026 Creative Trends 자료는 AI 발전과 함께 감각적 디테일,
문화적 진정성, 감정 연결, 의도적인 craft를 강조한다. Apple의 Liquid
Glass 설명은 단순 투명 블러가 아니라 주변 콘텐츠의 반사·굴절,
실시간 스펙큘러 반응, 콘텐츠와 상황에 따른 동적 변형을 핵심으로 둔다.

참고:

- Adobe 2026 Creative Trends:
  https://business.adobe.com/uk/resources/creative-trends-report.html
- Apple Liquid Glass:
  https://www.apple.com/ca/newsroom/2025/06/apple-introduces-a-delightful-and-elegant-new-software-design/
- Apple Developer, Meet Liquid Glass:
  https://developer.apple.com/videos/play/wwdc2025/219/
- Unreal real-time broadcast graphics:
  https://www.unrealengine.com/explainers/broadcast-and-live-events/what-are-broadcast-cinematics

Apple의 고유 구현을 복제하거나 동일하다고 주장하지 않는다. Tiger Studio는
동일한 시각 원리에서 출발한 자체 glass material을 구현한다.

## 2. 현재 기능 대조

판정:

- **강함**: UI, 문서 계약, Action/MCP, Preview/Export 경로가 이미 있음
- **부분**: 구성 요소는 있으나 하나의 제품 워크플로로 완결되지 않음
- **부족**: 유사 효과로 흉내는 가능해도 전용 계약과 제작 도구가 없음

| 2026 경향 | 판정 | 현재 근거 | 남은 핵심 |
| --- | --- | --- | --- |
| AI 워크플로 통합 | 강함 | `ai_generation.py`, 이미지 분해, segmentation, mask refine, background inpaint, OCR, choreography, 후보 비교와 patch Action | 영상 클린업 묶음, 스타일 잠금, 새 craft 기능을 편집 가능한 Action 조합으로 생성 |
| 진정성 있는 불완전함 | 부분 | Wiggle/Impact, Fractal Noise, Vignette, Posterize, Displacement | film grain, dust/scratch, gate weave, light flicker, print misregistration, 시간 일관 random seed |
| Craft를 럭셔리로 | 부분 | `cut_paper.py`, `paper_composite.py`, Paper Fold/Rip preset, Painter 연동 기반 | 스캔/종이/잉크 자산 라이브러리, rough edge, 프레임 드로잉·onion skin 전달, craft style stack |
| 2D+3D / Painterly 3D | 부분 | 2.5D camera, GLTF AR/PBR, light/shadow, 2D actor와 공통 composition | 3D 재질의 brush/toon/line/watercolor 스타일, 2D line overlay, painter texture projection |
| Liquid Glass / Glossy Motion | 부족 | Blur, Glow, Displacement, Light Sweep 조합으로 제한적 모사 가능 | backdrop sampling, 굴절 normal, 두께, dispersion, edge/specular, 움직임 반응, GPU/Export 일치 |
| 표현형 Kinetic Typography | 강함 | 글자/단어/줄 selector, per-glyph transform/opacity/fill/tracking/blur, text-on-path, shaping, GPU renderer | 스타일 템플릿과 오디오/감정 기반 자동 리듬 보강 |
| Mixed Media / Collage | 부분 | AI Collage 후보, image decomposition, cut-paper와 paste rig, 다중 매체 layer | collage 전용 작업공간, 스캔/손글씨/종이 texture browser, 접착·찢김·오려내기 modifier |
| Stop-motion inspired CGI | 부족 | Hold keyframe, time remap, posterize와 noise를 수동 조합 가능 | stepped exposure, pose/material jitter, clay/miniature surface, stop-motion camera/light preset |
| Story 중심 Brand Film | 부분 | AI brief/storyboard, multi-scene 광고·교육 템플릿, Voice/Music 연결 | 감정 arc와 beat graph, 장면 의도·캐릭터 목표, 음악 cue, review 가능한 story structure |
| 기타: mascot/platform/realtime/gradient | 부분~강함 | Live2D/Spine/MMD/VRM, 9:16·16:9·1:1 템플릿, generator/gradient stroke, Unreal UMG Link | 아날로그 nostalgia pack, 플랫폼별 재배치 규칙, 실시간 effect 예산 표시 |

### 결론

Tiger Studio의 약점은 기본 애니메이션 기능 수가 아니다. AI, 캐릭터,
타이포그래피, 합성 기반은 충분하다. 부족한 것은 다음 세 가지다.

1. 손맛을 반복해서 재사용할 수 있는 **Craft Style System**
2. backdrop을 실제로 읽는 **Glass/Refraction Material**
3. 단편 효과를 이야기와 플랫폼 결과물로 묶는 **Style/Story Direction**

## 3. 공통 완료 규칙

M21-M28은 다음 조건을 모두 만족해야 완료다.

- 직렬화 의미가 생기면 `.tgmotion` schema와 migration을 추가한다.
- UI 변경은 `MotionDocumentController`를 거쳐 undo/redo가 된다.
- 동일 기능을 `motion.*` Action/MCP로 조회·설정·제거할 수 있다.
- Motion Canvas, standalone Preview, main video preview, final Export가 같은
  시간에 같은 결과를 낸다.
- seed가 있는 procedural 결과는 동일 입력에서 결정적이어야 한다.
- GPU Preview가 없거나 실패하면 조용히 생략하지 않고 shared raster
  fallback 또는 blocked preflight를 반환한다.
- UMG로 전달 가능한 기능은 native/UI Material/bake/blocked 중 하나로
  `TigerStudioUMG`에 같은 변경에서 분류한다.
- 기능명만 있는 템플릿이 아니라 실제 입력 이미지·영상·3D·캐릭터로 만든
  16:9, 9:16 결과물과 UI 캡처를 남긴다.
- 60초 프로젝트 반복 재생과 export에서 cache budget, 메모리, 취소,
  recovery를 검증한다.

## 4. 전체 순서

| 순서 | 마일스톤 | 목적 | 상태 |
| --- | --- | --- | --- |
| M21 | Craft and Imperfection Style Stack | 아날로그 손맛을 재사용 가능한 효과 체계로 구현 | Complete v1 |
| M22 | Dynamic Glass Material | 실시간 backdrop glass와 glossy motion 구현 | Complete v1 |
| M23 | Mixed Media Craft Workspace | 종이·스캔·손그림·콜라주 제작 흐름 완성 | Complete v1 |
| M24 | Painterly 2D/3D Look Development | PBR 위에 2D line/brush/toon 스타일 결합 | Complete v1 |
| M25 | Stop-motion Timing and CGI | stepped timing, clay, miniature motion 구현 | Complete v1 |
| M26 | Story and Platform Direction | 감정 arc와 플랫폼별 장면 구조 구현 | Complete v1 |
| M27 | AI Style Director | 새 기능을 편집 가능한 AI 작업으로 통합 | Complete v1 |
| M28 | Trend Template and Product QA | 실제 템플릿, 성능, 배포 증거 완성 | Complete v1: 8-template pack |

의존 관계:

```text
M21 -> M23
M22 -> M24
M24 -> M25
M21 + M23 + M26 -> M27
M21-M27 -> M28
```

권장 착수 순서는 M21, M22, M23, M26, M24, M25, M27, M28이다. M21과
M22는 서로 다른 effect backend 작업으로 병렬 진행할 수 있다.

## 5. M21 - Craft and Imperfection Style Stack

목표: 사용자가 여러 효과를 수동으로 겹치지 않아도 통제 가능한 손맛을
레이어, 그룹, adjustment layer, composition에 적용한다.

### 2026-07-29 구현 상태

- `tigerstudio.motion.craft_style.v1` 계약과 `craft_style` 효과를 추가했다.
- Subtle Film, Handmade, Archive Print, Luxury Paper, Documentary Handheld,
  VHS Tape, Printed Poster, Warm Film, Rough Cut 프리셋을 제공한다.
- 결정론적 Film Grain, Dust/Scratch, Gate Weave, Light Flicker/Warmth,
  print misregistration, halation, VHS scan wobble, edge roughness가 Preview와
  Export의 공통 `effect_adapter` 경로를 사용한다.
- `Craft` Inspector에서 프리셋, 강도, grain, weave, flicker, locked seed를
  편집하고 기존 Craft 스택을 중복 없이 교체하거나 제거할 수 있다.
- `motion.craft.get/set/clear`, `motion.craft.preset.list/apply`,
  `motion.craft.texture.attach/relink`, `motion.craft.seed.randomize/lock`,
  `motion.craft.preflight` Action/MCP를 제공한다.
- durable paper/canvas/ink texture를 multiply/screen/overlay로 연결하며
  `debugCapture`를 프로젝트 의존 리소스로 사용하는 것은 거부한다.
- Unreal UMG 변환은 효과를 묵살하지 않고
  `effect_requires_bake:craft_style`로 명시한다.
- `tools/qa_motion_craft_style.py`가 실제 공통 렌더러로 Clean 포함 10종
  비교 PNG와 SHA-256 보고서를 생성한다.
- 300프레임 반복 렌더, loop boundary jump 0, Preview/Export 픽셀 parity를
  자동 테스트한다.
- 고급 Craft 품질 확장으로 RGB/mono grain 혼합, shadow/midtone/highlight
  grain response, dust/scratch 유지시간, scratch 방향, 결정론적 fibrous
  edge 강도·길이 조절을 공통 렌더 계약과 `Craft` Inspector에 추가했다.
  `tools/qa_motion_craft_style.py`는 RGB Grain, Angled Scratches, Fibrous
  Edge를 별도 비교 샘플로 렌더한다.

구현:

- `tigerstudio.motion.craft_style.v1`
- Film Grain: 크기, 강도, RGB/mono, shadow/midtone/highlight response
- Dust/Scratch: 밀도, 길이, 수명, 방향, seed
- Gate Weave/Handheld: 위치, 회전, 주파수, drift, settle
- Light Flicker/Exposure Breathing
- Chromatic Bleed와 Print Misregistration
- Halation, Warm Film Curve, VHS line/scan wobble
- Paper/Canvas/Ink texture overlay와 blend mode
- Edge Roughen, Torn/Fibrous edge
- 모든 시간 노이즈의 seed, cadence, loop period
- `Craft` Inspector와 style preset browser

Action/MCP:

- `motion.craft.get/set/clear`
- `motion.craft.preset.list/apply`
- `motion.craft.texture.attach/relink`
- `motion.craft.seed.randomize/lock`
- `motion.craft.preflight`

완료 증거:

- Clean/Crafted 비교 10종
- luxury paper, documentary handheld, VHS, printed poster, warm film preset
- 300프레임 loop 경계 jump 0
- Preview/Export seed와 픽셀 parity

## 6. M22 - Dynamic Glass Material

목표: blur 사각형이 아니라 뒤 콘텐츠를 읽고 움직임에 반응하는 Tiger
Glass material을 구현한다.

### 2026-07-29 구현 상태

- `tigerstudio.motion.glass.v1` 계약과 `tiger_glass` 효과를 추가했다.
- Clear, Frosted, Tinted, Glossy, Liquid CTA 프리셋을 제공한다.
- 레이어 합성 직전의 실제 canvas를 backdrop으로 샘플링하고 transformed
  layer alpha를 glass shape mask로 사용한다.
- blur, procedural normal refraction, thickness/absorption/tint, edge
  highlight/specular, chromatic dispersion, glossy bloom을 결정론적으로
  합성한다.
- `Look > Glass` Inspector와
  `motion.material.glass.create/get/set/remove`, preset list,
  driver bind, preflight Action/MCP를 제공한다.
- 지원 그래프는 `motion_glass_gpu` OpenGL backdrop shader로 렌더한다.
  지원 범위를 벗어난 그래프는 `backdrop_glass_requires_raster` 등 정확한
  진단과 shared backdrop raster로 fallback한다. Preview/Export 픽셀
  parity가 자동 검증된다.
- Draft/Preview blur는 multi-resolution pyramid를 사용하고 실제 glass
  mask bounds와 blur/refraction padding만 처리하는 ROI 경로를 사용한다.
- `tools/qa_motion_glass.py`는 1920x1080에서 5개 프리셋을 3프레임씩
  실렌더하고 contact sheet와 timing JSON을 남긴다. 2026-07-29 CPU
  fallback 측정은 ROI 전 278-374ms/frame, ROI 후 138-172ms/frame이다.
  이 값은 GPU 경로 도입 전 CPU 정확도 기준선이며 현재 실시간 제품
  판정에는 사용하지 않는다.
- Preview/Draft Glass는 이제 blur만 줄이는 대신 실제 Glass ROI의 backdrop,
  mask, refraction, dispersion, edge/specular 계산 전체를 각각 480/320px
  long-edge working surface에서 처리한 뒤 원본 alpha 경계로 복원한다.
  Final은 전해상도 계산을 유지한다. full-frame backdrop/mask를 먼저
  float32로 복사하던 경로도 ROI 확인 후 crop 변환으로 바꿨다.
- 같은 1080p 5프리셋 QA의 현재 Preview 평균은 프리셋별 약
  98-110ms/frame이고, 실제 표시 Motion 창의 5초 Liquid Glass 프로브는
  7.16fps였다. 이전 소스 프로브 3.63fps보다 약 97% 개선된 이 기록도
  GPU 경로 도입 전 역사적 기준선이다.
- Unreal UMG는 현재 복합 Glass를
  `effect_requires_bake:tiger_glass`로 명시한다.
- M22 v1은 GPU backdrop shader, 장시간 24fps 기준, 결정적 tiled export,
  UMG disposition까지 완료했다. UMG는 의미가 다른 native 근사를 하지
  않고 결정적 bake를 권고한다.

렌더 구조:

- glass layer 아래의 합성 결과를 별도 backdrop surface로 제공
- backdrop blur와 multi-resolution pyramid
- procedural 또는 texture normal 기반 UV refraction
- thickness, IOR-like bend, tint, absorption
- edge highlight, specular lobe, Fresnel-like response
- chromatic dispersion과 glossy bloom
- velocity/pointer/scroll driver에 따른 highlight와 shape response
- alpha/premultiplied 합성 및 중첩 glass 순서
- GPU Preview와 결정적 tiled Export

UI:

- `Material > Tiger Glass`
- Clear, Frosted, Tinted, Glossy, Liquid CTA preset
- Background contrast와 accessibility 경고
- performance quality: Draft/Preview/Final

Action/MCP:

- `motion.material.glass.create/get/set/remove`
- `motion.material.glass.driver.bind`
- `motion.material.glass.preflight`

UMG:

- 단순 blur/tint는 Retainer/UI Material 후보
- backdrop dependency 또는 복잡한 dispersion은 deterministic bake 또는
  명시적 blocked 결과

완료 증거:

- 실제 영상, gradient, text 위에 놓인 glass 5종
- 이동 중 refraction과 specular 반응
- 투명 배경, 중첩 glass, HDR source 회귀
- 1080p Preview 목표 프레임 시간과 Final export parity 기록

### 2026-07-29 상호작용 Glass 드라이버 갱신

- Preview 전용 pointer, pointer velocity, wheel scroll 입력을 문서를
  변경하지 않고 shared Glass render graph에 전달한다. 포인터 좌표는 실제
  컴포지션 표시 영역 기준이며 velocity와 scroll은 자연스럽게 감쇠한다.
  Export에는 이 일시 입력을 전달하지 않으므로 결과는 결정적이다.
  Liquid Glass App Promo의 Glass 3개는 기본적으로 pointer에 반응한다.
- `tools/qa_motion_glass.py`는 `tiger_glass_pointer_driver.png`를 생성하고
  1920x1080에서 중앙과 우하단 포인터가 서로 다른 픽셀을 렌더링했는지
  보고한다.
- non-raster GPU backdrop 경로와 안정적인 24fps 제품 기준은 아래
  OpenGL 제품 게이트에서 완료됐다. HDR 및 Glass-only tiled export
  증거도 완료됐다.
  UMG v1은 arbitrary sibling backdrop을 같은 의미로 샘플링할 수 없으므로
  native UI Material로 근사하지 않고 `effect_requires_bake:tiger_glass`
  차단과 결정적 image/video bake 권고로 확정했다.

### 2026-07-29 viewport-resolution Preview 갱신

- Glass만 raster effect로 사용하는 그래프는 Preview에서 더 이상
  1920x1080 전체를 합성한 뒤 축소하지 않고 실제 표시 영역 해상도로
  합성한다. Export와 다른 effect가 함께 있는 그래프는 전해상도 경로를
  그대로 유지한다.
- 전역 raster scale 뒤에 layer transform을 결합하고 Glass blur,
  refraction, dispersion, edge, bloom과 motion blur/card shadow의 픽셀
  거리도 표시 해상도에 맞춰 조절한다.
- 1920x1080 결과를 축소한 기준과 960x540 직접 합성 결과의 평균 절대
  차이는 RGB 0.25, alpha 0.18이고, 단일 프레임 측정은 약 2.4배 빨라졌다.
- 실제 표시 창의 716x403 Preview를 15.20초 재생해 296 frame swap,
  1회 loop, 19.48fps를 기록했고 RSS는 약 2.3MB 감소했다. 짧은 5초
  구간은 28.82fps였다. 이전 7.16fps보다 크게 개선됐지만 이 측정은
  아래 OpenGL 경로 도입 전 CPU viewport 기준선이다.

### 2026-07-29 HDR Glass 제품 증거 갱신

- 60초 통합 제품 게이트의 HDR artifact를 일반 Craft 대체 장면이 아니라
  `tiger_glass` 3개를 포함한 실제 Liquid Glass 장면으로 교체했다.
- Glass 제거 기준과 비교해 14,734 pixel, 평균 RGB 절대 차이 23.62를
  확인했고 실제 H.265 stream은 BT.2020 primaries와 SMPTE ST 2084
  transfer를 보고한다.
- 2 frame 이하의 짧은 H.265 MP4는 x265 B-frame DTS를 FFmpeg MP4
  muxer가 간헐적으로 거부하는 문제가 있어 이 조건에서만 B-frame을
  끈다. 긴 출력의 x265 압축 구조는 유지한다.
- HDR Glass 증거와 Glass 전용 결정적 tiled export가 완료됐다.

### 2026-07-29 결정적 Glass 타일 출력 갱신

- `tigerstudio.motion.tiled_export.v1`은 전체 프레임을 먼저 렌더한 뒤
  자르는 방식이 아니라, blur/refraction/dispersion/bloom 범위만큼
  padding한 composition source region을 타일별로 독립 렌더하고 중앙
  영역만 조립한다.
- Glass 좌표 계산은 타일의 로컬 크기가 아니라 composition 전역 좌표를
  사용하므로 타일 경계에서 굴절과 하이라이트 위상이 끊기지 않는다.
- v1은 Glass-only bounded graph만 허용한다. adjustment, precomp, matte,
  card shadow, motion blur, non-Glass effect가 있으면 full-frame fallback으로
  숨기지 않고 preflight 오류를 반환한다.
- 실제 60초 제품 게이트의 HDR H.265 artifact가 96px 타일 8개와 65px
  padding을 사용했다. 가장 큰 중간 surface는 36,386 pixel로 전체
  57,600 pixel보다 작았고, full-frame 기준과 평균/최대 pixel 차이는
  모두 0이었다.
- `motion.export.tiled.set`, `motion.export.tiled.preflight` Action/MCP로
  AI가 활성화와 호환성 검사를 수행할 수 있다. 최종 조립 image 자체는
  여전히 출력 해상도 크기이며, v1의 제품 주장은 중간 메모리 절감,
  seam 안전성, 결정적 parity에 한정한다.

### 2026-07-29 Unreal Glass disposition 확정

- 공유 Tiger UMG 계약을 schema v4로 올리고 Motion/Painter 양쪽 레이어에
  정식 `BlockReasons` 배열을 추가했다. PayloadJson을 해석해야만 사유를
  알 수 있던 v3와 달리 Unreal preflight가 layer ID와 사유를 직접
  반환한다.
- Motion 패키징 단계에서도 blocked layer를 발견하면 Unreal 실행 전에
  중단하고 정확한 layer/reason 목록을 반환한다.
- `D:\UE_5.8\Engine`으로 Editor, Game Development, Game Shipping
  플러그인 빌드가 모두 성공했다. source-free bundle로 실제 임시
  프로젝트에서 Widget Blueprint 1개와 UWidgetAnimation 1개를 생성,
  컴파일, 재로드했다.
- 별도 실제 UE preflight는 Glass 문서를
  `glass:effect_requires_bake:tiger_glass`로 차단했다. 따라서 M22 v1은
  Glass를 UI Material로 불완전하게 근사하지 않고 결정적 bake 경로를
  권장한다.

### 2026-07-29 OpenGL Glass 제품 기준 완료

- `MotionGlassGpuRenderer`는 실제 OpenGL fragment shader에서 backdrop
  blur, procedural refraction, chromatic dispersion, tint/absorption,
  edge/specular/bloom과 runtime driver를 처리한다. Glass 효과를 CPU
  raster 결과로 미리 굽지 않는다.
- 레이어 순서를 보존하기 위해 일반 레이어 구간은 shared raster segment,
  Glass 레이어는 shader pass로 나눈 뒤 두 개의 non-MSAA FBO를
  ping-pong한다. 각 Glass pass는 직전 framebuffer를 backdrop으로
  샘플링하므로 중첩과 임의 순서가 유지된다. FBO는 viewport 크기별로
  재사용하며 GPU working surface의 긴 변을 960px로 제한해 고DPI 화면의
  불필요한 preview 비용을 막는다.
- v1 GPU 범위는 normal blend, matte 없음, card shadow 없음, motion blur
  없음, adjustment/precomp 없음, Glass 레이어에 추가 effect 없음이다.
  범위를 벗어나면 조용히 생략하지 않고 기존 정확한 shared raster
  경로와 구체적인 reason으로 fallback한다. 전체 Motion graph가
  GPU-native라는 주장은 하지 않는다.
- 실제 15.36초 제품 프로브는 450 frame swap, 29.29fps, 1회 loop,
  `motion_glass_gpu`, GL error 0을 기록했다. 같은 시점 CPU 기준과의
  시각 parity는 평균 RGB 절대 차이 4.51/255, p95 8/255이며 자동 제품
  한계 12/36을 통과했다.
- 최종 60.36초 지속 프로브는 1,601 frame swap, 26.52fps, 4회 loop,
  GL error 0을 기록했다. 같은 시점 parity도 평균 3.84/255, p95 10/255로
  통과했다. 따라서 M22 Dynamic Glass v1은 완료다. 결정적 Final Export는
  GPU preview 근사가 아니라 기존 shared full/tiled renderer를 계속
  사용한다.

## 7. M23 - Mixed Media Craft Workspace

### 2026-07-29 구현 상태

- `tigerstudio.motion.collage.v1` 보드 계약이 기존 Motion layer를 stable
  item ID, z-stack, layout seed, edge, attachment, source revision, Painter
  link로 묶는다. `.tgmotion` 저장/로드 시 이 계약과 ID가 그대로
  round-trip 된다.
- `Look > Collage` Inspector와 `Mixed Media` Library category에서
  Editorial, Luxury Paper, Education, Scatter 보드를 만들고 Smart,
  Polygon, Torn, Feather, Fiber edge를 편집할 수 있다.
- Torn/Fiber/Feather edge는 실제 editable path mask로 렌더되며, Glue,
  Tape, Staple, Pin, Fold attachment는 native child layer 또는
  `paper_fold` effect로 남는다.
- `scan_cleanup` effect는 스캔 종이의 밝은 영역을 기준으로 white
  balance하고, 선택적으로 paper alpha를 제거하면서 dark ink를
  보존한다. Preview와 Export는 동일한 `effect_adapter` 경로를 쓴다.
- `motion.collage.create`, item add/update/reorder, edge/attachment/scan set,
  source replace, Painter send/refresh, preflight Action/MCP가 등록됐다.
- source replace는 Motion layer ID, collage item ID, parent, pivot, in/out,
  source-in, time scale, reverse를 보존한다. Painter handoff는
  `tigerstudio.motion.collage.painter_handoff.v1`로 같은 Motion layer ID를
  다시 돌려준다.
- UMG 변환은 collage semantics를 조용히 버리지 않고
  `motion_feature_requires_bake:collage_item`으로 deterministic bake를
  요구한다.
- `tools/qa_motion_collage.py`가 공용 export renderer로 10초 Editorial
  Collage, Luxury Paper Title, Education Cutaway 3종을 12프레임 렌더하고
  contact sheet, timing JSON, stable ID loss 0 증거를 생성한다.
- `tigerstudio.motion.collage_asset_pack.v1`은 Cotton Paper, Kraft
  Cardboard, Newsprint, Masking Tape, Black Ink Card, Graphite Sheet를
  외부 바이너리 없이 결정론적 shape와 Craft 효과로 생성한다. 빈
  프로젝트에서도 `Look > Collage`의 Starter Material로 바로 추가할 수
  있고 `motion.collage.asset.catalog/add` Action/MCP가 같은 editable
  layer 계약을 사용한다. `tools/qa_motion_collage_asset_pack.py`는 6개
  재료를 공용 renderer로 비교한다.
- v1 이후 확장 범위는 Painter 창에 직접 객체를 생성하는 양방향
  transport와 frame drawing exposure/onion-skin UI다. 이 후속 범위는
  v1의 보드·렌더·Action 계약 완료 주장을 막지 않는다.

목표: AI가 잘라준 레이어를 단순 이동하는 수준에서 벗어나, 종이와 손그림을
직접 조합하는 작업 흐름을 제공한다.

구현:

- `Mixed Media` Library category와 durable asset pack
- paper, cardboard, tape, ink, brush, scan, handwriting texture
- Cut/Paste mode: polygon cut, smart edge, torn edge, feather/fiber
- glue shadow, tape gloss, staple/pin, fold/crease modifier
- scan cleanup: white balance, paper remove, ink preserve
- collage board와 z-stack, random scatter, controlled overlap
- Painter로 보내기/받기와 stable layer ID
- frame drawing은 Painter가 소유하고 Motion은 timing, exposure,
  onion-skin reference와 clip placement를 소유

Action/MCP:

- `motion.collage.create`
- `motion.collage.item.add/update/reorder`
- `motion.collage.edge.set`
- `motion.collage.attachment.set`
- `motion.collage.paint.send/refresh`
- `motion.collage.preflight`

완료 증거:

- 10초 editorial collage, luxury paper title, 교육 cutaway
- source 교체 후 edge, pivot, parent, timing 보존
- Painter round-trip에서 ID 손실 0

## 8. M24 - Painterly 2D/3D Look Development

목표: 현재 AR/PBR 3D를 사실적 렌더 한 종류로 제한하지 않고 2D motion과
같은 미술 방향 안에 배치한다.

구현:

- PBR base를 유지한 toon band와 painted light ramp
- depth/normal 기반 silhouette와 선택 edge line
- material별 line 제외와 색상 지정
- brush stroke, watercolor granulation, paper projection
- texture-space 또는 screen-space painter overlay
- 2D annotation/path를 3D point/plane에 attach
- camera/light 변화에도 line과 texture가 안정적인 temporal filter
- layer별 `realistic`, `toon`, `painted`, `ink`, `paper` look preset

Action/MCP:

- `motion.lookdev.get/set`
- `motion.lookdev.material.override`
- `motion.lookdev.line.set`
- `motion.lookdev.texture.project`
- `motion.lookdev.preflight`

완료 증거:

- 같은 GLTF의 realistic/toon/painted/ink 비교
- 카메라 회전 중 line popping 기준
- video + 3D + 2D type 한 장면의 Preview/Export parity

### 8.1 구현 상태 - Complete v1

- `tigerstudio.motion.painterly_look.v1`과 `painterly_look` 효과를 추가했다.
  이 효과는 새 3D 렌더러가 아니라 이미지, 비디오 프레임, 기존 AR/PBR
  렌더 결과에 동일하게 적용되는 provider-neutral 후처리 계층이다.
- Realistic, Toon, Painted, Ink, Paper 5개 preset은 bilateral paint
  smoothing, 명도/색상 band, 안정적인 Sobel 계열 line, brush stroke,
  granulation, paper tint, cross-hatching을 편집 가능한 값으로 제공한다.
- procedural 질감과 line은 문서 seed와 screen 좌표에 고정되어 같은
  입력 프레임에서 시간만 달라져도 line popping이 생기지 않는다. 원본
  alpha는 보존된다.
- `Look > Painterly` Inspector와 일반 Effects 목록이 같은 효과 계약을
  편집한다. durable texture를 Multiply, Screen, Overlay 방식으로
  screen projection할 수 있다.
- Action/MCP는 `motion.lookdev.get/set/clear`,
  `motion.lookdev.preset.list`, `motion.lookdev.line.set`,
  `motion.lookdev.material.override`, `motion.lookdev.texture.project`,
  `motion.lookdev.preflight`를 제공한다.
- 현재 post-render 경로에는 material-ID pass가 없으므로 재질별 override를
  저장할 수는 있지만 적용 가능하다고 거짓 주장하지 않는다. override가
  있으면 preflight가 `material_id_pass_unavailable`을 명시적으로 반환한다.
- Unreal UMG 변환은 `effect_requires_bake:painterly_look`을 기록해 효과를
  조용히 생략하지 않는다.
- `tools/qa_motion_painterly_look.py`는 5개 preset의 실제 contact sheet,
  시간 안정성, alpha 보존, 픽셀 차이를 검증한다. 현재 모든 preset이
  통과했다. 960x540 warm Painted 진단은 480px bounded working surface에서
  약 28.1ms/frame을 기록했다. 이 수치는 CPU 진단이며 GPU 실시간 주장으로
  사용하지 않는다.
- M28의 `Painterly Character Spot`은 이미지, 비디오, 기존 AR/PBR 렌더
  레이어를 교체 슬롯으로 받는 실제 3장면 템플릿으로 전환됐다. 새로운
  3D 엔진을 추가한 것은 아니다.

## 9. M25 - Stop-motion Timing and CGI

목표: 단순 저프레임 영상이 아니라 촉각적인 stop-motion 움직임을 설계한다.

구현:

- layer/composition `stepped exposure`와 1s/2s/3s frame hold
- hold 중 미세 pose jitter와 material boil
- contact settle, overshoot, replacement-style pop
- clay, felt, cardboard, painted wood material preset
- miniature key/fill/rim과 hard contact shadow preset
- gate weave, focus breathing, exposure flicker 연결
- onion skin과 pose compare
- audio transient에 exposure/pose change snap

Action/MCP:

- `motion.stop_motion.get/set`
- `motion.stop_motion.pose.capture/apply`
- `motion.stop_motion.material.set`
- `motion.stop_motion.audio.snap`
- `motion.stop_motion.preflight`

완료 증거:

- 6초 clay mascot, 10초 miniature product, 8초 paper replacement animation
- frame cadence 위반 0
- 정지 노출 구간의 의도하지 않은 interpolation 0

### 9.1 Implementation Status - Complete v1

- `tigerstudio.motion.stop_motion.v1` stores composition or layer-level ones,
  twos, and threes exposure. The evaluator, Canvas source renderer, Preview,
  and Export use the same quantized time.
- Position, rotation, and scale jitter remain deterministic inside each held
  exposure. Contact settle, overshoot, and replacement pop provide tactile
  timing styles without flattening the source animation.
- Clay, felt, cardboard, and painted-wood presets use editable `craft_style`
  and `drop_shadow` effects with a locked seed and material metadata.
- Pose capture/apply keeps stable pose and keyframe IDs and writes hold
  interpolation. Onion inspection and audio-transient snapping use the same
  exposure grid.
- `Look > Stop Motion` and `motion.stop_motion.*` Action/MCP commands edit the
  same contract.
- Unreal conversion returns
  `motion_feature_requires_bake:stop_motion` instead of silently dropping
  stepped timing.
- `tools/qa_motion_stop_motion.py` renders the required 6-second clay mascot,
  10-second miniature product, and 8-second paper replacement scenarios.
  Current evidence has zero cadence violations and zero unintended pixel
  interpolation inside holds; the next exposure changes.
- v1 is a deterministic stepped-motion authoring tool. Physically simulated
  clay deformation, volumetric miniature lighting, and automatic frame
  sculpting remain later work and are not current claims.

## 10. M26 - Story and Platform Direction

목표: 효과가 많은 클립이 아니라 감정과 메시지가 진행되는 브랜드 필름을
만들고, 플랫폼별 결과로 안전하게 변환한다.

구현:

- Hook, setup, desire, conflict, reveal, proof, payoff, CTA beat graph
- beat별 목적, 감정, 캐릭터, copy, visual, audio cue
- Scene 카드와 composition/time range 연결
- Voice Lab 대사와 Music Lab cue/tempo marker 연결
- character/mascot continuity와 screen direction 검사
- 16:9, 9:16, 1:1 safe zone 및 text density 검사
- crop만 하는 변환이 아니라 priority 기반 constraint reflow
- 플랫폼별 최소 text size, CTA hold, subtitle-safe area
- 사람이 승인하는 variant diff

Action/MCP:

- `motion.story.inspect/update`
- `motion.story.beat.add/update/reorder`
- `motion.story.audio.bind`
- `motion.platform.variant.plan/preview/apply`
- `motion.platform.preflight`

완료 증거:

- 같은 15초 광고의 16:9, 9:16, 1:1 세 버전
- 캐릭터, CTA, 자막 잘림 0
- 자동 변경 내용을 사람이 검토 가능한 diff로 제시

### 10.1 구현 상태 - Complete v1

- `tigerstudio.motion.story_direction.v1`은 Hook, Setup, Desire, Conflict,
  Reveal, Proof, Payoff, CTA beat와 목적, 감정, 캐릭터, copy, visual,
  audio cue, scene/layer 연결을 composition metadata에 저장한다.
- Story workspace에서 제목, 메시지, 대상과 beat를 작성할 수 있다.
  Voice Lab 및 Music Lab 결과는 안정 ID, cue 시각, label, 선택적 BPM을
  beat에 연결한다. Story 패널은 문서에 실제 import된 Voice timing과
  Composer timing/audio path를 `Voice / Music` 목록으로 보여주고 선택한
  beat 시작점에 바인딩하며, beat 목록에 Voice/Music 상태를 표시한다.
  세부 beat 수정·재정렬과 audio binding은 동일 문서 계약을 사용하는
  Action/MCP에서도 제공된다.
- `tigerstudio.motion.platform_variant_plan.v1`은 원본을 변경하지 않고
  16:9, 9:16, 1:1 reflow diff를 만든다. Background, Headline, Subtitle,
  CTA, Character/Mascot, 일반 content 역할과 명시적 priority를 기준으로
  위치, scale, position/scale keyframe, font size를 변환한다.
- variant 적용은 source composition ID와 revision을 검증하며
  `approved=true`가 없으면 거부한다. 적용 결과는 새 composition ID를
  가지되 layer/keyframe stable ID를 유지하고, 전체 변경 diff와 원본
  revision을 metadata에 보존한다.
- platform preflight는 protected layer safe-area, subtitle safe-area,
  최소 text size, text density, CTA hold를 검사한다. Story preflight는
  range, overlap, 누락 layer, Hook/CTA, character screen-direction
  continuity를 검사한다.
- Action/MCP는 `motion.story.inspect/update`,
  `motion.story.beat.add/update/reorder`, `motion.story.audio.bind`,
  `motion.platform.variant.plan/preview/apply`,
  `motion.platform.preflight`를 제공한다.
- `tools/qa_motion_story_platform.py`는 15초 8-beat 광고를 shared Motion
  renderer로 16:9, 9:16, 1:1에 각각 4프레임씩 렌더한다. 현재 증거는
  story issue 0, protected character/headline/subtitle/CTA 잘림 0,
  stable ID loss 0, source mutation 0이다.
- v1은 role/priority 기반의 결정적 constraint reflow다. 장면의 의미를
  새로 해석하는 생성형 art direction과 플랫폼별 copy rewrite는 M27 AI
  Style Director와 후속 제품 폴리싱 범위다.

## 11. M27 - AI Style Director

목표: AI가 이미지를 교체하거나 평면 영상을 만드는 것이 아니라 M21-M26의
편집 가능한 문서와 Action을 조합하게 한다.

구현:

- prompt + image/video/audio reference에서 style intent와 story intent 분리
- Clean, Craft, Collage, Glass, Stop-motion 후보 생성
- 브랜드 색, font, texture, seed, mascot style lock
- 수정 시 사용자가 고친 layer와 keyframe 보호
- provenance와 generated/derived/manual 구분
- 비용과 backend availability를 계획 전에 표시
- 실패한 segmentation/glass GPU/3D style은 명시적 대체안 제시
- candidate preview는 실제 renderer 결과만 사용

Action/MCP:

- `motion.ai.style.plan`
- `motion.ai.style.candidates.generate`
- `motion.ai.style.apply`
- `motion.ai.style.lock.set`
- `motion.ai.story.plan/apply`
- `motion.ai.trend.preflight`

완료 증거:

- 같은 입력으로 5개 스타일 후보
- 적용 후 모든 결과가 일반 layer/effect/material/story 데이터로 편집 가능
- 사용자 수정 보존 회귀
- AI 없이도 같은 Action을 수동 실행 가능

구현 상태:

- `tigerstudio.motion.ai_style_plan.v1`은 style intent와 story intent,
  reference provenance, backend availability, 예상 비용, fallback을 계획 시점에
  고정한다. Claude 공유 provider를 사용할 수 있지만, v1의 5개 스타일
  컴파일은 오프라인에서도 동일하게 실행되는 결정적 로컬 경로다.
- AI 작업공간은 Clean, Craft, Collage, Glass, Stop Motion 후보를 복제된
  컴포지션에 적용하고 `MotionExportRenderer`로 실제 384x216 프레임을
  렌더한다. 사용자는 이 프레임과 operation, 보존 범위, backend, 비용,
  warning을 검토한 뒤 명시적으로 승인한다.
- 적용은 source, transform, pivot, keyframe, 수동 effect를 변경하지 않는다.
  brand font/texture/seed/mascot와 protected layer lock을 유지하며,
  Style Director가 생성한 데이터만 다음 후보에서 정리한다.
- `tigerstudio.motion.ai_story_plan.v1`은 Hook부터 CTA까지 8개 beat의 안정 ID를
  계획하고 승인 후 기존 story 데이터 계약으로 적용한다.
- `tigerstudio.motion.ai_semantic_style_direction.v1`은 기존 5개 후보 안에서만
  추천 style, 전체 순위, 후보별 짧은 이유, Hook/Pace/Payoff 지침을
  provider에 요청한다. 후보 추가·삭제·중복과 stale revision은 거부하고
  실패 시 fallback을 공개한 결정적 prompt-intent 순위를 사용한다.
  AI Workspace는 추천 후보를 첫 번째로 표시하고 승인 결과 metadata에
  추천과 provider provenance를 보존한다.
- `tigerstudio.motion.ai_platform_copy_plan.v1`은 16:9, 9:16, 1:1별
  Hook/Headline/Subtitle/Body/CTA 글자 제한과 현재 story audience/message를
  shared AI provider 경계에 전달한다. provider는 안정 target ID, 역할,
  원문, 제한값을 추가·삭제·변경할 수 없고 제안 문구와 이유만 바꿀 수 있다.
  provider가 없거나 실패하면 fallback 사실을 노출하고 결정적 길이 맞춤
  계획을 반환한다.
- `motion.ai.platform_copy.plan/apply/preflight`는 계획, 검사, 승인 적용을
  Action/MCP로 제공한다. protected text layer, 다른 composition, stale
  revision, 제한 초과, target set 변경은 거부한다. 승인 결과는 일반 story
  beat copy와 text source parameter로 남고 transform/media는 보존된다.
- AI Workspace에는 16:9/9:16/1:1 선택과 `Copy` 명령이 있으며 계획은 UI
  thread 밖에서 실행된다. 결과 창은 원문/제안, 현재/최대 글자 수,
  provider fallback과 preflight를 보여준 뒤 기존 `Apply` 승인으로
  적용한다. `tools/qa_motion_platform_copy_ui.py`가 실제 Qt 창 증거를
  캡처한다.
- Glass 후보는 현재 shared raster CPU fallback을 명시한다. Painterly는
  M24의 provider-neutral post-render 효과와 5개 preset을 사용한다. 기능을
  조용히 생략하거나 GPU/3D 지원을 주장하지 않는다.
- `tools/qa_motion_style_director.py`는 동일 입력의 5개 후보를 실제 renderer로
  렌더한다. 현재 QA는 원본 source mutation 0, transform/keyframe loss 0,
  story beat 8개를 기록한다.

M27 v1은 편집 가능한 deterministic style/copy compiler와 review workflow다.
생성형 모델이 완성된 art direction을 스스로 설계하거나 이미지 내용을 새로
그리는 기능이라고 주장하지 않는다.

## 12. M28 - Trend Template and Product QA

목표: 기능 데모를 제품 템플릿과 재현 가능한 QA로 완성한다.

필수 템플릿:

1. Luxury Craft Product Reveal
2. Editorial Mixed Media Collage
3. Liquid Glass App Promo
4. Painterly 3D Character Spot
5. Clay Stop-motion Mascot
6. Emotional Brand Story
7. VHS/Nostalgia Music Promo
8. Kinetic Type Vertical Short

각 템플릿은 16:9 또는 9:16 실제 사용 variant, 교체 슬롯, 라이선스 메타,
최소 3개 scene, preview thumbnail, tutorial steps를 제공한다.

QA:

- `tools/qa_motion_2026_trend_matrix.py`
- 실제 창 캡처와 실제 MP4/PNG sequence
- Preview/main viewer/export parity
- 60초 반복, cancel/resume, recovery
- CPU/GPU fallback과 backend missing UX
- HDR/SDR, alpha, nested composition, adjustment scope
- UMG native/bake/blocked 결과 누락 0

현재 구현:

- `tigerstudio.motion.trend_template.v1` 기반으로 다음 8개 제품 템플릿을
  템플릿 갤러리에 추가했다.
  Luxury Craft Product Reveal, Editorial Mixed Media Collage,
  Liquid Glass App Promo, Clay Stop-motion Mascot,
  Emotional Brand Story, VHS Nostalgia Music Promo,
  Kinetic Type Vertical Short, Painterly Character Spot.
- 각 템플릿은 10~15초, 3~5개 scene, 실제 교체 media slot, 4단계 tutorial,
  16:9/9:16/1:1 중 해당 제품 variant, 일반 layer/effect/story/stop-motion
  데이터로 구성된다. 템플릿 전환은 이전 템플릿이 소유한 composition
  상태만 정리하고 사용자의 별도 metadata는 유지한다.
- `motion.template.trend.capabilities`와
  `motion.template.trend.preflight`는 지원 템플릿, 모든 variant validation,
  UMG native/bake/blocked 사유를 반환한다.
- `tools/qa_motion_2026_trend_matrix.py`는 8개 템플릿의 모든 장면을
  `MotionExportRenderer`로 렌더하고 contact sheet, 장면 차이, 문서 validation,
  UMG 누락 여부를 기록한다. 현재 8개 템플릿과 19개 variant가 유효하며
  QA contact sheet는 비어 있지 않고 장면별 픽셀 차이가 있다.
- `tools/qa_motion_2026_product_gate.py`는 실제 60초 템플릿을 2fps PNG
  120프레임으로 렌더한다. 8프레임에서 취소한 뒤 손상 프레임 하나를
  재생성하고 유효한 7프레임을 재사용해 120프레임을 완성한다. 같은 실행에서
  recovery checksum roundtrip, straight-storage/premultiplied-composite alpha,
  nested composition Preview/Export pixel parity, HDR PQ H.265 preflight,
  실제 H.264 MP4 생성을 함께 검증한다. 실제 HDR H.265 파일도 생성하고
  스트림을 다시 읽어 Rec.2020 primaries와 SMPTE ST 2084 transfer를 확인한다.
- `tools/qa_motion_2026_trend_ui.py`는 실제 Qt Motion Designer 작업창과
  `2026 Trends` 템플릿 갤러리를 캡처하고 8개 템플릿 노출을 검사한다.
  긴 Library 설명이 패널 최소 폭을 밀어내지 않도록 말줄임 처리했으며,
  Library/Project 패널 폭을 제한해 Canvas가 주 작업 영역을 유지한다.
- `TigerStudio.exe --motion-runtime-probe <report.json>
  --motion-runtime-seconds 60`은 실제 Liquid Glass 템플릿과
  `QOpenGLWidget` Preview를 열어 벽시계 기준 반복 재생, frame swap, loop,
  memory, renderer diagnostics, 실제 작업창 캡처와 정확한 OpenGL
  framebuffer 캡처를 기록한다. 프로브 실행 유효성과 제품 실시간 기준
  (24fps 이상, raster fallback 아님)을 분리한다.
- runtime report는 frozen 여부, 실제 실행 파일 절대 경로·크기·SHA-256,
  정확한 `motion_glass_gpu` backend, GL feedback/error, GPU composition
  crop, 같은 시점 CPU reference와 parity 수치를 기록한다.
  `tigerstudio.motion.trend_distribution_qa.v2`는 검사 대상
  `TigerStudio.exe`와 이 provenance가 일치해야만 배포 증거로 인정한다.
  따라서 소스 프로브 결과를 오래된 설치본에 붙이거나
  `product_realtime_ready=true`만 조작해서 통과할 수 없다.
- 최종 PyInstaller 배포본의 표시 상태 60초 측정은 60.45초 동안 230회
  frame swap, 4회 전체 루프, 3.81fps를 기록했다. RSS는 457.7MB에서
  444.4MB로 13.3MB 감소했다. OpenGL context, 작업창 PNG, framebuffer
  PNG는 모두 유효하며 캡처 찢김도 없다.
  `tools/qa_motion_2026_frozen_distribution.py`는 세 배포 실행 파일,
  런타임 보고서, 최소 실행 시간, 측정 유효성, OpenGL, 메모리 샘플과 증가
  한도, 두 캡처를 검사하고 `frozen_bundle_smoke_ok=true`를 반환한다.
- 같은 배포 QA는 `product_realtime_ready=false`를 별도로 유지한다.
  이 결과는 새 `motion_glass_gpu` 소스를 포함하지 않은 이전 PyInstaller
  배포본의 역사적 기준선이다. 소스 제품 게이트에서 M22는 통과했지만
  M28은 새 frozen bundle로 동일한 60초 게이트를 다시 통과해야 한다.
- revision `14a36b98`의 새 PyInstaller 번들은 2,966개 파일,
  4,928,930,533바이트이며 `TigerStudio.exe`는 51,174,799바이트,
  SHA-256
  `187ff15e4a7aae3079555c88ffeba76324f105f08c068fc228dea4efc9b3e006`이다.
  이 frozen 실행 파일 자체의 60.34초 실창 프로브는 1,742 frame swap,
  28.87fps, 5회 loop, `motion_glass_gpu`, GL error 0, 메모리 증가
  16,887,808바이트를 기록했다. GPU/CPU parity는 평균 3.98/255,
  p95 8/255다.
- `tigerstudio.motion.trend_distribution_qa.v2`는 이 실행 파일의 경로,
  크기, SHA-256과 runtime report를 대조했고 모든 bundle/realtime/visual
  증거를 통과해 `blockers=[]`, `frozen_bundle_smoke_ok=true`,
  `product_realtime_ready=true`를 반환했다. 따라서 M28의 frozen 실시간
  배포 게이트는 완료됐다.
- 같은 frozen bundle로 Inno Setup 6.7.3 설치본을 생성했다. 설치본은
  2,109,158,225바이트이고 SHA-256은
  `8496a476cc58071af1c28587d6f5e0af654831abd2beeb3fa1d74d594e0fd594`다.
  설치 smoke는 임시 사용자 경로에 2,968개 파일을 설치하고 실제
  `Tiger Studio` 창을 확인했다. 설치된 `TigerStudio.exe`의 크기와
  SHA-256은 frozen runtime report와 정확히 일치했으며, 정상 제거 후
  임시 설치 경로도 남지 않았다.
- 설치 smoke의 freshness 기준은 더 이상 동시에 수정되는 소스 mtime이
  아니다. `--frozen-runtime-report`로 지정한 검증 완료 실행 파일의
  size/SHA-256을 설치 결과와 직접 비교하므로 다른 세션의 후속 소스
  편집이 거짓 실패나 거짓 통과를 만들지 않는다. 최종 보고서는 동시
  Painter 편집 때문에 `installer_current_for_source=false`지만
  `installer_current_for_frozen_report=true`,
  `frozen_provenance_matches=true`, `installer_freshness_ok=true`다.
- 현재 PyInstaller 번들로 Inno Setup 1.4.2 설치본을 다시 생성했다.
  설치본은 2,108,818,576바이트이고 SHA-256은
  `febff440973091ffc681b293379388daea23078aa1899d0982c734f28b4c90a2`다.
  임시 사용자 경로에 무인 설치한 뒤 2,968개 파일, `TigerCapture.exe`,
  `TigerStudio.exe`, 실제 `Tiger Studio` 창을 확인하고 정상 제거했다.
  측정 시점에는 설치본이 모든 packaging input보다 새 버전이었고 임시
  설치 경로도 제거됐다.
  이 증거 이후 M22 Glass ROI 최적화가 추가됐으므로 다음 공개 설치본은
  최적화 소스를 포함해 다시 생성해야 한다.
- 무거운 프레임에서 100ms를 초과한 경과 시간을 버리던 재생 시계를
  최대 1초까지 따라잡도록 수정했다. 따라서 프레임 드롭이 있어도 playhead가
  슬로 모션처럼 뒤처지지 않으며, 낮은 frame rate 자체는 QA에서 그대로 실패한다.

M28 Complete v1. 소스와 frozen runtime의 backend, 시각 parity,
provenance 계약이 완료됐다. `Painterly Character Spot`은 M24의
provider-neutral post-render 효과를 사용하는 실제 편집 가능 템플릿이다.
갤러리는 8개 템플릿과 19개 variant를 검증하며 blocked capability는 없다.
배포 번들의 60초 지속 실행과 설치·실행·제거 회귀는 통과했고 소스의
24fps GPU 실시간 기준도 M22에서 통과했다. 새 M24 소스를 포함한 설치본
재생성은 다음 공개 배포 시 수행할 packaging 작업이며 기존 M28 frozen
증거의 실행 파일 provenance를 소급해 바꾸지 않는다.
4.59GB 번들과 2.11GB 설치본의 PyTorch/CUDA 중복 런타임 축소도 공개
배포 전 패키징 최적화 항목이다.

## 13. 착수 결정

첫 구현 묶음은 다음으로 제한한다.

1. M21 schema와 Film Grain/Gate Weave/Light Flicker
2. M21 Craft Inspector와 Action/MCP
3. M22 backdrop surface 계약
4. M22 Frosted/Glossy Tiger Glass MVP
5. Clean/Craft/Glass 실제 비교 QA

이 묶음은 현재 강한 AI·타이포·캐릭터 기능을 건드리지 않으면서도 결과의
인상을 가장 크게 바꾼다. 템플릿 수를 먼저 늘리거나 AI 프롬프트만 추가하지
않는다. AI 통합은 편집 가능한 수동 기능과 Action이 안정화된 M27에서 한다.

## 14. 제외 및 주장 경계

- Apple Liquid Glass의 픽셀 동일 복제 또는 공식 호환을 주장하지 않는다.
- After Effects plugin, `.aep`, Adobe effect 호환을 목표로 하지 않는다.
- 외부 생성형 비디오 모델의 결과를 편집 가능한 motion layer라고 주장하지
  않는다.
- Painter의 브러시 엔진과 프레임 드로잉 UI를 Motion Designer에 복제하지
  않는다.
- Unreal UMG에서 표현할 수 없는 효과를 조용히 누락하지 않는다.
