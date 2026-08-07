# Painter UI Figma 호환성 코퍼스

## 목적

Painter UI의 Figma 호환성은 합성 fixture 몇 개만으로 판단하지 않는다. 공개 저장소의 실제 Figma REST 응답을 고정 커밋과 SHA-256으로 내려받고 다음 경로를 반복 검증한다.

1. Figma file / nodes / 단독 REST node import
2. Painter UI 문서 JSON round-trip
3. 선택 실행 시 Painter → Figma plugin exchange package round-trip
4. 모든 artboard의 Painter → TigerStudioUMG preflight
5. 이미지가 동봉된 archive의 `imageRef` → 로컬 이미지 → UMG texture resource contract

5번은 UMG 문서에 들어갈 텍스처 소스와 해시를 검증하는 단계다. 실제 Unreal `Texture2D` `.uasset` 생성, Widget Blueprint 컴파일, Unreal 캡처까지 증명하는 단계는 아니다.

파이프라인 통과와 UMG clean은 서로 다른 지표다. import가 성공해도 UMG에서 Material, Bake, Blocked가 필요하면 보고서에 그대로 남긴다.

## 코퍼스 등급

### 빠른 코퍼스

`qa_corpus/painter_ui_figma_documents/manifest.json`

- 공개 테스트 case 20개
- 9개 저장소
- GET file, GET nodes, 단독 REST node fragment 포함
- 텍스트, rich text, linear gradient, Auto Layout, component/component set/instance, mask, vector, effect, prototype 포함
- PR 및 일반 로컬 회귀 테스트용

### 대형/야간 코퍼스

`qa_corpus/painter_ui_figma_documents/nightly_manifest.json`

- 공개 테스트 case 4개
- 이미지 474개가 동봉된 Auto Layout Playground archive
- Radix Icons component/vector/boolean archive
- stroke geometry 및 self-intersecting vector 최소 fixture
- 성능, 실제 이미지 자원, 대규모 UMG preflight용

Figma 공식 `figma/plugin-samples`는 manifest 32개를 `external/tools/figma-plugin-samples`에 checkout해 둔다. 현재 로컬 자동 검증 대상은 code sample 3개와 UI sample 3개, 총 6개다. 이것은 Figma Desktop에서 플러그인을 실행한 결과가 아니라 로컬 호환 런타임 검증이다. REST 문서 코퍼스와 Plugin API 실행 코퍼스는 의미가 다르므로 보고서도 분리한다.

## 저장 경계

실제 외부 파일은 다음 durable 경로에 내려받는다.

```text
external/assets/figma/compat_corpus
```

이 경로는 Git에 넣지 않는다. 소스 미디어이므로 `debugCapture`에 저장하지 않는다. Git에는 다음만 추적한다.

- 고정 commit URL
- 원 저장소와 원본 경로
- 라이선스 URL과 attribution metadata
- CC BY 자료의 제작자, 원본 URL, 고정 커밋의 라이선스 근거, 변경 고지
- 예상 byte 수와 SHA-256
- 기대 source/import feature
- downloader, QA runner, 회귀 테스트

생성 보고서와 Figma plugin package는 재생성 가능하므로 `debugCapture`에 둔다.

## 실행

빠른 코퍼스 다운로드:

```powershell
.\.venv\Scripts\python.exe tools\fetch_painter_ui_figma_document_corpus.py
```

빠른 코퍼스 QA:

```powershell
.\.venv\Scripts\python.exe tools\qa_painter_ui_figma_document_corpus.py
```

실제 Painter 전체/아트보드 렌더 QA:

```powershell
.\.venv\Scripts\python.exe tools\qa_painter_ui_figma_document_corpus.py `
  --render-smoke --render-artboard-count 4
```

source geometry 대비 최종 constraint/Auto Layout geometry 측정:

```powershell
.\.venv\Scripts\python.exe tools\qa_painter_ui_figma_geometry.py `
  --assets-root external\assets\figma\compat_corpus `
  --max-drift-px 1 `
  --max-large-drift-count 0 `
  --max-known-blocked-excluded-count 1955 `
  --max-unexpected-excluded-count 0
```

대형 코퍼스 다운로드:

```powershell
.\.venv\Scripts\python.exe tools\fetch_painter_ui_figma_document_corpus.py `
  --manifest qa_corpus\painter_ui_figma_documents\nightly_manifest.json
```

대형 코퍼스 QA:

```powershell
.\.venv\Scripts\python.exe tools\qa_painter_ui_figma_document_corpus.py `
  --manifest qa_corpus\painter_ui_figma_documents\nightly_manifest.json `
  --output debugCapture\painter_ui_figma_document_corpus_nightly
```

선택 case만 실행하려면 `--case <case-id>`를 반복해서 지정한다. 기본 QA는 plugin exchange package를 만들지 않는다. Painter → Figma plugin package까지 파일로 만들고 round-trip을 검증하려면 `--write-packages`, 모든 UMG blocker를 실패로 취급하는 별도 검증에는 `--require-umg-clean`을 사용한다. 사용한 옵션은 report의 `options`에도 기록한다.

## 보고서 해석

`passed`는 다음을 뜻한다.

- 파일과 SHA가 맞음
- JSON/archive를 읽을 수 있음
- import 문서 validation이 성공함
- 기대한 source feature가 실제 샘플에 있음
- 보존 대상으로 지정한 feature가 import 결과에 최소 1개 이상 남음
- JSON round-trip이 동일함
- 모든 artboard에서 UMG preflight가 예외 없이 실행됨

`umg.clean`은 그 case의 UMG blocker와 preflight error가 모두 0이라는 별도 상태다. 모든 레이어가 Native라는 뜻은 아니며, 검증을 통과한 Material도 포함될 수 있다. `Blocked`가 존재하는 case도 corpus pipeline은 통과할 수 있다. 이것은 blocker를 누락하지 않고 안정적으로 분류하는지 검증하기 위해서다.

주요 보고서:

```text
debugCapture/painter_ui_figma_document_corpus/report.json
debugCapture/painter_ui_figma_document_corpus_nightly/report.json
```

## 현재 로컬 기준선 (2026-08-05)

위에 링크한 manifest별 non-render 보고서의 현재 값은 다음과 같다. 전체
render 승인값은 아래 exact100 release 기준선에서 별도로 관리한다.

- 빠른 REST 코퍼스: pipeline 14/14, UMG clean 1/14
  - UMG disposition: Native 252 / Material 4 / Baked 0 / Blocked 152
- 대형/야간 REST 코퍼스: pipeline 4/4, UMG clean 0/4
  - UMG disposition: Native 4,038 / Material 501 / Baked 0 / Blocked 7,693
- Auto Layout Playground: 123 artboards / 8,903 objects
  - 원본 변수 바인딩 2,966 nodes / 3,231 aliases를 복구 메타데이터까지 포함해 전부 보존
  - archive 이미지 474개 추출, 실제 참조 리소스 127개, 누락 0개
  - 음수 spacing, 상위 reflection, 숨은 subtree snapshot, baseline/overflow, missing-parent bounds, affine 복구 후 최대 edge drift 786.67px → 1.0px
  - `strokesIncludedInLayout` 36개 오차를 모두 개선했고 해당 집합의 신규 회귀는 0개
  - 숨은 유효 AABB subtree의 공통 측정 49개를 모두 개선했고 신규 회귀는 0개
  - 일반 직교 affine 504개를 개선했고 이전 공통 측정의 신규 회귀는 0개
  - `BASELINE`과 `SPACE_BETWEEN` overflow 대상 32개를 추가 개선했고 공통 측정의 신규 회귀는 0개
  - signed overflow와 경계 없는 Auto Layout 부모의 보수적 cross bounds 복구 후 1px 초과 오차를 101개에서 41개로 줄였고 측정 손실과 신규 회귀는 0개
  - 누적 affine가 항등으로 상쇄된 자식의 raw rotation 재적용을 제거하고, epsilon 이내 음수 선 extent와 증거가 충분한 legacy intrinsic-text quarter turn을 복구해 1px 초과 오차를 41개에서 0개로 줄임
- Geometry ratchet: 24 cases / 10,759 objects 측정
  - 0.5px 초과 236개, 1px 초과 0개, known-blocked 제외 1,955개, unexpected 제외 0개, 최대 1.0px
  - 이전 10,721개 공통 측정은 모두 유지했고 신규 측정 38개를 추가했으며, 공통 측정 회귀와 측정 손실은 모두 0개
  - enforced report: `debugCapture/painter_ui_figma_geometry_m1_strict_ratchet0/figma_geometry_report.json`
  - 숨은 0폭/0높이 source 43개는 `source_hidden_degenerate_bounding_box_nonrendered`로 명시 분류
- Figma ALPHA/LUMINANCE mask는 Painter와 deterministic asset export에서 실제 픽셀 마스크로 합성
  - 4K 기준 crop 954×2,140, 임시 peak 추정 25.31MiB, 11.20ms
  - UMG에서는 여전히 deterministic bake blocker를 유지
- 객체/paint/effect blend mode는 캔버스와 deterministic asset export가 동일한 합성 모드를 사용
  - 그림자별 blend mode를 독립 적용하고 버튼 object shadow가 글자에 중복 적용되던 렌더 오류를 제거
- `individualStrokeWeights`와 expanded `strokeGeometry`를 원본 의미대로 보존·렌더
  - INSIDE/OUTSIDE outline mask를 캔버스와 asset export에 공통 적용하고 UMG 미지원은 명시적 bake blocker로 분류
- raw `VECTOR` 타입과 검증 가능한 `geometry=paths` 증거를 분리
  - 완전 증거 기준은 non-empty `fillGeometry`/`strokeGeometry` path, finite `size`, finite 2×3 `relativeTransform`을 모두 만족하는 것이다.
  - 전체 24 case에서 geometry-complete 증거는 5 case / 4,815 nodes다. 빠른 코퍼스는 1/20 case, 야간 코퍼스는 4/4 case다.
  - source-incomplete는 44 nodes이며 그중 visible paint/mask가 있는 33 nodes를 `source_incomplete_vector_geometry` blocker로 보고한다. 이 노드는 semantic recovery가 가능해도 geometry 호환 성공 증거로 세지 않는다.
  - 실제 vector path는 Painter 렌더와 JSON/plugin exchange round-trip을
    통과했다. TigerStudioUMG에는 native vector brush가 없지만 schema 13의
    보수적 safe subset은 deterministic RGBA8 PNG로 물질화해 `Baked`로
    전달하며, unsafe 또는 다른 gate가 남은 벡터만 명시적 `Blocked`로
    유지한다.
- Component Set 코퍼스는 variant member, property definition/value/binding, instance override를 source/import 양쪽에서 별도로 측정
- 공식 Plugin API 자동 코퍼스: code 3/3 + UI 3/3 통과
- 전체 REST case 24개의 누락 이미지 asset과 빈 `imageRef`: 모두 0

현대 effect 코퍼스는 실제 캡처와 공식-schema fixture를 분리한다.

- 현재 TigerStudioUMG source와 source-free bundle은 모두
  `Version 16 / 1.5.0`이며 UE 5.8 Editor Development, Game Development,
  Game Shipping 빌드를 통과했다.

- OpenPencil 고정 commit의 MIT 라이선스 Figma Plugin API readback은
  Noise monotone/duotone/multitone와 Texture를 `real_plugin_api_capture`로
  보존한다. REST 응답이나 픽셀 golden으로 표기하지 않는다.
- Progressive Blur는 실제 캡처를 확보하기 전까지
  `official_schema_fixture`이며 호환 성공 표본으로 세지 않는다.
- 인증 REST import는 visible Noise/Texture/progressive 노드의 Render API PNG를
  별도로 수집하고 실패를 warning으로 남긴다. exact PNG가 없는 이 코퍼스의
  effect는 기존처럼 명시적 UMG blocker다.
- schema 14의 exact Noise Baked 경로는 별도 합성 계약 fixture로 UE 5.8
  WBP compile/reopen, Texture2D referencer와 `FWidgetRenderer` 픽셀 운반을
  증명했다. 이는 Figma visual golden이 아니며 release100의 기존 disposition
  수치를 바꾸지 않는다.
- schema 15는 exact Texture safe leaf Rectangle을
  `kind=static_figma_texture_png`, source
  `tigerstudio.umg.static_texture_bake.v1`, gate
  `figma_texture_effect_requires_ui_material_or_deterministic_bake`인 별도
  계약으로만 `Baked` 처리한다. 실제 UE 5.8 WBP compile/reopen, Texture2D,
  `FWidgetRenderer` QA는 alpha bounds `[23,17,54,40]`, RGB MAE `0`, alpha
  exact `1.0`, exact crop hash 일치, 외부 alpha `0`과 DLL hash 일치를
  통과했다. 이 역시 `synthetic_contract_fixture`이며
  `not_a_figma_visual_golden`이다. safe subset 밖의 Texture는 `Blocked`다.
- Progressive layer blur는 render-bounds outset을 보존할 layout-aware bake가
  필요하고 background blur는 live backdrop에 의존하므로 exact PNG가 있어도
  둘 다 명시적 `Blocked`다. hidden progressive effect는 필드를 왕복하지만
  PNG 요청이나 blocker를 만들지 않는다.
- Noise와 Texture 모두 실제 Figma payload와 동일 노드 Render API PNG를 묶은
  visual golden은 아직 없다.

가장 큰 UMG blocker는 고급 외형, 정의가 없는 Figma 변수 재연결, Boolean bake, 원격 컴포넌트 재연결, 동적 Rounded Card 크기다. 이 기준선의 pipeline 통과를 “UMG 완전 호환”으로 해석하지 않는다.

## 샘플 추가 규칙

1. 라이선스가 없거나 source provenance가 불명확한 파일은 추가하지 않는다.
2. branch URL 대신 40자리 commit에 고정된 URL을 사용한다.
3. byte 수와 SHA-256을 반드시 기록한다.
4. CC BY 자료는 제작자, 원본 URL, 정식 라이선스 URL, 고정된 라이선스 근거, 변경 내용, attribution을 함께 기록한다.
5. 기존 feature 수만 늘리는 중복 파일보다 새로운 node/paint/layout 유형을 우선한다.
6. IMAGE fill 샘플은 가능하면 실제 image binary가 동봉된 archive를 사용한다.
7. `IMAGE` paint의 `imageRef`가 비어 있거나 참조 이미지 asset이 없으면 corpus case로 받지 않는다.
8. 새 샘플이 실패하면 manifest 기대치를 낮추기 전에 importer의 silent omission 여부를 먼저 조사한다.
9. 지원하지 않는 feature는 import warning, Figma compatibility, UMG preflight 중 적절한 경로에서 명시적으로 Blocked/Converted 처리한다.

## 현재 경계

`.fig` 바이너리는 REST JSON과 다른 Kiwi 기반 컨테이너다. 현재 코퍼스는 REST payload와 REST archive만 검증한다.

`.fig` 리더는 실험적으로 구현되어 있다(`app/painter_ui_figma_kiwi.py`, `app/painter_ui_figma_fig.py`, `app/painter_ui_figma_fig_rest.py`). 동작 범위는 다음과 같다.

- 컨테이너: ZIP(`canvas.fig` + `images/` + `meta.json`)과 bare `fig-kiwi` / `fig-jam.` payload 모두 처리한다.
- 압축: schema chunk는 raw deflate, message chunk는 deflate 또는 zstd다. zstd는 Python 3.14의 `compression.zstd`(PEP 784)를 우선 사용하고 이전 버전에서는 `zstandard`로 폴백한다.
- 변환: 평면 `nodeChanges` 배열을 `parentIndex`로 트리로 복원하고, parent-relative affine transform을 합성해 `absoluteBoundingBox`를 만든 뒤 REST node shape로 이름을 맞춘다. 결과는 기존 `import_figma_payload`가 그대로 소비한다.
- 벡터: REST는 평탄화된 `fillGeometry` path 문자열을 주지만 `.fig`는 편집 가능한 vector network를 `Message.blobs`에 따로 담는다. `app/painter_ui_figma_fig_vector.py`가 vertex/segment/region 블롭을 SVG path로 복원해 `fillGeometry`를 채운다. 이게 없으면 모든 VECTOR 노드가 `missing_geometry_paths`로 blocked 된다.

### 검증 상태 (2026-08-07)

실제 Figma가 생성한 `.fig` payload(version 65)와 실제 Figma Kiwi 스키마(350 definitions)로 오프라인 검증을 마쳤다.

- 임베드된 스키마 350개 정의를 자체 디코더로 완전 파싱했다.
- 매핑에 쓰는 `NodeChange` 필드명 53개가 실제 스키마에 모두 존재함을 확인했다.
- `GUID`/`ParentIndex`/`Matrix`/`Vector`/`Color`/`Paint`/`Effect`/`TextData`/`FontName`/`Number`/`SymbolData`/`Image`/`ColorStop` 구조가 전부 일치했다.
- enum 대조에서 버그 1건을 잡았다: `StackSize`는 `FIXED`/`RESIZE_TO_FIT`/`RESIZE_TO_FIT_WITH_IMPLICIT_SIZE` 3개이며, 두 hug 변형 모두 REST `AUTO`로 가야 한다.
- 실제 파일 임포트 결과 아트보드 6·오브젝트 22, vector network 복원 후 blocked 경고 0건.

검증에 쓴 스키마·샘플은 **라이선스가 명시되지 않은 제3자 저장소** 출처라 레포에 포함하지 않았다. 커밋된 테스트는 자체 Kiwi 인코더로 합성 바이너리를 만들어 검증한다.

경계는 그대로 유지한다.

- 포맷은 공개 계약이 아니라 리버스 엔지니어링 결과다. Figma가 스키마 의미를 바꾸면 깨질 수 있으므로 REST import가 계속 지원 경로다.
- 매핑 범위는 importer가 실제로 읽는 필드로 한정한다. 매핑되지 않은 node type은 조용히 버리지 않고 report의 `fig_unmapped_node_types`와 warning으로 노출한다.
- import report는 항상 `fig_native_import`를 포함하며, 사용자향 문구는 계속 native `.fig` 호환이 아님을 명시한다.
- 라이선스가 명확한 `.fig` 샘플(Figma Community 무료 파일은 CC BY 4.0)을 확보하기 전까지 코퍼스 case로 등록하지 않는다. 등록 시에는 전용 manifest와 golden 비교를 사용한다.

로컬 `.fig`를 코퍼스에 넣기 전 확인하려면 `python tools/inspect_fig_archive.py <file>.fig`로 요약을,
`--dump-rest`로 변환된 REST payload를 얻는다.

## M6 릴리스 100-case 게이트 (2026-08-05)

릴리스 매니페스트는
`qa_corpus/painter_ui_figma_documents/release_manifest.json`이다. 정확한
case 계산은 다음과 같다.

- 빠른 독립 fixture 20개
- nightly 매니페스트에서 stroke/vector 독립 JSON fixture 2개만 include
- Auto Layout Playground archive의 서로 겹치지 않는 subtree 67개
- Radix Icons archive의 서로 겹치지 않는 subtree 11개
- 합계 100개

두 ZIP은 78개 selector가 공유하는 고정 source artifact일 뿐, 별도의
whole-document case로 세지 않는다. 따라서 archive 두 개를 더해 102개로
표기하면 안 된다. selector 합계는 7,578 nodes, canonical JSON
12,600,171 bytes이다.

v2 매니페스트는 include 경로/순환/깊이, 고정 artifact SHA-256과 크기,
selector node/type/name/canvas/ancestry, exact 및 semantic subtree SHA-256,
selector 비중첩과 중복, node/JSON/image 안전 한도를 검증한다. 실행기는
archive를 artifact별로 한 번 파싱하고 selector가 실제 참조하는
`imageRef` closure만 추출한다. 선택 subtree는 원래 DOCUMENT/CANVAS
메타데이터 아래 `promote_to_original_canvas` 방식으로 import한다.

릴리스 artifact 확인 및 실행:

```powershell
.\.venv\Scripts\python.exe tools\fetch_painter_ui_figma_document_corpus.py `
  --manifest qa_corpus\painter_ui_figma_documents\release_manifest.json

.\.venv\Scripts\python.exe tools\qa_painter_ui_figma_document_corpus.py `
  --manifest qa_corpus\painter_ui_figma_documents\release_manifest.json `
  --output debugCapture\painter_ui_figma_document_corpus_release100

.\.venv\Scripts\python.exe tools\qa_painter_ui_figma_document_corpus.py `
  --manifest qa_corpus\painter_ui_figma_documents\release_manifest.json `
  --output debugCapture\painter_ui_figma_document_corpus_release100_render `
  --render-smoke --no-render-pngs
```

매니페스트를 감사된 고정 archive에서 재계산하는 도구는
`tools/build_painter_ui_figma_release_manifest.py`이다. 이 도구의 결과와
체크인 매니페스트가 의미상 동일한지는 테스트에서 확인한다.

현재 실제 결과:

- non-render import/round-trip/preflight: 100/100 통과
- selector source feature ratchet: 모두 통과
- 참조 누락 image asset: 0
- in-memory render: case 100/100, focused artboard 109/109
- UMG 대상 7,989개: Native 2,131 / Material 240 / Baked 20 / Blocked 5,598
- Baked selector 10개 재감사: vector gate 109 → 89, 제거·물질화 20,
  최종 Baked 20, transition/materialization 오류 0
- UMG clean: 3/100. pipeline 통과는 UMG 완전 호환을 뜻하지 않는다.
- 동일 exact100 workload의 성능 비교: `-10.9549854729%`, 허용 회귀 15%,
  comparison `passed`
- schema 15 Texture 통합 후 non-render 재실행도 100/100과 기존 disposition
  `2,131 / 240 / 20 / 5,598`, UMG clean 3을 그대로 유지했다.

Radix `Alignment` selector는 완전한 boolean/path geometry를 가진 가시
component 정의다. importer의 editable Boolean operand 해석이 빈 path를
반환할 때 Painter가 source의 canonical flattened `fillGeometry`로
fallback하도록 수정했고, 이 case의 전체/집중 render를 회귀 테스트한다.
render gate를 완화하거나 selector를 교체하지 않았다.

증거 보고서:

```text
debugCapture/painter_ui_figma_document_corpus_release100/report.json
debugCapture/painter_ui_figma_document_corpus_release100_render_final/report.json
debugCapture/painter_ui_figma_document_corpus_release100_schema15_texture_exact_final/report.json
debugCapture/painter_ui_figma_m6_release100_perf_current_final/report.json
debugCapture/m6b_vector_static_bake_release100_baked_cases_selector_final/report.json
debugCapture/m6b_vector_static_bake_unreal_schema15_compat_final/qa_report.json
debugCapture/static_noise_ue_qa_plugin150/qa_report.json
debugCapture/static_texture_ue_qa/qa_report.json
```

`--write-packages`는 TigerStudioUMG 패키지가 아니라 Painter에서 Figma plugin
exchange로 되돌려 보내는 별도 역방향 export다. 따라서 unsupported object가
있는 case는 `PainterUIFigmaError`로 명시 차단되는 것이 정상이며, 이 옵션의
부분 통과를 UMG 실패로 해석하지 않는다. UMG의 schema 13 정적 벡터 Baked,
schema 14 exact Noise Baked, schema 15 exact Texture Baked 물질화는
`tools/qa_painter_ui_umg_static_vector_bake.py`,
`tools/qa_painter_ui_unreal_umg_static_appearance_bake.py` 및 실제 UE QA에서
별도로 검증한다.
