# Catalog PPT Style Rules

Last updated: 2026-07-03

This file is the catalog PPT style authority for review automation.

Do not use main-editor UI-renewal rules, Qt widget QSS, or runtime editor font
tokens as the page-design source for review PPT. The editor UI is photographed
inside the catalog. The catalog PPT has its own typography, spacing, and page
composition rules.

## Reference Mood

Use the Feat Paper minimal deck direction captured in:

```text
docs/review_reference_featpaper_style.md
```

Target feeling:

- product catalog,
- studio tour,
- design white paper,
- restrained gallery page,
- technical but not debug-like.

Avoid:

- AI-generated document feeling,
- heavy boxes,
- dashboard panels,
- raw QA pages,
- one-color purple/blue SaaS palette,
- dense bullets and cramped Korean/Japanese text.

## Typography

Catalog PPT/page typography:

- Primary slide/reference font: `IBM Plex Mono`, `Roboto Mono`, or
  `JetBrains Mono`.
- Large catalog/cover title fallback: `Inter`, `Helvetica Neue`, or `Arial`.
- Keep letter spacing at `0`.
- Do not use negative letter spacing.
- Titles should be light or regular where possible, not heavy display type.
- Body copy should be medium-small with generous line height.
- Footer metadata should be tiny and quiet.

Suggested 16:9 sizes:

- Page title: 42-56 px.
- Body text: 22-28 px.
- Section label: 14-18 px.
- Footer metadata: 12-16 px.
- Large stats, if used: 76-112 px light.

Korean/Japanese catalog pages should use a CJK-safe font and enough line height.
Do not cram translations into the same density as English.

Product typography feature pages:

- The editor screenshot should make typography the subject, not just add a
  small caption over video.
- Use a large on-canvas headline, a secondary line, and one or more smaller
  text layers so the viewer immediately understands titles/body/captions.
- When showing multilingual capability, include Korean, English, and Japanese
  samples at readable scale with CJK-safe fallback.
- Keep catalog page body copy restrained; the large text belongs inside the
  captured editor canvas or highlighted tablet/laptop screen.

## Page Composition

Use:

- off-white page,
- dark charcoal outer stage when needed,
- large whitespace,
- thin rules,
- calm metadata,
- real editor screenshot or device/workspace frame.

Common layout:

- thin horizontal rule near the top-left,
- small uppercase section label,
- main title and short copy on the left,
- laptop/monitor/editor evidence on the right,
- footer rule and metadata along the bottom.

Cards are rare. Prefer thin rules, real image frames, and whitespace.

## Screenshot Rules

Every product-facing editor image must be real:

- real YouTube Imports or review sample media,
- visible timeline clips,
- visible active operation or selected object,
- feature-specific panel or controller open,
- no fake generated editor UI as proof.

Generated or staged outer frames are allowed only as presentation devices. The
screen content inside laptop/monitor/template frames must be real TigerCapture
captures.

Do not add extra decorative imagery outside the selected product templates. The
only approved non-editor image frames are:

```text
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\laptop_catalog_template.png
E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates\multi_monitor_catalog_template.png
```

All other visible imagery in product-facing pages must be real TigerCapture
captures or real media frames inside those captures. Do not attach unrelated
generated illustrations, stock-style visuals, abstract graphics, or additional
mock monitor/device images.
