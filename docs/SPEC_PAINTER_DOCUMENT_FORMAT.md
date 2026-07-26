# Tiger Studio Painter Native Document

Status: implemented v1

## Purpose

`.tspaint` is the editable, standalone Tiger Studio Painter document format.
PNG is a flattened delivery format and is not a substitute for project
persistence. A saved Painter document must restore both the painting and the
non-destructive construction state used to continue the work.

## Container

- Extension: `.tspaint`
- Schema: `tigerstudio.painter.document.v1`
- Current format version: `1`
- Container: ZIP with `document.json` plus embedded assets
- Save: atomic temporary-file replacement
- Load: version/schema validation, safe archive paths, asset size limits, and
  SHA-256 verification

Background pixels, clipboard/sticker images, Painter references, and a PBR
source image are embedded when their source files are available. Loading
extracts those assets to a disposable runtime cache; the `.tspaint` file
remains the durable source.

## Persisted Editing State

- canvas dimensions, background pixels/presence/color, and Painter time
- ordered layers, names, visibility, opacity, lock, blend mode, color labels
- layer masks and mask enabled state
- standard and Material Paint layer types and settings
- complete editable strokes, including brush style, pressure, X/Y tilt,
  rotation, tangential pressure, load, bristle seed/count, and material values
- Wet Canvas enabled state, Mix, Bleed, Pickup, dry duration, and elapsed time
- selection geometry/inversion/mode, Quick Mask, channels, and Work Path
- active/selected layer, selected channel/path, grid, mirror, zoom, and pan
- active brush and material-light preview settings
- PBR Texture Lab settings and source
- non-destructive reference board with embedded reference images
- speech bubbles/stickers when present for compatibility

## 3D Blockout Persistence

The underdrawing 3D scene is part of the Painter document, not a disposable
preview. The format preserves:

- primitive kind/name/ID
- position, rotation, scale, color, opacity, wireframe, and lock state
- selected primitive and 3D layer
- Z-up camera target, yaw, pitch, distance, and FOV
- floor/grid, world-aligned checker behavior, Lit mode, shadows, fog, depth
  preview, light yaw/pitch, and snapping
- current Paint/3D workspace and Move/Rotate/Scale mode
- provider-neutral `tigerstudio.painter.ui.v1` UI document, including
  artboards, UI objects, hierarchy, style/content, constraints, selection,
  delivery profiles, and revision
- current Paint/UI Design/3D Place workspace
- UI workspace tool selection is transient, while every drag-created object,
  move, resize, duplicate, delete, visibility, lock, style, and geometry edit
  updates the provider-neutral UI document and participates in Painter
  Undo/Redo
- the UI workspace exposes Select, Frame, Rectangle, Ellipse, Line, Text,
  Image, Button, and Progress tools plus a dedicated `Layers | Inspect` panel
- Inspect edits name, type-readable geometry, opacity, fill, visibility, and
  lock state without converting UI objects into Paint layers

Opening a `.tspaint` restores the editable 3D scene. Baking the blockout to 2D
is optional and does not replace the saved scene.

## UI And Automation

File menu:

- `Open...` (`Ctrl+O`)
- `Save` (`Ctrl+S`)
- `Save As...` (`Ctrl+Shift+S`)
- PNG export remains a separate command

Actions:

- `paint.document.save`
- `paint.document.open`
- `paint.ui.document.inspect`
- `paint.ui.artboard.add/update/remove`
- `paint.ui.object.add/update/remove`
- `paint.ui.delivery.profiles/preflight`
- `paint.ui.handoff.export`
- `paint.state` reports the native format, current path, dirty state, and 3D
  persistence capability, plus the current UI document validation and
  workspace mode

## Compatibility Boundary

The video editor `.tgp` format still owns timeline overlays. `.tspaint` is the
authoritative format for standalone Painter documents and their full 2D/3D
construction and general UI design state. Do not claim that PNG, a generated
handoff package, Unreal UMG, or the legacy stroke-only `.tgp` overlay fields
can replace `.tspaint`.
