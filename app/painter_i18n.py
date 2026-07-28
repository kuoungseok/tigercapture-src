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
