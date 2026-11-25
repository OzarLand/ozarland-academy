---
title: Reconfigure Neutron
description: "What -t neutron reconfigure runs in 2025.1 on controllers, network nodes and every compute, which overrides restart which agents, and network impact."
tags: [neutron, openvswitch, ovn, reconfigure, genconfig, limit, one-shot]
impact: [restarts-on-drift, critical]
---

# Reconfigure Neutron

What `kolla-ansible -t neutron reconfigure` does in 2025.1: it runs the loadbalancer play (neutron-server frontend) and
the neutron play on `neutron-server`, every agent group, every compute and `manila-share`. The page gives the restart
set per change and what is known of the impact on networking.

The scenario sections are written for the [assumed deployment](index.md#assumed-deployment); the page uses the
definition of [drift](index.md#drift) and the notion of [code guarantees and environment
dependence](index.md#code-guarantees-and-environment-dependence).

> [!NOTE]
> **Key answers**
>
> - **`-t neutron reconfigure` ([§2 to §5](#2-execution-and-targets))** targets every compute, all hosts in one batch,
>   and still runs the `bootstrap_neutron` DB-sync container on every reconfigure [CODE]
>   ([§2](#2-execution-and-targets)).
> - **Changed in 2025.1** [CODE] ([§3](#3-what-restarts-code)): a change restarts only the containers whose own files
>   or definition changed (an `ml2_conf.ini` override restarts `neutron_server` alone); `reconfigure` cannot be batched,
>   so use `deploy -t neutron -e kolla_serial=N` or `--limit` ([F19](../reference/findings.md#f19)); Linux Bridge is
>   gone; the first 2025.1 run recreates most neutron containers. What an agent restart does to existing connectivity
>   is [NOT AVAILABLE] ([§4](#4-impact-on-networking)).

> [!WARNING]
> [R6](../risk/risk-register.md#r6): with `enable_neutron_agent_ha` (and the agent wrappers off, the default), the L3
> agent wrapper runs `neutron-netns-cleanup` before the agent starts, at every `neutron_l3_agent` restart; what that
> command deletes is [NOT AVAILABLE] — see [§4](#4-impact-on-networking).

## 1. Commands

### 1.1 Neutron

```bash
kolla-ansible reconfigure -i multinode -t neutron                        # server + all agents (+ computes), one batch
kolla-ansible deploy -i multinode -t neutron --limit network01            # one network node at a time
kolla-ansible deploy -i multinode -t neutron -e kolla_serial=10           # batches of 10 hosts
kolla-ansible deploy -i multinode -t openvswitch --limit compute042       # OVS on one host
```

- `-t neutron` targets every compute (the neutron play includes `compute`, `site.yml:669-691`).
- **Changed in 2025.1:** `reconfigure` passes `kolla_serial=0` after your own `-e`, so it always takes every host of
  the play at once (`kolla_ansible/cli/commands.py:128-140`; [F19](../reference/findings.md#f19)). `deploy` runs the
  same neutron tasks (`roles/neutron/tasks/reconfigure.yml:2`) and accepts `kolla_serial` ([Write config first, apply
  in controlled batches §1.2](controlled-batches.md#12-rolling-runs-with-kolla_serial-not-with-reconfigure)).
- Network nodes should be done one at a time. With `enable_neutron_agent_ha`, the L3 agent wrapper runs
  `neutron-netns-cleanup` before the agent starts, at every `neutron_l3_agent` restart; what that command deletes is
  [NOT AVAILABLE] ([R6](../risk/risk-register.md#r6)).

## 2. Execution and targets

`kolla-ansible -t neutron reconfigure` runs:

1. the loadbalancer play (neutron-server frontend; `site.yml:105-120`, neutron include `site.yml:243-247`). **Changed
   in 2025.1:** both frontends add `option httpchk` (`roles/neutron/defaults/main.yml:19-20`, `:28-29`), and the
   frontend file is written without restarting HAProxy under `-t neutron`
   ([F18](../reference/findings.md#f18));
2. the neutron play on `neutron-server`, every agent group, **every compute** and `manila-share`, with
   `serial: kolla_serial` (forced to `0` by `reconfigure`) and `max_fail_percentage` (default `100`)
   (`site.yml:669-691`).

Per host the steps are (`roles/neutron/tasks/deploy.yml:2-23`; `roles/neutron/tasks/reconfigure.yml:2` imports that
file):

- **the ML2 plugin check:** container facts for `neutron_openvswitch_agent`/`ovn_controller` and the OVN DB volumes;
  it fails the host if the running agent type does not match `neutron_plugin_agent`
  (`roles/neutron/tasks/neutron_plugin_agent_check.yml:2-37`). **New in 2025.1:** the OVN condition reads the volume
  facts at a key the module no longer returns ([Neutron](../components/neutron.md#known-limits-and-open-points));
- **register** (run_once): it grants the neutron user the `service` role in the `service` project
  (`roles/neutron/tasks/register.yml:2-8`, `roles/neutron/defaults/main.yml:898-901`);
- **config-host:** the kernel modules on L3 and Open vSwitch agent hosts (`roles/neutron/tasks/config-host.yml:2-13`);
  an IPv6 check on every host, whose result no task reads (`roles/neutron/tasks/config-host.yml:15-18`); the
  `gc_thresh` sysctl values on L3 agent hosts when `set_sysctl` (default `yes`, `group_vars/all.yml:816`), through the
  `sysctl` role (`roles/neutron/tasks/config-host.yml:20-34`, `roles/sysctl/tasks/main.yml:1-20`,
  `group_vars/all.yml:819`) [CODE];
- **config, check-containers**, the fake-driver config when `enable_nova_fake`, **bootstrap**, then a flush of the
  handlers (`roles/neutron/tasks/deploy.yml:11-23`).

`common` does not run under `-t neutron`: it is its own play, tagged `common` only (`site.yml:88-103`). The bootstrap
step always runs the Neutron DB and user/grant tasks (`mysql_db`/`mysql_user` via kolla_toolbox, run_once, delegated to
neutron-server[0], skipped only with `use_preconfigured_databases`, `roles/neutron/tasks/bootstrap.yml:2-36`) [CODE],
so MariaDB must be reachable.

**Still holds in 2025.1:** the `bootstrap_neutron` DB-sync container has no `when`, so it runs on every `reconfigure`
(and `deploy`), run_once on neutron-server[0] (`roles/neutron/tasks/bootstrap.yml:38`,
`roles/neutron/tasks/bootstrap_service.yml:2-21`). `neutron_enable_rolling_upgrade`
(`roles/neutron/defaults/main.yml:707`) is read only by `roles/neutron/tasks/upgrade.yml:4-8`. The container runs
`neutron-db-manage --subproject neutron upgrade head`, then the same for each enabled subproject in
`NEUTRON_BOOTSTRAP_SERVICES` (kolla `docker/neutron/neutron-server/extend_start.sh:5-13`;
`roles/neutron/defaults/main.yml:651-663`, `:702`). What a no-op `upgrade head` does to a running neutron-server is
[NOT AVAILABLE].

## 3. What restarts [CODE]

**Changed in 2025.1:** no config task notifies; `service-check-containers` notifies `Restart <service> container` for
each container whose `compare_container` reported a change (`roles/neutron/tasks/check-containers.yml:2-3`; [Tags
§2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)). A file change restarts a container only if that file is
copied into it by its `config.json`, which `kolla_set_configs --check` compares.

| Change | Restarted | Source |
|---|---|---|
| `/etc/kolla/config/neutron/ml2_conf.ini` (meant for the server) | neutron_server only (controllers), plus neutron_infoblox_ipam_agent where enabled. **Changed in 2025.1:** no longer the other neutron containers of a host that runs neutron-server. `openvswitch_agent.ini` does not merge `ml2_conf.ini`, so the agents on computes and network nodes do not restart | `roles/neutron/tasks/config.yml:134-164`; `roles/neutron/tasks/check-containers.yml:2-3` |
| `/etc/kolla/config/neutron/openvswitch_agent.ini` | neutron_openvswitch_agent on all computes and network nodes | `roles/neutron/tasks/config.yml:152-164` |
| `/etc/kolla/config/neutron.conf` (also `global.conf`, `neutron/<host>/neutron.conf`) | every neutron container on every host (all but neutron_tls_proxy render `neutron.conf`) | `roles/neutron/tasks/config.yml:73-104` |
| `/etc/kolla/config/neutron/<service>.conf`, e.g. `neutron/neutron-openvswitch-agent.conf` | that container only, on every host that runs it | `roles/neutron/tasks/config.yml:97` |
| Files in `/etc/kolla/config/neutron/plugins/` | neutron_server, and neutron_openvswitch_agent on every host that runs one, computes included | `roles/neutron/tasks/config.yml:12-22`, `roles/neutron/tasks/config.yml:377-396` |
| `/etc/kolla/config/neutron/fwaas_driver.ini`, with `enable_neutron_fwaas` | neutron_server and neutron_l3_agent (no per-host override file) | `roles/neutron/tasks/config.yml:254-270` |
| `/etc/kolla/config/neutron/neutron_taas.conf` (or `neutron/<host>/neutron_taas.conf`), with `enable_neutron_taas` | neutron_server and neutron_openvswitch_agent, so every compute | `roles/neutron/tasks/config.yml:411-428` |
| turning `enable_neutron_fwaas` or `enable_neutron_taas` on or off | every container that renders `neutron.conf` (its `service_plugins` gains `firewall_v2` or `taas`); TaaS also adds `taas` to the Open vSwitch agent `extensions`, FWaaS adds `fwaas_v2` to the L3 agent `extensions`; the next `bootstrap_neutron` migrates the subproject ([§2](#2-execution-and-targets)) | `roles/neutron/defaults/main.yml:720-750, :766-788`; `roles/neutron/templates/neutron.conf.j2:47`, `roles/neutron/templates/openvswitch_agent.ini.j2:9-10`, `roles/neutron/templates/l3_agent.ini.j2:17-18` |
| `/etc/kolla/config/neutron/neutron_vpnaas.conf` | neutron_server and neutron_l3_agent, only with `enable_neutron_vpnaas` | `roles/neutron/tasks/config.yml:105-123`; `roles/neutron/templates/neutron-server.json.j2:2`, `roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:18-22` |
| **New in 2025.1:** `neutron_physical_networks`, or the number of bridges in `neutron_bridge_name` | neutron_server (`ml2_conf.ini`: `network_vlan_ranges`, `flat_networks`) and neutron_openvswitch_agent on every host (`bridge_mappings`); the `ovn-controller` chassis mappings follow the same variable under `-t ovn` | `group_vars/all.yml:1214-1215`; `roles/neutron/templates/ml2_conf.ini.j2:18`, `:27`; `roles/neutron/templates/openvswitch_agent.ini.j2:18-19`; [OVN](../components/ovn.md) |
| **New in 2025.1:** `neutron_agents_wrappers` on or off | neutron_dhcp_agent and neutron_l3_agent are recreated (environment, `pid_mode`, `cgroupns_mode`, engine socket volumes), and the L3 wrapper script changes | `roles/neutron/defaults/main.yml:54-90`, `:483-507`, `:646`; `roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:5-16` |
| RabbitMQ/memcached membership change | every neutron container that renders `neutron.conf` (transport URLs, memcached list) | `group_vars/all.yml:274, :284`; `roles/neutron/templates/neutron.conf.j2:56, :121, :124`; [Change control-plane membership](change-control-plane-membership.md) |

**First run of the 2025.1 code on a cloud deployed by 2024.1** [CODE]: expect most neutron containers to be recreated
or restarted, computes included, even with no operator change:

- every neutron container's volume list now always has `/dev/shm` (2024.1 added it only with `om_enable_queue_manager`,
  default `false`), and the volume list is part of the container comparison
  (`roles/neutron/defaults/main.yml:483-599`; `module_utils/kolla_container_worker.py:58-65`);
- `neutron_dhcp_agent` and `neutron_l3_agent` get three new environment variables and an explicit `cgroupns_mode`
  (`roles/neutron/defaults/main.yml:54-90`);
- `neutron_metadata_agent` loses its healthcheck by default (`roles/neutron/defaults/main.yml:366-377`);
- `neutron.conf` changes for every container that renders it: the queue options are unconditional
  ([F17](../reference/findings.md#f17)), `www_authenticate_uri` points to the public Keystone URL, and booleans are
  written in lower case (`roles/neutron/templates/neutron.conf.j2:106`, `:131-144`);
- with `kolla_copy_ca_into_containers` or the TLS backend, every agent's `config.json` gains a `ca-certificates` entry
  (e.g. `roles/neutron/templates/neutron-openvswitch-agent.json.j2:37-43`; `roles/neutron/defaults/main.yml:938`);
- and the systemd unit of every container written by 2024.1 is reported as drift at its first 2025.1 check
  ([F16](../reference/findings.md#f16)).

In an `upgrade` the new images recreate the containers anyway. [NOT AVAILABLE] Whether the first 2025.1 `deploy` of a
cloud whose images did not change recreates every agent on every compute at once; to be confirmed by the community.

**Handlers** [CODE]: one `recreate_or_restart_container` handler per container; **changed in 2025.1**, they are no
longer skipped when `kolla_action` is `config` (no config task notifies any more), and the Linux Bridge handler is gone
(`roles/neutron/handlers/main.yml:1-296`). The L3 agent handler is a chain: container facts, a `group_by` on whether
`neutron_l3_agent` runs, start of the stopped ones, a wait of `neutron_l3_agent_failover_delay` when both kinds exist,
then the running ones (`roles/neutron/handlers/main.yml:67-134`). For the running ones, each host loops over the list
of hosts with a running L3 agent and restarts only on its own item, with a pause of `neutron_l3_agent_failover_delay`
seconds (default `0`, `roles/neutron/defaults/main.yml:626`) before every item but the first
(`roles/neutron/handlers/main.yml:112-134`; ansible-core 2.18.20 `lib/ansible/executor/task_executor.py:329-331`).
With the default `0` nothing spaces the restarts.

## 4. Impact on networking

| Component | On restart (code-guaranteed when drift) | Effect on existing connectivity (environment-dependent) |
|---|---|---|
| neutron-server | API unavailable during the stop/start, on all controllers at once under `reconfigure` (`kolla_serial` forced to 0, [F19](../reference/findings.md#f19)) | [NOT AVAILABLE] Whether existing traffic is unaffected, and whether port bindings and new instances fail during the window |
| neutron-openvswitch-agent | container stop/start, or recreate at the first 2025.1 run | [NOT AVAILABLE] Whether flows in OVS persist while the agent is down, whether and how the agent resyncs and re-installs flows on start with the 2025.1 defaults, and whether a VM loses packets during the agent restart |
| neutron-l3-agent | stop/start; with `enable_neutron_agent_ha: yes` and the wrappers off, the wrapper runs `neutron-netns-cleanup --force --agent-type l3` **before** the agent starts (the wrapper's comment: "Remove all l3 related netns"), with `fwaas_driver.ini` added when FWaaS is enabled (`roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:5-16`) | [CODE] Without the HA cleanup nothing in the wrapper deletes namespaces, and `/run/netns` is shared with the host (`roles/neutron/defaults/main.yml:501`). **New in 2025.1:** with `neutron_agents_wrappers`, keepalived, haproxy and radvd run in child containers (kolla `docker/neutron/neutron-l3-agent/extend_start.sh:31-37`). [NOT AVAILABLE] Whether the namespaces then persist, whether the keepalived/haproxy processes (or child containers) survive the agent's container, whether with the cleanup all routers on that node lose N-S/FIP connectivity until rebuilt, and whether HA routers fail over. [NOT AVAILABLE] What the cleanup command deletes: it is neutron code, which is not in these sources ([F12](../reference/findings.md#f12)) |
| neutron-dhcp-agent | stop/start | [NOT AVAILABLE] Whether dnsmasq processes (or, with the wrappers, child containers) die with the container, whether VMs renewing leases in the window fail to renew, and whether new ports wait for the agent to come back |
| neutron-metadata-agent | stop/start; no healthcheck by default in 2025.1 | [NOT AVAILABLE] Whether metadata requests (cloud-init) fail during the window. The requests now end at the `nova_metadata` container ([Nova](../components/nova.md)) |
| Open vSwitch | **not touched** by `-t neutron` (separate play/tag, `site.yml:605-619`) | – |
| OVN (if `neutron_plugin_agent: ovn`) | `-t neutron` touches neutron-server and `neutron-ovn-metadata-agent` (plus `neutron_ovn_agent` with `neutron_enable_ovn_agent`, default `no`, `group_vars/all.yml:1245`). `-t ovn` runs both the `ovn-controller` and the `ovn-db` plays (`site.yml:635-647`, `site.yml:649-663`). The `ovn-controller` role re-applies `br-int` and the `external_ids` keys on every ovn-controller host, and in 2025.1 points `ovn-remote` at an SB relay (`roles/ovn-controller/tasks/setup-ovs.yml:2-49`; [OVN](../components/ovn.md)) | ovn-controller restart is not triggered by `-t neutron` |

## 5. Risks and verification

- **Risks:** [R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6), [R7](../risk/risk-register.md#r7).
- **Before:**
  - `openstack network agent list` (all alive);
  - identify the network nodes that host HA router masters;
  - render with `kolla-ansible genconfig -t neutron` and diff `openvswitch_agent.ini` and `neutron.conf` on a compute
    (and `neutron_taas.conf` with TaaS). If one changed, **every compute will restart its agent**;
  - `kolla_set_configs --check` in `neutron_openvswitch_agent` on a few computes: exit 1 means that container will
    restart ([Kolla images
    §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)); the check does
    not see a changed volume list or unit file, which the module compares on the host;
  - on the first run of the 2025.1 code, expect most neutron containers to be recreated ([§3](#3-what-restarts-code));
  - expect the `bootstrap_neutron` DB-sync container on neutron-server[0] even with no change
    ([§2](#2-execution-and-targets)).
- **Apply:** network nodes one by one (`deploy -t neutron --limit network01`, then `network02`). Computes in batches
  (`deploy -t neutron -e kolla_serial=N`, or `--limit`), not with `reconfigure`.
- **After:**
  - agent list;
  - `ip netns` count on network nodes matches the number of routers/networks;
  - ping a VM's floating IP continuously during each batch;
  - a metadata request from an instance.
- [NOT AVAILABLE] Confirmation that an `ml2_conf.ini` change restarts `neutron_server` alone, and the data-plane effect
  of the first-run recreates on computes; to be confirmed by the community.

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R5](../risk/risk-register.md#r5)
  (`ml2_conf.ini` override meant for neutron-server; in 2025.1 it restarts `neutron_server` alone,
  [§3](#3-what-restarts-code)), [R6](../risk/risk-register.md#r6) (restart of `neutron_l3_agent` with
  `enable_neutron_agent_ha: yes`) and [R7](../risk/risk-register.md#r7) (`openvswitch_vswitchd` restart or recreate)
- [Neutron](../components/neutron.md) — service card, what changed in 2025.1 and where to look
- [Open vSwitch](../components/openvswitch.md) — service card and where to look; Open vSwitch has a separate play and
  tag and is not touched by `-t neutron`
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Write config first, apply in controlled batches](controlled-batches.md) — how to apply in batches (`genconfig`,
  then `deploy-containers --limit`; `deploy -e kolla_serial=N`); its examples use the nova tags
- [Kolla images §5.3](../concepts/kolla-images.md#53-neutron-l3-agent-the-wrapper) — neutron-l3-agent: the wrapper
  that runs the namespace cleanup with `enable_neutron_agent_ha`
- [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane) — what the sources do not establish
  about the network data plane
