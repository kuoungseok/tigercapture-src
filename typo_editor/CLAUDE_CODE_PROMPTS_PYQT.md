# Claude Code 전달 프롬프트 (PyQt 버전)

## 📦 프로젝트에 복사할 파일

```
your-project/
├── design-reference/                          ← 새로 만들기
│   ├── TYPOGRAPHY_SPEC_PYQT.md               ← 메인 기획서 ⭐
│   ├── japanese_mv_typography_showcase.html  ← 비주얼 참고 1
│   ├── folding_typography.html               ← 비주얼 참고 2
│   ├── typography_editor_mockup.html         ← UI 레이아웃 참고
│   └── jp_instagram_typography.html          ← 비주얼 참고 4
├── src/
└── ...
```

---

## 🎯 프롬프트 1: 시작 메시지 (이걸 먼저!)

```
우리 PyQt 기반 영상 편집 툴에 전문 타이포그래피 애니메이션 
시스템을 추가하려고 해.

### 먼저 이것부터 읽어줘 (순서대로)
1. design-reference/TYPOGRAPHY_SPEC_PYQT.md ← 메인 기획서
2. design-reference/japanese_mv_typography_showcase.html (브라우저로 열어서 비주얼 확인)
3. design-reference/folding_typography.html (글자 꺾임 애니메이션)
4. design-reference/typography_editor_mockup.html (에디터 UI)

### 중요 사항
- HTML 파일들은 **목표 비주얼 참고용**. 실제 구현은 PyQt (Qt)로!
- CSS 애니메이션을 PyQt의 QPropertyAnimation으로 변환해야 함
- QGraphicsScene + QGraphicsTextItem으로 텍스트 렌더링
- 기획서에 각 애니메이션의 PyQt 구현 예시 코드 있음

### 진행 방식
- Phase 1부터 차례대로 (절대 한 번에 다 하지 말 것)
- 각 Phase 시작 전에 구현 계획 먼저 알려주기
- Phase 완료 시 동작 영상이나 스크린샷 보여주기
- 내 승인 후 다음 Phase

### 프로젝트 현재 상태
- 기술 스택: [PyQt6 / PySide6 / PyQt5 중 어떤 건지 Claude Code가 확인]
- 기존 타임라인 구조: [기존 코드 분석 필요]

### 첫 번째 작업
1. 기획서 읽고 이해했는지 요약 보고
2. 현재 프로젝트 구조 분석 (어디에 뭘 추가해야 할지)
3. Phase 1 (텍스트 트랙 시스템) 구현 계획 제안
4. 승인 요청
```

---

## 🎯 프롬프트 2: Phase 1 - 텍스트 트랙 시스템

```
TYPOGRAPHY_SPEC_PYQT.md의 "Phase 1: 텍스트 트랙 시스템"을 구현해줘.

### 구현할 것
1. TextTrack 위젯 (기존 비디오/오디오 트랙과 동일 구조)
2. TextClip 위젯 (기획서의 paintEvent 예시 참고)
3. 좌측 툴바에 드래그 가능한 "T" 아이콘
4. T 아이콘 → 텍스트 트랙 드래그 앤 드롭 → 클립 생성
5. 클립 이동 (중앙 드래그)
6. 클립 길이 조절 (가장자리 드래그)
7. 우클릭 메뉴: Duplicate, Delete
8. 더블클릭: 시그널 emit (에디터는 Phase 2에서 연결)

### 시각 디자인
- 배경: 주황→핑크 그라데이션 (QLinearGradient)
- 테두리: 2px #D85A30
- T 아이콘 + 텍스트 미리보기 (앞 20자)
- 하단에 In/Hold/Out 타이밍 바 (초록/중간/주황)

### 데이터 모델
기획서의 TextClip dataclass를 models.py에 구현.

### 완료 조건
- 타임라인에 텍스트 트랙 표시됨
- T 아이콘 드래그로 클립 생성됨
- 클립 이동/리사이즈 부드럽게 작동
- 더블클릭 시 콘솔에 "Open editor for clip <id>" 출력
- 우클릭 메뉴 작동

### 주의
- Qt의 시그널/슬롯 사용 (MainWindow 의존성 줄이기)
- PyQt5/6 또는 PySide6 버전 확인 후 해당 API 사용
```

---

## 🎯 프롬프트 3: Phase 2 - 타이포 에디터 UI

```
TYPOGRAPHY_SPEC_PYQT.md의 "Phase 2: 에디터 모달 UI"를 구현.

### 시각 레퍼런스
design-reference/typography_editor_mockup.html
→ 브라우저로 열어서 레이아웃 확인

### 구현할 것
1. TypographyEditorDialog (QDialog 상속)
2. 클립 더블클릭 → 이 다이얼로그 오픈
3. 3-pane 레이아웃:
   - 좌: 텍스트 입력 (QTextEdit)
   - 중: 애니메이션 선택 (플레이스홀더 - Phase 3에서 채움)
   - 우: 스타일 설정 (폰트/크기/색상/정렬)
4. 상단: 실시간 프리뷰 영역 (QGraphicsView)
5. 하단: Save as Template / Cancel / Apply 버튼

### 실시간 반영
- 텍스트 변경 → 프리뷰 즉시 업데이트
- 스타일 변경 → 프리뷰 즉시 업데이트
- (애니메이션은 Phase 3에서 연결)

### 스타일 컨트롤
- Font Family: QComboBox (Noto Sans JP, Shippori Mincho, Pretendard 등)
- Font Size: QSlider + QSpinBox (16~200)
- Font Weight: QButtonGroup (Thin/Regular/Bold/Black)
- Color: QColorDialog 버튼
- Alignment: 버튼 3개 (Left/Center/Right)

### 완료 조건
- 클립 더블클릭 → 다이얼로그 열림
- 텍스트/폰트/크기/색상 변경 가능
- 프리뷰에 즉시 반영
- Apply 누르면 클립에 저장, Cancel은 취소

### Phase 3 준비
- 애니메이션 pane은 "Coming soon" 플레이스홀더
- 실제 애니메이션 선택은 다음 단계에서
```

---

## 🎯 프롬프트 4: Phase 3 - Basic + Folding 애니메이션

```
TYPOGRAPHY_SPEC_PYQT.md의 "Phase 3"를 구현.

### 먼저 구조 잡기
src/typography/animations/ 디렉토리 생성:
- base.py (BaseAnimation 추상 클래스)
- registry.py (애니메이션 등록 시스템)
- basic/ (Fade, Slide, Zoom, Pop)
- folding/ (Paper Fold, Joint Break, 3D Flip, Flag Wave, Angle Break)

### BaseAnimation 구현
기획서의 BaseAnimation 클래스 참고. 다음 메서드:
- build() - 추상 메서드
- start(), stop(), pause()
- create_text_item()
- split_text() - 글자 단위 분리 + 한자/가나 감지

### 우선순위대로 구현

#### 1. Fade In/Out (가장 쉬움)
QGraphicsOpacityEffect + QPropertyAnimation
기획서에 완성 코드 있음

#### 2. Slide In/Out
QPropertyAnimation(item, b"pos")로 위치 애니메이션

#### 3. Zoom In/Out
QPropertyAnimation(item, b"scale")

#### 4. Pop
스케일 애니메이션 + QEasingCurve.OutBack

#### 5. Paper Fold (종이접기)
- QTransform rotate X축
- 또는 QGraphicsItem의 setTransform()
- 글자 한가운데를 축으로 반으로 접힘

#### 6. Joint Break (관절 꺾임)
글자마다 QPropertyAnimation rotation
transform-origin = bottom center

#### 7. 3D Flip
setRotation() 대신 QTransform으로 Y축 회전 시뮬레이션
또는 QGraphicsRotation 사용 (Qt의 3D 회전)

#### 8. Flag Wave
글자별 순차 딜레이 + 회전

#### 9. Angle Break ⭐ (우타이테 시그니처!)
기획서에 완성 코드 있음.
각 글자마다 다른 transform origin + 각도 시퀀스.

### 애니메이션 Pane 연결
Phase 2에서 플레이스홀더로 만든 애니메이션 pane을 실제로 작동하게:
- 카테고리 탭 (Basic, Folding)
- 각 카테고리 안에 애니메이션 카드 (아이콘 + 이름)
- 클릭 시 해당 애니메이션 선택
- 프리뷰에 즉시 반영

### In/Hold/Out 타이밍 슬라이더
- 각각 QSlider (0 ~ 5초, 0.1초 단위)
- 값 변경 시 프리뷰 재생

### 테스트 포인트
각 애니메이션마다 독립적으로 실행 가능하도록:
- 파일 끝에 if __name__ == "__main__": 블록
- 단독 실행으로 해당 애니메이션만 테스트
```

---

## 🎯 프롬프트 5: Phase 4 - 특화 프리셋

```
TYPOGRAPHY_SPEC_PYQT.md의 "Phase 4: 특화 프리셋" 구현.

### 구현할 프리셋 (우선순위 순)

#### Utaite 6개 (가장 중요!)
1. **Ado 폭발** - 기획서에 완성 코드 있음
   - 메인 텍스트 + 빨간 그림자 분리
   - 블러 → 선명 + 스케일 애니메이션
   
2. **Eve 글리치** - 기획서에 완성 코드 있음
   - RGB 3레이어 (Cyan/Magenta/White)
   - QTimer로 주기적 글리치
   - 스캔라인 overlay
   
3. **須田景凪 여백** 
   - 단순 Fade + 얇은 선
   - 별 장식 (★)
   - 작은 글씨 + 영문 서브
   
4. **まふまふ 판타지**
   - 자줏빛 배경
   - Blur에서 선명하게 올라옴
   - 장식 문자 (✧ ✦)
   
5. **YOASOBI 가사 립싱크**
   - 글자별 순차 하이라이트
   - 이전/현재/다음 가사 3줄 표시
   - 현재 글자만 파란색 + glow
   
6. **일영 믹스**
   - 일본어 원가사 + 영어 번역
   - 둘 다 다른 스타일/타이밍

### Niconico 3개
7. **합창 멤버 크레딧** - 가장 복잡!
   - ChorusMember 데이터 모델 먼저
   - 9명 멤버 + 각자 색상
   - 순차 등장 (memberPop 애니메이션)
   
8. **실시간 파트 표시**
   - A멜로/B멜로/사비 색상 전환
   - 파트별 싱어 이름 표시
   
9. **타이틀 카드**
   - 네온 라인 좌우에서 확장
   - 타이틀 중앙 등장
   - 일본어 + 영문 서브

### DEVILA 2개
10. **EDM 드롭 레이저**
    - 3개 레이저 선 (핑크/시안/옐로우)
    - 중앙 타이틀 폭발 등장
    - 그리드 배경
    
11. **사이키 스트로브** ⚠️
    - **광민감성 경고 다이얼로그 먼저 필수!**
    - 사용자 확인 후에만 작동
    - 초당 3회 이하로 제한

### 프리셋 매니저 구현
기획서의 PresetManager 클래스:
- 빌트인 프리셋 로드 (builtin_presets.py)
- 사용자 프리셋 JSON으로 저장/로드
- 카테고리별 필터링

### 프리셋 pane
- 애니메이션 pane 옆에 프리셋 pane 추가 (또는 탭)
- 카테고리별로 프리셋 목록
- 클릭 시 애니메이션 + 스타일 일괄 적용

### 광민감성 경고 시스템
```python
def show_epilepsy_warning() -> bool:
    """스트로브 사용 전 경고 다이얼로그"""
    from PySide6.QtWidgets import QMessageBox
    
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle("⚠️ 광민감성 발작 주의")
    msg.setText(
        "이 효과는 빠른 플래시를 포함합니다.\n"
        "광민감성 발작 경험이 있거나 해당 증상이 있는 분은 "
        "사용을 자제해주세요."
    )
    msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    msg.button(QMessageBox.Ok).setText("알고 있습니다")
    msg.button(QMessageBox.Cancel).setText("취소")
    
    return msg.exec() == QMessageBox.Ok
```
```

---

## 🎯 프롬프트 6: Phase 5 - Export 기능

```
TYPOGRAPHY_SPEC_PYQT.md의 "Phase 5: Export 기능"을 구현.

### 목표
타이포 애니메이션이 최종 영상에 포함되어 Export되도록.

### 구현 방식

#### 1. 프레임 렌더링 엔진
각 시간별로 QImage 생성:
- 60fps로 3초 애니메이션 = 180 프레임
- 각 프레임은 해당 시간의 애니메이션 상태

#### 2. 애니메이션 상태 계산
시간 기반으로 각 글자의 위치/회전/투명도 계산:
```python
def calculate_state(self, time: float) -> dict:
    """특정 시간의 애니메이션 상태"""
    if time < self.config.in_duration:
        # In 단계
        progress = time / self.config.in_duration
        return self._interpolate_in(progress)
    elif time < self.config.in_duration + self.hold_duration:
        # Hold 단계
        progress = (time - self.config.in_duration) / self.hold_duration
        return self._interpolate_hold(progress)
    else:
        # Out 단계
        progress = (time - self.config.in_duration - self.hold_duration) / self.config.out_duration
        return self._interpolate_out(progress)
```

#### 3. QImage로 렌더
QPainter로 계산된 상태를 이미지에 그리기

#### 4. FFmpeg로 비디오화
프레임 PNG들을 FFmpeg 서브프로세스로 MP4 생성

### 성능
- QThread 사용 (UI 블록 방지)
- 진행률 QProgressBar로 표시
- 취소 가능

### 기존 비디오와 합성
- 비디오 트랙의 영상 위에 텍스트 오버레이
- FFmpeg filter_complex로 합성
```

---

## 🎯 프롬프트 7: 디버깅/문제 해결

### 애니메이션이 끊길 때
```
Phase 3의 [애니메이션 이름]이 끊겨서 나와.

### 확인할 것
1. QPropertyAnimation의 duration 단위 (ms인지 초인지)
2. EasingCurve 설정
3. setKeyValueAt의 progress 값 (0.0 ~ 1.0)
4. 글자 수 × 애니메이션 = 너무 많은지 확인

### 원본 레퍼런스
design-reference/[해당 HTML]에서 어떻게 움직이는지 확인.
브라우저에서 열어서 비교.

### 디버깅 정보
현재 구현 코드와 실행 결과(스크린샷 or 영상) 보여줘.
QTimer interval 값과 animation duration 값 알려줘.
```

### 글자가 깨져 보일 때
```
[애니메이션 이름]에서 글자가 겹치거나 깨져보여.

### 확인
1. 폰트가 제대로 로드됐는지 (QFontDatabase.families())
2. 일본어/한글 폰트 시스템에 있는지
3. QGraphicsTextItem의 크기 계산 (boundingRect)
4. setPos로 위치 설정 제대로 했는지

### 폰트 fallback
시스템 폰트 없으면 어떻게 할지:
- 번들 폰트 로드 (QFontDatabase.addApplicationFont)
- 또는 폰트 없을 때 경고

현재 코드와 스크린샷 공유해줘.
```

---

## 🎯 프롬프트 8: 최종 점검

```
Phase 1~5 완료. 최종 점검 해보자.

### 통합 테스트 시나리오

#### 시나리오 1: Ado 커버 영상
1. 비디오 파일 로드 (우타이테 커버)
2. 오디오 파일 로드
3. "うっせぇわ" 텍스트 클립 10~13초에 추가
4. Ado 폭발 프리셋 적용
5. Export (1080p 60fps)
6. 결과 확인

#### 시나리오 2: 니코니코 합창
1. 합창 멤버 5명 등록 (이름 + 색상)
2. 곡 시작 0~3초에 멤버 크레딧 클립 추가
3. 3~15초 파트별 가사 추가 (A멜로 → B멜로 → 사비)
4. 각 파트에 "실시간 파트 표시" 프리셋
5. Export

#### 시나리오 3: DEVILA 리믹스
1. 드롭 지점에 "EDM 드롭 레이저" 추가
2. 사비 클라이맥스에 "사이키 스트로브" 추가
   → 경고 다이얼로그 확인
3. Export

### 확인사항
- [ ] 모든 애니메이션 정상 재생
- [ ] 프리뷰와 Export 결과 일치
- [ ] Export 영상 품질 문제없음
- [ ] 프리셋 저장/로드 정상
- [ ] 광민감성 경고 정상
- [ ] 한자 감지 정확
- [ ] UI 반응성 좋음

각 시나리오 결과 영상이나 스크린샷 공유.
문제 있는 부분 정리해줘.
```

---

## 💡 PyQt 특화 팁

### 1. 시그널 명확히
```python
# 좋은 예
class TextClipWidget(QWidget):
    clicked = Signal(str)  # clip_id
    double_clicked = Signal(str)
    resized = Signal(str, float, float)  # clip_id, start, end
    
# 나쁜 예
class TextClipWidget(QWidget):
    def __init__(self, parent, main_window):
        self.main_window = main_window  # 강결합!
```

### 2. QGraphicsScene 활용
텍스트 클립이 많아지면 일반 QWidget으로는 한계.
QGraphicsScene 사용하면 수백 개도 가능.

### 3. 스레딩
Export처럼 오래 걸리는 작업은 QThread로:
```python
class ExportWorker(QThread):
    progress = Signal(int)
    finished = Signal(str)  # output_path
    
    def run(self):
        # 실제 렌더링
        pass
```

### 4. 리소스 관리
폰트, 이미지는 프로젝트에 번들:
```
resources/
├── fonts/
│   ├── NotoSansJP-Regular.ttf
│   ├── NotoSansJP-Bold.ttf
│   └── ShipporiMincho-Regular.ttf
└── icons/
    └── t_icon.svg
```

### 5. 디버깅
```python
# QPropertyAnimation 상태 확인
print(animation.state())        # Stopped / Paused / Running
print(animation.currentTime())  # ms
print(animation.duration())     # ms

# QGraphicsItem 확인
print(item.pos())
print(item.rotation())
print(item.scale())
print(item.boundingRect())
```

---

## 📋 최종 체크리스트

Claude Code에 전달 전 확인:

- [ ] `design-reference/` 폴더 생성
- [ ] TYPOGRAPHY_SPEC_PYQT.md 복사
- [ ] HTML 레퍼런스 4개 복사
- [ ] 프롬프트 1 (시작) 준비
- [ ] PyQt 버전 확인 (PyQt5/6 또는 PySide6)
- [ ] 기존 타임라인 코드 위치 파악
- [ ] Git 커밋 (백업!)

---

## ⚠️ 마지막 당부

1. **HTML은 비주얼 참고용**이지 코드 참고용 아님
2. CSS 애니메이션 → PyQt QPropertyAnimation 변환 필수
3. 각 Phase 완료 시 **반드시 확인** 후 진행
4. 성능 문제 생기면 **QGraphicsScene** 적극 활용
5. **Export가 가장 오래 걸림** (60fps 렌더링은 시간 많이 걸림)

Good luck! 🎬
