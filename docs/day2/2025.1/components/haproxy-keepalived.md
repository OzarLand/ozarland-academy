---
title: HAProxy + Keepalived
description: "Where the 2025.1 study covers HAProxy, keepalived, ProxySQL and haproxy_ssh: what the tags run, the restart order, the VIP unknowns, known bugs."
tags: [haproxy, keepalived, loadbalancer, proxysql, letsencrypt, tags, handlers, serial, inventory, risk, dependencies, bugs, unknowns]
---

# HAProxy + Keepalived

This page is the starting point for HAProxy and keepalived in 2025.1. The `loadbalancer` role is applied by the "Apply
role loadbalancer" play to the `loadbalancer` group (the network nodes of the example inventory,
`inventory/multinode:84-85`), restricted to `enable_loadbalancer_True`, with play tags `haproxy`, `keepalived` and
`loadbalancer` and a `max_fail_percentage` (`site.yml:105-120`). It runs the containers `haproxy`, `keepalived`
(`enable_keepalived`, default: follows `enable_haproxy`), `proxysql` (`enable_proxysql`, **default `yes` in 2025.1**)
and `haproxy_ssh` (only with `enable_letsencrypt`, default `no`) (`roles/loadbalancer/defaults/main.yml:2-36`,
`group_vars/all.yml:836-837, :958, :913`). The same play holds 38 per-service `include_role … tasks_from:
loadbalancer` tasks (39 in 2024.1: swift is gone), run only for `deploy`, `reconfigure`, `upgrade` and `config`
(`site.yml:121-327`); each of them also carries its service tag. A service's `loadbalancer.yml` imports
`loadbalancer-config`, which renders the HAProxy frontend through `haproxy-config` and, with `enable_proxysql`, the
ProxySQL users and rules through `proxysql-config` (`roles/loadbalancer-config/tasks/main.yml:2-8`). The `hacluster`
role is a separate play and is not covered here; nor is the `letsencrypt` play (`site.yml:329-341`), except where it
touches HAProxy. The lists below say where the study covers how to operate it, its impact, its dependencies and the
evidence, what to check around a run and what stays open; the service card follows them.

> [!NOTE]
> **Changed in 2025.1** [CODE]
>
> - **Who restarts HAProxy:** no config task of `loadbalancer` or `haproxy-config` notifies a handler any more; the
>   role's `check-containers.yml` imports `service-check-containers` (`roles/loadbalancer/tasks/check-containers.yml:2-3`),
>   which notifies `Restart <name> container` only for the containers `compare_container` reports changed. That check
>   runs once, at the end of the loadbalancer play (`site.yml:319-324`), which carries only the play tags. So
>   **`-t <service>` rewrites the service's frontend file but no longer restarts HAProxy**; the new frontend applies at
>   the next run of the play with `-t haproxy`, `-t loadbalancer` or no tag ([F18](../reference/findings.md#f18)).
> - **ProxySQL on by default:** `enable_proxysql: "yes"` (`group_vars/all.yml:958`), so the `mariadb` HAProxy frontend
>   is skipped and database traffic goes through ProxySQL on the internal VIP
>   (`roles/loadbalancer-config/defaults/main.yml:2`). New ProxySQL tuning defaults, and on single-node database shards
>   a 10-second `shun_on_failures` delay (`roles/loadbalancer/defaults/main.yml:203-237`). The upgrade from a 2024.1
>   cloud that ran without ProxySQL is covered on [MariaDB/Galera](mariadb.md).
> - **TLS 1.3 only by default:** `kolla_haproxy_ssl_settings: "modern"` (`group_vars/all.yml:441`) renders
>   `no-tlsv12` on the bind and server sides (`group_vars/all.yml:443, :457-461`,
>   `roles/loadbalancer/templates/haproxy/haproxy_main.cfg.j2:16-18`). `intermediate` or `legacy` restore older
>   settings. Which clients break is [NOT AVAILABLE] from the code.
> - **Layer-7 health checks:** the `haproxy` dicts of 28 roles now add `option httpchk` to their HTTP backends (e.g.
>   `roles/keystone/defaults/main.yml:21`; one role in 2024.1).
> - **`haproxy_run.sh` execs HAProxy** with `-f /etc/haproxy/services.d/` instead of piping the file list through
>   `xargs` (`roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:38`), so HAProxy replaces the shell and receives
>   the container's stop signal ([Kolla images §2.6](../concepts/kolla-images.md#26-signals-and-pid-1)).
> - **Keepalived ProxySQL check:** `check_alive_proxysql.sh` now runs `mariadb … -e "SELECT 1"` on the ProxySQL admin
>   socket with the admin password (`roles/loadbalancer/templates/keepalived/check_alive_proxysql.sh.j2:6-12`); the
>   keepalived image gains the MariaDB client (kolla `docker/keepalived/Dockerfile.j2:10-20`). The check-script tasks
>   no longer notify keepalived (`roles/loadbalancer/tasks/config.yml:74-105`).
> - **Certificates:** the PEM copies moved to `copy-certs.yml`, which runs when `loadbalancer_copy_certs` is true and
>   follows `letsencrypt_managed_certs` (`roles/loadbalancer/tasks/config.yml:180-182`,
>   `roles/loadbalancer/tasks/copy-certs.yml:2-32`, `roles/loadbalancer/defaults/main.yml:203`,
>   `group_vars/all.yml:518`). The certificate rotation for Let's Encrypt is unchanged in principle, under a new
>   script name, `update-loadbalancer-cert` (kolla `docker/letsencrypt/letsencrypt-lego/sync-and-update-certificate.sh:84, :89`,
>   `docker/haproxy/haproxy-ssh/update-loadbalancer-cert.sh:23, :50`).
> - **Single external frontend:** the role default was renamed to `haproxy_single_external_frontend_public_port`
>   (`roles/loadbalancer/defaults/main.yml:195`), the name `group_vars/all.yml:1068` sets, so the 2024.1 port mismatch
>   between the frontend and the endpoints is gone.
> - **Handlers:** the same staged sequence; the two "wait for backup" handlers are now `any_errors_fatal`
>   (`roles/loadbalancer/handlers/main.yml:115-119`, `:150-154`), so a backup HAProxy or ProxySQL that does not come
>   back stops the play on every host. The loadbalancer handlers keep their `kolla_action != "config"` guards.
> - **Since 2024.1, unchanged:** the `haproxy_ssh` container for Let's Encrypt, HAProxy's own Prometheus metrics on
>   port 9101, `haproxy_threads`, HTTP/2 on TLS binds.

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
  (the `loadbalancer` role in 2025.1); `haproxy-config`: [fact sheet A
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
  the restart handlers run only when the final check finds a container changed (`site.yml:319-324`,
  `roles/service-check-containers/tasks/main.yml:34-41`) [CODE]; with a change, prefer a window. Prerequisites: facts of every backend host; certificates if TLS is on and Let's Encrypt does not manage them (`roles/loadbalancer/tasks/precheck.yml:58-94`).
- **First 2025.1 run on a 2024.1 cloud:** expect the restart handlers. `compare_container` reports a unit file written
  by 2024.1 ([F16](../reference/findings.md#f16)), and the rendered files change (TLS settings, `haproxy_run.sh`,
  the ProxySQL check script, layer-7 checks in most frontends, CA entries in `config.json`); the shared check then
  notifies `Restart <name> container` for each changed container, which starts the staged sequence below for
  haproxy, proxysql and keepalived [CODE]. With ProxySQL newly enabled, the `proxysql` container is created on that
  run.
- [R8](../risk/risk-register.md#r8), the restart order, still staged in 2025.1. Handlers run in their definition order,
  and each `listen`s to `Restart haproxy container`, `Restart proxysql container` or `Restart keepalived container`
  [CODE]:
  1. on every host of the batch, read the API interface addresses and group the hosts by whether they hold
     `kolla_internal_vip_address` (`roles/loadbalancer/handlers/main.yml:9-34`);
  2. on the backup hosts: stop keepalived (keepalived change only, `:36-49`), stop haproxy (haproxy or keepalived
     change, `:54-68`), stop proxysql (any of the three, `:70-88`), start haproxy and wait for `haproxy_monitor_port`
     (haproxy or keepalived change, `:90-118`), start proxysql when enabled and wait for its admin port (any of the
     three, `:121-153`), start keepalived (keepalived change only, `:156-177`);
  3. on the VIP holder: stop haproxy (haproxy or keepalived change, `:181-195`), stop proxysql (proxysql or keepalived
     change, `:197-210`), stop keepalived (keepalived change only, `:212-224`), then start them again in the same
     order, waiting for each port (`:226-307`);
  4. after a keepalived start, wait for haproxy and, when enabled, proxysql to answer on the internal VIP
     (`:309-331`);
  5. last: `Restart haproxy-ssh container`, on every host at once, with no backup/VIP split (`:333-347`), notified
     by the shared check when the haproxy-ssh container changed.

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
  single external frontend, of `/etc/kolla/haproxy/external-frontend-map`) against the previous version. **Changed in
  2025.1:** the service's frontend file and its map block notify nothing (`roles/haproxy-config/tasks/main.yml:2-21,
  :23-49`), so after a service-tagged run HAProxy still serves the old frontend; apply it with `-t haproxy` and check
  with `docker ps --filter name=haproxy` that HAProxy restarted ([F18](../reference/findings.md#f18)) [CODE].
- **Upgrade from 2023.1 (still in the 2025.1 role):** `upgrade` stops and removes `prometheus_haproxy_exporter` before
  the deploy tasks
  (`roles/loadbalancer/tasks/upgrade.yml:4-21`); `deploy` and `reconfigure` do not
  (`roles/loadbalancer/tasks/deploy.yml:2-6`, `reconfigure.yml:2`). The old exporter listened on the same port 9101
  that HAProxy's own `listen metrics` now binds
  (`group_vars/all.yml:670`, `roles/loadbalancer/templates/haproxy/haproxy_main.cfg.j2:46-51`) [CODE]; what happens if
  a `deploy` runs while the old container still holds the port is [NOT AVAILABLE].
- **Overrides:** an override of the old role default `haproxy_external_single_frontend_public_port` is now ignored;
  set `haproxy_single_external_frontend_public_port` instead (`roles/loadbalancer/defaults/main.yml:195`) [CODE]. To
  keep TLS 1.2 clients working, set `kolla_haproxy_ssl_settings: intermediate` before the first 2025.1 run
  (`group_vars/all.yml:441-443`).

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `haproxy`, read against 2025.1:
  restart instead of reload still holds (the image's `kolla_ensure_haproxy_latest_config`, kolla
  `docker/haproxy/haproxy/Dockerfile.j2:17`, is never called from `ansible/`, [Kolla images
  §5](../concepts/kolla-images.md#5-per-image-start-behaviour)); only Let's Encrypt certificates are reloaded without a restart, through the admin socket (above). Stale `services.d` files are still never removed (`haproxy-config` only templates,
  `roles/haproxy-config/tasks/main.yml:2-21`; the only removal is `mariadb.cfg` when ProxySQL is enabled,
  `roles/loadbalancer/tasks/config.yml:63-72`, which now applies by default); keepalived priority still comes from inventory order; `upgrade` is
  still the `deploy` task flow, now preceded by the exporter removal (`roles/loadbalancer/tasks/upgrade.yml:21`).
  Status: [CODE].
- **Stale files, since 2024.1:** turning `haproxy_single_external_frontend` off leaves
  `services.d/external-frontend.cfg` in place (it is only templated when the option is on, `roles/loadbalancer/tasks/config.yml:143-153`), and HAProxy loads every
  file of `services.d` (`roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:38`); a disabled service's block also
  stays in `external-frontend-map` (`blockinfile` runs only for enabled services,
  `roles/haproxy-config/tasks/main.yml:43-47`).
  Status: [CODE].
- **Single external frontend, one point to check before enabling it** [CODE]: the map is copied into the container
  when external TLS is on and Let's Encrypt does not manage the external certificate, or when Let's Encrypt is off
  (`roles/loadbalancer/templates/haproxy/haproxy.json.j2:22-28`; it is `optional` only when the option is off), while
  the frontend always reads `/etc/haproxy/external-frontend-map`
  (`roles/loadbalancer/templates/haproxy/haproxy_external_frontend.cfg.j2:11`). The 2024.1 port mismatch is fixed:
  frontend and endpoints both use `haproxy_single_external_frontend_public_port` (`haproxy_external_frontend.cfg.j2:10`,
  `group_vars/all.yml:1068`).
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), second row `site.yml`: the placement
  loadbalancer include still lacks `when: enable_placement` (`site.yml:248-251`), as in 2024.1. Status: [CODE].
- [Q5](../troubleshooting/open-questions.md#q5): "HAProxy restart: VIP behaviour". Status: [NOT AVAILABLE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "HAProxy restart": the sources do not establish whether keepalived drops or moves the VIP, and for how long; whether
  the node goes to FAULT; whether established connections are cut; whether nova and neutron get DB errors and instance
  metadata requests fail meanwhile; how HAProxy treats backends that are not up yet on a first deploy.
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored": does not hold
  since 2024.1; containers stop through their systemd unit with `docker_graceful_timeout`
  ([R24](../risk/risk-register.md#r24)) [CODE]. **Changed in 2025.1:** `haproxy_run.sh` now `exec`s HAProxy
  (`roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:38`), so HAProxy gets the stop signal directly; what it
  does with in-flight connections in its `-W` master-worker mode is [NOT AVAILABLE: HAProxy semantics].
- [fact sheet A §1.8](../reference/factsheets/a-infra-lb-ovn.md#18-operationally-notable-behaviour), "Operationally notable behaviour", read against 2025.1: any change means a full restart of haproxy, never a reload, staged backups
  first and VIP holder last (R8 above); whether a haproxy restart causes VIP failover or a VIP outage is [NOT
  AVAILABLE]; keepalived priority depends on inventory order; stale frontends are never removed; `-t haproxy` does not
  run `common` (`common` is its own play, `site.yml:88-103`); non-local bind is still set by the role, now through the
  `sysctl` role with the same values and the same `KOLLA_UNSET`/`KOLLA_SKIP` handling
  (`roles/loadbalancer/tasks/config-host.yml:8-18`, `roles/sysctl/tasks/main.yml:7-20`, with `set_sysctl`); VRRP router
  id collisions: `keepalived_virtual_router_id` still defaults to `51` (`group_vars/all.yml:247`);
  `keepalived_traffic_mode: unicast` is still available (default `multicast`,
  `roles/loadbalancer/defaults/main.yml:62`, `keepalived.conf.j2:17-29`) [CODE].
- [fact sheet A §2.4](../reference/factsheets/a-infra-lb-ovn.md#24-notable), "Notable" for the `haproxy-config` role:
  stale files are not removed; the file of a service whose `enabled` is false is left as it was; file name; facts are
  required; precedence. Since 2024.1: the map block per service (above).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 15: the VIP follows the HAProxy stats
  socket, and the ProxySQL admin socket when ProxySQL is enabled (one `check_alive_<service>.sh` per enabled service,
  `roles/loadbalancer/tasks/config.yml:93-111`; `vrrp_script` with `interval 2`, `fall 2`, `rise 10`,
  `keepalived.conf.j2:1-8`) [CODE]. Since 2024.1: with no script under `/checks`, `check_alive.sh` does not test the HAProxy socket and reaches its end
  without a failing check (kolla `docker/keepalived/check_alive.sh:9-33`). **Changed in 2025.1:** the ProxySQL check
  logs in with the admin password instead of a socket `show info`
  (`roles/loadbalancer/templates/keepalived/check_alive_proxysql.sh.j2:6-12`), so a wrong `proxysql_admin_password`
  makes the check fail and can move the VIP; and a `keepalived.conf` or check-script change no longer restarts
  keepalived by itself unless the check step finds the container changed.
  With `keepalived_track_script_enabled: false` there is no `vrrp_script` at all
  (`roles/loadbalancer/defaults/main.yml:190`, `keepalived.conf.j2:1-8, :45-49`). Whether an HAProxy restart puts the
  node in FAULT, and for how long, is [NOT AVAILABLE: keepalived semantics].
- **ProxySQL**, **on by default in 2025.1** [CODE]: `loadbalancer-config` skips the HAProxy
  frontend of `mariadb` when ProxySQL is on (`roles/loadbalancer-config/defaults/main.yml:2`); the ProxySQL backends now
  use `mariadb_port` (`roles/loadbalancer/templates/proxysql/proxysql.yaml.j2:87`), which defaults to `database_port`
  (`group_vars/all.yml:538`). An haproxy change also stops and starts proxysql on the backup hosts, not on the VIP
  holder (`roles/loadbalancer/handlers/main.yml:83-87, :141-146, :197-210`).

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py loadbalancer -->

| Item | Value |
|---|---|
| Play | site.yml:105 |
| Tags | haproxy, keepalived, loadbalancer; each of the 38 per-service `include_role … tasks_from: loadbalancer` tasks in this play also carries its service tag |
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

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — a service tag renders the service's frontend;
  in 2025.1 HAProxy picks it up only at the next `-t haproxy` or untagged run
- [Tags §2.2](../risk/tags.md#22-handlers-ignore-tags-code) — handlers ignore tags; in 2025.1 nothing under
  `-t keystone` notifies the HAProxy handlers any more
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — every
  internal and public endpoint and the DB address resolve to the VIPs
- [MariaDB/Galera](mariadb.md) — HAProxy sends DB traffic to one active backend
- [Deployment execution flow](../concepts/deployment-execution-flow.md) — where the loadbalancer and letsencrypt plays
  run, and why the loadbalancer role flushes its handlers only at the end of its play
- [Technical findings](../reference/findings.md) — [F16](../reference/findings.md#f16), the first 2025.1 check of a
  container whose unit 2024.1 wrote; [F18](../reference/findings.md#f18), `-t <service>` no longer restarts HAProxy
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the checks before every production run
- [Components](index.md) — the other component pages
