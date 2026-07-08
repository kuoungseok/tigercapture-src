from __future__ import annotations

from pathlib import Path


def test_ensure_deck_actor_posters_extracts_video_and_generates_actor_cards(tmp_path, monkeypatch):
    from PIL import Image

    from app.pptgen.actor_posters import ensure_deck_actor_posters
    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec

    def fake_extract_video_still(source_path, *, source_ms=0, output_dir=None):
        target = tmp_path / f"video_{int(source_ms)}.png"
        Image.new("RGB", (160, 90), (20, 120, 220)).save(target)
        return target

    monkeypatch.setattr("app.pptgen.actor_posters.frame_extract.extract_video_still", fake_extract_video_still)

    deck = DeckSpec(id="deck-actors", title="Actors")
    slide = SlideSpec(id="slide-001", title="Actors")
    slide.add_element(
        SlideElement(
            id="video-1",
            kind="video_actor",
            source_path=str(tmp_path / "clip.mp4"),
            x=0.1,
            y=0.1,
            w=0.4,
            h=0.3,
            metadata={"source_ms": 1200},
        )
    )
    slide.add_element(
        SlideElement(
            id="model-1",
            kind="ar_pbr_actor",
            name="Model",
            source_path=str(tmp_path / "scene.gltf"),
            x=0.5,
            y=0.1,
            w=0.35,
            h=0.3,
        )
    )
    deck.slides.append(slide)

    result = ensure_deck_actor_posters(deck, output_dir=tmp_path)

    assert result["schema"] == "tigercapture.ppt.actor_posters.v1"
    assert result["actor_count"] == 2
    assert result["generated_count"] == 2
    assert all(row["poster_path"] for row in result["posters"])
    assert all(Path(row["poster_path"]).is_file() for row in result["posters"])
    assert slide.elements[0].metadata["poster_path"].endswith("video_1200.png")
    assert slide.elements[1].metadata["poster_path"].endswith(".png")

    cached = ensure_deck_actor_posters(deck, output_dir=tmp_path)
    assert cached["actor_count"] == 2
    assert cached["generated_count"] == 0
