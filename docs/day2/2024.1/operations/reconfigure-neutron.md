---
title: Reconfigure Neutron
description: What -t neutron reconfigure runs in 2024.1 on controllers, network nodes and every compute, which overrides restart which agents, and the known network impact.
tags: [neutron, openvswitch, ovn, reconfigure, genconfig, loop-notify, limit, one-shot]
impact: [restarts-on-drift, critical]
---

# Reconfigure Neutron

What `kolla-ansible -t neutron reconfigure` does in 2024.1: it runs the loadbalancer play (neutron-server frontend) and
the neutron play on `neutron-server`, every agent group, every compute and `manila-share`. The page gives the restart
set per change and what is known of the impact on networking.

The scenario sections are written for the [assumed deployment](index.md#assumed-deployment); the page uses the
definition of [drift](index.md#drift) and the notion of [code guarantees and environment
dependence](index.md#code-guarantees-and-environment-dependence).

> [!NOTE]
> **Key answers**
>
> - **`-t neutron reconfigure` ([§2 to §5](#2-execution-and-targets))** targets every compute, and still runs the
>   `bootstrap_neutron` DB-sync container on every reconfigure [CODE] ([§2](#2-execution-and-targets)). An
>   `ml2_conf.ini` override still restarts only `neutron_server` (and the other neutron containers of its host) [CODE]
>   ([§3](#3-what-restarts-code)); a `neutron.conf` override still restarts every neutron container on every host.
> - **New in 2024.1** [CODE] ([§3](#3-what-restarts-code)): FWaaS (`fwaas_driver.ini`) and TaaS (`neutron_taas.conf`,
>   which reaches the Open vSwitch agent on every compute); `neutron.conf` now always carries `dns_domain`; the L3-host
>   sysctl values go through the new `sysctl` role ([§2](#2-execution-and-targets)). The handlers are unchanged apart
>   from the module name. What an agent restart does to existing connectivity is [NOT AVAILABLE]
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

- `-t neutron` targets every compute (the neutron play includes `compute`, `site.yml:671-693`).
- Network nodes should be done one at a time. With `enable_neutron_agent_ha`, the L3 agent wrapper runs
  `neutron-netns-cleanup` before the agent starts, at every `neutron_l3_agent` restart; what that command deletes is
  [NOT AVAILABLE] ([R6](../risk/risk-register.md#r6)).

## 2. Execution and targets

`kolla-ansible -t neutron reconfigure` runs:

1. the loadbalancer play (neutron-server frontend; `site.yml:105-116`, neutron include `:243-247`). **Changed in
   2024.1:** the external frontend now names `neutron_external_fqdn` and `neutron_server_public_port`, which follows
   the single external frontend when it is enabled (`roles/neutron/defaults/main.yml:19-25`,
   `group_vars/all.yml:502-505`);
2. the neutron play on `neutron-server`, every agent group, **every compute** and `manila-share`, with
   `serial: kolla_serial` (default `"0"`) and, new in 2024.1, `max_fail_percentage` (default `100`)
   (`site.yml:671-693`).

Per host the steps are (`roles/neutron/tasks/deploy.yml:2-23`; `reconfigure.yml:2` imports that file):

- **the ML2 plugin check:** container facts for `neutron_openvswitch_agent`/`ovn_controller` and the OVN DB volumes;
  it fails the host if the running agent type does not match `neutron_plugin_agent`
  (`neutron_plugin_agent_check.yml:2-35`);
- **register** (run_once). **New in 2024.1:** it also grants the neutron user the `service` role in the `service`
  project (`register.yml:2-8`, `roles/neutron/defaults/main.yml:923-926`,
  `roles/service-ks-register/tasks/main.yml:103-117`);
- **config-host:** the `ip6_tables` module on L3, linuxbridge and Open vSwitch agent hosts (`config-host.yml:2-13`);
  an IPv6 check on every host; the `gc_thresh` sysctl values on L3 agent hosts when `set_sysctl` (default `yes`,
  `group_vars/all.yml:703`). **Changed in 2024.1:** the sysctl values are set by the new `sysctl` role, included with
  the list as `settings` (`config-host.yml:20-34`). The role runs its own `Check IPv6 support`, skips a value
  `KOLLA_SKIP`, removes a key whose value is `KOLLA_UNSET`, and skips the `net.ipv6.*` keys when
  `net.ipv6.conf.all.disable_ipv6` is `1`, writing to `kolla_sysctl_conf_path` (`/etc/sysctl.conf`)
  (`roles/sysctl/tasks/main.yml:1-20`, `group_vars/all.yml:706`). The neutron role's own IPv6 check
  (`config-host.yml:15-18`) still runs, but no task of the role reads its result any more [CODE];
- **config, check-containers**, the fake-driver config when `enable_nova_fake`, **bootstrap**, then a flush of the
  handlers (`deploy.yml:11-23`).

`common` does not run under `-t neutron`: it is its own play, tagged `common` only (`site.yml:88-104`). The bootstrap
step always runs the Neutron DB and user/grant tasks (`mysql_db`/`mysql_user` via kolla_toolbox, run_once, delegated to
neutron-server[0], skipped only with `use_preconfigured_databases`, `roles/neutron/tasks/bootstrap.yml:2-36`) [CODE],
so MariaDB must be reachable.

**Still holds in 2024.1:** the `bootstrap_neutron` DB-sync container has no `when`, so it runs on every `reconfigure`
(and `deploy`), run_once on neutron-server[0] (`roles/neutron/tasks/bootstrap.yml:38`, `bootstrap_service.yml:2-21`).
`neutron_enable_rolling_upgrade` (`roles/neutron/defaults/main.yml:732`) is read only by `upgrade.yml:5, :8`. The
container runs `neutron-db-manage --subproject neutron upgrade head`, then the same for each enabled subproject in
`NEUTRON_BOOTSTRAP_SERVICES` (kolla `docker/neutron/neutron-server/extend_start.sh:5-13`). **Changed in 2024.1:** the
subproject list gains neutron-fwaas (`enable_neutron_fwaas`) and tap-as-a-service (`enable_neutron_taas`), next to
networking-sfc, neutron-dynamic-routing, neutron-vpnaas and vmware-nsx (`roles/neutron/defaults/main.yml:674-686,
:727`); both flags default to `no` (`group_vars/all.yml:814, :822`). What a no-op `upgrade head` does to a running
neutron-server is [NOT AVAILABLE].

## 3. What restarts [CODE]

| Change | Restarted | Source |
|---|---|---|
| `/etc/kolla/config/neutron/ml2_conf.ini` (meant for the server) | neutron_server only (controllers), plus neutron_infoblox_ipam_agent where enabled; through loop-notify in the check step, also the other neutron containers of a host that runs neutron-server. **Still holds in 2024.1:** `openvswitch_agent.ini` and `linuxbridge_agent.ini` do not merge `ml2_conf.ini`, so the agents on computes and network nodes do not restart | `roles/neutron/tasks/config.yml:159-179, :181-213`; `roles/neutron/tasks/check-containers.yml:2-19`; [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) |
| `/etc/kolla/config/neutron/openvswitch_agent.ini` | neutron_openvswitch_agent on all computes and network nodes | `roles/neutron/tasks/config.yml:198-213` |
| `/etc/kolla/config/neutron.conf` (also `global.conf`, `neutron/<host>/neutron.conf`) | every neutron container on every host (all but neutron_tls_proxy render `neutron.conf`) | `roles/neutron/tasks/config.yml:87-122` |
| `/etc/kolla/config/neutron/<service>.conf`, e.g. `neutron/neutron-openvswitch-agent.conf` | that container only, on every host that runs it | `roles/neutron/tasks/config.yml:112` |
| Files in `/etc/kolla/config/neutron/plugins/` | neutron_server, and neutron_openvswitch_agent or neutron_linuxbridge_agent on every host that runs one, computes included | `roles/neutron/tasks/config.yml:15-21, :485-506` |
| **New in 2024.1:** `/etc/kolla/config/neutron/fwaas_driver.ini`, with `enable_neutron_fwaas` | neutron_server and neutron_l3_agent (no per-host override file) | `roles/neutron/tasks/config.yml:327-347` |
| **New in 2024.1:** `/etc/kolla/config/neutron/neutron_taas.conf` (or `neutron/<host>/neutron_taas.conf`), with `enable_neutron_taas` | neutron_server and neutron_openvswitch_agent, so every compute | `roles/neutron/tasks/config.yml:526-547` |
| **New in 2024.1:** turning `enable_neutron_fwaas` or `enable_neutron_taas` on or off | every container that renders `neutron.conf` (its `service_plugins` gains `firewall_v2` or `taas`); TaaS also adds `taas` to the Open vSwitch agent `extensions`, FWaaS adds `fwaas_v2` to the L3 agent `extensions`; the next `bootstrap_neutron` migrates the subproject ([§2](#2-execution-and-targets)) | `roles/neutron/defaults/main.yml:745-775, :791-813`; `roles/neutron/templates/neutron.conf.j2:49`, `openvswitch_agent.ini.j2:9-10`, `l3_agent.ini.j2:17-18` |
| **Changed in 2024.1:** `/etc/kolla/config/neutron/neutron_vpnaas.conf` | neutron_server and neutron_l3_agent, now only with `enable_neutron_vpnaas`; without it the file is no longer rendered or passed on the command line, and no task removes a copy written earlier | `roles/neutron/tasks/config.yml:124-145`; `roles/neutron/templates/neutron-server.json.j2:2`, `neutron-l3-agent-wrapper.sh.j2:16-20` |
| RabbitMQ/memcached membership change | every neutron container that renders `neutron.conf` (transport URLs, memcached list) | `group_vars/all.yml:248, :258`; `roles/neutron/templates/neutron.conf.j2:58, :123, :126`; [Change control-plane membership §2](change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller) |

**First run of the 2024.1 code on configs rendered by 2023.1** [CODE]: `neutron.conf` changes for every container
that renders it, because `dns_domain = {{ neutron_dns_domain }}` (default `openstacklocal`) is now written
unconditionally (2023.1 wrote it only with Designate) and because RabbitMQ quorum queues are on by default
([F17](../reference/findings.md#f17)) (`roles/neutron/templates/neutron.conf.j2:64, :146-155`,
`roles/neutron/defaults/main.yml:958`, `group_vars/all.yml:268`). Without VPNaaS, the neutron-server command and the L3
agent wrapper also change ([§3 row `neutron_vpnaas.conf`](#3-what-restarts-code)). And the systemd unit of a container
written by 2023.1 is reported as drift at its first 2024.1 check ([F16](../reference/findings.md#f16)). Every neutron
container on every host of the play can therefore restart on that run.

**Handlers, still hold in 2024.1:** one `recreate_or_restart_container` handler per container, skipped when
`kolla_action` is `config`; only the module name changed (`kolla_container`) (`roles/neutron/handlers/main.yml:1-341`).
The L3 agent handler is a chain: container facts, a `group_by` on whether `neutron_l3_agent` runs, start of the stopped
ones, a wait of `neutron_l3_agent_failover_delay` when both kinds exist, then the running ones
(`roles/neutron/handlers/main.yml:90-157`). For the running ones, each host loops over the list of hosts with a running
L3 agent and restarts only on its own item, with a pause of `neutron_l3_agent_failover_delay` seconds (default `0`,
`roles/neutron/defaults/main.yml:651`) before every item but the first (`handlers/main.yml:136-157`; ansible-core
`lib/ansible/executor/task_executor.py:318-322`). With the default `0` nothing spaces the restarts.

## 4. Impact on networking

| Component | On restart (code-guaranteed when drift) | Effect on existing connectivity (environment-dependent) |
|---|---|---|
| neutron-server | API unavailable during the stop/start, on all controllers at once (no `serial` unless `ANSIBLE_SERIAL` is set, `site.yml:686`) | [NOT AVAILABLE] Whether existing traffic is unaffected, and whether port bindings and new instances fail during the window |
| neutron-openvswitch-agent | container stop/start | [NOT AVAILABLE] Whether flows in OVS persist while the agent is down, whether and how the agent resyncs and re-installs flows on start with the 2024.1 defaults, and whether a VM loses packets during the agent restart |
| neutron-l3-agent | stop/start; with `enable_neutron_agent_ha: yes` the wrapper runs `neutron-netns-cleanup --force --agent-type l3` **before** the agent starts (the wrapper's comment: "Remove all l3 related netns"), with `fwaas_driver.ini` added when FWaaS is enabled (`neutron-l3-agent-wrapper.sh.j2:5-14`) | [CODE] Without the HA cleanup nothing in the wrapper deletes namespaces, and `/run/netns` is shared with the host (`roles/neutron/defaults/main.yml:514-523`). [NOT AVAILABLE] Whether the namespaces then persist, whether keepalived/haproxy child processes die with the container, whether with the cleanup all routers on that node lose N-S/FIP connectivity until rebuilt, and whether HA routers fail over. [NOT AVAILABLE] What the cleanup command deletes: it is neutron code, which is not in these sources ([F12](../reference/findings.md#f12)) |
| neutron-dhcp-agent | stop/start | [NOT AVAILABLE] Whether dnsmasq processes die with the container, whether VMs renewing leases in the window fail to renew, and whether new ports wait for the agent to come back |
| neutron-metadata-agent | stop/start | [NOT AVAILABLE] Whether metadata requests (cloud-init) fail during the window |
| Open vSwitch | **not touched** by `-t neutron` (separate play/tag, `site.yml:611-624`) | – |
| OVN (if `neutron_plugin_agent: ovn`) | `-t neutron` touches neutron-server and `neutron-ovn-metadata-agent` (plus `neutron_ovn_agent` with `neutron_enable_ovn_agent`, default `no`, `group_vars/all.yml:1119`). `-t ovn` runs both the `ovn-controller` and the `ovn-db` plays (`site.yml:641-653, :655-669`). The `ovn-controller` role, unchanged in 2024.1, re-applies `br-int` and 9 `external_ids` keys on every ovn-controller host, including `ovn-cms-options`, through the `openvswitch_bridge`/`openvswitch_db` modules (`roles/ovn-controller/tasks/setup-ovs.yml:2-40`); whether those report changed on an unchanged host is [NOT AVAILABLE] (the modules are not in these sources) ([OVN](../components/ovn.md)) | ovn-controller restart is not triggered by `-t neutron` |

## 5. Risks and verification

- **Risks:** [R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6), [R7](../risk/risk-register.md#r7).
- **Before:**
  - `openstack network agent list` (all alive);
  - identify the network nodes that host HA router masters;
  - render with `genconfig -t neutron` and diff `openvswitch_agent.ini` and `neutron.conf` on a compute (and
    `neutron_taas.conf` with TaaS). If one changed, **every compute will restart its agent**;
  - on the first run of the 2024.1 code, expect `neutron.conf` to change everywhere ([§3](#3-what-restarts-code));
  - expect the `bootstrap_neutron` DB-sync container on neutron-server[0] even with no change
    ([§2](#2-execution-and-targets)).
- **Apply:** network nodes one by one (`--limit network01`, then `network02`). Computes in batches.
- **After:**
  - agent list;
  - `ip netns` count on network nodes matches the number of routers/networks;
  - ping a VM's floating IP continuously during each batch.

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R5](../risk/risk-register.md#r5)
  (`ml2_conf.ini` override meant for neutron-server; in 2024.1 it still does not reach the agents,
  [§3](#3-what-restarts-code)), [R6](../risk/risk-register.md#r6) (restart of `neutron_l3_agent` with
  `enable_neutron_agent_ha: yes`) and [R7](../risk/risk-register.md#r7) (`openvswitch_vswitchd` restart or recreate)
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
