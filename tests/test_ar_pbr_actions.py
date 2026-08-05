from __future__ import annotations


class _Canvas:
    def __init__(self) -> None:
        self.update_count = 0

    def update(self) -> None:
        self.update_count += 1


class _PreviewState:
    pitch = -10.0
    yaw = 72.0
    roll = 0.0
    zoom = 1.5
    camera_z = 3.25
    pan_x = 0.0
    pan_y = 0.0
    pan_z = 0.0


class _PreviewGL:
    def __init__(self, state: _PreviewState) -> None:
        self.state = state
        self.auto_fit_enabled = True
        self.auto_fit_pending = True
        self.update_count = 0
        self.background_visible = True

    def fit_current_view(self) -> dict:
        self.state.zoom = 2.0
        return {"zoom": self.state.zoom}

    def set_environment_background_visible(self, visible: bool) -> None:
        self.background_visible = bool(visible)

    def update(self) -> None:
        self.update_count += 1


class _PreviewWindow:
    def __init__(self) -> None:
        self._state = _PreviewState()
        self._gl_widget = _PreviewGL(self._state)
        self.fit_count = 0
        self.sync_count = 0
        self.show_count = 0
        self.raise_count = 0
        self.activate_count = 0
        self.background_visible = True
        self.apply_count = 0
        self.last_apply_emit = None
        self._settings = {
            "render_profile": "authored",
            "tone_exposure": 0.0,
            "tone_gamma": 2.2,
            "shadow_strength": 0.6,
            "show_environment_background": True,
            "ambient_occlusion_mode": "off",
            "ao_strength": 0.0,
            "ao_radius": 3.0,
            "ao_distance": 0.45,
            "hybrid_sample_count": 1,
            "diffuse_gi_strength": 0.0,
            "specular_gi_strength": 0.0,
            "denoise_strength": 0.0,
            "ibl_exposure": 1.1,
            "ibl_rotation": 0.0,
            "surface_override_strength": 0.0,
            "surface_roughness": 0.45,
            "surface_metallic": 0.0,
            "surface_reflectance": 0.5,
            "clearcoat_strength": 0.0,
            "clearcoat_roughness": 0.12,
            "clearcoat_ior": 1.5,
        }

    def lighting_settings(self) -> dict:
        return dict(self._settings)

    def apply_lighting_settings(self, settings: dict, *, emit: bool = True) -> None:
        self.apply_count += 1
        self.last_apply_emit = emit
        for key, value in dict(settings or {}).items():
            self._settings[key] = value

    def fit_view(self) -> None:
        self.fit_count += 1
        self._gl_widget.fit_current_view()

    def sync_controls(self) -> None:
        self.sync_count += 1

    def show(self) -> None:
        self.show_count += 1

    def raise_(self) -> None:
        self.raise_count += 1

    def activateWindow(self) -> None:
        self.activate_count += 1

    def _set_environment_background_visible(self, visible: bool, *, emit: bool = True) -> None:
        self.background_visible = bool(visible)
        self._gl_widget.set_environment_background_visible(visible)


class _Owner:
    def __init__(self) -> None:
        self._ar_pbr_tracks = [
            {
                "id": "ar_pbr_001",
                "asset_path": "E:/assets/camera.gltf",
                "start_ms": 0,
                "end_ms": 10_000,
            }
        ]
        self._selected_ar_pbr_track_id = ""
        self._ar_pbr_gizmo_visible_track_id = ""
        self._ar_pbr_gizmo_drag = {"mode": "move_xy"}
        self._drawing_canvas = _Canvas()
        self.row_selection = []
        self.depth_cue_end_count = 0
        self._preview_gl_frame_size = (1280, 720)
        self._player = type(
            "_Player",
            (),
            {
                "_ar_pbr_last_diagnostics": {
                    "mode": "gpu_preview",
                    "packet_cache_hit": True,
                    "packet_cache_id": "packet_001",
                    "playback_optimized": True,
                }
            },
        )()
        self._preview_gl = type(
            "_PreviewGL",
            (),
            {
                "ar_pbr_overlay_diagnostics": lambda _self: {
                    "item_count": 1,
                    "vbo": {
                        "ar_pbr_vbo_cache_hits": 4,
                        "ar_pbr_vbo_cache_misses": 1,
                    },
                    "items": [
                        {
                            "track_id": "ar_pbr_001",
                            "packet_cache_id": "packet_001",
                            "diagnostics": {
                                "ar_pbr_vbo_cache_hit_rate": 0.8,
                            },
                        }
                    ],
                }
            },
        )()
        self._ar_pbr_preview_windows = []

    def _ar_pbr_active_tracks_at_playhead(self):
        return list(self._ar_pbr_tracks)

    def _set_ar_pbr_row_selection(self, track_id: str) -> None:
        self.row_selection.append(str(track_id))

    def _end_ar_pbr_depth_interaction_cue(self) -> None:
        self.depth_cue_end_count += 1


def test_ar_pbr_gizmo_actions_are_registered_for_automation() -> None:
    from app.actions import build_default_action_registry

    registry = build_default_action_registry(_Owner())
    action_specs = {row["id"]: row for row in registry.list_actions()}
    action_ids = set(action_specs)

    assert {
        "ar_pbr.preview.diagnostics",
        "ar_pbr.preview.view.get",
        "ar_pbr.preview.view.set",
        "ar_pbr.preview.settings.get",
        "ar_pbr.preview.settings.set",
        "ar_pbr.preview.depth_view.get",
        "ar_pbr.preview.depth_view.set",
        "ar_pbr.preview.surface.get",
        "ar_pbr.preview.surface.set",
        "ar_pbr.preview.rt_status",
        "ar_pbr.preview.rt_render",
        "ar_pbr.gizmo.state",
        "ar_pbr.gizmo.show",
        "ar_pbr.gizmo.hide",
        "ar_pbr.texture_lab.open",
        "ar_pbr.texture_lab.preview",
        "ar_pbr.texture_lab.backend_status",
        "ar_pbr.texture_lab.export",
        "ar_pbr.texture_lab.substrate_plan",
    } <= action_ids
    rt_render_schema = action_specs["ar_pbr.preview.rt_render"]["params_schema"]
    assert rt_render_schema["required"] == ["output_path"]
    assert rt_render_schema["properties"]["render_mode"]["enum"] == ["hybrid_rt", "path_traced"]
    settings_schema = action_specs["ar_pbr.preview.settings.set"]["params_schema"]["properties"]
    view_schema = action_specs["ar_pbr.preview.view.set"]["params_schema"]["properties"]
    depth_schema = action_specs["ar_pbr.preview.depth_view.set"]["params_schema"]["properties"]
    assert {"pan_x", "pan_y", "pan_z"} <= set(view_schema)
    assert {"mode", "refresh"} <= set(depth_schema)
    assert {"matte", "distance", "plane"} <= set(depth_schema["mode"]["enum"])
    assert {
        "ambient_occlusion_mode",
        "ao_strength",
        "ao_radius",
        "ao_distance",
        "hybrid_sample_count",
        "diffuse_gi_strength",
        "specular_gi_strength",
        "denoise_strength",
        "ibl_exposure",
        "ibl_rotation",
        "surface_override_strength",
        "surface_roughness",
        "surface_metallic",
        "surface_reflectance",
        "clearcoat_strength",
        "clearcoat_roughness",
        "clearcoat_ior",
        "surface",
        "clearcoat",
        "parallax",
    } <= set(settings_schema)
    assert {"off", "parallax", "pom"} <= set(
        settings_schema["parallax"]["properties"]["mode"]["enum"]
    )
    surface_schema = action_specs["ar_pbr.preview.surface.set"]["params_schema"]["properties"]
    assert {
        "ibl_exposure",
        "ibl_rotation",
        "surface_override_strength",
        "surface_roughness",
        "surface_metallic",
        "surface_reflectance",
        "clearcoat_strength",
        "clearcoat_roughness",
        "clearcoat_ior",
    } <= set(surface_schema)
    texture_export_schema = action_specs["ar_pbr.texture_lab.export"]["params_schema"]["properties"]
    texture_preview_schema = action_specs["ar_pbr.texture_lab.preview"]["params_schema"]["properties"]
    backend_schema = action_specs["ar_pbr.texture_lab.backend_status"]["params_schema"]["properties"]
    assert {"image_path", "output_dir", "settings", "maps", "packed_layouts", "backend", "allow_cpu"} <= set(
        texture_export_schema
    )
    assert "allow_cpu" in backend_schema
    assert "allow_cpu" in texture_preview_schema
    assert {"auto", "cpu", "torch_cuda"} <= set(backend_schema["backend"]["enum"])
    assert {"auto", "cpu", "torch_cuda"} <= set(texture_preview_schema["backend"]["enum"])
    assert {"plane", "sphere"} <= set(texture_preview_schema["preview_shape"]["enum"])
    assert {"material", "normal", "f0", "f90_mask", "unreal_orm", "gltf_mr"} <= set(
        texture_preview_schema["preview_mode"]["enum"]
    )
    assert {"base_color", "f0", "f90_mask"} <= set(texture_export_schema["maps"]["items"]["enum"])
    assert {"unreal_orm", "arm", "gltf_mr", "rma"} <= set(
        texture_export_schema["packed_layouts"]["items"]["enum"]
    )


def test_ar_pbr_preview_diagnostics_action_reports_packet_and_vbo_state() -> None:
    from app.actions import build_default_action_registry

    owner = _Owner()
    registry = build_default_action_registry(owner)

    result = registry.execute("ar_pbr.preview.diagnostics").to_dict()

    assert result["ok"] is True
    payload = result["result"]
    assert payload["active_track_ids"] == ["ar_pbr_001"]
    assert payload["preview_frame_size"] == [1280, 720]
    assert payload["packet_cache_hit"] is True
    assert payload["packet_cache_id"] == "packet_001"
    assert payload["gl"]["vbo"]["ar_pbr_vbo_cache_hits"] == 4
    assert payload["gl"]["items"][0]["diagnostics"]["ar_pbr_vbo_cache_hit_rate"] == 0.8


def test_ar_pbr_preview_depth_view_actions_toggle_main_viewer_mode() -> None:
    from app.actions import build_default_action_registry

    owner = _Owner()
    registry = build_default_action_registry(owner)

    initial = registry.execute("ar_pbr.preview.depth_view.get").to_dict()
    assert initial["ok"] is True
    assert initial["result"]["mode"] == "off"
    assert initial["result"]["enabled"] is False

    changed = registry.execute(
        "ar_pbr.preview.depth_view.set",
        {"mode": "heat", "refresh": False},
    ).to_dict()
    assert changed["ok"] is True
    assert changed["result"]["before"] == "off"
    assert changed["result"]["mode"] == "heat"
    assert changed["result"]["enabled"] is True
    assert owner._player._ar_pbr_depth_view_mode_value == "heat"

    disabled = registry.execute(
        "ar_pbr.preview.depth_view.set",
        {"mode": "off", "refresh": False},
    ).to_dict()
    assert disabled["ok"] is True
    assert disabled["result"]["mode"] == "off"


def test_ar_pbr_gizmo_actions_show_and_hide_viewport_gizmo() -> None:
    from app.actions import build_default_action_registry

    owner = _Owner()
    registry = build_default_action_registry(owner)

    initial = registry.execute("ar_pbr.gizmo.state").to_dict()
    assert initial["ok"] is True
    assert initial["result"]["visible"] is False
    assert initial["result"]["selected_track_id"] == ""

    shown = registry.execute("ar_pbr.gizmo.show", {"track_id": "ar_pbr_001"}).to_dict()
    assert shown["ok"] is True
    assert shown["changed"] is False
    assert shown["result"]["visible"] is True
    assert shown["result"]["visible_track_id"] == "ar_pbr_001"
    assert owner._selected_ar_pbr_track_id == "ar_pbr_001"
    assert owner._ar_pbr_gizmo_visible_track_id == "ar_pbr_001"
    assert owner._ar_pbr_gizmo_drag is None
    assert owner.row_selection == ["ar_pbr_001"]
    assert owner._drawing_canvas.update_count == 1

    hidden = registry.execute("ar_pbr.gizmo.hide").to_dict()
    assert hidden["ok"] is True
    assert hidden["changed"] is False
    assert hidden["result"]["visible"] is False
    assert hidden["result"]["visible_track_id"] == ""
    assert owner._selected_ar_pbr_track_id == "ar_pbr_001"
    assert owner._ar_pbr_gizmo_visible_track_id == ""
    assert owner.depth_cue_end_count == 1
    assert owner._drawing_canvas.update_count == 2


def test_ar_pbr_preview_view_get_returns_full_framing_state() -> None:
    from app.actions import build_default_action_registry

    owner = _Owner()
    preview = _PreviewWindow()
    preview._state.pitch = 14.0
    preview._state.yaw = 42.0
    preview._state.roll = -3.0
    preview._state.zoom = 2.7
    preview._state.camera_z = 2.2
    preview._state.pan_x = 0.21
    preview._state.pan_y = -0.11
    preview._state.pan_z = 0.04
    owner._ar_pbr_preview_windows.append(preview)
    registry = build_default_action_registry(owner)

    result = registry.execute("ar_pbr.preview.view.get").to_dict()

    assert result["ok"] is True
    assert result["result"]["view"] == {
        "pitch": 14.0,
        "yaw": 42.0,
        "roll": -3.0,
        "zoom": 2.7,
        "camera_z": 2.2,
        "pan_x": 0.21,
        "pan_y": -0.11,
        "pan_z": 0.04,
    }


def test_ar_pbr_preview_view_set_reframes_open_asset_preview() -> None:
    from app.actions import build_default_action_registry

    owner = _Owner()
    preview = _PreviewWindow()
    owner._ar_pbr_preview_windows.append(preview)
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "ar_pbr.preview.view.set",
        {
            "fit_first": True,
            "zoom_factor": 1.65,
            "camera_z": 2.4,
            "yaw": 38.0,
            "pan_x": 0.22,
            "pan_y": -0.14,
            "pan_z": 0.05,
            "hide_environment_background": True,
        },
    ).to_dict()

    assert result["ok"] is True
    payload = result["result"]
    assert payload["before"]["zoom"] == 1.5
    assert round(payload["after"]["zoom"], 3) == 3.3
    assert payload["after"]["camera_z"] == 2.4
    assert payload["after"]["yaw"] == 38.0
    assert payload["after"]["pan_x"] == 0.22
    assert payload["after"]["pan_y"] == -0.14
    assert payload["after"]["pan_z"] == 0.05
    assert payload["background_hidden"] is True
    assert preview.fit_count == 1
    assert preview.sync_count == 1
    assert preview._gl_widget.update_count == 1
    assert preview.show_count == 1
    assert preview.raise_count == 1
    assert preview.activate_count == 1
    assert preview.background_visible is False
    assert preview._gl_widget.background_visible is False


def test_ar_pbr_preview_settings_get_returns_scene_settings() -> None:
    from app.actions import build_default_action_registry

    owner = _Owner()
    preview = _PreviewWindow()
    owner._ar_pbr_preview_windows.append(preview)
    registry = build_default_action_registry(owner)

    result = registry.execute("ar_pbr.preview.settings.get").to_dict()

    assert result["ok"] is True
    payload = result["result"]
    assert payload["window"] == "ar_pbr_preview"
    assert payload["settings"]["render_profile"] == "authored"
    assert payload["settings"]["tone_exposure"] == 0.0


def test_ar_pbr_preview_settings_set_applies_scene_settings() -> None:
    from app.actions import build_default_action_registry

    owner = _Owner()
    preview = _PreviewWindow()
    owner._ar_pbr_preview_windows.append(preview)
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "ar_pbr.preview.settings.set",
        {
            "tone_exposure": 0.6,
            "shadow_strength": 0.35,
            "render_profile": "marmoset_pbr",
            "ambient_occlusion_mode": "screen",
            "ao_strength": 0.72,
            "ao_radius": 6.0,
            "ao_distance": 0.8,
            "hybrid_sample_count": 12,
            "diffuse_gi_strength": 0.28,
            "specular_gi_strength": 0.16,
            "denoise_strength": 0.35,
            "surface_override_strength": 0.62,
            "surface_roughness": 0.31,
            "surface_metallic": 0.18,
            "surface_reflectance": 0.44,
            "clearcoat_strength": 0.52,
            "clearcoat_roughness": 0.08,
            "clearcoat_ior": 1.57,
            "parallax": {
                "mode": "pom",
                "enabled": True,
                "strength": 0.58,
                "depth": 0.045,
                "center": 0.5,
                "steps": 32,
            },
            "light_azimuth": None,
        },
    ).to_dict()

    assert result["ok"] is True
    payload = result["result"]
    assert payload["applied"] == [
        "ambient_occlusion_mode",
        "ao_distance",
        "ao_radius",
        "ao_strength",
        "clearcoat_ior",
        "clearcoat_roughness",
        "clearcoat_strength",
        "denoise_strength",
        "diffuse_gi_strength",
        "hybrid_sample_count",
        "parallax",
        "render_profile",
        "shadow_strength",
        "specular_gi_strength",
        "surface_metallic",
        "surface_override_strength",
        "surface_reflectance",
        "surface_roughness",
        "tone_exposure",
    ]
    assert payload["before"]["tone_exposure"] == 0.0
    assert payload["after"]["tone_exposure"] == 0.6
    assert payload["after"]["shadow_strength"] == 0.35
    assert payload["after"]["render_profile"] == "marmoset_pbr"
    assert payload["after"]["ambient_occlusion_mode"] == "screen"
    assert payload["after"]["ao_strength"] == 0.72
    assert payload["after"]["ao_radius"] == 6.0
    assert payload["after"]["ao_distance"] == 0.8
    assert payload["after"]["hybrid_sample_count"] == 12
    assert payload["after"]["diffuse_gi_strength"] == 0.28
    assert payload["after"]["specular_gi_strength"] == 0.16
    assert payload["after"]["denoise_strength"] == 0.35
    assert payload["after"]["surface_override_strength"] == 0.62
    assert payload["after"]["surface_roughness"] == 0.31
    assert payload["after"]["surface_metallic"] == 0.18
    assert payload["after"]["surface_reflectance"] == 0.44
    assert payload["after"]["clearcoat_strength"] == 0.52
    assert payload["after"]["clearcoat_roughness"] == 0.08
    assert payload["after"]["clearcoat_ior"] == 1.57
    assert payload["after"]["parallax"]["mode"] == "pom"
    assert payload["after"]["parallax"]["steps"] == 32
    assert preview.apply_count == 1
    assert preview.last_apply_emit is True
    assert preview.show_count == 1
    assert preview.raise_count == 1
    assert preview.activate_count == 1


def test_ar_pbr_preview_surface_actions_get_and_apply_surface_settings() -> None:
    from app.actions import build_default_action_registry

    owner = _Owner()
    preview = _PreviewWindow()
    owner._ar_pbr_preview_windows.append(preview)
    registry = build_default_action_registry(owner)

    initial = registry.execute("ar_pbr.preview.surface.get").to_dict()

    assert initial["ok"] is True
    assert initial["result"]["surface"]["ibl_exposure"] == 1.1
    assert initial["result"]["surface"]["surface_roughness"] == 0.45
    assert initial["result"]["surface"]["clearcoat_strength"] == 0.0

    result = registry.execute(
        "ar_pbr.preview.surface.set",
        {
            "ibl_exposure": 1.75,
            "ibl_rotation": 0.18,
            "surface_override_strength": 0.7,
            "surface_roughness": 0.24,
            "surface_metallic": 0.33,
            "surface_reflectance": 0.42,
            "clearcoat_strength": 0.58,
            "clearcoat_roughness": 0.07,
            "clearcoat_ior": 1.62,
        },
    ).to_dict()

    assert result["ok"] is True
    payload = result["result"]
    assert payload["applied"] == [
        "clearcoat_ior",
        "clearcoat_roughness",
        "clearcoat_strength",
        "ibl_exposure",
        "ibl_rotation",
        "surface_metallic",
        "surface_override_strength",
        "surface_reflectance",
        "surface_roughness",
    ]
    assert payload["before"]["surface_override_strength"] == 0.0
    assert payload["after"]["ibl_exposure"] == 1.75
    assert payload["after"]["ibl_rotation"] == 0.18
    assert payload["after"]["surface_override_strength"] == 0.7
    assert payload["after"]["surface_roughness"] == 0.24
    assert payload["after"]["surface_metallic"] == 0.33
    assert payload["after"]["surface_reflectance"] == 0.42
    assert payload["after"]["clearcoat_strength"] == 0.58
    assert payload["after"]["clearcoat_roughness"] == 0.07
    assert payload["after"]["clearcoat_ior"] == 1.62
    assert preview.apply_count == 1
    assert preview.last_apply_emit is True
