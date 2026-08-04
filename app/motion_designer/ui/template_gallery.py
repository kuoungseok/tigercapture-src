from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
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
_THUMBNAIL_CACHE: dict[tuple[str, str], QPixmap] = {}


def _template_placeholder(template_id: str, variant: str) -> QPixmap:
    template = get_template(template_id)
    palette = {
        "Logo Reveals": ("#172129", "#43d7b5"),
        "Lower Thirds": ("#18202a", "#5b8cff"),
        "Titles & Typography": ("#1d1924", "#d987ff"),
        "Transitions": ("#211b1b", "#ff7657"),
        "Intros & Openers": ("#171d29", "#f2c14e"),
        "Slideshows": ("#172320", "#70d6a5"),
        "Infographics & Data": ("#17212b", "#57c7ff"),
        "Social Media & YouTube": ("#25191d", "#ff5d7d"),
        "Production Essentials": ("#1f2023", "#c7ccd4"),
    }
    background, accent = palette.get(template.category, ("#171b21", "#43d7b5"))
    pixmap = QPixmap(THUMBNAIL_SIZE)
    pixmap.fill(QColor(background))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.fillRect(QRect(0, 0, 8, THUMBNAIL_SIZE.height()), QColor(accent))
    painter.setPen(QColor("#f4f6f8"))
    painter.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
    painter.drawText(
        QRect(22, 22, THUMBNAIL_SIZE.width() - 38, 62),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
        template.name,
    )
    painter.setPen(QColor(accent))
    painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
    painter.drawText(
        QRect(22, 96, THUMBNAIL_SIZE.width() - 38, 20),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        f"{template.category.upper()}  /  {variant}",
    )
    painter.end()
    return pixmap


def motion_template_thumbnail(template_id: str, variant: str = "16:9") -> QPixmap:
    template = get_template(template_id)
    chosen = variant if variant in template.variants else template.variants[0]
    key = (template.id, chosen)
    cached = _THUMBNAIL_CACHE.get(key)
    if cached is not None and not cached.isNull():
        return QPixmap(cached)
    composition = instantiate_template(template.id, variant=chosen)
    image = MotionExportRenderer(cache_capacity=2).render_frame(
        composition,
        composition.duration_ms * 0.35,
        width=THUMBNAIL_SIZE.width(),
        height=THUMBNAIL_SIZE.height(),
        use_cache=False,
    )
    pixmap = QPixmap.fromImage(image)
    _THUMBNAIL_CACHE[key] = QPixmap(pixmap)
    return pixmap


class MotionTemplateGalleryDialog(QDialog):
    def __init__(self, parent=None, *, variant: str = "16:9") -> None:
        super().__init__(parent)
        self.setObjectName("MotionTemplateGalleryDialog")
        self.setWindowTitle("Motion Template Gallery")
        self.resize(1180, 760)
        self.setStyleSheet(MOTION_DESIGNER_QSS)
        self.selected_template_id = ""
        self._thumbnail_generation = 0
        self._thumbnail_queue: list[tuple[str, str]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)
        self.title = QLabel("Start with a template", self)
        self.title.setObjectName("MotionGalleryTitle")
        root.addWidget(self.title)
        catalog_rows = list_templates()
        popular_count = sum(
            1 for row in catalog_rows
            if str(row.get("id") or "").startswith("popular_")
        )
        caption = QLabel(
            f"{popular_count} production staples plus "
            f"{len(catalog_rows) - popular_count} Tiger Studio and learning templates. "
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
        self.category.addItem("Top 10")
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
        self.items.verticalScrollBar().valueChanged.connect(
            lambda _value: QTimer.singleShot(
                0,
                lambda: self._queue_visible_thumbnails(self._thumbnail_generation),
            )
        )
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
        self._thumbnail_generation += 1
        generation = self._thumbnail_generation
        self._thumbnail_queue.clear()
        query = self.search.text().strip().lower()
        category = self.category.currentText()
        selected = self.selected_template_id
        self.items.clear()
        rows = list_templates()
        if category == "Top 10":
            rows = sorted(
                (
                    row for row in rows
                    if int(row.get("featured_rank", 0) or 0) > 0
                ),
                key=lambda row: int(row.get("featured_rank", 0) or 0),
            )
        for row in rows:
            if category not in {"All", "Top 10"} and row["category"] != category:
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
            template_id = str(row["id"])
            template = get_template(template_id)
            requested_variant = str(self.variant.currentData() or "16:9")
            chosen_variant = (
                requested_variant
                if requested_variant in template.variants
                else template.variants[0]
            )
            cache_key = (template_id, chosen_variant)
            pixmap = _THUMBNAIL_CACHE.get(cache_key)
            if pixmap is None:
                pixmap = _template_placeholder(template_id, chosen_variant)
            item = QListWidgetItem(
                QIcon(pixmap),
                (
                    (
                        f"TOP {int(row.get('featured_rank', 0))}  "
                        if int(row.get("featured_rank", 0) or 0) > 0
                        else ""
                    )
                    + f"{row['name']}\n"
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
        self.title.setText(f"Start with a template  ({self.items.count()})")
        QTimer.singleShot(0, lambda: self._queue_visible_thumbnails(generation))

    def _queue_visible_thumbnails(self, generation: int) -> None:
        if generation != self._thumbnail_generation:
            return
        requested_variant = str(self.variant.currentData() or "16:9")
        viewport_rect = self.items.viewport().rect()
        visible: list[tuple[str, str]] = []
        current = self.items.currentItem()
        ordered_items = (
            ([current] if current is not None else [])
            + [
                self.items.item(index)
                for index in range(self.items.count())
                if self.items.item(index) is not current
            ]
        )
        for item in ordered_items:
            if item is None or (
                item is not current
                and not self.items.visualItemRect(item).intersects(viewport_rect)
            ):
                continue
            template_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
            template = get_template(template_id)
            chosen_variant = (
                requested_variant
                if requested_variant in template.variants
                else template.variants[0]
            )
            if (template_id, chosen_variant) not in _THUMBNAIL_CACHE:
                visible.append((template_id, chosen_variant))
        self._thumbnail_queue = visible
        if self._thumbnail_queue:
            QTimer.singleShot(0, lambda: self._render_next_thumbnail(generation))

    def _render_next_thumbnail(self, generation: int) -> None:
        if generation != self._thumbnail_generation or not self._thumbnail_queue:
            return
        template_id, variant = self._thumbnail_queue.pop(0)
        pixmap = motion_template_thumbnail(template_id, variant)
        for index in range(self.items.count()):
            item = self.items.item(index)
            if str(item.data(Qt.ItemDataRole.UserRole) or "") == template_id:
                item.setIcon(QIcon(pixmap))
                break
        if self._thumbnail_queue:
            QTimer.singleShot(0, lambda: self._render_next_thumbnail(generation))

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
