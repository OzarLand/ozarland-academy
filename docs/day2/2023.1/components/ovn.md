---
title: OVN
description: "Where the study covers OVN (roles ovn-controller and ovn-db): what the tags run, what restarts at once, dependencies and open points."
tags: [ovn, openvswitch, serial, kolla-set-configs, dependencies, unknowns]
---

# OVN

This page is the starting point for OVN, used if `neutron_plugin_agent: ovn`. **Changed in 2023.1:** the Ussuri `ovn`
role is split into two roles with their own plays: `ovn-controller` (container `ovn_controller`, tags `ovn` and
`ovn-controller`, `site.yml:568-576`) and `ovn-db` (containers `ovn_northd`, `ovn_nb_db` and `ovn_sb_db`, tags `ovn` and
`ovn-db`, `site.yml:578-588`). Together they run on the compute, control and network nodes of the example inventory;
the tag `ovn` selects both plays, and `ovn-controller` or `ovn-db` selects one. The lists below say where the study
covers how to operate it, its impact, its
dependencies and the evidence, what to check around a run and what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking) (row "OVN")

No operation page gives a command line for the `ovn`, `ovn-controller` or `ovn-db` tags, and no risk register item is
about a run of these tags. What the
study says about running it is in the rows linked under [Impact and risk](#impact-and-risk) and in [fact sheet A
§5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable).

### Impact and risk

- **What the tag executes (`ovn`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `ovn` (both
  plays)

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
  `ovn-cms-options` value is overwritten or removed on every deploy/reconfigure of `ovn-controller`. In 2023.1 the value
  is `enable-chassis-as-gw` on `ovn-controller-network` hosts, plus `availability-zones=` from
  `neutron_ovn_availability_zones` when set; elsewhere the key is removed
  (`roles/ovn-controller/tasks/setup-ovs.yml:17, :39`) [CODE]. Availability-zone hints therefore belong in
  `neutron_ovn_availability_zones`, not in a manual value. The impact of losing a manual value is [NOT AVAILABLE].
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), item (A): any change to
  `ovn-nb-db`/`ovn-sb-db` restarts every member at once under serial 0: the handlers have no serialization
  (`roles/ovn-db/handlers/main.yml:2-45`) [CODE]. **Changed in 2023.1:** `ANSIBLE_SERIAL` or `--limit` is no longer a
  mitigation on an existing cluster: when the current batch holds an NB (or SB) DB host that has its volume but not
  every
  `ovn-nb-db` (or `ovn-sb-db`) host, `lookup_cluster.yml` fails the play (`any_errors_fatal`); a `--limit` that holds
  no OVN DB host does not run the `ovn-db` play at all
  (`roles/ovn-db/tasks/lookup_cluster.yml:21-42, :79-95, :132`) [CODE]. It also fails when the cluster exists but no
  live member reports itself leader (`:73-77, :126-130`).
- The `ovn-db` play runs, on every deploy, reconfigure and upgrade (`upgrade.yml` and `reconfigure.yml` import
  `deploy.yml`): the volume and leader lookup, the bootstrap of members without a volume (a member whose IP is already
  in
  the cluster is first kicked out with `cluster/kick`, then joins the leader), config, check-containers, flush, and on
  hosts in both `ovn-nb-db` and `ovn-sb-db` an `ovn_leader_election_pause` pause (default 5 s) when the cluster existed,
  then `set-connection` on the NB and SB leaders (`roles/ovn-db/tasks/deploy.yml:2-22`,
  `bootstrap-initial.yml:35-67`, `bootstrap-db.yml:7-35`, `defaults/main.yml:98`) [CODE]. What `set-connection` does to
  established client connections is [NOT AVAILABLE].
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure): `ovn` is
  one of the tags that can restart the containers that Tags §3.1 traces to running VMs [CODE]; what those restarts do to
  running VMs is [NOT AVAILABLE].

### Known limits and open points

- [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane), row "OVN": the sources do not
  establish whether an `ovn-controller` restart re-programs flows on the host, and whether Kolla-Ansible's direct
  `ovn-ctl` call creates and upgrades the DB schema (`roles/ovn-db/defaults/main.yml:79-80, :88-89`).
- [Q3](../troubleshooting/open-questions.md#q3): "Data-plane loss during an `openvswitch_vswitchd` restart or recreate".
  Status: [NOT AVAILABLE]. Its row in [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane)
  includes whether the OVS agent or `ovn-controller` reprograms the OpenFlow tables.
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: agent, OVS and OVN images have no
  one-shot branch (no `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` in kolla `docker/ovn/*`).
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), "Operationally notable",
  items (A) to (H), read against 2023.1: the whole DB cluster restarts at once (above); a new cluster is seeded from the
  first `ovn-nb-db`/`ovn-sb-db` host, while a member re-created on an existing cluster joins the current leader
  (`roles/ovn-db/tasks/bootstrap-initial.yml:5-13, :59-67`) [CODE]; ovn-controller restarts; the chassis settings are
  re-applied on every ovn-controller host on each run, through the `openvswitch_bridge`/`openvswitch_db` modules in
  `kolla_toolbox` instead of the Ussuri `docker exec openvswitch_vswitchd ovs-vsctl` commands
  (`roles/ovn-controller/tasks/setup-ovs.yml:2-40`), and whether those modules report changed on an unchanged host is
  [NOT AVAILABLE]; gateway options are clobbered (above); security; with OVN and `enable_ovs_dpdk`, Kolla-Ansible
  deploys
  no Open vSwitch container at all: the openvswitch play is skipped (`site.yml:550`) and the ovs-dpdk containers are
  enabled only when `neutron_plugin_agent in ['openvswitch']` (`roles/ovs-dpdk/defaults/main.yml:10, :24`), while OVN
  needs `neutron_plugin_agent == 'ovn'` (`group_vars/all.yml:737`) [CODE]; whether OVN works with an OVSDB provided
  outside Kolla-Ansible is [NOT AVAILABLE]; missing inventory groups are still not caught (the prechecks of both roles
  check
  only free ports, `roles/ovn-db/tasks/precheck.yml`, `roles/ovn-controller/tasks/precheck.yml` is empty) [CODE].
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), item (C): the OVN manifests
  have no `config_files` (`roles/ovn-db/templates/*.json.j2`, `roles/ovn-controller/templates/ovn-controller.json.j2`),
  so `kolla_set_configs --check` always exits 0: a command-line change written by `genconfig` is
  applied neither by `deploy-containers` nor by a later run, until the container restarts for another reason.
- [Kolla images §7](../concepts/kolla-images.md#7-what-is-not-available-from-the-sources): not available from the
  sources: `ovn-ctl` schema creation and upgrade with Kolla-Ansible's direct call, and its hard-coded
  `/usr/share/ovn/scripts/` path on distributions that ship `ovn-ctl` elsewhere.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md) and
  [Findings](../reference/findings.md) have no entry on OVN.

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py ovn-controller ovn-db -->

### OVN controller — role `ovn-controller`

| Item | Value |
|---|---|
| Play | site.yml:568 |
| Tags | ovn, ovn-controller |
| Play host patterns | ovn-controller |
| Node types in play (example inventory) | compute, network |
| Node types running its containers | compute, network |
| Containers | `ovn_controller` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → setup-ovs → flush handlers |
| Task files | check-containers.yml, config.yml, config_validate.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, setup-ovs.yml, stop.yml, upgrade.yml |
| Templates | `ovn-controller.json.j2` |
| Handlers (definition order) | Restart ovn-controller container |
| Key variables | `enable_ovn`, `neutron_plugin_agent: ovn`, `neutron_ovn_distributed_fip` |
| Role dependencies | none |

### OVN databases — role `ovn-db`

| Item | Value |
|---|---|
| Play | site.yml:578 |
| Tags | ovn, ovn-db |
| Play host patterns | ovn-nb-db, ovn-northd, ovn-sb-db |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `ovn_northd`, `ovn_nb_db`, `ovn_sb_db` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | lookup_cluster (if) → bootstrap-initial (if) → config → check-containers → flush handlers → bootstrap-db (if) |
| Task files | bootstrap-db.yml, bootstrap-initial.yml, check-containers.yml, config.yml, config_validate.yml, deploy-containers.yml, deploy.yml, lookup_cluster.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `ovn-nb-db.json.j2`, `ovn-northd.json.j2`, `ovn-sb-db.json.j2` |
| Handlers (definition order) | Restart ovn-nb-db container; Restart ovn-sb-db container; Restart ovn-northd container |
| Key variables | `enable_ovn`, `neutron_plugin_agent: ovn`, `neutron_ovn_distributed_fip` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Open vSwitch](openvswitch.md) — OVN needs OVS running: `ovn-controller` connects to the local OVSDB
  (`tcp:127.0.0.1:{{ ovsdb_port }}`, `roles/ovn-controller/templates/ovn-controller.json.j2:2`) and its chassis settings
  are written into it
- [Neutron](neutron.md) — neutron-server (ML2/OVN) and `neutron-ovn-metadata-agent` depend on OVN
- [Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking) — what `-t neutron` and `-t ovn`
  touch with OVN
- [Component dependencies §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional) — the networking
  containers and their placement
- [Components](index.md) — the other component pages
