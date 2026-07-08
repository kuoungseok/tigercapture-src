"""App-facing AR/PBR asset preview window.

This window intentionally keeps the UI product-facing: a realtime model view
with environment lighting and only light/shadow controls. Import diagnostics
remain internal and are not shown as JSON in the UI.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.studio_slider import StudioSlider
from app.ar_pbr.ambient_occlusion import (
    DEFAULT_AMBIENT_OCCLUSION_MODE,
    DEFAULT_AO_ACTIVE_STRENGTH,
    DEFAULT_AO_DISTANCE,
    DEFAULT_AO_RADIUS,
    DEFAULT_AO_STRENGTH,
)
from app.ar_pbr.catcher import (
    DEFAULT_CONTACT_REFLECTION_FALLOFF,
    DEFAULT_CONTACT_REFLECTION_STRENGTH,
    DEFAULT_REFLECTION_CATCHER_OPACITY,
    DEFAULT_REFLECTION_CATCHER_ROUGHNESS,
    DEFAULT_REFLECTION_CATCHER_SOFTNESS,
    DEFAULT_SHADOW_CATCHER_MATTE_ALPHA,
    DEFAULT_SHADOW_CATCHER_OPACITY,
    DEFAULT_SHADOW_CATCHER_SOFTNESS,
)
from app.ar_pbr.clearcoat import (
    DEFAULT_CLEARCOAT_IOR,
    DEFAULT_CLEARCOAT_ROUGHNESS,
    DEFAULT_CLEARCOAT_STRENGTH,
    normalize_clearcoat_settings,
)
from app.ar_pbr.depth_occlusion import (
    DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX,
    DEFAULT_DEPTH_EDGE_GLOW_STRENGTH,
)
from app.ar_pbr.hdri_presets import HdriPreset, hdri_presets, resolve_hdri_preset
from app.ar_pbr.hybrid_rendering import (
    DEFAULT_DENOISE_STRENGTH,
    DEFAULT_DIFFUSE_GI_STRENGTH,
    DEFAULT_HYBRID_SAMPLE_COUNT,
    DEFAULT_SPECULAR_GI_STRENGTH,
)
from app.ar_pbr.asset_support import asset_support_status_text
from app.ar_pbr.render_profile import (
    PROFILE_AUTHORED,
    PROFILE_MARMOSET_PBR,
    PROFILE_VRM_MTOON,
    inspect_asset_render_profiles_from_descriptor,
    marmoset_pbr_available,
    vrm_mtoon_available,
)
from app.ar_pbr.shadow import DEFAULT_SHADOW_STRENGTH
from app.ar_pbr.surface import (
    DEFAULT_SURFACE_METALLIC,
    DEFAULT_SURFACE_OVERRIDE_STRENGTH,
    DEFAULT_SURFACE_REFLECTANCE,
    DEFAULT_SURFACE_ROUGHNESS,
    normalize_surface_settings,
)
from app.style import studio_chrome_qss


def _support_status_text(report: dict[str, Any] | None) -> str:
    text = asset_support_status_text(report)
    return "Realtime preview" if text == "Support check pending" else text


def _render_profile_combo_rows(render_profiles: dict[str, Any] | None) -> list[dict[str, Any]]:
    profiles = render_profiles if isinstance(render_profiles, dict) else {}
    rows = []
    if vrm_mtoon_available(profiles):
        rows.append({
            "id": PROFILE_VRM_MTOON,
            "label": "VRM MToon",
            "enabled": True,
        })
    rows.append({
        "id": PROFILE_AUTHORED,
        "label": "Authored material",
        "enabled": True,
    })
    if marmoset_pbr_available(profiles):
        rows.append({
            "id": PROFILE_MARMOSET_PBR,
            "label": "Marmoset-style PBR",
            "enabled": True,
        })
    return rows


class _ArPbrPreviewLoader(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        asset_path: Path,
        *,
        hdri_path: Path | None = None,
        max_triangles: int = 120_000,
        texture_max_size: int = 1024,
        render_profile: str = PROFILE_AUTHORED,
    ) -> None:
        super().__init__()
        self.asset_path = asset_path
        self.hdri_path = hdri_path
        self.max_triangles = int(max_triangles)
        self.texture_max_size = int(texture_max_size)
        self.render_profile = str(render_profile or PROFILE_AUTHORED)

    def run(self) -> None:
        timer = None
        try:
            from app.ar_pbr.importer import import_asset
            from app.ar_pbr.texture_plan import resolve_material_texture_plan
            from app.loading_performance import LoadingTimer
            from tools.ar_pbr_gpu_window import (
                _load_hdri_or_none,
                build_vertex_buffer,
            )

            timer = LoadingTimer("ar_pbr.preview", self.asset_path)
            timer.mark("queued", detail="3D preview loader started")
            descriptor, import_diag = import_asset(
                self.asset_path,
                settings={"max_triangles_per_geometry": max(100, self.max_triangles)},
            )
            timer.mark(
                "import",
                detail="asset descriptor ready",
                metadata={
                    "backend": import_diag.get("backend"),
                    "cached": bool(import_diag.get("cached")),
                },
            )
            vertices, mesh_diag = build_vertex_buffer(
                descriptor,
                track={"render": {"render_profile": self.render_profile}},
            )
            timer.mark(
                "vertex_buffer",
                detail="GPU vertex buffer source ready",
                metadata={
                    "vertex_count": int(len(vertices) // 13) if hasattr(vertices, "__len__") else 0,
                    "triangle_count": int(mesh_diag.get("triangle_count", 0) or 0),
                },
            )
            hdri, hdri_diag = _load_hdri_or_none(self.hdri_path)
            timer.mark(
                "hdri",
                detail="HDR environment ready",
                metadata={"enabled": bool(hdri_diag.get("enabled"))},
            )
            texture_plan, texture_diag = resolve_material_texture_plan(self.asset_path, descriptor)
            texture_diag["upload_max_size"] = self.texture_max_size
            timer.mark(
                "textures",
                detail="material texture plan ready",
                metadata={"material_count": len(texture_plan or {})},
            )
            self.loaded.emit({
                "descriptor": descriptor,
                "import_diag": import_diag,
                "vertices": vertices,
                "mesh_diag": mesh_diag,
                "hdri": hdri,
                "hdri_diag": hdri_diag,
                "texture_plan": texture_plan,
                "texture_diag": texture_diag,
                "load_trace": timer.mark("ready", detail="3D preview payload ready"),
            })
        except Exception as exc:
            if timer is not None:
                timer.mark("error", status="error", detail=f"{type(exc).__name__}: {exc}")
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _SliderRow(QWidget):
    value_changed = Signal(float)

    def __init__(
        self,
        label: str,
        minimum: float,
        maximum: float,
        value: float,
        *,
        steps: int = 1000,
        suffix: str = "",
        parent: QWidget | None = None,
        kind: str = "neutral",
    ) -> None:
        super().__init__(parent)
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.suffix = suffix
        self._block_emit = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(label, self)
        self._label.setObjectName("ArPbrControlLabel")
        self._value = QLabel("", self)
        self._value.setObjectName("ArPbrControlValue")
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self._label)
        top.addStretch(1)
        top.addWidget(self._value)
        layout.addLayout(top)

        self.slider = StudioSlider(kind, self)
        self.slider.setRange(0, max(1, int(steps)))
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)
        self.set_value(value, emit=False)

    def set_value(self, value: float, *, emit: bool = False) -> None:
        value = max(self.minimum, min(self.maximum, float(value)))
        ratio = (value - self.minimum) / max(self.maximum - self.minimum, 1e-8)
        self._block_emit = not emit
        self.slider.setValue(int(round(ratio * self.slider.maximum())))
        self._block_emit = False
        self._set_value_label(value)
        if emit:
            self.value_changed.emit(value)

    def value(self) -> float:
        ratio = self.slider.value() / max(float(self.slider.maximum()), 1.0)
        return self.minimum + (self.maximum - self.minimum) * ratio

    def _set_value_label(self, value: float) -> None:
        if self.suffix == "deg":
            text = f"{value:.0f} deg"
        elif self.suffix == "K":
            text = f"{value:.0f} K"
        elif self.suffix == "px":
            text = f"{value:.1f} px"
        elif self.suffix == "samples":
            text = f"{int(round(value))}"
        else:
            text = f"{value:.2f}"
        self._value.setText(text)

    def _on_slider_changed(self, _raw: int) -> None:
        value = self.value()
        self._set_value_label(value)
        if not self._block_emit:
            self.value_changed.emit(value)


class _ComboRow(QWidget):
    value_changed = Signal(str)

    def __init__(
        self,
        label: str,
        rows: list[tuple[str, str]],
        *,
        value: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self._label = QLabel(label, self)
        self._label.setObjectName("ArPbrControlLabel")
        layout.addWidget(self._label)

        self.combo = QComboBox(self)
        self.combo.setObjectName("ArPbrHdriCombo")
        for title, data in rows:
            self.combo.addItem(title, data)
        self.combo.currentIndexChanged.connect(self._on_index_changed)
        layout.addWidget(self.combo)
        self.set_value(value, emit=False)

    def value(self) -> str:
        return str(self.combo.currentData() or "")

    def set_value(self, value: str, *, emit: bool = False) -> None:
        wanted = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
        index = 0
        for row in range(self.combo.count()):
            if str(self.combo.itemData(row) or "") == wanted:
                index = row
                break
        was_blocked = self.combo.blockSignals(not emit)
        try:
            self.combo.setCurrentIndex(index)
        finally:
            self.combo.blockSignals(was_blocked)
        if emit:
            self.value_changed.emit(self.value())

    def _on_index_changed(self, _index: int) -> None:
        self.value_changed.emit(self.value())


class ArPbrAssetPreviewWindow(QMainWindow):
    """Realtime preview for FBX/GLB media-pool assets."""

    settings_changed = Signal(object)

    def __init__(
        self,
        asset_path: str | Path,
        parent: QWidget | None = None,
        *,
        initial_lighting: dict[str, Any] | None = None,
        track_label: str = "",
        max_triangles: int = 120_000,
        texture_max_size: int = 1024,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.asset_path = Path(asset_path).expanduser().resolve()
        self._loader: _ArPbrPreviewLoader | None = None
        self._gl_widget = None
        self._state = None
        self._mesh_diag: dict[str, Any] = {}
        self._asset_support: dict[str, Any] = {}
        self._descriptor: dict[str, Any] = {}
        self._render_profiles: dict[str, Any] = {}
        self._initial_lighting = dict(initial_lighting or {})
        self._render_profile = str(self._initial_lighting.get("render_profile") or PROFILE_AUTHORED).strip().casefold()
        if self._render_profile not in {PROFILE_AUTHORED, PROFILE_MARMOSET_PBR, PROFILE_VRM_MTOON}:
            self._render_profile = PROFILE_AUTHORED
        self._hdri_presets: list[HdriPreset] = hdri_presets()
        initial_hdri_key = str(self._initial_lighting.get("hdri_id") or self._initial_lighting.get("hdri_path") or "")
        self._selected_hdri = resolve_hdri_preset(initial_hdri_key)
        self._background_visible = bool(self._initial_lighting.get("show_environment_background", True))
        self._preview_max_triangles = max(1_000, int(max_triangles))
        self._preview_texture_max_size = max(64, int(texture_max_size))
        self._suppress_emit = False

        suffix = f" - {track_label}" if track_label else ""
        self.setWindowTitle(f"3D Preview - {self.asset_path.name}{suffix}")
        self.resize(1280, 860)
        self.setStyleSheet(studio_chrome_qss(_AR_PBR_PREVIEW_QSS))

        root = QWidget(self)
        root.setObjectName("ArPbrPreviewRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        title_icon = QLabel(self)
        title_icon.setPixmap(app_icon("layers", size=20, color="#F8F4EA").pixmap(icon_size(20)))
        header.addWidget(title_icon)
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        self._title = QLabel(self.asset_path.name, self)
        self._title.setObjectName("ArPbrPreviewTitle")
        self._subtitle = QLabel(str(self.asset_path.parent), self)
        self._subtitle.setObjectName("ArPbrPreviewSubtitle")
        title_col.addWidget(self._title)
        title_col.addWidget(self._subtitle)
        header.addLayout(title_col, stretch=1)
        self._status = QLabel("Loading 3D asset", self)
        self._status.setObjectName("ArPbrPreviewStatus")
        header.addWidget(self._status)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(0)
        self._viewport_host = QFrame(self)
        self._viewport_host.setObjectName("ArPbrViewportHost")
        self._viewport_layout = QVBoxLayout(self._viewport_host)
        self._viewport_layout.setContentsMargins(0, 0, 0, 0)
        self._viewport_layout.setSpacing(0)

        self._loading_panel = QWidget(self._viewport_host)
        self._loading_panel.setObjectName("ArPbrLoadingPanel")
        loading_layout = QVBoxLayout(self._loading_panel)
        loading_layout.setContentsMargins(28, 28, 28, 28)
        loading_layout.addStretch(1)
        loading_title = QLabel("Preparing realtime PBR preview", self._loading_panel)
        loading_title.setObjectName("ArPbrLoadingTitle")
        loading_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(loading_title)
        loading_body = QLabel("Importing mesh, textures, and environment lighting", self._loading_panel)
        loading_body.setObjectName("ArPbrLoadingBody")
        loading_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(loading_body)
        self._progress = QProgressBar(self._loading_panel)
        self._progress.setRange(0, 0)
        loading_layout.addWidget(self._progress)
        loading_layout.addStretch(1)
        self._viewport_layout.addWidget(self._loading_panel)
        body.addWidget(self._viewport_host, stretch=1)

        controls = QFrame(self)
        controls.setObjectName("ArPbrControls")
        controls.setMinimumWidth(330)
        controls.setMaximumWidth(390)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(12, 10, 12, 10)
        controls_layout.setSpacing(8)

        top_controls = QHBoxLayout()
        top_controls.setContentsMargins(0, 0, 0, 0)
        top_controls.setSpacing(8)
        controls_title = QLabel("Scene Lighting", controls)
        controls_title.setObjectName("ArPbrControlsTitle")
        top_controls.addWidget(controls_title)
        top_controls.addStretch(1)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        top_controls.addLayout(button_row)
        controls_layout.addLayout(top_controls)

        combo_row = QHBoxLayout()
        combo_row.setContentsMargins(0, 0, 0, 0)
        combo_row.setSpacing(8)

        self._render_profile_combo = QComboBox(controls)
        self._render_profile_combo.setObjectName("ArPbrHdriCombo")
        self._render_profile_combo.setEnabled(False)
        self._render_profile_combo.setToolTip("Render profile")
        combo_row.addWidget(self._render_profile_combo, stretch=1)

        self._hdri_combo = QComboBox(controls)
        self._hdri_combo.setObjectName("ArPbrHdriCombo")
        self._populate_hdri_combo()
        self._hdri_combo.setEnabled(False)
        self._hdri_combo.setToolTip("HDR cubemap preset")
        combo_row.addWidget(self._hdri_combo, stretch=1)
        controls_layout.addLayout(combo_row)

        self._ibl_exposure = _SliderRow("Environment Intensity", 0.0, 4.0, 1.1, parent=controls, kind="accent")
        self._ibl_rotation = _SliderRow("Environment Rotation", -180.0, 180.0, 0.0, suffix="deg", parent=controls, kind="accent")
        self._light_azimuth = _SliderRow("Key Light Azimuth", -180.0, 180.0, 45.0, suffix="deg", parent=controls, kind="accent")
        self._light_elevation = _SliderRow("Key Light Elevation", -20.0, 89.0, 45.0, suffix="deg", parent=controls, kind="accent")
        self._direct_strength = _SliderRow("Direct Strength", 0.0, 2.0, 0.42, parent=controls, kind="accent")
        self._shadow_strength = _SliderRow("Shadow Strength", 0.0, 1.0, DEFAULT_SHADOW_STRENGTH, parent=controls)
        self._shadow_pcf_radius = _SliderRow("PCF Softness", 0.0, 4.0, 1.35, parent=controls)
        self._self_shadow_strength = _SliderRow("Self Shadow", 0.0, 1.0, 0.45, parent=controls)
        self._ground_height = _SliderRow("Shadow Plane Height", -1.2, 0.4, -0.52, parent=controls)
        self._shadow_catcher_opacity = _SliderRow("Shadow Catcher", 0.0, 1.0, DEFAULT_SHADOW_CATCHER_OPACITY, parent=controls)
        self._shadow_catcher_softness = _SliderRow("Shadow Edge", 0.0, 1.0, DEFAULT_SHADOW_CATCHER_SOFTNESS, parent=controls)
        self._reflection_catcher_opacity = _SliderRow("Reflection", 0.0, 1.0, DEFAULT_REFLECTION_CATCHER_OPACITY, parent=controls, kind="accent")
        self._reflection_catcher_roughness = _SliderRow("Reflection Roughness", 0.02, 1.0, DEFAULT_REFLECTION_CATCHER_ROUGHNESS, parent=controls)
        self._reflection_catcher_softness = _SliderRow("Reflection Edge", 0.0, 1.0, DEFAULT_REFLECTION_CATCHER_SOFTNESS, parent=controls)
        self._contact_reflection_strength = _SliderRow("Contact Reflection", 0.0, 1.0, DEFAULT_CONTACT_REFLECTION_STRENGTH, parent=controls, kind="accent")
        self._contact_reflection_falloff = _SliderRow("Contact Falloff", 0.05, 1.0, DEFAULT_CONTACT_REFLECTION_FALLOFF, parent=controls)
        self._surface_override_strength = _SliderRow("Surface Mix", 0.0, 1.0, DEFAULT_SURFACE_OVERRIDE_STRENGTH, parent=controls, kind="accent")
        self._surface_roughness = _SliderRow("Roughness", 0.04, 1.0, DEFAULT_SURFACE_ROUGHNESS, parent=controls)
        self._surface_metallic = _SliderRow("Metallic", 0.0, 1.0, DEFAULT_SURFACE_METALLIC, parent=controls)
        self._surface_reflectance = _SliderRow("Reflectance", 0.0, 1.0, DEFAULT_SURFACE_REFLECTANCE, parent=controls)
        self._clearcoat_strength = _SliderRow("Clearcoat", 0.0, 1.0, DEFAULT_CLEARCOAT_STRENGTH, parent=controls, kind="accent")
        self._clearcoat_roughness = _SliderRow("Coat Roughness", 0.02, 1.0, DEFAULT_CLEARCOAT_ROUGHNESS, parent=controls)
        self._clearcoat_ior = _SliderRow("Coat IOR", 1.0, 2.5, DEFAULT_CLEARCOAT_IOR, parent=controls)
        self._tone_exposure = _SliderRow("Exposure", -4.0, 4.0, 0.0, parent=controls, kind="accent")
        self._tone_white_balance = _SliderRow("White Balance", 1000.0, 12000.0, 6500.0, suffix="K", parent=controls, kind="temperature")
        self._tone_gamma = _SliderRow("Gamma", 0.5, 3.0, 2.2, parent=controls)
        self._depth_edge_glow_strength = _SliderRow("Depth Edge Glow", 0.0, 1.0, DEFAULT_DEPTH_EDGE_GLOW_STRENGTH, parent=controls, kind="accent")
        self._depth_edge_glow_radius = _SliderRow("Glow Width", 0.5, 18.0, DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX, suffix="px", parent=controls)
        self._ao_mode = _ComboRow(
            "Ambient Occlusion",
            [
                ("Off", "off"),
                ("Screen AO", "screen"),
                ("Export Detail", "ray_traced"),
            ],
            value=DEFAULT_AMBIENT_OCCLUSION_MODE,
            parent=controls,
        )
        self._ao_mode.setToolTip("Preview/export AO mode. Export Detail is a packet/export policy, not realtime ray tracing.")
        self._ao_strength = _SliderRow("AO Strength", 0.0, 2.0, DEFAULT_AO_STRENGTH, parent=controls, kind="accent")
        self._ao_radius = _SliderRow("AO Radius", 0.5, 32.0, DEFAULT_AO_RADIUS, parent=controls)
        self._ao_distance = _SliderRow("AO Distance", 0.01, 4.0, DEFAULT_AO_DISTANCE, parent=controls)
        self._hybrid_sample_count = _SliderRow(
            "Hybrid Samples",
            1.0,
            64.0,
            DEFAULT_HYBRID_SAMPLE_COUNT,
            steps=63,
            suffix="samples",
            parent=controls,
            kind="accent",
        )
        self._hybrid_sample_count.setToolTip("Hybrid GI sample count for preview/export detail.")
        self._diffuse_gi_strength = _SliderRow("Diffuse GI", 0.0, 2.0, DEFAULT_DIFFUSE_GI_STRENGTH, parent=controls, kind="accent")
        self._specular_gi_strength = _SliderRow("Specular GI", 0.0, 2.0, DEFAULT_SPECULAR_GI_STRENGTH, parent=controls, kind="accent")
        self._denoise_strength = _SliderRow("Denoise", 0.0, 1.0, DEFAULT_DENOISE_STRENGTH, parent=controls)
        self._parameter_rows = (
            self._ibl_exposure,
            self._ibl_rotation,
            self._light_azimuth,
            self._light_elevation,
            self._direct_strength,
            self._shadow_strength,
            self._shadow_pcf_radius,
            self._self_shadow_strength,
            self._ground_height,
            self._shadow_catcher_opacity,
            self._shadow_catcher_softness,
            self._reflection_catcher_opacity,
            self._reflection_catcher_roughness,
            self._reflection_catcher_softness,
            self._contact_reflection_strength,
            self._contact_reflection_falloff,
            self._surface_override_strength,
            self._surface_roughness,
            self._surface_metallic,
            self._surface_reflectance,
            self._clearcoat_strength,
            self._clearcoat_roughness,
            self._clearcoat_ior,
            self._tone_exposure,
            self._tone_white_balance,
            self._tone_gamma,
            self._depth_edge_glow_strength,
            self._depth_edge_glow_radius,
            self._ao_strength,
            self._ao_radius,
            self._ao_distance,
            self._hybrid_sample_count,
            self._diffuse_gi_strength,
            self._specular_gi_strength,
            self._denoise_strength,
        )
        for row in (*self._parameter_rows, self._ao_mode):
            row.setEnabled(False)

        self._parameter_tabs = QTabWidget(controls)
        self._parameter_tabs.setObjectName("ArPbrParamTabs")
        self._parameter_tabs.setUsesScrollButtons(True)
        self._parameter_tabs.setDocumentMode(True)
        self._parameter_tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self._parameter_tabs.tabBar().setExpanding(False)
        controls_layout.addWidget(self._parameter_tabs, stretch=1)
        self._add_parameter_tab(
            "Light",
            (self._light_azimuth, self._light_elevation, self._direct_strength),
            tooltip="Key light",
        )
        self._add_parameter_tab(
            "Surface",
            (
                self._ibl_exposure,
                self._ibl_rotation,
                self._surface_override_strength,
                self._surface_roughness,
                self._surface_metallic,
                self._surface_reflectance,
                self._clearcoat_strength,
                self._clearcoat_roughness,
                self._clearcoat_ior,
            ),
            tooltip="Material surface and clearcoat",
        )
        self._add_parameter_tab(
            "Shad",
            (self._shadow_strength, self._shadow_pcf_radius, self._self_shadow_strength, self._ground_height),
            tooltip="Shadow",
        )
        self._add_parameter_tab(
            "Floor",
            (
                self._shadow_catcher_opacity,
                self._shadow_catcher_softness,
                self._reflection_catcher_opacity,
                self._reflection_catcher_roughness,
                self._reflection_catcher_softness,
                self._contact_reflection_strength,
                self._contact_reflection_falloff,
            ),
            tooltip="Floor catcher",
        )
        self._add_parameter_tab(
            "Tone",
            (self._tone_exposure, self._tone_white_balance, self._tone_gamma),
            tooltip="Tone mapping",
        )
        self._add_parameter_tab(
            "Z",
            (self._depth_edge_glow_strength, self._depth_edge_glow_radius),
            tooltip="Depth effects",
        )
        self._add_parameter_tab(
            "AO",
            (self._ao_mode, self._ao_strength, self._ao_radius, self._ao_distance),
            tooltip="Ambient occlusion",
        )
        self._add_parameter_tab(
            "GI",
            (self._hybrid_sample_count, self._diffuse_gi_strength, self._specular_gi_strength, self._denoise_strength),
            tooltip="Global illumination",
        )

        self._fit_btn = QPushButton("", controls)
        self._fit_btn.setObjectName("ArPbrIconButton")
        self._fit_btn.setIcon(app_icon("fit", size=16))
        self._fit_btn.setIconSize(icon_size(16))
        self._fit_btn.setToolTip("Fit model to view")
        self._fit_btn.setEnabled(False)
        self._fit_btn.clicked.connect(self.fit_view)
        button_row.addWidget(self._fit_btn)
        self._background_btn = QPushButton("", controls)
        self._background_btn.setObjectName("ArPbrToggleButton")
        self._background_btn.setIcon(app_icon("layers", size=16))
        self._background_btn.setIconSize(icon_size(16))
        self._background_btn.setCheckable(True)
        self._background_btn.setChecked(self._background_visible)
        self._background_btn.setEnabled(False)
        self._background_btn.clicked.connect(self._on_background_toggled)
        button_row.addWidget(self._background_btn)
        self._reset_btn = QPushButton("", controls)
        self._reset_btn.setObjectName("ArPbrIconButton")
        self._reset_btn.setIcon(app_icon("reset", size=16))
        self._reset_btn.setIconSize(icon_size(16))
        self._reset_btn.setToolTip("Reset light and view")
        self._reset_btn.setEnabled(False)
        self._reset_btn.clicked.connect(self.reset_view)
        button_row.addWidget(self._reset_btn)
        layout.addLayout(body, stretch=1)
        controls_dock = QDockWidget("Scene Lighting", self)
        controls_dock.setObjectName("ArPbrControlsDock")
        controls_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        controls_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea)
        controls_dock.setTitleBarWidget(QWidget(controls_dock))
        controls_dock.setWidget(controls)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, controls_dock)
        self._controls_dock = controls_dock

        for row, callback in (
            (self._ibl_exposure, self._set_ibl_exposure),
            (self._ibl_rotation, self._set_ibl_rotation_degrees),
            (self._light_azimuth, self._set_light_azimuth),
            (self._light_elevation, self._set_light_elevation),
            (self._direct_strength, self._set_direct_strength),
            (self._shadow_strength, self._set_shadow_strength),
            (self._shadow_pcf_radius, self._set_shadow_pcf_radius),
            (self._self_shadow_strength, self._set_self_shadow_strength),
            (self._ground_height, self._set_ground_height),
            (self._shadow_catcher_opacity, lambda value: self._set_state_float("shadow_catcher_opacity", value)),
            (self._shadow_catcher_softness, lambda value: self._set_state_float("shadow_catcher_softness", value)),
            (self._reflection_catcher_opacity, lambda value: self._set_state_float("reflection_catcher_opacity", value)),
            (self._reflection_catcher_roughness, lambda value: self._set_state_float("reflection_catcher_roughness", value)),
            (self._reflection_catcher_softness, lambda value: self._set_state_float("reflection_catcher_softness", value)),
            (self._contact_reflection_strength, lambda value: self._set_state_float("contact_reflection_strength", value)),
            (self._contact_reflection_falloff, lambda value: self._set_state_float("contact_reflection_falloff", value)),
            (self._surface_override_strength, lambda value: self._set_state_float("surface_override_strength", value)),
            (self._surface_roughness, lambda value: self._set_surface_channel("surface_roughness", value)),
            (self._surface_metallic, lambda value: self._set_surface_channel("surface_metallic", value)),
            (self._surface_reflectance, lambda value: self._set_surface_channel("surface_reflectance", value)),
            (self._clearcoat_strength, lambda value: self._set_state_float("clearcoat_strength", value)),
            (self._clearcoat_roughness, lambda value: self._set_state_float("clearcoat_roughness", value)),
            (self._clearcoat_ior, lambda value: self._set_state_float("clearcoat_ior", value)),
            (self._tone_exposure, lambda value: self._set_state_float("tone_exposure", value)),
            (self._tone_white_balance, lambda value: self._set_state_float("tone_white_balance", value)),
            (self._tone_gamma, lambda value: self._set_state_float("tone_gamma", value)),
            (self._depth_edge_glow_strength, lambda value: self._set_depth_edge_glow_strength(value)),
            (self._depth_edge_glow_radius, lambda value: self._set_state_float("depth_edge_glow_radius_px", value)),
            (self._ao_strength, self._set_ao_strength),
            (self._ao_radius, lambda value: self._set_state_float("ao_radius", value)),
            (self._ao_distance, lambda value: self._set_state_float("ao_distance", value)),
            (self._hybrid_sample_count, self._set_hybrid_sample_count),
            (self._diffuse_gi_strength, lambda value: self._set_state_float("diffuse_gi_strength", value)),
            (self._specular_gi_strength, lambda value: self._set_state_float("specular_gi_strength", value)),
            (self._denoise_strength, lambda value: self._set_state_float("denoise_strength", value)),
        ):
            row.value_changed.connect(callback)
        self._ao_mode.value_changed.connect(self._set_ambient_occlusion_mode)
        self._render_profile_combo.currentIndexChanged.connect(self._set_render_profile_index)
        self._hdri_combo.currentIndexChanged.connect(self._set_hdri_preset_index)
        self._sync_background_button()

        self._start_loading()

    def _add_parameter_tab(self, title: str, rows: tuple[QWidget, ...], *, tooltip: str = "") -> None:
        page = QWidget(self._parameter_tabs)
        page.setObjectName("ArPbrParamPage")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(10, 10, 10, 10)
        page_layout.setSpacing(9)
        for row in rows:
            page_layout.addWidget(row)
        page_layout.addStretch(1)

        scroll = QScrollArea(self._parameter_tabs)
        scroll.setObjectName("ArPbrTabScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        index = self._parameter_tabs.addTab(scroll, title)
        if tooltip:
            self._parameter_tabs.setTabToolTip(index, tooltip)

    def _populate_hdri_combo(self) -> None:
        self._hdri_combo.blockSignals(True)
        try:
            self._hdri_combo.clear()
            selected_id = str(self._selected_hdri.id if self._selected_hdri is not None else "")
            selected_index = 0
            for idx, preset in enumerate(self._hdri_presets):
                self._hdri_combo.addItem(preset.to_combo_label(), preset.id)
                if preset.id == selected_id:
                    selected_index = idx
            if self._hdri_combo.count() > 0:
                self._hdri_combo.setCurrentIndex(selected_index)
        finally:
            self._hdri_combo.blockSignals(False)

    def _populate_render_profile_combo(self) -> None:
        rows = _render_profile_combo_rows(self._render_profiles)
        available_ids = {str(row.get("id") or "") for row in rows}
        if self._render_profile not in available_ids:
            self._render_profile = str(rows[0].get("id") or PROFILE_AUTHORED) if rows else PROFILE_AUTHORED
        self._render_profile_combo.blockSignals(True)
        try:
            self._render_profile_combo.clear()
            selected_index = 0
            for idx, row in enumerate(rows):
                profile_id = str(row.get("id") or PROFILE_AUTHORED)
                self._render_profile_combo.addItem(str(row.get("label") or profile_id), profile_id)
                if profile_id == self._render_profile:
                    selected_index = idx
            if self._render_profile_combo.count() > 0:
                self._render_profile_combo.setCurrentIndex(selected_index)
        finally:
            self._render_profile_combo.blockSignals(False)

    def _sync_render_profile_combo(self) -> None:
        for index in range(self._render_profile_combo.count()):
            if str(self._render_profile_combo.itemData(index) or "") == self._render_profile:
                was_blocked = self._render_profile_combo.blockSignals(True)
                try:
                    self._render_profile_combo.setCurrentIndex(index)
                finally:
                    self._render_profile_combo.blockSignals(was_blocked)
                return

    def _sync_hdri_combo_to_selected(self) -> None:
        if self._selected_hdri is None:
            return
        selected_id = str(self._selected_hdri.id)
        for index in range(self._hdri_combo.count()):
            if str(self._hdri_combo.itemData(index) or "") == selected_id:
                was_blocked = self._hdri_combo.blockSignals(True)
                try:
                    self._hdri_combo.setCurrentIndex(index)
                finally:
                    self._hdri_combo.blockSignals(was_blocked)
                return

    def _start_loading(self) -> None:
        self._loader = _ArPbrPreviewLoader(
            self.asset_path,
            hdri_path=self._selected_hdri.path if self._selected_hdri is not None else None,
            max_triangles=self._preview_max_triangles,
            texture_max_size=self._preview_texture_max_size,
            render_profile=self._render_profile,
        )
        self._loader.loaded.connect(self._on_loaded)
        self._loader.failed.connect(self._on_failed)
        self._loader.finished.connect(self._cleanup_loader)
        self._loader.start()

    def _on_loaded(self, payload: dict[str, Any]) -> None:
        from tools.ar_pbr_gpu_window import GpuMeshWidget, GpuState

        fmt = QSurfaceFormat()
        fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setDepthBufferSize(24)
        QSurfaceFormat.setDefaultFormat(fmt)

        self._mesh_diag = dict(payload.get("mesh_diag") or {})
        descriptor = payload.get("descriptor") if isinstance(payload.get("descriptor"), dict) else {}
        self._descriptor = dict(descriptor)
        self._render_profiles = inspect_asset_render_profiles_from_descriptor(self._descriptor)
        self._populate_render_profile_combo()
        import_diag = payload.get("import_diag") if isinstance(payload.get("import_diag"), dict) else {}
        support = descriptor.get("support") if isinstance(descriptor.get("support"), dict) else import_diag.get("support")
        self._asset_support = dict(support if isinstance(support, dict) else {})
        hdri_diag = dict(payload.get("hdri_diag") or {})
        self._state = GpuState()
        self._selected_hdri = resolve_hdri_preset(str(self._selected_hdri.id if self._selected_hdri is not None else ""))
        self._state.light_azimuth = float(hdri_diag.get("key_light_azimuth", self._state.light_azimuth) or self._state.light_azimuth)
        self._state.light_elevation = float(hdri_diag.get("key_light_elevation", self._state.light_elevation) or self._state.light_elevation)
        bounds = self._mesh_diag.get("normalized_bounds") if isinstance(self._mesh_diag.get("normalized_bounds"), dict) else {}
        mins = bounds.get("min", []) if isinstance(bounds, dict) else []
        if isinstance(mins, list) and len(mins) >= 2:
            self._state.ground_y = float(mins[1]) + 0.01
        self.apply_lighting_settings(self._initial_lighting, emit=False)

        self._gl_widget = GpuMeshWidget(
            payload["vertices"],
            self._state,
            payload.get("hdri"),
            self._mesh_diag,
            payload.get("texture_plan") or {},
            int((payload.get("texture_diag") or {}).get("upload_max_size", 1024) or 1024),
            True,
            0.05,
            self._background_visible,
            parent=self._viewport_host,
        )
        self._viewport_layout.replaceWidget(self._loading_panel, self._gl_widget)
        self._loading_panel.hide()
        self._loading_panel.deleteLater()
        self._gl_widget.show()
        self._status.setText(_support_status_text(self._asset_support))
        self._enable_controls(True)
        self.sync_controls()
        self.fit_view()

    def _on_failed(self, reason: str) -> None:
        self._progress.hide()
        self._status.setText("Preview unavailable")
        for child in self._loading_panel.findChildren(QLabel):
            if child.objectName() == "ArPbrLoadingTitle":
                child.setText("Could not open this 3D asset")
            elif child.objectName() == "ArPbrLoadingBody":
                child.setText(str(reason or "Import failed"))

    def _cleanup_loader(self) -> None:
        if self._loader is not None:
            self._loader.deleteLater()
            self._loader = None

    def _enable_controls(self, enabled: bool) -> None:
        for row in (
            self._render_profile_combo,
            self._hdri_combo,
            self._parameter_tabs,
            self._ao_mode,
            *self._parameter_rows,
        ):
            row.setEnabled(enabled)
        self._fit_btn.setEnabled(enabled)
        self._background_btn.setEnabled(enabled)
        self._reset_btn.setEnabled(enabled)

    def sync_controls(self) -> None:
        if self._state is None:
            return
        self._ibl_exposure.set_value(float(self._state.ibl_exposure))
        self._ibl_rotation.set_value(float(self._state.ibl_rotation) * 360.0)
        self._light_azimuth.set_value(float(self._state.light_azimuth))
        self._light_elevation.set_value(float(self._state.light_elevation))
        self._direct_strength.set_value(float(self._state.direct_intensity))
        self._shadow_strength.set_value(float(self._state.shadow_strength))
        self._shadow_pcf_radius.set_value(float(self._state.shadow_pcf_radius))
        self._self_shadow_strength.set_value(float(self._state.self_shadow_strength))
        self._ground_height.set_value(float(self._state.ground_y))
        self._shadow_catcher_opacity.set_value(float(getattr(self._state, "shadow_catcher_opacity", DEFAULT_SHADOW_CATCHER_OPACITY)))
        self._shadow_catcher_softness.set_value(float(getattr(self._state, "shadow_catcher_softness", DEFAULT_SHADOW_CATCHER_SOFTNESS)))
        self._reflection_catcher_opacity.set_value(float(getattr(self._state, "reflection_catcher_opacity", DEFAULT_REFLECTION_CATCHER_OPACITY)))
        self._reflection_catcher_roughness.set_value(float(getattr(self._state, "reflection_catcher_roughness", DEFAULT_REFLECTION_CATCHER_ROUGHNESS)))
        self._reflection_catcher_softness.set_value(float(getattr(self._state, "reflection_catcher_softness", DEFAULT_REFLECTION_CATCHER_SOFTNESS)))
        self._contact_reflection_strength.set_value(float(getattr(self._state, "contact_reflection_strength", DEFAULT_CONTACT_REFLECTION_STRENGTH)))
        self._contact_reflection_falloff.set_value(float(getattr(self._state, "contact_reflection_falloff", DEFAULT_CONTACT_REFLECTION_FALLOFF)))
        self._surface_override_strength.set_value(float(getattr(self._state, "surface_override_strength", DEFAULT_SURFACE_OVERRIDE_STRENGTH)))
        self._surface_roughness.set_value(float(getattr(self._state, "surface_roughness", DEFAULT_SURFACE_ROUGHNESS)))
        self._surface_metallic.set_value(float(getattr(self._state, "surface_metallic", DEFAULT_SURFACE_METALLIC)))
        self._surface_reflectance.set_value(float(getattr(self._state, "surface_reflectance", DEFAULT_SURFACE_REFLECTANCE)))
        self._clearcoat_strength.set_value(float(getattr(self._state, "clearcoat_strength", DEFAULT_CLEARCOAT_STRENGTH)))
        self._clearcoat_roughness.set_value(float(getattr(self._state, "clearcoat_roughness", DEFAULT_CLEARCOAT_ROUGHNESS)))
        self._clearcoat_ior.set_value(float(getattr(self._state, "clearcoat_ior", DEFAULT_CLEARCOAT_IOR)))
        self._tone_exposure.set_value(float(getattr(self._state, "tone_exposure", 0.0)))
        self._tone_white_balance.set_value(float(getattr(self._state, "tone_white_balance", 6500.0)))
        self._tone_gamma.set_value(float(getattr(self._state, "tone_gamma", 2.2)))
        self._depth_edge_glow_strength.set_value(float(getattr(self._state, "depth_edge_glow_strength", DEFAULT_DEPTH_EDGE_GLOW_STRENGTH)))
        self._depth_edge_glow_radius.set_value(float(getattr(self._state, "depth_edge_glow_radius_px", DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX)))
        self._ao_mode.set_value(str(getattr(self._state, "ambient_occlusion_mode", DEFAULT_AMBIENT_OCCLUSION_MODE)))
        self._ao_strength.set_value(float(getattr(self._state, "ao_strength", DEFAULT_AO_STRENGTH)))
        self._ao_radius.set_value(float(getattr(self._state, "ao_radius", DEFAULT_AO_RADIUS)))
        self._ao_distance.set_value(float(getattr(self._state, "ao_distance", DEFAULT_AO_DISTANCE)))
        self._hybrid_sample_count.set_value(float(getattr(self._state, "hybrid_sample_count", DEFAULT_HYBRID_SAMPLE_COUNT)))
        self._diffuse_gi_strength.set_value(float(getattr(self._state, "diffuse_gi_strength", DEFAULT_DIFFUSE_GI_STRENGTH)))
        self._specular_gi_strength.set_value(float(getattr(self._state, "specular_gi_strength", DEFAULT_SPECULAR_GI_STRENGTH)))
        self._denoise_strength.set_value(float(getattr(self._state, "denoise_strength", DEFAULT_DENOISE_STRENGTH)))

    def lighting_settings(self) -> dict[str, Any]:
        if self._state is None:
            data = dict(self._initial_lighting)
            data["render_profile"] = self._render_profile
            return data
        return {
            "render_profile": self._render_profile,
            "hdri_id": str(self._selected_hdri.id if self._selected_hdri is not None else ""),
            "hdri_path": str(self._selected_hdri.path if self._selected_hdri is not None else ""),
            "show_environment_background": bool(self._background_visible),
            "ibl_exposure": float(self._state.ibl_exposure),
            "ibl_rotation": float(self._state.ibl_rotation),
            "light_azimuth": float(self._state.light_azimuth),
            "light_elevation": float(self._state.light_elevation),
            "direct_strength": float(self._state.direct_intensity),
            "shadow_strength": float(self._state.shadow_strength),
            "shadow_pcf_radius": float(self._state.shadow_pcf_radius),
            "self_shadow_strength": float(self._state.self_shadow_strength),
            "ground_height": float(self._state.ground_y),
            "shadow_catcher_opacity": float(getattr(self._state, "shadow_catcher_opacity", DEFAULT_SHADOW_CATCHER_OPACITY)),
            "shadow_catcher_softness": float(getattr(self._state, "shadow_catcher_softness", DEFAULT_SHADOW_CATCHER_SOFTNESS)),
            "shadow_catcher_matte_alpha": float(getattr(self._state, "shadow_catcher_matte_alpha", DEFAULT_SHADOW_CATCHER_MATTE_ALPHA)),
            "reflection_catcher_opacity": float(getattr(self._state, "reflection_catcher_opacity", DEFAULT_REFLECTION_CATCHER_OPACITY)),
            "reflection_catcher_roughness": float(getattr(self._state, "reflection_catcher_roughness", DEFAULT_REFLECTION_CATCHER_ROUGHNESS)),
            "reflection_catcher_softness": float(getattr(self._state, "reflection_catcher_softness", DEFAULT_REFLECTION_CATCHER_SOFTNESS)),
            "contact_reflection_strength": float(getattr(self._state, "contact_reflection_strength", DEFAULT_CONTACT_REFLECTION_STRENGTH)),
            "contact_reflection_falloff": float(getattr(self._state, "contact_reflection_falloff", DEFAULT_CONTACT_REFLECTION_FALLOFF)),
            "surface_override_strength": float(getattr(self._state, "surface_override_strength", DEFAULT_SURFACE_OVERRIDE_STRENGTH)),
            "surface_roughness": float(getattr(self._state, "surface_roughness", DEFAULT_SURFACE_ROUGHNESS)),
            "surface_metallic": float(getattr(self._state, "surface_metallic", DEFAULT_SURFACE_METALLIC)),
            "surface_reflectance": float(getattr(self._state, "surface_reflectance", DEFAULT_SURFACE_REFLECTANCE)),
            "clearcoat_mode": "clearcoat" if float(getattr(self._state, "clearcoat_strength", DEFAULT_CLEARCOAT_STRENGTH)) > 1.0e-6 else "off",
            "clearcoat_enabled": float(getattr(self._state, "clearcoat_strength", DEFAULT_CLEARCOAT_STRENGTH)) > 1.0e-6,
            "clearcoat_strength": float(getattr(self._state, "clearcoat_strength", DEFAULT_CLEARCOAT_STRENGTH)),
            "clearcoat_roughness": float(getattr(self._state, "clearcoat_roughness", DEFAULT_CLEARCOAT_ROUGHNESS)),
            "clearcoat_ior": float(getattr(self._state, "clearcoat_ior", DEFAULT_CLEARCOAT_IOR)),
            "tone_mapping": str(getattr(self._state, "tone_mapping", "aces")),
            "tone_exposure": float(getattr(self._state, "tone_exposure", 0.0)),
            "tone_white_balance": float(getattr(self._state, "tone_white_balance", 6500.0)),
            "tone_gamma": float(getattr(self._state, "tone_gamma", 2.2)),
            "depth_edge_glow_enabled": bool(getattr(self._state, "depth_edge_glow_enabled", False)),
            "depth_edge_glow_strength": float(getattr(self._state, "depth_edge_glow_strength", DEFAULT_DEPTH_EDGE_GLOW_STRENGTH)),
            "depth_edge_glow_radius_px": float(getattr(self._state, "depth_edge_glow_radius_px", DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX)),
            "ambient_occlusion_mode": str(getattr(self._state, "ambient_occlusion_mode", DEFAULT_AMBIENT_OCCLUSION_MODE)),
            "ao_strength": float(getattr(self._state, "ao_strength", DEFAULT_AO_STRENGTH)),
            "ao_radius": float(getattr(self._state, "ao_radius", DEFAULT_AO_RADIUS)),
            "ao_distance": float(getattr(self._state, "ao_distance", DEFAULT_AO_DISTANCE)),
            "hybrid_sample_count": int(round(float(getattr(self._state, "hybrid_sample_count", DEFAULT_HYBRID_SAMPLE_COUNT)))),
            "diffuse_gi_strength": float(getattr(self._state, "diffuse_gi_strength", DEFAULT_DIFFUSE_GI_STRENGTH)),
            "specular_gi_strength": float(getattr(self._state, "specular_gi_strength", DEFAULT_SPECULAR_GI_STRENGTH)),
            "denoise_strength": float(getattr(self._state, "denoise_strength", DEFAULT_DENOISE_STRENGTH)),
        }

    def apply_lighting_settings(self, settings: dict[str, Any] | None, *, emit: bool = True) -> None:
        if self._state is None or not isinstance(settings, dict):
            return
        previous_profile = self._render_profile
        self._suppress_emit = True
        try:
            if settings.get("hdri_id") or settings.get("hdri_path"):
                preset = resolve_hdri_preset(str(settings.get("hdri_id") or settings.get("hdri_path") or ""))
                if preset is not None:
                    self._selected_hdri = preset
                    self._sync_hdri_combo_to_selected()
            if settings.get("render_profile"):
                requested = str(settings.get("render_profile") or PROFILE_AUTHORED).strip().casefold()
                if requested in {PROFILE_AUTHORED, PROFILE_MARMOSET_PBR, PROFILE_VRM_MTOON}:
                    self._render_profile = requested
                    self._sync_render_profile_combo()
            if "show_environment_background" in settings:
                self._set_environment_background_visible(bool(settings["show_environment_background"]), emit=False)
            if "ibl_exposure" in settings:
                self._state.ibl_exposure = max(0.0, min(8.0, float(settings["ibl_exposure"])))
            if "ibl_rotation" in settings:
                self._state.ibl_rotation = max(-1.0, min(1.0, float(settings["ibl_rotation"])))
            if "light_azimuth" in settings:
                self._state.light_azimuth = max(-180.0, min(180.0, float(settings["light_azimuth"])))
            if "light_elevation" in settings:
                self._state.light_elevation = max(-20.0, min(89.0, float(settings["light_elevation"])))
            if "direct_strength" in settings:
                self._state.direct_intensity = max(0.0, min(4.0, float(settings["direct_strength"])))
            if "shadow_strength" in settings:
                self._state.shadow_strength = max(0.0, min(1.0, float(settings["shadow_strength"])))
            if "shadow_pcf_radius" in settings or "shadow_softness" in settings:
                raw_radius = settings.get("shadow_pcf_radius", settings.get("shadow_softness", self._state.shadow_pcf_radius))
                self._state.shadow_pcf_radius = max(0.0, min(8.0, float(raw_radius)))
            if "self_shadow_strength" in settings:
                self._state.self_shadow_strength = max(0.0, min(1.0, float(settings["self_shadow_strength"])))
            if "ground_height" in settings:
                self._state.ground_y = max(-3.0, min(3.0, float(settings["ground_height"])))
            for key in (
                "shadow_catcher_opacity",
                "shadow_catcher_softness",
                "shadow_catcher_matte_alpha",
                "reflection_catcher_opacity",
                "reflection_catcher_roughness",
                "reflection_catcher_softness",
                "contact_reflection_strength",
            ):
                if key in settings:
                    setattr(self._state, key, max(0.0, min(1.0, float(settings[key]))))
            if "contact_reflection_falloff" in settings:
                self._state.contact_reflection_falloff = max(0.05, min(1.0, float(settings["contact_reflection_falloff"])))
            if any(key in settings for key in (
                "surface",
                "surface_override",
                "surface_rendering",
                "surface_override_strength",
                "surface_mix",
                "surface_roughness",
                "surface_metallic",
                "surface_reflectance",
            )):
                surface = normalize_surface_settings(settings)
                self._state.surface_override_strength = float(surface["override_strength"])
                self._state.surface_roughness = float(surface["roughness"])
                self._state.surface_metallic = float(surface["metallic"])
                self._state.surface_reflectance = float(surface["reflectance"])
            if any(key in settings for key in (
                "clearcoat",
                "clear_coat",
                "coat",
                "clearcoat_enabled",
                "clearcoat_mode",
                "clearcoat_strength",
                "clearcoat_roughness",
                "clearcoat_ior",
                "clearcoat_tint",
            )):
                clearcoat = normalize_clearcoat_settings(settings)
                self._state.clearcoat_strength = float(clearcoat["strength"])
                self._state.clearcoat_roughness = float(clearcoat["roughness"])
                self._state.clearcoat_ior = float(clearcoat["ior"])
            if "tone_mapping" in settings:
                requested_tone = str(settings.get("tone_mapping") or "aces").strip().casefold()
                self._state.tone_mapping = requested_tone if requested_tone in {"aces", "agx", "reinhard"} else "aces"
            if "tone_exposure" in settings:
                self._state.tone_exposure = max(-8.0, min(8.0, float(settings["tone_exposure"])))
            if "tone_white_balance" in settings:
                self._state.tone_white_balance = max(1000.0, min(40000.0, float(settings["tone_white_balance"])))
            if "tone_gamma" in settings:
                self._state.tone_gamma = max(0.1, min(4.0, float(settings["tone_gamma"])))
            if "depth_edge_glow_strength" in settings:
                self._state.depth_edge_glow_strength = max(0.0, min(1.0, float(settings["depth_edge_glow_strength"])))
                self._state.depth_edge_glow_enabled = bool(self._state.depth_edge_glow_strength > 1.0e-6)
            if "depth_edge_glow_enabled" in settings:
                self._state.depth_edge_glow_enabled = bool(settings["depth_edge_glow_enabled"])
            if "depth_edge_glow_radius_px" in settings:
                self._state.depth_edge_glow_radius_px = max(0.5, min(18.0, float(settings["depth_edge_glow_radius_px"])))
            if "ambient_occlusion_mode" in settings:
                self._state.ambient_occlusion_mode = self._normalize_ao_mode(settings["ambient_occlusion_mode"])
                if self._state.ambient_occlusion_mode == "off":
                    self._state.ao_strength = 0.0
                elif "ao_strength" not in settings and float(getattr(self._state, "ao_strength", 0.0) or 0.0) <= 1.0e-6:
                    self._state.ao_strength = DEFAULT_AO_ACTIVE_STRENGTH
            if "ao_strength" in settings:
                self._state.ao_strength = max(0.0, min(2.0, float(settings["ao_strength"])))
                if self._state.ao_strength > 1.0e-6 and str(getattr(self._state, "ambient_occlusion_mode", "off")) == "off":
                    self._state.ambient_occlusion_mode = "screen"
            if "ao_radius" in settings:
                self._state.ao_radius = max(0.5, min(32.0, float(settings["ao_radius"])))
            if "ao_distance" in settings:
                self._state.ao_distance = max(0.01, min(4.0, float(settings["ao_distance"])))
            if "hybrid_sample_count" in settings:
                self._state.hybrid_sample_count = max(1, min(64, int(round(float(settings["hybrid_sample_count"])))))
            if "diffuse_gi_strength" in settings:
                self._state.diffuse_gi_strength = max(0.0, min(2.0, float(settings["diffuse_gi_strength"])))
            if "specular_gi_strength" in settings:
                self._state.specular_gi_strength = max(0.0, min(2.0, float(settings["specular_gi_strength"])))
            if "denoise_strength" in settings:
                self._state.denoise_strength = max(0.0, min(1.0, float(settings["denoise_strength"])))
            self.sync_controls()
        finally:
            self._suppress_emit = False
        if self._render_profile != previous_profile:
            self._apply_render_profile_to_mesh()
        self._update()
        if emit:
            self._emit_lighting_changed()

    def _emit_lighting_changed(self) -> None:
        if self._suppress_emit:
            return
        self.settings_changed.emit(self.lighting_settings())

    def _sync_background_button(self) -> None:
        button = getattr(self, "_background_btn", None)
        if button is None:
            return
        button.blockSignals(True)
        try:
            button.setChecked(bool(self._background_visible))
            button.setToolTip(
                "Hide HDR background; lighting stays active"
                if self._background_visible
                else "Show HDR background"
            )
        finally:
            button.blockSignals(False)

    def _set_environment_background_visible(self, visible: bool, *, emit: bool = True) -> None:
        self._background_visible = bool(visible)
        self._sync_background_button()
        if self._gl_widget is not None and hasattr(self._gl_widget, "set_environment_background_visible"):
            self._gl_widget.set_environment_background_visible(self._background_visible)
        if emit:
            self._emit_lighting_changed()

    def _on_background_toggled(self, checked: bool) -> None:
        self._set_environment_background_visible(bool(checked))

    def _apply_render_profile_to_mesh(self) -> None:
        if not self._descriptor or self._gl_widget is None:
            return
        try:
            from tools.ar_pbr_gpu_window import build_vertex_buffer

            vertices, mesh_diag = build_vertex_buffer(
                self._descriptor,
                track={"render": {"render_profile": self._render_profile}},
            )
            self._mesh_diag = dict(mesh_diag or {})
            if hasattr(self._gl_widget, "set_mesh_data"):
                self._gl_widget.set_mesh_data(vertices, self._mesh_diag)
            else:
                self._gl_widget.update()
            label = self._render_profile_combo.currentText() or "Authored material"
            self._status.setText(f"Render profile: {label}")
        except Exception as exc:
            self._status.setText(f"Render profile unavailable: {type(exc).__name__}")

    def _set_render_profile_index(self, index: int) -> None:
        if index < 0:
            return
        profile = str(self._render_profile_combo.itemData(index) or PROFILE_AUTHORED)
        if profile not in {PROFILE_AUTHORED, PROFILE_MARMOSET_PBR, PROFILE_VRM_MTOON}:
            profile = PROFILE_AUTHORED
        if profile == self._render_profile:
            return
        self._render_profile = profile
        self._apply_render_profile_to_mesh()
        self._emit_lighting_changed()

    def fit_view(self) -> None:
        if self._gl_widget is None:
            return
        self._gl_widget.auto_fit_enabled = True
        if self._state is not None:
            self._state.pan_x = 0.0
            self._state.pan_y = 0.0
            self._state.pan_z = 0.0
        self._gl_widget.fit_current_view()
        self._gl_widget.auto_fit_pending = False
        self.sync_controls()
        self._gl_widget.update()

    def reset_view(self) -> None:
        if self._state is None:
            return
        self._state.pitch = -10.0
        self._state.yaw = 72.0
        self._state.roll = 0.0
        self._state.camera_z = 3.25
        self._state.pan_x = 0.0
        self._state.pan_y = 0.0
        self._state.pan_z = 0.0
        self._state.ibl_exposure = 1.1
        self._state.ibl_rotation = 0.0
        self._state.direct_intensity = 0.42
        self._state.shadow_strength = DEFAULT_SHADOW_STRENGTH
        self._state.shadow_pcf_radius = 1.35
        self._state.self_shadow_strength = 0.45
        self._state.shadow_catcher_opacity = DEFAULT_SHADOW_CATCHER_OPACITY
        self._state.shadow_catcher_softness = DEFAULT_SHADOW_CATCHER_SOFTNESS
        self._state.shadow_catcher_matte_alpha = DEFAULT_SHADOW_CATCHER_MATTE_ALPHA
        self._state.reflection_catcher_opacity = DEFAULT_REFLECTION_CATCHER_OPACITY
        self._state.reflection_catcher_roughness = DEFAULT_REFLECTION_CATCHER_ROUGHNESS
        self._state.reflection_catcher_softness = DEFAULT_REFLECTION_CATCHER_SOFTNESS
        self._state.contact_reflection_strength = DEFAULT_CONTACT_REFLECTION_STRENGTH
        self._state.contact_reflection_falloff = DEFAULT_CONTACT_REFLECTION_FALLOFF
        self._state.surface_override_strength = DEFAULT_SURFACE_OVERRIDE_STRENGTH
        self._state.surface_roughness = DEFAULT_SURFACE_ROUGHNESS
        self._state.surface_metallic = DEFAULT_SURFACE_METALLIC
        self._state.surface_reflectance = DEFAULT_SURFACE_REFLECTANCE
        self._state.clearcoat_strength = DEFAULT_CLEARCOAT_STRENGTH
        self._state.clearcoat_roughness = DEFAULT_CLEARCOAT_ROUGHNESS
        self._state.clearcoat_ior = DEFAULT_CLEARCOAT_IOR
        self._state.tone_mapping = "aces"
        self._state.tone_exposure = 0.0
        self._state.tone_white_balance = 6500.0
        self._state.tone_gamma = 2.2
        self._state.depth_edge_glow_enabled = False
        self._state.depth_edge_glow_strength = DEFAULT_DEPTH_EDGE_GLOW_STRENGTH
        self._state.depth_edge_glow_radius_px = DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX
        self._state.ambient_occlusion_mode = DEFAULT_AMBIENT_OCCLUSION_MODE
        self._state.ao_strength = DEFAULT_AO_STRENGTH
        self._state.ao_radius = DEFAULT_AO_RADIUS
        self._state.ao_distance = DEFAULT_AO_DISTANCE
        self._state.hybrid_sample_count = DEFAULT_HYBRID_SAMPLE_COUNT
        self._state.diffuse_gi_strength = DEFAULT_DIFFUSE_GI_STRENGTH
        self._state.specular_gi_strength = DEFAULT_SPECULAR_GI_STRENGTH
        self._state.denoise_strength = DEFAULT_DENOISE_STRENGTH
        bounds = self._mesh_diag.get("normalized_bounds") if isinstance(self._mesh_diag.get("normalized_bounds"), dict) else {}
        mins = bounds.get("min", []) if isinstance(bounds, dict) else []
        self._state.ground_y = float(mins[1]) + 0.01 if isinstance(mins, list) and len(mins) >= 2 else -0.52
        self.sync_controls()
        self.fit_view()
        self._emit_lighting_changed()

    def _set_hdri_preset_index(self, index: int) -> None:
        if index < 0 or index >= len(self._hdri_presets):
            return
        preset = self._hdri_presets[index]
        if not preset.available:
            self._status.setText(f"HDRI missing: {preset.label}")
            return
        self._selected_hdri = preset
        self._status.setText(f"Loading HDRI: {preset.label}")
        try:
            from tools.ar_pbr_gpu_window import _load_hdri_or_none

            hdri, diag = _load_hdri_or_none(preset.path)
            if diag.get("enabled") and hdri is not None:
                if self._state is not None:
                    self._state.light_azimuth = float(diag.get("key_light_azimuth", self._state.light_azimuth) or self._state.light_azimuth)
                    self._state.light_elevation = float(diag.get("key_light_elevation", self._state.light_elevation) or self._state.light_elevation)
                if self._gl_widget is not None and hasattr(self._gl_widget, "set_hdri"):
                    self._gl_widget.set_hdri(hdri)
                self.sync_controls()
                self._status.setText(f"HDRI: {preset.label}")
                self._emit_lighting_changed()
            else:
                self._status.setText(f"HDRI unavailable: {diag.get('reason', 'unknown')}")
        except Exception as exc:
            self._status.setText(f"HDRI failed: {type(exc).__name__}")

    def _update(self) -> None:
        if self._gl_widget is not None:
            self._gl_widget.update()

    def _set_state_float(self, attr: str, value: float) -> None:
        if self._state is None:
            return
        setattr(self._state, attr, float(value))
        self._update()
        self._emit_lighting_changed()

    def _set_surface_channel(self, attr: str, value: float) -> None:
        if self._state is None:
            return
        setattr(self._state, attr, float(value))
        if float(getattr(self._state, "surface_override_strength", 0.0) or 0.0) <= 1.0e-6:
            self._state.surface_override_strength = 1.0
            self._surface_override_strength.set_value(1.0)
        self._update()
        self._emit_lighting_changed()

    @staticmethod
    def _normalize_ao_mode(value: Any) -> str:
        text = str(value or DEFAULT_AMBIENT_OCCLUSION_MODE).strip().casefold().replace("-", "_").replace(" ", "_")
        if text in {"ssao", "screen_space", "screen_space_ao"}:
            return "screen"
        if text in {"raytrace", "ray_tracing", "raytracing", "raytraced", "export_detail"}:
            return "ray_traced"
        if text in {"screen", "ray_traced"}:
            return text
        return "off"

    def _set_ambient_occlusion_mode(self, value: str) -> None:
        if self._state is None:
            return
        self._state.ambient_occlusion_mode = self._normalize_ao_mode(value)
        if self._state.ambient_occlusion_mode == "off":
            self._state.ao_strength = 0.0
            self._ao_strength.set_value(0.0)
        elif float(getattr(self._state, "ao_strength", 0.0) or 0.0) <= 1.0e-6:
            self._state.ao_strength = DEFAULT_AO_ACTIVE_STRENGTH
            self._ao_strength.set_value(DEFAULT_AO_ACTIVE_STRENGTH)
        self._update()
        self._emit_lighting_changed()

    def _set_ao_strength(self, value: float) -> None:
        if self._state is None:
            return
        self._state.ao_strength = max(0.0, min(2.0, float(value)))
        if self._state.ao_strength > 1.0e-6 and str(getattr(self._state, "ambient_occlusion_mode", "off")) == "off":
            self._state.ambient_occlusion_mode = "screen"
            self._ao_mode.set_value("screen")
        self._update()
        self._emit_lighting_changed()

    def _set_hybrid_sample_count(self, value: float) -> None:
        if self._state is None:
            return
        self._state.hybrid_sample_count = max(1, min(64, int(round(float(value)))))
        self._hybrid_sample_count.set_value(float(self._state.hybrid_sample_count))
        self._update()
        self._emit_lighting_changed()

    def _set_depth_edge_glow_strength(self, value: float) -> None:
        if self._state is None:
            return
        self._state.depth_edge_glow_strength = float(value)
        self._state.depth_edge_glow_enabled = bool(float(value) > 1.0e-6)
        self._update()
        self._emit_lighting_changed()

    def _set_ibl_exposure(self, value: float) -> None:
        if self._state is not None:
            self._state.ibl_exposure = float(value)
            self._update()
            self._emit_lighting_changed()

    def _set_ibl_rotation_degrees(self, value: float) -> None:
        if self._state is not None:
            self._state.ibl_rotation = float(value) / 360.0
            self._update()
            self._emit_lighting_changed()

    def _set_light_azimuth(self, value: float) -> None:
        if self._state is not None:
            self._state.light_azimuth = float(value)
            self._update()
            self._emit_lighting_changed()

    def _set_light_elevation(self, value: float) -> None:
        if self._state is not None:
            self._state.light_elevation = float(value)
            self._update()
            self._emit_lighting_changed()

    def _set_direct_strength(self, value: float) -> None:
        if self._state is not None:
            self._state.direct_intensity = float(value)
            self._update()
            self._emit_lighting_changed()

    def _set_shadow_strength(self, value: float) -> None:
        if self._state is not None:
            self._state.shadow_strength = float(value)
            self._update()
            self._emit_lighting_changed()

    def _set_shadow_pcf_radius(self, value: float) -> None:
        if self._state is not None:
            self._state.shadow_pcf_radius = float(value)
            self._update()
            self._emit_lighting_changed()

    def _set_self_shadow_strength(self, value: float) -> None:
        if self._state is not None:
            self._state.self_shadow_strength = float(value)
            self._update()
            self._emit_lighting_changed()

    def _set_ground_height(self, value: float) -> None:
        if self._state is not None:
            self._state.ground_y = float(value)
            self._update()
            self._emit_lighting_changed()


_AR_PBR_PREVIEW_QSS = """
QWidget#ArPbrPreviewRoot {
    background-color: #0B0D16;
}
QLabel#ArPbrPreviewTitle {
    color: #F8F4EA;
    font-size: 13px;
    font-weight: 900;
}
QLabel#ArPbrPreviewSubtitle,
QLabel#ArPbrPreviewStatus {
    color: #9EA6C7;
    font-size: 10px;
    font-weight: 700;
}
QFrame#ArPbrViewportHost {
    background-color: #05070C;
    border: 1px solid #30384F;
    border-radius: 14px;
}
QWidget#ArPbrLoadingPanel {
    background-color: #090B13;
    border-radius: 14px;
}
QLabel#ArPbrLoadingTitle {
    color: #F8F4EA;
    font-size: 16px;
    font-weight: 900;
}
QLabel#ArPbrLoadingBody {
    color: #9EA6C7;
    font-size: 11px;
    font-weight: 650;
}
QFrame#ArPbrControls {
    background-color: rgba(18, 21, 34, 226);
    border: 1px solid rgba(126, 141, 198, 44);
    border-radius: 16px;
    min-width: 330px;
}
QLabel#ArPbrControlsTitle {
    color: #F8F4EA;
    font-size: 12px;
    font-weight: 900;
}
QComboBox#ArPbrHdriCombo {
    background-color: rgba(255, 255, 255, 18);
    color: #F8F4EA;
    border: 1px solid #37405A;
    border-radius: 10px;
    padding: 6px 10px;
    min-height: 26px;
    font-size: 11px;
    font-weight: 800;
}
QComboBox#ArPbrHdriCombo:hover {
    background-color: rgba(255, 255, 255, 28);
    border-color: #7580A5;
}
QComboBox#ArPbrHdriCombo::drop-down {
    border: 0px;
    width: 22px;
}
QComboBox#ArPbrHdriCombo QAbstractItemView {
    background-color: #151927;
    color: #F8F4EA;
    selection-background-color: #6D5DFB;
    border: 1px solid #37405A;
}
QTabWidget#ArPbrParamTabs::pane {
    background-color: rgba(10, 12, 22, 150);
    border: 1px solid rgba(126, 141, 198, 42);
    border-radius: 13px;
    top: -1px;
}
QTabWidget#ArPbrParamTabs QTabBar::tab {
    background-color: rgba(255, 255, 255, 15);
    color: #AEB5CF;
    border: 1px solid rgba(126, 141, 198, 45);
    border-bottom-color: rgba(126, 141, 198, 26);
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 5px 4px;
    margin-right: 1px;
    min-width: 24px;
    font-size: 10px;
    font-weight: 900;
}
QTabWidget#ArPbrParamTabs QTabBar::tab:hover {
    background-color: rgba(255, 255, 255, 28);
    color: #F8F4EA;
}
QTabWidget#ArPbrParamTabs QTabBar::tab:selected {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #5BC6E8, stop:0.52 #7667FF, stop:1 #F06E5A);
    color: #FFFFFF;
    border-color: rgba(255, 255, 255, 126);
}
QScrollArea#ArPbrTabScroll,
QWidget#ArPbrParamPage {
    background: transparent;
    border: 0px;
}
QLabel#ArPbrControlLabel {
    color: #D7DAE7;
    font-size: 10px;
    font-weight: 800;
    background: transparent;
    border: 0px;
    padding: 0px;
}
QLabel#ArPbrControlValue {
    color: #F8F4EA;
    font-size: 10px;
    font-weight: 800;
    background-color: rgba(255, 255, 255, 20);
    border: 1px solid rgba(126, 141, 198, 50);
    border-radius: 7px;
    padding: 1px 6px;
    min-width: 42px;
}
QPushButton#ArPbrIconButton {
    background-color: rgba(255, 255, 255, 18);
    color: #E8EAF4;
    border: 1px solid #37405A;
    border-radius: 12px;
    padding: 0px;
    min-width: 36px;
    min-height: 34px;
}
QPushButton#ArPbrIconButton:hover {
    background-color: rgba(255, 255, 255, 30);
    border-color: #7580A5;
}
QPushButton#ArPbrToggleButton {
    background-color: rgba(255, 255, 255, 14);
    color: #E8EAF4;
    border: 1px solid #37405A;
    border-radius: 12px;
    padding: 0px;
    min-width: 36px;
    min-height: 34px;
}
QPushButton#ArPbrToggleButton:hover {
    background-color: rgba(255, 255, 255, 28);
    border-color: #7580A5;
}
QPushButton#ArPbrToggleButton:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #5BC6E8, stop:0.52 #7667FF, stop:1 #F06E5A);
    border-color: rgba(255, 255, 255, 145);
}
"""
