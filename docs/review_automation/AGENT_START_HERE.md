# Agent Start Here: Review Automation

Last updated: 2026-07-03

This is the first file a new Codex, Claude, or other coding agent should read
before touching TigerCapture review automation.

## One-Sentence Mission

Review automation creates product-catalog presentation assets that explain what
TigerCapture/Tiger Studio can do by driving the real editor, capturing real
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

1. `README.md`
2. `PURPOSE_RULES.md`
3. `CATALOG_PPT_STYLE.md`
4. `PRESENTATION_SCENARIO.md`
5. `PRODUCT_CATALOG_PT_SCENARIO.md`
6. `COMPARISON_TEMPLATE_RULES.md`
7. `MULTI_MONITOR_RULES.md`
8. `TEMPLATE_ASSET_MANIFEST.md`
9. `REVIEW_AUTOMATION_TODO.md`

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
  either the fixed approved templates or real TigerCapture editor captures.
- Prefer multi-track editor states for screenshots. A catalog capture should
  usually show more than one lane, such as video + audio, video + effect,
  video + typography, video + actor, or video + node/grade/keyframe lanes.
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
4. Verify sample media and template assets exist.
5. Verify feature-specific captures can be real.
6. Ask no extra questions if the requested mode is clear; otherwise choose the
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
- Cut/edit: zoomed timeline, selected clip, cut marker or edit boundary.
- Color: real footage plus grading controls, scopes, or before/after.
- Node graph: connected nodes plus selected node parameters.
- Audio: waveform, mixer, sound editor, spectrum, EQ, or dynamics.
- Comparison: use comparison templates only when the before/after state is
  visible on the canvas and the difference explains a real feature. Default to
  `Original | After`, `Color Off | Color On`, `Effect Off | Effect On`, or
  `Node Off | Node On` labels. Do not use generic PIP or fake split-screen
  graphics as product evidence.
- Typography: text on canvas plus text clip/keyframes/controls.
- Transitions/effects: applied effect or transition on real media.
- Live2D/actor: actor visible, actor lane/keyframes, actor controls.
- 3D/AR/PBR: use a real approved GLTF/GLB asset from `E:\ClaudeCodeApp\3d`,
  with the model visible and placement/material/lighting controls shown. Do not
  use the old motorcycle debug asset for catalog evidence. Do not repeat the
  Poly Haven camera model on every 3D page; prefer `Nexus_RX` or `Police_car`
  when they render cleanly, and reserve the camera model for camera-specific
  pages or fallback.
- VTuber: Program Output separated from Performance Source/tracking input.
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
