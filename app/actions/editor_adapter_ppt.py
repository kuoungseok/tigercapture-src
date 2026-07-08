"""PPT generator action adapter helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class PptAdapterMixin:
    def ppt_templates_list(self) -> dict[str, Any]:
        from app.pptgen.templates import list_templates

        return {
            "schema": "tigercapture.actions.ppt.templates.v1",
            "templates": [
                {
                    "id": template.id,
                    "name": template.name,
                    "category": template.category,
                    "description": template.description,
                    "layout_id": template.layout_id,
                    "tags": list(template.tags),
                }
                for template in list_templates()
            ],
        }

    def ppt_apply_template(self, *, template_id: str) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(template_id or "").strip():
            raise RuntimeError("template_id is required")
        method = getattr(owner, "_ppt_apply_template", None)
        if not callable(method):
            raise RuntimeError("PPT template bridge is unavailable")
        return dict(method(template_id=template_id) or {})

    def ppt_project_create(self, *, template_id: str = "blank", title: str = "", path: str = "") -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_project_create", None)
        if not callable(method):
            raise RuntimeError("PPT project bridge is unavailable")
        return dict(method(template_id=template_id or "blank", title=title, path=path) or {})

    def ppt_deck_from_prompt(
        self,
        *,
        prompt: str,
        title: str = "",
        template_id: str = "title_body",
        max_slides: int = 4,
        path: str = "",
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(prompt or "").strip():
            raise RuntimeError("prompt is required")
        method = getattr(owner, "_ppt_deck_from_prompt", None)
        if not callable(method):
            raise RuntimeError("PPT prompt deck bridge is unavailable")
        return dict(
            method(
                prompt=prompt,
                title=title,
                template_id=template_id or "title_body",
                max_slides=int(max_slides or 4),
                path=path,
            )
            or {}
        )

    def ppt_deck_from_timeline(
        self,
        *,
        title: str = "Timeline Presentation",
        max_slides: int = 24,
        path: str = "",
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_deck_from_timeline", None)
        if not callable(method):
            raise RuntimeError("PPT timeline deck bridge is unavailable")
        return dict(method(title=title, max_slides=int(max_slides or 24), path=path) or {})

    def ppt_project_open(self, *, path: str) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        method = getattr(owner, "_ppt_project_open", None)
        if not callable(method):
            raise RuntimeError("PPT project bridge is unavailable")
        return dict(method(path=Path(path)) or {})

    def ppt_project_save(self, *, path: str = "") -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_project_save", None)
        if not callable(method):
            raise RuntimeError("PPT project bridge is unavailable")
        return dict(method(path=Path(path) if str(path or "").strip() else "") or {})

    def ppt_project_save_as(self, *, path: str) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        method = getattr(owner, "_ppt_project_save_as", None)
        if not callable(method):
            raise RuntimeError("PPT project bridge is unavailable")
        return dict(method(path=Path(path)) or {})

    def ppt_deck_snapshot(self, *, include_metadata: bool = True) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_snapshot", None)
        if not callable(method):
            raise RuntimeError("PPT snapshot bridge is unavailable")
        return dict(method(include_metadata=bool(include_metadata)) or {})

    def ppt_deck_validate(self) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_validate", None)
        if not callable(method):
            raise RuntimeError("PPT validation bridge is unavailable")
        return dict(method() or {})

    def ppt_deck_import_pptx(self, *, path: str, asset_dir: str = "") -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        method = getattr(owner, "_ppt_import_pptx", None)
        if not callable(method):
            raise RuntimeError("PPTX import bridge is unavailable")
        return dict(method(path=path, asset_dir=asset_dir) or {})

    def ppt_deck_actor_posters_generate(self, *, force: bool = False) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_generate_actor_posters", None)
        if not callable(method):
            raise RuntimeError("PPT actor poster bridge is unavailable")
        return dict(method(force=bool(force)) or {})

    def ppt_deck_export_pptx(self, *, path: str) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        method = getattr(owner, "_ppt_export_deck_pptx", None)
        if not callable(method):
            raise RuntimeError("PPT deck export bridge is unavailable")
        return dict(method(path=Path(path)) or {})

    def ppt_deck_export_pdf(
        self,
        *,
        path: str,
        backend: str = "auto",
        timeout_sec: int = 90,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        method = getattr(owner, "_ppt_export_deck_pdf", None)
        if not callable(method):
            raise RuntimeError("PPT deck export bridge is unavailable")
        return dict(method(path=Path(path), backend=backend, timeout_sec=int(timeout_sec)) or {})

    def ppt_deck_export_video(
        self,
        *,
        path: str,
        fps: int = 30,
        width: int = 1280,
        height: int = 720,
        audio_path: str = "",
        audio_bitrate: str = "192k",
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        method = getattr(owner, "_ppt_export_deck_video", None)
        if not callable(method):
            raise RuntimeError("PPT deck export bridge is unavailable")
        return dict(
            method(
                path=Path(path),
                fps=int(fps),
                width=int(width),
                height=int(height),
                audio_path=str(audio_path or ""),
                audio_bitrate=str(audio_bitrate or "192k"),
            )
            or {}
        )

    def ppt_deck_history(self) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_history_status", None)
        if not callable(method):
            raise RuntimeError("PPT history bridge is unavailable")
        return dict(method() or {})

    def ppt_deck_undo(self) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_undo", None)
        if not callable(method):
            raise RuntimeError("PPT undo bridge is unavailable")
        return dict(method() or {})

    def ppt_deck_redo(self) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_redo", None)
        if not callable(method):
            raise RuntimeError("PPT redo bridge is unavailable")
        return dict(method() or {})

    def ppt_deck_autosave(self) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_autosave", None)
        if not callable(method):
            raise RuntimeError("PPT autosave bridge is unavailable")
        return dict(method() or {})

    def ppt_deck_recovery_list(self, *, limit: int = 20) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_recovery_list", None)
        if not callable(method):
            raise RuntimeError("PPT recovery list bridge is unavailable")
        return dict(method(limit=int(limit or 20)) or {})

    def ppt_deck_recovery_open(self, *, path: str = "") -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_recovery_open", None)
        if not callable(method):
            raise RuntimeError("PPT recovery open bridge is unavailable")
        return dict(method(path=path) or {})

    def ppt_deck_recovery_delete(self, *, path: str) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        method = getattr(owner, "_ppt_recovery_delete", None)
        if not callable(method):
            raise RuntimeError("PPT recovery delete bridge is unavailable")
        return dict(method(path=path) or {})

    def ppt_media_pool_list(self) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_media_pool_list", None)
        if not callable(method):
            raise RuntimeError("PPT media pool bridge is unavailable")
        return dict(method() or {})

    def ppt_media_pool_add(
        self,
        *,
        path: str,
        kind: str | None = None,
        name: str = "",
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        method = getattr(owner, "_ppt_media_pool_add", None)
        if not callable(method):
            raise RuntimeError("PPT media pool bridge is unavailable")
        return dict(method(path=path, kind=kind, name=name) or {})

    def ppt_media_pool_insert(
        self,
        *,
        asset_id: str,
        slide_id: str = "",
        x: float = 0.18,
        y: float = 0.24,
        w: float | None = None,
        h: float | None = None,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(asset_id or "").strip():
            raise RuntimeError("asset_id is required")
        method = getattr(owner, "_ppt_media_pool_insert", None)
        if not callable(method):
            raise RuntimeError("PPT media pool bridge is unavailable")
        return dict(method(asset_id=asset_id, slide_id=slide_id, x=x, y=y, w=w, h=h) or {})

    def ppt_media_pool_remove(self, *, asset_id: str) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(asset_id or "").strip():
            raise RuntimeError("asset_id is required")
        method = getattr(owner, "_ppt_media_pool_remove", None)
        if not callable(method):
            raise RuntimeError("PPT media pool bridge is unavailable")
        return dict(method(asset_id=asset_id) or {})

    def ppt_add_slide(
        self,
        *,
        title: str = "",
        layout_id: str = "blank",
        duration_ms: int = 5000,
        index: int | None = None,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_add_slide", None)
        if not callable(method):
            raise RuntimeError("PPT slide bridge is unavailable")
        return dict(method(title=title, layout_id=layout_id, duration_ms=int(duration_ms), index=index) or {})

    def ppt_duplicate_slide(self, *, slide_id: str = "", index: int | None = None) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_duplicate_slide", None)
        if not callable(method):
            raise RuntimeError("PPT slide bridge is unavailable")
        return dict(method(slide_id=slide_id, index=index) or {})

    def ppt_delete_slide(self, *, slide_id: str = "") -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_delete_slide", None)
        if not callable(method):
            raise RuntimeError("PPT slide bridge is unavailable")
        return dict(method(slide_id=slide_id) or {})

    def ppt_move_slide(self, *, slide_id: str, index: int) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(slide_id or "").strip():
            raise RuntimeError("slide_id is required")
        method = getattr(owner, "_ppt_move_slide", None)
        if not callable(method):
            raise RuntimeError("PPT slide bridge is unavailable")
        return dict(method(slide_id=slide_id, index=int(index)) or {})

    def ppt_update_slide(
        self,
        *,
        slide_id: str = "",
        title: str | None = None,
        layout_id: str | None = None,
        duration_ms: int | None = None,
        speaker_notes: str | None = None,
        transition: str | None = None,
        background: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_update_slide", None)
        if not callable(method):
            raise RuntimeError("PPT slide bridge is unavailable")
        return dict(
            method(
                slide_id=slide_id,
                title=title,
                layout_id=layout_id,
                duration_ms=None if duration_ms is None else int(duration_ms),
                speaker_notes=speaker_notes,
                transition=transition,
                background=background,
                metadata=metadata,
            )
            or {}
        )

    def ppt_set_slide_layout(self, *, layout_id: str, slide_id: str = "") -> dict[str, Any]:
        if not str(layout_id or "").strip():
            raise RuntimeError("layout_id is required")
        return self.ppt_update_slide(slide_id=slide_id, layout_id=layout_id)

    def ppt_set_slide_duration(self, *, duration_ms: int, slide_id: str = "") -> dict[str, Any]:
        return self.ppt_update_slide(slide_id=slide_id, duration_ms=int(duration_ms))

    def ppt_set_slide_notes(self, *, speaker_notes: str, slide_id: str = "") -> dict[str, Any]:
        return self.ppt_update_slide(slide_id=slide_id, speaker_notes=str(speaker_notes))

    def ppt_animation_lanes_list(self, *, slide_id: str = "") -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_animation_lanes_list", None)
        if not callable(method):
            raise RuntimeError("PPT animation lane bridge is unavailable")
        return dict(method(slide_id=slide_id) or {})

    def ppt_timeline_select_slide(self, *, slide_id: str) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(slide_id or "").strip():
            raise RuntimeError("slide_id is required")
        method = getattr(owner, "_ppt_timeline_select_slide", None)
        if not callable(method):
            raise RuntimeError("PPT timeline bridge is unavailable")
        return dict(method(slide_id=slide_id) or {})

    def ppt_timeline_set_playhead(
        self,
        *,
        time_ms: int | None = None,
        slide_id: str = "",
        local_ms: int | None = None,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_timeline_set_playhead", None)
        if not callable(method):
            raise RuntimeError("PPT timeline bridge is unavailable")
        return dict(
            method(
                time_ms=None if time_ms is None else int(time_ms),
                slide_id=slide_id,
                local_ms=None if local_ms is None else int(local_ms),
            )
            or {}
        )

    def ppt_timeline_play_preview(self, *, mode: str = "toggle") -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_timeline_play_preview", None)
        if not callable(method):
            raise RuntimeError("PPT timeline bridge is unavailable")
        return dict(method(mode=mode) or {})

    def ppt_delete_element(self, *, element_id: str, slide_id: str = "") -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(element_id or "").strip():
            raise RuntimeError("element_id is required")
        method = getattr(owner, "_ppt_delete_element", None)
        if not callable(method):
            raise RuntimeError("PPT element delete bridge is unavailable")
        return dict(method(element_id=element_id, slide_id=slide_id) or {})

    def ppt_add_text_element(
        self,
        *,
        text: str = "Text",
        slide_id: str = "",
        x: float = 0.12,
        y: float = 0.18,
        w: float = 0.62,
        h: float = 0.12,
        font_size: int = 28,
        color: str = "#182033",
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_add_text_element", None)
        if not callable(method):
            raise RuntimeError("PPT text element bridge is unavailable")
        return dict(method(text=text, slide_id=slide_id, x=x, y=y, w=w, h=h, font_size=int(font_size), color=color) or {})

    def ppt_add_video_element(
        self,
        *,
        path: str,
        slide_id: str = "",
        x: float = 0.18,
        y: float = 0.24,
        w: float | None = None,
        h: float | None = None,
    ) -> dict[str, Any]:
        return self.ppt_add_media_asset(path=path, slide_id=slide_id, x=x, y=y, w=w, h=h, kind="video_actor")

    def ppt_add_shape_element(
        self,
        *,
        slide_id: str = "",
        x: float = 0.18,
        y: float = 0.24,
        w: float = 0.34,
        h: float = 0.24,
        fill: str = "#F7F9FC",
        stroke: str = "#2F6FED",
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_add_shape_element", None)
        if not callable(method):
            raise RuntimeError("PPT shape element bridge is unavailable")
        return dict(method(slide_id=slide_id, x=x, y=y, w=w, h=h, fill=fill, stroke=stroke) or {})

    def ppt_add_chart_element(
        self,
        *,
        slide_id: str = "",
        x: float = 0.48,
        y: float = 0.28,
        w: float = 0.34,
        h: float = 0.32,
        chart_type: str = "bar",
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_add_chart_element", None)
        if not callable(method):
            raise RuntimeError("PPT chart element bridge is unavailable")
        return dict(method(slide_id=slide_id, x=x, y=y, w=w, h=h, chart_type=chart_type) or {})

    def ppt_duplicate_element(self, *, element_id: str, slide_id: str = "") -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(element_id or "").strip():
            raise RuntimeError("element_id is required")
        method = getattr(owner, "_ppt_duplicate_element", None)
        if not callable(method):
            raise RuntimeError("PPT element duplicate bridge is unavailable")
        return dict(method(element_id=element_id, slide_id=slide_id) or {})

    def ppt_set_element_z_order(self, *, element_id: str, mode: str = "front", slide_id: str = "") -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(element_id or "").strip():
            raise RuntimeError("element_id is required")
        method = getattr(owner, "_ppt_set_element_z_order", None)
        if not callable(method):
            raise RuntimeError("PPT element layer bridge is unavailable")
        return dict(method(element_id=element_id, mode=mode, slide_id=slide_id) or {})

    def ppt_align_element(
        self,
        *,
        element_id: str,
        slide_id: str = "",
        horizontal: str = "",
        vertical: str = "",
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(element_id or "").strip():
            raise RuntimeError("element_id is required")
        method = getattr(owner, "_ppt_align_element", None)
        if not callable(method):
            raise RuntimeError("PPT element align bridge is unavailable")
        return dict(method(element_id=element_id, slide_id=slide_id, horizontal=horizontal, vertical=vertical) or {})

    def ppt_arrange_element(
        self,
        *,
        element_id: str,
        slide_id: str = "",
        mode: str = "",
        horizontal: str = "",
        vertical: str = "",
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if str(mode or "").strip():
            result = self.ppt_set_element_z_order(element_id=element_id, slide_id=slide_id, mode=mode)
        if str(horizontal or "").strip() or str(vertical or "").strip():
            result = self.ppt_align_element(element_id=element_id, slide_id=slide_id, horizontal=horizontal, vertical=vertical)
        if not result:
            result = self.ppt_update_element(element_id=element_id, slide_id=slide_id)
        result["schema"] = "tigercapture.ppt.element_arranged.v1"
        result["arrange"] = {"mode": mode, "horizontal": horizontal, "vertical": vertical}
        return result

    def ppt_update_element(
        self,
        *,
        element_id: str,
        slide_id: str = "",
        name: str | None = None,
        text: str | None = None,
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
        rotation: float | None = None,
        opacity: float | None = None,
        visible: bool | None = None,
        style: dict[str, Any] | None = None,
        animation: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(element_id or "").strip():
            raise RuntimeError("element_id is required")
        method = getattr(owner, "_ppt_update_element", None)
        if not callable(method):
            raise RuntimeError("PPT element update bridge is unavailable")
        return dict(
            method(
                element_id=element_id,
                slide_id=slide_id,
                name=name,
                text=text,
                x=x,
                y=y,
                w=w,
                h=h,
                rotation=rotation,
                opacity=opacity,
                visible=visible,
                style=style,
                animation=animation,
                metadata=metadata,
            )
            or {}
        )

    def ppt_set_element_animation(
        self,
        *,
        element_id: str,
        slide_id: str = "",
        in_animation: str = "none",
        out_animation: str = "none",
        trigger: str = "on_slide_start",
        start_ms: int = 0,
        duration_ms: int = 450,
        click_index: int = 0,
        easing: str = "ease_out",
        motion_x: float = 0.0,
        motion_y: float = 0.0,
        scale: float = 1.0,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(element_id or "").strip():
            raise RuntimeError("element_id is required")
        method = getattr(owner, "_ppt_set_element_animation", None)
        if not callable(method):
            raise RuntimeError("PPT animation bridge is unavailable")
        return dict(
            method(
                element_id=element_id,
                slide_id=slide_id,
                in_animation=in_animation,
                out_animation=out_animation,
                trigger=trigger,
                start_ms=int(start_ms),
                duration_ms=int(duration_ms),
                click_index=int(click_index),
                easing=easing,
                motion_x=float(motion_x),
                motion_y=float(motion_y),
                scale=float(scale),
            )
            or {}
        )

    def ppt_set_table_data(
        self,
        *,
        element_id: str,
        cells: list[list[Any]],
        slide_id: str = "",
        header: bool | None = None,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(element_id or "").strip():
            raise RuntimeError("element_id is required")
        method = getattr(owner, "_ppt_set_table_data", None)
        if not callable(method):
            raise RuntimeError("PPT table data bridge is unavailable")
        return dict(method(element_id=element_id, cells=cells, slide_id=slide_id, header=header) or {})

    def ppt_set_chart_data(
        self,
        *,
        element_id: str,
        labels: list[Any],
        values: list[Any],
        slide_id: str = "",
        chart_type: str = "bar",
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(element_id or "").strip():
            raise RuntimeError("element_id is required")
        method = getattr(owner, "_ppt_set_chart_data", None)
        if not callable(method):
            raise RuntimeError("PPT chart data bridge is unavailable")
        return dict(
            method(
                element_id=element_id,
                labels=labels,
                values=values,
                slide_id=slide_id,
                chart_type=chart_type,
            )
            or {}
        )

    def ppt_summary(self, *, max_slides: int = 24) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        from app.pptgen.editor_bridge import deck_from_editor_timeline, timeline_clip_summaries

        clips = timeline_clip_summaries(owner, max_clips=max(1, int(max_slides or 24)))
        deck = deck_from_editor_timeline(owner, max_slides=max(1, int(max_slides or 24)))
        return {
            "schema": "tigercapture.actions.ppt.summary.v1",
            "timeline_clip_count": len(clips),
            "slide_count": len(deck.slides),
            "title": deck.title,
            "slides": [
                {"id": slide.id, "title": slide.title, "duration_ms": int(slide.duration_ms)}
                for slide in deck.slides
            ],
        }

    def ppt_open_generator(self, *, import_timeline: bool = False) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        opener = getattr(owner, "_open_ppt_generator", None)
        if not callable(opener):
            raise RuntimeError("PPT generator workflow is unavailable")
        return dict(opener(import_timeline=bool(import_timeline)) or {})

    def ppt_export_timeline(
        self,
        *,
        path: str,
        title: str = "Timeline Presentation",
        max_slides: int = 24,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        exporter = getattr(owner, "_export_timeline_pptx", None)
        if callable(exporter):
            return dict(exporter(Path(path), title=title, max_slides=max_slides) or {})
        from app.pptgen.actor_posters import ensure_deck_actor_posters
        from app.pptgen.editor_bridge import deck_from_editor_timeline
        from app.pptgen.writer_python_pptx import write_pptx_compatible

        deck = deck_from_editor_timeline(owner, title=title, max_slides=max_slides)
        ensure_deck_actor_posters(deck)
        out = write_pptx_compatible(deck, Path(path))
        return {
            "schema": "tigercapture.actions.ppt.timeline_export.v1",
            "path": str(out),
            "slide_count": len(deck.slides),
            "title": deck.title,
        }

    def ppt_export_timeline_pdf(
        self,
        *,
        path: str,
        title: str = "Timeline Presentation",
        max_slides: int = 24,
        backend: str = "auto",
        timeout_sec: int = 90,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        exporter = getattr(owner, "_export_timeline_pdf", None)
        if callable(exporter):
            return dict(
                exporter(
                    Path(path),
                    title=title,
                    max_slides=max_slides,
                    backend=backend,
                    timeout_sec=timeout_sec,
                )
                or {}
            )
        from app.pptgen.actor_posters import ensure_deck_actor_posters
        from app.pptgen.editor_bridge import deck_from_editor_timeline
        from app.pptgen.pdf_export import export_deck_pdf

        deck = deck_from_editor_timeline(owner, title=title, max_slides=max_slides)
        ensure_deck_actor_posters(deck)
        result = export_deck_pdf(deck, Path(path), backend=backend, timeout_sec=timeout_sec)
        if not result.get("ok"):
            raise RuntimeError(str(result.get("reason") or "PDF export failed"))
        return {
            "schema": "tigercapture.actions.ppt.timeline_pdf_export.v1",
            "path": str(result.get("output_pdf") or path),
            "slide_count": len(deck.slides),
            "title": deck.title,
            "backend": str(result.get("backend") or ""),
            "attempts": list(result.get("attempts") or []),
        }

    def ppt_export_timeline_video(
        self,
        *,
        path: str,
        title: str = "Timeline Presentation",
        max_slides: int = 24,
        fps: int = 30,
        width: int = 1280,
        height: int = 720,
        audio_path: str = "",
        audio_bitrate: str = "192k",
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        exporter = getattr(owner, "_export_timeline_video", None)
        if callable(exporter):
            return dict(
                exporter(
                    Path(path),
                    title=title,
                    max_slides=max_slides,
                    fps=int(fps),
                    width=int(width),
                    height=int(height),
                    audio_path=str(audio_path or ""),
                    audio_bitrate=str(audio_bitrate or "192k"),
                )
                or {}
            )
        from app.pptgen.actor_posters import ensure_deck_actor_posters
        from app.pptgen.editor_bridge import deck_from_editor_timeline
        from app.pptgen.video_export import export_deck_video

        deck = deck_from_editor_timeline(owner, title=title, max_slides=max_slides)
        ensure_deck_actor_posters(deck)
        result = export_deck_video(
            deck,
            Path(path),
            fps=int(fps),
            size=(int(width), int(height)),
            audio_path=str(audio_path or "") or None,
            audio_bitrate=str(audio_bitrate or "192k"),
        )
        if not result.get("ok"):
            raise RuntimeError("PPT video export failed")
        return {
            "schema": "tigercapture.ppt.timeline_video_export.v1",
            "path": str(result.get("output_path") or path),
            "slide_count": len(deck.slides),
            "title": deck.title,
            "fps": int(result.get("fps") or fps),
            "size": list(result.get("size") or [width, height]),
            "frames_written": int(result.get("frames_written") or 0),
            "duration_ms": int(result.get("duration_ms") or 0),
            "transition_count": int(result.get("transition_count") or 0),
            "audio_path": str(result.get("audio_path") or ""),
            "audio_muxed": bool(result.get("audio_muxed")),
        }

    def ppt_add_media_asset(
        self,
        *,
        path: str,
        slide_id: str = "",
        x: float = 0.18,
        y: float = 0.24,
        w: float | None = None,
        h: float | None = None,
        kind: str | None = None,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        method = getattr(owner, "_ppt_add_media_asset", None)
        if not callable(method):
            raise RuntimeError("PPT media bridge is unavailable")
        return dict(method(path, slide_id=slide_id, x=x, y=y, w=w, h=h, kind=kind) or {})

    def ppt_load_image(
        self,
        *,
        path: str,
        slide_id: str = "",
        element_id: str = "",
        x: float = 0.18,
        y: float = 0.24,
        w: float | None = None,
        h: float | None = None,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(path or "").strip():
            raise RuntimeError("path is required")
        method = getattr(owner, "_ppt_load_image", None)
        if not callable(method):
            raise RuntimeError("PPT image load bridge is unavailable")
        return dict(method(path, slide_id=slide_id, element_id=element_id, x=x, y=y, w=w, h=h) or {})

    def ppt_add_timeline_clip(
        self,
        *,
        track_id: int,
        clip_id: int,
        slide_id: str = "",
        x: float = 0.18,
        y: float = 0.24,
        w: float | None = None,
        h: float | None = None,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_add_timeline_clip", None)
        if not callable(method):
            raise RuntimeError("PPT timeline clip bridge is unavailable")
        return dict(
            method(
                track_id=int(track_id),
                clip_id=int(clip_id),
                slide_id=slide_id,
                x=x,
                y=y,
                w=w,
                h=h,
            )
            or {}
        )

    def ppt_add_timeline_clip_still(
        self,
        *,
        track_id: int | None = None,
        clip_id: int | None = None,
        slide_id: str = "",
        source_ms: int | None = None,
        x: float = 0.18,
        y: float = 0.24,
        w: float | None = None,
        h: float | None = None,
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        method = getattr(owner, "_ppt_add_timeline_clip_still", None)
        if not callable(method):
            raise RuntimeError("PPT timeline still bridge is unavailable")
        return dict(
            method(
                track_id=None if track_id is None else int(track_id),
                clip_id=None if clip_id is None else int(clip_id),
                slide_id=slide_id,
                source_ms=None if source_ms is None else int(source_ms),
                x=x,
                y=y,
                w=w,
                h=h,
            )
            or {}
        )

    def ppt_add_typography(
        self,
        *,
        text: str,
        slide_id: str = "",
        x: float = 0.21,
        y: float = 0.42,
        w: float = 0.58,
        h: float = 0.13,
        font_size: int = 34,
        color: str = "#182033",
    ) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            raise RuntimeError("no editor owner")
        if not str(text or "").strip():
            raise RuntimeError("text is required")
        method = getattr(owner, "_ppt_add_typography", None)
        if not callable(method):
            raise RuntimeError("PPT typography bridge is unavailable")
        return dict(
            method(
                text=text,
                slide_id=slide_id,
                x=x,
                y=y,
                w=w,
                h=h,
                font_size=font_size,
                color=color,
            )
            or {}
        )


__all__ = ["PptAdapterMixin"]
