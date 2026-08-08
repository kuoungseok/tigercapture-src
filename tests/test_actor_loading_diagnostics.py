from __future__ import annotations


def test_actor_loading_diagnostic_card_is_actionable_for_mmd_failure(tmp_path):
    from app.actor_loading_status import actor_loading_diagnostic_card, format_actor_loading_diagnostic_card

    card = actor_loading_diagnostic_card(
        "mmd",
        str(tmp_path / "missing.pmx"),
        status="error",
        stage="parse",
        message="PMX decode failed",
    )
    text = format_actor_loading_diagnostic_card(card)

    assert card["schema"] == "tigercapture.actor.loading_diagnostic_card.v1"
    assert card["kind"] == "mmd"
    assert card["tone"] == "error"
    assert card["blockers"]
    assert any("PMX" in action or "MMD" in action for action in card["actions"])
    assert "Next steps:" in text


def test_actor_loading_cache_persists_diagnostic_card(tmp_path):
    from app.actor_loading_cache import actor_loading_cache_report, record_actor_load

    cache_path = tmp_path / "actor_loading_cache.json"
    record_actor_load(
        "spine",
        str(tmp_path / "missing.skel"),
        status="error",
        stage="parse",
        message="no alpha pixels",
        cache_path=cache_path,
    )
    report = actor_loading_cache_report(cache_path)
    entry = report["entries"][0]

    assert entry["diagnostic_card"]["schema"] == "tigercapture.actor.loading_diagnostic_card.v1"
    assert entry["diagnostic_card"]["status"] == "error"
    assert entry["diagnostic_card"]["actions"]
