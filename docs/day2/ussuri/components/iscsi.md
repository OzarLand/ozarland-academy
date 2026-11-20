---
title: iscsid / tgtd
description: Where the study covers iscsid and tgtd (role iscsi), from what the tag runs to the effect of a restart on attached volumes, which the sources do not establish.
tags: [iscsi, bootstrap-servers, dependencies, bugs, unknowns]
---

# iscsid / tgtd

This page is the starting point for the `iscsi` role: the containers `iscsid` and `tgtd`, on the compute, control and
storage nodes of the example inventory, selected by the tag `iscsi`. [Component dependencies
§2](dependencies.md#2-infrastructure-components) lists it "only if `enable_iscsid` (cinder LVM/iSCSI or ironic)". The
lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to check
around a run and what stays open; the service card follows them.

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
  11: iscsid runs at debug `-d 8`; the precheck tests port 3260 on iscsid hosts.
- [fact sheet D §8](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#8-not-available-list):
  NOT AVAILABLE: what an iscsid, tgtd or multipathd restart does to attached volumes under I/O (session state, path
  failover, the guest view); for tgtd, whether the LVM targets come back without a cinder-volume restart.
- [R14](../risk/risk-register.md#r14): a `bootstrap-servers` re-run on a live host removes host packages (`open-iscsi`,
  `libvirt*`, `chrony`, …).
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
| Play | site.yml:512 |
| Tags | iscsi |
| Play host patterns | iscsid, tgtd |
| Node types in play (example inventory) | compute, control, storage |
| Node types running its containers | compute, control, storage |
| Containers | `iscsid`, `tgtd` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config-host → config → check-containers → flush handlers |
| Task files | check-containers.yml, check.yml, config-host.yml, config.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `iscsid.json.j2`, `tgtd.json.j2` |
| Handlers (definition order) | Restart iscsid container; Restart tgtd container |
| Key variables | `enable_iscsid`, `enable_cinder_backend_lvm` |
| Role dependencies | `common` (meta) |

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
