---
title: HAProxy + Keepalived
description: "Where the 2024.1 study covers HAProxy, keepalived, ProxySQL and haproxy_ssh: what the tags run, the restart order, the VIP unknowns, known bugs."
tags: [haproxy, keepalived, loadbalancer, proxysql, letsencrypt, tags, handlers, serial, inventory, risk, dependencies, bugs, unknowns]
---

# HAProxy + Keepalived

This page is the starting point for HAProxy and keepalived in 2024.1. The `loadbalancer` role is applied by the "Apply
role loadbalancer" play to the `loadbalancer` group (the network nodes of the example inventory,
`inventory/multinode:84-85`), restricted to `enable_loadbalancer_True`, with play tags `haproxy`, `keepalived` and
`loadbalancer` and, new in 2024.1, a `max_fail_percentage` (`site.yml:105-120`). It runs the containers `haproxy`,
`keepalived` (`enable_keepalived`, default: follows `enable_haproxy`), `proxysql` (`enable_proxysql`, default `no`) and,
new in 2024.1, `haproxy_ssh` (only with `enable_letsencrypt`, default `no`)
(`roles/loadbalancer/defaults/main.yml:2-36`,
`group_vars/all.yml:723-725, :796, :839`). The same play holds 39 per-service `include_role … tasks_from: loadbalancer`
tasks (44 in 2023.1), run only for `deploy`, `reconfigure`, `upgrade` and `config` (`site.yml:121-326`); each of them
also carries its service tag. A service's `loadbalancer.yml` imports `loadbalancer-config`, which renders the HAProxy
frontend through `haproxy-config` and, with `enable_proxysql`, the ProxySQL users and rules through `proxysql-config`
(`roles/loadbalancer-config/tasks/main.yml:2-8`). The `hacluster` role is a separate play (`site.yml:709-722`) and is
not covered here; nor is the new `letsencrypt` play (`site.yml:328-340`), except where it touches HAProxy. The lists
below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to check
around a run and what stays open; the service card follows them.

> [!NOTE]
> **Changed in 2024.1** [CODE]
>
> - **Includes:** the play lost the freezer, murano, sahara, senlin, solum and vitrage includes and gained a
>   `letsencrypt` one (`site.yml:208-212`); the rabbitmq include is `when: enable_rabbitmq | bool` only (`:288`). The
>   letsencrypt services define no `haproxy` entry (`roles/letsencrypt/defaults/main.yml:2-16`), so `haproxy-config`
>   writes no frontend for them (`roles/haproxy-config/tasks/main.yml:17-21`); the ACME challenge path is routed by
>   horizon's frontends to an `acme_client` backend (`roles/horizon/defaults/main.yml:36-37, :70-73`,
>   `group_vars/all.yml:951-952`).
> - **New container `haproxy_ssh`:** an `sshd -D` on `api_interface_address:2985` that accepts the `haproxy_ssh_key`
>   (`roles/loadbalancer/templates/haproxy-ssh/haproxy-ssh.json.j2:2`, `sshd_config.j2:1-2`, `id_rsa.pub:1`,
>   `group_vars/all.yml:408`). It shares the `haproxy_socket` and `letsencrypt_certificates` volumes with haproxy
>   (`roles/loadbalancer/defaults/main.yml:137-143`). The lego container pushes a renewed certificate over SSH and runs
>   `update-haproxy-cert`, which loads it through the HAProxy admin socket (`set ssl cert`, then `commit ssl cert`), not
>   through a restart (kolla `docker/letsencrypt/letsencrypt-lego/sync-and-update-certificate.sh:83-89`,
>   `docker/haproxy/haproxy-ssh/update-haproxy-cert.sh:23, :50, :123-125`). That is why `haproxy_socket_level_admin`
>   now follows `enable_letsencrypt` (`roles/loadbalancer/defaults/main.yml:182`,
>   `templates/haproxy/haproxy_main.cfg.j2:13`).
> - **Certificates:** the PEM files now live in `/etc/haproxy/certificates/`, owned by `haproxy`, and are copied only
>   without Let's Encrypt (`roles/loadbalancer/templates/haproxy/haproxy.json.j2:21-44`,
>   `roles/loadbalancer/tasks/config.yml:211-247`); with TLS on and no PEM file, `haproxy_run.sh` first writes a
>   one-day self-signed certificate (`roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:3-36`). The haproxy
>   container always mounts `letsencrypt_certificates:/etc/haproxy/certificates`
>   (`roles/loadbalancer/defaults/main.yml:121`), so its definition differs from a 2023.1 one.
> - **Renamed variables:** `haproxy_processes` and `haproxy_process_cpu_map` are now `haproxy_threads` and
>   `haproxy_thread_cpu_map`, rendered as `nbthread` and a fixed `cpu-map auto:1/all 0-63`
>   (`roles/loadbalancer/defaults/main.yml:66-67`, `templates/haproxy/haproxy_main.cfg.j2:9-12`). The old names are
>   read nowhere under `ansible/`: an override that still uses them is silently ignored.
> - **Single external frontend** (`haproxy_single_external_frontend`, default `false`, `group_vars/all.yml:931`): one
>   `external_frontend` on the external VIP routes by `Host` header through `/etc/haproxy/external-frontend-map`
>   (`roles/loadbalancer/templates/haproxy/haproxy_external_frontend.cfg.j2:3-12`, written by
>   `roles/loadbalancer/tasks/config.yml:162-175`); each service adds its block to the map
>   (`roles/haproxy-config/tasks/main.yml:25-53`) and skips its own external HTTP frontend
>   (`roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:148-152`). Every `<svc>_public_port` now
>   depends on it (e.g. `group_vars/all.yml:335`).
> - **HTTP/2 and metrics:** TLS binds add `alpn h2,http/1.1` (`haproxy_enable_http2: "yes"`,
>   `group_vars/all.yml:920-921`, `roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:2-5`); HAProxy
>   itself serves Prometheus metrics on `api_interface_address:9101`
>   (`roles/loadbalancer/templates/haproxy/haproxy_main.cfg.j2:45-50`, `group_vars/all.yml:567, :1213`), and `upgrade`
>   first stops and removes the old `prometheus_haproxy_exporter`
>   container and its configuration (`roles/loadbalancer/tasks/upgrade.yml:4-19`).
> - **Keepalived:** the image's `check_alive.sh` lost its fallback HAProxy socket test (kolla
>   `docker/keepalived/check_alive.sh:9-33`); the check scripts are still one per enabled service, never for
>   `keepalived` or `haproxy-ssh`, and the removal task now runs only with `keepalived_track_script_enabled`
>   (`roles/loadbalancer/tasks/config.yml:74-111`).
> - **Handlers:** the same staged dance as 2023.1, with `kolla_container` instead of `kolla_docker`, plus a last
>   `Restart haproxy-ssh container` (`roles/loadbalancer/handlers/main.yml:331-345`).

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)
  (`-t haproxy reconfigure` on an unchanged cloud)
- **Command:** [Reconfigure a single service
  §1.2](../operations/reconfigure-a-service.md#12-avoid-touching-haproxy-during-a-service-run), [Command quick lookup by
  tag](../operations/command-quick-lookup.md)

### Impact and risk

- **What the tag executes (`haproxy`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `haproxy`; the
  loadbalancer play under a service tag: [Tags
  §2.3](../risk/tags.md#23-include_role--tags-always-inside-the-haproxy-play-code)
- **Risks:** [R8](../risk/risk-register.md#r8)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)

### Evidence

- **Fact sheet:** [fact sheet A §1](../reference/factsheets/a-infra-lb-ovn.md#1-haproxy-role-haproxy--keepalived)
  (the `loadbalancer` role in 2024.1); `haproxy-config`: [fact sheet A
  §2](../reference/factsheets/a-infra-lb-ovn.md#2-haproxy-config-role)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `haproxy`,
  `keepalived`)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services); deployment order: [Deployment
  execution flow](../concepts/deployment-execution-flow.md)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 5 (health gates): before the run, check
  HAProxy backends all UP. Repeat after each batch.
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 7 (scope): add `--skip-tags haproxy` when
  the frontends are not meant to change; it skips the whole loadbalancer play, whose three play tags are `haproxy`,
  `keepalived` and `loadbalancer` (`site.yml:115-118`).
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `haproxy`:
  the restart handlers run only when a task reports a change (they are notified, e.g.
  `roles/loadbalancer/tasks/config.yml:141-142`, `roles/loadbalancer/tasks/check-containers.yml:17-18`) [CODE]; with a
  change, prefer a window. Prerequisites: facts of every backend host; certificates if TLS is on and Let's Encrypt is
  off (`roles/loadbalancer/tasks/precheck.yml:57-98`).
- **First 2024.1 run on a 2023.1 cloud:** expect the restart handlers. The haproxy container definition gained a volume
  (`roles/loadbalancer/defaults/main.yml:121`), and `compare_container` also reports a unit file written by 2023.1
  ([F16](../reference/findings.md#f16)); `check-containers.yml` then notifies `Restart <name> container` for each
  container (`roles/loadbalancer/tasks/check-containers.yml:2-18`), which starts the staged sequence below for
  haproxy and keepalived [CODE].
- [R8](../risk/risk-register.md#r8), the restart order, still staged in 2024.1. Handlers run in their definition order,
  and each `listen`s to `Restart haproxy container`, `Restart proxysql container` or `Restart keepalived container`
  [CODE]:
  1. on every host of the batch, read the API interface addresses and group the hosts by whether they hold
     `kolla_internal_vip_address` (`roles/loadbalancer/handlers/main.yml:9-34`);
  2. on the backup hosts: stop keepalived (keepalived change only, `:36-49`), stop haproxy (haproxy or keepalived
     change, `:54-68`), stop proxysql (any of the three, `:70-88`), start haproxy and wait for `haproxy_monitor_port`
     (haproxy or keepalived change, `:90-118`), start proxysql when enabled and wait for its admin port (any of the
     three, `:120-152`), start keepalived (keepalived change only, `:154-175`);
  3. on the VIP holder: stop haproxy (haproxy or keepalived change, `:179-193`), stop proxysql (proxysql or keepalived
     change, `:195-208`), stop keepalived (keepalived change only, `:210-222`), then start them again in the same
     order, waiting for each port (`:224-305`);
  4. after a keepalived start, wait for haproxy and, when enabled, proxysql to answer on the internal VIP
     (`:307-329`);
  5. new in 2024.1 and last: `Restart haproxy-ssh container`, on every host at once, with no backup/VIP split
     (`:331-345`), notified by the haproxy-ssh files, its `config.json` or a container change
     (`roles/loadbalancer/tasks/config.yml:113-124, :289-304`).

  Every stop and start handler is skipped for `kolla_action == "config"`, and the wait handlers are notified only by
  the start handlers. An haproxy-only change therefore stops HAProxy on the
  VIP holder while its keepalived keeps running; whether the VIP moves meanwhile, and for how long clients fail, is
  [NOT AVAILABLE: keepalived semantics]. Precautions: see [R8](../risk/risk-register.md#r8); `--skip-tags haproxy`
  when you don't intend to change frontends.
- [R22](../risk/risk-register.md#r22), inventory reordering (loadbalancer, mariadb, glance, nova-conductor, keystone
  groups): keepalived priorities change (priority = position in `loadbalancer` + 1,
  `roles/loadbalancer/templates/keepalived/keepalived.conf.j2:15`, still `state BACKUP` and `nopreempt`, `:11-12`).
  Precautions: treat inventory order as configuration; never reorder casually.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` (and, with the
  single external frontend, of `/etc/kolla/haproxy/external-frontend-map`) against the previous version; after,
  `docker ps --filter name=haproxy` shows whether HAProxy restarted. The service's frontend file and its map block both
  notify `Restart haproxy container` (`roles/haproxy-config/tasks/main.yml:2-23, :25-53`) [CODE].
- **Upgrade from 2023.1:** `upgrade` stops and removes `prometheus_haproxy_exporter` before the deploy tasks
  (`roles/loadbalancer/tasks/upgrade.yml:4-21`); `deploy` and `reconfigure` do not
  (`roles/loadbalancer/tasks/deploy.yml:2-6`, `reconfigure.yml:2`). The old exporter listened on the same port 9101
  that HAProxy's own `listen metrics` now binds
  (`group_vars/all.yml:567`, `roles/loadbalancer/templates/haproxy/haproxy_main.cfg.j2:45-50`) [CODE]; what happens if
  a `deploy` runs while the old container still holds the port is [NOT AVAILABLE].
- **Overrides:** rename `haproxy_processes`/`haproxy_process_cpu_map` to `haproxy_threads`/`haproxy_thread_cpu_map` in
  `globals.yml` before the run (`roles/loadbalancer/defaults/main.yml:66-67`) [CODE].

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `haproxy`, read against 2024.1:
  restart instead of reload still holds (the image's `kolla_ensure_haproxy_latest_config`, kolla
  `docker/haproxy/haproxy/Dockerfile.j2:17`, is never called from `ansible/`, [Kolla images
  §5](../concepts/kolla-images.md#5-per-image-start-behaviour)); only Let's Encrypt certificates are reloaded without a
  restart (above). Stale `services.d` files are still never removed (`haproxy-config` only templates,
  `roles/haproxy-config/tasks/main.yml:2-23`; the only removal is `mariadb.cfg` when ProxySQL is enabled,
  `roles/loadbalancer/tasks/config.yml:60-72`); keepalived priority still comes from inventory order; `upgrade` is
  still the `deploy` task flow, now preceded by the exporter removal (`roles/loadbalancer/tasks/upgrade.yml:21`).
  Status: [CODE].
- **New stale files in 2024.1:** turning `haproxy_single_external_frontend` off leaves
  `services.d/external-frontend.cfg` in place (it is only templated when the option is on,
  `roles/loadbalancer/tasks/config.yml:162-175`), and `haproxy_run.sh` loads every file of `services.d`
  (`roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:38-40`); a disabled service's block also stays in
  `external-frontend-map` (`blockinfile` runs only for enabled services, `roles/haproxy-config/tasks/main.yml:47-51`).
  Status: [CODE].
- **Single external frontend, two points to check before enabling it** [CODE]: the map is copied into the container
  only when external TLS is on and Let's Encrypt is off (`roles/loadbalancer/templates/haproxy/haproxy.json.j2:21-28`),
  while the frontend always reads `/etc/haproxy/external-frontend-map`
  (`roles/loadbalancer/templates/haproxy/haproxy_external_frontend.cfg.j2:11`); and the frontend binds
  `haproxy_external_single_frontend_public_port` (role default `"443"`, `roles/loadbalancer/defaults/main.yml:192`,
  used at `haproxy_external_frontend.cfg.j2:10`) while the endpoints use `haproxy_single_external_frontend_public_port`
  (`443` with external TLS, else `80`, `group_vars/all.yml:932`). How HAProxy behaves without the map file, and
  whether the two ports disagree in a working setup without TLS, is [NOT AVAILABLE].
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), second row `site.yml`: the placement
  loadbalancer include still lacks `when: enable_placement` (`site.yml:248-251`). Status: [CODE].
- [Q5](../troubleshooting/open-questions.md#q5): "HAProxy restart: VIP behaviour". Status: [NOT AVAILABLE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "HAProxy restart": the sources do not establish whether keepalived drops or moves the VIP, and for how long; whether
  the node goes to FAULT; whether established connections are cut; whether nova and neutron get DB errors and instance
  metadata requests fail meanwhile; how HAProxy treats backends that are not up yet on a first deploy.
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored": no longer
  holds in 2024.1; containers stop through their systemd unit with `docker_graceful_timeout`
  ([R24](../risk/risk-register.md#r24)) [CODE]. Still [NOT AVAILABLE]: whether services started by a shell wrapper that
  does not `exec` them (e.g. `neutron-l3-agent`, `haproxy`: `haproxy_run.sh` ends in `xargs /usr/sbin/haproxy`,
  `roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:38-40`) receive SIGTERM at all.
- [fact sheet A §1.8](../reference/factsheets/a-infra-lb-ovn.md#18-operationally-notable-behaviour), "Operationally
  notable behaviour", read against 2024.1: any change means a full restart of haproxy, never a reload, staged backups
  first and VIP holder last (R8 above); whether a haproxy restart causes VIP failover or a VIP outage is [NOT
  AVAILABLE]; keepalived priority depends on inventory order; stale frontends are never removed; `-t haproxy` does not
  run `common` (`common` is its own play, `site.yml:88-103`); non-local bind is still set by the role, now through the
  `sysctl` role with the same values and the same `KOLLA_UNSET`/`KOLLA_SKIP` handling
  (`roles/loadbalancer/tasks/config-host.yml:8-18`, `roles/sysctl/tasks/main.yml:7-20`, with `set_sysctl`); VRRP router
  id collisions: `keepalived_virtual_router_id` still defaults to `51` (`group_vars/all.yml:224`);
  `keepalived_traffic_mode: unicast` is still available (default `multicast`,
  `roles/loadbalancer/defaults/main.yml:62`, `keepalived.conf.j2:17-29`) [CODE].
- [fact sheet A §2.4](../reference/factsheets/a-infra-lb-ovn.md#24-notable), "Notable" for the `haproxy-config` role:
  stale files are not removed; the file of a service whose `enabled` is false is left as it was; file name; facts are
  required; precedence. New in 2024.1: the map block per service (above).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 15: the VIP follows the HAProxy stats
  socket, and the ProxySQL admin socket when ProxySQL is enabled (one `check_alive_<service>.sh` per enabled service,
  `roles/loadbalancer/tasks/config.yml:93-111`; `vrrp_script` with `interval 2`, `fall 2`, `rise 10`,
  `keepalived.conf.j2:1-8`) [CODE]. Changed in 2024.1: with no script under `/checks`, `check_alive.sh` no longer
  tests the HAProxy socket and reaches its end without a failing check (kolla `docker/keepalived/check_alive.sh:9-33`).
  With `keepalived_track_script_enabled: false` there is no `vrrp_script` at all
  (`roles/loadbalancer/defaults/main.yml:187`, `keepalived.conf.j2:1-8, :45-49`). Whether an HAProxy restart puts the
  node in FAULT, and for how long, is [NOT AVAILABLE: keepalived semantics].
- **ProxySQL**, still off by default [CODE]: `proxysql-config` is unchanged; `loadbalancer-config` skips the HAProxy
  frontend of `mariadb` when ProxySQL is on (`roles/loadbalancer-config/defaults/main.yml:2`); the ProxySQL backends now
  use `mariadb_port` (`roles/loadbalancer/templates/proxysql/proxysql.yaml.j2:33`), which defaults to `database_port`
  (`group_vars/all.yml:467`). An haproxy change also stops and starts proxysql on the backup hosts, not on the VIP
  holder (`roles/loadbalancer/handlers/main.yml:83-87, :140-145, :195-208`).

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py loadbalancer -->

| Item | Value |
|---|---|
| Play | site.yml:105 |
| Tags | haproxy, keepalived, loadbalancer; each of the 39 per-service `include_role … tasks_from: loadbalancer` tasks in this play also carries its service tag |
| Play host patterns | loadbalancer |
| Node types in play (example inventory) | network |
| Node types running its containers | network |
| Containers | `haproxy`, `proxysql`, `keepalived`, `haproxy_ssh` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config-host → config → check-containers |
| Task files | check-containers.yml, check.yml, config-host.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `haproxy-ssh/haproxy-ssh.json.j2`, `haproxy-ssh/sshd_config.j2`, `haproxy/haproxy.json.j2`, `haproxy/haproxy_external_frontend.cfg.j2`, `haproxy/haproxy_main.cfg.j2`, `haproxy/haproxy_run.sh.j2`, `keepalived/check_alive_haproxy.sh.j2`, `keepalived/check_alive_proxysql.sh.j2`, `keepalived/keepalived.conf.j2`, `keepalived/keepalived.json.j2`, `proxysql/proxysql.json.j2`, `proxysql/proxysql.yaml.j2`, `proxysql/proxysql_run.sh.j2` |
| Handlers (definition order) | Check IP addresses on the API interface; Group HA nodes by status; Stop backup keepalived container; Stop backup haproxy container; Stop backup proxysql container; Start backup haproxy container; Wait for backup haproxy to start; Start backup proxysql container; Wait for backup proxysql to start; Start backup keepalived container; Stop master haproxy container; Stop master proxysql container; Stop master keepalived container; Start master haproxy container; Wait for master haproxy to start; Start master proxysql container; Wait for master proxysql to start; Start master keepalived container; Wait for haproxy to listen on VIP; Wait for proxysql to listen on VIP; Restart haproxy-ssh container |
| Key variables | `enable_haproxy`, `enable_keepalived`, `kolla_internal_vip_address`, `kolla_external_vip_address`, `keepalived_virtual_router_id`, `kolla_enable_tls_*` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — a service tag renders the service's frontend
  and restarts HAProxy if it changed
- [Tags §2.2](../risk/tags.md#22-handlers-ignore-tags-code) — handlers ignore tags, which is why `-t keystone` can
  restart HAProxy
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — every
  internal and public endpoint and the DB address resolve to the VIPs
- [MariaDB/Galera](mariadb.md) — HAProxy sends DB traffic to one active backend
- [Deployment execution flow](../concepts/deployment-execution-flow.md) — where the loadbalancer and letsencrypt plays
  run, and why the loadbalancer role flushes its handlers only at the end of its play
- [Technical findings](../reference/findings.md) — [F16](../reference/findings.md#f16), the first 2024.1 check of a
  container whose unit 2023.1 wrote
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the checks before every production run
- [Components](index.md) — the other component pages
