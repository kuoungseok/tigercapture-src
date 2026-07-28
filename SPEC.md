# TigerCapture Feature Spec for AI Agents

Last updated: 2026-07-28

This file is an AI-readable map of features discovered while working with the
user. Keep it current when behavior changes, especially for features that span
the editor UI, preview renderer, project save/load, and export.

## Repository Scratch Boundary

`debugCapture` is disposable QA scratch space. It may contain regenerated
reports, screenshots, proof frames, thumbnails, logs, and temporary caches, but
it must not be used as the default location for source media, OpenSeeFace CSVs,
descriptors, models, avatars, external tools, SDKs, or project state. Durable
sample inputs belong under `sample_assets` or `external/assets`; asset/tool
default changes should pass `tests/test_debug_capture_boundary.py`.

## AI Navigation Map

Start here when changing a feature:

- App entry / main shell: `main.py`, `app/main_window.py`, `app/controller.py`.
- Capture flow: `app/capture.py`, `app/region_selector.py`,
  `app/recent_captures.py`.
- Main video editor integration shell: `app/video_editor_window.py`.
  This file is now a compatibility facade and must not receive new feature
  logic, UI classes, dialogs, long QSS blocks, workflow methods, media handlers,
  or timeline behavior. Keep it to imports/re-exports, `__all__`, and tiny
  compatibility helpers. Add editor features in focused modules and wire them
  through `app/video_editor_window_delegates.py`, the relevant workflow
  controller, or `app/video_editor_window_initializer.py`.
  `tests/test_editor_architecture_rules.py` enforces this boundary.
  Current UI renewal work is already split across
  focused helpers:
  `app/video_editor_command_bar.py`,
  `app/video_editor_timeline_palette.py`,
  `app/video_editor_layout_specs.py`,
  `app/video_editor_ai_command_dock.py`,
  `app/video_editor_preset_browser_style.py`,
  `app/video_editor_preset_browser_widgets.py`,
  `app/video_editor_preset_cards.py`,
  `app/video_editor_popouts.py`,
  `app/video_editor_screenstudio_dialogs.py`, and
  `app/video_editor_audio_style.py`. Keep new bounded UI surfaces in focused
  modules instead of regrowing `video_editor_window.py`.
- Editor menu/item UX: `docs/SPEC_EDITOR_MENU_ITEM_SYSTEM.md`. The editor
  should stay item-first: keep the default chrome minimal, expose creation
  materials as draggable items, and keep feature controls in contextual docks
  instead of scattering permanent text buttons across the top bar.
- Timeline data model: `app/timeline_model.py`, plus legacy dataclasses still
  defined in `app/video_editor_window.py`.
- Preview renderer: `app/project_player.py`.
- Video export: `app/video_exporter.py`.
- Project save/load: `app/project_io.py`.
- Comparison templates and before/after preview planning:
  `docs/SPEC_COMPARISON_TEMPLATES.md`.
- Media pool: `app/media_pool.py`, shared still-image helpers in
  `app/image_media.py`.
- Character Asset Hub: `app/character_asset_hub.py`,
  `app/character_asset_hub_window.py`,
  `app/character_one_click_templates.py`,
  `app/actions/character_template_namespace.py`,
  `app/video_editor_character_asset_hub_workflow.py`,
  `tools/qa_character_asset_hub.py`, and
  `tests/test_character_asset_hub.py`,
  `tests/test_character_one_click_templates.py`. This is the subculture
  character-folder intake layer above Media Pool: a user can point it at a
  folder and receive Live2D/Spine/MMD/VRM classification, dependency
  diagnostics, thumbnail placeholders, render-readiness state, feature
  summaries, recommended transform/origin, existing public action payloads for
  timeline/avatar insertion, and one-click character result templates.
- Workbench / node graph: `app/workbench_panel.py`, `app/workbench/node_graph/*`.
- Masks and rotoscope: `app/node_mask.py`, `app/mask_editor_window.py`,
  `app/node_mask_dialogs.py`.
- Sound Editor and audio timeline: `app/audio_tracks.py`,
  `app/audio_separation.py`, `app/audio_mixer_panel.py`,
  `app/sound_editor_panel.py::SoundEditorPanel`,
  `app/sound_editor_panel.py::SoundEditorDockWindow`, and legacy advanced-lab
  `app/video_editor_window.py::SoundEditorWindow`.
- UI renewal and real-evidence review flow:
  `docs/SPEC_UI_RENEWAL.md`, `docs/UI_RENEWAL_THREAD_HANDOFF.md`, and
  `docs/UI_RENEWAL_EVIDENCE_INDEX.md`. Generated images may be design
  references only; product/review evidence must come from real running UI
  captures.
- Broadcast scene / VTuber sidecar contracts:
  `docs/SPEC_BROADCAST_SCENE.md`, `docs/SPEC_VTUBER_STUDIO_BROADCAST.md`, and
  `docs/SPEC_VSEEFACE_BRIDGE.md`. VSeeFace is optional external-sidecar
  integration; Program Output must remain usable through internal VRM fallback
  when the sidecar is absent or degraded.
- Repository maintainability and refactor guard:
  `docs/SPEC_REPO_MAINTAINABILITY.md`, `AGENTS.md`, and
  `tests/test_editor_architecture_rules.py`. New editor features belong in
  focused modules, not in the `app/video_editor_window.py` compatibility
  facade.
- Typography and subtitles: `app/typography.py`, `app/typo_animations.py`,
  `app/typo_render.py`, `app/subtitles.py`,
  `app/video_editor_window.py::TypographyEditorDialog`.
- Live2D: `app/live2d/*`.
- Spine and NIKKE: `app/spine_editor/*`.
- AR/PBR 3D compositor and real-time model preview:
  `docs/SPEC_AR_PBR_COMPOSITOR.md`, `app/ar_pbr/*`, `app/depth/*`,
  `app/camera_solve/*`, `tools/qa_ar_pbr_gpu_preview.py`,
  `tools/qa_ar_pbr_attachment_stability.py`, `tools/ar_pbr_scene_smoke.py`,
  `tests/test_ar_pbr_*.py`. Critical quick rule: the main viewer `Depth`
  toggle is diagnostic, off by default, and must not affect export/composite
  output. Normal playback must not run live depth estimation unless AR/PBR
  occlusion, scene/plane anchoring, or explicit depth-map viewing is active.
  Use `ProjectPlayer.set_ar_pbr_depth_view_mode(...)` or Actions
  `ar_pbr.preview.depth_view.get/set`; do not add parallel private toggles.
- General video processing: `app/video_filters.py`, `app/chroma_key.py`,
  `app/background_removal.py`, `app/video_stabilizer.py`,
  `app/video_decoder.py`.
- Loading/performance acceleration:
  `app/loading_performance.py`, `app/preview_acceleration.py`,
  `app/preview_engine_status.py`, `tools/qa_loading_performance.py`,
  `debugCapture/loading_performance.jsonl`.
- Professional color workflow helpers:
  `app/color_grading.py`, `app/color_scopes.py`, `app/color_workflow.py`,
  `app/color_management.py`, `app/color_ocio.py`.
- Professional audio workflow helpers:
  `app/audio_tracks.py`, `app/audio_workflow.py`, `app/audio_accuracy.py`,
  `app/audio_separation.py`.
- Shared UX status/empty/progress/failure copy:
  `app/ux_feedback.py`.
- Undo/history helpers: `app/history.py`.
- Export parity, UI QA, localization QA, and performance profiling:
  `docs/SPEC_EXPORT_PARITY_AND_QA.md`, `tools/verify_export_parity.py`,
  `tools/qa_project_audit.py`, `tools/qa_ui_layout.py`,
  `tools/qa_localization_audit.py`, `tools/qa_color_audio_accuracy.py`.
- Live2D/Spine corpus render QA:
  `tools/actor_compat_matrix.py`, `tools/actor_render_qa.py`,
  `tools/test_spine_resources.py`, `tools/test_live2d_resources.py`.
- Render queue, media relink, and editor presets:
  `app/render_queue.py`, `app/render_queue_panel.py`,
  `app/batch_export_dialog.py`,
  `app/media_relink.py`, `tools/relink_project_media.py`,
  `app/preset_library.py`, `tools/list_editor_presets.py`.
- Commercial expansion package:
  `app/commercial_expansion.py`, `tools/qa_commercial_expansion.py`.
- Public release positioning guardrails:
  `docs/RELEASE_POSITIONING.md`, `tools/qa_public_positioning.py`.
- CapCut-style creator workflow:
  `app/capcut_workflow.py`, `app/capcut_apply.py`,
  `tools/qa_capcut_creator_workflow.py`,
  `app/preset_library.py::CAPCUT_CREATOR_WORKFLOW_PRESETS`.
- CapCut parity gap tracking:
  `app/capcut_parity.py`, `tools/qa_capcut_parity_next.py`,
  `debugCapture/capcut_parity_next_qa.json`.
- CapCut publish review/provider contracts:
  `app/capcut_publish.py`, `tools/qa_capcut_publish_review.py`,
  `debugCapture/capcut_publish_review_qa.json`.
- CapCut quick-result recommendation/quality gate:
  `app/capcut_quick_result.py`, `tools/qa_capcut_quick_result.py`,
  `debugCapture/capcut_quick_result_qa.json`.
- CapCut captions/voice workflow:
  `app/capcut_voice.py`, `tools/qa_capcut_voice_workflow.py`,
  `debugCapture/capcut_voice_workflow_qa.json`.
- Subculture TTS / voice generation direction:
  `docs/SPEC_TTS_VOICE_LAB.md`, `app/tts_setup.py`, `app/tts_synthesis.py`,
  `app/tts_subtitle_workflow.py`, `app/tts_model_training.py`,
  `app/tts_lab.py`, `app/tts_kokoro.py`, `app/tts_gpt_sovits.py`,
  `app/actions/tts_namespace.py`, and `app/actions/editor_adapter_tts.py`.
  Local Style-Bert-VITS2 experiments currently live outside the repo at
  `D:\TTS\sbv2\Style-Bert-VITS2`. This folder is not a runtime dependency for
  the current editor build, but it is a product-direction asset for the planned
  subculture media creator studio. Do not treat it as disposable solely because
  the current source tree has no direct reference. Future integration should use
  an external sidecar/provider adapter instead of copying the AGPL engine into
  the closed editor source tree. Project subtitles can now route through
  `tts.subtitle.generate_to_timeline`, producing WAV media under
  `external/assets/tts/generated` and placing aligned clips on a dialogue audio
  track. The generation action checks the local endpoint first and, when the
  sidecar install is valid but the server is offline, starts `server_fastapi.py`
  automatically and waits for readiness before synthesis. Sidecar failure QA is
  covered by `tools/qa_tts_voice_lab.py`, which writes
  `debugCapture/voice_lab_sidecar_qa.json` and must return actionable
  `tigercapture.tts_sidecar.guidance.v1` recovery steps instead of raw
  connection errors. The QA Dashboard exposes this as `Voice Lab Sidecar` and
  intentionally runs it with `--auto-start --wait-timeout 120`, so project
  evaluation sessions that load video, create subtitles, synthesize TTS, and
  render video do not fail only because the installed local sidecar was not
  already running. Voice Lab also supports a selectable Kokoro local provider.
  Kokoro installs
  under `external/tools/tts/kokoro/.venv` with a Python 3.12 runtime because the
  current editor venv is Python 3.13 and Kokoro 0.9.x requires `<3.13`. The
  editor must not import Kokoro directly; `app.tts_kokoro` calls
  `tools/kokoro_synthesize.py` as a subprocess and keeps model/cache files under
  `external/tools/tts/kokoro/hf_cache`. Voice Lab exposes an Engine selector,
  voice list, install/connect actions, and skips Style-Bert server startup for
  Kokoro because it is a local subprocess provider. GPT-SoVITS is also exposed
  as an optional local reference-voice sidecar under
  `external/tools/tts/gpt-sovits`; `tools/install_gpt_sovits.py` clones the
  official `RVC-Boss/GPT-SoVITS` repository, while user reference audio,
  trained weights, and model caches stay outside Git. GPT-SoVITS is considered
  synthesis-ready only when a `voice_presets/*.json` entry points to an existing
  local `ref_audio_path`; subtitle/TTS generation then posts to the local
  `api_v2.py` `/tts` endpoint, defaulting to `http://127.0.0.1:9880`.
  Voice Lab's provider selector is a visible Voice Library catalog rather than
  a hidden setup choice: all known libraries stay listed, currently usable
  libraries sort first, unavailable libraries are muted gray, and selecting an
  unavailable library prompts for installation. Providers with safe install
  commands run in a background installer; catalog-only planned adapters such as
  Piper, Coqui XTTS, F5-TTS, CosyVoice, Fish Speech, OpenVoice, MeloTTS,
  ChatTTS, Bark, Edge TTS, ElevenLabs, and Azure Speech remain visible but fall
  back to the install plan and guide until their provider boundaries are
  implemented. The same list is exposed to automation as
  `tts.voice_library.catalog` so AI/MCP workflows can discover ready,
  unavailable, and planned libraries without scraping the UI view model.
  TTS subtitle timing can now be baked to Live2D mouth and
  natural blink parameters through `tts.subtitle.apply_actor_lipsync`, or in
  the same generation call by passing `apply_actor_lipsync=true` plus an actor
  target. AI Dialogue Take is the higher-level path for raw dialogue text:
  `tts.dialogue.plan_actor_take` returns selectable Live2D targets, TTS voices,
  placement presets, size presets, and recommended defaults; then
  `tts.dialogue.generate_actor_take` creates subtitles, generated WAV media,
  Live2D mouth/blink keyframes, lower-corner actor placement, and default
  natural dialogue motion in one operation. If the user does not choose
  anything, it defaults to the selected or first timeline Live2D actor, the
  preferred TTS voice such as `koharune-ami`, and `bottom_right` / `auto_fit` with
  `apply_actor_motion=true`. If the chosen Live2D target is a media-pool
  `.model3.json` asset, the action creates the actor clip before applying TTS,
  placement, and natural head/body/breath/arm motion. When a Live2D model has
  multiple authored `.motion3.json` entries, the dialogue take also applies an
  authored motion storyboard after TTS lip-sync: it splits the actor clip into
  dialogue-line ranges, assigns suitable model motions by label/intent, and
  preserves sliced mouth/blink/parameter keys on the new clips. TTS dialogue
  rows can separate spoken text from rendered subtitles: `tts_text` /
  `spoken_text` is sent to the voice sidecar, while `subtitle_text` /
  `display_text` is rendered on video. For quick AI/user input, a line such as
  `Japanese => Korean` produces Japanese voice synthesis and Korean on-screen
  subtitles.
  Voice Lab also has a local Model Maker bridge for creating additional
  Style-Bert-VITS2 voices like the user's trained `zoe` model: actions
  `tts.model.training.plan`, `tts.model.training.execution_gate`,
  `tts.model.training.prepare_workspace`,
  `tts.model.training.launch_dataset`, `tts.model.training.launch_train`, and
  `tts.model.training.register_result` prepare `Data/<model>/raw`, launch the
  upstream Dataset/Train Gradio tools, and validate completed
  `model_assets/<model>` folders. The training engine remains an external
  sidecar; do not import the PyTorch/AGPL training stack into the editor
  process or copy it into the closed source tree.
- CapCut local collaboration handoff:
  `app/capcut_collaboration.py`, `tools/qa_capcut_collab_handoff.py`,
  `debugCapture/capcut_collab_handoff_qa.json`.
- CapCut cloud/share handoff contract:
  `app/capcut_cloud_handoff.py`, `tools/qa_capcut_cloud_handoff.py`,
  `debugCapture/capcut_cloud_handoff_qa.json`.
- CapCut prompt-to-edit fallback:
  `app/capcut_prompt_edit.py`, `tools/qa_capcut_prompt_edit.py`,
  `debugCapture/capcut_prompt_edit_qa.json`.
- Creator asset-pack catalog:
  `app/creator_asset_packs.py`, `tools/qa_creator_asset_packs.py`,
  `debugCapture/creator_asset_packs_qa.json`.
- Review/demo automation sample resources:
  `docs/SPEC_REVIEW_AUTOMATION.md`, `app/review_automation/*`,
  `tools/prepare_review_sample_resources.py`,
  `tools/review_automation_launcher.py`,
  `tools/generate_review_assets.py`, `tools/build_review_site.py`,
  `tools/build_review_deck.py`, `tools/qa_review_automation.py`,
  `../ReviewAutomationWorkspace/samples/manifest.json`,
  `../ReviewAutomationWorkspace/qa/review_sample_resources_qa.json`,
  `../ReviewAutomationWorkspace/outputs/review_report.json`,
  `../ReviewAutomationWorkspace/outputs/site/index.html`,
  `../ReviewAutomationWorkspace/outputs/site/features/*.html`,
  `../ReviewAutomationWorkspace/qa/review_automation_qa.json`,
  `../ReviewAutomationWorkspace/outputs/TigerCapture_Review_Automation.pptx`,
  `../ReviewAutomationWorkspace/outputs/TigerCapture_Review_Automation_detailed.pptx`,
  `../ReviewAutomationWorkspace/outputs/TigerCapture_Review_Automation_evidence_full.pptx`.
  The review automation workspace is developer-only and can be moved with
  `TIGERCAPTURE_REVIEW_ROOT`.
- User PPT generator and timeline-native presentation authoring:
  `docs/SPEC_USER_PPT_GENERATOR.md`, `app/pptgen/*`,
  `app/video_editor_ppt_workflow.py`, `app/actions/ppt_namespace.py`,
  `app/actions/editor_adapter_ppt.py`, `tools/pptgen.py`,
  `tools/qa_ppt_animation_compat.py`, and `tests/test_pptgen_*.py`.
  This feature is separate from review automation. It creates user decks from
  templates, media-pool/timeline/typography/3D assets, current timeline stills,
  document tools, and AI-editable `ppt.*` actions. The current animation MVP
  stores simple element effects (`appear`, `fade_in`, `fade_out`, `move`,
  `scale`), previews them on the PPT canvas/timeline, exports PowerPoint-
  compatible `.pptx` files through `app/pptgen/writer_python_pptx.py`
  (`python-pptx` plus targeted timing OOXML patches), and has a compatibility
  QA generator:
  `python tools/qa_ppt_animation_compat.py --out-dir debugCapture/ppt_animation_compat`.
  Project automation now covers `.tgppt` create/open/save/save-as plus
  editable deck creation from prompts and the current editor timeline through
  `ppt.project.*`, `ppt.deck.from_prompt`, and `ppt.deck.from_timeline`.
  PDF export is implemented in `app/pptgen/pdf_export.py` and is available
  from the PPT editor, `tools/pptgen.py --export-sample --export-pdf`, and the
  `ppt.timeline.export_pdf` action. The backend contract is `auto`
  (LibreOffice first, PowerPoint COM on Windows second), `libreoffice`, or
  `powerpoint_com`.
  MP4 presentation video export is implemented in `app/pptgen/video_export.py`
  using the shared Qt-free animation runtime in
  `app/pptgen/animation_runtime.py`; the same playhead-aware renderer now drives
  PPT canvas preview and H.264 MP4 frame generation through bundled FFmpeg. It
  is available from the PPT editor, `tools/pptgen.py --export-sample
  --export-video`, and the `ppt.timeline.export_video` action. Optional
  narration/soundtrack mux is supported through explicit `audio_path`, deck
  metadata (`narration_audio_path`, `audio_path`, or `soundtrack_path`), and
  CLI `--video-audio`; FFmpeg encodes it as AAC, pads short audio, and trims
  long audio to the video duration. In the PPT editor, MP4 export runs through
  `app/pptgen/ui/video_export_worker.py` on a background `QThread` with
  progress and cancellation. CLI/action exports remain synchronous from the
  caller's perspective. Current limits:
  render-queue integration for unattended batch jobs and narration
  recording/editing/loudness UI remain pending.
  Slide transitions are MVP-level: `cut` and the `fade` family
  (`dissolve`/`crossfade` aliases) render in MP4 without changing total deck
  duration; richer wipes, directional moves, zooms, and PowerPoint-native
  transition parity remain pending.
  Document-edit basics now include selected-element copy/paste/duplicate,
  front/back layer order, and slide-bound alignment controls in the PPT editor,
  with automation coverage through `ppt.element.duplicate`,
  `ppt.element.z_order`, and `ppt.element.align`.
  PPTX import MVP is implemented in `app/pptgen/import_pptx.py` and available
  through the PPT editor `Import` command plus `ppt.deck.import_pptx`; it
  imports text boxes, tables, pictures, and simple shapes as editable deck
  elements and extracts pictures into deck assets. It is best-effort and does
  not yet preserve masters, SmartArt, charts, embedded media, animations, or
  complex theme inheritance.
  PPT media/3D actors (`video_actor`, `ar_pbr_actor`, `vrm_actor`, `mmd_actor`,
  `audio_actor`, `media_actor`) now share a poster fallback contract:
  `poster_path`, `thumbnail_path`, `preview_path`, or `render_path` metadata is
  used by canvas/PNG/MP4 preview and `writer_python_pptx.py`; missing posters
  export as styled actor cards instead of blank content. `app/pptgen/actor_posters.py`
  generates cached posters on actor insertion and export: video actors try a
  source-frame still first, while 3D/MMD/audio/media actors receive
  deterministic fallback card posters. Automation can refresh this cache through
  `ppt.deck.actor_posters.generate`.
  Export-readiness validation is exposed through `ppt.deck.validate` and
  returns `tigercapture.ppt.validation.v1` with error/warning/info counts plus
  per-issue slide/element ids for AI repair loops.
  Current-deck export actions `ppt.deck.export_pptx`, `ppt.deck.export_pdf`,
  and `ppt.deck.export_video` operate on the open PPT editor deck and run actor
  poster preflight before writing. Timeline export actions remain separate and
  derive a draft deck from the main editor timeline.
  Slide-level automation now covers add, duplicate, remove, move, update, and
  focused layout/duration/notes setters through `ppt.slide.*` actions, backed by
  Qt-free helpers in `app/pptgen/editing.py`.
  PPT edit safety is implemented with Qt-free deck snapshots in
  `app/pptgen/history.py` and recovery writes in `app/pptgen/autosave.py`.
  The PPT editor exposes Undo/Redo command buttons, standard shortcuts, dirty
  title markers, and timed `.autosave.tgppt` recovery copies. Automation can
  inspect and drive the same safety surface through `ppt.deck.history`,
  `ppt.deck.undo`, `ppt.deck.redo`, and `ppt.deck.autosave`. Recovery copies
  can be listed and opened through the editor `Recovery` command and Actions
  `ppt.deck.recovery.list/open`; opening a recovery copy loads it as an unsaved
  dirty deck to protect the autosave file from accidental overwrite. Dirty decks
  prompt Save/Discard/Cancel before destructive deck replacement or close.
  Successful Save deletes the relevant `.autosave.tgppt` copy, and
  `ppt.deck.recovery.delete` refuses to delete non-recovery files.
  The PPT workspace media pool is implemented through `app/pptgen/assets.py`
  and `app/pptgen/ui/media_panel.py`, stores deck-local asset records in
  `DeckSpec.assets`, supports file add/drag/insert/remove in the PPT editor,
  and exposes `ppt.media_pool.list/add/insert/remove` actions.
  Chart elements now export through `writer_python_pptx.py` as native
  PowerPoint chart parts plus embedded workbook data, while the editor canvas
  and PNG path keep using TigerCapture's vector chart preview. The native chart
  export was host-smoked through PowerPoint COM at
  `debugCapture/pptgen_chart_export/native_chart.pptx` and
  `debugCapture/pptgen_chart_export/native_chart.pdf`.
  The selected-slide animation timing lane is implemented in
  `app/pptgen/animation_lanes.py` and `app/pptgen/ui/animation_lane.py`;
  clicking a lane selects that element and moves the local slide playhead,
  dragging a lane moves its start time, and dragging either edge trims start or
  duration within the slide bounds. On-click animations carry
  `AnimationSpec.click_index`; the inspector exposes `Click #`, lanes show
  `#n` badges with automatic sequence numbers for legacy click animations, and
  animation export order follows click sequence. Automation can inspect rows
  through `ppt.animation_lanes.list`. The click sequence path was host-smoked at
  `debugCapture/ppt_animation_click_sequence/manifest.json`.
  The QA output includes `.pptx`, `.tgppt`, PNG previews, a contact sheet, and
  `manifest.json` with OOXML static checks plus manual PowerPoint/LibreOffice
  verification steps. The broader export pipeline smoke runner is
  `tools/qa_ppt_export_pipeline.py`; it writes `.pptx`, slide PNGs, a contact
  sheet, optional PDF, optional MP4, and a `tigercapture.ppt.export_qa.v1`
  manifest for regression review. Product-readiness QA now lives in
  `app/pptgen/product_readiness.py` and `tools/qa_ppt_product_readiness.py`;
  it builds five real authoring scenarios (templates, document/chart tools,
  prompt decks, media/3D actors, and animation timeline), verifies project
  save/load, validation, PPTX, PNG/contact-sheet output, optional MP4 output,
  and writes a `tigercapture.ppt.product_readiness.v1` manifest.
  Release-acceptance QA now covers the first four productization gates through
  `app/pptgen/release_acceptance.py` and
  `tools/qa_ppt_release_acceptance.py`: Office compatibility static inspection
  plus optional LibreOffice/PowerPoint COM host conversion, editor workflow
  MIME/drop simulation on the real `SlideCanvas`, long-session save/autosave/
  undo/redo stability, and PNG-vs-MP4 first-frame parity. The current host run
  at `debugCapture/ppt_release_acceptance/manifest.json` passed all four gates;
  LibreOffice was not installed, PowerPoint COM conversion passed, and parity
  mean absolute difference was below the configured threshold.
- Studio-wide Python Action System implementation:
  `app/actions/*`, `docs/SPEC_PYTHON_ACTION_SYSTEM.md`. The registered action
  layer now backs AI, MCP/local-LLM handoff, QA, review automation, and
  developer tools through validated action specs. It wraps editor/model
  capabilities through `EditorAdapter` instead of exposing arbitrary Python or
  private editor methods directly. The current default registry exposes 426
  unique action IDs, including timeline/NLE actions, node graph actions,
  VTuber Performance Source actions, Live2D Performance Source retargeting,
  MMD actor/QA actions, capture evidence actions, and Music Lab / MIDI
  composition actions.
  Action registration is intentionally split by namespace; AR/PBR preview/
  depth/surface actions live behind `app/actions/ar_pbr_preview_namespace.py`,
  AR/PBR gizmo actions behind `app/actions/ar_pbr_gizmo_namespace.py`, and
  legacy callers continue through the `app/actions/ar_pbr_namespace.py`
  facade.
- Local-first ML backend:
  `app/local_ml.py`, `tools/qa_local_ml_backend.py`.
- AI Script / One-Click Editing foundation:
  `docs/SPEC_AI_TEXT_EDITING.md`, `app/ai_edit_plan.py`,
  `app/ai_text_editing.py`, `tools/qa_ai_text_editing.py`,
  `app/descript_lite_readiness.py`, `tools/qa_descript_lite_readiness.py`,
  `app/descript_lite_implementation_plan.py`,
  `tools/qa_descript_lite_implementation_plan.py`,
  `app/transcript_reflow.py`, `app/transcript_timeline_ops.py`,
  `app/transcript_selection_actions.py`, `app/transcript_edit_surface.py`,
  `app/transcription_providers.py`, `app/transcript_cleanup.py`,
  `app/transcription_settings.py`, `app/transcription_runtime_setup.py`,
  `app/retake_detection.py`,
  `app/speech_enhance.py`, `app/ai_voice_replacement.py`,
  `tools/qa_descript_lite_p1_services.py`,
  `tools/qa_descript_lite_p2_transcription.py`,
  `tools/configure_local_whisper_model.py`,
  `tools/qa_transcription_runtime_setup.py`,
  `tools/qa_descript_lite_p3_cleanup.py`,
  `tools/qa_speech_enhance.py`,
  `tools/qa_ai_voice_replacement.py`,
  `debugCapture/ai_text_editing_qa.json`,
  `debugCapture/descript_lite_readiness_qa.json`,
  `debugCapture/descript_lite_implementation_plan_qa.json`,
  `debugCapture/descript_lite_p1_services_qa.json`,
  `debugCapture/descript_lite_p2_transcription_qa.json`,
  `debugCapture/transcription_settings_configure_qa.json`,
  `debugCapture/transcription_runtime_setup_qa.json`,
  `debugCapture/descript_lite_p3_cleanup_qa.json`,
  `debugCapture/speech_enhance_qa.json`,
  `debugCapture/ai_voice_replacement_qa.json`.
- AI Composer / Music Lab foundation:
  `docs/SPEC_AI_COMPOSER_MUSIC_LAB.md`, `app/music_composer.py`,
  `app/actions/music_namespace.py`, `app/actions/editor_adapter_music.py`, and
  `tests/test_music_composer_actions.py`. The first implementation is
  structured-note based and deterministic: `music.compose` creates structured
  sections, tracks, clips, and notes; `music.render.preview` renders a local
  WAV preview mix and can skip per-role stem WAVs with `render_stems=false`; and
  `music.render_to_timeline` places rendered stems on real `AudioTrack` rows for
  the existing Sound Editor mixer/export/action stack. `update_existing=true`
  refreshes matching Music Lab composition/role tracks in place, and
  `music.export_midi` remains an optional interchange export rather than the
  default sound-tuning output. `music.compose_to_timeline` is the
  natural-language entry action, clear music edit prompts route to
  regenerate/mute/export actions, and the Workbench Sound Editor now includes a
  compact `Music Lab` tab for prompt-to-timeline and update.
  Composer sound shaping must reuse the Sound Editor effect model instead of
  duplicating a second audio stack: `music.apply_master_fx` finds rendered Music
  Mix/stem `AudioClip` rows by composition/role and merges Sound Editor
  `AudioClip.effects` payloads, while the Composer `Master FX` card is only a
  thin UI wrapper over AI Master, reverb/space, and loudness controls.
  Non-orchestral Music Lab generation now uses a 9-channel default baseline:
  drums, bass, bass pulse, pad/chords, arp, lead, answer lead, counter melody,
  and FX. Melodic EDM/NCS-style prompts use the same 9-channel layout with
  EDM-tuned labels and layer balances rather than the old four-track sketch.
  Music Lab chord progressions are key-aware, and long EDM/NCS prompts use
  intro/build/drop/breakdown/drop2 section plans with alternate breakdown and
  second-drop progressions to avoid a single repeated loop. Melody generation
  now uses an internal 8/16-bar phrase planner with A, A-prime, B, hook, and
  bridge labels, phrase memory, repetition scoring, chord-tone cadences, and
  separate lead/answer/counter roles instead of cycling the same short motif.
  Classical/Paganini/solo-violin prompts are a separate variation-planner path,
  documented in `docs/SPEC_CLASSICAL_VARIATION_COMPOSER.md`. They route before
  generic orchestral detection, keep `solo_violin` as the protagonist, vary a
  degree-based motif across theme/rhythmic/lyrical/climax/coda sections, and
  keep heavy roles such as brass, timpani, and cymbals silent until the climax.
  Genre-specific deterministic planners are documented in
  `docs/SPEC_GENRE_COMPOSER_PLANNERS.md`: lofi, rock/metal, jazz,
  hiphop/trap, synthwave, and ambient prompts now replace the default BGM
  sketch with dedicated section plans and track roles such as dusty drums,
  palm-muted/power-chord guitars, swing drums, walking bass, 808 bass, retro
  drums, pulse bass, and drumless ambient pads. Classical and orchestral routes
  still take priority, while unmatched non-orchestral prompts continue to use
  the 9-channel baseline.
  Music Lab renderer tiers are now explicit. The basic/default user-facing
  output is sample/SoundFont-based `backend=sample_production` with
  `sample_library_policy=auto`; advanced AI/production output is selected only
  by explicit provider/backend choice such as Stable Audio 3.0, ACE-Step, LMMS,
  or `backend=production`. Auto/basic rendering must not silently switch to AI
  just because a provider is configured. One-click AI music requests use the
  sample-production studio master profile
  `one_click_sample_production_studio_v1`, which records bus tone shaping,
  rumble/mud control, presence/air, room ambience, mid-side width, parallel
  glue compression, dropout/surge repair, sample-jump smoothing, and soft
  preview limiting in `render_backend.studio_mastering`. The same default
  route records `sample_production_articulation_expression_v1` in
  `render_backend.performance_profile`; it classifies notes by role/length,
  shapes short-note gates, writes CC1/CC11 expression automation for SoundFont
  renders, and shapes internal fallback envelopes. The same route now records
  `music_audio_output_safety_v1` in `render_backend.audio_safety`; final
  sample-production mixes and stems run a post-master safety guard for sample
  jumps, isolated 5/10/25ms dropouts, short surges, and final peak ceiling.
  Fast `classical_solo_violin` lead buses bypass General MIDI/SoundFont lead
  programs and use `procedural_clean_violin` because the SoundFont violin can
  sound broken on dense Paganini-style passages even when hard glitch metrics
  are clean. `tigerstudio.local_synth.v5` is
  `diagnostic_only`; `tigerstudio.studio_edm.v1` is `draft_sketch`;
  `fluidsynth.soundfont.v1` is `starter_preview`;
  `tigerstudio.sample_production.v1` is
  `enhanced_local_preview`; and only a configured external production renderer
  can be reported as `production_candidate`. The built-in renderers are useful
  for timing, arrangement, MIDI export, and workflow validation, but must not be
  claimed as modern release-quality music. `backend=sample_production` is the
  non-AI quality step above draft renderers: it groups roles into bus stems,
  applies bus tone shaping, cinematic ambience, stereo width, and a glue/master
  stage, then repairs short energy dips, clicky sample jumps, low resonance,
  narrow tonal whine, excess 10-25ms onset surges, and render-time timing
  jitter while using continuity-safe bass phrasing/tails to avoid low-end
  "tape chewing" artifacts. It still remains below AI/DAW-grade sample-library
  output. Sample-production now uses a sample-library-first policy. The
  percussion bus tries SFZ/DecentSampler/manifest drum kits from
  `external/assets/music/drum_kits`, then SoundFont/FluidSynth, then procedural
  synth/noise fallback. Non-percussion buses (`low`, `orchestra`, `pads`,
  `lead`, `fx`) also try SoundFont/FluidSynth stem rendering before procedural
  synthesis. This avoids presenting old FM/GM-like synthesized drums or
  calculated oscillator parts as the best local preview; backend status exposes
  `drum_sample_kit_ready`, `drum_sample_kits`,
  `sample_production_percussion`, `sample_production_bus_policy`,
  `sample_library_choices`, `sample_library_install_dirs`, and
  `recommended_sample_libraries`, and
  renders record `sample_library_policy`, `bus_renderers`,
  `external_bus_count`, `procedural_buses`, `percussion_source`, and
  `percussion_renderer` metadata. Music Lab accepts
  `sample_library_policy=auto|sample_kit_first|soundfont_only|procedural_only`
  plus optional `soundfont_path` and `drum_kit_path`, so UI, Claude, and local
  AI can choose whether sample-production uses user-installed drum kits,
  SoundFonts only, or diagnostic synth fallback for comparison. Sample packs,
  model weights, and licensed libraries are not bundled with TigerCapture:
  users install them under `external/assets/music`, the local
  `external/assets/music/README.md` guide explains the folder layout, and the
  compact Workbench Music Lab UI exposes `Assets` / `Guide` buttons plus
  discovered drum-kit/SoundFont counts. Natural-language AI composition
  requests such as "make a 30s BGM" default to
  `music.compose_to_timeline(backend=sample_production,
  sample_library_policy=auto)`, while explicit provider phrases such as Stable
  Audio 3.0 / ACE-Step / LMMS select `backend=production` with the matching
  `ai_provider` and `create_mix=true`. Follow-up AI edits inherit the current
  composition's render backend and sample policy so section regeneration does
  not fall back to a lower-quality renderer. The old local synth path remains
  explicit diagnostic-only and must not be presented as a useful output path.
  Metal-oriented sketch roles
  (`rhythm_guitar_*`, `lead_guitar_*`, `power_chord_guitar_*`,
  `palm_mute_guitar_*`) map to the sample-production lead bus and SoundFont
  overdrive/distortion guitar programs.
  `tools/music_audio_glitch_probe.py` is the required local diagnostic
  for this path before more audio-render guesses are made: it writes JSON/CSV
  reports for sample jumps, short frame drops/surges, spectral wobble
  candidates, separate hard-glitch/spectral-motion/envelope-pumping diagnostics,
  and optional conservative repaired WAVs. `glitch_score` is reserved for hard
  audio defects; spectral wobble remains a candidate list because normal musical
  bass/chord motion can trigger it. When the user reports "huffing" or "훅 훅",
  rerun the probe with `--bpm` and inspect `envelope_pumping`, especially
  beat-rate peak-to-peak dB. A zero `glitch_score` is not enough to pass this
  case if kick/percussion or sidechain-style gain motion is still moving the
  whole mix. Those probe reports and scratch repairs may live in `debugCapture`;
  source assets, SDKs, and durable renderer dependencies must not. For
  elimination testing, run `tools/music_render_stage_probe.py`; it renders
  `00_dry_note_mix`, `01_shaped_stem_mix`,
  `02_bus_polish_no_spatial_mix`, `03_bus_spatial_gain_mix`,
  `04_master_no_micro_mix`, and `05_master_full_mix`, each with a probe report,
  plus `dry_no_drums_mix` and `dry_drums_only_mix` ablations, so agents can
  identify the first stage or role family that introduces cutting or pumping.
  The tool also writes `*_playback_safe_48k.wav` companions for listening
  checks; measure the normal WAV/report, but use playback-safe copies when
  player/device buffering is suspected. Playback-safe companions must be only
  48 kHz conversion plus peak normalization. Do not add warm-up beds, pre-roll,
  synthetic noise floors, or extra stability padding: the 2026-07-10
  `playback_safe_v4` probe added a warm-up bed and created a false audible cut
  in an otherwise clean no-drums render. If a playback-safe copy fails while
  the measured WAV/report is clean, fix the companion generator first instead
  of guessing at the composer, drum, bass, or master stages.
  `backend=production` requires a renderer under `external/tools/music_renderer` or
  `TIGERCAPTURE_MUSIC_PRODUCTION_RENDERER_EXE`; if missing, it fails loudly
  instead of silently producing draft/starter audio.
  The current production bridge is `tools/music_production_renderer.py`,
  configured by `external/tools/music_renderer/renderer.json`, and routes Music
  Lab composition JSON to configured AI providers such as ACE-Step API before
  falling back to `tools/lmms_music_renderer.py` and
  `external/tools/lmms/app/lmms.exe`. Stable Audio 3.0 is also wired through
  that same production bridge as provider `stable_audio_3`: the default
  implementation calls the public `stabilityai/stable-audio-3` Hugging Face
  Space with `gradio_client`, uses the `small-music` variant by default, and
  writes the returned 44.1 kHz stereo WAV to the normal renderer output path.
  It stays disabled in `external/tools/music_renderer/provider.json` by
  default because prompts/audio requests leave the local machine; when the user
  explicitly chooses it, set `TIGERCAPTURE_MUSIC_AI_PROVIDER=stable_audio_3` or
  enable the `stable_audio_3` provider in that config. Explicit Stable Audio
  selection must override the disabled default instead of silently falling back
  to LMMS, while `auto` should keep local/offline fallbacks unless the provider
  is intentionally enabled. The compact Workbench Music Lab UI now exposes an
  `AI provider` selector with `AI auto`, `Stable Audio 3.0`, `ACE-Step`, and
  `LMMS offline`; explicit provider choices send `ai_provider` through
  `music.compose_to_timeline`, `music.render.preview`, and
  `music.render_to_timeline`, switch the backend to `production`, and force
  `mix only` because the current production bridge returns a stereo WAV mix
  rather than editable stems.
  Orchestral/symphonic/trailer-score prompts now expand to 128 deterministic
  internal composition tracks: strings divisi, woodwinds, brass, timpani,
  orchestral percussion, cymbal/FX, choir, and hybrid pads. Each orchestral
  track keeps a unique role id so Music Lab can render or export true separated
  parts instead of a four-track sketch.
  `.tgp` project save/load persists `music_compositions[]` plus music
  composition/role metadata on generated audio tracks and clips.
  2026-07-10 stabilization note: sample-production stems are bus stems, not
  necessarily the original composition role names. The percussion/drum output
  should be addressed through the `percussion` bus stem in project-IO and
  timeline-link tests rather than assuming a legacy `drums` rendered stem.
- Native worker protocol and migration strategy:
  `docs/SPEC_NATIVE_WORKER.md`, `app/native_worker.py`,
  `native/tigercapture_worker/src/main.rs`.

## Quick Answers

- NIKKE character assets are Spine assets, not Live2D and not "spline".
- Arbitrary object tracking is implemented through tracked `BitmapMask` masks:
  the user draws/selects any region, and OpenCV CSRT tracks that region by bbox.
  `app.tracking_cache_worker.ObjectTrackingCacheWorker` can pre-warm those
  tracker bbox caches in the background for the active node chain.
- The Color page Rotoscope menu and the node graph mask context menu expose
  "Track selected region"; it opens `MaskEditorWindow` with `Track object`
  enabled. Track rows show tracked-mask cache/failure/correction status and
  approximate failed-frame ticks.
- Masked effects are not blur-only in preview. The preview node chain applies
  masks to blur nodes, effect nodes, and color-grading nodes.
- The export path now has a preview-effect raw pre-render fallback for active
  `track.node_item_chain` data. When node graph blur/effect/color/mask work
  cannot be represented by FFmpeg, export bakes those frames through Python
  before applying the normal FFmpeg overlays/audio.
- Spine and Live2D actor tracks are baked into final video as transparent MOV
  overlays. Live2D must be added both to the overlay spec and to the FFmpeg
  input list.
- AR/PBR 3D object compositing is now a first-class tracked feature. The
  formal renderer contract is `docs/SPEC_AR_PBR_COMPOSITOR.md`. ProjectPlayer
  owns preview integration, Project I/O owns AR/PBR track persistence, Media
  Pool recognizes FBX/GLB/3D assets, and VideoExporter owns final bake hooks.
  Current behavior is hybrid: the main GL preview receives `ar_pbr_items`
  metadata from `ProjectPlayer` and draws shaded mesh triangles directly in
  `OpenGLPreviewWidget`; export now uses the same GPU-preview packet contract
  through `app.ar_pbr.export_packet_renderer` before falling back to
  `software_pbr` only when packet rendering cannot draw a track. The GPU
  packet path includes lightweight contact-shadow and screen-reflection catcher
  packets (`shadow_vertices`, `reflection_vertices`) and sorts mesh triangles
  back-to-front for more stable overlap. Export rasterizes those packets onto a
  transparent overlay with configurable packet SSAA
  (`TIGERCAPTURE_AR_PBR_PACKET_SSAA`, default `2`) before compositing back over
  the source frame, so edge smoothing does not resample the original video. It
  also shares `app.ar_pbr.texture_plan` with the model-view loader so material
  texture readiness is diagnosed consistently; when a base texture map is
  available, the preview packet path applies its cached average color as a
  lightweight fallback tint and also emits UV texture-triangle packets plus GL
  preview `pbr_triangles` containing projected position, UV, normal, tangent,
  bitangent, base color, material roughness/metallic/reflectance values,
  roughness/metallic/specular/normal/occlusion map paths, packed-channel
  selectors for glTF metallic-roughness/AO textures, and HDRI lighting metadata.
  `OpenGLPreviewWidget` draws those PBR triangles with a model-view-style
  material-map/HDRI fragment shader over the same contact-shadow/reflection
  packet fallback. Textured/PBR triangles keep their live depth texture so the
  GL fragment shader can discard occluded pixels instead of the packet builder
  coarse-culling the whole triangle. Headless
  export samples the UV texture triangles with affine UV mapping before
  encoding, so textured materials are no longer represented only as a flat
  material color in final MP4 output. It also mirrors AO map darkening and
  item-depth texture masking for packet export. Video-depth occlusion is now a
  shared contract across synthetic/software, packet PBR, GL preview, and the
  worker-safe full GPU helper: tracks must set `occlusion=true`, depth frames
  are normalized through `app.ar_pbr.depth_occlusion`, and successful paths
  report `pbr_depth_occlusion_applied` plus `pbr_depth_occluded_pixels`. The
  main viewer also has a user-controlled depth-map-only diagnostic mode through
  the `Depth` preview toggle, `ProjectPlayer.set_ar_pbr_depth_view_mode(...)`,
  and Python Actions `ar_pbr.preview.depth_view.get/set`. When a reference RGB
  frame is available, the diagnostic viewer exposes `matte`, `distance`, and
  `plane` checks: matte uses layered refinement for clean object bands,
  distance keeps a smooth gradient with contours for distance/slope reading,
  and plane overlays rough road/floor candidates for placement inspection. The
  actual export/composite depth remains a smooth occlusion map. This mode is
  off by default and must not change export output. Normal playback must not
  estimate depth unless an active AR/PBR track explicitly needs depth for
  occlusion, scene/plane anchoring, or the user has enabled the Depth viewer
  toggle. If no depth cache is available, live depth estimation is an
  intentional diagnostic or placement cost, not part of the baseline video
  playback path. The
  full GPU service bridge serializes the current `depth_frame` as a temporary
  float32 `.npy` payload and the helper applies an overlay alpha depth matte
  before compositing; this prevents export from losing video-depth occlusion,
  but it remains an overlay-matte approximation rather than a native
  model-depth buffer compare inside the helper renderer. It
  also resolves road-plane/scene anchor placement before creating packets, so
  QImage fallback, GL preview, and export agree on where a model should stick to
  the video surface. The timeline AR/PBR lane status badge is intentionally
  metadata-only: `3D` means manual 3D placement, `ANCH` means depth/plane
  anchored placement, and `TRK` means the anchored track has tracking metadata.
  The badge must not enable Depth view or trigger live depth estimation by
  itself. Encoded letterbox/pillarbox matte bands are detected from the RGB
  video frame and excluded from depth normalization and diagnostic
  matte/distance/plane inspection; they are not valid scene depth, road/floor,
  or occlusion evidence. The same encoded matte bands are preserved through
  CPU preview/export color grading and node effects so grade/effect pixels do
  not recolor black bars; legacy color-grade export falls back to CPU prerender
  when the source has encoded mattes. Worker-safe export-side model-view GPU
  rendering now exists through the helper process below; remaining renderer work is quality depth: real
  shadow-map passes, physically richer reflections, IBL prefilter tuning,
  batching, and camera/lens solve fidelity.
  Image-to-material work is covered by the AR/PBR Texture Lab: core generation
  lives in `app.ar_pbr.texture_map_lab`, the Qt plane-preview/sliders live in
  `app.ar_pbr.texture_map_lab_window`, and automation is exposed through
  `ar_pbr.texture_lab.open/preview/backend_status/export/substrate_plan`. It turns a source
  image into previewable PBR maps, exports separate BaseColor/Normal/AO/
  Roughness/Metallic/Height/Cavity/Curvature maps, and writes
  `unreal_orm`/`orm`/`arm` packed masks with R=AO, G=Roughness, B=Metallic
  plus `gltf_mr` with G=Roughness, B=Metallic. Optional advanced Substrate
  exports can also include an `f0` RGB map and `f90_mask` grayscale mask, but
  they are disabled by default because most materials should use constants or
  the Metalness-To-DiffuseAlbedo-F0 helper. Unreal Substrate does not require a different
  source texture set for the base workflow; the manifest records a Substrate
  graph plan that feeds BaseColor/Specular/Metallic through Unreal's
  `Substrate Metalness-To-DiffuseAlbedo-F0` helper and wires the result into a
  Slab BSDF `DiffuseAlbedo/F0`, while Roughness and Normal go directly to the
  Slab and AO remains a material/root occlusion input. Advanced Substrate maps
  such as second roughness, anisotropy/tangent, fuzz, and glint remain future
  optional generators rather than guessed from a single image.
  Texture Lab preview must avoid full-resolution PNG round trips where an
  in-memory source is available, cache generated maps by source/settings
  fingerprint, and re-shade preview-only light changes without regenerating
  height/normal/AO maps. The user-facing lab supports both `plane` and
  `sphere` material preview shapes so artists can inspect flat texture response
  and curved-lighting response without leaving the tool; generated channel
  labels and thumbnail labels must stay large enough to read in normal editor
  screenshots. `TIGERCAPTURE_TEXTURE_LAB_BACKEND=auto|cpu|torch_cuda|
  cupy|opencv_cuda` selects the map backend. Product UI/actions are GPU-required
  by default: CPU map generation and CPU/Pillow preview compositing are
  diagnostic-only and must require either explicit action parameter
  `allow_cpu=true` or `TIGERCAPTURE_TEXTURE_LAB_ALLOW_CPU=1`. If no implemented
  GPU backend is available, Texture Lab must show a GPU-required state instead
  of silently choosing CPU fallback or implying GPU acceleration. The legacy CPU
  path remains useful for small deterministic tests and offline diagnostics, not
  for the normal interactive product path. Texture Lab also follows
  TigerStudio's first-use automation policy: the
  `Install GPU` control opens an in-app progress/log dialog, runs the current
  TigerCapture virtual environment through `python -m pip install torch
  torchvision --index-url https://download.pytorch.org/whl/cu128`, verifies
  `torch.cuda.is_available()` in the same venv, and automatically selects
  `TIGERCAPTURE_TEXTURE_LAB_BACKEND=torch_cuda` for the running process when
  verification succeeds. The dialog must make clear that RTX/OpenGL AR/PBR
  preview working does not prove the PyTorch CUDA map-generation backend is
  installed; these are separate GPU paths. Completion must be explicit, with
  the close button enabled only after success, failure, or cancellation.
  GPU preview composition is owned by
  `app.ar_pbr.texture_map_gpu_preview`, an offscreen OpenGL fragment-shader
  compositor that samples Base/Normal/AO/Roughness/Metallic and packed map
  channels for plane/sphere previews. PNG/action outputs may read the rendered
  GPU result back to disk, but preview shading must not use the CPU compositor
  unless the caller explicitly opted into diagnostics.
  As of 2026-07-24, the interactive material-preview contract is:
  - Plane preview binds Base Color, tangent-space Normal, AO, Roughness, and
    Metallic maps in the OpenGL shader instead of displaying an unmapped
    placeholder.
  - Sphere preview uses longitude/latitude UV mapping and transforms sampled
    tangent-space normals into the curved sphere basis. Selecting Albedo,
    Normal, AO, Roughness, Metallic, Height, Cavity, or a packed-map view must
    preserve the selected sphere shape. Only explicitly multi-panel diagnostic
    views such as Intrinsic Channels and Delight Compare may force a plane.
  - Height is a first-class grayscale output (`black=low`, `white=high`) and
    must remain visible among the first Texture Lab thumbnails even in compact
    layouts. Separate-map export writes the Height PNG and records it in the
    material manifest instead of treating it as an internal Normal/AO
    intermediate.
  - Texture Lab Material preview binds Height to GPU Parallax Occlusion Mapping
    (POM). The user can enable/invert Height and adjust POM strength, depth,
    and 4-64 ray-march steps; the default preview uses 24 steps. Plane and
    Sphere both use the generated Height map, with Sphere retaining its
    longitude/latitude UV and tangent basis.
  - The shared AR/PBR renderer supports both legacy single-offset parallax and
    explicit `parallax_mode=pom`. Live OpenGL preview performs iterative
    Height sampling with linear intersection refinement; packet export mirrors
    POM for ordinary Height textures and reports a single-offset fallback for
    unsupported UDIM/triplanar combinations. Preview and export consume the
    same `parallax_strength`, `parallax_depth`, `parallax_center`, and
    `parallax_steps` contract.
  - POM changes texture lookup coordinates only. The exported Height map is
    ready for a future tessellation/displacement path, but this release does
    not claim mesh subdivision, silhouette displacement, or displaced shadow
    geometry.
  - The default studio light uses an upper-left key at approximately 45
    degrees, a softer right fill, a rim contribution, and restrained ambient
    light. The vertical light convention must keep the key above the material;
    lower-edge lighting caused by an inverted preview axis is a regression.
  - Animate Light moves the key only across the upper hemisphere. It requests
    updates with a precise 16 ms timer, uses a 256-pixel GPU preview while
    moving, skips map and thumbnail regeneration, and restores a 960-pixel
    settled frame when animation stops. Actual frame rate remains bounded by
    GPU render completion rather than being claimed as guaranteed 60 fps.
  - Native window move/resize suspends heavy preview work and resumes with one
    settled refresh, while normal widget repainting remains enabled so the
    canvas does not disappear during interaction.
  `app.ar_pbr.full_gpu_export_service` defines and invokes the worker-safe
  helper-process path for that full-GPU route.
  `tools/ar_pbr_full_gpu_export_service.py` is the default helper; it accepts
  `--probe` and `--request <json>`, renders model-view PBR/texture/HDRI output
  in a separate Qt/OpenGL process, returns an RGBA frame path plus diagnostics,
  and lets `VideoExportThread` stay free of Qt/OpenGL context creation.
  On Windows the helper forces desktop OpenGL for the service process because
  Qt's ANGLE/software defaults can leave the PyOpenGL model-view path with an
  invalid `QOpenGLWidget` context. The helper window is created offscreen and
  fixed to the export tile size instead of using `WA_DontShowOnScreen`, which
  keeps the worker process hidden while preserving a valid native GL surface.
  `tools/qa_ar_pbr_full_gpu_export_service.py` writes
  `debugCapture/ar_pbr_full_gpu_export_service_qa.json`; when probe succeeds,
  `product_gap_push` can count full model-view GPU export as claim-ready for
  the AR/PBR renderer-quality gate.
- GPU preview metadata is explicitly collision-tested: one `gpu_frame_ready`
  payload can carry color grade data, shader clip effects, Spine direct overlay
  items, and AR/PBR overlay items together, and `VideoEditorWindow` dispatches
  them separately to `OpenGLPreviewWidget` without dropping the grade or overlay
  contracts.
- GPU preview pixel visibility is also covered by
  `tools/qa_gpu_preview_pixel_collision.py`. The QA renders an actual
  `OpenGLPreviewWidget` framebuffer with color grade uniforms, shader clip
  effect uniforms, and AR/PBR mesh/shadow/reflection packets, then checks the
  captured pixels and stores `debugCapture/gpu_preview_pixel_collision.png`.
  It also exercises a real Spine sample through the direct GL overlay path and
  a real Live2D sample through the CPU/prerender-to-GPU-display path, storing
  actor screenshots and changed-pixel counts. This catches GL framebuffer,
  shader, AR/PBR overlay, Spine overlay, and Live2D display regressions in the
  combined preview surface; full editor-window interaction screenshots remain
  covered by the broader visual regression suite.
- GPU preview/export parity is summarized by
  `tools/qa_gpu_export_parity_matrix.py` and
  `debugCapture/gpu_export_parity_matrix_qa.json`. This QA runs the GL pixel
  collision report, final editor export-bake smoke, and synthetic export parity
  smoke into one matrix for color grade, shader effects/chroma, typography
  export pixels, Spine/Live2D actor preview/export evidence, transitions, and
  masked node graph export. It also runs `tools/qa_ar_pbr_export_bake.py` to
  prove AR/PBR object tracks are baked into final MP4 output through the
  preview-packet export renderer (`mode=gpu_packet_export`). That report checks
  mesh, shadow, and reflection packet triangles, packet SSAA, final-pixel
  differences, AR-colored pixels, catcher darkening, texture-plan readiness,
  GL-preview model-view-style material-map PBR readiness, export UV texture
  sampling, headless PBR material-map/AO sampling, and live/item PBR depth-mask diagnostics
  on the encoded MP4. The matrix now reaches `release_ready=true` when all
  listed rows pass; real shadow maps, physically richer reflection passes,
  prefiltered IBL tuning, and deeper camera/lens solve remain renderer-quality
  work rather than an export-missing gap.
  Current latest recorded matrix requires `live2d_actor.preview=true`; Live2D
  export evidence without real preview coverage remains a release blocker.
  `render_clip_tracks`
  exports force the preview-parity base-frame path so nested/multi-source
  transition renders are not accidentally routed through a plain FFmpeg graph.
- AR/PBR attachment stability is covered by
  `tools/qa_ar_pbr_attachment_stability.py`. It drives the headless GPU packet
  path across several road-plane anchor positions, verifies model center drift,
  shadow/reflection packet generation, and coarse fallback depth-occlusion diagnostics,
  and writes `debugCapture/ar_pbr_attachment_stability_qa.json`. Scene-anchor
  tracking also estimates simple image-space affine motion. The first frame
  stores a main template plus several nearby probe templates; runtime matching
  combines their relative motion to update `placement.image_point`,
  `transform.scale`, and `transform.rotation.z`. This is a practical 2D
  roll/zoom tracking layer for attached props, not a full SLAM/camera-track
  solution. Runtime diagnostics expose `camera_motion_hint` / `slam_assist`
  with `mode=template_depth_plane_slam_assist`, confidence, translation, scale,
  roll, and an explicit `not_full_slam` limit. QA Dashboard exposes it as
  `AR/PBR Attachment Stability`.
- AR/PBR 3D object editing uses a standard transform-gizmo interaction on the
  editor preview canvas and preview pop-out. The selected object draws red X,
  green Y, and blue Z handles, per-axis rotation rings, axis scale cubes, a
  center screen-plane move handle, and a white uniform-scale handle. Dragging
  updates `placement.image_point`, `transform.position.z`, `transform.rotation`
  or `transform.scale` depending on the selected handle. Current axes are
  screen-oriented with a blue diagonal depth handle; camera/world/local axis
  modes remain tied to the future full camera solve.
  The Python Action adapter is split into focused AR/PBR modules:
  `app/actions/editor_adapter_ar_pbr_depth.py` owns diagnostics and depth-map
  viewer actions, `app/actions/editor_adapter_ar_pbr_preview.py` owns preview
  camera framing, `app/actions/editor_adapter_ar_pbr_settings.py` owns lighting/
  material/surface controls, and `app/actions/editor_adapter_ar_pbr_gizmo.py`
  owns viewport gizmo state/show/hide.
- The AR/PBR 3D model preview has an `HDR Environment` preset dropdown. Presets
  are discovered from `debugCapture/ar_pbr_resources/manifest.json`, resolved
  by `app.ar_pbr.hdri_presets`, and loaded into the OpenGL preview without
  reimporting the mesh. The bundled local Poly Haven CC0 1K HDRI set covers
  street, studio, indoor, forest, sunset, night-street, and glossy studio
  lighting. Track lighting persists the selection as `hdri_id` and `hdri_path`
  so project reloads and future export parity work can use the same IBL
  environment.
- Loading and first-use performance are measured persistently. Live2D/Spine
  actor stages, decoder backend selection/opening, AR/PBR preview import,
  vertex buffer, HDRI, and texture-plan stages append JSONL rows to
  `debugCapture/loading_performance.jsonl` through `app.loading_performance`.
  `app.preview_acceleration.configure_preview_acceleration_defaults()` is
  called at startup and defaults the editor to decoder auto-selection,
  frame-server auto mode, larger frame cache, Spine GL zero-readback preview,
  and AR/PBR GPU preview unless the user overrides env vars. Editor startup
  schedules background parser/importer/Live2D runtime prewarm, media-pool 3D
  imports prewarm persistent AR/PBR descriptors, and repeated 3D preview/model
  view windows are reused. Run
  `.\.venv\Scripts\python.exe tools\qa_loading_performance.py` to see the
  active policy and recent slow stages.
- `app/foreground_tracker.py` tracks the active Windows foreground window for
  quick-paste behavior. It is not visual face/object tracking.
- The Sound Editor is clip-scoped. It edits one `AudioClip` at a time, while
  timeline playback/export use `AudioTrack` lanes and FFmpeg filter graphs.
- Vocal/music separation lives in the Sound Editor AI Master tab. It writes two
  WAV stems and, when opened from the video editor, adds them as new audio
  tracks.
- The next commercial expansion layer is centralized in
  `app/commercial_expansion.py`. It tracks ten product surfaces: beta feedback
  bundle export, preview frame-server/hardware-decode UX, preview/export
  parity lock, AI one-click edit planning, preset marketplace health,
  audio postproduction depth, color-node workflow depth, project snapshots,
  plugin manifests, and release productization. `tools/qa_commercial_expansion.py`
  writes `debugCapture/commercial_expansion_qa.json`, and QA Dashboard plus the
  productization loop include it as a first-class report.
- The ordered 3,4,5,1,2,6 product-gap push is centralized in
  `app/product_gap_push.py`. `tools/qa_product_gap_push.py` writes
  `debugCapture/product_gap_push_qa.json` and covers, in the user-requested
  order: AI editing quality, interaction-ready screen-recording corpus,
  CapCut-style local template/asset scale, GPU preview/export parity, AR/PBR
  renderer quality, and release trust. The report distinguishes
  `implementation_ready` from `claim_ready` so missing evidence cannot be
  accidentally marketed as finished; the current refreshed report is 98/100
  with all six areas claim-ready. The AI area uses the selected provider
  evidence path, reusing the latest usable
  `debugCapture/ai_edit_corpus_quality_qa.json` when it contains provider
  evidence and running live provider QA only when that evidence is missing. This
  keeps a recent executor failure or success from being hidden by an unrelated
  live retry. If Claude/Codex/Qwen/local LLM falls back to the deterministic
  planner, the selected provider state is included in the report. The
  real-recording area
  also includes sidecar-intake
  evidence so missing cursor/click/drag/hotkey/auto-zoom proof points directly
  to fillable `.cursor.template.json` files instead of a vague corpus warning.
- CapCut-style creator features are centralized in `app/capcut_workflow.py`.
  They are deterministic product plans, not a bundled ML model: auto-caption
  styling, long-video-to-Shorts candidate picking, smart media search indexing,
  subject-aware vertical reframe keyframes, easy keyframe graphs, voice cleanup
  routing, background-removal route selection, social export settings, and
  one-click recommendations. `tools/qa_capcut_creator_workflow.py` writes
  `debugCapture/capcut_creator_workflow_qa.json`; QA Dashboard and the
  productization loop expose it.
- CapCut parity tracking is centralized in `app/capcut_parity.py`. It compares
  TigerCapture's current creator workflow against practical CapCut gaps:
  template ecosystem scale, one-click AI agent depth, captions/voice/TTS
  workflow, social publish handoff, cloud/mobile/collaboration, stock music/SFX,
  and beginner default-result flow. `tools/qa_capcut_parity_next.py` writes
  `debugCapture/capcut_parity_next_qa.json`, and QA Dashboard exposes it as a
  gap tracker. A passing report means the tracker is honest and runnable; it
  does not claim full CapCut parity.
- CapCut mobile/template parity can now be scoped to local-first work with
  cloud excluded. `app/capcut_mobile_templates.py` defines 108 mobile vertical
  template contracts across TikTok/Reels/Shorts, twelve creator categories,
  three hook styles, safe caption/action zones, cover-frame metadata, and
  deterministic recommendations. It also defines 216 local trend-template
  packs across six trend families, A/B storyboard contracts, and a 12-scenario
  deterministic creator-corpus quality report. `build_capcut_parity_next_report(
  exclude_cloud=True)` removes the cloud/mobile-sync area and scores
  `mobile_template_scale` instead, while `tools/qa_capcut_parity_next.py
  --exclude-cloud` writes the same no-cloud QA report. This is the intended way
  to discuss CapCut progress when cloud sync is deliberately out of scope.
  The no-cloud report now clears the local template, mobile safe-zone,
  beginner default-result, captions/voice cleanup, stock/SFX starter-pack, and
  publish-handoff areas, and it exposes trend pack count, trend families,
  storyboard count, and creator-corpus score. The remaining local gap is the
  true generative one-click creator agent, which must stay separate from
  deterministic fallback planning.
- CapCut publish review lives in `app/capcut_publish.py`. It turns the creator
  publish package into review cards for copy, thumbnail frame, platform
  variants, checklist rows, and provider contracts. Built-in providers cover
  local manifest, clipboard copy, TikTok/Shorts/Reels manual upload handoff,
  X/TikTok/Instagram browser quick-upload handoff, plus unconfigured
  TikTok/Instagram/X direct API upload slots and an unconfigured share-link
  provider slot. No network upload is performed by default; quick upload opens
  the platform handoff with copy/export metadata ready, while direct API upload
  remains disabled until platform OAuth/app-review providers are configured.
  `capcut_write_quick_upload_package()` writes a local browser-upload package
  with `publish_manifest.json`, `quick_uploads.json`, `upload_links.json`,
  provider contracts, title/description/hashtag text files, per-platform post
  text files for TikTok/Instagram/X, `package_index.json`, and `README.txt`.
  `tools/qa_capcut_publish_review.py` writes
  `debugCapture/capcut_publish_review_qa.json`, verifies the package writer,
  and QA Dashboard exposes it.
- CapCut quick-result recommendations live in `app/capcut_quick_result.py`.
  They inspect a creator bundle and choose the first useful template, explain
  what will happen, score one-click quality across hook/caption/pacing/format/
  delivery/safety, expose a beginner default path, and report visible feedback
  evidence for template badges, timeline markers, caption rows, render jobs,
  and review cards. They feed a Quick Result card into Creator Assist.
  `tools/qa_capcut_quick_result.py` writes
  `debugCapture/capcut_quick_result_qa.json`; the CapCut parity report uses
  this score and default-path evidence for the AI one-click and beginner
  default-result gaps.
- CapCut captions/voice workflow lives in `app/capcut_voice.py`. It combines
  transcript/SRT caption rows, caption beat styling, voice cleanup/loudness/
  stem-separation operations, and explicit TTS/custom voice/translation
  provider slots into one reviewable local-first model. Optional cloud/custom
  voice providers stay unconfigured by default and are shown with setup
  messages instead of being used silently. The workflow reports ready cards,
  enabled actions, manifest operations, and no-cloud-default evidence so local
  caption/cleanup readiness is not confused with finished TTS/custom voice.
  TTS is a required product direction for the planned subculture media creator
  studio: character narration, anime-style voiceover, PPT narration, subtitle-
  to-voice, VTuber/actor dialogue, and sentence-level replacement should all be
  able to route through a local or user-configured voice provider. The current
  local reference install is `D:\TTS\sbv2\Style-Bert-VITS2`; it has CUDA-ready
  Style-Bert-VITS2, FastAPI `/voice` and `/models/info` endpoints, and local
  model assets. Because Style-Bert-VITS2 is AGPL and its torch/whisper stack is
  heavy, TigerCapture should integrate it as an optional sidecar/provider
  (`tts.provider.status`, `tts.server.ensure_running`, `tts.voice.list`,
  `tts.subtitle.plan`, `tts.subtitle.generate_to_timeline`) rather than
  bundling or importing it directly into the editor process. Kokoro and
  GPT-SoVITS follow the same provider boundary: Kokoro runs through an external
  Python 3.12 subprocess, while GPT-SoVITS runs as an optional `api_v2.py`
  sidecar with explicit reference-voice presets and no bundled user audio,
  weights, or model caches. The current setup
  implementation is intentionally split: `app/tts_setup.py` owns provider
  detection/install-plan contracts, `app/tts_lab.py` owns the friendly setup UI,
  and `app/workbench_panel.py` exposes Voice Lab as a Composer-adjacent tool in
  the Workbench `Programs` tab rather than nesting it inside Sound Editor or
  the clip-level Audio tab. Composer and Voice Lab must remain available
  without an existing audio track or selected audio clip, but the Audio tab
  itself must not show large `COMPOSER` / `VOICE LAB` launcher buttons.
  Video clips with detected embedded audio expose the clip-scoped Sound Editor
  through a transient `AudioClip` proxy; this does not create a timeline audio
  track unless the user explicitly extracts audio. Preview and export rebuild
  hidden embedded-audio clips from the video clip's timeline position and
  source trim, then copy the Workbench proxy's gain/fade/effects state so the
  selected-video audio follows timeline edits without requiring extraction.
  The proxy also carries `picture sync` markers generated from clip in/out,
  transitions, video fades, zoom/motion actors, typography/keyframe events,
  speed changes, and frame repairs. Sound Editor waveform UI renders those
  markers as frame-locked audio editing references; moving/trimming the video
  clip regenerates marker source/project positions before preview/export.
  2026-07-25 UI note: Composer and Voice Lab launch from the Workbench
  `Programs` tile grid; standalone Voice Lab window chrome remains text-first.
  Voice Lab popup windows and all Voice Lab combo-box popup containers
  must force dark styled backgrounds/palettes so Windows/Qt native popup frames
  do not show white side gutters or white dropdown edges.
  2026-07-10 stabilization note: TTS/Voice Lab sidecar failures must be
  actionable instead of raw connection errors. `app.tts_sidecar_runtime`
  exposes `tigercapture.tts_sidecar.guidance.v1` guidance plus formatted text
  for missing/incomplete provider installs, startup failures, startup timeouts,
  and offline `/voice` servers. Subtitle TTS planning and generation actions
  should surface that guidance and keep the editor stable when the sidecar is
  absent.
  `tools/qa_capcut_voice_workflow.py`
  writes `debugCapture/capcut_voice_workflow_qa.json`; Creator Assist gets a
  Voice Workflow card, and the CapCut parity tracker uses its score for the
  captions/voice gap.
- CapCut local collaboration handoff lives in `app/capcut_collaboration.py`.
  It builds a local-first review package contract with project snapshot,
  review notes, media relink manifest, manual archive readiness, and explicit
  optional workspace/mobile/cloud-comment provider slots. No network upload or
  cloud sync is performed by default. `tools/qa_capcut_collab_handoff.py`
  writes `debugCapture/capcut_collab_handoff_qa.json`; Creator Assist gets a
  Collab Handoff card, and the CapCut parity tracker uses the score for the
  cloud/mobile/collaboration gap while still keeping full cloud/mobile parity
  marked incomplete.
- CapCut cloud/share handoff lives in `app/capcut_cloud_handoff.py`. It defines
  provider contracts for local sync folders, Google Drive, OneDrive, Dropbox,
  WebDAV, S3-compatible storage, and custom share providers. It does not upload
  files, store tokens, or call provider APIs. Instead it validates the package
  inventory, relink manifest, private-link default, conflict policy, explicit
  user-consent gate, no-token manifest rule, and configured-provider dry-run
  readiness. `capcut_write_cloud_ready_package()` can write a local sync-folder
  package containing `manifest.json`, `cloud_handoff_plan.json`,
  `review_notes.json`, `relink_manifest.json`, `provider_contracts.json`,
  `package_index.json`, and `README.txt` without copying original media by
  default. `tools/qa_capcut_cloud_handoff.py` writes
  `debugCapture/capcut_cloud_handoff_qa.json` and verifies the local package
  writer; QA Dashboard and CapCut parity consume it as progress on the
  cloud/mobile/collaboration gap, not as full cloud sync.
- CapCut prompt-to-edit lives in `app/capcut_prompt_edit.py`. It maps creator
  prompts to review-first operations such as captions, subject reframe, cursor
  polish, voice cleanup, asset recommendations, short exports, thumbnail
  candidates, publish handoff, and local collab handoff. `tools/qa_capcut_prompt_edit.py`
  writes `debugCapture/capcut_prompt_edit_qa.json`; Creator Assist gets a Prompt
  Edit card, QA Dashboard can run the benchmark, and CapCut parity uses the
  benchmark score. This is not a claim that a generative Descript/CapCut AI
  agent is complete; it is the local contract that remains useful when no LLM is
  configured.
- Creator asset packs are modeled in `app/creator_asset_packs.py`. The
  local-first catalog now covers 100 generated sticker, background, SFX, and
  short-loop metadata entries with explicit license IDs, search, external JSON
  pack loading, intent coverage, synthetic preview storyboards, ready
  collection shelves, and a local recommendation board with drag payloads. This
  improves the CapCut-style asset ecosystem path without pretending to ship a
  licensed stock media marketplace or trend feed. `tools/qa_creator_asset_packs.py`
  writes `debugCapture/creator_asset_packs_qa.json`, and CapCut parity uses the
  asset count, intent coverage, collection-shelf, recommendation, and storyboard
  evidence for template/stock gaps.
- Local ML is routed through `app/local_ml.py`. It never calls a cloud API and
  never auto-downloads models. After the launcher flicker fix, this path is
  enabled by default and can be disabled for diagnostics with
  `TIGERCAPTURE_LOCAL_ML_DISABLED=1` or `TIGERCAPTURE_LOCAL_ML_ENABLED=0`.
  `local_ml_backend_status()` reports optional local capabilities
  (OpenCV/Pillow visual analysis, local Whisper, SAM, Demucs, ONNX Runtime,
  Ultralytics). `local_ml_analyze_media()` samples local images/videos for
  foreground subject detections, scene ranges, and tags.
- AI Script / One-Click Editing has crossed into reviewed Descript-lite product
  behavior, but it is still not a full Descript-class natural-language editor.
  The video editor now has a
  bottom `AI Command` dock that is visible by default, right-dock
  `ScriptEditPanel`, SRT/VTT/local-Whisper transcript input, deterministic
  Korean/English prompt routing, `EditPlan`
  validation, preview markers, safe subtitle/marker/auto-zoom materialization,
  and a separate reviewed-cut apply path that can materialize reviewed
  video/audio ripple cuts. `app.descript_lite_readiness` preserves the current
  product priority ladder: text-based timeline editing, transcription quality,
  one-click cleanup, Studio Sound-grade audio, AI voice/replacement, AI
  co-editor UX, and collaboration/cloud. Priorities 1-3 must be claim-ready
  before any Descript-lite positioning, and priorities 1-5 must be claim-ready
  before a $149+ Descript-style AI value defense. New Descript-lite work should
  not add feature logic to `app/video_editor_window.py`; the implementation plan
  keeps work in services, providers, panels, and action surfaces first, with
  `VideoEditorWindow` reserved for final thin adapter calls. The first P1
  service layer now lives in `app.transcript_reflow`,
  `app.transcript_timeline_ops`, `app.transcript_selection_actions`, and
  `app.transcript_edit_surface`, with the surface owned by
  `ScriptEditPanelModel` and QA in `tools/qa_descript_lite_p1_services.py`.
  P2 editable-script generation now has a local-first provider contract in
  `app.transcription_providers` and cleanup/glossary support in
  `app.transcript_cleanup`; runtime claim readiness still depends on a saved
  local word-timestamp ASR model path or auto-discovered Systran
  faster-whisper Hugging Face cache snapshot in `app.transcription_settings`
  being verified by `tools/qa_descript_lite_p2_transcription.py`;
  missing-model guidance is emitted by `tools/configure_local_whisper_model.py`
  and `tools/qa_transcription_runtime_setup.py`.
  One-click cleanup also includes `app.retake_detection` for repeated takes and
  false-start/mistake candidates, with QA in
  `tools/qa_descript_lite_p3_cleanup.py`. P4/P5 now include
  `app.speech_enhance` local before/after speech cleanup QA and
  `app.ai_voice_replacement` reviewed sentence replacement plus consent gating,
  verified by `tools/qa_speech_enhance.py` and
  `tools/qa_ai_voice_replacement.py`. See
  `docs/SPEC_AI_TEXT_EDITING.md`,
  `docs/SPEC_LOCAL_AI_PROVIDERS.md`, `app/ai_script_edit_panel.py`, `app/ai_edit_plan.py`,
  `app/ai_text_editing.py`, `app/ai_edit_apply.py`, and
  `tools/qa_ai_script_edit_integration.py`. Smart-edit claim readiness is based
  on direct provider evidence, not on rule-based fallback. Historical evidence
  includes Claude direct/MCP executor corpus runs with 20/20 direct successes;
  the current default-free local evidence comes from `qwen_local` direct
  provider runs with the same 20/20 direct-success shape. Claude/Codex/local
  command providers remain switchable executor surfaces when configured.
  Rule-based fallback remains the safe failure path, but fallback evidence alone
  must not enable smart-AI marketing copy. The default free model profile is
  `qwen_local` (`Qwen3 1.7B GGUF`, official `Q8_0` first-use llama.cpp path)
  with first-use install/status UI, while `local_llm`, `codex_mcp`, and
  `claude_mcp` remain switchable readiness/provider surfaces unless explicitly
  configured.
  `local_ml_capcut_project_summary()` turns that analysis into the summary
  shape consumed by CapCut planners, and
  `capcut_creator_bundle_from_local_media()` returns a ready apply bundle
  through the local-only analysis route. `tools/qa_local_ml_backend.py` writes
  `debugCapture/local_ml_backend_qa.json`; QA Dashboard and the productization
  loop expose it as a first-class report.
- `app.capcut_workflow.capcut_creator_apply_bundle()` is the handoff payload
  for a one-button CapCut-style apply command. It returns
  `project_settings_patch`, `workflow_preset_ids`, `subtitle_rows`,
  `caption_beat_plan`, `hook_score_plan`, `timeline_markers`,
  `render_queue_jobs[*].create_kwargs`, `smart_media_index`, search chips,
  an explainable `edit_recipe`, multi-platform `publish_variants`, and
  a `publish_package`. `subtitle_rows` are compatible with
  `app.subtitles.Subtitle` plus sidecar styling fields; `create_kwargs` can be
  passed to `app.render_queue.RenderQueueJob.create()`. The publish package
  contains CapCut-style title suggestions, hashtags, thumbnail-frame choices,
  caption/reframe/export checklist rows, and hook/caption beat metadata so the
  editor can show a creator delivery card without re-analyzing the project.
- `capcut_creator_edit_recipe()` explains the one-click recommendation as
  reviewable trim/caption/reframe/audio/effect/delivery steps with reasons,
  confidence, missing inputs, and review points. `capcut_multi_platform_publish_plan()`
  creates Shorts/TikTok/Reels variants with per-platform export settings,
  title, hashtags, thumbnail frame, checklist status, and a recommended
  platform. The QA report surfaces `edit_recipe_steps` and `publish_variants`,
  and QA Dashboard includes those counts in the CapCut row.
  `capcut_caption_short_quality_model()` is the focused caption/shorts quality
  gate for this path: it checks styled caption rows, readable line length,
  monotonic subtitle timing, caption beat metadata, ranked short candidates,
  vertical caption safe areas, and publish-package readiness. Product-polish QA
  consumes that score so CapCut-style work is judged by usable output, not only
  by whether helper functions exist.
- `capcut_creator_review_panel_model()` is the Qt-ready data contract for a
  CapCut Creator panel. It groups the apply bundle into hero, recipe, short
  candidate, caption beat, hook ranking, publish variant, and smart-media
  cards, plus primary actions such as apply plan, preview best short, queue
  render jobs, copy publish copy, and open matching templates.
  `capcut_quick_create_button_model()` adds the editor-side quick-create
  contract: analyze current project/media, apply captions/short markers/output
  settings, queue social exports, and prepare publish copy without routing the
  user through the launcher or a template-first flow.
  `capcut_publish_handoff_plan()` builds copy/export handoff payloads for
  title, description, hashtags, thumbnail jump, and short-export queueing.
  Apply bundles and project sidecars preserve both models; QA reports
  `review_panel_cards`, `review_panel_ready`, `quick_create_ready`,
  `quick_create_steps`, `publish_handoff_actions`, and
  `publish_handoff_ready`.
- The user-facing CapCut workflow is intentionally editor-side, not
  launcher/template-first. `app.creator_assist_panel.CreatorAssistPanel` lives
  in the right dock and the main command bar opens it as "Creator Assist". It
  analyzes the current Media Pool, Workbench-backed project settings, subtitles,
  and timeline, then lets the user apply captions, short-range markers, social
  export defaults, render-queue handoff, and publish copy without hiding the
  normal TigerCapture media-pool/workbench/timeline identity. The panel is
  lazy-loaded only when opened so launcher-to-editor startup does not eagerly
  construct CapCut review widgets. Creator Assist must not carry general
  program launchers such as PPT Maker or Unreal Engine Link; those belong only
  in the Workbench `Programs` category so the right dock has one clear tool
  launcher surface.
- CapCut parity is intentionally tracked as a gap, not a claim. The current
  strongest local-first surfaces are Creator Assist, safe apply bundles,
  quick-result recommendations, preset search, publish review/provider handoff,
  local creator asset packs, render-queue handoff, and local ML hooks. The
  largest CapCut gaps remain large template/asset volume, generative one-click
  breadth, TTS/custom voice, direct social/cloud/mobile workflows, and licensed
  stock music/SFX marketplace scale.
- CapCut-style extensions have explicit feature gates in
  `app/capcut_features.py`. After the launcher flicker fix, they are enabled
  by default. Disable everything with `TIGERCAPTURE_CAPCUT_DISABLED=1` or
  disable/override one route at a time with
  `TIGERCAPTURE_CAPCUT_LOCAL_ML_ENABLED=0`,
  `TIGERCAPTURE_CAPCUT_CREATOR_ASSIST_ENABLED=0`,
  `TIGERCAPTURE_CAPCUT_APPLY_BUNDLE_ENABLED=0`,
  `TIGERCAPTURE_CAPCUT_TEMPLATE_AUTO_APPLY_ENABLED=0`, or
  `TIGERCAPTURE_CAPCUT_QA_ENABLED=0`. Disabled routes avoid creating their
  UI/panel work and report the feature-gate reason instead of loading panels or
  ML paths.
- Creator Assist supports partial apply toggles for subtitles, short markers,
  export/reframe settings, and render-queue staging. Applying timeline/project
  changes records one undo savepoint, while render jobs are added directly to
  `RenderQueueStore`/`RenderQueuePanel` instead of opening the batch-export
  folder dialog. During analysis, the editor merges local-only visual detections
  from `app.local_ml.local_ml_capcut_project_summary()` when a current media file
  is available, so subject-aware reframe can use OpenCV/Pillow detections without
  cloud APIs or model downloads. The panel also exposes a `Quick Start` button that
  selects all apply options, analyzes when needed, applies the bundle, stages
  render jobs, and copies publish text if available. The panel reports busy
  state and the last result counts for subtitles, short markers, settings, and
  queued jobs so quick-create does not feel like a silent black box.
- `app.capcut_apply.capcut_apply_bundle_to_project()` now applies that bundle
  to a project document without Qt: it merges project settings/export defaults,
  appends styled subtitles, adds visual timeline markers plus
  `capcut_short_ranges`, stages `render_queue_jobs`, writes the
  `capcut_creator_package` sidecar including hook/caption/package/recipe/
  variants/review-panel/handoff, preserves manual subtitles/markers, and
  deduplicates repeated applies. The CapCut QA report includes
  `apply_simulation` plus applied subtitle/render-job/package counts.
- `app.capcut_apply.capcut_render_queue_jobs_from_payload()` and
  `capcut_add_render_jobs_to_store()` turn staged CapCut short-export payloads
  into real `RenderQueueJob` entries with duplicate protection. The CapCut QA
  report now also checks `materialized_render_queue_jobs`.
- Project subtitle save/load preserves `show_box` and `style` metadata. This
  matters for CapCut caption presets because `caption-capcut-word-pop` and
  related style sidecars must survive a `.tgp` round trip.
- CapCut-like built-in presets live in
  `app.preset_library.CAPCUT_CREATOR_WORKFLOW_PRESETS`: word-pop/karaoke auto
  captions, hook question title, social CTA burst, subject reframe motion, feed
  swipe transition, background cutout effect, voice enhance audio, and
  templates for auto-caption shorts, long-to-shorts, subject reframe, smart
  search edits, and social publishing. Korean natural-language aliases cover
  common caption, auto-caption, background-removal, and intro/logo queries.
- The editor UI now follows a professional shell direction: app command bar,
  left media/assets rail, center viewer, right contextual inspector, and bottom
  timeline. Shared theme tokens live in `app/style.py`; editor-specific panel
  chrome is layered through object names in `app/video_editor_window.py`.
- UI font fallback is explicit: `app/font_fallback.py` chooses Pretendard/Noto
  Sans/Malgun/Segoe-family fonts at application startup, while `app/style.py`
  keeps the same CJK-aware stack in QSS so Korean labels remain readable.
- Shared UX micro-feedback lives in `app/ux_feedback.py`. Media Pool
  empty/no-match/drop feedback, Color Page scope/color-management status, and
  Audio Mixer empty states use the same `UXState` tone model so hover,
  selection, drag, progress, and failure states stay consistent across panels.
- The main editor keeps Media Pool and Workbench as primary surfaces, but
  secondary left/right dock sections are collapsible by default: Effect
  Presets, Title Presets, Transitions, Workflow Presets, Render Queue, Audio,
  and Subtitles are discoverable headers until opened. This preserves the
  existing media pool and node/workbench workflows while reducing first-screen
  clutter.
- Primary surfaces can still leave the main frame when the edit needs more
  room: Preview, Timeline, Color, Subtitles, and both side dock columns use
  reparented pop-out windows, so each surface keeps its live state and docks
  back into the original layout when the floating window closes. The Media Pool
  pop-out detaches the whole left column including Effect Presets, Title
  Presets, Transitions, and Workflow Presets; the Workbench pop-out detaches the
  whole right column including Workbench, Creator Assist, Script Edit, Render
  Queue, Audio, PIP, and Subtitles.
- The top command bar is intentionally compact: low-frequency project,
  recovery, relink, health, actor, queue, reset, and audio-scope commands are
  grouped behind `Project`, `Actors`, and `More` menus. Export settings and the
  primary Export button remain visible because they affect final delivery.
- The global Qt chrome is also part of the Screen Studio direction. `main.py`
  forces Qt's `Fusion` style, and `app/style.py::APP_QSS` now applies a late
  studio-wide override for generic Qt widgets: dialogs, message boxes, file
  dialogs, buttons, tool buttons, inputs, spin boxes, combo boxes, tabs, menus,
  list/tree/table views, headers, scrollbars, progress bars, toolbars, status
  bars, tooltips, and splitters. New secondary tools should lean on these
  global rules before adding local QSS.
- Local QSS-heavy tools must append `app.style.studio_chrome_qss(...)` so they
  keep the same CJK-safe font stack, rounded glass controls, purple/coral
  accents, menus, sliders, and scrollbars. This currently covers the new
  project dialog, mask editor, Live2D editor, Spine editor/scanner/timeline
  panels, actor-lane context menus, and Workbench node graph/popout chrome.
- Top-level Studio windows must fit onto the focused/parent/current monitor
  before first show and through the first few post-show layout passes. The
  shared `app.window_placement` policy is installed from Studio/Capture entry
  points and user-facing standalone tool launchers, including Preview/Color/
  Timeline/Media Pool/Workbench/VTuber popouts, Motion Designer, Spine, MMD,
  AR/PBR preview tools, Texture Lab, and PPT Maker. It uses current cursor/focus
  screen selection for ownerless windows, accounts for sizeHint/minimumSizeHint
  growth before first show, clamps oversized dialogs to the active screen's
  available geometry, and runs short 0/120/360 ms first-show refit passes so
  late Qt layout expansion cannot leave a window spanning monitors. Menus,
  tooltips, and popups are excluded, and exceptional windows can opt out with
  the `tiger_no_auto_place` Qt property.
- Screen-recording-inspired timeline visuals live in `app/studio_theme.py`:
  media clips use amber alpha-blended blocks, zoom/actions use violet blocks,
  blade cuts use yellow scissors markers, and the playhead is violet. Shared
  code-native editor icons live in `app/icons.py`; command menus, timeline
  edit tools, Export, Marker, and Zoom cards consume that icon helper. Blade
  cuts and Zoom drops emit short painter-native timeline bursts for immediate
  edit feedback.
- The second Screen Studio UI pass deliberately reduces visible control noise:
  top-bar zoom/proxy secondary actions move behind `More`, track add/delete
  lives behind a `Tracks` command menu, effect cards are shorter chip-like
  drag sources, side panels use rounder glass-like surfaces, and timeline
  diagonal stripes are low-contrast background texture rather than the dominant
  visual layer.
- The third Screen Studio UI pass adds product-feel details without removing
  Media Pool or Workbench: preview frames render inside a padded rounded canvas
  with shadow/border chrome, timeline media clips get stronger amber highlights
  and film-strip labels, core icon buttons pulse briefly on press, Media Pool
  grid cells stay compact, and collapsible asset/side sections have regression
  coverage so Show/Hide cannot collapse the entire section header again.
- Timeline clip thumbnails are decorative texture, not the only duration cue.
  `TrackRow` paints a muted per-track color block first, keeps the blurred
  thumbnail inset and semi-transparent, then redraws a full-width top rail,
  left/right caps, and a compact duration chip so clip length remains legible
  even when thumbnails are soft or dark.
- Preview transport now treats Play as a clip audition when possible. The
  editor resolves the selected video clip first, then the clip under the
  playhead, calls `ProjectPlayer.play_until(end_ms, return_to_ms=...)`, and
  restores the original playhead after the clip end. Real preview frames also
  clear the empty-project placeholder so the "Start your edit" card cannot
  remain behind video/GL playback after media is on the timeline. Placeholder
  mode now also hides stale GL preview surfaces and resets cached RGB/frame
  size state, while GPU-frame delivery clears the QLabel backing pixmap after
  the GL update so a small letterboxed GL frame cannot reveal the old card
  underneath.
- The timeline palette area is a dense Screen Studio-inspired wallpaper strip,
  not separate text toolbars. Edit commands and draggable creative presets sit
  in one shared rounded `TimelinePaletteBar`; Fade, Typography, Zoom, Speed,
  Spine, and Live2D are colorful swatch tiles from `app/effect_cards.py`.
  Avoid reintroducing wide status chips or separate row chrome into this area.
- The current Screen Studio direction for timeline tools is square,
  icon-first palette tiles. Select/Blade/Ripple/Roll/Slip/Slide, Trim, Nest,
  Split, Scopes, and Mixer use `QToolButton#ToolTile` in
  `app/video_editor_window.py`, with labels visually hidden until hover.
  Drag/drop cards in `app/effect_cards.py` are also square swatch tiles; their
  labels are empty by default and populated only on hover. Preserve this
  icon-first behavior when adding new timeline tools.
- The edit-tool tiles and drag/drop effect tiles now live inside one rounded
  `QWidget#TimelinePaletteBar` parent as a single compact row.
  `QWidget#TimelineToolBar` and `QWidget#TimelineEffectsBar` are only inner
  transparent groups. Keep future palette additions inside that shared parent
  so the timeline area keeps the Screen Studio wallpaper-palette composition.
- The current palette refinement uses 40 px icon-first tool tiles and 32 px
  painted swatches, with hover/checked states changing borders rather than
  replacing the tile artwork. This preserves the wallpaper-thumbnail feel.
  The selection/status row under the palette is intentionally icon-only and
  low-height; do not reintroduce persistent instruction text in that strip.
- Creative-layer workflow is now tracked as a product claim gate, not only as
  scattered UI affordances. The Python Action surface includes
  `transition.apply`, `transition.clear`, `clip.set_filter`,
  `clip.set_color_grade`, node graph actions, typography actions, actor
  actions, and `creative_layer.readiness`. The QA artifact
  `debugCapture/creative_layer_readiness_qa.json` reports effects,
  transitions, typography, node graph productization, Live2D/Spine workflow,
  AR/PBR 3D compositing, and template ecosystem depth. The safe positioning is
  "creator-grade creative layer foundations"; this is not yet a full
  Fusion/After Effects/Marmoset/CapCut creative-suite replacement.
- Screen Studio competitiveness is now treated as a functional editing path,
  not only a visual theme. The top command bar exposes an icon-only Auto
  Polish action and the Command Palette indexes it under Screen Studio / auto
  zoom / cursor polish. Auto Polish reads `*.cursor.json` sidecars when
  available, generates real per-clip `ZoomActor` windows, stores cursor polish
  and background/padding/shadow intent in `screenstudio_polish`, and seeks the
  preview to the first generated zoom. `ProjectPlayer` applies clip-level zoom
  before track-level zoom so the generated polish is visible immediately;
  export and render-queue jobs include clip zoom actors for single-source
  tracks to keep preview/export parity. New recordings written by
  `FrameRecorder` save cursor movement/click metadata beside the MP4 as
  `<video>.mp4.cursor.json`; the captured video plate intentionally excludes
  the OS cursor so the editor can re-render it with smoothing, click rings,
  scaling, and static-cursor hiding. The preview and export CPU paths both use
  `app/screenstudio_polish.py` to draw cursor FX and, when Auto Polish enables
  project-level `screenstudio_polish`, the same wallpaper-gradient padding and
  shadow frame style is baked into render-queue/export output.
- Auto Polish is now user-tunable, not only a one-shot command. The top toolbar
  opens `ScreenStudioPolishDialog`, which edits the project-level
  `screenstudio_polish` payload live. The panel exposes Screen Studio-style
  presets (`Clean Tutorial`, `Product Demo`, `Cursor Focus`, `Shorts Vertical`,
  `Soft Wallpaper`) plus cursor scale, smoothing, static-cursor hide, click-ring
  duration/color, wallpaper palette, padding, shadow, vertical handling, auto
  zoom scale, and zoom duration. Slider changes refresh the current preview
  immediately without requiring Apply; the Generate button uses the current
  panel values when creating per-clip `ZoomActor`s. Background palettes are
  cached in `screenstudio_polish.py` so repeated preview/export frames do not
  regenerate the same gradient.
- Screen Studio polish now treats interaction metadata as product data, not a
  decorative afterthought. Cursor sidecars distinguish click, drag, release,
  key, and hotkey events; preview/export can render click rings, release
  feedback, drag trails, key badges, static-cursor hiding, wallpaper padding,
  rounded screen corners, and edge-safe auto zoom crops from the same shared
  `screenstudio_polish` compositor. `screenstudio_polish_parity_report()` is
  the lightweight QA hook for checking deterministic preview/export compositor
  parity without launching the full editor or ffmpeg.
  The frame compositor no longer depends only on pre-filled
  `clip.cursor_events`: `screenstudio_fx_enabled()` and `apply_cursor_fx_rgb()`
  detect and lazy-load `<video>.cursor.json` sidecars from `owner.source_path`,
  so Media Pool AP status, preview frames, and export prerender decisions stay
  aligned even after project reload or alternate clip creation paths. Preview
  owner resolution and `VideoEditorWindow._snapshot_clip_effects_for_export()`
  also fall back from clip-level `cursor_events` / `screenstudio_polish` to
  track-level metadata, so cursor/click animation remains visible when metadata
  was attached to the track.
  `FrameRecorder` records hotkey labels only for tutorial-safe chords and
  function/navigation keys, intentionally ignoring plain text-entry letters and
  numbers unless a modifier key is part of the chord. This keeps hotkey callouts
  useful for tutorial videos without turning sidecars into text logs.
  Cursor motion uses a Screen Studio-style click settle: `click_hold_ms` holds
  the pointer briefly on click/release/hotkey events before interpolating toward
  the next sidecar sample, so click rings feel anchored instead of sliding away
  immediately. The Auto Polish dialog exposes this as `Click hold`.
  `screenstudio_interaction_report()` summarizes capture readiness from a real
  sidecar by counting click/drag/release/hotkey events, generated auto-zoom
  windows, hotkey labels, and compositor parity warnings; the micro-interaction
  QA report includes that readiness summary.
  Auto Zoom candidate inference uses raw cursor samples to detect long
  stationary "dwell" moments as soft zoom targets, and same-position
  click/release pairs are collapsed so default recordings do not produce
  redundant jumpy zoom windows. Candidate scheduling prefers fewer clean zooms
  over stacked motion: if a late candidate cannot be shifted before/after
  existing windows without overlap, it is dropped. Long recordings use
  `screenstudio_zoom_timing_profile()` to expand the Auto Zoom budget and space
  zoom windows across the capture instead of clustering every emphasis near the
  opening seconds; `screenstudio_interaction_report()` exposes the same
  `zoom_timing_profile` for QA and UI diagnostics.
  Cursor polish also supports loop-back: when enabled, the cursor eases back
  toward the first visible cursor position near the end of the source range,
  making tutorial clips easier to loop without an abrupt pointer jump. Auto
  Polish QA reports `cursor_loop_ready` and `cursor_loop_return_ms`.
  Media Pool video thumbnails use an `AP` badge when a cursor sidecar is found;
  clicking that badge focuses the matching timeline clip when present and opens
  the Auto Polish panel. Metadata/tooltips show readiness, click/drag/hotkey
  counts, hotkey labels, and candidate zoom-window count. The Auto Polish dialog
  shows the same readiness summary for the current selected clips, updating when
  polish settings change or when Generate Zoom Windows is run. It also lists the
  per-clip auto-zoom candidates before generation; each candidate can be toggled
  off or directly edited by start/end time and crop rectangle. The preview draws
  temporary zoom-candidate boxes while the Auto Polish panel is open; selecting a
  candidate seeks to its frame, and the preview box can be dragged or resized by
  edge/corner handles to update the same crop override fields. Generation
  stores/applies those disabled `target_index:point_index` keys plus per-candidate
  overrides. Auto Polish zoom actors carry preset-specific motion metadata:
  `zoom_easing` (`smooth_pop`, `cinematic`, `snappy`, or `linear`),
  `zoom_motion_blur`, and `zoom_focus_bias`. Preview and CPU prerender export
  both use the shared `zoom_window_at()` / `zoom_motion_blur_amount()` helpers,
  while the FFmpeg crop filter path uses the same easing expression when it is
  not prerendering. Generated clips show an `AP` status badge on the timeline.
  `tools/qa_screenstudio_auto_polish.py` validates the fixed cursor/click/drag/
  hotkey fixture corpus in `qa_corpus/screenstudio_auto_polish`, checks preview/
  export visual parity, and materializes small real MP4 samples with matching
  cursor sidecars under `debugCapture` for end-to-end QA. QA Dashboard exposes
  that report as "Screen Studio Auto Polish".
  `tools/qa_screenstudio_naturalness.py` is the higher-level product-feel
  guardrail for this path. It scores zoom-candidate framing, overlap-free zoom
  windows, long-recording zoom rhythm, cursor loop-back, preview/export parity,
  and starter export intents; QA Dashboard exposes it as "Screen Studio
  Naturalness". The `long_walkthrough` fixture checks that a 90-second screen
  recording receives enough rhythmic zoom emphasis across the whole timeline.
  The report summary includes `long_samples`, `long_rhythm_ok`, and
  `long_coverage_ok`, so long-recording coverage is tracked separately from
  short demo clips.
  `tools/qa_screenstudio_visual_polish.py` renders before/after contact sheets
  and now also measures isolated cursor-focus deltas, so the QA path catches
  cases where wallpaper framing changes but click/drag/hotkey cursor animation
  is too faint to read in the actual video frame.
  `tools/qa_visual_baseline_audit.py` now treats Screen Studio GUI-flow and
  export-handoff reports as baseline inputs too: a healthy visual baseline must
  have approved screenshots, a passing visual regression report, passing
  Screen Studio GUI-flow, passing export handoff, and default export readiness.
  It also requires `screenstudio_default_beauty_ready`, which comes from the
  export-handoff report's default result beauty score.
  `screenstudio_default_export_settings()` provides delivery intent metadata
  for Screen Studio-style starters: web demo, product demo, social vertical,
  and editor roundtrip. The editor applies those computed format/quality/FPS
  defaults when creating a new project instead of overwriting them with the
  timeline FPS immediately afterward. The Export button tooltip and final
  checklist expose the same delivery intent, format, quality, resolution, FPS,
  and Auto Polish readiness so Screen Studio-style projects communicate whether
  they are ready before the user starts rendering. A directly opened empty
  editor also seeds the Screen Studio web-demo defaults (`MP4/high`,
  `1920x1080`, `60fps`) before UI construction, so first-run export state is
  explicit instead of falling back to an ambiguous original-resolution preset.
  Those defaults also describe post-export handoff: MP4 web/product/social
  deliveries are clipboard/local-share ready, editor-roundtrip exports are
  local-package ready, and `share_link_ready` only becomes true when a share
  provider is configured. `screenstudio_share_provider_config()` normalizes
  the local/workspace/custom-template providers, while
  `screenstudio_build_share_link()` produces a deterministic share handoff URL
  for configured providers without requiring cloud upload from the core app.
  Successful single exports copy the output path to the clipboard when
  `copy_path` is present in `post_export_actions`; local-share actions also
  write `<output>.share.json` beside the exported video with intent, format,
  quality, resolution, destination, share provider, share URL, and handoff
  metadata.
  `tools/qa_screenstudio_export_handoff.py` validates web, social, product,
  editor-roundtrip, and configured share-link scenarios, validates the shared
  export-completion summary, and checks the default record/edit/export path for
  delivery defaults, frame styling, cursor FX, local-share handoff, and
  auto-zoom coverage. Successful single exports use that same completion model
  for a concise dialog with Reveal Output and Copy Path actions. QA Dashboard
  exposes it as "Screen Studio Export Handoff". Render Queue completion uses
  the same model: `app.render_queue_panel.RenderQueuePanel._on_success()`
  writes local-share manifests for eligible jobs, appends the Screen Studio
  completion summary to job diagnostics, and the diagnostics detail view lists
  completion status, manifest path, and Reveal/Copy/share actions.
  `app.render_queue.render_queue_product_diagnostics()` also includes the
  completion payload for completed jobs, so render history and Health/QA
  surfaces describe export handoff consistently.
  `screenstudio_simple_mode_profile()` is the shared product policy for the
  focused Screen Studio-style workspace: primary surfaces are record/import,
  preview, Auto Polish, trim, and export, while Media Pool, Workbench, node
  graph, actor lanes, Color, Audio, and Render Queue are classified as advanced
  drawer surfaces for simple-mode projects. `screenstudio_default_result_beauty_score()`
  is the default-result gate for "import/record then Export": it scores
  delivery defaults, wallpaper/frame styling, cursor FX, Auto Zoom, handoff,
  simple-mode policy, motion defaults, vertical-safe metadata, audio defaults,
  and golden-video coverage. The editor export badge appends this score, and
  `tools/qa_screenstudio_export_handoff.py` writes `default_beauty_ready` plus
  `default_beauty_score`. `screenstudio_audio_defaults()` supplies the default
  voice-normalization, noise-cleanup, dialogue-cleanup, and loudness intent for
  screen-recording starters. `screenstudio_default_golden_video_probe()` is the
  first golden short-video gate: it renders representative frames and verifies
  wallpaper/frame styling, cursor/click pixels, Auto Zoom planning, and
  preview/export compositor parity. The current synthetic default
  record/edit/export QA passes at 100/100.
  `app.screenstudio_parity` owns the explicit remaining-parity contract:
  `screenstudio_simple_mode_project_patch()` seeds true simple-mode project
  settings with polish/audio/transcript/export defaults and an advanced drawer
  surface map; `screenstudio_cursor_renderer_quality_report()` checks the
  product-grade cursor requirements; `screenstudio_transcript_subtitle_plan()`
  turns transcript segments into Subtitle-compatible styled rows, while
  `screenstudio_parse_srt_text()` and `screenstudio_subtitle_rows_from_srt_text()`
  power the editor SRT import path with the same Screen Studio caption presets.
  The remaining near-100% parity work is now expressed as first-class report
  functions instead of loose TODO prose:
  `screenstudio_first_run_empty_project_report()` locks the no-template-first
  empty-project path; `screenstudio_motion_tuning_report()` scores cursor/zoom
  smoothing, click settle, drag/dwell tracking, motion blur, crop breathing
  room, and overlap resolution; `screenstudio_manual_zoom_viewer_affordance_report()`
  defines viewer drag handles, keyboard nudge UI, duration/easing popover, live
  drag feedback, and undo commit; `screenstudio_vertical_social_export_plan()`
  defines safe-area/social-preview/thumbnail/contact-sheet readiness;
  `screenstudio_export_handoff_polish_report()` checks GIF/WebM preset parity,
  4K60 validation, share manifest readiness, and rich post-export card fields;
  `screenstudio_audio_subtitle_timing_report()` compares loudness/dialogue
  defaults with styled subtitle timing; `screenstudio_golden_short_video_baseline_plan()`
  defines golden short-video samples; `screenstudio_real_project_corpus_run_report()`
  defines before/after artifact paths for the 20-50 real recording corpus; and
  `screenstudio_advanced_strengths_separation_report()` keeps Live2D/Spine,
  node graph, Color, Audio, and general editor tools accessible without making
  them compete visually with the simple Screen Studio path.
  `screenstudio_recording_corpus_plan()` reports fixture count, real recording
  roots, 20/50 corpus targets, and missing capture slots without treating
  synthetic fixtures as external user recordings; `screenstudio_register_real_recording()`
  stores large user recordings by reference in
  `qa_corpus/screenstudio_real_recordings/manifest.json` so they can join corpus
  QA without being copied into the repo. If no slot id is supplied, the next
  empty `screenstudio-real-XX` slot is assigned automatically.
  `screenstudio_register_real_recordings_from_roots()` and
  `tools/register_screenstudio_real_recording.py --scan-root <folder>` batch
  register real local videos while ignoring tiny/non-video files. Video imports
  in both Simple and Full editor modes quietly register valid video paths as
  real-corpus candidates, so ordinary editing sessions help populate the Screen
  Studio parity corpus. Batch registration reports the same
  `missing_for_minimum` count used by corpus QA, so intake progress cannot show
  a stale minimum gap after 20+ recordings are already registered. Registration
  now records adjacent cursor sidecar status (`<video>.mp4.cursor.json` or
  `<video>.cursor.json`) in the manifest, and
  `tools/register_screenstudio_real_recording.py --scan-root <folder>` with
  `--require-sidecar` only admits recordings that already have cursor metadata.
  This keeps the "50 video files exist" gate separate from the stricter "20+
  interaction-ready cursor sidecars exist" gate.
  `screenstudio_real_recording_corpus_report()`
  is the deeper corpus verifier: it validates file existence/size/type, probes
  video frame metadata through OpenCV when available, checks cursor sidecar
  readiness through the same interaction report used by Auto Zoom, summarizes
  click/drag/hotkey counts, auto-zoom window count, per-recording interaction
  readiness, duplicate slot IDs, and progress toward the 20/50 real-recording
  target. `tools/qa_screenstudio_real_recording_corpus.py` writes
  `debugCapture/screenstudio_real_recording_corpus_qa.json`, and QA Dashboard
  exposes it as "Screen Studio Real Corpus". `tools/qa_screenstudio_parity_gap.py`
  writes `debugCapture/screenstudio_parity_gap_qa.json`, and QA Dashboard shows
  it as "Screen Studio Parity Gap". The empty editor startup and New Project
  flow merge `screenstudio_simple_mode_project_patch()` for Screen Recording,
  Vertical Shorts, and Product Demo starters, so those projects carry
  `screenstudio_simple_mode_ui`, audio defaults, transcript defaults, and
  export defaults immediately instead of only reporting the policy in QA. In
  editor UI, the main toolbar exposes an iPhone Control Center-style
  `Simple / Full` workspace switch so the user can see and change the active
  mode directly. Simple Mode keeps the left Media Pool and right Workbench
  visible because they are core TigerCapture surfaces. The `Panels` toolbar
  toggle only collapses secondary preset/render/audio/subtitle panels, never
  the Media Pool or Workbench.
- The next Screen Studio productization pass turns remaining real-world polish
  into actionable app/QA artifacts. `screenstudio_real_recording_intake_board()`
  lists uncovered 20-slot real recording targets, shows per-slot capture
  requirements, and points to `tools/register_screenstudio_real_recording.py`,
  which registers large local recordings by manifest reference.
  `screenstudio_real_recording_slot_board()` is the per-slot readiness board:
  each required recording target reports `empty`, `invalid`, `needs_sidecar`,
  `needs_clicks`, `needs_drag_hotkey`, `needs_auto_zoom`, or `ready`, plus the
  register command, interaction quality score, missing interaction requirements,
  and click/drag/hotkey/auto-zoom counts. `interaction_ready` now requires all
  four practical interaction signals, not just clicks plus auto zoom.
  `screenstudio_real_recording_corpus_report()` also exposes
  `replacement_claim_ready`, `replacement_claim_blockers`,
  `sidecar_needed_for_replacement`, and
  `interaction_needed_for_replacement`, so Screen Studio replacement wording is
  blocked by explicit corpus math rather than a vague recurring advisory.
  `build_final_product_readiness_report()` now has a dedicated
  `screenstudio_interaction_corpus` release area and treats this as a hard
  release blocker: a project can no longer report `release_ready=true` while
  cursor sidecar, click, drag, hotkey, auto-zoom, or interaction-ready counts
  are below the real-world target. The top-level report also exposes
  `screenstudio_replacement_claim_ready` so marketing copy can distinguish
  "release candidate" from "safe to call a Screen Studio replacement".
  `app.screenstudio_sidecar_intake` adds a safe intake bridge for this gap:
  `tools/prepare_screenstudio_sidecar_intake.py --write-templates` creates
  per-recording `.cursor.template.json` checklists that name the expected
  `<video>.cursor.json` target and required click/drag/hotkey/auto-zoom
  evidence. These templates deliberately contain no counted events and are not
  accepted as corpus readiness until real interaction metadata is captured.
  QA Dashboard exposes `debugCapture/screenstudio_sidecar_intake_qa.json` as
  "Screen Studio Sidecar Intake", and final readiness points to the same tool
  whenever the replacement corpus is blocked by missing sidecars.
  `app.screenstudio_sidecar_capture` and
  `tools/record_screenstudio_cursor_sidecar.py` provide the next step after
  intake: they write counted `<video>.cursor.json` files from a filled
  `.cursor.template.json` via `--from-template`, from a reviewed event JSON
  file, or from a short Windows live cursor capture, then can register the video
  with `--register --require-sidecar` semantics. Empty templates are rejected by
  default, so checklist files cannot accidentally become QA evidence. A generated sidecar only
  reports `counts_for_qa=true` when click/release, drag, hotkey, and auto-zoom
  readiness pass through the same `screenstudio_interaction_report()` gate.
  Sidecar intake templates and rows include a concrete
  `sidecar_capture_command` so a QA operator can move from checklist to counted
  sidecar without hand-editing paths. For batches,
  `tools/promote_screenstudio_sidecar_templates.py --register` scans a template
  directory, skips empty templates, promotes filled ones, and registers only
  sidecars that pass the same readiness gate by default.
  Smart Cursor FX extends the same sidecar path with `hit_role`, `hit_label`,
  `cursor_style`, and `animation` fields. TigerCapture recordings now try to
  classify the Qt widget under the cursor while recording, so timeline tools
  such as Blade/Split are saved as `blade_tool` and render as an animated
  `scissors` cursor with a `snip` click motion. The preview/export cursor
  renderer consumes those fields directly and supports pointer, hand/grab,
  scissors, I-beam, zoom, trim/slide, magic-AI, and color-picker cursor shapes.
  This keeps role-aware cursor changes renderable in final video instead of
  being only an OS cursor change.
  `screenstudio_adaptive_motion_tuning_patch()` derives conservative
  cursor/zoom tuning from current corpus readiness without pretending missing
  samples are available. `screenstudio_manual_zoom_viewer_command_model()`
  defines direct viewer handles, keyboard nudge behavior, tooltips, and status
  feedback for manual zoom editing. `screenstudio_export_result_parity_matrix()`
  locks MP4/WebM/GIF/4K60/vertical preview-export feature parity for
  wallpaper frame, cursor FX, click animation, zoom, subtitles, audio, effects,
  and color. `screenstudio_regression_hardening_plan()` keeps the known
  launcher, Live2D, Spine, Color, node graph, and timeline risks attached to
  concrete QA commands. `tools/qa_screenstudio_productization_next.py` writes
  `debugCapture/screenstudio_productization_next_qa.json`, and QA Dashboard
  exposes it as "Screen Studio Productization".
  `tools/qa_screenstudio_render_result_smoke.py` creates a tiny real MP4 smoke
  render and verifies file size, frame count, frame changes, FPS, and cursor
  highlight pixels. QA Dashboard exposes it as "Screen Studio Render Smoke" so
  preview/export polish is checked against an actual output artifact, not only
  static data contracts.
  `tools/qa_real_project_product_flow.py` scans real/local `.tgp` projects,
  verifies one-click preset plans are template-first and map to export-baked
  targets, and runs the same render-smoke artifact path. QA Dashboard exposes
  it as "Real Project Product Flow".
- Final product readiness is tracked separately from individual feature QA.
  `app.final_product_readiness.build_final_product_readiness_report()` and
  `tools/qa_final_product_readiness.py` aggregate release-facing areas:
  practical edit flow, real project corpus, Screen Studio interaction evidence,
  preview/GPU performance, preview scrub/seek claims, AI edit claim quality,
  Color/Audio accuracy, professional runtime parity, timeline polish, preset/
  template quality, crash recovery/project repair, and release packaging. The
  professional runtime parity area pulls in `Professional Runtime Next` and
  `Professional Pipeline Next`, so Resolve/Fairlight/Fusion-style payloads must
  exercise concrete frame, graph, local-ML, audio stress, and deliver checks
  before the final report can turn release-ready. The report distinguishes `ok`
  (the report/contract can be built) from `release_ready` (all areas score at
  least 90), so missing real recordings, smart-AI corpus evidence, scrub/seek
  coverage, or performance samples are not hidden behind a green implementation
  check. Top-level `commercial_claims_ready`,
  `screenstudio_replacement_claim_ready`, `preview_scrub_claim_ready`, and
  `smart_ai_edit_claim_ready` keep product-release status separate from
  competitor/AI marketing claims. QA Dashboard lists this as "Final Product
  Readiness" and can run it directly. The latest strict local evidence on
  2026-07-07 is `debugCapture/final_product_readiness_qa.json` at 99/100 with
  `release_ready=false`: practical edit flow, real project corpus, Screen
  Studio interaction corpus, preview/GPU performance, current-corpus scrub
  readiness, Color/Audio accuracy, professional runtime parity, timeline
  polish, presets, crash recovery, packaging, and direct smart-edit corpus
  evidence are ready. The current local artifact uses Qwen local direct
  evidence; previous Claude direct evidence also passed the same 20/20 corpus
  gate. Commercial broadcast evidence is the remaining release blocker, so
  `commercial_claims_ready=false` even though
  `smart_ai_edit_claim_ready=true`. The real
  recording manifest loader accepts UTF-8 BOM manifests so existing registered
  videos are no longer dropped from the corpus, and the new automation-generated
  local corpus path can provide 20/20 MP4 sidecars with click/drag/hotkey/zoom
  evidence for repeatable product QA. That corpus is explicitly tagged as
  generated evidence, not a human user recording study.
- The active 1~6 release-gap closure pass has its own smaller, claim-oriented
  audit surface. `app.release_gap_closure.build_release_gap_closure_report()`
  and `tools/qa_release_gap_closure.py` aggregate exactly six current product
  priorities: generative AI one-click editing, Screen Studio real-recording
  interaction corpus, preview scrub/seek responsiveness, Live2D/Spine
  real-model compatibility, release productization/public positioning, and
  UI/UX polish. The report returns `ok=true` when the audit can be built and
  `release_ready=true` only when all six areas are actually ready. It is
  intentionally stricter about claims than ordinary implementation checks:
  safe AI Script Edit MVP can pass while `smart_edit_claim_ready` remains
  false, and real recording files can exist while Screen Studio replacement
  wording remains blocked until cursor sidecars and interaction evidence pass.
  As of the current 2026-07-07 evidence run, `smart_edit_claim_ready=true`
  because `qwen_local` provider generation succeeded on 20/20 corpus cases
  without fallback. Earlier Claude direct provider runs also succeeded on
  20/20 corpus cases without fallback; Qwen is documented here as the latest
  local-default evidence path, not as the only provider that has ever passed.
  Use `tools/qa_release_gap_closure.py --strict` as the compact release gate
  when preparing public builds or marketing copy.
- The same remaining evidence can be pushed through a generated collection
  sprint without faking readiness. `app.release_evidence_sprint` and
  `tools/prepare_release_evidence_sprint.py` create a local sprint folder with
  a Screen Studio sidecar capture PowerShell script, AI real-case registration
  script, broadcast platform evidence registration script, safe sidecar
  templates, AI corpus templates, and a short playbook.
  The generated scripts are collection aids only: they do not write counted
  cursor sidecars unless the user performs real replay/cursor/hotkey actions,
  they do not register AI corpus cases until filled templates contain real
  transcripts, natural-language prompts, expected intents, and expected
  operations, and they do not register broadcast platform evidence until the
  operator supplies redacted RTMP and YouTube viewer evidence. The cursor recorder now
  defaults to the Windows virtual screen
  when no `--screen-rect` is supplied and can opt into modifier-hotkey capture
  with `--capture-hotkeys`, which keeps the real Screen Studio interaction
  corpus from getting stuck on missing hotkey evidence. A separate automation
  corpus builder, `tools/build_automated_release_evidence_corpus.py`, can create
  local synthetic MP4 recordings plus `.cursor.json` sidecars and AI transcript
  cases for repeatable QA; it registers every item with
  `evidence_provenance=automation_generated` /
  `counts_as_human_user_evidence=false` so product copy cannot treat it as
  customer evidence. The sprint report also
  writes a `progress` block with overall percent, Screen Studio
  interaction-ready counts, cursor-sidecar counts, AI real-case counts,
  broadcast platform evidence counts, and explicit blockers.
  `progress.screenstudio.requirements` breaks the Screen
  Studio proof into cursor sidecar, click animation, drag tracking, hotkey
  overlay, and auto-zoom window rows, each with ready/target/needed counts and
  an action. This is the release-facing guard against claiming Screen
  Studio-style automatic zoom and smooth cursor animation from ordinary video
  files alone. Progress is based on interaction-ready evidence, not just
  generated templates or sidecar filenames. The current 2026-07-05 sprint has
  templates/scripts prepared for 20 Screen Studio sidecars, 20 AI real cases,
  and 2 broadcast platform checks. The automation-generated local corpus now
  gives the release QA artifacts 20/20 Screen Studio interaction-ready sidecars
  and 20/20 AI real-case rows, while the operator sprint remains the path for
  human-reviewed sidecars/transcripts and redacted platform proof.
  `release_evidence_next_items()` also builds the sprint `work_queue`: concrete
  next tasks for the first blocked recordings, AI templates, and RTMP/YouTube
  platform checks, including the missing proof requirements, target
  `.cursor.json` or template path, and the safest command/action to run. The
  work queue is not evidence; it is the operator checklist for collecting
  evidence without guessing.
- `app.release_evidence_automation.build_release_evidence_automation_report()`
  and `tools/qa_release_evidence_automation.py` automate the part that is safe
  to automate after evidence exists: bulk-promote filled Screen Studio sidecar
  templates, bulk-register filled AI real-case templates, rerun broadcast
  platform/readiness QA, and refresh Final Product Readiness. The generated
  `debugCapture/release_evidence_automation/promote_filled_release_evidence.ps1`
  script intentionally calls only validated promotion/registration tools. Empty
  sidecar templates, placeholder AI prompts, and absent platform receipts remain
  blockers rather than being converted into counted evidence. The same report
  now also surfaces
  `debugCapture/release_evidence_automation/automated_release_evidence_corpus.json`
  when present, including its provenance and `counts_as_human_user_evidence`
  flag.
  `release_evidence_next_screenstudio_capture_target()` turns the first blocked
  Screen Studio work item into a one-slot PowerShell capture script
  (`record_next_screenstudio_sidecar.ps1`). The script opens the target video,
  waits for the operator, then calls `tools/record_screenstudio_cursor_sidecar.py`
  with `--capture-hotkeys --register` and the correct slot id, duration, and
  frame size. This is the preferred incremental capture UX because it collects
  exactly one real sidecar and then sends the user back to `Refresh Evidence
  Status`; it still never fabricates cursor events.
- QA Dashboard exposes the same release evidence sprint as an in-app action:
  selecting `Release Evidence Sprint` and pressing `Evidence Actions` prepares
  missing scripts if needed, then can open the cursor sidecar capture script,
  AI real-case registration script, broadcast platform evidence registration
  script, sprint playbook, or evidence folder. The same action dialog can rerun
  the Screen Studio real-corpus QA, AI corpus QA, and release gap gate after
  evidence has been collected. The cursor, AI, and broadcast scripts open in a
  visible terminal because they require real user replay, filled
  transcripts/prompts, redacted platform evidence, and post-run QA
  verification. The dashboard
  summary and Evidence Actions dialog show the same progress numbers so users
  can see whether they need more cursor interactions, AI real cases, or just
  follow-up QA. They now also show the per-proof Screen Studio requirement rows
  and the first evidence work-queue items, so a blocked state points at a
  specific recording/action instead of a vague advisory. The same dialog also
  exposes `Record Next Slot`, which writes/opens the one-slot capture script
  for the first blocked recording, `Register Next AI Case`, which prompts for
  one real transcript path, natural-language edit request, and review
  confirmation before filling/registering that single AI case, and
  `Refresh Evidence Status`, which
  reruns the Screen Studio real-corpus QA, AI corpus QA, broadcast platform
  E2E QA, broadcast release-readiness QA, evidence sprint generator, release
  gap gate, and final product-readiness gate in that order so every sales-facing
  gate reads fresh source evidence.
- Screen Studio-style manual zoom editing has a shared policy/helper path:
  `screenstudio_manual_zoom_edit_policy()` defines snap thresholds, minimum
  durations, handle sizes, nudge steps, and supported edit modes, while
  `screenstudio_apply_manual_zoom_edit()` applies move, edge resize, ramp
  handle, and target-rectangle edits with consistent clamping. Timeline zoom
  actor drags now use this policy instead of local ad hoc math, so move/resize
  handles snap to playhead/marker/edge targets and ramps stay inside the zoom
  span. `tools/qa_screenstudio_manual_zoom.py` verifies this path and QA
  Dashboard exposes it as "Screen Studio Manual Zoom". Edge target rectangles
  and oversized target rectangles are part of the QA contract so manual zoom
  edits do not crop at frame boundaries.
- The startup launcher is now the lightweight capture app boundary, not the
  default Tiger Studio entry point. Tiger Studio and the capture program are
  separated product surfaces; the capture program may be bundled with Studio,
  but capture-to-Studio handoff is blocked by default so capture stays small,
  fast, and focused. `app.launcher_studio_policy.capture_to_studio_enabled()`
  is the shared gate. Only explicit bundle/QA opt-in through
  `TIGERCAPTURE_CAPTURE_TO_STUDIO=1`, `TIGERCAPTURE_ALLOW_STUDIO_ENTRY=1`, or
  `TIGERSTUDIO_BUNDLED_STUDIO_ENTRY=1` exposes the Studio button, workspace
  switch, project/template opens, video-drop-to-editor behavior, and controller
  `VideoEditorWindow` construction. Without that opt-in, recording results are
  saved locally and Studio must be opened through the separate Tiger Studio app.
  `main.py` remains the capture-app entry point. `studio_main.py` is the Studio
  entry point, and packaged/source launchers can open it through
  the packaged `TigerStudio.exe`, `TigerCapture.exe --studio`, or the
  source-built `TigerStudio.exe` shim. PyInstaller builds must collect both
  `TigerCapture.exe` and `TigerStudio.exe` into `dist/TigerCapture`. Installer
  shortcuts should expose both the lightweight capture app and `Tiger Studio`
  while keeping the desktop shortcut focused on capture. Windows build tooling
  requirements live in `requirements-build.txt`; `build.ps1` must fail early
  with that install hint when PyInstaller is absent. NSIS and Inno Setup
  installers must use distinct output names so release artifacts do not
  overwrite each other: NSIS writes `installer_output\TigerCapture-Setup-<version>.exe`,
  while Inno Setup writes
  `installer_output\TigerCapture-InnoSetup-<version>.exe`.
  The launcher hero remains short, capture mode/delay/cursor options live in
  one thin settings bar, and the launcher body stays inside a scroll area so
  short windows do not clip capture controls.
- Left-dock preset libraries must stay scroll-safe. Effect, Title,
  Transition, and Workflow preset sections use painted square vector tiles in
  an adaptive `_PresetScrollGrid`; names are tooltip/hover information, not
  always-visible card text. The whole left dock is wrapped in
  `QScrollArea#LeftDockScroll`, so opening multiple preset sections must not
  hide lower section headers or stretch the dock beyond the viewport.
  Those sections are wrapped by `_PresetBrowser`: search stays above the
  scrollable grid, category chips filter large packs, top/bottom scroll
  shadows show hidden content, hover previews show name/metadata/details, and
  drag operations use a custom compact ghost instead of raw widget screenshots.
  `_PresetBrowser` also persists favorites and recent presets in a small JSON
  state file, adds pack-level filtering, and keeps hover previews animated so
  large commercial-style preset packs feel browsable rather than static.
  Hover previews must be contextual, not a shared decorative animation:
  effect previews reflect filter/keying payloads, title previews reflect text
  placement/animation, transition previews reflect the transition type, and
  workflow previews reflect template/caption/sticker/motion payloads.
  When a preview frame is available, preset hover previews use that frame as
  the sample: effects show an A/B original-vs-applied preview, chroma key
  previews composite against a checker background, titles overlay on the
  current frame, and transitions blend the current frame with a generated
  second source. Preview popovers include small QA badges, payload detail
  lines, and an intensity slider for effect/title/transition previews. Preset
  mini playback is payload-specific: transitions animate cross/wipe samples,
  motion presets show zoom/focus framing, title/caption presets slide text
  pills, stickers pop in, and templates also render a compact timeline plan
  strip so users can see how the one-click sequence will land before applying
  it. `Preview Apply` and A/B preset preview cache keys include the current
  preview-render version so visual polish changes invalidate old PNG swatches;
  effect previews draw payload-specific blur/denoise, sharpen, vignette,
  glitch, LUT, and key-matte hints instead of sharing one generic animation.
  Hovering effect and transition preset cards shows a viewer-frame overlay
  first, so the browsed FX/transition is visible even when no target clip is
  selected; when a selected/active target clip exists, the same hover also
  starts a delayed live preview on that clip. Leaving the card or starting a
  drag restores the original clip state without registering an undo step.
  Applying effect, transition, title, sticker, caption, or motion presets
  focuses the main preview on the affected timeline range and keeps a
  short-lived viewer overlay visible, so applied presets are not hidden simply
  because the playhead was outside their active frame range.
  Timeline video clips expose applied preset/effect state as compact badges:
  `FX` for clip filters, `Key` for chroma/alpha keying, `TR` for outgoing
  transitions, `T` for overlapping title/caption/sticker actors, `Mot` for
  overlapping motion/zoom actors, `Nest` for nested/compound clips, and `Off`
  when a clip FX stack is temporarily disabled but preserved. Clicking a badge
  selects the clip and routes the Workbench/preview to the relevant FX,
  transition, title, or motion context without starting a clip drag. The
  Workbench FX tab mirrors this with a selected-clip stack summary and safe
  Edit Clip FX, Disable/Enable Clip FX, Clear Clip FX, and Clear Transition
  actions. Disabled clip FX are saved on `VideoClip.disabled_video_filters`,
  `disabled_chroma_key`, and `disabled_bg_removal`, and are persisted through
  project save/load. Effect presets also preserve `preset_meta` inside
  `VideoFilterParams`, so the timeline can paint clip-length FX strips with
  human-readable preset labels. The same strip source now includes Screen
  Studio auto zoom, overlapping title/caption actors, overlapping motion/zoom
  actors, and nested/compound context, so the hover tooltip and painted strip
  describe the same active clip elements. Transition presets preserve
  `VideoClip.transition_preset_meta` through drag/drop, click apply, keyboard
  insert, context-menu insert, and project save/load, so transition strips can
  show names such as `Soft Zoom Bridge` instead of only raw transition types.
  These strips sit inside the clip body while the small badges remain clickable
  status shortcuts; narrow clips compact strip text to the tag and expose the
  full applied FX/transition/color list through a hover tooltip. Together they
  make applied effects/transitions look like editable timeline regions instead
  of invisible payloads.
  Hovering title, template, caption, sticker, motion, audio, or color preset
  cards starts a model-safe preview overlay on the viewer instead of mutating
  timeline data, so undo/redo remains clean while users browse creative packs.
  The left-dock `_PresetBrowser` includes a compact inspector panel that
  updates from hovered cards with target/cost/QA badges, payload hints, pack,
  category, and tag details. Static preset preview swatches are cached under
  `default_save_dir()/.cache/preset_previews` so reopening large preset
  libraries does not repeatedly repaint the same synthetic thumbnails. The
  Preset Preview Cache manager can also warm current-frame contextual previews:
  if a viewer frame exists, `_render_contextual_preset_preview()` stores
  sample-specific thumbnails keyed by preset payload plus a small frame digest,
  so A/B effect/title/transition previews can be reused on the active shot.
  Preset search supports natural Korean/user-language aliases through
  `PRESET_SEARCH_ALIASES` in `app.preset_library` and
  `_PRESET_NATURAL_QUERY_ALIASES` in `app.video_editor_window`. Queries for
  intro, game, vertical shorts, preset, sparkle, and Live2D concepts map to the
  English preset tags and rank stronger matches first.
  Preset browsers show a compact wallpaper-palette style pack row in addition
  to the pack combo and category chips, so users can switch packs through
  square color swatches.
  The Effects Presets action row exposes Template Composer, preset preview
  cache management, and Visual QA viewer entry points alongside save/import/
  export, pack management, QA, and one-click plan actions.
- The play/transport bar is also icon-first. Mark In, Mark Out, range clear,
  and Marker must not show text by default; their names live in tooltips.
  The former separate Clear/Edit/Color action strip is merged into the play
  bar so the timeline controls do not stack into multiple horizontal chrome
  bands. Speed is a compact `1.0x` chip, not the full localized
  `Current speed` sentence.
- The jog/shuttle widget keeps the existing jog/shuttle interaction contract
  but uses a compact, colorful Screen Studio-style knob rendering in the main
  editor instead of the earlier large metallic broadcast-deck circle.
- Shared `KnobWidget` controls render as soft glass tiles with a lively
  colored value arc, not as flat gray code-drawn circles. This affects color
  master knobs and audio-style knobs that use the shared widget.
- The embedded Color dock above the timeline is not the full Color Page. It is
  a compact Screen Studio-style palette strip with four small color-wheel
  swatches, compact LUT strength, and three primary grade knobs; it must avoid
  large numeric spinboxes or tall wheel grids that collide at normal editor
  heights.
- Edit/Color tab switches are preview-safe UI transitions. They must not
  mutate NodeGraph selection, and during the short transition guard they keep
  the last good preview frame when an unexpected tiny blank frame arrives while
  a renderable clip is active.
- The same preview transition guard is available to actor-editor focus and
  mask-edit refresh paths, so Live2D/Spine placement and node-mask edits do not
  leave the main viewer stuck on a transient blank frame.
- Offscreen UI layout QA must capture both the normal editor and the expanded
  compact Color dock. The color-dock capture checks compact height, palette
  card count, and absence of numeric spinboxes.
- Slider controls across the main editor, Workbench, Audio Mixer, Color page,
  Live2D editor, Spine editor, and node parameter widgets use the same quiet
  Screen Studio-style language: dark 3 px rail, compact round thumb, and a
  localized warm LED touch glow around the active handle that fades after
  release. Avoid full-rail glow fills, cyan/orange slider fills, or persistent
  neon bars unless the control itself is explicitly color-domain data.
- The editor icon strategy is code-native by default. `app/icons.py` provides
  vector icons for project menus, media/video/audio/actor filters, grid/list
  views, pop-out, delete, marker, mark-in/out, scopes, mixer, proxy/layers,
  color, fit, nest, play/pause/reset, previous/next, loop, and timeline edit
  tools. Main editor buttons, Sound Editor transport buttons, Typography preview
  transport buttons, and Media Pool buttons use code-native icons instead of
  font-dependent symbol glyphs, which keeps the UI stable across Korean/CJK
  font fallback.
- The Color/Color Grade icon must read as color grading, not a generic paint
  palette. `app.icons.app_icon("grading")` and the `color`/`palette` aliases
  draw a small color wheel plus curve/scope stroke, and the main Edit/Color page
  switcher uses that grading icon for the Color page.
- Timeline row play/status marks are painter-native shapes in
  `VideoTrackRow.paintEvent()`, not text glyphs. Keep future row-watermark and
  transport symbols in painter/icon code so offscreen QA, Windows fonts, and
  localized UI stacks do not change their appearance.
- The same font-independent rule now covers the high-traffic editor chrome:
  project buttons, actor buttons, audio scopes/mixer toggles, Edit/Color page
  buttons, PiP keyframe buttons, clip context-menu actions, Workbench mask
  action buttons, Live2D drag preview badges, and audio-track watermarks use
  `app.icons.app_icon()` or direct painter shapes instead of emoji/symbol text.
- Timeline edit tools use micro-interaction feedback. Mouse presses and
  keyboard mode changes pulse the active icon, blade cuts emit a short
  timeline burst at the cut point, timeline drops show a compact insertion
  guide for non-transition assets, and transient status is shown through a
  rounded toast banner rather than raw tooltips.
- Preset state is managed directly on timeline clips. Applied FX/Key/TR/Color/
  Title/Motion/Nested badges are clickable focus targets, and right-clicking a
  badge opens a focused badge menu for edit/focus, enable/disable FX, clear FX,
  or clear transition depending on the badge type. Dragging an effect preset
  over a valid clip shows the apply chip; hovering over empty timeline space
  shows a blocked chip that explains the preset must be dropped on a clip.
  `app.preset_feedback` centralizes the user-facing model for preset apply
  chips, badge labels, drop-blocked reasons, duration/time formatting, and
  Media Pool/Workbench discoverability cards. Successful apply events now carry
  this feedback model in UX telemetry.
  It also exposes `preset_timeline_strip_rows()`, `preset_preview_ab_model()`,
  and `timeline_interaction_feedback_model()` so timeline badges/strips,
  current-frame A/B preset previews, snap/drop/undo chips, QA reports, and
  future editor widgets use the same product-facing copy and timing data.
  `tools/qa_creator_polish_coverage.py` now gates this area together with
  payload-specific preset previews, Screen Studio defaults, CapCut quick-create
  flow, and long-project stability hooks.
- The main Select/Blade/Ripple/Roll/Slip/Slide timeline tool buttons use
  `_AnimatedTimelineToolButton`, a painter-native animated icon tile. The
  Select tool draws its cursor directly with hover/checked lift, glow, sparkle,
  and trail motion; neighboring edit tools keep the same square palette but add
  subtle icon motion so the toolbar feels closer to Screen Studio instead of a
  static Qt button row.
- The icon pass also covers the launch window, clip-effects tabs, Mask Editor
  zoom controls, Subtitle pop-out, Workbench node-graph toolbar/context menus,
  and the immediately visible Live2D/Spine editor controls. Those surfaces
  should continue using `app.icons.app_icon()`/`QIcon`/`QPixmap` rather than
  embedding emoji or transport glyphs in button text.
- Empty editor states are part of the product surface. The Preview panel draws
  a native rounded canvas/card for empty and audio-only projects instead of
  showing raw label text, and the Workbench hides property rows until a real
  clip/track is selected so the right dock reads as intentional rather than
  disabled form controls.
  Preview left-click is reserved for the paint/bubble/sticker canvas once any
  renderable video/actor frame exists. Import/open-media dialogs may appear only
  when the preview is genuinely empty; GPU-preview-only frames must be promoted
  to a paint `QPixmap` instead of being mistaken for an empty preview.
  Detached preview mirrors both the QImage and GPU RGB paths, and Live2D/Spine
  actor-only frames are treated as renderable content instead of being filtered
  out as "no video" placeholders.
  The OpenGL preview widget is intentionally lazy-created on the first real
  frame. Startup WinEventHook tracing showed that eager `QOpenGLWidget`
  construction creates transient Qt/NVIDIA helper windows
  (`NVOpenGLPbuffer`, `__wglDummyWindowFodder`, and a hidden 2x2 Qt window)
  during launcher-to-editor startup; an empty editor must not instantiate that
  path.
  Startup menu buttons follow the same rule: export, color, proxy, project,
  actor, and secondary command menus are built only on user press. Eager
  `QMenu` construction creates `Qt6110QWindowPopupDropShadowSaveBits` native
  popup/drop-shadow windows on Windows, which looks like many tiny flashing
  windows even when the menu is never shown.
  Current launcher-to-editor flicker diagnosis must be evidence-based, not
  inferred from process names alone. Official platform docs say
  `CREATE_NO_WINDOW` applies to console applications, Python exposes that flag
  through `subprocess.Popen(..., creationflags=...)`, Qt starts Windows child
  processes through `CreateProcess`, and Qt popup menus are native top-level
  widgets. Therefore startup QA distinguishes actual user-visible console
  windows from hidden Qt popup/drop-shadow/helper windows.
  The product-flow check is:
  `tools/trace_visible_windows.py --duration 10 --log-path debugCapture/startup_trace_logs/visible_window_trace_no_internal.jsonl -- .venv/Scripts/python.exe tools/trace_launcher_open.py --no-internal-trace`, followed by
  `tools/analyze_visible_windows.py debugCapture/startup_trace_logs/visible_window_trace_no_internal.jsonl`.
  The current passing baseline is `Visible console-like rows: 0` and no
  DWM Ghost rows in the product path. The internal `StartupFlickerTracer` is
  intentionally low-frequency and app-focused because aggressive all-process
  polling can itself create UI stalls and false DWM Ghost artifacts while
  Codex/Git/PowerShell helpers are active.
  The launcher delay selector uses segmented buttons instead of `QComboBox` so
  opening the editor does not pre-create a combo popup/native menu surface.
  The editor's former `startup_yield` hook no longer calls
  `QApplication.processEvents()` by default. Trace evidence showed that pumping
  events while the editor tree was half-built let parentless `QLabel`,
  `QPushButton`, and `QWidget#SelectionBar` objects become short-lived native
  `Qt6110QWindowIcon` windows titled "TigerCapture". The hook now only logs
  phases unless `TIGERCAPTURE_STARTUP_YIELD=1` is set, re-parents hidden
  orphan widgets at each bootstrap phase, and hidden toolbar placeholders such
  as the dormant Spine buttons have explicit parents.
  Windows/Qt startup widgets must be parented at construction time, not only
  after later `layout.addWidget(...)` calls. `WorkbenchPanel`, Workbench row
  widgets, the color/timeline splitter surface, Media Pool, preset browsers,
  toolbar controls, timeline palette controls, and collapsible section headers
  now pass explicit parents while being built. `cleanup_hidden_qt_orphan_windows`
  also handles hidden custom `QWidget` subclasses, but that cleanup is a safety
  net rather than the main strategy. The latest product-path trace
  `debugCapture/startup_trace_logs/visible_window_trace_parented_no_internal.jsonl`
  and internal diagnostic trace
  `debugCapture/startup_trace_logs/visible_window_trace_mediapool_parented.jsonl`
  show `Visible console-like rows: 0`; during the measured startup interval the
  only visible TigerCapture Python windows are the normal launcher and the real
  video editor. Hidden `Qt6110QWindowPopupDropShadowSaveBits` rows are native Qt
  helper surfaces, and DWM Ghost rows that appear after the diagnostic harness
  calls `os._exit()` are treated as teardown artifacts, not launcher startup
  flicker. User real-run confirmation on 2026-06-22: the launcher-to-editor
  flashing-window issue is fixed in practice. Startup crash-report notices are
  only shown for actionable, non-stale crash payloads; malformed or stale
  `crash_report_latest.json` files stay available in diagnostics but do not
  interrupt the launcher/editor entry path.
  Media Pool video tiles support hover scrub previews, and the Workbench keeps
  the existing Clip/FX/Mask/Audio/Meta contract while using icon-first tabs,
  compact swatches, and card-like empty states to match the Screen
  Studio-style palette direction.
- UI layout QA mirrors app startup font/theme setup. `tools/qa_ui_layout.py`
  creates a QApplication, applies `app.font_fallback.apply_ui_font()` and
  `app.style.APP_QSS`, then initializes i18n before instantiating
  `VideoEditorWindow`, so captured screenshots reflect the real app shell
  instead of Qt's offscreen defaults.
- The video editor command bar includes a compact globe language menu backed by
  `app.i18n.SUPPORTED_LANGUAGES`. Selecting a language calls `set_language()`
  and `save_language()`, then immediately refreshes the window title, primary
  toolbar labels/tooltips, preview/timeline/color/media/effects section labels,
  export dropdown text, and localized effect-preset guidance in the current
  editor session.
- Media Pool filtering is first-class UI. `app/media_pool.py` stores each item
  kind (`V`, `A`, `S`) on the `QListWidgetItem` and applies search/type filters
  without changing the registered media order.
- Media Pool also supports Grid/List presentation and Name/Type/Duration sort
  modes. Sorting reorders only the visible pool widget items; registered media
  paths and drag payloads remain path-based. Empty bins, filtered-out results,
  supported drag imports, and unsupported drops are reported through the shared
  UX feedback state instead of ad hoc label text.
  Long-project smart bins include Proxy Missing, Proxy Stale, and Duplicate
  Name filters so proxy debt and filename collisions can be found without
  leaving the Media Pool.
- New Project Dialog exposes starter template choices such as Blank, Screen
  Recording Demo, Vertical Shorts, Gameplay Highlight, Product Demo, and
  Live2D/Spine Actor. The selected starter id/label is preserved on
  `ProjectSettings` so one-click preset packs can route the first timeline
  setup.
- Sound Editor remains clip-scoped, but the normal video-editor surface is now
  the renewed Workbench audio panel from `app/sound_editor_panel.py`.
  Waveform and compact spectrum/level evidence sit in the panel, and the
  frequently used Basic/EQ/Dynamics/FX/AI controls are shown as compact
  icon-tab graph controls rather than the old full lab layout.
- The right Workbench/Inspector dock has a larger default share than the first
  UI pass: the main splitter defaults to `[248, 880, 360]` with right-dock
  stretch `2`, and the Workbench section gets more vertical stretch than PiP or
  subtitles. `WorkbenchPanel` is now backed by a real `QStackedWidget` with
  `Clip`, `FX`, `Mask`, `Audio`, and `Meta` pages. Clip/audio rows move between
  the Clip and Audio pages; the node graph lives on FX; blur/mask controls live
  on Mask; Meta shows a compact selection summary.
- The main editor right dock includes an Audio Workspace bridge. It finds the
  selected audio clip, the clip under the playhead, the first loaded audio clip,
  or a selected Media Pool audio source, then routes it into the Workbench
  `SoundEditorPanel`. Timeline sound-editor launches use
  `SoundEditorDockWindow`, a lightweight shell around the same renewed panel.
  The legacy `SoundEditorWindow` remains the explicit Advanced Lab for heavier
  waveform/spectrum/marker/stem/export workflows. Mixer and Scopes toggles stay
  mirrored so audio editing is discoverable without double-clicking the
  timeline.
- Spine and Live2D standalone editors share the darker professional palette,
  thicker splitter handles, and bordered asset lists/tree panels so they read
  as part of the same tool family.
- Project files are `.tgp` JSON. They intentionally do not store generated
  caches like thumbnails, waveform peaks, OpenGL state, or preview pre-render
  frame caches. Tracked mask bbox caches are project data because they represent
  user-correctable tracking state.
- There are two important render worlds: interactive preview
  (`ProjectPlayer`) and final export (`VideoExportThread`). Never assume a
  feature works in export just because it appears in preview.
- Real-project QA is scriptable. Use `tools/qa_project_audit.py --project
  path\to\edit.tgp --synthetic` to audit missing assets, feature coverage,
  media-probe timings, Live2D/Spine actor asset summaries, and synthetic export
  parity together. Add `--preview-samples <N>` to sample actual ProjectPlayer
  preview renders and include native/GPU bottleneck hints in the same report.
  Preview sampling now adds clip and actor active positions, so low sample
  counts still hit Live2D/Spine clips instead of only the start/end frames.
  QA reports also include `export_risks` for CPU fallback, actor baking,
  high-resolution decode/proxy, and nested timeline risk, and actor asset QA
  follows Spine atlas texture references plus Live2D model3 moc, texture,
  motion, and expression references.
  QA reports include `preview_engine` status from
  `app.preview_engine_status.preview_engine_status()`.
- Live2D/Spine model-corpus QA has a combined entry point:
  `tools/actor_render_qa.py <roots...> --parse-spine --limit N --summary-only`.
  It runs the fast dependency compatibility matrix first, then reuses the
  actual Spine and Live2D render-test paths to produce one JSON report with
  compatibility summary, render status counts, raw/unextracted Live2D bundle
  counts, top render failures, and promoted `compatibility_risk` stress
  summaries for high-risk rig/atlas/mesh/motion samples. Use
  `--render-top-risks --top-risk-limit N` to render the riskiest passing
  compatibility rows even when they are not in the normal render limit.
  Use `--animation-sweep --sweep-samples N` to sample multiple animation times
  per rendered actor and record blank-frame and bbox motion diagnostics.
  Use `--golden-dir path` to compare first nonblank render images against
  golden baselines, `--update-golden` to create or refresh those baselines, and
  `--known-failures qa_corpus/actor_known_failures.json` to quarantine expected
  compatibility/render failures without hiding them from the report.
  Use `--no-render` for dependency-only runs,
  or `--no-spine-render` / `--no-live2d-render` to isolate one actor family.
  `--baseline previous_actor_render_qa.json` compares the current run with a
  saved report and adds `baseline_comparison` with regressions, improvements,
  missing current models, and newly discovered models; any newly broken
  previously-passing compatibility/render row makes the combined report fail.
- Operational Live2D/Spine corpus regression QA is manifest-driven:
  `tools/actor_corpus_regression.py --manifest qa_corpus/actor_corpus_manifest.json`.
  It wraps compatibility, top-risk rendering, animation sweep, golden-image
  comparison, baseline comparison, and known-failure quarantine into one
  repeatable command. It writes both a full report and compact
  `debugCapture/actor_corpus_status.json`, which Health/professional readiness
  can surface without loading every raw model row. The GitHub workflow
  `.github/workflows/actor-corpus-qa.yml` runs the safe no-render preflight
  weekly and on manual dispatch; full render/golden runs are intended for the
  local workstation with GPU/Live2D runtime available.
  `qa_corpus/actor_corpus_manifest.json` also supports `optional_roots`; any
  existing external roots are added to the scan so real model folders can be
  kept outside the repo. Use `tools/run_actor_full_qa.ps1` for a local full
  render/golden run, and `tools/actor_golden_manager.py` to inspect golden
  baseline coverage or promote `_actual` renders into accepted baselines.
  The compact status artifact now includes per-model rows; Media Pool actor
  items read it through `app.actor_qa_status` and stamp `QA`, `RISK`, `Q`, or
  `FAIL` badges on actor thumbnails/tooltips. The Media Pool metadata panel
  expands the same status into readable per-model pass/fail, stress/risk,
  render status, golden baseline state, broken dependency, missing atlas/MOC/
  motion, known-failure, and recommendation lines. `ActorQABrowserDialog`
  provides the same per-model status as a full browser from the Actors menu and
  Command Palette, and shows baseline-vs-actual image previews when the report
  row references golden/render artifacts.
- Live2D and Spine editor loading is user-visible and cancellable. Timeline
  double-click opens the editor first, suppresses sample autoload for linked
  clips, and defers the heavy native/model load until the window is visible.
  Both editors show an indeterminate progress bar, cancel button, timeout
  handling, load-step log, retry/open-location/sample recovery buttons, and
  keep the progress state active until the first rendered frame is actually
  visible. Actor timeline clips show transient `LOAD`/`OK`/`ERR`/`TIME`/`STOP`
  badges through `app.actor_loading_status`.
  Live2D additionally mirrors progress in a large viewport loading panel, so
  the expensive first native/GL initialization does not look like a frozen
  window while the bottom control bar is out of focus.
- Live2D actor assignment is automatic: selecting/loading a model writes the
  model path to the linked timeline clip, the auto-selected idle motion writes
  its motion group/index, and closing the editor applies the current model and
  motion once more. The old explicit Apply flow is no longer the primary UX.
  Opening or adjusting a Live2D/Spine actor clip focuses the main preview
  playhead inside that clip when necessary, so position/scale edits are visible
  without manually scrubbing to the actor range.
- Spine software fallback rendering clips only the visible portion of oversized
  or partly off-frame textures/triangles before compositing. This keeps scaled
  NIKKE-style background plates and large meshes visible in preview/export
  instead of dropping the whole attachment when it crosses a frame boundary.
- Spine GL editor and preview render passes explicitly clear stale scissor
  state before drawing actors, so Qt/update-region state cannot crop actors to
  an old repaint rectangle. The Spine editor defaults to a work view that keeps
  the actual final-frame placement but zooms the editor camera out when needed;
  a final-frame toggle shows the exact output crop when users need delivery
  framing.
  2026-07-14 placement note: the Spine editor final/canvas transform treats
  renderer offsets as frame-center-relative values and converts them to the
  viewport widget origin before applying the work-view camera. This keeps
  zoomed Spine actors centered in the final frame instead of cropping them to
  the upper-left half of the viewer.
- Missing media/model paths can be relinked without opening the UI:
  `tools/relink_project_media.py project.tgp <search-root...>` writes a
  `.relinked.tgp` copy by matching filenames under the supplied roots.
  `tools/relink_project_media.py --health project.tgp <search-root...>` is a
  non-writing long-project preflight that reports missing rows, multi-root
  relink conflicts, repeated references, duplicate filename collisions, and
  sibling proxy state for video sources.
  The main editor `Health` toolbar action runs the same media/proxy audit on
  the current in-memory session without forcing a save. It shows a read-only
  table of status, file, proxy state, reference count, candidate count, path,
  and a detail pane with recommended action; rows with missing/relink-conflict
  status can jump directly to the Relink browser. The Health dialog also
  attaches `professional_readiness` for the current in-memory session, showing
  readiness score, high/medium issue counts, section scores, and top actions
  for long-project stability, GPU preview/export consistency, timeline edit
  integrity, color workflow depth, audio mix readiness, and preset/template
  ecosystem readiness. It also attaches an advisory
  `resolve_post_pipeline_parity` matrix that compares TigerCapture against
  Resolve/Fairlight/Fusion-class post production depth without failing ordinary
  export readiness. That matrix groups Color, Audio/Fairlight, VFX/Fusion,
  Performance, Post Pipeline, and Hardware ecosystem features, marking each as
  `supported`, `partial`, or `missing`. Tracked features include 32-bit/YRGB
  wide-gamut processing, HDR wheels and ST.2084/HLG tone mapping, HDR10+/
  Dolby Vision metadata, ACES/OCIO, RAW controls, Log/HDR wheels, advanced
  curves/warper, serial/parallel/layer/shared node grading, secondary grading,
  beauty/object repair, restoration FX, gallery/shot-match/scopes, Fairlight
  DAW scale, FlexBus routing, realtime EQ/dynamics, sample-accurate editing,
  ADR, elastic retime, take layers, Foley/SFX libraries, broadcast loudness,
  immersive audio, voice/music AI, plugin hosting, Fusion 2D/3D compositing,
  FBX/Alembic import, trackers, keying/roto, paint/repair/particles, spline/
  expression/macro workflows, GPU/native FX parity, local-ML/neural features,
  10-bit/120fps/4K+ delivery, proxy/render cache, remote rendering,
  professional ingest/A-V sync/metadata/multicam/collaboration/deliver flows,
  and DeckLink/color-panel/Fairlight-console hardware. Media Health expands
  this advisory into category scores, supported/partial/missing counts,
  supported highlights, and a ranked `implementation_backlog`/`top_actions`
  list so the next Color, Audio, VFX, performance, post-pipeline, and hardware
  work can be pulled directly from the product report. The advisory also emits
  `professional_depth_cards` for `resolve_color_depth`,
  `fairlight_audio_depth`, and `fusion_vfx_depth`; each card records the
  current maturity level, why the app is not yet at 100% parity, TigerCapture's
  product-fit strategy, implementation phases, daily-use checks, blocking
  counts, and QA gates for Color corpus, audio delivery, and compositor graph
  validation. The daily-use checks map directly to feature IDs such as
  float/ACES color, RAW/HDR delivery, node-secondary grading, realtime mixer
  routing, ADR, Fusion graph cache, tracking/roto/keying, and paint/particle/
  macro work. This keeps the comparison
  honest: RAW/HDR/ACES, Fairlight DAW scale, and Fusion 2D/3D compositing are
  tracked as productized/validated stages rather than implied complete support.
  Health detail text and the QA Dashboard now surface those depth cards beside
  the numeric parity score, so users can see the practical next Color/Fairlight/
  Fusion action without opening raw JSON. Color workflow helpers also provide a
  deterministic synthetic color-bar/luma-ramp sample and `scope_accuracy_report()`
  for basic waveform/parade/vectorscope QA gates. Audio workflow helpers expose
  `audio_delivery_qa_gate()` to combine loudness target checks with Fairlight-
  style bus/send validation. VFX/post-pipeline helpers expose a small
  `VFXNodeGraph`/`VFXNodeSpec` model plus `build_mini_vfx_node_graph()` so
  keyer, B-spline roto, clean plate, planar tracking, merge, title, and output
  nodes can share one preview/export-locked payload before a full Fusion-style
  compositor UI exists. The Color Page caches and exposes the scope accuracy QA
  gate in the scopes status tooltip, the Audio Mixer `Loudness` report now
  includes routing/bus validation alongside LUFS/true-peak checks, and Mask
  Editor stores both `vfx_repair_plan` and `vfx_node_graph` payloads so repair
  masks can be inspected as a small compositor graph instead of an opaque mask.
  Professional Readiness now embeds the Color scope QA report inside
  `color_workflow_depth`, Health detail text surfaces that report, and export/
  Render Queue preflight diagnostics append an `Audio Delivery QA` line covering
  loudness target, true peak, route count, and bus validation. Mask Editor also
  includes a `VFX Graph` inspector button that displays the mini compositor JSON
  before committing the mask. The in-memory Health serializer collects
  `vfx_repair_plan` and `vfx_node_graph` payloads from active clips and
  Workbench node chains, so masks authored in the editor are counted by
  Professional Readiness and export diagnostics without requiring a save/reload
  cycle. `vfx_node_graph_qa_report()` validates those mini compositor graphs for
  missing output nodes, unresolved input links, node counts, kind counts, and
  required media/output coverage. Health detail text, QA Dashboard project rows,
  and export diagnostics now include compact `Color Scope QA` and `VFX Graph QA`
  lines beside the readiness score. `app.workbench_panel.WorkbenchPanel`
  exposes `vfx_node_graph_qa_payload()` and `vfx_node_graph_summary_text()` so
  the FX tab can display mini VFX graph status directly from selected
  `track.node_item_chain` payloads. The same panel also uses
  `vfx_node_graph_overview_for_track()` to draw a compact read-only VFX strip
  with Media/Keyer/Roto/Clean/Track/Merge/Out pills below the FX summary, so a
  mask/repair graph is visible before opening deeper diagnostics. Tracks with a
  VFX payload also reveal an `Inspect VFX` action backed by
  `vfx_node_graph_detail_text_for_track()`, which opens QA gates, warnings,
  output/cache policy, and node input/parameter details from the Workbench.
  Mini graph pills are implemented as clickable buttons and derive review
  state from graph validation warnings if the payload did not persist warning
  text.
  `app.render_queue_panel` parses persisted
  preflight diagnostics with `render_preflight_cards_from_text()` and shows
  clickable readiness/Color/Audio/VFX/export-parity cards above the selected
  job log. Each card uses `render_preflight_card_detail_text()` for a focused
  detail dialog with copy support, so users can inspect one failing gate without
  scanning the full render log. `render_preflight_card_action_specs()` maps
  those cards to contextual resolution routes: Health/Health Center,
  QA Dashboard, Color Page, Audio Mixer, Preset QA, or Deliver Presets.
  Health Center also shows
  Professional Readiness as a dedicated row when opened from an editor session,
  so users do not need to dig through the media table to see long-project and
  Resolve/Fairlight/Fusion parity status. Timeline readiness
  also tracks professional Color/Audio parity signals: project LUT/HDR/OCIO
  intent, grade-local LUTs, qualifier cleanup, tracked power windows, audio
  effect graphs, clip/track automation, bus routing, and loudness/dialogue
  readiness are counted so Health, export preflight, and real-project QA report
  the same delivery risks.
  The first implementation tranche for this parity matrix is Qt-free and lives
  in workflow helpers rather than modal UI: `app.color_workflow` adds
  `AdvancedColorToolset`, `HDRZoneControl`, `LogWheelSet`, `HueCurveSet`,
  `ColorWarperPoint`, and frame helpers for HDR zone tone, log-wheel offsets,
  Hue vs Hue/Sat/Luma, and color-warper transforms, plus
  `advanced_color_product_capabilities()`. `app.audio_workflow` adds
  `AudioRoutingMatrix`, `AudioSendSpec`, `build_default_routing_matrix()`,
  `loudness_delivery_report()`, and `fairlight_product_capabilities()` for
  Fairlight-style routing, sends, realtime mix metadata, sample-accurate
  readiness, and loudness delivery checks. `app.post_pipeline_workflow` adds
  roto spline, clean-plate, planar-tracker, proxy/render-cache, ingest clone
  checksum, and Deliver-page job matrix models, with
  `post_pipeline_product_capabilities()` feeding VFX, performance, and
  post-pipeline readiness. `professional_readiness` deep-merges these built-in
  capabilities with project-supplied `product_capabilities`, so Health/QA shows
  implemented helper coverage by default while explicit project capability
  metadata can still override or extend it. `ColorGrade` also persists an
  `advanced_color_toolset` payload and bakes the implemented HDR-zone,
  log-wheel, Hue vs Hue/Sat/Luma, and Color Warper transforms through
  `apply_to_rgb()`, which is the shared preview/export RGB path. Color presets
  can now write these payloads with `apply_color_preset_to_grade()`, and
  Professional Readiness counts advanced color payloads plus project-level
  `audio_routing_matrix`, `vfx_repair_plans`, `proxy_render_cache`,
  `deliver_jobs`, and `ingest_clone_manifest` entries so Health/QA reflects the
  actual project workflow payloads, not only hard-coded product capability
  claims. `app.professional_workflow_payloads` is the shared UI/QA bridge for
  those payloads: it can non-destructively enrich a project document with
  Fairlight-style audio routing, proxy/render-cache policy, filtered
  Deliver-page job specs, and checksum ingest manifests. The Audio Mixer panel
  exposes matching routing/loudness payload helpers and displays a compact
  routing summary so this workflow can be surfaced before a full Fairlight-style
  mixer UI lands. The Color Page exposes an `Advanced Color` control block that
  writes HDR-zone, log-wheel, Hue/Sat, and Color Warper values directly into the
  shared `advanced_color_toolset` grade payload. Render Queue exposes a Deliver
  preset matrix for web/social/UHD/roundtrip jobs. Media Pool can produce
  selected/all ingest checksum manifests and shows proxy/checksum metadata for
  selected clips. Mask Editor can export a VFX repair payload with B-spline
  roto, clean-plate bounds, per-point feather values, and planar tracker intent.
  Presets expose `preset_preview_storyboard()` metadata so cards, overlays, and
  QA can describe before/after preview cues and bake targets without requiring a
  full render. The next polish layer is also connected to the same payloads:
  Color Page shows an Advanced Color before/after split preview, Hue/Sat mini
  curve, Color Warper mini grid, bypass/solo/reset controls, and a scroll-safe
  qualifier side panel; Audio Mixer exposes routing and loudness dialogs over
  the same Fairlight-style payloads; Render Queue can summarize Deliver presets
  for QA/status surfaces; Media Pool can generate a scoped media-health report
  covering proxy missing/stale state, duplicate filenames, and relink candidates;
  and Mask Editor shows a clean-plate/planar-tracker repair summary while the
  user edits masks.
  The next Resolve/Fairlight/Fusion parity tranche adds explicit professional
  workflow sidecars, still without claiming that TigerCapture is a full
  Resolve/Fairlight/Fusion replacement. `app.color_workflow` now exposes
  `build_professional_color_pipeline_payload()` and
  `professional_color_pipeline_report()` for a 32-bit scene-linear/YRGB
  pipeline contract, non-destructive RAW controls, HDR10+/Dolby Vision
  metadata, serial/parallel/layer/shared node render order, and restoration FX
  payloads. `app.audio_workflow.fairlight_engine_report()` models a realtime
  mixer graph with latency compensation, bus/send routing, ADR cues, elastic
  retime, and SFX library metadata. `app.post_pipeline_workflow` adds
  `professional_post_pipeline_report()`, a richer 2D/3D compositor graph, and a
  professional Deliver codec matrix for ProRes, DNxHR, EXR, and DPX. The shared
  bridge `app.professional_workflow_payloads.attach_professional_workflow_payloads()`
  can attach these sidecars to a project document as `color_pipeline_payload`,
  `fairlight_engine_payload`, `professional_deliver_jobs`, and `vfx_node_graphs`;
  Professional Readiness consumes those fields before falling back to advisory
  built-in capabilities. `tools/qa_professional_pipeline_next.py` writes
  `debugCapture/professional_pipeline_next_qa.json`, and QA Dashboard exposes
  the same report as `Professional Pipeline Next` so the product can track this
  deeper pipeline work separately from ordinary export health.
  The follow-up tranche connects the remaining advisory gaps into the same
  report: the Color payload now carries an `advanced_color_toolset`,
  tracked/cleaned secondary `color_workflow`, and `beauty_repair` payload for
  face refinement, skin retouching, object removal, and patch replacement.
  `app.post_pipeline_workflow.local_ml_readiness_report()` registers local-only
  object/face/reframe/retime/upscale/auto-color feature slots; no cloud provider
  is assumed. `fairlight_mixer_stress_report()` validates a 2,000-track virtual
  routing/stress contract, while `collaboration_readiness_report()` and
  `studio_hardware_readiness_report()` add bin/timeline/clip locks, shared
  markers, conflict/handoff hooks, color-panel mappings, Fairlight/audio-I/O
  registry rows, and DeckLink-style monitoring/calibration rows. These are
  readiness contracts and payloads: they remove blind spots from Health/QA and
  define the integration surface for future UI/native-engine work, but they do
  not by themselves make TigerCapture a full Resolve/Fairlight/Fusion engine.
  `app.professional_runtime` is the next validation layer after those
  contracts. It creates a deterministic RGB frame and runs the professional
  Color payload through `apply_advanced_color_toolset()` plus a tracked
  secondary `apply_color_node_workflow()` pass, comparing preview/export hashes
  and scope data. It also verifies 32-bit scene-linear/YRGB color precision,
  HDR metadata and scope-accuracy checks, topologically orders the Fusion-style
  VFX graph, records render/cache-boundary nodes, verifies spline/expression/
  modifier/macro plus deep-pixel/volumetric graph branches, writes a synthetic
  local-ML probe image through `local_ml_analyze_media()`, and runs a
  Fairlight-style 7.1 routing sample with ADR, elastic retime, SFX library,
  latency compensation, and 2,000-track stress metadata. `tools/qa_professional_runtime_next.py` writes
  `debugCapture/professional_runtime_next_qa.json`; QA Dashboard exposes it as
  `Professional Runtime Next`, and Final Product Readiness/Productization Loop
  now treat it as the professional runtime parity gate alongside
  `Professional Pipeline Next`. This still does not replace a native Resolve/
  Fairlight/Fusion engine, but it prevents the professional feature contracts
  from staying as metadata-only promises.
  The timeline readiness section
  separates large same-lane overlaps from one-frame micro-overlaps, and reports
  micro gaps/overlaps as `auto_fixable_edge_count` so Health cleanup guidance
  does not overstate small accidental edit-edge mistakes as major overlap
  failures. It also attaches `timeline_edge_cleanup` counts so accidental one-frame same-lane
  gaps/overlaps are visible during routine project health checks. When unlocked
  tracks have auto-fixable timeline edges, Health enables `Clean Timeline
  Edges` and routes it through the same undo-safe cleanup path as the track
  context menu. The Health detail pane previews the affected track, clip-id
  pair, duration, time span, and whether each edge is auto-fixable or manual.
  After a cleanup changes the timeline, Health rebuilds the report and reopens
  with fresh media/proxy/readiness/timeline-edge diagnostics.
  The main editor also has a `Relink...` toolbar action. It opens a
  missing-media browser for the current project file, or a chosen `.tgp` when
  no project is open. Users can add multiple search roots, scan all missing
  media/model paths, choose a replacement per missing file when several
  same-name candidates exist, and see conflict/unresolved/duplicate-selection
  warnings plus stale/missing proxy warnings before writing a non-destructive
  `.relinked.tgp` copy. The repaired copy can be opened immediately before
  `load_project()` skips missing video/audio tracks.
- Batch Export is backed by `app.render_queue.RenderQueueStore`, persisted at
  `~/Videos/TigerCapture/.cache/render_queue.json`. The main editor exposes a
  right-dock `Render Queue` panel through `app.render_queue_panel`. Marker
  ranges are queued as background jobs, run sequentially while the editor stays
  usable, and remain visible as history with status, progress, output path, and
  encoder diagnostics. The panel supports pause-after-current, resume, cancel
  current/pending jobs, retry failed jobs, clear completed jobs, refresh, and
  reveal selected output folders. Export cancellation calls
  `VideoExportThread.cancel()` so active FFmpeg subprocesses are terminated and
  temporary outputs are cleaned. Render failures are normalized through
  `app.render_diagnostics`: FFmpeg tails are classified as output-lock,
  disk-space, missing-media, unsupported-media, encoder, filter-graph,
  actor-bake, memory, empty-output, canceled, or unknown failures, with
  concrete recovery actions persisted into queue diagnostics and shown in
  single-export failure dialogs. The Render Queue panel has a selected-job
  diagnostics detail pane plus a copy-diagnostics command, so users can inspect
  and share the full failure report without reading truncated table cells.
  `render_queue_product_diagnostics()` adds a product-facing summary, suggested
  next actions, and preset/template export-parity hints; the panel also exposes
  a `View Log` dialog and `Render Failure Assistant` for the selected job. Both
  log dialogs can save the full text to disk for bug reports or long-running
  render diagnosis. The
  assistant can open Relink, run preset application QA, copy diagnostics, or
  queue a short retry range from the selected failed
  runtime job, using the failed job's last progress percentage to choose a
  5-second range around the likely failure point and writing to a suffixed
  output filename. Long queue histories can be narrowed with status filters
  and text search across job names, outputs, sources, and diagnostics; old
  terminal history can be pruned while pending/running work is preserved. The
  older modal `BatchExportDialog` remains as a compatibility fallback and
  stores the same failure diagnostics.
- Editor presets are centralized in `app.preset_library`: built-ins cover
  effect, title, transition, color, audio, template, caption style, sticker,
  and motion presets. Extra JSON preset files can be listed/searched with
  `tools/list_editor_presets.py` using `--kind`, `--query`, `--tag`, or
  `--summary`. Effect presets are visible in the left dock as clickable and
  draggable cards: clicking applies the effect to the selected clip or the clip
  under the playhead on the active track, while dragging applies the same
  clip-level effect payload to the clip under the drop cursor. During that drag,
  the target clip is painted with an FX outline and preset label so the valid
  drop area is explicit; a successful drop leaves the normal FX badge/burst
  feedback on the clip. Effect-preset click/drag tooltips, drop labels, and
  no-target warnings are routed through the six-language `app.i18n` tables
  instead of hard-coded mixed-language literals. If no compatible video clip
  exists, the status line tells the user to select a clip or drag the card onto
  one. Title presets from the library extend the existing
  title-card panel through the same timeline drop path.
  Template/caption/sticker/motion presets are visible
  in the left-dock Workflow Presets panel as compact library cards; clicking a
  card applies it to the current target and dragging it to a track applies it at
  the drop time. Dropped workflow cards prioritize the drop track/time over any
  previously selected clip, and template entry `at_ms` values are treated as
  offsets from the click/drop target time. Template presets expand into ordered
  effect/title/transition/audio/color/motion/caption/sticker actions through
  `template_sequence()`. The launcher deliberately shows no recent-work or
  recommended-template cards on the first screen; broader template browsing
  stays inside the editor so startup remains simple and the Media Pool /
  Workbench identity is not hidden. Inside the editor,
  the top toolbar exposes a focused Templates browser that filters the workflow
  library to `kind="template"` while the left Workflow Presets panel still
  keeps template/caption/sticker/motion drag workflows together. When a
  template launch payload is supplied, the editor
  keeps that pending template and applies it after the first compatible media
  drop/import. Template application surfaces an A/B wallpaper-palette preview, a
  preview-toast summary of applied step counts, and timeline badges for applied
  clip state (`FX`, `Key`, `TR`, `COL`, `T`, `Mot`, `Nest`) plus audio-chain
  state (`AUD`) so users can see which presets have landed without opening
  every clip.
  User presets live under `default_save_dir()/preset_packs`: the editor can
  save the selected clip's current effect/chroma payload as a user effect
  preset, import JSON preset packs into that directory, and export all
  non-bundled user presets as a portable JSON pack. `load_editor_presets()`
  automatically loads those user packs in addition to bundled presets.
  Template Composer creates user template presets by sequencing existing
  effect/title/transition/audio/color/caption/sticker/motion presets with
  millisecond offsets, per-step duration metadata, target hints
  (`auto`, `selected_clip`, `active_track`, `audio`, `color`), and conditional
  gates (`always`, `if_video`, `if_audio`, `if_vertical`, `if_shortform`). It
  can preview the composed template overlay before saving and writes through
  the same user preset pack.
  The Effects Presets panel exposes pack management, preset QA, and one-click
  auto-plan actions. Pack management lists enabled/disabled user JSON packs,
  can enable/disable imported packs by renaming them outside the loader glob,
  can delete non-primary packs, and can repair damaged packs after writing a
  timestamped backup. `inspect_preset_pack()` reports invalid rows, duplicate
  ids, built-in id conflicts, cross-pack conflicts, and missing template child
  references; `repair_user_preset_pack()` normalizes rows and removes broken
  template references. `preset_pack_marketplace_report()` summarizes installed
  user packs as a library/marketplace dashboard with enabled/disabled counts,
  issue-pack counts, kind/tag coverage, per-pack score/coverage labels,
  per-pack recommendations, and next actions for the Pack Manager UI. Health
  also embeds this marketplace summary as `preset_pack_marketplace`, so preset
  pack issues are visible beside media/proxy/readiness issues. Preset QA opens the ecosystem report in an
  in-editor dialog. The auto-plan action builds a project summary from media names,
  media counts, file types, probed video orientation, audio/video presence, and
  timeline/media duration, runs `one_click_preset_plan()`, and applies
  compatible presets to the active target.
  `search_presets()`, `preset_library_summary()`, and
  `preset_ecosystem_report()` provide library diagnostics, kind-count targets,
  topic coverage, one-click plan coverage, template child-preset reference
  checks, and normalized tag/name/description search, so punctuation differences
  such as `b-roll` versus `b roll` still match. The ecosystem report is also
  attached to `professional_readiness` as `preset_template_ecosystem`, allowing
  Health, export preflight, and real-project QA to flag weak or broken preset
  packs before users rely on one-click templates. The expanded built-ins include utility
  cleanup, UI capture, esports/gameplay, music-video, blue/green-screen,
  chapter, speaker, score-callout, Live2D nameplate, dialogue cleanup,
  loudness, color qualifier/window, one-click short-form templates, caption
  styles, stickers, and motion presets. A larger social/creator pack adds
  vertical short-form hooks, tutorial step packs, product-demo polish,
  streamer/reaction templates, creator voice chains, CTA/callout stickers, and
  product/social color starters. A production template pack adds news brief,
  hotkey tutorial, ranking/listicle, anime/actor reaction, food/product gloss,
  documentary clarity, noisy-room dialogue, keycap/ranking stickers, and
  editorial caption styles. A content expansion pack adds B-roll/cutaway,
  podcast chapter, product-review verdict, and patch-note update templates,
  with matching titles, transitions, effects, captions, stickers, motion, and
  audio chains wired into `one_click_preset_plan()`. A Screen Studio/CapCut
  style pack adds cursor-pop transitions, wallpaper-palette hooks, glass
  callouts, compact caption styles, cursor stickers, UI tutorial motion, and
  one-click short-form/product templates. A micro-interaction pack adds cursor
  spotlight wipes, glass panel pushes, hotkey chips, click rings, UI-focus
  motion, and hotkey/cursor templates. A Screen Studio template pack adds
  cursor tutorial chapters, clean product launch, shorts hook/caption burst,
  gaming highlight, and corporate demo sequences wired into
  `one_click_preset_plan()`. A Screen Studio delivery template pack adds
  `template-screenstudio-record-edit-export`,
  `template-screenstudio-click-to-cut`,
  `template-screenstudio-wallpaper-demo`,
  `template-screenstudio-product-walkthrough`, and
  `template-screenstudio-short-export`, composed from existing effect/title/
  sticker/motion/caption/color/transition presets so they work through the
  same preview, drag/drop, one-click planning, and template-reference QA paths.
  `CREATOR_EFFECT_TRANSITION_EXPANSION_PRESETS` adds 10 extra effect presets
  and 10 extra transition presets focused on everyday editing gaps: readable
  screen text, cursor focus, webcam cleanup, product UI polish, light glitch,
  anime/Live2D/Spine overlays, dark gameplay recovery, document capture,
  social pop, low-light denoise, click flashes, panel slides, soft zooms,
  clean wipes, chapter fades, and beat cuts. These presets only use supported
  `video_filters` and `transition_out_*` payloads, so they remain compatible
  with click apply, drag/drop, transition payload generation, preview overlays,
  export pre-render, search, summary counts, and preset ecosystem QA.
  Actor workflow presets now
  include `actor-live2d-placeholder`, `actor-spine-placeholder`,
  `template-live2d-actor-spotlight`, and `template-spine-actor-action`; these
  create Live2D/Spine actor placeholders through the workflow preset path and
  are included in preset ecosystem QA and one-click planning.
- `Ctrl+Shift+P` and the top-bar search icon open the Command Palette. It
  searches imported media, editor presets, and preset commands in one dialog.
  Activating media filters the Media Pool to that item; activating a preset
  applies it through the same editor-preset workflow path; command rows open
  preset QA, pack management, cache management, Template Composer, Visual QA
  viewer, import/export, or one-click auto-plan. The palette persists its own
  favorite and recent rows separately from the preset browser state. The
  selected row detail panel shows command descriptions, media paths, or preset
  target diagnostics via `_preset_apply_failure_reason()`, so incompatible
  presets explain whether they need a video clip, audio clip, color grade, or
  matching template condition before the user activates them. Preset rows also
  expose `Preview Apply` and `Fix Target`: preview opens
  `_open_preset_application_preview()`, which renders a looping A/B
  current-frame mini playback for the selected preset plus each
  template/application step as
  apply/blocked/skipped; fix calls `_run_preset_fix_action()` to select the
  first compatible video clip, add obvious missing video/audio lanes, prepare a
  color target, or create Live2D/Spine actor tracks when that is safe. Command
  Palette search uses natural-language alias groups and match scoring so exact
  topic matches rank above weaker substring hits.
- Actor workflow presets use the Media Pool as a model resolver. If a compatible
  `.model3.json` Live2D model or Spine `.json`/`.skel`/`.atlas` candidate is
  already imported, the preset creates the actor clip with that model path;
  otherwise it falls back to a placeholder clip that can be edited later.
- Preset Pack Manager presents each pack as a small marketplace card with score,
  coverage, tags, and issue state. `Inspect` shows duplicate ids, built-in id
  conflicts, cross-pack conflicts, and missing child presets; `Resolve Issues`
  repairs invalid rows, duplicate rows, and broken template child references,
  while surfacing id conflicts as manual rename/disable decisions.
- Timeline drop guides are duration-aware. Dragging media, titles, effects,
  speed/zoom/fade actors, or editor templates paints a translucent rounded
  block estimating the insertion span instead of only a vertical line. Template
  and workflow drags also paint small colored internal segments for their
  ordered child actions plus a small duration/type summary pill, making
  multi-step drops readable before release.
- The in-editor Visual QA viewer browses `debugCapture` layout/visual
  regression report folders, shows the captured PNG preview, and displays the
  compact report payload. `Approve Baseline` can promote the selected/current
  capture into the product baseline. The current productized baseline path is
  `debugCapture/visual_baseline/baseline.json`, with approved PNGs archived in
  `debugCapture/visual_baseline/approved/` and a `baseline_manifest.json` with
  approval time and source path, giving the UI a controlled baseline update
  path without hiding the CLI QA files.
- The in-editor QA Dashboard (`app.qa_dashboard.QADashboardDialog`) summarizes
  recent product QA reports: preset application/corpus parity, Color/Audio
  accuracy, timeline fuzzer results, timeline pixel-alignment QA,
  screenshot-based timeline visual-alignment QA, long-project stress QA,
  Live2D/Spine actor-lane workflow QA, Node Graph scene/widget fuzzer QA,
  actor corpus status, actor mass-compat smoke QA, actor render QA, latest
  visual regression/baseline audit reports, micro-interaction QA, and the
  latest crash report. It shows available/missing report state, pass/fail
  summary, update time, detail lines, and opens the selected report folder.
  Safe reports can be run from the dashboard: fixture generation,
  preset application QA, Color/Audio accuracy, long-project stress, timeline
  fuzzer, timeline alignment, timeline visual alignment, actor-lane workflow
  with real samples, Node Graph scene/widget fuzzers, visual regression,
  visual-baseline audit, micro-interactions, actor mass-compat smoke, and
  dependency-only actor corpus status when the manifest is present. `Run Fast
  QA` executes the safe command set, `qa_dashboard_history.json` stores recent
  pass/fail trend points, and visual baselines can be approved through
  `tools/qa_visual_baseline_manager.py`. The dashboard also paints a compact
  pass/fail/missing trend strip and shows thumbnails for visual-regression
  rows, so QA state is readable without opening each JSON file.
  The dashboard also includes "Product Polish Next", backed by
  `tools/qa_product_polish_next.py` and `app.product_polish`. That report is
  the current 10-item next-work gate: preset timeline visibility,
  preset/template result previews, Screen Studio real-corpus zoom/cursor
  readiness, CapCut caption/shorts quality, timeline feel feedback, Media Pool
  discoverability, export parity expansion, crash recovery productization, UI
  visual consistency, and QA Dashboard productization. It separates
  implementation readiness from real-world sample readiness; a passing local
  report can still show that the Screen Studio real recording corpus needs
  20-50 actual recordings.
- A consolidated productization loop is available through
  `tools/qa_productization_loop.py`, QA Dashboard, and Command Palette. It
  summarizes fifteen commercial-polish areas: UI visual QA, commercial
  expansion, CapCut creator workflow, preset preview realism, preset pack
  management, QA Dashboard coverage, Render Queue UX, Media Pool long-project
  state, Color/Audio accuracy, Screen Studio parity gap, Live2D/Spine actor
  compatibility/loading/overnight QA, crash recovery/project repair, and
  starter templates. With
  `--run-fast-qa` it now bootstraps the QA corpus, runs real-sample
  Color/Audio checks, Screen Studio parity-gap QA, long-project stress,
  micro-interactions, actor
  mass-compat, visual regression/baseline audit, timeline fuzz/alignment, actor
  lane workflow, Node Graph fuzzers, and preset application QA. The latest
  local productization run is expected to report score 100/100 when the
  generated corpus and approved visual baseline are present.
- Main-editor layout QA is scriptable. Use `tools/qa_ui_layout.py` for
  1366x768, 1920x1080, and full-wide captures; use `--onscreen` when doing a
  real-monitor pass.
- Preset/template application QA is scriptable through
  `tools/qa_preset_application_corpus.py`. It summarizes real `.tgp`/JSON
  project files, derives media/topic flags, runs `one_click_preset_plan()`,
  includes `preset_ecosystem_report()` and `preset_pack_marketplace_report()`,
  checks preview/export baking parity for every planned preset kind, and writes
  an optional JSON report so real project corpora can catch weak one-click
  template routing. With no explicit project arguments the script can
  auto-discover up to five project-like files from
  `qa_corpus/preset_application_samples`, `qa_corpus`, or supplied
  `--discover-root` directories via `discover_project_files()`. Health exposes
  direct buttons for Preset Pack Manager, preset ecosystem QA, and preset
  application corpus QA; the in-app corpus run writes
  `debugCapture/preset_application_corpus_ui.json`. Product QA sample planning
  is tracked in `qa_corpus/product_qa_corpus_manifest.json`, grouping
  screen-recording UI demos, short-form templates, tracking masks, actor
  models, long-project stability, and Color/Audio accuracy corpora.
- The persistent local QA corpus is generated by `tools/build_qa_corpus.py`.
  It now writes six `.tgp` fixtures: timeline/audio basics, masks/filters/
  tracking, nested multitrack, Live2D/Spine actors, audio-heavy mixed layout,
  and `06_long_project_stress.tgp`. The generator also writes a readable
  `.tigercapture_recovery/01_timeline_audio_basic~autosave.tgp` recovery
  candidate and default `qa_corpus/color_audio_samples` media for real
  Color/Audio diagnostics.
- Long-project/recovery smoke QA is scriptable through
  `tools/qa_long_project_stress.py`. It verifies at least 5 minutes of project
  duration, 100+ video clips, 120+ audio clips, nested sequence coverage, proxy
  state, no missing media/model paths, and an `open_safe` recovery candidate.
- UI micro-interaction QA is scriptable through
  `tools/qa_micro_interactions.py`. It verifies required code-native icons,
  wallpaper-palette card rollover labels, the timeline burst painter, blade
  tool entry points, and global hover/pressed styling.
- Visual regression uses `tools/qa_visual_regression.py`; approved captures are
  stored by `tools/qa_visual_baseline_manager.py`, and baseline coverage is
  audited by `tools/qa_visual_baseline_audit.py`. Screenshot hashes are still
  recorded, but tiny offscreen-render pixel jitter can be tolerated through
  image diff thresholds so real layout changes remain blocking while harmless
  capture noise does not.
- Live2D/Spine mass-compat smoke QA is scriptable through
  `tools/qa_actor_mass_compat.py`. It checks that actor corpus status exists,
  coverage targets are met, stress-tier models are represented, known-failure
  quarantine is present, and actor golden baselines remain seeded.
- Timeline interaction stress QA is scriptable through
  `tools/qa_timeline_fuzzer.py`. It randomly exercises select-era edit model
  operations such as blade, linked clip move, ripple/roll, slip/slide, nested
  clip markers, actor lanes, and undo snapshots, then writes
  `debugCapture/timeline_fuzzer_qa.json` for the QA Dashboard.
- Timeline row pixel alignment is scriptable through
  `tools/qa_timeline_alignment.py`. It verifies that TimelineRuler, video
  TrackRow, Live2DActorLaneRow, and SpineActorLaneRow share the same 10 px
  timing origin and writes `debugCapture/timeline_alignment_qa.json`.
- Live2D/Spine actor-lane interaction QA is scriptable through
  `tools/qa_actor_lane_workflow.py`. It creates empty actor clips, sends real
  Qt double-click events, verifies the emitted clip signal and hit-test result,
  and writes `debugCapture/actor_lane_workflow_qa.json`. Pass
  `--include-samples` to also load the first installed Live2D `.model3.json`
  and Spine sample skeleton, validating real asset assignment without running
  the slower render corpus.
- Node Graph interaction fuzzing is scriptable through
  `tools/qa_node_graph_fuzzer.py`. It exercises QGraphicsScene add/connect/
  reject/delete/move/save/load operations and writes
  `debugCapture/node_graph_fuzzer_qa.json`.
- Timeline visual alignment QA is scriptable through
  `tools/qa_timeline_visual_alignment.py`. It captures
  `debugCapture/timeline_visual_alignment_qa/timeline_visual_alignment.png`
  and verifies ruler/video/Live2D/Spine playhead x positions in the generated
  report.
- Timeline drag feedback QA is scriptable through
  `tools/qa_timeline_drag_feedback.py`. It drives real Qt mouse press/move
  gestures against `TrackRow`, captures snap and blocked drag-in-progress
  screenshots, verifies feedback text plus snap/blocked color pixels, writes
  `debugCapture/timeline_drag_feedback_qa/timeline_drag_feedback_report.json`,
  and is exposed in QA Dashboard as `Timeline Drag Feedback`.
- Timeline edit-mode mouse QA is scriptable through
  `tools/qa_timeline_edit_gestures.py`. It drives real `TrackRow`
  press/move/release gestures for trim, ripple, roll, slip, and slide; verifies
  exactly one `drag_committed` pulse per gesture; checks the final clip/source
  timing changes; captures per-mode screenshots; writes
  `debugCapture/timeline_edit_gestures_qa/timeline_edit_gestures_report.json`;
  and is exposed in QA Dashboard as `Timeline Edit Gestures`.
- Timeline hover-affordance QA is scriptable through
  `tools/qa_timeline_hover_affordance.py`. It drives real `TrackRow`
  mouse-move events over clip body, gap edge trim, shared-edge roll, slip, and
  slide targets; verifies hover chip text, native tooltip synchronization after
  repeated hover moves, cursor shape, and screenshots; writes
  `debugCapture/timeline_hover_affordance_qa/timeline_hover_affordance_report.json`;
  and is exposed in QA Dashboard as `Timeline Hover Affordance`.
- Timeline preset-visibility QA is scriptable through
  `tools/qa_timeline_preset_visibility.py`. It verifies that applied clip FX,
  keying, transitions, color grades, and title overlaps produce timeline-visible
  strip entries on wide clips and compact color markers on short clips, captures
  `debugCapture/timeline_preset_visibility_qa/timeline_preset_visibility.png`,
  writes `debugCapture/timeline_preset_visibility_qa/timeline_preset_visibility_report.json`,
  is exposed in QA Dashboard as `Timeline Preset Visibility`, and runs as part
  of the productization loop alongside drag-feedback/edit-gesture/hover QA.
- Node Graph widget fuzzing is scriptable through
  `tools/qa_node_graph_ui_fuzzer.py`. It drives `NodeGraphWidget` add/select/
  bypass/delete/fit/save-reload/set-track flows and writes
  `debugCapture/node_graph_ui_fuzzer_qa.json`.
- Crash breadcrumbs are captured by `app/crash_reporter.py`. `main.py` installs
  it at startup; it appends recent actions to the per-user runtime log folder
  (`runtime_log_dir()/recent_actions.jsonl`), writes
  `runtime_log_dir()/crash_report_latest.json` for unhandled Python exceptions,
  and can call the editor's emergency autosave hook before the report is
  written. Runtime logs intentionally stay outside the source checkout to avoid
  editor/Git watchers spawning status helpers during normal app use.
  `app.crash_report_dialog.CrashReportDialog` opens the latest report in-app,
  can open the emergency autosave, copy details, open the log folder, and export
  a repro bundle through `export_repro_bundle()`.
  `crash_report_user_summary()` translates exception, autosave, actor context,
  and recent action counts into a friendly headline plus recommended actions
  before the raw traceback is shown. The video editor startup path
  shows this crash dialog for unseen crash reports before the normal
  last-project resume prompt.
- `app.health_center_dialog.HealthCenterDialog` is the product-facing
  diagnostic hub. It summarizes crash status, QA failures, render queue
  failures/cancellations, current project media/proxy issues, and actor QA
  risk rows with direct buttons back into QA Dashboard and Crash Report.
- Localization QA is strict-clean across `en`, `ko`, `ja`, `zh`, `fr`, and
  `de`: all locale tables carry the reference keys and pass placeholder and
  mojibake checks via `tools/qa_localization_audit.py --strict`.
  The video editor language switcher depends on the same tables and has direct
  regression coverage for its language-changed and export-tooltip keys.
- Native worker calls now support JSON-lines progress events, file contracts,
  and cancel-token errors through `NativeWorkerClient.request_with_events()`.
- Preview chroma key now moves the heavy hue-distance/key-mask/soft-alpha work
  into OpenCV native C++ operations with cached LUTs in `app/chroma_key.py`.
  Spill/background compositing uses alpha==0/255 fast paths and only blends
  soft-edge pixels, so green-screen frames avoid full-frame float32 blending.
- Clip video filters avoid avoidable full-frame float work where possible:
  sharpen uses OpenCV saturation directly, chromatic aberration reuses channel
  buffers instead of stacking a new RGB frame, and vignette uses a cached
  uint16 multiplier mask.
- Preview-only video filters use a downsampled fast path by default
  (`TIGERCAPTURE_FILTER_PREVIEW_SCALE`, default `0.375`). Final export still
  uses full-resolution `VideoFilterParams.apply()`.
- Preview decoding is wrapped in a small LRU `FrameCacheDecoder` after prefetch
  so repeated scrubs to the same frame return from memory instead of touching
  the codec. `PrefetchDecoder` keeps indexed frames in its ahead buffer, so a
  near-future seek can reuse already-decoded frames instead of discarding the
  buffer and seeking the codec again. Disable the outer LRU with
  `TIGERCAPTURE_DISABLE_FRAME_CACHE=1`.
- Spine preview rendering now defaults to the GL/native renderer path with
  prewarm, cached layout/bounds calculations, a larger animated-frame cache,
  ProjectPlayer-level overlay cache, and 24fps preview-time quantization via
  `TIGERCAPTURE_SPINE_PREVIEW_FPS`. Set that env var to `0` to disable
  quantization. Set
  `TIGERCAPTURE_SPINE_PREVIEW_RENDERER=software` or `cpu` only for debugging.
- High-resolution proxy management is visible in the editor toolbar. `Proxy`
  toggles fresh 540p proxy playback, `Proxy...` can generate/refresh/delete the
  selected source proxy, and the status pill reports Original/Building/Ready/
  Stale/Active. Media Pool thumbnails also show `P` / `STALE` proxy badges.
  `Health` audits all current media/model references and highlights missing
  files, relink conflicts, duplicate names, and missing/stale proxies before
  the user discovers the problem during preview or export.

## App Shell, Capture, and Media Intake

Core files:

- `app/main_window.py`: title/main window, editor launcher buttons, drag/drop
  entry points.
- `app/controller.py`: connects main window actions to capture, video editor,
  standalone Sound Editor, and recent-project flows.
- `app/capture.py`: screenshot/GIF/MP4 capture implementation.
- `app/region_selector.py`: screen-region selection UI.
- `app/recent_captures.py`: recent capture file tracking.
- `app/media_pool.py`: media pool grid/list, drag source, file import, and
  optional YouTube URL import UI.
- `app/youtube_import.py`: optional `yt-dlp` based YouTube-to-MP4 downloader
  used by Media Pool when the dependency is installed.
- `app/new_project_dialog.py`: project aspect ratio, resolution, FPS setup.

Behavior notes:

- Screen capture supports screenshot, GIF, and MP4.
- Windows Graphics Capture is used for GPU-composited windows where possible.
- MP4 capture streams through FFmpeg.
- Media files can enter through the media pool, drag/drop, editor context
  menus, or standalone Sound Editor launch.
- Still images are first-class media-pool inputs. PNG, JPG/JPEG, JFIF, WebP,
  and BMP files use shared helpers in `app/image_media.py`; Media Pool shows an
  `IMG` badge, grid/list thumbnails come from the image itself, and timeline
  thumbnail extraction short-circuits to still-frame thumbnails instead of
  launching a video extractor.
- Dropping or importing an image creates an image-marked visual timeline lane:
  the underlying data stays on `VideoTrack` / `VideoClip` so color grading,
  blur, node effects, typography, project save/load, preview, and export reuse
  the normal visual pipeline, while `track_type="image"` and
  `program_output=True` distinguish it from ordinary video. New image clips
  default to `DEFAULT_IMAGE_DURATION_MS` from `app/image_media.py` unless an
  explicit duration is supplied.
- Media Pool can import a single YouTube URL as MP4 when `yt-dlp` is available:
  the header/context-menu command asks for a URL, validates it is a YouTube
  host, downloads into `YouTube Imports`, shows progress, and automatically
  registers/selects the resulting MP4. This is a user-rights workflow: the UI
  warns that only owned or permitted videos should be imported. If `yt-dlp` is
  not importable from the running app Python, the importer also probes
  `yt-dlp.exe`, the project `.venv` executable, and `.venv`'s `python -m yt_dlp`
  before showing the install hint, so launcher/editor interpreter mismatches do
  not falsely disable the feature. The import flow also lets the user choose
  Auto, 8K/4320p, 4K/2160p, 1440p, 1080p, 720p, 480p, or 360p; fixed choices are
  treated as maximum-height caps so `yt-dlp` still picks the best available
  format at or below that quality.
- `app/controller.py::_open_sound_editor()` creates an unparented
  `AudioClip`; timeline-bound sound editing is opened from
  `VideoEditorWindow._open_sound_editor()`.

## Timeline and Editor Data Model

Core files:

- `app/video_editor_window.py`: main UI, rows, dialogs, timeline commands, and
  some legacy timeline dataclasses.
- `app/timeline_model.py`: modern `VideoClip`, `VideoTrack`, speed/zoom helper
  model, drag constraints, legacy view builder.
- `app/history.py`: undo/redo snapshot helpers for video/audio/subtitle state.

Video timeline:

- `VideoTrack` owns clip lists, cuts, fades, speed segments, zoom actors, PIP,
  typography actors, node graph, and color state.
- Newer clip-level behavior should prefer `timeline_model.VideoClip` /
  `timeline_model.VideoTrack` where possible, but the editor still has legacy
  compatibility fields in `app/video_editor_window.py`.
- `TrackRow` paints and edits timeline clips, trims, cuts, fades, speed, zoom,
  typography markers, context menus, and drag/drop behavior.
- Image tracks are visual timeline tracks with an `I` lane label and image
  palette. They are intentionally backed by video-track data objects for
  compatibility with selection, effects, color grading, node graphs, preview,
  and export; UI code should test `app.timeline_track_colors.is_image_track()`
  or the `track_type="image"` marker instead of inventing a parallel image
  timeline model.
- Timeline selection supports additive/toggle selection with Shift or Ctrl.
  Dragging a selected clip moves the same-row selected clip group together,
  snaps group edges to project start/playhead/markers/other clip edges, and
  rejects overlaps with clips outside the group.
- Timeline tool modes are explicit UI state: Select, Blade, Ripple, Roll, Slip,
  and Slide. `B` switches to Blade tool, `V` to Select, `R/N/Y/U` to
  Ripple/Roll/Slip/Slide. `C`, `Ctrl+K`, and `Ctrl+\` still blade at the
  playhead. `Esc` is a context reset for timeline editing: when a non-Select
  tool is active it returns to Select first, and when already in Select it
  clears the current clip selection without clearing time-range selections or
  global markers. `Ctrl+A` selects all video timeline clips in track order,
  leaving linked-audio behavior to the existing linked clip move/nudge
  preflight. `Ctrl+D` duplicates selected video clips after their selected
  group, preserves intra-selection spacing, skips over occupied clip windows on
  the same lane, selects the new duplicates, and clears copied
  `linked_audio_id` / compound-group metadata so duplicated clips do not
  accidentally share links with the originals. Locked tracks block duplication.
  `Ctrl+C` stores selected video timeline clips in an internal timeline
  clipboard; `Ctrl+V` pastes them at the current playhead, preserves
  cross-track relative offsets, shifts the whole paste group later when any
  target lane would collide, selects the pasted clips, clears copied
  linked-audio/compound metadata, and blocks locked target tracks. `Ctrl+X`
  copies the current video clip selection to the same internal clipboard and
  then ripple-deletes the originals; locked selected tracks block the cut
  before the clipboard is changed. Delete/Backspace ripple delete also respects
  locked tracks. Blade edits respect locked tracks too: playhead blade skips
  locked lanes and reports when a locked lane was skipped, while track-specific
  blade clicks are blocked on locked lanes.
- Slip mode drags the clip's source in/out window while keeping its timeline
  position and duration fixed. Slide mode performs a true adjacent-clip slide
  edit when the selected clip has touching previous and next clips: the selected
  clip keeps its duration/source window, while the previous clip's out trim and
  next clip's in trim absorb the movement. If those adjacent clips are missing,
  the row falls back to ordinary select/move behavior.
- Ordinary clip trims are clamped against adjacent clips so a normal trim does
  not silently overlap the previous/next clip. Ripple/roll edits remain the
  structure-changing edit tools.
- Precision trim is available from the timeline toolbar and `Ctrl+Alt+T`.
  `Alt+Left/Right` nudges selected clips by one frame; `Shift+Alt+Left/Right`
  nudges by one second; `Ctrl+Alt+Left/Right` nudges by ten frames. Successful
  keyboard nudges show a short status banner with clip count, frame/ms amount,
  and linked-audio count. Empty nudge attempts prompt the user to select clips.
  The timeline status chip keeps this shortcut detail in a tooltip so the
  toolbar does not stretch on narrow/full-mode layouts.
- Clip move/delete operations must also be explicit from the video-clip
  right-click menu. The context menu targets the clicked clip, not an ambiguous
  global selection, and exposes a `Move clip` submenu with move-to-playhead,
  move-to-time, and frame nudge commands (`-1`, `+1`, `-5`, `+5` frames).
  Destructive choices are named separately as `Delete clip (leave gap)` and
  `Ripple delete clip (close gap)`. These menu items route through registered
  Python Actions (`clip.move`, `clip.nudge_frames`, `clip.delete`, and
  `timeline.ripple_delete`) so UI, automation, undo/history, and future MCP
  paths share the same edit contract.
- Plain `Up/Down` jumps the playhead to the previous/next edit point. Edit
  points include video clip in/out edges, audio clip offsets/ends, timeline
  markers, and Spine/Live2D actor clip start/end times. If the playhead is
  already on an edit point, the shortcut skips to the neighboring point instead
  of staying put.
- Timeline zoom is available from the toolbar buttons, mouse wheel over the
  timeline, and keyboard shortcuts: `Ctrl+=` zooms in, `Ctrl+-` zooms out, and
  `Ctrl+0` fits the timeline to the visible width. Keyboard zoom operations
  share the same clamped zoom path as the buttons and show a short status
  banner.
- Keyboard timeline navigation keeps the playhead visible without stealing view
  during ordinary playback: edit-point jumps, Left/Right/Home/End seeks, and
  keyboard zoom adjust the horizontal scroll only when the playhead is outside
  the current timeline viewport margin.
- Keyboard seek bounds use the full project duration reported by
  `ProjectPlayer`, not only the active video track duration. This lets
  `Right`/`End` reach audio-only tails and Spine/Live2D actor-only extents.
- `J/K/L` transport shortcuts mirror a commercial NLE deck workflow within the
  current player limits: `L` cycles forward shuttle speeds
  `1x/2x/4x/8x/16x/32x`, `K` pauses and resets shuttle speed, and `J` performs
  repeatable reverse jog steps because true reverse playback is not implemented
  in `ProjectPlayer` yet. The physical jog/shuttle widget now also treats a
  center/zero shuttle speed as pause.
- NLE positioning is intentionally conservative. Tiger Studio has a core
  nonlinear editing workflow/action surface: track targeting, In/Out markers,
  Source/Record monitor action state, 3-point insert/overwrite, lift/extract/
  range delete, clipboard insert/overwrite, gap close, frame nudge, snapping,
  marker/edit-point navigation, linked-clip movement, and Python Action / AI /
  MCP automation. `timeline.professional_nle_readiness` and
  `tools/qa_nle_readiness.py` keep this claim honest. It should not yet be
  marketed or documented as a full Premiere/Resolve-class NLE replacement. The
  evidence-free baseline remains conservative at about 49/100; the synthetic NLE contract corpus
  raises the current QA score to about 91/100 by proving registered actions,
  Source/Record workbench state and monitor layout, project-bin workbench and
  review-board metadata, long-project stress evidence, undo review-board
  evidence, proxy/bin/relink/search metadata, and multicam group/switch plan/
  tile-board/sync-quality/export handoff contracts. The 91/100 implementation
  score also includes UI-ready safety/polish boards for core NLE action safety,
  Source/Record usability, proxy/conform reviewed apply flows, multicam export
  parity, undo long-session rehearsal, and Final Cut-style gesture polish. This is still not real
  long-footage proof, so the safe claim is still "core NLE workflow/action
  surface" rather than "Premiere/Resolve-grade professional NLE".
- Correct intended wording: "core NLE workflow/action surface" rather than
  "Premiere/Resolve-grade NLE".
- Real long-project NLE evidence is now explicitly separated from generated
  fixtures. `tools/discover_nle_real_projects.py` and
  `nle.real_corpus.discover` find project-like `.tgp`/JSON candidates and
  explain whether each one can be registered. `tools/register_nle_real_project.py`
  registers real projects, `tools/qa_nle_real_project_corpus.py` writes
  `debugCapture/nle_real_project_corpus_qa.json`, and `nle.real_corpus.status`
  exposes the same state to Python Action/MCP callers. The full-NLE claim gate
  stays blocked unless at least three real projects meet aggregate duration,
  clip-count, and no-missing-media thresholds.
- `nle.real_corpus.intake_board` turns the same conservative gate into a
  product-facing intake surface. It groups threshold gaps, registerable
  candidates, rejected candidates, and registered projects so the editor/AI can
  guide users toward real long-project validation without treating generated
  stress fixtures as release evidence. This improves the corpus collection
  workflow, but it still does not clear the `real_world_long_project_corpus`
  professional-claim blocker until the real corpus itself passes.
- `nle.real_corpus.collection_kit` wraps discovery, intake, registration, real
  corpus QA, and NLE readiness rerun steps into one UI/AI-ready guide. It exists
  specifically to make the remaining long-project blocker actionable without
  pretending generated projects are release evidence.
- `nle.real_corpus.gate_board` is the combined claim-gate board for UI, local
  AI, and MCP callers. It merges current corpus status, blocked thresholds,
  registerable/rejected candidates, validation-missing projects, validation-ready
  projects, and rerun commands into one product-facing payload. The board is
  evidence visibility only: `professional_nle_claim_blocked=true` remains until
  the real corpus and validation evidence satisfy the strict gate.
- `nle.real_corpus.workbench` is the single UI/MCP entry point for the same
  workflow. It combines discovery, registerable candidates, machine preflight,
  operator-evidence status, claim blockers, cards, primary next action, QA
  commands, and an action sequence so the app can show one coherent "get me to
  NLE evidence" panel instead of scattering status across separate actions.
- `nle.real_corpus.validation_plan` is the follow-up surface for registered
  real projects. It breaks each project into open/reopen, scrub sampling,
  proxy/relink health, undo/recovery rehearsal, representative short export,
  and nested/proxy edge-case checks. This improves operator QA clarity, but the
  professional-NLE blocker still remains until the real corpus itself passes.
- `nle.real_corpus.validation_packet` is the project-specific operator packet
  for the same real-project gate. It auto-selects a registered project that
  still needs evidence when no project is specified, shows required/optional
  checks, redaction rules, manual steps, a reviewed action template, and a CLI
  template for `tools/register_nle_real_project_validation.py`. It is a form
  and checklist, not proof; the operator must run the checks and register real
  results before readiness can pass.
- `nle.real_corpus.validation_preflight` sits between the packet and evidence
  registration. It runs machine-checkable prerequisites for the selected real
  project (file exists, parse succeeds, no missing media, duration/clip counts,
  scrub sample plan, and short export range), then exposes operator checks as
  `ready_for_operator` or `blocked`. It never marks evidence as passed; its
  action template keeps every required validation check `pending` until a human
  records the actual result. `tools/qa_nle_real_project_preflight.py` writes
  the same machine-preflight status for every registered project into
  `debugCapture/nle_real_project_preflight_qa.json`. The strict real-corpus QA
  summary now also reports `preflight_ready_count` and blocks
  `validation_preflight` when registered projects are not machine-ready for
  operator evidence.
- `nle.real_corpus.validation_report` and
  `nle.real_corpus.validation_evidence.register` add the missing execution
  evidence layer for real NLE projects. A registered project can now store
  redacted per-check evidence for open/reopen, scrub sampling, proxy/relink
  health, undo/recovery, representative short export, and nested/proxy edge
  cases. The report summarizes validation-ready projects separately from the
  metric-only corpus gate, so product UI/AI can see whether real projects were
  actually exercised instead of merely registered. This still does not allow a
  full professional-NLE claim without enough real projects and passed evidence.
- Official NLE real-corpus QA now requires validation evidence by default.
  `tools/qa_nle_real_project_corpus.py` writes a claim-ready report only when
  the metric thresholds and the required per-project validation evidence both
  pass. The `--metric-only` switch exists for diagnostics, but metric-only
  reports must not clear release or marketing claim gates.
- Operator validation evidence can be written either through the Python Action
  `nle.real_corpus.validation_evidence.register` or the CLI
  `tools/register_nle_real_project_validation.py`. The CLI supports
  `--all-passed` for the required checks and repeatable `--check id=status`
  entries for partial/failure evidence. `nle.real_corpus.collection_kit` also
  exposes `validation.cli_examples` so UI/AI surfaces can show copy-ready
  operator commands for each registered real project.
- NLE readiness scoring now distinguishes implemented Final Cut-style UI polish
  from the current sample timeline's gap state. Role filter panel, cross-row
  connected-anchor overlay, audition card model, and magnetic drag visual
  language are explicit evidence flags in `app/nle_evidence.py`, and
  `app/nle_readiness.py` reflects them in the Final Cut-style storyline row.
  This can raise implementation readiness, but it still does not clear the
  `real_world_long_project_corpus` professional-claim blocker.
- `timeline.nle_target_gap` returns the UI/AI/MCP answer to "how far are we
  from 95?" without changing scores. It analyzes the current
  `timeline.professional_nle_readiness` rows, reports per-row score gaps, keeps
  `real_world_long_project_corpus` as a hard blocker, and lists the real-corpus
  project/duration/video/audio/validation evidence still required before any
  professional NLE claim is safe. `tools/qa_nle_target_gap.py` writes the same
  board to `debugCapture/nle_target_gap_qa.json` for dashboards and handoffs.
- NLE readiness scoring rules are split into `app/nle_readiness_scoring.py`.
  `app/nle_readiness.py` remains the report assembler, while row score ladders
  live in reusable helpers. The report also exposes `score_breakdown` so UI,
  local AI, and MCP callers can read per-row score/status without reparsing the
  long row list.
- NLE score ceilings now have a real-world unlock: when
  `evidence_level=real_project_corpus` and the strict real-project corpus gate
  passes, implemented NLE rows can score 95-96 and the aggregate can exceed
  95/100. Without that corpus, synthetic/action evidence remains capped around
  the current 91/100 and `real_world_long_project_corpus` stays blocked.
- NLE UI-ready evidence now includes `source_record.monitor_layout`,
  `source_record.apply_board`, `source_record.keyboard_overlay`,
  `source_record.usability_board`, `timeline.nle_core_safety_matrix`,
  `timeline.multicam.tile_board`, `timeline.multicam.review_board`,
  `timeline.multicam.sync_quality_board`, `timeline.multicam.waveform_sync_board`,
  `timeline.multicam.export_parity_board`,
  `project_bin.review_board`,
  `project_bin.search_filter_model`, `project_bin.offline_browser`,
  `project_bin.proxy_regeneration_board`, and
  `project_bin.proxy_apply_review_board`,
  `project_bin.conform_apply_review_board`,
  `timeline.undo_review_board` / `timeline.undo_recovery_playbook` /
  `timeline.undo_long_session_plan`, and
  `timeline.storyline_gesture_polish_board`. These are UI-neutral view models for drawing a
  Source/Record two-monitor panel plus reviewed insert/overwrite apply cards
  and J/K/L shortcut overlay, a multicam angle grid plus switch/bake review
  board and sync-confidence board, project-bin/proxy/conform review board,
  search/filter/metadata columns, an offline/missing media browser, a reviewed proxy regeneration
  queue, and undo/fuzzer risk plus failure-recovery boards. They improve implementation readiness but
  still do not replace real long-project corpus validation.
- `nle.real_corpus.register` is the product/API companion to the CLI tool. It
  can dry-run project metrics before writing the manifest, registers either the
  current saved project or an explicit `project_path`, rejects generated
  fixtures unless `allow_generated=true`, and lets AI/MCP surface corpus intake
  without exposing arbitrary filesystem or Python execution.
- Final Cut Pro positioning is handled as a different win condition, not as a
  one-for-one clone. Tiger Studio now exposes a named
  `timeline.magnetic_storyline.status/apply` workflow. It detects timeline
  gaps/overlaps, plans Final Cut-style primary-storyline gap closure, applies
  gap-closing moves while preserving clip order, and moves linked audio clips by
  the same delta. `app/nle_magnetic_storyline.py` owns the pure plan/status
  contract and `app/actions/editor_adapter_nle.py` applies it through the
  Python Action surface.
- Final Cut-style connected clip and role-color foundations are now explicit:
  `app/nle_connected_clips.py` owns pure connected-clip status, role palette,
  and action-contract evidence; `timeline.connected_clips.status`,
  `timeline.connected_clips.connect`, `timeline.role_colors.status`, and
  `timeline.clip_role.set` expose the surface to AI/MCP. `VideoClip` persists
  `connected_parent_track_id`, `connected_parent_clip_id`,
  `connected_offset_ms`, `clip_role`, and `role_color`, and project snapshots
  include the same fields for readiness/review automation. Timeline rows show a
  small connected/role strip, but this is still a metadata/action foundation,
  not a full Final Cut role-lane, audition, or visual magnetic interaction
  replacement. The safe competitive wording is: "Final Cut-style fast
  storyline/connected-clip foundations plus Tiger-only actors/PPT/AI/3D
  compositing on Windows," not "full Final Cut replacement."
- Role-aware lane contracts are available for UI renewal and AI review:
  `app/nle_role_lanes.py` groups timeline clips by inferred role, counts
  connected clips and audition clips per role, and exposes a `focused_role`
  state through `timeline.role_lanes.status` and `timeline.role_lanes.focus`.
  `app/video_editor_nle_role_panel.py` and
  `app/video_editor_nle_role_workflow.py` now expose that view-model as a
  compact timeline role filter bar. Timeline rows draw a small role-color rail
  on clips with explicit role, connected-clip, or audition metadata, plus a
  connected diamond and audition take dots when relevant. This is visual
  feedback and a view-model foundation; it is not yet a full Final Cut
  role-lane workspace because cross-row anchors, deep audition visuals, and
  real editor gesture QA are still incomplete.
  The editor mutation adapter now lives in
  `app/actions/editor_adapter_nle_storyline.py`, and public action registration
  lives in `app/actions/nle_storyline_namespace.py`.
- Final Cut-style timeline visual feedback contracts are now separated from
  Qt drawing code. `app/nle_visual_feedback.py` builds connected-clip anchor
  overlay descriptors, role-lane filter models, and magnetic drag-preview
  placements. Python Actions expose them as
  `timeline.connected_clips.anchor_overlay`,
  `timeline.role_lanes.filter_model`, and
  `timeline.magnetic_storyline.drag_preview`; adapter methods live in
  `app/actions/editor_adapter_nle_visual.py` and registration lives in
  `app/actions/nle_visual_namespace.py`. This gives UI renewal and AI/MCP a
  stable contract for anchor lines, dimmed/visible role clips, snap/push/collision
  drag feedback, and non-mutating drag previews without adding logic back to
  `app/video_editor_window.py`. The first Qt timeline integration now lives in
  `app/timeline_nle_visual_overlay.py` and is called from
  `app/timeline_track_row_paint.py`: connected clips draw a stronger in-clip
  anchor cue, and active drag preview rectangles draw compact move/snap/blocked
  guide marks. `timeline.role_lanes.focus` now also propagates to live
  `TrackRow` instances through `set_focused_clip_role(...)`, so non-matching
  roles are dimmed in the timeline while the selected outline remains visible.
  The timeline role filter bar calls the same registered action instead of
  using a private editor path, so UI and MCP/action state stay aligned.
  `app/timeline_connected_anchor_overlay_widget.py` adds a transparent
  viewport overlay for cross-row connected-clip curves when parent and child
  clips are both visible. Magnetic drag cue painting now uses richer
  `field_lines` / `hatch` metadata from `app/timeline_nle_visual_overlay.py`,
  so snap, push, move, and blocked previews read differently during drag. This
  is still not a full Final Cut UI clone until real gesture tuning and editor
  usability QA are completed.
- Final Cut-style audition/take foundations are implemented as host-clip
  metadata rather than hidden stacked timeline lanes. `app/nle_auditions.py`
  owns the pure status and action-contract helpers,
  `app/actions/editor_adapter_nle_auditions.py` owns the editor adapter
  mutation surface, and `app/actions/nle_auditions_namespace.py` owns the
  public Python Action registrations. `VideoClip` persists
  `audition_group_id`, `audition_name`, `audition_active_take_id`, and
  `audition_takes`; project IO saves/loads them; project snapshots expose the
  active take and take count. Python Actions `timeline.auditions.status`,
  `timeline.audition.compare`, `timeline.audition.add_take`,
  `timeline.audition.switch_take`, `timeline.audition.rename_take`, and
  `timeline.audition.remove_take` let AI/MCP build a UI-ready audition picker,
  add candidate takes, switch the active take, rename takes, and remove non-last
  takes safely. Switching copies the selected take's source fields onto the host
  clip, so existing preview/export paths see only the active take. Timeline rows
  show a minimal `AUD` strip/badge; clicking or context-opening that badge now
  routes to `app/video_editor_nle_audition_workflow.py`, a compact audition
  picker dialog that lists takes, marks the active take, and shows a card-style
  comparison strip backed by `app/nle_audition_visuals.py`. It calls the same
  Actions for switch/rename/remove. This is now a usable audition
  data/action/UI foundation, not the full Final Cut polished visual audition
  interaction.
- Multicam and project-bin NLE contracts now include richer UI-ready state:
  `timeline.multicam.sync_plan`, `timeline.multicam.angle_bins`,
  `timeline.multicam.switcher_workbench`, `timeline.multicam.sync_quality_board`,
  `timeline.multicam.waveform_sync_board`,
  `timeline.multicam.live_switch_dashboard`,
  `project_bin.batch_plan`, and `project_bin.search_filter_model` expose
  sync offsets, angle bins, coverage/gap diagnostics, angle tiles, active
  angle, sync confidence, relink/proxy/conform review operations, bin search,
  metadata columns, and export handoff readiness
  while still avoiding a full Premiere/Resolve live-switcher or conform claim.
- Source/Record 3-point editing now has an explicit review payload through
  `source_record.edit_decision_preview`, so insert/overwrite UI can show the
  source range, record range, target tracks, warnings, and safe-to-apply state
  before calling timeline mutation actions.
- Source/Record 3-point editing also exposes `source_record.patch_matrix`, a
  read-only UI contract for video/audio patch rows and insert/overwrite command
  cards before timeline mutation.
- Source/Record 3-point editing also exposes `source_record.keyboard_overlay`,
  a read-only J/K/L, mark-in/out, source patching, and insert/overwrite shortcut
  overlay so the two-monitor UI can show commercial-NLE keyboard affordances
  without binding directly to private editor methods.
- Timeline undo/edge-case evidence is now bridged into NLE readiness:
  `timeline.nle_fuzzer.status` normalizes `tools/qa_timeline_fuzzer.py`
  reports, requiring blade/move/ripple/roll/slip/slide/undo coverage, linked
  audio, actor-lane coverage, and zero failures before the undo QA row is
  treated as stronger evidence.
- Core NLE action coverage is exposed as `timeline.core_action_coverage`, a
  grouped matrix for edit, clipboard/insert, Source/Record, Project Bin,
  storyline, multicam, and undo/recovery action surfaces.
- Undo/edge-case evidence also exposes `timeline.undo_health`, a UI-ready
  operation coverage matrix with risk cards, blockers, and rerun/failure-report
  command state for QA Dashboard or health panels.
- Undo/edge-case recovery is exposed as `timeline.undo_recovery_playbook`, a
  UI-ready rerun/triage/reproduction-step playbook that lets the editor,
  QA Dashboard, or MCP caller show what to do after destructive edit failures
  without exposing private editor methods.
- Undo/edge-case stability is also exposed as
  `timeline.undo_stability_dashboard`, a UI-ready combined board for fuzzer
  status, operation coverage, risk cards, blockers, and recovery commands.
- Proxy/media management now exposes `project_bin.proxy_plan`, a read-only
  proxy policy and regeneration queue contract for usable proxies, stale/missing
  proxies, background-safe refresh candidates, and long-project proxy readiness.
- Proxy/media management also exposes `project_bin.proxy_health`, a read-only
  product health board for proxy state cards, safe background regeneration
  enablement, stale/missing/offline review signals, and long-project proxy
  readiness evidence.
- Proxy conflict handling exposes `project_bin.proxy_conflict_board`, a
  read-only board that separates safe background proxy jobs from offline
  blockers, duplicate media paths, and review-only conflicts so the editor can
  start only safe proxy work without hiding relink problems.
- Project-bin conform now exposes `project_bin.conform_report`, a read-only
  timeline-to-Media-Pool matching report for path matches, name-only matches,
  ambiguous names, offline matches, and missing clip sources before relink or
  batch apply operations.
- Project-bin relink now exposes `project_bin.relink_candidate_board`, a
  file-by-file candidate board for safe path matches, name-only review,
  ambiguous choices, offline matches, and missing sources.
  Product copy should describe this as a "core NLE workflow/action surface"
  rather than a "Premiere/Resolve-grade NLE".
- Remaining NLE gaps are explicit: source-monitor / record-monitor style
  3-point editing backend now exists but the dedicated UI is still shallow;
  dedicated live multicam switcher UI, deeper proxy/media management, conform,
  relink, metadata editing, and visual project-bin workflows need more depth;
  undo/redo and edge-case behavior require continuous regression QA; and
  long-duration / large-project real-world validation needs more evidence
  before strong "full NLE" claims are safe.
- Comma/period provide precise preview stepping: `,` moves back one project
  frame, `.` moves forward one project frame, and holding `Shift` steps ten
  frames. Frame stepping uses the current project FPS, pauses/reset shuttle
  transport first, clamps to project bounds, and keeps the playhead visible.
- Video clips can link to audio clips by `linked_audio_id`; video clip moves,
  group drags, and keyboard nudges move the linked audio clip by the same delta.
  Keyboard nudge uses `timeline_model.plan_linked_timeline_move()` to validate
  video lane collisions, linked-audio lane collisions, missing links, duplicate
  audio IDs, shared linked-audio references, stale selected clip IDs, locked
  video tracks, and project-start bounds before mutating either lane. Mouse
  clip drags use the same strict preflight through
  `TrackRow.set_clip_drag_validator()`, so a blocked locked-track,
  linked-audio, or cross-track move does not first move the video lane and then
  fail to sync the companion lane.
- Mouse-dragging a selected video clip can move selected clips on other video
  tracks by the same incremental delta. Each target track rejects movement that
  would overlap non-selected clips on that track.
- Timeline clip drag feedback is now explicit instead of described only as
  "polish": `timeline_model.apply_drag_constraints_detail()` returns
  `DragConstraintResult` with the final position plus snap target, snap edge,
  snap source, collision, and clamp fields. `TrackRow` paints that result as a
  localized live chip plus a translucent destination ghost near the affected
  timeline point while dragging. Same-row group drags use the same chip and
  ghost path. Linked/cross-track moves that fail preflight paint a red blocked
  ghost instead of silently refusing the drag. The editor-owned drag validator
  can return a structured blocked result (`ok`, `reason`, `message`, `details`);
  `TrackRow` turns reasons such as `timeline_start`, `video_collision`,
  `audio_collision`, `missing_linked_audio`, and `locked_track` into localized
  "Cannot move: reason" chips and appends a `timeline.drag.blocked` row to
  `ux_events.jsonl`. Idle hover chips label trim, roll, transition
  insertion/resizing, fades, speed zones, and typography/actor edges so the
  cursor affordance is discoverable without reading the toolbar. Preset
  applications store the focused target time so the affected row flashes a
  timeline burst and the status banner includes an `@ time` suffix. Drag
  releases and preset apply/failure outcomes append structured diagnostics to
  `ux_events.jsonl` in the runtime log directory. The chip/ghost paint path has
  a short pop/easing pass so feedback appears as a UI motion cue rather than a
  static debug label.
- Compound grouping still uses `VideoClip.compound_group_id` and
  `compound_group_name` for lightweight grouped selection/movement.
- Nested sequence parents use `VideoClip.nested_sequence_id`,
  `nested_sequence_name`, `nested_child_clips`, `nested_child_tracks`, and
  `nested_audio_tracks`, plus `nested_spine_actor_tracks` and
  `nested_live2d_actor_tracks` for actor lanes. `nested_child_tracks` is the
  true internal multi-track video form; `nested_audio_tracks` stores internal
  audio lanes. Child video clip times, actor clip times, and nested audio
  `AudioClip.offset_ms` values are relative to the parent sequence.
- `Nest` can fold a multi-track selection into one parent clip on the active
  selected track. Selected clips are removed from their original tracks and
  copied into internal child lanes in source track order.
- The clip context menu has `Edit nested sequence...` for the dedicated
  internal multi-track editor. It shows a compact timeline canvas for nested
  video/audio/Spine/Live2D lane movement and edge trimming, mouse-wheel zoom,
  Shift+wheel horizontal scrolling, and a playhead line, plus tables for
  precise video/audio millisecond values. `Expand nested sequence` puts child
  video clips, nested audio lanes, and nested actor lanes back onto the main
  timeline for direct editing.
- `ProjectPlayer` keeps nested parents as active clips and renders their
  internal lanes as opaque replacement video layers. Because the current nested
  stack does not alpha-composite child video tracks, preview walks child tracks
  top-down and decodes only the first active visible layer; hidden lower child
  tracks are skipped. `timeline_model.expanded_timeline_clips()` remains
  available for source discovery and compatibility paths.
- `ProjectPlayer.refresh_tracks()` must sync a single-source track's decoder
  metadata (`fps`, `total_frames`, `duration_ms`) before building the clip
  view. A track left at `duration_ms == 0` produces no synthesized clip, which
  makes timeline thumbnails and preview appear blank.
- Timeline drag gestures emit a single history savepoint on mouse release;
  live mouse-move updates should not flood undo/redo. `HistoryStack.push()`
  also ignores duplicate snapshots at the current cursor so no-op commits do
  not consume undo depth. Undo/redo snapshots reconcile the video/audio track
  collections themselves, so track add, delete, and ordering edits can be
  restored instead of only restoring fields on tracks that still exist. Clip
  selection is snapshotted too and restored only for clips that still exist, so
  selection borders and follow-up delete/nudge actions stay aligned after undo.
  `HistoryStack.undo_label()` and `redo_label()` expose the exact pending edit
  label so the editor status banner can say what was restored rather than only
  showing a generic Undo/Redo notice.
- Commercial trim-mode polish lives in pure helpers in `app.timeline_model`:
  `slip_clip_source_window()`, `roll_edit_adjacent()`,
  `slide_clip_between_neighbors()`, `detect_timeline_edge_issues()`,
  `cleanup_timeline_micro_edges()`, and `plan_linked_timeline_move()`. They
  clamp edits to source bounds, require valid adjacency where the edit mode
  needs it, preserve outer timeline spans for roll/slide, validate linked
  audio/video movement, can run strict selection validation for UI gestures,
  detect one-frame-ish same-lane gaps/overlaps, clean tiny accidental gaps by
  rippling following clips, clean tiny accidental overlaps by trimming the
  outgoing clip, and never mutate their input clip list. UI tool modes should
  call these helpers instead of duplicating edge-case math in mouse handlers.
  Track row context menus expose `Clean 1-frame gaps/overlaps` when the current
  lane has auto-fixable edges; the editor applies the cleanup to existing clip
  objects so thumbnail/effect payloads remain attached, then registers one undo
  savepoint and refreshes preview. The same action is available from Health as
  `Clean Timeline Edges` for whole-project cleanup across unlocked video lanes,
  with a count-aware button label and issue preview before execution. When
  cleanup ripples a video clip that has `linked_audio_id`, the linked audio clip
  moves by the same delta; cleanup is blocked before mutation if the linked
  audio is missing, duplicated, shared, would move before project start, or
  would overlap another audio clip.
- Timeline thumbnails are generated as `QImage` objects in worker threads and
  converted to `QPixmap` only on the UI thread. Thumbnail handlers ignore stale
  extractor signals when a newer extraction job has replaced an older one.
- Timeline thumbnails are persisted under
  `~/Videos/TigerCapture/.cache/timeline_thumbs`, keyed by source path, mtime,
  size, thumbnail height, and cache version.
- When the Rust worker is available, `ThumbnailExtractor` first asks
  `app.native_worker.native_generate_timeline_thumbnails()` to fill the
  persistent thumbnail cache via FFmpeg, then emits cached `QImage` frames.
  OpenCV extraction remains the fallback.
- Multi-source clip thumbnails are stored per clip. Painting clips the thumbnail
  draw region to each clip rect so thumbnails cannot bleed into neighboring
  clips.

Audio timeline:

- `AudioTrack` and `AudioClip` live in `app/audio_tracks.py`.
- Audio rows are inserted by `VideoEditorWindow._insert_audio_track_widget()`.
- Waveform and spectrum caches are regenerated; they are not project state.

State-change rule:

- After changing timeline structure, refresh the relevant row, then call the
  player/audio refresh methods used by neighboring code. Many bugs here are
  stale UI/player state rather than bad data.

## Project Save/Load

Core file: `app/project_io.py`.

Format:

- `.tgp` is plain JSON.
- `FORMAT_VERSION` is currently `1.2`.
- Paths are serialized as absolute strings where possible.
- The last project path is stored with Qt `QSettings` by
  `remember_last_project()` / `load_last_project_path()`.
- The main editor toolbar has a `Recovery` action. It ranks autosave/recovery
  candidates through `tools.repair_project`, opens a table-based recovery
  browser with health level, score, missing count, schema-change count, modified
  time, path, reason, recommended action, missing-by-kind counts, missing path
  previews, schema repair previews, actor asset failure previews, and suggested
  next steps, autosaves the current session, then opens the selected readable
  recovery project through the normal loader.
- Recovery reports now include product-facing guidance: each candidate receives
  a health level, score, recommended action, reason, missing path preview,
  missing-by-kind summary, schema change preview, actor failure preview, and
  suggested actions. `repair_project_doc()` also returns `repair_guidance` with
  missing-media, actor-asset, schema-change counts, and suggested next steps.

Saved:

- Video tracks, clip layout, cuts, fades, speed, zoom actors, typography actors,
  clip filters, chroma key, stabilization, background removal, node graph view
  data, per-clip node graph color state, masks, nested sequence child
  video/audio/Spine/Live2D tracks, audio tracks, subtitles, markers, timeline
  zoom, playhead, preview-only comparison mode/label visibility,
  project color-management settings, Spine actor tracks, Live2D actor tracks.
  Motion Designer documents are stored in `motion_compositions`; main-timeline
  placements are stored separately in `motion_clips` and reference a
  composition by stable ID.
- Undo/redo snapshots mirror the important saved edit state: video/audio tracks,
  subtitles, active track, timeline markers, timeline zoom, playhead, Spine
  actor tracks, and Live2D actor tracks. Snapshot restore recreates deleted
  video/audio tracks, removes tracks created after the snapshot, reorders rows,
  and refreshes audio mixer/player bindings. This keeps track-level edits,
  actor-lane moves, and marker edits from becoming one-way changes inside a
  session. Motion compositions and Motion Clips are included in the same
  snapshot/restore path.

Regenerated on load:

- Thumbnails, waveform peaks, spectrum bins, OpenGL state, player caches.

Important caveat:

- A `.tgp` project is an integrated editor document, not a universal Tiger
  Studio workspace package. It restores the supported timeline-owned state,
  but does not imply that every standalone tool document, transient lab
  session, external service state, or referenced source asset is embedded.
  PPT Maker uses `.tgppt`; Motion Designer uses `.tgmotion` for independent
  authoring and can also embed compositions in `.tgp`.
- The `project_io.py` header says node-level `ColorGrade` is not persisted, but
  newer node graph serialization may save some grade-like state through graph
  data. `app/color_workflow.py` presets return color-node workflow payloads for
  graph/UI attachment, but full UI persistence still depends on the active node
  graph serialization path. Verify current `project_io.py` and
  `app/workbench/node_graph/scene.py` before changing color persistence.

## Preview and Export Pipeline

Preview:

- `ProjectPlayer` in `app/project_player.py` renders interactive frames.
- It composites video, subtitles, drawings/stickers/bubbles, typography actors,
  Spine actors, Live2D actors, node graph effects, masks, and color processing.
- It uses `track.node_item_chain` when available, falling back to older
  `color_grade_chain` / `node_mask_chain` paths.
- `ProjectPlayer.gpu_frame_ready` is the primary main-preview path and carries
  the final RGB ndarray to `OpenGLPreviewWidget`. `ProjectPlayer.frame_ready`
  is the legacy CPU `QImage` path for popout/scopes/fallback consumers.
  `VideoEditorWindow` keeps `TIGERCAPTURE_PREVIEW_QIMAGE=auto` by default:
  QImage stays enabled until the GL preview has accepted a frame, then turns
  off unless a CPU-image consumer such as preview popout is active. Force with
  `TIGERCAPTURE_PREVIEW_QIMAGE=1` or disable with `=0`. Mask/tracking tools
  read from the latest GPU RGB cache first and fall back to `_preview_pixmap`.
- The viewer toolbar exposes a `Compare` popup for the current MVP comparison
  path. It can turn comparison off, show Original-only, or show Split/Wipe
  before-after preview with canvas `Original` / `After` labels. The label
  visibility can be disabled without disabling the comparison.
- The viewer `Fit` button must work in both CPU pixmap and GL preview modes.
  In GL mode it uses `_preview_gl_frame_size` to resync preview geometry and
  overlay placement even when `_preview_pixmap` is empty.

Export:

- `VideoEditorWindow._on_export()` creates `VideoExportThread`.
- Single export now runs a professional-readiness preflight from the current
  in-memory session before starting the encoder. The completion/failure dialog
  appends the same compact readiness diagnostics used by Health, so long-project
  stability, GPU preview/export, timeline, color, audio, and preset/template
  ecosystem risks are visible in the export result. A final checklist dialog
  summarizes queued jobs, actor clips, Color/Audio QA status, and readiness
  details before single or batch export starts.
  Preview/export readiness includes shader-vs-CPU feature parity, project and
  grade LUT bake samples, HDR/OCIO/display-transform metadata samples, audio
  effect graph samples, clip/track automation envelope samples, and bus-routing
  mixdown checks.
- `app/video_exporter.py` builds FFmpeg segment/filter graphs and runs the
  subprocess.
- `VideoExportThread` receives project settings and appends project
  color-management FFmpeg metadata (`-colorspace`, `-color_primaries`,
  `-color_trc`) on non-HDR-passthrough exports. HDR passthrough keeps the
  existing HEVC 10-bit BT.2020 PQ path and does not duplicate metadata.
- Active project input/creative/output LUT slots are appended to the final
  video filter graph with FFmpeg `lut3d`; strengths below 100% use a split and
  blend branch so LUT intensity is baked into exports instead of remaining a
  preview-only setting.
- Render diagnostics can compare a parsed ffprobe video stream against
  `validate_export_color_consistency()` via
  `compare_ffprobe_color_metadata()`, flagging missing or mismatched
  colorspace, primaries, and transfer tags.
- Export completion runs post-render color metadata QA through
  `probe_export_color_metadata()`. It prefers `ffprobe` when available and
  falls back to parsing `ffmpeg -i` stream metadata when only the bundled
  imageio-ffmpeg binary exists. Single exports append the result to the
  completion dialog; dockable Render Queue jobs persist the same result in the
  diagnostics column/history.
- LTX-style SDR-to-HDR upmapping is represented as a separate job-node/workflow
  foundation rather than mixed into ordinary export. `app/sdr_hdr_upmap.py`
  builds a deterministic SDR video -> HDR-capable float EXR frame sequence
  command with a scene-linear target contract and exposes LTX/ComfyUI provider
  hooks via environment configuration.
  `tools/convert_sdr_to_hdr_exr.py` can dry-run or execute the EXR conversion,
  and `tools/qa_sdr_hdr_upmap.py` validates that the pipeline produces an EXR
  float command, preset gallery, review model, and an honest claim label. The
  module exposes `sdr_hdr_upmap_preset_gallery()` and
  `sdr_hdr_upmap_review_model()` so UI adapters can show Soft HDR / Social HDR /
  Cinematic Probe / EXR Archive presets and slider controls instead of raw
  FFmpeg settings. The Workbench node graph exposes this as an `SDR -> HDR EXR`
  job node with peak-nits, exposure, highlight, saturation, and max-frame
  controls. In the main Workbench inspector the node
  also exposes a `Create EXR Frames...` action that asks for an output folder
  and runs the hidden FFmpeg EXR job against the selected video track. This is
  not a bundled LTX 2.3 HDR model claim; when no external provider is configured
  it uses the deterministic local inverse-tone-map fallback.
- LTX-style Storyboard / Shot Card planning is represented as a local-first
  pre-timeline planning layer. `app/ltx_storyboard.py` converts a creator prompt
  plus project/media metadata into `StoryboardPlan` and `ShotCard` objects with
  shot type, source media query, camera angle, camera motion, transition hint,
  actor/audio/color intent, style bible, and optional provider hook state. It
  converts those cards into validated review-first `EditPlan` operations
  (`create_short_candidate`, `add_marker`, `add_auto_zoom`, `add_callout`,
  `apply_preset`, `set_reframe`, `add_render_queue_job`) without mutating the
  timeline directly. `tools/build_ltx_storyboard.py` writes a standalone report
  and `tools/qa_ltx_storyboard.py` verifies shot-card metadata, safe EditPlan
  validation, apply payload markers/sidecars, retake variations, template
  recommendations, provider-contract presence, and the honest claim label
  `ltx_inspired_local_shot_cards_not_ltx_cloud_parity`.
  `tools/qa_ltx_storyboard_corpus.py` runs multiple screen-tutorial,
  gameplay, product-demo, dialogue, and Korean storyboard prompts as a
  local corpus. Creator Assist / CapCut workflow bundles expose this as
  `ltx_storyboard`, `ltx_storyboard_apply_payload`,
  `ltx_storyboard_effect_materialization`,
  `ltx_storyboard_variations`, and
  `ltx_storyboard_template_recommendations`; the review panel shows a
  `Shot cards` card with zoom/callout/retake/template counts. The effect
  materialization payload contains normalized review-first zoom windows,
  callout labels, template links, and effect rows so editor UI can stage actual
  visual effects without re-parsing shot-card prose. Creator Assist applies the
  zoom windows as clip zoom actors and mirrors them to timeline-visible zoom
  chips; callouts become real typography actors on the video track, with LTX
  source metadata so re-applying replaces only the staged storyboard effects.
  Template links are mapped to existing workflow template presets where a safe
  local alias exists, staged once per target clip/start time, and recorded in
  project settings to prevent duplicate stacks.
  Project settings record
  `ltx_storyboard_ready`, `ltx_storyboard_shots`,
  `ltx_storyboard_zoom_windows`, `ltx_storyboard_callouts`,
  `ltx_storyboard_variations`, and
  `ltx_storyboard_template_recommendations`.
- Export formats: MP4, WebM, MOV.
- Quality presets and format registry live in `app/video_exporter.py`.
- Audio tracks are mixed through the FFmpeg audio graph from
  `app/audio_tracks.py`.
- Spine actors are pre-rendered to transparent overlays by export.
- Live2D actors are pre-rendered on the main thread before export because of
  OpenGL/runtime constraints.
- Final baking of Spine and Live2D overlays was verified with a synthetic
  export smoke test: a fake Spine clip and a pre-rendered Live2D MOV produced
  visible pixels in the final MP4 output.
- Batch export uses `app/batch_export_dialog.py`.
- Render Queue jobs created from the editor can persist professional-readiness
  preflight diagnostics. The queue keeps that preflight attached while the job
  moves through pending, running, stage updates, and completion diagnostics.
- Multi-source or multi-track nested sequence export uses the raw pre-render
  base path. `VideoEditorWindow._on_export()` switches to project-time
  segments and passes `render_clip_tracks` to `VideoExportThread`, which decodes
  and composites nested/internal lanes before piping RGB frames into FFmpeg.
- Nested sequence audio is persisted as nested `AudioClip` lanes. During
  nested/multi-source export, ordinary audio tracks and nested audio clips are
  remapped from project time to compact output time before being mixed through
  `app/audio_tracks.py`.
- Nested audio preview is handled through a hidden synthetic `AudioMixer` track
  that mirrors nested `AudioClip` lanes into project time whenever player
  tracks are refreshed.

Parity notes:

- Active-track node graph blur/effect/color/mask chains are exported through
  a raw pre-render fallback in `VideoExportThread`.
- Clip-level CPU effects are also routed through that raw pre-render fallback:
  stabilization, video filters, chroma key, and background removal params are
  applied before the normal FFmpeg overlay/audio stage.
- Nested child video clips also apply their clip-level stabilizer, filters,
  chroma key, background removal, per-clip color node state, and clip-attached
  typography actors in preview and raw export.
- Nested child video clips support internal fade segments and the common
  `fade_black`, `fade_white`, and `dissolve` transition-out types in preview
  and raw export.
- Nested Spine/Live2D actor lanes are first-class nested sequence data and are
  composited into the nested raw base in preview/export. Top-level actor tracks
  still use their existing overlay paths.
- This fallback is slower than the FFmpeg-only path and is used only when the
  node chain, clip effect snapshots, or nested/multi-source clip tracks require
  preview-parity baking.
- Background removal export calls the same `BackgroundRemovalParams.apply()`
  path as preview. Actual AI model quality still depends on installed
  MediaPipe/rembg/runtime behavior and should be profiled with real footage.

## Video Effects, Filters, and Background Tools

Core files:

- `app/video_filters.py`: filter parameter model and RGB application.
- `app/chroma_key.py`: HSV chroma key and spill suppression.
- `app/background_removal.py`: MediaPipe/rembg/fallback background removal.
- `app/video_stabilizer.py`: Lucas-Kanade optical-flow style stabilization.
- `app/video_decoder.py`: decoding helpers and FFmpeg/OpenCV frame access.

Behavior notes:

- Some processing is preview-time CPU work; some is exported through FFmpeg.
- Chroma key returns RGB plus alpha-like mask semantics.
- Background removal prefers MediaPipe selfie segmentation, then rembg, then a
  simple fallback.
- Stabilization is optical-flow based and can be expensive. Preview uses
  `FrameStabilizer.apply_preview()`: motion is estimated on a low-resolution
  grayscale buffer controlled by `TIGERCAPTURE_STABILIZER_PREVIEW_SCALE`
  (default `0.5`, clamped `0.25..1.0`), then the affine warp/crop is applied to
  the full preview frame. Export still uses full-quality
  `FrameStabilizer.apply()`, so preview speedups do not change final render
  quality.
- Proxy generation is triggered for high-resolution media from
  `VideoEditorWindow._start_proxy_generation()`.

## Text, Typography, Subtitles, and Overlays

Core files:

- `app/subtitles.py`: subtitle model, edit dialog, subtitle panel.
- `app/typography.py`: text clip/track data model.
- `app/typo_animations.py`: animation preset and timing logic.
- `app/typo_render.py`: text/typography rendering helpers.
- `app/video_editor_window.py::TypographyEditorDialog`: modal typography
  editor.
- `app/drawing.py`: drawing canvas, stickers, bubbles, overlay composition.

Behavior notes:

- Subtitles are timeline-lane items and are saved in `.tgp`.
- Typography supports IN / HOLD / OUT style animation stacking.
- Typography actors exist both as video-track-local actors and separate text
  track/editor UI concepts; check call sites before moving state.
- Speech bubbles, stickers, and freehand strokes are composed as overlays in
  preview/export paths.

## Node Graph, Masks, and Object Tracking

Core files:

- `app/node_mask.py`: mask data model and evaluation.
- `app/mask_editor_window.py`: large-canvas mask editor.
- `app/workbench/node_graph/widget.py`: node right-click mask menu.
- `app/workbench/node_graph/scene.py`: node graph save/load, including masks.
- `app/workbench/node_graph/items/node_item.py`: base color/serial node item.
- `app/workbench/node_graph/items/blur_node_item.py`: blur/bokeh node.
- `app/workbench/node_graph/items/effect_node_item.py`: generic effect node.
- `app/effect_node_params.py`: effect-node parameter models.
- `app/blur_params.py`: blur parameter model and masked blur composition.
- `app/project_player.py`: preview render pipeline.
- `app/video_editor_window.py`: node mask requests and preview refresh.
- `app/workbench_panel.py`: blur-node mask controls.

Node graph behavior:

- Node graph UI, connections, serialization, and scene restore live under
  `app/workbench/node_graph/`.
- Node graph scenes are dynamic and must use `QGraphicsScene.NoIndex`, not a
  BSP index, because connection paths change geometry while users drag ports
  and nodes. Temporary drag connections must be discarded before node deletion
  or scene reload, and `ConnectionItem.prepareGeometryChange()` must run before
  changing temporary endpoint coordinates.
- Color nodes are base `NodeItem` instances with `color_grade`.
- `app/color_workflow.py` holds Qt-free professional color concepts used by
  future Color-page UI and QA: RGB/master curves, HSV qualifiers, tracked
  power-window masks, masked node application, and numeric scope diagnostics.
  Qualifiers persist HSL range, softness, clean black, clean white, denoise
  radius, and invert controls so key cleanup can match commercial color-page
  behavior. Tracking windows persist normalized shape/feather/opacity plus
  tracker status metadata for later correction UI.
- `app/color_management.py` is the Qt-free project color-management model:
  Rec.709, sRGB, Rec.2020 HDR PQ/HLG, P3-D65, ACEScg/ACEScct intent,
  optional OCIO config path, input/creative/output LUT slots, FFmpeg color
  metadata generation, pipeline summaries, and project/export consistency
  validation. It also compares parsed ffprobe video stream color metadata
  against the expected project output metadata for render diagnostics.
- `app/color_ocio.py` is the PyOpenColorIO bridge. Source and packaged
  dependencies include OpenColorIO 2.5.2 or newer. It accepts external config
  files and versioned built-in config URIs such as
  `ocio://studio-config-v2.2.0_aces-v1.3_ocio-v2.4`; the latter is the default
  selected when a user first chooses ACEScg/ACEScct or the ACES view. It uses
  separate input and display-output color-space resolution and returns the
  original frame with explicit diagnostics if the runtime or config is
  unavailable.
- `app/color_runtime.py` is the shared main-editor/Motion runtime boundary.
  Default Rec.709/sRGB projects remain byte-identical. ACEScg/ACEScct projects
  use the configured OCIO processor when available and otherwise use an
  explicitly diagnosed deterministic ACES-fitted display fallback. Main
  preview applies the transform once after Motion/video compositing and before
  both OpenGL and QImage emission. Main export bakes the same display transform
  to a cached 3D LUT and converts HDR delivery to real 10-bit Rec.2020 PQ/HLG
  with FFmpeg `zscale`, matching primaries/transfer metadata.
- `tools/qa_color_ocio_parity.py` generates a real Studio ACES 1.3 color-chart
  preview and its 17-cube export LUT evidence under
  `debugCapture/color_ocio_parity`. The 2026-07-28 run compared all 4,913 LUT
  grid samples and measured `max_abs_byte_delta=0` between the shared preview
  processor and export LUT. This proves Tiger's current Preview/LUT parity; it
  is not an ACES product-certification claim.
- `TigerStudio.exe --color-runtime-probe <report.json>` is a headless frozen
  build smoke path. It does not create a Qt window; it verifies the packaged
  PyOpenColorIO extension, built-in ACES registry, Studio ACES 1.3 processor,
  real pixel transform, and cached LUT generation. The 2026-07-28 frozen build
  reported OpenColorIO 2.5.2, eight built-in configs, `engine=ocio`, and exit
  code zero in `debugCapture/color_frozen_runtime_probe.json`.
- `tools/qa_color_encoded_export.py` writes an actual 24-frame H.265 Main 10
  Rec.2020 PQ chart, decodes it back through the inverse display conversion,
  and measures patch-center RGB and CIE76 error. The 2026-07-28 run reported
  mean byte error `2.18`, mean Delta E 76 `1.05`, maximum Delta E 76 `1.93`,
  and matching `bt2020nc/bt2020/smpte2084` stream metadata. Regenerable
  artifacts and the report live under
  `debugCapture/color_encoded_export_qa`.
- `app/color_scopes.py` includes `scope_quality_diagnostics()` for color-page
  badges and QA: luma IRE percentiles, HDR nits estimate, channel clipping,
  saturation/gamut risk, skin-tone angle, and warning strings.
- `tools/qa_color_audio_accuracy.py` is the repeatable synthetic accuracy QA
  entry point for scopes, color-management metadata/LUT graph expectations,
  loudness, true peak, stereo correlation, and dialogue-cleanup preset
  clamping. It also accepts `--video-sample` and `--audio-sample` paths for
  real media diagnostics without changing the deterministic reference checks.
  `--sample-root` or the default `qa_corpus/color_audio_samples` folder can
  auto-discover video/image and audio samples for ongoing scopes/LUT/OCIO,
  loudness, and dialogue-cleanup corpus validation. It writes
  `debugCapture/color_audio_accuracy_qa.json`. Latest Color/Audio QA status is
  appended to export and Render Queue preflight diagnostics as a compact badge
  with OK/FAIL, check count, failure count, and real sample count.
- `ColorPageWindow` exposes a compact project color-management strip above the
  scopes/wheels area. It edits input, working, output, transfer, view transform,
  HDR flag, OCIO config, project LUT slots, and creative LUT intensity directly against
  `_project_settings["color_management"]`. The creative LUT slot also syncs to
  the existing global preview LUT path so the viewer reflects the selected look.
  Changing pipeline settings invalidates the player frame cache and refreshes
  the current preview immediately. Actions/MCP expose the same project boundary
  through `color.management.get/set`.
  Color-management validation and scope warnings are displayed through shared
  UX tone states so valid, warning, and failure states are visually distinct.
- The Color Page chrome is intentionally less programmatic than the underlying
  data model: the top bar uses a palette ribbon and `Color Grade` title, the
  pipeline bar groups input/look/output controls, color wheels sit in rounded
  glass cards, scope displays have rounded black monitor surfaces, and
  qualifier/window controls use compact pill rows with color-domain gradient
  sliders.
- The timeline `Color` page switch defaults to the embedded in-editor color
  dock instead of opening the detached `ColorPageWindow`. This keeps the main
  preview visible while grading and prevents the power-window overlay from
  feeling like a second stacked preview. Detached Color Page behavior remains
  available to explicit callers, and Color Page grade changes rebuild the live
  node chain before refreshing preview.
- `ColorPageWindow` also exposes a right-side Qualifier / Window panel. It
  edits HSL qualifier enable/invert, hue center/width, saturation/value ranges,
  softness, clean black/white, denoise radius, power-window shape, normalized
  center/size, feather, opacity, and tracking intent. Changes are written into
  `ColorGrade.color_workflow` so the existing preview/export CPU path can apply
  the same masked grade and curves. The panel also shows compact scope warning
  text from `scope_quality_diagnostics()` while frames are pushed to the page.
- When the Color Page is open and the active grade's power window is enabled,
  the main preview `DrawingCanvas` shows a direct editable overlay on the video
  rect: users can move the center or drag side/corner handles for ellipse and
  rectangle windows. The overlay writes normalized window coordinates back to
  `ColorGrade.color_workflow`, throttles live preview refresh to roughly 30fps
  while dragging, and records one undo step on mouse release.
- The standalone drawing/paint dialog supports explicit PNG export from the
  window. `Export PNG` offers a composited PNG path that includes the current
  backing image plus all paint/object overlays, and a transparent-overlay PNG
  path that writes only the editable paint/object layer. The same contract is
  available to automation through `paint.export_png`, so AI workflows can
  produce reviewable still overlays without routing through timeline video
  export.
- The standalone drawing/paint dialog has canvas zoom controls for detailed
  brush and object placement. The top bar exposes zoom out, zoom in, and Fit
  buttons plus a `25%` to `800%` zoom slider and percent readout. Keyboard and
  mouse shortcuts share the same clamped zoom path: `Ctrl++`/`Ctrl+=` zoom in,
  `Ctrl+-` zooms out, `Ctrl+0` and `Ctrl+1` reset to fit/100%, and
  `Ctrl+MouseWheel` zooms around the paint workspace. Zoom is an editing-view
  affordance only; PNG/timeline export still uses the original canvas/export
  size and normalized paint/object coordinates.
- At high Painter zoom levels, the canvas draws an automatic pixel-grid overlay
  from the backing document pixel dimensions so dot/pixel-art work has visible
  cells. The overlay is view-only, separate from the explicit Grid/Snap controls,
  stride-capped for large documents, and never baked into PNG/timeline export.
  High-zoom canvas display uses crisp nearest-neighbor scaling so source pixel
  boundaries remain legible while normal zoom keeps smoother preview scaling.
- `ColorGrade.color_workflow` persists color workflow payloads from the
  professional color preset menu. `apply_to_rgb()` applies the workflow's
  qualifier/window mask and curves on the CPU path so preview/export can see
  the result before shader support exists.
- `ColorGrade` also carries grade-local input/creative/output LUT slots.
  `apply_to_rgb()` applies those LUT slots through the existing cube-LUT
  renderer, and `apply_grade_stack()` applies clip/group/timeline grade layers
  in explicit order. `suggest_shot_match_grade()` provides a deterministic
  exposure/contrast/saturation adjustment for future auto color-match UI.
- Blur nodes have `NODE_KIND = "blur"` and use `BlurParams`.
- Effect nodes use `EffectNodeItem` plus parameter classes from
  `app/effect_node_params.py`.
- Scene serialization stores node positions, graph topology, masks, blur params,
  effect params, and node view metadata.
- The default editor color node is not decorative: when a track is first bound
  to the node graph, `NodeGraphWidget.set_track()` must create `Node 1` as an
  active `IN -> Node 1 -> OUT` chain. Older or damaged `node_graph_view_data`
  snapshots with serial nodes but no output connection are repaired by
  `NodeGraphScene.ensure_default_chain()` when opened so color controls affect
  the visible preview immediately.
- `VideoEditorWindow._rebuild_active_chain()` decides what the main preview
  should render through. The current behavior is "full IN -> OUT chain" for
  visible preview, with selected-node binding still used by the Color panel.
- `VideoEditorWindow._commit_color_preview_edit()` is the common commit point
  for color dock, Color Page, LUT, and preset changes. It clears stale preview
  caches, rebuilds/repairs the active node chain when necessary, and refreshes
  the current frame without requiring a playhead seek.
- The compact Color dock shows an active target badge so users can see whether
  the edit is routed to a color node or a track fallback grade.
- The compact Color dock and viewer `Compare` popup expose preview-only
  `Before`/`Original`, `Split`, and `Wipe` comparison controls. They set
  `track.preview_color_compare_mode`; projects persist that preview state plus
  `track.preview_compare_labels_enabled`, but export still treats it as
  preview-only until the planned `comparison_view` project model exists.
  `ProjectPlayer` uses `_apply_node_chain_preview_compare()` to skip active
  ColorGrade nodes for Before, or composite before/after halves for Split/Wipe,
  while keeping non-color node effects visible. See
  `docs/SPEC_COMPARISON_TEMPLATES.md` for the export-safe long-term design.

Mask types in `app/node_mask.py`:

- `PowerWindow`: polygon mask.
- `HSLQualifier`: color-range mask.
- `MagicMask`: MediaPipe/OpenCV semantic masks for lips, face, eyes, person.
- `MaskTracker`: wrapper for older tracker workflows.
- `BitmapMask`: baked pixel mask from GrabCut/SAM/manual drawing; can track.

Tracked object masks:

- `BitmapMask.track_object=True` enables OpenCV CSRT tracking.
- `BitmapMask.init_frame` stores the source frame where the region was selected.
- Runtime bbox cache is stored in `_track_cache` as `frame_idx -> (x, y, w, h)`.
- Persisted bbox cache is stored in `tracking_cache_bboxes` as normalized bbox
  values and restored into `_track_cache` on demand.
- Failed frames are tracked in `_failed_frames` and persisted as
  `tracking_failed_frames`.
- Correction keyframes are persisted in `correction_bboxes` and serialized by
  `to_dict()` / `from_dict()`.
- `reset_tracking_cache(clear_corrections=False)` clears runtime and persisted
  tracking cache state; correction keyframes are kept unless requested.
- `add_correction_from_mask(mask_uint8, frame_idx)` stores a manual correction.
- `tracking_status()` reports cache/correction/failure counts for UI.
- `tracking_status_text()` formats the same state for editor labels/tooltips.

Mask editor UI:

- `MaskEditorWindow.open_for_node(..., frame_idx=...)` opens the editor for the
  current preview frame.
- Tools: polygon, rectangle GrabCut, click SAM/Auto, foreground brush, and
  background brush.
- GrabCut rectangles are post-refined in `app.node_mask.grabcut_from_rect()`
  to reduce loose rectangular spill on low-contrast scenes; `Clean`, `Shrink`,
  and `Expand` provide quick manual cleanup after auto segmentation.
- Mask edit undo/redo stores both bitmap mask data and polygon points. The
  overlay preview applies current softness/invert settings so the user sees the
  committed feather/invert behavior before pressing OK.
- The Color page Rotoscope dropdown and node graph right-click Add Mask menu
  both include "Track selected region". It routes to
  `VideoEditorWindow._on_node_mask_request(..., "track_region")`, opens the
  mask editor in rectangle mode, and pre-checks `Track object`.
- `Track object` makes the committed `BitmapMask` follow the selected region.
- `Reset track` clears cache/failure state while keeping correction keyframes.
- `Add correction` records the current drawn/selected mask as a drift correction
  at the current frame.
- `Clear keys` clears both correction keyframes and cached tracking state.
- Existing tracked `BitmapMask` settings are restored when editing.
- `TrackRow._paint_tracking_status_overlay()` reads active tracked
  `BitmapMask` instances from `track.node_item_chain` and paints cache,
  failure, and correction counts on the timeline without starting tracking
  work from paint. Failed-frame ticks are approximate 30fps source-frame
  markers for quick visual diagnosis.

Preview render behavior:

- `VideoEditorWindow._rebuild_active_chain()` builds `track.node_item_chain`.
- `ProjectPlayer` evaluates `track.node_item_chain` every frame.
- Export pre-render parity uses the same node/effect application helper:
  preview calls `_apply_node_effect_player()` and `VideoExportThread`
  `_apply_node_chain_cpu()` delegates to that helper for `node_item_chain`.
  Regression tests must keep these two paths byte-equivalent for basic color
  node grades.
- `_apply_node_effect_player()` applies masks to:
  - blur nodes via `BlurParams.apply_with_mask()`
  - effect nodes via `effect_params.apply()` plus masked compositing
  - color nodes via masked `apply_to_rgb()`
- `evaluate_node_masks()` unions enabled masks.

Export behavior:

- `VideoEditorWindow._snapshot_node_item_chain_for_export()` clones live graph
  items into worker-safe snapshots before `VideoExportThread` starts.
- `VideoExportThread._node_chain_needs_prerender()` detects active node graph
  work. If needed, input 0 becomes a raw RGB `pipe:0` stream.
- `_write_prerendered_base_frames()` decodes source frames, applies CPU zoom,
  then runs the same `_apply_node_effect_player()` helper used by preview.
- This path covers active color, blur, effect, and mask nodes, including
  tracked `BitmapMask` evaluation by source frame index.
- `VideoEditorWindow._snapshot_clip_effects_for_export()` clones per-clip
  `VideoFilterParams`, `ChromaKeyParams`, `BackgroundRemovalParams`, and
  `StabilizerParams` into segment-aligned snapshots.
- During raw pre-render, `VideoExportThread` applies clip effects in preview
  order: stabilizer, zoom, node/legacy color, video filters, chroma key, then
  background removal.
- If raw pre-render is used and no external audio tracks are present, export
  adds the original source file as a separate optional audio input so source
  audio is not lost.
- Actor overlays are handled separately: Spine actors are passed as
  `spine_actor_tracks`, and Live2D actors are pre-rendered before export.
  Both are baked into the final FFmpeg output as alpha MOV overlays.
- Developer smoke verification lives in `tools/verify_export_parity.py`. It
  covers synthetic export parity, tracked masked-node export, FFmpeg audio
  separation fallback, and tracked `BitmapMask` serialization.

## Character Asset Hub

Character Asset Hub is the subculture asset intake layer for folders that may
contain Live2D, Spine, MMD, and VRM assets mixed together. It does not replace
Media Pool, the Live2D/Spine editors, MMD Actor Editor, or VTuber Studio; it
normalizes discovery and preflight so those existing workflows can be launched
from a single character-card surface.

Core implementation:

- `app/character_asset_hub.py` is Qt-free and owns the durable report schema
  `tigercapture.character_asset_hub.v1`.
- `scan_character_asset_folder(root)` scans a user-selected folder and returns
  one `tigercapture.character_asset_hub.asset.v1` record per placeable asset.
  The first implementation recognizes `.model3.json` Live2D models, Spine
  `.json`/`.skel`/`.atlas` skeleton candidates, MMD `.pmx`/`.pmd`/`.pbx.json`
  models, nearby `.vmd` motions, and `.vrm` avatars.
- Reports include `kind`, `asset_type`, `display_name`, absolute and relative
  paths, `features`, `missing_files`, `warnings`, `errors`,
  `recommended_transform`, `render`, `thumbnail`, and `timeline_add`.
- Thumbnail generation is deterministic and safe by default:
  `write_character_asset_hub_thumbnails()` writes placeholder SVG thumbnails
  with the asset kind and readiness state. Real render-frame thumbnails can
  replace these later, but renderer failure must never make the Hub card blank.
- `simulate_character_asset_hub_user_flow()` is the headless user simulation:
  it scans a folder and returns the public timeline/avatar action payloads that
  would be invoked when the user presses Add on each ready card.

Editor integration:

- `app/character_asset_hub_window.py` owns the Qt dialog and card list. It is a
  thin visual shell over the Qt-free scanner and must show friendly readiness
  summaries, not raw JSON diagnostics.
- The Media Pool empty-area context menu exposes `Open Character Asset Hub...`.
  It emits `MediaPool.character_asset_hub_requested(folder)` after the user
  chooses a folder.
- `app/video_editor_character_asset_hub_workflow.py` is the editor bridge. It
  opens/reuses the dialog and forwards each card Add request to the registered
  Action Registry. Do not add parallel insertion logic here: Live2D/Spine use
  `actor.add`, MMD uses `mmd.actor.add`, and VRM0 uses
  `vtuber.vseeface_select_vrm0_avatar`.
- The workflow is bound through `app/video_editor_delegates_actor.py` and wired
  from `app/video_editor_ui_left_dock.py`; `app/video_editor_window.py` remains
  a compatibility facade.

Per-format contracts:

- Live2D cards parse `FileReferences` for MOC, textures, motions, expressions,
  physics, and pose. Missing MOC/textures block render readiness; missing
  motions/expressions/physics/pose are recorded as optional missing files.
  Timeline insertion uses `actor.add` with `kind=live2d`.
- Spine cards resolve the loadable skeleton file, matching atlas, atlas texture
  pages, animations, skins, PMA state, and binary version when available.
  Missing atlas or texture pages block render readiness. Timeline insertion
  uses `actor.add` with `kind=spine`, `atlas_path`, first animation, and first
  skin.
- MMD cards recognize PMX/PMD/PBX models and nearby VMD motions. Without
  `render_probe`, they are dependency-ready but unprobed; with `render_probe`,
  the hub can call MMD diagnostics and record parse/render risks. Timeline
  insertion uses `mmd.actor.add` and attaches the nearest VMD motion when one
  is available.
- VRM cards use `app.vtuber.vrm_profile.inspect_vrm_profile()`. VRM0 avatars
  become addable through `vtuber.vseeface_select_vrm0_avatar`; VRM1 or invalid
  VRM files remain visible with diagnostics but are not advertised as
  VSeeFace-ready avatar targets.

Testing:

- `tests/test_character_asset_hub.py` creates a synthetic user folder with
  minimal Live2D, Spine, MMD, and VRM assets, verifies classification,
  missing-file reporting, supported motion/expression/skin summaries,
  recommended transforms, timeline payloads, placeholder thumbnail output, and
  the Qt dialog's card/action emission path.
- `tools/qa_character_asset_hub.py <folder>` writes a regenerated QA report to
  `debugCapture/character_asset_hub_qa.json` and optional placeholder SVG
  thumbnails under `debugCapture/character_asset_hub_thumbnails`.
- This QA intentionally simulates the user at the workflow level: folder drop,
  card generation, and Add-to-Timeline/Add-as-Avatar payload creation. UI mouse
  automation should be a later visual smoke test, not the primary correctness
  proof.

## Character One-Click Templates

Character one-click templates are result-first presets for the subculture
creator workflow. The intended user flow is: put one character folder/model into
Character Asset Hub, press a template, and get an executable timeline/avatar
plan without manually building actor, title, caption, and voice steps.

Core implementation:

- `app/character_one_click_templates.py` is Qt-free and owns
  `tigercapture.character_one_click_template.v1` and
  `tigercapture.character_one_click_plan.v1`.
- The required built-in result templates are:
  `template-character-intro-short`, `template-talking-live2d-short`,
  `template-game-ui-commentary`, `template-gacha-character-showcase`,
  `template-mmd-dance-clip`, `template-anime-pv-intro`,
  `template-meme-reaction-character`, `template-vtuber-announcement`, and
  `template-subtitle-to-voice-dialogue-scene`.
- Five of those are the explicit Character Short starter set and carry the
  `character-short` tag: character intro, talking Live2D short, game UI
  commentary, gacha showcase, and meme reaction.
- Plans always start from the existing Character Asset Hub add contract:
  Live2D/Spine route through `actor.add`, MMD routes through `mmd.actor.add`,
  and VRM0 routes through `vtuber.vseeface_select_vrm0_avatar`.
- Optional decoration steps use existing actions such as `text.add` and
  `tts.subtitle.generate_to_timeline`. If no target video `track_id`/`clip_id`
  is supplied, title/caption decoration steps are marked skipped rather than
  failing the whole template. The required character/avatar step is not optional
  and must fail loudly when the asset is missing or unsupported.
- `app/actions/character_template_namespace.py` exposes registered actions:
  `character.template.list`, `character.template.plan`, and
  `character.template.apply`. The apply action executes only registered Action
  Registry steps; it must not call private editor methods directly.
- `app/character_asset_hub_window.py` adds a `Template` menu to each ready asset
  card. Selecting a template emits `character.template.apply` with the selected
  asset record, so the Hub path uses the same plan as automation and QA.
- The same nine templates are also surfaced as built-in `kind="template"`
  presets in `app/preset_library.py` with `requires_character_asset=true`.
  Generic Workflow Presets can display/search them, while Character Asset Hub
  remains the correct path for applying them to a real asset.

Testing:

- `tests/test_character_one_click_templates.py` verifies the nine required
  templates, the action plan shape, registry exposure, successful Live2D actor
  plus text application against a synthetic owner, and blocked missing-asset
  behavior.
- `tests/test_character_asset_hub.py` verifies the Hub dialog emits
  `character.template.apply` from a card template selection.
- Preset QA expects these templates to appear in `one_click_preset_plan()` for
  character-heavy summaries.

## Live2D

Core files:

- `app/live2d/actor_track.py`: Live2D timeline data model and offscreen render.
- `app/live2d/actor_lane_row.py`: Live2D actor lane UI.
- `app/live2d/live2d_viewer.py`: in-process Live2D editor/viewer.
- `app/live2d/compat.py`: model path normalization and support checks.
- `app/actor_mocap.py`: offline video/webcam-motion helpers that convert
  detected face motion into Live2D actor keyframes and preserve richer
  parameter retarget payloads.
- `app/live2d_motion_storyboard.py`: reads a model's `.motion3.json` entries
  and rebuilds one Live2D actor clip into multiple video-cut-aligned clips so
  authored model motions are used directly instead of only transform mocap.
- `app/project_player.py`: Live2D preview compositing.
- `app/video_exporter.py`: Live2D pre-render for video export.
- `app/project_io.py`: project save/load for `live2d_actor_tracks`.

Behavior notes:

- Live2D clips live on separate actor tracks, not normal video clips.
- Drag/click actions can add Live2D actor clips to the timeline.
- Double-clicking a Live2D clip opens the editor bound to that clip.
- Live2D-only preview playback, including detached preview windows, is expected
  to animate through the same actor-only render path used by export fallback.
- Right-clicking a Live2D actor clip exposes the same actor workflow actions
  users expect from the global Actors menu: video motion mapping and automatic
  authored-motion storyboard, alongside diagnostics/probe/prerender/quarantine
  utilities.
- Live2D and Spine actor lanes use the same 10 px `TimelineRuler` / video-track
  time origin for clip rectangles, drop placement, hit-testing, and playhead
  painting. Actor lane labels may use a wider visual background, but that visual
  label area must never become the timeline coordinate origin.
- Live2D editor construction, including its bottom transport/background swatch
  bar, is covered by regression QA because actor double-click opens this window
  directly from the timeline.
- Export supports Live2D as an overlay on a video-backed project, and also has
  a Live2D-only file-output fallback: if there is no active video source but
  Live2D actor clips exist, export pre-renders those actors and composites them
  over a neutral dark 1920x1080 (or selected export-resolution) background into
  MP4/MOV/WebM.
- Live2D rendering has OpenGL constraints, so export pre-renders Live2D actors on
  the main thread before starting `VideoExportThread`.
- `VideoExportThread.run()` must include each Live2D pre-rendered MOV in the
  FFmpeg `-i` list after typography and Spine MOVs. Overlay specs alone are not
  enough.
- Offline video-to-Live2D mocap is now an MVP actor workflow, not a livestream
  feature: the editor command `Apply Video Motion to Live2D` asks for a local
  video file, uses OpenCV Haar face detection, writes renderable `pos_x`,
  `pos_y`, and `scale` keyframes to the selected/current Live2D clip, and saves
  the source/backend/payload/parameter-keyframe metadata on the clip. The
  renderer now evaluates arbitrary Live2D parameter tracks after the authored
  motion update and before draw, so face/gesture payloads can layer on top of a
  selected `.motion3.json` motion instead of only moving/scaling the actor. The
  baseline OpenCV path emits `ParamAngleX`, `ParamAngleY`, and
  `ParamBodyAngleX`. When the optional local MediaPipe FaceMesh dependency is
  available, the analyzer enriches the same payload with landmark-derived
  `ParamAngleZ`, `ParamEyeBallX`, `ParamEyeBallY`, `ParamMouthOpenY`,
  `ParamMouthForm`, `ParamEyeLOpen`, and `ParamEyeROpen`, so a source performer
  can turn the head one way while the eyes look another way and mouth-open
  values continue to drive talking animation. Future hand/gesture detectors
  should write the same `parameter_keyframes` payload shape for hand and
  expression controls. The default retarget profile is `talking_head_stabilized`: face
  center and face-size tracks pass through deadzone + low-pass smoothing, and
  scale is capped to a subtle range so upper-body speech footage does not make
  the actor look like a camera is dollying forward/backward. Body retargeting is
  deliberately much weaker than face-angle retargeting in this profile; talking
  head footage should keep the character planted and use only subtle
  `ParamBodyAngleX` correction. The mocap payload also classifies framing as
  `face_closeup`, `upper_body`, `full_body`, or the face-only fallback
  `full_body_or_wide`. When OpenCV HOG person boxes are available, upper-body
  footage is identified as a cropped person box or large face-to-body ratio and
  uses a damped transform profile; full-body footage is identified by a person
  box reaching the lower frame with a small face-to-body ratio and keeps normal
  actor translation/zoom. `face_closeup` still locks actor `pos_x`, `pos_y`,
  `scale`, and body-angle transform output so only face parameters move. If the
  person detector fails, the classifier falls back to conservative face-box
  thresholds so speech videos remain planted instead of drifting. If MediaPipe
  is not installed, mouth/eye detail capability is reported as unavailable and
  the clip still receives the OpenCV transform/head fallback. The analyzer now
  also exposes an operator-facing mocap summary: face close-ups are reported as
  transform-locked, upper-body shots as damped, and full-body shots as
  translation/zoom-enabled, with the driven Live2D channels listed so users can
  tell whether the clip is using head angle, eye gaze, mouth, eye-open, and/or
  actor transform keys.
  Because the transform keyframes and parameter tracks are ordinary
  `Live2DActorClip` state, preview and final export bake them through the
  existing Live2D actor pre-render path. After a successful video-mocap apply,
  the editor automatically attempts the same authored-motion storyboard pass
  used by `Auto Storyboard Live2D Motions`; if the model has usable
  `.motion3.json` clips, the single mocap actor is rebuilt into cut-aligned
  motion clips while preserving transform and parameter retargeting. If no
  motions are available, the mocap transform/parameter result remains in place
  without interrupting the user. Real-time webcam driving, hand/body gesture
  detection, production-grade MediaPipe QA, and YouTube/RTMP output remain
  separate future stages. The current output target is a normal video file.
- Live2D can also consume the shared VTuber Performance Source timeline
  contract. The bridge is `app.live2d.performance_source_bridge` with schema
  `tigerstudio.live2d.performance_source_bridge.v1`, and the registered Python
  Action is `actor.live2d.apply_performance_source`. It resolves the active
  input-only Performance Source clip at timeline time, applies mocap parameter
  keyframes when available, maps VTuber source-framing payloads such as
  `tigerstudio.vtuber.source_framing_control.v1` into conservative Live2D
  `pos_x`, `pos_y`, and `scale` keyframes, and stores the original framing
  payload on the Live2D actor clip for roundtrip and diagnostics. Program
  Output must still skip Performance Source video; it is tracking input only.
  The public subject types are `face_only`, `upper_body`, `full_body`, and
  `unknown`: face-only locks actor transform, upper-body damps movement and
  zoom, full-body permits the wider transform range, and unknown uses
  conservative limits when subject guidance exists. VRM source-video visibility
  uses the same public subject vocabulary through
  `tigerstudio.vtuber.source_to_vrm_visibility_policy.v1`: `face_only` maps to
  `bust_up`, `upper_body` maps to at least `half_body`, and `full_body` maps to
  `full_body`. Source-framing plans expose `source_exposure` and
  `visibility_policy` with rule id
  `match_source_person_exposure_to_vrm_visibility`, so AI/review automation can
  explain and enforce the selected VRM framing. The bridge also expands
  canonical Cubism parameter tracks into common aliases via
  `tigerstudio.live2d.parameter_aliases.v1` so models using alternate ids can
  still receive head, body, breath, eye, mouth, and blink control tracks when
  the renderer exposes matching parameters. The current production-tuning pass
  applies separate smoothing for head yaw/pitch/roll, gaze, mouth shape/open,
  and eye-open inputs, adds aggregate `ParamEyeOpen` / `ParamEyeBlink` tracks,
  and emits subtle `ParamBreath`, `ParamBodyAngleY`, and `ParamBodyAngleZ`
  tracks so supported models avoid the "only zooms/scales" look. Basic
  face-box-only footage still reports mouth/eye detail as unavailable; those
  richer tracks are only marked as detail when the source payload actually
  contains gaze, mouth, or eye-open measurements.
- Live2D AI Dialogue Take is the one-shot edited-dialogue workflow for Voice
  Lab and AI actions. The non-mutating plan action
  `tts.dialogue.plan_actor_take` exposes the user-choice surface: existing
  timeline Live2D actor clips, media-pool `.model3.json` assets, available TTS
  models, placement presets, and size presets. The mutating action
  `tts.dialogue.generate_actor_take` accepts those choices through
  `actor_target_id`, `model_name`, `placement_preset`, and `size_preset`; if
  choices are omitted it uses recommended defaults and still completes the
  take. It creates subtitle rows, TTS WAV clips, mouth keyframes, deterministic
  natural blink keyframes, actor placement, and `apply_actor_motion` body keys.
  Unless explicitly disabled, `app.live2d.dialogue_motion` prefers the model's
  authored idle motion and adds deterministic head/body/breath/arm parameter
  tracks so a 30-second generated take does not remain in a static A/T pose.
  The default acting profile uses slower, wider face rotation for speech while
  avoiding rapid side-to-side head-shake motion.
  Placement is not based on an assumed full-body model:
  `app.live2d.dialogue_placement` renders/measures the Live2D frame alpha bounds
  when possible, then fits the visible bbox to the selected safe area such as
  `bottom_right` / `auto_fit` so the visible lower edge touches the bottom of
  the Program Output. The `bottom_right` preset sits close to the right edge for
  normal VTuber-style commentary. If measurement fails, the helper uses deterministic
  fallback coordinates and records diagnostics on
  `Live2DActorClip.dialogue_placement_payload`. The same payload,
  `dialogue_motion_payload`, `tts_lipsync_payload`, and `tts_lipsync_source`
  are project state and must roundtrip through save/load.
- The user entry points keep the original Live2D workflow intact. Dragging a
  Live2D item to the timeline creates a Live2D actor track/clip, and
  double-clicking that clip still opens the Live2D viewer for model, authored
  motion, scale, and placement. VTuber Studio is an avatar-agnostic
  operator/status window, not a replacement editor and not a Live2D-only
  feature: it is opened from the toolbar, Actor menu, Command Palette, or
  selected-actor Workbench card, and shows Program Output, Source Tracking,
  Avatar Mapping, and Studio Controls for VRM/VSeeFace, Live2D, and future
  avatar targets. The selected Live2D Workbench card exposes `Live2D Viewer`,
  `Map Source`, and `VTuber Studio` actions so users can distinguish
  model/motion editing from input-only Performance Source retargeting.
- VTuber Studio uses a shared `Avatar Target` model instead of separate
  Live2D/VRM studio windows. `Avatar Target` can be `VRM / VSeeFace Bridge`, a
  Live2D actor clip, or a future avatar type. The registered Action System
  surface for this shared studio is `vtuber.studio.open`,
  `vtuber.avatar_target.summary`, `vtuber.avatar_target.select`,
  `vtuber.vrm.bridge_status`, and `vtuber.vrm.pose_stream_preview`. VRM /
  VSeeFace targets display avatar path/name, bridge state, capture status,
  current Performance Source, and pose-stream readiness inside the same Studio
  UI. Their route is `Performance Source -> OpenSeeFace -> VMC/pose stream ->
  VRM / VSeeFace Bridge`; they do not use Live2D direct key baking.
  `actor.live2d.apply_performance_source` remains the Live2D-only baking action
  for writing mapping keys to a Live2D actor clip.
- Studio and VRM rendering use the VTuber VRM/MToon renderer boundary
  (`app/vtuber/vrm_renderer.py`, `renderer_family=vtuber_vrm`,
  `render_profile=vrm_mtoon`). `.vrm` Program Output, Avatar Mapping, and
  internal VRM fallback must not route through AR/PBR preview, Marmoset PBR,
  or old debug proof images. The exposed backend is `vrm_mtoon_gpu`; `auto`,
  `mtoon`, `vrm_mtoon`, PBR-looking aliases, and legacy
  `vrm_mtoon_software` requests are rewritten to `vrm_mtoon_gpu`. The legacy
  software VRM renderer is disabled for product/UI/AI-selected routes because
  it can display dense VRM meshes as broken point-like contact previews.
  `vrm_renderer_contract()` and `make_vrm_render_track()` expose
  `software_renderer_available=false`, `legacy_software_renderer_disabled=true`,
  `requested_renderer`, `renderer_rewritten`, and rewrite warnings so AI/action
  surfaces can explain why a requested software/PBR renderer was not used.
- VRM avatars are first-class Media Pool assets, not normal video clips. `.vrm`
  import creates a `VRM Avatar` / `Avatar Target` item with a `VRM` badge.
  Double-clicking it selects `Avatar Target = VRM / VSeeFace Bridge` and opens
  the shared VTuber Studio; the context menu also exposes `Use as Avatar
  Target`, `Open VTuber Studio`, and `Set as VRM / VSeeFace Bridge Avatar`.
  Selection persists `project_settings["vseeface_bridge"]["avatar_vrm"]` and
  `project_settings["vtuber_studio"]["avatar_target_id"] =
  "vrm:vseeface_bridge"`. The VRM file itself is never rendered directly as
  Program Output, and direct `.vrm` drops are routed away from AR/PBR preview
  placement into the same Avatar Target flow.
- The canonical shared VTuber Studio/Broadcast contract is
  `docs/SPEC_VTUBER_STUDIO_BROADCAST.md`. It records the post-split module
  ownership (`VTuberBroadcastStudioWindow` and detached popout UI in
  `app/video_editor_popouts.py`, evidence UI copy/payload helpers in
  `app/broadcast_evidence_ui.py`), the rule that Performance Source media is
  tracking input only, the Program Output/Live Target boundary, session-only
  stream-key handling, and the Broadcast Evidence gate that keeps
  `commercial_ready=false` until real private RTMP ingest and YouTube
  private/unlisted viewer playback evidence are registered. Discord/window-share
  remains an optional extra evidence slot, not a required release blocker. The
  operator-facing checklist is generated by
  `app.broadcast_platform_e2e.build_broadcast_platform_evidence_checklist()`.
  It now exposes `primary_cta`, `why_required`, and `safe_registration_hint`
  for each pending evidence row so VTuber Studio and release QA say the same
  thing: run a private/unlisted RTMP ingest test, then click `Register RTMP`;
  open the private/unlisted YouTube viewer or preview page, then click
  `Register YouTube View`. VTuber Studio also exposes a `Guide` button
  that opens a step-by-step Broadcast Evidence wizard using
  `app.broadcast_evidence_ui.broadcast_evidence_wizard_summary()`: local MP4,
  Live2D MP4, capture/composite, private RTMP, YouTube viewer playback, and
  optional Discord/window-share checks
  are shown in order with Done/Pending state, rationale, safe-evidence hints,
  and direct Register RTMP/Register YouTube View actions. The Studio evidence
  card and guide expose an `Open YouTube Studio`/`YouTube Studio` button that
  opens `https://studio.youtube.com`; it does not store stream keys or account
  data. The guide header shows the YouTube-only path summary and the next
  required CTA before the full step list. The checklist also exposes
  `youtube_only_flow` with required checks
  `private_rtmp_ingest` and `youtube_unlisted_viewer_playback`, plus optional
  `discord_window_share`, so UI/AI/MCP surfaces can explain that a YouTube
  account alone is sufficient for the current commercial broadcast evidence
  gate. Python Actions/MCP also expose
  `broadcast.youtube_evidence_quickstart`, a read-only operator plan containing
  the YouTube Studio URL, the `youtube_live` target id, the two required
  evidence registrations, safe-evidence rules, and the next required CTA.
  `register_manual_platform_evidence()`
  rejects unredacted secret-like fields and common RTMP ingest URLs containing
  stream keys/tokens. After a valid registration it refreshes
  `debugCapture/broadcast_release_readiness_qa.json` and
  `debugCapture/final_product_readiness_qa.json` through
  `app.broadcast_evidence_refresh.refresh_broadcast_evidence_readiness_artifacts()`
  and returns a `readiness_refresh` summary so the UI can say whether the
  broadcast commercial gate or final release gate is now unblocked. Python
  Actions/MCP can run the same refresh explicitly through
  `broadcast.evidence_readiness.refresh`; evidence registration itself remains
  `broadcast.platform_evidence.register`. Automation can call
  `broadcast.platform_evidence.preflight` first to validate the proposed
  redacted note/path without mutating the evidence artifact. Redacted
  notes/screenshots/log paths
  are allowed; stream keys, YouTube watch/preview URLs, signed URLs, tokens,
  account names, private chat, and raw Performance Source frames are not
  allowed evidence. The registration validator rejects common YouTube viewer
  URLs (`youtube.com/watch`, `youtu.be`, `youtube.com/live`) and YouTube Studio
  preview/live URLs so users register only redacted proof, not private share
  links. VTuber Studio registration dialogs and
  `tools/register_broadcast_platform_evidence.py` use the same preflight
  warning text before calling the backend validator.
- Broadcast commercial evidence status, as of 2026-07-10: missing/incomplete.
  This exact status is intentional for spec analyzers. A private YouTube Live
  smoke run proved that TigerCapture can push RTMP Program Output and that a
  VRM frame can appear briefly in YouTube Studio, but that run is not sufficient
  commercial evidence. `private_rtmp_ingest` is only acceptable when registered
  as redacted evidence through `broadcast.platform_evidence.register`, and
  `youtube_unlisted_viewer_playback` remains missing while YouTube Studio/player
  preview buffers or only briefly shows the avatar. Treat ingest health and
  viewer playback as separate evidence states. `commercial_ready` and
  `commercial_claims_ready` must stay false until both
  `private_rtmp_ingest` and `youtube_unlisted_viewer_playback` are registered
  with redacted notes or artifact paths.
- Live2D authored-motion use is separate from transform mocap. The editor
  command `Auto Storyboard Live2D Motions` uses the selected Live2D clip's
  model as the source, reads all available `.motion3.json` motions, then splits
  that Live2D actor into timeline clips aligned to the active video track's
  cut/clip ranges. If there are fewer video ranges than motions, long ranges are
  subdivided so more authored motions can be used at least once; if there are
  more ranges than motions, the motion palette cycles. Transform keyframes and
  Live2D parameter keyframes are sliced into each generated segment, preserving
  mocap retargeting across authored motion changes. This is the current
  practical answer to "change motions by video cut" because `Live2DActorClip`
  still has one `motion_group`/`motion_idx` at a time.

## MMD

Tiger Studio includes an MMD actor path for PMX/PMD models and VMD motions. The
MMD renderer uses the editor `OpenGLPreviewWidget` path and is Toon-only; the
older Marmoset option has been removed. PMX/PMD files appear in the Media Pool
as MMD actors. VMD files are hidden from the general Media Pool and managed
inside the MMD Actor Editor motion library.

Implemented scope:

- PMX/PMD model loading and VMD motion loading.
- IK, morph, append/inherit, SDEF CPU deformation path, and GPU skinning for
  non-SDEF models.
- CPU fallback for SDEF models, with explicit `sdef_cpu_skinning_required`
  diagnostics.
- MMD actor drag/drop, visible timeline rows, double-click editor entry, motion
  apply, lighting, bloom, physics, and material setting persistence.
- ProjectPlayer/export MMD alpha pre-render plus FFmpeg overlay path.
- Local MMD QA corpus manifest, text diagnostics runner, visual OpenGL contact
  sheet runner, editor video-composite/export smoke QA runner, multi-actor
  timeline/export smoke QA runner, segment trim/speed export timing QA runner,
  MMD actor action workflow QA runner, and ownerless automation actions for
  MCP/QA execution.
- Toon ramp, backface outline, self-shadow, contact shadow, MMD-only bloom,
  hemisphere ambient, skin highlight clamp/warm tint/wrap diffuse, eye/lip/
  stocking/metal/emissive/transparent material branches.
- ZZZ-style face detail, eye/brow/lash/mouth outline suppression, hair/
  accessory outline suppression, transparent front/internal hair ordering, and
  alpha-gradient handling.
- Lightweight spring physics and optional PyBullet physics. PyBullet creates
  PMX sphere/box/capsule collision bodies, applies MMD Y-axis capsule-frame
  correction, group/mask filters, static anchors, body-local point constraints,
  joint-local linear/angular limit and spring approximations, and secondary
  bone rotation hints from rigid-body orientation feedback.
- PyBullet solver tuning is explicit: deterministic overlapping pairs,
  model-scaled solver iterations, fixed timestep, contact/joint/friction ERP,
  and PMX spring/mass-based max-force diagnostics.

Current focused MMD test suite is `tests/test_mmd_schema.py`,
`tests/test_mmd_pmx.py`, and `tests/test_mmd_editor_integration.py`; latest
handoff state records `80 passed`. The local MMD QA corpus lives at
`local_resources/mmd/qa_corpus_manifest.json`; `tools/mmd_qa_corpus.py` runs
the reusable `app.mmd.qa_corpus.run_mmd_qa_manifest` text diagnostics, and
`tools/mmd_qa_visual_corpus.py` renders offscreen OpenGL PNGs plus
`debugCapture/mmd_player/qa_corpus_visual/mmd_qa_visual_contact_sheet.png`.
`tools/qa_mmd_editor_composite.py` builds a synthetic video timeline, renders
MMD preview RGBA, pre-renders the MMD alpha MOV, exports an MP4 overlay, and
checks that MMD pixels affect the actor region without contaminating the rest
of the video. `tools/qa_mmd_multi_actor_timeline.py` adds two MMD actor tracks
with staggered start/end ranges and a motion offset, then samples
none/single/overlap/single/none frames through preview, alpha pre-render, and
final MP4 export. `tools/qa_mmd_segment_timing.py` verifies that MMD alpha
pre-render and final MP4 export keep actor timing aligned across trimmed source
starts, skipped source gaps, and 2x speed segments. `tools/qa_mmd_render_queue_wiring.py`
verifies that the batch/render-queue export factory forwards trimmed/speed
segments, MMD tracks, and the MMD pre-rendered alpha overlay into
`VideoExportThread`. `tools/qa_mmd_render_queue_export.py` runs that factory
with the real exporter, writes baseline/MMD MP4 outputs, and checks two
simultaneous MMD actor regions against a preview overlay sample.
`tools/qa_mmd_long_project_export.py` runs a 10s synthetic source through the
real render-queue factory, preserves five trimmed/speed segments, uses two
simultaneous MMD actors, and samples the final MP4 against preview overlays.
`tools/qa_mmd_actor_workflow.py`
verifies the action-level user flow: add an actor, add an external VMD to the
actor motion library, apply the motion, persist physics/render/material
settings, move/trim/duplicate, and delete with destructive confirmation. The
registered ownerless, non-mutating QA actions are `mmd.qa.run`,
`mmd.qa.visual_run`, `mmd.qa.composite_run`, `mmd.qa.timeline_run`,
`mmd.qa.segment_run`, `mmd.qa.render_queue_run`,
`mmd.qa.render_queue_export_run`, `mmd.qa.long_project_run`, and
`mmd.qa.workflow_run`. Material diagnostics include
missing texture row/path details through
`missing_texture_rows` and `missing_texture_paths`. Latest
PyBullet smoke capture is
`debugCapture/mmd_player/regression/cantarella_wavefile_pybullet.png` with the
matching JSON diagnostics. The smoke profile reports `backend=pybullet`,
`bodies=415`, `shapes=415`, `spheres=3`, `boxes=223`, `capsules=189`,
`capsule_axis_fixes=189`, `constraints=574`, `joint_frame_constraints=574`,
`solver_iterations=56`, `constraint_force_avg=44.41`,
`constraint_force_max=260.0`, `orientation_feedback=378`, and
`profile_ok=true`.
2026-07-10 stabilization QA reran the text corpus, editor composite/export,
and multi-actor timeline/export paths. The working-sample evidence is
`debugCapture/actor_working_samples_stabilization.json`: MMD preview/export
passed for the `cantarella_wavefile_cloth_motion` path, both the single
editor-composite and multi-actor timeline QA reports passed all six checks, and
the MMD corpus reported 9 runnable entries. `vivian_full_body_pmx` remains a
blocked corpus entry because its local bundle is incomplete, not because the
renderer should silently accept the missing sphere texture.

Current release posture:

- Do not expand MMD scope speculatively. Local synthetic QA covers preview,
  video composite, multi-actor timing, segment timing, render queue export,
  and long-project export. Further MMD work should only open for native
  MMD/Bullet reference captures or a concrete failing user asset/project.
- SDEF visual validation is covered by the external local-bundle
  `tda_onepiece_sdef_validation` PMX at `E:/ClaudeCodeApp/mmd`. It reports
  4,602 SDEF vertices and renders through the expected CPU fallback path.
- Per-model collision, constraint, material, or motion exceptions should be
  added only when a real broken model requires them.

See `docs/mmd_player_handoff.md` and `docs/MMD_TODO.md` for the active handoff
and MMD backlog.

## Spine and NIKKE

Core files:

- `app/spine_editor/spine_json_parser.py`: Spine JSON and binary `.skel` parser.
- `app/spine_editor/spine_data.py`: skeleton, bones, slots, skins, animations.
- `app/spine_editor/spine_gl_renderer.py`: interactive OpenGL Spine viewport.
- `app/spine_editor/spine_offscreen_gl_renderer.py`: timeline/export renderer.
- `app/spine_editor/editor_window.py`: Spine editor window and model loading.
- `app/spine_editor/actor_track.py`: Spine actor track/clip data model.
- `app/spine_editor/actor_lane_row.py`: Spine actor lane UI.
- `app/project_player.py`: Spine preview compositing.
- `app/video_exporter.py`: Spine actor pre-render overlays.
- `app/project_io.py`: project save/load for `spine_actor_tracks`.

Behavior notes:

- NIKKE uses Spine-formatted assets. Treat NIKKE problems as Spine parser,
  atlas, mesh, blend, slot-order, or animation issues.
- `tools/actor_compat_matrix.py` is the fast local model-corpus preflight for
  Live2D/Spine compatibility. It scans roots for Spine `.skel`/JSON and
  Live2D `.model3.json`, checks atlas/model dependencies, reports missing
  assets, and can optionally run the Spine parser before slower render QA.
  Reports include per-row severity, issue codes, dependency counts, missing
  dependency kinds, family grouping, recommendations, issue-count summaries,
  and top failures. Reports also classify passing-but-risky stress samples with
  `feature_flags`, `risk_codes`, `risk_severity`, `risk_score`, and
  `stress_tier`. Spine risk coverage includes 4.2+ assets, binary version
  unknowns, weighted/linked mesh, clipping, constraints, multi-page atlas,
  multi-skin rigs, high bone/slot counts, events, and static/no-animation
  assets. Live2D risk coverage includes many texture pages, large motion sets,
  non-ASCII runtime paths, physics, pose, display info, user data, expressions,
  and hit areas. Summary output aggregates `risk_counts`, `feature_counts`,
  `stress_tiers`, and `top_risks` so hundreds of models can be triaged by risk
  class instead of only pass/fail. The stress threshold is calibrated so
  NIKKE-style Spine rigs with weighted mesh + constraints + multi-page atlas
  coverage enter `stress` even when each individual dependency passes.
  `--known-failures` accepts the same
  quarantine JSON used by render QA; matching failed rows become
  `quarantined` instead of counted as hard failures while still appearing with
  the attached `known_failure` reason. `--summary-only` keeps large corpus runs readable, and
  `--limit` now short-circuits discovery instead of scanning the full corpus
  first.
- `tools/actor_render_qa.py` is the combined large-corpus render QA entry
  point. It runs `actor_compat_matrix` first, then reuses
  `tools/test_spine_resources.py` for Spine render/nonblank validation and
  `tools/test_live2d_resources.py` for per-model Live2D child-process render
  checks. Live2D render QA is UTF-8 safe for non-ASCII model paths and records
  alpha-bbox nonblank status. It must render the normalized ASCII-safe runtime
  model path, not the original source path, because non-ASCII/Unity-style
  source packages can pass dependency QA but fail or render blank when handed
  directly to the Live2D runtime. The combined report separates compatibility
  failures from render failures so missing assets, blank actor output, Live2D
  crashes, and raw Unity/bundle inputs are triaged independently with
  recommendations. Its summary promotes compatibility stress metrics under
  `compatibility_risk`, carrying risk counts, feature counts, stress tiers, and
  top-risk models into the combined render report. `--render-top-risks` adds
  the highest-risk passing compatibility rows to the render set, and
  `--animation-sweep` records per-animation sample counts, blank frames, bbox
  bounds, center-jump diagnostics, Spine skin/slot attachment summaries, and
  Spine mix-and-match skin-combination samples from the render helpers.
  Live2D motion and expression variants are actually rendered through
  `Live2DActorClip.expression_id`; physics, pose, display-info, user-data, and
  hit-area references are recorded as metadata coverage until those runtime
  controls become first-class clip fields.
  `--golden-dir` enables first-nonblank image regression checks, with
  `--update-golden` used only when intentionally accepting new baselines.
  `--known-failures` quarantines expected compatibility/render failures; the
  default local allowlist is `qa_corpus/actor_known_failures.json`.
  Render summaries include `failure_categories` and per-result `quality`
  taxonomy, so base-frame blank output, runtime crashes, timeouts,
  animation-sweep blanks, and golden mismatches are separated instead of
  collapsing into generic failure rows.
  With `--baseline`, it also reports compatibility and render
  regressions against a previous corpus run so large Live2D/Spine packs can be
  re-tested without manually comparing JSON files.
- `tools/test_live2d_resources.py` marks child-process JSON with a
  `__TIGERCAPTURE_LIVE2D_RESULT__` sentinel. The Live2D native runtime can
  write long motion-load logs without a newline, so QA parsers must find the
  result JSON even when it appears in the middle of a native log line. Per-model
  child-process timeouts are reported as `timeout` rows with stdout/stderr tails
  instead of aborting the full corpus run.
- In the Live2D compatibility matrix, MOC and texture references are render
  required. Missing expressions, physics, display info, user data, or motions
  stay visible in `missing_dependencies` and issue summaries, but are warnings
  rather than base-render failures because a model can still render nonblank
  without them.
- `spine_json_parser.py` includes a NIKKE raw-hash header fallback for some
  binary `.skel` exports.
- The editor, compatibility matrix, and render QA prefer JSON when a same-stem
  JSON export exists beside binary `.skel`, because JSON is easier to inspect,
  usually more complete, and can keep QA useful for Spine 4.2 binary samples
  that the current binary parser does not support yet.
- The installed local actor corpus was last validated without limits on
  2026-06-16: 199 total models passed compatibility and render QA, including
  160 Spine models and 39 Live2D models.
- The stress/known-failure compatibility path was validated on 2026-06-17:
  200 local actor resources scanned, 199 passed, 1 synthetic missing-atlas
  parser fixture quarantined, and 0 hard compatibility failures. A top-risk
  render-sweep smoke run rendered the highest-risk Spine sample and recorded
  animation-sweep diagnostics in the saved report.
- The actor corpus was recalibrated and fully golden-seeded on 2026-06-17:
  200 local actor resources scanned, stress-tier coverage rose to 10 models,
  no coverage issues remained, and 40 top-risk Live2D/Spine render baselines
  were created under `qa_corpus/actor_golden`.
- 2026-07-14 Unity AssetBundle compatibility probe status is
  `dependency_compatibility_verified`; this is dependency feasibility evidence,
  not a claim that raw AssetBundle import is already a product feature.
  The compatibility review gate is `PASS_SCOPED` with
  `blocking_compatibility_issue=false`: extracted Spine runtime assets are a
  supported, corpus-tested input, and standard AssetBundle reader feasibility
  is verified. Raw AssetBundle import remains an unclaimed integration item,
  not a blocking defect in the documented product scope.
  `UnityPy 1.25.2` was downloaded into the isolated local tool directory
  `external/tools/unitypy_compat` and exercised with the Tiger Studio Python
  3.13.2 runtime. It loaded the real 30,952,617-byte VSeeFace
  `data.unity3d` bundle in 0.155 seconds, enumerated 12,996 objects including
  5 `TextAsset` and 134 `Texture2D` objects, and reported zero parse errors.
  A 166,819-byte NIKKE `bba001_00.skel` payload was round-tripped through a
  Unity `TextAsset`; the source and recovered SHA-256 were both
  `3fa1b30d05f3236e0d2866715d87f060e95550d716b80e15bcb8d1e079539eba`.
  The installed extracted-runtime corpus also contains 157 Unity-game-style
  Spine models: 148 NIKKE, 6 Arknights, and 3 Blue Archive samples.
  Review interpretation: standard Unity bundle object extraction and binary
  Spine payload preservation are verified and should not be reported as an
  unknown compatibility gap. End-to-end discovery/pairing of
  `.skel`/`.atlas`/`Texture2D` from a raw Spine-containing AssetBundle is not
  integrated or verified yet; encrypted/custom bundles and universal
  Unity/game-export compatibility are not claimed.
- 2026-07-10 stabilization render QA writes
  `debugCapture/actor_render_qa_stabilization.json` and
  `debugCapture/actor_working_samples_stabilization.json`. In that run,
  compatibility passed for 99 scanned actor resources, 16 Spine samples passed
  standalone nonblank render QA, and 16 sampled Live2D resources returned
  `render_none`. Until that Live2D runtime issue is fixed, Live2D assets from
  this run are compatibility-passing but must not be listed as render-proven
  working samples.
- Live2D/Spine editor loading is productized as a staged operation, not a
  blocking black box. `app.actor_compat_repair` performs non-destructive path
  repair and dependency diagnostics; `app.actor_loading_cache` records queued,
  file_check, repair, compat, parse, textures, first_frame, ready/error/timeout
  stages with progress percentages; `app.actor_process_probe` and
  `tools/actor_isolated_probe.py` run one-frame child-process probes; and
  `app.actor_prerender_cache` can save short PNG preview sequences for faster
  future diagnostics. The Live2D and Spine editors write these records while
  showing determinate progress/cancel/retry UI, and `app.actor_loading_manager`
  exposes the cache and loading QA from the Command Palette. Crash reports now
  include `actor_context`, and `tools/qa_actor_overnight.py` plans or runs
  large isolated actor render sweeps for long compatibility sessions.
- Actor loading diagnostics are wired into editing surfaces. `ProjectPlayer`
  checks exact-size prerender cache frames for safe default-transform
  Live2D/Spine clips before using live render fallback; actor timeline context
  menus can show recent loading status, run isolated probes, generate prerender
  cache, quarantine known failures, and open source folders; and the startup
  crash dialog displays actor context when the latest crash happened around
  Live2D/Spine open/load/drop breadcrumbs. Screen Studio-style preset coverage
  now includes cursor scissor/zoom/drag animated-icon stickers, wallpaper
  palette effects, and blade/palette template packs.
- 2026-07-10 stabilization note: Live2D/Spine/MMD load failures must show a
  diagnostic card instead of a black viewport, silent crash, or raw JSON dump.
  `app.actor_loading_status.actor_loading_diagnostic_card()` emits
  `tigercapture.actor.loading_diagnostic_card.v1` cards with title, summary,
  blockers, next actions, and metadata; `app.actor_loading_cache` persists the
  card on load records; `ActorLoadingManager` displays the formatted card
  before technical details; MMD player load exceptions record the same card;
  and actor evidence cards paint the diagnosis for failed Live2D clips. The
  fallback policy is to keep the editor responsive and make recovery visible.
- Actor compatibility repair now has a user-facing guidance report:
  `app.actor_compat_repair.actor_repair_guidance_report()` maps missing atlas
  pages, missing Live2D model files, unsupported formats, optional MediaPipe
  status, corpus status rows, issue codes, and risk codes into actionable
  repair steps plus release-claim blockers. This keeps Live2D/Spine positioned
  as a strong differentiator with corpus QA, not as a promise that every
  Unity/game-exported rig will load.
- Spine actor clips are composited in preview by `ProjectPlayer` and exported by
  pre-rendering transparent overlays.
- Spine export uses `_prepare_spine_actor_overlays()` to bake each clip to a
  ProRes 4444 alpha MOV, then includes that MOV as an FFmpeg overlay input.

## Sound Editor and Audio Tracks

Core files:

- `app/audio_tracks.py`: audio data model, waveform extraction, preview mixer,
  FFmpeg audio export filters, single-clip export.
- `app/audio_workflow.py`: dialogue-cleanup presets, loudness targets, bus
  specs, clip-gain helpers, and one-click audio plan helpers.
- `app/audio_accuracy.py`: Qt-free reference diagnostics for approximate
  integrated LUFS, true peak, stereo correlation, and audio warning checks.
- `app/audio_separation.py`: vocal/instrumental source separation worker.
- `app/sound_editor_panel.py`: renewed compact Sound Editor surface for the
  Workbench audio state and detached timeline-editor shell. It owns
  `SoundEditStateStore`, `SoundEditorPanel`, `SoundEditorDockWindow`, and the
  Workbench Sound Editor Mixer tab channel strips.
- `app/video_editor_window.py`: `SoundEditorWindow`, `ClipWaveformView`,
  `SpectrumView`, timeline audio rows, audio track insertion, and the legacy
  Advanced Lab entry point.
- `app/audio_mixer_panel.py`: mixer strip UI with volume, pan, VU, scopes.
- `app/project_io.py`: project save/load for audio tracks and clips.
- `app/controller.py`: standalone Sound Editor launch path.

Data model:

- `AudioTrack` is a timeline lane. It owns clips and carries track-level volume,
  pan, mute, solo, label, `bus_id`, and normalized `automation_points`.
- `AudioClip` references a source file and stores offset, trim range, cuts,
  fades, selection, waveform/spectrum cache, gain, and sound-editor effects.
- Splitting an audio clip creates multiple `AudioClip` objects on the same
  `AudioTrack`; it does not create new tracks.

Preview and export:

- Preview playback uses `AudioMixer`, with one `QMediaPlayer` per live clip.
- Qt preview supports timing and volume but not true per-channel pan; pan is
  applied in FFmpeg export via `apan`.
- Track mute/solo are real mix state. They affect preview volume, FFmpeg export
  filtering, project save/load, undo snapshots, AI snapshots, and the timeline
  Audio Mixer UI.
- Track automation is exported as a frame-evaluated FFmpeg `volume` expression.
- Waveforms are extracted asynchronously by `WaveformExtractor`, using FFmpeg
  through `QProcess`.
- Waveform and spectrum analysis results are cached by `(path, mtime, size)`
  through helpers in `app/audio_tracks.py`; duplicate in-flight jobs for the
  same source file are joined by `VideoEditorWindow`.
- Single-clip Sound Editor export uses `ClipExporter` and
  `build_single_clip_filter()`.
- Timeline video export passes loaded `AudioTrack` lanes into
  `VideoExportThread`, which builds a larger FFmpeg audio mix.
- Audio Mixer LUFS display and Color/Audio accuracy QA share
  `audio_accuracy.integrated_lufs_approx()` so the UI meter and scripted
  diagnostics do not drift by using different reference math.

Sound Editor UI:

- The default in-editor Sound Editor surface is the renewed embedded
  `SoundEditorPanel` inside the Workbench Audio tab. It is also wrapped by
  `SoundEditorDockWindow` when a timeline audio clip opens a detached editor.
- The renewed panel has no Load workflow. Its target is either the selected
  Media Pool audio source or the selected Timeline audio clip.
- `SoundEditStateStore` keeps Media Pool audio edits separate from Timeline
  clip edits by keying Media Pool state by resolved source path. Timeline clips
  continue to carry their edit data directly on `AudioClip`.
- The compact panel uses waveform and spectrum/level strips, icon tabs, chain
  chips, shared `StudioSlider` controls, and interactive EQ/Dynamics/FX/
  AI Master mini graphs.
- EQ/Dynamics/FX/AI graph handles are functional edit controls. Dragging them
  updates the matching slider and real `AudioClip.effects` state; double-click
  resets handles to their defaults.
- EQ/Dynamics/Effects/Advanced/AI Master, dialogue cleanup, and loudness state
  are stored in `AudioClip.effects`.
- AI Master is macro mastering for AI-generated music and renders via FFmpeg
  filters on export.
- The legacy `SoundEditorWindow` remains available as an Advanced Lab and as
  the standalone Sound Editor launch path. It owns the heavier waveform/
  spectrum/marker/stem-separation/export workflow and should not be treated as
  the normal compact Workbench surface.
- The AI Master tab also exposes professional audio presets from
  `app.preset_library` for dialogue cleanup, loudness delivery, and music
  mastering. Applying one mutates `AudioClip.effects` and, when the clip is
  timeline-bound, labels/routes the owning `AudioTrack` to a dialogue or music
  bus.
- Audio Mixer uses the shared UX empty-state copy when no tracks are loaded,
  and names its mixer header by actual track count so empty/progress/failure
  polish is visible before playback starts.
- Dialogue cleanup renders through stable FFmpeg filters: high-pass,
  `afftdn`, hum notch EQ, presence/air EQ, light tail control, de-essing, and
  `dynaudnorm`. Loudness targets render through `loudnorm`.

Vocal/music separation:

- UI entry: legacy Advanced Lab / `SoundEditorWindow` AI Master tab,
  "Vocal / Music Separation" section. The compact Workbench panel links to the
  Advanced Lab for this heavier workflow instead of embedding source separation
  directly.
- Worker: `AudioSeparationWorker` in `app/audio_separation.py`.
- `planned_separation_method(prefer_demucs=True)` reports whether a run will
  try Demucs or the FFmpeg mid/side fallback.
- `validate_audio_source()` rejects missing, non-file, or empty sources before
  starting expensive separation work.
- The UI exposes an `Auto` / `Fast fallback` backend selector. Auto uses Demucs
  when installed; Fast fallback forces FFmpeg mid/side.
- `AudioSeparationWorker.cancel()` terminates the active Demucs/FFmpeg
  subprocess and emits `cancelled`.
- High-quality path: if the current Python environment has `demucs`, the worker
  runs `python -m demucs --two-stems=vocals`.
- Fallback path: FFmpeg mid/side extraction. This is fast and local but
  approximate; it works best when vocals are centered in a stereo mix.
- Outputs: `<source>_vocals.wav` and `<source>_instrumental.wav` under a
  `<source>_stems` folder in the user-selected output root.
- When `SoundEditorWindow` has a video-editor parent, separated stems are added
  as two new `AudioTrack` lanes. The new clips copy the original clip's
  timeline offset, trim, cuts, and fades, but start with neutral effects.
- Standalone Sound Editor mode has no timeline parent, so it only writes files
  and shows their paths.

## Performance Hotspots

- `app/perf_monitor.py` provides opt-in slow-call logging. Set
  `TIGERCAPTURE_PERF=1` and optionally `TIGERCAPTURE_PERF_SLOW_MS=<ms>` to log
  slow preview tick/seek/refresh renders from `ProjectPlayer`.
- `ProjectPlayer._render_frame_at()` also logs stage timings when performance
  logging is enabled. Use `TIGERCAPTURE_PERF_STAGE_MS=<ms>` to change the
  per-stage threshold. Stage labels include decode, frame_blend, stabilizer,
  zoom, node_effect, legacy_mask_grade, video_filters, chroma_key,
  background_removal, transition, PIP, Spine, Live2D, final_grade, emit_gpu,
  and qimage. The qimage stage is skipped in the auto GPU-preview path when no
  CPU-image consumer is active.
- `app/media_pool.py` caches duration probes and first-frame thumbnails by
  `(path, mtime, size)` so repeated media-pool loads do not repeatedly decode
  the same first frame.
- `app/audio_tracks.py` caches waveform and spectrum analysis results by
  `(path, mtime, size)`; `VideoEditorWindow` joins duplicate in-flight jobs.
- `app/video_decoder.py::open_decoder()` wraps full decoder implementations in
  `PrefetchDecoder` for background preview reads. Lightweight test or alternate
  decoder stubs that do not expose the full decoder interface are returned
  directly. Existing fresh sibling proxies at `proxies/<stem>_proxy.mp4` are
  used automatically for preview decode unless
  `TIGERCAPTURE_DISABLE_AUTO_PROXY=1` is set. `TIGERCAPTURE_PREVIEW_HEIGHT`
  can override the preview-buffer downscale height; otherwise 4K sources use a
  540p preview buffer and other sources default to 720p. Prefetch buffers store
  frame indices with frames, allowing small seeks into the hot buffer. Explicit
  seeks to the next sequential OpenCV frame skip the expensive
  `CAP_PROP_POS_FRAMES` call.
  `TIGERCAPTURE_PREFETCH_FRAMES` and
  `TIGERCAPTURE_PREFETCH_READ_TIMEOUT` tune the internal preview frame-server
  buffer and main-thread wait budget without changing project files.
  `TIGERCAPTURE_PREFETCH_FORWARD_SEEK_WINDOW` and
  `TIGERCAPTURE_CV2_FORWARD_SEEK_WINDOW` can opt into satisfying small forward
  seeks by continuing sequential decode instead of repositioning; both default
  to `0` because local QA on the current 720p corpus showed discarding 10-40
  frames was slower than OpenCV random seek. OpenCV
  FFMPEG decode can attempt hardware acceleration as open parameters when
  `TIGERCAPTURE_ENABLE_HW_DECODE=1` is set; this is opt-in because local QA
  showed OpenCV HW decode can report active acceleration while being slower
  than software decode. Set `TIGERCAPTURE_DISABLE_HW_DECODE=1` to force
  software decode or `TIGERCAPTURE_HW_DEVICE=<index>` to request a specific
  device when OpenCV exposes `CAP_PROP_HW_DEVICE`. A process-level FFmpeg RGB
  pipe frame server is available with `TIGERCAPTURE_PREVIEW_FRAME_SERVER=1`;
  keep it opt-in because local random-seek QA on the 720p corpus was slower
  than OpenCV prefetch/cache. Set `TIGERCAPTURE_PREVIEW_DECODER_AUTO=1` or
  `TIGERCAPTURE_PREVIEW_FRAME_SERVER=auto` to benchmark OpenCV vs the FFmpeg
  frame server for each source/proxy/preview-height tuple. The result is cached
  under `~/Videos/TigerCapture/.cache/decoder_choices.json`, and the auto path
  only chooses the FFmpeg frame server when it beats OpenCV by the configured
  margin (`TIGERCAPTURE_PREVIEW_DECODER_AUTO_MARGIN`, default `0.85`). When the
  frame-server or auto path is opened without an explicit preview height, it now
  receives the same monitoring-scale hint used by preview decode (720p by
  default, overridden by `TIGERCAPTURE_PREVIEW_HEIGHT`) before benchmarking or
  spawning FFmpeg, so opt-in comparisons do not accidentally decode full-source
  frames. `ProjectPlayer` also passes an explicit per-project
  `preview_decode_height` / `preview.preview_height` style setting through to
  the decoder factory when present; absent that setting, the decoder keeps its
  source-aware 4K/720p defaults.
- 4K/60-style preview resilience is policy-driven through
  `app.preview_performance_policy`. Preview quality modes are `auto`,
  `performance`, and `quality`: Auto keeps source-aware monitoring scale,
  Performance caps monitoring decode at 540p when no explicit height is set,
  and Quality requests original-size preview frames. Auto/Performance allow
  playback frame dropping so project time follows audio/wall-clock time instead
  of slowing the audio path; Quality disables this catch-up behavior. The
  current playback mode, decode height, and dropped-frame counter are exposed by
  `ProjectPlayer.preview_playback_diagnostics()`.
- Importing high-resolution/high-FPS sources queues background proxy generation
  through `app.video_editor_proxy_controller.queue_auto_proxy_generation()` when
  `app.preview_performance_policy` marks the source as `needs_proxy`. The
  existing toolbar and Media Pool states continue to report Original/Building/
  Ready/Stale/Active, and export keeps using the original source media.
- `OpenGLPreviewWidget.preview_gl_diagnostics()` reports frame size, upload
  count, latest texture-upload time, and latest paint time. Slow or periodic
  texture uploads are also recorded as `preview.gl/texture_upload` rows in
  `app.loading_performance`, making it possible to separate decode stalls from
  GPU upload/paint stalls during 4K60 QA.
- Preview playback is mostly Python/NumPy/OpenCV plus some OpenGL paths. Heavy
  masks, full-res previews, Live2D, and Spine overlays can make playback slow.
- Spine actor preview renders use the GL/offscreen renderer when available and
  the half-resolution software fast-mesh path as fallback
  (`TIGERCAPTURE_SPINE_PREVIEW_SCALE`, default `0.5`). Actor tracks prewarm up
  to 8 actor clip renderers when attached to the player. Per-clip preview
  layout is cached, animated-frame cache size defaults to 72
  (`TIGERCAPTURE_SPINE_PREVIEW_CACHE_LIMIT`), animated preview time is cached
  at 24fps by default (`TIGERCAPTURE_SPINE_PREVIEW_FPS`, `0` disables it), and
  composited Spine overlay images/RGBA arrays are cached in `ProjectPlayer`
  (`TIGERCAPTURE_SPINE_OVERLAY_CACHE_LIMIT`). Complex Spine rigs use a lower
  adaptive overlay cache/readback cadence by default:
  `TIGERCAPTURE_SPINE_COMPLEX_THRESHOLD=900` and
  `TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_FPS=12`. This reduces repeated FBO
  readbacks for single complex actor clips without changing full-quality
  export. CPU fallback Spine preview now uses
  `TIGERCAPTURE_SPINE_PLAYBACK_PREVIEW_SCALE` (default `0.375`) for animated
  playback, then lowers further to `TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_SCALE`
  (default `0.25`) when a complex Spine rig is active or when strict CPU
  compositor fallback is forced. Paused/editor frames keep the normal preview scale so
  placement and scale adjustments stay readable. Export keeps using the
  full-quality actor render path. The GL viewport/offscreen path batches consecutive meshes sharing
  the same atlas texture before issuing `glDrawArrays`, reducing draw-call
  churn for complex rigs. An experimental direct RGBA ndarray compositor is
  available with
  `TIGERCAPTURE_SPINE_ARRAY_COMPOSITOR=1`; local QA showed its blend kernel is
  faster but the current FBO readback path can still make it slower overall, so
  the default remains the previously measured PIL compositor. A shared
  `SpineOverlayGLCompositor` is now attempted by default for preview overlays:
  it can draw multiple active Spine clips into one offscreen FBO and read back
  once, then falls back to the older per-clip renderer if unavailable. For the
  main editor GL preview, `TIGERCAPTURE_SPINE_ZERO_READBACK=1` is now the
  default: when QImage/final-CPU consumers are inactive, `ProjectPlayer` sends Spine
  `preview_render_state` metadata with `gpu_frame_ready` and
  `OpenGLPreviewWidget` draws the actor meshes directly into the letterboxed
  preview viewport. This skips CPU overlay pixels and FBO readback for that
  frame. `TIGERCAPTURE_SPINE_DIRECT_WITH_LIVE2D=1` is also default, allowing
  Spine direct-GL preview even when top-level Live2D is active; set it to `0`
  for strict CPU-composited actor layer-order debugging. If the direct Spine
  shader/context path fails, the preview widget
  emits a failure signal and `VideoEditorWindow` disables the direct path,
  refreshes the frame, and falls back to CPU compositing. Export keeps the
  full-quality Spine render path. Direct overlay states are cached by quantized
  preview time, output size, and clip signature, so repeated paints for the same
  frame do not rebuild Spine actor state.
- AR/PBR preview/export uses a hybrid renderer. CPU `software_pbr` still
  projects imported FBX/GLB descriptor triangles, applies material
  color/roughness/metallic/reflectance controls, depth occlusion, shadow
  catcher, and reflection catcher masks for QImage fallback consumers and as a
  final export fallback. For the main OpenGL editor preview, AR/PBR GPU preview
  is enabled by default unless `TIGERCAPTURE_AR_PBR_GPU_PREVIEW=0`, `cpu`, or
  `software` is set. When QImage/final-CPU consumers are inactive,
  `ProjectPlayer` builds
  `ar_pbr_items` via `app.ar_pbr.gpu_preview.build_gpu_preview_items()` and
  sends them through `gpu_frame_ready`; `OpenGLPreviewWidget` draws
  `shadow_vertices`, `reflection_vertices`, then mesh `vertices` directly over
  the letterboxed video texture. When geometry has UVs and resolved material
  maps, the same packet also carries `pbr_triangles` with projected
  position, UV, normal, tangent, bitangent, base color, material
  roughness/metallic/reflectance values, base/roughness/metallic/specular/
  normal/occlusion map metadata, packed channel selectors, live depth texture
  metadata, and HDRI lighting metadata; the GL preview draws those with a
  model-view-style material-map PBR fragment shader over the color-packet
  fallback. Export now
  uses the same GPU-preview packet
  builder through `app.ar_pbr.export_packet_renderer` as the deterministic
  fallback (`TIGERCAPTURE_AR_PBR_EXPORT_RENDERER=packet`; set `software` for
  the old compositor fallback). Export defaults to the worker-safe full GPU
  helper first and falls back to packet PBR on helper failure. The GPU packet
  builder resolves road-plane, plane,
  screen-plane, and scene-anchor placement before projection, matching fallback
  attachment semantics. The packet path currently uses shaded color triangles,
  GL model-view-style material-map PBR triangles, screen-space mesh silhouette
  contact shadows, mirrored mesh reflection catchers, and lightweight fallback
  catcher layers rather than the full model-view PBR renderer.
  `app.ar_pbr.texture_plan` is shared by the model-view loader and the packet
  path; it reports `ready`, `missing`, `referenced`, or `none` texture-map
  states and supplies cached base-map average colors for fallback packet tint.
  The packet builder also emits per-triangle UV/base texture packets when
  geometry UVs exist; headless export samples those packets with affine texture
  mapping, then consumes `pbr_triangles` with a headless PBR rasterizer that
  samples base, roughness, metallic, specular, normal, and occlusion maps. When an HDRI is
  available, export samples the environment by normal and reflection direction
  for diffuse/specular IBL instead of using only a flat average color, builds
  cached downsampled HDRI prefilter levels, and samples roughness-selected mip
  levels for specular IBL. The export diagnostics expose
  `pbr_hdri_directional_sampling`, `pbr_hdri_sampled_pixels`,
  `pbr_prefiltered_ibl`, `pbr_prefiltered_ibl_level_count`, and
  `pbr_prefiltered_ibl_pixels`. When a depth frame is available and the track
  enables occlusion, export applies a per-pixel alpha depth mask using the
  packet's object-depth hint; if export has no global depth source, it can use
  the packet's live depth texture payload. The same normalized video-depth
  occlusion helper is used by synthetic/software fallback and packet PBR export,
  and `OpenGLPreviewWidget` keeps the live depth texture fragment-discard path.
  The main viewer can also show depth-map-only diagnostics through the `Depth`
  preview toggle or Python Actions `ar_pbr.preview.depth_view.get/set`; the UI
  button cycles `off -> matte -> distance -> plane -> off`. Matte is for
  occlusion-boundary checks, Distance is for depth gradient/contour inspection,
  and Plane is for rough road/floor placement candidates. The toggle is
  user-controlled, off by default, and must not affect export/composite output.
  Normal playback should not run live depth estimation unless AR/PBR occlusion,
  scene/plane anchoring, or explicit depth-map viewing is active; cache misses
  during depth viewing are accepted as diagnostic/placement cost, not baseline
  playback overhead.
  Full GPU helper export now receives the bridge-provided depth frame as a
  temporary float32 `.npy` payload and applies an overlay alpha depth matte
  before compositing the model-view render over the source frame. The supported
  controls are `occlusion_tolerance` / `depth_occlusion_tolerance` and
  `occlusion_softness` / `depth_occlusion_softness`; diagnostics include
  `depth_frame_available`, `pbr_depth_occlusion_applied`, and
  `pbr_depth_occluded_pixels`. This closes the previous full-GPU-service
  export gap, but native helper-side per-fragment object-depth comparison is
  still future quality work. Export uses
  overlay-only packet SSAA
  (`TIGERCAPTURE_AR_PBR_PACKET_SSAA`, default `2`) so AR/PBR edges are smoothed
  without softening the source video frame. `tools/qa_ar_pbr_gpu_preview.py` is
  the headless
  contract QA:
  it imports durable PolyHaven PBR samples from
  `sample_assets/pbr_blender_scenes/polyhaven` rather than disposable
  `debugCapture` assets, falling back only to a generated FBX smoke scene when
  the durable sample set is unavailable, and fails unless mesh, shadow, and
  reflection GPU packets are produced, including mesh-aware contact-shadow and
  layered depth-fade screen-reflection catcher packets.
  Remaining performance/product parity work is real shadow-map passes,
  physically richer reflections, GPU/model-view cubemap prefilter parity, and
  real-asset export quality with the full GPU model-view renderer.
  `TIGERCAPTURE_AR_PBR_EXPORT_RENDERER=gpu`
  and `offscreen_gpu` are recognized as explicit full-GPU requests; export first
  invokes the full model-view GPU helper. On success export records
  `mode=full_model_view_gpu_export_service`, `fallback=false`, and
  `worker_safe=true`. On failure it records
  `mode=offscreen_gpu_requested_packet_fallback` and uses the shared PBR packet
  renderer rather than silently ignoring the request. The fallback diagnostics
  include the service attempt, command environment variable,
  configuration/availability state, and service blockers so export logs
  distinguish "helper failed" from ordinary packet renderer failures.
- `tools/qa_ar_pbr_export_bake.py` is the encoded-output QA for the same
  contract. It verifies the packet export renderer reports
  `mode=gpu_packet_export`, renders at least one mesh/shadow/reflection packet,
  keeps packet SSAA enabled, changes final MP4 pixels, produces AR/PBR-colored
  overlay pixels, leaves catcher darkening in the encoded result, resolves at
  least one material texture map, reports GL-preview model-view-style material
  map PBR packet readiness, confirms at least one texture triangle and one PBR
  material-map triangle were sampled during export, and records
  `renderer_quality=preview_packet_pbr_material_maps`, HDRI directional
  sampling, roughness IBL prefilter sampling, and PBR depth-mask diagnostics.
- `tools/qa_ar_pbr_attachment_stability.py` is the product-level "does the 3D
  model stick to the video?" QA. It verifies road-plane anchor center drift,
  per-frame placement application, shadow/reflection catcher packets, and
  coarse fallback depth-occlusion skip counts through the same GPU preview
  packet path.
  It also checks the scene-anchor multi-probe video tracker can follow a
  shifted, scaled, and rotated asymmetric patch and apply the measured
  scale/roll to the AR/PBR track transform. Runtime diagnostics expose the
  `template_depth_plane_slam_assist` payload for UI/QA confidence display
  without claiming full SLAM. QA Dashboard exposes the report as
  `AR/PBR Attachment Stability`.
- The editor preview and preview pop-out expose a standard 3D transform gizmo
  for selected AR/PBR tracks. X/Y/Z handles use red/green/blue color coding for
  constrained move, axis scale, and per-axis rotation rings; the center moves
  in screen plane and the white diagonal handle performs uniform scale. This is
  an editor UX layer over the existing `transform` and `placement` payloads,
  not a replacement for the renderer or scene-anchor solver.
- The AR/PBR model preview window exposes an `HDR Environment` dropdown. It is
  backed by `debugCapture/ar_pbr_resources/manifest.json` and
  `app.ar_pbr.hdri_presets`, currently with eight local Poly Haven CC0 1K HDRIs.
  Selecting a preset reloads only the GL HDRI texture and updates estimated key
  light azimuth/elevation; it does not reimport the FBX/GLB mesh. Normalized
  track lighting preserves `hdri_id` and `hdri_path`.
- Combined GPU metadata is now a first-class regression target. The automated
  preview tests verify that color grade data, shader clip effects, Spine
  overlay packets, and AR/PBR overlay packets can share the same GL preview
  frame payload and still reach their separate `OpenGLPreviewWidget` consumers.
- `tools/qa_gpu_preview_pixel_collision.py` is the visible-framebuffer QA for
  the same surface. It captures a real `OpenGLPreviewWidget` framebuffer and
  verifies that shader changes plus AR/PBR mesh/shadow/reflection overlay
  pixels are present. It additionally verifies a real Spine sample on the
  direct GL overlay path and a real Live2D sample on the rendered-frame upload
  path. The report is tracked by the QA Dashboard under `GPU Preview Pixel
  Collision`.
- `tools/qa_editor_e2e_smoke.py` is the full Video Editor smoke gate for
  user-visible combinations that unit tests miss. It opens the real editor,
  imports a QA MP4 through Media Pool + timeline, verifies that the startup
  preview placeholder is removed, preview RGB is nonblank, side docks do not
  overlap the viewer, the preview pop-out receives frames, Media Pool and
  Workbench pop-outs restore their child panels, and bounded clip-audition
  playback returns to the original playhead. It then loads the actor QA
  project and verifies video, restored Media Pool state, Spine and Live2D
  actor lanes, shared timeline-ruler alignment, and nonblank preview together.
  QA Dashboard exposes this as `Editor E2E Smoke` and previews its contact
  sheet/screenshots.
- `tools/qa_editor_export_bake.py` is the final-file smoke gate for editor
  render parity. It exports a baseline QA clip and a processed clip through
  `VideoExportThread`, exercising text overlays, clip-level filters, zoom
  actors, and color grading. It then reads both encoded MP4s back through
  OpenCV, saves baseline/processed stills, and fails if the processed output is
  unreadable, visually unchanged, or missing the overlay/effect pixel evidence.
  QA Dashboard exposes this as `Editor Export Bake` and previews the processed
  output still.
- Chroma-key preview uses the OpenCV native HSV/LUT/mask path plus a
  preview-only downsample/upsample fast path controlled by
  `TIGERCAPTURE_CHROMA_PREVIEW_SCALE` (default `0.375`). Export still calls the
  full-resolution `apply()` path for parity. When clip-level video filters and
  chroma key are both enabled, `app.preview_effects.apply_filter_chroma_preview_batch()`
  runs both effects through one shared downsample/upsample pass; disable with
  `TIGERCAPTURE_DISABLE_FILTER_CHROMA_BATCH=1` for debugging. The main GL
  preview also has a shader-backed clip-effect path enabled by
  `TIGERCAPTURE_SHADER_CLIP_FX=1` (default). When QImage/final-CPU consumers
  are inactive, no background-removal/PIP/Live2D/transition ordering issue is
  present, and active Spine actors can use the direct GL overlay path,
  `ProjectPlayer` sends `clip_effects` metadata with `gpu_frame_ready` instead
  of running CPU preview filters/chroma. `OpenGLPreviewWidget` applies
  preview-safe `sharpen`, `vignette`, `chroma_aberration`, and HSV chroma key
  uniforms before color grade and before direct Spine mesh drawing. Temporal or
  random effects (`denoise`, `glitch`) and all QImage/popup/color-page fallback
  frames stay on the CPU path for preview/export parity.
- Clip-level video filters cache vignette masks by frame shape and parameters
  so repeated preview frames do not rebuild the same radial mask.
- `tools/qa_preview_perf.py` now produces an automated preview-performance
  report with media probe, timeline thumbnail, sampled `ProjectPlayer` render,
  optional 1080p/4K fixture measurements, and `native_gpu_candidates` hints
  derived from repeated slow preview stages. Run with `--clean --include-hires
  --render-samples 8` for the broader baseline. The report also records
  `preview_engine` capability/configuration state so perf numbers can be tied
  to the active decoder/frame-server/native-worker/Spine mode. Final Product
  Readiness requires actual sampled `preview_render` rows before the Preview/
  GPU area can score ready; media-probe/thumbnail-only or `--skip-render`
  reports are treated as attention states. The sampler now labels perf rows by
  context (`refresh`, `seek`, `playback_warmup`, `playback`), emits
  `playback_frame_summary`, and includes `stage_summary_by_context`. The gate
  reads nested `preview_render[].stage_summary` rows directly on old reports,
  and on current reports it uses `stage_summary_by_context["playback"]` plus
  `playback_frame_summary` for release-blocking Preview/GPU decisions. Slow
  refresh and random-seek decode samples remain visible as advisory polish debt,
  so startup/scrub issues are not hidden but no longer block steady playback
  release readiness. The release gate now prefers the
  canonical `debugCapture/preview_perf_report.json` artifact before falling back
  to experimental `preview_perf_report_*.json` files, so one-off decoder/scale
  experiments do not accidentally redefine product readiness. Supplying
  `--baseline <previous-report.json>` attaches `baseline_comparison`, comparing
  batch media probe, timeline thumbnail, preview-frame, and per-stage timings
  with absolute/relative thresholds. Blocking regressions make the report fail
  and retain native/GPU migration advice for stage-level slowdowns. Warm-up
  `preview.refresh.render` spikes, p95-only stage spikes without a sustained
  average regression, and stage regressions from changed preview sample plans
  are retained under `advisory_regressions` so QA still shows the signal without
  treating non-comparable measurements as release blockers. Preview perf QA now
  defaults to the main editor's GPU-only preview consumer
  (`TIGERCAPTURE_QA_PREVIEW_MODE=gpu`), disabling the legacy QImage signal so
  shader clip effects and Spine zero-readback paths are measured. Set
  `TIGERCAPTURE_QA_PREVIEW_MODE=qimage` to intentionally measure the CPU/QImage
  fallback path.
- `app.preview_scrub_readiness.build_preview_scrub_readiness_report()` turns
  the preview performance artifact into a user-feel gate for timeline scrubbing.
  It separates `current_corpus_scrub_ready` from `release_scrub_claim_ready`,
  scores each project on seek average/p95/max, playback average/p95, slow seek
  stages, and coverage across basic video, mask/filter/tracking, nested
  timeline, actor-heavy, audio-heavy, long project, and 4K. The CLI entry point
  `tools/qa_preview_scrub_readiness.py` writes
  `debugCapture/preview_scrub_readiness_qa.json`. A project can be ready on the
  current corpus while still blocking the stronger "4K/long/actor-heavy
  scrubbing is always smooth" claim if a required coverage class is missing.
  Pass `--auto-hires` to have the tool run `qa_preview_perf` with generated
  1080p/4K fixtures and fresh 540p sibling proxies when 4K coverage is absent,
  then rebuild the scrub report from that higher-coverage performance artifact.
  Final Product Readiness reads this artifact as `preview_scrub_claims`, so a
  release report can no longer score cleanly while the stronger smooth-scrub
  claim is missing required coverage. The 2026-07-05 strict clean-cache run is
  claim-ready for the current corpus: score 92/100,
  `release_scrub_claim_ready=true`, 8/8 projects ready, 0 blocked projects, and
  full basic/mask/nested/actor/audio/long/4K coverage. Keep universal
  no-latency claims blocked outside the measured corpus.
- `tools/qa_project_audit.py --preview-samples <N>` reuses the same preview
  render sampler for real user projects, keeping missing-asset audit, media
  probing, actor-asset checks, synthetic export parity, preview render timings,
  and native/GPU migration hints in one read-only report. Supplying
  `--baseline <previous-project-qa.json>` adds `baseline_comparison`, flagging
  projects that became unhealthy, missing media/model increases, actor asset
  failure increases, export-risk increases, synthetic parity regressions, and
  delegated preview-performance regressions. Each project report also includes
  `professional_readiness` from `app.professional_readiness`, scoring
  long-project stability, GPU preview/export consistency, timeline edit
  integrity, color workflow depth, audio mix readiness, and preset/template
  ecosystem readiness. The same report carries the advisory
  `resolve_post_pipeline_parity` matrix so project corpus QA can summarize
  Resolve/Fairlight/Fusion-class Color, Audio, VFX, performance, post-pipeline,
  and hardware ecosystem gaps separately from project export readiness. The
  manifest-level `professional_readiness_summary` aggregates ordinary readiness
  scores plus `resolve_parity.avg_score`, `resolve_parity.min_score`, and
  per-category minimum scores. QA Dashboard includes
  `debugCapture/project_qa_report.json` as "Project QA / Professional
  Readiness" and shows each audited project's readiness and advisory Resolve
  parity score with compact category scores. The readiness report
  carries the same Color/Audio parity feature counts used by Health/export:
  project LUT/HDR/OCIO intent, grade-local LUTs, secondary grade masks,
  loudness/dialogue cleanup, automation, and routed bus mixdown. Manifest
  reports include `professional_readiness_summary`.
- 2026-06-14 local baseline: tracked mask/filter project is dominated by
  `preview.stage.chroma_key` and `preview.stage.video_filters`; actor project is
  dominated by `preview.stage.spine_overlay`; 1080p/4K baseline fixtures are
  dominated by `preview.stage.decode`.
- 2026-06-14 after preview optimization pass: mask/filter/tracking project
  improved from 115.95 ms average to about 93-112 ms depending on run, with
  `preview.stage.video_filters` reduced by the vignette cache but
  `preview.stage.chroma_key` still the main Python hotspot. Live2D/Spine actor
  project improved from 117.93 ms average / 373.24 ms max to 69.93 ms average /
  114.26 ms max after half-resolution Spine preview, GL-preview bypass, and
  renderer prewarm.
- 2026-06-14 after the second preview/cache pass
  (`debugCapture/preview_perf_report_after_all_remaining_v2.json`):
  mask/filter/tracking project measured 40.34 ms average, with decode now the
  largest stage; Live2D/Spine actor project measured 62.60 ms average, with
  `preview.stage.spine_overlay` still the main hotspot at 36.26 ms average /
  82.22 ms p95. `native_gpu_candidates` in the report names the next measured
  migration targets.
- 2026-06-15 after GPU/native-facing preview pass
  (`debugCapture/preview_perf_report_after_gpu_native_v1.json`): chroma-key
  preview in the mask/filter/tracking project dropped to 4.31 ms average while
  total preview averaged 35.54 ms. Decode remains the largest stage there at
  22.29 ms average. The actor QA project averaged 67.13 ms; Spine overlay
  remained the top hotspot at 38.51 ms average / 88.11 ms p95, indicating that
  the next Spine step is a true GPU actor compositor/readback reduction rather
  than another Python cache.
- 2026-06-15 after the follow-up preview-speed pass
  (`debugCapture/preview_perf_report_after_gpu_native_v4.json`): filter/chroma
  preview defaults moved to 0.375 scale, OpenCV sequential next-frame seeks now
  avoid redundant `CAP_PROP_POS_FRAMES`, prefetch defaults moved to 24 frames /
  80 ms wait budget, and Spine preview time is quantized at 24fps by default.
  The mask/filter/tracking project measured 37.46 ms average, with decode
  25.50 ms, video filters 5.73 ms, and chroma key 4.44 ms. The actor project
  measured 68.64 ms average, with Spine overlay still the dominant hotspot at
  43.01 ms average / 98.46 ms p95. The remaining high-value step is still a
  full GL actor compositor/FBO-readback reduction plus a process-level decode
  frame server for projects without fresh proxies.
- 2026-06-15 after the "big three" implementation pass
  (`debugCapture/preview_perf_report_after_all_big_three_v1.json`): a shared
  Spine overlay GL compositor was added, FFmpeg pipe frame-server decode was
  added behind `TIGERCAPTURE_PREVIEW_FRAME_SERVER=1`, and filter+chroma preview
  can batch into one downsample/upsample pass. The mask/filter/tracking project
  improved to 32.46 ms average, with the combined
  `preview.stage.filter_chroma_batch` at 8.24 ms average and decode still
  23.46 ms. The actor project measured 74.07 ms average; Spine overlay remained
  43.05 ms average / 100.68 ms p95 on the single-Spine-clip sample, so the next
  Spine win requires deeper FBO readback elimination for single/complex rigs.
  Opt-in FFmpeg frame-server QA
  (`debugCapture/preview_perf_report_after_frame_server_optin_v1.json`) worked
  functionally but was slower on this random-seek corpus, so it remains a
  comparison path rather than the default.
- 2026-06-17 actor preview QA calibration
  (`debugCapture/preview_perf_report_after_spine_state_cache_v3.json`):
  baseline comparison now separates blocking regressions from advisory warm-up,
  p95-only, and changed-sample-plan signals. The run passed with zero blocking
  regressions; the actor project improved from 74.07 ms average / 129.31 ms p95
  to 54.94 ms average / 77.80 ms p95. `preview.stage.spine_overlay` is still the
  largest actor hotspot at 48.62 ms average / 72.96 ms p95. The opt-in array
  compositor trial passed but did not improve enough to become the default.
  A later product-gate pass added a separate animated Spine playback scale
  (`spine_playback_preview_scale=0.375`) and lowered animated complex/overlap
  Spine fallback scale from 0.375 to 0.25 while keeping paused preview at the
  normal scale; current `qa_preview_perf.py` reports include both scale values
  in `preview_engine` so this tradeoff is visible.
- 2026-06-23 stabilizer preview fast path
  (`debugCapture/preview_perf_report.json`): `ProjectPlayer` now calls
  `FrameStabilizer.apply_preview()` for main and nested preview clips while
  export keeps `apply()`. On the current QA corpus, `02_masks_filters_tracking`
  playback improved from the previous 20.39 ms average / 28.94 ms p95 to
  14.83 ms average / 18.47 ms p95, and `preview.stage.stabilizer` dropped from
  12.62 ms average / 13.34 ms p95 to 6.16 ms average / 7.72 ms p95. The report
  has zero `native_gpu_candidates`; remaining slow entries are warm-up/seek
  advisory decode/refresh costs, not steady playback blockers.
- 2026-06-23 refresh/seek advisory cleanup
  (`debugCapture/preview_perf_report.json`): `ProjectPlayer` no longer imports
  the heavy `app.video_editor_window` module during preview zoom rendering; it
  imports zoom helpers from `app.timeline_model` instead. The same-position
  seek path also re-emits the last completed preview frame when the playhead,
  clip, frame, and cache generation match, avoiding repeated decoder reads from
  duplicate UI position updates. On the current QA corpus, the first project
  setup path dropped to 92.27 ms and `preview.refresh.render` to 42.82 ms. The
  mask/filter/tracking project keeps steady playback at 14.92 ms average /
  18.14 ms p95 with zero `native_gpu_candidates`; remaining seek rows are
  random-access decoder advisory costs.
- 2026-06-23 preview warm-up/seek advisory tightening; refreshed 2026-07-05
  (`debugCapture/preview_perf_report.json`): `ProjectPlayer.refresh_tracks()`
  now accepts `render_immediately=False` so QA/batch setup can rebuild decoder
  state without also charging the first visible preview render to refresh.
  Preview perf QA now applies the same acceleration defaults as app startup
  before measuring preview frames, so clean-cache performance evidence reflects
  the shipped runtime path. The current report samples 8 projects, has zero
  `preview.refresh.render` rows and zero `native_gpu_candidates`, and leaves
  only advisory random seek/decode costs; the scrub gate is claim-ready even
  though hotspots remain visible for polish.
- `PrefetchDecoder` now defaults
  `TIGERCAPTURE_PREFETCH_FORWARD_SEEK_WINDOW` to 12 frames. Near-future forward
  scrubs can reuse already-prefetched frames by default while still allowing
  the window to be tuned or disabled through the environment.
- Windowed editor dragging uses a runtime move guard. `VideoEditorWindow.moveEvent`
  starts a short settle timer; while active it stops the decorative blade/
  selection marching-ants timer, suspends animated timeline tool buttons,
  preset hover/live-preview timers, preset preview swatches, and the audio
  mixer VU decay timer, then calls `ProjectPlayer.set_window_move_guard(True)`.
  The player switches its playback timer to coarse timing with a minimum 100 ms
  interval, then restores precise timing and the previous interval when the OS
  window move settles. Begin/end UX telemetry records how many surfaces were
  suspended and the move-guard duration, so future titlebar-drag reports can be
  checked from logs rather than guessed. This keeps native titlebar dragging
  from competing with preview/decorative repaint loops.
- `tools/qa_window_move_guard.py` is the product QA for that behavior. It writes
  `debugCapture/window_move_guard_qa.json`, verifies `ProjectPlayer` timer
  relaxation/restoration, individual timeline/preset/audio animation suspension,
  and a real offscreen `VideoEditorWindow` guard pass. Final product readiness
  consumes this artifact in the `timeline_polish` area, alongside fuzzer,
  alignment, and visual-alignment QA.
- Python should remain the UI/orchestration layer for now. The long-term
  performance path is not a full rewrite first; move hot preview/render/cache
  stages to FFmpeg/OpenGL/native C++ or Rust helpers where profiling proves
  Python overhead or CPU copies are dominant.
- Static `BitmapMask` evaluation caches the resized/softened float mask.
- Tracked `BitmapMask` does not cache final masks because each frame can move,
  but it caches tracker bboxes to avoid repeated random-seek tracker work.
- `VideoEditorWindow._prewarm_tracking_caches_for_track()` starts
  `ObjectTrackingCacheWorker` for active tracked `BitmapMask` masks so preview
  playback can reuse bbox cache entries instead of discovering them one frame at
  a time.
- `ProjectPlayer` owns a small generation-based preview pre-render cache for
  safe CPU node-effect frames. `PreviewPrerenderWorker` fills this cache for
  near-future frames when the active node chain contains no color-grade node
  whose order relative to overlays could change the result.
- Live2D editor startup can be slow because model discovery/loading and OpenGL
  initialization are expensive; prefer lazy loading and cache checks.
- Sound Editor waveform extraction is already asynchronous; source separation is
  a background `QThread`, but Demucs can still run for a long time and may
  download/load model weights if the local environment has no cached model.

## Development Strategy

- Short term: keep the PySide/Python application as the product shell. Stabilize
  timeline UX, save/load, preview/export parity, and undo/redo before attempting
  a UI rewrite.
- Performance work must start with measurement. Use `TIGERCAPTURE_PERF=1` on
  real 1080p/4K projects, then move only proven hot paths out of Python.
- Preferred native direction is Rust for cross-platform helper cores. Use Rust
  first for cache/indexing/render-worker style modules where the UI contract can
  be cleanly expressed as files, JSON, or frame buffers.
- C++ remains appropriate only where an SDK or UI/runtime binding strongly
  favors it, such as low-level Qt/OpenGL/Live2D integration.
- The safest migration boundary is process-first: build Rust helpers as CLI or
  JSON-lines worker processes before binding them with `pyo3`. This keeps crash
  isolation, packaging, and rollback simpler while the product is still moving.
- Candidate Rust modules, in order: media indexing/probing, timeline thumbnail
  cache generation, waveform/spectrum generation, OpenCV/object-tracking cache,
  preview pre-render workers, and eventually a GPU-backed preview compositor.
- Do not rewrite the full UI until the Python version has stable editing
  semantics and the native core APIs are proven by tests/golden media fixtures.

Native worker implementation:

- Rust source lives in `native/tigercapture_worker`. It is a JSON-lines
  subprocess worker and currently implements `capabilities`, `shutdown`,
  `media_probe`, `batch_media_probe`, `timeline_thumbnails`,
  `timeline_drag_constraints`, `timeline_gaps`, `timeline_trim_plan`,
  `audio_waveform`, and `audio_spectrum`.
- `timeline_drag_constraints` is the first native timeline-core planner. The
  `clip.move_snapped` Python Action asks the Rust worker for snap/collision/
  clamp resolution when available and falls back to Python
  `apply_drag_constraints_detail` when the worker is missing, outdated, or
  rejects the request.
- `timeline_gaps` is the second native timeline-core planner. The shared
  `_track_gaps` helper asks the Rust worker for gap detection when available,
  so `timeline.gaps`, `timeline.close_gap`, and `timeline.close_all_gaps` get
  native gap rows while preserving Python fallback.
- `timeline_trim_plan` is the third native timeline-core planner. It computes
  video-only ripple/precision trim windows and following-clip shifts for
  `clip.ripple_trim`, `timeline.precision_trim`, and
  `timeline.trim_to_playhead`. Python keeps validation, linked-audio movement,
  undo transactions, and final project mutation, so missing or outdated workers
  still fall back to the established Python edit policy.
- Python integration lives in `app/native_worker.py`. Discovery checks
  `TIGERCAPTURE_NATIVE_WORKER`, then local debug/release worker paths, then a
  bundled native path.
- The worker is optional. If it is missing or rejects the protocol, Python paths
  keep running and `get_native_worker_capabilities()` returns `None`.
- `app.media_pool`, `probe_video_duration_ms()`, `_probe_video_dimensions()`,
  `probe_audio_duration_ms()`, `ThumbnailExtractor`, `WaveformExtractor`, and
  `SpectrumExtractor` prefer the native worker where available and fall back to
  the previous Python/OpenCV/FFmpeg paths when needed.
- The first stable protocol is `json-lines-v1`: one JSON request per stdin line,
  one JSON response per stdout line. Every request has `id`, `method`, and
  `params`; every response has `id`, `ok`, and either `result` or `error`.

AI Script Edit MVP integration:

- `app.ai_script_edit_panel.ScriptEditPanel` is available from the video
  editor toolbar and right dock as a reviewable transcript-edit planning panel.
- The toolbar AI button opens a compact bottom `AI Command` dock in the main
  frame editor instead of forcing the right Workbench/Inspector open. The dock
  has a visible `AI` badge, one-line prompt input, `Plan`, `Review`, pop-out,
  and hide controls. It is hidden until requested, can detach to a parented
  floating `QDialog`, and can re-dock without rebuilding the Script Edit model.
  `Plan` generates the same safe `EditPlan` pipeline as Script Edit; if project
  subtitles exist they become the transcript source, otherwise plain edit
  prompts stay command-only review requests until a provider returns concrete
  operations. Provider
  connection/status questions such as "Claude connected?" are answered in chat
  only and must not seed a transcript, subtitle row, or Review plan.
- The AI Command dock keeps a compact chat transcript (`AI` / provider label),
  but the primary action label must be provider-specific rather than a generic
  message-send button: Claude shows `Plan 생성` when direct generation is ready
  and `Open Claude CLI` only for terminal handoff/setup, local LLM shows
  `Run local LLM`, Qwen shows `Run free AI`, and rule-based mode shows
  `Generate rule-based plan`.
- Provider interaction copy is centralized in
  `app.ai_providers.provider_interaction_model()`. AI Command and Script Edit
  share the same provider run label, setup label, placeholder, and status
  summary. Claude is a direct `EditPlan` surface when CLI/MCP readiness is
  complete, with terminal handoff kept as setup/diagnostic fallback; local LLM
  is shown as setup-or-run depending on command readiness, and Review
  remains a validated `EditPlan` inspection/apply surface rather than an
  in-app Claude chat or subtitle-only panel.
- Provider runtime state is also centralized through
  `app.ai_providers.provider_user_state()`. UI surfaces can now show the
  selected provider, the effective generation provider, whether rule-based
  fallback is active, whether the action opens a terminal, and the next action
  the user should take. This prevents ambiguous labels such as "connected" from
  implying that Claude/Qwen/Codex directly generated the current Plan when the
  app actually used the safe rule-based planner.
- The bottom AI Command `Review` button opens a centered `AI Edit Review` dialog
  seeded with the current prompt/plan instead of unexpectedly expanding the
  cramped right Workbench Script Edit section. The underlying Script Edit widget
  owns its own dark, high-contrast styling so it remains readable in docks,
  pop-outs, and review dialogs.
- AI Command Review no longer converts a plain prompt into temporary SRT/subtitle
  content. It uses real project subtitles/transcripts only when they exist; if
  no transcript context is present, the baseline is a command-only review plan
  and provider output is the only source of concrete operations. The Review
  button also regenerates when the prompt differs from the last plan, preventing
  stale subtitle plans from being shown for a new command.
- Review-mode `ScriptEditPanel` clears stale transcript widgets for command-only
  prompts, labels the dialog as AI task review rather than subtitle entry, and
  explicitly states when no timeline operation has been produced yet.
- Script Edit now checks provider connection/status prompts before importing
  transcript text. Questions such as "Is Claude connected?" create a
  `prompt_only_edit_request` status plan with zero operations and
  `transcript_required=false`, so the prompt is not inserted into subtitles or
  treated as edit text.
- The panel imports pasted SRT/VTT transcript text, transcript files, or a local
  speech-recognition result from `app.local_ml.local_ml_transcribe_media()`.
  Local transcription never downloads models or calls a cloud API; when a local
  faster-whisper model is missing, the panel shows an actionable non-fatal
  status and keeps the manual transcript path available.
- The panel shows segment rows, generates deterministic `EditPlan` objects
  through `app.ai_text_editing`, resolves Korean/English editing prompts to
  local recipes, and exposes checked review-card/operation ids for selected
  apply.
- AI planning now has a pre-MCP contract layer. `app.ai_edit_plan` emits
  `schema_version: 1` and `provider` on every `EditPlan`; old missing-version
  payloads are treated as v1, while unsupported future versions are rejected.
- `app.ai_providers` registers the safe provider ids `rule_based`,
  `qwen_local`, `local_llm`, `codex_mcp`, `claude_mcp`, and `manual_json`.
  `qwen_local` is the default free local AI profile described in
  `docs/SPEC_LOCAL_AI_PROVIDERS.md`; source builds must report setup/readiness
  without committing model weights. The AI Command dock exposes a setup action:
  Qwen opens a first-use progress dialog with console output, can install/start
  the local llama.cpp path, saves the endpoint/model path, and selects the
  provider after connection. When an OpenAI-compatible Qwen endpoint is
  available, `generate_selected_provider_plan()` sends the prompt, transcript
  summary, and deterministic baseline plan to Qwen, accepts only validated
  `EditPlan` JSON, and falls back to the deterministic plan on invalid output.
  The Qwen first-use runner now prefers `llama-server.exe`; if the local
  Hugging Face cache already contains the GGUF blob it starts from `-m <cache>`
  rather than forcing a fresh `-hf` download. Headless/QA startup is centralized
  in `app.ai_qwen_server`: it checks the OpenAI-compatible `/v1/models`
  endpoint, can start the configured llama.cpp runner without a console window,
  and returns structured startup/readiness diagnostics. `tools/qa_ai_edit_corpus_quality.py`
  can use this path with `--provider qwen_local --auto-start-qwen` before
  exercising the provider corpus. Real 2026-06-28 smoke runs loaded
  `Qwen3-1.7B-Q8_0.gguf` on `127.0.0.1:8080` and produced validated plans in
  `debugCapture/qwen_local_editplan_smoke.json` and
  `debugCapture/qwen_local_editplan_smoke_repaired.json`. The 2026-07-07 local
  provider corpus run used `qwen_local` directly against
  `http://127.0.0.1:8080/v1` and produced 20/20 direct `EditPlan` successes
  with zero deterministic fallbacks.
  Saved Qwen endpoints are treated as retryable configuration, not proof that
  the local server is currently alive; a failed direct request is remembered and
  the UI shows an action-oriented reconnect/attention state until a valid
  response clears that state.
  Claude is direct-first when ready: selecting Claude runs validated in-app
  `EditPlan` generation without any hidden environment setup. The terminal
  handoff remains available for setup/diagnostics/manual agent work: it opens a
  visible PowerShell Claude Code terminal in the Tiger Studio workspace, writes
  `TIGER_STUDIO_CLAUDE_START.md`, passes that Markdown brief as Claude's initial
  prompt, copies it to the clipboard as a fallback, runs/prints the
  `tiger-studio` MCP registration step, and tells the user to check `/mcp`. The
  older in-app progress/log dialog remains available for MCP registration and
  status checks.
  `generate_selected_provider_plan()` validates Claude-produced `EditPlan` JSON
  automatically when Claude is selected, the MCP bridge is registered, and
  Claude Code CLI is available. Leaving `TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR`
  unset is the normal auto-direct behavior. The direct Claude executor sends compact EditPlan
  context through stdin rather than a long command-line argument, defaults to
  `TIGERCAPTURE_CLAUDE_MODEL` or `haiku` with low effort for responsive
  edit-planning calls, and accepts only validated `EditPlan` JSON before Review.
  Real English and Korean smoke reports live at
  `debugCapture/claude_direct_editplan_smoke.json` and
  `debugCapture/claude_direct_editplan_ko_smoke.json`. Claude direct provider
  corpus evidence has also passed the 20/20 direct-success smart-edit gate in
  earlier release runs; that evidence remains valid provider support even
  though the current default-free path is Qwen local.
  Setting `TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR=0` disables automatic in-app
  Claude plan generation for diagnostics or terminal-only workflows, causing
  `effective_generation_provider` to remain `rule_based`. The AI Command dock
  posts an explicit Tiger Studio chat/status message before opening the terminal
  handoff so users understand when they are leaving the direct Review flow. The
  default interactive Claude UX no longer pretends that the app itself is an
  unrestricted Claude chat surface. Codex has the same Review-first
  executor path when
  `TIGERCAPTURE_CODEX_EXECUTOR_COMMAND` is explicitly configured: the command
  receives the JSON prompt payload through stdin or `{payload_json}`, and stdout
  is accepted only after validated `EditPlan` parsing. Codex MCP/terminal
  bridge instructions remain available for handoff-only workflows. This registry
  reports readiness and validates provider/manual JSON; it does not let external
  agents mutate projects directly without the app's safety boundary.
- `local_llm` is no longer status-only: when
  `TIGERCAPTURE_LOCAL_LLM_COMMAND` points to an available command, the app sends
  a JSON prompt payload through stdin and accepts either raw `EditPlan` JSON or
  an OpenAI-compatible wrapper from stdout after validation. The bottom AI
  Command chat therefore works for configured local models the same way it does
  for Claude/Qwen, while still falling back to deterministic rules on timeout or
  invalid output. The same command can also be stored through the in-app local
  LLM setup dialog; the environment variable remains the highest-priority
  override, but users no longer need to edit shell variables for the common
  local-runner setup path. Both the bottom AI Command dock and the Script Edit
  provider setup button expose this command-entry flow and refresh provider
  readiness immediately after saving. When Script Edit is hosted inside the
  video editor, provider setup is delegated to the owning editor so Qwen uses
  the full first-use install/connect dialog, Claude setup can open the terminal
  handoff while ready-state generation is automatic, and local LLM uses the
  shared command-entry setup rather than a detached instruction-only message.
- The dedicated AI Review dialog is not the full Script Edit entry form. It
  reuses `ScriptEditPanel` in review mode, hiding prompt, transcript import,
  segment, and manual-plan controls so the user only sees the generated Plan
  summary, warnings, review cards, operations, and the selected/all/cut apply
  buttons. This keeps Review visually separate from subtitle/transcript editing.
- `app.ai_project_snapshot.build_project_snapshot_from_editor()` builds the
  read-only JSON state an agent may inspect: timeline tracks/clips, media pool,
  subtitles, markers, selected clips, locks, current position, and a stable
  snapshot hash.
- `app.ai_plan_validation.validate_edit_plan_for_snapshot()` is the gate between
  AI output and editor mutation. It performs dry-run counts, time-range checks,
  selected-operation checks, destructive-operation review warnings, and locked
  track blocking for explicit cut materialization.
- `app.ai_action_log.append_ai_action_log()` writes JSONL audit events under
  `debugCapture/ai_action_log.jsonl`, redacting token/secret/password/api-key
  fields. Script Edit generation, validation, review-safe apply, and
  materialized cuts log through this path.
- `app.ai_edit_corpus_quality.build_ai_edit_corpus_quality_report()` is the
  quality gate for claiming intelligent AI editing. It scores Korean, English,
  tutorial, short-form, product-demo, and long-form corpus cases for prompt
  intent, required operation coverage, review-card validity, transcript
  coverage, and provider evidence. Built-in fixtures can pass
  `safe_mvp_ready`, but `smart_edit_claim_ready` stays false until a wired
  LLM/agent provider is exercised on a real user corpus. The CLI entry point is
  `tools/qa_ai_edit_corpus_quality.py`, which writes
  `debugCapture/ai_edit_corpus_quality_qa.json`. Long-running local/agent
  providers can be exercised with `--use-provider --provider <id>
  --provider-timeout 240 --provider-retries 1`; Qwen can additionally be
  started from the same QA command with `--provider qwen_local
  --auto-start-qwen`. This keeps transient timeouts measured separately from
  real fallback behavior. Final Product Readiness reads
  this artifact as `ai_edit_claim_quality`, so rule-based success can still be
  reported as a safe MVP without accidentally enabling smart-AI marketing copy.
  The current provider-exercised report runs `qwen_local` through the local
  OpenAI-compatible Qwen endpoint; it reports 20/20 direct successes, 0
  fallbacks, score 99/100, and `smart_edit_claim_ready=true`. Earlier Claude
  direct provider reports also passed 20/20 direct successes with 0 fallbacks,
  so Claude should be treated as a validated optional provider path rather than
  a failed or unproven path. These reports prove the smart-edit gate for the
  local automation-generated corpus, not universal human editing quality.
- `app.ai_edit_corpus_intake.build_ai_edit_corpus_intake_report()` turns the
  missing real-corpus work into concrete collection slots. It can write
  `.template.json` files under `qa_corpus/ai_editing_corpus/intake_templates`
  for Korean, English, tutorial, short-form, product, and long-form cases, but
  those files deliberately set `counts_for_ai_claim: false` and are not loaded
  as manifest cases until a real transcript, natural-language prompt, expected
  operations, and provider review evidence are filled in. The CLI
  `tools/prepare_ai_edit_corpus_intake.py --write-templates` writes
  `debugCapture/ai_edit_corpus_intake_qa.json`, QA Dashboard exposes it as
  "AI Edit Corpus Intake", and Final Product Readiness includes the template
  count while keeping `smart_ai_edit_claim_ready` false until real cases and a
  direct provider run pass.
- `app.ai_edit_corpus_registration.register_ai_edit_corpus_case()` and
  `tools/register_ai_edit_corpus_case.py` are the safe promotion path from
  intake template to counted real corpus case. They require a real transcript
  file, natural-language prompt, language/scenario, expected intent, and
  required operations; by default the transcript is copied under
  `qa_corpus/ai_editing_corpus/transcripts/` and the manifest case is marked
  `fixture=false`. Placeholder prompts, missing transcripts, and too-few
  transcript segments are rejected before the manifest is written. The CLI also
  supports `--from-template <filled.template.json>`, so a reviewer can fill
  `manifest_case.prompt` and `manifest_case.transcript_path` in the generated
  template, then promote it without retyping every field. AI corpus intake
  templates and rows include a `registration_command` that points to this CLI so
  real cases are promoted through validation instead of manual manifest edits.
  `tools/register_ai_edit_corpus_templates.py` provides the batch path: it scans
  a template directory, skips placeholder templates, validates filled templates,
  and registers only real cases with transcript and natural-language prompt.
- Direct AI provider output is repaired only at the Review metadata boundary:
  `validate_provider_plan_json()` now fills missing operation ids with the same
  `make_operation_id()` rule used by core plans, adds missing review-card ids or
  titles, and reconnects empty review-card `operation_ids` before running the
  normal strict `EditPlan` validator. Unknown keys, bad operation types,
  forbidden payload fields, unsafe params, and invalid time ranges still fail.
- `app.automation_commands.AutomationCommandRegistry` is the internal command
  boundary for future MCP exposure. It registers only named safe commands:
  `get_app_status`, `get_ai_provider_status`, `get_project_snapshot`,
  `get_timeline_summary`, `get_selected_clip`, `get_media_pool_summary`,
  `get_transcript_summary`, `validate_edit_plan`, `generate_edit_plan`,
  `preview_generated_plan`, `preview_edit_plan`, `apply_edit_plan`,
  `apply_reviewed_cuts`, and `add_marker`. The registry explicitly forbids
  arbitrary Python/shell execution by construction; external MCP tools should
  call these commands instead of touching editor internals.
- This command registry is intentionally narrower than the studio-wide Python
  Action System. `app.actions.build_default_action_registry()` is now the
  broader registered action surface, while `app.automation_commands` remains
  the compatibility bridge for EditPlan, marker, and reviewed-cut workflows.
  The Action System routes through `app.actions.editor_adapter.EditorAdapter`
  and currently exposes validated actions for media intake, timeline/NLE
  editing, clips, tracks, transitions, audio, color, node graphs, typography,
  Live2D/Spine actor data, VTuber Performance Source, UI focus, detachable
  popout window open/geometry/capture/close control, review scenarios, capture
  evidence, viewer comparison controls (`ui.viewer.compare.set`), viewer fit
  (`ui.viewer.fit`), and QA without exposing arbitrary Python or private editor
  methods to external clients. External MCP/Codex/Claude
  adapters that need broad editor control should wrap the registered action
  schema/preview/execute sequence instead of calling editor internals.
- Editor/studio capture is now an action-only capability rather than a new UI
  panel. `capture.targets` returns the semantic capture targets available in
  the live editor (`editor`, `viewer`, `timeline`, `media_pool`, `workbench`,
  `color`, `audio`, and diagnostic `screen`) and whether each target resolves
  to a grab-capable widget. `capture.screenshot` and `capture.gif` accept the
  same target names, so MCP/AI callers can handle commands such as "capture the
  viewer" or "capture the timeline" without depending on launcher capture UI.
  Launcher capture and Studio/editor action capture are intentionally separate:
  future launcher work can split Capture and Studio visually while keeping
  MCP/AI capture routed through the registered Action System.
  Agent shorthand: when the user says "캡쳐기능 봐줘", "에디터 안 캡쳐", or
  "editor capture" without explicitly mentioning visible capture UI, region
  selection, or launcher recording controls, treat the request as MCP/AI
  action capture first.
- Specific external-program capture is also exposed through the same action
  layer, without adding a new editor UI. `app/window_capture.py` implements
  Windows top-level window enumeration and capture. `capture.windows.list`
  returns candidate windows by title substring, process substring, pid, or
  handle; `capture.window.screenshot` saves a still image from the matched
  window; and `capture.window.video` records a short MP4/MOV/MKV by piping RGB
  frames into ffmpeg with hidden subprocess flags to avoid flashing console
  windows. `backend=auto` may use Windows Graphics Capture for supported
  top-level windows and falls back to visible rectangle capture when needed.
  The `printwindow` backend remains an explicit fallback for covered windows
  but may return black for GPU-rendered apps. This is the intended route for
  AI/MCP commands such as "record an external tool window for five seconds" or
  "capture the Chrome window."
  When another AI agent owns the operation length, use the session actions
  instead of guessing a fixed duration:
  `capture.window.video.start` with a `max_duration_ms` safety cap, optional
  `capture.window.video.status` polling, then `capture.window.video.stop` when
  the external task completes. If an external agent asks "until when?", the
  contract answer is "until you send stop after the task completes, with
  `max_duration_ms` as the hard timeout."
- `generate_edit_plan` lets external agents create deterministic Script Edit
  plans from SRT/WebVTT transcript text, existing project subtitles, an optional
  Korean/English prompt, style preset, and silence intervals. It returns the
  `EditPlan`, document summary, review preview, payload counts, and validation
  result without mutating the timeline. `preview_generated_plan` provides the
  same review-card/operation preview for already generated plan JSON.
- `VideoEditorWindow.automation_command_specs()` and
  `VideoEditorWindow.automation_execute_command()` expose that registry from a
  running editor instance. `preview_edit_plan` can paint non-destructive preview
  markers, `apply_edit_plan` can apply safe payload sections only, and
  `apply_reviewed_cuts` is the separate destructive path that reuses the same
  validation gate and locked-track checks.
- `app.automation_bridge.AutomationBridge` is the JSON-lines protocol layer that
  Codex/Claude MCP adapters should wrap. Supported methods are
  `automation.ping`, `automation.schema`, `automation.list_commands`, and
  `automation.execute`; requests are size-limited, schema-described, and routed
  only to registered automation commands. The bridge reports that arbitrary
  Python and arbitrary shell execution are unavailable by design.
- `app.automation_mcp.AutomationMCPServer` is the minimal stdio JSON-RPC MCP
  wrapper over that bridge. It handles `initialize`, `tools/list`, `tools/call`,
  `ping`, empty `resources/list`, and empty `prompts/list`. Exposed tool names
  are `tigercapture_ping`, `tigercapture_schema`,
  `tigercapture_list_commands`, and `tigercapture_execute_command`; the execute
  tool forwards only registered automation commands and preserves dry-run
  semantics.
- `VideoEditorWindow.automation_bridge_handle()` exposes the same bridge against
  a running editor instance, and `VideoEditorWindow.automation_mcp_handle()`
  exposes the same MCP method handler against live editor state.
  `tools/automation_bridge_cli.py` can smoke-test the bridge without a GUI
  owner, `tools/automation_mcp_server.py --stdio` is the standalone MCP server
  command, `tools/qa_automation_bridge.py` writes
  `debugCapture/automation_bridge_qa.json`, and
  `tools/qa_automation_mcp.py` writes `debugCapture/automation_mcp_qa.json`.
- `app.ai_providers.provider_snapshot()` now includes `automation_mcp` metadata:
  the default server command, tool names, and the explicit
  `registered_commands_only` flag. The Script Edit provider tooltip surfaces the
  same information for human inspection.
- `app.ai_edit_apply.build_ai_script_apply_payload()` converts validated plans
  to safe editor payloads. Subtitles and markers can be materialized by the
  editor; destructive text/range cuts are still review-only during normal
  apply, but the panel has a separate explicit "Apply reviewed cuts" path. That path
  calls `app.ai_edit_apply.apply_ai_script_cut_intents_to_tracks()` and performs
  global ripple deletes across video and audio tracks after splitting at the
  reviewed cut boundaries.
- Generating or previewing a Script Edit plan now paints temporary timeline
  markers for AI cut ranges, short candidates, and auto-zoom suggestions. Actual
  cut materialization replaces those temporary markers with applied-cut markers.
- `add_auto_zoom` sidecars from Script Edit recipes are connected to the
  existing Screen Studio Polish engine, so applying a tutorial/product/shorts
  plan can generate the same cursor/click-based zoom actors used by the Auto
  Polish panel when cursor metadata is available.
- `tools/qa_ai_script_edit_integration.py` writes the current MVP QA artifact
  at `debugCapture/ai_script_edit_integration_qa.json`.
- `tools/qa_automation_commands.py` writes the command-registry QA artifact at
  `debugCapture/automation_commands_qa.json`.

## Motion Designer

- The independent authoring window lives under `app/motion_designer/ui`; the
  main-editor integration is isolated in `app/video_editor_motion_workflow.py`,
  `app/video_editor_delegates_motion.py`, and
  `app/video_editor_motion_lane_row.py`. Do not add Motion Designer feature
  logic to `app/video_editor_window.py`.
- `.tgp` format `1.2` persists `motion_compositions` and `motion_clips`.
  Invalid motion compositions are isolated during load instead of preventing
  the rest of the project from opening. Composition revisions invalidate the
  shared frame cache.
- Motion Designer also owns the independent `.tgmotion` document format for
  authoring work that is not yet placed in the main video timeline. The
  standalone window provides Open, Save, Save As, dirty-close confirmation,
  and a 30-second recovery copy. Saves are atomic and validated before replace.
  `motion.project.save` and `motion.project.load` expose the same document
  boundary to Actions/MCP.
- `.tgp` remains the integrated video-editor project, not a portable archive of
  every Tiger Studio tool. It embeds Motion compositions and placements plus
  the supported Music, Spine, Live2D, MMD, and AR/PBR timeline state, while
  independent PPT documents use `.tgppt` and Motion documents may use
  `.tgmotion`. Referenced media and model resources normally remain external
  paths; a future workspace/package format must bundle or relink those assets
  before one file can guarantee reopening every standalone tool document.
- The Qt-free evaluator supports hierarchy, hold/linear/cubic-Bezier
  keyframes, trim/source-in/time-scale/reverse, loop/ping-pong, constraints,
  and fade/slide/scale/pop/spring/wiggle behaviors. Behavior output can be
  sampled and baked to ordinary transform keyframes.
- The authoring workspace keeps four production regions visible together:
  `Library/Inspector`, `Layers/Media/Audio`, `Canvas/Preview`, and the lower
  `Layer Timeline + Graph`. This layout is intentionally compatible with the
  dense layer-first workflow used by dedicated motion-graphics tools; the
  timeline and graph are not mutually exclusive tabs.
- `docs/motion-user-guide.pdf` is the durable interaction and workspace
  reference for Motion Designer. The desktop shell follows its Classic layout:
  Library/Inspector occupies the full-height left column; Layers/Media/Audio
  and Canvas share the upper production area; Timeline/Keyframe Editor spans
  the full width below both. The top toolbar exposes Library, Inspector,
  Project Pane, and File on the left, with Add Object, Behaviors, and Filters
  as primary authoring commands. Tiger Studio retains its own branding,
  icons, Windows conventions, AI workspace, character actors, and Unreal Link.
- Selecting a layer changes the left side from Add/Library to the contextual
  Inspector and chooses the relevant Text, Image, Shape, Generator, Actor,
  MMD, VRM, 3D, or Particle page. Replicator has its own Inspector page and
  toolbar command because it is a layer pattern system, not a Transform
  property. Re-selecting the same layer preserves the user's current inspector
  subpage. Clearing selection returns to Add.
- The former ambiguous `Library / Apply` surface is presented as an action-led
  `Add` panel. `Templates` and `Create with AI` are the primary starting
  choices; object, animation, effect, template, and motion-preset categories
  show a concise purpose for every item and use contextual commands such as
  `Add Text`, `Animate with Fade`, and `Apply Glow`. The AI workspace is closed
  by default to preserve canvas width and opens from either `Create with AI` or
  the toolbar AI toggle.
- The authoring UI provides a searchable object/behavior/filter library, layer
  tree, canvas, Transform/Behaviors/Effects/Masks inspector, playback,
  undo/redo, layer duplicate/delete, drag-based layer reorder/parenting, and
  direct layer-bar move/trim editing. The graph panel can switch among
  Position, Scale, Rotation, Opacity, and Anchor Point and dragging a graph
  keyframe updates the shared composition document through the same undoable
  controller used by the inspector and AI actions.
- A top-toolbar language selector uses the shared Tiger Studio
  `en`, `ko`, `ja`, `zh`, `fr`, and `de` application preference; switching
  language retranslates the open authoring window, tabs, toolbar, high-traffic
  panels, tooltips, template gallery, Unreal Link dialog, and project
  open/save prompts without rebuilding the composition. Missing translations
  fall back to authored English rather than altering project data. Locale is a
  user preference and is never serialized into `.tgmotion` or `.tgp`.
  Automation uses `motion.ui.language.get` and `motion.ui.language.set`.
- Image layers expose `tilt_x`, `tilt_y`, and `perspective` beside ordinary
  transform controls. Each control can create source-parameter keyframes; the
  Layer Timeline paints their diamonds and the Graph panel edits their curves
  through the same document controller. Changing a static value preserves
  existing source keyframes instead of replacing the animated property.
- The timeline transport is fixed immediately left of the timecode and exposes
  visible start, reverse-play, stop, forward-play, loop, and end controls.
  Forward and reverse playback use elapsed wall time; non-looping playback
  stops at the composition boundary, while loop mode wraps in either direction.
  Keyboard transport uses `J` reverse, `K` stop, `L` forward, and `Ctrl+L` loop.
- Preview and export consume the same render graph and premultiplied-alpha
  compositor in `app/motion_designer/render_graph.py` and
  `app/motion_designer/compositor.py`. The interactive presenter is a
  persistent `QOpenGLWidget`; file export renders the same graph to RGBA.
- Supported shared-render features currently include normal/add/screen/
  multiply blends; rectangle/ellipse masks; alpha/luma track matte;
  per-layer brightness/contrast, saturation, Gaussian and directional blur,
  glow, unsharp, vignette, drop shadow, light sweep, deterministic animated
  fractal noise, posterize, displacement, corner pin, mesh warp, paper fold,
  and keying effects; and adjustment layers. Effect and mask parameters are
  serializable animated properties. Vector and typography GPU renderers must
  reject an active effect stack and use the shared raster graph rather than
  drawing an unfiltered layer. Unreal UMG preflight reports these raster
  effects as explicit deterministic-bake requirements; it never silently
  removes them from generated output.
- Adjustment layers default to the backward-compatible `all_below` scope.
  Their Effects inspector can switch to `selected_layers_below` and check
  specific renderable layers below the adjustment. Selected scope effects are
  evaluated on each chosen layer surface before it is composited, leaving
  unselected layers unchanged; invalid, non-rendering, self, and above-layer
  IDs are removed by the shared scope contract. Preview and export use the
  same render graph, while Actions/MCP use
  `motion.adjustment.scope.get/set`.
- Group layers may own a reusable effect stack scoped to all renderable
  descendants or an explicit subset of descendants. Group effects are applied
  to each target layer surface after that layer's own effects and before
  scoped adjustment effects; outside and invalid IDs are filtered. The Effects
  inspector exposes `All Descendants` and `Selected Descendants`, and
  Actions/MCP expose `motion.effect_group.scope.get/set`. Preview and export
  use the same scoped stack. OpenGL-only preview backends explicitly fall back
  to the shared raster graph when an effect group is active.
- Numeric rows in the Effects and Masks inspectors expose keyframe diamonds.
  The diamond adds, updates, or removes a keyframe at the selected layer's
  local time after in-point, source-time, reverse, and time-remap conversion.
  Moving the playhead evaluates animated values back into the controls without
  replacing their keyframe curves. Editing a parameter that is already
  animated updates the current local-time keyframe instead of flattening it.
  Actions/MCP expose the same boundary through
  `motion.effect.keyframe.set/delete` and
  `motion.mask.keyframe.set/delete`; keyframe deletion requires destructive
  confirmation.
- Motion masks support rectangle, ellipse, and animated Bezier paths with
  animated feather, expansion, and opacity. Point/planar tracking caches are
  interpolated by the Qt-free `mask_tracking.py` core and applied by the same
  `mask_adapter.py` path in preview and export. `tracking_provider.py` can now
  generate those samples from the current mask ROI in a source video using
  Shi-Tomasi/LK optical flow, forward-backward rejection, and RANSAC partial
  affine estimation. It records confidence/source revision metadata and stops
  at detected shot cuts instead of carrying a false transform into the next
  shot. The Masks Inspector runs generation in a cancellable worker thread and
  exposes mode, progress, failures, and cached sample count. Automation uses
  `motion.mask.path.set`, `motion.mask.keyframe.set`,
  `motion.mask.tracking.set`, `motion.mask.tracking.generate`, and
  `motion.mask.tracking.clear`. Reversed Motion layers remain an explicit
  unsupported case for automatic generation; imported caches still work.
- The base Vector Shape Engine is implemented in
  `app/motion_designer/vector_shapes.py` and
  `app/motion_designer/vector_tessellation.py`. It supports rectangle,
  rounded rectangle, ellipse, polygon, star, and open/closed cubic-Bezier
  paths; winding/even-odd fill; solid or linear/radial-gradient fill; stroke
  width/dash/cap/join; union/subtract/intersect/exclude Boolean geometry;
  Trim Path; and bounded transform/opacity Repeaters. Deterministic path
  flattening is Qt-free, while QPainterPath construction and Boolean results
  use a revision-sensitive bounded cache at the renderer boundary.
- Vector-only Preview graphs use `vector_gpu.py` to tessellate the final
  QPainterPath fill and stroke into cached triangles, then
  `vector_gpu_renderer.py` keeps those meshes in raw OpenGL VAO/VBO resources.
  Layer transform, anchor, opacity, and Repeater instances are GPU uniforms, so
  repeated frames with unchanged geometry do not upload the VBO again. GPU
  packets are Preview opt-in and are not built by export or main composition.
  Radial gradients, effects, masks, mattes, unsupported blend modes, and
  non-vector nodes report a reason and fall back to the shared Painter graph.
- Fill-only typography Preview graphs use a bounded raster glyph atlas in
  `typography_gpu.py` and persistent OpenGL textures in
  `typography_gpu_renderer.py`. `typography_layout.py` shapes complete lines
  with Qt `QTextLayout`/`QGlyphRun`; glyph bitmaps are cached by the resolved
  raw font, contextual glyph id, and source cluster. Animated per-glyph
  transform, color, and opacity are evaluated without rebuilding the atlas.
  Arabic joining forms, ligatures, and mixed RTL/LTR positions therefore stay
  shaped in both Painter export and GPU Preview. Page revisions prevent
  unchanged frames from re-uploading texture data. The Windows GL QA records
  `backend=motion_typography_gpu`, `gl_error=0`, one initial texture upload and
  no repeated-frame upload, contextual Arabic glyph ids and valid source
  indexes, with mean Painter RGB error below `0.2/255`.
  Stroke, shadow, background, effects, masks, mattes, unsupported blends,
  atlas capacity overflow, and mixed non-typography graphs fall back to the
  shared Painter path without dropping glyphs. File export remains on that
  common Painter path. GPU glyph fragments are clipped to the local text-layer
  rectangle so fixed-height wrapping matches Painter/export boundaries.
- Vector Inspector can link multiple shape layers as live Boolean operands and
  select union, subtract, intersect, or exclude while optionally retaining the
  operand layers in the final picture. Stable `operand_layer_ids` are stored;
  `boolean_layers.py` resolves current operand time, hierarchy transform, and
  anchor into target-local paths for Canvas, preview, and export. Missing,
  non-shape, self, and cyclic links fail validation. AI/MCP callers use
  `motion.vector.boolean.layers.set` for the same operation.
- The Canvas shows anchor and in/out tangent handles for a selected Path.
  Dragging updates the shared document, double-clicking inserts an anchor on
  the nearest segment, and Delete removes an anchor or resets a selected
  tangent. The Shape Inspector edits primitives, fill/stroke, Trim Path, and
  Repeater parameters. These edits remain undoable through the same document
  controller used by other Motion Designer panels.
- Motion Designer inspector chrome is dark-only. A near-white scroll viewport
  or content surface is a visual regression, not an alternate theme. The
  Vector Inspector sets explicit dark palettes for its panel, viewport, and
  content, while `tools/qa_motion_ui.py` fails capture QA when sampled inspector
  chrome crosses the allowed brightness threshold.
- Advanced typography reuses the existing Tiger Studio animation registry
  through the Qt-free selector/timing adapter in
  `app/motion_designer/typography_motion.py`. Text layers support IN/HOLD/OUT
  animation IDs, character/word/line selectors, normalized selector ranges,
  reverse order, per-unit stagger, and per-glyph opacity/position/scale/
  rotation/color output. Korean/CJK and combining sequences use grapheme-aware
  selection instead of raw byte or UTF-16 indexing.
- `app/motion_designer/adapters/typography.py` supports multiline wrapping,
  alignment, tracking, line height, outline/shadow/background, bounded glyph
  path caching, variable font `wght`/`wdth` axes, and text-on-Bezier-path
  layout. `app/motion_designer/typography_fonts.py` resolves installed font
  fallbacks and reports missing families or invalid variable-axis tags.
  The Text Inspector exposes style, variable axes, IN/HOLD/OUT animation,
  selector, range, reverse, and stagger controls.
- `tests/test_motion_typography_shaping.py` loads a real contextual font and
  verifies Arabic joining glyph ids, RTL positions, source-index mapping,
  mixed-direction Painter/GPU layout reuse, and shaped text-on-path. The real
  Windows OpenGL check is `tools/qa_motion_gpu_typography.py`.
- Motion Clips can be placed, moved, trimmed, split, duplicated, looped,
  previewed over video, saved/reopened, and baked into final video export.
  An inactive Motion Clip does not allocate its renderer.
- Existing Tiger Studio `TextClip` and PPT `SlideElement` data can be imported
  through `app/motion_designer/content_bridge.py`. Supported text/image/shape
  layers can be converted back to a PPT element. The Qt-free
  `app/motion_designer/ppt_animation_bridge.py` round-trips native PPT
  `appear`, `fade_in`, `fade_out`, `move`, and `scale` effects through Motion
  behaviors while preserving start/duration, easing, trigger, click index, and
  the original in/out slot. Imported entrance effects remain hidden before
  their start and retain their terminal state. Effects, masks, hierarchy,
  blend modes, multiple or unsupported behaviors, transform keyframes, and
  native-range overflow return explicit bake warnings rather than being
  silently discarded. `app/pptgen/writer_ooxml.py` also emits timing XML for
  out-only animations.
- Motion automation is registered in `app/actions/motion_namespace.py` and
  implemented by `app/actions/editor_adapter_motion.py`; focused M7 audio
  operations live in `app/actions/editor_adapter_motion_audio.py`. UI and AI mutations
  use the same composition model and validation rules. Vector automation uses
  `motion.vector.path.set`, `motion.vector.primitive.set`,
  `motion.vector.boolean.set`, `motion.vector.trim.set`,
  `motion.vector.repeater.set`, and `motion.vector.param.keyframe.set`.
  Typography automation uses `motion.typography.style.set`,
  `motion.typography.animation.set`, `motion.typography.text_path.set`,
  `motion.typography.text_path.clear`, `motion.typography.text_path.offset.set`,
  `motion.typography.param.keyframe.set`, and
  `motion.typography.preflight`.
- Motion Designer's Audio tab analyzes WAV directly and other supported audio or
  video containers through FFmpeg on a background worker. The serializable cache
  stores amplitude, bass, mid, treble, onset, beat markers, timeline offset, and
  a SHA-256 signature over source path/size/mtime/explicit revision. Reusing a
  changed source through the action surface is rejected until it is analyzed
  again; frame evaluation never runs an FFT.
- A selected layer can bind one cached channel to Position, Scale, Rotation,
  Opacity, or Anchor using replace/add/multiply mapping with output range,
  smoothing, attack, release, invert, and clamp controls. The compiled curve is
  evaluated in composition time after ordinary behaviors, so Preview, main video
  composition, and file export share the same result. Bake samples that result
  into ordinary transform keyframes and removes the live audio bindings and
  behaviors captured by that bake.
- Composer imports exact BPM beat markers, section/intensity ranges, and MIDI
  note events with priority over estimated beat markers. Voice Lab imports
  sentence, word, and phoneme intervals; missing word intervals are distributed
  deterministically within their sentence. Text layers can reference these
  events for word reveal, while Live2D/Spine/VRM-style actor layers receive the
  same source ID and lip-sync cue list.
- M7 automation IDs are `motion.audio.analyze`,
  `motion.audio_reactive.bind`, `motion.audio_reactive.update`,
  `motion.audio_reactive.bake`, `motion.composer.import_timing`, and
  `motion.voice.import_timing`. `tools/qa_motion_audio_sync.py` verifies a
  600,000ms/30fps fixture with zero-frame envelope drift and the same evaluator
  matrix in Preview's shared render graph and RGBA export.
- Motion Designer AR/PBR support is implemented as an adapter over Tiger
  Studio's existing OpenGL renderer, not as a parallel software 3D renderer.
  `ar_pbr`, `camera`, and `light` Motion layers are serialized and evaluated at
  composition time; camera FOV/target/focus, object transform/material values,
  HDRI exposure, one key-light color/intensity, PCF shadow, contact AO, bloom,
  depth of field, and explicit depth groups are authorable from the 3D
  Inspector and Action surface.
- AR/PBR object sources default to bounds-based Auto Frame so differently
  scaled GLTF/GLB/FBX assets remain visible. It can be disabled per source.
  Camera rotation currently maps to inverse model orbit in the shared
  model-view renderer, and the supported light rig is one key light plus HDRI.
  These are explicit limits, not multi-camera or multi-light claims.
- M8 automation IDs are `motion.ar_pbr.add`,
  `motion.ar_pbr.set_material`, `motion.camera.add`,
  `motion.camera.update`, `motion.light.add`, `motion.light.update`,
  `motion.depth_group.set`, and `motion.ar_pbr.diagnostics`.
  `tools/qa_motion_ar_pbr.py` renders the durable Poly Haven Camera GLTF
  through `full_model_view_gpu_export_service`, rejects fallback, verifies
  texture/shadow/auto-frame/depth diagnostics, and compares same-time Preview
  and Export RGBA. The current Windows evidence records zero differing pixels.
- Motion Designer Live2D/Spine layers share the Qt-free actor source contract
  in `app/motion_designer/actor_source.py`. Both source kinds serialize asset,
  playback, actor transform/opacity, catalog, parameter, and Voice Lab lip-sync
  cue data. The Actor Inspector exposes Live2D motion group/index/expression,
  Spine animation/skin, and shared loop/rate/position/scale/opacity controls.
- `app/motion_designer/adapters/live2d.py` reuses the existing Cubism GPU
  renderer. Stateful motion is evaluated by fixed-FPS reset/forward seeking,
  and a quality-neutral canonical frame cache makes same-time Preview and
  Export deterministic. Motion-owned Live2D clips disable automatic random
  blink/breath so authored motion, expression, parameters, and lip-sync cues
  remain stable; the normal Live2D editor defaults are unchanged.
- `app/motion_designer/adapters/spine.py` reuses the existing Spine renderer.
  Motion Preview and Export currently share its worker-safe full CPU path for
  pixel parity. A default Spine skin whose visual bounds are below 5% of the
  fullest named skin is treated as a guide/effect-only skin and automatically
  resolves to that fuller skin.
- M9A automation IDs are `motion.live2d.add`, `motion.spine.add`,
  `motion.actor.update`, `motion.actor.lipsync.set`, and
  `motion.actor.diagnostics`. `tools/qa_motion_actors.py` serially renders the
  durable Hiyori, Haru, Mao, celestial-circus, chibi-stickers, and
  mix-and-match samples. It rejects blank/near-blank results and currently
  records zero Preview/Export channel differences for all six models. The same
  run captures the real Motion Designer Actor Inspector and rejects a light
  inspector viewport regression.
- M9A does not claim raw/encrypted Unity AssetBundle extraction. Spine
  lip-sync timing is attached to the actor source, but generic per-rig mouth
  slot/attachment inference is not implemented. A supported model/skeleton,
  atlas, and texture set is required.
- Motion Designer MMD layers use the Qt-free source contract in
  `app/motion_designer/mmd_source.py`. PMX/PMD/PBX model references, optional
  VMD motion, VMD-camera preference, bounds framing, toon light/shadow/bloom,
  material tuning, IK, physics, GPU skinning, and playback timing are stored in
  one serializable source. The common Motion layer transform and opacity remain
  responsible for composition placement and alpha.
- `app/motion_designer/adapters/mmd.py` reuses the existing
  `project_player_mmd_workflow` packet generator and
  `MMDOffscreenGLRenderer`; it does not introduce a software MMD renderer.
  Preview and Export share a bounded, quality-neutral canonical RGBA frame
  cache, so the same source revision, composition revision, viewport, and
  quantized time produce identical pixels.
- The MMD Inspector exposes VMD replacement, loop/rate, VMD camera, IK,
  physics/backend/spring response, GPU skinning, framing, bloom, key/fill/rim/
  ambient/shadow, and skin/hair/eye/lip/matcap/emissive controls. It reports
  `Cache pending` before a frame exists and the actual cache, GPU, and physics
  backend state afterward. The inspector viewport is dark-only.
- M9B automation IDs are `motion.mmd.add`, `motion.mmd.update`,
  `motion.mmd.motion.set`, and `motion.mmd.diagnostics`. Validation rejects
  missing/unsupported model or motion paths, reports static-pose VMD absence,
  records bounds-framing fallback when camera frames are absent, and identifies
  the SDEF precision CPU path instead of claiming GPU-only deformation.
- `tools/qa_motion_mmd.py` renders durable Cantarella, Alice, and Miku assets
  through the real MMD OpenGL renderer. The current Windows evidence verifies
  nonblank and temporally changing frames, GPU skinning/IK/spring physics,
  transparent/cutout materials, self-shadow receivers, bloom, VMD camera, zero
  missing textures, and zero same-time Preview/Export channel differences. It
  also captures the actual dark MMD Inspector. Evidence is regenerated under
  `debugCapture/motion_designer/mmd`.
- M9B does not claim Bullet-exact physics: `auto` may resolve to PyBullet when
  installed or the spring backend otherwise, and the current Motion evidence
  uses spring. Camera-only and dance VMD files are not merged by a multi-VMD
  authoring UI, and the three Motion evidence models do not include an SDEF
  visual sample even though the existing MMD runtime supports that path.
- Motion Designer VRM layers use the Qt-free source contract in
  `app/motion_designer/vrm_source.py`. The source stores a validated `.vrm`
  profile, explicit head/shoulder/mouth/blink pose, source-person exposure,
  bust-up/half/full-body framing, placement, MToon lighting, and cache timing.
  Source exposure is resolved through
  `match_source_person_exposure_to_vrm_visibility`; narrower requested framing
  is upgraded unless an explicit allow-narrower override is stored.
- `app/motion_designer/adapters/vrm.py` exclusively reuses
  `app.vtuber.internal_vrm_fallback.render_internal_vrm_fallback_frame()` with
  `renderer=vrm_mtoon_gpu`. Motion VRM does not select a software renderer or
  route the avatar through generic AR/PBR/Marmoset shading. Preview and Export
  share a bounded, quality-neutral canonical RGBA frame cache.
- `app/vtuber/internal_vrm_fallback.py` accepts an optional direct
  `motion_frame`. Existing broadcast CSV/idle callers are unchanged when that
  field is absent. Direct pose drives upper-body/head curves and face morphs;
  full-body Motion framing adds a relaxed standing arm pose instead of exposing
  the imported T-pose. Alpha bounds are cropped, scaled, centered, and anchored
  to the lower safe edge by the existing autofit path.
- The VRM Inspector exposes source exposure/framing, procedural idle/rate,
  head and shoulder pose, mouth/blink, output size/center/bottom anchor, and
  MToon light controls. It reports cache state and uncached render duration and
  remains dark-only. M9C automation IDs are `motion.vrm.add`,
  `motion.vrm.update`, `motion.vrm.pose.set`, and `motion.vrm.diagnostics`.
- `tools/qa_motion_vrm.py` uses the durable Milica VRM0 and the actual
  `vrm_mtoon_gpu` path for full-body and bust-up open/blink/speak poses. Current
  Windows evidence records no software renderer, 50,622 temporally changed
  pixels, visible alpha, lower-edge anchoring, a dark VRM Inspector, and exact
  same-time Preview/Export pixels under `debugCapture/motion_designer/vrm`.
  The first uncached 320x320 frame measured about 15.6 seconds, subsequent new
  poses about 3.2-5.2 seconds, and same-time cache hits about 0.0005 seconds.
  This is a pre-cache authoring path, not a realtime-rendering claim. The QA
  validates Milica VRM0, not universal third-party humanoid/expression/spring
  compatibility or full-body mocap.
- The Text Inspector exposes Follow Path, normalized Offset, and Reset Curve.
  For the selected text layer, the Canvas renders the actual curved typography
  plus its Bezier guide, anchor/tangent handles, and draggable offset marker.
  Double-click inserts a path point and Delete removes the selected point or
  tangent. These edits use the document controller and remain undoable.
- Motion Designer includes a dockable multimodal `AI Workspace` implemented by
  `app/motion_designer/ui/ai_panel.py`. One prompt surface accepts typed or
  dropped text, local image/text/audio/video files, and pasted clipboard images.
  References remain visible as removable items. `Plan` creates a
  reviewable proposal without mutating the composition; `Apply` commits all
  proposed layers as one document-controller undo step.
- The shared Qt-free request/proposal contract is
  `app/motion_designer/ai_workspace.py`. The versioned brief, beat storyboard,
  editable composition compiler, and scoped patch contracts are implemented in
  `app/motion_designer/ai_generation.py`. Motion generation uses the existing
  Tiger Studio provider selection/readiness boundary in `app/ai_providers.py`:
  a provider can return only structured JSON, never mutate a project, and its
  output must pass the Motion schema validator before it reaches Review.
  Provider failure falls back explicitly to a deterministic validated plan.
  The AI panel runs provider planning off the UI thread and continues to use
  `Apply` as the single document-controller mutation point.
- `motion.ai.plan/apply` remain the v1 compatibility actions. New Action/MCP
  endpoints are `motion.ai.provider.status`, `motion.ai.reference.analyze`,
  `motion.ai.brief.create`, `motion.ai.storyboard.generate`,
  `motion.ai.candidate.generate`, `motion.ai.candidates.generate`,
  `motion.ai.candidate.preview`, `motion.ai.layer.*`,
  `motion.ai.background.inpaint`, `motion.ai.background.replace`,
  `motion.ai.text.reconstruct`,
  `motion.ai.choreography.plan/apply`, `motion.ai.integrity.validate`,
  `motion.ai.patch.plan`, `motion.ai.patch.apply`,
  `motion.ai.provenance.inspect`, and `motion.ai.continuity.validate`.
  Image source automation uses `motion.image.param.set`,
  `motion.image.param.keyframe.set`, and
  `motion.image.param.keyframe.delete`.
  Candidate generation does not change the composition;
  candidate apply or patch apply is reviewed and committed as one revision.
  Patch plans are restricted to registered layer IDs and the allowlisted text,
  timing, transform, image-source parameter, behavior, and visibility
  operations, with stale-revision rejection. Layered-image generation uses
  source alpha, Basic Local, or
  optional SAM segmentation behind one provider contract; mask integrity,
  background reconstruction limits, OCR confidence gates, parent/rigid/pivot/
  z-order graph data, and first-frame reconstruction validation are recorded in
  the regenerable manifest. The AI dock creates selectable Clean, Dynamic, and
  Collage treatments off the UI thread and presents them in a horizontal
  candidate strip. Representative frames and thumbnails are rendered through
  the shared Motion renderer and reused from a content-hashed preview cache.
  Follow-up prompts produce a scope-aware patch diff with before/after values,
  reasons, affected layers, and affected time range before one-revision apply.
  `Refine Layers` supports original/
  reconstruction comparison, add/remove mask brush, merge/split, lock,
  parenting, pivot, and ordering, then recompiles only the reviewed candidate
  before the existing single Apply/Undo transaction.
  Basic Local is not claimed as universal semantic instance segmentation.
  When `auto_detect_objects` is enabled without a configured local semantic
  detector, OpenCV proposes reviewable generic foreground regions only. It
  does not invent character, limb, product, or vehicle labels. A user-installed
  Ultralytics-compatible checkpoint can provide semantic labels through
  `TIGERSTUDIO_OBJECT_DETECTOR_MODEL`; Tiger Studio never downloads that model
  implicitly.
  A decomposition request can carry named normalized `object_hints`, including
  optional foreground/background points. Basic Local runs an independent
  GrabCut pass for each box, preserves reviewed disconnected components such
  as legs or accessories, and retains labels plus optional parent, part, rigid,
  and pivot data in separate editable RGBA/mask layers. This enables reviewed
  part rigs without heuristic limb naming. Edge-aware local trimap matting
  preserves soft boundary alpha; it is
  not claimed as learned hair matting. A reviewed
  clean background plate can replace weak large-hole local inpainting through
  `motion.ai.background.replace`. Image layers evaluate animatable `tilt_x`,
  `tilt_y`, and `perspective` source parameters in the shared Preview/Export
  renderer, providing independent X/Y perspective tilt in addition to normal
  position, scale, and Z rotation.
  Motion AI now treats OpenCV GrabCut as an explicit `Legacy Basic`
  compatibility mode rather than the normal quality path. The recommended
  local stack is BiRefNet-matting for automatic soft-alpha cutout and SAM 2.1
  Hiera Small for point/box-assisted masks. Their readiness contract lives in
  `app.motion_designer.segmentation_setup`; models are stored durably under
  `external/assets/motion_ai/models` and optional Python packages under
  `external/tools/motion_ai/python_packages`, never `debugCapture`. The
  installer does not modify the editor's primary Python package directory.
  When either model
  is unavailable, the Motion UI labels it `not installed`, exposes a
  consent-gated `Install cutout AI` action, and blocks normal Auto apply
  instead of silently presenting GrabCut as an AI result. Installation plans
  and status are also exposed through
  `motion.ai.segmentation.setup.status/plan/install`; install requires explicit
  `confirm=true`.
  Every extracted RGBA foreground is evaluated by the shared
  `tigerstudio.motion.cutout_quality.v1` contract before it can be compiled
  into independently animated Motion layers. The deterministic gate rejects
  empty or fully opaque plates, near-full-frame foreground masks, and long
  low-contrast alpha boundaries that remain connected to the source
  background. Bright neutral edge spill, detached fragments, and source-frame
  crop risk remain explicit review warnings because they cannot be classified
  semantically with certainty. Cached decompositions and every manual
  merge/split/mask edit are reevaluated under the current contract. Failed
  extraction remains visible and repairable in the layer-review UI, but its
  repaired-layer Apply action stays disabled and normal choreography compile
  fails before the bad cutout reaches Preview or Export. Automation can inspect
  the same report through `motion.ai.cutout.quality.validate`; bypass requires
  the explicit `allow_quality_override=true` argument and is never implicit.
  Reviewed, separated body parts can be converted into an editable 2D cutout
  arm rig through the Motion toolbar `Rig > Arm Wave...` or Python Action
  `motion.cutout_rig.arm_wave.create`. The contract uses four aligned
  transparent layers (torso, upper arm, forearm, hand), composition-pixel
  shoulder/elbow/wrist pivots, and a torso -> upper arm -> forearm -> hand FK
  hierarchy. It writes ordinary anchor, parent, and rotation keyframes for
  lift, repeated wave, and lower phases, so the result remains editable and
  uses the same hierarchy evaluation in Preview and Export. This is rigid 2D
  cutout articulation; it does not claim Live2D mesh deformation, automatic
  limb recognition, inverse kinematics, or hidden-joint texture synthesis.
  `motion.cut_paper.create` separately creates an editable five-layer
  cut-paper treatment with a hole matte, released paper piece, edge shadow,
  trimmed fiber line, and path-following scissors.
  Audio references are decoded by the existing deterministic analyzer and
  contribute beat markers to generated choreography. Video references are
  sampled by OpenCV Farneback flow; restrained camera/layer motion is converted
  to editable image tilt/perspective curves. This is not body-pose or character
  performance transfer. Image references expose a deterministic palette,
  luminance, and orientation profile; generated native title cards and text
  derive restrained foreground/background colors from that profile. This is
  palette-and-tone transfer, not identity or full visual-style synthesis.
  Proposal and scoped-patch application append bounded conversation history,
  preserve existing layer/source/reference identity, validate hierarchy and
  timing continuity, and record local reference fingerprints in composition
  metadata. The manifest is inspectable but is not cryptographically C2PA
  signed. External image/video generation can feed its output back through the
  same reference contract, but the base installation does not claim Gemini
  Omni-equivalent pixel generation, arbitrary object insertion, environment
  synthesis, or physical-scene generation.
  Missing SAM or enhanced inpainting reports an explicit local fallback;
  cloud image transfer is not performed without a future consented provider.
  The detailed product boundary and QA corpus are defined in
  `docs/MOTION_AI_LAYERED_IMAGE_PRODUCT_PLAN_KO.md`.
- Motion Designer M10 adds safe structured expressions, deterministic
  particles, ten built-in templates, broadcast cost/cache preflight, and AI
  proposal analysis. `expressions.py` evaluates a bounded JSON operation tree
  with dependency-cycle detection and keyframe bake; it never executes Python
  or JavaScript strings. `particles.py` is the one simulation source for
  Preview, Export, actions, and alpha bake. Circle/square/triangle particles use
  the real OpenGL vector packet path; sprite particles currently use the
  canonical premultiplied-alpha renderer and are reported as a broadcast bake
  requirement instead of being mislabeled GPU-native.
- `templates.py` provides Clean Lower Third, Character Nameplate, Logo Reveal,
  Product Callout, Stream Stinger, Music Beat Title, Vertical Shorts Hook,
  Anime Character Intro, MMD Dance Title, and VRM Stream Starting/Ending with
  supported 16:9/9:16/1:1 variants. Published IDs are stable:
  `headline`, `subtitle`, `accent_color`, `surface_color`, and `duration_ms`.
  `tools/qa_motion_template_catalog.py` production-renders all ten templates and
  verifies animation, validation, and control IDs.
- `broadcast_bridge.py` grades a composition `realtime`, `cached`, or
  `offline_only`. Cached Program Output requires a current-revision,
  premultiplied-alpha frame manifest and valid path. Live template controls
  invalidate stale caches; `motion.broadcast.stinger.render` writes a real RGBA
  PNG sequence and registers its manifest. `ai_planner.py` adds projected layer
  count, renderer cost, missing assets, bake/cache requirements, and validation
  to the same dry-run proposal shown by the AI Workspace and Python Actions.
- `tools/qa_motion_ui.py` renders the real Qt authoring window at 1600x900 and
  1280x720 into disposable `debugCapture/motion_designer` screenshots for
  layout regression review. These captures use an actual composition with
  layers, behaviors, effects, timeline bars, and keyframes rather than a UI
  mockup. It also saves a shared-render-graph PNG of the Vector QA scene so
  Trim Path and Repeater output are checked independently of offscreen
  `QOpenGLWidget` capture support.
  The same tool captures the real docked AI workspace with an actual attached
  frame, generated proposal, applied layers, and undo-capable document state.
- `tools/qa_motion_ai_review_ui.py` opens the actual Motion Designer window,
  generates three candidate compositions, renders and caches their thumbnail
  previews, applies one candidate, and displays a conversational patch with
  before/after values and affected time range. Candidate application and patch
  application remain separate reviewable document revisions.
- `tools/qa_motion_gpu_vector.py` opens a real Windows desktop OpenGL context,
  captures the linked-Boolean scene in the actual Preview tab, requires the
  `motion_vector_gpu` backend with zero GL errors, verifies stable VBO upload
  count across repeated paints, and compares the framebuffer against the
  Painter reference with mean RGB absolute error at or below `2/255`.
- Motion Designer M11 originally defined the shipping color/output scope as SDR sRGB.
  New compositions carry a `linear-srgb` final-composite contract with straight
  alpha at the file boundary and premultiplied alpha internally; legacy
  compositions without color metadata retain display-sRGB behavior. Final
  Motion-over-video compositing decodes encoded sRGB, composites premultiplied
  values in linear space, and encodes sRGB again. The current Qt render graph's
  internal multi-layer blend remains display-space and is reported by output
  preflight. M20 now shares the main-editor ACES/OCIO display transform,
  supports Rec.2020 PQ/HLG through the H.265 10-bit profile, and applies the
  same alpha-safe transform to standalone Preview and Export. The Delivery
  control offers the validated built-in Studio/CG ACES 1.3 configs plus
  external `.ocio` files; missing or invalid runtimes remain blocked with
  explicit diagnostics. Motion standalone Preview and Export now share the
  ordered `Input LUT -> Tone Map -> Creative LUT -> Display/OCIO -> Output LUT`
  runtime in `app.motion_designer.color_runtime`. Delivery exposes Reinhard and
  ACES-fitted tone maps plus three strength-controlled 3D `.cube` slots.
  Missing, malformed, 1D, or non-`.cube` Motion LUTs fail preflight instead of
  being silently omitted. The alpha-safe pipeline unpremultiplies before color
  processing and restores the original alpha afterward; OpenEXR remains
  scene-linear and intentionally bypasses the display/creative delivery chain.
  `tools/qa_motion_color_pipeline.py` proves zero-byte Preview/runtime versus
  actual PNG Export error and zero alpha error. Main-editor Motion-over-video
  compositing remains raw linear-alpha composition followed by the main project
  color transform, avoiding a second Motion delivery transform. Unreal UMG
  output reports non-default
  Motion color management as deterministic-bake-required instead of omitting it.
- `export_profiles.py` and `export_pipeline.py` provide H.264, H.265, ProRes
  4444 alpha, PNG RGBA sequence, OpenEXR scene-linear sequence, and PNG/JPEG/
  WebP still output. PNG sequences resume only already-valid frames and publish
  their manifest only after completion. Canceled video exports remove the
  `.partial` file and retry from the beginning. Lottie/SVG are limited shape/
  text subsets, OTIO is a media-timing reference subset, and glTF/GLB is a
  single AR/PBR-source passthrough subset; lossy features are blocked or marked
  bake-required by preflight.
- `relink.py` resolves moved Motion projects deterministically: it first tests
  the old-root-relative path, then accepts only a unique basename under the new
  root. Ambiguous duplicates are never applied automatically. The same scanner
  covers media, MMD model/motion, actor and AR/PBR sources, font files, and
  particle sprites. `recovery.py` writes atomic SHA-256-protected recovery
  snapshots and rejects damaged, stale, or wrong-composition payloads unless an
  explicit override is supplied.
- `release_acceptance.py` keeps render readiness separate from product release
  readiness. Product evidence requires real standard-output artifacts, color/
  alpha golden output, desktop OpenGL Preview/Export parity, a 30-minute
  wall-clock OpenGL burn-in, 1,000-layer and 10,000-keyframe stress, 500-cycle
  undo/redo plus recovery, queue cancel/resume/retry, GPU context recreation,
  deterministic project relink, and an installed-build smoke test. The evidence
  is regenerated by `tools/qa_motion_release_acceptance.py`; installer and GPU
  evidence may not claim a software renderer.
- The 2026-07-22 M11 release run completed the real 30-minute desktop OpenGL
  burn-in with 80,723 frame swaps at 44.84 average FPS, 8,896,512 bytes of RSS
  growth, `motion_vector_gpu`, a valid context, zero GL errors, and no software
  renderer. The current-source Inno installer installed 516 files, launched a
  visible `Tiger Studio` window, and uninstalled cleanly. All 41 Motion test
  files passed independently (215 tests), and the final evidence aggregate has
  no missing release evidence with `product_release_ready=true`.
- Motion Designer M12 now exposes ownerless Action/MCP management endpoints:
  `motion.plugin.list`, `motion.plugin.inspect`, `motion.plugin.validate`,
  `motion.plugin.enable`, `motion.plugin.disable`,
  `motion.template_pack.validate`, and `motion.template_pack.install`.
  `plugin_manifest.py` and `plugin_registry.py` validate a versioned declarative
  manifest, API major, capabilities, dependencies, duplicate IDs, and JSON-only
  contribution descriptors without importing plugin code. Enable state is
  written atomically and reports `runtime_loaded=false` plus
  `restart_required=true`.
- `template_pack.py` validates directory, manifest, and ZIP packs before
  installation. It blocks archive traversal, symbolic links, executable
  content, excessive file/byte counts, invalid aspect variants, duplicate
  published controls, missing license metadata, and invalid Motion composition
  JSON. Confirmed installs use staging and atomic rename into durable per-user
  storage; `debugCapture` is rejected as an installation destination.
- This is the M12 management and automation foundation, not a claim that
  third-party source/effect/behavior/exporter code is already hosted. Runtime
  contribution registration, sandbox/failure isolation, uninstall, and safe
  mode remain pending. These M12 source changes require a fresh installer build
  and installed-build smoke before they are included in a public binary.
- Motion Designer advanced editorial direction is implemented across the shared
  Preview/Export render graph. `app/motion_designer/advanced_motion.py` projects
  ordinary 2D layers through an explicitly enabled Camera layer using editable
  `depth_z`, FOV, camera position, roll, and parallax strength. AR/PBR camera
  behavior is unchanged because `apply_to_2d` is off by default.
- Any renderable image, text, vector, actor, or particle layer may use the
  renderer-neutral metadata `replicator` contract. The independent Replicator
  Inspector and Library presets expose line, grid, and radial arrangements,
  count, grid columns, offset/radius, per-copy rotation and scale, opacity
  falloff, deterministic jitter, and seed. This is separate from the existing
  vector-path Repeater and is composited before track matte output. Canvas,
  OpenGL Preview, file export, and main-timeline Motion Clip rendering consume
  the same evaluated instance list. Per-layer movement-derived motion blur uses
  bounded temporal samples and shutter values in the same shared render graph.
- Motion Designer supports independent procedural Generator layers for solid
  color, two-color linear gradient, checkerboard, grid, deterministic noise,
  and radial rays. Generator dimensions, colors, scale, angle, offset, seed,
  detail, and contrast are serialized in `.tgmotion`, validated, and rendered
  through the common source adapter in Canvas, Preview, and export. Library and
  Add Object can create Generator layers; Actions/MCP uses
  `motion.generator.create` and `motion.generator.update`.
- Alpha and luma track mattes remain stable layer-ID references and now have
  dedicated `motion.matte.set/clear` actions and `Motion` Inspector controls.
  The Motion Inspector exposes 2.5D depth and motion blur; Replicator is a
  dedicated page while the former compact controls remain compatibility
  aliases that preserve new arrangement fields. Text character/word/line
  animation continues to use the existing typography selector/stagger renderer
  and is exposed to automation through `motion.text.animator.set`.
- The common effect path now includes `directional_blur`, `displacement`,
  `corner_pin`, `mesh_warp`, and `paper_fold` in addition to the existing
  grading, blur, glow, sharpen, and vignette effects. These effects use the same
  source surface in desktop Preview, file export, and main-timeline Motion Clip
  compositing.
- `app/motion_designer/paper_composite.py` creates editable paper shadow, tape,
  staple, fold-shading, impact, and motion-blur layers around a selected source.
  It complements the existing path-trimmed scissors/cut-hole paper rig rather
  than replacing it. The `impact` behavior adds damped landing scale, rotation,
  and positional response.
- The Library `Direction Presets` category and
  `app/motion_designer/advanced_presets.py` provide `Headline Slam`,
  `Paper Rip Reveal`, `Cutout Collage`, `Editorial Camera Push`, and
  `Beat-Synced Montage`. Equivalent automation is available through
  `motion.advanced_preset.apply`, `motion.paper_paste.create`,
  `motion.camera.2_5d.set`, `motion.layer.depth.set`, `motion.blur.set`, and
  `motion.replicator.set`. `Learn 05 - Generators and Replicators` is a
  complete editable tutorial template for the two independent feature paths.
- Motion Designer layers and groups may be converted into reusable interactive
  button components through `app/motion_designer/interactive_button.py`.
  Components persist `Normal`, `Hover`, `Pressed`, `Disabled`, and `Focused`
  transform/opacity states, pointer/focus trigger mappings, bounds-based hit
  padding, transition duration, and easing. The selected preview state is
  evaluated by the same composition evaluator used by Canvas, Preview, export,
  and Motion Clip compositing. Canvas pointer enter/down/up/leave previews use
  a transient 16 ms transition timer that does not add undo entries; committed
  state selection remains deterministic for Preview and export. The dedicated
  `Button` Inspector and toolbar
  `Component > Button` command use the document controller, so creation,
  editing, removal, and undo remain project mutations rather than UI-only
  state.
- Automation uses `motion.button.inspect`, `motion.button.create`,
  `motion.button.update`, `motion.button.state.set`, and
  `motion.button.remove`. The component contract is suitable for authored
  video overlays and downstream interactive exporters; Tiger Studio does not
  yet claim native HTML/Lottie application-runtime export or event execution
  inside a rendered MP4.
- Painter-owned UI objects and Motion-owned animation now meet through the
  versioned `tigerstudio.motion.ui_binding.v1` contract in
  `app/motion_designer/ui_motion_binding.py`. A binding keeps the Painter
  document/object/component stable IDs, Motion target layers and properties,
  component state or transition scope, trigger, animation name, and delivery
  policy without copying the Painter layout or style source of truth into the
  Motion document. Bindings persist under composition metadata and are
  validated with the normal Motion document.
- Automation uses `motion.ui_binding.list`, `motion.ui_binding.set`,
  `motion.ui_binding.remove`, and `motion.ui_binding.preflight`. UMG-native
  transform and opacity tracks are assigned the binding's animation name.
  Supported button pointer triggers generate a `play_animation` interaction;
  material properties, unsupported triggers, missing stable references, and
  conflicting track ownership are reported explicitly by preflight.
- Unreal UMG delivery is a Tiger Studio-owned workflow, not a manual Unreal
  plugin workflow. The shared, provider-neutral plugin source lives at
  `resources/unreal_plugins/UMG/TigerStudioUMG`; it accepts `motion_designer`,
  `painter`, and future providers through one versioned document contract.
  The plugin contains separate `TigerStudioUMG` runtime and
  `TigerStudioUMGEditor` editor modules, and both compile against the canonical
  UE 5.8 installation.
- `app.unreal_umg_plugin` discovers the internal plugin, installs it only into
  `<Project>/Plugins/TigerStudioUMG`, enables it in the selected `.uproject`,
  preserves unrelated plugin entries, and reports whether an Unreal restart is
  required. It must never install into `Engine/Plugins`.
- Private plugin source is not part of the public installer.
  `tools/build_unreal_umg_plugin.py` creates a source-free Win64 bundle under
  `bundled/unreal_plugins/UMG/TigerStudioUMG`, and `TigerCapture.spec` packages
  only that bundle.
- The user-facing entry point must live in Motion
  Designer and expose project selection, compatibility/preflight status,
  `Generate`/`Regenerate`, progress, generated-asset navigation, and real result
  capture. Tiger Studio must internally package the composition, install or
  update its project plugin when required, launch the configured Unreal Editor,
  generate and compile the Widget Blueprint, validate the generated asset, and
  return the report and capture to the same Tiger operation.
- The Unreal plugin is a non-interactive execution backend controlled by Tiger
  Studio. Users must not be required to enable JSON utilities, construct
  structs, run Blueprint parsing nodes, copy files into a project, invoke a
  commandlet, compile a Widget Blueprint, or capture evidence manually.
- Native conversion currently creates Group/Text/Image/Button widget trees,
  imports referenced textures and sounds, normalizes textures for the UI LOD
  group, and converts position/rotation/scale/opacity tracks to
  `UWidgetAnimation`. `UTigerStudioButton` executes clicked/hovered/
  unhovered/pressed/released action records for named event emission,
  animation playback, sound playback, visibility, opacity, and material-scalar
  changes. Font assignment, complete per-state button styling, arbitrary UI
  Material construction, and deterministic mask/effect baking remain explicit
  follow-up scope; unsupported content must fail preflight or be reported as
  baked and must never be silently omitted.
- UMG generation follows one deterministic UE 5.8 pipeline:
  1. validate the Tiger UMG document and resolve stable source IDs;
  2. create or load the destination package and create a `UWidgetBlueprint`
     through `UWidgetBlueprintFactory`;
  3. replace or reconcile the generated `WidgetTree`, using a root
     `UCanvasPanel` and stable widget names derived from layer IDs;
  4. create native `UTextBlock`, `UImage`, `UButton`, panel, and provider
     fallback widgets, then apply anchors, offsets, alignment, z-order, render
     transform, opacity, brushes, fonts, and button styles;
  5. import or reimport textures, fonts, and generated UI Materials into the
     Tiger-generated content root before assigning object references;
  6. create `UWidgetAnimation` and its `UMovieScene`, bind each stable widget,
     and write position/rotation/scale and render-opacity channels using the
     source frame rate and interpolation;
  7. generate button state behavior and named interaction events without
     replacing user-owned Blueprint graphs;
  8. compile through Kismet/Widget Blueprint compiler APIs, save the package,
     reopen and validate the generated class, then capture the actual Unreal
     result.
- Regeneration owns only assets and graph regions marked with Tiger source
  metadata. Stable layer IDs preserve compatible widgets and animation
  bindings; removed Tiger layers are deleted, but user-owned additions outside
  the generated boundary survive regeneration.
- Every future Motion Designer or Painter feature that can be serialized into a
  Tiger UMG document must update the shared plugin conversion in the same
  implementation. A feature must be classified as native UMG, UI Material,
  deterministic bake, or blocked preflight. Silent omission is prohibited.
- The Action/MCP surface provides `motion.umg.plugin.status`,
  `motion.umg.plugin.install`, `motion.umg.preflight`, `motion.umg.package`, and
  `motion.umg.generate`. `motion.umg.generate` performs the complete package,
  project-plugin install/update, Unreal commandlet generation, Kismet compile,
  package save, and generated-asset load validation sequence. Motion Designer
  exposes the same operation through a separate top-toolbar `Unreal Link`
  action using the Unreal Engine logo. It opens `MotionUnrealLinkDialog`;
  Unreal project connection and UMG generation must not occupy an Inspector,
  Library, or Output tab. Dedicated
  visible Unreal capture/navigation remains follow-up scope and uses the shared
  external-window capture actions rather than a second capture implementation.
- UE 5.8 product QA generated
  `/Game/TigerStudio/Generated/qa_interactive_button/Widgets/`
  `WBP_TS_qa_interactive_button` twice consecutively from the same source
  document. Both runs loaded the resulting `WidgetBlueprint`, generated one
  widget and one animation, imported texture and sound assets, and reported no
  compiler or generation errors. The reproducible command is
  `tools/qa_unreal_umg_generation.py`; disposable evidence is written below
  `debugCapture/unreal_umg_generation_qa`.
- Motion Designer exposes a top-level `Templates` action beside its authoring
  tools. `MotionTemplateGalleryDialog` presents production-rendered thumbnails,
  category/search filters, and 16:9, 9:16, and 1:1 variants before applying a
  complete editable template to the current composition. Templates that do not
  support the requested aspect ratio automatically select a supported variant.
  The compact Library template list remains a secondary quick-apply surface,
  not the beginner-facing gallery.
- The built-in catalog contains 24 templates: ten quick production starters,
  five `Learn` templates, and nine multi-scene production packages for
  UI/Product, Advertising, and Education. The production packages cover
  15-, 20-, 24-, 30-, 45-, and 60-second workflows with four to eight
  contiguous scenes. They include explicit media replacement slots, workflow,
  tags, scene count, duration, and replacement checklists. `iOS App UI Motion
  Kit` is a Tiger Studio system-inspired mobile UI package, not an Apple
  official UI kit or bundled Apple design resource.
- The UI/Product package provides app chrome, cards, quick actions, search,
  lists, progress, toggles, notification, bottom-sheet, tab-bar, and CTA
  examples. Advertising templates separate hook, reveal, benefits, proof,
  offer, and CTA beats. Education templates separate module/objective,
  numbered demo, comparison/check, recap, and next-lesson beats. Each scene is
  composed of normal editable Motion layers rather than a flattened preview.
- Selecting a card shows its included features, intended workflow, duration,
  scene count, difficulty, estimated edit time, and replacement checklist.
  Learning cards additionally show ordered hands-on steps. Applying a learning
  template stores the same guide in
  `composition.metadata.motion_tutorial`, marks example layers with tutorial
  roles/steps, and exposes the metadata through the existing
  `motion.template.list/inspect/apply` Action/MCP contract.
- Applying another template from the gallery or compact Library replaces only
  the previous template instance. User-authored layers remain intact, so
  repeated selection does not accumulate hidden template layers or degrade
  playback. `motion.template.apply` follows the same default and reports added
  and removed layer IDs; automation may explicitly pass
  `replace_existing=false` when stacked template instances are intentional.
- A template change always resets the Motion Designer playhead to zero. If
  forward playback is active, playback remains active and the elapsed-time
  clock restarts from the first frame of the new template rather than
  continuing from the previous template time.
- `tools/qa_motion_template_catalog.py` renders every catalog entry plus a
  representative frame from every scene through `MotionExportRenderer`.
  Catalog QA fails on invalid compositions, non-animated templates, unstable
  published controls, or missing catalog entries. Expansion priorities and
  acceptance criteria are recorded in
  `docs/MOTION_TEMPLATE_CATALOG_STRATEGY_KO.md`.
- These tools provide editable 2.5D editorial motion and deterministic
  distortion; they do not claim a full 3D scene graph, arbitrary user-authored
  displacement video maps, cloth simulation, or After Effects plugin parity.
- The post-M12 professional motion-graphics roadmap is recorded in
  `docs/MOTION_DESIGNER_AE_GAP_MILESTONES_KO.md`. M13-M20 cover full-body
  cutout rigging, Puppet mesh deformation, nested compositions and advanced
  animation curves, typography/vector motion, video matte/roto/keying,
  tracking/stabilization, unified 2.5D/3D composition, and product-scale
  effects/color/templates. The 2026 style and market gap analysis is recorded
  separately in `docs/MOTION_DESIGNER_2026_TREND_MILESTONES_KO.md`. M21-M28
  add a craft/imperfection style stack, dynamic backdrop glass, mixed-media
  authoring, painterly 2D/3D look development, stop-motion timing, story and
  platform direction, editable AI style direction, and trend-template QA.
  M21-M28 remain product milestones and must not be described as fully
  complete until their schema, Action/MCP, Preview/Export parity, stress test,
  and real artifact gates pass. M21 Craft and Imperfection Style Stack v1 is
  complete:
  `tigerstudio.motion.craft_style.v1` stores deterministic Film Grain, Gate
  Weave, Light Flicker/Warmth, locked seed, and preset metadata in an ordinary
  Motion effect. Subtle Film, Handmade, and Archive Print are available from
  the dedicated Craft Inspector and through
  `motion.craft.get/set/clear`, preset list/apply, durable texture
  attach/relink, seed randomize/lock, and preflight actions. The shared effect
  additionally implements Dust/Scratch, print misregistration, halation,
  warmth, VHS scan wobble, edge roughness, and multiply/screen/overlay texture
  blending. The advanced Craft controls add RGB/mono grain mixing,
  shadow/midtone/highlight response, dust/scratch lifetime, scratch direction,
  and deterministic fibrous-edge strength/length to the same effect and
  Inspector. Preview and export share `effect_adapter`; UMG preflight reports
  `effect_requires_bake:craft_style` instead of silently dropping the look.
  Nine designed presets plus Clean are rendered by
  `tools/qa_motion_craft_style.py`, together with explicit RGB Grain, Angled
  Scratches, and Fibrous Edge samples; automated QA covers 300 frames, zero
  loop boundary jump, deterministic seed, and Preview/Export pixel parity.
- M22 Dynamic Glass core is implemented as
  `tigerstudio.motion.glass.v1`. A `tiger_glass` effect samples the already
  composed layers behind its transformed shape mask and applies deterministic
  backdrop blur, procedural refraction, tint/absorption, thickness,
  edge/specular response, dispersion, and glossy bloom. Clear, Frosted,
  Tinted, Glossy, and Liquid CTA presets are editable in `Look > Glass` and
  through `motion.material.glass.*` actions. Eligible preview graphs use the
  real `motion_glass_gpu` OpenGL backdrop shader. Unsupported graphs explicitly
  report reasons such as `backdrop_glass_requires_raster`; the shared raster
  fallback retains Preview/Export pixel parity. Complex Glass remains a
  deterministic UMG bake candidate and reports
  `effect_requires_bake:tiger_glass`. The v1 Unreal decision is explicit:
  Tiger Glass is not mapped to a native UI Material because UMG cannot sample
  arbitrary sibling backdrop content with equivalent semantics. Direct Widget
  Blueprint generation is blocked with
  `effect_requires_bake:tiger_glass`; deterministic image/video bake is the
  recommended output. Deterministic Glass-only tiled export evidence is
  complete.
  Draft/Preview
  blur now uses a multi-resolution pyramid and glass-mask ROI. The real 1080p
  QA tool records 138-172 ms/frame on the shared CPU fallback after ROI
  optimization, down from 278-374 ms/frame. This is the historical accuracy
  baseline for unsupported graphs, not the current eligible-preview
  performance path.
  `MotionGlassGpuRenderer` applies blur, refraction, dispersion,
  tint/absorption, edge/specular/bloom, and runtime drivers in a fragment
  shader. Ordinary contiguous layer ranges are rendered as shared raster
  segments, while Glass layers ping-pong two non-MSAA FBOs so each pass samples
  the preceding framebuffer without flattening the Glass effect on CPU. The
  FBO pair is reused per viewport size and the GPU working surface is bounded
  to a 960-pixel long edge to avoid unnecessary high-DPI preview cost.
  Eligibility rejects adjustment/precomp, mattes, card shadows, motion blur,
  non-normal blends, effect groups, and additional effects on a Glass layer;
  those graphs keep the accurate shared raster fallback with an explicit
  reason. This is a Glass-effect GPU path, not a claim that the complete Motion
  graph is GPU-native.
  The formal 15.36-second product probe recorded 450 swaps at 29.29 fps,
  one loop, `motion_glass_gpu`, and GL error 0. Its same-time CPU reference
  measured mean RGB absolute error 4.51/255 and p95 8/255 against automatic
  limits of 12 and 36. The final 60.36-second sustained probe recorded 1,601
  swaps at 26.52 fps, four loops, and GL error 0; its same-time reference also
  passed at mean 3.84/255 and p95 10/255. M22 Dynamic Glass v1 is therefore
  complete. Deterministic Final Export continues to use the shared
  full-frame/tiled renderer instead of treating the preview shader
  approximation as pixel-identical export.
- M23 Mixed Media Craft Workspace v1 is implemented around the provider-neutral
  `tigerstudio.motion.collage.v1` contract. A collage board binds existing
  Motion layers to stable item IDs, deterministic layout seed and z-order,
  editable edge treatment, attachment treatment, source revision, and an
  optional Painter link. `Look > Collage` and the `Mixed Media` library expose
  Editorial, Luxury Paper, Education, and Scatter workflows without replacing
  the underlying layers.
- Smart, Polygon, Torn, Feather, and Fiber edges are persisted on each item;
  non-smart edges render through editable path masks. Glue, Tape, Staple, Pin,
  and Fold treatments remain native child layers or an editable `paper_fold`
  effect. The shared `scan_cleanup` effect white-balances scanned paper,
  optionally removes the paper alpha, and preserves dark ink through the same
  Preview/Export effect adapter.
- Motion automation includes `motion.collage.create`, item add/update/reorder,
  edge/attachment/scan set, source replace, Painter send/refresh, and
  preflight. Replacing or refreshing a source preserves the collage item ID,
  Motion layer ID, parent, pivot, timing, source offset, rate, and reverse
  state. Painter exchange uses
  `tigerstudio.motion.collage.painter_handoff.v1`; v1 provides the stable
  handoff contract, while direct live Painter-object creation remains a later
  transport extension.
- The built-in `tigerstudio.motion.collage_asset_pack.v1` adds Cotton Paper,
  Kraft Cardboard, Newsprint, Masking Tape, Black Ink Card, and Graphite Sheet
  as deterministic editable shape/Craft layers with no external binary
  dependency. Beginners can add one from `Look > Collage` before a board
  exists; automation uses `motion.collage.asset.catalog/add`.
- Unreal conversion never silently omits collage semantics:
  `motion_feature_requires_bake:collage_item` requests deterministic bake.
  `tools/qa_motion_collage.py` renders 10-second Editorial Collage, Luxury
  Paper Title, and Education Cutaway scenes through the shared exporter,
  generates a 12-frame contact sheet and timing report, and verifies zero
  stable-ID loss across source replacement and Painter linking.
  `tools/qa_motion_collage_asset_pack.py` renders all six starter materials.
  Frame-drawing exposure/onion-skin UI remains a post-v1 extension.
- M25 Stop-motion Timing and CGI v1 is implemented through
  `tigerstudio.motion.stop_motion.v1`. Composition and layer overrides support
  ones, twos, and threes exposure, locked deterministic pose jitter,
  contact-settle/overshoot/replacement-pop timing, reusable stable-ID poses,
  onion-pose inspection, and audio-transient snapping to the exposure grid.
  The evaluator, Canvas source rendering, Preview, and Export consume the same
  quantized local and composition time instead of applying a cosmetic
  posterize effect after animation.
- Clay, felt, cardboard, and painted-wood treatments remain editable ordinary
  `craft_style` and `drop_shadow` effects with a locked material seed and
  explicit material metadata. They are available under `Look > Stop Motion`
  and through `motion.stop_motion.get/set`, pose capture/apply, material set,
  audio snap, onion inspect, and preflight actions.
- Unreal conversion reports
  `motion_feature_requires_bake:stop_motion` whenever active stepped timing
  cannot be represented natively; it never silently emits continuously
  interpolated UMG animation. `tools/qa_motion_stop_motion.py` renders 6-second
  clay mascot, 10-second miniature product, and 8-second paper replacement
  scenes through the shared exporter. Current evidence records zero cadence
  violations and zero pixel interpolation inside held exposures, while the
  following exposure changes. Physically simulated clay deformation,
  volumetric miniature lighting, and automatic frame sculpting are not M25 v1
  claims.
- M26 Story and Platform Direction v1 is implemented through
  `tigerstudio.motion.story_direction.v1`. A composition can persist ordered
  Hook, Setup, Desire, Conflict, Reveal, Proof, Payoff, and CTA beats with
  stable IDs, time ranges, purpose, emotion, character, copy, visual intent,
  audio cue, scene ID, and linked Motion layer IDs. Story metadata also stores
  audience/message direction, character continuity, and Voice Lab or Music Lab
  bindings with stable source IDs, cue time, and optional tempo.
- The Motion Designer `Story` workspace exposes the core story brief, beat
  creation, imported Voice/Composer timing source selection, selected-beat
  audio binding, visible Voice/Music binding status, and platform preview/apply
  workflow. Automation exposes
  `motion.story.inspect/update`, `motion.story.beat.add/update/reorder`,
  `motion.story.audio.bind`, `motion.platform.variant.plan/preview/apply`, and
  `motion.platform.preflight`.
  `tools/qa_motion_story_audio_ui.py` captures a real Qt Story workspace with
  imported Voice and Composer sources and verifies selected-beat binding state.
- Platform conversion uses the reviewable
  `tigerstudio.motion.platform_variant_plan.v1` contract. The plan is
  non-destructive and records every composition resize, role-aware layer
  position/scale change, animated position/scale keyframe conversion, and
  minimum font-size adjustment. Applying a plan requires explicit human
  approval, rejects stale source revisions, creates a new composition ID,
  preserves layer/keyframe stable IDs, and stores the accepted diff.
- Landscape 16:9, vertical 9:16, and square 1:1 profiles define separate
  content and subtitle safe areas, minimum text size, and CTA hold. Preflight
  checks protected headline/subtitle/CTA/character bounds, text density,
  minimum text size, CTA duration, story ranges, missing layers, beat overlap,
  Hook/CTA presence, and unmotivated character screen-direction changes.
  Platform variants consist of ordinary Motion layers and therefore continue
  through the existing Preview/Export and UMG conversion paths; story metadata
  is authoring direction rather than a visual effect that may be silently lost.
- `tools/qa_motion_story_platform.py` renders one 15-second, eight-beat ad at
  four times in all three aspect ratios through `MotionExportRenderer`.
  Current evidence reports 12 real frames, zero protected-layer clipping, zero
  story issues, zero stable-ID loss, and no mutation of the source composition.
  M26 v1 is a deterministic role/priority constraint reflow. Semantic
  generative art direction remains M27 work; platform copy rewriting now uses
  the separate reviewable M27 contract described below.
- M27 AI Style Director v1 is implemented through the reviewable
  `tigerstudio.motion.ai_style_plan.v1` contract. It separates style intent
  from story intent, records reference provenance, backend availability,
  estimated cost, explicit fallbacks, and five editable candidates: Clean,
  Craft, Collage, Glass, and Stop Motion. The shared Claude provider context
  may inform planning when available, while the v1 style compiler remains a
  deterministic local path that can run without AI.
- `tigerstudio.motion.ai_semantic_style_direction.v1` adds provider-backed
  candidate recommendation without granting mutation access. It may return
  only one recommended style, a complete ranking of the existing five style
  IDs, concise per-candidate notes, and Hook/Pace/Payoff guidance. Validation
  rejects unknown, missing, or duplicate candidates and stale revisions.
  Provider failure is disclosed and falls back to deterministic prompt-intent
  ranking. The AI workspace places the recommendation first, labels it, shows
  its rationale and story guidance, and records the reviewed direction with
  the applied style provenance.
- The Motion AI workspace applies every candidate to a cloned composition and
  renders a real 384x216 preview through `MotionExportRenderer`. It displays
  operations, preserved data, backend, cost, and warnings before the user can
  approve a candidate. Apply rejects stale revisions and requires explicit
  approval.
- Candidate application preserves source references, transform properties,
  pivots, keyframes, and manual effects. Brand font, texture, seed, mascot, and
  protected-layer locks persist in
  `tigerstudio.motion.ai_style_lock.v1`; only Style Director-owned effects,
  collage metadata, or stop-motion metadata are replaced on a later style
  pass. Reports distinguish all eligible layers from layers that received a
  visual style change.
- `tigerstudio.motion.ai_story_plan.v1` plans eight stable-ID beats from Hook
  through CTA and applies them to the ordinary story-direction document only
  after approval. Automation exposes `motion.ai.style.plan`,
  `motion.ai.style.candidates.generate`, `motion.ai.style.apply`,
  `motion.ai.style.lock.set`, `motion.ai.story.plan/apply`, and
  `motion.ai.trend.preflight`.
- M27 platform-aware copy direction is implemented through
  `tigerstudio.motion.ai_platform_copy_plan.v1`. It sends only bounded story
  context and stable-ID copy targets through the shared AI provider boundary;
  providers cannot access or mutate the project. Landscape 16:9, vertical
  9:16, and square 1:1 profiles define role-specific character limits for
  Hook, Headline, Subtitle, Body, and CTA copy.
- `motion.ai.platform_copy.plan/apply/preflight` expose the workflow to
  Action/MCP clients. Plans preserve target kind, stable ID, role, original
  text, and limit; provider output may change only proposed text and reason.
  Validation rejects target additions/removals, protected layers, character
  limit overflow, stale revisions, and plans for another composition. Apply
  requires explicit approval, changes ordinary story/text fields, preserves
  media and transforms, and records provider provenance and the accepted diff.
  If the selected provider is unavailable, the shared provider boundary
  discloses the fallback and returns a deterministic length-fit plan.
- The Motion AI workspace exposes a compact 16:9/9:16/1:1 selector and `Copy`
  command. Planning runs off the UI thread, presents original and proposed
  copy with live character counts, provider/fallback disclosure, and
  preflight issues, then reuses the explicit `Apply` approval control.
  `tools/qa_motion_platform_copy_ui.py` captures this flow from a real Qt
  Motion Designer window.
- Glass candidates disclose the current shared-raster CPU fallback. Painterly
  candidates use the M24 provider-neutral post-render effect and its editable
  Realistic, Toon, Painted, Ink, and Paper presets.
  Existing Craft, Collage, Glass, and Stop Motion UMG native/bake/blocked
  classifications remain authoritative; AI provenance metadata is authoring
  data and does not create a second Unreal rendering path.
- `tools/qa_motion_style_director.py` renders all five candidates through the
  shared renderer. Current evidence records five distinct candidates, zero
  source mutation, zero transform/keyframe loss, and an eight-beat story plan.
  M27 v1 is a reviewable editable style and copy compiler, not a claim that a
  generative model autonomously produces finished art direction or replaces
  the underlying Motion tools.
- M24 Painterly 2D/3D Look Development is complete v1 through the
  `tigerstudio.motion.painterly_look.v1` contract. `painterly_look` is a
  provider-neutral post-render effect for image, video, and existing AR/PBR
  result layers; it does not add or replace a 3D renderer. It provides
  bilateral paint smoothing, editable color bands, temporally locked ink
  lines, brush texture, granulation, paper tint, hatching, durable projected
  textures, five presets, a focused `Look > Painterly` Inspector, and
  `motion.lookdev.*` Action/MCP controls.
- Painterly output preserves source alpha and uses a stable document seed and
  image-space coordinates, so repeated source frames do not develop random
  line popping. UMG conversion explicitly reports
  `effect_requires_bake:painterly_look`. Per-material overrides are serialized,
  but preflight reports `material_id_pass_unavailable` until an upstream
  renderer provides a real material-ID pass; they are never silently omitted.
  `tools/qa_motion_painterly_look.py` generates five real preset frames and a
  contact sheet and verifies temporal stability, alpha preservation, and
  nontrivial pixel differences. Painterly processing uses a 480 px bounded
  working surface and restores the original alpha and output dimensions. The
  current 960x540 warm Painted diagnostic is about 28.1 ms/frame; this is a CPU
  diagnostic and not a claim that the effect has a dedicated GPU backend.
  The Painterly Inspector exposes editable line/paper color swatches and
  projected-texture blend/opacity controls. Preview and export share the same
  deterministic effect path and are covered by pixel-identical parity tests;
  `tools/qa_motion_painterly_ui.py` captures the real Qt workspace with those
  controls visible.
- M28 Trend Template and Product QA is complete v1. The built-in gallery now
  contains eight editable 2026 product templates under
  `tigerstudio.motion.trend_template.v1`: Luxury Craft Product Reveal,
  Editorial Mixed Media Collage, Liquid Glass App Promo, Clay Stop-motion
  Mascot, Emotional Brand Story, VHS Nostalgia Music Promo, Kinetic Type
  Vertical Short, and Painterly Character Spot. Each is a 10-15 second,
  three-to-five-scene composition with
  real replacement media slots, four tutorial steps, relevant 16:9/9:16/1:1
  variants, and ordinary Motion layer/effect/story/stop-motion data.
- Replacing a managed trend template clears only composition-level state owned
  by that template and preserves unrelated user metadata.
  `motion.template.trend.capabilities` and
  `motion.template.trend.preflight` expose supported templates, validate every
  variant, and retain explicit UMG native/bake/blocked outcomes.
- `tools/qa_motion_2026_trend_matrix.py` renders every scene through
  `MotionExportRenderer` and writes a real contact sheet plus validation,
  scene-difference, editability, and UMG omission evidence. Current evidence
  covers eight templates and 19 variants. Painterly Character Spot accepts
  image, video, or an existing AR/PBR render layer and uses the M24 post-render
  contract; it does not claim a second 3D engine. The trend capability report
  has no blocked product templates and explicitly notes that material-ID
  overrides require an upstream ID pass.
- `tools/qa_motion_2026_product_gate.py` renders a real 60-second trend
  composition to a 120-frame PNG sequence at 2 fps, cancels after eight
  frames, corrupts one partial frame, then resumes by reusing seven valid
  frames and rendering the remaining 113. The same gate verifies atomic
  recovery checksum roundtrip, straight-storage/premultiplied-composite alpha,
  nested-composition Preview/Export pixel parity, HDR PQ H.265 preflight, an
  actual H.264 MP4 artifact, and an actual HDR H.265 artifact whose stream
  reports Rec.2020 primaries and SMPTE ST 2084 transfer.
- `tools/qa_motion_2026_trend_ui.py` captures the real Qt Motion Designer
  workspace and the 2026 Trends gallery, verifies that all eight templates are
  present, and records the active UI language and template control label.
  Motion workspace side panels now have bounded working widths and long
  Library descriptions elide instead of forcing the Canvas into a narrow
  column.
- The complete 2026 trend claim surface is machine-auditable through
  `tigerstudio.motion.trend_capability_audit.v1` and the non-mutating
  `motion.trend.capabilities.inspect` action. The audit maps all ten trend
  categories to concrete contracts, registered actions, QA tools, and explicit
  limitations. `tools/qa_motion_trend_capabilities.py` verifies the mapping
  against the live ActionRegistry and repository evidence files. The current
  result is eight `supported_v1`, two `limited_v1`, zero unavailable, zero
  missing actions, and zero missing evidence files. `limited_v1` remains
  mandatory for M24 per-material painterly overrides until a material-ID pass
  exists and for M25 physical clay deformation, miniature volumetric lighting,
  and automatic frame sculpting. This audit does not create replacement
  milestones or convert those limitations into completed claims.
- `TigerStudio.exe --motion-runtime-probe <report.json>
  --motion-runtime-seconds 60` opens the real Liquid Glass template in the
  `QOpenGLWidget` Preview, runs loop playback against wall-clock time, and
  records frame swaps, loop count, memory, renderer diagnostics, a real
  workspace screenshot, and an exact OpenGL framebuffer capture. Probe
  execution validity is separate from the product realtime gate (`>=24 fps`
  and a non-raster-fallback backend).
- The runtime probe also records whether the process is frozen, the exact
  executable path, size, and SHA-256, the `motion_glass_gpu` backend and GL
  feedback state, a cropped GPU composition, a same-time CPU reference, and
  visual parity metrics. `tigerstudio.motion.trend_distribution_qa.v2`
  independently requires that provenance to match the evaluated
  `TigerStudio.exe`; a source report, stale binary, alternate GPU backend, or
  forged `product_realtime_ready` boolean cannot satisfy the frozen gate.
- A previous visible PyInstaller build ran for 60.45 seconds, produced 230 frame
  swaps and four full timeline loops, and retained a valid OpenGL context.
  Process RSS decreased from 457.7 MB to 444.4 MB during the run. Both captures
  are non-empty and visually free of the diagonal tearing caused by the former
  whole-window Qt grab path. The measured rate is 3.81 fps and the mixed graph
  reports `qt_painter_fallback`. This is retained as historical frozen-build
  evidence from before `motion_glass_gpu`, not the current source result.
- `tools/qa_motion_2026_frozen_distribution.py` evaluates this evidence without
  conflating packaging with render performance. It verifies all three frozen
  launchers, the 60-second report, wall-clock duration, measurement validity,
  OpenGL context, non-zero memory samples, bounded RSS growth, workspace PNG,
  and framebuffer PNG. Current evidence returns `frozen_bundle_smoke_ok=true`
  but `product_realtime_ready=false`, with explicit `minimum_24_fps` and
  `gpu_render_path` blockers. M22 now passes those gates in the source build;
  M28 still requires a newly frozen bundle and the same sustained validation.
- Revision `14a36b98` was subsequently frozen into a 2,966-file,
  4,928,930,533-byte bundle. Its 51,174,799-byte `TigerStudio.exe` has SHA-256
  `187ff15e4a7aae3079555c88ffeba76324f105f08c068fc228dea4efc9b3e006`.
  The frozen executable itself ran the visible probe for 60.34 seconds,
  produced 1,742 swaps at 28.87 fps and five loops, used
  `motion_glass_gpu`, reported GL error 0, and increased RSS by 16,887,808
  bytes. Same-time visual parity passed at mean 3.98/255 and p95 8/255.
  Distribution QA v2 matched the runtime path, size, and SHA-256 to the
  evaluated binary and returned `blockers=[]`,
  `frozen_bundle_smoke_ok=true`, and `product_realtime_ready=true`.
  M28's frozen realtime gate is complete.
- Inno Setup 6.7.3 then packaged that exact frozen bundle into a
  2,109,158,225-byte installer with SHA-256
  `8496a476cc58071af1c28587d6f5e0af654831abd2beeb3fa1d74d594e0fd594`.
  Installer smoke installed 2,968 files to a temporary user path, launched a
  visible titled `Tiger Studio` window, matched the installed
  `TigerStudio.exe` size and SHA-256 to the frozen runtime report, uninstalled
  successfully, and removed the temporary root. The smoke tool's
  `--frozen-runtime-report` contract uses binary provenance rather than live
  source mtimes, so concurrent source edits cannot cause a false result.
  The final report honestly records `installer_current_for_source=false`
  because Painter changed afterward, while
  `installer_current_for_frozen_report=true`,
  `frozen_provenance_matches=true`, and `installer_freshness_ok=true`.
  M28's previously blocked M24-dependent template is now implemented and its
  source product gate is complete. The frozen binary evidence remains bound to
  its recorded revision and SHA-256; a future public installer must be rebuilt
  to include subsequent M24 source changes rather than relabeling old evidence.
- Inno Setup 1.4.2 was rebuilt from the current 4.59 GiB frozen bundle. The
  2,108,818,576-byte installer has SHA-256
  `febff440973091ffc681b293379388daea23078aa1899d0982c734f28b4c90a2`.
  `tools/qa_motion_installer_smoke.py` installed it to a temporary user path,
  verified 2,968 installed files, both Capture and Studio executables, and a
  live titled `Tiger Studio` window, then uninstalled successfully and proved
  temporary-root removal. Installer regression is therefore proven for this
  source state. The 2.11 GB installer remains too large for a polished public
  distribution; PyTorch/CUDA dependency splitting or optional AI packs are a
  separate packaging optimization requirement.
- Motion playback now catches up by as much as one second after a slow rendered
  frame instead of discarding all elapsed time above 100 ms. This keeps the
  playhead near wall-clock time while the performance gate still reports
  dropped-frame quality honestly.
- M22 Glass preview now processes the complete backdrop, mask, refraction,
  dispersion, and edge/specular pipeline on a bounded ROI working surface
  (480 px Preview, 320 px Draft), then restores the original-resolution alpha
  boundary. Final quality retains full-resolution processing. The renderer also
  determines the mask ROI before converting backdrop pixels to float32,
  avoiding two full-frame float copies per Glass layer.
- Current 1080p five-preset Preview evidence measures roughly 98-110 ms/frame.
  A real visible five-second Liquid Glass workspace probe reaches 7.16 fps,
  versus the earlier 3.63 fps source baseline. This is a material CPU fallback
  improvement from the historical CPU fallback baseline. The later
  `motion_glass_gpu` gate supersedes this performance result.
- Tiger Glass drivers now consume real Preview-only pointer, pointer-velocity,
  and wheel-scroll vectors. Pointer coordinates are normalized against the
  visible composition viewport; velocity and scroll decay without changing the
  document, revision, or `.tgmotion` payload. The runtime vector is added to
  the animated static driver and clamped before the shared render graph passes
  it to the Glass renderer. Export remains deterministic because it supplies
  no ephemeral runtime input. Liquid Glass App Promo binds its three managed
  Glass surfaces to pointer input by default. The 1080p Glass QA records and
  saves a center-versus-lower-right driver comparison with distinct rendered
  pixels.
- Glass-only effect graphs now use a viewport-resolution shared raster in
  Preview instead of always composing at 1920x1080 and scaling the finished
  image down. Layer transforms are applied after the global raster scale, and
  Glass blur, refraction, dispersion, edge, bloom, motion blur, and card-shadow
  pixel distances scale with the viewport. Export and mixed-effect graphs keep
  the full-resolution path. A 1920x1080-to-960x540 parity sample records mean
  absolute differences of 0.25 RGB and 0.18 alpha with a 2.4x isolated render
  speedup. A real 15.20-second visible workspace run at a 716x403 viewport
  completed one loop and 296 frame swaps (19.48 fps), with RSS decreasing by
  2.3 MB. A shorter five-second scene reached 28.82 fps. The variable
  end-to-end rate is a substantial improvement over 7.16 fps. This is retained
  as the unsupported-graph CPU fallback baseline; eligible Glass graphs now
  use the separately validated `motion_glass_gpu` path.
- The integrated 60-second product gate now encodes its HDR artifact from a
  real Liquid Glass composition rather than a non-Glass placeholder. The
  artifact contains three `tiger_glass` effects, differs from a no-Glass
  reference at 14,734 pixels with mean RGB absolute difference 23.62, and its
  actual H.265 stream reports BT.2020 primaries and SMPTE ST 2084 transfer.
  Two-frame H.265 MP4 exports disable B-frames to avoid the FFmpeg MP4 muxer's
  short-clip DTS failure; longer exports retain the normal x265 compression
  structure. Deterministic Glass-only tiled export is implemented under
  `tigerstudio.motion.tiled_export.v1`: it renders independently padded source
  regions, uses composition-global Glass coordinates to prevent seams, and
  rejects adjustment layers, precomps, mattes, card shadows, motion blur, and
  non-Glass effects instead of silently changing output. The same HDR product
  artifact now renders through eight 96-pixel tiles with 65-pixel padding,
  avoids full-frame intermediate surfaces, and matches the full-frame
  reference with zero pixel difference. AI control is available through
  `motion.export.tiled.set` and `motion.export.tiled.preflight`. The final
  assembled output image is still full resolution; this v1 claim concerns
  intermediate memory, seam safety, and deterministic parity, not arbitrary
  infinite-canvas rendering.
- M13 character-rigging foundation is complete. Motion compositions persist
  provider-neutral `tigerstudio.motion.rig.v1` cutout rigs with stable rig and
  bone IDs, a validated parent hierarchy, rest positions, animated rotation
  and translation channels, joint limits and lock flags, layer bindings,
  poses, constraints, and metadata. Invalid roots, parent cycles, duplicate
  IDs, missing layers/bones, and duplicate bindings fail composition
  validation.
- Motion Designer can create a symmetric 17-bone humanoid cutout rig from the
  `Rig > Full Body Rig` mapping dialog. Selecting a bound layer displays the
  bone hierarchy over the Canvas; joints can be moved directly and the Rig
  Inspector edits rest position, rotation limits, and lock state through the
  normal undoable document controller.
- The Qt-free evaluator applies animated bone deltas to bound layers, so Canvas,
  Preview, Motion Clip, and export share the same transform result. Current
  automation includes `motion.rig.create`, `motion.rig.humanoid.create`,
  list/inspect/delete, bone add/update/delete, layer bind/unbind,
  `motion.rig.ik.solve`, persistent `motion.rig.constraint.set/remove/enable`,
  `motion.rig.ik.bake`, `motion.rig.bone.mirror`, pose save/apply with
  mirroring, and `motion.rig.motion.apply` for arm-wave, head-nod, and
  walk-contact presets. Persistent two-bone IK targets and poles are animated
  properties; evaluation blends FK and IK by animated weight without mutating
  the document. Disabling a constraint switches the chain to FK, while baking
  samples IK into ordinary rotation keyframes and then disables the constraint.
- The Rig Inspector exposes end locking, FK/IK switching, IK bake, and selected
  bone mirroring. Selecting a rig bone exposes Bone Rotation and Bone
  Translation in the Timeline graph editor, using the same keyframe mutation
  and undo path as layer channels.
- M13 evidence uses three durable real character-part sets from the bundled
  Spine samples (girl, Erikari, and Celestial Circus). A ten-minute composition
  QA samples persistent leg IK and arm motion through Preview/Export evaluation
  and verifies the renderer frame cache remains at its configured capacity.
  This completes the rigid cutout-rig milestone; deformable skin and cloth
  remain M14 work rather than an M13 claim.
- M14 Puppet Mesh Deformation is complete. Image layers may store a validated
  `tigerstudio.motion.puppet_mesh.v1` triangular mesh with stable
  vertex/pin IDs and Position, Bend, Starch, or Overlap pin roles. Position and
  rotation are ordinary animated properties. The shared render graph applies a
  premultiplied-alpha piecewise affine warp for both Preview and Export.
- Mesh creation locally subdivides mixed-alpha boundary cells with Delaunay
  triangulation while discarding fully transparent source regions; its alpha
  threshold is available in Action/MCP. Overlap pin depth uses spatial falloff
  to order triangles. Flip, degenerate, and excessive edge-stretch problems
  are repaired around affected triangles, with a deterministic safe fallback.
- The Puppet Inspector creates the mesh, adds pins, and edits radius, strength,
  and bend. Selected pins are draggable on the Canvas and expose Pin Position
  and Pin Bend in the Timeline graph editor. Pins may reference an M13 rig bone
  as a translation/rotation driver. Action/MCP coverage includes
  `motion.puppet.inspect`, `motion.puppet.mesh.create/remove`,
  `motion.puppet.pin.add/update/delete`, and `motion.puppet.bind.rig`.
- M14 QA includes a bundled Celestial Circus transparent character part at
  three deformation times and a 100-pin, 20,000-triangle stress contract.
  Preview evaluates pins and rig drivers on CPU, updates dynamic position/UV
  VBO data, and rasterizes the textured mesh in OpenGL while caching the source
  texture. Unsupported effects and mattes use the shared Painter fallback;
  deterministic Export retains the CPU piecewise-affine path. Real OpenGL QA
  covers 476 triangles with GL error 0 and one texture upload, while 10-minute
  30fps solver QA covers 18,001 frames with no unsafe/non-finite/drift frames
  and a 52KB working-set increase.
- M15 Composition and Animation Core is complete. `precomp` layers embed a
  validated `tigerstudio.motion.precomp.v1` child composition snapshot so a
  `.tgmotion` document remains self-contained. Layers can be multi-selected
  and pre-composed, opened in place by double-click, edited, and committed back
  through Parent navigation. Saving or autosaving while inside a child rebuilds
  the root snapshot instead of losing the parent document.
- Pre-compose Preview and Export use the same recursive render graph.
  Per-instance child-layer overrides are non-destructive and Action/MCP exposes
  create, inspect, override, and refresh operations.
- Layer source time can use `tigerstudio.motion.time_remap.v1` keyframes with
  linear, reverse, freeze/hold, or speed-ramp presets. Source Time appears in
  the Graph Editor. The Graph Editor has Value and Speed displays plus
  Auto/Linear/Hold tangent modes, and `motion.graph.tangent.update` exposes
  exact tangent/interpolation mutation to automation.
- Child transform/source properties can be published and animated separately
  on each pre-compose instance without changing the child snapshot. Controller
  Nulls are non-rendering layers whose matching transform channels can drive
  target layers through the existing validated expression dependency graph.
  Graph keys can be marked roving and are redistributed by value/vector
  distance between fixed neighbors. These operations are available through
  `motion.property.publish`, `motion.precomp.published_value.set`,
  `motion.controller.create/link`, and `motion.graph.roving.set`.
- M15 stress QA renders three nested composition levels and 100 embedded
  instances, and verifies 500 document edits can be undone to the exact
  starting state.
- M15 direct Graph editing includes draggable incoming/outgoing Bezier handles;
  dragging persists a broken tangent through the same controller and undo path.
- M15 Frame Blending uses adjacent source-frame sampling in the shared
  Preview/Export render graph, including nested compositions. Optical Flow
  requests report OpenCV backend availability but currently use an explicit
  deterministic Frame Mix fallback until vector warping is enabled. The UI and
  Action/MCP surface never silently claim optical interpolation.
- M16 Typography and Vector Motion is complete. `text_animators` is an
  ordered, 32-entry stack evaluated per grapheme, word, or line. Each entry can
  select a normalized range, apply square/ramp/triangle/round influence,
  offset or reorder it deterministically, and composite per-glyph position,
  scale, rotation, opacity, fill, tracking, and blur over legacy typography
  presets. The Typography Inspector and
  `motion.text.animator.stack.set/add/update/remove` edit the same contract.
- Shape rendering now supports `offset_path`, topology-safe animated Path
  Morph correspondence, linear gradient/dashed strokes, dash offset, taper,
  and variable-width profiles. Action coverage includes
  `motion.vector.offset_path.set`, `motion.vector.path_morph.set`, and
  `motion.vector.stroke.set`. Variable-width strokes explicitly fall back from
  the vector GPU packet to the shared painter render path.
- Tiger UMG schema v4 blocks advanced Text/Shape/Glass features that do not yet
  have native UMG or deterministic bake output and serializes exact
  per-layer `BlockReasons`. Python packaging stops before Unreal generation
  when blocked content is present. The UE 5.8 plugin was rebuilt successfully;
  the source-free bundle generated and reloaded a real Widget Blueprint with
  one native button and one animation. A second real UE preflight rejected
  Tiger Glass with the exact
  `glass:effect_requires_bake:tiger_glass` reason. No Motion feature is
  silently omitted from Widget Blueprint generation.
- `motion.typography.character_3d.prepare` stores versioned, non-rendering
  per-grapheme source spans, extrusion depth, bevel, material slot, and 3-axis
  transform intent for the M19 renderer. Its payload explicitly reports
  `prepared_for_m19_not_rendered_in_m16`.
- M16 acceptance evidence is generated by
  `tools/qa_motion_m16_typography_vector.py`: five kinetic typography samples,
  five logo reveals, three animated infographic paths, a PNG contact sheet,
  and a 3840x2160 partial-alpha vector-edge check. Editable SVG still export
  reports advanced Text/Shape features as explicit bake requirements instead
  of silently dropping them.
- M17 Matte, Roto and Keying is complete. Motion exposes
  `motion.matte.object.select/refine/propagate/correction.set/freeze/assign`
  and `motion.key.create/update/diagnostics`. Point and planar propagation
  caches interpolate correction keys, can be frozen against accidental
  retracking, and are shared by Preview and Export.
- Chroma, Luma, and Difference Key effects run in the common effect adapter
  with choke, feather, and despill controls. Garbage and Holdout mask modes
  remove marked regions through the common mask adapter. Alpha/Luma and their
  inverse track-matte modes can reuse one matte layer across multiple targets.
- Edge-aware matte refinement preserves soft alpha delivered by semantic
  segmentation instead of binarizing hair strands, translucent material, or
  motion-blurred boundaries. `tools/qa_motion_m17_matte_keying.py` generates a
  10-case green/blue-screen corpus and measures minimum IoU, maximum edge spill,
  temporal flicker, and soft-alpha error. General moving-object removal remains
  experimental and is not claimed as completed video cleanup.
- M18 Tracking and Stabilization is in progress. Composition metadata can store
  provider-neutral `tigerstudio.motion.track_asset.v1` Point, Multi-point,
  Planar, Mask, and Face tracks. `motion.track.*` actions can create, analyze,
  inspect, and bake them to layer Position/Scale/Rotation; inverse baking is
  exposed by `motion.stabilize.create`.
- The Motion Tracking inspector reports mean confidence, occluded samples,
  reacquisition count, maximum step, drift review state, and source-revision
  status. It runs Point, Planar, or Face analysis in a background worker, then
  applies Attach, Stabilize, or affine Corner Pin baking to the selected layer,
  or Relinks to a newly hashed source.
  Composition validation rejects malformed, duplicate, and dangling tracking
  assets.
- Tracks can also bake translation into effect-point parameters and normalized
  Puppet-pin position/rotation. Planar tracks can bake their affine result into
  all four parameters of an existing Corner Pin effect. AR/PBR layers use the
  same layer transform path.
  `motion.track.face` reuses the VTuber face-video extractor and converts
  MediaPipe/OpenCV face center, scale, and roll into a reusable track. UI
  analysis preserves the selected layer context while it runs and retimes face
  samples from trimmed source time into layer in/out and time-scale; the same
  mapping is available through optional `motion.track.face` action parameters.
- Video tracking skips up to 1.5 seconds of featureless opening frames while
  retaining an identity hold at the requested start. Real-video QA is provided
  by `tools/qa_motion_m18_real_tracking.py`; current local evidence has 11
  clips, 10 generated tracks, and 9 quality passes, so the 20-clip M18 gate is
  not complete.
- During a full Point-track occlusion, the provider may extrapolate the last
  valid optical-flow velocity for at most 0.5 seconds, then returns to measured
  motion after feature reacquisition. The predicted-frame count is preserved
  in diagnostics; this is not claimed as general nonlinear occlusion recovery.
- Point-track observations larger than 4% of the target-frame diagonal per
  analysis step are rejected as implausible correspondence outliers. Rejected
  clips remain visible as low-confidence Review results rather than receiving
  a fabricated motion path.
- `motion.camera_solve.create` currently stores only a manual-assisted
  `manual_depth_plane_v1` ground-plane and camera-intrinsics contract. Full
  automatic 3D matchmove, perspective homography, facial-region tracks, and
  20-real-video drift evidence remain M18 work and are not product claims.
- M19 Unified 2.5D/3D Composition is in progress. A normal Motion renderable
  layer can opt into the versioned 3D-card metadata through
  `motion.3d.layer.enable`; the Advanced inspector edits Depth Z, X/Y card
  rotation, camera exclusion, and cast/receive-shadow intent. Preview and
  Export share `advanced_motion.project_layer_matrix`, including affine
  axis-foreshortening for card tilt.
- Motion camera layers now expose Perspective and Orthographic projection plus
  `orthographic_size`. Orthographic 2.5D projection keeps layer scale
  independent of Depth Z, while the existing AR/PBR bridge uses the same
  camera contract for distance-independent model framing. The current 3D-card
  tilt is an affine approximation.
- Enabled 3D cards can cast a receiver-clipped silhouette onto lower cards
  that explicitly enable `receive_shadows`. The shared Render Graph derives
  offset from card depth difference and the active Directional Light azimuth
  and elevation, then applies authored strength and softness before both
  Preview and Export. This is currently a Qt raster compositing path, not a GPU
  shadow map.
- Motion AR/PBR lighting supports at most three active direct lights in the
  shared preview/export contract. One Directional Light is selected as the
  primary shadowed key; up to two remaining Directional, Point, or Spot lights
  are evaluated as unshadowed Cook-Torrance direct contributions. Point lights
  use position/range attenuation and Spot lights additionally use inner/outer
  cone attenuation. `app.ar_pbr.schema.normalize_lighting_settings`,
  `app.motion_designer.ar_pbr_source.evaluate_ar_pbr_frame`,
  `app.opengl_preview`, and `app.ar_pbr.export_packet_pbr` share the normalized
  payload. This is not an unlimited light stack: secondary-light shadow maps,
  continuous 3D surfaces, mesh perspective deformation, model animation clips,
  and text/shape extrusion remain M19 work and are not product claims.
- Current limits: the render graph uses QImage source surfaces presented by
  OpenGL rather than a shader-only layer compositor. Fully GPU-native Bezier
  path tessellation remains pending. Audio analysis is
  file-source based; direct selection of an in-memory, unsaved Sound Editor bus
  is not claimed. Voice word timing is estimated when Voice Lab does not provide
  explicit intervals, and phoneme lip-sync requires explicit phoneme data for
  exact mouth cues. PPT round-trip
  is native for the animation subset represented by `AnimationSpec`; richer
  Motion behavior stacks intentionally require video bake.

## When Updating This Spec

- Add the user-visible behavior, not just implementation details.
- Add exact file/function/class names so an AI can jump directly to code.
- If preview and export differ, document the difference explicitly.
- Keep TODO work in `TODO.md`; keep this file focused on current behavior and
  architecture.
## Repository Maintainability and Packaging Guardrails

- `app/video_editor_window.py` and the action layer are intentionally treated as
  high-risk integration modules. New work should prefer presenter/view-model
  helpers and action namespace helpers instead of adding more unrelated logic to
  the largest files.
- Public Python Action IDs must remain stable while registration is split by
  namespace. MCP/AI automation should keep using registered actions rather than
  private editor methods.
- The first action namespace split is active:
  `app/actions/nle_namespace.py` is now a thin compatibility/orchestration
  module. Source/Record action registration lives in
  `app/actions/nle_source_record_namespace.py`; Project Bin action registration
  lives in `app/actions/nle_project_bin_namespace.py`; NLE
  readiness, real corpus, timeline fuzzer, and undo-health action registration
  lives in `app/actions/nle_readiness_namespace.py`; multicam action
  registration lives in `app/actions/nle_multicam_namespace.py`; magnetic
  storyline, connected clip, and role-lane action registration lives in
  `app/actions/nle_storyline_namespace.py`; Final Cut-style audition/take action
  registration lives in
  `app/actions/nle_auditions_namespace.py`; Final Cut-style visual feedback
  registration lives in `app/actions/nle_visual_namespace.py`. New NLE actions should be added to
  the focused namespace module instead of growing `app/actions/registry.py`.
- The VSeeFace bridge action namespace split is active:
  `app/actions/vtuber_namespace.py` owns VSeeFace input-source, bridge status,
  launch/probe, sidecar install/settings, executable/avatar/capture/framing,
  tracking-input selection, shared VTuber Studio, Avatar Target, VRM
  pose-stream preview, Performance Source, and Program Output contract
  registrations. Public VTuber action IDs remain unchanged; new VTuber/VSeeFace
  actions should be added there instead of the central registry.
- The broadcast action namespace split is active:
  `app/actions/broadcast_namespace.py` is now a facade for focused broadcast
  registration modules. Live Target and troubleshooting schemas live in
  `app/actions/broadcast_live_target_namespace.py`; broadcast release readiness
  and platform evidence schemas live in
  `app/actions/broadcast_evidence_namespace.py`; virtual-camera/OBS bridge
  schemas live in `app/actions/broadcast_virtual_camera_namespace.py`. Public
  broadcast action IDs remain unchanged; new broadcast actions should be added
  to the focused module instead of the central registry.
- The actor action namespace split is active:
  `app/actions/actor_namespace.py` owns Live2D/Spine actor add, transform,
  keyframe, and Live2D Performance Source retargeting registrations. Public
  actor action IDs remain unchanged; new actor track control actions should be
  added there instead of the central registry.
- The evidence/review action namespace split is active:
  `app/actions/evidence_namespace.py` owns UI focus, screenshot, GIF capture,
  and review scenario registrations. Public UI/capture/review action IDs remain
  unchanged; new review-evidence actions should be added there instead of the
  central registry.
- The creative action namespace split is active:
  `app/actions/creative_namespace.py` owns creative readiness, preset catalog,
  clip filter/color-grade, transition, node graph, and typography
  registrations. Public creative/node/text/transition action IDs remain
  unchanged; new creative-layer actions should be added there instead of the
  central registry.
- The audio action namespace split is active:
  `app/actions/audio_namespace.py` owns video-audio extraction, audio clip
  split/trim/delete/gain, and audio track mix registrations.
- The UI and Voice Lab action split is active:
  `app/actions/ui_namespace.py` owns detachable popout controls plus
  collapsible section operations such as `ui.section.list` and
  `ui.section.set_open`; `app/actions/tts_namespace.py` owns Voice Lab/TTS
  operations including `tts.voice_lab.open`. Voice Lab styling fixes do not
  need actions, but any user-visible Voice Lab launch or dock/section
  operation must stay reachable through these registered actions for AI/MCP
  control.
- The paint action namespace is active: `app/actions/paint_namespace.py` owns
  drawing-window editor-object listing/render/import
  (`paint.editor_objects.list`, `paint.editor_object.render`,
  `paint.editor_object.import`), document creation/export
  (`paint.document.new`, `paint.document.export_png`), and the legacy
  `paint.export_png` export path. PNG export actions must preserve the same two
  UI modes as the dialog: composited PNG for backing image plus overlays, and
  transparent-overlay PNG for the editable layer only.
- Standalone Painter is a production drawing workspace for game concept art,
  not a video-annotation side tool. Its north star is a Photoshop/Clip Studio
  style replacement for character, background, prop, and texture artists. Video
  paint-over, typography, 3D, and PBR are optional supporting workflows; the
  default workspace must prioritize drawing, brush choice, color, reference,
  layers, masks, selections, and canvas navigation.
- The implementation source of truth for the game concept-art Painter workspace
  is `docs/PAINTER_PRODUCTION_ART_WORKSPACE_PLAN.md`; keep future detailed UX,
  brush, layer, reference, 3D blockout, action parity, and QA planning there
  instead of duplicating large prose in this file.
- Painter UX references are role-based, not a one-app clone:
  Photoshop defines the base mental model (left tool rail, top tool options,
  Layers/Channels/Paths, selection/mask/layer workflow, and shortcuts);
  Clip Studio Paint defines game-character/concept-art flow, perspective
  guides, rulers, and 3D materials as drawing references; Corel Painter defines
  natural-media brush feel and stroke-preview expectations; Krita defines an
  inspectable brush-engine/preset palette model; Procreate informs fast
  low-friction drawing interactions; PureRef informs reference-board behavior;
  SketchUp plus Blender gizmos inform simple 3D blockout placement; Clip Studio
  3D Material informs how 3D should stay a draw-over reference instead of taking
  over the painting workflow. Do not import Blender-level UI complexity, old
  Corel-style dense panels, CapCut/Screen Studio video chrome, or main editor
  timeline-first behavior into Painter.
- The intended Painter layout is: large central canvas, compact left icon rail,
  top current-tool options, right Navigator/Reference plus Color/Brush plus
  a pinned Layers/Channels/Paths dock, and optional lower/popup panels for Brush Presets,
  History, 3D Blockout, Typography, and PBR. Painter must remain usable as a
  pure 2D drawing app with every optional panel hidden. Layers/Channels/Paths
  are frequent production panels and must not be displaced by optional 3D,
  PBR, typography, or helper panels in the default workspace.
- Standalone Painter follows the Photoshop-like contract in
  `docs/PAINTER_STANDALONE_PLAN_KO.md`: left icon toolbar, central canvas,
  and a right inspector where the color palette sits above a standalone
  `Layers / Channels / Paths` tab set. Brush presets are exposed from the
  top tool-options `Brush Preset` button as visual stroke thumbnails instead
  of text-only rows,
  and the full brush settings panel is reachable from the `Brush` menu and
  `Window > Brush`. Selection actions cover
  select-all, deselect, invert, rectangular marquee, elliptical marquee, and
  marquee aspect modes (`free`, `square`, `16:9`, `4:3`). Path and layer-mask
  actions must round-trip selection/path geometry through
  `paint.selection.to_path`, `paint.path.to_selection`,
  `paint.layer.mask_from_selection`, and `paint.layer.mask_from_path`.
  The Layers/Channels/Paths dock must stay Photoshop-familiar: the Layers tab
  shows kind filter icons, blend/opacity/lock/fill controls, row visibility
  icons, subtle layer color labels, and small bottom-row icon actions instead
  of large text buttons; the Channels tab exposes RGB/Red/Green/Blue/Alpha with
  eye-icon visibility toggles and copy/paste channel image actions; the Paths
  tab keeps a Work Path stack plus selected/saved paths with direct make-
  selection and make-mask commands. Path mode must preserve the Photoshop
  mental model that Pen creates paths, Path Selection moves paths, Direct
  Selection adjusts points, and paths can become selections or layer masks.
  The dock's visual contract also follows the Photoshop panel reference: neutral
  flat gray surfaces, compact `Color / Swatches / Gradients / Patterns` tabs,
  an interactive horizontal saturation/value field with a vertical hue strip,
  and thin `Layers / Channels / Paths` tabs. Layer and channel rows expose a
  dedicated eye hit area plus thumbnails; RGB, Red, Green, Blue, and Alpha
  thumbnails must visualize their actual channel data. Rounded card panels,
  purple control accents, and oversized tab buttons are invalid in this dock.
- New Painter documents default to transparent and contain no painted pixels,
  sample strokes, or implicit Background layer. New paint layers are likewise
  empty until paint, paste, or Fill modifies them. Photoshop-style neutral-gray
  checker tiles are a view-only transparency indicator and must never be baked
  into document pixels or PNG export. Choosing White or Dark in `New Canvas`
  explicitly creates the corresponding Background layer.
- The detailed Photoshop parity audit is
  `docs/PAINTER_PHOTOSHOP_PARITY_AUDIT.md`. Painter uses a flat
  `File/Edit/Image/Layer/Select/View/Window` menu order, a contextual options
  bar directly below it, a borderless dominant document canvas, and a bottom
  zoom/document status bar. The options bar owns Brush/Eraser size and opacity,
  marquee New/Add/Subtract/Intersect plus ratio, Magic tolerance, Crop actions,
  and Fill choices. Brush detail, Reference, and 3D panels are optional and
  closed in the clean default workspace. Layer drag reorder changes actual
  preview and export stroke order; `paint.selection.set_mode` exposes the same
  selection-combination state to AI automation.
- Painter 3D support is for game-art blockout and paint-over, not a general 3D
  editor. The first-class workflow runs directly in the Painter canvas through
  `Paint | 3D Place` modes. Its Shapes palette provides Cube, Sphere, Cylinder,
  Cone, Plane, and Arch; clicking adds at the default focus while dragging a
  shape onto the canvas unprojects the cursor through the active camera and
  places it on the Z-up ground plane. Artists move, rotate, and scale the result
  with an Unreal-style X-red/Y-green/Z-blue gizmo. Move is the default mode;
  selecting an actor reveals the current gizmo, each axis line/ring is
  pickable, the active axis brightens, and drag changes only that world axis.
  Camera distance, orbit, pan,
  and FOV are editable; 3D mode also accepts W/A/S/D camera travel and wheel
  zoom. Grid snap, wireframe, and camera presets remain available.
  Default shapes use an opaque white Lit material under a configurable
  directional light (45-degree horizontal and vertical defaults) with shadows
  enabled. A world-aligned Z=0 checker floor is enabled by default and has its
  own visibility toggle; checker tile size is fixed in world units and must
  not stretch when a Plane or other actor is scaled. The OpenGL FBO carries a
  depth attachment fed by per-vertex floor/object depth, and directional-light
  shadows use projected primitive silhouettes rather than a universal ellipse.
  Lit, Shadow, Fog, and
  diagnostic grayscale Depth are independent toggles. 3D scene data stays
  separate from raster strokes but is represented
  by a bottom `3D Blockout` reference layer whose visibility and opacity are
  controlled through the normal Layers dock. Paint strokes render above this
  guide. Leaving 3D Place freezes the current result into a reusable 2D display
  cache for fast paint-over; returning to 3D or changing scene/camera/material
  state invalidates that cache. The workflow must support undo and remain
  reachable through registered `paint.3d_blockout.*` actions before any MCP/AI
  workflow relies on it.
  The action surface includes `state/add/update/delete/duplicate/align_ground/
  snap/camera/material_preview/camera_preset/bake`; `material_preview` controls
  Lit, shadows, fog, depth, and directional-light angles.
  A later Figure mode may reuse this camera/layer/cache contract with a
  license-verified rigged mannequin, bone-local joint rotation, mirrored and
  saved pose presets, and dedicated automation actions. Figure assets must be
  durable external assets and must never depend on `debugCapture`.
  3D blockout preview/overlay now uses an OpenGL-first policy through
  `app.painter_opengl`: when the current Qt session can create an offscreen GL
  context it renders the serialized scene/projection to an FBO, and when RDP,
  headless Qt, missing PyOpenGL, or disabled GPU settings prevent that, it
  falls back to the maintained QPainter path instead of showing a black surface
  or crashing. `paint.gpu.status` exposes the readiness/fallback contract and
  last blockout renderer for AI/MCP workflows. The paint canvas itself remains
  remote-safe: basic round/marker/highlighter strokes may render through an
  offscreen OpenGL FBO cache wrapped by a session-local persistent stroke atlas
  cache, while masks, textured brushes, custom tip dynamics, unavailable GL,
  and headless/RDP failures fall back to the maintained QPainter stroke loop.
  The atlas path reports `painter_canvas_opengl_persistent_stroke_atlas_v1`
  and limits GL readback to stroke-signature changes; the next canvas GPU
  target is retained GL texture display plus textured-brush stamp/noise shader
  parity.
- The 2026-07-28 Painter stroke-latency pass makes uninterrupted brush input a
  release gate rather than a best-effort optimization. Live rendering must do
  work proportional to only the newest input segment (at most two stroke points
  per sample), committed strokes must be served from a retained raster/OpenGL
  cache, and appending a new top-layer stroke must update that cache without
  replaying the full document. Stroke add/remove Undo uses delta commands instead
  of copying the whole document; broader structural edits may still use document
  snapshots. View-only changes such as pan, zoom, Canvas Pose rotation, guides,
  and selection chrome must not invalidate or rebuild committed brush content.
  The OpenGL brush path may reuse a precomputed stroke signature instead of
  hashing the same stroke twice. Wet Canvas exact refinement runs asynchronously
  behind a stale/fallback frame and is capped to a 768-pixel preview dimension;
  Material/PBR preview uses revision-based cache keys and capped preview
  dimensions. These preview limits never reduce `.tspaint` source data or final
  export fidelity. This is a bounded-work interaction contract, not a claim of
  absolute hardware-independent hard real time; supported tablet/GPU combinations
  still require latency QA before release.
- Canvas Pose v1 is a non-destructive document-view transform for artists who
  rotate the working surface while drawing. It applies one shared
  rotation/zoom/pan transform to the raster background, editable strokes,
  paths/selections, guides, and in-canvas material preview, while mouse and
  tablet coordinates are inverse-transformed back into document space before
  sampling. `R` + drag rotates freely, `Shift+R` + drag snaps to 15-degree
  increments, `Alt+R` + drag is temporary and restores the prior angle on
  release, tapping `R` toggles the previous/current angle, and double-tapping
  `R` resets to 0 degrees. The status-bar angle field supports direct numeric
  entry. View-menu slots 1-4 save and recall rotation, zoom, and pan together,
  and those slots plus the active angle persist in the `.tspaint` view payload.
  Rotation must reuse the retained committed canvas instead of re-rendering
  strokes, and drawing is accepted only inside the transformed document bounds.
  Export remains in unrotated document coordinates. Widget-based speech-bubble
  or sticker editing chrome, UI Design, 3D Place, trackpad twist gestures, and
  automatic edge/handedness alignment are outside v1 and must not be advertised
  as supported until they use the same transform contract.
- The 2026-07-28 Painter Quick Palette is the primary tablet-first brush/color
  switching surface. `F6`, a right-click, or a pen-barrel right-click opens it
  at the pointer with the current/previous color comparison, RGB/HSV/HEX values,
  pinned/recent/OKLCH colors, up to eight recent/favorite brushes, and direct
  size/opacity/hardness fields. A right-button/barrel movement beyond the
  six-pixel click threshold becomes a HUD adjustment instead of opening the
  menu: horizontal movement changes brush size exponentially and vertical
  movement changes hardness. The gesture is consumed before normal paint input,
  so opening or adjusting the HUD must never create a stroke. `Alt` + canvas
  click samples the displayed merged canvas color and records it in color
  history. Quick Palette controls and palette persistence must remain outside
  the per-tablet-sample render path.
- Painter brush size supports `1..2048` document pixels consistently in the
  canvas, top-bar spin box, Brush Selector, Quick Palette, document restore, and
  user presets. Brush pressure response is a saved `25..250%` curve applied to
  normalized tablet pressure before the stroke is committed; `100%` is linear.
  The global brush library persists favorites, the last 16 brush keys, custom
  brushes, tags/groups, pressure response, and touch-target preference under
  `~/TigerStudio/Painter/palette_library.json`. Custom brushes support create
  from current settings, update, duplicate, rename/tag/regroup, reorder, delete,
  and `.tsbrushes` JSON bundle import/export. Built-in brushes remain immutable.
  Brush thumbnails use a preset-signature icon cache so search/filter/open does
  not repaint identical previews repeatedly.
- Painter color history stores up to 32 global recent colors and 32 colors in
  the active `.tspaint` document palette. Global pinned colors survive across
  documents; document colors serialize as
  `tigerstudio.painter.document-palette.v1`. The selected color is added at
  stroke completion as well as explicit palette/picker selection, and palette
  disk writes are debounced after input. Reference-board palette extraction
  prepends colors to the document palette without replacing recent history.
  Default tablet targets are at least 36 pixels wide for recent/document colors,
  with a compact-target preference available.
- Derived shade/tint/analogous/complement colors use
  `oklch_srgb_gamut_mapped_v1`: operations happen in OKLCH and reduce chroma
  until the result fits display sRGB, producing more stable perceived-lightness
  steps than the previous HSV scaling. Full, monochrome, analogous,
  complementary, split-complementary, and triadic modes are selectable, and the
  selected harmony mode persists with the global palette library. The current
  stroke/document color payload remains 8-bit sRGB; this is not a claim of
  native wide-gamut or ACES/OCIO Painter stroke storage. A future schema revision
  is required before preserving out-of-sRGB paint values through edit and export.
- Painter Output v1 removes the need for users to calculate print pixels
  manually. New Canvas begins with a `Screen / Web / Video` versus `Print`
  purpose selector. Print presets include A4, A5, B5 manga, postcard, A3/A2
  poster, and square formats; the user may work in millimetres or inches and
  selects color/general print, line art/manga, or large-poster intent. The UI
  shows trim size, PPI, bleed, and the resulting pixel dimensions together.
  Pixel dimensions include bleed while the displayed physical size is the final
  trimmed page. For example, A4 at 300 PPI is 2480x3508 pixels without bleed and
  2551x3579 pixels with the default 3 mm bleed on every edge.
- `Image > Image & Output Size` exposes Photoshop-style resampling semantics in
  plain language. With `Resample pixel data` off, the pixel dimensions are
  locked and changing PPI changes only the physical print size/metadata; it
  cannot create detail. With resampling on, physical size or PPI changes
  recalculate and resize pixels. The existing document stores normalized
  `tigerstudio.painter.output.v1` output intent including trim millimetres, PPI,
  bleed, safe margin, artwork kind, color-space intent, and resampling
  preference in `.tspaint`.
- Print canvases display non-exporting output guides inside the same Canvas Pose
  transform: a dashed magenta trim line and a dotted cyan safe-area line. The
  default print safe margin is 5 mm. Output preflight reports effective PPI and
  compares it with intent targets (300 PPI color/general, 600 PPI line art/manga,
  150 PPI large format), warns when bleed is absent or an sRGB printer profile
  must be confirmed, blocks dimensions beyond Painter's 16384-pixel canvas
  limit, and is available before export from `Image > Output Preflight`.
- PNG print export writes PPI metadata and returns the same output-preflight
  report without changing document pixels. Screen exports remain pixel-only.
  Output guides are never rasterized into export. Native CMYK editing,
  printer-profile conversion, TIFF, and print-ready PDF are not part of Output
  v1 and must not be claimed until their color/profile and bleed-box contracts
  are implemented and verified.
- Painter reference-board support is non-destructive by default. The 2026-07-24
  first slice adds a right-inspector `REFERENCE` panel, image import from file
  or clipboard, selected reference position/size/opacity/visibility controls,
  canvas overlay rendering behind transparent paint strokes, duplicate/delete,
  explicit bake-to-exportable sticker, `Window > Reference Board`, and
  registered `paint.reference.state/add/update/delete/duplicate/bake` actions.
  The second 2026-07-24 slice adds per-reference rotation, lock UI,
  bake-with-rotation behavior, and `paint.reference.sample_color` /
  `paint.reference.extract_palette` actions for reference-driven color picking.
  Reference images do not export or merge into paint layers unless the user
  explicitly bakes them. The third 2026-07-24 slice adds canvas-level
  perspective and symmetry overlays controlled by `paint.guide.perspective` and
  `paint.guide.symmetry`, and reports them through `paint.state.guides`. These
  overlays are remote-safe QPainter guides today; perspective snapping and true
  mirrored stroke drawing remain later work. The remaining parity work is
  media-pool reference add, navigator thumbnails, and value/silhouette checks.
- Standalone Painter also exposes the Photoshop-style selection/view helpers
  added in the 2026-07-23 Painter pass: Quick Mask is available through the
  visible `Quick Mask` control, `Q`, and `paint.quick_mask.set`; Magic Select
  uses `paint.selection.select_by_color` to build a fast similar-color bounding
  selection; and grid/snap state is controlled by `paint.view.grid`.
- The Painter left-rail Brush icon selects the Brush tool only and must not
  share, own, or anchor the preset popup. The dedicated top tool-options
  `Brush Preset` button owns the preset menu and opens it directly below that
  button. The pop-up is an image-first thumbnail palette with a compact header,
  category filter, and hover tooltips for name/width/opacity; it uses the same
  `BRUSH_LIBRARY_PRESETS` backing data as the Painter automation layer, and
  both the inspector palette and top preset popup use compact `53x25` rendered
  brush icons (30% smaller than the original `76x36` presentation) with
  proportionally reduced cells.
  Selecting a preset switches to Pen while applying style, width, and opacity.
  The right inspector also has a Photoshop-like `BRUSH` detail panel with
  Brush/Brush Presets tabs, tip preset thumbnails, style selection, Size,
  Opacity, Hardness, Spacing, Angle, Roundness, Flip X/Y, section toggles, and
  a live stroke preview. Size, Opacity, Style, and preset selection are wired
  to all current strokes; Hardness, Spacing, Angle, Roundness, and Flip X/Y are
  persisted in `Stroke` data and rendered through the general tip-dab brush
  path. The deeper dynamics/scattering categories are visible planning surfaces
  for the next brush-engine pass. The 2026-07-23 brush-engine pass adds
  first-tier textured Painter-style brushes (`loaded_oil`, `impasto_oil`,
  `oil_smear`, `soft_oil_glaze`, `real_wet_oil`, `bristle_oil`, `dry_oil`,
  `palette_knife`, `textured_chalk`) that render in both the Qt preview and the
  PIL/MP4 export path from the same `brush_style` field. Oil brushes simulate
  loaded-paint chunks, impasto ridge highlights/shadows, smear/glaze passes,
  bristle lanes, and palette-knife scrape marks. This is an expressive
  textured-stroke engine, not a full Corel Painter-style wet media simulation
  with real pigment mixing or canvas-state smudge physics.
- The 2026-07-25 professional oil pass adds seven renderer-distinct brush tips:
  `filbert_oil`, `flat_hog_oil`, `fan_bristle_oil`, `rigger_oil`,
  `scumble_oil`, `stipple_oil`, and `knife_scrape_oil`. They model rounded
  filbert deposits, square hog-bristle grooves, separated fan lanes, long
  rigger lines, canvas-revealing scumble, clustered stipple, and sharp broken
  knife deposits in both Qt canvas output and PIL/MP4 export. `Pro Oils`
  presets store real hardness, spacing, angle, and roundness values, apply
  those values to the active controls, and use the same renderer for their
  thumbnail previews. Both `paint.brush.set` and `paint.stroke.draw` expose
  every professional style to local/Claude automation.
- The 2026-07-25 oil-material correction removes periodic procedural
  micro-ridge decoration from the material path. Color and height now share
  authored bristle paths for loaded/impasto strokes, palette knives use a
  compressed contact plateau, and stipple uses compact irregular deposits.
  Opaque later paint buries earlier relief in its solid contact region so
  underpaint ridges cannot show through the center of a top stroke. The current
  implementation remains a deterministic 2.5D deposited-height renderer. The
  2026-07-26 Wet Canvas v1 baseline adds editable, layer-owned RGB color
  exchange with Mix/Bleed/Pickup controls, saved deterministic drying state,
  Dry Now, canvas/PNG parity, Undo/Redo, and
  `paint.wet_canvas.settings.set/advance/dry` actions. It is not a full
  wet-paint simulator: conservative fluid transport, per-cell paint volume and
  velocity, physical bidirectional pigment storage, and spectral pigment
  mixing remain explicit future work. The research and acceptance contract is
  maintained in `docs/PAINTER_PRODUCTION_ART_WORKSPACE_PLAN.md`.
- The 2026-07-25 designer catalog pass expands Painter beyond oil with 22
  production presets across Basic, Drawing, Ink, Water Media, Airbrush,
  Concept, Texture, and FX. Renderer styles include soft/flat/pixel tips,
  graphite and charcoal grain, technical and expressive ink strands,
  watercolor washes with edge deposits, opaque gouache/acrylic bristles,
  soft airbrush and skin blending, hair/foliage/cloud brushes, rock/fabric
  texture, and paint splatter. These use profile-driven Qt and PIL renderers,
  not text-only aliases. The top `Brush Preset` popup provides an `All Brushes`
  view plus category filtering over actual rendered-tip thumbnails, while the
  inspector retains Photoshop-style Brush/Brush Presets and parameter sections.
  The catalog is a production v1 set. The 2026-07-26 tablet pass captures
  native pressure, signed X/Y tilt, barrel rotation, and tangential pressure
  per point; preserves those channels through live preview, editable strokes,
  Undo/Redo, clipboard, project save/load, Actions, GPU cache signatures, and
  PNG/PBR rendering; and exposes the same contract through `paint.stroke.draw`.
  Pressure changes basic-stroke width and Engine v2 bristle spread while X/Y
  tilt shifts/fans the contact patch. Mouse input remains full-pressure and
  zero-tilt for visual compatibility. Wet Canvas v1 consumes these editable
  strokes through deterministic RGB overlap exchange and bounded bleed while
  keeping native material relief channels intact. Device calibration curves,
  persistent GPU wet-canvas fluid simulation, and validated physical pigment
  mixing remain later engine work.
- The 2026-07-26 standalone Painter persistence pass adds the versioned
  `.tspaint` single-file format (`tigerstudio.painter.document.v1`). It stores
  background pixels, ordered layers/masks, editable strokes and tablet
  channels, Material Paint, Wet Canvas state, selections, channels, Work
  Paths, references and linked bitmap assets, brush/PBR settings, and the full
  underdrawing 3D Blockout scene. The 3D payload retains primitives and
  transforms, Z-up camera/FOV, floor/grid, Lit/shadow/fog/depth/light/snap
  settings, selection, and transform mode. Open/Save/Save As and
  `paint.document.open/save` share the same serializer. PNG remains flattened
  output; legacy `.tgp` overlay fields are not claimed as a replacement for a
  native Painter document. The detailed contract is
  `docs/SPEC_PAINTER_DOCUMENT_FORMAT.md`.
- The 2026-07-25 brush workspace pass follows the current Painter 2023 Brush
  Selector information architecture without copying proprietary brush
  resources. The selector uses a compact icon header rather than large text
  tabs, active-library and favorite controls, search, simultaneous checkable
  filters (`My Favorites`, `Painter Masters`, `Stamps`, `Watercolor
  Compatible`, `Thick Paint Compatible`), an empty-state-aware recent strip,
  categories on the left, and named stroke-preview rows on the right. Full and
  Compact selector modes are functional. The selected brush preview is kept
  shallow and reports Default/Watercolor/Thick Paint layer compatibility.
  Advanced Brush Controls remain a separate stacked page. Session favorites,
  recent brushes, active filters, and compact mode are reflected in
  `paint.state`; `paint.brush.library.view` controls tab/category/single or
  multi-filter/search/compact state and `paint.brush.favorite.set` controls
  favorites. The Brush tool options bar exposes `Brush Selector` at the former
  `Brush Preset` position. Clicking it opens a compact category/preset grid
  directly below that button and never redirects the user to the right
  inspector. Re-clicking closes the grid and choosing a brush applies it and
  collapses the grid. The right inspector is reserved for Advanced Brush
  Controls. Painter numeric controls use the shared
  `StudioSlider`; hue/saturation/value controls remain dedicated color
  gradients because the gradient itself conveys the edited channel.
  The initial library is `Tiger Studio Brushes`; external Painter libraries,
  Painter brush packs, and ABR/captured-dab import remain separate future
  ingestion work and must not be simulated as installed content.
- The left Painter toolbar is a compact Photoshop-style single-column icon
  rail, not a text toolbar and not a two-column grid. It groups real supported
  tools with separators, keeps labels in tooltips/accessibility names, exposes
  Fit/Fill/Quick Mask shortcuts without duplicating fake unsupported tools, and
  includes foreground/background color swatches with swap. The rail can be
  collapsed or hidden, and hidden rails are restored from `Window > Show Tool
  Bar` so users cannot lose the primary tool surface.
- Standalone Painter must open as a clean drawing document at 100% zoom with no
  generated sample strokes, guides, or demo marks. 400-800% zoom is for pixel
  and dot work only; it must not be the default QA or user launch state. The
  top application area follows the Photoshop desktop hierarchy: the menu bar
  owns File/Edit commands and the contextual options bar contains controls for
  the active tool only. Undo/Redo stay under Edit and their shortcuts; PNG
  export stays under File; zoom stays in the View menu, shortcuts, canvas
  context menu, status bar, and tool rail. These commands must not return as a
  permanent row of large buttons above the canvas. The right inspector is
  capped as a side dock so the central canvas remains wider than the inspector
  on small remote/offscreen windows.
- The standalone Painter color panel is a compact Painter-style color dock, not
  an oversized decorative picker: a 176 px hue ring with triangular
  saturation/value picker, current-color swatch, hex readout, compact
  Mixer/Hue/Value controls, Recent swatches, a compact current-color-derived
  `Shades` harmony strip, and an `Advanced Picker` handoff. It does not show a
  large decorative all-purpose color grid because that consumed inspector space
  without helping brush work. It keeps the Painter reference shape while using
  Tiger Studio's restrained chrome. The color dock must stay in the upper
  inspector scroll without overlapping the larger independent lower
  `Layers / Channels / Paths` dock. The Layers tab control header must split
  filter, layer-kind icons, opacity, lock, and fill status into separate rows
  so the middle controls remain readable at narrow inspector widths. Painter
  inspector controls should visually follow the main Video Editor Workbench
  property-panel language: flatter dark rows, compact radii, restrained borders,
  and editor-style slider handles instead of bulky standalone-app widgets.
- Standalone Painter startup sizing must respect the current screen's available
  geometry and the same global Studio window-placement policy. Its initial and
  minimum window sizes are capped below the monitor work area, then clamped back
  on-screen on first show so low-resolution laptop, scaled Windows desktops, and
  multi-monitor workspaces do not open with controls outside the viewport.
- Painter automation includes direct document, view, tool, brush, panel, layer,
  guide, channel, selection, path, clipboard, fill, mask, mirror, crop, image,
  canvas, editor-object, and PBR actions. Layer automation covers add/select/rename/
  duplicate/delete, visibility, lock, opacity, blend mode, and Photoshop-style
  layer color labels through `paint.layer.set_color`. Selection automation
  covers select-all, deselect, invert, rectangle, ellipse, aspect mode,
  similar-color selection, and selection-to-path. Path automation covers
  create/delete/clear/commit and path-to-selection. Clipboard automation covers
  `paint.clipboard.copy`, `paint.clipboard.cut`, and `paint.clipboard.paste`.
- Painter UI Design automation includes `paint.ui.selection.set` for
  provider-neutral multi-selection and `paint.ui.object.arrange` for
  selection-bound alignment or horizontal/vertical distribution. The canvas
  and Layers panel share the same ordered selection contract; Ctrl toggles,
  Shift adds, group movement is one Undo transaction, and only the primary
  object exposes resize/rotation handles. Phone and desktop artboards preserve
  their document aspect ratio while fitting the available UI Design workspace
  rather than stretching to the underlying paint-canvas dimensions.
- Painter UI Design uses a three-column desktop authoring workspace:
  provider-neutral `Pages` and the canonical draggable `Layers` hierarchy live
  in the left navigator, artboards own the center canvas, and static
  properties, Components, Tokens, Motion delivery, Publish, and inspection
  live in the right inspector. The Layers navigator reuses the same selection,
  hierarchy, group, mask, reorder, and delete mutations as Actions rather than
  maintaining a second document model. Creation, fit, and Motion commands use
  a separate icon toolbar below the workspace-mode row; nonessential commands
  collapse at narrow canvas widths so controls never overlap.
- Painter UI object constraints use normalized pivot X/Y; horizontal
  left/center/right/stretch/scale; vertical
  top/center/bottom/stretch/scale; minimum, preferred, and maximum dimensions;
  and optional aspect locking. The document captures reference-parent size,
  edge margins, and center offsets, then resolves them deterministically when
  artboards or parent objects resize. Canvas rotation and hit testing use the
  authored pivot. Canvas and Inspector resizing share the same size-policy
  resolver, and geometry edits recapture anchors through the normal undoable
  `paint.ui.object.update` mutation path rather than maintaining private UI
  state.
- Painter UI image objects render real PNG, WebP, JPEG, and BMP references with
  `fit` (contain), `fill` (center crop), `stretch`, or bounded-scale `tile`
  placement. Optional 9-slice rendering uses left/top/right/bottom source-pixel
  margins, preserves corner regions when space allows, and proportionally
  contracts fixed edges for undersized destinations. Inspector edits preserve
  unrelated image content metadata and flow through the same undoable
  `paint.ui.object.update` contract. Missing sources remain visible as crossed
  placeholders. Source-byte embedding, hashes, density variants, and delivery
  packaging remain explicit P8 follow-up scope.
- Painter UI objects normalize editable accessibility `role`, `label`, and
  `focus_order`; zero uses document order and positive values are explicit.
  Validation reports missing semantic labels and duplicate positive focus
  orders per artboard. The Inspector uses the shared undoable object mutation
  path and displays Asset Export, Design Handoff, Review Prototype, and Unreal
  UMG disposition plus reason. `painter_ui_delivery` is the single classifier:
  preflight v2 reports only `Native`, `Material`, `Baked`, or `Blocked`, so UI,
  Actions, and handoff cannot silently disagree about conversion support.
- Painter UI document version 9 defines deterministic Auto Layout. A Frame,
  Group, or Button may use Horizontal or Vertical flow with independent
  L/T/R/B padding, gap, main-axis Start/Center/End/Space Between, and
  cross-axis Start/Center/End/Stretch. Children are ordered by stable z/document
  order; `positioning=absolute` opts out; nested containers resolve
  bottom-up for Hug measurement and outer-to-inner for placement after
  constraints. Each axis supports Fixed, Hug Content, or Fill Container, and
  fixed-size containers may wrap children into deterministic rows or columns.
  Fill distributes remaining line space after fixed children and gaps.
  Inspector edits and
  `paint.ui.layout.set` both delegate to the undoable object mutation path.
  Localization overrides remain explicit follow-up work.
- Each Painter UI artboard stores provider-neutral `layout_grid`, `guides`,
  `safe_area`, and `safe_area_visible` records. Uniform grids and multi-column
  layouts are clipped to the owning artboard; custom horizontal/vertical guides
  and safe-area bounds render as non-export authoring overlays. Inspector edits,
  Undo/Redo, persistence, and `paint.ui.artboard.layout.set` use the shared
  artboard mutation path.
- Painter UI validation v2 includes deterministic layout diagnostics. It blocks
  Hug-parent/Fill-child sizing cycles, inverted minimum/maximum constraints,
  collapsed column grids, and collapsed safe areas. It warns when Wrap is
  ignored on a Hug main axis, padding leaves no content space, or fixed children
  overflow a non-wrapping container. Inspector status, document inspection,
  delivery preflight, and `paint.ui.layout.diagnostics` share this report.
- Painter UI objects store stable-ID `responsive_overrides` keyed by breakpoint
  and orientation. Wildcard overrides apply first and exact context overrides
  refine them without changing the base object ID. The active artboard context
  drives Canvas, Constraint, Auto Layout, and Motion geometry resolution.
  Inspector can edit or clear the current context override, while automation
  uses `paint.ui.responsive.override.set/remove`; both use normal Undo/Redo.
- Painter UI artboards persist `light`, `dark`, or `high_contrast` preview
  themes. Typed tokens resolve default values, per-theme `theme_values`, and
  stable alias chains into provider-neutral object paths after responsive
  overrides. Canvas, Inspector, and layout diagnostics share this effective
  preview without mutating authored values. UI changes use the normal artboard
  mutation/Undo path; automation uses `paint.ui.theme.set/inspect` and
  `paint.ui.token.theme.set/remove`.
- Painter UI objects persist `component_role`, stable
  `component_source_object_id`, and dotted-path `instance_overrides`.
  A selected subtree can become a Component Definition; Instance creation
  clones its hierarchy with new object IDs while retaining source IDs.
  Definition property and child-topology changes synchronize to every Instance,
  and local Instance edits remain explicit overrides. Inspector and Actions
  share the same Undoable service through `paint.ui.component.create`,
  `paint.ui.component.instantiate`, and `paint.ui.component.sync`.
- Component Definitions expose typed properties and receive a default `state`
  enum with Normal, Hover, Pressed, Focused, Disabled, and Selected values.
  State overrides address Definition objects by stable source ID; Instance
  roots persist property values. Effective preview order is component state,
  local Instance override, responsive override, then theme token. Inspector
  State preview and `paint.ui.component.property.define`,
  `paint.ui.component.state.override.set`, and
  `paint.ui.component.instance.property.set` share the same undoable document
  services. Linked Variants duplicate Definition topology into the same
  component family with deterministic source correspondence. Instance switching
  preserves stable object IDs and compatible local overrides. Detach
  materializes the current state as local objects; Localize immediately creates
  a new independent component. Inspector and
  `paint.ui.component.variant.create`,
  `paint.ui.component.instance.variant.set`, and
  `paint.ui.component.instance.detach` share Undo and validation.
- Painter UI Design includes a dedicated `Components` library tab. It groups
  base Definitions and Variants, reports Instance usage, filters by name,
  selects the stable Definition root, places Instances, creates Variants, and
  renames component records. The read-only
  `paint.ui.component.library.inspect` Action exposes the same family and usage
  report to AI automation.
- Painter UI Design includes a dedicated `Tokens` library tab for Color,
  Typography, Spacing, Radius, Border, Shadow, Opacity, Icon, and Image tokens.
  It searches and groups typed tokens, edits default and Light/Dark/High
  Contrast values, manages aliases, reports binding/alias usage and unused
  tokens, and binds supported object properties by stable token ID. UI and AI
  use the same document services through `paint.ui.token.library.inspect`,
  `paint.ui.token.bind`, and `paint.ui.token.unbind`; token edits and bindings
  remain Undo/Redo operations. The same panel imports and exports deterministic
  token-library JSON. Import accepts legacy token arrays or the versioned
  library envelope and requires an explicit `update`, `skip`, or `regenerate`
  stable-ID conflict policy; regenerated aliases are remapped as one graph.
  Automation uses `paint.ui.token.library.import/export`.
- Painter UI Design includes a visual `Templates` library and full gallery.
  The initial catalog contains 12 original complete-document templates across
  11 categories: Mobile, Web/SaaS, Dashboard, E-commerce, Portfolio, Game UI,
  Broadcast, Presentation, Wireframe, Forms, and Design System. Applying a
  template duplicates editable artboards, objects, tokens, a reusable
  Component Definition, and a prototype-ready interaction rather than placing
  a flattened image. Every manifest includes source, author, version, tags,
  difficulty, and license data; `.tspaint` persists that provenance under
  `linked_targets.template_source`. UI and AI share
  `paint.ui.template.catalog.inspect` and `paint.ui.template.apply`.
- Painter UI production authoring extends that gallery with validated
  `.tstemplate` import/export/install, user templates, recent items, favorites,
  explicit license/dependency/hash manifests, and version-update inspection.
  Object-anchored comments, replies, resolution, named checkpoints, stable-ID
  revision diff, developer inspection, and offline review packages persist
  through `.tspaint`. A self-contained HTML prototype replays pointer and
  keyboard triggers plus navigation, overlays, state, visibility, opacity,
  animation, and sound actions. Production delivery exports PNG/WebP/SVG,
  density variants, object slices, trim/padding, 9-slice, texture atlas, and
  resource hashes without silently omitting unsupported vector appearance.
- Painter UI `Publish > Figma` provides editable Figma exchange without
  pretending to read or forge the proprietary `.fig` archive. Import accepts a
  Figma Design URL/file key through the official REST API or an offline REST
  JSON snapshot. It converts pages/frames, geometry, text, solid/image fills,
  constraints, Auto Layout, local components/instances, variables, token
  bindings, and supported prototype reactions to stable Tiger IDs. Signed
  image URLs are downloaded to durable user assets under
  `~/TigerStudio/PainterFigmaAssets`; API tokens are used once and are never
  persisted in `.tspaint`.
- Figma vector import preserves separate fill and stroke geometry, nonzero or
  even-odd winding, stroke width, cap, join, miter, and dash pattern. Geometry
  returned by `geometry=paths` renders as SVG paths; snapshots that omit both
  fill and stroke geometry report `blocked:...:missing_geometry_paths` and
  never substitute misleading filled bounding boxes.
- Figma linear and radial gradient fills preserve normalized handle positions,
  sorted color stops, per-stop alpha, and paint opacity. The shared Painter
  canvas renders the same gradient contract on ordinary geometry and imported
  SVG paths. Figma development-plugin export restores editable
  `GRADIENT_LINEAR` or `GRADIENT_RADIAL` paints rather than flattening them to
  a sampled solid color.
- Figma image fills map downloaded durable assets to the shared Painter
  `source_path` and Fit/Fill/Stretch/Tile contract. Missing image references
  remain explicit crossed placeholders and are reported by object ID and image
  reference. The Figma panel compares requested text families with locally
  installed fonts and reports missing families instead of silently presenting
  fallback typography as an exact import.
- Figma Auto Layout import maps modern and legacy Hug/Fill/Fixed sizing,
  child Grow and cross-axis Stretch, independent wrapped-row spacing, absolute
  positioning, and minimum/preferred/maximum dimensions. `cross_gap` defaults
  to the historical `gap` when older Painter documents are normalized and is
  editable through both Inspector and `paint.ui.layout.set`.
- Figma Component Set import preserves local component families and Variant
  membership through `base_component_id` and `variant_ids`. Variant, text,
  boolean, and instance-swap property definitions and per-instance property
  values remain editable Painter component data. Stable path-based source maps
  let an imported instance switch between local Figma variants while retaining
  compatible overrides; unresolved remote-library components remain explicit
  converted groups rather than false local component claims.
- Painter UI document version 13 stores component sublayer property bindings
  explicitly. `content.text`, `visible`, and nested `component_id` targets map
  to Figma `characters`, `visible`, and `mainComponent` references. Text and
  Boolean bindings resolve in Painter instances, Variant cloning preserves
  definition bindings without leaking them onto instances, and UI/AI use the
  shared `paint.ui.component.property.bind` mutation. Nested instances keep
  separate target-component and outer-scope IDs, so instance swaps preserve
  the nested root ID, parent, local overrides, and subsequent outer-component
  synchronization.
- Painter UI v13 also persists provider-neutral object masks, ordered
  multi-paint Fill/Stroke stacks, object blend mode, independent corner radii,
  stroke alignment, mixed text ranges, recoverable remote-component metadata,
  editable Boolean operands, and stable Figma Sections. The Inspector and
  dedicated `paint.ui.mask.*`, `paint.ui.appearance.*`,
  `paint.ui.text.range.style.*`, `paint.ui.component.remote.*`,
  `paint.ui.vector.boolean.*`, and `paint.ui.section.*` Actions share focused
  mutation services and the normal Painter Undo/Redo path.
- Figma import/export preserves those v13 features as editable nodes where the
  official Plugin API permits it. Figma comments convert to the existing
  object-anchored Painter Review contract because a local development plugin
  cannot author file comments. Shared TigerStudioUMG preflight never silently
  omits these expressions: mask, Boolean, mixed text, unresolved remote
  components, multi-paint, non-normal blend, independent corners, and
  non-center stroke alignment are explicitly `Blocked` until a real native,
  material, or deterministic-bake generator is available.
- Painter UI v12 preserves ordered Figma Drop Shadow, Inner Shadow, Layer Blur,
  and Background Blur effects in `style.effects`. Shadows retain color alpha,
  offset, blur radius, signed spread, and blend mode; blur effects retain their
  editable radius. The first Drop Shadow remains available through the legacy
  `style.shadow` alias. Painter renders every outer shadow before object fill,
  clips Inner Shadows to supported object geometry, composites Layer Blur on
  an isolated object surface, and samples Background Blur from the already
  painted scene inside the object shape. Development-plugin export restores
  all four as editable Figma `node.effects`.
- UI Design Inspector exposes a compact `Appearance` editor for the same
  provider-neutral gradient/effect contract. Linear and Radial fills provide
  ordered stop editing plus angle or center/radius controls. Drop and Inner
  Shadows provide add/remove/reorder, color, offset, blur, signed spread, and
  blend controls. Layer and Background Blur entries expose a focused radius
  control and preserve stack order. AI/MCP parity uses
  `paint.ui.appearance.inspect`, `paint.ui.appearance.gradient.set/remove`, and
  `paint.ui.appearance.effect.add/update/remove/reorder`; dedicated blur
  automation uses `paint.ui.appearance.blur.add/update/remove/reorder`. These
  Actions and the Inspector ultimately use the validated UI object mutation
  path and normal Painter Undo/Redo.
- Painter UI Frame objects expose `clip_content` as an editable, persistent
  hierarchy property. Canvas rendering intersects every child with all enabled
  ancestor Frame paths, including rounded corners and rotated parent paths;
  overflow pixels and overflow-only hit targets are both excluded. Selected
  clipping Frames show a compact amber boundary indicator. Inspector and
  automation share `app.painter_ui_clipping` through
  `paint.ui.clip.inspect/set`, and normal Painter Undo/Redo records the change.
  Figma `clipsContent` imports and exports as the same editable property.
- Shared TigerStudioUMG delivery maps clipping Painter Frames to native
  `UCanvasPanel` widgets using `EWidgetClipping::ClipToBoundsAlways`; unclipped
  containers inherit the parent clipping policy. The provider payload includes
  `clip_content`, so this behavior is never silently omitted during Unreal
  generation.
- The required UI/Action parity matrix is
  `docs/PAINTER_UI_FIGMA_INTERFACE_ACTION_MATRIX_KO.md`. A Figma feature is not
  considered complete when it only survives import JSON; it must also expose
  Painter authoring UI, a dedicated Action family, and round-trip tests.
- Figma export writes `TigerStudioFigmaExport`, containing
  `figma_exchange.json`, a compatibility report, and a local development
  plugin (`manifest.json` and `code.js`). Running that plugin in Figma Design
  recreates editable frames, nodes, text, images, components/instances,
  variables and bindings, Auto Layout, and supported prototype links through
  the official Plugin API. Component families are emitted as real Figma
  Component Sets through `combineAsVariants`; variant names and supported enum,
  text, boolean, and instance-swap properties are restored before root
  instances receive their property values. Definition and instance sublayers
  remain children instead of being duplicated as standalone components or
  instances. Unsupported property types and broken instance-swap defaults
  block preflight, while Plugin API failures remain explicit. Unsupported
  content is classified as
  `native/converted/baked/blocked`; Motion actors are baked instead of silently
  represented as editable Figma motion. UI and AI share
  `paint.ui.figma.compatibility.inspect/import/export`. Automation reads
  `FIGMA_ACCESS_TOKEN` rather than placing secrets in Action payloads.
- Painter Unreal output uses the shared `TigerStudioUMG` backend through
  `paint.ui.umg.preflight/package/generate`; no Painter-specific Unreal plugin
  exists. Win64 Development/Shipping builds and real UE 5.8 generation were
  verified with an eight-widget checkout Widget Blueprint. AI co-design uses
  `paint.ui.ai.plan/apply/audit`: it returns a preview document and revision
  diff, requires explicit apply, supports selected operations, rejects stale
  plans, and audits accessibility, localization, resource budgets, and target
  delivery.
- Painter UI Design exposes `Animate` beside the canvas tools. It opens the
  selected object or group in Motion Designer, maps the selected subtree with
  the original Painter object IDs as Motion layer IDs, and keeps Painter as the
  layout/style source of truth. Linked compositions and keyframes persist
  inside the native `.tspaint` payload and participate in Painter Undo/Redo.
  The adjacent playback control evaluates the linked composition directly on
  the Painter canvas for position, scale, rotation, and opacity preview.
- Basic horizontal/vertical Auto Layout is resolved before Motion mapping.
  Parent padding, gap, cross-axis alignment, stretch, and absolute-positioned
  child opt-out are supported. When Auto Layout changes, the bridge rebases
  existing position keyframes by the layout delta so authored Motion offsets
  remain intact instead of snapping back to stale absolute coordinates.
  Automation uses `paint.ui.motion.attach`, `paint.ui.motion.open`,
  `paint.ui.motion.preview`, and `paint.ui.motion.inspect`.
- Painter-to-Motion links use the versioned canonical binding reference
  `{composition_id, binding_id, composition_revision}`. Legacy object-to-
  composition strings remain readable and are upgraded explicitly through
  `paint.ui.motion.binding.migrate`; migration also replaces legacy
  interaction composition references with binding IDs when resolvable.
  `paint.ui.motion.binding.inspect` reports missing compositions/bindings,
  stale revisions, orphan objects, and `play_animation` mismatches.
  `paint.ui.motion.binding.relink` validates ownership before changing a link,
  while destructive `paint.ui.motion.binding.detach` removes only the Painter
  reference and preserves the editable Motion composition for recovery.
- Object or artboard deletion removes affected Painter motion links together
  with other dangling records. Motion composition cleanup remains a separate
  explicit policy; document deletion never silently destroys reusable motion.
- Motion-to-Painter placement is a separate actor workflow. The UI Design
  toolbar's `Motion Actor` command imports a `.tgmotion` project as a
  `motion_actor` object instead of flattening it to a poster. The actor keeps
  its Motion composition ID and source path, is selected, moved, resized,
  rotated, reordered, grouped, and deleted through the normal Painter UI
  object contract, and renders its current transparent Motion frame inside its
  object bounds. The shared playback control advances all placed Motion Actors
  while continuing to preview selected Painter-to-Motion bindings.
- Motion Actor compositions are embedded in `.tspaint` alongside the UI
  document and survive save/load and Undo/Redo. Selecting a Motion Actor and
  pressing `Animate` opens its original editable composition rather than
  generating a second wrapper composition. Automation uses
  `paint.ui.motion_actor.import` and `paint.ui.motion_actor.list`; import accepts
  explicit placement and size for deterministic AI/MCP layout.
- Painter UI groups keep stable child IDs and remain editable: grouping,
  ungrouping, and layer-stack reordering are exposed through
  `paint.ui.object.group`, `paint.ui.object.ungroup`, and
  `paint.ui.object.reorder`. Group movement translates descendants in one Undo
  transaction; ungrouping removes only the group container and preserves its
  children.
- Layers drag/drop uses the same provider-neutral hierarchy contract as
  `paint.ui.object.reparent`: dropping in a group center nests the selection,
  dropping above or below an item reorders it beside that sibling, and dropping
  on empty space returns it to the artboard root. Cycle checks, active-artboard
  validation, ordered selection, stable IDs, and one-step Undo apply to UI and
  Action callers equally.
- Painter AI/agent painting uses the same editable `Stroke` model and preview/
  export renderer as manual drawing. `paint.stroke.draw` accepts up to 512
  strokes per call, each with normalized canvas points, color, opacity, width,
  textured brush style, tip hardness/spacing/angle/roundness, closed state, and
  destination layer. Action-authored paths declare `path_mode=smooth` for
  interpolated natural curves or `path_mode=polyline` for intentional corners.
  Responses preserve the submitted `point_count` and separately report
  `rendered_point_count`. One batch is one named undo transaction so Claude or a
  local AI can build painterly passages efficiently without synthesizing mouse
  events. Unknown or locked destination layers and out-of-bounds points fail
  without partially applying the batch. `paint.history.undo` and
  `paint.history.redo` operate on the Painter document history rather than the
  video-editor `history.*` stack. Agents inspect progress through `paint.state`
  and render review iterations through `paint.document.export_png`. Direct
  provider runners require explicit destination layer IDs, feed periodic real
  canvas exports back to the visual model, and save replayable in-progress
  action checkpoints. PNG and Painter-to-PBR source export must use the same
  canonical Bristle Engine stroke renderer as the canvas; legacy PIL line
  rendering is not valid export parity. Image generation is optional and is not
  required for action-driven painting.
- High-fidelity reference reconstruction is provider-neutral and uses
  `paint.study.analyze_reference`, `segment_regions`, `build_underpaint`,
  `generate_strokes`, `trace_contours`, `compare_render`, `refine_region`, and
  `quality_report`. Claude, OpenAI, and local providers select semantic focus
  regions and pass order; Tiger Studio performs deterministic Lab segmentation,
  structure-flow planning, vector underpainting, editable Engine v2 stroke
  creation, and measured error refinement. Providers must not invent the full
  image as raw coordinates or bake the approved reference into export pixels.
  They stop only when `quality_report.status=ready`. The durable rule and gate
  contract is `docs/PAINTER_AI_STUDY_PIPELINE.md`.
- A user request to capture AI painting must produce a real Painter-window
  timelapse from the same generated layers and editable strokes. The replay
  begins on a blank canvas and advances through underpaint, forms, detail,
  accent, contours, and measured refinement. To keep capture responsive,
  `tools/capture_painter_study_timelapse.py` may pre-render truthful cumulative
  layer states before recording; it must not show the generated reference as a
  fake drawing process. Final PNG, MP4, and capture JSON remain regenerable
  evidence, while durable references live under `external/assets`.
- Painter image and channel automation must stay exposed through
  `paint.crop.to_selection`, `paint.image.resize`, `paint.canvas.resize`,
  `paint.canvas.flip`, `paint.mirror.set`, `paint.channel.select`,
  `paint.channel.copy_image`, and `paint.channel.paste_image`. Channel
  copy/paste targets RGB, Red, Green, Blue, or Alpha and uses the system
  image clipboard so AI workflows can move raster channel data without a
  visible dialog.
- Painter `Copy`/`Cut`/`Paste` must accept both the internal Tiger Studio paint
  payload and normal system clipboard images. Copy/Cut writes the internal
  payload plus a standard image preview when the selected paint layer, strokes,
  bubble, or sticker can be rasterized. Pasted screenshots, copied images,
  local image file URLs, or local image-path text are saved under
  `external/assets/paint_clipboard` and placed as movable PNG sticker layers so
  undo, selection, resizing, and export continue to use the existing sticker
  pipeline.
- Painter fill/mask automation must stay exposed through `paint.fill.solid`,
  `paint.fill.gradient`, `paint.fill.pattern`, and `paint.layer.mask_create`.
  Current fill operations target the document background raster or active
  selection clip; true independent raster-layer fill, Clone/Heal, and
  content-aware operations are later pixel-engine work, not current claims.
- Painter owns the PBR texture-map automation workflow through
  `paint.pbr.preview`, `paint.pbr.backend_status`, `paint.pbr.export`, and
  `paint.pbr.substrate_plan`, with
  stable internal defaults for normal/AO/roughness/metallic generation. The
  shared Texture Lab export surface covers Base/Normal/AO/Roughness/Metallic/
  Height/Cavity/Curvature plus optional Substrate-oriented `f0` and `f90_mask`
  maps. Existing Texture Lab entry points must be preserved as optional Painter
  doorways. These controls are no longer mixed into the right-side
  layer/channel/path tab set, and must not displace that pinned dock;
  lower-level `ar_pbr.texture_lab.*` actions remain available for ownerless
  file-based automation.
  Painter preview uses an in-memory, preview-sized source and the shared
  Texture Lab map cache so slider changes do not write and reopen a 4K PNG for
  every refresh. Painter PBR preview/export inherits the Texture Lab GPU-required
  default: CPU map generation and CPU preview compositing are available only for
  explicit diagnostics through `allow_cpu=true` or
  `TIGERCAPTURE_TEXTURE_LAB_ALLOW_CPU=1`. The Painter UI must expose backend
  status and missing-GPU install guidance through the shared Texture Lab backend
  contract.
- Painter implementation is GPU-forward and remote-safe: natural-media brush
  preview, 3D blockout, high-zoom canvas work, and optional video paint-over may
  use CPU/QPainter first-pass contracts while their data models stay ready for
  GPU preview/export parity. OpenGL preview paths must be preferred when a valid
  context exists, and the Painter canvas exposes its last `canvas_renderer`
  through `paint.state` / `paint.gpu.status`. `paint.gpu.status` also exposes
  the canvas GPU capability contract: persistent stroke atlas readback policy,
  texture-brush parity target styles, layer/mask shader plan, and high-zoom
  dirty-region state. RDP/remote/headless sessions must keep a maintained
  fallback path rather than failing black. Active freehand drawing invalidates
  only the current stroke segment's dirty bounds while the pointer moves; full
  canvas invalidation is reserved for committed stroke/layer/document changes.
  Standalone Painter also suppresses widget updates while the top-level window
  is being moved, then performs one geometry sync and repaint after movement
  idles so remote-desktop window dragging does not continuously refresh the UI.
  Texture
  Lab/PBR preview is stricter:
  product entry points must not run CPU fallback by default. None of these paths
  may slow the default 2D drawing workspace at startup.
- Standalone Painter must avoid GIMP-style ambiguous state changes: channel row
  clicks select the channel only, visibility changes require the per-row eye
  icon toggle or `paint.channel.set_visible`, tool-specific controls live in a
  `TOOL OPTIONS` area rather than inside Brush/Color panels, and crop can be
  applied from the visible `Apply Crop` control or Enter/Return when a crop
  selection exists.
- The track/selection action namespace split is active:
  `app/actions/track_selection_namespace.py` owns track reorder/state/lock/mute/
  rename/select, clip selection, timeline select-all, and selection set/clear/
  range registrations.
- Media/track basics, marker, and timeline core action namespaces are active:
  `app/actions/media_track_namespace.py` owns media import, import-to-timeline,
  and base track add/remove, `app/actions/marker_namespace.py` owns marker
  actions, and `app/actions/timeline_core_namespace.py` owns transport, In/Out,
  edit-point navigation, bounded playback, zoom, snap, gap, and history actions.
  `media.import_to_timeline` accepts `kind="image"` as well as video/audio, or
  infers image kind from PNG/JPG/JPEG/JFIF/WebP/BMP paths. The adapter creates
  the same image-marked visual lane used by Media Pool drag/drop, and the
  rule-based AI command router prefers image media when prompts mention image,
  photo, PNG, JPG, or equivalent Korean terms. Review automation treats image
  import results as video-scoped targets so follow-up color, blur, node, text,
  and split-compare steps can address the new still-image clip.
- Clip edit and selection movement action namespaces are active:
  `app/actions/clip_edit_namespace.py` owns split, trim, range delete,
  lift/extract, clipboard insert/overwrite, 3-point edit, linked move,
  slip/roll/slide, speed, and fade actions; `app/actions/selection_movement_namespace.py`
  owns selection move/nudge, frame nudge, align, distribute, snap, and
  ripple-delete actions.
- Read-only status and Source/Record monitor action namespaces are active:
  `app/actions/readonly_namespace.py` owns app/project/media/timeline/
  selection summaries, and `app/actions/source_record_monitor_namespace.py`
  owns Source monitor and Record monitor state/load/In/Out/clear actions.
- The central `app/actions/registry.py` is now a thin action execution and
  namespace registration orchestrator; new domain actions should be added to
  focused namespace helpers rather than directly into the registry.
- The public `EditorAdapter` action implementation has been split into domain
  mixins: `app/actions/editor_adapter_timeline.py`,
  `app/actions/editor_adapter_editing.py`, `app/actions/editor_adapter_vtuber.py`,
  and `app/actions/editor_adapter_nle.py`. The private helper layer is also
  split into `app/actions/editor_adapter_core_helpers.py`,
  `app/actions/editor_adapter_timeline_helpers.py`, and
  `app/actions/editor_adapter_object_helpers.py`. The remaining
  `app/actions/editor_adapter.py` owns only snapshot/status/app-summary behavior.
- Root `.gitattributes`, `.editorconfig`, `ruff.toml`, and `pyproject.toml`
  define baseline line-ending, editor, lint, and type-tool expectations so
  Windows LF/CRLF churn does not dominate review diffs.
- PyInstaller packaging must include runtime resources, not only code modules.
  Windows and macOS specs bundle locales, the application icon,
  `resources/luts/*.cube`, native helper binaries when present, and
  imageio-ffmpeg metadata. `tools/qa_packaging_resources.py` verifies this
  contract.
- The first `app/video_editor_window.py` UI extraction is active:
  detached preview/dock popouts and the shared VTuber Studio surface live in
  `app/video_editor_popouts.py`; Screen Studio Auto Polish lives in
  `app/video_editor_screenstudio_dialogs.py`. New popout/studio/dialog code
  should extend those modules instead of regrowing `video_editor_window.py`.
