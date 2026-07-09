from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QVBoxLayout, QWidget


class LazyPanelHost(QWidget):
    """Lightweight placeholder that builds a dock panel only when shown."""

    def __init__(
        self,
        builder: Callable[[QWidget], QWidget],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._builder = builder
        self._panel: QWidget | None = None
        self._build_failed = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

    def ensure_panel(self) -> QWidget | None:
        if self._panel is not None:
            return self._panel
        if self._build_failed:
            return None
        try:
            panel = self._builder(self)
        except Exception:
            self._build_failed = True
            raise
        self._panel = panel
        layout = self.layout()
        if layout is not None and layout.indexOf(panel) < 0:
            layout.addWidget(panel)
        panel.setVisible(True)
        return panel

    def refresh_library(self) -> None:
        panel = self._panel
        refresh = getattr(panel, "refresh_library", None) if panel is not None else None
        if callable(refresh):
            refresh()

    def refresh_from_store(self) -> None:
        panel = self._panel
        refresh = getattr(panel, "refresh_from_store", None) if panel is not None else None
        if callable(refresh):
            refresh()

    @property
    def _default_ms(self) -> int:
        panel = self._panel
        try:
            return int(getattr(panel, "_default_ms", 500))
        except Exception:
            return 500

    @property
    def _cards(self) -> list:
        panel = self._panel
        cards = getattr(panel, "_cards", None) if panel is not None else None
        return list(cards or [])

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        if self._panel is None and not self._build_failed:
            try:
                self.ensure_panel()
            except Exception:
                pass
