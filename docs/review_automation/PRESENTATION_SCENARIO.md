# Presentation Scenario Rules

Last updated: 2026-07-03

This file defines the review automation story shape. It is a compact scenario
contract; the expanded current-spec scenario remains in:

```text
docs/CURRENT_SPEC_PRESENTATION_SCENARIO.md
```

## Required Discovery Before Rebuild

Before rebuilding PPT/HTML/catalog output, inspect the current project state.
The product changes frequently, so stale deck memory is not enough.

Minimum inputs:

- `SPEC.md`
- `README.md`
- `TODO.md`
- `docs/RELEASE_POSITIONING.md`
- `docs/SPEC_REVIEW_AUTOMATION.md`
- feature `docs/SPEC_*.md` files
- `docs/review_automation/*`
- Python Action registry
- current sample manifest and review reports under `../ReviewAutomationWorkspace/`

Preferred source footage for visual catalog captures:

```text
C:\Users\artmouse\Videos\TigerCapture\YouTube Imports
```

When multiple clips are available, prefer city scenery, night skylines,
drone/aerial footage, car racing, motorsport, driving, and cinematic HDR/OLED
demo clips. These make product screenshots feel like real creator work rather
than QA fixtures.

Current catalog exclusion:

```text
Do not use Le Mans / 24 Hours of Le Mans / FIA WEC footage in product-catalog
PPT screenshots, source notes, media-pool reference items, or overview pages.
```

## Deck Modes

- `summary`: short product-catalog introduction.
- `detailed`: main feature-by-feature catalog deck with real editor evidence.
- `evidence-full`: internal appendix only. This mode may show QA/evidence rows,
  but those pages must not leak back into product-facing catalog modes.

## Main Story

The deck should feel like a studio tour:

1. TigerCapture is more than a recorder.
2. It imports or captures real media into a local editing session.
3. It can polish, cut, grade, process audio, add typography, use actors, and
   compose node/3D/VTuber workflows.
4. Each feature is shown through a real automated editor state.
5. The final output is a product catalog, not a QA report.

## Feature Page Rule

A feature page is valid only when the screenshot matches the feature:

- General capture rule: prefer multi-track timelines. A strong catalog screenshot
  should show video plus at least one meaningful companion lane, such as audio,
  effects, color grade, typography, transition, actor, node, marker, or keyframe
  lanes. Single-track captures are allowed only when the feature genuinely needs
  an isolated view.
- Long-session texture rule: product-catalog screenshots must not look like a
  tiny test clip. Prefer real imported clips with a visibly long timeline,
  multiple media-pool sources, and at least one practical edit state. Short
  six-second/sample timelines are allowed only for tightly cropped feature
  details, not for overview, laptop, or multi-monitor hero pages.
- Natural edit texture rule: some screenshots should include a random-looking
  mid-timeline cut, adjacent clip boundary, marker, or transition to suggest a
  real editing session. Do not force this into every screenshot; repeated
  cut/transition layouts across all pages look artificial.
- Cut/editing: timeline zoom, cut markers, selected clip.
- Color grading: real footage, grading controls, before/after or scopes.
- Node graph: connected nodes and selected node parameters.
- Audio: waveform, mixer, spectrum/EQ/dynamics, or sound editor.
- Typography: visible text on canvas plus keyframes/controls.
- Transition/effects: effect or transition applied to a real clip.
- Live2D/actor: actor visible, actor lane/keyframes, actor controls.
- 3D/AR/PBR: use a real approved GLTF/GLB asset from `E:\ClaudeCodeApp\3d`,
  show the model in the Viewer, and keep placement/material/lighting controls
  visible. Do not use motorcycle debug evidence for catalog captures. Do not
  repeat the Poly Haven camera model on every 3D page; prefer `Nexus_RX` or
  `Police_car` when they render cleanly, and reserve the camera model for
  camera-specific pages or fallback.
- VTuber: Program Output separated from Performance Source/tracking input.

If the real UI cannot show the feature, mark the page pending instead of
showing a generic editor screenshot.

## Screenshot-Driven Copy Revision

The scenario is a draft until real editor captures exist. After each feature
screenshot or GIF is captured, inspect the visible UI and revise the slide title,
body copy, and caption to match the actual evidence.

Rules:

- If the capture shows the intended feature clearly, keep or strengthen the
  product wording.
- If the capture shows only setup, partial controls, or a weaker feature state,
  lower the wording to match what is visible.
- If the capture is generic, empty, broken, or unrelated, reject it and recapture
  instead of writing around it.
- If a feature is not currently implemented or visually reliable, mark it
  pending/guarded or remove it from product-catalog modes.

This means deck writing is iterative:

```text
latest spec -> scenario draft -> real action capture -> screenshot inspection
-> copy rewrite -> final catalog page
```

## Current 3D Catalog Scope

The current product scenario should cover AR/PBR 3D object compositing only
where real TigerCapture UI and real capture evidence exist.

Future engine-handoff work must be reintroduced as a separate explicitly
verified feature with real UI evidence before it enters summary, detailed, or
product-catalog deck outlines.
