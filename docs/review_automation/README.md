# TigerCapture Review Automation Hub

Last updated: 2026-07-03

This folder is the canonical rule hub for TigerCapture review automation.

Review automation means automated product-catalog generation. It does not mean
code review, QA status reporting, or release-dashboard output. The system should
show what TigerCapture/Tiger Studio can do, using real captured editor states,
then place those captures into catalog PPT, HTML, and preview layouts.

## Read Order

Before rebuilding or rewriting any review PPT, HTML page, catalog image, or
phone-preview PNG, read these files in order:

0. `AGENT_START_HERE.md`
1. `PURPOSE_RULES.md`
2. `CATALOG_PPT_STYLE.md`
3. `PRESENTATION_SCENARIO.md`
4. `FULL_PRODUCT_CATALOG_MANIFEST.md`
5. `FULL_PRODUCT_CATALOG_PAGE_PLAN.md`
6. `FULL_PRODUCT_CATALOG_TALK_TRACK.md`
7. `PRODUCT_CATALOG_PT_SCENARIO.md`
8. `COMPARISON_TEMPLATE_RULES.md`
9. `MULTI_MONITOR_RULES.md`
10. `TEMPLATE_ASSET_MANIFEST.md`
11. `REVIEW_AUTOMATION_TODO.md`

If a new agent has time to read only one file, read `AGENT_START_HERE.md`.

## Source Separation

Use this folder for review automation rules.

- `docs/review_automation/`: purpose, catalog PPT rules, scenarios, template
  manifests, and review-specific TODO.
- `app/review_automation/`: implementation code only.
- `E:\ClaudeCodeApp\ReviewAutomationWorkspace\source_assets\templates`:
  durable laptop/device, monitor template, screen-map, and design reference
  sources.
- `../ReviewAutomationWorkspace/`: generated samples, reports, outputs, and
  temporary presentation artifacts.
- `debugCapture/`: regenerated evidence captures only. Do not keep original
  templates or reference sources here.

Final PPT generation must not use historical screenshots as slide screen
contents. In particular, do not source product-catalog device screens from
`fresh_first_slide_capture`, `actual_3d_viewer_capture`, or `debugCapture`.
Those folders are allowed for diagnosis/history only. Rebuild current feature
screens into `E:\ClaudeCodeApp\ReviewAutomationWorkspace\tmp\fresh_review_recapture`
and fail the deck build if the required current capture is missing.

Do not treat `docs/SPEC_UI_RENEWAL.md`, Qt QSS files, or runtime editor widget
styles as catalog PPT typography or page-design authority. The live editor UI is
the photographed product. The catalog PPT rules in this folder are the
presentation frame.

## Expanded References

The older top-level documents remain useful expanded references:

- `docs/SPEC_REVIEW_AUTOMATION.md`
- `docs/CURRENT_SPEC_PRESENTATION_SCENARIO.md`
- `docs/MULTI_MONITOR_REVIEW_SCENARIO_RULES.md`
- `docs/review_reference_featpaper_style.md`
- `docs/VTUBER_TRUMP_SOURCE_MAPPING_CONTEXT.md`

When these documents disagree with this folder on review/PPT purpose or catalog
style, this folder wins.

## Fixed Full Catalog

The current full product-catalog deck is locked in:

```text
docs/review_automation/FULL_PRODUCT_CATALOG_MANIFEST.md
```

Use it as the slide-count and slide-title contract for full catalog generation.
Do not add, remove, split, merge, or reorder its 21 slides unless the user
explicitly changes that manifest first.

The page-by-page production plan for those 21 slides is locked in:

```text
docs/review_automation/FULL_PRODUCT_CATALOG_PAGE_PLAN.md
```

Use it to decide each page's template, screen composition, capture source,
action/capture method, and rejection criteria.

The Korean presenter talk track for those 21 pages is locked in:

```text
docs/review_automation/FULL_PRODUCT_CATALOG_TALK_TRACK.md
```

Use it as speaker-note or narration guidance, not as visible slide body text.
