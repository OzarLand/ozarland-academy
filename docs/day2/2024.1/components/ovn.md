---
title: OVN
description: "Where the 2024.1 study covers OVN (roles ovn-controller and ovn-db): what the tags run, what restarts at once, dependencies and open points."
tags: [ovn, openvswitch, serial, kolla-set-configs, dependencies, unknowns]
---

# OVN

This page is the starting point for OVN, used if `neutron_plugin_agent: ovn` (`enable_ovn`, `group_vars/all.yml:834`).
OVN has two roles with their own plays: `ovn-controller` (container `ovn_controller`, tags `ovn` and `ovn-controller`,
`site.yml:641-653`) and `ovn-db` (containers `ovn_northd`, `ovn_nb_db` and `ovn_sb_db`, tags `ovn` and `ovn-db`,
`site.yml:655-669`). Together they run on the compute, control and network nodes of the example inventory
(`inventory/multinode:593-613`); the tag `ovn` selects both plays, and `ovn-controller` or `ovn-db` selects one. The
lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to check
around a run and what stays open; the service card follows them.

> [!NOTE]
> **Key answers**
>
> - **Restart semantics still hold:** apart from the module rename to `kolla_container`, the handlers of both roles
>   and the whole `ovn-controller` role are unchanged; any change to the NB or SB DB restarts every member of the
>   batch at once, and with the default `kolla_serial` of `0` the batch is the whole group
>   (`roles/ovn-db/handlers/main.yml:2-45`, `site.yml:655-662`) [CODE] ([Before and after a
>   run](#before-and-after-a-run)).
> - **`ovn-controller`:** the chassis settings (`br-int`, nine `external_ids` keys) are re-applied through
>   `kolla_toolbox` on every deploy, reconfigure and upgrade, before the handlers run; these tasks notify nothing
>   (`roles/ovn-controller/tasks/deploy.yml:2-9`, `setup-ovs.yml:2-40`) [CODE].
> - **DB bootstrap, changed in 2024.1:** `set-connection` on the NB and SB leaders is retried (`retries: 3`,
>   `delay: 5`), and every `docker exec` of the role now goes through `kolla_container_engine`
>   (`roles/ovn-db/tasks/bootstrap-db.yml:12-56`) [CODE].
> - **Image start, new in 2024.1:** every OVN image now has its own `kolla_ovn_extend_start`, sourced by the ovn-base
>   script, which creates the container's log file (kolla `docker/ovn/ovn-base/extend_start.sh:13`,
>   `docker/ovn/ovn-controller/extend_start.sh:3-6`) [CODE].

## Where to look

### Operate

- **Scenario:** [Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking) (row "OVN")

No operation page gives a command line for the `ovn`, `ovn-controller` or `ovn-db` tags, and no risk register item is
about a run of these tags. What the study says about running it is in the rows linked under [Impact and
risk](#impact-and-risk) and in [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable).

### Impact and risk

- **What the tag executes (`ovn`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `ovn` (both
  plays)

### Dependencies

- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components), [Component dependencies
  §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional)

### Evidence

- **Fact sheet:** [fact sheet A §5](../reference/factsheets/a-infra-lb-ovn.md#5-ovn-role)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `ovn-*`), [Kolla
  images §2.5](../concepts/kolla-images.md#25-the-extend_start-chain)

### Before and after a run

- **`ovn-controller`, still holds in 2024.1:** the role runs config, check-containers, `setup-ovs`, then a flush of
  the handlers (`roles/ovn-controller/tasks/deploy.yml:2-9`); `reconfigure` and `upgrade` import that file
  (`reconfigure.yml:2`, `upgrade.yml:2`). Its only handler, `Restart ovn-controller container`
  (`recreate_or_restart_container`, skipped when `kolla_action` is `config`), is notified by a changed `config.json`
  or by drift found by the check (`roles/ovn-controller/handlers/main.yml:2-15`, `tasks/config.yml:15-26`,
  `check-containers.yml:2-16`) [CODE]. With the default `kolla_serial` of `0`, the play's single batch holds every
  compute and network node (`site.yml:641-653`, `inventory/multinode:593-601`) [CODE].
- **Chassis settings:** `setup-ovs` creates `br-int` with `fail_mode: secure` through the `openvswitch_bridge` module,
  then sets nine `external_ids` keys of the local OVSDB through the `openvswitch_db` module, both in `kolla_toolbox`
  (`roles/ovn-controller/tasks/setup-ovs.yml:2-40`) [CODE]. Neither task notifies a handler, and they run before the
  flush, so a restart of `ovn_controller` in the same run comes after them (`deploy.yml:6-9`). Whether those modules
  report *changed* on an unchanged host is [NOT AVAILABLE]: their code is not in the studied sources (the kolla-toolbox
  image installs the `openvswitch.openvswitch` collection, `<3`, kolla `docker/kolla-toolbox/requirements.yml:13-14`).
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), item (E): any manual
  `ovn-cms-options` value is overwritten or removed on every deploy, reconfigure and upgrade of `ovn-controller`. The
  value is `enable-chassis-as-gw` on `ovn-controller-network` hosts, plus `availability-zones=` from
  `neutron_ovn_availability_zones` when set; elsewhere the key is removed
  (`roles/ovn-controller/tasks/setup-ovs.yml:17, :39`) [CODE]. Availability-zone hints therefore belong in
  `neutron_ovn_availability_zones` (default `[]`, `group_vars/all.yml:1116`), not in a manual value. Bridge mappings
  are removed on hosts that are neither network nodes nor covered by `computes_need_external_bridge` (`:37`) [CODE].
  The impact of losing a manual value is [NOT AVAILABLE].
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), item (A): any change to
  `ovn-nb-db`/`ovn-sb-db` restarts every member of the batch at once: the handlers have no serialization
  (`roles/ovn-db/handlers/main.yml:2-45`), and the play has `serial: kolla_serial`, default `0` (`site.yml:662`)
  [CODE]. **Still holds in 2024.1:** `ANSIBLE_SERIAL` or `--limit` is not a mitigation on an existing cluster: when
  the current batch holds an NB (or SB) DB host that has its volume but not every `ovn-nb-db` (or `ovn-sb-db`) host,
  `lookup_cluster.yml` fails the play (`any_errors_fatal`); a `--limit` that holds no OVN DB host does not run the
  `ovn-db` play at all (`roles/ovn-db/tasks/lookup_cluster.yml:21-42, :79-95, :132`, `site.yml:655-661`) [CODE]. It
  also fails when the cluster exists but no live member reports itself leader (`:73-77, :126-130`).
- The `ovn-db` play runs, on every deploy, reconfigure and upgrade (`upgrade.yml:2` and `reconfigure.yml:2` import
  `deploy.yml`): the volume and leader lookup, the bootstrap of members without a volume (a member whose IP is already
  in the cluster is first kicked out with `cluster/kick`, then joins the leader), config, check-containers, flush, and
  on hosts in both `ovn-nb-db` and `ovn-sb-db` an `ovn_leader_election_pause` pause (default 5 s) when the cluster
  existed, then `set-connection` on the NB and SB leaders (`roles/ovn-db/tasks/deploy.yml:2-22`,
  `bootstrap-initial.yml:35-67`, `bootstrap-db.yml:7-56`, `defaults/main.yml:98`) [CODE]. **Changed in 2024.1:** each
  `set-connection` is retried (`retries: 3`, `delay: 5`, until `rc` is 0) instead of failing at once
  (`bootstrap-db.yml:29-32, :52-55`), and the `docker exec` calls of `bootstrap-db.yml` now use
  `kolla_container_engine` (`:14-17, :25-28, :37-40, :48-51`) [CODE]. What `set-connection` does to established
  client connections is [NOT AVAILABLE].
- **First 2024.1 check after an upgrade from 2023.1:** the check compares the systemd unit too, and its text changed,
  so an OVN container whose unit 2023.1 wrote, and that no 2024.1 run has recreated or restarted yet, is restarted by
  the first 2024.1
  check ([F16](../reference/findings.md#f16)) [CODE]. For the DB containers, that is every member of the batch.
- **Image start, new in 2024.1:** the ovn-base start script, which replaces the Open vSwitch one, now ends by sourcing
  `kolla_ovn_extend_start` (kolla `docker/ovn/ovn-base/Dockerfile.j2:23`, `docker/ovn/ovn-base/extend_start.sh:13`).
  ovn-controller, ovn-northd, ovn-nb-db-server and ovn-sb-db-server each install their own, which creates the
  container's log file owned by `openvswitch` when it is not readable (e.g.
  `docker/ovn/ovn-controller/Dockerfile.j2:23-24`, `docker/ovn/ovn-controller/extend_start.sh:3-6`,
  `docker/ovn/ovn-nb-db-server/extend_start.sh:3-6`) [CODE].
  Kolla-Ansible's manifests still set `/var/log/kolla/openvswitch` to `root:root`, recursively
  (`roles/ovn-controller/templates/ovn-controller.json.j2:3-9`, `roles/ovn-db/templates/ovn-nb-db.json.j2:3-9`)
  [CODE]; what the two ownerships do to logging is [NOT AVAILABLE].
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
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: the OVN images have no one-shot
  branch (no `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` in kolla `docker/ovn/*`, grep).
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), "Operationally notable",
  items (A) to (H), read against 2024.1:
  - the whole DB cluster batch restarts at once (above);
  - a new cluster is seeded from the first `ovn-nb-db`/`ovn-sb-db` host, while a member re-created on an existing
    cluster joins the current leader (`roles/ovn-db/tasks/bootstrap-initial.yml:5-13, :59-67`) [CODE]; there is still
    no backup code (grep of `ansible/roles`: no `ovsdb-client backup`);
  - ovn-controller restarts and chassis settings (above); whether the `openvswitch_bridge`/`openvswitch_db` modules
    report changed on an unchanged host is [NOT AVAILABLE];
  - gateway options are clobbered (above);
  - NB and SB clients connect over plain TCP (`ovn_nb_connection` and `ovn_sb_connection` use `tcp:`,
    `group_vars/all.yml:548-549`), and the DB listeners are set to `ptcp:<port>:0.0.0.0`
    (`roles/ovn-db/tasks/bootstrap-db.yml:28, :51`) [CODE];
  - with OVN and `enable_ovs_dpdk`, Kolla-Ansible deploys no Open vSwitch container at all: the openvswitch play
    targets only `enable_ovs_dpdk` false (`site.yml:615, :624`), and the ovs-dpdk containers are enabled only when
    `neutron_plugin_agent in ['openvswitch']` (`roles/ovs-dpdk/defaults/main.yml:10, :24`), while OVN needs
    `neutron_plugin_agent == 'ovn'` (`group_vars/all.yml:834`) [CODE]; whether OVN works with an OVSDB provided
    outside Kolla-Ansible is [NOT AVAILABLE];
  - missing inventory groups are still not caught: the precheck of `ovn-db` checks only free ports and that of
    `ovn-controller` is empty (`roles/ovn-db/tasks/precheck.yml:2-32`, `roles/ovn-controller/tasks/precheck.yml:1`)
    [CODE].
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), item (C): the OVN manifests
  have no `config_files` (`roles/ovn-db/templates/ovn-nb-db.json.j2:1-10`, `ovn-northd.json.j2:1-10`,
  `roles/ovn-controller/templates/ovn-controller.json.j2:1-10`), and `kolla_set_configs --check` compares only
  `config_files` entries (kolla `docker/base/set_configs.py:556-559`), so it always exits 0 for them [CODE]: a
  command-line change written by `genconfig` is applied neither by `deploy-containers` nor by a later run, until the
  container restarts for another reason ([Kolla images
  §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
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
| Play | site.yml:641 |
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
| Play | site.yml:655 |
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
