from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator


CORE_PROXY_STATES = frozenset({"missing", "ready", "stale"})
"""File-backed states returned by ``app.video_editor_media_proxy``."""

BUILDING_PROXY_STATE = "building"
CONTROLLER_PROXY_STATES = CORE_PROXY_STATES | {BUILDING_PROXY_STATE}
MEDIA_POOL_MISSING_PROXY_STATE = ""
"""Media Pool stores a missing video proxy as an empty string, not "missing"."""

NO_PROXY_SOURCE_TEXT = "Original"
NO_PROXY_SOURCE_TOOLTIP = "Select a video clip or video track to manage its proxy."


@dataclass(frozen=True)
class ProxyStatusUi:
    text: str
    tooltip: str
    manage_enabled: bool
    refresh_enabled: bool
    delete_enabled: bool
    busy: bool


_UNSET = object()


def _proxy_thread_key(path: Path) -> str:
    return str(Path(path))


def _default_proxy_path_for(path: Path) -> Path:
    from app.video_editor_media_proxy import _proxy_path_for

    return _proxy_path_for(Path(path))


def _default_proxy_state_for(path: Path) -> str:
    from app.video_editor_media_proxy import _proxy_state_for

    return _proxy_state_for(Path(path))


def _default_delete_proxy_for_source(path: Path) -> bool:
    from app.video_editor_media_proxy import _delete_proxy_for_source

    return bool(_delete_proxy_for_source(Path(path)))


def _default_thread_factory(path: Path, *, force: bool = False, parent: Any = None) -> Any:
    from app.video_editor_media_proxy import ProxyGeneratorThread

    return ProxyGeneratorThread(Path(path), force=force, parent=parent)


def owner_original_source(owner: Any) -> Path | None:
    """Return the source path an owner logically represents.

    ``owner`` only needs to expose ``source_path`` and, when proxy mode has
    swapped it, ``_original_source_path``. This mirrors the current
    ``VideoEditorWindow._owner_original_source`` duck-typing contract.
    """

    if owner is None:
        return None
    original = getattr(owner, "_original_source_path", None)
    if original is not None:
        return Path(original)
    source = getattr(owner, "source_path", None)
    if source is None:
        return None
    return Path(source)


def fresh_proxy_for(
    source: Path,
    *,
    state_for: Callable[[Path], str] | None = None,
    path_for: Callable[[Path], Path] | None = None,
) -> Path | None:
    """Return an existing fresh proxy path for ``source``, or ``None``."""

    source = Path(source)
    state_for = state_for or _default_proxy_state_for
    path_for = path_for or _default_proxy_path_for
    if state_for(source) != "ready":
        return None
    proxy = Path(path_for(source))
    return proxy if proxy.exists() else None


def apply_proxy_owner(
    owner: Any,
    checked: bool,
    *,
    fresh_proxy_for_source: Callable[[Path], Path | None] | None = None,
) -> None:
    """Switch one track/clip-like owner between original and proxy paths."""

    if owner is None or getattr(owner, "source_path", None) is None:
        return
    if checked:
        original = owner_original_source(owner)
        if original is None:
            return
        fresh_proxy_for_source = fresh_proxy_for_source or fresh_proxy_for
        proxy = fresh_proxy_for_source(original)
        if proxy is None:
            return
        setattr(owner, "_original_source_path", original)
        owner.source_path = Path(proxy)
        return

    original = getattr(owner, "_original_source_path", None)
    if original is not None:
        owner.source_path = Path(original)
        setattr(owner, "_original_source_path", None)


def iter_proxy_owners(tracks: Any) -> Iterator[Any]:
    """Yield track owners followed by their clip owners."""

    for track in tracks or []:
        yield track
        for clip in getattr(track, "clips", []) or []:
            yield clip


def active_proxy_source_path(owner: Any) -> Path | None:
    """Return the selected or active source used by proxy management UI."""

    finder = getattr(owner, "_find_video_clip", None)
    if callable(finder):
        for track_id, clip_id in list(getattr(owner, "_selected_clips", []) or []):
            try:
                _track, clip = finder(track_id, clip_id)
            except Exception:
                continue
            source = owner_original_source(clip)
            if source is not None:
                return source

    active_track = getattr(owner, "_active_track", None)
    track = active_track() if callable(active_track) else None
    if track is None:
        return None
    source = owner_original_source(track)
    if source is not None:
        return source

    pos = 0
    player = getattr(owner, "_player", None)
    position = getattr(player, "position", None)
    if callable(position):
        try:
            pos = int(position())
        except Exception:
            pos = 0

    first_source = None
    for clip in getattr(track, "clips", []) or []:
        source = owner_original_source(clip)
        if source is None:
            continue
        if first_source is None:
            first_source = source
        try:
            if int(getattr(clip, "timeline_in_ms", 0)) <= pos < int(getattr(clip, "timeline_out_ms", 0)):
                return source
        except Exception:
            continue
    return first_source


def proxy_thread_key(path: Path) -> str:
    return str(Path(path))


def proxy_status_for_path(
    owner: Any,
    path: Path,
    *,
    state_for: Callable[[Path], str] | None = None,
) -> str:
    key = proxy_thread_key(Path(path))
    if key in (getattr(owner, "_proxy_threads", {}) or {}):
        return BUILDING_PROXY_STATE
    state_for = state_for or _default_proxy_state_for
    return str(state_for(Path(path)))


def proxy_label_for_status(status: str, *, proxy_mode: bool) -> str:
    if status == BUILDING_PROXY_STATE:
        return "Building"
    if status == "ready":
        return "Active" if proxy_mode else "Ready"
    if status == "stale":
        return "Stale"
    return NO_PROXY_SOURCE_TEXT


def media_pool_proxy_state(core_state: str | None) -> str:
    """Map core proxy state to Media Pool storage convention.

    Media Pool uses ``""`` for "missing" so its existing filters and
    metadata labels continue to work. ``ready`` and ``stale`` are stored
    verbatim.
    """

    state = str(core_state or "")
    if state == "missing":
        return MEDIA_POOL_MISSING_PROXY_STATE
    if state in {"ready", "stale"}:
        return state
    return MEDIA_POOL_MISSING_PROXY_STATE


def core_proxy_state_from_media_pool_state(pool_state: str | None) -> str:
    state = str(pool_state or "")
    return "missing" if state == MEDIA_POOL_MISSING_PROXY_STATE else state


def _settings_preview_mapping(owner: Any) -> dict:
    settings = getattr(owner, "_project_settings", {}) or {}
    preview = settings.get("preview") if isinstance(settings, dict) else None
    return preview if isinstance(preview, dict) else {}


def auto_proxy_generation_enabled(owner: Any) -> bool:
    env = os.environ.get("TIGERCAPTURE_DISABLE_AUTO_PROXY_GENERATION", "").strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return False
    preview = _settings_preview_mapping(owner)
    if "auto_proxy" in preview:
        return bool(preview.get("auto_proxy"))
    settings = getattr(owner, "_project_settings", {}) or {}
    if isinstance(settings, dict) and "auto_proxy" in settings:
        return bool(settings.get("auto_proxy"))
    return True


def source_preview_proxy_policy(
    source: Path,
    *,
    quality_mode: str = "auto",
    requested_preview_height: int | None = None,
) -> dict[str, Any]:
    from app.preview_performance_policy import preview_performance_policy_from_probe
    from app.video_editor_media_proxy import _probe_video_metadata

    return preview_performance_policy_from_probe(
        _probe_video_metadata(Path(source)),
        path=source,
        requested_preview_height=requested_preview_height,
        quality_mode=quality_mode,
    )


def _source_paths_for_auto_proxy(owner: Any) -> list[Path]:
    seen: set[str] = set()
    paths: list[Path] = []
    for item in iter_proxy_owners(getattr(owner, "_tracks", []) or []):
        source = owner_original_source(item)
        if source is None:
            continue
        try:
            key = str(Path(source).resolve()).casefold()
        except Exception:
            key = str(Path(source)).casefold()
        if key in seen:
            continue
        seen.add(key)
        paths.append(Path(source))
    return paths


def auto_proxy_candidates(
    owner: Any,
    *,
    paths: list[Path] | None = None,
    policy_for: Callable[[Path], dict[str, Any]] | None = None,
    state_for: Callable[[Path], str] | None = None,
) -> list[dict[str, Any]]:
    if not auto_proxy_generation_enabled(owner):
        return []
    preview = _settings_preview_mapping(owner)
    quality_mode = str(preview.get("quality_mode") or preview.get("mode") or "auto")
    requested_height = preview.get("decode_height", preview.get("height", None))
    try:
        requested_preview_height = None if requested_height in (None, "") else int(requested_height)
    except Exception:
        requested_preview_height = None
    state_for = state_for or _default_proxy_state_for
    if policy_for is None:
        policy_for = lambda p: source_preview_proxy_policy(
            p,
            quality_mode=quality_mode,
            requested_preview_height=requested_preview_height,
        )
    rows: list[dict[str, Any]] = []
    for source in paths if paths is not None else _source_paths_for_auto_proxy(owner):
        source = Path(source)
        try:
            if not source.exists() or source.suffix.lower() not in {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}:
                continue
        except Exception:
            continue
        state = str(state_for(source))
        if state not in {"missing", "stale"}:
            continue
        try:
            policy = dict(policy_for(source) or {})
        except Exception:
            policy = {}
        if not bool(policy.get("needs_proxy")):
            continue
        rows.append({
            "source": source,
            "state": state,
            "force": state == "stale",
            "policy": policy,
        })
    return rows


def proxy_status_ui_state(
    source: Path | None,
    *,
    status: str = "missing",
    proxy: Path | None = None,
    proxy_mode: bool = False,
    proxy_exists: bool = False,
) -> ProxyStatusUi:
    if source is None:
        return ProxyStatusUi(
            text=NO_PROXY_SOURCE_TEXT,
            tooltip=NO_PROXY_SOURCE_TOOLTIP,
            manage_enabled=False,
            refresh_enabled=False,
            delete_enabled=False,
            busy=False,
        )

    source = Path(source)
    proxy = Path(proxy) if proxy is not None else _default_proxy_path_for(source)
    busy = status == BUILDING_PROXY_STATE
    return ProxyStatusUi(
        text=proxy_label_for_status(status, proxy_mode=proxy_mode),
        tooltip=f"Source: {source}\nProxy: {proxy}\nState: {status}",
        manage_enabled=True,
        refresh_enabled=not busy,
        delete_enabled=bool(proxy_exists) and not busy,
        busy=busy,
    )


def _set_enabled(widget: Any, enabled: bool) -> None:
    if widget is None:
        return
    set_enabled = getattr(widget, "setEnabled", None)
    if callable(set_enabled):
        set_enabled(bool(enabled))


def _set_text(widget: Any, text: str) -> None:
    set_text = getattr(widget, "setText", None)
    if callable(set_text):
        set_text(text)


def _set_tooltip(widget: Any, tooltip: str) -> None:
    set_tooltip = getattr(widget, "setToolTip", None)
    if callable(set_tooltip):
        set_tooltip(tooltip)


def refresh_proxy_status_ui(
    owner: Any,
    *,
    active_source: Path | None | object = _UNSET,
    path_for: Callable[[Path], Path] | None = None,
    state_for: Callable[[Path], str] | None = None,
    status_for: Callable[[Any, Path], str] | None = None,
) -> ProxyStatusUi | None:
    label = getattr(owner, "proxy_status_label", None)
    if label is None:
        return None

    source = active_proxy_source_path(owner) if active_source is _UNSET else active_source
    manage_btn = getattr(owner, "proxy_manage_btn", None)
    refresh_action = getattr(owner, "proxy_refresh_action", None)
    delete_action = getattr(owner, "proxy_delete_action", None)
    if source is None:
        ui = proxy_status_ui_state(None)
    else:
        source = Path(source)
        path_for = path_for or _default_proxy_path_for
        status = status_for(owner, source) if status_for is not None else proxy_status_for_path(
            owner,
            source,
            state_for=state_for,
        )
        proxy = Path(path_for(source))
        try:
            proxy_exists = proxy.exists()
        except Exception:
            proxy_exists = False
        ui = proxy_status_ui_state(
            source,
            status=status,
            proxy=proxy,
            proxy_mode=bool(getattr(owner, "_proxy_mode", False)),
            proxy_exists=proxy_exists,
        )

    _set_text(label, ui.text)
    _set_tooltip(label, ui.tooltip)
    _set_enabled(manage_btn, ui.manage_enabled)
    _set_enabled(refresh_action, ui.refresh_enabled)
    _set_enabled(delete_action, ui.delete_enabled)
    return ui


def _refresh_player_tracks(owner: Any) -> None:
    refresh = getattr(owner, "_refresh_player_tracks", None)
    if callable(refresh):
        refresh()


def _update_track_rows(owner: Any) -> None:
    for row in (getattr(owner, "_track_rows", {}) or {}).values():
        update = getattr(row, "update", None)
        if callable(update):
            update()


def toggle_proxy_mode(
    owner: Any,
    checked: bool,
    *,
    apply_owner: Callable[[Any, bool], None] | None = None,
    refresh_ui: Callable[[Any], Any] | None = refresh_proxy_status_ui,
) -> None:
    setattr(owner, "_proxy_mode", bool(checked))
    apply_owner = apply_owner or apply_proxy_owner
    for track in getattr(owner, "_tracks", []) or []:
        apply_owner(track, bool(checked))
        for clip in getattr(track, "clips", []) or []:
            apply_owner(clip, bool(checked))
    _refresh_player_tracks(owner)
    _update_track_rows(owner)
    if callable(refresh_ui):
        refresh_ui(owner)


def _connect(signal: Any, handler: Callable[..., Any]) -> None:
    connect = getattr(signal, "connect", None)
    if callable(connect):
        connect(handler)


def _make_thread(thread_factory: Callable[..., Any], source: Path, force: bool, owner: Any) -> Any:
    try:
        return thread_factory(source, force=force, parent=owner)
    except TypeError:
        return thread_factory(source, force=force)


def start_proxy_generation(
    owner: Any,
    path: Path,
    *,
    force: bool = False,
    thread_factory: Callable[..., Any] | None = None,
    state_for: Callable[[Path], str] | None = None,
    refresh_ui: Callable[[Any], Any] | None = refresh_proxy_status_ui,
) -> bool:
    """Start a proxy generation thread if one is needed.

    The thread object only needs ``done``, ``failed``, ``progress``, and
    ``finished`` signal-like attributes with ``connect`` methods plus a
    ``start`` method. This keeps QThread and ffmpeg out of controller tests.
    """

    source = Path(path)
    key = proxy_thread_key(source)
    threads = getattr(owner, "_proxy_threads", None)
    if threads is None:
        threads = {}
        setattr(owner, "_proxy_threads", threads)
    if key in threads:
        return False

    state_for = state_for or _default_proxy_state_for
    if not force and state_for(source) == "ready":
        if callable(refresh_ui):
            refresh_ui(owner)
        return False

    thread_factory = thread_factory or _default_thread_factory
    thread = _make_thread(thread_factory, source, bool(force), owner)

    done_handler = getattr(owner, "_on_proxy_done", None)
    if not callable(done_handler):
        done_handler = lambda original_path, proxy_path: on_proxy_done(owner, original_path, proxy_path)
    failed_handler = getattr(owner, "_on_proxy_failed", None)
    if not callable(failed_handler):
        failed_handler = lambda original_path, reason: on_proxy_failed(owner, original_path, reason)

    _connect(getattr(thread, "done", None), done_handler)
    _connect(getattr(thread, "failed", None), failed_handler)
    _connect(
        getattr(thread, "progress", None),
        lambda _value: refresh_ui(owner) if callable(refresh_ui) else None,
    )

    def _finished() -> None:
        threads.pop(key, None)
        if callable(refresh_ui):
            refresh_ui(owner)

    _connect(getattr(thread, "finished", None), _finished)
    threads[key] = thread
    if callable(refresh_ui):
        refresh_ui(owner)
    start = getattr(thread, "start", None)
    if callable(start):
        start()
    return True


def queue_auto_proxy_generation(
    owner: Any,
    *,
    paths: list[Path] | None = None,
    start_generation: Callable[..., bool] | None = start_proxy_generation,
    policy_for: Callable[[Path], dict[str, Any]] | None = None,
    state_for: Callable[[Path], str] | None = None,
    max_jobs: int = 2,
) -> int:
    start_generation = start_generation or start_proxy_generation
    started = 0
    rows = auto_proxy_candidates(
        owner,
        paths=paths,
        policy_for=policy_for,
        state_for=state_for,
    )
    for row in rows[:max(0, int(max_jobs))]:
        source = Path(row["source"])
        if start_generation(owner, source, force=bool(row.get("force", False))):
            started += 1
    if started:
        try:
            status_bar = getattr(owner, "statusBar", None)
            bar = status_bar() if callable(status_bar) else None
            show = getattr(bar, "showMessage", None)
            if callable(show):
                show(f"Auto proxy generation queued: {started}", 3500)
        except Exception:
            pass
    return started


def _refresh_media_pool_proxy_statuses(owner: Any) -> None:
    pool = getattr(owner, "_media_pool", None)
    refresh = getattr(pool, "refresh_proxy_statuses", None)
    if callable(refresh):
        refresh()


def apply_completed_proxy_to_owners(owner: Any, original_path: Path, proxy_path: Path) -> int:
    original = Path(original_path)
    proxy = Path(proxy_path)
    applied = 0
    for item in iter_proxy_owners(getattr(owner, "_tracks", []) or []):
        if owner_original_source(item) == original:
            setattr(item, "_original_source_path", original)
            item.source_path = proxy
            applied += 1
    return applied


def on_proxy_done(
    owner: Any,
    original_path: str,
    proxy_path: str,
    *,
    refresh_ui: Callable[[Any], Any] | None = refresh_proxy_status_ui,
) -> int:
    applied = 0
    if bool(getattr(owner, "_proxy_mode", False)):
        applied = apply_completed_proxy_to_owners(owner, Path(original_path), Path(proxy_path))
        _refresh_player_tracks(owner)
        _update_track_rows(owner)
    _refresh_media_pool_proxy_statuses(owner)
    if callable(refresh_ui):
        refresh_ui(owner)
    return applied


def on_proxy_failed(
    owner: Any,
    original_path: str,
    reason: str,
    *,
    refresh_ui: Callable[[Any], Any] | None = refresh_proxy_status_ui,
) -> None:
    del original_path
    try:
        status_bar = getattr(owner, "statusBar", None)
        bar = status_bar() if callable(status_bar) else None
        show = getattr(bar, "showMessage", None)
        if callable(show):
            show(f"Proxy generation failed: {reason}", 5000)
    except Exception:
        pass
    if callable(refresh_ui):
        refresh_ui(owner)


def regenerate_proxy_for_active_source(
    owner: Any,
    *,
    active_source_path: Callable[[Any], Path | None] | None = active_proxy_source_path,
    start_generation: Callable[..., bool] | None = start_proxy_generation,
) -> bool:
    source = active_source_path(owner) if callable(active_source_path) else None
    if source is None:
        return False
    start_generation = start_generation or start_proxy_generation
    return bool(start_generation(owner, source, force=True))


@contextmanager
def _temporarily_block_signals(widget: Any) -> Iterator[None]:
    block_signals = getattr(widget, "blockSignals", None)
    old = False
    did_block = False
    if callable(block_signals):
        try:
            old = bool(block_signals(True))
            did_block = True
        except Exception:
            did_block = False
    try:
        yield
    finally:
        if did_block:
            try:
                block_signals(old)
            except Exception:
                pass


def delete_proxy_for_active_source(
    owner: Any,
    *,
    active_source_path: Callable[[Any], Path | None] | None = active_proxy_source_path,
    delete_proxy: Callable[[Path], bool] | None = None,
    toggle_mode: Callable[[Any, bool], Any] | None = toggle_proxy_mode,
    refresh_ui: Callable[[Any], Any] | None = refresh_proxy_status_ui,
    block_signals: Callable[[Any], Any] | None = None,
) -> bool:
    source = active_source_path(owner) if callable(active_source_path) else None
    if source is None:
        return False

    if bool(getattr(owner, "_proxy_mode", False)):
        btn = getattr(owner, "proxy_btn", None)
        if btn is not None:
            signal_blocker = block_signals(btn) if callable(block_signals) else _temporarily_block_signals(btn)
            with signal_blocker:
                set_checked = getattr(btn, "setChecked", None)
                if callable(set_checked):
                    set_checked(False)
        if callable(toggle_mode):
            toggle_mode(owner, False)

    delete_proxy = delete_proxy or _default_delete_proxy_for_source
    deleted = bool(delete_proxy(Path(source)))
    _refresh_media_pool_proxy_statuses(owner)
    if callable(refresh_ui):
        refresh_ui(owner)
    return deleted
