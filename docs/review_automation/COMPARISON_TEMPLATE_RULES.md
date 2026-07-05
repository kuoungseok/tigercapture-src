# Comparison Template Rules For Review Automation

Last updated: 2026-07-05

These rules translate `docs/SPEC_COMPARISON_TEMPLATES.md` into product-catalog
review automation behavior.

## Purpose

Comparison Templates are used in review/catalog output to make a real feature
delta readable:

- original vs edited,
- effect off vs effect on,
- color off vs color on,
- selected node off vs selected node on,
- old UI vs renewed UI,
- before audio vs processed audio.

They are not decorative PIP presets, QA evidence boxes, or generic split-screen
graphics. Use them only when the comparison itself helps the viewer understand
what TigerCapture/Tiger Studio changed.

## Product Story Rule

Every comparison page must answer one visible question:

```text
What changed, and why is that useful to a creator?
```

If the slide cannot answer that question from the screenshot alone, do not use
a comparison template on that slide.

## Allowed Review Uses

Use comparison templates for these catalog stories:

- Color grading: `Original | After`, `Color Off | Color On`, LUT/HDR look
  before/after.
- Node graph: `Selected Node Off | On`, `Node Chain Off | On`, masked effect
  before/after.
- Effects: blur, sharpen, denoise, stabilization, background removal, glow,
  vignette, film grain, pixelate, or other implemented effect off/on states.
- AI processing: source state vs AI-assisted result, only when the real editor
  state shows Claude/local-AI action context or the edited result.
- Audio: waveform, spectrum, EQ, dynamics, cleanup, or loudness before/after.
- UI renewal/internal catalog: old capture vs renewed capture, only when the
  page is explicitly about UI renewal.
- Prompt-to-result: input/source prompt or media vs generated result, only when
  both sides are real captured product states or real generated output from the
  tool. Do not invent synthetic editor evidence.

Avoid comparison templates for:

- overview slides where the main point is the whole studio layout,
- multi-monitor hero slides unless one monitor is specifically explaining a
  before/after feature,
- 3D/AR/PBR pages where the model itself is the evidence unless occlusion,
  lighting, or depth-aware compositing before/after is visible,
- Live2D/Spine/MMD pages unless the actor visibility/transform/opacity change
  is the actual story,
- any page where the screenshot already looks crowded.

## Template Priority

Review automation should prefer these templates in this order:

1. `Before / After Split`
   - Best default for color, effects, node changes, UI renewal, and AI result
     pages.
2. `Wipe Reveal`
   - Use when a divider communicates the transformation more clearly than a
     static split.
3. `Zoom Detail Compare`
   - Use with the laptop+iPad emphasis template when the important change is
     small, such as mask edge quality, denoise detail, subtitles, or UI control
     refinement.
4. `Audio Compare`
   - Use on sound-editor pages only when waveform/spectrum/EQ or dynamics
     changes are visible.
5. `A/B Grid`
   - Use sparingly for multi-variant presets or model/result comparisons.
6. `Benchmark Compare`
   - Developer/internal only. Product catalog slides must not show QA scores,
     pass counts, raw metrics, or implementation health dashboards.

`Overlay Fade`, `Prompt To Result`, and multi-variant layouts are later-phase
stories unless the real editor capture already supports them clearly.

## Source Mode Rules

Default to single-source compare.

Single-source compare means one clip produces both sides from different render
states:

- `Original / Current`
- `Effects Off / On`
- `Color Off / On`
- `Selected Node Off / On`

Use dual-source compare only when the two sources are genuinely different
captures or assets:

- old UI recording vs renewed UI recording,
- external AI result vs TigerCapture result,
- two rendered clips,
- before audio render vs processed audio render.

Dual-source compare must keep crop, zoom, and sync visually aligned. If the two
sources cannot be aligned, do not use the comparison as a polished catalog
slide.

## Canvas Requirements

The comparison must be visible on the video canvas or on a real editor/viewer
surface. It is not enough to show a popup list or inspector saying a comparison
exists.

Required visible elements:

- both comparison states,
- readable labels,
- visible divider or layout boundary,
- real media or real editor output,
- at least one nearby feature control or context surface when possible.

Default labels:

```text
Original | After
```

Feature-specific labels are allowed when they are clearer:

- `Color Off | Color On`
- `Node Off | Node On`
- `Effect Off | Effect On`
- `Before EQ | After EQ`
- `Old UI | Renewed UI`

Keep labels short. Do not write long explanatory text inside the video canvas.

## Visual Style Rules

Use comparison overlays as quiet product UI:

- compact high-contrast canvas pills,
- thin divider,
- no loud neon borders,
- no large explanatory panels,
- no fake metric strips in product catalog pages,
- no decorative PIP frames,
- no unrelated generated imagery.

The comparison must still feel like a real editor screenshot inside the catalog
template. The user should see a creator editing, not a marketing mockup pasted
over the viewer.

## Action And Implementation Boundary

Current implemented MVP bridge actions:

```text
ui.viewer.compare.set
ui.viewer.fit
```

These may be used to create preview-safe viewer comparison evidence.

Do not claim the full export-safe `comparison_view` object API unless it is
implemented and verified. Until then, phrase catalog copy as viewer/editor
comparison, not as a finished export-template engine.

Longer-term actions from `SPEC_COMPARISON_TEMPLATES.md` may be mentioned only
in planning or internal TODOs:

```text
comparison.create
comparison.set_template
comparison.set_scope
comparison.set_sources
comparison.set_labels
comparison.set_split
comparison.set_sync
comparison.set_enabled
comparison.toggle_export
comparison.remove
```

## Screenshot Rules

Before using a comparison screenshot in a deck:

1. Capture real media from the editor, preferably from
   `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`.
2. Verify the comparison state is actually visible.
3. Verify the labels match the slide claim.
4. Verify the feature effect is visually noticeable.
5. If the difference is too subtle, use `Zoom Detail Compare` or recapture a
   stronger example.
6. If the comparison shows only a generic split but no clear feature outcome,
   reject it.

## Recommended Catalog Placement

Use comparisons on feature-specific pages, not as a default for every slide.

Good placements:

- Color Grading Workspace
- Node Graph Composition
- Effects And Background Tools
- AI-Assisted Editing
- Sound Editor / EQ / Dynamics
- UI Renewal comparison pages

Weak placements:

- first multi-monitor overview,
- general studio thesis page,
- product readiness/final page,
- pages whose main evidence is actor/3D visibility rather than a before/after
  transformation.

## Copy Rules

Allowed copy direction:

```text
Compare the raw clip with the edited result directly in the viewer.
```

```text
Toggle a node, grade, or effect and keep the change readable on the canvas.
```

```text
Show original/current, color off/on, effects off/on, and selected node off/on
without duplicating clips by hand.
```

Avoid:

- "full Fusion replacement",
- "complete benchmark dashboard",
- "export-safe comparison engine" unless implemented,
- "AI-generated proof" when the screen is not real editor output.

## Readiness Rule

A comparison page is catalog-ready only when all of these are true:

- real editor/viewer capture,
- visible before/after states,
- labels readable,
- feature-specific effect visible,
- slide copy matches the screenshot,
- no QA metrics or raw debug details,
- no fake generated editor UI.

