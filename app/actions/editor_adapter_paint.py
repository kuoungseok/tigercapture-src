"""Paint / drawing action adapter methods."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.actions.editor_adapter_object_helpers import _int


class PaintAdapterMixin:
    """Registered action surface for paint dialog object import workflows."""

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


__all__ = ["PaintAdapterMixin"]
