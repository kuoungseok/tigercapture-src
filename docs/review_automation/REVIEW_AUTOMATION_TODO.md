# Review Automation TODO

Last updated: 2026-07-08

## Immediate Organization

- [x] Create `docs/review_automation/` as the review automation rule hub.
- [x] Separate catalog PPT design rules from runtime editor UI-renewal rules.
- [x] Record that review automation is product promotion, not QA/status output.
- [x] Record laptop and multi-monitor templates as product-story devices.
- [x] Move available laptop/device reference images into a durable source
  location.
- [x] Write the current product-catalog PT scenario after re-reading current
  spec and review automation rules.
- [x] Restore the selected canonical multi-monitor template and screen-map JSON
  into the durable template source location.
- [ ] Add a machine-readable template manifest if the number of templates grows.

## Before Rebuilding PPT/HTML

- [x] P0: Restore the full-catalog build gate so missing strict feature captures
  cannot silently become repeated generic placeholder slides. If a feature page
  is pending, either stop the build or create a page-specific pending marker
  that names the exact feature and missing capture. Never allow three or more
  catalog slides to show the same generic `RECAPTURE REQUIRED` laptop/iPad
  image.
- [x] P0: Enforce the device-screen source rule in
  `tools/build_full_product_catalog_decks.py`: laptop and monitor screens must
  receive full editor/window captures only. Small panel crops, media-pool crops,
  timeline strips, detail screenshots, and contact sheets may appear only in
  iPad/detail frames or supporting monitor panes, never as the main laptop
  screen.
- [x] P0: Enforce the Color Grading iPad/detail contract in
  `tools/build_full_product_catalog_decks.py`: the iPad source must be a
  controls-only color detail capture, not a full editor/viewer/timeline/media
  pool screenshot.
- [x] P0: Disable cross-feature capture normalization. The old
  `tools/prepare_full_product_catalog_captures.py` path could copy Live2D into
  MMD, cut/edit into transitions, node/color into unrelated details, and
  debugCapture PPT examples into final catalog sources. It now audits strict
  captures only and must not stage substitutes.
- [x] P0: Remove automatic laptop-to-iPad duplication from the full catalog
  builder. If a page does not have a feature-specific iPad/detail source, it
  must render as laptop-only instead of showing the same screen twice.
- [x] P0: Add semantic capture contract gates for multi-monitor, PPT Maker
  detail, effect/transition/typography/keyframe details, node details, Live2D,
  and MMD. Image existence and nonblack pixels are no longer enough for those
  pages.
- [x] P0: Add pixel-level semantic visual gates so black screens, nearly blank
  panels, and thin meaningless PPT/timeline fragments fail even when a sidecar
  contract exists.
- [x] P0: Add a color-grading laptop Viewer guard. The Color Grading page now
  validates the actual Viewer sub-region, not the wider workbench area, and its
  compare contract must point to a successful source report proving
  `viewer_frame_visible`, `color_dock_viewer_reforced`, and
  `viewer_compare_split`. A black Viewer with active color controls is invalid.
- [x] P0: Add bounded adaptive recapture before full-catalog build via
  `tools/retry_full_catalog_page_capture.py`. When strict preflight fails, this
  runner may only rerun same-feature capture scripts or create focused crops
  from same-feature real TigerCapture captures, then write explicit
  `.capture-contract.json` sidecars and rerun preflight. If preflight still
  fails, PPT generation stays blocked.
- [x] 2026-07-08 Detailed review regeneration after Cubase-style Sound Mixer renewal:
  `tools/generate_review_assets.py --deck-mode detailed` now completes against
  `../ReviewAutomationWorkspace/outputs/mixer_cubase_round_1_detailed`, writes
  `TigerCapture_Review_Automation_detailed.pptx`, and passes
  `tools/qa_review_automation.py` with
  `../ReviewAutomationWorkspace/qa/mixer_cubase_round_1_detailed_review_qa.json`.
  `feature_color_audio_vfx_editor_surface.png` is seeded from
  `debugCapture/ui_renewal_sound_editor_cubase_round_1/dock_sound_editor_mixer_action.png`
  and the evidence graph records `audio.track.set_volume`,
  `audio.track.set_pan`, `audio.track.mute`, `audio.track.solo`, and
  `audio.track.set_type`, `audio.track.insert.set`,
  `audio.track.send.set_level`, `audio.track.route_to_bus`,
  `audio.automation.write`, `audio.track.meter.state`,
  `audio.mixer.snapshot.save`, and `audio.mixer.state`. This refresh includes
  renewed custom Mixer pan/fader controls plus peak/clip, insert/send,
  automation R/W, track type, and snapshot evidence.
- [ ] P0: Recapture page 1 multi-environment payloads with distinct semantic
  contracts: center = main video preview/timeline/AI only, left =
  Live2D/VRM/3D workspace without main video preview, right = node graph plus
  sound/audio workspace without main video preview. These contracts must be
  written by the real multi-monitor capture step, not auto-stamped by the retry
  script. Required proof includes monitor_role, real_tigercapture_capture,
  Lamborghini + long multi-track center timeline, left actor/asset/neutral-3D
  support, and right node-dominant audio workbench.
- [ ] P0: Recapture slide 8/9/10 detail sources. The iPad/detail frames must
  show transition controls/preview, rich typography controls with multiple text
  styles, and keyframe/curve/transform controls respectively; timeline-only
  strips are invalid.
- [ ] P0: Recapture Live2D and MMD pages so the actor/character is visible in
  the editor viewer and the iPad/detail frame is the matching Live2D or MMD
  viewer/detail surface.
- [ ] P0: Add/recapture slide 4 `PPT Maker / Timeline-Native Presentation
  Studio` evidence from the real `app/pptgen` / `.tgppt` workflow. The catalog
  must show an actual PPT Maker project with video_actor, typography/text,
  chart/table or action cards, AR/PBR actor material when available, timeline
  clip bars, and export/snapshot/validation context. Do not use a generic
  PowerPoint mockup or stale `debugCapture` screenshot as final evidence.
- [ ] P0: Fix slide 5 `Media Pool And Imports`: the laptop must show the full
  editor with media pool, viewer, workbench, and timeline visible; the iPad may
  show the enlarged media-pool/detail crop. Reject any build where the media
  pool crop is enlarged to fill the laptop screen.
- [ ] P0: Recapture the strict full-catalog evidence batch expected by
  `tools/build_full_product_catalog_decks.py`. The build now intentionally
  fails if these captures are missing or if the editor Viewer region is black.
- [ ] Re-read current specs and this hub.
- [ ] Verify sample media exists under `../ReviewAutomationWorkspace/samples/`.
- [ ] Verify real YouTube Imports-derived clips are available.
- [ ] Clear PPT/review generation caches and reject historical capture roots:
  `fresh_first_slide_capture`, `actual_3d_viewer_capture`, and `debugCapture`.
  Final PPT screen contents must come from the current `fresh_review_recapture`
  batch.
- [x] Verify selected laptop/device template source exists.
- [x] Verify multi-monitor template source and screen-map JSON exist.
- [ ] Verify feature-specific editor action scenarios can create real states.
- [ ] Prefer multi-track editor states in screenshots; avoid single lonely clips
  unless the feature requires an isolated view.
- [ ] Add natural cut/transition/edit-boundary texture to selected screenshots,
  not all screenshots.
- [ ] Reject empty/generic/unrelated editor screenshots.
- [ ] Inspect every real screenshot/GIF and revise each slide title/body/caption
  to match what is actually visible.
- [ ] For slides using Comparison Templates, verify the before/after states,
  canvas labels, divider/layout boundary, and feature delta are clearly visible.
  Reject generic PIP or split-screen shots that do not explain a real feature.
- [ ] Add/verify `.capture-contract.json` sidecars for color/effect/node
  before-after captures. They must record compare mode, non-neutral
  changed_params, visible_delta=true, and preset reference/source when the
  values came from research instead of an implemented preset. The full-catalog
  build now also blocks these captures unless the sidecar links a successful
  source_report or embeds an action log proving `ui.viewer.compare.set` plus
  the relevant feature action (`clip.set_color_grade` for color, node graph/set
  actions for node pages).
- [ ] Add/verify VTuber Studio product capture through `vrm_mtoon_gpu`. Block
  `vrm_mtoon_software`, dotted/point-cloud avatar output, meta thumbnails, and
  AR/PBR/PBR renderer substitutions.
- [ ] Keep QA metrics out of summary/detailed/product catalog modes.
- [ ] Keep 3D catalog scenarios scoped to implemented AR/PBR compositing
  evidence until a new real-capture feature is explicitly added.
- [ ] Add/verify review-only editor actions for AR/PBR same-asset capture:
  load approved asset into the editor AR/PBR track or composite layer, select
  it, scale/pan it until it is large in the video viewer, then capture the
  editor state.
- [ ] Replace raw-frame Viewer patching in review capture scripts with actual
  editor-rendered frame capture. Raw video frames may be used to choose pretty
  timestamps, but not as proof that color/effect/node/actor output rendered.
- [ ] Add Viewer-region validation for every feature capture whose slide claim
  depends on the video preview.
- [ ] Add current timeline visual validation against
  `E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\references\current_editor_timeline_reference_2026-07-06.png`.
  Reject old V1/A1 block tabs, synthetic colored strips, and obsolete thumbnail
  layouts.

## Feature Capture Backlog

- [ ] Cut/edit timeline scenario.
- [ ] PPT Maker / timeline-native presentation scenario using `ppt.*` actions,
  `.tgppt` save, PPTX export, PNG snapshot/contact sheet, and deck validation
  from the same generated project state.
- [ ] Drag-first effect scenario with hovered/selected effect and visible
  applied result.
- [ ] Color grading scenario with `ui.viewer.compare.set(mode=split)` after
  real non-neutral grade changes plus a compare capture sidecar.
- [ ] Node graph scenario with a real node chain and visible before/after or
  split viewer result plus a compare capture sidecar.
- [ ] Comparison template scenario for color/effect/node/audio before-after
  pages, using `COMPARISON_TEMPLATE_RULES.md`.
- [ ] Audio/sound editor scenario.
- [ ] Typography animation scenario.
- [ ] Transition/effects scenario.
- [ ] Live2D/actor scenario with the Live2D character visible in the editor
  video preview plus actor lane/keyframes; a standalone Live2D viewer alone is
  not enough.
- [ ] MMD/character motion scenario with the MMD character visible in the
  editor/composited result plus motion controls or actor lane.
- [ ] 3D/AR/PBR same-asset scenario using the approved plaster statue/bust
  preset for both the editor video viewer and iPad/detail viewer. Do not mix
  this with the camera model or motorcycle debug evidence.
- [ ] VTuber Program Output / Performance Source scenario using the actual
  VTuber Studio layout: Program Output, Source Tracking, Avatar Mapping, and
  Studio Controls. Main laptop/monitor must be the full VTuber Studio work
  screen; the iPad/detail frame must be Program Output only.
- [ ] Multi-monitor composite scenario with distinct current captures for
  left/center/right monitor roles; do not duplicate the center editor payload
  on side monitors.
