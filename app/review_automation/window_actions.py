from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MULTI_MONITOR_TEMPLATE = (
    ROOT.parent
    / "ReviewAutomationWorkspace"
    / "source_assets"
    / "templates"
    / "multi_monitor_catalog_template.png"
)
DEFAULT_MULTI_MONITOR_SCREEN_MAP = DEFAULT_MULTI_MONITOR_TEMPLATE.with_suffix(
    ".screen-map.json"
)


class ReviewWindowActionError(RuntimeError):
    """Raised only inside the review-only window action runner."""


@dataclass(frozen=True)
class PopoutSurface:
    attr: str
    toggle: str
    owner_attr: str = ""


POPOUT_SURFACES: dict[str, PopoutSurface] = {
    "viewer": PopoutSurface("_preview_popout", "_toggle_preview_popout"),
    "preview": PopoutSurface("_preview_popout", "_toggle_preview_popout"),
    "timeline": PopoutSurface("_timeline_popout", "_toggle_timeline_popout"),
    "media_pool": PopoutSurface("_media_pool_popout", "_toggle_media_pool_popout"),
    "media": PopoutSurface("_media_pool_popout", "_toggle_media_pool_popout"),
    "workbench": PopoutSurface("_workbench_popout", "_toggle_workbench_popout"),
    "color": PopoutSurface("_color_popout", "_toggle_color_popout"),
    "color_grading": PopoutSurface("_color_popout", "_toggle_color_popout"),
    "node": PopoutSurface("_node_graph_popout", "_toggle_node_graph_popout", "_workbench_panel"),
    "node_graph": PopoutSurface("_node_graph_popout", "_toggle_node_graph_popout", "_workbench_panel"),
}


def compose_multi_monitor_template(
    *,
    template_path: str | Path = DEFAULT_MULTI_MONITOR_TEMPLATE,
    screen_map_path: str | Path = DEFAULT_MULTI_MONITOR_SCREEN_MAP,
    slot_images: Mapping[str, str | Path],
    out_path: str | Path,
    strict: bool = True,
) -> dict[str, Any]:
    """Composite real slot captures into the review-only monitor template."""

    try:
        from PIL import Image, ImageOps
    except Exception as exc:  # pragma: no cover - Pillow is present in CI/runtime.
        raise ReviewWindowActionError("Pillow is required for multi-monitor composition") from exc

    template = Path(template_path)
    screen_map = Path(screen_map_path)
    out = Path(out_path)
    if not template.exists():
        raise ReviewWindowActionError(f"multi-monitor template not found: {template}")
    if not screen_map.exists():
        raise ReviewWindowActionError(f"multi-monitor screen map not found: {screen_map}")

    payload = json.loads(screen_map.read_text(encoding="utf-8"))
    regions = _iter_screen_regions(payload)
    canvas = Image.open(template).convert("RGB")
    pasted: list[dict[str, Any]] = []
    missing: list[str] = []
    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")

    for region in regions:
        region_id = str(region.get("id") or "").strip()
        rect = _screen_region_rect(region)
        quad = _screen_region_quad(region)
        if not region_id or (not rect and not quad):
            continue
        raw_image = slot_images.get(region_id)
        if not raw_image:
            missing.append(region_id)
            continue
        image_path = Path(raw_image)
        if not image_path.exists():
            missing.append(region_id)
            continue
        if rect:
            x = int(rect.get("x") or 0)
            y = int(rect.get("y") or 0)
            width = int(rect.get("width") or 0)
            height = int(rect.get("height") or 0)
        else:
            xs = [point[0] for point in quad or []]
            ys = [point[1] for point in quad or []]
            x = int(math.floor(min(xs)))
            y = int(math.floor(min(ys)))
            width = int(math.ceil(max(xs) - min(xs)))
            height = int(math.ceil(max(ys) - min(ys)))
        if width <= 0 or height <= 0:
            continue
        source = Image.open(image_path).convert("RGB")
        fit_mode = str(region.get("fit") or "cover").strip().lower()
        fitted = _fit_screen_capture(source, (width, height), fit_mode, resample=resample)
        if quad:
            _paste_perspective_region(canvas, fitted, quad, resample=resample)
            pasted_region: dict[str, Any] = {
                "rect": {"x": x, "y": y, "width": width, "height": height},
                "quad": [{"x": px, "y": py} for px, py in quad],
                "mapping": "perspective_quad",
            }
        else:
            canvas.paste(fitted, (x, y))
            pasted_region = {
                "rect": {"x": x, "y": y, "width": width, "height": height},
                "mapping": "rect",
            }
        pasted.append(
            {
                "id": region_id,
                "source": str(image_path),
                "fit": fit_mode,
                **pasted_region,
            }
        )

    if strict and missing:
        raise ReviewWindowActionError(f"missing multi-monitor slot captures: {', '.join(missing)}")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return {
        "path": str(out.resolve()),
        "template": str(template),
        "screen_map": str(screen_map),
        "pasted": pasted,
        "missing": missing,
    }


def _fit_screen_capture(
    source: Any,
    size: tuple[int, int],
    fit_mode: str,
    *,
    resample: Any,
) -> Any:
    from PIL import Image, ImageOps

    width, height = size
    if fit_mode in {"contain", "fit", "inside"}:
        fitted = ImageOps.contain(source, size, method=resample)
        canvas = Image.new("RGB", size, (8, 10, 13))
        canvas.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
        return canvas
    if fit_mode in {"stretch", "fill"}:
        return source.resize(size, resample=resample)
    return ImageOps.fit(source, size, method=resample, centering=(0.5, 0.5))


def _iter_screen_regions(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw_regions = payload.get("screen_regions")
    if isinstance(raw_regions, list):
        return [region for region in raw_regions if isinstance(region, Mapping)]

    regions = payload.get("regions")
    if isinstance(regions, Mapping):
        normalized: list[Mapping[str, Any]] = []
        for region_id, region in regions.items():
            if not isinstance(region, Mapping):
                continue
            item = dict(region)
            item.setdefault("id", str(region_id))
            normalized.append(item)
        return normalized

    return []


def _screen_region_rect(region: Mapping[str, Any]) -> Mapping[str, Any]:
    rect = region.get("rect")
    if isinstance(rect, Mapping):
        return rect
    if all(key in region for key in ("x", "y", "width", "height")):
        return {
            "x": region.get("x"),
            "y": region.get("y"),
            "width": region.get("width"),
            "height": region.get("height"),
        }
    return {}


def _screen_region_quad(region: Mapping[str, Any]) -> list[tuple[float, float]]:
    raw_quad = region.get("quad") or region.get("points") or region.get("corners")
    if not isinstance(raw_quad, Sequence) or isinstance(raw_quad, (str, bytes)) or len(raw_quad) != 4:
        return []
    quad: list[tuple[float, float]] = []
    for point in raw_quad:
        if isinstance(point, Mapping):
            x = point.get("x")
            y = point.get("y")
        elif isinstance(point, Sequence) and not isinstance(point, (str, bytes)) and len(point) >= 2:
            x = point[0]
            y = point[1]
        else:
            return []
        try:
            quad.append((float(x), float(y)))
        except (TypeError, ValueError):
            return []
    return quad


def _paste_perspective_region(
    canvas: Any,
    source: Any,
    quad: Sequence[tuple[float, float]],
    *,
    resample: Any,
) -> None:
    from PIL import Image

    source_rgba = source.convert("RGBA")
    width, height = source_rgba.size
    source_rect = [(0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height))]
    coeffs = _perspective_coefficients(quad, source_rect)
    transform_mode = getattr(getattr(Image, "Transform", Image), "PERSPECTIVE")
    warp_resample = getattr(getattr(Image, "Resampling", Image), "BICUBIC")
    warped = source_rgba.transform(canvas.size, transform_mode, coeffs, resample=warp_resample)
    mask = Image.new("L", source_rgba.size, 255).transform(canvas.size, transform_mode, coeffs, resample=warp_resample)
    canvas.paste(warped.convert("RGB"), (0, 0), mask)


def _perspective_coefficients(
    destination_points: Sequence[tuple[float, float]],
    source_points: Sequence[tuple[float, float]],
) -> tuple[float, ...]:
    """Return Pillow perspective coefficients for destination-to-source mapping."""

    matrix: list[list[float]] = []
    values: list[float] = []
    for (x, y), (u, v) in zip(destination_points, source_points):
        matrix.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
        values.append(u)
        matrix.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
        values.append(v)
    return tuple(_solve_linear_system(matrix, values))


def _solve_linear_system(matrix: list[list[float]], values: list[float]) -> list[float]:
    size = len(values)
    augmented = [row[:] + [values[index]] for index, row in enumerate(matrix)]
    for pivot_index in range(size):
        pivot_row = max(range(pivot_index, size), key=lambda row: abs(augmented[row][pivot_index]))
        if abs(augmented[pivot_row][pivot_index]) < 1e-9:
            raise ReviewWindowActionError("invalid perspective screen map quad")
        if pivot_row != pivot_index:
            augmented[pivot_index], augmented[pivot_row] = augmented[pivot_row], augmented[pivot_index]
        pivot = augmented[pivot_index][pivot_index]
        for col in range(pivot_index, size + 1):
            augmented[pivot_index][col] /= pivot
        for row in range(size):
            if row == pivot_index:
                continue
            factor = augmented[row][pivot_index]
            if factor == 0:
                continue
            for col in range(pivot_index, size + 1):
                augmented[row][col] -= factor * augmented[pivot_index][col]
    return [augmented[row][size] for row in range(size)]


class ReviewWindowActionRunner:
    """Review-only UI/window action runner.

    This is intentionally not registered in the main Python Action System. It is
    for evidence capture orchestration where windows may be shown, moved, hidden,
    and captured in a staged order for PPT/HTML review assets.
    """

    def __init__(
        self,
        owner: Any,
        *,
        root: str | Path = ROOT,
        output_dir: str | Path | None = None,
    ) -> None:
        self.owner = owner
        self.root = Path(root)
        self.output_dir = Path(output_dir) if output_dir is not None else self.root / "debugCapture" / "review_window_actions"

    def execute(self, action: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        action_id = str(action or "").strip()
        options = dict(params or {})
        try:
            if action_id == "review.ui.popout.open":
                result = self._open_popout(options)
            elif action_id == "review.ui.popout.close":
                result = self._close_popout(options)
            elif action_id == "review.ui.window.open":
                result = self._open_window(options)
            elif action_id == "review.ar_pbr.preview.view.get":
                result = self._get_ar_pbr_preview_view()
            elif action_id == "review.ar_pbr.preview.view.set":
                result = self._set_ar_pbr_preview_view(options)
            elif action_id == "review.ar_pbr.preview.settings.set":
                result = self._set_ar_pbr_preview_settings(options)
            elif action_id == "review.ui.window.set_geometry":
                result = self._set_window_geometry(options)
            elif action_id == "review.ui.window.visibility":
                result = self._set_window_visibility(options)
            elif action_id == "review.capture.window":
                result = self._capture_window(options)
            elif action_id == "review.capture.screen_region":
                result = self._capture_screen_region(options)
            elif action_id == "review.multi_monitor.compose":
                result = self._compose_multi_monitor(options)
            elif action_id == "review.multi_monitor.capture_slots":
                result = self._capture_multi_monitor_slots(options)
            else:
                raise ReviewWindowActionError(f"unknown review window action: {action_id}")
            return {"ok": True, "action": action_id, "review_only": True, "result": result}
        except Exception as exc:
            return {
                "ok": False,
                "action": action_id,
                "review_only": True,
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    def execute_sequence(self, steps: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        failed_index = -1
        for index, step in enumerate(steps):
            if not isinstance(step, Mapping):
                result = {
                    "ok": False,
                    "action": "",
                    "review_only": True,
                    "error": f"invalid step at index {index}",
                }
            else:
                result = self.execute(str(step.get("action") or ""), step.get("params") if isinstance(step.get("params"), Mapping) else {})
            results.append({"index": index, **result})
            if not result.get("ok"):
                failed_index = index
                break
        return {
            "ok": failed_index < 0,
            "review_only": True,
            "failed_index": failed_index,
            "results": results,
        }

    def _open_popout(self, params: Mapping[str, Any]) -> dict[str, Any]:
        surface = _normal_surface(params.get("surface") or params.get("target") or params.get("window_id"))
        spec = self._surface_spec(surface)
        owner = self._surface_owner(spec)
        current = getattr(owner, spec.attr, None)
        already_open = current is not None and _is_visible(current)
        if not already_open:
            toggle = getattr(owner, spec.toggle, None)
            if not callable(toggle):
                raise ReviewWindowActionError(f"surface cannot be popped out: {surface}")
            toggle()
            _process_events()
            current = getattr(owner, spec.attr, None)
        if current is None:
            raise ReviewWindowActionError(f"popout window was not created: {surface}")
        if _as_bool(params.get("show"), True):
            self._show_for_capture(current, activate=_as_bool(params.get("activate"), True))
        return {"surface": surface, "window_id": surface, "already_open": already_open, "visible": _is_visible(current)}

    def _close_popout(self, params: Mapping[str, Any]) -> dict[str, Any]:
        surface = _normal_surface(params.get("surface") or params.get("target") or params.get("window_id"))
        spec = self._surface_spec(surface)
        owner = self._surface_owner(spec)
        current = getattr(owner, spec.attr, None)
        if current is None:
            return {"surface": surface, "closed": False, "reason": "not_open"}
        close = getattr(current, "close", None)
        if callable(close):
            close()
        else:
            toggle = getattr(owner, spec.toggle, None)
            if callable(toggle):
                toggle()
        _process_events()
        return {"surface": surface, "closed": True}

    def _open_window(self, params: Mapping[str, Any]) -> dict[str, Any]:
        target = _normal_surface(params.get("surface") or params.get("target") or params.get("window_id"))
        if target in POPOUT_SURFACES:
            return self._open_popout({"surface": target, **dict(params)})
        if target in {"ar_pbr_preview", "pbr_preview", "3d_preview", "3d_asset"}:
            return self._open_ar_pbr_preview_window(params)
        raise ReviewWindowActionError(f"unknown review window surface: {target}")

    def _open_ar_pbr_preview_window(self, params: Mapping[str, Any]) -> dict[str, Any]:
        asset_path = params.get("asset_path") or params.get("path") or params.get("target_path")
        track_id = str(params.get("track_id") or "").strip()
        track = self._find_ar_pbr_track(track_id)
        if track is not None:
            opener = getattr(self.owner, "_open_ar_pbr_track_model_view", None)
            if not callable(opener):
                raise ReviewWindowActionError("owner cannot open AR/PBR track model view")
            opener(track)
        else:
            if not asset_path:
                raise ReviewWindowActionError("asset_path or track_id is required for ar_pbr_preview")
            opener = getattr(self.owner, "_open_ar_pbr_asset_preview", None)
            if not callable(opener):
                raise ReviewWindowActionError("owner cannot open AR/PBR asset preview")
            opener(str(asset_path))
        _process_events()
        window = self._latest_ar_pbr_preview_window()
        if window is None:
            raise ReviewWindowActionError("AR/PBR preview window was not created")
        self._show_for_capture(window, activate=_as_bool(params.get("activate"), True))
        return {
            "surface": "ar_pbr_preview",
            "window_id": "ar_pbr_preview",
            "asset_path": str(asset_path or track.get("asset_path") if isinstance(track, Mapping) else asset_path or ""),
            "track_id": str(track.get("id") or "") if isinstance(track, Mapping) else track_id,
            "visible": _is_visible(window),
        }

    def _find_ar_pbr_track(self, track_id: str = "") -> Mapping[str, Any] | None:
        selected = track_id or str(getattr(self.owner, "_selected_ar_pbr_track_id", "") or "").strip()
        tracks = list(getattr(self.owner, "_ar_pbr_tracks", []) or [])
        if selected:
            for track in tracks:
                if isinstance(track, Mapping) and str(track.get("id") or "") == selected:
                    return track
        return None

    def _latest_ar_pbr_preview_window(self) -> Any | None:
        windows = list(getattr(self.owner, "_ar_pbr_preview_windows", []) or [])
        for window in reversed(windows):
            if window is not None:
                return window
        registry = getattr(self.owner, "_ar_pbr_preview_window_registry", None)
        if isinstance(registry, Mapping):
            for window in reversed(list(registry.values())):
                if window is not None:
                    return window
        return None

    @staticmethod
    def _coerce_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clamp_float(value: float, minimum: float, maximum: float) -> float:
        return max(float(minimum), min(float(maximum), float(value)))

    @staticmethod
    def _ar_pbr_state_payload(state: Any) -> dict[str, Any]:
        return {
            "pitch": float(getattr(state, "pitch", 0.0) or 0.0),
            "yaw": float(getattr(state, "yaw", 0.0) or 0.0),
            "roll": float(getattr(state, "roll", 0.0) or 0.0),
            "zoom": float(getattr(state, "zoom", 0.0) or 0.0),
            "camera_z": float(getattr(state, "camera_z", 0.0) or 0.0),
            "pan_x": float(getattr(state, "pan_x", 0.0) or 0.0),
            "pan_y": float(getattr(state, "pan_y", 0.0) or 0.0),
            "pan_z": float(getattr(state, "pan_z", 0.0) or 0.0),
        }

    def _get_ar_pbr_preview_view(self) -> dict[str, Any]:
        window = self._latest_ar_pbr_preview_window()
        if window is None:
            raise ReviewWindowActionError("AR/PBR preview window not found")
        gl_widget = getattr(window, "_gl_widget", None) or getattr(window, "gl_widget", None)
        state = getattr(window, "_state", None) or getattr(window, "state", None) or getattr(gl_widget, "state", None)
        if state is None:
            raise ReviewWindowActionError("AR/PBR preview state not ready")
        return {
            "surface": "ar_pbr_preview",
            "view": self._ar_pbr_state_payload(state),
        }

    def _set_ar_pbr_preview_view(self, params: Mapping[str, Any]) -> dict[str, Any]:
        window = self._latest_ar_pbr_preview_window()
        if window is None:
            raise ReviewWindowActionError("AR/PBR preview window not found")
        gl_widget = getattr(window, "_gl_widget", None) or getattr(window, "gl_widget", None)
        state = getattr(window, "_state", None) or getattr(window, "state", None) or getattr(gl_widget, "state", None)
        if state is None:
            raise ReviewWindowActionError("AR/PBR preview state not ready")

        before = self._ar_pbr_state_payload(state)
        if _as_bool(params.get("hide_environment_background"), False):
            setter = getattr(window, "_set_environment_background_visible", None)
            if callable(setter):
                setter(False, emit=False)
            elif gl_widget is not None and hasattr(gl_widget, "set_environment_background_visible"):
                gl_widget.set_environment_background_visible(False)

        if _as_bool(params.get("fit_first"), True):
            fit = getattr(window, "fit_view", None)
            if callable(fit):
                fit()
            elif gl_widget is not None and hasattr(gl_widget, "fit_current_view"):
                gl_widget.fit_current_view()
            for key in ("pan_x", "pan_y", "pan_z"):
                try:
                    setattr(state, key, 0.0)
                except Exception:
                    pass

        current_zoom = float(getattr(state, "zoom", before["zoom"]) or before["zoom"] or 1.0)
        zoom_factor = self._coerce_optional_float(params.get("zoom_factor"))
        if zoom_factor is not None:
            current_zoom *= self._clamp_float(zoom_factor, 0.01, 100.0)
        absolute_zoom = self._coerce_optional_float(params.get("zoom"))
        if absolute_zoom is not None:
            current_zoom = absolute_zoom
        state.zoom = self._clamp_float(current_zoom, 0.03, 40.0)

        for key, minimum, maximum in (
            ("camera_z", 0.2, 20.0),
            ("pitch", -180.0, 180.0),
            ("yaw", -360.0, 360.0),
            ("roll", -180.0, 180.0),
            ("pan_x", -20.0, 20.0),
            ("pan_y", -20.0, 20.0),
            ("pan_z", -20.0, 20.0),
        ):
            number = self._coerce_optional_float(params.get(key))
            if number is not None:
                setattr(state, key, self._clamp_float(number, minimum, maximum))

        if gl_widget is not None:
            for attr in ("auto_fit_enabled", "auto_fit_pending"):
                try:
                    setattr(gl_widget, attr, False)
                except Exception:
                    pass
            update = getattr(gl_widget, "update", None)
            if callable(update):
                update()
        sync = getattr(window, "sync_controls", None)
        if callable(sync):
            sync()
        self._show_for_capture(window, activate=_as_bool(params.get("activate", True), True))
        return {
            "surface": "ar_pbr_preview",
            "before": before,
            "after": self._ar_pbr_state_payload(state),
            "background_hidden": _as_bool(params.get("hide_environment_background"), False),
        }

    def _set_ar_pbr_preview_settings(self, params: Mapping[str, Any]) -> dict[str, Any]:
        window = self._latest_ar_pbr_preview_window()
        if window is None:
            raise ReviewWindowActionError("AR/PBR preview window not found")
        getter = getattr(window, "lighting_settings", None)
        applier = getattr(window, "apply_lighting_settings", None)
        if not callable(getter) or not callable(applier):
            raise ReviewWindowActionError("AR/PBR preview settings not available")

        before = dict(getter() or {})
        settings = {
            key: value
            for key, value in dict(params).items()
            if value is not None and key not in {"activate", "show", "target", "surface", "window_id"}
        }
        applier(settings, emit=True)
        self._show_for_capture(window, activate=_as_bool(params.get("activate", True), True))
        return {
            "surface": "ar_pbr_preview",
            "applied": sorted(settings.keys()),
            "before": before,
            "after": dict(getter() or {}),
        }

    def _set_window_geometry(self, params: Mapping[str, Any]) -> dict[str, Any]:
        target = str(params.get("target") or params.get("surface") or params.get("window_id") or "editor")
        window = self._window_for_target(target)
        x, y, width, height = self._geometry_from_params(params)
        setter = getattr(window, "setGeometry", None)
        if callable(setter):
            setter(int(x), int(y), int(width), int(height))
        else:
            mover = getattr(window, "move", None)
            resizer = getattr(window, "resize", None)
            if callable(mover):
                mover(int(x), int(y))
            if callable(resizer):
                resizer(int(width), int(height))
        if _as_bool(params.get("show"), True):
            self._show_for_capture(window, activate=_as_bool(params.get("activate"), False))
        _process_events()
        return {"target": target, "geometry": {"x": x, "y": y, "width": width, "height": height}}

    def _set_window_visibility(self, params: Mapping[str, Any]) -> dict[str, Any]:
        target = str(params.get("target") or params.get("surface") or params.get("window_id") or "editor")
        mode = str(params.get("mode") or params.get("visibility") or "show").strip().lower()
        window = self._window_for_target(target)
        if mode in {"show", "visible"}:
            self._show_for_capture(window, activate=_as_bool(params.get("activate"), False))
        elif mode == "hide":
            hide = getattr(window, "hide", None)
            if callable(hide):
                hide()
        elif mode in {"minimize", "minimized"}:
            minimize = getattr(window, "showMinimized", None)
            if callable(minimize):
                minimize()
        elif mode == "raise":
            raiser = getattr(window, "raise_", None)
            if callable(raiser):
                raiser()
        elif mode == "activate":
            self._show_for_capture(window, activate=True)
        else:
            raise ReviewWindowActionError(f"unknown visibility mode: {mode}")
        _process_events()
        return {"target": target, "mode": mode, "visible": _is_visible(window)}

    def _capture_window(self, params: Mapping[str, Any]) -> dict[str, Any]:
        target = str(params.get("target") or params.get("surface") or params.get("window_id") or "editor")
        if target == "screen":
            return self._capture_screen_region(params)
        window = self._window_for_target(target)
        strategy = str(params.get("visible_strategy") or "show_then_capture").strip().lower()
        if strategy != "grab_only":
            self._show_for_capture(window, activate=_as_bool(params.get("activate"), True))
            _process_events()
            _sleep_ms(int(params.get("settle_ms") or 120))
        out = Path(str(params.get("path") or self.output_dir / f"{_safe_name(target)}.png"))
        if not out.is_absolute():
            out = self.root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        grab = getattr(window, "grab", None)
        if not callable(grab):
            raise ReviewWindowActionError(f"target does not support QWidget.grab(): {target}")
        pixmap = grab()
        save = getattr(pixmap, "save", None)
        if not callable(save) or not save(str(out)):
            raise ReviewWindowActionError(f"failed to save window capture: {out}")
        return {
            "target": target,
            "path": str(out.resolve()),
            "visible_strategy": strategy,
            "method": "qt_widget_grab_after_show" if strategy != "grab_only" else "qt_widget_grab_only",
        }

    def _capture_screen_region(self, params: Mapping[str, Any]) -> dict[str, Any]:
        x, y, width, height = self._geometry_from_params(params)
        out = Path(str(params.get("path") or self.output_dir / "screen_region.png"))
        if not out.is_absolute():
            out = self.root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        _process_events()
        _sleep_ms(int(params.get("settle_ms") or 160))
        try:
            from PySide6.QtCore import QRect

            from app.capture import capture_region

            image = capture_region(QRect(int(x), int(y), int(width), int(height)), include_cursor=_as_bool(params.get("include_cursor"), False))
            image.save(out)
            method = "qt_screen_grab_window"
        except Exception:
            from PIL import ImageGrab

            image = ImageGrab.grab(bbox=(int(x), int(y), int(x + width), int(y + height)), all_screens=True)
            image.save(out)
            method = "pil_imagegrab_all_screens"
        return {"path": str(out.resolve()), "geometry": {"x": x, "y": y, "width": width, "height": height}, "method": method}

    def _compose_multi_monitor(self, params: Mapping[str, Any]) -> dict[str, Any]:
        slot_images = params.get("slot_images") or params.get("slots") or {}
        if not isinstance(slot_images, Mapping):
            raise ReviewWindowActionError("slot_images must be an object keyed by screen region id")
        out_path = params.get("out_path") or params.get("path") or self.output_dir / "multi_environment_review.png"
        return compose_multi_monitor_template(
            template_path=params.get("template_path") or DEFAULT_MULTI_MONITOR_TEMPLATE,
            screen_map_path=params.get("screen_map_path") or DEFAULT_MULTI_MONITOR_SCREEN_MAP,
            slot_images={str(key): Path(str(value)) for key, value in slot_images.items()},
            out_path=out_path,
            strict=_as_bool(params.get("strict"), True),
        )

    def _capture_multi_monitor_slots(self, params: Mapping[str, Any]) -> dict[str, Any]:
        slots = _slot_rows(params.get("slots"))
        if not slots:
            raise ReviewWindowActionError("slots are required")
        slot_images: dict[str, Path] = {}
        slot_results: list[dict[str, Any]] = []
        slot_dir = Path(str(params.get("slot_dir") or self.output_dir / "multi_monitor_slots"))
        if not slot_dir.is_absolute():
            slot_dir = self.root / slot_dir
        slot_dir.mkdir(parents=True, exist_ok=True)
        for slot in slots:
            slot_id = str(slot.get("id") or "").strip()
            if not slot_id:
                raise ReviewWindowActionError("slot id is required")
            prep = self._prepare_slot(slot)
            capture_params = dict(slot.get("capture") if isinstance(slot.get("capture"), Mapping) else {})
            capture_params.setdefault("target", slot.get("target") or "editor")
            capture_params.setdefault("path", slot.get("path") or slot_dir / f"{slot_id}.png")
            capture_params.setdefault("visible_strategy", "show_then_capture")
            capture = self._capture_window(capture_params)
            slot_images[slot_id] = Path(capture["path"])
            slot_results.append({"id": slot_id, "prepare": prep, "capture": capture})
            for target in list(slot.get("hide_after") or []):
                self._set_window_visibility({"target": target, "mode": "hide"})
        out_path = params.get("out_path") or params.get("path") or self.output_dir / "multi_environment_review.png"
        compose = compose_multi_monitor_template(
            template_path=params.get("template_path") or DEFAULT_MULTI_MONITOR_TEMPLATE,
            screen_map_path=params.get("screen_map_path") or DEFAULT_MULTI_MONITOR_SCREEN_MAP,
            slot_images=slot_images,
            out_path=out_path,
            strict=_as_bool(params.get("strict"), True),
        )
        return {"slots": slot_results, "slot_images": {key: str(value) for key, value in slot_images.items()}, "compose": compose}

    def _prepare_slot(self, slot: Mapping[str, Any]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for target in list(slot.get("hide") or []):
            results.append(self.execute("review.ui.window.visibility", {"target": target, "mode": "hide"}))
        for target in list(slot.get("show") or []):
            results.append(self.execute("review.ui.window.visibility", {"target": target, "mode": "show"}))
        for row in list(slot.get("windows") or []):
            if not isinstance(row, Mapping):
                continue
            target = str(row.get("target") or row.get("surface") or "")
            if _as_bool(row.get("popout"), False):
                results.append(self.execute("review.ui.popout.open", {"surface": target}))
            if any(key in row for key in ("x", "y", "width", "height", "screen_index", "preset")):
                params = dict(row)
                params["target"] = target
                results.append(self.execute("review.ui.window.set_geometry", params))
        for step in list(slot.get("steps") or slot.get("actions") or []):
            if not isinstance(step, Mapping):
                results.append({"ok": False, "error": "invalid slot step"})
                continue
            results.append(self.execute(str(step.get("action") or ""), step.get("params") if isinstance(step.get("params"), Mapping) else {}))
        failed = [row for row in results if not row.get("ok")]
        if failed:
            raise ReviewWindowActionError(str(failed[0].get("error") or "slot preparation failed"))
        return {"ok": True, "results": results}

    def _window_for_target(self, target: str) -> Any:
        text = _normal_surface(target)
        if text in {"editor", "main", "owner"}:
            return self.owner
        if text in {"ar_pbr_preview", "pbr_preview", "3d_preview", "3d_asset"}:
            window = self._latest_ar_pbr_preview_window()
            if window is not None:
                return window
        if text in POPOUT_SURFACES:
            spec = self._surface_spec(text)
            surface_owner = self._surface_owner(spec)
            window = getattr(surface_owner, spec.attr, None)
            if window is not None:
                return window
        direct = getattr(self.owner, target, None)
        if direct is not None:
            return direct
        raise ReviewWindowActionError(f"review window target not found: {target}")

    def _surface_spec(self, surface: str) -> PopoutSurface:
        spec = POPOUT_SURFACES.get(surface)
        if spec is None:
            raise ReviewWindowActionError(f"unknown popout surface: {surface}")
        return spec

    def _surface_owner(self, spec: PopoutSurface) -> Any:
        if not spec.owner_attr:
            return self.owner
        nested = getattr(self.owner, spec.owner_attr, None)
        if nested is None:
            raise ReviewWindowActionError(f"popout owner not found: {spec.owner_attr}")
        return nested

    def _geometry_from_params(self, params: Mapping[str, Any]) -> tuple[int, int, int, int]:
        if all(key in params for key in ("x", "y", "width", "height")):
            return (int(params["x"]), int(params["y"]), max(1, int(params["width"])), max(1, int(params["height"])))
        x, y, width, height = _screen_geometry(int(params.get("screen_index") or 0))
        preset = str(params.get("preset") or "fullscreen").strip().lower()
        if preset in {"fullscreen", "screen", "stage"}:
            return x, y, width, height
        if preset == "left_half":
            return x, y, max(1, width // 2), height
        if preset == "right_half":
            half = max(1, width // 2)
            return x + width - half, y, half, height
        if preset == "center":
            w = int(params.get("width") or width * 0.72)
            h = int(params.get("height") or height * 0.72)
            return x + (width - w) // 2, y + (height - h) // 2, max(1, w), max(1, h)
        raise ReviewWindowActionError(f"unknown geometry preset: {preset}")

    def _show_for_capture(self, window: Any, *, activate: bool = True) -> None:
        show = getattr(window, "show", None)
        if callable(show):
            show()
        raiser = getattr(window, "raise_", None)
        if callable(raiser):
            raiser()
        if activate:
            activate_window = getattr(window, "activateWindow", None)
            if callable(activate_window):
                activate_window()
        _process_events()


def _normal_surface(value: Any) -> str:
    text = str(value or "editor").strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "preview_popout": "viewer",
        "viewer_popout": "viewer",
        "media_pool_popout": "media_pool",
        "left_dock": "media_pool",
        "right_dock": "workbench",
        "workbench_popout": "workbench",
        "color_popout": "color",
    }.get(text, text)


def _safe_name(value: Any) -> str:
    text = _normal_surface(value)
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in text) or "capture"


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _is_visible(window: Any) -> bool:
    method = getattr(window, "isVisible", None)
    if callable(method):
        try:
            return bool(method())
        except Exception:
            return False
    return bool(window is not None)


def _process_events() -> None:
    try:
        from PySide6.QtCore import QCoreApplication

        app = QCoreApplication.instance()
        if app is not None:
            app.processEvents()
    except Exception:
        pass


def _sleep_ms(value: int) -> None:
    if value > 0:
        time.sleep(min(2000, value) / 1000.0)


def _screen_geometry(index: int) -> tuple[int, int, int, int]:
    try:
        from PySide6.QtGui import QGuiApplication

        screens = list(QGuiApplication.screens() or [])
        if screens:
            screen = screens[max(0, min(int(index), len(screens) - 1))]
            rect = screen.availableGeometry()
            return (int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))
    except Exception:
        pass
    return (0, 0, 1920, 1080)


def _slot_rows(raw: Any) -> list[Mapping[str, Any]]:
    if isinstance(raw, Mapping):
        rows: list[Mapping[str, Any]] = []
        for key, value in raw.items():
            row = dict(value if isinstance(value, Mapping) else {})
            row.setdefault("id", str(key))
            rows.append(row)
        return rows
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, Mapping)]
    return []


def run_review_multi_monitor_capture(owner: Any, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Run the review-only multi-monitor capture scenario.

    This is intentionally reached from review automation, not from the main
    action registry. Callers may pass custom slots; otherwise a conservative
    left/editor/right layout is used.
    """

    options = dict(params or {})
    root = Path(options.get("project_root") or ROOT)
    out_dir = Path(options.get("out_dir") or root / "debugCapture" / "review_multi_monitor")
    report_path = Path(options.get("report_path") or out_dir / "multi_monitor_capture_report.json")
    output_path = Path(options.get("out_path") or out_dir / "multi_environment_review.png")
    runner = ReviewWindowActionRunner(owner, root=root, output_dir=out_dir)
    slots = options.get("slots") or _default_multi_monitor_slots()
    action = runner.execute(
        "review.multi_monitor.capture_slots",
        {
            "template_path": options.get("template_path") or DEFAULT_MULTI_MONITOR_TEMPLATE,
            "screen_map_path": options.get("screen_map_path") or DEFAULT_MULTI_MONITOR_SCREEN_MAP,
            "out_path": str(output_path),
            "slot_dir": options.get("slot_dir") or out_dir / "slots",
            "slots": slots,
            "strict": _as_bool(options.get("strict"), True),
        },
    )
    payload = {
        "kind": "review_multi_monitor_capture",
        "ok": bool(action.get("ok")),
        "review_only": True,
        "scenario": "multi-monitor-capture",
        "output_path": str(output_path),
        "action_result": action,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["report_path"] = str(report_path)
    return payload


def _default_multi_monitor_slots() -> dict[str, Mapping[str, Any]]:
    return {
        "left_monitor": {
            "windows": [
                {
                    "target": "media_pool",
                    "popout": True,
                    "preset": "left_half",
                    "screen_index": 0,
                }
            ],
            "target": "media_pool",
        },
        "center_monitor": {
            "target": "editor",
        },
        "right_monitor": {
            "windows": [
                {
                    "target": "workbench",
                    "popout": True,
                    "preset": "right_half",
                    "screen_index": 0,
                }
            ],
            "target": "workbench",
        },
    }
