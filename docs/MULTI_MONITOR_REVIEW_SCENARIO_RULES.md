# Multi-Monitor Review Scenario Rules

Last updated: 2026-07-03

Canonical compact rule:

```text
docs/review_automation/MULTI_MONITOR_RULES.md
```

Use the canonical review automation hub first, then this document for expanded
multi-monitor composition detail.

This is the working agreement for TigerCapture review/PPT/HTML images that
explain a multi-monitor editing environment. Treat this as a scenario and
composition rule, not a fake marketing mockup rule.

## Purpose Rule

The multi-monitor template is a product-catalog device, not a QA dashboard
frame. Use it to show a believable TigerCapture/Tiger Studio work environment:
viewer, timeline, AI, nodes, sound, actors, 3D/AR, and supporting docks spread
across monitors. Do not use it to present code review, QA status, readiness
counts, raw reports, or implementation health as the main story.

## Reference Asset

Use this image as the outer presentation frame:

Template files:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_catalog_template.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_catalog_template.screen-map.json
```

Front-facing replacement candidate for avoiding side-screen paste artifacts:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_front_facing_catalog_template_v1.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_front_facing_catalog_template_v1.screen-map.json
```

Screen replacement regions use template pixel coordinates. The side monitors
are angled and must be perspective-warped into four-point quads:

```text
left_monitor   quad=(586,315) (856,327) (856,546) (586,555)
center_monitor rect=908,344,278,196
right_monitor  quad=(1250,327) (1514,315) (1514,555) (1250,546)
```

Quad order is top-left, top-right, bottom-right, bottom-left. Only the inserted
real capture is perspective-warped; the monitor hardware and catalog template
must not be transformed.

When the front-facing candidate is used, do not perspective-warp the captures.
Use rectangular full-LCD replacement regions instead:

```text
left_monitor   rect=542,327,339,236
center_monitor rect=886,327,333,236
right_monitor  rect=1225,327,348,236
```

Do not mix the angled template and the front-facing screen-map.

## Non-Negotiable Rule

The monitor frame may be staged or generated. The screen content inside the
three monitors must be real TigerCapture captures.

Do not put generated UI, fake panels, placeholder bars, color bars, empty
editors, generic test scenes, explanatory labels, or marketing copy inside the
monitor screens. If a required real capture does not exist, mark the scenario
pending rather than faking it.

## Capture Method

Use the review-only window action layer, not the main Python Action System:

```text
app/review_automation/window_actions.py
review.scenario.run scenario="multi-monitor-capture"
```

The capture mode is show-then-capture. Each slot should briefly show, raise,
settle, and capture the relevant editor window or popout. Do not rely on hidden
window capture for Viewer/GPU/OpenGL/video preview surfaces because those can
capture black.

Physical three-monitor hardware is optional. A single monitor may be reused as
a capture stage:

1. Prepare a real editor project with real imported YouTube Imports media.
2. Stage the left monitor surface, show it, capture it.
3. Stage the center monitor surface, show it, capture it.
4. Stage the right monitor surface, show it, capture it.
5. Map those three real captures into the template screen-map JSON.

When a monitor slot contains more than one window, capture the staged screen
region instead of a single widget. This is especially important for the left and
right monitors, where several real popout windows may be arranged together.

## Video Preview Viewer Exclusivity

Only the main timeline video preview Viewer is center-monitor-only.

- Center monitor: must show the main editor video Viewer or Preview popout with
  the real edit frame, plus timeline and AI when relevant.
- Left/right monitors: must not show the main editor video Viewer, Preview
  popout, or a large imported-video frame from the timeline.
- Left/right monitors may freely show specialized tool viewers when they are
  real UI evidence and match the slide story: Live2D Viewer, MMD Player, AR/PBR
  asset preview, VTuber Studio, Spine editor, 3D object viewer, and similar
  feature-specific windows.

Validation: if a left or right monitor reads as the main edit-video preview,
the multi-monitor catalog image fails and must be regenerated. If it reads as a
specialized feature viewer or tool surface, it is allowed.

## Actual Window And Surface Inventory

This inventory is based on the current codebase, not imagination. Use it to
decide which surfaces can be used immediately and which require connection work
before they can appear in public review material.

### Capture-Ready Review Popouts

These are already represented in the review-only window action layer or follow
the same reparenting popout pattern:

| Surface | Real UI class / owner | Use in multi-monitor image |
| --- | --- | --- |
| Viewer popout | `PreviewPopoutWindow` | Center monitor only, large video preview Viewer area. |
| Timeline popout | `TimelinePopoutWindow` | Center monitor when a detached timeline is needed. |
| Media Pool / left dock | `MediaPoolPopoutWindow` | Left monitor support area, includes media pool and preset sections. |
| Workbench | `WorkbenchPopoutWindow` | Right or left monitor support panel. |
| Color grading | `ColorPopoutWindow` | Right monitor when color/scopes are the story. |
| Node Graph | `NodeGraphPopoutWindow` | Right monitor hero surface. |

### Real Windows Present But Needing Review Capture Wiring

These windows exist, but the review-only window action layer may need explicit
aliases/openers before they can be reliably staged by `multi-monitor-capture`.

| Surface | Real UI class / entry point | Recommended slot |
| --- | --- | --- |
| AI command popout | `_toggle_ai_command_popout`, `QDialog#AICommandPopout` | Center monitor, lower or side band. |
| Sound editor dock window | `SoundEditorDockWindow` from `_open_sound_editor` | Right monitor, below Node Graph. |
| Advanced sound lab | `SoundEditorWindow` from `_open_advanced_sound_lab` | Right monitor, secondary audio detail. |
| Audio mixer/scopes | `AudioMixerPanel`, `AudioScopesPanel` | Right monitor or center lower-right support. |
| Live2D editor | `Live2DEditorWindow` from `_open_live2d_viewer` | Left monitor hero/upper area. |
| Spine editor | `SpineEditorWindow` from `_open_spine_editor` | Left monitor only when rendering evidence is correct. |
| VTuber Studio | `VTuberBroadcastStudioWindow` | Left monitor hero surface when the story is VTuber broadcast or Trump Performance Source mapping. See `docs/VTUBER_TRUMP_SOURCE_MAPPING_CONTEXT.md`. |
| AR/PBR 3D preview | `ArPbrAssetPreviewWindow` | Left monitor AR/PBR camera-scene preview area. Use the Poly Haven camera scene from `E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene`, not motorcycle debug evidence. |
| MMD actor editor | `MMDActorEditorDialog` from `mmd.editor.open` | Left monitor MMD controls area. |
| MMD player | `MMDPlayerWindow` via `tools/mmd_player.py` | Left monitor allowed as specialized MMD evidence; do not imply it is the normal editor window unless integrated. |

### Main-Editor Surfaces That Can Support The Composition

These are not necessarily separate windows, but they are real UI surfaces that
can be captured inside the main editor or a dock popout:

- Actor Library panel.
- Effect, transition, title, and workflow preset panels.
- Workbench `fx`, `audio`, `mask`, `meta`, and actor-related rows.
- Render Queue panel.
- QA Dashboard, only for internal/release evidence pages.
- Media Pool selected item metadata and import/project bin context.

## Detailed First Target Layout

The first serious multi-monitor image should use a staged region capture for
each monitor. The center can be a single editor/window capture; the left and
right should usually be screen-region captures containing multiple arranged
windows.

```text
LEFT MONITOR
  top-left / large      Live2D editor or Live2D actor controls
  top-right / medium    AR/PBR Poly Haven camera scene preview
  bottom-left / medium  MMD Actor Editor with motion/physics/light controls
  bottom-right / narrow Media Pool or Actor Library support strip

CENTER MONITOR
  upper / dominant      Main Viewer with real video frame
  lower / full width    Timeline with real clips, playhead, actor/audio lanes
  lower overlay/side    AI command/chat dock or popout

RIGHT MONITOR
  upper / dominant      Node Graph popout, connected nodes, selected node visible
  lower-left            Sound Editor with waveform/spectrum/EQ/Dynamics/FX tabs
  lower-right           Audio mixer/scopes or levels
  optional side strip   Workbench inspector for the selected node/audio target
```

This layout is intentionally asymmetric:

- Center is for editing and AI.
- Right is for procedural/sound finishing.
- Left is for actor/character/3D production.

The left and right monitors should feel like separate specialist benches, not
copies of the main editor.

## Slot Composition Grid

The template monitor slots are not equally shaped. The center monitor is wider,
while the left and right monitors are closer to square. Use that difference
instead of forcing the same layout everywhere.

### Left Monitor Grid

The left monitor region is roughly square (`716x684`). It should look like a
character/asset production board.

```text
┌──────────────────────────────┬────────────────────┐
│ Live2D editor / actor view    │ AR/PBR 3D preview  │
│ 58-62% width, 52-58% height   │ 38-42% width       │
├──────────────────────────────┼────────────────────┤
│ MMD Actor Editor              │ Actor Library /    │
│ 58-62% width, 38-44% height   │ Media/Preset strip │
└──────────────────────────────┴────────────────────┘
```

Priority:

1. For the general overview hero, AR/PBR or a balanced actor/3D/MMD board
   carries the left monitor.
2. Live2D gets the largest visual cell only on actor-specific feature pages.
3. MMD Actor Editor appears as controls or real visual evidence, not as a
   decorative label.
4. Actor Library or Media Pool is the supporting strip.

First-page 3D viewer lock:

- The first multi-monitor studio hero must include a real 3D viewer/AR-PBR
  preview surface on the left monitor.
- Use the Poly Haven camera scene asset:
  `E:\ClaudeCodeApp\3d\polyhaven_pbr_camera_scene\models\Camera_01\Camera_01_1k.gltf`.
- Hide the visible HDR/cubemap environment background before capture. Keep
  environment lighting if needed, but use the viewer's background toggle so the
  screenshot shows the model on a neutral 3D viewer surface, not an HDRI room.
- A 3D/AR-PBR workbench inspector without an actual 3D viewer or asset preview
  is not sufficient for the first page.

If this becomes too busy, remove the support strip first. Do not let one
Live2D actor/viewer consume the entire left monitor unless the slide is
explicitly the Live2D actor workflow page.

### Center Monitor Grid

The center monitor region is wide (`990x678`). It should look like the main
edit bay.

```text
┌──────────────────────────────────────────────────┐
│ Project chrome / compact toolbar                 │
├──────────────────────────────────────────────────┤
│ Large Viewer                                     │
│ 65-72% width, 52-60% height                      │
│                                                  │
├──────────────────────────────────────┬───────────┤
│ Timeline, full width if possible     │ AI command│
│ clips + playhead + lanes             │ chat/dock │
└──────────────────────────────────────┴───────────┘
```

Priority:

1. Viewer must be large enough to read the real video frame.
2. Timeline must prove editing, not just playback.
3. AI command/chat should be visible but secondary.

First-page media lock:

- The first multi-monitor studio hero must use the Lamborghini YouTube Imports
  video in the center Viewer.
- Do not use macro human eye, face, skin, or body close-up footage on this
  page. Those frames make the catalog hero feel unrelated to editing and
  production.
- If the Lamborghini clip is missing, fail the first-page build and report the
  missing media instead of silently substituting another clip.

Preferred AI placement is lower-right or bottom dock. A floating AI panel is
allowed only if it does not cover the Viewer or make the Timeline unreadable.

### Right Monitor Grid

The right monitor region is also near-square (`782x686`). It should look like a
technical finishing bench.

```text
┌──────────────────────────────────────────────────┐
│ Large Node Graph                                 │
│ connected nodes + selected node + parameter area │
│ 58-68% height                                    │
├────────────────────────────┬─────────────────────┤
│ Sound Editor               │ Audio mixer/scopes  │
│ waveform/spectrum/EQ tabs  │ levels/meters       │
└────────────────────────────┴─────────────────────┘
```

Priority:

1. Node Graph dominates the monitor.
2. Sound Editor is visible enough to read waveform/spectrum/audio tabs.
3. Audio mixer/scopes fill the remaining lower-right space.
4. Workbench inspector can appear only as a thin side strip if it helps explain
   the selected node.

If Node Graph and Sound compete, keep Node Graph larger and let Sound become a
secondary dock. The first read should be "node environment", the second read
should be "sound tools are also open".

## Readiness And Fallback Order

Use the most ambitious real surface that is capture-ready. If a target surface
is not ready, replace it with the next real implemented surface in the same
family and record the skipped target as pending.

### Left Monitor Fallbacks

Preferred:

```text
Live2D editor + AR/PBR Poly Haven camera scene preview + MMD Actor Editor + Actor Library
```

Fallback order:

1. Live2D editor or Live2D actor lane/workbench controls.
2. AR/PBR 3D preview window with the real Poly Haven camera scene asset.
3. MMD Actor Editor.
4. VTuber Studio, only when the page is about broadcast/avatar mapping. For
   Trump-source mapping, use the dedicated VTuber variant instead of cramming it
   into the general actor/3D layout.
5. Media Pool Actor Library / asset browser.

Do not use Spine in the first public composition until its rendering evidence is
visually correct.

### Center Monitor Fallbacks

Preferred:

```text
Main editor capture with large Viewer + Timeline + AI command/chat
```

Fallback order:

1. Main editor with AI command dock visible.
2. Viewer popout plus timeline inside the main editor.
3. Main editor with AI dock collapsed but visible as an icon/command strip.

Do not let the center become only a full-screen Viewer.

### Right Monitor Fallbacks

Preferred:

```text
Node Graph popout + Sound Editor + Audio mixer/scopes
```

Fallback order:

1. Node Graph popout with selected node controls.
2. Workbench FX tab with node graph embedded.
3. Sound Editor dock window or Workbench audio tab.
4. Audio mixer/scopes.
5. Color grading popout if audio is not ready for this pass.

Do not shrink the Node Graph below readability just to fit every tool.

## Implementation Wiring Needed

The layout above requires review-only window action aliases for several real
windows. These are implementation tasks for the review automation layer, not the
main Python Action System.

Required aliases:

```text
review.ui.popout.open surface="ai_command"
review.ui.window.open surface="sound_editor"      target selected audio clip
review.ui.window.open surface="advanced_sound_lab"
review.ui.window.open surface="live2d_editor"
review.ui.window.open surface="ar_pbr_preview"    target selected/imported 3D asset
review.ui.window.open surface="mmd_actor_editor"  target selected MMD track
review.ui.window.open surface="vtuber_studio"
```

Required capture behavior:

- Center monitor can be captured as the main editor or a staged screen region.
- Left monitor should be captured as a staged screen region, because it contains
  multiple real windows.
- Right monitor should be captured as a staged screen region, because it
  combines Node Graph and sound windows.
- Use `show_then_capture` for all GPU/video/3D/Viewer surfaces.
- For 3D/AR-PBR viewer surfaces, the capture setup must turn off visible
  environment background / cubemap display before `show_then_capture`.
- Use widget `grab()` only for simple Qt panels or tests.

Do not add these aliases to `app/actions/registry.py`. They belong only in
`app/review_automation/window_actions.py` or another review-only module.

## Core Story

The image should communicate one clear idea:

TigerCapture can spread an editing job across separate working surfaces, so the
creator can keep the main edit visible while asset browsing, nodes, color,
audio, render, or review panels live on independent screens.

This is not a generic "many monitors are cool" image. It has to show concrete
editor work in progress.

## User-Aligned Preferred Composition

This is the preferred composition agreed with the user. It should replace the
earlier safe "editor command center" default when building the first serious
multi-monitor catalog image.

### Center Monitor: Main Edit And AI

Purpose: make the center monitor feel like the creator's primary working
screen.

Recommended real capture:

- Viewer is large and visually dominant.
- Timeline is visible under the Viewer with real clips, playhead, lanes, and
  active edit context.
- AI command/chat window is present on the center monitor, because text/AI
  editing is one of the product's differentiators.
- Transport controls and edit state remain visible enough to read as an active
  editor, not a still preview.

Avoid:

- Center monitor becoming only a full-screen video preview.
- Timeline being too small to prove editing is happening.
- AI panel covering the Viewer or making the composition unreadable.

### Right Monitor: Node And Sound Workbench

Purpose: show a specialist production environment on a separate monitor.

Recommended real capture:

- Node Graph is large and clearly readable.
- Connected nodes are visible, with at least one selected node and its controls.
- Sound-related surface is also present: Sound Editor, audio mixer, waveform,
  spectrum, EQ, levels, or cleanup panel.
- Color/scopes can share this monitor only if they do not shrink the Node Graph
  too much.

Avoid:

- A tiny decorative node graph that cannot be read.
- Repeating the same generic Workbench inspector for every feature.
- Fake node/audio panels. If the real surface is not capturable yet, mark it
  pending.

### Left Monitor: Character, 3D, And Asset Surfaces

Purpose: show actor/character/3D production surfaces that do not belong on the
main edit monitor.

Recommended real capture:

- Live2D actor window or actor library.
- AR/PBR/3D object preview surface, when real UI evidence
  exists.
- MMD window or MMD actor/tool surface.
- Media Pool, preset browser, actor/effect library, or import/project bin may
  share this monitor if there is room.

Avoid:

- One full-screen Live2D actor/viewer on the general overview hero. That makes
  the left monitor read as a Live2D-only feature page instead of a support bench.
- Fake Live2D, fake MMD, or fake AR/PBR/3D windows.
- Claiming Spine/Live2D/MMD/3D evidence if the real renderer or panel capture is
  not visually correct.

### Remaining Windows

Any supporting windows that are not central to the story should be placed on the
left or right monitors, not the center monitor. The center monitor should stay
focused on Viewer, Timeline, and AI.

Possible supporting surfaces:

- Media Pool
- Actor Library
- Effect/Transition/Title palettes
- Inspector/Workbench details
- Render Queue
- QA/evidence panel, only for release or internal proof pages

## Scenario Variants To Discuss

The default image can be reused, but the inserted screen captures should change
depending on the story.

### Variant A: Full Studio Command Center

Use this for general product overview.

```text
left_monitor   Live2D + 3D/AR-PBR + MMD + asset/preset support
center_monitor Large Viewer + Timeline + AI command/chat
right_monitor  Large Node Graph + Sound Editor/audio mixer/scopes
```

Strength: strongest expression of the product as a multi-surface studio.

Composition note: for this general overview, AR/PBR or a balanced
actor/3D/MMD layout should carry the left monitor. Use Live2D as one real pane
among several unless the whole slide is specifically about actor workflow.

Risk: only acceptable when each inserted surface is a real TigerCapture capture.
If Live2D/3D/MMD/audio evidence is not ready, the affected surface must be
pending or replaced with another real implemented surface.

### Variant B: Node / Color / Audio Studio

Use this for professional workflow or detailed feature pages.

```text
left_monitor   Media Pool + selected source media
center_monitor Viewer + timeline with graded/effected clip
right_monitor  Node Graph + Color scopes or Audio editor popouts
```

Strength: visually proves that tools can live outside the main editor.

Risk: must ensure the right monitor is not fake. Capture actual node/color/audio
surfaces only.

### Variant C: Actor And Overlay Production

Use this for Live2D, Spine, VTuber, 3D object, or overlay pages.

```text
left_monitor   Actor library + asset/preset browser
center_monitor Viewer with actor/overlay visible + actor lane/keyframes
right_monitor  Actor controls, transform/keyframe panel, or Live2D/3D tool dock
```

Strength: explains why separate panels help character/overlay editing.

Risk: actor rendering must be visibly correct. If Live2D/Spine evidence is not
ready, do not use this as a public proof image.

### Variant D: Delivery And Review Bay

Use this for export, render queue, QA, or release-evidence pages.

```text
left_monitor   Media/project context
center_monitor Timeline range selected for export
right_monitor  Render Queue, QA Dashboard, review report, or preview parity panel
```

Strength: useful for internal/release trust material.

Risk: do not let this become a raw QA log screenshot in a catalog page.

## Current Recommendation

Start with the user-aligned Variant A as the first target composition, but gate
each monitor surface by real capture readiness.

Reason:

- It shows the editor as a real studio instead of a single crowded window.
- Center monitor clearly communicates editing plus AI.
- Right monitor makes node/sound work feel large and professional.
- Left monitor gives Live2D, AR/PBR/3D, and MMD their own production space.
- The result matches the user's intended story better than a generic
  MediaPool/Editor/Inspector split.

The first generated multi-monitor catalog image should therefore use:

```text
left_monitor   Live2D + real 3D/AR-PBR viewer + MMD + asset/preset support
center_monitor Large Viewer with Lamborghini clip + Timeline + AI command/chat
right_monitor  Large Node Graph + Sound Editor/audio mixer/scopes
```

If one of those specific surfaces is not real-capture ready, keep the slot real
by using the closest implemented surface and record the missing target as a
pending follow-up. Never synthesize the missing UI.

For the first page, do not downgrade the 3D viewer requirement to only AR/PBR
controls. If the viewer cannot be captured, treat the first page as blocked and
fix the capture path before generating the deck.

## Open Decisions With User

These are the points to align before treating the rule as final:

- On later feature pages, should Live2D, AR/PBR/3D, or MMD be visually dominant?
  The first multi-monitor hero is already locked to include a visible 3D viewer
  on the left monitor.
- On the right monitor, should Node Graph dominate with Sound as a secondary
  dock, or should Node and Sound split the screen evenly?
- On the center monitor, should the AI command/chat be a bottom dock, side dock,
  or floating panel over the Timeline area?
- Should the center monitor show the whole editor chrome or a tighter
  Viewer+Timeline+AI capture?
- Should multi-monitor images appear only in detailed/evidence decks, or also
  in the summary catalog deck?

## Acceptance Checklist

A multi-monitor review image is acceptable only if:

- The outer template matches the dedicated monitor template.
- All three monitor screens are filled using the screen-map JSON.
- Every inserted screen is a real TigerCapture capture.
- The center screen clearly shows a real active edit.
- The left and right screens explain different supporting surfaces.
- The image has no fake UI, no empty editor, no test bars, and no explanatory
  labels inside the monitors.
- The final composition still feels like a product catalog image, not a debug
  report.
