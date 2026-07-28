# Motion Designer 전문 모션 그래픽 확장 마일스톤

작성일: 2026-07-27  
상태: 계획 승인, 구현 전  
기준: 기존 M0-M11 완료 범위와 M12 잔여 작업 이후의 제품 확장

## 1. 목표와 경계

이 계획은 After Effects를 기능 수로 복제하는 계획이 아니다. Tiger Studio가
이미 가진 영상 편집, AR/PBR, Live2D, Spine, MMD, VRM, Painter, PPT, Voice
Lab, Music Lab을 활용하면서 다음 결과를 만들 수 있게 하는 계획이다.

- 단순 위치·크기·회전 반복을 벗어난 캐릭터와 그래픽 변형
- 여러 장면과 중첩 컴포지션을 관리할 수 있는 장편 제작
- 전문적인 키프레임, 시간 변형, 텍스트와 벡터 애니메이션
- 동영상 로토, 키잉, 매트, 추적과 3D 합성
- 사용자가 재사용하고 AI가 안전하게 편집할 수 있는 템플릿

공식 Adobe 문서에서 비교 기준으로 확인한 기능:

- Puppet mesh와 Position/Starch/Overlap/Advanced/Bend pin:
  https://helpx.adobe.com/after-effects/desktop/animate-in-after-effects/animate-with-puppet-tools/animating-puppet-tools.html
- Object Matte와 시간축 전파:
  https://helpx.adobe.com/after-effects/desktop/roto-brush-and-refine-matte/roto-brush/object-matte.html
- Tracking, stabilization, face/point/mask/3D camera tracking:
  https://helpx.adobe.com/after-effects/desktop/animate-in-after-effects/track-motion/tracking-stabilizing-motion-cs5.html
- Shape layer와 vector path:
  https://helpx.adobe.com/after-effects/using/overview-shape-layers-paths-vector.html
- Motion Graphics Template와 replaceable media:
  https://helpx.adobe.com/in/after-effects/using/creating-motion-graphics-templates.html
- Advanced 3D renderer:
  https://helpx.adobe.com/after-effects/desktop/work-with-3d-composition/advanced-3d-renderer/advanced-3d-renderer.html

After Effects 완전 호환, `.aep` 읽기/쓰기, AE 플러그인 호환, 임의 Adobe
효과의 재현은 이 계획의 주장이 아니다.

## 2. 공통 완료 규칙

각 마일스톤은 다음 조건을 모두 만족해야 완료다.

- `.tgmotion` schema와 migration이 정의되어 있다.
- UI 조작이 `MotionDocumentController` 명령을 사용하고 undo/redo가 된다.
- 동일 기능을 Action/MCP에서 조회하고 변경할 수 있다.
- Preview, main-editor Motion Clip, Export가 같은 시점에 같은 결과를 만든다.
- 긴 프로젝트에서 캐시가 무한 증가하거나 UI thread를 장시간 막지 않는다.
- 실제 UI 캡처와 실제 출력 artifact가 있다.
- 실패하거나 지원하지 않는 입력은 조용히 누락하지 않고 preflight에 표시된다.
- 관련 기능이 UMG 문서에 들어갈 수 있다면 `TigerStudioUMG`도 같은 변경에서
  native, UI Material, bake 또는 blocked로 분류한다.

## 3. 전체 순서

| 순서 | 마일스톤 | 목적 | 상태 |
| --- | --- | --- | --- |
| M13 | Character Rigging Foundation | 전신 2D 컷아웃 리깅 | Complete |
| M14 | Puppet Mesh Deformation | 핀 기반 자연스러운 이미지 변형 | Complete |
| M15 | Composition and Animation Core | Precomp, Graph, Expression, Time | Complete |
| M16 | Typography and Vector Motion | 전문 텍스트·Shape 애니메이션 | Complete |
| M17 | Matte, Roto and Keying | 인물·물체 분리와 합성 | Complete |
| M18 | Tracking and Stabilization | 영상 움직임과 그래픽 결합 | In Progress |
| M19 | Unified 2.5D/3D Composition | 카메라·라이트·PBR 통합 | In Progress |
| M20 | Effects, Color, Templates and Render Scale | 제품 생태계와 대형 작업 | In Progress |

권장 의존 순서:

```text
M13 -> M14
M15 -> M16
M17 -> M18
M15 + M18 -> M19
M14 + M16 + M17 + M19 -> M20
```

M13과 M15는 병렬 진행할 수 있지만 schema/evaluator 수정은 같은 시점에
병합하지 않는다.

## 4. M13 - Character Rigging Foundation

목표: 현재 `arm_chain_v1` 팔 흔들기 MVP를 범용 전신 2D 컷아웃 리거로
확장한다.

2026-07-27 구현 상태:

- 완료: `tigerstudio.motion.rig.v1` 계약, stable rig/bone ID, parent-cycle 및
  layer/bone binding 검증, `.tgmotion` round-trip
- 완료: 17본 humanoid 생성기와 `Full Body Rig` 레이어 매핑 UI
- 완료: Canvas bone hierarchy overlay, 관절 rest-position drag, Rig Inspector의
  위치·회전 제한·translation/rotation/scale lock 편집과 undo/redo
- 완료: 제한각을 적용하는 2-bone IK solve, 바인딩 레이어의 공통 evaluator 반영
- 완료: pose 저장·적용·좌우 mirror와 `arm_wave`, `head_nod`,
  `walk_contact` keyframe preset
- 완료: `motion.rig.*` Action/MCP의 create/inspect/delete, bone CRUD,
  bind/unbind, IK, pose, motion preset
- 남음: 지속형 IK constraint와 pole/손발 고정, FK/IK 전환과 bake, 대칭 본
  편집 명령, Timeline bone channel, 3개 실제 전신 PNG 및 10분 cache QA

구현 범위:

- Canvas 위 Bone/Joint 편집 모드
- Root, pelvis, torso, neck, head, 양팔, 양다리 체인
- 레이어를 bone에 attach하고 기준 anchor와 rest pose 저장
- 회전 최소/최대, scale lock, translation lock
- 2-bone IK, pole target, 손·발 고정
- FK/IK 전환과 bake
- 좌우 대칭 bone 생성
- Pose 저장, 적용, 좌우 반전
- Head turn, nod, arm wave, breathe, idle, walk-contact 기본 포즈/모션
- 선택 bone, hierarchy, constraint를 Inspector와 Timeline에 표시

Action/MCP 초안:

- `motion.rig.create`
- `motion.rig.inspect`
- `motion.rig.bone.add/update/delete`
- `motion.rig.layer.bind`
- `motion.rig.constraint.set`
- `motion.rig.ik.solve`
- `motion.rig.pose.save/apply/mirror`
- `motion.rig.motion.apply`

완료 증거:

- 최소 3종 전신 투명 PNG 캐릭터
- 팔 인사, 고개 숙임, 앉기, 보행 접지 시퀀스
- 관절 제한 위반 0, parent cycle 0
- Preview/Export 픽셀 parity
- 10분 재생 중 bone/pose cache 증가 제한

제외:

- 메시 스킨 웨이트와 자유 변형은 M14
- Live2D Cubism 모델 제작은 포함하지 않음
- MMD/VRM skeleton 편집은 포함하지 않음

### 2026-07-27 M13 완료 기록

- 지속형 2-bone IK constraint를 target, pole, weight 애니메이션 채널로
  구현했다. 평가기는 문서를 변형하지 않고 매 프레임 FK/IK를 혼합한다.
- 손·발 end lock, constraint enable 기반 FK/IK 전환, IK-to-FK keyframe bake를
  Rig Inspector와 Action/MCP 양쪽에 연결했다.
- 선택 본의 좌우 대칭 생성·편집과 제한각/키프레임 반전을 구현했다.
- Timeline Graph Editor에 Bone Rotation과 Bone Translation 채널을 연결했다.
- 번들된 실제 캐릭터 파츠 3종(girl, Erikari, Celestial Circus)을 사용해
  10분 길이 리그를 평가·렌더하고 frame cache가 설정 용량을 넘지 않음을
  자동 검증한다.
- M13은 rigid cutout rigging 범위에서 완료다. mesh deformation, skin,
  cloth는 M14 범위다.

## 5. M14 - Puppet Mesh Deformation

### 2026-07-27 구현 상태: Complete

- 완료: `tigerstudio.motion.puppet_mesh.v1` mesh/pin 직렬화 계약과 검증
- 완료: regular grid 삼각화와 stable vertex/pin ID
- 완료: Position, Bend, Starch pin 가중 변형과 triangle flip/degenerate 진단
- 완료: Puppet Inspector, Canvas pin drag, Timeline Pin Position/Bend channel
- 완료: M13 rig bone을 pin translation/rotation driver로 연결
- 완료: Action/MCP CRUD와 Preview/Export 공통 piecewise-affine alpha warp
- 완료: source alpha 기반 투명 삼각형 제거, Overlap pin 거리 감쇠 depth 정렬,
  triangle inversion을 rest mesh 방향으로 되돌리는 결정론적 안정화
- 완료: 번들 Celestial Circus 실제 투명 파츠 3시점 렌더와
  100 pin / 20,000 triangle stress 계약
- 완료: alpha 경계 셀만 세분화하는 Delaunay local subdivision과
  flip/과도한 edge stretch를 문제 삼각형 주변에서만 완화하는 tear repair
- 완료: CPU pin solver + OpenGL textured mesh rasterizer Preview 경로,
  unsupported effect/matte에 대한 Painter fallback, 정적 texture cache
- 완료: 실제 OpenGL 컨텍스트에서 476 triangle GPU 캡처, GL error 0,
  texture upload 1회 유지, CPU 기준 평균 RGB 오차 1.42
- 완료: 10분/30fps 18,001-frame deformation 평가에서 unsafe/non-finite/
  cycle mismatch 0, Windows working-set 증가 52KB

목표: 잘라낸 관절 조각을 딱딱하게 돌리는 수준을 넘어 하나의 이미지나
부드러운 파츠를 메시로 변형한다.

구현 범위:

- 알파 또는 닫힌 path에서 삼각형 mesh 생성
- Position, Bend, Starch, Overlap pin
- pin 위치·회전·스케일·강도·영향 반경
- 자동 keyframe과 Canvas motion path
- mesh density와 adaptive refinement
- self-intersection, triangle flip, tear 진단
- overlap depth와 pin별 앞뒤 순서
- GPU mesh deformation Preview
- CPU deterministic Export fallback 또는 동일 GPU export
- M13 bone을 Puppet pin driver로 연결

Action/MCP 초안:

- `motion.puppet.create`
- `motion.puppet.mesh.rebuild`
- `motion.puppet.pin.add/update/delete`
- `motion.puppet.pin.keyframe`
- `motion.puppet.bind.rig`
- `motion.puppet.diagnostics`

### 2026-07-27 M14 완료 기록

- alpha boundary Delaunay 메시 생성기는 투명 영역 전체를 과도하게
  세분화하지 않고 mixed-alpha cell의 edge/center에만 정점을 추가한다.
- local tear repair는 정상 삼각형을 유지하면서 flip, degenerate, 과도한
  edge stretch가 발생한 인접 정점만 안전 pose 쪽으로 완화한다.
- Preview는 pin과 rig driver를 CPU에서 결정론적으로 평가하고, 변형된
  position/UV mesh를 OpenGL VBO로 매 프레임 갱신한다. source texture는
  파일·파라미터 signature로 캐시한다.
- Export는 기존 CPU piecewise-affine 경로를 유지해 headless와 배치 렌더의
  결정성을 보장한다.
- GPU 증거는 `tools/qa_motion_gpu_puppet.py`, 장시간 증거는
  `tools/qa_motion_m14_long_playback.py`로 재생성한다.

완료 증거:

- 머리카락, 치마, 팔, 꼬리, 천 배너 샘플
- 100개 pin, 20k triangle stress
- triangle flip과 alpha hole 회귀 corpus
- Preview/Export 최대 픽셀 오차 기준 기록

## 6. M15 - Composition and Animation Core

### 2026-07-27 구현 상태: Complete

- 완료: self-contained `tigerstudio.motion.precomp.v1` 중첩 composition 계약
- 완료: Layers 다중 선택 Pre-compose, 더블클릭 open-in-place, Parent 복귀,
  중첩 편집 중 root save/autosave 보존
- 완료: Preview/Export 공통 recursive render와 per-instance child override
- 완료: `motion.precomp.create/inspect/override.set/refresh` Action/MCP
- 완료: Source Time keyframe, Linear/Reverse/Freeze/Speed Ramp preset,
  Timeline Source Time channel
- 완료: Graph Editor Value/Speed 표시와 Auto/Linear/Hold tangent mutation,
  `motion.graph.tangent.update`
- 완료: published property와 per-instance animated value, Controller Null
  property link, value/vector 거리 기반 roving keyframe
- 완료: 3단 nested render, 100 precomp instance, 500 undo 자동 QA
- 완료: Graph 위 in/out Bezier handle 표시와 broken tangent 직접 drag
- 완료: Timeline expression pick-whip UI와 dependency/cycle validation
- 완료: Off/Frame Mix/Optical Flow 선택, frame-mix 공통 렌더 경로와
  optical-flow backend availability/fallback preflight

목표: 짧은 단일 composition 중심 구조를 장편·중첩 제작 구조로 확장한다.

구현 범위:

- Pre-compose, open-in-place, breadcrumb
- nested composition instance와 per-instance override
- published property group과 Controller/Null layer
- Graph Editor의 Value/Speed mode
- Bezier tangent, broken/continuous/auto tangent
- roving keyframe, temporal/spatial interpolation
- 여러 곡선 normalize, solo, filter, snap
- expression pick-whip, dependency graph, cycle/error 표시
- expression 결과와 원본 curve 동시 표시
- Time Remap, freeze, reverse, hold, speed ramp
- frame blending과 optical-flow backend preflight
- per-layer motion blur와 shutter angle/phase

Action/MCP 초안:

- `motion.precomp.create/open/replace`
- `motion.property.publish`
- `motion.controller.create/link`
- `motion.graph.keyframe.update`
- `motion.graph.tangent.update`
- `motion.expression.link/validate`
- `motion.time_remap.set/bake`

완료 증거:

- 3단 nested composition, 100 instance override
- 60초 speed-ramp와 reverse/freeze 출력
- expression cycle이 UI와 Action에서 같은 오류 반환
- Graph Editor 조작 undo/redo 500회

### 2026-07-27 M15 완료 회귀 기록

- precomposition, 100-instance/500-undo stress, time remap, frame blending,
  expression/cycle, controller, evaluator 핵심 테스트 29개를 재실행해 모두
  통과했다.
- Optical Flow는 설치 여부를 감지하더라도 현재 vector-warp backend가
  비활성화된 경우 Frame Mix로 명시적으로 폴백한다. 조용한 누락이나
  지원 과장은 하지 않는다.

## 7. M16 - Typography and Vector Motion

목표: 텍스트와 Shape가 단순 transform preset을 넘어 모션 디자인의 주요
제작 도구가 되게 한다.

구현 범위:

- Text animator stack과 Range Selector
- character, word, line 단위 selector
- start/end/offset, random, reverse, ping-pong, smoothness
- per-glyph position, scale, rotation, opacity, fill, tracking, blur
- text-on-path와 per-character 3D 준비 데이터
- Trim Paths, Offset Paths, Merge Paths
- Repeater의 per-copy transform, color, opacity
- Gradient Fill/Stroke, dash, taper, variable width
- path morph topology 검사와 correspondence 보정
- Illustrator/SVG path 교환 범위 명시

Action/MCP 초안:

- `motion.text.animator.*`
- `motion.text.selector.*`
- `motion.shape.operator.*`
- `motion.shape.stroke.*`
- `motion.path.morph.*`

완료 증거:

- kinetic typography 5종
- logo reveal 5종
- infographic path animation 3종
- 4K scaling에서 vector edge 품질 검사

완료 기록:

- `tools/qa_motion_m16_typography_vector.py`가 5+5+3 실제 렌더 샘플,
  contact sheet, 3840x2160 edge 검사를 생성한다.
- `motion.typography.character_3d.prepare`는 M19 렌더러용 글자별 source
  span, depth, bevel, 3축 transform 준비 데이터를 저장하며 M16에서 3D
  렌더링된다고 주장하지 않는다.
- SVG still preflight와 Tiger UMG schema v3는 지원하지 않는 고급
  Text/Shape 기능을 조용히 누락하지 않고 bake/block 사유를 반환한다.

## 8. M17 - Matte, Roto and Keying

상태: **Complete (2026-07-27)**

구현 및 증거:

- `motion.matte.object.select/refine/propagate/correction.set/freeze/assign`
  Action으로 선택, 정제, 전파, 수동 보정 키, 캐시 고정, 트랙 매트 할당을
  자동화할 수 있다.
- 포인트/플래너 추적 캐시는 보정 키를 보간하며, 승인 후 Freeze하면 재전파가
  기존 결과를 덮어쓰지 못한다. 인스펙터에서도 Freeze 상태를 표시하고 제어한다.
- Chroma/Luma/Difference Key는 choke, feather, despill과 함께 공통
  Preview/Export effect adapter에서 처리된다.
- Add/Subtract/Intersect/Exclude 외에 Garbage/Holdout 매트 모드를 제공하며
  Alpha/Luma/Inverse 트랙 매트는 여러 대상 레이어가 동일 매트 레이어를 참조할
  수 있다.
- BiRefNet/SAM 계열의 소프트 알파를 로컬 edge-aware 매팅이 이진화하지 않도록
  보존하여 머리카락, 반투명 재질, 모션 블러 경계를 유지한다.
- `tools/qa_motion_m17_matte_keying.py`가 green/blue screen 10종
  (hair, fast arm, motion blur, translucent 포함)을 렌더하고 IoU, edge spill,
  temporal flicker, soft-alpha MAE를 측정한다. 현재 증거는
  `debugCapture/motion_designer/m17_matte_keying`에 생성된다.
- Moving-object removal은 기존 분해/인페인트 경로의 experimental 기능으로만
  유지하며 범용 비디오 오브젝트 제거 성능을 주장하지 않는다.

목표: 이미지 한 장 누끼를 넘어 동영상의 인물·물체를 시간축에서 안정적으로
분리하고 합성한다.

구현 범위:

- object selection, add/subtract brush, refine edge
- mask propagation, correction keyframe, freeze/cache
- 머리카락과 반투명 경계 보정
- chroma/luma/difference key
- garbage matte와 holdout matte
- edge clean, choke, feather, despill
- 임의 Alpha/Luma/Inverse track matte
- 한 matte를 여러 레이어·효과에서 참조
- moving object removal은 별도 experimental 단계로 시작

Action/MCP 초안:

- `motion.matte.object.select/refine/propagate/freeze`
- `motion.key.create/update`
- `motion.matte.assign`
- `motion.matte.diagnostics`

완료 증거:

- 머리카락, 빠른 팔, 모션 블러, 반투명 소재 corpus
- green/blue screen 10종
- matte temporal flicker와 white halo 자동 측정

## 9. M18 - Tracking and Stabilization

상태: **In Progress (2026-07-28)**

현재 구현:

- Composition에 저장되는 `tigerstudio.motion.track_asset.v1` 공용 트랙
  자산과 Point/Multi-point/Planar/Mask/Face 종류를 추가했다.
- `motion.track.point/multi_point/planar/mask/face/create/apply`,
  `motion.stabilize.create`, `motion.track.diagnostics`,
  `motion.camera_solve.create` Action을 제공한다.
- 동일 트랙을 레이어 Position/Scale/Rotation에 정방향으로 bake하거나
  역변환하여 안정화할 수 있다.
- 트랙은 이펙트 point와 Puppet pin에도 직접 bake할 수 있으며 AR/PBR
  레이어는 동일 layer transform 경로를 사용한다. Planar 트랙은 기존
  Corner Pin 효과의 네 꼭짓점에 affine 결과를 bake할 수 있다.
- `motion.track.face`는 기존 VTuber face-video extractor를 재사용하여
  MediaPipe/OpenCV 결과를 위치·크기·roll 트랙으로 변환한다. UI와 Action은
  트림된 source-in, layer in/out, time-scale을 Composition 시간으로
  변환할 수 있다.
- Tracking 인스펙터가 평균 신뢰도, 가림 샘플, 재획득 횟수, 소스 리비전
  일치 상태와 drift 검토 사유를 표시하며 Attach/Stabilize/Pin/Relink를
  실행한다. 선택 비디오 레이어에서 Point/Planar/Face 분석을 백그라운드로
  실행해 공용 트랙 자산을 생성할 수 있다.
- 트랙 자산 중복/손상과 삭제된 트랙 참조는 Composition validation에서
  차단된다.
- 추적 시작점의 무특징/검은 인트로는 최대 1.5초 동안 첫 유효 프레임을
  탐색하고 identity hold하며 합성 회귀 테스트가 이 동작과 이후 이동
  복구를 검증한다. `tools/qa_motion_m18_real_tracking.py`의 현재
  로컬 실영상 감사에서는 11종 중 10종 생성, 9종 품질 통과이며 20종 완료
  기준에는 9종이 부족하다.
- Point tracker는 완전 가림 중 마지막 유효 속도를 최대 0.5초까지만
  예측하고 특징점 재검출 후 실제 광학 흐름으로 복귀한다. 합성 가림
  회귀 테스트가 재획득과 최종 이동 복구를 검증하며 예측 프레임 수는
  Tracking 진단에 표시된다.
- Point optical-flow의 단일 분석 스텝이 타깃 대각선의 4%를 넘으면
  이상치로 거부한다. 실제 LA 석양 실패 클립의 700px 오대응은 0px
  hold로 차단됐고 클립은 낮은 신뢰도/가림 때문에 계속 Review로 남는다.
- 현재 Camera Solve는 `manual_depth_plane_v1` 보조 평면/내부 파라미터
  계약이다. 자동 3D matchmove로 주장하지 않는다.

남은 완료 조건:

- 눈·입 등 얼굴 부위별 landmark 트랙과 타깃
- perspective/homography, 장기/비선형 occlusion 재획득 강화
- 실제 영상 20종 drift corpus와 3D camera solve 공유 증거

목표: 그래픽, 마스크, 효과, 3D 객체를 영상 움직임에 신뢰성 있게 붙인다.

구현 범위:

- single/multi-point tracker
- mask tracker와 planar tracker
- face landmark와 부위별 tracking
- tracking 결과를 Null, layer, effect point, Puppet pin에 적용
- object stabilization과 camera shake stabilization
- track confidence, drift, occlusion, reacquire UI
- 3D camera solve, ground plane, origin, scale
- tracking cache relink와 source revision 검증

Action/MCP 초안:

- `motion.track.point/planar/mask/face`
- `motion.track.apply`
- `motion.stabilize.create`
- `motion.camera_solve.create`
- `motion.track.diagnostics`

완료 증거:

- translation, scale, rotation, perspective, occlusion corpus
- 실제 영상 20종의 drift 측정
- AR/PBR 배치와 3D camera solve 공유

## 10. M19 - Unified 2.5D/3D Composition

상태: **In Progress (2026-07-28)**

목표: 별도 AR/PBR 뷰어에서 끝나지 않고 Motion layer, text, shape, camera,
light, 3D model이 같은 composition 공간에서 움직이게 한다.

2026-07-27 구현 상태:

- 일반 2D 레이어를 명시적인 3D 카드로 전환하는
  `motion.3d.layer.enable` 액션과 Inspector 컨트롤을 추가했다. Depth Z,
  X/Y 회전, 카메라 제외, cast/receive shadow 의도를 같은 메타데이터에
  보존한다.
- 3D 카드 X/Y 회전은 현재 공통 2D affine renderer에서 축별
  foreshortening으로 평가되며 Preview와 Export가 같은 행렬을 사용한다.
  이는 완전한 perspective homography나 실제 mesh 변형이 아니다.
- Motion camera는 `perspective`와 `orthographic` projection 및
  `orthographic_size`를 공유한다. 직교 모드에서 2.5D 레이어 크기는
  Depth Z와 독립적이며, AR/PBR 모델도 같은 카메라의 거리 독립 framing
  값을 사용한다.
- 기존 `motion.layer.depth.set`, `motion.camera.add/update`,
  `motion.light.add/update`, `motion.ar_pbr.add/set_material` 계약은
  호환 유지된다.
- `Receive shadows`가 켜진 하위 3D 카드에는 상위 `Cast shadows` 카드의
  알파 실루엣을 깊이 차와 Directional Light 방향/고도에 따라 투영한다.
  강도와 softness를 Inspector와 Action에서 조절하며 Preview와 Export가
  같은 receiver-clipped 결과를 사용한다.
- Motion의 AR/PBR 경로는 활성 직접광을 최대 3개까지 평가한다. 첫
  Directional Light를 그림자 key light로 사용하고, 나머지
  Directional/Point/Spot 중 최대 2개를 그림자 없는 보조광으로 누적한다.
  Point는 위치와 range 감쇠, Spot은 inner/outer cone 감쇠를 사용하며
  OpenGL Preview와 packet Export가 같은 정규화된 조명 payload를 사용한다.
- 현재 2.5D 카드 그림자는 Qt raster Render Graph에서 계산한다. GPU
  실시간 shadow map이 아니며 여러 높이의 연속 surface를 지원하지 않는다.
  보조광에는 shadow map이 없으므로 무제한 다중 라이트나 모든 라이트의
  self/cast shadow를 지원한다고 주장하지 않는다.

구현 범위:

- 2D/2.5D/3D layer 전환
- perspective/orthographic camera
- camera rig, depth of field, focus target
- environment, directional, spot, point light
- shadow cast/receive와 contact shadow
- GLTF/GLB/OBJ/FBX import 범위와 animation clip
- PBR/IBL material과 AR/PBR Surface 설정 재사용
- 3D model camera/light extraction
- 3D text/shape extrusion
- video depth occlusion과 camera solve 연결

Action/MCP 초안:

- `motion.3d.layer.enable`
- `motion.3d.camera.*`
- `motion.3d.light.*`
- `motion.3d.model.import/animation.set`
- `motion.3d.material.update`

완료 증거:

- 2D text + GLTF + video depth 합성
- 다중 라이트와 self/cast shadow
- Viewer/Main preview/Export 동일 camera와 material
- software renderer 0인 실시간 QA

## 11. M20 - Effects, Color, Templates and Render Scale

상태: **In Progress (2026-07-27)**

목표: 앞 단계 기능을 제품 수준의 효과, 템플릿, 대형 프로젝트와 배포
워크플로로 묶는다.

현재 구현:

- Effects/Masks Inspector의 숫자 파라미터에 현재 시간 키프레임 다이아몬드
- layer in/source time/time scale/reverse/time remap을 반영한 로컬 시간 기록
- 스크럽 시 AnimatedProperty 평가값 표시와 기존 곡선을 보존하는 값 수정
- `motion.effect.keyframe.set/delete`,
  `motion.mask.keyframe.set/delete` Action/MCP 동등성
- 삭제 액션의 destructive confirmation 계약과 UI/Action 회귀 테스트
- Adjustment Layer의 기존 `all_below` 호환 모드와
  `selected_layers_below` 체크 대상 모드
- 선택한 아래 렌더 레이어의 독립 surface에만 효과를 적용하는
  Preview/Export 공통 렌더 경로
- 잘못된 ID, 비렌더링 레이어, 자기 자신, 위쪽 레이어를 제거하는 범위 검증과
  `motion.adjustment.scope.get/set` Action/MCP
- 일반 레이어의 자체 effect stack이 Preview/Export surface에 실제 적용되는
  공통 경로와 scoped adjustment와의 명시적 적용 순서
- Group 레이어의 effect stack을 전체 renderable descendant 또는 선택한
  descendant에만 적용하는 `effect_group` 계약과 Effects Inspector
- `motion.effect_group.scope.get/set` Action/MCP, invalid/outside target 필터,
  GPU-only backend의 명시적 shared-raster fallback
- Drop Shadow, Light Sweep, 다중 옥타브 Fractal Noise, Posterize 효과와
  Effects Inspector 기본값/애니메이션 파라미터
- 동일 seed/time에서 동일 픽셀을 생성하고 시간 변화에 따라 전개되는
  결정론적 Fractal Noise Preview/Export 경로
- 효과가 활성화된 Vector/Typography GPU 패킷의 명시적 shared-raster
  fallback. 효과를 건너뛴 GPU 프레임은 허용하지 않음
- 새 효과 4종의 범용 `motion.effect.*` Action/MCP 직렬화 검증
- Unreal UMG 변환 시 Drop Shadow, Light Sweep, Fractal Noise,
  Posterize를 자동 누락하지 않고 deterministic bake 필요로 차단하는
  preflight 계약
- 메인 편집기와 공유하는 `app/color_runtime.py` 기반 ACES/OCIO display
  transform. 기본 sRGB 프로젝트는 무변환이며 ACES는 OCIO 우선,
  미설치 시 명시적 ACES-fitted fallback
- OpenColorIO 2.5.2 런타임과 버전 고정 내장 Studio/CG ACES 1.3 구성 선택.
  ACES 최초 선택 시 안정적인 Studio ACES 1.3 구성을 자동 지정하며 외부
  `.ocio` 파일도 동일 계약으로 지원
- `tools/qa_color_ocio_parity.py` 실제 색상 차트/17-cube 검증:
  Preview와 Export LUT 4,913 격자 샘플의 최대 byte 오차 0
- frozen `TigerStudio.exe --color-runtime-probe` 검증: OpenColorIO 2.5.2,
  내장 구성 8개, Studio ACES 1.3 픽셀/LUT 변환, 종료 코드 0
- 실제 H.265 Main 10 Rec.2020 PQ 24-frame 색상 차트 왕복 검증:
  평균 byte 오차 2.18, 평균 Delta E 76 1.05, 최대 Delta E 76 1.93,
  `bt2020nc/bt2020/smpte2084` 메타데이터 일치
- 메인 편집기의 Video+Motion 최종 합성 뒤 한 번만 실행되는 Preview
  transform과 OpenGL/QImage 동일 픽셀 경계
- Motion standalone Preview/Export의 alpha-safe 동일 transform,
  H.265 10-bit Rec.2020 PQ/HLG 출력 및 FFmpeg `zscale` 변환
- Motion Delivery 패널의 Working/Output/Transfer/View/OCIO 선택과
  `motion.color.get/set` Action/MCP 동등성
- 비기본 색상 관리가 UMG에서 조용히 유실되지 않도록
  `motion_feature_requires_bake:color_management` preflight 차단

구현 범위:

- effect property 전체 keyframe과 effect mask
- adjustment layer와 scoped effect group
- distortion, glow, blur, light, noise, stylize 핵심 효과 보강
- GPU shader effect contribution과 실패 격리
- 더 넓은 카메라/로그/고휘도 corpus와 장시간 HDR 인코딩 검증
- Essential Properties 수준 published control group
- replaceable image/video/character/3D/audio slot
- nested composition override와 template validation
- template bundle collect/relink/license metadata
- Composition Profiler
- proxy, disk cache, cache budget와 purge UI
- background render, resumable sequence, render worker 준비

Action/MCP 초안:

- `motion.effect.property.*`
- `motion.color.project.*`
- `motion.template.control.*`
- `motion.template.media.replace`
- `motion.profiler.capture`
- `motion.cache.inspect/purge/budget.set`

완료 증거:

- M13-M19 기능을 사용하는 15초 광고, 60초 교육, UI interaction template
- 1,000 layer, 10,000 keyframe, nested composition stress
- cache budget 초과와 recovery 검증
- packaged template을 새 프로젝트에서 설치·교체·출력

## 12. 우선 착수 순서

첫 구현 묶음은 다음 순서로 제한한다.

1. M13 rig schema, bone hierarchy, Canvas bone overlay
2. M13 two-bone IK와 joint constraint
3. M13 pose 저장과 arm/head/leg motion preset
4. M14 alpha mesh 생성과 Position pin
5. M14 Starch/Bend/Overlap pin
6. M15 Pre-compose schema와 nested evaluator
7. M15 Graph Editor tangent와 Time Remap
8. M16 Text Range Selector와 Trim Paths

템플릿 수를 먼저 늘리거나 AI 프롬프트를 먼저 붙이지 않는다. AI는 위
기능이 Action/MCP로 안정화된 뒤 해당 액션을 조합한다.

## 13. 별도 추적 항목

- Painter에서 Motion Actor를 배치하는 후속 작업:
  `docs/MOTION_PAINTER_INTEGRATION_TODO_KO.md`
- Unreal UMG 변환:
  `resources/unreal_plugins/UMG/TigerStudioUMG`
- M12 runtime plugin host는 본 계획과 별도지만 M20 effect contribution 전에
  완료해야 한다.
