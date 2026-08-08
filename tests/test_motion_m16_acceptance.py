from __future__ import annotations

from tools.qa_motion_m16_typography_vector import build_acceptance_corpus


def test_m16_acceptance_corpus_has_required_categories_and_features() -> None:
    compositions = build_acceptance_corpus()
    assert len(compositions) == 13
    assert sum(row.name.startswith("Kinetic") for row in compositions) == 5
    assert sum(row.name.startswith("Logo Reveal") for row in compositions) == 5
    assert sum(row.name.startswith("Infographic Path") for row in compositions) == 3
    assert all(row.duration_ms >= 2000 for row in compositions)
    assert all(row.layers for row in compositions)
    assert any(
        layer.source.params.get("text_animators")
        for composition in compositions
        for layer in composition.layers
    )
    assert any(
        layer.metadata.get("path_morph")
        for composition in compositions
        for layer in composition.layers
    )
    assert any(
        layer.source.params.get("stroke_gradient")
        for composition in compositions
        for layer in composition.layers
    )
