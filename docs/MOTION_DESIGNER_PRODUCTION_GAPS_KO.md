# Motion Designer 제작 품질 보강 마일스톤

작성일: 2026-08-02

이 문서는 기존 M0-M20 및 2026 트렌드 M21-M28을 다시 번호 매기지 않는다.
이미 존재하는 분할, 인페인팅, 퍼펫, 트래킹 기능을 실제 광고·뉴스·캐릭터
모션 제작에 안정적으로 쓰기 위한 남은 제품화 작업만 `PG`로 관리한다.

## 상태 요약

| 단계 | 목표 | 상태 |
|---|---|---|
| PG1 | 레이어 제작 준비도 게이트와 복구 계획 | Complete v1 |
| PG2 | 시간축 매트·트래킹 안정화 | Complete v1 |
| PG3 | 배경 복원·접지·색 일치 합성 | Complete v1 |
| PG4 | 반복을 피하는 자동 연출 디렉터 | Complete v1 |
| PG5 | GPU·캐시·장시간 재생 제품 게이트 | Complete v1 |

## PG1 - Layer Production Readiness

목표는 “레이어 파일이 생성됐다”와 “독립 모션에 써도 된다”를 분리하는 것이다.

구현:

- `app/motion_designer/layer_readiness.py`
- 컷아웃 경계, 불투명 배경 잔류, 첫 프레임 재합성, 배경 복원 confidence,
  카메라 이동 한계, segmentation provider 상태를 하나의 보고서로 통합한다.
- 결과는 `ready`, `review`, `repair_required`, `fallback_only` 중 하나다.
- 실패 시 mask refine, mask replace, clean plate, provider 설치 계획 순서의
  실행 가능한 Action repair plan을 제공한다.
- `motion.ai.layer.readiness.inspect`를 Action/MCP에 공개한다.
- 이미지 분해의 신규 생성과 캐시 재사용 양쪽에 같은 보고서를 기록한다.
- AI 패널은 분석 결과에 production gate 상태와 최저 점수를 표시한다.
- 품질 실패 시 원본 픽셀을 유지하는 single-layer motion을 명시적 fallback으로
  제공하되, 편집 가능한 다중 레이어 결과라고 주장하지 않는다.

완료 기준:

- 정상 source-alpha 자산은 `ready`가 된다.
- 불투명 배경이 붙은 전경은 `repair_required`가 된다.
- UI, Action, 캐시 결과가 같은 스키마를 사용한다.
- 실제 제품 자산 QA 보고서를 재생성할 수 있다.

## PG2 - Temporal Matte Stability

기존 tracking cache, correction key, confidence diagnostics를 유지하면서 다음을 구현했다.

- [구현] 프레임별 matte 면적·중심·경계 변화량 측정
- [구현] confidence 급락과 mask pop/flicker 구간 자동 표시
- [구현] drift 임계값을 넘으면 propagation 자동 중단 지점 반환
- [구현] `motion.matte.temporal.validate` Action/MCP
- [구현] 비디오 tracking Action과 UI worker 완료 직후 자동 품질 검사
- [구현] 위험 프레임부터 tracking sample 자동 제거 또는 cache 비활성화
- [구현] 타임라인의 중단 지점·보정 후보 error/warning 마커
- [구현] 보정 키 입력 후 원본 sample을 복원해 안정성 재계산
- [구현] 머리카락·손가락처럼 얇은 영역의 별도 temporal tolerance

완료 기준:

- Action과 UI tracking 결과에 같은 `tigerstudio.motion.temporal_matte_quality.v1`
  보고서가 자동 기록된다.
- unsafe 결과는 첫 위험 프레임 이후를 재생하지 않는다.
- 타임라인에서 중단 지점과 보정 후보를 확인할 수 있다.
- correction key를 추가하면 보정 전 sample을 포함해 품질을 다시 계산한다.

## PG3 - Restoration and Contact Composite

- [구현] `app/motion_designer/restoration_preflight.py`
- [구현] 전경 마스크 합집합과 inpaint confidence를 이용한 8x8 기본 위험 heatmap
- [구현] 카메라 이동량에 따른 복원 노출 위험 사전 계산과 안전 이동 벡터 clamp
- [구현] 분해 결과를 직접 받는 `motion.ai.restoration.preflight` Action/MCP
- [구현] 원시 복원 마스크를 받는 `motion.restoration.preflight` QA Action
- [구현] `app/motion_designer/contact_composite.py`
- [구현] 반투명 edge decontamination, 제한된 배경 광색 match, 별도 soft contact shadow PNG
- [구현] `motion.ai.contact_composite.prepare` Action/MCP와 Preview/export 공유 자산 계약
- [구현] choreography camera 벡터를 복원 한계 안으로 자동 clamp하고 preflight를 레이어에 기록
- [구현] Preview/export render graph가 동일한 보정 전경·그림자 자산을 참조하는 parity 검사
- [검증] `debugCapture/motion_designer/contact_composite_qa/report.json`
  - 320x180, 6fps H.264 MP4 6프레임 재디코딩
  - contact shadow 레이어와 비어 있지 않은 프레임 확인

제품 경계:

- H.264 MP4는 alpha delivery 포맷이 아니다. alpha parity는 공통 render graph와
  PNG/alpha-capable 출력까지의 계약이며, MP4에서는 최종 색·그림자 합성 결과를 검증한다.
- v1 안전 경로는 요청 방향을 유지한 벡터 clamp다. 복원 heatmap을 우회하는 곡선형
  카메라 경로 탐색은 후속 고급 기능으로 남긴다.

## PG4 - Choreography Director

- [구현] 의미 역할, 장면 길이, 오디오 hit를 함께 쓰는 기존 cue planner 보강
- [구현] `app/motion_designer/choreography_director.py`
- [구현] 레이어 motion signature 반복도와 최대 동시 진입량 검출
- [구현] headline burst, product orbit, puppet greeting, editorial cutout shot grammar
- [구현] 최대 동시 레이어 진입량을 실제 cue 시간에 적용
- [구현] Clean/Dynamic/Collage 3개 후보의 복잡도·가독성·반복도 비교와 추천
- [구현] `motion.ai.choreography.candidates` Action/MCP
- [구현] source hash와 명시적 승인을 검사하는 `motion.ai.choreography.candidate.apply`
- [검증] `debugCapture/motion_designer/choreography_director_qa/report.json`
  - Action 기반 이미지 분해, 3개 후보 생성, 추천 후보 승인 적용
  - 640x360, 12fps, 3초 H.264 광고 36프레임 재디코딩
  - 추천 후보 반복 signature 0, 최대 동시 동작 2, 가독성 96.696

## PG5 - GPU, Cache and Release Gate

- [구현] 항목 수와 이미지 바이트를 함께 제한하는 `MotionFrameCache` LRU 및
  hit/miss/eviction/current/max byte 진단
- [구현] graph build, GPU 시도, CPU paint, 전체 프레임 시간과 명시적 fallback
  원인을 기록하는 export 진단
- [구현] segmentation/matte/depth/inpaint 결과를 함께 보관하는 decomposition
  fingerprint 디렉터리의 2 GiB LRU 예산과 현재 결과 보호
- [구현] 결정적 프레임 hash, p50/p95, GPU 요구, cache budget/hit, 템플릿 전환
  안정성을 검사하는 `motion.performance.gate` Action/MCP
- [구현] 반복 템플릿 전환에서 managed layer 누적과 retained/peak memory 검사
- [검증] `debugCapture/motion_designer/pg5_release_gate/report.json`
  - 16:9, 9:16, 1:1 Product Callout 결과의 hash 결정성 및 캐시 예산 통과
  - 각 화면비에서 3개 템플릿 12회 전환 후 layer growth 0
  - Product Callout export의 `gpu_effect_missing` CPU fallback을 숨기지 않고 기록
- [검증] `debugCapture/motion_designer/long_run_30m/report.json`
  - 실제 OpenGL Preview 1800.24초, 평균 44.84 frame swaps/s
  - RSS 증가 8.9 MB, software renderer 미사용
- [검증] `debugCapture/motion_designer/release_acceptance/report.json`의
  GPU Preview/Export parity와 packaged installer smoke 증거 연결

## 제품 표현 경계

PG1 완료는 모든 이미지의 완전 자동 분해를 뜻하지 않는다. 현재 올바른 표현은
`AI-assisted editable layered motion with explicit production readiness and fallback`이다.
PG1-PG5는 위 증거 범위에서 Complete v1이다. 새로운 결함이나 제품 요구 없이
억지로 후속 production-gap 번호를 만들지 않는다.
