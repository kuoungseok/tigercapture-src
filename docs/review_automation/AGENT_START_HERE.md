# Agent Start Here: Review Automation

Last updated: 2026-07-08

This is the first file a new Codex, Claude, or other coding agent should read
before touching Tiger Studio review automation.

Before acting, also read `../AGENT_START_HERE.md`. It is the repository-wide
handoff index for current assumptions such as `debugCapture` being disposable,
durable asset locations, `video_editor_window.py` boundaries, and the current
VTuber/VSeeFace fallback stance.

## One-Sentence Mission

Review automation creates product-catalog presentation assets that explain what
Tiger Studio can do by driving the real editor, capturing real
feature states, and placing those captures into polished PPT/HTML/catalog
layouts.

It is not code review, QA status reporting, or a release dashboard.

## Current Working Context

- The user wants review automation to produce beautiful product-catalog style
  PPT/HTML/images.
- The catalog style should follow `CATALOG_PPT_STYLE.md`, not runtime editor UI
  style.
- Real editor screenshots are required for feature claims.
- Laptop/device and multi-monitor templates are presentation frames for product
  storytelling.
- Generated fake editor UI must not be used as evidence.
- The user may be remote on iPhone and may ask to see images directly in chat.
- Generated PPT files were intentionally deleted. Do not regenerate decks unless
  the user explicitly asks for generation.

## Must-Read Order

Read these before planning or editing:

1. `../AGENT_START_HERE.md`
2. `README.md`
3. `PURPOSE_RULES.md`
4. `CATALOG_PPT_STYLE.md`
5. `PRESENTATION_SCENARIO.md`
6. `FULL_PRODUCT_CATALOG_MANIFEST.md`
7. `FULL_PRODUCT_CATALOG_PAGE_PLAN.md`
8. `FULL_PRODUCT_CATALOG_TALK_TRACK.md`
9. `PRODUCT_CATALOG_PT_SCENARIO.md`
10. `COMPARISON_TEMPLATE_RULES.md`
11. `COLOR_NODE_COMPARE_PRESETS.md`
12. `MULTI_MONITOR_RULES.md`
13. `TEMPLATE_ASSET_MANIFEST.md`
14. `REVIEW_AUTOMATION_TODO.md`

Expanded references:

- `../SPEC_REVIEW_AUTOMATION.md`
- `../CURRENT_SPEC_PRESENTATION_SCENARIO.md`
- `../MULTI_MONITOR_REVIEW_SCENARIO_RULES.md`
- `../review_reference_featpaper_style.md`
- `../VTUBER_TRUMP_SOURCE_MAPPING_CONTEXT.md`

## Hard Rules

- Do not generate PPT/HTML/images unless the user explicitly asks to generate.
- Do not rebuild deleted decks just because outputs are missing.
- Do not use test-pattern media, color bars, or empty editors in catalog output.
- Do not use AI-generated editor scenes as proof of features.
- Do not attach or insert decorative/new generated images outside the already
  selected laptop and multi-monitor templates. Product-facing imagery must be
  either the fixed approved templates or real Tiger Studio editor captures,
  except for the approved final `Specification Index` bonsai object documented
  in `PURPOSE_RULES.md` and `FULL_PRODUCT_CATALOG_MANIFEST.md`.
- Final PPT generation must not use old screenshots from historical capture
  roots such as `fresh_first_slide_capture`, `actual_3d_viewer_capture`, or
  `debugCapture`. Those folders are debug/history only. Use the current
  approved recapture batch under
  `E:\ClaudeCodeApp\ReviewAutomationWorkspace\tmp\fresh_review_recapture`, or
  stop and recapture the feature.
- Prefer multi-track editor states for screenshots. A catalog capture should
  usually show more than one lane, such as video + audio, video + effect,
  video + typography, video + actor, or video + node/grade/keyframe lanes.
- Timeline captures must match the current editor timeline reference:
  `E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\references\current_editor_timeline_reference_2026-07-06.png`.
  Current means horizontal ruler, red playhead triangles, continuous clip
  thumbnail strip, subtle dark rows, simple left track labels, and modern
  Viewer controls such as Compare/Fit/zoom. Old blocky V1/A1 tabs, synthetic
  colored strips, or obsolete thumbnail systems are stale evidence.
- Add natural edit texture to some screenshots: a mid-clip cut, adjacent clip
  boundary, marker, or transition can make the project feel real. Do not apply
  this to every screenshot, because repeated identical cut/transition layouts
  will look staged.
- Do not show QA scores, pass counts, readiness numbers, raw JSON, or file-path
  dumps in summary/detailed/product-catalog slides.
- Keep the 3D catalog page scoped to implemented AR/PBR camera and object
  compositing evidence. Do not add future engine-handoff claims to catalog
  pages unless the user explicitly revives them after implementation exists.
- Do not treat `SPEC_UI_RENEWAL.md`, Qt QSS, or runtime widget font settings as
  catalog PPT design authority.
- Do not move large generated assets into git-tracked docs unless explicitly
  requested.
- Do not store original PPT templates, laptop/device references, monitor
  templates, or screen-map JSON in `debugCapture`; it is disposable. Stable
  template sources live in
  `E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates`.
- Do not delete generated output broadly. If asked to remove PPTs, filter by
  exact extension with `Where-Object { $_.Extension -in '.ppt', '.pptx' }`.
- The full product catalog is a locked 23-slide scenario defined in
  `FULL_PRODUCT_CATALOG_MANIFEST.md`. Do not add, remove, split, merge, or
  reorder those slides unless the user changes that manifest first.
- Slide 23 is the final `Specification Index` page. It uses dense micro-spec
  text and the approved blue-pot bonsai cutout only as a closing-page object. The
  bonsai is not feature evidence. Reject visible white halos, checkerboard
  remnants, background strips, or a large pasted-object drop shadow.
  Shadow mode is locked to `pot_contact_only`: only a subtle contact shadow
  under the pot base is allowed. Left subtitle/body text must wrap inside the
  left text column and never overlap the central micro-spec columns.
- Slide 23 visible spec groups come from
  `docs/review_automation/spec_index_groups.json`, not from improvised slide
  copy. Before regenerating the catalog, update that source from the latest
  `SPEC.md`, `TODO.md`, and relevant `docs/SPEC_*.md` changes. It must cover
  current axes such as PPT Maker / `.tgppt`, Music Lab, Sound Editor, Local AI,
  Python Action, MCP, VTuber Studio, AR/PBR, depth-aware compositing, PPTX, and
  MP4, while excluding internal renderer bridge names, Marmoset, QA readiness numbers, and
  pass/fail status language.
- Slide 4 is `PPT Maker / Timeline-Native Presentation Studio`. It must use
  actual `.tgppt` / `app.pptgen` evidence and must not be folded into AI,
  export, or generic editor overview pages.
- Slide 14 is `Music Lab / Composition`. Music Lab is a composition feature,
  separate from Sound Editor, EQ/dynamics, mixer, waveform editing, and generic
  audio pages. Its evidence must show prompt composition, sections, chords,
  MIDI/notes, preview mix, or render-to-timeline controls from the real current
  UI.
- MMD catalog evidence must never use the first frame. Use a middle/active
  motion frame so the character reads as animated, not a static thumbnail. The
  semantic capture contract must explicitly include `first_frame_used=false`,
  `capture_frame_position=mid_motion` or equivalent middle-frame proof, and
  `mmd_motion_active=true`.
- Color grading, effects, and node pages must not use neutral/original-looking
  before/after captures. The capture must actually change numeric grade,
  filter, or node parameters through the editor/action surface, write the
  compare sidecar contract, and visibly differ from the original. If the agent
  does not know suitable preset values, it must research real preset values and
  record that source in the capture contract before building the deck.
- The default researched color comparison preset is
  `cinematic_teal_orange_strong_compare_v1` from
  `COLOR_NODE_COMPARE_PRESETS.md`. Apply its strong teal-orange target values,
  record the source URLs in the capture report, and prove
  `strong_researched_color_preset_applied=true`. For node/effect pages, default
  to `Gaussian Blur` with a strong visible radius, normally 24 px and never
  below 18 px for catalog evidence, unless a stronger implemented node is
  explicitly documented.
- Color grading, node graph, and node/effect pages must prefer the
  comparison-workbench composition: one real full editor/window screenshot where
  the left Viewer shows `Before`/`After` or `Split` with a visible divider and
  the right/workbench side shows the actual color/node/effect controls that
  produced the result. Separate pasted screenshots, comparison-only popouts,
  controls-only panels, and iPad crops are not valid main evidence.
- Each full-catalog page's screen composition, template, capture source,
  action/capture method, and rejection criteria are defined in
  `FULL_PRODUCT_CATALOG_PAGE_PLAN.md`.
- The Korean presenter narration for the locked 23-slide deck is defined in
  `FULL_PRODUCT_CATALOG_TALK_TRACK.md`. Use it as speaker-note guidance, not as
  visible slide body text.

## Source And Output Boundaries

Canonical rules:

```text
docs/review_automation/
```

Implementation code:

```text
app/review_automation/
tools/generate_review_assets.py
tools/build_review_office_decks.py
tools/build_review_site.py
```

Generated workspace:

```text
../ReviewAutomationWorkspace/
```

User-provided real video source:

```text
C:\Users\artmouse\Videos\TigerCapture\YouTube Imports
```

Preferred review capture footage from that folder:

- city skyline, city night view, drone/aerial footage, travel/cinematic scenes,
- car racing, motorsport, driving, or vehicle footage,
- visually rich HDR/OLED demo footage when it helps color/audio/export pages.

Avoid dull test clips, color bars, placeholder patterns, or footage that makes
the product screenshot look like an internal QA screen.

Debug/evidence captures:

```text
debugCapture/
```

## Safe Workflows

### If the user asks for planning or rules

Update `docs/review_automation/` first. Keep the output workspace untouched.

### If the user asks to generate a deck

Before generation:

1. Re-read this folder.
2. Re-read current `SPEC.md`, `README.md`, `TODO.md`, and relevant `docs/SPEC_*.md`.
3. Clear review/PPT generation caches so stale screenshots, old slide PNGs, and
   previous deck asset crops cannot leak into the new catalog. Never delete
   source templates, source media, or rule documents while doing this.
4. Reject historical capture roots in final PPT sources:
   `fresh_first_slide_capture`, `actual_3d_viewer_capture`, and `debugCapture`.
   If one appears in a slide source path, replace it with a current recapture
   path or stop the build.
5. Verify sample media and template assets exist.
6. Verify feature-specific captures can be real.
7. Stop instead of generating PPTX if strict captures are missing or invalid.
   Do not put repeated `RECAPTURE REQUIRED`, `PENDING`, blank, black, or generic
   placeholder screens into laptop, iPad, monitor, or feature evidence frames.
8. Laptop and monitor screens must use full editor/window captures. Cropped
   detail panels, media-pool-only crops, timeline strips, and contact sheets
   belong only in detail frames such as the iPad.
9. iPad/detail frames must explain the selected feature, not repeat the whole
   editor. For Color Grading, the iPad must show only color controls such as
   wheels, curves, scopes, tone controls, or sliders. It must not include the
   video viewer, media pool, or timeline. If that color detail does not add
   meaning beyond the main comparison-workbench capture, omit the iPad and use
   the laptop-only layout.
10. iPad/detail frames are optional. If there is no feature-specific detail
   worth showing, use the laptop-only template. Never duplicate the laptop
   screen into the iPad just to fill the device frame.
11. Cross-feature screenshot substitution is forbidden. Live2D evidence must
   not fill an MMD page, node/color captures must not fill typography or
   transition details, and generic editor crops must not fill an iPad/detail
   frame.
12. Full-catalog generation must block if a page's semantic capture contract is
   missing. Image existence and nonblack pixels are not enough when the page
   claims a specific feature.
13. The reverse is also true: a semantic contract is not enough if the image is
   black, blank, nearly empty, or just a thin meaningless PPT/timeline fragment.
   The build must inspect the pixels and block these outputs instead of placing
   them in a laptop, monitor, or iPad frame.
14. After rendering slide PNGs, run final visual QA on the rendered slides
   before exporting PPTX. This QA must inspect the actual laptop, iPad, and
   multi-monitor screen regions in the finished catalog slide, reject blank or
   flat mapped screens, reject duplicated evidence screens, and reject iPad
   detail frames that visually duplicate the laptop screen.
15. After exporting PPTX, validate the file as a PPTX package: ZIP integrity,
   required Office entries, slide XML parseability, embedded media count, and
   successful `python-pptx` reopen. Do not deliver a deck that may trigger a
   PowerPoint repair warning.
16. Ask no extra questions if the requested mode is clear; otherwise choose the
   safest catalog mode.

After generation:

- Show one or more preview PNGs directly if the user is remote.
- Report output paths.
- Do not show QA metrics in product-facing deck summaries.

### If the user asks to show screenshots

Use local absolute image paths when embedding images in chat. Prefer showing the
most relevant single image first rather than a large gallery.

### If template assets are missing

Mark the template scenario as pending. Do not silently invent product evidence.
Outer frames can be generated or staged only when the user explicitly asks for
that template work; screen contents must still be real editor captures.

## Feature Evidence Checklist

Every feature page needs a screenshot that visibly matches the feature:

- General: prefer visible multi-track timelines instead of a single lonely clip.
- General: some, but not all, timeline screenshots should show a natural mid-
  timeline cut or transition.
- General: timeline visuals must match the current editor reference, not older
  review-generated track art.
- Cut/edit: zoomed timeline, selected clip, cut marker or edit boundary.
- Color: real footage plus grading controls, scopes, or before/after.
- Node graph: connected nodes plus selected node parameters, with a visible
  before/after or split Viewer result in the same workbench capture whenever the
  page claims an effect result.
- Audio: waveform, mixer, sound editor, spectrum, EQ, or dynamics.
- Comparison: use comparison templates only when the before/after state is
  visible on the canvas and the difference explains a real feature. Default to
  `Original | After`, `Color Off | Color On`, `Effect Off | Effect On`, or
  `Node Off | Node On` labels. Do not use generic PIP or fake split-screen
  graphics as product evidence.
- Typography: large on-canvas title text, at least one secondary text layer,
  visible text clips/keyframes/controls, and readable multilingual samples when
  the page claims localization. A single tiny caption line is not valid
  typography evidence.
- Transitions/effects: applied effect or transition on real media.
- Live2D/actor: actor visible, actor lane/keyframes, actor controls.
- 3D/AR/PBR: use a real approved GLTF/GLB asset from `E:\ClaudeCodeApp\3d`,
  with the model visible and placement/material/lighting controls shown. For
  laptop/iPad AR/PBR pages, lock the editor video viewer and the iPad/detail
  viewer to the same named 3D asset and preset. If the iPad shows the plaster
  statue/bust, the editor video viewer must also show that same plaster
  statue/bust composited into the edit and scaled up through actions or saved
  view state. Do not use the old motorcycle debug asset for catalog evidence.
  Do not repeat the Poly Haven camera model on every 3D page; reserve the
  camera model for camera-specific pages or fallback. For the AR/PBR 3D
  Composite catalog page, the iPad/detail frame must be the standalone AR/PBR
  or 3D viewer for the same asset, not the composited video output, raw video
  frame, Program Output, or a duplicate laptop/editor screen.
- VTuber: Program Output separated from Performance Source/tracking input.
  The main laptop/monitor frame must be the full actual `VTuber Studio - Tiger
  Studio` work screen. If the page uses an iPad/detail frame, that iPad must
  contain Program Output only; never put Source Tracking, Avatar Mapping, the
  full workspace, or a generic editor crop in the iPad.
  When the source is the Trump chest-up seated Performance Source, the avatar
  shown in Program Output / Avatar Mapping must use `bust_up` /
  head-to-mid-chest framing: head, neck, shoulders, and upper torso visible,
  but not a widened waist/full-body view. Face-only VRM meta thumbnails are
  invalid.
  The Program Output avatar must also be visually large and grounded: trim
  transparent VRM padding before fitting, keep the visible avatar large enough
  to read in the catalog frame, and anchor the lower visible edge to the Program
  Output bottom safe line. Tiny or floating avatars are invalid even when the
  metadata says `bust_up`.
  Product-catalog VTuber captures must use the VTuber VRM GPU renderer
  `vrm_mtoon_gpu`. Software VRM fallback renders, dotted/point-cloud avatar
  output, meta thumbnails, AR/PBR, Marmoset PBR, and generic full-gpu debug
  proof PNGs are invalid for this page.
- Multi-monitor: real captures mapped into real template screen regions.

If the feature is not actually visible, the page is not ready.

## User Preference Summary

- Product catalog over QA report.
- Beautiful, restrained Feat Paper-like layout.
- Real editor work, not empty UI.
- Feature-specific screenshots, not one generic editor image reused everywhere.
- No fake generated editor UI as evidence.
- Laptop and multi-monitor templates are important presentation devices.
- Korean/Japanese/English output should avoid mojibake and cramped typography.

## Screenshot-Driven Copy Rule

Catalog slide copy is not final until the real screenshot/GIF for that slide has
been reviewed.

Workflow:

1. Draft the scenario from the latest spec.
2. Drive the real editor and capture the feature state.
3. Inspect what is actually visible in the capture.
4. Rewrite the slide title, body, and caption to match the capture.
5. If the capture and claim disagree, either recapture the feature correctly or
   weaken/remove the claim.

Examples:

- If Color Wheels and scopes are visible, the slide can say `Color Grading
  Workspace`.
- If only a simple LUT/intensity control is visible, call it `Fast Look
  Adjustment`.
- If a Live2D actor is visible with actor lane/keyframes, call it `Live2D Actor
  Track`.
- If the actor is not visible, do not claim actor compositing; call it setup or
  mark it pending.
- If Spine/NIKKE renders incorrectly, do not use it as a success catalog page.
