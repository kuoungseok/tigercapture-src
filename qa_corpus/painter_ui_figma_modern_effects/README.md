# Painter UI Figma modern-effect corpus

This corpus separates captured evidence from generated conformance fixtures.

- `real_plugin_api_capture`: data read back from a real Figma file through the
  Plugin API. It proves field shapes and values, but is not labeled as a REST
  response and does not prove pixels without a matching Figma PNG export.
- `official_schema_fixture`: a Tiger-owned minimal payload derived from the
  pinned official REST schema. It may test parsing and fail-closed behavior,
  but must not be described as a real Figma capture.

The OpenPencil capture is pinned to an immutable commit, kept byte-for-byte in
`external/assets/figma/compat_corpus`, and accompanied by its MIT license. Its
Noise and Texture records are suitable for import/normalization/round-trip
tests. Progressive Blur remains an official-schema fixture until a licensed
real capture and its Figma-rendered PNG golden are available.

Authenticated REST imports now request exact PNGs for visible Noise, Texture,
and progressive blur nodes through Figma's Render API and preserve node/bounds/
request provenance. Schema 14 can consume only a fail-closed leaf Noise subset
when such an exact PNG is present. Schema 15 separately accepts only a fixed,
unrotated leaf Rectangle with one visible Texture effect, exact matching bounds,
and a validated PNG under `static_figma_texture_png` /
`tigerstudio.umg.static_texture_bake.v1`. The satisfied gate is
`figma_texture_effect_requires_ui_material_or_deterministic_bake`; Texture
outside that subset stays explicitly blocked. This corpus still has no matching
same-node PNG for Noise or Texture, so it tests field compatibility only and
must not be used as a Figma visual golden.

UE 5.8 transport QA for both accepted subsets uses generated contract pixels,
not this corpus. The Noise and Texture inputs are labeled
`synthetic_contract_fixture` and `not_a_figma_visual_golden`. Texture QA creates,
compiles, saves, and reloads a real WBP and Texture2D, then passes
`FWidgetRenderer` bounds `[23,17,54,40]`, RGB MAE `0`, alpha exact `1`, exact
crop hash equality, outside alpha `0`, and exact plugin DLL hashes. Current
TigerStudioUMG source and source-free bundle are `Version 16 / 1.5.0` and build
for UE 5.8 Editor Development, Game Development, and Game Shipping.

Progressive blur remains explicitly blocked even when an authenticated node PNG
is available. A layer blur can expand `absoluteRenderBounds` beyond the authored
box, so replacing only the leaf would change layout, clipping, or hit geometry
unless a layout-aware bake also preserves those outsets. A background blur
samples the live backdrop; a node PNG captures only one backdrop state and
cannot reproduce runtime composition. Hidden progressive effects still round
trip as authored data, but intentionally request no render and create no UMG
blocker until made visible.
