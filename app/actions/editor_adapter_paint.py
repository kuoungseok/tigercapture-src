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

    def paint_gpu_status(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_opengl import painter_opengl_status

        status = painter_opengl_status()
        state = dialog.painter_action_state()
        return {
            **status,
            "last_blockout_renderer": dict(state.get("gpu", {}).get("blockout_renderer", {}) or {}),
            "last_canvas_renderer": dict(state.get("gpu", {}).get("canvas_renderer", {}) or {}),
            "remote_work_contract": {
                "safe_for_rdp": True,
                "opengl_is_preferred_not_required": True,
                "fallback_is_product_path": True,
            },
        }

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

    def paint_view_grid(
        self,
        *,
        visible: bool | None = None,
        snap: bool | None = None,
        size_px: int | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_grid_options(visible=visible, snap=snap, size_px=size_px)
        return dialog.painter_action_state()

    def paint_quick_mask_set(self, *, enabled: bool = True) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_quick_mask_enabled(bool(enabled))
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

    def paint_selection_select_by_color(
        self,
        *,
        x: float = 0.5,
        y: float = 0.5,
        tolerance: int | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._select_by_color_at(float(x), float(y), tolerance=tolerance):
            raise ValueError("Magic Select could not create a color selection")
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

    def paint_fill_solid(self, *, color: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._fill_document("solid", color1=str(color or "") or None)
        return dialog.painter_action_state()

    def paint_fill_gradient(self, *, color1: str = "", color2: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._fill_document(
            "gradient",
            color1=str(color1 or "") or None,
            color2=str(color2 or "") or None,
        )
        return dialog.painter_action_state()

    def paint_fill_pattern(self, *, color1: str = "", color2: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._fill_document(
            "pattern",
            color1=str(color1 or "") or None,
            color2=str(color2 or "") or None,
        )
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

    def paint_layer_mask_create(
        self,
        *,
        layer_id: str = "",
        mask_type: str = "selection",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._create_layer_mask(str(mask_type or "selection"), layer_id or None):
            raise ValueError("layer mask creation requires valid mask source pixels or points")
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
            "magic_select": "magic_select",
            "magic_wand": "magic_select",
            "select_color": "magic_select",
            "crop": "crop",
            "pan": "pan",
            "select": "select",
        }
        dialog._set_tool(aliases.get(tool_name, "select"))
        return dialog.painter_action_state()

    def paint_brush_set(
        self,
        *,
        preset: str = "",
        style: str = "",
        width: int | None = None,
        opacity: int | None = None,
        hardness: int | None = None,
        spacing: int | None = None,
        angle: int | None = None,
        roundness: int | None = None,
        flip_x: bool | None = None,
        flip_y: bool | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.drawing import BRUSH_LIBRARY_PRESETS, _normalize_paint_brush_style

        preset_key = str(preset or "").strip().casefold().replace("-", "_").replace(" ", "_")
        if preset_key:
            for row in BRUSH_LIBRARY_PRESETS:
                name_key = str(row.get("name") or "").strip().casefold().replace("-", "_").replace(" ", "_")
                style_key = str(row.get("style") or "").strip().casefold().replace("-", "_").replace(" ", "_")
                if preset_key in {name_key, style_key}:
                    dialog._apply_brush_library_preset(row)
                    break
            else:
                raise ValueError("Painter brush preset not found")

        if style:
            style_id = _normalize_paint_brush_style(str(style))
            dialog._pen_style = style_id
            if hasattr(dialog, "canvas"):
                dialog.canvas.set_pen_style(style_id)
            if hasattr(dialog, "brush_style_combo"):
                index = dialog.brush_style_combo.findData(style_id)
                if index >= 0:
                    dialog.brush_style_combo.setCurrentIndex(index)
        if width is not None:
            value = max(1, min(60, int(width or 1)))
            if hasattr(dialog, "width_slider"):
                dialog.width_slider.setValue(value)
            else:
                dialog._pen_width = float(value)
                if hasattr(dialog, "canvas"):
                    dialog.canvas.set_pen_width(dialog._pen_width)
        if opacity is not None:
            value = max(10, min(100, int(opacity or 100)))
            if hasattr(dialog, "opacity_slider"):
                dialog.opacity_slider.setValue(value)
            else:
                dialog._pen_opacity = int(value * 255 / 100)
                if hasattr(dialog, "canvas"):
                    dialog.canvas.set_pen_opacity(dialog._pen_opacity)
        for key, value in (
            ("hardness", hardness),
            ("spacing", spacing),
            ("angle", angle),
            ("roundness", roundness),
        ):
            if value is not None:
                dialog._set_brush_detail_value(key, int(value))
        if flip_x is not None:
            dialog._set_brush_detail_toggle("flip_x", bool(flip_x))
        if flip_y is not None:
            dialog._set_brush_detail_toggle("flip_y", bool(flip_y))
        dialog._set_tool("pen")
        return dialog.painter_action_state()

    def paint_window_show_panel(self, *, panel: str = "layers") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(panel or "layers")
        if target.strip().casefold() in {"brush", "brushes", "brush_settings"}:
            dialog._focus_brush_panel()
        elif target.strip().casefold() in {"reference", "references", "reference_board", "ref"}:
            dialog._focus_reference_board_panel()
        elif target.strip().casefold() in {"3d", "blockout", "3d_blockout"}:
            dialog._focus_3d_blockout_panel()
        else:
            dialog._show_painter_tab(target)
        return dialog.painter_action_state()

    def paint_pbr_preview(
        self,
        *,
        path: str = "",
        preview_mode: str = "material",
        preview_shape: str = "plane",
        width: int = 512,
        settings: dict[str, Any] | None = None,
        allow_cpu: bool | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not path:
            import tempfile

            path = str(Path(tempfile.gettempdir()) / "tiger_painter_pbr" / f"painter_pbr_{preview_mode or 'material'}.png")
        return dialog.preview_pbr_map_to_path(
            path,
            preview_mode=str(preview_mode or "material"),
            preview_shape=str(preview_shape or "plane"),
            width=int(width or 512),
            settings=dict(settings or {}),
            allow_cpu=allow_cpu,
        )

    def paint_pbr_export(
        self,
        *,
        output_dir: str = "",
        settings: dict[str, Any] | None = None,
        maps: list[str] | None = None,
        packed_layouts: list[str] | None = None,
        packed: bool = True,
        allow_cpu: bool | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not output_dir:
            from datetime import datetime

            from app.paths import default_save_dir

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = str(default_save_dir() / f"painter_pbr_maps_{stamp}")
        return dialog.export_pbr_maps_to_path(
            output_dir,
            settings=dict(settings or {}),
            maps=maps,
            packed_layouts=packed_layouts,
            packed=bool(packed),
            allow_cpu=allow_cpu,
        )

    def paint_pbr_substrate_plan(
        self,
        *,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.ar_pbr.texture_map_lab import substrate_export_plan

        merged = dialog._pbr_texture_settings_payload(dict(settings or {}))
        return substrate_export_plan(merged)

    def paint_pbr_backend_status(
        self,
        *,
        backend: str = "auto",
        allow_cpu: bool | None = None,
    ) -> dict[str, Any]:
        self._paint_dialog_owner()
        from app.ar_pbr.texture_map_lab import select_texture_map_backend, texture_lab_cpu_fallback_allowed

        cpu_allowed = texture_lab_cpu_fallback_allowed(False) if allow_cpu is None else bool(allow_cpu)
        return select_texture_map_backend(backend, allow_cpu=cpu_allowed)

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

    def paint_3d_blockout_state(
        self,
        *,
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        scene = self._paint_3d_blockout_scene(dialog)
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_add(
        self,
        *,
        preview_width: int = 640,
        preview_height: int = 360,
        **params: Any,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import add_blockout_primitive

        scene = add_blockout_primitive(self._paint_3d_blockout_scene(dialog), **dict(params))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Add Painter 3D blockout primitive")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_update(
        self,
        *,
        primitive_id: str = "",
        preview_width: int = 640,
        preview_height: int = 360,
        **params: Any,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import update_blockout_primitive

        scene = update_blockout_primitive(
            self._paint_3d_blockout_scene(dialog),
            str(primitive_id or ""),
            **dict(params),
        )
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Update Painter 3D blockout primitive")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_delete(
        self,
        *,
        primitive_id: str = "",
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import delete_blockout_primitive

        scene = delete_blockout_primitive(self._paint_3d_blockout_scene(dialog), str(primitive_id or ""))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Delete Painter 3D blockout primitive")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_duplicate(
        self,
        *,
        primitive_id: str = "",
        offset_x: float = 0.65,
        offset_y: float = 0.0,
        offset_z: float = 0.25,
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import duplicate_blockout_primitive

        scene = duplicate_blockout_primitive(
            self._paint_3d_blockout_scene(dialog),
            str(primitive_id or ""),
            offset=(float(offset_x), float(offset_y), float(offset_z)),
        )
        rows = scene.to_dict().get("primitives", [])
        if rows:
            setattr(dialog, "_painter_3d_blockout_selected_id", str(rows[-1].get("id") or ""))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Duplicate Painter 3D blockout primitive")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_align_ground(
        self,
        *,
        primitive_id: str = "",
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import align_blockout_primitive_to_ground

        scene = align_blockout_primitive_to_ground(self._paint_3d_blockout_scene(dialog), str(primitive_id or ""))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Align Painter 3D blockout primitive to ground")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_snap(
        self,
        *,
        enabled: bool | None = None,
        primitive_id: str = "",
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import set_blockout_snap, snap_blockout_primitive_to_grid

        scene = self._paint_3d_blockout_scene(dialog)
        if enabled is not None:
            scene = set_blockout_snap(scene, bool(enabled))
        if str(primitive_id or "").strip():
            scene = snap_blockout_primitive_to_grid(scene, str(primitive_id or ""))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Set Painter 3D blockout snap")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_camera(
        self,
        *,
        preview_width: int = 640,
        preview_height: int = 360,
        **params: Any,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import update_blockout_camera

        scene = update_blockout_camera(self._paint_3d_blockout_scene(dialog), **dict(params))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Adjust Painter 3D blockout camera")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_camera_preset(
        self,
        *,
        preset: str = "perspective",
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import apply_blockout_camera_preset

        scene = apply_blockout_camera_preset(self._paint_3d_blockout_scene(dialog), str(preset or "perspective"))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Apply Painter 3D blockout camera preset")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_bake(
        self,
        *,
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        bake = getattr(dialog, "_bake_3d_blockout_to_layer", None)
        if not callable(bake):
            raise RuntimeError("Active Painter dialog does not support 3D blockout baking")
        report = bake()
        if not report:
            raise ValueError("No Painter 3D blockout guide edges are available to bake")
        self._register_change("Bake Painter 3D blockout")
        scene = self._paint_3d_blockout_scene(dialog)
        payload = self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)
        payload["bake"] = report
        return payload

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

    def _paint_3d_blockout_scene(self, dialog: Any):
        from app.painter_3d_blockout import blockout_scene_from_dict

        return blockout_scene_from_dict(getattr(dialog, "_painter_3d_blockout_scene", None))

    def _store_paint_3d_blockout_scene(self, dialog: Any, scene: Any) -> None:
        setattr(dialog, "_painter_3d_blockout_scene", scene.to_dict())
        refresh = getattr(dialog, "_refresh_3d_blockout_panel", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass
        update = getattr(dialog, "update", None)
        if callable(update):
            try:
                update()
            except Exception:
                pass

    def _paint_3d_blockout_payload(
        self,
        scene: Any,
        *,
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        from app.painter_3d_blockout import project_blockout_scene
        from app.painter_opengl import PAINTER_OPENGL_RENDERER_ID

        projection = project_blockout_scene(scene, int(preview_width or 640), int(preview_height or 360))
        try:
            dialog = self._paint_dialog_owner()
            renderer_status = dict(getattr(dialog, "_painter_3d_blockout_renderer_status", {}) or {})
        except Exception:
            renderer_status = {}
        return {
            "schema": "tigerstudio.actions.paint.3d_blockout.v1",
            "scene": scene.to_dict(),
            "projection": projection,
            "renderer": {
                "preferred": PAINTER_OPENGL_RENDERER_ID,
                "fallback": "painter_blockout_qpainter_v1",
                "last_render": renderer_status,
                "remote_safe": True,
            },
            "gpu_contract": {
                "future_gpu_preview": True,
                "opengl_first_preview": True,
                "qpainter_fallback": True,
                "payload_is_serializable": True,
                "qt_preview_is_reference_only": True,
            },
            "ui_guardrails": {
                "preserve_texture_lab_entry_points": True,
                "layers_channels_paths_remain_primary_dock": True,
                "blockout_is_optional_painter_doorway": True,
            },
            "gizmo_contract": {
                "standard_3d_gizmo": True,
                "object_modes": ["move", "rotate", "scale"],
                "camera_modes": ["orbit", "pan", "zoom_distance", "fov"],
                "primitive_scope": ["box", "arch"],
            },
        }

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

    def _paint_reference_board(self, dialog: Any):
        from app.painter_reference_board import reference_board_from_dict

        return reference_board_from_dict(getattr(dialog, "_painter_reference_board", None))

    def _store_paint_reference_board(self, dialog: Any, board: Any) -> None:
        setattr(dialog, "_painter_reference_board", board.to_dict())
        refresh = getattr(dialog, "_refresh_reference_board_panel", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass
        update = getattr(dialog, "update", None)
        if callable(update):
            try:
                update()
            except Exception:
                pass

    def _paint_reference_payload(self, dialog: Any) -> dict[str, Any]:
        board = self._paint_reference_board(dialog)
        selected = str(getattr(dialog, "_painter_reference_selected_id", "") or "")
        return {
            "schema": "tigerstudio.actions.paint.reference_board.v1",
            "board": board.to_dict(),
            "selected_reference_id": selected,
            "ui_contract": {
                "non_destructive_reference_overlay": True,
                "exported_by_default": False,
                "requires_explicit_bake": True,
                "layers_channels_paths_remain_primary_dock": True,
            },
        }

    def paint_reference_state(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        return self._paint_reference_payload(dialog)

    def paint_reference_add(
        self,
        *,
        path: str = "",
        name: str = "",
        x_norm: float = 0.04,
        y_norm: float = 0.04,
        width_norm: float = 0.34,
        height_norm: float = 0.34,
        opacity: float = 0.58,
        rotation_deg: float = 0.0,
        visible: bool = True,
        locked: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_reference_board import add_reference_image

        board = add_reference_image(
            self._paint_reference_board(dialog),
            path=str(path or ""),
            name=str(name or ""),
            x_norm=float(x_norm),
            y_norm=float(y_norm),
            width_norm=float(width_norm),
            height_norm=float(height_norm),
            opacity=float(opacity),
            rotation_deg=float(rotation_deg),
            visible=bool(visible),
            locked=bool(locked),
        )
        rows = board.to_dict().get("references", [])
        if rows:
            setattr(dialog, "_painter_reference_selected_id", str(rows[-1].get("id") or ""))
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_update(
        self,
        *,
        reference_id: str = "",
        name: str | None = None,
        x_norm: float | None = None,
        y_norm: float | None = None,
        width_norm: float | None = None,
        height_norm: float | None = None,
        opacity: float | None = None,
        rotation_deg: float | None = None,
        visible: bool | None = None,
        locked: bool | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(reference_id or getattr(dialog, "_painter_reference_selected_id", "") or "")
        from app.painter_reference_board import update_reference_image

        board = update_reference_image(
            self._paint_reference_board(dialog),
            target,
            name=name,
            x_norm=x_norm,
            y_norm=y_norm,
            width_norm=width_norm,
            height_norm=height_norm,
            opacity=opacity,
            rotation_deg=rotation_deg,
            visible=visible,
            locked=locked,
        )
        setattr(dialog, "_painter_reference_selected_id", target)
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_delete(self, *, reference_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(reference_id or getattr(dialog, "_painter_reference_selected_id", "") or "")
        from app.painter_reference_board import delete_reference_image

        board = delete_reference_image(self._paint_reference_board(dialog), target)
        rows = board.to_dict().get("references", [])
        setattr(dialog, "_painter_reference_selected_id", str(rows[-1].get("id") or "") if rows else "")
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_duplicate(
        self,
        *,
        reference_id: str = "",
        offset_x: float = 0.04,
        offset_y: float = 0.04,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(reference_id or getattr(dialog, "_painter_reference_selected_id", "") or "")
        from app.painter_reference_board import duplicate_reference_image

        board = duplicate_reference_image(
            self._paint_reference_board(dialog),
            target,
            offset_x=float(offset_x),
            offset_y=float(offset_y),
        )
        rows = board.to_dict().get("references", [])
        if rows:
            setattr(dialog, "_painter_reference_selected_id", str(rows[-1].get("id") or ""))
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_bake(self, *, reference_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if reference_id:
            setattr(dialog, "_painter_reference_selected_id", str(reference_id))
        bake = dialog._bake_selected_reference_to_sticker()
        return {
            **self._paint_reference_payload(dialog),
            "bake": dict(bake or {}),
        }

    def paint_reference_sample_color(
        self,
        *,
        reference_id: str = "",
        x_norm: float = 0.5,
        y_norm: float = 0.5,
        apply: bool = True,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(reference_id or getattr(dialog, "_painter_reference_selected_id", "") or "")
        if target:
            setattr(dialog, "_painter_reference_selected_id", target)
        reference = dialog._selected_reference_payload()
        if not reference:
            raise ValueError("Painter reference not found")
        from app.painter_reference_board import sample_reference_color
        from PySide6.QtGui import QColor

        sample = sample_reference_color(str(reference.get("path") or ""), x_norm=float(x_norm), y_norm=float(y_norm))
        if bool(apply):
            rgb = sample.get("rgb", [255, 255, 255])
            dialog._apply_pen_color(QColor(int(rgb[0]), int(rgb[1]), int(rgb[2])), remember=True)
        return {
            **self._paint_reference_payload(dialog),
            "sample": sample,
            "applied_to_foreground": bool(apply),
        }

    def paint_reference_extract_palette(
        self,
        *,
        reference_id: str = "",
        max_colors: int = 8,
        apply: bool = True,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(reference_id or getattr(dialog, "_painter_reference_selected_id", "") or "")
        if target:
            setattr(dialog, "_painter_reference_selected_id", target)
        reference = dialog._selected_reference_payload()
        if not reference:
            raise ValueError("Painter reference not found")
        from app.painter_reference_board import extract_reference_palette
        from PySide6.QtGui import QColor

        palette = extract_reference_palette(str(reference.get("path") or ""), max_colors=int(max_colors or 8))
        applied_colors: list[tuple[int, int, int]] = []
        if bool(apply):
            for row in palette.get("colors", []) or []:
                rgb = row.get("rgb")
                if isinstance(rgb, list) and len(rgb) >= 3:
                    applied_colors.append((int(rgb[0]), int(rgb[1]), int(rgb[2])))
            if applied_colors:
                limit = len(getattr(dialog, "_recent_colors", []) or []) or 5
                dialog._recent_colors = applied_colors[:limit]
                dialog._apply_pen_color(QColor(*applied_colors[0]), remember=False)
        return {
            **self._paint_reference_payload(dialog),
            "palette": palette,
            "applied_to_recent_colors": bool(apply),
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
