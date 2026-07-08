# Full Product Catalog Manifest

Last updated: 2026-07-07

This is the fixed full-version product catalog scenario for TigerCapture review
automation.

Companion presenter narration:

```text
docs/review_automation/FULL_PRODUCT_CATALOG_TALK_TRACK.md
```

Companion page production plan:

```text
docs/review_automation/FULL_PRODUCT_CATALOG_PAGE_PLAN.md
```

Review automation is product promotion and feature explanation. It is not code
review, QA reporting, release readiness reporting, or raw evidence dumping.

Do not generate PPT, PNG, HTML, or GIF output from this manifest until the user
explicitly asks for generation. When the user asks to make the full catalog PPT,
use this 22-slide list as the locked slide contract.

## Fixed Full Version

- Mode name: `full-product-catalog`
- Slide count: 22
- Audience: product catalog / external product introduction
- Language variants: English and Korean can both be generated from this same
  manifest.
- Primary rule: do not add, remove, split, merge, or reorder slides unless the
  user explicitly changes this manifest first.

## Required Build Behavior

Before any full catalog rebuild:

1. Re-read `SPEC.md`, `README.md`, relevant `docs/SPEC_*.md`, and this
   `docs/review_automation/` folder.
2. Clear review/PPT generation caches so stale slide PNGs, old screenshot crops,
   and old PPT renders cannot leak into the new catalog.
3. Use real TigerCapture editor captures from the current approved recapture
   batch for screen contents. Final PPT generation must reject historical
   capture roots such as `fresh_first_slide_capture`, `actual_3d_viewer_capture`,
   and `debugCapture`.
4. Use approved laptop/iPad and multi-monitor templates only as presentation
   frames.
5. Do not use fake/generated editor UI as product evidence.
6. Do not show QA scores, pass/fail rows, raw JSON, file-path dumps, or internal
   release-readiness summaries in product-facing slides.
7. If a current feature capture is missing, fail the deck build or mark the page
   pending. Do not substitute an older screenshot just because it exists.
8. Prefer visually rich real footage from:

```text
C:\Users\artmouse\Videos\TigerCapture\YouTube Imports
```

   Avoid Le Mans / 24 Hours of Le Mans / FIA WEC footage.
9. Color grading, effect, and node before/after captures must include a
   machine-readable capture contract proving non-neutral parameter changes,
   viewer compare mode, and a visible delta. Original-looking neutral output is
   invalid. If preset values are unknown, research real preset values and record
   the source/reference in that contract.
10. VTuber Studio captures must use the VTuber VRM GPU renderer
    `vrm_mtoon_gpu`. Software VRM fallback output is not product evidence,
    especially when it produces dotted/point-cloud avatars.
11. After slide PNGs are rendered, run final visual QA against the finished
    catalog pages. The QA must inspect actual laptop, iPad, and multi-monitor
    screen regions, block blank/flat mapped screens, block duplicated evidence
    screens, and block iPad detail frames that merely repeat the laptop screen.
12. After PPTX export, validate the package before delivery: ZIP integrity,
    required PowerPoint entries, parsable XML, embedded media count, and
    successful `python-pptx` reopen. A deck that is likely to show a PowerPoint
    repair dialog is invalid.

## Fixed Slide List

### 1. Multi-Monitor Studio Overview

Show the studio as a flexible multi-environment editing workspace. Three
monitors are the approved catalog template, but the product claim is broader:
the same project can spread across the screens the creator has, and four or
more monitors can make the workspace even more comfortable.

- Center monitor: video preview, long timeline, and AI command area.
- Left monitor: Live2D/VRM/3D-related windows.
- Right monitor: node and sound workbench.
- Use real captures mapped into the approved multi-monitor template.
- Video preview and video frame viewer appear only on the center monitor.
  Non-video viewers, such as 3D, Live2D, VRM, MMD, node, and audio views, may
  appear on side monitors.
- Each monitor payload must be a fresh, front-facing capture made for that
  monitor role. Do not duplicate the center editor view on the side monitors.

### 2. TigerCapture Studio

Introduce TigerCapture as one local creator studio for capture, editing,
characters, 3D, audio, color, AI command, and export.

### 3. AI-Driven Editing And Automation

Position AI near the front of the deck.

- Main message: AI can drive the editor directly.
- Explain that local AI, Claude, MCP, and Python Action can share the same
  action surface.
- Show natural-language commands executing editor operations.
- Cover cut, filter, speed, track creation/removal, node operations, capture,
  and automated scenarios briefly.
- Do not title the page as Claude-only. Claude is one supported connection;
  the product message is AI-driven editing across local AI, cloud AI, MCP, and
  Python Action.
- Good copy direction: "Local AI and Claude can both control the same editor
  actions."

This page consolidates what used to be AI Command Dock, Claude-connected editor
actions, Local LLM workflow, and Python Action/MCP automation. Keep it to one
page unless the user edits this manifest.

### 4. PPT Maker / Timeline-Native Presentation Studio

Show TigerCapture's PPT Maker as its own production surface, not as an
external PowerPoint mockup.

- Use real `.tgppt` / `app.pptgen` evidence from the current build or recapture
  batch.
- Show a page canvas with real video, typography/text, chart/table, timeline
  clip bars, and AR/PBR actor material where possible.
- Explain that PPT Maker can save `.tgppt`, export PPTX, generate PNG
  snapshots/contact sheets, validate decks, and be controlled through `ppt.*`
  AI/action commands.
- Use actual video stills from YouTube Imports and GPU-captured AR/PBR actor
  posters. Do not use software renderer output as 3D proof.
- Do not repeat a generic laptop/iPad `RECAPTURE REQUIRED` placeholder for this
  page. If the PPT Maker capture is missing, fail the build or mark the page
  pending.

### 5. Media Pool And YouTube Imports

Show several real imported videos in the media pool. The page should feel like a
real editing project, not a test fixture.

### 6. Timeline Editing

Show cut, split, move, multi-track editing, and a visibly long timeline.

- Avoid short, simple test timelines.
- Prefer real mid-timeline edits, adjacent clip boundaries, or markers.
- Not every page needs a transition, but this page must feel like real work.
- The timeline drawing must match the current editor reference:
  `E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\references\current_editor_timeline_reference_2026-07-06.png`.
  Old blocky colored tracks, large V1/A1 tab blocks, and synthetic fallback
  strips are invalid.

### 7. Drag-First Effects

Show effects being selected or dragged from a library/palette into the editing
surface.

- The screenshot must match effects, not a generic editor surface.
- Hover/preview state is useful when available.
- The visible editor state must include a real clip with an applied effect or a
  clear drag/hover target that explains what will happen when dropped.
- The iPad/detail view must explain the selected effect, not show an unrelated
  crop.

### 8. Transitions

Show a transition applied between real clips.

- The clip boundary and transition area must be visible.
- The viewer should show a relevant transition preview or frame state.

### 9. Typography And Title Animation

Show typography as a real feature, not one tiny caption.

- Use large visible title text in the viewer.
- Show at least one secondary text layer or style control.
- Show keyframes or text clips when available.

### 10. Keyframes And Motion

Show position, scale, rotation, or opacity animation.

- The timeline should show key markers or animation controls.
- Use product-facing explanation such as timed opacity or transform changes.

### 11. Color Grading Workspace

Show the redesigned color workspace.

- Include color wheels, curves, before/after, scopes, or standard sliders.
- Use beautiful real footage.
- Avoid generic or mismatched editor screenshots.
- The iPad/detail frame must be a controls-only color detail crop: wheels,
  curves, scopes, tone controls, or sliders. Do not put the video viewer, media
  pool, or timeline inside the iPad on this page.
- Required evidence: manipulate a real color grade, enable the viewer's
  before/after or split comparison state, and capture that state from the
  editor. A raw footage frame, generic color panel, or neutral/original-looking
  grade is not enough.
- Required capture contract: changed grade parameters must be non-neutral and
  the captured viewer must visibly differ from the original. If the preset
  values were not known before capture, record the researched preset source.

### 12. Node Graph Composition

Show the connected node graph and compositing flow.

- Nodes should have real effect names.
- The selected node parameters should be visible.
- The page must explain the node chain, not just show boxes.
- Required evidence: at least one node in the graph must visibly affect the
  viewer through before/after or split comparison.
- Required capture contract: changed node parameters must be non-neutral and
  visible. A connected graph that renders the same as the original is invalid.

### 13. Node Effects Library

Explain available node/effect types.

Recommended node/effect categories:

- Blur
- Glow
- LUT
- Mask
- Keyer
- Noise
- Sharpen
- Distort
- Composite

Use real UI evidence where possible.

Required visual evidence:

- Include one concrete node/effect example with a visible before/after result.
- Prefer Blur, Glow, LUT, or Sharpen unless another implemented node produces a
  clearer visible difference.
- The page can label the comparison as `Effect Off | Effect On` or
  `Node Off | Node On`.
- Do not ship this page as a text-only effect list.
- The node/effect example must be captured after applying the node in the
  editor. Do not use a standalone library screenshot as the only proof.
- Required capture contract: the effect/node must use non-neutral values and a
  visible before/after delta. Unknown preset values require a recorded
  reference/source.

### 14. Audio Workbench

Show the sound editor inside the workbench.

- Include waveform, spectrum, levels, mixer, or audio clip context.
- The editor should operate on the selected media/audio clip or selected audio
  track.
- It should not look like a separate load-only sound utility.

### 15. EQ, Dynamics And FX Curves

Show audio controls in a detail-emphasis layout.

- The iPad/detail area is appropriate for EQ, dynamics, and FX curves.
- Keep the main laptop/monitor context connected to the editor workflow.

### 16. Live2D And Spine Actor Tracks

Live2D is the main feature on this page. Spine is mentioned briefly.

- Show a visible Live2D model, actor lane, and transform/opacity keyframes.
- The Live2D character must appear in the editor video preview or Program
  Output, not only in a separate Live2D viewer.
- Spine may appear as a small viewer or supporting asset area.
- Do not overclaim Spine/NIKKE quality. If Spine rendering is visibly broken,
  use it only as guarded/supporting evidence or omit the visible Spine detail.

### 17. VRM VTuber Studio

Show VRM/VTuber Studio as its own page.

- Show character, mapping/control UI, and broadcast studio workflow.
- Main laptop/monitor frame: the actual full VTuber Studio work screen
  (`VTuber Studio - Tiger Studio`). It must show the studio UI, not a synthetic
  summary panel.
- iPad/detail frame: Program Output only. Do not put Source Tracking, Avatar
  Mapping, the whole VTuber Studio workspace, or a generic editor crop in the
  iPad on this page.
- The capture must reflect the actual VTuber Studio source layout:
  Program Output on top, Source Tracking in the lower-left, Avatar Mapping in
  the lower-right/center detail region, and Studio Controls nearby.
- If using Trump source mapping context, make it clear that source/tracking is
  separate from final avatar/program output.
- Trump source mapping is upper-body evidence. Avatar Mapping and Program Output
  must show at least the avatar's head, neck, shoulders, and upper torso. A
  face-only/head-only Milica VRM meta thumbnail is invalid for this page.
- Motion/performance source: Trump source footage or mapping context.
- Avatar target: Milica VRM model:

```text
E:\ClaudeCodeApp\GifCam\external\assets\vtuber\booth_milica\Milica1.3free\Milica_v1.3.vrm
```

- Do not let this page disappear in future rebuilds.
- Do not use a synthetic summary image as the only VRM evidence. If the actual
  VTuber Studio capture is unavailable, stop the build and recapture it.
- Required renderer: `vtuber_vrm / vrm_mtoon` with GPU backend
  `vrm_mtoon_gpu`. Do not use `vrm_mtoon_software` or any software fallback
  output for product-catalog evidence. If GPU VRM is unavailable, stop the
  build instead of shipping dotted/point-cloud avatar output.
- Required catalog capture binding:
  `vtuber_studio_editor` -> full VTuber Studio work screen, and
  `vtuber_studio_program_output` -> Program Output crop for the iPad/detail
  frame.

### 18. MMD / Character Motion

Show MMD or character motion workflow.

- Prefer visible character/motion controls, actor lane, or 3D character editor.
- Do not label this as Marmoset.
- The monitor/editor evidence must show the MMD character or motion result. A
  video preview without the MMD character is invalid.
- Do not use the first MMD frame for product evidence. Capture a middle/active
  motion frame so hair, cloth, pose, or timeline motion is readable. The
  capture sidecar must prove `first_frame_used=false`,
  `capture_frame_position=mid_motion` or equivalent middle-frame timing, and
  `mmd_motion_active=true`.

### 19. AR/PBR 3D Composite

Combine 3D asset placement, depth-aware composition, and lighting controls into
one page.

Required layout intent:

- Laptop/monitor: normal TigerCapture editor view with a small 3D viewer or
  visible 3D object inside the editing workflow.
- In the laptop/monitor editor view, zoom or pan the 3D object so it is large
  enough to read immediately in the video viewer. It must not be a tiny object
  at the edge of the frame.
- iPad/detail area: standalone AR/PBR viewer window.
- Same-asset lock: the laptop/monitor video viewer and the iPad/detail AR/PBR
  viewer must use the same named 3D asset and preset. If the iPad shows the
  approved plaster statue/bust, the laptop/monitor video viewer must show that
  same plaster statue/bust composited into the edit. Do not show the camera
  model, a vehicle, or another placeholder in the laptop video viewer.
- Model: use the approved plaster statue/bust model when available.
- The editor capture must be made after loading the approved asset into the
  editor AR/PBR track or composite layer, selecting it, and scaling/panning it
  through actions or saved view state until the object is visibly large.
- Mention lighting, shadows, tone, AO/GI, and depth-aware occlusion.
- Hide visible HDR/cubemap background in 3D viewer captures; environment
  lighting may remain active.
- Do not use motorcycle debug evidence.
- Do not repeat the same 3D model on every 3D-related page.
- If a same-asset editor capture is missing, mark this page pending or fail the
  deck build. Do not silently fall back to an older camera or debug capture.

### 20. Creator Assist

Show creator assistance for clip cleanup, subtitle/caption help, auto polish, or
editing support.

- Keep it product-facing.
- Avoid raw QA/status language.

### 21. Export And Render Queue

Show delivery/output workflow.

- Include export/render queue context and a meaningful timeline/project state.
- Do not mention MRQ or Unreal Bridge in the catalog.
- Do not include QA readiness numbers.
- The timeline must use the current editor track visual style and a real project
  state. Old synthetic timeline strips are not allowed.

### 22. Specification Index Closing Page

Close with a dense product specification index, not another editor screenshot.
This page is the final catalog summary and must use the approved blue-pot bonsai
cutout as a right-side object.

Recommended message:

```text
TigerCapture Studio is one local creator studio for capture, edit, audio, color,
actors, 3D, AI action, automation, and delivery.
```

Visual rules:

- Locked visual contract: ivory catalog page, dense micro-spec text, approved
  blue-pot bonsai on the right, and `pot_contact_only` shadow treatment.
- Use the same clean product-catalog page format as the laptop/multi-monitor
  catalog design: ivory page, dark outer background, thin section label,
  restrained footer, generous negative space.
- Left side: title plus dense micro-spec text. The text may be small and
  catalog-like; it should feel like a specification index, not a QA report.
- Right side: approved blue-pot bonsai cutout.
- The bonsai is a closing-page visual object only. It is not feature
  evidence and must not replace any real editor screenshot on feature pages.
- Do not use a large object drop shadow around the bonsai. Use only a subtle
  floor/contact shadow under the pot base.
- The subtitle/body copy on the left must stay inside the left text area and
  must not overlap the micro-spec columns.
- Reject visible white halos, checkerboard remnants, or background strips
  around the cutout.
- Approved source/cutout paths:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\references\bonsai_blue_pot_spec_page_source_2026-07-07.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\tmp\catalog_spec_closing\bonsai_blue_pot_cutout_v1.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\tmp\catalog_spec_closing\spec_closing_bonsai_blue_pot_page_v1.png
```

## Explicitly Removed From Full Version

The user removed these from the full product catalog scenario. Do not re-add
them unless the user changes this manifest:

- Workspace Philosophy
- Mask & Rotoscope Style Work
- Audio From Video
- Screen Recording & Capture
- Multilingual UI
- Detached Docks & Popout Workflow
- Multi-Monitor Production Layout
- Laptop + iPad Detail Focus
- Preview Parity
- Production-Ready Editing Surface
- What You Can Make

## Page Consolidation Rules

- AI Command Dock, Claude-connected editor actions, Local LLM workflow, and
  Python Action/MCP automation are consolidated into slide 3.
- PPT Maker / Timeline-Native Presentation Studio stays as slide 4. Do not fold
  it into AI, export, or generic editor overview pages.
- Live2D and Spine are consolidated into slide 16, with Live2D as the main
  visual feature and Spine as a small/guarded support mention.
- AR/PBR 3D Asset, Depth-Aware 3D Composite, and 3D Viewer Lighting Controls
  are consolidated into slide 19.
