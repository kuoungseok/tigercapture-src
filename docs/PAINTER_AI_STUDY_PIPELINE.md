# Painter AI Study Pipeline

## Goal

Claude, OpenAI, and local providers must be able to turn an approved reference
or generated concept into editable Tiger Studio paint layers and real brush
strokes. Providers direct the work; Tiger Studio performs pixel analysis,
stroke planning, rendering, and measurable refinement.

## Non-Negotiable Rules

1. Never ask a language model to invent the complete painting as raw point
   coordinates.
2. Never claim a baked reference image is an editable stroke reconstruction.
3. Keep the approved reference non-destructive and excluded from final export.
4. Segment composition regions before creating detail strokes.
5. Build broad underpainting before contours and focal detail.
6. Derive stroke direction from local image structure, not random decoration.
7. Allocate the highest density to faces, hands, silhouettes, and focal light.
8. Compare every reconstruction pass with the approved reference.
9. Refine only measured high-error regions; do not repeatedly tune the whole
   image by prompt.
10. Do not report completion until quality, editability, performance, action,
    undo, and replay gates pass.

## Action Contract

- `paint.study.analyze_reference`
- `paint.study.segment_regions`
- `paint.study.build_underpaint`
- `paint.study.trace_contours`
- `paint.study.generate_strokes`
- `paint.study.compare_render`
- `paint.study.refine_region`
- `paint.study.quality_report`

All mutating actions must use one named undo transaction, stable layer IDs, and
deterministic seeds. Reports must identify the reference, canvas dimensions,
layer and stroke counts, render time, reconstruction error, focal-region error,
and whether the output contains any baked reference pixels.

## Quality Gates

- The reference image is not present as an exported sticker or raster shortcut.
- Every visible reconstruction mark belongs to an editable paint layer.
- Silhouette and focal-region error improve after refinement.
- The face, hands, principal subject, and primary light remain recognizable at
  fit-to-window scale.
- Repeated identical symbols, uniform dots, and whole-canvas decorative hatching
  fail review.
- The result must survive save/replay and PNG export with canvas/export brush
  parity.
- A provider may stop only when `paint.study.quality_report` returns `ready`.

## Provider Responsibilities

Providers choose the approved concept, semantic priorities, layer organization,
brush families, and refinement order. They inspect real Painter renders between
passes. They do not approximate image analysis in prose when a `paint.study.*`
action can perform it deterministically.

## Verified Production Proof

The durable QA command is:

```powershell
.\.venv\Scripts\python.exe tools\reconstruct_painter_reference_strokes.py `
  external\assets\painter_references\moonlit_woman_oil_reference.png `
  --output external\assets\painter_openai_agent\moonlit_woman_ai_study_final_v7.png `
  --width 800 --refinement-passes 1 `
  --focus-region "face,0.29,0.14,0.46,0.36,3.0" `
  --focus-region "hands,0.32,0.43,0.61,0.62,2.7" `
  --focus-region "figure,0.16,0.22,0.78,0.97,1.4"
```

Verified result:

- `status=ready`
- 21,199 editable strokes
- six generated layers (five study passes and one measured refinement pass)
- no baked reference pixels
- mean absolute RGB error `8.729/255`
- luminance correlation `0.928`
- structural-edge F1 `0.643`
- face focus-region error `9.056/255`
- hands focus-region error `11.834/255`

The output and JSON action log are regenerable QA evidence and therefore remain
ignored local assets rather than source dependencies.
