# TigerCapture Agent Rules

These rules are for AI coding agents working in this repository.

## Main Editor Boundary

`app/video_editor_window.py` is a compatibility facade. Do not add new feature
logic, UI classes, dialogs, long QSS blocks, workflow methods, media handlers,
or timeline behavior there.

Allowed in `app/video_editor_window.py`:

- imports and re-exports that preserve older public import paths
- `__all__`
- tiny compatibility helpers such as `_format_ms`, `_format_speed`, `_format_size`

When adding editor features, choose or create a focused module instead:

- editor startup/state: `app/video_editor_window_initializer.py`,
  `app/video_editor_window_core.py`
- method binding/legacy names: `app/video_editor_window_delegates.py`
- UI layout sections: `app/video_editor_ui_*.py`
- timeline operations/view/drag/layout: `app/video_editor_timeline_*.py`
- media import/proxy/thumbnailing: `app/video_editor_media_*.py`,
  `app/media_pool*.py`
- context menus: `app/video_editor_context_menu_*.py`
- player/preview bridge: `app/video_editor_player_bridge.py`,
  `app/video_editor_preview_*.py`
- export/render queue: `app/video_editor_export_*.py`,
  `app/video_editor_render_queue_bridge.py`
- color tools: `app/video_editor_color_*.py`, `app/color_*.py`
- audio tools: `app/video_editor_audio_*.py`, `app/audio_*.py`
- actor/Live2D/Spine/MMD/AR-PBR workflows:
  `app/video_editor_actor_*.py`, `app/video_editor_live2d_workflow.py`,
  `app/video_editor_mmd_workflow.py`, `app/ar_pbr/*`, `app/mmd/*`
- reusable action/MCP surfaces: `app/actions/*`, `app/automation_*.py`

If no suitable module exists, create a new focused module named after the
feature area. Wire it into the editor through `video_editor_window_delegates.py`,
the relevant controller/workflow module, or the initializer. Keep the facade
small.

## Refactor Guard

Run the architecture guard after editor-facing changes:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_editor_architecture_rules.py -q
```

If the guard fails because a real feature was added to `video_editor_window.py`,
move that feature into a focused module instead of raising the limit.
