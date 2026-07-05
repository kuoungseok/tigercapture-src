# TigerCapture Product Catalog PT Scenario

Last updated: 2026-07-03

이 문서는 최신 `SPEC.md`와 `docs/review_automation/` 규칙을 읽은 뒤 작성한
제품 카탈로그 PT 시나리오 초안이다.

중요: 이 문서는 시나리오 문서다. 사용자가 명시적으로 승인하기 전까지 PPT,
PNG, HTML, GIF를 생성하지 않는다.

## 읽은 기준 문서

- `SPEC.md`
- `README.md`
- `TODO.md`
- `docs/RELEASE_POSITIONING.md`
- `docs/SPEC_REVIEW_AUTOMATION.md`
- `docs/SPEC_PYTHON_ACTION_SYSTEM.md`
- `docs/SPEC_UI_RENEWAL.md`
- `docs/SPEC_AR_PBR_COMPOSITOR.md`
- `docs/SPEC_VTUBER_STUDIO_BROADCAST.md`
- `docs/VTUBER_TRUMP_SOURCE_MAPPING_CONTEXT.md`
- `docs/CURRENT_SPEC_PRESENTATION_SCENARIO.md`
- `docs/MULTI_MONITOR_REVIEW_SCENARIO_RULES.md`
- `docs/review_reference_featpaper_style.md`
- `docs/review_automation/README.md`
- `docs/review_automation/AGENT_START_HERE.md`
- `docs/review_automation/PURPOSE_RULES.md`
- `docs/review_automation/CATALOG_PPT_STYLE.md`
- `docs/review_automation/PRESENTATION_SCENARIO.md`
- `docs/review_automation/MULTI_MONITOR_RULES.md`
- `docs/review_automation/TEMPLATE_ASSET_MANIFEST.md`
- `docs/review_automation/REVIEW_AUTOMATION_TODO.md`
- `app/review_automation/deck_modes.py`
- `app/review_automation/feature_action_scenarios.py`
- `app/actions/audio_namespace.py`

## 핵심 판단

TigerCapture는 제품 카탈로그에서 다음처럼 보여야 한다.

> 로컬 우선 Windows 크리에이터 스튜디오. 화면 녹화와 외부 영상을 가져와
> 실제 타임라인에서 편집하고, AI 명령, 컬러, 사운드, 노드, Live2D/MMD/3D,
> VTuber 워크플로를 하나의 로컬 편집 환경 안에서 다룬다.

이 PT의 목적은 QA 통과 상태를 보고하는 것이 아니라, 사용자가 이 툴로 무엇을
만들 수 있는지 보여주는 것이다. 따라서 각 장은 실제 TigerCapture 편집 화면을
근거로 삼되, 표현은 제품 카탈로그처럼 조용하고 고급스럽게 구성한다.

## 절대 규칙

- PT 제작은 이 시나리오 승인 후에만 한다.
- 첫 화면은 멀티 모니터 템플릿을 우선 사용한다.
- 노트북/멀티 모니터 템플릿은 왜곡하지 않는다.
- 템플릿의 화면 영역만 실제 TigerCapture 캡처로 교체한다.
- 전에 확정한 노트북/멀티모니터 템플릿 외의 장식용 이미지, 생성형 이미지,
  새 디바이스 목업, 스톡 이미지성 첨부 이미지는 사용하지 않는다.
- 제품-facing 페이지에 QA 점수, pass/fail 수, action 수, raw JSON, 파일 경로
  덤프를 넣지 않는다.
- 빈 에디터, 컬러바, 테스트 패턴, 가짜 생성형 에디터 UI를 넣지 않는다.
- 스크린 안쪽 편집 화면은 실제 TigerCapture 캡처만 사용한다.
- 샘플 영상은 `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`에서
  가져온다.
- Le Mans / 24 Hours of Le Mans / FIA WEC 영상은 사용하지 않는다.
- 외부 엔진 브리지는 현재 카탈로그 시나리오에서 제외한다.
- AR/PBR은 `E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene`의 카메라 씬을
  사용한다. 예전 오토바이 디버그 에셋은 사용하지 않는다.
- Spine/NIKKE는 렌더가 시각적으로 틀어지면 성공 페이지로 쓰지 않는다.

## 사용 템플릿

노트북 템플릿:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\laptop_catalog_template.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\laptop_catalog_template.screen-map.json
```

멀티 모니터 템플릿:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_catalog_template.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_catalog_template.screen-map.json
```

화면 형태 기준:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\monitor_shape_lock_reference.png
```

## 영상 소스 방향

우선 후보:

- 서울/부산/송도 드론 영상
- 도쿄 야경 항공 영상
- 도시 야경 / 석양 / 건축 투어
- Lamborghini / Bugatti 같은 자동차 영상
- Samsung QD-OLED / HDR 데모 영상

미디어풀에는 항상 여러 영상이 보여야 한다. 오버뷰와 디바이스 프레임 화면은
단일 클립만 놓인 짧은 테스트 타임라인처럼 보이면 안 된다. 주요 화면은 최소한
비디오, 오디오, 효과, 컬러, 텍스트, 노드, 배우 트랙 중 둘 이상이 보여야 한다.

## 멀티 모니터 창 배치 룰

첫 화면 멀티 모니터 이미지는 아래 구성을 기본값으로 한다.

중앙 모니터:

- 메인 편집 베이.
- 위쪽은 Viewer.
- 아래쪽은 가로 전체 Timeline.
- AI Command는 아래 또는 오른쪽의 작은 보조 영역.
- Viewer와 Timeline을 가리면 안 된다.
- 긴 멀티 트랙 프로젝트가 보여야 한다.

오른쪽 모니터:

- 기술 마감 베이.
- Node Graph가 가장 크게 보여야 한다.
- 연결된 노드와 선택 노드 파라미터가 보여야 한다.
- Sound Editor, waveform, spectrum, audio mixer, levels는 아래/보조 영역.
- Color/scopes는 Node Graph를 너무 작게 만들지 않을 때만 같이 둔다.

왼쪽 모니터:

- 배우/3D/에셋 베이.
- Live2D 또는 Actor Library가 가장 읽기 쉬워야 한다.
- AR/PBR은 Poly Haven 카메라 씬을 사용한다.
- MMD Actor Editor는 실제 캡처 가능한 경우 배치한다.
- 남는 공간에 Media Pool, Effect Library, preset support strip을 둔다.

공통:

- 세 모니터 안쪽은 모두 실제 TigerCapture 캡처다.
- 숨겨진 GPU/Viewer 위젯 grab에 의존하지 않는다.
- 캡처할 창을 잠깐 실제로 show/raise/settle한 뒤 찍는다.
- 없는 창은 생성형 이미지로 채우지 않고 보류한다.

## 상세 카탈로그 PT 구조

권장 상세본은 32장이다. 요약본은 이 구조에서 8장 안팎으로 압축하고,
evidence-full은 내부 부록으로만 확장한다.

### 1. Multi-Monitor Studio Hero

목적: TigerCapture가 단일 녹화 앱이 아니라 분리 가능한 스튜디오 환경임을 첫
장부터 보여준다.

첫 장 고정 룰:

- 중앙 모니터의 영상 프리뷰 Viewer는 `YouTube Imports`의 Lamborghini 영상을
  사용한다.
- 사람 눈/얼굴/피부 같은 매크로 클로즈업 영상은 이 첫 장에서 사용하지 않는다.
  첫 장은 제품/편집/프로덕션 환경을 보여줘야 한다.
- 왼쪽 모니터에는 Live2D/MMD만 두지 말고 실제 3D viewer 또는 AR/PBR asset
  preview가 반드시 보여야 한다.
- 3D는 Poly Haven camera scene을 사용한다:
  `E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene\models\Camera_01\Camera_01_1k.gltf`
- 3D viewer capture rule: hide the visible HDR/cubemap environment background
  before every catalog screenshot. Keep environment lighting if needed, but use
  the viewer background toggle so the model reads on a neutral viewer surface.
- AR/PBR workbench 컨트롤만 보이는 것은 첫 장 증거로 부족하다. 실제 3D 뷰어가
  캡처되지 않으면 첫 장 생성을 중단하고 캡처 경로를 먼저 고친다.

시각:

- 멀티 모니터 템플릿을 첫 화면에 배치한다.
- 왼쪽 모니터: Live2D/MMD/AR-PBR/Actor Library 중 실제 캡처 가능한 조합.
- 중앙 모니터: Viewer, 긴 Timeline, AI Command.
- 오른쪽 모니터: Node Graph, Sound Editor, Color/Audio Workbench.

캡처 조건:

- 세 화면 모두 실제 TigerCapture 캡처.
- 중앙 타임라인은 길고 복잡해야 한다.
- 미디어풀에는 여러 영상이 보여야 한다.
- 화면 안쪽에 설명 라벨을 그려 넣지 않는다.

### 2. Product Thesis

목적: “Record -> Edit -> Workbench -> Export” 흐름을 한 문장으로 각인한다.

시각:

- 노트북 템플릿 또는 얇은 다이어그램.
- 실제 편집 화면은 도시/자동차/HDR 영상이 올라간 상태.

대사 방향:

- “녹화와 가져오기가 곧 편집 세션이 되는 로컬 크리에이터 스튜디오.”
- QA나 자동화 수치가 아니라 사용자 결과물을 이야기한다.

### 3. Editor Overview

목적: 현재 리뉴얼된 메인 편집기 전체 구조를 보여준다.

시각:

- Media Pool, Viewer, Workbench, Timeline이 모두 보이는 실제 캡처.
- Project > 프로젝트명, Viewer, Timeline 텍스트가 깨지지 않아야 한다.

캡처 조건:

- 미디어풀에 여러 영상.
- 타임라인은 비디오와 오디오를 포함한 멀티 트랙.
- 일부 컷/마커/전환이 자연스럽게 보이면 좋다.

### 4. Media Intake And YouTube Imports

목적: 외부 영상을 가져와 편집 프로젝트로 시작하는 흐름을 보여준다.

시각:

- Media Pool의 선택된 클립 카드와 리스트형 다른 클립.
- YouTube Imports 영상 파일명이 너무 깨지면 ASCII 표시명을 사용한다.

대사 방향:

- “여러 소스가 프로젝트 빈에 모이고, 선택한 소스가 바로 Viewer와 Timeline으로
  이어진다.”

### 5. Screen Recording And Auto Polish

목적: Screen Studio식 녹화 보정 방향을 보여준다.

시각:

- 커서 강조, 클릭, 줌 후보, 타임라인 zoom actor 또는 polish 설정.
- 실제 화면 녹화 샘플이 없으면 이 장은 보류한다.

주의:

- Screen Studio 완전 대체라고 쓰지 않는다.
- “Screen Studio-inspired polish” 정도의 표현만 사용한다.

### 6. Timeline Editing Core

목적: TigerCapture가 단순 컷툴이 아니라 NLE형 기본 편집 표면을 갖췄음을 보여준다.

시각:

- 확대된 타임라인.
- 컷 지점, 선택 클립, playhead, speed/fade/marker 상태.
- 비디오와 오디오가 같이 보이면 좋다.

캡처 액션 후보:

```text
media.import_to_timeline
timeline.set_zoom
timeline.split
clip.set_speed
timeline.marker.add
capture.screenshot
```

문구 제한:

- “Premiere/Resolve급 NLE”라고 쓰지 않는다.
- “core NLE workflow/action surface” 또는 “실제 컷/속도/마커 편집 표면”으로 표현한다.

### 7. Trim, Ripple, Roll, Slip, Slide

목적: 타임라인 편집 도구의 깊이를 별도 장으로 보여준다.

시각:

- Ripple/Roll/Slip/Slide 중 하나를 선택한 상태.
- 트랙 왼쪽 V/A 레일과 클립 전체 폭이 잘 보이게 캡처한다.

캡처 조건:

- 한 프레임 gap cleanup이나 edge issue 상태를 디버그처럼 보여주지 않는다.
- 실제 편집 중인 상태처럼 보여야 한다.

### 8. Drag Presets

목적: 왼쪽 독의 아이콘 기반 이펙트/타이틀/트랜지션/워크플로 프리셋을 설명한다.

시각:

- Effect Library 또는 Transition/Title/Workflow Presets.
- 롤오버된 타일은 은은하게 다른 상태.
- Inspector preview가 Viewer 프레임 기반으로 동작하는 모습.

주의:

- 아이콘만으로 모호하면 hover preview와 짧은 target strip을 보여준다.
- 큰 텍스트 카테고리 탭으로 화면을 지저분하게 만들지 않는다.

### 9. Transitions On Real Cuts

목적: 트랜지션이 메뉴가 아니라 실제 컷 사이에 적용되는 것을 보여준다.

시각:

- 두 클립 경계.
- transition strip/handle.
- Viewer에는 전환 프레임 또는 preview overlay.

캡처 액션 후보:

```text
timeline.split
transition.apply
capture.screenshot
```

### 10. Effects And Background Tools

목적: 필터, chroma key, background removal, stabilizer, masks가 타임라인/워크벤치와
연결됨을 보여준다.

비교 템플릿 사용:

- `COMPARISON_TEMPLATE_RULES.md`를 따른다.
- 기본은 `Effect Off | Effect On` Before / After Split.
- blur, sharpen, denoise, stabilization, background removal, glow, vignette,
  film grain, pixelate처럼 눈에 보이는 효과에만 사용한다.
- 효과 차이가 약하면 Zoom Detail Compare 또는 iPad emphasis 템플릿으로
  작은 영역을 강조한다.

시각:

- 실제 영상 위에 적용된 효과.
- Workbench의 효과 파라미터 또는 clip FX 상태.

주의:

- 효과가 눈에 보이지 않으면 이 장의 문구를 낮춘다.

### 11. Typography Animation

목적: 텍스트가 단순 자막이 아니라 키프레임/애니메이션 가능한 레이어임을 보여준다.

시각:

- Viewer 위에 텍스트.
- 타임라인에 텍스트/타이포그래피 구간.
- opacity/position/keyframe 컨트롤.

캡처 액션 후보:

```text
text.add
text.set_keyframes
capture.screenshot
```

### 12. Subtitles And Caption Workflow

목적: 자막과 캡션 흐름을 별도 기능으로 보여준다.

시각:

- 캡션이 실제 영상 위에 보이는 Viewer.
- Subtitle 또는 Script/Edit 패널이 같이 보이면 좋다.

주의:

- 텍스트 깨짐이 있으면 캡처 실패로 본다.

### 13. AI Command

목적: AI가 임의 코드를 실행하는 게 아니라 검토 가능한 편집 명령 표면임을 보여준다.

시각:

- 하단 AI Command rail.
- 타임라인 컨텍스트가 같이 보이는 상태.

문구 제한:

- Descript 대체라고 쓰지 않는다.
- “reviewed edit plans”, “local-first command surface”로 표현한다.

### 14. AI Script Edit

목적: 텍스트/트랜스크립트 기반 편집이 가능한 방향을 보여준다.

시각:

- Script Edit 패널 또는 edit plan preview.
- 실제 컷 후보가 타임라인에 표시되어야 한다.

주의:

- 실제 AI corpus가 부족하면 “MVP / reviewed apply”로 표현한다.

### 15. Local LLM And MCP Automation

목적: 로컬 LLM, Codex/Claude MCP, Python Action으로 조작 가능한 스튜디오라는 점을
제품적으로 설명한다.

시각:

- 제품-facing 다이어그램과 작고 깨끗한 실제 AI Command 캡처.
- raw action count나 JSON은 보이지 않는다.

### 16. Node Graph Composition

목적: 노드 기반 합성/효과 워크플로를 보여준다. 이 페이지는 단순히
"노드 그래프가 있다"가 아니라, 노드 체인으로 어떤 영상 처리를 만들 수
있는지 설명해야 한다.

비교 템플릿 사용:

- `COMPARISON_TEMPLATE_RULES.md`를 따른다.
- Node Graph 페이지에서는 `Selected Node Off | On` 또는
  `Node Chain Off | On` 비교를 우선한다.
- 비교가 보이지 않으면 추상적인 노드 박스만으로 이 페이지를 만들지 않는다.

제품 메시지:

```text
Connect color, blur, glow, masks, LUTs, and HDR prep as editable node chains.
```

설명해야 할 노드 효과:

- Color / Grade: White Balance, Curves, Levels, Channel Mixer, LUT.
- Look / VFX: Glow, Vignette, Film Grain, Unsharp Mask, Pixelate.
- Blur / Soft Pass: Blur node와 soft-focus/out-of-focus 처리.
- Mask / Tracking: Power Window, HSL mask, tracked region, face/eyes/lips/person
  masks. 마스크는 blur, effect, color node에 적용될 수 있어야 한다.
- Pipeline / HDR: SDR -> HDR EXR prep node.
- Workflow presets: Color Polish, Glow + Mask, HDR Prep chain.

권장 노드 체인 예:

```text
Media In -> White Balance -> Curves -> Glow -> Mask -> Output
Media In -> Levels -> Unsharp Mask -> SDR -> HDR EXR -> Output
Media In -> Blur -> Vignette / Edge Mask -> Output
```

시각:

- 큰 Node Graph.
- 연결된 노드. 노드 라벨은 실제 구현된 효과 이름을 사용한다.
- 선택 노드의 파라미터 패널. 예: Curves, Glow, Blur, Mask, SDR -> HDR EXR.
- 가능하면 Viewer 또는 iPad emphasis 영역에 선택 노드의 결과/파라미터를
  같이 보여준다.
- 노드 그래프만 있고 효과 종류를 알 수 없는 화면은 사용하지 않는다.

캡처 액션 후보:

```text
node.graph.set
node.add
node.connect
node.set_param
capture.screenshot
```

주의:

- 참고 이미지처럼 노드 색/포트/링크는 얇고 절제되어야 한다.
- 말이 안 되는 가짜 AI 노드 이미지를 쓰지 않는다.
- Fusion/After Effects 전체 대체처럼 말하지 않는다. 현재 제품 메시지는
  "편집 타임라인 안에서 쓰는 실용적인 노드 기반 효과 체인"이다.
- 구현되지 않은 노드 이름을 꾸며내지 않는다. 위 목록의 실제 노드와
  실제 캡처 가능한 파라미터만 사용한다.

### 17. Masks And Object Tracking

목적: 전체 화면 효과가 아니라 특정 영역 추적/마스크 기반 처리 가능성을 보여준다.

시각:

- Viewer의 선택 영역 또는 mask overlay.
- Mask editor / node mask controls.

주의:

- Fusion 대체처럼 과장하지 않는다.

### 18. Color Grading Workspace

목적: 컬러 페이지/워크벤치가 카탈로그 핵심 장면으로 보일 만큼 성숙해졌음을 보여준다.

비교 템플릿 사용:

- `COMPARISON_TEMPLATE_RULES.md`를 따른다.
- 기본은 `Before / After Split` 또는 `Wipe Reveal`.
- 기본 라벨은 `Original | After`, 더 명확한 경우 `Color Off | Color On`.
- 비교가 너무 미묘하면 iPad emphasis 또는 Zoom Detail Compare 규칙을 사용한다.

시각:

- 실제 야경/도시/HDR 영상.
- Before/After split.
- 큰 Color Wheels.
- Scopes 또는 Light/Primary sliders.

문구 제한:

- Resolve Color Page 대체가 아니다.
- “creator-grade color foundation”, “LUT/HDR/scopes-aware workflow”로 표현한다.

### 19. Color Node And Grade Layer

목적: 컬러가 단순 전역 슬라이더가 아니라 노드/타임라인 상태와 연결됨을 보여준다.

시각:

- Color node 선택.
- 오른쪽 Color Grading workbench.
- 타임라인 Grade Layer rail 또는 diamond marks.

### 20. Sound Editor In Workbench

목적: 사운드 에디터가 별도 Load 중심 앱이 아니라 선택된 미디어/오디오 클립을 편집하는
워크벤치 표면임을 보여준다.

비교 템플릿 사용:

- `COMPARISON_TEMPLATE_RULES.md`를 따른다.
- Audio Compare는 waveform, spectrum, EQ, dynamics, cleanup, loudness 차이가
  실제로 보일 때만 사용한다.
- 추천 라벨은 `Before EQ | After EQ`, `Raw Audio | Cleaned Audio`,
  `Before Dynamics | After Dynamics`.
- 세부 오디오 비교 액션이 아직 부족하면 완성된 export-safe 비교 엔진처럼
  말하지 말고, 실제 Sound Editor 캡처와 선택된 클립 상태를 보여준다.

시각:

- Workbench Audio 탭.
- waveform, spectrum/level, EQ/Dynamics/FX/AI mini graph.
- timeline audio lane이 같이 보이면 좋다.

캡처 액션 후보:

```text
audio.extract_from_video
audio.clip.set_gain
audio.track.set_mix
audio.sound_editor.jog_shuttle.set
audio.sound_editor.advanced_lab.set
capture.screenshot
```

주의:

- 현재 세부 EQ/comp/stem/export 액션은 완전 등록 상태가 아니다.
- 그 부분은 “UI에서 편집 가능, 자동 캡처 액션 확장 필요”로 기록한다.

### 21. Audio Extraction And Mix

목적: 영상에서 사운드트랙을 분리하고, 별도 오디오 트랙으로 편집할 수 있음을 보여준다.

시각:

- 비디오 트랙과 추출된 오디오 트랙.
- waveform.
- track mix / gain controls.

캡처 액션:

```text
audio.extract_from_video
audio.clip.split
audio.clip.set_gain
audio.track.set_mix
```

### 22. Vocal / Music Separation

목적: Sound Editor Advanced Lab의 더 무거운 AI Master 기능을 소개한다.

시각:

- Advanced Lab 또는 legacy SoundEditorWindow를 명시적으로 띄운 캡처.
- vocals/instrumental 출력 흐름.

주의:

- 자동 액션은 아직 부족하므로 제품 카탈로그에서는 “Advanced Lab workflow”로
  설명하고, 완전 자동 시나리오는 후속 작업으로 둔다.

### 23. Live2D Actor Track

목적: Live2D가 영상 위에 올라가는 실제 actor track임을 보여준다.

시각:

- Viewer 안에 Live2D actor가 실제로 보인다.
- actor lane, transform/opacity keys.
- Live2D viewer 또는 actor controls.

캡처 조건:

- actor가 보이지 않으면 장을 만들지 않는다.
- 얼굴/파츠가 틀어지는 캡처는 성공 페이지로 쓰지 않는다.

### 24. Spine / NIKKE Guarded Actor Support

목적: Spine/NIKKE는 기능 후보이지만, 잘못 렌더된 화면을 홍보하지 않는다는 신뢰를
보여준다.

시각:

- 알려진 good Spine 샘플이 실제로 정상 렌더될 때만 사용.
- NIKKE가 깨지면 제품-facing 장에서는 제외하고 내부 보류로 기록한다.

문구:

- “Spine/NIKKE actor track research and guarded compatibility” 정도로 제한한다.

### 25. MMD Actor Workflow

목적: PMX/PMD + VMD 기반 MMD actor가 별도 3D/캐릭터 축임을 보여준다.

시각:

- MMD actor viewer/editor.
- actor timeline lane.
- motion/lighting/material 설정.

주의:

- Marmoset이라고 쓰지 않는다. 스펙상 Marmoset 옵션은 제거되었고 MMD는 Toon
  renderer 방향이다.

### 26. VTuber Studio

목적: Performance Source와 Program Output의 차이를 명확히 보여준다.

시각:

- VTuber Studio.
- Source Tracking: Trump face video.
- Avatar Target: Milica VRM / VSeeFace Bridge.
- Program Output: raw Trump 영상이 아닌 avatar output.
- Studio Controls / Live Target.

주의:

- Trump 영상은 최종 출력 배경으로 쓰지 않는다.
- VSeeFace 캡처가 black/degraded이면 internal VRM fallback을 정직하게 표시한다.

### 27. AR/PBR Camera Scene

목적: 3D 오브젝트를 영상 위에 배치하는 AR/PBR 워크플로를 보여준다.

시각:

- Poly Haven 카메라 씬 모델.
- Viewer 안 배치 결과.
- transform/material/HDR environment controls.

필수 소스:

```text
E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene\models\Camera_01\Camera_01_1k.gltf
```

주의:

- 3D viewer capture rule: hide the visible HDR/cubemap environment background.
  Keep HDRI lighting if useful, but do not show the HDRI room/background in the
  catalog screenshot.
- motorcycle debug asset은 사용하지 않는다.
- 외부 엔진 브리지를 언급하지 않는다.

### 28. 3D / Actor / Overlay Production Monitor

목적: Live2D, MMD, AR/PBR, VTuber가 한 편집 프로젝트 안에 얹히는 방향을 한 장으로
보여준다.

시각:

- 노트북 템플릿 또는 멀티모니터 서브 변형.
- actor lane, 3D placement, main viewer가 같이 보이는 실제 캡처.

### 29. Multilingual UI

목적: 다국어가 제품 장점이라는 점을 깨끗한 화면으로 보여준다.

시각:

- 한국어 또는 일본어 UI 캡처.
- mojibake, tofu box, 잘림이 없어야 한다.

주의:

- `README.md`의 깨진 한국어 문단은 절대 복사하지 않는다.

### 30. Export And Render Queue

목적: MP4/WebM/MOV, HDR metadata, render queue를 제품의 delivery 단계로 보여준다.

시각:

- Render Queue 또는 Export panel.
- 실제 프로젝트 범위가 선택된 타임라인.
- long timeline context.

주의:

- readiness 점수나 QA pass 수는 숨긴다.

### 31. Developer-Only Review Automation Pipeline

목적: 내부적으로 이 카탈로그를 자동으로 만들 수 있는 구조를 설명한다.

시각:

- 아주 간단한 파이프라인 다이어그램:

```text
latest spec -> action scenarios -> live editor capture -> catalog templates -> PPT/HTML/PNG
```

주의:

- 이 장은 공개 제품 기능처럼 보이면 안 된다.
- “developer-only product catalog automation”으로 표현한다.

### 32. Closing: Local Creator Studio

목적: 첫 장의 멀티모니터 인상을 다시 회수한다.

시각:

- 가장 좋은 실제 편집 캡처 또는 멀티모니터 템플릿 재사용.
- 단, 첫 장과 같은 화면을 그대로 반복하지 않는다.

문구 방향:

- “하나의 로컬 세션에서 녹화, 편집, AI, 배우, 3D, 사운드, 컬러, 내보내기를 연결한다.”

## 요약본 구성

요약본은 8장으로 압축한다.

1. Multi-Monitor Studio Hero
2. Product Thesis
3. Editor Overview
4. Timeline + Presets
5. AI Command + Script Edit
6. Color / Node / Sound Workbench
7. Live2D / MMD / AR-PBR / VTuber
8. Export + Closing

요약본도 빈 에디터나 QA 수치 장면을 쓰지 않는다.

## evidence-full 구성

evidence-full은 내부 부록이다. 이 모드에서만 QA/액션/파일 경로를 일부 보여줄 수
있다. 단, 현재 사용자가 원하는 카탈로그 PT에는 evidence-full 성격의 raw QA 장을
섞지 않는다.

## 캡처 준비 상태

| 기능군 | 현재 판단 | 카탈로그 처리 |
| --- | --- | --- |
| 템플릿 | 노트북/멀티모니터 소스 존재 | 사용 가능 |
| 샘플 영상 | YouTube Imports에 도시/자동차/HDR 영상 존재 | 사용 가능 |
| 타임라인/미디어풀 | UI 리뉴얼 캡처와 액션 흐름 존재 | 사용 가능 |
| 컬러 | soft-glass workbench, scopes, split compare 존재 | 핵심 장면으로 사용 |
| 노드 | real connected node workflow 캡처 가능 | 핵심 장면으로 사용 |
| 사운드 | 추출/게인/믹스/조그/Advanced Lab 액션 존재 | 사용 가능, 세부 FX 액션은 후속 |
| Typography | text.add / keyframe 액션 존재 | 사용 가능 |
| Transitions | transition.apply 존재 | 사용 가능 |
| Live2D | actor track/preview/export path 존재 | 실제 actor 표시 검증 후 사용 |
| Spine/NIKKE | 스펙상 존재하나 사용자 캡처에서 렌더 문제 경험 | 정상 샘플만 사용, 아니면 보류 |
| MMD | 구현 범위 큼, QA/액션 존재 | 실제 캡처 준비 후 사용 |
| VTuber | shared VTuber Studio 계약 존재 | Trump source mapping 규칙 지켜 사용 |
| AR/PBR | 카메라 씬 지정됨 | Poly Haven camera scene으로 사용 |
| External engine bridge | 현재 카탈로그 제외 | 언급 금지 |

## PPT 제작 전 승인 체크리스트

PPT 생성 전에 아래를 다시 확인한다.

- [ ] 사용자가 이 시나리오를 승인했다.
- [ ] 최신 `SPEC.md`를 다시 읽었다.
- [ ] `docs/review_automation/` 규칙을 다시 읽었다.
- [ ] 노트북/멀티모니터 템플릿이 durable source root에 있다.
- [ ] YouTube Imports 영상 중 Le Mans가 아닌 후보를 골랐다.
- [ ] 실제 에디터를 조작해 각 기능별 캡처를 만들 수 있다.
- [ ] 각 캡처는 feature-specific 장면이다.
- [ ] 각 캡처에 여러 미디어/멀티 트랙/실작업 느낌이 있다.
- [ ] 캡처 후 문구를 실제 보이는 화면에 맞게 수정한다.
- [ ] 제품-facing 장에는 QA 수치와 raw JSON을 넣지 않는다.

## 다음 구현 순서

1. 이 시나리오 승인.
2. slide manifest 생성.
3. YouTube Imports에서 샘플 영상 선별.
4. 실제 editor action scenario로 기능별 캡처 생성.
5. 노트북/멀티모니터 템플릿에 실제 캡처를 screen-map으로 합성.
6. 각 PNG를 사람이 보고 제목/본문/캡션 수정.
7. 그 다음에야 PPT 생성.
