# Tiger Studio UMG

Tiger Studio owns this project-local Unreal Engine plugin. It is the shared UMG
backend for Motion Designer, Painter, and future Tiger authoring surfaces.

The plugin is installed by Tiger Studio into:

```text
<Unreal Project>/Plugins/TigerStudioUMG
```

It is not installed into the Unreal Engine directory. Tiger explicitly enables
it in the connected `.uproject` and requests a safe editor restart when module
loading or an update requires one.

## Modules

- `TigerStudioUMG`: provider-neutral runtime document metadata, generated widget
  base class, and interaction events.
- `TigerStudioUMGEditor`: JSON preflight, import/reimport, Widget Blueprint and
  animation generation, validation, and headless Slate/UMG PNG evidence
  capture through `RenderWidgetBlueprintToPng`.

## Provider boundary

Motion Designer and Painter do not write Unreal assets directly. Each exports a
versioned Tiger UMG document with a `Provider` value such as
`motion_designer` or `painter`. The editor module converts that common document
to native UMG assets and reports every serialized layer as exactly one of
`Native`, `Material`, `Baked`, or
`Blocked`; raw JSON is checked before legacy defaults or UStruct conversion so
an unknown or missing value cannot become Native accidentally.
Schema v5 adds explicit Canvas-slot anchors, offsets, alignment, and a separate
render-transform pivot while preserving v4 import compatibility. Schema v6
adds a provider-neutral, validated UI Material record. Its first generator maps
leaf rectangle linear/radial gradients to a fixed Custom HLSL graph in a
translucent `MD_UI` Material and assigns it to a native `UImage`; arbitrary HLSL
is not accepted. Schema v7 adds provider-neutral horizontal and vertical flow
panels. Schema v8 adds the fixed `tigerstudio.umg.ui_material.v2` Rounded Card
generator: per-corner radii and smoothing, solid/linear/radial fill, inside,
center, or outside stroke, and independent drop and inner shadows are rendered
analytically by one validated Custom HLSL expression. The layer keeps a stable
`CanvasPanel` binding at its original geometry and the material `UImage` expands
inside it by `VisualPadding`, so shadow pixels are not clipped. Radial fills use
the authored Start-to-End and Start-to-Width basis, including rotated elliptical
gradients. Schema-v8 through schema-v18 Rounded Cards retain the fixed-size
behavior. No document-provided HLSL is accepted.
Schema v9 adds native Grid panels and row/column spans. Schema v10 adds
provider-neutral `ScrollOverflow` and `ScrollPosition`: horizontal and vertical
overflow generate `UScrollBox`, Both generates nested ScrollBoxes, and each
scroll frame uses a `UOverlay` plus a fixed `UCanvasPanel` for Fixed children.
Sticky remains an explicit runtime-binding blocker and is never silently
flattened.
Schema v11 adds one typed, provider-neutral `ImageFill` record shared by
Painter and Motion Designer. Texture resources are referenced by the same
stable `AssetId` used by standalone images, and the record preserves fit/fill,
focal crop, explicit source crop, tiling, opacity, tint, source size,
nine-slice margins, and corner radii. Native UMG brushes handle supported
combinations; image adjustments and brush combinations that Slate cannot
faithfully compose are explicit material-or-bake blockers.
Schema v12 adds a provider-neutral `Flipbook` atlas record for `Image`/`Shape`
layers with Material disposition. `Columns`, `Rows`, `FrameCount`,
`FramesPerSecond`, `StartFrame`, `Loop`, `Phase`, and
`StaticFrameOverride` are range-validated before import. Unreal always creates
the fixed `tiger_ui_flipbook_atlas_custom_hlsl_v1` graph: Texture Coordinate
and Time plus eight scalar parameters feed one float2 Custom node, which drives
the coordinates of one `TextureSampleParameter2D`; its named RGB and A outputs
connect directly to the UI Emissive and Opacity properties. Atlas textures are
imported as UI textures with clamped addressing. Documents cannot supply HLSL,
cannot combine Flipbook with Material/ImageFill visual records, and cannot
silently use unsupported crop, rotation, rounded clipping, or event-relative
time. Painter bake provenance keeps event-triggered playback blocked until a
dynamic material time-origin path exists; ambient loops are Material-ready.
Schema v13 gives `Baked` a materialized, provider-neutral meaning. Unreal does
not execute a provider rasterizer: the package must already contain a PNG
texture resource plus a complete typed `ImageFill`. The first accepted subset
is deliberately narrow: a leaf static-vector result serialized as `Kind=Image`,
`Mode=Stretch`, white tint, image opacity 1, and no crop, nine-slice, corner
radii, adjustments, Material, Flipbook, or remaining block reasons. Layer,
ImageFill, and texture resource IDs must match, and the payload must preserve
the static-vector source/content/pixel hashes and `Baked` provenance. Schemas
v4-v12 retain their previous behavior: every `Baked` layer is explicitly
blocked as `baked_generation_unavailable`. Schema-v13 generation consumes the
validated Texture2D through the normal `UImage` path while retaining
`Disposition=Baked` in the document and diagnostics.
The C++ trust boundary validates the real PNG SHA-256, canonical source hash,
SVG path/subpath structure, RGBA8 dimensions, and PNG sRGB intent. It does not
link Qt or rerasterize vector pixels. Python package creation rerenders the
canonical source and verifies both PNG and decoded RGBA hashes before Unreal is
allowed to consume the artifact.
Schema v14 adds a second narrow materialized `Baked` subset for exact Figma
appearance pixels. It accepts only a fixed-size, unrotated leaf Rectangle with
one visible normalized Noise effect, one normal solid fill, matching source and
render bounds, and an authenticated Render API PNG. Python and C++ validate the
source/effect canonical JSON and hashes, RGBA8/sRGB intent-0 PNG structure,
decoded pixel hash, provenance, typed ImageFill/resource identity, and exact
layout preservation. Existing schema-v13 static-vector documents remain valid;
ordinary documents stay on v13 and only documents containing this exact Noise
subset are emitted as v14. Schema v14 itself does not accept Texture or
progressive blur; dynamic layout, children, rotation, strokes, masks, Boolean
geometry, image content, or any additional blocker also remain explicitly
blocked.
Schema v15 adds a separate, fail-closed materialized `Baked` contract for one
visible Texture effect on an exact-PNG, fixed-size, unrotated leaf Rectangle.
It uses `Kind=static_figma_texture_png`, source schema
`tigerstudio.umg.static_texture_bake.v1`, and gate
`figma_texture_effect_requires_ui_material_or_deterministic_bake`; these values,
the canonical effect/source hashes, typed ImageFill/resource identity, exact
bounds and size, RGBA8/sRGB PNG contract, provenance, and layout preservation
must all agree. This is not a broad Texture claim: multiple visible effects,
render/source bounds mismatch, children, dynamic geometry, transforms, strokes,
masks, Boolean/image content, or any other blocker on a visible Texture remain
`Blocked`. A hidden effect is preserved but does not require output until made
visible.
Progressive layer blur remains `Blocked` even with an exact PNG because its
render bounds can require layout outsets. Progressive background blur remains
`Blocked` because it samples the live backdrop and a node PNG freezes only one
composition state. Hidden progressive effects round-trip without a render
request or blocker until made visible.
Schema v16 adds a typed, provider-neutral `ButtonStyle` v1 contract for every
native Button layer. Enabled plus Normal, Hovered, Pressed, and Disabled states carry
fill, stroke, stroke width, four corner radii, label color, font size, font
weight, and opacity. Unreal maps the state visuals to native
`UTigerStudioButton`/`FButtonStyle` rounded-box brushes and inherited Slate
foreground colors; one validated label font is applied across all states.
Per-state font-metric variation is explicitly blocked until a runtime font
binding exists. ImageFill buttons retain their explicit
`SelfHitTestInvisible` image child, so the parent Button remains the hit-test
owner. Schemas v4-v15 deserialize an empty default ButtonStyle and keep their
previous native Button behavior. Schema v16 also accepts the narrow typed
layer visibility set `Visible`/`HitTestInvisible`; generated artboard paint
uses the latter so it cannot consume pointer input intended for controls.
Schema v17 adds the explicit provider-neutral `Overlay` panel. Its children
use the native `UOverlaySlot` padding and horizontal/vertical alignment fields;
document child order remains the bottom-to-top paint order because UMG does
not expose a separate `UOverlaySlot` Z-order property. Fixed edge insets map to
padding, while proportional `scale` and custom anchor ranges remain explicit
Canvas requirements. Schema v17 also makes panel spacing intentional through
`SpacingStrategy=Padding|Spacer`. Linear Horizontal/Vertical panels can create
native `USpacer` children with `SpacerSizeRule=Auto|Fill` and a positive
`SpacerFillCoefficient`; Canvas, Grid, and Overlay never claim that spacers can
replace responsive absolute positioning.
Schema v18 adds reusable `Components` and screen `ComponentInstances`.
Each stable component ID generates one dependency-ordered
`WBP_TS_C_<ComponentId>` Widget Blueprint under the document's Components
folder; nested definition instances and screen placements are real child
`UUserWidget` instances of those generated classes. Text and boolean bindings,
static enum variables, fixed variant tuples, and static Named Slot content are
validated before generation. Instance source-layer overrides are restricted to
`content.text` and `visible`. Missing dependencies, dependency cycles, unknown
or mismatched properties, unsupported runtime property types, invalid slot
roots, and unsupported component-only layout combinations are explicit
preflight failures rather than flattened output. Component Widget Blueprints
compile and save before the screen Widget Blueprint, and generation reports
stable component asset/class maps plus per-layer class and visibility audit.
Schema v19 adds explicit Rounded Card `SizeBinding=FixedSize|WidgetGeometry`.
`FixedSize` preserves the schema-v8 material and visual-slot behavior.
`WidgetGeometry` is emitted only for allocations that can actually resize the
host: split Canvas anchors; Horizontal main-axis Fill with Fill alignment or
cross-axis Fill; the corresponding Vertical rules; Grid/Overlay Fill on either
axis; and Named Slot roots grafted into their generated Overlay when that
Overlay slot fills. Auto/non-Fill flow children remain `FixedSize` so an
otherwise old-schema document is not needlessly promoted. Image Fill still has
no dynamic UV binding and therefore remains explicitly blocked in the same
runtime-resized slots, including generated Named Slot Overlays.
the generated `UTigerStudioRoundedCardHost` receives the current Slate
`AllottedGeometry` in logical units immediately before child paint, resizes the
padded visual surface, and updates the per-widget MID `CardSize` parameter.
Application DPI scale is not multiplied a second time. Schema 8-18 materials
without this field are upgraded recursively, including component definition
layers, to `FixedSize`; schema 19 requires the explicit validated enum.
Canvas slots receive the same stable document-order Z-order explicitly. This
preserves paint order even though generation constructs container panels before
leaf widgets, including the synthetic artboard background.
The importer supplies field defaults only while upgrading schemas that predate
the corresponding layout, material, scroll, or ImageFill contract. Current
schema records remain strict and must carry their complete validated fields.
Painter's
continuous custom Min/Max anchors use this same v5 path, including point and
stretched `FAnchors`; no provider-specific Unreal plugin path is used. Per-layer
`BlockReasons` identify Motion/Painter features that need a deterministic raster
or UI-material bake; these features are never silently omitted from generated
Widget Blueprints. Motion effect stacks,
including paper crumple/unfold deformation, keyers, and animated masks
currently require that deterministic bake and are
reported as `effect_requires_bake:*` or `mask_requires_bake:*` during
preflight.
Motion scoped effect groups are likewise reported as
`motion_feature_requires_bake:effect_group`; their target scope is never
silently flattened or omitted.

UE 5.8 QA compiles the source plugin, generates and reloads real
WidgetBlueprints with native widgets, generated UI Materials, and
UWidgetAnimation. Flipbook QA additionally verifies the exact 12-expression
material graph, serialized Widget Blueprint/material/atlas references, zero
material shader compile failures, and an actual `FWidgetRenderer` 2x2
red/green/blue/yellow atlas capture against a single-transfer sRGB reference.
Evidence capture keeps Slate shading linear and writes into an explicit sRGB
render target, preventing both raw-linear output and double gamma encoding.
Schema-v14 Noise and schema-v15 Texture appearance QA each generate, compile,
save, and reload a real Widget Blueprint and Texture2D reference, then compare
a 96x64 `FWidgetRenderer` capture with the packaged 32x24 RGBA texture. Both
transport inputs are labeled `synthetic_contract_fixture` and
`not_a_figma_visual_golden`; neither is a claim of visual parity with a real
same-node Figma render. Noise QA is recorded at
`debugCapture/static_noise_ue_qa_plugin150/qa_report.json`. Texture QA is
recorded at `debugCapture/static_texture_ue_qa/qa_report.json` and passes alpha
bounds `[23,17,54,40]`, RGB MAE `0`, alpha exact `1`, exact crop hash equality,
outside alpha `0`, and exact source/bundle/install DLL hashes. The schema-v13
vector compatibility run is recorded at
`debugCapture/m6b_vector_static_bake_unreal_schema15_compat_final/qa_report.json`.
Tiger Glass rejection remains covered with the exact
`glass:effect_requires_bake:tiger_glass` reason.

Schema-v16 Button QA preserves the Mobile Onboarding active artboard paint and
CTA visual, while replacing only its unsupported cross-screen `navigate`
reaction with a supported `emit_event` runtime fixture. UE 5.8 generates,
compiles, saves, reloads, and renders a real Widget Blueprint containing a
`HitTestInvisible` background `UImage` and a visible `UTigerStudioButton`.
The post-construction audit verifies all four `FButtonStyle` states, radius 8,
font size 19, and the authored colors; the render verifies an opaque
`#F7F8FC` artboard plus the `#5B6CFF` rounded CTA. Evidence is recorded at
`debugCapture/painter_ui_designer/unreal_umg_button_schema16/qa_report.json`.
The original `navigate` reaction remains explicitly blocked until a UMG screen
router is implemented.

## Distribution

The current private source plugin is `Version 21 / 1.8.2`; the source-free
bundle is regenerated from this source for distribution. It compiles with UE
5.8 for Editor Development, Game Development, and Game Shipping.

`tools/build_unreal_umg_plugin.py` compiles this private source with the
canonical `D:\UE_5.8\Engine` installation and writes a source-free bundle to
`bundled/unreal_plugins/UMG/TigerStudioUMG`. PyInstaller includes only that
binary bundle. It never packages this `Source` directory into the public
installer.
