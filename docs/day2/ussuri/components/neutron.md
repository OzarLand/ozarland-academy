---
title: Neutron
description: Where the study covers Neutron (role neutron), from the reconfigure commands and the agent restart risks to the upgrade gaps and what stays open.
tags: [neutron, reconfigure, upgrade, loop-notify, limit, one-shot, risk, dependencies, bugs, unknowns]
---

# Neutron

This page is the starting point for Neutron, the `neutron` role: `neutron_server` and twelve agent containers, on the
compute, control and network nodes of the example inventory, selected by the tag `neutron`. The neutron play includes
every compute, and Open vSwitch is not touched by `-t neutron`: it has a separate play and tag ([Reconfigure
Neutron](../operations/reconfigure-neutron.md)). The lists below say where the study covers how to operate it, its
impact, its dependencies and the evidence, what to check around a run and what stays open; the service card follows
them.

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
  §5](../risk/tags.md#5-role--handler-map-core-services)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 5 (health gates): before the run, check
  `openstack compute service list` and `openstack network agent list` all up. Repeat after each batch.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `neutron`:
  safe on its own "risky without batching" ([R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6));
  prerequisites: Open vSwitch or OVN running, MariaDB, RabbitMQ, Keystone.
- [R5](../risk/risk-register.md#r5), precautions for an `ml2_conf.ini` override: put server-only options in
  `neutron/neutron-server.conf`, or check the rendered `openvswitch_agent.ini` diff.
- [R6](../risk/risk-register.md#r6), precautions for any restart of `neutron_l3_agent` with
  `enable_neutron_agent_ha: yes`: restart network nodes one at a time; fail routers over first.
- [R3](../risk/risk-register.md#r3), precautions for a change of RabbitMQ group membership, password or port: plan as a
  maintenance; batch with `--limit`; verify RabbitMQ cluster health first.
- [R4](../risk/risk-register.md#r4), precautions for a change of memcached membership: plan as a dataplane change, like
  R3/R5: batch with `--limit` or `ANSIBLE_SERIAL`, network nodes one at a time; low-traffic window.
- [R12](../risk/risk-register.md#r12), precautions for changing `openstack_tag` / `*_tag` and running `deploy` instead
  of `upgrade`: use `pull` then `upgrade` (Ussuri docs); per-service tags; `ANSIBLE_SERIAL`.
- [Reconfigure Neutron §2](../operations/reconfigure-neutron.md#2-execution-and-targets): the bootstrap step always runs
  the Neutron DB and user/grant tasks (skipped only with `use_preconfigured_databases`) [CODE], so MariaDB must be
  reachable.
- [Reconfigure Neutron §5](../operations/reconfigure-neutron.md#5-risks-and-verification), verification: before,
  `openstack network agent list` (all alive), identify the network nodes that host HA router masters, and render with
  `genconfig -t neutron` and diff `openvswitch_agent.ini` on a compute (if it changed, every compute will restart its
  agent). Apply: network nodes one by one (`--limit network01`, then `network02`), computes in batches. After: the agent
  list, an `ip netns` count on network nodes that matches the number of routers/networks, and a continuous ping of a
  VM's floating IP during each batch.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `neutron`: `upgrade` with the
  default `neutron_enable_rolling_upgrade: "yes"` expands/contracts only `neutron`, `neutron-fwaas` and
  `neutron-vpnaas`, so `neutron-dynamic-routing` is never migrated by `upgrade`; any non-zero rc of
  `has_offline_migrations` stops `neutron_server` on every neutron-server host in the play until the handler flush after
  the contract container. Status: [CODE]; impact on the Neutron API [NOT AVAILABLE].
- [Q2](../troubleshooting/open-questions.md#q2): "Data-plane loss during a `neutron_openvswitch_agent` restart". Status:
  [NOT AVAILABLE].
- [Q4](../troubleshooting/open-questions.md#q4): "L3 agent restart with and without `enable_neutron_agent_ha`". Status:
  [NOT AVAILABLE].
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: neutron-server's `KOLLA_BOOTSTRAP`
  migrates neutron, -dynamic-routing, -fwaas and -vpnaas; the rolling upgrade list omits -dynamic-routing. Agent, OVS
  and OVN images have no one-shot branch.
- [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane), group "Network data plane": what the
  sources do not establish about a restart of `neutron_openvswitch_agent`, `neutron_l3_agent`, `neutron_dhcp_agent`,
  `neutron_metadata_agent` and `neutron_server`, about the processes that agent containers spawn, and about a change of
  `neutron_legacy_iptables`.
- [What is not known](../troubleshooting/what-is-not-known.md#upgrades-and-database-migrations): the sources do not
  establish whether `neutron-db-manage … upgrade head`, run by a tag change applied with `deploy`, applies contract
  migrations under live old-version servers, and what that does to them.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish whether services started by a shell wrapper that does not `exec` them (`neutron-l3-agent`
  among them) receive SIGTERM at all before the container stops.
- [Update container images §4](../operations/update-container-images.md#4-risks): with a tag change applied by `deploy`
  instead of `upgrade`, `bootstrap_neutron` runs `neutron-db-manage … upgrade head` with the new image before the
  handlers restart the old `neutron_server` containers [CODE].
- [F1](../reference/findings.md#f1), "Loop-notify amplification": a change on a network node restarts all neutron agents
  there [CODE].
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": Neutron is the exception: with the default
  `neutron_enable_rolling_upgrade: "yes"`, `bootstrap_neutron` runs on `deploy` but is skipped on `reconfigure`, so a
  reconfigure re-runs Neutron's DB create/grant tasks but not its DB sync [CODE].
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files [CODE].
- [F8](../reference/findings.md#f8), "`--limit` does not confine actions": with `deploy --limit` set to a compute host,
  `control01` runs the Neutron DB create/grant and the `bootstrap_neutron` container [CODE].
- [F11](../reference/findings.md#f11), "The `openvswitch_agent.ini` merge" includes the operator's `ml2_conf.ini`
  overrides [CODE]: server-side ML2 changes restart every OVS agent.
- [F12](../reference/findings.md#f12), "The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at
  start" when `enable_neutron_agent_ha: yes` [CODE]; [NOT AVAILABLE] whether an L3 agent restart interrupts router
  traffic on that node.
- [F13](../reference/findings.md#f13), "The Nova deploy order" puts nova-compute before OVS and the Neutron agents on
  new computes [CODE]; [NOT AVAILABLE] whether instances can be scheduled on such a compute before the later plays
  finish.
- [F15](../reference/findings.md#f15), "What the bootstrap containers run differs per image": neutron-server's bootstrap
  container migrates `neutron-dynamic-routing`, which the rolling `upgrade` never migrates [CODE].
- [Component dependencies §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional), "Runtime
  facts" [CODE]: the L3 agent wrapper runs a namespace cleanup on start; agent containers do not share the host PID
  namespace;
  the OVS bridge layout is set in a post-config step.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 8 and 12: Neutron upgrade gaps [CODE]; the
  L3 agent wrapper does not `exec` the agent, and [NOT AVAILABLE] whether SIGTERM then reaches only bash, so that the
  agent is killed without a graceful shutdown.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py neutron -->

| Item | Value |
|---|---|
| Play | site.yml:761 |
| Tags | neutron |
| Play host patterns | neutron-server, neutron-dhcp-agent, neutron-l3-agent, ironic-neutron-agent, neutron-metadata-agent, neutron-ovn-metadata-agent, neutron-metering-agent, neutron-bgp-dragent, neutron-infoblox-ipam-agent, compute, manila-share |
| Node types in play (example inventory) | compute, control, network |
| Node types running its containers | compute, control, network |
| Containers | `neutron_server`, `neutron_openvswitch_agent`, `neutron_openvswitch_agent_xenapi`, `neutron_linuxbridge_agent`, `neutron_dhcp_agent`, `neutron_l3_agent`, `neutron_sriov_agent`, `neutron_metadata_agent`, `neutron_ovn_metadata_agent`, `neutron_bgp_dragent`, `neutron_infoblox_ipam_agent`, `neutron_metering_agent`, `ironic_neutron_agent` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → clone (if) → config-host → config → check-containers → config-neutron-fake (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config-host.yml, config-neutron-fake.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, legacy_upgrade.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, rolling_upgrade.yml, stop.yml, upgrade.yml |
| Templates | `bgp_dragent.ini.j2`, `dhcp_agent.ini.j2`, `dnsmasq.conf.j2`, `fwaas_driver.ini.j2`, `ironic-neutron-agent.json.j2`, `ironic_neutron_agent.ini.j2`, `l3_agent.ini.j2`, `linuxbridge_agent.ini.j2`, `metadata_agent.ini.j2`, `metering_agent.ini.j2`, `ml2_conf.ini.j2`, `neutron-bgp-dragent.json.j2`, `neutron-dhcp-agent.json.j2`, `neutron-infoblox-ipam-agent.json.j2`, `neutron-l3-agent-wrapper.sh.j2`, `neutron-l3-agent.json.j2`, `neutron-linuxbridge-agent.json.j2`, `neutron-metadata-agent.json.j2`, `neutron-metering-agent.json.j2`, `neutron-openvswitch-agent-xenapi.json.j2`, `neutron-openvswitch-agent.json.j2`, `neutron-ovn-metadata-agent.json.j2`, `neutron-server.json.j2`, `neutron-sriov-agent.json.j2`, `neutron.conf.j2` … (+6) |
| Handlers (definition order) | Restart neutron-server container; Restart neutron-openvswitch-agent container; Restart neutron-openvswitch-agent-xenapi container; Restart fake neutron-openvswitch-agent container; Restart neutron-linuxbridge-agent container; Restart neutron-dhcp-agent container; Restart neutron-l3-agent container; Restart neutron-sriov-agent container; Restart neutron-metadata-agent container; Restart neutron-ovn-metadata-agent container; Restart neutron-bgp-dragent container; Restart neutron-infoblox-ipam-agent container; Restart neutron-metering-agent container; Restart ironic-neutron-agent container |
| Key variables | `enable_neutron`, `neutron_plugin_agent`, `enable_neutron_dvr`, `enable_neutron_agent_ha`, `enable_neutron_provider_networks`, `neutron_enable_rolling_upgrade` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

## Related

- [Reconfigure Neutron](../operations/reconfigure-neutron.md) — what `-t neutron reconfigure` runs on controllers,
  network nodes and every compute
- [Open vSwitch](openvswitch.md) — `openvswitch_db` and `openvswitch_vswitchd` forward all VM traffic and have their own
  play and tag
- [OVN](ovn.md) — the role used if `neutron_plugin_agent: ovn`
- [Change control-plane membership](../operations/change-control-plane-membership.md) — in the default inventory a
  controller change (RabbitMQ and memcached membership) restarts all nova and neutron containers on all computes; a
  `memcached`-only change still restarts the neutron agents on computes
- [Update container images §4](../operations/update-container-images.md#4-risks) — what a tag change applied with
  `deploy` runs against the Neutron DB
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
