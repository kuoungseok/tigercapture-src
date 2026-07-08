# AI Composer / Music Lab Spec

## Purpose

Music Lab turns a natural-language request into editable background music for a
TigerCapture timeline. The first implementation is MIDI-first: the app creates
structured sections, chord progressions, MIDI-like notes, synthetic preview
stems, and then places those stems onto normal audio tracks.

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

- "make a 30s BGM" routes to `music.compose_to_timeline`.
- "make the main music section stronger" routes to
  `music.regenerate_section` + `music.render_to_timeline(update_existing)` +
  `music.mixer.auto_balance`.
- "make the selected music section stronger" uses
  `snapshot.music_lab_selection.section_name` from the Workbench arranger.
- "mute selected music track" uses `snapshot.music_lab_selection.role` and
  emits `audio.track.mute` for the matching Music Lab stem track.
- `build_project_snapshot_from_editor` exposes `music_lab_selection` with
  `composition_id`, `role`, `section_name`, section timing, chords, note count,
  and note preview so Claude/local AI can reason about the selected block.

## Rendering Strategy

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
  `backend=auto|production|local_synth|studio_edm|soundfont` plus optional
  `soundfont_path`.
- Quality tiers are explicit and machine-readable:
  `tigerstudio.local_synth.v5` and `tigerstudio.studio_edm.v1` are
  `draft_sketch`; `fluidsynth.soundfont.v1` is `starter_preview`;
  `production.external_music_renderer.v1` is the only
  `production_candidate` tier.
- Modern release-quality music must not be claimed from built-in renderers.
  The current built-in paths are useful for timing, arrangement, MIDI export,
  and timeline workflow validation. They are not a replacement for a
  sample/model/DAW-grade production music engine.
- `auto` uses a configured production renderer for mix-only preview when one
  is available. Otherwise it uses FluidSynth + SoundFont when both are
  available and falls back to `tigerstudio.local_synth.v5`.
- `fluidsynth.soundfont.v1` enables FluidSynth reverb/chorus and runs a light
  studio-polish mix pass after rendering: stereo width, room/tail ambience,
  gentle parallel compression, soft smoothing, and final preview normalization.
  This improves raw MIDI playback, but it is still a starter preview, not a
  production-quality modern music result.
- EDM/NCS/electronic prompts can use `tigerstudio.studio_edm.v1` only when
  explicitly requested through `backend=studio_edm` or `backend=draft_synth`.
  This path does not rely on General MIDI instruments, but it is still a draft
  synth renderer for arrangement inspection.
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
- GeneralUser GS can be used as the small default GM/GS SoundFont for local
  development. Keep its license text next to the `.sf2` file.
- Environment overrides:
  `TIGERCAPTURE_MUSIC_SOUNDFONT_DIR`, `TIGERCAPTURE_FLUIDSYNTH_EXE`,
  `TIGERCAPTURE_MUSIC_PRODUCTION_RENDERER_EXE`, and
  `TIGERCAPTURE_MUSIC_PRODUCTION_RENDERER_ARGS`.
- `debugCapture` may contain regenerated proof renders only; never store
  durable SoundFonts, sample packs, or installed synth tools there.

Backend status action:

```text
music.render.backends
```

This returns the preferred backend, production renderer readiness, quality
tiers, discovered SoundFonts, FluidSynth path, and warnings explaining why the
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
- Renderer selector: `auto renderer`, `production`, `soundfont`, `studio EDM`,
  or `local v5`.

Future deeper Music Lab UI can expand into a detachable dock:

- Prompt row: genre, mood, BPM, key, duration.
- Arrange lane: intro/build/main/outro sections.
- Chord lane: chord progression per section.
- Track lanes: drums, bass, chords, melody, fx, plus grouped orchestral views
  for the 128-track score mode.
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
- Non-orchestral prompts create the 9-channel default baseline unless the user
  explicitly disables FX, in which case the same arrangement can render as eight
  channels.
- Melodic EDM/NCS-style prompts create all nine arranged layers including bass
  pulse, arp, answer lead, counter melody, and FX by default.
- Key-aware progression tests must keep common minor EDM requests such as
  `A minor` on natural progressions like `Am-F-C-G`, with alternate breakdown
  and second-drop progressions for longer cues.
- `music.render.preview` writes a non-empty preview mix WAV and, when
  `render_stems=false`, does not write per-role stem WAVs.
- EDM/NCS/electronic `backend=auto` previews use
  `tigerstudio.studio_edm.v1`; tests should keep that route separate from
  `fluidsynth.soundfont.v1` and `tigerstudio.local_synth.v5`.
- `music.render_to_timeline` creates audio tracks and clips from those stems.
- `music.render_to_timeline(update_existing=true)` refreshes matching
  composition/role tracks instead of adding duplicate music lanes.
- `music.compose_to_timeline` composes, renders, inserts, and balances in one
  action so natural-language command routing does not need cross-step variable
  substitution.
- `music.export_midi` writes a standard `.mid` file beginning with a valid MIDI
  header.
- `music.state` exposes compositions and rendered stem paths.
- MIDI edit actions can create clips, write notes/chords, and quantize notes.
- Project save/load preserves composition state and music track/clip links.
- Clear prompts such as "make a 30s BGM" route to Music Lab instead of Sound
  Editor mastering.
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
