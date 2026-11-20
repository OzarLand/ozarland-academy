---
title: Memcached
description: Where the study covers memcached (role memcached, two tags), from the membership risk and what the drift check cannot see to dependencies and open points.
tags: [memcached, kolla-set-configs, inventory, risk, dependencies, bugs, unknowns]
---

# Memcached

This page is the starting point for memcached, the `memcached` role: one container, `memcached`, on the control nodes of
the example inventory, selected by the tags `memcached` and `memcache`. Unlike most roles, it has no `common` dependency
([fact sheet A §3.8](../reference/factsheets/a-infra-lb-ovn.md#38-operationally-notable)). The lists below say where the
study covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays
open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Change control-plane membership
  §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller),
  [Reconfigure Neutron §3](../operations/reconfigure-neutron.md#3-what-restarts-code)
- **Command:** [Change control-plane membership
  §1.1](../operations/change-control-plane-membership.md#11-remove-or-replace-a-controller)

### Impact and risk

- **What the tag executes (`memcached` / `memcache`):** [Tags
  §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `memcached` /
  `memcache`
- **Risks:** [R4](../risk/risk-register.md#r4)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)

### Evidence

- **Fact sheet:** [fact sheet A §3](../reference/factsheets/a-infra-lb-ovn.md#3-memcached-role)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (row `memcached`)

### Before and after a run

- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `memcached`
  / `memcache`: safe on its own "yes, off-peak"; prerequisites: none.
- [R4](../risk/risk-register.md#r4), precautions for a change of memcached membership: plan as a dataplane change, like
  R3/R5: batch with `--limit` or `ANSIBLE_SERIAL`, network nodes one at a time; low-traffic window.
- [Predict and inspect a run](../operations/predict-a-run.md), row "See what will restart": `command`, `permissions`,
  removed entries and stale optional files are not compared, so memcached (`"config_files": []`) always returns 0.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 1: a normal deploy or reconfigure applies a
  `config.json`-only change; after a separate `genconfig`, `deploy-containers` sees no drift and later runs do not
  restart for it either. Memcached is the extreme case. The change applies at the next restart for another reason
  [CODE].

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `kolla images`:
  `kolla_set_configs --check` compares only `config_files` entries ([F14](../reference/findings.md#f14)): changes
  confined to `config.json` (`command`, `permissions`; all of memcached's settings) are never detected. Status: [CODE].
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files [CODE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "memcached": the sources do not establish whether cached tokens are lost when the membership changes or the container
  restarts, and the effect on auth latency and Horizon sessions.
- [fact sheet A §3.8](../reference/factsheets/a-infra-lb-ovn.md#38-operationally-notable), "Operationally notable", four
  items: all memcached instances restart at once; adding or removing a memcached host is expensive; tag aliases differ
  (`-t memcache` reconfigures the container but not its haproxy file, only `-t memcached` does both); memcached has no
  `common` dependency.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 14: memcached has no data volume and no
  persistence option [CODE]; whether every restart therefore empties the cache is [NOT AVAILABLE: memcached semantics].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py memcached -->

| Item | Value |
|---|---|
| Play | site.yml:481 |
| Tags | memcache, memcached |
| Play host patterns | memcached |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `memcached` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers |
| Task files | check-containers.yml, check.yml, config.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `memcached.json.j2` |
| Handlers (definition order) | Restart memcached container |
| Key variables | `enable_memcached`, `memcached_port` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Change control-plane membership](../operations/change-control-plane-membership.md) — a `memcached`-only change does
  not touch nova-compute but still restarts the neutron agents on computes
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — the templates
  of 37 roles loop over `groups['memcached']`
- [Keystone](keystone.md) — memcached is its token cache
- [Horizon](horizon.md) — it keeps its sessions in memcached when `horizon_backend_database` is false
- [Predict and inspect a run](../operations/predict-a-run.md) — `kolla_set_configs --check` and its exit codes
- [Components](index.md) — the other component pages
