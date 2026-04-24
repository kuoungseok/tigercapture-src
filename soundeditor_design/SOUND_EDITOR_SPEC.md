# Sound Editor - 조그 노브 UI 구현 스펙

## 📋 개요

기존 사운드 편집 창(Sound Editor Dialog)을 업그레이드하여 조그 노브 기반의 전문 오디오 편집 UI를 구현한다. 5개 탭 구조로 기능을 분리하고, 각 탭에서 조그 노브로 파라미터를 정밀 조절할 수 있게 한다.

## 🎯 구현 목표

- [ ] 5개 탭 구조 (Basic / EQ / Dynamics / Effects / Advanced)
- [ ] 재사용 가능한 조그 노브 컴포넌트
- [ ] 3가지 조작 방식 (드래그, 휠, 정밀 모드)
- [ ] 파형 디스플레이 + playhead + selection
- [ ] 프리셋 시스템
- [ ] Transport 컨트롤

**디자인 레퍼런스**: `design-reference/sound_editor_knob_ui.html`

---

## 🏗️ 단계별 구현 순서

### Phase 1: 조그 노브 컴포넌트 (최우선)
독립적으로 재사용 가능한 Knob 컴포넌트를 먼저 완성. 이게 핵심이고, 모든 탭에서 이걸 사용함.

### Phase 2: 레이아웃 & Basic 탭
전체 창의 레이아웃을 잡고 Basic 탭의 6개 노브를 구현.

### Phase 3: 파형 디스플레이
실제 오디오 파일을 분석해서 파형을 그리고, playhead/selection 표시.

### Phase 4: Transport 컨트롤
재생/정지, 마커 이동, 루프 기능.

### Phase 5: 다른 탭들
EQ, Dynamics, Effects, Advanced 탭을 순차적으로 추가.

### Phase 6: 프리셋 시스템
프리셋 저장/불러오기/편집.

---

## 🎛️ Phase 1: 조그 노브 컴포넌트

### 컴포넌트 인터페이스

```typescript
interface KnobProps {
  // 값 관련
  value: number;              // 현재 값
  min: number;                // 최솟값
  max: number;                // 최댓값
  defaultValue: number;       // 기본값 (더블클릭 시 리셋)
  step?: number;              // 일반 스텝 (기본 1)
  fineStep?: number;          // Shift 누를 때 스텝 (기본 0.1)
  ultraFineStep?: number;     // Ctrl 누를 때 스텝 (기본 0.01)
  
  // 표시
  label: string;              // 노브 레이블 (예: "Volume")
  unit?: string;              // 단위 (예: "dB", "Hz", "%")
  color?: 'blue' | 'green' | 'orange' | string;  // 노브 색상
  tier?: 1 | 2 | 3;           // 우선순위 뱃지
  
  // 동작
  onChange: (value: number) => void;
  onChangeEnd?: (value: number) => void;  // 드래그 종료 시
  
  // 특수
  bipolar?: boolean;          // 양방향 (Pan처럼 중앙이 0)
  logarithmic?: boolean;      // 로그 스케일 (Hz 등)
  formatter?: (value: number) => string;  // 값 표시 커스터마이징
}
```

### 조작 방식 (모두 구현 필수)

#### 1. 드래그 방식
```javascript
// 마우스 위치 기반
onMouseDown -> 시작 위치 저장
onMouseMove -> (시작 Y - 현재 Y) * 감도로 값 변경
onMouseUp -> 종료

// 감도: 100px 드래그 = 전체 범위의 100%
const sensitivity = (max - min) / 100;
newValue = startValue + (startY - currentY) * sensitivity;
```

#### 2. 휠 스크롤
```javascript
onWheel -> event.deltaY 방향으로 step만큼 증감
// 기본: step = (max - min) / 100
// Shift 누름: fineStep 사용
```

#### 3. 정밀 모드
```javascript
if (event.shiftKey) sensitivity *= 0.1;   // Shift: 10배 정밀
if (event.ctrlKey) sensitivity *= 0.01;   // Ctrl: 100배 정밀
```

#### 4. 기타 인터랙션
```javascript
onDoubleClick -> setValue(defaultValue)
onContextMenu -> 직접 입력 모달 띄우기
```

### 값 → 각도 변환

```javascript
// 노브는 -135도(최소) ~ +135도(최대) 범위로 회전 (270도)
const KNOB_MIN_ANGLE = -135;
const KNOB_MAX_ANGLE = 135;
const KNOB_RANGE = KNOB_MAX_ANGLE - KNOB_MIN_ANGLE; // 270

function valueToAngle(value, min, max) {
  const normalized = (value - min) / (max - min);  // 0~1
  return KNOB_MIN_ANGLE + normalized * KNOB_RANGE;
}

// 로그 스케일 (Hz 등)
function valueToAngleLog(value, min, max) {
  const logMin = Math.log(min);
  const logMax = Math.log(max);
  const normalized = (Math.log(value) - logMin) / (logMax - logMin);
  return KNOB_MIN_ANGLE + normalized * KNOB_RANGE;
}
```

### 시각적 요소 (SVG 기반)

노브는 아래 레이어로 구성:
1. **외곽 트랙 원** (회색, 항상 표시) — `<circle r="42" stroke="#2a2a30" />`
2. **값 아크** (컬러, 현재 값만큼 표시) — `stroke-dasharray` 사용
3. **노브 본체** (gradient 채움) — `<circle r="30" fill="url(#gradient)" />`
4. **인디케이터 라인** (노브 위 작은 선, 값 방향 가리킴) — `<line>` + `transform: rotate()`
5. **중앙 마크** (Pan 같은 bipolar일 때 12시 방향에 점)

```svg
<svg viewBox="0 0 100 100">
  <!-- 외곽 트랙 -->
  <circle cx="50" cy="50" r="42" fill="none" stroke="#2a2a30" stroke-width="3"/>
  
  <!-- 값 아크 (stroke-dasharray로 채움 정도 조절) -->
  <circle cx="50" cy="50" r="42" fill="none" 
          stroke="{color}" stroke-width="3"
          stroke-dasharray="{filledLength} 264"
          stroke-dashoffset="0"
          transform="rotate(-225 50 50)"
          stroke-linecap="round"/>
  
  <!-- 노브 본체 -->
  <circle cx="50" cy="50" r="30" fill="url(#knobGrad)" stroke="#3a3a3e" stroke-width="1"/>
  
  <!-- 인디케이터 (value에 따라 rotate) -->
  <line x1="50" y1="28" x2="50" y2="18" 
        stroke="{color}" stroke-width="3" stroke-linecap="round"
        transform="rotate({angle} 50 50)"/>
</svg>
```

### 색상 매핑

```javascript
const KNOB_COLORS = {
  blue: '#4a9bee',     // 기본 파라미터 (Volume, Fade)
  green: '#5DCAA5',    // 밸런스/믹스 (Pan, Dry/Wet)
  orange: '#D85A30',   // 시간 기반 (Speed, Pitch) — 원본 변형
};
```

### 값 포맷팅 예시

```javascript
const formatters = {
  volume: (v) => v === -Infinity ? '-∞' : v.toFixed(1) + ' dB',
  pan: (v) => {
    if (v === 0) return 'Center';
    return v > 0 ? `R${Math.abs(v).toFixed(0)}` : `L${Math.abs(v).toFixed(0)}`;
  },
  percentage: (v) => v.toFixed(0) + ' %',
  time: (v) => v.toFixed(2) + ' s',
  hz: (v) => v >= 1000 ? (v/1000).toFixed(1) + ' kHz' : v.toFixed(0) + ' Hz',
  semitones: (v) => (v >= 0 ? '+' : '') + v.toFixed(0) + ' st',
  speed: (v) => v.toFixed(2) + ' x',
};
```

---

## 🎨 Phase 2: 레이아웃 & Basic 탭

### 전체 구조

```
SoundEditorDialog
├── TitleBar (파일명, 닫기 버튼)
├── FileInfo (파일명, 길이, Cuts, Fades 등 메타)
├── WaveformSection (파형 + playhead + selection)
├── TabBar (Basic / EQ / Dynamics / Effects / Advanced)
├── TabContent (선택된 탭 내용)
│   ├── BasicTab (6개 노브 + 액션 버튼 + 프리셋)
│   ├── EQTab
│   ├── DynamicsTab
│   ├── EffectsTab
│   └── AdvancedTab
└── TransportBar (재생/정지, 마커, 루프, Apply/Close)
```

### Basic 탭 상세 스펙

#### 노브 6개 (각 노브별 설정)

| 노브 | min | max | default | unit | color | tier | formatter |
|------|-----|-----|---------|------|-------|------|-----------|
| Volume | -60 | +12 | 0 | dB | blue | 1 | volume |
| Pan | -100 | +100 | 0 | - | green | 1 | pan |
| Fade In | 0 | 10 | 0 | s | blue | 1 | time |
| Fade Out | 0 | 10 | 0 | s | blue | 1 | time |
| Speed | 0.5 | 2.0 | 1.0 | x | orange | 2 | speed |
| Pitch | -12 | +12 | 0 | st | orange | 2 | semitones |

*볼륨은 기술적으로는 -∞가 최소지만 UI에서는 -60dB를 "mute"로 처리*

#### 액션 버튼

- **Mute** (토글)
- **Solo** (토글)
- **Normalize** (단발 액션, 실행 시 Volume 자동 조정)
- **Reverse** (토글, 파형 뒤집기)
- **Fade Curve** (드롭다운: Linear / Exponential / Logarithmic)
- **Reset All** (확인 다이얼로그 후 모든 값 기본값으로)

#### 프리셋 (Basic 탭용)

```javascript
const basicPresets = {
  'Voice Recording': {
    volume: 3, pan: 0, fadeIn: 0.1, fadeOut: 0.3, 
    speed: 1.0, pitch: 0,
  },
  'Background Music': {
    volume: -6, pan: 0, fadeIn: 1.5, fadeOut: 2.0,
    speed: 1.0, pitch: 0,
  },
  'Game Audio': {
    volume: 0, pan: 0, fadeIn: 0, fadeOut: 0.2,
    speed: 1.0, pitch: 0,
  },
  'Podcast': {
    volume: 2, pan: 0, fadeIn: 0.5, fadeOut: 0.5,
    speed: 1.0, pitch: 0,
  },
};
```

---

## 🌊 Phase 3: 파형 디스플레이

### 요구사항
- 오디오 파일을 Web Audio API로 로드
- 파형을 Canvas 또는 SVG로 그리기
- Playhead 표시 (현재 재생 위치)
- Selection 영역 (드래그로 범위 선택)
- 줌 인/아웃 지원

### 파형 데이터 추출

```javascript
async function extractWaveformData(audioFile, samples = 1000) {
  const audioContext = new AudioContext();
  const arrayBuffer = await audioFile.arrayBuffer();
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
  
  const channelData = audioBuffer.getChannelData(0);  // 모노 또는 왼쪽
  const blockSize = Math.floor(channelData.length / samples);
  const waveform = [];
  
  for (let i = 0; i < samples; i++) {
    let sum = 0;
    for (let j = 0; j < blockSize; j++) {
      sum += Math.abs(channelData[i * blockSize + j]);
    }
    waveform.push(sum / blockSize);
  }
  
  return waveform;
}
```

### 파형 렌더링 (Canvas)

```javascript
function drawWaveform(canvas, waveformData, options = {}) {
  const { color = '#4a9bee', bgColor = '#000' } = options;
  const ctx = canvas.getContext('2d');
  const { width, height } = canvas;
  
  // 배경
  ctx.fillStyle = bgColor;
  ctx.fillRect(0, 0, width, height);
  
  // 파형
  const barWidth = width / waveformData.length;
  const centerY = height / 2;
  
  ctx.fillStyle = color;
  waveformData.forEach((amplitude, i) => {
    const barHeight = amplitude * centerY * 2;
    ctx.fillRect(
      i * barWidth, 
      centerY - barHeight / 2, 
      barWidth - 1, 
      barHeight
    );
  });
}
```

### Selection 인터랙션

```javascript
// 파형 위에서 드래그하면 범위 선택
onMouseDown(x) -> selectionStart = x
onMouseMove(x) -> selectionEnd = x (실시간 업데이트)
onMouseUp -> 선택 확정

// Shift+클릭으로 기존 선택 확장
// 더블클릭으로 선택 해제
// Ctrl+A로 전체 선택
```

---

## 🎵 Phase 4: Transport 컨트롤

### 버튼 구성

| 버튼 | 아이콘 | 기능 | 단축키 |
|------|--------|------|--------|
| Prev Marker | ⏮ | 이전 마커로 이동 | `,` |
| Play/Pause | ▶/⏸ | 재생/정지 | Space |
| Next Marker | ⏭ | 다음 마커로 이동 | `.` |
| Loop | 🔁 | 선택 영역 반복 재생 토글 | L |
| Add Marker | 📌 | 현재 위치에 마커 추가 | M |
| Time Display | 0:12.35 / 0:29.94 | 현재/전체 시간 | - |

### 우측 액션 버튼

- **Apply** — 변경사항을 실제 오디오에 적용 (파일 수정)
- **Export Audio** — 편집된 오디오를 새 파일로 저장
- **Close** — 창 닫기 (변경사항 무시 확인)

### Web Audio API 통합

```javascript
class AudioPlayer {
  constructor(audioBuffer) {
    this.context = new AudioContext();
    this.buffer = audioBuffer;
    this.source = null;
    this.gainNode = this.context.createGain();
    this.pannerNode = this.context.createStereoPanner();
    
    // 노드 체인: source -> gain -> panner -> destination
    this.gainNode.connect(this.pannerNode);
    this.pannerNode.connect(this.context.destination);
  }
  
  play(startTime = 0) {
    this.source = this.context.createBufferSource();
    this.source.buffer = this.buffer;
    this.source.playbackRate.value = this.speed;
    this.source.connect(this.gainNode);
    this.source.start(0, startTime);
  }
  
  setVolume(db) {
    // dB -> linear: gain = 10^(db/20)
    this.gainNode.gain.value = Math.pow(10, db / 20);
  }
  
  setPan(value) {
    // -100 ~ +100 -> -1 ~ +1
    this.pannerNode.pan.value = value / 100;
  }
  
  setSpeed(rate) {
    if (this.source) this.source.playbackRate.value = rate;
  }
}
```

---

## 🎚️ Phase 5: 다른 탭 상세 스펙

### EQ 탭

```javascript
// 3-Band EQ
const eqBands = [
  { name: 'LOW',  freq: 80,    gain: 0, q: 0.7, type: 'lowshelf'  },
  { name: 'MID',  freq: 1000,  gain: 0, q: 1.0, type: 'peaking'   },
  { name: 'HIGH', freq: 10000, gain: 0, q: 0.7, type: 'highshelf' },
];
```

각 밴드마다 3개 노브:
- **Freq**: 주파수 (로그 스케일)
- **Gain**: -12 ~ +12 dB
- **Q**: 0.1 ~ 10 (폭)

+ EQ 커브 실시간 시각화 (SVG 그래프)
+ 프리셋: Flat / Vocal Boost / Bass Boost / Podcast / Treble Cut

### Dynamics 탭

Compressor:
- **Threshold**: -60 ~ 0 dB
- **Ratio**: 1:1 ~ 20:1
- **Attack**: 0.1 ~ 100 ms (로그)
- **Release**: 10 ~ 1000 ms (로그)
- **Makeup Gain**: 0 ~ +24 dB
- **Knee**: 0 ~ 10 dB

Gate/Noise Reduction:
- **Threshold**: -80 ~ 0 dB
- **Reduction Amount**: 0 ~ 100%

### Effects 탭

Reverb:
- **Size**: 0 ~ 100%
- **Decay**: 0.1 ~ 10 s
- **Damping**: 0 ~ 100%
- **Mix (Dry/Wet)**: 0 ~ 100%
- 타입 선택: Room / Hall / Plate / Spring

Delay:
- **Time**: 0 ~ 2000 ms (또는 1/4, 1/8, 1/16 노트)
- **Feedback**: 0 ~ 95%
- **Mix**: 0 ~ 100%

### Advanced 탭

- **Ducking**: Threshold, Reduction, Attack, Release
- **De-esser**: Frequency (4~10kHz), Threshold, Reduction
- **Time Stretch**: Ratio (0.5x~2x), Algorithm (WSOLA/Phase Vocoder)
- **Markers**: 마커 리스트 + 이름 편집 + 삭제

---

## 💾 Phase 6: 프리셋 시스템

### 데이터 구조

```typescript
interface AudioPreset {
  id: string;
  name: string;
  tab: 'basic' | 'eq' | 'dynamics' | 'effects' | 'advanced';
  settings: Record<string, number | string>;
  createdAt: Date;
  isBuiltIn: boolean;  // 기본 제공 프리셋인지
}
```

### 저장 위치

- 로컬 스토리지 or 프로젝트 폴더의 `presets.json`
- 사용자 프리셋과 빌트인 프리셋을 분리 관리

### UI

- 각 탭 하단에 프리셋 버튼 리스트
- "+ Save Current" 버튼으로 현재 값 저장
- 사용자 프리셋은 우클릭으로 이름변경/삭제
- 빌트인 프리셋은 삭제 불가

---

## 🎨 디자인 토큰 (기존 시스템과 통일)

```css
/* 배경 계층 */
--bg-1: #000;        /* 가장 어두움 - 파형 */
--bg-2: #0f0f14;     /* 탭 컨텐츠 */
--bg-3: #1a1a1c;     /* 다이얼로그 본체 */
--bg-4: #2a2a30;     /* 타이틀바, 탭바 */
--bg-5: #3a3a3e;     /* 버튼 hover */

/* 테두리 */
--border-default: #2a2a30;
--border-hover: #3a3a3e;
--border-active: #378ADD;

/* 텍스트 */
--text-primary: #fff;
--text-secondary: #c8c8d0;
--text-tertiary: #8a8a92;
--text-disabled: #5a5a62;

/* 액센트 */
--accent-blue: #378ADD;
--accent-blue-light: #4a9bee;
--accent-green: #5DCAA5;
--accent-orange: #D85A30;

/* 스페이싱 */
--space-xs: 4px;
--space-sm: 8px;
--space-md: 12px;
--space-lg: 16px;
--space-xl: 20px;
--space-xxl: 24px;
```

---

## 🔧 구현 시 주의사항

### 1. 노브 드래그 중 커서 처리
```javascript
onMouseDown -> document.body.style.cursor = 'grabbing';
onMouseUp -> document.body.style.cursor = '';
```

### 2. 노브 드래그 중 마우스가 창 밖으로 나가도 계속 추적
```javascript
// window에 이벤트 리스너 등록 (노브 요소가 아니라)
window.addEventListener('mousemove', handleDrag);
window.addEventListener('mouseup', handleDragEnd);
```

### 3. 노브 값 부드럽게 변경 (optional)
```javascript
// requestAnimationFrame으로 smooth interpolation
function smoothUpdate(current, target, speed = 0.2) {
  return current + (target - current) * speed;
}
```

### 4. 파형 렌더링 최적화
- 줌 레벨에 따라 다운샘플링
- 가시 영역만 그리기 (virtual scrolling)
- Canvas 사용 추천 (SVG보다 빠름)

### 5. 실시간 프리뷰
- 노브 값 변경 시 오디오에 즉시 반영 (Web Audio API 노드 업데이트)
- Apply 버튼 누를 때 실제 파일 수정

### 6. 실행 취소/다시 실행
- 각 파라미터 변경을 history에 저장
- Ctrl+Z / Ctrl+Y 단축키

---

## 📦 추천 라이브러리

- **파형 표시**: [wavesurfer.js](https://wavesurfer-js.org/) (많이 쓰임)
- **오디오 처리**: Web Audio API (네이티브)
- **이펙트**: [Tone.js](https://tonejs.github.io/) (리버브, 딜레이 등 내장)
- **파일 처리**: [ffmpeg.wasm](https://ffmpegwasm.netlify.app/) (브라우저에서 오디오 변환)

---

## 🎯 구현 체크리스트

### Phase 1 ✅
- [ ] Knob 컴포넌트 기본 렌더링 (SVG)
- [ ] 드래그 인터랙션
- [ ] 마우스 휠 인터랙션
- [ ] Shift/Ctrl 정밀 모드
- [ ] 더블클릭 리셋
- [ ] 우클릭 메뉴
- [ ] 색상 variant (blue/green/orange)
- [ ] 값 포맷터 지원
- [ ] Bipolar 모드 (Pan)
- [ ] 로그 스케일 지원

### Phase 2 ✅
- [ ] SoundEditor 다이얼로그 레이아웃
- [ ] 타이틀바 + 파일 정보
- [ ] 탭 네비게이션
- [ ] Basic 탭 6개 노브
- [ ] 액션 버튼 (Mute, Solo, Normalize, Reverse, Reset)

### Phase 3 ✅
- [ ] 오디오 파일 로드 (Web Audio API)
- [ ] 파형 데이터 추출
- [ ] Canvas로 파형 렌더링
- [ ] Playhead 표시 및 이동
- [ ] Selection 영역 (드래그로 범위 선택)
- [ ] 줌 인/아웃

### Phase 4 ✅
- [ ] 재생/정지
- [ ] 시간 표시
- [ ] 마커 추가/이동
- [ ] 루프 재생
- [ ] Apply / Export / Close

### Phase 5 ✅
- [ ] EQ 탭 (3-Band + 커브 시각화)
- [ ] Dynamics 탭 (Compressor + Noise Reduction)
- [ ] Effects 탭 (Reverb + Delay)
- [ ] Advanced 탭 (Ducking, De-esser, Time Stretch, Markers)

### Phase 6 ✅
- [ ] 프리셋 저장
- [ ] 프리셋 불러오기
- [ ] 프리셋 편집/삭제
- [ ] 빌트인 프리셋 제공

---

## 💡 Claude Code 프롬프트

위 문서를 전달할 때 이렇게 요청하세요:

```
design-reference/SOUND_EDITOR_SPEC.md를 읽고 
design-reference/sound_editor_knob_ui.html을 시각 레퍼런스로 참고해서 
사운드 편집 창을 업그레이드해줘.

### 우선순위
1. Phase 1 (조그 노브 컴포넌트)을 먼저 완성
2. Phase 2 (Basic 탭)까지 구현한 후 나에게 보여줘
3. 내가 확인한 뒤에 Phase 3 이후 진행

### 요구사항
- 조그 노브는 재사용 가능한 컴포넌트로
- 3가지 조작 방식(드래그/휠/정밀) 모두 지원
- 기존 디자인 시스템(색상, 간격)과 일치
- 현재 오디오 파일 로드 기능은 유지

Phase 1과 Phase 2가 완성되면 스크린샷 보여줘.
```
