from app.actions.registry import ActionRegistry
from app.motion_designer.evaluator import evaluate_composition
import math
from pathlib import Path
import wave

import numpy as np


class Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}


def test_motion_ui_language_actions_are_automation_ready(monkeypatch) -> None:
    import app.i18n as i18n

    previous = i18n.current_language()
    monkeypatch.setattr(i18n, "save_language", lambda _code: None)
    try:
        registry = ActionRegistry(Owner())
        specs = {row["id"]: row for row in registry.list_actions()}
        assert "motion.ui.language.get" in specs
        assert "motion.ui.language.set" in specs

        changed = registry.execute(
            "motion.ui.language.set",
            {"language": "ja"},
        )
        assert changed.ok
        assert changed.result["language"] == "ja"
        inspected = registry.execute("motion.ui.language.get", {})
        assert inspected.ok
        assert inspected.result["language"] == "ja"
        assert set(inspected.result["supported_languages"]) == {
            "ko", "en", "ja", "zh", "fr", "de",
        }
    finally:
        i18n.set_language(previous)


def test_motion_actions_share_service_and_support_dry_run() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    preview = registry.execute("motion.composition.create", {"name": "Dry"}, dry_run=True)
    assert preview.ok and not owner._motion_compositions

    created = registry.execute("motion.composition.create", {"name": "Real"})
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Title", "layer_type": "text", "source": {"kind": "text", "params": {"text": "Tiger"}}},
    })
    assert added.ok
    listed = registry.execute("motion.layer.list", {"composition_id": composition_id})
    assert listed.result["count"] == 1
    specs = {row["id"]: row for row in registry.list_actions()}
    assert specs["motion.layer.add"]["undo_label"]


def test_motion_effect_actions_preserve_light_noise_and_stylize_parameters() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "Effect Automation",
        "duration_ms": 1000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Card", "layer_type": "shape", "out_ms": 1000},
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]

    for kind, params in (
        ("drop_shadow", {"offset_x": 18.0, "opacity": 0.7}),
        ("light_sweep", {"center_x": 0.35, "intensity": 1.6}),
        ("fractal_noise", {"amount": 0.4, "seed": 37.0}),
        ("posterize", {"levels": 7.0, "amount": 0.8}),
    ):
        result = registry.execute("motion.effect.add", {
            "composition_id": composition_id,
            "layer_id": layer_id,
            "effect": {"kind": kind, "params": params},
        })
        assert result.ok
        assert result.result["effect"]["kind"] == kind

    effects = owner._motion_compositions[composition_id].layers[0].effects
    assert [effect.kind for effect in effects] == [
        "drop_shadow",
        "light_sweep",
        "fractal_noise",
        "posterize",
    ]
    assert effects[2].params["seed"].default == 37.0
    assert effects[3].params["levels"].default == 7.0


def test_motion_craft_actions_apply_replace_and_clear_one_style(tmp_path) -> None:
    from PySide6.QtGui import QColor, QImage

    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {"name": "Craft"})
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Plate", "layer_type": "shape"},
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]

    presets = registry.execute("motion.craft.presets", {})
    assert presets.ok
    assert {row["id"] for row in presets.result["presets"]} == {
        "subtle_film", "handmade", "archive_print", "luxury_paper",
        "documentary_handheld", "vhs_tape", "printed_poster", "warm_film",
        "rough_cut",
    }
    first = registry.execute("motion.craft.apply", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "preset": "handmade",
        "settings": {"seed": 77, "grain_amount": 0.31},
    })
    assert first.ok
    effect_id = first.result["effect"]["id"]
    second = registry.execute("motion.craft.apply", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "preset": "archive_print",
    })
    assert second.ok
    assert second.result["effect"]["id"] == effect_id
    inspected = registry.execute("motion.craft.get", {
        "composition_id": composition_id,
        "layer_id": layer_id,
    })
    assert inspected.ok and inspected.result["enabled"]
    assert inspected.result["effect"]["metadata"]["preset"] == "archive_print"
    assert len(owner._motion_compositions[composition_id].layers[0].effects) == 1
    texture_path = tmp_path / "paper.png"
    texture = QImage(8, 8, QImage.Format_RGBA8888)
    texture.fill(QColor("#d8c49b"))
    assert texture.save(str(texture_path))
    attached = registry.execute("motion.craft.texture.attach", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "uri": str(texture_path),
        "blend_mode": "overlay",
        "opacity": 0.4,
    })
    assert attached.ok
    assert attached.result["texture"]["blend_mode"] == "overlay"
    randomized = registry.execute("motion.craft.seed.randomize", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "seed": 512,
    })
    assert randomized.ok and randomized.result["seed"] == 512
    unlocked = registry.execute("motion.craft.seed.lock", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "locked": False,
    })
    assert unlocked.ok and not unlocked.result["seed_locked"]
    preflight = registry.execute("motion.craft.preflight", {
        "composition_id": composition_id,
        "layer_id": layer_id,
    })
    assert preflight.ok
    assert preflight.result["issues"] == ["craft_seed_unlocked"]
    assert preflight.result["umg_disposition"] == "deterministic_bake"
    cleared = registry.execute("motion.craft.clear", {
        "composition_id": composition_id,
        "layer_id": layer_id,
    })
    assert cleared.ok and cleared.result["changed"]


def test_motion_glass_actions_create_bind_preflight_and_remove() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {"name": "Glass"})
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "CTA", "layer_type": "shape"},
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]
    presets = registry.execute("motion.material.glass.preset.list", {})
    assert presets.ok
    assert {row["id"] for row in presets.result["presets"]} == {
        "clear", "frosted", "tinted", "glossy", "liquid_cta",
    }
    applied = registry.execute("motion.material.glass.create", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "preset": "liquid_cta",
        "settings": {"refraction": 7.5},
    })
    assert applied.ok
    effect_id = applied.result["effect"]["id"]
    bound = registry.execute("motion.material.glass.driver.bind", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "source": "pointer",
        "strength": 2.0,
        "x": 0.5,
        "y": -0.25,
    })
    assert bound.ok
    assert bound.result["driver_value"] == [1.0, -0.5]
    updated = registry.execute("motion.material.glass.set", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "preset": "frosted",
    })
    assert updated.ok and updated.result["effect"]["id"] == effect_id
    assert updated.result["effect"]["metadata"]["driver"]["source"] == "pointer"
    preflight = registry.execute("motion.material.glass.preflight", {
        "composition_id": composition_id,
        "layer_id": layer_id,
    })
    assert preflight.ok
    assert preflight.result["preview_backend"] == "shared_backdrop_raster"
    assert preflight.result["umg_disposition"] == "deterministic_bake"
    removed = registry.execute("motion.material.glass.remove", {
        "composition_id": composition_id,
        "layer_id": layer_id,
    })
    assert removed.ok and removed.result["changed"]


def test_advanced_keyframe_and_behavior_actions_are_automation_ready() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {"name": "Automation", "duration_ms": 1000})
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Box", "layer_type": "shape", "out_ms": 1000},
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]
    first = registry.execute("motion.keyframe.add", {
        "composition_id": composition_id, "layer_id": layer_id, "property_name": "position",
        "keyframe": {"time_ms": 100, "value": [10, 20]},
    })
    assert first.ok
    key_id = owner._motion_compositions[composition_id].layers[0].transform.position.keyframes[0].id
    assert registry.execute("motion.keyframe.set_interpolation", {
        "composition_id": composition_id, "layer_id": layer_id, "property_name": "position",
        "keyframe_id": key_id, "interpolation": "hold",
    }).ok
    assert registry.execute("motion.keyframe.copy", {
        "composition_id": composition_id, "layer_id": layer_id, "property_name": "position",
    }).result["copied"] == 1
    assert registry.execute("motion.keyframe.paste", {
        "composition_id": composition_id, "layer_id": layer_id, "property_name": "position", "time_ms": 500,
    }).result["pasted"] == 1
    retimed = registry.execute("motion.curve.retime", {
        "composition_id": composition_id, "layer_id": layer_id, "property_name": "position", "offset_ms": 100,
    })
    assert retimed.result["retimed"] == 2

    behavior = registry.execute("motion.behavior.add", {
        "composition_id": composition_id, "layer_id": layer_id,
        "behavior": {"kind": "wiggle", "start_ms": 0, "end_ms": 1000, "params": {"amplitude": 8}},
    })
    behavior_id = behavior.result["behavior"]["id"]
    assert registry.execute("motion.behavior.set_param", {
        "composition_id": composition_id, "layer_id": layer_id, "behavior_id": behavior_id,
        "key": "frequency", "value": 3,
    }).ok
    before = evaluate_composition(owner._motion_compositions[composition_id], 250)[0].rotation
    baked = registry.execute("motion.behavior.bake", {
        "composition_id": composition_id, "layer_id": layer_id, "sample_fps": 20,
    })
    assert baked.ok and baked.result["keyframes"] > 0
    after = evaluate_composition(owner._motion_compositions[composition_id], 250)[0].rotation
    assert abs(before - after) < 1e-6
    assert owner._motion_compositions[composition_id].layers[0].behaviors == []

    effect = registry.execute("motion.effect.add", {
        "composition_id": composition_id, "layer_id": layer_id,
        "effect": {"kind": "brightness_contrast", "params": {"brightness": {"default": 0.1}}},
    })
    effect_id = effect.result["effect"]["id"]
    assert registry.execute("motion.effect.set_param", {
        "composition_id": composition_id, "layer_id": layer_id, "effect_id": effect_id,
        "key": "contrast", "value": 1.2,
    }).ok
    assert registry.execute("motion.effect.keyframe.set", {
        "composition_id": composition_id, "layer_id": layer_id, "effect_id": effect_id,
        "key": "brightness", "keyframe": {"time_ms": 500, "value": 0.25},
    }).ok
    assert registry.execute("motion.effect.list", {
        "composition_id": composition_id, "layer_id": layer_id,
    }).result["count"] == 1
    assert registry.execute("motion.effect.keyframe.delete", {
        "composition_id": composition_id, "layer_id": layer_id,
        "effect_id": effect_id, "key": "brightness", "time_ms": 500,
    }, confirm_destructive=True).ok
    assert (
        owner._motion_compositions[composition_id]
        .layers[0].effects[0].params["brightness"].keyframes
        == []
    )

    mask = registry.execute("motion.mask.add", {
        "composition_id": composition_id, "layer_id": layer_id,
        "mask": {"kind": "ellipse", "params": {"width": {"default": 100}, "height": {"default": 100}}},
    })
    mask_id = mask.result["mask"]["id"]
    assert registry.execute("motion.mask.set_param", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
        "key": "x", "value": 12,
    }).ok
    path = {"closed": True, "points": [
        {"position": [0, 0]}, {"position": [100, 0]},
        {"position": [100, 100]}, {"position": [0, 100]},
    ]}
    assert registry.execute("motion.mask.path.set", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
        "path": path,
    }).ok
    assert registry.execute("motion.mask.keyframe.set", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
        "key": "feather", "keyframe": {"time_ms": 500, "value": 8},
    }).ok
    assert registry.execute("motion.mask.keyframe.delete", {
        "composition_id": composition_id, "layer_id": layer_id,
        "mask_id": mask_id, "key": "feather", "time_ms": 500,
    }, confirm_destructive=True).ok
    assert (
        owner._motion_compositions[composition_id]
        .layers[0].masks[0].params["feather"].keyframes
        == []
    )
    tracking = registry.execute("motion.mask.tracking.set", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
        "tracking": {"mode": "planar", "origin": [50, 50], "samples": [
            {"time_ms": 0, "translate": [0, 0]},
            {"time_ms": 1000, "translate": [25, 10], "scale": [1.1, 1.1], "rotation": 5},
        ]},
    })
    assert tracking.ok and tracking.result["sample_count"] == 2
    assert registry.execute("motion.mask.tracking.clear", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
    }).ok
    specs = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.mask.keyframe.set", "motion.mask.path.set",
        "motion.mask.tracking.set", "motion.mask.tracking.generate",
        "motion.mask.tracking.clear",
    } <= specs
    assert registry.execute("motion.mask.delete", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
    }, confirm_destructive=True).ok


def test_adjustment_scope_actions_filter_targets_to_lower_render_layers() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute(
        "motion.composition.create",
        {"name": "Scoped Grade", "duration_ms": 1000},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    for layer in (
        {"id": "background", "name": "Background", "layer_type": "shape"},
        {"id": "controller", "name": "Controller", "layer_type": "null"},
        {"id": "grade", "name": "Grade", "layer_type": "adjustment"},
        {"id": "foreground", "name": "Foreground", "layer_type": "shape"},
    ):
        assert registry.execute(
            "motion.layer.add",
            {"composition_id": composition_id, "layer": layer},
        ).ok
    result = registry.execute(
        "motion.adjustment.scope.set",
        {
            "composition_id": composition_id,
            "layer_id": "grade",
            "mode": "selected_layers_below",
            "layer_ids": ["background", "controller", "foreground", "missing"],
        },
    )
    assert result.ok
    assert result.result["scope"] == {
        "mode": "selected_layers_below",
        "layer_ids": ["background"],
    }
    inspected = registry.execute(
        "motion.adjustment.scope.get",
        {"composition_id": composition_id, "layer_id": "grade"},
    )
    assert inspected.ok
    assert inspected.result["eligible_layer_ids"] == ["background"]


def test_effect_group_scope_actions_filter_targets_to_descendants() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute(
        "motion.composition.create",
        {"name": "Effect Group", "duration_ms": 1000},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    for layer in (
        {"id": "group", "name": "Group", "layer_type": "group"},
        {"id": "child", "name": "Child", "layer_type": "shape", "parent_id": "group"},
        {"id": "nested", "name": "Nested", "layer_type": "group", "parent_id": "group"},
        {"id": "grandchild", "name": "Grandchild", "layer_type": "shape", "parent_id": "nested"},
        {"id": "outside", "name": "Outside", "layer_type": "shape"},
    ):
        assert registry.execute(
            "motion.layer.add",
            {"composition_id": composition_id, "layer": layer},
        ).ok
    result = registry.execute(
        "motion.effect_group.scope.set",
        {
            "composition_id": composition_id,
            "layer_id": "group",
            "mode": "selected_descendants",
            "layer_ids": ["grandchild", "outside", "child", "missing"],
        },
    )
    assert result.ok
    assert result.result["scope"] == {
        "enabled": True,
        "mode": "selected_descendants",
        "layer_ids": ["grandchild", "child"],
    }
    inspected = registry.execute(
        "motion.effect_group.scope.get",
        {"composition_id": composition_id, "layer_id": "group"},
    )
    assert inspected.ok
    assert inspected.result["eligible_layer_ids"] == ["child", "grandchild"]
    assert inspected.result["resolved_layer_ids"] == ["child", "grandchild"]


def test_vector_shape_actions_update_shared_source_and_animated_params() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {"name": "Vector", "duration_ms": 2000})
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Logo", "layer_type": "shape", "out_ms": 2000,
                  "source": {"kind": "shape", "params": {"width": 400, "height": 300}}},
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]
    assert registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Cutout", "layer_type": "shape", "out_ms": 2000,
                  "source": {"kind": "shape", "params": {
                      "width": 120, "height": 120, "shape": "ellipse",
                  }}},
    }).ok
    operand_id = owner._motion_compositions[composition_id].layers[-1].id
    path = {"closed": True, "points": [
        {"position": [20, 20]}, {"position": [380, 20]},
        {"position": [380, 280]}, {"position": [20, 280]},
    ]}
    assert registry.execute("motion.vector.path.set", {
        "composition_id": composition_id, "layer_id": layer_id, "path": path,
    }).ok
    assert registry.execute("motion.vector.boolean.layers.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "operation": "subtract", "operand_layer_ids": [operand_id],
        "hide_operands": True,
    }).ok
    assert registry.execute("motion.vector.trim.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "start": 0.1, "end": 0.8, "offset": 0.05,
    }).ok
    assert registry.execute("motion.vector.offset_path.set", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "amount": 12,
        "join": "round",
    }).ok
    assert registry.execute("motion.vector.stroke.set", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "color": "#ffffff",
        "width": 6,
        "gradient": {
            "type": "linear",
            "stops": [[0, "#ff0000"], [1, "#0000ff"]],
        },
        "dash": [8, 4],
        "dash_offset": 2,
        "taper_start": 1,
        "taper_end": 0.25,
    }).ok
    assert registry.execute("motion.vector.repeater.set", {
        "composition_id": composition_id, "layer_id": layer_id, "count": 4,
        "offset": [18, 0], "rotation": 5, "scale": [.95, .95],
        "opacity_start": 1, "opacity_end": .4,
    }).ok
    assert registry.execute("motion.vector.param.keyframe.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "parameter_name": "trim", "keyframe": {
            "time_ms": 1000, "value": {"start": 0.2, "end": 1.0, "offset": 0.0},
        },
    }).ok
    layer = owner._motion_compositions[composition_id].layers[0]
    assert layer.source.params["shape"] == "path"
    assert layer.source.params["repeater"]["count"] == 4
    assert layer.source.params["offset_path"]["amount"] == 12
    assert layer.source.params["stroke_taper"]["end"] == 0.25
    assert layer.source.params["trim"]["value_type"] == "scalar"
    assert layer.source.params["trim"]["keyframes"][0]["time_ms"] == 1000
    assert layer.source.params["boolean"]["operand_layer_ids"] == [operand_id]
    specs = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.vector.path.set", "motion.vector.primitive.set",
        "motion.vector.boolean.set", "motion.vector.boolean.layers.set", "motion.vector.trim.set",
        "motion.vector.offset_path.set", "motion.vector.repeater.set",
        "motion.vector.stroke.set", "motion.vector.param.keyframe.set",
    } <= specs


def test_typography_actions_update_style_animation_path_and_keyframes() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {"name": "Type", "duration_ms": 2400})
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Title", "layer_type": "text", "out_ms": 2400,
                  "source": {"kind": "typography", "params": {"text": "Tiger"}}},
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]
    assert registry.execute("motion.typography.style.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "changes": {"font_family": "Segoe UI", "font_size": 84, "fill": "#f7f7f7"},
    }).ok
    assert registry.execute("motion.typography.animation.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "animation": {"in": "typewriter-in", "hold": "hold-wave", "out": "fade-out",
                      "unit": "word", "stagger_ms": 80},
    }).ok
    text_path = {"closed": False, "points": [
        {"position": [0, 100]}, {"position": [500, 100]},
    ]}
    assert registry.execute("motion.typography.text_path.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "path": text_path, "offset": .4,
    }).ok
    assert registry.execute("motion.typography.text_path.offset.set", {
        "composition_id": composition_id, "layer_id": layer_id, "offset": .6,
    }).ok
    assert registry.execute("motion.typography.param.keyframe.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "parameter_name": "text_path_offset", "keyframe": {"time_ms": 900, "value": .7},
    }).ok
    layer = owner._motion_compositions[composition_id].layers[0]
    assert layer.source.params["font_size"] == 84
    assert layer.source.params["text_animation"]["unit"] == "word"
    assert layer.source.params["text_path"]["points"][1]["position"] == [500, 100]
    assert layer.source.params["text_path_offset"]["default"] == .6
    assert layer.source.params["text_path_offset"]["keyframes"][0]["value"] == .7
    assert registry.execute("motion.typography.text_path.clear", {
        "composition_id": composition_id, "layer_id": layer_id,
    }).ok
    assert owner._motion_compositions[composition_id].layers[0].source.params["text_path"] is None
    specs = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.typography.style.set", "motion.typography.animation.set",
        "motion.typography.text_path.set", "motion.typography.text_path.clear",
        "motion.typography.text_path.offset.set", "motion.typography.param.keyframe.set",
        "motion.typography.preflight",
    } <= specs


def test_motion_ai_plan_and_apply_actions_share_the_reviewed_proposal_contract() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "AI Motion", "width": 1280, "height": 720, "duration_ms": 3000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    planned = registry.execute("motion.ai.plan", {
        "composition_id": composition_id,
        "prompt": 'fade in "AI TITLE"',
        "references": [{"kind": "image", "name": "reference.png", "uri": "C:/reference.png"}],
    })
    assert planned.ok
    proposal = planned.result
    assert proposal["schema"] == "tigercapture.motion.ai.proposal.v1"
    assert len(proposal["layers"]) == 2
    assert proposal["analysis"]["created_layer_count"] == 2
    assert proposal["analysis"]["missing_assets"]
    assert owner._motion_compositions[composition_id].layers == []

    applied = registry.execute("motion.ai.apply", {
        "composition_id": composition_id, "proposal": proposal,
    })
    assert applied.ok
    assert applied.result["added_layers"] == 2
    assert len(owner._motion_compositions[composition_id].layers) == 2
    specs = {row["id"] for row in registry.list_actions()}
    assert {"motion.ai.plan", "motion.ai.apply"} <= specs


def test_motion_audio_reactive_actions_share_analysis_preview_and_bake(tmp_path) -> None:
    rate = 16000
    t = np.arange(rate, dtype=np.float32) / rate
    audio = 0.45 * np.sin(2 * math.pi * 110 * t)
    audio[int(rate * .45):int(rate * .47)] += .8
    source = tmp_path / "pulse.wav"
    with wave.open(str(source), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())

    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {"name": "Audio", "duration_ms": 1000, "fps": 10})
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Pulse", "layer_type": "shape", "out_ms": 1000},
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]
    dry = registry.execute("motion.audio.analyze", {
        "composition_id": composition_id, "source_path": str(source),
    }, dry_run=True)
    assert dry.ok and "audio_analysis" not in owner._motion_compositions[composition_id].metadata
    analyzed = registry.execute("motion.audio.analyze", {
        "composition_id": composition_id, "source_path": str(source), "hop_ms": 25,
    })
    assert analyzed.ok and analyzed.result["sample_count"] >= 35
    analysis_id = analyzed.result["analysis_id"]
    reused = registry.execute("motion.audio.analyze", {
        "composition_id": composition_id, "source_path": str(source), "hop_ms": 25,
    })
    assert reused.result["reused"] is True
    bound = registry.execute("motion.audio_reactive.bind", {
        "composition_id": composition_id, "layer_id": layer_id, "analysis_id": analysis_id,
        "binding": {"property_name": "scale", "mode": "multiply", "output_min": 1, "output_max": 1.5,
                    "smoothing_ms": 0, "attack_ms": 0, "release_ms": 0},
    })
    assert bound.ok and bound.result["binding_count"] == 1
    binding_id = bound.result["binding"]["id"]
    assert registry.execute("motion.audio_reactive.update", {
        "composition_id": composition_id, "layer_id": layer_id, "binding_id": binding_id,
        "changes": {"output_max": 1.8},
    }).ok
    assert evaluate_composition(owner._motion_compositions[composition_id], 250)[0].scale[0] > 1.1
    baked = registry.execute("motion.audio_reactive.bake", {
        "composition_id": composition_id, "layer_id": layer_id, "sample_fps": 10,
    })
    assert baked.ok and baked.result["keyframe_count"] == 55


def test_motion_composer_and_voice_timing_actions_are_registered_and_attach_layers() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {"name": "Timing", "duration_ms": 3000})
    composition_id = created.result["payload"]["composition"]["id"]
    text = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Subtitle", "layer_type": "text", "out_ms": 3000,
                  "source": {"kind": "typography", "params": {"text": "Tiger"}}},
    })
    text_id = text.result["payload"]["composition"]["layers"][0]["id"]
    composer = registry.execute("motion.composer.import_timing", {
        "composition_id": composition_id,
        "music": {"id": "music_action", "bpm": 120, "duration_ms": 2000,
                  "prompt": "", "genre": "pop", "mood": "bright", "key": "C",
                  "sections": [], "tracks": []},
    })
    assert composer.ok and composer.result["beat_count"] == 5
    voice = registry.execute("motion.voice.import_timing", {
        "composition_id": composition_id, "text_layer_id": text_id,
        "rows": [{"start_ms": 0, "end_ms": 1000, "text": "Hello Tiger"}],
    })
    assert voice.ok and voice.result["word_count"] == 2
    layer = owner._motion_compositions[composition_id].layers[0]
    assert layer.source.params["text_reveal_timing"]["source_id"] == voice.result["timing"]["id"]
    specs = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.audio.analyze", "motion.audio_reactive.bind", "motion.audio_reactive.update",
        "motion.audio_reactive.bake", "motion.composer.import_timing", "motion.voice.import_timing",
    } <= specs


def test_motion_ar_pbr_camera_light_material_and_depth_actions() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "3D Motion", "width": 640, "height": 360, "duration_ms": 2000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    asset = str(Path("sample_assets/pbr_blender_scenes/polyhaven/models/Camera_01/Camera_01_1k.gltf").resolve())
    model = registry.execute("motion.ar_pbr.add", {
        "composition_id": composition_id, "asset_path": asset,
    })
    assert model.ok
    model_id = model.result["layer"]["id"]
    camera = registry.execute("motion.camera.add", {"composition_id": composition_id})
    light = registry.execute("motion.light.add", {"composition_id": composition_id})
    point = registry.execute("motion.light.add", {
        "composition_id": composition_id,
        "name": "Point Light",
        "params": {
            "light_type": "point",
            "position": [1.0, 2.0, 3.0],
            "range": 7.0,
            "intensity": 1.25,
        },
    })
    assert camera.ok and light.ok and point.ok
    assert registry.execute("motion.camera.update", {
        "composition_id": composition_id, "layer_id": camera.result["layer"]["id"],
        "changes": {
            "fov": 62.0,
            "projection": "orthographic",
            "orthographic_size": 4.5,
        },
        "time_ms": 500,
    }).ok
    camera_layer = owner._motion_compositions[composition_id].layers[1]
    assert camera_layer.source.params["projection"]["value_type"] == "string"
    assert registry.execute("motion.light.update", {
        "composition_id": composition_id, "layer_id": light.result["layer"]["id"],
        "changes": {"color": [1.0, .6, .3], "intensity": 1.1},
    }).ok
    assert registry.execute("motion.ar_pbr.set_material", {
        "composition_id": composition_id, "layer_id": model_id,
        "changes": {"override_strength": 1.0, "roughness": .28, "metallic": .7, "clearcoat": .6},
    }).ok
    depth = registry.execute("motion.depth_group.set", {
        "composition_id": composition_id, "member_layer_ids": [model_id],
        "depth_source_id": "video_depth", "occlusion": True,
    })
    assert depth.ok
    specs = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.ar_pbr.add", "motion.ar_pbr.set_material", "motion.ar_pbr.diagnostics",
        "motion.camera.add", "motion.camera.update", "motion.light.add", "motion.light.update",
        "motion.depth_group.set",
    } <= specs


def test_motion_live2d_spine_actor_actions_and_lipsync() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "Actor Motion", "width": 640, "height": 360, "duration_ms": 2000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    live2d_path = str(Path(
        "resources/live2d_samples/CubismWebSamples/Samples/Resources/Hiyori/Hiyori.model3.json"
    ).resolve())
    spine_path = str(Path(
        "resources/spine_samples/celestial-circus/export/celestial-circus-pro.skel"
    ).resolve())
    live2d = registry.execute("motion.live2d.add", {
        "composition_id": composition_id, "asset_path": live2d_path,
    })
    spine = registry.execute("motion.spine.add", {
        "composition_id": composition_id, "asset_path": spine_path,
    })
    assert live2d.ok and spine.ok
    live2d_id = live2d.result["layer"]["id"]
    assert registry.execute("motion.actor.update", {
        "composition_id": composition_id, "layer_id": live2d_id,
        "changes": {"playback": {"rate": 1.25}, "actor": {"scale": 1.4}},
    }).ok
    lipsync = registry.execute("motion.actor.lipsync.set", {
        "composition_id": composition_id, "layer_id": live2d_id, "source_id": "voice_action",
        "cues": [{"start_ms": 200, "end_ms": 500, "text": "a"}],
    })
    assert lipsync.ok and lipsync.result["cue_count"] == 1
    layer = next(item for item in owner._motion_compositions[composition_id].layers if item.id == live2d_id)
    assert layer.source.params["playback"]["rate"] == 1.25
    assert layer.metadata["voice_timing_source_id"] == "voice_action"
    specs = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.live2d.add", "motion.spine.add", "motion.actor.update",
        "motion.actor.lipsync.set", "motion.actor.diagnostics",
    } <= specs
