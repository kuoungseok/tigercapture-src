# Review Automation Purpose Rules

Last updated: 2026-07-03

## Primary Purpose

Review automation is a product promotion and product explanation system. It
should show what TigerCapture/Tiger Studio can do and what a creator can make
with it.

Despite the name, it is not:

- a code-review system,
- a QA dashboard,
- a release status report,
- a raw evidence dump,
- a JSON/report viewer.

## Product-Facing Output

Summary decks, detailed decks, catalog pages, HTML pages, and phone-preview PNGs
must feel like a product catalog or studio tour.

They should:

- explain features through realistic editor work,
- show real media on the timeline,
- prefer multi-track timelines so screenshots look like real editing work, not
  a single imported test clip,
- avoid short/simple timeline hero shots. Product-facing overview, laptop, and
  multi-monitor pages should show a long real project with multiple media-pool
  sources and visible edit texture such as cuts, transitions, audio, effects,
  markers, keyframes, nodes, or actor lanes,
- allow some screenshots to include natural mid-timeline cuts, edit boundaries,
  markers, or transitions, while avoiding the same treatment on every page,
- prefer visually strong real footage from
  `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`, especially city
  scenery, night skylines, drone/aerial scenes, car racing, motorsport, driving,
  and cinematic HDR/OLED demo clips,
- within the same source video, select catalog-worthy timestamps before capture.
  Do not accept the first decoded frame, an arbitrary action timestamp, or a
  dark/blurred/macro frame just because it came from an approved video,
- user-provided timestamps are a strong candidate pool, not a forced final
  frame. If a candidate is blurred, too dark, cropped awkwardly, or weak as a
  catalog image, replace it with a prettier frame from the same approved video,
- maintain a small approved timestamp list for frequently used videos. Examples:
  Taichung night skyline around `00:34` and `01:42`, Tokyo tower aerial around
  `02:23`, Lamborghini car-driving around `01:26`, South Korea bridge/skyline
  around `03:51` and `09:24`, Fallingwater exterior around `03:55` and
  `13:28`,
- choose a different timestamp when an otherwise useful clip lands on a face,
  eye close-up, skin macro, color-bar, or test-looking frame,
- keep Live2D actor backgrounds visually quiet unless the slide is explicitly
  demonstrating dense compositing,
- vary AR/PBR 3D evidence. Do not make every 3D page use the same camera model;
  prefer visually readable approved GLTF/GLB assets from
  `E:\ClaudeCodeApp\3d` when they render cleanly,
- regenerate feature screenshots after UI renderer changes; do not reuse
  historical `TigerCapture_Product_Catalog_EN_v*_assets` crops as current UI
  evidence,
- show active feature-specific panels and controls,
- use laptop and multi-monitor templates when they help the product story,
- avoid attaching any decorative/generated images beyond the approved laptop
  and multi-monitor templates, except for the user-approved final
  `Specification Index` page object described below,
- hide QA/action details behind the scenes unless the page is explicitly an
  internal appendix.

They must not show:

- QA scores, pass counts, readiness counts, or action counts,
- raw report tables, raw JSON, file-path lists, or debug logs,
- empty editors, color bars, placeholder media, or fake generated editor UI,
- unrelated generated images, stock-like visuals, or newly invented device
  frames outside the approved templates,
- screenshots whose main message is implementation health.

## Evidence Boundary

QA and action evidence are still important, but they are backing data. Product
catalog pages may say a feature is evidence-backed, guarded, blocked, or pending,
but should not make the evidence machinery the visible story.

## Feature Evidence Binding

Every product-catalog slide must show the feature it claims to explain. The
builder must reject a slide if the visible editor state is unrelated to the
page's message.

Hard rules:

- Color grading, node, and effect pages must apply the actual grade/filter/node
  through the editor action surface, enable the viewer's before/after or split
  comparison state, and capture that changed editor state. The changed state
  must use non-neutral numeric parameters and must visibly differ from the
  original; a neutral/original-looking comparison is invalid. If suitable preset
  values are unknown, research real preset values and record the source in the
  capture contract.
- A black, blank, or raw-source-only Viewer region is a build blocker. Do not
  hide a failed Viewer capture by pasting in an unrelated source frame.
- Live2D, VRM, MMD, and other actor pages must show the character inside the
  editor's video preview or Program Output workflow, plus the related actor lane
  or controls. A standalone actor viewer is useful as detail evidence but is not
  enough as the main page proof.
- VRM/VTuber Studio pages must show the actual studio layout: Program Output,
  Source Tracking, Avatar Mapping, and Studio Controls. The tracking/source
  video is not the final Program Output.
- For VRM/VTuber Studio pages, the main laptop/monitor frame must be the full
  `VTuber Studio - Tiger Studio` work screen. If an iPad/detail frame is used,
  it must show Program Output only, not Source Tracking, Avatar Mapping, a
  duplicated workspace, or a generic editor crop.
- If the VRM/VTuber page uses the Trump Performance Source, treat it as
  chest-up seated talk footage. Avatar evidence must use `bust_up` /
  head-to-mid-chest framing: head, neck, shoulders, and upper torso visible,
  but not widened to waist/full-body. A face-only VRM meta thumbnail is invalid.
- Trump-source VTuber Program Output must make the VRM readable and grounded:
  trim transparent avatar padding before scaling, keep the visible avatar large
  enough for catalog use, and anchor the lower visible edge to the output's
  bottom safe line. Tiny avatars, centered transparent canvases, or avatars that
  visually float above the video are invalid even when the `bust_up` label is
  present.
- VRM/VTuber product evidence must use the VTuber VRM GPU renderer
  `vrm_mtoon_gpu`. Software VRM fallback output is allowed only as diagnostic
  proof, not as product-catalog evidence, because it can produce dotted or
  point-cloud avatar rendering.
- MMD pages must show a visible MMD character or motion result in the editor or
  character-motion workflow. A generic video editor screenshot or standalone
  MMD player without editor context is not acceptable.
- AR/PBR pages must keep the laptop/editor viewer and the iPad/detail viewer on
  the same named 3D asset. If the iPad shows the approved plaster bust, the
  editor viewer must also show that same bust, scaled large enough to read.
- The timeline in product screenshots must come from the current editor UI. Do
  not reuse old timeline thumbnails, old track styling, or synthetic fallback
  strips that no longer match the application.
- Multi-monitor pages describe multi-environment flexibility, not a fixed
  three-screen requirement. Three monitors are one example; more screens should
  be described as giving the same workspace more room.

If a required feature capture cannot be produced, the correct result is to stop
the build and recapture or mark the slide pending. Never replace it with a
visually pleasing but unrelated image.

## Final Specification Page Visual Exception

The locked full product catalog must use one non-editor visual object on the
final `Specification Index` page:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\references\bonsai_blue_pot_spec_page_source_2026-07-07.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\tmp\catalog_spec_closing\bonsai_blue_pot_cutout_v1.png
```

This bonsai cutout is a closing-page catalog object only. It must not be used as
feature evidence, must not appear on feature pages, and must not replace real
editor captures. Do not use a large drop shadow around it; only a subtle
floor/contact shadow under the pot base is allowed. Visible white halos,
checkerboard remnants, or background strips around the cutout are invalid.
The build-side shadow mode is locked as `pot_contact_only`, and left-side
subtitle/body copy must wrap inside the left text area without overlapping the
micro-spec columns.
The visible micro-spec groups must come from
`docs/review_automation/spec_index_groups.json` and be refreshed from the latest
`SPEC.md`, `TODO.md`, and relevant `docs/SPEC_*.md` files before catalog
generation. The final page must stay product-catalog oriented: include current
surfaces such as PPT Maker / `.tgppt`, Music Lab, Sound Editor, Local AI,
Python Action, MCP, VTuber Studio, AR/PBR, depth-aware compositing, PPTX, and
MP4, but exclude MRQ, Unreal Bridge, Marmoset, QA readiness numbers, and
pass/fail status wording.

## Current Timeline Visual Contract

The current timeline reference is:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\references\current_editor_timeline_reference_2026-07-06.png
```

Use this reference when judging whether a product-catalog editor screenshot is
current. The current timeline presentation uses:

- a horizontal time ruler above the tracks,
- a red playhead line with triangular markers on the ruler and clip lane,
- long continuous clip thumbnail strips inside the track area,
- understated dark rows with subtle grid lines,
- simple left-side track labels such as `Video`,
- current Viewer transport controls with `Compare`, `Fit`, and zoom state near
  the Viewer area,
- no old blocky colored track bars, no large V1/A1 tab blocks, no synthetic
  debug track strips, and no obsolete thumbnail layout.

If a screenshot uses the older track drawing system, treat it as stale even if
the media and Viewer frame look good. Recapture from the current editor.

## PPT Cache Rule

Before generating any PPT/PPTX catalog, clear transient review/PPT generation
caches first. This includes stale slide PNGs, previous deck asset crops,
temporary screen composites, and old rendered preview images that could make the
new deck reuse outdated UI or bad frames.

Final PPT generation must not read screen contents from historical capture
folders such as:

```text
fresh_first_slide_capture
actual_3d_viewer_capture
debugCapture
```

Treat those folders as investigation/debug evidence only. Product-catalog PPT
screen contents must come from the current approved recapture batch, normally
under:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\tmp\fresh_review_recapture
```

If a required current capture does not exist, stop the build and recapture the
feature. Do not silently fall back to an older screenshot.

## No Placeholder Deck Rule

Product-catalog PPT builders must not place generic `RECAPTURE REQUIRED`,
`PENDING`, blank, black, or other repeated placeholder images inside laptop,
iPad, monitor, or feature evidence frames. If strict feature evidence is
missing, the builder must stop before creating PPTX output and write a blocked
report instead.

Do not generate a deck where multiple feature pages share the same fallback
screen image. Missing evidence is a build blocker, not a slide asset.

Laptop and monitor frames are reserved for full editor/window captures. Cropped
panel details, media-pool-only screenshots, timeline strips, contact sheets,
and inspector/detail views may be used only in detail frames such as the iPad
or in explicitly labeled supporting panes. They must never fill the main laptop
or monitor screen.

## Detail Frame Contract Rule

The iPad/detail frame is an emphasis surface, not a second full editor screen.
It must show the close-up detail that proves the page claim. Do not place a
miniature copy of the whole editor inside the iPad unless the page explicitly
asks for a secondary full workspace.

For the Color Grading Workspace page, the iPad/detail frame must contain only
color controls such as color wheels, curves, scopes, tone controls, or standard
sliders. It must not contain the video viewer, media pool, or timeline. The
main laptop/editor screen is where the before/after viewer and timeline belong.

Do not delete:

- `E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates`,
- source videos under `C:\Users\artmouse\Videos\TigerCapture\YouTube Imports`,
- source specs or rules under `docs/`,
- manually approved source assets unless the user explicitly asks.

If cleanup is scripted, it must target known cache/output directories or exact
PPT/PPTX files only. Broad workspace deletion is forbidden.

## Developer-Only Access

The review automation tool remains developer-only. It should not appear as a
normal packaged-app feature. Use developer flags or source-checkout tooling to
run it.
