# Comparison Templates

## Purpose

`Comparison Templates` is a product category for tech-demo, review, and proof
videos that show two or more render states side by side. It should not be
implemented as a plain PIP preset category. PIP, crop, mask, typography, and
timeline transforms can be reused internally, but the user-facing feature should
be an editor/viewer comparison system that understands render states.

The core promise is simple:

- Show before and after without manually duplicating, aligning, and cropping
  clips.
- Make the comparison state readable on the video itself with clear
  `Original | After` labels by default.
- Compare effect on/off states such as color grading, blur, sharpen, denoise,
  stabilization, node graph changes, and AI processing.
- Support both one-source comparisons and already-rendered two-source
  comparisons.
- Expose clear action-system commands so Codex, Claude, local AI, and automation
  can create and modify comparisons.

## Product Category

Category title:

`Comparison Templates`

Initial template entries:

| Template | Primary use | Required source mode |
| --- | --- | --- |
| Before / After Split | Classic left/right tech-demo comparison | single or dual |
| Wipe Reveal | Dragging divider or animated reveal between states | single or dual |
| Overlay Fade | Crossfade between before and after over the same frame | single |
| Zoom Detail Compare | Full frame plus magnified before/after detail region | single or dual |
| A/B Grid | Compare two or three variants equally | dual or multi |
| Benchmark Compare | Visual comparison plus metric strips | single or dual |
| Color Grade Compare | Color off/on with optional scopes | single |
| Audio Compare | Waveform/spectrum before/after for sound processing | single or dual |
| UI Renewal Compare | Old UI capture vs renewed UI capture | dual |
| Prompt To Result | Input/source prompt or media vs generated result | dual |

## Source Modes

### Single Source Compare

One timeline clip produces both sides. The editor renders the same source frame
through different render states.

Examples:

- `before`: original media only.
- `after`: current edited result.
- `before`: selected node disabled.
- `after`: selected node enabled.
- `before`: color grade bypassed.
- `after`: color grade applied.

This is the default mode because it removes the most manual work.

### Dual Source Compare

Two existing clips or images are compared.

Examples:

- Old UI recording vs new UI recording.
- External AI render vs TigerCapture render.
- Model A result vs model B result.
- Pre-rendered before video vs pre-rendered after video.

Dual source mode must provide sync offset, crop link, zoom link, and source label
controls.

### Multi Variant Compare

Three or more states are compared in a grid or progression layout.

Examples:

- Original / AI pass / final grade.
- A / B / C model comparison.
- Low / medium / high denoise strength.

This can be a second phase after single and dual source modes are stable.

## Compare Render State

The engine needs an explicit compare render state, not only a visual layout.

Suggested model:

```json
{
  "type": "comparison_view",
  "template_id": "before_after_split",
  "mode": "single_source",
  "layout": "split_vertical",
  "before": {
    "label": "Before",
    "source": "active_clip",
    "render_state": {
      "base": "original",
      "bypass_effects": ["color_grade", "node_graph", "clip_effects"]
    }
  },
  "after": {
    "label": "After",
    "source": "active_clip",
    "render_state": {
      "base": "current_timeline",
      "enabled_effects": ["color_grade", "node_graph", "clip_effects"]
    }
  },
  "viewer": {
    "split": 0.5,
    "labels": true,
    "label_style": "canvas_pill",
    "linked_crop": true,
    "linked_zoom": true
  }
}
```

Required render scopes:

- `original`: raw media frame before TigerCapture edits.
- `current_timeline`: normal current render result.
- `effects_off`: current clip with all clip effects bypassed.
- `color_off`: current clip with color grading bypassed.
- `node_graph_off`: current clip with node graph bypassed.
- `selected_node_off`: current node graph with one selected node bypassed.
- `selected_effect_off`: selected effect disabled.
- `custom`: explicit include/exclude lists for effects and nodes.

The render state should be preview-safe and export-safe. A comparison shown in
the viewer should export the same unless the user marks it as preview-only.

## Viewer Interface

Comparison controls should live in the viewer because users need to judge the
result visually.

Recommended viewer affordances:

- Compare mode button: `Off`, `Split`, `Wipe`, `Overlay`, `Grid`.
- Compact popup list from the compare button; the viewer itself should keep only
  the active state pill and canvas overlays visible.
- Scope selector: `Original / Current`, `Effects Off / On`, `Color Off / On`,
  `Selected Node Off / On`, `Dual Source`.
- Draggable split divider for split and wipe modes.
- Label toggle and label text fields.
- Linked crop/zoom toggle.
- Sync offset for dual source mode.
- Swap before/after button.
- Save as template button.

The interface should feel like an editing instrument, not a marketing overlay.
Use compact icon controls and inline overlays. Avoid large explanatory panels in
the viewer.

## Canvas Overlay Requirements

The actual comparison must be visible on the video canvas, not only in a popup
or inspector.

Default single-source label pair:

- Left/top state: `Original`
- Right/bottom state: `After`

Label requirements:

- `Original | After` must be clearly readable in split and wipe layouts.
- Labels should render as compact high-contrast canvas pills pinned inside each
  comparison region.
- The divider should be visible enough to communicate the split, but calmer than
  the content labels.
- Users must be able to disable labels without disabling the comparison.
- Users must be able to disable the whole comparison and return to normal
  viewer/render output.
- When `exportable` is enabled, labels and content divider are included in
  export unless the user disables them.
- Editing-only handles may remain preview-only and must not be exported unless
  explicitly promoted to content overlays.

## Node And Effect Integration

The feature must be reachable from the places where comparisons are naturally
needed.

Entry points:

- Viewer toolbar: create or toggle comparison.
- Node graph context menu: `Compare this node`.
- Color grading Workbench: `Compare grade`.
- Clip effect row: `Compare effect`.
- AI effect result toast: `Compare before / after`.
- Template browser: `Comparison Templates`.

Required behavior:

- Color grading comparison must bypass only color grade state, not the whole
  edit.
- Blur/sharpen/noise reduction comparison must bypass the selected effect or
  selected node.
- Node graph comparison must support comparing up to a selected node versus the
  full chain.
- If a selected node has dependencies, the system should preserve upstream
  nodes and bypass only the selected node by default.
- A comparison state must be serializable in the project, undoable, and
  accessible to automation.

## Engine Responsibilities

The comparison engine should sit above the existing render path and request
multiple frame variants for the same timeline time.

Responsibilities:

- Resolve the before and after source clips.
- Build render contexts with effect bypass/include rules.
- Render the variants at the same project time.
- Composite the selected comparison layout.
- Keep crop, zoom, pan, and playback synchronized where requested.
- Fall back gracefully when a render state is unsupported.
- Export comparison templates as normal timeline output when active.

PIP can remain an internal layout primitive, but the persisted feature object
should be `comparison_view` or equivalent rather than a generic PIP object.

## Action System

AI and automation must be able to create, update, and export comparisons without
using mouse-only UI.

Current MVP bridge actions already implemented:

| Action | Purpose |
| --- | --- |
| `ui.viewer.compare.set` | Set the active track viewer compare mode to off, original, split, or wipe and optionally toggle `Original | After` labels |
| `ui.viewer.fit` | Invoke the same viewer Fit behavior exposed in the viewer toolbar |

These MVP actions operate on the current preview-only color/node comparison path
and persist `preview_color_compare_mode` plus
`preview_compare_labels_enabled` on the video track. The longer-term
`comparison.*` actions below should become the export-safe comparison object
API once `comparison_view` exists as a first-class project model.

Proposed actions:

| Action | Purpose |
| --- | --- |
| `comparison.create` | Create a comparison template on the active clip or supplied clips |
| `comparison.set_template` | Switch split, wipe, overlay, grid, or detail mode |
| `comparison.set_scope` | Set original/current, color off/on, selected node off/on, etc. |
| `comparison.set_sources` | Assign before and after clips for dual source mode |
| `comparison.set_labels` | Change labels and visibility |
| `comparison.set_split` | Set divider position or wipe animation keyframes |
| `comparison.set_sync` | Set dual-source sync offset |
| `comparison.set_enabled` | Enable or disable the active comparison without deleting it |
| `comparison.toggle_export` | Mark comparison as preview-only or exportable |
| `comparison.remove` | Remove the comparison view |

Example:

```json
{
  "action": "comparison.create",
  "template_id": "before_after_split",
  "mode": "single_source",
  "scope": "selected_node_off_on",
  "track_id": 3,
  "clip_id": 12,
  "node_id": "blur_01"
}
```

## MVP

Build the first version around two templates and four scopes.

MVP templates:

- `Before / After Split`
- `Wipe Reveal`

MVP scopes:

- `Original / Current`
- `Effects Off / On`
- `Color Off / On`
- `Selected Node Off / On`

MVP UI:

- Viewer toolbar compare toggle.
- Compare popup list instead of a permanently expanded viewer panel.
- Visible `Original | After` canvas labels by default.
- Split divider.
- Label toggle.
- Scope selector.
- Node graph context menu entry.
- Color Workbench compare entry.

MVP actions:

- `ui.viewer.compare.set` (implemented bridge)
- `ui.viewer.fit` (implemented viewer utility)
- `comparison.create`
- `comparison.set_enabled`
- `comparison.set_template`
- `comparison.set_scope`
- `comparison.set_split`
- `comparison.remove`

## Phase 2

- `Overlay Fade`
- `Zoom Detail Compare`
- Dual source sync controls.
- Export-safe comparison tracks.
- Benchmark metric strip.
- Audio waveform/spectrum compare.
- Save custom comparison template.

## Phase 3

- A/B/C grid and multi-variant comparison.
- Animated wipe keyframes.
- AI-generated comparison recommendations.
- Auto-detect best comparison scope from the selected tool or last AI action.
- Batch-generate comparison reels from multiple clips.

## Acceptance Criteria

- A user can select one clip, choose `Comparison Templates > Before / After
  Split`, and immediately see original/current comparison without duplicating
  the clip.
- `Original | After` labels are visible on the video canvas by default.
- The user can disable labels while keeping the split comparison active.
- The user can disable the whole comparison and return to normal viewer output.
- A user can select a color grade and compare `Color Off / On` in the viewer.
- A user can right-click a blur node and choose `Compare this node`.
- The split divider can be dragged and exported.
- The same comparison can be created through the action system.
- The comparison state is saved with the project and survives reload.
- Disabling the comparison returns the viewer/export to the normal render path.

## Open Questions

- Should comparison be stored as a timeline item, viewer state, or both?
- Should preview-only comparisons be allowed, or should every comparison be
  exportable by default?
- Should single source `Original` mean raw file only, or raw file plus timeline
  timing transforms such as speed and crop?
- How should comparison interact with nested templates and compound clips?
- Should audio comparison live in the same category or in Sound Editor first?
