# AR/PBR Capture Presets

Last updated: 2026-07-05

This file records stable AR/PBR capture presets for product-catalog review
automation. Presets here are source rules, not generated debug evidence.

## Nexus RX Car Catalog Preset

Preset file:

```text
docs/review_automation/presets/ar_pbr_nexus_rx_car.json
```

Use this preset when the catalog needs a vehicle 3D asset instead of repeating
the Poly Haven camera model.

Rules:

- Use the real GLTF asset at
  `E:\ClaudeCodeApp\3d\Nexus_RX-19491522\gltf\converted\nexus_rx_gltf_extracted\scene.gltf`.
- Hide the environment/cubemap background for catalog screenshots.
- Frame the car close enough to show wheels, body panels, and material response.
- Do not use this asset as the only AR/PBR quality proof. The Poly Haven camera
  remains the highest-detail material-quality hero asset.
- Always store the full view state for repeatable catalog framing:
  `pitch`, `yaw`, `roll`, `zoom` or `zoom_factor`, `camera_z`, `pan_x`,
  `pan_y`, and `pan_z`.
- If the user manually adjusts the 3D Preview window, read back the exact view
  with `ar_pbr.preview.view.get` or the review-only
  `review.ar_pbr.preview.view.get`, then update the JSON preset.
- If the preview is launched as a separate standalone process, include
  `--view-state-out <path>` and close the window after manual adjustment. The
  saved JSON contains `view` and `scene_settings` for preset updates.

Current launch pattern:

```text
E:\ClaudeCodeApp\GifCam\.venv\Scripts\python.exe E:\ClaudeCodeApp\GifCam\tools\ar_pbr_preview_window.py --asset E:\ClaudeCodeApp\3d\Nexus_RX-19491522\gltf\converted\nexus_rx_gltf_extracted\scene.gltf --width 1440 --height 1000 --hide-background --pitch 10 --yaw 35 --zoom-factor 1.55 --pan-x 0 --pan-y 0 --pan-z 0 --set render_profile=authored --set hdri_id=wide_street_01 --set ibl_exposure=1.1 --set ibl_rotation=0 --set light_azimuth=45 --set light_elevation=45 --set direct_strength=0.42 --set show_environment_background=false
```

## Space Station Modules Catalog Preset

Preset file:

```text
docs/review_automation/presets/ar_pbr_space_station_modules.json
```

Use this preset for a non-camera hard-surface 3D asset page. The user approved
this asset on 2026-07-05 after rejecting the castle, bicycle collection,
Ancient Corinth, and Spaceship 4 candidates.

Rules:

- Use the real GLTF asset at
  `E:\ClaudeCodeApp\3d\Space_Station_Modules-431ca84e\gltf\converted\space_station_modules_gl_extracted\scene.gltf`.
- Hide the environment/cubemap background for catalog screenshots.
- Use editor-wide HDRI resources under
  `E:\ClaudeCodeApp\GifCam\resources\ar_pbr\hdri`.
- Use this as an approved variety asset beside the higher-detail Poly Haven
  camera hero asset and the Nexus RX vehicle asset.
- Store and replay full view coordinates, including pan, for every accepted
  AR/PBR catalog asset.

Current launch pattern:

```text
E:\ClaudeCodeApp\GifCam\.venv\Scripts\python.exe E:\ClaudeCodeApp\GifCam\tools\ar_pbr_preview_window.py --asset E:\ClaudeCodeApp\3d\Space_Station_Modules-431ca84e\gltf\converted\space_station_modules_gl_extracted\scene.gltf --width 1440 --height 1000 --hide-background --pitch 10 --yaw 35 --zoom-factor 1.25 --pan-x 0 --pan-y 0 --pan-z 0 --set render_profile=authored --set hdri_id=wide_street_01 --set ibl_exposure=1.1 --set ibl_rotation=0 --set light_azimuth=45 --set light_elevation=45 --set direct_strength=0.42 --set show_environment_background=false
```

## Somewhat Recognizable Catalog Preset

Preset file:

```text
docs/review_automation/presets/ar_pbr_somewhat_recognizable.json
```

Use this preset as an additional user-approved AR/PBR model candidate. The user
approved this asset on 2026-07-05 after a real 3D Preview pass.

Rules:

- Use the real GLTF asset at
  `E:\ClaudeCodeApp\3d\Somewhat_Recognizable-668ed982\gltf\converted\somewhat_recognizable_gl_extracted\scene.gltf`.
- Hide the environment/cubemap background for catalog screenshots.
- Replay the saved view and lighting from the preset JSON; do not refit it from
  scratch when generating catalog evidence.
- Use editor-wide HDRI resources under
  `E:\ClaudeCodeApp\GifCam\resources\ar_pbr\hdri`.

## AKS Tactical Upgrade Catalog Preset

Preset file:

```text
docs/review_automation/presets/ar_pbr_aks_tactical_upgrade.json
```

Use this preset for a user-approved hard-surface/material-detail AR/PBR page
when a close technical asset is useful. Prefer neutral assets for broad public
hero pages.

Rules:

- Use the real GLTF asset at
  `E:\ClaudeCodeApp\3d\AKS_Tactical_Upgrade-587e3f02\gltf\converted\akriflefbx_gltf_extracted\scene.gltf`.
- Hide the environment/cubemap background for catalog screenshots.
- Replay the saved user-adjusted view and lighting from the preset JSON.
- Use editor-wide HDRI resources under
  `E:\ClaudeCodeApp\GifCam\resources\ar_pbr\hdri`.

## Rejected AR/PBR Catalog Candidates

These assets were opened in the real 3D Preview and rejected by the user for
catalog/review use. Do not automatically select them for PPT, HTML, or review
screenshots unless the user explicitly revives the asset.

| Date | Asset | Path | Decision |
|---|---|---|---|
| 2026-07-05 | Schwerin Castle | `E:\ClaudeCodeApp\3d\Schwerin_Castle-dff1ffb4\fbx\schwerin-castle_extracted\source\Schwerin_extracted\Schwerin.fbx` | Rejected by user: not usable for catalog/review 3D evidence. |
| 2026-07-05 | Bicycle Collection Free | `E:\ClaudeCodeApp\3d\Bicycle_Collection_Free-0dd4f277\gltf\converted\bicycle_collection_free__extracted\scene.gltf` | Rejected by user: not usable for catalog/review 3D evidence. |
| 2026-07-05 | Ancient Corinth | `E:\ClaudeCodeApp\3d\Ancient_Corinth-69d97182\gltf\converted\ancient_corinth_gltf_extracted\scene.gltf` | Rejected by user: not usable for catalog/review 3D evidence. |
| 2026-07-05 | Spaceship 4 | `E:\ClaudeCodeApp\3d\Spaceship_4-f2bb6a86\gltf\converted\spaceship_4_gltf_extracted\scene.gltf` | Rejected by user: not usable for catalog/review 3D evidence. |
| 2026-07-05 | AK-47 F Modern | `E:\ClaudeCodeApp\3d\AK_47_-_F_Modern-1353e155\gltf\converted\source_gltf_extracted\scene.gltf` | Rejected by user: texture did not render in the real 3D Preview. |
| 2026-07-05 | Police Car | `E:\ClaudeCodeApp\3d\Police_car-009451b7\gltf\converted\police_car_gltf_extracted\scene.gltf` | Rejected by user: wheels did not render correctly in the real 3D Preview. |
