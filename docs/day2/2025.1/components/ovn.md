---
title: OVN
description: "Where the 2025.1 study covers OVN (roles ovn-controller and ovn-db): the new SB relays, what the tags run, what restarts at once, open points."
tags: [ovn, openvswitch, serial, kolla-set-configs, dependencies, unknowns]
---

# OVN

This page is the starting point for OVN, used if `neutron_plugin_agent: ovn` (`enable_ovn`, `group_vars/all.yml:952`).
OVN has two roles with their own plays: `ovn-controller` (container `ovn_controller`, tags `ovn` and `ovn-controller`,
`site.yml:635-647`) and `ovn-db` (containers `ovn_northd`, `ovn_nb_db`, `ovn_sb_db` and, **new in 2025.1**, one
`ovn_sb_db_relay_<n>` per relay, tags `ovn` and `ovn-db`, `site.yml:649-663`). Together they run on the compute,
control and network nodes of the example inventory (`inventory/multinode:579-602`); the tag `ovn` selects both plays,
and `ovn-controller` or `ovn-db` selects one. The lists below say where the study covers how to operate it, its
impact, its dependencies and the evidence, what to check around a run and what stays open; the service card follows
them.

> [!NOTE]
> **Key answers**
>
> - **SB relays on by default, new in 2025.1:** `enable_ovn_sb_db_relay` follows `enable_ovn`
>   (`group_vars/all.yml:953`). The `ovn-db` role starts `ceil(<ovn-controller hosts> / 50)` relay containers on every
>   `ovn-sb-db-relay` host (the `ovn-database` hosts, `inventory/multinode:601-602`), each listening on
>   `16640 + <n>` (`group_vars/all.yml:640-644`; `roles/ovn-db/defaults/main.yml:31-41`). `ovn-controller` and the
>   Neutron OVN metadata and OVN agents now connect to a relay, picked per host with a seeded random choice;
>   `ovn-northd`, neutron-server and Octavia still connect to the SB cluster (`group_vars/all.yml:646-648`;
>   `roles/ovn-controller/tasks/setup-ovs.yml:42`; `roles/neutron/templates/ml2_conf.ini.j2:40`) [CODE].
> - **Restart decision, changed in 2025.1:** the config tasks notify nothing; both roles import
>   `service-check-containers`, which notifies the handler of each changed container only, and the relays through an
>   iterated variant that restarts only the changed relay numbers (`roles/ovn-db/tasks/check-containers.yml:2-3`,
>   `roles/service-check-containers/tasks/iterated.yml:2-42`, `roles/ovn-db/handlers/main.yml:30-46`) [CODE]. A change
>   to the NB or SB DB container still restarts every member of the batch at once.
> - **`ovn-controller`:** the chassis settings (`br-int`, `external_ids` keys) are re-applied through `kolla_toolbox`
>   on every deploy, reconfigure and upgrade; these tasks notify nothing (`roles/ovn-controller/tasks/deploy.yml:2-9`,
>   `setup-ovs.yml:2-50`) [CODE]. The bridge mappings now take the physical network names from
>   `neutron_physical_networks` (default `physnet1`, `physnet2`, … as before, `group_vars/all.yml:1215`).
> - **Upgrade order to check** [CODE]: the `ovn-controller` play runs before the `ovn-db` play (`site.yml:635`, `:649`),
>   so on the first 2025.1 run `setup-ovs` points every chassis at a relay (`ovn-remote`) before the `ovn-db` play has
>   created the relays. [NOT AVAILABLE] How long `ovn-controller` stays without an SB connection, and what that does to
>   the data plane; to be confirmed by the community.

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

- **`ovn-controller`:** the role runs config, check-containers, `setup-ovs`, then a flush of the handlers
  (`roles/ovn-controller/tasks/deploy.yml:2-9`); `reconfigure` and `upgrade` import that file
  (`roles/ovn-controller/tasks/reconfigure.yml:2`, `roles/ovn-controller/tasks/upgrade.yml:2`). Its only handler,
  `Restart ovn-controller container` (`recreate_or_restart_container`, `roles/ovn-controller/handlers/main.yml:2-13`),
  is notified only by the shared check when the container differs (`roles/ovn-controller/tasks/check-containers.yml:2-3`)
  [CODE]. With the default `kolla_serial` of `0`, and always under `reconfigure` and `upgrade`
  ([F19](../reference/findings.md#f19)), the play's single batch holds every compute and network node
  (`site.yml:635-647`, `inventory/multinode:579-587`) [CODE].
- **Chassis settings:** `setup-ovs` creates `br-int` with `fail_mode: secure` through the `openvswitch_bridge` module,
  then sets the `external_ids` keys of the local OVSDB through the `openvswitch_db` module, both in `kolla_toolbox`
  (`roles/ovn-controller/tasks/setup-ovs.yml:2-50`) [CODE]. Neither task notifies a handler, and they run before the
  flush (`roles/ovn-controller/tasks/deploy.yml:6-9`). **Changed in 2025.1:** `ovn-remote` is the relay connection
  when relays are on (`setup-ovs.yml:42`, `group_vars/all.yml:646`), so the first 2025.1 run moves every chassis from
  the SB cluster to a relay without restarting `ovn_controller`. Whether those modules report *changed* on an
  unchanged host is [NOT AVAILABLE]: their code is not in the studied sources (the kolla-toolbox image installs the
  `openvswitch.openvswitch` collection, kolla `docker/kolla-toolbox/requirements.yml:13-14`).
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), item (E): any manual
  `ovn-cms-options` value is overwritten or removed on every deploy, reconfigure and upgrade of `ovn-controller`. The
  value is `enable-chassis-as-gw` on `ovn-controller-network` hosts, plus `availability-zones=` from
  `neutron_ovn_availability_zones` when set; elsewhere the key is removed
  (`roles/ovn-controller/tasks/setup-ovs.yml:19-26`, `:48`) [CODE]. **Changed in 2025.1:** several zones are now
  joined with `:` (`:24`); 2024.1 joined them with `,`, the separator of the options themselves, so a host with two
  or more zones gets a different value at the first 2025.1 run. Availability-zone hints belong in
  `neutron_ovn_availability_zones` (`group_vars/all.yml:1242`), not in a manual value. Bridge mappings are removed on
  hosts that are neither network nodes nor covered by `computes_need_external_bridge` (`:46`) [CODE].
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), item (A): any change to the
  NB or SB DB container restarts every member of the batch at once: the handlers have no serialization
  (`roles/ovn-db/handlers/main.yml:2-29`, `:48-61`), and the play has `serial: kolla_serial`, default `0`
  (`site.yml:656`) [CODE]. `--limit` is not a mitigation on an existing cluster: when the current batch holds an NB
  (or SB) DB host that has its volume but not every `ovn-nb-db` (or `ovn-sb-db`) host, `lookup_cluster.yml` fails the
  play (`any_errors_fatal`); a `--limit` that holds no OVN DB host does not run the `ovn-db` play at all
  (`roles/ovn-db/tasks/lookup_cluster.yml:22-43, :80-96`, `site.yml:649-655`) [CODE]. It also fails when the cluster
  exists but no live member reports itself leader (`:73-77, :126-130`).
- **SB relays, new in 2025.1** [CODE]: `config.yml` renders one `config.json` and one `ovsdb-relay.json` per relay
  number under `/etc/kolla/ovn-sb-db-relay-<n>/` (`roles/ovn-db/tasks/config.yml:22-25`,
  `roles/ovn-db/tasks/config-relay.yml:2-32`); the relay's upstream is the SB cluster
  (`roles/ovn-db/templates/ovsdb-relay.json.j2:12`). On Debian the relay gets its remote on the command line instead
  (`roles/ovn-db/defaults/main.yml:110-118`). After the flush, the hosts in both DB groups wait up to 10 × 60 s for each
  relay port (`roles/ovn-db/tasks/bootstrap-db.yml:84-98`). The relay count follows the number of `ovn-controller`
  hosts, so adding the 51st compute adds a relay container on every relay host at the next `ovn-db` run, and
  `ovn_sb_db_relay_client_group_id` is recomputed for every chassis (`group_vars/all.yml:640-644`): [NOT AVAILABLE]
  how many chassis then change relay, and what a relay change costs them.
- The `ovn-db` play runs, on every deploy, reconfigure and upgrade (`roles/ovn-db/tasks/upgrade.yml:2` and
  `roles/ovn-db/tasks/reconfigure.yml:2` import `deploy.yml`): the volume and leader lookup, the bootstrap of members
  without a volume (a member whose IP is already in the cluster is first kicked out with `cluster/kick`, then joins the
  leader), config, check-containers, flush, and on hosts in both `ovn-nb-db` and `ovn-sb-db` an
  `ovn_leader_election_pause` pause when the cluster existed, then `set-connection` on the NB and SB leaders, retried
  3 times, and **new**, run against the local unix socket (`roles/ovn-db/tasks/deploy.yml:2-22`,
  `roles/ovn-db/tasks/bootstrap-initial.yml:35-67`, `roles/ovn-db/tasks/bootstrap-db.yml:25-31`, `:50-56`) [CODE].
  What `set-connection` does to established client connections is [NOT AVAILABLE].
- **First 2025.1 check after an upgrade from 2024.1:** the systemd unit text changed ([F16](../reference/findings.md#f16)),
  and the DB containers gain an `environment` (`OVN_NB_DB`, `OVN_SB_DB`, `roles/ovn-db/defaults/main.yml:7-9, :17-18,
  :26-27`), which `compare_container` compares, so every OVN DB container of the batch is restarted, all members at
  once [CODE]. `ovn-northd`'s command also changes (`--ovnsb-db` is now the cluster list without relays,
  `roles/ovn-db/templates/ovn-northd.json.j2:2`).
- **Image start, since 2024.1:** the ovn-base start script ends by sourcing `kolla_ovn_extend_start`, which creates
  the container's log file owned by `openvswitch` when it is not readable (kolla `docker/ovn/ovn-base/extend_start.sh:13`,
  `docker/ovn/ovn-controller/extend_start.sh:3-6`) [CODE]. Kolla-Ansible's manifests, the new relay one included, set
  `/var/log/kolla/openvswitch` to `root:root`, recursively (`roles/ovn-db/templates/ovn-sb-db-relay.json.j2:11-16`)
  [CODE]; what the two ownerships do to logging is [NOT AVAILABLE]. On CentOS Stream 10 and Rocky 10 images the OVN
  packages are `ovn25.03` (kolla `docker/ovn/ovn-base/Dockerfile.j2:11-19`).
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure): `ovn` is
  one of the tags that can restart the containers that Tags §3.1 traces to running VMs [CODE]; what those restarts do to
  running VMs is [NOT AVAILABLE].

### Known limits and open points

- [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane), row "OVN": the sources do not
  establish whether an `ovn-controller` restart re-programs flows on the host, and whether Kolla-Ansible's direct
  `ovn-ctl` call creates and upgrades the DB schema (`roles/ovn-db/defaults/main.yml:120-121, :129-130`).
- **New in 2025.1, [NOT AVAILABLE]:** what a relay restart or a relay change does to the chassis connected to it, and
  the SB gap during the first 2025.1 run described in the key answers. To be confirmed by the community.
- [Q3](../troubleshooting/open-questions.md#q3): "Data-plane loss during an `openvswitch_vswitchd` restart or recreate".
  Status: [NOT AVAILABLE].
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: the OVN images have no one-shot
  branch (no `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` in kolla `docker/ovn/*`, grep).
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), "Operationally notable",
  items (A) to (H), read against 2025.1:
  - the whole DB cluster batch restarts at once (above);
  - a new cluster is seeded from the first `ovn-nb-db`/`ovn-sb-db` host, while a member re-created on an existing
    cluster joins the current leader (`roles/ovn-db/tasks/bootstrap-initial.yml:5-13, :59-67`) [CODE]; there is still
    no backup code (grep of `ansible/roles`: no `ovsdb-client backup`);
  - ovn-controller restarts and chassis settings (above);
  - gateway options are clobbered (above);
  - NB, SB and relay clients connect over plain TCP (`group_vars/all.yml:645-648`), and the DB listeners are set to
    `ptcp:<port>:0.0.0.0` (`roles/ovn-db/tasks/bootstrap-db.yml:30`, `:55`) [CODE];
  - with OVN and `enable_ovs_dpdk`, Kolla-Ansible deploys no Open vSwitch container at all: the openvswitch play
    targets only `enable_ovs_dpdk` false (`site.yml:609, :618`), and the ovs-dpdk containers are enabled only when
    `neutron_plugin_agent in ['openvswitch']` (`roles/ovs-dpdk/defaults/main.yml:10, :24`), while OVN needs
    `neutron_plugin_agent == 'ovn'` (`group_vars/all.yml:952`) [CODE];
  - missing inventory groups are still not caught: the precheck of `ovn-db` checks only free ports and that of
    `ovn-controller` is empty (`roles/ovn-db/tasks/precheck.yml:2-32`, `roles/ovn-controller/tasks/precheck.yml:1`)
    [CODE]. A missing `ovn-sb-db-relay` group with relays on is not checked either.
- [fact sheet A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable), item (C), **changed in
  2025.1**: the NB, SB, northd and controller manifests still have no `config_files`, but `kolla_set_configs --check`
  now compares the `command` (kolla `docker/base/set_configs.py:580-586`), so a command-line change written by
  `genconfig` is applied by the next `deploy-containers`, `deploy` or `reconfigure` [CODE] ([Kolla images
  §3.1](../concepts/kolla-images.md#31-what-is-compared)).
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
| Play | site.yml:635 |
| Tags | ovn, ovn-controller |
| Play host patterns | ovn-controller |
| Node types in play (example inventory) | compute, network |
| Node types running its containers | compute, network |
| Containers | `ovn_controller` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → setup-ovs → flush handlers |
| Task files | check-containers.yml, check.yml, config.yml, config_validate.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, setup-ovs.yml, stop.yml, upgrade.yml |
| Templates | `ovn-controller.json.j2` |
| Handlers (definition order) | Restart ovn-controller container |
| Key variables | `enable_ovn`, `neutron_plugin_agent: ovn`, `neutron_ovn_distributed_fip` |
| Role dependencies | none |

### OVN databases — role `ovn-db`

| Item | Value |
|---|---|
| Play | site.yml:649 |
| Tags | ovn, ovn-db |
| Play host patterns | ovn-nb-db, ovn-northd, ovn-sb-db |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `ovn_northd`, `ovn_nb_db`, `ovn_sb_db`, `ovn_sb_db_relay` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | lookup_cluster (if) → bootstrap-initial (if) → config → check-containers → flush handlers → bootstrap-db (if) |
| Task files | bootstrap-db.yml, bootstrap-initial.yml, check-containers.yml, check.yml, config-relay.yml, config.yml, config_validate.yml, deploy-containers.yml, deploy.yml, lookup_cluster.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `ovn-nb-db.json.j2`, `ovn-northd.json.j2`, `ovn-sb-db-relay.json.j2`, `ovn-sb-db.json.j2`, `ovsdb-relay.json.j2` |
| Handlers (definition order) | Restart ovn-nb-db container; Restart ovn-sb-db container; Restart ovn-sb-db-relay container; Restart ovn-northd container |
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
