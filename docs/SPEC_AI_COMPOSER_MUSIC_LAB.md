# AI Composer / Music Lab Spec

## Purpose

Music Lab turns a natural-language request into editable background music for a
TigerCapture timeline. Internally, the app creates structured sections, chord
progressions, and note events, but the basic user-facing output is rendered
audio: sample/SoundFont-based stems and a mix placed onto normal audio tracks.

The goal is not to replace Cubase, Logic, or FL Studio. The goal is a
creator-video music workbench where local AI can compose, revise, render, and
mix simple background music without leaving TigerCapture.

## Product Scope

MVP:

- Prompt to composition: genre, mood, BPM, key, sections, chords, tracks.
- Generated parts use a 9-channel default baseline: drums, bass, bass pulse,
  chords/pad, arp, melody/lead, answer lead, counter melody, and FX.
- Melodic EDM/NCS-style prompts use that same 9-channel layout with EDM-tuned
  labels, balances, and layer behavior so the result is not a static four-track
  loop.
- Chord progressions are key-aware. For example, `A minor` EDM uses
  `Am-F-C-G` rather than a hard-coded `Am-Ab-Eb-Bb` progression.
- Orchestral/symphonic/trailer-score prompts generate 128 internal tracks,
  split across strings divisi, woodwinds, brass, timpani, percussion, cymbal/FX,
  choir, and hybrid pads.
- Section structure: intro, build, main, outro.
- MIDI-like internal note model.
- Preview WAV render from the internal note model.
- Render stems into timeline `AudioTrack` lanes.
- Update/replace existing Music Lab timeline stems instead of stacking duplicate
  tracks when `update_existing` is true.
- Standard MIDI export for the current composition.
- Compact Workbench Sound Editor `Music Lab` tab for prompt, genre/mood,
  duration, BPM, key, render mode, preview playback, timeline update, and MIDI
  export.
- Composition-aware arrange preview: the tab reads real `MusicComposition`
  sections/tracks/clips, shows selectable section blocks, chord progression,
  note counts, and selected-note previews.
- Selected section editing from the UI: regenerate selected section and resize
  section length, then update existing timeline stems.
- AI-readable and AI-editable action surface.

Not MVP:

- Full DAW parity.
- Piano-roll UI.
- VST/plugin hosting.
- Vocal generation or voice cloning.
- Cloud music-provider dependency.

## User Scenario

1. User imports a video.
2. User asks: "Make a 30 second cinematic tech demo BGM."
3. The AI command router emits `music.compose_to_timeline` for clear music
   generation prompts.
4. `music.compose` creates a composition with BPM, key, sections, tracks, and
   notes.
5. `music.render.preview` writes a local WAV preview mix. For listening-only
   previews, callers should pass `render_stems=false` so `_bass.wav`,
   `_drums.wav`, and other role stem files are not generated.
6. `music.render_to_timeline` places those stems onto audio tracks.
7. `music.mixer.auto_balance` sets initial music-track volume and pan.
8. User can open the Workbench Sound Editor `Music Lab` tab and generate,
   preview the generated mix, update existing timeline stems, or export MIDI
   without knowing action IDs.
9. The tab displays the real generated composition as an arranger, not a static
   mockup. Selecting a block exposes its role, section, chords, duration, and
   MIDI-note summary.
10. User or AI can regenerate a section, resize a section, mute/unmute music
    stems, export MIDI, or edit notes through MIDI actions.

## Data Model

```text
MusicComposition
- id
- prompt
- genre
- mood
- bpm
- key
- duration_ms
- ticks_per_beat
- sections[]
- tracks[]
- rendered_stems{}

MusicSection
- name
- start_ms
- duration_ms
- intensity
- chord_progression[]

MusicTrack
- id
- role: drums | bass | chords | melody | fx, or an orchestral unique role such
  as violins_i_001, cellos_004, horns_003, flutes_001, timpani_002,
  orchestral_percussion_007, choir_005, or hybrid_pad_001
- instrument
- volume
- pan
- clips[]

MidiClip
- id
- section_name
- start_ms
- duration_ms
- notes[]

MidiNote
- pitch
- start_tick
- duration_tick
- velocity
```

Rendered stems are normal WAV files and are linked to the existing
`AudioTrack`/`AudioClip` system. That keeps preview, export, mixer automation,
and AI audio actions aligned with the rest of the editor.

Project persistence:

- `.tgp` saves `music_compositions[]` with the full structured composition.
- Music-generated `AudioTrack` rows save `music_composition_id` and
  `music_role`.
- Music-generated `AudioClip` rows save the same composition/role metadata so
  the relationship survives project reloads even though rendered WAV stems are
  normal external media files.

## Action Surface

Implemented MVP actions:

```text
music.compose
music.arrange.create
music.section.set
music.track.create
music.track.set_instrument
midi.clip.create
midi.clip.write_notes
midi.clip.write_chords
midi.clip.quantize
music.render.preview
music.export_midi
music.render_to_timeline
music.compose_to_timeline
music.regenerate_section
music.mixer.auto_balance
music.state
```

The action surface is intentionally structured. AI should not write arbitrary
files or run arbitrary Python; it should call these actions and receive an
inspectable composition state.

AI command routing:

- "make a 30s BGM" routes to `music.compose_to_timeline` with
  `backend=sample_production` and `sample_library_policy=auto` by default.
  This is the normal "the user asked AI to compose music" path: use
  user-installed sample libraries when available, fall back clearly when they
  are not, apply the default studio master chain, and avoid silently producing
  the cheaper internal synth route.
- Explicit renderer phrases override that default. For example, "Stable Audio
  3.0" routes to `backend=production`, `ai_provider=stable_audio_3`, and
  `create_mix=true`; "ACE-Step" routes to `ai_provider=acestep_api`; "LMMS"
  routes to `ai_provider=lmms`; "internal synth/no samples/diagnostic synth"
  routes to `backend=sample_production`,
  `sample_library_policy=procedural_only` as a diagnostic comparison only; and
  "sample kit first" routes to `sample_library_policy=sample_kit_first`.
- "make the main music section stronger" routes to
  `music.regenerate_section` + `music.render_to_timeline(update_existing)` +
  `music.mixer.auto_balance`, carrying the existing composition's render
  backend and `sample_library_policy` so follow-up AI edits do not regress to a
  lower-quality renderer.
- "make the selected music section stronger" uses
  `snapshot.music_lab_selection.section_name` from the Workbench arranger.
- "mute selected music track" uses `snapshot.music_lab_selection.role` and
  emits `audio.track.mute` for the matching Music Lab stem track.
- `build_project_snapshot_from_editor` exposes `music_lab_selection` with
  `composition_id`, `role`, `section_name`, section timing, chords, note count,
  and note preview so Claude/local AI can reason about the selected block.

## Rendering Strategy

Product renderer tiers:

- Basic/default output is sample/SoundFont-based rendering:
  `backend=sample_production`, `sample_library_policy=auto`, and
  `tigerstudio.sample_production.v1`. This is the normal path for user-facing
  Music Lab previews, timeline stems, and natural-language "compose music"
  requests. It includes the default studio master profile
  `one_click_sample_production_studio_v1`: bus tone shaping, rumble/mud
  control, presence/air enhancement, room ambience, mid-side width, parallel
  glue compression, short dropout/surge repair, sample-jump smoothing, and a
  soft preview limiter. It also applies the default performance profile
  `sample_production_articulation_expression_v1`: role/length-based
  articulation classification, short-note gate shaping, velocity/expression
  contouring, MIDI CC1/CC11 automation for SoundFont renderers, and matching
  internal fallback envelope shaping.
- Advanced output is AI/production rendering: explicit provider choices such as
  Stable Audio 3.0, ACE-Step, or LMMS route to `backend=production` with
  `ai_provider` and `create_mix=true`. AI must not be silently selected merely
  because a provider is configured.
- MIDI/clip data is an internal arrangement representation and an optional
  export format. Product sound tuning is judged from rendered audio, not from
  MIDI files.

The MVP renderer is intentionally simple and local:

- drums: synthesized kick, snare, and hat transients
- bass: low sine/soft-square style notes
- chords/pad: quiet layered tones
- melody: short lead tones
- fx: section impact/rise hints
- v2 polish: detuned pads, softened bass harmonics, vibrato lead tones,
  lightweight stereo width, and soft limiting before WAV write
- v3 polish: sharper but restrained drum transients, short room/early tail,
  slightly wider stem polish, and a final soft limiter
- v4 video-BGM polish: 44.1 kHz WAV render, softer pad/lead envelopes, less
  angular bass harmonics, smoothed noise transients, and longer musical release
  tails to avoid old GM/chiptune-style preview playback.
- v5 arrangement/mix polish: wider pad voicings, less repetitive bass and
  melody phrasing, deterministic micro timing/velocity humanization, per-stem
  tone shaping, and master glue/soft limiting so the preview reads more like a
  video BGM bed than raw MIDI playback.
- Orchestral 128-track mode: explicit orchestral prompts use 128 unique
  `MusicTrack` rows. The local renderer maps role prefixes to families
  (strings, brass, woodwinds, timpani, percussion, choir, hybrid pad) so the
  result is not the old four-track sketch repeated many times.
- Melodic EDM/NCS-style mode: explicit EDM/NCS/electronic prompts add
  `bass_pulse`, `arp`, `lead_answer`, and `counter` layers on top of the
  9-channel default. These layers use different note patterns from the main
  bass/lead so preview mixes feel like an arranged cue rather than a repeated
  loop.
- EDM/NCS durations above 32 seconds use a song-form section plan:
  `intro`, `build`, `drop_1`, `breakdown`, and `drop_2_outro`. The breakdown
  and second drop use alternate chord progressions, so the cue changes harmonic
  direction instead of repeating one loop.
- Render path: `music.render.preview`, `music.render_to_timeline`, and
  `music.compose_to_timeline` accept
  `backend=auto|production|local_synth|studio_edm|soundfont|sample_production`
  plus optional `soundfont_path`, `drum_kit_path`, and
  `sample_library_policy=auto|sample_kit_first|soundfont_only|procedural_only`.
- Quality tiers are explicit and machine-readable:
  `tigerstudio.local_synth.v5` is `diagnostic_only`;
  `tigerstudio.studio_edm.v1` is `draft_sketch`;
  `tigerstudio.sample_production.v1` is `enhanced_local_preview`;
  `fluidsynth.soundfont.v1` is `starter_preview`;
  `production.external_music_renderer.v1` is the only
  `production_candidate` tier.
- Modern release-quality music must not be claimed from built-in renderers.
  The current built-in paths are useful for timing, arrangement, MIDI export,
  and timeline workflow validation. They are not a replacement for a
  sample/model/DAW-grade production music engine.
- `auto` uses `backend=sample_production`. It must not jump to AI/production
  rendering automatically, even when a production renderer is configured.
  Explicit `backend=soundfont` uses FluidSynth + SoundFont directly when both
  are available. `tigerstudio.local_synth.v5` remains available only as an
  explicit diagnostic renderer; it is not a useful music-output path.
- `fluidsynth.soundfont.v1` enables FluidSynth reverb/chorus and runs a light
  studio-polish mix pass after rendering: stereo width, room/tail ambience,
  gentle parallel compression, soft smoothing, and final preview normalization.
  This improves raw MIDI playback, but it is still a starter preview, not a
  production-quality modern music result.
- EDM/NCS/electronic prompts can use `tigerstudio.studio_edm.v1` only when
  explicitly requested through `backend=studio_edm` or `backend=draft_synth`.
  This path does not rely on General MIDI instruments, but it is still a draft
  synth renderer for arrangement inspection.
- Non-AI sample-production preview: `backend=sample_production` routes to
  `tigerstudio.sample_production.v1`. It renders Music Lab tracks into grouped
  bus stems (`percussion`, `low`, `orchestra`, `pads`, `lead`, `fx`), applies
  bus-specific tone shaping, cinematic room/delay, stereo width, non-rhythmic
  stealth ambience for tactical/covert prompts, short energy-dip repair,
  sample-jump smoothing, low-resonance taming, narrow tonal-whine suppression,
  tight sample-production timing, note-edge de-click ramps, short-surge
  limiting, low-end continuity-safe bass phrasing, and a glue/limiter master. It is meant
  to narrow the gap between raw MIDI/SoundFont previews and AI audio, but it is
  still not a replacement for real DAW-grade sample libraries or AI generation.
  Percussion quality is treated separately because synthesized kick/snare/hat
  transients can sound like old FM/GM preview drums. Sample-production now uses
  a sample-library-first policy: the percussion bus tries a durable local
  SFZ/DecentSampler/`tigercapture_drumkit.json` kit from
  `external/assets/music/drum_kits`, then SoundFont/FluidSynth, then procedural
  synth/noise fallback. Non-percussion buses (`low`, `orchestra`, `pads`,
  `lead`, `fx`) also try external SoundFont/FluidSynth stem rendering before
  procedural synthesis, which reduces the overall "calculated preview" sound.
  Backend status exposes `drum_sample_kit_ready`, `drum_sample_kits`,
  `sample_production_percussion`, and `sample_production_bus_policy`; each
  sample-production render records `sample_library_policy`, `bus_renderers`,
  `external_bus_count`, `procedural_buses`, `percussion_source`, and
  `percussion_renderer` metadata so AI/review automation can explain which
  parts were sample-based and which were fallback synthesis.
  Render metadata also records `studio_mastering.enabled=true`,
  `studio_mastering.profile=one_click_sample_production_studio_v1`, and the
  chain applied to the preview mix/stems so one-click AI music requests are
  auditable as mastered sample renders rather than raw MIDI/SoundFont output.
  Render metadata also records `performance_profile.enabled=true`,
  `performance_profile.profile=sample_production_articulation_expression_v1`,
  note/articulation counts, MIDI CC support, gate shaping, and internal fallback
  envelope shaping so Claude/local AI can explain why the output is not a raw
  note dump.
  `sample_library_policy` is user/AI selectable: `auto` and
  `sample_kit_first` try user-installed drum kits before SoundFont and internal
  fallback, `soundfont_only` skips drum-kit files and renders through
  FluidSynth/SoundFont when possible, and `procedural_only` disables external
  sample assets for a diagnostic synth comparison render.
  Metal test arrangements may use `rhythm_guitar_*`, `lead_guitar_*`,
  `power_chord_guitar_*`, and `palm_mute_guitar_*` roles; these map to the
  sample-production `lead` bus and SoundFont overdrive/distortion guitar
  programs so speed/power-metal sketches are not rendered as generic synths.
- Audio glitch diagnosis: use `tools/music_audio_glitch_probe.py` for
  non-destructive analysis before changing render code. The probe reports
  sample jumps, 10/25/50 ms frame drops/surges, spectral wobble candidates, and
  separate hard-glitch, spectral-motion, and envelope-pumping diagnostics, can
  write a JSON report/CSV event list, and can write a conservative repaired WAV.
  `glitch_score` tracks hard discontinuities and short frame defects;
  `spectral_wobble` is a candidate list only because musical bass/chord changes
  can look like dominant-frequency movement. `envelope_pumping` must be checked
  with `--bpm` when the user hears "huffing" or "훅 훅": high beat-rate
  peak-to-peak dB usually means kick/percussion or sidechain-style gain motion is
  dominating the mix even when `glitch_score` is zero. Reports and repaired
  scratch WAVs belong under `debugCapture`; they are reproducible diagnostics,
  not durable assets. Recent Music Lab work found that perceived "tape chewing"
  and "huffing" came from different causes: tape-like ticks concentrated in
  low/bass continuity and short percussion/mix frame dropouts, while huffing came
  from 128 BPM beat-rate envelope motion in the percussion/kick bus. Fixes
  should start with bass note continuity, bass tail length, pulse-layer
  intensity, final-mix micro-dropout repair, and percussion/kick envelope balance
  before adding broad master processing.
- Stage-by-stage elimination: when the user still hears cutting, huffing, or
  unexplained artifacts after the normal probe, run
  `tools/music_render_stage_probe.py`. It renders the same composition as
  `00_dry_note_mix`, `01_shaped_stem_mix`,
  `02_bus_polish_no_spatial_mix`, `03_bus_spatial_gain_mix`,
  `04_master_no_micro_mix`, and `05_master_full_mix`, with a JSON probe report
  for each. This is the preferred way to find whether the artifact starts in
  the raw note oscillator, stem shaping, bus polish, spatial/bus gain, master,
  or micro-repair stage. The same tool also writes `dry_no_drums_mix` and
  `dry_drums_only_mix`; if dry glitches disappear without drums, continue inside
  the drum oscillator/pattern instead of changing broad mix/master effects.
  Each stage also writes a `*_playback_safe_48k.wav` companion for human
  listening: it is 48 kHz and peak-normalized to about 0.45. Do not add warm-up
  beds or synthetic pre-roll to these files because that can introduce a new
  audible transition that is not present in the measured stage WAV. Do not add
  noise floors, silence padding, crossfaded warm-up sections, or other
  "player-stability" audio either; playback-safe must stay a transparent
  delivery variant of the measured render. Use the normal stage WAV/report for
  measurement and the playback-safe file for listening checks.
  2026-07-10 regression note: `playback_safe_v4` added a warm-up bed to a clean
  no-drums render and created a false audible cut. The corrected v5 companion,
  made with only 48 kHz conversion and peak normalization, did not cut. If this
  symptom returns, audit `_playback_safe_samples()` /
  `tools/music_render_stage_probe.py` before changing composer, drum, bass, or
  master code.
- Production renderer contract: a durable external renderer can be configured
  through `external/tools/music_renderer/renderer.json` or
  `TIGERCAPTURE_MUSIC_PRODUCTION_RENDERER_EXE`. It must accept
  `--composition-json` and `--output-wav` and write a stereo WAV mix. If
  `backend=production` is requested without that renderer, the action must fail
  loudly instead of silently producing draft/starter audio.
- Current local production renderer: `tools/lmms_music_renderer.py` is wired by
  the production router as an offline fallback. It converts a Music Lab
  composition JSON request into a temporary LMMS `.mmp` project and renders it
  with `external/tools/lmms/app/lmms.exe render`. LMMS mix rendering is enabled;
  stem rendering remains false until the wrapper maps Music Lab roles to LMMS
  `rendertracks` output reliably.
- Current AI production router: `tools/music_production_renderer.py` is wired by
  `external/tools/music_renderer/renderer.json`. It reads
  `external/tools/music_renderer/provider.json`, tries configured AI providers,
  writes a renderer sidecar JSON next to the output WAV, and falls back to LMMS
  when AI generation is unavailable.
- ACE-Step 1.5 provider: `acestep_api` is the first implemented AI provider.
  It uses the documented async HTTP flow: `/health`, `POST /release_task`,
  `POST /query_result`, and `GET /v1/audio`. The router builds a prompt from
  Music Lab prompt/genre/mood/BPM/key/sections/chords/track roles, submits
  `audio_duration`, `bpm`, `key_scale`, `time_signature`, `thinking`, model,
  and inference settings, then downloads the generated WAV. If the local
  ACE-Step API server is not healthy, the router falls back to LMMS unless
  strict mode is enabled.
- Stable Audio 3.0 provider: `stable_audio_3` is implemented as an optional
  Hugging Face Space provider. The router calls the `stabilityai/stable-audio-3`
  Space through `gradio_client`, using the `small-music` variant by default,
  and copies the returned WAV into the normal production renderer output path.
  It is disabled by default because prompts/audio requests leave the local
  machine; set `TIGERCAPTURE_MUSIC_AI_PROVIDER=stable_audio_3` or enable the
  provider explicitly when the user chooses that cloud path.
- Stable Audio 3.0 local/open-weight slot: Stability
  describes Stable Audio 3.0 Small/Medium as open-weight, fully licensed-data
  models with output ownership/commercialization under the Community License
  for eligible users. A local/API wrapper can be added once the installed
  inference contract is selected.
- MusicGen/AudioCraft provider slot: reserved as a reference/experimental
  provider. Its model docs remain useful for comparison, but GPU and license
  checks must pass before it can be a default production path.
- The Windows development setup may keep FluidSynth under
  `external/tools/fluidsynth` and GeneralUser GS under
  `external/assets/music/soundfonts`. These are durable external assets/tools,
  not `debugCapture` scratch files.
- Mix-only preview: `music.render.preview(render_stems=false)` writes only the
  final preview mix WAV and leaves `rendered_stems` empty. Workbench Music Lab
  Preview uses this path. Timeline insertion keeps `render_stems=true` unless
  it is inserting the single mix as a clip.
- Composer Master FX: Composer does not own a separate audio-effect engine.
  Its `Master FX` card reuses Sound Editor state (`AudioClip.effects`) and
  emits `music.apply_master_fx`, which applies AI Master, space/reverb, and
  loudness payloads to the rendered Music Mix or matching stem clips. MIDI/note
  generation remains upstream of this step; Sound Editor effects are applied to
  rendered audio clips and final export uses the same audio effect chain.

Output:

- one WAV stem per music track when `render_stems=true`
- one summed preview mix WAV

Playback rule:

- Music Lab `Preview` plays the rendered WAV preview mix inside the embedded
  Video Editor Lab.
- MIDI export remains a data interchange format for DAWs. If a user opens the
  `.mid` directly in an OS/player with a weak General MIDI synth, that external
  player can sound cheap; product playback quality should be judged through the
  rendered WAV preview/stems.

Durable asset/tool locations:

- Put `.sf2`, `.sf3`, or `.sfz` files in
  `external/assets/music/soundfonts`.
- Optional FluidSynth binaries belong in `external/tools/fluidsynth` or PATH.
- Optional production music renderer binaries or SDK wrappers belong under
  `external/tools/music_renderer`; licensed sample packs and models belong
  under `external/assets/music`, never in `debugCapture`.
- SFZ/DecentSampler/DrumGizmo-style drum kits belong under
  `external/assets/music/drum_kits`; never place sample packs in `debugCapture`.
  Local development can use AVL Drumkits as an ignored external asset under
  `external/assets/music/drum_kits/avl-drumkits`. The kit is not source code and
  should stay out of commits except for project documentation and local license
  files retained beside the asset.
- GeneralUser GS can be used as the small default GM/GS SoundFont for local
  development. Keep its license text next to the `.sf2` file.
- Environment overrides:
  `TIGERCAPTURE_MUSIC_SOUNDFONT_DIR`, `TIGERCAPTURE_FLUIDSYNTH_EXE`,
  `TIGERCAPTURE_MUSIC_PRODUCTION_RENDERER_EXE`, and
  `TIGERCAPTURE_MUSIC_PRODUCTION_RENDERER_ARGS`.
- `debugCapture` may contain regenerated proof renders only; never store
  durable SoundFonts, sample packs, or installed synth tools there.
- Music sample packs are not bundled with TigerCapture. The product exposes a
  connection/install surface instead: `external/assets/music/README.md` is the
  local guide, `music.render.backends` reports install directories, discovered
  assets, sample-policy choices, and recommended external libraries, and the
  Workbench Music Lab UI provides `Assets` / `Guide` buttons for opening the
  user-managed asset folder and guide.

Backend status action:

```text
music.render.backends
```

This returns the preferred backend, production renderer readiness, quality
tiers, discovered SoundFonts, drum sample kits, sample-library install folders,
recommended external libraries, FluidSynth path, and warnings explaining why the
system is falling back to starter/draft renderers.

The default output location is:

```text
%USERPROFILE%\Videos\TigerCapture\Music Lab Renders
```

Tests and automation may override the output directory.

## UX Direction

The current compact Music Lab UI lives in the Workbench Sound Editor tab:

- Prompt field.
- Genre, mood, duration, BPM, key, and stem/mix render mode.
- Generate to timeline, update existing timeline music tracks, and MIDI export
  buttons.
- Preview/Stop buttons that play the generated preview mix inside the embedded
  Video Editor Music Lab. If no preview mix exists yet, Preview requests
  `music.render.preview(render_stems=false)` instead of sending the user to an
  external player or writing unnecessary stem WAVs.
- Renderer selector: `sample prod`, `production`, `soundfont`, `studio EDM`,
  `auto renderer`, or `diagnostic synth`. `sample prod` is the normal default.
- Sample library selector: `auto samples`, `sample kit first`,
  `soundfont only`, or `diagnostic synth`. This controls how
  `backend=sample_production` uses user-installed libraries. The tab also shows
  discovered drum-kit/SoundFont counts and exposes `Assets` / `Guide` buttons
  so users can download libraries themselves, place them in the external asset
  folders, and reconnect without bundling those libraries in the application.
- AI provider selector: `AI auto`, `Stable Audio 3.0`, `ACE-Step`, or
  `LMMS offline`. Explicit AI provider choices set `backend=production`, pass
  `ai_provider` through the action layer, and force `mix only` because the
  current production bridge returns a finished stereo WAV rather than editable
  stems. `Stable Audio 3.0` is labeled as an external Space path; `ACE-Step`
  as a local/API server path; `LMMS offline` as the local fallback.

Future deeper Music Lab UI can expand into a detachable dock:

- Prompt row: genre, mood, BPM, key, duration.
- Arrange lane: intro/build/main/outro sections.
- Chord lane: chord progression per section.
- Track lanes: default drums/bass/chords/melody/fx roles, genre-specific
  roles such as guitar bands, swing sections, 808/trap layers, synthwave
  pulses, and ambient pads, plus grouped orchestral views for the 128-track
  score mode.
- Right panel: AI change list and regenerate controls.
- Bottom actions: Render Preview, Render to Timeline, Auto Balance.

The Cubase-style arrange reference is useful for density and color coding, but
TigerCapture should stay focused on creator-video music generation rather than
full DAW editing.

## Acceptance Criteria

- `music.compose` creates a valid composition with sections and at least four
  music tracks.
- Orchestral/symphonic/trailer-score prompts create exactly 128 internal music
  tracks with unique role ids and non-empty MIDI-note content.
- Paganini, caprice, classical variation, rondo, concerto, or solo-violin
  prompts use the dedicated classical variation planner from
  `docs/SPEC_CLASSICAL_VARIATION_COMPOSER.md` instead of the generic 128-track
  trailer plan. The solo violin must remain active in every section, and heavy
  climax roles such as brass, timpani, and cymbals must not play before the
  climax section.
- Clear lofi, rock/metal, jazz, hiphop/trap, synthwave, and ambient prompts use
  the dedicated genre planners from
  `docs/SPEC_GENRE_COMPOSER_PLANNERS.md`. These planners must replace both
  section names and track roles instead of relabeling the generic BGM sketch.
- Unmatched non-orchestral prompts create the 9-channel default baseline unless
  the user explicitly disables FX, in which case the same arrangement can render
  as eight channels.
- Melodic EDM/NCS-style prompts create all nine arranged layers including bass
  pulse, arp, answer lead, counter melody, and FX by default.
- Key-aware progression tests must keep common minor EDM requests such as
  `A minor` on natural progressions like `Am-F-C-G`, with alternate breakdown
  and second-drop progressions for longer cues.
- `music.render.preview` writes a non-empty preview mix WAV and, when
  `render_stems=false`, does not write per-role stem WAVs.
- Music/Composer UI default previews use `backend=sample_production` with
  `sample_library_policy=auto`. `tigerstudio.local_synth.v5` must stay explicit
  diagnostic-only and should not be the normal fallback for user-facing music.
- `music.render_to_timeline` creates audio tracks and clips from those stems.
- `music.render_to_timeline(update_existing=true)` refreshes matching
  composition/role tracks instead of adding duplicate music lanes.
- `music.compose_to_timeline` composes, renders, inserts, and balances in one
  action so natural-language command routing does not need cross-step variable
  substitution.
- `music.export_midi` writes a standard `.mid` file beginning with a valid MIDI
  header and includes the default performance profile metadata plus CC1/CC11
  expression automation for non-percussion tracks.
- `music.state` exposes compositions and rendered stem paths.
- MIDI edit actions can create clips, write notes/chords, and quantize notes.
- Project save/load preserves composition state and music track/clip links.
- Clear prompts such as "make a 30s BGM" route to Music Lab instead of Sound
  Editor mastering, and the generated plan must include
  `backend=sample_production` plus `sample_library_policy=auto` unless the
  user explicitly chooses a provider or comparison renderer.
- Melodic generation must be phrase-based, not a tiny motif loop. The local
  deterministic composer plans 8/16-bar phrases where possible and assigns
  A, A-prime, B, hook, or bridge labels by section. The lead melody keeps a
  phrase memory, scores candidate contours against recent phrases to avoid
  immediate repetition, resolves phrase endings to chord-tone cadences, and
  varies rhythm, register, and contour. `lead_answer` is call-and-response
  material and `counter` is sparse offbeat support; neither should simply
  duplicate the primary lead.
- Clear edit prompts such as "make the main music section stronger", "remove
  drums from the music", "pad only", and "export midi" route to structured
  Music Lab/audio actions.
- Selection-aware prompts such as "make the selected music section stronger" or
  "mute selected music track" use the active Music Lab arranger selection from
  the project snapshot.
- The compact Music Lab tab must draw the real generated composition and expose
  selected-section chord/note hints before a full piano-roll UI exists.
- Unit tests cover action registration, composition generation, rendering, and
  timeline placement.
