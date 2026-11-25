---
title: Memcached
description: Where the 2025.1 study covers memcached (role memcached, two tags), from the membership risk and its command-only settings to dependencies and open points.
tags: [memcached, kolla-set-configs, inventory, risk, dependencies, bugs, unknowns]
---

# Memcached

This page is the starting point for memcached, the `memcached` role: one container, `memcached`, on the control nodes of
the example inventory (`inventory/multinode:116-117`), selected by the tags `memcached` and `memcache`
(`site.yml:417-429`). As in 2024.1, no role has a `common` dependency: `common` is its own play, tagged `common` only
(`site.yml:88-103`), and no role under `ansible/roles/` has a `meta/` directory, so memcached is not an exception
([Tags §1](../risk/tags.md#1-where-tags-are-defined), row "Role-level tags") [CODE]. **Changed in 2025.1** [CODE]: the config task notifies no handler any more and the container check is the shared
`service-check-containers` role (below); the image name takes `docker_image_name_prefix`
(`roles/memcached/defaults/main.yml:27`); `check.yml` runs the `service-check` role of `kolla-ansible check`
(`roles/memcached/tasks/check.yml:2-4`). The lists below say where the study covers how
to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open; the
service card follows them.

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
- **Sequence** [CODE]: `deploy` and `reconfigure` run `config.yml` (config directory and `config.json`) then
  `check-containers.yml`, with no flush, so the restart handler runs at the end of the play
  (`roles/memcached/tasks/deploy.yml:2-4`, `reconfigure.yml:2`); `upgrade` runs the same two files
  (`roles/memcached/tasks/upgrade.yml:2-4`). **Changed in 2025.1:** the `config.json` task notifies nothing (`roles/memcached/tasks/config.yml:13-23`);
  `check-containers.yml` imports `service-check-containers` (`roles/memcached/tasks/check-containers.yml:2-3`), which
  notifies `Restart memcached container` only when `compare_container` reports the container changed. The handler
  has no `kolla_action != "config"` guard any more (`roles/memcached/handlers/main.yml:2-13`).
- **Risks:** [R4](../risk/risk-register.md#r4)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)
- **Who reads the membership** [CODE]: the templates or defaults of 27 roles loop over `groups['memcached']` (28 in 2024.1; the swift role is gone). Example: `memcached_servers` in `neutron.conf`
  (`roles/neutron/templates/neutron.conf.j2:121`), which is rendered for the Open vSwitch agent too
  (`roles/neutron/tasks/config.yml:73-103`).

### Evidence

- **Fact sheet:** [fact sheet A §3](../reference/factsheets/a-infra-lb-ovn.md#3-memcached-role)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (row `memcached`). The
  kolla `docker/memcached` directory is identical to 2024.1's apart from a `kolla_patch_sources()` macro call: a
  `memcached` user, the `memcached` package, no start script (kolla `docker/memcached/Dockerfile.j2:10-20`) [CODE].

### Before and after a run

- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `memcached`
  / `memcache`: safe on its own "yes, off-peak"; prerequisites: none.
- [R4](../risk/risk-register.md#r4), precautions for a change of memcached membership: plan as a dataplane change, like
  R3/R5: batch with `--limit` or `deploy -e kolla_serial=N` (`reconfigure` forces `kolla_serial=0`,
  [F19](../reference/findings.md#f19)), network nodes one at a time; low-traffic window.
- **Settings in the command, now seen by the check** [CODE]. Every memcached setting is in the `command` of its
  `config.json`, and its `config_files` list is empty: listen address `api_interface_address`, `memcached_port`,
  `memcached_connection_limit` and `memcached_max_memory` (`roles/memcached/templates/memcached.json.j2:1-4`; defaults
  `roles/memcached/defaults/main.yml:54-57`, `group_vars/all.yml:575`). In 2024.1 `kolla_set_configs --check` saw none
  of them. **Changed in 2025.1:** it compares the `command` of `config.json` with the command saved in `/run_command`
  when the container started (kolla `docker/base/set_configs.py:580-586`, [F14](../reference/findings.md#f14),
  [Kolla images §3.1](../concepts/kolla-images.md#31-what-is-compared)). What follows for a change of one of these
  settings:
  1. A normal `deploy`/`reconfigure` writes the new `config.json`; the check step finds the command different and
     notifies `Restart memcached container`. The restart runs `kolla_set_configs` again, which writes the new
     `command` to `/run_command`, and `kolla_start` executes it ([Kolla images
     §2.2](../concepts/kolla-images.md#22-kolla_start-step-by-step)).
  2. **Changed in 2025.1:** after a separate `genconfig` (`kolla_action=config`), the next `deploy-containers`,
     `deploy` or `reconfigure` detects the change the same way and restarts the container. In 2024.1 the change
     applied only at the next restart for another reason ([Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences),
     item 1; [Predict and inspect a run](../operations/predict-a-run.md), row "See what will restart").
  3. The other compared items: the image, the volumes, the dimensions and the healthcheck, which are container
     parameters compared by `compare_container` (`roles/service-check-containers/tasks/main.yml:4-29`,
     `module_utils/kolla_container_worker.py:58-89`), plus the systemd unit text. The healthcheck is
     `healthcheck_listen memcached <memcached_port>` (`roles/memcached/defaults/main.yml:36-43`), so a port change also
     changes a compared parameter.
- **First 2025.1 check of a container that 2024.1 created** [CODE]: the systemd unit text changed again
  ([F16](../reference/findings.md#f16)), so a memcached container that no 2025.1 run has recreated or restarted yet is
  restarted at its first 2025.1 `deploy`/`reconfigure` (recreated with Docker on Debian or Ubuntu, for the new default
  `nofile` ulimit), on all memcached hosts at once (the play's `serial`, below).

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `kolla images`, and
  [F14](../reference/findings.md#f14): **narrower in 2025.1**, the command is now compared, so memcached's settings
  are detected; only a `permissions`-only change of `config.json` is still missed [CODE].
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files [CODE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "memcached": the sources do not establish whether cached tokens are lost when the membership changes or the container
  restarts, and the effect on auth latency and Horizon sessions.
- [fact sheet A §3.8](../reference/factsheets/a-infra-lb-ovn.md#38-operationally-notable), "Operationally notable", four
  items. Checked against 2025.1 [CODE]: all memcached instances restart at once (the play's `serial` is `kolla_serial`,
  default `0`, `site.yml:422`; the play's new `max_fail_percentage` defaults to 100, `site.yml:423-426`, and so never
  stops it early); adding or removing a memcached host is expensive (27 roles loop over `groups['memcached']` in their
  templates or defaults, [R4](../risk/risk-register.md#r4)); tag aliases differ: only `-t memcached` selects the
  memcached include of the loadbalancer play (`site.yml:233-237`), and that include renders a frontend only with
  `enable_haproxy_memcached` (default `no`, `group_vars/all.yml:850`, `roles/memcached/defaults/main.yml:11-13`), so
  with defaults the two tags differ in nothing visible; "memcached has no `common` dependency" is not specific to
  memcached (no role has one, see above).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 14: memcached has no data volume and no
  persistence option (`roles/memcached/defaults/main.yml:45-48`, `roles/memcached/templates/memcached.json.j2:2`)
  [CODE]; whether every restart therefore empties the cache is [NOT AVAILABLE: memcached semantics].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py memcached -->

| Item | Value |
|---|---|
| Play | site.yml:417 |
| Tags | memcache, memcached |
| Play host patterns | memcached |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `memcached` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers |
| Task files | check-containers.yml, check.yml, config.yml, config_validate.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `memcached.json.j2` |
| Handlers (definition order) | Restart memcached container |
| Key variables | `enable_memcached`, `memcached_port` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Change control-plane membership](../operations/change-control-plane-membership.md) — a `memcached`-only change does
  not touch nova-compute but still restarts the neutron agents on computes
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — the templates
  of 27 roles loop over `groups['memcached']` ([R4](../risk/risk-register.md#r4))
- [Keystone](keystone.md) — memcached is its token cache
- [Horizon](horizon.md) — it keeps its sessions in memcached when `horizon_backend_database` is false (the default,
  `group_vars/all.yml:1267`) and the `memcached` group is not empty
  (`roles/horizon/templates/_9998-kolla-settings.py.j2:19-22`)
- [Predict and inspect a run](../operations/predict-a-run.md) — `kolla_set_configs --check` and its exit codes
- [Components](index.md) — the other component pages
