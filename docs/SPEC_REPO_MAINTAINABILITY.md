# Tiger Studio Repository Maintainability Contract

Date: 2026-07-01

This document records the current structural risk and the conservative path out
of it. It is intentionally not a broad refactor request.

## Current Risks

- `app/video_editor_window.py` is a very large integration module. It still owns
  too much UI wiring for timeline, preview, AI, actors, presets, export, QA, and
  workbench entry points.
- `app/actions/registry.py` is now a thin action execution and registration
  orchestrator. `app/actions/editor_adapter.py` has been reduced to
  snapshot/status/app-summary behavior. Public adapter behavior and private
  helper seams live in focused action mixin modules.
- The working tree can contain many unrelated product changes at once. This
  makes review, regression isolation, and release branching difficult.
- Packaging must explicitly include runtime resources used by color/LUT,
  localization, icon, and native helper paths.
- Root editor/lint/line-ending policy must remain explicit to avoid LF/CRLF
  churn in large Windows-heavy changes.

## Required Guardrails

- Do not expose private `VideoEditorWindow` methods directly through MCP or AI.
  All automation must continue through registered Python Actions.
- New action namespaces should be implemented in small modules before being
  registered in the central registry.
- New UI surfaces should prefer narrow presenter/view-model helpers instead of
  adding more business logic to `video_editor_window.py`.
- VTuber Studio, detached dock, and popout UI must stay in
  `app/video_editor_popouts.py`; Broadcast Evidence copy/defaults/payload
  helpers must stay in `app/broadcast_evidence_ui.py`. The canonical product
  contract is `docs/SPEC_VTUBER_STUDIO_BROADCAST.md`.
- New package resources must have a QA check, not only a PyInstaller spec edit.
- Large refactors must preserve current action IDs and project file schema.

## Recommended Split Order

1. Move Source/Record, Project Bin, Multicam, NLE readiness, and QA-entry action
   registration into namespace registration helpers.
   - Status: Source/Record, Project Bin, Multicam, NLE readiness, real corpus,
     timeline fuzzer, and undo health registration now live in
     `app/actions/nle_namespace.py` while preserving public action IDs.
2. Move VTuber/VSeeFace bridge registration into VTuber namespace helpers.
   - Status: VSeeFace bridge, install, start/probe, sidecar, capture backend,
     VRM0 avatar, framing, tracking-input, shared VTuber Studio, Avatar Target,
     VRM pose-stream, Performance Source, and Program Output contract
     registration now live in `app/actions/vtuber_namespace.py` while preserving
     public action IDs.
3. Move AI panel/command registration into an `app/actions/ai_actions.py`
   namespace helper when provider-backed action registration grows beyond the
   current command router.
4. Move remaining actor/Live2D/Spine actions into actor namespace helpers.
   - Status: Live2D/Spine actor add, transform, keyframes, and Live2D
     Performance Source retargeting registration now live in
     `app/actions/actor_namespace.py` while preserving public action IDs.
5. Move broadcast/live-output actions into a separate namespace helper.
   - Status: Live Target, troubleshooting, broadcast release readiness, manual
     platform evidence, and virtual-camera/OBS bridge registration now live in
     `app/actions/broadcast_namespace.py` while preserving public action IDs.
6. Move evidence/review capture actions into a separate namespace helper.
   - Status: UI focus, screenshot, GIF capture, and review scenario registration
     now live in `app/actions/evidence_namespace.py` while preserving public
     action IDs.
7. Move creative layer actions into a separate namespace helper.
   - Status: creative readiness, preset catalog, clip filters/color grades,
     transitions, node graph, and typography registration now live in
     `app/actions/creative_namespace.py` while preserving public action IDs.
8. Move audio edit/mix actions into a separate namespace helper.
   - Status: video-audio extraction, audio clip split/trim/delete/gain, and
     audio track mix registration now live in `app/actions/audio_namespace.py`
     while preserving public action IDs.
9. Move track focus and selection actions into a separate namespace helper.
   - Status: track reorder/state/lock/mute/rename/select, clip selection,
     timeline select-all, and selection set/clear/range registration now live in
     `app/actions/track_selection_namespace.py` while preserving public action
     IDs.
10. Move media import, base track add/remove, marker, and timeline core actions
    into separate namespace helpers.
    - Status: media pool import, import-to-timeline, and track add/remove
      registration now live in `app/actions/media_track_namespace.py`; timeline
      marker registration now
      lives in `app/actions/marker_namespace.py`; transport, In/Out, edit-point
      navigation, bounded playback, zoom, snap, gap, and history registration
      now live in `app/actions/timeline_core_namespace.py`.
11. Move clip edit and selection movement actions into separate namespace
    helpers.
    - Status: split, trim, range delete, lift/extract, clipboard insert/
      overwrite, 3-point edit, linked move, slip/roll/slide, speed, and fade
      registration now live in `app/actions/clip_edit_namespace.py`; selection
      nudge, align, distribute, snap, and ripple-delete registration now live in
      `app/actions/selection_movement_namespace.py`.
12. Move read-only status and Source/Record monitor actions into separate
    namespace helpers.
    - Status: app/project/media/timeline/selection summary registration now
      lives in `app/actions/readonly_namespace.py`; Source monitor and Record
      monitor state/load/In/Out/clear registration now lives in
      `app/actions/source_record_monitor_namespace.py`. The central action
      registry is now reduced to about 200 lines of registration orchestration
      and execution safety.
13. Move AR/PBR/3D actions into a separate namespace helper.
14. Split `app/actions/editor_adapter.py` by domain facade.
    - Status: adapter split is active. NLE/project-bin/multicam adapter
      methods live in `app/actions/editor_adapter_nle.py`; VTuber, broadcast,
      VSeeFace, Performance Source, and Avatar Target adapter methods live in
      `app/actions/editor_adapter_vtuber.py`; timeline/media/source-monitor/
      marker/selection public methods live in `app/actions/editor_adapter_timeline.py`;
      clip edit, linked edit, audio, creative, actor, capture, and review public
      methods live in `app/actions/editor_adapter_editing.py`.
    - Status: private helper split is active. Capture/owner/media/UI helpers
      live in `app/actions/editor_adapter_core_helpers.py`; timeline lookup,
      selection, clipboard, linked audio, trim, and gap helpers live in
      `app/actions/editor_adapter_timeline_helpers.py`; actor/text/node graph
      and editor refresh helpers live in
      `app/actions/editor_adapter_object_helpers.py`. The remaining
      `editor_adapter.py` file is reduced to snapshot/status methods.
15. Extract `video_editor_window.py` UI construction into presenter modules.
   - Status: first UI extraction is active. Detached preview/dock popouts and
     the shared VTuber Studio surface live in `app/video_editor_popouts.py`.
     Screen Studio Auto Polish lives in `app/video_editor_screenstudio_dialogs.py`.
   - Remaining targets: top bar command groups, media/workbench docks,
     preview/transport, timeline palette, right inspector, AI command dock,
     preset browser panels, and audio/editor panels.

## New Baseline Checks

- `.gitattributes`, `.editorconfig`, `ruff.toml`, and `pyproject.toml` define
  line-ending and tooling expectations.
- `tools/qa_packaging_resources.py` verifies PyInstaller resource contracts for
  locales, icon, LUT files, and imageio-ffmpeg metadata.
