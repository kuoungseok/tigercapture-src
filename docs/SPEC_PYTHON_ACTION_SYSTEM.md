# Studio-Wide Python Action System

Status: phase 1 broad action surface active.

This document defines the target action layer for AI, MCP, local LLM, QA, and
review automation control of TigerCapture/Tiger Studio. It is intentionally
broader than the current Script Edit automation registry.

Current implementation:

- `app/actions/schema.py`
- `app/actions/result.py`
- `app/actions/editor_adapter.py`
- `app/actions/editor_adapter_ui.py`
- `app/actions/registry.py`
- `app/actions/ui_namespace.py`
- `app/actions/mmd_namespace.py`
- `app/actions/editor_adapter_mmd.py`
- `app/automation_bridge.py` action methods:
  `automation.list_actions`, `automation.get_action_schema`,
  `automation.preview_action`, `automation.execute_action`,
  `automation.execute_sequence`
- `app/automation_mcp.py` action tools:
  `tigercapture_list_actions`, `tigercapture_get_action_schema`,
  `tigercapture_preview_action`, `tigercapture_execute_action`,
  `tigercapture_execute_sequence`
- `tests/test_python_action_system.py`
- `tests/test_python_action_review_flow.py`
- `tests/test_automation_bridge.py`
- `tests/test_automation_mcp.py`
- `tools/qa_python_action_review_flow.py`
- `app/ai_action_command.py`
- `tests/test_ai_action_command.py`
- `tests/test_mmd_editor_integration.py`
- `tools/mmd_qa_corpus.py`
- `tools/mmd_qa_visual_corpus.py`
- `tools/qa_mmd_editor_composite.py`
- `tools/qa_mmd_multi_actor_timeline.py`
- `tools/qa_mmd_segment_timing.py`
- `tools/qa_mmd_render_queue_wiring.py`
- `tools/qa_mmd_render_queue_export.py`
- `tools/qa_mmd_long_project_export.py`
- `tools/qa_mmd_actor_workflow.py`

AI Command integration:

- The bottom `AI Command` dock first tries a narrow natural-language action
  router for clear editor operations such as media-to-timeline placement,
  split, marker, Mark In/Out, bounded clip audition playback,
  next/previous edit-point jumps, copy/cut/paste, speed, fade, slip/slide/roll edit,
  title/text, basic filter, and basic color-grade commands.
- Routed commands are converted to registered Python Action steps, dry-run
  checked with `execute_sequence(..., dry_run=True)`, and displayed in a
  dedicated AI Action Review dialog before execution.
- Ambiguous chat, provider-status, subtitle, transcript, cleanup, shorts, and
  story prompts continue to Script Edit / provider `EditPlan` generation instead
  of being forced into timeline actions.

NLE positioning:

- The current implementation should be documented as a **core NLE
  workflow/action surface**, not as a full Premiere/Resolve replacement.
- NLE-related registration is now physically split into
  `app/actions/nle_namespace.py` for Source/Record, Project Bin, Multicam, NLE
  readiness, real corpus, timeline fuzzer, and undo health actions. Keep public
  action IDs stable and add new NLE actions there instead of growing the central
  registry.
- VSeeFace bridge registration is physically split into
  `app/actions/vtuber_namespace.py` for bridge status, tracking input source,
  launch/probe, sidecar setup, executable/avatar/capture/framing selection, and
  related dry-run gates. The same module also owns shared VTuber Studio, Avatar
  Target, VRM pose-stream, Performance Source, and Program Output contract
  registrations. Keep public VTuber action IDs stable and add new VTuber/
  VSeeFace actions there instead of growing the central registry.
- Broadcast registration is physically split into
  `app/actions/broadcast_namespace.py` for Live Target, troubleshooting,
  broadcast readiness, platform evidence, and virtual-camera/OBS bridge
  actions. Keep public broadcast action IDs stable and add new broadcast
  actions there instead of growing the central registry.
- Actor registration is physically split into `app/actions/actor_namespace.py`
  for Live2D/Spine actor add, transform, keyframe, and Live2D Performance Source
  retargeting actions. Keep public actor action IDs stable and add new actor
  track-control actions there instead of growing the central registry.
- MMD registration is physically split into `app/actions/mmd_namespace.py` for
  MMD summary, diagnostics, actor track operations, motion/settings/editor
  actions, and ownerless QA corpus actions. Keep public `mmd.*` action IDs
  stable and add new MMD behavior there instead of growing the central registry.
- Evidence/review registration is physically split into
  `app/actions/evidence_namespace.py` for UI focus, screenshot, GIF capture, and
  review scenario actions. Keep public UI/capture/review IDs stable and add new
  review-evidence actions there instead of growing the central registry.
- UI viewer/popout registration is physically split into
  `app/actions/ui_namespace.py` and `app/actions/editor_adapter_ui.py`. It
  exposes only product actions under `ui.viewer.*` for viewer comparison/Fit
  controls and `ui.popout.*` for detached preview/timeline/media/workbench/color/
  subtitle/node/AI-command/VTuber Studio windows plus secondary editor panels:
  actor/effect/title/transition/workflow libraries, Creator Assist, Script
  Edit, Render Queue, Audio Workspace, PIP, and Audio Mixer. Review-only
  `review.ui.*` window actions remain outside the main action catalog.
- Creative registration is physically split into
  `app/actions/creative_namespace.py` for creative readiness, preset catalog,
  clip filter/color-grade, transition, node graph, and typography actions. Keep
  public creative/node/text/transition IDs stable and add new creative actions
  there instead of growing the central registry.
- Audio registration is physically split into `app/actions/audio_namespace.py`
  for video-audio extraction, audio clip split/trim/delete/gain, and audio
  track mix actions, plus Workbench Sound Editor jog-shuttle and inline
  Advanced Lab state actions.
- Track/selection registration is physically split into
  `app/actions/track_selection_namespace.py` for track focus/state, clip
  selection, timeline select-all, and selection set/clear/range actions.
- Media/track basics, markers, and timeline core registration are physically
  split into `app/actions/media_track_namespace.py`,
  `app/actions/marker_namespace.py`, and
  `app/actions/timeline_core_namespace.py`. These own media import,
  import-to-timeline, base track add/remove, marker create/list/remove/move/
  jump, transport, In/Out, edit-point navigation, bounded playback, zoom, snap,
  gap, and history actions.
- Read-only status registration is physically split into
  `app/actions/readonly_namespace.py` for app, project, media, timeline,
  NLE-status, range/edit-point, selected-clip, and selection summaries.
- Source/Record monitor registration is physically split into
  `app/actions/source_record_monitor_namespace.py` for Source monitor state,
  load, In/Out, clear, and Record monitor state/In/Out/clear actions.
- The central `app/actions/registry.py` is intentionally thin: it owns action
  execution, duplicate-id protection, dry-run/destructive gates, sequence
  execution, and calls to namespace registration helpers. Domain behavior should
  not be added directly there.
- `app/actions/editor_adapter.py` is intentionally thin: it owns only
  snapshot/status/app-summary behavior. Public behavior is split across domain
  adapter mixins, and private helper seams are split across
  `editor_adapter_core_helpers.py`, `editor_adapter_timeline_helpers.py`, and
  `editor_adapter_object_helpers.py`. New adapter behavior should be added to
  the matching domain mixin/helper module instead of regrowing
  `editor_adapter.py`.
- Clip edit registration is physically split into
  `app/actions/clip_edit_namespace.py` for split, trim, ripple trim, precision
  trim, range delete, lift/extract, clipboard insert/overwrite, 3-point edit,
  linked clip move, slip/roll/slide, speed, and fade actions.
- Selection movement registration is physically split into
  `app/actions/selection_movement_namespace.py` for selection move/nudge,
  frame nudge, align, distribute, snap, and ripple-delete actions.
- Implemented NLE-style core operations include track targeting, In/Out range
  edits, lift/extract, range delete, insert/overwrite from clipboard, gap
  listing/closing, frame nudge, snapping, marker/edit-point navigation,
  linked-clip movement, and AI/Python Action/MCP automation.
- Source/Record monitor foundations now exist in the action layer:
  `source_monitor.*`, `record_monitor.*`, `timeline.three_point_insert`, and
  `timeline.three_point_overwrite`. This gives future Source monitor / Record
  monitor UI a tested backend without exposing private editor methods.
  `source_record.edit_decision_preview` provides the reviewed insert/overwrite
  decision payload before timeline mutation. `source_record.patch_matrix`
  exposes video/audio patch rows and insert/overwrite command cards for a
  dedicated Source/Record UI. `source_record.keyboard_overlay` exposes J/K/L
  transport, mark-in/out, patching, insert/overwrite, and navigation shortcut
  hints for the same two-monitor UI. `source_record.usability_board` combines
  those pieces into a UI-ready checklist for a two-monitor Source/Record panel
  without mutating the timeline.
- Multicam foundations now exist in the action layer:
  `timeline.multicam.summary`, `timeline.multicam.create_group`,
  `timeline.multicam.switch_plan`, `timeline.multicam.angle_bins`,
  `timeline.multicam.set_active_angle`, `timeline.multicam.sync_quality_board`,
  `timeline.multicam.waveform_sync_board`, and
  `timeline.multicam.live_switch_dashboard`, and
  `timeline.multicam.export_parity_board` / `timeline.multicam.export_handoff`.
  This is a group/switch/export-handoff
  contract with live dashboard, sync-confidence, and cached waveform/transient
  review state, not a full Premiere/Resolve live multicam switcher UI.
- Product-facing NLE workbench state now exists in the action layer:
  `source_record.workbench` summarizes Source/Record monitor command
  enablement, patching, and edit navigation; `project_bin.workbench` summarizes
  bins, metadata columns, proxy state, offline media, and relink readiness;
  `project_bin.batch_plan` adds a read-only relink/proxy/conform review plan;
  `project_bin.conform_report` checks timeline clip source paths against Media
  Pool rows for path/name/ambiguous/missing matches;
  `project_bin.relink_candidate_board` exposes file-by-file relink choices for
  exact, name-only, ambiguous, missing, and offline sources;
  `project_bin.proxy_plan` exposes preview proxy policy, usable proxies, and
  regeneration queues; `project_bin.proxy_health` exposes product-facing proxy
  health cards, safe background regeneration state, and stale/missing/offline
  review signals; `project_bin.offline_browser` exposes offline/missing media
  and relink review state; `project_bin.proxy_regeneration_board` exposes
  reviewed proxy job batches for long-project workflows;
  `project_bin.proxy_conflict_board` separates safe background proxy jobs from
  offline blockers, duplicate media paths, and review-only proxy conflicts;
  `project_bin.search_filter_model` exposes product-bin search/filter chips,
  metadata columns, and filtered media rows. `project_bin.proxy_apply_review_board`
  and `project_bin.conform_apply_review_board` expose the reviewed apply layer
  for proxy regeneration and conform/relink batches, so UI can show what will
  change before jobs run.
- Final Cut-style visual timeline feedback now exists in the action layer:
  `timeline.connected_clips.anchor_overlay` returns anchor-line descriptors for
  connected clips, `timeline.role_lanes.filter_model` returns visible/hidden
  role-filter clip sets, and `timeline.magnetic_storyline.drag_preview` returns
  a non-mutating snap/push/collision preview for magnetic drags. The adapter
  lives in `app/actions/editor_adapter_nle_visual.py`, registration lives in
  `app/actions/nle_visual_namespace.py`, and pure contracts live in
  `app/nle_visual_feedback.py`. The first Qt timeline paint integration is
  separate from the action layer: `app/timeline_nle_visual_overlay.py` converts
  cue metadata into reusable connected-anchor and drag-preview drawing helpers
  consumed by `app/timeline_track_row_paint.py`. `timeline.role_lanes.focus`
  is still a normal registered action, but the adapter now pushes the focused
  role into live `TrackRow.set_focused_clip_role(...)` instances so the timeline
  dims non-matching clip roles immediately. The compact role filter bar in
  `app/video_editor_nle_role_panel.py` consumes the same filter model and routes
  user clicks back through `timeline.role_lanes.focus`, keeping the UI surface
  aligned with MCP/Python Action state. Cross-row connected-clip curves are
  painted by `app/timeline_connected_anchor_overlay_widget.py` from the
  `timeline.connected_clips.anchor_overlay` contract, so the visual overlay
  remains an action-backed view instead of a private timeline-only rule.
- Audition/take UI also has an action-backed visual model:
  `app/nle_audition_visuals.py` converts `timeline.audition.compare` results
  into compact take cards, and `app/video_editor_nle_audition_workflow.py`
  uses those cards while applying switch/rename/remove through the registered
  `timeline.audition.*` actions.
- Multicam workbench actions now include `timeline.multicam.sync_plan`,
  `timeline.multicam.angle_bins`, and `timeline.multicam.switcher_workbench`,
  giving the future switcher UI angle bins, coverage/gap diagnostics, angle
  tiles, active-angle state, sync offsets, sync quality confidence, and export
  handoff readiness without claiming a full live switcher.
- `timeline.professional_nle_readiness` and `tools/qa_nle_readiness.py` keep a
  conservative claim gate. The current report can pass QA while still returning
  `professional_nle_claim_ok=false`, because the product is not yet a full
  Premiere/Resolve-class NLE.
- `timeline.nle_fuzzer.status` exposes `tools/qa_timeline_fuzzer.py` output as
  undo/edge-case readiness evidence, including required edit operations,
  failures, undo depth, linked audio, and actor-lane coverage.
- `timeline.core_action_coverage` exposes a grouped coverage matrix for core
  NLE edit, clipboard/insert, Source/Record, Project Bin, storyline, multicam,
  and undo/recovery actions.
- `timeline.nle_core_safety_matrix` exposes the safety layer that must stay
  visible for NLE claims: dry-run preview, destructive confirmation, undo
  recovery, and real-corpus claim gates.
- `timeline.undo_health` exposes the same fuzzer evidence as UI-ready
  operation coverage rows, risk cards, blockers, and rerun/failure-report
  command enablement for undo/edge-case QA panels.
- `timeline.undo_recovery_playbook` exposes a UI-ready recovery plan for undo
  and destructive-edit failures: rerun fuzzer, inspect gaps, replay undo/redo,
  verify autosave/reopen, and copy reproduction steps.
- `timeline.undo_stability_dashboard` combines fuzzer status, undo health,
  review-board rows, and recovery steps into one UI-ready QA dashboard for
  coverage cards, blocker rows, and rerun/recovery commands.
- `timeline.undo_long_session_plan` turns undo/recovery checks into a
  repeatable long-session rehearsal plan that still requires real project
  execution before clearing professional-NLE claim gates.
- `timeline.storyline_gesture_polish_board` exposes Final Cut-style gesture
  polish readiness for anchor overlays, role filters, magnetic drag preview,
  audition cards, and role focus. It is evidence for implementation depth, not
  a replacement for real editor gesture QA.
- Real long-project corpus evidence is tracked separately from generated QA
  fixtures through `tools/discover_nle_real_projects.py`,
  `tools/register_nle_real_project.py`,
  `tools/qa_nle_real_project_corpus.py`, and the read-only
  `nle.real_corpus.status` / `nle.real_corpus.discover` /
  `nle.real_corpus.intake_board` / `nle.real_corpus.collection_kit` /
  `nle.real_corpus.gate_board` / `nle.real_corpus.workbench` /
  `nle.real_corpus.validation_plan` /
  `nle.real_corpus.validation_packet` /
  `nle.real_corpus.validation_preflight` /
  `nle.real_corpus.validation_report`
  actions. `nle.real_corpus.gate_board` is the combined product board for claim
  blockers, candidate registration, validation gaps, validation-ready projects,
  and rerun commands; it does not clear the professional claim gate by itself.
  `nle.real_corpus.workbench` wraps discovery, preflight, validation, cards,
  primary next action, QA commands, and action sequence into one UI-ready
  payload.
  `nle.real_corpus.validation_packet` is the project-specific operator packet
  with required/optional checks, redaction rules, manual steps, and reviewed
  action/CLI templates. `nle.real_corpus.validation_preflight` performs only
  machine prerequisite checks and leaves required evidence rows pending until an
  operator records actual results; the CLI companion is
  `tools/qa_nle_real_project_preflight.py`. Redacted operator evidence for registered projects is written
  through `nle.real_corpus.validation_evidence.register`, covering open/reopen,
  scrub sampling, proxy/relink health, undo/recovery, representative short
  export, and nested/proxy edge-case checks. Synthetic stress evidence can
  improve implementation confidence, but it must not clear the real-world
  corpus claim gate.
- The official real-corpus QA path requires validation evidence by default.
  `tools/qa_nle_real_project_corpus.py --metric-only` is diagnostic only; AI,
  MCP, release readiness, and marketing copy must use the stricter default that
  requires registered validation evidence.
- `timeline.nle_target_gap` computes a target-score board from the current NLE
  readiness report. It is read-only and exists to explain why 95/100 cannot be
  treated as safe professional-NLE parity while `real_world_long_project_corpus`
  remains blocked.
- `nle.real_corpus.collection_kit` includes `validation.cli_examples` for the
  companion `tools/register_nle_real_project_validation.py` CLI, so product UI
  and local agents can show copy-ready validation registration commands without
  inventing command syntax.
- Remaining honest gaps before claiming full NLE parity:
  dedicated source-monitor / record-monitor UI is still shallow; live multicam
  switcher UI, deeper proxy/media management, conform, relink, metadata editing,
  and visual project-bin workflows need more depth; undo/redo and edge-case
  behavior need continuous QA; long-duration and large-project real-world
  validation need more evidence.

Registered actions:

- `app.status`
- `project.snapshot`
- `media.summary`
- `project_bin.workbench`
- `project_bin.batch_plan`
- `project_bin.conform_report`
- `project_bin.proxy_plan`
- `project_bin.proxy_health`
- `project_bin.review_board`
- `project_bin.offline_browser`
- `project_bin.relink_candidate_board`
- `project_bin.proxy_regeneration_board`
- `project_bin.proxy_conflict_board`
- `project_bin.search_filter_model`
- `timeline.summary`
- `timeline.nle_status`
- `preset.catalog`
- `selected.clip`
- `media.import`
- `track.add`
- `track.remove`
- `track.select`
- `track.lock`
- `track.mute`
- `track.rename`
- `timeline.range`
- `timeline.edit_points`
- `timeline.set_playhead`
- `timeline.play`
- `timeline.pause`
- `timeline.stop`
- `timeline.step_frames`
- `timeline.set_shuttle_rate`
- `timeline.set_in`
- `timeline.set_out`
- `timeline.clear_in_out`
- `timeline.set_in_out_from_selection`
- `timeline.jump_in_out`
- `timeline.track_targets`
- `timeline.track_target.set`
- `timeline.track_target.clear`
- `timeline.jump_edit_point`
- `timeline.play_range`
- `timeline.play_clip_range`
- `timeline.select_all`
- `timeline.set_zoom`
- `timeline.fit`
- `timeline.nudge`
- `timeline.snap.get`
- `timeline.snap.set`
- `timeline.snap.toggle`
- `timeline.edge_issues`
- `timeline.cleanup_edges`
- `timeline.gaps`
- `timeline.close_gap`
- `timeline.close_all_gaps`
- `timeline.range_delete`
- `timeline.lift`
- `timeline.extract`
- `history.undo`
- `history.redo`
- `timeline.marker.add`
- `timeline.marker.list`
- `timeline.marker.remove`
- `timeline.marker.move`
- `timeline.marker.jump`
- `marker.add`
- `timeline.split`
- `timeline.precision_trim`
- `timeline.trim_to_playhead`
- `clip.trim`
- `clip.ripple_trim`
- `timeline.ripple_delete`
- `timeline.lift`
- `timeline.extract`
- `timeline.range_delete`
- `timeline.insert_clipboard`
- `timeline.overwrite_clipboard`
- `timeline.three_point_insert`
- `timeline.three_point_overwrite`
- `timeline.professional_nle_readiness`
- `timeline.nle_target_gap`
- `nle.real_corpus.status`
- `nle.real_corpus.discover`
- `nle.real_corpus.intake_board`
- `nle.real_corpus.collection_kit`
- `nle.real_corpus.gate_board`
- `nle.real_corpus.workbench`
- `nle.real_corpus.validation_plan`
- `nle.real_corpus.validation_packet`
- `nle.real_corpus.validation_preflight`
- `nle.real_corpus.validation_report`
- `nle.real_corpus.validation_evidence.register`
- `timeline.nle_fuzzer.status`
- `timeline.core_action_coverage`
- `timeline.undo_health`
- `timeline.undo_review_board`
- `timeline.undo_recovery_playbook`
- `timeline.undo_stability_dashboard`
- `timeline.magnetic_storyline.status`
- `timeline.magnetic_storyline.apply`
- `timeline.magnetic_storyline.drag_preview`
- `timeline.connected_clips.status`
- `timeline.connected_clips.connect`
- `timeline.connected_clips.anchor_overlay`
- `timeline.role_colors.status`
- `timeline.role_lanes.status`
- `timeline.role_lanes.focus`
- `timeline.role_lanes.filter_model`
- `timeline.clip_role.set`
- `timeline.auditions.status`
- `timeline.audition.compare`
- `timeline.audition.add_take`
- `timeline.audition.switch_take`
- `timeline.audition.rename_take`
- `timeline.audition.remove_take`
- `timeline.multicam.summary`
- `timeline.multicam.create_group`
- `timeline.multicam.sync_plan`
- `timeline.multicam.switch_plan`
- `timeline.multicam.angle_bins`
- `timeline.multicam.set_active_angle`
- `timeline.multicam.switcher_workbench`
- `timeline.multicam.tile_board`
- `timeline.multicam.review_board`
- `timeline.multicam.sync_quality_board`
- `timeline.multicam.waveform_sync_board`
- `timeline.multicam.export_handoff`
- `source_monitor.state`
- `source_monitor.load_media`
- `source_monitor.set_in`
- `source_monitor.set_out`
- `source_monitor.clear`
- `source_record.workbench`
- `source_record.edit_decision_preview`
- `source_record.patch_matrix`
- `source_record.monitor_layout`
- `source_record.apply_board`
- `source_record.keyboard_overlay`
- `record_monitor.state`
- `record_monitor.set_in`
- `record_monitor.set_out`
- `record_monitor.clear`
- `clip.select`
- `clip.delete`
- `clip.duplicate`
- `clip.copy`
- `clip.cut_to_clipboard`
- `clip.paste`
- `clip.set_speed`
- `clip.set_fade`
- `media.import_to_timeline`
- `vtuber.performance_source.summary`
- `vtuber.performance_source.mark_media`
- `vtuber.performance_source.add_clip`
- `vtuber.program_output_contract`
- `actor.live2d.apply_performance_source`
- `mmd.summary`
- `mmd.diagnostics`
- `mmd.qa.run`
- `mmd.qa.visual_run`
- `mmd.qa.composite_run`
- `mmd.qa.timeline_run`
- `mmd.qa.segment_run`
- `mmd.qa.render_queue_run`
- `mmd.qa.render_queue_export_run`
- `mmd.qa.long_project_run`
- `mmd.qa.workflow_run`
- `mmd.actor.add`
- `mmd.actor.delete`
- `mmd.actor.duplicate`
- `mmd.track.move`
- `mmd.track.trim`
- `mmd.motion.list`
- `mmd.motion.add`
- `mmd.motion.apply`
- `mmd.settings.apply`
- `mmd.editor.open`
- `clip.move`
- `clip.move_snapped`
- `clip.move_linked`
- `clip.link_audio`
- `clip.unlink_audio`
- `clip.set_sync_offset`
- `clip.j_cut`
- `clip.l_cut`
- `clip.slip`
- `clip.roll`
- `clip.slide`
- `clip.nudge`
- `clip.nudge_frames`
- `track.reorder`
- `track.set_state`
- `selection.summary`
- `selection.set`
- `selection.clear`
- `selection.select_range`
- `selection.move`
- `selection.nudge`
- `selection.nudge_frames`
- `timeline.nudge_frames`
- `selection.align_to_playhead`
- `selection.align_to_marker`
- `selection.snap_to_nearest`
- `selection.ripple_delete`
- `audio.clip.split`
- `audio.clip.trim`
- `audio.clip.delete`
- `audio.clip.set_gain`
- `audio.track.set_mix`
- `audio.track.set_volume`
- `audio.track.set_pan`
- `audio.track.mute`
- `audio.track.solo`
- `audio.mixer.state`
- `audio.sound_editor.jog_shuttle.state`
- `audio.sound_editor.jog_shuttle.set`
- `audio.sound_editor.advanced_lab.state`
- `audio.sound_editor.advanced_lab.set`
- `clip.set_filter`
- `clip.set_color_grade`
- `transition.apply`
- `transition.clear`
- `node.graph.set`
- `creative_layer.readiness`

Clipboard contract:
`clip.copy`, `clip.cut_to_clipboard`, and `clip.paste` include linked audio
by default. Paste creates a fresh audio clip and rewires the pasted video clip
to the new audio id while preserving the original sync offset. Callers can set
`include_linked_audio=false` for video-only clipboard operations.
- `node.add`
- `node.connect`
- `node.set_param`
- `node.delete`
- `text.add`
- `text.set_keyframes`
- `actor.add`
- `actor.set_transform`
- `actor.set_keyframes`
- `ui.popout.list`
- `ui.popout.open`
- `ui.popout.set_geometry`
- `ui.popout.capture`
- `ui.popout.close`
- `ui.viewer.compare.set`
- `ui.viewer.fit`
- `capture.screenshot`
- `capture.gif`
- `review.scenario.run`
- `creative_layer.readiness` returns the conservative claim gate for effects,
  transitions, typography, node graphs, Live2D/Spine actors, AR/PBR 3D
  compositing, and template ecosystem depth. It must stay read-only and must
  not imply Fusion/After Effects/Marmoset/CapCut parity.

Implementation notes:

- Destructive actions require `confirm_destructive=true` unless dry-run is used.
- `capture.gif` uses an editor owner GIF backend when available and falls back
  to short Qt `grab()` frame capture for review/QA evidence.
- `ui.popout.*` is the unattended QA/control surface for detachable windows.
  It can list targets, open/raise them, set geometry, capture a popout image,
  and close the window without exposing private editor methods. It accepts
  `surface` as an alias for `target` so old review-runner naming can be bridged,
  but the review-only `review.ui.*` actions are still not registered in the
  main Action Registry.
- `ui.viewer.compare.set` is the current MVP bridge for viewer Comparison
  Templates. It updates the active video track's preview compare mode and
  optional `Original | After` label visibility without exposing private editor
  internals. `ui.viewer.fit` invokes the same viewer Fit behavior as the toolbar
  button.
- `review.scenario.run` calls the review automation report runner when the
  live editor owner does not provide its own scenario backend.
- `VideoEditorWindow` now provides a live review scenario backend. When the
  action is executed with a running editor owner, feature review scenarios can
  mutate the actual timeline through registered actions and save live editor
  screenshots to the review artifact paths.
- `tools/qa_python_action_review_flow.py` verifies the action surface with a
  sample-media flow: import media, edit timeline, capture screenshot/GIF, and
  generate a review report.
- Review automation now records action-driven scenarios through
  `app.review_automation.scenario_manifest` and traceability through
  `app.review_automation.evidence_graph`, so action evidence can be tied back to
  feature claims, sample media, artifacts, QA reports, and registered action ids.
- Actor actions support Live2D and Spine model tracks at the data-model level.
- MMD actions support editor actor-track control and QA automation. The
  ownerless `mmd.qa.run` action executes the local manifest diagnostics from
  `app.mmd.qa_corpus`, `mmd.qa.visual_run` renders offscreen OpenGL PNGs and a
  visual contact sheet for text-first/remote review, and
  `mmd.qa.composite_run` exercises synthetic-video preview alpha, MMD alpha MOV
  pre-render, final MP4 overlay, and outside-region contamination metrics.
  `mmd.qa.timeline_run` extends that to two staggered MMD actor tracks and
  checks none/single/overlap/single/none timing through preview, alpha
  pre-render, and final MP4 export. `mmd.qa.segment_run` verifies trimmed
  source starts, skipped source gaps, and 2x speed segments against expected
  MMD active windows through preview, alpha pre-render, and final MP4 export.
  `mmd.qa.render_queue_run` verifies the batch/render-queue export factory
  forwards trimmed/speed segments, MMD tracks, and the MMD pre-rendered alpha
  overlay into `VideoExportThread`. `mmd.qa.render_queue_export_run` runs that
  factory with the real exporter, writes baseline/MMD MP4 outputs, and checks
  two simultaneous MMD actor regions against a preview overlay sample.
  `mmd.qa.long_project_run` runs a 10s synthetic source through the real
  render-queue factory, preserves five trimmed/speed segments, uses two MMD
  actors, and samples the final MP4 against preview overlays. `mmd.qa.workflow_run`
  verifies the action-level actor workflow, including external VMD library add
  via `mmd.motion.add`, motion apply, settings persistence,
  move/trim/duplicate, destructive delete confirmation, summary, diagnostics,
  and player sync.
- Node actions mutate `VideoTrack.node_graph_view_data`, the same payload used by
  the Workbench node graph widget.
- `clip.move_snapped` shares the timeline model drag policy with UI dragging:
  dry-run computes the exact snap/collision result, then execution applies the
  same resolved position as one undoable action. The action now prefers the
  Rust native worker `timeline_drag_constraints` result when available and
  falls back to Python `apply_drag_constraints_detail` when the worker is
  missing, outdated, or rejects the method.
- `timeline.gaps`, `timeline.close_gap`, and `timeline.close_all_gaps` share the
  same gap detector. That helper now prefers the Rust native worker
  `timeline_gaps` result when available and falls back to Python `_track_gaps`
  when the worker is missing, outdated, or rejects the method.
- `clip.ripple_trim`, `timeline.precision_trim`, and actions that delegate to
  precision trim such as `timeline.trim_to_playhead` share the same pure
  video-window planner. They now prefer the Rust native worker
  `timeline_trim_plan` result when available and fall back to Python trim math
  when the worker is missing, outdated, or rejects the method. Linked audio,
  validation, undo transactions, and final mutation remain in Python.

## Why This Exists

The current automation boundary is safe but narrow. `app.automation_commands`
exposes a registered command set for app status, project snapshots, validated
EditPlan preview/apply, reviewed cuts, and marker creation. That is correct for
the first AI Script Edit/MCP bridge, but it is not enough for a studio-wide
control surface.

The target system should let trusted developer tools and approved AI/MCP
clients perform real editor workflows without using arbitrary Python, shell
commands, or UI-only mouse gestures.

Examples:

- import media, add/remove tracks, split clips, ripple delete, trim, nudge,
  duplicate, paste, set speed, add fades, apply transitions, and clean timeline
  edges.
- apply clip filters, chroma key, background removal, stabilization, color
  grades, LUTs, node graph changes, masks, and tracked masks.
- edit audio clips/tracks, apply Sound Editor chains, extract audio from video,
  separate vocals/music, set mixer state, and run loudness delivery checks.
- add typography, subtitles, stickers, drawings, speech bubbles, motion presets,
  Screen Studio style auto polish, cursor/click/hotkey emphasis, and auto zoom.
- add/control Live2D, Spine/NIKKE, VTuber/VSeeFace, and AR/PBR 3D actor tracks.
- stage render jobs, run render queue operations, create publish packages, run
  QA/health checks, and capture review evidence.

## Non-Goals

- Do not expose arbitrary Python execution.
- Do not expose arbitrary shell execution.
- Do not make MCP call `VideoEditorWindow` private methods directly.
- Do not make destructive timeline operations implicit.
- Do not claim Spine render correctness as solved by action automation. Spine
  can have actions, but renderer quality remains a separate tracked risk.

## Current Relevant Surfaces

- Safe command bridge:
  - `app/automation_commands.py`
  - `app/automation_bridge.py`
  - `app/automation_mcp.py`
  - `tools/automation_bridge_cli.py`
  - `tools/automation_mcp_server.py`
- Main editor/private UI entry points:
  - `app/video_editor_window.py`
- Timeline model:
  - `app/timeline_model.py`
- Project persistence:
  - `app/project_io.py`
- Preview/export:
  - `app/project_player.py`
  - `app/video_exporter.py`
- Presets/templates:
  - `app/preset_library.py`
- Audio:
  - `app/audio_tracks.py`
  - `app/audio_workflow.py`
  - `app/audio_separation.py`
  - `app/audio_mixer_panel.py`
- Color/VFX/node graph:
  - `app/color_grading.py`
  - `app/color_management.py`
  - `app/color_workflow.py`
  - `app/workbench_panel.py`
  - `app/workbench/node_graph/*`
  - `app/node_mask.py`
  - `app/mask_editor_window.py`
- Actors:
  - `app/live2d/*`
  - `app/spine_editor/*`
  - `app/actor_*`
  - `app/ar_pbr/*`
  - `app/vtuber/*`
- Review/QA/health:
  - `app/review_automation/*`
  - `app/qa_dashboard.py`
  - `app/health_center_dialog.py`
  - `app/media_health_dialog.py`

## Target Architecture

```text
AI / MCP / local LLM / QA / review automation
        |
        v
Action Registry
        |
        v
Validated Python Actions
        |
        v
Editor Adapter
        |
        v
VideoEditorWindow / TimelineModel / Audio / Color / Node / Actor systems
```

The Action Registry is the stable public surface. The Editor Adapter is allowed
to call current private editor methods while the monolith is being extracted.
External clients should only see registered action schemas.

## Proposed Modules

```text
app/actions/__init__.py
app/actions/schema.py
app/actions/registry.py
app/actions/result.py
app/actions/ids.py
app/actions/editor_adapter.py
app/actions/editor_adapter_timeline.py
app/actions/editor_adapter_editing.py
app/actions/editor_adapter_vtuber.py
app/actions/editor_adapter_nle.py
app/actions/project_actions.py
app/actions/capture_actions.py
app/actions/media_actions.py
app/actions/timeline_actions.py
app/actions/clip_actions.py
app/actions/audio_actions.py
app/actions/color_actions.py
app/actions/vfx_actions.py
app/actions/node_actions.py
app/actions/text_actions.py
app/actions/preset_actions.py
app/actions/screenstudio_actions.py
app/actions/actor_actions.py
app/actions/nle_namespace.py
app/actions/vtuber_namespace.py
app/actions/broadcast_namespace.py
app/actions/actor_namespace.py
app/actions/evidence_namespace.py
app/actions/creative_namespace.py
app/actions/audio_namespace.py
app/actions/track_selection_namespace.py
app/actions/media_track_namespace.py
app/actions/marker_namespace.py
app/actions/timeline_core_namespace.py
app/actions/readonly_namespace.py
app/actions/source_record_monitor_namespace.py
app/actions/clip_edit_namespace.py
app/actions/selection_movement_namespace.py
app/actions/render_actions.py
app/actions/publish_actions.py
app/actions/health_actions.py
app/actions/qa_actions.py
tests/test_python_action_system.py
tests/test_automation_bridge.py
tests/test_automation_mcp.py
tests/test_automation_commands.py
tools/qa_automation_bridge.py
tools/qa_automation_mcp.py
tools/qa_automation_commands.py
```

Existing `app.automation_commands` can either wrap this registry later or keep
its current EditPlan-specific commands and add forwarding commands such as
`list_actions`, `preview_action`, `execute_action`, and `execute_action_sequence`.

## Action Contract

Every action should declare:

- `id`: stable dotted name such as `timeline.split`.
- `title`: human-readable label.
- `namespace`: one of the namespaces below.
- `params_schema`: JSON-serializable schema.
- `result_schema`: JSON-serializable result contract.
- `mutating`: true when editor/project state changes.
- `destructive`: true for deletes, ripple operations, overwrites, and cancels.
- `requires_owner`: true when a live editor instance is required.
- `requires_review`: true when a human-visible review step is required.
- `supports_dry_run`: true whenever possible.
- `undo_label`: label used when creating an editor history transaction.
- `async_kind`: empty for sync actions, or `render`, `analysis`, `export`,
  `actor_probe`, `media_import`, etc.

Example request:

```json
{
  "action": "timeline.split",
  "params": {
    "track_id": 1,
    "at_ms": 2500
  },
  "dry_run": false
}
```

Example sequence:

```json
[
  {"action": "media.import", "params": {"path": "sample.mp4", "target": "video_track"}},
  {"action": "timeline.set_zoom", "params": {"px_per_sec": 220}},
  {"action": "timeline.split", "params": {"track_id": 1, "at_ms": 2500}},
  {"action": "clip.set_speed", "params": {"track_id": 1, "clip_id": 2, "speed": 1.5}},
  {"action": "clip.apply_filter", "params": {"track_id": 1, "clip_id": 2, "preset_id": "effect-clean-sharpen"}},
  {"action": "transition.apply", "params": {"track_id": 1, "clip_id": 1, "preset_id": "transition-clean-dissolve"}},
  {"action": "capture.screenshot", "params": {"target": "editor", "name": "cut_effect_demo"}}
]
```

## Required Namespaces

```text
app.*
project.*
capture.*
media.*
timeline.*
track.*
clip.*
audio.*
color.*
vfx.*
node.*
text.*
subtitle.*
overlay.*
preset.*
template.*
screenstudio.*
ai.*
actor.*
live2d.*
spine.*
vtuber.*
ar_pbr.*
preview.*
render.*
publish.*
health.*
qa.*
cache.*
settings.*
```

## Minimum Action Catalog

### App and Project

- `app.status`
- `app.set_language`
- `settings.get`
- `settings.set`
- `project.new`
- `project.open`
- `project.save`
- `project.save_as`
- `project.snapshot`
- `project.recover`
- `project.autosave_now`

### Capture and Media Intake

- `capture.screenshot`
- `capture.gif.start`
- `capture.mp4.start`
- `capture.stop`
- `capture.select_region`
- `media.import`
- `media.import_youtube`
- `media.remove`
- `media.select`
- `media.refresh_thumbnail`
- `media.scrub_preview`
- `media.health`
- `project_bin.workbench`
- `project_bin.batch_plan`
- `project_bin.conform_report`
- `project_bin.proxy_plan`
- `project_bin.proxy_health`
- `project_bin.review_board`
- `project_bin.offline_browser`
- `project_bin.relink_candidate_board`
- `project_bin.proxy_regeneration_board`
- `project_bin.proxy_conflict_board`
- `media.relink.plan`
- `media.relink.apply`

### Timeline, Tracks, and Clips

- `track.add`
- `track.remove`
- `track.select`
- `track.lock`
- `track.mute`
- `track.rename`
- `track.reorder`
- `timeline.set_playhead`
- `timeline.play`
- `timeline.play_range`
- `timeline.play_clip_range`
- `timeline.pause`
- `timeline.stop`
- `timeline.step_frames`
- `timeline.set_shuttle_rate`
- `timeline.set_zoom`
- `timeline.fit`
- `timeline.snap.get`
- `timeline.snap.set`
- `timeline.snap.toggle`
- `timeline.edit_points`
- `timeline.select_all`
- `timeline.set_in`
- `timeline.set_out`
- `timeline.clear_in_out`
- `timeline.set_in_out_from_selection`
- `timeline.jump_in_out`
- `timeline.track_targets`
- `timeline.track_target.set`
- `timeline.track_target.clear`
- `timeline.marker.add`
- `timeline.marker.remove`
- `timeline.marker.list`
- `timeline.marker.move`
- `timeline.marker.jump`
- `timeline.split`
- `timeline.ripple_delete`
- `timeline.range_delete`
- `timeline.lift`
- `timeline.extract`
- `timeline.insert_clipboard`
- `timeline.overwrite_clipboard`
- `timeline.three_point_insert`
- `timeline.three_point_overwrite`
- `timeline.professional_nle_readiness`
- `timeline.nle_target_gap`
- `nle.real_corpus.status`
- `nle.real_corpus.discover`
- `nle.real_corpus.intake_board`
- `nle.real_corpus.collection_kit`
- `nle.real_corpus.gate_board`
- `nle.real_corpus.workbench`
- `nle.real_corpus.validation_plan`
- `nle.real_corpus.validation_packet`
- `nle.real_corpus.validation_preflight`
- `nle.real_corpus.validation_report`
- `nle.real_corpus.validation_evidence.register`
- `timeline.nle_fuzzer.status`
- `timeline.core_action_coverage`
- `timeline.undo_health`
- `timeline.undo_review_board`
- `timeline.undo_recovery_playbook`
- `timeline.undo_stability_dashboard`
- `timeline.multicam.summary`
- `timeline.multicam.create_group`
- `timeline.multicam.sync_plan`
- `timeline.multicam.switch_plan`
- `timeline.multicam.angle_bins`
- `timeline.multicam.set_active_angle`
- `timeline.multicam.switcher_workbench`
- `timeline.multicam.tile_board`
- `timeline.multicam.review_board`
- `timeline.multicam.sync_quality_board`
- `timeline.multicam.waveform_sync_board`
- `timeline.multicam.export_handoff`
- `source_monitor.state`
- `source_monitor.load_media`
- `source_monitor.set_in`
- `source_monitor.set_out`
- `source_monitor.clear`
- `source_record.workbench`
- `source_record.edit_decision_preview`
- `source_record.patch_matrix`
- `source_record.monitor_layout`
- `source_record.apply_board`
- `source_record.keyboard_overlay`
- `record_monitor.state`
- `record_monitor.set_in`
- `record_monitor.set_out`
- `record_monitor.clear`
- `timeline.precision_trim`
- `timeline.trim_to_playhead`
- `timeline.nudge`
- `timeline.nudge_frames`
- `timeline.jump_edit_point`
- `timeline.edge_issues`
- `timeline.cleanup_edges`
- `timeline.gaps`
- `timeline.close_gap`
- `timeline.close_all_gaps`
- `clip.select`
- `selection.summary`
- `selection.select_range`
- `selection.move`
- `selection.nudge`
- `selection.nudge_frames`
- `selection.align_to_playhead`
- `selection.align_to_marker`
- `selection.snap_to_nearest`
- `selection.ripple_delete`
- `clip.delete`
- `clip.duplicate`
- `clip.copy`
- `clip.cut_to_clipboard`
- `clip.paste`
- `clip.move`
- `clip.move_snapped`
- `clip.move_linked`
- `clip.trim_left`
- `clip.trim_right`
- `clip.ripple_trim`
- `clip.nudge_frames`
- `clip.slip`
- `clip.slide`
- `clip.roll`
- `clip.j_cut`
- `clip.l_cut`
- `clip.set_speed`
- `clip.add_speed_segment`
- `clip.set_fade`
- `clip.set_pip`
- `clip.link_audio`
- `clip.unlink_audio`
- `clip.nest`
- `clip.expand_nested`

### Effects, Presets, Screen Polish

- `clip.apply_filter`
- `clip.clear_filters`
- `clip.set_fx_enabled`
- `clip.apply_chroma_key`
- `clip.apply_background_removal`
- `clip.apply_stabilizer`
- `transition.apply`
- `transition.clear`
- `preset.search`
- `preset.apply`
- `preset.pack.import`
- `preset.pack.export`
- `preset.pack.enable`
- `preset.pack.disable`
- `preset.pack.repair`
- `template.apply`
- `template.compose`
- `screenstudio.apply_auto_polish`
- `screenstudio.set_payload`
- `screenstudio.generate_auto_zoom`
- `screenstudio.edit_zoom`
- `screenstudio.local_share_manifest`

### Audio

Current registered audio action surface, verified against `ActionRegistry` on
2026-07-04:

- `audio.clip.split`
- `audio.clip.trim`
- `audio.clip.delete`
- `audio.clip.set_gain`
- `audio.extract_from_video`
- `audio.sound_editor.jog_shuttle.state`
- `audio.sound_editor.jog_shuttle.set`
- `audio.sound_editor.advanced_lab.state`
- `audio.sound_editor.advanced_lab.set`
- `audio.sound_editor.apply_effects`
- `audio.sound_editor.apply_ai_preset`
- `audio.loudness_report`
- `audio.separate_stems`
- `audio.export_clip`
- `audio.track.set_mix`
- `audio.track.set_volume`
- `audio.track.set_pan`
- `audio.track.mute`
- `audio.track.solo`
- `audio.mixer.state`

The renewed Sound Editor UI mutates `AudioClip.effects` through
`SoundEditorPanel` / `SoundEditorDockWindow`. The action layer can now focus the
Workbench Sound Editor, set/read the reference-05 jog shuttle state, and
expand/collapse the inline Advanced Lab without opening the legacy lab window.
Legacy Sound Editor feature parity is exposed through `audio.sound_editor.apply_effects`
for Basic/EQ/Dynamics/FX/Advanced state, `audio.sound_editor.apply_ai_preset`
for AI Master presets, `audio.loudness_report` for waveform-cache diagnostics,
`audio.separate_stems` for vocals/instrumental separation, and `audio.export_clip`
for edited clip export planning or rendering.

2026-07-08 mixer automation update: the Workbench Sound Editor also exposes a
Mixer tab backed by real `AudioTrack` state. Local AI and review automation can
use `audio.track.set_volume`, `audio.track.set_pan`, `audio.track.mute`,
`audio.track.solo`, and read `audio.mixer.state` (`tigerstudio.audio.mixer.v1`)
to inspect volume, pan, mute, solo, bus, clip count, and audible state. Track
mute/solo is persisted in project files, participates in undo snapshots, drives
the timeline mixer UI, and is honored by preview volume and FFmpeg export.

### Color, VFX, Masks, and Nodes

- `color.set_management`
- `color.apply_grade`
- `color.apply_preset`
- `color.apply_lut`
- `color.set_compare_mode`
- `color.scope.capture`
- `color.scope.report`
- `vfx.apply_chroma_key`
- `vfx.apply_background_removal`
- `vfx.apply_stabilizer`
- `mask.create_power_window`
- `mask.create_hsl_qualifier`
- `mask.create_magic_mask`
- `mask.create_bitmap`
- `mask.refine_grabcut`
- `mask.refine_sam_point`
- `mask.track`
- `mask.add_tracking_correction`
- `node.add`
- `node.remove`
- `node.connect`
- `node.disconnect`
- `node.select`
- `node.set_params`
- `node.attach_mask`
- `node.detach_mask`
- `node.evaluate_preview`

### Text, Subtitles, and Overlays

- `subtitle.import`
- `subtitle.add`
- `subtitle.update`
- `subtitle.remove`
- `subtitle.apply_style`
- `text.add_title`
- `text.update`
- `text.delete`
- `text.duplicate`
- `text.set_animation`
- `text.export_mov`
- `overlay.add_sticker`
- `overlay.add_speech_bubble`
- `overlay.add_drawing`
- `overlay.clear_drawing`

### AI and Creator Workflows

- `ai.provider_status`
- `ai.generate_edit_plan`
- `ai.preview_edit_plan`
- `ai.apply_edit_plan`
- `ai.apply_reviewed_cuts`
- `ai.transcript.import`
- `ai.transcript.transcribe_media`
- `ai.text_edit.remove_fillers`
- `ai.text_edit.remove_silence`
- `ai.creator_bundle.generate`
- `ai.creator_bundle.preview`
- `ai.creator_bundle.apply`
- `ai.storyboard.generate`
- `ai.storyboard.apply`

### Actors, VTuber, and 3D

- `actor.scan`
- `actor.loading_status`
- `actor.qa_report`
- `actor.prerender_cache`
- `live2d.add`
- `live2d.select`
- `live2d.set_transform`
- `live2d.set_motion`
- `live2d.set_expression`
- `live2d.apply_motion_storyboard`
- `live2d.apply_video_mocap`
- `live2d.export_only`
- `spine.add`
- `spine.select`
- `spine.set_skin`
- `spine.set_animation`
- `spine.probe_render`
- `spine.prerender_cache`
- `vtuber.vseeface.preflight`
- `vtuber.vseeface.launch_plan`
- `vtuber.vseeface.broadcast_source`
- `ar_pbr.import_asset`
- `ar_pbr.add_track`
- `ar_pbr.set_transform`
- `ar_pbr.set_lighting`
- `ar_pbr.set_anchor`
- `ar_pbr.depth_estimate`
- `ar_pbr.camera_solve`
- `ar_pbr.preview`

### Render, Publish, Health, and QA

- `preview.seek`
- `preview.capture_frame`
- `preview.clear_cache`
- `render.export`
- `render.queue.add`
- `render.queue.start`
- `render.queue.pause`
- `render.queue.resume`
- `render.queue.cancel`
- `render.queue.retry_failed`
- `render.queue.clear_completed`
- `render.batch_export`
- `render.failure_diagnostics`
- `publish.capcut_review_model`
- `publish.quick_upload_package`
- `publish.collab_handoff`
- `publish.cloud_ready_package`
- `health.center_report`
- `health.media_report`
- `health.professional_readiness`
- `qa.dashboard_rows`
- `qa.run_selected`
- `qa.run_fast_suite`
- `qa.visual_capture`
- `qa.approve_visual_baseline`

## Safety and State Rules

- All actions must validate params before touching editor state.
- All mutating actions should support dry-run where practical.
- Destructive actions must expose `requires_review` or an explicit
  `confirm_destructive` parameter.
- Actions that mutate the editor should create one undo/history transaction per
  action or per sequence.
- Action sequences should be transactional where practical. If a later action
  fails, the result must clearly report which action failed and what state was
  changed before failure.
- Track, clip, node, actor, audio clip, subtitle, and render job identifiers
  must be stable enough for multi-step AI plans.
- Long-running actions should return a `job_id` and expose status via a matching
  status action.
- UI-only interactions should be converted to model operations whenever
  possible. Use UI automation only for smoke tests and screenshots.

## Implementation Order

1. Create `app/actions/schema.py`, `registry.py`, `result.py`, and a tiny
   `editor_adapter.py`.
2. Add read-only actions first: status, project snapshot, media summary,
   timeline summary, selected object, preset catalog.
3. Add low-risk mutating timeline actions: playhead, zoom, markers, select,
   import media, add track.
4. Add core edit actions: split, trim, ripple delete, delete, duplicate,
   set speed, fades, move/nudge.
5. Add preset/effect/transition/color/audio actions.
6. Add Screen Studio polish and node/mask actions.
7. Add actor actions for Live2D, Spine, VTuber, and AR/PBR. Keep Spine renderer
   quality flagged as separate risk.
8. Add render queue, publish, QA, health, and review capture actions.
9. Add MCP bridge tools:
   - `tigercapture_list_actions`
   - `tigercapture_get_action_schema`
   - `tigercapture_preview_action`
   - `tigercapture_execute_action`
   - `tigercapture_execute_sequence`
10. Update review automation to use the same action registry instead of bespoke
    UI scripts where possible.

## QA Requirements

Minimum scripted checks:

- registry loads and every action has a unique id.
- every action has a JSON-serializable schema.
- dry-run never mutates project state.
- destructive actions are blocked without review/confirmation.
- import/split/speed/filter/transition/render-queue smoke sequence works on a
  tiny fixture project.
- MCP list/schema/preview/execute calls match the Python registry behavior.
- review automation can call the registry for at least one editor demo capture.

## Handoff Summary

The main implementation thread should not start by widening MCP directly. Start
with the Python Action Registry, wrap current editor/model functions through an
adapter, then expose only registered actions to MCP and AI clients. This keeps
the system powerful enough for full studio automation while preserving the
current safety rule: no arbitrary Python, no arbitrary shell, and no direct
external access to editor internals.
