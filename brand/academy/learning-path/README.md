# Art direction of the learning path (stops 1 to 7)

The common art direction of stops 1 to 7, in the same
spirit as [`../../village/`](../../village/) for stop 0. Not published on the site.

| File | Content |
|---|---|
| `direction-artistique-parcours.md` | Concept, LUMO's validated progression, characters, places, palette, framing and formats, accessibility and negative rules, teaching messages per stop, production order. |
| `personnages.md` | The characters of [`../characters/cast.webp`](../characters/cast.webp), with their stops, trade, signature object and what they teach. |
| `manifest-parcours.json` | Image manifest: the shared island map, then an opening (1536x1024) and a LUMO pose (800x800) per stop. Every entry is `prompt-only` until the image is generated and reviewed. Each stop can grow to at most 10 images. |
| `decisions.md` | Decisions still open. |
| `stop-1/` | Scene plan and manifest of stop 1 (Quick lab). The 8 images are generated and placed in `docs/lab/assets/images/` under English names: `S1-opening`, `S1-lumo-pose`, `S1-pick-your-lab`, `S1-create-use-destroy`, `S1-network`, `S1-compute`, `S1-failure-and-maintenance`, `S1-controllers-and-quorum`. |
| `stop-2/` | Scene plan and manifest of stop 2 (Deployment patterns). The 9 images are in `docs/deploy/assets/images/`: `S2-opening`, `S2-lumo-pose`, `S2-topologies`, `S2-networking-and-storage`, `S2-configuration-and-secrets`, `S2-services`, `S2-deployment-errors`, `S2-operations`, `S2-comparisons`. |
| `stop-3/` | Scene plan and manifest of stop 3 (Kolla-Ansible Academy). The 9 images are copied into each of the three studies, in `docs/day2/<release>/assets/images/`: `S3-opening`, `S3-lumo-pose`, `S3-studies-shelves`, `S3-start`, `S3-predict-a-run`, `S3-what-is-not-known`, `S3-components`, `S3-small-change-large-effect`, `S3-concepts-and-reference`. |
| `stop-4/` | Scene plan and manifest of stop 4 (VM runbooks). The 9 images are in `docs/runbooks/assets/images/`: `S4-opening`, `S4-lumo-pose`, `S4-observe-before-acting`, `S4-lifecycle-and-scheduling`, `S4-migration`, `S4-networking`, `S4-volumes`, `S4-diagnostics-and-logs`, `S4-recovery`. |
| `stop-5/` | Scene plan and manifest of stop 5 (Production guide). The 9 images are in `docs/production/illustrations/` (the module excludes its `assets/` folder, which belongs to the memo renderer): `S5-opening`, `S5-lumo-pose`, `S5-how-to-read-a-memo` on the home page, and one per category (`S5-vm-lifecycle`, `S5-compute`, `S5-networking`, `S5-storage`, `S5-control-plane`, `S5-production-operations`), placed by `scripts/build.cjs` on the generated category pages. The 44 memo cards keep their own images. |

Decisions already taken: LUMO gains one accessory per stop; the existing 1600x400 bands stay; 6 to 10 images per stop;
production starts with stop 1 (Quick lab).
