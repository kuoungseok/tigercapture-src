from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEO_EDITOR_WINDOW = ROOT / "app" / "video_editor_window.py"


def _module_ast() -> ast.Module:
    return ast.parse(VIDEO_EDITOR_WINDOW.read_text(encoding="utf-8"))


def test_video_editor_window_stays_a_facade() -> None:
    lines = VIDEO_EDITOR_WINDOW.read_text(encoding="utf-8").splitlines()

    assert len(lines) <= 180, (
        "app/video_editor_window.py is a compatibility facade. "
        "Move new editor feature code into a focused video_editor_* module."
    )


def test_video_editor_window_does_not_define_feature_classes() -> None:
    tree = _module_ast()
    classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]

    assert classes == [], (
        "Do not define editor UI/feature classes in app/video_editor_window.py. "
        "Define them in a focused module and re-export them if compatibility is needed."
    )


def test_video_editor_window_only_keeps_tiny_compat_helpers() -> None:
    tree = _module_ast()
    allowed = {"_format_ms", "_format_speed", "_format_size"}
    functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]

    assert set(functions) <= allowed, (
        "app/video_editor_window.py may only keep tiny compatibility helpers. "
        "Move feature handlers/builders/workflows into focused modules."
    )


def test_video_editor_window_does_not_bind_feature_methods() -> None:
    tree = _module_ast()
    suspicious_assignments: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "VideoEditorWindow"
            ):
                suspicious_assignments.append(target.attr)

    assert suspicious_assignments == [], (
        "Bind legacy VideoEditorWindow methods in app/video_editor_window_delegates.py, "
        "not in app/video_editor_window.py."
    )
