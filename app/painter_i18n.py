"""Runtime localization for the complete Painter widget surface.

Painter grew from several focused tools, so a large part of its UI predates
translation keys.  This module localizes those widgets without coupling the
document model or action contracts to display text.
"""
from __future__ import annotations

import re
from importlib import import_module
from typing import Iterable

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QTabWidget,
    QTreeWidget,
    QWidget,
)

from app.i18n import current_language


_LANGUAGES = ("en", "ko", "ja", "zh", "fr", "de")

# English source, Korean, Japanese, Simplified Chinese, French, German.
_ROWS: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("Overrides", "오버라이드", "オーバーライド", "覆盖", "Remplacements", "Überschreibungen"),
    ("Reset", "초기화", "リセット", "重置", "Réinitialiser", "Zurücksetzen"),
    ("Reset All", "모두 초기화", "すべてリセット", "全部重置", "Tout réinitialiser", "Alle zurücksetzen"),
    (
        "Local values that differ from the component definition",
        "컴포넌트 정의와 다른 로컬 값",
        "コンポーネント定義と異なるローカル値",
        "与组件定义不同的本地值",
        "Valeurs locales différentes de la définition du composant",
        "Lokale Werte, die von der Komponentendefinition abweichen",
    ),
    (
        "Reset only the selected override",
        "선택한 오버라이드만 초기화",
        "選択したオーバーライドのみリセット",
        "仅重置所选覆盖",
        "Réinitialiser uniquement le remplacement sélectionné",
        "Nur die ausgewählte Überschreibung zurücksetzen",
    ),
    (
        "Reset every local override in this component instance",
        "이 컴포넌트 인스턴스의 모든 로컬 오버라이드 초기화",
        "このコンポーネントインスタンスの全ローカルオーバーライドをリセット",
        "重置此组件实例中的所有本地覆盖",
        "Réinitialiser tous les remplacements locaux de cette instance",
        "Alle lokalen Überschreibungen dieser Instanz zurücksetzen",
    ),
    ("Responsive Preview", "반응형 프리뷰", "レスポンシブプレビュー", "响应式预览", "Aperçu adaptatif", "Responsive Vorschau"),
    ("Component Playground", "컴포넌트 플레이그라운드", "コンポーネントプレイグラウンド", "组件试验场", "Atelier de composant", "Komponenten-Spielwiese"),
    ("Component Properties", "컴포넌트 속성", "コンポーネントプロパティ", "组件属性", "Propriétés du composant", "Komponenteneigenschaften"),
    ("New Page", "새 페이지", "新規ページ", "新建页面", "Nouvelle page", "Neue Seite"),
    ("Delete Page", "페이지 삭제", "ページを削除", "删除页面", "Supprimer la page", "Seite löschen"),
    (
        "Duplicate to next artboard",
        "다음 아트보드로 복제",
        "次のアートボードに複製",
        "复制到下一个画板",
        "Dupliquer vers le plan de travail suivant",
        "Auf nächste Zeichenfläche duplizieren",
    ),
    (
        "Copy the selected hierarchy to the next screen",
        "선택한 계층을 다음 화면으로 복제",
        "選択した階層を次の画面に複製",
        "将所选层级复制到下一个画面",
        "Copier la hiérarchie sélectionnée vers l’écran suivant",
        "Ausgewählte Hierarchie auf den nächsten Bildschirm kopieren",
    ),
    (
        "Duplicated to",
        "복제 완료:",
        "複製先:",
        "已复制到:",
        "Dupliqué vers :",
        "Dupliziert nach:",
    ),
    ("Vector", "벡터", "ベクター", "矢量", "Vecteur", "Vektor"),
    ("nodes", "노드", "ノード", "节点", "nœuds", "Knoten"),
    ("Straight", "직선", "直線", "直线", "Droit", "Gerade"),
    ("Bezier", "베지어", "ベジェ", "贝塞尔", "Bézier", "Bézier"),
    ("Split", "분할", "分割", "拆分", "Diviser", "Teilen"),
    (
        "Reverse path",
        "경로 반전",
        "パスを反転",
        "反转路径",
        "Inverser le tracé",
        "Pfad umkehren",
    ),
    (
        "Simplify path",
        "경로 단순화",
        "パスを単純化",
        "简化路径",
        "Simplifier le tracé",
        "Pfad vereinfachen",
    ),
    (
        "Outline stroke",
        "획 윤곽 변환",
        "線をアウトライン化",
        "轮廓化描边",
        "Vectoriser le contour",
        "Kontur umwandeln",
    ),
    (
        "Union selection",
        "선택 합치기",
        "選択範囲を合体",
        "合并所选项",
        "Unir la sélection",
        "Auswahl vereinen",
    ),
    (
        "Subtract selection",
        "선택 빼기",
        "選択範囲を型抜き",
        "减去所选项",
        "Soustraire la sélection",
        "Auswahl abziehen",
    ),
    (
        "Intersect selection",
        "선택 교차",
        "選択範囲を交差",
        "交集所选项",
        "Intersection de la sélection",
        "Auswahl schneiden",
    ),
    (
        "Exclude selection",
        "선택 제외",
        "選択範囲を中マド",
        "排除所选项",
        "Exclure la sélection",
        "Auswahl ausschließen",
    ),
    (
        "Release Boolean group",
        "불리언 그룹 해제",
        "ブーリアングループを解除",
        "释放布尔组",
        "Libérer le groupe booléen",
        "Boolesche Gruppe lösen",
    ),
    (
        "Boolean group",
        "불리언 그룹",
        "ブーリアングループ",
        "布尔组",
        "Groupe booléen",
        "Boolesche Gruppe",
    ),
    ("selected", "선택", "選択", "已选择", "sélectionnés", "ausgewählt"),
    (
        "Delete node",
        "노드 삭제",
        "ノードを削除",
        "删除节点",
        "Supprimer le nœud",
        "Knoten löschen",
    ),
    (
        "Exit vector edit",
        "벡터 편집 종료",
        "ベクター編集を終了",
        "退出矢量编辑",
        "Quitter l'édition vectorielle",
        "Vektorbearbeitung beenden",
    ),
    (
        "Open path",
        "패스 열기",
        "パスを開く",
        "打开路径",
        "Ouvrir le tracé",
        "Pfad öffnen",
    ),
    (
        "Close path",
        "패스 닫기",
        "パスを閉じる",
        "闭合路径",
        "Fermer le tracé",
        "Pfad schließen",
    ),
    ("Painter - Tiger Studio", "페인터 - Tiger Studio", "ペインター - Tiger Studio", "画板 - Tiger Studio", "Peinture - Tiger Studio", "Maler - Tiger Studio"),
    ("New Canvas", "새 캔버스", "新規キャンバス", "新建画布", "Nouveau canevas", "Neue Leinwand"),
    ("Image & Output Size", "이미지 및 출력 크기", "画像と出力サイズ", "图像与输出尺寸", "Taille de l'image et de sortie", "Bild- und Ausgabegröße"),
    ("Choose a canvas template or enter a custom size.", "캔버스 템플릿을 선택하거나 사용자 크기를 입력하세요.", "キャンバステンプレートを選択するか、サイズを入力してください。", "选择画布模板或输入自定义尺寸。", "Choisissez un modèle de canevas ou saisissez une taille.", "Wählen Sie eine Leinwandvorlage oder geben Sie eine Größe ein."),
    ("Purpose", "용도", "用途", "用途", "Usage", "Zweck"),
    ("Screen / Web / Video", "화면 / 웹 / 비디오", "画面 / Web / ビデオ", "屏幕 / Web / 视频", "Écran / Web / Vidéo", "Bildschirm / Web / Video"),
    ("Print", "인쇄", "印刷", "打印", "Impression", "Druck"),
    ("Template", "템플릿", "テンプレート", "模板", "Modèle", "Vorlage"),
    ("Custom", "사용자 지정", "カスタム", "自定义", "Personnalisé", "Benutzerdefiniert"),
    ("Width", "너비", "幅", "宽度", "Largeur", "Breite"),
    ("Common", "공통", "共通", "通用", "Commun", "Gemeinsam"),
    ("Horizontal", "가로", "水平", "水平", "Horizontal", "Horizontal"),
    ("Vertical", "세로", "垂直", "垂直", "Vertical", "Vertikal"),
    ("Tidy Up", "간격 정리", "間隔を整列", "整理间距", "Uniformiser", "Abstände ordnen"),
    ("Make the selected object spacing uniform", "선택 객체의 간격을 균일하게 맞춥니다", "選択したオブジェクトの間隔を均等にします", "使所选对象的间距均匀", "Uniformiser l'espacement des objets sélectionnés", "Abstände der ausgewählten Objekte vereinheitlichen"),
    ("Height", "높이", "高さ", "高度", "Hauteur", "Höhe"),
    ("Trim Size", "재단 크기", "仕上がりサイズ", "裁切尺寸", "Format fini", "Endformat"),
    ("Resolution", "해상도", "解像度", "分辨率", "Résolution", "Auflösung"),
    ("Bleed", "도련", "塗り足し", "出血", "Fond perdu", "Beschnitt"),
    ("Artwork", "작업 유형", "作品", "作品类型", "Illustration", "Werk"),
    ("Background", "배경", "背景", "背景", "Arrière-plan", "Hintergrund"),
    ("Create", "만들기", "作成", "创建", "Créer", "Erstellen"),
    ("Apply", "적용", "適用", "应用", "Appliquer", "Anwenden"),
    ("Cancel", "취소", "キャンセル", "取消", "Annuler", "Abbrechen"),
    ("Brush", "브러시", "ブラシ", "画笔", "Pinceau", "Pinsel"),
    ("Pen", "펜", "ペン", "笔", "Stylet", "Stift"),
    ("Brush Tool (B)", "브러시 도구 (B)", "ブラシツール (B)", "画笔工具 (B)", "Outil Pinceau (B)", "Pinselwerkzeug (B)"),
    ("Undo (Ctrl+Z)", "실행 취소 (Ctrl+Z)", "元に戻す (Ctrl+Z)", "撤销 (Ctrl+Z)", "Annuler (Ctrl+Z)", "Rückgängig (Ctrl+Z)"),
    ("Redo (Ctrl+Y)", "다시 실행 (Ctrl+Y)", "やり直し (Ctrl+Y)", "重做 (Ctrl+Y)", "Rétablir (Ctrl+Y)", "Wiederholen (Ctrl+Y)"),
    ("Export PNG", "PNG 내보내기", "PNGを書き出し", "导出 PNG", "Exporter en PNG", "PNG exportieren"),
    ("Zoom out (Ctrl+-)", "축소 (Ctrl+-)", "縮小 (Ctrl+-)", "缩小 (Ctrl+-)", "Zoom arrière (Ctrl+-)", "Verkleinern (Ctrl+-)"),
    ("Zoom in (Ctrl++)", "확대 (Ctrl++)", "拡大 (Ctrl++)", "放大 (Ctrl++)", "Zoom avant (Ctrl++)", "Vergrößern (Ctrl++)"),
    ("Fit canvas (Ctrl+0)", "캔버스 맞춤 (Ctrl+0)", "キャンバスを全体表示 (Ctrl+0)", "适合画布 (Ctrl+0)", "Ajuster le canevas (Ctrl+0)", "Leinwand einpassen (Ctrl+0)"),
    ("Painter tools", "페인터 도구", "ペインターツール", "画板工具", "Outils de peinture", "Malerwerkzeuge"),
    ("Select / Move", "선택 / 이동", "選択 / 移動", "选择 / 移动", "Sélection / Déplacement", "Auswahl / Verschieben"),
    ("Pan", "화면 이동", "パン", "平移", "Déplacer la vue", "Ansicht verschieben"),
    ("Rect Select", "사각형 선택", "長方形選択", "矩形选择", "Sélection rectangulaire", "Rechteckauswahl"),
    ("Ellipse Select", "타원 선택", "楕円選択", "椭圆选择", "Sélection elliptique", "Ellipsenauswahl"),
    ("Magic Select", "자동 선택", "自動選択", "魔棒选择", "Sélection magique", "Zauberauswahl"),
    ("Crop", "자르기", "切り抜き", "裁剪", "Recadrer", "Freistellen"),
    ("Mirror X", "좌우 반전", "左右反転", "水平翻转", "Miroir horizontal", "Horizontal spiegeln"),
    ("Mirror Y", "상하 반전", "上下反転", "垂直翻转", "Miroir vertical", "Vertikal spiegeln"),
    ("Path", "패스", "パス", "路径", "Tracé", "Pfad"),
    ("Editor Object", "에디터 객체", "エディターオブジェクト", "编辑器对象", "Objet de l'éditeur", "Editorobjekt"),
    ("Cutout", "오려내기", "切り抜き", "抠图", "Détourage", "Freisteller"),
    ("Fill", "채우기", "塗りつぶし", "填充", "Remplissage", "Füllen"),
    ("Stroke", "선", "線", "描边", "Contour", "Kontur"),
    ("Radius", "모서리 반경", "角丸", "圆角", "Rayon", "Radius"),
    ("Zoom", "확대/축소", "ズーム", "缩放", "Zoom", "Zoom"),
    ("Quick Mask", "퀵 마스크", "クイックマスク", "快速蒙版", "Masque rapide", "Schnellmaske"),
    ("CANVAS", "캔버스", "キャンバス", "画布", "CANEVAS", "LEINWAND"),
    ("Paint", "페인트", "ペイント", "绘画", "Peinture", "Malen"),
    ("UI Design", "UI 디자인", "UIデザイン", "UI 设计", "Design UI", "UI-Design"),
    ("3D Place", "3D 배치", "3D配置", "3D 放置", "Placement 3D", "3D-Platzierung"),
    ("Motion Actor", "모션 액터", "モーションアクター", "动效 Actor", "Acteur d'animation", "Motion-Akteur"),
    ("Animate", "애니메이션", "アニメーション", "制作动画", "Animer", "Animieren"),
    ("Scene", "씬", "シーン", "场景", "Scène", "Szene"),
    ("TOOL OPTIONS", "도구 옵션", "ツールオプション", "工具选项", "OPTIONS DE L'OUTIL", "WERKZEUGOPTIONEN"),
    ("Mode", "모드", "モード", "模式", "Mode", "Modus"),
    ("Style", "스타일", "スタイル", "样式", "Style", "Stil"),
    ("Normal", "표준", "通常", "正常", "Normal", "Normal"),
    ("Fixed Ratio 1:1", "고정 비율 1:1", "固定比率 1:1", "固定比例 1:1", "Ratio fixe 1:1", "Festes Verhältnis 1:1"),
    ("Fixed Ratio 16:9", "고정 비율 16:9", "固定比率 16:9", "固定比例 16:9", "Ratio fixe 16:9", "Festes Verhältnis 16:9"),
    ("Fixed Ratio 4:3", "고정 비율 4:3", "固定比率 4:3", "固定比例 4:3", "Ratio fixe 4:3", "Festes Verhältnis 4:3"),
    ("Apply Crop", "자르기 적용", "切り抜きを適用", "应用裁剪", "Appliquer le recadrage", "Freistellen anwenden"),
    ("Mask", "마스크", "マスク", "蒙版", "Masque", "Maske"),
    ("Deselect", "선택 해제", "選択解除", "取消选择", "Désélectionner", "Auswahl aufheben"),
    ("Grid", "그리드", "グリッド", "网格", "Grille", "Raster"),
    ("Snap", "스냅", "スナップ", "吸附", "Magnétisme", "Einrasten"),
    ("Tolerance", "허용치", "許容値", "容差", "Tolérance", "Toleranz"),
    ("Gradient", "그라디언트", "グラデーション", "渐变", "Dégradé", "Verlauf"),
    ("Pattern", "패턴", "パターン", "图案", "Motif", "Muster"),
    ("Brush Selector", "브러시 선택기", "ブラシセレクター", "画笔选择器", "Sélecteur de pinceaux", "Pinselauswahl"),
    ("Size", "크기", "サイズ", "大小", "Taille", "Größe"),
    ("Opacity", "불투명도", "不透明度", "不透明度", "Opacité", "Deckkraft"),
    ("Material", "머티리얼", "マテリアル", "材质", "Matériau", "Material"),
    ("COLOR", "색상", "カラー", "颜色", "COULEUR", "FARBE"),
    ("Mixer", "믹서", "ミキサー", "混色器", "Mélangeur", "Mischer"),
    ("Recent Colors", "최근 색상", "最近の色", "最近颜色", "Couleurs récentes", "Zuletzt verwendete Farben"),
    ("Pinned / Document", "고정 / 문서", "固定 / ドキュメント", "固定 / 文档", "Épinglées / Document", "Angeheftet / Dokument"),
    ("Pin Current", "현재 색상 고정", "現在の色を固定", "固定当前颜色", "Épingler la couleur", "Aktuelle Farbe anheften"),
    ("Touch Targets", "터치 대상", "タッチターゲット", "触控目标", "Cibles tactiles", "Touch-Ziele"),
    ("Shades", "명암", "シェード", "明暗", "Nuances", "Schattierungen"),
    ("Multiply", "곱하기", "乗算", "正片叠底", "Produit", "Multiplizieren"),
    ("Screen", "스크린", "スクリーン", "滤色", "Écran", "Negativ multiplizieren"),
    ("Overlay", "오버레이", "オーバーレイ", "叠加", "Incrustation", "Überlagern"),
    ("REFERENCE", "레퍼런스", "リファレンス", "参考", "RÉFÉRENCE", "REFERENZ"),
    ("Image", "이미지", "画像", "图像", "Image", "Bild"),
    ("Clip", "클립", "クリップ", "剪辑", "Clip", "Clip"),
    ("Duplicate", "복제", "複製", "复制", "Dupliquer", "Duplizieren"),
    ("Delete", "삭제", "削除", "删除", "Supprimer", "Löschen"),
    ("Bake", "베이크", "ベイク", "烘焙", "Précalculer", "Backen"),
    ("Visible", "표시", "表示", "可见", "Visible", "Sichtbar"),
    ("Locked", "잠금", "ロック", "锁定", "Verrouillé", "Gesperrt"),
    ("Lock", "잠금", "ロック", "锁定", "Verrouiller", "Sperren"),
    ("Sample", "샘플", "サンプル", "采样", "Échantillon", "Probe"),
    ("Palette", "팔레트", "パレット", "调色板", "Palette", "Palette"),
    ("Drop references here", "여기에 레퍼런스를 놓으세요", "ここにリファレンスをドロップ", "将参考图拖到此处", "Déposez les références ici", "Referenzen hier ablegen"),
    ("3D BLOCKOUT", "3D 블록아웃", "3Dブロックアウト", "3D 灰模", "BLOCAGE 3D", "3D-BLOCKOUT"),
    ("Place Shapes", "도형 배치", "シェイプを配置", "放置形状", "Placer des formes", "Formen platzieren"),
    ("Ground", "바닥 배치", "地面に配置", "放置到地面", "Poser au sol", "Auf Boden setzen"),
    ("Floor", "바닥", "床", "地面", "Sol", "Boden"),
    ("Wire", "와이어", "ワイヤー", "线框", "Fil de fer", "Drahtgitter"),
    ("Lit", "라이팅", "ライティング", "光照", "Éclairé", "Beleuchtet"),
    ("Shadow", "그림자", "シャドウ", "阴影", "Ombre", "Schatten"),
    ("Fog", "포그", "フォグ", "雾", "Brouillard", "Nebel"),
    ("Depth", "뎁스", "深度", "深度", "Profondeur", "Tiefe"),
    ("Transform", "트랜스폼", "トランスフォーム", "变换", "Transformation", "Transformieren"),
    ("Camera / FOV", "카메라 / 시야각", "カメラ / 視野角", "相机 / 视野", "Caméra / Champ", "Kamera / Sichtfeld"),
    ("PLACE ACTORS", "액터 배치", "アクター配置", "放置 Actor", "PLACER DES ACTEURS", "AKTEURE PLATZIEREN"),
    ("Shapes", "도형", "シェイプ", "形状", "Formes", "Formen"),
    ("Drag to place on ground", "드래그하여 바닥에 배치", "ドラッグして地面に配置", "拖动以放置到地面", "Glissez pour poser au sol", "Ziehen, um auf dem Boden zu platzieren"),
    ("Search brushes", "브러시 검색", "ブラシを検索", "搜索画笔", "Rechercher des pinceaux", "Pinsel suchen"),
    ("RECENT", "최근 사용", "最近", "最近", "RÉCENTS", "ZULETZT"),
    ("MATERIAL PAINT", "머티리얼 페인트", "マテリアルペイント", "材质绘画", "PEINTURE MATÉRIAU", "MATERIALMALEREI"),
    ("WET CANVAS", "젖은 캔버스", "ウェットキャンバス", "湿画布", "CANEVAS HUMIDE", "NASSE LEINWAND"),
    ("Enable editable wet layer", "편집 가능한 젖은 레이어 사용", "編集可能なウェットレイヤーを有効化", "启用可编辑湿画层", "Activer le calque humide modifiable", "Bearbeitbare Nassschicht aktivieren"),
    ("Dry time", "건조 시간", "乾燥時間", "干燥时间", "Temps de séchage", "Trocknungszeit"),
    ("Dry Now", "지금 건조", "今すぐ乾燥", "立即干燥", "Sécher maintenant", "Jetzt trocknen"),
    ("FILTER BRUSHES", "브러시 필터", "ブラシを絞り込む", "筛选画笔", "FILTRER LES PINCEAUX", "PINSEL FILTERN"),
    ("Clear Filters", "필터 지우기", "フィルターを解除", "清除筛选", "Effacer les filtres", "Filter löschen"),
    ("Select a brush", "브러시를 선택하세요", "ブラシを選択", "选择画笔", "Sélectionnez un pinceau", "Pinsel auswählen"),
    ("QUICK PALETTE", "퀵 팔레트", "クイックパレット", "快速调色板", "PALETTE RAPIDE", "SCHNELLPALETTE"),
    ("UI DESIGN", "UI 디자인", "UIデザイン", "UI 设计", "DESIGN UI", "UI-DESIGN"),
    ("File", "파일", "ファイル", "文件", "Fichier", "Datei"),
    ("Edit", "편집", "編集", "编辑", "Edition", "Bearbeiten"),
    ("Image", "이미지", "画像", "图像", "Image", "Bild"),
    ("Layer", "레이어", "レイヤー", "图层", "Calque", "Ebene"),
    ("Select", "선택", "選択", "选择", "Selection", "Auswahl"),
    ("View", "보기", "表示", "视图", "Affichage", "Ansicht"),
    ("Window", "창", "ウィンドウ", "窗口", "Fenetre", "Fenster"),
    ("UI", "UI", "UI", "UI", "UI", "UI"),
    ("Undo", "실행 취소", "元に戻す", "撤销", "Annuler", "Ruckgangig"),
    ("Redo", "다시 실행", "やり直す", "重做", "Retablir", "Wiederholen"),
    ("Reset", "초기화", "リセット", "重置", "Réinitialiser", "Zurücksetzen"),
    ("Duplicate UI Object", "UI 객체 복제", "UIオブジェクトを複製", "复制 UI 对象", "Dupliquer l'objet UI", "UI-Objekt duplizieren"),
    ("Delete UI Object", "UI 객체 삭제", "UIオブジェクトを削除", "删除 UI 对象", "Supprimer l'objet UI", "UI-Objekt loschen"),
    ("Delete Active Artboard", "활성 아트보드 삭제", "アクティブなアートボードを削除", "删除活动画板", "Supprimer le plan de travail actif", "Aktive Zeichenflache loschen"),
    ("Delete active artboard", "활성 아트보드 삭제", "アクティブなアートボードを削除", "删除活动画板", "Supprimer le plan de travail actif", "Aktive Zeichenflache loschen"),
    ("Fit All Artboards", "모든 아트보드 맞춤", "すべてのアートボードを表示", "适合所有画板", "Ajuster tous les plans de travail", "Alle Zeichenflachen einpassen"),
    ("Fit Active Artboard", "활성 아트보드 맞춤", "アクティブなアートボードを表示", "适合活动画板", "Ajuster le plan de travail actif", "Aktive Zeichenflache einpassen"),
    ("Fit Selection", "선택 영역 맞춤", "選択範囲を表示", "适合所选内容", "Ajuster la selection", "Auswahl einpassen"),
    ("Layers", "레이어", "レイヤー", "图层", "Calques", "Ebenen"),
    ("Sections", "섹션", "セクション", "分区", "Sections", "Abschnitte"),
    ("Components", "컴포넌트", "コンポーネント", "组件", "Composants", "Komponenten"),
    ("Tokens", "토큰", "トークン", "令牌", "Jetons", "Token"),
    ("Motion", "모션", "モーション", "动效", "Animation", "Motion"),
    ("Publish", "배포", "公開", "发布", "Publier", "Veroffentlichen"),
    ("Inspect", "속성", "検査", "检查", "Inspecter", "Prufen"),
    ("Open UI template gallery", "UI 템플릿 갤러리 열기", "UIテンプレートギャラリーを開く", "打开 UI 模板库", "Ouvrir la galerie de modeles UI", "UI-Vorlagengalerie offnen"),
    ("Context", "대상", "コンテキスト", "上下文", "Contexte", "Kontext"),
    ("Theme", "테마", "テーマ", "主题", "Theme", "Thema"),
    ("Layout", "레이아웃", "レイアウト", "布局", "Disposition", "Layout"),
    ("Metrics", "그리드", "メトリクス", "网格参数", "Mesures", "Metrik"),
    ("Safe Area", "안전 영역", "セーフエリア", "安全区域", "Zone sure", "Sicherheitsbereich"),
    ("Status", "상태", "状態", "状态", "Etat", "Status"),
    ("No layout grid", "레이아웃 그리드 없음", "レイアウトグリッドなし", "无布局网格", "Aucune grille", "Kein Layoutraster"),
    ("Uniform grid", "균일 그리드", "均等グリッド", "均匀网格", "Grille uniforme", "Gleichmassiges Raster"),
    ("Columns", "열", "カラム", "列", "Colonnes", "Spalten"),
    ("Desktop", "데스크톱", "デスクトップ", "桌面", "Bureau", "Desktop"),
    ("Mobile", "모바일", "モバイル", "移动端", "Mobile", "Mobil"),
    ("Console", "콘솔", "コンソール", "主机", "Console", "Konsole"),
    ("Broadcast", "방송", "放送", "播出", "Diffusion", "Broadcast"),
    ("Artboard Settings", "아트보드 설정", "アートボード設定", "画板设置", "Reglages du plan de travail", "Zeichenflachen-Einstellungen"),
    ("Edit common properties, align, or distribute.", "공통 속성을 편집하거나 정렬 및 분배합니다.", "共通プロパティを編集、整列、分布します。", "编辑通用属性，或对齐和分布。", "Modifiez les propriétés communes, alignez ou distribuez.", "Gemeinsame Eigenschaften bearbeiten, ausrichten oder verteilen."),
    ("Show artboard context, layout grid, safe area, and guides", "아트보드 대상, 레이아웃 그리드, 안전 영역과 가이드를 표시합니다", "アートボードのコンテキスト、レイアウトグリッド、セーフエリア、ガイドを表示", "显示画板上下文、布局网格、安全区域和参考线", "Afficher le contexte, la grille, la zone sure et les reperes", "Kontext, Layoutraster, Sicherheitsbereich und Hilfslinien anzeigen"),
    ("Portrait", "세로", "縦", "竖屏", "Portrait", "Hochformat"),
    ("Landscape", "가로", "横", "横屏", "Paysage", "Querformat"),
    ("Light", "라이트", "ライト", "浅色", "Clair", "Hell"),
    ("Dark", "다크", "ダーク", "深色", "Sombre", "Dunkel"),
    ("High Contrast", "고대비", "ハイコントラスト", "高对比度", "Contraste élevé", "Hoher Kontrast"),
    ("Safe", "안전 영역", "セーフ", "安全区", "Zone sûre", "Sicherheitsbereich"),
    ("Guides", "가이드", "ガイド", "参考线", "Repères", "Hilfslinien"),
    ("Layout: Ready", "레이아웃: 준비됨", "レイアウト: 準備完了", "布局：就绪", "Mise en page : prête", "Layout: bereit"),
    ("Group", "그룹", "グループ化", "编组", "Grouper", "Gruppieren"),
    ("Ungroup", "그룹 해제", "グループ解除", "取消编组", "Dissocier", "Gruppierung aufheben"),
    ("Use as Mask", "마스크로 사용", "マスクとして使用", "用作蒙版", "Utiliser comme masque", "Als Maske verwenden"),
    ("Lock aspect ratio", "비율 잠금", "縦横比を固定", "锁定宽高比", "Verrouiller les proportions", "Seitenverhältnis sperren"),
    ("Base values", "기본값", "基本値", "基础值", "Valeurs de base", "Basiswerte"),
    ("Not a component", "컴포넌트 아님", "コンポーネントではありません", "不是组件", "Pas un composant", "Keine Komponente"),
    ("Wrap", "줄 바꿈", "折り返し", "换行", "Retour à la ligne", "Umbrechen"),
    ("Auto", "자동", "自動", "自动", "Auto", "Auto"),
    ("Absolute", "절대 위치", "絶対配置", "绝对定位", "Absolu", "Absolut"),
    ("Clip child content", "자식 콘텐츠 클리핑", "子コンテンツをクリップ", "裁剪子内容", "Découper le contenu enfant", "Untergeordneten Inhalt beschneiden"),
    ("Motion Link", "모션 링크", "モーションリンク", "动效链接", "Lien d'animation", "Motion-Verknüpfung"),
    ("Motion Delivery", "모션 전달", "モーション出力", "动效交付", "Livraison d'animation", "Motion-Ausgabe"),
    ("Normal -> Hover", "기본 -> 호버", "通常 -> ホバー", "正常 -> 悬停", "Normal -> Survol", "Normal -> Hover"),
    ("No report", "보고서 없음", "レポートなし", "无报告", "Aucun rapport", "Kein Bericht"),
    ("No link", "링크 없음", "リンクなし", "无链接", "Aucun lien", "Keine Verknüpfung"),
    ("Composition", "컴포지션", "コンポジション", "合成", "Composition", "Komposition"),
    ("Binding", "바인딩", "バインディング", "绑定", "Liaison", "Bindung"),
    ("Revision", "리비전", "リビジョン", "修订版", "Révision", "Revision"),
    ("Not set", "설정 안 됨", "未設定", "未设置", "Non défini", "Nicht festgelegt"),
    ("No object selected", "선택된 객체 없음", "オブジェクト未選択", "未选择对象", "Aucun objet sélectionné", "Kein Objekt ausgewählt"),
    ("No Motion binding", "모션 바인딩 없음", "モーションバインドなし", "无动效绑定", "Aucune liaison d'animation", "Keine Motion-Bindung"),
    ("Ready", "준비됨", "準備完了", "就绪", "Prêt", "Bereit"),
    ("Legacy link", "레거시 링크", "旧形式リンク", "旧版链接", "Lien hérité", "Alte Verknüpfung"),
    ("Missing binding", "바인딩 누락", "バインディングがありません", "缺少绑定", "Liaison manquante", "Bindung fehlt"),
    ("Missing composition", "컴포지션 누락", "コンポジションがありません", "缺少合成", "Composition manquante", "Komposition fehlt"),
    ("Stale revision", "오래된 리비전", "古いリビジョン", "修订版已过期", "Révision obsolète", "Veraltete Revision"),
    ("Orphan object", "고립된 객체", "孤立オブジェクト", "孤立对象", "Objet orphelin", "Verwaistes Objekt"),
    ("The Painter object and Motion binding are synchronized.", "Painter 객체와 Motion 바인딩이 동기화되었습니다.", "PainterオブジェクトとMotionバインディングは同期されています。", "Painter 对象与 Motion 绑定已同步。", "L'objet Painter et la liaison Motion sont synchronisés.", "Painter-Objekt und Motion-Bindung sind synchronisiert."),
    ("This link uses a composition ID and should be migrated to a binding ID.", "이 링크는 컴포지션 ID를 사용하므로 바인딩 ID로 마이그레이션해야 합니다.", "このリンクはコンポジションIDを使用しているため、バインディングIDへ移行してください。", "此链接使用合成 ID，应迁移到绑定 ID。", "Ce lien utilise un ID de composition et doit être migré vers un ID de liaison.", "Diese Verknüpfung verwendet eine Kompositions-ID und sollte zu einer Bindungs-ID migriert werden."),
    ("The Motion composition exists, but its referenced binding cannot be found.", "Motion 컴포지션은 있지만 참조한 바인딩을 찾을 수 없습니다.", "Motionコンポジションは存在しますが、参照バインディングが見つかりません。", "Motion 合成存在，但找不到引用的绑定。", "La composition Motion existe, mais sa liaison est introuvable.", "Die Motion-Komposition existiert, aber ihre Bindung wurde nicht gefunden."),
    ("The linked Motion composition is unavailable. Relink it to continue.", "연결된 Motion 컴포지션을 사용할 수 없습니다. 계속하려면 다시 연결하세요.", "リンクされたMotionコンポジションを利用できません。再リンクしてください。", "链接的 Motion 合成不可用。请重新链接以继续。", "La composition Motion liée est indisponible. Reliez-la pour continuer.", "Die verknüpfte Motion-Komposition ist nicht verfügbar. Verknüpfen Sie sie neu."),
    ("Painter references an older Motion composition revision.", "Painter가 이전 Motion 컴포지션 리비전을 참조합니다.", "Painterは古いMotionコンポジションのリビジョンを参照しています。", "Painter 引用了较旧的 Motion 合成修订版。", "Painter référence une ancienne révision de la composition Motion.", "Painter verweist auf eine ältere Revision der Motion-Komposition."),
    ("The link points to a Painter object that no longer exists.", "링크가 더 이상 존재하지 않는 Painter 객체를 가리킵니다.", "リンク先のPainterオブジェクトは存在しません。", "链接指向已不存在的 Painter 对象。", "Le lien pointe vers un objet Painter qui n'existe plus.", "Die Verknüpfung zeigt auf ein nicht mehr vorhandenes Painter-Objekt."),
    ("Relink", "다시 연결", "再リンク", "重新链接", "Relier", "Neu verknüpfen"),
    ("Migrate", "마이그레이션", "移行", "迁移", "Migrer", "Migrieren"),
    ("Detach Link", "링크 분리", "リンクを解除", "分离链接", "Détacher le lien", "Verknüpfung lösen"),
    ("Open Motion", "Motion 열기", "Motionを開く", "打开 Motion", "Ouvrir Motion", "Motion öffnen"),
    ("Preview Hover", "호버 미리보기", "ホバーをプレビュー", "预览悬停", "Aperçu du survol", "Hover-Vorschau"),
    ("Delivery blockers", "전달 차단 사유", "出力ブロッカー", "交付阻断项", "Blocages de livraison", "Ausgabeblocker"),
    ("No blockers reported.", "보고된 차단 사유가 없습니다.", "ブロッカーは報告されていません。", "未报告阻断项。", "Aucun blocage signalé.", "Keine Blocker gemeldet."),
    ("Figma Exchange", "Figma 교환", "Figma交換", "Figma 交换", "Échange Figma", "Figma-Austausch"),
    ("Import", "가져오기", "読み込み", "导入", "Importer", "Importieren"),
    ("Export", "내보내기", "書き出し", "导出", "Exporter", "Exportieren"),
    ("Search components", "컴포넌트 검색", "コンポーネントを検索", "搜索组件", "Rechercher des composants", "Komponenten suchen"),
    ("No components", "컴포넌트 없음", "コンポーネントなし", "无组件", "Aucun composant", "Keine Komponenten"),
    ("Search tokens", "토큰 검색", "トークンを検索", "搜索令牌", "Rechercher des jetons", "Token suchen"),
    ("No tokens", "토큰 없음", "トークンなし", "无令牌", "Aucun jeton", "Keine Token"),
    ("New", "새로 만들기", "新規", "新建", "Nouveau", "Neu"),
    ("Rename", "이름 변경", "名前を変更", "重命名", "Renommer", "Umbenennen"),
    ("Detach", "분리", "切り離す", "分离", "Détacher", "Trennen"),
    ("Appearance", "모양", "アピアランス", "外观", "Apparence", "Erscheinungsbild"),
    ("Solid", "단색", "単色", "纯色", "Uni", "Einfarbig"),
    ("Linear", "선형", "線形", "线性", "Linéaire", "Linear"),
    ("Radial", "방사형", "放射状", "径向", "Radial", "Radial"),
    ("Drop Shadow", "드롭 섀도", "ドロップシャドウ", "投影", "Ombre portée", "Schlagschatten"),
    ("Inner Shadow", "내부 그림자", "内側シャドウ", "内阴影", "Ombre interne", "Innerer Schatten"),
    ("Layer Blur", "레이어 블러", "レイヤーブラー", "图层模糊", "Flou du calque", "Ebenenunschärfe"),
    ("Background Blur", "배경 블러", "背景ブラー", "背景模糊", "Flou d'arrière-plan", "Hintergrundunschärfe"),
    ("Color / General Print", "컬러 / 일반 인쇄", "カラー / 一般印刷", "彩色 / 常规打印", "Couleur / Impression générale", "Farbe / Allgemeiner Druck"),
    ("Line Art / Manga", "선화 / 만화", "線画 / マンガ", "线稿 / 漫画", "Dessin au trait / Manga", "Strichzeichnung / Manga"),
    ("Large Poster", "대형 포스터", "大型ポスター", "大型海报", "Grande affiche", "Großes Poster"),
    ("Resample pixel data", "픽셀 데이터 리샘플링", "ピクセルデータを再サンプル", "重采样像素数据", "Rééchantillonner les pixels", "Pixeldaten neu berechnen"),
    ("Foreground / background colors", "전경색 / 배경색", "描画色 / 背景色", "前景色 / 背景色", "Couleurs de premier plan / arrière-plan", "Vordergrund- / Hintergrundfarben"),
    ("Foreground color", "전경색", "描画色", "前景色", "Couleur de premier plan", "Vordergrundfarbe"),
    ("Background color", "배경색", "背景色", "背景色", "Couleur d'arrière-plan", "Hintergrundfarbe"),
    ("Swap foreground/background", "전경색/배경색 교체", "描画色と背景色を入れ替え", "交换前景色/背景色", "Permuter premier plan/arrière-plan", "Vorder-/Hintergrund tauschen"),
    ("PBR", "PBR", "PBR", "PBR", "PBR", "PBR"),
    ("BRUSH", "브러시", "ブラシ", "画笔", "PINCEAU", "PINSEL"),
    ("Advanced Brush Controls", "고급 브러시 설정", "詳細ブラシ設定", "高级画笔设置", "Réglages avancés du pinceau", "Erweiterte Pinseleinstellungen"),
    ("Flip X", "좌우 뒤집기", "左右反転", "水平翻转", "Retourner horizontalement", "Horizontal spiegeln"),
    ("Flip Y", "상하 뒤집기", "上下反転", "垂直翻转", "Retourner verticalement", "Vertikal spiegeln"),
    ("Active brush library", "활성 브러시 라이브러리", "使用中のブラシライブラリ", "当前画笔库", "Bibliothèque de pinceaux active", "Aktive Pinselbibliothek"),
    ("Filter brushes", "브러시 필터", "ブラシを絞り込む", "筛选画笔", "Filtrer les pinceaux", "Pinsel filtern"),
    ("Compact Brush Selector", "간단 브러시 선택기", "コンパクトブラシセレクター", "紧凑画笔选择器", "Sélecteur compact", "Kompakte Pinselauswahl"),
    ("Manage custom brushes", "사용자 브러시 관리", "カスタムブラシを管理", "管理自定义画笔", "Gérer les pinceaux personnalisés", "Eigene Pinsel verwalten"),
    ("Save Current as New…", "현재 설정을 새 브러시로 저장…", "現在の設定を新規保存…", "将当前设置另存为新画笔…", "Enregistrer comme nouveau…", "Aktuell als neu speichern…"),
    ("Update Selected Custom Brush", "선택한 사용자 브러시 업데이트", "選択したカスタムブラシを更新", "更新所选自定义画笔", "Mettre à jour le pinceau sélectionné", "Ausgewählten Pinsel aktualisieren"),
    ("Rename / Tags…", "이름 / 태그 변경…", "名前 / タグを変更…", "重命名 / 标签…", "Renommer / Étiquettes…", "Umbenennen / Tags…"),
    ("Import Brush Bundle…", "브러시 번들 가져오기…", "ブラシバンドルを読み込み…", "导入画笔包…", "Importer un lot de pinceaux…", "Pinselpaket importieren…"),
    ("Export My Brushes…", "내 브러시 내보내기…", "マイブラシを書き出し…", "导出我的画笔…", "Exporter mes pinceaux…", "Meine Pinsel exportieren…"),
    ("Default Layer", "기본 레이어", "デフォルトレイヤー", "默认图层", "Calque par défaut", "Standardebene"),
    ("New Layer", "새 레이어", "新規レイヤー", "新建图层", "Nouveau calque", "Neue Ebene"),
    ("New Material Paint Layer", "새 머티리얼 페인트 레이어", "新規マテリアルペイントレイヤー", "新建材质绘画图层", "Nouveau calque de peinture matériau", "Neue Material-Malebene"),
    ("Toggle Visibility", "표시 전환", "表示を切り替え", "切换可见性", "Basculer la visibilité", "Sichtbarkeit umschalten"),
    ("Cut", "잘라내기", "切り取り", "剪切", "Couper", "Ausschneiden"),
    ("Copy", "복사", "コピー", "复制", "Copier", "Kopieren"),
    ("Paste", "붙여넣기", "貼り付け", "粘贴", "Coller", "Einfügen"),
    ("Select All", "모두 선택", "すべて選択", "全选", "Tout sélectionner", "Alles auswählen"),
    ("Crop To Selection", "선택 영역으로 자르기", "選択範囲で切り抜き", "裁剪到选区", "Recadrer sur la sélection", "Auf Auswahl zuschneiden"),
    ("Gradient Fill", "그라디언트 채우기", "グラデーション塗り", "渐变填充", "Remplissage en dégradé", "Verlaufsfüllung"),
    ("Pattern Fill", "패턴 채우기", "パターン塗り", "图案填充", "Remplissage par motif", "Musterfüllung"),
    ("Zoom In", "확대", "拡大", "放大", "Zoom avant", "Vergrößern"),
    ("Zoom Out", "축소", "縮小", "缩小", "Zoom arrière", "Verkleinern"),
    ("Fit", "맞춤", "全体表示", "适合", "Ajuster", "Einpassen"),
    ("Reset Pan", "화면 이동 초기화", "パンをリセット", "重置平移", "Réinitialiser le déplacement", "Ansicht zurücksetzen"),
    ("Pixels", "픽셀", "ピクセル", "像素", "Pixels", "Pixel"),
    ("Harmony", "색상 조화", "ハーモニー", "色彩和谐", "Harmonie", "Harmonie"),
    ("Hardness", "경도", "硬さ", "硬度", "Dureté", "Härte"),
    ("Previous", "이전", "前", "上一个", "Précédent", "Vorher"),
    ("Current", "현재", "現在", "当前", "Actuel", "Aktuell"),
    ("Color Stops", "색상 정지점", "カラーストップ", "色标", "Points de couleur", "Farbstopps"),
    ("Component name", "컴포넌트 이름", "コンポーネント名", "组件名称", "Nom du composant", "Komponentenname"),
    ("Select", "선택", "選択", "选择", "Sélectionner", "Auswählen"),
    ("Instance", "인스턴스", "インスタンス", "实例", "Instance", "Instanz"),
    ("Variant", "배리언트", "バリアント", "变体", "Variante", "Variante"),
    ("Figma file URL or file key", "Figma 파일 URL 또는 파일 키", "FigmaファイルURLまたはキー", "Figma 文件 URL 或文件密钥", "URL ou clé du fichier Figma", "Figma-Datei-URL oder -Schlüssel"),
    ("Replace current UI document", "현재 UI 문서 교체", "現在のUIドキュメントを置換", "替换当前 UI 文档", "Remplacer le document UI actuel", "Aktuelles UI-Dokument ersetzen"),
    ("Append as new artboards", "새 아트보드로 추가", "新規アートボードとして追加", "追加为新画板", "Ajouter comme nouveaux plans de travail", "Als neue Artboards anhängen"),
    ("Import Editable Figma File", "편집 가능한 Figma 파일 가져오기", "編集可能なFigmaファイルを読み込み", "导入可编辑 Figma 文件", "Importer un fichier Figma modifiable", "Bearbeitbare Figma-Datei importieren"),
    ("Import Figma REST JSON...", "Figma REST JSON 가져오기...", "Figma REST JSONを読み込み...", "导入 Figma REST JSON...", "Importer le JSON REST Figma...", "Figma-REST-JSON importieren..."),
    ("EXPORT TO FIGMA", "FIGMA로 내보내기", "FIGMAへ書き出し", "导出到 FIGMA", "EXPORTER VERS FIGMA", "NACH FIGMA EXPORTIEREN"),
    ("Export Figma Plugin Bundle...", "Figma 플러그인 번들 내보내기...", "Figmaプラグインバンドルを書き出し...", "导出 Figma 插件包...", "Exporter le bundle du plugin Figma...", "Figma-Pluginpaket exportieren..."),
    ("No UI document", "UI 문서 없음", "UIドキュメントなし", "无 UI 文档", "Aucun document UI", "Kein UI-Dokument"),
    ("Section name", "섹션 이름", "セクション名", "区段名称", "Nom de la section", "Abschnittsname"),
    ("Object IDs, comma separated", "객체 ID, 쉼표로 구분", "オブジェクトID（カンマ区切り）", "对象 ID，以逗号分隔", "ID d'objets, séparés par des virgules", "Objekt-IDs, durch Kommas getrennt"),
    ("Edit current override", "현재 오버라이드 편집", "現在のオーバーライドを編集", "编辑当前覆盖", "Modifier la surcharge actuelle", "Aktuelle Überschreibung bearbeiten"),
    ("Apply Range", "범위 적용", "範囲を適用", "应用范围", "Appliquer la plage", "Bereich anwenden"),
    ("Clear Range", "범위 지우기", "範囲を解除", "清除范围", "Effacer la plage", "Bereich löschen"),
    ("Enable 9-slice", "9-슬라이스 사용", "9スライスを有効化", "启用九宫格", "Activer le découpage en 9", "9-Slice aktivieren"),
    ("Locked", "잠김", "ロック中", "已锁定", "Verrouillé", "Gesperrt"),
    ("Motion composition ID", "Motion 컴포지션 ID", "MotionコンポジションID", "Motion 合成 ID", "ID de composition Motion", "Motion-Kompositions-ID"),
    ("Canonical binding ID", "표준 바인딩 ID", "正規バインディングID", "规范绑定 ID", "ID de liaison canonique", "Kanonische Bindungs-ID"),
    ("Template ID", "템플릿 ID", "テンプレートID", "模板 ID", "ID du modèle", "Vorlagen-ID"),
    ("Template name", "템플릿 이름", "テンプレート名", "模板名称", "Nom du modèle", "Vorlagenname"),
    ("Save Current as Template", "현재 문서를 템플릿으로 저장", "現在をテンプレートとして保存", "将当前内容保存为模板", "Enregistrer comme modèle", "Aktuell als Vorlage speichern"),
    ("Install Template Package", "템플릿 패키지 설치", "テンプレートパッケージをインストール", "安装模板包", "Installer le paquet de modèles", "Vorlagenpaket installieren"),
    ("Add Comment", "댓글 추가", "コメントを追加", "添加评论", "Ajouter un commentaire", "Kommentar hinzufügen"),
    ("Create Checkpoint", "체크포인트 만들기", "チェックポイントを作成", "创建检查点", "Créer un point de contrôle", "Prüfpunkt erstellen"),
    ("Export Offline Review", "오프라인 리뷰 내보내기", "オフラインレビューを書き出し", "导出离线审阅", "Exporter la révision hors ligne", "Offline-Review exportieren"),
    ("Export Interactive Prototype", "인터랙티브 프로토타입 내보내기", "インタラクティブプロトタイプを書き出し", "导出交互原型", "Exporter le prototype interactif", "Interaktiven Prototyp exportieren"),
    ("Texture Atlas", "텍스처 아틀라스", "テクスチャアトラス", "纹理图集", "Atlas de textures", "Texturatlas"),
    ("Export Production Assets", "프로덕션 에셋 내보내기", "プロダクションアセットを書き出し", "导出生产资源", "Exporter les ressources de production", "Produktionsassets exportieren"),
    ("Plan and Preview", "계획 및 미리보기", "計画とプレビュー", "规划并预览", "Planifier et prévisualiser", "Planen und Vorschau"),
    ("No AI plan", "AI 계획 없음", "AIプランなし", "无 AI 计划", "Aucun plan IA", "Kein KI-Plan"),
    ("Apply Approved Plan", "승인된 계획 적용", "承認済みプランを適用", "应用已批准计划", "Appliquer le plan approuvé", "Genehmigten Plan anwenden"),
    ("Run Product QA", "제품 QA 실행", "製品QAを実行", "运行产品 QA", "Exécuter la QA produit", "Produkt-QA ausführen"),
    ("Accessibility QA", "접근성 QA", "アクセシビリティQA", "无障碍 QA", "QA d’accessibilité", "Barrierefreiheits-QA"),
    ("Not checked", "검사 전", "未確認", "未检查", "Non vérifié", "Nicht geprüft"),
    ("Run Product QA to inspect the current UI document.", "제품 QA를 실행해 현재 UI 문서를 검사하세요.", "製品QAを実行して現在のUIドキュメントを検査します。", "运行产品 QA 以检查当前 UI 文档。", "Exécutez la QA produit pour inspecter le document UI actuel.", "Führen Sie die Produkt-QA aus, um das aktuelle UI-Dokument zu prüfen."),
    ("No audit report yet", "아직 감사 보고서가 없습니다", "監査レポートはまだありません", "尚无审核报告", "Aucun rapport d’audit", "Noch kein Prüfbericht"),
    ("No accessibility issues found", "접근성 문제가 발견되지 않았습니다", "アクセシビリティの問題は見つかりませんでした", "未发现无障碍问题", "Aucun problème d’accessibilité détecté", "Keine Barrierefreiheitsprobleme gefunden"),
    ("{errors} errors · {warnings} warnings", "오류 {errors}개 · 경고 {warnings}개", "エラー {errors}件 · 警告 {warnings}件", "{errors} 个错误 · {warnings} 个警告", "{errors} erreurs · {warnings} avertissements", "{errors} Fehler · {warnings} Warnungen"),
    ("{objects} objects · contrast {checked} checked · {unknown} unknown", "객체 {objects}개 · 대비 검사 {checked}개 · 확인 불가 {unknown}개", "オブジェクト {objects}件 · コントラスト確認 {checked}件 · 不明 {unknown}件", "{objects} 个对象 · 已检查 {checked} 个对比度 · {unknown} 个未知", "{objects} objets · {checked} contrastes vérifiés · {unknown} inconnus", "{objects} Objekte · {checked} Kontraste geprüft · {unknown} unbekannt"),
    ("Accessible name is missing", "접근성 이름이 없습니다", "アクセシブル名がありません", "缺少无障碍名称", "Le nom accessible est manquant", "Barrierefreier Name fehlt"),
    ("Focus order is duplicated", "포커스 순서가 중복되었습니다", "フォーカス順序が重複しています", "焦点顺序重复", "L’ordre de focus est dupliqué", "Fokusreihenfolge ist doppelt"),
    ("Focus target is unavailable", "포커스 대상이 사용할 수 없는 상태입니다", "フォーカス対象を使用できません", "焦点目标不可用", "La cible de focus est indisponible", "Fokusziel ist nicht verfügbar"),
    ("Touch target is too small", "터치 영역이 너무 작습니다", "タッチ領域が小さすぎます", "触控目标太小", "La cible tactile est trop petite", "Berührungsziel ist zu klein"),
    ("Text contrast is too low", "텍스트 대비가 너무 낮습니다", "テキストのコントラストが低すぎます", "文本对比度过低", "Le contraste du texte est trop faible", "Textkontrast ist zu niedrig"),
    ("Focus order conflicts with visual order", "포커스 순서가 시각적 순서와 다릅니다", "フォーカス順序が視覚順序と一致しません", "焦点顺序与视觉顺序冲突", "L’ordre de focus diffère de l’ordre visuel", "Fokusreihenfolge widerspricht der visuellen Reihenfolge"),
    ("Select Same", "같은 속성 선택", "同じ属性を選択", "选择相同属性", "Sélectionner les mêmes propriétés", "Gleiche Eigenschaften auswählen"),
    ("Find / Replace", "찾기 / 바꾸기", "検索 / 置換", "查找 / 替换", "Rechercher / Remplacer", "Suchen / Ersetzen"),
    ("Preview text and linked references before changing the document.", "문서를 변경하기 전에 텍스트와 연결된 참조를 미리 확인합니다.", "文書を変更する前にテキストとリンク参照を確認します。", "更改文档前预览文本和链接引用。", "Prévisualisez le texte et les références liées avant de modifier le document.", "Text und verknüpfte Referenzen vor der Änderung prüfen."),
    ("Find", "찾기", "検索", "查找", "Rechercher", "Suchen"),
    ("Replace with", "바꿀 내용", "置換後", "替换为", "Remplacer par", "Ersetzen durch"),
    ("Font", "글꼴", "フォント", "字体", "Police", "Schrift"),
    ("Case sensitive", "대/소문자 구분", "大文字と小文字を区別", "区分大小写", "Respecter la casse", "Groß-/Kleinschreibung"),
    ("Whole value", "전체 값 일치", "値全体に一致", "匹配完整值", "Valeur entière", "Gesamten Wert abgleichen"),
    ("Preview", "미리보기", "プレビュー", "预览", "Aperçu", "Vorschau"),
    ("Enter a value, then preview matching UI properties.", "찾을 값을 입력한 뒤 일치하는 UI 속성을 미리 확인하세요.", "検索値を入力して一致する UI プロパティを確認してください。", "输入查找值，然后预览匹配的 UI 属性。", "Saisissez une valeur puis prévisualisez les propriétés UI correspondantes.", "Wert eingeben und passende UI-Eigenschaften prüfen."),
    ("Select valid", "적용 가능 항목 선택", "適用可能な項目を選択", "选择可应用项", "Sélectionner les éléments valides", "Gültige auswählen"),
    ("Apply selected", "선택 항목 적용", "選択項目を適用", "应用所选项", "Appliquer la sélection", "Auswahl anwenden"),
    ("No UI document is available.", "사용 가능한 UI 문서가 없습니다.", "利用可能な UI 文書がありません。", "没有可用的 UI 文档。", "Aucun document UI disponible.", "Kein UI-Dokument verfügbar."),
    ("Enter a value to find.", "찾을 값을 입력하세요.", "検索する値を入力してください。", "请输入要查找的值。", "Saisissez une valeur à rechercher.", "Suchwert eingeben."),
    ("Select at least one category.", "카테고리를 하나 이상 선택하세요.", "カテゴリを 1 つ以上選択してください。", "请至少选择一个类别。", "Sélectionnez au moins une catégorie.", "Mindestens eine Kategorie auswählen."),
    ("No matches found.", "일치하는 항목이 없습니다.", "一致する項目がありません。", "未找到匹配项。", "Aucune correspondance.", "Keine Treffer gefunden."),
    ("Blocked", "차단됨", "ブロック", "已阻止", "Bloqué", "Blockiert"),
    ("{count} matches · {valid} can be applied", "{count}개 일치 · {valid}개 적용 가능", "{count} 件一致 · {valid} 件適用可能", "{count} 个匹配 · {valid} 个可应用", "{count} correspondances · {valid} applicables", "{count} Treffer · {valid} anwendbar"),
    ("{count} matches applied.", "{count}개 항목을 적용했습니다.", "{count} 件を適用しました。", "已应用 {count} 个匹配项。", "{count} correspondances appliquées.", "{count} Treffer angewendet."),
    ("Batch Rename", "일괄 이름 변경", "一括名前変更", "批量重命名", "Renommer par lot", "Stapelweise umbenennen"),
    ("Preview names for the selected UI objects before applying.", "선택한 UI 객체의 이름을 적용 전에 미리 확인합니다.", "選択した UI オブジェクト名を適用前に確認します。", "应用前预览所选 UI 对象的名称。", "Prévisualisez les noms des objets UI sélectionnés avant application.", "Namen der ausgewählten UI-Objekte vor dem Anwenden prüfen."),
    ("Prefix", "접두사", "接頭辞", "前缀", "Préfixe", "Präfix"),
    ("Suffix", "접미사", "接尾辞", "后缀", "Suffixe", "Suffix"),
    ("Add numbering", "순번 추가", "連番を追加", "添加编号", "Ajouter une numérotation", "Nummerierung hinzufügen"),
    ("Start", "시작", "開始", "起始", "Début", "Start"),
    ("Digits", "자릿수", "桁数", "位数", "Chiffres", "Stellen"),
    ("Select UI objects to rename.", "이름을 변경할 UI 객체를 선택하세요.", "名前を変更する UI オブジェクトを選択してください。", "请选择要重命名的 UI 对象。", "Sélectionnez les objets UI à renommer.", "UI-Objekte zum Umbenennen auswählen."),
    ("{count} selected objects", "{count}개 객체 선택됨", "{count} 個のオブジェクトを選択", "已选择 {count} 个对象", "{count} objets sélectionnés", "{count} Objekte ausgewählt"),
    ("{count} names can be changed", "{count}개 이름 변경 가능", "{count} 件の名前を変更可能", "可更改 {count} 个名称", "{count} noms peuvent être modifiés", "{count} Namen können geändert werden"),
    ("No name changes to apply.", "적용할 이름 변경이 없습니다.", "適用する名前変更がありません。", "没有可应用的名称更改。", "Aucun changement de nom à appliquer.", "Keine Namensänderungen anzuwenden."),
    ("{count} names changed.", "{count}개 이름을 변경했습니다.", "{count} 件の名前を変更しました。", "已更改 {count} 个名称。", "{count} noms modifiés.", "{count} Namen geändert."),
    ("Object Type", "객체 유형", "オブジェクトの種類", "对象类型", "Type d’objet", "Objekttyp"),
    ("Text Style", "텍스트 스타일", "テキストスタイル", "文本样式", "Style de texte", "Textstil"),
    ("Interaction", "인터랙션", "インタラクション", "交互", "Interaction", "Interaktion"),
    ("Select same object type", "같은 객체 유형 선택", "同じオブジェクト種類を選択", "选择相同对象类型", "Sélectionner le même type d’objet", "Gleichen Objekttyp auswählen"),
    ("Select same fill", "같은 채우기 선택", "同じ塗りを選択", "选择相同填充", "Sélectionner le même remplissage", "Gleiche Füllung auswählen"),
    ("Select same component", "같은 컴포넌트 선택", "同じコンポーネントを選択", "选择相同组件", "Sélectionner le même composant", "Gleiche Komponente auswählen"),
    ("Select matching objects on the active artboard", "활성 아트보드에서 일치하는 객체를 선택합니다", "アクティブなアートボードで一致するオブジェクトを選択します", "在活动画板中选择匹配对象", "Sélectionner les objets correspondants sur le plan de travail actif", "Übereinstimmende Objekte auf der aktiven Zeichenfläche auswählen"),
    ("Select matching instances on the active artboard", "활성 아트보드에서 일치하는 인스턴스를 선택합니다", "アクティブなアートボードで一致するインスタンスを選択します", "在活动画板中选择匹配实例", "Sélectionner les instances correspondantes sur le plan de travail actif", "Übereinstimmende Instanzen auf der aktiven Zeichenfläche auswählen"),
    ("Production tools ready", "프로덕션 도구 준비됨", "プロダクションツール準備完了", "生产工具已就绪", "Outils de production prêts", "Produktionswerkzeuge bereit"),
    ("Painter UI Template Gallery", "Painter UI 템플릿 갤러리", "Painter UIテンプレートギャラリー", "Painter UI 模板库", "Galerie de modèles Painter UI", "Painter-UI-Vorlagengalerie"),
    ("Search templates, categories, or tags", "템플릿, 카테고리 또는 태그 검색", "テンプレート、カテゴリ、タグを検索", "搜索模板、类别或标签", "Rechercher modèles, catégories ou tags", "Vorlagen, Kategorien oder Tags suchen"),
    ("All categories", "모든 카테고리", "すべてのカテゴリ", "所有类别", "Toutes les catégories", "Alle Kategorien"),
    ("Select a template", "템플릿을 선택하세요", "テンプレートを選択", "选择模板", "Sélectionnez un modèle", "Vorlage auswählen"),
    ("Use Template", "템플릿 사용", "テンプレートを使用", "使用模板", "Utiliser le modèle", "Vorlage verwenden"),
    ("No matching templates", "일치하는 템플릿 없음", "一致するテンプレートなし", "无匹配模板", "Aucun modèle correspondant", "Keine passenden Vorlagen"),
    ("No Motion link report. Select a linked UI object to inspect it.", "Motion 링크 보고서가 없습니다. 연결된 UI 객체를 선택해 확인하세요.", "Motionリンクレポートがありません。リンクされたUIオブジェクトを選択してください。", "无 Motion 链接报告。请选择已链接的 UI 对象进行检查。", "Aucun rapport de lien Motion. Sélectionnez un objet UI lié.", "Kein Motion-Link-Bericht. Wählen Sie ein verknüpftes UI-Objekt aus."),
    ("No Motion delivery report. Select an animated UI object to inspect it.", "Motion 전달 보고서가 없습니다. 애니메이션 UI 객체를 선택해 확인하세요.", "Motion出力レポートがありません。アニメーション付きUIオブジェクトを選択してください。", "无 Motion 交付报告。请选择带动画的 UI 对象进行检查。", "Aucun rapport de livraison Motion. Sélectionnez un objet UI animé.", "Kein Motion-Ausgabebericht. Wählen Sie ein animiertes UI-Objekt aus."),
    ("The selected UI object has no Motion link.", "선택한 UI 객체에 Motion 링크가 없습니다.", "選択したUIオブジェクトにはMotionリンクがありません。", "所选 UI 对象没有 Motion 链接。", "L'objet UI sélectionné n'a aucun lien Motion.", "Das ausgewählte UI-Objekt hat keine Motion-Verknüpfung."),
    ("This Motion link report is not a supported v2 report.", "이 Motion 링크 보고서는 지원되는 v2 보고서가 아닙니다.", "このMotionリンクレポートは対応するv2形式ではありません。", "此 Motion 链接报告不是受支持的 v2 报告。", "Ce rapport de lien Motion n'est pas un rapport v2 pris en charge.", "Dieser Motion-Link-Bericht ist kein unterstützter v2-Bericht."),
    ("All kinds", "모든 종류", "すべての種類", "所有类型", "Tous les types", "Alle Arten"),
    ("Value or JSON", "값 또는 JSON", "値またはJSON", "值或 JSON", "Valeur ou JSON", "Wert oder JSON"),
    ("Bind", "연결", "バインド", "绑定", "Lier", "Binden"),
    ("Unbind", "연결 해제", "バインド解除", "解除绑定", "Délier", "Lösen"),
    ("Assets", "에셋", "アセット", "资源", "Ressources", "Assets"),
    ("Design", "디자인", "デザイン", "设计", "Design", "Design"),
    ("Prototype", "프로토타입", "プロトタイプ", "原型", "Prototype", "Prototyp"),
    ("Document", "문서", "ドキュメント", "文档", "Document", "Dokument"),
    ("PAGES", "페이지", "ページ", "页面", "PAGES", "SEITEN"),
    (
        "Search pages and layers",
        "페이지와 레이어 검색",
        "ページとレイヤーを検索",
        "搜索页面和图层",
        "Rechercher pages et calques",
        "Seiten und Ebenen suchen",
    ),
    ("Artboard", "아트보드", "アートボード", "画板", "Plan de travail", "Zeichenfläche"),
    ("Frame", "프레임", "フレーム", "框架", "Cadre", "Rahmen"),
    ("Group", "그룹", "グループ", "组", "Groupe", "Gruppe"),
    ("Text", "텍스트", "テキスト", "文本", "Texte", "Text"),
    ("Button", "버튼", "ボタン", "按钮", "Bouton", "Schaltfläche"),
    ("Image", "이미지", "画像", "图像", "Image", "Bild"),
    ("Ellipse", "타원", "楕円", "椭圆", "Ellipse", "Ellipse"),
    ("Line", "선", "線", "线", "Ligne", "Linie"),
    ("Progress", "진행률", "進行状況", "进度", "Progression", "Fortschritt"),
    ("Object", "객체", "オブジェクト", "对象", "Objet", "Objekt"),
    ("Select an object to edit its properties.", "속성을 편집할 객체를 선택하세요.", "プロパティを編集するオブジェクトを選択してください。", "选择一个对象以编辑其属性。", "Sélectionnez un objet pour modifier ses propriétés.", "Wählen Sie ein Objekt aus, um seine Eigenschaften zu bearbeiten."),
    ("Align or distribute the current selection.", "현재 선택 항목을 정렬하거나 균등 분배합니다.", "現在の選択範囲を整列または均等配置します。", "对当前选择进行对齐或均匀分布。", "Alignez ou répartissez la sélection actuelle.", "Richten Sie die aktuelle Auswahl aus oder verteilen Sie sie."),
    ("Layout, clipping, appearance, and constraints", "레이아웃, 클리핑, 모양 및 제약 조건", "レイアウト、クリッピング、外観、制約", "布局、裁剪、外观和约束", "Disposition, découpage, apparence et contraintes", "Layout, Beschneidung, Darstellung und Einschränkungen"),
    ("Layout, appearance, and constraints", "레이아웃, 모양 및 제약 조건", "レイアウト、外観、制約", "布局、外观和约束", "Disposition, apparence et contraintes", "Layout, Darstellung und Einschränkungen"),
    ("Typography, appearance, and accessibility", "타이포그래피, 모양 및 접근성", "タイポグラフィ、外観、アクセシビリティ", "排版、外观和无障碍", "Typographie, apparence et accessibilité", "Typografie, Darstellung und Barrierefreiheit"),
    ("Variable Axes", "가변 글꼴 축", "バリアブルフォント軸", "可变字体轴", "Axes de police variable", "Variable Schriftachsen"),
    ("Enable OpenType wght axis", "OpenType 굵기 축 사용", "OpenType wght 軸を有効化", "启用 OpenType wght 轴", "Activer l'axe OpenType wght", "OpenType-Achse wght aktivieren"),
    ("Enable OpenType wdth axis", "OpenType 너비 축 사용", "OpenType wdth 軸を有効化", "启用 OpenType wdth 轴", "Activer l'axe OpenType wdth", "OpenType-Achse wdth aktivieren"),
    ("Enable OpenType opsz axis", "OpenType 옵티컬 크기 축 사용", "OpenType opsz 軸を有効化", "启用 OpenType opsz 轴", "Activer l'axe OpenType opsz", "OpenType-Achse opsz aktivieren"),
    ("Component state, typography, and interaction", "컴포넌트 상태, 타이포그래피 및 인터랙션", "コンポーネント状態、タイポグラフィ、インタラクション", "组件状态、排版和交互", "État du composant, typographie et interaction", "Komponentenstatus, Typografie und Interaktion"),
    ("Source, crop behavior, and export", "소스, 자르기 방식 및 내보내기", "ソース、クロップ動作、書き出し", "源、裁剪行为和导出", "Source, recadrage et export", "Quelle, Zuschneiden und Export"),
    ("Geometry, appearance, and delivery", "지오메트리, 모양 및 전달", "ジオメトリ、外観、配信", "几何、外观和交付", "Géométrie, apparence et livraison", "Geometrie, Darstellung und Ausgabe"),
    ("Detach inspector", "인스펙터 분리", "インスペクターを分離", "分离检查器", "Détacher l'inspecteur", "Inspektor abdocken"),
    ("Dock inspector", "인스펙터 도킹", "インスペクターをドッキング", "停靠检查器", "Ancrer l'inspecteur", "Inspektor andocken"),
    ("Close temporary properties", "임시 속성 닫기", "一時プロパティを閉じる", "关闭临时属性", "Fermer les propriétés temporaires", "Temporäre Eigenschaften schließen"),
    ("Pin properties", "속성 패널 고정", "プロパティを固定", "固定属性面板", "Épingler les propriétés", "Eigenschaften anheften"),
    ("Auto-hide properties", "속성 패널 자동 숨김", "プロパティを自動的に隠す", "自动隐藏属性面板", "Masquer automatiquement les propriétés", "Eigenschaften automatisch ausblenden"),
    ("Layers and assets", "레이어 및 에셋", "レイヤーとアセット", "图层和资源", "Calques et ressources", "Ebenen und Assets"),
    ("Properties", "속성", "プロパティ", "属性", "Propriétés", "Eigenschaften"),
    ("Pin navigator", "탐색 패널 고정", "ナビゲーターを固定", "固定导航面板", "Épingler le navigateur", "Navigator anheften"),
    ("Close navigator", "탐색 패널 닫기", "ナビゲーターを閉じる", "关闭导航面板", "Fermer le navigateur", "Navigator schließen"),
    ("Show navigator", "탐색 패널 열기", "ナビゲーターを表示", "显示导航面板", "Afficher le navigateur", "Navigator anzeigen"),
    ("Auto-hide navigator", "탐색 패널 자동 숨김", "ナビゲーターを自動的に隠す", "自动隐藏导航面板", "Masquer automatiquement le navigateur", "Navigator automatisch ausblenden"),
    ("Detach navigator", "탐색 패널 분리", "ナビゲーターを切り離す", "分离导航面板", "Détacher le navigateur", "Navigator lösen"),
    ("Dock navigator", "탐색 패널 도킹", "ナビゲーターをドッキング", "停靠导航面板", "Ancrer le navigateur", "Navigator andocken"),
    ("UI Layers and Assets", "UI 레이어 및 에셋", "UIレイヤーとアセット", "UI 图层和资源", "Calques et ressources UI", "UI-Ebenen und Assets"),
    ("Zoom and fit", "확대/축소 및 맞춤", "ズームとフィット", "缩放和适配", "Zoom et ajustement", "Zoom und Einpassen"),
    ("Fit all artboards", "모든 아트보드 맞춤", "すべてのアートボードに合わせる", "适配所有画板", "Ajuster tous les plans de travail", "Alle Zeichenflächen einpassen"),
    ("Fit active artboard", "현재 아트보드 맞춤", "現在のアートボードに合わせる", "适配当前画板", "Ajuster le plan de travail actif", "Aktive Zeichenfläche einpassen"),
    ("Fit selection", "선택 영역 맞춤", "選択範囲に合わせる", "适配所选内容", "Ajuster à la sélection", "Auswahl einpassen"),
    ("Select parent", "상위 객체 선택", "親オブジェクトを選択", "选择父对象", "Sélectionner le parent", "Übergeordnetes Objekt auswählen"),
    ("Deep select", "깊은 객체 선택", "深いオブジェクトを選択", "深层选择", "Sélection profonde", "Tiefenauswahl"),
    ("Enter group", "그룹 편집 시작", "グループ編集を開始", "进入组编辑", "Entrer dans le groupe", "Gruppe bearbeiten"),
    ("Exit group", "그룹 편집 종료", "グループ編集を終了", "退出组编辑", "Quitter le groupe", "Gruppenbearbeitung beenden"),
    ("Advanced properties", "고급 속성", "詳細プロパティ", "高级属性", "Propriétés avancées", "Erweiterte Eigenschaften"),
    ("Content Test", "콘텐츠 테스트", "コンテンツテスト", "内容测试", "Test de contenu", "Inhaltstest"),
    ("Off", "꺼짐", "オフ", "关闭", "Désactivé", "Aus"),
    ("Long Korean", "긴 한국어", "長い韓国語", "长韩文", "Coréen long", "Langes Koreanisch"),
    ("Long English", "긴 영문", "長い英語", "长英文", "Anglais long", "Langes Englisch"),
    ("Large Type", "큰 글자", "大きな文字", "大字号", "Grand texte", "Große Schrift"),
    ("Missing Image", "누락 이미지", "画像なし", "缺失图像", "Image manquante", "Fehlendes Bild"),
    ("Empty List", "빈 목록", "空のリスト", "空列表", "Liste vide", "Leere Liste"),
    ("Clear content preview", "콘텐츠 프리뷰 지우기", "コンテンツプレビューを消去", "清除内容预览", "Effacer l'aperçu du contenu", "Inhaltsvorschau löschen"),
    ("Preview only - document is unchanged", "프리뷰 전용 · 문서는 변경되지 않음", "プレビューのみ・文書は変更されません", "仅预览，文档不会更改", "Aperçu uniquement · document inchangé", "Nur Vorschau · Dokument bleibt unverändert"),
    ("Suggested tokens", "추천 토큰", "提案トークン", "建议令牌", "Jetons suggérés", "Vorgeschlagene Token"),
    ("Bind suggested token", "추천 토큰 연결", "提案トークンをバインド", "绑定建议令牌", "Lier le jeton suggéré", "Vorgeschlagenes Token binden"),
    ("Exact value match", "정확한 값 일치", "値が完全一致", "值完全匹配", "Valeur identique", "Exakter Wert"),
    ("Text color", "텍스트 색상", "テキストカラー", "文本颜色", "Couleur du texte", "Textfarbe"),
    ("Stroke width", "선 두께", "線の太さ", "描边宽度", "Épaisseur du contour", "Konturstärke"),
    ("Font size", "글자 크기", "フォントサイズ", "字号", "Taille de police", "Schriftgröße"),
    ("Cross gap", "교차 간격", "交差間隔", "交叉间距", "Espacement transversal", "Querabstand"),
    ("Padding left", "왼쪽 패딩", "左パディング", "左内边距", "Marge interne gauche", "Innenabstand links"),
    ("Padding top", "위쪽 패딩", "上パディング", "上内边距", "Marge interne supérieure", "Innenabstand oben"),
    ("Padding right", "오른쪽 패딩", "右パディング", "右内边距", "Marge interne droite", "Innenabstand rechts"),
    ("Padding bottom", "아래쪽 패딩", "下パディング", "下内边距", "Marge interne inférieure", "Innenabstand unten"),
    ("Rows", "행", "行", "行", "Lignes", "Zeilen"),
    ("Grid Alignment", "그리드 정렬", "グリッド配置", "网格对齐", "Alignement de la grille", "Rasterausrichtung"),
    ("Stretch", "늘이기", "ストレッチ", "拉伸", "Étirer", "Strecken"),
    ("Center", "가운데", "中央", "居中", "Centrer", "Zentrieren"),
    ("Grid Style", "그리드 스타일", "グリッドスタイル", "网格样式", "Style de grille", "Rasterstil"),
    ("Local", "로컬", "ローカル", "本地", "Local", "Lokal"),
    ("Save as grid style", "그리드 스타일로 저장", "グリッドスタイルとして保存", "另存为网格样式", "Enregistrer comme style de grille", "Als Rasterstil speichern"),
    ("Update linked grid style", "연결된 그리드 스타일 업데이트", "リンクしたグリッドスタイルを更新", "更新链接的网格样式", "Mettre à jour le style lié", "Verknüpften Rasterstil aktualisieren"),
    ("Remove grid style", "그리드 스타일 삭제", "グリッドスタイルを削除", "删除网格样式", "Supprimer le style de grille", "Rasterstil entfernen"),
    ("Save Grid Style", "그리드 스타일 저장", "グリッドスタイルを保存", "保存网格样式", "Enregistrer le style de grille", "Rasterstil speichern"),
    ("Style name:", "스타일 이름:", "スタイル名:", "样式名称：", "Nom du style :", "Stilname:"),
    ("Copy object", "객체 복사", "オブジェクトをコピー", "复制对象", "Copier l'objet", "Objekt kopieren"),
    ("Copy properties", "속성 복사", "プロパティをコピー", "复制属性", "Copier les propriétés", "Eigenschaften kopieren"),
    ("Paste properties", "속성 붙여넣기", "プロパティを貼り付け", "粘贴属性", "Coller les propriétés", "Eigenschaften einfügen"),
    ("Paste to replace", "대체하여 붙여넣기", "置き換えて貼り付け", "粘贴并替换", "Coller pour remplacer", "Zum Ersetzen einfügen"),
    ("Paste in place", "제자리에 붙여넣기", "同じ位置に貼り付け", "原位粘贴", "Coller sur place", "An Originalposition einfügen"),
    ("Recent actions", "최근 작업", "最近の操作", "最近操作", "Actions récentes", "Letzte Aktionen"),
    ("Move inside", "안으로 이동", "内側へ移動", "移入内部", "Déplacer à l’intérieur", "Nach innen verschieben"),
    ("Baseline", "기준선", "ベースライン", "基线", "Ligne de base", "Grundlinie"),
    ("Padding", "패딩", "パディング", "内边距", "Marge interne", "Innenabstand"),
    ("Equal gap", "동일 간격", "等間隔", "等间距", "Espacement égal", "Gleicher Abstand"),
    ("Equal width", "동일 너비", "同じ幅", "等宽", "Même largeur", "Gleiche Breite"),
    ("Equal height", "동일 높이", "同じ高さ", "等高", "Même hauteur", "Gleiche Höhe"),
    ("Scale selection...", "선택 영역 크기 조절...", "選択範囲を拡大・縮小...", "缩放所选内容...", "Mettre la sélection à l’échelle...", "Auswahl skalieren..."),
    ("Scale selection", "선택 영역 크기 조절", "選択範囲を拡大・縮小", "缩放所选内容", "Mettre la sélection à l’échelle", "Auswahl skalieren"),
    ("Scale percentage", "크기 비율 (%)", "拡大率 (%)", "缩放百分比 (%)", "Échelle (%)", "Skalierung (%)"),
    ("Quick Actions", "빠른 실행", "クイックアクション", "快速操作", "Actions rapides", "Schnellaktionen"),
    ("Search commands, layers, pages, components, variables", "명령, 레이어, 페이지, 컴포넌트, 변수를 검색", "コマンド、レイヤー、ページ、コンポーネント、変数を検索", "搜索命令、图层、页面、组件和变量", "Rechercher commandes, calques, pages, composants et variables", "Befehle, Ebenen, Seiten, Komponenten und Variablen suchen"),
    ("No matching actions", "일치하는 항목이 없습니다", "一致する項目がありません", "没有匹配项", "Aucun résultat", "Keine passenden Einträge"),
    ("Select tool", "선택 도구", "選択ツール", "选择工具", "Outil de sélection", "Auswahlwerkzeug"),
    ("Move and select objects", "객체 이동 및 선택", "オブジェクトを移動・選択", "移动和选择对象", "Déplacer et sélectionner", "Objekte bewegen und auswählen"),
    ("Frame tool", "프레임 도구", "フレームツール", "画框工具", "Outil Cadre", "Rahmenwerkzeug"),
    ("Draw an artboard container", "아트보드 컨테이너 그리기", "アートボードコンテナを描画", "绘制画板容器", "Dessiner un conteneur", "Artboard-Container zeichnen"),
    ("Add rectangle", "사각형 추가", "長方形を追加", "添加矩形", "Ajouter un rectangle", "Rechteck hinzufügen"),
    ("Create on the active artboard", "활성 아트보드에 생성", "現在のアートボードに作成", "在当前画板中创建", "Créer sur l’artboard actif", "Auf aktivem Artboard erstellen"),
    ("Add ellipse", "타원 추가", "楕円を追加", "添加椭圆", "Ajouter une ellipse", "Ellipse hinzufügen"),
    ("Add text", "텍스트 추가", "テキストを追加", "添加文本", "Ajouter du texte", "Text hinzufügen"),
    ("Create editable text", "편집 가능한 텍스트 생성", "編集可能なテキストを作成", "创建可编辑文本", "Créer un texte modifiable", "Bearbeitbaren Text erstellen"),
    ("Add image", "이미지 추가", "画像を追加", "添加图像", "Ajouter une image", "Bild hinzufügen"),
    ("Create an image placeholder", "이미지 자리표시자 생성", "画像プレースホルダーを作成", "创建图像占位符", "Créer un emplacement d’image", "Bildplatzhalter erstellen"),
    ("Place image...", "이미지 배치...", "画像を配置...", "放置图像...", "Placer une image...", "Bild platzieren..."),
    ("Choose an image for the active artboard", "활성 아트보드에 배치할 이미지를 선택", "現在のアートボードに配置する画像を選択", "选择要放置在当前画板上的图像", "Choisir une image pour l’artboard actif", "Bild für das aktive Artboard auswählen"),
    ("Set image fill...", "이미지 채우기 설정...", "画像塗りを設定...", "设置图像填充...", "Définir le remplissage d’image...", "Bildfüllung festlegen..."),
    ("Choose or replace the selected shape image", "선택한 도형의 이미지를 선택하거나 교체", "選択した図形の画像を選択または置換", "选择或替换所选形状的图像", "Choisir ou remplacer l’image de la forme sélectionnée", "Bild der ausgewählten Form auswählen oder ersetzen"),
    ("Auto-hide inspector", "인스펙터 자동 숨김", "インスペクターを自動的に隠す", "自动隐藏检查器", "Masquer automatiquement l’inspecteur", "Inspektor automatisch ausblenden"),
    ("Show properties only when the selection needs them", "선택에 필요할 때만 속성 표시", "選択時に必要なプロパティだけを表示", "仅在选择需要时显示属性", "Afficher les propriétés uniquement si nécessaire", "Eigenschaften nur bei Bedarf anzeigen"),
    ("Pin inspector", "인스펙터 고정", "インスペクターを固定", "固定检查器", "Épingler l’inspecteur", "Inspektor anheften"),
    ("Keep the contextual properties beside the canvas", "문맥 속성을 캔버스 옆에 유지", "コンテキストプロパティをキャンバス横に固定", "将上下文属性保留在画布旁", "Conserver les propriétés contextuelles près du canevas", "Kontexteigenschaften neben der Arbeitsfläche halten"),
    ("Open inspector as window", "인스펙터를 창으로 열기", "インスペクターをウィンドウで開く", "将检查器作为窗口打开", "Ouvrir l’inspecteur dans une fenêtre", "Inspektor als Fenster öffnen"),
    ("Move the contextual properties into a separate window", "문맥 속성을 별도 창으로 이동", "コンテキストプロパティを別ウィンドウに移動", "将上下文属性移动到单独窗口", "Déplacer les propriétés contextuelles dans une fenêtre séparée", "Kontexteigenschaften in ein separates Fenster verschieben"),
    ("Image Fit", "이미지 맞춤", "画像の合わせ方", "图像适配", "Ajustement de l’image", "Bildanpassung"),
    ("Focal Point", "초점 위치", "焦点位置", "焦点位置", "Point focal", "Fokuspunkt"),
    ("Original size", "원본 크기", "元のサイズ", "原始尺寸", "Taille d’origine", "Originalgröße"),
    ("Tile", "타일", "タイル", "平铺", "Mosaïque", "Kacheln"),
    ("Edit focal point", "초점 위치 편집", "焦点位置を編集", "编辑焦点", "Modifier le point focal", "Fokuspunkt bearbeiten"),
    ("Replace image", "이미지 교체", "画像を置換", "替换图像", "Remplacer l’image", "Bild ersetzen"),
    ("Place UI Image", "UI 이미지 배치", "UI画像を配置", "放置 UI 图像", "Placer une image UI", "UI-Bild platzieren"),
    ("Set UI Image Fill", "UI 이미지 채우기 설정", "UI画像塗りを設定", "设置 UI 图像填充", "Définir le remplissage d’image UI", "UI-Bildfüllung festlegen"),
    ("Could not place image", "이미지를 배치하지 못했습니다", "画像を配置できませんでした", "无法放置图像", "Impossible de placer l’image", "Bild konnte nicht platziert werden"),
    ("Could not set image fill", "이미지 채우기를 설정하지 못했습니다", "画像塗りを設定できませんでした", "无法设置图像填充", "Impossible de définir le remplissage d’image", "Bildfüllung konnte nicht festgelegt werden"),
    ("Fit all artboards", "모든 아트보드 맞춤", "全アートボードを表示", "适合所有画板", "Ajuster tous les artboards", "Alle Artboards einpassen"),
    ("Frame the whole UI document", "전체 UI 문서 보기", "UIドキュメント全体を表示", "查看整个 UI 文档", "Afficher tout le document UI", "Gesamtes UI-Dokument anzeigen"),
    ("Fit active artboard", "활성 아트보드 맞춤", "現在のアートボードを表示", "适合当前画板", "Ajuster l’artboard actif", "Aktives Artboard einpassen"),
    ("Frame the current page", "현재 페이지 보기", "現在のページを表示", "查看当前页面", "Afficher la page actuelle", "Aktuelle Seite anzeigen"),
    ("Fit selection", "선택 영역 맞춤", "選択範囲を表示", "适合所选内容", "Ajuster la sélection", "Auswahl einpassen"),
    ("Frame selected objects", "선택 객체 보기", "選択オブジェクトを表示", "查看所选对象", "Afficher les objets sélectionnés", "Ausgewählte Objekte anzeigen"),
    ("Scale bounds and visual metrics", "경계와 시각 속성을 함께 조절", "境界と視覚属性を同時に拡大縮小", "同时缩放边界和视觉属性", "Mettre à l’échelle limites et attributs", "Grenzen und visuelle Werte skalieren"),
    ("Duplicate selection", "선택 항목 복제", "選択項目を複製", "复制所选内容", "Dupliquer la sélection", "Auswahl duplizieren"),
    ("Duplicate the primary object", "대표 객체 복제", "主オブジェクトを複製", "复制主对象", "Dupliquer l’objet principal", "Primäres Objekt duplizieren"),
    ("Delete selection", "선택 항목 삭제", "選択項目を削除", "删除所选内容", "Supprimer la sélection", "Auswahl löschen"),
    ("Remove the selected object hierarchy", "선택 객체 계층 제거", "選択オブジェクト階層を削除", "移除所选对象层级", "Supprimer la hiérarchie sélectionnée", "Ausgewählte Hierarchie entfernen"),
    ("Group selection", "선택 항목 그룹화", "選択項目をグループ化", "组合所选内容", "Grouper la sélection", "Auswahl gruppieren"),
    ("Create one editable group", "편집 가능한 그룹 생성", "編集可能なグループを作成", "创建可编辑组", "Créer un groupe modifiable", "Bearbeitbare Gruppe erstellen"),
    ("Ungroup selection", "선택 그룹 해제", "選択グループを解除", "取消组合", "Dissocier la sélection", "Gruppierung aufheben"),
    ("Release the selected group", "선택 그룹의 객체 분리", "選択グループを解除", "释放所选组", "Libérer le groupe sélectionné", "Ausgewählte Gruppe auflösen"),
    ("Animate in Motion Designer", "Motion Designer에서 애니메이션", "Motion Designerでアニメーション", "在 Motion Designer 中制作动画", "Animer dans Motion Designer", "In Motion Designer animieren"),
    ("Open the selected stable-ID object", "선택 객체를 stable ID로 열기", "選択オブジェクトをstable IDで開く", "通过稳定 ID 打开所选对象", "Ouvrir l’objet via son ID stable", "Ausgewähltes Objekt per stabiler ID öffnen"),
    ("Layer", "레이어", "レイヤー", "图层", "Calque", "Ebene"),
    ("Page", "페이지", "ページ", "页面", "Page", "Seite"),
    ("Component", "컴포넌트", "コンポーネント", "组件", "Composant", "Komponente"),
    ("Variable", "변수", "変数", "变量", "Variable", "Variable"),
    ("Insert instance", "인스턴스 삽입", "インスタンスを挿入", "插入实例", "Insérer une instance", "Instanz einfügen"),
    ("Polygon", "다각형", "多角形", "多边形", "Polygone", "Polygon"),
    ("Star", "별", "星形", "星形", "Etoile", "Stern"),
    ("Arc", "호", "円弧", "圆弧", "Arc", "Bogen"),
    ("Points", "꼭짓점", "頂点", "顶点", "Points", "Punkte"),
    ("Inner", "내부 반경", "内側半径", "内半径", "Rayon interieur", "Innenradius"),
    ("Rotation", "회전", "回転", "旋转", "Rotation", "Drehung"),
    ("Shape", "도형", "シェイプ", "形状", "Forme", "Form"),
    ("Sweep", "호 길이", "円弧角", "弧角", "Balayage", "Bogenwinkel"),
    ("Keyboard shortcuts", "키보드 단축키", "キーボードショートカット", "键盘快捷键", "Raccourcis clavier", "Tastenkürzel"),
    ("Keyboard Shortcuts...", "키보드 단축키...", "キーボードショートカット...", "键盘快捷键...", "Raccourcis clavier...", "Tastenkürzel..."),
    ("Search commands or keys", "명령 또는 키 검색", "コマンドまたはキーを検索", "搜索命令或按键", "Rechercher une commande ou une touche", "Befehl oder Taste suchen"),
    ("Conflicts only", "충돌만 보기", "競合のみ", "仅显示冲突", "Conflits uniquement", "Nur Konflikte"),
    ("Command", "명령", "コマンド", "命令", "Commande", "Befehl"),
    ("Shortcut", "단축키", "ショートカット", "快捷键", "Raccourci", "Tastenkürzel"),
    ("Mode", "모드", "モード", "模式", "Mode", "Modus"),
    ("UI Design", "UI 디자인", "UIデザイン", "UI 设计", "Design UI", "UI-Design"),
    ("3D Place", "3D 배치", "3D配置", "3D 放置", "Placement 3D", "3D-Platzierung"),
    ("Global", "공통", "共通", "全局", "Global", "Global"),
    ("No shortcuts match this search.", "검색과 일치하는 단축키가 없습니다.", "検索に一致するショートカットはありません。", "没有与搜索匹配的快捷键。", "Aucun raccourci ne correspond.", "Keine passenden Tastenkürzel."),
    ("{visible} commands · {active} active · {conflicts} conflicts", "{visible}개 명령 · {active}개 활성 · {conflicts}개 충돌", "{visible}件のコマンド · {active}件有効 · {conflicts}件競合", "{visible} 个命令 · {active} 个启用 · {conflicts} 个冲突", "{visible} commandes · {active} actives · {conflicts} conflits", "{visible} Befehle · {active} aktiv · {conflicts} Konflikte"),
    ("Conflicts with: {items}", "충돌 대상: {items}", "競合: {items}", "冲突对象：{items}", "Conflit avec : {items}", "Konflikt mit: {items}"),
    ("Scale tool", "크기 조절 도구", "スケールツール", "缩放工具", "Outil de mise à l'échelle", "Skalierungswerkzeug"),
    ("Nudge selection", "선택 항목 미세 이동", "選択項目を微移動", "微移所选项", "Déplacer légèrement la sélection", "Auswahl fein verschieben"),
    ("Nudge selection 10 px", "선택 항목 10px 이동", "選択項目を10px移動", "移动所选项 10 px", "Déplacer la sélection de 10 px", "Auswahl um 10 px verschieben"),
    ("Pan canvas", "캔버스 이동", "キャンバスをパン", "平移画布", "Déplacer le canevas", "Leinwand verschieben"),
    ("Show measurements", "측정값 표시", "計測値を表示", "显示测量值", "Afficher les mesures", "Maße anzeigen"),
    ("Exit edit scope", "편집 범위 나가기", "編集範囲を終了", "退出编辑范围", "Quitter la portée d'édition", "Bearbeitungsbereich verlassen"),
    ("Save", "저장", "保存", "保存", "Enregistrer", "Speichern"),
    ("Save As", "다른 이름으로 저장", "名前を付けて保存", "另存为", "Enregistrer sous", "Speichern unter"),
    ("Move tool", "이동 도구", "移動ツール", "移动工具", "Outil Déplacement", "Verschieben-Werkzeug"),
    ("Brush tool", "브러시 도구", "ブラシツール", "画笔工具", "Outil Pinceau", "Pinsel-Werkzeug"),
    ("Eraser tool", "지우개 도구", "消しゴムツール", "橡皮擦工具", "Outil Gomme", "Radiergummi-Werkzeug"),
    ("Fill tool", "채우기 도구", "塗りつぶしツール", "填充工具", "Outil Remplissage", "Füllwerkzeug"),
    ("Path tool", "패스 도구", "パスツール", "路径工具", "Outil Tracé", "Pfadwerkzeug"),
    ("Zoom tool", "확대/축소 도구", "ズームツール", "缩放工具", "Outil Zoom", "Zoom-Werkzeug"),
    ("Copy layer", "레이어 복사", "レイヤーをコピー", "复制图层", "Copier le calque", "Ebene kopieren"),
    ("Cut layer", "레이어 잘라내기", "レイヤーをカット", "剪切图层", "Couper le calque", "Ebene ausschneiden"),
    ("Paste layer", "레이어 붙여넣기", "レイヤーをペースト", "粘贴图层", "Coller le calque", "Ebene einfügen"),
    ("Delete layer", "레이어 삭제", "レイヤーを削除", "删除图层", "Supprimer le calque", "Ebene löschen"),
    ("Move 3D camera", "3D 카메라 이동", "3Dカメラを移動", "移动 3D 相机", "Déplacer la caméra 3D", "3D-Kamera bewegen"),
    ("UI / Action parity", "UI / Action 일치성", "UI / Action整合性", "UI / Action 一致性", "Parité UI / Action", "UI-/Action-Parität"),
    ("UI / Action Parity...", "UI / Action 일치성...", "UI / Action整合性...", "UI / Action 一致性...", "Parité UI / Action...", "UI-/Action-Parität..."),
    ("No parity report available.", "일치성 보고서가 없습니다.", "整合性レポートはありません。", "没有一致性报告。", "Aucun rapport de parité.", "Kein Paritätsbericht verfügbar."),
    ("Feature", "기능", "機能", "功能", "Fonction", "Funktion"),
    ("UI surface", "UI 위치", "UIサーフェス", "UI 界面", "Surface UI", "UI-Oberfläche"),
    ("Actions", "Action 수", "Action数", "Action 数量", "Actions", "Actions"),
    ("Status", "상태", "状態", "状态", "État", "Status"),
    ("Covered", "연결됨", "対応済み", "已覆盖", "Couvert", "Abgedeckt"),
    ("Missing", "누락", "不足", "缺失", "Manquant", "Fehlt"),
    ("{actions} Actions · {covered}/{families} surfaces covered · {orphans} orphan candidates", "{actions}개 Action · {covered}/{families}개 UI 연결 · orphan 후보 {orphans}개", "{actions} Actions · {covered}/{families} UI対応 · orphan候補 {orphans}", "{actions} 个 Action · {covered}/{families} 个界面已覆盖 · {orphans} 个孤立候选", "{actions} Actions · {covered}/{families} surfaces couvertes · {orphans} orphelines", "{actions} Actions · {covered}/{families} Oberflächen abgedeckt · {orphans} verwaiste Kandidaten"),
    ("Productivity", "생산성 도구", "生産性", "效率工具", "Productivité", "Produktivität"),
    ("Workspace and view", "작업공간과 보기", "ワークスペースと表示", "工作区与视图", "Espace de travail et vue", "Arbeitsbereich und Ansicht"),
    ("Templates and assets", "템플릿과 에셋", "テンプレートとアセット", "模板与资源", "Modèles et ressources", "Vorlagen und Assets"),
    ("Pages, artboards, rulers and guides", "페이지·아트보드·자·가이드", "ページ・アートボード・定規・ガイド", "页面、画板、标尺与参考线", "Pages, plans, règles et guides", "Seiten, Artboards, Lineale und Hilfslinien"),
    ("Objects and selection", "객체와 선택", "オブジェクトと選択", "对象与选择", "Objets et sélection", "Objekte und Auswahl"),
    ("Vector editing", "벡터 편집", "ベクター編集", "矢量编辑", "Édition vectorielle", "Vektorbearbeitung"),
    ("Appearance and effects", "모양과 효과", "外観とエフェクト", "外观与效果", "Apparence et effets", "Aussehen und Effekte"),
    ("Typography", "타이포그래피", "タイポグラフィ", "排版", "Typographie", "Typografie"),
    ("Layout and responsive design", "레이아웃과 반응형", "レイアウトとレスポンシブ", "布局与响应式设计", "Mise en page adaptative", "Layout und Responsive Design"),
    ("Components, variables and styles", "컴포넌트·변수·스타일", "コンポーネント・変数・スタイル", "组件、变量与样式", "Composants, variables et styles", "Komponenten, Variablen und Stile"),
    ("Motion", "모션", "モーション", "动效", "Motion", "Motion"),
    ("Delivery and Unreal UMG", "전달과 Unreal UMG", "配信とUnreal UMG", "交付与 Unreal UMG", "Livraison et Unreal UMG", "Ausgabe und Unreal UMG"),
    ("Developer handoff and review", "개발 전달과 리뷰", "開発者ハンドオフとレビュー", "开发交付与审查", "Livraison dev et révision", "Entwicklerübergabe und Review"),
    ("Figma exchange and AI", "Figma 교환과 AI", "Figma交換とAI", "Figma 交换与 AI", "Échange Figma et IA", "Figma-Austausch und KI"),
    ("UI menu / Quick Actions", "UI 메뉴 / 빠른 작업", "UIメニュー / クイックアクション", "UI 菜单 / 快速操作", "Menu UI / Actions rapides", "UI-Menü / Schnellaktionen"),
    ("Canvas shell / panel controls / zoom menu", "캔버스 셸 / 패널 / 확대 메뉴", "キャンバス / パネル / ズーム", "画布 / 面板 / 缩放菜单", "Canevas / panneaux / zoom", "Canvas / Panels / Zoom"),
    ("Resources / Assets", "리소스 / 에셋", "リソース / アセット", "资源 / 资产", "Ressources / Assets", "Ressourcen / Assets"),
    ("Navigator / View options / Artboard inspector", "탐색기 / 보기 옵션 / 아트보드 속성", "ナビゲータ / 表示 / アートボード", "导航 / 视图 / 画板属性", "Navigation / Affichage / Artboard", "Navigator / Ansicht / Artboard"),
    ("Canvas / Layers / contextual Design", "캔버스 / 레이어 / 선택 속성", "キャンバス / レイヤー / コンテキスト", "画布 / 图层 / 上下文设计", "Canevas / Calques / Design contextuel", "Canvas / Ebenen / Kontextdesign"),
    ("Canvas vector mode / contextual toolbar", "캔버스 벡터 모드 / 선택 도구막대", "ベクターモード / コンテキストツールバー", "矢量模式 / 上下文工具栏", "Mode vectoriel / Barre contextuelle", "Vektormodus / Kontextleiste"),
    ("Design > Appearance", "디자인 > 모양", "デザイン > 外観", "设计 > 外观", "Design > Apparence", "Design > Aussehen"),
    ("Design > Typography / inline text editor", "디자인 > 글자 / 인라인 편집", "デザイン > 文字 / インライン編集", "设计 > 排版 / 行内编辑", "Design > Typographie / Édition directe", "Design > Typografie / Inline-Editor"),
    ("Design > Layout / responsive preview", "디자인 > 레이아웃 / 반응형 미리보기", "デザイン > レイアウト / レスポンシブ", "设计 > 布局 / 响应式预览", "Design > Mise en page / Aperçu", "Design > Layout / Vorschau"),
    ("Assets / Design component and token sections", "에셋 / 컴포넌트·토큰 속성", "アセット / コンポーネント・トークン", "资产 / 组件与令牌", "Assets / Composants et jetons", "Assets / Komponenten und Token"),
    ("Prototype tab / canvas connections", "프로토타입 탭 / 캔버스 연결", "プロトタイプ / キャンバス接続", "原型 / 画布连线", "Prototype / Connexions", "Prototyp / Verbindungen"),
    ("Prototype > Motion / Motion dialogs", "프로토타입 > 모션 / 모션 창", "プロトタイプ > モーション", "原型 > 动效", "Prototype > Motion", "Prototyp > Motion"),
    ("Inspect > Delivery / Export", "검사 > 전달 / 내보내기", "検査 > 配信 / 書き出し", "检查 > 交付 / 导出", "Inspecter > Livraison / Export", "Prüfen > Ausgabe / Export"),
    ("Inspect / Review Prototype", "검사 / 프로토타입 리뷰", "検査 / プロトタイプレビュー", "检查 / 原型审查", "Inspecter / Réviser le prototype", "Prüfen / Prototyp-Review"),
    ("File exchange / AI Design", "파일 교환 / AI 디자인", "ファイル交換 / AIデザイン", "文件交换 / AI 设计", "Échange de fichiers / Design IA", "Dateiaustausch / KI-Design"),
    ("Locale and font audit", "언어와 폰트 검사", "言語とフォントの検査", "语言与字体检查", "Audit langue et police", "Sprach- und Schriftprüfung"),
    ("Locale and Font Audit...", "언어와 폰트 검사...", "言語とフォントの検査...", "语言与字体检查...", "Audit langue et police...", "Sprach- und Schriftprüfung..."),
    ("No locale report available.", "언어 검사 보고서가 없습니다.", "言語検査レポートはありません。", "没有语言检查报告。", "Aucun rapport de langue.", "Kein Sprachbericht verfügbar."),
    ("Language", "언어", "言語", "语言", "Langue", "Sprache"),
    ("Overflow", "넘침", "はみ出し", "溢出", "Débordement", "Überlauf"),
    ("Elided", "줄임", "省略", "省略", "Abrégé", "Gekürzt"),
    ("Glyphs", "글리프", "グリフ", "字形", "Glyphes", "Glyphen"),
    ("{languages} languages · {entries} critical strings · {issues} issues · {font}", "{languages}개 언어 · 핵심 문구 {entries}개 · 문제 {issues}개 · {font}", "{languages}言語 · 重要文言{entries}件 · 問題{issues}件 · {font}", "{languages} 种语言 · {entries} 个关键文本 · {issues} 个问题 · {font}", "{languages} langues · {entries} textes · {issues} problèmes · {font}", "{languages} Sprachen · {entries} Texte · {issues} Probleme · {font}"),
    ("Save Recovery Snapshot Now", "복구 스냅샷 지금 저장", "復旧スナップショットを今すぐ保存", "立即保存恢复快照", "Enregistrer un instantané de récupération", "Wiederherstellung jetzt speichern"),
    ("Recover Autosave...", "자동 저장 복구...", "自動保存を復旧...", "恢复自动保存...", "Récupérer une sauvegarde automatique...", "Automatische Sicherung wiederherstellen..."),
    ("Recover autosave", "자동 저장 복구", "自動保存を復旧", "恢复自动保存", "Récupérer une sauvegarde automatique", "Automatische Sicherung wiederherstellen"),
    ("Discard snapshot", "스냅샷 폐기", "スナップショットを破棄", "丢弃快照", "Supprimer l'instantané", "Snapshot verwerfen"),
    ("Restore", "복원", "復元", "恢复", "Restaurer", "Wiederherstellen"),
    ("Untitled Painter document", "제목 없는 Painter 문서", "名称未設定のPainter文書", "未命名 Painter 文档", "Document Painter sans titre", "Unbenanntes Painter-Dokument"),
    ("Recovered", "복구됨", "復旧済み", "已恢复", "Récupéré", "Wiederhergestellt"),
    ("{count} recovery snapshots", "복구 스냅샷 {count}개", "復旧スナップショット {count} 件", "{count} 个恢复快照", "{count} instantanés de récupération", "{count} Wiederherstellungs-Snapshots"),
    ("No recovery snapshots are available.", "사용 가능한 복구 스냅샷이 없습니다.", "利用可能な復旧スナップショットはありません。", "没有可用的恢复快照。", "Aucun instantané de récupération disponible.", "Keine Wiederherstellungs-Snapshots verfügbar."),
    ("Keyboard Focus Audit...", "키보드 포커스 검사...", "キーボードフォーカス監査...", "键盘焦点检查...", "Audit du focus clavier...", "Tastaturfokus prüfen..."),
    ("UI Release Corpus...", "UI 릴리스 코퍼스...", "UIリリースコーパス...", "UI 发布语料库...", "Corpus de livraison UI...", "UI-Release-Korpus..."),
    ("UI release corpus", "UI 릴리스 코퍼스", "UIリリースコーパス", "UI 发布语料库", "Corpus de livraison UI", "UI-Release-Korpus"),
    ("Run the release corpus to verify exchange packages.", "교환 패키지를 검증하려면 릴리스 코퍼스를 실행하세요.", "交換パッケージを検証するにはリリースコーパスを実行します。", "运行发布语料库以验证交换包。", "Exécutez le corpus pour vérifier les paquets d'échange.", "Release-Korpus zur Prüfung der Austauschpakete ausführen."),
    ("Package", "패키지", "パッケージ", "包", "Paquet", "Paket"),
    ("Time", "시간", "時間", "时间", "Durée", "Zeit"),
    ("Scope", "범위", "範囲", "范围", "Portée", "Umfang"),
    ("Passed", "통과", "合格", "通过", "Réussi", "Bestanden"),
    ("Open output folder", "출력 폴더 열기", "出力フォルダーを開く", "打开输出文件夹", "Ouvrir le dossier de sortie", "Ausgabeordner öffnen"),
    ("Run corpus", "코퍼스 실행", "コーパスを実行", "运行语料库", "Exécuter le corpus", "Korpus ausführen"),
    ("Running release corpus...", "릴리스 코퍼스 실행 중...", "リリースコーパスを実行中...", "正在运行发布语料库...", "Exécution du corpus...", "Release-Korpus wird ausgeführt..."),
    ("{passed}/{total} release packages passed · {blocked} blocked", "릴리스 패키지 {passed}/{total}개 통과 · {blocked}개 차단", "リリースパッケージ {passed}/{total} 合格 · {blocked} ブロック", "发布包 {passed}/{total} 通过 · {blocked} 已阻止", "{passed}/{total} paquets réussis · {blocked} bloqués", "{passed}/{total} Release-Pakete bestanden · {blocked} blockiert"),
    ("Figma native file is not claimed. Unreal compile and real capture remain separate release gates.", "Figma 네이티브 파일 지원을 주장하지 않습니다. Unreal 컴파일과 실제 캡처는 별도 릴리스 관문입니다.", "Figmaネイティブファイル対応は主張しません。Unrealコンパイルと実キャプチャは別のリリースゲートです。", "不声明支持 Figma 原生文件。Unreal 编译和真实捕获仍是独立发布门槛。", "Le fichier Figma natif n'est pas revendiqué. La compilation Unreal et la capture réelle restent des contrôles séparés.", "Native Figma-Dateien werden nicht beansprucht. Unreal-Kompilierung und echte Aufnahme bleiben separate Freigaben."),
    ("Native .tspaint", "네이티브 .tspaint", "ネイティブ .tspaint", "原生 .tspaint", ".tspaint natif", "Natives .tspaint"),
    ("Figma plugin exchange", "Figma 플러그인 교환", "Figmaプラグイン交換", "Figma 插件交换", "Échange de plugin Figma", "Figma-Plugin-Austausch"),
    ("Template package", "템플릿 패키지", "テンプレートパッケージ", "模板包", "Paquet de modèle", "Vorlagenpaket"),
    ("Design handoff", "디자인 전달", "デザイン引き渡し", "设计交付", "Livraison du design", "Design-Übergabe"),
    ("Interactive prototype", "인터랙티브 프로토타입", "インタラクティブプロトタイプ", "交互式原型", "Prototype interactif", "Interaktiver Prototyp"),
    ("Offline review", "오프라인 리뷰", "オフラインレビュー", "离线审阅", "Révision hors ligne", "Offline-Review"),
    ("Tiger UMG contract", "Tiger UMG 계약", "Tiger UMG契約", "Tiger UMG 合约", "Contrat Tiger UMG", "Tiger-UMG-Vertrag"),
    ("semantic round trip", "의미 보존 왕복", "意味保持ラウンドトリップ", "语义往返", "aller-retour sémantique", "Semantischer Roundtrip"),
    ("editable_plugin_exchange_not_native_fig", "편집 가능 플러그인 교환 · 네이티브 .fig 아님", "編集可能なプラグイン交換・ネイティブ.figではありません", "可编辑插件交换 · 非原生 .fig", "échange de plugin éditable · pas un .fig natif", "Editierbarer Plugin-Austausch · keine native .fig"),
    ("provider_neutral_contract_only", "공급자 중립 계약만 검증", "プロバイダー中立契約のみ", "仅验证供应商中立合约", "contrat neutre uniquement", "Nur anbieterneutraler Vertrag"),
    ("Keyboard focus audit", "키보드 포커스 검사", "キーボードフォーカス監査", "键盘焦点检查", "Audit du focus clavier", "Tastaturfokus-Prüfung"),
    ("No keyboard focus report available.", "키보드 포커스 검사 결과가 없습니다.", "キーボードフォーカスの監査結果はありません。", "没有键盘焦点检查报告。", "Aucun rapport de focus clavier.", "Kein Tastaturfokus-Bericht verfügbar."),
    ("Control", "컨트롤", "コントロール", "控件", "Contrôle", "Steuerelement"),
    ("Type", "유형", "種類", "类型", "Type", "Typ"),
    ("Tab", "탭", "Tab", "Tab", "Tab", "Tab"),
    ("Focus ring", "포커스 링", "フォーカスリング", "焦点环", "Anneau de focus", "Fokusring"),
    ("Yes", "예", "はい", "是", "Oui", "Ja"),
    ("No", "아니요", "いいえ", "否", "Non", "Nein"),
    ("{controls} controls · {tab} keyboard · {rings} focus rings · {issues} issues", "컨트롤 {controls}개 · 키보드 {tab}개 · 포커스 링 {rings}개 · 문제 {issues}개", "コントロール {controls} · キーボード {tab} · フォーカスリング {rings} · 問題 {issues}", "{controls} 个控件 · {tab} 个键盘可达 · {rings} 个焦点环 · {issues} 个问题", "{controls} contrôles · {tab} clavier · {rings} anneaux · {issues} problèmes", "{controls} Steuerelemente · {tab} Tastatur · {rings} Fokusringe · {issues} Probleme"),
    ("Canvas zoom", "캔버스 확대/축소", "キャンバスズーム", "画布缩放", "Zoom du canevas", "Canvas-Zoom"),
)

_TABLE = {
    lang: {row[0]: row[index] for row in _ROWS}
    for index, lang in enumerate(_LANGUAGES)
}
_REVERSE = {
    translated: row[0]
    for row in _ROWS
    for translated in row
    if translated
}
_LOCALE_REVERSE: dict[str, str] | None = None


def _locale_source(text: str, language: str) -> str:
    global _LOCALE_REVERSE
    if _LOCALE_REVERSE is None:
        from app.locales import en

        _LOCALE_REVERSE = {
            str(value): str(key)
            for key, value in en.TRANSLATIONS.items()
            if isinstance(value, str)
        }
    key = _LOCALE_REVERSE.get(text)
    if not key:
        return ""
    module = import_module(f"app.locales.{language}")
    table = getattr(module, "TRANSLATIONS", {})
    if isinstance(table, dict):
        return str(table.get(key) or "")
    return ""


def painter_text(text: str, language: str | None = None) -> str:
    """Translate a Painter display string while preserving document data."""
    source = str(text or "")
    if not source:
        return source
    lang = str(language or current_language() or "en")
    if lang not in _LANGUAGES:
        lang = "en"
    english = _REVERSE.get(source, source)
    if "\n" in english:
        return "\n".join(painter_text(line, lang) for line in english.splitlines())
    translated = _TABLE.get(lang, {}).get(english)
    if translated:
        return translated
    locale_value = _locale_source(english, lang)
    if locale_value:
        return locale_value

    match = re.fullmatch(r"(\d+)\s+pinned", english)
    if match:
        count = match.group(1)
        templates = {
            "en": "{n} pinned", "ko": "{n}개 고정", "ja": "{n}件固定",
            "zh": "已固定 {n} 项", "fr": "{n} épinglé(s)", "de": "{n} angeheftet",
        }
        return templates[lang].format(n=count)
    match = re.fullmatch(r"(\d+)\s+objects selected", english)
    if match:
        count = match.group(1)
        templates = {
            "en": "{n} objects selected",
            "ko": "{n}개 객체 선택됨",
            "ja": "{n}個のオブジェクトを選択",
            "zh": "已选择 {n} 个对象",
            "fr": "{n} objets sélectionnés",
            "de": "{n} Objekte ausgewählt",
        }
        return templates[lang].format(n=count)
    if " · " in english:
        head, tail = english.split(" · ", 1)
        translated_head = painter_text(head, lang)
        if translated_head != head:
            return f"{translated_head} · {tail}"
    if english.startswith("Layer compatibility: "):
        value = english.partition(": ")[2]
        labels = {
            "en": "Layer compatibility", "ko": "레이어 호환성",
            "ja": "レイヤー互換性", "zh": "图层兼容性",
            "fr": "Compatibilité du calque", "de": "Ebenenkompatibilität",
        }
        return f"{labels[lang]}: {painter_text(value, lang)}"
    match = re.fullmatch(r"(Composition|Binding)\s{2}(.+)", english)
    if match:
        label, value = match.groups()
        return f"{painter_text(label, lang)}  {painter_text(value, lang)}"
    match = re.fullmatch(r"Revision\s+(\d+)\s+linked\s+/\s+(\d+)\s+current", english)
    if match:
        linked, current = match.groups()
        templates = {
            "en": "Revision  {a} linked / {b} current",
            "ko": "리비전  연결 {a} / 현재 {b}",
            "ja": "リビジョン  リンク {a} / 現在 {b}",
            "zh": "修订版  已链接 {a} / 当前 {b}",
            "fr": "Révision  liée {a} / actuelle {b}",
            "de": "Revision  verknüpft {a} / aktuell {b}",
        }
        return templates[lang].format(a=linked, b=current)
    return source


def _objects(root: QObject) -> Iterable[QObject]:
    yield root
    yield from root.findChildren(QObject)


class PainterWidgetLocalizer(QObject):
    """Translate current and newly created Painter widgets in place."""

    _EVENTS = {
        QEvent.Type.Show,
        QEvent.Type.PolishRequest,
        QEvent.Type.LayoutRequest,
        QEvent.Type.WindowActivate,
        QEvent.Type.LanguageChange,
    }

    def __init__(self, root: QWidget) -> None:
        super().__init__(root)
        self._root = root
        self._language = ""
        self._refresh_pending = False
        self._install(root)
        self.refresh()

    def _install(self, root: QObject) -> None:
        for obj in _objects(root):
            obj.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ChildAdded:
            child = getattr(event, "child", lambda: None)()
            if isinstance(child, QObject):
                self._install(child)
                self._schedule_refresh()
        elif event.type() in self._EVENTS:
            self._schedule_refresh()
        return False

    def _schedule_refresh(self) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True
        QTimer.singleShot(0, self._run_scheduled_refresh)

    def _run_scheduled_refresh(self) -> None:
        self._refresh_pending = False
        self.refresh()

    def refresh(self) -> None:
        self._language = current_language()
        for obj in _objects(self._root):
            self._translate_object(obj)

    def _translated_property(
        self,
        obj: QObject,
        property_name: str,
        current: str,
    ) -> str:
        source_name = f"_painter_i18n_source_{property_name}"
        last_name = f"_painter_i18n_last_{property_name}"
        source = obj.property(source_name)
        last = obj.property(last_name)
        if source is None or (last is not None and current != last):
            source = _REVERSE.get(current, current)
            obj.setProperty(source_name, source)
        translated = painter_text(str(source), self._language)
        obj.setProperty(last_name, translated)
        return translated

    def _translate_object(self, obj: QObject) -> None:
        if isinstance(obj, QLabel):
            value = self._translated_property(obj, "text", obj.text())
            if obj.text() != value:
                obj.setText(value)
        elif isinstance(obj, QAbstractButton):
            value = self._translated_property(obj, "text", obj.text())
            if obj.text() != value:
                obj.setText(value)
        if isinstance(obj, QGroupBox):
            value = self._translated_property(obj, "title", obj.title())
            if obj.title() != value:
                obj.setTitle(value)
        if isinstance(obj, QLineEdit):
            value = self._translated_property(
                obj, "placeholder", obj.placeholderText()
            )
            if obj.placeholderText() != value:
                obj.setPlaceholderText(value)
        if isinstance(obj, QWidget):
            if obj.accessibleName():
                value = self._translated_property(
                    obj,
                    "accessible_name",
                    obj.accessibleName(),
                )
                if obj.accessibleName() != value:
                    obj.setAccessibleName(value)
            if obj.windowTitle():
                value = self._translated_property(
                    obj, "window_title", obj.windowTitle()
                )
                if obj.windowTitle() != value:
                    obj.setWindowTitle(value)
            if obj.toolTip():
                value = self._translated_property(obj, "tooltip", obj.toolTip())
                if obj.toolTip() != value:
                    obj.setToolTip(value)
        if isinstance(obj, QComboBox):
            for index in range(obj.count()):
                value = painter_text(obj.itemText(index), self._language)
                if value != obj.itemText(index):
                    obj.setItemText(index, value)
        if isinstance(obj, QTabWidget):
            for index in range(obj.count()):
                value = painter_text(obj.tabText(index), self._language)
                if value != obj.tabText(index):
                    obj.setTabText(index, value)
                tooltip = painter_text(obj.tabToolTip(index), self._language)
                if tooltip != obj.tabToolTip(index):
                    obj.setTabToolTip(index, tooltip)
        if isinstance(obj, QListWidget):
            for index in range(obj.count()):
                item = obj.item(index)
                value = painter_text(item.text(), self._language)
                if value != item.text():
                    item.setText(value)
        if isinstance(obj, QTreeWidget):
            stack = [obj.topLevelItem(i) for i in range(obj.topLevelItemCount())]
            while stack:
                item = stack.pop()
                for column in range(item.columnCount()):
                    value = painter_text(item.text(column), self._language)
                    if value != item.text(column):
                        item.setText(column, value)
                stack.extend(item.child(i) for i in range(item.childCount()))
        if isinstance(obj, QMenu):
            title = self._translated_property(obj, "title", obj.title())
            if obj.title() != title:
                obj.setTitle(title)
            for action in obj.actions():
                value = painter_text(action.text(), self._language)
                if value != action.text():
                    action.setText(value)


__all__ = ["PainterWidgetLocalizer", "painter_text"]
