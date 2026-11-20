---
title: Cinder
description: Where the study covers Cinder (role cinder), from the single-service reconfigure and the 60 s stop timeout to dependencies, known bugs and open points.
tags: [cinder, reconfigure, one-shot, risk, dependencies, bugs, unknowns]
---

# Cinder

This page is the starting point for Cinder, the `cinder` role: the containers `cinder_api`, `cinder_scheduler`,
`cinder_volume` and `cinder_backup`, on the control and storage nodes of the example inventory, selected by the tag
`cinder`. `iscsid` and `tgtd` are in the `iscsi` play, not under `-t cinder` ([Tags
§3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites)). The lists below say
where the study covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and
what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)

No operation page gives a command line for the `cinder` tag. The scenario above describes
`kolla-ansible -t <svc> reconfigure` for an API service such as keystone, glance, cinder, heat or placement; its command
example is keystone ([Reconfigure a single service
§1.1](../operations/reconfigure-a-service.md#11-reconfigure-a-single-service)).

### Impact and risk

- **What the tag executes (`cinder`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row
  `<svc>`; [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `<svc>` API service
- **Risks:** [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet C §3](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#3-cinder)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `cinder-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 6 (workload gates): no live migrations,
  resizes, image uploads or volume migrations in flight on the targeted hosts; one of its two checks is
  `openstack volume list --status *ing`.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service: safe on its own "yes, it is the intended unit; it still runs Keystone registration and DB sync"; batch with
  `ANSIBLE_SERIAL`. Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP. Glance and cinder
  transfers in progress are SIGKILLed after 60 s (`docker_graceful_timeout`, `group_vars/all.yml:140,152`;
  `module_utils/kolla_systemd_worker.py:33`; [R24](../risk/risk-register.md#r24)).
- [fact sheet C §3.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#38-operational-notes), item 7:
  the cinder role itself does not target computes; enabling `enable_cinder_backend_iscsi`/LVM also flips glance-api to
  privileged with `/dev`, so glance-api is recreated. In 2023.1 `cinder_backend_ceph` also makes glance-api privileged,
  without `/dev` (`roles/glance/defaults/main.yml:10,192-193`) [CODE].
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `ANSIBLE_SERIAL=1` for haproxy changes;
  `--skip-tags haproxy` when you don't intend to change frontends.
- [R24](../risk/risk-register.md#r24), precautions for the container stop timeout (60 s in 2023.1: the systemd unit
  stops the container with `docker stop -t <docker_graceful_timeout>`): drain long operations before restarts; raise
  `docker_graceful_timeout` if needed (it reaches the unit on the next restart).
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible -t <svc> genconfig`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, e.g.
  `cinderv3` for cinder (the only service in `cinder_ks_services` in 2023.1, `roles/cinder/defaults/main.yml:319-325`),
  the API answers through the VIP, the container start times show which hosts restarted, and `docker ps --filter
  name=haproxy` shows whether HAProxy restarted.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `cinder`: no
  `host`/`backend_host`/`cluster`; etcd coordination uses only the first etcd host; Ceph backup driver default without a
  Ceph config. Status: [CODE]. Checked against 2023.1: `cinder.conf.j2` still sets no `host`, `backend_host` or
  `cluster`; the etcd item no longer holds as written: with `cinder_coordination_backend: etcd` (the default only when
  Redis is disabled and etcd enabled, `group_vars/all.yml:951`) the `backend_url` is
  `etcd3+<proto>://kolla_internal_fqdn:etcd_client_port`, i.e. the internal VIP, where the etcd role has a HAProxy
  frontend (`roles/cinder/templates/cinder.conf.j2:245-253`, `roles/etcd/defaults/main.yml:26-32`); the backup driver
  still defaults to `ceph` (`group_vars/all.yml:954`, `roles/cinder/templates/cinder.conf.j2:27-30`) while
  `ceph.conf` is copied only with `cinder_backend_ceph` (`roles/cinder/tasks/config.yml:15-19`) [CODE].
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored": an Ussuri
  finding that no longer holds as written in 2023.1. The role handlers pass `docker_common_options`, which carries
  `graceful_timeout: "{{ docker_graceful_timeout }}"` (60 s) and `client_timeout` (120 s) (`group_vars/all.yml:105,140,
  152-153`), and the container's systemd unit stops it with `docker stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:33`). On every restart, a service still running 60 s after SIGTERM is killed
  with its in-flight work (heat-engine, cinder copies, glance uploads); the 10 s value is only the module default when
  no `graceful_timeout` is passed (`module_utils/kolla_docker_worker.py:438-440,462-464`) [CODE]
  ([R24](../risk/risk-register.md#r24)).
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [fact sheet C §3.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#38-operational-notes),
  "Operational notes", nine items: no `host`/`backend_host`/`cluster` set in cinder.conf; cinder-volume restart impact;
  cinder-backup restart; upgrade restarts every cinder-volume and cinder-backup at once; oddity: backup driver vs. ceph
  files; multipath is never configured; compute-host touchpoints; external Ceph needs cinder-volume and cinder-backup
  hosts in the `storage` group; the sanity check (if enabled) creates a 1 GB volume on every deploy/reconfigure.
  Checked against 2023.1 [CODE]:
  - the upgrade still restarts every cinder container of the play at once (handlers, `kolla_serial` 0 by default,
    `site.yml:519-530`), and then a second time: after the flush, `reload.yml` restarts every enabled cinder container
    "to remove RPC version pin", after a `cinder_rpc_version_startup_delay` pause (30 s) that only runs on `upgrade`;
    the online data migration runs last (`roles/cinder/tasks/upgrade.yml:21-44`, `roles/cinder/tasks/reload.yml:2-9`,
    `roles/cinder/handlers/main.yml:78-88`, `roles/cinder/defaults/main.yml:229`);
  - the cinder role still sets no multipath option (no `multipath` in `roles/cinder/`); 2023.1 has a separate
    `multipathd` play, off by default (`site.yml:428`, `group_vars/all.yml:714`);
  - `external_ceph.yml` copies `ceph.conf` and keyrings to the hosts of each service's own group (`cinder-volume`,
    `cinder-backup`), with no reference to the `storage` group (`roles/cinder/tasks/external_ceph.yml:13-15,30`);
  - the sanity check does not exist in 2023.1: the role has no `check.yml` and `tasks/deploy.yml` has no check step
    (`roles/cinder/tasks/deploy.yml:1-14`).
- [fact sheet C §8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#8-not-available-list),
  "NOT AVAILABLE list", items 5 to 7: NOT AVAILABLE: whether cinder-backup works with default
  `cinder_backup_driver=ceph` and `cinder_backend_ceph=no`; whether the volumes owned by one of several RBD
  cinder-volume nodes can still be managed while that node is down, and what state an in-flight create-from-image is in
  after a cinder-volume restart; Cinder RPC pinning after `kolla-ansible upgrade`. In 2023.1 the role restarts all
  cinder services after an upgrade to remove the RPC version pin (`roles/cinder/tasks/reload.yml:2`); whether the pin
  is in fact lifted is service-side behaviour: [NOT AVAILABLE].
- [fact sheet C §6][sheet-c-6]: a reconfigure with a bumped image tag runs cinder's `db sync` without its online data
  migration step (the bootstrap container sets `KOLLA_BOOTSTRAP`, which runs `cinder-manage db sync`, not `KOLLA_OSM`;
  `KOLLA_OSM` is set only by `upgrade.yml`: `roles/cinder/tasks/bootstrap_service.yml:11`, kolla
  `docker/cinder/cinder-api/extend_start.sh:6-14`, `roles/cinder/tasks/upgrade.yml:26-44`); whether this leaves cinder
  in a partially upgraded state is NOT AVAILABLE.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 10: recursive chown on data volumes at every
  start: `kolla_set_configs` makes one `chown` per file of the `cinder` volume, twice for cinder-volume, on every
  `COPY_ALWAYS` start (`roles/cinder/templates/cinder-volume.json.j2:38-43`, kolla
  `docker/cinder/cinder-volume/extend_start.sh:3-5`) [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): fact sheet C has its own
  NOT AVAILABLE list, and its §3.8 is among the sections that contain NOT AVAILABLE marks.
- [Open questions](../troubleshooting/open-questions.md) has no entry on Cinder.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py cinder -->

| Item | Value |
|---|---|
| Play | site.yml:519 |
| Tags | cinder |
| Play host patterns | cinder-api, cinder-backup, cinder-scheduler, cinder-volume |
| Node types in play (example inventory) | control, storage |
| Node types running its containers | control, storage |
| Containers | `cinder_api`, `cinder_scheduler`, `cinder_volume`, `cinder_backup` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, external_ceph.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, reload.yml, stop.yml, upgrade.yml |
| Templates | `cinder-api.json.j2`, `cinder-backup.json.j2`, `cinder-scheduler.json.j2`, `cinder-volume.json.j2`, `cinder-wsgi.conf.j2`, `cinder.conf.j2` |
| Handlers (definition order) | Restart cinder-api container; Restart cinder-scheduler container; Restart cinder-volume container; Restart cinder-backup container; Wait for cinder services to update service versions |
| Key variables | `enable_cinder`, `enable_cinder_backend_*`, `cinder_backend_ceph`, `cinder_backup_driver`, `cinder_coordination_backend` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — what `-t <svc> reconfigure` runs for an API
  service such as cinder, with the risks and the verification
- [iscsid / tgtd](iscsi.md) — the `iscsi` role, on which cinder-volume (LVM) depends
- [Glance](glance.md) — enabling the cinder iSCSI/LVM or Ceph backend recreates glance-api
- [Nova](nova.md) — Nova needs Cinder for volume-backed boots
- [R24](../risk/risk-register.md#r24) — cinder-volume copies are among the in-flight work killed 60 s
  (`docker_graceful_timeout`) after SIGTERM
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages

[sheet-c-6]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#6-summary-matrix-what-reconfigure-does-per-role
