from __future__ import annotations

from types import SimpleNamespace

from app.video_editor_layout_reset_workflow import (
    LAYOUT_SPLITTER_SETTINGS_KEYS,
    reset_editor_layout_to_default,
)


class _FakeSettings:
    def __init__(self) -> None:
        self.removed: list[str] = []
        self.synced = False

    def remove(self, key: str) -> None:
        self.removed.append(key)

    def sync(self) -> None:
        self.synced = True


class _FakeSplitter:
    def __init__(self) -> None:
        self.sizes_set: list[list[int]] = []
        self.geometry_updates = 0
        self.updates = 0

    def setSizes(self, sizes) -> None:
        self.sizes_set.append([int(v) for v in sizes])

    def updateGeometry(self) -> None:
        self.geometry_updates += 1

    def update(self) -> None:
        self.updates += 1


class _FakeVisible:
    def __init__(self, visible: bool) -> None:
        self._visible = visible

    def isVisible(self) -> bool:
        return self._visible


def _owner(*, color_visible: bool = False) -> SimpleNamespace:
    calls: list[str] = []
    return SimpleNamespace(
        _main_dock_splitter=_FakeSplitter(),
        _editor_vertical_splitter=_FakeSplitter(),
        _top_work_splitter=_FakeSplitter(),
        _left_dock_sections_splitter=_FakeSplitter(),
        _right_dock_sections_splitter=_FakeSplitter(),
        _color_timeline_splitter=_FakeSplitter(),
        _color_container=_FakeVisible(color_visible),
        _timeline_compact_default_height=320,
        _refresh_command_bar_responsive=lambda: calls.append("refresh"),
        _flash_status=lambda message: calls.append(f"flash:{message}"),
        _calls=calls,
    )


def test_reset_editor_layout_to_default_clears_persisted_splitter_state(monkeypatch):
    import app.video_editor_layout_reset_workflow as workflow

    settings = _FakeSettings()
    monkeypatch.setattr(workflow, "_editor_settings", lambda: settings)

    owner = _owner()
    result = reset_editor_layout_to_default(owner)

    assert result["ok"] is True
    assert settings.removed == list(LAYOUT_SPLITTER_SETTINGS_KEYS)
    assert settings.synced is True
    assert owner._main_dock_splitter.sizes_set[-1] == [188, 1240]
    assert owner._editor_vertical_splitter.sizes_set[-1] == [600, 320]
    assert owner._top_work_splitter.sizes_set[-1] == [720, 600]
    assert owner._left_dock_sections_splitter.sizes_set[-1] == [520, 260]
    assert owner._right_dock_sections_splitter.sizes_set[-1] == [540, 260]
    assert owner._color_timeline_splitter.sizes_set[-1] == [0, 320]
    assert "refresh" in owner._calls
    assert "flash:Editor layout reset" in owner._calls


def test_reset_editor_layout_to_default_restores_visible_color_splitter(monkeypatch):
    import app.video_editor_layout_reset_workflow as workflow

    monkeypatch.setattr(workflow, "_editor_settings", _FakeSettings)

    owner = _owner(color_visible=True)
    result = reset_editor_layout_to_default(owner)

    assert result["ok"] is True
    assert owner._color_timeline_splitter.sizes_set[-1] == [230, 320]
