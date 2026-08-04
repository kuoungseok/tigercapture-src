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
고유 행은 6,603개이며, 기존 라우터가 덮지 못한 행은 현재 5,024개다. 이 중 PSD
signature/version 2행을 [Adobe Photoshop File Header](https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/)
계약으로 분리·승인했으며 현재 AST 미해결은 4,813개다. 같은 Adobe 표의 26바이트 헤더와 필드
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
호환 계약으로만 승인했다. uint16 채널 변환·배열 형상 불변식 13행은 uint8 전체범위 확장, uint16 보존, 미지원 정수형 거부 테스트 후 승인했다. PNG16 zlib level 6 두 행은 외부 규격이 아닌 명시적 Tiger 인코딩 정책으로만 승인했고, flat writer 배열 형상 4행은 구조 불변식으로 승인했다. 8/16-bit flat export 8행은 포맷 전체 능력이 아닌 Tiger 지원 범위로만 승인했다. PSD 비교용 8-bit premultiplication 6행은 W3C 정의와 정수 반올림 수학에 한정해 승인했다. intent 1 기본값 3행은 ICC 의미를 인용하되 Tiger 기본 정책으로만 승인했다. 내부 `asset://` 접두 길이 1행도 정확한 문자열 불변식으로 승인했다. Advanced Brush 숫자 55행은 실제 Painting 렌더 경로, 결정적 replay, Protect Texture 문서 우선순위, Undo/Redo와 문서 복원 테스트를 갖춘 명시적 Tiger 제품 모델로 승인했으며 물리 매체나 Adobe/Corel parity는 주장하지 않는다. 반복 soak baseline 구조 3행은 안정성 임계값이 아닌 운영 집계 계약으로만 승인했고, 3회 retention review 10행은 보편 통계가 아닌 Tiger evidence 정책으로만 승인했다. runtime 통계 13행과 Windows resource selector 3행도 합격 임계값이 아닌 보고 수학/API 계약으로 승인했다. 외부 증거 SHA-256의 1 MiB read chunk 1행은 Tiger I/O 정책으로만 승인했다. readiness flat-export matrix 4행도 포맷 전체 능력이 아닌 Tiger 지원 범위로만 승인했다. ARGB32 alpha byte 1행은 little-endian Windows 범위와 직접 회귀에 한정해 승인했다. reapproval aggregation 8행은 fail-closed 운영 구조로만 승인했다. AST 미해결은 4,813개다. 예외·품질·용량·의미 감사까지
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
