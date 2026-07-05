# MMD TODO

Date: 2026-07-03

## Current Release Posture

- Do not force new MMD feature work just to expand scope. The temporary MMD
  player, editor actor flow, ProjectPlayer composition, and export overlay path
  are implemented enough for parity and real-project validation.
- Remaining high-value work is native MMD/Bullet comparison when reference
  captures are available. Synthetic single-actor, multi-actor, segment timing,
  render-queue, and long-project export QA now exists, but it is still not a
  native-MMD parity claim.
- The current local QA corpus and visual contact-sheet runner are implementation
  evidence, not a native-MMD parity claim.
- Per-model collision, constraint, material, or motion exceptions should be
  handled when a real model breaks instead of adding speculative branches.
- SDEF visual validation now has a real SDEF-weighted PMX candidate:
  `tda_onepiece_sdef_validation` from the external local bundle at
  `E:/ClaudeCodeApp/mmd`. It has 4,602 SDEF vertices and intentionally triggers
  the CPU fallback path.

## Productization Gate

MMD reaches product level when a user can place PMX/PMD + VMD on the editor
timeline, preview it, composite it over video, and export it without the feature
feeling like a debug tool. Keep this as a release gate, not a mandate to add
speculative scope before real breakage appears.

- [ ] Compatibility stabilization
  - PMX/PMD and VMD loading must fail gracefully on real-world files.
  - VMD bone, morph, camera, and light motions need native-MMD comparison.
  - IK, foot locking, append/inherit, and bone-name mismatch behavior need
    broader real-model coverage.
  - SDEF has real-model text and visual QA coverage through
    `tda_onepiece_sdef_validation`.
  - PyBullet/native Bullet behavior needs parity tuning on real cloth, hair,
    skirt, and accessory sequences.
- [ ] MMD render-order and material fidelity
  - Opaque, alpha-cutout, transparent hair/lace, face detail, eye, brow, lash,
    mouth, and accessory passes need regression coverage by material bucket.
  - Toon ramp, sphere/matcap, emissive, bloom, contact shadow, and self-shadow
    behavior should be checked against native MMD captures.
  - Face, eye, brow, lash, and mouth detail layers should avoid inappropriate
    outlines unless a model-specific material policy explicitly allows them.
- [ ] Video-composite and export parity
  - Preview and export must match for MMD alpha, premultiplied blending,
    MMD-only bloom, self-shadow/contact-shadow, and FFmpeg overlay output.
  - Shadow/bloom must stay isolated to the MMD layer so source video grading and
    compositing are not contaminated.
  - Real timeline QA must include long clips, trimmed clips, offset source time,
    batch export, render queue export, and multiple simultaneous MMD actors.
- [ ] Performance release budget
  - GPU skinning should remain the default fast path.
  - Pose cache, VBO/texture/bone-matrix caches, adaptive IK iteration counts,
    physics cadence, and GPU/CPU fallback diagnostics must remain visible.
  - Heavy model preview should degrade predictably instead of turning into
    slow-motion playback without explanation.
- [ ] Editor UX readiness
  - PMX/PMD stay visible as MMD Actor media; VMD stays managed inside the MMD
    Actor Editor motion library to avoid Media Pool confusion.
  - Media Pool right-click exposes a 3D/MMD import route that auto-routes
    `.fbx/.glb/.gltf` to AR/PBR 3D, `.vrm` to Avatar Target, and
    `.pmx/.pmd/.pbx.json` to MMD Actor media while still excluding `.vmd`.
  - Dragging an MMD actor creates a timeline row; double-click opens the MMD
    Actor Editor; same-folder VMD discovery and external VMD add remain clear.
  - Physics, lighting, toon/material, bloom, playback, and camera/view settings
    need model-level preset persistence.
- [ ] Automation and MCP readiness
  - Maintain `mmd.*` actions for actor add/delete/duplicate, track move/trim,
    motion list/add/apply, settings apply, diagnostics, editor open, QA corpus
    diagnostics, visual contact-sheet QA, editor video-composite/export smoke
    QA, multi-actor timeline/export smoke QA, segment trim/speed export timing
    QA, render-queue wiring QA, render-queue MP4 export QA, long-project export
    QA, actor workflow QA, preview capture, and render-test workflows.
  - QA and automation should use the same actions as the UI so regressions are
    caught without manual-only paths.
- [ ] QA corpus and failure handling
  - Keep a corpus with short skirts, long hair, transparent bangs/lace, metal,
    stockings, wings/accessories, separated face parts, heavy physics, and
    camera VMDs.
  - The local manifest is `local_resources/mmd/qa_corpus_manifest.json`; it
    currently tracks 9 passing entries and one blocked entry for the incomplete
    Vivian bundle.
  - Text diagnostics are run with `tools/mmd_qa_corpus.py`; visual evidence is
    run with `tools/mmd_qa_visual_corpus.py` and writes
    `debugCapture/mmd_player/qa_corpus_visual/mmd_qa_visual_contact_sheet.png`.
  - Editor video-composite/export smoke QA is run with
    `tools/qa_mmd_editor_composite.py`; it verifies MMD preview alpha, MMD
    alpha MOV pre-render, final MP4 overlay, and outside-region contamination
    metrics on a synthetic source video.
  - Multi-actor timeline/export smoke QA is run with
    `tools/qa_mmd_multi_actor_timeline.py`; it verifies staggered MMD actor
    start/end ranges, motion offset, overlap frames, alpha MOV pre-render, and
    final MP4 timing against the expected `[0, 1, 2, 1, 0]` active-count path.
  - Segment timing QA is run with `tools/qa_mmd_segment_timing.py`; it verifies
    trimmed source starts, skipped source gaps, and 2x speed segments against
    the expected `[0, 1, 0, 1, 1, 0]` MMD active-count path and confirms a
    gap-only actor does not leak into output.
  - Render-queue wiring QA is run with `tools/qa_mmd_render_queue_wiring.py`;
    it verifies the batch/render-queue export factory forwards trimmed/speed
    segments, MMD tracks, and MMD pre-rendered alpha overlays into
    `VideoExportThread`.
  - Render-queue MP4 export QA is run with `tools/qa_mmd_render_queue_export.py`;
    it runs the captured batch/render-queue export factory with the real
    exporter, writes baseline/MMD MP4 outputs, and compares two simultaneous
    MMD actor regions against a preview overlay sample.
  - Long-project export QA is run with `tools/qa_mmd_long_project_export.py`;
    it exports a 10s synthetic project through the real render-queue factory,
    preserves five trimmed/speed segments, uses two simultaneous MMD actors,
    and samples the final MP4 against preview overlays.
  - Actor workflow QA is run with `tools/qa_mmd_actor_workflow.py`; it verifies
    add actor, add external VMD to the motion library, apply motion, settings
    persistence, move/trim/duplicate/delete, destructive confirmation, summary,
    diagnostics, and player sync through registered actions.
  - Every release candidate needs screenshot/text diagnostics for material
    order, motion, physics, alpha, self-shadow, bloom, and export alpha health.
  - Missing textures, missing toon/sphere maps, VMD bone mismatch, physics
    backend failure, encoding issues, and too-heavy models need user-readable
    warnings and safe fallbacks.

## Next After Physics

- Editor track integration
  - Done: track schema persists model, motion, view, toon render, lighting, bloom, IK, physics, GPU skinning, GPU morph slots, physics cadence, and physics smoothing.
  - Done: ProjectPlayer uses GPU morph slots and decimated/smoothed physics from track playback settings.
  - Note: default physics smoothing response is intentionally high (`0.88`) so cloth/hair do not feel stiff.
  - Done: Media Pool exposes PMX/PMD as MMD actors; VMD is hidden from the general pool and managed inside the MMD Actor Editor.
  - Done: Media Pool right-click 3D/MMD import auto-routes FBX/GLB/GLTF, VRM, and PMX/PMD/PBX packages through their existing asset classifiers while skipping VMD motion files.
  - Done: dragging an MMD model creates a visible MMD actor timeline row; double-clicking the row opens the MMD Actor Editor.
  - Done: MMD actor rows support selection sync, motion-drop feedback, context menu edit/change-motion/physics/duplicate/delete operations, and timeline move/trim.
  - Done: MMD Actor Editor lists same-folder VMD motions, supports adding external VMD files, and applies playback, lighting, physics, and material settings back to the track.
  - Done: automation/MCP actions expose MMD summary, actor add/delete/duplicate, track move/trim, motion list/add/apply, settings apply, and editor open commands.
  - Done: `mmd.motion.add` exposes the external VMD-add flow used by the MMD Actor Editor motion library.
  - Done: ownerless automation/MCP actions expose `mmd.qa.run`, `mmd.qa.visual_run`, `mmd.qa.composite_run`, `mmd.qa.timeline_run`, `mmd.qa.segment_run`, `mmd.qa.render_queue_run`, `mmd.qa.render_queue_export_run`, `mmd.qa.long_project_run`, and `mmd.qa.workflow_run`; all are non-mutating QA actions for text corpus diagnostics, offscreen OpenGL contact-sheet capture, editor video-composite/export smoke coverage, multi-actor timeline/export smoke coverage, segment trim/speed export timing coverage, render-queue wiring coverage, render-queue MP4 export coverage, long-project export coverage, and actor workflow coverage.
  - Done: `mmd.diagnostics` reports active track state, playback/render settings, and material bucket rows from ProjectPlayer.
  - Done: missing texture diagnostics report exact material rows and paths through `missing_texture_rows` and `missing_texture_paths`.
  - Done: single-file video export pre-renders MMD actors on the GUI thread to a full-frame alpha MOV and overlays it through FFmpeg. The offscreen path now restores the export FBO after internal shadow/layer/bloom passes, so real model pixels survive the nested FBO render.
  - Done: batch/export-queue jobs use the same MMD pre-render path before starting the worker thread.
  - Done: long-project render-queue export QA covers a 10s source, two MMD
    actors, five trimmed/speed segments, preview-overlay samples, MMD alpha
    pre-render, and final MP4 output.
  - Cutoff: do not add more local MMD export QA unless a user-provided project,
    model, or render output exposes a concrete failure.

- Transparent material order
  - Done: material draw packets expose named class/bucket diagnostics, draw sort keys, alpha/depth/shadow state, and transparent row summaries.
  - Done: per-material UV alpha sampling promotes real local hair/face alpha gradients to the transparent pass without letting tiny whole-texture antialias alpha make front bangs disappear.
  - Done: transparent front/internal hair draws after face detail layers, so real bang alpha gradients tint eyes/brows instead of being overwritten by them.
  - Done: MMD QA reports expose `alpha_policy`, including UV blend material count and transparent front-hair count for remote/text-first review.
  - Done: near-opaque hair textures, such as ZZZ `前髪/前髮/前发` alpha maps with only soft anti-aliased alpha, stay in the opaque/depth-write pass instead of being treated as transparent overlays.
  - Done: ZZZ-style face detail planes for eye, brow, lash, mouth, teeth, and eye-shadow materials suppress shader outlines; those details already carry texture line art.
  - Done: ZZZ-style eye layers use semantic transparent ordering (`白目`/eye shadow before iris, highlight/lashes after) so `目影` does not haze the iris.
  - Done: ZZZ-style `目影` alpha is softened and `目光` is shifted toward lower-alpha emissive highlights so eyes read less like cloudy glass.
  - Done: face surface outlines are softened to a warm skin-tone edge instead of black, hair outlines use texture-derived softer color plus reduced width, and hair-accessory/head-ornament plus internal/bright head-hair outlines are suppressed so ZZZ-style ears, bangs, and headpieces do not create black bands.
  - Done: model-specific regression profile/capture for ZZZ Alice Sea of Thyme checks front hair opacity, hair overlay transparency, eye-layer order, outline suppression, and emissive eye highlight state.
  - Done: model-specific regression profile/capture for Cantarella + Wavefile checks motion curve coverage, active bones/IK, and cloth/hair physics rotation probe health.
  - Cutoff: review depth write and alpha cutoff decisions only when a concrete
    model fails; do not add speculative material branches.

- Performance diagnostics
  - Done: temporary MMD player diagnostics now report refresh ms, estimated FPS, pose ms, render-item build ms, pose cache size, adaptive IK iteration count, GPU/CPU mode, and SDEF CPU fallback reason.
  - Done: OpenGL MMD preview renderer reports VBO bind, hit, miss, transient upload, byte, and eviction counters into render-item diagnostics.
  - Done: compact OpenGL MMD debug overlay is available off by default; set `TIGERCAPTURE_MMD_DEBUG_OVERLAY=1` or call `set_mmd_debug_overlay_enabled(True)` to show Perf/VBO state.

- Compatibility backlog
  - Done: optional PyBullet backend can be selected from the temporary player and MMD Actor Editor; it creates PMX sphere/box/capsule collision bodies, static anchor bodies, collision group/mask filters, MMD Y-axis capsule shape frames, body-local point constraints, PMX joint-local linear/angular limit and spring approximations, and exposes backend/body/shape/constraint/correction diagnostics.
  - Done: PyBullet rigid-body orientation feedback is blended back into secondary bone rotation hints, so cloth/hair bodies are no longer translation-only in the Bullet path.
  - Done: physics body/joint index `0` is preserved instead of being coerced to `-1`; Cantarella + Wavefile now creates all 574 PMX joint constraints in the PyBullet smoke capture.
  - Done: PyBullet solver response is now explicit: deterministic overlapping pairs, model-scaled solver iterations, fixed timestep, contact/joint/friction ERP, and PMX spring/mass-based constraint max force diagnostics.
  - Done: PyBullet collision diagnostics expose sphere/box/capsule counts and capsule-axis correction count; Cantarella + Wavefile reports 3 spheres, 223 boxes, 189 capsules, and 189 capsule axis fixes.
  - Blocked: full native-MMD Bullet parity for per-model collision/constraint
    behavior requires native MMD/Bullet reference captures.
  - Done: lightweight spring physics now emits secondary bone rotation hints so skirt/hair bodies do not only translate.
  - Done: MMD QA reports expose `physics_policy`, including synthetic spring probe translation/rotation counts so stiff cloth/hair regressions are visible without screenshots.
  - Done: ZZZ Alice regression profile now checks physics secondary rotation health (`physrot`/`rotdeg`) in addition to face/hair material order.
  - Note: secondary rotation hints are currently limited to `0.12` of the first pass so dress/hair do not over-flare.
  - Note: spring target response defaults to `0.60`, giving cloth/hair a visible follow-through delay instead of snapping to the target.
  - Done: temporary MMD player exposes Cloth/Hair and Follow sliders; track schema persists the same values.
  - Blocked: compare PyBullet joint/orientation feedback against native
    MMD/Bullet only when real cloth/hair reference sequences are available.
  - Done: SDEF CPU deformation is covered by synthetic tests, and render/track QA now reports `sdef_cpu_skinning_required`/`sdefcpu` when GPU skinning falls back.
  - Done: real SDEF-weighted PMX validation is covered by `tda_onepiece_sdef_validation`; text QA reports 4,602 SDEF vertices and visual QA renders with `gpu=False` as expected for SDEF CPU fallback.
  - Done: VMD Bezier interpolation now uses stricter curve inversion and QA exposes `motion_policy`/`vmdcurv` so nonlinear motion curves are visible in text reports.
  - Blocked: compare curve timing against native MMD on full-size real bone and
    camera motions only when native reference captures are available.
  - Cutoff: foot IK and PMX append/inherit get more work only for a concrete
    failing model-motion pair.

- Render polish backlog
  - Done: PMX self-shadow cast/receive flags are split into `casts_self_shadow` and `receives_self_shadow`, and transparent/face-detail layers are kept out of the self-shadow map.
  - Blocked: compare self-shadow visual parity against native MMD on full
    motions only when reference captures are available.
  - Done: material-specific toon branches exist for eye, lip, stocking, metal,
    hair, skin, emissive, and transparent accessories.
  - Done: bloom/emissive masking per MMD layer for editor composition safety.
  - Done: screen/display surfaces such as `屏幕` are classified as emissive, and eye-highlight materials such as `目光` keep eye shading while contributing a weak bloom mask.
  - Cutoff: harden offscreen OpenGL MMD export further only when a target
    environment reports a concrete failure; Windows desktop QPA has been
    smoke-tested with Cantarella PMX + Wavefile VMD alpha output.

## Stop Line

- Local implementation and synthetic QA coverage are complete for the current
  MMD scope.
- Do not create new MMD tasks just because the backlog can be expanded.
- Reopen MMD work only for user-provided failing assets/projects or native
  MMD/Bullet reference captures.
