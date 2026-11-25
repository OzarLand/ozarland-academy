---
title: Change control-plane membership
description: What adding, removing or replacing a controller changes in 2025.1 through the rabbitmq, memcached, keystone and etcd groups, what restarts, and why to batch it.
tags: [rabbitmq, memcached, mariadb, keystone, etcd, nova, neutron, haproxy, reconfigure, inventory, loop-notify]
impact: [restarts-on-drift, maintenance-window]
---

# Change control-plane membership

What adding, removing or replacing a controller triggers on the rest of the platform through the `rabbitmq`,
`memcached`, `keystone` and `etcd` groups, which are children of `control` in the default inventory. The page gives no
command line and no verification steps: it states what restarts, with the risks R3 and R4, lists what restarts when
`control04` is added and `-t nova,neutron reconfigure` is run, and says that Galera and RabbitMQ membership changes need
their own procedures (2025.1 still has no automated member removal for them, while the etcd role can remove a deleted
member when asked to).

The scenario section is written for the [assumed deployment](index.md#assumed-deployment).

> [!WARNING]
> [R3](../risk/risk-register.md#r3) and [R4](../risk/risk-register.md#r4): in the default inventory a controller change
> restarts all nova and neutron containers on all computes, and most control-plane services — see
> [§1.1](#11-remove-or-replace-a-controller).

## 1. Commands

### 1.1 Remove or replace a controller

- Changing the `rabbitmq` membership changes the transport URL everywhere, and changing `memcached` changes the memcache
  server lists. In the default inventory both are children of `control` (`inventory/multinode:90-91`,
  `inventory/multinode:116-117`), so a controller change does both. That restarts all nova and neutron containers on all
  computes, and most control-plane services ([R3](../risk/risk-register.md#r3) and [R4](../risk/risk-register.md#r4)
  in [Risk register](../risk/risk-register.md)). Still holds in 2025.1 [CODE]: `rpc_transport_url` and
  `notify_transport_url` loop over the `rabbitmq` group (`group_vars/all.yml:271-274`,
  `group_vars/all.yml:281-284`). A `memcached`-only change does not touch nova-compute (the cell `nova.conf` has no
  memcache setting; no match in `roles/nova-cell/templates/nova.conf.j2`) but still restarts the neutron agents on
  computes, whose `neutron.conf` lists every memcached host (`roles/neutron/templates/neutron.conf.j2:121`).
- Galera and RabbitMQ membership changes need their own procedures. Still holds in 2025.1: the rabbitmq and mariadb
  roles never remove a node from the cluster (no member-removal command in `roles/rabbitmq` or `roles/mariadb`), they
  only render the current group into the configuration (`roles/mariadb/templates/galera.cnf.j2:33`,
  `roles/rabbitmq/templates/rabbitmq.conf.j2:18-21`) [CODE] (fact sheets [A](../reference/factsheets/a-infra-lb-ovn.md),
  [B](../reference/factsheets/b-mariadb-rabbitmq-keystone.md)). With quorum queues now always on in 2025.1
  ([F17](../reference/findings.md#f17)), the rabbitmq role runs no command that adds or removes quorum-queue replicas
  when a node joins or leaves (no such task in `roles/rabbitmq/tasks`) [CODE]; where RabbitMQ then places the replicas
  is [NOT AVAILABLE: RabbitMQ semantics].
- **etcd membership is handled by the role (still holds in 2025.1)** (when `enable_etcd`, default `no`,
  `group_vars/all.yml:878`; `etcd` is a child of `control`, `inventory/multinode:62-63`) [CODE]. A host whose
  `kolla_etcd` volume is new is added with `etcdctl member add`, run on the leader, and started with
  `ETCD_INITIAL_CLUSTER_STATE: "existing"` (`roles/etcd/tasks/bootstrap_services.yml:2-25`,
  `roles/etcd/defaults/main.yml:44-49`). A member that is no longer in the inventory is removed with
  `etcdctl member remove` only when `etcd_remove_deleted_members` is set (default `"no"`,
  `roles/etcd/defaults/main.yml:82`; `roles/etcd/tasks/lookup_cluster.yml:20-26`,
  `roles/etcd/tasks/remove_deleted_members.yml:15-39`). Members are matched by `ansible_facts.hostname`
  (`roles/etcd/tasks/remove_deleted_members.yml:19-27`).
- **Keystone's Fernet schedule depends on the group** [CODE]. Each keystone host's rotation cron is computed from its
  index in `groups['keystone']` and the size of the group (`roles/keystone/tasks/config.yml:163-168`), and
  `fernet-push.sh` lists every other keystone host as an rsync target
  (`roles/keystone/templates/fernet-push.sh.j2:17-22`).
  Adding or removing a keystone host changes both files on every keystone host, which notifies the `keystone_fernet`
  files there (`roles/keystone/tasks/config.yml:180-197`), and the compare of `check-containers.yml` then notifies the
  `keystone_fernet` restart there (changed in 2025.1: no config task notifies any more). A new host gets the existing keys: when a
  `keystone_fernet` container is listed on some host, no new keys are bootstrapped
  (`roles/keystone/tasks/bootstrap_service.yml:53-76`) and the push runs from the first such host
  (`roles/keystone/tasks/distribute_fernet.yml:12-16`).

## 2. Change control-plane membership (add or remove a controller)

[CODE] Adding `control04` to `control` (and therefore to `rabbitmq`, `memcached`, `mariadb`, `keystone`, `etcd`,
…) and running `-t nova,neutron reconfigure`, read from the templates:

- **Restarted on every compute:** nova_compute and neutron_openvswitch_agent. Changed in 2025.1: nova_libvirt and
  nova_ssh no longer restart with them, since only the containers whose files changed are notified and their files
  hold no transport URL (`roles/nova-cell/defaults/main.yml:496-502`, `roles/nova-cell/tasks/config.yml:135`).
- **Restarted on every controller:** the nova containers that read `nova.conf` and neutron_server (`neutron-server` is a child of `control`,
  `inventory/multinode:254-255`).
- **Restarted on both network nodes:** all neutron agents. The haproxy backend files of nova and neutron are rewritten
  (`loadbalancer` is a child of `network`, `inventory/multinode:84-85`; `roles/haproxy-config/tasks/main.yml:2-21`),
  but changed in 2025.1, `-t nova,neutron` no longer restarts HAProxy: the new backends apply at the next run with
  `-t haproxy`, `-t loadbalancer` or no tag ([F18](../reference/findings.md#f18)).
- **Why:** `rpc_transport_url` lists every RabbitMQ host (`group_vars/all.yml:274`,
  `roles/nova-cell/defaults/main.yml:217`; used at `roles/nova-cell/templates/nova.conf.j2:37` and
  `roles/neutron/templates/neutron.conf.j2:56`), and the haproxy backends list every API host
  (`roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:101-110`). Loop-notify is gone in 2025.1 ([Tags
  §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)): each container restarts only if its own files changed. The neutron play targets every compute (`site.yml:669-683`).
- **Plus:** RabbitMQ and Galera cluster joins, which need their own plays (`-t rabbitmq`, `-t mariadb`), in the separate
  playbooks `mariadb.yml` and `rabbitmq.yml` (`site.yml:415`, `site.yml:483`). Galera membership changes restart all DB
  nodes (`galera.cnf` lists all nodes, `roles/mariadb/templates/galera.cnf.j2:33`); existing members restart in a play
  with `serial: "33%"` (`roles/mariadb/handlers/main.yml:59-74`, `mariadb.yml:18-34`) ([fact sheet B §1.4][sheet-b-14]
  and [§1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities)
  item 11). RabbitMQ members restart the same way (`rabbitmq.yml:30-49`), since `rabbitmq.conf` lists every node
  (`roles/rabbitmq/templates/rabbitmq.conf.j2:18-21`).
- **Plus, under `-t keystone`:** `keystone` and `keystone_fernet` restart on every keystone host, since their
  `keystone.conf` carries the transport URL and the memcache server list (`roles/keystone/templates/keystone.conf.j2:4`,
  `roles/keystone/templates/keystone.conf.j2:51`); `keystone_fernet` also gets a new crontab and push script (see
  [§1.1](#11-remove-or-replace-a-controller)). With the default serial 0 these restarts happen on all keystone hosts at
  once (`site.yml:503`, `roles/keystone/handlers/main.yml:43-69`); `reconfigure` cannot be batched in 2025.1
  ([F19](../reference/findings.md#f19)), so a batched keystone run is `deploy -t keystone -e kolla_serial=N`.
- **Plus, under `-t etcd` (when enabled):** the etcd play has no `serial` (`site.yml:485-496`), so `kolla_serial`
  does not batch it. The new member is added and started; then the existing members are restarted by the handlers, the
  non-leaders in `% 4` waves and the leader last (`roles/etcd/handlers/main.yml:38-61`). The bootstrap fact that
  notifies these handlers is reported changed on every etcd host of the play (`roles/etcd/tasks/bootstrap.yml:16-25`),
  and `recreate_or_restart_container` restarts a container even when nothing in it differs
  with the default `COPY_ALWAYS` strategy (`group_vars/all.yml:49`; `module_utils/kolla_docker_worker.py:352-374`,
  `module_utils/kolla_podman_worker.py:609-626`), so every existing member restarts although its own configuration
  does not list the members [CODE]. Clients reach etcd through the internal VIP (e.g.
  `roles/cinder/templates/cinder.conf.j2:280`), so their configuration does not change; the haproxy `etcd` backend does
  (`roles/etcd/defaults/main.yml:11-17`). Whether clients fail while the members restart is [NOT AVAILABLE].

**Takeaway:** controller membership changes are fleet-wide restart events for every messaging consumer. Schedule them
as such, and batch the compute side.

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R3](../risk/risk-register.md#r3) (changing
  RabbitMQ group membership) and [R4](../risk/risk-register.md#r4) (changing memcached membership)
- [RabbitMQ](../components/rabbitmq.md) — service card and where to look
- [Memcached](../components/memcached.md) — service card and where to look
- [MariaDB/Galera](../components/mariadb.md) — service card and where to look; Galera membership changes restart all
  DB nodes
- [Keystone](../components/keystone.md) — Fernet keys, rotation schedule and key distribution
- [Tags §2.5](../risk/tags.md#25-run_once-with-serial-code) — why the etcd play is not batched by `kolla_serial`
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Write config first, apply in controlled batches](controlled-batches.md) — how to apply in batches (`genconfig`,
  then `deploy-containers --limit`; `deploy -e kolla_serial=N`); its examples use the nova tags
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) — one extra controller changes
  the transport URL in every messaging service everywhere

[sheet-b-14]: ../reference/factsheets/b-mariadb-rabbitmq-keystone.md#14-config-files-generated-ansiblerolesmariadbtasksconfigyml
