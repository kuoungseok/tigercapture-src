# AR/PBR Real-Time Compositor

## Goal

TigerCapture should support an internal real-time AR/PBR compositor for placing
3D assets into real footage without calling Blender, Marmoset, or another
external renderer.

The target workflow is:

1. Import a street or road video.
2. Generate or load a temporally stable depth map sequence.
3. Estimate a road plane and camera solution from depth, tracking, and manual
   calibration points.
4. Import an FBX/GLB asset and place it on the solved plane.
5. Render the asset with PBR material controls.
6. Composite it over the existing preview frame with depth occlusion, shadows,
   reflections, and color matching.
7. Export with the same visual contract as preview.

## Ownership

As of 2026-06-27, AR/PBR renderer work is owned by the active TigerCapture
Codex implementation session. Keep the implementation modular and prefer new
code under:

- `app/ar_pbr/*`
- `app/depth/*`
- `app/camera_solve/*`
- `tests/test_ar_pbr_*`
- `tests/test_depth_*`
- `tests/test_camera_solve_*`

The first integration points should remain thin hooks only:

- `app/project_player.py`: preview compositor hook
- `app/video_exporter.py`: export compositor hook
- `app/project_io.py`: AR/PBR track persistence
- `app/media_pool.py`: FBX/GLB/3D asset recognition

Avoid broad refactors in these integration files unless the user explicitly
asks for a larger renderer integration pass. When touching them, preserve the
thin-hook contract between ProjectPlayer preview, VideoExporter export bake,
Project I/O track persistence, and Media Pool 3D asset recognition.

## Hook Contract

Preview hook:

```python
from app.ar_pbr.compositor import composite_preview_frame

frame, diagnostics = composite_preview_frame(
    base_frame,
    time_ms=pos_ms,
    ar_tracks=ar_tracks,
    camera_solution=camera_solution,
    depth_frame=depth_frame,
    settings=settings,
)
```

Export hook:

```python
from app.ar_pbr.compositor import composite_export_frame

frame, diagnostics = composite_export_frame(
    base_frame,
    time_ms=project_ms,
    ar_tracks=ar_tracks,
    camera_solution=camera_solution,
    depth_frame=depth_frame,
    settings=settings,
)
```

Both hooks must:

- Accept plain Python, NumPy, or PIL-compatible data.
- Avoid PyQt dependencies in core modules.
- Lazy import optional dependencies.
- Return the original frame unchanged on failure.
- Return diagnostics explaining fallback, missing dependencies, cache IDs, and
  active track counts.
- Preserve preview/export visual parity when using the same quality settings.

## Track Schema

```json
{
  "id": "ar_pbr_001",
  "type": "ar_pbr_object",
  "asset_path": "model.fbx",
  "start_ms": 0,
  "end_ms": 10000,
  "transform": {
    "position": [0, 0, 0],
    "rotation": [0, 0, 0],
    "scale": [1, 1, 1]
  },
  "placement": {
    "mode": "road_plane_anchor",
    "image_point": [960, 720],
    "coordinate_space": "frame",
    "surface_offset": 0.0
  },
  "camera_solution_id": "cam_001",
  "depth_source_id": "depth_001",
  "occlusion": true,
  "shadow_catcher": true,
  "reflection_catcher": false,
  "color_match": {
    "exposure": 0.0,
    "white_balance": 6500,
    "contrast": 1.0
  }
}
```

Optional material fields:

```json
{
  "material": {
    "base_color": [1.0, 1.0, 1.0, 1.0],
    "roughness": 0.45,
    "metallic": 0.0,
    "reflectance": 0.5
  },
  "render": {
    "shadow_quality": "medium",
    "reflection_quality": "preview"
  }
}
```

When `material` is omitted, imported FBX material data is used. When `material`
is present on the track, it is treated as a user override.

## Depth Contract

Depth frames should use normalized float values with this convention:

- `0.0`: near camera
- `1.0`: far from camera

Depth sources must produce diagnostics with:

- `depth_source_id`
- `frame_count` or `time_ms`
- `backend`
- `metric`: true or false
- `cache_path` when persisted
- `warnings`

Initial synthetic QA may use a deterministic luminance and vertical-gradient
depth estimator. Production quality requires a video-consistent model such as
Video Depth Anything or an ONNX equivalent, loaded only when available.

### Depth Quality Gap And Response Plan

Current implementation status:

- `app.depth.providers` owns the registered depth-provider layer. Implemented
  provider ids are `synthetic_luma_depth`, `onnx_monocular_depth`, and
  `external_depth_sequence`, and `video_temporal_depth`.
- `app.depth.estimator.estimate_depth_from_luma` is retained as a compatibility
  wrapper for the deterministic QA fallback. It blends a vertical near/far
  gradient with luma so renderer paths can be tested without model downloads.
- `onnx_monocular_depth` is enabled only when `onnxruntime` is installed and
  `TIGERCAPTURE_DEPTH_ONNX_MODEL_PATH` points at a local ONNX model. TigerCapture
  does not silently download depth models.
- `app.depth.jobs.generate_depth_cache_for_frames` can generate clip/keyframe
  depth caches with manifest metadata.
- `app.depth.cache` stores frame `.npy` files plus a manifest with provider,
  source path, source mtime, frame count, stale-cache status, and nearest-frame
  lookup support.
- `app.depth.refinement` provides compositor-oriented depth cleanup:
  robust normalization, invalid edge-band masking, RGB-guided edge-aware
  smoothing, foreground bias, and a separate layered depth-matte path for
  viewer diagnostics. `app.depth.temporal` provides scene-cut-aware temporal
  stabilization.
- `ProjectPlayer` and `VideoExporter` already pass depth frames into AR/PBR
  preview/export when `depth_source_id`, scene-anchor depth, or runtime depth is
  available. Cached depth is loaded first, including nearby cached frames for
  scrub/export continuity. If no cached source exists, they fall back through
  `app.depth.estimator.estimate_depth(...)`.
- `app.ar_pbr.depth_occlusion` can apply normalized 0..1 depth matte
  occlusion, tolerance, softness, and optional edge-glow diagnostics.
- The worker-safe full GPU helper currently applies video-depth as an overlay
  alpha matte after model-view rendering; this is useful but not the final
  native model-depth-buffer compare path.

Product implication:

- TigerCapture must not claim high-quality photo/video depth generation while
  the runtime depth backend is `synthetic_luma_depth`.
- The current fallback is sufficient for QA, simple road-plane smoke tests, and
  proof that preview/export consume depth. The refinement pass can make viewer
  diagnostics look like stable layered mattes, but synthetic fallback depth is
  still not a substitute for a high-quality monocular/video depth model.

Production response plan:

1. DONE: Registered depth-provider layer under `app/depth/`:
   - provider ids: `synthetic_luma_depth`, `onnx_monocular_depth`,
     `external_depth_sequence`, `video_temporal_depth`.
   - common result: normalized float32 depth, provider diagnostics, and provider
     status.
   - no silent model downloads.
2. DONE: ONNX-first local backend contract:
   - `onnx_monocular_depth` runs local ONNX models through `onnxruntime` when a
     model path is configured.
   - if unavailable, the selector returns the deterministic fallback and reports
     provider availability.
3. DONE: Depth cache job for clips/keyframes:
   - generate frame depth `.npy` files.
   - store a manifest with provider, version, frame count, source path, source
     mtime, diagnostics, and stale-cache detection.
   - preview/export can read exact or nearby cached depth frames.
   - CLI/manual QA entry point:
     `python tools/generate_depth_cache.py clip.mp4 --interval-ms 200 --max-frames 60`.
4. PARTIAL: Edge/refinement passes before AR/PBR occlusion:
   - robust normalize, invalid border masking, RGB-guided edge-aware smoothing,
     optional foreground bias, and layered viewer matte are implemented.
   - remaining work: SAM/object-mask integration, manual brush correction UI,
     and a production monocular/video depth backend.
5. PARTIAL: Video temporal stabilization:
   - lightweight temporal smoothing with scene-cut reset exists.
   - remaining work: optical-flow-guided propagation and Video Depth Anything or
     equivalent high-quality backend.
6. TODO: Add calibration controls:
   - floor/road plane hints, horizon/vanishing lines, known-height scale, camera
     FOV/focal estimate, and depth range remap.
   - save these as clip-sidecar depth calibration data so export matches
     preview.
7. TODO: Upgrade full GPU helper occlusion:
   - expose/capture rendered model depth from the helper.
   - compare video depth against rendered object depth per fragment/pixel,
     rather than only applying an overlay alpha matte.

Acceptance criteria for "AR/PBR depth is production-usable":

- Diagnostics show a real provider such as `onnx_monocular_depth` or
  `video_temporal_depth`, not `synthetic_luma_depth`.
- Cached depth has a manifest, frame count, provider version, and stale-cache
  detection.
- A human foreground can hide a 3D model with stable edges in preview and
  export.
- A 10-30 second handheld video does not flicker frame-to-frame after temporal
  stabilization.
- The user can manually fix wrong foreground/background regions without leaving
  TigerCapture.

## Camera Solve Contract

A camera solution should include:

```json
{
  "id": "cam_001",
  "model": "manual_depth_plane_v1",
  "frame_size": [1920, 1080],
  "intrinsics": {
    "fx": 1600.0,
    "fy": 1600.0,
    "cx": 960.0,
    "cy": 540.0
  },
  "plane": {
    "point": [0.0, 0.0, 1.0],
    "normal": [0.0, 1.0, 0.0],
    "d": 0.0
  },
  "image_points": [[900, 700], [1100, 700], [1000, 500]],
  "depth_source_id": "depth_001"
}
```

The first pass can be manual-assisted: users select road points, horizon,
vanishing lines, or known scale. Fully automatic plane and camera tracking can
arrive later.

## Road-Plane Placement Contract

Object tracks can be manually transformed, or anchored to the solved road plane.
For road placement, the compositor resolves `placement.image_point` through the
camera intrinsics and `camera_solution.plane`, then writes a renderer-space
`transform.position` just before drawing:

```python
from app.ar_pbr.placement import resolve_track_placement

resolved_track, diagnostics = resolve_track_placement(
    track,
    camera_solution,
    frame_size=(frame_width, frame_height),
    settings={"camera_z": 3.25},
)
```

Supported placement modes:

- `manual`: use `transform` as-is.
- `road_plane_anchor` / `plane_anchor`: cast a camera ray from `image_point` and
  intersect it with `camera_solution.plane`.

`coordinate_space` can be `frame`, `camera_solution`, or `normalized`. The
original `transform.position` is preserved as a manual offset after anchoring.

Runtime scene-anchor tracking is pragmatic rather than full SLAM. The first
anchored frame stores a grayscale template around `placement.image_point` plus
several nearby probe templates. Later frames search translation plus bounded
scale and roll candidates, then use the relative motion of the matched probes
to stabilize zoom/roll. A successful match updates:

- `placement.image_point` for translation.
- `transform.scale` from the matched template scale.
- `transform.rotation.z` from the matched image-space roll.

This is suitable for props that should follow local video zoom/roll. It is not
a complete 3D camera tracker yet; full perspective rotation, lens distortion,
multi-point solve, and SLAM-style camera motion remain production-renderer work.
Runtime diagnostics expose `camera_motion_hint` / `slam_assist` with
`mode=template_depth_plane_slam_assist`, pixel translation, normalized
translation, scale, roll, tracking confidence, plane solve state, and an
explicit `not_full_slam` limit string. UI and QA should use that payload to
show tracking confidence without claiming full SLAM.

## Renderer Direction

External Blender/Marmoset calls are out of scope. The intended production
renderer is an internal native real-time PBR backend, with Filament as the
preferred candidate because it already covers:

- glTF/PBR material semantics
- metallic and roughness workflow
- HDR and tone mapping
- image-based lighting
- physically based lights
- shadows and real-time renderer infrastructure

FBX should be imported through a conversion or asset adapter layer and normalized
into a runtime-friendly representation. Runtime rendering should prefer GLB/glTF
style PBR material data.

Render-profile policy:

- `authored` preserves source shader intent for ordinary assets.
- `vrm_mtoon` is the default profile for imported VRM assets with VRM0/MToon
  material metadata. It keeps the avatar on the toon path, carries MToon
  renderQueue/ZWrite/culling/cutoff metadata into preview/export diagnostics,
  and prevents VRM avatars from silently falling into the generic PBR route.
- `marmoset_pbr` is an optional profile in the existing AR/PBR 3D pipeline, not
  a VTuber bridge feature. It is exposed only when the imported resource has
  explicit glTF PBR data such as base-color, metallic/roughness, normal,
  occlusion, emissive maps, PBR factors, or PBR material extensions.
- Choosing `marmoset_pbr` lets the GPU preview/export packet path use IBL/PBR
  shading for eligible materials. It must not force ordinary MToon-only VRM
  assets away from their authored toon look.
- The descriptor field is `render_profiles` with schema
  `tigerstudio.ar_pbr.render_profiles.v1`; AR/PBR tracks can request the option
  with `track["render"]["render_profile"] == "vrm_mtoon"` or
  `track["render"]["render_profile"] == "marmoset_pbr"`.

## Asset Import Contract

FBX is a supported source format, but it should not be parsed inside preview or
export hot paths. Import should happen through:

```python
from app.ar_pbr.importer import import_asset, import_track_asset

asset, diagnostics = import_asset("assets/car.fbx", project_root=project_root)
```

The importer must:

- Accept `.fbx` and `.vrm` without requiring Blender, Marmoset, or another
  external renderer.
- Lazy-load optional backends such as `trimesh`, `pyassimp`, or an Autodesk FBX
  SDK adapter only when import is requested.
- Return a stable placeholder asset descriptor if the backend is unavailable,
  the file is missing, or parsing fails.
- Preserve source metadata including `source_path`, `source_ext`,
  `requires_runtime_conversion`, `mesh_count`, `material_count`, `bounds`,
  `units`, `axes`, and diagnostics.
- Prefer conversion into GLB/glTF-style PBR data for the production renderer.
  `.vrm` is treated as a GLB/glTF avatar source and preserves VRM0/VRM1
  metadata for downstream avatar/broadcast tooling.
- Cache imported asset descriptors outside preview/export hot paths.
- Attach `support` to both the descriptor and diagnostics. The report uses
  `support_level` values `ready`, `limited`, `unsupported`, or `placeholder`,
  plus `issue_codes`, `feature_flags`, `render_path`, and preview/export
  booleans so UI can show a product message instead of raw JSON.
- Main editor integration must expose only public support rows such as
  `Ready: skeletal PBR`, `Ready: VRM avatar`, `Limited: FBX conversion`, or
  `Unsupported: compressed mesh`. Media Pool must not run heavy import during
  ingest; it shows a deferred status and lets preview/place/export hooks attach
  the authoritative `support` report.

The internal importer can parse ASCII and binary FBX metadata without external
renderers: static mesh counts, vertex-derived bounds, model names, material
slots, hierarchy connections, units, axes, texture count, and animation stack
count. FBX mesh buffers are normalized into preview `vertices` and triangulated
`triangles`; binary FBX normals/UVs and ASCII FBX `LayerElementUV` data are
preserved by splitting render vertices when one source control point has
multiple polygon-vertex UVs. Very large binary meshes are decimated for the CPU
preview path while preserving full-scene bounds. Later milestones can add blend
shapes, texture relinking, and a native high-quality renderer.

Current support levels:

- `ready`: glTF/GLB/VRM static or skeletal assets with renderable geometry.
  Skeletal meshes use CPU pose baking into the full GPU PBR path. VRM keeps its
  avatar metadata and can report as a humanoid avatar.
- `limited`: FBX source assets and assets with incomplete material coverage.
  Static FBX can still preview/export through the normalized descriptor path.
- `unsupported`: known unsupported data such as required Draco or meshopt
  compression without a decoder.
- `placeholder`: missing assets or failed imports that intentionally return a
  safe no-op descriptor.

Asset descriptor cache:

```python
from app.ar_pbr.asset_cache import store_asset_descriptor, load_asset_descriptor

cache_info = store_asset_descriptor(asset, diagnostics=diagnostics)
asset = load_asset_descriptor(cache_info["asset_id"])
```

## Media Pool Asset Preview UX

Media Pool treats `.fbx`, `.glb`, `.gltf`, and `.vrm` as 3D assets, separate
from the Live2D/Spine actor bin. Double-clicking a 3D asset opens the app-facing
AR/PBR preview window.

The preview window must stay consistent with the editor chrome:

- dark studio panel styling;
- model viewport as the primary surface;
- HDR/IBL environment background when available;
- controls limited to environment light, key light, and shadow parameters;
- no JSON diagnostics or debug dumps in the user-facing window.

Diagnostics and renderer internals can remain available in standalone tools,
but the Media Pool flow should be product-facing and safe to use during normal
editing.

## HDR Environment Presets

The 3D model preview exposes an `HDR Environment` dropdown for image-based
lighting presets. The user-facing term can be "HDR cubemap preset", but the
current runtime asset is an equirectangular `.hdr` environment loaded into the
OpenGL preview shader.

Preset metadata lives in:

```text
resources/ar_pbr/manifest.json
```

Runtime discovery lives in:

```python
from app.ar_pbr.hdri_presets import hdri_presets, resolve_hdri_preset
```

The local bundled preset set currently contains editor-wide Poly Haven CC0 1K HDRIs:

- Wide Street
- Studio Small 09
- Abandoned Parking
- Cayley Interior
- Autumn Forest
- Belfast Sunset
- Cobblestone Night
- Brown Photostudio

Changing the preset in the preview window must not reimport the mesh. It should
only reload the HDRI texture, update any estimated key-light direction, refresh
the viewport, and persist the selection into AR/PBR track lighting as
`hdri_id` and `hdri_path`.

## Software Preview Renderer

Before the native real-time backend lands, `renderer="software_pbr"` provides a
deterministic CPU preview path:

```python
frame, diagnostics = composite_preview_frame(
    base_frame,
    time_ms=pos_ms,
    ar_tracks=ar_tracks,
    camera_solution=camera_solution,
    depth_frame=depth_frame,
    settings={
        "renderer": "software_pbr",
        "asset_descriptors": {
            "assets/car.fbx": imported_asset_descriptor
        },
        "light_direction": [-0.35, -0.85, -0.4],
        "camera_z": 3.25
    },
)
```

This path projects triangles from the imported asset descriptor, applies
material color, roughness, metallic, and reflectance controls with simple
PBR-like shading, and composites depth occlusion, shadow catcher, and reflection
catcher masks. It is intended for contract verification and fast preview
development, not final Marmoset-class quality.

## GPU Preview Mesh Path

The editor preview now has a first GPU mesh overlay path for AR/PBR tracks.
`app.ar_pbr.gpu_preview.build_gpu_preview_items()` converts active tracks and
asset descriptors into NDC colour-triangle packets. `ProjectPlayer` sends those
packets as `ar_pbr_items` through the existing `gpu_frame_ready` payload even
when the QImage/CPU consumer path is still enabled for pop-outs or scopes, and
`OpenGLPreviewWidget` draws them directly over the video texture.
In the main OpenGL video viewer, `auto` and `full_gpu` preview modes must prefer
this packet path before any CPU/QImage composition fallback so material colors,
texture-map packets, and PBR shader data are not collapsed into a flat preview.

This is deliberately preview-first:

- CPU `software_pbr` remains the export and QImage fallback path.
- The GPU path draws color packets, UV texture packets, and model-view-style
  `pbr_triangles`. `OpenGLPreviewWidget` samples base, roughness, metallic,
  specular, normal, and occlusion maps, including glTF-style channel selection
  for packed metallic/roughness/AO textures. If a base map is missing but other
  material maps exist, a white fallback texture preserves the material base
  color instead of dropping the triangle.
- Packet building prefers explicit per-triangle/face-corner UVs when present,
  then falls back to per-render-vertex `uvs`. This keeps FBX UV seams stable
  after import and prevents texture islands from being sampled with shared
  control-point indices.
- glTF import preserves available `TEXCOORD_n` attributes as `uv_sets`.
  Materials record the base texture's `texCoord` and `KHR_texture_transform`
  offset/rotation/scale metadata; packet building applies the base texture UV
  set and transform before sending textured/PBR triangles to GL preview/export.
  glTF sampler `wrapS` / `wrapT` is also preserved for material maps and the
  GL preview uploads AR/PBR textures with matching `Repeat`, `ClampToEdge`, or
  `MirroredRepeat` modes. This prevents UVs outside 0..1 from smearing at image
  edges in preview. Map-specific UV transforms beyond the shared material base
  path remain a future extension.
- During timeline playback the packet path uses a lower default triangle budget
  than paused/scrubbed preview (`AR_PBR_PLAYBACK_TRIANGLE_LIMIT`, currently
  1,000) and samples triangles evenly across the source mesh instead of drawing
  only the first triangles. Static playback packets are cached by frame size,
  camera solution, track render/transform/material data, descriptor fingerprint,
  and triangle limit. Cache hits reuse the same `ar_pbr_items` payload so a
  static object does not rebuild thousands of Python triangle rows every frame;
  diagnostics expose `packet_cache_hit`. Animated descriptors and live
  depth-texture frames are not cached because their projected vertices or depth
  tests can change per frame. If packet rendering cannot produce items during
  playback, `ProjectPlayer` leaves the video frame unchanged rather than
  falling back to CPU `software_pbr`; this keeps playback responsive and
  surfaces the failure through diagnostics.
- Textured/PBR meshes use a live depth texture fragment discard path in the GL
  preview and a mirrored per-pixel item-depth mask in packet export. Coarse
  packet-time center culling is retained only for non-textured color fallback
  meshes.
- Video-depth occlusion is normalized through `app.ar_pbr.depth_occlusion`.
  Synthetic/software fallback, packet PBR export, GL preview, and the full GPU
  helper must all honor track `occlusion=true` when a `depth_frame` is
  available. `occlusion_tolerance` / `depth_occlusion_tolerance` set the
  compare margin, and `occlusion_softness` / `depth_occlusion_softness` can
  soften the alpha matte edge for noisy monocular depth. The same helper also
  owns optional `depth_edge_glow_*` settings for a thin depth-boundary rim glow
  on visible object pixels next to foreground depth edges.
- Reflection catchers are layered depth-fade screen-space packets so preview
  and export have softer, less card-like contact reflections. Shadow catchers
  remain lightweight contact approximations. Real shadow maps are explicitly
  deferred; product-quality AR/PBR still needs a future shadow-map pass and
  deeper reflection/lens/camera tuning before all fallback renderers can become
  diagnostic-only paths.

The current integration promotes the model-view GPU renderer as the quality
source of truth where it is safe to pay the cost:

- `renderer="full_gpu"` / `renderer="offscreen_gpu"` /
  `renderer="model_view_gpu"` route preview/export through the
  `full_model_view_gpu_pbr` helper first.
- Export defaults to the full GPU helper and falls back to packet PBR if the
  helper fails.
- Timeline preview defaults to `auto`: paused/scrubbed frames use the full GPU
  helper for inspection quality, while playback can keep the packet GL overlay
  for responsiveness. In auto QImage mode, the preview window must keep the GL
  surface visible whenever `spine_items`, `ar_pbr_items`, or `mmd_items` are
  present in the `gpu_frame_ready` payload.
- `ProjectPlayer._apply_or_defer_ar_pbr_overlay()` must try the full GPU helper
  before building packet metadata whenever `auto` is not playing or
  `full_gpu` is explicitly requested. If the helper fails, it falls back to the
  packet GL overlay and records the failed full-GPU diagnostics.
- `TIGERCAPTURE_AR_PBR_PREVIEW_RENDERER=packet|full_gpu|software|off` and
  `TIGERCAPTURE_AR_PBR_EXPORT_RENDERER=gpu|packet|software|off` can force a
  specific path for QA or low-power machines.
- Newly placed AR/PBR objects use `DEFAULT_PREVIEW_SCALE=3.25` so the first
  appearance reads as an inspectable foreground object instead of a tiny safe
  thumbnail. Existing tracks keep their saved transform scale.

## Video-Depth Occlusion Contract

AR/PBR video-depth occlusion means the source video depth map can hide AR/PBR
pixels when a video-space foreground object is closer than the rendered 3D
object. This is separate from material AO/occlusion maps.

Current implemented behavior as of 2026-07-03:

- `ProjectPlayer` and `VideoExporter` resolve runtime depth frames from
  `depth_source_id` or scene-anchor/runtime depth and pass them to
  `composite_preview_frame` / `composite_export_frame`.
- `app.ar_pbr.depth_occlusion` owns depth normalization, tolerance/softness
  parsing, and alpha-mask application. Depth inputs are normalized to a 0..1
  convention where lower values are closer to the camera.
- `app.ar_pbr.depth_occlusion.build_depth_effect_masks(...)` is the reusable
  depth-mask extraction point for effects. It returns visible, hidden,
  transition, scene-depth-edge, object-boundary, and final edge masks so glow,
  contact effects, depth-aware outlines, and future node effects do not each
  reimplement depth math.
- `app.ar_pbr.depth_view.depth_frame_to_rgb(...)` is the viewer-only depth map
  display path. The main ProjectPlayer preview can be switched to
  depth-map-only via `ProjectPlayer.set_ar_pbr_depth_view_mode(...)` or Python
  Actions `ar_pbr.preview.depth_view.get/set`. The UI `Depth` button cycles
  `off -> matte -> distance -> plane -> off`: `matte` uses
  `app.depth.refinement.layered_depth_matte_for_viewer(...)` for cleaner object
  bands and sharper visual edges, `distance` keeps a smoother depth gradient
  with contour lines for distance/slope checking, and `plane` overlays rough
  road/floor candidate regions for placement inspection. `heat` and
  `inverted_grayscale` remain debug options. These modes are diagnostic only
  and must not change export/composite output.
- Depth-map-only preview is user-controlled and must stay off by default. Normal
  playback must not estimate depth unless an active AR/PBR track explicitly
  needs depth for occlusion, scene/plane anchoring, or the user has enabled the
  Depth viewer toggle. If no depth cache is available, live depth estimation may
  be slower and should be treated as an intentional diagnostic/placement cost,
  not part of the baseline video playback path.
- AR/PBR track status is separate from the Depth viewer. Timeline AR/PBR lanes
  expose a compact metadata badge: `3D` for manual placement, `ANCH` for
  depth/plane anchored placement, and `TRK` when the anchored track also has
  template tracking metadata. This badge must not run depth estimation or scene
  solving by itself.
- Encoded letterbox/pillarbox mattes are detected from the RGB video frame
  before depth refinement. Detected matte bands are treated as invalid scene
  area for depth normalization and diagnostic matte/plane inspection; they are
  not valid road/floor or occlusion evidence.
- Optional depth-boundary glow is configured through
  `depth_edge_glow_enabled`, `depth_edge_glow_strength`,
  `depth_edge_glow_radius_px`, and `depth_edge_glow_color`. This is a visible
  rim effect on object pixels adjacent to foreground depth discontinuities,
  not a substitute for the actual alpha occlusion matte.
- While an AR/PBR object is being moved with the viewport gizmo, the editor
  temporarily enables viewer-only `occlusion` plus a depth-boundary glow cue so
  users can see that video depth is influencing the object placement. This cue
  is restored to the track's original render settings on release and must not
  be treated as a persisted material or lighting change.
- The GL preview path uploads live depth textures for PBR triangles and uses a
  fragment discard comparison against each triangle's object-depth hint. When
  depth edge glow is enabled, the fragment shader samples neighboring depth
  pixels and adds a small display-space glow on visible fragments near the
  depth boundary.
- Packet/headless PBR export applies the same per-pixel alpha mask to sampled
  PBR triangles. If a global export depth frame is unavailable, packet export
  can consume the item's live depth texture payload. Packet export mirrors the
  depth-boundary glow as a post-display RGB addition before compositing.
- The worker-safe full GPU export bridge serializes the current `depth_frame`
  to a temporary float32 `.npy` payload in
  `app.ar_pbr.full_gpu_export_service`; `tools/ar_pbr_full_gpu_export_service.py`
  reads it and applies an overlay alpha depth matte before compositing the
  model-view render over the source frame.
- Successful diagnostics should expose `depth_frame_available`,
  `pbr_depth_occlusion_applied`, `pbr_depth_occluded_pixels`,
  `pbr_depth_edge_glow_applied`, and `pbr_depth_edge_glow_pixels` where that
  renderer can report them.

Known limitation: the full GPU helper currently applies video-depth occlusion
as an overlay matte after the model-view render is captured. That closes the
export correctness gap where depth was previously dropped, but it is not yet a
native helper-side model-depth-buffer compare. True per-fragment helper
occlusion should compare video depth against the helper's rendered object depth
buffer once that buffer is exposed in the service path.

Skeletal meshes are supported in the descriptor pipeline and the full GPU helper
now bakes animation before building the model-view vertex buffer. The current
implementation is CPU pose baking plus GPU PBR rendering, not shader skinning:

- glTF/GLB skeletal meshes with `JOINTS_0` / `WEIGHTS_0`, inverse bind matrices,
  bones, and animation clips can be sampled by track `animation.clip`.
- FBX skeletal metadata, cluster weights, and parsed animation curves are
  normalized into the same descriptor shape when available.
- The helper reports `skeletal_animation_applied=true` when a skinned geometry
  is actually deformed for that frame.
- This path is appropriate for export and paused/scrubbed preview quality; live
  playback should keep using packet/low-cost preview until GPU skinning or a
  persistent renderer process lands.
- Blend shapes/morph targets remain future work.

Headless GPU packet QA can be run without opening a Qt window:

```powershell
.\.venv\Scripts\python.exe tools\qa_ar_pbr_gpu_preview.py `
  --out debugCapture\ar_pbr_gpu_preview_qa.json
```

The default QA uses durable PolyHaven PBR samples under
`sample_assets/pbr_blender_scenes/polyhaven` instead of `debugCapture`.
`debugCapture` is scratch-only; generated FBX smoke scenes are still allowed as
temporary fallback output, but required QA/tool sample assets must live under
`sample_assets` or `external/assets`. The report checks mesh triangles, GPU
contact-shadow packets, and GPU reflection packets.

## Editor Transform Gizmo

The editor preview canvas and preview pop-out expose a standard 3D-style
transform gizmo for AR/PBR objects that are explicitly clicked in the viewer:

- Red X, green Y, and blue Z handles perform constrained movement.
- Colored cube handles scale the corresponding axis.
- Colored rotation rings update pitch, yaw, and roll.
- The center handle moves the object in screen plane.
- The white diagonal handle performs uniform scale.

This is a viewport editing layer over AR/PBR `placement` and `transform`
payloads. The handles are drawn inside the viewer, not in an external slider
panel. Track/list selection and numeric parameter editing do not force the
gizmo to appear; it is hidden until the user clicks the visible 3D object in
the preview, and it hides again when the user clicks blank viewer space. Local
X/Y/Z axes and rotation rings are projected from the active gizmo track's
current Euler rotation so the gizmo behaves like a DCC-style
viewport manipulator. The blue Z move handle maps to transform depth in the
current AR/PBR preview camera approximation; exact world-space ray/plane
intersection remains part of the future camera-solve/SLAM path.

Automation and MCP clients must use the registered Python Action System rather
than editor private methods for viewport gizmo control:

- `ar_pbr.gizmo.state` returns selected/visible/active AR/PBR track state.
- `ar_pbr.gizmo.show` shows the viewport gizmo for `track_id`, or the selected
  active AR/PBR track when `track_id` is omitted.
- `ar_pbr.gizmo.hide` hides the viewport gizmo without deselecting the track.

Scene smoke rendering can be run locally:

```powershell
.\.venv\Scripts\python.exe tools\ar_pbr_scene_smoke.py
```

By default, the script writes a generated ASCII FBX scene with rough asphalt,
metallic, and painted materials, imports it, renders a software preview, and
stores the PNG plus diagnostics under `debugCapture/ar_pbr_scene_smoke/`.

External FBX files can be tested without committing them:

```powershell
.\.venv\Scripts\python.exe tools\ar_pbr_scene_smoke.py --asset C:\path\to\scene.fbx
```

Asset support regression over the local sample corpus:

```powershell
.\.venv\Scripts\python.exe tools\qa_ar_pbr_asset_support_matrix.py
```

The matrix checks representative static FBX, skeletal GLB, and unsupported
compressed GLB samples and writes
`debugCapture/ar_pbr_asset_support_matrix_qa.json`.

## First QA Targets

Start with synthetic tests:

- Depth map generation from a synthetic frame.
- Road plane solve from three image points plus depth.
- Road-plane anchor placement from image point to renderer transform.
- PBR-ish generated FBX scene import/render smoke test.
- AR/PBR track schema normalization.
- FBX safe import descriptor and fallback diagnostics.
- Asset support matrix for static FBX, skeletal GLB, and compressed/unsupported
  GLB samples.
- GLB/FBX placeholder placement in a synthetic compositor.
- Depth occlusion mask behavior, including full GPU service depth payload
  serialization and overlay matte application.
- Shadow catcher placeholder behavior.
- Preview/export parity for the compositor contract.
- No-op fallback returns the original frame unchanged.
