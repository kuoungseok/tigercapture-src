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
    QScrollArea,
    QVBoxLayout,
    QWidget,
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
        self.resize(1180, 760)
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
        self.items.setGridSize(QSize(286, 220))
        self.items.setSpacing(12)
        self.items.itemDoubleClicked.connect(lambda _item: self.accept())
        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self.items, 1)

        detail_scroll = QScrollArea(self)
        detail_scroll.setObjectName("MotionTemplateGuide")
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setMinimumWidth(300)
        detail_scroll.setMaximumWidth(360)
        detail_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        detail = QWidget(detail_scroll)
        detail.setObjectName("MotionTemplateGuideBody")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(10, 4, 8, 8)
        detail_layout.setSpacing(9)
        self.guide_title = QLabel("Select a template", detail)
        self.guide_title.setObjectName("MotionInspectorSection")
        self.guide_title.setWordWrap(True)
        self.guide_meta = QLabel("", detail)
        self.guide_meta.setObjectName("MotionOutputStatus")
        self.guide_description = QLabel("", detail)
        self.guide_description.setObjectName("MotionGalleryCaption")
        self.guide_description.setWordWrap(True)
        self.guide_features = QLabel("", detail)
        self.guide_features.setWordWrap(True)
        self.guide_replacements = QLabel("", detail)
        self.guide_replacements.setWordWrap(True)
        self.guide_steps = QLabel("", detail)
        self.guide_steps.setWordWrap(True)
        detail_layout.addWidget(self.guide_title)
        detail_layout.addWidget(self.guide_meta)
        detail_layout.addWidget(self.guide_description)
        detail_layout.addWidget(self.guide_features)
        detail_layout.addWidget(self.guide_replacements)
        detail_layout.addWidget(self.guide_steps)
        detail_layout.addStretch(1)
        detail_scroll.setWidget(detail)
        content.addWidget(detail_scroll)
        root.addLayout(content, 1)

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
            haystack = " ".join([
                str(row["name"]),
                str(row["category"]),
                str(row.get("description") or ""),
                *[str(item) for item in row.get("features", [])],
                *[str(item) for item in row.get("replace_items", [])],
                *[str(item) for item in row.get("tags", [])],
            ]).lower()
            if query and query not in haystack:
                continue
            pixmap = motion_template_thumbnail(
                str(row["id"]),
                self.selected_variant,
            )
            item = QListWidgetItem(
                QIcon(pixmap),
                (
                    f"{row['name']}\n"
                    f"{row['category']}  |  "
                    f"{int(row.get('default_duration_ms', 0)) // 1000}s  |  "
                    f"{int(row.get('scene_count', 1))} scenes"
                ),
            )
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            item.setData(Qt.ItemDataRole.UserRole + 1, row)
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
        row = item.data(Qt.ItemDataRole.UserRole + 1) if item else None
        self._show_guide(row if isinstance(row, dict) else {})

    def _show_guide(self, row: dict) -> None:
        if not row:
            self.guide_title.setText("Select a template")
            self.guide_meta.clear()
            self.guide_description.clear()
            self.guide_features.clear()
            self.guide_replacements.clear()
            self.guide_steps.clear()
            return
        self.guide_title.setText(str(row.get("name") or "Template"))
        minutes = int(row.get("estimated_minutes", 0) or 0)
        duration_seconds = int(row.get("default_duration_ms", 0) or 0) // 1000
        scene_count = int(row.get("scene_count", 1) or 1)
        meta = (
            f"{row.get('category', '')}  |  "
            f"{duration_seconds}s  |  {scene_count} scenes  |  "
            f"{row.get('difficulty', 'Starter')}"
        )
        if minutes:
            meta += f"  |  {minutes} min"
        self.guide_meta.setText(meta)
        self.guide_description.setText(str(row.get("description") or (
            "A complete animated layout. Apply it, then inspect and replace its layers."
        )))
        workflow = str(row.get("workflow") or "Quick graphic")
        self.guide_description.setText(
            f"<b>Best for</b><br>{workflow}<br><br>"
            + self.guide_description.text()
        )
        features = [str(item) for item in row.get("features", [])]
        self.guide_features.setText(
            "<b>Included features</b><br>"
            + ("<br>".join(f"- {feature}" for feature in features) if features else "- Editable layers and controls")
        )
        replacements = [str(item) for item in row.get("replace_items", [])]
        self.guide_replacements.setText(
            "<b>Replace before export</b><br>"
            + (
                "<br>".join(f"- {item}" for item in replacements)
                if replacements
                else "- Headline, subtitle, colors, and media"
            )
        )
        steps = [str(item) for item in row.get("tutorial_steps", [])]
        self.guide_steps.setText(
            "<b>Try it</b><br>"
            + (
                "<br><br>".join(f"{index}. {step}" for index, step in enumerate(steps, 1))
                if steps
                else "Apply the template, select a layer, and replace the published text and colors."
            )
        )


__all__ = [
    "MotionTemplateGalleryDialog",
    "THUMBNAIL_SIZE",
    "motion_template_thumbnail",
]
