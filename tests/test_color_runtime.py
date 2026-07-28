from __future__ import annotations

from pathlib import Path

import numpy as np

from app.color_management import validate_color_management
from app.color_ocio import (
    build_ocio_plan,
    list_builtin_ocio_configs,
    preferred_aces_ocio_uri,
)
from app.color_runtime import (
    append_project_output_transform_graph,
    apply_project_display_transform_premultiplied_rgba,
    apply_project_display_transform_rgb,
    ensure_display_lut,
)


def test_builtin_aces_studio_config_is_available() -> None:
    rows = list_builtin_ocio_configs()
    uri = preferred_aces_ocio_uri()
    assert rows
    assert uri == "ocio://studio-config-v2.2.0_aces-v1.3_ocio-v2.4"
    assert any(row["uri"] == uri for row in rows)
    plan = build_ocio_plan(
        {
            "input_space": "srgb",
            "working_space": "acescg",
            "ocio_config_path": uri,
        },
        source="srgb",
        destination="rec709",
    )
    assert plan.available
    assert plan.enabled
    assert plan.source == "sRGB Encoded Rec.709 (sRGB)"
    assert plan.destination == "Rec.1886 Rec.709 - Display"


def test_frozen_builds_collect_ocio_binary_and_builtin_config_data() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in (root / "TigerCapture.spec", root / "mac" / "TigerCapture-mac.spec"):
        text = path.read_text(encoding="utf-8")
        assert "collect_all('PyOpenColorIO')" in text
        assert "ocio_binaries" in text
        assert "ocio_datas" in text
        assert "ocio_hiddenimports" in text


def test_builtin_ocio_uri_passes_project_validation() -> None:
    report = validate_color_management({
        "input_space": "srgb",
        "working_space": "acescg",
        "output_space": "rec709",
        "view_transform": "aces-1.3",
        "ocio_config_path": preferred_aces_ocio_uri(),
    })
    assert report["ok"]
    assert not any("unavailable" in warning.lower() for warning in report["warnings"])
    assert not any("does not exist" in warning.lower() for warning in report["warnings"])


def test_default_runtime_color_transform_is_byte_identical() -> None:
    rgb = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
    output, report = apply_project_display_transform_rgb(rgb, None)
    assert np.array_equal(output, rgb)
    assert report["applied"] is False
    assert report["engine"] == "identity"


def test_aces_fallback_changes_pixels_deterministically() -> None:
    rgb = np.full((4, 4, 3), 128, dtype=np.uint8)
    settings = {
        "working_space": "acescg",
        "view_transform": "aces-1.3",
        "output_space": "rec709",
        "output_transfer": "bt709",
    }
    first, first_report = apply_project_display_transform_rgb(rgb, settings)
    second, second_report = apply_project_display_transform_rgb(rgb, settings)
    assert np.array_equal(first, second)
    assert not np.array_equal(first, rgb)
    assert first_report["engine"] == "aces_fitted_fallback"
    assert second_report["applied"] is True


def test_premultiplied_alpha_survives_display_transform() -> None:
    rgba = np.array([[[64, 32, 16, 128], [0, 0, 0, 0]]], dtype=np.uint8)
    output, report = apply_project_display_transform_premultiplied_rgba(
        rgba,
        {"working_space": "acescg", "view_transform": "aces-1.3"},
    )
    assert report["applied"] is True
    assert output[..., 3].tolist() == rgba[..., 3].tolist()
    assert output[0, 1].tolist() == [0, 0, 0, 0]
    assert np.all(output[0, 0, :3] <= output[0, 0, 3])


def test_hdr_output_graph_uses_real_pq_and_hlg_zscale() -> None:
    pq_graph, pq_label, pq_report = append_project_output_transform_graph(
        "[0:v]null[outv]",
        "outv",
        {"output_space": "rec2020", "output_transfer": "pq"},
    )
    assert "t=smpte2084" in pq_graph
    assert "format=yuv420p10le" in pq_graph
    assert pq_label.endswith("_hdr")
    assert pq_report["hdr_transfer"] == "pq"

    hlg_graph, _hlg_label, hlg_report = append_project_output_transform_graph(
        "[0:v]null[outv]",
        "outv",
        {"output_space": "rec2020", "output_transfer": "hlg"},
    )
    assert "t=arib-std-b67" in hlg_graph
    assert hlg_report["hdr_transfer"] == "hlg"


def test_export_display_lut_is_baked_from_the_preview_transform() -> None:
    settings = {
        "working_space": "acescg",
        "view_transform": "aces-1.3",
        "output_space": "rec709",
        "output_transfer": "bt709",
    }
    path, report = ensure_display_lut(settings, size=5)
    lines = [
        line
        for line in open(path, encoding="ascii").read().splitlines()
        if line and line[0].isdigit()
    ]
    center = np.asarray([float(value) for value in lines[62].split()])
    preview, _preview_report = apply_project_display_transform_rgb(
        np.asarray([[[127, 127, 127]]], dtype=np.uint8),
        settings,
    )
    assert report["applied"] is True
    assert np.allclose(center, preview[0, 0] / 255.0, atol=1e-7)


def test_real_ocio_preview_and_export_lut_are_byte_identical_at_grid_nodes() -> None:
    settings = {
        "input_space": "srgb",
        "working_space": "acescg",
        "view_transform": "aces-1.3",
        "output_space": "rec709",
        "output_transfer": "bt709",
        "ocio_config_path": preferred_aces_ocio_uri(),
    }
    path, report = ensure_display_lut(settings, size=5)
    lines = [
        line
        for line in open(path, encoding="ascii").read().splitlines()
        if line and line[0].isdigit()
    ]
    lut = np.rint(
        np.asarray([[float(value) for value in line.split()] for line in lines]) * 255.0
    ).clip(0, 255).astype(np.uint8)
    axis = np.linspace(0, 255, 5, dtype=np.uint8)
    samples = np.asarray(
        [[red, green, blue] for blue in axis for green in axis for red in axis],
        dtype=np.uint8,
    ).reshape(-1, 1, 3)
    preview, preview_report = apply_project_display_transform_rgb(samples, settings)
    assert report["engine"] == "ocio"
    assert preview_report["engine"] == "ocio"
    assert preview_report["ocio"]["applied"] is True
    assert not np.array_equal(preview, samples)
    assert np.array_equal(lut, preview.reshape(-1, 3))


def test_project_color_management_actions_refresh_the_shared_player() -> None:
    from app.actions.registry import ActionRegistry

    class Player:
        def __init__(self) -> None:
            self.settings = {}
            self.refresh_count = 0

        def set_project_settings(self, settings) -> None:
            self.settings = dict(settings)

        def refresh_current_frame(self) -> None:
            self.refresh_count += 1

    class Owner:
        def __init__(self) -> None:
            self._project_settings = {}
            self._player = Player()
            self.changes = []

        def _register_change(self, label: str) -> None:
            self.changes.append(label)

    owner = Owner()
    registry = ActionRegistry(owner)
    result = registry.execute("color.management.set", {
        "settings": {
            "working_space": "acescg",
            "view_transform": "aces-1.3",
            "output_space": "rec2020",
            "output_transfer": "pq",
        },
    })
    assert result.ok
    assert owner._player.refresh_count == 1
    assert owner._player.settings["color_management"]["working_space"] == "acescg"
    assert (
        owner._player.settings["color_management"]["ocio_config_path"]
        == preferred_aces_ocio_uri()
    )
    fetched = registry.execute("color.management.get", {})
    assert fetched.ok
    assert fetched.result["settings"]["output_transfer"] == "pq"
