# Tiger Studio AI Layered Image Motion 제품 기획서

## 구현 상태 (2026-07-24)

- `LIM0~LIM2` 구현: v1 manifest/cache, Alpha·Basic Local·선택형 SAM 공급자
  계약, 마스크 무결성, 비파괴 Merge/Split/Mask Replace/Lock/Parent/Pivot/
  Z-order, Layer Graph와 첫 프레임 재합성 검증을 지원한다.
- `LIM3` 로컬 경로 구현: Fast Local과 multi-scale 복원, 복원 신뢰도에 따른
  카메라 이동 제한을 적용한다. `Enhanced Local` 모델이 없으면 명시적으로 Fast
  Local로 폴백하며 Cloud inpaint는 아직 지원하지 않는다.
- `LIM4` 구현: OCR line 병합, 제목/본문/CTA 역할, confidence gate,
  native Typography와 raster fallback을 지원한다.
- `LIM5` 구현: Clean/Dynamic/Collage 후보, 레이어별 방향·속도·stagger,
  카메라와 audio hit, 강체/부모 잠금 검증을 지원한다.
- `LIM6` 1차 제품 구현: AI 패널 고급 옵션, 3후보 selector, 원본/복원/마스크
  보정 대화상자, 브러시와 구조 수정, 후보 재컴파일, Apply 1회/Undo 1회,
  분석·보정·안무·프리뷰 Action/MCP를 제공한다.
- `LIM7` 개발 QA 구현: 지속 자산 3종을 16:9·9:16·1:1로 분석하고 세 후보의
  시작/중간/끝 PNG 및 Dynamic MP4를 생성하는
  `tools/qa_motion_layered_images.py`를 제공한다. 설치본의 저장/재열기,
  장시간 메모리, 선택형 모델 설치 UX와 Cloud 동의 검증은 릴리스 QA로 남는다.

제품 표현은 현재도 `AI-assisted editable layered motion composition`이다.
Basic Local 결과를 범용 의미 분할 또는 모든 이미지의 완전한 자동 분해로 주장하지
않는다.

작성일: 2026-07-24
상태: 구현 연계 제품 기획
대상: Tiger Studio Motion Designer
작업명: `AI Layer Motion`

관련 문서:

- `docs/MOTION_DESIGNER_PRODUCT_PLAN_KO.md`
- `docs/MOTION_DESIGNER_MILESTONES_KO.md`
- `docs/MOTION_AI_GENERATION_PRODUCT_PLAN_KO.md`
- `docs/MOTION_DESIGNER_ARCHITECTURE.md`
- `SPEC.md`

## 1. 한 줄 정의

AI Layer Motion은 사용자가 프롬프트와 이미지 몇 장을 넣으면 이미지 안의 인물,
제품, 소품, 글자, 장식, 배경을 편집 가능한 레이어로 분해하고, 각 레이어에
깊이·계층·시간차·카메라 연출을 적용해 Motion Designer 컴포지션을 만드는
AI 보조 제작 기능이다.

출력은 완성된 동영상 한 장이 아니라 다음 항목을 유지하는 편집 가능한 결과여야 한다.

- 원본 이미지와 생성·복원 자산
- RGBA 레이어와 마스크
- 부모·자식 및 강체 그룹
- 깊이와 가림 순서
- 네이티브 타이포그래피
- 키프레임, Behavior, 카메라, 오디오 큐
- 분석 근거, 신뢰도, 사용한 AI 공급자

## 2. 제품 목표

사용자는 3~6장의 이미지와 한두 문장의 지시만으로 6~15초 길이의 모션 그래픽
초안을 만들 수 있어야 한다. 생성 후에는 일반 Motion Designer 프로젝트처럼
레이어를 선택하고 위치, 크기, 시간, 마스크와 움직임을 직접 수정할 수 있어야 한다.

핵심 목표는 다음과 같다.

1. 이미지 안의 의미 단위를 자동으로 찾아 편집 가능한 레이어로 만든다.
2. 레이어 이동으로 드러나는 빈 영역을 자연스럽게 복원한다.
3. 물체의 형태를 보존하면서 레이어마다 서로 다른 움직임을 준다.
4. 이미지 속 제목과 문구를 가능한 경우 네이티브 텍스트로 복원한다.
5. 프롬프트와 음악에 맞는 모션 연출을 자동으로 구성한다.
6. 프리뷰와 MP4 출력에서 같은 결과를 보장한다.
7. 자동화와 MCP가 UI와 동일한 기능을 사용할 수 있게 한다.

## 3. 하지 않을 주장

초기 제품은 다음을 주장하지 않는다.

- 모든 이미지의 완전한 의미 분할
- 모든 인물의 자연스러운 관절 애니메이션
- 단일 사진에서 보이지 않는 면을 정확히 복원하는 3D 재구성
- 범용 이미지 투 비디오 모델과 동일한 자유 변형
- 로고와 작은 문자의 100% 정확한 OCR 복원
- 투명 유리, 머리카락, 연기, 레이스의 무손실 자동 분리
- 사용자의 동의 없는 클라우드 이미지 업로드

제품 표현은 `AI-assisted editable layered motion composition`을 사용한다.
`Universal image-to-video` 또는 `모든 이미지를 자동 애니메이션`으로 표현하지 않는다.

## 4. 현재 구현 기준선

2026-07-24 기준으로 다음 기능은 구현되어 있다.

| 항목 | 현재 상태 | 구현 위치 |
|---|---|---|
| 로컬 이미지 분석 | 구현 | `app/motion_designer/image_decomposition.py` |
| Source Alpha 사용 | 구현 | 동일 모듈 |
| Alpha·Basic Local·선택형 SAM 공급자 계약 | 구현 | `semantic_segmentation.py` |
| 연결 성분별 RGBA·마스크 생성 | 구현 | 동일 모듈 |
| 공용 Depth Provider 연결 | 구현 | `app/depth/providers.py` |
| Fast/multi-scale 인페인팅과 이동 제한 | 구현 | `background_inpainting.py` |
| OCR와 네이티브 Typography confidence gate | 구현 | `typography_reconstruction.py` |
| Layer Graph와 비파괴 보정 | 구현 | `layer_graph.py`, `image_decomposition_edits.py` |
| Clean/Dynamic/Collage 안무 컴파일 | 구현 | `motion_choreography.py` |
| 투명·희소 강체 보호 | 구현 | 배경과 동일 변환으로 잠금 |
| 이미지 분해/보정 UI와 3후보 선택 | 구현 | `ui/ai_panel.py`, `ui/layer_extraction_dialog.py` |
| 이미지 분해·보정·안무·프리뷰 Action | 구현 | `motion.ai.layer.*`, `motion.ai.choreography.*` |
| AI Brief·Storyboard·Composition 컴파일 | 1차 구현 | `ai_generation.py` |
| Claude 등 기존 AI 계약 사용 | 구현 | `app/ai_providers.py` |

현재 Basic Local 경로는 유용한 폴백이지만 의미 기반 인스턴스 분할은 아니다.
선택형 SAM이 없거나 복잡한 콜라주에서 사람, 손, 소품, 글자와 장식을 정확히
구분하지 못하면 보정 UI 또는 향후 동의형 Vision 공급자가 필요하다.

## 5. 대표 사용자 시나리오

### 5.1 콜라주형 세로 광고

입력:

- 인물 사진 1장
- 제품 또는 작업 화면 2~4장
- 제목과 CTA
- “팝아트 콜라주, 빠르고 화려하게, 9:16, 8초”

결과:

- 중앙 인물 강체 그룹
- 손에 든 소품 분리
- 배경 패턴과 종이 질감
- 단어별 제목 레이어
- 화살표, 별, 말풍선, 필름 프레임
- 깊이별 패럴랙스와 리듬형 팝
- 마지막 로고와 CTA 정지 구간

### 5.2 제품 리빌

입력:

- 제품 사진 3장
- 로고
- 가격 또는 기능 문구

결과:

- 제품은 형태가 깨지지 않는 강체 레이어
- 기능 부위는 별도의 콜아웃 레이어
- 배경은 복원 후 느린 카메라 이동
- 로고와 가격은 네이티브 텍스트·벡터

### 5.3 캐릭터 소개

입력:

- 캐릭터 전신 또는 반신 이미지
- 표정 이미지
- 배경 이미지
- 음악

결과:

- 몸 전체는 기본적으로 하나의 강체
- 머리카락·소매·소품은 신뢰도가 높을 때만 보조 레이어
- 표정은 별도 이미지 컷 또는 기존 Live2D/Spine/VRM 경로 사용
- 임의의 관절 변형보다 안전한 카메라·패럴랙스 연출 우선

## 6. 사용자 경험

### 6.1 생성 흐름

1. 사용자가 Motion Designer의 AI 영역에 이미지와 프롬프트를 드롭한다.
2. 시스템이 로컬 분석 가능 여부와 선택된 AI 공급자를 표시한다.
3. 사용자가 `이미지 레이어 분해`를 켜고 생성한다.
4. 시스템은 분석, 분할, 배경 복원, 계층 생성, 연출 계획 순서로 진행 상태를 표시한다.
5. 생성 결과를 적용하기 전에 2~3개의 후보와 레이어 분해 미리보기를 보여준다.
6. 사용자는 잘못 분리된 레이어를 합치거나 나누고, 움직이지 않을 레이어를 잠근다.
7. 선택한 후보를 하나의 Undo 트랜잭션으로 컴포지션에 적용한다.
8. 일반 Motion Designer 타임라인과 그래프 편집기에서 계속 편집한다.

### 6.2 기본 UI

AI 패널은 다음만 첫 화면에 노출한다.

- 프롬프트
- 참조 이미지 스트립
- 비율
- 길이
- 모션 강도
- 이미지 레이어 분해
- 음악 반응
- 생성

고급 설정은 별도 펼침 영역에 둔다.

- 최대 레이어 수
- 로컬 또는 AI 분할
- 배경 복원 품질
- 텍스트 복원
- 인물 부분 분리 허용
- 깊이 강도
- 카메라 움직임
- 클라우드 전송 동의

### 6.3 레이어 분해 보정 UI

캔버스 위에서 다음 작업을 지원한다.

- 레이어 선택
- 브러시로 마스크 추가·제거
- 클릭 기반 SAM 선택
- 레이어 합치기·나누기
- 강체로 묶기
- 부모 지정
- 앞·뒤 순서 변경
- 피벗 이동
- 배경 복원 재실행
- 원본과 분해 결과 Before/After

잘못 분리된 결과를 프롬프트만으로 반복 생성하게 하지 않고 사용자가 직접 고칠 수
있어야 한다.

## 7. 레이어 모델

### 7.1 레이어 역할

| 역할 | 예 | 기본 동작 |
|---|---|---|
| Background | 벽, 풍경, 종이 질감 | 느린 줌·패닝 |
| Hero Rigid | 인물 전체, 제품, 유리잔 | 형태 보존, 카메라 중심 |
| Articulated Part | 팔, 손, 소매 | 부모 피벗 기준 제한 회전 |
| Prop | 노트북, 컵, 카드 | Hero에 부착하거나 독립 팝 |
| Decoration | 별, 화살표, 말풍선 | 시차 팝·회전 |
| Native Text | 제목, 가격, CTA | 단어·글자 단위 타이포 모션 |
| Raster Text | 복원 신뢰도가 낮은 문자 | 이미지로 보존 |
| Foreground Frame | 종이 찢김, 필름, 테두리 | 화면 앞쪽 패럴랙스 |

### 7.2 그룹 규칙

- 제품, 얼굴, 몸통과 투명 용기는 기본적으로 강체다.
- 자식 레이어는 부모 변환을 상속한다.
- 독립 움직임은 분할 신뢰도와 피벗 신뢰도가 모두 기준을 넘을 때만 허용한다.
- 머리카락, 레이스, 연기처럼 경계가 불안정한 요소는 배경 잠금 또는 원본 단일
  레이어로 폴백한다.
- 같은 물체의 마스크 조각은 서로 다른 Depth 값만으로 분리하지 않는다.
- 첫 프레임에서 모든 레이어를 합성한 결과는 원본과 일치해야 한다.

### 7.3 예시 콜라주 구성

```text
Composition
  Camera
  Foreground Frame Group
    Arrow Left
    Arrow Right
    Film Strip
  Native Title Group
    AI
    MOTION
    GRAPHICS
    VIDEOS
  Hero Group [rigid]
    Person Body
    Raised Hand [optional articulated]
    Tablet Prop
  Sticker Group
    Boom Bubble
    Star
    Create Badge
  Background Collage Group
    Paper Texture
    UI Screenshot 1
    UI Screenshot 2
    Landscape Cutout
```

## 8. 처리 파이프라인

```text
Reference Intake
  -> Local Inspection
  -> Semantic Segmentation
  -> Mask Integrity Repair
  -> Background Inpainting
  -> OCR and Typography Reconstruction
  -> Layer Graph and Depth Ordering
  -> Creative Brief and Beat Storyboard
  -> Motion Choreography
  -> Deterministic Validation
  -> Candidate Preview
  -> User Repair
  -> Apply as Motion Composition
```

### 8.1 Reference Intake

- 파일 존재, 포맷, 해상도, 알파, EXIF 회전을 확인한다.
- 원본 파일은 수정하지 않는다.
- 동일 자산은 콘텐츠 해시로 분석 캐시를 공유한다.
- 프로젝트 자산과 재생성 가능한 분석 캐시를 분리한다.

### 8.2 Semantic Segmentation

분할은 공급자 인터페이스로 구성한다.

1. `source_alpha`: 투명 PNG의 알파
2. `local_basic`: 현재 GrabCut·연결 성분
3. `local_sam`: 기존 `app/sam_segment.py`를 확장한 자동·클릭 기반 SAM
4. `cloud_vision`: 사용자 동의가 있을 때만 사용하는 의미 분할 공급자

모든 공급자는 동일한 `SemanticLayerManifest`를 반환해야 한다. 공급자가 실패하면
조용히 낮은 품질을 AI 결과로 표시하지 않고 실제 사용한 폴백 수준을 UI에 표시한다.

### 8.3 Mask Integrity Repair

다음 진단을 수행한다.

- 마스크 면적과 바운딩 박스 채움률
- 연결 성분 수
- 외곽선 단절
- 내부 구멍
- 얇은 투명 경계
- 원본 대비 합성 오차
- 같은 물체로 추정되는 조각 간 거리

진단 결과에 따라 다음 중 하나를 선택한다.

- 마스크 팽창·축소·홀 채우기
- 조각 병합
- 부모와 동일 변환으로 잠금
- 원본 단일 레이어 폴백
- 사용자 확인 요청

형태 보존 실패는 화려하지 않은 모션보다 더 심각한 오류로 취급한다.

### 8.4 Background Inpainting

배경 복원은 세 단계로 제공한다.

- `Fast Local`: 현재 저해상도 OpenCV 복원
- `Enhanced Local`: 선택 설치형 로컬 인페인팅 모델
- `Cloud Quality`: 명시적 동의 후 클라우드 생성 편집

큰 빈 영역에서 OpenCV 결과를 제품 품질로 주장하지 않는다. 복원 신뢰도가 낮으면
카메라 이동 범위를 자동으로 제한해 빈 공간이 드러나지 않게 한다.

### 8.5 OCR와 Typography Reconstruction

- OCR 박스, 문자열, 언어, 신뢰도를 저장한다.
- 높은 신뢰도의 제목·가격·CTA만 네이티브 텍스트로 변환한다.
- 원본 폰트를 찾지 못하면 유사 폰트를 제안하되 자동 확정하지 않는다.
- 낮은 신뢰도의 문자는 Raster Text로 유지한다.
- 로고 내부 문자는 OCR 대상으로 취급하지 않는다.
- 네이티브 텍스트가 원본 위에 중복으로 남지 않도록 원본 문자 영역을 복원하거나
  원본 텍스트 레이어를 숨긴다.

### 8.6 Layer Graph

레이어 그래프는 다음 정보를 가진다.

```text
SemanticLayer
  id
  role
  label
  source_id
  rgba_path
  mask_path
  bbox
  depth
  z_order
  parent_id
  motion_group_id
  pivot
  rigid
  confidence
  provenance
  warnings
```

Depth는 가림과 패럴랙스 제안에 사용하지만 의미 그룹을 깨뜨리는 근거로 단독
사용하지 않는다.

### 8.7 Motion Choreography

AI 연출기는 픽셀을 직접 생성하지 않고 허용된 Motion schema만 계획한다.

- 카메라 시작·종료 프레이밍
- Beat별 등장 순서
- 레이어 진입·유지·퇴장
- 깊이별 이동량
- 팝·오버슈트·회전 범위
- 텍스트 단어·글자 Stagger
- 음악 Hit와 전환 시점
- 마지막 읽기 가능한 정지 구간

동일한 프롬프트에서도 최소 다음 세 후보를 만들 수 있다.

- `Clean`: 적은 레이어, 읽기 쉬운 모션
- `Dynamic`: 빠른 시차, 팝, 카메라 Hit
- `Collage`: 장식과 프레임을 적극적으로 사용

모든 레이어를 같은 방향과 속도로 흔드는 결과는 실패로 판정한다.

## 9. AI 사용 경계

### 9.1 Basic Local

AI 공급자와 인터넷 없이 동작한다.

- Alpha·GrabCut·연결 성분
- 공용 Depth 폴백
- 제한된 OCR
- 규칙 기반 Storyboard
- 안전한 강체 잠금
- 기본 2.5D 모션

### 9.2 Enhanced Local

선택 설치형 모델을 사용한다.

- SAM 의미 마스크 보조
- 로컬 OCR
- 로컬 인페인팅
- 선택적인 포즈·피벗 추정

모델이 없으면 설치 안내와 예상 디스크·GPU 요구량을 표시한다.

### 9.3 Cloud Assist

클라우드는 다음 경우에만 사용한다.

- 사용자가 해당 이미지 전송에 동의했다.
- 전송 파일, 공급자, 목적과 예상 비용을 확인했다.
- 결과에 모델과 요청 provenance를 기록한다.

Claude는 Creative Brief, 의미 라벨 보정, 레이어 그룹과 모션 계획에 사용한다.
마스크 픽셀 생성은 해당 기능을 가진 Vision/Segmentation 공급자가 담당한다.

## 10. 데이터 계약

현재 `tigerstudio.motion.image_decomposition.v1`은 유지한다. 제품 확장 시에는 기존
프로젝트를 깨지 않고 v2 manifest를 추가한다.

```text
SemanticLayerManifest v2
  schema
  algorithm
  source_hash
  canvas
  providers[]
  background
  layers[]
  groups[]
  ocr_regions[]
  depth
  validation
  warnings[]
```

모든 생성 자산은 다음을 기록한다.

- 원본 자산 ID와 해시
- 생성 공급자와 모델
- 프롬프트 또는 입력 해시
- 생성 시각
- 캐시 또는 프로젝트 자산 여부
- 재생성 가능 여부
- 클라우드 전송 동의

## 11. Action과 자동화

기존 Action:

- `motion.ai.reference.decompose`
- `motion.ai.plan`
- `motion.ai.apply`
- `motion.ai.candidate.generate`
- `motion.ai.patch.plan`
- `motion.ai.patch.apply`

추가 Action:

- `motion.ai.layer.analyze`
- `motion.ai.layer.segment`
- `motion.ai.layer.mask.refine`
- `motion.ai.layer.mask.replace`
- `motion.ai.layer.merge`
- `motion.ai.layer.split`
- `motion.ai.layer.group`
- `motion.ai.layer.lock`
- `motion.ai.layer.pivot`
- `motion.ai.layer.order`
- `motion.ai.background.inpaint`
- `motion.ai.text.reconstruct`
- `motion.ai.choreography.plan`
- `motion.ai.choreography.apply`
- `motion.ai.integrity.validate`
- `motion.ai.candidate.preview`
- `motion.ai.candidates.generate`

분석 Action은 프로젝트를 변경하지 않는다. 적용 Action은 stable ID, base revision과
Undo transaction을 사용한다. AI와 UI는 같은 서비스와 Action 계약을 사용한다.

## 12. 모듈 계획

기존 모듈을 유지하면서 다음처럼 분리한다.

```text
app/motion_designer/
  image_decomposition.py       # 현재 로컬 기준선과 manifest facade
  semantic_segmentation.py     # 공급자 계약과 레이어 후보
  mask_integrity.py            # 병합, 홀, 강체, 합성 오차
  background_inpainting.py     # 로컬·선택형·클라우드 복원
  typography_reconstruction.py # OCR에서 네이티브 텍스트
  layer_graph.py               # 부모, 그룹, 깊이, 피벗
  motion_choreography.py       # Beat에서 레이어별 연출 계획
  image_motion_validation.py   # 구조·시각·시간·출력 QA
  ui/
    ai_panel.py
    layer_extraction_panel.py
    mask_refine_canvas.py
```

`app/video_editor_window.py`에는 이 기능을 추가하지 않는다. 메인 에디터 연결은 기존
Motion Designer 진입점과 Action adapter를 사용한다.

## 13. 구현 마일스톤

### LIM0 - 기준선 고정

현재 구현을 회귀 테스트로 고정한다.

- v1 manifest와 캐시
- 로컬 분해
- 2.5D 컴파일
- 투명·희소 마스크 강체 잠금
- 첫 프레임 합성 검증

완료 조건:

- 유리잔 QA에서 레이어 상대 위치 변화로 인한 파손이 없다.
- 기존 Motion AI와 아키텍처 테스트가 통과한다.

### LIM1 - Semantic Provider 계약

- `SemanticSegmentationProvider` 인터페이스
- Alpha, Basic Local, SAM adapter
- capability와 실제 사용 backend 표시
- 자동 후보와 클릭 기반 수정

완료 조건:

- 사람·제품·장식·배경 corpus에서 의미 레이어 후보를 반환한다.
- SAM이 없어도 Basic Local이 정상 동작한다.

### LIM2 - 마스크 보정과 Layer Graph

- 마스크 합치기·나누기
- 강체·관절형 그룹
- 부모, 피벗, z-order
- 원본 재합성 오차 검사

완료 조건:

- 인물 몸통과 제품이 조각별로 다른 변환을 받지 않는다.
- 모든 자동 수정은 diagnostics에 근거를 남긴다.

### LIM3 - 배경 복원

- Fast Local 품질 제한
- Enhanced Local provider
- Cloud provider 경계
- 복원 품질에 따른 카메라 이동 제한

완료 조건:

- 레이어 이동 후 검은 구멍과 반복 텍스처가 없는 샘플만 자동 승인한다.
- 실패 샘플은 카메라 이동 제한 또는 사용자 확인으로 전환한다.

### LIM4 - OCR와 네이티브 텍스트

- OCR 영역 병합
- 제목·가격·CTA 역할 분류
- 폰트 후보와 네이티브 Typography 생성
- 원본 Raster Text 폴백

완료 조건:

- 낮은 신뢰도 문자를 임의로 바꾸지 않는다.
- 네이티브 텍스트와 원본 문자가 이중으로 보이지 않는다.

### LIM5 - Motion Choreography

- Claude Brief·Storyboard 연계
- 레이어별 Motion assignment
- 카메라·텍스트·장식·오디오 Hit
- Clean, Dynamic, Collage 후보

완료 조건:

- 각 후보의 레이어별 속도·방향·시작 시간이 실제로 다르다.
- 강체와 잠금 정책을 Motion planner가 위반하지 않는다.

### LIM6 - 보정 UI와 Action 완성

- 레이어 분해 패널
- 캔버스 마스크 수정
- Merge, Split, Lock, Parent
- Before/After
- 모든 기능 Action 노출

완료 조건:

- 마우스와 Action 양쪽에서 동일한 프로젝트 결과가 생성된다.
- 한 번의 Apply를 한 번의 Undo로 되돌릴 수 있다.

### LIM7 - 제품 QA와 설치본 검증

- 실제 이미지 corpus
- 16:9, 9:16, 1:1
- 1080p 프리뷰와 MP4
- 장시간 메모리·캐시
- 클라우드 동의와 오프라인 폴백

완료 조건:

- 설치본에서 3~6장 이미지로 후보 생성, 수정, 저장, 재열기, MP4 출력이 가능하다.
- 공개 기능 설명과 실제 evidence가 일치한다.

## 14. QA Corpus

최소 다음 입력을 유지한다.

1. 투명 유리잔과 액체
2. 전신 인물과 손에 든 소품
3. 머리카락이 복잡한 캐릭터
4. 제품 패키지와 작은 문자
5. 팝아트 콜라주
6. 밝은 배경의 흰색 제품
7. 어두운 배경의 검은 제품
8. 레이스와 반투명 천
9. 연기·불꽃·빛 입자
10. 한글·영문 혼합 제목
11. 9:16 세로 포스터
12. 여러 물체가 서로 겹친 사진

각 샘플은 원본, manifest, 마스크, 첫 프레임, 중간 프레임, 마지막 프레임,
구조 보고서와 MP4 evidence를 가진다. 중요한 원본은 `debugCapture`에 두지 않는다.

## 15. 품질 기준

### 15.1 구조

- 레이어 ID 중복 0개
- 부모 순환 0개
- 누락된 자산 경로 0개
- 원본 바깥으로 잘린 Hero 0개
- 잠긴 강체 내부의 상대 변환 변화 0개

### 15.2 시각

- 첫 프레임 원본 재합성 SSIM 목표 0.99 이상
- 2픽셀을 넘는 검은 Alpha halo 0개
- 인물·제품·투명 물체의 분할 파손 0개
- 인페인팅 빈 구멍 0개
- 네이티브 텍스트 중복 표시 0개
- Safe Area를 벗어난 필수 제목·CTA 0개

### 15.3 모션

- 모든 레이어가 동일한 변환을 받는 Dynamic 후보 0개
- 읽기용 제목 정지 구간 최소 0.8초
- Beat와 주요 Hit의 오차 목표 1프레임 이하
- 강체 정책 위반 0개
- 첫 프레임 순간 점프 0개

### 15.4 성능

- 분석과 인페인팅은 비동기 작업으로 실행한다.
- 분석 중 UI 메인 스레드 정지 100ms 초과 0회가 목표다.
- 캐시가 준비된 1080p·20개 2D 레이어 프리뷰는 기준 GPU에서 30fps를 목표로 한다.
- Preview와 Export는 동일한 Motion evaluation 결과를 사용한다.

## 16. 실패 처리

| 실패 | 처리 |
|---|---|
| 전경을 찾지 못함 | 원본 단일 이미지 레이어 |
| 투명 물체가 조각남 | 배경과 동일 변환으로 잠금 |
| 큰 배경 복원이 불량 | 카메라 이동 제한 또는 재복원 |
| OCR 신뢰도가 낮음 | Raster Text 유지 |
| 관절 피벗이 불명확 | 인물 전체 강체 유지 |
| SAM 미설치 | Basic Local로 명시적 폴백 |
| 클라우드 거부 | 로컬 결과 유지 |
| Provider timeout | 프로젝트 변경 없이 후보 작업 취소 |
| Export unsupported | Apply 전에 경고 또는 지원 효과로 bake |

## 17. 성공 지표

제품 베타 기준:

- 3~6장의 이미지로 10초 내외 초안을 생성할 수 있다.
- 지원 corpus의 80% 이상에서 Hero를 자동으로 올바른 강체 그룹으로 만든다.
- 사용자가 원하는 결과까지 필요한 마스크 수정이 평균 3회 이하다.
- 생성 결과의 90% 이상이 수동 레이어 재구축 없이 편집을 시작할 수 있다.
- 실패한 자동 분석은 잘못된 AI 성공 표시 대신 폴백과 경고를 제공한다.
- 사용자 테스트에서 10분 안에 첫 MP4 출력까지 도달한다.

## 18. 우선 구현 순서

1. 현재 유리잔 강체 보호와 첫 프레임 재합성 검사를 LIM0으로 고정한다.
2. 기존 `app/sam_segment.py`를 공급자 인터페이스 뒤로 옮기고 자동 후보를 추가한다.
3. 레이어 Merge·Split·Lock과 부모 그룹을 먼저 구현한다.
4. 배경 복원 공급자와 카메라 이동 제한을 연결한다.
5. OCR 결과를 네이티브 Typography로 변환한다.
6. Claude Storyboard가 Layer Graph를 대상으로 연출하도록 확장한다.
7. 보정 UI와 Action을 같은 서비스에 연결한다.
8. 실제 콜라주 샘플로 설치본 QA를 완료한다.

이 순서를 지키면 AI 모델 품질이 부족해도 사용자가 고칠 수 있는 제품을 먼저 확보하고,
이후 모델을 교체해도 Motion Composition과 편집 경험은 유지할 수 있다.
