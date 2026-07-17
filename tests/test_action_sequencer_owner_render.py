from __future__ import annotations

import json
import subprocess
import sys
import types
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
    assert idle in descriptor.animation_sequence_paths
    assert action in descriptor.animation_sequence_paths
    assert anim_bp not in descriptor.animation_sequence_paths
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
    _touch(content / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "MM_Idle.uasset")
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


def test_owner_unreal_ar_pbr_bridge_exports_target_descriptor(tmp_path, monkeypatch) -> None:
    from app.action_sequencer_owner_render import discover_owner_render_descriptor
    from app.action_sequencer_unreal_asset_bridge import export_owner_unreal_ar_pbr_asset

    project = tmp_path / "ActionSequencer" / "ActionSequencer.uproject"
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_text('{"EngineAssociation":"5.8"}', encoding="utf-8")
    content = project.parent / "Content"
    _touch(content / "Variant_Combat" / "Blueprints" / "BP_CombatCharacter.uasset")
    _touch(content / "Characters" / "Mannequins" / "Meshes" / "SKM_Manny_Simple.uasset")
    descriptor = discover_owner_render_descriptor(project)
    target = tmp_path / "owner_real.arpbr"
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        target.write_text('{"schema":"tigerstudio.ar_pbr.unreal_skeletal_mesh_export.v1"}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout='{"ok":true}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    exported = export_owner_unreal_ar_pbr_asset(descriptor, target, max_triangles=1234)

    assert exported == target
    assert calls
    command = calls[0]
    assert "export-skeletal-mesh" in command
    assert "--asset" in command
    assert str(descriptor.render_asset_path) in command
    assert "--max-triangles" in command
    assert "1234" in command


def test_owner_unreal_animation_bridge_exports_clip(tmp_path, monkeypatch) -> None:
    from app.action_sequencer_owner_render import discover_owner_render_descriptor
    from app.action_sequencer_unreal_asset_bridge import export_owner_unreal_animation_clip

    project = tmp_path / "ActionSequencer" / "ActionSequencer.uproject"
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_text('{"EngineAssociation":"5.8"}', encoding="utf-8")
    content = project.parent / "Content"
    _touch(content / "Variant_Combat" / "Blueprints" / "BP_CombatCharacter.uasset")
    _touch(content / "Characters" / "Mannequins" / "Meshes" / "SKM_Manny_Simple.uasset")
    animation = _touch(content / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "MM_Idle.uasset")
    descriptor = discover_owner_render_descriptor(project)
    target = tmp_path / "idle.animation_clip.json"
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        target.write_text(
            json.dumps({
                "schema": "tigerstudio.ar_pbr.unreal_animation_clip_export.v1",
                "animation_clip": {"id": "MM_Idle", "name": "MM_Idle", "duration_ms": 1000.0, "model_curves": {}},
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout='{"ok":true}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    clip = export_owner_unreal_animation_clip(descriptor, animation, target, max_samples=24)

    assert clip["id"] == "MM_Idle"
    assert clip["_export_path"] == str(target)
    command = calls[0]
    assert "export-animation-clip" in command
    assert "--asset" in command
    assert str(animation) in command
    assert "--max-samples" in command
    assert "24" in command
    assert "--reference-mesh" in command
    assert str(descriptor.render_asset_path) in command


def test_owner_unreal_animation_bridge_falls_back_to_editor_python(tmp_path, monkeypatch) -> None:
    from app.action_sequencer_owner_render import discover_owner_render_descriptor
    from app.action_sequencer_unreal_asset_bridge import export_owner_unreal_animation_clip
    from app.unreal_link_reference_paths import UE_ENGINE_ENV

    project = tmp_path / "ActionSequencer" / "ActionSequencer.uproject"
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_text('{"EngineAssociation":"5.8"}', encoding="utf-8")
    content = project.parent / "Content"
    _touch(content / "Variant_Combat" / "Blueprints" / "BP_CombatCharacter.uasset")
    _touch(content / "Characters" / "Mannequins" / "Meshes" / "SKM_Manny_Simple.uasset")
    animation = _touch(content / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "MM_Idle.uasset")
    engine = tmp_path / "UE_5.8"
    editor = _touch(engine / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe")
    monkeypatch.setenv(UE_ENGINE_ENV, str(engine))
    descriptor = discover_owner_render_descriptor(project)
    target = tmp_path / "idle.fallback.animation_clip.json"
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        if "dotnet" in str(command[0]).lower():
            return subprocess.CompletedProcess(command, 1, stdout="", stderr='{"message":"cue4parse failed"}')
        assert str(editor) == command[0]
        assert kwargs["env"]["TIGERSTUDIO_UNREAL_ANIM_ASSET"] == "/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle"
        assert kwargs["env"]["TIGERSTUDIO_UNREAL_REFERENCE_MESH"] == "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
        target.write_text(
            json.dumps({
                "schema": "tigerstudio.ar_pbr.unreal_animation_clip_export.v1",
                "exporter": "unreal_editor_python",
                "animation_clip": {
                    "id": "MM_Idle",
                    "name": "MM_Idle",
                    "duration_ms": 1000.0,
                    "source_mode": "unreal_editor_python_pose",
                    "model_curves": {"bone_0": {}},
                },
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    clip = export_owner_unreal_animation_clip(descriptor, animation, target, max_samples=12)

    assert clip["id"] == "MM_Idle"
    assert clip["_exporter"] == "unreal_editor_python"
    assert len(calls) == 2
    assert "export-animation-clip" in calls[0]
    assert any(str(item).startswith("-ExecutePythonScript=") for item in calls[1])


def test_owner_ar_pbr_window_uses_left_stage_view(tmp_path, monkeypatch) -> None:
    import app.action_sequencer_owner_render as owner_render

    assert owner_render.OWNER_ANIMATION_PANEL_WIDTH == 200
    assert owner_render.OWNER_ANIMATION_PREVIEW_BACKEND == "uasset_inspector_gpu_bone_palette"

    project = tmp_path / "ActionSequencer" / "ActionSequencer.uproject"
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_text('{"EngineAssociation":"5.8"}', encoding="utf-8")
    content = project.parent / "Content"
    _touch(content / "Variant_Combat" / "Blueprints" / "BP_CombatCharacter.uasset")
    _touch(content / "Characters" / "Mannequins" / "Meshes" / "SKM_Manny_Simple.uasset")
    _touch(content / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "MM_Idle.uasset")

    exported_asset = tmp_path / "owner.arpbr"
    exported_asset.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(owner_render, "export_owner_unreal_ar_pbr_asset", lambda _descriptor: exported_asset)

    captured: dict[str, object] = {}

    class FakeSignal:
        def __init__(self, key: str) -> None:
            self._key = key

        def connect(self, callback) -> None:
            captured[self._key] = callback

    class FakeOwnerAnimationPanel:
        def __init__(self, descriptor) -> None:
            captured["panel_descriptor"] = descriptor
            self._descriptor = descriptor
            self.animation_selected = FakeSignal("animation_callback")
            self.animation_preview_requested = FakeSignal("animation_preview_callback")

        def selected_animation_path(self):
            return self._descriptor.idle_animation_path

    class FakeArPbrAssetPreviewWindow:
        def __init__(self, *args, **kwargs) -> None:
            captured["args"] = args
            captured["kwargs"] = kwargs

        def setWindowTitle(self, title: str) -> None:
            captured["title"] = title

        def show(self) -> None:
            captured["shown"] = True

        def raise_(self) -> None:
            captured["raised"] = True

        def activateWindow(self) -> None:
            captured["activated"] = True

        def apply_animation_preview_once(self, clip: str):
            raise AssertionError("Unreal animation preview must not use AR/PBR skeletal deformation")

        def attach_animation_clip(self, clip: dict):
            raise AssertionError("Unreal animation preview must not attach AR/PBR animation clips")

    fake_preview_module = types.ModuleType("app.ar_pbr.preview_window")
    fake_preview_module.ArPbrAssetPreviewWindow = FakeArPbrAssetPreviewWindow
    monkeypatch.setitem(sys.modules, "app.ar_pbr.preview_window", fake_preview_module)
    monkeypatch.setattr(owner_render, "_OwnerAnimationPanel", FakeOwnerAnimationPanel)

    owner = types.SimpleNamespace()
    window = owner_render.open_action_sequencer_owner_render_window(owner, project)

    assert window is owner._action_sequencer_owner_render_window
    assert captured["args"][0] == exported_asset
    assert captured["kwargs"]["initial_view"] == owner_render.OWNER_STAGE_PREVIEW_VIEW
    assert captured["kwargs"]["left_panel"] is not None
    assert captured["kwargs"]["controls_mode"] == "cubemap_only"
    assert captured["kwargs"]["initial_lighting"]["show_environment_background"] is False
    assert captured["panel_descriptor"].animation_sequence_paths
    assert callable(captured["animation_callback"])
    assert callable(captured["animation_preview_callback"])
    captured["animation_preview_callback"]({
        "animation_path": content / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "MM_Idle.uasset",
        "clip": "MM_Idle",
        "apply_frame_ms": 0,
        "play_once": True,
    })
    assert window.owner_animation_preview_request["preview_backend"] == owner_render.OWNER_ANIMATION_PREVIEW_BACKEND
    assert window.owner_animation_preview_request["ar_pbr_animation_enabled"] is False
    assert window.owner_animation_preview_request["reference_pipeline"] == "UAssetInspector SamplePalette -> Bones UBO -> skinned shader"
    assert window.owner_animation_preview_result["status"] == "requires_uasset_inspector_palette_renderer"
    assert window.owner_animation_preview_result["clip"] == "MM_Idle"
    assert window.owner_animation_preview_result["ar_pbr_animation_enabled"] is False
    assert captured["shown"] is True
    assert captured["raised"] is True
    assert captured["activated"] is True
