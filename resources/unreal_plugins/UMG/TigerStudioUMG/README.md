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
Schema v3 also carries explicit block reasons for Motion/Painter features that
need a deterministic raster or UI-material bake; these features are never
silently omitted from generated Widget Blueprints. Motion effect stacks,
keyers, and animated masks currently require that deterministic bake and are
reported as `effect_requires_bake:*` or `mask_requires_bake:*` during
preflight.
Motion scoped effect groups are likewise reported as
`motion_feature_requires_bake:effect_group`; their target scope is never
silently flattened or omitted.

The current source tree establishes the plugin and document boundary. Native
WidgetTree/UWidgetAnimation generation must not be claimed until an actual
generated asset has compiled and been captured from Unreal Editor.

## Distribution

`tools/build_unreal_umg_plugin.py` compiles this private source with the
canonical `D:\UE_5.8\Engine` installation and writes a source-free bundle to
`bundled/unreal_plugins/UMG/TigerStudioUMG`. PyInstaller includes only that
binary bundle. It never packages this `Source` directory into the public
installer.
