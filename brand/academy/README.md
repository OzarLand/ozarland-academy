# OzarLand Academy art direction handoff

This archive packages the Academy's chosen visual direction for an engineer integrating it into the Zensical site. It contains the reusable style anchor, approved path metaphor, module system, one-page charter, accessibility guidance, typography, palette tokens, six hand-written module/book icons, five stage seals, existing OzarLand raster artwork, and image prompts for the new Lumo pose variants.

## What's final

- The island-trail concept and module-to-place mapping.
- The style anchor and written brand rules.
- The CSS and JSON palette tokens, including measured WCAG contrast pairs.
- The six SVG icons and five SVG stage seals.
- Existing OzarLand Academy / Day 2 illustrations reused for the path hero, section bands, state pages and social preview. These retain their original compositions and are packaged as WebP.

## What's still a draft

- Six additional standalone Lumo pose illustrations are prompt-only. Their full generation prompts are in prompts/. Their intended output paths and dimensions are recorded in manifest.json.
- The website hostname is still undecided; use relative asset paths until the domain is confirmed.
- The illustration mappings should receive a final crop check against the actual page templates after integration.

## Status and manifest

Manifest entries cover every visual asset. For an included asset, file is the packaged path. For a prompt-only asset, file points to the prompt document that is present in this archive; target_path is where the generated WebP should be placed in the site. The manifest status remains prompt-only until that image is generated and reviewed. All manifest file paths exist in the ZIP.

All target_path values are under overrides/assets/images/ozarland/. SVG files use only palette colors and currentColor; they have no embedded raster images, scripts or external references. All included painted images are text-free. Page titles and captions belong in HTML/CSS, not baked into artwork.

## Contents

- README.md — handoff status, integration notes and directory guide.
- manifest.json — machine-readable visual asset index.
- brand-charter.md — one-page summary for designers and reviewers.
- style-anchor.md — reusable exact paragraph for image prompts.
- concept.md — metaphor variants and per-module mapping.
- tokens/palette.css and tokens/palette.json — light/dark tokens and contrast data.
- typography.md, templates.md and accessibility.md — implementation guidance.
- icons/ and seals/ — flat scalable vectors.
- images/ — existing WebP artwork included in the handoff.
- prompts/ — full prompts for six Lumo pose images not yet generated.
