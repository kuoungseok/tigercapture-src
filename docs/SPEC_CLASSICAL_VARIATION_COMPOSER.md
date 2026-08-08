# Classical Variation Composer Spec

## Goal

Classical prompts such as Paganini, caprice, rondo, solo violin, violin
concerto, or theme-and-variation must not be treated as generic orchestral
trailer music. The main musical subject stays with solo violin. Other
instruments support the form and may bloom in the climax, but they must not
take over the entire cue.

## User Intent

When the user asks for Paganini/violin/classical variation:

- The violin is the protagonist from beginning to end.
- The initial material can be aggressive and virtuosic.
- The middle should be more lyrical, with thinner support.
- The climax may add strings, percussion, brass, and woodwinds.
- The orchestra is climax-only expansion, not a constant full-score bed.
- The final coda should return attention to the solo violin or its residue.

## Musical Method

The generator should behave more like a classical variation planner than a
short-loop generator.

- Motif extraction: start from a short degree-based motif, not a full repeated
  melody loop.
- Rhythmic variation: change note spacing between theme, rhythmic variation,
  lyrical variation, virtuoso climax, and coda.
- Register variation: move the same material between lower, middle, and high
  violin positions.
- Articulation variation: short spiccato/staccato figures for aggressive
  passages, legato/sustain for lyrical material.
- Harmonic reinterpretation: use a softer relative-major or relaxed progression
  in the lyrical section, then return to minor/cadential pressure for climax.
- Sequence and ornament: move motif fragments by degree and add occasional
  passing notes so repeated material evolves.
- Call and response: woodwinds/horns may answer the violin in lyrical/climax
  sections, but should remain sparse.
- Solo prominence: `solo_violin` note count and volume should dominate before
  the climax. Heavy roles such as `brass_climax`, `timpani_climax`, and
  `cymbals_climax` should be silent outside climax/coda.

## Current Implementation

`app/music_composer.py` detects classical variation requests through
`_is_classical_variation_request(...)`. Matching requests use:

- `CLASSICAL_VARIATION_TRACK_COUNT`
- `_classical_variation_sections(...)`
- `_classical_variation_tracks(...)`
- `_render_classical_variation_role(...)`

The dedicated track layout is intentionally smaller than the 128-track
orchestral trailer plan:

- `solo_violin`
- `solo_violin_echo`
- `solo_violin_harmony`
- `chamber_strings`
- `cello_bass`
- `woodwind_response`
- `horn_response`
- `brass_climax`
- `timpani_climax`
- `hall_pad`
- `cymbals_climax`

The 128-track plan remains for broad orchestral/symphonic/trailer prompts.
Classical violin prompts are routed before generic orchestral detection so a
phrase such as "Paganini violin with orchestra in the climax" stays
solo-centered.

## Acceptance Criteria

- Paganini/violin/classical variation prompts create a dedicated classical
  variation composition rather than the generic 128-track trailer plan.
- Sections include `theme`, `rhythmic_variation`, `lyrical_variation`,
  `climax`, and `solo_coda` for longer cues.
- `solo_violin` has notes in every section.
- Heavy climax roles have no notes before the `climax` section.
- The lyrical section has lower density and longer notes than the aggressive
  opening/virtuoso climax.
- The solo violin phrase signatures differ across sections; the same tiny
  melody loop must not be copied unchanged.
- MIDI export maps solo violin to a violin program and keeps climax percussion
  on the percussion channel.
