# Agent Start Here

This is the first durable handoff index for Codex/AI agents continuing work in
TigerCapture. Use it when the user says a previous session did work, when the
current task sounds like review automation or UI renewal, or when VTuber /
VSeeFace context is involved.

## Read Order

Always start with:

1. `AGENTS.md`
2. this file
3. the focused handoff/spec listed below for the active area

Focused entry points:

- Claude/Codex handoff mailbox wakeups:
  `docs/AGENT_MAILBOX_WAKEUP.md`. If `.agent_mailbox/CODEX_WAKE_PENDING.md`
  exists, read it before assuming there is no cross-agent message.
- UI renewal: `docs/UI_RENEWAL_THREAD_HANDOFF.md`,
  `docs/SPEC_UI_RENEWAL.md`, then `TODO.md`.
- MCP/AI editor capture, including user requests like "캡쳐기능 봐줘" or
  "에디터 안 캡쳐": `docs/SPEC_PYTHON_ACTION_SYSTEM.md`, then
  `app/actions/evidence_namespace.py` and
  `app/actions/editor_adapter_editing_review.py`. Treat this as action-only
  capture unless the user explicitly asks for visible Capture app UI.
- Review automation and presentation evidence:
  `docs/review_automation/AGENT_START_HERE.md`.
- Music Lab / AI Composer / generated audio playback artifacts:
  `docs/SPEC_AI_COMPOSER_MUSIC_LAB.md`, then the Music Lab section in
  `SPEC.md`.
- VTuber Studio, Program Output, VSeeFace, VRM, Trump source mapping:
  `docs/WORKFLOW_VTUBER_BROADCAST_CONTEXT.md`,
  `docs/VTUBER_TRUMP_SOURCE_MAPPING_CONTEXT.md`,
  `docs/SPEC_VTUBER_STUDIO_BROADCAST.md`,
  `docs/SPEC_VSEEFACE_BRIDGE.md`.
- MMD player: `docs/mmd_player_handoff.md`.
- Motion Designer: `docs/MOTION_DESIGNER_ARCHITECTURE.md`, then
  `docs/MOTION_DESIGNER_MILESTONES_KO.md`. The professional motion-graphics
  expansion after M12 is tracked in
  `docs/MOTION_DESIGNER_AE_GAP_MILESTONES_KO.md`; use that file's per-feature
  evidence instead of treating all M13-M20 work as either complete or absent.
  This is not an After Effects parity claim. Prompt/reference-driven editable
  generation planning is in `docs/MOTION_AI_GENERATION_PRODUCT_PLAN_KO.md`.
  Current implementation includes M0-M12 plus recorded portions of M13-M20;
  runtime plugin contribution hosting remains pending.
  Use `debugCapture/motion_designer/release_acceptance/report.json` as the
  regenerable release-evidence index. M20 shares the main-editor ACES/OCIO
  display runtime and supports Motion H.265 10-bit Rec.2020 PQ/HLG output.
  OpenColorIO 2.5.2 and the versioned built-in Studio ACES 1.3 config are the
  shipping source defaults. `tools/qa_color_ocio_parity.py` proves zero-byte
  Preview/export-LUT error at 4,913 grid samples. The frozen EXE probe and
  `tools/qa_color_encoded_export.py` additionally prove packaged OCIO execution
  and a real H.265 Main 10 Rec.2020 PQ round trip with mean Delta E 76 1.05,
  maximum 1.93, and matching stream tags. Motion standalone Preview/Export also
  shares a 3D `.cube` Input/Creative/Output LUT chain with Reinhard or
  ACES-fitted tone mapping; `tools/qa_motion_color_pipeline.py` records
  zero-byte PNG parity and zero alpha error. OpenEXR bypasses this delivery
  chain, and main-timeline Motion compositing defers to the main project color
  transform to avoid double processing. Do not turn this parity evidence into
  a full ACES product-certification claim.
  Do not reopen completed milestone work without a failing test, reproducible
  defect, or explicit user request.
- Painter UI Designer: read `docs/PAINTER_UI_FIGMA_WORKLIST_KO.md` first,
  followed by `docs/PLAN_PAINTER_UI_DESIGNER.md` and
  `docs/PAINTER_UI_DESIGNER_MILESTONES_KO.md`. The P0-P10 worklist owns
  priority and product boundaries; the milestone document records implemented
  evidence. Painter owns static UI structure/layout/components/tokens, Motion
  Designer owns animation, and Unreal output must use shared `TigerStudioUMG`.
  Painter/Motion integration ownership and execution order were agreed with
  Painter authoring session `019f1c1c-039f-71a3-a776-b8334175150f` and are
  canonical in `docs/MOTION_PAINTER_INTEGRATION_TODO_KO.md`. Start with its P0
  binding-contract consolidation, then complete the `Normal -> Hover`
  component-state vertical slice before broader Motion Actor polish.
- Painter UI Design has a left navigator and right inspector that both default
  to zero-width Auto-hide and can be pinned, resized, or detached.
  Navigator/canvas/Inspector are hosted by one horizontal splitter; do not
  reintroduce equal minimum/maximum width locks for expanded panels. Expanded
  panels have usable minimums but no arbitrary maximum; only their collapsed
  rails use fixed widths. Splitter movement is the canonical UI width mutation
  and persisted panel state is its presentation-only counterpart.
  `paint.ui.inspector.presentation` owns the same three presentation states for
  automation. The Design tab progressively discloses
  rows for artboard, text, image, frame/group/button, component, and multiple
  selection; advanced rows stay behind the shared Advanced properties toggle.
  Its header, artboard bar, and Prototype tab are context-adaptive instead of
  remaining fixed: Prototype appears only for a single selected object.
  User-adjusted side-panel widths and collapsed states persist independently
  from responsive automatic collapse.
  Nested UI selections expose a canvas breadcrumb; parent/deep selection and
  Alt-click overlap cycling share `paint.ui.selection.parent/deep_select`.
  Double-click/Escape and `paint.ui.selection.scope.inspect/enter/exit` share
  the nested frame/group edit-scope stack without document mutation.
  Double-clicking an unlocked UI text object opens the canvas inline editor;
  `paint.ui.text.content.set` is its stable-ID Action equivalent and both paths
  preserve one-step Undo semantics.
  Multi-selection on one artboard uses a common resize boundary and preserves
  each object's relative geometry; Shift/Alt modifiers and
  `paint.ui.property.batch_set` share one constraint-aware batch mutation and
  one-step Undo. Locked or cross-artboard selections intentionally expose no
  common resize handles.
  Multi-selection also exposes a context-only Common Inspector for
  Opacity/Fill/Stroke/Stroke Width/Radius/Visible/Locked. Shared values render
  normally, mixed values render as `—` or a partial check, and editing one
  property preserves every unrelated per-object style/content value while
  committing through the same `paint.ui.property.batch_set` mutation contract.
  Smart Selection spacing lives in `app/painter_ui_smart_selection.py`.
  The Common Inspector exposes Auto/Horizontal/Vertical spacing, mixed `—`,
  explicit px gap, and Tidy Up. `paint.ui.selection.tidy` uses the same planner
  and rejects locked, cross-artboard, or cross-parent selections explicitly.
  Painter UI numeric fields share `app/painter_ui_numeric_input.py`: absolute
  and safe arithmetic input, leading relative operations, percentage scaling,
  and localized Reset all commit through the field's existing mutation/Undo
  path. Do not replace this with `eval` or a parallel property editor.
  As of 2026-07-27 the local M2A-M6 production foundation is implemented:
  `.tstemplate` packages and local library state, review comments/checkpoints,
  revision diff, self-contained prototype, production asset export, shared
  Painter UMG adapter, and safe AI plan/preview/partial apply/audit Actions.
  Cloud multi-user sync and broader template content remain optional follow-up
  scope. UE 5.8 generated and loaded an eight-widget Painter sample; refresh
  visible Unreal capture evidence before making screenshot-based release claims.
  Painter Figma exchange lives in `app/painter_ui_figma.py` and
  `app/painter_ui_figma_panel.py`. It uses official REST JSON for import and
  exports a Figma development-plugin bundle; it must never claim native `.fig`
  compatibility. Tokens are ephemeral or read from `FIGMA_ACCESS_TOKEN`, and
  imported images belong under durable `~/TigerStudio/PainterFigmaAssets`.
  The Figma-class interaction shell and its current implementation status are
  tracked in `docs/PAINTER_UI_FIGMA_INTERFACE_SPEC_KO.md` and
  `docs/PAINTER_UI_FIGMA_UX_MILESTONES_2026_KO.md`. As of 2026-07-28 the first
  M0 slice has a bottom floating toolbar, left Layers/Assets navigation, right
  Design/Prototype/Inspect modes, resizable/detachable panels, persisted panel
  state, and a selection-triggered temporary Properties overlay that reparents
  the canonical Inspector while its 36 px rail is collapsed. Grouped flyouts,
  rulers/guides, contextual Inspector disclosure, transient Zoom popover, and
  canvas-first wheel/Space navigation are implemented and verified. View
  automation uses `paint.ui.view.focus/pan/zoom/fit`; remaining milestone work
  continues in the focused roadmap.
  As of 2026-07-29 the M2 canvas also exposes transient Auto Layout direction,
  main/cross alignment, gap, four-edge padding, and child Flow/Absolute
  controls. The implementation lives in
  `app/painter_ui_auto_layout_overlay.py`, emits the existing object layout
  mutation, and is covered by `tests/test_painter_ui_auto_layout.py` plus the
  M2 screenshot in `tools/qa_painter_ui_designer.py`.
  The same M2 surface now uses `app/painter_ui_sizing_control.py` for visual
  Fixed/Hug/Fill selection and `app/painter_ui_property_contract.py` for
  `paint.ui.property.inspect/reset`. Layout warnings are selection-local and
  include recovery guidance; do not replace them with a second validation
  model or a canvas-only reset path.
  M2 Content Test is implemented in `app/painter_ui_stress_preview.py`.
  `paint.ui.layout.stress_preview` and the Inspector share one presentation
  entry point; only the canvas Overlay receives the ephemeral preview document.
  Canonical revision, persistence, and Undo must remain unchanged.
  M2 token suggestions live in `app/painter_ui_token_suggestion.py`.
  M2 variable-font support lives in `app/painter_ui_typography.py`. Painter
  persists named OpenType axes in `style.font_axes`, exposes contextual
  `wght/wdth/opsz` controls and `paint.ui.typography.variable_axis.set/reset`,
  applies axes in Qt canvas/export paths, preserves them in Figma shared plugin
  metadata, and explicitly blocks Unreal UMG output until a real deterministic
  text-bake path exists.
  Schema 18 adds explicit non-destructive Boolean groups. Compatible sibling
  shapes compose through the transient multi-selection bar or
  `paint.ui.vector.boolean.compose`; `set/release` preserve editable operands,
  and Canvas/PNG/SVG resolve `app/painter_ui_boolean_geometry.py`. Do not
  restore the old Inspector operand-ID text field as primary UX.
  Schema 17 added typed stable-ID Vector Networks through
  `app/painter_ui_vector_network.py`. The Pen/Vector tool, double-click Vector
  Edit, canvas node/segment/Bezier-handle editing, contextual command bar,
  Canvas/PNG/SVG paths, and `paint.ui.vector.*` Actions must share that
  contract. Reverse Path preserves stable IDs and handle direction; Simplify
  removes only redundant straight anchors; Outline Stroke creates editable
  closed fill geometry and rebases object bounds. Their transient context-bar
  commands and `paint.ui.vector.path.reverse/simplify/outline` Actions share
  one-step Undo and the same document mutation services.
  Schema 16 added persistent Polygon/Star/Arc parameters through the shared
  `app/painter_ui_parametric_shapes.py` geometry contract. The grouped Shape
  flyout, contextual Inspector, `paint.ui.object.add/update`, canvas hit
  testing, PNG, and SVG must remain behaviorally aligned.
  Schema 15 adds ordered artboard `layout_grids[]`, simultaneous
  Uniform/Columns/Rows canvas rendering, Stretch/Center alignment, and Action
  parity through `paint.ui.artboard.layout.set`. Reusable named grid styles
  have stable IDs, linked-artboard propagation, Inspector CRUD, and
  `paint.ui.layout_grid.style.*` Action parity.
  `paint.ui.token.suggest` and the contextual Inspector row share that pure
  planner. Suggestions require exact type-compatible values after active-theme
  and alias resolution, never mutate the document, and must apply through the
  existing stable-ID token bind/Undo path.
  `app/painter_ui_property_clipboard.py` owns UI-object Copy/Paste Properties
  and Paste to Replace. It preserves target stable IDs, hierarchy, position,
  and z-order; UI and `paint.ui.object.properties.*` Actions must share it.
  `app/painter_ui_object_scale.py` owns Figma-style selection scaling. Keep its
  UI contextual rather than adding a fixed panel, scale visual metrics with
  bounds, and reject selections spanning different parent coordinate spaces.
  `app/painter_ui_quick_actions.py` is the canonical contextual command and
  document-asset search catalog. The Painter UI opens it only as a transient
  `Ctrl+/` / bottom-toolbar popover; mutating results must continue to call
  existing focused services instead of growing a parallel mutation layer.
  `app/painter_ui_cross_artboard.py` owns responsive-screen duplication.
  Context menus, Quick Actions, and `paint.ui.object.duplicate_to_artboard`
  must use it so object trees, Boolean/Mask dependencies, component links,
  interactions, focus-order conflict reporting, and one-step Undo stay aligned.

If two areas overlap, keep the product boundary from the focused docs. Do not
merge UI renewal, review automation, and VTuber sidecar setup into one unbounded
task unless the user explicitly asks for that.

## Current Hard Rules

- `debugCapture` is disposable scratch space. The user may delete it when it
  grows large. Do not store important source assets, SDKs, installed apps,
  manifests, project state, or non-regenerable files there.
- External apps and SDKs belong under `external/tools`.
- Third-party/local durable assets belong under `external/assets`.
- `app/video_editor_window.py` is a compatibility facade. Add editor features in
  focused modules and wire them through delegates, controllers, or popouts.
- Tiger Studio and the lightweight capture launcher are separated product
  surfaces. The capture program may be bundled with Studio, but capture-to-Studio
  handoff is blocked by default through
  `app.launcher_studio_policy.capture_to_studio_enabled()`. Only explicit
  bundle/QA opt-in such as `TIGERCAPTURE_CAPTURE_TO_STUDIO=1` should expose
  Studio buttons or construct `VideoEditorWindow` from the capture app.
  `main.py` is the capture-app entry point; `studio_main.py`, `TigerCapture.exe
  --studio`, packaged `TigerStudio.exe`, and source-built `TigerStudio.exe` are
  the Studio entry paths.
- In editor context, "capture" without explicit launcher/recording UI wording
  means MCP/AI action capture: `capture.targets`, `capture.screenshot`,
  `capture.gif`, `capture.windows.list`, `capture.window.screenshot`,
  `capture.window.video`, and `ui.popout.capture`. Do not start by changing
  toolbar buttons or the standalone capture launcher for that request.
  For external tasks with unknown duration, use
  `capture.window.video.start/status/stop` with `max_duration_ms` as the hard
  timeout instead of guessing one fixed `duration_ms`.
- Music Lab playback-safe files are for human listening only and must be made
  from the measured WAV by 48 kHz conversion plus peak normalization only. Do
  not add warm-up beds, pre-roll, noise floors, synthetic silence padding, or
  other "player stability" audio; a previous attempt introduced a false audible
  cut that was not present in the measured render. If the original probe report
  is clean but a playback-safe copy cuts, audit the companion-file generator
  before changing the composer or mix code.
- Music Lab's basic/default renderer is sample/SoundFont-based
  `backend=sample_production` with `sample_library_policy=auto`. AI/production
  audio is the advanced path and must be selected explicitly with
  `backend=production` or a concrete `ai_provider`; `auto` must not silently
  switch to AI just because a provider is configured.
- One-click Music Lab requests such as "make BGM/music" must render through the
  default sample-production studio master profile
  `one_click_sample_production_studio_v1`: bus tone shaping, rumble/mud
  control, presence/air enhancement, room ambience, mid-side width, parallel
  glue compression, dropout/surge repair, sample-jump smoothing, and soft
  preview limiting. The same route also applies
  `sample_production_articulation_expression_v1`, which classifies notes by
  role/length, shapes short-note gates, writes CC1/CC11 expression automation
  for SoundFont renders, and shapes internal fallback envelopes. Do not return
  raw SoundFont/internal-synth audio for that path unless the user explicitly
  chooses a diagnostic comparison.
- Sample-production renders must report
  `render_backend.audio_safety.profile=music_audio_output_safety_v1` after the
  post-master output safety guard runs. Treat audible crackle/distortion/"깨짐"
  as a bus/source problem even when generic glitch checks are clean. Inspect
  bus renderers and stems; fast `classical_solo_violin` lead material should
  bypass General MIDI/SoundFont lead programs and use
  `procedural_clean_violin` unless the user explicitly requests a raw
  SoundFont comparison.
- After editor-facing changes, run
  `.\.venv\Scripts\python.exe -m pytest tests\test_editor_architecture_rules.py -q`.

## VTuber Default Assumption

As of 2026-07-07, assume VSeeFace is absent unless the user explicitly asks to
work on the VSeeFace sidecar. TigerCapture must still provide a usable VTuber
Studio path through its own internal VRM fallback.

Default behavior for VRM/VSeeFace-style work:

- `Performance Source` is face/body tracking input only.
- `Program Output` is the final recorded or streamed picture.
- The raw Trump/person source video must not be used as Program Output.
- Studio and VRM rendering must use the VTuber VRM/MToon renderer boundary
  (`app/vtuber/vrm_renderer.py`, renderer family `vtuber_vrm`). Do not route
  `.vrm`, Avatar Mapping, or internal VRM Program Output through AR/PBR,
  Marmoset PBR, generic AR/PBR `full-gpu` debug proof images, or old debug proof
  images. Product-catalog VTuber evidence must request and prove the exposed
  VTuber backend `vrm_mtoon_gpu`. Legacy `vrm_mtoon_software` /
  `software-zbuffer` output is diagnostic only and must be rejected for product
  screenshots because it can produce point-like broken avatar output.
- Source-person visibility must drive VRM visibility. The code rule is
  `match_source_person_exposure_to_vrm_visibility` in
  `app/vtuber/source_framing.py`: `face_only` maps to `bust_up`,
  `chest_up` / `bust_up` maps to `bust_up` / head-to-mid-chest, `upper_body`
  maps to at least `half_body`, and `full_body` maps to `full_body`.
  Product evidence must also trim transparent avatar padding before fitting,
  scale the visible avatar large enough to read, and anchor its lower visible
  edge to the Program Output bottom safe line. Tiny/floating avatars are not
  valid product evidence.
  Source framing plans expose `source_exposure` and
  `visibility_policy` for AI/review automation; do not show a head-only or
  face-only VRM thumbnail when the source person is chest-up, upper-body, or
  full-body.
- VSeeFace missing, black, degraded, unregistered, or not installed is a
  degraded sidecar state, not a blocker for Program Output when internal VRM
  fallback assets are available.
- Do not chase VSeeFace virtual-camera registration or window-capture debugging
  unless the user explicitly asks for sidecar repair.

Current stable local references:

```text
Trump source video:
C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\trump_oval_office_live_GnzWEo_HfE0.mp4

Milica VRM:
external\assets\vtuber\booth_milica\Milica1.3free\Milica_v1.3.vrm

Optional VSeeFace sidecar install root:
external\tools\vseeface
```

Current fallback note: `app/vtuber/internal_vrm_fallback.py` no longer requires
generated `debugCapture` descriptor or motion files for its default path. It
loads the durable `.vrm` through the VTuber VRM/MToon renderer boundary and uses
internal idle motion when `debugCapture` has been cleaned. Remaining debt is
first-frame performance: runtime VRM descriptor generation/rendering can be slow
and needs a dedicated optimization pass before making strong preview-performance
claims.
2026-07-10 update: Trump-to-VRM pitch now goes through
`app.vtuber.vrm_motion_mapping.source_pitch_to_vrm_pitch`
(`vrm_pitch = -source_pitch - 12deg`) for internal VRM pose curves and VMC
messages. The latest real Studio proof uses `vrm_mtoon_gpu` and records
`mapped_vrm_motion.pitch_deg=-12.97`. Live-render diagnostics are faster after
the helper keeps the hidden Qt/GL widget alive: cached frames measured about
`2.852s/frame` with `gpu_widget_cache_hit=1`, `build_vertex_buffer_s ~= 1.23`,
and `gpu_widget_grab_s ~= 0.035`. This is still not real-time; the next
bottleneck is per-frame CPU vertex-buffer build plus helper-service round trip.
Do not lower triangle caps aggressively because dense hair/cloth becomes
visibly dotted.

## Evidence Discipline

Review/catalog/PPT evidence must use real TigerCapture UI screenshots and real
rendered proof outputs. Generated monitor frames, mockups, and debug captures
can be used only when clearly labeled as design/reference or regenerated proof,
not as fake editor evidence.
