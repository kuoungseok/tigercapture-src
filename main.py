import sys

from PySide6.QtWidgets import QApplication


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GifCam")
    app.setOrganizationName("GifCam")

    # Global dark theme — applies to every widget that doesn't set its own.
    from app.style import APP_QSS
    app.setStyleSheet(APP_QSS)

    from app.i18n import initialize as init_i18n

    init_i18n()

    from app.controller import AppController
    from app.main_window import MainWindow

    window = MainWindow()
    controller = AppController(window)
    _ = controller
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
