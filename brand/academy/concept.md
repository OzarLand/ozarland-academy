# Core concept: one island trail

## Recommended metaphor

The Academy is a shared journey across one inhabited island. It starts in LUMO's village, a prelude where a beginner builds a mental map of a cloud. Then eight connected places make a clear learning path: a learner arrives at the harbour, compares routes at the deployment workshop, studies how the cloud works in the library workshop, follows evidence across the bridge, then reaches the lighthouse before production. Beyond it, the citadel of automatons compares another way to run OpenStack, the old quarters' bridge leads legacy clouds to a current release, and the companions' hall equips the learner's assistant. The separate book is the island's archive library: it belongs to the same world and offers a deeper route for readers who want more detail.

This metaphor fits the actual learning order without implying that every operator uses one mandated deployment pattern. Every place keeps its literal module name in the interface; the island scene supports orientation and memory but never replaces the technical label.

## Alternatives considered

1. **A fleet's passage:** each module is a stage in a shared voyage. It is warm and communal, but it makes the steps feel more sequential than the curriculum's comparison and reference work.
2. **A citadel of connected towers:** each module is a tower joined by aqueducts. It communicates systems thinking well, but says less about practice, preparation and safe intervention.

## Per-module system

| Module | Location / scene | Accent | Icon | Seal | Lumo pose |
|---|---|---|---|---|---|
| Begin (stop 0) — LUMO's village | The new village on its plateau above the sea; art direction in `brand/village/` | Olive, #5B7F2A | village.svg | stage-0.svg, two houses and a lantern | LUMO as an apprentice builder, with a work apron and a small lantern |
| Discover — Quick Lab | Harbour lab, welcome gate, disposable cloud-lab dock | Sea, #1E9FB5 | lab.svg | stage-1.svg, gate | Waving hello with lantern raised |
| Deploy — Deployment Patterns | Harbour-side pattern workshop with two blank model routes | Sky, #2F6FD0 | deploy.svg | stage-2.svg, route marker | Pointing at two alternatives without presenting either as the one right answer |
| Operate — Kolla-Ansible Academy | Library workshop with source scrolls and brass server models | Wood, #C4904F | day2.svg | stage-3.svg, gear | Reading source beside a small server model |
| Intervene — VM Runbooks | Bridge watch above a calm sea | Green, #2C7A43 | runbooks.svg | stage-4.svg, bridge | Inspecting a clue with the lantern and showing the next safe check |
| Go to production — Production Guide | Lighthouse and harbour mouth | Terracotta, #B55A3A | production.svg | stage-5.svg, lighthouse | Pausing with compass and lantern before the production-bound route |
| Compare — OKD OpenStack lab | Citadel of automatons, where brass mechanisms move identical crates | Navy, #1F3A6B | okd.svg | stage-6.svg, stacked crates and a loop | Watching the mechanisms, comparing them with the deployment workshop |
| Equip — Operator skills | Companions' hall open to the sea, where lanterns, maps and tools are made ready | Violet, #6E5A9E | skills.svg | stage-7.svg, a satchel | Packing a satchel for the road |
| Book — deeper reading | Quiet archive library overlooking the island | Wood-dark, #6B4220 | book.svg | Separate bookplate; not a sixth stage seal | Sitting on a crate and reading |

The module accent is a navigation and illustration cue only. Readable labels use the shared text and link tokens. Risk states use their separate semantic colors.
