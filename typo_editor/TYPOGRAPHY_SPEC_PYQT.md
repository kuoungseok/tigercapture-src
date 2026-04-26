# 타이포그래피 애니메이션 시스템 기획서 (PyQt 버전)

> **PyQt 기반 영상 편집 툴에 전문 타이포그래피 애니메이션 기능 추가**  
> 범위: 타이포 애니메이션만 (우타이테 + 니코니코 + DEVILA + 꺾임)  
> 우선순위: 표준 (MVP + 주요 프리셋)

---

## 📌 프로젝트 개요

### 목표
기존 PyQt 기반 영상 편집 툴의 타임라인에 **"텍스트 트랙"**을 추가하고, 
더블클릭으로 열리는 **타이포그래피 에디터**를 구현한다.

### 차별화 포인트
- 🎤 **우타이테 MV 스타일** 프리셋 (Ado, Eve, 須田景凪, まふまふ 등)
- 🌀 **니코니코 합창** 시스템 (멤버 크레딧, 파트별 색상)
- ⚡ **DEVILA/EDM 리믹스** 스타일 (레이저, 스트로브, 카오스)
- 🔨 **글자 꺾임 애니메이션** 다수 (종이접기, 관절 꺾임, 각도 꺾임)

### MVP 범위 (이것만 먼저!)
1. 텍스트 트랙 + 클립 시스템
2. 타이포 에디터 모달 (3-pane)
3. **핵심 애니메이션 20개** (전체 49개 중 가장 인기 있는 것)
4. 기본 스타일 시스템
5. 프리셋 저장/불러오기

---

## 🛠️ 기술 스택

### 필수 라이브러리

```python
# requirements.txt
PyQt6>=6.6.0              # 또는 PySide6 (권장)
# 또는: PyQt5, PySide2 (구버전)

# 애니메이션 및 그래픽
# PyQt 내장: QGraphicsScene, QPropertyAnimation

# 추가 기능
Pillow>=10.0.0            # 이미지 처리
numpy>=1.24.0             # 수치 계산
```

### 왜 PySide6 권장?
- Qt의 공식 Python 바인딩
- LGPL 라이선스 (상업적 사용 자유)
- PyQt6와 거의 동일한 API
- Qt 6의 최신 기능 사용 가능

### 핵심 Qt 모듈
- **QtWidgets**: UI 컴포넌트 (에디터 모달, 버튼, 슬라이더)
- **QtGui**: 폰트, 색상, 페인팅
- **QtCore**: `QPropertyAnimation`, `QTimer`, 시그널/슬롯
- **QtGraphicsScene**: 타이포 렌더링 (핵심!)

---

## 🏗️ 아키텍처

### 전체 구조

```
src/
├── timeline/
│   ├── text_track.py              # 텍스트 트랙 위젯
│   └── text_clip.py               # 텍스트 클립 위젯
│
├── typography/
│   ├── editor_dialog.py           # 타이포 에디터 모달
│   ├── preview_widget.py          # 실시간 프리뷰
│   │
│   ├── panes/
│   │   ├── text_input_pane.py     # 좌측: 텍스트 입력
│   │   ├── animation_pane.py      # 중앙: 애니메이션 선택
│   │   └── style_pane.py          # 우측: 스타일 설정
│   │
│   ├── animations/
│   │   ├── base.py                # 애니메이션 베이스 클래스
│   │   ├── basic/                 # 기본 (Fade, Slide, Zoom, Pop)
│   │   ├── folding/               # 꺾임 (9개)
│   │   ├── utaite/                # 우타이테 (8개)
│   │   ├── niconico/              # 니코니코 합창 (5개)
│   │   └── devila/                # DEVILA (5개)
│   │
│   ├── presets/
│   │   ├── preset_manager.py      # 프리셋 로드/저장
│   │   └── builtin_presets.py     # 빌트인 프리셋 정의
│   │
│   └── models.py                  # 데이터 모델 (TextClip, Preset 등)
│
└── utils/
    ├── korean_detector.py         # 한글 감지
    └── japanese_detector.py       # 한자/가나 감지
```

---

## 🎯 데이터 모델 (Python)

### TextClip

```python
from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

@dataclass
class TextStyle:
    font_family: str = "Noto Sans JP"
    font_size: int = 48
    font_weight: int = 700  # 100-900
    color: str = "#FFFFFF"
    alignment: str = "center"  # "left" | "center" | "right"
    letter_spacing: int = 0
    line_height: float = 1.2
    
    # 위치 (화면 비율, 0.0 ~ 1.0)
    position_x: float = 0.5
    position_y: float = 0.5
    rotation: float = 0.0
    
    # 효과
    outline_color: Optional[str] = None
    outline_width: int = 0
    
    shadow_color: Optional[str] = None
    shadow_offset_x: int = 0
    shadow_offset_y: int = 0
    shadow_blur: int = 0
    
    background_color: Optional[str] = None
    background_padding: int = 0
    background_radius: int = 0


@dataclass
class AnimationConfig:
    preset_id: str = "basic-fade"
    in_animation: str = "fade-in"
    hold_animation: str = "none"
    out_animation: str = "fade-out"
    
    in_duration: float = 0.5      # 초
    out_duration: float = 0.5
    # hold_duration = clip_duration - in - out (자동)
    
    custom_params: dict = field(default_factory=dict)


@dataclass
class TextClip:
    id: str = field(default_factory=lambda: str(uuid4()))
    track_id: str = ""
    
    # 타이밍 (프레임 단위 또는 초)
    start_time: float = 0.0  # 초
    end_time: float = 2.0
    
    # 콘텐츠
    text: str = "Enter text..."
    
    # 애니메이션 & 스타일
    animation: AnimationConfig = field(default_factory=AnimationConfig)
    style: TextStyle = field(default_factory=TextStyle)
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def hold_duration(self) -> float:
        return max(0, self.duration - self.animation.in_duration - self.animation.out_duration)


@dataclass
class TypographyPreset:
    id: str
    name: str
    category: str  # 'basic' | 'folding' | 'utaite' | 'niconico' | 'devila'
    
    animation: AnimationConfig
    style: TextStyle
    
    description: str = ""
    reference_artist: str = ""  # "Ado", "Eve" 등
    thumbnail_path: str = ""
    is_builtin: bool = True
```

---

## 🎨 UI 구현 (PyQt)

### 1. 텍스트 클립 위젯

```python
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QLinearGradient, QColor, QPen

class TextClipWidget(QWidget):
    """타임라인에 표시되는 텍스트 클립"""
    
    double_clicked = Signal(str)  # clip_id 전달
    
    def __init__(self, clip: TextClip, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.setMinimumHeight(50)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
    
    def paintEvent(self, event):
        """클립 시각 디자인"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        
        # 1. 배경 그라데이션 (보라 → 핑크)
        gradient = QLinearGradient(0, 0, rect.width(), 0)
        gradient.setColorAt(0, QColor(216, 90, 48, 80))   # 주황
        gradient.setColorAt(1, QColor(184, 63, 173, 80))  # 핑크
        painter.fillRect(rect, gradient)
        
        # 2. 테두리
        pen = QPen(QColor("#D85A30"), 2)
        painter.setPen(pen)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)
        
        # 3. T 아이콘 + 텍스트 미리보기
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(self.font())
        
        preview_text = self.clip.text[:20]  # 앞 20글자만
        if len(self.clip.text) > 20:
            preview_text += "..."
        painter.drawText(
            rect.adjusted(30, 5, -5, -15),
            Qt.AlignLeft | Qt.AlignTop,
            preview_text
        )
        
        # 4. In/Hold/Out 타이밍 바
        self._draw_timing_bar(painter, rect)
    
    def _draw_timing_bar(self, painter: QPainter, rect: QRect):
        """하단에 In/Hold/Out 시각화"""
        bar_y = rect.height() - 10
        bar_rect = QRect(5, bar_y, rect.width() - 10, 4)
        
        total = self.clip.duration
        in_ratio = self.clip.animation.in_duration / total
        out_ratio = self.clip.animation.out_duration / total
        
        # In (초록)
        in_width = int(bar_rect.width() * in_ratio)
        painter.fillRect(
            QRect(bar_rect.x(), bar_rect.y(), in_width, bar_rect.height()),
            QColor("#5DCAA5")
        )
        
        # Hold (중간)
        hold_x = bar_rect.x() + in_width
        hold_width = bar_rect.width() - in_width - int(bar_rect.width() * out_ratio)
        painter.fillRect(
            QRect(hold_x, bar_rect.y(), hold_width, bar_rect.height()),
            QColor(255, 255, 255, 50)
        )
        
        # Out (주황)
        out_x = hold_x + hold_width
        out_width = bar_rect.width() - in_width - hold_width
        painter.fillRect(
            QRect(out_x, bar_rect.y(), out_width, bar_rect.height()),
            QColor("#D85A30")
        )
    
    def mouseDoubleClickEvent(self, event):
        """더블클릭 시 에디터 열기"""
        self.double_clicked.emit(self.clip.id)
```

### 2. 타이포 에디터 모달

```python
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt

class TypographyEditorDialog(QDialog):
    def __init__(self, clip: TextClip, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.setWindowTitle(f"Typography Editor — {clip.text[:30]}")
        self.setModal(True)
        self.resize(1200, 800)
        self._setup_ui()
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # 상단: 프리뷰
        self.preview = TypographyPreview(self.clip)
        main_layout.addWidget(self.preview, 2)
        
        # 재생 컨트롤
        controls = self._create_playback_controls()
        main_layout.addLayout(controls)
        
        # 중단: 3-pane 레이아웃
        panes_layout = QHBoxLayout()
        
        self.text_pane = TextInputPane(self.clip)
        self.animation_pane = AnimationPane(self.clip)
        self.style_pane = StylePane(self.clip)
        
        # 변경 시 실시간 반영
        self.text_pane.changed.connect(self._update_preview)
        self.animation_pane.changed.connect(self._update_preview)
        self.style_pane.changed.connect(self._update_preview)
        
        panes_layout.addWidget(self.text_pane, 1)
        panes_layout.addWidget(self.animation_pane, 2)
        panes_layout.addWidget(self.style_pane, 1)
        
        main_layout.addLayout(panes_layout, 3)
        
        # 하단: 액션 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("Save as Template")
        cancel_btn = QPushButton("Cancel")
        apply_btn = QPushButton("Apply")
        apply_btn.setDefault(True)
        
        cancel_btn.clicked.connect(self.reject)
        apply_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addSpacing(20)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(apply_btn)
        
        main_layout.addLayout(btn_layout)
    
    def _update_preview(self):
        """어떤 값이든 바뀌면 프리뷰 재생성"""
        self.preview.update_clip(self.clip)
```

### 3. 실시간 프리뷰 (핵심!)

```python
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtCore import QPropertyAnimation, QParallelAnimationGroup, QEasingCurve
from PySide6.QtGui import QFont, QColor, QBrush

class TypographyPreview(QGraphicsView):
    """애니메이션 실시간 프리뷰 영역"""
    
    def __init__(self, clip: TextClip, parent=None):
        super().__init__(parent)
        self.clip = clip
        
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QBrush(QColor("#000000")))
        self.scene.setSceneRect(0, 0, 1920, 1080)  # 16:9 영상 기준
        
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        
        self.current_animation = None
        self._render_clip()
    
    def update_clip(self, clip: TextClip):
        """클립 업데이트 시 재렌더"""
        self.clip = clip
        self._render_clip()
    
    def _render_clip(self):
        """현재 클립 설정으로 애니메이션 생성"""
        # 기존 애니메이션 정리
        if self.current_animation:
            self.current_animation.stop()
        self.scene.clear()
        
        # 애니메이션 레지스트리에서 가져오기
        from .animations import get_animation
        
        animation_class = get_animation(self.clip.animation.preset_id)
        self.current_animation = animation_class(
            text=self.clip.text,
            style=self.clip.style,
            config=self.clip.animation,
            scene=self.scene,
        )
        
        self.current_animation.start()
    
    def play(self):
        if self.current_animation:
            self.current_animation.start()
    
    def pause(self):
        if self.current_animation:
            self.current_animation.pause()
    
    def resizeEvent(self, event):
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        super().resizeEvent(event)
```

---

## 🎬 애니메이션 구현 (PyQt 네이티브)

### 베이스 클래스

```python
from abc import ABC, abstractmethod
from PySide6.QtCore import QPropertyAnimation, QParallelAnimationGroup, QEasingCurve
from PySide6.QtWidgets import QGraphicsTextItem, QGraphicsScene
from PySide6.QtGui import QFont, QColor

class BaseAnimation(ABC):
    """모든 타이포 애니메이션의 베이스"""
    
    ID = "base"
    NAME = "Base"
    CATEGORY = "basic"
    
    def __init__(
        self,
        text: str,
        style: TextStyle,
        config: AnimationConfig,
        scene: QGraphicsScene,
    ):
        self.text = text
        self.style = style
        self.config = config
        self.scene = scene
        self.animation_group = QParallelAnimationGroup()
        self.items = []  # 글자 단위 QGraphicsItem들
    
    @abstractmethod
    def build(self):
        """씬에 아이템 추가 및 애니메이션 구성"""
        pass
    
    def start(self):
        self.build()
        self.animation_group.start()
    
    def stop(self):
        self.animation_group.stop()
    
    def pause(self):
        self.animation_group.pause()
    
    def create_text_item(self, char: str, x: float, y: float) -> QGraphicsTextItem:
        """글자 하나를 QGraphicsTextItem으로 생성"""
        item = QGraphicsTextItem(char)
        
        font = QFont(self.style.font_family, self.style.font_size)
        font.setWeight(self.style.font_weight)
        item.setFont(font)
        
        item.setDefaultTextColor(QColor(self.style.color))
        item.setPos(x, y)
        
        # 회전 중심을 중앙으로
        bounding = item.boundingRect()
        item.setTransformOriginPoint(bounding.center())
        
        self.scene.addItem(item)
        self.items.append(item)
        return item
    
    def split_text(self) -> list[tuple[str, str]]:
        """텍스트를 글자 단위로 분리 + 한자/가나/한글 타입 분류"""
        result = []
        for char in self.text:
            code = ord(char)
            if 0x4E00 <= code <= 0x9FFF:
                char_type = "kanji"
            elif 0x3040 <= code <= 0x309F:
                char_type = "hiragana"
            elif 0x30A0 <= code <= 0x30FF:
                char_type = "katakana"
            elif 0xAC00 <= code <= 0xD7A3:
                char_type = "hangul"
            else:
                char_type = "other"
            result.append((char, char_type))
        return result
```

### 예시 1: Fade In (가장 간단)

```python
from PySide6.QtWidgets import QGraphicsOpacityEffect

class FadeInAnimation(BaseAnimation):
    ID = "basic-fade-in"
    NAME = "Fade In"
    CATEGORY = "basic"
    
    def build(self):
        # 텍스트 아이템 생성
        item = self.create_text_item(self.text, 960, 540)
        
        # 중앙 정렬
        bounding = item.boundingRect()
        item.setPos(
            960 - bounding.width() / 2,
            540 - bounding.height() / 2
        )
        
        # 투명도 효과
        opacity_effect = QGraphicsOpacityEffect()
        opacity_effect.setOpacity(0.0)
        item.setGraphicsEffect(opacity_effect)
        
        # 애니메이션
        anim = QPropertyAnimation(opacity_effect, b"opacity")
        anim.setDuration(int(self.config.in_duration * 1000))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        
        self.animation_group.addAnimation(anim)
```

### 예시 2: 각도 꺾임 (우타이테 스타일!)

```python
from PySide6.QtCore import QPointF

class AngleBreakAnimation(BaseAnimation):
    """각 글자가 서로 다른 방향으로 꺾이는 애니메이션"""
    
    ID = "utaite-angle-break"
    NAME = "각도 꺾임"
    CATEGORY = "utaite"
    
    # 각 글자별 회전축 (index 기반 순환)
    ORIGINS = [
        ("right", "bottom"),
        ("left", "bottom"),
        ("right", "top"),
        ("left", "top"),
        ("center", "center"),
    ]
    
    # 회전 각도 시퀀스 (키프레임)
    ANGLE_KEYFRAMES = [
        (0.0, 0),      # 시작: 0도
        (0.15, -25),   # 15%: -25도
        (0.30, 15),    # 30%: 15도
        (0.45, -8),    # 45%: -8도
        (0.60, 0),     # 60%: 정상
        (1.0, 0),      # 끝: 정상
    ]
    
    # 색상 시퀀스
    COLOR_KEYFRAMES = [
        (0.0, "#FFFFFF"),
        (0.15, "#FF006E"),
        (0.45, "#FFDE00"),
        (0.60, "#FFFFFF"),
    ]
    
    def build(self):
        chars = list(self.text)
        total_width = sum(
            QFontMetrics(self._get_font()).horizontalAdvance(c) 
            for c in chars
        )
        
        current_x = 960 - total_width / 2  # 중앙 정렬
        
        for i, char in enumerate(chars):
            item = self.create_text_item(char, current_x, 540)
            
            # 글자별 회전축 설정
            origin_x_name, origin_y_name = self.ORIGINS[i % len(self.ORIGINS)]
            self._set_transform_origin(item, origin_x_name, origin_y_name)
            
            # 순차 딜레이
            delay = i * 100  # 100ms씩 지연
            
            # 회전 애니메이션
            rotation_anim = QPropertyAnimation(item, b"rotation")
            rotation_anim.setDuration(2000)  # 2초 루프
            rotation_anim.setLoopCount(-1)   # 무한 반복
            
            for progress, angle in self.ANGLE_KEYFRAMES:
                rotation_anim.setKeyValueAt(progress, angle)
            
            rotation_anim.setEasingCurve(QEasingCurve.OutElastic)
            
            # 시작 지연
            from PySide6.QtCore import QSequentialAnimationGroup, QPauseAnimation
            seq = QSequentialAnimationGroup()
            seq.addPause(delay)
            seq.addAnimation(rotation_anim)
            
            self.animation_group.addAnimation(seq)
            
            # 다음 글자 위치로
            current_x += QFontMetrics(item.font()).horizontalAdvance(char)
    
    def _set_transform_origin(self, item, x_name, y_name):
        bounding = item.boundingRect()
        x = {
            "left": 0,
            "center": bounding.width() / 2,
            "right": bounding.width(),
        }[x_name]
        y = {
            "top": 0,
            "center": bounding.height() / 2,
            "bottom": bounding.height(),
        }[y_name]
        item.setTransformOriginPoint(QPointF(x, y))
```

### 예시 3: Ado 폭발 (우타이테 시그니처)

```python
class AdoExplosionAnimation(BaseAnimation):
    """Ado 스타일 폭발적 등장"""
    
    ID = "utaite-ado-explosion"
    NAME = "Ado 폭발"
    CATEGORY = "utaite"
    REFERENCE_ARTIST = "Ado"
    
    def build(self):
        # 메인 텍스트 (흰색)
        main_item = self.create_text_item(self.text, 960, 540)
        bounding = main_item.boundingRect()
        main_item.setPos(
            960 - bounding.width() / 2,
            540 - bounding.height() / 2
        )
        
        # 그림자 텍스트 (빨간색, 뒤에)
        shadow_item = QGraphicsTextItem(self.text)
        shadow_item.setFont(main_item.font())
        shadow_item.setDefaultTextColor(QColor("#FF0033"))
        shadow_item.setPos(main_item.pos())
        shadow_item.setZValue(-1)  # 뒤로
        self.scene.addItem(shadow_item)
        self.items.append(shadow_item)
        
        # 1. 스케일 + 블러 애니메이션 (메인)
        from PySide6.QtWidgets import QGraphicsBlurEffect
        blur_effect = QGraphicsBlurEffect()
        blur_effect.setBlurRadius(30)
        main_item.setGraphicsEffect(blur_effect)
        
        blur_anim = QPropertyAnimation(blur_effect, b"blurRadius")
        blur_anim.setDuration(300)
        blur_anim.setStartValue(30)
        blur_anim.setEndValue(0)
        
        scale_anim = QPropertyAnimation(main_item, b"scale")
        scale_anim.setDuration(500)
        scale_anim.setKeyValueAt(0.0, 0.5)
        scale_anim.setKeyValueAt(0.4, 1.2)
        scale_anim.setKeyValueAt(0.6, 0.95)
        scale_anim.setKeyValueAt(1.0, 1.0)
        scale_anim.setEasingCurve(QEasingCurve.OutBack)
        
        # 2. 그림자 분리 애니메이션
        shadow_offset_anim = QPropertyAnimation(shadow_item, b"pos")
        shadow_offset_anim.setDuration(500)
        shadow_offset_anim.setStartValue(main_item.pos())
        shadow_offset_anim.setKeyValueAt(
            0.5, 
            main_item.pos() + QPointF(8, -4)
        )
        shadow_offset_anim.setEndValue(main_item.pos())
        
        self.animation_group.addAnimation(blur_anim)
        self.animation_group.addAnimation(scale_anim)
        self.animation_group.addAnimation(shadow_offset_anim)
```

### 예시 4: Eve 글리치

```python
from PySide6.QtCore import QTimer

class EveGlitchAnimation(BaseAnimation):
    """Eve 스타일 RGB 글리치 + 스캔라인"""
    
    ID = "utaite-eve-glitch"
    NAME = "Eve 글리치"
    CATEGORY = "utaite"
    REFERENCE_ARTIST = "Eve"
    
    def build(self):
        # RGB 3개 레이어 생성
        self.cyan_item = self._create_colored_text("#00FFFF", z=-1)
        self.magenta_item = self._create_colored_text("#FF00FF", z=-2)
        self.white_item = self._create_colored_text("#FFFFFF", z=0)
        
        # 글리치 타이머 (주기적으로 위치 어긋나게)
        self.glitch_timer = QTimer()
        self.glitch_timer.timeout.connect(self._trigger_glitch)
        self.glitch_timer.start(2000)  # 2초마다
    
    def _create_colored_text(self, color: str, z: int):
        item = QGraphicsTextItem(self.text)
        
        font = QFont(self.style.font_family, self.style.font_size)
        font.setWeight(self.style.font_weight)
        item.setFont(font)
        
        item.setDefaultTextColor(QColor(color))
        bounding = item.boundingRect()
        item.setPos(960 - bounding.width() / 2, 540 - bounding.height() / 2)
        item.setZValue(z)
        
        self.scene.addItem(item)
        self.items.append(item)
        return item
    
    def _trigger_glitch(self):
        """주기적 글리치 효과"""
        import random
        
        for item, range_px in [
            (self.cyan_item, 10),
            (self.magenta_item, 8),
        ]:
            original_pos = item.pos()
            
            # 짧은 순간 위치 어긋나게
            anim = QPropertyAnimation(item, b"pos")
            anim.setDuration(200)
            anim.setKeyValueAt(0.0, original_pos)
            anim.setKeyValueAt(
                0.5, 
                original_pos + QPointF(
                    random.randint(-range_px, range_px),
                    random.randint(-range_px, range_px)
                )
            )
            anim.setKeyValueAt(1.0, original_pos)
            anim.start()
```

---

## 📦 MVP 포함 애니메이션 (20개)

### 🎬 Basic (4개)
1. Fade In/Out
2. Slide In/Out
3. Zoom In/Out
4. Pop

### 🔨 Folding (5개 - 9개 중 핵심)
5. Paper Fold (종이접기)
6. Joint Break (관절 꺾임)
7. 3D Flip (카드 뒤집기)
8. Flag Wave (깃발)
9. Angle Break (각도 꺾임 - 우타이테!)

### 🎤 Utaite (6개 - 8개 중 핵심)
10. Ado 폭발
11. Eve 글리치
12. 須田景凪 여백
13. まふまふ 판타지
14. YOASOBI 가사 립싱크
15. 일영 믹스

### 🌀 Niconico (3개 - 5개 중 핵심)
16. 합창 멤버 크레딧
17. 실시간 파트 표시
18. 타이틀 카드

### ⚡ DEVILA (2개 - 5개 중 핵심)
19. EDM 드롭 레이저
20. 사이키 스트로브 (경고 포함!)

**나머지 29개는 MVP 이후 추가**

---

## 💾 프리셋 시스템

### 빌트인 프리셋 정의

```python
# builtin_presets.py
from .models import TypographyPreset, AnimationConfig, TextStyle

BUILTIN_PRESETS = [
    TypographyPreset(
        id="ado-explosion",
        name="Ado 폭발",
        category="utaite",
        reference_artist="Ado",
        animation=AnimationConfig(
            preset_id="ado-explosion",
            in_animation="utaite-ado-explosion",
            hold_animation="none",
            out_animation="fade-up",
            in_duration=0.5,
            out_duration=0.3,
        ),
        style=TextStyle(
            font_family="Shippori Mincho",
            font_size=86,
            font_weight=900,
            color="#FFFFFF",
            shadow_color="#FF0033",
            shadow_offset_x=8,
            shadow_offset_y=-4,
        ),
    ),
    
    TypographyPreset(
        id="eve-glitch",
        name="Eve 글리치",
        category="utaite",
        reference_artist="Eve",
        animation=AnimationConfig(
            preset_id="eve-glitch",
            in_animation="utaite-eve-glitch",
            hold_animation="utaite-eve-glitch-loop",
            out_animation="fade-out",
        ),
        style=TextStyle(
            font_family="Noto Sans JP",
            font_size=54,
            font_weight=900,
            color="#FFFFFF",
            letter_spacing=6,
        ),
    ),
    
    # ... 나머지 프리셋들
]
```

### 프리셋 매니저

```python
import json
from pathlib import Path

class PresetManager:
    def __init__(self, user_data_dir: Path):
        self.user_data_dir = user_data_dir
        self.user_presets_file = user_data_dir / "user_presets.json"
        
        self.builtin_presets = self._load_builtin()
        self.user_presets = self._load_user()
    
    def _load_builtin(self) -> list[TypographyPreset]:
        from .builtin_presets import BUILTIN_PRESETS
        return BUILTIN_PRESETS
    
    def _load_user(self) -> list[TypographyPreset]:
        if not self.user_presets_file.exists():
            return []
        
        try:
            with open(self.user_presets_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [self._dict_to_preset(d) for d in data]
        except Exception as e:
            print(f"Failed to load user presets: {e}")
            return []
    
    def save_user_preset(self, preset: TypographyPreset):
        self.user_presets.append(preset)
        self._save_user()
    
    def _save_user(self):
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.user_presets_file, 'w', encoding='utf-8') as f:
            json.dump(
                [self._preset_to_dict(p) for p in self.user_presets],
                f, ensure_ascii=False, indent=2
            )
    
    def get_by_category(self, category: str) -> list[TypographyPreset]:
        all_presets = self.builtin_presets + self.user_presets
        return [p for p in all_presets if p.category == category]
```

---

## 🎨 한자/한글 감지 유틸

```python
# utils/japanese_detector.py

def get_char_type(char: str) -> str:
    """문자 타입 판별"""
    if not char:
        return "empty"
    
    code = ord(char)
    
    # 한자 (CJK Unified Ideographs)
    if 0x4E00 <= code <= 0x9FFF:
        return "kanji"
    # 히라가나
    elif 0x3040 <= code <= 0x309F:
        return "hiragana"
    # 가타카나
    elif 0x30A0 <= code <= 0x30FF:
        return "katakana"
    # 한글
    elif 0xAC00 <= code <= 0xD7A3:
        return "hangul"
    # 영문/숫자
    elif 0x0020 <= code <= 0x007E:
        return "ascii"
    else:
        return "other"

def highlight_kanji(text: str) -> list[tuple[str, bool]]:
    """한자만 True로 표시"""
    return [(c, get_char_type(c) == "kanji") for c in text]
```

---

## 🎬 렌더링 (Export)

### PyQt에서 비디오로 Export

PyQt의 애니메이션은 **화면에서만 재생**되므로, 영상 파일로 Export하려면 프레임별 렌더링이 필요합니다.

```python
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import QSize

class TypographyRenderer:
    """타이포 애니메이션을 비디오 프레임으로 렌더링"""
    
    def __init__(self, clip: TextClip, fps: int = 60):
        self.clip = clip
        self.fps = fps
        self.size = QSize(1920, 1080)
    
    def render_frames(self) -> list[QImage]:
        """모든 프레임을 이미지로 생성"""
        total_frames = int(self.clip.duration * self.fps)
        frames = []
        
        # 프레임별로 수동 렌더링
        for frame_idx in range(total_frames):
            time = frame_idx / self.fps  # 현재 시간 (초)
            frame = self._render_frame_at(time)
            frames.append(frame)
        
        return frames
    
    def _render_frame_at(self, time: float) -> QImage:
        """특정 시간의 프레임 하나 렌더링"""
        image = QImage(self.size, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        # 시간 기반으로 애니메이션 상태 계산
        # 예: Fade In이면 opacity = time / in_duration
        
        # ... 애니메이션별 렌더 로직
        
        painter.end()
        return image
    
    def export_to_video(self, output_path: str):
        """프레임들을 비디오로 합치기"""
        frames = self.render_frames()
        
        # 옵션 1: OpenCV 사용
        import cv2
        import numpy as np
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(
            output_path, fourcc, self.fps,
            (self.size.width(), self.size.height())
        )
        
        for frame in frames:
            # QImage → numpy array
            ptr = frame.bits()
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
                frame.height(), frame.width(), 4
            )
            # BGRA → BGR
            bgr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
            writer.write(bgr)
        
        writer.release()
```

### 실용적 접근: FFmpeg 사용

```python
import subprocess
from pathlib import Path

def export_with_ffmpeg(
    frames_dir: Path,
    output_path: Path,
    fps: int = 60,
    codec: str = "libx264",
):
    """프레임 PNG들을 FFmpeg로 영상으로 합치기"""
    cmd = [
        "ffmpeg",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%06d.png"),
        "-c:v", codec,
        "-pix_fmt", "yuv420p",
        "-crf", "18",  # 고품질
        str(output_path),
    ]
    subprocess.run(cmd, check=True)
```

---

## 🚀 구현 로드맵

### Phase 1: 텍스트 트랙 시스템 (1주)
- [ ] TextTrack 위젯 구현
- [ ] TextClip 위젯 (페인팅 + 드래그)
- [ ] 툴바에 T 아이콘 드래그 소스
- [ ] 클립 생성/이동/삭제/복제
- [ ] 우클릭 메뉴

### Phase 2: 에디터 모달 UI (1주)
- [ ] TypographyEditorDialog 구조
- [ ] 3-pane 레이아웃 (텍스트/애니메이션/스타일)
- [ ] 실시간 프리뷰 영역
- [ ] Apply/Cancel 동작

### Phase 3: Basic + Folding 애니메이션 (2주)
- [ ] BaseAnimation 추상 클래스
- [ ] AnimationRegistry 시스템
- [ ] Basic 4개 구현 (Fade, Slide, Zoom, Pop)
- [ ] Folding 5개 구현 (Paper Fold, Joint Break, 3D Flip, Flag Wave, Angle Break)
- [ ] 실시간 프리뷰 연동

### Phase 4: 특화 프리셋 (2주)
- [ ] Utaite 6개 (Ado, Eve, 須田景凪, まふまふ, YOASOBI, 일영믹스)
- [ ] Niconico 3개 (멤버 크레딧, 파트 표시, 타이틀 카드)
- [ ] DEVILA 2개 (EDM 드롭, 스트로브 + 경고)
- [ ] 프리셋 매니저 (저장/로드)

### Phase 5: Export 기능 (1주)
- [ ] 프레임 단위 렌더링 엔진
- [ ] 영상 파일 Export (MP4)
- [ ] 진행률 표시

### Phase 6: 마감 (1주)
- [ ] 한자/한글 자동 감지
- [ ] 광민감성 경고 시스템
- [ ] 프리셋 미리보기 썸네일
- [ ] 문서화 및 테스트

**총 8주 (2개월)**

---

## ⚠️ 주의사항

### 1. 성능
- PyQt 애니메이션은 웹만큼 가볍지 않음
- 글자 많을 때 (50자 이상) 성능 저하 가능 → 제한 필요
- `QGraphicsScene`의 `setItemIndexMethod(QGraphicsScene.NoIndex)`로 최적화

### 2. 폰트 문제
- 일본어/한글 폰트 번들 필요 (또는 시스템 폰트 fallback)
- 추천 무료 폰트:
  - **일본어**: Noto Sans JP, Noto Serif JP, Shippori Mincho (Google Fonts)
  - **한글**: Pretendard, Noto Sans KR
  - **픽셀**: DOS Gothic, Galmuri 11 (무료)

### 3. Export 성능
- 60fps 1080p 렌더링은 상당히 느림
- 프로그레스 표시 + 취소 기능 필수
- 백그라운드 스레드 (`QThread`) 사용

### 4. 광민감성 경고
- DEVILA "스트로브" 사용 시 자동 경고 다이얼로그
- 초당 3회 이상 플래시 제한

---

## 🧪 테스트 시나리오

### 시나리오 1: Ado 스타일 자막
```python
# 텍스트 클립 생성
clip = TextClip(
    text="うっせぇわ",
    start_time=10.0,
    end_time=13.0,
)

# Ado 폭발 프리셋 적용
preset = preset_manager.get_by_id("ado-explosion")
clip.animation = preset.animation
clip.style = preset.style

# 타임라인에 추가
text_track.add_clip(clip)
```

### 시나리오 2: 합창 멤버 관리
```python
# 멤버 등록
members = [
    ChorusMember(name="Alice", color="#FF3366"),
    ChorusMember(name="Bob", color="#00FFCC"),
    ChorusMember(name="Carol", color="#FFDE00"),
]

# 오프닝 크레딧 자동 생성
credit_clip = create_credit_clip(
    members=members,
    song_title="ブリキノダンス",
    remix="DEVILA REMIX",
)
text_track.add_clip(credit_clip)
```

---

## 📂 디자인 레퍼런스 파일

Claude Code가 비주얼을 이해할 수 있도록 HTML 레퍼런스 파일 포함:

```
design-reference/
├── japanese_mv_typography_showcase.html   # 우타이테/합창/DEVILA 18개 비주얼
├── folding_typography.html                 # 글자 꺾임 9개 비주얼
├── typography_editor_mockup.html           # 에디터 UI 레이아웃
```

**중요**: 이 HTML들은 **목표 비주얼 참고용**이에요. 
실제 구현은 PyQt로 해야 하며, Qt의 애니메이션 프레임워크와 QGraphicsScene을 사용해야 합니다.

---

## 💡 Claude Code 구현 시 팁

### 1. Qt 공식 예제 참고
PyQt의 `QPropertyAnimation`, `QGraphicsScene` 공식 문서와 예제를 먼저 확인.

### 2. 테스트 가능한 구조
각 애니메이션을 독립적인 클래스로 만들어 단독 실행 가능하게:

```python
if __name__ == "__main__":
    # 각 애니메이션 파일 단독 실행으로 테스트
    app = QApplication([])
    
    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    view.setSceneRect(0, 0, 1920, 1080)
    view.show()
    
    anim = AngleBreakAnimation(
        text="狂う世界!",
        style=TextStyle(font_size=72, color="#FFFFFF"),
        config=AnimationConfig(),
        scene=scene,
    )
    anim.start()
    
    app.exec()
```

### 3. 점진적 개발
- Phase 1-2: UI만 (애니메이션은 플레이스홀더)
- Phase 3: Basic만 작동시키기
- Phase 4: Folding 추가
- Phase 5+: 특화 프리셋 확장

### 4. 디버깅
- PyQt 위젯 계층 확인: `print(widget.children())`
- 애니메이션 상태: `animation.state()` (Stopped/Paused/Running)
- QGraphicsItem 위치: `item.pos()`, `item.rotation()`, `item.scale()`
