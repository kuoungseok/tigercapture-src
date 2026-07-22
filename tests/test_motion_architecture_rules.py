from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MOTION_ROOT = ROOT / "app" / "motion_designer"
ARCHITECTURE_DOC = ROOT / "docs" / "MOTION_DESIGNER_ARCHITECTURE.md"
BASELINE_TOOL = ROOT / "tools" / "qa_motion_baseline.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _load_baseline_tool():
    spec = importlib.util.spec_from_file_location("qa_motion_baseline", BASELINE_TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_motion_core_contracts_are_qt_and_editor_facade_free() -> None:
    forbidden_prefixes = ("PySide6", "app.video_editor_window", "app.video_editor_ui")
    core_files = [MOTION_ROOT / "__init__.py", MOTION_ROOT / "contracts.py"]
    for path in core_files:
        assert path.is_file()
        offenders = sorted(
            name for name in _imports(path) if name.startswith(forbidden_prefixes)
        )
        assert not offenders, f"{path.relative_to(ROOT)} imports forbidden dependencies: {offenders}"


def test_motion_vector_geometry_core_is_qt_free() -> None:
    path = MOTION_ROOT / "vector_shapes.py"
    offenders = sorted(name for name in _imports(path) if name.startswith("PySide6"))
    assert not offenders, f"{path.relative_to(ROOT)} imports UI dependencies: {offenders}"
    tessellation_imports = _imports(MOTION_ROOT / "vector_tessellation.py")
    assert "vector_shapes" in tessellation_imports
    boolean_path = MOTION_ROOT / "boolean_layers.py"
    boolean_offenders = sorted(
        name for name in _imports(boolean_path) if name.startswith("PySide6")
    )
    assert not boolean_offenders, (
        f"{boolean_path.relative_to(ROOT)} imports UI dependencies: {boolean_offenders}"
    )


def test_motion_typography_selector_core_is_qt_free() -> None:
    path = MOTION_ROOT / "typography_motion.py"
    offenders = sorted(name for name in _imports(path) if name.startswith("PySide6"))
    assert not offenders, f"{path.relative_to(ROOT)} imports UI dependencies: {offenders}"


def test_motion_mask_tracking_cache_core_is_qt_free() -> None:
    path = MOTION_ROOT / "mask_tracking.py"
    offenders = sorted(name for name in _imports(path) if name.startswith("PySide6"))
    assert not offenders, f"{path.relative_to(ROOT)} imports UI dependencies: {offenders}"


def test_motion_tracking_provider_is_qt_and_renderer_free() -> None:
    path = MOTION_ROOT / "tracking_provider.py"
    forbidden_prefixes = ("PySide6", "app.motion_designer.render", "app.video_editor_window")
    offenders = sorted(
        name for name in _imports(path) if name.startswith(forbidden_prefixes)
    )
    assert not offenders, f"{path.relative_to(ROOT)} imports forbidden dependencies: {offenders}"


def test_motion_ai_request_and_proposal_core_is_qt_free() -> None:
    path = MOTION_ROOT / "ai_workspace.py"
    offenders = sorted(name for name in _imports(path) if name.startswith("PySide6"))
    assert not offenders, f"{path.relative_to(ROOT)} imports UI dependencies: {offenders}"


def test_motion_contracts_validate_boundaries_and_commands() -> None:
    from app.motion_designer import Bounds, MotionCommand, SourceFrame, Viewport

    frame = SourceFrame(rgba=object(), bounds=Bounds(width=10, height=20), diagnostics={"renderer": "test"})
    command = MotionCommand(id="cmd-1", operation="layer.add", composition_id="comp-1")

    assert frame.premultiplied_alpha is True
    assert frame.diagnostics == {"renderer": "test"}
    assert command.params == {}
    with pytest.raises(ValueError):
        Viewport(0, 1080)
    with pytest.raises(ValueError):
        MotionCommand(id="", operation="layer.add", composition_id="comp-1")


def test_motion_architecture_document_captures_required_contracts() -> None:
    text = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    for required in (
        "SourceFrame",
        "MotionComposition",
        "MotionCommand",
        "premultiplied alpha",
        "app/video_editor_window.py",
        "debugCapture",
        "sample_assets",
        "qa_corpus",
        "tracking_provider.py",
    ):
        assert required in text


def test_motion_baseline_uses_durable_input_and_disposable_output() -> None:
    module = _load_baseline_tool()

    assert module.DEFAULT_MEDIA.is_relative_to(ROOT / "qa_corpus")
    assert module.DEFAULT_OUTPUT.is_relative_to(ROOT / "debugCapture")
    assert "debugCapture" not in str(module.DEFAULT_MEDIA)


def test_motion_baseline_builds_without_mutating_a_user_project(tmp_path: Path) -> None:
    module = _load_baseline_tool()
    report = module.build_report(module.DEFAULT_MEDIA, sample_count=2)

    assert report["ok"] is True
    assert report["project_io"]["canonical_equal"] is True
    assert report["project_io"]["format_version"] == "1.2"
    assert report["project_io"]["motion_compositions_present"] is True
    assert report["playback"]["decoded_frames"] == 2
    assert report["opengl_preview"]["ok"] is True
    assert report["boundaries"]["user_project_mutated"] is False
