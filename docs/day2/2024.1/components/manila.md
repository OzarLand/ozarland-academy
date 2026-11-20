---
title: Manila
description: Where the 2024.1 study covers Manila (role manila), from its fact sheet and the new external Ceph layout to the neutron agents on manila-share hosts.
tags: [manila, neutron, one-shot, dependencies, bugs, unknowns]
---

# Manila

This page is the starting point for Manila, the `manila` role: the containers `manila_api`, `manila_scheduler`,
`manila_share` and `manila_data`, on the control and network nodes of the example inventory (`manila` is a child of
`control`, `inventory/multinode:140-141`; `manila-share` a child of `network`, `inventory/multinode:320-321`), selected
by the tag `manila` (`site.yml:786-801`) [CODE]. The manila-share hosts also get neutron agents ([Component dependencies
§3](dependencies.md#3-control-plane-services)): the neutron play includes `manila-share` (`site.yml:671-693`; [fact
sheet D §4.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#41-plays)). The lists below say
where the study covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and
what stays open; the service card follows them.

## Where to look

### Operate

No operation page gives a command line for the `manila` tag, and the tag has no row of its own in [Tags
§3](../risk/tags.md#3-what-a-tag-really-executes-master-table) or in the [Tag index](../risk/tag-index.md). What the
study says about running it is in fact sheet D: the plays the tag selects
([§4.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#41-plays)) and the task flow per
action ([§4.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#43-task-flow)). The tag also
selects the manila include of the loadbalancer play (`site.yml:218-222`) [CODE].

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet D §4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#4-manila)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `manila-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

### Before and after a run

- [fact sheet D §4.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#43-task-flow): the flow
  is unchanged since 2023.1 apart from the module rename (`kolla_docker` → `kolla_container`). `reconfigure` imports
  `deploy` (`roles/manila/tasks/reconfigure.yml:2`), which runs clone (dev mode only), register, config,
  check-containers, bootstrap (DB and DB user, then `bootstrap_manila`), flush (`roles/manila/tasks/deploy.yml:2-14`,
  `roles/manila/tasks/bootstrap.yml:2-38`). `upgrade` runs config, check-containers, `bootstrap_service.yml` and flush,
  without register or DB creation (`roles/manila/tasks/upgrade.yml:2-9`) [CODE].
- **External Ceph: changed in 2024.1** [CODE]. With `enable_manila_backend_cephfs_native` or `_cephfs_nfs`, config
  still includes `external_ceph.yml` on manila-share hosts (`roles/manila/tasks/config.yml:15-18`), but the file now
  follows the multi-cluster layout:
  1. The Ceph backends moved to their own list, `manila_ceph_backends`, each with a `cluster` (default `ceph`) and a
     `share_name` (`roles/manila/defaults/main.yml:240-255`). `manila_enabled_backends` appends the enabled Ceph
     backends after the other ones (`:257`), so `enabled_share_backends` lists them last
     (`roles/manila/templates/manila-share.conf.j2:3`).
  2. A sub-directory `manila-share/ceph` is created (`roles/manila/tasks/external_ceph.yml:2-14`). For each enabled
     Ceph backend, `<cluster>.conf` is now built by `merge_configs` from `/etc/kolla/config/manila/<cluster>.conf` and
     `/etc/kolla/config/manila/manila-share/<cluster>.conf` (`:16-29`; 2023.1 rendered one `ceph.conf` with
     `template`), and the keyring is read from `manila/<cluster>.client.manila.keyring` (`:31-42`;
     `ceph_manila_keyring` is now `client.<user>.keyring`, `group_vars/all.yml:1178,1186`). With the default cluster
     `ceph`, the operator's source names are the same as in 2023.1 (`ceph.conf`, `ceph.client.manila.keyring`).
  3. Both files land in `/etc/kolla/manila-share/ceph/`, with mode `0660` (the 2023.1 keyring was `0600`), and
     `config.json` now copies that whole directory to `/etc/ceph` instead of two named files
     (`roles/manila/templates/manila-share.json.j2:9-15`). The share sections point to `/etc/ceph/<cluster>.conf` and
     `cephfs_cluster_name = <cluster>` (`manila-share.conf.j2:108-142`), so with the default cluster the paths inside
     the container stay `/etc/ceph/ceph.conf` and `/etc/ceph/ceph.client.manila.keyring`.
  4. Consequence for the first 2024.1 `deploy`, `reconfigure` or `upgrade` with a CephFS backend: the `config.json`
     template task changes and notifies `Restart manila-share container` (`roles/manila/tasks/config.yml:43-54`), and
     each Ceph file task notifies the same handler when it writes a new file (`external_ceph.yml:28-29,41-42`). No task
     of the role removes the 2023.1 files `manila-share/ceph.conf` and `manila-share/ceph.client.manila.keyring` (no
     `state: absent` under `roles/manila/`); they stay in the config directory but are no longer listed in
     `config.json`.
- **Other 2024.1 changes to the containers** [CODE]: `manila_share` and `manila_data` mount `/run` as
  `/run:/run:shared` under Docker (2023.1 `/run/:/run/:shared`) and get `run_default_volumes_<engine>`, empty for
  Docker (`roles/manila/defaults/main.yml:39,48,162,186`, `group_vars/all.yml:165-172`); `/dev/shm` is mounted only with
  `om_enable_queue_manager` (default `false`, `group_vars/all.yml:269`). [NOT AVAILABLE] Whether the Docker engine
  reports the old `/run/` bind in a form that `compare_volumes` sees as different
  (`module_utils/kolla_docker_worker.py:124-144`): the containers restart at their first 2024.1 check anyway, because
  the systemd unit text changed ([F16](../reference/findings.md#f16)). `manila.conf` gets `rabbit_quorum_queue = true`
  by default (`roles/manila/templates/manila.conf.j2:71-72`, `group_vars/all.yml:268`;
  [F17](../reference/findings.md#f17)).
- [fact sheet D §4.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#41-plays): in the
  default inventory `manila-share` is a child of `network`, and the `openvswitch` children include `manila-share`
  (`inventory/multinode:105-108,320-321`); the OVS agent, `openvswitch_db` and `openvswitch_vswitchd` run on
  manila-share hosts only with the generic backend (`roles/neutron/defaults/main.yml:36`,
  `roles/openvswitch/defaults/main.yml:11,27`) [CODE]. Still holds in 2024.1.
- [Reconfigure Neutron §2](../operations/reconfigure-neutron.md#2-execution-and-targets): `-t neutron reconfigure` runs
  the neutron play on `neutron-server`, every agent group, every compute and `manila-share` (`site.yml:671-693`) [CODE].
- [fact sheet D
  §4.6](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#46-operationally-notable): Kolla does
  not create share types, the service image or networks (no such task in `roles/manila/tasks/` in 2024.1) [CODE].

### Known limits and open points

- [fact sheet D §4.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#43-task-flow): the
  Ussuri `fix_cephfs_owner.yml`, which mounted CephFS with `secret=<keyring secret>` on the command line, is still
  absent in 2024.1: no task under `roles/manila/tasks/` mounts anything or passes `secret=` [CODE].
- [fact sheet D
  §4.6](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#46-operationally-notable),
  "Operationally notable", three points, checked against 2024.1 [CODE]: Kolla does not create share types, the service
  image or networks (still holds); the generic backend's service-instance credentials default to `manila`/`manila`
  (still holds, `roles/manila/defaults/main.yml:211-212`); endpoints use `kolla_internal_fqdn` and
  `kolla_external_fqdn` directly: **changed in 2024.1**, they use `manila_internal_fqdn` and `manila_external_fqdn`
  through the `kolla_url` filter (`roles/manila/defaults/main.yml:199-200`), which default to `kolla_internal_fqdn` and
  `kolla_external_fqdn` (`group_vars/all.yml:461-462`), and the public endpoint uses `manila_api_public_port`, the
  single external frontend port when `haproxy_single_external_frontend` is set (`group_vars/all.yml:463-465`).
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  6: CephFS secret on the command line on every deploy; policy copy has no `become`; service-instance password defaults
  to `manila`; neutron `host_in_groups` for manila-share are asymmetric (OVS: generic only; LB: any backend). In 2024.1
  the CephFS point is still gone (see above); the other three still hold (`roles/manila/tasks/config.yml:101-112`,
  `roles/manila/defaults/main.yml:212`, `roles/neutron/defaults/main.yml:36,60`) [CODE].
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  15: Barbican and other bootstraps (octavia, manila, ceilometer, masakari, zun, cyborg) re-run their DB sync container
  on every deploy/reconfigure (manila: `roles/manila/tasks/deploy.yml:11`, `roles/manila/tasks/bootstrap.yml:38`)
  [CODE].
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- The share sections of `manila-share.conf.j2` loop over every entry of `manila_ceph_backends` whose `driver` matches,
  guarded only by the global `enable_manila_backend_cephfs_native` / `_cephfs_nfs` flag, not by the entry's `enabled`
  (`roles/manila/templates/manila-share.conf.j2:108-143`), while the file tasks skip disabled entries
  (`roles/manila/tasks/external_ceph.yml:26,40`) [CODE]. With the default list (one entry per driver, each enabled by
  the same flag, `roles/manila/defaults/main.yml:240-255`) the two agree; [NOT AVAILABLE] how Manila behaves with an
  operator-defined list where they do not.
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): fact sheet D has its own
  NOT AVAILABLE list, and its §4.3 is among the sections that contain NOT AVAILABLE marks.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), [Open
  questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry specific to
  Manila.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py manila -->

| Item | Value |
|---|---|
| Play | site.yml:786 |
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
- [Findings F16](../reference/findings.md#f16) — why the first 2024.1 check restarts the manila containers
- [Components](index.md) — the other component pages
