---
title: Horizon
description: Where the 2025.1 study covers Horizon (role horizon), from what -t horizon runs and its settings files to the single compress attempt and sessions in memcached.
tags: [horizon, memcached, images, risk, dependencies, unknowns]
---

# Horizon

This page is the starting point for Horizon, the `horizon` role: one container, `horizon`, on the control nodes of the
example inventory (`inventory/multinode:119-120`), selected by the tag `horizon` (`site.yml:738-750`). The role has no
`register.yml`, so it is never registered in Keystone, and by default it runs no bootstrap: `bootstrap.yml` is included
only when `horizon_backend_database` is true (`roles/horizon/tasks/deploy.yml:10-11`). As in 2024.1, that variable is
a plain `false` (`group_vars/all.yml:1267`) [CODE] ([Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)).

**Changed in 2025.1** [CODE]:
- **One `compress` attempt:** the image start script runs `manage.py compress --force` once, under `set -o errexit`
  (kolla `docker/horizon/extend_start.sh:3`, `:244-248`); the 2024.1 loop of five attempts is gone. A failing
  `compress` now stops the start at the first failure (below).
- **Restarts:** the config tasks notify nothing; `check-containers.yml` imports `service-check-containers`, which
  restarts `horizon` only when its configuration or definition changed
  ([Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)). The handler has no `kolla_action != "config"`
  guard any more (`roles/horizon/handlers/main.yml:2-15`). New `check.yml` (`roles/horizon/tasks/check.yml:2-4`).
- **`ENABLE_VENUS` is now set** from `enable_horizon_venus`, which follows `enable_venus`
  (`roles/horizon/defaults/main.yml:23`, `group_vars/all.yml:902`): the container environment gains a variable, so the
  first 2025.1 run recreates `horizon` and regenerates the static assets.
- **Swift settings removed** from `_9998-kolla-settings.py` (`SWIFT_FILE_TRANSFER_CHUNK_SIZE` and the `swiftclient`
  logger), with the Swift role ([Swift](swift.md)).
- **Glance CORS:** `horizon_public_endpoint`, which Glance allows as CORS origin, is now built from
  `horizon_external_fqdn` instead of `kolla_external_fqdn` (`group_vars/all.yml:479-481`,
  `roles/glance/templates/glance-api.conf.j2:147-148`); with `horizon_external_fqdn` overridden, the first 2025.1 run
  changes `glance-api.conf`.
- **Other:** both HAProxy backends add `option httpchk` (`roles/horizon/defaults/main.yml:41,62`), which a
  `-t horizon` run renders without restarting HAProxy ([F18](../reference/findings.md#f18)); `horizon_copy_certs` drives
  the CA copy; the image name takes `docker_image_name_prefix`; the settings hash also covers
  `/etc/openstack-dashboard/themes` (kolla `docker/horizon/extend_start.sh:209-213`).
- **No rolling reconfigure** through the CLI ([F19](../reference/findings.md#f19)); a batched run is
  `kolla-ansible deploy -t horizon -e kolla_serial=N`.

The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)

No operation page gives a command line for the `horizon` tag. With defaults, `-t horizon` runs the loadbalancer horizon
include (`site.yml:188-192`), config, check-containers and, if anything changed, the horizon restart handler
(`roles/horizon/tasks/deploy.yml:2-14`; [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), paragraph
below the table). It does not run `common`: as in 2024.1, `common` is its own play, tagged `common` only
(`site.yml:88-103`) [CODE]. `upgrade` runs the same files, with `bootstrap_service.yml` (no DB creation) instead of
`bootstrap.yml`, again only with `horizon_backend_database` (`roles/horizon/tasks/upgrade.yml:2-14`) [CODE].

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

- **Settings files (since 2024.1)** [CODE]. `local_settings.j2` and `custom_local_settings.j2` no longer
  exist; the role renders `_9998-kolla-settings.py` and `_9999-custom-settings.py`
  (`roles/horizon/tasks/config.yml:64-90`), each looked up with `with_first_found` in
  `/etc/kolla/config/horizon/<host>/`, then `/etc/kolla/config/horizon/`, then the role template (`:72-75`, `:86-89`).
  `config.json` copies them into `/etc/openstack-dashboard/local_settings.d/`
  (`roles/horizon/templates/horizon.json.j2:21-32`), a directory the image creates and links into the
  `openstack_dashboard` package, next to a `local_settings.py` copied from Horizon's example file (kolla
  `docker/horizon/Dockerfile.j2:59-66`). What follows for an operator:
  1. An override kept at the pre-2024.1 names, `/etc/kolla/config/horizon/local_settings` or `custom_local_settings`,
     is not read by any task: the lookup falls through to the role template, with no warning. It must be moved to the
     new names.
  2. The role's `_9998` template no longer starts from Horizon's example file: it has no imports and no example
     comments, and it starts directly with Kolla's settings (`roles/horizon/templates/_9998-kolla-settings.py.j2:1-5`);
     `_9999-custom-settings.py.j2` is empty. An operator file at the new names replaces the whole role template, as
     before. [NOT AVAILABLE] In which order Horizon loads `local_settings.py` and the files of `local_settings.d`, and
     where the `CACHES` that `_9998` extends is defined (`:21-22`): that is Horizon code, not in these sources.
    3. No task of the role removes older `local_settings` and `custom_local_settings` files from `/etc/kolla/horizon/` (no
     `state: absent` under `roles/horizon/`); they are not listed in `config.json`.
- **Removed dashboards (since 2024.1)** [CODE]. The freezer, murano, sahara, senlin, solum and vitrage entries are
  absent from the container environment (`ENABLE_*`, `roles/horizon/defaults/main.yml:9-25`) and from the policy list
  (`roles/horizon/tasks/config.yml:16-38`), and the murano-dashboard clone and dev-mode volume are gone
  (`roles/horizon/tasks/clone.yml`, `roles/horizon/defaults/main.yml:126-131`). `ENABLE_FWAAS`, added in 2024.1, is driven by
  `enable_horizon_fwaas` = `enable_neutron_fwaas` (`roles/horizon/defaults/main.yml:12`, `group_vars/all.yml:891`).
    Changed in 2025.1: Kolla-Ansible now sets the image's venus switch, `ENABLE_VENUS` (above).
- [fact sheet C §4.2][sheet-c-42]: enabling or disabling any service that has a horizon plugin (designate, octavia,
  magnum, fwaas, …) changes the container environment (`ENABLE_<PLUGIN>`, `roles/horizon/defaults/main.yml:9-25`); the
  horizon container is then recreated on the next deploy/reconfigure even if no horizon config changed [CODE].
- [Kolla images §5.2](../concepts/kolla-images.md#52-horizon-static-assets): a recreate (new image, changed parameters)
  or a settings change makes the next start regenerate the static assets; a plain restart with unchanged settings does
  not [CODE]. The settings hash covers `/etc/openstack-dashboard/local_settings.d`, where the two kolla files now live
  (kolla `docker/horizon/extend_start.sh:206-224`). **Changed in 2025.1:** `manage.py compress --force` runs once
  (`:244-248`); the script runs under `set -o errexit` (`:3`), so a failing `compress` ends the script at once.
  `kolla_start` sources this script (kolla `docker/base/start.sh:23`), so the start fails before `kolla_httpd_setup`
  and httpd (kolla `docker/horizon/extend_start.sh:264`) [CODE]. [NOT AVAILABLE] How long such a start takes, and why
  `compress` would fail; to be confirmed by the community.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>`
  API service: safe on its own "yes, it is the intended unit"; horizon runs neither Keystone registration nor DB sync,
  by default; batch with `deploy -e kolla_serial=N` (`reconfigure` forces `kolla_serial=0`). Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy
  VIP. The play's `serial` is `kolla_serial`, default `0`, and its `max_fail_percentage` defaults to 100
  (`site.yml:743-747`) [CODE].
- **HAProxy frontends** [CODE]: as in 2024.1, the external frontends take `horizon_external_fqdn` (default
  `kolla_external_fqdn`, `group_vars/all.yml:479`) and the redirect frontends get an ACME challenge rule
  (`roles/horizon/defaults/main.yml:43-72`). The backend balances `roundrobin` when memcached or the DB backend is
  enabled, else `source` (`:40`); changed in 2025.1, they add `option httpchk`.
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `--skip-tags haproxy` when you don't
  intend to change frontends; a `-t horizon` run renders the frontends without restarting HAProxy
  ([F18](../reference/findings.md#f18)).
- [R24](../risk/risk-register.md#r24), container stop timeout: the stop goes through the container's systemd unit,
  whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:33`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:148`).
  Precautions: drain long operations before restarts; raise `docker_graceful_timeout` if needed. The first 2025.1 check
  of a container whose unit 2024.1 wrote reports drift ([F16](../reference/findings.md#f16)).

### Known limits and open points

- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour),
  row "Horizon": the sources do not establish how long a start that regenerates the static assets takes.
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "memcached": the sources do not establish whether cached tokens are lost when the membership changes or the container
  restarts, and the effect on auth latency and Horizon sessions.
- [fact sheet C §4.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#48-operational-notes),
  "Operational notes", three points, checked against 2025.1: sessions live in memcached unless the DB backend is used
  (in 2025.1: when `horizon_backend_database` is false and the `memcached` group is not empty,
  `roles/horizon/templates/_9998-kolla-settings.py.j2:7-23` [CODE]; NOT AVAILABLE: whether a horizon restart or a
  memcached restart logs users out); image side: when `collectstatic` and `compress` run (NOT AVAILABLE: how long they
  take); Horizon config is independent of host count except for the memcached list (the only `groups[...]` lookup of
  the settings template is `groups['memcached']`, `_9998-kolla-settings.py.j2:19-21`) [CODE].
- [fact sheet C §8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#8-not-available-list), item 9:
  NOT AVAILABLE: Horizon restart: session survival (memcached) and start-up duration.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 14: memcached has no data volume and no
  persistence option [CODE]; whether every restart therefore empties the cache, with token-cache misses and lost Horizon
  sessions where they are kept in memcached, is [NOT AVAILABLE: memcached semantics].
- [Kolla images §7](../concepts/kolla-images.md#7-what-is-not-available-from-the-sources): not available from the
  sources: Horizon regeneration time after a recreate or a settings change, and why `compress` could fail (in 2025.1 a
  single failure stops the start).
- The image start script still handles the pre-2024.1 names: it links `/etc/openstack-dashboard/custom_local_settings` when
  that file exists and includes `local_settings` and `custom_local_settings` in the settings hash (kolla
  `docker/horizon/extend_start.sh:17-23,209-212`) [CODE]. Kolla-Ansible 2025.1 does not write either file
  (`roles/horizon/templates/horizon.json.j2:21-32`), so under Kolla-Ansible these branches find nothing.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), [Open
  questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry specific to
  Horizon.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py horizon -->

| Item | Value |
|---|---|
| Play | site.yml:738 |
| Tags | horizon |
| Play host patterns | horizon |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `horizon` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → clone (if) → bootstrap (if) → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, policy_item.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `_9998-kolla-settings.py.j2`, `_9999-custom-settings.py.j2`, `horizon.conf.j2`, `horizon.json.j2` |
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
- [Kolla images §5.2](../concepts/kolla-images.md#52-horizon-static-assets) — when a start regenerates the static
  assets, and the new `compress` retry
- [Components](index.md) — the other component pages

[sheet-c-42]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#42-horizon_services-ansibleroleshorizondefaultsmainyml2-76
