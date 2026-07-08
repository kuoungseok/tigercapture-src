# User PPT Generator Production Plan

Last updated: 2026-07-07

This document defines the user-facing PPT generation and editing product for
TigerCapture. It is intentionally separate from review automation.

Review automation creates product-catalog decks about TigerCapture itself. The
user PPT generator helps a user create their own presentations from their own
materials, media, timeline edits, screenshots, notes, and AI-assisted outlines.

## Current Implementation Snapshot

The first real implementation lives outside review automation in `app/pptgen/`.
It is connected to the main editor through `app/video_editor_ppt_workflow.py`,
the `Create` command menu, Command Palette entries, and the registered
`ppt.*` action namespace.

Implemented now:

- `DeckSpec`, `SlideSpec`, element style, slide timeline, validation, PNG
  preview, and PowerPoint-compatible PPTX export through `python-pptx` plus
  targeted OOXML patches.
- A standalone `PptGeneratorWindow` with slide list, white slide canvas,
  page-attached PPT timeline rail with ruler/slide clips/playhead, top
  contextual text toolbar, font family/size/B/I/U/align/line/color controls,
  left insert toolbox, speaker notes, `.tgppt` save/open, PPTX export, and PNG
  export. The selected slide also exposes animation timing lanes under the PPT
  timeline, and the top command bar exposes PDF export.
- Insert toolbox primitives: text box, document/content box, editable OOXML
  table, image placeholder, shape, line, and chart. Charts preview as
  TigerCapture vector drawings on the canvas/PNG path and export to native
  editable PowerPoint chart parts in PPTX.
- PPT workspace media pool: deck-local assets live in `DeckSpec.assets`, are
  shown in the left media-pool panel, can be added from files, dragged as local
  file URLs onto the canvas, inserted into the current slide, and removed from
  the pool without deleting existing slide elements.
- Image loading: the Image Box tool can open a file picker to insert PNG/JPEG/
  WebP/BMP/GIF files, and selected image/image-placeholder elements expose a
  Load/Replace Image control. The same path is available to automation through
  `ppt.image.load`.
- Minimum PPT document operations: add, duplicate, and delete slides; copy,
  paste, duplicate, align, and front/back layer order for the selected element.
- PPT edit safety: `app/pptgen/history.py` stores bounded deck snapshots for
  Undo/Redo, the editor exposes command-bar buttons plus standard shortcuts,
  and `app/pptgen/autosave.py` writes `.autosave.tgppt` recovery copies for
  dirty decks on a background timer without importing Qt into the core package.
  The `Recovery` command lists readable recovery candidates and opens the
  selected copy as an unsaved dirty deck so the autosave file itself is not
  overwritten by a normal Save. Dirty decks prompt Save/Discard/Cancel before
  New, Open, timeline import, recovery open, or window close. A successful Save
  deletes the current autosave/sibling recovery copy, and recovery deletion is
  restricted to files ending in `.autosave.tgppt`.
- Built-in slide template registry and PowerPoint-style thumbnail gallery:
  blank, title, title/body, two-column, image/video hero, 3D showcase,
  timeline recap, table/chart report, and typography title. `New` opens the
  gallery to create a deck from a template. `Templates` opens the same gallery
  in apply mode, replacing the current slide's layout while keeping the slide
  identity/timeline position.
- PPTX import MVP: `app/pptgen/import_pptx.py` uses `python-pptx` to import
  text boxes, tables, pictures, and simple shapes into editable `DeckSpec`
  slides. Pictures are extracted to an asset directory and registered in
  `DeckSpec.assets`. This is a best-effort content import, not full Office
  fidelity: masters, advanced SmartArt, charts, media, animations, and complex
  theme inheritance are still out of scope.
- Deck-level header/footer support: optional header text, footer text, date, and
  slide number overlays are stored in deck metadata and rendered consistently to
  canvas preview, PNG export, and PPTX export.
- Element animation MVP: selected PPT elements can store `appear`, `fade_in`,
  `fade_out`, `move`, or `scale` intent with trigger, start, duration, easing,
  motion offset, and scale parameters. The PPT editor shows these controls in
  the element inspector, marks animated elements on the slide timeline, draws
  per-element animation timing lanes for the selected slide, and can scrub/play
  the PPT timeline to preview opacity, movement, and scale changes on the
  canvas. Clicking an animation lane selects the element and moves the local
  playhead to that animation. Dragging a lane bar moves the animation start;
  dragging its left/right edge trims start or duration within the slide bounds.
  On-click animations also store a `click_index`; the inspector exposes it as
  `Click #`, animation lanes display `#n` badges, and unset legacy click
  animations are assigned visible sequence numbers automatically. PPTX export
  writes native timing/effect XML for the supported simple effects.
- PPTX animation compatibility QA: `tools/qa_ppt_animation_compat.py` generates
  a `.pptx`, `.tgppt`, slide PNGs, contact sheet, and manifest for manual
  PowerPoint/LibreOffice verification plus OOXML static checks. With
  `--host-check auto`, it attempts LibreOffice first when installed and then
  validates against local PowerPoint COM on Windows.
- PDF export: `app/pptgen/pdf_export.py` converts generated PPTX files to PDF
  through `auto`, `libreoffice`, or `powerpoint_com` backends. The PPT editor
  has a PDF export button, `tools/pptgen.py --export-sample --export-pdf`
  performs CLI smoke export, and automation exposes timeline PDF generation
  through `ppt.timeline.export_pdf`.
- MP4 presentation video export MVP: `app/pptgen/animation_runtime.py` now owns
  Qt-free element animation preview math, `app/pptgen/preview.py` can render a
  slide at a specific local playhead, and `app/pptgen/video_export.py` streams
  those frames to bundled FFmpeg as H.264 MP4. The PPT editor exposes an `MP4`
  export button, `tools/pptgen.py --export-sample --export-video` performs CLI
  smoke export, and automation exposes timeline video generation through
  `ppt.timeline.export_video`. MP4 export honors slide duration and the basic
  `cut`/`fade` transition family (`dissolve`/`crossfade` aliases) without
  extending total presentation duration. It can also mux an optional narration
  or soundtrack file as AAC audio from `audio_path`, deck metadata
  (`narration_audio_path`, `audio_path`, or `soundtrack_path`), or the CLI
  `--video-audio` option; short audio is padded with silence and long audio is
  trimmed to the presentation video duration. In the PPT editor, MP4 export runs
  in `app/pptgen/ui/video_export_worker.py` on a background `QThread` with a
  modal progress/cancel dialog. CLI and automation exports remain synchronous
  from the caller's perspective.
- Editor integration bridge: media-pool file drags onto the PPT canvas create
  typed PPT actors (`video_actor`, `ar_pbr_actor`, `vrm_actor`, `mmd_actor`,
  `audio_actor`, or `image`) based on asset type. Typography drags/text payloads
  create `typography_actor` elements. The same bridge is exposed to automation
  through `ppt.asset.add`, `ppt.timeline_clip.add`, and `ppt.typography.add`.
- Actor export fallback: PPT media/3D actors can carry `poster_path`,
  `thumbnail_path`, `preview_path`, or `render_path` metadata. Canvas/PNG/MP4
  preview and `writer_python_pptx.py` use that image as the visible actor
  representation. Without a poster, actors export as styled placeholder cards
  rather than disappearing. `app/pptgen/actor_posters.py` now auto-generates
  cached posters when actors are inserted or exported: `video_actor` first tries
  a real source-frame still, while 3D/MMD/audio/media actors get deterministic
  card posters until render-cache capture is wired in.
- Timeline clip still import: the PPT editor can capture the selected/current
  video timeline cut as a cached PNG still and insert it as an editable image
  element. Automation exposes the same path through
  `ppt.timeline_clip.still.add`.
- Current editor timeline to draft deck conversion via
  `deck_from_editor_timeline`.
- Automation actions: `ppt.summary`, `ppt.editor.open`,
  `ppt.timeline.export`, `ppt.timeline.export_pdf`, `ppt.timeline.export_video`, `ppt.asset.add`, `ppt.timeline_clip.add`,
  `ppt.timeline_clip.still.add`, `ppt.typography.add`, `ppt.templates.list`, `ppt.template.apply`,
  `ppt.deck.apply_template`, `ppt.project.create`, `ppt.project.open`, `ppt.project.save`, `ppt.project.save_as`,
  `ppt.deck.from_prompt`, `ppt.deck.from_timeline`,
  `ppt.deck.snapshot`, `ppt.deck.validate`, `ppt.deck.import_pptx`, `ppt.deck.actor_posters.generate`,
  `ppt.deck.export_pptx`, `ppt.deck.export_pdf`, `ppt.deck.export_video`,
  `ppt.deck.history`, `ppt.deck.undo`, `ppt.deck.redo`, `ppt.deck.autosave`,
  `ppt.deck.recovery.list`, `ppt.deck.recovery.open`, `ppt.deck.recovery.delete`,
  `ppt.element.add_text`, `ppt.element.add_image`, `ppt.element.add_video`,
  `ppt.element.add_shape`, `ppt.element.add_chart`, `ppt.element.update`,
  `ppt.element.animation.set`, `ppt.element.delete`, `ppt.element.remove`,
  `ppt.element.duplicate`, `ppt.element.z_order`, `ppt.element.align`,
  `ppt.element.arrange`, `ppt.timeline.select_slide`, `ppt.timeline.set_playhead`,
  `ppt.timeline.play_preview`,
  `ppt.slide.add`, `ppt.slide.duplicate`, `ppt.slide.remove`,
  `ppt.slide.move`, `ppt.slide.update`, `ppt.slide.set_layout`,
  `ppt.slide.set_duration`, `ppt.slide.set_notes`,
  `ppt.table.data.set`, `ppt.chart.data.set`, `ppt.image.load`,
  `ppt.media_pool.list`, `ppt.media_pool.add`, `ppt.media_pool.insert`, and
  `ppt.media_pool.remove`, and `ppt.animation_lanes.list`.
- AI-editable PPT surface: automation can create/open/save `.tgppt` projects,
  read the current deck/slide/element
  tree, validate export-readiness issues through `ppt.deck.validate`, update
  slide title/layout/duration/notes/order, add text/image/video/shape/chart
  elements, update text/layout/style/metadata, arrange or delete elements, move
  the presentation playhead, and replace table or chart data. Table cells and
  chart values can include lightweight formulas such as `=A2+B2`, `=SUM(...)`,
  and `=AVG(...)`.
- Current-deck export actions `ppt.deck.export_pptx`,
  `ppt.deck.export_pdf`, and `ppt.deck.export_video` operate on the open PPT
  editor deck. Timeline export actions (`ppt.timeline.export*`) first derive a
  draft deck from the main editor timeline.
- Export QA runner: `tools/qa_ppt_export_pipeline.py` writes a sample PPT QA
  bundle with `.pptx`, slide PNGs, contact sheet, optional PDF, optional MP4,
  and `manifest.json` using schema `tigercapture.ppt.export_qa.v1`.
- Product-readiness QA runner: `tools/qa_ppt_product_readiness.py` builds five
  authoring scenarios (`template_authoring`, `document_tools`, `prompt_deck`,
  `media_and_actors`, `animation_timeline`), then verifies project save/load,
  validation, PPTX export, slide PNG rendering, contact sheets, and optional
  MP4 export. It writes schema `tigercapture.ppt.product_readiness.v1`.
- Release-acceptance QA runner: `tools/qa_ppt_release_acceptance.py` is the
  first four-step product gate. It verifies Office compatibility through static
  PPTX package checks plus optional LibreOffice/PowerPoint COM PDF conversion,
  runs the real `SlideCanvas` MIME/drop ingestion path for timeline,
  typography, image, and AR/PBR assets, stress-tests long editing sessions with
  bounded undo/redo plus autosave/recovery, and compares PNG preview against
  the first MP4 frame for output parity. It writes schema
  `tigercapture.ppt.release_acceptance.v1`.
- Native Office chart export: chart elements store labels, values, chart type,
  and series metadata in `DeckSpec`; `writer_python_pptx.py` exports them as
  PowerPoint chart XML plus embedded workbook data so users can edit the chart
  inside PowerPoint after export.
- Official dev entry point: `tools/pptgen.py`. `tools/pptgen_prototype.py`
  remains only as a compatibility wrapper.

Still pending for product level: external `.pptx` theme/template import,
advanced Office chart formatting/round-trip import, richer click build-list
authoring such as grouped clicks and per-click labels, HTML preview, and
high-fidelity effect-aware video-frame/3D capture as slide assets. MP4 export
exists at MVP level, but still needs render-queue integration for unattended
batch jobs, narration recording/editing UI, loudness normalization, and richer
transition handling such as wipes, directional moves, zooms, and PowerPoint-
native transition parity.

## Product Position

TigerCapture should treat PPT creation as a timeline-native presentation studio:

```text
A timeline-based presentation maker that turns media, text, screenshots,
effects, and AI outlines into editable PPTX decks, previews, PDFs, videos, and
presentable slide sequences.
```

The product should not feel like a clone of PowerPoint or Keynote. It should
borrow their polish where appropriate, but the differentiator is that the user
can make slides while seeing time, scene order, layer timing, transitions, and
media rhythm directly on a timeline.

## Non-Goals

- Do not merge the feature into `app/review_automation`.
- Do not add feature logic to `app/video_editor_window.py`.
- Do not require Microsoft PowerPoint to create a basic deck.
- Do not assume that every video frame maps to one PPT slide.
- Do not make a QA/report-only deck generator. The output must be useful to
  ordinary users making presentations for their own goals.
- Do not make generated slides look like debug dashboards unless the user
  explicitly chooses a technical/report style.

## Core Concept

The main abstraction is a PPT timeline:

```text
PptProject
  DeckSpec
  PptTimeline
    SlideClip[]
      slide_id
      start_ms
      duration_ms
      transition
      speaker_notes
      elements[]
        text/image/video/frame/shape/chart/table/3d/callout
        layout
        style
        animation
```

One slide clip equals one PPT slide. The slide clip duration controls preview,
video export, and speaker pacing. It does not mean the PPTX has a frame for
every video frame.

## User Personas

### 1. Creator / YouTuber

Needs:

- Turn a video edit into a pitch deck, tutorial, or sponsor deck.
- Reuse thumbnails, screenshots, captions, zoom moments, and timeline markers.
- Export both PPTX and video previews.

Success:

- The deck feels visually intentional without manual slide design.
- Existing timeline assets become useful slide material.

### 2. Student / Teacher

Needs:

- Create lecture slides from notes, PDFs, images, and screen recordings.
- Add simple animations and presentation timing.
- Export PPTX/PDF/video.

Success:

- The first draft is structurally correct and readable.
- The user can quickly fix text overflow and layout issues.

### 3. Product / Business User

Needs:

- Create product intros, comparisons, roadmaps, status decks, and reports.
- Use templates, charts, tables, icon rows, callouts, and screenshots.

Success:

- Decks look professional by default.
- Tables/charts do not fall apart in PPTX export.

### 4. AI / Automation User

Needs:

- Generate or update a deck via actions/MCP.
- Apply a theme, replace assets, regenerate thumbnails, and export deliverables.
- Keep changes inspectable and reversible.

Success:

- Every major workflow is available through actions.
- Generated output includes validation reports.

## UX Model

### Primary Screen

The first screen should be the actual authoring surface, not a landing page.

Suggested layout:

```text
+---------------------------------------------------------------+
| top bar: project name, deck purpose, export, present, preview |
+---------------+-----------------------------------------------+
| outline/media | slide canvas / live preview                   |
| pool          |                                               |
|               |                                               |
+---------------+-----------------------------------+-----------+
| PPT timeline: Slide 1 | Slide 2 | Slide 3 ...    | inspector |
| element lanes inside selected slide               |           |
+---------------------------------------------------+-----------+
```

### Main Regions

- Outline panel: slide list, sections, generated outline, speaker notes toggle.
- Media pool: images, videos, screenshots, screen recordings, icons, 3D assets.
- Slide canvas: selected slide editing.
- Timeline: slide clip order and per-slide element timing.
- Inspector: selected slide or element properties.
- Preset browser: templates, style packs, typography presets, transitions.

### Interaction Rules

- Drag media to the timeline to create a slide.
- Drag media to a selected slide canvas to create an element.
- Double-click a slide clip to open detailed slide editing.
- Move slide clips to reorder deck structure.
- Stretch a slide clip to adjust presentation duration.
- Use element lanes inside a slide to control appearance timing.
- Scrub the timeline to preview the deck as a timed presentation.
- Press Play to preview slide transitions and element animations.

## Key Workflows

### Workflow A: Create From Goal

1. User opens PPT Generator.
2. User chooses a goal: product intro, lesson, report, portfolio, proposal.
3. User adds source material: text, images, video, timeline markers, screenshots.
4. Planner creates an editable outline.
5. Layout engine generates a first deck.
6. User edits on canvas/timeline.
7. User exports PPTX/PDF/video.

### Workflow B: Create From Existing Timeline

1. User selects a video project or timeline range.
2. Tool extracts important moments: markers, cuts, zoom actors, titles, effects.
3. User selects deck type: tutorial, pitch, recap, case study.
4. Tool creates slide clips from timeline events.
5. User edits slide text and visual emphasis.
6. Tool exports PPTX and optional narrated video.

### Workflow C: Manual Deck Authoring

1. User creates blank deck or template deck.
2. User adds slide clips on timeline.
3. User edits each slide on canvas.
4. User applies typography/effect presets.
5. User runs validation.
6. User exports.

### Workflow D: AI Update Existing Deck

1. User imports PPTX or opens a generated deck spec.
2. User asks: "make it shorter", "make it more visual", "add comparison".
3. AI planner updates deck structure, not just raw pixels.
4. User reviews diff: added/removed/changed slides.
5. User accepts or rejects changes.

## Required New Modules

The feature should live under a new pure core package and separate UI adapters.

```text
app/pptgen/
  __init__.py
  schema.py
  timeline.py
  planner.py
  layout.py
  templates.py
  theme.py
  assets.py
  autosave.py
  history.py
  typography_adapter.py
  effects_adapter.py
  validation.py
  preview.py
  writer.py
  writer_ooxml.py
  writer_python_pptx.py
  import_pptx.py
  export_video.py
  report.py

app/pptgen/ui/
  window.py
  canvas.py
  timeline.py
  inspector.py
  media_panel.py
  template_panel.py

app/actions/
  ppt_namespace.py

tests/
  test_pptgen_schema.py
  test_pptgen_timeline.py
  test_pptgen_layout.py
  test_pptgen_writer.py
  test_pptgen_validation.py
  test_pptgen_actions.py
```

The core `app/pptgen` package must not import Qt. UI code may import Qt only
under `app/pptgen/ui` or editor workflow modules.

## Existing Code Reuse

### Reuse As Concepts Or Adapters

- `app/timeline_model.py`
  - Reuse timing concepts, clip fields, transition thinking, marker logic.
  - Do not reuse video-specific classes directly as the PPT source of truth.

- `app/typography.py`
  - Reuse `TextStyle`, `AnimationConfig`, and `TextClip` ideas.
  - Add PPT-specific style conversion because PPT text boxes differ from video
    rendered text.

- `app/typo_presets.py`
  - Reuse preset metadata as style inspiration.
  - Complex video typography effects may need raster or video baking.

- `app/typo_animations.py`
  - Reuse easing and transform concepts.
  - Map only simple animations to native PPT animations at first.

- `app/color_grading.py` and `app/video_filters.py`
  - Reuse as image/video preprocessing when embedding visual assets.
  - Do not pretend all video effects have native PPT equivalents.

- `app/timeline_thumbnail_cache.py`
  - Reuse the cache idea.
  - Split a Qt-free image cache if PPT preview needs it.

- `app/review_automation/ppt_export.py`
  - Use as a low-level OOXML reference only.
  - Do not build user-facing deck logic on top of review automation.

### Do Not Reuse Directly

- `app/video_editor_window.py`
- Review automation deck scenario modules
- Real-time preview loops
- Timeline paint classes without a clean adapter
- Hard-coded product catalog templates

## Data Model

### DeckSpec

Fields:

- `id`
- `title`
- `purpose`
- `language`
- `aspect_ratio`
- `theme`
- `slides`
- `sections`
- `assets`
- `metadata`

### SlideSpec

Fields:

- `id`
- `title`
- `layout_id`
- `section_id`
- `background`
- `elements`
- `transition`
- `duration_ms`
- `speaker_notes`
- `tags`

### SlideElement

Common fields:

- `id`
- `kind`
- `name`
- `x`
- `y`
- `w`
- `h`
- `rotation`
- `z_index`
- `opacity`
- `style`
- `animation`
- `locked`
- `visible`

Kinds:

- `text`
- `image`
- `video`
- `shape`
- `table`
- `chart`
- `callout`
- `icon`
- `frame_capture`
- `timeline_snapshot`
- `code_block`
- `3d_preview`

### PptTimeline

Fields:

- `slide_clips`
- `playhead_ms`
- `selected_slide_id`
- `zoom`
- `markers`

### SlideClip

Fields:

- `id`
- `slide_id`
- `start_ms`
- `duration_ms`
- `transition_in`
- `transition_out`
- `collapsed`
- `label_color`

### ElementTiming

Fields:

- `start_ms`
- `end_ms`
- `in_animation`
- `hold_animation`
- `out_animation`
- `trigger`
- `click_index`
- `easing`

If an element has no timing, it is visible for the whole slide.

## Template System

Templates should be semantic, not just images.

### TemplateSpec

Fields:

- `id`
- `name`
- `purpose`
- `aspect_ratio`
- `theme_tokens`
- `slide_layouts`
- `placeholder_roles`
- `font_policy`
- `spacing_policy`

### Layout Types

MVP layouts:

- Cover
- Title and body
- Image hero
- Two-column comparison
- Three-card summary
- Timeline / process
- Table
- Chart
- Quote
- Section divider
- Closing slide

Later layouts:

- Case study
- Product feature
- Before/after
- Tutorial step
- Device mockup
- Multi-screen workspace
- Video frame analysis
- 3D object showcase

## Auto Layout Engine

The layout engine is the quality core. It should solve common problems before
the user sees the slide.

Required behavior:

- Fit title and body into safe areas.
- Preserve image aspect ratio.
- Choose crop/fit/fill behavior per placeholder.
- Avoid overlap between text and media.
- Detect text overflow.
- Detect off-slide elements.
- Scale font within bounds when necessary.
- Maintain visual hierarchy.
- Apply consistent margins and spacing.
- Support CJK text without broken wrapping.
- Produce validation warnings when a layout cannot be made clean.

MVP can use deterministic rules. A later version can add search-based layout
scoring.

## Typography Rules

Text must be presentation-native by default.

MVP:

- font family
- size
- weight
- color
- alignment
- line height
- fill/background
- outline
- shadow
- basic position

Later:

- rich text spans
- per-word emphasis
- auto title shortening
- language-aware wrapping
- text style diffing
- speaker-note to slide-summary generation

Native PPT text should be preferred for editable text. Rasterized text is
allowed only when the effect cannot be represented cleanly in PPT.

## Animation And Transition Rules

MVP native mappings:

- fade in/out
- slide in/out
- scale/zoom
- simple appear/disappear
- dissolve slide transition

Preview-only or baked mappings:

- glitch
- RGB split
- per-glyph typography
- motion blur
- complex node effects
- video-style masks

Each animation should store both:

- a native PPT hint
- a preview/render hint

This keeps PPTX export and video preview honest.

## Media Handling

Supported source types:

- image files
- video files
- timeline frame captures
- screenshots
- project thumbnails
- audio/narration
- existing PPTX assets
- charts/tables from CSV or typed data
- 3D preview images

Rules:

- Embed images in PPTX when possible.
- Link or embed video based on export target.
- Preserve original asset paths in metadata.
- Create optimized preview thumbnails.
- Detect missing media.
- Allow relink.
- Store generated derivatives under a stable cache path.

## Importable And Renderable Asset Expansion

TigerCapture already has a strong AR/PBR path: imported 3D assets can be
rendered with high-quality lighting, materials, shadows, reflections, depth
occlusion, and video compositing. The PPT generator should use the same product
idea for other rich asset families:

```text
Bring rich creative assets into TigerCapture, render or bake them well, then
place the result into PPT as editable metadata plus compatible media.
```

The important distinction is native PPT support versus TigerCapture-rendered
support.

- Native PPT support means the generated PPTX can contain an editable object
  that PowerPoint/Keynote understands.
- TigerCapture-rendered support means TigerCapture keeps the rich source data
  and exports a compatible still image, image sequence, transparent video, or
  ordinary embedded video for the deck.

### Priority Asset Families

| Priority | Asset family | Source examples | PPT output strategy | Why it matters |
| --- | --- | --- | --- | --- |
| P0 | AR/PBR 3D object | GLB, GLTF, FBX, OBJ-style imports | Rendered PNG, transparent video, optional GLB passthrough | Already a TigerCapture strength; gives decks premium product visuals. |
| P0 | Timeline frame / clip moment | video clip, marker, zoom actor, color grade | Still frame, short MP4, before/after pair | Turns existing video edits into slide evidence quickly. |
| P0 | Typography/title cards | `TextClip`, typography presets, subtitles | Native text when simple; raster/video when complex | Makes decks feel designed instead of plain. |
| P0 | Screenshots and screen recordings | capture region, app window, imported recording | Cropped image, annotated image, MP4 | Core TigerCapture source material. |
| P1 | Live2D actor | model3/moc runtime, performance source | Transparent PNG or alpha video; metadata retained | Useful for VTuber, education, character-led presentations. |
| P1 | MMD actor | PMX/PMD/PBX + VMD | Transparent PNG/MP4 with toon render and bloom | Strong visual differentiator for character or music decks. |
| P1 | Spine actor | Spine JSON/SKEL + atlas | Transparent PNG/MP4 or sprite sequence | Good for game, marketing, and character motion slides. |
| P1 | VRM/avatar capture | VRM, VSeeFace/performance source | Avatar still/video, optional camera-framed live persona card | Bridges presentation and presenter identity. |
| P1 | Color/VFX look | LUT, color grade, node graph, masks | Processed image/video plus editable effect metadata | Lets users make visual comparison slides from real edits. |
| P1 | Audio/narration | extracted audio, voice cleanup, loudness preset | Embedded audio, waveform/spectrum image, speaker notes | Useful for narrated decks and presentation rehearsal. |
| P1 | Charts/tables/data | CSV, typed rows, project metrics, manual data | Native table/chart where possible; image fallback | Required for business/report decks. |
| P2 | Depth/camera solve visual | depth map, road plane, occlusion preview | Split-view slide, depth matte image, AR proof clip | Explains spatial compositing clearly. |
| P2 | Node graph/workflow graph | effect node graph, automation steps | SVG-like diagram or raster graph | Makes technical/process decks clearer. |
| P2 | Comparison/device mockup | laptop/multi-monitor templates, phone frames | Composited image with real captures | Useful for product decks and case studies. |
| P2 | 360/panorama/environment | HDRI, equirectangular image, skybox | Cropped environment still, optional 360 preview video | Supports immersive/space/product context slides. |
| P3 | Interactive/live camera | webcam, virtual camera, presenter view | PPT cameo-like intent; baked video fallback | Nice later, but native interoperability is fragile. |
| P3 | PDF/document/page import | PDF pages, DOCX screenshots, web pages | Page images plus extracted text | Useful but should not distract from media-first MVP. |

### Asset Strategy By Output Type

#### Native PPT Objects

Use native objects when editability matters and the feature maps cleanly:

- plain text boxes
- images
- simple shapes
- icons/SVG where supported
- tables
- basic charts
- embedded MP4/audio
- optional GLB/3D model passthrough if writer support is added

#### TigerCapture-Rendered Objects

Use rendered outputs when visual quality matters more than PowerPoint
editability:

- AR/PBR beauty renders
- AR/PBR transparent overlays
- MMD toon/bloom/shadow renders
- Live2D/Spine actor frames
- complex typography effects
- node-processed images
- depth occlusion demos
- 3D gizmo/placement explanation frames

Each rendered object should preserve source metadata so the user can reopen it
in TigerCapture and re-render at higher quality.

### PPT Generator Import Menu

The PPT generator should eventually expose these import choices:

- Import Image/Video/Audio
- Import 3D Object
- Import Actor
  - Live2D
  - Spine
  - MMD
  - VRM/avatar
- Import Timeline Moment
- Import Screen Capture
- Import Data Table/Chart
- Import Node Graph/Effect Look
- Import PDF/Page

The UI can still show a simple "Import" button first. The asset router should
classify file types and suggest the correct treatment.

### Suggested Internal Element Kinds

Add these element kinds beyond the MVP list:

- `ar_pbr_render`
- `actor_render`
- `mmd_render`
- `live2d_render`
- `spine_render`
- `timeline_moment`
- `screen_capture`
- `effect_before_after`
- `depth_visualization`
- `waveform`
- `node_graph_diagram`
- `device_mockup`
- `data_chart`
- `pdf_page`

### Compatibility Notes

- PowerPoint recommends MP4 with H.264 video and AAC audio for broad
  compatibility.
- PowerPoint uses glTF/GLB as the preferred Office 3D model path; FBX support
  has been turned off in Office and should not be a target output format.
- Keynote supports USD-family 3D objects such as USDZ, USDA, and USDC.
- Both PowerPoint and Keynote have live-camera presentation concepts, but the
  PPT generator should treat live camera as an intent or baked media source
  until native writer support is proven.

### Recommended Order

1. AR/PBR render element: still PNG plus short MP4/alpha-video export.
2. Timeline moment element: selected video frame/clip segment with grade/effects.
3. Typography/title-card element: native text first, baked effect fallback.
4. Screen capture element: annotated screenshot and short recording.
5. Actor render element: Live2D/Spine/MMD still and transparent video.
6. Data chart/table element: CSV to native chart/table.
7. Node/depth/process visualization elements.

## PPTX Writer Strategy

### MVP Writer

Use `app/pptgen/writer_python_pptx.py` as the default user-facing writer. It
creates the deck through `python-pptx` for package validity and then applies
small OOXML patches for supported animation timing. The older minimal OOXML
writer remains useful as a low-level reference and static test helper, but it
is not the primary export path for user decks.

Pros:

- Python-native.
- Does not require PowerPoint.
- Good for slides, text boxes, images, shapes, tables, and basic charts.

Cons:

- Limited animation/transition support.
- Some advanced PowerPoint features require direct OOXML patching.
- Animation patches must stay host-validated because malformed timing XML can
  make PowerPoint reject the whole file.

### Advanced Writer

Add a lower-level OOXML patch layer for:

- transitions
- animation timing
- media properties
- master/theme details
- custom XML metadata

### PDF Export

PDF export is a conversion step after PPTX generation, not a separate renderer.
The shared implementation is `app/pptgen/pdf_export.py`.

Supported backends:

- `auto`: try LibreOffice first, then PowerPoint COM on Windows.
- `libreoffice`: use `soffice --headless --convert-to pdf`.
- `powerpoint_com`: use local Microsoft PowerPoint through COM automation.

Product behavior:

- UI export should report which backend produced the PDF.
- Actions should return backend attempts for automation diagnostics.
- If neither backend is available, fail with a clear reason instead of silently
  writing an empty or stale PDF.

### Validation Writer

Use generated PNG previews or conversion outputs to detect:

- missing images
- broken text
- empty slides
- out-of-bounds objects
- severe visual mismatch

## Preview Strategy

The editor needs preview at two levels.

### Fast Canvas Preview

- Qt-based canvas.
- Good enough for editing.
- Uses the same DeckSpec model.
- Not expected to be pixel-identical to PowerPoint.

### Export Validation Preview

- Render generated PPTX to images using an available backend.
- Compare page count, dimensions, missing assets, and visible content.
- Store validation report.

Candidate render backends:

- LibreOffice headless for PPTX to PDF/images.
- PowerPoint COM on Windows as optional high-fidelity validation.
- Internal raster preview for quick tests.

## AI Planner

The AI planner should create structured DeckSpec, not direct pixels.

Inputs:

- user goal
- source text
- timeline selection
- media files
- project metadata
- target audience
- desired length
- style preset

Outputs:

- outline
- slide specs
- speaker notes
- asset recommendations
- validation issues

Planner modes:

- draft from prompt
- summarize source material
- convert video timeline to deck
- improve existing deck
- shorten deck
- make more visual
- add speaker notes
- translate/localize

## Automation And Actions

Add `app/actions/ppt_namespace.py`.

Required actions:

- `ppt.project.create`
- `ppt.project.open`
- `ppt.project.save`
- `ppt.project.save_as`
- `ppt.deck.from_prompt`
- `ppt.deck.from_timeline`
- `ppt.deck.apply_template`
- `ppt.deck.validate`
- `ppt.deck.export_pptx`
- `ppt.deck.export_pdf`
- `ppt.deck.export_video`
- `ppt.slide.add`
- `ppt.slide.remove`
- `ppt.slide.duplicate`
- `ppt.slide.move`
- `ppt.slide.set_layout`
- `ppt.slide.set_duration`
- `ppt.slide.set_notes`
- `ppt.element.add_text`
- `ppt.element.add_image`
- `ppt.element.add_video`
- `ppt.element.add_shape`
- `ppt.element.add_chart`
- `ppt.element.update`
- `ppt.element.remove`
- `ppt.element.arrange`
- `ppt.timeline.select_slide`
- `ppt.timeline.set_playhead`
- `ppt.timeline.play_preview`

All actions should support dry-run where practical.

## Editor Integration

Do not wire the first version into `video_editor_window.py`.

Suggested integration modules:

```text
app/video_editor_ppt_workflow.py
app/pptgen/ui/window.py
app/pptgen/ui/canvas.py
app/pptgen/ui/timeline.py
app/pptgen/ui/inspector.py
```

Menu placement:

- File -> New -> Presentation
- File -> Export -> PowerPoint
- Media Pool context -> Create Presentation From Selection
- Timeline context -> Create Slides From Range

The PPT generator can open as a separate window at first. Full integration can
come after the core model and writer stabilize.

## Export Targets

MVP:

- PPTX
- PNG slide images
- validation JSON
- PDF
- MP4 presentation video

Next:

- HTML preview
- template package

Later:

- editable import from PPTX
- Google Slides export bridge
- speaker mode
- presenter recording

## Validation Requirements

Every generated deck should return a validation report.

Checks:

- deck has at least one slide
- every slide has visible content
- no required asset is missing
- text overflow warning
- element out-of-bounds warning
- duplicate z-index warning
- unsupported animation warning
- unsupported media embedding warning
- export file exists and is non-empty
- optional rendered preview page count matches slide count

Validation should not block export unless the error is fatal. It should explain
what the user can fix.

## Visual Quality Rules

- Do not overuse cards.
- Keep templates quiet, readable, and purpose-specific.
- Use large imagery when the slide is visual.
- Keep report slides dense but not cramped.
- Avoid generic marketing gradients.
- Preserve contrast and text legibility.
- Use subtle slide backgrounds.
- Make template colors configurable.
- Keep CJK font fallback strong.
- Avoid tiny UI labels in final slides unless the slide is a screenshot.

## Implementation Phases

### Phase 0: Spec And Boundaries

Deliverables:

- This spec.
- Initial TODO list.
- Confirm dependency policy for PPTX writer.

Exit criteria:

- User agrees on timeline-based PPT model.
- Review automation boundary is documented.

### Phase 1: Pure Core MVP

Deliverables:

- `app/pptgen/schema.py`
- `app/pptgen/timeline.py`
- `app/pptgen/validation.py`
- tests for schema/timeline/validation

Capabilities:

- Create DeckSpec.
- Add/move/remove slides.
- Add text/image elements.
- Validate basic issues.

Exit criteria:

- DeckSpec can round-trip JSON.
- Timeline slide ordering is deterministic.

### Phase 2: Writer MVP

Deliverables:

- `app/pptgen/writer.py`
- `app/pptgen/writer_python_pptx.py` or minimal OOXML writer
- writer tests

Capabilities:

- Export PPTX with text, images, shapes, simple tables.
- Export PNG contact sheet if possible.

Exit criteria:

- A generated deck opens in PowerPoint/LibreOffice.
- Validation report identifies missing assets and overflow risk.

### Phase 3: Template And Layout

Deliverables:

- `app/pptgen/templates.py`
- `app/pptgen/theme.py`
- `app/pptgen/layout.py`
- built-in starter templates

Capabilities:

- Generate cover, body, image hero, comparison, table, chart layouts.
- Auto-fit text and images.

Exit criteria:

- User can create a decent first draft without manual placement.

### Phase 4: UI Prototype

Deliverables:

- standalone PPT generator window
- canvas preview
- slide timeline
- inspector
- media pool bridge

Capabilities:

- Create/edit slides manually.
- Reorder slide clips.
- Drag media to create elements.
- Export PPTX.

Exit criteria:

- User can make a short deck without touching the video editor facade.

### Phase 5: Timeline And Editor Bridge

Deliverables:

- `app/video_editor_ppt_workflow.py`
- timeline-to-deck adapter
- action namespace

Capabilities:

- Create deck from timeline markers/clips/screenshots.
- Create slides from selected video range.
- Reuse typography presets.
- Export through render queue later if needed.

Exit criteria:

- Existing editor project can produce a presentation draft.

### Phase 6: Product Polish

Deliverables:

- richer templates
- AI planner
- PPTX import improvement
- presenter preview
- video/PDF export

Capabilities:

- Goal-based deck generation.
- Shorten/improve/localize decks.
- Present and record.

Exit criteria:

- Feature can be used as a real product workflow.

## Dependency Policy

Recommended first path:

- Use pure dataclasses and JSON for core.
- Add `python-pptx` only for writer MVP if dependency review accepts it.
- Use Pillow for preview/contact sheet if already available.
- Use LibreOffice/PowerPoint COM only as optional validation tools.

Avoid:

- Requiring Node just for PPTX generation.
- Requiring PowerPoint for core export.
- Commercial SDKs unless product licensing is decided.

## Risks

### PPTX Fidelity Risk

Native PPTX animation support is harder than static slide export.

Mitigation:

- Support static deck quality first.
- Store animation intent separately.
- Add OOXML patches only where needed.

### Layout Quality Risk

Bad auto layout makes the product feel cheap.

Mitigation:

- Start with fewer, stronger templates.
- Add validation warnings.
- Prefer clean default layouts over many mediocre ones.

### Scope Risk

Trying to recreate PowerPoint will explode scope.

Mitigation:

- Focus on timeline-based creation, media conversion, AI outline, and export.
- Leave deep PowerPoint compatibility for later.

### Editor Coupling Risk

If the feature is wired directly into editor internals, refactors become painful.

Mitigation:

- Keep `pptgen` pure.
- Use adapters for timeline, typography, media pool, and actions.

## MVP Definition

The first useful product version should support:

- Create a deck from a prompt or blank template.
- Add slide clips on a PPT timeline.
- Edit slide title/body/image on a canvas.
- Apply one of a few clean templates.
- Export PPTX.
- Produce a validation report.
- Generate PNG previews for chat/remote review.

The MVP does not need:

- perfect PPT import
- full native animations
- Google Slides integration
- every PowerPoint feature
- live collaborative editing

## Success Criteria

Technical:

- Core modules are Qt-free and testable.
- Writer exports valid PPTX.
- Validation catches common broken decks.
- Actions can create and export a small deck.

UX:

- A non-designer can make a clean 5-slide deck quickly.
- Timeline order and slide timing are obvious.
- Text overflow and missing media are visible before export.
- Exported slides do not look like debug output.

Product:

- The feature is clearly different from PowerPoint/Keynote because it is
  timeline-native and media-aware.
- It reuses TigerCapture strengths: media pool, screenshots, video timeline,
  typography presets, effects, and automation.

## Immediate TODO

1. Create `app/pptgen/schema.py`.
2. Create `app/pptgen/timeline.py`.
3. Create `app/pptgen/validation.py`.
4. Add JSON round-trip tests.
5. Decide writer dependency: `python-pptx` vs minimal OOXML.
6. Add a tiny sample deck export.
7. Add PNG preview/contact sheet.
8. Add action namespace skeleton.
9. Build standalone UI prototype only after the core passes tests.
