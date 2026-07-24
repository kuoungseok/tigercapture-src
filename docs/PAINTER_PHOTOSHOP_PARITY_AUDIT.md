# Tiger Studio Painter: Photoshop Parity Audit

Updated: 2026-07-25

## Objective

Painter should use the Photoshop desktop mental model without requiring the
user to identify every mismatch. Parity means matching placement, state,
interaction, keyboard behavior, and document results. Similar colors alone do
not count.

Primary references:

- Adobe workspace overview:
  https://helpx.adobe.com/photoshop/desktop/get-started/learn-the-basics/workspace-overview.html
- Adobe toolbar customization:
  https://helpx.adobe.com/photoshop/desktop/get-started/set-up-toolbars-panels/customize-the-toolbar.html
- Adobe Layers panel:
  https://helpx.adobe.com/photoshop/desktop/create-manage-layers/get-started-layers/work-with-the-layers-panel.html
- Adobe Channels:
  https://helpx.adobe.com/photoshop/using/channel-basics.html
- Adobe selections:
  https://helpx.adobe.com/photoshop/using/making-selections.html
- Adobe marquee tools:
  https://helpx.adobe.com/photoshop/using/selecting-marquee-tools.html
- Adobe Color and Swatches:
  https://helpx.adobe.com/photoshop/using/choosing-colors-color-swatches-panels.html

## Workspace Contract

| Area | Photoshop contract | Tiger Studio status |
| --- | --- | --- |
| Menu bar | Flat application menu at the top | Implemented; File/Edit/Image/Layer/Select/View/Window ordering |
| Options bar | Directly below menu; changes with current tool | Implemented for Brush, Eraser, Marquee, Magic Select, Crop, Fill |
| Tools | Compact grouped vertical rail with foreground/background swatches | Implemented |
| Document | Canvas dominates; no decorative card/header | Implemented |
| Status | Bottom zoom and document information | Implemented |
| Right dock | Color and production panels stacked/docked | Implemented baseline |
| Optional panels | Open only when requested | Brush detail, Reference, and 3D hidden by default |
| Responsive | No overlap at 1100x640 and 1300x880 | Screenshot QA required on every structural pass |

The 2026-07-25 contract review also removed the stale requirement for a
permanent Undo/Redo/Export/Zoom command row. Undo/Redo are Edit commands, export
is a File command, zoom is a View/status/canvas-navigation control, and the
options bar is reserved for the active tool. This hierarchy is the durable
specification for future Painter passes.

## Tool And Selection Audit

| Capability | Status | Required follow-up |
| --- | --- | --- |
| Move, Marquee, Magic Select, Crop, Brush, Eraser, Fill, Pen, Hand | Present | Continue icon/shortcut QA |
| New/Add/Subtract/Intersect selection modes | Implemented | Add lasso and polygonal lasso |
| Normal/fixed-ratio marquee options | Implemented | Add fixed-size width/height and feather |
| Marching ants and Quick Mask | Present | Add saved-selection alpha round-trip |
| Magic tolerance | Present | Replace bounding-region approximation with contiguous pixel mask |
| Crop | Selection-based crop present | Add adjustable crop handles, cancel, straighten, overlay |
| Brush options | Size and opacity in top options bar | Add mode, flow, smoothing, tablet pressure toggles |
| Keyboard | V/W/C/B/E/G/P plus edit shortcuts | Add M/Shift+M, L/Shift+L, I, S, J, X/D |

## Color Audit

| Capability | Status | Required follow-up |
| --- | --- | --- |
| Foreground/background colors | Present in tool rail | Add active-well switching and default/swap shortcuts |
| Color field and hue strip | Present | Add RGB/HSB numeric modes and gamut warnings |
| Swatches | Present | Add named groups, create/delete, import/export |
| Gradients/patterns | Basic presets | Add visual thumbnails and editable presets |
| Recent colors | Present | Persist per-user settings |

## Layers Audit

| Capability | Status | Required follow-up |
| --- | --- | --- |
| Eye, thumbnail, name, double-click rename | Present | Keep thumbnail synchronized with all raster data |
| Drag reorder | Implemented and connected to preview/export stroke order | Add autoscroll and multi-select |
| Blend and opacity | Present | Complete blend-mode renderer parity |
| Lock controls | Present | Split transparency/pixels/position/all behavior |
| Masks | Selection/path/channel mask creation present | Add mask thumbnail selection and unlink/disable/delete |
| Bottom actions | New/duplicate/copy/paste/delete present | Replace with Photoshop order: link, fx, mask, adjustment, group, new, delete |
| Groups | Missing | Add nested group model and disclosure rows |
| Merge/flatten | Missing | Add Merge Down, Merge Visible, Flatten |
| Raster layer pixels | Foundational gap | Move fill/import/paste from the single background surface to per-layer raster storage |
| Smart objects/adjustments | Missing | Add only after raster-layer architecture |

## Channels Audit

| Capability | Status | Required follow-up |
| --- | --- | --- |
| RGB/Red/Green/Blue/Alpha thumbnails | Present | Keep channel thumbnails tied to composite layer output |
| Eye visibility | Present | Support Shift multi-channel selection |
| Channel copy/paste | Present | Preserve channel pixel depth and selection semantics |
| Saved alpha channels | Partial single Alpha | Add multiple named alpha channels, reorder, rename, delete |
| Channel to/from selection | Partial | Add explicit bottom-panel actions and automation |

## Paths Audit

| Capability | Status | Required follow-up |
| --- | --- | --- |
| Work Path and saved paths | Present | Add path thumbnail accuracy and rename |
| Path to selection/mask | Present | Add tolerance/feather options |
| Selection to path | Present | Add Make Work Path tolerance |
| Pen editing | Basic point creation | Add anchor selection, handles, add/delete/convert point |
| Path operations | Missing | Add duplicate, reorder, fill path, stroke path |

## Document, Clipboard, And File Audit

| Capability | Status | Required follow-up |
| --- | --- | --- |
| New transparent document | Implemented; checker is display-only | Keep export alpha tests |
| Image Size/Canvas Size/Flip/Crop | Present | Add interpolation and anchor controls |
| Copy/Cut/Paste | Present for current layer/channel contract | Complete raster selection clipboard behavior |
| Open/Save editable document | Missing | Define `.tpaint` versioned document format |
| Place/import as layer | Missing | Depends on per-layer raster storage |
| PNG export | Present | Add JPEG/TIFF/PSD interchange only after format contract |
| Undo/Redo | Present | Add History panel and transaction labels for continuous controls |

## Filters And Adjustments Audit

The Painter UI must not expose fake controls that only resemble Photoshop.
Levels, Curves, Brightness/Contrast, Hue/Saturation, Color Balance, blur,
sharpen, clone/heal, and content-aware operations remain open until their
preview, apply, undo, layer/selection scope, export parity, and action contracts
are real. Existing Tiger Studio color modules should be reused behind a Painter
adapter rather than copied.

## Automation Rule

Every user-facing Painter command must have one registered `paint.*` action,
return state that explains the active document/layer/selection, and use the same
implementation as the UI. New UI-only behavior is incomplete.

Claude/local-agent painting is contracted through `paint.stroke.draw`, using
normalized points and the real Painter brush/render model. Batches are atomic
Painter undo steps exposed through `paint.history.undo` and
`paint.history.redo`; they do not use the video-editor history stack. Agents
should inspect `paint.state` between composition passes and use
`paint.document.export_png` for visual review output.

The agent should work from this audit in priority order and update statuses
without waiting for the user to point out each missing control.

## Implementation Order

1. Workspace/options bar and selection mode parity.
2. Per-layer raster storage, composite renderer, import/place, fill, clipboard.
3. Layer groups, masks, merge/flatten, blend parity.
4. Named alpha channels and full channel-selection round-trip.
5. Pen/path editing and lasso family.
6. Shared adjustment/filter adapters.
7. Editable `.tpaint` document persistence and interchange formats.
8. Shortcut, accessibility, performance, and multi-resolution visual QA.
