import os


def _qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _write_spine_stub(folder, name: str):
    model_path = folder / f"{name}.json"
    atlas_path = folder / f"{name}.atlas"
    model_path.write_text('{"skeleton": {"spine": "4.1"}}', encoding="utf-8")
    atlas_path.write_text("page.png\nsize: 1,1\n", encoding="utf-8")
    return model_path


def test_spine_asset_browser_auto_loads_single_file_folder(tmp_path, monkeypatch):
    app = _qapp()

    from PySide6.QtGui import QIcon
    from app.spine_editor import editor_window as spine_editor_window

    loaded: list[str] = []

    def fake_load_character(self, path: str, *, _from_deferred: bool = False):
        loaded.append(path)
        self._current_json = path

    monkeypatch.setattr(spine_editor_window.SpineEditorWindow, "_all_search_roots", lambda self: [])
    monkeypatch.setattr(spine_editor_window.SpineEditorWindow, "_load_character", fake_load_character)
    monkeypatch.setattr(spine_editor_window, "_generate_thumb", lambda _path: QIcon())

    model_path = _write_spine_stub(tmp_path, "hero")
    win = spine_editor_window.SpineEditorWindow(autoload_sample=False)
    try:
        win._current_folder = os.fspath(tmp_path)
        win._populate_grid(os.fspath(tmp_path))
        for _ in range(3):
            app.processEvents()

        assert loaded == [os.fspath(model_path)]
        assert win._char_grid.currentRow() == 0
        assert win._status_lbl.text() == "1개 - 자동 선택"
    finally:
        win.hide()
        win.deleteLater()


def test_spine_asset_browser_keeps_grid_choice_for_multiple_files(tmp_path, monkeypatch):
    app = _qapp()

    from PySide6.QtGui import QIcon
    from app.spine_editor import editor_window as spine_editor_window

    loaded: list[str] = []

    monkeypatch.setattr(spine_editor_window.SpineEditorWindow, "_all_search_roots", lambda self: [])
    monkeypatch.setattr(
        spine_editor_window.SpineEditorWindow,
        "_load_character",
        lambda self, path, **_kwargs: loaded.append(path),
    )
    monkeypatch.setattr(spine_editor_window, "_generate_thumb", lambda _path: QIcon())

    _write_spine_stub(tmp_path, "hero_a")
    _write_spine_stub(tmp_path, "hero_b")
    win = spine_editor_window.SpineEditorWindow(autoload_sample=False)
    try:
        win._current_folder = os.fspath(tmp_path)
        win._populate_grid(os.fspath(tmp_path))
        for _ in range(3):
            app.processEvents()

        assert loaded == []
        assert win._char_grid.count() == 2
        assert win._status_lbl.text() == "2개"
    finally:
        win.hide()
        win.deleteLater()
