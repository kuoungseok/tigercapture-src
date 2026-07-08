from __future__ import annotations

from pathlib import Path


class _Clip:
    def __init__(self, clip_id: int, source_path: Path, timeline_in_ms: int, duration_ms: int) -> None:
        self.id = clip_id
        self.source_path = source_path
        self.timeline_in_ms = timeline_in_ms
        self.source_in_ms = 0
        self.source_out_ms = duration_ms
        self.source_duration_ms = duration_ms


class _Track:
    def __init__(self, track_id: int, clips: list[_Clip]) -> None:
        self.id = track_id
        self.clips = clips


class _Owner:
    def __init__(self, tmp_path: Path) -> None:
        self._tracks = [
            _Track(2, [_Clip(20, tmp_path / "b.mp4", 2000, 3000)]),
            _Track(1, [_Clip(10, tmp_path / "a.mp4", 0, 5000)]),
        ]

    def _ppt_add_media_asset(self, path, **kwargs):
        return {
            "schema": "tigercapture.ppt.asset_added.v1",
            "element_id": "asset-1",
            "kind": kwargs.get("kind") or "video_actor",
            "source_path": str(path),
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "slide_count": 1,
        }

    def _ppt_load_image(self, path, **kwargs):
        return {
            "schema": "tigercapture.ppt.image_loaded.v1",
            "element_id": kwargs.get("element_id") or "image-1",
            "kind": "image",
            "source_path": str(path),
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "slide_count": 1,
            "replaced": bool(kwargs.get("element_id")),
        }

    def _ppt_add_timeline_clip(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.timeline_clip_added.v1",
            "element_id": "timeline-clip-1",
            "kind": "video_actor",
            "source_path": str(self._tracks[0].clips[0].source_path),
            "track_id": int(kwargs.get("track_id") or 0),
            "clip_id": int(kwargs.get("clip_id") or 0),
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "slide_count": 1,
        }

    def _ppt_add_timeline_clip_still(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.timeline_clip_still_added.v1",
            "element_id": "timeline-still-1",
            "kind": "image",
            "source_path": str(kwargs.get("source_path") or "still.png"),
            "source_video_path": str(self._tracks[0].clips[0].source_path),
            "source_ms": int(kwargs.get("source_ms") or 0),
            "track_id": int(kwargs.get("track_id") or 0),
            "clip_id": int(kwargs.get("clip_id") or 0),
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "slide_count": 1,
        }

    def _ppt_add_typography(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.typography_added.v1",
            "element_id": "typo-1",
            "kind": "typography_actor",
            "text": kwargs.get("text") or "",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "slide_count": 1,
        }

    def _ppt_add_text_element(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.element_added.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "element": {
                "id": "text-added",
                "kind": "text",
                "text": kwargs.get("text") or "Text",
                "style": {"font_size": int(kwargs.get("font_size") or 28), "color": kwargs.get("color") or "#182033"},
            },
            "slide_count": 1,
        }

    def _ppt_add_shape_element(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.element_added.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "element": {
                "id": "shape-added",
                "kind": "shape",
                "style": {"fill": kwargs.get("fill") or "#F7F9FC", "stroke": kwargs.get("stroke") or "#2F6FED"},
            },
            "slide_count": 1,
        }

    def _ppt_add_chart_element(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.element_added.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "element": {
                "id": "chart-added",
                "kind": "chart",
                "metadata": {"chart_type": kwargs.get("chart_type") or "bar"},
            },
            "slide_count": 1,
        }

    def _ppt_apply_template(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.template_applied.v1",
            "template_id": kwargs.get("template_id") or "",
            "slide_id": "slide-001",
            "layout_id": kwargs.get("template_id") or "",
            "element_count": 4,
            "slide_count": 1,
        }

    def _ppt_project_create(self, **kwargs):
        raw_path = kwargs.get("path") or ""
        if raw_path:
            Path(raw_path).write_text("{}", encoding="utf-8")
        return {
            "schema": "tigercapture.ppt.project_created.v1",
            "deck_id": "created",
            "title": kwargs.get("title") or "Created",
            "template_id": kwargs.get("template_id") or "blank",
            "slide_count": 1,
            "path": str(raw_path),
        }

    def _ppt_deck_from_prompt(self, **kwargs):
        raw_path = kwargs.get("path") or ""
        if raw_path:
            Path(raw_path).write_text("{}", encoding="utf-8")
        return {
            "schema": "tigercapture.ppt.deck_from_prompt.v1",
            "deck_id": "prompt-deck",
            "title": kwargs.get("title") or "Prompt",
            "template_id": kwargs.get("template_id") or "title_body",
            "slide_count": int(kwargs.get("max_slides") or 1),
            "path": str(raw_path),
        }

    def _ppt_deck_from_timeline(self, **kwargs):
        raw_path = kwargs.get("path") or ""
        if raw_path:
            Path(raw_path).write_text("{}", encoding="utf-8")
        return {
            "schema": "tigercapture.ppt.deck_from_timeline.v1",
            "deck_id": "timeline-deck",
            "title": kwargs.get("title") or "Timeline Presentation",
            "slide_count": min(int(kwargs.get("max_slides") or 24), 3),
            "path": str(raw_path),
        }

    def _ppt_project_open(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.project_opened.v1",
            "path": str(kwargs.get("path") or ""),
            "deck_id": "opened",
            "title": "Opened",
            "slide_count": 1,
        }

    def _ppt_project_save(self, **kwargs):
        path = Path(kwargs.get("path") or "saved.tgppt")
        path.write_text("{}", encoding="utf-8")
        return {
            "schema": "tigercapture.ppt.project_saved.v1",
            "path": str(path),
            "deck_id": "saved",
            "title": "Saved",
            "slide_count": 1,
        }

    def _ppt_project_save_as(self, **kwargs):
        return self._ppt_project_save(**kwargs)

    def _ppt_snapshot(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.deck_snapshot.v1",
            "deck_id": "deck",
            "title": "Deck",
            "slide_count": 1,
            "selected_slide_id": "slide-001",
            "slides": [{"id": "slide-001", "elements": [{"id": "table-1", "kind": "table"}]}],
        }

    def _ppt_validate(self):
        return {
            "schema": "tigercapture.ppt.validation.v1",
            "ok": True,
            "issue_count": 1,
            "error_count": 0,
            "warning_count": 1,
            "info_count": 0,
            "issues": [{"severity": "warning", "code": "missing_asset", "slide_id": "slide-001", "element_id": "asset-1"}],
        }

    def _ppt_import_pptx(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.pptx_imported.v1",
            "path": kwargs.get("path") or "",
            "deck_id": "imported",
            "title": "Imported",
            "slide_count": 2,
            "asset_count": 1,
        }

    def _ppt_generate_actor_posters(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.actor_posters.v1",
            "actor_count": 2,
            "generated_count": 2 if kwargs.get("force") else 1,
            "posters": [
                {"slide_id": "slide-001", "element_id": "actor-1", "kind": "video_actor", "generated": True},
                {"slide_id": "slide-001", "element_id": "actor-2", "kind": "ar_pbr_actor", "generated": bool(kwargs.get("force"))},
            ],
        }

    def _ppt_export_deck_pptx(self, **kwargs):
        path = Path(kwargs.get("path") or "deck.pptx")
        path.write_bytes(b"pptx")
        return {
            "schema": "tigercapture.ppt.deck_pptx_export.v1",
            "path": str(path),
            "slide_count": 1,
            "title": "Deck",
        }

    def _ppt_export_deck_pdf(self, **kwargs):
        path = Path(kwargs.get("path") or "deck.pdf")
        path.write_bytes(b"pdf")
        return {
            "schema": "tigercapture.ppt.deck_pdf_export.v1",
            "path": str(path),
            "slide_count": 1,
            "title": "Deck",
            "backend": kwargs.get("backend") or "auto",
            "attempts": [],
        }

    def _ppt_export_deck_video(self, **kwargs):
        path = Path(kwargs.get("path") or "deck.mp4")
        path.write_bytes(b"mp4")
        return {
            "schema": "tigercapture.ppt.deck_video_export.v1",
            "path": str(path),
            "slide_count": 1,
            "title": "Deck",
            "fps": int(kwargs.get("fps") or 30),
            "size": [int(kwargs.get("width") or 1280), int(kwargs.get("height") or 720)],
            "frames_written": 12,
            "duration_ms": 400,
            "transition_count": 0,
            "audio_path": kwargs.get("audio_path") or "",
            "audio_muxed": False,
        }

    def _ppt_history_status(self):
        return {
            "schema": "tigercapture.ppt.history_status.v1",
            "can_undo": True,
            "can_redo": False,
            "undo_label": "Text edit",
            "redo_label": "",
            "history_depth": 2,
            "dirty": True,
            "autosave_path": "",
        }

    def _ppt_undo(self):
        return {
            "schema": "tigercapture.ppt.undo.v1",
            "changed": True,
            "can_undo": False,
            "can_redo": True,
        }

    def _ppt_redo(self):
        return {
            "schema": "tigercapture.ppt.redo.v1",
            "changed": True,
            "can_undo": True,
            "can_redo": False,
        }

    def _ppt_autosave(self):
        return {
            "schema": "tigercapture.ppt.autosave.v1",
            "path": "deck.autosave.tgppt",
            "dirty": True,
            "slide_count": 1,
        }

    def _ppt_recovery_list(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.recovery_candidates.v1",
            "candidate_count": 1,
            "candidates": [
                {
                    "path": "deck.autosave.tgppt",
                    "valid": True,
                    "title": "Recovered",
                    "slide_count": 1,
                }
            ],
            "limit": int(kwargs.get("limit") or 20),
        }

    def _ppt_recovery_open(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.recovery_opened.v1",
            "path": kwargs.get("path") or "deck.autosave.tgppt",
            "deck_id": "recovered",
            "title": "Recovered",
            "slide_count": 1,
            "dirty": True,
        }

    def _ppt_recovery_delete(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.recovery_deleted.v1",
            "path": kwargs.get("path") or "",
            "deleted": True,
        }

    def _ppt_media_pool_list(self):
        return {
            "schema": "tigercapture.ppt.media_pool_list.v1",
            "asset_count": 1,
            "assets": [{"id": "asset-1", "kind": "image", "path": "hero.png"}],
        }

    def _ppt_media_pool_add(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.media_pool_asset_added.v1",
            "asset": {
                "id": "asset-1",
                "kind": kwargs.get("kind") or "image",
                "name": kwargs.get("name") or "Hero",
                "path": kwargs.get("path") or "",
            },
            "asset_count": 1,
        }

    def _ppt_media_pool_insert(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.media_pool_asset_inserted.v1",
            "asset_id": kwargs.get("asset_id") or "",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "element": {"id": "el-asset", "kind": "image", "metadata": {"ppt_asset_id": kwargs.get("asset_id")}},
            "slide_count": 1,
        }

    def _ppt_media_pool_remove(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.media_pool_asset_removed.v1",
            "asset_id": kwargs.get("asset_id") or "",
            "asset_count": 0,
        }

    def _ppt_add_slide(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.slide_added.v1",
            "slide": {
                "id": "slide-002",
                "title": kwargs.get("title") or "New Slide",
                "layout_id": kwargs.get("layout_id") or "blank",
                "duration_ms": int(kwargs.get("duration_ms") or 5000),
            },
            "slide_count": 2,
            "selected_slide_id": "slide-002",
        }

    def _ppt_duplicate_slide(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.slide_duplicated.v1",
            "source_slide_id": kwargs.get("slide_id") or "slide-001",
            "slide": {"id": "slide-001-copy", "title": "Slide Copy"},
            "slide_count": 2,
            "selected_slide_id": "slide-001-copy",
        }

    def _ppt_delete_slide(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.slide_deleted.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "slide_count": 1,
            "selected_slide_id": "slide-001",
        }

    def _ppt_move_slide(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.slide_moved.v1",
            "slide": {"id": kwargs.get("slide_id") or "slide-001"},
            "index": int(kwargs.get("index") or 0),
            "slide_order": [kwargs.get("slide_id") or "slide-001"],
            "slide_count": 1,
            "selected_slide_id": kwargs.get("slide_id") or "slide-001",
        }

    def _ppt_update_slide(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.slide_updated.v1",
            "slide": {
                "id": kwargs.get("slide_id") or "slide-001",
                "title": kwargs.get("title") or "Slide",
                "layout_id": kwargs.get("layout_id") or "blank",
                "duration_ms": int(kwargs.get("duration_ms") or 5000),
                "speaker_notes": kwargs.get("speaker_notes") or "",
            },
            "slide_count": 1,
            "selected_slide_id": kwargs.get("slide_id") or "slide-001",
        }

    def _ppt_animation_lanes_list(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.animation_lanes.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "row_count": 1,
            "rows": [
                {
                    "slide_id": kwargs.get("slide_id") or "slide-001",
                    "element_id": "text-1",
                "effect": "fade_in",
                "trigger": "on_slide_start",
                "click_index": 0,
                "start_ms": 300,
                    "duration_ms": 700,
                    "end_ms": 1000,
                    "lane_index": 0,
                }
            ],
        }

    def _ppt_timeline_select_slide(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.timeline_slide_selected.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "playhead_ms": 0,
            "slide_count": 1,
        }

    def _ppt_timeline_set_playhead(self, **kwargs):
        playhead_ms = kwargs.get("time_ms")
        if playhead_ms is None:
            playhead_ms = int(kwargs.get("local_ms") or 0) + 1000
        return {
            "schema": "tigercapture.ppt.timeline_playhead_set.v1",
            "playhead_ms": int(playhead_ms),
            "selected_slide_id": kwargs.get("slide_id") or "slide-001",
            "local_ms": int(kwargs.get("local_ms") or 0),
            "duration_ms": 5000,
        }

    def _ppt_timeline_play_preview(self, **kwargs):
        mode = kwargs.get("mode") or "toggle"
        return {
            "schema": "tigercapture.ppt.timeline_preview.v1",
            "mode": mode,
            "playing": mode in {"play", "toggle"},
            "playhead_ms": 1000,
            "selected_slide_id": "slide-001",
        }

    def _ppt_delete_element(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.element_deleted.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "element_id": kwargs.get("element_id") or "",
            "element_count": 0,
        }

    def _ppt_duplicate_element(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.element_duplicated.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "source_element_id": kwargs.get("element_id") or "",
            "element": {"id": "text-1-copy", "kind": "text"},
            "element_count": 2,
        }

    def _ppt_set_element_z_order(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.element_z_order_set.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "mode": kwargs.get("mode") or "front",
            "element": {"id": kwargs.get("element_id") or "", "kind": "text"},
            "z_order": ["body", kwargs.get("element_id") or ""],
        }

    def _ppt_align_element(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.element_aligned.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "horizontal": kwargs.get("horizontal") or "",
            "vertical": kwargs.get("vertical") or "",
            "element": {"id": kwargs.get("element_id") or "", "kind": "text", "x": 0.35, "y": 0.9},
        }

    def _ppt_update_element(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.element_updated.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "element": {
                "id": kwargs.get("element_id") or "",
                "kind": "text",
                "text": kwargs.get("text") or "",
            },
        }

    def _ppt_set_element_animation(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.element_animation_set.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "element": {"id": kwargs.get("element_id") or "", "kind": "text"},
            "animation": {
                "in_animation": kwargs.get("in_animation") or "none",
                "trigger": kwargs.get("trigger") or "on_slide_start",
                "click_index": int(kwargs.get("click_index") or 0),
                "start_ms": int(kwargs.get("start_ms") or 0),
                "duration_ms": int(kwargs.get("duration_ms") or 450),
            },
        }

    def _ppt_set_table_data(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.table_data_set.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "element": {"id": kwargs.get("element_id") or "", "kind": "table", "metadata": {"cells": kwargs.get("cells")}},
        }

    def _ppt_set_chart_data(self, **kwargs):
        return {
            "schema": "tigercapture.ppt.chart_data_set.v1",
            "slide_id": kwargs.get("slide_id") or "slide-001",
            "element": {
                "id": kwargs.get("element_id") or "",
                "kind": "chart",
                "metadata": {"labels": kwargs.get("labels"), "values": kwargs.get("values")},
            },
        }


def test_deck_from_editor_timeline_orders_clips_and_preserves_metadata(tmp_path):
    from app.pptgen.editor_bridge import deck_from_editor_timeline

    deck = deck_from_editor_timeline(_Owner(tmp_path), title="Editor Deck")

    assert deck.title == "Editor Deck"
    assert len(deck.slides) == 3
    assert deck.slides[1].metadata["track_id"] == 1
    assert deck.slides[1].metadata["clip_id"] == 10
    assert deck.slides[2].metadata["track_id"] == 2


def test_ppt_project_element_alias_and_timeline_actions(tmp_path):
    from app.actions import build_default_action_registry

    owner = _Owner(tmp_path)
    registry = build_default_action_registry(owner)
    action_ids = {row["id"] for row in registry.list_actions()}

    expected = {
        "ppt.deck.apply_template",
        "ppt.project.create",
        "ppt.project.open",
        "ppt.project.save",
        "ppt.project.save_as",
        "ppt.deck.from_prompt",
        "ppt.deck.from_timeline",
        "ppt.element.add_text",
        "ppt.element.add_image",
        "ppt.element.add_video",
        "ppt.element.add_shape",
        "ppt.element.add_chart",
        "ppt.element.remove",
        "ppt.element.arrange",
        "ppt.timeline.select_slide",
        "ppt.timeline.set_playhead",
        "ppt.timeline.play_preview",
    }
    assert expected <= action_ids

    template = registry.execute("ppt.deck.apply_template", {"template_id": "3d_showcase"}).to_dict()
    assert template["ok"] is True
    assert template["result"]["template_id"] == "3d_showcase"

    project_path = tmp_path / "deck.tgppt"
    created = registry.execute(
        "ppt.project.create",
        {"template_id": "blank", "title": "Deck", "path": str(project_path)},
    ).to_dict()
    assert created["ok"] is True
    assert created["result"]["path"] == str(project_path)

    prompt_deck = registry.execute(
        "ppt.deck.from_prompt",
        {"prompt": "Launch plan\nAudience\nTimeline", "title": "Prompt Deck", "max_slides": 2},
    ).to_dict()
    assert prompt_deck["ok"] is True
    assert prompt_deck["result"]["schema"] == "tigercapture.ppt.deck_from_prompt.v1"
    assert prompt_deck["result"]["slide_count"] == 2

    timeline_deck = registry.execute(
        "ppt.deck.from_timeline",
        {"title": "Timeline Deck", "max_slides": 2},
    ).to_dict()
    assert timeline_deck["ok"] is True
    assert timeline_deck["result"]["schema"] == "tigercapture.ppt.deck_from_timeline.v1"
    assert timeline_deck["result"]["slide_count"] == 2

    opened = registry.execute("ppt.project.open", {"path": str(project_path)}).to_dict()
    assert opened["ok"] is True
    assert opened["result"]["deck_id"] == "opened"

    saved = registry.execute("ppt.project.save", {"path": str(tmp_path / "saved.tgppt")}).to_dict()
    assert saved["ok"] is True
    assert Path(saved["result"]["path"]).is_file()

    saved_as = registry.execute("ppt.project.save_as", {"path": str(tmp_path / "saved_as.tgppt")}).to_dict()
    assert saved_as["ok"] is True
    assert Path(saved_as["result"]["path"]).is_file()

    text = registry.execute("ppt.element.add_text", {"text": "Hello", "font_size": 32}).to_dict()
    assert text["ok"] is True
    assert text["result"]["element"]["kind"] == "text"
    assert text["result"]["element"]["text"] == "Hello"

    image = registry.execute("ppt.element.add_image", {"path": str(tmp_path / "hero.png")}).to_dict()
    assert image["ok"] is True
    assert image["result"]["kind"] == "image"

    video = registry.execute("ppt.element.add_video", {"path": str(tmp_path / "hero.mp4")}).to_dict()
    assert video["ok"] is True
    assert video["result"]["kind"] == "video_actor"

    shape = registry.execute("ppt.element.add_shape", {"fill": "#FFFFFF"}).to_dict()
    assert shape["ok"] is True
    assert shape["result"]["element"]["kind"] == "shape"

    chart = registry.execute("ppt.element.add_chart", {"chart_type": "line"}).to_dict()
    assert chart["ok"] is True
    assert chart["result"]["element"]["metadata"]["chart_type"] == "line"

    removed = registry.execute("ppt.element.remove", {"element_id": "text-1"}).to_dict()
    assert removed["ok"] is True
    assert removed["result"]["schema"] == "tigercapture.ppt.element_deleted.v1"

    arranged = registry.execute(
        "ppt.element.arrange",
        {"element_id": "text-1", "mode": "front", "horizontal": "center"},
    ).to_dict()
    assert arranged["ok"] is True
    assert arranged["result"]["schema"] == "tigercapture.ppt.element_arranged.v1"
    assert arranged["result"]["arrange"]["horizontal"] == "center"

    selected = registry.execute("ppt.timeline.select_slide", {"slide_id": "slide-001"}).to_dict()
    assert selected["ok"] is True
    assert selected["result"]["slide_id"] == "slide-001"

    playhead = registry.execute("ppt.timeline.set_playhead", {"slide_id": "slide-001", "local_ms": 1200}).to_dict()
    assert playhead["ok"] is True
    assert playhead["result"]["playhead_ms"] == 2200

    preview = registry.execute("ppt.timeline.play_preview", {"mode": "play"}).to_dict()
    assert preview["ok"] is True
    assert preview["result"]["playing"] is True


def test_ppt_actions_register_and_export_timeline(tmp_path):
    from app.actions import build_default_action_registry

    owner = _Owner(tmp_path)
    registry = build_default_action_registry(owner)
    action_ids = {row["id"] for row in registry.list_actions()}

    assert {
        "ppt.templates.list",
        "ppt.template.apply",
        "ppt.deck.snapshot",
        "ppt.deck.validate",
        "ppt.deck.import_pptx",
        "ppt.deck.actor_posters.generate",
        "ppt.deck.export_pptx",
        "ppt.deck.export_pdf",
        "ppt.deck.export_video",
        "ppt.deck.history",
        "ppt.deck.undo",
        "ppt.deck.redo",
        "ppt.deck.autosave",
        "ppt.deck.recovery.list",
        "ppt.deck.recovery.open",
        "ppt.deck.recovery.delete",
        "ppt.element.delete",
        "ppt.element.duplicate",
        "ppt.element.z_order",
        "ppt.element.align",
            "ppt.element.update",
            "ppt.element.animation.set",
            "ppt.animation_lanes.list",
            "ppt.table.data.set",
            "ppt.chart.data.set",
            "ppt.summary",
            "ppt.editor.open",
            "ppt.timeline.export",
            "ppt.timeline.export_video",
            "ppt.media_pool.list",
            "ppt.media_pool.add",
            "ppt.media_pool.insert",
            "ppt.media_pool.remove",
            "ppt.slide.add",
            "ppt.slide.duplicate",
            "ppt.slide.remove",
            "ppt.slide.move",
            "ppt.slide.update",
            "ppt.slide.set_layout",
            "ppt.slide.set_duration",
            "ppt.slide.set_notes",
            "ppt.asset.add",
            "ppt.image.load",
        "ppt.timeline_clip.add",
        "ppt.timeline_clip.still.add",
        "ppt.typography.add",
    } <= action_ids
    summary = registry.execute("ppt.summary", {"max_slides": 4}).to_dict()
    assert summary["ok"] is True
    assert summary["result"]["slide_count"] == 3

    out = tmp_path / "timeline.pptx"
    exported = registry.execute(
        "ppt.timeline.export",
        {"path": str(out), "title": "Timeline Export", "max_slides": 4},
    ).to_dict()
    assert exported["ok"] is True
    assert out.is_file()
    assert exported["result"]["slide_count"] == 3

    media = registry.execute("ppt.asset.add", {"path": str(tmp_path / "scene.gltf"), "kind": "ar_pbr_actor"}).to_dict()
    assert media["ok"] is True
    assert media["result"]["kind"] == "ar_pbr_actor"

    image = registry.execute("ppt.image.load", {"path": str(tmp_path / "hero.png"), "element_id": "image-slot"}).to_dict()
    assert image["ok"] is True
    assert image["result"]["kind"] == "image"
    assert image["result"]["replaced"] is True

    clip = registry.execute("ppt.timeline_clip.add", {"track_id": 1, "clip_id": 10}).to_dict()
    assert clip["ok"] is True
    assert clip["result"]["kind"] == "video_actor"

    still = registry.execute("ppt.timeline_clip.still.add", {"track_id": 1, "clip_id": 10, "source_ms": 1200}).to_dict()
    assert still["ok"] is True
    assert still["result"]["kind"] == "image"
    assert still["result"]["source_ms"] == 1200

    typo = registry.execute("ppt.typography.add", {"text": "Title"}).to_dict()
    assert typo["ok"] is True
    assert typo["result"]["kind"] == "typography_actor"

    templates = registry.execute("ppt.templates.list").to_dict()
    assert templates["ok"] is True
    assert "3d_showcase" in {row["id"] for row in templates["result"]["templates"]}

    applied = registry.execute("ppt.template.apply", {"template_id": "3d_showcase"}).to_dict()
    assert applied["ok"] is True
    assert applied["result"]["template_id"] == "3d_showcase"

    snapshot = registry.execute("ppt.deck.snapshot").to_dict()
    assert snapshot["ok"] is True
    assert snapshot["result"]["selected_slide_id"] == "slide-001"

    validation = registry.execute("ppt.deck.validate").to_dict()
    assert validation["ok"] is True
    assert validation["result"]["warning_count"] == 1

    imported = registry.execute("ppt.deck.import_pptx", {"path": str(tmp_path / "source.pptx")}).to_dict()
    assert imported["ok"] is True
    assert imported["result"]["deck_id"] == "imported"

    posters = registry.execute("ppt.deck.actor_posters.generate", {"force": True}).to_dict()
    assert posters["ok"] is True
    assert posters["result"]["generated_count"] == 2

    deck_pptx = registry.execute("ppt.deck.export_pptx", {"path": str(tmp_path / "deck.pptx")}).to_dict()
    assert deck_pptx["ok"] is True
    assert Path(deck_pptx["result"]["path"]).is_file()

    deck_pdf = registry.execute("ppt.deck.export_pdf", {"path": str(tmp_path / "deck.pdf"), "backend": "auto"}).to_dict()
    assert deck_pdf["ok"] is True
    assert Path(deck_pdf["result"]["path"]).is_file()

    deck_video = registry.execute("ppt.deck.export_video", {"path": str(tmp_path / "deck.mp4"), "fps": 24}).to_dict()
    assert deck_video["ok"] is True
    assert deck_video["result"]["fps"] == 24

    history = registry.execute("ppt.deck.history").to_dict()
    assert history["ok"] is True
    assert history["result"]["undo_label"] == "Text edit"

    undo = registry.execute("ppt.deck.undo").to_dict()
    assert undo["ok"] is True
    assert undo["result"]["changed"] is True

    redo = registry.execute("ppt.deck.redo").to_dict()
    assert redo["ok"] is True
    assert redo["result"]["changed"] is True

    autosave = registry.execute("ppt.deck.autosave").to_dict()
    assert autosave["ok"] is True
    assert autosave["result"]["path"].endswith(".autosave.tgppt")

    recovery_list = registry.execute("ppt.deck.recovery.list", {"limit": 3}).to_dict()
    assert recovery_list["ok"] is True
    assert recovery_list["result"]["candidate_count"] == 1

    recovery_open = registry.execute("ppt.deck.recovery.open", {"path": "deck.autosave.tgppt"}).to_dict()
    assert recovery_open["ok"] is True
    assert recovery_open["result"]["title"] == "Recovered"

    recovery_delete = registry.execute("ppt.deck.recovery.delete", {"path": "deck.autosave.tgppt"}).to_dict()
    assert recovery_delete["ok"] is True
    assert recovery_delete["result"]["deleted"] is True

    pool = registry.execute("ppt.media_pool.list").to_dict()
    assert pool["ok"] is True
    assert pool["result"]["asset_count"] == 1

    pool_add = registry.execute("ppt.media_pool.add", {"path": str(tmp_path / "hero.png"), "kind": "image"}).to_dict()
    assert pool_add["ok"] is True
    assert pool_add["result"]["asset"]["kind"] == "image"

    pool_insert = registry.execute("ppt.media_pool.insert", {"asset_id": "asset-1"}).to_dict()
    assert pool_insert["ok"] is True
    assert pool_insert["result"]["element"]["metadata"]["ppt_asset_id"] == "asset-1"

    pool_remove = registry.execute("ppt.media_pool.remove", {"asset_id": "asset-1"}).to_dict()
    assert pool_remove["ok"] is True
    assert pool_remove["result"]["asset_count"] == 0

    slide_add = registry.execute("ppt.slide.add", {"title": "Agenda", "layout_id": "title", "duration_ms": 3500}).to_dict()
    assert slide_add["ok"] is True
    assert slide_add["result"]["slide"]["title"] == "Agenda"

    slide_duplicate = registry.execute("ppt.slide.duplicate", {"slide_id": "slide-001"}).to_dict()
    assert slide_duplicate["ok"] is True
    assert slide_duplicate["result"]["slide"]["id"] == "slide-001-copy"

    slide_move = registry.execute("ppt.slide.move", {"slide_id": "slide-001", "index": 0}).to_dict()
    assert slide_move["ok"] is True
    assert slide_move["result"]["index"] == 0

    slide_update = registry.execute("ppt.slide.update", {"slide_id": "slide-001", "title": "Updated"}).to_dict()
    assert slide_update["ok"] is True
    assert slide_update["result"]["slide"]["title"] == "Updated"

    slide_layout = registry.execute("ppt.slide.set_layout", {"slide_id": "slide-001", "layout_id": "section"}).to_dict()
    assert slide_layout["ok"] is True
    assert slide_layout["result"]["slide"]["layout_id"] == "section"

    slide_duration = registry.execute("ppt.slide.set_duration", {"slide_id": "slide-001", "duration_ms": 4200}).to_dict()
    assert slide_duration["ok"] is True
    assert slide_duration["result"]["slide"]["duration_ms"] == 4200

    slide_notes = registry.execute("ppt.slide.set_notes", {"slide_id": "slide-001", "speaker_notes": "Talk"}).to_dict()
    assert slide_notes["ok"] is True
    assert slide_notes["result"]["slide"]["speaker_notes"] == "Talk"

    slide_remove = registry.execute("ppt.slide.remove", {"slide_id": "slide-002"}).to_dict()
    assert slide_remove["ok"] is True
    assert slide_remove["result"]["slide_count"] == 1

    updated = registry.execute("ppt.element.update", {"element_id": "text-1", "text": "AI edited"}).to_dict()
    assert updated["ok"] is True
    assert updated["result"]["element"]["text"] == "AI edited"

    duplicated = registry.execute("ppt.element.duplicate", {"element_id": "text-1"}).to_dict()
    assert duplicated["ok"] is True
    assert duplicated["result"]["element"]["id"] == "text-1-copy"

    z_order = registry.execute("ppt.element.z_order", {"element_id": "text-1", "mode": "back"}).to_dict()
    assert z_order["ok"] is True
    assert z_order["result"]["mode"] == "back"

    aligned = registry.execute("ppt.element.align", {"element_id": "text-1", "horizontal": "center"}).to_dict()
    assert aligned["ok"] is True
    assert aligned["result"]["horizontal"] == "center"

    animation = registry.execute(
        "ppt.element.animation.set",
        {"element_id": "text-1", "in_animation": "fade_in", "start_ms": 300, "duration_ms": 700},
    ).to_dict()
    assert animation["ok"] is True
    assert animation["result"]["animation"]["in_animation"] == "fade_in"
    assert animation["result"]["animation"]["start_ms"] == 300
    assert animation["result"]["animation"]["click_index"] == 0

    lanes = registry.execute("ppt.animation_lanes.list", {"slide_id": "slide-001"}).to_dict()
    assert lanes["ok"] is True
    assert lanes["result"]["row_count"] == 1
    assert lanes["result"]["rows"][0]["element_id"] == "text-1"

    table = registry.execute(
        "ppt.table.data.set",
        {"element_id": "table-1", "cells": [["Item", "A"], ["Total", "=SUM(1,2)"]]},
    ).to_dict()
    assert table["ok"] is True
    assert table["result"]["element"]["kind"] == "table"

    chart = registry.execute(
        "ppt.chart.data.set",
        {"element_id": "chart-1", "labels": ["A", "B"], "values": ["10", "=SUM(10,20)"]},
    ).to_dict()
    assert chart["ok"] is True
    assert chart["result"]["element"]["metadata"]["values"][1] == "=SUM(10,20)"

    deleted = registry.execute("ppt.element.delete", {"element_id": "text-1"}).to_dict()
    assert deleted["ok"] is True
    assert deleted["result"]["element_id"] == "text-1"


def test_ppt_action_exports_timeline_pdf(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    from app.pptgen import pdf_export

    def fake_export_deck_pdf(deck, path, **_kwargs):
        Path(path).write_bytes(b"%PDF-1.4\n")
        return {
            "schema": pdf_export.PDF_EXPORT_SCHEMA,
            "ok": True,
            "status": "passed",
            "backend": "fake",
            "output_pdf": str(path),
            "attempts": [{"host": "fake", "status": "passed"}],
            "slide_count": len(deck.slides),
        }

    monkeypatch.setattr(pdf_export, "export_deck_pdf", fake_export_deck_pdf)

    registry = build_default_action_registry(_Owner(tmp_path))
    action_ids = {row["id"] for row in registry.list_actions()}
    assert "ppt.timeline.export_pdf" in action_ids

    out = tmp_path / "timeline.pdf"
    exported = registry.execute(
        "ppt.timeline.export_pdf",
        {"path": str(out), "title": "Timeline PDF", "max_slides": 4},
    ).to_dict()

    assert exported["ok"] is True
    assert out.read_bytes().startswith(b"%PDF")
    assert exported["result"]["slide_count"] == 3
    assert exported["result"]["backend"] == "fake"


def test_ppt_action_exports_timeline_video(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    from app.pptgen import video_export

    def fake_export_deck_video(deck, path, **kwargs):
        Path(path).write_bytes(b"fake-mp4")
        return {
            "schema": "tigercapture.ppt.video_export.v1",
            "ok": True,
            "output_path": str(path),
            "slide_count": len(deck.slides),
            "fps": int(kwargs.get("fps") or 1),
            "size": list(kwargs.get("size") or [320, 180]),
            "frames_written": 12,
            "duration_ms": 3000,
            "transition_count": 2,
            "audio_path": str(kwargs.get("audio_path") or ""),
            "audio_muxed": bool(kwargs.get("audio_path")),
        }

    monkeypatch.setattr(video_export, "export_deck_video", fake_export_deck_video)

    registry = build_default_action_registry(_Owner(tmp_path))
    action_ids = {row["id"] for row in registry.list_actions()}
    assert "ppt.timeline.export_video" in action_ids

    out = tmp_path / "timeline.mp4"
    exported = registry.execute(
        "ppt.timeline.export_video",
        {
            "path": str(out),
            "title": "Timeline Video",
            "max_slides": 4,
            "fps": 4,
            "width": 320,
            "height": 180,
            "audio_path": str(tmp_path / "voice.wav"),
        },
    ).to_dict()

    assert exported["ok"] is True
    assert out.read_bytes() == b"fake-mp4"
    assert exported["result"]["slide_count"] == 3
    assert exported["result"]["fps"] == 4
    assert exported["result"]["frames_written"] == 12
    assert exported["result"]["transition_count"] == 2
    assert exported["result"]["audio_muxed"] is True
