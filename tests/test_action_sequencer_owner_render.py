from __future__ import annotations

import json
from pathlib import Path


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_owner_render_descriptor_prefers_combat_owner_and_manny_mesh(tmp_path, monkeypatch) -> None:
    from app.action_sequencer_owner_render import (
        ACTION_SEQUENCER_PROJECT_ENV,
        default_action_sequencer_project_path,
        discover_owner_render_descriptor,
    )
    from app.unreal_link_reference_paths import UASSET_INSPECTOR_ENV, UE_ENGINE_ENV

    project = tmp_path / "ActionSequencer" / "ActionSequencer.uproject"
    _touch(project)
    content = project.parent / "Content"
    owner = _touch(content / "Variant_Combat" / "Blueprints" / "BP_CombatCharacter.uasset")
    mesh = _touch(content / "Characters" / "Mannequins" / "Meshes" / "SKM_Manny_Simple.uasset")
    anim_bp = _touch(content / "Variant_Combat" / "Anims" / "ABP_Manny_Combat.uasset")
    idle = _touch(content / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "MM_Idle.uasset")
    action = _touch(content / "Variant_Combat" / "Anims" / "AM_ComboAttack.uasset")

    inspector = tmp_path / "Inspector"
    _touch(inspector / "UAssetInspector.sln")
    _touch(inspector / "src" / "UAssetInspector.App" / "placeholder")
    _touch(inspector / "src" / "UAssetInspector.Core" / "placeholder")
    _touch(inspector / "src" / "UAssetInspector.Rendering" / "placeholder")
    engine = tmp_path / "UE_5.8"
    _touch(engine / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe")

    monkeypatch.setenv(ACTION_SEQUENCER_PROJECT_ENV, str(project))
    monkeypatch.setenv(UASSET_INSPECTOR_ENV, str(inspector))
    monkeypatch.setenv(UE_ENGINE_ENV, str(engine))

    assert default_action_sequencer_project_path() == project
    descriptor = discover_owner_render_descriptor()

    assert descriptor.owner_asset_path == owner
    assert descriptor.render_asset_path == mesh
    assert descriptor.animation_blueprint_path == anim_bp
    assert descriptor.idle_animation_path == idle
    assert descriptor.action_candidate_path == action
    assert descriptor.owner_class_name == "ACombatCharacter"
    assert descriptor.stage_position == (-120.0, 0.0, 0.0)
    assert descriptor.stage_forward == "+X / screen right"
    assert descriptor.can_render is True
    assert descriptor.diagnostics == ()


def test_owner_render_descriptor_reports_missing_mesh(tmp_path, monkeypatch) -> None:
    from app.action_sequencer_owner_render import discover_owner_render_descriptor
    from app.unreal_link_reference_paths import UASSET_INSPECTOR_ENV, UE_ENGINE_ENV

    project = tmp_path / "ActionSequencer" / "ActionSequencer.uproject"
    _touch(project)
    inspector = tmp_path / "Inspector"
    engine = tmp_path / "UE_5.8"
    monkeypatch.setenv(UASSET_INSPECTOR_ENV, str(inspector))
    monkeypatch.setenv(UE_ENGINE_ENV, str(engine))

    descriptor = discover_owner_render_descriptor(project)

    assert descriptor.owner_name == "BP_CombatCharacter"
    assert descriptor.owner_asset_path is None
    assert descriptor.render_asset_path is None
    assert descriptor.can_render is False
    assert any("BP_CombatCharacter" in item for item in descriptor.diagnostics)
    assert any("skeletal mesh" in item for item in descriptor.diagnostics)


def test_owner_ar_pbr_proxy_descriptor_is_renderable(tmp_path, monkeypatch) -> None:
    from app.action_sequencer_ar_pbr_proxy import (
        OWNER_AR_PBR_PROXY_SCHEMA,
        write_owner_ar_pbr_proxy_asset,
    )
    from app.action_sequencer_owner_render import discover_owner_render_descriptor
    from app.ar_pbr.importer import import_asset

    project = tmp_path / "ActionSequencer" / "ActionSequencer.uproject"
    _touch(project)
    content = project.parent / "Content"
    _touch(content / "Variant_Combat" / "Blueprints" / "BP_CombatCharacter.uasset")
    _touch(content / "Characters" / "Mannequins" / "Meshes" / "SKM_Manny_Simple.uasset")
    descriptor = discover_owner_render_descriptor(project)

    proxy_path = write_owner_ar_pbr_proxy_asset(descriptor, tmp_path / "owner.arpbr")
    payload = json.loads(proxy_path.read_text(encoding="utf-8"))

    assert payload["schema"] == OWNER_AR_PBR_PROXY_SCHEMA
    assert payload["runtime_format"] == "ar_scene_descriptor"
    assert payload["descriptor"]["metadata"]["owner_name"] == "BP_CombatCharacter"
    assert payload["descriptor"]["metadata"]["render_asset_path"].endswith("SKM_Manny_Simple.uasset")
    assert payload["descriptor"]["mesh_count"] >= 10
    assert sum(item["triangle_count"] for item in payload["descriptor"]["geometries"]) > 500

    imported, diagnostics = import_asset(proxy_path, settings={"disable_descriptor_cache": True})

    assert diagnostics["imported"] is True
    assert diagnostics["backend"] == "proxy_descriptor"
    assert imported["support"]["ok_for_preview"] is True
    assert imported["support"]["metrics"]["triangle_count"] > 500
