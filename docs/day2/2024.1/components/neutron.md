---
title: Neutron
description: Where the 2024.1 study covers Neutron (role neutron), from the reconfigure commands and agent restart risks to FWaaS, TaaS and the upgrade traps.
tags: [neutron, reconfigure, upgrade, loop-notify, limit, one-shot, risk, dependencies, bugs, unknowns]
---

# Neutron

This page is the starting point for Neutron, the `neutron` role: `neutron_server` and fifteen other containers (the
agents, `ironic_neutron_agent` and `neutron_tls_proxy`, `roles/neutron/defaults/main.yml:2-210`), on the compute,
control and network nodes of the example inventory, selected by the tag `neutron`. The neutron play includes every
compute and `manila-share` (`site.yml:671-693`), and Open vSwitch is not touched by `-t neutron`: it has a separate
play and tag (`site.yml:611-624`; [Reconfigure Neutron](../operations/reconfigure-neutron.md)). `common` is not run by
`-t neutron`: it is its own play, tagged `common` (`site.yml:88-104`). The lists below say where the study covers how
to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open; the
service card follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure Neutron](../operations/reconfigure-neutron.md)
- **Command:** [Reconfigure Neutron §1.1](../operations/reconfigure-neutron.md#11-neutron)

### Impact and risk

- **What the tag executes (`neutron`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `neutron`
- **Risks:** [R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6), [R7](../risk/risk-register.md#r7);
  membership changes: [R3](../risk/risk-register.md#r3), [R4](../risk/risk-register.md#r4)

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services), [Component dependencies
  §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional)

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
- **Agents on computes, still holds in 2024.1** [CODE]: with the default `neutron_plugin_agent: "openvswitch"`
  (`group_vars/all.yml:325`), every compute runs `neutron_openvswitch_agent` (`roles/neutron/defaults/main.yml:26-46`).
  With `enable_neutron_dvr` (default `no`, `group_vars/all.yml:813`) computes also run `neutron_l3_agent` and
  `neutron_metadata_agent` (`roles/neutron/defaults/main.yml:85-89, :122-126`); with SR-IOV or Mellanox enabled, the
  `neutron_sriov_agent`, `neutron_mlnx_agent` and `neutron_eswitchd` containers run on computes only (`:93-114`).
- [R5](../risk/risk-register.md#r5), still narrow in 2024.1: an `ml2_conf.ini` override reaches only `neutron_server`
  (and `neutron_infoblox_ipam_agent`), plus, through loop-notify in the check step, the other neutron containers of a
  host that also runs neutron-server (`roles/neutron/tasks/config.yml:159-179`, `check-containers.yml:2-19`); put agent
  options in `neutron/openvswitch_agent.ini` (`config.yml:198-213`) and check the rendered diff.
- [R6](../risk/risk-register.md#r6), precautions for any restart of `neutron_l3_agent` with
  `enable_neutron_agent_ha: yes`: restart network nodes one at a time; fail routers over first. The handler is
  unchanged in 2024.1 apart from the module name (`kolla_container`): stopped L3 agents are started first, then each
  host loops over the hosts with a running L3 agent and restarts its own container on its own item, with a pause of
  `neutron_l3_agent_failover_delay` seconds (default `0`) between items (`roles/neutron/handlers/main.yml:90-157`,
  `roles/neutron/defaults/main.yml:651`; ansible-core `lib/ansible/executor/task_executor.py:318-322`) [CODE].
- [R3](../risk/risk-register.md#r3), precautions for a change of RabbitMQ group membership, password or port: plan as a
  maintenance; batch with `--limit`; verify RabbitMQ cluster health first.
- [R4](../risk/risk-register.md#r4), precautions for a change of memcached membership: plan as a dataplane change, like
  R3: batch with `--limit` or `ANSIBLE_SERIAL`, network nodes one at a time; low-traffic window.
- [R12](../risk/risk-register.md#r12), precautions for changing `openstack_tag` / `*_tag` and running `deploy` instead
  of `upgrade`: use `pull` then `upgrade`; per-service tags; `ANSIBLE_SERIAL`.
- [Reconfigure Neutron §2](../operations/reconfigure-neutron.md#2-execution-and-targets), still holds in 2024.1: the
  bootstrap step always runs the Neutron DB and user/grant tasks (skipped only with `use_preconfigured_databases`) and
  the `bootstrap_neutron` DB-sync container on neutron-server[0] on every `deploy` and `reconfigure`
  (`roles/neutron/tasks/bootstrap.yml:2-38`, `bootstrap_service.yml:2-21`, no `when`) [CODE], so MariaDB must be
  reachable.
- **Host settings, changed in 2024.1:** the L3-host `gc_thresh` sysctl values now go through the new `sysctl` role,
  which runs its own IPv6 check and skips the `net.ipv6.*` keys when IPv6 is disabled
  (`roles/neutron/tasks/config-host.yml:20-34`, `roles/sysctl/tasks/main.yml:1-20`). The neutron role's own `Check IPv6
  support` task still runs on every host of the play, and no task of the role reads its result any more
  (`config-host.yml:15-18`) [CODE]
  ([Reconfigure Neutron §2](../operations/reconfigure-neutron.md#2-execution-and-targets)).
- **FWaaS and TaaS, new in 2024.1:** `enable_neutron_fwaas` and `enable_neutron_taas` (both default `no`,
  `group_vars/all.yml:814, :822`) add `fwaas_driver.ini` (neutron-server and L3 agents) and `neutron_taas.conf`
  (neutron-server and the Open vSwitch agents, so every compute) (`roles/neutron/tasks/config.yml:327-347, :526-547`),
  a service plugin in `neutron.conf` (`roles/neutron/defaults/main.yml:745-775`, `templates/neutron.conf.j2:49`) and a
  subproject that `bootstrap_neutron` migrates (`defaults/main.yml:674-686, :727`) [CODE]. Turning either on therefore
  restarts every neutron container that renders `neutron.conf` ([Reconfigure Neutron
  §3](../operations/reconfigure-neutron.md#3-what-restarts-code)).
- **DNS domain, changed in 2024.1:** `neutron.conf` always renders `dns_domain = {{ neutron_dns_domain }}` (default
  `openstacklocal`), and `external_dns_driver = designate` only with `enable_designate` and `neutron_dns_integration`
  (default `enable_designate`) (`roles/neutron/templates/neutron.conf.j2:64-76`,
  `roles/neutron/defaults/main.yml:956-958`)
  [CODE]. 2023.1 wrote `dns_domain` only with Designate, from `designate_ns_record`. The new precheck fails when DNS
  integration is on and `neutron_dns_domain` is empty, lacks a final `.` or is `openstacklocal`
  (`roles/neutron/tasks/precheck.yml:57-68`); it runs only in `prechecks`, not in `reconfigure` [CODE].
- [Reconfigure Neutron §5](../operations/reconfigure-neutron.md#5-risks-and-verification), verification: before,
  `openstack network agent list` (all alive), identify the network nodes that host HA router masters, and render with
  `genconfig -t neutron` and diff `openvswitch_agent.ini` and `neutron.conf` on a compute (if either changed, every
  compute will restart its agent). Apply: network nodes one by one (`--limit network01`, then `network02`), computes
  in batches. After: the agent list, an `ip netns` count on network nodes that matches the number of routers/networks,
  and a continuous ping of a VM's floating IP during each batch.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `neutron`. **Still holds in
  2024.1:** `upgrade` with the default `neutron_enable_rolling_upgrade: "yes"` expands/contracts `neutron` plus every
  enabled subproject of `neutron_subprojects`, the same list the bootstrap container migrates; **changed in 2024.1**,
  the list now also holds neutron-fwaas and tap-as-a-service (`roles/neutron/defaults/main.yml:674-686, :727, :733`).
  The `has_offline_migrations` check loops over the enabled subprojects only, never `neutron` itself: any non-zero rc
  (or a failed `exec`, `ignore_errors`) stops `neutron_server` on every neutron-server host in the play until the
  handler flush after the contract container, and with no subproject enabled no server is stopped before
  `upgrade --contract` (`roles/neutron/tasks/rolling_upgrade.yml:38-89`) [CODE]. Impact on the Neutron API, and whether
  a neutron contract migration is safe against running servers: [NOT AVAILABLE] ([Kolla images
  §6](../concepts/kolla-images.md#6-day-2-consequences), item 8).
- **New in 2024.1:** `register` and `upgrade` grant the neutron user the `service` role in the `service` project
  (`roles/neutron/tasks/register.yml:8`, `upgrade.yml:10-15`, `roles/neutron/defaults/main.yml:923-926`,
  `roles/service-ks-register/tasks/main.yml:103-117`) [CODE].
- [Q2](../troubleshooting/open-questions.md#q2): "Data-plane loss during a `neutron_openvswitch_agent` restart". Status:
  [NOT AVAILABLE].
- [Q4](../troubleshooting/open-questions.md#q4): "L3 agent restart with and without `enable_neutron_agent_ha`". Status:
  [NOT AVAILABLE].
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: in 2024.1 neutron-server's
  `KOLLA_BOOTSTRAP` and `KOLLA_UPGRADE` branches both migrate `neutron`, then each subproject passed in
  `NEUTRON_BOOTSTRAP_SERVICES` / `NEUTRON_ROLLING_UPGRADE_SERVICES`, which are the same enabled-subproject list (kolla
  `docker/neutron/neutron-server/extend_start.sh:5-34`; `roles/neutron/defaults/main.yml:727, :733`). **Changed in
  2024.1:** neutron-fwaas is back in the list, and tap-as-a-service is new (`roles/neutron/defaults/main.yml:674-686`);
  the kolla images install `tap-as-a-service` in neutron-base and carry a `neutron-fwaas` plugin source (kolla
  `docker/neutron/neutron-base/Dockerfile.j2:59-63`, `kolla/common/sources.py:224-227`); whether a given built image
  contains them is [NOT AVAILABLE]. Agent, OVS and OVN images have no one-shot branch (no
  `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` in kolla `docker/neutron/*`, `docker/openvswitch/*`, `docker/ovn/*` other than
  neutron-server).
- [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane), group "Network data plane": what the
  sources do not establish about a restart of `neutron_openvswitch_agent`, `neutron_l3_agent`, `neutron_dhcp_agent`,
  `neutron_metadata_agent` and `neutron_server`, about the processes that agent containers spawn, and about a change of
  `neutron_legacy_iptables`.
- [What is not known](../troubleshooting/what-is-not-known.md#upgrades-and-database-migrations): the sources do not
  establish whether `neutron-db-manage … upgrade head`, run by a tag change applied with `deploy`, applies contract
  migrations under live old-version servers, and what that does to them.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish whether services started by a shell wrapper that does not `exec` them (`neutron-l3-agent`
  among them, `roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:16-20`) receive SIGTERM at all before the
  container stops.
- [Update container images §4](../operations/update-container-images.md#4-risks): with a tag change applied by `deploy`
  instead of `upgrade`, `bootstrap_neutron` runs `neutron-db-manage … upgrade head` with the new image before the
  handlers restart the old `neutron_server` containers (`roles/neutron/tasks/deploy.yml:13-23`) [CODE].
- [F1](../reference/findings.md#f1), "Loop-notify amplification": a change on a network node restarts all neutron agents
  there (`roles/neutron/tasks/check-containers.yml:2-19`) [CODE].
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": still holds in 2024.1: `reconfigure.yml` imports
  `deploy.yml`, and `bootstrap_neutron` has no `when`, so a reconfigure re-runs Neutron's DB create/grant tasks **and**
  its DB sync; `neutron_enable_rolling_upgrade` is read only by `upgrade.yml:5, :8`
  (`roles/neutron/tasks/reconfigure.yml:2`, `bootstrap_service.yml:2-21`) [CODE].
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files; `neutron.conf`,
  with the transport URLs and the memcached list, is rendered for the Open vSwitch agent too
  (`roles/neutron/templates/neutron.conf.j2:58, :123, :126`, `roles/neutron/tasks/config.yml:87-122`) [CODE].
- [F8](../reference/findings.md#f8), "`--limit` does not confine actions": with `deploy --limit` set to a compute host,
  `control01` runs the Neutron DB create/grant and the `bootstrap_neutron` container
  (`roles/neutron/tasks/bootstrap.yml:13-14, :33-34`, `bootstrap_service.yml:20-21`) [CODE].
- [F11](../reference/findings.md#f11), "The `openvswitch_agent.ini` merge": **no longer applies, as in 2023.1**. The
  merge reads only `openvswitch_agent.ini.j2` and the `neutron/openvswitch_agent.ini` overrides, and `ml2_conf.ini` is
  rendered only for neutron-server and neutron-infoblox-ipam-agent, so server-side ML2 changes do not restart the OVS
  agents (`roles/neutron/tasks/config.yml:159-179, :198-213`) [CODE].
- [F12](../reference/findings.md#f12), "The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at
  start" when `enable_neutron_agent_ha: yes`; **changed in 2024.1**, the cleanup and the agent also read
  `fwaas_driver.ini` when FWaaS is enabled, and the agent reads `neutron_vpnaas.conf` only when VPNaaS is enabled
  (`roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:5-20`) [CODE]; [NOT AVAILABLE] whether an L3 agent restart
  interrupts router traffic on that node.
- [F13](../reference/findings.md#f13), "The Nova deploy order" puts nova-compute before OVS and the Neutron agents on
  new computes (`site.yml:609` imports `nova.yml` before the openvswitch play at `:611` and the neutron play at `:671`)
  [CODE]; [NOT AVAILABLE] whether instances can be scheduled on such a compute before the later plays finish.
- [F15](../reference/findings.md#f15), "What the bootstrap containers run differs per image": the bootstrap container
  and the rolling `upgrade` migrate the same enabled subprojects, neutron-dynamic-routing included when
  `enable_neutron_bgp_dragent` is set and, new in 2024.1, neutron-fwaas and tap-as-a-service when enabled
  (`roles/neutron/defaults/main.yml:674-686, :727, :733`) [CODE].
- [Component dependencies §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional), "Runtime
  facts" [CODE]: the L3 agent wrapper runs a namespace cleanup on start; `/run/netns` is shared with the host
  (`roles/neutron/defaults/main.yml:514-523`); the OVS bridge layout is set in a post-config step of the `openvswitch`
  role.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 8 and 12: the contract-step traps of the
  Neutron upgrade [CODE]; the L3 agent wrapper does not `exec` the agent, and [NOT AVAILABLE] whether SIGTERM then
  reaches only bash, so that the agent is killed without a graceful shutdown.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py neutron -->

| Item | Value |
|---|---|
| Play | site.yml:671 |
| Tags | neutron |
| Play host patterns | neutron-server, neutron-dhcp-agent, neutron-l3-agent, ironic-neutron-agent, neutron-metadata-agent, neutron-ovn-metadata-agent, neutron-metering-agent, neutron-bgp-dragent, neutron-infoblox-ipam-agent, compute, manila-share |
| Node types in play (example inventory) | compute, control, network |
| Node types running its containers | compute, control, network |
| Containers | `neutron_server`, `neutron_openvswitch_agent`, `neutron_linuxbridge_agent`, `neutron_dhcp_agent`, `neutron_l3_agent`, `neutron_sriov_agent`, `neutron_mlnx_agent`, `neutron_eswitchd`, `neutron_metadata_agent`, `neutron_ovn_metadata_agent`, `neutron_bgp_dragent`, `neutron_infoblox_ipam_agent`, `neutron_metering_agent`, `ironic_neutron_agent`, `neutron_tls_proxy`, `neutron_ovn_agent` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | neutron_plugin_agent_check → register → clone (if) → config-host → config → check-containers → config-neutron-fake (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config-host.yml, config-neutron-fake.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, legacy_upgrade.yml, loadbalancer.yml, main.yml, neutron_plugin_agent_check.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, rolling_upgrade.yml, stop.yml, upgrade.yml |
| Templates | `bgp_dragent.ini.j2`, `dhcp_agent.ini.j2`, `dnsmasq.conf.j2`, `eswitchd.conf.j2`, `fwaas_driver.ini.j2`, `ironic-neutron-agent.json.j2`, `ironic_neutron_agent.ini.j2`, `l3_agent.ini.j2`, `linuxbridge_agent.ini.j2`, `metadata_agent.ini.j2`, `metering_agent.ini.j2`, `ml2_conf.ini.j2`, `mlnx_agent.ini.j2`, `neutron-bgp-dragent.json.j2`, `neutron-dhcp-agent.json.j2`, `neutron-eswitchd.json.j2`, `neutron-infoblox-ipam-agent.json.j2`, `neutron-l3-agent-wrapper.sh.j2`, `neutron-l3-agent.json.j2`, `neutron-linuxbridge-agent.json.j2`, `neutron-metadata-agent.json.j2`, `neutron-metering-agent.json.j2`, `neutron-mlnx-agent.json.j2`, `neutron-openvswitch-agent-xenapi.json.j2`, `neutron-openvswitch-agent.json.j2` … (+14) |
| Handlers (definition order) | Restart neutron-server container; Restart neutron-openvswitch-agent container; Restart fake neutron-openvswitch-agent container; Restart neutron-linuxbridge-agent container; Restart neutron-dhcp-agent container; Get container facts; Group hosts; Start stopped neutron-l3-agent container; Wait if container starting; Restart running neutron-l3-agent container; Restart neutron-sriov-agent container; Restart neutron-mlnx-agent container; Restart neutron-eswitchd container; Restart neutron-tls-proxy container; Restart neutron-metadata-agent container; Restart neutron-ovn-metadata-agent container; Restart neutron-bgp-dragent container; Restart neutron-infoblox-ipam-agent container; Restart neutron-metering-agent container; Restart ironic-neutron-agent container; Restart neutron-ovn-agent container |
| Key variables | `enable_neutron`, `neutron_plugin_agent`, `enable_neutron_dvr`, `enable_neutron_agent_ha`, `enable_neutron_provider_networks`, `neutron_enable_rolling_upgrade` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure Neutron](../operations/reconfigure-neutron.md) — what `-t neutron reconfigure` runs on controllers,
  network nodes and every compute
- [Open vSwitch](openvswitch.md) — `openvswitch_db` and `openvswitch_vswitchd` forward all VM traffic and have their own
  play and tag
- [OVN](ovn.md) — the roles used if `neutron_plugin_agent: ovn`
- [Change control-plane membership](../operations/change-control-plane-membership.md) — in the default inventory a
  controller change (RabbitMQ and memcached membership) restarts all nova and neutron containers on all computes; a
  `memcached`-only change still restarts the neutron agents on computes
- [Update container images §4](../operations/update-container-images.md#4-risks) — what a tag change applied with
  `deploy` runs against the Neutron DB
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the checks before every production run
- [Components](index.md) — the other component pages
