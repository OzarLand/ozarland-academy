# Accessibility

## Alt text

- Describe what is visibly present and relevant to the page; use one concise factual sentence.
- Do not include “image of”, brand claims, mood judgements or information that is not visible.
- If an image is decorative or duplicates an adjacent caption, use empty alt text and mark it decorative.
- The hero and banners describe the scene, not the page's message. Put the message in a real heading.
- Icons next to visible labels are decorative; if an icon is the only control label, provide an accessible name in HTML.
- Do not expose a stage seal's color as its name; pair it with the stage's literal module title.

## Contrast and states

Use the tested text/background pairings in tokens/palette.json. Links are underlined in prose. Do not use the light-mode accent blue, sea, sky, wood, lantern or terracotta as small text on parchment. Use module accents as fills or icon details with a dark outline. Risk states always have a written label and icon as well as color.

The light focus treatment is a gold inner ring plus a navy keyline; gold alone does not reach 3:1 against the pale canvas. Dark mode uses a gold ring with a parchment keyline. Keep focus visible over cards, buttons, links, tabs and theme controls.

## Dark mode

Use the slate token set rather than CSS filters over illustrations. Preserve the original bright artwork with a tested solid surface behind text. Test code blocks, tables, diagrams, search suggestions and focus rings in both schemes.

## Reduced motion

Avoid autoplay, parallax, continuous glow and moving map paths. If a small transition is useful, limit it to opacity or transform and disable it under prefers-reduced-motion: reduce. Communicate progress with a stable label and seal, not animation alone.

## Phone reading

At 320 CSS px, keep the page in one column, body text at least 16 px, controls at least 44×44 CSS px, and images cropped around their focal subject. Tables and code may scroll inside labeled containers; the page itself must not scroll horizontally. Keep the path order, breadcrumbs, stage labels and next action visible without relying on a wide graphic.

## Image prompt rule

All generated illustrations must have no text, letters, numbers, watermark or known characters. Check the output manually for accidental marks before adding it to the site. The manifest contains a factual English alt_text for every packaged or prompt-only visual asset.
