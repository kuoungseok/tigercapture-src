"""Qt dialog for Character Asset Hub folder intake."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.character_asset_hub import (
    scan_character_asset_folder,
    summarize_character_asset_hub,
    write_character_asset_hub_thumbnails,
)
from app.icons import app_icon, icon_size


class CharacterAssetCard(QFrame):
    action_requested = Signal(str, object)

    def __init__(self, record: Mapping[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.record = dict(record)
        self.setObjectName("CharacterAssetCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(104)
        self.setStyleSheet(
            "QFrame#CharacterAssetCard{background:#111315;border:1px solid rgba(220,225,238,20);"
            "border-radius:8px;}"
            "QLabel{background:transparent;color:#D8DCE6;}"
            "QPushButton{background:#20252B;color:#F0F3F7;border:1px solid #3B4651;"
            "border-radius:7px;padding:5px 9px;font-size:10px;font-weight:600;}"
            "QPushButton:hover{background:#2B333D;border-color:#6B7786;}"
            "QPushButton:disabled{background:#15181C;color:#6F7782;border-color:#252B32;}"
        )
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        self._thumb = QLabel(self)
        self._thumb.setFixedSize(72, 72)
        self._thumb.setPixmap(_pixmap_for_record(self.record, 72))
        root.addWidget(self._thumb)

        body = QVBoxLayout()
        body.setSpacing(3)
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        badge = QLabel(str(self.record.get("kind") or "?").upper(), self)
        badge.setObjectName("KindBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(52, 20)
        badge.setStyleSheet(f"background:{_kind_color(self.record)};color:#fff;border-radius:5px;font-size:9px;font-weight:700;")
        title = QLabel(str(self.record.get("display_name") or "Character"), self)
        title.setObjectName("CardTitle")
        title.setStyleSheet("font-size:12px;font-weight:650;color:#F2F4F8;")
        title.setToolTip(str(self.record.get("path") or ""))
        title_row.addWidget(badge)
        title_row.addWidget(title, stretch=1)
        body.addLayout(title_row)

        render = self.record.get("render") if isinstance(self.record.get("render"), Mapping) else {}
        missing = list(self.record.get("missing_files") or [])
        features = self.record.get("features") if isinstance(self.record.get("features"), Mapping) else {}
        meta = QLabel(_feature_summary(str(self.record.get("kind") or ""), features), self)
        meta.setStyleSheet("font-size:10px;color:#B8C0CC;")
        body.addWidget(meta)
        status = QLabel(_status_summary(render, missing), self)
        status.setStyleSheet("font-size:10px;color:#9EA8B5;")
        status.setWordWrap(True)
        body.addWidget(status)
        root.addLayout(body, stretch=1)

        action = self.record.get("timeline_add") if isinstance(self.record.get("timeline_add"), Mapping) else {}
        self._add_btn = QPushButton(str(action.get("label") or "Add"), self)
        self._add_btn.setIcon(app_icon("plus", size=12))
        self._add_btn.setIconSize(icon_size(12))
        self._add_btn.setEnabled(bool(action.get("enabled") and action.get("action")))
        self._add_btn.setToolTip(str(action.get("reason") or ""))
        self._add_btn.clicked.connect(self._emit_action)
        root.addWidget(self._add_btn)

        self._template_btn = QPushButton("Template", self)
        self._template_btn.setIcon(app_icon("workflow", size=12))
        self._template_btn.setIconSize(icon_size(12))
        self._template_btn.setMenu(self._build_template_menu())
        self._template_btn.setEnabled(bool(action.get("enabled") and action.get("action")))
        self._template_btn.setToolTip("Create a one-click timeline from this character")
        root.addWidget(self._template_btn)

    def _emit_action(self) -> None:
        action = self.record.get("timeline_add") if isinstance(self.record.get("timeline_add"), Mapping) else {}
        action_id = str(action.get("action") or "")
        params = dict(action.get("params") or {})
        if action_id:
            self.action_requested.emit(action_id, params)

    def _build_template_menu(self) -> QMenu:
        menu = QMenu(self)
        try:
            from app.character_one_click_templates import character_one_click_templates

            templates = character_one_click_templates()
        except Exception:
            templates = []
        for template in templates:
            template_id = str(template.get("id") or "")
            label = str(template.get("name") or template_id)
            if not template_id:
                continue
            action = menu.addAction(label)
            action.setToolTip(str(template.get("description") or ""))
            action.triggered.connect(
                lambda checked=False, tid=template_id: self._emit_template_action(tid)
            )
        if not templates:
            empty = menu.addAction("No templates available")
            empty.setEnabled(False)
        return menu

    def _emit_template_action(self, template_id: str) -> None:
        if not template_id:
            return
        self.action_requested.emit(
            "character.template.apply",
            {
                "template_id": str(template_id),
                "asset_record": dict(self.record),
                "start_ms": 0,
                "include_decorations": True,
            },
        )


class CharacterAssetHubDialog(QDialog):
    action_requested = Signal(str, object)

    def __init__(self, root_path: str | Path = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CharacterAssetHubDialog")
        self.setWindowTitle("Character Asset Hub")
        self.resize(820, 620)
        self._payload: dict[str, Any] = {}
        self._cards: list[CharacterAssetCard] = []
        self.setStyleSheet(
            "QDialog#CharacterAssetHubDialog{background:#0B0D10;color:#E6EAF2;}"
            "QLineEdit{background:#12161B;color:#E6EAF2;border:1px solid #303842;"
            "border-radius:7px;padding:6px 8px;}"
            "QLabel#HubTitle{font-size:16px;font-weight:700;color:#F4F6FA;}"
            "QLabel#HubStatus{color:#AAB3C0;font-size:10px;}"
            "QPushButton{background:#20252B;color:#F0F3F7;border:1px solid #3B4651;"
            "border-radius:7px;padding:6px 10px;font-size:10px;font-weight:600;}"
            "QPushButton:hover{background:#2B333D;border-color:#6B7786;}"
            "QScrollArea{border:none;background:transparent;}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("Character Asset Hub", self)
        title.setObjectName("HubTitle")
        root.addWidget(title)

        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        self._path_edit = QLineEdit(self)
        self._path_edit.setPlaceholderText("Character folder")
        self._path_edit.setText(str(root_path or ""))
        browse_btn = QPushButton("", self)
        browse_btn.setToolTip("Choose character folder")
        browse_btn.setIcon(app_icon("folder", size=14))
        browse_btn.setIconSize(icon_size(14))
        browse_btn.clicked.connect(self._browse)
        scan_btn = QPushButton("Scan", self)
        scan_btn.setIcon(app_icon("search", size=13))
        scan_btn.setIconSize(icon_size(13))
        scan_btn.clicked.connect(self.scan_current_folder)
        path_row.addWidget(self._path_edit, stretch=1)
        path_row.addWidget(browse_btn)
        path_row.addWidget(scan_btn)
        root.addLayout(path_row)

        self._status = QLabel("Drop or choose a folder with Live2D, Spine, MMD, or VRM assets.", self)
        self._status.setObjectName("HubStatus")
        root.addWidget(self._status)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._content = QWidget(self._scroll)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)
        self._content_layout.addStretch(1)
        self._scroll.setWidget(self._content)
        root.addWidget(self._scroll, stretch=1)

        if str(root_path or "").strip():
            self.scan_current_folder()

    def payload(self) -> dict[str, Any]:
        return dict(self._payload)

    def cards(self) -> list[CharacterAssetCard]:
        return list(self._cards)

    def set_root_path(self, path: str | Path) -> None:
        self._path_edit.setText(str(path or ""))

    def scan_current_folder(self) -> dict[str, Any]:
        root = Path(str(self._path_edit.text() or "")).expanduser()
        payload = scan_character_asset_folder(root)
        try:
            payload = write_character_asset_hub_thumbnails(
                payload,
                Path("debugCapture") / "character_asset_hub_ui_thumbnails",
                size=128,
            )
        except Exception:
            pass
        self._payload = payload
        self._status.setText(summarize_character_asset_hub(payload))
        self._populate(payload)
        return payload

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Character Asset Hub", self._path_edit.text())
        if not folder:
            return
        self._path_edit.setText(folder)
        self.scan_current_folder()

    def _populate(self, payload: Mapping[str, Any]) -> None:
        while self._content_layout.count() > 0:
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards = []
        assets = [row for row in list(payload.get("assets") or []) if isinstance(row, Mapping)]
        if not assets:
            empty = QLabel("No character assets found.", self._content)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(180)
            empty.setStyleSheet("color:#8D97A4;border:1px dashed #303842;border-radius:8px;")
            self._content_layout.addWidget(empty)
        for row in assets:
            card = CharacterAssetCard(row, self._content)
            card.action_requested.connect(self.action_requested.emit)
            self._cards.append(card)
            self._content_layout.addWidget(card)
        self._content_layout.addStretch(1)


def _kind_color(record: Mapping[str, Any]) -> str:
    return {
        "live2d": "#8F7CFF",
        "spine": "#D98845",
        "mmd": "#E95A9D",
        "vrm": "#B06BFF",
    }.get(str(record.get("kind") or ""), "#607086")


def _pixmap_for_record(record: Mapping[str, Any], size: int) -> QPixmap:
    thumb = record.get("thumbnail") if isinstance(record.get("thumbnail"), Mapping) else {}
    path = Path(str(thumb.get("path") or ""))
    if path.is_file():
        pix = QPixmap(str(path))
        if not pix.isNull():
            return pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    pix = QPixmap(size, size)
    pix.fill(QColor("#171B20"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor(_kind_color(record)), 2))
    painter.drawRoundedRect(2, 2, size - 4, size - 4, 9, 9)
    font = QFont(painter.font())
    font.setPointSize(10)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#F4F6FA"))
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, str(record.get("kind") or "?").upper())
    painter.end()
    return pix


def _feature_summary(kind: str, features: Mapping[str, Any]) -> str:
    if kind == "live2d":
        return (
            f"motions {len(list(features.get('motions') or []))} | "
            f"expressions {len(list(features.get('expressions') or []))} | "
            f"textures {len(list(features.get('textures') or []))}"
        )
    if kind == "spine":
        return (
            f"animations {len(list(features.get('animations') or []))} | "
            f"skins {len(list(features.get('skins') or []))} | "
            f"atlas {'yes' if features.get('atlas_path') else 'missing'}"
        )
    if kind == "mmd":
        return (
            f"motions {len(list(features.get('motions') or []))} | "
            f"materials {int(features.get('materials', 0) or 0)} | "
            f"physics {'yes' if features.get('physics') else 'not probed'}"
        )
    if kind == "vrm":
        return (
            f"{features.get('profile') or 'VRM'} | bones {int(features.get('humanoid_bone_count', 0) or 0)} | "
            f"blendshapes {int(features.get('blend_shape_group_count', 0) or 0)}"
        )
    return "Character asset"


def _status_summary(render: Mapping[str, Any], missing: list[Any]) -> str:
    ready = "Ready" if bool(render.get("capable")) else "Needs attention"
    suffix = f" | missing {len(missing)}" if missing else ""
    reason = str(render.get("reason") or "")
    if reason:
        suffix += f" | {reason[:80]}"
    return f"{ready}: {render.get('status') or 'unknown'}{suffix}"


__all__ = ["CharacterAssetCard", "CharacterAssetHubDialog"]
