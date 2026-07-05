# Editor Menu And Drag Item System

Last updated: 2026-06-29

This spec defines how TigerCapture/Tiger Studio should organize its large editor
surface without losing capability. The direction is item-first: the default
chrome stays quiet and catalog-like, while real operations are exposed as
draggable assets, contextual docks, command palettes, and right-click menus.

## Design Goal

The default editor should resemble the product catalog reference mockups:

- Media Pool on the left as a compact thumbnail list.
- Viewer in the center with real loaded media.
- Timeline lanes as readable layered strips.
- Workbench/Node/Color/Audio/Actor controls on the right as contextual docks.
- Top chrome reduced to a few command groups, not a long row of buttons.
- Dark editor controls with neutral borders; color is reserved for media,
  selected state, scopes, node links, and timeline layers.

The product has many features, so hiding them all in popups would make it look
clean but hard to operate. Popups are for quick choice and search; editing
surfaces must remain visible in docks when active.

## Primary Rule

Every feature that creates or applies something should prefer a draggable item
when that matches the user's mental model.

Examples:

- Media file -> drag to video/audio/actor/3D target.
- Effect preset -> drag to clip.
- Transition preset -> drag to clip boundary.
- Title preset -> drag to text/timeline lane.
- Speed/Fade/Zoom/Text card -> drag to timeline position.
- Live2D/Spine model -> drag to actor lane or empty timeline area.
- 3D asset -> drag to preview/canvas.
- Node/effect -> add at cursor from node graph context menu or palette.

Buttons are for commands. Items are for materials.

## Top Chrome Policy

The default command bar should be reduced to command groups:

- `Project`: new/open/save/recovery/relink/health/QA.
- `Create`: templates, creator assist, script edit, auto polish, subtitles,
  command palette.
- `Actors`: Live2D/Spine add/open/mocap/storyboard/QA.
- `View`: panels, workspace mode, popouts, scopes/mixer, proxy state.
- `More`: diagnostics and lower-frequency tools.
- `Export`: export, render queue, format/fps/resolution/quality.

High-frequency edit actions live near the timeline as icon tools:

- select
- blade/split
- ripple/roll/slip/slide/trim/nest
- marker
- scopes/mixer toggles
- drag cards for fade, speed, zoom, typography, Live2D, Spine

The top bar should not show every feature family as a permanent text button.

## Dock Policy

Use docks for persistent editing context:

- Left dock:
  - Media Pool
  - Actor Library
  - Effect Presets
  - Title Presets
  - Transitions
  - Workflow Presets
  - Future: Node/Effect Palette, Asset Pack Library
- Center:
  - Viewer
  - Play bar
  - Timeline tool palette
  - Timeline lanes
- Right dock:
  - Workbench
  - Node Graph
  - Color controls
  - Mask/rotoscope controls
  - Audio workspace
  - Render Queue
  - Script/AI panels
  - Subtitles
  - PIP/contextual properties

Secondary docks may start collapsed, but the open dock must show the actual UI
inside the dock, not a popup floating away from the related feature.

## Current Drag Sources

| Source | Payload | Current target | Result |
| --- | --- | --- | --- |
| Media Pool item | `text/uri-list` | video/audio rows, empty editor, actor rows, preview for 3D | Adds media to the right timeline/media context. |
| OS file drop | `text/uri-list` | Media Pool, editor, timeline rows, actor lanes, preview | Imports/routs video/audio/actor/3D assets. |
| `FadeCard` | `application/x-tigercapture-transition` | video/audio track row | Adds a fade segment. |
| `SpeedCard` | `application/x-tigercapture-speed` | video track row | Adds/replaces a speed segment. |
| `ZoomCard` | `application/x-tigercapture-zoom` | video track row | Adds a zoom actor. |
| `TypographyCard` | `application/x-tigercapture-text-clip` | video row or text lane | Adds a text clip/actor. |
| `TitlePresetCard` | `application/x-tigercapture-title-preset` | video row or text lane | Adds styled text with animation. |
| `TransitionCard` | `application/x-tigercapture-clip-transition` | clip right edge | Applies clip boundary transition. |
| `EffectPresetCard` | `application/x-tigercapture-effect-preset` | video clip | Applies clip FX preset. |
| `WorkflowPresetCard` | `application/x-tigercapture-editor-preset` | video timeline | Applies a multi-step workflow/template. |
| Live2D card/button | `application/x-live2d-actor-new` | actor lane or tracks host | Adds an empty Live2D actor clip. |
| Live2D viewer model | `application/x-live2d-model` + URL | Live2D lane/tracks host | Adds a Live2D model clip. |
| Spine card/button | `application/x-spine-actor-new` | actor lane or tracks host | Adds an empty Spine actor clip. |
| Spine editor model | `application/x-spine-model` + URL | Spine lane/tracks host | Adds a Spine model clip. |
| 3D asset URL | file URL | preview/canvas/timeline routing | Adds AR/PBR object to preview/composite context. |

## Current Drop Targets

| Target | Accepts | Notes |
| --- | --- | --- |
| `MediaPool` | OS media files | Ingest bin. Items drag out as file URLs. |
| `TrackRow` | fade, transition, text, speed, zoom, title, effect preset, workflow preset, media URLs | Main video edit surface. Drop guide already previews width/details. |
| `TextLaneRow` | text clip MIME | Dedicated typography lane. |
| `AudioTrackRow` | fade MIME, audio/video URLs | Adds audio clips and audio fades. |
| `Live2DActorLaneRow` | Live2D actor/model MIME, Live2D URLs | Adds/places Live2D actor clips. |
| `SpineActorLaneRow` | Spine actor/model MIME, Spine URLs | Adds/places Spine actor clips. |
| Tracks host | Live2D/Spine model or actor MIME | Creates actor lane/clip from empty timeline area. |
| Preview host/label/GL | AR/PBR asset URLs | Places 3D object at preview drop point. |
| Node graph canvas | right-click add at cursor | Needs an item palette later; current add path is context menu/toolbar. |

## UX Problems Found

- The drag system is broad, but the UI does not present all draggable items as
  one coherent asset/palette system.
- The top command bar still exposes too many low-frequency text commands.
- Actor creation exists in top buttons, cards, viewers, and track-host drops;
  it needs one consistent "Actor Library" surface.
- Node add is split between toolbar and right-click menus; it should also have a
  draggable/searchable node palette.
- Media Pool defaults should visually match the catalog list reference, not a
  square contact sheet, for the main editor workspace.
- Existing cards are functional but look like tool buttons. They should read as
  small draggable material swatches.
- Review automation should capture active feature docks and actual dragged item
  outcomes, never generic editor screenshots.

## Current Menu Audit

| Group | Current role | Keep visible? | Item-first rule |
| --- | --- | --- | --- |
| Project | project lifecycle, relink, recovery, health, QA | command menu only | Not draggable; these are application commands. |
| Create | templates, AI command dock, captions, language | command menu only | Templates/workflows should also appear as draggable preset items. |
| Actors | add/open Live2D/Spine, mocap, storyboard, QA | command menu plus Actor Library | Actor creation must be visible as draggable cards. |
| View | workspace mode, panels, popouts, scopes, proxy | command menu only | Not draggable; these are view/state commands. |
| More | lower-frequency timeline and diagnostic actions | command menu only | Move any "creates/applies material" action into a palette later. |
| Export | export, render queue, resolution, FPS, format, quality | command menu plus primary Export button | Not draggable; these are delivery settings. |
| Timeline tools | select, blade, trim, nest, scopes/mixer | compact icon toolbar | Direct edit tools stay near the timeline. |
| Timeline item palette | fade, text, zoom, speed, Live2D, Spine | always available near timeline | Drag to add at a time position. |
| Left item libraries | media, actors, effects, titles, transitions, workflows | dock/palette | Drag item to clip, lane, boundary, or viewer. |

## Item Interaction Rules

- Drag source hover must show the item as a material, not as a generic command
  button.
- Drop targets must highlight only when the item is valid for that target.
- A dropped item must leave visible evidence on the timeline: clip, actor lane,
  effect badge, transition marker, node, keyframes, or control overlay.
- Double-click is allowed as a fallback for opening an editor/viewer, but the
  main creation path should be drag-to-place.
- Right-click/context menus are for advanced options, not the primary way to
  discover item creation.
- Review automation must reject captures where the claimed feature item is not
  visible or the timeline/resulting editor state does not match the claim.
- Review/catalog images must be real editor captures driven from real imported
  media. Use vector/code drawing for icons and frames; do not synthesize fake
  editor feature scenes to stand in for missing UI.

## Visual Reference Alignment

The editor should follow the generated catalog reference style used for the
Node Graph Composition page:

- Top bar is a thin status/header strip: brand, project breadcrumb, compact
  icon-only command menus, and one export entry.
- Feature families should not appear as large text buttons in the top bar.
- Media Pool is a compact thumbnail list.
- Viewer title is short and quiet, with transport controls below it.
- Transport controls use a small previous/play-stop/next cluster, not a large
  hero play button.
- Timeline lanes use stable layer colors:
  - Composite/video: blue
  - Plate/actor: purple
  - Overlay/VFX: teal
  - Sign/title/element: warm orange
  - Grade: olive
  - Audio: green
- Playhead uses a red vertical line with a triangular top marker.
- Keyframe points are diamond-shaped and remain visible on top of layer strips.
- Node selection and node-wire emphasis use cool blue/purple accents instead
  of loud orange unless the state is destructive or warning-level.
- Collapsed palettes may be icon-only, but selected/expanded item panels must
  show short item names so drag targets remain discoverable.

## Required Behavior For Review/Catalog Capture

When review automation captures a feature page:

- The relevant item library or dock must be open.
- The feature item must be visible as an item or selected control.
- The timeline must show the resulting clip/actor/effect/lane.
- The Workbench/Color/Node/Actor/Audio panel must show relevant controls.
- Empty editor states are invalid for public/catalog output.

## Implementation Direction

Short term:

- Collapse the top bar into the command groups listed above.
- Make Media Pool default to list view in the main workspace.
- Keep the timeline drag cards visible near the timeline, but make them neutral
  swatches instead of loud buttons.
- Keep Effect/Title/Transition/Workflow libraries in the left dock.
- Add an Actor Library section in the left dock for Live2D/Spine actor items.
- Keep 3D/AR/PBR assets item-first through Media Pool until a dedicated asset
  pack library exists.

Current implementation status:

- Done: top command groups are present.
- Done: Media Pool defaults to compact list view.
- Done: timeline item palette includes fade/text/zoom/speed/Live2D/Spine.
- Done: Actor Library exposes Live2D and Spine draggable cards in the left dock.
- Partial: 3D assets route through Media Pool and preview/canvas drops.
- Partial: Node graph uses toolbar/right-click creation; a draggable node
  palette is still needed.
- Partial: review automation can capture reports and screenshots, but each
  feature scenario still needs a feature-specific editor state script.

Mid term:

- Add a unified `EditorItemCatalog` model that records item id, label, icon,
  category, MIME type, payload builder, allowed targets, action fallback, and
  review scenario id.
- Use the catalog to populate docks, command palette results, automation
  metadata, and review scenario manifests.
- Add target highlighting that says exactly where an item can be dropped.

Long term:

- Make AI/MCP/local LLM operations choose from the same item catalog when a task
  asks to "add/apply/place" something.
- Expose palette state to review automation so generated decks can prove which
  item was used and where it landed.
