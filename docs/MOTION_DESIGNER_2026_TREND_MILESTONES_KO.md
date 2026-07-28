# Motion Designer 2026 Trend Gap and Implementation Milestones

작성일: 2026-07-29  
상태: 기능 대조 완료, M21-M28 계획  
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
| M21 | Craft and Imperfection Style Stack | 아날로그 손맛을 재사용 가능한 효과 체계로 구현 | In progress: core stack |
| M22 | Dynamic Glass Material | 실시간 backdrop glass와 glossy motion 구현 | Planned |
| M23 | Mixed Media Craft Workspace | 종이·스캔·손그림·콜라주 제작 흐름 완성 | Planned |
| M24 | Painterly 2D/3D Look Development | PBR 위에 2D line/brush/toon 스타일 결합 | Planned |
| M25 | Stop-motion Timing and CGI | stepped timing, clay, miniature motion 구현 | Planned |
| M26 | Story and Platform Direction | 감정 arc와 플랫폼별 장면 구조 구현 | Planned |
| M27 | AI Style Director | 새 기능을 편집 가능한 AI 작업으로 통합 | Planned |
| M28 | Trend Template and Product QA | 실제 템플릿, 성능, 배포 증거 완성 | Planned |

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
- Subtle Film, Handmade, Archive Print 프리셋을 제공한다.
- 결정론적 Film Grain, Gate Weave, Light Flicker/Warmth가 Preview와
  Export의 공통 `effect_adapter` 경로를 사용한다.
- `Craft` Inspector에서 프리셋, 강도, grain, weave, flicker, locked seed를
  편집하고 기존 Craft 스택을 중복 없이 교체하거나 제거할 수 있다.
- `motion.craft.presets/get/apply/clear` Action/MCP를 제공한다.
- Unreal UMG 변환은 효과를 묵살하지 않고
  `effect_requires_bake:craft_style`로 명시한다.
- 남은 M21 범위는 Dust/Scratch, print misregistration, halation/VHS,
  durable texture attach/relink, loop-boundary QA와 실제 비교 샘플이다.

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

## 7. M23 - Mixed Media Craft Workspace

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
