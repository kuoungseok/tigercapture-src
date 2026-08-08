# Genre Composer Planners

TigerCapture Music Lab must not treat every non-orchestral prompt as the same
generic 9-track BGM sketch. Clear genre prompts route to dedicated deterministic
planners before note generation and before MIDI/export rendering.

## Supported Planner Routes

- `lofi`: dusty drums, vinyl/noise bed, warm sub bass, jazz chords, sample
  chops, mellow keys, tape pad, soft motif, room/cassette texture.
- `rock_metal`: rock drums, picked electric bass, palm-muted guitar, rhythm
  guitar, power-chord guitar, lead guitar, dark stage pad, impact FX.
- `jazz`: swing drums, walking bass, piano comping, comping guitar, sax lead,
  trumpet answer, brush/club ambience.
- `hiphop_trap`: trap drums, 808 bass, hat rolls, sample chop, dark keys,
  pluck lead, sub drops, hook counter, riser FX.
- `synthwave`: retro drum machine, octave pulse bass, analog pad, neon arp,
  synth lead, counterline, synth-brass stabs, noise/neon FX.
- `ambient`: drumless drone pad, shimmer pad, low bloom, slow motif, air
  texture, bell echo, space FX.

## Behavioral Contract

- Genre detection happens after classical/orchestral routing, so Paganini,
  solo-violin, symphonic, and 128-track orchestral prompts keep their dedicated
  higher-priority planners.
- Genre planners replace both section names and track roles. A `jazz` prompt
  must produce `head`, `solo_a`, `solo_b`, and `out_head`, while a `metal`
  prompt must produce riff/solo/final-chorus sections.
- Genre tracks must produce non-empty MIDI-note clips. They cannot be cosmetic
  labels over the default `drums/bass/chords/melody/fx` sketch.
- MIDI export and sample-production rendering must understand genre roles well
  enough to select plausible programs and buses: drums to percussion, 808/sub
  to low, guitar/sax/synth lead to lead, pads/chords to pads, and textures to
  FX.
- This is still a deterministic local planner, not an AI audio model and not a
  DAW-grade sample library. It exists so one-click composition produces
  structurally genre-aware source material that external SoundFonts, sample
  libraries, or production/AI renderers can improve.

## Validation

`tests/test_music_composer_actions.py::test_genre_specific_planners_route_common_music_styles`
locks the expected role/section routes for lofi, metal, jazz, trap, synthwave,
and ambient prompts.
