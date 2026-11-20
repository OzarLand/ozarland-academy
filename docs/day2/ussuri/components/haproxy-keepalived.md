---
title: HAProxy + Keepalived
description: Where the study covers HAProxy and keepalived (role haproxy), from what the tag and the service tags run to the restart risk, the VIP unknowns and known bugs.
tags: [haproxy, keepalived, tags, handlers, serial, inventory, risk, dependencies, bugs, unknowns]
---

# HAProxy + Keepalived

This page is the starting point for HAProxy and keepalived, the `haproxy` role: the containers `haproxy` and
`keepalived`, on the network nodes of the example inventory, selected by the tag `haproxy`. The same play holds the 49
per-service `loadbalancer` includes, and each of them also carries its service tag. The lists below say where the study
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

- **Fact sheet:** [fact sheet A §1](../reference/factsheets/a-infra-lb-ovn.md#1-haproxy-role-haproxy--keepalived);
  `haproxy-config`: [fact sheet A §2](../reference/factsheets/a-infra-lb-ovn.md#2-haproxy-config-role)
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
  batch with `ANSIBLE_SERIAL=1 … reconfigure`. Prerequisites: facts of every backend host; certificates if TLS is on.
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `ANSIBLE_SERIAL=1` for haproxy changes;
  `--skip-tags haproxy` when you don't intend to change frontends.
- [R22](../risk/risk-register.md#r22), inventory reordering (haproxy, mariadb, glance, nova-conductor, keystone groups):
  keepalived priorities change. Precautions: treat inventory order as configuration; never reorder casually.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the
  previous version; after, `docker ps --filter name=haproxy` shows whether HAProxy restarted.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `haproxy`: restart instead of
  reload; stale `services.d` files never removed; keepalived priority from inventory order; upgrade "Stopping all slave
  keepalived" without an `enable_keepalived` guard and with raw interface names. Status: [CODE]; effect of the upgrade
  bugs [NOT AVAILABLE].
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), second row `site.yml`: placement
  haproxy include lacks `when: enable_placement`. Status: [CODE].
- [Q5](../troubleshooting/open-questions.md#q5): "HAProxy restart: VIP behaviour". Status: [NOT AVAILABLE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "HAProxy restart": the sources do not establish whether keepalived drops or moves the VIP, and for how long; whether
  the node goes to FAULT; whether established connections are cut; whether nova and neutron get DB errors and instance
  metadata requests fail meanwhile; how HAProxy treats backends that are not up yet on a first deploy; the effect of the
  haproxy upgrade bugs.
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored" [CODE]:
  [NOT AVAILABLE] whether services started by a shell wrapper that does not `exec` them (e.g. `neutron-l3-agent`,
  `haproxy`) receive SIGTERM at all.
- [fact sheet A §1.8](../reference/factsheets/a-infra-lb-ovn.md#18-operationally-notable-behaviour), "Operationally
  notable behaviour", items (A) to (I): any change means a full restart of haproxy on all haproxy nodes at once, never a
  reload; whether a haproxy restart causes VIP failover or a VIP outage is NOT AVAILABLE; keepalived priority depends on
  inventory order; stale frontends are never removed; `-t haproxy` also runs `common` on haproxy hosts; upgrade
  "Stopping all slave keepalived containers"; things that run on every deploy, reconfigure and upgrade; non-local bind
  is needed; VRRP router id collisions.
- [fact sheet A §2.4](../reference/factsheets/a-infra-lb-ovn.md#24-notable), "Notable" for the `haproxy-config` role:
  stale files are not removed; the file of a service whose `enabled` is false is left as it was; file name; facts are
  required; precedence.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 15: the VIP follows the HAProxy stats socket
  only [CODE]; whether an HAProxy restart puts the node in FAULT, and for how long, is
  [NOT AVAILABLE: keepalived semantics].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py haproxy -->

| Item | Value |
|---|---|
| Play | site.yml:126 |
| Tags | haproxy; each of the 49 per-service `include_role … tasks_from: loadbalancer` tasks in this play also carries its service tag |
| Play host patterns | haproxy |
| Node types in play (example inventory) | network |
| Node types running its containers | network |
| Containers | `haproxy`, `keepalived` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config-host → config → check-containers |
| Task files | check-containers.yml, check.yml, config-host.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `haproxy.json.j2`, `haproxy_main.cfg.j2`, `haproxy_run.sh.j2`, `keepalived.conf.j2`, `keepalived.json.j2` |
| Handlers (definition order) | Restart haproxy container; Restart keepalived container; Waiting for haproxy to start; Waiting for virtual IP to appear |
| Key variables | `enable_haproxy`, `enable_keepalived`, `kolla_internal_vip_address`, `kolla_external_vip_address`, `keepalived_virtual_router_id`, `kolla_enable_tls_*` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — a service tag renders the service's frontend
  and restarts HAProxy if it changed
- [Tags §2.2](../risk/tags.md#22-handlers-ignore-tags-code) — handlers ignore tags, which is why `-t keystone` can
  restart HAProxy
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — every
  internal, admin and public endpoint and the DB address resolve to the VIPs
- [MariaDB/Galera](mariadb.md) — HAProxy sends DB traffic to one active backend
- [Chrony](chrony.md) — in the example inventory `chrony-server` is the haproxy group, and the VIP is the internal time
  source
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
