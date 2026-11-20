---
title: Cinder
description: Where the 2024.1 study covers Cinder (role cinder), from the multi-cluster Ceph layout and the 60 s stop timeout to the upgrade restarts and open points.
tags: [cinder, reconfigure, one-shot, risk, dependencies, bugs, unknowns]
---

# Cinder

This page is the starting point for Cinder, the `cinder` role: the containers `cinder_api`, `cinder_scheduler`,
`cinder_volume` and `cinder_backup` (`roles/cinder/defaults/main.yml:2-54`), on the control and storage nodes of the
example inventory (`cinder-api` and `cinder-scheduler` on `cinder`, i.e. `control`; `cinder-volume` and
`cinder-backup` on `storage`: `inventory/multinode:110-111`, `inventory/multinode:284-295`), selected by the tag
`cinder` (`site.yml:576-591`). `iscsid` and `tgtd` are in the `iscsi` play, not under `-t cinder` ([Tags
§3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites)). The lists below say
where the study covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and
what stays open; the service card follows them.

## What changed in 2024.1

- **External Ceph: one sub-directory and one file per cluster** [CODE]. The Ceph backend is no longer an entry of
  `cinder_backends`: it is a list of its own, `cinder_ceph_backends`, whose default has one entry, name
  `cinder_backend_ceph_name` (`rbd-1`), cluster `ceph`, enabled by `cinder_backend_ceph`
  (`roles/cinder/defaults/main.yml:239-273`); `enabled_backends` adds its enabled entries
  (`roles/cinder/defaults/main.yml:280`, `roles/cinder/templates/cinder.conf.j2:23-25`). `external_ceph.yml` now
  creates `<node_config_directory>/cinder-volume/ceph/` and `.../cinder-backup/ceph/`, merges one `<cluster>.conf` per
  backend into it, and copies the keyrings there under the name `<cluster>.client.<user>.keyring`
  (`roles/cinder/tasks/external_ceph.yml:2-75`; the keyring variables are now `client.<user>.keyring`,
  `group_vars/all.yml:1182-1183`). 2023.1 wrote `ceph.conf` and `ceph.client.<user>.keyring` directly in the service
  config directory.
- **What the operator provides keeps its name for the default cluster** [CODE]. The sources are
  `/etc/kolla/config/cinder/<cluster>.conf`, then `cinder/<service>/<cluster>.conf`, merged
  (`roles/cinder/tasks/external_ceph.yml:27-31`), and the keyrings `cinder/cinder-volume/<cluster>.<keyring>` and
  `cinder/cinder-backup/<cluster>.<keyring>` (`roles/cinder/tasks/external_ceph.yml:44-69`). With the cluster `ceph`
  these are the 2023.1 names: `ceph.conf` and `ceph.client.cinder.keyring`. A missing `.conf` source is skipped,
  because `merge_configs` only reads sources it can read (`action_plugins/merge_configs.py:149-151`); the keyrings are
  copied with `template`, which needs its source.
- **Inside the container, `/etc/ceph` is replaced as a whole** [CODE]. `cinder-volume.json.j2` and
  `cinder-backup.json.j2` now copy the directory `ceph` to `/etc/ceph`, only when `cinder_backend_ceph` is set
  (`roles/cinder/templates/cinder-volume.json.j2:9-15`, `roles/cinder/templates/cinder-backup.json.j2:15-21`).
  `kolla_set_configs` deletes the destination before it copies a source that is not merged, then copies the directory
  content (kolla `docker/base/set_configs.py:136-156`, `docker/base/set_configs.py:89-103`), so `/etc/ceph` in the
  container holds exactly what the role put in `ceph/`.
- **One `cinder.conf` section per Ceph backend** [CODE]. With `cinder_backend_ceph`, the template writes a section for
  every entry of `cinder_ceph_backends`, with `rbd_ceph_conf = /etc/ceph/<cluster>.conf`, the new `rbd_cluster_name`
  and `rbd_keyring_conf`, and `backend_availability_zone` when the entry defines one
  (`roles/cinder/templates/cinder.conf.j2:161-178`). The pool (`ceph_cinder_pool_name`), the user (`ceph_cinder_user`)
  and `rbd_secret_uuid` are the same for every backend (`roles/cinder/templates/cinder.conf.j2:166-172`). The section
  loop, the `.conf` loop and the keyring loop do not test the entry's `enabled` flag
  (`roles/cinder/templates/cinder.conf.j2:162`, `roles/cinder/tasks/external_ceph.yml:38-40`,
  `roles/cinder/tasks/external_ceph.yml:52`); only `enabled_backends` does.
- **cinder-backup follows one named backend** [CODE]. `cinder_backup_ceph_backend` is the entry of
  `cinder_ceph_backends` whose name is `cinder_backup_backend_ceph_name`, default `rbd-1`
  (`roles/cinder/defaults/main.yml:275-276`); its cluster gives `backup_ceph_conf` and the two backup keyrings
  (`roles/cinder/templates/cinder.conf.j2:28-30`, `roles/cinder/tasks/external_ceph.yml:67-69`). The default only
  matches because `cinder_backend_ceph_name` is also `rbd-1` (`roles/cinder/defaults/main.yml:259`): renaming the Ceph
  backend without setting `cinder_backup_backend_ceph_name` leaves the lookup with no entry.
- **The first 2024.1 run restarts the Ceph services** [CODE]. On a Ceph cloud, the `config.json` of `cinder-volume`
  and `cinder-backup` changes text, and the task that writes it notifies the restart handlers
  (`roles/cinder/tasks/config.yml:44-55`). The 2023.1 files left in `<node_config_directory>/cinder-volume/` and
  `.../cinder-backup/` are no longer referenced; no task of the role removes them (no `state: absent` under
  `roles/cinder/`).
- **New `hostnqn` file for cinder-volume** [CODE]. `config.yml` renders
  `nqn.2014-08.org.nvmexpress:uuid:<uuid of the hostname>` into `<node_config_directory>/cinder-volume/hostnqn` and
  notifies the cinder-volume restart (`roles/cinder/tasks/config.yml:95-108`, `roles/cinder/templates/hostnqn.j2:1`);
  `config.json` copies it, not optional, to `/etc/nvme/hostnqn` (`roles/cinder/templates/cinder-volume.json.j2:23-27`).
  So the first 2024.1 run that renders configs restarts every `cinder_volume`; the value is stable while the hostname
  is. On the image side, `nvme-cli` moved from the cinder-volume image to `cinder-base` (kolla
  `docker/cinder/cinder-base/Dockerfile.j2:15-31`).
- **New S3 backup driver** [CODE]: `cinder_backup_driver: s3` writes `S3BackupDriver` with the four
  `cinder_backup_s3_*` values (`roles/cinder/templates/cinder.conf.j2:51-56`), which default to `s3_url`,
  `s3_bucket`, `s3_access_key` and `s3_secret_key` (`roles/cinder/defaults/main.yml:319-322`). The new precheck asserts
  only that the four variables are defined (`roles/cinder/tasks/precheck.yml:58-68`); since the role defaults define
  them and `group_vars/all.yml:1282-1285` declares the `s3_*` variables with no value, the assertion does not detect an
  empty value.
- **Messaging** [CODE]: with the default quorum queues, `rabbit_quorum_queue = true` is rendered, plus
  `rabbit_stream_fanout` and `rabbit_transient_quorum_queue` when their options are on
  (`roles/cinder/templates/cinder.conf.j2:90-99`, `group_vars/all.yml:268-279`; [F17](../reference/findings.md#f17)).
  With `om_enable_queue_manager` (default `false`, `group_vars/all.yml:269`) `use_queue_manager` is set
  (`roles/cinder/templates/cinder.conf.j2:76-81`) and `cinder_api` and `cinder_scheduler` mount `/dev/shm`
  (`roles/cinder/defaults/main.yml:167`, `roles/cinder/defaults/main.yml:185`). The `vitrage_notifications` topic is
  gone (`roles/cinder/defaults/main.yml:285-287`).
- **Container engine** [CODE]: `cinder_volume` and `cinder_backup` mount `/run` with `:shared` only under Docker and
  add `run_default_volumes_<engine>`, empty for Docker (`roles/cinder/defaults/main.yml:43`,
  `roles/cinder/defaults/main.yml:52`, `roles/cinder/defaults/main.yml:175`, `roles/cinder/defaults/main.yml:193`,
  `group_vars/all.yml:172`).
- **Endpoints and registration** [CODE]: the endpoints are built with `kolla_url`, the public one on
  `cinder_api_public_port`, which follows the single external frontend option
  (`roles/cinder/defaults/main.yml:215-216`, `group_vars/all.yml:358`); the external HAProxy entry carries
  `external_fqdn` (`roles/cinder/defaults/main.yml:19-26`). `cinder_ks_roles` is gone and `register.yml` no longer
  passes extra roles (`roles/cinder/tasks/register.yml:1-8`).
- **etcd coordination URL** [CODE]: `backend_url` now ends in `?api_version=v3`
  (`roles/cinder/templates/cinder.conf.j2:274-280`).
- **Still holds in 2024.1** [CODE]: the five handlers, in the same order, with the module renamed `kolla_container`
  (`roles/cinder/handlers/main.yml:2-88`); the play still takes `serial` from `kolla_serial`, default `0`
  (`site.yml:584`), and now also sets `max_fail_percentage`, default 100 (`site.yml:585-588`), which never stops the
  play early ([Controlled batches
  §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).

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
  (`roles/cinder/tasks/upgrade.yml:25-43`).
- **Handlers:** [Tags §5](../risk/tags.md#5-role--handler-map-core-services); a change that concerns one container
  restarts every cinder container of that host through loop-notify ([Tags
  §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)). The Ceph `.conf`
  task loops over the services and the backends with `notify: "Restart {{ service_name }} container"`
  (`roles/cinder/tasks/external_ceph.yml:19-42`), so on a host in both groups a change for `cinder-volume` also
  restarts `cinder_backup` [CODE].

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 6 (workload gates): no live migrations,
  resizes, image uploads or volume migrations in flight on the targeted hosts; one of its two checks is
  `openstack volume list --status *ing`.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service: safe on its own "yes, it is the intended unit; it still runs Keystone registration and DB sync"; batch with
  `ANSIBLE_SERIAL`. Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP. Glance and cinder
  transfers in progress are SIGKILLed after 60 s (`docker_graceful_timeout`, `group_vars/all.yml:139`;
  [R24](../risk/risk-register.md#r24)).
- **First run after the upgrade from 2023.1** [CODE]: on a Ceph cloud, expect `cinder_volume` and `cinder_backup` to
  restart for the new `config.json` and `ceph/` files, every `cinder_volume` for the new `hostnqn` file, and every
  cinder container for the quorum-queue option of `cinder.conf` unless the cloud already had it
  ([What changed in 2024.1](#what-changed-in-20241), [F17](../reference/findings.md#f17)). A container that no 2024.1
  run
  has recreated or restarted yet is also flagged by the changed systemd unit text ([F16](../reference/findings.md#f16)).
- [fact sheet C §3.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#38-operational-notes), item 7:
  the cinder role itself does not target computes; enabling `enable_cinder_backend_iscsi`/LVM also flips glance-api to
  privileged with `/dev`, so glance-api is recreated. In 2024.1 `cinder_backend_ceph` (with Cinder enabled) still makes
  glance-api privileged, without `/dev` (`roles/glance/defaults/main.yml:10`,
  `roles/glance/defaults/main.yml:202-203`) [CODE].
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `ANSIBLE_SERIAL=1` for haproxy changes;
  `--skip-tags haproxy` when you don't intend to change frontends.
- [R24](../risk/risk-register.md#r24), container stop timeout: in 2024.1 the stop goes through the container's systemd
  unit, whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:32`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:139`,
  `group_vars/all.yml:151`) ([F3](../reference/findings.md#f3)). Precautions: drain long operations before restarts;
  raise `docker_graceful_timeout` if needed (it reaches the unit on the next restart).
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible -t <svc> genconfig`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, e.g.
  `cinderv3` for cinder (still the only service in `cinder_ks_services`, with an `internal` and a `public` endpoint,
  `roles/cinder/defaults/main.yml:335-341`), the API answers through the VIP, the container start times show which
  hosts restarted, and the haproxy container's start time shows whether HAProxy restarted.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `cinder`: no
  `host`/`backend_host`/`cluster`; etcd coordination uses only the first etcd host; Ceph backup driver default without a
  Ceph config. Checked against 2024.1 [CODE]: `cinder.conf.j2` still sets no `host`, `backend_host` or `cluster` (the
  only `cluster` in the template is the new `rbd_cluster_name` and the VMware `vmware_cluster_name`); the etcd item
  still does not hold as written: with `cinder_coordination_backend: etcd` (the default only when Redis is disabled and
  etcd enabled, `group_vars/all.yml:1047`) the `backend_url` is
  `etcd3+<proto>://kolla_internal_fqdn:etcd_client_port?api_version=v3`, i.e. the internal VIP, where the etcd role has
  a HAProxy frontend (`roles/cinder/templates/cinder.conf.j2:271-281`, `roles/etcd/defaults/main.yml:11-17`); the backup
  driver still defaults to `ceph` (`group_vars/all.yml:1050`, `roles/cinder/templates/cinder.conf.j2:27-36`) while the
  Ceph files are written only with `cinder_backend_ceph` (`roles/cinder/tasks/config.yml:15-19`,
  `roles/cinder/templates/cinder-backup.json.j2:15-21`).
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored": an Ussuri
  finding that still does not hold in 2024.1. The role handlers pass `docker_common_options`
  (`roles/cinder/handlers/main.yml:7-9`), which carries `graceful_timeout: "{{ docker_graceful_timeout }}"` (60 s) and
  `client_timeout` (120 s) (`group_vars/all.yml:105`, `group_vars/all.yml:139`, `group_vars/all.yml:142-153`), and the
  container's systemd unit stops it with `<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:32`). On every restart, a service still running 60 s after SIGTERM is killed
  with its in-flight work (heat-engine, cinder copies, glance uploads); the 10 s value is only the fallback when no
  `graceful_timeout` is passed (`library/kolla_container.py:370`, `module_utils/kolla_docker_worker.py:439-443`)
  [CODE] ([R24](../risk/risk-register.md#r24)).
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [fact sheet C §3.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#38-operational-notes),
  "Operational notes", nine items: no `host`/`backend_host`/`cluster` set in cinder.conf; cinder-volume restart impact;
  cinder-backup restart; upgrade restarts every cinder-volume and cinder-backup at once; oddity: backup driver vs. ceph
  files; multipath is never configured; compute-host touchpoints; external Ceph needs cinder-volume and cinder-backup
  hosts in the `storage` group; the sanity check (if enabled) creates a 1 GB volume on every deploy/reconfigure.
  Checked against 2024.1 [CODE]:
  - the upgrade still restarts every cinder container of the play at once (handlers, `kolla_serial` 0 by default,
    `site.yml:584`), and then a second time. `upgrade.yml` renders the config on the first `cinder-api` host, runs the
    `db sync` bootstrap, renders the config everywhere, checks the containers, re-runs the Keystone user-role
    registration (marked for removal in the next cycle), then flushes the handlers; the flush includes a
    `cinder_rpc_version_startup_delay` pause (30 s) that only runs on `upgrade`; `reload.yml` then restarts every
    enabled cinder container "to remove RPC version pin", and the online data migration runs last
    (`roles/cinder/tasks/upgrade.yml:1-43`, `roles/cinder/handlers/main.yml:78-88`,
    `roles/cinder/tasks/reload.yml:2-10`,
    `roles/cinder/defaults/main.yml:232`);
  - the cinder role still sets no multipath option (no `multipath` under `roles/cinder/`); the separate `multipathd`
    play is still off by default (`site.yml:454-466`, `group_vars/all.yml:809`);
  - `external_ceph.yml` still targets the hosts of each service's own group (`cinder-volume`, `cinder-backup`), with no
    reference to the `storage` group (`roles/cinder/tasks/external_ceph.yml:12-14`,
    `roles/cinder/tasks/external_ceph.yml:34-37`, `roles/cinder/tasks/external_ceph.yml:53-56`,
    `roles/cinder/tasks/external_ceph.yml:70-73`);
  - the sanity check still does not exist: the role has no `check.yml` and `tasks/deploy.yml` has no check step
    (`roles/cinder/tasks/deploy.yml:1-14`).
- [fact sheet C §8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#8-not-available-list),
  "NOT AVAILABLE list", items 5 to 7: NOT AVAILABLE: whether cinder-backup works with default
  `cinder_backup_driver=ceph` and `cinder_backend_ceph=no`; whether the volumes owned by one of several RBD
  cinder-volume nodes can still be managed while that node is down, and what state an in-flight create-from-image is in
  after a cinder-volume restart; Cinder RPC pinning after `kolla-ansible upgrade`. In 2024.1 the role still restarts all
  cinder services after an upgrade to remove the RPC version pin (`roles/cinder/tasks/reload.yml:2`); whether the pin
  is in fact lifted is service-side behaviour: [NOT AVAILABLE].
- Multi-cluster Ceph: what Cinder does with several RBD backends on different clusters, and whether Nova can attach a
  volume of a cluster other than its own, is service-side behaviour that the role does not establish: [NOT AVAILABLE].
- [fact sheet C §6][sheet-c-6]: a reconfigure with a bumped image tag runs cinder's `db sync` without its online data
  migration step (the bootstrap container sets `KOLLA_BOOTSTRAP`, which runs `cinder-manage db sync`, not `KOLLA_OSM`;
  `KOLLA_OSM` is set only by `upgrade.yml`: `roles/cinder/tasks/bootstrap_service.yml:10-12`, kolla
  `docker/cinder/cinder-api/extend_start.sh:6-14`, `roles/cinder/tasks/upgrade.yml:25-43`); whether this leaves cinder
  in a partially upgraded state is NOT AVAILABLE.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 10: recursive chown on data volumes at every
  start: `kolla_set_configs` makes one `chown` per file of the `cinder` volume, twice for cinder-volume, on every
  `COPY_ALWAYS` start (`roles/cinder/templates/cinder-volume.json.j2:37-41`, kolla
  `docker/cinder/cinder-volume/extend_start.sh:3-5`, `group_vars/all.yml:43`) [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): fact sheet C has its own
  NOT AVAILABLE list, and its §3.8 is among the sections that contain NOT AVAILABLE marks.
- [Open questions](../troubleshooting/open-questions.md) has no entry on Cinder.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py cinder -->

| Item | Value |
|---|---|
| Play | site.yml:576 |
| Tags | cinder |
| Play host patterns | cinder-api, cinder-backup, cinder-scheduler, cinder-volume |
| Node types in play (example inventory) | control, storage |
| Node types running its containers | control, storage |
| Containers | `cinder_api`, `cinder_scheduler`, `cinder_volume`, `cinder_backup` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, external_ceph.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, reload.yml, stop.yml, upgrade.yml |
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
  per-cluster Ceph layout in 2024.1
- [Nova](nova.md) — Nova needs Cinder for volume-backed boots
- [RabbitMQ](rabbitmq.md) — the quorum-queue default that changes `cinder.conf` ([F17](../reference/findings.md#f17))
- [R24](../risk/risk-register.md#r24) — cinder-volume copies are among the in-flight work killed 60 s
  (`docker_graceful_timeout`) after SIGTERM
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the checks before every production run
- [Components](index.md) — the other component pages

[sheet-c-6]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#6-summary-matrix-what-reconfigure-does-per-role
