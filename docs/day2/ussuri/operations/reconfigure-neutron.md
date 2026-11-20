---
title: Reconfigure Neutron
description: What -t neutron reconfigure runs on controllers, network nodes and every compute, which overrides restart which agents, and what is known of the network impact.
tags: [neutron, openvswitch, ovn, reconfigure, genconfig, loop-notify, limit, one-shot]
impact: [restarts-on-drift, critical]
---

# Reconfigure Neutron

What `kolla-ansible -t neutron reconfigure` does: it runs the haproxy play (neutron-server frontend) and the neutron
play on `neutron-server`, every agent group, every compute and `manila-share`. The page gives the restart set per change
and what is known of the impact on networking.

The scenario sections are written for the [assumed deployment](index.md#assumed-deployment); the page uses the
definition of [drift](index.md#drift) and the notion of [code guarantees and environment
dependence](index.md#code-guarantees-and-environment-dependence).

> [!NOTE]
> **Key answers**
>
> - **`-t neutron reconfigure` ([§2 to §5](#2-execution-and-targets))** targets every compute. An `ml2_conf.ini`
>   override meant for the server also restarts `neutron_openvswitch_agent` on all computes and network nodes [CODE]
>   ([§3](#3-what-restarts-code)). What an agent restart does to existing connectivity is [NOT AVAILABLE]
>   ([§4](#4-impact-on-networking)).

> [!WARNING]
> [R6](../risk/risk-register.md#r6): with `enable_neutron_agent_ha`, the L3 agent wrapper runs
> `neutron-netns-cleanup` before the agent starts, at every `neutron_l3_agent` restart; what that command deletes is
> [NOT AVAILABLE] — see [§4](#4-impact-on-networking).

## 1. Commands

### 1.1 Neutron

```bash
kolla-ansible -i multinode -t neutron reconfigure                        # server + all agents (+ computes)
kolla-ansible -i multinode -t neutron reconfigure --limit network01       # one network node at a time
kolla-ansible -i multinode -t openvswitch reconfigure --limit compute042  # OVS on one host
```

- `-t neutron` targets every compute (the neutron play includes `compute`).
- Network nodes should be done one at a time. With `enable_neutron_agent_ha`, the L3 agent wrapper runs
  `neutron-netns-cleanup` before the agent starts, at every `neutron_l3_agent` restart; what that command deletes is
  [NOT AVAILABLE] ([R6](../risk/risk-register.md#r6)).

## 2. Execution and targets

`kolla-ansible -t neutron reconfigure` runs:

1. the haproxy play (neutron-server frontend);
2. the neutron play on `neutron-server`, every agent group, **every compute** and `manila-share` (`site.yml:761-780`).

Per host the steps are: `common` (first play for the host under this tag), register (run_once), config-host
(`ip6_tables` module; sysctl on L3 hosts), config, check-containers, bootstrap, flush. The bootstrap step always runs
the Neutron DB and user/grant tasks (`mysql_db`/`mysql_user` via kolla_toolbox, run_once, delegated to
neutron-server[0], skipped only with `use_preconfigured_databases`, `roles/neutron/tasks/bootstrap.yml:2-34`)
[CODE], so MariaDB must be reachable.
The `bootstrap_neutron` DB-sync container is skipped on reconfigure only because `neutron_enable_rolling_upgrade`
defaults to `yes` (`roles/neutron/defaults/main.yml:411`). With it set to `no`, the DB sync also runs on every
reconfigure (`roles/neutron/tasks/bootstrap_service.yml:21-22`). With `enable_neutron_sfc`, the SFC bootstrap container
runs on every reconfigure regardless (`bootstrap_service.yml:24-46`).

## 3. What restarts [CODE]

| Change | Restarted | Source |
|---|---|---|
| `/etc/kolla/config/neutron/ml2_conf.ini` (meant for the server) | neutron_server (controllers); **neutron_openvswitch_agent on all computes and network nodes** (`openvswitch_agent.ini` merges `ml2_conf.ini`); on network nodes also **dhcp, l3, metadata agents** (loop-notify) | `roles/neutron/tasks/config.yml:130-150, :172-190`; `roles/neutron/tasks/check-containers.yml:2-18`; [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) |
| `/etc/kolla/config/neutron.conf` | every neutron container on every host | `roles/neutron/tasks/config.yml:73-106` |
| RabbitMQ/memcached membership change | every neutron container (transport URL) | `group_vars/all.yml:206`; `roles/neutron/templates/neutron.conf.j2:57, :119`; [Change control-plane membership §2](change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller) |

## 4. Impact on networking

| Component | On restart (code-guaranteed when drift) | Effect on existing connectivity (environment-dependent) |
|---|---|---|
| neutron-server | API unavailable during the stop/start, on all controllers at once | [NOT AVAILABLE] Whether existing traffic is unaffected, and whether port bindings and new instances fail during the window |
| neutron-openvswitch-agent | container stop/start | [NOT AVAILABLE] Whether flows in OVS persist while the agent is down, whether and how the agent resyncs and re-installs flows on start with the Ussuri defaults, and whether a VM loses packets during the agent restart |
| neutron-l3-agent | stop/start; with `enable_neutron_agent_ha: yes` the wrapper runs `neutron-netns-cleanup --force --agent-type l3` **before** the agent starts (the wrapper's comment: "Remove all l3 related netns"; `neutron-l3-agent-wrapper.sh.j2:5-12`) | [CODE] Without the HA cleanup nothing in the wrapper deletes namespaces, and `/run/netns` is shared with the host (`roles/neutron/defaults/main.yml:259`). [NOT AVAILABLE] Whether the namespaces then persist, whether keepalived/haproxy child processes die with the container, whether with the cleanup all routers on that node lose N-S/FIP connectivity until rebuilt, and whether HA routers fail over. [NOT AVAILABLE] What the cleanup command deletes: it is neutron code, which is not in these sources ([F12](../reference/findings.md#f12)) |
| neutron-dhcp-agent | stop/start | [NOT AVAILABLE] Whether dnsmasq processes die with the container, whether VMs renewing leases in the window fail to renew, and whether new ports wait for the agent to come back |
| neutron-metadata-agent | stop/start | [NOT AVAILABLE] Whether metadata requests (cloud-init) fail during the window |
| Open vSwitch | **not touched** by `-t neutron` (separate play/tag) | – |
| OVN (if `neutron_plugin_agent: ovn`) | `-t neutron` touches neutron-server and `neutron-ovn-metadata-agent`. `-t ovn` re-runs chassis registration on every compute/network node (about 5 `ovs-vsctl` each, always reported changed) and overwrites `ovn-cms-options` ([fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable)) | ovn-controller restart is not triggered by `-t neutron` |

## 5. Risks and verification

- **Risks:** [R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6), [R7](../risk/risk-register.md#r7).
- **Before:**
  - `openstack network agent list` (all alive);
  - identify the network nodes that host HA router masters;
  - render with `genconfig -t neutron` and diff `openvswitch_agent.ini` on a compute. If it changed, **every compute
    will restart its agent**.
- **Apply:** network nodes one by one (`--limit network01`, then `network02`). Computes in batches.
- **After:**
  - agent list;
  - `ip netns` count on network nodes matches the number of routers/networks;
  - ping a VM's floating IP continuously during each batch.

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R5](../risk/risk-register.md#r5)
  (`ml2_conf.ini` override meant for neutron-server), [R6](../risk/risk-register.md#r6) (restart of
  `neutron_l3_agent` with `enable_neutron_agent_ha: yes`) and [R7](../risk/risk-register.md#r7)
  (`openvswitch_vswitchd` restart or recreate)
- [Neutron](../components/neutron.md) — service card and where to look
- [Open vSwitch](../components/openvswitch.md) — service card and where to look; Open vSwitch has a separate play and
  tag and is not touched by `-t neutron`
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Write config first, apply in controlled batches](controlled-batches.md) — how to apply in batches (`genconfig`,
  then `deploy-containers --limit`; `ANSIBLE_SERIAL`); its examples use the nova tags
- [Kolla images §5.3](../concepts/kolla-images.md#53-neutron-l3-agent-the-wrapper) — neutron-l3-agent: the wrapper
  that runs the namespace cleanup with `enable_neutron_agent_ha`
- [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane) — what the sources do not establish
  about the network data plane
