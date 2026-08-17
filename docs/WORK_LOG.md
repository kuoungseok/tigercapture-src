# Work Log

A dated, append-only session diary. Unlike `CHANGELOG.md` (shipped
feature/behaviour changes) or the per-topic handoff docs (deep-dive state for
one work stream, e.g. `docs/FIGMA_UMG_UNREAL_HANDOFF.md`), this file exists so
a new session can answer "what did we just find out / decide, and why" without
re-deriving it. Keep entries short: what was found or decided, and a pointer to
the detailed doc/memory if one exists. Newest entry at the top.

## 2026-08-17

- **Both root causes of the UMG Widget View icon-mangling bug found and fixed**
  (screenshot-verified). (1) `app/painter_ui_umg_simulator.py`
  `project_tiger_umg_document()`: a child whose parent frame was Blocked (e.g.
  `figma_transformed_auto_layout_requires_affine_layout`, so never entered
  `parent_panels`) fell straight to the canvas root, losing every skipped
  ancestor's position offset. Added `_apply_reachable_parent()` to walk up and
  fold each skipped ancestor's own local offset (`Position - Size*Anchor`)
  into the child instead, always landing on true root (never on some
  unrelated Overlay panel, which would apply the wrong slot rules). (2) THE
  ACTUAL VISIBLE BUG: `app/painter_ui_style_renderer.py`
  `draw_ui_vector_paths()` built its SVG `viewBox` from `rect.width()` /
  `rect.height()` (already view-scaled screen pixels) as the fallback
  `source_width`/`source_height`, but the embedded fill-path coordinates are
  in *document* space (e.g. a 386.67-wide hexagon). At 100% zoom the two
  numbers coincide, hiding the bug for years; the UMG Widgets pane fits its
  own panel (scale≈0.406 here), so every boolean-result icon rendered
  `1/scale` (~2.46x) oversized and bled into its neighbours — this, not a
  position bug, is why the donut/hexagon/diamond looked like one overlapping
  blob and "the donut only shows 1/4, looks 4x too big." Source Design looked
  fine because it still has the boolean operands in its own document, so
  `_boolean_path()` succeeds there and never takes this buggy fallback path;
  the UMG projection consumes/drops the operands, forcing the fallback.
  Fixed by dividing by `scale` in the fallback. `pytest
  tests/test_painter_ui_style_renderer.py
  tests/test_painter_ui_boolean_authoring.py` (46 tests) pass. Both fixes are
  **uncommitted** — commit only on explicit instruction. See
  `memory/project_umg_icon_size_mismatch_bug.md` for the full repro/verify
  method (paint a single object to an offscreen QImage with its own
  `_object_rect` outlined in red — mismatch is immediately visible).
- Superseded below: the position-only root cause I originally wrote up
  (effective_parent) was real and worth keeping, but was NOT what caused the
  visible garbling — that was the `draw_ui_vector_paths` scale bug above.
- **Root cause found (not yet fixed)** for the UMG Widget View icon
  size/position bug below: `app/painter_ui_umg_widget_view.py`
  `_UMGWidgetViewPanel.set_document()` (~2743-2744) feeds the "UMG Widgets"
  pane a *different* document (`project_painter_ui_umg_widgets()` ->
  `project_tiger_umg_document()` in `app/painter_ui_umg_simulator.py`) than
  the "Source Design" pane gets. That simulator's parent-panel resolution
  (`painter_ui_umg_simulator.py:1867-1895`, comment: "Mirror
  TigerStudioUMGGeneration.cpp") only registers `Kind == "Group"` layers as
  valid parents; a leaf whose `ParentId` isn't in that set gets silently
  reparented to the canvas root, losing its real parent's transform. Prime
  suspect: the `imagine` wrapper frame (plain, `layout.mode: none`, wraps only
  `Subtract`) likely isn't exported as Kind="Group", so `Subtract` (the donut)
  gets orphaned to root and renders overlapping everything else near the
  origin -- this reads as "4x too big, only 1/4 visible, clipped" (user's
  live-window description) because of the overlap, not an actual size error.
  `iterate`/`make` are direct children of `visual layout` (an auto-layout
  frame, likely exported as Group), so they mostly dodge this path. Because
  the simulator explicitly mirrors the Unreal C++ generator, this may be a
  real Unreal-export bug too, not just a Python preview glitch -- unverified,
  needs an Unreal editor to check. See
  `memory/project_umg_icon_size_mismatch_bug.md` (Claude auto-memory) for the
  full trace and exact next verification steps.
- Confirmed (user-verified against real Figma): in "Auto layout — Cover" >
  "visual layout", icons #1 `iterate` and #3 `make` render at the **same**
  footprint size in Figma and in Painter UI Source Design. Only the UMG
  Widget View (mock render) shows them at different sizes — this is a UMG-only
  render/bake bug, not a document/source discrepancy. (Data-level checks --
  `resolved_rect`, `plan_static_vector_bake`, packaged UMG `Position`/`Size` --
  all came back internally consistent and correct for both icons, so the bug
  is not in geometry resolution; see the simulator finding above instead.)
- Moved the Figma Community sample file ("Auto layout playground") from
  Downloads into `external/assets/figma/fig_native/auto_layout_playground.fig`
  (CC BY 4.0, git-ignored per `external/assets/figma/` `.gitignore` rule — see
  `external/assets/figma/fig_native/SOURCES.md`).
- Started this file. Update it every session with what was found/decided, not
  a transcript of what was tried.
