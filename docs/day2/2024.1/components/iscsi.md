---
title: iscsid / tgtd
description: Where the 2024.1 study covers iscsid and tgtd (role iscsi), from the configfs load and what the tag runs to restart effects the sources do not establish.
tags: [iscsi, bootstrap-servers, dependencies, bugs, unknowns]
---

# iscsid / tgtd

This page is the starting point for the `iscsi` role: the containers `iscsid` and `tgtd`, on the compute, control and
storage nodes of the example inventory (`inventory/multinode:305-311`), selected by the tag `iscsi`. Its play runs only
on hosts where `enable_iscsid` is true (`site.yml:439-452`, pattern `&enable_iscsid_True` at `:444`), and in 2024.1
`enable_iscsid` is still `enable_cinder` and `enable_cinder_backend_iscsi` only (`group_vars/all.yml:794`), as in
2023.1. Inside the play, `iscsid` runs on `compute`, `cinder-volume` and `cinder-backup` hosts for cinder, and on
`ironic-conductor` hosts when `enable_ironic` is set; `tgtd` runs only with the LVM backend and
`cinder_target_helper: tgtadm` (`roles/iscsi/defaults/main.yml:6, :15, :62-73`) [CODE]. Before any container task, the
play loads the `configfs` kernel module on the `iscsid` hosts ([Before and after a run](#before-and-after-a-run)). The
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
- **Sequence** [CODE]: `deploy`, `reconfigure` and `upgrade` all run `deploy.yml`
  (`roles/iscsi/tasks/reconfigure.yml:2`, `upgrade.yml:2`): `config-host.yml` (the `configfs` module), `config.yml`
  (config directories and `config.json`), `check-containers.yml`, then a flush of the handlers
  (`roles/iscsi/tasks/deploy.yml:2-9`). The handlers `Restart iscsid container` and `Restart tgtd container` are skipped
  when `kolla_action` is `config` (`roles/iscsi/handlers/main.yml:2-17`, `:19-34`).

### Dependencies

- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components), [Component dependencies
  §5](dependencies.md#5-compute-node-dependency-summary)
- **Host side** [CODE]: both containers are privileged with the host IPC namespace and bind-mount `/dev`, `/run`,
  `/lib/modules` (read-only) and `/sys/kernel/config` as `/configfs` (`roles/iscsi/defaults/main.yml:8-9, :17-18,
  :40-58`); `iscsid` also mounts the `iscsi_info` volume as `/etc/iscsi` (`:49`).

### Evidence

- **Fact sheet:** [fact sheet D
  §5.2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#52-iscsi-iscsid-tgtd)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `iscsid`, `tgtd`).
  The kolla `docker/iscsid` and `docker/tgtd` directories are identical to 2023.1's; the `iscsid` start script writes
  a new initiator name only when `/etc/iscsi/initiatorname.iscsi` is missing (kolla `docker/iscsid/extend_start.sh:3-7`)
  [CODE].
- **Role diff 2023.1 → 2024.1** [CODE]: the module rename (`kolla_docker` → `kolla_container`), the `/run` mount
  ([Known limits and open points](#known-limits-and-open-points)), and a new variable `tgtd_interface_address`
  (default `api_interface_address`, `roles/iscsi/defaults/main.yml:22`), now used for the tgtd portal
  (`roles/iscsi/templates/tgtd.json.j2:2`) and the port precheck (`roles/iscsi/tasks/precheck.yml:17-27`). Nothing
  else in the role changed.

### Before and after a run

- **`configfs` is loaded and persisted first** [CODE]. `config-host.yml` imports the `module-load` role with
  `modules: [{name: configfs}]`, on hosts of the `iscsid` group where `iscsid` is enabled
  (`roles/iscsi/tasks/config-host.yml:2-10`). The `module-load` role runs `modprobe configfs` and writes
  `/etc/modules-load.d/configfs.conf` (from `roles/module-load/templates/module-load.conf.j2:1-2`), both skipped when
  `kolla_action` is `config` (`roles/module-load/tasks/main.yml:4-27`). So `genconfig` does not load the module, while
  `deploy`, `reconfigure` and `upgrade` do, on every run (the tasks are idempotent). **Still holds in 2024.1**:
  `config-host.yml` and the `module-load` role are unchanged since 2023.1.
- The condition names only the `iscsid` side: a host that runs `tgtd` but is not an enabled `iscsid` host gets no
  `configfs` load from this role, although `tgtd` also mounts `/sys/kernel/config` (`roles/iscsi/defaults/main.yml:58`).
  In the example inventory every `tgtd` host (`storage`) is also in the `iscsid` group (`inventory/multinode:305-311`)
  [CODE]. [NOT AVAILABLE] Whether `tgtd` needs `configfs`.
- The role never unloads `configfs` and never removes `/etc/modules-load.d/configfs.conf`: it passes no `state` to
  `module-load` (`roles/iscsi/tasks/config-host.yml:6-7`), and `stop.yml` only stops the containers
  (`roles/iscsi/tasks/stop.yml:2-6`) [CODE].
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `iscsi`:
  safe on its own "with care, per host batch"; the row names no prerequisite.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure): `iscsi` is
  one of the tags that can restart the containers that Tags §3.1 traces to running VMs [CODE]; what those restarts do to
  running VMs is [NOT AVAILABLE].
- **Settings that the drift check cannot see** [CODE]: both `config.json` files have `"config_files": []`, so every
  setting is in the command: `iscsid -d 8 -f`, and `tgtd … --iscsi portal=<tgtd_interface_address>:<iscsi_port>`
  (`roles/iscsi/templates/iscsid.json.j2:2-3`, `tgtd.json.j2:2-3`). `kolla_set_configs --check` compares only
  `config_files` entries (kolla `docker/base/set_configs.py:556-559`, [F14](../reference/findings.md#f14)). A normal
  `deploy`/`reconfigure` applies a change of `tgtd_interface_address` or `iscsi_port`, because the changed `config.json`
  task notifies the restart handler (`roles/iscsi/tasks/config.yml:15-26`); after a separate `genconfig`,
  `deploy-containers` does not ([Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 1).
- **First 2024.1 check of a container that 2023.1 created** [CODE]: the systemd unit text changed
  ([F16](../reference/findings.md#f16)), so a container that no 2024.1 run has recreated or restarted yet is reported as
  changed and
  restarted at its first 2024.1 `deploy`/`reconfigure` check.

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
  11: both still hold in 2024.1. iscsid runs `iscsid -d 8 -f` (`roles/iscsi/templates/iscsid.json.j2:2`); the precheck
  tests that `iscsi_port` (3260, `group_vars/all.yml:442`) is free on `tgtd_interface_address` of the iscsid hosts
  while no `iscsid` container exists yet (`roles/iscsi/tasks/precheck.yml:17-27`) [CODE].
- **Changed in 2024.1: the `/run` mount** [CODE]. 2023.1 mounted `/run/:/run/:shared`; 2024.1 mounts `/run:/run:shared`
  with Docker and `/run:/run` without `:shared` with Podman (`roles/iscsi/defaults/main.yml:46, :56`), and appends
  `run_default_volumes_<engine>` to both containers' volumes (`:10, :19`): nothing with Docker, five `/run/...:shared`
  sub-mounts with Podman (`group_vars/all.yml:165-172`). The volume check compares the bind strings as sets, without
  normalising a trailing slash (`module_utils/kolla_docker_worker.py:124-144`,
  `module_utils/kolla_container_worker.py:400-434`). [NOT AVAILABLE: Docker semantics] Whether Docker reports the 2023.1
  bind with its trailing slashes, and so whether this alone flags drift; the unit change above flags it anyway.
- Still holds in 2024.1 [CODE]: the precheck fails on RedHat-family hosts when `enable_tgtd` is true
  (`roles/iscsi/tasks/precheck.yml:29-35`); `cinder_target_helper` defaults to `lioadm` there
  (`group_vars/all.yml:1045`), so `tgtd` is not enabled by default on those hosts. The containers mount neither the
  `cinder` volume nor `/sys/fs/cgroup`, and `tgtd` does not mount `iscsi_info` (`roles/iscsi/defaults/main.yml:40-58`).
- Ironic without the cinder iSCSI backend [CODE]: the `iscsid` service is enabled for `ironic-conductor` hosts
  (`roles/iscsi/defaults/main.yml:6, :68-69`), but the play only targets `&enable_iscsid_True` hosts (`site.yml:44,
  :444`) and `enable_iscsid` does not include `enable_ironic` (`group_vars/all.yml:794`), so in that case the play
  matches no host and no `iscsid` container is deployed. **Still holds in 2024.1.** [NOT AVAILABLE] Whether ironic
  needs one there.
- [fact sheet D §8](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#8-not-available-list):
  NOT AVAILABLE: what an iscsid, tgtd or multipathd restart does to attached volumes under I/O (session state, path
  failover, the guest view); for tgtd, whether the LVM targets come back without a cinder-volume restart.
- [R14](../risk/risk-register.md#r14): a `bootstrap-servers` re-run on a live host removes host packages: `open-iscsi`
  on Debian/Ubuntu always, `iscsi-initiator-utils` on RedHat only with the libvirt container (ansible-collection-kolla
  `roles/packages/defaults/main.yml:25-34`, `roles/packages/tasks/main.yml:15-23`) [CODE].
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 19: the iSCSI initiator name is stable per
  `iscsi_info` volume across restart and recreate [CODE]. [NOT AVAILABLE] Whether removing the volume produces a new IQN
  at the next start, and whether that breaks backend ACLs keyed on the old one.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), [Open
  questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry specific to
  `iscsid` or `tgtd`; [F14](../reference/findings.md#f14) and [F16](../reference/findings.md#f16) apply to them as to
  other containers.

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py iscsi -->

| Item | Value |
|---|---|
| Play | site.yml:439 |
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
- [Repository architecture §5](../concepts/repository-architecture.md#5-shared-helper-roles) — the `module-load` helper
  role and the roles that use it
- [Components](index.md) — the other component pages
