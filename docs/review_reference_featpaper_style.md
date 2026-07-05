# Feat Paper Minimal Deck Reference Style

Source: https://featpaper.inblog.io/minimal-figma-template-for-design-projects-25526

Canonical catalog PPT rule:

```text
docs/review_automation/CATALOG_PPT_STYLE.md
```

Use the canonical review automation hub first, then this document for expanded
Feat Paper reference detail.

This note captures the visual rules from the reference page images so Tiger Studio
review decks and catalog pages can reproduce the same restrained product-catalog
tone without copying the original assets.

This document is a catalog PPT/page reference only. It controls review deck,
catalog image, and phone-preview presentation style. It does not define the
runtime editor UI style, and runtime editor UI-renewal rules must not override
these catalog PPT typography, spacing, or page-composition rules.

## Core Mood

- Minimal technical catalog, closer to a design white paper than a marketing deck.
- Large negative space, quiet composition, and very limited color usage.
- Screenshots/images are treated as product evidence, not decorative backgrounds.
- "Review automation" pages are product-catalog pages: they explain what the
  tool lets a creator do. They are not code review pages, QA status pages, or
  release-health dashboards.
- Decorative images are not used for editor chrome, device frames, buttons, or
  icons; those are code/vector shapes. Only real media, real thumbnails, and
  real editor captures count as image evidence.
- The slide should feel like a captured design-system artifact, not an AI-generated
  presentation.

## Color Tokens

Use these as the default review theme tokens:

- Page background: `#F0F1F1`
- Alternate page background: `#ECEDEC`
- Canvas surround / contact-sheet gray: `#CCCCCC`
- Primary text: `#202126`
- Secondary text: `#6C6D70`
- Hairline / rules: `#2A2B2D` at low visual weight
- Soft border: `#DCDCDC`
- White frame: `#FBFBFB`
- Dark variant background: `#202126`
- Dark variant text: `#F0F1F1`
- Natural media accent only: muted green/blue from screenshots; avoid synthetic
  accent gradients.

Avoid purple-blue SaaS gradients, beige themes, saturated accent blocks, and
decorative blobs.

## Typography

The reference images rely heavily on monospaced typography.

- Primary slide font: `IBM Plex Mono`, `Roboto Mono`, or `JetBrains Mono`.
- Large catalog/cover title fallback: `Inter`, `Helvetica Neue`, or `Arial`.
- Use uppercase for section labels and page titles.
- Keep letter spacing at `0`; do not use negative letter spacing.
- Titles should be light/regular mono where possible, not heavy display type.
- Body copy should be mono, medium-small, with generous line height.
- Footer metadata should be tiny mono text.

Suggested sizes for 16:9 review slides:

- Page title: 42-56 px mono regular.
- Body text: 22-28 px mono regular.
- Section eyebrow: 14-18 px mono regular.
- Footer metadata: 12-16 px mono regular.
- Big stats: 76-112 px sans or mono light.

## Layout Rules

- Use 16:9 slides with a strict hidden grid.
- Leave large empty areas; do not fill every slide.
- Keep content aligned to a few strong vertical axes.
- Common structure:
  - Thin horizontal rule on the left.
  - Small uppercase section title near the rule.
  - Main title and body block in the middle-left.
  - Large screenshot/device/mockup on the right.
  - Footer rule and metadata along the bottom.
- Use thin lines instead of heavy cards.
- Cards are rare; when needed, they are flat and softly bordered.
- Do not nest cards inside cards.

## Image And Screenshot Rules

- Never show an empty editor in catalog/review slides.
- Never synthesize a fake editor scene for a feature claim. Public catalog images
  must be captured after importing a real clip from the TigerCapture YouTube
  Imports folder into the timeline.
- Every editor screenshot must look like a real editing session:
  - media loaded,
  - visible timeline clips,
  - at least one active operation or selected object,
  - relevant panels open for the feature being described.
- Crop or zoom the screenshot so the feature area is readable.
- Keep the screenshot inside a laptop/device frame, a flat white frame, or a large
  clean rectangle with a very subtle shadow.
- For multi-monitor workflow pages, use the three-monitor template and screen map
  documented in `docs/SPEC_REVIEW_AUTOMATION.md`; only real TigerCapture captures
  may be composited into the monitor screens.
- If showing UI controls, enlarge the relevant controller/menu/panel instead of
  showing the whole editor at unreadable scale.
- Avoid blurry dark screenshots unless the feature itself is dark UI.
- Product catalog pages must not show QA scores, pass/fail counts, action counts,
  evidence row counts, raw JSON, file-path lists, or dashboard-style diagnostic
  blocks. Keep those in the evidence-full appendix or machine-readable reports.

## Review Deck Application

For Tiger Studio review outputs:

- Before any PPTX/deck/catalog rewrite, inspect the current project spec first.
  Required inputs include `SPEC.md`, `README.md`, `docs/RELEASE_POSITIONING.md`,
  `docs/SPEC_REVIEW_AUTOMATION.md`, feature `docs/SPEC_*.md` files, the Python
  Action System registry, current review reports, sample manifest, and relevant
  QA evidence. The product spec changes often, so style application must follow
  fresh spec discovery instead of old deck memory.
- Summary version: cover + product overview + 3-5 strongest evidence slides.
- Catalog version: one feature family per section, with large editor evidence.
- Detailed version: each feature gets a scenario screenshot/GIF frame and a short
  technical explanation.
- Node pages should show an actual node graph with the selected node controller
  visible in the node dock.
- Live2D/3D/typography/effects pages should show the object selected on canvas and
  the active property controls, not just the final result.

## Implementation Notes

- Store reference images under:
  `debugCapture/reference_figma_template/`
- Generated contact sheet:
  `debugCapture/reference_figma_template/contact_sheet.jpg`
- Extracted palette summary:
  `debugCapture/reference_figma_template/image_color_summary.json`
