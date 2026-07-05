# TigerCapture Export Parity and QA Spec

Last updated: 2026-06-17

This sub-spec describes how to verify that preview-only editor features are
actually baked into final exports, and how to run repeatable UI/performance QA.

## Export Parity Targets

The export path must preserve these preview-visible features:

- Video clip trimming, cuts, speed segments, fades, and transitions.
- Multi-source and nested sequence video lanes.
- Nested sequence audio lanes.
- Clip-level filters: video filters, chroma key, background removal, and
  stabilization.
- Node graph effects, color grading, blur nodes, and masks.
- Tracked `BitmapMask` masks, including cache/failure/correction state.
- Typography overlays when the active license tier allows them.
- Spine actor tracks and nested Spine actor lanes.
- Live2D actor tracks and nested Live2D actor lanes.
- External audio tracks and nested audio remapping.

## Automated Smoke Coverage

Run:

```powershell
.\.venv\Scripts\python.exe tools\verify_export_parity.py
```

This synthetic fixture verifies:

- masked node graph export
- tracked masked node graph export
- Spine overlay baking
- Live2D pre-render overlay baking
- chroma key export
- video filter export
- background-removal pipeline export
- stabilizer export completion
- audio separation fallback/cancel behavior
- tracked mask serialization round trip

The tracked masked-node case uses `BitmapMask(track_object=True)` with a
correction keyframe, then verifies the exported pixels. This is the regression
guard for masks that look correct in preview but fail to bake in final export.

## Real Project Audit

Build the local 6-project QA corpus:

```powershell
.\.venv\Scripts\python.exe tools\build_qa_corpus.py
```

The generated `qa_corpus/` projects cover:

- timeline video/audio basics
- masks, filters, chroma key, and tracked mask cache state
- nested multi-track video/audio
- Live2D/Spine actor track references when local samples are installed
- audio-heavy mixed layouts
- long-project proxy/relink/recovery stress with 100+ video clips and 120+
  audio clips

The generator also creates a readable
`qa_corpus/projects/.tigercapture_recovery/*~autosave.tgp` candidate and
default real-media Color/Audio samples under `qa_corpus/color_audio_samples`.

Run:

```powershell
.\.venv\Scripts\python.exe tools\qa_project_audit.py --project path\to\project.tgp --synthetic
.\.venv\Scripts\python.exe tools\qa_project_audit.py --manifest qa_corpus\qa_corpus_manifest.json
.\.venv\Scripts\python.exe tools\qa_project_audit.py --manifest qa_corpus\qa_corpus_manifest.json --preview-samples 8
.\.venv\Scripts\python.exe tools\qa_project_audit.py --manifest qa_corpus\qa_corpus_manifest.json --preview-samples 8 --baseline debugCapture\project_qa_report_previous.json
.\.venv\Scripts\python.exe tools\qa_long_project_stress.py --out debugCapture\long_project_stress_qa.json
```

The audit is read-only. It reports:

- missing media/model paths
- counts of clips, masks, tracked masks, filters, nested clips, audio clips,
  Spine/Live2D actor clips
- native worker batch media-probe timings for real source files
- Live2D/Spine actor asset completeness, including Spine atlas texture
  dependencies and Live2D model3 moc/texture/motion/expression dependencies
- Live2D/Spine actor asset summary counts by actor kind
- `export_risks` for CPU fallback baking, actor overlays, high-resolution
  decode/proxy needs, and nested timeline export complexity
- synthetic export parity result
- optional sampled `ProjectPlayer` preview timings plus `native_gpu_candidates`
  when `--preview-samples` is supplied
- `preview_engine` status: active decoder/frame-server env, QImage preview mode,
  native worker capabilities, filter/chroma batch state, and Spine
  preview/compositor modes
- `baseline_comparison` when `--baseline` is supplied, flagging projects that
  became unhealthy, missing media/model regressions, actor-asset failure
  increases, export-risk count increases, synthetic parity regressions, and
  delegated preview-performance regressions
- `professional_readiness`, a project-level diagnostic for long-project
  stability, GPU preview/export consistency, timeline edit integrity, color
  workflow depth, and audio mix readiness. Manifest audits also include
  `professional_readiness_summary` with average/min scores and high/medium issue
  totals.
- `qa_long_project_stress.py`, a fast product smoke check for the generated
  long-project fixture, verifying 5+ minutes of duration, nested sequences,
  proxy state, no missing paths, and an `open_safe` recovery candidate.

The preview sampler includes feature positions in addition to evenly-spaced
timeline points: clip starts/mids/ends and Live2D/Spine actor starts/mids/ends.
This prevents low-sample audits from missing actor clips that are not visible at
the exact project start or end.

Use `--fail-on-missing` in CI or release QA when all referenced assets must be
available.

## UI Layout QA

Run:

```powershell
.\.venv\Scripts\python.exe tools\qa_ui_layout.py --out debugCapture\ui_qa
.\.venv\Scripts\python.exe tools\qa_visual_regression.py --out debugCapture\visual_regression
.\.venv\Scripts\python.exe tools\qa_visual_baseline_manager.py
.\.venv\Scripts\python.exe tools\qa_visual_baseline_audit.py --out debugCapture\visual_baseline_audit.json
.\.venv\Scripts\python.exe tools\qa_micro_interactions.py --out debugCapture\micro_interactions_qa.json
```

The script captures the main editor at 1366x768, 1920x1080, and 2560x1080 and
writes `layout_report.json`. It fails if the left rail, center viewer, right
inspector, workbench, or timeline collapse below practical minimum dimensions.
`qa_visual_regression.py` compares the captured layout against the approved
baseline; tiny offscreen-render pixel jitter is tolerated with image-diff
thresholds, while real layout changes remain blocking. `qa_micro_interactions.py`
smoke-tests code-native icons, rollover labels, timeline burst painter
availability, blade entry points, and global hover/pressed styling.

For real monitor QA:

```powershell
.\.venv\Scripts\python.exe tools\qa_ui_layout.py --onscreen --out debugCapture\ui_qa_real
```

## Color and Audio Accuracy QA

Run:

```powershell
.\.venv\Scripts\python.exe tools\qa_color_audio_accuracy.py --out debugCapture\color_audio_accuracy_qa.json
.\.venv\Scripts\python.exe tools\qa_color_audio_accuracy.py --video-sample path\to\shot.mp4 --audio-sample path\to\dialogue.wav --out debugCapture\color_audio_accuracy_qa.json
.\.venv\Scripts\python.exe tools\qa_color_audio_accuracy.py --sample-root qa_corpus\color_audio_samples --out debugCapture\color_audio_accuracy_qa.json
```

This synthetic QA pass validates the professional Color/Audio features that are
easy to regress while polishing UI:

- scopes: luma ramp range, clipping warnings, and nonblank histogram, parade,
  waveform, and vectorscope renders
- color management: Rec.709 metadata, Rec.2020 HDR PQ metadata, ACES/OCIO
  warning behavior, LUT blend graph generation, and ffprobe metadata comparison
- audio: approximate integrated LUFS target matching, true-peak warning,
  stereo correlation warning, dialogue-cleanup clamping, and shared LUFS helper
  consistency with the Audio Mixer meter

The report should return `ok: true`, zero failures, and writes a structured
check list to `debugCapture/color_audio_accuracy_qa.json`. Real sample checks
verify that media can be decoded and that scope/loudness diagnostics produce
finite values; creative warnings such as clipping or loudness mismatch are
included in the report without replacing the deterministic reference checks.
The default generated corpus includes two video scope samples and two audio
diagnostic samples, so the productization loop expects a nonzero real-sample
count rather than synthetic-only coverage.

## Actor Mass Compatibility QA

Run:

```powershell
.\.venv\Scripts\python.exe tools\qa_actor_mass_compat.py --out debugCapture\actor_mass_compat_qa.json
```

This product smoke check reads `debugCapture/actor_corpus_status.json` and
`qa_corpus/actor_corpus_manifest.json`. It verifies total/Spine/Live2D/stress
coverage targets, known-failure quarantine presence, no high-severity actor
issues, and seeded golden baselines.

## Productization Fast QA

Run:

```powershell
.\.venv\Scripts\python.exe tools\qa_productization_loop.py --run-fast-qa
```

The fast loop bootstraps the QA corpus, then runs Color/Audio real-sample QA,
long-project stress, micro-interactions, actor mass compatibility, visual
regression/baseline audit, timeline fuzz/alignment, actor workflow with real
samples, Node Graph fuzzers, and preset application QA. A healthy local run
reports score `100`.

## Commercial Expansion QA

Run:

```powershell
.\.venv\Scripts\python.exe tools\qa_commercial_expansion.py --out debugCapture\commercial_expansion_qa.json
```

This broader product-readiness layer tracks the next ten commercial surfaces:
beta feedback bundles, preview frame-server/hardware-decode UX, preview/export
parity lock settings, AI one-click edit planning, preset marketplace health,
audio postproduction depth, color-node workflow depth, project snapshots,
plugin manifests, and release productization. The report is exposed in QA
Dashboard and is included in the productization fast-QA loop.

## Localization QA

Run:

```powershell
.\.venv\Scripts\python.exe tools\qa_localization_audit.py
.\.venv\Scripts\python.exe tools\qa_localization_audit.py --strict
```

This verifies locale placeholder compatibility and scans translation strings
for known mojibake tokens. `--strict` is expected to pass for `en`, `ko`, `ja`,
`zh`, `fr`, and `de`; it fails if any non-English table falls back to English
because a key is missing.

## Performance QA

Before moving more code out of Python, collect real-project baselines:

```powershell
$env:TIGERCAPTURE_PERF='1'
$env:TIGERCAPTURE_PERF_STAGE_MS='2'
.\.venv\Scripts\python.exe main.py
```

Then open a representative project and play/export:

- 1080p baseline project
- 4K baseline project
- tracked mask project
- Live2D/Spine actor project
- audio-heavy project
- nested multi-track project

The slowest repeated `[perf] preview.stage.*` and raw pre-render export stages
are the only candidates for native/Rust migration. Do not rewrite broad UI or
timeline logic until a measurement names the hotspot.

For automated preview and cache baselines:

```powershell
.\.venv\Scripts\python.exe tools\qa_preview_perf.py --clean
.\.venv\Scripts\python.exe tools\qa_preview_perf.py --clean --include-hires --render-samples 8
.\.venv\Scripts\python.exe tools\qa_preview_perf.py --clean --include-hires --render-samples 8 --baseline debugCapture\preview_perf_report_previous.json
```

This measures native `batch_media_probe`, `timeline_thumbnails`, and sampled
`ProjectPlayer` preview renders over the QA corpus. `--include-hires` also
generates 1080p and 4K baseline fixture projects under `debugCapture/` and
includes them in the same report. Output is written to
`debugCapture/preview_perf_report.json`. When `--baseline` is supplied, the
report includes `baseline_comparison` with media-probe, thumbnail, preview-frame,
and per-stage regressions/improvements. Blocking regressions make the report
fail so release QA can catch decode, thumbnail, shader/filter, Live2D, or Spine
slowdowns before they become user-visible. Non-comparable or noisy signals stay
visible as `advisory_regressions`: warm-up `preview.refresh.render` samples,
p95-only stage spikes without a sustained average regression, and per-stage
changes from a different preview sample plan.

For missing-media repair after moving projects between machines:

```powershell
.\.venv\Scripts\python.exe tools\relink_project_media.py path\to\project.tgp D:\Footage D:\Models
.\.venv\Scripts\python.exe tools\relink_project_media.py --health path\to\project.tgp D:\Footage D:\Models
```

This writes a `.relinked.tgp` copy by matching missing filenames under the
provided search roots. It does not mutate the original unless `--in-place` is
used. `--health` does not write a copy; it reports missing paths, candidate
conflicts, repeated path references, duplicate filename collisions, and
ready/stale/missing sibling proxy state for long-project triage.

The editor toolbar also exposes `Health`, which audits the current in-memory
session without forcing a save. It shows media/model references in a read-only
status table with proxy state, reference counts, relink candidate counts, path,
and recommended action; missing/relink-conflict rows can jump straight into the
Relink browser. The same dialog now includes professional-readiness scoring for
long-project stability, GPU preview/export consistency, timeline edit integrity,
color workflow depth, and audio mix readiness, with section scores and top
actions shown in the detail pane.

Single export and editor-created Render Queue jobs also run the same
professional-readiness preflight from the current in-memory session. Single
exports append the compact readiness diagnostic to success/failure dialogs, and
Render Queue jobs preserve it in job diagnostics while the encoder moves
through pending/running/stage/done states. Screen Studio-style completion is
shared as well: successful single exports and completed Render Queue jobs use
`screenstudio_export_completion_summary()`, eligible jobs write
`<output>.share.json`, and Render Queue diagnostics show completion status,
manifest path, and Reveal/Copy/share actions. The Screen Studio export-handoff
QA report also includes a default-result beauty gate:
`default_beauty_ready` and `default_beauty_score` are derived from
`screenstudio_default_result_beauty_score()`, which scores the no-manual-tuning
path across delivery defaults, frame styling, cursor FX, Auto Zoom, handoff,
simple-mode policy, motion defaults, vertical safety, audio defaults, and
golden-video coverage. The current fast golden-video gate is
`screenstudio_default_golden_video_probe()`: it renders representative frames
and checks wallpaper/frame styling, cursor/click pixel deltas, Auto Zoom
planning, and preview/export compositor parity.

The editor toolbar also exposes `Relink...`, which opens a missing-media
browser for the same non-destructive project-file repair flow. The browser can
scan multiple search roots, show every missing file, let the user pick a
replacement when multiple same-name candidates exist, warn about unresolved
files, duplicate selections, stale proxies, or missing proxies, and open the
relinked copy immediately.

For preset-library QA:

```powershell
.\.venv\Scripts\python.exe tools\list_editor_presets.py
.\.venv\Scripts\python.exe tools\list_editor_presets.py --kind transition
.\.venv\Scripts\python.exe tools\list_editor_presets.py --kind audio --query dialogue
.\.venv\Scripts\python.exe tools\list_editor_presets.py --kind color --tag tracking
.\.venv\Scripts\python.exe tools\list_editor_presets.py --summary
```

The editor also exposes built-in effect presets as left-dock draggable cards.
Dropping an effect preset on a video clip applies its clip-level effect payload
through `app.preset_library.apply_effect_preset_to_clip()`. Built-ins now cover
basic transitions, beat/long dissolves, gameplay/cleanup/glitch filters,
green/blue-screen keying, UI capture, archive cleanup, esports/gameplay,
music-video, lower thirds, short captions, chapter cards, speaker tags, score
callouts, Live2D nameplates, color qualifier/window workflows, dialogue cleanup,
loudness delivery targets, short-form templates, caption styles, stickers, and
motion presets. The social/creator pack adds vertical-safe captions, tutorial
step packs, product-demo templates, streamer/reaction workflows, creator voice
chains, CTA/callout stickers, and product/social color starters. Screen
Studio delivery templates now include record/edit/export, click-to-cut,
wallpaper demo, product walkthrough, and short export one-click flows; they are
composed from existing child presets so `preset_ecosystem_report()` can catch
missing or wrong-kind references. Use
`app.preset_library.search_presets()` and `preset_library_summary()` for
library diagnostics.
Visible UI surfaces: effect cards in the left dock, Workflow Presets in the
left dock for template/caption/sticker/motion packs, professional color presets
inside the Color preset dropdown, and professional audio presets inside the
Sound Editor AI Master tab. Workflow Preset cards can be clicked for the
current target or dropped on a timeline row for time-specific application;
timeline drops prioritize the drop track/time, and template cards expand into
their ordered preset sequence with entry times relative to the target time.
The launcher keeps template entry points quiet instead of showing large
template cards on the first screen; the full template library is opened through
the editor's focused Templates browser, which filters Workflow Presets to
template-only cards while keeping drag/drop workflow cards available in the
left dock. When a startup template payload is supplied, the editor stores the
pending template and applies it after the first compatible media import.
Template application must remain visible in product QA through the A/B
wallpaper-palette preview, a preview-overlay summary toast, video timeline
badges for applied state (`FX`, `Key`, `TR`, `COL`, `T`, `Mot`, `Nest`), and
the audio timeline `AUD` badge for clip-level audio chains.
`tools/qa_startup_flow.py` captures both the template A/B preview and the
template apply-summary screenshot, and also writes `startup_layout_metrics.json`
with structural checks that the launcher has a small templates button rather
than a large template-card panel, so this startup/template path is covered by
repeatable visual QA.

For actor model compatibility QA before slow render tests:

```powershell
.\.venv\Scripts\python.exe tools\actor_compat_matrix.py resources\spine_samples resources\live2d_samples
.\.venv\Scripts\python.exe tools\actor_compat_matrix.py resources --parse-spine --limit 20
.\.venv\Scripts\python.exe tools\actor_compat_matrix.py resources\spine_samples resources\live2d_samples --limit 10 --summary-only
.\.venv\Scripts\python.exe tools\actor_render_qa.py resources\spine_samples resources\live2d_samples --parse-spine --limit 10 --summary-only
.\.venv\Scripts\python.exe tools\actor_corpus_regression.py --manifest qa_corpus\actor_corpus_manifest.json --summary-only
.\tools\run_actor_full_qa.ps1 -Manifest qa_corpus\actor_corpus_manifest.json
.\.venv\Scripts\python.exe tools\actor_golden_manager.py --manifest qa_corpus\actor_corpus_manifest.json
```

This writes `debugCapture/actor_compat_matrix.json` and checks Spine atlas
textures plus Live2D model3 moc/texture/motion/expression dependencies. It is
the fast corpus preflight; use `tools/test_spine_resources.py` afterward for
render/nonblank validation. The report includes severity, issue codes, family
grouping, dependency/missing-dependency counts, recommendations, issue-count
summary, and top failures. `--summary-only` prints only the compact summary
while still saving the full JSON report.

For large Live2D/Spine render QA, prefer `tools/actor_render_qa.py`. It writes
`debugCapture/actor_render_qa.json`, preserves the compatibility matrix inside
the same report, then runs Spine render/nonblank validation and Live2D
child-process render checks with separate status counts and top failures.
Live2D model paths and stdout are forced through UTF-8 so Korean/Japanese/
Chinese sample names do not crash the QA worker, and visible output is judged
by alpha bbox rather than only by image-object existence. The Live2D pass
renders the normalized runtime model path directly, samples several early
timestamps, and separates `render_none` from alpha-blank output. A slow Live2D
child process is recorded as a `timeout` result with captured stdout/stderr
tails, so one model cannot abort the full corpus report. Use
`--render-limit` when compatibility should scan more models than the slower
render pass, `--no-spine-render` or `--no-live2d-render` to isolate a family,
and `--no-render` for a dependency-only dry run through the same output shape.
Compatibility rows treat Live2D MOC and texture references as render-required;
missing expression/physics/display/motion references remain in the report as
warnings so they are not mistaken for base-render failures.
Spine compatibility and render QA prefer a same-stem Spine JSON export over a
binary `.skel` when both exist. This keeps large corpus runs actionable for
Spine 4.2 binary samples while the current binary parser still lacks full 4.2
support.

For operational regression runs, use `tools/actor_corpus_regression.py` with
`qa_corpus/actor_corpus_manifest.json`. The manifest ties together actor roots,
known-failure quarantine, top-risk render sampling, animation sweep,
golden-image comparison, and optional baseline comparison. The command writes a
full report plus `debugCapture/actor_corpus_status.json`, a compact UI/Health
artifact with coverage totals, render failure categories, golden counts,
quarantine counts, per-model `pass/risk/fail/quarantined` rows, and top
actions. The manifest also accepts `optional_roots` so large real model
corpora can live outside the repository and join local runs when present.
Media Pool actor items read the compact status artifact and display QA badges
on actor thumbnails/tooltips. The safe GitHub preflight workflow
`.github/workflows/actor-corpus-qa.yml` runs weekly with `--no-render`; local
render/golden runs should be used for real GPU/Live2D validation. Use
`tools/run_actor_full_qa.ps1` for that local full pass and
`tools/actor_golden_manager.py --promote-actual` only when intentionally
accepting new golden baselines. The golden manager reports baseline/actual
matching counts, pending promotions, and stale baselines so acceptance state is
visible without opening the full render report.

Animation sweep now goes beyond first-frame nonblank checks. Spine sweep samples
multiple animations across selected skins, records skin/slot attachment
summaries, blank-frame counts, bounding boxes, center-jump diagnostics, and
mix-and-match skin-combination samples. Live2D sweep renders multiple motion
and expression variants; physics, pose, display-info, user-data, and hit-area
metadata coverage is recorded so models that only fail outside the default idle
path are easier to prioritize.

Full installed actor corpus result from 2026-06-16 on this workstation:
compatibility and render QA both passed for 199 models total, covering 160 Spine
models and 39 Live2D models.

Actor corpus recalibration from 2026-06-17 on this workstation:

- NIKKE-style Spine rigs with weighted mesh + constraints + multi-page atlas
  are classified as `stress`, lifting local stress coverage from 2 to 10.
- `tools/run_actor_full_qa.ps1 -UpdateGolden` passed and created 40 actor
  golden baselines: 20 Spine/top-risk and 20 Live2D/top-risk renders.
- `debugCapture/actor_corpus_status.json` reported 200 total resources, 161
  Spine, 39 Live2D, 1 quarantined synthetic fixture, 0 issues, and
  `ready_for_compare=true`.

Initial baseline from 2026-06-14 on this workstation:

- batch media probe: 194.59 ms for 6 media files
- slowest thumbnail batch: 634.68 ms for 8 thumbnails
- mask/filter/tracking QA project: preview avg 115.95 ms, max 122.16 ms;
  top stages are `preview.stage.chroma_key` and `preview.stage.video_filters`
- Live2D/Spine actor QA project: preview avg 117.93 ms, max 373.24 ms;
  top stage is `preview.stage.spine_overlay`
- 1080p baseline fixture: preview avg 46.12 ms, max 53.99 ms;
  top stage is `preview.stage.decode`
- 4K baseline fixture: preview avg 63.20 ms, max 64.20 ms;
  top stage is `preview.stage.decode`

After the first preview optimization pass on 2026-06-14:

- mask/filter/tracking QA project: best rerun preview avg 93.32 ms,
  max 104.67 ms; `preview.stage.video_filters` dropped from 45.50 ms avg to
  21.99 ms avg after vignette-mask caching, while `preview.stage.chroma_key`
  remains the main Python hotspot.
- Live2D/Spine actor QA project: preview avg 69.93 ms, max 114.26 ms after
  half-resolution Spine preview, software fast-mesh rendering, GL-preview
  bypass, animated-frame cache, and renderer prewarm.
- Existing fresh sibling proxies at `proxies/<stem>_proxy.mp4` are used
  automatically by preview decode. When no proxy exists, high-resolution decode
  remains dominated by source decode cost and should be addressed with proxy
  generation or a native/GPU decode path.

After the second preview/cache pass on 2026-06-14
(`debugCapture/preview_perf_report_after_all_remaining_v2.json`):

- mask/filter/tracking QA project: preview avg 40.34 ms; top stages are
  `preview.stage.decode` 22.28 ms avg, `preview.stage.chroma_key` 10.01 ms avg,
  and `preview.stage.video_filters` 6.92 ms avg.
- Live2D/Spine actor QA project: preview avg 62.60 ms; `preview.stage.spine_overlay`
  is still the main bottleneck at 36.26 ms avg / 82.22 ms p95.
- `native_gpu_candidates` now names Spine mesh batching/GPU actor compositing,
  decode/proxy/hardware frame server, and shader-backed chroma key as the next
  measured migration candidates.

After the GPU/native-facing preview pass on 2026-06-15
(`debugCapture/preview_perf_report_after_gpu_native_v1.json`):

- mask/filter/tracking QA project: preview avg 35.54 ms; top stages are
  `preview.stage.decode` 22.29 ms avg, `preview.stage.video_filters` 8.03 ms
  avg, and `preview.stage.chroma_key` 4.31 ms avg. The chroma preview path now
  uses OpenCV native LUT/mask operations plus preview-only downsample/upsample;
  export still uses full-resolution chroma key for parity.
- Live2D/Spine actor QA project: preview avg 67.13 ms; `preview.stage.spine_overlay`
  remains the main bottleneck at 38.51 ms avg / 88.11 ms p95. The GL renderer
  now batches consecutive meshes by atlas texture. An opt-in direct RGBA ndarray
  compositor is available with `TIGERCAPTURE_SPINE_ARRAY_COMPOSITOR=1`, but
  local QA showed the current FBO readback path can make it slower overall, so
  the default remains the previously measured PIL compositor. The next measured
  Spine target is full GL actor compositing / FBO readback elimination rather
  than another Python cache.
- Decode remains a broad preview floor at roughly 21-25 ms avg across sampled
  video projects. `PrefetchDecoder` now exposes `TIGERCAPTURE_PREFETCH_FRAMES`
  and `TIGERCAPTURE_PREFETCH_READ_TIMEOUT` for internal preview frame-server
  tuning. OpenCV FFMPEG hardware decode can be attempted through open
  parameters with `TIGERCAPTURE_ENABLE_HW_DECODE=1`, but software decode stays
  the default because local QA showed active HW decode can be slower on this
  machine. Process-level frame serving remains the next larger architecture
  step when decode stays dominant.

After the follow-up preview-speed pass on 2026-06-15
(`debugCapture/preview_perf_report_after_gpu_native_v4.json`):

- mask/filter/tracking QA project: preview avg 37.46 ms; top stages are
  `preview.stage.decode` 25.50 ms avg, `preview.stage.video_filters` 5.73 ms
  avg, and `preview.stage.chroma_key` 4.44 ms avg. Preview filter/chroma
  downsample defaults are now 0.375 scale; export still uses full-resolution
  clip-effect paths.
- Live2D/Spine actor QA project: preview avg 68.64 ms; `preview.stage.spine_overlay`
  remains the main bottleneck at 43.01 ms avg / 98.46 ms p95. Spine preview now
  quantizes animated cache time at 24fps by default, which helps normal
  playback reuse but does not remove the FBO readback cost.
- General video/audio projects measured decode floors around 20-25 ms avg.
  `PrefetchDecoder` now keeps 24 frames by default with an 80 ms read budget,
  and OpenCV next-frame explicit seeks skip redundant `CAP_PROP_POS_FRAMES`.
  The remaining measured architecture target is still a process-level preview
  frame server or stronger proxy/hardware-decode path for no-proxy projects.

After the "big three" implementation pass on 2026-06-15
(`debugCapture/preview_perf_report_after_all_big_three_v1.json`):

- mask/filter/tracking QA project: preview avg 32.46 ms. The separate
  video-filter and chroma passes are replaced, when both are active and
  preview-safe, by `preview.stage.filter_chroma_batch` at 8.24 ms avg /
  12.13 ms p95. Decode remains the largest stage at 23.46 ms avg.
- Live2D/Spine actor QA project: preview avg 74.07 ms. `preview.stage.spine_overlay`
  remains 43.05 ms avg / 100.68 ms p95 on this single-Spine-clip sample.
  `SpineOverlayGLCompositor` now supports drawing multiple active Spine clips
  into one FBO/readback. Single complex rigs also use an adaptive lower preview
  cache/readback FPS (`TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_FPS`, default 12)
  when their complexity score crosses
  `TIGERCAPTURE_SPINE_COMPLEX_THRESHOLD` (default 900). The main GL preview
  now also has a zero-readback path (`TIGERCAPTURE_SPINE_ZERO_READBACK=1`):
  when CPU final-frame consumers are inactive and no top-level Live2D actor
  requires CPU ordering, Spine render states are sent to `OpenGLPreviewWidget`
  and actor meshes are drawn directly in the preview GL viewport. A shader or
  context failure disables this path and refreshes through CPU compositing.
  Direct overlay states are cached by quantized preview time, output size, and
  clip signature, avoiding repeated Spine state rebuilds while the same frame is
  repainted.
- `TIGERCAPTURE_PREVIEW_FRAME_SERVER=1` enables the FFmpeg pipe frame-server
  decoder. It passed functional QA in
  `debugCapture/preview_perf_report_after_frame_server_optin_v1.json`, but
  random-seek decode on this corpus rose to roughly 55-63 ms avg, so OpenCV
  prefetch/cache remains the default on this machine.
- `TIGERCAPTURE_PREVIEW_DECODER_AUTO=1` or
  `TIGERCAPTURE_PREVIEW_FRAME_SERVER=auto` now benchmarks OpenCV vs the FFmpeg
  frame server per source/proxy/preview-height tuple and caches the winning
  backend. The auto path keeps OpenCV unless the frame server wins by a
  meaningful margin, so the slower opt-in frame-server result above does not
  become the default accidentally.

After the 2026-06-17 actor preview QA calibration
(`debugCapture/preview_perf_report_after_spine_state_cache_v3.json`):

- Preview baseline comparison now separates blocking regressions from advisory
  signals. `preview.refresh.render` warm-up spikes, p95-only stage spikes
  without an average regression, and per-stage changes caused by different
  preview sample plans stay visible in `advisory_regressions` but do not fail
  the report.
- The comparison against
  `debugCapture/preview_perf_report_after_all_big_three_v1.json` passed with
  zero blocking regressions. The Live2D/Spine actor QA project improved from
  74.07 ms average / 129.31 ms p95 to 54.94 ms average / 77.80 ms p95. Its
  decode stage improved from 23.59 ms average to 5.31 ms average, while
  `preview.stage.spine_overlay` remains the largest measured actor hotspot at
  48.62 ms average / 72.96 ms p95.
- Golden actor comparison was also verified without promotion:
  `debugCapture/actor_corpus_regression_golden_verify.json` reported 40 matching
  golden baselines, zero pending promotions, zero stale baselines, and no actor
  corpus issues.
- An opt-in `TIGERCAPTURE_SPINE_ARRAY_COMPOSITOR=1` trial
  (`debugCapture/preview_perf_report_spine_array_compositor_trial_v1.json`)
  passed but did not produce a clear default-setting win on this machine
  (actor preview stayed near 55 ms average and p95 rose to about 91.87 ms), so
  the default compositor remains unchanged until the full GPU actor compositor
  removes the remaining readback cost.

After the shader preview parity pass on 2026-06-16:

- `TIGERCAPTURE_SHADER_CLIP_FX=1` is the default GL-preview path for
  preview-safe clip effects. When QImage/popout/color-page CPU consumers are
  inactive and ordering-sensitive effects are absent, `ProjectPlayer` sends
  `clip_effects` metadata instead of running CPU preview filters/chroma.
- `OpenGLPreviewWidget` applies shader uniforms for `sharpen`, `vignette`,
  `chroma_aberration`, and HSV chroma key before color grade and before direct
  Spine GL overlay drawing. QImage fallback, export, `denoise`, `glitch`,
  background removal, PIP/Live2D ordering, and active transitions stay on the
  CPU path for parity.
- No new real-project timing report has been generated for this pass yet; run
  `tools/qa_preview_perf.py --render-samples <N>` or
  `tools/qa_project_audit.py --preview-samples <N>` on the QA corpus before
  comparing it against the previous 32.46 ms mask/filter baseline.

After the loading/prewarm acceleration pass on 2026-06-27:

- First-use slowness is now diagnosable without a profiler. Live2D/Spine actor
  loading stages are mirrored from `app.actor_loading_cache` into
  `debugCapture/loading_performance.jsonl`; decoder auto-benchmark/open
  decisions are logged from `app.video_decoder`; AR/PBR model preview logs
  import, GPU vertex source, HDRI, texture-plan, and ready stages.
- `app.preview_acceleration.configure_preview_acceleration_defaults()` applies
  conservative fast-path defaults unless overridden: decoder auto-selection,
  frame-server auto mode, forward-seek/cache tuning, Spine GL/zero-readback
  preview, direct Spine-with-Live2D preview when safe, and AR/PBR GPU preview.
- Editor startup schedules background parser/importer/Live2D runtime prewarm
  after the window is visible. Media Pool 3D asset intake also warms the
  persistent AR/PBR descriptor cache so the first model preview does not pay
  full FBX parse cost on every open.
- AR/PBR model preview windows are keyed by asset/track and reused when already
  open. This avoids repeated GL/context/import setup when the user double-clicks
  the same model repeatedly.
- Run `.\.venv\Scripts\python.exe tools\qa_loading_performance.py` to write
  `debugCapture/loading_performance_qa.json`. The report verifies the active
  preview policy and summarizes recent slow loading stages.

After the GPU/export parity matrix pass on 2026-06-27:

- `tools/verify_export_parity.py` now writes
  `debugCapture/export_parity_smoke_qa.json` and includes a render-clip
  dissolve transition smoke test. `VideoExportThread` automatically uses the
  preview-parity base-frame path when `render_clip_tracks` are present, so
  multi-source/nested transition renders cannot silently fall back to a plain
  FFmpeg graph.
- `tools/qa_gpu_export_parity_matrix.py` runs the GL pixel-collision QA, final
  editor export-bake QA, and synthetic export parity smoke into
  `debugCapture/gpu_export_parity_matrix_qa.json`. The matrix covers color
  grade, shader effects/chroma, typography export pixels, Spine/Live2D actor
  preview/export evidence, transition export, and masked node graph export.
- The matrix has two concepts: `ok` means the current blocking parity evidence
  is healthy; `release_ready` means every listed coverage area is complete.
- `tools/qa_ar_pbr_export_bake.py` now verifies AR/PBR object tracks are baked
  into final MP4 output. The exporter forces the raw preview-parity base-frame
  path when AR/PBR tracks are present and uses
  `app.ar_pbr.export_packet_renderer` to rasterize the same
  `build_gpu_preview_items()` packet contract that the GL preview draws.
  `composite_export_frame()` remains a fallback when packet rendering cannot
  draw a track. The packet renderer composites an overlay-only SSAA pass
  (`TIGERCAPTURE_AR_PBR_PACKET_SSAA`, default `2`) over the original source
  frame. The QA checks mesh, shadow, and reflection packet triangles, packet
  SSAA, final MP4 pixel differences, AR/PBR-colored overlay pixels, and catcher
  darkening. It also verifies shared material texture-plan readiness,
  base-texture average preview tinting, headless UV texture sampling, and
  headless PBR material-map sampling for base/roughness/metallic/specular/normal/occlusion
  maps. The GL timeline preview now also receives
  `pbr_triangles` with projected position, UV, normal, tangent, bitangent,
  base color, material roughness/metallic/reflectance data, resolved
  roughness/metallic/specular/normal/occlusion maps, glTF-style packed-channel
  selectors, and HDRI lighting metadata.
  `OpenGLPreviewWidget` draws those triangles with a model-view-style material
  map PBR fragment shader over the existing shadow/reflection packet fallback.
  The headless packet renderer mirrors that material-map path with a CPU
  rasterizer, direction-sampled HDRI diffuse/specular IBL, cached downsampled
  HDRI prefilter levels for roughness-selected specular IBL, packet SSAA,
  occlusion-map darkening, and a per-pixel depth mask from either the export
  depth source or the packet's live depth texture. The QA
  requires `pbr_hdri_directional_sampling`, `pbr_prefiltered_ibl`, at least two
  prefilter levels, and nonzero sampled pixels so export cannot silently fall
  back to flat average lighting. Mesh
  shadows/reflections are screen-space silhouette catchers with layered
  depth-fade reflection fallback, not real shadow maps yet.
  `qa_ar_pbr_export_bake.py` forces packet export so this fallback contract is
  tested even on machines where the full-GPU helper is available.
  `gpu`/`offscreen_gpu` export renderer
  requests now invoke `tools/ar_pbr_full_gpu_export_service.py` through
  `app.ar_pbr.full_gpu_export_service` before falling back. A successful helper
  render reports `mode=full_model_view_gpu_export_service`,
  `renderer_quality=full_model_view_gpu_pbr`, `worker_safe=true`, and
  `fallback=false`; helper failure reports the service attempt and then uses
  `offscreen_gpu_requested_packet_fallback`. This keeps model-view OpenGL work
  outside `VideoExportThread` while allowing final export to use the same
  PBR/texture/HDRI renderer family as the standalone model viewer.
  On Windows the service process now forces `QT_OPENGL=desktop`; without that
  guard Qt can choose an ANGLE/software surface that fails the PyOpenGL
  model-view path at `glViewport`, causing an unnecessary packet fallback.
  The helper renders in an offscreen-positioned native window instead of a
  `WA_DontShowOnScreen` widget so the GL context stays valid.
  The GPU/export parity matrix now also includes the full model-view GPU helper
  smoke render, actor loading UX, and actor-lane workflow QA with real
  Live2D/Spine samples, and can reach `release_ready=true` only when the helper
  path renders without packet fallback.
- Current latest matrix status requires `live2d_actor` preview coverage and
  export evidence together. Export-side synthetic Live2D bake evidence does not
  satisfy the release gate by itself; the real Live2D preview path must also be
  visible in the GPU preview pixel-collision QA.
- AR/PBR still has renderer-quality follow-up work, but the worker-safe
  full-GPU helper path exists. Current packet/GL paths cover live depth texture
  fragment occlusion, item-depth export masking, AO/packed-channel material
  parity, and layered reflection catchers. Remaining quality work is real
  shadow maps, physically richer reflections, GPU/model-view cubemap prefilter
  tuning, batching/reuse across frames, and lens/camera-solve fidelity.

## Crash Recovery and Project Repair

The editor autosaves a resumable `*~autosave.tgp` file and also keeps rotating
recovery snapshots. The default interval is 120 seconds and can be overridden
with `TIGERCAPTURE_AUTOSAVE_INTERVAL_MS`; snapshots retain 24 copies by default
and can be overridden with `TIGERCAPTURE_RECOVERY_KEEP`:

- named projects: `<project folder>\.tigercapture_recovery\`
- untitled projects: `~/Videos/TigerCapture/.recovery/`

The newest autosave is remembered in QSettings so the title flow can offer
resume on next launch.

Unhandled Python exceptions also write a structured report to
`logs/crash_report_latest.json`; recent breadcrumbs are appended to
`logs/recent_actions.jsonl`. The editor registers its autosave callback with
`app.crash_reporter`, so an unhandled exception attempts one emergency autosave
before the JSON report is finalized.

The editor exposes the latest crash report through `Crash Report` in the
Project menu and Command Palette. The dialog shows the exception, traceback,
recent breadcrumbs, emergency autosave, log-folder shortcut, and repro export.
On blank editor startup, unseen crash reports are shown before the normal
last-project resume prompt so users can inspect or open the emergency autosave
immediately.

For reproducible bug reports:

```powershell
.\.venv\Scripts\python.exe -c "from app.crash_reporter import export_repro_bundle; print(export_repro_bundle())"
```

This writes `debugCapture/repro/crash_repro_*.json` with summarized repro
steps plus the raw recent-action trail.

Recovery candidates can be ranked without opening the UI:

```powershell
.\.venv\Scripts\python.exe tools\repair_project.py --list-recovery
.\.venv\Scripts\python.exe tools\repair_project.py --list-recovery path\to\project-folder
```

The command reports the newest readable autosave/recovery project, whether it
passes repair/audit checks, missing media counts, and the normalized project
summary. It also includes a `product_summary` with candidate health levels,
scores, recommended user actions, and reasons. Use `--drop-missing-media` only
when intentionally creating a repaired copy that omits unavailable sources.

The main editor toolbar also has a `Recovery` action. It audits the same
candidate set, opens a table-based recovery browser with health/action details,
missing-media counts, schema-change counts, modified time, size, and path,
autosaves the current session defensively, then opens the chosen readable
recovery project through the normal project loader.

To repair a damaged or legacy project without mutating the original:

```powershell
.\.venv\Scripts\python.exe tools\repair_project.py path\to\project.tgp
```

The repair tool writes `<name>.repaired.tgp`, fills missing schema defaults,
normalizes clip timing lists, de-duplicates the media pool, reports missing
assets, and can optionally drop missing media references with
`--drop-missing-media`. `repair_project_doc()` also returns `repair_guidance`
with missing-media, actor-asset, schema-change counts, severity, and suggested
next actions.
