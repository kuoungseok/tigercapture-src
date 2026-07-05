# Current-Spec Presentation Scenario

Last updated: 2026-07-03

Canonical review automation rule hub:

```text
docs/review_automation/
```

New agents should start with:

```text
docs/review_automation/AGENT_START_HERE.md
```

Use that folder first for product-catalog purpose, PPT style, templates, and
review automation TODO. This document is the expanded current-spec story
reference.

This document defines the presentation scenario for the current TigerCapture /
Tiger Studio spec. It is not a generated deck. It is the narrative and capture
contract that the review automation should follow when it later builds PPTX,
HTML, catalog images, or phone-viewable PNG previews.

## Inputs Inspected

This scenario is based on the current local project state and these files:

- `SPEC.md`
- `README.md`
- `TODO.md`
- `docs/RELEASE_POSITIONING.md`
- `docs/SPEC_REVIEW_AUTOMATION.md`
- `docs/SPEC_UI_RENEWAL.md` for current live-editor surface status only, not
  catalog PPT typography or page design.
- `docs/SPEC_PYTHON_ACTION_SYSTEM.md`
- `docs/SPEC_AR_PBR_COMPOSITOR.md`
- `docs/SPEC_AI_TEXT_EDITING.md`
- `docs/SPEC_EXPORT_PARITY_AND_QA.md`
- `docs/SPEC_BROADCAST_SCENE.md`
- `docs/SPEC_VTUBER_STUDIO_BROADCAST.md`
- `docs/SPEC_VSEEFACE_BRIDGE.md`
- `docs/MULTI_MONITOR_REVIEW_SCENARIO_RULES.md`
- `docs/VTUBER_TRUMP_SOURCE_MAPPING_CONTEXT.md`
- `docs/review_reference_featpaper_style.md`
- Current action registry was inspected for automation coverage.
- Current review workspace outputs under `../ReviewAutomationWorkspace/`.

## Core Position

TigerCapture should be presented as:

```text
A local-first Windows creator studio for polished screen recordings,
AI-assisted editing, real timeline work, actor/avatar overlays, and
evidence-backed export/review automation.
```

Safe comparison language:

- Screen Studio-inspired polish, not full Screen Studio parity.
- CapCut-style creator assist, not CapCut-scale template/AI ecosystem.
- AI Script Edit MVP, not a Descript replacement.
- Creator-grade color/audio/VFX foundations, not Resolve/Fairlight/Fusion
  replacement.
- Dedicated Live2D/Spine actor tracks and guarded actor support, not universal
  game-resource compatibility.

## Visual Doctrine

Every product-facing slide must obey these rules:

- Catalog PPT design must follow the catalog PPT/reference rules only:
  `docs/review_reference_featpaper_style.md`,
  `docs/SPEC_REVIEW_AUTOMATION.md`, and the laptop/multi-monitor templates.
  Do not import main-editor UI-renewal typography, Qt widget spacing, or runtime
  app style tokens into the PPT page design.
- The deck is a product catalog and studio tour first. "Review automation"
  does not mean code review, QA status reporting, or release dashboard output.
  It means automated product demonstration: explaining what the tool can do and
  what creators can make with it.
- No empty editor screenshots.
- No fake generated editor UI as feature evidence.
- No color bars or placeholder test media.
- Use real YouTube Imports media for editor captures.
- Feature screenshots must show the feature being edited, not a generic editor.
- Public catalog pages use a quiet Feat Paper-style frame:
  off-white page, dark charcoal surround, large whitespace, thin rules, calm
  typography, real screenshot/device visual.
- Product-catalog slides must not show QA numbers, pass counts, action counts,
  scores, release booleans, raw report tables, or debug-style metrics.
- QA/debug details are allowed only in evidence-full appendix pages and machine
  metadata, not in product catalog story pages.
- Laptop and multi-monitor templates are product-story templates. Use them to
  show how TigerCapture works in a believable creator environment, not to frame
  QA dashboards or code-review/status pages.

## Deck Modes

The scenario supports the existing three output modes:

| Mode | Length Target | Purpose |
| --- | ---: | --- |
| `summary` | 6-8 slides | Quick product-catalog introduction. |
| `detailed` | 28-36 slides | Main presentation with feature-specific editor evidence. |
| `evidence-full` | 60+ slides | Internal appendix with QA/evidence rows and blocked items. |

The detailed deck is the main design target. Summary and evidence-full are
derived views of the same evidence graph.

## Detailed Deck Story Arc

The deck should feel like a studio tour, not a feature checklist.

```text
1. The problem:
   screen recordings and creator videos need polish, AI help, actors, post
   tools, and trustworthy export without a heavy professional suite.

2. The product:
   TigerCapture turns capture/import into a real local editing session.

3. The proof:
   each feature is shown through a real automated editor state.

4. The differentiator:
   local-first automation, actor/avatar tracks, node/audio/color workbenches,
   review evidence, and multi-monitor production surfaces.

5. The trust boundary:
   claims are backed by real evidence and explicit blocked states.
```

## Slide Scenario: Detailed Mode

### 1. Cover

- Message: TigerCapture is a local-first creator studio, not just a recorder.
- Visual: Feat Paper-style off-white catalog page, dark stage, real editor
  screenshot in laptop/monitor frame.
- Evidence requirement: real editor capture with imported YouTube video,
  visible Viewer, timeline clips, and playhead.

### 2. Product Thesis

- Message: Record, polish, edit, automate, and deliver without leaving the local
  workstation.
- Visual: minimal four-part diagram:
  `Capture -> Timeline -> Workbench -> Export`.
- Evidence requirement: no fake editor; use icons/diagram only, or a real
  contact sheet.

### 3. Current Editor Surface

- Message: The renewed editor shell is moving toward a compact, icon-first,
  professional workspace.
- Visual: full editor capture.
- Must show: Media Pool, Viewer, Timeline, Workbench/Inspector, real media.
- Do not show: empty import card as the main image.

### 4. Media Intake And Auto Polish

- Message: screen recordings and imported videos become polished demos.
- Visual: Viewer with real screen/video frame, cursor/click/hotkey/crop or zoom
  evidence.
- Capture recipe:
  `media.import_to_timeline -> screenstudio.apply_auto_polish -> capture`.

### 5. Timeline Editing

- Message: the core edit surface supports real cut/speed/effect work.
- Visual: zoomed timeline crop with split point, selected clip, speed/filter
  badge, playhead, visible clip body.
- Capture recipe:
  `media.import_to_timeline -> timeline.split -> clip.set_speed ->
  clip.set_filter -> timeline.set_zoom -> capture`.

### 6. Drag Presets And Creator Workflow

- Message: effects, transitions, titles, and workflows are item-first and
  drag-first.
- Visual: left preset browser with hover preview plus timeline drop guide.
- Must show: integrated preview, semantic icons, real Viewer frame underneath.

### 7. AI Command And Script Edit

- Message: AI edits are reviewable action plans, not arbitrary code.
- Visual: bottom AI Command dock or Script Edit panel with timeline still
  visible.
- Capture recipe:
  import transcript/sample -> generate edit plan -> preview reviewed cuts.
- Claim guardrail: do not claim Descript-class editing.

### 8. Local-First Automation

- Message: AI, MCP, and review automation use the registered Python Action
  System.
- Visual: clean architecture slide plus small real action log or evidence graph.
- Avoid: raw debug JSON, action counts, or QA metrics as the primary slide image.

### 9. Multilingual UI And Localization

- Message: Korean/Japanese/English UI quality is a product feature, not an
  afterthought.
- Visual: real UI capture in Korean or Japanese with no mojibake.
- Evidence requirement: targeted localization screenshot.
- Block if: text is garbled, cramped, or truncated.

### 10. Color Grading Workspace

- Message: color tools are becoming a real creator-grade workspace.
- Visual: Viewer with graded footage, Color Wheels deck, soft-glass sliders,
  scopes/curve evidence.
- Must show: real footage and active controls.
- Avoid: generic city footage unless grading controls are visibly applied.

### 11. Node Graph Composition

- Message: node workflows connect color, blur, glow, masks, LUTs, and HDR prep
  as editable chains inside the editor.
- Visual: Node Graph popout or Workbench node tab with connected nodes and
  selected node parameters.
- Must explain the available node-effect families:
  White Balance, Curves, Levels, Channel Mixer, LUT; Glow, Vignette, Film Grain,
  Unsharp Mask, Pixelate; Blur / soft pass; Power Window, HSL, tracked region,
  face/eyes/lips/person masks; SDR -> HDR EXR prep.
- Preferred chain example:
  `Media In -> White Balance -> Curves -> Glow -> Mask -> Output`.
- Capture recipe:
  `node.graph.set -> node.add -> node.connect -> node.set_param -> capture`.
- Must show: connected graph, real implemented node labels, and selected-node
  controller. A generic graph with unnamed boxes is not enough.

### 12. Masks And Object Tracking

- Message: masks and tracked regions make effects local, not global.
- Visual: Viewer with visible mask/selection result plus Workbench parameters.
- Capture recipe: create bitmap/power window, track/refine if available.
- Claim guardrail: do not imply full VFX-suite replacement.

### 13. Sound Editor And Audio Tracks

- Message: audio editing is moving into a dedicated dock/workbench.
- Visual: Sound Editor with waveform/spectrum/EQ or levels; timeline audio lane
  visible if possible.
- Capture recipe:
  `audio.extract_from_video -> audio.clip.set_gain -> audio.track.set_mix ->
  open sound editor -> capture`.
- Current gap: registered Sound Editor effect actions are limited; some capture
  wiring may still be needed.

### 14. Typography And Subtitles

- Message: text/title layers are timeline objects with keyframes and style.
- Visual: preview text over real video, text clip/keyframes, title controls.
- Capture recipe:
  `text.add -> text.set_keyframes -> capture`.

### 15. Transitions And Effects

- Message: transitions/effects are placed on real cuts, not just selected from a
  menu.
- Visual: timeline edit point, transition strip, effect lane, Workbench controls.
- Capture recipe:
  `timeline.split -> transition.apply -> clip.set_filter -> capture`.

### 16. Live2D Actor Track

- Message: Live2D actors sit on dedicated actor tracks and can be transformed or
  driven by performance sources.
- Visual: visible Live2D actor on Viewer, actor lane, transform/opacity keys,
  Live2D controls.
- Capture rule: block the slide if the actor is blank or visually broken.

### 17. Spine / NIKKE Actor Track

- Message: Spine/NIKKE support is guarded until visual compatibility evidence is
  strong enough.
- Visual: only use a known-good Spine render if it is visually correct.
- Current guardrail: do not use broken NIKKE/Spine render evidence in public
  catalog slides.
- Alternative: appendix-only compatibility/status slide.

### 18. AR/PBR 3D Object Compositor

- Message: 3D objects can be placed into video with lighting/material context.
- Visual: AR/PBR preview with the Poly Haven camera scene from
  `E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene`.
- Required asset: prefer `models\Camera_01\Camera_01_1k.gltf` or
  `models\Camera_01\Camera_01_1k.fbx`, with the texture folder and
  `wooden_studio_17` HDRI/material context where available.
- Guardrail: do not use the old motorcycle debug evidence for public catalog
  captures.
- Capture recipe:
  import camera scene -> add AR/PBR track -> set transform/material/lighting
  -> capture Viewer and Workbench controls.

### 19. VTuber Broadcast Mapping

- Message: VTuber Studio separates tracking input from final program output.
- Visual: dedicated VTuber Studio capture with:
  Program Output, Source Tracking, Avatar Mapping, Studio Controls.
- Required story:
  Trump face video is Performance Source only.
  Milica VRM / VSeeFace Bridge is Avatar Target.
  Program Output must not show raw Trump source as background.
- Use internal VRM fallback honestly if VSeeFace capture is black/degraded.

### 20. Multi-Monitor Studio

- Message: advanced work can spread across a production environment.
- Visual: Dell triple-monitor template with only real TigerCapture screenshots
  mapped into the three screens.
- Layout:
  left = actor/3D surfaces,
  center = Viewer + Timeline + AI,
  right = Node Graph + Sound Editor + scopes.
- Rule: no generated UI inside monitor screens.

### 21. Export And Render Queue

- Message: export is guarded by parity and diagnostics, not blind render.
- Visual: render queue/export panel with real project context and preview/export
  parity indicators.
- Include: MP4/WebM/MOV, vertical/square/4K/HDR metadata where evidence exists.

### 22. Evidence System

- Message: the review deck is generated from evidence, not manually invented.
- Visual: elegant evidence graph/contact sheet with links to screenshots and
  GIFs.
- Do not show raw giant JSON, QA scores, pass/fail counts, or dashboard rows as
  a product slide.

### 23. Competitive Positioning

- Message: TigerCapture is strongest at the intersection of screen polish,
  local creator assist, actor/avatar overlays, and post foundations.
- Visual: quiet comparison matrix.
- Safe terms only; no replacement claims.

### 24. Review Automation Itself

- Message: the same system can generate screenshots, GIFs, HTML, PPTX, and
  evidence artifacts from current specs.
- Visual: pipeline diagram:
  `spec discovery -> action scenarios -> live capture -> evidence graph ->
  PPT/HTML/catalog`.
- Mention: developer-only root under `../ReviewAutomationWorkspace/`.

### 25. Roadmap / What Is Intentionally Blocked

- Message: blocked evidence is a trust feature.
- Visual: compact status list:
  Spine/NIKKE render guard, VSeeFace capture black-frame fallback, Sound Editor
  action wiring, long-project NLE claim gate.

### 26. Closing

- Message: TigerCapture is becoming a local, automatable creator studio with
  real editor evidence behind every public claim.
- Visual: strongest current editor capture or multi-monitor composition.

## Summary Mode Scenario

Summary mode should not be a raw QA report. It should be a short catalog story:

1. Cover: real editor in catalog frame.
2. Product thesis: local-first creator studio.
3. Live edit proof: Viewer + Timeline + Media Pool with real media.
4. AI/action proof: AI Command + action-backed edit state.
5. Workbench proof: color/node/audio feature contact sheet.
6. Actor/3D/VTuber proof: only evidence-ready items, with blocked notes hidden
   from the visual but recorded in report metadata.
7. Export/review proof: evidence graph and deck modes.
8. Closing: multi-monitor studio or product catalog hero.

## Evidence-Full Mode Scenario

Evidence-full mode can be less beautiful and more complete, but it must still
avoid useless blank slides.

Unlike summary/detailed catalog slides, evidence-full may contain internal QA
metrics, report rows, action counts, and file paths. Those values must not leak
back into product-catalog pages.

Appendix sections:

- Spec discovery report.
- Action registry catalog summary.
- Sample media manifest.
- Feature action scenarios and executed actions.
- Live editor screenshot paths.
- GIF/short MP4 evidence.
- QA dashboard rows.
- Export parity rows.
- Localization/font checks.
- Actor compatibility and render QA.
- Blocked/missing evidence table.
- Release-positioning guardrail result.

## Required Capture Families

The detailed deck needs these capture families before it can be considered
good enough:

| Family | Minimum Evidence |
| --- | --- |
| Editor overview | real imported video in Viewer, Timeline, Media Pool. |
| Timeline edit | split/cut/speed/filter/transition visible. |
| Presets | hover preview and drag/drop guide visible. |
| AI | action plan or AI Command dock visible with timeline context. |
| Color | wheels/sliders/scopes visible with real footage. |
| Node | connected graph plus selected node controls. |
| Audio | waveform/spectrum/mixer/Sound Editor visible. |
| Typography | text on canvas plus keyframes/controls. |
| Live2D | actor visible plus actor lane/controls. |
| Spine | only known-good renderer evidence; otherwise appendix blocked state. |
| AR/PBR | Poly Haven camera scene from `E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene`; do not use motorcycle debug evidence. |
| VTuber | Trump source tracking + Milica VRM mapping + Program Output separation. |
| Multi-monitor | real captures mapped into the triple-monitor template. |
| Export/evidence | render queue, parity, evidence graph, blocked states. |

## Implementation Sequence For Review Automation

1. Re-run spec discovery and action registry probe.
2. Verify review sample media from:

```text
C:\Users\artmouse\Videos\TigerCapture\YouTube Imports
```

3. Reject synthetic/test-pattern media unless explicitly internal.
4. Build a scenario manifest for each slide family.
5. Run action-backed editor setup for the feature.
6. Use review-only window choreography for popouts and multi-monitor staging.
7. Capture still PNG and optional GIF/MP4 evidence.
8. Validate screenshot relevance:
   no empty editor, real media visible, feature-specific UI visible.
9. Generate summary/detailed/evidence-full decks from the same evidence graph.
10. Render deck PNGs for phone review.

## Current Blockers And Notes

- `README.md` contains mojibake in the Korean paragraph. Do not copy that text
  into product-facing slides.
- The existing review workspace still contains older assets such as
  `editor_empty.png`; public deck generation must reject those.
- The current action registry has broad coverage, but some important visual
  surfaces still need review-only open/stage aliases.
- Bicycle model asset is missing from the searched local evidence paths.
- VSeeFace can be degraded or black in this remote/GPU environment; the deck
  should show internal VRM fallback honestly.
- Spine/NIKKE pages must stay guarded until visual evidence is correct.

## Speaker Flow

Use this talk track:

```text
TigerCapture starts as a recorder, but the product story is bigger:
it turns capture into an editable local production session.

The first proof is the editor itself: real media, real cuts, real effects,
not a landing-page mockup.

Then we show the workflow depth: AI command plans, timeline operations,
drag presets, color, nodes, sound, typography, actors, 3D, and VTuber mapping.

The important thing is trust. Every feature page is backed by an automated
scenario and a captured editor state. If something is not ready, the deck says
so instead of faking it.

That is why the review automation matters: it is not just marketing output.
It is a living evidence system for a changing product.
```
