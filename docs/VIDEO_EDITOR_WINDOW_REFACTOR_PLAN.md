# Video Editor Window Refactor Plan

Date: 2026-07-05

Scope: `app/video_editor_window.py` refactoring policy and handoff notes for the
current 10-agent split. This document is intentionally a refactoring contract,
not a request to change behavior.

## Goal

`app/video_editor_window.py` must keep shrinking from a feature monolith into a
thin editor shell. New code should land in focused modules, while old imports
and editor behavior keep working through compatibility wrappers until call sites
are migrated deliberately.

## 10-Agent Refactoring Principles

1. One agent owns one bounded surface. Do not let two agents edit the same UI
   class or behavior path in the same pass.
2. Preserve behavior first. A split is valid only when public imports, runtime
   behavior, action IDs, and project file data remain compatible.
3. Keep `video_editor_window.py` as a shell. It may compose panels, own editor
   state, and expose temporary wrappers; it should not regain extracted domain
   logic.
4. Prefer pure modules for model logic. Timeline data, payload parsing, media
   routing, and render math should avoid Qt when possible.
5. Extract UI by surface, not by convenience. Dialogs, popouts, palette chrome,
   preset browser widgets, command controls, and workers each get their own
   module boundary.
6. Avoid circular imports. Extracted modules must not import
   `VideoEditorWindow`; pass an owner object, callback, signal, or plain data
   instead.
7. Keep wrappers boring. Compatibility methods should delegate, import, or
   re-export; they must not duplicate the moved implementation.
8. Validate near the boundary. A module split needs syntax/import checks plus
   the smallest behavior tests that cover that surface.
9. Document the ownership transfer. Every extracted module should have a clear
   responsibility and a known compatibility path.
10. Do not clean unrelated worktree changes. Refactor agents must leave
    unrelated modified or untracked files untouched.

## Module Split Order

1. Baseline and inventory: record current imports, public symbols used by tests,
   and user-facing behaviors before moving code.
2. Pure data/model helpers: move timeline dataclasses, clip math, zoom helpers,
   payload parsers, and media-routing helpers before moving UI that depends on
   them.
3. Legacy compatibility data: keep `VideoTrack` and legacy clip sync helpers in
   a dedicated module while the UI still depends on old track semantics.
4. Shared style/layout primitives: extract constants, QSS builders, section
   chrome, tile styling, and layout specs before presenter widgets.
5. Passive UI widgets: extract cards, swatches, preset browser widgets, text
   lane rows, and actor/evidence panels that can be constructed independently.
6. Background workers and IO helpers: extract thumbnailing, proxy generation,
   probes, cache helpers, and any long-running thread class.
7. Detached surfaces: extract preview/timeline/color/media/workbench popouts,
   VTuber Studio windows, and modal dialogs.
8. Command/control presenters: extract command bar helpers, export menus, AI
   command dock controls, and small controller functions that operate on owner
   state.
9. High-risk editor methods: move timeline mutation, preview composition, audio
   editing, color workbench, and export wiring only after targeted tests exist.
10. Final shell cleanup: after direct imports migrate, remove obsolete wrappers
    in small passes guarded by `rg` checks and compatibility tests.

## Compatibility Wrapper Rules

- `app.video_editor_window` remains the compatibility import surface for old
  tests, tools, and app entry points.
- When a symbol moves, re-export it from `video_editor_window.py` with the same
  name until all call sites are migrated. Use direct imports with `# noqa: F401`
  where the re-export is intentional.
- When a `VideoEditorWindow` method moves to a helper, leave a thin method on
  `VideoEditorWindow` that delegates to the helper and preserves arguments,
  return values, status messages, and exceptions.
- New code should import from the extracted module directly. Only legacy code
  should add new dependencies on `app.video_editor_window`.
- Extracted modules must not import `VideoEditorWindow`; use owner callbacks,
  signal connections, or plain helper functions.
- Do not rename public constants, MIME types, dataclasses, action IDs, or project
  schema fields during a split.
- A wrapper can be removed only after `rg` shows no remaining old import/method
  dependency and the focused compatibility tests pass.

## Test Priority

1. Syntax/import gate:
   `.\.venv\Scripts\python.exe -m py_compile app\video_editor_window.py`
   plus every extracted module touched in the pass.
2. Import compatibility gate:
   import `app.video_editor_window` and any moved symbols still re-exported from
   it.
3. Pure model tests:
   `tests\test_timeline_model.py`, timeline payload/cache tests, and any tests
   covering moved dataclasses or helper math.
4. Compatibility-heavy editor tests:
   `tests\test_media_pool_timeline_drop.py`,
   `tests\test_render_queue_relink_presets.py`,
   `tests\test_project_player.py`, and `tests\test_window_move_guard.py`.
5. Surface-specific tests:
   run color/audio, preset browser, actor, VTuber, broadcast, or Screen Studio
   tests matching the module being split.
6. Action/MCP regression:
   `tests\test_python_action_system.py`, `tests\test_automation_bridge.py`,
   `tests\test_automation_mcp.py`, and `tests\test_automation_commands.py` when
   editor methods used by actions move.
7. UI smoke:
   `tools\qa_editor_e2e_smoke.py` or the relevant `tools\qa_ui_renewal_*.py`
   capture when layout, popout, dock, or visual styling code moves.

## Prohibited Changes

- Do not add new feature logic directly to `app/video_editor_window.py` unless
  it is temporary composition glue for an extracted module.
- Do not duplicate moved implementations in both the wrapper and the extracted
  module.
- Do not let extracted modules import `app.video_editor_window`.
- Do not change public Python Action IDs, MCP method names, destructive-action
  gates, or project file schema as part of a UI split.
- Do not expose private `VideoEditorWindow` methods directly through MCP or AI.
- Do not mix broad visual redesign, formatting churn, or unrelated cleanup into
  a refactor pass.
- Do not rely on screenshot-only validation for model or action behavior.
- Do not remove compatibility wrappers based on intuition; prove the old surface
  is unused with search and tests.

## Modules Split Out In This Refactor

Current `video_editor_window.py` compatibility imports and adjacent split
modules show these ownership boundaries:

- `app/video_editor_actor_evidence.py`: Live2D and AR/PBR evidence cards.
- `app/video_editor_actor_library.py`: actor source/library panel widgets.
- `app/video_editor_ai_command_controller.py`: AI command dock show/hide,
  popout, restore, and owner-driven controller helpers.
- `app/video_editor_ai_command_dock.py`: AI command dock sizing constants and
  stylesheet.
- `app/video_editor_audio_style.py`: audio mixer/editor colors and QSS.
- `app/video_editor_command_bar.py`: command button sizing, breakpoints, lazy
  menus, and existing-menu display helpers.
- `app/video_editor_export_controls.py`: export quality/format/resolution/FPS
  menu builders and label refresh helpers.
- `app/video_editor_layout_specs.py`: main dock dimensions, splitter QSS, and
  scroll-area QSS builders.
- `app/video_editor_media_proxy.py`: proxy path/state helpers, proxy deletion,
  proxy generation, high-resolution probe, and `ProxyGeneratorThread`.
- `app/video_editor_popouts.py`: detached preview, color, timeline, subtitle,
  effects, media pool, workbench, section popout, VTuber Broadcast Studio, and
  broadcast audio mixdown thread.
- `app/video_editor_preset_browser_style.py`: preset browser tile metrics,
  icons, palette button style, search/combo/menu QSS.
- `app/video_editor_preset_browser_widgets.py`: preset scroll grid, inspector,
  target strip, preview swatch, and preset browser widget.
- `app/video_editor_preset_cards.py`: transition/title/effect/editor preset
  MIME types, preset preview rendering helpers, and preset card/panel widgets.
- `app/video_editor_screenstudio_dialogs.py`: Screen Studio Auto Polish dialog.
- `app/video_editor_section_chrome.py`: section headers, popout header buttons,
  collapsible headers, disclosure state, and host height handling.
- `app/video_editor_text_lane.py`: text lane row widget.
- `app/video_editor_thumbnailing.py`: video duration probing,
  `ThumbnailExtractor`, and thumbnail sizing constants.
- `app/video_editor_timeline_palette.py`: timeline cursor role mapping and tile
  palette configuration.
- `app/video_editor_window_style.py`: editor-wide extra QSS and media-pool
  reference QSS.

Related foundation modules that already act as compatibility targets:

- `app/effect_cards.py`: drag-source fade, speed, zoom, typography, Live2D, and
  Spine effect cards plus MIME constants.
- `app/timeline_model.py`: timeline dataclasses, clip-list model, zoom helpers,
  and model-level timeline operations.
- `app/video_track_legacy.py`: legacy `VideoTrack` dataclass and clip sync
  helpers re-exported by `video_editor_window.py`.
- `app/timeline_cursor.py`: timeline tool cursor helper.
- `app/timeline_drop_guides.py`: drag/drop guide labels, widths, and segment
  helpers.
- `app/timeline_drop_payloads.py`: effect, transition, speed, fade, zoom, title,
  text, and editor preset payload parsers.
- `app/timeline_thumbnail_cache.py`: timeline thumbnail cache root, load,
  prepare, and store helpers.
- `app/media_asset_routing.py`: media-pool MIME path routing for timeline,
  AR/PBR, MMD, VRM, and performance-source drops.
- `app/qt_pixmap_painting.py`: shared pixmap cover painting helper.
- `app/typo_layout.py`: typography measurement, fill color, opacity, pivot, and
  background rectangle helpers.

## Next Split Targets

- Preview composition and placeholder/recovery logic.
- Timeline row mutation and drag/drop editing methods.
- Audio editor/mixer panels still embedded in the window module.
- Color grading workbench and comparison controls.
- Export dialog orchestration beyond simple menu controls.
- Command palette state and command catalog construction.
- Remaining modal dialogs and tool-specific mini widgets still declared inside
  `video_editor_window.py`.
