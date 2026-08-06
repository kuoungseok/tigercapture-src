# Painter Painting 전수검사 수정 리스트

작성일: 2026-08-06  
범위: Painter의 **Painting 모드만 포함**. UI Design 모드와 `painter_ui_*` 구현·테스트는 제외한다.  
근거 기준: 공식 제품·플랫폼·포맷 문서, Tiger가 명시적으로 선언한 제품 정책, 수학·파일 구조 불변식, 실패·fallback 계약, 실제 측정. 관행이나 “보통 이 정도”는 승인 근거로 사용하지 않는다.

## 1. 최종 검사 현황

| 항목 | 최종 결과 |
| --- | --- |
| Painting 앱/테스트/QA 조사 범위 | 앱 63개, 테스트 68개, QA 도구 45개 |
| AST 숫자 리터럴 | 6,415개 고유 사이트 조사 |
| 미검토 숫자·품질·용량·예외·의미 축약 | 0개 |
| 근거 미해결 행 | 0개 |
| stale/pending 장부 계약 | 0개 |
| 테스트/QA에서 참조되지 않은 Painting 앱 모듈 | 0개 |
| Painting 전체 회귀(UI Design 제외) | 639/639 통과 |
| 아키텍처·debugCapture·증거 계약 가드 | 36/36 통과 |
| 장기 실행 | 7,200초 × 3회, workload 오류 0회 |
| 독립 M55 delta QA | PASS_DELTA, P0/P1/P2 0/0/0, focused 33/33 |

현재 감사 보고서: `debugCapture/painter/evidence_audit/report.json`. 이 보고서는 소스 inventory를 SHA-256으로 고정하며, 문서나 구현이 바뀌면 다시 생성해야 한다.

## 2. 발견·수정 목록

| ID | 발견된 문제 | 적용한 수정 | 판정 근거·검증 | 상태 |
| --- | --- | --- | --- | --- |
| P-01 | 테스트 성공을 제품 준비 완료로 올리거나 `tests_passed=True`처럼 결과를 하드코딩할 수 있었음 | 증거 등급과 claim을 분리하고 artifact SHA-256 검증에 실패하면 fail-closed 처리 | `app/painter_evidence_contract.py`, `app/painter_product_reapproval.py`, evidence contract 테스트 | 완료 |
| P-02 | offscreen 고배율, 합성 stylus, CPU fallback이 각각 실제 모니터·물리 태블릿·실제 GPU 증거처럼 읽힐 수 있었음 | `simulated_high_dpi_layout`, `synthetic_tablet_channel_roundtrip`, CPU fallback 등으로 증거 이름과 한계를 명시 | Qt High-DPI/QTabletEvent/QOpenGLContext 공식 문서, native-environment 보고서 | 완료 |
| P-03 | 근거 없는 시간·화질 cutoff가 PASS/ready를 결정했음 | M7/M8 micro timing과 AI Study cutoff를 기능 판정에서 제거하고 raw measurement/diagnostic-only로 변경 | 실제 측정 보고서와 threshold 독립 QA | 완료 |
| P-04 | brush width 공개 범위가 UI·Action·adapter 사이에서 달랐고 일부 경로가 60 px로 잘렸음 | Painting brush width 도메인을 단일 계약으로 통일하고 Action 입력을 엄격 검증 | Adobe 5,000 px brush 참고 경계, `painter_brush_domains.py`, Actions/도메인 테스트 | 완료 |
| P-05 | bool, 문자열, 소수, NaN/Inf, 0/음수 크기가 `int`, truthiness, `max(1, …)`로 정상값처럼 바뀔 수 있었음 | 공용 strict dimension/channel/index/input 검증기를 추가하고 잘못된 필수 입력은 mutation 전에 거부 | `painter_dimensions.py`, `painter_action_inputs.py`, `painter_channel_contract.py`, 639개 회귀 | 완료 |
| P-06 | 문서·레이어·마스크·PSD/PBR/OpenGL 크기 오류가 1 px 또는 FHD로 대체될 수 있었음 | raster/physical dimension을 분리하고 PNG/PSD, 레이어, 선택, wet canvas, blockout, PBR, GL까지 strict domain 적용 | Qt QImage, PNG 3, Adobe PSD 형식 문서, 적대 입력 테스트 | 완료 |
| P-07 | pressure/rotation 누락 시 0.82/180° 같은 임의값을 만들 수 있었음 | 장치의 중립값과 누락/유효성 계약을 분리하고 required Action 값은 실패 처리 | Qt QTabletEvent 공식 범위, 실제 QTabletEvent 생성 테스트 | 완료 |
| P-08 | dynamic dab이 segment마다 고정 상한을 적용해 같은 선이 control-point 수에 따라 다른 결과를 냈음 | 전체 polyline arc length와 caller budget을 기준으로 결정적 spacing/샘플링으로 교정 | 2점/33점 동일 직선 replay 및 100/700/2,300점 경로 테스트 | 완료 |
| P-09 | paint load 감소가 event 개수에 의존해 같은 이동거리라도 입력 샘플 수에 따라 달라졌음 | 누적 문서 픽셀 이동거리 기반으로 load/dryout을 통일 | Corel Artists’ Oils/Blending 문서 경계, 거리 등가 테스트 | 완료 |
| P-10 | pressure 0, pickup/load 0에서 재질이나 브리슬 효과가 남는 우회 경로가 있었음 | 13개 v2 스타일에서 exact zero identity를 강제하고 preview/live/commit/export/reopen을 같은 renderer에 연결 | M52 독립 QA가 결함 재현 후 수정 확인, endpoint/measurement 테스트 | 완료 |
| P-11 | legacy brush 결과가 새 엔진의 참조 구현처럼 취급될 수 있었고 공개 제어와 저장값 연결이 불명확했음 | legacy는 별도 Tiger-authored deterministic model로 경계화하고 공개 제어·preset·snapshot/replay를 연결 | `painter_legacy_brush.py`, M51 측정/독립 QA | 완료 |
| P-12 | 브리슬·재질 계수가 물리 매체 측정값처럼 해석될 수 있었음 | authored stylization 계약과 `physical_media_claim=false`, `paint_rheology_claim=false`, external parity 제외를 명시 | Corel/Krita/Adobe는 기능 경계 참고만 사용, M52 측정 | 완료 |
| P-13 | 낮은 진폭 재질 신호가 8-bit 중간 변환에서 사라질 수 있었음 | 결정적 float32 Gaussian fallback과 최종 양자화 경계를 사용 | Pillow/OpenCV fallback 테스트, sub-8-bit 신호 측정 | 완료 |
| P-14 | selection/mask/path/layer index와 tuple cardinality가 clamp되어 잘못된 편집을 만들 수 있었음 | mask, layer, catalog, path, saved-channel 구조 검증기를 분리하고 invalid 입력은 Undo snapshot 전에 거부 | `painter_layer_contract.py`, `painter_catalog_indices.py`, selection/path/layer 테스트 | 완료 |
| P-15 | Quick Mask와 Saved Selection의 8-bit selectedness·overlay 의미가 암묵적이었음 | Alpha8 보존, 128 binary chrome 경계, 임시 Quick Mask와 영속 Saved Channel을 분리 | Adobe Quick Mask, Qt QImage, exact [0,64,128,255] 테스트 | 완료 |
| P-16 | cross-document Saved Selection 복사/교환 시 문서 크기·ID·이름 충돌·Undo 원자성이 불완전할 수 있었음 | exact pixel dimension 사전검증, 안정 ID, 중복 거부, 단일 Undo transaction 적용 | M45/M46 독립 QA와 file exchange 테스트 | 완료 |
| P-17 | `.tspaint` archive가 Windows 경로, UNC, drive absolute, ADS colon, 중복 entry, hash/size mismatch를 충분히 거부하지 못했음 | 추출 전 manifest/경로/중복/크기/SHA 검증 및 atomic open 적용 | Python zipfile 경계, corrupt v5·legacy migration 테스트 | 완료 |
| P-18 | autosave/recovery가 성공 여부와 crash/disk-full 증거를 섞을 수 있었음 | 임시 파일·replace·rollback·cleanup을 transaction으로 분리하고 typed failure telemetry 및 다음 실행 recovery 검증 추가 | Win32 `ERROR_DISK_FULL=112`, crash/disk-full native QA | 완료 |
| P-19 | PNG/TIFF/PSD/ICC 구조와 8/16-bit 변환이 구현 관행으로 승인될 수 있었음 | signature/header/chunk/IFD/tag/channel/precision을 규격별 exact contract로 분리하고 unsupported 변환은 preflight 차단 | PNG 3, TIFF 6.0, ICC.1:2022, Adobe PSD 명세, round-trip/손상 테스트 | 완료 |
| P-20 | PSD alpha-over 비교가 고정 1 LSB처럼 근거 없이 단순화됐음 | 보이는 alpha-over stage 수에 따른 8-bit quantization 오차 계약으로 교정하고 byte-identical claim 제거 | W3C Compositing, 실제 다층 측정 | 완료 |
| P-21 | print PPI·bleed·safe-area 값이 보편 품질 기준처럼 보일 수 있었음 | ISO/Adobe/Clip Studio 근거가 있는 예와 Tiger 시작 preset을 분리하고 universal quality claim 제거 | ISO 216, Adobe print resolution, Clip Studio manuscript 안내 | 완료 |
| P-22 | ICC embedding과 실제 색변환, sRGB 지원 범위가 혼동될 수 있었음 | profile 검사/embedding, rendering intent, 미구현 CMYK conversion blocked preflight를 분리 | ICC.1:2022, Qt QColorSpace, Photoshop color-mode 문서 | 완료 |
| P-23 | Action schema의 색상·PBR·문서 크기·payload 한계가 adapter 구현과 어긋나거나 silent clamp될 수 있었음 | schema/runtime/adapter를 한 strict contract로 연결하고 invalid 입력의 no-mutation을 검증 | M54 15/15 측정, 독립 QA 6/6 적대 호출 차단 | 완료 |
| P-24 | OpenGL cleanup 실패가 무시되거나 context lifetime이 매 render마다 늘어날 수 있었음 | retained context, makeCurrent 검증, one-shot context recreation, typed last error와 bounded telemetry, primary error 보존 적용 | Qt QOpenGLContext/Khronos 문서, 60회 context churn 오류 0 | 완료 |
| P-25 | large-canvas cache/worker/Undo 예산이 코드 상수일 뿐 실제 할당·회수와 연결되지 않았음 | 공유 tile policy, 네 cache의 byte accounting, dirty-tile 처리, executor drain, CPU fallback telemetry를 연결 | native 4K/8K 보고서, large-canvas 테스트 | 완료 |
| P-26 | soak harness 자체가 ctypes type, 모든 latency, 모든 resource sample을 누적해 앱 누수처럼 보였음 | ctypes binding을 1회 초기화하고 DKW–Massart 근거의 6,623개 bounded reservoir와 NDJSON streaming으로 수정 | runtime-metrics/orchestration 테스트, 독립 harness QA | 완료 |
| P-27 | Windows Working Set 증가를 retained private allocation으로 오판했음 | WorkingSetSize는 residency 관찰값으로 유지하고 PrivateUsage(private Commit Charge)만 retention 차단 신호로 사용 | Microsoft Process Working Set 및 PROCESS_MEMORY_COUNTERS_EX 문서, series v3 테스트 | 완료 |
| P-28 | 실행 중 UI Design 파일 변경으로 Painting soak 전체가 실패 처리됐음 | Painting fingerprint에서 `painter_ui_*`를 제외하고 이미 완료된 raw workload와 packaging 상태를 분리 | UI Design-only 변경 확인, 독립 QA deep-equal 재계산 | 완료 |
| P-29 | 숫자·capacity·예외 감사가 regex 일부만 보고 “0건”을 만들 수 있었음 | AST 전체 숫자 사이트, exact row count/SHA ledger, stale/pending 검출, source inventory를 추가 | 6,415 사이트, 미검토/미해결/미참조 0 | 완료 |
| P-30 | Painting과 UI Design 범위가 파일 이름이나 공용 `drawing.py`에서 섞일 수 있었음 | `painter_ui_*`, `test_painter_ui*`, UI Design 함수명을 감사·회귀·soak fingerprint에서 명시 제외 | 보고서 scope=`painting_only_ui_design_excluded` | 완료 |

## 3. M55 장기 실행 원시 증거

| 실행 | 시간 | operations | cycles | samples | workload errors | SHA-256 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 7,200.0017초 | 259,481 | 2,162 | 1,437 | 0 | `78e443fb642c44f06579269c9283772ef4e56f7998022bf72232cba2f71d244b` |
| 2 | 7,200.0257초 | 259,995 | 2,166 | 1,437 | 0 | `ba8d82273469d9f1dc6c5d7530c86685718f7e11c5d60bd6892d15120b3475b4` |
| 3 | 7,200.0769초 | 254,622 | 2,121 | 1,437 | 0 | `456b8619e4890388844441d1c8ab8a1ada6a94d47207a7ee4a91ca9c510049f9` |

세 실행 모두 late-half `PrivateUsage` retention 판정은 false였다. Working Set은 세 실행에서 소폭 증가했지만 Microsoft 정의상 shared/private를 함께 포함한 resident physical pages이므로 관찰값으로 보고하며 차단 판정으로 사용하지 않는다. 이 결과는 **해당 코드·환경·workload에서 미해결 retained-private-commit 신호를 찾지 못했다**는 뜻이며, 보편적인 leak-free 인증은 아니다.

독립 판정: `debugCapture/painter/evidence_audit/m55_soak_semantics_delta_qa.json`, SHA-256 `7fa362f33d9b9ec19991f4ac53bf6b8a535c1901954d2e283926abc6131e5a0b`.

## 4. 주요 추가·분리 모듈

- strict 입력·도메인: `app/painter_action_inputs.py`, `app/painter_dimensions.py`, `app/painter_brush_domains.py`, `app/painter_channel_contract.py`
- 구조·인덱스: `app/painter_catalog_indices.py`, `app/painter_layer_contract.py`, `app/painter_open_documents.py`
- Painting 도구 계약: `app/painter_grid.py`, `app/painter_zoom.py`, `app/painter_preview_geometry.py`, `app/painter_legacy_brush.py`
- 선택·채널: `app/painter_quick_mask.py`, `app/painter_saved_selection_channels.py`, `app/painter_alpha_channel_exchange.py`
- 측정·승인: `app/painter_runtime_metrics.py`, `app/painter_soak_series.py`, `tools/qa_painter_soak.py`, `tools/run_painter_long_soak_series.py`, `tools/watch_painter_long_soak.py`, `tools/audit_painter_painting_evidence.py`
- 근거 장부: `docs/PAINTER_NUMERIC_DECISION_LEDGER.json`, `docs/PAINTER_EXCEPTION_DECISION_LEDGER.json`

## 5. 승인에서 제외되는 남은 환경 한계

다음 항목은 구현 결함으로 숨기거나 자동 PASS로 바꾸지 않는다.

- 현재 1× 모니터에서는 실제 고배율 모니터 관찰을 완료할 수 없음
- 현재 물리 태블릿 입력 캡처가 없어 장치별 pressure/tilt/rotation 품질을 인증할 수 없음
- 독립 에이전트 QA는 사람의 시각적 제품 검토를 대체하지 않음
- 외부 앱/드라이버/하드웨어 전체 조합의 성능·메모리·색상·파일 호환성을 보편 인증하지 않음
- UI Design 모드는 이번 수정 리스트와 승인 범위 밖임

이 한계들은 최종 product reapproval의 `release_ready`와 별개로 유지한다. Painting 구현·근거 집계가 유효하다는 것과 모든 물리 환경에서 출시 준비가 끝났다는 주장을 혼동하지 않는다.
