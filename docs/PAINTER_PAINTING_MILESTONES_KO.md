# Tiger Painter Painting 전용 마일스톤

> 역사적 M0-M8 자동 구현 기준선이다. 현재 제품 승인 상태와 보정 순서는
> `PAINTER_EVIDENCE_AUDIT_AND_CORRECTION_MILESTONES_KO.md` 및 `SPEC.md`가 기준이다.
> 이 문서의 완료 표시는 release approval을 의미하지 않는다.

기준일: 2026-08-03  
상태: 실행 로드맵  
범위: Standalone Painter의 Painting 모드만 포함

## 1. 범위와 제품 목표

이 로드맵은 `UI Design` 모드의 아트보드, 컴포넌트, 프로토타입,
Figma/UMG 전달 기능을 다루지 않는다. Painting 모드가 캐릭터, 배경,
컨셉 아트, 일러스트, 텍스처 제작에 매일 사용할 수 있는 독립형 페인터가
되는 데 필요한 작업만 소유한다.

현재 강점은 다음과 같다.

- 편집 가능한 스트로크와 브러시 프리셋
- 브리슬 엔진 v2, Material Paint, Wet Canvas v1
- 레이어/마스크/채널/기본 Path
- Reference Board, 3D Blockout, PBR Texture Lab
- 네이티브 `.tspaint` v1 저장, 자동 저장 및 복구
- PNG와 PBR 맵 출력, `paint.*` Action 자동화

제품 완료 기준은 Photoshop 기능 수를 복제하는 것이 아니다. 기본 페인팅
작업에서 픽셀 레이어, 선택, 변형, 브러시, 색상, 저장, 출력이 서로 같은
문서와 렌더 계약을 사용하고, 긴 작업에서도 결과가 바뀌거나 멈추지 않는
것이 목표다.

## 2. 공통 완료 규칙

모든 마일스톤은 아래 조건을 만족해야 완료로 표시할 수 있다.

- UI와 `paint.*` Action이 동일한 서비스와 Undo 경로를 사용한다.
- 화면 미리보기, PNG 출력, `.tspaint` 재열기 결과가 시각적으로 일치한다.
- 파괴적 작업에는 한 단계 Undo와 실패 전 사전 검증이 있다.
- 760x560, 1920x1080, High-DPI 환경에서 Painting UI가 겹치지 않는다.
- 기능 단위 테스트와 실제 Painter 캡처가 모두 존재한다.
- `debugCapture`에는 재생성 가능한 QA 결과만 두고 원본 작업 파일은 두지 않는다.
- 전체 Painting 테스트에서 알려지지 않은 실패가 0개다.

## 3. 현재 기준선

2026-08-03 M0 완료 기준:

- Painting 전용 테스트 101개 전부 통과
- Architecture guard 4개 전부 통과
- 실시간/확정 브리슬 픽셀 일치와 샘플당 2점 이하 bounded 렌더 동시 통과
- 760x560과 1920x1080 실제 Painting 캡처에서 패널 겹침 없음
- 760px 상단 바는 브러시 선택기·크기·불투명도를 유지하고 Material/PBR을
  숨기며, 1920px에서는 전체 브러시 항목을 표시

## M0. 기준선 안정화와 계약 정리

상태: 완료 (2026-08-03)  
선행 조건: 없음

목표:

- 현재 Painting 회귀를 제거하고 이후 구조 변경의 측정 기준을 고정한다.

작업:

- 실시간 브리슬 렌더에 전역 sample index, 접선 연속성, pressure/load
  depletion 상태를 전달하는 증분 계약을 정의한다.
- 드래그 중/pen-up 픽셀 일치를 유지하면서 샘플당 작업량을 bounded 상태로
  되돌린다.
- 작은 창 Inspector 높이 실패가 오래된 테스트인지 실제 반응형 회귀인지
  실제 캡처로 판정하고 구현/테스트 중 하나를 정정한다.
- `PAINTER_PHOTOSHOP_PARITY_AUDIT.md`의 오래된 `.tpaint` 미구현 표기를
  현재 `.tspaint` v1 구현 상태로 갱신한다.

완료 조건:

- `tests/test_painter_stroke_latency_guards.py` 전체 통과
- 실시간/확정 브리슬 픽셀 parity 테스트 통과
- UI Design 테스트를 제외한 `test_painter_*.py`가 100% 통과
- 760x560과 1920x1080 실제 Painting 캡처에서 패널 겹침이 없음

## M1. 레이어별 래스터 코어

상태: 완료 (2026-08-03)  
선행 조건: M0

목표:

- 단일 배경 표면과 Sticker 우회에서 벗어나 각 Paint Layer가 독립적인
  래스터 픽셀을 소유하게 한다.

작업:

- 레이어별 투명 래스터 surface와 composite 순서를 정의한다.
- 큰 캔버스를 고려해 전체 이미지 복사 대신 tile/dirty-region 기반 저장과
  갱신 계약을 사용한다.
- Fill, Gradient, Pattern, Paste, Import Image as Layer를 선택된 래스터
  레이어에 적용한다.
- 선택 영역 Copy/Cut/Paste가 알파와 위치를 보존하도록 한다.
- 기존 stroke-only 문서를 무손실로 여는 `.tspaint` v2 migration을 추가한다.
- 래스터 자산을 네이티브 문서 안에 해시와 함께 포함한다.

완료 조건:

- 서로 다른 두 레이어의 픽셀이 독립적으로 편집됨
- Import/Paste가 Sticker가 아닌 일반 Paint Layer를 만들 수 있음
- Save/Open 후 픽셀, 알파, 레이어 순서가 동일함
- 4K 캔버스에서 한 레이어 수정이 모든 레이어 전체 복사를 유발하지 않음

검증 결과:

- UI Design 제외 전체 Painter 테스트 108개 통과
- Architecture guard 4개 통과
- 독립 QA 지정 테스트 29개 통과 및 전체 Painter 108개 재통과
- `.tspaint` v2 저장/재열기, v1 stroke-only 무손실 migration 통과
- `debugCapture/painter/painting_m1` 실제 재열기 화면과 PNG 출력 parity 통과
- 작은 래스터 편집은 변경 레이어 하나의 `raster_replace` delta Undo만 저장

## M2. 프로덕션 레이어와 합성

상태: 완료 (2026-08-03)  
선행 조건: M1

목표:

- 일러스트 작업에 필요한 레이어 구조와 합성 동작을 완성한다.

작업:

- Group/Folder와 중첩 disclosure
- Clipping Mask와 클리핑 체인
- Merge Down, Merge Visible, Flatten
- 투명 픽셀, 픽셀, 위치, 전체 잠금 분리
- 마스크 썸네일 선택, 활성/비활성, 연결/해제, 삭제
- 레이어 다중 선택, 드래그 autoscroll, 색상 라벨
- Normal/Multiply/Screen/Overlay 이후 필수 blend mode 확장과 화면/출력 parity

완료 조건:

- 그룹, 클리핑, 마스크가 `.tspaint`와 PNG에서 동일함
- Merge/Flatten이 보이는 결과를 바꾸지 않고 한 단계 Undo 가능
- 잠긴 항목에 대한 UI와 Action의 거부 이유가 동일함

검증 결과:

- UI Design 제외 전체 Painter 테스트 117개 통과
- Architecture guard 4개 통과
- 독립 QA focused 14개 및 전체 Painter 117개 재통과
- 그룹/클리핑/마스크/12종 blend의 화면·PNG·`.tspaint` parity 통과
- Merge Down/Merge Visible/Flatten 픽셀 보존 및 1-step Undo 통과
- pixel/transparency/position/all lock 우회 및 계층 재정렬 경계 검증 통과
- `debugCapture/painter/painting_m2` 저장 전·재열기·병합 후 PNG SHA-256 동일

## M3. 선택, Crop, Transform, Path

상태: 완료 (2026-08-03)  
선행 조건: M1

목표:

- 반복적인 제작 작업에 필요한 정밀 선택과 변형을 제공한다.

작업:

- Lasso와 Polygonal Lasso
- contiguous Magic Wand와 Color Range preview
- Feather, Expand, Contract, Border
- 선택 영역 이동과 Free Transform
- Rotate, Scale, Skew, Flip 및 pivot
- 조절 가능한 Crop handles, 취소, overlay, straighten
- Path anchor/Bezier handle 선택, add/delete/convert point
- Fill Path, Stroke Path, path duplicate/rename/reorder

완료 조건:

- 선택 mask가 bounding box가 아니라 실제 픽셀 형태를 보존함
- 래스터/스트로크/마스크 대상 변형 결과가 미리보기와 commit에서 동일함
- Crop과 Transform이 취소 가능하고 한 단계 Undo로 복구됨

검증 결과:

- 실제 Alpha8 픽셀 선택 mask로 Lasso/Polygonal Lasso, 연속/전체 Color Range, Feather/Expand/Contract/Border 통과
- 선택 픽셀 및 레이어 래스터/스트로크/레이어 마스크의 Move/Rotate/Scale/Skew/Flip/pivot 미리보기·커밋 parity 통과
- 조절 가능한 Crop bounds, preview/cancel/commit, straighten 및 레이어 래스터 crop/1-step Undo 통과
- Bezier anchor/handle add/delete/move/corner/smooth, Fill/Stroke, duplicate/rename/reorder 및 `.tspaint` 복원 통과
- M3 focused 테스트 16개 및 UI Design 제외 전체 Painter 테스트 133개 통과, Architecture guard 4개 통과
- 독립 QA에서 feather Alpha8 가중치, 실제 marching-ants 윤곽, Crop/Transform/Bezier 직접 조작 및 상단 brush lane 50% 이하를 재검증해 PASS
- 760/806/900 px에서 brush lane 최대 42.89%, 위치 고정, 브러시 선택기와 `6 px`/`100%` 숫자 표시 유지
- `debugCapture/painter/painting_m3`에서 preview=commit, cancel=원본, undo=원본, save/open PNG SHA-256 parity 통과

## M4. 브러시 엔진 프로 패스

상태: 완료 (2026-08-03)  
선행 조건: M0, M1

목표:

- 프리셋 수가 아니라 사용자가 직접 조절할 수 있는 브러시 동역학을 완성한다.

작업:

- Flow와 buildup/deposition 분리
- 실제 stroke stabilization과 보정 강도
- Pressure curve 및 장치별 calibration
- Scatter, Texture, Transfer, Color Dynamics의 실제 파라미터
- 브러시별 tilt/rotation/barrel-pressure mapping
- Smudge/Mixer/Pickup 브러시
- captured dab와 공개적으로 허용 가능한 ABR import 범위
- 프리셋 저장/가져오기/내보내기 및 missing resource 진단

완료 조건:

- Advanced Brush Controls의 활성 카테고리가 모두 실제 렌더 결과를 변경함
- 마우스와 태블릿 입력이 저장/Undo/출력까지 동일 채널을 유지함
- 긴 선에서도 실시간/확정 형태가 바뀌지 않고 입력 지연 기준을 통과함

검증 결과:

- Flow/Build Up 분리, prefix-stable Smoothing, 압력 곡선과 장치별 calibration 구현
- Scatter/Texture/Transfer/Color Dynamics 및 tilt/rotation/barrel mapping이 실제 픽셀을 각각 변경
- Smudge/Mixer/Pickup, captured PNG dab, brush bundle v2 저장·가져오기 및 누락 자원 진단 구현
- proprietary ABR dab decoder를 포함하지 않는 명시적 metadata-only 범위와 변환 안내 제공
- M4 focused 테스트 6개, UI Design 제외 전체 Painter 139개, Architecture/Debug boundary 5개 통과
- `debugCapture/painter/painting_m4`에서 동적 렌더 변화와 `.tspaint` 저장·재열기 SHA-256 parity 통과
- 독립 QA에서 8개 고급 범주, mouse/tablet Undo·Redo·저장·출력 parity 및 기존 상단 바 회귀를 재검증해 PASS
- 5,000점 스트로크 7,500 dabs/42.416 ms로 cap과 지연 기준 통과

## M5. 색상, 필터, 비파괴 보정

상태: 완료 (2026-08-03)  
선행 조건: M1, M2

목표:

- 외부 편집기로 이동하지 않고 기본 보정과 마무리를 수행하게 한다.

작업:

- RGB/HSB 숫자 입력, foreground/background active well, `X`/`D` shortcut
- Levels, Curves, Brightness/Contrast, Hue/Saturation, Color Balance
- Blur, Sharpen과 선택/레이어 범위 적용
- Adjustment Layer의 최소 비파괴 모델
- named swatch group과 ASE/GPL 등 검증 가능한 palette interchange
- sRGB 기준 gamut 경고와 display/output profile 경계

완료 조건:

- 모든 보정이 preview/apply/undo/action/export parity를 가짐
- Adjustment Layer가 원본 픽셀을 변경하지 않음
- 선택 영역 밖 픽셀이 필터 적용으로 바뀌지 않음

검증 결과:

- RGB/HSB 숫자 입력, foreground/background well, `X` swap 및 `D` 기본색 구현
- Levels/Curves/Brightness-Contrast/Hue-Saturation/Color Balance/Blur/Sharpen 공통 sRGB 엔진 구현
- 실제 Alpha8 선택 mask 기반 preview/apply/cancel/1-step Undo 및 선택 밖 픽셀 보존 통과
- 원본 raster를 변경하지 않는 Adjustment Layer와 `.tspaint` 저장·재열기·export parity 통과
- 이름 그룹을 보존하는 GPL/ASE 가져오기·내보내기와 sRGB gamut/profile 경계 보고 구현
- M5 focused 및 관련 회귀 39개, UI Design 제외 전체 Painter 145개, Architecture/Debug boundary 5개 통과
- `debugCapture/painter/painting_m5`에서 preview=commit, cancel/undo=원본, adjustment save/open SHA-256 parity 통과
- 독립 QA에서 잘못된/빈 GPL·ASE 거부, 범위 밖 HSB 원본 진단, output profile boundary를 재검증해 PASS

## M6. 파일 교환과 프로 출력

상태: 완료 (2026-08-03)  
선행 조건: M1, M2, M5

목표:

- `.tspaint`를 원본으로 유지하면서 일반 제작 파이프라인과 안전하게 교환한다.

작업:

- JPEG/WebP/TIFF export
- 16-bit PNG/TIFF와 16-bit Material Height
- layered PSD import/export의 지원 범위 정의 및 구현
- ICC profile embedding, soft-proof 경계, CMYK는 명시적 변환/제한 보고
- print bleed, trim, safe margin을 실제 export에 반영
- unsupported layer/effect를 자동 누락하지 않고 preflight에 표시

완료 조건:

- 내보낸 파일의 크기, 알파, bit depth, profile metadata 자동 검사
- PSD round-trip에서 지원 레이어의 이름/순서/불투명도/블렌드가 유지됨
- 지원하지 않는 항목은 bake 또는 blocked로 명시됨

검증 결과:

- JPEG/WebP/TIFF/PNG 8-bit와 RGBA 16-bit PNG/TIFF를 실제 재열어 크기·알파·비트 깊이·ICC 검사 통과
- Material Height 16-bit PNG/TIFF가 256개를 넘는 높이 값을 보존하고 PBR export의 `precision_files`에 포함
- 지원 PSD 레이어의 이름·순서·가시성·불투명도·블렌드·그룹 왕복 및 합성 최대 채널 오차 1/255 이내
- Adjustment/Clipping/Mask/Material/비지원 blend는 silent drop 없이 blocked 또는 명시적 단일 baked layer로 출력
- sRGB profile boundary, informational soft-proof 경고, CMYK 미지원 차단, bleed/trim/safe 픽셀 geometry 보고 구현
- M6 focused 14개, 관련 통합 38개, UI Design 제외 전체 Painter 159개, Architecture/Debug boundary 5개 통과
- `debugCapture/painter/painting_m6`에 형식별 실제 파일과 자동 검사 보고서 생성
- 독립 QA에서 고정밀 RGBA/Height 1,024개 이상 값, PSD 계층·속성·Undo, ICC·CMYK 제한·인쇄 geometry를 재검증해 PASS

## M7. 대형 캔버스와 GPU 지속성

상태: 완료 (2026-08-03)  
선행 조건: M1, M4

목표:

- 복잡한 4K 이상 문서와 장시간 페인팅에서 지연과 메모리 급증을 막는다.

작업:

- retained GPU texture/FBO와 tile upload
- texture/bristle/material brush의 GPU stamp atlas
- 레이어/mask compositor shader와 CPU parity fallback
- Material Height/Normal/AO 비동기 dirty-tile 갱신
- Wet Canvas GPU atlas와 bounded cache
- Undo delta memory budget, cache eviction, document stress telemetry

완료 조건:

- 4K 다층 문서와 긴 브리슬 스트로크의 정의된 latency/memory 예산 통과
- GPU/CPU fallback 결과 차이가 허용 오차 이내
- 원격/헤드리스 환경에서도 검은 화면이나 crash 없이 QPainter fallback

검증 결과:

- 256px document tile LRU와 실제 persistent OpenGL texture/FBO uploader, dirty-tile 전용 갱신 구현
- texture/bristle captured dab stamp atlas, Material Height/Normal/AO 및 Wet Canvas bounded tile cache 구현
- normal SourceOver GL compositor와 pre-applied mask 계약, advanced blend/mask QPainter parity fallback 구현
- Material map dirty 작업 큐의 dedupe·bounded eviction·완료 처리와 Undo 256MB 기본 예산/오래된 상태 축출 구현
- 3840x2160 초기 135타일 뒤 16x16 수정은 1타일만 재업로드, 강제 context loss에서 CPU tile 픽셀 parity 통과
- 4K 2,000점 브리슬 스트로크와 tile upload가 3초 예산 이내, M7 focused 6개 및 관련 30개 통과
- UI Design 제외 전체 Painter 165개, Architecture/Debug boundary 5개, `debugCapture/painter/painting_m7` QA 보고 통과
- 독립 QA에서 4K 타일 경계, 모든 cache eviction, Undo oversize, upload/compositor/cross-cache context loss를 재검증해 PASS
- 실제 OpenGL 성공 경로는 offscreen 환경에서 context 생성 불가로 미실행이며, QPainter fallback 픽셀 parity를 승인 근거로 기록

## M8. Painting 자동화 기준선 (제품 재승인 철회)

상태: 자동화 기준선 완료 (2026-08-03), 네이티브 제품 승인은 R0-R8까지 보류 (2026-08-04 감사)  
선행 조건: M0-M7

목표:

- 합성/offscreen 자동화로 Painting 작업 경로의 내부 기준선을 만든다.
- 이 결과만으로 네이티브 GPU, 물리 태블릿, 장시간 안정성 또는 외부 앱
  상호운용 제품 승인을 주장하지 않는다.

필수 작업 시나리오:

- 캐릭터 line/flat/render 작업
- 배경 thumbnail/block-in/detail 작업
- Material Paint impasto 작업
- 레퍼런스 사용, 선택/변형, 그룹/클리핑/마스크 작업
- 저장, crash recovery, 재열기, PNG/TIFF/PSD 교환
- 760x560, 1080p, High-DPI, 4K canvas, 태블릿 입력

완료 조건:

- Painting 전용 자동 테스트 100% 통과
- 각 시나리오의 실제 UI 캡처와 결과 파일 존재
- crash/recovery와 장시간 stress 테스트 통과
- 알려진 제한 목록과 지원 포맷 표가 사용자 문서에 반영됨
- Photoshop/Clip Studio/Corel Painter 전체 parity 표현은 사용하지 않고,
  검증된 Painting 작업 범위만 제품 문구로 사용

제품 지원 범위:

| 구분 | 검증된 범위 | 경계 |
| --- | --- | --- |
| 원본 문서 | `.tspaint`, 편집 상태·레이어·브러시 입력·복구 snapshot | Painting 모드 기준 |
| PNG | 8/16-bit, alpha, embedded sRGB ICC | 대화형 캔버스 자체는 8-bit |
| TIFF | 8/16-bit, alpha, embedded sRGB ICC | CMYK 변환 미지원 |
| JPEG | 8-bit, embedded sRGB ICC | alpha 미지원 |
| WebP | 8-bit, alpha, embedded sRGB ICC | 16-bit 미지원 |
| PSD | paint layer, group, visibility, opacity, 지원 blend | adjustment/clipping/mask/material/비지원 blend는 차단 또는 명시적 bake |
| 태블릿 입력 | pressure, tilt, rotation, tangential pressure 저장·재열기 | 실제 드라이버·기기 호환은 장치별 검증 필요 |
| 대형 캔버스 | 4K tiled cache, dirty update, bounded Undo/cache | headless에서 OpenGL 불가 시 검증된 QPainter fallback |

알려진 제한:

- 이 승인은 Painting 모드만 대상으로 하며 UI Design 모드는 포함하지 않는다.
- Photoshop, Clip Studio Paint, Corel Painter의 전체 기능 동등성을 주장하지 않는다.
- 작업·출력 기준 색 공간은 sRGB이며 CMYK 문서 변환은 제공하지 않는다.
- proprietary ABR 브러시 렌더링 동등성을 주장하지 않으며 검증된 metadata 교환만 지원한다.
- PSD로 직접 표현할 수 없는 Painter 기능은 자동 누락하지 않고 차단하거나 사용자가 선택한 bake로 출력한다.
- 실제 OpenGL context를 만들 수 없는 원격/headless 환경에서는 QPainter parity fallback을 사용한다.

검증 결과:

- 캐릭터 line/flat/render, 배경 thumbnail/block-in/detail, Material Paint impasto를 실제 Painter 문서·결과 이미지·UI 캡처로 생성
- 레퍼런스, perspective guide, 선택 변형, group, clipping, mask를 같은 제작 시나리오에서 사용하고 `.tspaint` 재열기 픽셀 parity 통과
- 760×560과 1920×1080 logical window를 DPR 1.5에서 실제 캡처해 각각 1140×840, 2880×1620 픽셀 증거 생성; 배경·Material 캡처도 1650×1080으로 검증
- PNG/TIFF/PSD 3개 시나리오 교환 통과. 독립 QA에서 발견한 layered PSD 역순 합성 결함을 수정하고 저장 직후 가시 RGBA parity gate를 추가
- 수정 후 character/material baked PSD는 최대 채널 오차 0, background 3-layer PSD는 독립 판독 최대 오차 1/255
- crash recovery snapshot 복원 결과가 원본과 동일하고 QA recovery 파일 cleanup 완료
- pressure/tilt X·Y/rotation/tangential pressure 5점 입력이 저장·재열기에서 모두 유지
- 3840×2160 문서 135타일, dirty update 240회, 3,000점 bristle stroke, bounded cache/메모리 stress 통과
- M8 focused 18개, UI Design 제외 전체 Painter 169개, Architecture/Debug boundary 5개 통과
- 별도 QA 에이전트가 파일 시그니처·두 PSD 판독기·캡처 4장·복구·태블릿·stress·지원 문구를 재검증해 최종 PASS

2026-08-04 근거 감사 정정:

- `tests_passed=True`, `QT_SCALE_FACTOR`, 합성 tablet stroke, in-process recovery,
  240회 microbenchmark가 제품 증거로 승격된 문제를 확인했다.
- 위 결과는 구현 회귀와 자동화 기준선으로는 유효하지만 제품 출시는 승인하지 않는다.
- 후속 기준과 실행 순서는
  `docs/PAINTER_EVIDENCE_AUDIT_AND_CORRECTION_MILESTONES_KO.md`의 R0-R8이 소유한다.

## 4. 실행 우선순위

즉시 실행 순서는 다음과 같다.

1. M0: 정확도와 입력 지연 회귀 동시 해결
2. M1: 레이어별 래스터 코어
3. M2와 M3: 레이어 합성, 선택, 변형
4. M4: 브러시 동역학과 Smudge/Mixer
5. M5와 M6: 보정, 색상 관리, 교환 포맷
6. M7: GPU/대형 문서 최적화
7. M8: 실제 제작 승인

M1 이전에 필터, PSD, Smart Object, 고급 Adjustment UI를 먼저 추가하지
않는다. 독립 픽셀 레이어가 없으면 이 기능들은 배경 표면이나 Sticker를
우회하는 두 번째 문서 모델이 되기 때문이다.

## 5. 핵심 검증 명령

```powershell
$files = Get-ChildItem -LiteralPath tests -Filter 'test_painter_*.py' |
  Where-Object { $_.Name -notlike 'test_painter_ui*' } |
  ForEach-Object { $_.FullName }
.\.venv\Scripts\python.exe -m pytest @files -q
.\.venv\Scripts\python.exe -m pytest tests\test_editor_architecture_rules.py -q
```

마일스톤별 QA 스크립트는 구현과 함께 `tools/qa_painter_painting_m*.py`
형식으로 추가하고, 결과는 `debugCapture/painter/painting_m*` 아래에
재생성 가능하게 저장한다.

## 6. 2026-08-06 M55 전수검사 완료 갱신

- 범위는 계속 Painting 전용이며 UI Design 모드는 제외한다.
- 공식 문서·수학/포맷 불변식·명시적 Tiger 정책·실제 실패/측정 계약으로
  숫자·품질·capacity·예외·fallback 근거를 재분류했다.
- Painting app 63개, test 68개, QA 45개와 AST 숫자 사이트 6,415개를
  조사했다. 미검토, 근거 미해결, stale, pending, defect, 미참조 모듈은 0이다.
- UI Design을 제외한 Painting 전체 회귀 639/639와
  architecture/debugCapture/evidence guard 36/36이 통과했다.
- 수정된 harness로 7,200초 장기 실행을 세 번 완료했고 workload error는
  모두 0이었다. 독립 M55 QA는 stored v3 판정을 deep-equal로 재계산하고
  P0/P1/P2 `0/0/0`, focused 33/33, raw 재실행 불필요로 판정했다.
- Windows Working Set은 resident shared/private memory 관찰값이고,
  PrivateUsage는 private Commit Charge이므로 반복 soak의 차단 retention 신호는
  PrivateUsage로 한정한다. 보편적인 leak-free 주장은 하지 않는다.
- 실제 고배율 모니터, 물리 태블릿, 사람의 시각 검토, 모든 외부 환경 조합은
  미검증 한계로 남긴다. 자동화 통과로 이 한계를 대체하지 않는다.
- 발견·수정 항목과 증거 링크의 전체 목록은
  `docs/PAINTER_PAINTING_FULL_AUDIT_CHANGE_LIST_KO.md`가 소유한다.
