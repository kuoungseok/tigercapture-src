# Painter Painting 근거 전수감사와 보정 마일스톤

작성일: 2026-08-04  
범위: Painter Painting만 포함, UI Design 제외  
상태: R0 근거 장부 재개방, R1/R2 물리 장치 대기, R3 반복 측정 진행·disk-full 미완료, R4-R7 보정 진행, R8 제품 재승인 미통과

## 1. 원칙

기능 이름, 경쟁 제품의 익숙한 동작, 자체 생성 이미지, 내부 테스트 통과만으로
제품 동작을 추정하지 않는다. 모든 주장은 다음 중 무엇으로 확인했는지 기록한다.

- 공식 제품·플랫폼·포맷 문서
- Tiger Studio 코드와 동일 경로를 실행한 자동 테스트
- 실제 네이티브 OS/GPU/디스플레이 실행
- 실제 태블릿 장치 입력
- 독립 프로그램에서 파일을 연 상호운용성 검사
- 구현자와 분리된 사람이 확인한 실제 UI·작업 결과

`app/painter_evidence_contract.py`가 이 증거 종류를 분리한다. 낮은 등급의
증거를 높은 등급 주장에 대신 사용할 수 없다.

## 2. 공식 기준 자료

| 영역 | 기준 자료 | 여기서 확인할 계약 |
| --- | --- | --- |
| Qt 태블릿 | [QTabletEvent](https://doc.qt.io/qt-6/qtabletevent.html) | pressure, x/y tilt의 -60..60도, rotation, tangential pressure와 미지원 장치의 0 값 |
| Qt 태블릿 예제 | [Qt Tablet Example](https://doc.qt.io/qt-6/qtwidgets-widgets-tablet-example.html) | 고해상도 드로잉 앱은 압축될 수 있는 합성 mouse event가 아니라 tablet event를 직접 accept하고, press/move/release별 실제 pressure·rotation을 보존 |
| Windows 펜 | [Windows Ink pen interactions](https://learn.microsoft.com/en-us/windows/uwp/ui-input/pen-and-stylus-interactions) | wet/dry ink 처리, pressure와 펜 속성, 마우스·터치 구분 |
| Wacom | [Wintab basics](https://developer-docs.wacom.com/docs/icbt/windows/wintab/wintab-basics/) | 장치별 pressure/tilt/tangential 범위와 기능은 `WTInfo`로 조회해야 함 |
| 펜 측정 방법 | [Microsoft Pen Down Latency](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/latency---down) | 물리 측정은 반복·영역 분산·활성압 조건이 필요함. 42ms는 장치 down-latency 기준이며 앱 지연 기준으로 전용하지 않음 |
| High-DPI | [Qt High DPI testing](https://doc.qt.io/qt-6.8/highdpi.html) | `QT_SCALE_FACTOR`는 하드웨어 없이 수행하는 테스트용 값이며 네이티브 DPI 증거가 아님 |
| OpenGL | [QOpenGLContext](https://doc.qt.io/qt-6/qopenglcontext.html) | `create`, `isValid`, `makeCurrent`, 실제 format, context loss 후 재생성 확인 |
| 레이어 그룹 | [Adobe layer groups](https://helpx.adobe.com/in/photoshop/desktop/create-manage-layers/get-started-layers/organize-layers-with-layer-groups.html) | 그룹 계층, 그룹 mask와 비파괴 편집 |
| Clipping | [Adobe clipping masks](https://helpx.adobe.com/photoshop/using/revealing-layers-clipping-masks.html) | base alpha와 clipped layer의 가시 범위, group blend 경계 |
| Layer mask | [Adobe layer masks](https://helpx.adobe.com/ca/photoshop/desktop/create-masks/layer-masks/add-layer-masks.html), [Clip Studio layer masks](https://help.clip-studio.com/en-us/manual_en/180_layers/Layer_masks.htm) | 래스터/alpha mask, 부분 투명도, 편집, enable, link/unlink, apply/delete |
| Perspective | [Clip Studio perspective rulers](https://help.clip-studio.com/en-us/manual_en/510_ruler/Perspective_Rulers.htm), [drawing with rulers](https://help.clip-studio.com/en-us/manual_en/510_ruler/Drawing_along_a_perspective_ruler.htm) | 1/2/3점, 편집 가능한 소실점·eye level, 방향별 snap |
| Smudge | [Krita Color Smudge engine](https://docs.krita.org/en/reference_manual/brushes/brush_engines/color_smudge_engine.html) | color rate, smudge length/radius, spacing, current/all-layer sampling 상호작용 |
| Dab·spacing·sensor | [Krita Pixel Brush Engine](https://docs.krita.org/en/reference_manual/brushes/brush_engines/pixel_brush_engine.html) | stroke는 tip impression(dab)의 연속이고 spacing이 밀도를 정하며 pressure·speed 등 sensor가 각 dab의 size/color/opacity를 조절 |
| Texture mode | [Krita Texture settings](https://docs.krita.org/en/reference_manual/brushes/brush_settings/texture.html) | pattern/scale/offset, alpha 기반 texturing mode, strength와 per-stroke random offset을 서로 다른 계약으로 검증 |
| Texture·Dual Brush | [Adobe textured and dual brushes](https://helpx.adobe.com/photoshop/using/creating-textured-brushes.html) | texture depth 0%는 pattern을 숨기고 100%는 low point에 paint가 없으며, dual tip은 primary와 secondary가 겹치는 영역만 칠함 |
| Grain·Water | [Corel Grain controls](https://product.corel.com/help/Painter/540213829/Main/EN/Win-Documentation/Corel-Painter-Grain-controls.html), [Water controls](https://product.corel.com/help/Painter/540215550/Main/EN/Win-Documentation/Corel-Painter-Water-controls.html) | grain 고정/랜덤 위치·회전과 pressure expression, wetness/pickup/dry-rate/diffusion의 독립 parameter-response |
| Thick Paint | [Corel Thick Paint](https://product.corel.com/help/Painter/540111162/Corel-Painter-en/Corel-Painter-Thick-Paint.html), [brush controls](https://product.corel.com/help/Painter-Essentials/540234649/Main/EN/Win-Documentation/Corel-Painter-Thick-Paint-Brush-controls.html) | paint load 고갈, resaturation, bleed, bristle density/clump, push/pull/scrape, stylus tilt |
| Oil loading·Dryout | [Corel Artists’ Oils controls](https://product.corel.com/help/Painter/540111162/Corel-Painter-en/Corel-Painter-Artists-Oils-controls.html), [Blending controls](https://product.corel.com/help/Painter/540219480/Main/EN/Win-Documentation/Corel-Painter-Blending-controls.html) | 유한 paint load가 이동하면서 줄고 Dryout은 pixel 단위임; tablet event 개수로 고갈시키지 않으며 Amount/Viscosity/Resaturation 의미를 분리 |
| Impasto | [Corel Impasto controls](https://product.corel.com/help/Painter/540215550/Main/EN/Win-Documentation/Corel-Painter-Adjust-and-create-Impasto-brush.html) | color/depth 분리, negative depth, depth source, plow와 교차 stroke 변위 |
| PNG | [W3C PNG 3rd Edition](https://www.w3.org/TR/png-3/) | truecolor/alpha 8·16-bit, 비연관 alpha, CRC와 정보 보존 |
| 레이어 문서 크기 | [OpenRaster Layer Stack Specification](https://www.openraster.org/baseline/layer-stack-spec.html) | 논리 image의 `w`·`h`는 양의 정수인 필수 속성이며 layer extents와 분리됨; 누락된 문서 크기를 임의 FHD로 만들지 않음 |
| Alpha compositing | [W3C Compositing and Blending Level 1](https://www.w3.org/TR/compositing-1/) | source-over의 premultiplied 공식과 이전 layer composite가 다음 backdrop이 되는 반복 구조 |
| TIFF | [TIFF Revision 6.0 index](https://www.loc.gov/preservation/digital/formats/fdd/fdd000022.shtml) | tag, sample depth, alpha/profile 상호운용 경계 |
| ICC | [ICC.1:2022](https://www.color.org/icc_specs2.xalter) | profile embedding과 실제 색 변환은 별개 |
| PSD library | [psd-tools API](https://psd-tools.readthedocs.io/en/stable/reference/psd_tools.html) | append는 top에 추가, composite/save 배경·alpha 계약 |
| Photoshop color | [Adobe soft proof](https://helpx.adobe.com/uk/photoshop/using/proofing-colors.html), [mode conversion](https://helpx.adobe.com/ca/photoshop/desktop/adjust-color/color-modes/convert-an-image-to-another-color-mode.html) | 출력 profile 변환, proof profile, CMYK 변환은 단순 ICC embedding이 아님 |
| Hue/Saturation | [Adobe Hue/Saturation](https://helpx.adobe.com/photoshop/desktop/adjust-color/color-corrections/apply-a-hue-or-saturation-adjustment.html), [Photoshop Elements numeric ranges](https://helpx.adobe.com/pl/photoshop-elements/desktop/working-with-colors/adjusting-color-saturation-hue-vibrance.html) | Hue는 -180…180도, Saturation/Lightness는 -100…100이며 숫자 단위를 숨겨 환산하지 않음 |
| Levels | [Adobe Levels adjustment](https://helpx.adobe.com/photoshop/using/levels-adjustment.html) | black/white input을 output 0…255에 매핑하고 중간 입력이 gamma를 조정한다는 기능 의미만 참조; Tiger의 gamma·blur·sharpen 조절 한계는 별도 제품 정책 |
| OKLab/OKLCH | [W3C CSS Color 4](https://www.w3.org/TR/css-color-4/) | OKLCH polar 변환, powerless hue epsilon `C <= 0.000004`, 중성축의 missing hue |
| Photoshop automation | [Adobe Photoshop scripting](https://helpx.adobe.com/photoshop/using/scripting.html) | Windows COM과 Photoshop JavaScript를 실제 외부 open/save 증거 생산자로 사용 |
| Magic Select | [Adobe Magic Wand](https://helpx.adobe.com/photoshop/desktop/make-selections/automatic-color-based-selections/select-areas-by-color-with-the-magic-wand-tool.html), [Krita Contiguous Selection](https://docs.krita.org/en/reference_manual/tools/contiguous_select.html) | RGB tolerance 0–255, contiguous와 all-layer reference의 의미를 직접 계약 |
| Windows disk-full | [Win32 system error codes](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--0-499-), [NTFS disk quota](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/fsutil-quota) | 실제 `ERROR_DISK_FULL=112` 또는 hard quota 거부를 요구하며 주입 예외와 구분 |
| Raster blur fallback | [Pillow ImageFilter.GaussianBlur](https://pillow.readthedocs.io/en/stable/reference/ImageFilter.html#PIL.ImageFilter.GaussianBlur) | OpenCV가 없거나 실패해도 blur 효과를 제거하지 않고 같은 sigma/radius 의미의 공식 Pillow fallback 사용 |
| Python 예외 처리 | [Python Errors and Exceptions](https://docs.python.org/3/tutorial/errors.html) | 의도한 예외 형식을 구체적으로 처리하고 예상하지 못한 예외는 전파하며, broad `Exception`을 잡아야 할 때는 기록 후 재전파하는 공식 지침 |
| Qt 객체 생존성 | [Shiboken module](https://doc.qt.io/qtforpython-6.8/shiboken6/shibokenmodule.html) | Python wrapper가 남아 있어도 C++ 객체가 유효한지는 `Shiboken.isValid()`로 판정 |
| Print resolution | [Adobe print resolution](https://helpx.adobe.com/ca/photoshop/desktop/crop-resize-transform/resize-adjust-resolution/resolution-specs-for-printing-images.html), [Clip Studio print manuscript guidance](https://tips.clip-studio.com/en-us/articles/1747) | 300 PPI는 일반 고품질 인쇄 권고, 흑백 만화 600 PPI도 제출 권고이며 프린터·인쇄소 지침이 우선 |
| Image dimensions | [Qt QImage](https://doc.qt.io/qt-6/qimage.html), [W3C PNG 3](https://www.w3.org/TR/png-3/) | Qt QImage는 16384 고정 한계를 선언하지 않고 PNG width/height는 0이 아닌 최대 `2^31-1`; Tiger의 16384는 현재 런타임 정책이지 포맷 한계가 아님 |

### 수치·용량 정책 추가 근거

- 브러시 프리셋과 현재 브러시의 최대 크기는 Adobe Photoshop 공식 문서의
  5,000 px 최대값을 함께 사용한다. 이는 최대 크기에서의 성능이나 물리 브러시
  재현성을 보증하지 않는다.
- 16,384 px 캔버스 상한은 Qt 또는 이미지 포맷의 한계가 아니라 현재 Tiger
  런타임 정책이다. Corel Painter 공식 문서의 16,382 px 상한은 비교 자료일 뿐
  Tiger 값의 근거로 둔갑시키지 않는다.
- 타일 크기·캐시·논리 undo 예산·복구 writer 동시성·아카이브 guard·queue·palette
  보존 수는 Tiger authored resource policy로 분류한다. 실제 telemetry와 명시적
  실패 동작은 검증하지만 모든 장비의 성능·메모리 안전 한계라고 주장하지 않는다.
- 참고: [Adobe Photoshop brush reference](https://helpx.adobe.com/pdf/cs6/photoshop_reference.pdf),
  [Corel Painter document dimensions](https://product.corel.com/help/Painter/540213829/Main/EN/Win-Documentation/Corel-Painter-Creating-Documents.html),
  [Qt QImage](https://doc.qt.io/qt-6/qimage.html),
  [W3C PNG 3](https://www.w3.org/TR/png-3/).

## 3. 전수감사 결과

현재 재생성 기준 조사 대상은 UI Design을 제외한 Painting app 49개, test 51개,
tool 39개와 핵심 문서 7개다. 현재 380개 test function을 색인하고 모든 app module이
test 또는 QA에서 정적으로 참조되는지 기록한다. 숫자 scale 변환은 단순 검색으로
끝내지 않고 percent→8-bit/단위구간 같은 명시 계약과 미검토 항목을 구분한다.

2026-08-04 추가 분리: `0..1` clamp 144행을 하나의 상식적 계약으로 승인하지 않았다.
그중 직접적인 `QColor.setAlphaF`, `QColor.fromRgbF`, `QPainter.setOpacity` 호출 3행만
[Qt QColor](https://doc.qt.io/qt-6/qcolor.html)와
[Qt QPainter](https://doc.qt.io/qt-6.8/qpainter.html)의 공식 0.0..1.0 계약에 연결해
exact-row hash로 승인했다. 남은 141행의 센서, 브러시 모델, 좌표, OpenGL 값에는 이
근거를 전이하지 않으며 계속 pending이다. ICC 헤더 경계 7행도
[ICC.1:2022 Table 17](https://www.color.org/specifications/ICC.1-2022-05.pdf)의
128바이트 헤더와 고정 필드 오프셋에 정확히 대응시켜 별도 승인했으며 rendering intent와
LittleCMS 동작은 제외했다. 이후 AST 숫자 리터럴 coverage 감사를 추가해 기존
비교·clamp 중심 1,921행 집계가 전수조사가 아니었음을 확인했다. Painting 숫자 리터럴
고유 행은 6,603개이며, 기존 라우터가 덮지 못한 행은 현재 5,025개다. 이 중 PSD
signature/version 2행을 [Adobe Photoshop File Header](https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/)
계약으로 분리·승인했으며 현재 AST 미해결은 4,814개다. 같은 Adobe 표의 26바이트 헤더와 필드
끝 오프셋을 검사하는 7행도 별도 승인했다. W3C PNG 3의 signature, 4+4+payload+4
chunk, CRC, IHDR-first, IEND-final 구조에 직접 대응하는 10행도 승인했다.
TIFF Revision 6.0 Section 2의 8-byte header, endian-aware 42 identifier,
first-IFD offset, 2-byte entry count, 12-byte entries, 4-byte next-IFD offset에
해당하는 AST 전용 4행도 분리 승인했다. 두 16-bit TIFF writer의 IFD layout, field
packing, word alignment, baseline RGB/strip/resolution/alpha tag 27행도 같은 규격에
직접 대응시켜 별도 승인했다. PNG16 writer의 IHDR 16-bit RGBA/RGB와 pHYs metre-unit
4행도 W3C PNG 3에 직접 대응시켜 승인하되 zlib level 6은 구현 정책으로 제외했다.
PNG IHDR bit-depth byte offset 24와 TIFF BitsPerSample tag 258을 읽는 3행도 규격에
직접 대응시켰다. NIST의 정확한 25.4 mm/in 1행과 ICC v2/v4 판별 2행도 별도 승인했다.
`.tspaint` v1/v2/v3 3행은 포맷 문서와 실제 마이그레이션 회귀에 근거한 Tiger 내부
호환 계약으로만 승인했다. uint16 채널 변환·배열 형상 불변식 13행은 uint8 전체범위 확장, uint16 보존, 미지원 정수형 거부 테스트 후 승인했다. PNG16 zlib level 6 두 행은 외부 규격이 아닌 명시적 Tiger 인코딩 정책으로만 승인했고, flat writer 배열 형상 4행은 구조 불변식으로 승인했다. 8/16-bit flat export 8행은 포맷 전체 능력이 아닌 Tiger 지원 범위로만 승인했다. PSD 비교용 8-bit premultiplication 6행은 W3C 정의와 정수 반올림 수학에 한정해 승인했다. intent 1 기본값 3행은 ICC 의미를 인용하되 Tiger 기본 정책으로만 승인했다. 내부 `asset://` 접두 길이 1행도 정확한 문자열 불변식으로 승인했다. Advanced Brush 숫자 55행은 실제 Painting 렌더 경로, 결정적 replay, Protect Texture 문서 우선순위, Undo/Redo와 문서 복원 테스트를 갖춘 명시적 Tiger 제품 모델로 승인했으며 물리 매체나 Adobe/Corel parity는 주장하지 않는다. 반복 soak baseline 구조 3행은 안정성 임계값이 아닌 운영 집계 계약으로만 승인했고, 3회 retention review 10행은 보편 통계가 아닌 Tiger evidence 정책으로만 승인했다. runtime 통계 13행과 Windows resource selector 3행도 합격 임계값이 아닌 보고 수학/API 계약으로 승인했다. 외부 증거 SHA-256의 1 MiB read chunk 1행은 Tiger I/O 정책으로만 승인했다. readiness flat-export matrix 4행도 포맷 전체 능력이 아닌 Tiger 지원 범위로만 승인했다. ARGB32 alpha byte 1행은 little-endian Windows 범위와 직접 회귀에 한정해 승인했다. reapproval aggregation 8행은 fail-closed 운영 구조로만 승인했다. AST 미해결은 4,814개다. 예외·품질·용량·의미 감사까지
합친 최신 감사 행은 6,975개, 미해결은 5,934개다. 5,934개 모두 exact-row 테스트와 근거 장부 승인이 필요한 후보이며,
현재 suppressed-exception 위치는 모두 구체 계약으로 라우팅했다. 라우팅은 승인이 아니다. TIFF ICC type, uint8→uint16 변환, 디코더 원인 보존,
히스토리 크기 사전 검증 결함은 회귀 테스트와 규격 근거로 교정 완료했다.
근거 분류는 외부 표준 79,
수학·포맷 불변식 127, 명시적 Tiger 정책 447, 범위 경계 177, 운영 실패 계약
120이다.
현재 미참조 app module은 0개다. 이후 Qt rotation 변환과 예외 억제까지 범위를
확장하면서 미검토 scale 변환 20개와 예외 억제 122개를 열었으며, 교정 전에는
감사 완료로 표시하지 않는다.
`tools/audit_painter_painting_evidence.py`가 동일 범위를 다시 스캔한다.

초기 감사기는 품질·성능 관련 변수명 주변만 찾아 숫자 비교문 전체를 놓쳤다.
이를 Painting 비교 제어문 전체로 확장해 1,505건을 구조 최소점 수, 표준 색공간
경계, 계산 퇴화 방지, 플랫폼 입력 설정, 명시적 Tiger authored 모델 및 실제
품질 판정 후보로 분류했다. 과거에는 확대 직후 83건만 미검토로 보고 이후 0건이라
표시했지만, 역감사 결과 이 0건은 광범위한 자동 승격으로 만들어진 잘못된 결론이었다.
그 비교·clamp 하위 집합의 수치는 더 이상 전수감사 총계로 사용하지 않는다. AST가
숫자 기본값, 할당, tuple/schema 값, 비교식 왼쪽의 숫자까지 고유 source line으로
색인하며, 현재 미라우팅·미승인 4,918행도 `numeric_control_audit_complete`를 실패시킨다. 제품
재승인은 coverage gap과 기존 미검토 목록이 모두 비어야 한다.

출력 프리플라이트의 기존 50% 오류·90% 경고 PPI 규칙은 공식 인쇄 품질 판정이
아니어서 제거했다. 300 PPI 컬러와 600 PPI 흑백 만화 값은 각각 Adobe와 Clip
Studio의 권고 출처를 노출하고 항상 인쇄소 확인을 요구하며, 부족한 값도 자동
품질 실패가 아니라 경고다. 150 PPI 대형 출력은 Tiger authored 시작점으로만
표시한다. 16384 px 제한 역시 Qt/PNG/TIFF/PSD 한계가 아니라 현재 Tiger 런타임
정책이며 보편 용량 주장을 하지 않는다.

PSD 내부 composite 비교의 기존 고정 2-level 허용치는 출처 없는 시각 유사도 값이었다.
처음 적용한 고정 1 LSB도 실제 다중 layer M8 background에서 최대 2 LSB가 측정되어
반증됐다. 현재는 보이는 8-bit pixel layer alpha-over 단계마다 최대 1 LSB라는
구현 간 반올림 오차 예산을 layer graph에서 계산하고 보고서에
`tolerance_contract=8bit_one_lsb_per_visible_alpha_over_stage`,
`byte_identical_claim=false`를 기록한다. 이 허용치는 Photoshop 알고리즘 parity나
눈으로 같은 품질이라는 주장이 아니다.
W3C는 source-over의 premultiplied 식과 0–1 값 범위를 정의하고 PNG는 8-bit
sample의 0–255 범위를 정의한다. “단계당 1 code unit”은 두 문서의 문구를 그대로
옮긴 것이 아니라 각 단계의 정수 반올림 차이가 다음 backdrop으로 전달된다는
구현 모델에서 도출한 보수적 상한이며, 3-layer 단위 테스트와 실제 M8 다중-layer
최대 2 LSB 결과로 검증한다.

AI Study의 기존 `quality_report`는 MAE 32, luminance correlation 0.86,
structural edge F1 0.42, focus MAE 28, editable stroke 1,000을 아무 측정 corpus나
외부 기준 없이 `ready` 판정에 사용했다. 이 숫자 판정은 제거했다. 비교값은 계속
원시 진단 지표로 제공하지만 상태는 `diagnostic_only`이고
`quality_threshold_claim=false`, `release_readiness_claim=false`다. Phase preset,
focus 가중치, brush 모양 계수는
`tiger_authored_reference_study_planner_v1`의 authored style parameter이며 검증된
재구성 품질 모델이나 경쟁 제품 parity가 아니다.

같은 검사에서 AI Study의 `edge_coverage >= 0.22` 진단과 material-response의
`coverage > 0.1` 표본 선택도 근거 없는 cutoff로 확인했다. AI Study는 edge의
mean/p95 원시값을 보고하고, material response는 coverage-weighted mean을 사용해
cutoff를 제거했다. Material preview의 0.025 시각 deadband는 최종 8-bit alpha에서
표현 가능한 한 단위인 `1/255` 양자화 경계로 교체했다.

M8 micro stress의 15초 tile·5초 stroke 제한도 기능 PASS에서 제거했다. tile 수,
budget bounded 상태, 실제 stroke pixel 생성만 correctness를 결정하고 시간은 raw
measurement로만 남는다. Large Canvas v3는 RGB 표준편차 8·사분면 차이 16·고유색
16 같은 임의 cutoff를 제거했다. 알려진 pattern을 직접 쓰는 source Canvas와
runtime-reconstructed Canvas를 같은 25/100/400% view에서 premultiplied 1 LSB로
비교하고, 비균일 표본 여부는 품질 기준이 아닌 blank-capture 방지 사실로만 쓴다.
M7의 4K upload·2,000-point stroke 3초 제한도 같은 이유로 PASS에서 제거했다.
시간은 원시값으로 남고 tile/dirty/hash/budget/fallback parity와 실제 stroke pixel만
기능 판정을 구성한다.
M8 readiness의 `long_stroke_session`은 실제로 3,000-point 단일 stroke였고
`bounded_memory`는 process memory가 아니라 tile cache budget이었다. v2 계약은
이를 `large_stroke_render`, `bounded_tile_cache`로 고쳐 넓은 주장을 제거한다.
같은 방식으로 `high_dpi`, `tablet`, `canvas_4k` boolean도 각각
`simulated_high_dpi_layout`, `synthetic_tablet_channel_roundtrip`,
`4k_tile_cardinality`로 바꿨다. offscreen window capture 역시 이름에 offscreen을
포함한다. 이 자동 기준선 항목은 native monitor·물리 tablet·실제 4K display
소비 증거로 승격되지 않는다.

Material brush capability의 style별 thickness/wetness/roughness 계수도 물성 측정값이
아니다. 보고서는 `tiger_authored_stylized_relief_v1`,
`coefficient_source=authored_style_preset_not_measured_physical_media`,
`physical_media_claim=false`, `external_brush_parity_claim=false`를 노출한다. 비호환
brush의 `simple_relief`라는 모호한 이름은 `stylized_reduced_relief`로 바꿨다.

Brush Dynamics의 pressure curve, stabilization, scatter, jitter, buildup, dab size와
alpha 계수도 `tiger_authored_deterministic_dab_dynamics_v1`로 분류한다. 동일 입력의
결정적 replay는 자동 검증하지만 물리 매체, driver latency, Photoshop/Corel brush
engine parity는 주장하지 않으며 이 경계를 `paint.state.brush.engine.model_contract`에
노출한다.

Bristle v2의 strand density cutoff와 fan/jitter/load 계수도 측정된 실제 강모나
페인트 유변학 모델이 아니다. 이를
`tiger_authored_deterministic_bristle_stylization_v1`로 별도 분류하고
`paint.state.brush.engine.bristle_model_contract`에 노출한다. 결정적 replay만
주장하며 `physical_bristle_claim=false`, `paint_rheology_claim=false`,
`external_brush_engine_parity_claim=false`로 경계를 고정한다.

OKLCH 변환은 표준 수학식 영역이므로 authored harmony 계수와 분리했다. 기존에는
회색 `(128,128,128)`의 수치 오차 chroma에서 약 89.9° hue를 만들고 최소 chroma
0.025를 강제해 중성색에 임의 색조를 넣었다. CSS Color 4의 powerless hue epsilon
`C <= 0.000004`를 적용해 hue를 missing(`NaN`)으로 반환하고, 이 경우 모든 harmony
mode는 중성 tonal 8색만 생성한다.
Powerless 경계 바로 위의 저채도 색을 강제로 chroma 0.025까지 올리던 floor도
제거해 입력 chroma를 그대로 사용한다. state는 `harmony_chroma_floor=0.0`과
`css_gamut_mapping_claim=false`를 노출한다. 현재 binary chroma reduction은 Tiger
gamut 처리이며 CSS의 전체 gamut-mapping 알고리즘 parity 주장이 아니다.

별도 QA 에이전트가 threshold 보정 범위를 구현 수정 없이 재검토해 집중 테스트
43개, AI Study diagnostic-only, M7/M8 raw timing, Large Canvas v3의 세 zoom delta 0,
PSD 단계별 LSB 예산, audit 미검토 항목 0개를 확인했다. 보고서는
`debugCapture/painter/independent_threshold_qa/report.json`이며 R8 집계가 schema와
read-only 역할을 검증한다. 이 agent PASS는 사람의 `visual_product_review`를
대체하지 않는다.

### 수치 clamp와 Actions 경로 재감사

초기 감사기는 비교식만 찾고 `min/max` clamp 및 Painting Actions 경로를 빠뜨렸다.
이를 보정해 `app/actions/paint_namespace.py`, `editor_adapter_paint.py`와
`painter_action_contract.py`를 포함한 Painting app 47개를 색인한다. clamp까지
포함한 numeric control 1,176건은 class/function context를 기록해 구조적 도메인,
공식 포맷·색상 도메인, 명시된 Tiger authored 모델/자원 정책, UI Design 제외
항목으로 나눴다. 경로 단위 catch-all로 0건을 만들지 않는다.

독립 읽기 전용 QA는 당시 소스·감사 보고서 SHA-256을 고정해 64개 집중 테스트와
1,505개 numeric control, 48개 capacity policy를 재검증했다. 판정은
`PASS_WITH_LIMITATIONS`이며 실제 태블릿·다중 모니터 DPI·사람 시각 검토나 릴리스
승인을 대신하지 않는다. 보고서는
`debugCapture/painter/independent_numeric_resource_qa_20260804/report.json`이다.
현재 exception/rotation 감사 확장으로 source hash가 바뀌었으므로 이 서명은 재사용하지
않고 최신 감사의 pending 계약과 근거 장부 후보 5,934개 해소 후 별도
QA가 다시 생성한다.

재감사에서 발견해 수정한 실제 결함은 다음과 같다.

- `dynamic_dabs`의 숨은 per-segment 256 dab cap을 제거하고 전체 polyline
  arc-length spacing으로 바꿨다. 같은 직선은 2개 control point와 33개 control
  point 모두 동일한 7,681 dab을 만든다.
- `.tspaint` asset entry는 POSIX `../`뿐 아니라 Windows `..\\`, drive absolute,
  UNC, NTFS alternate-data-stream colon을 거부하고 최종 resolve containment도
  확인한다.
- `paint.stroke.draw`의 512 strokes/2,048 points는 문서 용량이 아니라 단일
  atomic action/undo transaction의 Tiger authored payload guard로 노출한다.
  action brush width는 UI·프리셋과 동일한 5,000 px로 통일한다. Adapter의 60px
  clamp뿐 아니라 `paint.brush.set` JSON schema의 별도 60px maximum도 전수감사
  대상에 포함한다.
- AI Study analysis width/region, smudge radius/scatter copies, bristle count, grid
  size, large-canvas cache와 recovery writer 수치는 각각 모델·자원 계약에
  귀속하며 외부 제품 parity나 보편 성능 한계라고 주장하지 않는다.

### A. 제품 승인 증거의 잘못된 승격

1. `tools/qa_painter_painting_m8.py`가 `tests_passed=True`를 직접 전달한다.
   실제 pytest 결과 파일과 연결되지 않는다.
2. High-DPI PASS는 `QT_SCALE_FACTOR=1.5`로 만든 offscreen 테스트다. Qt 공식
   문서상 유효한 시뮬레이션 테스트지만 네이티브 모니터 검증은 아니다.
3. 태블릿 PASS는 직접 만든 `Stroke`와 가짜 `_TabletEvent`다. Painting test와
   QA에는 실제 `QTabletEvent(...)` 생성·전달이나 물리 장치 evidence가 없다.
4. OpenGL 성공 경로는 offscreen 환경에서 실행하지 못했다. 강제 실패와 CPU
   fallback 검증을 GPU 성공 검증으로 바꿔 말하면 안 된다.
5. “장시간 stress”는 4K 이미지의 240회 단일 픽셀 갱신과 한 번의 3,000점
   stroke다. 시간 경과, process RSS, handle 증가, autosave 경쟁은 측정하지 않는다.
6. “crash recovery”는 같은 프로세스에서 recovery 저장 함수를 부른 뒤 즉시
   restore한다. 프로세스 kill, 미완성 임시파일, 다음 실행의 recovery 발견이 없다.
7. M0 산출물은 이미지뿐이고 machine-readable `report.json`이 없다.
8. M8 그림은 실제 Painter 창에 표시되지만 픽셀 내용은 QPainter 도형을 직접
   layer raster에 주입한 것이다. 입력 도구로 line/flat/render를 완주했다는
   증거는 아니다.

결론: 기존 M8은 `automated_baseline_only`로 재분류한다. 기능 구현과 내부
회귀 결과는 유효하지만 네이티브 제품 출시는 아직 승인하지 않는다.

### B. 기능 의미 감사의 현재 판정

초기 전수감사에서 찾은 10건을 현재 소스와 증거에 다시 대조했다. 해결된 항목을
미구현 목록에 계속 두거나, 의도적으로 제한된 제품 경계를 해결된 것으로 부풀리지
않는다.

1. **해결:** polygon-only layer mask를 Alpha8 raster asset으로 이행했고 부분 alpha,
   gradient/brush 편집, link/unlink, apply/delete, transform과 문서 왕복을 검증했다.
2. **해결:** perspective overlay-only 경로를 1/2/3점 ruler와 실제 mouse/tablet
   공용 stroke sample의 선택 축 snap으로 교체했다.
3. **의도적 제한:** Material/Impasto/Wet 계수는 물성 측정값이 아니다. 현재 기능은
   `tiger_authored_stylized_relief_v1` 및 고정 synthetic metamorphic corpus로만
   주장하며 physical-media/외부 brush parity claim은 false다.
4. **해결:** `MaterialTileExecutor`가 실제 worker에서 derived-map bytes/hash를
   생산하고 revision stale/cancel/error telemetry를 노출한다.
5. **부분 해결:** round 기본 stroke와 retained tile texture의 실제 GPU 소비는
   검증했다. textured/wet/material/mask shader의 end-to-end GPU parity는 아직
   증명하지 않았고 QPainter product fallback으로 명시한다.
6. **해결:** 알 수 없는 객체를 64 bytes로 추정하던 accounting을 제거했다.
   현재 값은 실제 소유 QImage/QPixmap/CPython payload의
   `owned_logical_history_payload_bytes`이며 process memory claim은 false다.
7. **의도적 제한:** 16-bit PNG/TIFF container 왕복은 검증했지만 8-bit source에서
   새 정밀도가 생기지 않는다. `source_precision_kind`와
   `new_precision_created=false`를 기록하며 16-bit 편집 claim을 하지 않는다.
8. **해결(지원 경계 포함):** 실제 RGB ICC transform과 CMYK soft proof를
   LittleCMS 경로로 측정했다. 16-bit 비동일 profile transform은 조용히 8-bit로
   축소하지 않고 blocked preflight이며 CMYK 문서 편집 parity는 주장하지 않는다.
9. **부분 해결:** Adobe Photoshop 26.11.6의 실제 open/save 4-artifact corpus는
   통과했다. 이 PC에 없는 Clip Studio/Corel Painter corpus는 별도 미검증 경계다.
10. **해결:** M7/M8의 3/5/15초 cutoff를 correctness PASS에서 제거했다. 시간은
    raw measurement로만 남고 장시간 안정성은 3회의 실제 7,200초 관측 envelope로
    분리한다.

수치 검색과 별도로 `heuristic`, `approximation`, `simulation`, `synthetic`,
`mock/fake/proxy`, `placeholder`, `not implemented` 같은 의미 축소 표지를 app 47개에서
함수·클래스 문맥과 함께 감사한다. 각 표지는 증거 경계, synthetic corpus,
authored stylization, 명시적 사용자 placeholder, blocked preflight 중 하나로 귀속해야
하며 미분류 표지가 있으면 제품 재승인 집계가 실패한다.

감사 v2는 각 행에 `decision_basis`도 기록한다. 2026-08-04 역감사에서 파일명·함수명
패턴만으로 광범위한 수치를 `reviewed_*`로 승격하던 감사기 자체의 결함을 발견했다.
이 자동 승격을 제거하고 해당 행을 `candidate_explicit_ledger_*`로 강등했다. 현재
공용 `drawing.py` 안의 UI Design 함수가 generic 구조 규칙에 먼저 잡히던 분류 순서도
교정해 21개 판정을 Painting 미해결에서 명시적 범위 제외로 이동했다. 파일명만이
아니라 함수 문맥으로 제외하며 이를 회귀 테스트로 고정했다. 이어 선언형 Action
schema의 `minimum/maximum/minItems/maxItems`를 Action ID와 연결해 색인했다.
`paint.ui.*`를 제외한 Painting schema 판정은 현재 197개다. 비교·clamp 중심의
기존 1,921행 수치는 폐기했다. AST coverage를 포함한 최신 감사 6,975행 중 5,934행이
미해결이다. 모두 라우팅 또는 명시적 근거 장부 연결 대기이며, 기존 43개
suppressed-exception 위치도 구체 계약으로 라우팅했지만 미검증 계약은 pending이다. 입력·문서 크기·색상 조작,
1px 강제 축소, Actions brush 축소, paint 고갈, bristle 수 불일치, TIFF ICC 타입,
uint8→uint16 변환, 디코더 진단, 히스토리 크기 결함은 직접 회귀로 교정했다. 후보는 공식 출처, 수학·포맷
불변식, 또는 외부 제품 parity를 주장하지 않는 명시적 Tiger 제품 정책과 정확히
연결되기 전에는 완료로 세지 않는다.

감사 보고서는 이제 UTC 생성 시각과 app/test/tool/doc/두 decision ledger/감사기
자체를 포함한 파일별 byte 수·SHA-256 및 전체 inventory SHA-256을 기록한다. 따라서
소스가 바뀐 뒤 과거 `report.json`의 집계를 최신 결과처럼 재사용할 수 없다.
R8 집계도 이 inventory를 현재 workspace에서 다시 계산하며 파일 누락·byte 수·개별
hash·전체 hash 중 하나라도 다르면 `numeric_control_audit_complete`와 집계 유효성을
모두 실패시킨다.

명시적 FHD 대체 2곳을 generic UI-preview 후보에서 결함으로 재분류하자 동결된
`ui_layout_or_preview_only_policy_not_artwork_claim` 장부는 30행에서 28행으로 바뀌어
자동으로 stale 처리됐다. 28행을 다시 검사한 결과 색상 입력 geometry 2행, wet-canvas
건조시간 UI 변환 1행, palette harmony enum 선택 1행이 preview-only 범위에 잘못 섞여
있었다. 이 네 행은 각각 별도 계약으로 분리했다. 문서 상태나 committed stroke
pixel을 쓰지 않는 창·패널·popup·icon·brush-preview 23행만 새 exact-row hash로 승인해
현재 stale 계약은 0개다.

Wet Canvas 건조시간 계약은 기존 저장 범위 1..86,400초를 UI의 1..1,440분 전체 범위와
연결했다. 초→분은 양수 half-up 반올림을 명시하고 분→초는 정확히 60을 곱한다. 저장 가능한
모든 정수 초를 전수 검사해 최대 오차가 UI 최소 1분 때문에 생기는 59초뿐임을 확인했으며,
bool·분수·범위 밖 분 값은 거부한다. 실제 Material 메뉴도 1..1,440을 표시하고 721분을
43,260초로 문서 상태에 반영하는 통합 테스트를 통과했다. 상수와 변환식 6행은 별도
exact-row hash로 승인했으며 물리 페인트 건조시간 parity는 주장하지 않는다. 색상 입력
geometry는 계속 pending이고 palette harmony enum은 아래 의미 기반 fallback 계약으로 교정했다.

Painting의 output kind, palette harmony, layer blend 선택은 더 이상 “목록의 첫 행이
기본값일 것”이라고 가정하지 않는다. Qt 공식 문서대로 `findData()` 미발견값 `-1`을
검사하고, 호출자가 이름으로 선언한 `color`·`complementary`·`normal` 데이터만 fallback으로
찾는다. 그 fallback 자체가 없으면 다른 시각 행을 고르지 않고 실패한다. 첫 행을 무관한
항목으로 재배치한 테스트에서 요청값 선택, 이름 기반 fallback, fallback 누락 거부를 모두
검증했고 숫자 비교 2행은 scanner/AST 독립 exact-row 계약으로 승인했다. 근거:
[Qt for Python QComboBox](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QComboBox.html).

색상 입력 geometry는 내부 forward/inverse 수식끼리 비교한 최초 증거를 QA가 기각한 뒤
실제 부동소수점 `QMouseEvent` dispatch로 다시 검증했다. 두 wheel 크기의 세 꼭짓점 바로
안쪽과 centroid, SV field 네 모서리·외부 clamp·hue strip, 강제 8-DIP floor를 측정했고,
별도 `QT_SCALE_FACTOR=1/2` 프로세스에서 논리 geometry와 실제 SV event 결과가 동일했다.
Qt의 local `QPointF` 및 High-DPI DIP 계약만 외부 근거로 사용하며 wheel radius와 field
margin은 Tiger 입력 정책일 뿐 Adobe picker parity가 아니다.

출력 가이드는 저장된 output 설정을 별도로 재해석하지 않고 `normalize_output_settings`를
공유한다. 별도 QA가 발견한 `include_bleed=False` 불일치는 교정되어 trim-only 래스터에서는
설정에 bleed 값이 남아 있어도 물리 크기 fallback과 가이드 inset 모두 이를 제외한다.
safe margin은 축별 trim 절반까지만 적용해 작은 문서의 과도한 값도 음수 QRectF가 아니라
중앙의 0 extent로 수렴한다. A4 bleed/safe, trim-only 2480×3508 약 300 PPI, 10×8 mm의
100 mm safe margin, screen-mode 가이드 없음이 직접 테스트됐다. 프린터 승인이나 인쇄 품질
합격 주장은 하지 않는다.

최신 기능 회귀는 UI Design의 `test_painter_ui_*`와 장시간 `test_painter_soak_*`를
명시적으로 제외한 Painting 전용 48개 파일에서 427 passed다. Pillow의 의도적 truncated
TIFF fixture 경고 1건만 남았고 architecture/debug-capture boundary guard는 5/5 passed다.
처음의 광범위 filename 실행은 UI Design 테스트를 잘못 포함해 프로세스 종료가 발생했으므로
Painting 증거로 재사용하지 않는다.

8-bit 후보 55행도 그대로 승인하지 않았다. 최소 알파 1 또는 32를 강제하는 bristle,
pen opacity, tip detail, brush preview, panel icon 6행은 포맷 불변식이 아니라 Tiger
가시성 정책이므로 별도 pending 계약으로 분리했다. 순수한 RGB/RGBA/Alpha8/tone-curve
0..255 채널, per-channel selection tolerance, `/255` OpenGL/ASE 변환 51행만
수학·포맷 불변식으로 승인했다.

현재 집계는 수학·포맷 불변식 146, 외부 표준 81, 명시적 Tiger 제품 정책(외부
parity 주장 없음) 462, 명시적 범위 경계 178,
운영 실패·fallback 계약 174, 미해결 5,934이다. authored policy는 제품이 선택한 계약일 뿐 업계 표준이나 측정된
선호로 승격하지 않는다. `unresolved_decision_basis_rows`가 하나라도 남으면 재승인
집계는 실패한다.

초기 `pass/NotImplemented/Reserved` 검색에서 비활성 예약 항목이었던 Painting
Advanced Brush의 `Dual Brush`, `Noise`, `Wet Edges`, `Protect Texture`는 R4B에서
실제 Painting 렌더·저장·Undo·export 경로에 연결했다. 과거 예약 상태는 최신 제품
승인의 근거로 재사용하지 않으며, 현재 승인은 provenance-aware AST 호출 그래프와
독립 parameter-response/replay 테스트에만 의존한다.

### 예외 억제 경로 재감사

줄 단위 검색으로 놓치기 쉬운 `except ...: pass`와 core `painter_*.py`의 broad
Exception fallback을 Python AST로 app 47개 전체에서 함수·클래스 문맥과 함께
수집한다. 현재 broad suppression/fallback과 GL cleanup callsite를 합친 계약 행은
117곳이며 전부 구체 계약으로 라우팅돼 미분류 결함 위치는 0곳이다. exact-row
실패 테스트와 장부 해시가 일치하는 117행 모두를 운영 실패·fallback 계약으로 승인했다.
기본 폴더 fallback 3행과 메뉴 index 검증 1행은 예상 예외만
받도록 좁혀 suppressed-operation 집계에서 분리했다. 마지막 12행도 정확한 운영 오류를
노출하고 성공을 주장하지 않는 테스트와 transactional partial-output 테스트로 승인했다.
[Python os.replace](https://docs.python.org/3/library/os.html#os.replace)와
[Python tempfile](https://docs.python.org/3/library/tempfile.html)을 기준으로 destination과
같은 filesystem의 staging, 기존 파일 backup, commit 실패 rollback, temporary cleanup을
구현했다. generation·backup·install·removal·restore·directory/staging cleanup 실패를
주입했고, rollback 불완전 시 정확한 오류와 recovery staging 경로를 보존한다. 파일별 원자적
교체와 테스트된 다중 파일 rollback만 주장하며 전원 손실까지 포함한 전체 filesystem
transaction은 주장하지 않는다.
함수명만으로 실제 주 결과 보존이나 오류 노출을 증명하지 않는다.

`docs/PAINTER_EXCEPTION_DECISION_LEDGER.json`은 숫자 장부와 마찬가지로 정확한
path/class/function/handler text의 행 수와 SHA-256, 실패 경로 테스트, 근거 문구가
함께 고정되어야만 승인할 수 있다. 현재 exact handler를 가진 계약 20개와 117행은
모두 승인됐다. 이 중 Painter Action의 post-commit UI refresh 8행은
sticker·3D blockout·reference-board 데이터를 먼저 보존하고, 실패한 작업명·예외
형식·메시지를 `ui_refresh` 결과에 노출하는 실패 주입 테스트로 승인했다. Wet Canvas,
retained layer, reference, blockout, PBR, brush profile, recovery의 optional feature 9행도
기능 보고서·fallback 상태·운영 오류·recovery detail에 원문을 보존하는 테스트로 승인했다.
Painter canvas의 optional extension callback 11행도 interaction/context-menu 진단과
stroke 불변성을 검증해 승인했으며, double-click 실패 뒤 press callback으로 내려가 원인이
덮이던 fallthrough를 제거했다.
부모·이전 window/runtime·cutout 임시 자원 수명 7행도 primary operation 오류와 cleanup
오류를 별도 상태로 보존하고, 실패한 cutout이 sticker를 commit하지 않는 테스트로 승인했다.
`structured_async_worker_failure_telemetry`의 정확한 한 행만 승인했으며,
`MaterialTileExecutor._finish` 실패 주입 테스트가 type/message/kind/tile/revision의
32개 bounded queue 기록과 `failed=1`, `completed=0`을 직접 검증한다. 또한
`invalid_icc_reported_as_validation_error`의 한 행은 malformed payload 주입 테스트가
typed LittleCMS validation error와 `valid=false`, `littlecms_valid=false`를 검증한다.
제품 재승인의 required-source loop와 independent/threshold/numeric/soak-series decoder
5행도 malformed JSON 주입 테스트가 typed error, `loaded=false`, aggregation/release
실패를 직접 검증했다. 이후 clipboard/decode/overlay, Wet Canvas diffusion,
OpenCV→Pillow raster, OpenGL availability, canvas·retained GPU fallback와 cleanup,
Qt alpha/capability fallback 계약도 직접 실패 주입 후 승인했다.

별도 QA 후속 P1도 같은 규칙으로 교정했다. null·오크기·무renderer GPU compositor
결과는 성공으로 인정하지 않고 CPU QImage 경로로 되돌리며, 정상 runtime close 실패도
handles/owner를 먼저 비활성화한 뒤 typed cleanup telemetry로 남긴다. context를 만들지
않는 cheap status는 `dependency_ready`와 `candidate_backend`만 보고하고 실제
`active_backend`는 QPainter로 유지한다. capability probe 자체 실패도 status를
중단하지 않는다. Advanced Brush 감사기는 import provenance뿐 아니라 함수 parameter와
지역 assignment shadowing도 거부한다. Material OpenCV→Pillow 전환은 backend,
fallback count, typed reason을 Action state에 노출한다.

GL teardown은 Qt의 `QOpenGLContext.doneCurrent()`와 `QOffscreenSurface` GUI-thread
수명 규칙, Khronos OpenGL 삭제 entry point, Python 활성 예외와 exception note 규칙을
근거로 다시 작성했다. texture/renderbuffer/FBO/default bind/context/surface/session
정리는 한 번에 하나의 이름 있는 callback으로 제한하고, 실패 시 operation·type·message·
누적 횟수와 primary-error 보존 여부를 OpenGL status에 남긴다. 실패 주입 회귀는 FBO
release 실패가 기존 render 예외를 대체하지 않고 note와 telemetry로 남는지 검증한다.
[Qt QOpenGLContext](https://doc.qt.io/qt-6/qopenglcontext.html),
[Qt QOffscreenSurface](https://doc.qt.io/qt-6.8/qoffscreensurface.html),
[Khronos OpenGL reference](https://registry.khronos.org/OpenGL-Refpages/gl4/html/),
[Python Errors and Exceptions](https://docs.python.org/3/tutorial/errors.html)을 근거로 하며,
driver context-loss 뒤 실제 자원 회수 성공은 주장하지 않는다.
감사기는 helper의 `except` 한 줄만 승인하지 않는다. AST로 23개 named cleanup
delegate, helper handler, 그리고 호출자에게 예외를 전달하는 두 cleanup primitive까지
26행을 exact-row hash로 동결한다. `delete`/`done_current` 경계 밖에서 새로 추가되는
직접 `destroy`/`release`/`doneCurrent`/GL delete 호출은 즉시 미분류 결함이 된다.

- Canvas large-tile view sync와 PBR material-map cache 반영 실패
- palette library 디스크 저장과 material brush profile 적용 실패
- 손상되거나 읽을 수 없는 palette library를 무음 기본값으로 교체하는 load 경로
- Material tile worker의 원인 없는 실패 count와 OpenCV blur 실패 시 효과 제거
- Actions의 active dialog visibility, player time, canvas/export size 조회 실패

이 목록은 `unreviewed_suppressed_exception_sites`이며 0이 되기 전에는
`numeric_control_audit_complete`가 PASS하지 않는다. 수정 전 3회 soak의 소스와
보정 후 소스를 섞지 않는다. 입력·문서 크기, 색상 fallback, 1px 강제 축소,
Actions brush 폭 축소, bristle 이동거리 고갈/명시적 개수 계약, 운영 오류 노출을
보정했고 보정 후 소스는 별도 7,200초 soak로 다시 판정한다. 잘못된 Undo/복원
snapshot 크기를 1×1로 조용히 바꾸는 2행과 TIFF ICC Profile tag를 잘못된 field
type으로 쓰는 2행과 uint8 ndarray를 uint16 전체 범위로 확장하지 않는 1행도 추가 결함으로 분리한 뒤 교정했다. 모든 예외 위치는
구체 계약으로 라우팅했으며, 현재 exact handler를 가진 20개 계약 117행을 모두 실패
주입 테스트 후 승인했다.

각 예외 위치는 다음 네 계약 중 하나와 테스트를 가져야 한다. 저장·내보내기·문서
변경 실패는 호출자에게 전파한다. 비동기 worker 실패는 예외 형식·메시지·작업 종류·
revision을 bounded telemetry와 제품 상태에 노출한다. 선택 기능의 실패를 격리할
때는 주 결과 보존과 기능별 오류 상태를 함께 검증한다. `close`/FBO 해제 같은 정리
단계만 원래 예외를 보존하기 위해 무시할 수 있으며 그 범위를 정리 호출 하나로
제한한다. 빈 `except Exception` 뒤 임의 기본값을 반환하거나 사용자 작업 성공처럼
계속하는 경로는 허용하지 않는다.

수정 전 RED 기준선은 2026-08-04에 관련 9개 test module을 한 프로세스로 실행해
76개 중 50개 통과, 26개 실패로 고정했다. 실패는 입력 3, canvas 2, Actions 4,
문서 I/O 3, bristle 3, OpenGL 2, 운영 오류 4, autosave 오류 구조 1,
Advanced Brush 미구현 4건이다. 이 수치는 완료율이나 품질 점수가 아니라 수정 대상과
회귀 범위를 고정하는 진단 증거다.

동일한 9개 module의 보정 후 명령은 strict-integer와 GL 수명 회귀를 추가한 현재
83개를 모두 통과한다. module 목록은 `test_painter_stylus.py`,
`test_painter_new_canvas.py`, `test_painter_actions.py`, `test_painter_document_io.py`,
`test_painter_brush_engine_v2.py`, `test_painter_stroke_latency_guards.py`,
`test_painter_large_canvas.py`, `test_painter_autosave.py`,
`test_painter_advanced_brush.py`다.

별도 읽기 전용 QA는 관련 11개 module 102개와 evidence/soak/product/architecture
gate 24개, 합계 126개를 실패 없이 재실행했다. 동시에 `int(value)`가 실수와 bool을
문서 크기로 조용히 변환하는 새 결함을 보고했고, Painting canvas·OpenGL render·v3
document loader를 `operator.index` 기반 엄격한 정수 계약으로 보정했다. 19.9, `True`,
13.5 손상 입력 회귀를 포함한 관련 36개와 최신 focused 83개가 통과한다. QA는
corrected soak 완료, 최신 예외 pending과 전체 근거 후보 해소 전에는 승인 게이트를
열지 않았다.

Qt 입력 4건은 `StylusSample`의 출처 없는 0.82 pressure 기본값, tablet pressure
조회 실패 시 0.82 생성, rotation 조회 실패 시 180° 생성, Qt의 0°를 내부
비중립 회전으로 바꾸는 `/360` 변환이다. Qt 공식 계약은 pressure 0이 tip이
tablet에 닿지 않은 상태이고 rotation 미지원은 항상 0°라고 명시한다. 따라서
mouse는 별도 `mouse_stylus_sample()`의 명시적 1.0을 유지하되, 알 수 없는 tablet
축을 중간 압력이나 반회전으로 꾸미지 않는다.

같은 0.82 가정이 Action에서 pressure를 생략한 점, clipboard에 pressure가 없는
점, 구형 bristle stroke에 pressure curve가 없는 점에도 반복돼 있었다. Material
stroke는 pressure가 없으면 0.68 기반 sine curve까지 만들어 냈다. 입력이 없는
경우에는 brush width를 변조하지 않는 명시적 1.0 constant를 사용하고, 실제
pressure가 제공된 경우만 곡선을 적용하도록 통일한다. pressure curve preset의
제어점 0.82와 `0.18 + pressure*0.82` 폭 함수는 별도의 공개된 Tiger authored
response 모델이므로 이 “누락 입력 생성” 교정과 구분한다.

FHD도 같은 방식으로 구분한다. New Canvas의 `Full HD 16:9`는 이름이 보이는 Tiger
시작 프리셋이므로 허용하지만, 필수 resize 인자, 자동화 canvas/export 크기,
compositor frame size, 문서 loader의 누락 width/height를 `1920×1080`으로 바꾸는
경로는 입력이나 손상 상태를 숨기는 미해결 항목이다. v1/v2 문서에서 크기를 배경
asset으로 복구할 수 없으면 임의 해상도를 만들지 않고 원인과 필요한 복구 정보를
명시한 preflight 오류로 중단한다.

별도 QA의 2026-08-04 후속 검토는 새 blur fallback 테스트의
`sum > 0.9`도 출처 없는 품질 임계값이라고 지적했다. 해당 조건은 제거했고 shape,
dtype, 중심 감소, 인접 픽셀 확산이라는 구조적 결과만 검증한다. 같은 검토에서
누락 pressure의 bristle/Action/clipboard/Material 네 경로와 non-finite tablet
입력 회귀를 보강했다. 검토 보고서는
`debugCapture/painter/independent_numeric_resource_qa_20260804/review_followup.json`이며
PASS 또는 출시에 대한 승인이 아니다.

## 4. 보정 마일스톤

### R0. 증거 출처와 주장 재분류 — 근거 장부 재개방

- 모든 QA 결과에 evidence kind, producer, command, environment, artifact hash 기록
- M8 hardcoded test PASS 제거
- simulated/native/hardware/external/manual evidence를 대체 불가능하게 분리
- 기존 M0-M8 문구를 `automated baseline`과 `release evidence`로 재분류

완료 조건: 증거 출처가 없는 boolean만으로 release claim이 PASS할 수 없다.

2026-08-04 실행 결과:

- evidence kind뿐 아니라 각 레코드가 증명하는 claim을 명시한다. 같은
  `native_runtime` 레코드 하나로 DPI, GPU, 복구, 장시간 안정성을 한꺼번에
  통과시킬 수 없다.
- M8 QA의 하드코딩된 test PASS를 실제 pytest 하위 프로세스 결과로 교체했다.
  `--skip-tests`는 산출물만 만들며 readiness는 반드시 실패한다.
- M8의 offscreen workflow provenance에 남아 있던 별도 `passed=True`도 제거했다.
  character/background/material/editing/exchange/display/stress의 모든 leaf 결과를
  계산한 `workflow_passed`만 evidence record에 전달하며, 감사기는 모든 Painting
  QA producer의 `passed/ready/success=True` literal을 차단한다.
- `SPEC.md`와 기존 M8 문서의 제품 승인 표현을 철회하고 automated baseline으로
  재분류했다.
- `tools/audit_painter_painting_evidence.py`가 동일 범위 감사를 반복 생성한다.
- `docs/PAINTER_NUMERIC_DECISION_LEDGER.json`은 승인한 계약마다 정확한
  path/class/function/text 행 목록의 SHA-256과 행 수를 고정한다. 새 숫자나 변경된
  수치가 생기면 해당 계약 전체가 자동으로 미해결로 돌아가며, 파일명·함수명만으로
  승인되지 않는다.
- `docs/PAINTER_EXCEPTION_DECISION_LEDGER.json`도 같은 exact-row 규칙을 적용한다.
  현재 exact handler를 가진 20개 그룹 117행을 exact-row hash와 실패 경로 회귀로
  모두 승인했다. 원인 노출 계약 없이
  `except` 위치를 승인하지 않는다.

### R1. 실제 입력과 latency 측정

- 실제 QTabletEvent event path 캡처 도구
- Qt device capability와 Wintab/Windows Ink 장치 범위 기록
- pressure/tilt/rotation/tangential/button/eraser/palm 동시 입력 corpus
- event timestamp → wet frame → committed frame latency percentile 측정

완료 조건: 최소 2개 제조사 실제 장치 결과와 raw anonymized report. 장치가 없는
환경에서는 harness 완료까지만 표시하고 제품 승인은 blocked로 유지한다.

2026-08-04 진행 결과:

- `tools/qa_painter_tablet_input.py`가 실제 Qt `TabletPress`, `TabletMove`,
  `TabletRelease`와 pressure/tilt/rotation/tangential/button/device identity를
  raw event corpus로 기록한다.
- 단위 회귀는 fake event만 쓰지 않고 PySide6의 실제 `QPointingDevice`와
  `QTabletEvent` 객체를 생성해 Qt channel 변환을 검증한다. 이는 Qt 객체 계약
  증거이며 실물 digitizer·driver·latency 증거로 승격하지 않는다.
- 서로 다른 clock origin을 빼서 latency로 부르지 않으며 paint-event 수신도
  물리 pen-down/display latency로 주장하지 않는다.
- 현재 네이티브 점검은 tablet event 0건, device 0개로 `blocked_external`이다.
- 공식 Qt 계약 재대조에서 rotation은 0°가 stylus tip이 tablet 위쪽을 향한
  실제 방향이며 미지원 장치도 0을 보낸다는 점을 확인했다. 현재 내부
  `StylusSample.rotation=0.5`는 무회전 중심값인데 Qt degree를 단순 `/360`해
  실제 0°를 내부 최솟값으로 만드는 변환 결함이 있다. 수정 시
  `((degrees + 180) % 360) / 360`의 signed-centered 표현을 명시하고
  0°→0.5, +90°→0.75, -90°/270°→0.25를 회귀로 고정한다. 0.5 중심 표현은
  Qt의 숫자 계약이 아니라 기존 brush dynamics가 사용하는 명시적 Tiger 내부
  정책이다. 물리 장치 capability 검증은 여전히 별도다.

상태: 하네스 완료, 실제 2종 장치 corpus와 물리 latency 측정 대기.

### R2. 네이티브 DPI·한국어·OpenGL

- offscreen/QT_SCALE_FACTOR 없는 Windows 실행
- 실제 screen logical DPI/DPR, monitor 이동, 글꼴 family와 glyph coverage 기록
- QOpenGLContext create/isValid/makeCurrent, 실제 version/vendor/renderer/FBO 확인
- context loss 복구와 CPU parity

완료 조건: native 캡처와 GPU report가 같은 실행 세션의 hash로 연결된다.

2026-08-04 진행 결과:

- 강제 QPA/scale factor 없이 Windows 플랫폼, screen DPI/DPR, 한글 glyph,
  Qt OpenGL FBO와 실제 DrawingCanvas 기본 스트로크 renderer state를 기록한다.
- 측정 중 PyOpenGL FBO 심볼과 Qt context의 불일치를 발견했다. 기본 스트로크
  FBO를 공식 Qt `QOpenGLFramebufferObject`와 `QOpenGLPaintDevice` 경로로
  교정했고 제품 `paintEvent`의 네이티브 OpenGL 사용을 재측정했다.
- 현재 WinDisc 화면은 1920×1080, DPR 1.0, logical DPI 96이며 물리 크기를
  제공하지 않는다. 한글 glyph와 기본 스트로크 GPU 경로는 통과했지만 native
  high-DPI claim은 실패 상태다.
- GPU 증거는 round 기본 스트로크에만 한정한다. textured/wet/material/mask와
  zero-readback widget display는 증명하지 않는다.

상태: 기본 스트로크 GPU 경로 완료, 실제 high-DPI 화면·확장 경로 검증 대기.

### R3. 실제 crash와 장시간 안정성

- 별도 child process를 paint/autosave 중 강제 종료
- 다음 프로세스에서 snapshot 자동 발견·복원
- truncated ZIP/manifest, disk-full, permission, concurrent autosave fault injection
- 2시간 이상 configurable soak에서 RSS, GDI/USER handle, latency p50/p95/p99 기록

완료 조건: 임의의 고정 시간 threshold가 아니라 baseline 대비 증가율과 leak slope를
보고하고, 실패 artifact를 보존한다.

2026-08-04 진행 결과:

- `tools/qa_painter_crash_recovery.py`가 제품 autosave 경로를 실행한 별도 Painter
  프로세스를 강제 종료하고 새 프로세스에서 snapshot 발견·복원을 수행한다.
- 첫 측정은 복원은 성공했지만 픽셀 parity가 실패했다. 원인은 저장 손상이 아니라
  `Stroke.width_px`가 문서에 저장되면서도 export/merge/mask/clipboard 합성에서
  현재 editor viewport 폭으로 다시 환산되던 좌표 계약 결함이었다.
- 브러시 크기를 문서 픽셀로 고정하고 명시적 output resize에서만 문서 크기 대비
  배율을 적용했다. 재측정은 writer 강제종료, 다음 프로세스 복원, 전체 RGBA
  SHA-256 parity를 모두 통과했다.
- 이 결과는 autosave 완료 후 crash 한 corpus에 한정된다. ZIP 교체 중 종료,
  truncated manifest, disk-full/permission, 장시간 soak는 아직 통과하지 않았다.
- Recovery 목록은 이제 ZIP의 `document.json`, JSON schema, 전체 entry CRC를
  확인하고 손상된 archive를 복원 대상으로 제시하지 않는다. truncated ZIP
  회귀는 통과했지만 손상 snapshot 격리·사용자 경고 UX는 후속 범위다.

상태: 실제 다음-프로세스 crash recovery와 수정 전 소스의 7,200초 native soak
3회는 생존 조건을 통과했다. 그러나 3회 envelope는 1·3차 실행의 후반 working-set과
private-usage 양의 retention 때문에 `evidence_incomplete`이며 leak-free 증거가 아니다.
3차 원본은 `debugCapture/painter/soak/20260804-125505-f3b07525/report.json`, 집계는
`debugCapture/painter/soak/three_run_envelope/report.json`이다. 수정 전 진단은 300회
렌더에 GL context를 300회 만들었고 canvas-lifetime session 재사용 보정 후 같은
진단은 300회에 1회 생성으로 줄었다. 각각
`debugCapture/painter/gl_context_churn/pre_fix_report.json`과
`post_fix_report.json`에 보존한다. 이 짧은 진단만으로 누수 해결을 주장하지 않는다.
첫 보정 후 soak는 후속 strict-integer 결함 수정으로 최종 소스와 달라져 중간 측정으로
종료했다. 해당 수정까지 포함한 7,200초 native soak는
`debugCapture/painter/soak/20260804-154034-4349048a`에서 수용 판정을 통과했다.
다만 그 뒤 파일 교환·히스토리 결함을 수정했으므로 새 소스의 증거로 재사용하지 않고
동일 조건의 corrected-source soak를 다시 실행한다. 실제 disk-full은 관리자
권한의 격리 VHD가 필요해 미완료다.

현재 자동화 기준선: UI Design 제외 Painter 376개와 architecture/debug boundary
5개, 합계 381개 통과. 이 숫자는 `release_ready=false`인 구현 회귀 기준선이지
제품 승인 수가 아니다.

### R4. Mask와 Perspective 의미 보정

- polygon layer mask를 실제 Alpha8 raster mask asset으로 이행
- brush/gradient 편집, enable, link/unlink, apply/delete, transform semantics
- 1/2/3점 perspective ruler와 방향별 stroke snap

완료 조건: Adobe/CSP 공식 절차를 Tiger 기능별 test matrix로 재현한다.

### R4B. 고급 브러시 예약 항목 계약화 — 제품 연결·독립 QA 완료

구현 의미는 다음 공식 문서에 고정한다.

- [Adobe textured/dual brush](https://helpx.adobe.com/photoshop/using/creating-textured-brushes.html): texture pattern/scale/depth와 primary-secondary tip 교차 영역
- [Adobe Brush Settings panel](https://helpx.adobe.com/photoshop/desktop/apply-painting-techniques/brushes-presets/display-brush-panel-brush-options.html): 항목별 enable과 설정 그룹의 구분
- [Corel Painter Grain controls](https://product.corel.com/help/Painter/540215550/Main/EN/Win-Documentation/Corel-Painter-Grain-controls.html): 고정 grain, dab/stroke별 randomization, jitter 의미
- [Corel Digital Watercolor](https://product.corel.com/help/Painter/540235477/707000/EN/Doc/Working_with_Digital_Watercolor_brushes.html): Wet Fringe는 젖은 stroke 가장자리의 물·안료 pooling이며 drying 전 상태와 결합
- [Krita Pixel Brush Engine](https://docs.krita.org/en/reference_manual/brushes/brush_engines/pixel_brush_engine.html): brush stroke를 tip dab의 연속으로 보고 spacing과 sensor response를 서로 독립된 축으로 검증
- [Krita Texture settings](https://docs.krita.org/en/reference_manual/brushes/brush_settings/texture.html): pattern/scale/offset, alpha texture mode, strength와 stroke별 random offset을 구분

- `Dual Brush`: Adobe 계약대로 primary와 secondary tip mask의 교차 영역만
  deposit하며 diameter/spacing/scatter/count와 결합 mode를 각각 측정한다.
- `Noise`: “자연스러워 보이는 임의 노이즈”가 아니라 seed를 저장한 결정적 dab
  modulation으로 한정하고 동일 문서 replay parity를 요구한다. Adobe parity는
  실제 외부 raster corpus가 생기기 전에는 주장하지 않는다.
- `Wet Edges`: 단순 어두운 테두리 필터로 대신하지 않는다. 현재 Wet Canvas의
  수분/확산 자산과 결합할지, 별도 per-stroke edge accumulation인지 공식 제품
  corpus로 분리해 검증한 뒤 활성화한다.
- `Protect Texture`: Adobe의 여러 textured brush preset이 같은 pattern/scale을
  공유하는 설정 계약으로 구현하며 paint 결과 효과처럼 이름만 연결하지 않는다.

완료 조건: 네 항목 모두 활성화 시 독립 parameter-response, 저장/Undo/export,
결정적 replay가 통과하고 비활성 시 기존 결과와 byte parity를 유지한다.

2026-08-04에는 Painting Advanced Brush의 `Dual Brush`, `Noise`, `Wet Edges`,
`Protect Texture`를 UI Design 작업과 분리된 Painting 엔진·preset/action 설정 경로로
구현했다. 기존 Texture 슬라이더나 Wet Canvas를 증거로 재사용하지 않고 별도
document-level texture, per-stroke seed, dual-mask 교차와 pigment/water 상태를
`advanced_dab_alphas`에서 결합한다.

`app/painter_brush_dynamics.py::dynamic_dabs`가 이 진입점을 실제 호출하고
`DrawingCanvas._paint_stroke`가 live와 committed 렌더 모두 같은 코어를 소비한다.
비활성 byte identity, 활성 픽셀 변화, 동일 seed replay, Protect Texture 문서 설정
우선순위와 scale 반응, 잘못된 중첩 설정 진단, Undo/Redo, 문서 payload 복원을 테스트했다.
감사기는 AST one-hop 호출 그래프로 네 primitive와 비테스트 제품 경로를 연결하며 현재
네 행 모두 `product_paths=[app/painter_brush_dynamics.py]`,
`advanced_brush_product_integrated=true`다. UI Design 컨트롤 완성은 이 Painting 범위의
승인 근거가 아니며, 물리 wet-media 또는 Adobe/Corel parity도 주장하지 않는다.

별도 QA가 찾아낸 무제한 228,304-dab/약 111.7 MB 경로는 stroke당 8,192 dab의
측정 기반 Tiger 실행 예산으로 보정했다. 이는 포맷·품질·외부 제품 한계가 아니다.
전체 arc-length를 균일 재표본화해 양 끝점과 검사한 모든 segment를 보존하고, Action
상태에 저하 stroke 수와 예상/실제 dab 수를 노출한다. 렌더는 authored
`brush_dynamics`를 변경하지 않는다. 최신 256×256 최악조건 측정은 228,304개 예상에서
8,192개를 생성했고, generation 중앙값 26.0007 ms, QImage 중앙값 54.7404 ms,
tracemalloc peak 4,432,465 bytes였다. 별도 16K/5,000점 QA도 8,192개와 약 4.78 MB로
제한됐다. 이 측정은 해당 장비의 bounded-materialization 근거일 뿐 보편적 frame-time
보장이 아니다.

### R5. Brush·Smudge·Wet·Impasto 검증 — 완료 (자동 기능 증거)

- 현재 효과를 `stylized`로 명명하고 물리 simulation 주장을 제거
- 공식 parameter-response 행렬: load 고갈, pickup/resaturation/bleed, smudge
  length/radius/overlay, plow/negative depth, tilt knife
- 자체 reference corpus와 monotonic/metamorphic test, CPU/export parity

완료 조건: 각 control이 이름만 존재하지 않고 독립적으로 측정 가능한 결과를 만든다.

2026-08-04 실행 결과:

- Smudge에 Color Rate, Smudge Length, Smudge Radius를 실제 carried-color
  렌더 경로와 Inspector/Action/persistence에 연결했다.
- `app/painter_media_response.py`의 고정 synthetic corpus가 Smudge 3개 제어,
  Wet Canvas Mix/Bleed/Pickup/drying, Material load/thickness/wetness/gloss/
  roughness의 픽셀·채널 반응을 독립적으로 측정한다.
- `tools/qa_painter_media_response.py` 결과는
  `debugCapture/painter/media_response/report.json`에 저장한다. 현재 측정된
  항목은 모두 response=true이나 이는 품질 또는 물리 매체 검증이 아니다.
  보고서가 `automated_measurement`, `quality_threshold_claim=false`,
  `physical_media_validation=false`를 명시한다.
- Krita 공식 의미대로 Overlay는 blend mode가 아니라 current layer/all
  layers sampling 토글로 구현했다. all-layer projection에서 얻은 dab별 RGBA를
  stroke에 저장하므로 하위 레이어를 나중에 바꿔도 이미 주운 색이 재샘플링되지
  않는다. Smear/Dulling을 분리하고 Radius는 Dulling에만 적용한다.
- Corel 공식 의미대로 Plow는 교차한 기존 signed relief를 knife normal 쪽으로
  변위시키며, Negative Depth는 양의 높이를 약하게 만드는 대신 별도 excavation
  채널과 음의 signed height를 만든다. PBR height 병합은 해당 경우
  `signed_neutral_0_5` encoding을 명시한다.
- 자동 Resaturation은 authored point-load 회복과 별도인 저장 제어값이다.
  load 고갈 뒤 선택색/paint load를 보충하며 0/100% height 합 반응을 고정
  corpus에서 독립적으로 측정한다.
- Overlay Smudge PNG export, Material signed-depth PBR merge, Wet Canvas export,
  `.tspaint` v3의 sampled RGBA/Plow/Resaturation/Negative Depth round-trip을
  회귀로 고정했다.
- 최신 R5 포함 전체 자동 게이트는 Painting `376 passed`, architecture/debug-boundary
  `5 passed`다. 이는 parameter-response와 내부 parity 완료 증거이며 실제
  물감의 물리 정확도나 출시 승인이 아니다. M8 분류는 계속
  `automated_baseline_only`, `release_ready=false`다.
- live Smudge/Mixer/Pickup은 별도의 committed current-layer sampling image를
  사용한다. 투명 live overlay와 pen-up direct layer render 사이의 허용 차이는
  premultiplied-alpha 8-bit 반올림 1 code value뿐이며, 기존처럼 live cache의
  투명 픽셀을 샘플링해 pen-up 때 색이 바뀌는 경로를 제거했다.
- 전체 자동 회귀 결과는 Painting `376 passed`, architecture/debug-boundary
  `5 passed`다. `debugCapture/painter/painting_m8/report.json`은
  `baseline_passed=true`, `classification=automated_baseline_only`,
  `release_ready=false`를 유지한다.

### R6. 정밀도·색상·파일 상호운용

- 8-bit source의 16-bit 포장과 실제 16-bit source를 보고서에서 분리
- ICC v4 validation과 실제 profile transform/soft proof
- Photoshop/Clip Studio/Corel 또는 확보 가능한 외부 앱 open/save corpus
- PSD/PNG/TIFF corruption, alpha, profile, layer ordering 검사

완료 조건: Tiger 내부 reader만으로 상호운용 PASS를 선언하지 않는다.

2026-08-04 실행 결과 — 완료(측정된 외부 앱 범위):

- `source_precision_kind`는 네이티브 uint16/float와 8-bit 승격을 분리하고
  `new_precision_created=false`를 기록한다. 8-bit 입력을 16-bit 컨테이너에
  쓰는 행위를 16-bit 편집 정밀도로 승격하지 않는다.
- ICC header/크기/signature/v2·v4/LittleCMS validation을 추가했다. 설치된
  Dell RGB 프로파일 사이의 비동일 변환과 RSWOP CMYK soft proof가 실제 픽셀을
  바꾸고 alpha를 보존하는지 측정했다. 현재 Pillow 경로가 16-bit 비동일 변환을
  8-bit로 양자화하므로 이 조합은 조용히 처리하지 않고 명시적으로 차단한다.
- PNG는 전체 chunk CRC·순서·IEND를, TIFF는 byte order/magic/IFD 범위와 완전
  decode를, PSD는 header/version/depth/composite/ICC/layer decode를 검사한다.
  손상 PNG, 잘린 TIFF, signature 손상·잘린 PSD는 유효한 입력으로 통과하지 않는다.
- layered PSD에 검증된 sRGB ICC를 포함하며 저장 후 내부 composite parity와
  profile 무결성을 검사한다. 내부 reader 결과는 외부 앱 증거로 분류될 수 없도록
  `app/painter_interop_evidence.py`가 producer/version/execution/artifact hash를
  별도로 검증한다.
- 설치된 Adobe Photoshop 26.11.6을 Windows COM + Photoshop JavaScript로
  실행하여 Tiger PNG8, 네이티브 PNG16/TIFF16, 3-layer PSD를 실제로 열고
  PSD 사본으로 저장했다. 4개 모두 fresh nonce, 64x48 크기, ICC 인식,
  8/16-bit 구분, alpha round-trip, Top/Middle/Bottom 순서, SHA-256 artifact
  검증을 통과했다. 보고서는
  `debugCapture/painter/external_interop/report.json`이다.
- 색관리 측정 보고서는
  `debugCapture/painter/color_management/report.json`이다. Clip Studio/Corel은
  이 PC에 설치되어 있지 않아 검증 대상으로 가장하지 않았다.

R6 완료는 위 Photoshop 26.11.6 코퍼스와 현재 지원 포맷 범위에 한정한다.
CMYK 파일 생성, 16-bit 비동일 ICC 변환, Clip Studio/Corel 상호운용까지
지원한다는 뜻은 아니다.

### R7. 대형 캔버스 경로 실사용 보정

- renderer가 retained GPU tile/stamp atlas를 실제 소비하는지 trace
- Material dirty tile을 실제 executor에서 처리하고 stale/cancel semantics 검증
- 실제 process RSS와 GPU resource count 기반 budget
- 4K/8K 다층 작업의 입력·zoom·save 동시 부하

완료 조건: telemetry 객체 존재가 아니라 사용 경로 trace와 결과 parity가 있어야 한다.

2026-08-04 실행 결과 — 완료(측정 범위 및 fallback 포함):

- 기존 GL tile uploader는 texture를 만들었지만 Canvas에는 원본 전체 QImage가
  전달되어 표시 단계에서 texture를 소비하지 않았다. 이제 완전한 tile set은
  `PainterRetainedGLTileUploader.composite_tile_records()`가 실제 texture handle을
  FBO에 그린 결과를 Canvas raster 입력으로 사용한다. tile이 하나라도 eviction된
  layer는 불완전 이미지를 만들지 않고 `source_qimage_incomplete_tile_cache`로
  명시적 fallback한다.
- Windows Qt context에서 PyOpenGL의 FBO 함수 포인터가 비어 있던 실제 실패를
  확인해 출력 FBO와 texture 수명은 Qt 객체로 소유하고, RGBA8 upload/draw/readback은
  현재 Qt context의 함수 포인터를 사용하도록 보정했다. 512x256 반투명 코퍼스가
  8개 texture를 실제로 읽고 premultiplied-alpha max delta 1 이하로 통과했다.
  `debugCapture/painter/native_environment/report.json`의 retained-tile claim은
  PASS지만, 같은 환경의 DPR은 1.0이고 물리 태블릿도 없어 전체 native report는
  계속 FAIL이다.
- Material derived-map 출력 tile은 `MaterialTileExecutor`가 실제 RGBA bytes,
  크기, SHA-256을 worker에서 처리한다. kind별 revision이 바뀐 과거 결과는 stale로
  폐기하고 cancel도 revision을 무효화하며, pending/result 수와 실패를 telemetry로
  노출한다. 단순히 queue를 비운 것을 비동기 처리 완료로 부르지 않는다.
- `tools/qa_painter_large_canvas_runtime.py`는 고정 시간 PASS 없이 별도 네이티브
  프로세스에서 4K 3-layer와 8K 2-layer를 full upload, Canvas 25/100/400% zoom,
  1-pixel dirty update, material executor, PNG save/reopen까지 실행했다. 독립 QA가
  최초 코퍼스의 단색 화면과 `len(set(bytes)) > 1` 판정이 시각 소비 증거가 될 수
  없음을 발견했다. 이를 폐기하고 gradient/checker/tile-scale 선·원 특징이 있는
  source로 교체했으며, runtime이 tile texture에서 재구성한 결과를 실제 Canvas에
  연결했다. v3에서는 임의 RGB 표준편차·사분면 차이·고유색 개수 gate를 폐기하고,
  같은 view pose의 직접 source Canvas와 runtime-reconstructed Canvas를
  premultiplied 1 LSB로 비교한다. 비균일 표본은 blank capture가 아니라는 사실만
  확인하며 품질 threshold로 쓰지 않는다.
  4K는 3/3 layer가 tile-complete이고 409 GL textures, GPU display 3회를 기록했다.
  8K는 256MB total tile budget에서 1/2 layer만 complete여서 GPU display 1회와
  source fallback 1회를 기록했다. 두 경우 모두 시각 parity, 1-tile dirty,
  저장 무결성은 통과했다.
- 최신 v3 코퍼스에서 측정된 working-set delta는 4K 513,875,968 bytes, 8K
  867,106,816 bytes였고 private-usage delta는 각각 719,589,376 / 1,273,016,320
  bytes였다. 이 값은 한 장비의 관측값이며 release
  threshold가 아니다. 보고서는 `debugCapture/painter/large_canvas_runtime/4k_report.json`과
  `8k_report.json`이다.
- `budget_plan`은 `width*height*4*raster_layers / main-cache-share(0.60)` 공식으로
  현재 문서의 full-coverage 최소값과 fallback 여부를 계산한다. 임의의 “충분한
  MB”를 PASS 상수로 두지 않는다.

R7 완료는 trace, parity, bounded fallback, 실제 자원 측정에 대한 것이다.
8K 2-layer가 기본/256MB budget에서 전부 GPU resident라는 주장은 하지 않으며,
zero-readback widget-native display도 후속 최적화다.

후속 전수검색에서 Undo budget의 알 수 없는 객체를 일괄 64 bytes로 계산하면서
`memory`라고 부른 잔여 추정을 제거했다. v2 accounting은 QImage의 실제
`sizeInBytes`, QPixmap의 raster payload, CPython `getsizeof`와 재귀 소유값을
중복 참조 없이 합산한다. telemetry 명칭은
`owned_logical_history_payload_bytes`이고 `process_memory_claim=false`다. 실제
process working set/private usage는 계속 별도 Windows 계측만 근거로 삼는다.

### R8. 제품 재승인

- 실제 Painter input path로 character/background/material 세 작업 완주
- native DPI, physical tablet, real GPU, crash/soak, external interchange 증거 결합
- 구현과 분리된 QA가 artifact를 재현하고 시각 검토

완료 조건: `app/painter_evidence_contract.py`의 모든 release claim PASS.

2026-08-04 실행 결과 — 증거 집계 완료, 제품 재승인 미통과:

- `app/painter_product_reapproval.py`와
  `tools/qa_painter_product_reapproval.py`가 M8 자동 기준선, native Qt/OpenGL,
  실제 process crash, soak, Photoshop, 4K/8K 보고서를 읽고 artifact hash와
  evidence kind를 보존한 채 release claim을 다시 계산한다. 결과는
  `debugCapture/painter/product_reapproval/report.json`이다.
- 자동 기능 기준선, basic-stroke GPU, retained GPU tile display, 실제 process
  crash/다음 process 복원, Adobe Photoshop 26.11.6 PSD 상호운용은 PASS다.
- native DPR은 1.0이고 physical tablet event가 없다. 첫 실제 7,200초 native
  soak는 scoped acceptance를 통과했지만 반복 3회 envelope는 아직 진행 중이다.
  실제 disk-full 환경 결과도 없고 독립 QA 에이전트는 사람의
  `independent_manual` 검토로 승격하지 않는다.
- 따라서 차단 claim은 `native_high_dpi`, `physical_tablet_input`,
  `disk_full_recovery`, `three_run_two_hour_resource_envelope`,
  `visual_product_review`이고
  `release_ready=false`다. R8은 완료로 표시하지 않는다.

## 5. 실행 순서

R0 → R1/R2 harness → R3 → R4 → R5 → R6 → R7 → R8 순서로 진행한다.

## 2026-08-04 R3 추가 측정 기록

근거 자료를 다음 공식 문서로 보강했다.

- [Windows GetGuiResources](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getguiresources): 프로세스별 GDI/USER 객체 수 측정
- [PROCESS_MEMORY_COUNTERS_EX](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex): working set과 private usage 측정 구조체
- [Windows process memory usage](https://learn.microsoft.com/en-us/windows/win32/psapi/process-memory-usage-information): 프로세스 메모리 계측 API 범위
- [Python zipfile.testzip](https://docs.python.org/3/library/zipfile.html#zipfile.ZipFile.testzip): recovery ZIP 전체 entry CRC 검사
- [Qt QOpenGLContext](https://doc.qt.io/qt-6/qopenglcontext.html): context의 current/thread/lifetime 및 context 소멸 전 GL resource 정리 계약
- [Qt QOpenGLFramebufferObject](https://doc.qt.io/qt-6/qopenglframebufferobject.html): FBO 생성·유효성·소유 context 계약
- [Qt QOpenGLPaintDevice](https://doc.qt.io/qt-6/qopenglpaintdevice.html): 생성 시 current context를 캡처하며 해당 context에서만 유효한 QPainter GL target 계약

구현·실측 결과:

- 실제 child Painter를 autosave 뒤 강제 종료하고 다음 프로세스에서 자동 검색·복원해 전체 RGBA SHA-256 parity를 확인했다.
- 약 12 MB의 비압축성 교체 payload를 쓰는 동안 실제 `.tmp`가 보인 시점에 writer를 종료했다. 기존 recovery ZIP의 SHA-256과 CRC가 유지되어 atomic replace 경계가 확인됐다. 보고서: `debugCapture/painter/crash_recovery/20260804-064534-5893c87b/report.json`.
- 손상·절단 ZIP은 `document.json`, JSON schema, 모든 ZIP entry CRC를 검사한 뒤 복원 목록에서 제외한다.
- 비동기 recovery writer의 permission 등 예외는 더 이상 유실하지 않는다. `painter_action_state().recovery.last_error`에 노출하고 재시도를 허용하며, 이후 성공하면 오류를 해제한다.
- Windows working set/private usage/process handle/GDI/USER 객체와 작업 지연 p50/p95/p99를 실제 프로세스에서 수집하는 bounded cyclic soak를 추가했다.
- 동일 조건 15초 교정 측정 3회를 `debugCapture/painter/soak/calibration-baseline-20260804.json`에 집계했다. 지연 p95 중앙값은 약 104.74 ms, working-set delta 중앙값은 6,762,496 bytes, GDI delta는 세 번 모두 0이었다.
- 15초의 초기화 구간을 시간당 slope로 외삽하면 값이 과장되므로 이 수치는 합격 기준으로 사용하지 않는다. 집계기는 관측 min/max/median/MAD만 기록하고 `release_claim_passed=false`를 강제한다.

R3 상태: 실제 crash/다음 프로세스 복원, 교체 중단 원자성, 손상 ZIP 격리, writer 오류 표면화, 반복 계측 harness까지 완료. 실제 disk-full 환경과 반복 장시간 측정에 근거한 비교 envelope는 미완료다.

2026-08-04 후속 실행:

- `tools/qa_painter_soak.py --duration-seconds 7200 --release-evidence`를 별도
  native Windows Qt 프로세스로 시작했다. 완료 전에는 장시간 안정성 PASS로
  집계하지 않는다.
- `app/painter_soak_acceptance.py`는 원시 시간축, 1,000개 이상 표본, 실제 Windows
  working set/private usage/process handle/GDI/USER 계측, 작업 주기와 오류 유무를
  검사한다. 통과해도 `single_native_two_hour_survival`만 증명하며 leak-free,
  보편 성능, latency threshold는 모두 주장하지 않는다. 별도 감시 프로세스가
  원시 보고서 생성 후 승인기와 R8 재집계를 자동 실행한다.
- 단일 2시간 실행을 포괄적인 “장시간 안정성”으로 부르지 않는다.
  `three_run_two_hour_resource_envelope`는 서로 다른 3회 × 각 7,200초 원본이 모두
  scoped acceptance를 통과하고 자원 delta/slope와 latency p50/p95/p99의
  min/max/median/MAD를 만들 때만 통과한다. leak-free와 보편 성능 claim은 false다.
- `tools/run_painter_long_soak_series.py`가 현재 첫 실행 보고서를 기다린 뒤 추가
  2회를 순차 실행하고 series acceptance와 R8 재집계를 자동 수행한다.
- 첫 7,200초 원본 `20260804-085456-a033e83a`는 62,114회 작업과 517회 bounded
  cycle을 오류 없이 완료했다. 그러나 15분 구간 중앙값이 working set
  356,388,864→610,451,456 bytes, private usage
  1,043,558,400→1,354,539,008 bytes로 계속 증가했다. 따라서 이 실행의 PASS는
  오직 “2시간 생존”이며 안정화 또는 leak-free 증거가 아니다.
- 두 번째 7,200초 원본 `20260804-105458-6312b969`는 132,058회 작업과 1,100회
  bounded cycle을 오류 없이 완료했고 raw-summary 재계산도 통과했다. working set
  delta는 -21,184,512 bytes였지만 private usage 끝값은 시작보다 256,118,784
  bytes 높았다. 중간에 큰 회수 구간이 있어 전체 private 선형 slope는 음수였으므로
  첫 실행의 단조 증가를 그대로 재현했다고 판정하지 않는다. 이 역시 단일 2시간
  생존 증거일 뿐이며 세 번째 원본 전에는 retention 방향 일관성을 결정하지 않는다.
- 세 번째 기존-source 실행 `20260804-125505-f3b07525`는 12:55:05에 자동
  시작됐다. 이 실행이 끝나기 전에는 core Painter runtime을 수정하지 않는다.
- 세 실행 중 하나라도 후반 slope가 양수이면서 마지막 세 quarter median이 연속
  증가하면 다른 실행의 안정화가 이를 다수결로 지우지 못한다. 관측 envelope 안에
  들어왔다는 이유로 승인하지 않는다. cycle마다 stroke를 비우는 bounded workload에서 retained
  memory가 증가한 원인을 Python/Qt raster cache, recovery payload, allocator
  high-water로 분해 계측하고, 수정 뒤 동일 workload를 다시 실행하는 R3B를
  선행한다. 임의 MB/hour 허용치를 새로 만들어 통과시키지 않는다.
- 정적 추적에서 basic stroke의 signature가 바뀔 때마다
  `render_canvas_strokes_opengl_qimage`가 새 `QOffscreenSurface`, `QOpenGLContext`,
  FBO를 만들고 파괴하는 경로를 확인했다. 이는 현재의 우선 조사 가설이지 아직
  원인 확정이 아니다. 기존 3회 측정 완료 후 context/FBO 생성 횟수와 Python/Qt
  raster 보유량을 함께 계측해 상관을 확인하고, 공식 Qt lifetime 계약대로
  session-local current context와 동일 크기 FBO를 재사용한 뒤 같은 cyclic
  workload에서 후반 retained growth가 사라지는지 검증한다.
- Microsoft의 Win32 오류 계약에서 `ERROR_DISK_FULL`은 112이고, NTFS hard
  quota는 한도를 넘은 추가 공간 할당을 거부한다. 이를 근거로
  `tools/qa_painter_disk_full.py`는 `debugCapture/painter/disk_full` 아래의 고유
  96MB VHD만 선택·NTFS 포맷하고 실제 112/errno 28을 요구하도록 구현했다.
  기존 snapshot 보존, action-state 오류 노출, 공간 해제 후 retry까지 모두
  통과해야 한다. 오류 노출 판정은 영어 `disk full` 문자열에 의존하지 않고
  `last_error_detail.winerror==112` 또는 `errno==28`을 사용한다. 현재 호스트는
  DiskPart 시작에 UAC 상승을 요구해 WinError 740로
  setup이 차단되었으며 물리 disk/partition은 변경되지 않았다. 예외 주입 결과로
  대체하거나 PASS로 올리지 않는다.

## 2026-08-04 R4 착수 기록

- `app/painter_layer_masks.py`에 문서 크기 `QImage.Format_Alpha8` 마스크를 추가했다. 값은 0/255 이진 폴리곤으로 축약하지 않고 0–255 부분 투명도를 유지한다.
- polygon rasterization, 선형 gradient, 원형 brush hide/reveal, RGBA `DestinationIn` 적용을 픽셀 단위 테스트로 고정했다.
- 공용 layer compositor는 layer-id별 래스터 마스크가 전달되면 이를 우선 적용한다. 기존 point polygon은 v2 문서 호환을 위한 fallback일 뿐 새 마스크의 기준 모델이 아니다.
- 현재 8개 mask/compositor 집중 테스트가 통과한다.

R4 상태: 구현·자동 회귀 완료. `.tspaint` v3가 레이어별 Alpha8 mask PNG를 저장하며 v1/v2를 읽는다. 선택·경로·채널·레이어 알파 생성, 0–255 brush/gradient 편집, enable, link/unlink, apply/delete, Undo, clipboard, recovery, image/canvas resize·crop·flip·free transform이 같은 래스터 자산을 사용한다. 1/2/3점 perspective ruler는 캔버스 밖 소실점과 별도 snap 상태를 저장하고 실제 mouse/tablet 공용 stroke sample을 선택 축에 투영한다. 최신 전체 Painting 자동 기준선 376개와 architecture/debug boundary 5개가 통과했다. 이는 자동 기능 기준선이며 수동 제품 승인 증거로 승격하지 않는다.

후속 전수검색에서 Magic Select tolerance가 임의의 0–100 UI 값을 2.55배해
0–255로 되돌리는 축약임을 발견했다. Photoshop 공식 계약은 RGB tolerance
0(좁음)–255(넓음)이므로 UI, Action schema, mask 입력을 모두 0–255 직접값으로
통일했다. Tiger의 현재 max-channel RGBA 비교를 Photoshop 내부 알고리즘 parity로
주장하지 않는다.

같은 검색에서 `paint.selection.modify`는 schema로 4096px까지 받으면서 Pillow의
단일 Min/MaxFilter 제한 때문에 실제 kernel을 99px, 즉 radius 49px로 조용히
잘랐다. square morphology의 반경은 반복 합성 가능하므로 최대 49px 단위의
필터를 남은 요청 반경만큼 적용하도록 교체했다. 120px 단일점 expand의 실제
241x241 결과를 회귀로 고정했다.

Adjustment의 Hue도 -100…100 값을 내부에서 ±180도로 바꾸던 숨은 축약이었다.
Hue 입력을 공식 숫자 의미인 -180…180 degrees로 변경하고 HSV 변환도 degree를
직접 사용한다. Saturation/Lightness만 -100…100 relative percent다. 전체 adjustment
parameter의 범위·단위·렌더 모델을 `paint.state.adjustment_preview.parameter_contracts`
에 노출했다. Color Balance 등은 `tiger_*`/`pillow_*` 로컬 모델이며 Photoshop
algorithm parity를 주장하지 않는다.

OKLCH harmony의 표준 각도 관계와 별개로 shade/tint lightness·chroma 가중치는
사용자 선호를 측정한 값이 아닌 Tiger authored preset이다. `paint.state.palette`는
이를 `tiger_authored_oklch_suggestions_v1`,
`tonal_weight_source=authored_preset_not_measured_preference`,
`harmony_quality_claim=false`로 명시한다. 추천색의 미적 우수성을 검증된 사실로
표현하지 않는다.
실물 장치나 외부 상용 앱이 없는 경우 해당 마일스톤을 억지로 PASS하지 않고,
자동화 가능한 준비 작업을 마친 뒤 evidence 상태를 `blocked_external`로 남긴다.

## 2026-08-04 줌·팬 계약 분리

- 기존 `canvas_view_or_document_product_domain`은 줌, 팬, 색상 패널 배치를
  한 근거로 묶어 승인할 수 없으므로 제거했다.
- `app/painter_zoom.py`가 25..800%, 기본 100%, 파생 배율 0.25..8.0을
  단일 Tiger 제품 계약으로 정의한다. 외부 제품의 표준값이라고 주장하지 않는다.
- 0%는 기본값 100%로 치환하지 않고 하한 25%로 제한한다. bool·분수·문자열
  percent와 bool·문자열·None·비유한 저장 배율은 거부한다.
- `.tspaint`의 저장 배율은 `_restore_state` 전에 검증하므로 손상된 값이 열린
  문서의 캔버스, 레이어, 시간, 출력 설정을 부분 변경하지 못한다.
- 팬 경계 두 행은 대칭적인 반-초과영역이라는 수학 계약으로, 색상 패널 높이
  두 행은 문서·작품 픽셀과 무관한 Painting 창 레이아웃 범위로 각각 분리했다.
- 직접 helper, 실제 Canvas/Dialog, Canvas Pose, 문서 실패 원자성, 양축 팬 경계
  테스트를 추가했으며 관련 회귀 22개가 통과했다. 정확 행 계약은 numeric ledger의
  `painter_zoom_literal_domain_contract`, `canvas_pan_bounds_geometry_contract`,
  `painting_color_panel_layout_scope_contract`에 저장한다.

## 2026-08-04 고정 epsilon 제거

- `computational_degeneracy_epsilon` 후보 14개를 관행으로 승인하지 않고 모두
  함수별로 조사했다. 값들은 3D ray/clip, 벡터 정규화, pressure control 중복,
  tilt 방향, perspective 방향, pixel transform scale, action point 중복, 선분,
  색상 삼각형, crop/canvas rotation의 퇴화 또는 동일성 판정이었다.
- 입력 단위나 외부 포맷이 해당 고정값을 정의하지 않으므로 1e-4..1e-9를 임의
  허용오차로 유지하지 않았다. 실제 0과 정확히 같은 값만 퇴화·중복·동일 상태로
  처리한다.
- 1e-12 벡터·scale, 1e-10 간격 pressure controls, 1e-8 near-plane 교차,
  1e-3 선분, 1e-9도 회전을 보존하는 경계 테스트와 관련 회귀 103개가 통과했다.
  따라서 pending epsilon ledger 항목은 승인으로 바꾸지 않고 제거했다.

- 독립 QA가 pressure controls의 목록 보존 뒤 소비 단계에 남은 `max(1e-9, Δx)`와
  canvas geometry의 회전 `>1e-6` 분기를 추가 발견했다. 전자는 정확한 양수 Δx를
  사용하고 후자는 모든 nonzero 회전을 동일 렌더 경로로 보낸다. 1e-10 간격 곡선의
  midpoint=0.5/end=0.8과 tiny 회전의 background/stroke 경로 일치를 추가 검증했다.

## 2026-08-04 Grid 계약 분리

- 4..512 px, 기본 64 px를 `app/painter_grid.py`의 단일 Tiger view-control
  계약으로 옮겼다. 0은 64로 치환하지 않고 4로 clamp하며 잘못된 타입은 거부한다.
- display, snap, Canvas/Dialog setter, 저장, 복원이 공용 normalizer를 사용한다.
  손상된 저장 grid 값은 문서 상태 변경 전에 실패한다.
- brush preset의 style combo는 row 0 fallback을 제거하고 semantic data와 명명된
  `round` fallback을 사용한다. 관련 grid/combo/document/new-canvas 회귀 39개가
  통과했다.
- 이 배치 뒤 UI Design과 장시간 soak를 제외한 Painting 전용 전체 회귀는
  최신 Action transform/resize 배치까지 468개 통과, architecture/debug-capture
  boundary는 5개 통과했다. 경고 1개는
  손상 TIFF 검증 fixture를 Pillow가 보고한 의도된 경고다. 독립 QA 재검토는
  P0/P1/P2 없이 PASS했다.

## 2026-08-04 Brush/Material/Grid 혼합 계약 해체

- brush detail 5개와 width 범위를 `app/painter_brush_domains.py`로 분리했다.
  detail은 strict integer, flip은 실제 bool, width는 finite real 1..5000 px이며
  저장 width/detail 오류는 문서 상태 변경 전에 실패한다. Canvas, dialog commit,
  payload, document restore가 같은 normalizer를 사용한다.
- PBR preview는 source width 0을 1로 바꾸거나 축소 stroke를 0.25 px로 올리지
  않는다. 보고서 dimension은 양수 정수여야 하고 폭은 정확한 width×scale이다.
- custom brush delete/move는 strict catalog helper를 사용한다. move direction은
  -1/+1만 허용하며 empty/out-of-range/noninteger 상태를 테스트한다.
- 이전 `shared_brush_material_or_grid_contract`의 서로 다른 15행은 grid, semantic
  combo, brush input, PBR preview, catalog index 계약으로 분해되어 잔여 후보가 0이
  되었고 혼합 pending 항목은 제거했다.

## 2026-08-04 Action schema 분해 1: PNG export 입력

- `paint.document.export_png`와 `paint.export_png`의 width/height는 `(0,0)`만
  현재 크기 sentinel로 허용한다. 그 외에는 두 값 모두 양수 strict integer이며
  현재 canvas capacity 이하여야 한다.
- 한쪽만 0인 요청, 음수, bool, fraction, text, capacity 초과는 다른 크기로
  대체하지 않고 실패한다. `time_ms`도 explicit/owner/player 모든 경로에서 strict
  nonnegative integer를 사용해 잘못된 값이 0ms가 되지 않는다.
- schema 9행, runtime scanner 2행, AST sentinel 1행을 각각 정확 계약으로
  분리했으며 helper와 두 adapter entry의 실패 순서를 테스트했다.

## 2026-08-04 Action schema 분해 2: Brush 및 View 입력

- `paint.brush.set`은 전체 payload를 dialog 접근 전에 검증한다. width,
  opacity, hardness, spacing, angle, roundness, flip bool, dynamics object,
  preset/style 문자열과 canonical style enum이 모두 통과한 뒤에만 상태를
  변경한다. 별칭이나 뒤쪽 필드 오류 때문에 앞쪽 상태만 바뀌는 부분 commit은
  허용하지 않는다.
- `paint.view.zoom`과 `paint.view.grid`는 각각 기존 공용 Zoom 25..800%와 Grid
  4..512px 계약을 사용한다. 0을 기본 zoom으로 치환하거나 bool/float/text를
  정수로 바꾸지 않으며 visible/snap은 실제 bool 또는 생략만 허용한다.
- PNG export의 `(0,0)` sentinel은 schema `oneOf`에도 omission/zero pair/positive
  pair로 표현했다. runtime 크기 검증은 owner 조회와 기본 출력 경로 생성보다
  먼저 실행되어 잘못된 빈-path 요청이 디렉터리 생성·이름 변경을 일으키지 않는다.
- 감사 계약은 brush 12행, view 4행, export 9행, runtime 2행으로 분리되며 broad
  Action 후보는 172행이다. 각 범위는 Tiger Action 호환성 정책 또는 구조적
  실패 계약이며 외부 제품의 최적값이나 미적 품질 주장이 아니다.

## 2026-08-04 Action schema 분해 3: 압력 보정 입력

- `paint.brush.calibration.set`은 비어 있지 않은 device ID, 유한한 normalized
  minimum/maximum, `minimum < maximum`, 정확히 두 숫자로 된 curve point를
  dialog 접근 전에 검증한다.
- curve의 x는 엄격히 증가해야 하며 모든 x/y는 `[0,1]`이다. malformed row,
  bool, NaN/Inf, 범위 이탈, 중복·역순 x를 clamp·정렬·skip·overwrite하지 않고
  실패시킨다.
- 이는 단일값 piecewise-linear graph와 normalized pressure channel의 구조적
  계약이다. 선호 압력감이나 특정 태블릿 제품 parity를 주장하지 않는다.
- schema 8행, runtime 1행, AST 구조 3행을 정확 계약으로 분리했고 broad Action
  후보는 164행으로 감소했다.

## 2026-08-04 Action schema 분해 4: Large Canvas 자원 설정

- `paint.performance.configure`는 기존 `LARGE_CANVAS_RESOURCE_POLICY_CONTRACT`의
  tile size 32..1024px, tile budget 1..4096MiB, Undo budget 1..8192MiB를
  공용 strict-integer validator로 사용한다.
- Action adapter는 owner 조회 전에, `PaintDialog.configure_painter_large_canvas`는
  기존 runtime을 닫기 전에 검증한다. 잘못된 요청이 활성 cache/runtime을 먼저
  파괴한 뒤 생성자 clamp 값으로 성공하는 경로를 제거했다.
- bool, float, text, 범위 이탈은 실패하며 기존 runtime의 `close()`가 호출되지
  않는 회귀 테스트를 추가했다. 이는 Tiger 자원 설정 정책이며 보편적 메모리
  안전성이나 성능 보장이 아니다.
- schema 6행을 별도 계약으로 분리해 broad Action 후보는 158행으로 감소했다.

## 2026-08-04 Action schema 분해 5: 새 문서 크기

- `paint.document.new`의 두 축은 Tiger가 선언한 새 캔버스 control 최소 64px부터
  현재 runtime capacity 16384px까지의 strict integer다. 별도
  `PAINTER_NEW_CANVAS_DIMENSION_CONTRACT`로 Action schema, adapter, 문서 교체
  기본값과 Painting 크기 control이 같은 상수를 사용한다.
- adapter는 owner 조회 전에 dimensions와 background 문자열을 검증한다.
  bool/float/text를 `int()`/`str()`로 바꾸지 않으며 문서 교체 함수도 Undo 생성
  전에 독립 검증한다.
- background는 선언된 transparent 토큰 또는 유효한 QColor 문자열만 허용한다.
  invalid/non-string 배경은 owner와 Undo 전에 실패하며 부분 문서 상태를 남기지
  않는 회귀 테스트를 추가했다.
- 64px는 Tiger product-control 범위이며 파일 포맷 한계나 작품 품질 임계값이
  아니다. schema 4행 분리 후 broad Action 후보는 154행이다.

## 2026-08-04 Action schema 분해 6: Selection geometry

- rectangle, ellipse, lasso Action 좌표는 유한한 real `[0,1]`이며 bool과 coercible
  text를 거부한다. lasso는 최소 3개의 정확한 2-number 배열이고 aspect, combine
  mode, polygonal도 schema와 같은 canonical enum/type만 허용한다.
- 전체 payload를 owner 조회 전에 검증하므로 dialog path normalizer가 malformed
  Action point를 skip/clamp/replace하거나 부분 Undo/selection 상태를 남기지 않는다.
- normalized 공용 scanner 1행, lasso runtime 1행, AST 구조 3행, schema 21행을
  정확 계약으로 분리했다. 이는 2D geometry/cardinality 불변식이지 선호 selection
  shape가 아니다.
- broad Action 후보는 154행에서 133행으로 감소했다.

## 2026-08-04 Action schema 분해 7: Magic Select 입력

- `paint.selection.select_by_color`는 normalized sample x/y, strict integer
  tolerance, actual bool contiguous, canonical preview/commit/cancel phase를 owner
  조회 전에 검증한다.
- tolerance는 Adobe Magic Wand 공식 입력 범위 0..255를 schema, adapter, Painting
  spin control, preview, raster mask가 같은 상수로 사용한다. 이전처럼 반복 literal이
  서로 다른 계약으로 drift하지 않는다.
- Tiger의 max-channel RGBA 비교 metric은 local implementation이며 Adobe의 비공개
  pixel-selection algorithm parity를 주장하지 않는다.
- geometry schema 4행과 tolerance schema 2행을 분리해 broad Action 후보는
  133행에서 127행으로 감소했다.

## 2026-08-05 Action schema 분해 8: Zoom Area

- `paint.view.zoom_area`의 origin은 normalized `[0,1]`, width/height는 `(0,1]`이며
  `x+width`, `y+height`가 unit canvas 안에 있어야 한다.
- 근거 없던 `0.001` 최소값을 제거했다. `1e-12`와 `1e-320` 양수 extent도 유효하다.
  극소 extent는 역수를 먼저 계산하지 않는 대수적 분기로 800%에 안전하게 포화된다.
  임의 epsilon이나 최소 drag 크기를 품질 계약으로 만들지 않는다.
- bool, NaN/Inf, 음수, 0, unit 초과, right/bottom overflow는 owner 조회 전에
  실패한다.
- 감사기가 `exclusiveMinimum/exclusiveMaximum`을 누락하던 결함도 수정했다.
  schema 8행, runtime 2행, AST 1행을 분리해 broad Action 후보는 119행이다.

## 2026-08-05 Action schema 분해 9: Layer Opacity / Selection Modify

- `paint.layer.set_opacity`의 `int(opacity or 0)`와 dialog clamp를 제거했다. 이제
  기존 Painting layer model의 정수 0..100%만 owner/layer 선택 전에 허용한다.
- Selection Modify의 공통 `0.1..4096`은 근거 없는 범위였다. Pillow 공식 API 구조에
  맞춰 feather는 유한 양수 실수, expand/contract/border는 1px 이상 정수로 분리했다.
- 상한은 새 감각값이 아니라 이미 선언된 현재 문서 용량 16384px를 재사용한다.
  schema, adapter, dialog, 직접 mask 함수가 같은 검증을 수행한다.
- 설치된 Pillow probe에서 초대형 Gaussian radius는 native backend 실패가 확인되어
  무제한 입력을 전달하지 않는다. focused 회귀는 28개 통과했다.
- opacity schema 2행/AST 2행, selection-modify schema 4행/runtime AST 2행을
  분리해 broad Action 후보는 115행으로 줄었다.

## 2026-08-05 Action schema 분해 10: Selection Transform

- 기존 adapter는 모든 수치를 `float`, flip을 `bool`, phase/target을 문자열로 조용히
  변환한 뒤 owner를 조회했다. 이제 전체 payload를 먼저 검증한다.
- translation/rotation에는 임의 크기 상한을 두지 않고 유한 실수만 요구한다. scale은
  정확히 0만 퇴화로 거부하며 음수 scale은 허용한다. pivot은 normalized `[0,1]`이다.
- skew는 실제 구현의 `tan(angle)`이 특이해지는 ±90도를 제외한 principal interval만
  허용한다. epsilon이나 근사 임계값은 도입하지 않았다.
- direct preview도 동일 validator를 먼저 거치므로 잘못된 입력이 기존 preview를
  cancel하거나 변형 상태를 부분 변경할 수 없다.
- 중복 상수/validator를 제거한 뒤 schema 8행, AST/runtime 3행으로 고정했고,
  당시 broad Action 후보는 111행이었다.

## 2026-08-05 Action schema 분해 11: Image / Canvas Resize

- 두 resize Action의 `int(width/height)` 절삭을 제거하고 New Canvas와 같은 strict
  integer 64..16384px 제품 용량 계약을 재사용한다.
- Canvas background는 transparent token 또는 유효 QColor 문자열인지 owner 조회 전에
  검증한다. direct dialog 경로도 size 비교와 Undo보다 background를 먼저 검증한다.
- bool, 실수, 문자열 숫자, None, 64 미만, 16384 초과, 잘못된 색은 문서와 history를
  변경하지 않는다.
- schema 8행을 분리해 broad Action 후보는 103행이다.
- 이 checkpoint의 UI Design/soak 제외 Painting 전체 회귀는 468개 통과했고,
  architecture/debug-capture boundary는 5개 통과했다. 독립 QA는 P0/P1/P2 없음,
  네 ledger stale 배열 0, unreviewed defect 0으로 승인했다.

## 2026-08-05 Action schema 분해 12: Document Export

- `paint.document.export`의 전체 payload를 owner 조회와 transactional destination 처리
  전에 검증한다. 빈/non-string path, format alias, bool bit depth, truthy boolean,
  실수 quality/intent, non-string ICC path를 허용하지 않는다.
- format과 8/16 bit depth는 정확한 enum, quality는 정수 1..100, ICC rendering intent는
  정수 0..3이다. 이 범위는 Tiger export control 계약이며 보편적 codec 품질 주장이 아니다.
- format은 필수이며 schema/runtime 모두 16-bit를 PNG/TIFF에만 허용한다. JPEG/WebP/PSD
  16-bit 조합은 owner와 staging 파일 생성 전에 실패한다.
- 공백만 있는 path는 거부하지만 유효한 원본 path 문자열을 trim/rewrite하지 않는다.
- schema 4행, AST 6행을 분리해 broad Action 후보는 99행이다. focused export 회귀는
  62개 통과했다.

## 2026-08-05 Action schema 분해 13: Perspective / Symmetry Guides

- horizon과 symmetry position에 있던 `0.02..0.98`은 근거 없는 화면 가장자리 여백이었다.
  normalized 좌표 구조대로 정확한 `[0,1]`을 허용하고 endpoint silent clamp를 제거했다.
- perspective vanishing point는 화면 밖 소실점도 필요하므로 임의 범위를 만들지 않고
  유한 실수만 요구한다. enabled/snap은 실제 bool, mode는 정수 1..3이다.
- symmetry axis는 canonical vertical/horizontal만 허용한다. Action, dialog, direct canvas가
  같은 validator를 사용한다.
- schema 6행, AST 2행을 분리해 broad Action 후보는 93행이다. focused 회귀는 24개
  통과했다.

## 2026-08-05 Action schema 분해 14: Wet Canvas

- `paint.wet_canvas.settings.set`은 실제 bool enabled, `[0,1]`의 유한 실수
  mixing/diffusion/pickup, 기존 저장 계약인 1..86400초 drying time만 허용한다.
  layer_id만 전달한 빈 변경 요청은 더 이상 성공 경로로 들어가지 않는다.
- `paint.wet_canvas.advance`는 0초가 상태를 바꿀 수 없으므로 양의 유한 실수만
  허용하며 저장 상태의 86400초 상한을 공유한다. 내부 순수 상태 helper만 정확한
  0초를 허용하고 음수, bool, 문자열, NaN/Inf, 상한 초과는 거부한다.
- Action adapter는 전체 payload와 layer_id를 owner 조회 전에 검증한다. direct dialog도
  동일 validator를 layer 조회와 Undo 전에 호출하므로 잘못된 값이 다른 레이어 선택,
  silent clamp, 부분 history를 만들 수 없다. 문서 load용 forgiving normalization은
  외부 변경 계약과 의도적으로 분리했다.
- schema 10행, runtime scanner 2행, AST 1행을 정확 계약으로 분리했다. broad Action
  후보는 82행이며 focused Wet Canvas/Action 회귀는 28개 통과했다. 재감사 결과 numeric
  ledger stale 0, unreviewed defect 0이다. 이 범위는 Tiger 저장 상태와 실패 순서 계약이며
  실제 안료 혼합이나 물리적 건조 시간 parity를 주장하지 않는다.
- QA 수정까지 반영한 checkpoint에서 UI Design/soak 제외 Painting 전체 회귀 473개와
  architecture/debug-capture guard 5개가 통과했다. 별도 읽기 전용 QA는 P0/P1/P2 없음,
  네 ledger stale 0, source inventory 일치, unreviewed defect 0으로 최종 승인했다.

## 2026-08-05 Action schema 분해 15: Material Preview Light

- `paint.material.preview.set`의 기존 Tiger inspection-light 범위인 azimuth
  -180..180도와 elevation 5..85도를 이름 붙인 공용 상수로 고정했다. 이는 기존 schema와
  renderer가 이미 사용하던 제품 control이며 물리 조명 보정값이나 타 제품 parity가 아니다.
- 빈 요청과 explicit null을 거부하고 enabled는 실제 bool, 두 각도는 범위 안의 유한 실수만
  허용한다. Action은 owner 조회 전에, direct dialog는 preview state/cache 변경 전에 전체
  payload를 검증하므로 더 이상 silent clamp나 빈 성공을 만들지 않는다.
- 저장 복원과 renderer는 별도 forgiving normalizer를 공유한다. 유효한 0도는 보존하고,
  유한 범위 초과만 같은 endpoint로 clamp하며 bool/non-real/NaN/Inf는 이름 붙인 -38/48도
  Tiger 기본값으로 복구한다.
- schema 4행과 endpoint/default AST 상수 6행을 정확 계약으로 분리해 broad Action 후보는
  78행이다. focused Action/Material Paint/Document 회귀는 44개 통과했다.
- 이 checkpoint의 UI Design/soak 제외 Painting 전체 회귀는 474개, architecture/
  debug-capture guard는 5개 통과했다. 별도 읽기 전용 QA는 P0/P1/P2 없음, UI Design
  비변경, 네 ledger stale 0, unreviewed defect 0으로 승인했다.

## 2026-08-05 Action schema 분해 16: Reference Sample / Palette Request

- sample x/y는 유한 normalized `[0,1]`이고 QImage의 `0..width-1` / `0..height-1`
  pixel index로 변환한다. Qt QImage의 rect/valid/pixelColor 공식 문서를 근거로 사용했다.
- 생략 좌표는 normalized 중심 0.5다. 결과 좌표를 근거 없이 소수 5자리로 반올림하던
  동작은 제거해 검증된 요청값을 그대로 반환한다.
- palette max_colors는 기존 atomic Action resource 계약의 정수 1..12를 재사용한다.
  reference_id는 문자열, apply는 실제 bool만 허용하며 bool-as-int, fraction, text,
  NaN/Inf, 범위 초과는 owner와 이미지 load 전에 실패한다.
- 요청한 reference가 없거나 sample/extract가 실패하면 selected reference를 바꾸지 않는다.
  성공한 뒤에만 명시 target을 선택 상태로 반영한다.
- sample 또는 palette foreground 적용 중 예외가 발생하면 foreground/previous color,
  recent colors, document palette, dirty 상태와 canvas pen을 복구한다. 완전 투명 이미지의
  빈 palette는 `apply=true`여도 `applied_to_recent_colors=false`이며 recent colors를
  변경하지 않는다.
- schema 6행, palette AST 1행, sample pixel-index scanner 2행, center AST 1행을 정확
  계약으로 분리해 broad Action 후보는 72행이다. 서로 다른 끝점 픽셀, Action 좌표 원값,
  missing target, sample/extract 이미지 load 실패, sample/palette 적용 예외 rollback,
  빈 palette를 포함한 focused 회귀는 28개 통과했다. 별도 읽기 전용 QA는 P0/P1/P2 없음,
  네 ledger stale 0, unreviewed defect 0으로 승인했다.
  이 계약은 96px downsample과 24단계 palette quantization 품질을 승인하지 않으며 해당
  알고리즘은 별도 측정 마일스톤에 남긴다.

## 2026-08-05 Action schema 분해 17: 3D Blockout Projection Viewport

- 11개 `paint.3d_blockout.*` endpoint의 preview width/height를 하나의 이름 붙인
  Action 응답 viewport 계약으로 통합했다. 범위는 기존 64..8192, 기본값은 640x360이며
  외부 3D 제품 규격이나 화질 기준으로 주장하지 않는다.
- 모든 endpoint와 내부 payload 경계가 같은 strict integer validator를 사용한다. bool,
  fraction, text, null, 범위 밖 값은 owner 조회, scene 저장, Undo 등록, bake 전에 실패한다.
  기존 `int(value or 640)` 식의 직접 호출 coercion/대체는 제거했다.
- six-primitive scene을 각 viewport에서 25회 실제 측정했다. 64x64, 640x360,
  8192x8192 모두 145 faces, 515 edges, 685 floor tiles로 동일했다.
  `tools/qa_painter_blockout_projection_viewport.py`가 timestamp, Python/platform/
  processor, scene digest, raw sample, nearest-rank p95를 포함한 fail-closed report를
  `debugCapture/painter/blockout_projection_viewport/report.json`에 기록한다. 이 Action은 viewport
  좌표만 직렬화하고 동일 크기 raster를 할당하지 않으므로 측정도 투영 응답 비용만
  증명하며 raster memory나 작품 품질은 증명하지 않는다.
- 네 named literal의 정확 계약은 4행/
  `56580811c349f21238007beb8fffe7557a602965170eecbc6b874f6f0fd0c78d`다.
  공용 schema object로 중복 숫자 결정을 제거해 broad Action 후보는 72행에서
  36행/`73b6d79928f93143c97d940661fcde8d37360b2e368f665e8849429b0d52ae7f`로
  줄었다. focused Action/Input/Blockout 회귀는 43개 통과했고 네 ledger stale 0,
  unreviewed defect 0이다. 별도 읽기 전용 QA는 일반 실행과 `python -O` 실행을
  재검증해 P0/P1/P2 없음으로 승인했다.
- primitive scale/opacity, camera distance/FOV, light angle, preset, renderer projection
  수치는 이 checkpoint가 승인하지 않으며 이어지는 별도 Blockout 감사 단위다.

## 2026-08-05 Action schema 분해 18: 3D Blockout Camera Finite State

- 실제 재현에서 `NaN` yaw와 무한 distance가 scene/JSON에 남고, `NaN` FOV가 근거 없이
  90도로 바뀌며, 무한 target은 투영 중 예외를 발생시키는 것을 확인했다.
- Action과 직접 update는 actual real/not-bool/finite 값을 요구한다. 실제 Painter camera
  control 범위인 yaw -180..180, pitch -85..85, distance 0.25..30, target 각 축
  -5..5, FOV 15..90을 schema/restore/Action/QSpinBox/wheel/WASD/projection이 공유한다.
  empty/preview-only/unknown/null/coercion/
  non-finite/out-of-range 요청과 canonical+alias 중복을 owner와 scene mutation 전에
  거부한다. schema도 일곱 camera field 중 하나를 요구한다.
- 저장 scene 복원은 별도 forgiving 경계다. 잘못된 scalar/vector 구성요소는 이름 붙인
  유한 Tiger 기본값 yaw 35, pitch -18, distance 8.5, target `[0,0,0.8]`, FOV 42로
  복구하고 유한 overflow는 해당 control endpoint로 clamp한다. valid zero와 정확
  endpoint는 보존하며 `json.dumps(..., allow_nan=False)` 회귀를 통과한다.
- projection/QSpinBox/wheel의 중복 endpoint literal을 제거하고 WASD endpoint nudge를
  clamp했다. `1e308` restore/projection, Action rejection/state preservation, endpoint
  `allow_nan=False`, UI key/wheel 경계를 회귀한다.
  schema 14행/`03b33149ee4148c8364a5ed4860d3147c662989661ff05279484ade635825554`,
  input 1행/`1b61482d7910aa4c0fee09f5e4ca9ba6a4d0a38d56515f570a02f026c175c4c5`,
  named literal 15행/`29390be4a8a2b77c5caa858a21bad528afcb1391da4e5b7efe3684c9d0b800e2`,
  structural input literal 1행/`5b3b309070e56eb56eb2c83aadee782189cd07a21cbfb3bab9199cc1da92795b`다.
  residual Blockout preview는 22행/`35864ace4dbb88c99c68dcac32db9792d1801d921b1728b25016282ddd7f4e2a`,
  broad Action 후보는 33행/`2aed11af3e110c06b3d8e898a73c0f8a3e6e8c30c464793a1f0850281263f4b2`다.
  focused 회귀는 56개, viewport producer는 pass, 네 ledger stale 0, defect 0이다.
- 이 checkpoint는 기존 Tiger inspection-camera 상태를 유한하게 만드는 계약이며 physical
  lens, 최적 composition, 외부 3D 제품 parity를 주장하지 않는다. primitive/light/preset
  품질 정책은 아직 승인하지 않았다.

## 2026-08-05 Action schema 분해 19: 3D Blockout Primitive / Light / Preset

- 실제 코드와 Action 재현에서 primitive 위치·회전과 duplicate offset이 무제한 실수였고,
  bool/NaN/Inf가 숫자로 통과했으며, 잘못된 kind/color/preset은 box/default perspective로
  조용히 바뀌었다. 저장 scene의 primitive/grid/light에도 비유한 값이 들어가 projection과
  JSON까지 전달될 수 있었다.
- 기준은 추정한 외부 제품 수치가 아니라 현재 Painting 패널의 실제 QSpinBox다. position
  -5..5, rotation -180..180도, scale 0.1..8, light yaw -180..180도, pitch 5..85도를
  이름 붙인 상수로 통합했고 기존 opacity 0.05..1과 `#RRGGBB`, 화면에 표시된 six primitive,
  four camera preset을 명시 계약으로 고정했다.
- Action/direct mutation은 unknown/empty update, bool-as-number, non-real/non-finite,
  control 밖 transform/light, 잘못된 color/kind/preset을 owner/Undo/scene mutation 전에
  거부한다. duplicate offset은 유한해야 하며 결과 위치가 실제 transform domain 안이어야
  한다. 저장 복원은 별도 forgiving 경계로 malformed/non-finite를 유한 기본값으로 바꾸고
  finite overflow를 같은 UI endpoint로 clamp한다.
- 공개 Action invalid 요청의 scene 상태 보존, 정확 endpoint Action 결과와 손상 scene/
  projection의 `allow_nan=False`, UI와 schema endpoint 일치를 회귀한다. 최초 focused
  Action/Input/Blockout/Document 회귀는 58개 통과했다.
- scene schema는 4행/`6dd13940a084284a152f0943c43fdd5bdd6e5648c1a3d4464d2a4de8250e4f0f`,
  named primitive/light literal은 12행/`0743f6050ced51367cf81045497817793c92d1da953923cd9d8a99dccc867ebe`,
  color input literal은 1행/`035f35a97d8ac2c6667d6cf204f18098822d8923abea3c7c22d589d5273d7ac0`다.
  structural scene input은 1행/`5918d2d13f80c9902a0a175d3f77ab5f4d126a6142109e12c9c30efa252b343d`,
  residual Blockout helper는 20행/`41bd0336f9492c43dc8bcbd2dae916e4f15368ea619a396a85bda10f9ccfb7c0`,
  broad Action 후보는 29행/`2f6fd81ce58fb9b7b4abaf23f8af7858b64a6aa68d04f580c25f7e61e47a232e`로
  분리됐고, 구조 경계 보강 후 감사 미분류 후보는 5,711건이며 unreviewed defect는 0이다.
- 추가 구조 감사에서 empty snap/update, empty/non-string primitive ID, bool snap coercion,
  non-finite/0 grid step을 owner/Undo 전에 거부하고 snap/material schema도 실제 변경 field를
  하나 이상 요구하게 했다. 별도 QA가 재현한 `#GGGGGG` 저장 색상 누출도 실제 hex 문자
  검사로 수정했다.
- 이 단계는 authored guide-control 안정성만 승인한다. 물리 world scale, lighting calibration,
  최적 composition, 렌더 품질, 외부 3D 제품 parity를 주장하지 않는다.
- 별도 읽기 전용 QA는 확장 회귀 62개, architecture guard 4개, 양방향 import,
  8192 endpoint projection 직렬화와 모든 invalid-state 보존을 재검증해 P0/P1/P2 없음으로
  최종 승인했으며 QA 중 소스는 수정하지 않았다.

## 2026-08-05 Action schema 분해 20: Atomic Stroke Strict Input

- `paint.stroke.draw`의 공개 schema는 strict였지만 direct adapter는 owner를 먼저 찾은 뒤
  bool/fraction을 int/float로 바꾸고 opacity, width, hardness, spacing, angle, roundness,
  engine, bristle, load와 tablet channel을 silent clamp했다. 호출 경로별 의미 차이를 실제
  재현하고 complete nested request validator를 owner 조회 앞으로 이동했다.
- 1..512 stroke, stroke당 2..2048 point라는 기존 atomic Action/Undo resource 계약,
  normalized/signed tablet domain, 공용 brush detail domain, 이름 붙인 Action width/opacity/
  engine/bristle endpoint를 schema와 runtime이 공유한다. unknown nested field, bool-as-number,
  fraction integer, NaN/Inf, 범위 밖 값, 잘못된 color/style/path/closed/layer/seed를 배치 전체
  mutation 전에 거부한다.
- schema 2행/`8d4b7d7a46887109237e689290f1c5fbf8446286ec2c75d65e2ad7927545765e`,
  input 1행/`95dd8cfabfa05317edc40b3e8abbe488b558b60a6c75f7a3e6a231c0f8e15006`,
  named literal 9행/`e1a40c1f8cee90f4469f0758825877d6464b2cecf548085da857d094d562cb1c`,
  structural literal 2행/`7deebb95b433e3746fc37197119284aee3dd05fdfde01893604604150409ed09`로
  분리했고 broad Action 후보는 25행/`c208c4d56afd2ed0c43c272d4cf403eedecf485733259e7b11fb4fdb636a56d0`다.
- 이 계약은 atomic request 안전성만 승인하며 작품 품질, 물리 매체 fidelity, latency,
  문서 전체 stroke capacity 또는 외부 painter parity를 주장하지 않는다.
- 최종 focused Action/Input/Brush-domain/Blockout/Document/degeneracy 회귀는 69개,
  architecture guard는 4개 통과했고, 계약 승인 후 감사는 미분류 5,702건,
  네 ledger stale 0, unreviewed defect 0이다.
- 별도 QA는 `seed=10**1000` Action 성공 후 v2 bristle render에서 발생하는
  `OverflowError`를 P1으로 재현했다. 기존 advanced-brush replay의 uint64 계약을 Action
  schema/validator에 연결해 seed를 `0..2^64-1`로 고정했고, 음수/초과/거대 정수는 상태와
  Undo를 보존하며 거부하고 uint64 max는 실제 v2 bristle QWidget render와
  `allow_nan=False`를 통과한다.

## 2026-08-05 Action schema 분해 21: Editor Object List / Render / Import

- 실제 코드에서 list limit와 time, include/force가 `int`/`bool`로 조용히 변환됐고,
  import의 명시 width/height 0은 런타임에서 0.04로, x/y는 크기에 따라 캔버스 안으로
  silently clamp됐다. `object_id`와 `kind`를 함께 보내면 kind가 무시됐고 공개 schema에는
  adapter가 받지 않는 `metadata`도 노출돼 있었다.
- 근거는 외부 제품 추정값이 아니라 기존 `drawing_editor_object_import`와 Painter sticker
  생성 경로가 실제 사용하던 최소 크기 0.04, normalized canvas containment, 기존 list 기본값
  100이다. 0.96은 최소 크기 객체가 캔버스에 들어오는 최대 시작점 `1-0.04`로만 도출했다.
  limit에는 근거 없는 최대치를 추가하지 않았다.
- list/render/import는 owner 조회 전에 실제 bool, 문자열 locator/output path, strict
  nonnegative integer time/limit, 유한 geometry를 검증한다. object_id+kind 동시 지정,
  bool-as-int, fraction/text/NaN/Inf, 0.04 미만 크기, 명시 rectangle overflow는 실패한다.
  명시 입력은 clamp하지 않고, 렌더러/객체의 누락·손상 fallback geometry만 별도 복구
  경계에서 같은 유한 domain으로 보정한다. 실패 시 sticker 수와 기존 상태가 보존된다.
- exact 계약은 input 2행/`bed6ecfe501b02a479d789124d545fef8fea35c7306eba36f398e98ab2268f7a`,
  schema 12행/`6dcb3d63acb6f648741b8bec79b7ac7937b39ac4530d97597f6d93f50bde8a37`,
  named literal 3행/`14a070c18b4a836f52846340d8dc041f7678f4cb2c8c7d80b742e20721b61ead`,
  structural literal 2행/`eaf7a5921062f6db5c2687a990b8d67cf9b3190b02f2b35e9b4a72a79a12c9db`,
  fallback JSON/containment literal 10행/`d832b147ae4890c2eea738270ab2524a2f56308fc15da553ce4e70cffcabede0`다.
  focused Action/Input 회귀는 32개 통과했고 재감사는 미분류 5,683건, 네 ledger stale 0,
  unreviewed defect 0이다. 이 단계는 Action 일관성과 상태 안전만 승인하며 4%를 보편적
  가독성·사용성 최적값이나 외부 제품 parity로 주장하지 않는다.
- 별도 읽기 전용 QA는 두 P1을 재현했다. 첫째, fallback sticker는 유한했지만 raw render와
  object payload의 NaN/Inf가 응답에 남아 `allow_nan=False`가 실패했다. geometry report와
  object payload를 유한 containment 경계로 정규화하고, 기타 nested non-JSON/nonfinite는
  mutation 전에 실패하도록 수정했다. 둘째, schema가 빈 locator 두 key의 존재만으로
  거부해 runtime의 strip/nonblank 의미와 달랐다. 두 nonblank locator가 실제로 함께 있을
  때만 거부하도록 맞췄다. QA는 76개 pre-owner invalid 조합, endpoint, overflow/state 보존,
  full strict JSON, focused 32개와 architecture 4개를 재검증해 최종 P0/P1/P2 없음으로
  승인했으며 소스는 수정하지 않았다.

## 2026-08-05 Action schema 분해 22: Atomic Stroke Canonical Construction

- strict input validator 뒤의 `paint_stroke_draw`가 이미 검증된 point/brush 값을 다시
  float/int/bool로 바꾸고 clamp했으며, 4px width, point-channel fallback, 0.28 depletion,
  7919/131 seed 계수와 material-disabled 채널이 adapter와 Stroke 모델에 흩어져 있었다.
  입력 거부 계약과 생성 계약이 달라질 수 있는 중복 경계였다.
- 근거는 외부 painter 수치가 아니라 현재 Stroke dataclass, 공용 BRUSH_DETAIL_DEFAULTS,
  기존 Action 결과다. 이름 붙인 Action 기본 계약으로 기존 바이트 의미를 이동하고 validator가
  omitted point/brush field를 owner 전에 canonical payload로 완성한다. adapter는 해당 값을
  재-clamp하지 않고 사용한다. 명시 blank/whitespace layer_id는 active layer로 silently
  대체하지 않고 실패한다.
- smooth path는 canonical point를 기존 `smooth_action_points`에 전달하고, polyline은 같은
  canonical channel을 그대로 전달한다. 표준 레이어의 material-disabled 채널은 Stroke 기본과
  같은 named map, 실제 material layer는 `normalize_material_settings` 결과를 사용한다.
  현재 timeline time은 기존 strict `_paint_action_time_ms` 경계를 사용한다.
- named default AST는 4행/`4a475e9ba15864ec0e7ea2fa8f08ae445dbe95c394a8ac91f4e6bd67b5e3dc75`,
  point/material channel은 14행/`0c76696e74d78b060e8fda28d58230382ab4cdbda1819a4a0707f31b8cfe7132`,
  diagnostic counter는 2행/`992024dd8fc929ab634635c5e8e3e082d326890997ba247a0be2d2be3d4ae156`,
  percent-to-alpha는 1행/`f7739fc72546693904b55afa720e430d6508a588d37a9cf95f262bcf5c82e296`다.
  focused Action/Input/architecture 회귀 36개가 통과했고 이 checkpoint 감사는 미분류 5,646건,
  네 ledger stale 0, defect 0이다. 이 계약은 replay/serialization 호환성만 승인하며
  seed 통계 품질, brush feel, 물리 안료, latency 또는 외부 painter parity를 주장하지 않는다.

## 2026-08-05 구조 계약 분해 23: Selection Transform Identity Defaults

- `paint_selection_transform`의 생략값 9개를 affine identity로 명시했다. translate/rotation/
  skew는 0, x/y scale은 1, normalized pivot은 정확한 중심 `(0.5, 0.5)`다.
- 공용 strict transform validator가 이 payload를 그대로 보존하고 nonfinite, zero scale,
  ±90도 singular skew, normalized 밖 pivot, 잘못된 bool/phase/target을 owner 전에 거부한다.
  identity 전체를 회귀에 고정했다.
- exact AST 계약은 9행/`4c5a3205c0cb3fed43bc4b8dd3a179a5867f51a9e462be501302c019aae5b7a5`다.
  focused input 26개가 통과했고 재감사는 미분류 5,637건, 네 ledger stale 0, defect 0이다.
  이 값은 항등변환과 normalized midpoint의 수학 구조이며 모든 작업에서 center pivot이
  최적이라는 UX 주장이 아니다.

## 2026-08-05 Action schema 분해 24: Brush Set Complete Request

- 기존 `paint.brush.set`은 빈 payload도 성공시키면서 Pen 도구로 전환했고, schema/adapter/UI가
  width·opacity·hardness·spacing·angle·roundness 범위를 서로 다른 literal로 중복 선언했다.
  preset/style/numeric 검증은 owner 전이었지만 missing preset과 active combo 누락 검사는
  owner 뒤에 있어 상태 불일치 위험이 있었다.
- actual Painting opacity slider 10..100, 공용 brush-domain 상수, 공개 canonical style enum만
  근거로 `validate_brush_set_action`을 만들었다. 전체 payload를 먼저 검증하고 at least one
  authored field를 요구한다. 빈/whitespace-only 이름, unknown preset, aliases, bool-as-int,
  fraction/out-of-range numeric, nonbool flip, nonobject dynamics는 mutation 전에 실패한다.
- preset row는 owner 전에 resolve하고, requested style의 active QComboBox index도 preset/model/
  canvas mutation 전에 preflight한다. schema anyOf는 11개 authored field 중 하나를 요구하고,
  preset-only branch는 실제 nonblank text만 인정한다. 명시 `{}` dynamics는 기존 dynamics
  defaults reset이라는 실제 변경 요청이므로 허용한다.
- schema exact는 3행/`27b886aac44107ee9eccfb61f690bfadfc581be33412fa17eebd1f5a875a08ec`,
  opacity named literal은 2행/`3dcf4ce96fcf5f9038036b585c86909240af10e822378a2db1c4127590c3cf10`,
  empty guard는 1행/`1cb0f8be1ffeae826f0300adaf7716ce4d3b7b0bd27cab0209064f15e77cedbd`,
  percent-alpha fallback은 1행/`c0eb9c3f616e31513f7802284edb6f2e642d97632ef092d88bf08a21ce0295a7`,
  combo lookup은 1행/`23ddc6df0c2d2699297bd8272a74dcc58fbf5a81317c1943072d84f0a09866cc`다.
  focused Action/Input/Brush 회귀 56개가 통과했고 재감사는 미분류 5,635건, 네 ledger
  stale 0, defect 0이다. dynamics 내부 값의 coercion/default/model 품질은 이 단계가 승인하지
  않으며 별도 Brush Dynamics 측정 단위에 남긴다.

## 2026-08-05 구조 계약 분해 25: Editor Object Commit / Lifetime

- editor-object import의 검증/JSON fallback 뒤 남은 commit 수치를 분리했다. 최종 rect는
  normalized canvas 각 축 1.0 안이어야 하며 explicit geometry는 clamp하지 않는다. fallback
  x/y만 width/height를 뺀 범위로 보정한다.
- 새 Sticker는 기존 최대 z-index보다 정확히 1 위에 놓이고, 기존 Sticker 모델이 문서화한
  `end_ms=-1`(프로젝트 끝까지 표시) sentinel을 사용한다. containment와 z-order 계산은
  append 전에 끝난다. 연속 import는 z-index 1/2, overflow와 nested failure는 기존 count
  보존, malformed fallback은 full strict JSON을 회귀한다.
- commit scanner는 2행/`86213f1fb6d8cfa3fd300db7882dced2ac9bd8480cb9b88611b083e5758a4d2b`,
  geometry AST는 4행/`faf193f11b36447083c75c1fd541f98c1e4390830d90c61ad695bdb78b650cff`,
  lifetime sentinel은 1행/`b44efdb4dc4407150bd36654da7f58b7c06e92f253fca10ca2ee4446fb28c0ef`다.
  후속 재감사는 미분류 5,628건, 네 ledger stale 0, defect 0이다. 이는 내부 normalized
  geometry/list/timeline 구조이며 placement 품질이나 외부 포맷 관례를 주장하지 않는다.

## 2026-08-05 Action schema 분해 26: Canvas Pan QPoint / Operation Mode

- `paint.view.pan` 직접 호출이 실수·문자열·bool을 `int()`로 변환하고, reset/absolute/
  relative 입력을 함께 받아도 우선순위로 일부 필드를 조용히 무시하던 경로를 제거했다.
  빈 요청, `reset=false`, 혼합 모드, `(dx,dy)=(0,0)`은 owner 조회 전에 실패한다.
- 근거는 감각적인 pan 한계가 아니라 실제 저장 형식이다. Qt 공식 문서는 `QPoint`를
  integer-precision 좌표와 `QPoint(int,int)` 생성자로 정의한다. 번들 PySide6를 직접
  측정해 signed 32-bit 양 끝값은 보존되고 바깥값은 `OverflowError`임을 확인했다.
  schema와 runtime은 같은 이름 붙인 -2147483648..2147483647 끝점을 사용한다.
- 실제 `QPoint` 덧셈이 범위를 넘으면 반대쪽 끝으로 wrap되는 것도 측정했다. 따라서
  relative pan은 Python에서 목표 좌표를 계산하고 같은 끝점으로 재검증한 다음 한 번만
  commit한다. overflow는 `_set_canvas_pan` 전에 실패한다.
- exact 계약은 schema 2행
  `def030127a3dc2ea3344453cfb0000c2dddc7a5219d4c0c3011d7bb9592552c2`, named
  endpoint 2행 `e5d8f9813f01e7ed49323cbdbb9e788e00861d9700671cbe8806175de813eb72`,
  zero-vector input 1행 `499050e12010f030d74347eeb67784249354126610c64287e76f7fcf788dbb54`,
  commit identity 6행 `cdcbeeda37558c5c80a6fe0487de1e92bce9d54df56f9d9566264279b5eabbcf`이다.
  focused Action/Input/architecture 37개가 통과했다. 이 계약은 Qt 좌표 안전성과 Action
  원자성만 승인하며 사용감, 최대 유용 이동량, 외부 Painter parity를 주장하지 않는다.
- 독립 QA가 명시 `null`을 생략과 같게 취급하는 schema/runtime P1을 재현했다. 공용
  omission sentinel로 다섯 필드의 property presence를 보존하고 `dx=1,reset=null`,
  `dy=1,x=null`, `x=1,dy=null`을 모두 owner 전에 거부했다. Pan+Mask 집중 회귀 48개와
  재QA가 통과해 최종 P0/P1/P2는 모두 0이다.

## 2026-08-05 Action schema 분해 27: Layer Mask State / Paint / Gradient

- 인접한 세 mask Action은 bool/float/int coercion, normalized 좌표 clamp, Alpha8 값 clamp,
  0.5px radius 대체, gradient extra-coordinate 무시를 서로 다르게 수행했다. 세 경로를
  하나의 사전검증 계약으로 묶어 owner와 Undo 전에 전체 payload를 확정한다.
- state는 enabled/linked 중 하나 이상 또는 단독 `delete=true`만 허용한다. paint는 finite
  normalized 좌표, 실제 QImage Alpha8의 0..255 정수, 기존 rasterizer의 0.5px 최소 반지름을
  사용한다. gradient는 정확히 두 좌표인 start/end, 서로 다른 endpoint, Alpha8 시작/끝값을
  요구한다. 명시 layer ID의 whitespace-only 값도 active layer fallback으로 바꾸지 않는다.
- Alpha8 범위 근거는 Qt 공식 `QImage::Format_Alpha8` 8-bit alpha-only 문서다. normalized
  좌표와 서로 다른 두 점은 canvas mapping/선형 gradient 구조이고, 0.5px는 기존 Tiger
  rasterization 정책으로만 유지하며 미학·사용감·외부 제품 parity를 주장하지 않는다.
- exact 계약은 schema 19행
  `1eda0648c6a61015363f57bfcd5950c4a78c45a1296c7fb7455360b980e0658f`, input AST 6행
  `29cb482e3d9b24796d99921a323e872726d90724db738b0957293c90db9dfe5f`, gradient default
  2행 `54bda2ffd4c94fb3f5e35281ef4b3c9d1a71655cba1608dbfe5e7db8690edc1e`다.
  Pan을 포함한 Action/Input/Layer-mask/architecture 집중 회귀 48개가 통과했다.

## 2026-08-05 Fallback 분해 28: Canvas Size Source

- `_paint_canvas_size`와 export background 경로가 문서/Qt geometry의 문자열·실수·bool을
  `int()`로 조용히 변환하던 동작을 제거했다. raster extent는 양의 실제 정수만 인정한다.
- document size는 width/height 정확히 두 축이어야 한다. malformed document state는 기존
  순서대로 drawing/preview widget, preview pixmap으로 넘어가며 모두 실패하면 명시 오류다.
  background export도 같은 helper를 거쳐 canvas source로 fallback한다.
- exact scanner는 1행/`33215446b232a9e97c954697863ce6c6b275655d75612dbde8e019bd36994fce`,
  two-axis AST는 3행/`6619b51d1f140d16b19c7030cae49f64904386d91466d183f3cf29f7d15d8d87`다.
  Mask/Pan 포함 집중 회귀는 49개가 통과했다. 이는 operational recovery와 raster 구조이며
  기본 해상도, 품질 최적값, 외부 제품 관례를 주장하지 않는다.

## 2026-08-05 Action schema 분해 29: Reference Board Mutation

- add/update/delete/duplicate/bake가 owner 뒤에서 path/name/normalized geometry/opacity/rotation/
  bool/offset을 `str/float/bool`로 변환하고 update 빈 요청과 명시 `null`을 허용하던 경계를
  제거했다. 전체 payload는 owner 전에 검증되며 update는 하나 이상의 authored field를
  요구하고 omission sentinel로 `null`과 생략을 구분한다.
- update/delete/duplicate는 명시적인 비공백 reference ID를 반드시 요구한다. ID 생략 시
  현재 선택 항목으로 바꾸던 암묵 fallback은 의도하지 않은 대상 변경 위험과 공개 schema의
  required 계약 불일치 때문에 제거했다. 선택 항목을 대상으로 하는 bake만 optional ID를
  유지한다.
- 근거는 기존 Reference Board 직렬화 모델이다. position 0..1, size 0.02..1, opacity
  0.05..1, rotation -180..180도, 이름 80자, add 기본 0.04/0.04/0.34/0.34/0.58/0,
  duplicate offset 0.04를 이름 붙인 공용 상수로 통합했다. duplicate 최대 시작점 0.98은
  `1.0-0.02`로만 도출한다. offset 자체에는 추정 최대치를 추가하지 않고 finite만 요구한다.
- 기존 `value or default` 때문에 유효한 x/y=0이 0.04로 바뀌던 문제를 제거했다. restore의
  malformed/nonfinite scalar는 별도 forgiving 경계에서 이름 붙인 default로 복구하지만 실제
  0은 보존한다. Action은 clamp/truncate/coercion하지 않는다.
- exact named model 계약은 명시 대상 ID의 구조적 1자 최소값을 포함한 18행
  `aa9c50799240bc245a73661dbc50bcc15eed4957caf3643f876bdba8ee2d21b4`, commit selection
  구조는 3행 `08609ae84fe70be374351abeea7f9bf32012b5c937fb92407c33bf9ea82e26b5`다.
  기존 geometry/model 16행은 이름 붙인 duplicate 최대점으로 갱신되어
  `924728edf2bf330cfd82afcf59082f8ad86553c0e079d6501a93adf7a3cd9b88`이다.
  집중 회귀 52개가 통과했다. 이 계약은 Tiger 모델 호환성만 승인하며 composition 최적값이나
  외부 제품 parity를 주장하지 않는다.

## 2026-08-05 Action schema 분해 30: Saved Path Create

- `paint.path.create`가 owner 뒤에서 `points or []`, `bool(...)`, `float(...)`와 clamp/skip으로
  요청 의미를 바꾸던 경계를 분리했다. Action은 owner 전에 전체 배열을 검증하고, 각 행을
  정확한 2값 배열 또는 정확한 `x/y`, `x_norm/y_norm` 객체로 제한한다. bool, 문자열,
  nonfinite, 누락/혼합 key, 여분 값, 0..1 밖 좌표는 보정하지 않고 실패한다.
- 2점은 선 path의 구조적 최소, selection 동시 생성의 3점은 polygon 경계의 구조적 최소다.
  최대 2048점은 saved path가 `Stroke.points`에 직렬화되므로 기존 단일 Stroke Action 자원
  계약을 그대로 재사용한다. Qt QPainterPath 공식 문서의 element/subpath 의미를 플랫폼
  근거로 사용한다: https://doc.qt.io/qt-6/qpainterpath.html
- path-to-selection/delete의 optional active-target ID도 실제 문자열만 허용하고 공백은 거부한다.
  commit `closed`는 실제 bool만 허용한다. schema와 runtime은 selection 요청의 3점 조건까지
  일치한다.
- exact schema 계약은 15행
  `8aea7026862ffecb767a786c0f3cd4a3469fd48db09a4c3b852319ea38be6bac`, named literal
  계약은 중복 정의 제거 후 canonical 4행
  `032c235852245dd14e96ae2178a3533ec6bfaee89d346e3a02c6b6e5c4eaf0d0`다.
  이는 path topology/normalized serialization/기존 atomic Action 한도만 승인하며 선호 곡선,
  composition 또는 외부 Painter parity를 주장하지 않는다.

## 2026-08-05 Action schema 분해 31: Saved Path Mutation

- anchor edit의 index/operation/point/handle 조합을 owner 전에 완전 검증한다. add/move는
  normalized point 필수, delete는 point/handle 금지, add는 handle 금지, corner는 실제 연산이
  handle을 초기화하므로 handle 입력을 금지한다. point는 0..1 finite, Bezier handle은 canvas
  밖 곡률 표현을 위해 범위를 추정하지 않고 finite만 요구한다.
- duplicate/rename/reorder/fill/stroke의 ID·이름·index·색·width 변환을 owner 앞으로 옮겼다.
  색상 문법은 Qt QColor `isValid()` 공식 계약을 사용한다:
  https://doc.qt.io/qtforpython-6/PySide6/QtGui/QColor.html
  stroke width는 기존 Action brush domain 0.25..5000px를 재사용하고, 근거 없던 schema의
  0.1..4096 pair는 제거했다.
- schema exact는 1행
  `a2b87c29a5e2907e09a56331cd7c0a362f781b8efc14baaebbd1c49adab96caa`, named literal은
  2행 `383440966d2ace4308d9573610458de7040caaf2672845c1b20286ff3edcf1cf`다.
  zero-based index와 nonblank identity만 승인하며 이름 선호, 곡선 미학, 품질 parity를
  주장하지 않는다.

## 2026-08-05 Action schema 분해 32: Layer Mutation

- add/import/group/rename의 이름을 직렬화 모델의 canonical 80자 한도 전에 검증한다. 기존
  `[:80]` silent truncation은 Action에서 실패로 바뀌고, core layer 생성/rename도 같은 이름
  상수를 사용한다. type/blend/color는 exact enum만 허용하며 invalid 값을
  standard/normal/none으로 바꾸지 않는다.
- optional active-layer ID는 exact empty만 허용하고 명시 ID 공백은 owner 전에 거부한다.
  select/group disclosure는 explicit nonblank ID 필수다. clipping/expanded/visible/locked와
  lock channel은 실제 bool만 허용하고, lock update는 omission sentinel로 empty/null을
  구분하며 하나 이상의 authored field를 요구한다.
- 그룹 생성은 모든 target 존재와 position lock을 mutation 전에 확인한다. unknown/duplicate/
  blank/position-locked target이 하나라도 있으면 그룹 자체를 만들지 않는다. 기존 테스트가
  group 생성 여부만 보고 일부 child가 빠진 partial success를 놓치던 문제를 parent_id 전수
  assertion으로 보강했다.
- duplicate/delete는 PaintLayer만 대상으로 하며 missing explicit ID가 이전 선택 레이어로
  fallback하지 않는다. duplicate의 text-focus/payload 실패, delete의 missing/locked/last-layer
  유지 실패를 성공으로 보고하지 않고 layer list와 선택을 보존한다. merge-visible/flatten의
  무시되던 layer_id schema/property도 제거했다.
- blend backend 근거는 Qt QPainter CompositionMode 공식 문서다:
  https://doc.qt.io/qt-6/qpainter.html
  canonical identity literal은 2행
  `e30c03050d4ae3c4a28a8616740c5ea989d1f26eb56c7baa6c7d09bf41a6902f`다.
  이는 Tiger 직렬화 identity와 Qt backend semantics만 승인하며 naming 취향이나 Photoshop
  parity를 주장하지 않는다.

## 2026-08-05 Action schema 분해 33: Channel / Quick Mask

- 채널 Action ID는 `RGB`, `Red`, `Green`, `Blue`, `Alpha`의 정확한 문자열만
  허용한다. Adobe 공식 Channels 문서의 RGB composite/component 구조와 alpha
  channel 정의를 근거로 삼되, Tiger의 단일 `Alpha`는 현재 background source의
  alpha component라는 제한을 스펙에 명시했다. 임의 개수 alpha channel을 지원한다고
  추정하거나 Photoshop parity를 주장하지 않는다.
- visibility와 Quick Mask boolean은 실제 bool만 허용한다. no-op visibility는 선택
  채널을 바꾸지 않고 실패하며, no-op Quick Mask도 mutation 성공으로 보고하지 않는다.
  copy는 read Action이므로 명시 channel을 읽어도 현재 선택을 바꾸지 않는다. paste는
  Qt `QClipboard.image()`의 null-image 계약에 따라 클립보드 이미지를 먼저 확인한 뒤에만
  선택과 document를 변경한다.
- 2-pixel RGBA fixture로 Blue copy의 grayscale 값 `30/200`과 Red paste의 결과
  `(60,20,30,255)/(180,150,200,255)`를 실제 측정한다. 빈 clipboard 실패, copy/no-op
  선택 불변, exact enum/schema/runtime 검증도 회귀로 고정한다.
- Adobe 공식 Quick Mask는 임시 마스크를 paint/filter로 편집하고 종료 시 selection으로
  되돌린다. 현재 Tiger는 기존 selection overlay 토글만 구현되어 있으므로 이 편집·변환
  기능은 미충족 Painting gap으로 다음 기능 마일스톤에 남기며 완료로 간주하지 않는다.
  근거: https://helpx.adobe.com/photoshop/using/channel-basics.html,
  https://helpx.adobe.com/photoshop/using/create-temporary-quick-mask.html,
  https://doc.qt.io/qt-6/qclipboard.html
- M32 회귀를 포함한 집중 테스트 51개가 통과했다. fresh 전수감사는 unresolved
  `5555`, numeric-literal gap `4685`, stale ledger `0/0/0/0`, defect site `0`으로
  M32 기준보다 새 미결정이나 stale 계약을 만들지 않았다.

## 2026-08-05 Action schema 분해 34: Selection State

- `set_aspect`와 `set_mode`의 direct adapter 경로가 `str(... or default)`와 core alias
  fallback으로 잘못된 입력을 `free/new`로 바꾸던 경계를 제거했다. schema와 runtime은
  각각 `free|square|16:9|4:3`, `new|add|subtract|intersect` exact enum을 공유하고 owner
  전에 non-string, casing alias, 빈 값을 거부한다.
- Select All은 현재 Alpha8 selection mask가 전부 255일 때 no-op로 보고 Undo를 추가하지
  않는다. active selection 없는 Deselect와 3점 selection 없는 Selection To Path도 실패를
  성공으로 보고하지 않으며 Undo/document를 보존한다. Invert의 empty→full은 집합 보수의
  수학적 동작이므로 유지한다.
- Adobe 공식 근거는 basic Select All/Deselect, marquee의 New/Add/Subtract/Intersect 및
  Normal/Fixed Ratio, selection-to-work-path의 사전 selection 요구다. Tiger의 네 aspect
  preset은 명시적 subset이며 Photoshop Fixed Ratio/Fixed Size 전체 parity를 주장하지 않는다.
  근거: https://helpx.adobe.com/photoshop/using/making-selections.html,
  https://helpx.adobe.com/photoshop/using/selecting-marquee-tools.html,
  https://helpx.adobe.com/sg/photoshop/using/converting-paths-selection-borders.html
- M29-M34 관련 집중 회귀와 selection-mask 회귀 56개가 통과했다. full-mask 판정은 기존
  8-bit max 상수의 이름 붙인 alias를 사용해 새 숫자 literal을 추가하지 않았고, fresh 감사는
  unresolved `5555`, numeric-literal gap `4685`, stale `0/0/0/0`, defect `0`을 유지했다.

## 2026-08-05 Action schema 분해 35: Crop Preview

- crop preview bounds는 네 좌표 전부 생략하여 active selection을 쓰거나, x1/y1/x2/y2를
  모두 명시하는 두 형태만 허용한다. 일부 좌표가 주어졌는데 `bounds=None`으로 버리던 silent
  fallback을 제거하고, null/bool/non-real/nonfinite/out-of-range/non-positive rectangle을
  owner 전에 거부한다. schema도 두 exclusive object shape으로 같은 계약을 표현한다.
- 기존 `straighten_degrees`의 -45..45 schema/core clamp를 제거했다. Adobe 공식 Crop 및
  Straighten 문서는 crop corner 회전과 straighten line 동작을 설명하지만 이 수치 한도를
  제시하지 않고, QPainter 회전 backend도 해당 clamp를 요구하지 않는다. 따라서 finite real만
  요구하며 이는 외부 angle interaction parity 주장이 아니라 근거 없는 제한 제거다.
- 동일 preview 반복, preview 없는 cancel/commit은 mutation 성공으로 보고하지 않는다.
  partial/invalid payload는 preview/document를 보존한다. 16x12 fixture의 0.25..0.75 crop이
  실제 8x6 document가 되는지, 90도 authored preview가 clamp 없이 90도로 저장되는지 측정한다.
  근거: https://helpx.adobe.com/photoshop/desktop/crop-resize-transform/crop-straighten/crop-photos.html,
  https://helpx.adobe.com/photoshop/desktop/crop-resize-transform/crop-straighten/straighten-tilted-photos.html
- 독립 QA에서 Action/core와 별개인 direct-canvas rotate 분기에 남은 -45..45 clamp와,
  `_handle_m3_canvas_interaction` 전체를 UI Design으로 제외하던 감사 누락을 발견했다. 두 경로를
  바로잡아 rotate handle 측정이 180도를 그대로 저장하도록 회귀를 추가했고, 해당 함수의 crop,
  selected-pixel transform, saved-path interaction 전부를 Painting 감사 범위에 포함했다.
- 새로 노출된 Painting 경로에서 근거 없는 0.01 normalized resize floor, 0.001 transform
  denominator, 고정 11 px pivot hit radius를 제거했다. resize는 `math.nextafter`의 정확한 양수
  extent, transform은 이미 검증된 양수 bounds, hit test는 Qt 플랫폼 metric인
  `QApplication.startDragDistance()`를 쓴다.
- M29-M35 집중/selection-mask 회귀 58개가 통과했다. canvas control 57행은 hash
  `27831b6d60f13974842f56f084205c3efba3e53c8c685334b082637f3b14884d`, 서로 다른 스캐너가
  같은 broad ID로 승인되지 않도록 분리한 structural literal 11행은 hash
  `e54798bc31a9d3878e07f728a83543f5b7239b44d20092291b1177f3d4e38fd9`로 각각 동결했다.
  fresh 감사 결과 unresolved `5550`, numeric-literal gap `4681`, stale `0/0/0/0`, defect `0`이며,
  보정 대상 함수에 남은 미심사 canvas-selection 리터럴은 0개다.

## 2026-08-05 Action schema 분해 36: Canvas Flip / Fill / Mirror

- 공식 근거는 Adobe의 whole-canvas horizontal/vertical flip, selection-clipped fill/gradient
  설명과 Qt `QImage`, `QColor`, `QLinearGradient`, `QBrush` 계약이다. Adobe pattern preset
  parity나 미술적 최적값은 주장하지 않는다.
- flip axis는 exact `horizontal|vertical` 필수값으로 고정했다. 생략, x/y alias, case/공백
  보정, non-string은 owner 전에 실패한다. asymmetric 8x8 raster의 양 끝 색이 정확히
  교환되는지 측정한다.
- solid/gradient/pattern Action의 색은 명시 필수이며 `QColor.isValid()`를 owner 전에
  통과해야 한다. gradient의 추정 0.52 middle stop과 136/132 명암 factor를 제거하고 authored
  color1 stop 0에서 color2 stop 1까지의 Qt 선형 보간만 사용한다.
- pattern의 추정 118 darken, 문서 크기 /360 line width, /80 spacing, 14 px floor를 제거하고
  Qt 공식 `Dense4Pattern`을 color1 base 위에 color2로 적용한다. 8x8 측정에서 출력 색 집합이
  authored 두 색과 정확히 일치한다.
- 잠금/group/pixel-lock layer에서 `_fill_document`가 false를 반환하면 Action도 실패하며
  픽셀을 보존하고, 출력 raster가 입력과 동일한 fill 반복도 no-op 실패다. mirror는 x/y 중
  하나 이상의 실제 bool을 요구하고 동일 상태 반복을 mutation 성공으로 보고하지 않는다.
- 근거: https://doc.qt.io/qt-6/qimage.html, https://doc.qt.io/qt-6/qcolor.html,
  https://doc.qt.io/qt-6/qlineargradient.html, https://doc.qt.io/qt-6/qbrush.html,
  https://helpx.adobe.com/photoshop/using/adjusting-crop-rotation-canvas.html,
  https://helpx.adobe.com/photoshop/desktop/adjust-color/color-effects-techniques/apply-gradient-fill.html,
  https://helpx.adobe.com/sg/photoshop/desktop/apply-painting-techniques/fill-objects-selections-layers/fill-selection-layer-color.html
- Action/input/architecture 집중 회귀 50개와 별도 8x8 raster 측정 2개가 통과했다. numeric
  ledger는 guessed pattern rows 제거 후 12행 hash
  `370ac4a1fd80a885d091feb9ddd0819908887caaa2961bbc95247252e413748a`, mirror tuple 구조는
  1행 hash `d7e117649c3c7e57a35e0445c46c4d14ee876bec476e6fe908e8eb471b4d0424`로 동결했다.
  fresh 감사 결과 unresolved `5546`, numeric-literal gap `4677`, stale `0/0/0/0`, defect `0`이다.

## 2026-08-05 Action schema 분해 37: Layer Mask Source / Apply

- Adobe 공식 Layer Mask의 Reveal Selection, Current Path, Apply/Delete 구분과 Qt Alpha8 및
  DestinationIn-equivalent alpha multiplication을 근거로 삼았다. Smart Object/vector-mask parity는
  주장하지 않는다.
- selection/path/create/apply의 layer/path/source 입력을 owner 전에 검증한다. path 전용 Action은
  nonblank `path_id`가 필수이며, Action이 지정한 path를 UI `_path_list.currentItem()`이 다시
  덮어쓰던 경로를 제거했다. 성공/실패 모두 기존 `_selected_path_item_id`를 보존한다.
- generic create의 source type은 공개 schema의 exact canonical set만 받는다. alpha/layer_alpha와
  white/reveal_all은 기존 공개 Action alias로 명시 보존하며 case/공백/추가 legacy alias는 거부한다.
- selection 및 closed path 결과는 `QImage.Format_Alpha8`로 정규화한다. 동일 enabled mask를 다시
  만들면 Undo나 성공을 생성하지 않는다.
- create/apply는 target layer를 direct lookup으로 preflight하고 성공 mutation 직전에만 선택한다.
  존재하지만 locked인 다른 target으로 실패해도 기존 active layer ID가 보존되는 회귀를 추가했다.
- 4x1 red raster에 `[255,128,0,255]` Alpha8 mask를 Apply한 실측 결과가 같은 알파 배열이고,
  적용 뒤 editable mask가 제거되는지 확인했다. locked/non-paint/disabled/missing mask는 raster를
  바꾸지 않고 실패한다.
- create는 paint뿐 아니라 group/adjustment mask를 지원한다. Tiger compositor가 group output과
  adjustment effect에 Alpha8을 실제 적용하고 Adobe도 layer/group mask를 문서화하기 때문이다.
  8x8 red child의 group path mask 실측은 내부 alpha 255, 외부 alpha 0이다. 반면 Apply는 paint
  raster에만 허용하며 group Apply는 기존 mask를 보존하고 실패한다.
- 근거: https://helpx.adobe.com/photoshop/desktop/create-masks/layer-masks/add-layer-masks.html,
  https://helpx.adobe.com/photoshop/using/converting-paths-selection-borders.html,
  https://helpx.adobe.com/photoshop/using/masking-layers-vector-masks.html,
  https://helpx.adobe.com/photoshop/desktop/create-masks/layer-masks/apply-or-delete-layer-masks.html,
  https://doc.qt.io/qt-6/qimage.html
- Action/input/layer-mask/architecture 집중 회귀 63개가 통과했다. fresh 감사 결과 unresolved
  `5546`, numeric-literal gap `4677`, stale `0/0/0/0`, defect `0`이다. 이 단계는 새 수치 정책을
  만들지 않았으므로 기존 numeric ledger 지문을 변경하지 않는다.

## 2026-08-05 Action schema 분해 38: Path to Selection

- Adobe 공식 path-to-selection 문서의 closed path, selection border, New/Add/Subtract/Intersect
  의미를 근거로 조사했다. Tiger Action은 현재 New Selection만 지원하며 feather/operation parity는
  주장하지 않는다.
- 기존 adapter는 `path_id`를 selected state에 먼저 쓴 뒤 core를 호출했지만, core가 visible
  `_path_list.currentItem()`으로 다시 덮어썼고 3점 미만이어도 void return 뒤 성공을 보고했다.
- core에 explicit `path_id` 경로와 bool mutation 결과를 추가했다. 명시 ID는 UI current item보다
  우선하며, 생략 시에만 active path를 쓰는 interactive 호환 계약이다.
- missing `path:999`와 2점 work path는 Undo/tool/selection/pixel mask/selected path를 바꾸지 않고
  실패한다. 3점 explicit work path는 다른 selected ID 상태에서도 authored 순서 그대로 3점
  selection을 만들며, 그 결과 상태에서 동일 변환 반복은 no-op 실패다.
- 근거: https://helpx.adobe.com/photoshop/using/converting-paths-selection-borders.html
- 로컬 Action/input/new-canvas/architecture 집중 회귀 75개와 독립 QA의 path 포함 5모듈
  집중 회귀 77개가 통과했다. fresh 감사 결과
  unresolved `5546`, numeric-literal gap `4677`, stale `0/0/0/0`, defect `0`, test functions
  `455`다. 새 수치 정책은 없다.

## 2026-08-05 Action schema 분해 39: Clipboard Copy / Cut / Paste

- Qt 공식 QClipboard/QMimeData의 global clipboard, custom MIME, image/URL/text payload 계약과
  Adobe 공식 selection Copy/Cut/Paste 의미를 기준으로 조사했다. Tiger editable layer MIME 보존은
  자체 포맷이며 Photoshop layer-object 포맷 parity는 주장하지 않는다.
- 기존 세 adapter는 core void return을 무시해 빈 paste, locked cut, 선택 없음에도 성공을
  보고했다. core copy/cut/paste와 payload paste를 bool mutation 계약으로 바꾸고 adapter가 false를
  Action 실패로 전달한다.
- Copy/Cut은 Tiger custom MIME와 rasterizable QImage preview를 같은 QMimeData에 쓴다. 시스템
  clipboard write가 실패하면 Copy/Cut도 실패하며 Cut은 픽셀/레이어를 삭제하지 않는다.
- active selection이 있으면 보이는 selected raster만 대상으로 하며 empty selection raster를
  whole-layer로 fallback하지 않는다. 선택이 없으면 active Tiger layer payload를 복사한다.
- 마지막 paint layer는 document shell로 남겨야 하므로 Cut은 nonempty raster/stroke/mask를 비우고
  성공한다. 이미 빈 마지막 shell Cut은 clipboard와 Undo를 만들지 않는다. 다른 paint node가
  있을 때만 target paint layer를 제거하며 group/adjustment node는 shell 수에 포함하지 않는다.
- 독립 QA가 malformed custom MIME, malformed process-local payload, structurally valid empty payload,
  `[paint 1 + group 1]`의 마지막-paint 삭제 문제를 P1으로 재현했다. v2 필수 구조와 base64/PNG를
  fail-closed로 검증하고, 실제 raster/stroke/mask content를 요구하며, invalid custom MIME가 valid
  standard-image preview나 local fallback으로 내려가지 않게 했다. v1의 optional mask 호환은
  명시적으로 유지한다. Clipboard의 empty guard와 Layer Duplicate의 빈 구조 복제도 서로 분리했다.
- 4x2 red raster의 half-selection round trip 실측에서 custom MIME+standard image가 모두 존재하고,
  paste 크기 4x2, 선택 내부 red, 외부 alpha0, Cut은 선택 half만 alpha0으로 만든다. 강제 clipboard
  write failure와 locked Cut은 원본 raster를 exact 보존하며 empty Paste는 Undo를 만들지 않는다.
- 근거: https://doc.qt.io/qt-6/qclipboard.html, https://doc.qt.io/qt-6/qmimedata.html,
  https://helpx.adobe.com/photoshop/desktop/make-selections/refine-modify-selections/copy-and-paste-selections.html,
  https://helpx.adobe.com/photoshop/desktop/make-selections/refine-modify-selections/delete-or-cut-selected-pixels.html
- 로컬 Painting Action/래스터/레이어/mask/새 캔버스/아키텍처 묶음 회귀는 `143 passed`,
  독립 QA 7모듈 회귀는 `131 passed`다. last-shell 수 계산의 새 숫자 literal을 identity 기반
  `other_paint_node_exists`로 바꾼 뒤 fresh 감사는 unresolved `5545`, numeric-literal gap `4677`,
  stale `0/0/0/0`, defect `0`, test functions `457`이다. M38 기준보다 unresolved는 1 감소했고
  numeric gap은 증가하지 않았다.

## 2026-08-05 M40 완료·독립 QA PASS: Editable Quick Mask lifecycle

- Adobe 공식 Quick Mask 문서는 temporary channel, protected overlay, white=selection 추가,
  black=selection 제거, gray=partial selection, 종료 시 unprotected 영역의 selection 변환을
  정의한다. 50%는 경계 표시 기준이며 partial weight 삭제 기준이 아니다.
  근거: https://helpx.adobe.com/photoshop/using/create-temporary-quick-mask.html
- Qt 공식 `QImage::Format_Alpha8`와 `QPainter`를 저장·stroke raster backend로 사용한다.
  근거: https://doc.qt.io/qt-6/qimage.html, https://doc.qt.io/qt-6/qpainter.html
- `app/painter_quick_mask.py`가 document-sized Alpha8 selectedness, 50% boundary chrome,
  inverse red overlay와 coverage 합성을 담당한다. 진입은 기존 weighted mask를 exact 보존하거나
  no-selection을 전부 보호된 0으로 시작하며 foreground/background를 black/white로 전환한다.
- Quick Mask 중 pen/eraser stroke는 active paint layer에 들어가지 않고 selection mask만 편집한다.
  pen은 Qt `qGray` 값을 사용하며 eraser=white/add-selection은 Adobe eraser parity가 아닌 명시적
  Tiger 정책이다. 실제 mouse Eraser도 `stroke_added(source_tool=eraser)` 1개를 만들고 기존
  `stroke_erased_at` 삭제 신호는 내지 않으며 tablet eraser도 같은 lifecycle을 사용한다. effective
  edit만 full snapshot Undo 1개를 만들고 opacity 0/no-op은 만들지 않는다.
- 종료는 128 이상만 boundary chrome으로 바꾸되 partial Alpha8는 그대로 보존하고 이전 swatch를
  복구한다. mode 중 저장은 exact selection mask와 이전 swatch를 보존하되 temporary mode 자체는
  false로 열리며, inverted polygon 진입도 실제 inverted pixel mask를 사용한다.
- 순수 측정은 source `[0,64,128,255]`, white `[255,255,192,255]`, black `[0,0,64,255]`,
  gray `[128,128,128,255]`, boundary `[0,0,255,255]`, overlay alpha `[128,64,63,0]`을
  확인했다. focused 회귀는 `96 passed`, 태블릿/M3 입력 포함 확대 회귀는 `173 passed`다.
  fresh 감사는 unresolved `5542`, numeric-literal gap `4674`, stale `0/0/0/0`, defect `0`,
  test functions `461`이다.
- custom overlay 색/불투명도, 필터 기반 Quick Mask 편집, permanent alpha-channel 변환은 후속
  gap이며 M40은 해당 Photoshop 옵션 parity를 주장하지 않는다.
- 별도 QA 에이전트의 최신 판정은 P0/P1/P2 `0/0/0`이다. Quick Mask 4개, focused 96개,
  evidence+architecture 30개, 확대 10모듈 173개가 모두 통과했고 writer 없는 fresh 감사와
  `git diff --check`도 동일하게 재현됐다.

## 2026-08-05 M41 완료·독립 QA PASS: Saved Selection Alpha Channels

- Adobe 공식 문서는 selection을 별도 grayscale alpha channel로 저장하고 새 채널 또는 기존
  채널의 replace/add/subtract/intersect로 합성한 뒤, load 시 new/add/subtract/intersect와 invert를
  적용할 수 있다고 정의한다. 근거:
  https://helpx.adobe.com/ca/photoshop/using/saving-selections-alpha-channel-masks.html
- Quick Mask는 standard mode로 돌아온 뒤 Save Selection을 해야 permanent alpha channel이 된다.
  overlay color와 0-100% opacity는 표시만 바꾸며 protection 데이터에는 영향을 주지 않는다.
  근거: https://helpx.adobe.com/photoshop/using/create-temporary-quick-mask.html
- 고정 `RGB/Red/Green/Blue/Alpha` component/transparency row와 persistent saved-selection row를
  분리했다. 저장 채널은 document-sized Alpha8, stable `saved-selection-N` ID, 공백이 아닌
  case-insensitive unique name을 사용하며 근거 없는 이름 길이 상한은 두지 않는다.
- save의 new/replace/add/subtract/intersect와 load의 new/add/subtract/intersect+invert를 구현했다.
  고정 배열 `[0,64,128,255]`와 `[255,128,64,0]`의 exact 결과는 replace
  `[255,128,64,0]`, add `[255,128,128,255]`, subtract `[0,0,64,255]`, intersect
  `[0,64,64,0]`, inverted load `[255,191,127,0]`이다. 생성·갱신·로드와 ID serial까지
  Undo/Redo가 복원한다.
- `.tspaint`를 v4로 올려 saved-channel Alpha8 PNG를 checksum manifest에 포함하고 v1/v2/v3는
  빈 채널 목록으로 이행한다. reopen은 mask 존재/문서 크기/중복 ID·이름/최대 ID suffix 이상의
  serial을 대화상자 상태 변경 전에 검증한다. 손상 serial 입력 뒤 기존 채널·마스크·Undo가 그대로인
  원자성 회귀를 추가했다.
- `paint.selection.save_channel/load_channel` Action과 Channels row의 save/load 경로를 같은 core에
  연결했다. invalid/no-op 요청은 owner 또는 Undo를 부분 변경하지 않는다. focused 문서·autosave·채널
  회귀는 `22 passed`; fresh 감사는 unresolved `5549`, numeric-literal gap `4681`, stale
  `0/0/0/0`, defect `0`, test functions `464`이며 M41 신규 numeric-literal contract 2개는 pending 0이다.
- 독립 QA는 최종 P0/P1/P2 `0/0/0` PASS다. 지정 회귀 `111 passed`, 로컬 확대 회귀
  `123 passed`, fresh 감사 unresolved `5549`, numeric gap `4681`, defect `0`, test functions
  `464`, stale `0/0/0/0`, M41 numeric contract accepted/pending 0, `git diff --check`를 재현했다.
  QA가 발견한 P1 3건은 ① save Action 조건부 name/ID 검증이 owner 조회 뒤였던 문제,
  ② invalid v4 serial 실패 전에 output settings가 부분 변경되던 문제, ③ checksum-valid
  wrong-size Alpha8가 자동 scale되던 문제였으며 모두 원자적 거부로 수정·재검증했다.
- cross-document, filter, spot channel, PSD/TIFF extra-channel interop와 앱 전역 Quick Mask 표시
  preference는 후속 gap이다.

## 2026-08-05 M42 완료·독립 QA PASS: Saved Alpha Channel Lifecycle

- Adobe Channel Basics는 alpha channel 이름 변경, drag reorder, delete를 정의하고 alpha channel
  삭제는 이미지를 flatten하지 않는다고 명시한다. Duplicate Channels 문서는 독립 channel copy와
  새 이름을 정의한다. 근거:
  https://helpx.adobe.com/ca/photoshop/using/channel-basics.html
  https://helpx.adobe.com/sg/photoshop/using/duplicate-split-merge-channels.html
- stable ID rename, optional invert를 포함한 byte-independent exact Alpha8 duplicate, saved-row 범위의
  before/after reorder, delete를 Channels panel double-click/duplicate/up/down/delete control과
  `paint.selection.channel.rename/duplicate/reorder/delete` Action에 구현했다. 모든 변경은 한 번의
  Undo이며 `.tspaint` v4가 order/name/ID/bytes를 복원한다.
- duplicate는 saved list 끝에 append한다. 선택된 row 삭제 시 같은 index의 생존자, 없으면 이전
  생존자, 모두 없으면 RGB를 선택한다. 두 위치 규칙은 Tiger deterministic policy이며 Photoshop의
  same-document row 위치 parity라고 주장하지 않는다. raster/background alpha/active selection/fixed
  component channel은 불변이고 duplicate image는 write-detached copy다.
- invalid ID, blank/duplicate name, bool coercion, self reorder, unsupported placement, no-op은 owner/Undo
  전에 실패한다. 독립 QA는 최종 P0/P1/P2 `0/0/0` PASS를 판정했다. 지정 회귀 `112 passed`,
  saved-channel/Action 집중 회귀 `40 passed`, 최종 로컬 Painting 회귀 `126 passed`이다. QA가 발견한
  Channels panel 재구성 시 current RGB가 선택 saved-channel model을 덮어 lifecycle 버튼을 비활성화하던
  상태 결함은 selected-channel model을 authoritative하게 유지하도록 수정하고 UI signal, mutation당 Undo
  1회, delete fallback, no-op 원자성, v4 round-trip, channel invariant를 재검증했다. fresh 감사는 unresolved
  `5559`, numeric gap `4690`, stale `0/0/0/0`, defect `0`, test functions `467`이며 lifecycle numeric
  contract는 accepted/pending 0이다.
- direct channel paint/filter, display options, cross-document duplicate, spot channel, PSD/TIFF extra-channel
  exchange는 M42에 포함하지 않으며 lifecycle 구현만으로 해당 parity를 주장하지 않는다.

## 2026-08-05 M43 완료·독립 QA PASS: Saved Alpha Direct Edit & View

- Adobe Channel Basics의 white=full intensity, gray=lower intensity, black=remove 규칙과
  eye visibility/active edit 분리, Save Selections의 composite+alpha color overlay를 기준으로 삼았다.
  Qt `QImage::Format_Alpha8`의 8-bit alpha-only 계약을 실제 저장 형식으로 유지한다.
  근거: https://helpx.adobe.com/ca/photoshop/using/channel-basics.html,
  https://helpx.adobe.com/ca/photoshop/using/saving-selections-alpha-channel-masks.html,
  https://doc.qt.io/qt-6/qimage.html
- saved channel을 선택하면 mouse/tablet/Action stroke를 layer가 아니라 해당 Alpha8 mask로 보낸다.
  white/gray/black은 Qt `qGray` intensity를 기록하고 eraser는 black/0 removal로 처리한다. effective
  edit마다 Undo 1회, zero-coverage no-op은 Undo 0회이며 layer/selection/background/ordinary stroke는
  불변이다. 실제 mouse eraser가 stroke delete가 아니라 channel stroke를 내는 경로도 측정했다.
- saved row별 eye visibility와 RGB composite overlay/grayscale-alone view를 구현했다. v4 visibility는
  reopen 후 보존되고 unknown ID, bool coercion, RGB aggregate 불일치는 state mutation 전에 거부한다.
  근거 없는 clipboard auto-scale은 제거해 exact document-size image만 saved channel에 paste한다.
- direct-edit/view numeric literal 계약은 2행 hash
  `ee76bbcd3541a397d5d924465dcd91257d91ebdad1dbc5ffc388e1806e4efef4`로 승인했다.
  확장 로컬 Painting 회귀는 `128 passed`; fresh 감사는 unresolved `5553`, numeric gap `4684`,
  stale `0/0/0/0`, defect `0`, test functions `469`이며 M43 contract accepted/pending 0이다.
  custom overlay color/opacity, 여러 visible alpha의 색상 구분, filter, cross-document, spot,
  PSD/TIFF extra-channel exchange는 후속 gap이다.
- 독립 QA 최종 판정은 P0/P1/P2 `0/0/0`, 지정 `116 passed`, 별도 실제 QTabletEvent eraser
  probe PASS, 로컬 확장 `128 passed`다. QA가 최종 PASS 전에 재현한 P1 4건은 ① Action stroke가
  saved core를 우회해 ordinary stroke를 append하던 문제, ② `[]`/빈 문자열/0/null visibility가
  truthiness default로 object 검증을 통과하던 문제, ③ wrong-size saved paste 실패가 selected channel을
  부분 변경하던 문제, ④ 그 원자성 수정 중 fixed Red/Alpha 성공 paste가 target selection을 잃은 회귀다.
  모두 동일 core/strict preflight/성공 후 mutation으로 수정하고 재검증했다.

## 2026-08-05 M44 완료·독립 QA PASS: Channel Options

- Adobe Save Selections가 정의한 `Masked Areas`(masked=black, selected=white)와
  `Selected Areas`(masked=white, selected=black)를 채널별 표시·편집 경계에 구현했다. 내부
  Alpha8는 두 모드 모두 canonical selectedness를 보존한다. 채널별 `#RRGGBB` overlay color와
  정수 `0..100` opacity는 표시 영상만 바꾸며 저장 mask/protection에는 영향을 주지 않는다.
- Tiger eraser는 표시 모드와 무관하게 selectedness를 제거한다. 이는 명시적 Tiger 제품 정책이며
  Adobe eraser parity 주장이 아니다. rename/duplicate는 옵션을 그대로 상속하고 no-op은 Undo를
  만들지 않는다. UI 옵션 버튼과 `paint.selection.channel.options.set`은 동일 strict core를 사용한다.
- `.tspaint`를 v5로 올려 세 옵션 필드를 필수 저장한다. malformed v5는 dialog state mutation 전에
  거부하고 v4 이하는 `masked_areas`, `#ff0000`, 50%로 결정론적으로 migration한다.
- 고정 배열 `[0,64,128,255]`의 Selected Areas grayscale은 `[255,191,127,0]`, green 25% overlay의
  full-selected endpoint alpha는 `64`로 측정했다. 옵션 변경 전후 Alpha8 byte 동일성, black/white
  편집 반전, Undo/Redo, no-op, UI eligibility, Action 선검증, v5 round trip, corrupt-v5 원자성,
  v4 migration을 포함한 집중 회귀 `64 passed`다.
- numeric-literal 계약은 Channel Options 12행 hash
  `f7f450e49900c8d7b37042c11b10e2d554a657c519c7821214b22ff350d64e86`, M43 direct-edit
  잔여 1행 hash `cdfa03eb983eb458574649f4dce9d10ed9001e04805e44342e874bd020ae5ddb`,
  v1-v5 migration 5행 hash `d879f6e047e863120b92b1383858dfcce33e0126c84189700ce7ab73c7eb95cc`로
  분리했다. 독립 QA 최종 판정은 P0/P1/P2 `0/0/0` PASS이며 UI Design 제외 Painter 전체,
  architecture, debug-boundary 회귀는 `531 passed`다. red100+green50 순차 overlay의 실제 결과는
  `(127,128,0,255)`이고 grayscale-alone은 visible row order의 마지막 영상이 보이는 것을 별도 측정했다.
- QA가 발견한 P1 두 건은 ① 옵션을 바꾸지 않고 확인했을 때 core no-op ValueError가 UI 밖으로
  전파되던 문제, ② v5 `saved_selection_channels`의 `{}`/빈 문자열/0/null이 빈 list로 축소되어
  silent data loss가 생기던 문제다. UI no-op은 False·Undo 0으로 바꾸고, current v5는 channels object,
  saved-channel list, serial 존재를 asset 추출과 dialog mutation 전에 강제했다. missing serial도
  원자적으로 거부하며 v4 migration은 계속 default를 합성한다.
- v5 structure numeric 계약은 1행 hash
  `f6134e2bda5682d047c4cdd869bc6db036760ad6c85f1605f3c11ab37d070697`, writer default literal은
  1행 hash `95da8cb54a770498be9da20398b0e83e2ad9419dad4e93e8673e94221517bd55`다.
  fresh 감사는 unresolved `5555`, numeric gap `4684`, stale `0/0/0/0`, defect `0`, M44 pending `0`이다.
- 공식 근거: https://helpx.adobe.com/ca/photoshop/using/saving-selections-alpha-channel-masks.html,
  https://doc.qt.io/qt-6/qimage.html

## M45 구현 완료: Cross-document Saved Selection (독립 QA PASS)

- Adobe Save Selection의 다른 open image와 동일 pixel dimensions 조건을 그대로 경계로 삼았다.
  Tiger는 visible/open standalone Painter 문서만 열거하며, source와 destination의 `(width, height)`가
  정확히 같을 때만 canonical Alpha8 mask를 복사한다. resize/resample은 하지 않는다.
- 각 open document는 opaque runtime ID를 갖는다. `paint.documents.inspect`와 `paint.state`가 같은 ID를
  노출하고, 저장은 ID를 유지하며 성공한 문서 열기는 새 ID를 발급한다. 닫혔거나 숨겨졌거나 교체된
  문서의 stale ID, 자기 문서 ID, 잘못된 ID 형식은 mutation 전에 거부한다. Qt의 공식
  `QApplication.topLevelWidgets()`가 live top-level enumeration의 근거다.
- UI는 Save Selection의 Destination Document와 Load Selection의 Source Channel chooser를 제공한다.
  Actions는 `paint.selection.save_channel_to_document`와
  `paint.selection.load_channel_from_document`다. conditional name/channel 입력은 owner resolution 전에
  strict 검증한다.
- cross-save의 Undo owner는 destination만, cross-load의 Undo owner는 active destination만이다.
  source Undo, source selection/channel bytes, layer/background/stroke state는 바뀌지 않는다. load는
  destination의 selected channel도 바꾸지 않는다. dimension mismatch, missing channel, no-op replace/load는
  Undo 0·부분 mutation 0으로 실패한다.
- Adobe가 함께 설명하는 “new image 생성 destination”은 아직 구현·주장하지 않는다. M45의 범위는
  이미 열려 있는 Painter 문서 간 전송뿐이다.
- 회귀는 identity save/open lifetime, closed-window exclusion, inspect/action-state 대응, UI chooser,
  new/replace/load, exact mask bytes, metadata preservation, mismatch/same/no-op atomicity, Undo/Redo를 고정한다.
  감사 원장은 positive raster input 1행
  `7240a9a98636f14783a27466688acafd0d061ab25fc5599ace5670530c8cb358`와 strict two-axis structure 5행
  `428d4cb3055d0bbf45ed42166704ece8505130045aca19e6ea0572a249f27926`를 승인한다. Float와 numeric
  string은 더 이상 정수로 절삭·변환하지 않는다. chooser identity/tuple 10행은
  `62fab36bfd7a828401dbb53c08de7cb7dc3b25f24d1eb49b7e1e64f66ef20b9f`로 별도 승인한다.
- 공식 근거: https://helpx.adobe.com/ca/photoshop/using/saving-selections-alpha-channel-masks.html,
  https://doc.qt.io/qt-6/qapplication.html#topLevelWidgets,
  https://doc.qt.io/qt-6/qimage.html
- 독립 QA 1차는 P1 4건/P2 3건으로 FAIL했다. non-standalone dialog 열거, closed active Action
  owner의 destination mutation, chooser 중 닫힌 object를 그대로 쓰는 TOCTOU, wrong-size mask의
  SmoothTransformation 보간, 마지막 source close 뒤 stale Load button, float/string dimension coercion,
  자동 검증보다 앞선 ledger 문구가 대상이었다.
- 수정 후 standalone+visible membership과 양쪽 endpoint를 transfer 시점에 재검증하고, chooser는 object가
  아니라 runtime ID를 다시 resolve한다. selection mask는 문서와 정확히 같은 크기만 byte-preserving 복사하며,
  show/hide가 peer eligibility를 갱신하고 dimension은 `operator.index`가 허용하는 strict integer만 받는다.
- 재-QA 최종 판정은 P0/P1/P2 `0/0/0` PASS다. focused `63`, cross-only `7`, architecture/debug `5`,
  audit exit 0, diff-check PASS다. final fresh audit는 unresolved `5557`, numeric literal gap `4684`,
  defect `0`, stale ledger `0/0/0/0`, M45 pending `0`이다. UI Design 제외 Painting 전체와
  architecture/debug-boundary 회귀는 `538 passed`, 의도된 corrupt-EXIF Pillow warning 1건이다.

## M46 구현 완료: Saved Channel File Exchange (독립 QA PASS)

> 아래 초기 조사 문구는 이 구현 결과로 대체한다. M46은 PSD/TIFF에 한해 구현 완료되었고,
> 독립 QA 최종 판정은 P0/P1/P2 `0/0/0` PASS다.

- PSD 교환은 8-bit RGB 문서로 제한한다. 다른 PSD channel depth는 양자화하지 않고 문서 변경
  전에 거부한다. PSD는 merged RGBA 투명도와 이름 있는 extra alpha channel을 저장한다. AlphaIdentifiers와
  Unicode alpha name을 기록하며, 가져올 때 이름과 Alpha8 byte를 정확히 복구한다. PSD header의
  공식 최대 56 channel을 강제하므로 RGB 3 + merged transparency 1 이후 saved channel은 최대
  52개다. 표시 모드·overlay 색·opacity는 PSD 표준 보존 항목으로 주장하지 않으며 가져온 채널은
  Tiger 기본 표시 옵션을 명시적으로 사용한다.
- TIFF는 uncompressed chunky RGB, unassociated alpha `ExtraSamples=2`, saved-selection plane
  `ExtraSamples=0`으로 내보낸다. 8/16-bit 모두 Alpha8 byte를 정확히 왕복한다. 16-bit는
  `value8 * 257`만 허용하고 257로 나누어떨어지지 않는 외부 sample은 양자화하지 않고 거부한다.
  필수 baseline/ExtraSamples tag의 TIFF 6.0 field type을 검사하고 duplicate IFD tag도 거부한다.
  TIFF 6.0에는 표준 channel-name 필드가 없으므로 이름 보존을 주장하지 않고 `Alpha 1...`을
  합성하며 `names_preserved=false`를 보고한다.
- Channels 패널과 `paint.selection.channels.import_file`은 동일 pixel size의 PSD/TIFF만 받는다.
  전체 channel 집합의 크기·이름·mask를 먼저 검증한 뒤 정확히 한 번 Undo를 만들고 반영한다.
  빈 source, 크기 불일치, 중복 이름, 잘못된 정밀도/컨테이너/확장자/경로는 부분 변경 없이
  실패한다. 가져온 채널은 숨김 상태이고 첫 채널이 선택되며 layer/background/stroke/active
  selection은 바뀌지 않는다.
- PNG/JPEG/WebP는 saved-channel 누락을 preflight/report에 명시한다. PDF/raw/PSB와 임의의
  비지원 flat export 경고는 결과 보고서뿐 아니라 완료 UI에도 표시한다. PSD export 보고서는
  `display_options_preserved=false`와 `source_display_options`를 분리해 source metadata를 on-disk
  보존으로 오해하지 않게 한다. PDF/raw/PSB와 임의의 compressed/tiled TIFF는 M46 지원으로
  주장하지 않는다. 집중 회귀 78개가 통과했고 M46 숫자
  결정은 PSD input 1행, TIFF input 6행, PSD structure 7행
  (`b5497305d615026e014342cb0d69a74951477f764d5874d6feb401a675b54184`),
  TIFF structure 82행
  (`2ed03f2ef01445559d30f1744a1040dc7033eded6f00c5e947f6135baee709bb`),
  TIFF inspection 2행, import structure 2행의 정확 inventory로 동결했다.
- 독립 QA는 초기 구현에서 PSD document Action의 PIL/bytes JSON 직렬화 실패, 16-bit PSD
  alpha의 silent quantization, flat export UI의 채널 누락 경고 미표시, PSD display-option
  보존 보고의 모호성, TIFF required-tag field type 미검증과 duplicate IFD tag 수용, 그리고
  milestone 지문 불일치를 발견했다. 모두 수정·회귀화한 뒤 재QA P0/P1/P2 `0/0/0` PASS를 받았다.
- 최종 UI Design 제외 Painting 61개 test file과 architecture/debug-boundary 전역 회귀는
  `548 passed`, 의도된 corrupt-EXIF Pillow warning 1건이다. fresh 감사는 unresolved `5560`,
  numeric literal gap `4687`, defect `0`, 네 ledger stale `0/0/0/0`이며 M46 계약은 모두 accepted다.
- 공식 근거: https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/,
  https://www.itu.int/itudoc/itu-t/com16/tiff-fx/docs/tiff6.pdf

- Adobe가 alpha-preserving으로 열거한 Photoshop/PDF/TIFF/PSB/raw를 포맷별
  공식 규격과 실제 round trip으로 검증한다. PNG/JPEG 또는 `.tspaint` 성공을 대체 증거로 쓰지 않는다.
- 공통 근거: https://helpx.adobe.com/ca/photoshop/using/saving-selections-alpha-channel-masks.html,
  https://helpx.adobe.com/ca/photoshop/using/channel-basics.html

## M47 구현: Capture GIF Painting burn-in canonical renderer

- 전수감사에서 `compose_pil_frame_with_overlays`가 Painter의 canonical QImage renderer와
  별개인 Pillow textured-brush 구현을 사용하며 pressure/load/dynamics/material 정보를 버리는
  것을 확인했다. 이 경로는 Capture GIF 저장에 실제로 사용되므로 단순 미사용 helper가 아니었다.
- Capture GIF burn-in을 `compose_pil_paint_overlays`로 통일했다. 동일한 `Stroke` 전체와 layer
  compositor를 사용하며 width scale만 copy에 적용한다. 별도 Pillow textured/dashed/color
  renderer 약 750줄은 삭제했다.
- 실제 material/bristle stroke에서 burn-in byte가 canonical overlay와 정확히 같고,
  pressure/load 변경이 출력 byte를 바꾸는 회귀를 추가했다. 실제 GifEditorWindow의
  scale/time 경로까지 고정한 관련 회귀는 `30 passed`다.
- 이 삭제와 원장 재동결 후 fresh 감사의 numeric literal은 `6739`→`6451`, numeric
  gap은 `4687`→`4481`, 전체 unresolved는 `5560`→`5293`으로 감소했다. 삭제 영향
  원장은 optional preview 1행 `7f383bc6...`, 8-bit channel 44행 `36a249bb...`로
  재동결한다.
- Capture GIF가 현재 저장하는 것은 stroke overlay뿐이다. M47은 기존 GIF 경로에
  존재하지 않는 layer mask 보존을 주장하지 않는다.
- 이는 남은 canonical `_paint_textured_stroke` 계수를 자연 매체 parity로 승인한 것이 아니다.
  해당 authored 계수는 다음 전수감사 배치에서 계속 미해결로 둔다.
- 공식 근거: https://docs.krita.org/en/reference_manual/brushes/brush_engines/pixel_brush_engine.html,
  https://product.corel.com/help/Painter/540111162/Corel-Painter-en/Corel-Painter-Thick-Paint.html

## M48 구현: paint load 누적 문서 픽셀 이동거리 통일

- 브리슬과 재질 경로를 대조해 실제 결함 두 건을 확인했다.
  `bristle_lane_paths`는 이미 픽셀로 변환한 좌표 차이에 캔버스 폭·높이를 다시
  곱했고, material raster는 이동거리 대신 `sample_offset + index`를 `64`로
  나누어 load를 소모했다. 후자는 `load_dryout_px`도 무시했다.
- `depleted_load_curve`를 공통 계산으로 추가했다. 정규화 좌표 차이를 문서 픽셀로
  정확히 한 번 변환하고, `brush_travel_offset_px`를 이어받아 live 2점 segment와
  최종 whole stroke가 동일한 누적 이동거리를 사용한다.
- 독립 QA에서 points 4개에 sensor/load 값 2개처럼 유효한 sparse curve를 넣으면
  live segment가 raw 배열을 먼저 잘라 final 보간 결과와 달라지는 P1을 재현했다.
  전체 point count로 pressure/load/tilt/rotation 곡선을 먼저 정규화한 뒤 segment를
  자르도록 교정했고, exact-binary adversarial fixture의 live/full delta도 `0`이다.
- 공식 의미는 Krita의 spacing/dab/sensor 설명과 Corel Thick Paint의 finite Paint
  Load·Resaturation·bristle density·Plow 설명에서 가져왔다. 정확한 계수는 외부
  제품이나 물리 모델에서 왔다고 주장하지 않고 Tiger authored response로 제한한다.
- `tools/measure_painter_brush_response.py`를 추가해 실제 수치를 저장했다. exact binary
  fixture에서 coarse/dense 최종 load는 모두 `0.4375`, 이벤트 밀도 차이와
  live/full 차이는 모두 `0`이다. 압력 증가 시 평균 dab size `6.88`→`18.36`, alpha
  `0.40`→`0.925`, spacing 변화 시 dab 수 `33`→`9`, pressure/load 증가 시 material
  height 합 `3.77598`→`709.00659`였고 replay SHA-256도 반복 실행에서 일치했다.
  재생성 보고서는 `debugCapture/painter/evidence_audit/m48_brush_response.json`이다.
- 새 exact 원장 `brush_load_cumulative_travel_contract` 4행은
  `0a29bdc43c4df1fd70535b12c62666adcb69b47422e2b1d7c12b77135aaa5827`로
  동결했다. 나머지 bristle/material/legacy authored 계수는 이 교정으로 승인하지
  않으며 후속 측정 배치에 남긴다.
- 집중 회귀는 brush response measurement를 포함해 `47 passed`다. fresh 감사는
  test functions `492`, numeric literal `6448`, numeric gap `4480`, unresolved
  `5286`, defect/pending/stale `0`이다.
- 공식 근거:
  https://docs.krita.org/en/reference_manual/brushes/brush_engines/pixel_brush_engine.html,
  https://product.corel.com/help/Painter/540219480/Main/EN/Win-Documentation/Corel-Painter-Thick-Paint-Brush-controls.html,
  https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html

## M49 구현: pressure 구간과 pickup 0의 정확한 끝점

- Qt `QTabletEvent.pressure()`의 공식 입력 의미는 `0.0`이 비접촉, `1.0`이
  장치 최대 압력이다. Tiger 저장/UI 계약은 정수 percent `0..100`이므로 보정
  구간도 반드시 그 안의 비퇴화 구간이어야 한다.
- 기존 `normalize_brush_dynamics`는 `pressure_min=100`, `pressure_max=100`을
  `100/101`로 만들었다. 이는 선언한 percent 범위를 벗어나고 정규화 high가
  `1.0`을 초과하는 실제 모순이다. 이제 min은 `0..99`, max는
  `min+1..100`에 머문다. collapsed `100/100`은 `99/100`, reversed `80/20`은
  `80/81`이며 raw `0.99`와 `1.0`이 각각 정확히 `0`과 `1`로 매핑된다.
- Pickup/Smudge 경로에는 사용자가 0을 지정해도 `max(0.08, pickup/100)`으로
  최소 8%를 칠하는 숨은 바닥값이 있었다. 이를 제거해 0%를 정확한 무투입
  끝점으로 만들었다. Krita Color Smudge 문서는 Color Rate를 전경색 투입량으로
  정의하고 0%에서는 색 기여가 없다고 설명한다. 이는 방향 의미의 근거이며
  Krita 픽셀 parity 주장은 아니다.
- 실제 QImage 측정에서 Pickup 0, Smudge Pickup 0, 같은 배경의 zero-flow 기준은
  모두 SHA-256
  `252cf4fbc28af867bbe5072b38805ff3ed1bf234ba23675c2a1212adeca44e29`로
  byte-identical이다. pressure 범위와 끝점도 동일 측정 도구가 exact assertion으로
  검사한다. 재생성 보고서는
  `debugCapture/painter/evidence_audit/m49_brush_response.json`이다.
- exact 원장 `brush_pressure_window_contract` 2행은
  `6fdd3cad77af4cba9e01dbbd7096623f56560df7d7b8e4e2afa6edcd2be2d473`로
  동결했다. 이 교정은 압력 감각, 장치별 calibration, smudge 물성이나 남은
  brush dynamics 계수를 승인하지 않는다.
- 공식 근거:
  https://doc.qt.io/qtforpython-6/PySide6/QtGui/QTabletEvent.html,
  https://docs.krita.org/en/reference_manual/brushes/brush_engines/color_smudge_engine.html
- 최종 집중 Painting 및 architecture/debug-boundary 회귀는 `40 passed`다.
  fresh 감사는 test functions `494`, numeric literal `6450`, numeric gap
  `4483`, unresolved `5286`, defect/stale/pending `0`이다.
- 독립 QA는 생성 보고서의 `official_sources`에 Qt URL이 빠진 P2 한 건을
  찾았다. URL을 측정 도구에 추가하고 exact 테스트로 고정한 뒤 재검증은
  P0/P1/P2 `0/0/0` PASS다.

## M50 구현: 브러시 응답 방정식과 제한된 스머지 작업량

- 동적 dab 렌더러에서 공식 문서나 측정 근거가 없던 숨은 수치를 제거했다.
  대상은 `0.7 px` 간격 하한, `0.5/4 px` 사설 폭 fallback, `8%` 크기 하한,
  `18% + 82% * pressure` 크기 응답, `25% + 75% * pressure` 알파 응답,
  `10%` texture-scale 하한, buildup 나눗수 `34`, scatter 지수 `0.55`,
  stabilization의 `0.08/0.9`, 임의의 5점 기본 pressure curve, sine noise
  상수다. 이 값들은 플랫폼·포맷·제품 문서·실측 어느 쪽에도 근거가 없었다.
- 폭·간격·roundness는 Painting 공용 brush domain을 사용한다. 누락되거나
  잘못된 폭은 명명된 기본값 `6 px`, 유효한 0은 선언된 최솟값 `1 px`가 된다.
  간격은 정확히 `width * spacing_percent / 100`이므로 선언된 최소 조합은
  dab plan에 `0.01 px`로 도달한다. roundness는 공용 `10..100%` 범위다.
- 기본 pressure curve는 `[0,0]..[1,1]` 항등선이다. 크기는
  `width * max(0, pressure * (1 + size_jitter + tilt))`, 알파는 flow·texture·
  pressure의 직접 곱이다. 따라서 pressure 0은 정확히 크기/알파 0이고,
  size jitter 100%도 숨은 8% 바닥을 남기지 않는다. stabilization 100%는
  `alpha=0`의 정확한 끝점이고, buildup 100%는 scatter 8개를 16개로 만든다.
- scatter 반경은 면적 균일 원판 변환인 `sqrt(U)`를 쓴다. noise 입력은
  unsigned 64-bit seed/index/channel을 `TigerDab`으로 domain separation한
  BLAKE2b digest다. 같은 입력의 재현성만 주장하며 보안 난수나 타 엔진의
  난수열 parity는 주장하지 않는다.
- Krita가 Dulling의 brush-size 비율로 문서화한 Smudge Radius에서 숨은
  `32 px` 반경 절단을 제거했다. `32 px` 이하는 원 안의 모든 유효 픽셀을
  열거하고, 그보다 큰 반경은 전체 반경에 걸친 결정적 `17 x 17`, 최대
  `289`개 후보 grid를 사용한다. 큰 반경의 결과를 정확한 원판 평균이나
  타 제품 픽셀 parity로 주장하지 않는 명시적 Tiger 작업량 정책이다.
- `tools/measure_painter_brush_response.py`의 M50 보고서는 21개 exact check를
  모두 통과한다. 주요 측정값은 최소 간격 `0.01`, full-jitter 최소 크기
  `0.001325411145726152`, pressure 0의 크기/알파 `0`, buildup `8 -> 16`,
  stabilization `[[0,0],[0,0],[0.4,0.8]]`, texture scale 0의 alpha 종류 1개,
  큰 스머지 sample `197/289`, blue 응답 `36 -> 197`, 동일 replay SHA-256
  `ee20cfc7d60b02eec023db681cde895f9cd34e36bd40a9fee40aa87dd8aecd1f`다.
- 공식 근거는 Qt QTabletEvent/QImage, Krita Pixel Brush·Color Smudge·Texture,
  RFC 7693 BLAKE2다. 이 근거는 채널 범위·control 의미·알고리즘만 뒷받침하며
  Tiger의 감각 계수, 물리 매체, 장치 지연, 경쟁 제품 결과를 승인하지 않는다.
- 최종 회귀는 서로 무관한 Qt 모듈이 QApplication/native graphics 수명을
  공유하지 않도록 두 프로세스로 분리해 `62 passed`와 `60 passed`다. brush
  domain/dynamics/measurement, engine-v2, live/commit/export parity, 문서 I/O,
  media/material/Action, 감사 분류기, architecture/debugCapture guard를 포함한다.
  fresh 감사는 test function `498`, numeric literal `6464`, routed scanner gap
  `5067`, numeric gap `4499`, unresolved `5259`, unreviewed defect `0`이다.
  M50 계약은 모두 accepted이며 M50 stale/pending은 `0`이고, 이후 마일스톤의
  별도 계약만 전역 pending으로 남는다.
- 독립 QA는 BLAKE2b를 별도 재계산하고 scatter 20,000개의 평균
  `r^2=0.4995349381`, 반경 `0,1,7,31,32`의 brute-force 원판 일치,
  `33,64,100,1000`의 최대 289개 제한, malformed/zero 끝점을 직접 확인했다.
  P0/P1/P2는 `0/0/0`이다. 이후 발견한 감사 분류 회귀도 별도 delta QA했다.
  dynamic `QColor.setAlphaF`는 Qt normalized-color 계약, 같은 함수의 pressure
  clamp는 generic unit-domain으로 분리되고 Qt/smudge 근거를 상속하지 않는다.
  최종 Qt/smudge 원장은 각각 `3/15`행이며 delta QA도 P0/P1/P2 `0/0/0` PASS다.

## M51 구현 진행: 유지 브러시의 공개 제어와 결정적 경로 계약

- 기존 감사기는 `max/min` 형태를 중심으로 세어 렌더러 내부의 단순 곱셈 계수를
  누락했다. AST 전수 라우팅을 추가한 결과 `_paint_textured_stroke` 계열에서 처음
  222개 리터럴 행이 드러났다. 독립 QA가 1픽셀 oil dab 굵기 바닥값과 3행짜리
  scumble/stipple 비공개 cadence를 추가로 찾아 제거해 최종 승인 인벤토리는 219행이다.
  과거의 91행, 125행, 수정 전 222행 추정은 폐기한다.
- 디자이너 프로필에서 비공개 `body`, `alpha`, `spacing` 배율을 제거했다. 크기,
  불투명도, 간격, 경도, 각도, 원형도는 공개 브러시 값만 사용하며 37개 유지
  텍스처 스타일 모두 먼저 같은 공개 팁 외곽을 렌더한다.
- 근거 없던 0.7/0.8/1/2/2.5/3/4/5/7/8픽셀 바닥값과 1픽셀 샘플 간격을
  제거했다. Qt가 dash 값을 펜 폭 단위로 해석하는데 다시 문서 폭을 곱하던
  사용자 dash 배열은 Qt `DashLine`으로 교체했다. 유지 스타일의 샘플 간격은
  공개된 `width * spacing_percent / 100`에서 시작한다.
- 새 누적거리 샘플러는 collinear 점 분할에 불변이고 양 끝점을 보존한다. 요청량이
  M50에서 측정한 8,192 예산을 넘으면 꼬리를 자르지 않고 전 경로를 균일 재표본화하며
  요청/유효 간격, 예상/실제 샘플 수, 예산, 열화 여부를 보고한다.
- sine 의사난수를 제거하고 RFC 7693 BLAKE2b 기반 uint64 seed/index/channel과
  안정적인 style seed를 사용한다. 이는 Tiger 재현성 계약일 뿐 물리 매체나 타사
  브러시 엔진의 난수·픽셀 일치를 주장하지 않는다.
- 레거시 dirty 영역의 `max(8, width*1.75)` 추정은 scatter/회전/offset 지원 범위를
  증명하지 못하므로 제거했다. 각 스타일의 정확한 support bound가 제공되기 전에는
  전체 위젯 갱신으로 누락 픽셀을 방지한다.
- PNG 출력은 preview/layer와 같은 premultiplied ARGB32에서 렌더한다. 실제 측정에서
  PNG와 PIL overlay RGBA는 정확히 같고, premultiplied preview와 PNG decode 사이는
  최대 1 LSB 차이다. byte-identical이라고 과장하지 않는다.
- `tools/measure_painter_legacy_brush.py`가 생성하는
  `debugCapture/painter/evidence_audit/m51_legacy_brush.json`은 현재 22/22를 통과한다.
  37개 유지 스타일과 21개 디자이너 프로필의 비어 있지 않은 서로 다른 해시,
  반복 결정성, 공개 제어 반응, 전 경로 예산 처리, 출력 parity를 측정한다. 시각 품질
  인증, 물리 매체, 타사 픽셀 parity는 명시적으로 주장하지 않는다.
- 독립 M51 QA는 P0/P1/P2 `0/0/0`으로 PASS했다. focused/guard 52/52,
  측정 22/22를 통과했고 geometry 4, geometry literal 25, preset/profile 41,
  renderer literal 219행이 정확히 승인됐다. M51 literal 원장은 stale/pending이 없다.
- 공식 근거:
  https://doc.qt.io/qt-6/qpen.html,
  https://doc.qt.io/qt-6/qpainter.html,
  https://docs.krita.org/en/reference_manual/brushes/brush_settings/options.html,
  https://helpx.adobe.com/photoshop/desktop/apply-painting-techniques/brushes-presets/create-brush-set-painting-options.html,
  https://product.corel.com/help/Painter/540219480/Main/EN/Win-Documentation/Corel-Painter-Spacing-controls.html,
  https://www.rfc-editor.org/rfc/rfc7693

## M52 구현 완료: Engine v2 브리슬·재질 근거 계약

- `painter_brush_engine_v2.py`, `painter_material_paint.py`와 live/commit/
  clipboard 구성 행을 AST 리터럴까지 전수 라우팅했다. 승인 대상은 브리슬 숫자
  23행·리터럴 129행, 재질 숫자 51행·리터럴 257행이다. 브리슬 프로필에서
  렌더러가 읽지 않던 옛 `body_width`/`body_alpha` 필드는 승인 전에 삭제했다.
- Corel 공식 문서는 브리슬 수/밀도, 폭 연동, tilt Spread, 유한 Paint Load,
  Resaturation, Plow를 설명하고 Adobe는 Mixer Brush Wet/Load/Mix 끝점을 설명한다.
  어느 문서도 Tiger 픽셀 계수를 제공하지 않는다. 따라서 두 모델 계약은 계수를
  Tiger 아트 디렉션으로 명시하고 실물 브리슬·유변학·시각 품질·타사 픽셀 일치를
  주장하지 않는다.
- sine 기반 변이를 제거했다. 브리슬은 공용 BLAKE2b unit, dry/scumble 재질 grain은
  고정 uint64 정수 혼합을 사용한다. 자동 브리슬의 숨은 5..36/7..36 범위를 없애고
  공개 폭, Tiger 자동 밀도 계수, 구조적 최소 1개와 공개 최대 64개만 사용한다.
  명시적 64개 요청은 실제 64개 lane을 만든다.
- 0.25/0.35/0.55/0.65/0.8/0.85/1픽셀 detail 바닥값, 압력과 무관한 18% 폭·48%
  alpha, 재질 90% alpha 덮어쓰기, knife 전용 cadence를 제거했다. v2 색상은 먼저
  공개 크기/불투명도/간격/경도/각도/원형도 팁을 렌더하고 스타일 프로필은 내부
  표현만 더한다. 13개 스타일 RGBA 해시는 모두 서로 다르다.
- 압력 0 또는 point Load 0은 13개 v2 스타일 모두에서 색상과 재질
  coverage/height/excavation에 정확한 무변화다. 독립 QA가 찾은 stipple/knife
  우회도 공용 pressure×load gate와 전 스타일 회귀로 막았다. Corel이 Paint Load
  0의 무도포 scrape/drag를 명시하므로 기존 0.04
  최소 load를 제거했다. 재질의 0.04/0.06/0.08 deposit, roughness 0.04,
  deposition 0.0001, sine grain, plateau blur 0.55픽셀 바닥값도 제거했다.
- OpenCV가 없을 때 blur는 8비트 Pillow 임시 이미지가 아니라 결정적 float32
  separable Gaussian을 사용해 실제 측정에서 1/1024 입력 신호를 보존한다.
- `tools/measure_painter_bristle_material.py`의 현재 결과는 27/27다. 13개 색상
  스타일과 13개 재질 height/roughness의 구별, 반복 결정성, whole/incremental,
  압력/tilt/밀도/공개 팁, 64 lane, zero endpoint, preview/PNG 1 LSB, 재질 채널,
  load/roughness 반응, float blur를 검사한다. 고정 Tiger 회귀 corpus일 뿐 작품
  품질 인증은 아니다.
- 수정 후 Painting 전체 회귀 584/584와 architecture/debugCapture guard 5/5가
  통과했다. 별도 QA 에이전트는 초기 zero-pressure/load 우회를 P1으로 발견했고,
  수정판에서 색상·재질 13스타일×3 endpoint 모드의 78개 적대적 조합 실패 0,
  focused/guard 66/66, 측정 27/27, P0/P1/P2 `0/0/0`으로 최종 PASS했다.
- 공식 근거:
  https://doc.qt.io/qtforpython-6/PySide6/QtGui/QTabletEvent.html,
  https://doc.qt.io/qt-6/qimage.html,
  https://product.corel.com/help/Painter/540219480/Main/EN/Win-Documentation/Corel-Painter-Bristle-controls.html,
  https://product.corel.com/help/Painter/540219480/Main/EN/Win-Documentation/Corel-Painter-Thick-Paint-Brush-controls.html,
  https://helpx.adobe.com/photoshop/using/painting-mixer-brush.html,
  https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html,
  https://www.rfc-editor.org/rfc/rfc7693

## M53 구현 완료: Painting 저장·복구·파일 교환 근거 계약 (독립 QA PASS)

- 범위는 Painting 전용이다. UI Design은 계속 제외한다. 조사 대상은
  `painter_document_io.py`, `painter_autosave.py`, `painter_file_exchange.py`,
  `painter_output.py`와 표시 전용 복구 대화상자다. 내부 재열기 성공만으로 외부
  프로그램 호환성이나 인쇄 품질을 인증하지 않는다.
- PNG 16비트→8비트 변환은 하위 바이트를 버리는 시프트에서 PNG 제3판 13.12의
  최근접 선형 변환 `(sample * 255 + 32767) // 65535`로 교정했다. 실제 측정은
  uint16 전체 65,536개 입력과 실제 PNG8 출력 픽셀을 검사한다.
- v5 `.tspaint`는 `document.json` 정확히 1개, list 형식 manifest, object 행,
  manifest/ZIP entry 중복 금지, 문자열 entry 이름, bool이 아닌 정수
  version/serial/size, 정확한 바이트 크기와 소문자 SHA-256을 요구한다. 모든
  archive payload를 검증한 뒤 추출하며, 자동 생성한 추출 디렉터리는 후속 실패 시
  제거한다. 손상 ZIP과 I/O 실패는 `PainterDocumentError` 경계로 통일했다.
- Recovery v2의 동일 내용 생략은 self-hash가 맞는 typed manifest, session/file key,
  내용 hash, 원본 경로, 저장된 archive 전체 SHA-256, ZIP CRC, JSON, document schema가
  모두 맞을 때만 허용한다. 구조상 유효한
  ZIP이라도 사후 변경되면 복구 목록에서 제외하고 다음 저장에서 다시 쓴다. manifest는
  같은 디렉터리의 무작위 임시 파일과 `os.replace`로 교체하며, manifest가 다른 복구
  경로로 우회하도록 만들 수 없다. 구 v1은 identity/path 검사와 실제 `.tspaint`
  strict load를 통과한 경우에만 보이며, 신뢰할 수 없는 옛 source path는 비우고 다음
  저장에서 v2로 올린다. 기본 보존 12개는 Tiger 정책일 뿐 보편적 복구
  용량·내구성·전원 차단 원자성을 주장하지 않는다.
- 출력 설정은 NaN/Infinity와 문자열 boolean을 거부·정규화하고 현재 구현 범위를
  sRGB로 명시한다. ISO A 계열, Manga B5 182×257 mm·600 PPI 예시와 Tiger가 정한
  postcard/square/bleed/safe margin/large-format 시작값을 구분했다. 실제 인쇄소와
  출판사 요구사항이 우선이며 보편적 품질이나 bleed 값을 주장하지 않는다.
- `tools/measure_painter_persistence_exchange.py`는
  `debugCapture/painter/evidence_audit/m53_persistence_exchange.json`을 재생성한다.
  최종 18/18 측정과 집중 구현·계약 테스트 124/124, UI Design/soak 제외 Painting
  전체 회귀 609/609, architecture/debug/evidence 묶음 37/37이 통과했다.
- M53 승인 inventory는 output/archive numeric 32, flat export 15, print output 31,
  PSD 4, recovery dialog 9, recovery snapshot 14, TIFF writer 29, `.tspaint` archive
  13, uint16→uint8 2행이다. 새 감사에서 stale literal과 unreviewed defect는 0이다.
- 별도 QA는 종료 전 손상 manifest가 전체 복구 목록·autosave를 깨뜨리는 P1,
  session id와 파일 key 불일치로 Discard가 실패하는 P2, 같은 v1 schema에 새 필드를
  필수화해 기존 복구를 숨기는 P1을 발견했다. typed/self-hashed manifest, exact key
  pairing, v1 안전 목록·source path 비신뢰·v2 upgrade로 교정했고 적대 회귀를 추가했다.
  수정 후 독립 QA는 focused/evidence/guard 129/129, 측정 18/18, 별도 Painting
  563/563을 통과했고 최종 P0/P1/P2는 `0/0/0`이다. Windows manifest `os.replace`
  access failure 1회는 즉시 측정 5회와 combined 재실행에서 재현되지 않았고, writer
  오류 노출·재시도 계약 안에 남겼다. 전원 차단 원자성은 주장하지 않는다.
- 공식 근거:
  https://www.w3.org/TR/png-3/,
  https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/,
  https://printtechnologies.org/standards/files/tiff-v6.pdf,
  https://www.color.org/icc32.pdf,
  https://www.iso.org/standard/36631.html,
  https://helpx.adobe.com/photoshop/desktop/crop-resize-transform/resize-adjust-resolution/resolution-specs-for-printing-images.html,
  https://tips.clip-studio.com/en-us/articles/1019,
  https://docs.python.org/3/library/zipfile.html,
  https://docs.python.org/3/library/tempfile.html,
  https://docs.python.org/3/library/os.html#os.replace,
  https://www.rfc-editor.org/rfc/rfc7693

## M54 구현 완료: Painting Action 스키마와 PBR 미리보기 자원 근거 계약 (독립 QA PASS)

- 범위는 Painting 전용이며 UI Design은 제외한다. 남아 있던 일반 Action 스키마
  6개 행을 숫자 색상 3요소, 저장 선택 오버레이 불투명도, PBR 미리보기 자원
  계약으로 분리했다. 각 스키마는 동일한 런타임 검증기와 정확한 감사 원장으로
  연결했다.
- `paint.color.numeric.set`은 순서가 있는 숫자 3개만 받는다. 네 번째 값을 조용히
  버리던 동작을 제거했고 boolean, NaN, Infinity도 거부한다. JSON Schema는
  `minItems`/`maxItems`를 배열 길이 계약으로 정의하고 Qt QColor는 RGB를 r/g/b,
  HSV를 h/s/v로 정의한다.
- 저장 선택 채널의 `overlay_opacity_percent`는 Action과 코어 모두 boolean이 아닌
  정수 `0..100`으로 통일했다. Adobe Channel Options 문서에 따라 이 색상과
  불투명도는 마스크 표시만 바꾸며 보호 내용은 바꾸지 않는다. 분수, 문자열,
  boolean, 범위 밖 정수는 소유자 조회나 변경 전에 실패한다.
- 기존 PBR 미리보기 최대 `8192 px`는 실측 근거가 없었다. 실제 CPU 생성기를
  `64/256/512/1024` 정사각형으로 측정한 결과 14개 맵 참조는 12개 고유 배열이며
  고유 보유량은 정확히 픽셀당 80바이트다. `1024²`는 `83,886,080`바이트,
  `2048²` 투영은 `335,544,320`바이트, 제거한 `8192²` 투영은
  `5,368,709,120`바이트다.
- 따라서 Tiger 운영 정책으로 고유 보유 배열 예산 `128 MiB`, Action 범위
  `64..1024 px`, 기본값 `512 px`를 선언했다. 이는 선택적 PBR 미리보기 전용이며
  PBR 내보내기 크기를 제한하지 않는다. 관측 시간과 Python peak는 보고만 하고
  합격 기준으로 사용하지 않는다. 보편적 메모리/지연 안전, GPU 동등성, 시각 품질,
  타 제품 동등성은 주장하지 않는다.
- `tools/measure_painter_action_schema_resources.py`는 15/15, 초기 관련 회귀는
  62/62를 통과했다. 정확히 승인한 목록은 숫자 색상 스키마 2행, 선택 채널 옵션
  3행, 숫자 색상 런타임 cardinality 1행, PBR Action 스키마 2행, PBR 정책
  리터럴 4행, 내부 미리보기 용량 3행이다.
  stale 계약은 0이며 남은 일반 숫자 5그룹과 런타임 용량 1그룹은 이후 마일스톤
  범위다.
- 독립 M54 QA는 P0/P1/P2 `0/0/0`으로 PASS했다. 색상 적대 호출 6/6,
  오버레이 불투명도 8/8, PBR 폭 8/8이 owner 조회 또는 생성 전에 차단됐고 양 끝점은
  전달됐다. 실제 배열 공유 교차검사도 두 공유 쌍이 같은 객체임을 확인해 CPU
  고유 보유량 계산이 정확함을 검증했다. 별도 관련 회귀 61/61, guard 43/43,
  정리 후 핵심 2/2가 통과했다. QA 보고서는
  `debugCapture/painter/evidence_audit/m54_qa_independent.json`이다.
- 공식 근거:
  https://json-schema.org/understanding-json-schema/reference/array#length,
  https://doc.qt.io/qt-6/qcolor.html,
  https://helpx.adobe.com/photoshop/using/saving-selections-alpha-channel-masks.html#edit_channel_options

## M55 완료: Painting 숫자·그래픽·자원 계약의 엄격화와 실제 측정

- 범위는 Painting 전용이며 UI Design 모드는 제외한다. M55는 문법상 `max/min`,
  0 비교, `len` 비교를 근거로 승인하지 않고, 요구 입력 검증, 직렬화 구조,
  수학적 퇴화, Qt 임시 위젯 크기, 파생 래스터 크기, Tiger 작화 모델을 서로
  다른 해시 계약으로 분리했다.
- 공통 `app/painter_dimensions.py` 계약을 추가했다. 래스터 크기는 bool이나
  분수가 아닌 양의 정수여야 하며, 물리 크기·PPI·배율은 유한한 양수 또는
  명시된 비음수여야 한다. PNG/PSD, 레이어 래스터, 마스크, Wet Canvas,
  OpenGL, Blockout/PBR, 인쇄 크기와 선택 마스크가 잘못된 값을 1픽셀로
  바꾸지 않고 실패하도록 수정했다.
- 추가 전수검사에서 PSD `(0, h)`를 `(1, h)`로 바꾸던 경로, PNG 획 배율을
  임의의 `0.001`로 올리던 경로, Material Paint의 0 폭과 0 크기를 1/8픽셀로
  바꾸던 경로, 참조 이미지·스티커 비율 분모의 불필요한 1픽셀 보정을
  제거했다. 유효한 양의 서브픽셀 폭은 authored 값으로 보존되고, 실제 정수
  래스터화 단계에서만 최소 한 픽셀을 차지한다.
- OpenGL 캔버스는 현재 정확히 지원하는 round/비동역학 획만 GPU로 처리하고,
  marker/highlighter, authored dynamics, 범위 밖 점·크기·불투명도는 CPU로
  명시적으로 폴백한다. 0 opacity는 정확히 0이며, 0.25 px를 1 px로 넓히거나
  pressure/tilt 공식을 추정하지 않는다. `QOpenGLContext.isValid()`와
  `makeCurrent()` 실패를 감지해 기존 context/surface를 정리하고 한 번
  재생성하며 생성·활성화·복구·실패 텔레메트리를 노출한다.
- 대형 캔버스 자원은 Qt `Format_RGBA8888`의 4 bytes/pixel과
  `QImage.sizeInBytes()`를 근거로 계산한다. 60/10/20/10 캐시 배분 합은 설정
  바이트와 정확히 같고, 각 캐시가 RGBA8 타일 하나를 담지 못하는 설정은
  실패한다. queue, worker, result, timeout, undo budget도 bool/분수/음수
  보정을 허용하지 않는다.
- 실제 native context churn 측정은 60 operations, context 생성 1회, 활성화
  실패 0, 오류 0을 기록했다. 실제 4K/8K 측정은 프로세스/GPU 자원 관측,
  렌더 parity, 단일 dirty tile, 저장 무결성, executor drain, zoom reference
  parity와 설정된 자원 예산을 모두 통과했다. 이는 해당 장비·실행의 관측이며
  보편적 누수 없음, 지연 상한, GPU 동등성 주장은 아니다.
- 수정된 soak harness는 Windows ctypes 구조를 프로세스당 한 번만 만들고,
  DKW-Massart 99% 신뢰도·0.02 CDF rank error 정책에서 산출한 6,623개
  deterministic bounded reservoir만 유지하며, resource sample은 측정 중 NDJSON으로
  흘려보낸다. 이전 harness 자체의 무제한 ctypes/latency/sample 누적 결과는 실패
  증거로 보존하며 승인에 사용하지 않는다.
- 수정 소스에서 7200초 실행 3회가 각각 259,481 / 259,995 / 254,622 operations,
  2,162 / 2,166 / 2,121 cycles, resource sample 1,437개, workload error 0으로
  완료됐다. raw report SHA-256은 각각
  `78e443fb642c44f06579269c9283772ef4e56f7998022bf72232cba2f71d244b`,
  `ba8d82273469d9f1dc6c5d7530c86685718f7e11c5d60bd6892d15120b3475b4`,
  `456b8619e4890388844441d1c8ab8a1ada6a94d47207a7ee4a91ca9c510049f9`이다.
- Windows WorkingSetSize는 shared/private를 포함한 resident physical page이므로
  관찰값으로 유지한다. PROCESS_MEMORY_COUNTERS_EX.PrivateUsage는 process private
  Commit Charge이므로 retained-private-allocation 차단 신호로 사용한다. 세 실행의
  late-half PrivateUsage retention 신호는 모두 false이며 Working Set 증가는 그대로
  보고한다. 이는 보편적인 leak-free 인증이 아니다.
- 독립 M55 delta QA는 stored v3 series를 정확히 재계산해 deep-equal을 확인했고,
  focused 33/33, P0/P1/P2 `0/0/0`, raw 재실행 불필요로 판정했다. 보고서는
  `debugCapture/painter/evidence_audit/m55_soak_semantics_delta_qa.json`, SHA-256은
  `7fa362f33d9b9ec19991f4ac53bf6b8a535c1901954d2e283926abc6131e5a0b`이다.
- 최종 Painting 전수감사는 app 63개, test 68개, QA 45개, AST 숫자 사이트
  6,415개를 포함한다. 미검토, 근거 미해결, stale, pending, defect, 미참조 앱
  모듈은 모두 0이다. UI Design을 제외한 전체 Painting 회귀는 639/639,
  architecture/debugCapture/evidence guard는 36/36 통과했다.
- M55 승인은 구현된 Painting 계약과 현재 증거 집계에 한정한다. 현재 1× 모니터의
  실제 high-DPI 관찰, 물리 태블릿, 사람의 시각 검토, 모든 외부 드라이버·앱 조합은
  미검증 한계로 유지하며 자동 PASS로 바꾸지 않는다. 전체 수정 목록은
  `docs/PAINTER_PAINTING_FULL_AUDIT_CHANGE_LIST_KO.md`에 저장했다.
- 공식 근거:
  https://doc.qt.io/qt-6/qopenglcontext.html,
  https://doc.qt.io/qt-6/qimage.html,
  https://doc.qt.io/qt-6/qpainter.html,
  https://docs.python.org/3/library/concurrent.futures.html,
  https://learn.microsoft.com/en-us/windows/win32/procthread/process-working-set,
  https://learn.microsoft.com/en-us/windows/win32/memory/working-set,
  https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex
