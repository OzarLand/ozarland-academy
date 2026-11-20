---
title: Architecture and concepts
description: "Entry to the concept pages: repository architecture, deployment execution flow, compute scaling, and what the kolla images do at container start."
tags: [deploy, reconfigure, handlers, serial, scaling, images, kolla-set-configs, one-shot]
---

# Architecture and concepts

How Kolla-Ansible Ussuri is built, how it decides what runs when, how its work grows with the number of compute nodes,
and what the kolla images do when a container starts. [Repository architecture](repository-architecture.md) defines the
vocabulary that the other pages build on.

## Pages

<div class="grid cards" markdown>

- **[Repository architecture](repository-architecture.md)** — How the machine is built: which entry points exist, how a
  CLI command becomes an `ansible-playbook` run, how `site.yml` is laid out, what every service role has in common, and
  which custom modules actually touch the hosts.
- **[Deployment execution flow](deployment-execution-flow.md)** — How Kolla-Ansible Ussuri decides what runs when: play
  order, the steps inside each role, handler flush points, batching, and how `deploy`, `reconfigure`, `upgrade`,
  `deploy-containers`, `genconfig`, `pull` and `stop` differ.
- **[Compute scaling and performance](compute-scaling-and-performance.md)** — Which Kolla-Ansible Ussuri operations grow
  with the number of compute nodes, why, and how to bound them. No timings are given: work is counted as operations read
  from the source.
- **[Kolla images: start path and one-shot containers](kolla-images.md)** — What the kolla images do when a container
  starts, and what the one-shot containers that Kolla-Ansible starts with `KOLLA_BOOTSTRAP`, `KOLLA_UPGRADE`,
  `KOLLA_OSM` and similar variables actually run. The images were read, not built or run.

</div>

## Related

- [What a tag really executes](../risk/tags.md) — how tags select the work described here
- [Component dependencies](../components/dependencies.md) — runtime communication, which is not deployment order
- [Nova deep dive](../components/nova-deep-dive.md) — the nova plays
- [Generated inventory](../reference/generated-inventory.md) — every play, container, role and handler
- [Glossary](../reference/glossary.md) — the terms the study uses, with the place where each is defined
