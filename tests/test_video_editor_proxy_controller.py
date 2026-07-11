from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import app.video_editor_proxy_controller as proxy_controller


class FakeSignal:
    def __init__(self) -> None:
        self.handlers = []

    def connect(self, handler) -> None:
        self.handlers.append(handler)

    def emit(self, *args) -> None:
        for handler in list(self.handlers):
            handler(*args)


class FakeThread:
    instances = []

    def __init__(self, source: Path, *, force: bool = False, parent=None) -> None:
        self.source = Path(source)
        self.force = force
        self.parent = parent
        self.done = FakeSignal()
        self.failed = FakeSignal()
        self.progress = FakeSignal()
        self.finished = FakeSignal()
        self.started = False
        FakeThread.instances.append(self)

    def start(self) -> None:
        self.started = True
        self.progress.emit(10)


class FakeWidget:
    def __init__(self) -> None:
        self.enabled = None
        self.text = ""
        self.tooltip = ""

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def setText(self, text: str) -> None:
        self.text = text

    def setToolTip(self, tooltip: str) -> None:
        self.tooltip = tooltip


class FakeButton(FakeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.checked = True
        self.blocked = False
        self.block_history = []
        self.checked_while_blocked = []

    def blockSignals(self, blocked: bool) -> bool:
        previous = self.blocked
        self.blocked = bool(blocked)
        self.block_history.append(self.blocked)
        return previous

    def setChecked(self, checked: bool) -> None:
        self.checked = bool(checked)
        self.checked_while_blocked.append(self.blocked)


class FakeRow:
    def __init__(self) -> None:
        self.updates = 0

    def update(self) -> None:
        self.updates += 1


class FakePool:
    def __init__(self) -> None:
        self.refreshes = 0

    def refresh_proxy_statuses(self) -> None:
        self.refreshes += 1


def test_owner_original_source_and_apply_proxy_owner_restore_original(tmp_path):
    source = tmp_path / "clip.mp4"
    proxy = tmp_path / "proxies" / "clip_proxy.mp4"
    proxy.parent.mkdir()
    source.write_bytes(b"source")
    proxy.write_bytes(b"proxy")
    owner = SimpleNamespace(source_path=source)

    proxy_controller.apply_proxy_owner(
        owner,
        True,
        fresh_proxy_for_source=lambda path: proxy if path == source else None,
    )

    assert owner.source_path == proxy
    assert owner._original_source_path == source
    assert proxy_controller.owner_original_source(owner) == source

    proxy_controller.apply_proxy_owner(owner, False)

    assert owner.source_path == source
    assert owner._original_source_path is None


def test_active_proxy_source_path_prefers_selected_clip_then_active_track_position(tmp_path):
    selected_source = tmp_path / "selected.mp4"
    active_source = tmp_path / "active.mp4"
    early_source = tmp_path / "early.mp4"
    selected_clip = SimpleNamespace(source_path=selected_source)
    active_clip = SimpleNamespace(source_path=active_source, timeline_in_ms=100, timeline_out_ms=200)
    early_clip = SimpleNamespace(source_path=early_source, timeline_in_ms=0, timeline_out_ms=50)
    track = SimpleNamespace(source_path=None, clips=[early_clip, active_clip])
    owner = SimpleNamespace(
        _selected_clips=[(1, 9)],
        _find_video_clip=lambda _track_id, _clip_id: (track, selected_clip),
        _active_track=lambda: track,
        _player=SimpleNamespace(position=lambda: 120),
    )

    assert proxy_controller.active_proxy_source_path(owner) == selected_source

    owner._selected_clips = []

    assert proxy_controller.active_proxy_source_path(owner) == active_source


def test_proxy_status_strings_ui_labels_and_media_pool_missing_convention():
    source = Path("clip.mp4")
    proxy = Path("proxies/clip_proxy.mp4")

    assert proxy_controller.CORE_PROXY_STATES == frozenset({"missing", "ready", "stale"})
    assert proxy_controller.CONTROLLER_PROXY_STATES == frozenset({"missing", "ready", "stale", "building"})
    assert proxy_controller.proxy_label_for_status("building", proxy_mode=False) == "Building"
    assert proxy_controller.proxy_label_for_status("ready", proxy_mode=False) == "Ready"
    assert proxy_controller.proxy_label_for_status("ready", proxy_mode=True) == "Active"
    assert proxy_controller.proxy_label_for_status("stale", proxy_mode=True) == "Stale"
    assert proxy_controller.proxy_label_for_status("missing", proxy_mode=True) == "Original"

    assert proxy_controller.media_pool_proxy_state("missing") == ""
    assert proxy_controller.media_pool_proxy_state("ready") == "ready"
    assert proxy_controller.media_pool_proxy_state("stale") == "stale"
    assert proxy_controller.core_proxy_state_from_media_pool_state("") == "missing"

    building = proxy_controller.proxy_status_ui_state(
        source,
        status="building",
        proxy=proxy,
        proxy_mode=True,
        proxy_exists=True,
    )
    assert building.text == "Building"
    assert building.refresh_enabled is False
    assert building.delete_enabled is False
    assert "State: building" in building.tooltip

    missing = proxy_controller.proxy_status_ui_state(
        source,
        status="missing",
        proxy=proxy,
        proxy_mode=True,
        proxy_exists=False,
    )
    assert missing.text == "Original"
    assert missing.refresh_enabled is True
    assert missing.delete_enabled is False

    empty = proxy_controller.proxy_status_ui_state(None)
    assert empty.text == "Original"
    assert empty.manage_enabled is False
    assert empty.refresh_enabled is False


def test_refresh_proxy_status_ui_applies_active_ready_and_busy_states(tmp_path):
    source = tmp_path / "clip.mp4"
    proxy = tmp_path / "proxies" / "clip_proxy.mp4"
    proxy.parent.mkdir()
    source.write_bytes(b"source")
    proxy.write_bytes(b"proxy")
    owner = SimpleNamespace(
        _proxy_mode=True,
        proxy_status_label=FakeWidget(),
        proxy_manage_btn=FakeWidget(),
        proxy_refresh_action=FakeWidget(),
        proxy_delete_action=FakeWidget(),
    )

    ui = proxy_controller.refresh_proxy_status_ui(
        owner,
        active_source=source,
        path_for=lambda _path: proxy,
        status_for=lambda _owner, _path: "ready",
    )

    assert ui is not None
    assert owner.proxy_status_label.text == "Active"
    assert "State: ready" in owner.proxy_status_label.tooltip
    assert owner.proxy_manage_btn.enabled is True
    assert owner.proxy_refresh_action.enabled is True
    assert owner.proxy_delete_action.enabled is True

    ui = proxy_controller.refresh_proxy_status_ui(
        owner,
        active_source=source,
        path_for=lambda _path: proxy,
        status_for=lambda _owner, _path: "building",
    )

    assert ui is not None
    assert owner.proxy_status_label.text == "Building"
    assert owner.proxy_refresh_action.enabled is False
    assert owner.proxy_delete_action.enabled is False

    ui = proxy_controller.refresh_proxy_status_ui(owner, active_source=None)

    assert ui is not None
    assert owner.proxy_status_label.text == "Original"
    assert owner.proxy_manage_btn.enabled is False
    assert owner.proxy_refresh_action.enabled is False
    assert owner.proxy_delete_action.enabled is False


def test_toggle_proxy_mode_swaps_tracks_clips_and_refreshes_window_ports(tmp_path):
    track_source = tmp_path / "track.mp4"
    clip_source = tmp_path / "clip.mp4"
    track_proxy = tmp_path / "track_proxy.mp4"
    clip_proxy = tmp_path / "clip_proxy.mp4"
    track = SimpleNamespace(source_path=track_source, clips=[SimpleNamespace(source_path=clip_source)])
    row = FakeRow()
    owner = SimpleNamespace(
        _proxy_mode=False,
        _tracks=[track],
        _track_rows={1: row},
        player_refreshes=0,
        ui_refreshes=0,
    )
    owner._refresh_player_tracks = lambda: setattr(owner, "player_refreshes", owner.player_refreshes + 1)
    proxy_map = {track_source: track_proxy, clip_source: clip_proxy}

    def apply_owner(item, checked):
        proxy_controller.apply_proxy_owner(
            item,
            checked,
            fresh_proxy_for_source=lambda path: proxy_map.get(path),
        )

    proxy_controller.toggle_proxy_mode(
        owner,
        True,
        apply_owner=apply_owner,
        refresh_ui=lambda window: setattr(window, "ui_refreshes", window.ui_refreshes + 1),
    )

    assert owner._proxy_mode is True
    assert track.source_path == track_proxy
    assert track.clips[0].source_path == clip_proxy
    assert owner.player_refreshes == 1
    assert row.updates == 1
    assert owner.ui_refreshes == 1

    proxy_controller.toggle_proxy_mode(
        owner,
        False,
        apply_owner=apply_owner,
        refresh_ui=lambda window: setattr(window, "ui_refreshes", window.ui_refreshes + 1),
    )

    assert owner._proxy_mode is False
    assert track.source_path == track_source
    assert track.clips[0].source_path == clip_source
    assert owner.player_refreshes == 2
    assert row.updates == 2


def test_start_proxy_generation_uses_fake_thread_and_tracks_building_state(tmp_path):
    FakeThread.instances = []
    source = tmp_path / "clip.mp4"
    proxy = tmp_path / "proxies" / "clip_proxy.mp4"
    source.write_bytes(b"source")
    owner = SimpleNamespace(_proxy_threads={}, refreshes=0, done_args=[], failed_args=[])
    owner._on_proxy_done = lambda original, generated: owner.done_args.append((original, generated))
    owner._on_proxy_failed = lambda original, reason: owner.failed_args.append((original, reason))

    started = proxy_controller.start_proxy_generation(
        owner,
        source,
        thread_factory=FakeThread,
        state_for=lambda _path: "missing",
        refresh_ui=lambda window: setattr(window, "refreshes", window.refreshes + 1),
    )

    thread = FakeThread.instances[0]
    assert started is True
    assert thread.started is True
    assert thread.force is False
    assert owner._proxy_threads == {str(source): thread}
    assert proxy_controller.proxy_status_for_path(owner, source, state_for=lambda _path: "missing") == "building"
    assert owner.refreshes >= 2

    duplicate = proxy_controller.start_proxy_generation(
        owner,
        source,
        thread_factory=FakeThread,
        state_for=lambda _path: "missing",
        refresh_ui=lambda _window: None,
    )
    assert duplicate is False
    assert len(FakeThread.instances) == 1

    thread.done.emit(str(source), str(proxy))
    thread.failed.emit(str(source), "boom")
    assert owner.done_args == [(str(source), str(proxy))]
    assert owner.failed_args == [(str(source), "boom")]

    thread.finished.emit()
    assert owner._proxy_threads == {}
    assert proxy_controller.proxy_status_for_path(owner, source, state_for=lambda _path: "missing") == "missing"


def test_start_proxy_generation_skips_ready_proxy_unless_forced(tmp_path):
    FakeThread.instances = []
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"source")
    owner = SimpleNamespace(_proxy_threads={}, refreshes=0)

    skipped = proxy_controller.start_proxy_generation(
        owner,
        source,
        thread_factory=FakeThread,
        state_for=lambda _path: "ready",
        refresh_ui=lambda window: setattr(window, "refreshes", window.refreshes + 1),
    )

    assert skipped is False
    assert FakeThread.instances == []
    assert owner.refreshes == 1

    forced = proxy_controller.start_proxy_generation(
        owner,
        source,
        force=True,
        thread_factory=FakeThread,
        state_for=lambda _path: "ready",
        refresh_ui=lambda window: setattr(window, "refreshes", window.refreshes + 1),
    )

    assert forced is True
    assert FakeThread.instances[0].force is True


def test_on_proxy_done_applies_immediately_when_proxy_mode_is_enabled(tmp_path):
    source = tmp_path / "track.mp4"
    proxy = tmp_path / "proxies" / "track_proxy.mp4"
    other_source = tmp_path / "clip.mp4"
    track = SimpleNamespace(source_path=source, clips=[SimpleNamespace(source_path=other_source)])
    row = FakeRow()
    pool = FakePool()
    owner = SimpleNamespace(
        _proxy_mode=True,
        _tracks=[track],
        _track_rows={1: row},
        _media_pool=pool,
        player_refreshes=0,
        ui_refreshes=0,
    )
    owner._refresh_player_tracks = lambda: setattr(owner, "player_refreshes", owner.player_refreshes + 1)

    applied = proxy_controller.on_proxy_done(
        owner,
        str(source),
        str(proxy),
        refresh_ui=lambda window: setattr(window, "ui_refreshes", window.ui_refreshes + 1),
    )

    assert applied == 1
    assert track.source_path == proxy
    assert track._original_source_path == source
    assert track.clips[0].source_path == other_source
    assert owner.player_refreshes == 1
    assert row.updates == 1
    assert pool.refreshes == 1
    assert owner.ui_refreshes == 1


def test_on_proxy_failed_shows_status_bar_message_and_refreshes_ui():
    messages = []
    owner = SimpleNamespace(
        statusBar=lambda: SimpleNamespace(showMessage=lambda text, timeout: messages.append((text, timeout))),
        refreshes=0,
    )

    proxy_controller.on_proxy_failed(
        owner,
        "clip.mp4",
        "ffmpeg failed",
        refresh_ui=lambda window: setattr(window, "refreshes", window.refreshes + 1),
    )

    assert messages == [("Proxy generation failed: ffmpeg failed", 5000)]
    assert owner.refreshes == 1


def test_regenerate_and_delete_active_source_use_injected_controller_ports(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"source")
    pool = FakePool()
    button = FakeButton()
    owner = SimpleNamespace(_proxy_mode=True, _media_pool=pool, proxy_btn=button, refreshes=0)
    starts = []
    toggles = []
    deletes = []

    regenerated = proxy_controller.regenerate_proxy_for_active_source(
        owner,
        active_source_path=lambda _owner: source,
        start_generation=lambda _owner, path, force=False: starts.append((path, force)) or True,
    )

    assert regenerated is True
    assert starts == [(source, True)]

    @contextmanager
    def block_signals(widget):
        previous = widget.blockSignals(True)
        try:
            yield
        finally:
            widget.blockSignals(previous)

    deleted = proxy_controller.delete_proxy_for_active_source(
        owner,
        active_source_path=lambda _owner: source,
        delete_proxy=lambda path: deletes.append(path) or True,
        toggle_mode=lambda window, checked: toggles.append(checked) or setattr(window, "_proxy_mode", checked),
        refresh_ui=lambda window: setattr(window, "refreshes", window.refreshes + 1),
        block_signals=block_signals,
    )

    assert deleted is True
    assert button.checked is False
    assert button.checked_while_blocked == [True]
    assert button.block_history == [True, False]
    assert toggles == [False]
    assert deletes == [source]
    assert pool.refreshes == 1
    assert owner.refreshes == 1


def test_auto_proxy_candidates_use_preview_policy_and_skip_ready_sources(tmp_path):
    source = tmp_path / "hires.mp4"
    ready = tmp_path / "ready.mp4"
    source.write_bytes(b"source")
    ready.write_bytes(b"ready")
    owner = SimpleNamespace(
        _project_settings={"preview": {"quality_mode": "auto", "auto_proxy": True}},
        _tracks=[],
    )

    rows = proxy_controller.auto_proxy_candidates(
        owner,
        paths=[source, ready],
        policy_for=lambda path: {"needs_proxy": path == source, "preview_height": 540},
        state_for=lambda path: "ready" if path == ready else "missing",
    )

    assert len(rows) == 1
    assert rows[0]["source"] == source
    assert rows[0]["force"] is False
    assert rows[0]["policy"]["preview_height"] == 540


def test_queue_auto_proxy_generation_starts_missing_and_forces_stale(tmp_path):
    source = tmp_path / "hires.mp4"
    stale = tmp_path / "stale.mp4"
    source.write_bytes(b"source")
    stale.write_bytes(b"stale")
    owner = SimpleNamespace(
        _project_settings={"preview": {"auto_proxy": True}},
        _tracks=[],
        statusBar=lambda: SimpleNamespace(showMessage=lambda *_args: None),
    )
    starts = []

    count = proxy_controller.queue_auto_proxy_generation(
        owner,
        paths=[source, stale],
        policy_for=lambda _path: {"needs_proxy": True},
        state_for=lambda path: "stale" if path == stale else "missing",
        start_generation=lambda _owner, path, force=False: starts.append((path, force)) or True,
        max_jobs=4,
    )

    assert count == 2
    assert starts == [(source, False), (stale, True)]


def test_auto_proxy_generation_can_be_disabled_from_project_settings(tmp_path):
    source = tmp_path / "hires.mp4"
    source.write_bytes(b"source")
    owner = SimpleNamespace(
        _project_settings={"preview": {"auto_proxy": False}},
        _tracks=[],
    )

    assert proxy_controller.auto_proxy_candidates(
        owner,
        paths=[source],
        policy_for=lambda _path: {"needs_proxy": True},
        state_for=lambda _path: "missing",
    ) == []
