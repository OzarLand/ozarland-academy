# OzarLand Academy art direction handoff

This archive packages the Academy's chosen visual direction for an engineer integrating it into the Zensical site. It contains the reusable style anchor, approved path metaphor, module system, one-page charter, accessibility guidance, typography, palette tokens, the module/book icons and the stage seals, existing OzarLand raster artwork, and image prompts for the new Lumo pose variants.

## What's final

- The island-trail concept and module-to-place mapping.
- The style anchor and written brand rules.
- The CSS and JSON palette tokens, including measured WCAG contrast pairs.
- The SVG icons (one per module, and the book) and the SVG stage seals (`stage-0.svg` to `stage-7.svg`). The first set covered five stops; the icons and seals of stops 0, 6 and 7 were drawn later in the same style, and their bands were painted to match the series.
- Existing OzarLand Academy / Day 2 illustrations reused for the path hero, section bands, state pages and social preview. These retain their original compositions and are packaged as WebP.

## What's still a draft

- Six standalone Lumo pose illustrations were planned as prompts in prompts/. Five of them, one per stop, are superseded by the LUMO pose of each stop in the art direction of the learning path (`learning-path/`), which follows LUMO's progression; manifest.json marks them `superseded`. The book pose (`prompts/lumo-book.md`) is still prompt-only.
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
- characters/ — reference sheets of LUMO (evolution from stop 0 to stop 7, expressions, turnaround) and of the recurring characters, for the art direction of stops 1 to 7.
