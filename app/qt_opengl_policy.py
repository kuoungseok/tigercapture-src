"""Qt/OpenGL startup policy helpers.

These helpers must stay import-light because they run before QApplication is
created.  The editor uses QOpenGLWidget for the GPU preview, and Qt 6 may
recreate a shown top-level native window when the first QOpenGLWidget is added
late.  Applying the application attribute early plus prewarming the actual
preview widget keeps that transition out of the user's drag/drop path.
"""
from __future__ import annotations


def configure_qt_opengl_application_attributes() -> bool:
    """Apply Qt application attributes required before QApplication exists."""
    try:
        from PySide6.QtCore import QCoreApplication, Qt

        QCoreApplication.setAttribute(
            Qt.ApplicationAttribute.AA_ShareOpenGLContexts,
            True,
        )
        return True
    except Exception:
        return False
