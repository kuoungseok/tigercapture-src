# Changelog

Format: grouped by area, newest work at the top of each section.

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
