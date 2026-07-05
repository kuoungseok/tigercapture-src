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
  and multi-monitor templates,
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

## PPT Cache Rule

Before generating any PPT/PPTX catalog, clear transient review/PPT generation
caches first. This includes stale slide PNGs, previous deck asset crops,
temporary screen composites, and old rendered preview images that could make the
new deck reuse outdated UI or bad frames.

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
