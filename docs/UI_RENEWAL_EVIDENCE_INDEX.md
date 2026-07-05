# UI Renewal Evidence Index

This file is the handoff index for renewed main-editor evidence. Review/PPT/HTML
automation should use these real editor captures instead of generated editor
mockups or generic empty screenshots.

## Rules

- Use real TigerCapture UI captures only.
- Use media from `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`.
- Do not use color bars, placeholder test footage, empty editors, or generated
  fake editor scenes as product evidence.
- If a feature cannot render correct pixels, record it as blocked rather than
  showing a broken or fake success image.
- Before regenerating product review output, re-run or refresh any stale capture
  whose source UI or action contract has changed.
- Do not use old versioned catalog asset folders such as
  `outputs/TigerCapture_Product_Catalog_EN_v*_assets` as fresh product
  evidence. They are historical output, not current UI evidence.
- When a source video contains a face, eye, macro skin detail, color bars, or
  test-looking frame, choose a different timestamp from the same real video or
  use another approved YouTube Imports clip.
- Even inside an approved source video, do not accept an arbitrary decoded
  frame. Prefer catalog-worthy timestamps with a clear subject and attractive
  composition, such as Taichung night skyline `00:34` / `01:42`, Tokyo aerial
  `02:23`, Lamborghini driving `01:26`, South Korea bridge/skylines `03:51` /
  `09:24`, and Fallingwater exterior `03:55` / `13:28`.
- Treat user-picked timestamps as candidates. When a candidate is visibly
  blurred, too dark, too empty, or awkwardly cropped, replace it with a prettier
  frame from the same approved video rather than forcing the exact timestamp.
- Live2D catalog captures must use a calm, low-detail background. Avoid dense
  city/night aerials behind the actor unless the slide is explicitly about
  compositing complexity.
- Timeline evidence must reflect the current timeline renderer. If thumbnail
  rendering changes, regenerate the editor screenshot instead of reusing an
  older crop or previous PPT asset.

## Current Feature Evidence

| Feature area | Action-backed source | Latest artifact | Review use |
| --- | --- | --- | --- |
| Main editor shell / media pool / timeline | `tools/qa_ui_renewal_effect_workspace.py` | `debugCapture/ui_renewal_effect_workspace_contact_sheet_round_1/editor_effect_stack_action.png` | General overview only, not a feature-detail slide. |
| Cut / edit point | `tools/qa_ui_renewal_cut_edit_workspace.py` | `debugCapture/ui_renewal_timeline_review_framing_round_3/editor_cut_edit_action.png` | Cut/split/marker/transition edit workflow. |
| Preset browser | `tools/qa_ui_renewal_preset_browser_left_dock.py --section ...` | `debugCapture/ui_renewal_preset_semantic_icons_round_2/left_dock_transitions_browser.png` | Left-dock preset browsing and hover prediction. |
| Preset drag/drop guides | `tools/qa_ui_renewal_preset_drop_guides.py` + `tools/qa_ui_renewal_preset_browser_left_dock.py` | `debugCapture/ui_renewal_preset_review_contact_sheet_round_1/preset_review_contact_sheet.png` | Preset browser, hover context, drag intent, target lanes, and cut-edge placement. |
| Node graph | `tools/qa_ui_renewal_workbench.py` / `tools/qa_workbench_node_action_flow.py` | `debugCapture/ui_renewal_node_toolbar_polish_round/editor_workbench_node_graph_action.png` | Connected node graph and inline node controls. |
| Color grading | `tools/qa_workbench_node_action_flow.py` | `debugCapture/ui_renewal_standard_slider_round_1/editor_color_dock_action.png` | Color wheels, sliders, scopes, and timeline grade evidence. |
| Audio mixer / extracted audio | `tools/qa_ui_renewal_sound_editor.py` | `debugCapture/ui_renewal_sound_editor_full_feature_round_1/sound_editor_graphs_contact_sheet.png` | Waveform, spectrum, levels, EQ/Dynamics/FX/AI graphs. |
| Typography | `tools/qa_ui_renewal_typography_workspace.py` | `debugCapture/ui_renewal_typography_workspace_round_5/editor_typography_action.png` | Text layer, keyframes, animation, and preview overlay. |
| Effects / transitions | `tools/qa_ui_renewal_effect_workspace.py` | `debugCapture/ui_renewal_effect_workspace_contact_sheet_round_1/effect_workspace_contact_sheet.png` | Real split clip, FX/TR badges, transition edge, Workbench node stack. |
| Live2D actor | `tools/qa_ui_renewal_actor_workspaces.py` | `debugCapture/ui_renewal_live2d_perf_source_round_4/editor_live2d_actor_action.png` | Actor lane, keyframes, Performance Source, and Workbench mapping. |
| Live2D Viewer | `tools/qa_ui_renewal_live2d_viewer_isolated.py` | `debugCapture/ui_renewal_live2d_viewer_isolated_round_2/live2d_viewer_action.png` | Opt-in viewer evidence only; keep outside default QA until repeated native shutdown stability is proven. |
| Spine / NIKKE actors | `app/spine_editor/SPINE_WORK_IN_PROGRESS.md` | blocked | Do not use as visual success evidence until rendering, transforms, draw order, and assets are correct. |
| AR/PBR / 3D object | `tools/qa_ui_renewal_ar_pbr_workspace.py` | `debugCapture/ui_renewal_ar_pbr_workspace_round_6/editor_ar_pbr_object_action.png` | Real GLB placement, transform, lighting, and material controls. |
| Render queue / export | `tools/qa_ui_renewal_render_queue_workspace.py` | `debugCapture/ui_renewal_render_queue_workspace_round_8/render_queue_panel_action.png` | Staged render queue jobs and export-readiness controls. |

## Open Review Automation Handoff

The next review automation pass should map detailed deck topics to the artifact
ids above, then regenerate PPT/HTML from those real captures. If a topic needs a
new feature state, create or extend an action-backed QA capture first.

## Current Reference Gaps

- Catalog framing is still separate from real editor evidence. The catalog can
  place these screenshots inside a MacBook/monitor or gallery page frame, but
  the screen content must remain one of the real captures listed above.
- The main editor is now close to the generated reference in layout language,
  but it remains denser than the mockup because it must expose real Media Pool,
  Workbench, Timeline, AI command, and preset-browser state at once.
- Color grading is the closest dedicated workspace to the generated style, but
  the exact wide grading-console composition still belongs in a future Color
  page or popout. The main-editor Workbench version is a functional compromise.
- AR/PBR evidence is real and visually usable, but the current QA still calls
  the editor placement helper directly; a first-class Python Action surface is
  still pending.
- Live2D Viewer evidence is opt-in and isolated. The latest subprocess returned
  `0`, but default QA should wait for repeated native shutdown stability.
- Spine/NIKKE visual evidence remains blocked until rendering, transforms, draw
  order, and asset binding issues are fixed. Do not replace this with generated
  art or placeholder screenshots.
