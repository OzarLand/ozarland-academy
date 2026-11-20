---
title: HAProxy + Keepalived
description: "Where the study covers HAProxy, keepalived and ProxySQL (role loadbalancer): what the tags run, the restart risk, the VIP unknowns and known bugs."
tags: [haproxy, keepalived, loadbalancer, proxysql, tags, handlers, serial, inventory, risk, dependencies, bugs, unknowns]
---

# HAProxy + Keepalived

This page is the starting point for HAProxy and keepalived. **Changed in 2023.1:** the Ussuri `haproxy` role is the
`loadbalancer` role, applied by the "Apply role loadbalancer" play to the `loadbalancer` group (the network nodes of
the example inventory, `inventory/multinode:86-87`) with play tags `haproxy`, `keepalived` and `loadbalancer`
(`site.yml:99-108`). It runs the containers `haproxy`, `keepalived` (`enable_keepalived`, default: follows
`enable_haproxy`) and `proxysql` (`enable_proxysql`, default `no`) (`roles/loadbalancer/defaults/main.yml:2-24`,
`group_vars/all.yml:622-624, :742`). The same play holds the 44 per-service `include_role … tasks_from: loadbalancer`
tasks, run only for `deploy`, `reconfigure`, `upgrade` and `config` (`site.yml:110-341`); each of them also carries its
service tag. A service's `loadbalancer.yml` imports `loadbalancer-config`, which renders the HAProxy frontend through
`haproxy-config` and, with `enable_proxysql`, the ProxySQL users and rules through `proxysql-config`
(`roles/loadbalancer-config/tasks/main.yml:2-8`). The `hacluster` role is a separate play (`site.yml:620`) and is not
covered here. The lists below say where the study
covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open;
the service card follows them.

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
  haproxy play under a service tag: [Tags
  §2.3](../risk/tags.md#23-include_role--tags-always-inside-the-haproxy-play-code)
- **Risks:** [R8](../risk/risk-register.md#r8)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)

### Evidence

- **Fact sheet:** [fact sheet A §1](../reference/factsheets/a-infra-lb-ovn.md#1-haproxy-role-haproxy--keepalived)
  (the `loadbalancer` role in 2023.1); `haproxy-config`: [fact sheet A
  §2](../reference/factsheets/a-infra-lb-ovn.md#2-haproxy-config-role)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `haproxy`,
  `keepalived`)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 5 (health gates): before the run, check
  HAProxy backends all UP. Repeat after each batch.
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 7 (scope): add `--skip-tags haproxy` when
  the frontends are not meant to change.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `haproxy`:
  safe on its own "yes if nothing reports a change, since the restart handlers then never run [CODE]"; with a change,
  prefer a window. Prerequisites: facts of every backend host; certificates if TLS is on.
- [R8](../risk/risk-register.md#r8), still applies with a staged restart: the handlers find the host that holds
  `kolla_internal_vip_address`, stop and start `haproxy` on every backup host at once and wait for
  `haproxy_monitor_port`, then stop and start it on the VIP holder (`roles/loadbalancer/handlers/main.yml:9-34, :54-118,
  :179-253`) [CODE]. A `keepalived` change also stops and starts `haproxy` (and `proxysql`) on each host, backups first,
  and stops the master's keepalived last, so the VIP moves (`:36-52, :154-177, :210-222, :284-300`) [CODE]. Precautions:
  `ANSIBLE_SERIAL=1` for haproxy changes; `--skip-tags haproxy` when you don't intend to change frontends.
- [R22](../risk/risk-register.md#r22), inventory reordering (loadbalancer, mariadb, glance, nova-conductor, keystone
  groups): keepalived priorities change (priority = position in `loadbalancer` + 1,
  `roles/loadbalancer/templates/keepalived/keepalived.conf.j2:15`). Precautions: treat inventory order as configuration;
  never reorder casually.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the
  previous version; after, `docker ps --filter name=haproxy` shows whether HAProxy restarted.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `haproxy`, read against 2023.1:
  restart instead of reload still holds (the image's `kolla_ensure_haproxy_latest_config` is never called, [Kolla images
  §5](../concepts/kolla-images.md#5-per-image-start-behaviour)); stale `services.d` files are still never removed
  (`haproxy-config` only templates, `roles/haproxy-config/tasks/main.yml:2-23`; the only removal is `mariadb.cfg` when
  ProxySQL is enabled, `roles/loadbalancer/tasks/config.yml:60`); keepalived priority still comes from inventory order;
  the Ussuri upgrade bug is gone: `roles/loadbalancer/tasks/upgrade.yml:2` imports `deploy.yml`, with no "Stopping all
  slave keepalived" task. Status: [CODE].
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), second row `site.yml`: the placement
  loadbalancer include still lacks `when: enable_placement` (`site.yml:243-246`). Status: [CODE].
- [Q5](../troubleshooting/open-questions.md#q5): "HAProxy restart: VIP behaviour". Status: [NOT AVAILABLE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "HAProxy restart": the sources do not establish whether keepalived drops or moves the VIP, and for how long; whether
  the node goes to FAULT; whether established connections are cut; whether nova and neutron get DB errors and instance
  metadata requests fail meanwhile; how HAProxy treats backends that are not up yet on a first deploy. The Ussuri
  haproxy upgrade bugs no longer exist in 2023.1 (above).
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored": no longer
  holds as written in 2023.1; containers stop through their systemd unit with `docker_graceful_timeout` (60 s)
  ([R24](../risk/risk-register.md#r24))
  [CODE]. Still [NOT AVAILABLE]: whether services started by a shell wrapper that does not `exec` them (e.g.
  `neutron-l3-agent`, `haproxy`: `haproxy_run.sh` ends in `xargs /usr/sbin/haproxy`,
  `roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:7-9`) receive SIGTERM at all.
- [fact sheet A §1.8](../reference/factsheets/a-infra-lb-ovn.md#18-operationally-notable-behaviour), "Operationally
  notable behaviour", items (A) to (I), read against 2023.1: any change means a full restart of haproxy, never a
  reload, now staged backups first and VIP holder last (R8 above); whether a haproxy restart causes VIP failover or a
  VIP outage is [NOT AVAILABLE]; keepalived priority depends on inventory order; stale frontends are never removed;
  `-t haproxy` no longer runs `common` (`common` is its own play, `site.yml:86-97`); the upgrade "Stopping all slave
  keepalived containers" task is gone, and `upgrade` is the same task flow as `deploy`/`reconfigure`
  (`roles/loadbalancer/tasks/upgrade.yml:2`, `reconfigure.yml:2`); non-local bind is still set by the role
  (`net.ipv4/ipv6.ip_nonlocal_bind`, `roles/loadbalancer/tasks/config-host.yml:8-26`, with `set_sysctl`); VRRP router id
  collisions: `keepalived_virtual_router_id` still defaults to `51` (`group_vars/all.yml:189`). New in 2023.1:
  `keepalived_traffic_mode: unicast` (default `multicast`, `roles/loadbalancer/defaults/main.yml:50`,
  `keepalived.conf.j2:17-29`) [CODE].
- [fact sheet A §2.4](../reference/factsheets/a-infra-lb-ovn.md#24-notable), "Notable" for the `haproxy-config` role:
  stale files are not removed; the file of a service whose `enabled` is false is left as it was; file name; facts are
  required; precedence.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 15: the VIP follows the HAProxy stats
  socket, and the ProxySQL admin socket when ProxySQL is enabled (one `check_alive_<service>.sh` per enabled service,
  `roles/loadbalancer/tasks/config.yml:74-105`) [CODE]; whether an HAProxy restart puts the node in FAULT, and for how
  long, is
  [NOT AVAILABLE: keepalived semantics].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py loadbalancer -->

| Item | Value |
|---|---|
| Play | site.yml:99 |
| Tags | haproxy, keepalived, loadbalancer; each of the 44 per-service `include_role … tasks_from: loadbalancer` tasks in this play also carries its service tag |
| Play host patterns | loadbalancer |
| Node types in play (example inventory) | network |
| Node types running its containers | network |
| Containers | `haproxy`, `proxysql`, `keepalived` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config-host → config → check-containers |
| Task files | check-containers.yml, check.yml, config-host.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `haproxy/haproxy.json.j2`, `haproxy/haproxy_main.cfg.j2`, `haproxy/haproxy_run.sh.j2`, `keepalived/check_alive_haproxy.sh.j2`, `keepalived/check_alive_proxysql.sh.j2`, `keepalived/keepalived.conf.j2`, `keepalived/keepalived.json.j2`, `proxysql/proxysql.json.j2`, `proxysql/proxysql.yaml.j2`, `proxysql/proxysql_run.sh.j2` |
| Handlers (definition order) | Check IP addresses on the API interface; Group HA nodes by status; Stop backup keepalived container; Stop backup haproxy container; Stop backup proxysql container; Start backup haproxy container; Wait for backup haproxy to start; Start backup proxysql container; Wait for backup proxysql to start; Start backup keepalived container; Stop master haproxy container; Stop master proxysql container; Stop master keepalived container; Start master haproxy container; Wait for master haproxy to start; Start master proxysql container; Wait for master proxysql to start; Start master keepalived container; Wait for haproxy to listen on VIP; Wait for proxysql to listen on VIP |
| Key variables | `enable_haproxy`, `enable_keepalived`, `kolla_internal_vip_address`, `kolla_external_vip_address`, `keepalived_virtual_router_id`, `kolla_enable_tls_*` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — a service tag renders the service's frontend
  and restarts HAProxy if it changed
- [Tags §2.2](../risk/tags.md#22-handlers-ignore-tags-code) — handlers ignore tags, which is why `-t keystone` can
  restart HAProxy
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — every
  internal, admin and public endpoint and the DB address resolve to the VIPs
- [MariaDB/Galera](mariadb.md) — HAProxy sends DB traffic to one active backend
- [Chrony](chrony.md) — in Ussuri `chrony-server` was the haproxy group and the VIP the internal time source; 2023.1
  has no chrony role
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
