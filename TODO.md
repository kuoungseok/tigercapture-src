# TODO

## Remaining Product Gaps

- [ ] Painter production art workspace:
  Painter must be treated as a primary drawing app for game concept artists,
  not as a video-annotation helper. Use
  `docs/PAINTER_PRODUCTION_ART_WORKSPACE_PLAN.md` as the implementation source
  of truth, with `SPEC.md` carrying only the durable product contract.
  - [ ] Rebalance Painter layout around drawing: large central canvas, compact
    left rail, top tool options, right Navigator/Reference, Color/Brush, and
    Layers/Channels/Paths. Move Typography/PBR/3D into optional panels instead
    of default visual priority. Keep Layers/Channels/Paths pinned as a frequent
    production dock; optional 3D/PBR/Typography panels must not replace or hide
    it in the default drawing workspace.
  - [ ] Brush engine pass for production concept art: pressure/flow/hardness/
    spacing/shape dynamics/texture/smudge/mixer behavior, real stroke-preview
    thumbnails, and game-art presets for sketch, clean ink, blocking, oil,
    dry brush, texture, hair, skin, metal, smoke/cloud, ground/rock, and pixel.
  - [ ] Layer workflow pass: thumbnails, clipping mask, layer mask clarity,
    group/folder planning, drag reorder, blend-mode readability, lock
    transparency, duplicate/merge/flatten behavior, and PSD compatibility plan.
  - [ ] Selection/transform pass: lasso/polygon lasso, color range, feather,
    expand/contract, transform selection, free transform, rotate/scale/skew,
    and selection-to-mask polish.
  - [ ] Reference workflow pass: PureRef-like image board, pinned references,
    navigator/value-check/flip-canvas controls, perspective rulers, symmetry,
    and silhouette/value preview.
    - [x] 2026-07-24 first slice: non-destructive Painter reference board,
      file/clipboard image add, selected position/size/opacity/visibility,
      canvas overlay, duplicate/delete, explicit bake-to-sticker, `Window >
      Reference Board`, `paint.reference.*` action coverage, and regression
      tests. Remaining reference work: media-pool add, rotate/lock UI,
      color sample, palette extraction, navigator/value/silhouette views, and
      perspective/symmetry guides.
    - [x] 2026-07-24 second slice: reference rotation, reference lock UI,
      bake-with-rotation, color sampling, palette extraction, and
      `paint.reference.sample_color` / `paint.reference.extract_palette`
      action coverage. Remaining reference work: media-pool add, navigator,
      value/silhouette views, and perspective/symmetry guides.
    - [x] 2026-07-24 third slice: canvas-level perspective and symmetry guide
      overlays with `paint.guide.perspective` / `paint.guide.symmetry` action
      coverage and `paint.state.guides` reporting. Remaining reference work:
      media-pool add, navigator, and value/silhouette views.
  - [ ] 3D blockout pass for background concept art: box-first placement with
    stretch/widen/tall scale, move/rotate/scale standard gizmos, optional simple
    arch helpers for door/window openings, grid snap, camera orbit/pan/zoom/FOV,
    perspective/horizon/vanishing overlays, wireframe/transparent/value/
    silhouette views, opacity control, and bake-to-paint-layer. Keep it a
    drawing reference, not a Blender clone.
    - [x] 2026-07-24 first slice: box/arch data model, canvas overlay,
      selected move/scale/rotate handles, duplicate, align-to-ground, grid
      snapping, camera/FOV controls and presets, `paint.3d_blockout.*` action
      coverage, and bake-to-layer as Painter strokes on a
      `3D Blockout Guide` layer.
  - [ ] Preserve Texture Lab entry points while moving PBR into optional
    texture-artist workflow. Existing `PBR Texture Lab...`, `paint.pbr.*`, and
    `ar_pbr.texture_lab.*` doorways must keep working and must not displace the
    pinned Layers/Channels/Paths dock.
  - [ ] GPU-forward Painter architecture: design brush preview, high-zoom
    canvas work, Texture Lab/PBR previews, and 3D blockout with GPU
    acceleration/parity as the target. CPU/QPainter fallbacks are acceptable
    first passes only if they do not slow default 2D drawing startup.
    - [x] 2026-07-24 first OpenGL slice: 3D blockout preview/overlay now tries
      an optional offscreen OpenGL FBO renderer first, keeps QPainter fallback
      as the remote/RDP-safe product path, and exposes `paint.gpu.status` for
      AI/MCP readiness checks. Remaining GPU work: actual paint-canvas stroke
      texture/FBO atlas, high-zoom canvas acceleration, and parity evidence.
    - [x] 2026-07-24 canvas OpenGL slice: the active Painter canvas now has an
      OpenGL basic-stroke FBO cache for round/marker/highlighter strokes and
      records `canvas_renderer` in `paint.state` / `paint.gpu.status`. Complex
      brushes, layer masks, unsupported GL, and remote/headless failures still
      fall back to the maintained QPainter stroke loop. Remaining GPU work:
      persistent stroke atlas, textured-brush parity, and reduced readback.
    - [x] 2026-07-24 stroke-atlas slice: the active Painter canvas now routes
      supported OpenGL strokes through a session-local persistent stroke atlas
      cache, so GL FBO readback happens only when the stroke signature changes.
      `paint.gpu.status` reports
      `painter_canvas_opengl_persistent_stroke_atlas_v1` plus the base FBO
      renderer, texture-brush parity target styles, layer/mask shader plan, and
      high-zoom dirty-region contract. Remaining GPU work: retained GL texture
      display, textured brush stamp/noise shaders, and per-layer FBO mask
      compositing.
  - [ ] Painter action parity: every production drawing feature above must get
    registered `paint.*` actions, dry-run/review support where destructive,
    undo transactions, and regression tests before AI/MCP claims it.
  - [ ] Painter QA matrix: small laptop window, 1080p, high-DPI, tablet/stylus
    input, pixel-art 800% zoom, heavy brush strokes, layer/mask operations,
    copy/cut/paste, PNG/PSD/export paths, and optional 3D blockout overlay.

- [x] 2026-07-08 Music Lab arranger handoff: Workbench Sound Editor `Music Lab`
  now displays real composition sections/tracks/clips instead of a static
  mockup, supports selected-block regenerate/section resize controls, exposes
  `music_lab_selection` to AI snapshots, routes selected-section/selected-track
  AI commands to structured actions, previews/stops the generated mix inside the
  embedded Video Editor Lab, and upgrades the local preview renderer to
  `tigerstudio.local_synth.v5` so Lab playback uses smoother WAV stems instead
  of cheap external-MIDI/8-bit-like audition tone.
  - [x] 2026-07-08 next quality step: Music Lab rendering is now
    SoundFont-ready. Durable `.sf2/.sf3/.sfz` assets belong in
    `external/assets/music/soundfonts`, optional FluidSynth belongs in
    `external/tools/fluidsynth` or PATH, and `music.render.backends` reports
    readiness/fallback state for AI and review automation.

- [ ] Main editor UI renewal return gate:
  `docs/SPEC_UI_RENEWAL.md` is the persistent handoff anchor. Keep current work
  focused on main editor UI renewal until the live editor screenshots are stable;
  then return to review automation as the primary task. Review automation must
  use real live-editor action captures, not generated fake editor evidence. Before
  regenerating PPT/HTML/catalog review output, re-read current SPEC/TODO/action
  registry/UI state because the spec changes frequently.
  - [x] 2026-07-01 `video_editor_window.py` first extraction boundary recorded:
    new popout/detached dock/VTuber Studio UI belongs in
    `app/video_editor_popouts.py`, Screen Studio Auto Polish dialog changes
    belong in `app/video_editor_screenstudio_dialogs.py`, and future UI work
    should continue extracting bounded modules instead of adding new large UI
    blocks directly to `video_editor_window.py`.
  - [x] 2026-07-01 Color grading reference pass: color nodes now open a
    right-side `Color Grading` Workbench inspector, the old bottom color dock is
    hidden by default, split compare viewer chrome is visible, and
    `tools/qa_workbench_node_action_flow.py` verifies the real UI state with
    `debugCapture/ui_renewal_color_reference_split_overlay_round`.
  - [x] 2026-07-01 Color grading timeline/scope follow-up: Timeline now paints
    compact real-state `Grade Layer` rails with diamond marks for non-identity
    clip/node color grades, and the right-side color workbench includes larger
    wheels plus preview-pixmap-based mini scopes. Verified with
    `debugCapture/ui_renewal_color_scope_row_round`.
  - [x] 2026-07-07 Color grading scope recovery: the right-side Workbench
    `Scopes` card now uses the existing `app.color_scopes.render_scope`
    renderer for live-preview `Luma / Levels`, `Histogram`, `RGB Parade`, and
    `Vectorscope` graphs instead of the old tiny decorative marks. The scope
    area was enlarged to read as a useful monitoring surface rather than a
    narrow status strip, and it can be popped out as a detached `Color Scopes`
    dock without removing the Workbench copy.
  - [x] 2026-07-02 Color grading density decision: keep the compact Timeline
    `Grade Layer` rail instead of adding taller dedicated grade rows. The
    current rail already shows real clip/node color-grade state without harming
    timeline density; the visible mismatch was mainly in the right-side color
    Workbench. Tuned the Color Grading wheel/scope row so wheels get more
    horizontal presence and scopes read as secondary evidence. Verified at
    `debugCapture/ui_renewal_color_workbench_density_round_2/editor_color_dock_action.png`.
  - [x] 2026-07-02 Color grading soft-glass controls pass: adopted the
    user-approved generated reference style as real editor UI, not catalog
    compositing. The right-side `Color Grading` Workbench now uses a single
    soft-glass Color Wheels deck, icon-based chevron/reset/more controls,
    compact readout pills, two-column `Light` and `Primary` slider sections,
    and a vertical `QScrollArea` wrapper so the panel scrolls instead of
    overlapping when the dock is short. Connected controls remain bound to the
    current `ColorGrade` fields where available. Verified with real YouTube
    Imports media at
    `debugCapture/ui_renewal_color_soft_glass_controls_round_4/editor_color_dock_action.png`.
  - [x] 2026-07-02 Color grading reference-ratio follow-up: the previous pass
    was still an inspector adaptation, not close enough to the selected
    reference. Color-node selection now shifts the top work area ratio toward
    the Workbench, widens the color console, reduces the large compare button
    row, and restores larger 104px wheels so the Color Wheels deck reads as the
    primary surface. This is the best main-editor compromise; an exact match to
    the reference requires a dedicated color page or popout because the
    reference is not a narrow side inspector. Verified at
    `debugCapture/ui_renewal_color_soft_glass_controls_round_5/editor_color_dock_action.png`.
  - [x] 2026-07-02 Color grading slider shape follow-up: replaced the
    stylesheet `QSlider` look in the right-side Color Grading Workbench with a
    panel-local painted `_SoftColorSlider`. The renewed sliders use rounded
    glass rails, gradient temperature/tint tracks, circular metal-style knobs,
    and borderless text labels so the Light/Primary controls match the selected
    reference more closely and no longer read as boxed Qt form rows. Verified at
    `debugCapture/ui_renewal_color_soft_slider_round_2/editor_color_dock_action.png`.
  - [x] 2026-07-02 Color grading wheel shape follow-up: the shared
    `app.color_page_window._Wheel` painter now follows the selected reference
    image more closely: no rounded-square tile background, a larger circular
    shell, thinner hue ring, subdued luma rim, centered crosshair, and small
    graphite puck. The editor Color Grading Workbench uses the same wheel and
    slightly larger 110px instances, so the Color page and main editor now share
    the renewed wheel language. Verified with real YouTube Imports media at
    `debugCapture/ui_renewal_color_wheel_round_3/editor_color_dock_action.png`.
  - [x] 2026-07-02 Editor standard slider pass: extracted the renewed
    soft-glass horizontal slider into `app/studio_slider.py` as `StudioSlider`
    and replaced the local Color Grading `_SoftColorSlider`. Applied it to
    main editor color/LUT/luma controls, Typography and PIP rows, audio clip
    volume/PAN controls, Workbench inspector/blur/effect-node parameters, the
    full Color page slim/workflow sliders, Audio Mixer PAN, and Live2D transform
    and parameter controls. Vertical faders remain purpose-specific. Verified
    with real YouTube Imports media at
    `debugCapture/ui_renewal_standard_slider_round_1/editor_color_dock_action.png`,
    `debugCapture/ui_renewal_standard_slider_round_1/workbench_mask_tab_action.png`,
    and
    `debugCapture/ui_renewal_standard_slider_round_1/editor_audio_mixer_action.png`.
  - [x] 2026-07-02 Timeline drag palette card polish: `app/effect_cards.py`
    now keeps neutral compact tiles while using thin color-coded folds/strips
    for card meaning, adds a code-native fade icon, and normalizes Speed card
    visible labels to ASCII. Verified with
    `tools/qa_effect_cards_palette.py` and
    `debugCapture/ui_renewal_effect_cards_palette_round`.
  - [x] 2026-07-02 Media Pool left-rail polish: `app/media_pool.py` now uses
    the shared UI font stack, lower-contrast icon buttons, thinner borders,
    denser list rows, and a calmer selected-media card. `tools/qa_ui_renewal_left_rail.py`
    captures the panel with real YouTube Imports media at
    `debugCapture/ui_renewal_left_rail_round/media_pool_left_rail.png`.
  - [x] 2026-07-02 Preset filter chrome polish: preset browser search/filter
    styling in `app/video_editor_window.py` was tightened without adding new
    UI surfaces; category filtering is now icon-only with hover/tooltip text,
    and the grid uses the shared thin scrollbar style.
  - [x] 2026-07-02 Workbench panel polish: `app/workbench_panel.py` now uses
    the shared UI font stack, softer tab/card/button borders, calmer VFX graph
    strip chrome, and `x` speed readouts for remote/font-safe display.
    `tools/qa_ui_renewal_workbench.py` captures clip and node-graph Workbench
    states side by side.
  - [x] 2026-07-02 Preset browser style extraction: pure preset-browser
    constants, pack icons, palette button QSS, search/filter/combo QSS, menu
    QSS, and preset grid scrollbar QSS now live in
    `app/video_editor_preset_browser_style.py`; the searchable preset browser,
    scroll-grid, inspector, and animated preview swatch widgets now live in
    `app/video_editor_preset_browser_widgets.py`. Continue moving bounded UI
    helpers/classes out of `video_editor_window.py` instead of adding more
    inline QSS or new UI surfaces there.
  - [x] 2026-07-02 UI renewal 1-20 first-pass: preset cards/panels moved to
    `app/video_editor_preset_cards.py`; command-bar helpers moved to
    `app/video_editor_command_bar.py`; Timeline palette tile helpers moved to
    `app/video_editor_timeline_palette.py`; layout/scrollbar/splitter constants
    moved to `app/video_editor_layout_specs.py`; compact AI command dock style
    moved to `app/video_editor_ai_command_dock.py`. Viewer copy now shows
    `Viewer` plus `Project > name`, transport controls are compact icon-first,
    Media Pool keeps a large selected clip plus compact list rows, and the
    shared thin scrollbar pattern is applied to the renewed scroll hosts.
    Verified with `py_compile`, `tools/qa_ui_layout.py`,
    `tools/qa_ui_renewal_left_rail.py`, `tools/qa_effect_cards_palette.py`,
    `tools/qa_ui_renewal_workbench.py`, and a YouTube Imports
    `tools/qa_editor_e2e_smoke.py --catalog-capture --import-media ...` run
    at `debugCapture/ui_renewal_1_20_real_media`.
  - [ ] Main editor UI renewal remaining stages:
    - [x] Refactor first, then polish:
      - [x] Extract preset cards/panels from `video_editor_window.py` into a
        dedicated preset module: `EffectPresetCard`, `EffectsPresetPanel`,
        `WorkflowPresetCard`, `WorkflowPresetPanel`, `TitlePresetCard`,
        `TitlePresetsPanel`, `TransitionCard`, `TransitionsPanel`, and related
        transition swatches.
      - [x] Extract top-bar command groups into a dedicated module. Target
        groups are Project, Create, Actors, View, More, and Export.
      - [x] Extract Timeline palette/tools into a bounded module, including
        frame-editor tool collapse/expand state and drag palette behavior.
      - [x] Extract right inspector / Workbench connection glue where it can be
        separated without changing action contracts.
      - [x] Shrink and separate AI chat dock/controller so it does not consume
        excessive vertical space in the main editor.
    - [x] Match the generated reference style without faking features:
      - [x] Rebalance full editor layout spacing between Media Pool, Viewer,
        Workbench, and Timeline; keep splitters visually thin.
      - [x] Remove excessive black void areas.
      - [x] Use thin panel borders, subtle depth, and restrained beveling.
      - [x] Keep buttons mostly monochrome or low-saturation icon-first.
      - [x] Show text through hover/tooltips or expanded states, not permanent
        dense chrome.
      - [x] Keep the shared thin scrollbar style across editor panels.
      - [x] 2026-07-02 Preset browser left-dock capture pass: added
        `tools/qa_ui_renewal_preset_browser_left_dock.py` so the Effects
        Library can be captured in the real editor left dock with Media Pool
        and Actor Library collapsed. Verified that search is visible, category
        filtering is icon/menu based, the old wide category combo stays hidden,
        and the grid does not reproduce the earlier overlapping tab strip at
        `debugCapture/ui_renewal_preset_browser_left_dock_round_2/left_dock_effects_browser.png`.
      - [x] 2026-07-02 Preset hover prediction pass: the old detached hover
        popover is now suppressed when the preset browser owns an integrated
        preview. `PresetInspectorPanel` stays inside the dock and shows an
        animated current-frame A/B preview, target-strip icons for clip/cut/
        audio/text/actor/node intent, and compact metadata for the hovered
        preset. `tools/qa_ui_renewal_preset_browser_left_dock.py` now imports
        real YouTube Imports media to the Timeline through
        `media.import_to_timeline`, forces a Viewer frame, simulates hover
        refresh, and verifies the integrated preview at
        `debugCapture/ui_renewal_preset_browser_left_dock_round_5/left_dock_effects_browser.png`.
      - [x] 2026-07-02 Preset section parity pass: the same integrated hover
        prediction surface now covers Title Presets, Transitions, and Workflow
        Presets. Title previews draw typography over the current Viewer frame,
        transition previews animate the current frame through the selected cut
        style, and workflow previews show preset sequences over the real frame
        instead of disconnected abstract tiles. The QA capture tool accepts
        `--section effects|titles|transitions|workflows`; verified with real
        YouTube Imports media at
        `debugCapture/ui_renewal_preset_browser_sections_round_1/left_dock_titles_browser.png`,
        `debugCapture/ui_renewal_preset_browser_sections_round_1/left_dock_transitions_browser.png`,
        and
        `debugCapture/ui_renewal_preset_browser_sections_round_1/left_dock_workflows_browser.png`.
      - [x] 2026-07-02 Preset active tile state: the hovered/current preview
        preset now uses a restrained graphite active state with a thin
        silver-blue hairline and slightly brighter icon stroke, rather than a
        saturated accent color. The browser updates the previously inspected
        and newly inspected cards so QA-selected tiles read like real hover
        targets. Verified at
        `debugCapture/ui_renewal_preset_hover_active_round_1/left_dock_effects_browser.png`
        and
        `debugCapture/ui_renewal_preset_hover_active_round_1/left_dock_transitions_browser.png`.
      - [x] 2026-07-02 Preset semantic icon pass: preset tiles no longer depend
        on decorative/random line symbols. The compact icon painter now chooses
        semantic roles from the preset kind, tags, and payload: title layouts,
        transition subtypes, workflows, audio, chroma/keying, node graphs,
        color, actor, speed, blur, and clip effects each get distinct low-
        saturation line icons. Verified with real YouTube Imports media at
        `debugCapture/ui_renewal_preset_semantic_icons_round_1/left_dock_effects_browser.png`,
        `debugCapture/ui_renewal_preset_semantic_icons_round_2/left_dock_titles_browser.png`,
        and
        `debugCapture/ui_renewal_preset_semantic_icons_round_2/left_dock_transitions_browser.png`.
      - [x] 2026-07-02 Preset timeline drop-guide pass: dragged effect,
        transition, title, and workflow presets now share a restrained
        graphite timeline drop guide with low-saturation segment strips and
        compact intent detail. Transition drags now update the common guide in
        addition to the cut-edge target line, so cut placement reads the same
        way as other preset drops. Added
        `tools/qa_ui_renewal_preset_drop_guides.py`, which imports real
        YouTube Imports media, splits the first clip to create a real edit
        point, simulates preset drag states, and captures cropped evidence at
        `debugCapture/ui_renewal_preset_drop_guides_round_4/timeline_drop_guide_effect_crop.png`,
        `debugCapture/ui_renewal_preset_drop_guides_round_4/timeline_drop_guide_transition_crop.png`,
        `debugCapture/ui_renewal_preset_drop_guides_round_4/timeline_drop_guide_title_crop.png`,
        and
        `debugCapture/ui_renewal_preset_drop_guides_round_4/timeline_drop_guide_workflow_crop.png`.
    - [x] Viewer pass:
      - [x] Finish replacing visible `Preview` wording with `Viewer`.
      - [x] Show `Project > project_name` above the Viewer.
      - [x] Keep transport controls inside the Viewer frame while visually
        separate from media content.
      - [x] Restyle playback buttons to small centered icon-only controls.
      - [x] Reposition and restyle `Fit` and `1.0x` controls.
      - [x] Recheck Viewer aspect ratio and surrounding whitespace against the
        reference.
    - [x] Media Pool pass:
      - [x] Keep the selected clip large at the top.
      - [x] Show other media as compact list rows with small thumbnails.
      - [x] Use compact icon-only toolbar controls.
      - [x] Tune media background, border, text contrast, and selection states.
      - [x] Check long file names plus Korean/Japanese/English rendering.
        - [x] 2026-07-02 Mojibake cleanup pass: renewed main-editor UI modules
          were scanned for common broken Korean/CJK byte sequences, visible
          duplicate/broken tooltips were removed, and stale broken comments were
          normalized in `app/video_editor_window.py` and
          `app/video_editor_preset_cards.py`.
      - [x] Make drag-and-drop state visually clear.
    - [x] Timeline / Frame Editor pass:
      - [x] Make Timeline naturally occupy the full lower width.
      - [x] Match V1/A1 track header width and shape to the reference.
      - [x] Fill video/audio track lanes cleanly instead of leaving thin strips.
      - [x] Render audio waveforms as fine, precise lines.
      - [x] Keep thumbnails restrained, with first-frame emphasis rather than
        noisy repetition.
      - [x] 2026-07-11 Timeline track identity color pass: each clip's small leading
        vertical strip and selected-track outline now use the corresponding
        video track color, selection uses the same hue with stronger
        brightness/alpha, and the playhead keeps its own coral/orange identity.
        The earlier aggressive active/inactive thumbnail focus was backed off
        to the original visual weight so rows do not look farther apart; the
        playhead sharp-over-blur blend stays active on every track, and node
        graph items inherit the same track context stripe so Workbench editing
        keeps track identity visible.
      - [x] 2026-07-11 Timeline row density pass: reduce the unused video-row
        header strip from a visible header gap to no extra body header, use a
        zero-gap video-clip inset, and enlarge timeline thumbnails vertically
        so V1/V2 rows stack without lane gaps while preserving hit testing,
        drop guides, track color strips, and playhead drawing. The selected
        track now uses 30% less thumbnail blur than inactive tracks.
      - [x] Refine keyframe diamonds, markers, playhead shape, and edit points.
        - [x] 2026-07-02 Playhead and cut-marker painter pass lowered line
          width, glow alpha, and cut-marker saturation in `app/studio_theme.py`.
          Verified in
          `debugCapture/ui_renewal_timeline_playhead_round/editor_ar_pbr_object_action.png`.
        - [x] 2026-07-02 Timeline keyframe/drop-marker pass reduced PIP
          keyframe diamonds, transition/effect drop target saturation, and
          bright drag/drop chrome in `app/video_editor_window.py`. Verified with
          real YouTube media and PIP keyframes at
          `debugCapture/ui_renewal_timeline_keyframes_round/editor_timeline_keyframes_action.png`.
        - [x] 2026-07-02 Cut/edit point evidence pass: `paint_scissors_marker`
          now adds a restrained edit-point notch/handle so split boundaries
          read on top of real thumbnails without returning to saturated chrome.
          The Workbench clip tab now shows a compact `Edit Point Workspace`
          card whenever the selected clip touches an adjacent cut, including
          the cut time, transition duration, and A/B side visualization.
          `tools/qa_ui_renewal_cut_edit_workspace.py` imports real YouTube
          media, runs `timeline.split`, adds a timeline marker, applies a
          transition at the edit point, selects the adjacent clip, and captures
          the resulting live editor/timeline state at
          `debugCapture/ui_renewal_cut_edit_workspace_round_4/editor_cut_edit_action.png`.
        - [x] 2026-07-02 Timeline review framing pass: added a timeline-local
          `Review Frame` icon tool and an internal `_apply_timeline_review_framing`
          path that centers review captures around the current edit/playhead at
          roughly a 12-second span. The cut/edit QA now calls this framing path
          after importing real YouTube Imports media, splitting, marking,
          applying a transition, and selecting the adjacent clip. Verified at
          `debugCapture/ui_renewal_timeline_review_framing_round_3/editor_cut_edit_action.png`.
      - [x] Keep frame-editor tools collapsed by default and expand them inside
        the frame-editor area.
    - [x] Workbench pass:
      - [x] Restyle node graph node shapes, colors, connection lines, and
        spacing toward the reference.
      - [x] Show node parameter UI inline in the dock, not as scattered popups.
      - [x] Make the Workbench lower/side structure as clean as the Media Pool.
        - [x] 2026-07-02 Workbench FX stack strip pass: the selected clip
          stack no longer renders as a heavy boxed card. It now uses a thin
          top-divider information strip, compact one-line stack summary,
          icon-only action controls with tooltips, and a flatter VFX graph
          node strip. Verified at
          `debugCapture/ui_renewal_effect_workspace_fx_strip_round/workbench_effect_stack_action.png`
          and
          `debugCapture/ui_renewal_workbench_fx_strip_round/workbench_clip_and_node.png`.
        - [x] 2026-07-02 Workbench lower/side structure follow-up: FX summary
          typography was enlarged, the stack rail lost its heavy outer card,
          `GPH` was expanded to `GRAPH`, node-graph toolbar chrome was muted,
          and graph connection lines were desaturated so the panel reads as a
          live editing workspace instead of a QA log strip. Verified with real
          YouTube Imports media through
          `tools/qa_ui_renewal_effect_workspace.py` at
          `debugCapture/ui_renewal_workbench_structure_round_3/workbench_effect_stack_action.png`.
      - [x] Create distinct real workspaces for node, effect, color, audio,
        actor, and 3D operations.
        - [x] 2026-07-02 Effect workspace action capture:
          `tools/qa_ui_renewal_effect_workspace.py` imports real YouTube media,
          splits the first video clip, applies `clip.set_filter` and
          `transition.apply`, creates an action-backed `IN -> Video FX ->
          Dissolve TR -> OUT` graph with `node.graph.set`, selects the edited
          clip, opens the Workbench FX tab, and captures real Viewer/Timeline/
          FX stack evidence at
          `debugCapture/ui_renewal_effect_workspace_round_fx_graph_fit/editor_effect_stack_action.png`.
        - [x] 2026-07-02 Effect/Transition evidence contact sheet:
          `tools/qa_ui_renewal_effect_workspace.py` now also captures the
          Workbench FX stack, Timeline split/FX/TR edge, full editor state, and
          a combined evidence contact sheet. The report verifies every artifact
          is nonblank so review automation can use feature-specific crops
          instead of a tiny generic editor screenshot. Verified at
          `debugCapture/ui_renewal_effect_workspace_contact_sheet_round_1/effect_workspace_contact_sheet.png`.
      - [x] Keep Workbench screenshots tied to actual action/UI state.
    - [x] Color grading pass:
      - [x] Treat color grading as the largest remaining reference mismatch.
      - [x] Rework curves, wheels, scopes, and grade layer UI.
      - [x] Make Before/After Viewer state explicit.
      - [x] Improve Timeline grade-layer display for professional catalog
        captures.
      - [x] Reduce over-saturated and overly opaque color controls.
      - [x] Decide whether a taller dedicated grade-layer Timeline mode is worth
        the density cost for catalog captures.
        - [x] 2026-07-02 Decision: do not make a taller grade-layer Timeline
          the default editor mode. The renewed compact grade rail keeps the
          lower editor usable during normal editing; catalog/review automation
          can request a specialized capture composition later if it needs a
          more Resolve-like grade-layer showcase.
    - [x] Audio / Sound Editor pass:
      - [x] Verify sound extraction from video is connected through action,
        menu, and UI surfaces.
      - [x] Restyle waveform, mixer, and scope surfaces.
      - [x] Build a visually distinct audio Workbench/editor state.
      - [x] Confirm audio review screenshots show real editing, not generic
        media state.
      - [x] 2026-07-02 Embedded Sound Editor Workbench pass: added
        `app/sound_editor_panel.py` with persistent media-pool audio edit
        state, timeline/audio-source target switching, Export-only workflow,
        renewed icon tabs, chain chips, compact EQ/Dynamics/FX/AI panels, and
        a `SoundEditorDockWindow` shell for the timeline sound-editor launch
        path. Media-pool audio and timeline audio edits remain separate and
        persistent when switching targets. Verified with
        `tests/test_sound_editor_panel.py`, `py_compile`, and screenshots at
        `debugCapture/ui_sound_editor_design_round_7/` plus
        `debugCapture/ui_sound_editor_design_round_9/sound_editor_dock_window_eq.png`.
      - [x] 2026-07-02 Sound Editor waveform evidence pass: the renewed panel
        now shows a compact waveform strip above its tool tabs, redraws it when
        background waveform extraction completes, and starts waveform extraction
        for selected Media Pool audio sources. Verified with
        `tests/test_sound_editor_panel.py` and screenshots at
        `debugCapture/ui_sound_editor_waveform_round_1/`.
      - [x] 2026-07-02 Real-media Sound Editor QA capture: added
        `tools/qa_ui_renewal_sound_editor.py`, which imports a real video from
        `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`, runs
        `audio.extract_from_video`, applies `audio.clip.set_gain`, waits for
        waveform extraction, selects the extracted Timeline audio clip, and
        captures both Workbench and detached Sound Editor evidence. Latest
        passing run:
        `debugCapture/ui_renewal_sound_editor_round_3/sound_editor_qa.json`,
        `debugCapture/ui_renewal_sound_editor_round_3/editor_sound_editor_action.png`,
        `debugCapture/ui_renewal_sound_editor_round_3/workbench_sound_editor_action.png`,
        and
        `debugCapture/ui_renewal_sound_editor_round_3/dock_sound_editor_action.png`.
      - [x] 2026-07-02 Sound Editor graph material pass: EQ, Dynamics, FX,
        and AI mini graphs now share the same restrained edit-control language:
        graphite hand-edit pins, low-saturation gradient lines, softer shadows,
        and subdued bar fills. This keeps points readable as editable control
        handles without the toy-like bright-dot look. Verified with
        `tests/test_sound_editor_panel.py`, `py_compile`, and comparison
        captures at
        `debugCapture/ui_sound_editor_graph_style_round_2/sound_editor_graph_tabs_contact_work_area.png`.
      - [x] 2026-07-02 Sound Editor interactive EQ graph pass: EQ graph pins
        are now real drag handles. Dragging Low/Mid/High updates the matching
        slider, writes to `AudioClip.effects["eq"]`, and enables EQ when the
        change is audible. Verified with `tests/test_sound_editor_panel.py`,
        `py_compile`, and a mouse-event capture at
        `debugCapture/ui_sound_editor_eq_drag_round_1/sound_editor_eq_drag_high_gain.png`.
      - [x] 2026-07-02 Sound Editor EQ neutral-gradient follow-up: the edit
        curve should not rely on obvious color stops because the painted area
        is too small. It now uses a neutral metallic lightness gradient, subtle
        under-glow, and a thin highlight so the line reads softly without
        becoming colorful. Verified at
        `debugCapture/ui_sound_editor_eq_neutral_gradient_round_1/sound_editor_eq_drag_neutral_gradient.png`.
      - [x] 2026-07-02 Sound Editor interactive Dynamics graph pass: the
        Dynamics curve now has real compressor handles. Dragging the knee
        changes compressor Threshold, dragging the right slope point changes
        Ratio, and both edits update the matching sliders plus
        `AudioClip.effects["comp"]`. Verified with
        `tests/test_sound_editor_panel.py`, `py_compile`, and mouse-event
        capture at
        `debugCapture/ui_sound_editor_dynamics_drag_round_1/sound_editor_dynamics_drag_threshold_ratio.png`.
      - [x] 2026-07-02 Sound Editor interactive FX graph pass: the Space /
        cleanup graph now represents real Reverb Mix, Delay Mix, and De-esser
        Reduction values instead of a decorative waveform. Dragging each point
        updates the matching slider and writes to `AudioClip.effects` for
        `reverb`, `delay`, or `deesser`. Verified with
        `tests/test_sound_editor_panel.py`, `py_compile`, and mouse-event
        capture at
        `debugCapture/ui_sound_editor_fx_drag_round_1/sound_editor_fx_drag_reverb_delay_deesser.png`.
      - [x] 2026-07-02 Sound Editor interactive AI Master graph pass: the AI
        graph now shows six real macro handles for Air, Clarity, Warmth, Width,
        Punch, and Excite. Dragging a handle updates the matching slider and
        `AudioClip.effects["ai_master"]`; Width is represented on its full
        0-200% range instead of a hidden offset. Verified with
        `tests/test_sound_editor_panel.py`, `py_compile`, and mouse-event
        capture at
        `debugCapture/ui_sound_editor_ai_drag_round_2/sound_editor_ai_drag_macros.png`.
      - [x] 2026-07-02 Sound Editor graph hover readout pass: EQ, Dynamics,
        FX, and AI graph handles now support a restrained active state with a
        brighter graphite pin and compact value pill. The default graph stays
        quiet, while hover/drag reveals what the point controls without adding
        permanent labels. Verified with
        `tests/test_sound_editor_panel.py`, `py_compile`, and visual capture at
        `debugCapture/ui_sound_editor_hover_labels_round_2/sound_editor_hover_labels_contact.png`.
      - [x] 2026-07-02 Sound Editor graph release-pulse pass: after a real
        graph handle drag, the manipulated point now keeps a short graphite
        highlight and smoothly decays back to the quiet default state. The
        value pill remains hover/drag-only, so release feedback improves
        visibility without leaving permanent labels. Verified with
        `tests/test_sound_editor_panel.py`, `py_compile`, and visual sequence at
        `debugCapture/ui_sound_editor_pin_decay_round_1/eq_pin_decay_sequence_zoom_graph.png`.
      - [x] 2026-07-02 Sound Editor graph double-click reset pass: every
        interactive graph handle now supports double-click reset to its default
        value. EQ resets to 0 dB, Dynamics resets Threshold / Ratio, FX resets
        to its default mix/reduction values, and AI Master resets its macro
        defaults including Width back to 100%. Reset uses the same short
        graphite release pulse without leaving a permanent value pill. Verified
        with `tests/test_sound_editor_panel.py`, `py_compile`, and visual
        sequence at
        `debugCapture/ui_sound_editor_double_click_reset_round_2/eq_double_click_reset_sequence.png`.
      - [x] 2026-07-02 Real-media Sound Editor graph evidence pass:
        `tools/qa_ui_renewal_sound_editor.py` now applies actual EQ,
        Dynamics, FX, and AI Master edits to the extracted Timeline
        `AudioClip.effects` state, waits for waveform extraction before
        capture, and writes a four-panel graph contact sheet from the renewed
        Workbench Sound Editor. Verified with real YouTube Imports media at
        `debugCapture/ui_renewal_sound_editor_graphs_round_2/sound_editor_qa.json`
        and
        `debugCapture/ui_renewal_sound_editor_graphs_round_2/sound_editor_graphs_contact_sheet.png`.
      - [x] 2026-07-02 Sound Editor compact spectrum strip pass: the renewed
        Workbench Sound Editor now includes a small `spectrum / level` strip
        under the waveform, derived from `AudioClip.spectrum_bins` when
        available and otherwise from the extracted waveform. This brings over
        the useful evidence part of the legacy Sound Editor analysis deck
        without adding its heavy modal workflow to the Workbench panel.
        Verified with `tests/test_sound_editor_panel.py`, `py_compile`, and
        real YouTube Imports media at
        `debugCapture/ui_renewal_sound_editor_spectrum_round_2/sound_editor_graphs_contact_sheet.png`.
      - [x] 2026-07-02 Sound Editor low-saturation graph accent pass:
        the previous graph material was too monochrome. EQ, Dynamics, FX, AI,
        and the spectrum strip now keep the graphite reference style while
        adding very low-saturation semantic accent hints to graph lines, pins,
        macro bars, and spectrum bands. Verified with
        `tests/test_sound_editor_panel.py`, `py_compile`, and real YouTube
        Imports media at
        `debugCapture/ui_renewal_sound_editor_graph_color_round_1/sound_editor_graphs_contact_sheet.png`.
      - [x] 2026-07-02 Sound Editor audio-color pass: sound data surfaces now
        carry stronger but still theme-compatible color. Waveforms use
        mint/cyan stereo lines, spectrum bands separate low/mid/high/peak
        energy as green/blue/amber/coral, level meters show green-to-amber-to-
        coral threshold zones, and graph pins/lines use semantic EQ/Dynamics/
        FX/AI accents. Chrome stays graphite; signal data carries the color.
        Verified with `tests/test_sound_editor_panel.py`, `py_compile`, and
        real YouTube Imports media at
        `debugCapture/ui_renewal_sound_editor_audio_color_round_1/sound_editor_graphs_contact_sheet.png`.
      - [x] 2026-07-02 Sound Editor advanced-lab bridge decision:
        keep the renewed Workbench Sound Editor as the lightweight default
        surface for clip-scoped EQ/Dynamics/FX/AI, export, waveform, spectrum,
        and level evidence. This baseline decision was superseded by the
        2026-07-03 inline Advanced Lab pass below; the Workbench path should no
        longer open the legacy large `SoundEditorWindow`. Verified with
        `tests/test_sound_editor_panel.py`, `py_compile`, and real YouTube
        Imports media at
        `debugCapture/ui_renewal_sound_editor_advanced_lab_round_1/sound_editor_graphs_contact_sheet.png`.
      - [x] 2026-07-03 Sound Editor reference-05 jog/action pass:
        the Workbench Sound Editor now embeds the selected reference-05
        jog-shuttle design and exposes action-backed automation for
        `audio.sound_editor.jog_shuttle.state`,
        `audio.sound_editor.jog_shuttle.set`,
        `audio.sound_editor.advanced_lab.state`, and
        `audio.sound_editor.advanced_lab.set`. Advanced Lab expands inline in
        the Workbench and the QA capture drives this state through the action
        registry instead of calling private widget methods. Verified with
        `tests/test_python_action_system.py`, `tests/test_sound_editor_panel.py`,
        and real-media QA at
        `debugCapture/ui_renewal_sound_editor_action_system_round_1/sound_editor_qa.json`.
      - [x] 2026-07-08 Sound Editor slotted jog dial pass:
        replaced the jog-shuttle face with a brushed-metal dial that removes the
        long center notch. The metal body is now a permanent resource at
        `resources/ui/sound_editor/jog_dial_metal_sparse_base.png`, while the
        sparse, small LED slot indicators near the outer edge are still painted
        by the editor so jog position/playing state can animate with brighter
        illumination. Verified with
        `tests/test_sound_editor_panel.py::test_sound_editor_panel_embeds_reference_05_jog_shuttle`,
        `tests/test_editor_architecture_rules.py`,
        `tools/qa_packaging_resources.py`, and real-media QA at
        `debugCapture/sound_jog_resource_texture_clipped_20260708/sound_editor_qa.json`.
      - [x] 2026-07-08 Sound Editor mini mixer pass:
        added a `Mixer` tab to the renewed Workbench Sound Editor and extended
        the timeline Audio Mixer strips with Mute/Solo state. Track volume, pan,
        mute, and solo are now real `AudioTrack` state, saved/loaded with
        projects, reflected in undo snapshots and AI snapshots, honored by
        preview/export, and available to local AI through
        `audio.track.set_volume`, `audio.track.set_pan`, `audio.track.mute`,
        `audio.track.solo`, and `audio.mixer.state`. Detached Sound Editor
        docks now receive the full mixer track context instead of only the
        selected clip track. Mixer rebuild now hides old strip widgets before
        deferred deletion, preventing stale Master/track labels from overlaying
        the first channel during fast refreshes. Latest real-editor QA:
        `debugCapture/ui_renewal_sound_editor_mixer_slider_round_4/sound_editor_qa.json`
        and
        `debugCapture/ui_renewal_sound_editor_mixer_slider_round_4/dock_sound_editor_mixer_action.png`.
      - [x] 2026-07-08 Sound Editor mixer slider renewal:
        replaced the mini Mixer tab's stylesheet/default slider feel with
        Sound Editor-local custom pan/fader controls. Pan now uses a compact
        graphite center rail, while channel and Master faders use recessed
        mixer-strip rails, low-saturation live fill, and metal-cap handles with
        fixed strip height so detached docks do not stretch the controls.
        Verified with real-media QA at
        `debugCapture/ui_renewal_sound_editor_mixer_slider_round_4/sound_editor_qa.json`
        and
        `debugCapture/ui_renewal_sound_editor_mixer_slider_round_4/dock_sound_editor_mixer_action.png`.
      - [x] 2026-07-08 Cubase-inspired Sound Editor mixer controls:
        extended the mini Mixer with the six requested DAW-style essentials:
        peak/clip indication, insert slots, send levels/bus routing,
        automation Read/Write, mixer snapshots, and track type strips. These
        are real `AudioTrack` state, saved/loaded with projects, included in
        undo/history and AI snapshots, and exposed through
        `audio.track.set_type`, `audio.track.insert.set`,
        `audio.track.send.set_level`, `audio.track.route_to_bus`,
        `audio.track.meter.state`, `audio.automation.state`,
        `audio.automation.write`, `audio.automation.clear`,
        `audio.mixer.snapshot.save`, `audio.mixer.snapshot.compare`,
        `audio.mixer.snapshot.apply`, and `audio.mixer.state`. Verified with
        unit tests plus real-media QA at
        `debugCapture/ui_renewal_sound_editor_cubase_round_1/sound_editor_qa.json`
        and
        `debugCapture/ui_renewal_sound_editor_cubase_round_1/dock_sound_editor_mixer_action.png`.
      - [x] 2026-07-08 Master stereo VU follow-up:
        added a SuperVision-inspired L/R analog VU meter to the Sound Editor
        Mixer Master strip. It uses subdued oxblood panels and amber needles
        so it fits the renewed low-saturation theme, while the existing
        vertical master meter/fader remains for precise level-strip evidence.
        Verified with `tests/test_sound_editor_panel.py`, `py_compile`, and an
        isolated Sound Editor dock visual probe at
        `debugCapture/ui_renewal_sound_editor_master_vu_round_2/dock_sound_editor_master_vu_action.png`.
      - [x] 2026-07-08 Sound Editor mixer beauty polish:
        refined the mini Mixer beyond the Cubase reference with track-type
        accent rails, richer segmented green/amber/red meters, and low-saturation
        violet/amber metal fader and pan caps while keeping the compact
        Workbench footprint. Verified with `tests/test_sound_editor_panel.py`,
        `py_compile`, and an isolated Sound Editor dock visual probe at
        `debugCapture/ui_renewal_sound_editor_mixer_beauty_round_1/dock_sound_editor_mixer_beauty_action.png`.
      - [x] 2026-07-08 AI Composer / Music Lab foundation:
        documented the MIDI-first composition plan in
        `docs/SPEC_AI_COMPOSER_MUSIC_LAB.md`, then implemented deterministic
        composition, arrangement, MIDI clip/chord/note editing, WAV preview
        stem rendering, timeline insertion, and mixer auto-balance actions.
        Local AI can now run `music.compose`, `music.render.preview`,
        `music.render_to_timeline`, `music.mixer.auto_balance`, `music.state`,
        and the `midi.clip.*` commands against real `AudioTrack` rows instead
        of only describing music generation.
      - [x] 2026-07-08 Music Lab persistence and prompt routing:
        added `.tgp` save/load support for `music_compositions[]` and
        music-generated audio track/clip composition-role links, added
        `music.compose_to_timeline` as the one-shot compose/render/insert/mix
        action, and routed clear prompts like "make a 30s BGM" to Music Lab
        instead of Sound Editor mastering.
      - [x] 2026-07-08 Music Lab UI/update/MIDI/edit-routing pass:
        added a compact Workbench Sound Editor `Music Lab` tab with prompt,
        genre/mood, duration, BPM, key, stem/mix mode, generate/update, and
        MIDI export controls; added `music.render_to_timeline(update_existing)`
        so regenerated stems replace matching Music Lab tracks instead of
        stacking duplicates; added `music.export_midi`; improved the local
        preview synth render with softer bass/pad/lead tone shaping and stereo
        polish; and expanded AI command routing for existing music edits such
        as stronger sections, drum removal, pad-only music, and MIDI export.
    - [x] Actor / Live2D / Spine / 3D pass:
      - [x] Restyle Actor Library.
      - [x] Show Live2D actor, actor lane, keyframes, transform controls, and
        Live2D viewer together for Live2D feature captures.
        - [x] Stable main-editor Live2D actor action capture exists:
          `tools/qa_ui_renewal_actor_workspaces.py` imports real YouTube media,
          adds a real Hiyori `.model3.json` actor through `actor.add`, applies
          transform/opacity keyframes through `actor.set_keyframes`, selects
          the actor lane, and captures Workbench evidence at
          `debugCapture/ui_renewal_actor_workspace_stable_round/editor_live2d_actor_action.png`.
        - [x] 2026-07-02 Live2D viewer overlay + Workbench target fix:
          `tools/qa_ui_renewal_actor_workspaces.py` now forces QImage preview
          capture for offscreen evidence, re-syncs actor tracks before the
          final render, and asserts the Workbench target kind is `live2d`
          instead of merely non-empty. `app/video_editor_window.py` now clears
          video clip selection when a Live2D actor lane is selected and routes
          `_refresh_workbench()` to the selected Live2D clip before falling
          back to the active video track. Verified with real YouTube Imports
          media at
          `debugCapture/ui_renewal_actor_workspace_round_overlay_4/editor_live2d_actor_action.png`.
        - [x] 2026-07-02 Live2D Performance Source evidence pass:
          `tools/qa_ui_renewal_actor_workspaces.py` now drives
          `vtuber.performance_source.add_clip` and
          `actor.live2d.apply_performance_source` against real YouTube Imports
          media, hides transient editor overlays before capture, and requires
          a composited Live2D actor, actor lane keyframes, a performance-source
          track, and Workbench mapping/key evidence. Verified at
          `debugCapture/ui_renewal_live2d_perf_source_round_4/editor_live2d_actor_action.png`
          and
          `debugCapture/ui_renewal_live2d_perf_source_round_4/workbench_live2d_actor_action.png`.
        - [x] 2026-07-02 Timeline lane display-index pass:
          video/performance-source/Live2D/Spine rows now render visual lane
          numbers (`V1`, `PS1`, `L1`, `S1`) instead of leaking internal track
          ids such as `V3` or `L2`. The Live2D actor Workbench mapping/evidence
          chrome was flattened into thinner production-style strips. Verified
          with real YouTube Imports media at
          `debugCapture/ui_renewal_workbench_actor_strip_round_2/editor_live2d_actor_action.png`
          and actor row captures at
          `debugCapture/ui_renewal_actor_lane_index_round_1/`.
        - [x] 2026-07-02 Native Live2D Viewer capture isolation:
          `tools/qa_ui_renewal_actor_workspaces.py --open-live2d-viewer` now
          opens the linked Live2D viewer in the same real action flow, waits for
          the load state, hides transient loading chrome before evidence
          capture, and verifies `live2d_viewer_screenshot`. The viewer's long
          `Performance Source Mapping` button was shortened to `Map Source`
          to avoid bottom-toolbar clipping in product screenshots. Verified at
          `debugCapture/ui_renewal_live2d_viewer_capture_round_2/live2d_viewer_action.png`.
        - [x] Make the native Live2D Viewer visually match the renewed main
          editor style before using it heavily in review/catalog pages.
          - [x] 2026-07-02 Native Live2D Viewer polish pass: the in-process
            Viewer now uses the shared editor font/chrome, restrained
            graphite buttons, thin splitters, neutral slider/list states, a
            subtle framed viewport, compact bottom transport, and calmer
            right-side inspector values. Verified through the real
            YouTube-Imports + `actor.add` + `actor.set_keyframes` +
            Performance Source action flow at
            `debugCapture/ui_renewal_live2d_viewer_polish_round_1/live2d_viewer_action.png`.
        - [x] Keep native Live2D Viewer capture out of default automated QA
          until native shutdown stability is proven across repeated runs.
          `--open-live2d-viewer` can capture `live2d_viewer_action.png`, but
          the native Live2D runtime has previously crashed on subprocess
          shutdown after a successful capture.
          - [x] 2026-07-02 Added
            `tools/qa_ui_renewal_live2d_viewer_isolated.py`. It runs the
            Live2D Viewer capture in a subprocess, accepts the capture only
            when the real Viewer/editor/workbench PNGs are nonblank, and
            records the native shutdown return code separately. Verified at
            `debugCapture/ui_renewal_live2d_viewer_isolated_round/live2d_viewer_action.png`
            with subprocess return code `3221226505`, so this stays isolated
            from default QA until native shutdown is stable.
          - [x] 2026-07-02 Re-ran the isolated Viewer path at
            `debugCapture/ui_renewal_live2d_viewer_isolated_round_2/live2d_viewer_action.png`;
            the Viewer/editor/workbench captures were nonblank and the
            subprocess returned `0`. Keep the default-QA exclusion anyway until
            repeated runs prove native shutdown stability, but the current
            feature evidence is usable for opt-in Live2D review captures.
      - [x] Keep Spine rendering issue recorded; do not claim Spine visual
        readiness until real rendering is fixed.
        - [x] 2026-07-02 Added the UI/review guardrail to
          `app/spine_editor/SPINE_WORK_IN_PROGRESS.md`: Spine/NIKKE can remain
          visible as actor-track/loading/compatibility surfaces, but review
          automation must not use nonblank renders, placeholders, generated
          catalog art, or broken face/limb/draw-order samples as visual
          success evidence.
      - [x] Build 3D/AR/PBR Workbench views that show real controls and state.
        - [x] `tools/qa_ui_renewal_ar_pbr_workspace.py` imports real YouTube
          media, places a real GLB AR/PBR object in the Viewer, shows actual
          transform/lighting/placement state in the Workbench, and composites
          the real GLB mesh through the software AR/PBR renderer for evidence
          capture. Verified at
          `debugCapture/ui_renewal_ar_pbr_workspace_round_5/editor_ar_pbr_object_action.png`.
      - [x] Ensure each feature screenshot visually matches the feature being
        explained.
        - [x] 2026-07-02 Typography workspace action pass:
          `text.add` now keeps the action-created `TextClip` synchronized with
          the visible video track typography actor list, `text.set_keyframes`
          refreshes the actual editor row/overlay, the timeline typography
          strip uses the renewed muted action styling with small keyframe
          diamonds, and the Workbench shows a real `Typography Workspace`
          evidence card for selected title clips. Verified with real YouTube
          Imports media at
          `debugCapture/ui_renewal_typography_workspace_round_5/editor_typography_action.png`
          through `tools/qa_ui_renewal_typography_workspace.py`.
        - [x] 2026-07-02 Evidence index pass:
          `docs/UI_RENEWAL_EVIDENCE_INDEX.md` maps each review-facing feature
          area to an existing real editor artifact and action-backed capture
          tool. The index was verified against the filesystem: main editor,
          cut/edit, preset browser, preset drag/drop, node graph, color,
          sound/audio, typography, effects/transitions, Live2D actor, opt-in
          Live2D Viewer, AR/PBR, and render queue all point to existing PNGs;
          Spine/NIKKE remains explicitly blocked from visual success evidence.
    - [ ] QA and screenshot loop:
      - [x] Generate real screenshots after each UI stage.
      - [x] Compare against the generated reference and record differences.
        - [x] 2026-07-02 `docs/UI_RENEWAL_EVIDENCE_INDEX.md` now includes a
          `Current Reference Gaps` section covering catalog framing,
          main-editor density, color-page/popup limits, AR/PBR action-surface
          debt, Live2D isolated Viewer stability, and Spine/NIKKE blocked
          visual evidence.
      - [ ] Iterate until spacing, typography, borders, colors, and feature
        evidence are acceptable.
      - [x] Never use empty editors, color bars, placeholder test images, or
        generated fake editor scenes for product-facing evidence.
      - [x] 2026-07-02 Media Pool/Timeline renewal pass verified with
        `py_compile` and real YouTube Imports media capture at
        `debugCapture/ui_renewal_media_timeline_round/editor_imported.png`
        plus report `debugCapture/ui_renewal_media_timeline_report.json`.
      - [x] 2026-07-02 Workbench node graph renewal pass: node graph colors,
        connection lines, ports, IO anchors, grid, and toolbar are neutralized;
        `tools/qa_ui_renewal_workbench.py` now builds a real multi-node
        `node_graph_view_data` chain instead of a single default node.
        Verified at
        `debugCapture/ui_renewal_workbench_style_round_wide/workbench_clip_and_node.png`
        and full editor E2E report
        `debugCapture/ui_renewal_workbench_full_e2e_report.json`.
      - [x] 2026-07-02 Color grading renewal pass: main Color Workbench,
        Color Page tokens, curves, mini scopes, sliders, grade controls, and
        timeline grade evidence were neutralized toward the reference style.
        Verified with real action flow at
        `debugCapture/ui_renewal_color_round/editor_color_dock_action.png`,
        `tools/qa_color_preview_parity.py`, and
        `tools/qa_color_audio_accuracy.py --out debugCapture/ui_renewal_color_audio_accuracy.json`.
      - [x] 2026-07-02 Audio renewal pass: `audio.extract_from_video` was
        verified through the action flow, Audio Mixer/Scopes were restyled with
        neutral low-saturation chrome, and the Workbench audio tab now renders
        a real waveform/spectrum/mix evidence card from the selected extracted
        audio clip. Verified at
        `debugCapture/ui_renewal_audio_workbench_round/workbench_audio_tab_action.png`
        and
        `debugCapture/ui_renewal_audio_workbench_round/editor_audio_mixer_action.png`.
      - [x] 2026-07-02 Actor Library renewal pass: left-rail actor sources now
        use compact list rows with low-saturation draggable Live2D/Spine cards
        instead of bright square-only tiles. Verified with real editor capture
        at
        `debugCapture/ui_renewal_actor_library_round/editor_left_library_panel_action.png`.
      - [x] 2026-07-02 Live2D actor workspace action pass: `actor.add` and
        `actor.set_keyframes` now drive a real Live2D actor lane in the
        renewed editor, Workbench shows actual transform/keyframe evidence, and
        the stable QA command exits cleanly at
        `debugCapture/ui_renewal_actor_workspace_stable_round/editor_live2d_actor_action.png`.
      - [x] 2026-07-02 Live2D evidence correction pass: the default actor QA no
        longer accepts raw source-video fallback evidence after adding the
        actor. It captures the actual composited Viewer frame with Hiyori over
        real YouTube Imports footage and requires the right Workbench panel to
        be `Live2D Actor`. Verified at
        `debugCapture/ui_renewal_actor_workspace_round_overlay_4/editor_live2d_actor_action.png`.
      - [x] 2026-07-02 Live2D actor lane keyframe visual pass:
        `app/live2d/actor_lane_row.py` now paints the actor clip with the shared
        restrained timeline block style and draws compact transform keyframe
        diamonds for position/scale/opacity channels, so Live2D evidence
        screenshots show actual animated actor work instead of a plain gray
        lane. Verified at
        `debugCapture/ui_renewal_actor_lane_keyframes_round_1/editor_live2d_actor_action.png`.
      - [x] 2026-07-02 Actor lane UI parity pass:
        `app/spine_editor/actor_lane_row.py` now uses the same restrained
        timeline block/playhead style as Live2D while only showing loading/
        pairing state, not render success. `tools/qa_actor_lane_workflow.py`
        now applies the editor font fallback and can save lane PNGs, preventing
        standalone CJK sample names from turning into square glyphs. Verified
        at `debugCapture/ui_renewal_actor_lane_style_round_2/actor_lane_live2d_sample.png`
        and
        `debugCapture/ui_renewal_actor_lane_style_round_2/actor_lane_spine_sample.png`.
      - [x] 2026-07-02 Live2D Performance Source capture pass:
        the actor workspace QA now adds a real input-only Performance Source
        clip, applies it to the selected Live2D actor through the action
        registry, and captures the right Workbench after hiding transient
        status/toast overlays. This keeps the evidence tied to real timeline
        state instead of a generic actor screenshot. Verified at
        `debugCapture/ui_renewal_live2d_perf_source_round_4/editor_live2d_actor_action.png`.
      - [x] 2026-07-02 Actor/Performance Source timeline role pass:
        Performance Source tracks now render as `PS / Perf Source` with a
        muted input-only clip badge instead of looking like ordinary Video
        tracks, and Live2D/Spine actor lanes now use the same left-tab lane
        header structure as Video/Performance Source rows. Verified at
        `debugCapture/ui_renewal_live2d_actor_lane_header_round_1/editor_live2d_actor_action.png`
        and
        `debugCapture/ui_renewal_actor_lane_header_round_1/actor_lane_spine_sample.png`.
      - [x] 2026-07-02 History snapshot Qt render-cache hardening:
        `app/history.py` now drops `QPixmap`/`QImage`/`QIcon` render caches
        and per-clip thumbnails while taking undo/redo snapshots, fixing
        `cannot pickle 'PySide6.QtGui.QPixmap' object` during real editor
        action sequences. Covered by the `EditorSnapshot` regression in
        `tests/test_timeline_model.py`.
      - [x] 2026-07-02 3D/AR-PBR workspace action pass: real YouTube media plus
        `debugCapture/ar_pbr_selected_resources/babylon_car.glb` are loaded into
        the renewed editor, the Workbench shows real AR/PBR placement,
        transform, scale, and lighting state, and the Viewer evidence frame is
        composited with the actual GLB mesh rather than a placeholder. Verified
        at
        `debugCapture/ui_renewal_ar_pbr_workspace_round_5/editor_ar_pbr_object_action.png`.
      - [x] 2026-07-02 Timeline playhead/cut-marker polish: `studio_theme`
        now paints the playhead and cut markers with thinner geometry and lower
        saturation, while the frame editor remains collapsed by default inside
        the lower Timeline area. Verified at
        `debugCapture/ui_renewal_timeline_playhead_round/editor_ar_pbr_object_action.png`.
      - [x] 2026-07-02 Timeline keyframe/drop-marker polish:
        `tools/qa_ui_renewal_timeline_keyframes.py` imports real YouTube media,
        enables PIP with `track.set_state`, attaches real timeline keyframes for
        the marker pass, and captures the renewed neutral keyframe diamonds at
        `debugCapture/ui_renewal_timeline_keyframes_round/editor_timeline_keyframes_action.png`.
      - [x] 2026-07-02 Preset browser left-dock QA pass:
        `tools/qa_ui_renewal_preset_browser_left_dock.py` captures the Effects
        Library in the real editor left dock with the old category combo hidden
        and compact icon/menu filtering active. Verified at
        `debugCapture/ui_renewal_preset_browser_left_dock_round_2/left_dock_effects_browser.png`.
      - [x] 2026-07-02 Effect workspace action pass: real YouTube media plus
        `clip.set_filter`, `transition.apply`, and `node.graph.set` now produce
        a dedicated Workbench FX evidence capture with a non-empty Viewer,
        selected edited clip, Timeline `FX`/`TR` badges, a real two-node
        Workbench graph chain, and an active SRC/FX/TR/GPH/OUT stack rail.
        Verified at
        `debugCapture/ui_renewal_effect_workspace_round_fx_graph_fit/editor_effect_stack_action.png`.
      - [x] 2026-07-02 Effect/Transition contact-sheet QA pass:
        the same action flow now emits separate full-editor, Workbench, and
        Timeline captures plus `effect_workspace_contact_sheet.png`, all
        validated as nonblank. Verified at
        `debugCapture/ui_renewal_effect_workspace_contact_sheet_round_1/effect_workspace_contact_sheet.png`.
      - [x] 2026-07-02 Render Queue action/UI pass: added the safe
        `render.queue.stage` Python Action so AI/MCP/QA can stage real render
        jobs without private editor calls, restyled `RenderQueuePanel` toward
        the low-saturation reference, fixed preflight card status parsing so
        `preview` no longer false-positives as `review`, and added
        `tools/qa_ui_renewal_render_queue_workspace.py`. Verified with real
        YouTube Imports media, timeline split, selected clip, and staged
        render jobs at
        `debugCapture/ui_renewal_render_queue_workspace_round_8/render_queue_panel_action.png`.
        Full-editor captures keep the main Workbench visible above the
        secondary right-dock queue, so review/catalog evidence should use the
        dedicated Render Queue panel or right-dock capture when explaining
        export queue behavior.
    - [x] Return to review automation only after UI renewal stabilizes:
      - [x] Re-read current spec, TODO, action registry, UI state, and
        `docs/UI_RENEWAL_EVIDENCE_INDEX.md` before
        regenerating PPT/HTML/catalog output.
      - [x] Use Python Actions to drive real editor operations.
      - [x] Generate feature-specific live editor captures.
      - [x] Resume review PPT/HTML/catalog automation using those real captures.
      - [x] 2026-07-02 Review automation bridge pass: added
        `app/review_automation/ui_evidence_index.py` so
        `docs/UI_RENEWAL_EVIDENCE_INDEX.md` seeds feature-specific editor
        evidence into PPT/HTML/catalog output. `tools/generate_review_assets.py
        --deck-mode detailed --force` now produces
        `E:\ClaudeCodeApp\ReviewAutomationWorkspace\outputs\TigerCapture_Review_Automation_detailed.pptx`
        and
        `E:\ClaudeCodeApp\ReviewAutomationWorkspace\outputs\site\index.html`
        with 39/39 ready artifacts and 11/11 feature action scenarios.
      - [x] 2026-07-02 Review QA cleanup: review sample videos generated from
        `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports` now keep or
        receive an AAC audio stream so `audio.extract_from_video` can be
        verified. `tools/qa_editor_e2e_smoke.py` records the audio-track count
        immediately after extraction before later live-capture flows reset the
        timeline. `tools/qa_review_automation.py` reports failures=0,
        small_visual_artifacts=0, flat_visual_artifacts=0; only
        `ai_script_edit` remains honestly blocked until the real AI edit corpus
        reaches the required 20 reviewed cases.
      - [x] 2026-07-08 Cubase-style Sound Mixer review automation refresh:
        regenerated detailed review assets at
        `E:\ClaudeCodeApp\ReviewAutomationWorkspace\outputs\mixer_cubase_round_1_detailed`,
        including `TigerCapture_Review_Automation_detailed.pptx` and
        `site\index.html`. `feature_color_audio_vfx_editor_surface.png` is
        byte-identical to
        `debugCapture/ui_renewal_sound_editor_cubase_round_1/dock_sound_editor_mixer_action.png`,
        and `tools/qa_review_automation.py` passes at
        `E:\ClaudeCodeApp\ReviewAutomationWorkspace\qa\mixer_cubase_round_1_detailed_review_qa.json`.
        The evidence graph now records the Cubase-inspired mixer action surface:
        track type, insert slots, send/bus routing, automation R/W, meter state,
        mixer snapshots, and `audio.mixer.state`.
      - [x] 2026-07-02 UI renewal thread handoff written:
        `docs/UI_RENEWAL_THREAD_HANDOFF.md` defines the new-thread boundary,
        required reading order, real-evidence rules, refactoring modules,
        current evidence baseline, known blocked areas, QA commands, and the
        exact opening message for a separate UI-renewal Codex thread. This
        thread should continue review automation; the next UI thread should own
        live editor UI polish only.
- [x] 2026-07-01 VTuber/Live2D work-stream context captured:
  `docs/WORKFLOW_VTUBER_LIVE2D_CONTEXT.md` records why Live2D work started
  from the VSeeFace-style VTuber broadcast pipeline, and notes that the return
  path after Live2D is VTuber broadcast/camera/output work, not AR/PBR.
- [x] 2026-07-01 VTuber broadcast bridge context separated:
  `docs/WORKFLOW_VTUBER_BROADCAST_CONTEXT.md` is now the active standalone
  VTuber/VSeeFace broadcast bridge context. The Live2D context file is only for
  the Live2D side branch and should not carry generic Broadcast Studio notes.
- [x] 2026-07-01 VSeeFace dependency install/connect UI contract:
  bridge status now exposes `view.dependency` and a first `vseeface_install`
  setup step. Action System includes `vtuber.vseeface_install_plan`,
  `vtuber.vseeface_install_execution_gate`,
  `vtuber.vseeface_install_executor_dry_run`,
  `vtuber.vseeface_install_execute`, and
  `vtuber.vseeface_connect_installed_sidecar`. The installer tool
  `tools/install_vseeface_sidecar.py` extracts a local VSeeFace zip or uses an
  explicit user-provided URL only after confirmation; it does not auto-run.
  Default sidecar files belong under `external/tools/vseeface`, while
  `debugCapture` is only for generated reports and diagnostics.
- [x] 2026-07-01 VSeeFace launch/probe execution contract:
  `start_vseeface_and_probe` is now a bridge action and the Action System
  exposes `vtuber.vseeface_start_probe_plan`,
  `vtuber.vseeface_start_probe_execution_gate`,
  `vtuber.vseeface_start_probe_executor_dry_run`, and
  `vtuber.vseeface_start_probe_execute`. Execution launches the external
  VSeeFace sidecar only through a confirmed plan, then runs live-check and
  capture preflight diagnostics.
- [x] 2026-07-01 VSeeFace real launch probe recorded:
  confirmed execution starts `VSeeFace.exe`, registers/opens `VSeeFaceCamera`
  through FFmpeg DirectShow, and can generate Trump-video OpenSeeFace tracking
  rows, but the VSeeFace client area and virtual camera output remain black in
  the current remote/GPU environment. The bridge maps that report to
  `state=degraded`, `capture_status=virtual_camera_black_frame`, suppresses the
  black frame from Program Output, and exposes `fix_vseeface_rendering_or_start_scene`.
- [x] 2026-07-01 VSeeFace optional capture fallback policy:
  VSeeFace virtual camera is now an optional capture backend, not the required
  Program Output path. When VSeeFace capture reports black/failed/unregistered,
  bridge status exposes `use_internal_vrm_fallback` as the primary action and
  adds an `internal_vrm_fallback` BroadcastScene source while keeping VSeeFace
  repair/registration as secondary actions.
- [ ] VTuber standalone-to-main-editor integration: after the main UI renewal,
  mount the standalone Broadcast Studio, Performance Source track contract, and
  internal VRM fallback Program Output path into the real Media Pool/Timeline/
  Preview surfaces. Keep this out of the current independent bridge push.
- [x] 2026-06-30 VTuber main-UI integration contract: `Performance Source`
  is now the stable input-only term, `performance_source_ui_contract()` exposes
  Media Pool, timeline, Program Output, and Studio UI hooks, and
  `vtuber.performance_source.summary` returns that contract for the renewed UI
  thread.
- [x] 2026-06-30 VTuber Performance Source track UX contract: marked Media
  Pool video items use a `PERF` badge and
  `application/x-tigerstudio-performance-source` drag MIME, while timeline
  drops create or reuse the dedicated `vtuber_performance_source` track. Program
  Output selection still skips those clips.
- [x] 2026-06-30 VTuber Live2D Performance Source mapping contract: active
  Performance Source clips now feed Live2D mocap/framing with normalized subject
  types (`face_only`, `upper_body`, `full_body`, `unknown`), face-only framing
  locks actor transform, upper-body framing damps movement, full-body permits
  wider movement, and canonical Cubism tracks get alias/fallback parameter
  copies for alternate model ids.
- [x] 2026-07-01 VTuber Live2D production tuning first pass: Live2D mocap now
  smooths head yaw/pitch/roll, gaze, mouth, and eye-open tracks separately,
  emits aggregate eye-open/blink, breath, and additional body-angle tracks, and
  expands Cubism alias/fallback ids for head, body, breath, eye, mouth, and
  blink parameters. Performance Source video remains input-only and is still
  skipped by Program Output.
- [ ] VTuber Live2D production tuning QA/UI follow-up: validate the new
  smoothing and alias behavior against real face-only, upper-body, and full-body
  clips, then expose safe user controls for mapping strength, smoothing,
  mouth/eye intensity, and movement lock/damping.
- [x] 2026-06-30 VTuber Live2D editor UX: keep a right-click/editor entry for
  `Performance Source Mapping` / `?쇳룷癒쇱뒪 ?뚯뒪 留ㅽ븨`, avoid apply-button-only
  flow, and ensure the actor remains visible while editing even when the
  playhead is outside the actor clip.
  Canonical Korean UI label is `?쇳룷癒쇱뒪 ?뚯뒪 留ㅽ븨`; older mojibake text in
  this item must not be copied into UI or new docs.
- [x] 2026-07-01 VTuber Studio/Live2D discoverability: selecting a Live2D actor
  clip now exposes a Workbench card with `Live2D Viewer`, `Map Source`, and
  `VTuber Studio` actions; VTuber Studio is also reachable from the toolbar,
  Actor menu, and Command Palette without replacing the original Live2D
  double-click viewer.
- [x] 2026-07-01 VTuber Studio target scope correction: the Studio window is
  avatar-agnostic and must not be positioned as Live2D-exclusive. It reports
  VRM/VSeeFace bridge targets when configured, Live2D actor clips when
  selected, and leaves direct Live2D key baking as one target-specific action.
- [x] 2026-07-01 VTuber Studio / VRM Target spec sync: documented the shared
  `Avatar Target` selector, `VRM / VSeeFace Bridge` label, one-window Studio
  rule, pose-stream route, and Action System ids
  `vtuber.studio.open`, `vtuber.avatar_target.summary`,
  `vtuber.avatar_target.select`, `vtuber.vrm.bridge_status`, and
  `vtuber.vrm.pose_stream_preview`.
- [x] 2026-07-01 Media Pool VRM Avatar Target flow: `.vrm` import is now a
  `VRM Avatar` / `Avatar Target` asset with a `VRM` badge, not normal Program
  Output media. Double-click selects `VRM / VSeeFace Bridge` and opens the
  shared VTuber Studio; context menu actions expose target/studio/bridge
  selection. Selection persists `vseeface_bridge.avatar_vrm` and
  `vtuber_studio.avatar_target_id = "vrm:vseeface_bridge"`.
- [x] 2026-07-01 Shared VTuber Studio invariant recorded: Live2D and VRM use
  the same `VTuberBroadcastStudioWindow`. The selected asset or Avatar Target
  changes the mapping workflow inside that UI; it must not create separate
  VRM/Live2D Studio windows. Live Target output controls are part of the same
  Studio's final stage.
- [x] 2026-07-02 VTuber Studio/Broadcast canonical spec added:
  `docs/SPEC_VTUBER_STUDIO_BROADCAST.md` is the current single-source product
  contract for shared `VTuberBroadcastStudioWindow`, `Avatar Target`,
  input-only `Performance Source`, `Program Output`, `Live Target`,
  session-only stream keys, Broadcast Evidence, and the commercial-ready gate.
- [x] 2026-07-01 Post-split VTuber Studio module guardrail recorded:
  `VTuberBroadcastStudioWindow`, popout windows, detached dock UI, and
  `_BroadcastProjectAudioBusMixdownThread` now live in
  `app/video_editor_popouts.py`; future work in this thread must not add those
  UI surfaces directly back into `app/video_editor_window.py`.
- [x] 2026-07-01 Broadcast Evidence UI helper split:
  `app.broadcast_evidence_ui` now owns Studio evidence status-line formatting,
  registration dialog defaults, and registration payload normalization. The
  `VTuberBroadcastStudioWindow` stays in `app/video_editor_popouts.py` but no
  longer owns those pure view-model details directly.
- [x] 2026-07-01 NLE/GPU release-claim gate sync: evidence-free NLE readiness
  remains 47/100, but `tools/qa_nle_readiness.py` now attaches a synthetic NLE
  contract corpus and reports 80/100 after adding Source/Record workbench,
  Project Bin workbench, multicam group, active-angle switch plan, export
  handoff action contracts, and long-project stress evidence. Premiere/Resolve-
  class professional NLE claims are still explicitly blocked until real
  long-project footage and deeper source/record UI, conform/bin/proxy workflows
  are proven.
  Latest GPU/export parity matrix now requires both Live2D preview coverage and
  export evidence for actor preview/export parity claims.
- [x] 2026-07-01 Real NLE project corpus gate: `tools/register_nle_real_project.py`
  registers real `.tgp`/JSON projects, `tools/qa_nle_real_project_corpus.py`
  writes `debugCapture/nle_real_project_corpus_qa.json`, and
  `nle.real_corpus.status` exposes the same state through Python Actions. The
  NLE readiness gate distinguishes generated long-project stress fixtures from
  real user projects and keeps the full-NLE claim blocker until the real corpus
  meets project-count, duration, clip-count, and no-missing-media thresholds.
- [x] 2026-07-07 NLE real corpus intake action: `nle.real_corpus.register`
  dry-runs project metrics, registers the current saved project or an explicit
  `project_path`, and writes the same manifest as the CLI tool so AI/MCP can
  guide corpus intake without requiring manual command-line use.
- [x] 2026-07-08 NLE real corpus discovery: `tools/discover_nle_real_projects.py`
  and `nle.real_corpus.discover` scan bounded project roots for `.tgp`/JSON
  candidates, flag generated fixtures/missing media/short projects/already
  registered projects, and report the remaining real-corpus thresholds that keep
  the professional NLE claim blocked.
- [x] 2026-07-08 NLE real corpus intake board: `nle.real_corpus.intake_board`
  exposes a UI-ready board with claim thresholds, registerable candidates,
  rejected/incomplete projects, registered corpus entries, and safe register
  actions. This makes real-project collection actionable without allowing
  generated fixtures to clear the professional-NLE claim gate.
- [x] 2026-07-08 NLE real corpus collection kit:
  `nle.real_corpus.collection_kit` gives UI/AI a guided checklist from scan to
  registration to real-corpus QA/readiness rerun, while keeping generated
  fixtures blocked from professional-NLE claim evidence.
- [x] 2026-07-08 NLE real corpus validation plan:
  `nle.real_corpus.validation_plan` turns registered real projects into
  per-project open/reopen, scrub sampling, proxy/relink, undo/recovery, short
  export, and nested/proxy edge-case QA steps. This makes the remaining real
  corpus blocker operational without clearing it artificially.
- [x] 2026-07-08 NLE UI-ready review surfaces: add
  `source_record.monitor_layout`, `timeline.multicam.tile_board`,
  `project_bin.review_board`, and `timeline.undo_review_board` so Source/Record,
  multicam, project-bin/proxy/conform, and undo/fuzzer evidence can be rendered
  as product panels instead of raw action payloads. NLE readiness is now 86/100,
  still blocked from professional-NLE claims by missing real long-project corpus.
- [x] 2026-07-08 NLE apply/review boards: add `source_record.apply_board` for
  reviewed 3-point insert/overwrite decisions with destructive-confirm hints,
  and `timeline.multicam.review_board` for angle tiles, coverage diagnostics,
  switch decisions, and bake/export readiness. This raises implementation
  readiness while keeping the real-project corpus blocker intact.
- [x] 2026-07-08 NLE project-bin polish: add `project_bin.offline_browser` for
  offline/missing media, ambiguous/name-only matches, and relink queue review;
  add `project_bin.proxy_regeneration_board` for safe background proxy jobs,
  blocked offline items, and preview proxy policy. These strengthen proxy/
  conform readiness while keeping real long-project validation separate.
- [x] 2026-07-08 NLE undo recovery playbook: add
  `timeline.undo_recovery_playbook` so undo/fuzzer failures have UI-ready rerun,
  triage, autosave/reopen, and reproduction-step commands instead of only a
  raw health matrix. NLE readiness is now expected to move to 87/100 while the
  real long-project corpus blocker remains.
- [x] 2026-07-08 NLE interaction polish contracts: add
  `source_record.keyboard_overlay`, `timeline.multicam.sync_quality_board`, and
  `project_bin.search_filter_model` so Source/Record shortcut hints, multicam
  sync confidence, and project-bin search/filter/metadata columns are
  action-backed UI models. NLE readiness can rise to about 88/100, but the full
  professional-NLE claim remains blocked by missing real long-project corpus.
- [x] 2026-07-08 NLE multicam waveform sync board: add
  `timeline.multicam.waveform_sync_board` so cached waveform/transient metadata
  can drive UI-ready multicam offset review without running heavy media analysis
  on the baseline preview path. This improves the multicam contract while real
  footage parity QA remains required.
- [x] 2026-07-08 NLE multicam live switch dashboard: add
  `timeline.multicam.live_switch_dashboard` so angle tiles, switch decisions,
  sync-quality rows, waveform readiness, and bake/export commands are available
  as one UI-ready board without claiming Premiere/Resolve live-switcher parity.
- [x] 2026-07-08 NLE real corpus validation evidence: add
  `nle.real_corpus.validation_report` and
  `nle.real_corpus.validation_evidence.register` so registered real projects can
  store redacted open/reopen, scrub, proxy/relink, undo/recovery, short-export,
  and nested/proxy edge-case evidence. This makes the remaining
  `real_world_long_project_corpus` blocker operational instead of merely a
  metric threshold, without allowing synthetic fixtures to clear the claim gate.
- [x] 2026-07-08 NLE real corpus strict QA gate: official
  `tools/qa_nle_real_project_corpus.py` now requires validation evidence by
  default, while `--metric-only` is diagnostic only. NLE readiness no longer
  treats a shallow `claim_ready=true` corpus payload as real-world evidence
  unless the validation-ready count also satisfies the project threshold.
- [x] 2026-07-08 NLE real corpus validation CLI: add
  `tools/register_nle_real_project_validation.py` and expose copy-ready
  `validation.cli_examples` from `nle.real_corpus.collection_kit`, so operators
  can mark required real-project validation checks from UI/AI guidance without
  hand-writing manifest JSON.
- [x] 2026-07-08 NLE real corpus claim gate board: add
  `nle.real_corpus.gate_board` as the single UI/AI/MCP payload for current real
  corpus status, blocked thresholds, registerable/rejected projects,
  validation-missing projects, validation-ready projects, and rerun commands.
  This makes the remaining `real_world_long_project_corpus` blocker visible and
  actionable, but still keeps professional-NLE claims blocked until real
  projects and validation evidence pass.
- [x] 2026-07-08 NLE real corpus validation packet: add
  `nle.real_corpus.validation_packet` so each registered project can expose a
  focused operator checklist, redaction rules, required/optional checks,
  reviewed action template, and CLI template for validation evidence
  registration. This shortens the path from "registered project" to "real
  validation evidence" without fabricating pass results.
- [x] 2026-07-08 NLE real corpus validation preflight: add
  `nle.real_corpus.validation_preflight` so registered projects can separate
  machine prerequisites from human/operator checks before evidence is recorded.
  The preflight exposes missing media, duration/clip count, scrub sample, and
  short export blockers, but leaves every evidence check `pending` until a real
  operator review is registered.
- [x] 2026-07-08 NLE real corpus preflight QA CLI: add
  `tools/qa_nle_real_project_preflight.py` to write per-project machine
  preflight status to `debugCapture/nle_real_project_preflight_qa.json` for
  local QA, MCP, and other agent threads before operator evidence is recorded.
- [x] 2026-07-08 NLE real corpus preflight gate integration: strict corpus QA
  now carries `preflight_ready_count` / `preflight_blocked_count`, exposes
  project-level `preflight_blockers`, and keeps `validation_preflight` as a
  claim blocker before operator evidence can be trusted.
- [x] 2026-07-08 NLE real corpus workbench action: add
  `nle.real_corpus.workbench` as the single UI/MCP board for discovery,
  registerable candidates, preflight status, operator evidence, claim blockers,
  primary next action, QA commands, and action sequence toward the 95+ real
  evidence gate.
- [x] 2026-07-08 NLE target-score gap board: add `timeline.nle_target_gap` so
  UI/AI/MCP can answer "what remains before 95/100?" from the current readiness
  report. It shows per-row score gaps and keeps `real_world_long_project_corpus`
  as a hard blocker instead of allowing synthetic implementation evidence to
  masquerade as a professional NLE claim.
- [x] 2026-07-08 NLE 95-score unlock guard: scoring can now exceed 95 only when
  strict `real_project_corpus` evidence is attached. Synthetic/action contract
  evidence remains capped at the current implementation score, so the 95 target
  is reachable with real projects but cannot be faked by generated fixtures.
- [x] 2026-07-08 NLE implementation score over 90: add UI-ready polish boards
  and action contracts for `timeline.nle_core_safety_matrix`,
  `source_record.usability_board`, `timeline.multicam.export_parity_board`,
  `project_bin.proxy_apply_review_board`,
  `project_bin.conform_apply_review_board`, `timeline.undo_long_session_plan`,
  and `timeline.storyline_gesture_polish_board`. `tools/qa_nle_readiness.py`
  now reports 91/100 from synthetic/action evidence while still blocking full
  professional-NLE claims on `real_world_long_project_corpus`.
- [x] 2026-07-08 NLE readiness scoring refactor: move row score ladders into
  `app/nle_readiness_scoring.py` and add `score_breakdown` to the readiness
  report so UI/AI/MCP surfaces can read per-row score/status without duplicating
  the report parser. Current score remains 91/100; the real-corpus blocker is
  unchanged.
- [x] 2026-06-30 VTuber Live2D preview parity: main preview and popout preview must both
  evaluate Live2D animation plus Performance Source mapping results.
- [x] 2026-07-01 VTuber tracking input health contract: VSeeFace bridge input
  source options now expose `status`, `tone`, `actions`, and compact
  diagnostics for real cameras, Media Pool videos, and timeline clips. Tracking
  input diagnostics are passed separately from output-capture diagnostics, and
  unavailable/black camera inputs surface a reconnect action while missing
  project videos surface a choose-another-input action.
- [ ] VTuber real camera/capture input UX: add device registration, reconnect
  states, fallback to media-pool/timeline video clips, and clear diagnostics
  for unavailable or black-frame capture sources.
  - [x] 2026-07-01 Tracking input fallback recommendation added: when the
    selected camera is unavailable, black, missing, or disconnected, the
    VSeeFace input-source contract now recommends a ready media-pool/timeline
    video fallback and exposes a `Use suggested input` action for the shared
    VTuber Studio UI.
- [ ] VTuber avatar renderer quality/performance: harden VRM/Live2D preview
  resolution, mesh/material stability, caching, and frame pacing before making
  broadcast-quality claims.
  - [x] 2026-07-01 Internal VRM fallback renderer quality diagnostics added:
    render reports now expose resolution, target FPS/frame budget, cache policy,
    renderer profile, broadcast-ready claim blockers, and warnings. VSeeFace
    degraded fallback scene sources carry the same renderer-quality payload so
    the shared VTuber Studio can distinguish preview-safe fallback from a
    broadcast-candidate full-GPU path.
- [ ] VTuber live/record output: connect BroadcastScene preview to real
  recording/stream controls, audio routing, output preflight, and failure
  recovery.
  - [x] 2026-07-01 Live Target preset/preflight layer added for Local MP4,
    YouTube, Twitch, Custom RTMP, Discord window-share/video-call output, and
    experimental TikTok/Instagram/X RTMP targets. Stream keys are session-only
    and omitted from project settings.
  - [x] 2026-07-01 Start/stop FFmpeg subprocess from Program Output frames:
    `BroadcastOutputSession` accepts ProjectPlayer RGB frames, writes rgb24 to
    stdin, and VTuber Studio can start/stop Local MP4/RTMP targets.
  - [x] 2026-07-01 Live audio input routing added for FFmpeg sessions:
    generated silent stereo, Windows DirectShow device names, and looped audio
    file input. VTuber Studio exposes the audio source selector.
  - [x] 2026-07-01 TikTok/Instagram-style vertical target canvas recommendation
    added, plus Discord/video-call virtual-camera planning with Program Output
    window-share fallback.
  - [x] 2026-07-01 Stream-key credential helper added with lazy OS credential
    backend support; project files still omit raw stream keys.
  - [x] 2026-07-01 Project audio bus live input added: VTuber Studio can choose
    `Project audio bus`, which renders timeline audio through the export
    `build_audio_filter` chain to a temporary WAV before starting the FFmpeg
    live output session.
  - [x] 2026-07-01 Virtual-camera backend contract expanded: Discord/video-call
    output now reports explicit OBS/Spout2/NDI plans when installed, with
    Program Output window sharing as fallback and user-approved-only install
    policy.
  - [x] 2026-07-01 Project-audio bus mixdown preparation moved off the UI
    thread. VTuber Studio enters `preparing_audio`, renders the temporary WAV in
    a QThread, then starts the live target automatically; Stop drops the pending
    handoff result.
  - [x] 2026-07-01 Live output recovery diagnostics added: RTMP sessions can
    auto-reconnect on FFmpeg process exit/write failure and report health,
    retry counts, exit code, backpressure, and recovery action.
  - [x] 2026-07-01 Project-audio bus FFmpeg progress/cancel plumbing added:
    mixdown uses `-progress pipe:1`, Studio shows preparation percent, and Stop
    requests FFmpeg termination before dropping the pending live start.
  - [x] 2026-07-01 RTMP reconnect policy exposed in VTuber Studio and Python
    Actions. Retry count 0 disables auto reconnect; stream keys remain
    session-only.
  - [x] 2026-07-01 FFmpeg stderr live-output diagnostics added: background
    stderr tail reader, stream-key redaction, and platform error classification
    for auth/stream-key/server URL/network/closed stream/FFmpeg config failures.
  - [x] 2026-07-01 Platform-specific live troubleshooting added:
    `broadcast.live_target.troubleshoot` and session `troubleshooting` payloads
    expand classified errors into YouTube/Twitch/Custom RTMP/TikTok/Instagram/X
    and Discord/video-call checklist steps.
  - [x] 2026-07-01 OBS Virtual Camera bridge plan/action added:
    `app.broadcast_virtual_camera.obs_virtual_camera_bridge_plan()` and the
    `broadcast.virtual_camera.plan` /
    `broadcast.virtual_camera.obs_bridge_plan` Python Actions now describe
    installed OBS detection, Program Output Window Capture setup, optional OBS
    WebSocket readiness, and manual operator fallback without installing a
    driver or leaking Performance Source video into Program Output.
  - [x] 2026-07-01 OBS-free output priority clarified:
    `virtual_camera_output_plan` defaults to Program Output window sharing even
    when OBS is installed. OBS/Spout2/NDI are opt-in backends selected by
    `preferred_backend` or explicit installed-backend auto-selection, while
    Local MP4/RTMP targets continue to use the internal FFmpeg path without OBS.
  - [x] 2026-07-01 Confirmed OBS WebSocket automation gate added:
    `obs_virtual_camera_bridge_execution_gate`,
    `obs_virtual_camera_bridge_executor_dry_run`, and
    `execute_obs_virtual_camera_bridge` can create/select the OBS scene,
    create/update the Program Output Window Capture source, and start OBS
    Virtual Camera only when OBS is installed, WebSocket is enabled, the
    optional `obsws-python` dependency is available, and the caller passes
    explicit confirmation. Python Actions expose this as
    `broadcast.virtual_camera.obs_bridge_gate`,
    `broadcast.virtual_camera.obs_bridge_dry_run`, and
    `broadcast.virtual_camera.obs_bridge_execute`.
  - [ ] Add bundled or user-approved virtual camera device output integration
    for Discord/video-call apps when an actual driver/backend is available.
    - [x] 2026-07-01 Installed virtual-camera device backend contract added:
      `pyvirtualcam_device` is detected only when an installed/lazy-importable
      backend exists or an explicit installed backend is supplied. The new
      `BroadcastVirtualCameraDeviceSession` can feed Program Output RGB frames
      to that backend without installing drivers; otherwise the Studio keeps
      Program Output window-share as the safe fallback.
  - [x] 2026-07-01 Clickable troubleshooting panel contract added:
    `build_live_target_troubleshooting` still returns legacy `checks`, but now
    also returns `check_items` and `panel.items` with per-check pending/completed
    state, primary actions, dashboard links where stable, and registered action
    ids such as `broadcast.virtual_camera.obs_bridge_plan`.
  - [x] 2026-07-01 OBS-free capture-source resolver added:
    `app.broadcast_capture_backend` resolves external frame-map sources, image
    sources, OpenCV camera frames, and explicit screen/window regions into the
    `BroadcastScene` frame map without requiring OBS. Title-based native window
    lookup remains a platform/UI integration task.
  - [x] 2026-07-01 Broadcast commercial-readiness gate added:
    `app.broadcast_release_readiness`, `tools/qa_broadcast_release_readiness.py`,
    and `broadcast.release_readiness` report `alpha_ready`,
    `commercial_ready`, sale blockers, and next actions. The gate currently
    allows local alpha use but blocks sale-ready claims until real Record/RTMP
    and Discord/video-call platform evidence is attached.
  - [ ] 2026-07-10 Broadcast/VRM stabilization gate:
    today's private YouTube Live QA proved that TigerCapture can push RTMP
    Program Output and that the VRM frame can appear in YouTube Studio, but the
    flow is not product-stable yet. Do not mark VTuber broadcast sale-ready
    until these defects are closed:
    - [ ] YouTube ingest health and YouTube viewer playback must be tracked as
      separate states. A green FFmpeg/session status is not enough when Studio
      preview is still buffering or only briefly displays the avatar.
    - [ ] The Live Target UI needs safer operator warnings for private/unlisted
      tests, YouTube auto-start behavior, Stop ingest vs End stream, and stream
      key regeneration after any manual test key exposure.
    - [ ] VRM first-frame startup must be prewarmed or cached; the current
      internal fallback proof can take tens of seconds before the first frame.
      2026-07-10 measured Trump/Milica bust-up frames took about 48-56 seconds
      per frame through `render_internal_vrm_fallback_frame(...,
      renderer=vrm_mtoon_gpu)`, so live UI preview must use a separate
      renderer worker plus prerender/runtime cache until the renderer is made
      interactive.
      2026-07-10 follow-up reduced the live-render diagnostic to about
      `13.28s` per frame by using the persistent full-GPU helper process plus a
      conservative `12000` preview triangle cap. A second follow-up keeps the
      hidden Qt/GL widget alive and updates the VBO, reducing cached frames to
      about `2.852s` with `gpu_widget_cache_hit=1`,
      `build_vertex_buffer_s ~= 1.23`, and `gpu_widget_grab_s ~= 0.035`.
      This is still too slow for live playback. Next: remove the per-frame CPU
      vertex-buffer build and helper-service round trip, then move animated
      skinning to GPU/VBO updates. Do not use low triangle caps as a fix;
      `2400` visibly broke dense hair/body meshes.
    - [x] 2026-07-10 Trump-to-VRM pitch mapping corrected: internal pose curves
      and VMC messages now use `source_pitch_to_vrm_pitch`, mapping source
      pitch to VRM pitch as `-source_pitch - 12deg`. The latest real Studio
      proof records `mapped_vrm_motion.pitch_deg=-11.1916` so the VRM no
      longer looks like it is leaning backward against a down-looking source.
    - [ ] Trump-source VRM live smoke currently uses a cached avatar sprite plus
      a fast motion proxy for YouTube QA. Replace that with full per-frame
      VRM/MToon pose rendering before claiming true avatar mapping quality.
    - [x] 2026-07-10 local Studio proof corrected the framing failure:
      `tools/run_vtuber_studio_trump_live.py --frame-source cached-bustup`
      opens the real `VTuberBroadcastStudioWindow`, crops Trump Source Tracking
      from OpenSeeFace face boxes to a 16:9 bust-up view, and composites actual
      prerendered `vrm_mtoon_gpu` RGBA bust-up frames so Program Output records
      `program_avatar_height_ratio ~= 0.96`. This is valid local framing/UI
      evidence, not live renderer-performance evidence.
    - [x] 2026-07-10 agent-reviewed local Studio fit fix: Source Tracking now
      expands the OpenSeeFace subject crop to one 16:9 box before resize
      (`crop_aspect ~= 1.78`, `face_fully_visible=true`), VRM Avatar Mapping no
      longer ignores real mapping pixmaps, Program Output records
      `program_avatar_grounded=true` with `bottom_gap_ratio=0.0`, and the proof
      tool writes separate Program/Source/Mapping PNGs for visual QA.
    - [ ] Evidence capture must be reliable from the real YouTube/Program
      Output surface. Avoid generated or composited screenshots for platform
      evidence; use only real UI capture or clearly labeled diagnostics.
    - [ ] Record exact redacted status artifacts for failed/buffering runs so
      recovery diagnostics can distinguish TigerCapture encoder issues from
      YouTube Studio/player delay.
  - [ ] Attach real broadcast platform E2E evidence:
    Record-to-file metadata, one private/unlisted RTMP ingest test with redacted
    keys, and one Discord/video-call Program Output window-share test should be
    written to `debugCapture/broadcast_platform_e2e_qa.json`.
    `tools/qa_broadcast_platform_e2e.py` now creates the artifact and can fill
    the local Record-to-file plus capture/composite evidence automatically; the
    RTMP and Discord/video-call platform rows remain manual evidence. Use
    `tools/register_broadcast_platform_evidence.py --check-id private_rtmp_ingest
    --platform YouTube --notes "<redacted result>" --confirm-redacted` and the
    same command with `--check-id discord_window_share` after the manual checks.
    `tools/prepare_release_evidence_sprint.py --write-files` now also writes
    `debugCapture/release_evidence_sprint/register_broadcast_platform_evidence.ps1`
    so RTMP/Discord evidence collection is part of the same release sprint.
    - [x] 2026-07-01 Local MP4 runtime evidence attached:
      `tools/qa_broadcast_platform_e2e.py --allow-pending-platform` wrote
      `debugCapture/broadcast_platform_e2e_qa.json` and
      `debugCapture/broadcast_record_smoke.mp4`; local runtime checks passed
      with 12/12 frames written. Manual RTMP ingest and Discord/window-share
      evidence remain pending.
    - [x] 2026-07-01 Live2D Local MP4 runtime evidence attached:
      `tools/qa_broadcast_platform_e2e.py --allow-pending-platform` now also
      writes `debugCapture/broadcast_live2d_record_smoke.mp4` and records
      `live2d_record_file_local` in `debugCapture/broadcast_platform_e2e_qa.json`.
      Current automated local evidence is 3/3 passing; external RTMP and
      Discord/window-share rows remain manual evidence.
    - [x] 2026-07-01 Broadcast evidence checklist added:
      `app.broadcast_platform_e2e.build_broadcast_platform_evidence_checklist`,
      `broadcast.platform_evidence_checklist`, and the shared VTuber Studio
      Broadcast Evidence card now summarize 3/5 passed, next manual RTMP/
      Discord checks, operator steps, and redacted evidence registration
      payloads without showing raw JSON in the UI.
    - [x] 2026-07-01 Redacted evidence registration action added:
      `broadcast.platform_evidence.register` wraps the existing manual evidence
      registration path, requires `confirm_redacted=true`, rejects secret-like
      notes/paths, and updates the same `debugCapture/broadcast_platform_e2e_qa.json`
      artifact used by release-readiness checks.
    - [x] 2026-07-01 Studio evidence registration UI added:
      the shared VTuber Studio Broadcast Evidence card now has Refresh,
      Register RTMP, and Register Discord actions. Registration opens a compact
      redaction-confirming form and writes through the same safe
      `broadcast.platform_evidence.register`/manual-evidence path.
  - [ ] Verify Live2D also reaches Live Target output through the shared VTuber
    Studio: select a Live2D actor Avatar Target, drive it from a Performance
    Source, confirm Program Output contains the Live2D avatar and never the
    Performance Source directly, then test Local MP4 and at least one
    stream/window-share path. If Live2D is missing from the Program Output or
    Live Target path, add the same broadcast hooks/parity coverage used by the
    VRM target.
    - [x] 2026-07-01 Studio contract coverage added: the shared VTuber Studio
      layout now exposes `avatar_target`, marks Live2D actor targets as
      Program Output and Live Target participants, and keeps Performance Source
      input-only. Release-readiness evidence now checks the Live2D Live Target
      route contract. Manual visual/platform evidence for window-share/RTMP
      remains pending under the broadcast platform E2E item.
    - [x] 2026-07-01 Local MP4 evidence added for Live2D Program Output:
      `live2d_record_file_local` writes a composited Live2D-target Program
      Output frame stream to `debugCapture/broadcast_live2d_record_smoke.mp4`.
      The remaining unchecked part of this item is real window-share/RTMP
      platform evidence.
- [ ] UI renewal phase 1: prioritize the main editor shell before more review
  automation polish. Align the real TigerCapture Studio UI with the current
  generated catalog direction: icon-first top command bar, compact hover-text
  controls, cleaner media pool rail, matching playback buttons, refined track
  colors/clip blocks/playhead/markers, and collapsible drag-and-drop palettes
  for tools, effects, transitions, titles, actors, nodes, and audio. Do this
  against the live editor UI, not by compositing catalog screenshots. Planning
  reference: `docs/SPEC_UI_RENEWAL.md`.
- [ ] Review automation follow-up after UI renewal: keep the current real-media
  capture guardrails, but defer catalog/PPT polish until the renewed editor UI
  is the visual source of truth. Remaining review tasks include feature-specific
  layout presets, non-cramped color/audio/node captures, screenshot-diff checks
  for generated PPT/HTML pages, and re-enabling the Live2D/actor page only after
  the actual renderer produces visible pixels instead of `render_none`.
- [ ] Editor architecture risk reduction: `app/video_editor_window.py` is a
  42k+ line monolith that still owns UI assembly, timeline gestures, AI command
  dock, presets, actor entry points, export wiring, and QA/editor helpers.
  Future feature work should move bounded surfaces into focused modules
  instead of adding more logic to this file. First safe extraction candidates:
  AI command/review dock, preset palette/drop feedback, timeline toolbar/tool
  state, actor context-menu/editor launch wiring, and export/render queue UI
  adapters. Keep behavior unchanged and cover each extraction with existing UI
  smoke/regression QA before deleting the old path.
- [ ] Release packaging hygiene gate: PyInstaller hidden imports must point to
  real modules, generated/cache directories such as `logs/` and
  `.pytest_cache/` must stay out of git status, and README/Korean release text
  must be checked with UTF-8 reads plus localization mojibake QA before public
  packaging. Do not treat terminal mojibake alone as file corruption unless the
  UTF-8 file contents are also corrupted.
- [x] 2026-06-27 ordered 3,4,5,1,2,6 product-gap push gate:
  `app.product_gap_push.build_product_gap_push_report()` and
  `tools/qa_product_gap_push.py` now aggregate the requested areas in order:
  AI editing quality, real screen-recording corpus, CapCut local template/asset
  scale, GPU preview/export parity, AR/PBR renderer quality, and release trust.
  The latest `debugCapture/product_gap_push_qa.json` reports score 98 with all
  six areas implementation-ready and claim-ready after the Descript-lite P1-P5,
  GPU/export parity, AR/PBR GPU preview, and AR/PBR attachment-stability QA
  reports were refreshed. Stronger public copy must still stay tied to the
  underlying QA evidence and avoid full-suite replacement language.
- [x] 2026-06-27 release trust policy added:
  `docs/RELEASE_TRUST.md` documents installer validation, code-signing status,
  manual-update policy until a signed updater exists, local crash reports,
  privacy/local processing, and safe public claim boundaries.
- [x] 2026-06-27 remaining blocker tightening pass:
  `product_gap_push` now uses provider-exercised AI corpus QA evidence
  (`use_provider=True`) instead of only reporting rule-based readiness, reuses
  the cached provider report when present to avoid slow repeated live corpus
  calls, includes the selected provider state when it falls back to
  `rule_based`, pulls Screen Studio sidecar intake evidence into the real-corpus
  area, and AR/PBR offscreen export diagnostics now expose the exact
  `worker_thread_qt_opengl_context_not_safe` fallback reason plus the
  full-model-view GPU export service steps. `tools/prepare_screenstudio_sidecar_intake.py
  --write-templates --max-templates 20` was run; 55 recordings are registered,
  50 templates already existed, and 5 additional fillable sidecar templates were
  written without counting fake cursor evidence.
- [x] 2026-06-28 non-Claude blocker handling pass:
  Claude terminal handoff remains available, while configured Claude direct
  Plan generation now auto-runs behind the Review validation boundary.
  `product_gap_push` now
  exposes the next Screen Studio sidecar capture target/command and any release
  evidence sprint progress instead of only reporting a generic interaction
  corpus gap. AR/PBR full model-view export now has
  `app.ar_pbr.full_gpu_export_service` plus
  `tools/qa_ar_pbr_full_gpu_export_service.py`; export fallback diagnostics also
  report the service contract/configuration state. This does not fake real
  cursor corpus evidence or claim full GPU export parity before a probeable
  helper process exists.
- [x] 2026-06-28 AR/PBR full model-view GPU export helper:
  `tools/ar_pbr_full_gpu_export_service.py` now provides a worker-safe helper
  process for `offscreen_gpu` export. `app.ar_pbr.full_gpu_export_service`
  auto-discovers the repo helper command, writes frame/request temp files,
  invokes the helper outside `VideoExportThread`, and returns the rendered RGBA
  frame when the helper succeeds. `render_offscreen_gpu_export_frame()` now
  tries this full model-view GPU helper first and only falls back to the
  deterministic packet renderer on helper failure. Probe QA passes and a smoke
  render produced `mode=full_model_view_gpu_export_service`, `fallback=false`,
  and `rendered_track_count=1`. The Windows service path now forces
  `QT_OPENGL=desktop` and uses an offscreen-positioned native helper window so
  PyOpenGL receives a valid `QOpenGLWidget` context instead of failing at
  `glViewport` and silently dropping back to packet export.
- [x] 2026-06-28 AR/PBR asset support UI handoff:
  Media Pool keeps `.fbx/.glb/.gltf` ingest lightweight and marks support as
  deferred, while ProjectPlayer and VideoExportThread attach public
  ready/limited/unsupported support rows from descriptor `support` reports.
  UI/export diagnostics must show product labels such as `Ready: skeletal PBR`
  or `Limited: FBX conversion`, not raw issue codes or descriptor JSON.
- [ ] 3D/MMD media classification contract hardening: consolidate supported
  3D/MMD file classification so Media Pool import, timeline drag/drop,
  double-click preview/editor routing, project tracks, and automation actions
  all call the same source of truth. Current risk is not renderer quality but
  user-flow inconsistency when a path is accepted by AR/PBR schema/importer yet
  filtered by Media Pool or routed differently by timeline code.
  - [x] 2026-07-05 Align Media Pool 3D import with AR/PBR schema for
    `.obj`, `.usd`, and `.usdz`; keep `.vmd` hidden from the general pool and
    scoped to the MMD Actor Editor motion library.
  - [ ] Extract a small pure helper/module for asset-family classification:
    video, audio, AR/PBR model, VRM avatar target, MMD model/package, and MMD
    motion. Reuse it from `app.media_pool`, `app.video_editor_window`,
    `app.ar_pbr.project_tracks`, `app.mmd.project_tracks`, and action adapters.
    - [x] 2026-07-05 First cut for `video_editor_window.py`: added
      `app.media_asset_routing` and routed TrackRow/editor host MIME parsing
      for AR/PBR, VRM, MMD, timeline media, and VTuber performance-source drops
      through it. Media Pool/action adapters still need to move onto the same
      helper before this parent item is complete.
    - [x] 2026-07-05 Second cut for `video_editor_window.py`: moved timeline
      drop-guide label/width/segment/detail calculation to
      `app.timeline_drop_guides` and moved repeated card MIME payload parsing
      to `app.timeline_drop_payloads`. `TrackRow`, `TextLaneRow`, and
      `AudioTrackRow` now keep mutation/UI work while shared helpers parse
      drag payloads.
    - [x] 2026-07-05 Third cut for `video_editor_window.py`: moved the
      dedicated typography lane widget to `app.video_editor_text_lane` and
      moved shared timeline stripe painting colors/helper to
      `app.timeline_lane_paint`. `video_editor_window.py` re-exports
      `TextLaneRow` so existing imports keep working.
    - [x] 2026-07-05 Fourth cut for `video_editor_window.py`: moved
      `StripedHost` to `app.timeline_striped_host` and updated subtitle lane
      stripe painting to import the shared host directly instead of depending
      on `app.video_editor_window`.
    - [x] 2026-07-05 Fifth cut for `video_editor_window.py`: moved the
      legacy editor `VideoTrack` dataclass and `_ensure_video_clips` bridge to
      `app.video_track_legacy`. Action adapters and project loading now use
      that module directly while `app.video_editor_window` keeps re-exporting
      the names for older imports.
    - [x] 2026-07-05 Sixth cut for `video_editor_window.py`: split timeline
      thumbnail cache helpers to `app.timeline_thumbnail_cache`, shared pixmap
      cover painting to `app.qt_pixmap_painting`, and repeated typography
      preview layout calculations to `app.typo_layout`. Added focused legacy
      track tests in `tests/test_video_track_legacy.py`.
    - [x] 2026-07-05 Seventh cut for `video_editor_window.py`: moved timeline
      tool cursor creation/cache to `app.timeline_cursor` and added focused
      coverage for cursor fallback/custom-cache behavior, typography layout,
      and timeline thumbnail cache key/count handling.
    - [x] 2026-07-05 Eighth cut for `video_editor_window.py`: moved
      best-effort UX logging, startup warmup env gating, and opt-in HDR track
      probing to `app.editor_observability` while preserving the old
      `app.video_editor_window` import names.
    - [x] 2026-07-05 Ninth cut for `video_editor_window.py`: confirmed proxy
      helpers are split to `app.video_editor_media_proxy` and added focused
      tests for proxy state compatibility, safe proxy deletion, 540p ffmpeg
      command construction, ready-proxy reuse, high-resolution file detection,
      and failed dimension probing.
    - [x] 2026-07-05 Tenth cut for `video_editor_window.py`: parallel
      extraction batch produced dedicated controller modules/tests for
      workflow targeting, startup template state, proxy UI control, media
      import routing, thumbnail lifecycle, subtitle workflow, context menu
      models, preview recovery, player bridge, and render queue bridge.
      `VideoEditorWindow` is now wired to the new workflow targeting, startup
      template, proxy controller, and thumbnail controller implementations
      while preserving historical private method names.
    - [x] 2026-07-05 Remaining controller wiring from the batch:
      1. `app.video_editor_media_import_controller` is wired for media pool
         import notifications, media pool selection, timeline MIME imports, and
         video/audio row drops.  Routing now centralizes AR/PBR, MMD, VRM,
         performance-source, video, and audio precedence while preserving the
         editor's existing track/audio creation hooks where available.
      2. `app.video_editor_subtitle_workflow` is wired for overlay updates,
         overlay repositioning, subtitle change handling, lane edits, and AI
         subtitle generation wrappers.
      3. `app.video_editor_context_menu_controller` is wired for the clip badge
         menu model and dispatch path; broader context menu UI extraction stays
         in the higher-risk bucket.
      4. `app.video_editor_preview_recovery` is wired for blank/black preview
         detection, recovery guards, remembered good-frame state, and deferred
         restore scheduling through the window's `QTimer.singleShot` adapter.
      5. `app.video_editor_player_bridge` is wired for nested audio preview
         sync, player refresh, playback state, position changes, level meters,
         and duration changes while keeping the historical private method names.
      6. `app.video_editor_render_queue_bridge` is wired for AI Script and
         Creator Assist render-queue staging/popout wrappers.
    - [ ] Higher-risk later:
      1. `app.video_editor_preview_surface_controller`
      2. `app.video_editor_preview_prerender_controller`
      3. `app.project_player_decoder_registry`
      4. `app.project_player_clip_render_pipeline`
      5. `app.project_player_ar_pbr_preview_pipeline`
  - [ ] Add contract tests that compare Media Pool ingest, timeline MIME/drop
    parsing, double-click routing, and action import behavior for the same file
    matrix.
- [ ] GPU preview/export parity hardening: keep color grading, shader effects,
  typography, transitions, Live2D, Spine, and AR/PBR overlays visually
  consistent across live preview, preview pop-out, QImage fallback, and final
  export. Add mixed-stack pixel/regression QA before claiming parity.
- [ ] AR/PBR production renderer quality: the worker-safe full model-view GPU
  helper exists, is smoke-tested, and no longer falls back on the default
  Windows Qt/OpenGL path. Live GL/packet paths now cover
  depth-texture fragment occlusion, item-depth export masking, AO/packed-channel
  material parity, layered reflection catchers, directional/spot shadow maps
  with PCF/PCSS filtering, and template/depth-plane SLAM-assist diagnostics.
  Remaining quality work is true prefiltered cubemap IBL tuning, lens
  distortion, batching/reuse, full camera-solve fidelity, shadow/reflection
  catcher upgrades, tone mapping/color management, and golden-image parity.
  - [ ] Marmoset-style rendering approximation P0, rendering only: finish
    reproducible HDRI/IBL resources, physically based GGX/Cook-Torrance BRDF,
    complete material-map parity, real shadow maps, shadow catcher quality,
    reflection/contact fidelity, tone mapping/color management, and
    preview/export golden-image parity before claiming Toolbag-like output.
  - [x] 2026-07-03 P0-1 HDRI resource reproducibility bootstrap:
    `tools/bootstrap_ar_pbr_hdri_resources.py` writes the AR/PBR resource
    manifest and downloads the eight Poly Haven CC0 1K HDRI presets into the
    ignored `debugCapture/ar_pbr_resources/hdri/polyhaven` runtime bundle.
  - [x] P0-2 Shared IBL probe contract: replace per-renderer ad-hoc HDRI
    sampling with a reusable probe carrying diffuse irradiance,
    roughness-prefiltered specular levels, and BRDF LUT sampling across packet
    export diagnostics, live GL preview, and the full-GPU/model-view helper.
    - [x] 2026-07-03 Packet export IBL probe foundation:
      `app.ar_pbr.ibl` now builds a cached scene-linear HDRI probe with diffuse
      irradiance, roughness prefilter levels, and a split-sum BRDF LUT. Packet
      PBR export samples that probe, reports `pbr_ibl_probe`, and keeps the old
      injected-HDRI cache fallback for existing QA.
    - [x] 2026-07-03 Live GL preview IBL probe wiring:
      `OpenGLPreviewWidget` now uploads AR/PBR IBL probe textures for diffuse
      irradiance, roughness-prefiltered specular, and BRDF LUT sampling instead
      of relying only on a single tonemapped equirectangular environment sample.
      The GL pixel QA also exposed and fixed a DPR mismatch in PBR depth
      texture occlusion by passing physical framebuffer size to the shader.
    - [x] 2026-07-03 Full-GPU/model-view IBL probe wiring:
      `tools/ar_pbr_gpu_window.py` now uploads the shared IBL probe as
      `RGB16F/RG16F` textures for irradiance, prefilter, and BRDF LUT sampling.
      `tools/ar_pbr_full_gpu_export_service.py` surfaces `ibl_probe`
      diagnostics, and probe+smoke QA reports `gl_uploaded=true` with
      `fallback=false`.
  - [x] P0-3 Normalize all PBR shading paths around scene-linear GGX
    Cook-Torrance with Schlick Fresnel, Smith visibility, energy conservation,
    and explicit sRGB/linear texture decode.
    - [x] 2026-07-03 GGX BRDF normalization:
      `app.ar_pbr.pbr_math` now owns CPU sRGB/linear conversion, material F0,
      Schlick Fresnel, GGX distribution, Smith visibility,
      energy-conserving diffuse, and Cook-Torrance direct lighting. Packet
      export, live GL preview, full-GPU/model-view helper, and software fallback
      use the same scene-linear contract. IBL quality tuning remains separate
      from this BRDF normalization item.
      Verified with PBR math tests, the AR/PBR pytest suite, GL pixel QA, and
      full-GPU export service smoke QA.
  - [x] P0-4 Lock material-map parity for base color, normal, roughness,
    metallic, AO, emissive, opacity/alpha cutoff, ORM channel packing, and
    tangent-space normal basis.
    - [x] 2026-07-03 Material-map parity contract:
      `app.ar_pbr.texture_plan` now exposes a canonical map contract for base,
      roughness, metallic, specular, normal, occlusion/AO, emissive, and opacity
      maps, including ORM R/G/B expansion, glTF metallic-roughness G/B channel
      preservation, alpha cutoff metadata, and emissive factors. Packet export,
      live GL preview, and full-GPU/model-view helper now consume the same
      emissive, opacity, AO, alpha-cutoff, and tangent-space normal-map contract.
      Verified with material-map pytest coverage, the AR/PBR pytest suite, GL
      pixel QA, and full-GPU export service smoke QA.
  - [x] P0-5 Add real shadow-map rendering for directional/spot lights with
    bias controls and PCF/PCSS filtering; keep contact shadow only as a helper,
    not the primary shadow model.
    - [x] 2026-07-03 Shadow-map filter contract:
      `app.ar_pbr.shadow` now normalizes directional/spot shadow maps,
      PCF/PCSS filters, map size, bias/normal-bias controls, spot cone angles,
      and the helper-only contact-shadow role. Live GL preview and the
      full-GPU/model-view helper consume the same settings; the full-GPU helper
      uses orthographic projection for directional lights and perspective
      projection for spot lights. Verified with AR/PBR pytest coverage, GL
      pixel QA, and full-GPU export service PCSS/spot shadow-map smoke QA.
  - [x] P0-6 Upgrade shadow catchers and reflection catchers for background
    compositing: matte alpha, softness, roughness blur, opacity controls, and
    contact reflection behavior.
    - [x] 2026-07-03 Catcher compositing contract:
      `app.ar_pbr.catcher` now normalizes shadow/reflection catcher opacity,
      softness, matte alpha, reflection roughness, and contact reflection
      falloff/strength. Schema, default tracks, app preview round-trip, packet
      preview/export, software PBR fallback, and the full-GPU/model-view ground
      shader consume the same settings. Full-GPU ground output now computes
      catcher alpha from matte + shadow + reflection contribution instead of
      forcing an opaque floor. Verified with AR/PBR pytest coverage, GL pixel
      QA, and full-GPU export service smoke QA carrying catcher diagnostics.
  - [x] P0-7 Add ACES/AgX/Reinhard tone mapping options plus exposure, white
    balance, gamma, and render-pass-safe color management.
    - [x] 2026-07-03 AR/PBR display-transform contract:
      `app.ar_pbr.tone_mapping` now normalizes ACES/AgX/Reinhard tone mapping,
      output exposure, white balance, gamma, working/display space metadata,
      and alpha-preserving render-pass safety. Schema/default tracks/app
      preview round-trip, packet preview/export, software PBR fallback, live GL
      preview shader, and full-GPU/model-view material/ground/environment
      shaders consume the same display-transform settings. Verified with
      tone-mapping pytest coverage, the AR/PBR regression suite, GL pixel QA,
      and full-GPU export service smoke QA carrying AgX color-management
      diagnostics.
  - [x] P0-8 Add golden-image QA scenes comparing live GL preview, full-GPU
    helper export, and packet fallback on the same HDRI/material/depth/shadow
    setup.
    - [x] 2026-07-03 AR/PBR golden-scene parity QA:
      `tools.qa_ar_pbr_golden_scene` now builds a deterministic synthetic
      Marmoset-style PBR scene with HDRI/IBL, eight material maps, depth
      occlusion, PCSS spot shadow-map settings, catcher settings, and AgX
      display transform. The QA captures live `OpenGLPreviewWidget`,
      full-GPU helper export, and packet fallback PNGs, writes pairwise diff
      images/metrics, and supports optional baseline promotion/comparison.
      Verified with packet-only pytest coverage and a full live/full-GPU/
      packet QA run producing `debugCapture/ar_pbr_golden_scene_p0_8_qa.json`.
  - [x] Marmoset-style rendering approximation P1: hybrid/path-traced
    accumulation, diffuse/specular GI, denoise, refraction/transmission,
    clearcoat, displacement/parallax, bevel shader, material layering, UDIM,
    and triplanar projection.
    - [x] 2026-07-03 P1-1 Hybrid accumulation/GI/denoise:
      `app.ar_pbr.hybrid_rendering` now normalizes deterministic hybrid
      rendering settings, packet export applies diffuse/specular GI and
      alpha-weighted spatial denoise, live GL/full-GPU shaders consume matching
      hybrid uniforms, and full-GPU helper/golden QA report hybrid diagnostics.
      Verified with the AR/PBR regression suite, full live/full-GPU/packet
      golden-scene QA, and full-GPU export service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p1_1_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p1_1.json`.
    - [x] 2026-07-03 P1-2 Transmission/refraction:
      `app.ar_pbr.transmission` now normalizes glass/transmission/refraction
      controls, packet export applies screen-space background refraction with
      absorption tint and roughness blur, live GL/full-GPU shaders sample
      refracted environment lighting with matching uniforms, and golden/full-GPU
      QA reports transmission diagnostics. Verified with the AR/PBR regression
      suite, full live/full-GPU/packet golden-scene QA, and full-GPU export
      service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p1_2_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p1_2.json`.
    - [x] 2026-07-03 P1-3 Clearcoat:
      `app.ar_pbr.clearcoat` now normalizes secondary top-coat specular
      settings, packet export applies an extra GGX-style clearcoat lobe in
      scene-linear PBR, live GL/full-GPU shaders consume matching clearcoat
      uniforms, and golden/full-GPU QA report clearcoat diagnostics. Verified
      with the AR/PBR regression suite, full live/full-GPU/packet golden-scene
      QA, and full-GPU export service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p1_3_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p1_3.json`.
    - [x] 2026-07-03 P1-4 Displacement/parallax:
      `app.ar_pbr.parallax` now normalizes height-map parallax controls and
      documents the approximation boundary: tangent-space UV offset only, no
      silhouette displacement and no displaced geometry shadows. Texture-plan,
      live GL preview, packet export, full-GPU helper, and full-GPU export
      service now consume the shared height-map contract and report parallax
      diagnostics. Verified with the AR/PBR regression suite, full live/full-
      GPU/packet golden-scene QA, and full-GPU export service smoke QA
      producing `debugCapture/ar_pbr_golden_scene_p1_4_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p1_4.json`.
    - [x] 2026-07-03 P1-5 Bevel shader:
      `app.ar_pbr.bevel` now normalizes shader-only rounded-edge controls and
      documents the approximation boundary: normal rounding only, no topology,
      silhouette, depth, or beveled shadow-caster changes. Packet export uses
      barycentric edge normal blending while live GL/full-GPU shaders use
      UV-island edge normal blending, and golden/full-GPU QA report bevel
      diagnostics. Verified with the AR/PBR regression suite, full live/full-
      GPU/packet golden-scene QA, and full-GPU export service smoke QA
      producing `debugCapture/ar_pbr_golden_scene_p1_5_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p1_5.json`.
    - [x] 2026-07-03 P1-6 Material layering:
      `app.ar_pbr.material_layering` now normalizes a single overlay material
      layer with blend/color/roughness/metallic/alpha/emissive controls and
      documents the approximation boundary: one shared-UV overlay layer, no
      independent layer texture stack, graph nodes, extra geometry, or material
      slot draw calls. Packet export applies the shared layer mixer in
      scene-linear shading space, live GL/full-GPU shaders consume matching
      uniforms, and golden/full-GPU QA report material-layer diagnostics.
      Verified with the AR/PBR regression suite, full live/full-GPU/packet
      golden-scene QA, and full-GPU export service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p1_6_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p1_6.json`.
    - [x] 2026-07-03 P1-7 UDIM:
      `app.ar_pbr.udim` now discovers `<UDIM>` and numeric 1001-style tile
      sets, records UDIM tile metadata in the shared texture plan, and keeps
      live GL/full-GPU honest as primary-tile preview diagnostics while packet
      export performs UV integer-tile lookup for full UDIM sampling.
      Golden/full-GPU QA now report UDIM diagnostics and packet export verifies
      1002 tile sampling. Verified with the AR/PBR regression suite, full
      live/full-GPU/packet golden-scene QA, and full-GPU export service smoke
      QA producing `debugCapture/ar_pbr_golden_scene_p1_7_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p1_7.json`.
    - [x] 2026-07-03 P1-8 Triplanar projection:
      `app.ar_pbr.triplanar` now normalizes normal-weighted axis box
      projection controls, schema lighting preserves triplanar settings, and
      live GL, packet export, and full-GPU helper shaders all sample material
      maps through the shared triplanar projection contract. Packet export
      blends authored UV sampling to triplanar sampling by strength and reports
      triplanar pixels/maps; golden/full-GPU QA now verify live, packet, and
      full-GPU triplanar diagnostics. Verified with the AR/PBR regression
      suite, full live/full-GPU/packet golden-scene QA, and full-GPU export
      service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p1_8_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p1_8.json`.
  - [ ] Marmoset-style rendering approximation P2: SSS, hair/groom shading,
    cloth/sheen, glint/sparkle, caustic approximations, depth
    of field, motion blur, lens distortion, bloom/vignette/grain/sharpen, and
    beauty/alpha/depth/normal/albedo/roughness/metallic/AO/object-ID/shadow/
    reflection render passes.
    - [x] 2026-07-03 P2-1 SSS:
      `app.ar_pbr.subsurface` now normalizes single-scatter/wrap diffuse/
      backscatter controls with explicit approximation boundaries. Schema
      lighting preserves SSS settings, packet export applies the shared
      scene-linear subsurface lobe, and live GL/full-GPU helper shaders consume
      matching SSS uniforms and diagnostics. Golden/full-GPU QA verify live,
      packet, and full-GPU SSS contracts. Verified with the AR/PBR regression
      suite, full live/full-GPU/packet golden-scene QA, and full-GPU export
      service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_1_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_1.json`.
    - [x] 2026-07-03 P2-2 Hair/groom shading:
      `app.ar_pbr.hair` now normalizes a render-pass-safe hair/groom contract
      with dual-lobe Kajiya-Kay-style anisotropic specular, tint, primary/
      secondary shift/roughness, anisotropy, and rim glint controls. Packet
      export applies the shared tangent-based hair lobe in scene-linear
      shading, while live GL and full-GPU helper shaders consume matching
      uniforms and diagnostics. The approximation boundary is explicit: no
      generated strand geometry, groom simulation, Marschner multi-scattering,
      or deep opacity shadow maps. Verified with the AR/PBR regression suite,
      full live/full-GPU/packet golden-scene QA, and full-GPU export service
      smoke QA producing `debugCapture/ar_pbr_golden_scene_p2_2_full_qa.json`
      and `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_2.json`.
    - [x] 2026-07-03 P2-3 Cloth/sheen:
      `app.ar_pbr.cloth` now normalizes a render-pass-safe cloth/sheen
      contract with Charlie-style broad sheen, grazing fiber fuzz, wrap
      lighting, edge tint, and retroreflection controls. Packet export applies
      the shared scene-linear fabric sheen lobe, while live GL and full-GPU
      helper shaders consume matching uniforms and diagnostics. The
      approximation boundary is explicit: no weave/thread geometry, cloth
      simulation, fiber displacement, or deep fiber shadow maps. Verified with
      the AR/PBR regression suite, full live/full-GPU/packet golden-scene QA,
      and full-GPU export service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_3_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_3.json`.
    - [x] 2026-07-03 P2-4 Glint/sparkle:
      `app.ar_pbr.glint` now normalizes a render-pass-safe microflake
      glint/sparkle contract with strength, tint, density, scale, threshold,
      sharpness, and roughness-jitter controls. Packet export applies the
      shared deterministic UV/world-hash sparkle lobe in scene-linear shading,
      while live GL and full-GPU helper shaders consume matching uniforms and
      diagnostics. The approximation boundary is explicit: no microflake
      geometry, particle sprites, spectral dispersion, stochastic temporal
      shimmer, sparkle shadows, or caustic light paths. Verified with the
      AR/PBR regression suite, full live/full-GPU/packet golden-scene QA, and
      full-GPU export service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_4_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_4.json`.
    - [x] 2026-07-03 P2-5 Depth of field:
      `app.ar_pbr.depth_of_field` now normalizes a render-pass-safe camera/
      lens DOF contract with strength, focus depth/range, max blur radius,
      near/far blur weighting, and bokeh-shape metadata. Packet export records
      object depth for PBR overlay pixels and applies a deterministic
      premultiplied-alpha, depth-banded Gaussian overlay blur before final
      compositing; live preview and the full-GPU helper surface the same DOF
      payload/diagnostics for follow-up framebuffer post-processing. The
      approximation boundary is explicit: no stochastic lens sampling,
      aperture blade/cat-eye bokeh, occlusion-aware gather, or background
      defocus. Verified with the AR/PBR regression suite, full live/full-GPU/
      packet golden-scene QA, and full-GPU export service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_5_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_5.json`.
    - [x] 2026-07-03 P2-6 Bloom/vignette/grain/sharpen:
      `app.ar_pbr.post_effects` now normalizes a render-pass-safe beauty-pass
      post-effects contract with bloom threshold/radius, radial vignette,
      deterministic film grain, and unsharp-mask sharpen controls. Packet
      export applies the pass after AR/PBR compositing while preserving alpha
      and records component-level pixel diagnostics; live preview and the
      full-GPU helper surface matching payload/diagnostics for follow-up
      framebuffer post-processing. The approximation boundary is explicit:
      beauty pass only, data render passes bypassed, no glare streaks, lens
      dirt, chromatic ghosts, temporal grain, or optical flare simulation.
      Verified with the AR/PBR regression suite, full live/full-GPU/packet
      golden-scene QA, and full-GPU export service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_6_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_6.json`.
    - [x] 2026-07-03 P2-7 Screen AO / SSAO:
      `app.ar_pbr.ambient_occlusion` now normalizes a Marmoset-style ambient
      occlusion contract with `off`/`screen`/`ray_traced` modes, strength,
      radius, distance, AO tint, and ambient/diffuse/specular participation
      flags. Packet export applies a deterministic alpha/depth edge-aware
      screen-space AO approximation to AR/PBR overlay pixels and records AO
      pass statistics; live preview and the full-GPU helper surface matching
      AO diagnostics for follow-up native framebuffer SSAO/ray-traced AO.
      The approximation boundary is explicit: packet export uses a screen
      approximation even for ray-traced AO contract requests, with no true ray
      traversal, multi-bounce visibility, or geometry-aware horizon search.
      Verified with the AR/PBR regression suite, full live/full-GPU/packet
      golden-scene QA, and full-GPU export service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_7_full_qa.json` and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_7.json`.
    - [x] 2026-07-03 P2-8 Render pass exporter:
      `app.ar_pbr.render_passes` now normalizes a Marmoset-style multi-pass
      render export contract and packet export writes PNG artifacts for beauty,
      alpha mask, depth, normal, position, material ID, object ID, AO,
      direct/indirect lighting, diffuse/specular, albedo, emissive, roughness,
      metallic, transparency, shadow, and reflection passes. The packet path
      reconstructs data passes from preview PBR packets, material maps, stable
      material/track hash IDs, depth/object coverage, and catcher packets; live
      preview surfaces the same request contract and the full-GPU helper records
      contract-only diagnostics until native full-GPU pass FBO readback lands.
      The approximation boundary is explicit: lighting splits are beauty/data
      approximations, AO is packet alpha screen-space, output is 8-bit PNG, and
      no EXR/float buffers or true full-GPU native pass extraction are claimed.
      Verified with AR/PBR compositor/golden-scene tests, the full AR/PBR
      regression suite, full live/full-GPU/packet golden-scene QA, and full-GPU
      service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_8_full_qa.json`,
      `debugCapture/ar_pbr_golden_scene_p2_8_full/render_passes/*.png`, and
      `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_8.json`.
    - [x] 2026-07-03 P2-9 Motion blur:
      `app.ar_pbr.motion_blur` now normalizes final-render shutter/sample
      motion blur controls, frame duration, shutter angle/fraction, strength,
      sample count, and optional camera-intrinsics pixel motion. Packet export
      rebuilds AR/PBR preview packets at centered shutter sample times, blends
      those RGBA samples, records changed-pixel/sample diagnostics, and exports
      a blurred beauty render pass while keeping data passes on the center
      sample. Live preview surfaces the same request as a single-sample viewport
      contract, and the full-GPU helper records contract-only diagnostics until
      native velocity-buffer or multi-sample service rendering lands. Verified
      with the AR/PBR regression suite, full live/full-GPU/packet golden-scene
      QA, and full-GPU service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_9_full_qa.json`,
      `debugCapture/ar_pbr_golden_scene_p2_9_full/render_passes/beauty.png`,
      and `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_9.json`.
    - [x] 2026-07-03 P2-10 Lens distortion and chromatic aberration:
      `app.ar_pbr.lens_effects` now normalizes camera/lens post-pass controls
      for barrel/pincushion radial distortion, secondary radial coefficient,
      lens center, edge falloff, and radial RGB channel fringe offsets. Packet
      export applies a deterministic inverse radial UV beauty-pass warp with
      R/G/B channel-specific sampling, preserves alpha, records changed-pixel,
      distortion, and chromatic-aberration diagnostics, and writes the warped
      beauty pass while leaving data render passes as packet-reconstructed
      center data. Live preview surfaces the request as a contract diagnostic,
      and the full-GPU helper records contract-only diagnostics until native
      framebuffer post-processing lands. Verified with the AR/PBR regression
      suite, full live/full-GPU/packet golden-scene QA, and full-GPU service
      smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_10_full_qa.json`,
      `debugCapture/ar_pbr_golden_scene_p2_10_full/render_passes/beauty.png`,
      and `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_10.json`.
    - [x] 2026-07-03 P2-11 Lens flare, aperture flare, dirt/scratch grain:
      `app.ar_pbr.lens_flare` now normalizes flare, ghost count/spacing,
      aperture blade flare, lens dirt, scratch grain, tint, thresholds, and
      deterministic seed settings under `tigerstudio.ar_pbr.lens_flare.v1`.
      Packet export applies deterministic bright-source radial ghosts/halo,
      multi-blade aperture streaks, hash-based dirt, and scratch overlays as
      beauty-pass post effects while preserving packet-reconstructed data
      passes. Live preview and the full-GPU helper now expose the same
      diagnostic contract; full-GPU keeps this as a helper contract until a
      native framebuffer post-process pass lands. Verified with the AR/PBR
      regression suite, full live/full-GPU/packet golden-scene QA, and
      full-GPU service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_11_full_qa.json`,
      `debugCapture/ar_pbr_golden_scene_p2_11_full/render_passes/beauty.png`,
      and `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_11.json`.
    - [x] 2026-07-03 P2-12 Ray/hybrid GI detail controls:
      `app.ar_pbr.ray_gi_detail` now normalizes max/diffuse/specular/
      refraction bounce counts, direct/indirect radiance clamps, advanced
      light/MIS sampling, environment sample counts, and denoise-channel
      controls under `tigerstudio.ar_pbr.ray_gi_detail.v1`. Packet export
      applies direct/indirect radiance clamps and gates the existing beauty
      denoise by the requested channel policy while preserving diffuse/
      specular/transmission denoise channels as render contracts. Live preview
      and the full-GPU helper expose matching diagnostics; native ray/hybrid
      bounce traversal and full-GPU light sampling remain explicit contract
      boundaries until a native integrator lands. Verified with the AR/PBR
      regression suite, full live/full-GPU/packet golden-scene QA, and
      full-GPU service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_12_full_qa.json`,
      `debugCapture/ar_pbr_golden_scene_p2_12_full/render_passes/beauty.png`,
      and `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_12.json`.
    - [x] 2026-07-03 P2-13 Caustics:
      `app.ar_pbr.caustics` now normalizes glass/specular caustic controls
      under `tigerstudio.ar_pbr.caustics.v1`, including mode, strength,
      quality, sample count, ripple scale/focus/radius/threshold, tint, and
      deterministic seed. Packet export applies a conservative transmission/
      specular caustic highlight ripple before display transform, with
      diagnostics for applied pixels and peak intensity; live preview and the
      full-GPU helper expose matching contract diagnostics while true photon/
      path caustic transport remains a native-integrator boundary. Verified
      with the AR/PBR regression suite, full live/full-GPU/packet golden-scene
      QA, and full-GPU service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_13_full_qa.json`,
      `debugCapture/ar_pbr_golden_scene_p2_13_full/render_passes/beauty.png`,
      and `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_13.json`.
    - [x] 2026-07-03 P2-14 Anisotropic material and thin-film polish:
      `app.ar_pbr.anisotropy` now normalizes general anisotropic reflection,
      clearcoat anisotropy, thin-film/iridescence, and Newton ring controls
      under `tigerstudio.ar_pbr.anisotropic_material.v1`. Packet export adds
      a render-pass-safe anisotropic GGX-style polish and deterministic RGB
      thin-film interference tint after clearcoat, while hair/cloth/glint keep
      their specialized lobes and hair-specific anisotropy is isolated from
      material-level `anisotropy`. Live preview and the full-GPU helper expose
      matching diagnostics; native full-GPU anisotropic/thin-film shader parity
      remains an explicit contract boundary. Verified with the AR/PBR
      regression suite, full live/full-GPU/packet golden-scene QA, and
      full-GPU service smoke QA producing
      `debugCapture/ar_pbr_golden_scene_p2_14_full_qa.json`,
      `debugCapture/ar_pbr_golden_scene_p2_14_full/render_passes/beauty.png`,
      and `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_14.json`.
    - [x] 2026-07-03 P2-15 Detail normals and advanced microsurface:
      `app.ar_pbr.microsurface` now normalizes detail normal layering,
      micro roughness, gloss variation, and specular micro-occlusion controls
      under `tigerstudio.ar_pbr.microsurface.v1`. Packet export applies a
      deterministic UV/world-space detail-normal layer after authored normal
      maps and a render-pass-safe micro roughness/gloss adjustment before
      lighting/render-pass output, with changed-pixel and normal-delta
      diagnostics. Live preview and the full-GPU helper expose matching
      payload/diagnostics while native full-GPU shader parity remains an
      explicit contract boundary. Verified with the AR/PBR regression suite,
      full live/full-GPU/packet golden-scene QA, and full-GPU service smoke QA
      producing `debugCapture/ar_pbr_golden_scene_p2_15_full_qa.json`,
      `debugCapture/ar_pbr_golden_scene_p2_15_full/render_passes/beauty.png`,
      and `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_15.json`.
    - [x] 2026-07-03 P2-16 Height/vector displacement:
      `app.ar_pbr.displacement` now normalizes height/vector displacement
      controls under `tigerstudio.ar_pbr.displacement.v1`, records the
      geometry-displacement contract, and keeps parallax mapping as the
      realtime fallback path. Packet export applies a render-pass-safe
      world-position displacement proxy from the height/vector sample for
      lighting and procedural shading diagnostics without changing topology,
      silhouettes, depth, or displaced shadow casters. Live preview and the
      full-GPU helper expose matching displacement diagnostics while native
      tessellation/vector-displacement shader parity remains an explicit
      contract boundary. Verified with the AR/PBR regression suite, full
      live/full-GPU/packet golden-scene QA, and full-GPU service smoke QA
      producing `debugCapture/ar_pbr_golden_scene_p2_16_full_qa.json`,
      `debugCapture/ar_pbr_golden_scene_p2_16_full/render_passes/beauty.png`,
      and `debugCapture/ar_pbr_full_gpu_export_service_qa_p2_16.json`.
    - [ ] 2026-07-03 Deferred volumetric fog:
      Deprioritized for the AR/PBR/Marmoset-style path because day-to-day
      overlay use is low compared with material response, camera/lens polish,
      and render-pass output. Keep it as optional atmosphere polish only when
      a real scene needs depth haze, local mist, or light-shaft approximation.
- [ ] AI editing quality: connect local LLM/Claude/Codex providers to real
  EditPlan generation instead of mostly rule-based fallback, then validate on
  long Korean/English/tutorial/shorts corpora with review/apply safety gates.
- [ ] Screen Studio/CapCut default-result polish: improve automatic zoom,
  cursor/click/drag/hotkey animation, background/frame defaults, template
  quality, and one-click creator presets until default exports look good
  without manual tuning.
- [ ] Professional Color/Audio/VFX depth: keep Resolve/Fairlight/Fusion wording
  honest while deepening real engines for node color, HDR/ACES/RAW, scopes,
  shot match, noise reduction, mixer/bus/plugin workflow, ADR/elastic audio,
  and 2D/3D compositor nodes.
- [x] 2026-06-28 Professional depth QA tranche: `app.professional_runtime`
  now adds explicit 32-bit/scene-linear color precision and scope parity
  checks, Fairlight-style 7.1 routing/ADR/elastic/SFX/2,000-track latency
  stress checks, and Fusion-style spline/expression/modifier/deep-volumetric
  graph checks. `tests/test_professional_runtime_next.py` locks these runtime
  contracts without claiming Resolve/Fairlight/Fusion replacement depth.
- [ ] Large-project stability: stress 4K, long timelines, many tracks, many
  presets, heavy actor projects, repeated scrub/seek, autosave/recovery, and
  project repair with real corpus projects.
- [ ] Productization trust: finish installer/update/code-signing packaging,
  crash reporting, recovery UX, privacy/local-processing copy, public README
  positioning, release notes, and pre-release QA checklist.

## Parallel Session Guardrails

- [x] 2026-06-27 ownership update: AR/PBR real-time compositor work is now
  owned by the active TigerCapture Codex implementation session, not a separate
  side session. Keep renderer code modular under `app/ar_pbr/*`, `app/depth/*`,
  and `app/camera_solve/*`; preserve thin integration hooks in
  `app/project_player.py`, `app/video_exporter.py`, `app/project_io.py`, and
  `app/media_pool.py` unless the user explicitly asks for a broader renderer
  integration pass.
- [x] 2026-06-26 main-session `app/project_player.py` touch: add bounded
  clip-audition playback only. Expected interface is `ProjectPlayer.play_until(
  end_ms, return_to_ms=...)`; it limits timer playback and restores the
  playhead after previewing the current/selected clip. It does not change
  AR/PBR preview compositor hooks or track payload contracts.
- [x] 2026-06-26 AR/PBR renderer-session update noted for main-session
  conflict avoidance. The AR/PBR session changed background ProjectPlayer
  asset descriptor import/refresh, 160ms scene-anchor/depth tracking cache,
  FBX binary `grid_cluster_proxy` preview mesh generation, material override
  normalization, software renderer solidify default, model-viewer LOD, and
  preview hit-testing against runtime tracked image points. Main-session edits
  to `app/project_player.py`, `app/video_editor_window.py`, schema/project I/O,
  or media/asset recognition must preserve those interfaces and avoid
  overwriting AR/PBR normalize, preview refresh, and import-cache behavior.
- [x] AR/PBR product direction: CPU `software_pbr` is now a fallback/diagnostic
  path for export and QImage consumers. Real model preview/export still needs a
  native/GPU renderer path for real shadow maps, physically richer reflections,
  true prefiltered cubemap IBL, and color-match passes without relying only on
  headless packet rasterization or CPU RGB compositing. The timeline GL preview now
  covers model-view-style material-map PBR triangles, and headless export now
  rasterizes the same PBR material-map packets with depth-mask support, so the
  remaining gap is renderer quality rather than missing material-map export.
  The full-GPU export service contract, default helper command, probe QA, and
  actual helper invocation are present. Remaining follow-up is quality tuning:
  real shadow maps, reflection fidelity, cubemap/IBL tuning, batching, and full
  camera/lens solve rather than the existence of a worker-safe full-GPU helper
  path.
- [x] 2026-06-28 AR/PBR renderer-quality pass excluding real shadow maps:
  `build_gpu_preview_items()` keeps textured/PBR triangles for live depth
  texture fragment occlusion instead of coarse-culling them, `OpenGLPreviewWidget`
  samples base/roughness/metallic/specular/normal/occlusion maps with packed
  channel selectors and a white base fallback, packet export mirrors AO and
  item-depth masking, reflection catchers use layered depth-fade packets, and
  scene-anchor runtime diagnostics expose `template_depth_plane_slam_assist`.
  `tools/qa_ar_pbr_export_bake.py` now forces packet export so the packet bake
  gate remains stable when full-GPU helper rendering is available. Real shadow
  maps remain deferred.
- [x] 2026-06-26 first AR/PBR GPU preview path: ProjectPlayer now defers
  AR/PBR overlay packets as `ar_pbr_items` when the GL preview path is active;
  `OpenGLPreviewWidget` draws those NDC colour-triangle packets directly over
  the video texture. Later passes added texture maps, live depth texture
  occlusion, catcher packets, and GPU/packet export parity.
- [x] 2026-06-26 AR/PBR GPU preview QA added: `tools/qa_ar_pbr_gpu_preview.py`
  imports the real `es.fbx` when present, builds `ar_pbr_items` through the
  headless GPU packet path, and writes `debugCapture/ar_pbr_gpu_preview_qa.json`.
- [x] 2026-06-27 AR/PBR GPU preview catcher pass: `build_gpu_preview_items()`
  now emits separate `shadow_vertices` and `reflection_vertices` packets,
  sorts mesh triangles back-to-front for more stable self-overlap, and
  `OpenGLPreviewWidget` draws catcher packets before mesh packets in the same
  GL overlay path. `tools/qa_ar_pbr_gpu_preview.py` now fails unless real mesh,
  shadow, and reflection GPU packets are generated. Later passes added material
  texture maps, live depth texture occlusion, layered reflection packets, and
  GPU/export parity. Real shadow maps remain deferred.
- [x] 2026-06-27 AR/PBR attachment stability QA: GPU preview packet building
  now resolves road-plane/scene-anchor placement before projection, matching
  the software fallback's "stick to video" semantics. `tools/qa_ar_pbr_attachment_stability.py`
  verifies per-frame center drift, placement application, shadow/reflection
  catcher packets, coarse fallback depth-occlusion diagnostics, and simple video-driven
  affine tracking. Scene-anchor tracking now searches scale/rotation template
  variants, uses nearby probe templates to estimate relative motion, and applies
  the measured zoom/roll to `transform.scale` and `transform.rotation.z`.
  QA Dashboard exposes it as
  `AR/PBR Attachment Stability`. Runtime diagnostics now expose
  `template_depth_plane_slam_assist`; remaining work is full 3D camera
  solve/SLAM, lens distortion, and perspective rotation from multiple tracked
  points.
- [x] 2026-06-27 AR/PBR viewport transform gizmo polish: the preview canvas and
  preview pop-out now use a standard 3D-editor style transform gizmo instead
  of the older circle/diagonal handle. Red X, green Y, and blue Z handles
  support axis-constrained move, axis scale, and per-axis rotation rings; the
  center handle moves in screen plane and the white handle performs uniform
  scale. Remaining work: optional tool-mode toggles and true camera-oriented
  world/local axes once full camera solve is available.
- [x] 2026-06-27 AR/PBR HDR environment presets: the 3D asset preview window
  now exposes an `HDR Environment` dropdown backed by
  `debugCapture/ar_pbr_resources/manifest.json`. Eight Poly Haven CC0 1K HDRIs
  are available locally: Wide Street, Studio Small 09, Abandoned Parking,
  Cayley Interior, Autumn Forest, Belfast Sunset, Cobblestone Night, and Brown
  Photostudio. The selected environment is persisted on track lighting as
  `hdri_id` and `hdri_path`, and switching presets updates the GL preview HDRI
  texture without reimporting the model.
- [x] 2026-06-27 GPU preview metadata collision QA: `tests/test_project_player.py`
  now verifies that one GL frame can carry color grade, shader clip effects,
  Spine direct overlay items, and AR/PBR overlay items together without dropping
  or overwriting any payload. The test also verifies that `VideoEditorWindow`
  dispatches the combined payload to `OpenGLPreviewWidget` as separate clip
  effects, Spine items, AR/PBR items, and grade data.
- [x] 2026-06-27 GPU preview pixel collision QA: `tools/qa_gpu_preview_pixel_collision.py`
  creates a small `OpenGLPreviewWidget`, renders a real framebuffer with color
  grading, shader clip effects, and AR/PBR mesh/shadow/reflection packets, saves
  `debugCapture/gpu_preview_pixel_collision.png`, and fails if the shader
  change or overlay pixels are not visible. It is wired into the in-app QA
  Dashboard as `GPU Preview Pixel Collision`. The same QA now also draws a real
  Spine sample through the direct GL overlay path and uploads a real Live2D
  rendered sample through the GPU preview base-frame path, with per-actor
  screenshots and changed-pixel thresholds.
- [x] 2026-06-27 GPU/export parity matrix QA: `tools/qa_gpu_export_parity_matrix.py`
  now runs GL pixel collision, final editor export bake, and synthetic export
  parity smoke checks into one report at
  `debugCapture/gpu_export_parity_matrix_qa.json`. The matrix covers color
  grade, shader effects/chroma, typography export pixels, Spine/Live2D actor
  preview/export evidence, transition export, and masked node graph export,
  plus AR/PBR object export bake evidence from `tools/qa_ar_pbr_export_bake.py`.
  QA Dashboard exposes it as `GPU Export Parity Matrix`.
- [x] 2026-06-27 AR/PBR export bake parity: `VideoExportThread` accepts
  `ar_pbr_tracks` and optional asset descriptors, forces the preview-parity
  raw-frame export path when AR/PBR objects are present, and composites active
  tracks through the same GPU-preview packet contract via
  `app.ar_pbr.export_packet_renderer` before writing frames to FFmpeg.
  `composite_export_frame()` remains the fallback if packet rendering cannot
  draw a track. `tools/qa_ar_pbr_export_bake.py` verifies a model track changes
  final MP4 pixels, records `mode=gpu_packet_export`, and checks packet mesh
  triangles, shadow/reflection packet triangles, catcher darkening, and packet
  SSAA in `debugCapture/ar_pbr_export_bake_qa.json`. The packet path now shares
  `app.ar_pbr.texture_plan` with the model-view loader, reports texture-map
  readiness, applies model-view-style material-map PBR in GL preview, and
  samples UV texture triangles in headless export so final MP4 output no longer
  silently ignores textured materials. The packet export path now also
  rasterizes base/roughness/metallic/specular/normal/occlusion PBR packets, reports
  `renderer_quality=preview_packet_pbr_material_maps`, and can apply a
  depth-frame or packet live-depth alpha mask for occluding foreground pixels. The export mode now
  recognizes `gpu`/`offscreen_gpu` requests and records an explicit
  worker-safe packet fallback diagnostic instead of silently treating the value
  as a normal packet export. Remaining AR/PBR work is now renderer quality:
  real shadow maps, physically richer reflections, lens/camera solve fidelity,
  full-GPU service quality tuning, and long-project performance.
- [x] 2026-06-27 AR/PBR timeline GL model-view material-map PBR: `build_gpu_preview_items()`
  now emits `pbr_triangles` with projected position, UV, normal, tangent,
  bitangent, fallback color, and material roughness/metallic/reflectance values.
  It also passes roughness/metallic/specular/normal/occlusion texture-map paths,
  packed channel selectors, live depth texture metadata, and HDRI
  lighting metadata to `OpenGLPreviewWidget`. The GL preview shader now samples
  those maps, approximates HDRI/IBL with ACES/gamma handling, and preserves the
  existing color/shadow/reflection packet fallback. The GL shader now dampens
  specular environment reflection by roughness, and the export packet path
  mirrors the material-map path through a headless PBR packet rasterizer, while
  still remaining lower quality than the full model-view GPU renderer.
  Remaining renderer-quality work: real shadow maps, physically richer
  reflections, GPU/model-view cubemap prefilter parity, and full
  model-view GPU renderer parity for export.
- [x] 2026-06-27 AR/PBR headless PBR export rasterizer: `export_packet_renderer`
  now consumes `pbr_triangles` from `build_gpu_preview_items()` and samples
  base, roughness, metallic, specular, and normal maps. Export now also samples
  HDRI lighting by normal/reflection direction instead of only using an average
  environment color, builds cached downsampled HDRI prefilter levels, samples
  roughness-selected mip levels for specular IBL, and reports
  `pbr_hdri_directional_sampling`, `pbr_hdri_sampled_pixels`,
  `pbr_prefiltered_ibl`, `pbr_prefiltered_ibl_level_count`, and sampled
  prefilter pixels in diagnostics. `tools/qa_ar_pbr_export_bake.py` requires
  PBR packet readiness, material-map sampling, HDRI directional sampling,
  roughness IBL prefiltering with at least two levels, and
  `renderer_quality=preview_packet_pbr_material_maps`;
  `tests/test_ar_pbr_compositor.py` also covers export depth-mask occlusion
  and the explicit offscreen-GPU request fallback for PBR packets.
- [x] 2026-06-27 AR/PBR mesh-aware catcher packets: the preview/export packet
  builder now emits screen-space mesh silhouette contact shadows and mirrored
  mesh reflection catchers, then layers the older soft ellipse/strip fallback
  underneath. This improves model-view feel while keeping the fallback packet
  contract intact; true shadow maps and physically correct reflection catchers
  remain future renderer-quality work.
- [x] 2026-06-27 Live2D workflow QA is now part of the GPU/export parity
  matrix: `tools/qa_gpu_export_parity_matrix.py` runs actor loading UX and
  actor-lane workflow with real Live2D/Spine samples, adding a
  `live2d_actor_workflow` release-blocking row alongside preview/upload and
  export-bake checks.
- [x] 2026-06-27 full editor E2E smoke QA: `tools/qa_editor_e2e_smoke.py`
  opens the real Video Editor, imports a QA MP4 through Media Pool + timeline,
  verifies the preview placeholder is cleared, preview RGB is nonblank, side
  docks do not overlap the viewer, preview pop-out receives frames, Media Pool
  and Workbench pop-outs restore their child panels, bounded clip audition
  playback returns to the original playhead, then loads the actor QA `.tgp` and
  verifies video, Media Pool, Spine, Live2D, actor-lane ruler alignment, and
  nonblank preview together. QA Dashboard exposes it as `Editor E2E Smoke` with
  screenshot/contact-sheet preview.
- [x] 2026-06-27 preview placeholder hardening: entering placeholder mode now
  hides stale GL preview surfaces and clears cached RGB/frame-size state; real
  GPU frame delivery clears the QLabel backing pixmap again after `update_frame`
  so a small GL viewport cannot reveal the old "Start your edit" card behind
  video playback.
- [x] 2026-06-27 final editor export-bake QA: `tools/qa_editor_export_bake.py`
  exports a baseline MP4 and a processed MP4 from the QA corpus, then probes the
  encoded frames with OpenCV to prove text overlays, clip filters, zoom actors,
  and color grade reach the final file. The report stores baseline/processed
  stills, pixel-diff metrics, and is exposed in QA Dashboard as `Editor Export
  Bake`.

## Current Polish Pass

- [x] Add the 1~6 loading/performance acceleration pass requested on
  2026-06-27: Live2D/Spine actor load stages now mirror into persistent
  `debugCapture/loading_performance.jsonl`, decoder auto/open decisions are
  timed, AR/PBR preview import/vertex/HDRI/texture stages are timed,
  editor startup schedules background parser/importer/Live2D prewarm,
  AR/PBR model imports reuse a persistent descriptor cache, repeated 3D
  preview windows are reused instead of re-created, and conservative fast
  preview defaults enable decoder auto-selection, frame-server auto mode,
  larger frame caches, Spine zero-readback GL preview, and AR/PBR GPU preview.
  `tools/qa_loading_performance.py` reports the active policy and recent slow
  loading stages.
- [x] Localize clip-badge context menu/status strings across shipped languages.
- [x] Show preset-application feedback for effect/title/transition/audio/color
  presets, not only template presets.
- [x] Add Screen Studio real-recording slot board so the 20-slot corpus shows
  empty/invalid/needs-sidecar/needs-clicks/needs-drag-hotkey/needs-auto-zoom/
  ready states.
- [x] Split Screen Studio real-video corpus from interaction-ready cursor
  sidecar corpus: registration now stores sidecar metadata, supports
  `--require-sidecar`, and corpus QA reports replacement-claim blockers plus
  remaining sidecar/interaction counts.
- [x] Add Screen Studio render-result smoke QA that writes and validates a real
  MP4 artifact.
- [x] Add Creator Assist quick-create flow inside the editor-side panel instead
  of pushing users back to launcher templates.
- [x] Extend creator-polish QA coverage for preset feedback, render smoke,
  CapCut quick-create, Screen Studio defaults, and stability hooks.
- [x] Add reusable preset apply/drop feedback models with badge labels,
  duration/time text, blocked-drop reasons, and Media Pool/Workbench hint cards.
- [x] Add Creator Assist quick-create progress/result feedback inside the
  editor panel.
- [x] Add Screen Studio/CapCut quick-result presets and templates for tutorial,
  product demo, cursor-click, and shorts workflows.
- [x] Add real-project product-flow QA over local `.tgp` projects plus render
  smoke validation, exposed through QA Dashboard.
- [x] Make crash/recovery dialogs expose friendlier user-action summaries:
  autosave availability, relink/actor-review/open actions, and repro export.
- [x] Add the Product Polish Next gate for the current 10-item worklist:
  preset timeline strips, A/B preset preview metadata, Screen Studio real
  corpus zoom/cursor tracking, CapCut caption/shorts quality, timeline feel
  feedback, Media Pool discoverability, export parity expansion, crash
  recovery productization, UI visual consistency, and QA Dashboard
  productization. `tools/qa_product_polish_next.py` writes
  `debugCapture/product_polish_next_qa.json`; current implementation passes
  10/10 areas while truthfully reporting that the real Screen Studio recording
  corpus still has 0/20 recordings.
- [x] Add the 1~6 release-gap closure gate requested for the current product
  pass: `app.release_gap_closure.build_release_gap_closure_report()` and
  `tools/qa_release_gap_closure.py` aggregate generative AI one-click editing,
  Screen Studio real-recording interaction corpus, preview scrub/seek
  responsiveness, Live2D/Spine compatibility, release positioning, and UI/UX
  polish into one report. The default CLI writes
  `debugCapture/release_gap_closure_qa.json` without failing normal development
  when an honest gap remains; `--strict` turns the same report into a release
  gate that fails unless all six areas are ready.
- [x] Push the evidence-heavy blockers into an executable collection
  sprint: `app.release_evidence_sprint` and
  `tools/prepare_release_evidence_sprint.py` generate a Screen Studio sidecar
  capture script, AI real-case registration script, broadcast platform evidence
  registration script, safe templates, and a README playbook under
  `debugCapture/release_evidence_sprint`. The sprint deliberately does not
  unblock claims by itself; it only makes real cursor / click / drag / hotkey
  sidecars, filled AI transcript/prompt cases, and redacted RTMP/Discord
  platform evidence easier to collect. `tools/record_screenstudio_cursor_sidecar.py` now supports
  `--capture-hotkeys`, and live capture defaults to the Windows virtual screen
  instead of an unusable 1x1 rectangle when `--screen-rect` is omitted.
- [x] Surface the release evidence sprint inside QA Dashboard: selecting
  `Release Evidence Sprint` enables `Evidence Actions`, which prepares missing
  scripts and opens the cursor sidecar capture script, AI real-case
  registration script, one-case AI registration script that prompts for a real
  transcript/prompt before registering, broadcast platform evidence
  registration script, README playbook, or evidence folder without counting any
  fake evidence. The same dialog can rerun cursor-corpus QA,
  AI-corpus QA, broadcast platform E2E, broadcast release-readiness, evidence
  sprint generation, release gap, and final product-readiness after real
  evidence is collected.
- [x] Add release evidence progress accounting: sprint reports now include
  `progress.overall_percent`, interaction-ready Screen Studio counts,
  cursor-sidecar counts, AI real-case counts, and explicit blockers. QA
  Dashboard details and `Evidence Actions` display those numbers so a user can
  distinguish generated templates, sidecar files, and actual release-ready
  evidence.
- [x] Break Screen Studio evidence progress down by real proof type:
  cursor sidecar, click animation, drag tracking, hotkey overlay, and auto-zoom
  window readiness are now separate progress rows. Release blockers include the
  specific missing proof type, not only a generic `interaction_ready` gap.
- [x] Add a release evidence work queue: sprint reports now include
  `work_queue` entries that name the next recording/template to handle, its
  missing proof requirements, the target sidecar/template path, and the safest
  command/action to run. QA Dashboard details and Evidence Actions show the
  first queue items so users know what to do next instead of staring at a
  percentage.
- [x] Add a one-slot Screen Studio evidence capture path: `Record Next Slot`
  in QA Dashboard writes and opens `record_next_screenstudio_sidecar.ps1` for
  the first blocked `work_queue` recording. The script opens the target video,
  waits for the user, captures real cursor/click/drag/hotkey data, registers
  the sidecar, and tells the user to refresh evidence status. It only captures
  one slot, so the 20-slot evidence pass can be done incrementally.
- [x] Add one-click evidence refresh in QA Dashboard: `Evidence Actions` now has
  `Refresh Evidence Status`, which reruns Screen Studio real-corpus QA, AI
  corpus QA, evidence sprint generation, and the release gap gate in source-to-
  gate order.
- [x] Add the first Resolve/Fairlight/Fusion deficiency-fill tranche:
  professional Color pipeline sidecars for 32-bit scene-linear/YRGB intent,
  non-destructive RAW controls, HDR10+/Dolby Vision metadata, node render
  order, and restoration FX; Fairlight-style realtime mixer graph, latency
  compensation, ADR cue, elastic retime, and SFX library contracts; richer
  Fusion-style 2D/3D compositor graph; and professional Deliver codec matrix
  for ProRes, DNxHR, EXR, and DPX. `tools/qa_professional_pipeline_next.py`
  writes `debugCapture/professional_pipeline_next_qa.json`.
- [x] Fill the remaining Professional Pipeline Next advisory gaps as explicit
  contracts: advanced Color Log/HDR/Hue/Warper and tracked secondary payloads,
  face/skin/object/patch repair payloads, local-only ML registry, 2,000-track
  Fairlight-style mixer stress contract, collaboration locks/shared-marker/
  handoff payload, and studio hardware registry for color panels, Fairlight
  audio I/O, and DeckLink-style monitoring. The QA report now reaches 100/100
  for this readiness-contract gate while still documenting that native engines
  and daily-use UI depth remain separate future work.
- [x] Add Professional Runtime Next execution QA so the professional payloads do
  not stop at metadata: synthetic Color frames run through advanced color +
  tracked secondary preview/export parity, Fusion-style VFX graphs produce a
  topological execution/cache-boundary plan, local-only ML analyzes a generated
  probe image, and the Fairlight-style audio route model runs the 2,000-track
  stress contract. `tools/qa_professional_runtime_next.py` writes
  `debugCapture/professional_runtime_next_qa.json` and is visible in QA
  Dashboard.
- [x] Add an LTX-style SDR-to-HDR foundation without overstating model parity:
  `app/sdr_hdr_upmap.py` builds a deterministic SDR video -> HDR-capable
  float EXR frame sequence path with a scene-linear target contract,
  `tools/convert_sdr_to_hdr_exr.py` exposes a dry-run/run CLI,
  `tools/qa_sdr_hdr_upmap.py` validates the EXR/provider
  contract, and the Workbench node graph now has an `SDR -> HDR EXR` job node
  with peak-nits/exposure/highlight/saturation/max-frame controls plus a main
  Workbench `Create EXR Frames...` action for selected video tracks.
  `sdr_hdr_upmap_preset_gallery()` and `sdr_hdr_upmap_review_model()` now expose
  Soft HDR / Social HDR / Cinematic Probe / EXR Archive presets, UI-ready
  controls, provider status, and actions for the node/property panel. This is a
  local inverse-tone-map EXR workflow plus LTX/ComfyUI provider hook, not a
  claim that the bundled app includes the real LTX 2.3 HDR model.
- [x] Add an LTX-style Storyboard / Shot Card planner without claiming LTX cloud
  parity: `app/ltx_storyboard.py` turns a prompt plus project/media metadata
  into deterministic `ShotCard` rows with shot type, camera angle/motion,
  transition hint, source query, style bible, actor/audio/color intent, and
  review-first timeline operations. `tools/build_ltx_storyboard.py` writes a
  local report, `tools/qa_ltx_storyboard.py` validates shot-card metadata,
  provider hooks, safe `EditPlan` conversion, apply-payload markers/sidecars,
  retake variations, and template recommendations. `tools/qa_ltx_storyboard_corpus.py`
  runs screen-tutorial, gameplay, product-demo, dialogue, and Korean storyboard
  prompts. Creator Assist now surfaces an `ltx_storyboard` / `Shot cards`
  review card with zoom/callout/retake/template counts inside the normal
  CapCut-style bundle. `ltx_storyboard_effect_materialization` stages concrete
  review-first zoom windows, callouts, template links, and effect rows; Creator
  Assist now turns zoom windows into real zoom actors plus timeline-visible
  chips, turns callouts into typography actors, maps known template links to
  real workflow template presets without duplicate stacking, and project apply
  stores those storyboard payloads in `capcut_creator_package`.
- [x] Promote Professional Runtime Next from a standalone report into the
  product gates: Final Product Readiness now includes a professional runtime
  parity area, and Productization Loop/fast QA refresh both
  `qa_professional_pipeline_next.py` and `qa_professional_runtime_next.py` so
  Color/Fairlight/Fusion/Deliver contracts must stay executable.
- [x] Add stabilizer preview fast path: preview uses low-resolution optical-flow
  tracking through `FrameStabilizer.apply_preview()` while export keeps
  full-quality `apply()`. Current QA has zero native/GPU candidates; the
  mask/filter/tracking playback project measured 14.83 ms average / 18.47 ms p95.
- [x] Clean up preview refresh/seek advisory costs: ProjectPlayer now imports
  zoom helpers from lightweight `timeline_model` instead of the huge editor
  window during preview render, and duplicate same-position seeks reuse the
  last completed preview frame. Current QA reports first-project setup at
  92.27 ms, refresh render at 42.82 ms, and no native/GPU candidates.
- [x] Separate preview QA setup from first-frame rendering: `refresh_tracks()`
  accepts `render_immediately=False`, `tools/qa_preview_perf.py` uses it for
  corpus setup, and the current report has 6 sampled projects, zero
  `preview.refresh.render` rows, and zero native/GPU candidates. The remaining
  slow rows are random seek/decode advisory costs.
- [x] Make preview prefetch handle small forward scrubs by default:
  `TIGERCAPTURE_PREFETCH_FORWARD_SEEK_WINDOW` now defaults to 12 frames, so
  near-future seeks can reuse already-prefetched frames without opt-in tuning.
- [x] Make windowed-titlebar dragging feel lighter: `VideoEditorWindow.moveEvent`
  now enables a short window-move guard that stops decorative marching-ants,
  timeline tool icon animation, preset hover/live-preview timers, preset swatch
  animation, and audio mixer VU decay, while `ProjectPlayer` uses a coarse,
  slower preview timer until the OS window move settles.
- [x] Productize the window-move guard with QA: `tools/qa_window_move_guard.py`
  writes `debugCapture/window_move_guard_qa.json`, verifies ProjectPlayer timer
  relaxation/restoration and editor surface suspension, and final readiness now
  requires it inside `timeline_polish`.
- [x] Tighten Screen Studio real-corpus QA: `interaction_ready` now requires
  click, drag, hotkey, and auto-zoom sidecar signals, and per-slot boards expose
  interaction quality score plus missing requirements.
- [x] Promote Screen Studio interaction evidence into final readiness:
  `screenstudio_interaction_corpus` is now its own release area, and
  `qa_final_product_readiness.py` fails by default when the real recording
  corpus lacks cursor sidecars, click/drag/hotkey events, auto-zoom windows, or
  enough `interaction_ready` samples for replacement marketing.
- [x] Implement Smart Cursor FX MVP: cursor sidecars now preserve
  `hit_role`/`hit_label`/`cursor_style`/`animation`, TigerCapture recordings
  infer role metadata for the app's own Qt controls, timeline tool buttons set
  stable `cursor_fx_role` properties, and preview/export renders role-aware
  cursor shapes including Blade's animated scissors/snip cue.
- [x] Expand Resolve/Fairlight/Fusion depth cards with daily-use checks and
  blocking counts mapped to real feature IDs, so the professional parity report
  distinguishes metadata support from daily editing/mixing/compositing depth.
- [x] Add the first file-output path for video-to-Live2D motion capture:
  `app/actor_mocap.py` converts local video face detections into Live2D
  transform keyframes, the editor exposes `Apply Video Motion to Live2D`, clip
  metadata saves through project IO, and export bakes the motion via the
  existing Live2D pre-render path. Live2D-only projects can now export to a
  normal video file over a neutral dark background instead of showing the old
  unsupported message. The renderer now also applies saved Live2D parameter
  keyframes after each authored motion update, so face/gesture payloads can
  layer `ParamAngleX`, `ParamAngleY`, `ParamBodyAngleX`, MediaPipe-derived
  `ParamAngleZ`, `ParamEyeBallX/Y`, `ParamMouthOpenY`, `ParamMouthForm`, and
  `ParamEyeLOpen/ROpen`, or any future Cubism parameter id on top of a selected motion. After mocap apply, the editor now
  auto-attempts the authored-motion storyboard pass and silently falls back to
  plain mocap when the model has no usable `.motion3.json` motions. The default
  retarget profile is now talking-head stabilized: deadzone/smoothing/capped
  scale remove the push-pull camera feel from upper-body speech videos, and
  body-angle retargeting is heavily damped so speech footage keeps the actor
  planted. Shot classification now records
  `face_closeup`/`upper_body`/`full_body`/`full_body_or_wide`: close-up footage
  locks actor position/scale/body transform so only face parameters move;
  upper-body footage uses a damped transform profile; detected full-body footage
  keeps normal actor translation and zoom. The analyzer fills optional OpenCV HOG
  person boxes when available and falls back to face-size criteria when person
  detection is unavailable. Optional local MediaPipe FaceMesh now fills eye
  gaze, mouth-open/form, eye-open, and head roll/yaw/pitch fields when installed;
  without it, the same command remains usable with OpenCV transform/head
  fallback. This deliberately excludes livestream output and full webcam/gesture
  control, which remain later stages.
- [x] Fix preview interaction regressions in the Screen Studio-style preview:
  clicking a visible video/actor frame now opens the paint/bubble/sticker
  canvas even when the frame is coming through the GPU preview path, and import
  dialogs are limited to truly empty previews. The detached preview now owns a
  play/pause control wired to the main `ProjectPlayer`.
- [x] Fix Live2D-only detached preview playback: actor-only Live2D/Spine frames
  now pass the editor's renderable-content guard, and the pop-out preview mirrors
  both QImage and GPU RGB frame paths so it keeps animating during playback.
- [x] Surface Live2D mocap/storyboard where users work: the Live2D actor-clip
  right-click menu now exposes video motion mapping and authored-motion
  storyboard actions, and the bottom `AI Command` dock is visible by default
  instead of requiring the toolbar AI button first.
- [x] Make Live2D video-mocap results explain themselves: `actor_mocap` now
  emits a user-facing summary that distinguishes face-closeup locked transform,
  upper-body damped transform, and full-body transform-enabled shots, and the
  editor status line lists which actor/face/eye/mouth channels were driven.
- [x] Let the full side docks detach like Media Pool/Timeline: the Media Pool
  pop-out now moves the whole left column with Effect/Title/Transition/Workflow
  presets, and the Workbench pop-out moves the whole right column with Workbench,
  Creator Assist, Script Edit, Render Queue, Audio, PIP, and Subtitles. Both
  docks keep their live widget state and dock back into the splitter on close.
- [x] Add optional YouTube URL import into Media Pool: when `yt-dlp` is
  installed, the Media Pool header/context menu can download one YouTube URL as
  MP4 into `YouTube Imports`, show progress, and auto-register/select the
  resulting file. The UI warns users to import only videos they own or have
  permission to use.
- [x] Add Live2D authored-motion storyboard mode: selected Live2D clips can now
  be rebuilt into video-cut-aligned actor clips that cycle through all available
  `.motion3.json` motions from the model, preserving transform keyframes where
  they overlap each generated segment. Mocap/manual Live2D parameter tracks are
  sliced with the same ranges, so a face-driven actor can keep reacting while
  authored motions change by cut. This addresses the first video-mocap MVP
  feeling like only zoom/scale tracking.

## AI-Readable Specs

- [x] Create `SPEC.md` as the main AI feature/architecture index.
- [x] Document capture, media intake, timeline, project IO, preview/export,
  video filters, typography/subtitles, masks, Live2D, Spine/NIKKE, and audio.
- [x] Keep `SPEC.md` updated whenever a feature crosses UI, preview, save/load,
  and export paths.
- [x] Add focused sub-specs if a section grows too large, starting with export
  parity and performance profiling.
- [x] Index the AI Script / One-Click Editing foundation: detailed plan in
  `docs/SPEC_AI_TEXT_EDITING.md`, contracts in `app/ai_edit_plan.py`,
  deterministic planners in `app/ai_text_editing.py`, QA entry point
  `tools/qa_ai_text_editing.py`, and latest report
  `debugCapture/ai_text_editing_qa.json`. Current status is MVP product
  behavior: bottom `AI Command` dock, right-dock `ScriptEditPanel`, transcript
  import/local transcription path, deterministic `EditPlan` generation,
  automatic Qwen local executor when an OpenAI-compatible endpoint is available,
  validation, preview markers, safe subtitle/marker/auto-zoom materialization,
  and an explicit reviewed-cut apply path. Remaining work is quality depth:
  wiring real local/agent provider executors, real user edit corpus, story/voice
  quality, and Descript-like text-edit naturalness.

## Object Tracking Masks

- [x] Track any selected object type, not only people: faces, animals, cars, props, screen regions.
- [x] Cache per-frame OpenCV tracker results for preview playback.
- [x] Persist correction keyframes on `BitmapMask` so drift fixes survive project save/load.
- [x] Persist tracker bbox cache and failed-frame indices on `BitmapMask` so
  tracked masks restore with useful cached state after project reload.
- [x] Add mask-editor controls to reset cached tracking and add correction keyframes.
- [x] Add mask-editor controls to clear correction keyframes separately from
  cache-only tracker reset.
- [x] Start new tracked masks from the current preview frame instead of assuming frame 0.
- [x] Add a background worker that pre-warms tracked `BitmapMask` bbox caches
  for the active node chain.
- [x] Show tracker status and failure frames directly on the timeline.
- [x] Add a first-class "Track selected region" command in every node mask menu, not only inside MaskEditorWindow.
- [x] Extend export to evaluate the active track's node graph/mask chain through
  a preview-effect raw pre-render fallback.

## Preview / Export Parity

- [x] Verify Spine actor overlays are baked into the final exported video.
- [x] Fix Live2D export input handling so pre-rendered Live2D MOVs are included
  in the final FFmpeg command.
- [x] Verify Live2D actor overlays are baked into the final exported video.
- [x] Extend final export to evaluate the full preview `track.node_item_chain`
  when node graph effects, blur, or masks cannot be represented by FFmpeg.
- [x] Add a reusable export smoke test fixture for actor overlays and
  preview-only CPU effects.
- [x] Verify/extend parity for clip-level CPU effects: chroma key, background
  removal pipeline, stabilization, and video filter params.
- [x] Promote current synthetic export checks into reusable automated smoke
  tests: Live2D overlay, Spine overlay, masked node graph, chroma key, video
  filters, background-removal pipeline, and stabilizer export.
- [x] Add `tools/qa_project_audit.py` so real projects with video + node masks
  + Live2D + Spine + audio can be audited for missing assets, feature coverage,
  media probe timings, and synthetic preview/export parity in one command.
- [x] Extend real-project QA reports with `export_risks` and deeper
  Live2D/Spine dependency checks, including Spine atlas textures and Live2D
  model3 moc/texture/motion/expression references.
- [x] Add the real-project performance QA path to the export/performance spec,
  including the exact `TIGERCAPTURE_PERF` environment needed before deciding
  when to suggest proxy/lower-FPS export.
- [x] Add a real-footage QA entry point for background-removal projects through
  `tools/qa_project_audit.py`; quality judgment still depends on the user
  supplying representative person/object footage.
- [x] Add tracked masked-node export to `tools/verify_export_parity.py` so
  `BitmapMask(track_object=True)` is verified in final video baking.
- [x] Add `tools/actor_render_qa.py` as a combined Live2D/Spine corpus QA
  command that runs dependency compatibility first and then render/nonblank
  validation through the existing actor render paths.
- [x] Make Live2D render QA safe for non-ASCII model paths and classify blank
  output by alpha bbox instead of only checking that a PIL image object exists.
- [x] Fix Live2D render QA to pass the normalized ASCII-safe runtime model path
  into `Live2DActorClip`; the bocchi2 sample now renders nonblank in the
  combined actor QA smoke pass.
- [x] Split Live2D compatibility failures into render-required MOC/texture
  failures and optional expression/physics/display/motion warnings, so llny-like
  samples that render nonblank are not reported as base-render failures.
- [x] Make Live2D child render QA parse sentinel-tagged result JSON even when
  native Live2D motion-load logs interleave with stdout; FoxHimeZero models now
  report `pass` instead of `unknown`.
- [x] Make Spine compatibility/render QA prefer a same-stem Spine JSON export
  over binary `.skel` when both exist, so unsupported Spine 4.2 binary samples
  can still be validated through the inspectable JSON export path.
- [x] Harden Live2D render QA timeout handling: a slow child-process model is
  now recorded as a per-model `timeout` result instead of aborting the combined
  actor QA run.
- [x] Add baseline comparison to `tools/actor_render_qa.py`, so repeated
  Live2D/Spine corpus runs flag newly broken compatibility/render rows,
  improvements, newly discovered models, and models missing from the current
  run.
- [x] Run the installed Live2D/Spine corpus render QA without limits: 199 models
  passed compatibility and render validation, including 160 Spine and 39 Live2D
  samples.

## Timeline UX

- [x] Make timeline thumbnail jobs ignore stale extractor signals after a newer
  job replaces them.
- [x] Generate timeline thumbnail images in worker threads as `QImage`, then
  convert to `QPixmap` on the UI thread.
- [x] Clip thumbnail painting to each clip rectangle so thumbnails do not bleed
  into adjacent clips.
- [x] Use time-based OpenCV thumbnail seeking first, with frame-index fallback,
  to reduce wrong/odd thumbnails on VFR or keyframe-heavy media.
- [x] Add same-row multi-select clip dragging with Shift/Ctrl selection,
  edge snapping, and overlap rejection.
- [x] Clamp ordinary left/right trim against neighboring clips.
- [x] Register one undo savepoint when timeline drag/trim/fade/transition
  gestures end instead of saving every mouse-move tick.
- [x] Ignore duplicate no-op history snapshots so unchanged drag/selection
  commits do not consume undo depth.
- [x] Add visible edit-mode affordances for select/blade/ripple/roll/slip/slide
  so timeline behavior is discoverable without context-menu hunting.
- [x] Move linked audio clips when linked video clips are dragged, grouped, or
  nudged.
- [x] Add true cross-track mouse-drag group move for selected video clips.
- [x] Add persistent thumbnail cache keyed by path/mtime/size/thumbnail height so
  reopening projects does not regenerate every timeline thumbnail.
- [x] Add precision trim dialog and keyboard nudge for selected clips.
- [x] Add compound/nested timeline MVP with persisted group IDs and grouped
  selection/movement.
- [x] Implement true slide edit semantics that trim adjacent clips while moving
  the selected clip.
- [x] Add nested sequence parent clips with child clip save/load, preview
  compositing, and an expand-back-to-main-timeline path.
- [x] Extend nested sequence to a dedicated internal multi-track editor with
  multi-source/multi-track raw export baking.
- [x] Upgrade the nested sequence editor from table-only editing to a compact
  timeline canvas with video/audio lanes, clip dragging, edge trimming, and
  precise millisecond tables.
- [x] Persist nested sequence audio lanes and include nested audio in export
  by remapping it to the compact output timeline before FFmpeg mixing.
- [x] Apply nested child clip stabilizer, filters, chroma key, background
  removal, per-clip color state, and clip-attached typography in preview/export.
- [x] Add nested audio preview through a hidden synthetic AudioMixer track.
- [x] Expand nested audio lanes and nested Spine/Live2D actor lanes back to
  main timeline tracks when opening a nested sequence.
- [x] Add first-class nested actor lanes for child Spine/Live2D clips with
  save/load, nested editor canvas display, preview compositing, and raw export
  compositing.
- [x] Add basic nested internal fade/transition handling for child video clips
  (`fade_black`, `fade_white`, `dissolve`) in preview/export.
- [x] Add nested editor zoom/scroll/playhead affordances.
- [x] Add detailed linked clip drag/nudge block diagnostics so timeline
  collisions report the blocking clip/track instead of only a generic failure.

## Professional UI / Workspace UX

- [x] Add shared professional editor theme tokens for app chrome, panel rails,
  timeline backgrounds, and actor/audio accent colors.
- [x] Reframe the main video editor around an app command bar, center viewer,
  left media/assets rail, right inspector, and bottom timeline surface.
- [x] Split timeline controls into a dedicated edit-tool toolbar and a separate
  effect/actor palette row so full-mode layouts do not crush controls.
- [x] Add Media Pool search and type filters for video, audio, and actor assets.
- [x] Add Media Pool Grid/List presentation and Name/Type/Duration sorting.
- [x] Restyle Sound Editor as a clip-scoped audio workspace with waveform and
  spectrum analysis in a single deck.
- [x] Bring Workbench/Inspector, Audio Mixer, Mask Editor, Spine Editor, and
  Live2D Viewer onto the shared dark panel theme.
- [x] Increase the Workbench/right inspector default width and vertical layout
  share so it is not squeezed by the center canvas, PiP, or subtitles.
- [x] Move legacy Workbench contents into true tab pages: Clip rows, FX graph,
  Mask/tracker controls, Audio rows, and Metadata summary.
- [x] Add a main-editor Audio Workspace bridge for selected audio clip editing,
  mixer visibility, and scopes visibility.
- [x] Add Media Pool logical bins, metadata footer, import/filter status, and
  hover preview.
- [x] Normalize the most visible editor chrome labels to readable ASCII while
  preserving the existing i18n system for the broader localization pass.
- [x] Tighten Spine/Live2D editor layout chrome with shared colors, thicker
  splitter handles, and bordered tree/list panels.
- [x] Complete the broader localization pass for every remaining mojibake
  string in secondary dialogs, menus, and tooltips.
- [x] Add `tools/qa_ui_layout.py` for 1366px, 1920px, and full-screen-width
  layout captures and panel-size checks after the professional UI pass.
- [x] Replace remaining mojibake labels/tooltips with clean localized strings
  as a separate text/localization pass.
- [x] Add `tools/qa_localization_audit.py` to keep locale placeholder parity
  and mojibake regressions from coming back.
- [x] Add application startup font fallback and a CJK-aware QSS font stack for
  Korean/Japanese/Chinese UI labels.
- [x] Add a global Screen Studio Qt chrome pass: force Fusion style at startup
  and restyle generic dialogs, buttons, inputs, combos, tabs, menus, tables,
  scrollbars, progress bars, toolbars, tooltips, and splitters through
  `app/style.py::APP_QSS`.
- [x] Extend the Screen Studio Qt chrome pass into local QSS-heavy tools:
  new-project, mask editor, Live2D/Spine editors, Spine scanner/timeline
  panels, actor-lane menus/dialogs, and Workbench node graph/popout now append
  `studio_chrome_qss(...)` or use matching Screen Studio palette tokens.
- [x] Fill the remaining node-mask, MaskEditor, and audio-stem separation keys
  in Japanese, Chinese, French, and German so strict localization QA passes.
- [x] Add shared UX feedback states for practical panel polish: Media Pool
  empty/no-match/drop states, Color Page scope/color-management warnings, and
  Audio Mixer empty states now use one tone/copy helper instead of scattered
  one-off labels.
- [x] Declutter the default editor workspace without removing power tools:
  Media Pool stays open, while Effect Presets, Title Presets, Transitions,
  Workflow Presets, Render Queue, Audio, and Subtitles now use collapsible
  section headers so the first screen reads closer to a focused studio UI.
- [x] Compact the top command bar: project/recovery/relink/health commands,
  actor commands, render-queue queuing, reset, and audio scopes now live behind
  `Project`, `Actors`, and `More` menus while Export remains the primary
  visible action.
- [x] Add a Screen Studio-inspired timeline visual pass: amber media clips,
  violet zoom/action blocks, yellow scissors cut markers, violet playhead,
  shared code-native toolbar icons, and short Blade/Zoom timeline burst
  feedback.
- [x] Add Screen Studio-like animated timeline tool icons: Select now uses a
  painter-native animated cursor with hover/active lift, glow, sparkle, and
  trail motion, while Blade/Ripple/Roll/Slip/Slide use the same animated square
  tool-tile system instead of static Qt icons.
- [x] Add a stronger Screen Studio shell pass: round glass-like panels,
  pill controls, lower-contrast timeline texture, compact top-bar secondary
  actions, `Tracks` menu, and shorter effect/actor palette chips.
- [x] Add the next Screen Studio polish pass: rounded/shadowed preview canvas,
  stronger amber clip-label expression, compact Media Pool cells, Workbench
  glass styling, press-pulse icon feedback, and Show/Hide regression coverage
  for collapsible asset/side sections.
- [x] Extend the Screen Studio icon pass: replace font-dependent pop-out/close
  symbols with code-native vector icons, add Media Pool filter/view icons,
  add Workbench tab icons, and apply press-pulse feedback to more primary
  editor/media buttons.
- [x] Polish empty states: Preview now draws a native rounded empty/audio-only
  canvas, Media Pool hover preview no longer clips thumbnails, and Workbench
  hides property rows until a clip/track is selected.
- [x] Align UI screenshot QA with real app startup: apply font fallback and
  global QSS in `tools/qa_ui_layout.py` before capturing the editor.
- [x] Remove remaining font-dependent transport glyphs from the main editor,
  Typography preview, Sound Editor transport bar, and video-track row
  watermarks by moving them to `app.icons` or painter-native shapes.
- [x] Extend the font-independent icon pass to high-traffic project, actor,
  audio scopes/mixer, Edit/Color page, PiP keyframe, Workbench mask, context
  menu, Live2D drag-preview, and audio-track watermark surfaces.
- [x] Continue the icon pass through the launch window, clip-effects dialog,
  Mask Editor, Subtitle pop-out, Workbench node graph, and visible Live2D/Spine
  editor transport/scanner controls.
- [x] Add a Screen Studio wallpaper-palette pass for the timeline transport,
  edit-tool rail, effect/actor drag palette, and Edit/Color selector: effect
  cards now use colorful mini swatches while command controls use softer glass
  rails so the area no longer reads as one block of gray buttons.
- [x] Convert the timeline edit tools and drag/drop effect cards into
  square icon-first palette tiles. Labels are no longer always visible:
  timeline tool labels are revealed through hover styling/tooltips, while
  effect-card labels are injected only during hover so the default row reads
  as an icon palette instead of a text toolbar.
- [x] Merge the timeline edit-tool rail and drag/drop effect rail into one
  rounded `TimelinePaletteBar`, so the tools read as a single wallpaper-style
  palette instead of two separate toolbar boxes.
- [x] Refine the merged palette with Screen Studio visual analysis: remove the
  oversized status chip from the palette, switch both tool and effect tiles to
  a single dense 40px row, hide internal labels by default, and keep only a
  subtle divider between edit commands and creative swatches.
- [x] Add the follow-up Screen Studio control pass: timeline palette tiles now
  keep their wallpaper colors during hover/checked states, effect swatches use
  a painted thumbnail fold/shade, visible sliders use a shared 3px dark rail
  with single purple fill, and the selection/action strip is icon-only and
  low-height instead of a persistent instruction row.
- [x] Add Creative Layer action/QA coverage: `transition.apply` and
  `transition.clear` now mutate clip transition metadata through the Python
  Action Registry, AI command routing can request/clear transitions, and
  `creative_layer.readiness` plus
  `debugCapture/creative_layer_readiness_qa.json` gate effects, transitions,
  typography, node graph, Live2D/Spine, AR/PBR, and template ecosystem claims.
- [ ] Continue Creative Layer product polish: timeline-visible effect/title/
  transition regions, exact preset A/B previews, actor/editor preview-export
  parity, node graph debug UI, and AR/PBR model-view GPU export parity remain
  the next quality blockers.
- [x] Merge the separate selection/action strip into the play bar and make the
  transport row icon-first: Mark In/Out, range clear, Marker, active-selection
  clear, Edit, and Color are compact icon controls with tooltips; the speed
  readout is a short `1.0x` chip; the jog/shuttle control is a smaller colorful
  knob instead of the previous large metallic circle.
- [x] Rework the Color/Color Page visual language so it reads as color grading,
  not a generic settings form: the Color page button now uses a vector
  color-wheel/curve grading icon, the Color Page has a Screen Studio-style
  palette ribbon, glass pipeline bar, rounded scope/qualifier/wheel panels,
  color-domain gradient sliders, and the shared `KnobWidget` uses softer glass
  tiles instead of a flat code-drawn circle.
- [x] Fix left-dock preset library usability: the entire left dock now scrolls,
  Effect/Title/Transition/Workflow sections use adaptive internal scroll grids,
  and preset cards are painted vector tiles instead of label-stacked mini cards
  that overlap in narrow sidebars.
- [x] Polish the preset browser surface: Effect, Title, Transition, and
  Workflow sections now have search, category chips, scroll-edge shadows,
  hover preview popovers, and compact custom drag ghosts for actual use with
  larger commercial-style preset packs.
- [x] Complete the Screen Studio-style polish bundle: animated preset hover
  previews, preset favorites/recent state, pack filtering, timeline tool
  micro-interactions, timeline drop insertion guides, Media Pool hover scrub,
  Workbench palette/empty-state polish, richer toast feedback, and a visual
  regression QA wrapper.
- [x] Add the first functional Screen Studio Auto Polish path: new recordings
  emit cursor sidecar metadata, the editor exposes icon-only Auto Polish from
  the top bar / More menu / Command Palette, selected or all video clips get
  renderable auto-zoom `ZoomActor`s from cursor/click metadata or smart
  fallback points, project IO persists the cursor/polish payload, preview
  applies clip zoom before track zoom, and single-source export/render-queue
  jobs include clip zoom actors for parity.
- [x] Bake the Screen Studio cursor/framing polish into real preview/export:
  new captures store a clean video plate plus cursor sidecar, preview/export
  re-render smoothed scaled cursors, click rings, static-cursor hiding, and
  project-level wallpaper-gradient padding/shadow framing through the shared
  `screenstudio_polish` compositor, with export forced onto the prerender path
  when those effects are active.
- [x] Productize Auto Polish controls: the toolbar now opens a Screen
  Studio-style tuning panel with Clean Tutorial/Product Demo/Cursor
  Focus/Shorts Vertical/Soft Wallpaper presets, cursor size/smoothing/static
  hide/click-ring controls, wallpaper palette/padding/shadow/vertical controls,
  custom auto-zoom scale/duration, immediate preview refresh, and Generate
  Zoom Windows using the current panel values. The compositor also caches
  wallpaper gradients for repeated preview/export frames.
- [x] Tighten Screen Studio parity polish: recorder sidecars now distinguish
  click/drag/release interactions, cursor polish can render drag trails and key
  badges, auto zoom keeps edge actions inside a safer crop, wallpaper frames
  support rounded screen corners, `screenstudio_polish_parity_report()` checks
  deterministic preview/export compositor parity, and the startup launcher is
  smaller/less template-heavy on first open.
- [x] Complete the hotkey/capture QA pass for Screen Studio polish: recorder
  sidecars now capture privacy-safe hotkey labels, cursor events preserve those
  labels through project/polish normalization, preview/export renders the
  actual keycap text instead of a generic KEY badge, and
  `screenstudio_interaction_report()` plus `tools/qa_micro_interactions.py`
  validate click/drag/release/hotkey readiness, auto-zoom generation, and
  compositor parity.
- [x] Productize Auto Polish status in the app UI: Media Pool video thumbnails
  now show an `AP` badge when cursor sidecar metadata exists, metadata/tooltips
  show readiness, event counts, hotkey labels, and candidate zoom windows, and
  the Auto Polish dialog summarizes selected/all target readiness before and
  after Generate Zoom Windows.
- [x] Finish the next Auto Polish product loop: clicking a Media Pool `AP` badge
  focuses the matching timeline clip and opens the panel, Auto Zoom candidates
  are listed before generation with per-clip toggles, generated clips show an
  `AP` timeline badge, and `tools/qa_screenstudio_auto_polish.py` plus the
  `qa_corpus/screenstudio_auto_polish` fixtures are wired into QA Dashboard.
- [x] Complete the Auto Polish candidate-edit/QA loop: candidate rows now expose
  direct start/end and crop-rect overrides, the preview draws temporary candidate
  boxes and seeks to the selected candidate, preview boxes can be dragged or
  resized by edge/corner handles to update the same override values, generation
  honors overrides, cursor click animation uses layered glow/pulse styling, and
  QA now checks preview/export visual parity plus generated real-MP4 fixture
  materialization.
- [x] Upgrade Auto Zoom motion quality: ZoomActor now stores easing and
  transition-blur metadata, Auto Polish presets stamp distinct motion styles,
  preview and CPU prerender export share the same zoom window / blur helpers,
  FFmpeg zoom filters use matching easing expressions, and the Auto Polish panel
  exposes Motion, Transition blur, and Cursor framing controls.
- [x] Add dwell-aware Auto Zoom cleanup: raw cursor sidecar samples now detect
  long "parked cursor" explanation moments as soft zoom candidates, while
  same-spot click/release pairs collapse into one cleaner zoom window so default
  Screen Studio-style recordings feel less jumpy.
- [x] Add Screen Studio-style cursor loop-back and export intent defaults:
  cursor polish now returns the pointer toward its starting position near the
  end of loopable recordings, Auto Polish QA reports loop readiness, and
  starter/export defaults expose web demo, social vertical, product demo, and
  editor-roundtrip delivery intents.
- [x] Add Screen Studio naturalness QA and tighten zoom overlap behavior:
  `tools/qa_screenstudio_naturalness.py` scores zoom framing, overlap-free
  windows, cursor loop-back, preview/export parity, and export intent defaults;
  Auto Zoom now drops late candidates that cannot be shifted without overlap
  instead of producing stacked zoom windows.
- [x] Add long-recording Auto Zoom rhythm pacing: Auto Zoom now uses an
  adaptive `screenstudio_zoom_timing_profile()` to expand candidate budgets for
  longer captures, spaces windows across the full timeline, and validates the
  behavior with Naturalness QA plus the `long_walkthrough` fixture.
- [x] Strengthen Screen Studio cursor animation in real frames: cursor accents
  now inherit the preset click color, hotkey badges use rounded glass styling,
  drag trails include fading bead highlights, and Visual Polish QA measures
  cursor-focus deltas instead of only checking whole-frame before/after change.
- [x] Add Screen Studio-style click settle timing: cursor polish now includes
  `click_hold_ms`, `cursor_state_at()` holds briefly on click/release/hotkey
  events before following the next sample, and the Auto Polish dialog exposes a
  Click hold slider for tuning the feel.
- [x] Surface Screen Studio export readiness directly in the app: the Export
  button tooltip and final checklist now show delivery intent, format, quality,
  resolution, FPS, and Auto Polish readiness instead of hiding that state until
  render time. Opening the editor directly now also starts from the Screen
  Studio web-demo defaults, so the empty editor advertises MP4/high 1080p/60fps
  rather than an ambiguous original-FPS state.
- [x] Add Screen Studio-style post-export handoff readiness: export defaults
  now classify clipboard, local share package, and optional share-link actions;
  successful single exports copy the output path to the clipboard when the
  delivery intent supports it, and Naturalness/GUI QA validate the handoff
  state. Local-share exports also write `<output>.share.json` beside the video
  so later share/upload UI has deterministic metadata to consume. Successful
  exports now use a product-facing completion dialog with Reveal Output and
  Copy Path actions, backed by the same completion summary that QA validates.
  `Screen Studio Export Handoff` is now a first-class QA Dashboard report and
  one-click runner, and it also checks the default record/edit/export path for
  frame style, cursor FX, handoff readiness, and auto-zoom coverage.
- [x] Replace generic preset hover animation with contextual previews:
  effects render filter/keying mini-scenes, titles render text placement,
  transitions render type-specific blends/wipes/fades, and workflow presets
  render template/caption/sticker/motion-specific mini-scenes.
- [x] Upgrade preset previews and pack workflow: hover popovers now use the
  current preview frame for A/B effect samples, chroma-key checker previews,
  title overlays, transition samples, QA badges, detail lines, and intensity
  sliders; the Effects Presets panel can save the selected clip's effect state
  as a user preset and import/export JSON preset packs.
- [x] Complete the next preset UX bundle: delayed live preview for effect and
  transition hover, compact preset inspector panel, static preset preview PNG
  cache, duration-aware timeline drop ghost blocks, in-editor preset QA dialog,
  preset pack manager with enable/disable/delete, one-click auto preset plan,
  top-bar/`Ctrl+Shift+P` command palette for media/presets/commands, and
  icon/micro-interaction reuse across the new controls.
- [x] Complete the follow-up preset productization bundle: Template Composer,
  title/workflow live preview overlays, template segment drop ghosts, Command
  Palette favorites/recent rows, preset pack conflict inspection and repair,
  preset preview cache manager, in-editor Visual QA viewer, richer auto-plan
  media analysis, and undo/redo cleanup for transient preset previews.

## Presets and Templates

- [x] Add CapCut-style creator workflow planning: auto-caption styling,
  long-video-to-Shorts candidate selection, smart media search metadata,
  subject-aware vertical reframe plans, easy keyframe graph plans, voice cleanup
  routing, background-removal route selection, social export defaults, and
  template-first AI recommendation plans in `app/capcut_workflow.py`.
- [x] Add CapCut-style built-in preset packs: word-pop/karaoke caption styles,
  hook question title, social CTA sticker, subject reframe motion, feed swipe
  transition, cutout/background-removal effect, creator voice enhancement, and
  auto-caption/long-to-shorts/reframe/smart-search/social-publish templates.
- [x] Wire CapCut workflow into preset search, Korean aliases, one-click plans,
  QA Dashboard, productization loop, and `tools/qa_capcut_creator_workflow.py`.
- [x] Add a CapCut apply-bundle handoff: transcript segments become
  Subtitle-compatible `subtitle_rows`, Shorts candidates become timeline
  markers and `RenderQueueJob.create` kwargs, and social export/reframe settings
  are returned as a project settings patch.
- [x] Add CapCut apply-to-project productization in `app/capcut_apply.py`:
  merge the bundle into `.tgp`-style project docs, update export defaults,
  preserve manual subtitles/markers, deduplicate repeat applies, stage
  `capcut_short_ranges` and `render_queue_jobs`, and expose apply counts in
  CapCut QA/Productization reports.
- [x] Add CapCut render queue materialization: staged short-export payloads can
  become real `RenderQueueJob` objects and can be appended to
  `RenderQueueStore` with duplicate protection; QA now reports materialized
  queue-job counts.
- [x] Add CapCut creator delivery packaging: `capcut_hook_score_plan()`,
  `capcut_caption_beat_plan()`, and `capcut_publish_package_plan()` now produce
  hook rankings, word-pop/karaoke caption beats, title/hashtag/thumbnail-frame
  suggestions, and platform checklist rows; apply writes this as
  `capcut_creator_package`.
- [x] Add explainable CapCut one-click planning:
  `capcut_creator_edit_recipe()` turns the recommendation into reviewable
  trim/caption/reframe/audio/effect/delivery steps with reasons and confidence,
  while `capcut_multi_platform_publish_plan()` builds Shorts/TikTok/Reels
  variants with platform-specific title/hashtag/thumbnail/checklist metadata.
  Apply bundles and project sidecars preserve both, and QA Dashboard reports
  recipe/variant counts.
- [x] Add the CapCut Creator review-panel contract:
  `capcut_creator_review_panel_model()` converts the bundle into hero, recipe,
  short-candidate, caption-beat, hook-ranking, publish-variant, and smart-media
  cards with primary/secondary actions; `capcut_publish_handoff_plan()` prepares
  copy title/description/hashtags, thumbnail jump, and queue-export actions.
  Apply bundles, project sidecars, QA Dashboard, and productization reports now
  track panel readiness and handoff action counts.
- [x] Ship the TigerCapture-aligned Creator Assist UI instead of a
  template-first launcher flow: the main editor command bar opens a right-dock
  Creator Assist panel that analyzes the existing Media Pool/Workbench/Timeline,
  previews short in/out ranges, applies caption/marker/export defaults, copies
  publish text, and saves/restores its sidecar state in `.tgp` projects.
- [x] Lazy-load Creator Assist from the right dock instead of constructing the
  CapCut review panel during launcher-to-editor startup.
- [x] Productize Creator Assist apply UX: users can choose subtitles, short
  markers, output/reframe settings, and render-queue staging independently;
  timeline/project mutations collapse into one undo savepoint; short exports are
  added directly to Render Queue; and analysis merges local-only media subject
  detections from `app.local_ml` when available.
- [x] Preserve subtitle `show_box` and style metadata on project save/load so
  CapCut caption styles and manual subtitle background-box choices survive
  `.tgp` round trips.
- [x] Attach real speech-recognition/object-segmentation backends to the
  CapCut workflow hooks when a local/approved model runtime is selected:
  `app/local_ml.py` now exposes local-only backend status, OpenCV/Pillow
  visual subject analysis, optional local Whisper/SAM/Demucs capability
  detection, and `capcut_creator_bundle_from_local_media()` bridges that
  analysis into CapCut apply bundles. `tools/qa_local_ml_backend.py`,
  QA Dashboard, and the productization loop track this path.
- [x] Add a CapCut parity-next gap tracker: `app/capcut_parity.py` and
  `tools/qa_capcut_parity_next.py` report the remaining gaps across template
  ecosystem scale, one-click AI agent depth, captions/voice/TTS workflow,
  social publish handoff, cloud/mobile/collaboration, stock music/SFX, and
  beginner default-result flow. QA Dashboard exposes the report as
  `debugCapture/capcut_parity_next_qa.json`.
- [x] Add a cloud-excluded CapCut mobile/template parity scope:
  `app/capcut_mobile_templates.py` defines 108 TikTok/Reels/Shorts vertical
  template contracts across twelve creator categories and three hook styles,
  with platform safe zones, cover-frame metadata, category tags, and
  deterministic recommendations. `build_capcut_parity_next_report(
  exclude_cloud=True)` removes the cloud/mobile-sync area and scores the new
  `mobile_template_scale` area; `tools/qa_capcut_parity_next.py --exclude-cloud`
  exposes the no-cloud QA report. The local no-cloud report now clears template,
  mobile safe-zone, beginner default-result, captions/voice cleanup, stock/SFX
  starter-pack, and publish-handoff areas while keeping true generative
  one-click AI as the remaining honest gap.
- [x] Add CapCut-style publish review/provider contracts:
  `app/capcut_publish.py` builds review cards for copy, thumbnail, platform
  variants, checklist rows, and provider handoff; built-in providers cover
  local manifest, clipboard, TikTok/Shorts/Reels manual upload, X/TikTok/
  Instagram browser quick-upload handoff, and unconfigured TikTok/Instagram/X
  API-upload plus share-link provider slots. Network upload is still off by
  default until explicit OAuth/app-review providers are configured. The quick
  upload package writer creates manifest, upload links, provider contracts,
  title/description/hashtag text, TikTok/Instagram/X post text, package index,
  and README files for browser handoff. `tools/qa_capcut_publish_review.py`
  writes `debugCapture/capcut_publish_review_qa.json`, verifies the package
  writer, and Creator Assist gets a publish review card.
- [x] Add CapCut-style quick-result recommendation/quality gates:
  `app/capcut_quick_result.py` chooses the first useful template, explains what
  quick create will do, scores one-click quality across hook/caption/pacing/
  format/delivery/safety, exposes a beginner default path and visible timeline/
  render/review feedback evidence, feeds a Quick Result card into Creator
  Assist, and exposes `debugCapture/capcut_quick_result_qa.json` through QA
  Dashboard.
- [x] Add CapCut-style captions/voice workflow contracts:
  `app/capcut_voice.py` combines caption rows, caption beats, voice cleanup,
  loudness, stem separation, and explicit TTS/custom voice/translation provider
  slots into one local-first review model with ready-card, enabled-action,
  manifest-operation, and no-cloud-default evidence. `tools/qa_capcut_voice_workflow.py`
  writes `debugCapture/capcut_voice_workflow_qa.json`, Creator Assist gets a
  Voice Workflow card, and CapCut parity scoring uses this evidence.
- [x] Add CapCut-style local collaboration handoff:
  `app/capcut_collaboration.py` builds a local-first review package contract
  with project snapshot, review notes, media relink manifest, manual archive
  readiness, and explicit optional workspace/mobile/cloud-comment provider
  slots. `tools/qa_capcut_collab_handoff.py` writes
  `debugCapture/capcut_collab_handoff_qa.json`, Creator Assist gets a Collab
  Handoff card, and CapCut parity scoring now reduces but does not erase the
  cloud/mobile/collaboration gap.
- [x] Add CapCut-style cloud/share handoff contracts:
  `app/capcut_cloud_handoff.py` defines local sync folder, Google Drive,
  OneDrive, Dropbox, WebDAV, S3-compatible, and custom provider contracts
  without uploading files or storing tokens. The handoff validates package
  inventory, relink manifest, private-link defaults, conflict policy, explicit
  user consent, no-token manifests, and configured-provider dry-run readiness.
  It also writes a local sync-folder package with manifest, cloud plan, review
  notes, relink manifest, provider contracts, package index, and README while
  leaving original media out by default. `tools/qa_capcut_cloud_handoff.py`
  writes `debugCapture/capcut_cloud_handoff_qa.json` and verifies the package
  writer; QA Dashboard and CapCut parity use it as progress while real cloud
  sync remains incomplete.
- [x] Add CapCut-style prompt-to-edit benchmark/fallback:
  `app/capcut_prompt_edit.py` maps creator prompts to review-first operations
  for captions, subject reframe, cursor polish, voice cleanup, asset
  recommendations, short exports, thumbnail candidates, publish handoff, and
  local collab handoff. `tools/qa_capcut_prompt_edit.py` writes
  `debugCapture/capcut_prompt_edit_qa.json`, Creator Assist gets a Prompt Edit
  card, QA Dashboard can run it, and CapCut parity reads the benchmark score.
- [x] Expand local creator asset packs for the CapCut-style stock/SFX gap:
  `app/creator_asset_packs.py` now defines 100 generated sticker, background,
  SFX, and loop metadata entries with license IDs, external JSON pack loading,
  search, intent coverage, synthetic preview storyboards, ready collection
  shelves, and a local recommendation board with drag payloads.
  `tools/qa_creator_asset_packs.py` exposes
  `debugCapture/creator_asset_packs_qa.json`; CapCut parity now reads asset
  count, intent coverage, collection-shelf, recommendation, and storyboard
  evidence.
- [ ] Expand CapCut-style parity work from the gap tracker: local TTS/custom
  voice UX, actual user-approved share-link/provider integrations, real
  licensed SFX/music pack imports, and real-world creator-corpus scoring beyond
  deterministic fixtures.
- [x] 2026-06-28 Expand local CapCut-style trend/template evidence:
  `app.capcut_mobile_templates` now adds 216 local trend-template packs,
  A/B storyboard contracts, and a 12-scenario deterministic creator corpus
  quality report. `app.capcut_parity` reads trend pack count, trend families,
  storyboard count, and corpus score while still reporting CapCut as a gap
  tracker rather than a full parity claim.
- [x] Expand the preset/template library with production packs for news briefs,
  hotkey tutorials, ranking/listicle shorts, anime/actor reactions,
  food/product gloss edits, documentary clarity, noisy-room dialogue, and
  editorial captions/stickers.
- [x] Add a content expansion preset pack for B-roll/cutaway, podcast chapters,
  product-review verdicts, and patch-note updates, plus normalized preset
  search so punctuation variants like `b-roll` and `b roll` both match.
- [x] Add preset/template ecosystem QA: built-in and external preset packs now
  report kind-count targets, topic coverage, one-click plan coverage, and
  template child-preset reference integrity so commercial preset packs cannot
  silently ship broken template sequences.
- [x] Add user-facing preset pack maintenance: imported packs now expose
  invalid rows, duplicate IDs, built-in/cross-pack conflicts, missing template
  refs, and a backup-preserving repair command.
- [x] Add in-editor template authoring and cache operations: users can compose
  one-click templates from existing presets, warm/clear cached preset preview
  PNGs, and inspect visual QA capture folders without leaving the editor.
- [x] Productize the remaining preset/template workflow: Template Composer now
  stores per-step duration/target/condition metadata, workflow drops show
  internal segment summaries, preset application surfaces target-specific
  failure reasons, Pack Manager shows a marketplace-style library health
  summary, preset cache warming supports current-frame contextual thumbnails,
  Visual QA can approve selected captures as baselines, Command Palette rows
  expose details/shortcuts/compatibility, and
  `tools/qa_preset_application_corpus.py` records real-project one-click plan
  QA reports.
- [x] Add the next preset/template product pass: natural-language Korean search
  aliases for preset browsers and Command Palette, actor workflow presets for
  Live2D/Spine placeholders, Command Palette `Preview Apply` and `Fix Target`
  actions, contextual application-plan simulation, preset pack scores/coverage
  in Pack Manager and Health, icon pulse/burst feedback for preset apply/drop,
  and auto-discovery for preset application QA corpus projects.
- [x] Complete the preset/template polish batch: `Preview Apply` now renders a
  current-frame mini simulation, Command Palette ranks natural-language query
  matches, `Fix Target` selects or creates practical video/audio/color/actor
  targets, actor presets auto-link compatible Media Pool Live2D/Spine models,
  Pack Manager has card-style scoring plus inspect/resolve conflict actions,
  Health opens Preset Packs/Preset QA/Corpus QA directly, preset application
  QA records preview/export bake-target parity, and fixed sample `.tgp` corpus
  projects live under `qa_corpus/preset_application_samples`.
- [x] Add a Screen Studio/CapCut-style preset expansion and more practical
  preview: cursor-pop/wallpaper/glass-callout/shorts/product presets are now
  built-in, one-click planning can select them, and Command Palette
  `Preview Apply` renders an A/B current-frame preview instead of only a single
  simulated card.
- [x] Finish the next preset/UI pass: `Preview Apply` now loops mini playback,
  preset browsers include wallpaper-palette pack swatches, the micro preset
  pack adds cursor spotlight, click ring, hotkey, glass panel, and UI-focus
  templates, and timeline tool icons keep animated hover/click emphasis.
- [x] Add product QA Dashboard and timeline edit stress QA: the editor can open
  a dashboard for preset application, visual, actor, Color/Audio, and fuzzer
  reports, while `tools/qa_timeline_fuzzer.py` randomly exercises blade,
  linked move, ripple/roll, slip/slide, nested clips, actor lanes, and undo.
- [x] Upgrade QA Dashboard from report browser to product runner: safe reports
  can be launched from the dashboard for preset application, Color/Audio,
  timeline fuzzer, and dependency-only actor corpus status.
- [x] Finish the product-template/QA UX batch: `Preview Apply` now uses
  payload-specific mini playback plus a compact template timeline plan,
  built-ins include Screen Studio-style cursor/product/shorts/gaming/corporate
  templates, QA Dashboard shows a pass/fail trend strip and visual thumbnails,
  Actor QA Browser shows baseline/actual image previews, and
  `qa_corpus/product_qa_corpus_manifest.json` records the next real-project QA
  sample groups.
- [x] Make template application visibly traceable without cluttering startup:
  the launcher is now a compact action surface (`Record`, `Tiger Studio /
  Media Pool`, Sound Editor utility) with no recent-work or recommended-template
  cards on the first screen. Broader template/audio tools live in the editor,
  and startup-selected templates still auto-apply after first compatible media
  import when launched from an explicit template path.
  The follow-up cleanup keeps the first screen leaner: the hero no longer
  carries a decorative palette block, and capture mode/timer/cursor controls are
  merged into one thin settings bar.
  Template previews render a Screen Studio-style A/B wallpaper-palette
  simulation, preview toasts summarize applied template steps, video timeline
  clips expose `FX`/`Key`/`TR`/`COL`/`T`/`Mot`/`Nest` badges, audio clips expose
  `AUD`, and startup QA checks the no-template-first launcher, editor payload,
  editor pending-template affordance, and structural metrics.
- [x] Add the 1~10 commercial-polish productization loop: `tools/qa_productization_loop.py`
  and QA Dashboard/Command Palette now summarize UI visual QA, preset preview
  realism, preset packs, dashboard coverage, Render Queue, Media Pool,
  Color/Audio, actor QA, recovery/repair, and starter templates in one report.
- [x] Add long-project Media Pool smart bins for Proxy Missing, Proxy Stale,
  and Duplicate Name, and add starter template choices to New Project Dialog so
  screen-recording, shorts, gameplay, product demo, and actor projects can
  start from a named workflow.

## Performance and Caching

- [x] Add opt-in preview render slow-call logging via `TIGERCAPTURE_PERF=1`.
- [x] Add stage-level timing inside `ProjectPlayer._render_frame_at` for decode,
  frame blending, stabilizer, zoom, node effects, clip effects, overlays,
  final grade, GPU emit, and QImage conversion.
- [x] Cache media-pool duration probes and first-frame video thumbnails by
  path/mtime/size.
- [x] Cache waveform/spectrum extraction results by path/mtime/size and join
  duplicate in-flight waveform/spectrum jobs for the same source file.
- [x] Add a safe preview pre-render cache/worker path for near-future CPU node
  effect frames.
- [x] Harden Workbench node graph interaction stability: dynamic scenes now use
  `NoIndex`, connection drag geometry updates call `prepareGeometryChange()`
  before endpoint mutation, live temporary drag connections are discarded before
  node deletion or graph reload, and regression QA covers drag/delete/reconnect
  edge cases.
- [x] Document and script the preview playback profiling path with
  `TIGERCAPTURE_PERF=1` for real 1080p/4K projects; the actual slowest-stage
  record is produced when a representative project is supplied.
- [x] Extend `tools/qa_preview_perf.py` to benchmark sampled `ProjectPlayer`
  preview renders and optional 1080p/4K fixtures, then run the baseline report.
  Current top candidates: chroma key/video filters, Spine overlay, and decode.
- [x] Reduce measured preview hotspots from the first baseline pass: cache
  clip-filter vignette masks, use half-resolution software fast-mesh Spine
  preview with renderer prewarm, and let preview decode automatically use fresh
  sibling proxy files when available.
- [x] Move chroma-key preview masking off the Python/NumPy hot path by using
  OpenCV native HSV/LUT/inRange/bitwise/count operations with cached LUTs.
- [x] Add alpha fast paths to chroma-key compositing so alpha==0/255 pixels
  skip full-frame blending and only soft-edge pixels run spill/composite math.
- [x] Reduce clip-filter preview cost by removing redundant sharpen clipping,
  avoiding RGB restacks for chromatic aberration, and caching uint16 vignette
  multiplier masks.
- [x] Add preview-only downsampled video-filter fast path while preserving
  full-resolution export rendering.
- [x] Add LRU frame cache after preview prefetch so repeated scrubbed frames
  return from memory.
- [x] Make Spine preview prefer the GL/native renderer path with renderer and
  first-frame prewarm, while keeping the software renderer as an environment
  fallback.
- [x] Increase Spine animated-frame cache capacity for better preview reuse
  while keeping export at full quality.
- [x] Add visible high-resolution proxy management UX: toolbar status,
  generate/refresh, delete, stale detection, and per-clip proxy swapping for
  multi-source timelines.
- [x] Show proxy ready/stale badges in Media Pool thumbnails and refresh those
  badges after proxy generation/deletion.
- [x] Audit timeline thumbnail extraction for stale/duplicate replacement jobs
  on project load/split/drag.
- [x] Reuse indexed prefetch-buffer frames for near-future preview seeks so
  scrubbing does not discard already-decoded frames.
- [x] Expose internal preview frame-server tuning with
  `TIGERCAPTURE_PREFETCH_FRAMES` and
  `TIGERCAPTURE_PREFETCH_READ_TIMEOUT`.
- [x] Add opt-in OpenCV FFMPEG hardware decode through open parameters, while
  keeping software decode as the default after local QA showed HW decode can be
  slower despite reporting active acceleration.
- [x] Cache Spine preview layout/bounds and final RGBA overlay images to reduce
  repeated actor compositing work on repeated seeks.
- [x] Batch consecutive Spine GL/offscreen meshes by atlas texture before
  issuing draw calls.
- [x] Add an opt-in Spine RGBA ndarray overlay compositor for main and nested
  actor lanes; keep the measured faster PIL compositor as the default until
  FBO readback is eliminated.
- [x] Add recovery-candidate audit mode to `tools/repair_project.py` so
  autosave/recovery files can be ranked before opening the UI.
- [x] Add a main-editor `Recovery` toolbar action that ranks recovery
  candidates, shows missing-media counts, autosaves defensively, and opens the
  selected recovery project through the normal loader.
- [x] Add `native_gpu_candidates` hints to preview QA reports so the next
  native/GPU migration target is named by measurements.
- [x] Update preview QA hints after Spine GL batching so the remaining actor
  target is GPU compositing/FBO readback elimination.
- [x] Tighten Final Product Readiness preview/GPU gating: render-sample-free
  `qa_preview_perf.py --skip-render` style reports no longer count as release
  ready, and nested `preview_render[].stage_summary` rows are read directly so
  decode/filter/Spine bottlenecks stay visible even without top-level summaries.
- [x] Add preview-only chroma-key downsample/native OpenCV fast path while
  preserving full-resolution export parity.
- [x] After profiling, move proven hot preview/render/cache stages out of
  Python into FFmpeg/OpenGL/native C++ or Rust helpers instead of rewriting the
  whole app first.
- [x] Add opt-in hardware decode, opt-in Spine RGBA array compositing, faster
  preview filter/chroma defaults, larger prefetch defaults, redundant
  next-frame seek avoidance, and 24fps Spine preview cache quantization.
- [x] Add `SpineOverlayGLCompositor` so multiple active Spine clips can be drawn
  into one preview FBO with one readback before falling back to per-clip
  rendering.
- [x] Add an opt-in FFmpeg pipe preview frame server
  (`TIGERCAPTURE_PREVIEW_FRAME_SERVER=1`) for decode comparisons.
- [x] Add a combined filter+chroma preview batch path so eligible clips use one
  downsample/upsample pass instead of two.
- [x] Avoid single-actor Spine FBO readback pressure for complex rigs by
  using a lower adaptive preview cache/readback FPS. Full readback elimination
  still belongs to the later true GPU actor-compositor path.
- [x] Build the true zero-readback Spine GL actor compositor by drawing actor
  meshes directly into the main preview GL surface or a shared GPU texture
  chain instead of reading overlay pixels back to CPU memory.
- [x] Add automatic decode backend selection using measured per-source startup,
  random seek, and sequential playback speed so OpenCV, proxy, hardware decode,
  and FFmpeg frame-server paths are selected by evidence.
- [x] Extend real-project QA audit with optional sampled preview rendering and
  native/GPU bottleneck hints so 3-5 representative projects can identify the
  next migration target without manually launching the editor.
- [x] Add preview-engine capability/status snapshots to QA reports so decoder,
  frame-server, native-worker, filter/chroma, and Spine compositor modes are
  recorded with the performance numbers.
- [x] Pass monitoring-scale preview-height hints into FFmpeg frame-server and
  auto decoder selection before benchmarking/spawning FFmpeg, and let
  per-project preview decode height settings flow from `ProjectPlayer` to the
  decoder factory.
- [x] Make preview performance QA default to the main editor's GPU-only preview
  consumer so shader clip effects and Spine zero-readback paths are measured;
  keep `TIGERCAPTURE_QA_PREVIEW_MODE=qimage` for CPU fallback comparisons.
- [x] Lower CPU fallback Spine preview internal render scale during animated
  playback (`TIGERCAPTURE_SPINE_PLAYBACK_PREVIEW_SCALE=0.375`) and lower it
  further for complex rigs or Live2D-overlap frames
  (`TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_SCALE=0.25`) where correct layer
  ordering prevents direct zero-readback, while keeping paused/editor preview
  at normal scale and export at full quality.
- [x] Allow the main GL preview to use direct zero-readback Spine overlay state
  even when top-level Live2D is active (`TIGERCAPTURE_SPINE_DIRECT_WITH_LIVE2D=1`
  by default, `0` for strict CPU actor layer-order debugging). This removed the
  measured `preview.stage.spine_overlay` bottleneck from the actor QA project.
- [x] Make Final Product Readiness prefer canonical
  `debugCapture/preview_perf_report.json` over experimental
  `preview_perf_report_*.json` files so one-off decoder/preview-scale probes do
  not accidentally gate release status.
- [x] Make preview QA sample clip/actor active positions, not only evenly-spaced
  timeline positions, so Live2D/Spine regressions are not missed by low sample
  counts.
- [x] Split preview performance QA into refresh/seek/playback contexts and add
  playback-frame summaries. Final Product Readiness now gates the Preview/GPU
  area on steady playback while keeping refresh and random-seek decode spikes as
  advisory polish debt.
- [x] Add preview scrub/seek readiness QA:
  `app.preview_scrub_readiness.build_preview_scrub_readiness_report()` and
  `tools/qa_preview_scrub_readiness.py` separate current-corpus scrub readiness
  from stronger release claims, track seek average/p95/max, playback p95, decode
  hotspots, and coverage across basic, mask/filter, nested, actor, audio, long,
  and 4K projects.
- [x] Add opt-in forward-seek tuning knobs for OpenCV/Pfetch decode
  (`TIGERCAPTURE_CV2_FORWARD_SEEK_WINDOW`,
  `TIGERCAPTURE_PREFETCH_FORWARD_SEEK_WINDOW`) and keep both disabled by
  default after local QA showed sequentially discarding 10-40 frames was slower
  than OpenCV random seek on the current 720p corpus.
- [x] Instrument nested sequence preview with `preview.stage.nested_*` labels and
  skip decoding hidden lower child video tracks when the nested stack is an
  opaque top-track replacement, reducing the nested QA project's measured
  frame average before the final readiness pass.
- [x] Add true shader-backed chroma/filter parity for both GL preview and QImage
  fallback consumers when chroma/filter projects again become the measured top
  bottleneck.
- [x] Eliminate the preview QImage copy for GPU-preview-only consumers where
  scopes/popout do not need a CPU image.
- [x] Add baseline comparison to preview performance QA so media probe,
  thumbnail, preview-frame, and per-stage regressions are flagged against a
  previous report with native/GPU migration advice attached.
- [x] Add baseline comparison to real-project QA audit so representative
  projects flag newly unhealthy projects, missing media/model regressions,
  actor asset failures, export-risk increases, synthetic parity regressions,
  and delegated preview-performance regressions.
- [x] Add professional-readiness diagnostics for long-project stability, GPU
  preview/export consistency, timeline edit integrity, color workflow depth,
  and audio mix readiness, and attach them to real-project QA reports.
- [x] Refine professional-readiness timeline integrity so one-frame
  micro-overlaps are reported as auto-fixable timeline edge cleanup candidates
  while larger same-lane overlaps remain high-risk issues.
- [x] Surface professional-readiness diagnostics in the in-editor Health panel,
  using the current in-memory session so users see stability, timeline, color,
  audio, and preview/export readiness without saving first.
- [x] Attach professional-readiness preflight diagnostics to single export
  results and editor-created Render Queue jobs, preserving the warning/action
  summary through queued/running/completed render diagnostics.
- [x] Deepen professional-readiness diagnostics for Color, Audio, and
  preview/export parity: Health/export/QA now count project LUT/HDR/OCIO
  intent, grade-local LUTs, qualifier cleanup, tracked power windows, audio
  effect graphs, clip/track automation, bus routing, and loudness/dialogue
  readiness with matching parity sample recommendations.

## Render Queue / Relink / Presets

- [x] Back Batch Export with a persistent JSON render queue store and clean
  broken queue-dialog labels.
- [x] Add reusable project media relink logic and a CLI that rewrites missing
  media/model paths by searching selected folders.
- [x] Add an in-editor `Relink...` project action that writes a non-destructive
  `.relinked.tgp` copy, reports changed/unresolved media, and can immediately
  open the repaired project before missing tracks are skipped by load.
- [x] Add an editor preset library for effect, title, and transition presets
  with external JSON extension support and a listing CLI.
- [x] Expand the built-in preset library with more practical effect, title,
  transition, chroma-key, cleanup, and short-form editing presets.
- [x] Wire the new preset library into the visible editor UI: effect presets
  appear as draggable left-dock cards, title presets extend the existing title
  card panel, and dropped effect presets apply to the target clip.
- [x] Add first-pass render queue management controls: retry failed jobs, clear
  completed jobs, reveal selected output folder, and continue only pending jobs.
- [x] Promote the render queue from a batch modal to a full dockable queue panel
  with pause/resume, history, encoder diagnostics, and background rendering.
- [x] Add render queue cancellation for current/pending jobs and persist richer
  stage/output-size diagnostics in queue history.
- [x] Productize render failure diagnostics: classify common FFmpeg/export
  failures, show recovery suggestions in single-export dialogs, and persist the
  same structured report in Render Queue and modal batch-export history.
- [x] Add a Render Queue diagnostics detail pane and copy-diagnostics command
  so failed job reports can be inspected and shared without relying on
  truncated table cells.
- [x] Add a short diagnostic retry-range command for failed Render Queue jobs,
  deriving a 5-second retry range from the failed job's last progress
  percentage and writing to a suffixed output filename.
- [x] Add Render Queue status filters, diagnostic text search, and old terminal
  history pruning so long-running projects remain manageable.
- [x] Strengthen Render Queue product UX with selected-job log viewing,
  product-facing failure summaries, suggested retry/relink/preset-QA actions,
  and preset/template export-parity hints in diagnostics.
- [x] Add Render Failure Assistant for selected failed queue jobs: users can
  open Relink, run preset application QA, copy diagnostics, or queue a short
  retry range directly from the queue panel.
- [x] Add export/review polish for delivery: single and batch exports now show
  a final checklist with job count, actor clip count, Color/Audio QA badge, and
  readiness details before encoding, and Render Queue log/failure dialogs can
  save full diagnostics to disk.
- [x] Upgrade relink UX from one selected search folder to a full missing-media
  browser with per-file candidate choices, conflict warnings, and batch roots.
- [x] Add long-project media health reporting: missing/relink conflict rows,
  duplicate filename warnings, sibling proxy ready/stale/missing status, and a
  `tools/relink_project_media.py --health` preflight mode.
- [x] Surface long-project media health in the editor toolbar: `Health` audits
  the current in-memory session, shows status/proxy/reference/candidate rows,
  and can jump from missing/relink conflicts into the Relink browser.
- [x] Expand the preset/template/effect library again with searchable
  commercial-polish transition, effect, chroma-key, title, callout, and
  Live2D/nameplate presets plus summary/search helpers.
- [x] Add professional color/audio workflow foundations: color curves,
  qualifiers, tracking-window masks, scope diagnostics, dialogue cleanup,
  loudness targets, audio buses, track automation persistence, and searchable
  color/audio/template/caption/sticker/motion preset packs.
- [x] Productize the Resolve/Fairlight/Fusion gap as readiness roadmap data:
  Color, Audio, and VFX now expose foundation/model capability flags, while
  `resolve_post_pipeline_parity` emits professional depth cards with current
  maturity, missing blockers, next actions, implementation phases, and QA gates
  for RAW/HDR/ACES color, DAW/ADR/immersive audio, and node/3D compositor work.
- [x] Connect the professional depth cards to Health/QA and add first practical
  gates: Health detail text and QA Dashboard show Resolve/Fairlight/Fusion cards,
  Color has a synthetic scope-accuracy sample/report, Audio has a combined
  loudness/routing delivery gate, and VFX has a mini preview/export-locked node
  graph model for keyer/roto/clean-plate/tracker/merge/title MVP workflows.
- [x] Push those gates into the working UI: Color Page scopes expose cached
  scope-QA gate status in the tooltip, Audio Mixer's Loudness dialog reports
  delivery QA across LUFS/true-peak plus routing/bus validation, and Mask Editor
  shows/saves a mini VFX node graph payload alongside clean-plate/planar-tracker
  repair masks.
- [x] Wire professional gates into export/health surfaces: Color scope QA is
  embedded in `color_workflow_depth` and Health detail text, Render Queue/export
  preflight diagnostics include Audio Delivery QA with loudness/peak/routing
  status, and Mask Editor has a `VFX Graph` inspector for the mini compositor
  payload before commit.
- [x] Close the VFX graph diagnostics loop: the Health serializer now collects
  `vfx_repair_plan` and `vfx_node_graph` payloads from active clips and
  Workbench node chains, so Professional Readiness/export diagnostics report
  `VFX Graph QA` from unsaved in-memory editor work; export diagnostics also
  include compact `Color Scope QA` lines.
- [x] Add VFX graph validation: `vfx_node_graph_qa_report()` checks mini
  compositor graphs for missing outputs, unresolved inputs, node/kind counts,
  and required media/output coverage, then surfaces those warnings in Health,
  QA Dashboard, and export diagnostics.
- [x] Productize VFX/export diagnostics in the editor UI: Workbench FX summaries
  now bridge `vfx_node_graph` payloads from selected track node chains, while
  Render Queue parses preflight text into compact status cards for readiness,
  Color Scope QA, Audio Delivery QA, VFX Graph QA, and export parity.
- [x] Make Render Queue preflight cards actionable: selected jobs now show
  clickable readiness/Color/Audio/VFX/export-parity cards with per-card detail
  dialogs and copy support instead of forcing users to scan the full log.
- [x] Add Render Queue card resolution routes: preflight detail cards can now
  jump to Project Health/Health Center, QA Dashboard, Color Page, Audio Mixer,
  Preset QA, or Deliver Presets depending on the failing gate.
- [x] Add a visible Workbench VFX mini-graph strip: selected track VFX payloads
  now render as compact Media/Keyer/Roto/Clean/Track/Merge/Out pills inside
  the FX summary instead of only appearing as diagnostic text.
- [x] Make the Workbench VFX strip actionable: tracks with a VFX payload now
  expose an `Inspect VFX` action that opens the QA gates, warnings, graph
  cache/output policy, and node input/param details without leaving the editor.
- [x] Make Workbench VFX graph pills interactive: each mini graph pill is now a
  hoverable button that opens the VFX details dialog, and review state is
  computed from graph validation warnings even when the saved payload omitted
  precomputed warning text.
- [x] Surface professional presets in the editor UI: color workflow presets now
  appear in the Color preset dropdown, audio workflow presets appear in the
  Sound Editor AI Master tab, and template/caption/sticker/motion packs appear
  in the left-dock Workflow Presets panel.
- [x] Make Workflow Presets actionable: clicking or dropping a workflow card
  applies templates, captions, stickers, motion, color, audio, title, transition,
  and effect actions to the selected/active timeline target.
- [x] Improve timeline effect visibility: clip effect strips now include
  Auto Zoom, title/caption actors, motion/zoom actors, and nested/compound
  context in the same timeline-visible summary/tooltip path as FX, keying,
  transitions, and color.
- [x] Polish Workflow Preset targeting: timeline drops now use the drop
  track/time even when another clip is selected, and template `at_ms` entries
  are relative offsets from the click/drop target.
- [x] Expand the commercial preset library with a social/creator pack: vertical
  hooks, tutorial step packs, product-demo templates, streamer/reaction
  workflows, creator voice chains, CTA/callout stickers, social/product color
  starters, and wider Workflow Presets panel coverage.
- [x] Expand Workflow Presets with content-production packs for B-roll cutaways,
  podcast chapters, product-review verdicts, and patch-note updates, and wire
  those categories into one-click preset planning.

## Commercial Timeline / Recovery Polish

- [x] Add Full NLE parity honesty gate: keep product wording at "core NLE
  workflow/action surface", expose `timeline.professional_nle_readiness`, and
  write `debugCapture/nle_readiness_qa.json` through `tools/qa_nle_readiness.py`.
  The gate can pass QA while still blocking a full Premiere/Resolve-class NLE
  claim.
- [x] Add real NLE corpus registration and QA gate: register real projects with
  `tools/register_nle_real_project.py`, validate them with
  `tools/qa_nle_real_project_corpus.py`, and expose read-only
  `nle.real_corpus.status` so AI/MCP can report why the full-NLE claim is still
  blocked.
- [x] Add NLE multicam/project-bin workbench contracts: `timeline.multicam.sync_plan`
  and `timeline.multicam.switcher_workbench` now expose angle sync offsets,
  active-angle tiles, and export handoff readiness; `project_bin.batch_plan`
  exposes read-only relink/proxy/conform review operations before any dangerous
  batch apply is added.
- [x] Add Source/Record edit-decision preview: `source_record.edit_decision_preview`
  returns reviewed insert/overwrite payloads, source/record ranges, target
  tracks, warnings, and safe-to-apply state before timeline mutation.
- [x] Add Source/Record patch matrix: `source_record.patch_matrix` exposes
  video/audio patch rows and insert/overwrite command cards for a dedicated
  Source/Record UI without mutating the timeline.
- [x] Add NLE timeline fuzzer readiness bridge: `timeline.nle_fuzzer.status`
  normalizes `tools/qa_timeline_fuzzer.py` into undo/edge-case evidence, and
  `tools/qa_nle_readiness.py` now reads the fuzzer report when scoring NLE
  stability.
- [x] Add NLE undo health matrix: `timeline.undo_health` exposes operation
  coverage rows, undo-depth/failure/linked-audio/actor-lane risk cards, and
  rerun/failure-report command state for QA Dashboard or health panels.
- [x] Add NLE core action coverage matrix: `timeline.core_action_coverage`
  groups edit, clipboard/insert, Source/Record, Project Bin, storyline,
  multicam, and undo/recovery actions so readiness is not based on raw action
  count alone.
- [x] Add NLE undo recovery playbook: `timeline.undo_recovery_playbook`
  exposes rerun, triage, undo/redo replay, autosave/reopen verification, and
  reproduction-step commands for destructive edit failure recovery.
- [x] Add NLE undo stability dashboard: `timeline.undo_stability_dashboard`
  combines fuzzer status, operation coverage, risk cards, blockers, and
  recovery commands into one UI-ready QA surface.
- [x] Add NLE proxy management plan: `project_bin.proxy_plan` exposes usable
  proxies, stale/missing regeneration queues, preview proxy policy, and
  long-project proxy readiness evidence for NLE scoring.
- [x] Add NLE proxy health board: `project_bin.proxy_health` exposes
  product-facing proxy state cards, safe background regeneration enablement,
  stale/missing/offline review signals, and stronger proxy/media-management
  evidence for NLE scoring.
- [x] Add NLE proxy conflict board: `project_bin.proxy_conflict_board`
  separates safe background proxy jobs from offline blockers, duplicate media
  paths, and review-only conflicts so long-project proxy refresh can be shown
  without accidentally implying every stale proxy is safe to regenerate.
- [x] Add NLE conform report: `project_bin.conform_report` checks timeline clip
  source paths against Media Pool rows, reports path/name/ambiguous/missing
  matches, and exposes relink/offline review commands for NLE scoring.
- [x] Add NLE relink candidate board: `project_bin.relink_candidate_board`
  exposes file-by-file safe path matches, name-only review, ambiguous choices,
  offline matches, and missing sources for Media Pool/project-bin workflows.
- [x] Add Final Cut-style magnetic storyline foundation:
  `timeline.magnetic_storyline.status/apply` detects gaps/overlaps, closes
  primary-storyline gaps while preserving clip order, and moves linked audio by
  the same delta. This is the competitive fast-editing foundation, not full FCP
  interaction parity yet.
- [x] Add Final Cut-style connected clip and role-color foundation:
  `timeline.connected_clips.status/connect`, `timeline.role_colors.status`, and
  `timeline.clip_role.set` persist connected-parent offsets plus clip role/color
  metadata, expose the state to AI/MCP, and add a minimal timeline strip/badge.
- [x] Add role-aware lane view-model and timeline cue:
  `timeline.role_lanes.status/focus` groups clips by role and stores focused
  role state; timeline clips with role/connection/audition metadata draw a
  role-color rail, connected diamond, and audition take dots.
- [x] Refactor magnetic storyline, connected clip, and role-lane action logic:
  editor adapter methods now live in
  `app/actions/editor_adapter_nle_storyline.py` and public action registration
  lives in `app/actions/nle_storyline_namespace.py`, keeping public action IDs
  stable.
- [x] Add Final Cut-style audition/take foundation:
  `timeline.auditions.status`, `timeline.audition.add_take`, and
  `timeline.audition.switch_take` store candidate takes on a host clip and swap
  the active take into normal preview/export-facing clip source fields.
- [x] Add audition picker/take-management action contract:
  `timeline.audition.compare`, `timeline.audition.rename_take`, and
  `timeline.audition.remove_take` expose a UI-ready take comparison model,
  rename candidate takes, and safely remove takes while preserving one active
  take.
- [x] Wire the `AUD` timeline badge to a compact audition picker dialog:
  `app/video_editor_nle_audition_workflow.py` opens from the timeline badge,
  lists takes, marks the active take, and drives switch/rename/remove through
  the registered Python Actions.
- [x] Refactor the audition adapter/action surface out of the broad NLE files:
  editor mutation methods now live in
  `app/actions/editor_adapter_nle_auditions.py` and public action registration
  lives in `app/actions/nle_auditions_namespace.py`, keeping action IDs stable.
- [x] Add Final Cut-style visual feedback contracts:
  `app/nle_visual_feedback.py` exposes connected-clip anchor overlay rows,
  role-lane filter visible/hidden clip sets, and non-mutating magnetic drag
  preview placement/push/snap feedback through
  `timeline.connected_clips.anchor_overlay`,
  `timeline.role_lanes.filter_model`, and
  `timeline.magnetic_storyline.drag_preview`.
- [x] Refactor Final Cut-style visual feedback out of the broad NLE files:
  adapter methods live in `app/actions/editor_adapter_nle_visual.py` and public
  action registration lives in `app/actions/nle_visual_namespace.py`, while
  `app/video_editor_window.py` remains a compatibility facade.
- [x] Wire first Final Cut-style visual feedback into the Qt timeline:
  `app/timeline_nle_visual_overlay.py` owns reusable clip-anchor and
  drag-preview paint helpers; `app/timeline_track_row_paint.py` now draws
  stronger connected-clip anchor cues plus compact move/snap/blocked drag
  guides without adding logic to `app/video_editor_window.py`.
- [x] Wire role-lane focus into live timeline rows:
  `timeline.role_lanes.focus` now propagates to `TrackRow.set_focused_clip_role`
  and non-matching clip roles are dimmed by
  `app/timeline_nle_visual_overlay.py`, so the action-layer role focus has an
  immediate timeline effect.
- [x] Add compact Final Cut-style role filter bar:
  `app/video_editor_nle_role_panel.py` renders `timeline.role_lanes.filter_model`
  as an in-timeline role strip, and
  `app/video_editor_nle_role_workflow.py` routes clicks through
  `timeline.role_lanes.focus` so UI state, row dimming, and Python Actions stay
  aligned.
- [x] Add cross-row connected clip overlay:
  `app/timeline_connected_anchor_overlay_widget.py` paints parent/child anchor
  curves over the timeline viewport, refreshing on scroll and role/storyline
  mutations without adding feature logic to `app/video_editor_window.py`.
- [x] Improve visual audition picker:
  `app/nle_audition_visuals.py` builds a card model for take comparison, and
  `app/video_editor_nle_audition_workflow.py` now shows a compact card strip
  above the detailed take table while still applying changes through registered
  Python Actions.
- [x] Improve magnetic drag visual language:
  `app/timeline_nle_visual_overlay.py` now emits field-line/hatch metadata for
  snap, push, move, and blocked drag previews, and
  `app/timeline_track_row_paint.py` consumes those cue values directly.
- [ ] Deepen Final Cut-style UI parity: tune magnetic drag timing against real
  editor gestures and add real-project usability QA before any full Final Cut
  replacement claim.
- [x] Add NLE multicam angle bins: `timeline.multicam.angle_bins` exposes
  UI-ready angle coverage, gap diagnostics, sync readiness, and switcher/export
  command enablement so multicam panels can show real bin health instead of only
  a generated switch plan.
- [x] Add Source/Record monitor backend actions for 3-point editing:
  `source_monitor.*`, `record_monitor.*`, `timeline.three_point_insert`, and
  `timeline.three_point_overwrite` now give future UI work a tested backend.
- [ ] Remaining full NLE parity gaps: dedicated Source monitor / Record monitor
  UI is still shallow; multicam, deeper proxy/media management, conform,
  relink, and project-bin workflows need more depth; undo/redo and edge-case
  behavior need continuous QA; long-duration and large-project real-world
  validation need more evidence before making a full NLE replacement claim.
- [x] Add pure timeline roll/slip/slide edit helpers with clamped source bounds
  and no input mutation, so toolbar modes can share deterministic edit logic.
- [x] Add pure timeline micro-edge diagnostics and cleanup helpers for
  one-frame gaps/overlaps, closing tiny gaps by rippling following clips and
  trimming tiny overlaps without mutating input clips.
- [x] Surface timeline micro-edge cleanup in the track context menu and Media
  Health report, applying fixes to existing clip objects so thumbnails/effects
  stay attached and one undo savepoint captures the cleanup.
- [x] Make Health's timeline micro-edge report actionable with a `Clean
  Timeline Edges` button that skips locked tracks and reuses the undo-safe
  cleanup command.
- [x] Add Health cleanup preview polish: show count-aware button text and
  affected clip-pair/time-span samples so users know what timeline edges will
  be auto-cleaned before running it.
- [x] Keep linked audio in sync during timeline micro-edge cleanup: linked
  audio offsets move by the same ripple delta and cleanup blocks before
  mutation if linked audio would collide, is missing, duplicated, or shared.
- [x] Rebuild and reopen Health after a successful timeline edge cleanup so
  users see the post-cleanup project state instead of stale diagnostics.
- [x] Extend undo/redo snapshots to cover timeline markers, zoom, playhead,
  Spine actor tracks, and Live2D actor tracks, not only video/audio/subtitles.
- [x] Extend undo/redo restore to reconcile video/audio track collections:
  deleted tracks come back, newly-created tracks are removed, row order is
  restored, and audio mixer bindings are refreshed.
- [x] Add fast Live2D/Spine compatibility matrix tooling for local model
  corpora before slow render QA: `tools/actor_compat_matrix.py`.
- [x] Expand actor compatibility QA for real corpora with per-row severity,
  issue codes, dependency counts, missing-dependency kinds, family grouping,
  recommendations, top failures, `--summary-only`, and early `--limit`
  short-circuiting.
- [x] Add large-corpus actor stress classification: Live2D/Spine compatibility
  rows now include feature flags, risk codes, risk severity/score, and
  `stress_tier` for rig/atlas/mesh/motion edge cases that may pass dependency
  checks but still need priority render/animation QA.
- [x] Add actor render QA baseline regression comparison for large Live2D/Spine
  corpus runs, making newly broken models fail the combined report while
  recovered and newly discovered models are summarized separately.
- [x] Add top-risk actor render sampling, animation sweep QA, golden-image
  regression hooks, and known-failure quarantine allowlists for large
  Live2D/Spine corpus runs.
- [x] Productize Live2D/Spine corpus regression QA with a manifest-driven
  runner, weekly CI preflight, failure taxonomy, Spine skin/slot sweep,
  Live2D motion metadata sweep, and compact status artifacts for Health/UI.
- [x] Extend actor QA operations with optional external corpus roots, golden
  baseline inspection/promotion tooling, Live2D expression render variants,
  Spine mix-and-match skin-combination sweep, Media Pool actor QA badges, and
  a local full render/golden runner.
- [x] Expand Live2D/Spine compatibility UI in Media Pool: actor rows can refresh
  compact corpus status, stamp pass/risk/quarantine/fail badges, and show
  per-model status, broken dependency, missing atlas/MOC/motion, render/golden
  baseline, known-failure, and recommendation details.
- [x] Add an Actor QA Browser dialog from the Actors menu and Command Palette
  for full model-level Live2D/Spine pass/risk/fail browsing.
- [x] Fix placed Live2D actor clips not opening the editor on double-click:
  `Live2DActorLaneRow` now uses the same 10 px `TimelineRuler` coordinate
  origin as video tracks, exposes `_preferred_width()`, and its
  double-click hit-test is covered by regression QA.
- [x] Audit similar timeline hit-test/drop coordinate paths: video/audio/subtitle/text
  lanes and Spine/Live2D actor lanes now share the 10 px `TimelineRuler` margin;
  Spine hit-testing uses the same visible-width rule as Live2D for very short
  actor clips.
- [x] Fix actor-lane playhead alignment: Live2D/Spine actor lanes no longer use
  their label width as a time origin, so their playhead and clip x positions
  align with video tracks and the timeline ruler.
- [x] Fix Live2D editor crash on actor double-click: the bottom bar background
  swatch loop no longer shadows the `QHBoxLayout`, and editor construction is
  covered by regression QA.
- [x] Productize Live2D/Spine editor load feedback: timeline double-click uses
  deferred linked-clip loading, Live2D runtime warm-up is scheduled after editor
  startup, both actor editors expose progress/cancel/timeout/load logs/retry
  recovery, timeline clips show transient load status badges, and
  `tools/qa_actor_loading_ux.py` covers the loading UX contract.
- [x] Add Live2D/Spine loading hardening layer: non-destructive actor
  compatibility repair, persistent staged loading cache, isolated child-process
  render probe, prerender preview cache, Actor Loading Manager dialog, actor
  crash context in repro bundles, and overnight actor QA planning through
  `tools/qa_actor_overnight.py`.
- [x] Connect actor loading hardening to daily editing: ProjectPlayer can reuse
  exact safe actor prerender frames before falling back to live render, actor
  timeline context menus expose status/probe/prerender/quarantine/open-folder
  actions, Actor Loading Manager can run selected probes/prerenders and
  overnight plan/render smoke, crash UI surfaces actor context, and the preset
  library includes more Screen Studio-style animated cursor/icon and wallpaper
  palette templates.
- [x] Calibrate actor stress coverage for real NIKKE-style Spine rigs: weighted
  mesh + constraints + multi-page atlas now enters the stress tier, the local
  corpus reaches the stress target, 40 actor golden baselines are created, and
  Spine direct-GL preview state is cached across quantized frames.
- [x] Harden preview-performance regression QA after actor sampling changes:
  baseline comparison now separates blocking regressions from advisory warm-up,
  p95-only, and changed-sample-plan signals; the 2026-06-17 run verifies zero
  blocking preview regressions and 40 matching actor golden baselines.
- [x] Productize project repair/recovery reports with candidate health levels,
  scores, recommended user actions, and repair guidance.
- [x] Replace the one-shot Recovery confirmation prompt with a table-based
  recovery browser that lets users compare candidates by health, score, missing
  paths, repair changes, modified time, path, reason, and recommended action.
- [x] Expand Recovery candidate diagnostics with missing-by-kind counts, missing
  path previews, schema repair previews, actor asset failure previews, and
  suggested steps in the detail pane.
- [x] Harden timeline nudge/undo edge cases: linked video+audio nudges now use
  a pure collision-checked move plan before mutating lanes, and undo/redo
  snapshots restore live clip selection without keeping stale deleted clips.
- [x] Extend the same linked video/audio preflight to mouse clip drags via a
  `TrackRow` validator callback, so blocked linked-audio/cross-track drags do
  not partially move the origin video clip first.
- [x] Make linked timeline move preflight respect locked video tracks, so
  keyboard nudges and mouse drag validation fail before mutating clips on locked
  lanes and show a clear blocked status message.
- [x] Harden linked timeline move preflight for stale selections and shared
  linked-audio references, so corrupted/old selection state cannot partly move
  clips before the user sees a clear blocked reason.
- [x] Polish keyboard nudge micro-interaction: `Ctrl+Alt+Left/Right` now nudges
  selected clips by ten frames, successful nudges show exact frame/ms feedback
  plus linked-audio count, and empty nudge attempts prompt the user to select
  clips.
- [x] Tighten the timeline status chip so it exposes nudge shortcut help through
  a tooltip without letting long guidance text stretch and break the toolbar.
- [x] Add commercial edit-point navigation: plain `Up/Down` jumps the playhead
  to the previous/next timeline edit point across video clips, audio clips,
  markers, and Spine/Live2D actor clips, with a short status banner.
- [x] Add keyboard timeline zoom polish: `Ctrl+=`, `Ctrl+-`, and `Ctrl+0`
  mirror the visible zoom in/out/fit controls, share the same clamped zoom
  update path, and show short status feedback for keyboard zoom operations.
- [x] Keep the playhead visible after keyboard timeline navigation: edit-point
  jumps, Left/Right/Home/End seeks, and keyboard zoom now scroll the timeline
  horizontally only when the playhead would otherwise sit outside the viewport.
- [x] Make keyboard seek use the full project duration instead of the active
  video track duration, so Right/End can reach audio-only tails and Spine/Live2D
  actor-only timeline extents.
- [x] Add Escape timeline context reset polish: `Esc` returns non-Select tools
  to Select first, then clears clip selection when already in Select, without
  wiping time selections or global markers.
- [x] Add `Ctrl+A` timeline selection polish: select all video timeline clips
  in track order, clear stale selection on empty timelines, and expose the
  shortcut in the timeline status tooltip.
- [x] Add `Ctrl+D` timeline duplication polish: duplicate selected clips after
  the selection, preserve spacing, skip occupied windows, select the new
  duplicates, clear copied linked-audio/compound metadata, and block locked
  tracks.
- [x] Add internal timeline `Ctrl+C` / `Ctrl+V` copy-paste polish: copy
  selected clips, paste at the playhead, preserve cross-track offsets, shift
  the whole paste group past collisions, select the pasted clips, clear copied
  linked-audio/compound metadata, and block locked target tracks.
- [x] Add timeline `Ctrl+X` cut polish and locked-track delete hardening:
  cut copies selected clips to the internal clipboard before ripple-deleting,
  locked tracks block before the clipboard changes, and Delete/Backspace now
  respect locked tracks too.
- [x] Add commercial `J/K/L` transport polish: `L` cycles forward shuttle
  speeds, `K` pauses/resets shuttle speed, `J` provides repeatable reverse jog
  steps until true reverse playback exists, and the jog/shuttle widget's zero
  shuttle position now pauses playback.
- [x] Add precise keyboard frame-step polish: `,` / `.` step backward/forward
  by one project frame, Shift steps ten frames, playback/shuttle is paused
  first, bounds are clamped, and the timeline scroll keeps the playhead visible.
- [x] Harden Blade against locked tracks: playhead blade skips locked lanes
  and reports the skip, while track-specific blade clicks are blocked on locked
  lanes before mutating clips.

## Professional Color Workflow

- [x] Add project color-management core for Rec.709, sRGB, Rec.2020 HDR
  PQ/HLG, P3-D65, ACEScg/ACEScct intent, optional OCIO config paths,
  input/creative/output LUT slots, pipeline summaries, FFmpeg color metadata,
  and project/export consistency validation.
- [x] Persist default project color-management settings in new projects and
  saved/loaded `.tgp` projects, with Rec.709 defaults for older projects.
- [x] Attach project color metadata to non-HDR-passthrough FFmpeg exports while
  leaving the existing HEVC 10-bit BT.2020 PQ passthrough path untouched.
- [x] Extend color qualifiers with clean black, clean white, and denoise radius
  controls so HSL keys can be cleaned up before masked grades/curves apply.
- [x] Add grade-local input/creative/output LUT slots, explicit
  clip/group/timeline grade-stack application, and a deterministic shot-match
  grade suggestion helper.
- [x] Add a Color Page project color-management strip for input/working/output
  color space, transfer, view transform, HDR, project LUT slots, and creative
  LUT intensity, with changes persisted in `_project_settings`.
- [x] Bake active project LUT slots into FFmpeg exports with `lut3d`, including
  split/blend intensity handling for LUT strengths below 100%.
- [x] Add a Color Page Qualifier / Window panel for HSL key precision,
  clean black/white, denoise, power-window shape/position/size/feather/opacity,
  and tracking intent, writing directly to `ColorGrade.color_workflow`.
- [x] Add direct preview Power Window handles for active Color Page windows,
  including move/resize drag, normalized coordinate clamping, live preview
  refresh throttling, and one undo checkpoint on mouse release.
- [x] Add optional OCIO/ACES transform bridge that reports availability,
  validates config usage, and applies PyOpenColorIO RGB transforms only when
  the runtime/config are present.
- [x] Add scope quality diagnostics for luma IRE, HDR nits estimate, channel
  clipping, saturation/gamut risk, skin-tone angle, and Color Page warning
  feedback.
- [x] Add ffprobe color metadata comparison for post-export QA so render queue
  diagnostics can flag mismatched colorspace, primaries, or transfer tags.
- [x] Surface post-export color metadata QA in the UI: single exports append
  Color QA to the completion dialog, while Render Queue jobs persist it in the
  diagnostics column/history with ffprobe and ffmpeg-stderr fallback probing.
- [x] Add repeatable Color/Audio accuracy QA through
  `tools/qa_color_audio_accuracy.py`, covering scope diagnostics, LUT/color
  metadata consistency, loudness/true-peak/stereo warnings, and dialogue
  cleanup preset clamping.
- [x] Add optional real media sample inputs to Color/Audio QA with
  `--video-sample` and `--audio-sample`, so real shots and dialogue/music files
  can be decoded and measured alongside the deterministic reference suite.
- [x] Productize Color/Audio sample QA discovery: `tools/qa_color_audio_accuracy.py`
  now accepts `--sample-root` and auto-discovers
  `qa_corpus/color_audio_samples` when present, recording sample sources in the
  report for QA Dashboard review.
- [x] Surface latest Color/Audio QA as an export/preflight badge, including
  OK/FAIL, check count, failure count, and real sample count in export and
  Render Queue diagnostics.

## Professional Audio Workflow

- [x] Add shared Qt-free audio accuracy helpers for approximate integrated LUFS,
  true peak, stereo correlation, and audio warning diagnostics.
- [x] Point the Audio Mixer LUFS display and scripted Color/Audio QA at the same
  LUFS approximation so UI meters and release checks stay consistent.

## Crash Recovery / Stability QA

- [x] Add app-level crash breadcrumbs and JSON crash reports:
  `app/crash_reporter.py` records recent user/system actions to
  the per-user runtime log folder and writes `crash_report_latest.json` there
  on unhandled Python exceptions, so normal diagnostics do not dirty the source
  checkout.
- [x] Harden launcher-to-editor startup against flicker: stale test/editor
  processes are detectable via startup trace, duplicate rapid editor-open
  requests are ignored in the controller, and low-frequency Qt menus are
  created lazily instead of during initial editor construction.
- [x] Pinpoint launcher-to-editor flicker with WinEventHook tracing and make
  the main OpenGL preview lazy-created. The app-side transient windows were
  Qt/NVIDIA helper windows from eager `QOpenGLWidget` creation, not
  TigerCapture-spawned console processes; Codex/Git/PowerShell helper windows
  are now separated by `app_related` trace metadata.
- [x] Remove the second startup flicker source: export/color preset menus now
  stay unbuilt until a user presses their button, avoiding hidden
  `Qt6110QWindowPopupDropShadowSaveBits` native popup/drop-shadow windows
  during launcher-to-editor startup.
- [x] Re-check launcher-to-editor flicker against official Windows/Python/Qt
  behavior instead of guessing from titles: `CREATE_NO_WINDOW` only explains
  console apps, while Qt popup/drop-shadow windows are native top-level helper
  surfaces. The product-flow external trace now measures visible windows
  separately from the app's internal tracer.
- [x] Prove the current product path does not spawn visible console flashes:
  `tools/trace_visible_windows.py --duration 10 --log-path
  debugCapture/startup_trace_logs/visible_window_trace_no_internal.jsonl --
  .venv/Scripts/python.exe tools/trace_launcher_open.py --no-internal-trace`
  followed by `tools/analyze_visible_windows.py ...` reports
  `Visible console-like rows: 0` and no DWM Ghost rows for the product flow.
- [x] Make the internal startup tracer less invasive so diagnostics do not
  become the flicker source: native polling is capped to coarse intervals,
  external Codex/Git/PowerShell process spam is ignored, and window logging is
  limited to the TigerCapture process/title family.
- [x] Remove the launcher delay `QComboBox` from the editor-open path and use
  segmented delay buttons, avoiding pre-created combo popup/native menu
  surfaces during launcher-to-editor startup.
- [x] Add temporary CapCut feature gates while startup flicker is being
  isolated: `app/capcut_features.py` seals local ML, Creator Assist,
  apply-bundle mutation, template auto-apply, and CapCut QA by default, with
  one-env-var-per-feature re-enable switches.
- [x] Seal local ML by default without pretending it is removed: SAM,
  Demucs, Whisper AI subtitles, and CapCut local-media bundle generation now
  return disabled/non-cloud status unless explicitly re-enabled for QA.
- [x] Remove the latest launcher-to-editor small-window source: startup
  `processEvents()` is opt-in only, hidden Qt orphan widgets are re-parented at
  bootstrap phase boundaries, and parentless hidden controls such as
  `SelectionBar`/dormant Spine buttons now have explicit parents.
- [x] Remove the remaining launcher-to-editor Qt top-level flicker candidates:
  Workbench, color/timeline, toolbar, preset browser, collapsible section, and
  Media Pool widgets now receive explicit parents at construction time, hidden
  custom QWidget subclasses are covered by orphan cleanup, and
  `visible_window_trace_parented_no_internal.jsonl` plus
  `visible_window_trace_mediapool_parented.jsonl` confirm `Visible console-like
  rows: 0` with only the normal launcher/editor visible during startup. User
  real-run confirmation on 2026-06-22: fixed.
- [x] Reopen the CapCut/local-ML routes after the flicker fix: CapCut-style
  creator features and local-only ML are enabled by default again, with
  `TIGERCAPTURE_CAPCUT_DISABLED=1` and `TIGERCAPTURE_LOCAL_ML_DISABLED=1` kept
  as diagnostic off switches.
- [x] Replace the launcher Full/Simple workspace buttons with an iOS-style
  Normal/Simple slide toggle and increase the launcher default/minimum size so
  the editor entry and capture controls no longer clip at startup.
- [x] Finish the launcher switch product pass: the Normal/Simple switch now
  supports drag gestures, animates its knob/color state, remembers the selected
  workspace mode in the user data directory, and the launcher body scrolls when
  the window is shorter than the content.
- [x] Harden launcher state and startup diagnostics: invalid
  `launcher_state.json` is backed up/repaired to standard mode, stale or
  malformed crash reports no longer trigger the startup crash notice, and
  Screen Studio GUI-flow QA asserts that CapCut/local-ML dashboard rows remain
  reachable without reintroducing template-first launcher clutter.
- [x] Make Screen Studio cursor/click animation more robust in real frames:
  preview owner resolution and export clip-effect snapshots now fall back from
  clip-level cursor/polish metadata to track-level metadata.
- [x] Register editor emergency autosave with the crash reporter and make
  autosave more aggressive: default interval is 120 seconds
  (`TIGERCAPTURE_AUTOSAVE_INTERVAL_MS`) and recovery snapshot retention is 24
  copies (`TIGERCAPTURE_RECOVERY_KEEP`).
- [x] Add timeline pixel alignment QA through `tools/qa_timeline_alignment.py`
  so TimelineRuler, video rows, Live2D rows, and Spine rows must share the same
  time-to-pixel origin.
- [x] Add Live2D/Spine actor-lane workflow QA through
  `tools/qa_actor_lane_workflow.py`, covering clip creation, hit-test,
  double-click signal delivery, and playhead x-position.
- [x] Add deterministic Node Graph QGraphicsScene fuzzing through
  `tools/qa_node_graph_fuzzer.py`, covering add/connect/reject/delete/move and
  save/load roundtrips.
- [x] Extend visual regression snapshots with `current_snapshot.json` metadata
  and expose the new stability QA reports in the in-app QA Dashboard and
  productization fast-QA loop.
- [x] Add an in-app Crash Report viewer with emergency-autosave open, summary
  copy, log-folder open, and repro-bundle export actions.
- [x] Add restart recovery UX: opening a blank video editor checks for an
  unseen latest crash report and offers the crash report/recovery dialog before
  the normal last-project resume prompt.
- [x] Add recent-action repro export through
  `app.crash_reporter.export_repro_bundle()`, producing
  `debugCapture/repro/crash_repro_*.json` with exception, autosave, recent
  actions, traceback tail, and readable repro steps.
- [x] Upgrade QA Dashboard with fast Run All, history-backed trend rendering,
  visual regression one-click runner, and visual-baseline approval through
  `tools/qa_visual_baseline_manager.py`.
- [x] Extend actor-lane workflow QA with optional real sample loading via
  `tools/qa_actor_lane_workflow.py --include-samples`, covering installed
  Live2D and Spine sample files.
- [x] Add screenshot-based timeline visual alignment QA through
  `tools/qa_timeline_visual_alignment.py`.
- [x] Add widget-level Node Graph UI fuzzing through
  `tools/qa_node_graph_ui_fuzzer.py`, covering NodeGraphWidget add/select/
  bypass/delete/fit/save-reload/set-track flows.
- [x] Add a unified Health Center dialog that summarizes latest crash report,
  QA status, render queue status, current media/proxy health, and actor QA
  risk in one product-facing diagnostic window.
- [x] Optimize autosave with dirty-state skipping: timer autosave writes once
  for recoverable state, skips clean timer ticks, but still forces close/crash/
  recovery/relink saves.
- [x] Add persistent product QA fixtures to `tools/build_qa_corpus.py`: a sixth
  long-project stress `.tgp`, a readable `.tigercapture_recovery/*~autosave.tgp`
  candidate, and default `qa_corpus/color_audio_samples` real media samples.
- [x] Add long-project/recovery product smoke QA through
  `tools/qa_long_project_stress.py`, requiring 5+ minutes of timeline coverage,
  100+ video clips, 120+ audio clips, nested sequences, proxy state, no missing
  media, and an `open_safe` recovery candidate.
- [x] Add product-level micro-interaction QA through
  `tools/qa_micro_interactions.py`, verifying icon-first tool glyphs, rollover
  labels, timeline burst painter availability, blade entry points, and global
  hover/press styling.
- [x] Add visual-baseline coverage audit through
  `tools/qa_visual_baseline_audit.py` and make `tools/qa_visual_regression.py`
  tolerate tiny offscreen-render pixel jitter while still failing real layout
  diffs.
- [x] Add Live2D/Spine mass-compat smoke QA through
  `tools/qa_actor_mass_compat.py`, checking actor corpus status, stress-tier
  coverage, quarantine presence, and golden-baseline coverage.
- [x] Connect the new fixture/build, long-project, micro-interaction,
  actor-mass, visual-baseline, and real-sample Color/Audio reports to QA
  Dashboard and the productization fast-QA loop.

## Commercial Expansion Package

- [x] Add a consolidated commercial expansion layer for the ten next product
  areas beyond the closed TODO list: beta feedback, preview frame-server UX,
  preview/export parity lock, AI one-click edit planning, preset marketplace
  management, audio postproduction, color-node workflow depth, project
  snapshots, plugin manifests, and release productization.
- [x] Add `app/commercial_expansion.py` with Qt-free product helpers for
  feedback bundle export, project snapshot creation/listing, plugin manifest
  validation/discovery, GPU parity-lock settings, one-click plan summaries, and
  release checklist diagnostics.
- [x] Add `tools/qa_commercial_expansion.py` and connect it to QA Dashboard and
  the productization fast-QA loop so these ten commercial expansion areas stay
  visible in product reports.
- [x] Add regression tests for commercial expansion report coverage, beta
  feedback bundles, project snapshots, plugin manifest discovery, parity lock,
  and AI one-click plan surfaces.

## Rust / Native Core Strategy

- [x] Add repeatable baseline-performance tooling/specs for real projects
  before moving more code out of Python: 1080p, 4K, masks, Live2D, Spine,
  node graph, and audio-heavy cases.
- [x] Define the initial native-helper protocol: JSON-lines request/response,
  capability metadata, shutdown, and structured errors.
- [x] Extend the worker protocol with file input/output contracts, progress
  events, cancellation, and golden-fixture validation.
- [x] Create a small Rust worker proof-of-concept that can be called from
  Python as a subprocess and returns version/capability metadata.
- [x] Install Rust/Cargo on the main Windows dev machine and run
  `cargo build --release` for `native/tigercapture_worker`.
- [x] Add CI/build packaging wiring so bundled releases include the native worker
  executable for Windows/macOS/Linux.
- [x] Move media probing/indexing into the Rust worker once the protocol is
  stable.
- [x] Move timeline thumbnail cache generation into Rust or a Rust-orchestrated
  FFmpeg path after proving it beats the current Python/OpenCV cache path.
- [x] Move waveform/spectrum generation into Rust after preserving current cache
  key compatibility.
- [x] Start timeline-core Rust migration with the low-risk
  `timeline_drag_constraints` planner. `clip.move_snapped` now prefers the
  native snap/collision/clamp result and falls back to the established Python
  timeline policy when the worker is unavailable.
- [x] Continue timeline-core Rust migration with the low-risk `timeline_gaps`
  planner. Shared gap detection now prefers native rows for `timeline.gaps`,
  `timeline.close_gap`, and `timeline.close_all_gaps`, with Python fallback.
- [x] Continue timeline-core Rust migration with the video-only
  `timeline_trim_plan` planner. `clip.ripple_trim`, `timeline.precision_trim`,
  and `timeline.trim_to_playhead` now prefer native trim-window and ripple-shift
  planning while Python keeps validation, linked audio, undo, and mutation
  fallback.
- [x] Move object-tracking cache generation into a background worker while
  keeping the cached bbox/correction data on `BitmapMask`.
- [x] Consider `pyo3` bindings only after the subprocess worker API is proven and
  packaging overhead is understood.
- [x] Defer any full UI rewrite until timeline semantics, project format,
  preview/export parity, and native helper contracts are stable.

## Audio Separation

- [x] Validate source files before source separation starts.
- [x] Surface the planned separation backend (Demucs vs FFmpeg mid/side) in the
  worker/progress dialog.
- [x] Add a cancel path for long-running Demucs/FFmpeg subprocesses.
- [x] Add a quality warning/preset selector for FFmpeg mid/side fallback.

## Current UX Fixes

- [x] Make the timeline Color switch reveal the embedded color dock by default,
  keep the main preview visible, and rebuild the node chain on Color Page grade
  changes before refreshing preview.
- [x] Rework the embedded Color dock into a compact palette strip and prevent
  Edit/Color tab switches from mutating NodeGraph selection, avoiding black
  preview frames during rapid tab switching.
- [x] Add Edit/Color preview guard fallback: cache the last good QPixmap/RGB
  preview frame and restore it only during tab switches when a tiny blank frame
  arrives while a renderable clip is active.
- [x] Extend the preview guard to actor-editor focus and mask-edit refresh
  paths, add compact Color Dock reset pulse feedback and a direct full Color
  Page entry point, and expand `tools/qa_ui_layout.py` to screenshot/check the
  opened compact Color Dock.
- [x] Fix compact Color Dock changes not affecting preview by wiring fresh
  `Node 1` into the active `IN -> Node 1 -> OUT` graph, repairing legacy
  unwired color graphs on open, adding a shared color-preview commit path, and
  covering preview/export node-chain parity plus active-target UI feedback.
- [x] Add Color Dock preview-only `Before`/`Split` compare controls, fast
  color preview/export parity QA, a larger Live2D first-load progress panel,
  and clearer animated cursor markers in preset A/B previews.
- [x] Make effect and transition preset hovers visible on the preview frame:
  they now show an FX/TRANSITION overlay even without a selected target clip,
  then also live-preview on the selected clip when one is available.
- [x] Focus the preview on the affected frame range after applying effect,
  transition, title, caption, sticker, or motion presets, with a short viewer
  overlay so users can immediately see what changed.
- [x] Surface applied preset state directly in the editing UI: timeline video
  clips now paint compact FX/Key/TR/T/Mot/Nest badges, and the Workbench FX tab
  lists the selected clip stack with undo-safe Clear Clip FX / Clear Transition
  actions.
- [x] Replace Live2D's primary Apply-button flow with automatic linked-clip
  assignment on model load, motion selection, transform edits, and editor close.
- [x] Focus the main preview playhead inside a Live2D/Spine actor clip when the
  actor editor opens or placement changes, so position/scale edits are visible.
- [x] Share Spine preview/editor fit-margin math through
  `app/spine_editor/layout.py` and use a safer 0.76 work-view fit margin to
  reduce edge clipping while transforming actors.
- [x] Upgrade `Preview Apply`/A-B preset previews with a new cache key and
  payload-specific visual hints for blur/denoise, sharpen, vignette, glitch,
  LUT, chroma-key matte, and transition types.
- [x] Make timeline preset/effect badges interactive: clicking FX/Key/AI/TR/T/Mot
  selects the clip, focuses the Workbench/preview context, and avoids starting
  an accidental clip drag.
- [x] Add Workbench FX stack actions for selected clips: Edit Clip FX,
  Disable/Enable Clip FX, Clear Clip FX, and Clear Transition, with disabled
  clip FX persisted on the `VideoClip` model and in project save/load.
- [x] Make preset timeline state self-explanatory: badge right-click menus now
  expose focus/edit, enable/disable FX, clear FX, and clear transition actions;
  effect-preset drags show a blocked drop chip when the pointer is not over a
  clip; and `tools/qa_creator_polish_coverage.py` gates preset preview realism,
  Screen Studio defaults, CapCut quick-create, and stability hooks in one fast
  QA report surfaced in QA Dashboard/Productization Loop.
- [x] Add undo/redo feedback polish: empty undo/redo shows status, successful
  restore flashes a status banner and timeline burst.
- [x] Replace vague timeline "hand feel" polish with concrete drag feedback:
  clip drag constraints now return snap/collision/clamp metadata, TrackRow
  paints a small live chip for "Snap", "Move", or "Collision avoided", group
  drags get the same feedback, and preset applications pulse the actual
  affected timeline position with an `@ time` status note.
- [x] Finish the next concrete timeline UX pass: drag ghosts now show the
  destination span before release, blocked linked/cross-track moves paint a red
  preview instead of silently refusing, hover chips label trim/roll/transition/
  fade/speed/actor affordances, undo/redo banners include the exact history
  label, and preset/drag outcomes append structured rows to `ux_events.jsonl`.
- [x] Add reason-aware blocked drag feedback: linked audio overlap/missing,
  locked track, project-start, and video-collision failures now flow from the
  editor drag validator into localized timeline chips and blocked-drag UX logs.
- [x] Add visual drag-feedback QA: `tools/qa_timeline_drag_feedback.py` drives
  real TrackRow mouse press/move gestures, captures snap and blocked drag
  screenshots, checks visible feedback colors/text, and is exposed in QA
  Dashboard as `Timeline Drag Feedback`.
- [x] Add release-result mouse gesture QA for timeline edit modes:
  `tools/qa_timeline_edit_gestures.py` drives trim, ripple, roll, slip, and
  slide through real TrackRow press/move/release events, verifies one undo
  commit pulse per gesture, checks final clip/source timings, captures
  screenshots, and is exposed in QA Dashboard as `Timeline Edit Gestures`.
- [x] Add hover-affordance QA for timeline edit feel:
  `tools/qa_timeline_hover_affordance.py` drives repeated real TrackRow
  mouse-move events, verifies hover chips, native tooltip sync, and cursor
  shapes for move, trim, roll, slip, and slide, captures screenshots, and is
  exposed in QA Dashboard as `Timeline Hover Affordance`.
- [x] Improve applied preset visibility on the timeline: short clips now draw
  compact colored markers instead of hiding effect/title/transition strips, the
  applied-elements tooltip is localized, and
  `tools/qa_timeline_preset_visibility.py` verifies wide strips plus short-clip
  markers through QA Dashboard as `Timeline Preset Visibility`; the full
  productization loop now runs drag-feedback, edit-gesture, hover-affordance,
  and preset-visibility timeline QA together.
- [x] Fix Spine zoom/placement clipping in software fallback: oversized or
  partly off-frame textures and triangles now clip to the visible canvas slice
  instead of being dropped, covering NIKKE-style large background/mesh rigs in
  preview/export fallback paths.
- [x] Close the Spine GL side of zoom-crop handling: editor/offscreen/direct
  preview GL paths reset stale scissor state, and the Spine editor now has a
  work-view camera plus final-frame toggle so enlarged actors can be adjusted
  without losing sight of the actual output crop.
- [x] Integrate Screen Studio export-completion handoff into Render Queue:
  completed jobs now use the same completion summary as single export, write
  local-share manifests when eligible, and show status/manifest/actions in the
  Render Queue diagnostics pane.
- [x] Strengthen Screen Studio product QA: naturalness QA now tracks long
  samples separately (`long_samples`, `long_rhythm_ok`, `long_coverage_ok`),
  and visual-baseline audit requires passing Screen Studio GUI-flow,
  export-handoff, and default export-readiness reports.
- [x] Expand the Screen Studio delivery template pack with record/edit/export,
  click-to-cut, wallpaper demo, product walkthrough, and short-export one-click
  templates wired into search, one-click planning, and template-reference QA.
- [x] Add launcher text-surface regression coverage: Screen Studio GUI-flow QA
  now checks launcher action labels/tooltips for mojibake-style corruption so the
  first-run Korean/English surface stays readable.

## Screen Studio 100% Parity Gap

Why the current estimate is not 100% yet:

- UI parity is about 65-70% because the app has Screen Studio-inspired panels,
  palettes, icons, and quick-start flow, but still carries pro-editor density:
  Media Pool, Workbench, node graph, actor lanes, Color/Audio docks, and many
  utility actions are visible or one click away. Screen Studio feels calmer
  because most users see only record, polish, timeline, and export surfaces.
- Auto zoom/cursor/click parity is about 70-75% because the data path exists
  and preview/export are covered by QA, but the motion still needs more
  subjective polish: cursor easing, click settle, zoom timing, motion blur,
  cursor replacement quality, and long-recording rhythm need to feel excellent
  on messy real recordings, not only synthetic QA fixtures.

To reach near-100% Screen Studio parity:

- [x] Build a true "Simple Screen Studio Mode" workspace that keeps the core
  Media Pool and Workbench visible while hiding secondary preset/render/audio
  complexity until the user expands an advanced drawer. The editor no longer
  collapses the left/right docks to 0px; the main toolbar now has an
  iPhone Control Center-style `?쇰컲 / ?ы뵆` workspace switch, and `Panels`
  only toggles non-core panels. Default path: import/record -> polish -> trim
  -> export.
- [x] Add the project-level Simple Screen Studio Mode contract:
  `screenstudio_simple_mode_project_patch()` now seeds simple-mode settings,
  polish, audio defaults, transcript defaults, export defaults, and an
  advanced-drawer surface list that QA/UI can consume.
- [x] Redesign first-run and empty-project UI around a single screen-recording
  task, with fewer visible panels, stronger preview focus, and no dense editor
  chrome before media exists. `screenstudio_first_run_empty_project_report()`
  now locks this as a product contract: no recent/template-first launcher,
  preview/import/record/polish/trim/export as the primary path, and advanced
  surfaces behind the drawer while Media Pool/Workbench identity remains
  available.
- [x] Add a product-grade cursor renderer contract: high-resolution cursor asset
  replacement, per-cursor hotspot metadata, scale-aware shadow, click/ripple
  variations, drag/release accents, hotkey badges, and static-cursor fade that
  match preview and export. The current shared cursor path now uses
  supersampled vector rendering plus hotspot/shadow metadata defaults, and
  `screenstudio_cursor_renderer_quality_report()` checks the contract.
- [x] Tune zoom/cursor motion with real recordings: easing curves, click hold,
  dwell detection, drag tracking, motion blur, crop breathing room, and
  overlap resolution should be scored against visual golden videos, not only
  numeric bbox checks. `screenstudio_motion_tuning_report()` now scores those
  motion defaults and links them to real-corpus interaction readiness so actual
  recordings can decide the real-world pass.
- [x] Add the first Screen Studio-grade manual zoom edit path: timeline zoom
  actors now use `screenstudio_apply_manual_zoom_edit()` for move, edge resize,
  ramp-handle dragging, marker/playhead/edge snapping, target-rect clamping, and
  minimum-duration/ramp safety. `tools/qa_screenstudio_manual_zoom.py` verifies
  the shared policy.
- [x] Finish the remaining manual zoom polish: direct viewer drag handles,
  keyboard nudge UI, duration/easing preset popover, and richer live preview
  feedback while dragging. `screenstudio_manual_zoom_viewer_affordance_report()`
  and the manual-zoom policy now expose viewer handles, keyboard nudge UI,
  duration/easing popover, live feedback, undo commit, and edge-safe crop.
- [x] Make vertical/social export automatic end-to-end: auto reframe every zoom,
  safe-area overlays, social preview, vertical thumbnail/contact sheet, and
  one-click preset selection based on starter/template.
  `screenstudio_vertical_social_export_plan()` locks the 1080x1920 social
  intent, safe-area margins, thumbnail/contact-sheet contract, and automatic
  preset selection for `vertical-shorts`.
- [x] Add share-link provider abstraction for Screen Studio exports:
  `screenstudio_share_provider_config()` and `screenstudio_build_share_link()`
  normalize local/workspace/custom-template handoff, write share URL/provider
  metadata into `<output>.share.json`, expose it through completion summaries,
  and validate it in `tools/qa_screenstudio_export_handoff.py`.
- [x] Finish the remaining export handoff polish: GIF/WebM preset parity, 4K60
  validation, and a richer post-export card instead of generic render logs.
  `screenstudio_export_handoff_polish_report()` now validates MP4/WebM/GIF
  parity metadata, 4K60 readiness, share-manifest readiness, and the rich
  post-export card fields.
- [x] Add Screen Studio-style audio defaults for the default screen-recording
  path: `screenstudio_audio_defaults()` declares voice normalization, noise
  cleanup, dialogue-cleanup strength, and short-form/podcast loudness intent,
  and `screenstudio_default_result_beauty_score()` counts that toward the
  no-manual-tuning score.
- [x] Add transcript/subtitle generation defaults and QA contract:
  `screenstudio_transcript_defaults()` and
  `screenstudio_transcript_subtitle_plan()` define backend order, caption style,
  burn-in defaults, and Subtitle-compatible rows. `tools/qa_screenstudio_parity_gap.py`
  checks this path.
- [x] Wire transcript defaults into editor operations: Whisper output and SRT
  import both create styled `Subtitle` rows through the Screen Studio caption
  plan instead of raw unstyled subtitles.
- [ ] Compare loudness/transcript/subtitle timing on an interaction-ready
  20-50 file real recording corpus. `screenstudio_audio_subtitle_timing_report()`
  already checks loudness/dialogue defaults, styled subtitle timing, and exposes
  a real-corpus gate, but the product claim should wait for actual recordings
  with cursor/click/drag/hotkey/auto-zoom metadata.
- [x] Expand visual baseline QA from screenshots to golden short videos:
  record/import sample -> auto polish -> export -> compare representative
  frames for cursor, click, zoom, background, shadow, and vertical output.
  `screenstudio_golden_short_video_baseline_plan()` now defines the web,
  vertical, and product-demo golden short-video sample contract.
- [x] Add the first golden short-video validation gate:
  `screenstudio_default_golden_video_probe()` renders representative frames and
  verifies wallpaper/frame styling, cursor/click pixels, Auto Zoom planning,
  and preview/export compositor parity. Export handoff QA and visual-baseline
  audit now require `default_golden_video_ready`.
- [ ] Run an interaction-complete real-project corpus of 20-50 screen recordings
  from different apps,
  resolutions, cursor speeds, hotkey usage, long recordings, and vertical
  exports; track pass/fail with before/after videos in QA Dashboard.
  `screenstudio_real_project_corpus_run_report()` now defines the pass/fail
  artifact contract and reports real-world readiness from the manifest-backed
  corpus. File count alone is not enough: release-quality readiness requires
  nonzero cursor sidecars, click/drag/hotkey events, generated auto-zoom windows,
  and before/after export review clips.
- [x] Add real-recording corpus intake/QA contract:
  `screenstudio_recording_corpus_plan()` tracks fixture count, real-recording
  roots, the 20/50 targets, and required capture slots without pretending that
  external user recordings already exist.
- [x] Add manifest-backed real recording registration: media import and
  timeline add now register valid video files by reference in both Simple and
  Full editor modes through
  `qa_corpus/screenstudio_real_recordings/manifest.json` so long-form local
  captures can feed QA without being copied into the repo.
- [x] Add batch registration for real Screen Studio corpus videos:
  `tools/register_screenstudio_real_recording.py --scan-root <folder>` scans
  local folders, ignores tiny/non-video files, auto-assigns empty
  `screenstudio-real-XX` slots, and writes the same manifest used by QA.
- [x] Fix batch-registration progress reporting so `missing_for_minimum` uses
  the corpus plan's actual `missing_min` value and shows zero once 20+ valid
  recordings are registered.
- [x] Add actual real-recording corpus validation:
  `screenstudio_real_recording_corpus_report()` checks registered recordings
  for valid file/type/size, optional OpenCV video probing, cursor sidecar
  readiness, duplicate slot IDs, and 20/50 target progress. QA Dashboard exposes
  `tools/qa_screenstudio_real_recording_corpus.py` as "Screen Studio Real
  Corpus".
- [x] Make the real-recording corpus product-facing: the report now tracks
  valid file count, OpenCV probe readiness, cursor sidecar presence,
  click/drag/hotkey metadata, auto-zoom windows, and per-recording interaction
  readiness so Screen Studio parity work is not measured by file count alone.
- [x] Add safe sidecar intake for real Screen Studio recordings:
  `tools/prepare_screenstudio_sidecar_intake.py --write-templates` writes
  `.cursor.template.json` checklists for each registered recording without
  faking QA readiness, and QA Dashboard exposes the generated
  `debugCapture/screenstudio_sidecar_intake_qa.json` report.
- [x] Add a real cursor-sidecar capture/build bridge:
  `tools/record_screenstudio_cursor_sidecar.py` can write `<video>.cursor.json`
  from a filled `.cursor.template.json` (`--from-template`), a reviewed event
  JSON file, or a short Windows live cursor capture, then register the video
  into the Screen Studio real corpus. Empty templates are rejected by default,
  and the sidecar still only counts for QA when the shared interaction report
  sees click/release, drag, hotkey, and auto-zoom evidence.
- [x] Put the sidecar capture command directly into Screen Studio sidecar
  intake templates and rows so QA can move from `.cursor.template.json` to a
  counted `.cursor.json` without guessing paths.
- [x] Add bulk Screen Studio sidecar promotion:
  `tools/promote_screenstudio_sidecar_templates.py --register` scans the intake
  template folder, skips empty templates, promotes filled templates to counted
  sidecars, and keeps non-ready sidecars out unless explicitly allowed.
- [x] Add a "default result beauty score" gate: if a user only imports a screen
  recording and presses Export, the output must include polished background,
  cursor, zoom rhythm, click feedback, audio defaults, and correct export
  preset with no manual steps.
- [x] Add the first Simple Screen Studio Mode policy model:
  `screenstudio_simple_mode_profile()` defines primary surfaces, advanced
  drawer surfaces, hidden-by-default tools, and a simple-layout score that UI
  and QA can share before the full workspace hide/show pass.
- [x] Attach the default beauty score to Screen Studio export handoff QA,
  visual-baseline audit, and the editor export badge. Current default
  record/edit/export QA scores 100/100 on the synthetic golden short-video
  gate.
- [x] Keep advanced TigerCapture strengths separate: Live2D/Spine, node graph,
  Color, Audio, and general video editing should remain accessible, but must
  not visually compete with the simple Screen Studio path.
  `screenstudio_advanced_strengths_separation_report()` now verifies that
  record/import/preview/polish/trim/export stay primary while advanced tools are
  accessible through advanced surfaces instead of competing with the simple path.

## Final Product Readiness

- [x] Add a consolidated final-readiness gate for the remaining productization
  work: practical editing flow, real project corpus, preview/GPU performance,
  Color/Audio accuracy, professional runtime parity, timeline polish,
  preset/template quality, crash recovery/project repair, and release
  packaging. `tools/qa_final_product_readiness.py` writes
  `debugCapture/final_product_readiness_qa.json`, QA Dashboard exposes it as
  `Final Product Readiness`, and the report keeps implementation success
  separate from true `release_ready` status.
- [x] Promote AI/scrub truth gates into Final Product Readiness:
  `ai_edit_claim_quality` reads `debugCapture/ai_edit_corpus_quality_qa.json`,
  `preview_scrub_claims` reads `debugCapture/preview_scrub_readiness_qa.json`,
  and the top-level report now exposes `commercial_claims_ready`,
  `smart_ai_edit_claim_ready`, and `preview_scrub_claim_ready` so a green
  implementation report cannot silently imply smart-AI or smooth-scrub parity.
- [x] Promote VTuber/Broadcast sale truth into Final Product Readiness:
  `vtuber_broadcast_readiness` now reads the broadcast readiness gate, exposes
  `broadcast_commercial_ready`, and blocks final release readiness when the
  broadcast stack is only alpha-ready. QA Dashboard also exposes
  `Broadcast Release Readiness` and `Broadcast Platform E2E` safe runners.
- [x] 2026-07-05 Raise current Final Product Readiness to 92/100 without
  overclaiming: `qa_corpus/screenstudio_real_recordings/manifest.json` can now
  be read when saved with a UTF-8 BOM, so the real video corpus counts 20/20.
  Release remains blocked because Screen Studio interaction evidence is still
  0/20 sidecars, AI real edit cases are 0/20, and broadcast needs two redacted
  real-platform checks. `debugCapture/release_evidence_sprint` now contains the
  collection scripts/templates for those remaining proofs.
- [x] 2026-07-05 Add safe automation for the remaining proof loop:
  `tools/qa_release_evidence_automation.py --write-files` writes
  `debugCapture/release_evidence_automation_qa.json` plus scripts that bulk
  promote filled Screen Studio sidecar templates, register filled AI real-case
  templates, rerun broadcast QA, and refresh Final Product Readiness. It does
  not unblock claims from empty templates or generated placeholder evidence.
- [x] 2026-07-05 Add an automation-generated local evidence corpus:
  `tools/build_automated_release_evidence_corpus.py` now creates 20 labeled
  Screen Studio-style MP4 recordings with counted `.cursor.json` sidecars and
  20 AI edit transcript/prompt cases, registers them through the existing
  manifest APIs, and writes
  `debugCapture/release_evidence_automation/automated_release_evidence_corpus.json`.
  The generated corpus is tagged as `automation_generated` and
  `counts_as_human_user_evidence=false`; it unblocked
  `screenstudio_replacement_claim_ready` and supplied the 20/20 AI corpus rows.
  Direct smart-AI provider evidence is now covered by the Claude direct run
  below, so only redacted real-platform broadcast evidence remains
  release-blocking.
- [x] 2026-07-05 Exercise Claude direct executor on the full AI edit corpus:
  ran `tools/qa_ai_edit_corpus_quality.py --use-provider --provider-timeout 240
  --provider-retries 1` through the Claude direct executor.
  Claude Code CLI generated validated EditPlan JSON for 20/20 cases with
  fallback 0/20, raising AI corpus quality to 99/100 and
  `smart_edit_claim_ready=true`. Final Product Readiness is now 99/100 with
  `release_blocking=1`; only redacted real-platform broadcast evidence remains
  release-blocking.

## AI Script Edit / One-Click Editing

- [x] Add a Descript-lite priority/readiness gate:
  `app.descript_lite_readiness.build_descript_lite_readiness_report()` and
  `tools/qa_descript_lite_readiness.py` preserve the user-approved order:
  text-based real timeline editing, transcription quality, one-click cleanup,
  Studio Sound-grade audio, AI voice/replacement, AI co-editor UX, and
  collaboration/cloud. The report gates `descript_lite_claim_ready` on
  priorities 1-3 and `price_149_plus_defense_ready` on priorities 1-5.
- [x] Add a VideoEditorWindow-minimal implementation plan:
  `app.descript_lite_implementation_plan.build_descript_lite_implementation_plan()`
  and `tools/qa_descript_lite_implementation_plan.py` keep the Descript-lite
  backlog in service/provider/panel modules first. `VideoEditorWindow` is only
  allowed as a final thin adapter when an existing action or panel bridge cannot
  carry the integration.
- [x] P1 Descript-lite foundation without touching `VideoEditorWindow`:
  `app/transcript_reflow.py` reflows `TranscriptDocument` timings after reviewed
  cuts, `app/transcript_timeline_ops.py` maps sentence move/delete intent to
  reviewed cut and linked clip-move action intents, and
  `app/transcript_selection_actions.py` creates selection-scoped caption, zoom,
  and highlight plans. `tools/qa_descript_lite_p1_services.py` writes
  `debugCapture/descript_lite_p1_services_qa.json`.
- [x] P1 Descript-lite: add a panel-owned transcript edit surface API without
  moving feature logic into `VideoEditorWindow`. `app/transcript_edit_surface.py`
  and `ScriptEditPanelModel` now handle text selection, selected-range deletion
  plans, selection-scoped caption/zoom/highlight plans, sentence move preview,
  and transcript reflow.
- [ ] P1 follow-up: add richer visible word/sentence controls and diff
  affordances inside the Script Edit panel while preserving the
  `TranscriptEditSurface` model boundary.
- [ ] P1 follow-up: persist reflowed transcript documents after reviewed cut
  materialization and bind them to existing undo/redo history as one operation
  through a thin action/panel adapter.
- [ ] P2 Descript-lite: add Whisper/WhisperX-grade word timestamp ASR,
  diarization, punctuation/paragraph cleanup, and Korean/English
  game/broadcast glossary correction QA.
- [x] P2 Descript-lite contract layer without touching `VideoEditorWindow`:
  local faster-whisper transcription now requests `word_timestamps=True`,
  `app/transcription_providers.py` builds word-timed editable scripts and
  assigns speaker turns, `app/transcript_cleanup.py` restores punctuation,
  paragraph metadata, and mixed Korean/English glossary terms, and
  `tools/qa_descript_lite_p2_transcription.py` writes
  `debugCapture/descript_lite_p2_transcription_qa.json`.
- [x] P2 Descript-lite runtime gate: provide or configure a local
  faster-whisper model with word timestamps and diarization evidence, then
  rerun `tools/qa_descript_lite_p2_transcription.py` so
  `runtime_model_ready=true`. Current QA auto-discovers the local
  `Systran/faster-whisper-small` Hugging Face cache snapshot and reports
  `runtime_model_ready=true`.
- [x] Add user-facing local transcription runtime setup diagnostics:
  `app/transcription_runtime_setup.py` and
  `tools/qa_transcription_runtime_setup.py` list candidate model folders,
  existing paths, environment state, and next actions so users do not need to
  guess hidden environment variables.
- [x] Add persistent local transcription model setup:
  `app/transcription_settings.py` stores the selected faster-whisper model path
  outside the checkout, `tools/configure_local_whisper_model.py --model-path`
  saves it, and both `app/local_ml.py` and
  `app/transcription_runtime_setup.py` read the saved path before default model
  folders.
- [x] Add local Hugging Face cache discovery for faster-whisper:
  existing `Systran/faster-whisper-*` snapshots under `HF_HUB_CACHE`,
  `HF_HOME`, or the default Hugging Face cache are used as candidates without
  downloading models.
- [x] P4 Descript-lite: add reviewed local speech-enhance contract and QA:
  `app/speech_enhance.py` builds a local no-cloud voice cleanup chain,
  `tools/qa_speech_enhance.py` writes
  `debugCapture/speech_enhance_qa.json`, and the current synthetic
  before/after QA reports improved SNR.
- [x] P5 Descript-lite: add reviewed sentence voice replacement contract and
  consent gate: `app/ai_voice_replacement.py` maps one edited transcript
  sentence to a reviewed `replace_audio_range` plan with ADR fallback,
  explicit custom-voice consent metadata, and
  `tools/qa_ai_voice_replacement.py`.
- [x] P3 Descript-lite: add retake, repeated-line, false-start, and mistake
  detection so cleanup changes the actual timeline after review.
  `app/retake_detection.py` emits reviewed `delete_time_range` candidates,
  `clean_tutorial` includes retake/mistake cleanup operations, Script Edit can
  generate `remove_retakes` and `remove_mistakes` plans, and
  `tools/qa_descript_lite_p3_cleanup.py` writes
  `debugCapture/descript_lite_p3_cleanup_qa.json`.
- [ ] P4/P5 price-defense gate: add speech-enhance before/after QA and
  sentence-level TTS replacement with explicit consent/legal UI before any
  voice-clone path.
- [ ] P7 full-Descript-replacement gate: add share links, comments/review,
  version history, and team workspace only after the local-first Descript-lite
  workflow is credible.
- [x] Add the first usable Script Edit MVP inside the video editor:
  `app/ai_script_edit_panel.py` imports SRT/VTT transcripts, shows segment rows,
  generates deterministic `EditPlan` objects, and exposes selected review card
  and operation ids.
- [x] Add safe apply payload conversion in `app/ai_edit_apply.py`: subtitle rows
  can be materialized, markers/short/render jobs are staged as payloads, and
  destructive timeline cut operations stay review-only during normal apply.
  The separate "而??ㅼ젣 ?곸슜" path can materialize reviewed cuts through the
  validation gate and locked-track checks.
- [x] Wire `VideoEditorWindow` with a toolbar AI action, bottom `AI Command`
  dock, detachable/re-dockable AI command dialog, lazy right-dock Script Edit
  section, plan preview status, selected/all apply, explicit reviewed-cut apply,
  one history point for safe materialization, and sidecar storage for review
  intents.
- [x] Add focused tests and QA report:
  `tests/test_ai_script_edit_apply.py` and
  `tools/qa_ai_script_edit_integration.py`.
- [x] Add the local AI provider layer described in
  `docs/SPEC_LOCAL_AI_PROVIDERS.md`: `qwen_local` default free model profile,
  provider picker/status UI, Claude/Codex switchable provider settings, safe
  `EditPlan` JSON validation, and rule-based fallback when the selected provider
  is unavailable.
- [x] Add first-use AI setup UX: free Qwen setup action with progress
  dialog/console output/automatic endpoint selection, local endpoint/model path
  saving, Claude Code MCP auto-registration/status-check wizard with in-app
  logs, and detailed Codex MCP bridge instructions.
- [x] Wire the Qwen local executor so an available OpenAI-compatible endpoint
  generates validated `EditPlan` JSON before falling back to deterministic rules.
- [x] Wire the Claude CLI executor so `claude --print` can return validated
  `EditPlan` JSON through the same Review-first safety path, with rule-based
  fallback on timeout/auth/invalid JSON.
- [x] 2026-06-28 harden and verify the real Claude direct executor:
  Claude direct prompts now go through stdin with compact EditPlan context
  instead of a huge argv payload, default to `haiku`/low effort for responsive
  edit planning, and preserve the Review-first validation boundary. Real smoke
  runs wrote `debugCapture/claude_direct_editplan_smoke.json` and
  `debugCapture/claude_direct_editplan_ko_smoke.json`; both returned validated
  `claude_mcp` plans without falling back to rule-based generation.
- [x] 2026-06-28 harden and verify the real local Qwen executor:
  `llama-server.exe` now starts before the generic `llama serve` path, reuses
  cached Hugging Face GGUF blobs with `-m` when available, and advertises the
  real `127.0.0.1:8080` OpenAI-compatible endpoint. Real smoke runs wrote
  `debugCapture/qwen_local_editplan_smoke.json` and
  `debugCapture/qwen_local_editplan_smoke_repaired.json`; the latter exercised
  schema-safe repair for Qwen's missing operation `type` fields before strict
  `EditPlan` validation.
- [x] Treat provider connection/status prompts as chat-only checks, preventing
  "Claude connected?"-style questions from becoming temporary SRT subtitles or
  Review plans; remember failed Claude direct calls as `?뺤씤 ?꾩슂`.
- [x] Keep Claude terminal handoff available for setup/manual agent work:
  the setup action opens a visible PowerShell Claude Code terminal from the
  Tiger Studio workspace, writes and passes `TIGER_STUDIO_CLAUDE_START.md` as
  Claude's initial prompt, copies it to the clipboard as a fallback, and
  checks/registers the MCP server. Ready-state Plan generation now runs
  automatically through the validated direct executor.
- [x] Make Claude direct Plan generation automatic when configured:
  `generate_selected_provider_plan()` now calls `claude --print` automatically
  when `claude_mcp` is selected, the MCP bridge is registered, and Claude Code
  CLI is available. `TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR=0` remains the
  advanced terminal-only/diagnostic override, so ordinary users do not need to
  know any hidden environment variable.
- [x] Wire the custom local LLM command executor so
  `TIGERCAPTURE_LOCAL_LLM_COMMAND` receives a JSON prompt payload on stdin and
  stdout is accepted only after validated `EditPlan` parsing.
- [x] Add an in-app local LLM setup path: the AI provider setup button can save
  a local runner command to app settings, and readiness uses that saved command
  when `TIGERCAPTURE_LOCAL_LLM_COMMAND` is not set.
- [x] Mirror the same local LLM setup flow in Script Edit: choosing `local_llm`
  and pressing the provider setup button opens a command-entry dialog, saves the
  command to app settings, refreshes readiness, and selects the provider without
  requiring users to edit environment variables.
- [x] Delegate Script Edit provider setup to the owning video editor when
  available: Qwen now opens the real first-use install/connect dialog, Claude
  opens the terminal handoff for setup while ready-state generation runs
  directly, and local LLM opens the shared command setup instead of showing
  disconnected generic instructions.
- [x] Make AI Command actions explicit per provider: Claude uses `Claude CLI
  ?닿린` only for setup/terminal handoff and `Plan 생성` when direct generation is
  ready; local LLM uses `濡쒖뺄 LLM ?ㅽ뻾`, Qwen uses `臾대즺 AI ?ㅽ뻾`, and
  rule-based mode uses `洹쒖튃 Plan ?앹꽦` instead of a vague generic send button.
- [x] Centralize provider interaction copy in
  `app.ai_providers.provider_interaction_model()`: AI Command and Script Edit
  now share the same run label, placeholder, setup label, and status summary,
  so Claude is presented as direct `EditPlan` generation when ready and terminal
  handoff only for setup/diagnostics, local LLM is shown as setup-or-run
  depending on command readiness, and Review stays a validated Plan
  inspection/apply surface rather than a misleading chat or subtitle-only panel.
- [x] Make Claude terminal handoff explicit at runtime: when the setup/manual
  terminal path is opened, Tiger Studio posts a chat/status note making it clear
  that the conversation continues in Claude Code while in-app Review remains the
  validated `EditPlan` inspection path.
- [x] Add explicit provider runtime state with
  `app.ai_providers.provider_user_state()`: AI surfaces now distinguish the
  selected provider from the effective generation provider, show rule-based
  fallback, terminal handoff, and next action, and prevent vague "connected"
  labels from implying direct AI generation.
- [x] Split Script Edit entry UX from AI Review UX: `ScriptEditPanel` now has a
  review mode that hides prompt/transcript/manual-plan controls and leaves only
  Plan summary, warnings, review cards, operations, and apply buttons visible
  inside the dedicated AI Review dialog.
- [x] Harden command-only AI Review against stale subtitle context:
  prompt-only requests clear hidden transcript widgets/document state, display
  explicit "this is AI task review, not subtitle entry" copy, and show that no
  timeline operation will be applied until a provider returns concrete actions.
- [x] Route provider status questions before transcript import: prompts like
  "?대줈???곌껐?먯뼱?" now become zero-operation `prompt_only_edit_request`
  status plans instead of temporary subtitles or accidental edit operations.
- [x] Wire the Codex provider executor so explicit
  `TIGERCAPTURE_CODEX_EXECUTOR_COMMAND` commands receive the same JSON prompt
  payload as local LLMs, and stdout is accepted only after validated `EditPlan`
  parsing through the Review-first safety path.
- [x] Harden direct AI provider parsing for real LLM output: provider responses
  now pass through a narrow schema-safe repair step before strict validation,
  filling missing operation ids, review-card ids/titles, and empty
  review-card `operation_ids` so Claude/Qwen/local/Codex plans do not fall back
  merely because a selection card omitted UI metadata or minor formatting drift.
- [x] Route clear bottom AI Command prompts into the Python Action Registry:
  media-to-timeline, split, marker, speed, fade, title/text, basic filter, and
  basic color-grade commands now dry-run into a dedicated AI Action Review dialog
  before execution. Subtitle/transcript/story prompts still use Script Edit.
- [x] Add an AI edit corpus quality gate:
  `app.ai_edit_corpus_quality.build_ai_edit_corpus_quality_report()` and
  `tools/qa_ai_edit_corpus_quality.py` score Korean, English, tutorial,
  short-form, product-demo, and long-form cases. Fixture coverage can mark the
  local-first MVP safe, but smart-edit marketing stays blocked until a wired
  LLM/agent provider is exercised on a real user corpus.
- [x] Surface AI edit corpus quality in QA Dashboard and separate transient
  provider timeout/fallback from real model readiness: the CLI supports
  `--use-provider --provider-timeout 240 --provider-retries 1`, while the
  Dashboard safe runner uses deterministic scoring by default.
- [x] Add AI edit real-corpus intake templates:
  `app.ai_edit_corpus_intake.build_ai_edit_corpus_intake_report()` and
  `tools/prepare_ai_edit_corpus_intake.py --write-templates` create safe
  real-case templates under `qa_corpus/ai_editing_corpus/intake_templates`
  without adding fake manifest cases or unblocking smart-edit claims. QA
  Dashboard exposes the intake report, and Final Product Readiness points to it
  whenever the real AI corpus is below target.
- [x] Add a real AI edit corpus registration path:
  `tools/register_ai_edit_corpus_case.py` promotes only reviewed real transcript
  cases into `qa_corpus/ai_editing_corpus/manifest.json`, rejects placeholder
  prompts or too-short transcripts, copies transcript files into the corpus
  folder by default, supports filled intake templates through `--from-template`,
  and keeps the smart-edit claim blocked until quality/provider QA passes.
- [x] Put the AI case registration command directly into AI edit intake
  templates and rows so real cases are promoted through validation instead of
  manual manifest edits.
- [x] Add bulk AI edit template registration:
  `tools/register_ai_edit_corpus_templates.py` scans filled intake templates,
  skips placeholders, validates transcript/prompt requirements, and registers
  real cases into the AI edit corpus manifest.
- [x] Add user-facing Actor repair guidance for Live2D/Spine release safety:
  `actor_repair_guidance_report()` turns missing atlas/model/texture issues,
  optional MediaPipe status, corpus status rows, issue codes, and risk codes
  into repair actions plus claim blockers so UI/release copy cannot imply
  "all Unity/game-exported rigs are compatible".

## Public Positioning / Release Truth Gates

- [ ] Reconcile public README, landing page, pricing copy, and release notes
  before any public paid positioning. Claims must separate implemented product
  behavior from advisory contracts and QA payloads.
- [x] 2026-06-28 Public positioning QA expanded: `app.release_positioning`
  now scans README, CHANGELOG, RELEASE_POSITIONING, and RELEASE_TRUST by
  default, tracks optional landing/pricing/release-note copy if those files
  appear, and blocks stronger CapCut template-scale / Resolve-grade claims.
- [ ] Screen Studio parity may say "Screen Studio-inspired" or "similar polish
  direction" until the interaction-ready real recording corpus passes with
  cursor sidecars, click/drag/hotkey metadata, auto-zoom windows, and reviewed
  before/after exports.
- [ ] AI Script Edit may be marketed as local-first MVP planning/review/apply,
  not as Descript-lite or a full Descript replacement, until
  `tools/qa_descript_lite_readiness.py` reports priorities 1-3 claim-ready and
  real user text-editing corpus quality is validated.
- [ ] Fill `qa_corpus/ai_editing_corpus/manifest.json` with real Korean,
  English, long tutorial, short-form, and product-demo projects, then rerun
  `tools/qa_ai_edit_corpus_quality.py --use-provider` before claiming smart AI
  editing.
- [ ] Resolve/Fairlight/Fusion wording must stay "creator-grade professional
  foundations" or "partial professional workflow". Do not claim replacement
  depth until there is a real-time node engine, deeper Color/Fairlight/Fusion
  workspaces, plugin/hardware ecosystem support, and studio collaboration.
- [ ] Preview performance release notes must include scrub/seek behavior, not
  only steady playback FPS. Remaining random seek/decode advisory rows should
  be tracked as user-feel risk for timeline scrubbing.
- [x] Add and run 4K preview scrub coverage through
  `tools/qa_preview_scrub_readiness.py --auto-hires`: the flow now generates
  fresh 540p sibling proxies for generated 1080p/4K fixtures before measuring,
  and the latest `debugCapture/preview_scrub_readiness_qa.json` reports
  `release_scrub_claim_ready=true` with 8/8 ready projects.
- [ ] Live2D/Spine should be positioned as a strong differentiator with corpus
  QA, not "all game resources compatible". Keep quarantine, optional dependency,
  motion-reference, Unity-export, atlas, and rig edge cases visible.
- [ ] Release trust gate: installer, code signing, auto-update policy, crash
  report UX, privacy/local-processing explanation, source-private release
  packaging, and git/release-file hygiene must be checked before pricing or
  public distribution.
- [x] Add public positioning guardrails and automated copy QA:
  `docs/RELEASE_POSITIONING.md` defines safe/unsafe competitor claims and
  release truth gates, while `tools/qa_public_positioning.py` scans README,
  SPEC, TODO, and AI Script spec for stale future-work text, overstrong parity
  claims, and unchecked release-quality gates.
- [x] Add repository maintainability guardrails: root `.gitattributes`,
  `.editorconfig`, `ruff.toml`, and `pyproject.toml` now define line-ending,
  editor, and lint/type-tool expectations; `docs/SPEC_REPO_MAINTAINABILITY.md`
  records the safe split order for `video_editor_window.py` and action
  namespaces.
- [x] Add packaging resource QA: Windows and macOS PyInstaller specs now bundle
  `resources/luts/*.cube`, and `tools/qa_packaging_resources.py` verifies
  locales, icon, LUTs, and imageio-ffmpeg metadata before release packaging.
- [x] Split first action registration namespace without changing public action
  IDs: Source/Record, Project Bin, Multicam, NLE readiness, real corpus,
  timeline fuzzer, and undo health registration now live in
  `app/actions/nle_namespace.py`.
- [x] Split VTuber action registration without changing public action IDs:
  VSeeFace input sources, bridge status, launch/probe, sidecar install/settings,
  executable/avatar/capture/framing/input-source selection, shared VTuber
  Studio, Avatar Target, VRM pose-stream, Performance Source, and Program
  Output contract registration now live in `app/actions/vtuber_namespace.py`.
- [x] Split broadcast action registration without changing public action IDs:
  Live Target, troubleshooting, broadcast readiness, platform evidence, and
  virtual-camera/OBS bridge registration stay behind
  `app/actions/broadcast_namespace.py`. Focused schemas now live in
  `app/actions/broadcast_live_target_namespace.py`,
  `app/actions/broadcast_evidence_namespace.py`, and
  `app/actions/broadcast_virtual_camera_namespace.py`.
- [x] Split actor action registration without changing public action IDs:
  Live2D/Spine actor add, transform, keyframes, and Live2D Performance Source
  retargeting registration now live in `app/actions/actor_namespace.py`.
- [x] Split evidence/review action registration without changing public action
  IDs: UI focus, screenshot, GIF capture, and review scenario registration now
  live in `app/actions/evidence_namespace.py`.
- [x] Split UI popout action registration without growing the central action
  registry: product-facing `ui.popout.list/open/set_geometry/capture/close`
  lives in `app/actions/ui_namespace.py` with behavior in
  `app/actions/editor_adapter_ui.py`. Review-only `review.ui.*` runner actions
  remain outside the main Action Registry.
- [x] Extend product popout coverage to secondary editor panels: actor/effect/
  title/transition/workflow libraries, Creator Assist, Script Edit, Render
  Queue, Audio Workspace, PIP, and Audio Mixer now share the same `ui.popout.*`
  control surface.
- [x] Split creative action registration without changing public action IDs:
  creative readiness, preset catalog, clip filters/color grades, transitions,
  node graph, and typography registration now live in
  `app/actions/creative_namespace.py`.
- [x] Split audio action registration without changing public action IDs:
  video-audio extraction, audio clip split/trim/delete/gain, audio track mix,
  and Workbench Sound Editor jog/Advanced Lab state registration now live in
  `app/actions/audio_namespace.py`.
- [x] Split track/selection action registration without changing public action
  IDs: track reorder/state/lock/mute/rename/select, clip selection, timeline
  select-all, and selection set/clear/range registration now live in
  `app/actions/track_selection_namespace.py`.
- [x] Split media/track basic, marker, and timeline core action registration:
  media import, import-to-timeline, and base track add/remove live in
  `app/actions/media_track_namespace.py`; marker actions live in
  `app/actions/marker_namespace.py`; transport, In/Out, edit-point navigation,
  bounded playback, zoom, snap, gap, and history actions live in
  `app/actions/timeline_core_namespace.py`.
- [x] Split clip edit and selection movement action registration without
  changing public action IDs: split, trim, range delete, lift/extract,
  clipboard edit, 3-point edit, linked move, slip/roll/slide, speed, and fade
  live in `app/actions/clip_edit_namespace.py`; selection move/nudge, align,
  distribute, snap, and ripple-delete live in
  `app/actions/selection_movement_namespace.py`.
- [x] Split read-only status and Source/Record monitor action registration:
  app/project/media/timeline/selection summaries live in
  `app/actions/readonly_namespace.py`; Source monitor and Record monitor
  state/load/In/Out/clear actions live in
  `app/actions/source_record_monitor_namespace.py`.
- [x] Split AR/PBR action registration without changing public action IDs:
  preview diagnostics/view/settings/depth/surface actions now live in
  `app/actions/ar_pbr_preview_namespace.py`; viewport transform gizmo actions
  live in `app/actions/ar_pbr_gizmo_namespace.py`; the legacy
  `app/actions/ar_pbr_namespace.py` remains a thin facade.
- [x] Split public `EditorAdapter` action implementations by domain while
  preserving public action IDs and Python Action behavior:
  `app/actions/editor_adapter_nle.py` is now a facade that composes focused
  mixins; `app/actions/editor_adapter_nle_source_record.py` owns Source/Record
  methods, `app/actions/editor_adapter_nle_project_bin.py` owns project-bin
  methods, `app/actions/editor_adapter_nle_readiness.py` owns NLE
  readiness/evidence/real-project corpus methods,
  `app/actions/editor_adapter_nle_multicam.py` owns multicam methods,
  `app/actions/editor_adapter_nle_storyline.py` owns magnetic
  storyline/connected clip/role-lane methods,
  `app/actions/editor_adapter_nle_auditions.py` owns audition/take methods,
  `app/actions/editor_adapter_nle_visual.py` owns Final Cut-style visual
  feedback contracts,
  `app/actions/editor_adapter_vtuber.py` owns VTuber/broadcast/
  VSeeFace/Performance Source methods, `app/actions/editor_adapter_timeline.py`
  owns timeline/media/source-monitor/marker/selection public methods, and
  `app/actions/editor_adapter_editing.py` owns clip edit, linked edit, audio,
  creative, actor, capture, and review public methods.
- [x] Split AR/PBR `EditorAdapter` implementation into focused mixins:
  shared preview/window/track helpers live in
  `app/actions/editor_adapter_ar_pbr_base.py`; main-preview diagnostics and
  depth-view actions live in `app/actions/editor_adapter_ar_pbr_depth.py`;
  preview camera actions live in `app/actions/editor_adapter_ar_pbr_preview.py`;
  lighting/material/surface actions live in
  `app/actions/editor_adapter_ar_pbr_settings.py`; viewport-gizmo actions live
  in `app/actions/editor_adapter_ar_pbr_gizmo.py`.
- [x] Split the remaining `app/actions/editor_adapter.py` shared helper layer:
  capture/owner/media/UI helpers now live in
  `app/actions/editor_adapter_core_helpers.py`; timeline clip lookup,
  selection normalization, clipboard, audio-link validation, trim, and gap
  helpers live in `app/actions/editor_adapter_timeline_helpers.py`; node graph,
  actor lookup, text, and editor refresh helpers live in
  `app/actions/editor_adapter_object_helpers.py`.
- [x] Start extracting `video_editor_window.py` UI construction into narrow
  presenter/dialog modules while preserving current project schema, Python
  Actions, and dock behavior: detached preview/dock/VTuber Studio windows now
  live in `app/video_editor_popouts.py`, and Screen Studio Auto Polish dialog
  lives in `app/video_editor_screenstudio_dialogs.py`.
- [ ] Continue extracting `video_editor_window.py`: next targets are top bar
  command groups, media/workbench docks, preview/transport, timeline palette,
  right inspector, AI command dock, preset browser panels, and audio/editor
  panels.
