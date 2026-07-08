"""User PPT generator workflow hooks for the main editor."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _flash(owner: Any, message: str) -> None:
    method = getattr(owner, "_flash_status", None)
    if callable(method):
        try:
            method(message)
        except Exception:
            pass


def _show_window(window: Any) -> None:
    show = getattr(window, "show", None)
    if callable(show):
        show()
    raise_ = getattr(window, "raise_", None)
    if callable(raise_):
        raise_()
    activate = getattr(window, "activateWindow", None)
    if callable(activate):
        activate()


def _ensure_ppt_generator_window(owner: Any):
    from app.pptgen.ui.window import PptGeneratorWindow

    window = getattr(owner, "_ppt_generator_window", None)
    if window is None:
        window = PptGeneratorWindow(source_owner=owner)
        setattr(owner, "_ppt_generator_window", window)
    return window


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _current_project_ms(owner: Any) -> int:
    player = getattr(owner, "_player", None)
    if player is None or not hasattr(player, "position"):
        return 0
    try:
        return max(0, _as_int(player.position()))
    except Exception:
        return 0


def _selected_video_clip_pair(owner: Any) -> tuple[int, int] | None:
    for raw in list(getattr(owner, "_selected_clips", []) or []):
        if isinstance(raw, dict):
            kind = str(raw.get("track_kind") or raw.get("kind") or "video").lower()
            if kind and kind != "video":
                continue
            return _as_int(raw.get("track_id")), _as_int(raw.get("clip_id"))
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            return _as_int(raw[0]), _as_int(raw[1])
    return None


def _resolve_timeline_clip_summary(
    owner: Any,
    *,
    track_id: int | None = None,
    clip_id: int | None = None,
):
    from app.pptgen.editor_bridge import timeline_clip_summaries

    clips = timeline_clip_summaries(owner, max_clips=10000)
    if not clips:
        raise RuntimeError("No timeline video clips are available")

    if track_id is not None or clip_id is not None:
        if track_id is None or clip_id is None:
            raise RuntimeError("track_id and clip_id must be provided together")
        wanted_track = int(track_id)
        wanted_clip = int(clip_id)
        match = next(
            (
                row
                for row in clips
                if int(row.track_id) == wanted_track and int(row.clip_id) == wanted_clip
            ),
            None,
        )
        if match is None:
            raise RuntimeError(f"timeline clip not found: track={wanted_track} clip={wanted_clip}")
        return match

    selected = _selected_video_clip_pair(owner)
    if selected is not None:
        wanted_track, wanted_clip = selected
        match = next(
            (
                row
                for row in clips
                if int(row.track_id) == wanted_track and int(row.clip_id) == wanted_clip
            ),
            None,
        )
        if match is not None:
            return match

    current_ms = _current_project_ms(owner)
    match = next(
        (
            row
            for row in clips
            if int(row.duration_ms) > 0
            and int(row.timeline_in_ms) <= current_ms < int(row.timeline_in_ms) + int(row.duration_ms)
        ),
        None,
    )
    return match or clips[0]


def _source_ms_for_still(match: Any, *, source_ms: int | None, project_ms: int) -> int:
    source_in = max(0, _as_int(getattr(match, "source_in_ms", 0)))
    duration = max(0, _as_int(getattr(match, "duration_ms", 0)))
    source_out = max(0, _as_int(getattr(match, "source_out_ms", 0)))
    if source_out <= source_in:
        source_out = source_in + duration
    upper = max(source_in + 1, source_out)
    if source_ms is not None:
        return max(source_in, min(upper - 1, _as_int(source_ms)))

    timeline_in = _as_int(getattr(match, "timeline_in_ms", 0))
    if duration > 0 and timeline_in <= project_ms < timeline_in + duration:
        return max(source_in, min(upper - 1, source_in + max(0, project_ms - timeline_in)))
    return source_in


def open_ppt_generator(self, *, import_timeline: bool = False) -> dict[str, Any]:
    from app.pptgen.editor_bridge import deck_from_editor_timeline

    deck = None
    if import_timeline:
        deck = deck_from_editor_timeline(self, title="Timeline Presentation")
    window = getattr(self, "_ppt_generator_window", None)
    created = window is None
    window = _ensure_ppt_generator_window(self)
    if deck is not None:
        window.set_deck(deck)
    _show_window(window)
    _flash(self, "PPT Generator opened")
    return {
        "schema": "tigercapture.ppt.open.v1",
        "opened": True,
        "created": bool(created),
        "imported_timeline": bool(import_timeline),
        "slide_count": len(getattr(window, "deck", None).slides) if getattr(window, "deck", None) is not None else 0,
    }


def create_ppt_project(
    self,
    *,
    template_id: str = "blank",
    title: str = "",
    path: str | Path = "",
) -> dict[str, Any]:
    from app.pptgen.project_io import save_deck_project
    from app.pptgen.templates import deck_from_template

    window = _ensure_ppt_generator_window(self)
    deck = deck_from_template(template_id or "blank", title=title or "")
    window.set_deck(deck)
    saved_path = ""
    if str(path or "").strip():
        target = save_deck_project(deck, path)
        window.project_path = target
        if hasattr(window, "_mark_saved"):
            window._mark_saved()
        saved_path = str(target)
    _show_window(window)
    _flash(self, f"Created PPT project: {deck.title}")
    return {
        "schema": "tigercapture.ppt.project_created.v1",
        "deck_id": deck.id,
        "title": deck.title,
        "template_id": str(template_id or "blank"),
        "slide_count": len(deck.slides),
        "path": saved_path,
    }


def create_ppt_deck_from_prompt(
    self,
    *,
    prompt: str,
    title: str = "",
    template_id: str = "title_body",
    max_slides: int = 4,
    path: str | Path = "",
) -> dict[str, Any]:
    from app.pptgen.project_io import save_deck_project
    from app.pptgen.prompt_deck import deck_from_prompt

    window = _ensure_ppt_generator_window(self)
    deck = deck_from_prompt(
        prompt,
        title=title,
        template_id=template_id or "title_body",
        max_slides=max(1, int(max_slides or 4)),
    )
    window.set_deck(deck)
    saved_path = ""
    if str(path or "").strip():
        target = save_deck_project(deck, path)
        window.project_path = target
        if hasattr(window, "_mark_saved"):
            window._mark_saved()
        saved_path = str(target)
    _show_window(window)
    _flash(self, f"Created prompt PPT deck: {deck.title}")
    return {
        "schema": "tigercapture.ppt.deck_from_prompt.v1",
        "deck_id": deck.id,
        "title": deck.title,
        "template_id": str(template_id or "title_body"),
        "slide_count": len(deck.slides),
        "path": saved_path,
    }


def create_ppt_deck_from_timeline(
    self,
    *,
    title: str = "Timeline Presentation",
    max_slides: int = 24,
    path: str | Path = "",
) -> dict[str, Any]:
    from app.pptgen.actor_posters import ensure_deck_actor_posters
    from app.pptgen.editor_bridge import deck_from_editor_timeline
    from app.pptgen.project_io import save_deck_project

    window = _ensure_ppt_generator_window(self)
    deck = deck_from_editor_timeline(self, title=title or "Timeline Presentation", max_slides=max(1, int(max_slides or 24)))
    ensure_deck_actor_posters(deck)
    window.set_deck(deck)
    saved_path = ""
    if str(path or "").strip():
        target = save_deck_project(deck, path)
        window.project_path = target
        if hasattr(window, "_mark_saved"):
            window._mark_saved()
        saved_path = str(target)
    _show_window(window)
    _flash(self, f"Created timeline PPT deck: {deck.title}")
    return {
        "schema": "tigercapture.ppt.deck_from_timeline.v1",
        "deck_id": deck.id,
        "title": deck.title,
        "slide_count": len(deck.slides),
        "path": saved_path,
    }


def open_ppt_project(self, *, path: str | Path) -> dict[str, Any]:
    from app.pptgen.project_io import load_deck_project

    if not str(path or "").strip():
        raise RuntimeError("path is required")
    window = _ensure_ppt_generator_window(self)
    deck = load_deck_project(path)
    window.set_deck(deck, project_path=path)
    _show_window(window)
    _flash(self, f"Opened PPT project: {Path(path).name}")
    return {
        "schema": "tigercapture.ppt.project_opened.v1",
        "path": str(Path(path)),
        "deck_id": deck.id,
        "title": deck.title,
        "slide_count": len(deck.slides),
    }


def save_ppt_project(self, *, path: str | Path = "") -> dict[str, Any]:
    from app.pptgen.project_io import save_deck_project

    window = _ensure_ppt_generator_window(self)
    target = Path(path) if str(path or "").strip() else getattr(window, "project_path", None)
    if target is None:
        raise RuntimeError("path is required for an unsaved PPT project")
    saved = save_deck_project(window.deck, target)
    window.project_path = saved
    if hasattr(window, "_mark_saved"):
        window._mark_saved()
    _flash(self, f"Saved PPT project: {saved.name}")
    return {
        "schema": "tigercapture.ppt.project_saved.v1",
        "path": str(saved),
        "deck_id": window.deck.id,
        "title": window.deck.title,
        "slide_count": len(window.deck.slides),
    }


def save_ppt_project_as(self, *, path: str | Path) -> dict[str, Any]:
    if not str(path or "").strip():
        raise RuntimeError("path is required")
    return save_ppt_project(self, path=path)


def add_media_asset_to_ppt(
    self,
    path: str | Path,
    *,
    slide_id: str = "",
    x: float = 0.18,
    y: float = 0.24,
    w: float | None = None,
    h: float | None = None,
    kind: str | None = None,
) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    element = window.add_media_asset_to_slide(path, slide_id=slide_id, x=x, y=y, w=w, h=h, kind=kind, source="editor_action")
    _show_window(window)
    _flash(self, f"Added PPT asset: {Path(path).name}")
    return {
        "schema": "tigercapture.ppt.asset_added.v1",
        "element_id": element.id,
        "kind": element.kind,
        "source_path": str(path),
        "slide_id": window.timeline.selected_slide_id,
        "slide_count": len(window.deck.slides),
    }


def add_text_element_to_ppt(
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
    from app.pptgen.editing import element_payload, unique_element_id
    from app.pptgen.schema import SlideElement

    window = _ensure_ppt_generator_window(self)
    slide = window.deck.slide_by_id(slide_id) if slide_id else window._selected_slide()
    if slide is None:
        raise RuntimeError("No slide is available")
    element = SlideElement.text_box(
        unique_element_id(slide, f"{slide.id}-text"),
        str(text or "Text"),
        x=x,
        y=y,
        w=w,
        h=h,
        font_size=int(font_size or 28),
        color=str(color or "#182033"),
    )
    slide.add_element(element)
    window.timeline.select_slide(slide.id)
    window.selected_element_id = element.id
    window._refresh_selected()
    window._commit_history("Add text")
    _show_window(window)
    _flash(self, "Added PPT text")
    return {
        "schema": "tigercapture.ppt.element_added.v1",
        "slide_id": slide.id,
        "element": element_payload(element),
        "slide_count": len(window.deck.slides),
    }


def add_shape_element_to_ppt(
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
    from app.pptgen.editing import element_payload, unique_element_id
    from app.pptgen.schema import ElementStyle, SlideElement

    window = _ensure_ppt_generator_window(self)
    slide = window.deck.slide_by_id(slide_id) if slide_id else window._selected_slide()
    if slide is None:
        raise RuntimeError("No slide is available")
    element = SlideElement(
        id=unique_element_id(slide, f"{slide.id}-shape"),
        kind="shape",
        name="Shape",
        x=x,
        y=y,
        w=w,
        h=h,
        style=ElementStyle(fill=fill, stroke=stroke, stroke_width=1.0),
    )
    slide.add_element(element)
    window.timeline.select_slide(slide.id)
    window.selected_element_id = element.id
    window._refresh_selected()
    window._commit_history("Add shape")
    _show_window(window)
    _flash(self, "Added PPT shape")
    return {
        "schema": "tigercapture.ppt.element_added.v1",
        "slide_id": slide.id,
        "element": element_payload(element),
        "slide_count": len(window.deck.slides),
    }


def add_chart_element_to_ppt(
    self,
    *,
    slide_id: str = "",
    x: float = 0.48,
    y: float = 0.28,
    w: float = 0.34,
    h: float = 0.32,
    chart_type: str = "bar",
) -> dict[str, Any]:
    from app.pptgen.editing import element_payload, unique_element_id
    from app.pptgen.schema import SlideElement

    window = _ensure_ppt_generator_window(self)
    slide = window.deck.slide_by_id(slide_id) if slide_id else window._selected_slide()
    if slide is None:
        raise RuntimeError("No slide is available")
    element = SlideElement.chart(unique_element_id(slide, f"{slide.id}-chart"), x=x, y=y, w=w, h=h)
    element.metadata["chart_type"] = str(chart_type or "bar")
    slide.add_element(element)
    window.timeline.select_slide(slide.id)
    window.selected_element_id = element.id
    window._refresh_selected()
    window._commit_history("Add chart")
    _show_window(window)
    _flash(self, "Added PPT chart")
    return {
        "schema": "tigercapture.ppt.element_added.v1",
        "slide_id": slide.id,
        "element": element_payload(element),
        "slide_count": len(window.deck.slides),
    }


def load_image_to_ppt(
    self,
    path: str | Path,
    *,
    slide_id: str = "",
    element_id: str = "",
    x: float = 0.18,
    y: float = 0.24,
    w: float | None = None,
    h: float | None = None,
) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    element = window.add_image_file_to_slide(
        path,
        slide_id=slide_id,
        replace_element_id=element_id,
        x=x,
        y=y,
        w=w,
        h=h,
    )
    _show_window(window)
    _flash(self, f"Loaded PPT image: {Path(path).name}")
    return {
        "schema": "tigercapture.ppt.image_loaded.v1",
        "element_id": element.id,
        "kind": element.kind,
        "source_path": element.source_path,
        "slide_id": window.timeline.selected_slide_id,
        "slide_count": len(window.deck.slides),
        "replaced": bool(element_id),
    }


def add_typography_to_ppt(
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
    window = _ensure_ppt_generator_window(self)
    element = window.add_typography_to_slide(
        {"text": text, "style": {"font_size": int(font_size), "color": color}},
        slide_id=slide_id,
        x=x,
        y=y,
        w=w,
        h=h,
        source="editor_action",
    )
    _show_window(window)
    _flash(self, "Added PPT typography")
    return {
        "schema": "tigercapture.ppt.typography_added.v1",
        "element_id": element.id,
        "kind": element.kind,
        "text": element.text,
        "slide_id": window.timeline.selected_slide_id,
        "slide_count": len(window.deck.slides),
    }


def add_timeline_clip_to_ppt(
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
    from app.pptgen.editor_bridge import timeline_clip_summaries

    wanted_track = int(track_id)
    wanted_clip = int(clip_id)
    match = next(
        (
            row
            for row in timeline_clip_summaries(self, max_clips=10000)
            if int(row.track_id) == wanted_track and int(row.clip_id) == wanted_clip
        ),
        None,
    )
    if match is None:
        raise RuntimeError(f"timeline clip not found: track={wanted_track} clip={wanted_clip}")
    window = _ensure_ppt_generator_window(self)
    element = window.add_media_asset_to_slide(
        match.source_path or match.source_name,
        slide_id=slide_id,
        x=x,
        y=y,
        w=w,
        h=h,
        kind="video_actor",
        source="timeline_clip",
    )
    element.metadata.update(
        {
            "track_id": match.track_id,
            "clip_id": match.clip_id,
            "timeline_in_ms": match.timeline_in_ms,
            "duration_ms": match.duration_ms,
            "source_in_ms": match.source_in_ms,
            "source_out_ms": match.source_out_ms,
        }
    )
    window._refresh_selected()
    _show_window(window)
    _flash(self, f"Added timeline clip to PPT: {match.source_name}")
    return {
        "schema": "tigercapture.ppt.timeline_clip_added.v1",
        "element_id": element.id,
        "kind": element.kind,
        "source_path": match.source_path,
        "track_id": match.track_id,
        "clip_id": match.clip_id,
        "slide_id": window.timeline.selected_slide_id,
        "slide_count": len(window.deck.slides),
    }


def add_timeline_clip_still_to_ppt(
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
    from app.pptgen.frame_extract import extract_video_still

    match = _resolve_timeline_clip_summary(self, track_id=track_id, clip_id=clip_id)
    raw_source_path = str(getattr(match, "source_path", "") or "").strip()
    if not raw_source_path:
        raise RuntimeError("Selected timeline clip has no source video path")
    source_path = Path(raw_source_path)
    project_ms = _current_project_ms(self)
    capture_ms = _source_ms_for_still(match, source_ms=source_ms, project_ms=project_ms)
    still_path = extract_video_still(source_path, source_ms=capture_ms)

    window = _ensure_ppt_generator_window(self)
    element = window.add_image_file_to_slide(still_path, slide_id=slide_id, x=x, y=y, w=w, h=h)
    element.name = f"Still - {getattr(match, 'source_name', source_path.name)}"
    element.metadata.update(
        {
            "source": "editor_timeline_still",
            "track_id": int(getattr(match, "track_id", 0)),
            "clip_id": int(getattr(match, "clip_id", 0)),
            "timeline_in_ms": int(getattr(match, "timeline_in_ms", 0)),
            "duration_ms": int(getattr(match, "duration_ms", 0)),
            "source_in_ms": int(getattr(match, "source_in_ms", 0)),
            "source_out_ms": int(getattr(match, "source_out_ms", 0)),
            "source_video_path": str(source_path),
            "source_ms": int(capture_ms),
            "project_ms": int(project_ms),
            "still_image_path": str(still_path),
        }
    )
    window._refresh_selected()
    _show_window(window)
    _flash(self, f"Added timeline still to PPT: {Path(still_path).name}")
    return {
        "schema": "tigercapture.ppt.timeline_clip_still_added.v1",
        "element_id": element.id,
        "kind": element.kind,
        "source_path": str(still_path),
        "source_video_path": str(source_path),
        "source_ms": int(capture_ms),
        "track_id": int(getattr(match, "track_id", 0)),
        "clip_id": int(getattr(match, "clip_id", 0)),
        "slide_id": window.timeline.selected_slide_id,
        "slide_count": len(window.deck.slides),
    }


def apply_template_to_ppt(self, *, template_id: str) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    slide = window.apply_template_to_current_slide(template_id)
    _show_window(window)
    _flash(self, f"Applied PPT template: {template_id}")
    return {
        "schema": "tigercapture.ppt.template_applied.v1",
        "template_id": str(template_id),
        "slide_id": slide.id,
        "layout_id": slide.layout_id,
        "element_count": len(slide.elements),
        "slide_count": len(window.deck.slides),
    }


def snapshot_ppt(self, *, include_metadata: bool = True) -> dict[str, Any]:
    from app.pptgen.editing import deck_snapshot

    window = _ensure_ppt_generator_window(self)
    return deck_snapshot(
        window.deck,
        selected_slide_id=str(getattr(window.timeline, "selected_slide_id", "") or ""),
        include_metadata=bool(include_metadata),
    )


def validate_ppt_deck(self) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    method = getattr(window, "validate_deck_report", None)
    if not callable(method):
        raise RuntimeError("PPT validation is unavailable")
    return dict(method() or {})


def _refresh_ppt_window_after_slide_edit(window: Any, *, selected_slide_id: str, history_label: str) -> None:
    from app.pptgen.timeline import PptTimeline

    window.timeline = PptTimeline.from_deck(window.deck)
    if selected_slide_id:
        window.timeline.select_slide(selected_slide_id)
    window.selected_element_id = ""
    window._refresh_all()
    window._commit_history(history_label)


def add_ppt_slide(
    self,
    *,
    title: str = "",
    layout_id: str = "blank",
    duration_ms: int = 5000,
    index: int | None = None,
) -> dict[str, Any]:
    from app.pptgen.editing import add_deck_slide, slide_payload

    window = _ensure_ppt_generator_window(self)
    slide = add_deck_slide(window.deck, title=title, layout_id=layout_id, duration_ms=duration_ms, index=index)
    _refresh_ppt_window_after_slide_edit(window, selected_slide_id=slide.id, history_label="Add slide")
    _show_window(window)
    _flash(self, f"Added PPT slide: {slide.title or slide.id}")
    return {
        "schema": "tigercapture.ppt.slide_added.v1",
        "slide": slide_payload(slide),
        "slide_count": len(window.deck.slides),
        "selected_slide_id": slide.id,
    }


def duplicate_ppt_slide(self, *, slide_id: str = "", index: int | None = None) -> dict[str, Any]:
    from app.pptgen.editing import duplicate_slide, slide_payload

    window = _ensure_ppt_generator_window(self)
    target_id = str(slide_id or getattr(window.timeline, "selected_slide_id", "") or "").strip()
    slide = duplicate_slide(window.deck, target_id, index=index)
    _refresh_ppt_window_after_slide_edit(window, selected_slide_id=slide.id, history_label="Duplicate slide")
    _show_window(window)
    _flash(self, f"Duplicated PPT slide: {slide.id}")
    return {
        "schema": "tigercapture.ppt.slide_duplicated.v1",
        "source_slide_id": target_id,
        "slide": slide_payload(slide),
        "slide_count": len(window.deck.slides),
        "selected_slide_id": slide.id,
    }


def delete_ppt_slide(self, *, slide_id: str = "") -> dict[str, Any]:
    from app.pptgen.editing import delete_slide

    window = _ensure_ppt_generator_window(self)
    target_id = str(slide_id or getattr(window.timeline, "selected_slide_id", "") or "").strip()
    result = delete_slide(window.deck, target_id)
    _refresh_ppt_window_after_slide_edit(
        window,
        selected_slide_id=str(result.get("selected_slide_id") or ""),
        history_label="Delete slide",
    )
    _show_window(window)
    _flash(self, f"Deleted PPT slide: {target_id}")
    return result


def move_ppt_slide(self, *, slide_id: str, index: int) -> dict[str, Any]:
    from app.pptgen.editing import move_deck_slide, slide_payload

    if not str(slide_id or "").strip():
        raise RuntimeError("slide_id is required")
    window = _ensure_ppt_generator_window(self)
    slide = move_deck_slide(window.deck, slide_id, index=index)
    _refresh_ppt_window_after_slide_edit(window, selected_slide_id=slide.id, history_label="Move slide")
    _show_window(window)
    _flash(self, f"Moved PPT slide: {slide.id}")
    return {
        "schema": "tigercapture.ppt.slide_moved.v1",
        "slide": slide_payload(slide),
        "index": window.deck.slides.index(slide),
        "slide_order": [row.id for row in window.deck.slides],
        "slide_count": len(window.deck.slides),
        "selected_slide_id": slide.id,
    }


def update_ppt_slide(
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
    from app.pptgen.editing import slide_payload, update_slide

    window = _ensure_ppt_generator_window(self)
    target_id = str(slide_id or getattr(window.timeline, "selected_slide_id", "") or "").strip()
    slide = update_slide(
        window.deck,
        target_id,
        title=title,
        layout_id=layout_id,
        duration_ms=duration_ms,
        speaker_notes=speaker_notes,
        transition=transition,
        background=background,
        metadata=metadata,
    )
    _refresh_ppt_window_after_slide_edit(window, selected_slide_id=slide.id, history_label="Update slide")
    _show_window(window)
    _flash(self, f"Updated PPT slide: {slide.id}")
    return {
        "schema": "tigercapture.ppt.slide_updated.v1",
        "slide": slide_payload(slide),
        "slide_count": len(window.deck.slides),
        "selected_slide_id": slide.id,
    }


def import_pptx_to_ppt(self, *, path: str, asset_dir: str = "") -> dict[str, Any]:
    from app.pptgen.import_pptx import import_pptx_deck

    if not str(path or "").strip():
        raise RuntimeError("path is required")
    window = _ensure_ppt_generator_window(self)
    deck = import_pptx_deck(path, asset_dir=asset_dir or None)
    window.set_deck(deck)
    window._dirty = True
    window._update_window_caption()
    _show_window(window)
    _flash(self, f"Imported PPTX: {Path(path).name}")
    return {
        "schema": "tigercapture.ppt.pptx_imported.v1",
        "path": str(path),
        "deck_id": deck.id,
        "title": deck.title,
        "slide_count": len(deck.slides),
        "asset_count": len(deck.assets),
    }


def generate_ppt_actor_posters(self, *, force: bool = False) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    method = getattr(window, "ensure_actor_posters", None)
    if not callable(method):
        raise RuntimeError("PPT actor poster generation is unavailable")
    result = dict(method(force=bool(force)) or {})
    _show_window(window)
    _flash(self, "Generated PPT actor posters")
    return result


def export_ppt_deck_pptx(self, *, path: str | Path) -> dict[str, Any]:
    from app.pptgen.actor_posters import ensure_deck_actor_posters
    from app.pptgen.writer_python_pptx import write_pptx_compatible

    if not str(path or "").strip():
        raise RuntimeError("path is required")
    window = _ensure_ppt_generator_window(self)
    ensure_deck_actor_posters(window.deck)
    out = write_pptx_compatible(window.deck, Path(path))
    _flash(self, f"Exported PPT deck: {out.name}")
    return {
        "schema": "tigercapture.ppt.deck_pptx_export.v1",
        "path": str(out),
        "slide_count": len(window.deck.slides),
        "title": window.deck.title,
    }


def export_ppt_deck_pdf(
    self,
    *,
    path: str | Path,
    backend: str = "auto",
    timeout_sec: int = 90,
) -> dict[str, Any]:
    from app.pptgen.actor_posters import ensure_deck_actor_posters
    from app.pptgen.pdf_export import export_deck_pdf

    if not str(path or "").strip():
        raise RuntimeError("path is required")
    window = _ensure_ppt_generator_window(self)
    ensure_deck_actor_posters(window.deck)
    result = export_deck_pdf(window.deck, Path(path), backend=backend, timeout_sec=timeout_sec)
    if not result.get("ok"):
        raise RuntimeError(str(result.get("reason") or "PDF export failed"))
    _flash(self, f"Exported PPT deck PDF: {Path(path).name}")
    return {
        "schema": "tigercapture.ppt.deck_pdf_export.v1",
        "path": str(result.get("output_pdf") or path),
        "slide_count": len(window.deck.slides),
        "title": window.deck.title,
        "backend": str(result.get("backend") or ""),
        "attempts": list(result.get("attempts") or []),
    }


def export_ppt_deck_video(
    self,
    *,
    path: str | Path,
    fps: int = 30,
    width: int = 1280,
    height: int = 720,
    audio_path: str = "",
    audio_bitrate: str = "192k",
) -> dict[str, Any]:
    from app.pptgen.actor_posters import ensure_deck_actor_posters
    from app.pptgen.video_export import export_deck_video

    if not str(path or "").strip():
        raise RuntimeError("path is required")
    window = _ensure_ppt_generator_window(self)
    ensure_deck_actor_posters(window.deck)
    result = export_deck_video(
        window.deck,
        Path(path),
        fps=fps,
        size=(width, height),
        audio_path=str(audio_path or "") or None,
        audio_bitrate=str(audio_bitrate or "192k"),
    )
    if not result.get("ok"):
        raise RuntimeError("PPT deck video export failed")
    _flash(self, f"Exported PPT deck video: {Path(path).name}")
    return {
        "schema": "tigercapture.ppt.deck_video_export.v1",
        "path": str(result.get("output_path") or path),
        "slide_count": len(window.deck.slides),
        "title": window.deck.title,
        "fps": int(result.get("fps") or fps),
        "size": list(result.get("size") or [width, height]),
        "frames_written": int(result.get("frames_written") or 0),
        "duration_ms": int(result.get("duration_ms") or 0),
        "transition_count": int(result.get("transition_count") or 0),
        "audio_path": str(result.get("audio_path") or ""),
        "audio_muxed": bool(result.get("audio_muxed")),
    }


def ppt_history_status(self) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    method = getattr(window, "ppt_history_status", None)
    if not callable(method):
        raise RuntimeError("PPT history is unavailable")
    return dict(method() or {})


def undo_ppt_edit(self) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    method = getattr(window, "undo_deck_edit", None)
    if not callable(method):
        raise RuntimeError("PPT undo is unavailable")
    result = dict(method() or {})
    _show_window(window)
    _flash(self, "PPT Undo")
    return result


def redo_ppt_edit(self) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    method = getattr(window, "redo_deck_edit", None)
    if not callable(method):
        raise RuntimeError("PPT redo is unavailable")
    result = dict(method() or {})
    _show_window(window)
    _flash(self, "PPT Redo")
    return result


def autosave_ppt(self) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    method = getattr(window, "save_recovery_copy", None)
    if not callable(method):
        raise RuntimeError("PPT autosave is unavailable")
    result = dict(method() or {})
    _flash(self, "PPT recovery copy saved")
    return result


def list_ppt_recovery_candidates(self, *, limit: int = 20) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    method = getattr(window, "recovery_candidates", None)
    if not callable(method):
        raise RuntimeError("PPT recovery listing is unavailable")
    return dict(method(limit=limit) or {})


def open_ppt_recovery_copy(self, *, path: str = "") -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    method = getattr(window, "open_recovery_copy", None)
    if not callable(method):
        raise RuntimeError("PPT recovery open is unavailable")
    result = dict(method(path=path) or {})
    _show_window(window)
    _flash(self, "Opened PPT recovery copy")
    return result


def delete_ppt_recovery_copy(self, *, path: str) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    method = getattr(window, "delete_recovery_copy", None)
    if not callable(method):
        raise RuntimeError("PPT recovery delete is unavailable")
    result = dict(method(path) or {})
    _flash(self, "Deleted PPT recovery copy")
    return result


def list_ppt_media_pool(self) -> dict[str, Any]:
    from app.pptgen.assets import list_deck_assets

    window = _ensure_ppt_generator_window(self)
    assets = list_deck_assets(window.deck)
    return {
        "schema": "tigercapture.ppt.media_pool_list.v1",
        "asset_count": len(assets),
        "assets": assets,
    }


def list_ppt_animation_lanes(self, *, slide_id: str = "") -> dict[str, Any]:
    from app.pptgen.animation_lanes import animation_lane_rows_for_slide

    window = _ensure_ppt_generator_window(self)
    slide = window.deck.slide_by_id(slide_id) if slide_id else window._selected_slide()
    rows = animation_lane_rows_for_slide(slide)
    return {
        "schema": "tigercapture.ppt.animation_lanes.v1",
        "slide_id": slide.id if slide is not None else "",
        "row_count": len(rows),
        "rows": [row.to_dict() for row in rows],
    }


def select_ppt_timeline_slide(self, *, slide_id: str) -> dict[str, Any]:
    if not str(slide_id or "").strip():
        raise RuntimeError("slide_id is required")
    window = _ensure_ppt_generator_window(self)
    slide = window.deck.slide_by_id(slide_id)
    if slide is None:
        raise RuntimeError(f"slide not found: {slide_id}")
    window._select_slide_id(slide.id)
    _show_window(window)
    _flash(self, f"Selected PPT slide: {slide.id}")
    return {
        "schema": "tigercapture.ppt.timeline_slide_selected.v1",
        "slide_id": slide.id,
        "playhead_ms": int(getattr(window.timeline, "playhead_ms", 0) or 0),
        "slide_count": len(window.deck.slides),
    }


def set_ppt_timeline_playhead(
    self,
    *,
    time_ms: int | None = None,
    slide_id: str = "",
    local_ms: int | None = None,
) -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    target_ms = 0 if time_ms is None else max(0, int(time_ms))
    if str(slide_id or "").strip():
        slide = window.deck.slide_by_id(slide_id)
        if slide is None:
            raise RuntimeError(f"slide not found: {slide_id}")
        for clip in window.timeline.slide_clips:
            if clip.slide_id == slide.id:
                offset = 0 if local_ms is None else max(0, min(max(1, int(clip.duration_ms)) - 1, int(local_ms)))
                target_ms = int(clip.start_ms) + offset
                break
        window.timeline.select_slide(slide.id)
    total = max(1, sum(max(1, int(clip.duration_ms)) for clip in window.timeline.slide_clips))
    window.timeline.playhead_ms = max(0, min(total - 1, target_ms))
    window._timeline_playhead_changed()
    _show_window(window)
    _flash(self, f"Set PPT playhead: {window.timeline.playhead_ms} ms")
    return {
        "schema": "tigercapture.ppt.timeline_playhead_set.v1",
        "playhead_ms": int(window.timeline.playhead_ms),
        "selected_slide_id": str(getattr(window.timeline, "selected_slide_id", "") or ""),
        "local_ms": int(window._slide_local_playhead_ms(window._selected_slide())),
        "duration_ms": total,
    }


def play_ppt_timeline_preview(self, *, mode: str = "toggle") -> dict[str, Any]:
    window = _ensure_ppt_generator_window(self)
    mode_key = str(mode or "toggle").strip().lower()
    if mode_key in {"play", "start"}:
        if not bool(getattr(window, "_ppt_playing", False)):
            window._toggle_ppt_playback()
    elif mode_key in {"pause", "toggle"}:
        window._toggle_ppt_playback()
    elif mode_key in {"stop", "reset"}:
        window._stop_ppt_playback()
    else:
        raise RuntimeError(f"unknown preview mode: {mode}")
    _show_window(window)
    _flash(self, f"PPT preview {mode_key}")
    return {
        "schema": "tigercapture.ppt.timeline_preview.v1",
        "mode": mode_key,
        "playing": bool(getattr(window, "_ppt_playing", False)),
        "playhead_ms": int(getattr(window.timeline, "playhead_ms", 0) or 0),
        "selected_slide_id": str(getattr(window.timeline, "selected_slide_id", "") or ""),
    }


def add_ppt_media_pool_asset(
    self,
    path: str | Path,
    *,
    kind: str | None = None,
    name: str = "",
) -> dict[str, Any]:
    from app.pptgen.assets import add_deck_asset

    window = _ensure_ppt_generator_window(self)
    asset = add_deck_asset(window.deck, path, kind=kind, name=name, source="ppt_media_pool_action")
    refresh = getattr(window, "_refresh_media_pool", None)
    if callable(refresh):
        refresh()
    _show_window(window)
    _flash(self, f"Added PPT media-pool asset: {Path(path).name}")
    return {
        "schema": "tigercapture.ppt.media_pool_asset_added.v1",
        "asset": dict(asset),
        "asset_count": len(window.deck.assets),
    }


def insert_ppt_media_pool_asset(
    self,
    *,
    asset_id: str,
    slide_id: str = "",
    x: float = 0.18,
    y: float = 0.24,
    w: float | None = None,
    h: float | None = None,
) -> dict[str, Any]:
    from app.pptgen.assets import insert_deck_asset_to_slide
    from app.pptgen.actor_posters import ensure_actor_poster
    from app.pptgen.editing import element_payload

    window = _ensure_ppt_generator_window(self)
    slide = window.deck.slide_by_id(slide_id) if slide_id else window._selected_slide()
    if slide is None:
        raise RuntimeError("No slide is available")
    idx = len(slide.elements) + 1
    element = insert_deck_asset_to_slide(
        window.deck,
        asset_id,
        slide,
        element_id=f"{slide.id}-asset-{idx}",
        x=x,
        y=y,
        w=w,
        h=h,
        source="ppt_media_pool_action",
    )
    ensure_actor_poster(element)
    window.timeline.select_slide(slide.id)
    window.selected_element_id = element.id
    window._refresh_all()
    _show_window(window)
    _flash(self, f"Inserted PPT media asset: {asset_id}")
    return {
        "schema": "tigercapture.ppt.media_pool_asset_inserted.v1",
        "asset_id": asset_id,
        "slide_id": slide.id,
        "element": element_payload(element),
        "slide_count": len(window.deck.slides),
    }


def remove_ppt_media_pool_asset(self, *, asset_id: str) -> dict[str, Any]:
    from app.pptgen.assets import remove_deck_asset

    window = _ensure_ppt_generator_window(self)
    removed = remove_deck_asset(window.deck, asset_id)
    refresh = getattr(window, "_refresh_media_pool", None)
    if callable(refresh):
        refresh()
    _flash(self, f"Removed PPT media-pool asset: {asset_id}")
    return {
        "schema": "tigercapture.ppt.media_pool_asset_removed.v1",
        "asset_id": asset_id,
        "asset": dict(removed),
        "asset_count": len(window.deck.assets),
    }


def delete_ppt_element(self, *, element_id: str, slide_id: str = "") -> dict[str, Any]:
    from app.pptgen.editing import delete_element

    window = _ensure_ppt_generator_window(self)
    result = delete_element(window.deck, element_id, slide_id=slide_id)
    window.timeline.select_slide(result["slide_id"])
    window.selected_element_id = ""
    window._refresh_selected()
    _show_window(window)
    _flash(self, f"Deleted PPT element: {element_id}")
    return result


def duplicate_ppt_element(self, *, element_id: str, slide_id: str = "") -> dict[str, Any]:
    from app.pptgen.editing import duplicate_element, element_payload

    window = _ensure_ppt_generator_window(self)
    slide, clone = duplicate_element(window.deck, element_id, slide_id=slide_id)
    window.timeline.select_slide(slide.id)
    window.selected_element_id = clone.id
    window._refresh_selected()
    _show_window(window)
    _flash(self, f"Duplicated PPT element: {element_id}")
    return {
        "schema": "tigercapture.ppt.element_duplicated.v1",
        "slide_id": slide.id,
        "source_element_id": element_id,
        "element": element_payload(clone),
        "element_count": len(slide.elements),
    }


def set_ppt_element_z_order(self, *, element_id: str, mode: str = "front", slide_id: str = "") -> dict[str, Any]:
    from app.pptgen.editing import element_payload, set_element_z_order

    window = _ensure_ppt_generator_window(self)
    slide, element = set_element_z_order(window.deck, element_id, slide_id=slide_id, mode=mode)
    window.timeline.select_slide(slide.id)
    window.selected_element_id = element.id
    window._refresh_selected()
    _show_window(window)
    _flash(self, f"Updated PPT layer order: {element_id}")
    return {
        "schema": "tigercapture.ppt.element_z_order_set.v1",
        "slide_id": slide.id,
        "mode": str(mode),
        "element": element_payload(element),
        "z_order": [row.id for row in sorted(slide.elements, key=lambda item: int(item.z_index))],
    }


def align_ppt_element(
    self,
    *,
    element_id: str,
    slide_id: str = "",
    horizontal: str = "",
    vertical: str = "",
) -> dict[str, Any]:
    from app.pptgen.editing import align_element, element_payload

    window = _ensure_ppt_generator_window(self)
    slide, element = align_element(
        window.deck,
        element_id,
        slide_id=slide_id,
        horizontal=horizontal,
        vertical=vertical,
    )
    window.timeline.select_slide(slide.id)
    window.selected_element_id = element.id
    window._refresh_selected()
    _show_window(window)
    _flash(self, f"Aligned PPT element: {element_id}")
    return {
        "schema": "tigercapture.ppt.element_aligned.v1",
        "slide_id": slide.id,
        "horizontal": str(horizontal or ""),
        "vertical": str(vertical or ""),
        "element": element_payload(element),
    }


def update_ppt_element(
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
    from app.pptgen.editing import element_payload, update_element

    window = _ensure_ppt_generator_window(self)
    slide, element = update_element(
        window.deck,
        element_id,
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
    window.timeline.select_slide(slide.id)
    window.selected_element_id = element.id
    window._refresh_selected()
    _show_window(window)
    _flash(self, f"Updated PPT element: {element_id}")
    return {
        "schema": "tigercapture.ppt.element_updated.v1",
        "slide_id": slide.id,
        "element": element_payload(element),
    }


def set_ppt_element_animation(
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
    from app.pptgen.animations import animation_payload
    from app.pptgen.editing import element_payload, set_element_animation

    window = _ensure_ppt_generator_window(self)
    slide, element = set_element_animation(
        window.deck,
        element_id,
        slide_id=slide_id,
        in_animation=in_animation,
        out_animation=out_animation,
        trigger=trigger,
        start_ms=start_ms,
        duration_ms=duration_ms,
        click_index=click_index,
        easing=easing,
        motion_x=motion_x,
        motion_y=motion_y,
        scale=scale,
    )
    window.timeline.select_slide(slide.id)
    window.selected_element_id = element.id
    window._refresh_selected()
    _show_window(window)
    _flash(self, f"Updated PPT animation: {element_id}")
    return {
        "schema": "tigercapture.ppt.element_animation_set.v1",
        "slide_id": slide.id,
        "element": element_payload(element),
        "animation": animation_payload(element.animation),
    }


def set_ppt_table_data(
    self,
    *,
    element_id: str,
    cells: list[list[Any]],
    slide_id: str = "",
    header: bool | None = None,
) -> dict[str, Any]:
    from app.pptgen.editing import element_payload, set_table_data

    window = _ensure_ppt_generator_window(self)
    slide, element = set_table_data(window.deck, element_id, cells=cells, slide_id=slide_id, header=header)
    window.timeline.select_slide(slide.id)
    window.selected_element_id = element.id
    window._refresh_selected()
    _show_window(window)
    _flash(self, f"Updated PPT table data: {element_id}")
    return {
        "schema": "tigercapture.ppt.table_data_set.v1",
        "slide_id": slide.id,
        "element": element_payload(element),
    }


def set_ppt_chart_data(
    self,
    *,
    element_id: str,
    labels: list[Any],
    values: list[Any],
    slide_id: str = "",
    chart_type: str = "bar",
) -> dict[str, Any]:
    from app.pptgen.editing import element_payload, set_chart_data

    window = _ensure_ppt_generator_window(self)
    slide, element = set_chart_data(
        window.deck,
        element_id,
        labels=labels,
        values=values,
        slide_id=slide_id,
        chart_type=chart_type,
    )
    window.timeline.select_slide(slide.id)
    window.selected_element_id = element.id
    window._refresh_selected()
    _show_window(window)
    _flash(self, f"Updated PPT chart data: {element_id}")
    return {
        "schema": "tigercapture.ppt.chart_data_set.v1",
        "slide_id": slide.id,
        "element": element_payload(element),
    }


def export_timeline_pptx(
    self,
    path: str | Path,
    *,
    title: str = "Timeline Presentation",
    max_slides: int = 24,
) -> dict[str, Any]:
    from app.pptgen.actor_posters import ensure_deck_actor_posters
    from app.pptgen.editor_bridge import deck_from_editor_timeline
    from app.pptgen.writer_python_pptx import write_pptx_compatible

    target = Path(path)
    deck = deck_from_editor_timeline(self, title=title, max_slides=max_slides)
    ensure_deck_actor_posters(deck)
    out = write_pptx_compatible(deck, target)
    _flash(self, f"Exported timeline PPTX: {out.name}")
    return {
        "schema": "tigercapture.ppt.timeline_export.v1",
        "path": str(out),
        "slide_count": len(deck.slides),
        "title": deck.title,
    }


def export_timeline_pdf(
    self,
    path: str | Path,
    *,
    title: str = "Timeline Presentation",
    max_slides: int = 24,
    backend: str = "auto",
    timeout_sec: int = 90,
) -> dict[str, Any]:
    from app.pptgen.actor_posters import ensure_deck_actor_posters
    from app.pptgen.editor_bridge import deck_from_editor_timeline
    from app.pptgen.pdf_export import export_deck_pdf

    target = Path(path)
    deck = deck_from_editor_timeline(self, title=title, max_slides=max_slides)
    ensure_deck_actor_posters(deck)
    result = export_deck_pdf(deck, target, backend=backend, timeout_sec=timeout_sec)
    if not result.get("ok"):
        reason = result.get("reason") or "PDF export failed"
        raise RuntimeError(str(reason))
    _flash(self, f"Exported timeline PDF: {target.name}")
    return {
        "schema": "tigercapture.ppt.timeline_pdf_export.v1",
        "path": str(result.get("output_pdf") or target),
        "slide_count": len(deck.slides),
        "title": deck.title,
        "backend": str(result.get("backend") or ""),
        "attempts": list(result.get("attempts") or []),
    }


def export_timeline_video(
    self,
    path: str | Path,
    *,
    title: str = "Timeline Presentation",
    max_slides: int = 24,
    fps: int = 30,
    width: int = 1280,
    height: int = 720,
    audio_path: str = "",
    audio_bitrate: str = "192k",
) -> dict[str, Any]:
    from app.pptgen.actor_posters import ensure_deck_actor_posters
    from app.pptgen.editor_bridge import deck_from_editor_timeline
    from app.pptgen.video_export import export_deck_video

    target = Path(path)
    deck = deck_from_editor_timeline(self, title=title, max_slides=max_slides)
    ensure_deck_actor_posters(deck)
    result = export_deck_video(
        deck,
        target,
        fps=fps,
        size=(width, height),
        audio_path=str(audio_path or "") or None,
        audio_bitrate=str(audio_bitrate or "192k"),
    )
    if not result.get("ok"):
        raise RuntimeError("PPT video export failed")
    _flash(self, f"Exported timeline PPT video: {target.name}")
    return {
        "schema": "tigercapture.ppt.timeline_video_export.v1",
        "path": str(result.get("output_path") or target),
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


__all__ = [
    "add_chart_element_to_ppt",
    "add_media_asset_to_ppt",
    "add_ppt_media_pool_asset",
    "add_shape_element_to_ppt",
    "add_text_element_to_ppt",
    "add_timeline_clip_to_ppt",
    "add_timeline_clip_still_to_ppt",
    "add_typography_to_ppt",
    "apply_template_to_ppt",
    "create_ppt_deck_from_prompt",
    "create_ppt_deck_from_timeline",
    "create_ppt_project",
    "delete_ppt_element",
    "delete_ppt_recovery_copy",
    "align_ppt_element",
    "duplicate_ppt_element",
    "export_ppt_deck_pdf",
    "export_ppt_deck_pptx",
    "export_ppt_deck_video",
    "export_timeline_pdf",
    "export_timeline_pptx",
    "export_timeline_video",
    "generate_ppt_actor_posters",
    "insert_ppt_media_pool_asset",
    "import_pptx_to_ppt",
    "list_ppt_animation_lanes",
    "list_ppt_media_pool",
    "load_image_to_ppt",
    "list_ppt_recovery_candidates",
    "open_ppt_generator",
    "open_ppt_project",
    "open_ppt_recovery_copy",
    "autosave_ppt",
    "play_ppt_timeline_preview",
    "ppt_history_status",
    "redo_ppt_edit",
    "add_ppt_slide",
    "delete_ppt_slide",
    "duplicate_ppt_slide",
    "move_ppt_slide",
    "remove_ppt_media_pool_asset",
    "save_ppt_project",
    "save_ppt_project_as",
    "set_ppt_element_z_order",
    "set_ppt_element_animation",
    "set_ppt_chart_data",
    "select_ppt_timeline_slide",
    "set_ppt_timeline_playhead",
    "update_ppt_slide",
    "set_ppt_table_data",
    "snapshot_ppt",
    "undo_ppt_edit",
    "update_ppt_element",
    "validate_ppt_deck",
]
