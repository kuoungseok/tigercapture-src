# Painter UI Template and Library Research

Status: active implementation reference

## Product finding

Figma's template advantage is not only the number of files. The durable product
loop combines:

- complete-file duplication into an independently editable document
- searchable Community resources and UI kits
- components, styles, and variables bundled as reusable library assets
- published library updates that downstream files can review and accept
- explicit creator, source, license, and attribution requirements
- component naming and hierarchy that remain searchable after duplication

Tiger Studio templates therefore must be complete editable UI documents rather
than flattened screenshots or decorative presets. A template is useful only
when its artboards, objects, tokens, components, interactions, provenance, and
delivery contract remain editable and inspectable.

## Primary references

- Figma, Guide to libraries:
  https://help.figma.com/hc/en-us/articles/360041051154-Guide-to-libraries-in-Figma
- Figma, Library fundamentals:
  https://help.figma.com/hc/en-us/articles/39723547036055-Components-collection-Library-fundamentals
- Figma, Community copyright and licensing:
  https://help.figma.com/hc/en-us/articles/360042296374-Figma-Community-copyright-and-licensing
- Figma, Duplicate or copy files:
  https://help.figma.com/hc/en-us/articles/360038511533-Duplicate-or-copy-files
- Figma, Variables, collections, and modes:
  https://help.figma.com/hc/en-us/articles/14506821864087-Overview-of-variables-collections-and-modes
- Figma, Component organization:
  https://help.figma.com/hc/en-us/articles/360038663994-Name-and-organize-components
- Apple Human Interface Guidelines, Layout:
  https://developer.apple.com/design/human-interface-guidelines/layout
- W3C WAI-ARIA Authoring Practices patterns:
  https://www.w3.org/WAI/ARIA/apg/patterns/

## Tiger Studio template contract

Every built-in template must provide:

1. A complete normalized Painter UI document.
2. At least one editable artboard and five editable objects.
3. Shared typed design tokens with stable IDs.
4. At least one reusable Component Definition.
5. At least one prototype-ready interaction.
6. Category, tags, difficulty, source, author, and license metadata.
7. Template ID and version provenance persisted in `.tspaint`.
8. Validation through the same document, Action, Undo, and delivery services
   used by manually authored UI.

Templates must not silently embed third-party design kits. External Community
resources require their original license and attribution metadata. Free Figma
Community files commonly require CC BY 4.0 attribution, while paid resources
have different redistribution restrictions; imports must preserve the actual
creator-supplied terms rather than assume a universal license.

## Initial built-in coverage

The first catalog provides twelve original Tiger Studio templates:

- Mobile Onboarding Flow
- Personal Finance Mobile
- Responsive SaaS Dashboard
- Analytics Command Center
- Editorial Product Detail
- Designer Case Study
- Tactical Game HUD
- Live Broadcast Overlay
- Product Pitch Story
- Product Wireframe Flow
- Accessible Checkout Form
- Design System Starter

This is a foundation, not the completion metric. M2A still requires external
package import/export, favorites and recent items, richer component libraries,
template update review, visual QA, and a substantially broader high-quality
catalog.
