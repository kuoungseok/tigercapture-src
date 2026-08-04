from pathlib import Path

from app.motion_designer.templates import instantiate_template, list_templates


def _hot_rows() -> list[dict]:
    return [row for row in list_templates() if row["category"] == "Hot Motion 2026"]


def test_hot_motion_2026_catalog_has_exactly_ten_distinct_templates():
    rows = _hot_rows()
    assert len(rows) == 10
    assert len({row["id"] for row in rows}) == 10
    assert len({row["default_duration_ms"] for row in rows}) >= 6


def test_hot_motion_2026_templates_use_durable_generated_media_and_editable_layers():
    for row in _hot_rows():
        composition = instantiate_template(str(row["id"]), variant="16:9")
        state = composition.metadata["trend_template_state"]
        assert state["editable"] is True
        assert composition.duration_ms == row["default_duration_ms"]
        backgrounds = [
            layer for layer in composition.layers
            if layer.metadata.get("replaceable") == "background_image"
        ]
        assert backgrounds
        source = Path(backgrounds[0].source.uri)
        assert source.is_file()
        assert "resources" in source.parts
        assert "hot_2026" in source.parts
        assert any(layer.layer_type == "text" for layer in composition.layers)
        assert any(layer.metadata.get("template_role") == "scene" for layer in composition.layers)


def test_hot_motion_2026_templates_have_distinct_layout_signatures():
    signatures = set()
    for row in _hot_rows():
        composition = instantiate_template(str(row["id"]), variant="16:9")
        roles = tuple(sorted({
            str(layer.metadata.get("template_role") or "")
            for layer in composition.layers
            if layer.metadata.get("hot_2026_distinct_layout")
        }))
        layer_types = tuple(sorted(
            (layer.layer_type, str(layer.metadata.get("template_role") or ""))
            for layer in composition.layers
        ))
        signatures.add((roles, layer_types))
    assert len(signatures) == 10
