from __future__ import annotations

import os


def test_template_gallery_renders_builtin_thumbnail_cards():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from app.pptgen.ui.template_gallery import TemplateGalleryDialog, template_thumbnail_pixmap

    app = QApplication.instance() or QApplication([])
    assert app is not None

    pixmap = template_thumbnail_pixmap("3d_showcase")
    assert pixmap.isNull() is False
    assert pixmap.width() == 224
    assert pixmap.height() == 126

    dialog = TemplateGalleryDialog(mode="new")
    assert dialog.template_list.count() >= 9
    assert dialog.selected_template_id == "blank"
