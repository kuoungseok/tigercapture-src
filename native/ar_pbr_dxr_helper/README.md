# Tiger Studio DXR Helper

This is a headless Direct3D 12 / DXR Tier 1.1 renderer used by Tiger Studio's
AR/PBR subsystem. It uses Shader Model 6.5 inline `RayQuery` traversal and runs
in a separate process so device setup and acceleration-structure work never
enters Painter's stroke path.

The implementation was written against Microsoft's MIT-licensed
DirectX-Graphics-Samples and the Windows SDK API contracts. It does not copy
or redistribute the Microsoft sample runtime.

Commands:

```text
TigerStudioDxrHelper.exe --capabilities-json
TigerStudioDxrHelper.exe --render --mode hybrid_rt --output proof.png
TigerStudioDxrHelper.exe --render --mode path_traced --samples 16 --output proof.png
TigerStudioDxrHelper.exe --render --vertices scene.bin --environment environment-rgba32f.bin --environment-width 1024 --environment-height 512 --output asset.png
```

The output is only labelled hardware RT when the selected adapter reports DXR
Tier 1.1 and Shader Model 6.5 support.

The optional vertex stream is a non-indexed triangle array of 11 little-endian
`float32` values per vertex: position XYZ, normal XYZ, base color RGB,
metallic, and roughness. The optional environment is a row-major linear RGBA
`float32` equirectangular image. `app.ar_pbr.native_rt` owns these conversion
details for normal product use.

Version-one limits are explicit: texture/normal/height sampling, transmission,
soft shadows, denoising, and exact realtime-preview camera parity are not yet
implemented in the native renderer.
