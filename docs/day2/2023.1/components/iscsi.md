---
title: iscsid / tgtd
description: Where the study covers iscsid and tgtd (role iscsi), from what the tag runs to the effect of a restart on attached volumes, which the sources do not establish.
tags: [iscsi, bootstrap-servers, dependencies, bugs, unknowns]
---

# iscsid / tgtd

This page is the starting point for the `iscsi` role: the containers `iscsid` and `tgtd`, on the compute, control and
storage nodes of the example inventory, selected by the tag `iscsi`. Its play runs only on hosts where
`enable_iscsid` is true (`site.yml:417-426`), and in 2023.1 `enable_iscsid` is `enable_cinder` and
`enable_cinder_backend_iscsi` only (`group_vars/all.yml:700`; Ussuri also counted `enable_ironic`). Inside the play,
`iscsid` runs on `compute`, `cinder-volume` and `cinder-backup` hosts for cinder, and on `ironic-conductor` hosts when
`enable_ironic` is set; `tgtd` runs only with the LVM backend and `cinder_target_helper: tgtadm`
(`roles/iscsi/defaults/main.yml:6, :15, :61-72`) [CODE]. The lists below say where the study covers how to operate
it, its impact, its dependencies and the evidence, what to check around a run and what stays open; the service card
follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure) (VM impact:
  [NOT AVAILABLE])

No operation page gives a command line for the `iscsi` tag, and no risk register item is about a run of this tag. What
the study says about running it is in the rows linked under [Impact and risk](#impact-and-risk) and in [fact sheet D
§5.2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#52-iscsi-iscsid-tgtd).

### Impact and risk

- **What the tag executes (`iscsi`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `iscsi`

### Dependencies

- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components), [Component dependencies
  §5](dependencies.md#5-compute-node-dependency-summary)

### Evidence

- **Fact sheet:** [fact sheet D
  §5.2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#52-iscsi-iscsid-tgtd)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `iscsid`, `tgtd`)

### Before and after a run

- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `iscsi`:
  safe on its own "with care, per host batch"; the row names no prerequisite.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure): `iscsi` is
  one of the tags that can restart the containers that Tags §3.1 traces to running VMs [CODE]; what those restarts do to
  running VMs is [NOT AVAILABLE].

### Known limits and open points

- [What is not known](../troubleshooting/what-is-not-known.md#storage-and-images), rows `iscsid` and `tgtd`: the sources
  do not establish, for an `iscsid` restart, whether existing sessions are kernel-held and whether attach/detach during
  the window fails; for a `tgtd` restart, whether tgtd loads `targets.conf` itself or keeps targets only in memory, and
  so whether a restart cuts disk I/O for VMs that use LVM volumes from that host. Same table: whether removing the
  `iscsi_info` volume produces a new IQN at the next start, and whether that breaks backend ACLs.
- [fact sheet D §5.2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#52-iscsi-iscsid-tgtd),
  bullets "Host interaction" (bootstrap-servers removes host `open-iscsi` / `iscsi-initiator-utils`), "VM impact
  (NOT AVAILABLE)", "tgtd restart (consequences NOT AVAILABLE)" and "Precheck oddity" (it checks that `iscsi_port` 3260
  is free on the iscsid hosts, but 3260 is the target (tgtd) port).
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  11: both still hold in 2023.1. iscsid runs `iscsid -d 8 -f` (`roles/iscsi/templates/iscsid.json.j2:2`); the precheck
  tests that `iscsi_port` (3260, `group_vars/all.yml:369`) is free on the iscsid hosts while no `iscsid` container
  exists yet (`roles/iscsi/tasks/precheck.yml:17-27`) [CODE].
- New in 2023.1 [CODE]: the `iscsid` and `tgtd` containers no longer mount the `cinder` volume or `/sys/fs/cgroup`, and
  `tgtd` no longer mounts `iscsi_info` (`roles/iscsi/defaults/main.yml:39-57`). The precheck fails on RedHat-family
  hosts when `enable_tgtd` is true (`roles/iscsi/tasks/precheck.yml:29-35`); `cinder_target_helper` defaults to
  `lioadm` there (`group_vars/all.yml:949`), so `tgtd` is not enabled by default on those hosts.
- Ironic without the cinder iSCSI backend [CODE]: the `iscsid` service is enabled for `ironic-conductor` hosts
  (`roles/iscsi/defaults/main.yml:6, :67-68`), but the play only targets `&enable_iscsid_True` hosts (`site.yml:41,
  :422`) and `enable_iscsid` no longer includes `enable_ironic` (`group_vars/all.yml:700`), so in that case the play
  matches no host and no `iscsid` container is deployed. [NOT AVAILABLE] Whether ironic needs one there.
- [fact sheet D §8](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#8-not-available-list):
  NOT AVAILABLE: what an iscsid, tgtd or multipathd restart does to attached volumes under I/O (session state, path
  failover, the guest view); for tgtd, whether the LVM targets come back without a cinder-volume restart.
- [R14](../risk/risk-register.md#r14): a `bootstrap-servers` re-run on a live host removes host packages: `open-iscsi`
  on Debian/Ubuntu always, `iscsi-initiator-utils` on RedHat only with the libvirt container (ansible-collection-kolla
  `roles/packages/defaults/main.yml:24-33`) [CODE].
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 19: the iSCSI initiator name is stable per
  `iscsi_info` volume across restart and recreate [CODE]. [NOT AVAILABLE] Whether removing the volume produces a new IQN
  at the next start, and whether that breaks backend ACLs keyed on the old one.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), [Open
  questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry on `iscsid` or
  `tgtd`.

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py iscsi -->

| Item | Value |
|---|---|
| Play | site.yml:417 |
| Tags | iscsi |
| Play host patterns | iscsid, tgtd |
| Node types in play (example inventory) | compute, control, storage |
| Node types running its containers | compute, control, storage |
| Containers | `iscsid`, `tgtd` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config-host → config → check-containers → flush handlers |
| Task files | check-containers.yml, check.yml, config-host.yml, config.yml, config_validate.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `iscsid.json.j2`, `tgtd.json.j2` |
| Handlers (definition order) | Restart iscsid container; Restart tgtd container |
| Key variables | `enable_iscsid`, `enable_cinder_backend_lvm` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Cinder](cinder.md) — cinder-volume (LVM) depends on this role
- [Nova](nova.md) — nova-compute depends on it for volume attach
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure) — the tags
  that can restart containers traced to running VMs, `iscsi` among them
- [Component dependencies §5](dependencies.md#5-compute-node-dependency-summary) — what lands on a compute host,
  `iscsid` included
- [Components](index.md) — the other component pages
