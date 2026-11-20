---
title: Open vSwitch
description: Where the study covers Open vSwitch (role openvswitch), from what the tag runs on compute and network nodes to the Critical vswitchd restart risk.
tags: [openvswitch, upgrade, serial, images, risk, dependencies, bugs, unknowns]
---

# Open vSwitch

This page is the starting point for Open vSwitch, the `openvswitch` role: the containers `openvswitch_db` and
`openvswitch_vswitchd`, on the compute and network nodes of the example inventory, selected by the tag `openvswitch`.
The play runs only while `enable_ovs_dpdk` is `no`; `ovs-dpdk` has its own play and tag (`site.yml:546-566`).
The risk register rates a restart or recreate of `openvswitch_vswitchd` Critical ([R7](../risk/risk-register.md#r7)).
The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking) (row "Open
  vSwitch"), [Update container images §4](../operations/update-container-images.md#4-risks) (OVS image change)
- **Command:** [Reconfigure Neutron §1.1](../operations/reconfigure-neutron.md#11-neutron)
- [Command quick lookup by tag](../operations/command-quick-lookup.md), row `-t openvswitch reconfigure`: hosts touched
  with the default inventory: network, all computes; can restart, only if drift is detected: openvswitch_db/vswitchd;
  typical duration driver: the number of computes.

### Impact and risk

- **What the tag executes (`openvswitch`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and
  [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows
  `openvswitch`
- **Risks:** [R7](../risk/risk-register.md#r7)

### Dependencies

- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components), [Component dependencies
  §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional)

### Evidence

- **Fact sheet:** – (`ovs-dpdk`: [fact sheet A §6](../reference/factsheets/a-infra-lb-ovn.md#6-ovs-dpdk-role))
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `openvswitch-*`)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)

### Before and after a run

- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `openvswitch`: safe on its own "yes if unchanged"; **changed in 2023.1:** `system-id` and `hw-offload` are set
  through the `openvswitch_db` module in `kolla_toolbox`, and a change notifies `Restart openvswitch-vswitchd container`
  (`roles/openvswitch/tasks/post-config.yml:3-22`) [CODE]; whether the module reports *ok* when the value is already set
  is [NOT AVAILABLE] (the module is not in these sources). Image changes per host batch; prerequisite: the
  `openvswitch` kernel module.
- [R7](../risk/risk-register.md#r7), precautions: upgrade or recreate OVS host by host with evacuation or acceptance;
  never fleet-wide with serial 0.
- [Update container images §4](../operations/update-container-images.md#4-risks): an OVS image change recreates
  `openvswitch_vswitchd` on every OVS host simultaneously (serial 0); [NOT AVAILABLE] whether VM networking is
  interrupted on every compute at the same time. Upgrade OVS per batch with
  `ANSIBLE_SERIAL=<n> kolla-ansible -t openvswitch upgrade`, or use `--limit` batches.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure):
  `openvswitch` is one of the tags that can restart the containers that Tags §3.1 traces to running VMs [CODE]; what
  those restarts do to running VMs is [NOT AVAILABLE].

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `openvswitch`: the Ussuri
  `Set system-id` command that always reported changed is gone; 2023.1 uses the `openvswitch_db` module and restarts
  `openvswitch_vswitchd` when it reports changed (`roles/openvswitch/tasks/post-config.yml:3-22`) [CODE]. Whether it
  reports changed on an unchanged host: [NOT AVAILABLE].
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `ovs-dpdk`: the `pull` bug is
  fixed in 2023.1 (`pull` imports `service-images-pull`, which reads `ovsdpdk_services` through
  `kolla_role_name: "ovsdpdk"`; `roles/ovs-dpdk/tasks/pull.yml:2-3`, `vars/main.yml:4`,
  `roles/service-images-pull/tasks/main.yml:14`); the NIC mapping file is still written once (`gen_config` only if the
  file is absent, `roles/ovs-dpdk/files/ovs-dpdkctl.sh:350-353`); the 300 s wait handler still has no port
  (`roles/ovs-dpdk/handlers/main.yml:88-92`), but the notify that should reach it is spelled `wait for dpdk tunnel ip`
  while the handler is named `Wait for dpdk tunnel ip` (`roles/ovs-dpdk/handlers/main.yml:21, :88`), so whether the wait
  runs at all, or the run fails on the missing handler, is [NOT AVAILABLE]; see [fact sheet A
  §6](../reference/factsheets/a-infra-lb-ovn.md#6-ovs-dpdk-role). Status: [CODE].
- [Q3](../troubleshooting/open-questions.md#q3): "Data-plane loss during an `openvswitch_vswitchd` restart or recreate".
  Status: [NOT AVAILABLE].
- [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane), row "`openvswitch_vswitchd` restart
  or recreate": the sources do not establish whether the OpenFlow tables are lost, whether the OVS agent or
  `ovn-controller` reprograms them, and whether all VM traffic on the host is interrupted, and for how long. Same table:
  whether VM network traffic stops under `kolla-ansible stop`.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish whether services started by a shell wrapper that does not `exec` them
  (`neutron-l3-agent`, `haproxy`, `ovs-vswitchd`, `ovsdb-server`) receive SIGTERM at all before the container stops;
  `start-ovs` runs `ovs-vswitchd` without `exec` (`roles/openvswitch/templates/start-ovs.j2:2`).
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: agent, OVS and OVN images have no
  one-shot branch (no `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` in kolla `docker/openvswitch/*`).
- [F13](../reference/findings.md#f13), "The Nova deploy order" puts nova-compute before OVS and the Neutron agents on
  new computes (`site.yml:544` imports `nova.yml` before the openvswitch play at `:546`) [CODE]; [NOT AVAILABLE] whether
  instances can be scheduled on such a compute before the later plays
  finish.
- [fact sheet A §6.8](../reference/factsheets/a-infra-lb-ovn.md#68-operationally-notable), "Operationally notable" for
  the `ovs-dpdk` role (no fact sheet covers `openvswitch`): any `ovsdpdk-db` restart also restarts `ovs-vswitchd`; NIC
  rebinding and unit installation run on every deploy, reconfigure, upgrade and genconfig; sticky configuration.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 13: an `openvswitch_vswitchd` restart
  replaces only the userspace daemon; the kernel module stays loaded and `conf.db` keeps bridges and ports [CODE].
  [NOT AVAILABLE] Whether the OpenFlow tables are lost and must be reprogrammed by the OVS agent or `ovn-controller`.

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py openvswitch -->

| Item | Value |
|---|---|
| Play | site.yml:546 |
| Tags | openvswitch |
| Play host patterns | openvswitch |
| Node types in play (example inventory) | compute, network |
| Node types running its containers | compute, network |
| Containers | `openvswitch_db`, `openvswitch_vswitchd` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config-host → config → check-containers → flush handlers → post-config |
| Task files | check-containers.yml, check.yml, config-host.yml, config.yml, config_validate.yml, deploy-containers.yml, deploy.yml, main.yml, post-config.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `openvswitch-db-server.json.j2`, `openvswitch-vswitchd.json.j2`, `ovs-vsctl.j2`, `start-ovs.j2`, `start-ovsdb-server.j2` |
| Handlers (definition order) | Restart openvswitch-db-server container; Waiting for openvswitch_db service to be ready; Restart openvswitch-vswitchd container |
| Key variables | `enable_openvswitch`, `neutron_bridge_name`, `neutron_external_interface`, `computes_need_external_bridge` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure Neutron](../operations/reconfigure-neutron.md) — `-t neutron` does not touch Open vSwitch, which has a
  separate play and tag
- [Update container images](../operations/update-container-images.md) — what an OVS image change recreates, and how to
  batch it
- [Component dependencies §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional) — `openvswitch_db`
  and `openvswitch_vswitchd` forward all VM traffic
- [Neutron](neutron.md) — `neutron_openvswitch_agent` programs the OVS flows
- [OVN](ovn.md) — `ovn_controller` programs OVS from the SB DB
- [Components](index.md) — the other component pages
