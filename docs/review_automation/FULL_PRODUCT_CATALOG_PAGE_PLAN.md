# Full Product Catalog Page Production Plan

Last updated: 2026-07-12

This is the page-by-page production plan for the locked 23-slide
`full-product-catalog` deck.

Use this document to decide how each page should be composed before generating
PPT, PNG, HTML, or GIF output. It complements:

```text
docs/review_automation/FULL_PRODUCT_CATALOG_MANIFEST.md
docs/review_automation/FULL_PRODUCT_CATALOG_TALK_TRACK.md
```

## Global Composition Rules

- Use real Tiger Studio editor captures for every screen inside a device frame.
- Do not use fake/generated editor UI as feature evidence.
- Approved presentation frames live under:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates
```

- Preferred real media source:

```text
C:\Users\artmouse\Videos\TigerCapture\YouTube Imports
```

- Prefer visually rich city, night skyline, drone, architecture, driving, HDR,
  and cinematic footage.
- Do not use Le Mans / 24 Hours of Le Mans / FIA WEC footage.
- Do not use test patterns, color bars, empty editors, tiny six-second toy
  timelines, raw QA evidence, JSON dumps, or file-path report pages.
- For pages with laptop/iPad or multi-monitor frames, preserve the template
  hardware exactly. Do not distort, stretch, crop, or perspective-warp the
  laptop, iPad, or monitor body.
- Video preview and video frame viewer appear only on the center monitor in
  multi-monitor pages. Non-video viewers such as 3D, Live2D, VRM, MMD, node,
  and audio viewers may appear on side monitors.
- Hidden GPU/OpenGL widgets may capture black. For review automation, show,
  raise, settle, and capture the target window instead of grabbing a hidden
  viewer.
- Do not patch a raw video frame into an editor screenshot to hide a failed
  capture. A transport fallback may only use the editor's actual rendered
  current frame for the same project state, after applying the requested
  feature.
- For feature pages with before/after claims, execute the feature action first,
  then execute `ui.viewer.compare.set` with `split` or `before`, then capture
  the resulting editor state.
- Color grading, effects, and node before/after captures must also write an
  adjacent `.capture-contract.json` sidecar. That sidecar must record the
  compare mode, changed non-neutral parameters, `visible_delta=true`, and
  whether preset values were researched. If preset values are unknown, research
  real preset values first and record the source/reference in the sidecar.
- The sidecar must also prove action execution, not just declare the result:
  either link a successful `source_report` containing the action `steps`, or
  embed an explicit action log. For color pages the log must include a real
  color action such as `clip.set_color_grade` plus `ui.viewer.compare.set`. For
  node pages the log must include node actions such as `node.graph.set`,
  `node.add`, `node.connect`, or `node.set_param` plus
  `ui.viewer.compare.set`. A missing `source_report` or helper-written contract
  without action proof is invalid.
- A comparison that uses identity/neutral values or looks the same as the
  original is invalid even when the UI says before/after.
- Validate the main Viewer region separately from the full screenshot. A
  nonblank workbench around a black Viewer is still a failed product capture.
- Device detail frames are optional. If a page has no meaningful
  feature-specific detail, use the laptop-only template. Do not duplicate the
  laptop screen into the iPad.
- Every iPad/detail source must have a page-specific purpose and semantic
  capture contract. Timeline strips are invalid for effect, transition,
  typography, keyframe, color, Live2D, MMD, and VTuber detail frames unless the
  slide is specifically about the timeline.
- A semantic contract does not override pixels. Black screens, blank panels,
  nearly empty white panels, and thin meaningless PPT/timeline fragments are
  invalid even if a sidecar exists.
- Do not repair a missing page by copying a screenshot from another feature.
  Live2D cannot stand in for MMD, color/node captures cannot stand in for
  typography or transitions, and a generic editor crop cannot stand in for a
  feature detail.
- Timeline evidence must match the current editor timeline reference:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\references\current_editor_timeline_reference_2026-07-06.png
```

Current timeline captures should show the horizontal time ruler, red playhead
triangles, continuous clip thumbnail strip, subtle dark track rows, and simple
left-side labels such as `Video`. Reject old blocky V1/A1 tab layouts, synthetic
colored strips, or obsolete thumbnail systems.

## Page Details

### 1. Multi-Monitor Studio Overview

**Layout:** Approved front-facing three-monitor catalog template.

```text
multi_monitor_front_facing_catalog_template_v2_tight_clean.png
multi_monitor_front_facing_catalog_template_v2_tight_clean.screen-map.json
```

**Screen composition:**

- Center monitor: full editor with real video preview, long multi-track
  timeline, and AI command area.
- Left monitor: Live2D/VRM/3D-related windows plus a small 3D viewer if a clean
  capture is available.
- Right monitor: node graph plus sound workbench or audio visualizer.

**Capture sources:**

- Center: current editor overview capture from a real project using YouTube
  Imports footage.
- Left: real Live2D/VRM/MMD/3D captures. Do not show a video preview viewer on
  the left monitor.
- Right: real node graph and sound editor captures.

**Build method:**

- Capture each monitor payload separately as front-facing rectangles created
  for that role. The center payload must not be duplicated on the side
  monitors.
- Map each capture to the calibrated screen-map.
- Validate that no gray or white template backing remains around the screens.

**Reject if:**

- Any side monitor contains the main video preview.
- A screen looks pasted on top of the monitor rather than inside it.
- Left monitor contains only one sparse Live2D view with no 3D/character work
  context.
- The slide's copy implies that Tiger Studio requires exactly three monitors.
- Any monitor payload lacks its semantic contract:
  `multi_monitor_left_workspace_v1`, `multi_monitor_center_editor_v1`, or
  `multi_monitor_right_workspace_v1`.
- Center monitor contains node graph/workbench content that belongs on the
  right monitor, or a side monitor duplicates the center editor payload.

### 2. Tiger Studio

**Layout:** Laptop catalog template or clean laptop/iPad template without using
the iPad as the main message.

**Screen composition:**

- Main laptop screen shows the complete editor: media pool, viewer, workbench,
  timeline, and a real project state.
- The timeline should contain more than one meaningful lane.
- The media pool should contain several real clips.

**Capture sources:**

- Real editor overview capture using YouTube Imports footage.
- Prefer city/night/driving footage with a visually appealing preview frame.

**Build method:**

- Use this page as the product thesis page.
- Keep visible copy short and product-facing.
- Speaker notes come from the talk-track document.

**Reject if:**

- The editor is empty.
- The timeline is too short or looks like a QA fixture.
- The page shows raw automation report text.

### 3. AI-Driven Editing And Automation

**Layout:** Laptop/iPad detail layout.

**Screen composition:**

- Laptop: normal editor state with AI command dock visible and at least one
  real edit result visible on the timeline.
- iPad/detail: close view of the AI command area, showing local AI/Claude-style
  command flow without making the title Claude-only.

**Capture sources:**

- Real editor capture after an action sequence such as import, split, speed,
  filter, node change, and screenshot.
- AI command area should be legible enough to show natural-language control.

**Build method:**

- Use Python Action/MCP/editor action surfaces to produce a real changed editor
  state.
- Good action chain:

```text
media.import_to_timeline -> timeline.split -> clip.set_speed
-> clip.set_filter -> node.add/connect or capture.screenshot
```

**Reject if:**

- The page looks like a code console or QA log.
- Claude is presented as the only AI path.
- No visible editor change corresponds to the AI command.

### 4. PPT Maker / Timeline-Native Presentation Studio

**Layout:** Laptop/iPad detail layout or clean laptop-only layout if the PPT
Maker UI needs more room.

**Screen composition:**

- Laptop: actual PPT Maker / `.tgppt` project editing surface, not a generated
  PowerPoint mockup.
- The page canvas should contain a real `video_actor` poster from YouTube
  Imports, text/typography, chart/table or action cards, and an AR/PBR actor
  area when available.
- The lower area should show the PPT Maker timeline/clip bars or page element
  timeline, so the feature reads as timeline-native presentation editing.
- iPad/detail: focused PPT Maker detail such as `ppt.*` actions, export/snapshot
  controls, validation/contact-sheet result, or the selected page element
  inspector. Do not duplicate the whole laptop screen.

**Capture sources:**

- Regenerate the PPT Maker example from the current `app/pptgen` / action
  registry path or capture the actual PPT Maker UI.
- Video source: `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`.
- 3D source: a current GPU/OpenGL AR/PBR capture, such as Nexus RX or another
  approved clean asset. Do not use software renderer output.

**Build method:**

- Prefer the headless `ppt.*` action sequence:

```text
ppt.project.create -> ppt.element.add_shape/text/image/chart
-> ppt.asset.add -> ppt.project.save -> ppt.deck.validate
-> ppt.deck.export_pptx -> ppt.deck.snapshot
```

- Use `app.pptgen.frame_extract.extract_video_still` for the video poster.
- Use `tools/ar_pbr_gpu_window.py` for the 3D poster when an AR/PBR actor is
  shown.
- Save the `.tgppt` project and prove export/snapshot/validation from the same
  generated project state.

**Reject if:**

- The slide shows a generic PowerPoint window, static fake UI, or a repeated
  `RECAPTURE REQUIRED` placeholder.
- The page has no `.tgppt` / PPT Maker surface.
- The 3D poster came from `ar_pbr_scene_smoke.py` or any software-rendered proof.
- A stale `debugCapture` screenshot is used as final catalog evidence instead of
  a fresh/current capture or regenerated PPT Maker project.
- The iPad/detail image is broken, unreadable, duplicated from the laptop, or
  not tied to a concrete PPT Maker feature. If no useful detail exists, use the
  laptop-only layout.

### 5. Media Pool And YouTube Imports

**Layout:** Laptop catalog template.

**Screen composition:**

- Media pool is the hero area.
- Several real imported videos appear in the media list/grid.
- One selected clip appears in the viewer and has a corresponding timeline clip.

**Capture sources:**

- `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`
- Use several attractive clips, not just one repeated source.

**Build method:**

- Import multiple clips into the media pool.
- Select a visually attractive clip.
- Capture the editor with media pool, viewer, and timeline all visible.

**Reject if:**

- Media pool has only one item.
- Clip names or thumbnails make the page look like a test fixture.
- Test-pattern/color-bar footage appears.

### 6. Timeline Editing

**Layout:** Laptop template with timeline emphasized, optionally with an iPad or
detail crop for the timeline.

**Screen composition:**

- Long timeline across the lower part of the editor.
- Multi-track arrangement with video plus at least one companion lane.
- Visible cut, marker, selected clip, speed label, or edit boundary.
- Track visuals must match the current timeline reference: continuous thumbnail
  strip, current dark row styling, simple left label, red playhead markers, and
  the modern ruler.

**Capture sources:**

- Real imported video footage from YouTube Imports.
- Use an attractive frame in the viewer, but the timeline is the main proof.

**Build method:**

```text
media.import_to_timeline
timeline.set_zoom
timeline.split
clip.set_speed
timeline.marker.add
capture.screenshot
```

**Reject if:**

- The timeline is short and simple.
- There is no sign of an actual edit.
- The screenshot repeats the same generic overview used on another page.
- The timeline uses the old blocky colored-track visual system instead of the
  current editor timeline.

### 7. Drag-First Effects

**Layout:** Laptop/iPad detail layout.

**Screen composition:**

- Laptop: effect library or palette open beside the editor.
- iPad/detail: hovered or selected effect tile with preview, target, or payload
  hint.
- Timeline should show an applied effect lane or clip indicator.

**Capture sources:**

- Real effect library UI.
- Real video clip underneath the applied effect.

**Build method:**

```text
media.import_to_timeline
effect.palette.open
effect.hover_or_select
effect.apply_to_clip
ui.viewer.compare.set(mode=split)
capture.screenshot
```

**Reject if:**

- Only anonymous icons appear with no clue what the effect does.
- The screenshot does not show effects being used on media.
- The iPad/detail crop is unrelated to the hovered/selected effect.

### 8. Transitions

**Layout:** Laptop/iPad detail layout.

**Screen composition:**

- Laptop: two adjacent clips with a transition region between them.
- iPad/detail: close-up of the transition handle/strip or transition settings.
- Viewer shows the transition frame or a useful preview frame.

**Capture sources:**

- Two real clips from YouTube Imports, preferably visually different enough that
  the transition makes sense.

**Build method:**

```text
media.import_to_timeline
timeline.split_or_place_adjacent_clips
transition.apply
ui.focus_transition
capture.screenshot
```

**Reject if:**

- Only a transition browser is shown.
- The transition is not visible on the timeline.
- The viewer frame does not relate to the transition.
- The transition evidence uses an obsolete timeline drawing style.
- The iPad/detail frame is just a generic timeline strip. It must show a
  transition handle, transition preview, or transition settings surface.

### 9. Typography And Title Animation

**Layout:** Laptop template with optional iPad detail for title controls.

**Screen composition:**

- Viewer contains large, readable title text over real footage.
- Viewer must show a rich typography stack, not one caption: at least four
  visible text layers are required, including a large headline, secondary line,
  multilingual sample, and smaller caption/body/lower-third text.
- Timeline contains text/title clips and keyframe marks.
- Inspector/title controls show style or animation parameters.

**Capture sources:**

- Real editor typography/title tool state.
- Background footage should be visually clean enough for text readability.

**Build method:**

```text
media.import_to_timeline
text.add
text.set_style
text.set_keyframes
ui.focus_surface(title/text controls)
capture.screenshot
```

**Reject if:**

- Text is only a tiny subtitle.
- The title is unreadable.
- No title clip or control surface is visible.
- The page does not show multiple visible text styles or a richer typography
  composition. The iPad/detail must not be a generic timeline strip.
- The semantic contract does not record the visible text layer count and the
  headline/secondary/multilingual/smaller-text proof flags.

### 10. Keyframes And Motion

**Layout:** Laptop/iPad detail layout.

**Screen composition:**

- Laptop: editor viewer and timeline with animated element selected.
- iPad/detail: transform/opacity keyframe controls or timeline keyframe close-up.
- Good example: opacity, scale, position, or rotation changing over time.

**Capture sources:**

- Text layer, Live2D layer, overlay, or regular clip with animation keys.

**Build method:**

```text
media.import_to_timeline
clip_or_overlay.select
keyframe.set(position/scale/opacity/rotation)
timeline.focus_keyframes
capture.screenshot
```

**Reject if:**

- It looks identical to a normal timeline page.
- No key markers or animation controls are visible.
- The iPad/detail frame is only a track/timeline strip with no transform,
  opacity, curve, or keyframe-control context.

### 11. Color Grading Workspace

**Layout:** Laptop catalog template or color-grading reference composition.
Prefer laptop-only for this page unless the iPad/detail frame adds a meaningful
color-control close-up.

**Screen composition:**

- Laptop/main screen shows the redesigned color grading workspace with real
  footage, visible before/after or split comparison, and timeline context.
- Preferred main evidence is a single full editor/window capture in the
  comparison-workbench layout: Viewer on the left, `Before`/`After` or `Split`
  labels visible, a vertical comparison divider visible, and Color Grading
  controls on the right. The Viewer and controls must come from the same live
  editor state.
- iPad/detail frame is optional. If used, it must show only a meaningful
  color-control close-up: color wheels, curves, scopes, tone controls, and
  sliders. If this close-up does not add information beyond the main
  comparison-workbench capture, omit the iPad and use the laptop-only template.
- The iPad/detail frame must not contain a video viewer, media pool, or
  timeline. It is not a second miniature editor and must never be a smaller
  duplicate of the laptop screen.
- Viewer uses beautiful footage where color changes are obvious.

**Capture sources:**

- City night, HDR/OLED, architecture, or cinematic footage.
- Real color grading UI.
- Research preset values from `COLOR_NODE_COMPARE_PRESETS.md`. Default to
  `cinematic_teal_orange_strong_compare_v1` so the comparison is obvious at
  slide scale.

**Build method:**

```text
media.import_to_timeline
color.workspace.open
color.set_wheels_or_curves(preset=cinematic_teal_orange_strong_compare_v1)
ui.viewer.compare.set(mode=split)
capture.full_editor_with_compare_viewer_and_controls
capture.screenshot
write .capture-contract.json with changed_params, visible_delta=true,
compare_viewer_and_controls_same_frame=true, color_controls_visible=true,
strong_researched_color_preset_applied=true,
cinematic_teal_orange_preset_applied=true, preset_source_urls=[...]
```

**Reject if:**

- The shot is visually dull.
- Color controls are missing.
- The page reuses a generic editor screenshot without a color workspace.
- The viewer is black or does not show a visible before/after result.
- The comparison Viewer and color controls are separate pasted captures instead
  of one full editor/window screenshot from the same state.
- The iPad/detail frame contains the whole editor, viewer, media pool, or
  timeline instead of a controls-only color close-up.
- The iPad/detail frame is present but does not explain color grading better
  than the main laptop capture. In that case, render the page laptop-only.
- Grade parameters are neutral/identity values, or the sidecar contract is
  missing/non-specific.
- The grade uses tiny parameter changes that do not visibly alter the image at
  catalog slide scale.

### 12. Node Graph Composition

**Layout:** Laptop template, with node graph large enough to read.

**Screen composition:**

- Node graph appears as the main evidence.
- Connected nodes with real names are visible.
- Selected node parameters appear beside or below the graph.
- Viewer should show the affected media through the same comparison-workbench
  layout whenever possible: split/before-after Viewer on the left, node graph
  and selected node parameters on the right/workbench, all in one live editor
  capture.

**Capture sources:**

- Real node graph UI.
- Use a visually meaningful node chain such as:

```text
Media In -> White Balance -> Curves -> Glow -> Mask -> Output
Media In -> Blur -> Color Grade -> Composite -> Output
```

**Build method:**

```text
node.graph.set
node.add
node.connect
node.set_param(example=Gaussian Blur, radius_px=24)
ui.viewer.compare.set(mode=split)
capture.full_editor_with_compare_viewer_and_node_controls
capture.screenshot
write .capture-contract.json with changed_params, visible_delta=true,
compare_viewer_and_node_controls_same_frame=true,
node_or_effect_controls_visible=true, strong_blur_effect_applied=true
```

**Reject if:**

- Nodes are isolated boxes with no connections.
- Node names are fake or not implemented.
- No selected node parameters are visible.
- The viewer does not show a result from the node chain.
- The Viewer comparison and node controls are from different screenshots or a
  pasted mock composition.
- Node parameters are neutral/identity values, or the sidecar contract is
  missing/non-specific.
- The blur/effect value is too subtle. Gaussian Blur should normally use about
  24 px and must not be below 18 px for catalog evidence.

### 13. Node Effects Library

**Layout:** Laptop/iPad detail layout.

**Screen composition:**

- Laptop: node/effect library or node graph editor.
- iPad/detail: selected node category or effect list.
- Show useful categories: Blur, Glow, LUT, Mask, Keyer, Noise, Sharpen,
  Distort, Composite.
- Include one concrete node/effect example with a visible before/after result.
  Recommended examples are Blur, Glow, LUT, or Sharpen, whichever has the
  clearest implemented UI and visible image difference.
- The before/after can be shown as `Effect Off | Effect On`,
  `Node Off | Node On`, or an iPad/detail crop of the affected viewer region.
- Preferred laptop/main evidence still uses one full comparison-workbench
  capture where the Viewer comparison and selected node/effect controls are
  visible together.

**Capture sources:**

- Real node/effect palette, node menu, or implemented node browser.
- If the UI cannot show all categories at once, use the best real available
  category view and keep copy honest.
- Real viewer footage with the selected example effect disabled and enabled.

**Build method:**

```text
node.library.open
node.category.select
node.add(example effect=Gaussian Blur)
node.set_param(example effect=Gaussian Blur, radius_px=24)
ui.viewer.compare.set(mode=split)
node.preview_or_param_focus
capture.full_editor_with_compare_viewer_and_node_controls
capture.screenshot
write .capture-contract.json with changed_params, visible_delta=true,
compare_viewer_and_node_controls_same_frame=true,
node_or_effect_controls_visible=true, strong_blur_effect_applied=true
```

**Reject if:**

- The page becomes a text-only list.
- The node categories shown in copy do not exist in the UI.
- No concrete effect result or before/after comparison is visible.
- The laptop view and iPad detail are from unrelated editor states.
- The laptop/main evidence shows only the library or only the comparison result
  rather than the comparison Viewer and node/effect controls together.
- The example effect uses neutral/identity values, or the sidecar contract is
  missing/non-specific.
- The example effect is weaker than a visible Gaussian Blur comparison without a
  documented reason.

### 14. Music Lab / Composition

**Layout:** Laptop/iPad detail layout.

**Screen composition:**

- Laptop: real Tiger Studio Music Lab or composition workbench surface.
- Show prompt composition, genre/mood, BPM/key, arranger sections, chord
  progression, MIDI/note view, preview mix, generated stems, or
  render-to-timeline controls.
- iPad/detail: selected composition detail only, such as section/chord/MIDI
  controls, preview mix, or render controls.
- This page explains composition. It is not an audio correction, EQ, dynamics,
  mixer, or waveform-editing page.

**Capture sources:**

- Real current Music Lab UI from Tiger Studio.
- Use a generated composition state, not an empty panel.
- If the same workflow renders to the timeline, keep the timeline supporting;
  do not make it the only visible proof.

**Build method:**

```text
music.lab.open
music.compose or music.compose_to_timeline
music.section.select
music.preview.play or music.render.preview
music.render_to_timeline
capture.screenshot
write .capture-contract.json with music_lab, composition_surface,
prompt_composition, and non_empty_composition=true
```

**Reject if:**

- The page shows Sound Editor, EQ, dynamics, mixer, or waveform editing instead
  of composition.
- The iPad/detail frame is a full editor duplicate or a timeline-only crop.
- No prompt, sections, chords, notes/MIDI, preview mix, or render controls are
  visible.
- The page is text-only or uses generic audio evidence.

### 15. Audio Workbench

**Layout:** Laptop template with workbench visible.

**Screen composition:**

- Main editor context remains visible.
- Workbench shows sound editor UI tied to selected media/audio track.
- Include waveform, spectrum, level, mixer, or clip context.

**Capture sources:**

- Real sound editor/workbench capture.
- Use a real video or audio track, not an empty audio panel.

**Build method:**

```text
media.import_to_timeline
audio.track.select
audio.workbench.open
audio.clip.set_gain or audio.track.set_mix
capture.screenshot
```

**Reject if:**

- The audio editor appears disconnected from the selected project.
- No waveform/level/audio evidence is visible.

### 16. EQ, Dynamics And FX Curves

**Layout:** Laptop/iPad detail layout.

**Screen composition:**

- Laptop: editor plus audio workbench context.
- iPad/detail: EQ, dynamics, FX curve, or automation curve controls.
- The detail should make audio adjustment visually clear.

**Capture sources:**

- Real sound editor advanced panel or EQ/dynamics/FX curve UI.
- Use actual waveform or level display if possible.

**Build method:**

```text
audio.workbench.open
audio.eq.open
audio.dynamics.open
audio.fx_curve.adjust
capture.screenshot
```

**Reject if:**

- Only generic audio text is visible.
- Detail area has no curve, waveform, level, or control surface.

### 17. Live2D And Spine Actor Tracks

**Layout:** Laptop/iPad detail layout.

**Screen composition:**

- Live2D is the main visual subject.
- Viewer shows a visible Live2D actor over a clean background or real footage.
- Timeline shows actor lane and transform/opacity keys.
- Spine appears only as a small supporting viewer or asset area.

**Capture sources:**

- Real Live2D actor workflow capture.
- Spine sample only if it renders acceptably. Otherwise mention it only as a
  guarded supporting capability.

**Build method:**

```text
media.import_to_timeline
live2d.import
actor.track.add
actor.transform_keyframes.set
spine.viewer.open_optional
capture.screenshot
```

**Reject if:**

- Live2D actor is not visible.
- Spine rendering is visibly broken but presented as a successful feature.
- Background is too visually complex for the actor to read.
- The main laptop/editor view is only raw video with no actor overlay.
- The iPad/detail frame is not a Live2D viewer/detail surface or does not show
  the Live2D actor. A generic editor crop or unrelated timeline strip is
  invalid.

### 18. VRM VTuber Studio

**Layout:** Laptop/iPad detail or laptop-only studio page.

**Screen composition:**

- Main laptop/monitor: show the full actual VTuber Studio work screen
  (`VTuber Studio - Tiger Studio`).
- iPad/detail: show Program Output only. Do not show Source Tracking, Avatar
  Mapping, the full workspace, or a generic editor crop in the iPad.
- Top: Program Output, showing the final avatar/program result.
- Lower-left: Source Tracking, showing Trump/source input as tracking evidence.
- Lower-right or center detail: Avatar Mapping, showing the Milica VRM target
  and mapping controls.
- Trump source mapping is chest-up seated talk evidence. The avatar shown in
  Program Output and Avatar Mapping must use `bust_up` / head-to-mid-chest
  framing: head, neck, shoulders, and upper torso visible, but not a widened
  waist/full-body view. A face-only/head-only Milica VRM meta thumbnail is
  invalid.
- The Program Output avatar must be readable and bottom-anchored. Trim
  transparent avatar padding before scaling, keep the visible avatar large
  enough for the laptop/iPad frame, and align the lower visible edge to the
  Program Output bottom safe line. Do not accept tiny or floating avatar
  evidence.
- Renderer rule: Program Output and Avatar Mapping product evidence must use
  `vtuber_vrm / vrm_mtoon` through the VTuber VRM GPU backend
  `vrm_mtoon_gpu`. Internal fallback is allowed only when it is GPU-backed.
  Do not use `vrm_mtoon_software`, AR/PBR, Marmoset PBR, generic full-gpu debug
  proof PNGs, or dotted/point-cloud software avatar output.
- Side/detail: Studio Controls and status.
- Motion/performance source: Trump source footage or mapping context.
- Avatar target: Milica VRM model.

**Capture sources:**

- Real VRM/VTuber Studio capture.
- Main source: `review_vtuber_studio_full.png` mirrored as
  `vtuber_broadcast_studio_action.png`.
- iPad/detail source: `review_vtuber_studio_program_output.png` mirrored as
  `vtuber_program_output_action.png`.
- Use the current approved source-mapping context when relevant.
- Required VRM model:

```text
E:\ClaudeCodeApp\GifCam\external\assets\vtuber\booth_milica\Milica1.3free\Milica_v1.3.vrm
```

**Build method:**

```text
vtuber.studio.open
vrm.model.load(E:\ClaudeCodeApp\GifCam\external\assets\vtuber\booth_milica\Milica1.3free\Milica_v1.3.vrm)
tracking.source.set(Trump motion/source)
vtuber.renderer.set(vrm_mtoon_gpu)
program.output.focus
capture.screenshot
```

**Reject if:**

- The page only shows source footage and not avatar output.
- VRM character is missing.
- Trump/source mapping is shown as final output rather than source/tracking.
- The avatar is not the Milica VRM model unless the user explicitly changes the
  target model.
- The capture contract reports `vrm_mtoon_software`, missing GPU renderer
  evidence, dotted/point-cloud output, AR/PBR, Marmoset PBR, or generic full-gpu
  proof imagery.
- The slide uses a generated/synthetic VRM summary image instead of the actual
  studio layout capture.

### 19. MMD / Character Motion

**Layout:** Laptop template with character motion UI visible.

**Screen composition:**

- MMD or character viewer/editor is visible.
- Show motion controls, actor lane, lighting, material, or timeline context.
- Keep the page labeled MMD/Character Motion, not Marmoset.
- Never capture MMD at frame 0. Use a middle/active motion frame so the
  character pose, hair, cloth, or timeline movement is visibly alive.

**Capture sources:**

- Real MMD actor workflow capture.
- Use a clean character/background combination.
- Preferred evidence is `cantarella_wavefile_cloth_motion` or another MMD
  profile captured with `--time-ms >= 1000`; frame 0 is invalid even if the
  model is visible.

**Build method:**

```text
mmd.model.load
mmd.motion.load
actor.track.add
mmd.playhead.seek middle_motion_frame
mmd.controls.focus
capture.screenshot
```

**Reject if:**

- No character is visible.
- It looks like a generic 3D page with no motion context.
- The capture uses the first frame or a static idle thumbnail. The sidecar must
  include `first_frame_used=false`, `capture_frame_position=mid_motion` or
  equivalent middle-frame timing, and `mmd_motion_active=true`.
- The monitor/video area does not show the MMD character in the final composed
  result.
- The iPad/detail frame is not an MMD viewer/detail surface. Live2D, AR/PBR, or
  generic editor screenshots must not be substituted for MMD evidence.

### 20. AR/PBR 3D Composite

**Layout:** Laptop/iPad detail layout.

**Screen composition:**

- Laptop/monitor: normal Tiger Studio editor view with a small 3D viewer or
  visible 3D object inside the editing workflow.
- The laptop/monitor's video viewer must show the 3D object large enough to
  read immediately. Zoom/pan the 3D object so it is a clear subject in the
  viewer, not a tiny prop at the edge of the frame.
- iPad/detail: standalone AR/PBR or 3D viewer window. This detail frame must
  show the actual 3D viewer, not the composited Program Output/video result.
- Same-asset lock: the laptop/monitor video viewer and the iPad/detail AR/PBR
  viewer must show the same named 3D asset. If the iPad uses the approved
  plaster statue/bust, the laptop/monitor video viewer must also show that
  plaster statue/bust inside the edit. A camera model, vehicle, or unrelated
  3D object in the laptop video viewer is invalid for this page.
- The standalone viewer should use the approved plaster statue/bust model and
  must write the semantic contract `ar_pbr_standalone_viewer_detail_v1`.

**Capture sources:**

- Approved plaster statue/bust asset when available:

```text
E:\ClaudeCodeApp\3d\Somewhat_Recognizable-668ed982\gltf\converted\somewhat_recognizable_gl_extracted\scene.gltf
```

- Current AR/PBR viewer capture with environment background hidden.
- Current standalone AR/PBR/3D viewer capture for the iPad/detail frame:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\tmp\fresh_review_recapture\ar_pbr_statue_composite\ar_pbr_statue_viewer_detail_action.png
```

- Real editor capture showing the same 3D object inside the video viewer/editing
  context.
- Required matched editor capture path:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\tmp\fresh_review_recapture\ar_pbr_statue_composite\editor_ar_pbr_statue_composite_action.png
```

**Build method:**

```text
ar_pbr.viewer.open
ar_pbr.asset.load(plaster statue/bust)
editor.ar_pbr.asset.add_or_load_to_track(plaster statue/bust)
editor.ar_pbr.track.select
editor.ar_pbr.transform.set(scale=large_visible_subject)
ar_pbr.view.zoom_or_pan_until_object_is_large
ar_pbr.set_lighting_shadow_tone_ao_gi_depth
ar_pbr.hide_environment_background
capture.screenshot
```

**Reject if:**

- The laptop and iPad show the same standalone 3D viewer.
- The laptop does not show normal editor context.
- The iPad/detail frame shows the composited video output, a raw video frame,
  or Program Output instead of the standalone 3D viewer.
- The laptop video viewer and iPad/detail viewer show different 3D assets.
- The laptop viewer contains a tiny or hard-to-see 3D object.
- The model is the old motorcycle debug asset.
- HDR/cubemap background is visible behind the model.
- The page uses a pasted/fake 3D insert instead of a real editor capture after
  loading the asset into the edit.

### 21. Creator Assist

**Layout:** Laptop template or laptop/iPad detail if the assistant panel needs a
close-up.

**Screen composition:**

- Main editor state with creator assist/autopolish/subtitle/cleanup support.
- Show the assistant as helping a real edit, not as a standalone report.
- Timeline or viewer should reflect the result.

**Capture sources:**

- Real Creator Assist panel or workflow.
- Real footage with visible edit result.

**Build method:**

```text
media.import_to_timeline
creator_assist.open
creator_assist.apply_cleanup_or_polish
capture.screenshot
```

**Reject if:**

- It looks like a QA dashboard.
- The assistant panel is unrelated to the visible editor state.

### 22. Export And Render Queue

**Layout:** Laptop template.

**Screen composition:**

- Export or render queue panel is visible.
- Timeline/project context remains visible.
- Output settings are product-facing and clean.
- Timeline/project context must use the current editor timeline visual system,
  not an older fallback strip.

**Capture sources:**

- Real export/render queue UI.
- Use a meaningful project, not an empty timeline.

**Build method:**

```text
media.import_to_timeline
timeline.prepare_multitrack
export.panel.open
render_queue.add
capture.screenshot
```

**Reject if:**

- Internal renderer bridge names are mentioned.
- QA readiness numbers appear.
- Export screen has no project context.
- The timeline visual style does not match the current editor reference.

### 23. Specification Index Closing Page

**Layout:** Clean product-catalog specification index page.

**Page composition:**

- Locked visual contract: ivory catalog page, dense micro-spec text, approved
  blue-pot bonsai on the right, and `pot_contact_only` shadow treatment.
- Use the same visual grammar as the approved catalog templates: ivory paper,
  dark outer background, thin section label, restrained footer, and generous
  negative space.
- Left side: `Tiger Studio / Specification Index` title and dense
  micro-spec text. The text may be intentionally small, like a product catalog
  specification block.
- Right side: approved blue-pot bonsai cutout.
- The bonsai is a closing-page object only. It is not feature evidence and must
  not be used on feature pages as a substitute for real editor captures.
- Use no large drop shadow around the tree. Only a subtle floor/contact shadow
  under the pot base is allowed.
- Reject white halos, checkerboard remnants, or background strips around the
  cutout.

**Capture sources:**

- Approved source image:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\references\bonsai_blue_pot_spec_page_source_2026-07-07.png
```

- Approved cutout and sample render:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\tmp\catalog_spec_closing\bonsai_blue_pot_cutout_v1.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\tmp\catalog_spec_closing\spec_closing_bonsai_blue_pot_page_v1.png
```

- The final PPT build may regenerate the cutout from the approved source if
  needed, but it must keep the same object role and no-drop-shadow rule.

**Build method:**

- Read the latest spec/docs before generation.
- Compose a dense but clean spec index from
  `docs/review_automation/spec_index_groups.json`. Do not recreate the list in
  slide code or free-form prompt copy.
- Keep the spec-index source in sync with the current `SPEC.md`, `TODO.md`, and
  relevant `docs/SPEC_*.md` files before deck generation. Current required axes
  include Capture/Media, Timeline Editing, Effects/Nodes, Typography, Color,
  Audio/Sound Editor, Music Lab, Actors, VTuber Studio, AR/PBR/3D,
  AI/Python Action/MCP, PPT Maker / `.tgppt`, and delivery/export.
- Keep QA/status language out of the visible page.
- Place the bonsai on the right with only a subtle contact shadow under the pot
  base.
- Wrap the left subtitle/body copy inside the left text column. It must not run
  into the central micro-spec columns.

**Reject if:**

- It shows raw report/status/QA content.
- It omits current major spec axes such as PPT Maker / `.tgppt`, Music Lab,
  Sound Editor, Local AI, Python Action, MCP, VTuber Studio, AR/PBR,
  depth-aware compositing, PPTX, or MP4.
- The spec text reads like an implementation checklist instead of product
  capability categories.
- The page mentions internal renderer bridge names, Marmoset, QA readiness numbers, or
  pass/fail status language.
- The tree has a visible white fringe, checkerboard leftovers, or a large
  pasted-object shadow.
- The left subtitle/body copy overlaps the micro-spec columns.
- The page introduces a new feature not covered by real evidence in the deck.
