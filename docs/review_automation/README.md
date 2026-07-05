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
4. `PRODUCT_CATALOG_PT_SCENARIO.md`
5. `COMPARISON_TEMPLATE_RULES.md`
6. `MULTI_MONITOR_RULES.md`
7. `TEMPLATE_ASSET_MANIFEST.md`
8. `REVIEW_AUTOMATION_TODO.md`

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
