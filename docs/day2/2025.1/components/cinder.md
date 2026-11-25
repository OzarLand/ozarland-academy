---
title: Cinder
description: Where the 2025.1 study covers Cinder (role cinder), from the multi-cluster Ceph layout and the 60 s stop timeout to the upgrade restarts and open points.
tags: [cinder, reconfigure, one-shot, risk, dependencies, bugs, unknowns]
---

# Cinder

This page is the starting point for Cinder, the `cinder` role: the containers `cinder_api`, `cinder_scheduler`,
`cinder_volume` and `cinder_backup` (`roles/cinder/defaults/main.yml:2-60`), on the control and storage nodes of the
example inventory (`cinder-api` and `cinder-scheduler` on `cinder`, i.e. `control`; `cinder-volume` and
`cinder-backup` on `storage`: `inventory/multinode:110-111`, `inventory/multinode:286-297`), selected by the tag
`cinder` (`site.yml:574-589`). `iscsid` and `tgtd` are in the `iscsi` play, not under `-t cinder` ([Tags
§3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites)).

**Changed in 2025.1** [CODE]:
- **Two new prechecks can stop an upgrade with several `cinder-volume` hosts.** `kolla-ansible prechecks` now fails
  when `cinder-volume` has more than one host and `cinder_cluster_name` is empty, and when it has exactly one host and
  `cinder_cluster_name` is set (`roles/cinder/tasks/precheck.yml:92-115`); `cinder_cluster_skip_precheck` skips both
  (`roles/cinder/defaults/main.yml:381-382`). It also fails when `cinder_backend_ceph` is on, `cinder-volume` has more
  than one host and no coordination backend is enabled (valkey, redis or etcd,
  `roles/cinder/tasks/precheck.yml:60-68`, `group_vars/all.yml:1178`), unless `skip_cinder_backend_check`.
- **`cluster` in `cinder.conf`:** a non-empty `cinder_cluster_name` writes `cluster = <name>`, for `cinder-volume`
  only (`roles/cinder/templates/cinder.conf.j2:23-25`). What Cinder does with the existing volumes and services when
  the cluster is set on a running cloud is service-side: [NOT AVAILABLE], to be confirmed by the community.
- **`cinder.conf` differs per service:** `enabled_backends` and the Ceph backend sections are now written only for
  `cinder-volume` (`roles/cinder/templates/cinder.conf.j2:27-31`, `roles/cinder/templates/cinder.conf.j2:150-170`), so
  the first 2025.1 run changes the `cinder.conf` of `cinder-api`, `cinder-scheduler` and `cinder-backup`.
- **Ceph: user, pool and backend name per entry:** each entry of `cinder_ceph_backends` carries `backend_name`,
  `cluster` (default `ceph_cluster`), `user` and `pool` (`roles/cinder/defaults/main.yml:278-285`); the section writes
  `volume_backend_name`, `rbd_pool`, `rbd_user` and `rbd_keyring_conf` from it
  (`roles/cinder/templates/cinder.conf.j2:155-161`). With the defaults `volume_backend_name` stays `rbd-1`
  (`cinder_backend_ceph_name`, `roles/cinder/defaults/main.yml:266`). `cinder_backup_ceph_backend` adds the backup pool
  and user to the named entry (`roles/cinder/defaults/main.yml:286-287`), and `backup_ceph_user` and `backup_ceph_pool`
  come from it (`roles/cinder/templates/cinder.conf.j2:34-42`). The keyring files are
  `<cluster>.client.<user>.keyring` (`roles/cinder/tasks/external_ceph.yml:39-67`); `ceph_cinder_keyring` and
  `ceph_cinder_backup_keyring` are removed, so an override of them is no longer read.
- **uWSGI for `cinder-api`:** `cinder_wsgi_provider` defaults to `uwsgi` (`roles/cinder/defaults/main.yml:387`); the
  command becomes `uwsgi /etc/cinder/cinder-api-uwsgi.ini` (`roles/cinder/templates/cinder-api.json.j2:3-5`) and the
  Apache virtual host is rendered only with `apache` (`roles/cinder/tasks/config.yml:55-88`). uWSGI logs to
  `/var/log/kolla/cinder/cinder-api-uwsgi.log` (`roles/service-uwsgi-config/defaults/main.yml:4-5`).
- **New `block-storage` service in Keystone:** `cinder_ks_services` registers a `cinder` service of type
  `block-storage` with `/v3` endpoints and keeps `cinderv3` (`volumev3`) as "deprecated"
  (`roles/cinder/defaults/main.yml:346-359`). `upgrade.yml` has no registration step
  (`roles/cinder/tasks/upgrade.yml:1-36`; the 2024.1 user-role registration is removed), so the new service and its
  endpoints appear at the next `deploy` or `reconfigure`, not at `upgrade`.
- **Restarts:** the config tasks notify nothing except the Huawei XML copy (`roles/cinder/tasks/external_huawei.yml:10-11`);
  `check-containers.yml` imports `service-check-containers`, which restarts only the containers whose configuration
  or definition changed ([Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)). The handlers have no
  `kolla_action != "config"` guard any more (`roles/cinder/handlers/main.yml:2-81`). New `check.yml`
  (`roles/cinder/tasks/check.yml:2-4`).
- **First-run recreates:** `cinder_backup` now runs with `ipc_mode: host` like `cinder_volume`
  (`roles/cinder/defaults/main.yml:46`, `roles/cinder/defaults/main.yml:57`), and `cinder_api` and
  `cinder_scheduler` always mount `/dev/shm` (`roles/cinder/defaults/main.yml:173`,
  `roles/cinder/defaults/main.yml:191`). The queue settings are always rendered
  (`roles/cinder/templates/cinder.conf.j2:74,83,88`; [F17](../reference/findings.md#f17)), `www_authenticate_uri` is
  `keystone_public_url` and `memcache_security_strategy` is a variable
  (`roles/cinder/templates/cinder.conf.j2:122,133`). So every cinder container restarts or is recreated on the first
  2025.1 run.
- **Backends:** Hitachi HNAS NFS is removed; Pure NVMe/TCP, Lightbits and Huawei XML files are new
  (`roles/cinder/defaults/main.yml:261-264`, `roles/cinder/tasks/config.yml:12-16`); the Swift backup driver is gone
  with the Swift role; coordination can use valkey (`roles/cinder/templates/cinder.conf.j2:269-273`).
- **No rolling reconfigure or upgrade through the CLI** ([F19](../reference/findings.md#f19)); a batched reconfigure is
  `kolla-ansible deploy -t cinder -e kolla_serial=N`.
- **Still holds from 2024.1:** the per-cluster `ceph/` sub-directories and the copy over `/etc/ceph`
  (`roles/cinder/templates/cinder-volume.json.j2:16-22`, `roles/cinder/templates/cinder-backup.json.j2:15-21`); the
  `hostnqn` file (`roles/cinder/tasks/config.yml:105-114`), which now notifies nothing; the S3 backup driver and its
  precheck; the five handlers in the same order; the HAProxy backends now add `option httpchk`
  (`roles/cinder/defaults/main.yml:20-21`, `roles/cinder/defaults/main.yml:30-31`).

The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the service card follows them.

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
- **Sequence** [CODE]: `reconfigure` imports `deploy.yml` (`roles/cinder/tasks/reconfigure.yml:2`), which runs
  registration, config, check-containers, the clone in dev mode, bootstrap, then a flush of the handlers
  (`roles/cinder/tasks/deploy.yml:1-14`).
- **Risks:** [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet C §3](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#3-cinder)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `cinder-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **Bootstrap one-shots** [CODE]: on deploy and reconfigure, the database and its user are created from the first
  `cinder-api` host, unless `use_preconfigured_databases` (`roles/cinder/tasks/bootstrap.yml:2-36`), then one
  `bootstrap_cinder` container runs, `run_once`, on that host with `KOLLA_BOOTSTRAP`
  (`roles/cinder/tasks/bootstrap_service.yml:2-20`), which runs `cinder-manage db sync` (kolla
  `docker/cinder/cinder-api/extend_start.sh:6-9`). `KOLLA_OSM` (`cinder-manage db online_data_migrations`, kolla
  `docker/cinder/cinder-api/extend_start.sh:11-14`) is set only by `upgrade.yml`
  (`roles/cinder/tasks/upgrade.yml:18-36`).
- **Handlers:** [Tags §5](../risk/tags.md#5-role--handler-map-core-services); changed in 2025.1, a change restarts only
  the container whose files or definition changed ([Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)).
  The Ceph `.conf` task no longer notifies (`roles/cinder/tasks/external_ceph.yml:17-37`), so a change for
  `cinder-volume` no longer restarts `cinder_backup` on a host in both groups [CODE].

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 6 (workload gates): no live migrations,
  resizes, image uploads or volume migrations in flight on the targeted hosts; one of its two checks is
  `openstack volume list --status *ing`.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service: safe on its own "yes, it is the intended unit; it still runs Keystone registration and DB sync"; batch with
  `deploy -e kolla_serial=N` (`reconfigure` forces `kolla_serial=0`, [F19](../reference/findings.md#f19)). Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP. Glance and cinder
  transfers in progress are SIGKILLed after 60 s (`docker_graceful_timeout`, `group_vars/all.yml:148`;
  [R24](../risk/risk-register.md#r24)).
- **Before the upgrade from 2024.1** [CODE]: with more than one `cinder-volume` host, decide on `cinder_cluster_name`
  (or set `cinder_cluster_skip_precheck`), and with Ceph enable a coordination backend, or `kolla-ansible prechecks`
  fails (Changed in 2025.1 above). Setting a cluster name on a running cloud is a Cinder service change whose effect
  is [NOT AVAILABLE]; plan it as its own change, to be confirmed by the community.
- **First run after the upgrade from 2024.1** [CODE]: expect every cinder container to restart or be recreated (queue
  settings, `www_authenticate_uri`, the per-service `cinder.conf`, `/dev/shm` on `cinder_api` and `cinder_scheduler`,
  `ipc_mode: host` on `cinder_backup`, uWSGI on `cinder_api`; [F17](../reference/findings.md#f17)). A container that no
  2025.1 run has recreated or restarted yet is also flagged by the changed systemd unit text
  ([F16](../reference/findings.md#f16)). Run a `deploy` or `reconfigure` after the upgrade to register the
  `block-storage` endpoints.
- [fact sheet C §3.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#38-operational-notes), item 7:
  the cinder role itself does not target computes; enabling `enable_cinder_backend_iscsi`/LVM also flips glance-api to
  privileged with `/dev`, so glance-api is recreated. In 2025.1 `cinder_backend_ceph` (with Cinder enabled) still makes
  glance-api privileged, without `/dev` (`roles/glance/defaults/main.yml:10`,
    `roles/glance/defaults/main.yml:206-207`) [CODE].
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `--skip-tags haproxy` when you don't
  intend to change frontends; a `-t cinder` run renders the frontends without restarting HAProxy
  ([F18](../reference/findings.md#f18)).
- [R24](../risk/risk-register.md#r24), container stop timeout: the stop goes through the container's systemd unit,
  whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:33`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:148`,
  `group_vars/all.yml:160`) ([F3](../reference/findings.md#f3)). Precautions: drain long operations before restarts;
    raise `docker_graceful_timeout` if needed.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible genconfig -t <svc>`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
    after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers; for
  cinder in 2025.1 that is `block-storage` and the deprecated `cinderv3`, each with an `internal` and a `public`
  endpoint (`roles/cinder/defaults/main.yml:346-359`), and the first 2025.1 deploy or reconfigure adds the
  `block-storage` ones. The API answers through the VIP and the container start times show which hosts restarted;
  HAProxy no longer restarts on a service tag ([F18](../reference/findings.md#f18)).

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `cinder`: no
  `host`/`backend_host`/`cluster`; etcd coordination uses only the first etcd host; Ceph backup driver default without a
  Ceph config. Checked against 2025.1 [CODE]: `cinder.conf.j2` still sets no `host` or `backend_host`, but it now sets
  `cluster` for `cinder-volume` when `cinder_cluster_name` is set, and a precheck asks for it with several
  `cinder-volume` hosts (Changed in 2025.1 above); the etcd item
  still does not hold as written: with `cinder_coordination_backend: etcd` (the default only when valkey and Redis are disabled and
  etcd enabled, `group_vars/all.yml:1178`) the `backend_url` is
  `etcd3+<proto>://kolla_internal_fqdn:etcd_client_port?api_version=v3`, i.e. the internal VIP, where the etcd role has
  a HAProxy frontend (`roles/cinder/templates/cinder.conf.j2:269-281`, `roles/etcd/defaults/main.yml:11-17`); the backup
  driver still defaults to `ceph` (`group_vars/all.yml:1181`, `roles/cinder/templates/cinder.conf.j2:33-42`) while the
  Ceph files are written only with `cinder_backend_ceph` (`roles/cinder/tasks/config.yml:18-22`,
  `roles/cinder/templates/cinder-backup.json.j2:15-21`).
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored": an Ussuri
  finding that still does not hold in 2025.1. The role handlers pass `docker_common_options`
  (`roles/cinder/handlers/main.yml:7-9`), which carries `graceful_timeout: "{{ docker_graceful_timeout }}"` (60 s) and
  `client_timeout` (120 s) (`group_vars/all.yml:114`, `group_vars/all.yml:148`, `group_vars/all.yml:151-162`), and the
  container's systemd unit stops it with `<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:33`). On every restart, a service still running 60 s after SIGTERM is killed
  with its in-flight work (heat-engine, cinder copies, glance uploads); the 10 s value is only the fallback when no
  `graceful_timeout` is passed (`library/kolla_container.py:366`, `module_utils/kolla_docker_worker.py:450-454`)
  [CODE] ([R24](../risk/risk-register.md#r24)).
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [fact sheet C §3.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#38-operational-notes),
  "Operational notes", nine items: no `host`/`backend_host`/`cluster` set in cinder.conf; cinder-volume restart impact;
  cinder-backup restart; upgrade restarts every cinder-volume and cinder-backup at once; oddity: backup driver vs. ceph
  files; multipath is never configured; compute-host touchpoints; external Ceph needs cinder-volume and cinder-backup
  hosts in the `storage` group; the sanity check (if enabled) creates a 1 GB volume on every deploy/reconfigure.
    Checked against 2025.1 [CODE]:
  - the upgrade still restarts every cinder container of the play at once (handlers; `upgrade` always runs with
    `kolla_serial=0`, [F19](../reference/findings.md#f19)), and then a second time. `upgrade.yml` renders the config on
    the first `cinder-api` host, runs the `db sync` bootstrap, renders the config everywhere, checks the containers,
    then flushes the handlers (the 2024.1 Keystone user-role step is removed); the flush includes a
    `cinder_rpc_version_startup_delay` pause (30 s) that only runs on `upgrade`; `reload.yml` then restarts every
    enabled cinder container "to remove RPC version pin", and the online data migration runs last
        (`roles/cinder/tasks/upgrade.yml:1-36`, `roles/cinder/handlers/main.yml:71-81`,
    `roles/cinder/tasks/reload.yml:2-10`,
    `roles/cinder/defaults/main.yml:237`);
  - the cinder role still sets no multipath option (no `multipath` under `roles/cinder/`); the separate `multipathd`
    play is still off by default (`site.yml:469-481`, `group_vars/all.yml:927`);
  - `external_ceph.yml` still targets the hosts of each service's own group (`cinder-volume`, `cinder-backup`), with no
    reference to the `storage` group (`roles/cinder/tasks/external_ceph.yml:12`,
    `roles/cinder/tasks/external_ceph.yml:32-34`, `roles/cinder/tasks/external_ceph.yml:49-51`,
    `roles/cinder/tasks/external_ceph.yml:65-67`; the `service_enabled_and_mapped_to_host` filter maps a service by its
    `group`, `kolla_ansible/filters.py:58-82`);
    - the volume sanity check still does not exist: the new `check.yml` only runs the `service-check` role on the
    containers (`roles/cinder/tasks/check.yml:2-4`) and `tasks/deploy.yml` has no check step
    (`roles/cinder/tasks/deploy.yml:1-14`).
- [fact sheet C §8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#8-not-available-list),
  "NOT AVAILABLE list", items 5 to 7: NOT AVAILABLE: whether cinder-backup works with default
  `cinder_backup_driver=ceph` and `cinder_backend_ceph=no`; whether the volumes owned by one of several RBD
  cinder-volume nodes can still be managed while that node is down, and what state an in-flight create-from-image is in
  after a cinder-volume restart; Cinder RPC pinning after `kolla-ansible upgrade`. In 2025.1 the role still restarts all
  cinder services after an upgrade to remove the RPC version pin (`roles/cinder/tasks/reload.yml:2`); whether the pin
  is in fact lifted is service-side behaviour: [NOT AVAILABLE].
- Multi-cluster Ceph: what Cinder does with several RBD backends on different clusters, and whether Nova can attach a
  volume of a cluster other than its own, is service-side behaviour that the role does not establish: [NOT AVAILABLE].
- [fact sheet C §6][sheet-c-6]: a reconfigure with a bumped image tag runs cinder's `db sync` without its online data
  migration step (the bootstrap container sets `KOLLA_BOOTSTRAP`, which runs `cinder-manage db sync`, not `KOLLA_OSM`;
  `KOLLA_OSM` is set only by `upgrade.yml`: `roles/cinder/tasks/bootstrap_service.yml:10-12`, kolla
  `docker/cinder/cinder-api/extend_start.sh:6-14`, `roles/cinder/tasks/upgrade.yml:18-36`); whether this leaves cinder
  in a partially upgraded state is NOT AVAILABLE.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 10: recursive chown on data volumes at every
  start: `kolla_set_configs` makes one `chown` per file of the `cinder` volume, twice for cinder-volume, on every
  `COPY_ALWAYS` start (`roles/cinder/templates/cinder-volume.json.j2:50-54`, kolla
  `docker/cinder/cinder-volume/extend_start.sh:3-5`, `group_vars/all.yml:49`) [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): fact sheet C has its own
  NOT AVAILABLE list, and its §3.8 is among the sections that contain NOT AVAILABLE marks.
- [Open questions](../troubleshooting/open-questions.md) has no entry on Cinder.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py cinder -->

| Item | Value |
|---|---|
| Play | site.yml:574 |
| Tags | cinder |
| Play host patterns | cinder-api, cinder-backup, cinder-scheduler, cinder-volume |
| Node types in play (example inventory) | control, storage |
| Node types running its containers | control, storage |
| Containers | `cinder_api`, `cinder_scheduler`, `cinder_volume`, `cinder_backup` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, external_ceph.yml, external_huawei.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, reload.yml, stop.yml, upgrade.yml |
| Templates | `cinder-api.json.j2`, `cinder-backup.json.j2`, `cinder-scheduler.json.j2`, `cinder-volume.json.j2`, `cinder-wsgi.conf.j2`, `cinder.conf.j2`, `hostnqn.j2` |
| Handlers (definition order) | Restart cinder-api container; Restart cinder-scheduler container; Restart cinder-volume container; Restart cinder-backup container; Wait for cinder services to update service versions |
| Key variables | `enable_cinder`, `enable_cinder_backend_*`, `cinder_backend_ceph`, `cinder_backup_driver`, `cinder_coordination_backend` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — what `-t <svc> reconfigure` runs for an API
  service such as cinder, with the risks and the verification
- [iscsid / tgtd](iscsi.md) — the `iscsi` role, on which cinder-volume (LVM) depends
- [Glance](glance.md) — enabling the cinder iSCSI/LVM or Ceph backend recreates glance-api; Glance has the same
  per-cluster Ceph layout, with the user per backend in 2025.1
- [Nova](nova.md) — Nova needs Cinder for volume-backed boots
- [RabbitMQ](rabbitmq.md) — the queue settings, always on in 2025.1, that change `cinder.conf`
  ([F17](../reference/findings.md#f17))
- [R24](../risk/risk-register.md#r24) — cinder-volume copies are among the in-flight work killed 60 s
  (`docker_graceful_timeout`) after SIGTERM
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the checks before every production run
- [Components](index.md) — the other component pages

[sheet-c-6]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#6-summary-matrix-what-reconfigure-does-per-role
