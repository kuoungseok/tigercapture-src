# Painter UI Figma 호환성 마일스톤

## 완료 정의

기능 하나는 다음 조건을 모두 만족해야 완료로 본다.

1. 고정 커밋과 라이선스가 기록된 실제 Figma REST 샘플 또는 최소 회귀 fixture가 있다.
2. import에서 원본 의미를 보존하고 지원하지 못한 데이터는 조용히 버리지 않는다.
3. Painter 전체 문서와 대표 artboard 실제 렌더가 통과한다.
4. JSON 저장/재로드 round-trip이 동일하다.
5. UMG 결과가 Native, Material, Baked, Blocked 중 하나로 명시된다.
6. 지원을 주장하는 UMG 결과는 Widget Blueprint 컴파일과 실제 Unreal 캡처로 증명한다.

## M0 측정 기반 — 완료

- 빠른 20개 + 대형 4개 REST 코퍼스
- 실제 Painter whole/artboard 렌더 smoke
- source geometry 대비 resolved geometry ratchet
- 이미지, 벡터, 폰트, UMG disposition 보고서

현재 ratchet은 24 cases, 10,759 measured objects, 0.5px 초과 236개, 1px 초과 0개, known blocker 제외 1,955개, unexpected 제외 0개다. 최대 edge drift는 1.0px다. 이전 기준선의 공통 측정 10,721개는 손실 없이 모두 유지했고 신규 측정 38개를 추가했다.

## M1 레이아웃 정확도 — 완료

완료된 항목:

- CENTER constraint authored offset
- hidden Auto Layout child 제외
- transformed Auto Layout snapshot geometry
- 상위 reflection/affine 감지와 명시 blocker
- 음수 item spacing import·렌더·Inspector·캔버스 편집
- `itemReverseZIndex`와 flow order 분리
- `strokesIncludedInLayout` 부모 inset·자식 stroke footprint 반영
- 숨은 Auto Layout subtree의 imported snapshot 보존과 0폭/0높이 source의 명시적 geometry blocker
- 일반 직교 `relativeTransform`을 중심 피벗 rect·degree 회전으로 복원하고 선의 1px 최소 extent 보정
- Figma `BASELINE` 교차축 정렬의 resolved sibling baseline을 복구하고, `SPACE_BETWEEN` overflow의 음수 effective gap을 재현
- overflow 시 signed main-axis remaining을 보존하고, 경계가 없는 Auto Layout 부모의 cross-axis 최소 bounds를 직접 flow 자식과 padding에서 보수적으로 역복구
- 부모·자식 affine가 상쇄되어 누적 항등이 된 노드는 raw rotation을 다시 적용하지 않고 소비된 변환 근거를 보존
- epsilon 이내 음수 local size를 0으로 정규화해 퇴화 선의 1px 편집 extent를 source AABB 중심에 맞추고, exact quarter turn·intrinsic line height 증거가 있는 legacy text만 radian rotation과 누락 local box를 역복구
- 다중 Figma page artboard 비겹침 배치

종료 조건:

- 측정 가능한 객체의 1px 초과 drift 0개
- unexpected geometry exclusion 0개 유지
- known affine blocker는 기준선 이하로 단조 감소

## M2 정적 비주얼 — 진행 중

완료된 항목:

- 실제 ALPHA/LUMINANCE mask 픽셀 합성
- vector `geometry=paths`, semantic primitive, SVG render fallback
- bundled Inter와 headless QA 폰트 경로
- imageRef archive 추출 및 누락 검증
- 그림자별 blend와 객체 blend의 캔버스·asset export 합성 경로 통일
- asset export의 CSS RGBA 해석과 버튼 그림자 중복 렌더 수정
- `individualStrokeWeights`, expanded stroke outline, INSIDE/OUTSIDE 마스크 렌더
- raw `VECTOR` 노드와 geometry-complete source를 분리하고, 경로 없는 snapshot을 `source_incomplete_vector_geometry`로 명시 보고
  - 24 case에서 geometry-complete 5 case / 4,815 nodes를 실제 Painter render·round-trip·UMG disposition으로 검증
  - UMG native vector brush는 없지만 schema 13의 검증된 보수적 subset은
    deterministic RGBA8 PNG로 물질화해 `Baked`로 전달한다. 안전 범위를
    벗어나거나 다른 gate가 남은 벡터만 명시적 `Blocked`로 유지해 빈 Native
    Image 생성을 방지한다.
- 최신 REST `NOISE`, `TEXTURE`, progressive layer/background blur의 필드·JSON·Figma plugin export 왕복 보존
  - Painter 균일 blur로 근사하지 않고 effect별 render blocker를 보고
  - UMG도 effect별 UI Material 또는 deterministic bake 사유로 명시 차단
- MIT 라이선스 OpenPencil의 실제 Figma Plugin API readback을 고정 commit과
  SHA-256으로 보존했다. Noise monotone/duotone/multitone와 Texture의 원본
  float 및 `noiseSizeVector`를 왕복 검증하며, REST 응답이나 픽셀 golden으로
  오인하지 않는다.
- 인증 Figma import는 visible Noise/Texture/progressive blur 노드를 찾아
  `/v1/images/:key` exact PNG를 100개 단위로 요청한다. 요청·URL 누락·다운로드
  실패는 각각 명시적 warning이며, 성공한 PNG에는 node id, source/render
  bounds, scale, API provenance를 함께 묶는다.
- schema 14는 exact Figma PNG가 있는 고정 크기·leaf·무회전 Rectangle의
  visible Noise 1개만 보수적으로 `Baked` 처리한다. source/render bounds와
  논리/픽셀 크기 일치, RGBA8, sRGB intent 0, CRC/청크 구조, source/effect/
  PNG/RGBA hash와 canonical JSON을 Python과 C++ 양쪽에서 fail-closed로
  검증한다. 다른 blocker가 하나라도 남으면 계속 `Blocked`다.
- schema 15는 같은 안전 원칙을 Texture 전용 계약으로 확장한다. 허용 범위는
  exact Figma PNG가 있는 고정 크기·leaf·무회전 Rectangle의 visible Texture
  1개뿐이다. `kind=static_figma_texture_png`, source schema
  `tigerstudio.umg.static_texture_bake.v1`, satisfied gate
  `figma_texture_effect_requires_ui_material_or_deterministic_bake`를 서로
  교차 검증하며, 이 subset 밖의 Texture는 계속 명시적 `Blocked`다.
- 최종 `Version 16 / 1.5.0` source 및 source-free bundle로 schema 14 WBP 생성·컴파일·
  재오픈, Texture2D serialized referencer, `FWidgetRenderer` 96×64 캡처를
  통과했다. 32×24 텍스처의 content/file/RGBA hash가 일치했고 alpha bounds
  `[23,17,54,40]`, RGB MAE `0`, alpha exact `1.0`, 외부 alpha 최대 `0`이다.
  이 캡처의 입력은 `synthetic_contract_fixture`이므로 UMG 운반 정확도
  증거이지 실제 Figma Noise 픽셀 golden은 아니다.
- 같은 `Version 16 / 1.5.0`으로 schema 15 Texture도 실제 WBP compile/save/
  reopen, Texture2D 참조와 `FWidgetRenderer` 픽셀 운반을 통과했다. alpha
  bounds `[23,17,54,40]`, RGB MAE `0`, alpha exact `1.0`, exact crop hash
  일치, 외부 alpha 최대 `0`, source/bundle/install DLL hash 일치를 확인했다.
  이 입력도 `synthetic_contract_fixture`이며 실제 Figma Texture visual
  golden으로 세지 않는다.
- progressive layer blur는 exact PNG의 render bounds가 layout box 밖으로
  확장될 수 있고 background blur는 live backdrop에 의존하므로, exact PNG가
  있어도 둘 다 명시적 `Blocked`다. hidden progressive effect는 왕복
  보존하지만 render 요청과 blocker를 만들지 않는다.
- image fill transform/crop의 Painter·Figma plugin·UMG parity 완료
  - REST `FILL`, `FIT`, `TILE`, `STRETCH`와 `imageTransform`, rotation,
    tile scale, opacity, filters를 보존한다. REST `STRETCH`의
    target-normalized → source-normalized affine는 Plugin API의 `CROP`으로
    왕복한다.
  - 축 정렬 affine는 Painter가 동일 source UV를 샘플링하고 TigerStudioUMG
    schema v11의 normalized `Crop`/Slate `UVRegion`으로 Native 변환한다.
    skew·reflection·image rotation은 UI Material 또는 bake blocker로 명시하며
    조용히 버리지 않는다.
  - 실제 Grida archive에서 IMAGE paint 218개(`STRETCH` 81, `FILL` 73,
    `TILE` 49, `FIT` 15), unique imageRef 127개, imageTransform 81개를
    검사했다. 8,903개 객체의 whole render와 선택 artboard 2개 render,
    document round-trip이 통과했다.
  - UE 5.8은 생성 WBP를 compile/reopen하고 Texture2D referencer를 확인한 뒤
    OS 창 캡처가 아닌 실제 `FWidgetRenderer` 내부 경로로 격리 UImage를
    260×140 PNG화한다. UV `(0.2, 0.15, 0.6, 0.7)` actual/expected 비교는
    luminance correlation `0.9164188061`, RGB MAE `28.2694`, luminance MAE
    `27.5024`로 gate를 통과했다. headless 첫 프레임의 기본 텍스처를
    오인하지 않도록 asset compilation, Texture2D resource update, mip
    streaming 완료 후 렌더하며 검정·투명·기본 텍스처 결과는 실패 처리한다.

남은 항목:

- 인증된 실제 Figma REST payload와 같은 노드의 Render API PNG를 묶은 Noise와
  Texture visual golden 확보
- Texture safe subset 확대와 progressive blur의 layout/backdrop-aware
  Material 또는 bake 경로

## M3 디자인 시스템 의미 — 완료

- Component/Instance/Variant override와 component property reference를
  왕복한다. 빠른 20개에서 source alias 112개를 active 95개 + recovery
  17개로 정확히 보존했다.
- Figma `boundVariables`를 alias 슬롯 단위로 보존한다. 빠른 20개는
  `145 = 145`, 대형 4개는 `3,252 = 3,252`, Grida auto-layout 단일
  샘플은 `3,231 = 객체 3,212 + 아트보드 19`이며 unclassified는 0개다.
  정의가 없는 alias는 token처럼 오인하지 않고 relink blocker로 남긴다.
- remote component localization/relink, rich text range 편집·왕복,
  prototype interaction 보존 경로와 회귀 테스트가 통과한다.
- prototype reaction은 빠른 20개에서 source reaction/action `18/18`을
  native `15/15` + recovery `3/3`, 대형 4개에서 `1/1`을 recovery
  `1/1`로 보존한다.

## M4 머터리얼·모션 — 지원 경로 완료

- schema 12 provider-neutral FlipbookAtlas 계약과 범위 검증 완료
- Painter adapter v10의 `content.flipbook` → texture resource →
  `Layer.Flipbook` 패키징 및 preflight 완료
- 임의 HLSL 입력 없이 고정 Custom HLSL + TextureSample UI Material 그래프 생성
- Motion keyframe의 deterministic atlas bake, 검증된 Painter 문서 부착,
  Motion Delivery의 `Bake Flipbook` 제품 UI 경로 구현
- ambient loop는 Material-ready, event-triggered global-time 결과는
  `flipbook_trigger_requires_dynamic_material_time_origin`으로 명시 차단
- UE 5.8 Editor/Game Development/Game Shipping 빌드, WBP compile/reopen,
  12-expression graph, material/texture 참조, shader compile failure 0건 검증
- 실제 2×2 atlas `FWidgetRenderer` D3D12 캡처가 정확한 256×256 크기,
  셀 위치·상호 구분, 모든 내부 픽셀의 RGB 채널 오차 2 이하와 alpha 255를
  통과했다. 셀별 MAE 0.667/1.333/0.667/0.667은 진단값일 뿐 통과 기준으로
  평균하지 않는다.

남은 항목:

- event 발생 시 Material time origin을 reset하는 Dynamic Material 경로
- blur, 고급 blend, 복합 mask의 UI Material 또는 deterministic bake 확대

## M5 UMG 실사용 — 지원 경로 완료

- Motion Designer와 Painter가 TigerStudioUMG 단일 backend로 Widget
  Blueprint를 생성한다.
- `D:\UE_5.8\Engine`에서 Editor Development, Game Development,
  Game Shipping 플러그인 빌드를 통과했다.
- image crop과 flipbook 핵심 reference를 실제 `FWidgetRenderer` 캡처로
  비교했다. flipbook은 WBP compile/save/reopen, 4개 Material brush와
  atlas 참조, 머터리얼별 12개 expression까지 재검증한다.
- 지원 경로의 Material compile failure는 0개다. schema 13의 보수적인 정적
  벡터 subset은 deterministic RGBA8 PNG로 물질화한 뒤 `Baked` provenance와
  typed ImageFill을 유지해 UImage로 생성한다. schema 14의 exact-PNG leaf
  Noise subset과 schema 15의 별도 exact-PNG leaf Texture subset도 동일한
  UImage 경로를 쓰되 레이아웃을 확장하지 않는다. 안전 조건을 벗어난
  벡터/Noise/Texture, progressive blur, event time origin과 나머지 고급
  appearance는 계속 명시적 Blocked로 남아 silent omission이 없다.
- 제품 UI는 선택된 image/rectangle과 stable Motion binding을 확인하고
  AppData의 traversal-safe 경로에 atlas/manifest를 저장한다. 동일 bake는
  재사용하고 문서는 1회만 revision을 올린다.

schema 13 정적 벡터 실엔진 증거:

- 현재 source와 source-free bundle은 `Version 16 / 1.5.0`으로 일치하며 UE 5.8
  Editor Development, Game Development, Game Shipping 빌드를 통과했다.
- 실제 Widget Blueprint는 Baked UImage 2개와 Texture2D 2개를 생성·저장하고
  재오픈했다. 텍스처는 sRGB, UI group, no mip, never stream, clamp 계약을
  만족했다.
- `FWidgetRenderer`는 gamma-disabled Slate와 명시적 sRGB render target을
  사용해 출력 변환을 한 번만 적용한다. 반투명 삼각형 RGB 최대 오차는
  채널별 2 이하, 회전 even-odd ring의 full-mask IoU는 `1.0`, hole alpha는
  `0`, 회전 가장자리 RGB 최대 오차도 채널별 2 이하이다.
- C++ preflight는 실제 PNG SHA-256, source hash, SVG 구조, RGBA8/sRGB PNG
  계약을 검사한다. Qt 재래스터화에 의한 픽셀 등가 검증은 Python 패키징
  경계가 담당한다. 이 신뢰 경계를 넘어선 입력은 지원으로 주장하지 않는다.

schema 14 exact Noise 실엔진 증거:

- 일반 문서와 정적 벡터 문서는 계속 schema 13으로 발행하고, 안전한 exact
  Noise Baked 레이어가 실제 포함된 문서만 schema 14로 승격한다.
- 최종 payload는 `tigerstudio_umg_schema14_materialized`와
  `umg_support_claimed=true`를 기록한다. 현재 source/bundle/install 1.5.0 DLL의
  SHA-256 일치도 QA 통과 조건이다.
- 실제 WBP의 Baked UImage 1개와 Texture2D 참조를 생성·저장·재오픈했고,
  `FWidgetRenderer` 결과는 패키지 PNG와 RGB/alpha가 픽셀 단위로 일치했다.
- 증거 입력은 합성 계약 fixture다. 실제 Figma Plugin API 샘플에는 아직
  동일 노드의 Figma PNG가 없으며 `not_a_figma_visual_golden`으로 표시한다.
  따라서 Figma Noise 시각 동등성은 주장하지 않는다.

schema 15 exact Texture 실엔진 증거:

- Noise 계약을 타입만 바꿔 재사용하지 않고
  `kind=static_figma_texture_png`, source
  `tigerstudio.umg.static_texture_bake.v1`, gate
  `figma_texture_effect_requires_ui_material_or_deterministic_bake`인 별도
  fail-closed 계약으로 검증한다.
- 실제 WBP의 Baked UImage와 Texture2D를 생성·저장·재오픈하고
  `FWidgetRenderer`로 검증했다. alpha bounds는 `[23,17,54,40]`, RGB MAE는
  `0`, alpha exact는 `1.0`, exact crop hash는 일치하며 외부 alpha 최대값은
  `0`이다. source/bundle/install DLL hash도 정확히 일치했다.
- 증거 입력은 `synthetic_contract_fixture`이며
  `not_a_figma_visual_golden`이다. 실제 Figma same-node Render API PNG가
  확보되기 전에는 Figma Texture 시각 동등성을 주장하지 않는다.
- 고정 leaf Rectangle, exact bounds/size, 단일 visible Texture 등 안전 조건을
  벗어나면 schema 15에서도 계속 명시적 `Blocked`다.

## M6 확장·릴리스 — 100-case 기준선 완료, 지속 확장 중

- release manifest는 정확히 100 case다. 이는 100개 독립 파일이 아니라
  라이선스와 commit이 고정된 24개 artifact / 10개 저장소에서 direct 22개와
  서로 겹치지 않는 selector 78개를 구성한 것이다.
- 최신 실행은 import/round-trip `100/100`, whole render `100/100`, focused
  artboard render `109/109`, 누락 이미지 `0`을 통과했다.
- 7,989개 UMG 대상은 `Native 2,131 / Material 240 / Baked 20 / Blocked
  5,598`로 정확히 한 번씩 분류됐다. UMG clean은 `3/100`이므로 이 결과를
  전체 Figma 또는 전체 UMG 호환으로 해석하지 않는다.
- `Baked 20`이 나온 selector 10개를 원본 archive 전체로 중복 확대하지 않고
  각 고정 subtree로 다시 로드해 감사했다. 실제 vector gate는 `109 → 89`,
  제거된 20건은 모두 PNG materialization과 hash 검증을 통과했고 최종
  `Baked 20`과 정확히 일치했다. 이 10개 workload의 최종 분류는
  `Native 343 / Material 25 / Baked 20 / Blocked 306`이다.
- 스키마 4~15의 raw 문서는 `Layers`, 각 layer row, 정확한 네 disposition,
  존재하는 `Resources`와 각 resource row를 legacy 기본값 적용 전에 검사한다.
  잘못된 값은 명시적 blocker가 되며 기본 Native로 흘러가지 않는다.
- M1 geometry ratchet은 24 case / 10,759 measured, 최대 drift `1px`, 1px 초과
  `0`, known exclusion `1,955`, unexpected exclusion `0`을 유지한다.
- exact100 non-render core 성능은 동일 workload/profile 기준
  `24,023,871,200ns → 21,392,059,600ns`, `-10.9549854729%`로 15% 회귀
  차단 gate를 통과했다.
- schema 15 Texture 통합 뒤 exact100 non-render를 다시 실행해 `100/100`, disposition
  `Native 2,131 / Material 240 / Baked 20 / Blocked 5,598`, UMG clean `3`이
  그대로임을 확인했다. matching exact effect PNG가 없는 기존 corpus에서
  Noise나 Texture를 임의로 지원 처리하지 않았다는 회귀 증거다.

최신 핵심 증거:

```text
debugCapture/painter_ui_figma_geometry_m1_final/figma_geometry_report.json
debugCapture/painter_ui_figma_document_corpus_release100_render_final/report.json
debugCapture/painter_ui_figma_document_corpus_release100_schema15_texture_exact_final/report.json
debugCapture/painter_ui_figma_m6_release100_perf_current_final/report.json
debugCapture/m6b_vector_static_bake_release100_baked_cases_selector_final/report.json
debugCapture/m6b_vector_static_bake_unreal_strict_v3e/qa_report.json
debugCapture/m6b_vector_static_bake_unreal_schema15_compat_final/qa_report.json
debugCapture/static_noise_ue_qa_plugin150/qa_report.json
debugCapture/static_texture_ue_qa/qa_report.json
debugCapture/painter_ui_designer/unreal_umg_schema13_final_v2/qa_report.json
debugCapture/painter_ui_designer/unreal_umg_flipbook_1_3_final_v2/qa_report.json
```

계속 진행할 확장 항목은 M2의 실제 Noise/Texture REST+same-node PNG golden,
Texture safe subset 확대, progressive blur의 layout/backdrop-aware Material 또는 bake,
event-triggered Material time origin, 고급 blend·복합 mask, remote component와
variable relink, rich text와 나머지 벡터/Boolean 안전 범위다. 이들은 현재도
Material/Baked/Blocked 중 실제 가능한 결과로만 보고하고 조용히 누락하지 않는다.
