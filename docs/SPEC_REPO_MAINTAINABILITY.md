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
- AR/PBR preview and QA sample defaults must not depend on `debugCapture`.
  Durable sample assets live under `sample_assets` or `external/assets`; generated
  `debugCapture` scenes are allowed only as temporary fallback outputs.
- Source media, OpenSeeFace CSVs, descriptors, models, avatars, and other
  required input defaults must not point at `debugCapture`. Use explicit CLI
  arguments, `sample_assets`, or `external/assets`; keep `debugCapture` for
  regenerated reports, proof images, logs, and temporary cache output.

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
     platform evidence, and virtual-camera/OBS bridge registration stay behind
     the `app/actions/broadcast_namespace.py` facade while preserving public
     action IDs. Live Target schemas live in
     `app/actions/broadcast_live_target_namespace.py`; platform evidence and
     readiness schemas live in `app/actions/broadcast_evidence_namespace.py`;
     virtual-camera/OBS bridge schemas live in
     `app/actions/broadcast_virtual_camera_namespace.py`.
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
    - Status: preview camera, depth-view, lighting/material/surface, and
      viewport-gizmo registration now lives behind the
      `app/actions/ar_pbr_namespace.py` facade. Preview/depth/surface schemas
      live in `app/actions/ar_pbr_preview_namespace.py`; gizmo schemas live in
      `app/actions/ar_pbr_gizmo_namespace.py`.
14. Split `app/actions/editor_adapter.py` by domain facade.
    - Status: adapter split is active. `app/actions/editor_adapter_nle.py` is a
      facade that composes focused mixins. Source/Record methods live in
      `app/actions/editor_adapter_nle_source_record.py`; project-bin methods
      live in `app/actions/editor_adapter_nle_project_bin.py`; NLE readiness,
      evidence, and real-project corpus methods live in
      `app/actions/editor_adapter_nle_readiness.py`; multicam methods live in
      `app/actions/editor_adapter_nle_multicam.py`; magnetic storyline,
      connected clip, and role-lane methods live in
      `app/actions/editor_adapter_nle_storyline.py`; Final Cut-style
      audition/take methods live in
      `app/actions/editor_adapter_nle_auditions.py`; Final Cut-style visual
      feedback methods live in `app/actions/editor_adapter_nle_visual.py`;
      timeline visual paint helpers live in `app/timeline_nle_visual_overlay.py`
      and are consumed by `app/timeline_track_row_paint.py` rather than being
      added to `app/video_editor_window.py`; role-focus propagation stays in
      `app/actions/editor_adapter_nle_storyline.py`, `TrackRow`'s small
      `set_focused_clip_role(...)` setter, and the compact timeline UI glue in
      `app/video_editor_nle_role_panel.py` /
      `app/video_editor_nle_role_workflow.py`; cross-row connected-clip
      viewport drawing lives in `app/timeline_connected_anchor_overlay_widget.py`;
      audition card models live in `app/nle_audition_visuals.py` and the
      Qt picker remains in `app/video_editor_nle_audition_workflow.py`;
      VTuber, broadcast,
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
    - Status: AR/PBR adapter split is active. `app/actions/editor_adapter_ar_pbr.py`
      is a facade that composes focused mixins. Shared preview/window/track
      helpers live in `app/actions/editor_adapter_ar_pbr_base.py`; main-preview
      diagnostics and depth-view actions live in
      `app/actions/editor_adapter_ar_pbr_depth.py`; preview camera actions live
      in `app/actions/editor_adapter_ar_pbr_preview.py`; lighting/material/
      surface actions live in `app/actions/editor_adapter_ar_pbr_settings.py`;
      viewport-gizmo actions live in `app/actions/editor_adapter_ar_pbr_gizmo.py`.
15. Extract `video_editor_window.py` UI construction into presenter modules.
   - Status: first UI extraction is active. Detached preview/dock popouts and
     the shared VTuber Studio surface live in `app/video_editor_popouts.py`.
     Screen Studio Auto Polish lives in `app/video_editor_screenstudio_dialogs.py`.
   - Status: compatibility delegate installation is split by domain. The
     facade `app/video_editor_window_delegates.py` now delegates legacy method
     binding to `app/video_editor_delegates_core.py`,
     `app/video_editor_delegates_timeline.py`,
     `app/video_editor_delegates_media_preview_export.py`,
     `app/video_editor_delegates_audio_color.py`,
     `app/video_editor_delegates_creative.py`,
     `app/video_editor_delegates_actor.py`,
     `app/video_editor_delegates_ar_pbr.py`,
     `app/video_editor_delegates_ai.py`, and
     `app/video_editor_delegates_ppt.py`.
   - Status: editing action adapter methods are split behind the existing
     `EditingAdapterMixin` facade into clip/timeline, audio, creative/actor,
     and review/capture slices. Public action IDs and the adapter import path
     are unchanged.
   - Status: AR/PBR GPU preview packet helper code is split into
     `app/ar_pbr/gpu_preview_math.py` and
     `app/ar_pbr/gpu_preview_geometry.py`; the main packet builder remains the
     compatibility entry point. AR/PBR packet export texture, UDIM,
     triplanar, HDRI, IBL, and depth sampling helpers now live in
     `app/ar_pbr/export_packet_sampling.py` while
     PBR triangle rasterization now lives in
     `app/ar_pbr/export_packet_pbr.py`. `app/ar_pbr/export_packet_renderer.py`
     keeps the public rasterization/export entry points and compatibility
     cache/private helper symbols.
   - Status: timeline lane-header painting, Workbench VFX graph summaries,
     Workbench evidence/card widgets, Media Pool media-kind helpers, and Media
     Pool thumbnail/badge/proxy/performance-source decoration helpers now live
     in focused helper modules:
     `app/timeline_track_row_lane_paint.py`,
     `app/workbench_vfx_graph.py`, `app/workbench_cards.py`,
     `app/media_pool_kinds.py`, and `app/media_pool_thumbnails.py`.
   - Status: Sound Editor panel logic is separated from reusable audio UI
     widgets. The compact panel/dock shell remains in
     `app/sound_editor_panel.py`; waveform/spectrum/graph/jog-shuttle widgets
     live in `app/sound_editor_visual_widgets.py`; mixer strips, meters,
     faders, pan sliders, and mixer helper functions live in
     `app/sound_editor_mixer_widgets.py`.
   - Remaining targets: top bar command groups, media/workbench docks,
     preview/transport, timeline palette, right inspector, AI command dock,
     preset browser panels, and audio/editor panels.

## New Baseline Checks

- `.gitattributes`, `.editorconfig`, `ruff.toml`, and `pyproject.toml` define
  line-ending and tooling expectations.
- `tools/qa_packaging_resources.py` verifies PyInstaller resource contracts for
  locales, icon, LUT files, and imageio-ffmpeg metadata.
- `app/ar_pbr/sample_assets.py` centralizes durable AR/PBR sample paths used by
  AR/PBR preview tools and QA so disposable `debugCapture` cleanup does not
  break default model inspection or packet-preview tests.
- `tests/test_debug_capture_boundary.py` guards the disposable scratch-space
  boundary by failing when app/tool defaults use `debugCapture` as a required
  source-media, motion-CSV, descriptor, model, avatar, or imported-asset input.
