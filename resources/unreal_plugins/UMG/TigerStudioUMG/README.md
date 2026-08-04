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
  animation generation, validation, and evidence capture.

## Provider boundary

Motion Designer and Painter do not write Unreal assets directly. Each exports a
versioned Tiger UMG document with a `Provider` value such as
`motion_designer` or `painter`. The editor module converts that common document
to native UMG assets and reports every layer as native, baked, or blocked.
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
gradients. Rounded Card generation currently requires fixed geometry; stretched
Canvas anchors and horizontal, vertical, or grid parents are explicitly blocked
until dynamic material-size binding is implemented. No document-provided HLSL
is accepted.
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

UE 5.8 QA compiles the source plugin, generates and reloads a real
WidgetBlueprint with native widgets, a generated UI Material, and
UWidgetAnimation, and separately proves that a Tiger Glass document is rejected with the exact
`glass:effect_requires_bake:tiger_glass` reason.

## Distribution

`tools/build_unreal_umg_plugin.py` compiles this private source with the
canonical `D:\UE_5.8\Engine` installation and writes a source-free bundle to
`bundled/unreal_plugins/UMG/TigerStudioUMG`. PyInstaller includes only that
binary bundle. It never packages this `Source` directory into the public
installer.
