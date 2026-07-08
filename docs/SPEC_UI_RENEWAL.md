# TigerCapture Studio UI Renewal Plan

## Purpose

TigerCapture Studio's review and product catalog materials must be based on the
real editor UI. The immediate priority is therefore to renew the live editor
surface first, then resume review automation and PPT/HTML generation after the
renewed UI becomes the visual source of truth.

The target is a professional post-production tool that feels closer to a clean
product catalog mockup while remaining fully functional: icon-first controls,
real imported media on the timeline, compact drag-and-drop palettes, clear
feature-specific workspaces, and no fake composited editor scenes.

## Current Decision

- This document is the persistent handoff anchor. Do not rely on chat memory for
  the relationship between UI renewal and review automation.
- `docs/UI_RENEWAL_THREAD_HANDOFF.md` is the operational handoff for any new
  Codex thread that continues UI renewal while the current thread owns review
  automation.
- `docs/UI_RENEWAL_EVIDENCE_INDEX.md` is the current feature-capture artifact
  index. Review automation must read it before selecting screenshots for
  detailed/evidence slides.
- UI renewal comes before review automation polish.
- Review/PPT/catalog generation remains on TODO until the editor UI is stable.
- Screenshots for reviews must come from actual running TigerCapture UI.
- Generated images may be used only as design references or outer catalog
  presentation frames, not as fake evidence of implemented editor features.
- Sample review/editing media should come from:
  `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`

## Implementation Notes

- 2026-07-02 left-rail pass: `app/media_pool.py` now uses the shared UI font
  stack, lower-contrast icon buttons, thinner borders, denser list rows, and
  a calmer selected-media card. The lightweight QA capture
  `tools/qa_ui_renewal_left_rail.py` loads real files from the YouTube Imports
  folder first and writes
  `debugCapture/ui_renewal_left_rail_round/media_pool_left_rail.png`.
- 2026-07-02 preset-browser pass: existing preset filter chrome in
  `app/video_editor_window.py` was tightened without adding new UI surfaces:
  the category filter is icon-only with hover text, preset search is shorter,
  and the preset scroll grid uses the shared thin scrollbar style instead of
  overlapping local scrollbar rules.
- 2026-07-02 color grading soft-glass controls pass:
  the user-approved generated color-grading reference is now implemented as
  real right-side Workbench UI in `app/video_editor_window.py`. The color node
  inspector uses one soft-glass Color Wheels deck, code-native icon controls,
  compact RGB readout pills, `Light` and `Primary` two-column slider cards, and
  a vertical `QScrollArea` wrapper. The wrapper is required: without it, the
  Workbench dock compresses the multi-section color controls and causes wheel /
  slider overlap in short editor layouts. Current verified artifact:
  `debugCapture/ui_renewal_color_soft_glass_controls_round_4/editor_color_dock_action.png`.
- 2026-07-02 color grading reference-ratio follow-up:
  the first soft-glass pass was not close enough to the selected reference
  because it treated color grading as a narrow inspector. Color-node selection
  now temporarily gives the top Workbench a wider stretch and larger minimum
  width, trims the compare/preset row, and restores larger Color Wheels so the
  color panel reads as a real grading console. This still remains a main-editor
  compromise: the exact reference layout should be implemented as a dedicated
  Color page or Color popout because the reference is a wide full-panel console,
  not a side dock. Current verified artifact:
  `debugCapture/ui_renewal_color_soft_glass_controls_round_5/editor_color_dock_action.png`.
- 2026-07-02 color grading slider-shape follow-up:
  Light/Primary controls in the right-side Color Grading Workbench now use a
  panel-local painted `_SoftColorSlider` instead of the native stylesheet
  slider. This is intentional: the selected reference depends on thin rounded
  rails and circular metal knobs, while native `QSlider` rendered too boxy in
  captures. Text labels are borderless, value readouts remain subtle pills, and
  temperature/tint use gradient rails. Current verified artifact:
  `debugCapture/ui_renewal_color_soft_slider_round_2/editor_color_dock_action.png`.
- 2026-07-02 color grading wheel-shape follow-up:
  the shared `app.color_page_window._Wheel` painter has been moved toward the
  selected reference instead of leaving the old icon-like tile. The wheel now
  draws as a circular grading instrument with no square backdrop, a larger
  dark shell, thin hue ring, quiet luma rim, precise crosshair, and small
  graphite center puck. The main-editor Color Grading Workbench uses slightly
  larger 110px wheel instances while the Color page inherits the same painter.
  Current verified artifact:
  `debugCapture/ui_renewal_color_wheel_round_3/editor_color_dock_action.png`.
- 2026-07-02 editor standard slider pass:
  horizontal editor sliders should use `app.studio_slider.StudioSlider` instead
  of local QSS strings or panel-local subclasses. The first standardization
  pass applies it to Color Grading, LUT/luma controls, Typography/PIP rows,
  Workbench inspector and node-parameter controls, the full Color page, Audio
  Mixer PAN, and Live2D transform/parameter controls. Vertical mixer faders
  remain separate because they have a distinct audio-console role. Current
  verified artifacts:
  `debugCapture/ui_renewal_standard_slider_round_1/editor_color_dock_action.png`,
  `debugCapture/ui_renewal_standard_slider_round_1/workbench_mask_tab_action.png`,
  and
  `debugCapture/ui_renewal_standard_slider_round_1/editor_audio_mixer_action.png`.
- 2026-07-02 workbench pass: `app/workbench_panel.py` now uses the shared UI
  font stack, lower-contrast tabs/cards/buttons, calmer VFX graph strip chrome,
  and ASCII `x` speed readouts instead of the multiplication symbol that looked
  broken in some remote/font contexts. `tools/qa_ui_renewal_workbench.py`
  captures clip and node-graph Workbench states side by side at
  `debugCapture/ui_renewal_workbench_round/workbench_clip_and_node.png`.
- 2026-07-02 Live2D Performance Source pass:
  `tools/qa_ui_renewal_actor_workspaces.py` now builds the actor evidence from
  real action-registry steps: real YouTube Imports media, `actor.add`,
  `actor.set_keyframes`, `vtuber.performance_source.add_clip`, and
  `actor.live2d.apply_performance_source`. The evidence capture must show the
  composited actor, actor lane keyframes, input-only performance source clip,
  and Workbench mapping/key metadata. Transient editor toasts are hidden before
  capture so product evidence does not look like a debug session.
- 2026-07-02 lane identity pass: Timeline row labels now use display-order lane
  numbers instead of internal ids, so real captures show stable `V1`, `PS1`,
  `L1`, and `S1` labels even when the underlying action system creates tracks
  in a different order. The Live2D actor Workbench evidence card was also
  flattened from a boxed QA card into a thinner production strip. Current
  reference artifact:
  `debugCapture/ui_renewal_workbench_actor_strip_round_2/editor_live2d_actor_action.png`.
- 2026-07-02 native Live2D Viewer evidence pass:
  `tools/qa_ui_renewal_actor_workspaces.py --open-live2d-viewer` opens the
  linked Live2D Viewer from the same real action flow, hides transient loading
  chrome before capture, and verifies `live2d_viewer_screenshot`. The viewer
  bottom action was shortened from `Performance Source Mapping` to `Map Source`
  to avoid clipping. Keep this opt-in rather than default QA until native
  shutdown stability is proven across repeated runs. Current reference artifact:
  `debugCapture/ui_renewal_live2d_viewer_capture_round_2/live2d_viewer_action.png`.
- 2026-07-02 isolated Live2D Viewer follow-up:
  `tools/qa_ui_renewal_live2d_viewer_isolated.py` re-ran the real
  YouTube-Imports + `actor.add` + `actor.set_keyframes` + Performance Source
  action flow and captured nonblank Viewer/editor/workbench artifacts at
  `debugCapture/ui_renewal_live2d_viewer_isolated_round_2/live2d_viewer_action.png`
  with subprocess return code `0`. Keep native Viewer capture opt-in until
  repeated runs prove shutdown stability; do not fold it into default QA yet.
- 2026-07-02 native Live2D Viewer polish pass:
  `app/live2d/live2d_viewer.py` now follows the renewed main-editor chrome:
  shared font stack, low-saturation graphite buttons, thin splitters, a subtly
  framed viewport, compact bottom transport/background controls, neutral
  sliders/lists, and calmer inspector value colors. Verified with real
  YouTube Imports media and the action-backed Live2D/Performance Source flow at
  `debugCapture/ui_renewal_live2d_viewer_polish_round_1/live2d_viewer_action.png`.
- 2026-07-02 history snapshot guardrail:
  undo/redo snapshots must ignore Qt render caches such as `QPixmap`, `QImage`,
  `QIcon`, and clip thumbnail caches. Real editor action QA can otherwise fail
  on non-picklable render objects even when the feature itself works.
- 2026-07-02 refactor guardrail pass: preset-browser style constants and pure
  QSS/icon helpers were extracted to
  `app/video_editor_preset_browser_style.py`, and the searchable preset browser,
  scroll-grid, inspector, plus animated preview swatch widgets were extracted
  to `app/video_editor_preset_browser_widgets.py`. Future preset card/panel work
  should continue this extraction path and avoid adding inline QSS or new UI
  surfaces directly to
  `app/video_editor_window.py`.
- 2026-07-02 preset semantic icon pass:
  `app/video_editor_preset_cards.py` now selects compact tile icons from preset
  kind/tags/payload instead of rotating decorative symbols. Title, transition
  subtype, workflow, audio, chroma/keying, node, color, actor, speed, blur, and
  clip-effect presets have distinct low-saturation line icons while preserving
  the icon-first left-dock design. Verified at
  `debugCapture/ui_renewal_preset_semantic_icons_round_2/left_dock_titles_browser.png`
  and
  `debugCapture/ui_renewal_preset_semantic_icons_round_2/left_dock_transitions_browser.png`.
- 2026-07-02 UI renewal helper extraction pass:
  the current live editor is no longer only `app/video_editor_window.py`.
  Command-bar helpers live in `app/video_editor_command_bar.py`, Timeline
  palette tile helpers live in `app/video_editor_timeline_palette.py`, layout /
  scrollbar / splitter constants live in `app/video_editor_layout_specs.py`,
  compact AI command dock style lives in `app/video_editor_ai_command_dock.py`,
  preset cards/panels live in `app/video_editor_preset_cards.py`, preset
  browser style/widgets live in `app/video_editor_preset_browser_style.py` and
  `app/video_editor_preset_browser_widgets.py`, detached popouts and VTuber
  Studio live in `app/video_editor_popouts.py`, Screen Studio Auto Polish
  dialogs live in `app/video_editor_screenstudio_dialogs.py`, and audio renewal
  style tokens live in `app/video_editor_audio_style.py`. New work in these
  domains should extend those modules rather than adding another large UI block
  directly to `app/video_editor_window.py`.
- 2026-07-02 Timeline review framing pass:
  `app/video_editor_window.py` now has a timeline-local `Review Frame` icon tool
  and internal `_apply_timeline_review_framing` helper. The helper frames the
  Timeline around the current playhead/edit area at roughly a 12-second span,
  while preserving the left track header for early edits. The cut/edit QA now
  imports real YouTube Imports media, splits the clip, adds a marker, applies a
  transition, selects the adjacent clip, applies review framing, and captures
  the resulting real editor state at
  `debugCapture/ui_renewal_timeline_review_framing_round_3/editor_cut_edit_action.png`.
- 2026-07-02 Color grading density decision:
  keep the compact Timeline `Grade Layer` rail. Taller dedicated grade rows
  would make screenshots less dense without adding enough feature evidence. The
  better improvement is in the right-side Color Grading Workbench, where the
  wheel/scope row now gives wheels more horizontal presence and treats scopes as
  secondary evidence. Verified at
  `debugCapture/ui_renewal_color_workbench_density_round_2/editor_color_dock_action.png`.

## Design Direction

The desired direction is the generated catalog-style TigerCapture mockup:

- Dark professional editor shell.
- Compact top chrome.
- Media pool as a clean left rail with real thumbnails.
- Viewer centered with minimal playback controls underneath.
- Timeline tracks with strong color identity, visible thumbnails, clear
  playhead, markers, keyframes, and edit points.
- Right-side inspector/workbench panels that feel like real production tools,
  not debug tables.
- Feature controls presented as docked palettes or inline node controls instead
  of scattered popups.
- Text minimized in dense chrome; labels appear through tooltips, section
  headers, or expanded states.

Catalog and PPT pages may use a light, art-gallery-like presentation frame, but
the editor screenshot placed inside that frame must be a real capture.

## Generated Reference Characteristics To Follow

The generated reference images are valuable because they define the target
visual language. They are not product evidence, but they are the style guide for
the renewed UI and catalog output.

### Catalog Page Frame

- A large off-white page sits on a dark charcoal stage.
- The page has generous margins, soft rounded corners, and a subtle shadow.
- The page should feel like a product catalog, not a debug report.
- Layout is asymmetric: large calm text area on one side, strong editor/device
  visual on the other.
- Use a thin hairline rule near the top-left for the section label.
- Use a bottom footer line with small metadata such as product name, website,
  and page number.
- Leave real whitespace. Do not fill every area with boxes, tables, or bullets.

Target feeling: a design object or art print, not an internal QA document.

### Typography

- Main titles are large, clean, and quiet. They should feel premium, not loud.
- Prefer modern sans-serif styling for catalog titles.
- Small labels can use compact uppercase metadata style, but only in limited
  places such as section labels and footers.
- Korean and Japanese must not look cramped. Use enough line height and avoid
  dense bullet blocks.
- Avoid permanent button text in dense editor chrome.
- Do not use a monospaced/debug-report look for product-facing pages unless the
  content is intentionally technical evidence.

### Color And Material

Use this approximate palette direction:

- Catalog page: warm off-white, near `#F5F3EF`.
- Outer stage: charcoal/black, near `#1F1F1F`.
- Main editor shell: deep black-blue, near `#070A11` to `#111722`.
- Panel borders: thin cool gray-blue, not heavy boxed outlines.
- Text: near-white for editor labels, muted gray for secondary metadata.
- Accent colors are sparse and meaningful:
  coral/red for playhead or destructive/cut actions,
  violet/purple for actors, AI, or selected states,
  cyan/blue for media, node links, scopes, or active controls,
  amber/yellow for blade/cut/keyframe emphasis,
  green for audio/valid/ready states.

The UI should not become a one-color purple/blue theme. The reference works
because dark neutral surfaces are balanced by small vivid controls.

### Depth And Device Presentation

- Catalog pages may place real editor screenshots inside a MacBook/monitor-like
  frame or floating panel composition.
- The device/frame creates spatial depth, shadow, and premium presentation.
- The screen content inside that frame must be a real TigerCapture screenshot.
- Floating inspector panels are allowed in catalog presentation only when they
  represent real panels or real planned UI surfaces.
- Shadows should be soft and broad, not heavy or cartoonish.

### Editor Shell Characteristics

The real editor should move toward the generated editor screen:

- Top chrome is compact and icon-first.
- Menus are grouped: Project, Create, Actors, View, More, Export.
- Media pool sits as a clean left rail with real thumbnails.
- Viewer is central and visually calm.
- Playback buttons are small, centered, and icon-only.
- Timeline palette uses compact colored icon tiles.
- Timeline tracks use real thumbnails, colored clip bodies, visible playhead,
  edit markers, and keyframe diamonds.
- Right-side inspector/workbench panels look like production controls, not
  spreadsheet/debug tables.
- Node graph, color grading, audio, actor, and 3D workspaces each need their own
  visible control layout.

### Track And Control Visuals

Follow these details from the reference images:

- Clip tracks should be long enough to read as editable media, not tiny slivers.
- Video tracks show thumbnail strips.
- Effect/action tracks use distinct colored blocks.
- Keyframes use small diamonds or precise markers.
- Playhead is a clear red vertical line with a small top marker.
- Node links are thin colored curves or lines.
- Selected nodes/controls have a restrained glow or clear border.
- Buttons are mostly symbols, with text shown through tooltip/hover or expanded
  palettes.
- Collapsed palettes should reveal useful icons, not blank boxes.

### What Not To Copy

Do not copy the generated images blindly where they hide real functionality.

- Do not remove necessary menu items; group them into icon menus or palettes.
- Do not omit real buttons just because the mockup is clean.
- Do not fake node graphs, color panels, Live2D actors, 3D scenes, or timelines.
- Do not use generated editor screens as proof that the app supports a feature.
- Do not keep thick rectangular debug boxes.
- Do not show generic city footage for every feature unless that feature is
  visibly applied to the footage.
- Do not show empty panels, blank editors, color bars, or placeholder test media
  in product-facing output.

### Visual Acceptance Checklist

A renewed screen or catalog slide follows the generated reference only if:

- It has generous spacing and does not feel cramped.
- It has a calm off-white catalog frame or a polished dark editor shell.
- It uses thin lines, soft shadows, and small vivid accents.
- It shows real media and real editor state.
- It preserves all important commands through grouped menus, palettes, or docks.
- It avoids debug-report typography and large raw QA text blocks.
- It can be understood visually before reading the body text.

## Non-Negotiable Rules

1. Do not show an empty editor in catalog/review output.
2. Do not use color bars, placeholder test images, or fake generated editor
   scenes as product evidence.
3. Do not claim a feature visually unless the real UI is showing that feature in
   context.
4. Feature review screenshots must match the feature being explained:
   - Live2D: actor visible, actor lane/keyframes visible, Live2D controls visible.
   - Color grading: before/after or grading controls visible, real footage visible.
   - Node graph: node graph visible, connected nodes visible, node parameters visible.
   - Audio: waveform/mixer/scopes visible.
   - Typography: text clip, animation/keyframe controls, and preview text visible.
   - Transitions/effects: clip boundary or effect lane visible with controls.
   - 3D/AR/PBR: model/scene controls visible, not a generic video timeline.
5. Icon-first controls are preferred in dense editor chrome.
6. Text appears on hover/tooltips or expanded panels, not permanently on every
   button.
7. Drag-and-drop must remain a core interaction for media, effects, titles,
   transitions, actors, nodes, and audio items.
8. Routine automation and QA must not block on modal prompts.
9. Korean/Japanese/English text must be visually checked for font and spacing,
   not only string correctness.

## Scope

### Phase 1: Main Editor Shell

Goal: make the everyday editor view look like the product direction without
breaking existing editing behavior.

Tasks:

- Consolidate top toolbar into grouped icon menus:
  Project, Create, Actors, View, More, Export.
- Keep export as a distinct primary icon button.
- Keep labels hidden in dense chrome; expose names through tooltips.
- Remove visible `Hide` / `Show` text from section headers; use chevrons.
- Make media pool filters icon-only with hover labels.
- Refine media item cards so thumbnails, duration, type badge, and filename fit.
- Keep viewer, playbar, palette, and timeline aligned as one production surface.
- Remove visible toolbar scrollbars where grouping is available.
- Keep real imported media visible in preview and timeline.

Acceptance:

- `tools/qa_editor_e2e_smoke.py --catalog-capture` passes.
- Same QA passes with a real YouTube Imports media file.
- No modal prompt blocks automated capture.
- Screenshot shows imported media in preview, media pool, and timeline.
- No empty editor is used for review/catalog output.

### Phase 2: Timeline And Palette Interaction

Goal: make timeline editing feel like a real NLE while keeping the compact visual
language.

Tasks:

- Keep edit tools as icon tiles: select, blade, ripple, roll, slip, slide, trim,
  nest.
- Keep drag cards for fade, typography, zoom, speed, Spine, Live2D.
- Add/keep hover previews or tooltips for each tile.
- Make track colors consistent across clips, action lanes, keyframes, markers,
  audio, actors, and nodes.
- Preserve the modern blurred-thumbnail look, but make clip duration readable
  through full-width color rails, visible start/end caps, and compact duration
  chips. Thumbnails should sit inset with reduced opacity so they texture the
  clip rather than replacing the clip's color identity.
- Improve timeline zoom defaults for review captures so clip edits are legible.
- Ensure play/stop/previous/next buttons match the chosen icon style.

Acceptance:

- Tools are discoverable without permanent text labels.
- Timeline remains usable at 1440x900 capture size.
- Track clips show real thumbnails when media is imported.
- Cut/effect/keyframe states are visually distinguishable.

### Phase 3: Feature Workspaces

Goal: each major feature needs its own real workspace state, not the same generic
editor screenshot.

Workspaces:

- Color grading: real footage, grade controls, scopes or curve/wheel UI.
- Node graph: real node graph, node connections, selected node parameters.
- Audio editor: waveform, mixer, scopes, extraction/separation controls.
- Typography: text layer, keyframes, animation controls, preview result.
- Transitions/effects: clip boundary, transition/effect strip, parameters.
- Live2D/Spine/NIKKE actors: actor lane, transform/opacity keys, visible actor
  renderer. If renderer is blank or broken, mark blocked instead of showing it.
- AR/PBR/3D: imported model, transform controls, lighting/material inspector.
- Export/render queue: render queue, preview/export parity controls, metadata.

Acceptance:

- Every feature screenshot must show that feature being actively edited.
- If a feature cannot render real pixels, review automation must mark it blocked.
- No feature page should reuse a generic city video timeline unless the feature
  is actually applied to that timeline.
- 2026-07-02 Effect/Transition evidence baseline:
  `tools/qa_ui_renewal_effect_workspace.py` must remain action-backed. It
  imports real YouTube Imports media, splits the clip, applies
  `clip.set_filter`, applies `transition.apply`, sets a real node graph, and
  emits full-editor, Workbench, Timeline, and contact-sheet evidence. Current
  verified contact sheet:
  `debugCapture/ui_renewal_effect_workspace_contact_sheet_round_1/effect_workspace_contact_sheet.png`.

### Phase 4: Secondary Windows

Goal: the same renewal language applies beyond the main editor.

Windows to renew:

- Sound editor.
- Color page/window.
- Node workbench and popout.
- Mask editor.
- Live2D viewer/editor.
- Spine editor.
- AR/PBR 3D compositor.
- Render queue and export dialogs.
- Health/QA dashboards, but only after production editor surfaces are stable.

Rules:

- Prefer docked/inline controls over popups for frequent parameters.
- Popouts must preserve the same visual system as docked panels.
- Dialogs should be compact and functional, not catalog-decorative.

### Phase 5: Typography And Localization

Goal: remove the outdated/AI-document feel caused by poor font, spacing, and
text density.

Tasks:

- Use a consistent UI font stack for Korean, Japanese, Chinese, and English.
- Avoid monospace-like catalog typography inside the actual editor unless it is
  used for metadata/code-style labels.
- Verify Korean and Japanese screenshots visually.
- Check button text overflow at common capture sizes.
- Use shorter labels where text is unavoidable.

Acceptance:

- Korean UI does not look cramped or old-fashioned.
- Japanese UI renders with correct fallback fonts.
- No major controls show mojibake in real screenshots.

### Phase 6: Review Automation After UI Renewal

Goal: resume the automated review system only after the real UI looks good.

Return rule:

- The current UI renewal began because generated review/catalog mockups looked
  better than the live editor screenshots. Those generated images are now design
  references for the real editor UI, not deliverables and not evidence.
- When main editor UI renewal is finished, stop UI-only work and return to review
  automation as the primary task.
- Before regenerating any PPT/HTML/catalog output, re-read the current SPEC/TODO,
  action registry, and available UI surfaces because the product spec changes
  frequently.
- Review automation must drive the live editor through actions, create real
  feature states, capture those states, and then place the real captures into
  catalog/PPT layouts.

Tasks:

- Keep review automation as a separate root from TigerCapture/TigerStudio code.
- Generate three deck modes: summary, detailed feature review, evidence appendix.
- Use only real screenshots/GIFs from automated editor actions.
- Build feature-specific scenario presets that open the correct workspace and
  apply the relevant edit.
- Reject screenshots where the editor is empty, generic, or unrelated to the
  feature page.
- Use screenshot-diff checks for catalog/PPT pages.

Acceptance:

- Detailed decks include relevant editor screenshots on feature pages.
- No generated fake editor image is used as evidence.
- Actor pages are blocked if actual actor rendering is blank or broken.

## Implementation Strategy

Because `app/video_editor_window.py` is still a large monolith, the renewal
should proceed in small, verified passes:

1. Patch a bounded UI surface.
2. Run `py_compile`.
3. Run editor smoke QA.
4. Capture a PNG.
5. Visually inspect the PNG.
6. Only then continue to the next surface.

Avoid large refactors during visual renewal unless a component boundary is
clearly required. After the UI direction stabilizes, extract these areas into
separate modules:

- top command bar,
- timeline tool palette,
- media pool chrome,
- inspector/workbench shell,
- feature workspace presets,
- review capture runner hooks.

First extraction boundary:

- New detached dock/popout UI must go to `app/video_editor_popouts.py`, not back
  into `app/video_editor_window.py`.
- New VTuber Broadcast Studio UI must also go to `app/video_editor_popouts.py`.
- Screen Studio Auto Polish dialog changes must go to
  `app/video_editor_screenstudio_dialogs.py`.
- Python Action and MCP surface contracts must remain stable unless explicitly
  requested; the current action count is expected to stay at 200.
- Future UI work should keep extracting bounded presenters/panels while
  implementing visual changes. Do not grow `video_editor_window.py` for new
  popouts, detached docks, or Screen Studio dialogs.

## UI Work Limits Found During Renewal

- Other Codex thread state is not a reliable source unless the thread is
  explicitly handed off. Use this SPEC, TODO, action contracts, and local code as
  the working source of truth.
- `app/video_editor_window.py` has started splitting into focused modules, but
  it remains very large. Broad visual sweeps can still regress unrelated
  behavior. Prefer one bounded surface per pass with screenshot verification,
  and move new UI surfaces into the appropriate extracted module when the
  boundary is clear.
- Qt offscreen captures in this environment can report zero available font
  families, which makes Korean/Japanese text appear as boxes even when native
  screenshots render correctly. Visual QA for multilingual text should use native
  platform captures.
- Generated catalog images are style references only. They cannot be used as
  proof of editor features, and review automation must reject generic, empty, or
  feature-mismatched captures.
- Actor, Spine, Live2D, AR/PBR, and other renderer-dependent pages must stay
  blocked when the live renderer does not produce the expected pixels. A polished
  layout is not enough evidence.

## QA Commands

Fast syntax check:

```powershell
.\.venv\Scripts\python.exe -m py_compile app\video_editor_window.py app\media_pool.py tools\qa_editor_e2e_smoke.py
```

Default editor smoke:

```powershell
.\.venv\Scripts\python.exe tools\qa_editor_e2e_smoke.py --out-dir debugCapture\ui_renewal_smoke --report debugCapture\ui_renewal_smoke_report.json --catalog-capture
```

Real YouTube Imports media smoke:

```powershell
.\.venv\Scripts\python.exe tools\qa_editor_e2e_smoke.py --out-dir debugCapture\ui_renewal_smoke_youtube --report debugCapture\ui_renewal_smoke_youtube_report.json --import-media "E:\ClaudeCodeApp\GifCam\debugCapture\review_samples\youtube_import_sunset.mp4" --catalog-capture
```

When using the real `YouTube Imports` folder directly, automation must suppress
interactive prompts such as proxy-generation questions.

## Risks

- The editor monolith makes broad visual changes risky.
- High-resolution imports can trigger modal prompts and block automation.
- Large 4K/8K YouTube files can slow capture loops.
- Font fallback can differ between Korean, Japanese, and English screenshots.
- Feature-specific screenshots can drift back into generic timeline captures if
  scenario presets are not strict.
- Review decks can look polished while still lying visually; this must be
  prevented by using real feature states only.

## Current Status

Already started:

- Top command groups are icon-first.
- Export is a distinct primary icon button.
- Timeline palette has been compressed.
- Media pool filters and view buttons are icon-first.
- Collapsible section headers use chevrons instead of `Hide` / `Show`.
- Automated catalog capture suppresses interactive prompts.
- Real YouTube Imports-derived media smoke passes after prompt suppression.
- Workbench node graph parameters were reduced from debug-table rows to compact
  card-like controls and passed node/color-audio regression tests.
- Media Pool now keeps the selected clip as a featured card and uses cleaner
  narrow-list labels with real YouTube Imports verification.
- AI Command is now a thin workbench-attached command rail instead of a taller
  chat block; expanded height is constrained to one compact input row.
- Timeline clip bodies now get a subtle full-span wash so long clips read as
  occupying the whole visible track while keeping the single leading thumbnail.
- Timeline default density is higher (`52 px/s`) and the ruler/track typography
  now uses a slimmer catalog-style treatment.
- Timeline empty space now paints as a subtle editing grid instead of a dead
  black panel; this keeps the lower editor surface useful in screenshots even
  when only a few tracks are loaded.
- Preset libraries for effects, titles, transitions, and workflows share a
  calmer icon-palette grid with more left/right breathing room.
- Workbench node graph cards now use compact preview strips, muted borders,
  shallow shadows, restrained node colors, smaller ports, and thin amber/blue
  links instead of the older large debug-like cards.
- Node graph effect parameters now use a compact two-column inspector strip, so
  selected-node controls stay visible without consuming the whole Workbench.
- The FX Workbench page no longer reserves an empty trailing spacer below the
  node graph; the graph and inspector fill the Workbench instead of leaving a
  dead black gap above the AI command rail.
- Node graph toolbar controls are grouped into compact icon palettes instead of
  one flat row, and disabled future-only layer controls are hidden from the
  default chrome.
- Node graph workflow presets now add real connected node chains:
  color polish, glow/mask, and HDR prep. These are UI workflow helpers, not fake
  catalog evidence.
- Timeline track rows now use wider V/A rail tabs, quieter neutral clip
  material, a thin readable audio waveform, and a catalog-style selected-clip
  outline instead of a bright marching-ants debug border.
- Timeline/editor vertical balance now gives more height to the real Viewer and
  Workbench while constraining the default Timeline height; additional tracks
  should scroll instead of leaving a large dead grid in normal review captures.
- Timeline feature evidence badges (`FX`, `TR`, `COL`, etc.) are now muted,
  smaller, and drawn as thin clip-internal information strips instead of bright
  sticker-like pills.
- Cut and transition markers are now restrained edit boundaries: no large yellow
  scissors pin, thinner transition handles, and lower-opacity transition labels.
- The node-graph QA scenario now places real nodes in a tighter two-row
  composition, so Workbench captures read as an active node workflow instead of
  tiny nodes floating across empty canvas.
- Node Graph toolbar buttons now share the same compact icon-button style,
  including the popout action, so the header no longer shows a mismatched empty
  pill control.
- Workbench clip/audio property rows now use a compact inspector-width group
  instead of stretching table-like rows across the whole Workbench. Individual
  row boxes were removed; labels, values, and sliders now sit in one restrained
  panel.
- Workbench mask/blur controls follow the same compact inspector rule, with
  limited width, calmer borders, and subdued action buttons.
- Audio Mixer now negotiates Timeline height only while open, so the mixer is
  not clipped by the compact default Timeline. Hiding it returns the Timeline
  to the reference-style lower height.
- Audio Mixer channel strips now show short visual track ids (`A1`, `MASTER`)
  and keep long source names in tooltips, avoiding filename overlap in compact
  channel strips.
- The renewed embedded Sound Editor lives in the Workbench audio state and is
  also available through a lightweight `SoundEditorDockWindow` shell for the
  timeline sound-editor launch path. It has no Load workflow; the edit target is
  either the selected Media Pool audio source or the selected Timeline audio
  clip, and those states stay separate while the user switches targets. The UI
  uses a compact waveform strip, a small `spectrum / level` strip, icon tabs,
  chain chips, compact EQ/Dynamics/FX/AI panels, and shared `StudioSlider`
  controls. Selecting an audio source in Media Pool starts waveform extraction
  so the strips can become real evidence instead of static placeholders.
  Review captures should use this renewed surface unless the legacy full
  `SoundEditorWindow` waveform/spectrum/stem lab is explicitly being reviewed.
  The default panel exposes a compact Advanced Lab icon that expands inline
  inside the Workbench Sound Editor. The Workbench path must not open the
  legacy large `SoundEditorWindow`; that window remains only for explicit
  legacy/full-lab review paths outside the renewed Workbench flow.
- Sound Editor mini graphs use the same material rule as the renewed sliders:
  thin graphite surfaces, darker hand-edit pins, and controlled audio-data
  colors. The chrome stays graphite, but signal data should carry color:
  mint/cyan waveform stereo lines, green/blue/amber/coral spectrum bands,
  green-to-amber-to-coral level meter thresholds, and semantic EQ/Dynamics/
  FX/AI graph accents. Avoid bright white points, rainbow decoration, or boxed
  Qt-style plotted lines. Current visual reference:
  `debugCapture/ui_renewal_sound_editor_audio_color_round_1/sound_editor_graphs_contact_sheet.png`.
- EQ graph pins are functional edit handles, not decorative marks. Dragging the
  Low/Mid/High point must update the corresponding slider and
  `AudioClip.effects["eq"]` state, enabling EQ when the move creates an audible
  change. Current interaction evidence:
  `debugCapture/ui_sound_editor_eq_drag_round_1/sound_editor_eq_drag_high_gain.png`.
- Dynamics graph pins are also functional edit handles. The knee point controls
  compressor Threshold, and the right slope point controls compressor Ratio.
  Both controls must update the matching sliders and
  `AudioClip.effects["comp"]` rather than acting as visual-only graph marks.
  Current interaction evidence:
  `debugCapture/ui_sound_editor_dynamics_drag_round_1/sound_editor_dynamics_drag_threshold_ratio.png`.
- FX graph pins are functional edit handles for Space / cleanup controls. The
  three points map to Reverb Mix, Delay Mix, and De-esser Reduction. The graph
  must be drawn from those real values and dragging a point must update the
  matching slider and `AudioClip.effects` entry. Current interaction evidence:
  `debugCapture/ui_sound_editor_fx_drag_round_1/sound_editor_fx_drag_reverb_delay_deesser.png`.
- AI Master graph pins are functional macro handles. The six points map to Air,
  Clarity, Warmth, Width, Punch, and Excite, and Width must use its real
  0-200% range. Dragging a point must update the matching slider and
  `AudioClip.effects["ai_master"]`. Current interaction evidence:
  `debugCapture/ui_sound_editor_ai_drag_round_2/sound_editor_ai_drag_macros.png`.
- Sound Editor graph handles use progressive disclosure. The default graph
  should stay visually quiet; hover or drag may brighten the active graphite pin
  and show a small value pill naming the controlled parameter. Do not add
  permanent labels to every graph point in the compact Workbench panel. Current
  visual reference:
  `debugCapture/ui_sound_editor_hover_labels_round_2/sound_editor_hover_labels_contact.png`.
- On release after a real graph-handle drag, the manipulated point should keep
  a short graphite highlight and smoothly decay back to the quiet default
  state. The value pill should not remain after release; the pulse is the
  confirmation feedback. Current visual reference:
  `debugCapture/ui_sound_editor_pin_decay_round_1/eq_pin_decay_sequence_zoom_graph.png`.
- Interactive Sound Editor graph handles support double-click reset. Reset
  values are EQ 0 dB, Dynamics Threshold -20 dB / Ratio 4:1, FX default
  mix/reduction values, and AI Master defaults including Width 100%. Reset
  should use the same short graphite pulse and should not leave a permanent
  value pill. Current visual reference:
  `debugCapture/ui_sound_editor_double_click_reset_round_2/eq_double_click_reset_sequence.png`.
- The canonical Sound Editor evidence capture is
  `tools/qa_ui_renewal_sound_editor.py`. It must import real media from the
  YouTube Imports folder, run `audio.extract_from_video`, edit the extracted
  audio clip through the action registry, set the reference-05 jog shuttle via
  `audio.sound_editor.jog_shuttle.set`, expand the inline Advanced Lab via
  `audio.sound_editor.advanced_lab.set`, wait for waveform extraction, and
  capture both the Workbench Sound Editor and detached Sound Editor shell. It
  also captures a four-panel EQ / Dynamics / FX / AI graph contact sheet after
  applying those edits to the real extracted Timeline audio clip state, not to
  a generated mock image.
  Latest verified output:
  `debugCapture/ui_renewal_sound_editor_cubase_round_1/sound_editor_qa.json`,
  `debugCapture/ui_renewal_sound_editor_cubase_round_1/sound_editor_graphs_contact_sheet.png`,
  and
  `debugCapture/ui_renewal_sound_editor_cubase_round_1/dock_sound_editor_mixer_action.png`.
- The Sound Editor jog shuttle visual direction is now a low-saturation
  brushed-metal dial with no long center notch. The dial body now comes from
  the permanent project resource
  `resources/ui/sound_editor/jog_dial_metal_sparse_base.png`, while the active
  sparse eight-slot LED set is still painted by the editor so jog state and
  playback animation remain live. Latest verification:
  `debugCapture/sound_jog_resource_texture_clipped_20260708/sound_editor_qa.json`.
- The Workbench Sound Editor now has a `Mixer` tab with compact audio channel
  strips for track-level mixing. Each strip exposes a vertical fader, level
  meter with peak/clip indication, pan slider, Mute, Solo, automation R/W,
  insert slots, send levels, and a track type badge in the renewed
  low-saturation audio theme. The Master strip also includes a compact
  SuperVision-inspired stereo L/R VU meter with subdued oxblood panels, amber
  needles, and clipped-state indication while retaining the existing vertical
  master meter/fader.
  The Sound Editor mixer pan and fader controls are custom-painted local
  widgets, not stylesheet `QSlider` chrome: pan uses a small graphite center
  rail, and the vertical fader uses a recessed channel strip rail with a quiet
  metal cap and low-saturation live fill. The timeline Audio Mixer panel
  mirrors Mute/Solo, detached Sound Editor docks inherit the full mixer track
  context, stale widgets are hidden before mixer rebuilds, and automation can
  emit `tigerstudio.audio.mixer.v1`, `tigerstudio.audio.meter.v1`, and
  `tigerstudio.audio.automation.v1` state. Mixer snapshots are persisted with
  project/history snapshots so local AI can compare and restore mix states.
  AI-facing actions:
  `audio.track.set_volume`, `audio.track.set_pan`, `audio.track.mute`,
  `audio.track.solo`, `audio.track.set_type`, `audio.track.insert.set`,
  `audio.track.send.set_level`, `audio.track.route_to_bus`,
  `audio.track.meter.state`, `audio.automation.state`,
  `audio.automation.write`, `audio.automation.clear`,
  `audio.mixer.snapshot.save`, `audio.mixer.snapshot.compare`,
  `audio.mixer.snapshot.apply`, and `audio.mixer.state`. Latest QA screenshot:
  `debugCapture/ui_renewal_sound_editor_cubase_round_1/dock_sound_editor_mixer_action.png`.
  Latest isolated Master VU visual probe:
  `debugCapture/ui_renewal_sound_editor_master_vu_round_2/dock_sound_editor_master_vu_action.png`.
  Latest mixer visual polish probe:
  `debugCapture/ui_renewal_sound_editor_mixer_beauty_round_1/dock_sound_editor_mixer_beauty_action.png`.
- Color grading nodes now switch the Workbench stack to a right-side
  `Color Grading` inspector instead of opening the old wide bottom wheel dock.
  The default editor surface now reads as Viewer left, color controls right,
  Timeline unobstructed.
- The old color dock remains available for explicit popout/full-page routes,
  but selecting a color node collapses the bottom color container to zero height
  so the Timeline keeps its catalog-style lower surface.
- Color grading mode defaults the active track to split compare preview. The
  Viewer paints a real UI overlay with a center compare line plus `Before` /
  `After` labels; this is editor chrome, not generated review art.
- The color node QA flow applies a non-identity grade to the selected color
  node, rebuilds the active node chain, and verifies that the right-side color
  workbench is active while the bottom color container stays hidden.
- Color/mask toolbar emoji labels were replaced with code-native icons plus
  plain text so missing-glyph square boxes do not appear in captures.
- The Timeline now paints a restrained `Grade Layer` rail with small diamond
  marks when a clip or selected node chain has a non-identity color grade. This
  is bound to real `color_grade` state, not a fake catalog overlay.
- The right-side `Color Grading` workbench now places larger color wheels beside
  a compact Scopes card. The scope widget samples the current preview pixmap for
  larger live-preview `Luma / Levels`, `Histogram`, `RGB Parade`, and `Vectorscope`
  graphs through `app.color_scopes.render_scope`, so catalog/review captures
  remain based on the live editor state instead of decorative marks. The
  Scopes card can also open a detached `Color Scopes` dock while keeping the
  Workbench copy visible.
- Timeline drag palette cards in `app/effect_cards.py` now use the same compact
  neutral tile language with thin color-coded folds/strips for meaning. Fade
  uses a code-native icon, and the Speed card's visible preset labels are clean
  ASCII (`0.25x Smooth`, `0.5x Smooth`, etc.) instead of mojibake.
- Latest timeline density/layout verification used the real YouTube Imports
  source:
  `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports\South Korea 4K Drone Video ｜ Seoul, Busan, Songdo Cinematic Aerials [AA-sv3ilNBE].mp4`.
- Latest real-media verification captures:
  `debugCapture\ui_renewal_timeline_grid_round\editor_workbench_node_graph_action.png`
  and
  `debugCapture\ui_renewal_node_toolbar_round\editor_workbench_node_graph_action.png`
  and
  `debugCapture\ui_renewal_timeline_compact_round\editor_workbench_node_graph_action.png`
  and
  `debugCapture\ui_renewal_badge_polish_round\editor_workbench_node_graph_action.png`
  and
  `debugCapture\ui_renewal_cut_marker_polish_round\editor_workbench_node_graph_action.png`
  and
  `debugCapture\ui_renewal_node_graph_composition_round\editor_workbench_node_graph_action.png`
  and
  `debugCapture\ui_renewal_node_toolbar_polish_round\editor_workbench_node_graph_action.png`
  and
  `debugCapture\ui_renewal_workbench_mask_compact_round\editor_workbench_node_graph_action.png`
  and
  `debugCapture\ui_renewal_audio_mixer_strip_round\editor_audio_mixer_action.png`
  and
  `debugCapture\ui_renewal_color_reference_split_overlay_round\editor_color_dock_action.png`
  and
  `debugCapture\ui_renewal_color_scope_row_round\editor_color_dock_action.png`
  and
  `debugCapture\ui_renewal_effect_cards_palette_round\effect_cards_palette.png`.
- ASCII display name for the latest source, used when docs or screenshots need
  to avoid mojibake: `South Korea 4K Drone Video - Seoul, Busan, Songdo Cinematic Aerials`.
- Review automation handoff is active again after the main-editor evidence
  pass. `app/review_automation/ui_evidence_index.py` reads
  `docs/UI_RENEWAL_EVIDENCE_INDEX.md` and copies those real action-backed
  captures into `feature_<topic>_editor_surface.png` assets before PPT/HTML
  export. The latest detailed generation wrote
  `E:\ClaudeCodeApp\ReviewAutomationWorkspace\outputs\TigerCapture_Review_Automation_detailed.pptx`
  and `E:\ClaudeCodeApp\ReviewAutomationWorkspace\outputs\site\index.html`.
  `tools/qa_review_automation.py` currently passes with failures=0,
  feature_action_ready=11/11, small_visual_artifacts=0, and
  flat_visual_artifacts=0. `ai_script_edit` now has 20/20 local
  automation-generated transcript/prompt corpus cases for safe-plan QA, and
  Claude direct provider generation now succeeds on 20/20 cases without
  rule-based fallback. Keep visual/review copy scoped to this local corpus
  rather than implying a human customer study.
- Review sample videos remain sourced from
  `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`; generated 6-7s
  samples preserve source audio when possible and otherwise attach a quiet AAC
  stream so `audio.extract_from_video` can be tested without replacing the real
  video frames.

Next recommended pass:

1. Continue subjective UI polish only where a real editor screenshot still
   looks weaker than the generated reference; do not replace product evidence
   with generated editor art.
2. For review automation, improve blocked/limited claims by adding real data:
   redacted broadcast platform proof, repeated Live2D Viewer shutdown runs, and
   future Spine/NIKKE renderer fixes before any visual success claim.
