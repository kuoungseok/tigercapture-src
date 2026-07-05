# Tiger Studio PBR Blender Sample Pack

This folder contains a small CC0 PBR asset set downloaded from Poly Haven for
Tiger Studio renderer, Blender, AR/PBR compositor, and import QA work.

## Contents

- `models/Camera_01/`
  - `Camera_01_1k.blend`
  - `Camera_01_1k.gltf`
  - `Camera_01_1k.fbx`
  - PBR texture dependencies under `textures/`
- `materials/concrete_floor/`
  - `concrete_floor_1k.blend`
  - `concrete_floor_1k.gltf`
  - PBR texture dependencies under `textures/`
- `hdris/wooden_studio_17/`
  - `wooden_studio_17_1k.hdr`
  - `wooden_studio_17_1k.exr`
  - `wooden_studio_17_2k.hdr`
- `manifest.json`
  - Download metadata, source URLs, expected sizes, and hashes where available.

## Intended Use

- Import `.blend` files in Blender for source-scene inspection.
- Import `.gltf` or `.fbx` in Tiger Studio to test PBR material parsing,
  texture relinking, IBL lighting, model-view preview, and export parity.
- Use `wooden_studio_17_1k.hdr` or `.exr` as a lightweight HDRI/IBL source.
- Use the `2k` HDR only when the preview quality needs a better lighting probe.

## Source And License

Downloaded from Poly Haven:

- Camera 01: https://polyhaven.com/a/Camera_01
- Concrete Floor: https://polyhaven.com/a/concrete_floor
- Wooden Studio 17: https://polyhaven.com/a/wooden_studio_17

Poly Haven publishes its HDRIs, textures, and 3D models as CC0/public domain
assets: https://polyhaven.com/license

The files were fetched through the Poly Haven API/CDN. Poly Haven's public API
requires a unique User-Agent and has separate API usage terms:
https://polyhaven.com/our-api

## Notes

- These are deliberately 1K samples so they stay quick for regression tests.
- HDRI input is equirectangular HDR/EXR. The renderer can convert it to a cube
  map or irradiance/prefilter cache as needed.
- Blender is not required to use the `.gltf` or `.fbx` paths in Tiger Studio.
