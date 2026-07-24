# Single Image Object Motion Showcase

## Purpose

This sample proves object-level motion from one source image. It does not swap
rectangular image cards.

## Durable Inputs

- `single_source_character_car.png`: one flattened source containing a
  character, a car, and a street background.
- `single_source_clean_background.png`: a reviewed clean plate for the same
  camera view.

## Pipeline

1. Fit the source to a 720 x 1280 vertical canvas.
2. Pass named normalized boxes for `character` and `car`.
3. Add foreground points on both legs/shoes and background points in the leg
   gap when dark clothing overlaps a dark road.
4. Run an independent seeded local GrabCut pass for each object while
   preserving disconnected parts that belong to the same object.
5. Save each mask and RGBA cutout as a separate editable image layer.
6. Replace weak large-hole local inpainting with the reviewed clean plate.
7. Animate the character and car independently with position, scale, Z
   rotation, X/Y perspective tilt, and different keyframe timing.
8. Render Preview and H.264 MP4 through the same Motion renderer.

## Regeneration

```powershell
.\.venv\Scripts\python.exe tools\create_omni_object_motion_showcase.py
```

Disposable evidence is written under
`debugCapture/motion_ai_showcase/omni_object_motion`.

## Product Boundary

The base installation supports named box-guided multi-object extraction plus
optional foreground/background correction points. Automatic local object
proposals are best-effort; optional semantic detector models or SAM are still
needed for prompt-only discovery on arbitrary complex images.
