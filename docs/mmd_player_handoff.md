# MMD Player Handoff Spec

Date: 2026-07-03
Workspace: `E:\ClaudeCodeApp\GifCam`
MMD bundle: `E:\ClaudeCodeApp\mmd`

## Goal

The initial standalone MMD player exists, and the editor-facing actor flow is
now implemented. The renderer must continue to use the editor
`OpenGLPreviewWidget` path, not a separate renderer. MMD model assets are not
shipped with the editor.

The current product posture is not to force new MMD features. Local synthetic
QA now covers preview, video composite, multi-actor timing, segment timing,
render queue export, and long-project export. Further MMD work should only be
opened for native MMD/Bullet reference comparison or a concrete failing user
asset/project.

## Current Default

- Model: `local_resources/mmd/model_pool/playable/flashy_girls/wuthering_waves/Cantarella/Cantarella.pmx`
- Motion: `local_resources/mmd/model_pool/motions/validated/wavefile_v2_arora_14.vmd`
- Player entry: `tools/mmd_player.py`
- Screenshot output folder: `debugCapture/mmd_player/`
- Current handoff docs:
  - `docs/MMD_TODO.md`
  - `docs/mmd_player_handoff.md`

## Implemented

- Standalone MMD player window using `OpenGLPreviewWidget`.
- Toon-only rendering. Marmoset option was removed.
- Model pool dropdown, Play/Pause, Stop, open PMX/PMD, open VMD, reset view.
- Mouse drag rotates view, mouse wheel zooms.
- Bloom slider.
- Lighting preset dropdown plus manual lighting sliders:
  - Key Dir
  - Key Height
  - Key intensity
  - Fill
  - Rim
  - Ambient
  - Shadow
- Real elapsed-time playback. Playhead no longer advances by fixed timer interval only, so slow FPS should not become slow-motion playback.
- GPU skinning path for playback when SDEF is not present:
  - Static vertex packet includes bone indices/weights.
  - Bone matrices are uploaded through a float texture.
  - Shadow pass also uses GPU skinning.
- PMX/VMD MVP support:
  - PMX mesh/material/texture/toon/sphere map parsing.
  - VMD bone/morph/camera parsing.
  - VMD Bezier interpolation with nonlinear-curve diagnostics.
  - IK enabled during playback.
  - PMX append/inherit rotation/translation support for D bones such as `足D / ひざD / 足首D`.
  - SDEF CPU path exists.
  - SDEF models keep CPU skinning; render/track diagnostics expose the GPU fallback reason as `sdef_cpu_skinning_required`.
  - Temporary player status/diagnostics report preview refresh ms, estimated FPS, pose ms, render-item build ms, pose cache size, adaptive IK count, GPU/CPU mode, and SDEF fallback.
  - Lightweight spring physics exists.
  - Optional PyBullet backend exists for MMD physics preview. Install with `.\.venv\Scripts\python.exe -m pip install -r requirements-mmd.txt`; this workspace venv has been smoke-tested with pybullet 3.2.7.
  - PyBullet path creates PMX sphere/box/capsule rigid bodies, static anchor bodies, collision group/mask filters, MMD Y-axis capsule shape frames, body-local point constraints, joint-local linear/angular limit and spring approximations, and rigid-body orientation feedback into secondary bone rotations.
  - PyBullet solver response is explicit: deterministic overlapping pairs, model-scaled solver iterations, fixed timestep, contact/joint/friction ERP, and PMX spring/mass-based constraint max force.
  - PyBullet diagnostics expose body/shape/constraint counts plus sphere/box/capsule counts, capsule-axis correction count, joint-frame constraint, solver settings, constraint force, joint limit, spring, and orientation feedback correction counters.
- Toon visual features:
  - Backface outline.
  - Toon ramp darkest-color shadow tint.
  - Soft shadow/self-shadow path.
  - PMX self-shadow cast/receive policy is split per material; transparent face details do not draw into or receive the self-shadow map.
  - Ground/contact shadow.
  - MMD-only bloom compositing.
  - Hemisphere ambient.
  - Skin warm tint/highlight clamp/wrap diffuse.
  - Hair rim/toon highlight retained.
  - Hair angel ring disabled because it looked awkward.
  - Eye highlight, lip specular, stocking/metal sphere-map handling.
- Baseline editor integration:
  - PMX/PMD appear in the Media Pool as MMD actors.
  - VMD is hidden from the general Media Pool and managed through the MMD Actor Editor motion library.
  - Media Pool right-click 3D/MMD import auto-routes FBX/GLB/GLTF to AR/PBR
    3D, VRM to Avatar Target, and PMX/PMD/PBX packages to MMD actors while
    keeping VMD motion files out of the general pool.
  - MMD actor tracks can be placed on the editor timeline as visible actor rows and composited in ProjectPlayer.
  - Double-clicking an MMD actor row opens the MMD Actor Editor.
  - MMD actor rows support selection sync, context menu edit/change-motion/physics/duplicate/delete, VMD drop feedback, and direct move/trim.
  - The Workbench opens the MMD Actor Editor for the selected MMD track.
  - Track data persists motion library, playback, lighting, bloom, physics, and material tuning settings.
  - Automation/MCP actions are registered under `mmd.*` for summary, diagnostics, actor add/delete/duplicate, track move/trim, motion list/add/apply, settings apply, and editor open.
  - `mmd.motion.add` exposes the external VMD-add motion-library flow for automation before `mmd.motion.apply`.
  - Ownerless, non-mutating QA actions `mmd.qa.run`, `mmd.qa.visual_run`, `mmd.qa.composite_run`, `mmd.qa.timeline_run`, `mmd.qa.segment_run`, `mmd.qa.render_queue_run`, `mmd.qa.render_queue_export_run`, `mmd.qa.long_project_run`, and `mmd.qa.workflow_run` run the local MMD corpus diagnostics, visual contact-sheet workflow, editor video-composite/export smoke QA, multi-actor timeline/export smoke QA, segment trim/speed export timing QA, render-queue wiring QA, actual render-queue MP4 export QA, long-project render-queue export QA, and actor action workflow QA for MCP/automation.
  - ProjectPlayer exposes `mmd_diagnostics()` for active track, playback/render state, and material bucket rows.
  - Missing texture diagnostics report exact material rows and paths through `missing_texture_rows` and `missing_texture_paths`.
  - Single-file and batch/render-queue export pre-render MMD actors on the GUI thread using the same MMD OpenGL painter, then overlay the resulting alpha MOV through FFmpeg.
  - The MMD offscreen export path restores the parent export FBO after nested shadow/layer/bloom FBO passes and binds a VAO for offscreen draws.
  - ProjectPlayer/export use an MMD alpha pre-render plus FFmpeg overlay path.
  - Screen/display surfaces such as `屏幕` are classified as emissive, and eye-highlight materials such as `目光` keep eye shading while contributing a weak bloom mask.
  - Near-opaque hair alpha textures stay in the opaque/depth-write pass, which fixes ZZZ-style front bang materials such as `前髪/前髮/前发` becoming faint or disappearing behind face/eye layers.
  - Per-material UV alpha sampling promotes actual local hair/face alpha gradients to the transparent pass while keeping whole-texture antialias alpha in the opaque pass.
  - Transparent front/internal hair draws after face detail layers, so real bang alpha gradients tint eyes/brows instead of being overwritten by them.
  - `tools/mmd_qa_report.py` exposes `alpha_policy` and `physics_policy` plus `uvblend`/`fhairA`/`physrot`/`rotdeg` text columns for remote material-order and cloth/hair stiffness checks.
  - `local_resources/mmd/qa_corpus_manifest.json`, `tools/mmd_qa_corpus.py`, `tools/mmd_qa_visual_corpus.py`, `tools/qa_mmd_editor_composite.py`, `tools/qa_mmd_multi_actor_timeline.py`, `tools/qa_mmd_segment_timing.py`, `tools/qa_mmd_render_queue_wiring.py`, `tools/qa_mmd_render_queue_export.py`, `tools/qa_mmd_long_project_export.py`, and `tools/qa_mmd_actor_workflow.py` provide the current local MMD QA corpus, text diagnostics, offscreen OpenGL visual contact sheet, video-composite/export smoke QA, multi-actor timeline/export smoke QA, segment trim/speed export timing QA, render-queue wiring QA, actual render-queue MP4 export QA, long-project export QA, and actor workflow QA.
  - Eye, brow, lash, mouth, teeth, and eye-shadow face detail planes suppress shader outlines so ZZZ-style texture line art is not doubled by backface outlines.
  - ZZZ-style eye layers use semantic transparent ordering (`白目`/eye shadow before iris, highlight/lashes after) so `目影` does not haze the iris.
  - ZZZ-style `目影` alpha is softened and `目光` is shifted toward lower-alpha emissive highlights so eyes read less like cloudy glass.
  - Face surface outlines are kept but softened to a warm skin-tone edge; hair outlines use texture-derived softer colors and reduced width instead of heavy black lines, while hair-accessory/head-ornament and internal/bright head-hair outlines are suppressed to avoid black bands around ears, bangs, and headpieces.

## Important Current Findings

- `Everybody Left` looked flashy but has mostly static lower-body/leg keys, so it made legs look frozen.
- `wavefile_v2_arora_14.vmd` has active foot IK/lower-body keys and is currently the better default for validating leg motion.
- Cantarella visible lower-body vertices are heavily weighted to D bones. Without PMX append/inherit support, lower body appears stuck even when source leg bones move.
- Playback used to feel like slow video because playhead advanced by fixed `QTimer` interval. It now uses wall-clock delta with a per-tick cap.
- PyBullet joint creation used to drop rigid body index `0` because of a `value or -1` coercion pattern. That is fixed; Cantarella + Wavefile now creates 574 constraints instead of 556.

## Main Files

- `app/mmd/player_window.py`
  - Standalone player UI, playback, mouse view, lighting controls.
- `app/mmd/animation.py`
  - PMX pose evaluation, VMD channels, IK, append/inherit, SDEF/LBS skinning.
- `app/mmd/gpu_preview.py`
  - Converts PMX pose/model into OpenGL render packets and material shader controls.
- `app/opengl_preview.py`
  - Editor OpenGL preview renderer with direct MMD draw path, shader, bloom/shadow passes, GPU skinning bone texture.
- `app/mmd/lighting.py`
  - Toon lighting presets and override resolver.
- `tests/test_mmd_pmx.py`
  - Current MMD regression tests.

## Verification

Current focused suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_mmd_schema.py tests\test_mmd_pmx.py tests\test_mmd_editor_integration.py
```

Latest result:

```text
80 passed
```

Latest MMD QA corpus:

```powershell
.\.venv\Scripts\python.exe tools\mmd_qa_corpus.py
.\.venv\Scripts\python.exe tools\mmd_qa_visual_corpus.py
.\.venv\Scripts\python.exe tools\qa_mmd_editor_composite.py
.\.venv\Scripts\python.exe tools\qa_mmd_multi_actor_timeline.py
.\.venv\Scripts\python.exe tools\qa_mmd_segment_timing.py
.\.venv\Scripts\python.exe tools\qa_mmd_render_queue_wiring.py
.\.venv\Scripts\python.exe tools\qa_mmd_render_queue_export.py
.\.venv\Scripts\python.exe tools\qa_mmd_long_project_export.py
.\.venv\Scripts\python.exe tools\qa_mmd_actor_workflow.py
```

```text
mmd_qa_corpus: ok=True, run_count=9, blocked_count=1
mmd_qa_visual_corpus: ok=True, run_count=9, contact_sheet=debugCapture/mmd_player/qa_corpus_visual/mmd_qa_visual_contact_sheet.png
mmd_editor_composite_qa: ok=True, entry_id=cantarella_wavefile_cloth_motion, alpha_coverage=0.0699, export_inside=42.527, export_outside=1.924
mmd_timeline_qa: ok=True, active_counts=[0, 1, 2, 1, 0], active_diff=38.040, inactive_diff=2.556
mmd_segment_timing_qa: ok=True, active_counts=[0, 1, 0, 1, 1, 0], project_ms_samples=[100, 350, 800, 1700, 2040, 2300], gap_track_rendered=False, active_diff=42.080, inactive_diff=1.925
mmd_render_queue_wiring_qa: ok=True, queued_jobs=1, pre_render_calls=1, thread_inits=1, segments=[(500, 900, 1.0), (900, 1500, 2.0)], progress_values=[28]
mmd_render_queue_export_qa: ok=True, queued_jobs=1, mmd_track_count=2, pre_render_count=1, pre_render_size=1802078, alpha_coverage=0.0860, export_inside=39.368, export_outside=1.559
mmd_long_project_export_qa: ok=True, queued_jobs=1, duration_ms=10000, total_output_ms=8714, mmd_track_count=2, pre_render_size=5669673, segments=[(500, 1800, 1.0), (1800, 3000, 0.75), (3000, 5200, 1.0), (5200, 6800, 1.75), (6800, 9500, 1.0)], samples=[1100, 4457, 8900], export_inside=41.186, export_outside=2.074
mmd_workflow_qa: ok=True, action_count=13, checks=8/8, final_tracks=1
```

Latest MMD export smoke:

```text
Cantarella PMX + wavefile_v2_arora_14 VMD at 320x180: alpha max 255, nonzero alpha 4010
debugCapture/mmd_player/mmd_export_prerender_smoke_0.png
```

Latest PyBullet smoke:

```text
Cantarella PMX + wavefile_v2_arora_14 VMD: backend=pybullet, bodies=415, shapes=415, spheres=3, boxes=223, capsules=189, capsule_axis_fixes=189, constraints=574, joint_frame_constraints=574, solver_iterations=56, constraint_force_avg=44.41, constraint_force_max=260.0, orientation_feedback=378, profile_ok=True
debugCapture/mmd_player/regression/cantarella_wavefile_pybullet.png
debugCapture/mmd_player/regression/cantarella_wavefile_pybullet.json
```

Useful capture commands:

```powershell
.\.venv\Scripts\python.exe tools\capture_mmd_player_screenshot.py --pause --lighting studio_soft --bloom 0.35 --delay-ms 900 --out debugCapture\mmd_player\mmd_light_controls_ui.png
.\.venv\Scripts\python.exe tools\capture_mmd_player_screenshot.py --play --lighting studio_soft --bloom 0.35 --time-ms 6000 --delay-ms 1200 --out debugCapture\mmd_player\mmd_no_angelring_realtime_play.png
.\.venv\Scripts\python.exe tools\mmd_qa_report.py --profile zzz_alice_sea_of_thyme
.\.venv\Scripts\python.exe tools\capture_mmd_player_screenshot.py --profile zzz_alice_sea_of_thyme --delay-ms 900
.\.venv\Scripts\python.exe tools\mmd_qa_report.py --profile cantarella_wavefile_cloth_motion
.\.venv\Scripts\python.exe tools\capture_mmd_player_screenshot.py --profile cantarella_wavefile_cloth_motion --delay-ms 900
```

Latest profile capture:

```text
debugCapture/mmd_player/regression/zzz_alice_sea_of_thyme.png
debugCapture/mmd_player/regression/zzz_alice_sea_of_thyme.json
debugCapture/mmd_player/regression/cantarella_wavefile_cloth_motion.png
debugCapture/mmd_player/regression/cantarella_wavefile_cloth_motion.json
```

## Remaining Work

See also `docs/MMD_TODO.md` for the current MMD-focused backlog.

- Full native MMD compatibility is not claimed.
- Native MMD/Bullet parity comparison is blocked until reference captures are
  available.
- SDEF visual validation is now covered by `tda_onepiece_sdef_validation` from
  `E:/ClaudeCodeApp/mmd`; it has 4,602 SDEF vertices and visual QA renders with
  `gpu=False`, confirming the CPU fallback path.
- VMD curve/camera and self-shadow visual parity are blocked until native MMD
  reference captures are available.
- Do not add speculative MMD tasks. Reopen only for a concrete failing
  model/project or native reference captures.
