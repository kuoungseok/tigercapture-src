# Tiger Studio AEP Import Contract

## Status

Structural parser and compatibility inspection are implemented as v1. Native
composition conversion, visual playback, and After Effects render fallback are
separate follow-up stages. This document does not claim full After Effects
compatibility.

## Product goal

Tiger Studio should accept an `.aep` as a project source, determine what can be
converted to editable Motion Designer layers, preserve evidence about unknown
data, and route unsupported content to an explicit After Effects render/bake
path. Import must never silently drop an expression, effect, font, or linked
asset.

## Tiger-owned parser

The implementation under `app/motion_designer/aep` is dependency-free product
code. It was written for Tiger Studio and does not vendor or import another AEP
parser. Format behavior was cross-checked against these independent references:

- `forticheprod/py-aep` for current Python AEP structure research and sample
  corpus coverage (MIT).
- `boltframe/aftereffects-aep-parser` for an independent Go interpretation of
  the RIFX hierarchy (MIT).
- `inlife/nexrender` for the boundary between project mutation and official
  After Effects rendering (MIT).
- `airbnb/lottie-web` for the intentionally smaller portable animation subset
  and the need for explicit feature-loss reporting (MIT).

No reference package is a runtime dependency. Third-party source is not copied
into the Tiger implementation.

## Implemented v1 contract

- Validate the big-endian `RIFX/Egg!` root and trailing XMP boundary.
- Parse nested `LIST` chunks, known raw wrapper chunks, even-byte alignment,
  and opaque `btdk` payloads.
- Preserve unknown chunks in the structural tree by tag, size, offset, and
  payload location instead of discarding them.
- Enforce file-size, chunk-size, nesting-depth, and chunk-count limits before
  allocating or recursing further.
- Extract bounded strings and linked-media path candidates without opening the
  linked files.
- Detect expression metadata and high-risk external feature hints, returning
  either `native_conversion_candidate` or `ae_render_required`.
- Expose the ownerless, read-only `motion.aep.inspect` Action and
  `tools/qa_motion_aep_parser.py` CLI.

The report schema is `tigerstudio.motion.aep.inspect.v1`.

## Security boundary

Inspection does not execute or load:

- expressions, ExtendScript, or JavaScript
- third-party After Effects plug-ins
- fonts or linked footage
- Dynamic Link, Cineware, or external applications

All such features must remain metadata until a user-approved conversion or
render step handles them.

## Compatibility boundary

v1 is not an AEP renderer and does not yet create editable Tiger layers. It
does not evaluate effect pixels, text layout, masks, expressions, cameras,
lights, or color management. A structurally valid report only proves that the
project can be inspected safely.

The next conversion stage must map supported items to native Motion Designer
compositions, layers, transforms, masks, text, footage, and keyframes. Every
unmapped feature must produce a preflight blocker or deterministic bake plan.
The final fallback may use `aerender`/After Effects when installed, but the
Tiger parser remains usable without Adobe software.

## QA evidence

- Synthetic tests cover nested containers, odd-size padding, opaque lists,
  XMP, linked-path extraction, expression markers, truncation, and safety
  limits.
- The parser was exercised against 589 AEP files from the `py-aep` MIT sample
  corpus with zero structural failures. The largest parsed tree contained
  30,855 chunks.
- The external corpus is QA input only and is not bundled with Tiger Studio.
