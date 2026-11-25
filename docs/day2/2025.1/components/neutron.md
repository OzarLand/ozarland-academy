---
title: Neutron
description: "Where the 2025.1 study covers Neutron: Linux Bridge removed, restarts limited to changed agents, first-run recreates, L3 agent HA and upgrade traps."
tags: [neutron, reconfigure, upgrade, limit, one-shot, risk, dependencies, bugs, unknowns]
---

# Neutron

This page is the starting point for Neutron, the `neutron` role: `neutron_server` and fourteen other containers (the
agents, `ironic_neutron_agent` and `neutron_tls_proxy`, `roles/neutron/defaults/main.yml:2-209`), on the compute,
control and network nodes of the example inventory, selected by the tag `neutron`. The neutron play includes every
compute and `manila-share` (`site.yml:669-691`). Open vSwitch is not touched by `-t neutron`: it has a separate play
and tag, which in 2025.1 runs before the nova and neutron plays (`site.yml:605-619`; [Open vSwitch](openvswitch.md);
[Reconfigure Neutron](../operations/reconfigure-neutron.md)). `common` is not run by `-t neutron`: it is its own play,
tagged `common` (`site.yml:88-103`).

**Changed in 2025.1** [CODE]:

- **Linux Bridge is gone.** The `neutron-linuxbridge-agent` service, its template, handler and the `linuxbridge`
  branch of `neutron.conf` are removed (`roles/neutron/defaults/main.yml:2-209`, `roles/neutron/tasks/config.yml:73-104`;
  release note `remove-neutron-linuxbridge-b1a2457e848709f7.yaml`). No task of the 2025.1 tree mentions `linuxbridge`
  any more (a search of `ansible/`), so a cloud still on `neutron_plugin_agent: linuxbridge` gets no Linux Bridge agent
  and no precheck message. [NOT AVAILABLE] What such a run does to the existing `neutron_linuxbridge_agent` container
  and its networks; to be confirmed by the community.
- **Restarts follow the changed containers only.** The config tasks no longer notify, and `check-containers.yml`
  imports `service-check-containers` (`roles/neutron/tasks/check-containers.yml:2-3`), which notifies
  `Restart <service> container` for each changed container. An `ml2_conf.ini` change restarts `neutron_server` only,
  not the other neutron containers of its host ([Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code);
  [F1](../reference/findings.md#f1) no longer holds).
- **The first 2025.1 run recreates most neutron containers**, even with no operator change: every neutron container
  now always mounts `/dev/shm` (2024.1 only with `om_enable_queue_manager`, default `false`), the DHCP and L3 agents
  get new environment variables (`KOLLA_IMAGE`, `KOLLA_NAME`, `KOLLA_NEUTRON_WRAPPERS`) and an explicit
  `cgroupns_mode`, and the metadata agent's healthcheck is now off by default
  (`neutron_metadata_agent_enable_healthchecks: "no"`) (`roles/neutron/defaults/main.yml:54-90`,
  `roles/neutron/defaults/main.yml:366-377`, `roles/neutron/defaults/main.yml:483-599`). `neutron.conf` changes too:
  the queue settings are unconditional (`roles/neutron/templates/neutron.conf.j2:131-144`;
  [F17](../reference/findings.md#f17)), `www_authenticate_uri` points to the public Keystone URL (`:106`), and the
  booleans are written in lower case. Add the unit text of [F16](../reference/findings.md#f16).
- **Physical network names:** `ml2_conf.ini` and `openvswitch_agent.ini` take them from `neutron_physical_networks`
  (default `physnet1`, `physnet2`, … per bridge, `group_vars/all.yml:1215`). With the defaults the flat networks and
  bridge mappings are unchanged, but `network_vlan_ranges`, hard-coded `physnet1` in 2024.1, now lists one name per
  bridge (`roles/neutron/templates/ml2_conf.ini.j2:18`, `:27`; `roles/neutron/templates/openvswitch_agent.ini.j2:18-19`).
- **Agent wrappers, new and off by default:** with `neutron_agents_wrappers: "yes"` (default `"no"`,
  `roles/neutron/defaults/main.yml:646`) the DHCP and L3 agents run dnsmasq, haproxy, keepalived and radvd in child
  containers through the container engine socket, with `pid_mode: host` and `cgroupns_mode: host`
  (`roles/neutron/defaults/main.yml:54-90`, `:483-507`; kolla `docker/neutron/neutron-l3-agent/extend_start.sh:31-37`),
  and the L3 wrapper skips `neutron-netns-cleanup` (`roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:5-16`).
- **ML2/OVN:** neutron-server keeps talking to the SB cluster (`ovn_sb_connection_no_relay`,
  `roles/neutron/templates/ml2_conf.ini.j2:40`), while the OVN metadata and OVN agents follow the new SB relays
  ([OVN](ovn.md)).
- **Upgrade:** `upgrade.yml` no longer re-runs the Keystone registration; the `service` role grant is done by
  `register.yml` on deploy and reconfigure (`roles/neutron/tasks/upgrade.yml:1-8`,
  `roles/neutron/tasks/register.yml:2-8`, `roles/neutron/defaults/main.yml:898-901`).
- **Still holds in 2025.1:** `bootstrap_neutron` on every deploy and reconfigure ([F5](../reference/findings.md#f5));
  the L3 agent handler chain with `neutron_l3_agent_failover_delay` (`roles/neutron/handlers/main.yml:67-134`); the
  ML2 plugin check at the start of deploy and upgrade (`roles/neutron/tasks/deploy.yml:2`,
  `roles/neutron/tasks/upgrade.yml:2`).

The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure Neutron](../operations/reconfigure-neutron.md)
- **Command:** [Reconfigure Neutron §1.1](../operations/reconfigure-neutron.md#11-neutron)
- **Batches:** `reconfigure` cannot be batched in 2025.1; use `deploy -t neutron -e kolla_serial=N` or
  `--limit` ([F19](../reference/findings.md#f19); [Write config first, apply in controlled batches
  §1.2](../operations/controlled-batches.md#12-rolling-runs-with-kolla_serial-not-with-reconfigure))

### Impact and risk

- **What the tag executes (`neutron`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `neutron`
- **Risks:** [R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6), [R7](../risk/risk-register.md#r7);
  membership changes: [R3](../risk/risk-register.md#r3), [R4](../risk/risk-register.md#r4)
- **First 2025.1 run after 2024.1:** [Reconfigure Neutron §3](../operations/reconfigure-neutron.md#3-what-restarts-code),
  paragraph "First run of the 2025.1 code"; [F16](../reference/findings.md#f16), [F17](../reference/findings.md#f17)

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services), [Component dependencies
  §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional)
- **Metadata path, changed in 2025.1:** the metadata agents send instance requests to `nova_internal_fqdn` on
  `nova_metadata_port` (`roles/neutron/templates/metadata_agent.ini.j2:4-5`), which HAProxy now forwards to the new
  `nova_metadata` container ([Nova](nova.md))

### Evidence

- **Fact sheet:** –
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `neutron-server`),
  [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour), [Kolla images
  §5.3](../concepts/kolla-images.md#53-neutron-l3-agent-the-wrapper)
- **Also:** [Reconfigure Neutron](../operations/reconfigure-neutron.md); handlers: [Tags
  §5](../risk/tags.md#5-role--handler-map-core-services); the container module: [Repository architecture
  §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 5 (health gates): before the run, check
  `openstack compute service list` and `openstack network agent list` all up. Repeat after each batch.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `neutron`:
  safe on its own "risky without batching" ([R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6));
  prerequisites: Open vSwitch or OVN running, MariaDB, RabbitMQ, Keystone.
- **Agents on computes, still holds in 2025.1** [CODE]: with the default `neutron_plugin_agent: "openvswitch"`
  (`group_vars/all.yml:332`), every compute runs `neutron_openvswitch_agent` (`roles/neutron/defaults/main.yml:30-53`).
  With `enable_neutron_dvr` (default `no`, `group_vars/all.yml:931`) computes also run `neutron_l3_agent` and
  `neutron_metadata_agent` (`roles/neutron/defaults/main.yml:81-84`, `roles/neutron/defaults/main.yml:120-124`); with
  SR-IOV or Mellanox enabled, the `neutron_sriov_agent`, `neutron_mlnx_agent` and `neutron_eswitchd` containers run on
  computes only (`roles/neutron/defaults/main.yml:91-114`).
- [R5](../risk/risk-register.md#r5), narrower in 2025.1: an `ml2_conf.ini` override reaches only `neutron_server` (and
  `neutron_infoblox_ipam_agent`), and only that container restarts (`roles/neutron/tasks/config.yml:134-150`); put agent
  options in `neutron/openvswitch_agent.ini` (`roles/neutron/tasks/config.yml:152-164`) and check the rendered diff.
- [R6](../risk/risk-register.md#r6), precautions for any restart of `neutron_l3_agent` with
  `enable_neutron_agent_ha: yes`: restart network nodes one at a time; fail routers over first. The handler chain is
  unchanged apart from the container facts call and the new `pid_mode`/`cgroupns_mode` options: stopped L3 agents are
  started first, then each host loops over the hosts with a running L3 agent and restarts its own container on its own
  item, with a pause of `neutron_l3_agent_failover_delay` seconds (default `0`) between items
  (`roles/neutron/handlers/main.yml:67-134`, `roles/neutron/defaults/main.yml:626`; ansible-core 2.18.20
  `lib/ansible/executor/task_executor.py:329-331`) [CODE]. Only the hosts where the L3 agent's check reported a change
  run the chain.
- [R3](../risk/risk-register.md#r3), precautions for a change of RabbitMQ group membership, password or port: plan as a
  maintenance; batch with `--limit`; verify RabbitMQ cluster health first.
- [R4](../risk/risk-register.md#r4), precautions for a change of memcached membership: plan as a dataplane change, like
  R3: batch with `--limit` or `deploy -e kolla_serial=N`, network nodes one at a time; low-traffic window. Every
  container that renders `neutron.conf` carries the memcached list (`roles/neutron/templates/neutron.conf.j2:121`).
- [R12](../risk/risk-register.md#r12), precautions for changing `openstack_tag` / `*_tag` and running `deploy` instead
  of `upgrade`: use `pull` then `upgrade`; per-service tags. `upgrade` cannot be batched in 2025.1
  ([F19](../reference/findings.md#f19)).
- [Reconfigure Neutron §2](../operations/reconfigure-neutron.md#2-execution-and-targets), still holds in 2025.1: the
  bootstrap step always runs the Neutron DB and user/grant tasks (skipped only with `use_preconfigured_databases`) and
  the `bootstrap_neutron` DB-sync container on neutron-server[0] on every `deploy` and `reconfigure`
  (`roles/neutron/tasks/bootstrap.yml:2-38`, `roles/neutron/tasks/bootstrap_service.yml:2-21`, no `when`) [CODE], so
  MariaDB must be reachable.
- **Host settings, still hold in 2025.1:** the L3-host `gc_thresh` sysctl values go through the `sysctl` role
  (`roles/neutron/tasks/config-host.yml:20-34`, `roles/sysctl/tasks/main.yml:1-20`); the role's own `Check IPv6
  support` task still runs on every host, and no task reads its result (`roles/neutron/tasks/config-host.yml:15-18`).
  The kernel-module step now covers L3 and Open vSwitch agent hosts only (`roles/neutron/tasks/config-host.yml:2-13`)
  [CODE].
- **FWaaS and TaaS, still hold in 2025.1:** `enable_neutron_fwaas` and `enable_neutron_taas` (both default `no`,
  `group_vars/all.yml:932, :940`) add `fwaas_driver.ini` (neutron-server and L3 agents) and `neutron_taas.conf`
  (neutron-server and the Open vSwitch agents, so every compute) (`roles/neutron/tasks/config.yml:254-270`,
  `roles/neutron/tasks/config.yml:411-428`), a service plugin in `neutron.conf` (`roles/neutron/defaults/main.yml:720-750`,
  `roles/neutron/templates/neutron.conf.j2:47`) and a subproject that `bootstrap_neutron` migrates
  (`roles/neutron/defaults/main.yml:651-663`, `roles/neutron/defaults/main.yml:702`) [CODE]. Turning either on
  restarts every neutron container that renders `neutron.conf` ([Reconfigure Neutron
  §3](../operations/reconfigure-neutron.md#3-what-restarts-code)).
- **DNS domain, still holds:** `neutron.conf` always renders `dns_domain = {{ neutron_dns_domain }}` (default
  `openstacklocal`) (`roles/neutron/templates/neutron.conf.j2:62`, `roles/neutron/defaults/main.yml:933`); the precheck
  that rejects an empty domain, one without a final `.` or `openstacklocal` when DNS integration is on runs only in
  `prechecks` (`roles/neutron/tasks/precheck.yml:58-69`) [CODE].
- [Reconfigure Neutron §5](../operations/reconfigure-neutron.md#5-risks-and-verification), verification: before,
  `openstack network agent list` (all alive), identify the network nodes that host HA router masters, and render with
  `genconfig -t neutron` and diff `openvswitch_agent.ini` and `neutron.conf` on a compute (if either changed, every
  compute will restart its agent). Apply: network nodes one by one (`--limit network01`, then `network02`), computes
  in batches. After: the agent list, an `ip netns` count on network nodes that matches the number of routers/networks,
  and a continuous ping of a VM's floating IP during each batch.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `neutron`. **Still holds in
  2025.1:** `upgrade` with the default `neutron_enable_rolling_upgrade: "yes"` expands/contracts `neutron` plus every
  enabled subproject of `neutron_subprojects`, the same list the bootstrap container migrates
  (`roles/neutron/defaults/main.yml:651-663, :702, :707-708`). The `has_offline_migrations` check loops over the
  enabled subprojects only, never `neutron` itself: any non-zero rc (or a failed `exec`, `ignore_errors`) stops
  `neutron_server` on every neutron-server host in the play until the handler flush after the contract container, and
  with no subproject enabled no server is stopped before `upgrade --contract`
  (`roles/neutron/tasks/rolling_upgrade.yml:38-89`) [CODE]. Impact on the Neutron API, and whether a neutron contract
  migration is safe against running servers: [NOT AVAILABLE] ([Kolla images
  §6](../concepts/kolla-images.md#6-day-2-consequences), item 8).
- **New in 2025.1, the ML2 plugin check misses one case** [CODE]: the container facts module now returns its results
  under `containers` and `volumes`, and the "Check for ML2/OVN presence" condition reads the OVN DB volumes at the top
  level of the result (`container_volume_facts['ovn_nb_db']`), which no longer exists; the ML2/OVS check reads them
  under `volumes` (`roles/neutron/tasks/neutron_plugin_agent_check.yml:13-37`;
  `library/kolla_container_facts.py:177-185`). On a host with the OVN DB volumes but no `ovn_controller` container,
  the OVN check therefore does not fire. [NOT AVAILABLE] Whether this matters on a real host; to be confirmed by the
  community.
- [Q2](../troubleshooting/open-questions.md#q2): "Data-plane loss during a `neutron_openvswitch_agent` restart". Status:
  [NOT AVAILABLE].
- [Q4](../troubleshooting/open-questions.md#q4): "L3 agent restart with and without `enable_neutron_agent_ha`". Status:
  [NOT AVAILABLE].
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: neutron-server's `KOLLA_BOOTSTRAP`
  and `KOLLA_UPGRADE` branches both migrate `neutron`, then each subproject passed in `NEUTRON_BOOTSTRAP_SERVICES` /
  `NEUTRON_ROLLING_UPGRADE_SERVICES`, which are the same enabled-subproject list (kolla
  `docker/neutron/neutron-server/extend_start.sh:5-34`; `roles/neutron/defaults/main.yml:702, :708`); the kolla images
  install `tap-as-a-service` in neutron-base and carry a `neutron-fwaas` plugin source (kolla
  `docker/neutron/neutron-base/Dockerfile.j2:91-95`, kolla `kolla/common/sources.py:220-223`); whether a given built image
  contains them is [NOT AVAILABLE]. Agent, OVS and OVN images have no one-shot branch.
- [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane), group "Network data plane": what the
  sources do not establish about a restart of `neutron_openvswitch_agent`, `neutron_l3_agent`, `neutron_dhcp_agent`,
  `neutron_metadata_agent` and `neutron_server`, about the processes that agent containers spawn (and, new in 2025.1,
  the child containers of the agent wrappers), and about a change of `neutron_legacy_iptables`.
- [What is not known](../troubleshooting/what-is-not-known.md#upgrades-and-database-migrations): the sources do not
  establish whether `neutron-db-manage … upgrade head`, run by a tag change applied with `deploy`, applies contract
  migrations under live old-version servers, and what that does to them.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish whether services started by a shell wrapper that does not `exec` them (`neutron-l3-agent`
  among them, `roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:18-22`) receive SIGTERM at all before the
  container stops.
- [Update container images §4](../operations/update-container-images.md#4-risks): with a tag change applied by `deploy`
  instead of `upgrade`, `bootstrap_neutron` runs `neutron-db-manage … upgrade head` with the new image before the
  handlers restart the old `neutron_server` containers (`roles/neutron/tasks/deploy.yml:13-23`) [CODE].
- [F1](../reference/findings.md#f1), "Loop-notify amplification": **no longer holds in 2025.1** [CODE]; a change on a
  network node restarts only the agents whose own files or definition changed.
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": still holds: `reconfigure.yml` imports `deploy.yml`,
  and `bootstrap_neutron` has no `when`, so a reconfigure re-runs Neutron's DB create/grant tasks **and** its DB sync;
  `neutron_enable_rolling_upgrade` is read only by `upgrade.yml` (`roles/neutron/tasks/reconfigure.yml:2`,
  `roles/neutron/tasks/upgrade.yml:4-8`, `roles/neutron/tasks/bootstrap_service.yml:2-21`) [CODE].
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files; `neutron.conf`,
  with the transport URLs and the memcached list, is rendered for the Open vSwitch agent too
  (`roles/neutron/templates/neutron.conf.j2:56, :121, :124`, `roles/neutron/tasks/config.yml:73-104`) [CODE].
- [F8](../reference/findings.md#f8), "`--limit` does not confine actions": with `deploy --limit` set to a compute host,
  `control01` runs the Neutron DB create/grant and the `bootstrap_neutron` container
  (`roles/neutron/tasks/bootstrap.yml:13-14, :33-34`, `roles/neutron/tasks/bootstrap_service.yml:20-21`) [CODE].
- [F11](../reference/findings.md#f11), "The `openvswitch_agent.ini` merge": **no longer applies**. The merge reads only
  `openvswitch_agent.ini.j2` and the `neutron/openvswitch_agent.ini` overrides, and `ml2_conf.ini` is rendered only for
  neutron-server and neutron-infoblox-ipam-agent (`roles/neutron/tasks/config.yml:134-164`) [CODE].
- [F12](../reference/findings.md#f12), "The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at
  start" when `enable_neutron_agent_ha: yes`; **changed in 2025.1**, not when `neutron_agents_wrappers` is on
  (`roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:5-16`) [CODE]; [NOT AVAILABLE] whether an L3 agent restart
  interrupts router traffic on that node.
- [F13](../reference/findings.md#f13), "The Nova deploy order": **partly no longer holds** [CODE]: Open vSwitch now
  comes before `nova.yml`, the neutron play still after it (`site.yml:605`, `site.yml:667`, `site.yml:669`); [NOT
  AVAILABLE] whether instances can be scheduled on a new compute before the neutron play finishes.
- [F15](../reference/findings.md#f15), "What the bootstrap containers run differs per image": the bootstrap container
  and the rolling `upgrade` migrate the same enabled subprojects (`roles/neutron/defaults/main.yml:651-663, :702, :708`)
  [CODE].
- [Component dependencies §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional), "Runtime
  facts" [CODE]: the L3 agent wrapper runs a namespace cleanup on start (unless the agent wrappers are on);
  `/run/netns` is shared with the host (`roles/neutron/defaults/main.yml:488`, `:501`, `:543`).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 8 and 12: the contract-step traps of the
  Neutron upgrade [CODE]; the L3 agent wrapper does not `exec` the agent, and [NOT AVAILABLE] whether SIGTERM then
  reaches only bash, so that the agent is killed without a graceful shutdown.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py neutron -->

| Item | Value |
|---|---|
| Play | site.yml:669 |
| Tags | neutron |
| Play host patterns | neutron-server, neutron-dhcp-agent, neutron-l3-agent, ironic-neutron-agent, neutron-metadata-agent, neutron-ovn-metadata-agent, neutron-metering-agent, neutron-bgp-dragent, neutron-infoblox-ipam-agent, compute, manila-share |
| Node types in play (example inventory) | compute, control, network |
| Node types running its containers | compute, control, network |
| Containers | `neutron_server`, `neutron_openvswitch_agent`, `neutron_dhcp_agent`, `neutron_l3_agent`, `neutron_sriov_agent`, `neutron_mlnx_agent`, `neutron_eswitchd`, `neutron_metadata_agent`, `neutron_ovn_metadata_agent`, `neutron_bgp_dragent`, `neutron_infoblox_ipam_agent`, `neutron_metering_agent`, `ironic_neutron_agent`, `neutron_tls_proxy`, `neutron_ovn_agent` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | neutron_plugin_agent_check → register → clone (if) → config-host → config → check-containers → config-neutron-fake (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config-host.yml, config-neutron-fake.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, legacy_upgrade.yml, loadbalancer.yml, main.yml, neutron_plugin_agent_check.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, rolling_upgrade.yml, stop.yml, upgrade.yml |
| Templates | `bgp_dragent.ini.j2`, `dhcp_agent.ini.j2`, `dnsmasq.conf.j2`, `eswitchd.conf.j2`, `fwaas_driver.ini.j2`, `ironic-neutron-agent.json.j2`, `ironic_neutron_agent.ini.j2`, `l3_agent.ini.j2`, `metadata_agent.ini.j2`, `metering_agent.ini.j2`, `ml2_conf.ini.j2`, `mlnx_agent.ini.j2`, `neutron-bgp-dragent.json.j2`, `neutron-dhcp-agent.json.j2`, `neutron-eswitchd.json.j2`, `neutron-infoblox-ipam-agent.json.j2`, `neutron-l3-agent-wrapper.sh.j2`, `neutron-l3-agent.json.j2`, `neutron-metadata-agent.json.j2`, `neutron-metering-agent.json.j2`, `neutron-mlnx-agent.json.j2`, `neutron-openvswitch-agent-xenapi.json.j2`, `neutron-openvswitch-agent.json.j2`, `neutron-ovn-agent.json.j2`, `neutron-ovn-metadata-agent.json.j2` … (+12) |
| Handlers (definition order) | Restart neutron-server container; Restart neutron-openvswitch-agent container; Restart fake neutron-openvswitch-agent container; Restart neutron-dhcp-agent container; Get container facts; Group hosts; Start stopped neutron-l3-agent container; Wait if container starting; Restart running neutron-l3-agent container; Restart neutron-sriov-agent container; Restart neutron-mlnx-agent container; Restart neutron-eswitchd container; Restart neutron-tls-proxy container; Restart neutron-metadata-agent container; Restart neutron-ovn-metadata-agent container; Restart neutron-bgp-dragent container; Restart neutron-infoblox-ipam-agent container; Restart neutron-metering-agent container; Restart ironic-neutron-agent container; Restart neutron-ovn-agent container |
| Key variables | `enable_neutron`, `neutron_plugin_agent`, `enable_neutron_dvr`, `enable_neutron_agent_ha`, `enable_neutron_provider_networks`, `neutron_enable_rolling_upgrade` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure Neutron](../operations/reconfigure-neutron.md) — what `-t neutron reconfigure` runs on controllers,
  network nodes and every compute
- [Open vSwitch](openvswitch.md) — `openvswitch_db` and `openvswitch_vswitchd` forward all VM traffic and have their own
  play and tag
- [OVN](ovn.md) — the roles used if `neutron_plugin_agent: ovn`; the SB relays the agents now use
- [Nova](nova.md) — the new `nova_metadata` container behind the metadata agents
- [Change control-plane membership](../operations/change-control-plane-membership.md) — what a controller change
  (RabbitMQ and memcached membership) restarts on computes
- [Update container images §4](../operations/update-container-images.md#4-risks) — what a tag change applied with
  `deploy` runs against the Neutron DB
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the checks before every production run
- [Components](index.md) — the other component pages
