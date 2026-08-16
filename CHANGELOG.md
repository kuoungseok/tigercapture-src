# Changelog

Format: grouped by area, newest work at the top of each section.

## Unreleased

### Changed

- **Resolve/Fairlight/Fusion parity tracking** — Professional Readiness now
  includes an advisory `resolve_post_pipeline_parity` matrix covering advanced
  Color, Fairlight-style audio, Fusion/VFX, large-project performance,
  professional post pipeline, and hardware ecosystem gaps. The section maps
  supported/partial/missing capabilities such as HDR/ACES, RAW controls, node
  grading, Fairlight routing/loudness, Fusion tracking/keying/3D tools, proxy
  cache, render queue, collaboration, and DeckLink/control-surface readiness
  without unfairly failing ordinary export-readiness scores.
- **Resolve parity is visible and actionable** — Media Health now expands the
  advisory matrix into category scores, supported/partial/missing counts,
  supported highlights, and the next implementation actions. Health Center has
  a dedicated Professional Readiness row, and QA Dashboard now tracks
  `debugCapture/project_qa_report.json` with readiness and Resolve parity
  summaries from real-project QA.
- **First Resolve-class workflow tranche** — Added Qt-free workflow models and
  helpers for advanced Color, Fairlight-style Audio, VFX repair, performance
  cache policy, ingest clone manifests, and Deliver-page job matrices. Color now
  has 32-bit/YRGB capability metadata plus HDR zone tone, log wheel, Hue vs
  Hue/Sat/Luma, and Color Warper frame helpers. Audio now has routing-matrix,
  send, and loudness-delivery report helpers. VFX/Post now has roto spline,
  clean-plate, planar-tracker payloads, proxy/render-cache policy, checksum
  ingest manifests, and web/social/UHD/roundtrip delivery specs. Professional
  Readiness merges these built-in capabilities into the Resolve/Fairlight/
  Fusion parity matrix automatically.
- **Advanced Color bake path** — `ColorGrade` now persists
  `advanced_color_toolset` payloads and applies implemented HDR-zone, log-wheel,
  Hue curve, and Color Warper transforms through the same `apply_to_rgb()` path
  used by preview and export. Three Resolve-style color presets seed those
  payloads, preset application writes them onto grades, and Professional
  Readiness/GPU parity diagnostics now count advanced color, project-level audio
  routing, VFX repair plans, proxy/render cache, ingest clone manifests, and
  Deliver-page jobs instead of treating them as invisible metadata.
- **Professional workflow payload builder** — Added a shared project payload
  builder for Audio Mixer, Media Pool, Render Queue, Health, and QA. It can
  attach Fairlight-style audio routing, proxy/render-cache policy, filtered
  Deliver-page jobs, and checksum ingest manifests without mutating the live
  project document. Audio Mixer also exposes routing/loudness payload helpers
  and shows a compact routing summary for the current tracks.
- **Professional workflow UI hooks** — The full Color Page now exposes a small
  Advanced Color section for HDR shadow/highlight, log-wheel nudges, skin
  saturation, and Color Warper hue shift, writing the same
  `advanced_color_toolset` payload used by preview/export. Render Queue has a
  Deliver Presets matrix and JSON copy action, Media Pool exposes selected/all
  ingest manifests plus proxy/checksum metadata, Mask Editor exports
  B-spline/clean-plate/planar-tracker repair payloads, QA Dashboard surfaces
  Resolve parity top actions, and presets can report semantic A/B preview
  storyboards with bake targets.
- **Professional workflow polish layer** — Advanced Color now has a split
  before/after preview, Hue/Sat mini curve, Color Warper mini grid,
  bypass/solo/reset controls, and a scroll-safe qualifier panel. Audio Mixer
  exposes Routing/Loudness dialogs over its Fairlight-style payloads, Render
  Queue can summarize Deliver presets for QA/status surfaces, Media Pool can
  generate scoped proxy/relink health reports, and Mask Editor shows a
  clean-plate/planar-tracker repair summary while editing.
- **CapCut/local ML gates reopened** — CapCut-style creator features and
  local-only ML are enabled by default again after the launcher flicker fix.
  They still remain controllable with diagnostic off switches such as
  `TIGERCAPTURE_CAPCUT_DISABLED=1` and `TIGERCAPTURE_LOCAL_ML_DISABLED=1`.
- **Voice Lab sidecar readiness** — Voice Lab now has an optional local
  Style-Bert-VITS2 sidecar path for subtitle-to-voice generation, prefers the
  user's `zoe` model when available, exposes a Model Maker bridge for local
  voice models, and has QA Dashboard preflight coverage that can auto-start the
  sidecar for project evaluation sessions.
- **Voicebox TTS provider** — Added Voicebox (jamiepine/voicebox) as an optional
  local TTS sidecar provider — supports multiple engines (Qwen3-TTS, LuxTTS,
  Chatterbox, HumeAI TADA, Kokoro) through its own voice-profile system. New
  module `app/tts_voicebox.py`, install script `tools/install_voicebox.py`,
  wired into `app/tts_setup.py`, `app/tts_lab.py`, and
  `app/tts_subtitle_workflow.py`.

### UX

- **Launcher workspace switch** — Replaced the visible Full/Simple button pair
  with a draggable iOS-style Normal/Simple slide toggle, persist the user's
  chosen workspace mode, widened the launcher, wrapped the launcher body in a
  scroll area, and shortened the cursor option label so the startup screen no
  longer clips its editor/capture controls.
- **Launcher state and QA cleanup** — Corrupt launcher workspace state is now
  backed up and repaired to the normal editor mode, startup crash reports ignore
  malformed/stale payloads, Screen Studio GUI-flow QA now enforces the
  no-template-first launcher, and real-recording corpus reports expose
  click/drag/hotkey/auto-zoom readiness instead of only counting files.
- **Screen Studio parity contracts closed** — Added reportable contracts for
  first-run/empty-project focus, real-recording motion tuning, viewer-based
  manual zoom handles, vertical/social export, GIF/WebM/4K60 handoff polish,
  audio/subtitle timing, golden short-video baselines, real-project corpus
  artifacts, and separation of advanced TigerCapture tools from the simple path.
- **Screen Studio productization workbench** — Added an actionable real
  recording intake board, manifest-based recording registration CLI, adaptive
  cursor/zoom tuning patch, manual-zoom viewer command model, preview/export
  parity matrix, and regression hardening plan. QA Dashboard now exposes the
  combined Screen Studio Productization report.
- **Effect Presets are now clickable** — Left-dock effect preset cards now
  apply to the selected/current video clip on click while preserving drag-to-clip
  behavior for precise targeting, with clearer target feedback when no clip is
  available.
- **Effect preset drop targeting is visible** — Dragging an Effect Preset over
  the timeline now highlights the exact target clip with a bright FX outline and
  preset label, then shows the normal FX badge/burst after the drop so users can
  see where the preset landed.
- **Applied preset regions are visible** — Effect presets now preserve their
  preset metadata on `VideoFilterParams`, and timeline clips paint
  human-readable FX/KEY/AI/TR/COL strips inside the clip body in addition to the
  compact clickable badges. This makes applied effects and transitions read like
  editable regions rather than hidden clip properties.
- **Transition preset identity is preserved** — Transition drag/drop, click
  apply, keyboard insert, and context-menu insert now write
  `transition_preset_meta` onto clips, project save/load round-trips it, and
  timeline strips/tooltips prefer the real preset name while compacting to the
  tag on narrow clips.
- **Final product-readiness gate** — Added a consolidated eight-area release
  gate covering practical editing flow, real project corpus, preview/GPU
  performance, Color/Audio accuracy, timeline polish, preset/template quality,
  crash recovery/project repair, and packaging. The new
  `tools/qa_final_product_readiness.py` report is visible and runnable from QA
  Dashboard as `Final Product Readiness`, with `release_ready` kept separate
  from report-generation success so corpus/performance gaps stay visible.
- **Effect preset guidance is localized** — The new click/drag tooltips,
  timeline drop label, missing-preset warning, and no-target status text now use
  the existing six-language i18n tables instead of mixed Korean/English literals.
- **Video editor language switcher** — Added a compact globe menu to the video
  editor command bar. Picking a language saves it through the existing i18n
  settings path and immediately refreshes the main editor chrome, section
  headers, export controls, and localized effect-preset guidance.
- **Effect/transition preset expansion** — Added a Creator Effect/Transition
  Expansion pack with 10 practical clip effects and 10 drag-ready transitions
  for screen recordings, cursor tutorials, product demos, shorts, gameplay, and
  Live2D/Spine overlays. The new presets use the existing clip-filter and
  transition payloads, so they work through search, drag/drop, click apply, and
  preset QA instead of being static browser cards.

### Fixes

- **Launcher to video editor flicker** — Fixed the Windows/Qt startup path
  where parentless widgets could briefly appear as small native TigerCapture
  windows while the editor tree was being assembled. Workbench, color/timeline,
  toolbar, preset browser, collapsible section, and Media Pool widgets now get
  explicit parents at construction time. Verified by visible-window traces with
  `Visible console-like rows: 0` and confirmed in a real user run on 2026-06-22.
- **Screen Studio cursor metadata fallback** — Preview and export effect
  snapshots now fall back from clip-level cursor/polish metadata to track-level
  metadata, so click/cursor animation still appears when metadata was attached
  to the track rather than the clip.
- **Color tab black-frame recovery** — Color/Edit tab switches and Color Page
  grade refreshes keep the last good preview frame during short transition
  guards, while preserving legitimate large dark video frames outside the
  explicit recovery window.

## v1.4.2 - 2026-06-07

### Fixes

- **Reissued installer release** - Publishes the startup-crash hotfix from
  v1.4.1 under a clean tag so GitHub source/tag downloads point at the same
  fixed PyInstaller spec as the installer asset. This avoids the old
  ``pydoc`` / ``unittest`` exclusion mismatch.

## v1.4.1 — 2026-05-20

### Fixes

- **Startup crash on installed builds** — Setup-1.4.0.exe failed on
  launch with ``Unhandled exception: No module named 'pydoc'``. The
  PyInstaller spec excluded ``pydoc`` and ``unittest`` to shave a few
  MB off the bundle, but ``pyqtgraph`` (the audio-mixer scope) lazy-
  imports both modules. Removed those entries from ``excludes``;
  installer runs cleanly.

## v1.4.0 — 2026-04-27

### Pro video editor

- **Kinetic typography** — full 3-pane editor with 80+ animations
  (Basic / Kinetic / Folding / HOLD), 12 curated presets, multi-layer
  Eve glitch with RGB split, and animation composition: every IN /
  HOLD / OUT slot accepts a primary plus a list of "modifier" extras
  that stack (offsets/rotations add, scale/opacity multiply)
- **3-wheel color grading** — DaVinci-style Shadows / Midtones /
  Highlights chromaticity wheels with luma-aware tonal masks; bipolar
  Brightness / Contrast / Saturation knobs that match the sound editor
- **8 colour presets** — Cinematic, Vintage, Cool, Warm, Faded, B&W,
  Punch, Mute (designed looks gated as Pro)

### Sound editor

- **AI Master tab** — one-click fixes for Suno v3/v4, Udio, ACE-Step
  artefacts, plus a generic and a Custom slot. 6-knob Detailed
  Mastering (Air, Clarity, Warmth, Width, Punch, Excite)
- **Dynamics tab** — Compressor (Threshold / Ratio / Attack / Release
  / Makeup / Knee with Voice Gentle / Voice Strong / Podcast presets)
  and Noise Gate
- Audio export: 6 formats (MP3, WAV; FLAC, ALAC, AAC, OGG Pro) with
  4 quality presets (Low / Standard / High / Studio)

### Export

- Quality dropdown (Low / Standard / High / Best) and Format dropdown
  (MP4 / WebM / MOV) on the editor toolbar
- WebM (VP9 + Opus) and MOV (H.264-in-MOV) Pro-tier
- Save dialog filter and file extension switch with the format

### Tier system

- New `app/tier.py` — single source of truth for Pro/Free gating
- Pro features: high/best video quality, WebM/MOV containers, lossless
  audio formats, 48/96 kHz audio, designed colour presets, typography
  in export
- Free users see PRO-badged items + an upsell modal on click

### Localization

- Two new locales: 中文 (Chinese), Français (French) — total 6
  (한국어, English, 日本語, 中文, Français, Deutsch)

## v1.3.x — macOS port (experimental)

### macOS port

- New `mac/` overlay package — ScreenCaptureKit-based recorder,
  NSWorkspace foreground tracker, CGEventPost ⌘V paste, Finder reveal
  helpers. Shared cross-platform UI (editors, subtitles, i18n) runs
  unchanged via a namespace-package overlay.
- Preemptive fixes for first-build footguns: `ApplicationServices`
  import path (not `HIServices`), `Quartz`-umbrella import for
  CoreVideo/CoreGraphics, pyobjc hiddenimports in the PyInstaller
  spec, CVPixelBuffer pointer-cast + CIImage fallback, SCContentFilter
  constructor fallback.
- `mac/build.sh` → `.app` + `.dmg`, ad-hoc signed; `mac/README-mac.md`
  for Remote-SSH workflow and Gatekeeper workaround.
- GitHub Actions `.github/workflows/macos.yml` — Apple Silicon runner
  auto-builds on every `main` push and publishes a prerelease
  GitHub Release (`TigerCapture-<ver>-mac.dmg`) for every `v*-mac*` tag.
- Landing README adds an **experimental, unverified** macOS section
  pointing at the prerelease build and the `mac/` sources.

### Video editor — audio tracks (new)

- Multi-clip model: **`AudioTrack`** is now a lane that owns a list of
  **`AudioClip`** s. Each clip carries its own source / offset / trim /
  fades / cuts / waveform. Splitting a clip produces two clips on the
  same lane instead of two separate rows (DAW / NLE convention).
- Drag-drop support at the window level AND per-row:
  - drop a video on an empty video row → fill it
  - drop audio on an empty audio row → fill it
  - drop audio on a loaded audio row → append a new clip at the tail
  - drop mismatched types → spawn the right kind of track
- **Waveform** — background ffmpeg extractor decodes audio → ~40 Hz
  peak buckets → painted inside each clip bar with gamma shaping.
  Clips split on the same source share peaks (no re-decode).
- **Cut = split** — select range on a clip + right-click "Cut
  selection" produces two independent clips on the same lane with a
  real gap at the cut position (pieces stay at their original
  timeline positions; user drags them to reposition).
- **Fade actors** — drag the existing orange **Fade** card from the
  toolbar onto an audio clip to place a `FadeSegment`. Edges are
  resizable, double-click or right-click → Delete, right-click →
  kind (In / Out / Both).
- **Per-clip right-click menu**: cut selection, clear cuts, trim
  range, delete just this clip (vs. delete the whole track).
- **Volume slider** per track (master) in the row header.

### Video editor — selection & playhead

- **Mark In / Mark Out** buttons next to the play button with `I` / `O`
  keyboard shortcuts (Premiere-style). Sets selection from the
  current playhead on the active track (video or audio). `X` clears
  all selections. Shift+drag still works as a bonus path.

### Video editor — preview

- **Pop-out preview**: ⛶ icon inside the PREVIEW section header
  spawns a borderless mirror window that can be dragged to a second
  monitor and full-screened with F11. Original preview + editing UI
  keep working — pop-out is view-only.
- **🎵 Sound only** placeholder in the preview area when no video
  track has a source but audio does; player ticks still drive audio
  mixing, so preview playback works audio-only.
- **Delete track** on the only remaining video track is now allowed
  when audio tracks exist (project isn't empty).

### Video editor — sound editor (rebuilt, knob-based)

- Reusable `KnobWidget` (`app/knob_widget.py`) — 270° arc + gradient
  body + value indicator, painted via `QPainter`. Inputs: vertical
  drag (100 px = full range), wheel, `Shift` 10× / `Ctrl` 100×
  precision, double-click reset, right-click direct numeric entry.
  Color variants (blue / green / orange / custom), bipolar mode
  (Pan), logarithmic scale (Hz), custom formatter callbacks
  (dB / Pan / sec / Hz / semitones / speed).
- `SoundEditorWindow` rebuilt as a tabbed editor: TitleBar /
  FileInfo / Waveform / TabBar (Basic / EQ / Dynamics / Effects /
  Advanced — Basic live, others placeholders) / Transport.
- Basic tab: 6 knobs (Volume / Pan / Fade In / Fade Out / Speed /
  Pitch), Mute + Reverse toggles, "Reset All", 4 built-in presets
  (Voice Recording / Background Music / Game Audio / Podcast).
  Volume + Speed knobs feed the local QMediaPlayer in real time so
  the user hears the change while adjusting; Pan / Fade / Pitch
  land in the FFmpeg export chain.
- Interactive waveform: click = scrub the playhead, drag or
  Shift+drag = range selection, double-click = clear selection.
  Right-click on a marker deletes it.
- Transport bar: ⏮ / ▶ ⏸ / ⏭ / 📌 add-marker / 🔁 loop-selection.
  Keyboard: `Space` play, `M` marker, `L` loop, `,` `.` prev / next
  marker.
- Markers live on `clip._se_markers` (source-ms list); the waveform
  draws them as green triangle flags with dashed guide lines.
- When the waveform extractor finishes after the editor was opened,
  the in-editor view refreshes via a back-channel from
  `_on_waveform_ready`.

### Video editor — "extract audio from video"

- Right-click a video track → **🎵 영상에서 사운드 추출**. Creates a
  new audio track whose single clip references the video file
  directly (FFmpeg + QMediaPlayer both decode audio from mp4). Rejects
  audio-less videos with a clear dialog.

### Export

- Audio routing reworked: when any audio track is loaded, external
  audio supplants the source video's audio (via amix of per-clip
  `atrim + adelay + volume + afade` chains). When no audio tracks
  exist, the source video's audio stream passes through unchanged
  (`-map 0:a?`) instead of being silently dropped.
- Per-clip cuts / fades / volume fold into the filter chain, joined
  per track and across tracks with `amix=normalize=0`.

### UI polish

- Default dark-theme styling for all **dialog buttons**
  (`QMessageBox`, `QInputDialog`, `QFileDialog`, `QDialogButtonBox`) —
  non-default (Cancel etc.) now #4e4e56 bg with #7a7a84 border for
  strong contrast against the dialog body; default (OK) stays blue.
- **Capture-result z-order**: main window is re-shown *before*
  `ScreenshotWindow` / GIF / Video editor windows so the editor
  actually lands on top after its own raise/activate, instead of
  being buried behind the main TigerCapture window.

### Diagnostics

- `logs/tigercapture.log` — every session mirrors stderr to this file with
  a timestamp header. `faulthandler` writes native-crash tracebacks
  there too, and a `sys.excepthook` records unhandled Python
  exceptions. Makes post-mortem on background-run sessions tractable.

## v1.3.0 — 2026-04-21 (last Windows release)

Dark redesign, fade actors, speech bubbles, multi-monitor capture
fix. See the Windows release notes on GitHub.
