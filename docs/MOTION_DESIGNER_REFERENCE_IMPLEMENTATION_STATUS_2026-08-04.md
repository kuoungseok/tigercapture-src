# Motion Designer Reference Implementation Status

Date: 2026-08-04
Scope: the bounded RA reference-alignment implementation, desktop UI, Actions/MCP,
Preview/Export, project portability, and Unreal UMG preflight.

## Decision

The original audit correctly found several Tiger-only approximations. The current
implementation closes the actionable semantic and workflow gaps listed below, but
does not claim Adobe After Effects or Apple Motion project compatibility. Internal
Preview/Export parity and an external product reference comparison remain separate
acceptance claims.

## Implemented

| Area | Current contract | User surface | Evidence boundary |
| --- | --- | --- | --- |
| Unicode text units | Qt grapheme boundary provider with bounded cache | Typography evaluator | Full version-pinned Unicode conformance corpus is still an external acceptance gate. |
| Text selection | `standard_range_selector_v1` plus explicit legacy conversion | Typography Inspector and `motion.text.animator.selector.convert` | Supports percentage/index, character/space-excluding/word/line units, shapes, ease, amount, and selector combination. Wiggly and arbitrary expression selectors are not claimed. |
| Temporal interpolation | neighbor-derived Auto, Continuous, Broken, legacy Tiger Smooth | Graph Editor and Actions | Value/Speed evaluation is shared. This is not an AE project importer. |
| Spatial interpolation | `spatial_bezier_path_v1` | Position Graph commands and `motion.graph.spatial_tangent.update` | Position evaluation uses independent spatial handles. Direct on-canvas path-handle manipulation remains outside this completed command surface. |
| Motion blur | `temporal_shutter_samples_v1` and explicit fast-vector fallback | Advanced Inspector, Preview, Export | Angle/phase samples re-evaluate transform, opacity, repeater, source and puppet state. Full GPU temporal accumulation is not claimed. |
| Behaviors | `tiger_parameter_behavior_v1` | Behavior Inspector and `motion.behavior.contract.inspect` | Deterministic Tiger Fade/Slide/Pop/Spring/Wiggle/Impact/Spin/Drift/Grow/Oscillate/Random Motion; not Apple Behavior compatibility. |
| Repeater | `tiger_repeater_v2` | Repeater Inspector and `motion.replicator.set` | Line/grid/radial/spiral/path, deterministic order, jitter, stagger and reveal fade. Apple 3D/image-cell replicators are not claimed. |
| Puppet | Tiger cutout mesh plus stability diagnostics | Puppet Inspector and Actions | Adaptive mesh, pins, GPU packet and tear repair are supported. Adobe Puppet physics equivalence is not claimed. |
| Reference gate | `tigerstudio.motion.reference_gate.v1` | `motion.reference.gate.compare` | RGBA MAE, maximum error, alpha mismatch and global SSIM are available. A licensed external golden corpus is not bundled. |
| Interaction/data | Tiger button state and UI binding contracts | Button Inspector, Actions, Painter/Web/App/UMG adapters | Normal/hover/pressed/disabled/focus state and trigger/action data are serialized. |
| Expressions | bounded structured operation tree | Actions and expression link UI | No `eval`, JavaScript, scripts or plug-in execution. Cycles and node/depth limits are validated. |
| Portable project | `tigerstudio.motion.runtime_package.v1`, `.tgmotionpkg` | File menu and `motion.package.export/inspect/load` | Local resources are embedded, deduplicated and SHA-256 verified. Remote URLs are references, not downloaded content. |

## Unreal Boundary

Features without native UMG semantics are not silently discarded. Repeater,
temporal motion blur, puppet mesh, structured expressions and behaviors produce an
explicit deterministic-bake requirement in the provider-neutral Tiger UMG document.
The shared `TigerStudioUMG` plugin was rebuilt against `D:\UE_5.8\Engine`; this does
not by itself prove a generated Widget Blueprint for every effect.

## Verification

- Full Motion-selected repository regression: `878 passed, 3224 deselected`.
- Reference, renderer, Action, performance and UMG focused set: `99 passed`.
- Desktop spatial-path, repeater-v2, portable-package and UI focused set:
  `57 passed`.
- Unreal plugin packaging completed from the canonical engine and produced the
  source-free bundled plug-in artifact.
- Architecture and full Motion suites remain mandatory before release because the
  repository is concurrently changing in Painter and editor areas.

## Remaining Product Claims Blocked

- Editable `.aep` playback/write support and Adobe plug-in/expression execution.
- Apple Motion project import or Apple Replicator/Behavior compatibility.
- Pixel-identical external reference parity without a real reference corpus.
- Full-GPU temporal shutter accumulation for all source/effect types.
- Direct canvas editing of spatial path handles.
- Adobe Puppet physics parity and Apple 3D/image-cell replicators.

These are explicit product boundaries, not hidden fallbacks and not automatically
generated follow-up milestones.
