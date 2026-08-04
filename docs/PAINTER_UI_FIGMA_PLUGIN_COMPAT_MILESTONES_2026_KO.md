# Painter UI Figma Plugin 호환 마일스톤 (2026)

## 목표와 비목표

목표는 Figma Community 플러그인 전체를 그대로 실행한다고 주장하는 것이 아니다.
Painter UI 문서 모델로 안전하게 매핑할 수 있는 공개 Figma Plugin API의 작은 부분부터
실제 플러그인 corpus로 검증하며 넓힌다.

- 기존 `Figma plugin exchange`는 Painter 문서를 Figma로 보내고 다시 가져오는 경로다.
- 이 문서의 `Figma plugin compatibility runtime`은 타사 `manifest.json`과 JavaScript를
  Painter 안에서 실행하는 별도 기능이다.
- private/proposed API, Widget, FigJam 전용 기능, 결제, 조직·팀 데이터, 백그라운드
  실행은 초기 범위에서 제외한다.
- 지원하지 않는 API는 무시하지 않고 preflight에서 차단 사유로 표시한다.

## FP0 — Exchange 기준선

상태: `Active`

- editable node, component/instance/Slot stable ID 왕복
- 실제 Figma Desktop 개발 플러그인 재반입 캡처
- FP0 완료 전에도 FP1의 안전한 manifest 관리 기반은 개발할 수 있지만, 두 기능을
  같은 기능으로 표시하지 않는다.

## FP1 — 로컬 플러그인 관리자와 preflight

상태: `Complete (2026-08-04)`

범위:

- Figma `manifest.json` 읽기와 경로 탈출 방지
- `api`, `editorType`, `main`, `ui`, `documentAccess`, `networkAccess`,
  `permissions`, private/proposed API 검사
- 설치, 목록, 상세 검사, 제거
- 중복 ID와 손상된 package 차단
- 이 단계에서는 JavaScript를 절대 실행하지 않으며 `runtime_ready=false`다.

완료 증거:

- 정상·손상·경로 탈출·중복 ID·설치·제거 자동 테스트
- registry report가 `metadata_only_no_code_execution`을 명시
- 아키텍처 회귀 통과

구현 결과:

- `app/painter_ui_figma_plugin_manifest.py`: 공식 manifest 필드와 package resource
  경계를 검사한다.
- `app/painter_ui_figma_plugin_registry.py`: 설치·목록·상세·제거와 중복 ID를
  관리한다.
- `플러그인 > 로컬 Figma 플러그인 관리`에서 상태와 차단 사유를 확인한다.
- ownerless Python Actions로 validate/list/inspect/install/remove를 제공한다.
- 관련 Figma exchange와 편집기 아키텍처를 포함한 회귀 50개가 통과했다.
- FP1 완료 시점에는 실행 버튼이 없었다. FP2 기본 sandbox가 추가된 뒤에는 source
  preflight를 통과한 패키지에만 실행 버튼이 활성화된다.

## FP2 — Headless Core API 샌드박스

상태: `Complete (limited headless FP2 subset, 2026-08-04)`

- 별도 프로세스의 제한된 JavaScript 런타임
- 한 번에 플러그인 하나, 사용자 명시 실행, 시간·메모리 제한
- 첫 API 집합: `figma.currentPage`, selection, notify, closePlugin,
  createRectangle, createEllipse, createFrame, createText
- 첫 속성 집합: name, x/y, width/height, rotation, visible, opacity,
  fills, strokes, children
- 모든 변경은 하나의 Painter undo transaction으로 적용
- 브라우저·파일·프로세스·임의 Python 접근 없음

완료 증거:

- 자체 fixture가 아니라 최소 3개의 허용 API만 쓰는 공개/샘플 플러그인 corpus
- timeout, 예외, unsupported API 호출 시 문서 무변경 보장
- Canvas와 Layer hierarchy 실제 캡처

현재 구현:

- Node 24 별도 프로세스와 permission mode, 최소 environment, VM code-generation
  차단, source allowlist preflight, 내부 timeout과 외부 hard timeout을 함께 사용한다.
- `currentPage`, selection, notify, closePlugin, loadFontAsync,
  createRectangle/createEllipse/createFrame/createText, resize, appendChild를 지원한다.
- Rectangle·Ellipse·Frame·Text·Vector 생성, 기존 선택의 위치·크기·회전·표시·불투명도
  변경을 한 번에 Painter 문서로 반영한다.
- 플러그인 관리자와 `paint.ui.figma_plugin.run` Action에서 실행할 수 있다.
- require/process/fetch/WebSocket/eval/Function/dynamic import/constructor를 차단한다.
- 예외, unsupported API, timeout은 apply 이전에 종료되어 원본 문서를 변경하지 않는다.

완료된 FP2 증거:

- Figma 공식 `figma/plugin-samples`의 고정 revision
  `03131bef561eb25ee2b704e3b39e40acc70330e0`을 수정하지 않고 실행했다.
- `sierpinski` 485 Ellipse, `create-rects-shapes` 5 Rectangle,
  `vector-path` 1 Path의 예상 개수와 Painter 반영 결과가 모두 일치했다(3/3).
- corpus 정의는 `qa_corpus/painter_ui_figma_plugins/official_samples.json`,
  재현 도구는 `tools/qa_painter_ui_figma_plugin_official_corpus.py`다.
- solid fill/stroke의 RGBA·paint opacity·stroke width/alignment와 Text의
  family/style/size/weight/alignment/line-height를 공개 API fixture로 검증했다.
- `tools/qa_painter_ui_figma_plugin_product.py`가 관리자 UI의 실행 성공·실패를
  한글 글리프가 정상인 PNG로 캡처하고, 실제 `PaintDialog` UI Design 작업공간에서
  플러그인 생성 직후와 Undo 직후를 각각 캡처한다. 성공 실행은 단일 Undo
  스냅샷으로 되돌아가며 실패 실행은 문서를 변경하지 않는다.
- 관련 exchange/plugin/runtime/corpus/menu/architecture 회귀 59개가 통과했다.

## FP3 — Plugin UI bridge

상태: `Complete (bounded message/document/network/drop slice, 2026-08-04)`

- 격리된 WebView에서 `ui.html` 표시
- main/UI 간 `postMessage` bridge
- light/dark theme와 닫기·크기 변경
- manifest의 허용 domain만 네트워크 접근
- clipboard, download, external navigation은 사용자 확인 또는 명시적 차단

공식 계약 기준선:

- `figma.showUI(html, options)`는 HTML을 iframe에 표시하며 기본 크기는 300×200,
  최소 너비는 70이다. `visible`, `width`, `height`, `title`, `position`,
  `themeColors`를 제한된 옵션으로 해석한다.
- UI→main은 `parent.postMessage({pluginMessage: value}, '*')`, main→UI는
  `figma.ui.postMessage(value)`이며 UI에서는 `event.data.pluginMessage`로 받는다.
- main의 `figma.ui.onmessage` handler는 UI가 살아 있는 동안 유지되어야 하므로
  FP2의 실행 후 종료되는 일회성 worker를 억지로 재사용하지 않는다. FP3는
  수명주기가 있는 별도 worker session과 명시적 close/timeout을 사용한다.
- `themeColors: true`이면 iframe 루트에 `figma-light`/`figma-dark`와 공식 CSS
  변수 계층을 주입한다.
- 현재 FP2 preflight는 `showUI`, `figma.ui`, `__html__`, `__uiFiles__` 사용을
  `FP3 message bridge required`로 명시 차단하여 잘못된 실행 가능 표시를 막는다.

구현된 FP3 slice:

- `PainterFigmaPluginUISession`은 별도 Node permission-mode 프로세스를 유지하며
  `showUI`, `figma.ui.onmessage`, `figma.ui.postMessage`, show/hide/resize/close의
  제한된 수명주기를 JSON-lines session으로 제공한다.
- 전용 off-the-record `QWebEngineProfile`과 WebChannel을 사용한다. 다른 WebView의
  profile에 정책을 전파하지 않는다.
- CSP와 request interceptor가 원격 연결·외부 이동을 차단하며, WebView의
  클립보드 접근·파일 접근·다운로드·영구 cookie/cache를 비활성화한다.
- `themeColors`가 켜지면 light/dark class와 현재 지원하는 Figma CSS color 변수
  subset을 삽입한다.
- 관리자에서 headless `실행`과 제한된 document-capable `UI 실행`을 구분한다.
  UI source가 현재 허용되지 않은 Figma root를 사용하면 preflight가 차단한다.
- 실제 WebView 제품 QA에서 boot 메시지와 버튼 클릭의 UI→main→UI echo가
  순서대로 통과했으며 캡처에 최종 `UI 응답 7`이 표시된다.
- Figma 공식 UI sample corpus 3종을 고정 revision에서 수정 없이 분류했다.
  `post-message`는 실제 async timer 왕복까지 지원되고, `webpack-react`는 UI
  메시지로 3개 Rectangle을 생성한다. `icon-drag-and-drop`은 공식 `pluginDrop` →
  `figma.on('drop')` → `DropFile.getTextAsync()` → `createNodeFromSvg()` 경로로
  Feather SVG를 Frame+Vector hierarchy로 만든다. 세 샘플 모두 수정하지 않은 main/UI
  source로 실행되어 corpus 3/3이 지원 상태로 통과했다.
- UI session의 Rectangle/Ellipse/Frame/Text/Vector 생성과 선택을 FP2 원자적
  apply에 연결했다. 한 UI 세션에서 같은 plugin node ID는 같은 Painter object ID로
  유지되므로 후속 메시지가 기존 노드를 중복 생성하지 않는다.
- 실제 `PaintDialog`와 관리자 `UI 실행`, WebView 버튼 클릭으로 파란 Rectangle을
  만들고 `Run Figma UI plugin` Undo 한 번으로 제거하는 제품 QA가 통과했다.
  증거 캡처는 `debugCapture/painter_ui_figma_plugin_ui_document/`에 생성된다.
- worker·문서 callback 실패는 UI를 비활성화하고 세션을 종료하여 반쯤 적용된
  대화상자를 계속 사용하지 않게 한다.
- `networkAccess.allowedDomains`의 scheme, wildcard subdomain, port, exact/prefix
  path와 `none`/`*` 의미를 검증한다. `*`와 로컬 주소는 공식 계약대로 reasoning을
  요구하고, `devAllowedDomains`는 일반 제품 실행에서 열지 않는다.
- 원격 연결은 실행할 때마다 기본값 `아니요`인 승인 창을 거친다. 승인된 production
  domain만 CSP와 WebEngine request interceptor 양쪽에 전달되며 외부 navigation,
  iframe, clipboard, file, download 정책은 계속 차단된다. 승인은 저장되지 않는다.
- 실제 WebView 네트워크 QA는 승인한 `127.0.0.1` path 요청 성공과 같은 서버의
  미승인 `localhost` 요청 차단을 동시에 증명했다. 캡처는
  `debugCapture/painter_ui_figma_plugin_network/figma_plugin_network_permission.png`다.
- 실제 WebView 수명주기 QA는 360×220 표시, 560×300 resize, hide 후 timer show,
  close를 검증하고 initial/resized/restored 캡처를
  `debugCapture/painter_ui_figma_plugin_lifecycle/`에 남긴다. timer callback은 main→UI
  message가 없어도 UI 상태 push를 발생시키므로 숨김 상태에 고립되지 않는다.
- 무한 루프 message handler 제품 QA는 100ms VM timeout 뒤 worker 종료, polling
  중단, WebView 비활성화, `실행 오류` 제목을 검증한다. 캡처와 report는
  `debugCapture/painter_ui_figma_plugin_recovery/`에 남긴다.
- WebView bridge는 일반 `pluginMessage`와 `pluginDrop`을 분리한다. drop file은 최대
  16개/합계 1 MiB이며 활성 Painter artboard 밖의 drop은 무시한다. page/immediate
  parenting과 상대/절대 좌표를 전달하고 결과 전체는 기존 단일 Undo transaction에
  포함한다.
- `createNodeFromSvg`는 256 KiB/512 element 안에서 path, polyline, polygon, line,
  circle, ellipse, rect와 기본 solid fill/stroke를 Frame+Vector로 보존한다. transform,
  filter, mask, embedded image/font와 복합 SVG paint server 지원은 주장하지 않는다.
- 실제 PaintDialog/manager/WebView 제품 QA는 공식 첫 Feather icon을 활성 artboard에
  drop하고 `SVG > SVG polyline` 레이어 계층과 한 번의 Undo를 증명한다. 캡처는
  `debugCapture/painter_ui_figma_plugin_svg_drop/`에 남긴다.
- Figma 공식 계약대로 `createFrame()` 기본 100×100 흰색 배경을 FP2/FP3 양쪽에서
  유지한다.
- 관련 회귀 83개가 통과했다.

## FP4 — 디자인 API 확장

상태: `Active`

- component/instance, styles, variables, auto layout, boolean/vector
- font/image loading과 exportAsync의 Painter 대응 범위
- dynamic-page 의미를 Painter Page lazy access에 매핑
- 기능별 capability matrix와 실제 round-trip corpus

## FP5 — 호환성 등급과 제품화

상태: `Planned`

- `지원`, `부분 지원`, `차단`의 플러그인별 결과
- 최소 20개 실제 플러그인 corpus
- 충돌 복구, 상태 저장, 성능 예산, 접근성, 서명·출처 표시
- 전체 Figma API 호환이라는 표현은 corpus와 capability matrix가 증명하지 않는 한 금지

## 실행 순서

현재 실행 순서는 `FP1 manifest/registry → FP1 UI/Actions → FP2 sandbox →
FP2 official corpus/product evidence → FP3 UI bridge → FP3 document UI/Undo →
FP3 explicit network permission → FP3 lifecycle/recovery evidence → FP3 official
SVG drop → FP4 capability expansion`이다. 원격
네트워크는 manifest 선언만으로 자동 허용하지 않고 사용자 승인과 실행별 정책이
모두 일치할 때만 연다.
