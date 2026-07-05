from __future__ import annotations

import json
from pathlib import Path


class _FakePixmap:
    def __init__(self, color: tuple[int, int, int]) -> None:
        self.color = color

    def save(self, path: str) -> bool:
        from PIL import Image

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (180, 120), self.color).save(out)
        return True


class _FakeWindow:
    def __init__(self, color: tuple[int, int, int]) -> None:
        self.color = color
        self.visible = False
        self.geometry: tuple[int, int, int, int] | None = None
        self.raised = 0
        self.activated = 0
        self.closed = 0

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def close(self) -> None:
        self.closed += 1
        self.visible = False

    def isVisible(self) -> bool:
        return self.visible

    def raise_(self) -> None:
        self.raised += 1

    def activateWindow(self) -> None:
        self.activated += 1

    def setGeometry(self, x: int, y: int, width: int, height: int) -> None:
        self.geometry = (x, y, width, height)

    def grab(self) -> _FakePixmap:
        return _FakePixmap(self.color)


class _FakeArPbrPreviewState:
    def __init__(self) -> None:
        self.pitch = -10.0
        self.yaw = 72.0
        self.roll = 0.0
        self.zoom = 1.5
        self.camera_z = 3.25
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.pan_z = 0.0


class _FakeArPbrPreviewGL:
    def __init__(self, state: _FakeArPbrPreviewState) -> None:
        self.state = state
        self.auto_fit_enabled = True
        self.auto_fit_pending = True
        self.update_count = 0
        self.background_visible = True

    def fit_current_view(self) -> None:
        self.state.zoom = 2.0

    def set_environment_background_visible(self, visible: bool) -> None:
        self.background_visible = bool(visible)

    def update(self) -> None:
        self.update_count += 1


class _FakeArPbrPreviewWindow(_FakeWindow):
    def __init__(self) -> None:
        super().__init__((180, 185, 190))
        self._state = _FakeArPbrPreviewState()
        self._gl_widget = _FakeArPbrPreviewGL(self._state)
        self.fit_count = 0
        self.sync_count = 0
        self.background_visible = True
        self.apply_count = 0
        self.last_apply_emit = None
        self._settings = {
            "render_profile": "authored",
            "tone_exposure": 0.0,
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

    def fit_view(self) -> None:
        self.fit_count += 1
        self._gl_widget.fit_current_view()

    def sync_controls(self) -> None:
        self.sync_count += 1

    def lighting_settings(self) -> dict:
        return dict(self._settings)

    def apply_lighting_settings(self, settings: dict, *, emit: bool = True) -> None:
        self.apply_count += 1
        self.last_apply_emit = emit
        for key, value in dict(settings or {}).items():
            self._settings[key] = value

    def _set_environment_background_visible(self, visible: bool, *, emit: bool = True) -> None:
        self.background_visible = bool(visible)
        self._gl_widget.set_environment_background_visible(visible)


class _FakeOwner(_FakeWindow):
    def __init__(self) -> None:
        super().__init__((72, 88, 120))
        self._preview_popout = None
        self._media_pool_popout = None
        self._workbench_popout = None
        self._color_popout = None
        self._ar_pbr_preview_windows = []
        self._ar_pbr_tracks = []
        self._selected_ar_pbr_track_id = ""
        self.preview_toggle_count = 0
        self.opened_ar_asset = ""
        self.opened_ar_track = ""

    def _toggle_preview_popout(self) -> None:
        self.preview_toggle_count += 1
        if self._preview_popout is None:
            self._preview_popout = _FakeWindow((220, 40, 32))
        else:
            self._preview_popout.close()
            self._preview_popout = None

    def _toggle_media_pool_popout(self) -> None:
        self._media_pool_popout = _FakeWindow((40, 170, 120))

    def _toggle_workbench_popout(self) -> None:
        self._workbench_popout = _FakeWindow((70, 95, 230))

    def _toggle_color_popout(self) -> None:
        self._color_popout = _FakeWindow((230, 180, 45))

    def _open_ar_pbr_asset_preview(self, path: str) -> None:
        self.opened_ar_asset = path
        window = _FakeArPbrPreviewWindow()
        self._ar_pbr_preview_windows.append(window)

    def _open_ar_pbr_track_model_view(self, track: dict) -> None:
        self.opened_ar_track = str(track.get("id") or "")
        window = _FakeArPbrPreviewWindow()
        self._ar_pbr_preview_windows.append(window)


def _write_template(root: Path) -> tuple[Path, Path]:
    from PIL import Image

    template = root / "template.png"
    screen_map = root / "template.screen-map.json"
    Image.new("RGB", (320, 160), (18, 18, 18)).save(template)
    payload = {
        "screen_regions": [
            {"id": "left_monitor", "rect": {"x": 10, "y": 20, "width": 80, "height": 60}, "fit": "cover"},
            {"id": "center_monitor", "rect": {"x": 120, "y": 20, "width": 80, "height": 60}, "fit": "cover"},
            {"id": "right_monitor", "rect": {"x": 230, "y": 20, "width": 80, "height": 60}, "fit": "cover"},
        ]
    }
    screen_map.write_text(json.dumps(payload), encoding="utf-8")
    return template, screen_map


def test_review_window_actions_are_not_registered_in_main_action_catalog():
    from app.actions import build_default_action_registry

    registry = build_default_action_registry(None)
    action_ids = {row["id"] for row in registry.list_actions()}

    assert "review.ui.popout.open" not in action_ids
    assert "review.capture.window" not in action_ids
    assert "review.multi_monitor.capture_slots" not in action_ids


def test_review_window_runner_shows_popout_before_capture(tmp_path):
    from app.review_automation.window_actions import ReviewWindowActionRunner

    owner = _FakeOwner()
    runner = ReviewWindowActionRunner(owner, root=tmp_path, output_dir=tmp_path / "out")

    opened = runner.execute("review.ui.popout.open", {"surface": "viewer"})
    assert opened["ok"] is True
    assert owner.preview_toggle_count == 1
    assert owner._preview_popout is not None
    assert owner._preview_popout.isVisible() is True

    geometry = runner.execute(
        "review.ui.window.set_geometry",
        {"target": "viewer", "x": 11, "y": 22, "width": 333, "height": 222},
    )
    assert geometry["ok"] is True
    assert owner._preview_popout.geometry == (11, 22, 333, 222)

    owner._preview_popout.hide()
    capture_path = tmp_path / "viewer.png"
    captured = runner.execute(
        "review.capture.window",
        {"target": "viewer", "path": str(capture_path), "settle_ms": 0},
    )
    assert captured["ok"] is True
    assert capture_path.exists()
    assert owner._preview_popout.isVisible() is True
    assert owner._preview_popout.raised >= 1
    assert owner._preview_popout.activated >= 1


def test_review_window_runner_opens_ar_pbr_asset_preview_before_capture(tmp_path):
    from app.review_automation.window_actions import ReviewWindowActionRunner

    owner = _FakeOwner()
    runner = ReviewWindowActionRunner(owner, root=tmp_path, output_dir=tmp_path / "out")

    opened = runner.execute(
        "review.ui.window.open",
        {"surface": "ar_pbr_preview", "asset_path": "E:/assets/Camera_01_1k.gltf"},
    )
    assert opened["ok"] is True
    assert opened["review_only"] is True
    assert owner.opened_ar_asset == "E:/assets/Camera_01_1k.gltf"
    assert owner._ar_pbr_preview_windows[-1].isVisible() is True

    capture_path = tmp_path / "ar_pbr_preview.png"
    captured = runner.execute(
        "review.capture.window",
        {"target": "ar_pbr_preview", "path": str(capture_path), "settle_ms": 0},
    )
    assert captured["ok"] is True
    assert capture_path.exists()


def test_review_window_runner_reframes_ar_pbr_preview_for_capture(tmp_path):
    from app.review_automation.window_actions import ReviewWindowActionRunner

    owner = _FakeOwner()
    runner = ReviewWindowActionRunner(owner, root=tmp_path, output_dir=tmp_path / "out")
    runner.execute(
        "review.ui.window.open",
        {"surface": "ar_pbr_preview", "asset_path": "E:/assets/Camera_01_1k.gltf"},
    )
    preview = owner._ar_pbr_preview_windows[-1]

    result = runner.execute(
        "review.ar_pbr.preview.view.set",
        {
            "fit_first": True,
            "zoom_factor": 1.7,
            "camera_z": 2.4,
            "yaw": 35.0,
            "pan_x": 0.18,
            "pan_y": -0.12,
            "pan_z": 0.03,
            "hide_environment_background": True,
        },
    )

    assert result["ok"] is True
    payload = result["result"]
    assert payload["before"]["zoom"] == 1.5
    assert round(payload["after"]["zoom"], 3) == 3.4
    assert payload["after"]["camera_z"] == 2.4
    assert payload["after"]["yaw"] == 35.0
    assert payload["after"]["pan_x"] == 0.18
    assert payload["after"]["pan_y"] == -0.12
    assert payload["after"]["pan_z"] == 0.03
    assert payload["background_hidden"] is True
    assert preview.fit_count == 1
    assert preview.sync_count == 1
    assert preview._gl_widget.update_count == 1
    assert preview._gl_widget.auto_fit_enabled is False
    assert preview._gl_widget.auto_fit_pending is False
    assert preview.background_visible is False


def test_review_window_runner_reads_ar_pbr_preview_view_for_presets(tmp_path):
    from app.review_automation.window_actions import ReviewWindowActionRunner

    owner = _FakeOwner()
    runner = ReviewWindowActionRunner(owner, root=tmp_path, output_dir=tmp_path / "out")
    runner.execute(
        "review.ui.window.open",
        {"surface": "ar_pbr_preview", "asset_path": "E:/assets/Camera_01_1k.gltf"},
    )
    preview = owner._ar_pbr_preview_windows[-1]
    preview._state.pitch = 12.0
    preview._state.yaw = 44.0
    preview._state.roll = -2.0
    preview._state.zoom = 2.9
    preview._state.camera_z = 2.1
    preview._state.pan_x = 0.24
    preview._state.pan_y = -0.16
    preview._state.pan_z = 0.02

    result = runner.execute("review.ar_pbr.preview.view.get")

    assert result["ok"] is True
    assert result["result"]["view"] == {
        "pitch": 12.0,
        "yaw": 44.0,
        "roll": -2.0,
        "zoom": 2.9,
        "camera_z": 2.1,
        "pan_x": 0.24,
        "pan_y": -0.16,
        "pan_z": 0.02,
    }


def test_review_window_runner_applies_ar_pbr_preview_settings(tmp_path):
    from app.review_automation.window_actions import ReviewWindowActionRunner

    owner = _FakeOwner()
    runner = ReviewWindowActionRunner(owner, root=tmp_path, output_dir=tmp_path / "out")
    runner.execute(
        "review.ui.window.open",
        {"surface": "ar_pbr_preview", "asset_path": "E:/assets/Camera_01_1k.gltf"},
    )
    preview = owner._ar_pbr_preview_windows[-1]

    result = runner.execute(
        "review.ar_pbr.preview.settings.set",
        {
            "tone_exposure": 0.5,
            "shadow_strength": 0.3,
            "render_profile": "marmoset_pbr",
            "ambient_occlusion_mode": "screen",
            "ao_strength": 0.65,
            "ao_radius": 5.5,
            "ao_distance": 0.9,
            "hybrid_sample_count": 10,
            "diffuse_gi_strength": 0.24,
            "specular_gi_strength": 0.12,
            "denoise_strength": 0.3,
            "surface_override_strength": 0.66,
            "surface_roughness": 0.29,
            "surface_metallic": 0.21,
            "surface_reflectance": 0.41,
            "clearcoat_strength": 0.47,
            "clearcoat_roughness": 0.09,
            "clearcoat_ior": 1.58,
            "light_azimuth": None,
        },
    )

    assert result["ok"] is True
    payload = result["result"]
    assert payload["surface"] == "ar_pbr_preview"
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
    assert payload["after"]["tone_exposure"] == 0.5
    assert payload["after"]["surface_override_strength"] == 0.66
    assert payload["after"]["surface_roughness"] == 0.29
    assert payload["after"]["surface_metallic"] == 0.21
    assert payload["after"]["surface_reflectance"] == 0.41
    assert payload["after"]["clearcoat_strength"] == 0.47
    assert payload["after"]["clearcoat_roughness"] == 0.09
    assert payload["after"]["clearcoat_ior"] == 1.58
    assert payload["after"]["render_profile"] == "marmoset_pbr"
    assert payload["after"]["ambient_occlusion_mode"] == "screen"
    assert payload["after"]["ao_strength"] == 0.65
    assert payload["after"]["ao_radius"] == 5.5
    assert payload["after"]["ao_distance"] == 0.9
    assert payload["after"]["hybrid_sample_count"] == 10
    assert payload["after"]["diffuse_gi_strength"] == 0.24
    assert payload["after"]["specular_gi_strength"] == 0.12
    assert payload["after"]["denoise_strength"] == 0.3
    assert preview.apply_count == 1
    assert preview.last_apply_emit is True
    assert preview.visible is True


def test_review_window_runner_opens_selected_ar_pbr_track_preview(tmp_path):
    from app.review_automation.window_actions import ReviewWindowActionRunner

    owner = _FakeOwner()
    owner._ar_pbr_tracks = [{"id": "ar_pbr_001", "asset_path": "Camera_01_1k.gltf"}]
    owner._selected_ar_pbr_track_id = "ar_pbr_001"
    runner = ReviewWindowActionRunner(owner, root=tmp_path, output_dir=tmp_path / "out")

    opened = runner.execute("review.ui.window.open", {"surface": "ar_pbr_preview"})
    assert opened["ok"] is True
    assert owner.opened_ar_track == "ar_pbr_001"
    assert opened["result"]["track_id"] == "ar_pbr_001"


def test_multi_monitor_compose_maps_real_slot_images(tmp_path):
    from PIL import Image

    from app.review_automation.window_actions import compose_multi_monitor_template

    template, screen_map = _write_template(tmp_path)
    slots = {}
    for name, color in {
        "left_monitor": (255, 0, 0),
        "center_monitor": (0, 255, 0),
        "right_monitor": (0, 0, 255),
    }.items():
        path = tmp_path / f"{name}.png"
        Image.new("RGB", (64, 64), color).save(path)
        slots[name] = path

    out = tmp_path / "multi.png"
    result = compose_multi_monitor_template(
        template_path=template,
        screen_map_path=screen_map,
        slot_images=slots,
        out_path=out,
    )

    assert result["missing"] == []
    assert len(result["pasted"]) == 3
    image = Image.open(out).convert("RGB")
    assert image.getpixel((20, 30)) == (255, 0, 0)
    assert image.getpixel((130, 30)) == (0, 255, 0)
    assert image.getpixel((240, 30)) == (0, 0, 255)


def test_multi_monitor_compose_supports_perspective_quad_regions(tmp_path):
    from PIL import Image

    from app.review_automation.window_actions import compose_multi_monitor_template

    template = tmp_path / "template.png"
    screen_map = tmp_path / "template.screen-map.json"
    slot = tmp_path / "left_monitor.png"
    out = tmp_path / "multi_quad.png"

    Image.new("RGB", (120, 100), (18, 18, 18)).save(template)
    Image.new("RGB", (80, 60), (255, 0, 0)).save(slot)
    screen_map.write_text(
        json.dumps(
            {
                "screen_regions": [
                    {
                        "id": "left_monitor",
                        "rect": {"x": 10, "y": 10, "width": 80, "height": 70},
                        "quad": [
                            {"x": 10, "y": 10},
                            {"x": 90, "y": 20},
                            {"x": 80, "y": 80},
                            {"x": 20, "y": 70},
                        ],
                        "fit": "cover",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = compose_multi_monitor_template(
        template_path=template,
        screen_map_path=screen_map,
        slot_images={"left_monitor": slot},
        out_path=out,
    )

    assert result["missing"] == []
    assert result["pasted"][0]["mapping"] == "perspective_quad"
    image = Image.open(out).convert("RGB")
    assert image.getpixel((50, 45)) == (255, 0, 0)
    assert image.getpixel((12, 78)) == (18, 18, 18)


def test_multi_monitor_compose_honors_contain_fit(tmp_path):
    from PIL import Image

    from app.review_automation.window_actions import compose_multi_monitor_template

    template = tmp_path / "template.png"
    screen_map = tmp_path / "template.screen-map.json"
    slot = tmp_path / "wide_slot.png"
    out = tmp_path / "multi_contain.png"

    Image.new("RGB", (120, 100), (18, 18, 18)).save(template)
    Image.new("RGB", (120, 20), (255, 0, 0)).save(slot)
    screen_map.write_text(
        json.dumps(
            {
                "screen_regions": [
                    {
                        "id": "center_monitor",
                        "rect": {"x": 20, "y": 20, "width": 60, "height": 60},
                        "fit": "contain",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = compose_multi_monitor_template(
        template_path=template,
        screen_map_path=screen_map,
        slot_images={"center_monitor": slot},
        out_path=out,
    )

    assert result["pasted"][0]["fit"] == "contain"
    image = Image.open(out).convert("RGB")
    assert image.getpixel((50, 50)) == (255, 0, 0)
    assert image.getpixel((50, 24)) == (8, 10, 13)


def test_capture_slots_prepares_windows_and_composes_template(tmp_path):
    from PIL import Image

    from app.review_automation.window_actions import ReviewWindowActionRunner

    owner = _FakeOwner()
    template, screen_map = _write_template(tmp_path)
    runner = ReviewWindowActionRunner(owner, root=tmp_path, output_dir=tmp_path / "out")

    result = runner.execute(
        "review.multi_monitor.capture_slots",
        {
            "template_path": str(template),
            "screen_map_path": str(screen_map),
            "out_path": str(tmp_path / "final.png"),
            "slots": {
                "left_monitor": {
                    "windows": [{"target": "media_pool", "popout": True, "x": 0, "y": 0, "width": 300, "height": 200}],
                    "target": "media_pool",
                },
                "center_monitor": {"target": "editor"},
                "right_monitor": {
                    "windows": [{"target": "workbench", "popout": True, "x": 300, "y": 0, "width": 300, "height": 200}],
                    "target": "workbench",
                },
            },
            "strict": True,
        },
    )

    assert result["ok"] is True
    assert Path(result["result"]["compose"]["path"]).exists()
    assert owner._media_pool_popout is not None
    assert owner._media_pool_popout.geometry == (0, 0, 300, 200)
    assert owner._workbench_popout is not None
    assert owner._workbench_popout.geometry == (300, 0, 300, 200)
    image = Image.open(result["result"]["compose"]["path"]).convert("RGB")
    assert image.getpixel((20, 30)) == (40, 170, 120)
    assert image.getpixel((130, 30)) == (72, 88, 120)
    assert image.getpixel((240, 30)) == (70, 95, 230)


def test_live_review_scenario_routes_multi_monitor_capture_to_review_only_runner(tmp_path):
    from app.review_automation.live_runner import run_live_review_scenario

    owner = _FakeOwner()
    template, screen_map = _write_template(tmp_path)
    out_dir = tmp_path / "multi"
    result = run_live_review_scenario(
        owner,
        "multi-monitor-capture",
        {
            "project_root": str(tmp_path),
            "out_dir": str(out_dir),
            "template_path": str(template),
            "screen_map_path": str(screen_map),
            "slots": {
                "left_monitor": {
                    "windows": [{"target": "media_pool", "popout": True, "x": 0, "y": 0, "width": 300, "height": 200}],
                    "target": "media_pool",
                },
                "center_monitor": {"target": "editor"},
                "right_monitor": {
                    "windows": [{"target": "workbench", "popout": True, "x": 300, "y": 0, "width": 300, "height": 200}],
                    "target": "workbench",
                },
            },
        },
    )

    assert result["ok"] is True
    assert result["review_only"] is True
    assert result["scenario"] == "multi-monitor-capture"
    assert Path(result["output_path"]).exists()
    assert Path(result["report_path"]).exists()
