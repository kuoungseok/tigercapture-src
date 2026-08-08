from __future__ import annotations

from app.motion_designer.templates import TEMPLATE_CATALOG, TEMPLATE_VARIANTS, instantiate_template


def test_template_variants_use_declared_dimensions_and_roles() -> None:
    for template in TEMPLATE_CATALOG.values():
        for variant in template.variants:
            composition = instantiate_template(template.id, variant=variant)
            assert (composition.width, composition.height) == TEMPLATE_VARIANTS[variant]
            roles = {str(layer.metadata.get("template_role") or "") for layer in composition.layers}
            assert "headline" in roles
            assert roles - {"headline", "subtitle", "tutorial_hint"}


def test_vertical_only_template_rejects_landscape() -> None:
    try:
        instantiate_template("vertical_shorts_hook", variant="16:9")
    except ValueError as exc:
        assert "does not support" in str(exc)
    else:
        raise AssertionError("vertical template accepted an undeclared landscape variant")
