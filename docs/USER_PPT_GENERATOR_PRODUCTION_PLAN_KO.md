# TigerCapture PPT 제작기 기획서

작성일: 2026-07-06

이 문서는 TigerCapture 안에 새로 만들 **사용자용 PPT 제작기**의 제품 기획서다.

기존 `review_automation`은 TigerCapture 기능을 설명하기 위한 내부/홍보용 발표자료 자동화다. 이 문서의 PPT 제작기는 그와 다르다. 사용자가 자기 목적을 위해 발표자료를 만들고, TigerCapture의 영상/3D/타이포/효과 자산을 PPT로 가져가는 독립 기능이다.

## 1. 한 줄 정의

```text
TigerCapture PPT 제작기는 영상 편집 타임라인 감각으로 슬라이드, 미디어, 3D 렌더, 타이포, 애니메이션을 조립해 PPTX/영상/PDF 발표자료를 만드는 타임라인 기반 프레젠테이션 스튜디오다.
```

## 2. 왜 만들어야 하는가

일반 PPT 도구는 슬라이드를 잘 만든다. 하지만 TigerCapture가 가진 강점은 다르다.

- 영상 타임라인
- 화면 녹화와 스크린샷
- 자막/타이포그래피
- 컷 편집/줌/효과
- AR/PBR 3D 오브젝트 렌더링
- MMD/Live2D/Spine 같은 액터 렌더링
- 컬러 그레이딩/VFX/노드 처리
- 오디오/나레이션/파형
- AI 액션 자동화

이 자산들은 PowerPoint나 Keynote에 그대로 넣으면 품질이 낮거나 제어가 어렵다. 반대로 TigerCapture 안에서 고품질로 렌더하고, PPT에는 호환 가능한 이미지/비디오/텍스트/차트로 넣으면 강한 차별점이 생긴다.

목표는 PowerPoint를 대체하는 것이 아니다. 목표는 **영상과 3D를 잘 다루는 사람이 훨씬 빠르게 보기 좋은 발표자료를 만들 수 있게 하는 것**이다.

## 3. 제품 포지션

### PowerPoint와의 차이

PowerPoint는 문서 중심이다.

TigerCapture PPT 제작기는 **시간과 장면 중심**이다.

- 슬라이드를 타임라인 클립처럼 배치한다.
- 각 슬라이드 안에 텍스트/이미지/비디오/3D 렌더/액터/효과 레이어를 둔다.
- 재생하면 발표 흐름이 영상처럼 보인다.
- 내보내면 PPTX, PDF, MP4, PNG 슬라이드가 나온다.

### Keynote와의 차이

Keynote는 예쁜 기본값과 전환이 강하다.

TigerCapture는 여기에 **렌더링 자산 생산 능력**을 붙인다.

- AR/PBR로 3D 오브젝트를 예쁘게 렌더해서 슬라이드에 넣는다.
- MMD/Live2D/Spine 캐릭터를 투명 배경 이미지나 영상으로 넣는다.
- 타임라인 장면을 슬라이드 소재로 바로 가져온다.
- 컬러/VFX 처리 전후를 비교 슬라이드로 만든다.

## 4. 핵심 차별점

### 4.1 타임라인 기반 PPT 제작

PPT의 단위는 비디오 프레임이 아니다.

```text
1 PPT 프레임 = 1 슬라이드 클립
```

슬라이드 클립은 시작 시간과 길이를 가진다. 길이는 발표 미리보기, 영상 내보내기, 발표 리듬에 사용된다. PPTX 자체에는 슬라이드 1장으로 저장된다.

### 4.2 TigerCapture 렌더 자산 활용

PowerPoint가 직접 못하는 것은 TigerCapture가 먼저 렌더한다.

- 고품질 3D 렌더
- 그림자/반사/SSAO/IBL이 들어간 AR/PBR 이미지
- 깊이에 의해 가려지는 AR 합성 데모
- MMD toon/bloom/self-shadow 렌더
- Live2D/Spine 캐릭터 프레임
- 글리치/자막/타이포 애니메이션
- 영상 효과 전후 비교

PPT에는 결과물을 PNG/MP4/이미지 시퀀스/일반 비디오로 넣고, 원본 메타데이터는 TigerCapture 프로젝트에 보관한다.

### 4.3 AI와 액션 자동화

사용자는 이렇게 요청할 수 있어야 한다.

```text
이 영상에서 제품 소개 PPT 7장을 만들어줘.
3번 슬라이드를 더 이미지 중심으로 바꿔줘.
이 3D 모델을 표지에 크게 넣고, 어두운 배경에서 금속 느낌을 살려줘.
MMD 캐릭터를 마지막 슬라이드에 넣고 5초 루프 영상으로 만들어줘.
표를 비교 슬라이드로 바꿔줘.
```

내부적으로는 모두 액션으로 처리한다.

## 5. 목표 사용자

### 5.1 크리에이터

유튜브 영상, 쇼츠, 튜토리얼, 스폰서 제안서, 제품 소개 자료를 만든다.

필요 기능:

- 타임라인에서 중요한 장면을 슬라이드로 추출
- 영상 썸네일/줌 장면/자막 스타일 재사용
- 영상과 PPT를 동시에 내보내기

### 5.2 학생/교사

수업 자료, 발표자료, 강의 요약을 만든다.

필요 기능:

- 텍스트를 슬라이드 구조로 자동 변환
- 이미지/동영상/캡처 자료 삽입
- 발표 시간 미리보기
- PDF/PPTX 내보내기

### 5.3 제품/비즈니스 사용자

기획서, 제안서, 비교표, 로드맵, 제품 소개서를 만든다.

필요 기능:

- 템플릿
- 차트/표
- 비교 슬라이드
- 제품 이미지/3D 렌더
- 자동 정렬과 디자인 검증

### 5.4 AI/자동화 사용자

MCP/액션을 통해 PPT를 자동 생성하거나 수정한다.

필요 기능:

- DeckSpec 생성
- 슬라이드 추가/삭제/이동
- 요소 추가/수정
- 템플릿 적용
- PPTX/PDF/MP4 export
- validation report

## 6. 기본 사용자 시나리오

### 시나리오 A: 영상에서 PPT 만들기

1. 사용자가 편집 중인 영상 프로젝트를 연다.
2. 타임라인에서 범위를 선택한다.
3. `PPT 만들기`를 누른다.
4. 목적을 선택한다.
   - 제품 소개
   - 튜토리얼
   - 강의자료
   - 보고서
   - 포트폴리오
5. TigerCapture가 컷, 마커, 줌, 자막, 효과 장면을 분석한다.
6. 슬라이드 초안을 만든다.
7. 사용자가 PPT 타임라인에서 순서와 내용을 수정한다.
8. PPTX/PDF/MP4로 내보낸다.

### 시나리오 B: 3D 제품 소개 PPT 만들기

1. 사용자가 GLB/GLTF/FBX 모델을 가져온다.
2. AR/PBR 뷰어에서 조명, 재질, 카메라, 그림자, 반사를 설정한다.
3. 표지 슬라이드에 3D 렌더를 배치한다.
4. 모델을 회전한 3장짜리 제품 슬라이드를 자동 생성한다.
5. 각 슬라이드에 설명 텍스트와 스펙 표를 붙인다.
6. 고품질 PNG 또는 짧은 MP4 렌더를 PPT에 삽입한다.

### 시나리오 C: 캐릭터 발표자료 만들기

1. 사용자가 MMD/Live2D/Spine 캐릭터를 가져온다.
2. 모션이나 표정을 선택한다.
3. 배경이 투명한 캐릭터 이미지/짧은 영상으로 렌더한다.
4. 강의, 튜토리얼, VTuber식 발표자료에 배치한다.

### 시나리오 D: AI로 초안 만들기

1. 사용자가 주제를 입력한다.
2. 자료를 넣는다.
   - 텍스트
   - 영상
   - 이미지
   - 3D 모델
   - 표/CSV
3. AI가 슬라이드 구조를 만든다.
4. 사용자는 타임라인과 캔버스에서 수정한다.
5. validation report를 보고 깨진 부분을 고친다.

## 7. 화면 구성

첫 화면은 마케팅 화면이 아니라 실제 제작 화면이어야 한다.

```text
+----------------------------------------------------------------+
| 상단: 프로젝트명 / 템플릿 / 미리보기 / 발표 / 내보내기         |
+-------------------+--------------------------------------------+
| 왼쪽 패널          | 중앙 캔버스                                |
| - 아웃라인         | - 현재 슬라이드 편집                       |
| - 미디어풀         | - 오브젝트 선택/이동/정렬                  |
| - 템플릿           | - 안전영역/가이드                          |
+-------------------+-------------------------------+------------+
| 하단 PPT 타임라인                                  | 인스펙터   |
| Slide 1 | Slide 2 | Slide 3 ...                   |            |
| 선택 슬라이드 내부 요소 레이어/등장 타이밍          |            |
+----------------------------------------------------+------------+
```

### 7.1 왼쪽 패널

- 슬라이드 아웃라인
- 미디어풀
- 템플릿/테마
- 가져오기
- AI 초안

### 7.2 중앙 캔버스

- 현재 슬라이드 편집
- 오브젝트 선택/이동/크기 조절
- 정렬선
- 안전영역
- 배경/프레임/가이드

### 7.3 하단 PPT 타임라인

- 슬라이드 클립 순서
- 슬라이드 길이
- 전환 표시
- 슬라이드 내부 요소 등장 타이밍
- 발표 미리보기 playhead

### 7.4 오른쪽 인스펙터

선택 대상에 따라 바뀐다.

- 슬라이드 선택: 배경, 템플릿, 전환, 길이, 노트
- 텍스트 선택: 폰트, 크기, 색, 정렬, 애니메이션
- 이미지 선택: crop, fit/fill, 그림자, 테두리
- 3D 렌더 선택: 카메라, 조명, 재질, 렌더 품질
- 캐릭터 선택: 모션, 포즈, 표정, 투명 배경
- 차트 선택: 데이터, 색, 라벨

## 8. 가져올 수 있는 자산

### 8.1 P0: MVP에 꼭 필요한 자산

| 자산 | 입력 | 출력 |
| --- | --- | --- |
| 이미지 | PNG/JPG/WebP | PPT 이미지 |
| 비디오 | MP4/MOV/WebM | PPT 비디오 또는 프레임 |
| 텍스트 | 직접 입력/AI/자막 | PPT 텍스트 |
| 타임라인 장면 | 클립/마커/줌/효과 | 슬라이드 이미지/짧은 영상 |
| AR/PBR 3D | GLB/GLTF/FBX | 렌더 PNG/MP4 |
| 화면 캡처 | 영역/창/전체화면 | 스크린샷/짧은 녹화 |

### 8.2 P1: 제품 차별점 자산

| 자산 | 입력 | 출력 |
| --- | --- | --- |
| MMD | PMX/PMD/PBX + VMD | 투명 배경 PNG/MP4 |
| Live2D | model3/moc | 투명 배경 PNG/MP4 |
| Spine | JSON/SKEL + atlas | 투명 배경 PNG/MP4 |
| VRM/avatar | VRM/퍼포먼스 소스 | 발표자/캐릭터 카드 |
| 컬러/VFX | LUT/노드/마스크 | 전후 비교 이미지/영상 |
| 오디오 | WAV/MP3/영상 음성 | 파형/나레이션/스피커 노트 |
| 표/차트 | CSV/수동 입력 | PPT 네이티브 표/차트 |

### 8.3 P2: 고급 설명용 자산

| 자산 | 입력 | 출력 |
| --- | --- | --- |
| 깊이맵/카메라 solve | depth/camera data | AR occlusion 설명 슬라이드 |
| 노드 그래프 | 효과 그래프 | 프로세스/기술 다이어그램 |
| 디바이스 목업 | 캡처 이미지 | 노트북/모니터/폰 프레임 |
| HDRI/환경맵 | HDRI/equirectangular | 3D 배경/환경 슬라이드 |
| PDF/문서 | PDF/DOCX/웹페이지 | 페이지 이미지/텍스트 추출 |

## 9. PPT에 넣는 방식

### 9.1 네이티브 PPT 오브젝트

가능하면 편집 가능한 형태로 넣는다.

- 텍스트
- 이미지
- 도형
- 아이콘/SVG
- 표
- 기본 차트
- MP4 비디오
- 오디오

### 9.2 TigerCapture 렌더 오브젝트

PPT가 직접 표현하기 어려운 것은 우리 쪽에서 렌더한다.

- AR/PBR 3D 렌더
- MMD/Live2D/Spine 캐릭터
- 복잡한 타이포그래피 효과
- 컬러/VFX 처리 결과
- 깊이 occlusion 데모
- 3D 기즈모/배치 설명 이미지

렌더 결과는 PPT에 넣지만, 원본 설정은 TigerCapture 프로젝트에 남긴다. 사용자가 나중에 더 높은 해상도로 다시 렌더할 수 있어야 한다.

## 10. 내부 데이터 모델

### 10.1 DeckSpec

```text
DeckSpec
  id
  title
  purpose
  language
  aspect_ratio
  theme
  slides[]
  sections[]
  assets[]
  metadata
```

### 10.2 SlideSpec

```text
SlideSpec
  id
  title
  layout_id
  section_id
  background
  elements[]
  transition
  duration_ms
  speaker_notes
  tags[]
```

### 10.3 SlideElement

```text
SlideElement
  id
  kind
  name
  x, y, w, h
  rotation
  z_index
  opacity
  style
  animation
  source
  render_cache
```

종류:

- text
- image
- video
- shape
- table
- chart
- callout
- icon
- ar_pbr_render
- mmd_render
- live2d_render
- spine_render
- actor_render
- timeline_moment
- screen_capture
- effect_before_after
- waveform
- depth_visualization
- node_graph_diagram
- device_mockup

### 10.4 PptTimeline

```text
PptTimeline
  slide_clips[]
  playhead_ms
  selected_slide_id
  markers[]
```

### 10.5 SlideClip

```text
SlideClip
  id
  slide_id
  start_ms
  duration_ms
  transition_in
  transition_out
  label_color
```

## 11. 모듈 설계

기능은 새 모듈로 분리한다.

```text
app/pptgen/
  __init__.py
  schema.py
  timeline.py
  planner.py
  layout.py
  templates.py
  theme.py
  assets.py
  asset_router.py
  render_bridge.py
  typography_adapter.py
  effects_adapter.py
  ar_pbr_adapter.py
  actor_adapter.py
  validation.py
  preview.py
  writer.py
  writer_python_pptx.py
  writer_ooxml.py
  export_video.py
  report.py

app/pptgen/ui/
  window.py
  canvas.py
  timeline.py
  inspector.py
  media_panel.py
  template_panel.py

app/actions/
  ppt_namespace.py

app/video_editor_ppt_workflow.py
```

규칙:

- `app/pptgen` 코어는 Qt를 import하지 않는다.
- UI는 `app/pptgen/ui`에 둔다.
- 에디터 연결은 `app/video_editor_ppt_workflow.py`에서 한다.
- `app/video_editor_window.py`에는 기능을 넣지 않는다.
- `review_automation`과 섞지 않는다.

## 12. 자동 레이아웃

PPT 제작기의 품질은 자동 레이아웃이 결정한다.

필수 기능:

- 제목/본문 자동 배치
- 이미지 비율 유지
- crop/fit/fill 선택
- 텍스트 넘침 감지
- 슬라이드 밖으로 나간 오브젝트 감지
- 오브젝트 겹침 경고
- CJK 줄바꿈
- safe area 유지
- 폰트 자동 축소
- 제목/본문/캡션 시각 계층 유지

초기에는 규칙 기반으로 충분하다. 나중에 레이아웃 점수화나 AI 보정을 붙인다.

## 13. 템플릿

초기 템플릿은 적어도 품질이 좋아야 한다.

### MVP 템플릿

- 표지
- 제목 + 본문
- 이미지 중심
- 영상 프레임 중심
- 2열 비교
- 3카드 요약
- 표
- 차트
- 프로세스/타임라인
- 마무리

### TigerCapture 특화 템플릿

- 3D 제품 소개
- AR/PBR before/after
- 영상 튜토리얼
- 화면 녹화 강의
- MMD/Live2D 캐릭터 발표
- 컬러/VFX 비교
- 노드 그래프 설명
- 디바이스 목업

## 14. 내보내기

### MVP

- PPTX
- PNG 슬라이드 이미지
- validation JSON

### 다음 단계

- PDF
- MP4 발표 영상
- HTML 프리뷰
- 템플릿 패키지

### 후속 단계

- 기존 PPTX import
- Google Slides 연동
- 발표자 모드
- 발표 녹화

## 15. 액션/MCP

AI와 자동화를 위해 액션을 처음부터 설계한다.

필수 액션:

```text
ppt.project.create
ppt.project.open
ppt.project.save
ppt.deck.from_prompt
ppt.deck.from_timeline
ppt.deck.apply_template
ppt.deck.validate
ppt.deck.export_pptx
ppt.deck.export_pdf
ppt.deck.export_video
ppt.slide.add
ppt.slide.remove
ppt.slide.duplicate
ppt.slide.move
ppt.slide.set_layout
ppt.slide.set_duration
ppt.slide.set_notes
ppt.element.add_text
ppt.element.add_image
ppt.element.add_video
ppt.element.add_ar_pbr_render
ppt.element.add_actor_render
ppt.element.add_chart
ppt.element.update
ppt.element.remove
ppt.element.arrange
ppt.timeline.select_slide
ppt.timeline.set_playhead
ppt.timeline.play_preview
```

AR/PBR와 액터 쪽은 별도 렌더 액션도 필요하다.

```text
ppt.render.ar_pbr_still
ppt.render.ar_pbr_turntable
ppt.render.actor_still
ppt.render.actor_motion
ppt.render.timeline_moment
ppt.render.effect_before_after
```

## 16. 검증

PPT 생성 후 항상 validation report를 만든다.

체크 항목:

- 슬라이드가 1장 이상인지
- 빈 슬라이드가 있는지
- 누락된 미디어가 있는지
- 텍스트가 넘치는지
- 요소가 슬라이드 밖에 있는지
- 겹침이 심한지
- 지원하지 않는 애니메이션이 있는지
- 렌더 캐시가 최신인지
- PPTX 파일이 실제로 생성됐는지
- PNG preview 장수와 슬라이드 수가 맞는지

검증은 무조건 막는 용도가 아니라, 사용자가 고칠 수 있도록 알려주는 용도다.

## 17. 구현 단계

### Phase 0: 기획/경계 확정

결과물:

- 한국어 제작 기획서
- 기술 스펙
- 리뷰 자동화와 사용자 PPT 제작기 경계 확정

완료 기준:

- `review_automation`과 분리하기로 확정
- `app/pptgen` 구조 확정

### Phase 1: 순수 코어

결과물:

- `schema.py`
- `timeline.py`
- `validation.py`
- JSON round-trip 테스트

기능:

- DeckSpec 생성
- SlideSpec 생성
- SlideClip 추가/이동/삭제
- 기본 검증

### Phase 2: PPTX writer MVP

결과물:

- `writer.py`
- `writer_python_pptx.py` 또는 최소 OOXML writer
- 샘플 PPTX 생성 테스트

기능:

- 텍스트/이미지/도형/표 기본 출력
- PPTX 저장
- PNG preview 생성

### Phase 3: 템플릿/레이아웃

결과물:

- `templates.py`
- `theme.py`
- `layout.py`

기능:

- 표지/본문/이미지/비교/표/차트 템플릿
- 자동 배치
- 텍스트 overflow 경고

### Phase 4: TigerCapture 자산 연결

결과물:

- `asset_router.py`
- `render_bridge.py`
- `ar_pbr_adapter.py`
- `actor_adapter.py`
- `typography_adapter.py`

기능:

- AR/PBR still render를 슬라이드에 넣기
- 타임라인 순간을 슬라이드로 변환
- 타이포 프리셋 변환
- 화면 캡처/영상 프레임 삽입

### Phase 5: UI 프로토타입

결과물:

- 독립 PPT 제작기 창
- 캔버스
- PPT 타임라인
- 인스펙터
- 템플릿 패널

기능:

- 슬라이드 추가/삭제/이동
- 요소 편집
- 미리보기
- PPTX export

### Phase 6: AI/액션

결과물:

- `ppt_namespace.py`
- deck planner
- timeline-to-deck adapter

기능:

- 프롬프트로 PPT 초안 생성
- 영상 타임라인에서 PPT 생성
- AI로 슬라이드 수정

### Phase 7: 제품화

결과물:

- PDF/MP4 export
- 렌더 캐시
- 템플릿 패키지
- 품질 QA
- 샘플 프로젝트

기능:

- 실제 사용자 플로우 완성
- 발표자료 제작에 쓸 수 있는 수준의 안정성 확보

## 18. MVP 정의

처음 출시 가능한 MVP는 다음만 제대로 되면 된다.

- 새 PPT 프로젝트 생성
- 슬라이드 타임라인에서 슬라이드 추가/이동/길이 조절
- 슬라이드 캔버스에서 텍스트/이미지 편집
- 기본 템플릿 적용
- AR/PBR 렌더 이미지 삽입
- 타임라인 장면 이미지 삽입
- PPTX export
- PNG preview export
- validation report 생성

MVP에서 하지 않아도 되는 것:

- 완전한 PPTX import
- 모든 PowerPoint 애니메이션
- Google Slides 연동
- 실시간 공동 편집
- 모든 3D 포맷의 네이티브 PPT 삽입
- 완전한 캐릭터 모션 편집

## 19. 리스크

### 19.1 PPTX 포맷 리스크

PPTX의 애니메이션/전환/미디어 제어는 복잡하다.

대응:

- 초기에는 정적 슬라이드 품질을 우선한다.
- 애니메이션 의도는 메타데이터로 저장한다.
- 필요한 부분만 OOXML patch를 추가한다.

### 19.2 자동 레이아웃 품질 리스크

자동 배치가 못생기면 기능 전체가 저렴해 보인다.

대응:

- 템플릿 수를 줄이고 품질을 높인다.
- overflow/overlap 검증을 강하게 한다.
- 처음부터 너무 많은 스타일을 만들지 않는다.

### 19.3 범위 폭발 리스크

PowerPoint 전체를 따라 하려 하면 끝이 없다.

대응:

- TigerCapture만의 강점에 집중한다.
- 타임라인, 렌더 자산, AI 초안, export를 핵심으로 둔다.

### 19.4 에디터 결합 리스크

메인 에디터에 직접 붙이면 유지보수가 어려워진다.

대응:

- `app/pptgen` 코어를 독립 유지한다.
- 에디터와는 adapter/workflow로 연결한다.

## 20. 제품 성공 기준

기술 기준:

- 코어가 Qt 없이 테스트 가능하다.
- PPTX가 PowerPoint/LibreOffice에서 열린다.
- validation report가 주요 문제를 잡는다.
- 액션으로 작은 deck을 만들고 export할 수 있다.

사용자 기준:

- 비디자이너가 5장짜리 깔끔한 PPT를 빠르게 만들 수 있다.
- 타임라인에서 발표 흐름이 직관적으로 보인다.
- 3D/영상/캐릭터 자산을 PPT에 쉽게 넣을 수 있다.
- export 결과물이 디버그 화면처럼 보이지 않는다.

제품 기준:

- PowerPoint/Keynote와 다르게 보이는 이유가 명확하다.
- TigerCapture의 기존 강점이 PPT 제작에 자연스럽게 연결된다.
- AI/자동화로 반복 작업을 줄일 수 있다.

## 21. 첫 작업 목록

1. `app/pptgen/schema.py` 작성
2. `app/pptgen/timeline.py` 작성
3. `app/pptgen/validation.py` 작성
4. `tests/test_pptgen_schema.py` 작성
5. `tests/test_pptgen_timeline.py` 작성
6. writer 의존성 결정: `python-pptx` 또는 최소 OOXML
7. 샘플 3장 PPTX 생성
8. AR/PBR still render를 SlideElement로 넣는 adapter 설계
9. 타임라인 순간을 SlideElement로 만드는 adapter 설계
10. 독립 PPT 제작기 UI 와이어프레임 구현

## 22. 최종 방향

TigerCapture PPT 제작기는 “PPT를 만드는 기능”이 아니라 **TigerCapture 안의 모든 창작 자산을 발표자료로 바꾸는 제작 파이프라인**이어야 한다.

핵심은 다음 세 가지다.

```text
타임라인으로 흐름을 만들고,
TigerCapture 렌더러로 고품질 자산을 만들고,
PPTX/PDF/영상으로 안전하게 내보낸다.
```

