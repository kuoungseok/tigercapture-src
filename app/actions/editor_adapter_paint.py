"""Paint / drawing action adapter methods."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.actions.editor_adapter_object_helpers import _int


class PaintAdapterMixin:
    """Registered action surface for paint dialog object import workflows."""

    def paint_state(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        return dialog.painter_action_state()

    def paint_document_new(
        self,
        *,
        width: int = 1920,
        height: int = 1080,
        background: str = "#FFFFFF",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._replace_canvas_document(int(width or 1920), int(height or 1080), str(background or "#FFFFFF"))
        return dialog.painter_action_state()

    def paint_document_export_png(
        self,
        *,
        path: str = "",
        include_background: bool = True,
        width: int = 0,
        height: int = 0,
    ) -> dict[str, Any]:
        if not path:
            from datetime import datetime

            from app.paths import default_save_dir

            suffix = "composited" if include_background else "overlay"
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(default_save_dir() / f"paint_{suffix}_{stamp}.png")
        dialog = self._paint_dialog_owner()
        return dialog.export_png_to_path(
            path,
            include_background=bool(include_background),
            width=int(width or 0),
            height=int(height or 0),
        )

    def paint_view_zoom(self, *, percent: int = 100) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_zoom_percent(int(percent or 100))
        return dialog.painter_action_state()

    def paint_view_pan(
        self,
        *,
        x: int | None = None,
        y: int | None = None,
        dx: int = 0,
        dy: int = 0,
        reset: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if reset:
            dialog._reset_canvas_pan()
        elif x is not None or y is not None:
            current = getattr(dialog, "_canvas_pan", None)
            current_x = int(current.x()) if current is not None else 0
            current_y = int(current.y()) if current is not None else 0
            from PySide6.QtCore import QPoint

            dialog._set_canvas_pan(QPoint(current_x if x is None else int(x), current_y if y is None else int(y)))
        else:
            from PySide6.QtCore import QPoint

            dialog._pan_canvas_by(QPoint(int(dx or 0), int(dy or 0)))
        return dialog.painter_action_state()

    def paint_layer_add(self, *, name: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._new_paint_layer(str(name or "") or None)
        return dialog.painter_action_state()

    def paint_layer_select(self, *, layer_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._select_paint_layer_by_id(layer_id or None):
            raise ValueError("paint layer not found")
        return dialog.painter_action_state()

    def paint_layer_rename(self, *, layer_id: str = "", name: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._rename_layer_to(layer_id or None, str(name or "")):
            raise ValueError("layer rename did not change a paint layer")
        return dialog.painter_action_state()

    def paint_layer_duplicate(self, *, layer_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if layer_id:
            dialog._select_paint_layer_by_id(layer_id)
        dialog._duplicate_selected_layer()
        return dialog.painter_action_state()

    def paint_layer_delete(self, *, layer_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._delete_layer(layer_id or dialog._current_layer_id())
        return dialog.painter_action_state()

    def paint_layer_set_visible(self, *, layer_id: str = "", visible: bool = True) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_layer_visible(layer_id or None, bool(visible))
        return dialog.painter_action_state()

    def paint_layer_set_locked(self, *, layer_id: str = "", locked: bool = True) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_layer_locked(layer_id or None, bool(locked))
        return dialog.painter_action_state()

    def paint_layer_set_opacity(self, *, layer_id: str = "", opacity: int = 100) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_layer_opacity_value(layer_id or None, int(opacity or 0))
        return dialog.painter_action_state()

    def paint_layer_set_blend_mode(self, *, layer_id: str = "", blend_mode: str = "normal") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_layer_blend_mode(layer_id or None, str(blend_mode or "normal"))
        return dialog.painter_action_state()

    def paint_channel_set_visible(self, *, channel: str = "RGB", visible: bool = True) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_channel_visibility(str(channel or "RGB"), bool(visible))
        return dialog.painter_action_state()

    def paint_channel_select(self, *, channel: str = "RGB") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_selected_channel(str(channel or "RGB"))
        return dialog.painter_action_state()

    def paint_channel_copy_image(self, *, channel: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._copy_channel_image(str(channel or getattr(dialog, "_selected_channel", "RGB"))):
            raise ValueError("no Painter channel image available to copy")
        state = dialog.painter_action_state()
        state["channel_clipboard"] = "copied"
        return state

    def paint_channel_paste_image(self, *, channel: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._paste_channel_image(str(channel or getattr(dialog, "_selected_channel", "RGB"))):
            raise ValueError("system clipboard does not contain an image")
        return dialog.painter_action_state()

    def paint_selection_select_all(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._select_all()
        return dialog.painter_action_state()

    def paint_selection_deselect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._deselect()
        return dialog.painter_action_state()

    def paint_selection_invert(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._invert_selection()
        return dialog.painter_action_state()

    def paint_selection_to_path(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._selection_to_path()
        return dialog.painter_action_state()

    def paint_selection_rectangle(
        self,
        *,
        x1: float = 0.0,
        y1: float = 0.0,
        x2: float = 1.0,
        y2: float = 1.0,
        aspect: str = "free",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._push_undo_state("Rectangular selection")
        dialog._set_selection_aspect_mode(str(aspect or "free"))
        dialog.canvas.select_rectangle(float(x1), float(y1), float(x2), float(y2), shape="rect", aspect=str(aspect or "free"))
        dialog._selected_path_item_id = "selection"
        dialog._update_path_list()
        dialog._set_tool("rect_select")
        return dialog.painter_action_state()

    def paint_selection_ellipse(
        self,
        *,
        x1: float = 0.0,
        y1: float = 0.0,
        x2: float = 1.0,
        y2: float = 1.0,
        aspect: str = "free",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._push_undo_state("Elliptical selection")
        dialog._set_selection_aspect_mode(str(aspect or "free"))
        dialog.canvas.select_rectangle(float(x1), float(y1), float(x2), float(y2), shape="ellipse", aspect=str(aspect or "free"))
        dialog._selected_path_item_id = "selection"
        dialog._update_path_list()
        dialog._set_tool("ellipse_select")
        return dialog.painter_action_state()

    def paint_selection_set_aspect(self, *, aspect: str = "free") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_selection_aspect_mode(str(aspect or "free"))
        return dialog.painter_action_state()

    def paint_crop_to_selection(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._crop_to_selection():
            raise ValueError("crop requires an active Painter selection")
        return dialog.painter_action_state()

    def paint_image_resize(self, *, width: int = 1920, height: int = 1080) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._resize_image_document(int(width or 1920), int(height or 1080))
        return dialog.painter_action_state()

    def paint_canvas_resize(
        self,
        *,
        width: int = 1920,
        height: int = 1080,
        background: str = "transparent",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._resize_canvas_document(int(width or 1920), int(height or 1080), background=str(background or "transparent"))
        return dialog.painter_action_state()

    def paint_canvas_flip(self, *, axis: str = "horizontal") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        value = str(axis or "horizontal").strip().casefold()
        dialog._flip_canvas(horizontal=value in {"horizontal", "x"})
        return dialog.painter_action_state()

    def paint_mirror_set(self, *, x: bool | None = None, y: bool | None = None) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_mirror_enabled(x=x, y=y)
        return dialog.painter_action_state()

    def paint_layer_mask_from_selection(self, *, layer_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if layer_id and not dialog._select_paint_layer_by_id(layer_id):
            raise ValueError("paint layer not found")
        if not dialog._mask_selected_layer_from_selection():
            raise ValueError("layer mask from selection requires an active selection")
        return dialog.painter_action_state()

    def paint_layer_mask_from_path(self, *, layer_id: str = "", path_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if layer_id and not dialog._select_paint_layer_by_id(layer_id):
            raise ValueError("paint layer not found")
        if path_id:
            dialog._selected_path_item_id = str(path_id)
        if not dialog._mask_selected_layer_from_path():
            raise ValueError("layer mask from path requires a path with at least 3 points")
        return dialog.painter_action_state()

    def paint_path_to_selection(self, *, path_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if path_id:
            dialog._selected_path_item_id = str(path_id)
        dialog._make_selection_from_selected_path()
        return dialog.painter_action_state()

    def paint_path_create(
        self,
        *,
        points: list[Any] | None = None,
        closed: bool = True,
        make_selection: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._create_path_from_points(points or [], closed=bool(closed), make_selection=bool(make_selection)):
            raise ValueError("path requires at least two valid normalized points")
        return dialog.painter_action_state()

    def paint_path_delete(self, *, path_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._delete_path_by_id(path_id or None):
            raise ValueError("paint path not found")
        return dialog.painter_action_state()

    def paint_path_clear(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._clear_path_preview()
        return dialog.painter_action_state()

    def paint_path_commit(self, *, closed: bool = False) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._commit_path(bool(closed))
        return dialog.painter_action_state()

    def paint_clipboard_copy(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._copy_selected_layer()
        return dialog.painter_action_state()

    def paint_clipboard_cut(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._cut_selected_layer()
        return dialog.painter_action_state()

    def paint_clipboard_paste(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._paste_layer_clipboard()
        return dialog.painter_action_state()

    def paint_tool_set(self, *, tool: str = "select") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        tool_name = str(tool or "select").strip().casefold().replace("-", "_")
        aliases = {
            "move": "select",
            "hand": "pan",
            "brush": "pen",
            "pen": "pen",
            "eraser": "eraser",
            "path": "path",
            "rect_select": "rect_select",
            "rectangle": "rect_select",
            "marquee_rect": "rect_select",
            "ellipse_select": "ellipse_select",
            "ellipse": "ellipse_select",
            "marquee_ellipse": "ellipse_select",
            "crop": "crop",
            "pan": "pan",
            "select": "select",
        }
        dialog._set_tool(aliases.get(tool_name, "select"))
        return dialog.painter_action_state()

    def paint_window_show_panel(self, *, panel: str = "layers") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._show_painter_tab(str(panel or "layers"))
        return dialog.painter_action_state()

    def paint_editor_objects_list(
        self,
        *,
        time_ms: int | None = None,
        include_inactive: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        target_ms = self._paint_action_time_ms(time_ms)
        from app.drawing_editor_object_import import collect_editor_paint_objects

        rows = collect_editor_paint_objects(
            owner,
            time_ms=target_ms,
            include_inactive=bool(include_inactive),
        )
        max_rows = max(0, _int(limit, 100))
        objects = [self._paint_object_payload(row) for row in rows[:max_rows]]
        return {
            "schema": "tigerstudio.actions.paint.editor_objects.list.v1",
            "time_ms": target_ms,
            "count": len(rows),
            "returned": len(objects),
            "objects": objects,
        }

    def paint_editor_object_render(
        self,
        *,
        object_id: str = "",
        kind: str = "",
        time_ms: int | None = None,
        include_inactive: bool = True,
        output_dir: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        obj = self._paint_find_import_object(
            object_id=object_id,
            kind=kind,
            time_ms=time_ms,
            include_inactive=include_inactive,
        )
        from app.drawing_editor_object_import import render_paint_import_object

        report = render_paint_import_object(
            obj,
            canvas_size=self._paint_canvas_size(),
            output_dir=output_dir or None,
            force=bool(force),
        )
        return {
            "schema": "tigerstudio.actions.paint.editor_object.render.v1",
            "object": self._paint_object_payload(obj),
            "render": report,
        }

    def paint_editor_object_import(
        self,
        *,
        object_id: str = "",
        kind: str = "",
        time_ms: int | None = None,
        include_inactive: bool = True,
        x_norm: float | None = None,
        y_norm: float | None = None,
        width_norm: float | None = None,
        height_norm: float | None = None,
        output_dir: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        obj = self._paint_find_import_object(
            object_id=object_id,
            kind=kind,
            time_ms=time_ms,
            include_inactive=include_inactive,
        )
        from app.drawing import Sticker
        from app.drawing_editor_object_import import render_paint_import_object

        report = render_paint_import_object(
            obj,
            canvas_size=self._paint_canvas_size(),
            output_dir=output_dir or None,
            force=bool(force),
        )
        rect = dict(report.get("rect_norm") or {})
        w = _clamp_norm(width_norm if width_norm is not None else rect.get("w", obj.width_norm), 0.04, 1.0)
        h = _clamp_norm(height_norm if height_norm is not None else rect.get("h", obj.height_norm), 0.04, 1.0)
        x = _clamp_norm(x_norm if x_norm is not None else rect.get("x", obj.x_norm), 0.0, 1.0 - w)
        y = _clamp_norm(y_norm if y_norm is not None else rect.get("y", obj.y_norm), 0.0, 1.0 - h)
        stickers = getattr(owner, "_stickers", None)
        if stickers is None:
            stickers = []
            setattr(owner, "_stickers", stickers)
        start_ms = self._paint_action_time_ms(time_ms)
        sticker = Sticker(
            png_path=str(report.get("png_path") or ""),
            x_norm=x,
            y_norm=y,
            width_norm=w,
            height_norm=h,
            start_ms=start_ms,
            end_ms=-1,
            z_index=max((int(getattr(row, "z_index", 0) or 0) for row in stickers), default=0) + 1,
        )
        stickers.append(sticker)
        spawn = getattr(owner, "_spawn_sticker_item", None)
        if callable(spawn):
            try:
                spawn(sticker)
            except Exception:
                pass
        update_visibility = getattr(owner, "_update_sticker_visibility", None)
        if callable(update_visibility):
            try:
                update_visibility(start_ms)
            except Exception:
                pass
        canvas = getattr(owner, "_drawing_canvas", None)
        if canvas is not None and hasattr(canvas, "update"):
            try:
                canvas.update()
            except Exception:
                pass
        self._register_change("Import editor object into paint")
        return {
            "schema": "tigerstudio.actions.paint.editor_object.import.v1",
            "object": self._paint_object_payload(obj),
            "sticker": {
                "png_path": str(Path(sticker.png_path)),
                "x_norm": sticker.x_norm,
                "y_norm": sticker.y_norm,
                "width_norm": sticker.width_norm,
                "height_norm": sticker.height_norm,
                "start_ms": sticker.start_ms,
                "end_ms": sticker.end_ms,
                "z_index": sticker.z_index,
            },
            "render": report,
            "sticker_count": len(stickers),
        }

    def paint_export_png(
        self,
        *,
        path: str = "",
        mode: str = "composited",
        time_ms: int | None = None,
        width: int = 0,
        height: int = 0,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        target_ms = self._paint_action_time_ms(time_ms)
        mode_text = str(mode or "composited").strip().casefold().replace("-", "_")
        include_background = mode_text not in {"overlay", "transparent", "transparent_overlay"}
        if not path:
            from datetime import datetime

            from app.paths import default_save_dir

            suffix = "composited" if include_background else "overlay"
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(default_save_dir() / f"paint_{suffix}_{stamp}.png")
        background = getattr(owner, "_preview_pixmap", None) if include_background else None
        frame_size = None
        if int(width or 0) > 0 and int(height or 0) > 0:
            frame_size = (int(width), int(height))
        else:
            frame_size = self._paint_export_size_for_owner(background)
        canvas_w, _canvas_h = self._paint_canvas_size()
        stroke_width_scale = max(0.001, float(frame_size[0]) / max(1, float(canvas_w)))
        from app.drawing import export_paint_png

        report = export_paint_png(
            path,
            background_pixmap=background,
            strokes=list(getattr(owner, "_strokes", []) or []),
            bubbles=list(getattr(owner, "_bubbles", []) or []),
            stickers=list(getattr(owner, "_stickers", []) or []),
            time_ms=target_ms,
            frame_size=frame_size,
            include_background=include_background,
            stroke_width_scale=stroke_width_scale,
        )
        return report

    def _paint_dialog_owner(self) -> Any:
        owner = self._require_owner()
        if _looks_like_paint_dialog(owner):
            return owner
        for attr in (
            "_active_painter_window",
            "_active_paint_dialog",
            "_paint_dialog",
            "_painter_dialog",
        ):
            candidate = getattr(owner, attr, None)
            if _looks_like_paint_dialog(candidate):
                return candidate
        workbench = getattr(owner, "_workbench_panel", None) or getattr(owner, "workbench_panel", None)
        candidates: list[Any] = []
        if workbench is not None:
            candidates.extend(list(getattr(workbench, "_painter_windows", []) or []))
        candidates.extend(list(getattr(owner, "_painter_windows", []) or []))
        for candidate in reversed(candidates):
            if not _looks_like_paint_dialog(candidate):
                continue
            try:
                if hasattr(candidate, "isVisible") and not candidate.isVisible():
                    continue
            except Exception:
                pass
            return candidate
        raise ValueError("no active Painter dialog")

    def _paint_action_time_ms(self, time_ms: int | None) -> int:
        if time_ms is not None:
            return max(0, _int(time_ms, 0))
        owner = self._require_owner()
        player = getattr(owner, "_player", None)
        position = getattr(player, "position", None)
        if callable(position):
            try:
                return max(0, _int(position(), 0))
            except Exception:
                pass
        return 0

    def _paint_canvas_size(self) -> tuple[int, int]:
        owner = self._require_owner()
        for name in ("_drawing_canvas", "_preview_label", "_preview_widget"):
            widget = getattr(owner, name, None)
            if widget is not None:
                try:
                    width = int(widget.width())
                    height = int(widget.height())
                    if width > 0 and height > 0:
                        return (width, height)
                except Exception:
                    pass
        pixmap = getattr(owner, "_preview_pixmap", None)
        if pixmap is not None:
            try:
                width = int(pixmap.width())
                height = int(pixmap.height())
                if width > 0 and height > 0:
                    return (width, height)
            except Exception:
                pass
        return (1920, 1080)

    def _paint_export_size_for_owner(self, background: Any) -> tuple[int, int]:
        if background is not None:
            try:
                width = int(background.width())
                height = int(background.height())
                if width > 0 and height > 0:
                    return (width, height)
            except Exception:
                pass
        return self._paint_canvas_size()

    def _paint_find_import_object(
        self,
        *,
        object_id: str = "",
        kind: str = "",
        time_ms: int | None = None,
        include_inactive: bool = True,
    ):
        owner = self._require_owner()
        target_ms = self._paint_action_time_ms(time_ms)
        from app.drawing_editor_object_import import collect_editor_paint_objects

        rows = collect_editor_paint_objects(
            owner,
            time_ms=target_ms,
            include_inactive=bool(include_inactive),
        )
        wanted_id = str(object_id or "").strip()
        wanted_kind = str(kind or "").strip()
        if wanted_id:
            for row in rows:
                if row.id == wanted_id:
                    return row
            raise ValueError(f"paint import object not found: {wanted_id}")
        if wanted_kind:
            for row in rows:
                if row.kind == wanted_kind:
                    return row
            raise ValueError(f"paint import object kind not found: {wanted_kind}")
        if rows:
            return rows[0]
        raise ValueError("no paint import objects available")

    @staticmethod
    def _paint_object_payload(obj: Any) -> dict[str, Any]:
        return {
            "id": str(getattr(obj, "id", "")),
            "kind": str(getattr(obj, "kind", "")),
            "label": str(getattr(obj, "label", "")),
            "source_path": str(getattr(obj, "source_path", "")),
            "active": bool(getattr(obj, "active", False)),
            "start_ms": int(getattr(obj, "start_ms", 0) or 0),
            "end_ms": int(getattr(obj, "end_ms", -1) or -1),
            "x_norm": float(getattr(obj, "x_norm", 0.0) or 0.0),
            "y_norm": float(getattr(obj, "y_norm", 0.0) or 0.0),
            "width_norm": float(getattr(obj, "width_norm", 0.0) or 0.0),
            "height_norm": float(getattr(obj, "height_norm", 0.0) or 0.0),
            "payload": dict(getattr(obj, "payload", {}) or {}),
        }


def _clamp_norm(value: Any, lo: float, hi: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = lo
    return max(lo, min(hi, number))


def _looks_like_paint_dialog(candidate: Any) -> bool:
    if candidate is None:
        return False
    return bool(
        hasattr(candidate, "canvas")
        and callable(getattr(candidate, "painter_action_state", None))
        and callable(getattr(candidate, "export_png_to_path", None))
    )


__all__ = ["PaintAdapterMixin"]
