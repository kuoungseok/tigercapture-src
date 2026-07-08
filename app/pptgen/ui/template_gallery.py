"""Template gallery dialog for the user PPT generator."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.pptgen.preview import render_slide_image
from app.pptgen.schema import DeckSpec
from app.pptgen.templates import PptTemplateSpec, deck_from_template, list_templates
from app.pptgen.ui.style import PPT_DIALOG_QSS


THUMBNAIL_SIZE = (224, 126)


def _pixmap_from_rgba_bytes(raw: bytes, width: int, height: int) -> QPixmap:
    image = QImage(raw, width, height, width * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(image.copy())


def template_thumbnail_pixmap(template_id: str, *, size: tuple[int, int] = THUMBNAIL_SIZE) -> QPixmap:
    deck = deck_from_template(template_id)
    slide = deck.slides[0]
    image = render_slide_image(deck, slide, size=size).convert("RGBA")
    return _pixmap_from_rgba_bytes(image.tobytes("raw", "RGBA"), image.width, image.height)


def _template_icon(pixmap: QPixmap) -> QIcon:
    icon = QIcon()
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Active, QIcon.Mode.Selected, QIcon.Mode.Disabled):
        icon.addPixmap(pixmap, mode, QIcon.State.Off)
    return icon


def deck_from_selected_template(template_id: str, *, title: str = "Untitled Presentation") -> DeckSpec:
    return deck_from_template(template_id, deck_id="untitled-presentation", title=title)


class TemplateGalleryDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mode: str = "apply",
        templates: list[PptTemplateSpec] | None = None,
    ) -> None:
        super().__init__(parent)
        self.mode = "new" if str(mode or "").lower() == "new" else "apply"
        self.templates = list(templates or list_templates())
        self.selected_template_id = self.templates[0].id if self.templates else ""
        self._show_side_preview = self.mode != "new"
        self.setWindowTitle("Template Gallery")
        self.resize(1120, 560)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(12)

        title = QLabel("Create from a template" if self.mode == "new" else "Apply template to current slide")
        title.setObjectName("TemplateGalleryTitle")
        root.addWidget(title)

        caption = QLabel(
            "Choose Blank for a clean document, or start from a media, 3D, report, timeline, or typography layout."
            if self.mode == "new"
            else "The selected template replaces elements on the current slide while keeping the slide in the timeline."
        )
        caption.setWordWrap(True)
        caption.setObjectName("TemplateGalleryCaption")
        root.addWidget(caption)

        row = QHBoxLayout()
        row.setSpacing(16)
        root.addLayout(row, 1)

        self.template_list = QListWidget(self)
        self.template_list.setViewMode(QListView.ViewMode.IconMode)
        self.template_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.template_list.setMovement(QListView.Movement.Static)
        self.template_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.template_list.setIconSize(QSize(*THUMBNAIL_SIZE))
        self.template_list.setGridSize(QSize(254, 190))
        self.template_list.setSpacing(14)
        self.template_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.template_list.itemSelectionChanged.connect(self._selection_changed)
        self.template_list.itemDoubleClicked.connect(lambda _item: self.accept())
        row.addWidget(self.template_list, 1)

        self.preview: QLabel | None = None
        self.name_label: QLabel | None = None
        self.category_label: QLabel | None = None
        self.description_label: QLabel | None = None
        if self._show_side_preview:
            side = QFrame(self)
            side.setObjectName("TemplatePreviewSide")
            side_layout = QVBoxLayout(side)
            side_layout.setContentsMargins(14, 14, 14, 14)
            side_layout.setSpacing(10)
            self.preview = QLabel(side)
            self.preview.setObjectName("TemplateLargePreview")
            self.preview.setFixedSize(320, 180)
            self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            side_layout.addWidget(self.preview)
            self.name_label = QLabel(side)
            self.name_label.setObjectName("TemplateName")
            self.name_label.setWordWrap(True)
            side_layout.addWidget(self.name_label)
            self.category_label = QLabel(side)
            self.category_label.setObjectName("TemplateCategory")
            side_layout.addWidget(self.category_label)
            self.description_label = QLabel(side)
            self.description_label.setObjectName("TemplateDescription")
            self.description_label.setWordWrap(True)
            side_layout.addWidget(self.description_label)
            side_layout.addStretch(1)
            row.addWidget(side, 0)

        for template in self.templates:
            item = QListWidgetItem(_template_icon(template_thumbnail_pixmap(template.id)), template.name)
            item.setData(Qt.ItemDataRole.UserRole, template.id)
            item.setToolTip(template.description)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.template_list.addItem(item)
        if self.template_list.count():
            self.template_list.setCurrentRow(0)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("Create" if self.mode == "new" else "Apply")
        root.addWidget(buttons)

        self.setStyleSheet(PPT_DIALOG_QSS)
        self._selection_changed()

    def _selected_template(self) -> PptTemplateSpec | None:
        item = self.template_list.currentItem()
        template_id = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else self.selected_template_id
        return next((template for template in self.templates if template.id == template_id), None)

    def _selection_changed(self) -> None:
        template = self._selected_template()
        if template is None:
            self.selected_template_id = ""
            if self.preview is not None:
                self.preview.clear()
            if self.name_label is not None:
                self.name_label.setText("")
            if self.category_label is not None:
                self.category_label.setText("")
            if self.description_label is not None:
                self.description_label.setText("")
            return
        self.selected_template_id = template.id
        if self.preview is None:
            return
        pixmap = template_thumbnail_pixmap(template.id, size=(320, 180))
        self.preview.setPixmap(pixmap)
        if self.name_label is not None:
            self.name_label.setText(template.name)
        if self.category_label is not None:
            self.category_label.setText(template.category)
        if self.description_label is not None:
            self.description_label.setText(template.description)


def choose_template_id(parent: QWidget | None = None, *, mode: str = "apply") -> str:
    dialog = TemplateGalleryDialog(parent, mode=mode)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return ""
    return dialog.selected_template_id


__all__ = [
    "TemplateGalleryDialog",
    "choose_template_id",
    "deck_from_selected_template",
    "template_thumbnail_pixmap",
]
