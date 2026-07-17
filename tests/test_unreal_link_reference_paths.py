from __future__ import annotations

from app.unreal_link_reference_paths import (
    DEFAULT_UASSET_INSPECTOR_ROOT,
    DEFAULT_UE_ENGINE_ROOT,
    INTERNAL_CUE4PARSE_ROOT,
    UASSET_INSPECTOR_ENV,
    UE_ENGINE_ENV,
    format_unreal_link_reference_report,
    unreal_link_reference_report,
    unreal_link_reference_roots,
)


def test_unreal_link_reference_defaults_are_registered_for_ai_development() -> None:
    roots = unreal_link_reference_roots()

    assert roots["uasset_inspector"].path == DEFAULT_UASSET_INSPECTOR_ROOT
    assert roots["ue_58"].path == DEFAULT_UE_ENGINE_ROOT
    assert DEFAULT_UASSET_INSPECTOR_ROOT.as_posix() == "D:/Pupg_workspace/ToolsStandalone/UAssetInspector"
    assert DEFAULT_UE_ENGINE_ROOT.as_posix() == "D:/UE_5.8"
    assert "UAssetInspector.sln" in roots["uasset_inspector"].required_children
    assert "Engine/Binaries/Win64/UnrealEditor.exe" in roots["ue_58"].required_children
    assert roots["cue4parse_internal"].path == INTERNAL_CUE4PARSE_ROOT
    assert "CUE4Parse/CUE4Parse.csproj" in roots["cue4parse_internal"].required_children


def test_unreal_link_reference_env_overrides(monkeypatch, tmp_path) -> None:
    custom_tool = tmp_path / "tool"
    custom_engine = tmp_path / "engine"
    monkeypatch.setenv(UASSET_INSPECTOR_ENV, str(custom_tool))
    monkeypatch.setenv(UE_ENGINE_ENV, str(custom_engine))

    roots = unreal_link_reference_roots()

    assert roots["uasset_inspector"].path == custom_tool
    assert roots["ue_58"].path == custom_engine


def test_unreal_link_reference_report_is_human_readable() -> None:
    report = unreal_link_reference_report()
    text = format_unreal_link_reference_report()

    assert "CUE4Parse is vendored" in report["note"]
    assert "D:/UE_5.8" in text
    assert "CUE4Parse internal bridge runtime" in text
    assert UASSET_INSPECTOR_ENV in text
    assert UE_ENGINE_ENV in text


def test_unreal_link_reference_status_action_is_ownerless() -> None:
    from app.actions import build_default_action_registry

    registry = build_default_action_registry()
    result = registry.execute("unreal.link.reference_status").to_dict()
    spec = registry.get_action_schema("unreal.link.reference_status")

    assert result["ok"] is True
    assert result["changed"] is False
    assert spec["requires_owner"] is False
    assert result["result"]["roots"]["uasset_inspector"]["path"] == (
        "D:/Pupg_workspace/ToolsStandalone/UAssetInspector"
    )
    assert result["result"]["roots"]["ue_58"]["path"] == "D:/UE_5.8"
    assert result["result"]["roots"]["cue4parse_internal"]["path"] == INTERNAL_CUE4PARSE_ROOT.as_posix()


def test_unreal_engine_project_file_dialog_uses_uproject_filter(tmp_path) -> None:
    from app.video_editor_unreal_workflow import (
        UNREAL_ENGINE_PROJECT_DIALOG_TITLE,
        UNREAL_ENGINE_PROJECT_FILTER,
        select_unreal_engine_project_file,
    )

    selected = tmp_path / "SampleProject.uproject"
    calls = []

    def fake_dialog(parent, title: str, initial_dir: str, file_filter: str):
        calls.append(
            {
                "parent": parent,
                "title": title,
                "initial_dir": initial_dir,
                "file_filter": file_filter,
            }
        )
        return str(selected), file_filter

    result = select_unreal_engine_project_file(
        None,
        initial_dir=str(tmp_path),
        dialog_getter=fake_dialog,
    )

    assert result == selected
    assert calls == [
        {
            "parent": None,
            "title": "Open UnrealEngine5 project",
            "initial_dir": str(tmp_path),
            "file_filter": "Unreal Engine 5 Project (*.uproject);;All Files (*)",
        }
    ]
    assert UNREAL_ENGINE_PROJECT_DIALOG_TITLE == "Open UnrealEngine5 project"
    assert "*.uproject" in UNREAL_ENGINE_PROJECT_FILTER


def test_connected_unreal_engine_project_can_start_without_reopening(tmp_path) -> None:
    from app.video_editor_unreal_workflow import (
        UNREAL_ENGINE_OPEN_PROJECT_LABEL,
        UNREAL_ENGINE_START_CONNECTED_LABEL,
        connected_unreal_engine_project_path,
        start_unreal_engine_link_with_project,
    )

    class Owner:
        pass

    owner = Owner()
    project = tmp_path / "Connected.uproject"
    setattr(owner, "_unreal_engine_project_path", str(project))

    assert connected_unreal_engine_project_path(owner) == project
    result = start_unreal_engine_link_with_project(owner, project)

    assert result == {"status": "connected", "project_path": str(project)}
    assert getattr(owner, "_unreal_engine_project_path") == str(project)
    assert UNREAL_ENGINE_START_CONNECTED_LABEL == "Start with connected project"
    assert UNREAL_ENGINE_OPEN_PROJECT_LABEL == "Open UnrealEngine5 project"


def test_unreal_engine_link_start_mode_dialog_exposes_start_and_open(tmp_path) -> None:
    from app.video_editor_unreal_workflow import (
        UNREAL_ENGINE_OPEN_PROJECT_LABEL,
        UNREAL_ENGINE_START_CONNECTED_LABEL,
        choose_unreal_engine_link_start_mode,
    )

    class FakeButton:
        def __init__(self, label):
            self.label = label

    class FakeBox:
        def __init__(self, parent):
            self.parent = parent
            self.buttons = []
            self.clicked = None
            self.window_title = ""
            self.text = ""
            self.info = ""

        def setIcon(self, _icon):
            pass

        def setWindowTitle(self, title):
            self.window_title = title

        def setText(self, text):
            self.text = text

        def setInformativeText(self, text):
            self.info = text

        def addButton(self, label, _role=None):
            button = FakeButton(str(label))
            self.buttons.append(button)
            if button.label == UNREAL_ENGINE_START_CONNECTED_LABEL:
                self.clicked = button
            return button

        def setDefaultButton(self, button):
            self.default = button

        def exec(self):
            return 0

        def clickedButton(self):
            return self.clicked

    boxes = []

    def factory(parent):
        box = FakeBox(parent)
        boxes.append(box)
        return box

    choice = choose_unreal_engine_link_start_mode(
        None,
        tmp_path / "Connected.uproject",
        message_box_factory=factory,
    )

    assert choice == "start"
    assert boxes[0].window_title == "Unreal Engine Link"
    labels = [button.label for button in boxes[0].buttons]
    assert UNREAL_ENGINE_START_CONNECTED_LABEL in labels
    assert UNREAL_ENGINE_OPEN_PROJECT_LABEL in labels
