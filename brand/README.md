# OzarLand · Kolla-Ansible Academy graphic charter

> **OzarLand Academy art direction.** [`academy/`](academy/README.md) is the art direction of the whole
> academy: the island trail (one stop per module), the module accents and icons, the stage seals, the section
> bands and the state pages. It extends this charter and takes precedence where they differ; in particular,
> headings use the system font stack and no web font is loaded (Lora was removed). Where its assets live in
> the site: `overrides/assets/images/ozarland/` (`icons/<module>.svg`, `seals/stage-N.svg`,
> `bands/<module>.webp`, `hero/path-hero.webp`, `pages/`), styles in section 26 of
> `overrides/assets/stylesheets/portal.css`. The bands are named after the module id rather than the place
> (`bands/day2.webp`, not `bands/operate.webp`), so that the templates find them from `academy.toml`.

**A shared land for better OpenStack operations.** This portal helps engineers understand what Kolla-Ansible commands do to a running OpenStack cloud by reading the source. The visual world frames that work as a shared, careful journey: welcoming, curious, and trustworthy.

## Colour palette and use

Use navy for primary text, navigation, and important controls; parchment-soft for page backgrounds; parchment for raised reading surfaces; wood and brass for quiet structure and warm accents; sea and sky for links, diagrams, and informational states; terracotta for warnings and destructive actions. Lantern gold marks focus and active exploration. Keep large painted illustrations bright and let UI surfaces provide readable text contrast.

| Token | Light value | Use |
|---|---|---|
| navy | `#1F3A6B` | Main text, navigation, primary button |
| navy-strong | `#152A50` | Hover/pressed navy surfaces |
| parchment | `#F3E3C3` | Cards and raised panels |
| parchment-soft | `#FBF4E4` | Main light background |
| wood | `#C4904F` | Borders, secondary accents |
| wood-dark | `#6B4220` | Muted text on light surfaces, outlines |
| lantern | `#F0B440` | Focus ring, small highlights |
| sea | `#1E9FB5` | Links and informational accents |
| terracotta | `#B55A3A` | Warning accent |
| sky | `#2F6FD0` | Secondary blue accent |

Dark mode uses navy `#8FB0E6`, parchment-soft `#1C2433`, wood `#D9A865`, sea `#4CC3D6`, terracotta `#E0825F`, background `#11151A`, and hero gradient `#142038` → `#1D3550`. Prefer parchment text on dark surfaces; reserve bright accent colors for links, icons, and short labels.

### WCAG AA contrast

Ratios below are calculated using WCAG relative luminance. Normal text passes at 4.5:1 and large text at 3:1. Intended text pairings:

| Text / background | Ratio | Normal text |
|---|---:|---|
| navy `#1F3A6B` / parchment-soft `#FBF4E4` | 10.2:1 | Pass |
| navy `#1F3A6B` / parchment `#F3E3C3` | 8.8:1 | Pass |
| white `#FFFFFF` / navy-strong `#152A50` | 14.2:1 | Pass |
| wood-dark `#6B4220` / parchment-soft `#FBF4E4` | 7.9:1 | Pass |
| parchment `#F3E3C3` / background `#11151A` | 14.5:1 | Pass |
| navy `#8FB0E6` / background `#11151A` | 8.3:1 | Pass |
| sea `#4CC3D6` / background `#11151A` | 8.8:1 | Pass |
| terracotta `#E0825F` / background `#11151A` | 6.6:1 | Pass |
| wood `#D9A865` / background `#11151A` | 8.5:1 | Pass |

Pairs that fail for normal text and must stay decorative or be paired with a darker/lighter text color: white on light parchment-soft (1.1:1), white on parchment (1.3:1), navy `#1F3A6B` on dark background (1.64:1), sky on parchment-soft (4.45:1), sea on parchment-soft (2.87:1), terracotta on parchment-soft (4.27:1), lantern on parchment-soft (1.7:1), wood on parchment-soft (2.57:1), parchment-soft on sea (2.87:1). In particular, do not use the sea or terracotta accent as small text on the light page background; use navy text and keep those hues for fills, borders, and large graphical marks. White text belongs on navy only.

## Typography

Use system stacks only; no web fonts. UI and headings: `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. Code and command output: `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`. Use sentence case, generous line-height (1.5–1.65 for prose), and clear heading steps. Keep commands visually distinct with a dark navy code surface and parchment text.

## Layout and components

- Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64 px. Use 16–24 px inside controls/cards and 48–64 px between major sections.
- Corner radius: 8 px for controls, 14 px for cards, 20 px for large image panels. Keep the logo mark and icon shapes crisp.
- Borders: 1 px wood at 35–50% opacity on light surfaces; 1 px navy at 30% opacity in dark mode. Use lantern gold for a 2 px keyboard focus outline with 2 px offset.
- Shadows: one soft lift only, e.g. `0 6px 20px rgba(21,42,80,.12)` in light mode and `0 8px 24px rgba(0,0,0,.28)` in dark mode. Avoid heavy black shadows and glass effects.
- Primary button: navy fill, white label, 8 px radius; hover navy-strong; visible lantern focus outline. Secondary button: transparent/parchment surface with navy label and wood border. Destructive action: terracotta fill with white label only where contrast is adequate; otherwise use navy label on a pale terracotta tint.
- Hero surface: light uses a sky-to-navy gradient behind the artwork; dark uses `linear-gradient(120deg, #142038, #1D3550)`. Keep text on a solid or tested overlay area.

## Do and don't

**Do** use friendly traveller imagery, cloud pennants, parchment, wood, brass, waterfalls, and open sky consistently. Explain operational effects and risk in calm, direct language. Keep diagrams and UI icons flat, simple, and readable at small sizes.

**Don't** add extra logos, words, numerals, watermarks, visual noise, ominous danger imagery, or unverified claims to the painted images. Don't place body copy over detailed artwork, rely on color alone for status, use accent colors for low-contrast text, or use external fonts.

## Image guide

All painted images are WebP quality 80 with the requested pixel dimensions, except the requested `social-preview.png` link preview background with open sky and low detail on the left for the site to add its title. Use `hero.webp` at the page top, `why-map.webp` to explain source-led learning, and `learning-path.webp` for the sequence overview. Use the six feature images (`operations`, `troubleshooting`, `components`, `risk`, `concepts`, `reference`) as section cards or page headers. `coming-soon.webp` and `not-found.webp` are state illustrations. Keep image crops centered and avoid placing UI text on top of the focal subject. Corner cropping is already considered in the source compositions.

`logo-mark.svg` is the full-color cloud pennant for light or dark headers; `logo-mark-mono.svg` inherits its pennant color from `currentColor`. The 48 px favicon and 180 px Apple touch icon are raster exports. The twelve 48 px SVGs in `icons/` form the flat interface icon set. `previews/contact-sheet.png` is a review sheet; do not use it in the site UI.

## Where the kit is used in this repository

The site files live in `overrides/assets/images/` (resized and compressed for the web):

| Kit file | Site file | Used by |
|---|---|---|
| `logo/logo-mark.svg` | `logo.svg` | header of every page |
| `logo/favicon.svg`, `logo/apple-touch-icon.png` | `favicon.svg`, `apple-touch-icon.png` | browser tab, home screen |
| `illustrations/hero.webp` | `ozarland/hero.webp` | welcome page and home page of each release (`overrides/landing.html`, `overrides/home.html`) |
| `illustrations/why-map.webp`, `learning-path.webp` | `ozarland/why-map.webp`, `ozarland/learning-path.webp` | welcome page |
| `illustrations/social-preview.png` | `ozarland/social-preview.jpg` | link previews (`og:image`) |
| `icons/book.svg`, `lantern.svg`, `compass.svg`, `pennants.svg` | `ozarland/icons/` | cards of the welcome page |

The colour tokens (`--oz-*`) are in `overrides/assets/stylesheets/portal.css`, section 14. The text alternatives of the
images come from `manifest.json`.

The section illustrations (`operations` … `reference`), `coming-soon` and `not-found` of this kit were replaced by the
district banners and page scenes of the Academy charter (`brand/charter/`).
