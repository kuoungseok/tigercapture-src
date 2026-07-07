# UI Renewal Thread Handoff

## Purpose

This handoff is for the next Codex thread that will continue the main editor UI
renewal while the current thread returns to review automation.

Before using this handoff, read `docs/AGENT_START_HERE.md`. It contains the
global current-session assumptions, including the `debugCapture` boundary,
`video_editor_window.py` boundary, and VTuber/VSeeFace fallback rules that can
affect UI evidence work.

The split is intentional:

- Current thread owner: review automation, PPT/HTML/catalog generation, evidence
  mapping, QA around generated review output.
- New UI-renewal thread owner: live TigerCapture Studio editor UI polish,
  refactoring, feature-specific real editor captures, and updates to the UI
  evidence index when UI screenshots change.

Do not mix the two work streams unless a UI change requires a new evidence
capture path.

## Non-Negotiable Rules

- Work on the real editor UI, not generated catalog composites.
- Product/review evidence must use real TigerCapture screenshots only.
- Use sample media from:
  `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`
- Do not use color bars, placeholder test clips, empty editors, or generated
  fake editor scenes as feature evidence.
- If a feature cannot render correctly, mark it blocked instead of showing a
  fake or broken success image.
- Keep `video_editor_window.py` from growing further where possible. Extract
  bounded UI surfaces into focused modules.
- When a unit of UI work is done, capture the actual editor, compare it against
  the reference direction, then iterate.

## Required Reading Before Editing

Read these first in this order:

1. `docs/AGENT_START_HERE.md`
2. `docs/SPEC_UI_RENEWAL.md`
3. `docs/UI_RENEWAL_EVIDENCE_INDEX.md`
4. `TODO.md`, especially the `Main editor UI renewal return gate` section
5. `docs/SPEC_PYTHON_ACTION_SYSTEM.md` if adding or changing action-driven UI
   captures
6. `app/spine_editor/SPINE_WORK_IN_PROGRESS.md` before touching Spine/NIKKE
   visual claims

## Current Design Direction

The user likes the generated catalog-reference style, but the implementation
must be real UI. The visual target is:

- professional post-production app, not game UI
- dark graphite panels, thin borders, low saturation, subtle depth
- icon-first controls with hover/tooltips or expanded states for labels
- no saturated rainbow button grids unless the feature itself requires color
- compact but readable Media Pool, Viewer, Workbench, and Timeline
- lower Timeline spanning the editor width naturally
- real feature state visible in screenshots: clips, cuts, effects, nodes,
  color, audio, actors, 3D, render queue

Avoid:

- nested cards inside cards
- large black voids
- thick splitters
- fake MacBook/editor composites inside the product UI
- generic repeated screenshots that do not match the feature being explained

## Current Implementation State

The main editor renewal is advanced but not final. Completed or mostly-complete
areas:

- Viewer wording and `Project > name`
- compact Viewer transport controls
- Media Pool left rail polish
- thin shared scrollbar behavior
- preset browser extraction and integrated hover preview
- semantic preset icons
- preset drag/drop guides
- Timeline review framing, cut markers, keyframes, lane density
- Workbench node graph styling
- effect/transition evidence contact sheet
- Color Grading right Workbench with renewed wheels and `StudioSlider`
- Sound Editor embedded Workbench, detached shell, graph/contact-sheet evidence
- Live2D actor Workbench and opt-in Live2D Viewer styling
- AR/PBR object Workbench evidence
- Render Queue panel evidence

Important: "complete" here means good enough for current review automation
evidence. It does not mean every surface has reached the final catalog-grade
look.

## Refactoring Boundaries

Recent extraction already created these boundaries:

- New popout / detached dock / VTuber Studio UI:
  `app/video_editor_popouts.py`
- Screen Studio Auto Polish dialogs:
  `app/video_editor_screenstudio_dialogs.py`
- Command bar helpers:
  `app/video_editor_command_bar.py`
- Timeline palette/tool helpers:
  `app/video_editor_timeline_palette.py`
- Layout/scrollbar/splitter constants:
  `app/video_editor_layout_specs.py`
- AI command dock styling:
  `app/video_editor_ai_command_dock.py`
- Preset browser style:
  `app/video_editor_preset_browser_style.py`
- Preset browser widgets:
  `app/video_editor_preset_browser_widgets.py`
- Preset cards/panels:
  `app/video_editor_preset_cards.py`
- Standard horizontal slider:
  `app/studio_slider.py`
- Sound Editor panel:
  `app/sound_editor_panel.py`

When adding UI, prefer these modules or a new small module. Avoid adding large
new UI classes directly to `app/video_editor_window.py`.

## Evidence Index Contract

`docs/UI_RENEWAL_EVIDENCE_INDEX.md` is the bridge between UI renewal and review
automation. When the UI thread creates a better real screenshot for a feature,
update only that feature row.

Current review automation reads this index through:

- `app/review_automation/ui_evidence_index.py`
- `app/review_automation/artifacts.py`

The review automation thread owns the PPT/HTML generation logic. The UI thread
should not redesign review decks unless explicitly asked.

## Current Evidence Baseline

Use the latest artifacts listed in `docs/UI_RENEWAL_EVIDENCE_INDEX.md`.

Key examples:

- General editor:
  `debugCapture/ui_renewal_effect_workspace_contact_sheet_round_1/editor_effect_stack_action.png`
- Cut/edit:
  `debugCapture/ui_renewal_timeline_review_framing_round_3/editor_cut_edit_action.png`
- Preset browser/drop:
  `debugCapture/ui_renewal_preset_review_contact_sheet_round_1/preset_review_contact_sheet.png`
- Node graph:
  `debugCapture/ui_renewal_node_toolbar_polish_round/editor_workbench_node_graph_action.png`
- Color:
  `debugCapture/ui_renewal_standard_slider_round_1/editor_color_dock_action.png`
- Sound:
  `debugCapture/ui_renewal_sound_editor_full_feature_round_1/sound_editor_graphs_contact_sheet.png`
- Typography:
  `debugCapture/ui_renewal_typography_workspace_round_5/editor_typography_action.png`
- Effects/transitions:
  `debugCapture/ui_renewal_effect_workspace_contact_sheet_round_1/effect_workspace_contact_sheet.png`
- Live2D actor:
  `debugCapture/ui_renewal_live2d_perf_source_round_4/editor_live2d_actor_action.png`
- AR/PBR:
  `debugCapture/ui_renewal_ar_pbr_workspace_round_6/editor_ar_pbr_object_action.png`
- Render queue:
  `debugCapture/ui_renewal_render_queue_workspace_round_8/render_queue_panel_action.png`

## Known Blocked Or Sensitive Areas

- Spine / NIKKE rendering is not visually ready. Do not claim success. Keep it
  visible only as loading/actor-track/compatibility work until transforms,
  draw order, texture binding, and rig rendering are correct.
- Live2D Viewer evidence is opt-in. It has a passing isolated subprocess run,
  but default QA should wait for repeated native shutdown stability.
- AR/PBR evidence is visually usable, but first-class Python Action coverage
  for all placement/material operations is still incomplete.
- AI Script Edit review output remains blocked until the real AI edit corpus has
  20 reviewed transcript/prompt/provider cases. Do not fake that in UI review.

## Recommended Next UI Tasks

1. Run a fresh screenshot audit against the current live editor after reading
   the latest `SPEC_UI_RENEWAL.md`.
2. Pick one surface at a time. Do not restart broad UI redesign.
3. Prioritize remaining weak surfaces:
   - Color page or dedicated color popout if the main-editor Workbench cannot
     match the wide reference.
   - Typography panel density and animation control polish.
   - Transition/effect browser hover preview clarity.
   - Render Queue secondary panel polish.
   - Live2D Viewer repeated stability and visual pass.
   - AR/PBR first-class action surface.
4. After each unit:
   - run the matching `tools/qa_ui_renewal_*.py` capture
   - inspect the image
   - update `docs/UI_RENEWAL_EVIDENCE_INDEX.md` only if the new capture is
     better and still real
   - record the result in `TODO.md`

## Useful QA Commands

Use PowerShell from `E:\ClaudeCodeApp\GifCam`.

```powershell
.\.venv\Scripts\python.exe -m py_compile app\video_editor_window.py
.\.venv\Scripts\python.exe tools\qa_editor_e2e_smoke.py --catalog-capture --import-media "E:\ClaudeCodeApp\ReviewAutomationWorkspace\samples\media\overview_screen_demo.mp4"
.\.venv\Scripts\python.exe tools\qa_ui_renewal_left_rail.py
.\.venv\Scripts\python.exe tools\qa_ui_renewal_workbench.py
.\.venv\Scripts\python.exe tools\qa_workbench_node_action_flow.py
.\.venv\Scripts\python.exe tools\qa_ui_renewal_effect_workspace.py
.\.venv\Scripts\python.exe tools\qa_ui_renewal_sound_editor.py
.\.venv\Scripts\python.exe tools\qa_ui_renewal_typography_workspace.py
.\.venv\Scripts\python.exe tools\qa_ui_renewal_ar_pbr_workspace.py
.\.venv\Scripts\python.exe tools\qa_ui_renewal_render_queue_workspace.py
```

For broader safety after UI changes:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_python_action_system.py tests\test_review_automation_pipeline.py -q
```

## Coordination With Review Automation

The current review automation state is healthy:

- detailed PPT generation works
- HTML generation works
- feature action scenarios are 11/11 ready
- visual review QA reports no missing, small, or flat visual artifacts
- remaining warning is the honest `ai_script_edit` corpus blocker

Do not reset or redesign the review automation pipeline from the UI thread.
Only update evidence captures and the index when the UI improves.

Current generated outputs:

- `E:\ClaudeCodeApp\ReviewAutomationWorkspace\outputs\TigerCapture_Review_Automation_detailed.pptx`
- `E:\ClaudeCodeApp\ReviewAutomationWorkspace\outputs\site\index.html`
- `E:\ClaudeCodeApp\ReviewAutomationWorkspace\outputs\review_report.json`

## First Message To The New UI Thread

Use this as the opening handoff:

```text
You are taking over only the main editor UI renewal work. The current thread is
returning to review automation. Read:

1. docs/UI_RENEWAL_THREAD_HANDOFF.md
2. docs/SPEC_UI_RENEWAL.md
3. docs/UI_RENEWAL_EVIDENCE_INDEX.md
4. TODO.md main editor UI renewal section

Do not redo review automation. Work only on real TigerCapture editor UI.
Use real media from C:\Users\artmouse\Videos\TigerCapture\YouTube Imports.
After every UI unit, run the matching qa_ui_renewal capture, inspect the actual
screenshot, update the evidence index only if the new capture is better, and
record the result in TODO.md.
```
