"""UI popout action adapter mixin.

This keeps unattended window control out of the central registry and the large
editor adapter while still exposing a stable action surface for QA/MCP callers.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class _PopoutSpec:
    target: str
    attr: str
    opener: str
    owner_attr: str = ""
    aliases: tuple[str, ...] = ()


_POPOUT_SPECS: tuple[_PopoutSpec, ...] = (
    _PopoutSpec("preview", "_preview_popout", "_toggle_preview_popout", aliases=("viewer",)),
    _PopoutSpec("timeline", "_timeline_popout", "_toggle_timeline_popout"),
    _PopoutSpec("media_pool", "_media_pool_popout", "_toggle_media_pool_popout", aliases=("media",)),
    _PopoutSpec("workbench", "_workbench_popout", "_toggle_workbench_popout"),
    _PopoutSpec("color", "_color_popout", "_toggle_color_popout", aliases=("color_grading",)),
    _PopoutSpec("subtitle", "_subtitle_popout", "_toggle_subtitle_popout", aliases=("subtitles",)),
    _PopoutSpec("node_graph", "_node_graph_popout", "_toggle_node_graph_popout", "_workbench_panel", ("node",)),
    _PopoutSpec("ai_command", "_ai_command_popout", "_toggle_ai_command_popout", aliases=("ai", "command")),
    _PopoutSpec("vtuber_studio", "_vtuber_studio_window", "_open_vtuber_broadcast_studio", aliases=("vtuber",)),
    _PopoutSpec("actor_library", "_actor_library_popout", "_toggle_actor_library_popout", aliases=("actors",)),
    _PopoutSpec("effects_library", "_effects_library_popout", "_toggle_effects_library_popout", aliases=("effects", "effect_library")),
    _PopoutSpec("title_presets", "_title_presets_popout", "_toggle_title_presets_popout", aliases=("titles",)),
    _PopoutSpec("transitions", "_transitions_popout", "_toggle_transitions_popout", aliases=("transition_presets",)),
    _PopoutSpec("workflow_presets", "_workflow_presets_popout", "_toggle_workflow_presets_popout", aliases=("workflows",)),
    _PopoutSpec("creator_assist", "_creator_assist_popout", "_toggle_creator_assist_popout", aliases=("creator",)),
    _PopoutSpec("script_edit", "_script_edit_popout", "_toggle_script_edit_popout", aliases=("ai_script_edit", "script")),
    _PopoutSpec("render_queue", "_render_queue_popout", "_toggle_render_queue_popout", aliases=("render", "queue")),
    _PopoutSpec("audio_workspace", "_audio_workspace_popout", "_toggle_audio_workspace_popout", aliases=("audio",)),
    _PopoutSpec("pip", "_pip_popout", "_toggle_pip_popout", aliases=("picture_in_picture",)),
    _PopoutSpec("audio_mixer", "_popout_win", "_toggle_popout", "_audio_mixer_panel", ("mixer", "scopes")),
)

_ALIASES: dict[str, _PopoutSpec] = {}
for _spec in _POPOUT_SPECS:
    _ALIASES[_spec.target] = _spec
    for _alias in _spec.aliases:
        _ALIASES[_alias] = _spec


def _norm_target(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return text


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _norm_compare_mode(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"", "off", "none", "normal", "disable", "disabled", "false", "0"}:
        return ""
    if text in {"before", "original", "source", "raw"}:
        return "before"
    if text in {"split", "wipe", "before_after", "before_after_split", "original_after"}:
        return "split"
    raise RuntimeError(f"unknown viewer compare mode: {value!r}")


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _process_events() -> None:
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.processEvents()
    except Exception:
        pass


def _widget_geometry(widget: Any) -> dict[str, int]:
    return _geometry(widget)


def _is_visible(widget: Any) -> bool:
    method = getattr(widget, "isVisible", None)
    if callable(method):
        try:
            return bool(method())
        except Exception:
            return False
    return widget is not None


def _safe_widget_bool(widget: Any, name: str) -> bool:
    method = getattr(widget, name, None)
    if not callable(method):
        return False
    try:
        return bool(method())
    except Exception:
        return False


def _safe_widget_text(widget: Any, name: str) -> str:
    method = getattr(widget, name, None)
    try:
        value = method() if callable(method) else getattr(widget, name, "")
    except Exception:
        value = ""
    return str(value or "")


def _qapplication_top_level_state() -> list[dict[str, Any]]:
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        widgets = list(app.topLevelWidgets() or []) if app is not None else []
    except Exception:
        widgets = []
    rows: list[dict[str, Any]] = []
    for widget in widgets:
        rows.append(
            {
                "id": id(widget),
                "type": type(widget).__name__,
                "object_name": _safe_widget_text(widget, "objectName"),
                "window_title": _safe_widget_text(widget, "windowTitle"),
                "visible": _is_visible(widget),
                "minimized": _safe_widget_bool(widget, "isMinimized"),
                "active": _safe_widget_bool(widget, "isActiveWindow"),
                "geometry": _widget_geometry(widget),
            }
        )
    return rows


def _count_media_pool_items(owner: Any) -> int:
    pool = getattr(owner, "_media_pool", None)
    view = getattr(pool, "_list", None)
    count = getattr(view, "count", None)
    if callable(count):
        try:
            return int(count())
        except Exception:
            return 0
    return 0


def _timeline_drop_target(owner: Any) -> Any:
    scroll = getattr(owner, "_tracks_scroll", None)
    viewport = getattr(scroll, "viewport", None)
    if callable(viewport):
        try:
            target = viewport()
            if target is not None:
                return target
        except Exception:
            pass
    target = getattr(owner, "_tracks_host", None)
    if target is not None:
        return target
    raise RuntimeError("timeline drop surface is not available")


def _editor_window_state(owner: Any) -> dict[str, Any]:
    tracks = list(getattr(owner, "_tracks", []) or [])
    audio_tracks = list(getattr(owner, "_audio_tracks", []) or [])
    top_level_windows = _qapplication_top_level_state()
    player = getattr(owner, "_player", None)
    position = getattr(player, "position", None)
    try:
        position_ms = int(position()) if callable(position) else 0
    except Exception:
        position_ms = 0
    project_settings = getattr(owner, "_project_settings", None)
    if not isinstance(project_settings, dict):
        project_settings = {}
    state = {
        "owner_id": id(owner),
        "owner_type": type(owner).__name__,
        "object_name": _safe_widget_text(owner, "objectName"),
        "window_title": _safe_widget_text(owner, "windowTitle"),
        "visible": _is_visible(owner),
        "hidden": _safe_widget_bool(owner, "isHidden"),
        "minimized": _safe_widget_bool(owner, "isMinimized"),
        "active": _safe_widget_bool(owner, "isActiveWindow"),
        "geometry": _widget_geometry(owner),
        "top_level_count": len(top_level_windows),
        "visible_top_level_count": len([row for row in top_level_windows if row.get("visible")]),
        "top_level_windows": top_level_windows,
        "media_pool_count": _count_media_pool_items(owner),
        "video_track_count": len(tracks),
        "audio_track_count": len(audio_tracks),
        "active_track_id": getattr(owner, "_active_track_id", None),
        "player_position_ms": position_ms,
        "project_path": str(getattr(owner, "_current_project_path", "") or ""),
        "starter_template_id": str(project_settings.get("starter_template_id") or ""),
        "startup_template_id": str(getattr(owner, "_startup_template_id", "") or ""),
        "tracks_host": _surface_state(getattr(owner, "_tracks_host", None)),
        "tracks_viewport": _surface_state(_timeline_drop_target_or_none(owner)),
        "media_pool": _surface_state(getattr(owner, "_media_pool", None)),
        "preview": _surface_state(
            getattr(owner, "_preview_gl", None)
            or getattr(owner, "_preview_label", None)
            or getattr(owner, "_preview_host", None)
        ),
        "workbench": _surface_state(getattr(owner, "_workbench_panel", None)),
    }
    return state


def _timeline_drop_target_or_none(owner: Any) -> Any | None:
    try:
        return _timeline_drop_target(owner)
    except Exception:
        return None


def _surface_state(widget: Any) -> dict[str, Any]:
    if widget is None:
        return {"available": False, "id": 0, "type": "", "visible": False, "geometry": _geometry(None)}
    return {
        "available": True,
        "id": id(widget),
        "type": type(widget).__name__,
        "object_name": _safe_widget_text(widget, "objectName"),
        "visible": _is_visible(widget),
        "geometry": _widget_geometry(widget),
    }


def _window_state_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "owner_id",
        "owner_type",
        "object_name",
        "window_title",
        "visible",
        "hidden",
        "minimized",
        "geometry",
        "top_level_count",
        "visible_top_level_count",
        "project_path",
        "starter_template_id",
        "startup_template_id",
        "media_pool_count",
        "video_track_count",
        "audio_track_count",
        "active_track_id",
    )
    changed: dict[str, Any] = {}
    for key in keys:
        if before.get(key) != after.get(key):
            changed[key] = {"before": before.get(key), "after": after.get(key)}
    for key in ("tracks_host", "tracks_viewport", "media_pool", "preview", "workbench"):
        b = before.get(key) if isinstance(before.get(key), dict) else {}
        a = after.get(key) if isinstance(after.get(key), dict) else {}
        surface_changes = {
            name: {"before": b.get(name), "after": a.get(name)}
            for name in ("id", "type", "visible", "geometry")
            if b.get(name) != a.get(name)
        }
        if surface_changes:
            changed[key] = surface_changes
    return changed


def _geometry(widget: Any) -> dict[str, int]:
    if widget is None:
        return {"x": 0, "y": 0, "width": 0, "height": 0}
    raw = getattr(widget, "geometry", None)
    try:
        raw = raw() if callable(raw) else raw
    except Exception:
        raw = None
    if isinstance(raw, tuple) and len(raw) >= 4:
        return {"x": int(raw[0]), "y": int(raw[1]), "width": int(raw[2]), "height": int(raw[3])}
    result: dict[str, int] = {}
    for key in ("x", "y", "width", "height"):
        value = getattr(raw, key, None)
        try:
            result[key] = int(value() if callable(value) else value)
        except Exception:
            result[key] = 0
    return result


def _show_window(widget: Any, *, activate: bool) -> None:
    show = getattr(widget, "show", None)
    if callable(show):
        show()
    raise_ = getattr(widget, "raise_", None)
    if callable(raise_):
        raise_()
    if activate:
        activate_window = getattr(widget, "activateWindow", None)
        if callable(activate_window):
            activate_window()
    _process_events()


def _apply_geometry(widget: Any, *, x: Any = None, y: Any = None, width: Any = None, height: Any = None) -> dict[str, int]:
    gx = _int_or_none(x)
    gy = _int_or_none(y)
    gw = _int_or_none(width)
    gh = _int_or_none(height)
    current = _geometry(widget)
    if gx is None:
        gx = current["x"]
    if gy is None:
        gy = current["y"]
    if gw is None:
        gw = current["width"] or 320
    if gh is None:
        gh = current["height"] or 240
    gw = max(120, int(gw))
    gh = max(90, int(gh))
    set_geometry = getattr(widget, "setGeometry", None)
    if callable(set_geometry):
        set_geometry(int(gx), int(gy), gw, gh)
    else:
        if x is not None or y is not None:
            move = getattr(widget, "move", None)
            if callable(move):
                move(int(gx), int(gy))
        if width is not None or height is not None:
            resize = getattr(widget, "resize", None)
            if callable(resize):
                resize(gw, gh)
    _process_events()
    return _geometry(widget)


class UiAdapterMixin:
    """Action-facing helpers for detached editor windows."""

    def media_pool_drop_to_timeline(
        self,
        *,
        path: str,
        drop_x: int = 190,
        drop_y: int = 36,
        settle_ms: int = 300,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        media_path = Path(str(path or "")).expanduser()
        if not media_path.is_file():
            raise ValueError(f"media path does not exist: {media_path}")

        before = _editor_window_state(owner)
        pool = getattr(owner, "_media_pool", None)
        if pool is None:
            raise RuntimeError("media pool is not available")
        add_path = getattr(pool, "add_path", None)
        select_path = getattr(pool, "select_path", None)
        added = bool(add_path(media_path)) if callable(add_path) else False
        selected = bool(select_path(media_path)) if callable(select_path) else False

        item = None
        finder = getattr(pool, "_find_item_for_path", None)
        if callable(finder):
            try:
                item = finder(media_path)
            except Exception:
                item = None
        media_list = getattr(pool, "_list", None)
        mime_method = getattr(media_list, "mimeData", None)
        internal_mime_method = getattr(media_list, "_mime_data_for_items", None)
        if item is not None and callable(internal_mime_method):
            mime = internal_mime_method([item], include_file_urls=False)
        elif item is not None and callable(mime_method):
            mime = mime_method([item])
        else:
            from PySide6.QtCore import QMimeData

            from app.media_asset_routing import MEDIA_POOL_ITEM_MIME_TYPE

            mime = QMimeData()
            mime.setData(MEDIA_POOL_ITEM_MIME_TYPE, str(media_path.resolve()).encode("utf-8"))

        target = _timeline_drop_target(owner)
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        from PySide6.QtWidgets import QApplication

        x = max(0, int(drop_x or 0))
        y = max(0, int(drop_y or 0))
        point = QPointF(float(x), float(y))
        drag = QDragEnterEvent(
            point.toPoint(),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(target, drag)
        _process_events()
        drop = QDropEvent(
            point,
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(target, drop)
        deadline = time.monotonic() + max(0, int(settle_ms or 0)) / 1000.0
        while time.monotonic() < deadline:
            _process_events()
            time.sleep(0.02)
        _process_events()

        after = _editor_window_state(owner)
        changes = _window_state_changes(before, after)
        window_stable = bool(
            before.get("owner_id") == after.get("owner_id")
            and after.get("visible")
            and not after.get("hidden")
            and not after.get("minimized")
            and before.get("project_path") == after.get("project_path")
            and before.get("starter_template_id") == after.get("starter_template_id")
            and before.get("startup_template_id") == after.get("startup_template_id")
            and before.get("tracks_host", {}).get("id") == after.get("tracks_host", {}).get("id")
            and before.get("media_pool", {}).get("id") == after.get("media_pool", {}).get("id")
        )
        return {
            "schema": "tigerstudio.actions.media_pool_drop_to_timeline.v1",
            "path": str(media_path.resolve()),
            "pool_add_return": added,
            "pool_select_return": selected,
            "mime_formats": list(mime.formats()),
            "mime_has_urls": bool(mime.hasUrls()),
            "drop_target": _surface_state(target),
            "drag_enter_accepted": bool(drag.isAccepted()),
            "drop_accepted": bool(drop.isAccepted()),
            "window_stable": window_stable,
            "before_window": before,
            "after_window": after,
            "window_changes": changes,
        }

    def _viewer_compare_track(self, track_id: Any = None) -> Any:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if track_id not in (None, ""):
            wanted = int(track_id)
            finder = getattr(owner, "_find_track", None)
            if callable(finder):
                track = finder(wanted)
                if track is not None:
                    return track
            for track in getattr(owner, "_tracks", []) or []:
                try:
                    if int(getattr(track, "id", -1)) == wanted:
                        return track
                except Exception:
                    continue
            raise RuntimeError(f"video track not found: {wanted}")
        active = getattr(owner, "_active_track", None)
        if callable(active):
            track = active()
            if track is not None:
                return track
        active_id = getattr(owner, "_active_track_id", None)
        if active_id is not None:
            return self._viewer_compare_track(active_id)
        tracks = list(getattr(owner, "_tracks", []) or [])
        if tracks:
            return tracks[0]
        raise RuntimeError("no active video track")

    def set_viewer_compare(
        self,
        *,
        mode: Any = "",
        labels_enabled: Any = None,
        track_id: Any = None,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        track = self._viewer_compare_track(track_id)
        normalized = _norm_compare_mode(mode)
        setattr(track, "preview_color_compare_mode", normalized)
        if labels_enabled is not None:
            setattr(track, "preview_compare_labels_enabled", _bool(labels_enabled, True))
        elif not hasattr(track, "preview_compare_labels_enabled"):
            setattr(track, "preview_compare_labels_enabled", True)

        for method_name in ("_sync_color_compare_buttons", "_sync_viewer_compare_button"):
            method = getattr(owner, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception:
                    pass
        player = getattr(owner, "_player", None)
        if player is not None:
            for method_name in ("clear_preview_prerender_cache", "refresh_current_frame"):
                method = getattr(player, method_name, None)
                if callable(method):
                    try:
                        method()
                    except Exception:
                        pass
        canvas = getattr(owner, "_drawing_canvas", None)
        update = getattr(canvas, "update", None)
        if callable(update):
            try:
                update()
            except Exception:
                pass
        return {
            "schema": "tigerstudio.actions.viewer_compare_set.v1",
            "track_id": int(getattr(track, "id", 0) or 0),
            "mode": normalized,
            "labels_enabled": bool(getattr(track, "preview_compare_labels_enabled", True)),
        }

    def fit_viewer_preview(self) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        fit = getattr(owner, "_scale_preview_to_fit", None)
        if not callable(fit):
            raise RuntimeError("viewer fit method unavailable")
        fit()
        return {"schema": "tigerstudio.actions.viewer_fit.v1", "fit": True}

    def _ui_popout_spec(self, target: str | None = None, surface: str | None = None) -> _PopoutSpec:
        key = _norm_target(target or surface)
        spec = _ALIASES.get(key)
        if spec is None:
            choices = ", ".join(spec.target for spec in _POPOUT_SPECS)
            raise RuntimeError(f"unknown popout target: {target or surface!r}; expected one of: {choices}")
        return spec

    def _ui_popout_owner(self, spec: _PopoutSpec) -> Any:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if spec.owner_attr:
            nested = getattr(owner, spec.owner_attr, None)
            if nested is None:
                raise RuntimeError(f"popout owner unavailable: {spec.owner_attr}")
            return nested
        return owner

    def _ui_popout_window(self, spec: _PopoutSpec) -> Any:
        owner = self._ui_popout_owner(spec)
        return getattr(owner, spec.attr, None)

    def _ensure_ui_popout(
        self,
        target: str | None = None,
        surface: str | None = None,
        *,
        open_if_missing: bool = True,
        show: bool = True,
        activate: bool = False,
    ) -> tuple[_PopoutSpec, Any, bool]:
        spec = self._ui_popout_spec(target, surface)
        owner = self._ui_popout_owner(spec)
        window = getattr(owner, spec.attr, None)
        already_open = window is not None and _is_visible(window)
        if window is None and open_if_missing:
            opener = getattr(owner, spec.opener, None)
            if not callable(opener):
                raise RuntimeError(f"popout opener unavailable: {spec.opener}")
            opener()
            _process_events()
            window = getattr(owner, spec.attr, None)
        if window is None:
            raise RuntimeError(f"popout is not open: {spec.target}")
        if show:
            _show_window(window, activate=activate)
        return spec, window, already_open

    def list_ui_popouts(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for spec in _POPOUT_SPECS:
            available = False
            window = None
            try:
                owner = self._ui_popout_owner(spec)
                available = callable(getattr(owner, spec.opener, None)) or getattr(owner, spec.attr, None) is not None
                window = getattr(owner, spec.attr, None)
            except Exception:
                owner = None
            visible = bool(window is not None and _is_visible(window))
            rows.append(
                {
                    "target": spec.target,
                    "aliases": list(spec.aliases),
                    "available": bool(available),
                    "open": visible,
                    "visible": visible,
                    "owner_attr": spec.owner_attr,
                    "window_attr": spec.attr,
                    "geometry": _geometry(window) if window is not None else None,
                }
            )
        return {"schema": "tigerstudio.actions.ui_popout_list.v1", "targets": rows}

    def open_ui_popout(
        self,
        *,
        target: str = "",
        surface: str = "",
        x: Any = None,
        y: Any = None,
        width: Any = None,
        height: Any = None,
        show: Any = True,
        activate: Any = True,
    ) -> dict[str, Any]:
        spec, window, already_open = self._ensure_ui_popout(
            target,
            surface,
            open_if_missing=True,
            show=_bool(show, True),
            activate=_bool(activate, True),
        )
        if x is not None or y is not None or width is not None or height is not None:
            geom = _apply_geometry(window, x=x, y=y, width=width, height=height)
        else:
            geom = _geometry(window)
        return {
            "schema": "tigerstudio.actions.ui_popout_open.v1",
            "target": spec.target,
            "already_open": already_open,
            "visible": _is_visible(window),
            "geometry": geom,
        }

    def set_ui_popout_geometry(
        self,
        *,
        target: str = "",
        surface: str = "",
        x: Any = None,
        y: Any = None,
        width: Any = None,
        height: Any = None,
        open_if_missing: Any = True,
        show: Any = True,
        activate: Any = False,
    ) -> dict[str, Any]:
        spec, window, already_open = self._ensure_ui_popout(
            target,
            surface,
            open_if_missing=_bool(open_if_missing, True),
            show=_bool(show, True),
            activate=_bool(activate, False),
        )
        geom = _apply_geometry(window, x=x, y=y, width=width, height=height)
        return {
            "schema": "tigerstudio.actions.ui_popout_geometry.v1",
            "target": spec.target,
            "already_open": already_open,
            "visible": _is_visible(window),
            "geometry": geom,
        }

    def close_ui_popout(self, *, target: str = "", surface: str = "") -> dict[str, Any]:
        spec = self._ui_popout_spec(target, surface)
        window = self._ui_popout_window(spec)
        was_open = bool(window is not None and _is_visible(window))
        if window is not None:
            close = getattr(window, "close", None)
            if callable(close):
                close()
                _process_events()
        return {
            "schema": "tigerstudio.actions.ui_popout_close.v1",
            "target": spec.target,
            "was_open": was_open,
            "visible": bool(window is not None and _is_visible(window)),
        }

    def capture_ui_popout(
        self,
        *,
        path: str,
        target: str = "",
        surface: str = "",
        open_if_missing: Any = True,
        settle_ms: Any = 120,
        activate: Any = True,
    ) -> dict[str, Any]:
        spec, window, already_open = self._ensure_ui_popout(
            target,
            surface,
            open_if_missing=_bool(open_if_missing, True),
            show=True,
            activate=_bool(activate, True),
        )
        delay = max(0, min(2000, int(_int_or_none(settle_ms) or 0)))
        if delay:
            _process_events()
            time.sleep(delay / 1000.0)
            _process_events()
        grab = getattr(window, "grab", None)
        if not callable(grab):
            raise RuntimeError(f"popout cannot be captured: {spec.target}")
        out = Path(path).expanduser()
        if not out.is_absolute():
            out = Path.cwd() / out
        out.parent.mkdir(parents=True, exist_ok=True)
        pixmap = grab()
        save = getattr(pixmap, "save", None)
        if not callable(save):
            raise RuntimeError(f"popout grab did not return a savable image: {spec.target}")
        ok = bool(save(str(out)))
        if not ok:
            raise RuntimeError(f"failed to save popout capture: {out}")
        return {
            "schema": "tigerstudio.actions.ui_popout_capture.v1",
            "target": spec.target,
            "already_open": already_open,
            "visible": _is_visible(window),
            "path": str(out),
            "geometry": _geometry(window),
        }
