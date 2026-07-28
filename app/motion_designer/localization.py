from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QDockWidget,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from app.i18n import current_language


# Motion Designer keeps English as the authored source text.  This lets legacy
# panels participate in localization without coupling project data to a locale.
_KO = {
    "Motion Designer": "모션 디자이너",
    "Motion Tools": "모션 도구",
    "Library": "라이브러리",
    "Inspector": "인스펙터",
    "Project Pane": "프로젝트",
    "Open": "열기",
    "Save": "저장",
    "Save As": "다른 이름으로 저장",
    "File": "파일",
    "Parent": "상위",
    "Undo": "실행 취소",
    "Redo": "다시 실행",
    "Duplicate": "복제",
    "Delete": "삭제",
    "Add Object": "오브젝트 추가",
    "Behaviors": "동작",
    "Time": "시간",
    "Filters": "필터",
    "Replicate": "반복",
    "Rig": "리그",
    "Component": "컴포넌트",
    "Pre-compose": "프리컴포즈",
    "Templates": "템플릿",
    "Unreal Link": "언리얼 링크",
    "Language": "언어",
    "Export": "내보내기",
    "Properties": "속성",
    "Motion": "모션",
    "Generator": "제너레이터",
    "Replicator": "리플리케이터",
    "Image": "이미지",
    "Shape": "도형",
    "Text": "텍스트",
    "Masks": "마스크",
    "Actor": "액터",
    "Particles": "파티클",
    "Button": "버튼",
    "Puppet": "퍼펫",
    "Tracking": "트래킹",
    "Add": "추가",
    "Layers": "레이어",
    "Media": "미디어",
    "Audio": "오디오",
    "Output": "출력",
    "Canvas": "캔버스",
    "Preview": "미리보기",
    "Create": "만들기",
    "Create with AI": "AI로 만들기",
    "ADD TO COMPOSITION": "컴포지션에 추가",
    "Add Object": "오브젝트 추가",
    "No matching items": "일치하는 항목 없음",
    "Delivery": "딜리버리",
    "Choose output path": "출력 경로 선택",
    "Start with a template": "템플릿으로 시작",
    "Search templates": "템플릿 검색",
    "Select a template": "템플릿 선택",
    "Use Template": "템플릿 사용",
    "Analyze Video": "영상 분석",
    "Analyze...": "분석...",
    "Bind": "연결",
    "Bake": "베이크",
    "Attach": "부착",
    "Stabilize": "안정화",
    "Relink...": "다시 연결...",
    "Create Mesh": "메시 생성",
    "Add Pin": "핀 추가",
    "Mirror Bone": "본 미러",
    "Lock End": "끝 고정",
    "Bake IK": "IK 베이크",
    "AI WORKSPACE": "AI 작업공간",
    "Advanced": "고급",
    "Plan": "계획",
    "5 Styles": "5개 스타일",
    "Revise": "수정",
    "Apply": "적용",
    "PROPOSAL": "제안",
    "Refine Layers": "레이어 다듬기",
    "Dismiss": "닫기",
    "Apply Revision": "수정 적용",
    "Go to start": "처음으로",
    "Reverse playback (J)": "역재생 (J)",
    "Play / pause (L)": "재생 / 일시정지 (L)",
    "Loop playback": "반복 재생",
    "Show content and object library": "콘텐츠와 오브젝트 라이브러리 표시",
    "Show properties for the selected layer": "선택한 레이어의 속성 표시",
    "Show or hide Layers, Media, and Audio": "레이어, 미디어, 오디오 표시 또는 숨기기",
    "Open a Tiger Studio Motion project": "Tiger Studio 모션 프로젝트 열기",
    "Save the current Motion project": "현재 모션 프로젝트 저장",
    "Return to the parent composition": "상위 컴포지션으로 돌아가기",
    "Repeat the selected layer in a line, grid, or radial pattern": "선택 레이어를 선형, 격자 또는 방사형으로 반복",
    "Move selected layers into a nested composition": "선택 레이어를 중첩 컴포지션으로 이동",
    "Start from a Motion template": "모션 템플릿에서 시작",
    "Connect an Unreal project and generate editable UMG assets": "언리얼 프로젝트를 연결하고 편집 가능한 UMG 에셋 생성",
    "Show or hide the multimodal AI workspace": "멀티모달 AI 작업공간 표시 또는 숨기기",
    "Open Motion delivery and color settings": "모션 딜리버리 및 색상 설정 열기",
    "Search objects, animation, effects": "오브젝트, 애니메이션, 효과 검색",
    "Optional OCIO config.ocio": "선택 사항: OCIO config.ocio",
    "Unsaved Motion Project": "저장되지 않은 모션 프로젝트",
    "Save changes to the current Motion project?": "현재 모션 프로젝트의 변경 사항을 저장할까요?",
    "Open Motion Project": "모션 프로젝트 열기",
    "Save Motion Project": "모션 프로젝트 저장",
    "Opened {name}": "{name} 열림",
    "Saved {name}": "{name} 저장됨",
    "Motion Template Gallery": "모션 템플릿 갤러리",
    "Cutout Arm Wave": "컷아웃 팔 흔들기",
    "Create Full Body Rig": "전신 리그 생성",
    "Link Property": "속성 연결",
    "Layer Extraction": "레이어 추출",
    "OK": "확인",
    "Cancel": "취소",
}

_JA = {
    "Motion Designer": "モーションデザイナー",
    "Library": "ライブラリ", "Inspector": "インスペクター",
    "Project Pane": "プロジェクト", "Open": "開く", "Save": "保存",
    "Save As": "名前を付けて保存", "File": "ファイル", "Parent": "親",
    "Undo": "元に戻す", "Redo": "やり直す", "Duplicate": "複製",
    "Delete": "削除", "Add Object": "オブジェクトを追加",
    "Behaviors": "ビヘイビア", "Time": "時間", "Filters": "フィルター",
    "Rig": "リグ", "Component": "コンポーネント",
    "Pre-compose": "プリコンポーズ", "Templates": "テンプレート",
    "Unreal Link": "Unreal リンク", "Language": "言語", "Export": "書き出し",
    "Properties": "プロパティ", "Motion": "モーション", "Image": "画像",
    "Shape": "シェイプ", "Text": "テキスト", "Masks": "マスク",
    "Particles": "パーティクル", "Button": "ボタン", "Tracking": "トラッキング",
    "Add": "追加", "Layers": "レイヤー", "Media": "メディア",
    "Audio": "オーディオ", "Output": "出力", "Canvas": "キャンバス",
    "Preview": "プレビュー", "Create": "作成", "Create with AI": "AIで作成",
    "Start with a template": "テンプレートから開始",
    "Search templates": "テンプレートを検索", "Select a template": "テンプレートを選択",
    "Use Template": "テンプレートを使用", "Apply": "適用",
    "Unsaved Motion Project": "未保存のモーションプロジェクト",
    "Save changes to the current Motion project?": "現在のモーションプロジェクトへの変更を保存しますか？",
    "Open Motion Project": "モーションプロジェクトを開く",
    "Save Motion Project": "モーションプロジェクトを保存",
    "Motion Template Gallery": "モーションテンプレートギャラリー",
    "Create Full Body Rig": "全身リグを作成",
    "Link Property": "プロパティをリンク",
    "Layer Extraction": "レイヤー抽出",
    "Cancel": "キャンセル",
}

_ZH = {
    "Motion Designer": "动态图形设计器",
    "Library": "资源库", "Inspector": "检查器", "Project Pane": "项目",
    "Open": "打开", "Save": "保存", "Save As": "另存为", "File": "文件",
    "Parent": "上级", "Undo": "撤销", "Redo": "重做", "Duplicate": "复制",
    "Delete": "删除", "Add Object": "添加对象", "Behaviors": "行为",
    "Time": "时间", "Filters": "滤镜", "Rig": "绑定", "Component": "组件",
    "Pre-compose": "预合成", "Templates": "模板", "Unreal Link": "虚幻链接",
    "Language": "语言", "Export": "导出", "Properties": "属性",
    "Motion": "动画", "Image": "图像", "Shape": "形状", "Text": "文本",
    "Masks": "蒙版", "Particles": "粒子", "Button": "按钮", "Tracking": "跟踪",
    "Add": "添加", "Layers": "图层", "Media": "媒体", "Audio": "音频",
    "Output": "输出", "Canvas": "画布", "Preview": "预览", "Create": "创建",
    "Create with AI": "使用 AI 创建", "Start with a template": "从模板开始",
    "Search templates": "搜索模板", "Select a template": "选择模板",
    "Use Template": "使用模板", "Apply": "应用",
    "Unsaved Motion Project": "未保存的动态图形项目",
    "Save changes to the current Motion project?": "是否保存当前动态图形项目的更改？",
    "Open Motion Project": "打开动态图形项目", "Save Motion Project": "保存动态图形项目",
    "Motion Template Gallery": "动态图形模板库",
    "Create Full Body Rig": "创建全身绑定",
    "Link Property": "链接属性", "Layer Extraction": "图层提取", "Cancel": "取消",
}

_FR = {
    "Motion Designer": "Concepteur d'animation",
    "Library": "Bibliothèque", "Inspector": "Inspecteur", "Project Pane": "Projet",
    "Open": "Ouvrir", "Save": "Enregistrer", "Save As": "Enregistrer sous",
    "File": "Fichier", "Parent": "Parent", "Undo": "Annuler", "Redo": "Rétablir",
    "Duplicate": "Dupliquer", "Delete": "Supprimer", "Add Object": "Ajouter un objet",
    "Behaviors": "Comportements", "Time": "Temps", "Filters": "Filtres",
    "Rig": "Rig", "Component": "Composant", "Pre-compose": "Précomposer",
    "Templates": "Modèles", "Unreal Link": "Lien Unreal", "Language": "Langue",
    "Export": "Exporter", "Properties": "Propriétés", "Motion": "Animation",
    "Image": "Image", "Shape": "Forme", "Text": "Texte", "Masks": "Masques",
    "Particles": "Particules", "Button": "Bouton", "Tracking": "Suivi",
    "Add": "Ajouter", "Layers": "Calques", "Media": "Médias", "Audio": "Audio",
    "Output": "Sortie", "Canvas": "Canevas", "Preview": "Aperçu",
    "Create": "Créer", "Create with AI": "Créer avec l'IA",
    "Start with a template": "Commencer avec un modèle",
    "Search templates": "Rechercher des modèles", "Select a template": "Choisir un modèle",
    "Use Template": "Utiliser le modèle", "Apply": "Appliquer",
    "Unsaved Motion Project": "Projet d'animation non enregistré",
    "Save changes to the current Motion project?": "Enregistrer les modifications du projet d'animation actuel ?",
    "Open Motion Project": "Ouvrir un projet d'animation",
    "Save Motion Project": "Enregistrer le projet d'animation",
    "Motion Template Gallery": "Galerie de modèles d'animation",
    "Create Full Body Rig": "Créer un rig complet",
    "Link Property": "Lier la propriété",
    "Layer Extraction": "Extraction des calques", "Cancel": "Annuler",
}

_DE = {
    "Motion Designer": "Motion Designer",
    "Library": "Bibliothek", "Inspector": "Inspektor", "Project Pane": "Projekt",
    "Open": "Öffnen", "Save": "Speichern", "Save As": "Speichern unter",
    "File": "Datei", "Parent": "Übergeordnet", "Undo": "Rückgängig",
    "Redo": "Wiederholen", "Duplicate": "Duplizieren", "Delete": "Löschen",
    "Add Object": "Objekt hinzufügen", "Behaviors": "Verhalten", "Time": "Zeit",
    "Filters": "Filter", "Rig": "Rig", "Component": "Komponente",
    "Pre-compose": "Vorkomposition", "Templates": "Vorlagen",
    "Unreal Link": "Unreal-Verbindung", "Language": "Sprache", "Export": "Exportieren",
    "Properties": "Eigenschaften", "Motion": "Animation", "Image": "Bild",
    "Shape": "Form", "Text": "Text", "Masks": "Masken", "Particles": "Partikel",
    "Button": "Schaltfläche", "Tracking": "Tracking", "Add": "Hinzufügen",
    "Layers": "Ebenen", "Media": "Medien", "Audio": "Audio", "Output": "Ausgabe",
    "Canvas": "Arbeitsfläche", "Preview": "Vorschau", "Create": "Erstellen",
    "Create with AI": "Mit KI erstellen", "Start with a template": "Mit Vorlage beginnen",
    "Search templates": "Vorlagen durchsuchen", "Select a template": "Vorlage auswählen",
    "Use Template": "Vorlage verwenden", "Apply": "Anwenden",
    "Unsaved Motion Project": "Nicht gespeichertes Motion-Projekt",
    "Save changes to the current Motion project?": "Änderungen am aktuellen Motion-Projekt speichern?",
    "Open Motion Project": "Motion-Projekt öffnen",
    "Save Motion Project": "Motion-Projekt speichern",
    "Motion Template Gallery": "Motion-Vorlagengalerie",
    "Create Full Body Rig": "Ganzkörper-Rig erstellen",
    "Link Property": "Eigenschaft verknüpfen",
    "Layer Extraction": "Ebenenextraktion", "Cancel": "Abbrechen",
}

_CATALOGS = {"ko": _KO, "ja": _JA, "zh": _ZH, "fr": _FR, "de": _DE}


def motion_text(source: str, *, language: str | None = None, **kwargs: Any) -> str:
    text = str(source)
    code = str(language or current_language() or "en").split("_", 1)[0].lower()
    translated = _CATALOGS.get(code, {}).get(text, text)
    if not kwargs:
        return translated
    try:
        return translated.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return translated


def _qt_property(obj: QObject, name: str) -> Any:
    return QObject.property(obj, name)


def _set_qt_property(obj: QObject, name: str, value: Any) -> None:
    QObject.setProperty(obj, name, value)


def _translate_property(
    obj: Any,
    *,
    getter: str,
    setter: str,
    source_property: str,
    rendered_property: str,
    language: str,
) -> None:
    current = str(getattr(obj, getter)() or "")
    source = _qt_property(obj, source_property)
    rendered = _qt_property(obj, rendered_property)
    if source is None or (rendered is not None and current != str(rendered)):
        source = current
        _set_qt_property(obj, source_property, source)
    translated = motion_text(str(source), language=language)
    getattr(obj, setter)(translated)
    _set_qt_property(obj, rendered_property, translated)


def retranslate_motion_ui(root: QWidget, language: str | None = None) -> None:
    """Retranslate stable Motion UI chrome without rebuilding the workspace."""
    code = str(language or current_language() or "en")
    widgets = [root, *root.findChildren(QWidget)]
    for widget in widgets:
        if isinstance(widget, QMainWindow):
            continue
        if isinstance(widget, (QDialog, QDockWidget)):
            _translate_property(
                widget, getter="windowTitle", setter="setWindowTitle",
                source_property="motionI18nTitleSource",
                rendered_property="motionI18nTitleRendered", language=code,
            )
        elif isinstance(widget, QGroupBox):
            _translate_property(
                widget, getter="title", setter="setTitle",
                source_property="motionI18nTitleSource",
                rendered_property="motionI18nTitleRendered", language=code,
            )
        elif isinstance(widget, (QAbstractButton, QLabel)):
            _translate_property(
                widget, getter="text", setter="setText",
                source_property="motionI18nTextSource",
                rendered_property="motionI18nTextRendered", language=code,
            )
        if isinstance(widget, QLineEdit):
            _translate_property(
                widget, getter="placeholderText", setter="setPlaceholderText",
                source_property="motionI18nPlaceholderSource",
                rendered_property="motionI18nPlaceholderRendered", language=code,
            )
        elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
            _translate_property(
                widget, getter="placeholderText", setter="setPlaceholderText",
                source_property="motionI18nPlaceholderSource",
                rendered_property="motionI18nPlaceholderRendered", language=code,
            )
        tooltip = str(widget.toolTip() or "")
        tooltip_source = _qt_property(widget, "motionI18nTooltipSource")
        tooltip_rendered = _qt_property(widget, "motionI18nTooltipRendered")
        if tooltip_source is None or (
            tooltip_rendered is not None and tooltip != str(tooltip_rendered)
        ):
            tooltip_source = tooltip
            _set_qt_property(widget, "motionI18nTooltipSource", tooltip_source)
        translated_tooltip = motion_text(str(tooltip_source), language=code)
        widget.setToolTip(translated_tooltip)
        _set_qt_property(widget, "motionI18nTooltipRendered", translated_tooltip)

    for tabs in root.findChildren(QTabWidget):
        for index in range(tabs.count()):
            page = tabs.widget(index)
            source = _qt_property(page, "motionI18nTabSource")
            rendered = _qt_property(page, "motionI18nTabRendered")
            current = tabs.tabText(index)
            if source is None or (rendered is not None and current != str(rendered)):
                source = current
                _set_qt_property(page, "motionI18nTabSource", source)
            translated = motion_text(str(source), language=code)
            tabs.setTabText(index, translated)
            _set_qt_property(page, "motionI18nTabRendered", translated)

    for action in root.findChildren(QAction):
        _translate_property(
            action, getter="text", setter="setText",
            source_property="motionI18nTextSource",
            rendered_property="motionI18nTextRendered", language=code,
        )
        _translate_property(
            action, getter="toolTip", setter="setToolTip",
            source_property="motionI18nTooltipSource",
            rendered_property="motionI18nTooltipRendered", language=code,
        )
