# TigerCapture Agent Rules

These rules are for AI coding agents working in this repository.

## Git Remote Boundary

This repository uses separate remotes for private source and public
distribution.

- `source` / `kuoungseok/tigercapture-src` is the private source repository.
  Push source branches, feature branches, WIP checkpoints, source tags, and
  source PR work only to `source` unless the user explicitly says otherwise.
- `origin` / `kuoungseok/tigercapture` is the public distribution repository.
  Do not push full source, source checkpoints, feature branches, or source PRs
  to `origin`.
- `origin` should contain only distribution-safe branches, tags, docs, release
  metadata, installers, or packaged artifacts. Use the dedicated `release`
  branch or a sanitized release/export workflow for distribution updates.
- Never make `origin` public, create public release tags, or publish release
  artifacts until verifying that no source commits, source branches, source
  tags, or accidental PR refs would be exposed.
- If source content is accidentally pushed to `origin`, stop and report it
  immediately. Do not continue by changing repository visibility or creating
  more public-facing refs.
- Local Git must use the repository hook path `.githooks` and default pushes
  should go to `source`:

  ```powershell
  git config core.hooksPath .githooks
  git config remote.pushDefault source
  ```

  The tracked `.githooks/pre-push` guard blocks source branches, WIP branches,
  source tags, and source-tree refs from being pushed to `origin`. Do not bypass
  this guard except for an explicitly requested emergency cleanup.

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
