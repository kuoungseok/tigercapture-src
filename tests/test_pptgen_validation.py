from __future__ import annotations

from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec
from app.pptgen.validation import validate_deck, validation_report


def test_validation_reports_empty_deck():
    issues = validate_deck(DeckSpec(id="empty"))

    assert issues[0].code == "empty_deck"
    assert issues[0].severity == "error"


def test_validation_reports_missing_asset_warning():
    deck = DeckSpec(id="asset")
    slide = SlideSpec(id="slide-001")
    slide.add_element(SlideElement.image("image-1", "does-not-exist.png", x=0.1, y=0.1, w=0.5, h=0.4))
    deck.slides.append(slide)

    issues = validate_deck(deck)

    assert any(issue.code == "missing_asset" for issue in issues)


def test_validation_report_counts_actor_poster_readiness():
    deck = DeckSpec(id="actor")
    slide = SlideSpec(id="slide-001")
    slide.add_element(
        SlideElement(
            id="actor-1",
            kind="ar_pbr_actor",
            source_path="scene.gltf",
            x=0.1,
            y=0.1,
            w=0.5,
            h=0.4,
        )
    )
    deck.slides.append(slide)

    report = validation_report(deck)

    assert report["schema"] == "tigercapture.ppt.validation.v1"
    assert report["ok"] is True
    assert report["warning_count"] == 1
    assert report["info_count"] == 1
    codes = {row["code"] for row in report["issues"]}
    assert {"missing_asset", "actor_poster_missing"} <= codes
