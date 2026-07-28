"""Visual template gallery for complete Painter UI Design documents."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.painter_ui_template_store import (
    inspect_ui_template_store,
    instantiate_stored_ui_template,
    set_ui_template_favorite,
)
from app.painter_ui_themes import resolve_ui_theme_document


TEMPLATE_THUMBNAIL_SIZE = QSize(240, 150)


def _gallery_templates() -> list[dict[str, Any]]:
    store = inspect_ui_template_store()
    installed_latest: dict[str, dict[str, Any]] = {}
    for row in store["installed"]:
        key = str(row["id"])
        if key not in installed_latest or int(row["version"]) > int(
            installed_latest[key]["version"]
        ):
            installed_latest[key] = row
    rows = [dict(row) for row in store["built_in"]]
    rows.extend(installed_latest.values())
    favorite_ids = set(store["favorites"])
    recent_ids = set(store["recent"])
    for row in rows:
        row["favorite"] = row["id"] in favorite_ids
        row["recent"] = row["id"] in recent_ids
        row.setdefault("artboard_presets", [])
        row.setdefault("features", ["Complete editable document"])
        row.setdefault("difficulty", "Custom")
        row.setdefault("tags", [])
        row.setdefault("description", "")
    return rows


def ui_template_thumbnail(template_id: str) -> QPixmap:
    document, _report = instantiate_stored_ui_template(template_id)
    document = resolve_ui_theme_document(document)
    artboard = document["artboards"][0]
    width = TEMPLATE_THUMBNAIL_SIZE.width()
    height = TEMPLATE_THUMBNAIL_SIZE.height()
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#1A1D23"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    padding = 6.0
    scale = min(
        (width - padding * 2) / float(artboard["width"]),
        (height - padding * 2) / float(artboard["height"]),
    )
    board_width = float(artboard["width"]) * scale
    board_height = float(artboard["height"]) * scale
    offset_x = (width - board_width) * 0.5
    offset_y = (height - board_height) * 0.5
    painter.fillRect(
        int(offset_x),
        int(offset_y),
        max(1, int(board_width)),
        max(1, int(board_height)),
        QColor(str(artboard["background"])),
    )
    rows = sorted(
        (
            row
            for row in document["objects"]
            if row["artboard_id"] == artboard["id"] and row["visible"]
        ),
        key=lambda row: int(row["z_index"]),
    )
    for row in rows:
        x = offset_x + float(row["x"]) * scale
        y = offset_y + float(row["y"]) * scale
        row_width = max(1.0, float(row["width"]) * scale)
        row_height = max(1.0, float(row["height"]) * scale)
        style = row["style"]
        fill = QColor(str(style.get("fill") or "#FFFFFF"))
        fill.setAlphaF(max(0.0, min(1.0, float(row["opacity"]))))
        radius = max(0.0, float(style.get("radius") or 0.0) * scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(x, y, row_width, row_height, radius, radius)
        text = str(row["content"].get("text") or "")
        if text:
            painter.setPen(QColor(str(style.get("text_color") or "#111111")))
            font = QFont()
            font.setPixelSize(
                max(5, min(18, int(float(style.get("font_size") or 16) * scale)))
            )
            font.setBold("headline" in row["name"].casefold())
            painter.setFont(font)
            painter.drawText(
                int(x + 4),
                int(y + 2),
                max(1, int(row_width - 8)),
                max(1, int(row_height - 4)),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                text,
            )
    painter.end()
    return QPixmap.fromImage(image)


class PainterUITemplateGalleryDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Painter UI Template Gallery")
        self.resize(1120, 720)
        self.selected_template_id = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 14)
        title = QLabel("Start from a complete editable design")
        title.setObjectName("PaintSectionTitle")
        root.addWidget(title)

        filters = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search templates, categories, or tags")
        self.category_combo = QComboBox()
        self.category_combo.addItem("All categories", "")
        for category in sorted(
            {row["category"] for row in _gallery_templates()}
        ):
            self.category_combo.addItem(category, category)
        filters.addWidget(self.search_edit, 1)
        filters.addWidget(self.category_combo)
        root.addLayout(filters)

        content = QHBoxLayout()
        self.items = QListWidget()
        self.items.setViewMode(QListView.ViewMode.IconMode)
        self.items.setResizeMode(QListView.ResizeMode.Adjust)
        self.items.setMovement(QListView.Movement.Static)
        self.items.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.items.setIconSize(TEMPLATE_THUMBNAIL_SIZE)
        self.items.setGridSize(QSize(276, 218))
        self.items.setSpacing(8)
        self.items.itemDoubleClicked.connect(lambda _item: self.accept())
        content.addWidget(self.items, 1)

        details = QWidget()
        details.setMinimumWidth(280)
        details.setMaximumWidth(340)
        detail_layout = QVBoxLayout(details)
        self.detail_title = QLabel("Select a template")
        self.detail_title.setObjectName("PaintSectionTitle")
        self.detail_title.setWordWrap(True)
        self.detail_meta = QLabel("")
        self.detail_meta.setObjectName("PaintMuted")
        self.detail_description = QLabel("")
        self.detail_description.setWordWrap(True)
        self.detail_features = QLabel("")
        self.detail_features.setWordWrap(True)
        self.detail_license = QLabel("")
        self.detail_license.setWordWrap(True)
        self.favorite_button = QPushButton("Add to Favorites")
        self.favorite_button.clicked.connect(self._toggle_favorite)
        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_meta)
        detail_layout.addWidget(self.detail_description)
        detail_layout.addWidget(self.detail_features)
        detail_layout.addWidget(self.detail_license)
        detail_layout.addWidget(self.favorite_button)
        detail_layout.addStretch(1)
        content.addWidget(details)
        root.addLayout(content, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        use_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if use_button is not None:
            use_button.setText("Use Template")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.search_edit.textChanged.connect(self._populate)
        self.category_combo.currentIndexChanged.connect(self._populate)
        self.items.itemSelectionChanged.connect(self._selection_changed)
        self._populate()

    def _populate(self, *_args) -> None:
        selected = self.selected_template_id
        self.items.clear()
        query = self.search_edit.text().strip().casefold()
        category = str(self.category_combo.currentData() or "").casefold()
        rows = []
        for row in _gallery_templates():
            if category and str(row["category"]).casefold() != category:
                continue
            haystack = " ".join(
                [
                    str(row["name"]),
                    str(row["category"]),
                    str(row["description"]),
                    *[str(tag) for tag in row["tags"]],
                ]
            ).casefold()
            if query and query not in haystack:
                continue
            rows.append(row)
        for row in rows:
            item = QListWidgetItem(
                QIcon(ui_template_thumbnail(str(row["id"]))),
                (
                    f"{row['name']}\n"
                    f"{row['category']}  |  {len(row['artboard_presets'])} screens"
                ),
            )
            item.setData(Qt.ItemDataRole.UserRole, str(row["id"]))
            item.setData(Qt.ItemDataRole.UserRole + 1, row)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.items.addItem(item)
            if row["id"] == selected:
                self.items.setCurrentItem(item)
        if self.items.count() and self.items.currentRow() < 0:
            self.items.setCurrentRow(0)
        if not self.items.count():
            self._show_details({})

    def _selection_changed(self) -> None:
        item = self.items.currentItem()
        self.selected_template_id = (
            str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        )
        row = item.data(Qt.ItemDataRole.UserRole + 1) if item else {}
        self._show_details(row if isinstance(row, dict) else {})

    def _show_details(self, row: dict[str, Any]) -> None:
        if not row:
            self.detail_title.setText("No matching templates")
            self.detail_meta.clear()
            self.detail_description.clear()
            self.detail_features.clear()
            self.detail_license.clear()
            self.favorite_button.setEnabled(False)
            return
        self.favorite_button.setEnabled(True)
        self.detail_title.setText(str(row["name"]))
        self.detail_meta.setText(
            f"{row['category']}  |  {row['difficulty']}  |  "
            f"{len(row['artboard_presets'])} screens"
        )
        self.detail_description.setText(str(row["description"]))
        self.detail_features.setText(
            "<b>Included</b><br>"
            + "<br>".join(f"- {feature}" for feature in row["features"])
            + "<br><br><b>Tags</b><br>"
            + ", ".join(row["tags"])
        )
        license_row = row["license"]
        self.detail_license.setText(
            f"<b>Source and license</b><br>{row['source']}<br>"
            f"{license_row['name']}<br>"
            f"Commercial use: {'Yes' if license_row['commercial_use'] else 'No'}"
        )
        self.favorite_button.setText(
            "Remove from Favorites"
            if row.get("favorite")
            else "Add to Favorites"
        )

    def _toggle_favorite(self) -> None:
        item = self.items.currentItem()
        row = item.data(Qt.ItemDataRole.UserRole + 1) if item else {}
        if not isinstance(row, dict) or not row:
            return
        set_ui_template_favorite(
            str(row["id"]),
            not bool(row.get("favorite")),
        )
        self._populate()


class PainterUITemplateLibrary(QWidget):
    template_apply_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        catalog = _gallery_templates()
        summary = QLabel(
            f"{len(catalog)} complete templates across "
            f"{len({row['category'] for row in catalog})} categories"
        )
        summary.setObjectName("PaintMuted")
        summary.setWordWrap(True)
        layout.addWidget(summary)
        self.quick_list = QListWidget()
        for row in catalog:
            prefix = "★ " if row.get("favorite") else ""
            item = QListWidgetItem(
                QIcon(ui_template_thumbnail(str(row["id"]))),
                f"{prefix}{row['name']}\n{row['category']}",
            )
            item.setData(Qt.ItemDataRole.UserRole, str(row["id"]))
            self.quick_list.addItem(item)
        self.quick_list.itemDoubleClicked.connect(
            lambda item: self.template_apply_requested.emit(
                str(item.data(Qt.ItemDataRole.UserRole) or "")
            )
        )
        layout.addWidget(self.quick_list, 1)
        browse = QPushButton("Browse Template Gallery")
        browse.clicked.connect(self._browse)
        layout.addWidget(browse)

    def _browse(self) -> None:
        dialog = PainterUITemplateGalleryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.selected_template_id:
                self.template_apply_requested.emit(dialog.selected_template_id)


class PainterUITemplateStrip(QFrame):
    """Compact icon-first template access below the Painter menu bar."""

    template_apply_requested = Signal(str)

    def __init__(self, parent=None, *, quick_count: int = 5) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUITemplateStrip")
        self._quick_count = max(1, int(quick_count))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 4, 8, 4)
        layout.setSpacing(4)

        browse = QPushButton("")
        browse.setObjectName("PainterUITemplateBrowse")
        browse.setToolTip("Open UI template gallery")
        browse.setAccessibleName("UI template gallery")
        browse.setIcon(app_icon("grid", size=15, color="#DCE6F7"))
        browse.setIconSize(icon_size(15))
        browse.setFixedSize(36, 42)
        browse.clicked.connect(self._browse)
        self.browse_button = browse
        layout.addWidget(browse)

        divider = QFrame()
        divider.setObjectName("PainterUITemplateDivider")
        divider.setFixedSize(1, 30)
        layout.addWidget(divider)

        self.quick_buttons: list[QPushButton] = []
        for row in _gallery_templates()[: self._quick_count]:
            template_id = str(row["id"])
            button = QPushButton("")
            button.setObjectName("PainterUITemplateQuick")
            button.setToolTip(f"{row['name']}\n{row['category']}")
            button.setAccessibleName(str(row["name"]))
            button.setIcon(QIcon(ui_template_thumbnail(template_id)))
            button.setIconSize(QSize(66, 37))
            button.setFixedSize(76, 42)
            button.clicked.connect(
                lambda _checked=False, value=template_id: (
                    self.template_apply_requested.emit(value)
                )
            )
            layout.addWidget(button)
            self.quick_buttons.append(button)
        layout.addStretch(1)

    def _browse(self) -> None:
        dialog = PainterUITemplateGalleryDialog(self)
        if (
            dialog.exec() == QDialog.DialogCode.Accepted
            and dialog.selected_template_id
        ):
            self.template_apply_requested.emit(dialog.selected_template_id)


__all__ = [
    "PainterUITemplateGalleryDialog",
    "PainterUITemplateLibrary",
    "PainterUITemplateStrip",
    "TEMPLATE_THUMBNAIL_SIZE",
    "ui_template_thumbnail",
]
