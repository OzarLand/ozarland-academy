---
title: Manila
description: Where the study covers Manila (role manila), which has no operation page of its own, from its fact sheet to the neutron agents on manila-share hosts.
tags: [manila, neutron, one-shot, dependencies, bugs, unknowns]
---

# Manila

This page is the starting point for Manila, the `manila` role: the containers `manila_api`, `manila_scheduler`,
`manila_share` and `manila_data`, on the control and network nodes of the example inventory, selected by the tag
`manila`. The manila-share hosts also get neutron agents ([Component dependencies
§3](dependencies.md#3-control-plane-services)): the neutron play includes `manila-share` ([fact sheet D
§4.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#41-plays)). The lists below say where the
study covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays
open; the service card follows them.

## Where to look

### Operate

No operation page gives a command line for the `manila` tag, and the tag has no row of its own in [Tags
§3](../risk/tags.md#3-what-a-tag-really-executes-master-table) or in the [Tag index](../risk/tag-index.md). What the
study says about running it is in fact sheet D: the plays the tag selects
([§4.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#41-plays)) and the task flow per action
([§4.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#43-task-flow)).

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet D §4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#4-manila)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `manila-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

### Before and after a run

- [fact sheet D §4.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#43-task-flow):
  `reconfigure` = `deploy`: register, config, check-containers, bootstrap (DB, then `bootstrap_manila`), flush, then
  `fix_cephfs_owner.yml` when cephfs_native is enabled and the host is in manila-share. In 2023.1 the flow is clone (dev
  mode only), register, config, check-containers, bootstrap (DB, then `bootstrap_manila`), flush, and it ends there:
  `fix_cephfs_owner.yml` no longer exists (`roles/manila/tasks/reconfigure.yml`, `roles/manila/tasks/deploy.yml:1-14`,
  `roles/manila/tasks/bootstrap.yml:2-38`). With `enable_manila_backend_cephfs_native` or `_cephfs_nfs`, config now
  includes `external_ceph.yml` on manila-share hosts, which copies `ceph.conf` and the keyring
  (`roles/manila/tasks/config.yml:15-18`, `roles/manila/tasks/external_ceph.yml:2-33`) [CODE].
- [fact sheet D §4.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#41-plays): in the default
  inventory `manila-share` is a child of `network`, and the `openvswitch` children include `manila-share`; the OVS
  agent, `openvswitch_db` and `openvswitch_vswitchd` run on manila-share hosts only with the generic backend
  (`inventory/multinode:121-126,363-364`; `roles/neutron/defaults/main.yml:35`,
  `roles/openvswitch/defaults/main.yml:11,27`) [CODE].
- [Reconfigure Neutron §2](../operations/reconfigure-neutron.md#2-execution-and-targets): `-t neutron reconfigure` runs
  the neutron play on `neutron-server`, every agent group, every compute and `manila-share`.
- [fact sheet D
  §4.6](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#46-operationally-notable): Kolla does
  not create share types, the service image or networks (no such task in `roles/manila/tasks/` in 2023.1).

### Known limits and open points

- [fact sheet D §4.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#43-task-flow):
  `fix_cephfs_owner.yml` runs on every deploy/reconfigure and mounts CephFS with `secret=<keyring secret>` on the
  command line. Security (NOT AVAILABLE): whether the secret appears in the process list and in Ansible logs at `-v`.
  This does not apply to 2023.1: the role has no `fix_cephfs_owner.yml` and no task under `roles/manila/tasks/`
  mounts anything or passes `secret=` [CODE].
- [fact sheet D
  §4.6](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#46-operationally-notable),
  "Operationally notable", three points: Kolla does not create share types, the service image or networks; the generic
  backend's service-instance credentials default to `manila`/`manila`; endpoints use `kolla_internal_fqdn` and
  `kolla_external_fqdn` directly. All three still hold in 2023.1 (`roles/manila/defaults/main.yml:193-194,205-206`)
  [CODE].
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  6: CephFS secret on the command line on every deploy; policy copy has no `become`; service-instance password defaults
  to `manila`; neutron `host_in_groups` for manila-share are asymmetric (OVS: generic only; LB: any backend). In
  2023.1 the CephFS point is gone (see above); the other three still hold (`roles/manila/tasks/config.yml:101-112`,
  `roles/manila/defaults/main.yml:206`, `roles/neutron/defaults/main.yml:35,59`) [CODE].
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  15: Barbican and other bootstraps (octavia, manila, ceilometer, masakari, zun, cyborg) re-run their DB sync container
  on every deploy/reconfigure (manila: `roles/manila/tasks/deploy.yml:11`, `roles/manila/tasks/bootstrap.yml:38`).
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): fact sheet D has its own
  NOT AVAILABLE list, and its §4.3 is among the sections that contain NOT AVAILABLE marks.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), [Open
  questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry on Manila.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py manila -->

| Item | Value |
|---|---|
| Play | site.yml:714 |
| Tags | manila |
| Play host patterns | manila-api, manila-data, manila-share, manila-scheduler |
| Node types in play (example inventory) | control, network |
| Node types running its containers | control, network |
| Containers | `manila_api`, `manila_scheduler`, `manila_share`, `manila_data` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | clone (if) → register → config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, external_ceph.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `manila-api.json.j2`, `manila-data.json.j2`, `manila-scheduler.json.j2`, `manila-share.conf.j2`, `manila-share.json.j2`, `manila.conf.j2` |
| Handlers (definition order) | Restart manila-api container; Restart manila-data container; Restart manila-scheduler container; Restart manila-share container |
| Key variables | `enable_manila`, `enable_manila_backend_*` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [fact sheet D §4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#4-manila) — the per-role
  evidence: plays, services, task flow, config and dependencies
- [Neutron](neutron.md) — the neutron play includes `manila-share`
- [Open vSwitch](openvswitch.md) — the `openvswitch` group includes `manila-share`
- [Component dependencies §3](dependencies.md#3-control-plane-services) — Manila's config references Glance, Neutron,
  Nova, Cinder and Ceph (CephFS)
- [Components](index.md) — the other component pages
