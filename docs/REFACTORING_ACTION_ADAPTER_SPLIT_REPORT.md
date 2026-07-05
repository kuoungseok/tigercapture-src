# Action/Adapter/Editor Window Refactoring Report

Date: 2026-07-01

## Summary

The Python Action System and the first editor-window UI surfaces were split so
future AI/MCP/editor automation and VTuber/Screen Studio UI work do not keep
growing `app/actions/registry.py`, `app/actions/editor_adapter.py`, and
`app/video_editor_window.py`. Public action IDs and MCP methods were preserved.

## What Changed

- `app/actions/registry.py`
  - Now a thin orchestrator for duplicate-id checks, dry-run/destructive gates,
    sequence execution, and namespace registration.
  - Current size: 242 lines.
  - New action registrations must go through namespace modules.

- `app/actions/editor_adapter.py`
  - Now only owns owner binding, snapshot, app status, and media summary.
  - Current size: 76 lines.
  - It should not regain timeline/editing/VTuber/creative helper logic.

- `app/video_editor_window.py`
  - First UI extraction is active.
  - Current size: 48,819 lines, down from 50,933 lines at the start of this
    pass.
  - Popout and VTuber Studio windows were moved out of the main editor module.
  - Screen Studio Auto Polish dialog was moved out of the main editor module.

- Public adapter behavior was split into domain mixins:
  - `app/actions/editor_adapter_timeline.py`
    - timeline/media/source-monitor/record-monitor/marker/selection methods
  - `app/actions/editor_adapter_editing.py`
    - clip edit, linked edit, audio, creative, actor, capture, review methods
  - `app/actions/editor_adapter_vtuber.py`
    - VTuber, broadcast, VSeeFace, Performance Source, Avatar Target methods
  - `app/actions/editor_adapter_nle.py`
    - NLE, project bin, Source/Record workbench, multicam, readiness methods

- Private helper seams were split into focused helper mixins:
  - `app/actions/editor_adapter_core_helpers.py`
    - capture target, GIF fallback, owner/media registration, legacy track
      creation, audio UI sync helpers
  - `app/actions/editor_adapter_timeline_helpers.py`
    - video/audio track lookup, markers, edit points, gaps, selection,
      clipboard, linked audio, trim/ripple/slide helpers
  - `app/actions/editor_adapter_object_helpers.py`
    - typography actor lookup, actor clip lookup, node graph helpers, editor
      refresh/change notification helpers

- Editor-window UI surfaces were split into focused modules:
  - `app/video_editor_popouts.py`
    - `PreviewPopoutWindow`
    - `ColorPopoutWindow`
    - `TimelinePopoutWindow`
    - `SubtitlePopoutWindow`
    - `EffectsLibraryPopoutWindow`
    - `MediaPoolPopoutWindow`
    - `WorkbenchPopoutWindow`
    - `VTuberBroadcastStudioWindow`
    - `_BroadcastProjectAudioBusMixdownThread`
  - `app/video_editor_screenstudio_dialogs.py`
    - `ScreenStudioPolishDialog`

- Specs/TODO were updated:
  - `docs/SPEC_REPO_MAINTAINABILITY.md`
  - `docs/SPEC_PYTHON_ACTION_SYSTEM.md`
  - `SPEC.md`
  - `TODO.md`

## Public Contract Preserved

- MCP still exposes the same safe action methods:
  - `tigercapture_list_actions`
  - `tigercapture_get_action_schema`
  - `tigercapture_preview_action`
  - `tigercapture_execute_action`
  - `tigercapture_execute_sequence`
- Arbitrary Python and shell remain blocked.
- Destructive actions still require `confirm_destructive=true`.
- Action IDs are stable.
- Latest MCP QA reports `action_count: 200`.

## Validation

Commands run:

```powershell
.\.venv\Scripts\python.exe -m py_compile app/actions/editor_adapter.py app/actions/editor_adapter_core_helpers.py app/actions/editor_adapter_timeline_helpers.py app/actions/editor_adapter_object_helpers.py app/actions/registry.py
```

```powershell
.\.venv\Scripts\python.exe -m py_compile app/video_editor_window.py app/video_editor_popouts.py app/video_editor_screenstudio_dialogs.py
```

```powershell
.\.venv\Scripts\python.exe -c "import app.video_editor_window, app.video_editor_popouts, app.video_editor_screenstudio_dialogs; print('imports-ok')"
```

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_python_action_system.py tests\test_automation_bridge.py tests\test_automation_mcp.py tests\test_automation_commands.py tests\test_nle_timeline_stress.py tests\test_nle_readiness.py tests\test_vtuber_performance_source.py tests\test_vtuber_broadcast_studio_layout.py tests\test_vseeface_bridge.py tests\test_vseeface_bridge_action_tool.py tests\test_vseeface_bridge_status_tool.py tests\test_broadcast_virtual_camera.py tests\test_broadcast_output.py tests\test_broadcast_capture_backend.py
```

Result:

- `177 passed`

Additional editor-window split validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_vtuber_performance_source.py tests\test_vtuber_broadcast_studio_layout.py tests\test_vseeface_bridge.py tests\test_broadcast_virtual_camera.py tests\test_broadcast_output.py tests\test_broadcast_capture_backend.py tests\test_screenstudio_parity_gap.py tests\test_python_action_system.py tests\test_automation_bridge.py tests\test_automation_mcp.py
```

Result:

- `181 passed`

```powershell
.\.venv\Scripts\python.exe tools\qa_automation_mcp.py
```

Result:

- `ok: true`
- `score: 100`
- `action_count: 200`
- Report: `debugCapture/automation_mcp_qa.json`

## Rules For Other Threads

- Do not add new domain behavior directly to `app/actions/registry.py`.
  Add a focused `*_namespace.py` helper or extend the existing matching
  namespace.
- Do not add new editor/timeline/actor logic directly to
  `app/actions/editor_adapter.py`.
  Add it to the matching adapter mixin or helper mixin.
- Do not add new detached preview/popout/VTuber Studio window code directly to
  `app/video_editor_window.py`.
  Use `app/video_editor_popouts.py` unless the code truly belongs to the main
  editor object.
- Do not add new Screen Studio Auto Polish dialog code directly to
  `app/video_editor_window.py`.
  Use `app/video_editor_screenstudio_dialogs.py`.
- Keep public action IDs stable unless a migration is explicitly documented.
- Do not expose private `VideoEditorWindow` methods directly through MCP or AI.
  Route through registered Python Actions.
- Keep dry-run/preview behavior for mutating actions.
- Keep destructive actions behind explicit confirmation.
- Run the validation bundle above after changing action registration or adapter
  behavior.

## Remaining Maintainability Work

- `app/video_editor_window.py` is still the largest risk even after this first
  UI extraction. Next splits should target top bar command groups,
  media/workbench docks, preview/transport, timeline palette, right inspector,
  AI command dock, preset browser panels, and audio/editor panels.
- AR/PBR action registration still needs a dedicated namespace if more 3D
  automation actions are added.
- Worktree hygiene is still a release risk. There are many modified/untracked
  files from parallel product work, so release branching should happen only
  after the owner selects the intended change set.
