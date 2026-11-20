---
title: Change control-plane membership
description: What adding, removing or replacing a controller changes through the rabbitmq and memcached groups, which containers restart, and why to schedule and batch it.
tags: [rabbitmq, memcached, mariadb, nova, neutron, haproxy, reconfigure, inventory, loop-notify]
impact: [restarts-on-drift, maintenance-window]
---

# Change control-plane membership

What adding, removing or replacing a controller triggers on the rest of the platform through the `rabbitmq` and
`memcached` groups, which are children of `control` in the default inventory. The page gives no command line and no
verification steps: it states what restarts, with the risks R3 and R4, lists what restarts when `control04` is added and
`-t nova,neutron reconfigure` is run, and says that Galera and RabbitMQ membership changes need their own procedures
(Ussuri has no automated member removal).

The scenario section is written for the [assumed deployment](index.md#assumed-deployment).

> [!WARNING]
> [R3](../risk/risk-register.md#r3) and [R4](../risk/risk-register.md#r4): in the default inventory a controller change
> restarts all nova and neutron containers on all computes, and most control-plane services — see
> [§1.1](#11-remove-or-replace-a-controller).

## 1. Commands

### 1.1 Remove or replace a controller

- Changing the `rabbitmq` membership changes the transport URL everywhere, and changing `memcached` changes the memcache
  server lists. In the default inventory both are children of `control`, so a controller change does both. That restarts
  all nova and neutron containers on all computes, and most control-plane services ([R3](../risk/risk-register.md#r3)
  and [R4](../risk/risk-register.md#r4) in [Risk register](../risk/risk-register.md)). A `memcached`-only change does
  not touch nova-compute (the compute `nova.conf` has no memcache list) but still restarts the neutron agents on
  computes (`neutron.conf`).
- Galera and RabbitMQ membership changes need their own procedures. Ussuri has no automated member removal (fact sheets
  [A](../reference/factsheets/a-infra-lb-ovn.md), [B](../reference/factsheets/b-mariadb-rabbitmq-keystone.md)).

## 2. Change control-plane membership (add or remove a controller)

[CODE] Adding `control04` to `control` (and therefore to `rabbitmq`, `memcached`, `mariadb`, …) and running
`-t nova,neutron reconfigure`, read from the templates:

- **Restarted on every compute:** nova_compute, nova_libvirt, nova_ssh, neutron_openvswitch_agent.
- **Restarted on every controller:** all nova and neutron containers.
- **Restarted on both network nodes:** all neutron agents; haproxy (backend lists changed).
- **Why:** `rpc_transport_url` lists every RabbitMQ host (`group_vars/all.yml:206`,
  `roles/nova-cell/defaults/main.yml:174`), and the haproxy backends list every API host
  (`roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:93`). Loop-notify ([Tags
  §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)) restarts the sibling
  containers.
- **Plus:** RabbitMQ and Galera cluster joins, which need their own plays (`-t rabbitmq`, `-t mariadb`). Galera
  membership changes restart all DB nodes (`galera.cnf` lists all nodes, [fact sheet B §1.4][sheet-b-14] and
  [§1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities)
  item 11).

**Takeaway:** controller membership changes are fleet-wide restart events for every messaging consumer. Schedule them
as such, and batch the compute side.

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R3](../risk/risk-register.md#r3) (changing
  RabbitMQ group membership) and [R4](../risk/risk-register.md#r4) (changing memcached membership)
- [RabbitMQ](../components/rabbitmq.md) — service card and where to look
- [Memcached](../components/memcached.md) — service card and where to look
- [MariaDB/Galera](../components/mariadb.md) — service card and where to look; Galera membership changes restart all
  DB nodes
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Write config first, apply in controlled batches](controlled-batches.md) — how to apply in batches (`genconfig`,
  then `deploy-containers --limit`; `ANSIBLE_SERIAL`); its examples use the nova tags
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) — one extra controller changes
  the transport URL in every messaging service everywhere

[sheet-b-14]: ../reference/factsheets/b-mariadb-rabbitmq-keystone.md#14-config-files-generated-ansiblerolesmariadbtasksconfigyml
