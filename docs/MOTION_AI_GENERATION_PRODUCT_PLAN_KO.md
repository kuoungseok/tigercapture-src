# Tiger Studio AI Motion Generation 제품 기획서

## Gemini Omni 공식 설명 재검토 반영 (2026-07-24)

Google 공식 Gemini Omni 소개의 핵심은 텍스트·이미지·영상·오디오를 함께
참조하는 생성, 기존 결과를 이어가는 대화형 수정, 캐릭터와 장면의 일관성,
배경·행동·객체 변경, 음원 동기화, 모션/스타일 참조, 디지털 아바타, 그리고
출처 표시다. Tiger Studio는 같은 생성 모델을 주장하지 않고 다음 기능을
편집 가능한 Motion Composition으로 대응한다.

1. **자동 객체 제안**: 선택형 로컬 Ultralytics 모델은 의미 라벨을 제공하고,
   기본 OpenCV 경로는 의미를 추측하지 않는 `object_01` 형식의 검토 가능한
   전경 영역만 제안한다.
2. **마스크와 매팅**: source alpha, Basic Local, 선택형 SAM 뒤에
   edge-aware trimap alpha 보정을 적용한다. 학습형 hair matting은 아직 별도
   선택 모델이 필요하다.
3. **배경 복원**: 작은 구멍/제한된 카메라 이동은 결정론적 로컬 inpaint를
   사용하고, 큰 영역은 사용자가 검토한 clean plate로 교체할 수 있다.
4. **객체/파트 모션**: 위치·크기·Z 회전뿐 아니라 이미지 `tilt_x`,
   `tilt_y`, `perspective`를 키프레임과 Graph에서 편집한다.
   객체 힌트의 `parent_id`, `part`, `rigid`, `pivot`을 보존해 파츠 리그를
   만들 수 있으며 팔·바퀴 같은 의미를 근거 없이 추정하지 않는다.
5. **한 요청 오케스트레이션**: Prompt + References에서 브리프, 비트
   스토리보드, 분해, 안무, 검증, 후보 Preview까지 한 작업으로 실행하며
   Apply 전에는 프로젝트를 변경하지 않는다.
6. **대화형 후속 수정**: stable layer ID와 base revision을 사용하는
   allowlist patch로 텍스트·타이밍·변환·이미지 틸트/원근·행동·표시를
   수정하고 하나의 undo revision으로 적용한다.

공식 소개를 다시 읽고 1~6 외에 추가한 범위:

- **오디오 참조**: 비트/온셋을 추출해 분해 레이어 안무 타이밍에 전달한다.
- **영상 모션 참조**: OpenCV optical flow로 카메라/레이어 움직임을
  이미지 틸트와 원근 곡선으로 전이한다. 사람 pose transfer는 주장하지 않는다.
- **이미지 스타일 참조**: 로컬 이미지의 팔레트·명도·방향을 분석해 네이티브
  title card와 Typography 색에 반영한다. 정체성 또는 전체 화풍 생성은 아니다.
- **연속성 검사**: 후속 수정에서 기존 source URI와 reference ID, 부모 관계,
  레이어 시간 범위를 검사하고 대화 이력을 composition metadata에 남긴다.
- **출처 기록**: 로컬 참조의 크기·mtime·제한된 content hash를 기록하고
  `motion.ai.provenance.inspect`로 확인한다. 서명 키가 없으므로 C2PA 서명
  완료라고 표시하지 않는다.

남은 생성 모델 경계:

- 기본 설치는 새 픽셀/영상, 새 캐릭터 행동, 배경 환경을 생성하지 않는다.
- 외부 생성 공급자가 만든 이미지/영상은 동일 reference 계약으로 받아
  분해·합성·키프레임 편집할 수 있다.
- Gemini Omni와 같은 물리적 자연스러움, 임의 객체 삽입, 캐릭터 정체성
  보존을 제품 주장으로 사용하려면 실제 vision/generative provider와 별도
  품질 평가가 필요하다.

공식 참고:
https://blog.google/intl/ko-kr/company-news/technology/gemini-omni-kr/

## 구현 상태 (2026-07-24)

- AIG0 계약 기준선 구현: 기존 Tiger Studio AI provider 선택, 준비 상태,
  deterministic fallback, JSON-only, Review-before-Apply 경계를 재사용한다.
- AIG1 1차 구현: 이미지/텍스트/오디오/영상 reference 수집, 로컬 파일 사실
  확인, 오디오 비트, 영상 camera/layer optical-flow 분석을 지원한다.
  의미 기반 이미지 이해나 사람 pose transfer는 아직 주장하지 않는다.
- AIG1 이미지 분해 제품 경로 구현: `image_decomposition.py`가 source alpha,
  Basic Local 또는 선택형 SAM 공급자로 배경과 주·보조 피사체를 분리하고,
  마스크 무결성, Layer Graph, 선택적 로컬 OCR, 공용 depth, 배경 복원과
  카메라 이동 제한을 포함한 regenerable RGBA/mask/depth cache를 만든다.
  AI Workspace의 `Explode image layers`, 고급 옵션, `Refine Layers`와
  `motion.ai.reference.decompose`, `motion.ai.layer.*` Action이 같은 서비스를
  사용한다.
  불투명 단일 이미지에는 이름·박스와 선택적 전경/배경 포인트를 가진
  `object_hints`를 전달해 캐릭터·자동차 등 여러 객체를 독립 GrabCut
  마스크로 추출할 수 있다. 연결되지 않은 다리·소품 같은 검수된 객체 파트도
  하나의 편집 레이어로 보존한다. 검수된 clean plate는
  `motion.ai.background.replace`로 교체할 수 있다.
  박스가 없으면 OpenCV가 의미 없는 전경 후보를 제안하며, 사용자 설치
  Ultralytics 모델이 있을 때만 의미 라벨을 자동 제안한다. 추출 알파는
  edge-aware local trimap 매팅을 거친다.
- AIG2 1차 구현: versioned Creative Brief와 Beat Storyboard를 생성하고 엄격히 검증한다.
- AIG3 구현: storyboard를 native Image/Typography/Vector/Behavior 레이어로
  컴파일하고, 분해된 배경/피사체/텍스트에 depth-weighted 2.5D parallax,
  Ken Burns scale, staggered fade/pop을 적용한다. Clean, Dynamic, Collage
  후보는 강체·부모 잠금과 사용자 피벗을 보존한다. 이미지 소스 파라미터의
  `tilt_x`, `tilt_y`, `perspective`도 시간축에서 평가되어 객체별 X/Y축 원근
  회전이 Preview와 Export에 동일하게 반영된다. Image Inspector, Timeline,
  Graph, Action이 같은 소스 키프레임을 편집한다.
- AIG4 구현: AI Workspace가 하나의 provider plan에서 Clean/Dynamic/
  Collage 후보 3개를 만들고 가로 candidate strip에서 비교한다. 실제 공유
  렌더러로 대표 프레임과 썸네일을 만들며 composition/candidate content hash로
  preview cache를 재사용한다. 후보 레이어 보정 후 현재 후보만 재컴파일하며
  `motion.ai.candidate.preview`도 실제 PNG 검토 프레임을 만든다.
- AIG5 구현: stable layer ID와 base revision을 사용하는 scope-aware patch를
  계획하고 변경 전/후 값, 이유, 영향 레이어와 시간 범위를 diff UI에서 검토한
  뒤 한 번의 revision으로 적용한다. 기존 source/reference identity와
  부모·시간 연속성을 검사하고, 대화 이력과 로컬 참조 provenance를 composition
  metadata에 누적한다.
- 아직 남은 제품 단계: 실제 multimodal vision/generative provider와 C2PA
  서명(AIG6),
  설치본 저장/재열기 및 장시간 evidence(AIG7).
  현재 Basic Local 분해는 범용 semantic instance segmentation, 생성형 대형-hole inpaint,
  mesh warp 또는 Gemini Omni 영상 레이어 생성을 주장하지 않는다. 분해 신뢰도가
  낮으면 원본 단일 이미지 레이어로 되돌아간다.
  제품 기본 누끼 경로는 BiRefNet-matting soft alpha와 SAM 2.1 Hiera Small
  보조 마스크로 전환한다. 모델이 없는 환경에서는 `Auto (AI not installed)`와
  설치 버튼을 표시하고 정상 Apply를 막는다. 사용자가 동의한 경우에만 약
  1.3GB 모델은 `external/assets/motion_ai/models`, 선택 런타임 패키지는
  `external/tools/motion_ai/python_packages`에 격리 설치한다.
  GrabCut은 명시적으로 선택하는 `Legacy Basic` 호환 도구로만 유지한다.
  박스 유도 다중 객체 분리와 의미 없는 자동 전경 제안은 구현되었지만, 박스 없이
  객체 종류까지 판별하는 자동 발견은 선택형 로컬 검출기 또는 향후 동의형 Vision
  공급자가 필요하다.

구현 파일은 `app/motion_designer/ai_generation.py`와
`app/motion_designer/image_decomposition.py`, provider 공용 경계는
`app/ai_providers.py`, Action/MCP 표면은
`app/actions/motion_ai_generation_namespace.py`이다.
세부 이미지 레이어 제품 계약은
`docs/MOTION_AI_LAYERED_IMAGE_PRODUCT_PLAN_KO.md`를 따른다.

작성일: 2026-07-23  
상태: 제품 기획 및 구현 기준 초안  
대상: Tiger Studio Motion Designer  
작업명: `AI Motion Director`

연관 문서:

- `docs/MOTION_DESIGNER_PRODUCT_PLAN_KO.md`
- `docs/MOTION_DESIGNER_ARCHITECTURE.md`
- `docs/MOTION_DESIGNER_MILESTONES_KO.md`
- `SPEC.md`

## 1. 한 줄 정의

사용자가 프롬프트와 1~8장의 이미지만 넣으면 AI가 이미지의 역할과 스타일을
분석하고, 장면 구성과 타이밍을 설계한 뒤, Tiger Studio에서 다시 편집할 수 있는
레이어·키프레임·텍스트·이펙트·오디오 기반 Motion Composition을 만드는 기능이다.

## 2. 제품 목표

입력은 Google Gemini Omni처럼 단순하게 만들되 결과는 생성 영상 한 장으로 끝내지
않는다. Tiger Studio의 강점은 AI가 만든 결과를 다음 상태로 돌려주는 것이다.

- 모든 제목과 자막은 수정 가능한 Typography 레이어다.
- 입력 이미지는 원본을 보존한 Media Pool 자산과 개별 레이어다.
- 장면 전환, 카메라, 도형, 마스크, 파티클은 수정 가능한 Motion 데이터다.
- 3D, Live2D, Spine, MMD, VRM 자산은 기존 전용 렌더러를 유지한다.
- 음악, TTS, 자막, 오디오 반응은 Composer·Voice Lab·Sound Editor 계약을 재사용한다.
- 프리뷰와 최종 출력은 같은 Motion 평가 결과와 OpenGL 렌더 경로를 사용한다.
- 생성 후 “사진 2를 마지막에”, “제목을 천천히”, “캐릭터는 빼줘”처럼 대화로
  수정해도 전체 영상을 다시 생성하지 않고 구조화된 Composition patch를 적용한다.

## 3. 조사에서 가져올 원칙

Google Gemini Omni는 텍스트·이미지·영상·오디오 참조를 하나의 결과로 결합하고,
이전 결과의 맥락을 유지하며 단계적으로 대화 편집하는 방식을 전면에 둔다. 스타일과
모션 참조를 다른 대상에 옮기는 사용 사례도 공식적으로 제시한다.

Google Labs Pomelli는 참조 이미지뿐 아니라 색상, 폰트, 말투, 기존 시각 자산을
하나의 지속적인 브랜드 문맥으로 만들고, 템플릿 선택·생성·후속 편집을 분리한다.

Tiger Studio는 이 두 원칙을 다음처럼 해석한다.

1. **입력은 간단하게:** 프롬프트, 이미지, 선택적 오디오만 받는다.
2. **문맥은 지속적으로:** 프로젝트별 `Creative DNA`를 저장한다.
3. **계획과 생성은 분리:** 브리프와 스토리보드를 먼저 검토할 수 있다.
4. **출력은 편집 가능하게:** 가능한 요소는 네이티브 Motion 레이어로 만든다.
5. **대화 수정은 누적되게:** 안정된 레이어 ID를 대상으로 patch를 만든다.
6. **생성 미디어는 선택적으로:** 외부 영상 생성 모델이 없어도 기본 기능이 동작한다.

참고 자료:

- Google DeepMind Gemini Omni: https://deepmind.google/models/gemini-omni/
- Google Labs Pomelli: https://blog.google/innovation-and-ai/models-and-research/google-labs/pomelli/
- Pomelli Photoshoot: https://blog.google/innovation-and-ai/models-and-research/google-labs/pomelli-photoshoot/

## 4. 제품 포지션

### 4.1 기본 모드는 AI 편집 가능한 모션 그래픽이다

기본 생성 결과는 이미지-투-비디오 모델이 만든 납작한 MP4가 아니다. AI가
Motion Designer의 기능을 조합해 만든 프로젝트다.

```text
Prompt + References
        ↓
Creative Brief
        ↓
Beat Storyboard
        ↓
Motion Composition Plan
        ↓
Validated Layers / Keyframes / Behaviors / Audio Cues
        ↓
OpenGL Preview / Export
```

### 4.2 생성형 영상은 보조 레이어다

외부 생성형 영상 공급자가 연결된 경우 다음 용도로만 선택적으로 사용한다.

- 배경 plate
- 실사 또는 스타일 변환이 필요한 짧은 장면
- 복잡한 유체·연기·환경 전환
- 제공된 영상에 대한 생성형 확장 또는 대체 shot

브랜드 로고, 제목, 가격, CTA, 자막과 정확한 UI 문구는 생성 영상 안에 굽지 않고
Tiger Typography·Vector 레이어로 올린다. 텍스트 정확성과 수정 가능성을 지키기
위한 제품 규칙이다.

### 4.3 세 가지 생성 수준

| 수준 | 이름 | 결과 | 외부 생성 모델 |
|---|---|---|---|
| L0 | Smart Layout | 입력 이미지를 템플릿과 규칙으로 배치 | 불필요 |
| L1 | AI Motion Composition | 멀티모달 AI가 브리프·스토리보드·레이어 계획 생성 | 계획 공급자 필요 |
| L2 | Hybrid Generative Motion | 생성 이미지/영상 plate와 네이티브 Motion 결합 | 미디어 공급자 선택 |

UI와 evidence는 실제 사용된 수준을 표시한다. L0 fallback을 사용하면서 L1/L2라고
표현하지 않는다.

## 5. 목표 사용자와 대표 결과

### 서브컬쳐 크리에이터

- 캐릭터 이미지 3장으로 8초 소개 영상
- MMD/VRM 배우와 키비주얼을 결합한 방송 시작 화면
- 앨범 아트와 가사로 음악 타이틀 시퀀스
- 일러스트의 일부를 마스크로 분리한 2.5D 카메라 모션

### 영상·광고 제작자

- 제품 사진 4장으로 9:16 숏폼 광고
- 로고, 제품, 사용 장면으로 6초 bumper
- 기존 영상과 이미지로 기능 설명 callout
- 한 번의 입력으로 16:9, 9:16, 1:1 변형 생성

### 발표·교육 제작자

- 사진과 키워드로 시간 기반 인포그래픽
- 3D 제품과 캡션이 움직이는 설명 장면
- PPT Maker 페이지를 모션 버전으로 변환

## 6. 핵심 사용자 흐름

### 6.1 최초 생성

1. 사용자가 Motion Designer에서 `AI Create`를 연다.
2. 이미지 1~8장을 프롬프트 영역에 드롭한다.
3. “7초, 푸른 네온, 캐릭터는 중앙에 두지 말고, 마지막에 TIGER STUDIO”처럼
   자연어로 요청한다.
4. 필요하면 출력 비율, 길이, 용도만 선택한다.
5. 시스템이 이미지마다 `주인공`, `제품`, `배경`, `스타일`, `로고`, `텍스처`,
   `모션 참조` 역할을 제안한다.
6. 시스템이 한 문단 브리프와 3~6개 beat 스토리보드를 만든다.
7. 사용자가 바로 생성하거나 브리프의 역할·문구·순서를 수정한다.
8. AI가 2~3개의 편집 가능한 Composition 후보를 컴파일한다.
9. 선택된 후보가 캔버스와 타임라인에 나타난다.

### 6.2 대화형 수정

1. 사용자가 결과를 재생한다.
2. “두 번째 사진을 더 오래”, “글자에 글로우 빼”, “4초에 비트 컷”,
   “9:16에서도 얼굴이 안 잘리게”라고 입력한다.
3. AI는 전체 Composition이 아니라 대상 layer/property/time 범위를 지정한 patch를
   만든다.
4. 변경 전후 diff와 예상 영향이 표시된다.
5. Apply하면 하나의 undo transaction으로 적용된다.
6. Undo하면 생성 전 상태로 정확히 돌아간다.

### 6.3 현재 프로젝트 자산 활용

프롬프트 영역은 로컬 파일뿐 아니라 다음 항목의 drag-and-drop을 받는다.

- Media Pool 이미지·영상·3D·Live2D·Spine·MMD·VRM
- 메인 영상 타임라인 clip 또는 선택 구간
- Typography preset과 기존 텍스트 레이어
- PPT Maker의 페이지·도형·표·차트
- Composer 음악 cue와 Sound Editor clip
- Voice Lab TTS·자막·단어 타이밍

## 7. 입력 계약

### 7.1 필수 입력

- 자연어 프롬프트
- 이미지 1장 이상 또는 현재 프로젝트의 선택된 자산

### 7.2 선택 입력

- 길이: 기본 8초, 권장 3~30초
- 화면 비율: 16:9, 9:16, 1:1, 프로젝트 비율
- 용도: 타이틀, 캐릭터 소개, 제품 광고, 음악 비주얼, 방송 스팅어, 설명 그래픽
- 분위기: 절제, 화려, 귀여움, 고급, 다크, 에너지, 시네마틱
- 텍스트: 제목, 부제, CTA, 가격, 이름, 크레딧
- 음악·음성·비트 정보
- 출력 목표: 메인 타임라인, PPT, 방송, 투명 영상, 일반 영상
- 품질 모드: 빠른 초안, 균형, 최종

### 7.3 참조 이미지 역할

각 이미지는 AI가 역할을 제안하지만 사용자가 즉시 바꿀 수 있다.

| 역할 | 의미 | 기본 처리 |
|---|---|---|
| Hero | 주인공/제품 | 가장 긴 노출과 안전 프레이밍 |
| Supporting | 보조 장면 | cutaway·collage·transition |
| Background | 배경 | cover crop, 낮은 시각 우선순위 |
| Style | 색·재질·조명 참조 | 직접 레이어로 쓰지 않을 수 있음 |
| Logo | 브랜드 로고 | 비율 보존, 과도한 효과 금지 |
| Character | 인물/캐릭터 | 얼굴·실루엣 보호 |
| Texture | 질감·패턴 | mask 또는 blend source |
| Motion | 움직임·카메라 참조 | 경로·속도·리듬 분석용 |

역할을 지정하지 않은 경우 `auto`로 저장하며, 분석 결과에는 confidence와 근거를
포함한다. 낮은 confidence의 역할은 자동 적용 전에 사용자에게 표시한다.

## 8. Creative DNA

프로젝트별로 반복 사용 가능한 시각 문맥을 저장한다.

```text
CreativeDNA
  colors[]
  fonts[]
  logos[]
  title_hierarchy
  tone_keywords[]
  preferred_motion
  prohibited_motion
  safe_area_policy
  character_framing_policy
  audio_identity
  source_references[]
```

초기 버전은 사용자가 명시적으로 저장한 값만 사용한다. 웹사이트를 자동 수집하거나
외부 URL을 분석하는 기능은 별도 동의와 네트워크 정책이 준비되기 전에는 포함하지
않는다.

서브컬쳐용 기본 정책은 다음과 같다.

- 얼굴과 눈을 제목이나 장식으로 가리지 않는다.
- character reference의 비율과 고유 색을 임의로 바꾸지 않는다.
- 로고와 정확한 텍스트는 생성 영상에 굽지 않는다.
- 검은 외곽선과 bloom을 모든 자산에 일괄 적용하지 않는다.
- MMD/VRM/Live2D/Spine은 각 전용 재질·모션 계약을 유지한다.

## 9. AI 생성 파이프라인

### 9.1 Stage A - Intake

- 파일 존재, 해상도, alpha, 색공간, 방향 정보를 검사한다.
- 중복 자산을 fingerprint로 합친다.
- 원본은 변경하지 않고 project asset reference를 만든다.
- remote provider 전송 전에 대상 파일과 개인정보 경고를 표시한다.

### 9.2 Stage B - Reference Analysis

- 이미지 caption과 주요 피사체를 추정한다.
- 얼굴·제품·로고·텍스트·배경·여백을 영역 단위로 표시한다.
- 대표 색, 대비, 밝기, edge density, 시각 무게를 분석한다.
- saliency와 안전 crop 후보를 만든다.
- 선택적으로 segmentation mask와 depth proxy를 만든다.
- 분석 결과는 캐시하며 원본 이미지 픽셀을 덮어쓰지 않는다.

### 9.3 Stage C - Creative Brief

AI는 자유 문장 대신 다음 구조를 반환한다.

```json
{
  "intent": "character_intro",
  "duration_ms": 8000,
  "aspect_ratio": "9:16",
  "headline": "TIGER STUDIO",
  "visual_direction": ["neon", "elegant", "fast"],
  "pacing": "build_then_hit",
  "reference_roles": [],
  "must_keep": [],
  "must_avoid": [],
  "audio_strategy": "beat_sync",
  "output_target": "timeline"
}
```

브리프가 빠진 텍스트, 모순된 길이, 지원하지 않는 비율을 포함하면 Composition
생성 전에 사용자에게 보여준다.

### 9.4 Stage D - Beat Storyboard

장면을 고정 shot이 아니라 시간 beat로 나눈다.

```text
Beat 1  0.0-1.2s  Establish / background + motif
Beat 2  1.2-3.0s  Hero reveal / camera push
Beat 3  3.0-5.8s  Supporting images / rhythmic cuts
Beat 4  5.8-8.0s  Title resolve / logo + CTA
```

각 beat는 다음 데이터를 갖는다.

- 목적과 핵심 메시지
- 사용 reference ID
- layer 역할과 z-order
- 진입·유지·퇴장 방식
- camera framing
- transition
- audio cue 또는 beat index
- 필수 텍스트
- 예상 renderer cost

### 9.5 Stage E - Motion Composition Compiler

Storyboard를 기존 Motion schema로 컴파일한다.

- 이미지와 영상: `SourceRef`
- 텍스트: native Typography
- 배경과 장식: Vector Shape·Gradient·Mask
- 움직임: keyframe·Bezier·Behavior
- 반복 요소: Repeater·Particle
- 3D: AR/PBR camera·light·material packet
- 캐릭터: 기존 Live2D·Spine·MMD·VRM source adapter
- 오디오: Composer·Voice·audio-reactive binding
- 출력: 기존 color/output preflight

AI가 raw Python, JavaScript, shader code를 생성하거나 실행하지 않는다. 허용된 schema,
template, behavior, effect, action ID만 사용한다.

### 9.6 Stage F - Deterministic Validation

Provider 결과는 적용 전에 다음 검사를 통과해야 한다.

- Motion schema와 stable ID
- 부모·expression·dependency cycle
- media path와 relink 상태
- layer 시간 범위와 composition 길이
- safe area와 글자 overflow
- 이미지 crop으로 인한 얼굴·제품 절단
- unsupported effect와 export loss
- AR/PBR·캐릭터 renderer readiness
- broadcast realtime/cache 등급
- GPU·메모리 예상 비용
- Preview/Export 지원 여부

검증 실패는 조용히 삭제하지 않는다. repair 가능한 항목, bake가 필요한 항목,
사용자 결정을 요구하는 항목을 구분한다.

### 9.7 Stage G - Candidate Preview

같은 brief에서 기본 3개 후보를 만든다.

- `Clean`: 여백과 타이포그래피 중심
- `Dynamic`: 빠른 cut, scale, parallax 중심
- `Character/Product Focus`: hero 자산 노출 중심

후보는 별도 Composition revision 또는 임시 proposal로 유지한다. 사용자가 선택하기
전에는 현재 프로젝트를 변경하지 않는다. 저해상도 preview는 캐시할 수 있지만 최종
선택 결과는 동일한 OpenGL render graph로 다시 확인한다.

### 9.8 Stage H - Apply and Iterate

- 선택 후보는 하나의 undo transaction으로 적용한다.
- 생성된 각 layer에 request, reference, beat, provider provenance를 기록한다.
- 후속 대화는 전체 replacement가 아닌 stable-ID patch를 만든다.
- patch는 `add`, `update`, `delete`, `reorder`, `retime`, `replace_source`처럼 기존
  action으로 표현한다.
- Apply 전 diff에 layer 수, 길이, 삭제 대상, bake/cache 비용을 표시한다.

## 10. UI/UX 기획

### 10.1 진입점

- Motion Designer toolbar의 AI 아이콘
- 빈 Composition의 캔버스 하단 prompt composer
- 기존 AI Workspace의 `Expand` 명령
- Media Pool 선택 항목의 `Create Motion with AI`
- 메인 타임라인 선택 구간의 `Create Motion from Selection`

새로운 독립 프로그램을 만들지 않는다. Motion Designer 안에서 생성하고 즉시
타임라인·레이어·그래프 편집으로 넘어가야 한다.

### 10.2 Prompt Composer

```text
┌──────────────────────────────────────────────────────────────┐
│ [img1 Hero] [img2 Style] [img3 Supporting]       + Attach   │
│ 캐릭터 소개 8초. 푸른 네온, 마지막에 TIGER STUDIO...        │
│ 9:16  |  8s  |  Character Intro  |  Balanced      Generate │
└──────────────────────────────────────────────────────────────┘
```

- 참조 이미지는 한 줄 가로 strip으로 표시한다.
- 각 썸네일에는 삭제, 순서 변경, 역할 menu가 있다.
- prompt는 여러 줄 입력이 가능하고 `Ctrl+Enter`로 계획한다.
- 비율·길이·용도만 composer에 노출하고 세부 옵션은 brief review에서 다룬다.
- `Generate` 전에 현재 provider 수준과 외부 전송 여부를 표시한다.

### 10.3 Brief Review

브리프는 긴 설정 form이 아니라 편집 가능한 요약 영역이다.

- 핵심 문구
- reference 역할과 순서
- 3~6개 beat
- 스타일·색·폰트
- 출력 비율과 길이
- 생성 미디어 사용 여부
- 예상 비용·시간·cache 요구

`Create Draft`를 누르기 전에는 Composition을 변경하지 않는다.

### 10.4 후보 비교

- 캔버스 위에서 한 후보씩 실제 재생한다.
- 하단 candidate strip으로 전환한다.
- timeline과 layers는 선택 후보의 read-only proposal을 보여준다.
- `Use This` 후에만 일반 편집 상태가 된다.
- 후보별 prompt를 다시 입력하는 카드 UI는 만들지 않는다.

### 10.5 대화 수정

생성 후 prompt composer는 `Revise selected composition...` 상태로 바뀐다.

- 선택 레이어가 있으면 해당 레이어가 기본 범위다.
- 선택이 없으면 전체 composition이 범위다.
- “현재 구간”, “2~4초”, “Beat 3” 범위를 명시할 수 있다.
- AI가 삭제 또는 source 교체를 제안하면 review가 필수다.
- diff 적용 후 자동 재생은 변경 구간 앞 0.5초부터 시작한다.

### 10.6 진행 상태

막연한 spinner 대신 현재 단계를 보여준다.

```text
Analyzing references 3/4
Building creative brief
Planning 4 beats
Compiling editable layers
Validating output
Rendering preview 2/3
```

취소는 현재 job을 중단하고 기존 Composition을 그대로 유지한다.

## 11. 데이터 모델

### 11.1 MotionAIGenerationRequest v2

기존 `MotionAIRequest`를 즉시 파괴적으로 변경하지 않고 v2 request를 추가한다.

```text
MotionAIGenerationRequest
  id
  composition_id
  prompt
  references[]
    id / kind / uri / role / order / weight / crop_policy / consent
  target
    duration_ms / width / height / fps / output_target
  creative_dna_id
  generation_level
  planner_provider
  media_provider
  privacy_policy
```

### 11.2 MotionCreativeBrief

```text
MotionCreativeBrief
  schema / id / request_id / revision
  intent / audience / message
  headline / subtitle / cta
  visual_direction[]
  pacing / audio_strategy
  reference_assignments[]
  beats[]
  must_keep[] / must_avoid[]
  warnings[] / assumptions[]
```

### 11.3 MotionGenerationProposal

```text
MotionGenerationProposal
  schema / id / request_id / brief_id
  candidate_id / provider
  composition
  action_plan[]
  source_manifest[]
  validation
  estimated_cost
  provenance
  preview_cache
```

### 11.4 MotionCompositionPatch

```text
MotionCompositionPatch
  schema / id / base_composition_id / base_revision
  scope / prompt
  operations[]
  validation
  summary / warnings
```

base revision이 달라지면 자동 적용하지 않는다. 재계획하거나 사용자가 conflict를
해결한다.

## 12. Provider 아키텍처

한 공급자가 모든 기능을 제공한다고 가정하지 않는다.

```text
Reference Analyzer ─┐
Multimodal Planner ─┼─> Creative Brief / Storyboard / Action Plan
Image Generator ────┤
Video Generator ────┤
Audio Generator ────┘
                         ↓
                  Tiger Validation
                         ↓
               Motion Composition Compiler
```

### 12.1 Capability negotiation

각 provider는 다음 capability를 명시한다.

- text reasoning
- image understanding
- multiple image reference
- image generation/editing
- video generation/editing
- style reference
- motion reference
- audio reference/generation
- structured JSON output
- conversation continuation
- cancellation/progress

요청을 만족하지 못하면 자동으로 과장된 fallback을 사용하지 않는다. 예를 들어
image understanding이 없는 local layout은 `Smart Layout`이라고 표시한다.

### 12.2 Provider 출력 경계

- provider는 `.tgp`와 editor object를 직접 수정하지 않는다.
- provider는 versioned brief/proposal/patch JSON만 반환한다.
- 모든 path와 action ID를 Tiger가 검증한다.
- raw shell, Python, JavaScript, plugin code는 허용하지 않는다.
- provider 응답 원문은 민감 정보를 제거한 뒤 선택적으로 진단에 보관한다.
- timeout, retry, cancel, rate limit, estimated cost를 job metadata에 기록한다.

### 12.3 로컬 fallback

현재 `local_layout`은 유지한다. 다만 다음처럼 정확히 표현한다.

- 이미지를 grid/full-bleed로 배치하는 deterministic fallback
- 제한된 fade/slide/pop prompt token 처리
- 이미지 의미, 고급 스타일, narrative 이해를 주장하지 않음
- cloud/offline provider 실패 시 사용자가 선택한 경우에만 fallback

## 13. 생성 자산과 저장 정책

- 입력 원본은 수정하지 않는다.
- 사용자가 선택한 생성 이미지·영상은 Media Pool의 durable managed asset이 된다.
- segmentation, depth, caption, low-resolution preview는 재생성 가능한 cache다.
- `debugCapture`는 QA evidence에만 사용하고 프로젝트 의존 자산을 저장하지 않는다.
- provider asset은 request ID, provider, model, prompt hash, source reference ID를 가진다.
- 동일 source와 request의 중복 생성은 hash로 식별한다.
- 프로젝트 이동 시 기존 Motion relink 계약으로 복구한다.
- cloud 전송 대상, 생성 결과의 이용 조건, provenance를 inspect할 수 있어야 한다.

## 14. Action/MCP 설계

기존 액션:

- `motion.ai.plan`
- `motion.ai.apply`

추가할 액션:

- `motion.ai.reference.analyze`
- `motion.ai.brief.create`
- `motion.ai.brief.update`
- `motion.ai.storyboard.generate`
- `motion.ai.candidate.generate`
- `motion.ai.candidate.list`
- `motion.ai.candidate.select`
- `motion.ai.preview.render`
- `motion.ai.patch.plan`
- `motion.ai.patch.apply`
- `motion.ai.job.status`
- `motion.ai.job.cancel`
- `motion.ai.provenance.inspect`

### 액션 규칙

- analyze, brief, storyboard, candidate generation은 현재 프로젝트를 변경하지 않는다.
- candidate select와 patch apply는 reviewable mutation이다.
- delete, source replacement, generation asset overwrite는 destructive confirmation을
  요구한다.
- 모든 mutation은 document controller의 한 undo transaction을 사용한다.
- 장시간 provider/render 작업은 async job ID를 반환한다.
- MCP와 UI는 같은 adapter/service를 호출한다.
- editor owner가 필요한 액션과 ownerless 분석 액션을 구분한다.

## 15. 기존 Tiger Studio 기능 재사용표

| 필요한 기능 | 기존 구현 | 계획 |
|---|---|---|
| 이미지·텍스트 drop | `ui/ai_panel.py`, `ai_workspace.py` | reference role/order 확장 |
| 계획 후 적용 | `motion.ai.plan/apply` | brief/candidate/patch로 세분화 |
| 레이어 schema | `schema.py` | 그대로 사용 |
| 키프레임·curve | evaluator, graph editor | compiler target |
| Vector/Typography | M6 구현 | 네이티브 텍스트·장식 생성 |
| Mask/Tracking | M6 구현 | subject cutout/parallax 연결 |
| Audio reactive | M7 구현 | beat/pacing 연결 |
| AR/PBR | M8 구현 | 제품·카메라 후보 생성 |
| Live2D/Spine/MMD/VRM | M9 구현 | 캐릭터 scene 후보 생성 |
| Template/Behavior/Particle | M10 구현 | 후보 기본 문법 |
| Color/Export/Recovery | M11 구현 | preflight·undo·복구 |
| Plugin/Template pack Action | M12 관리 기반 | 확장 template source |

## 16. 품질 기준

### 16.1 구조 품질

- 생성된 composition validation error 0개
- missing source와 invalid path 0개
- stable ID 중복 0개
- undo/redo 후 canonical document 일치
- 사용자가 입력한 정확한 제목·CTA의 문자 변형 0개
- 지원하지 않는 효과의 조용한 누락 0개

### 16.2 시각 품질

- 제목과 얼굴·제품의 비의도적 겹침 0개
- safe area 밖 필수 텍스트 0개
- 이미지 비율 왜곡 0개
- alpha fringe와 검은 halo 0개
- 명시하지 않은 전역 bloom·검은 outline 적용 0개
- 16:9, 9:16, 1:1에서 주요 피사체 보호

### 16.3 시간 품질

- beat 경계가 composition duration을 초과하지 않음
- layer in/out과 transition overlap이 유효함
- 오디오 cue와 시각 hit의 오차 목표 1 frame 이하
- 대화 patch는 선택 범위 밖 keyframe을 임의로 변경하지 않음

### 16.4 렌더 품질

- Preview/Export 동일 시점 parity 유지
- 제품 evidence에서 software renderer 0
- 캐릭터·AR/PBR는 기존 전용 GPU renderer 사용
- 생성 preview가 실패해도 마지막 유효 frame과 진단 상태 유지
- 장시간 작업 취소 후 partial artifact와 project mutation이 남지 않음

### 16.5 AI 품질 측정

- prompt constraint 준수율
- reference 사용/누락 정확도
- image role 분류 정확도
- 사용자 후보 선택률
- 첫 생성 후 수정 횟수
- patch 적용 성공률
- provider fallback 비율
- 생성 후 수동으로 삭제된 layer 비율

## 17. QA corpus

실제 사용자 입력과 유사한 최소 corpus를 만든다.

1. 캐릭터 이미지 3장 + 한국어 소개 prompt
2. 제품 사진 4장 + 9:16 광고 prompt
3. 로고 + 배경 + 제품 + 정확한 가격/CTA
4. 앨범 아트 + 음악 cue + 가사
5. 3D GLB + 제품 사진 + 카메라 회전
6. MMD/VRM + 배경 이미지 + 방송 시작 prompt
7. 투명 PNG 여러 장 + collage prompt
8. 저해상도/세로/가로 혼합 이미지
9. 서로 충돌하는 prompt와 reference 역할
10. provider timeout·invalid JSON·부분 asset failure

각 case는 prompt, references, expected constraints, 허용/금지 요소, golden structural
report를 가진다. 생성형 provider의 픽셀 결과를 고정 golden으로 강제하지 않고 구조,
문구, 레이아웃 안전성, 사용 자산, action plan, render validity를 판정한다.

## 18. 구현 트랙

기존 Motion M0~M12와 혼동하지 않도록 `AIG` 트랙으로 관리한다.

### AIG0 - 계약과 기준선

- v2 request, reference role, brief, storyboard, candidate, patch schema
- 기존 `MotionAIRequest/Proposal` migration
- local layout 기준선과 현재 UI evidence
- Action ID와 provider security boundary

완료 조건: schema round-trip, unknown field 보존, invalid provider payload 격리.

### AIG1 - Reference Intake와 Analysis

- 이미지 1~8장 role/order UI
- Media Pool·timeline drag-and-drop
- 해상도·alpha·palette·saliency·safe crop
- durable source와 disposable analysis cache 분리

완료 조건: 실제 혼합 이미지 corpus에서 원본 보존, role 수정, crop evidence 통과.

### AIG2 - Brief와 Storyboard

- prompt parser/provider adapter
- Creative DNA
- 3~6 beat storyboard
- 정확한 text extraction과 review UI

완료 조건: plan 단계가 project를 변경하지 않고 모든 prompt constraint를 report.

### AIG3 - Editable Composition Compiler

- beat-to-layer compiler
- template, typography, vector, behavior, particle 연결
- 16:9/9:16/1:1 variant
- deterministic repair와 preflight

완료 조건: 10개 corpus가 validation error 없이 재생·undo·export 가능.

### AIG4 - Candidate Preview와 선택

- [x] 2~3개 candidate
- [x] 실제 공유 렌더러 기반 low-resolution preview job/cache
- [x] 가로 candidate strip과 실제 canvas proposal 적용
- [x] 선택 전 project immutability

완료 조건: 후보 선택·취소·재생성에서 임시 composition과 cache가 누수되지 않음.

### AIG5 - Conversational Patch

- [x] scope-aware patch planner
- [x] stable layer/property/time targeting
- [x] 변경 전/후 diff review와 영향 시간 범위
- [x] conflict/revision 처리
- [x] one-transaction apply/undo

완료 조건: 50개 한국어/영어 수정 prompt에서 범위 밖 mutation 0개.

### AIG6 - Hybrid Generated Media

- image/video provider capability broker
- async progress/cancel/retry
- generated plate import와 provenance
- 네이티브 Typography overlay
- privacy/cost/terms 안내

완료 조건: provider 부재 시 기본 편집 기능 정상, 실패 시 project mutation 0개.

### AIG7 - 제품화

- Action/MCP 전체 노출
- installed-build smoke
- 실제 OpenGL Preview/Export evidence
- long-run cache/memory test
- accessibility와 오류 UX
- public claim/evidence matrix

완료 조건: `AI Motion Generation Product` gate와 현재-source installer smoke 통과.

## 19. 첫 구현 순서

1. `ai_workspace.py` v2 schema를 별도 파일로 분리한다.
2. reference role/order/weight와 target output 계약을 추가한다.
3. 현재 local layout을 v2 brief/storyboard를 거치는 adapter로 감싼다.
4. brief와 storyboard가 project를 수정하지 않는 테스트를 작성한다.
5. storyboard-to-composition compiler를 focused module로 만든다.
6. 기존 `motion.ai.plan/apply`를 호환 facade로 유지한다.
7. 새 Action/MCP namespace를 추가한다.
8. AI panel에 role strip, target, progress를 연결한다.
9. 실제 이미지 corpus로 UI/렌더 evidence를 만든다.
10. 그 뒤에만 외부 multimodal/video provider를 연결한다.

외부 모델부터 연결하면 provider마다 다른 결과를 UI와 project schema가 직접 떠안게
된다. 먼저 Tiger의 brief, storyboard, compiler, validation 계약을 고정해야 한다.

## 20. MVP와 제품 품질의 경계

### 첫 사용 가능 버전

- 프롬프트 + 이미지 1~8장
- 16:9, 9:16, 1:1
- 3~15초
- 캐릭터 소개, 제품 광고, 로고 리빌, 음악 타이틀
- editable Typography/Image/Vector/Behavior composition
- 2개 candidate
- 한국어/영어 prompt
- plan review와 one-step apply/undo
- local layout + 한 개의 multimodal planner

### 제품 품질 버전

- Creative DNA
- 3개 candidate와 variant propagation
- conversational patch
- audio/character/3D 계획
- hybrid generated media
- job cancel/retry/resume
- provenance, privacy, 비용 표시
- 실제 corpus와 installed-build evidence

MVP UI가 보인다는 이유로 이미지 의미 이해, Omni 수준의 영상 생성, provider 간
동일 품질, 모든 이미지의 정확한 segmentation을 주장하지 않는다.

## 21. 주요 위험과 대응

| 위험 | 대응 |
|---|---|
| AI가 텍스트를 이미지에 구워 오타 생성 | 필수 문구는 native Typography로 강제 |
| 이미지 정체성 훼손 | 입력 원본 레이어 우선, 생성 변형은 명시적 opt-in |
| 결과가 매번 달라 QA 불가능 | 구조·constraint·render validity 중심 QA |
| provider가 project를 망가뜨림 | proposal/patch JSON만 받고 Tiger가 검증·적용 |
| 비싼 generation 반복 | brief review, candidate budget, cache, cost preview |
| cloud 전송 개인정보 문제 | 파일별 consent와 전송 목록 표시 |
| 3D/캐릭터를 generic renderer로 처리 | 기존 전용 adapter와 renderer boundary 고정 |
| 납작한 영상이라 수정 불가 | native layer 우선, generated plate는 보조 |
| 너무 많은 옵션으로 입력이 복잡해짐 | composer에는 prompt·image·ratio·duration만 노출 |
| local fallback을 AI로 과장 | 실제 provider level badge와 evidence 분리 |

## 22. 최종 제품 경험

사용자는 빈 캔버스에서 시작해 복잡한 레이어를 직접 만들 필요가 없다. 이미지 몇
장을 넣고 의도를 말하면 Tiger Studio가 먼저 편집 가능한 초안을 만든다. 사용자는
결과를 재생하고 자연어 또는 기존 Motion Designer 도구로 수정한다. AI는 렌더된
영상의 바깥에 있는 보조 기능이 아니라, Tiger Studio의 레이어·타임라인·액션을
안전하게 조합하는 감독 역할을 한다.

이것이 Gemini Omni식 간단한 입력 경험과 Tiger Studio의 편집 가능성, 캐릭터 자산,
3D, 오디오, PPT, 방송 연동을 동시에 살리는 제품 방향이다.
