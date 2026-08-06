from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.templates import (
    TEMPLATE_VARIANTS,
    get_template,
    instantiate_template,
    list_templates,
)
from .style import MOTION_DESIGNER_QSS


THUMBNAIL_SIZE = QSize(240, 135)


def motion_template_thumbnail(template_id: str, variant: str = "16:9") -> QPixmap:
    template = get_template(template_id)
    chosen = variant if variant in template.variants else template.variants[0]
    composition = instantiate_template(template.id, variant=chosen)
    image = MotionExportRenderer(cache_capacity=2).render_frame(
        composition,
        composition.duration_ms * 0.35,
        width=THUMBNAIL_SIZE.width(),
        height=THUMBNAIL_SIZE.height(),
        use_cache=False,
    )
    return QPixmap.fromImage(image)


class MotionTemplateGalleryDialog(QDialog):
    def __init__(self, parent=None, *, variant: str = "16:9") -> None:
        super().__init__(parent)
        self.setObjectName("MotionTemplateGalleryDialog")
        self.setWindowTitle("Motion Template Gallery")
        self.resize(1040, 680)
        self.setStyleSheet(MOTION_DESIGNER_QSS)
        self.selected_template_id = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)
        title = QLabel("Start with a template", self)
        title.setObjectName("MotionGalleryTitle")
        root.addWidget(title)
        caption = QLabel(
            "Choose a complete animated layout, then replace its text, media, "
            "character, and colors in the Inspector.",
            self,
        )
        caption.setWordWrap(True)
        caption.setObjectName("MotionGalleryCaption")
        root.addWidget(caption)

        filters = QHBoxLayout()
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search templates")
        self.category = QComboBox(self)
        categories = sorted({str(row["category"]) for row in list_templates()})
        self.category.addItem("All")
        self.category.addItems(categories)
        self.variant = QComboBox(self)
        for key in TEMPLATE_VARIANTS:
            self.variant.addItem(key, key)
        index = self.variant.findData(variant)
        self.variant.setCurrentIndex(max(0, index))
        filters.addWidget(self.search, 1)
        filters.addWidget(self.category)
        filters.addWidget(self.variant)
        root.addLayout(filters)

        self.items = QListWidget(self)
        self.items.setObjectName("MotionTemplateGallery")
        self.items.setViewMode(QListView.ViewMode.IconMode)
        self.items.setResizeMode(QListView.ResizeMode.Adjust)
        self.items.setMovement(QListView.Movement.Static)
        self.items.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.items.setIconSize(THUMBNAIL_SIZE)
        self.items.setGridSize(QSize(280, 202))
        self.items.setSpacing(12)
        self.items.itemDoubleClicked.connect(lambda _item: self.accept())
        root.addWidget(self.items, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        apply_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if apply_button is not None:
            apply_button.setText("Use Template")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.search.textChanged.connect(self._populate)
        self.category.currentTextChanged.connect(self._populate)
        self.variant.currentIndexChanged.connect(self._populate)
        self.items.itemSelectionChanged.connect(self._selection_changed)
        self._populate()

    @property
    def selected_variant(self) -> str:
        requested = str(self.variant.currentData() or "16:9")
        if not self.selected_template_id:
            return requested
        template = get_template(self.selected_template_id)
        return requested if requested in template.variants else template.variants[0]

    def _populate(self, *_args) -> None:
        query = self.search.text().strip().lower()
        category = self.category.currentText()
        selected = self.selected_template_id
        self.items.clear()
        for row in list_templates():
            if category != "All" and row["category"] != category:
                continue
            haystack = f"{row['name']} {row['category']}".lower()
            if query and query not in haystack:
                continue
            pixmap = motion_template_thumbnail(
                str(row["id"]),
                self.selected_variant,
            )
            item = QListWidgetItem(
                QIcon(pixmap),
                f"{row['name']}\n{row['category']}",
            )
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.items.addItem(item)
            if row["id"] == selected:
                self.items.setCurrentItem(item)
        if self.items.count() and self.items.currentRow() < 0:
            self.items.setCurrentRow(0)

    def _selection_changed(self) -> None:
        item = self.items.currentItem()
        self.selected_template_id = (
            str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        )


__all__ = [
    "MotionTemplateGalleryDialog",
    "THUMBNAIL_SIZE",
    "motion_template_thumbnail",
]
