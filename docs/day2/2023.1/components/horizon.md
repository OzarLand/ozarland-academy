---
title: Horizon
description: Where the study covers Horizon (role horizon), from what -t horizon runs with defaults to sessions in memcached, static assets and open points.
tags: [horizon, memcached, images, risk, dependencies, unknowns]
---

# Horizon

This page is the starting point for Horizon, the `horizon` role: one container, `horizon`, on the control nodes of the
example inventory (`inventory/multinode:140-141`), selected by the tag `horizon` (`site.yml:643`). The role has no
`register.yml`, so it is never registered in Keystone, and by default it runs no bootstrap: `bootstrap.yml` is included
only when `horizon_backend_database` is true (`roles/horizon/tasks/deploy.yml:10-11`), and that defaults to
`enable_murano` (`group_vars/all.yml:1052`) [CODE]
([Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)). The lists
below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to check around
a run and what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)

No operation page gives a command line for the `horizon` tag. With defaults, `-t horizon` runs the loadbalancer horizon
include, config, check-containers and, if anything changed, the horizon restart handler ([Tags
§3](../risk/tags.md#3-what-a-tag-really-executes-master-table), paragraph below the table). It no longer runs `common`:
in 2023.1 `common` is its own play, tagged `common` only (`site.yml:86-97`) [CODE].

### Impact and risk

- **What the tag executes (`horizon`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row
  `<svc>` and the paragraph below the table; [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service
- **Risks:** [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet C §4](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#4-horizon)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `horizon`), [Kolla
  images §5.2](../concepts/kolla-images.md#52-horizon-static-assets)

### Before and after a run

- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service: safe on its own "yes, it is the intended unit"; horizon runs neither Keystone registration nor DB sync, by
  default; batch with `ANSIBLE_SERIAL`. Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy
  VIP.
- [fact sheet C §4.2][sheet-c-42]: enabling or disabling any service that has a horizon plugin (designate, octavia,
  magnum, …) changes the container environment (`ENABLE_<PLUGIN>`, `roles/horizon/defaults/main.yml:8-29`); the horizon
  container is then recreated on the next deploy/reconfigure
  even if no horizon config changed.
- [Kolla images §5.2](../concepts/kolla-images.md#52-horizon-static-assets): a recreate (new image, changed parameters)
  or a settings change makes the next start regenerate the static assets; a plain restart with unchanged settings does
  not [CODE]. [NOT AVAILABLE] How long such a start takes.
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `ANSIBLE_SERIAL=1` for haproxy changes;
  `--skip-tags haproxy` when you don't intend to change frontends.
- [R24](../risk/risk-register.md#r24), container stop timeout: in 2023.1 the stop goes through the container's systemd
  unit with `docker stop -t` `docker_graceful_timeout` (60 s, `group_vars/all.yml:140`), no longer 10 s. Precautions:
  drain long operations before restarts; raise `docker_graceful_timeout` if needed.

### Known limits and open points

- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour),
  row "Horizon": the sources do not establish how long a start that regenerates the static assets takes.
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "memcached": the sources do not establish whether cached tokens are lost when the membership changes or the container
  restarts, and the effect on auth latency and Horizon sessions.
- [fact sheet C §4.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#48-operational-notes),
  "Operational notes", three points: sessions live in memcached unless the DB backend is used (in 2023.1: when
  `horizon_backend_database` is false and the `memcached` group is not empty,
  `roles/horizon/templates/local_settings.j2:32-33,177-178` [CODE]; NOT AVAILABLE: whether a horizon restart or a
  memcached restart logs users out); image side: when `collectstatic` and `compress` run
  (NOT AVAILABLE: how long they take); Horizon config is independent of host count except for the memcached list.
- [fact sheet C §8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#8-not-available-list), item 9:
  NOT AVAILABLE: Horizon restart: session survival (memcached) and start-up duration.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 14: memcached has no data volume and no
  persistence option [CODE]; whether every restart therefore empties the cache, with token-cache misses and lost Horizon
  sessions where they are kept in memcached, is [NOT AVAILABLE: memcached semantics].
- [Kolla images §7](../concepts/kolla-images.md#7-what-is-not-available-from-the-sources): not available from the
  sources: Horizon regeneration time after a recreate or a settings change.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), [Open
  questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry on Horizon.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py horizon -->

| Item | Value |
|---|---|
| Play | site.yml:643 |
| Tags | horizon |
| Play host patterns | horizon |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `horizon` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → clone (if) → bootstrap (if) → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, policy_item.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `custom_local_settings.j2`, `horizon.conf.j2`, `horizon.json.j2`, `local_settings.j2` |
| Handlers (definition order) | Restart horizon container |
| Key variables | `enable_horizon`, `enable_horizon_*`, `horizon_backend_database` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Memcached](memcached.md) — Horizon keeps its sessions there unless the DB backend is used
- [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) — what `-t horizon` runs with defaults, in the
  paragraph below the master table
- [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects) — what a service tag
  also touches
- [HAProxy + Keepalived](haproxy-keepalived.md) — `-t horizon` runs the loadbalancer horizon include
- [Kolla images §5.2](../concepts/kolla-images.md#52-horizon-static-assets) — when a start regenerates the static assets
- [Components](index.md) — the other component pages

[sheet-c-42]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#42-horizon_services-ansibleroleshorizondefaultsmainyml2-69
