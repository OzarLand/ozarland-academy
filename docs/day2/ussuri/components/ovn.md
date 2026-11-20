---
title: OVN
description: Where the study covers OVN (role ovn, used if neutron_plugin_agent is ovn), from what the tag runs and what restarts at once to dependencies and open points.
tags: [ovn, openvswitch, serial, kolla-set-configs, dependencies, unknowns]
---

# OVN

This page is the starting point for OVN, the `ovn` role, used if `neutron_plugin_agent: ovn`: the containers
`ovn_controller`, `ovn_northd`, `ovn_nb_db` and `ovn_sb_db`, on the compute, control and network nodes of the example
inventory, selected by the tag `ovn`. The lists below say where the study covers how to operate it, its impact, its
dependencies and the evidence, what to check around a run and what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking) (row "OVN")

No operation page gives a command line for the `ovn` tag, and no risk register item is about a run of this tag. What the
study says about running it is in the rows linked under [Impact and risk](#impact-and-risk) and in [fact sheet A
§5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable).

### Impact and risk

- **What the tag executes (`ovn`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `ovn`

### Dependencies

- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components), [Component dependencies
  §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional)

### Evidence

- **Fact sheet:** [fact sheet A §5](../reference/factsheets/a-infra-lb-ovn.md#5-ovn-role)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `ovn-*`)

### Before and after a run

- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `ovn`: safe
  on its own "check manual `ovn-cms-options` first"; prerequisite: Open vSwitch.
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), item (E): any manual
  `ovn-cms-options` value, such as availability-zone hints, is overwritten or removed on every reconfigure; the impact
  of that loss is NOT AVAILABLE.
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), item (A): any change to
  `ovn-nb-db`/`ovn-sb-db` restarts every member at once under serial 0. Mitigation: `ANSIBLE_SERIAL` gives a rolling
  restart, at the cost of making every play serial.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure): `ovn` is
  one of the tags that can restart the containers that Tags §3.1 traces to running VMs [CODE]; what those restarts do to
  running VMs is [NOT AVAILABLE].

### Known limits and open points

- [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane), row "OVN": the sources do not
  establish whether an `ovn-controller` restart re-programs flows on the host, and whether Kolla-Ansible's direct
  `ovn-ctl` call creates and upgrades the DB schema.
- [Q3](../troubleshooting/open-questions.md#q3): "Data-plane loss during an `openvswitch_vswitchd` restart or recreate".
  Status: [NOT AVAILABLE]. Its row in [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane)
  includes whether the OVS agent or `ovn-controller` reprograms the OpenFlow tables.
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: agent, OVS and OVN images have no
  one-shot branch.
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), "Operationally notable",
  items (A) to (H): the whole DB cluster restarts at once; whether the seed host is a single point of failure for
  re-deploys is NOT AVAILABLE; ovn-controller restarts; bootstrap cost scales with computes; gateway options are
  clobbered; security; OVN + DPDK cannot work in this release (inference from code); missing inventory groups are not
  caught.
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), item (C): the OVN manifests
  have no `config_files`, so `kolla_set_configs --check` always exits 0: a command-line change written by `genconfig` is
  applied neither by `deploy-containers` nor by a later run, until the container restarts for another reason.
- [Kolla images §7](../concepts/kolla-images.md#7-what-is-not-available-from-the-sources): not available from the
  sources: `ovn-ctl` schema creation and upgrade with Kolla-Ansible's direct call, and its hard-coded
  `/usr/share/ovn/scripts/` path on distributions that ship `ovn-ctl` elsewhere.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md) and
  [Findings](../reference/findings.md) have no entry on OVN.

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py ovn -->

| Item | Value |
|---|---|
| Play | site.yml:734 |
| Tags | ovn |
| Play host patterns | ovn-controller, ovn-nb-db, ovn-northd, ovn-sb-db |
| Node types in play (example inventory) | compute, control, network |
| Node types running its containers | compute, control, network |
| Containers | `ovn_controller`, `ovn_northd`, `ovn_nb_db`, `ovn_sb_db` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, check-containers.yml, check.yml, config.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `ovn-controller.json.j2`, `ovn-nb-db.json.j2`, `ovn-northd.json.j2`, `ovn-sb-db.json.j2` |
| Handlers (definition order) | Restart ovn-nb-db container; Restart ovn-sb-db container; Wait for ovn-nb-db; Wait for ovn-sb-db; Restart ovn-northd container; Restart ovn-controller container |
| Key variables | `enable_ovn`, `neutron_plugin_agent: ovn`, `neutron_ovn_distributed_fip` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

## Related

- [Open vSwitch](openvswitch.md) — OVN needs OVS running: its bootstrap commands exec into `openvswitch_vswitchd`
- [Neutron](neutron.md) — neutron-server (ML2/OVN) and `neutron-ovn-metadata-agent` depend on OVN
- [Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking) — what `-t neutron` and `-t ovn`
  touch with OVN
- [Component dependencies §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional) — the networking
  containers and their placement
- [Components](index.md) — the other component pages
