---
title: Architecture and concepts
description: "Entry to the 2025.1 concept pages: repository architecture, deployment execution flow, compute scaling, and what the kolla images do at container start."
tags: [deploy, reconfigure, handlers, serial, scaling, images, kolla-set-configs, one-shot, podman]
---

# Architecture and concepts

How Kolla-Ansible 2025.1 is built, how it decides what runs when, how its work grows with the number of compute nodes,
and what the kolla images do when a container starts. [Repository architecture](repository-architecture.md) defines the
vocabulary that the other pages build on, including the container module `kolla_container`, which drives Docker or
Podman, and, new in 2025.1, the Python `kolla-ansible` CLI.

<img src="../assets/images/S3-concepts-and-reference.webp" width="1536" height="1024" loading="lazy" alt="Ilyan and LUMO stand between a table of building models and brass columns and a bookcase of plain boxes, books and scrolls.">

## Pages

<div class="grid cards" markdown>

- **[Repository architecture](repository-architecture.md)** — How the machine is built: which entry points exist, how a
  CLI command becomes an `ansible-playbook` run (in 2025.1 through the Python CLI, which fixes `kolla_serial=0` for
  `reconfigure` and `upgrade`), how `site.yml` is laid out, what every service role has in common, which custom
  modules actually touch the hosts, and what ansible-collection-kolla (pulled by `requirements.yml`) contributes.
- **[Deployment execution flow](deployment-execution-flow.md)** — How Kolla-Ansible 2025.1 decides what runs when: play
  order, the steps inside each role, the shared `service-check-containers` step that now decides every restart,
  handler flush points, batching, and how `deploy`, `reconfigure`, `upgrade`, `deploy-containers`, `genconfig`, `pull`
  and `stop` differ.
- **[Compute scaling and performance](compute-scaling-and-performance.md)** — Which Kolla-Ansible 2025.1 operations grow
  with the number of compute nodes, why, and how to bound them, with the new per-compute hypervisor list. No timings
  are given: work is counted as operations read from the source.
- **[Kolla images: start path and one-shot containers](kolla-images.md)** — What the 2025.1 kolla images do when a
  container starts, what `kolla_set_configs --check` compares (in 2025.1 also the command and the list of files) and
  what its exit codes mean with Docker and with Podman, and what the one-shot containers that Kolla-Ansible starts
  actually run. The images were read, not built or run.

</div>

## Related

- [What a tag really executes](../risk/tags.md) — how tags select the work described here
- [Component dependencies](../components/dependencies.md) — runtime communication, which is not deployment order
- [Nova deep dive](../components/nova-deep-dive.md) — the nova plays
- [Generated inventory](../reference/generated-inventory.md) — every play, container, role and handler
- [Glossary](../reference/glossary.md) — the terms the study uses, with the place where each is defined
- [Architecture and concepts (2024.1)](../../2024.1/concepts/) — the same pages for the previous release
