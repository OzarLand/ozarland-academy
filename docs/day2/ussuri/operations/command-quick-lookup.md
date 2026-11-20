---
title: Command quick lookup by tag
description: One row per command and tag, with the hosts touched, the containers that can restart, the one-shot containers and what drives the duration.
tags: [tags, reconfigure, deploy-containers, genconfig, pull, one-shot, keystone, glance, placement, nova, neutron, openvswitch, haproxy, chrony, mariadb, rabbitmq]
impact: [restarts-on-drift, writes-config, pulls-images]
---

# Command quick lookup by tag

One row per command: the hosts it touches with the default inventory, the containers that can restart, the one-shot
containers it runs and what drives its duration. Twelve rows are `-t <tag> reconfigure`; the last four are `reconfigure`
without a tag, `deploy-containers`, `genconfig` and `pull`.

The table follows the [conventions of the command sections](index.md#conventions-used-by-the-command-sections), which
also say what the examples assume: "Can restart" is the **Restarts** convention, containers that can restart, only if
[drift](index.md#drift) is detected.

| Command | Hosts touched (default inventory) | Can restart | One-shot containers | Typical duration driver |
|---|---|---|---|---|
| `-t keystone reconfigure` | haproxy, control | keystone ×3, haproxy | keystone db sync | small |
| `-t glance reconfigure` | haproxy, `glance-api` | glance-api, haproxy | db sync + metadefs load + MariaDB global flag toggle | small |
| `-t placement reconfigure` | haproxy, control | placement-api, haproxy | db sync + online data migrations (one `bootstrap_placement` container) | small |
| `-t nova reconfigure` | haproxy, control, **all computes** | all nova incl. **libvirt**, haproxy | 5 runs (those of `nova-api` and `nova-cell` below) | number of computes |
| `-t nova-api reconfigure` | haproxy, control | nova-api, scheduler, haproxy | 2 (API DB sync, `map_cell0`) | small |
| `-t nova-cell reconfigure` | haproxy (console-proxy frontends), control (conductor, consoles), **all computes** | conductor, consoles, compute, libvirt, ssh; haproxy if a console-proxy frontend changed | 3 (cell DB sync, `list_cells` ×2: cell lookup and discovery; `discover_hosts` itself is a `docker exec` into `nova_conductor`) | number of computes |
| `-t neutron reconfigure` | haproxy, control, network, **all computes** | server, all agents, haproxy | none by default (neutron db sync is deploy-only while `neutron_enable_rolling_upgrade` is `yes`) | number of computes |
| `-t openvswitch reconfigure` | network, **all computes** | openvswitch_db/vswitchd | – | number of computes |
| `-t haproxy reconfigure` | haproxy | haproxy, keepalived, common | – | small |
| `-t chrony reconfigure` | **all hosts** | chrony + common (fluentd, cron, toolbox) | – | number of hosts |
| `-t mariadb reconfigure` | haproxy, mariadb | mariadb (4 waves), clustercheck, haproxy | – | Galera sync |
| `-t rabbitmq reconfigure` | haproxy, rabbitmq (+outward) | rabbitmq one by one, haproxy | – | broker start |
| `reconfigure` (no tag) | all | everything that drifted | db sync of every enabled service except neutron (see the neutron row) | number of hosts × tasks |
| `deploy-containers -t X` | X's hosts | X (drifted only) | none | small per host |
| `genconfig -t X` | X's hosts (+haproxy) | none | none | templating |
| `pull -t X` | X's hosts | none | none | image size × hosts |

## Related

- [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) — the master table: what each tag executes and
  on which hosts
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites) — per-tag
  answers: files, VMs, APIs, networking and storage, safety, prerequisites
- [Tag index](../risk/tag-index.md) — each tag with its component page
- [Operations catalogue](index.md#operations-catalogue) — the operation pages, with their full command lines
- [Predict and inspect a run](predict-a-run.md) — how to see what will restart before running one of these commands
- [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) — what each
  one-shot container runs
- [Compute scaling §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files)
  — the work per compute host, read from the task files
