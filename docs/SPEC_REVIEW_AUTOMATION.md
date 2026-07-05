# TigerCapture Review Automation Plan

Last updated: 2026-07-03

Canonical rule hub:

```text
docs/review_automation/
```

New agents should start with:

```text
docs/review_automation/AGENT_START_HERE.md
```

Use that folder first for review automation purpose, catalog PPT style,
presentation scenario, template assets, and TODO. This expanded spec remains a
supporting reference.

This document defines the automated review/demo asset pipeline for
TigerCapture. It is a developer-only review program with its own workspace
root, separate from TigerCapture/TigerStudio product roots. It is separate from
ordinary QA, but it should reuse QA fixtures and QA proof wherever possible.

## Product Promotion Purpose Rule

Despite the name, review automation is not a code-review system, a QA status
report generator, or a release dashboard. Its primary purpose is to explain and
promote the product: what TigerCapture/Tiger Studio can do, what a creator can
make with it, and how the tool feels in real editing use.

Therefore product-facing review outputs must behave like a product catalog or
studio tour, not like an engineering report:

- Explain features through realistic editor work, not raw QA rows.
- Show what users can create with the tool, not what internal tests passed.
- Use QA/action evidence only as hidden backing data or internal appendix
  material.
- Prefer cinematic device and workspace presentation, including the laptop
  template and multi-monitor template, because those templates exist to make
  the product story tangible.
- Do not use screenshots whose main message is code review, QA status,
  readiness numbers, JSON reports, or implementation health.

## Catalog PPT Design Source Rule

For review automation, the design reference means the product catalog PPT
system only. Do not use main-editor UI-renewal rules, runtime Qt style tokens,
or app widget font rules as the typography/layout source for review PPT pages.

Use these as the catalog PPT design sources:

- `docs/review_reference_featpaper_style.md`
- this document's catalog/PPT rules
- `docs/CURRENT_SPEC_PRESENTATION_SCENARIO.md` visual doctrine
- laptop and multi-monitor catalog templates

The live editor UI specs and code are still inspected only to know what real
screens can be captured. They are not the catalog PPT font, spacing, or page
layout authority. In short: the editor UI is the photographed product; the
catalog PPT rules are the presentation frame.

## Goal

Review automation should run product workflows without a human operator and
produce:

- Overview screenshots.
- Feature screenshots.
- GIF or short MP4 clips.
- Contact sheets.
- Evidence JSON.
- Static HTML pages.
- PPTX/deck-ready image sets.

The output is both product evidence and introduction material. A generated page
must not claim more than the current implementation and release-positioning
guardrails allow.

## Review Program Root

Review automation needs a stable private workspace root. By default it is a
sibling of the product checkout:

```text
../ReviewAutomationWorkspace/
```

This can be overridden for a fully external disk/location:

```powershell
set TIGERCAPTURE_REVIEW_ROOT=D:\TigerReviewAutomation
```

The default layout is:

```text
../ReviewAutomationWorkspace/samples/manifest.json
../ReviewAutomationWorkspace/samples/media/
../ReviewAutomationWorkspace/outputs/
../ReviewAutomationWorkspace/qa/
```

Generated media is created locally by:

```powershell
.\.venv\Scripts\python.exe tools\prepare_review_sample_resources.py
```

Editor-work sample videos are sourced first from:

```text
C:\Users\artmouse\Videos\TigerCapture\YouTube Imports
```

The tool converts imported videos into short 1280x720 review clips under
`../ReviewAutomationWorkspace/samples/media/`. Public review generation must use
real videos from this folder. If no usable imported video is available, the
sample report is not ready and the review deck must not silently substitute
test-pattern media. Override the folder with `--video-source-dir` or
`TIGERCAPTURE_REVIEW_VIDEO_SOURCE_DIR`; use `--synthetic-video` only for explicit
internal debugging.

The manifest is the stable contract; large generated media should not be
committed unless release policy changes.

## Developer-Only Access

Review automation is not a normal user feature. It is visible and runnable only
when one of these is true:

```powershell
set TIGERCAPTURE_REVIEW_AUTOMATION=1
set TIGERCAPTURE_DEV_TOOLS=1
set TIGERCAPTURE_DEVELOPER=1
```

or the tool is running from a source checkout that has `.git` and
`tools/review_automation_launcher.py`. Frozen/packaged app builds should not
show the QA Dashboard review rows or run the review automation CLI.

## Why A Separate Sample Folder Is Needed

Ordinary QA fixtures can be synthetic, minimal, and optimized for assertions.
Review automation needs media that is stable enough for screenshots and
readable enough for public/internal presentation.

The review sample folder prevents:

- Feature demos depending on random user projects.
- Marketing screenshots accidentally using private media.
- QA corpus layout changes breaking introduction pages.
- Public output leaking local test paths or third-party resources.

## Initial Sample Types

The first manifest covers:

- Overview screen video.
- Screen Studio Auto Polish video plus cursor sidecar.
- Dialogue/audio cleanup sample.
- AI Script Edit transcript sample.
- Overview poster image for HTML/deck generation.

The manifest is produced by `app.review_automation.sample_resources`.

## Future Pipeline

Planned modules:

```text
app/review_automation/registry.py
app/review_automation/runner.py
app/review_automation/capture.py
app/review_automation/html_export.py
app/review_automation/ppt_export.py
app/review_automation/scenario_manifest.py
app/review_automation/evidence_graph.py
```

Planned tools:

```text
tools/generate_review_assets.py
tools/build_review_office_decks.py
tools/build_review_site.py
tools/build_review_deck.py
tools/qa_review_automation.py
```

## Current Spec Discovery Rule

Before regenerating or rewriting any review PPTX, deck image set, catalog page,
or HTML review output, the pipeline and operator must re-discover the current
project spec first. TigerCapture/TigerStudio changes continuously, so a deck
must never be rebuilt from stale memory or an old slide outline.

Minimum required inputs to inspect before deck generation:

- `SPEC.md`
- `README.md`
- `TODO.md`
- `docs/RELEASE_POSITIONING.md`
- `docs/SPEC_REVIEW_AUTOMATION.md`
- `docs/SPEC_PYTHON_ACTION_SYSTEM.md`
- feature-specific spec files under `docs/SPEC_*.md`
- registered Python Action System catalog from `app/actions/registry.py`
- current review sample manifest and review report under
  `../ReviewAutomationWorkspace/`
- latest relevant QA reports under `debugCapture/` and
  `../ReviewAutomationWorkspace/qa/`

The generated review report should record which spec files and action catalog
were inspected, with timestamps or hashes. If this discovery step is skipped or
fails, the output must be marked `stale` or `spec_unverified`, even if images can
still be generated.

## Staleness Handling

Generated review output should record hashes or timestamps for:

- `SPEC.md`
- `README.md`
- `TODO.md`
- `docs/RELEASE_POSITIONING.md`
- `../ReviewAutomationWorkspace/samples/manifest.json`
- referenced QA reports

If these inputs change, review artifacts should be marked stale until
regenerated.

## Claim Safety

Review pages and decks must obey `docs/RELEASE_POSITIONING.md`.

Feature states should be explicit:

- `implemented`
- `evidence_ready`
- `safe_to_market`
- `planned`
- `blocked`
- `stale`

Failed or missing evidence should be visible, not silently omitted.

## Public Catalog Visual Rule

Public catalog screenshots and deck images must never show an empty editor
surface. A catalog editor image is valid only when it looks like a real editing
session in progress:

- A real review sample video frame is visible in the preview.
- Timeline lanes contain clip thumbnails or visible edit segments.
- At least one active edit indicator is visible, such as a playhead, cut,
  filter, color grade, typography/keyframe, audio, Live2D, or node lane marker.
- The catalog timeline detail image must be a zoomed-in active timeline crop,
  not a blank timeline or empty app shell.

The catalog surface must come from a real editor capture after the review
automation imports a real YouTube Imports clip into the timeline. Cropping or
zooming that capture is allowed; drawing a fake editor scene or falling back to
`editor_empty.png` is not allowed for public catalog assets. QA enforces this
with the `no_empty_editor` catalog artifact rule.

## Product Catalog No-QA-Metrics Rule

Summary, detailed, catalog, website, and phone-preview slides are product
catalog material first. They must not look like QA dashboards or internal
release reports.

Do not show these on product-facing catalog slides:

- QA scores, readiness scores, pass/fail counts, or pass rates.
- Action registry counts, action execution counts, or evidence row counts.
- Raw report tables, raw JSON, file path lists, debug logs, or release boolean
  fields such as `release_ready=false`.
- Large "status: passed/failed" blocks or appendix-style diagnostic summaries.

Product-facing slides may say that a feature is evidence-backed, guarded,
pending, or blocked, but the numeric and diagnostic details belong only in
`evidence-full`, internal QA pages, JSON metadata, or developer reports.

## Multi-Monitor Presentation Rule

When a review/PPT/HTML page explains multi-monitor or multi-environment editing,
use the dedicated three-monitor presentation asset set:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_catalog_template.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_catalog_template.screen-map.json
docs/MULTI_MONITOR_REVIEW_SCENARIO_RULES.md
```

The monitor frame/template may be generated or staged, but the content inserted
into each monitor must be real TigerCapture screenshots. The replacement regions
come only from the `.screen-map.json` file; preserve the monitor bezels, stands,
logos, shadows, and background.

The selected template has angled left and right monitors. Those side captures
must be perspective-warped into the `quad` coordinates from the screen-map JSON.
This warp applies only to inserted screen pixels and must never transform the
monitor body or slide template.

Required monitor meaning:

- Left monitor: real supporting workspace capture, such as Media Pool, project
  bin, import/workflow panel, asset browser, or timeline support view.
- Center monitor: real main editor capture with Viewer, active timeline, real
  media frame, clips, playhead, and current edit context.
- Right monitor: real detached or independent tool surface, such as Node Graph,
  color scopes, Inspector, Audio Mixer, Render Queue, QA Dashboard, or Workbench.

Do not place generated/fake UI inside the monitor screens. Do not use empty
editors, placeholder bars, generic test media, or explanatory labels inside the
final image. If real multi-monitor captures are unavailable, the asset should be
marked pending rather than faked.

## Review-Only Window Action Layer

Multi-monitor evidence needs window choreography that should not be exposed as
normal editing automation. Keep this layer separate from the main Python Action
System and MCP action catalog. The review-only implementation lives under:

```text
app/review_automation/window_actions.py
```

These action ids are reserved for review capture orchestration only:

- `review.ui.popout.open`
- `review.ui.popout.close`
- `review.ui.window.open`
- `review.ui.window.set_geometry`
- `review.ui.window.visibility`
- `review.capture.window`
- `review.capture.screen_region`
- `review.multi_monitor.capture_slots`
- `review.multi_monitor.compose`

They must not be registered in `app/actions/registry.py`. They are allowed to
open, show, hide, move, resize, raise, and capture editor popout windows because
their only purpose is developer-only review/PPT/HTML evidence generation.
The public entry point is the existing review scenario route:
`review.scenario.run` with `scenario="multi-monitor-capture"`, which internally
dispatches to the review-only runner.

The capture rule is show-then-capture by default. General Qt widgets may be
capturable while hidden, but Viewer/GPU/OpenGL/video preview surfaces can render
black when hidden. Review automation should therefore briefly show, raise, and
settle the target window before capture, then proceed to the next staged slot.
Use hidden/grab-only capture only for explicit internal tests.

Recommended multi-monitor automation flow:

1. Prepare a real editing project with real sample media imported into the
   timeline.
2. For a slot, open the required popouts or docks, set geometry, and hide
   unrelated windows.
3. Capture the visible window or screen region into a slot image.
4. Repeat for the left, center, and right monitor slots.
5. Compose the three slot images into the monitor template using the screen-map
   JSON.

Physical monitors are optional. If three real monitors are available, the same
actions can place windows on those screens. If not, a single capture stage can
be reused sequentially; each inserted monitor screen remains a real
TigerCapture capture.

## Feature Explanation Screenshot Rule

Summary decks may use a compact overview composition, but detailed and
evidence-full review decks must not explain major features with text alone.
Every feature-group explanation slide needs an editor-work screenshot artifact
that shows the feature being operated or reviewed inside the product context.

The current contract is:

- Each detailed topic has a stable artifact id:
  `feature_<topic_id>_editor_surface`.
- The artifact must be a screenshot/image, not a raw text report.
- The screenshot must show a populated preview/timeline/workbench state tied to
  the feature being explained.
- If a live UI capture backend exists, it should generate the artifact by
  driving registered Python actions and capturing the editor.
- If live capture is unavailable, the artifact remains missing/pending. The deck
  may show the missing-evidence state, but it must not generate a fake feature
  editor surface.

QA fails when these feature editor screenshot artifacts are missing. This keeps
the detailed deck from regressing into a text-only spec summary.

## Feature Action Scenario Rule

Each detailed feature screenshot also needs a matching registered-action
scenario. This is the bridge between humanless QA-style operation and catalog
material:

- Each feature topic has a scenario id:
  `feature_<topic_id>_action_review`.
- Each scenario must list only registered Python Action System action ids.
- Each scenario must end in a `capture.screenshot` action targeting the matching
  `feature_<topic_id>_editor_surface` artifact.
- The aggregate trace is written to
  `../ReviewAutomationWorkspace/outputs/action_scenarios/feature_action_scenarios.json`.
- `review_report.json` exposes the same rows as `feature_action_scenarios`.
- The evidence graph links feature -> feature action scenario -> actions ->
  screenshot artifact.

Live owner behavior:

- When `review.scenario.run` is executed against a running `VideoEditorWindow`
  owner, the editor routes it to the live review runner.
- `scenario="live-feature-captures"` runs all feature action scenarios against
  the live editor, mutates the timeline through the registered Python Action
  System, and writes live screenshots to the matching
  `feature_<topic_id>_editor_surface` artifact paths.
- A single topic can be captured with either the topic id, for example
  `timeline_editing`, or the scenario id
  `feature_timeline_editing_action_review`.
- Live capture evidence is written to
  `../ReviewAutomationWorkspace/outputs/action_scenarios/feature_action_scenarios_live.json`.
- The normal review report generator overlays that live evidence onto
  `feature_action_scenarios`, changing matching rows to `live_captured`.

Standalone CLI/MCP tools that construct `AutomationBridge(None)` or
`AutomationMCPServer(None)` remain ownerless and can only do schema/list,
dry-run, and headless fallback work. They cannot mutate or capture a currently
open editor unless they are called through the running editor owner or a future
developer-only live IPC bridge.

## Current Implementation

Implemented now:

- `app.review_automation.paths`
- `app.review_automation.dev_gate`
- `app.review_automation.sample_resources`
- `app.review_automation.registry`
- `app.review_automation.artifacts`
- `app.review_automation.html_export`
- `app.review_automation.ppt_export`
- `app.review_automation.runner`
- `app.review_automation.deck_modes`
- `app.review_automation.scenario_manifest`
- `app.review_automation.feature_action_scenarios`
- `app.review_automation.live_runner`
- `app.review_automation.evidence_graph`
- `tools/prepare_review_sample_resources.py`
- `tools/generate_review_assets.py`
- `tools/build_review_office_decks.py`
- `tools/review_automation_launcher.py`
- `tools/build_review_site.py`
- `tools/build_review_deck.py`
- `tools/qa_review_automation.py`
- `tests/test_review_sample_resources.py`
- `tests/test_review_automation_pipeline.py`
- QA Dashboard rows:
  - `Review Sample Resources`
  - `Review Automation`
  - `Review Automation QA`

Default full build:

```powershell
.\.venv\Scripts\python.exe tools\generate_review_assets.py
```

Interactive selector:

```powershell
GenerateReviewAssets.bat
ReviewAutomationSelector.bat
BuildReviewOfficeDecks.bat
```

Deck modes:

```powershell
.\.venv\Scripts\python.exe tools\generate_review_assets.py --deck-mode summary
.\.venv\Scripts\python.exe tools\generate_review_assets.py --deck-mode detailed
.\.venv\Scripts\python.exe tools\generate_review_assets.py --deck-mode evidence-full
```

Office-valid deck build with feature editor screenshots:

```powershell
.\.venv\Scripts\python.exe tools\build_review_office_decks.py --deck-mode all --force
.\.venv\Scripts\python.exe tools\build_review_office_decks.py --deck-mode all --locale ko --force
.\.venv\Scripts\python.exe tools\build_review_office_decks.py --deck-mode all --locale both --force
BuildReviewOfficeDecks.bat
```

This path renders review slides to PNG first and then asks installed
PowerPoint to save the final PPTX files. Use it for decks that will be opened
or presented in Office.

Locale behavior:

- `--locale en`: default English catalog decks.
- `--locale ko`: Korean catalog decks with CJK-safe `Malgun Gothic` rendering.
- `--locale both`: English and Korean decks in one run.

- `summary`: quick 4-slide introduction.
- `detailed`: feature-group presentation generated from README, SPEC,
  QA Dashboard, and review evidence.
- `evidence-full`: appendix-style deck that includes QA Dashboard evidence rows.

This writes:

```text
../ReviewAutomationWorkspace/outputs/review_report.json
../ReviewAutomationWorkspace/outputs/site/index.html
../ReviewAutomationWorkspace/outputs/site/features/*.html
../ReviewAutomationWorkspace/outputs/TigerCapture_Review_Automation.pptx
../ReviewAutomationWorkspace/outputs/TigerCapture_Review_Automation_detailed.pptx
../ReviewAutomationWorkspace/outputs/TigerCapture_Review_Automation_evidence_full.pptx
../ReviewAutomationWorkspace/outputs/TigerCapture_Review_Automation_ko.pptx
../ReviewAutomationWorkspace/outputs/TigerCapture_Review_Automation_detailed_ko.pptx
../ReviewAutomationWorkspace/outputs/TigerCapture_Review_Automation_evidence_full_ko.pptx
../ReviewAutomationWorkspace/outputs/assets/*
../ReviewAutomationWorkspace/qa/review_sample_resources_qa.json
../ReviewAutomationWorkspace/qa/review_automation_qa.json
```

Optional focused builds:

```powershell
.\.venv\Scripts\python.exe tools\build_review_site.py
.\.venv\Scripts\python.exe tools\build_review_deck.py
.\.venv\Scripts\python.exe tools\qa_review_automation.py
```

The HTML site includes a top-level overview plus one detail page per registered
feature. Feature pages embed available screenshots, images, GIFs, videos,
audio, and transcript files directly in the page.

The v2 evidence layer keeps the v1 output pipeline but inserts two data
contracts before presentation rendering:

- `scenario_manifest`: feature-level automation scenarios describing samples,
  registered actions, capture targets, expected artifacts, fallback behavior,
  and guardrails.
- `evidence_graph`: feature/scenario/sample/artifact/QA/action nodes with edges
  that explain where every visible review claim came from.

The review automation QA validates:

- report shape and stale state,
- scenario manifest and evidence graph presence,
- local HTML `href`/`src` references,
- feature page coverage,
- artifact existence,
- visual image/GIF artifact readability and non-tiny dimensions,
- feature editor screenshot artifacts for detailed/evidence slides,
- minimal PPTX package structure.

Current feature registry:

- Studio Overview.
- Screen Studio Auto Polish.
- AI Script Edit.
- AI/MCP Action Automation.
- Six-Language Runtime UI.
- Live2D Overlay Timeline.
- Dialogue And Audio Cleanup.
- Review Site And Deck Generator.

Current guardrail:

- Do not market Spine rendering quality from this pipeline until the separate
  Spine renderer issue is fixed.

Next implementation step:

1. Replace headless fallback storyboard evidence with per-feature live editor
   UI captures wherever the editor owner can provide a stable capture backend.
2. Promote selected feature clips into stable GIF/MP4 captures tied to scenario
   ids rather than ad hoc filenames.
3. Add screenshot diff checks for generated HTML and PPT preview pages.
4. Add release-positioning text extraction so marketing copy can be generated
   but still bounded by safe claims.
5. Expand the scenario manifest to cover every high-value feature area:
   color grading, node graph, typography animation, transitions, Live2D, 3D/AR,
   sound editor, publish/export, and AI text editing.
