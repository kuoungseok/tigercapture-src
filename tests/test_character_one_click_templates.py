from __future__ import annotations

from pathlib import Path


class _Owner:
    def __init__(self) -> None:
        from app.timeline_model import VideoClip, VideoTrack

        self._tracks = [
            VideoTrack(
                id=1,
                clips=[
                    VideoClip(
                        id=10,
                        source_duration_ms=12_000,
                        timeline_in_ms=0,
                        source_in_ms=0,
                        source_out_ms=12_000,
                    )
                ],
            )
        ]
        self._audio_tracks = []
        self._selected_clips = [(1, 10)]
        self._track_rows = {}
        self._live2d_actor_tracks = []
        self._spine_actor_tracks = []
        self.changes: list[str] = []
        self.refresh_count = 0
        self.width_count = 0

    def _register_change(self, label: str = "") -> None:
        self.changes.append(str(label))

    def _refresh_player_tracks(self) -> None:
        self.refresh_count += 1

    def _update_tracks_host_width(self) -> None:
        self.width_count += 1


def test_character_one_click_template_catalog_contains_required_result_types():
    from app.character_one_click_templates import character_one_click_templates, character_short_template_ids

    rows = character_one_click_templates()
    ids = {row["id"] for row in rows}
    assert len(rows) == 9
    assert ids == {
        "template-character-intro-short",
        "template-talking-live2d-short",
        "template-game-ui-commentary",
        "template-gacha-character-showcase",
        "template-mmd-dance-clip",
        "template-anime-pv-intro",
        "template-meme-reaction-character",
        "template-vtuber-announcement",
        "template-subtitle-to-voice-dialogue-scene",
    }
    assert all(row["preferred_kinds"] for row in rows)
    assert character_short_template_ids() == [
        "template-character-intro-short",
        "template-talking-live2d-short",
        "template-game-ui-commentary",
        "template-gacha-character-showcase",
        "template-meme-reaction-character",
    ]
    short_rows = [row for row in rows if "character-short" in row["tags"]]
    assert len(short_rows) == 5


def test_character_one_click_plan_uses_existing_actions_for_live2d(tmp_path):
    from app.character_one_click_templates import build_character_one_click_template_plan

    model = tmp_path / "avatar.model3.json"
    model.write_text("{}", encoding="utf-8")
    plan = build_character_one_click_template_plan(
        "template-character-intro-short",
        {
            "kind": "live2d",
            "path": str(model),
            "display_name": "Hero",
            "render": {"capable": True, "status": "ready"},
            "recommended_transform": {"pos_x": 0.5, "pos_y": 0.6, "scale": 0.9},
        },
        start_ms=1200,
        track_id=1,
        clip_id=10,
    )

    assert plan["ok"] is True
    assert plan["step_count"] >= 3
    assert plan["steps"][0]["action"] == "actor.add"
    assert plan["steps"][0]["params"]["kind"] == "live2d"
    assert plan["steps"][0]["params"]["start_ms"] == 1200
    assert any(step["action"] == "text.add" and step["executable"] for step in plan["steps"])


def test_character_template_actions_apply_live2d_actor_and_text(tmp_path):
    from app.actions import build_default_action_registry

    model = tmp_path / "avatar.model3.json"
    model.write_text("{}", encoding="utf-8")
    owner = _Owner()
    registry = build_default_action_registry(owner)
    ids = {row["id"] for row in registry.specs()}
    assert {
        "character.template.list",
        "character.template.plan",
        "character.template.apply",
    }.issubset(ids)

    result = registry.execute(
        "character.template.apply",
        {
            "template_id": "template-character-intro-short",
            "asset_record": {
                "kind": "live2d",
                "path": str(model),
                "display_name": "Hero",
                "render": {"capable": True, "status": "ready"},
                "recommended_transform": {"pos_x": 0.5, "pos_y": 0.6, "scale": 0.9},
            },
            "start_ms": 500,
            "track_id": 1,
            "clip_id": 10,
        },
    ).to_dict()

    assert result["ok"] is True
    assert result["changed"] is True
    assert len(owner._live2d_actor_tracks) == 1
    assert owner._live2d_actor_tracks[0].clips[0].model_path == str(model.resolve())
    assert len(owner._tracks[0].clips[0].typography_actors) >= 2


def test_character_template_apply_blocks_missing_required_character_step(tmp_path):
    from app.actions import build_default_action_registry

    owner = _Owner()
    registry = build_default_action_registry(owner)
    result = registry.execute(
        "character.template.apply",
        {
            "template_id": "template-character-intro-short",
            "path": str(Path(tmp_path) / "missing.model3.json"),
            "kind": "live2d",
        },
    ).to_dict()

    assert result["ok"] is False
    assert "required" in result["error"] or "missing" in result["error"]
