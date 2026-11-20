---
title: Glance
description: Where the 2024.1 study covers Glance (role glance), from the file-backend outage risk and the per-cluster Ceph layout to the backend switch and open points.
tags: [glance, reconfigure, one-shot, inventory, risk, dependencies, bugs, unknowns]
---

# Glance

This page is the starting point for Glance, the `glance` role: the containers `glance_api` and `glance_tls_proxy`
(`roles/glance/defaults/main.yml:2-13`, `roles/glance/defaults/main.yml:35-44`), on the control nodes of the example
inventory (`inventory/multinode:96-97`, `inventory/multinode:223-224`), selected by the tag `glance`
(`site.yml:544-556`). With the file backend on the default named volume (`glance_file_datadir_volume: "glance"`), only
the first host of `glance-api` runs glance (`glance_api_hosts`, `group_vars/all.yml:1001`, `group_vars/all.yml:1007`,
`group_vars/all.yml:1011`; [Component dependencies §3](dependencies.md#3-control-plane-services)), and any restart is
then a full Image API outage ([R20](../risk/risk-register.md#r20)). The lists below say where the study covers how to
operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open; the service
card follows them.

## What changed in 2024.1

- **External Ceph: one sub-directory and one file per cluster** [CODE]. The `rbd` store is no longer an entry of
  `glance_backends`: it is a list of its own, `glance_ceph_backends`, whose default has one entry, name `rbd`, type
  `rbd`, cluster `ceph`, enabled by `glance_backend_ceph` (`roles/glance/defaults/main.yml:220-244`);
  `glance_store_backends`, which gives `enabled_backends`, adds its enabled entries
  (`roles/glance/defaults/main.yml:246`, `roles/glance/templates/glance-api.conf.j2:17-19`). `external_ceph.yml` now
  creates `<node_config_directory>/glance-api/ceph/`, merges one `<cluster>.conf` per entry into it and copies the
  keyring there as `<cluster>.client.<user>.keyring` (`roles/glance/tasks/external_ceph.yml:2-38`; the keyring
  variable is now `client.<user>.keyring`, `group_vars/all.yml:1184`). 2023.1 wrote `ceph.conf` and
  `ceph.client.glance.keyring` directly in `glance-api/`.
- **What the operator provides keeps its name for the default cluster** [CODE]. The sources are
  `/etc/kolla/config/glance/<cluster>.conf`, then `glance/glance-api/<cluster>.conf`, merged, and the keyring
  `glance/<cluster>.client.glance.keyring` (`roles/glance/tasks/external_ceph.yml:16-38`): with the cluster `ceph`
  these are the 2023.1 names. The `.conf` is now written by `merge_configs`, which skips a source it cannot read
  (`action_plugins/merge_configs.py:149-151`): a missing `glance/ceph.conf` no longer stops the task, as the 2023.1
  `template` copy did, and gives a file without that content. The keyring is still copied with `template`, which needs
  its source.
- **Inside the container, `/etc/ceph` is replaced as a whole** [CODE]. With `glance_backend_ceph`, `glance-api.json.j2`
  copies the directory `ceph` to `/etc/ceph` (`roles/glance/templates/glance-api.json.j2:15-21`); `kolla_set_configs`
  deletes the destination of a source that is not merged before copying the directory content (kolla
  `docker/base/set_configs.py:136-156`, `docker/base/set_configs.py:89-103`).
- **One store section per Ceph entry** [CODE]: `glance-api.conf` writes a `[<name>]` section for every entry of
  `glance_ceph_backends`, now with `rbd_store_ceph_conf = /etc/ceph/<cluster>.conf`; the user (`ceph_glance_user`)
  and the pool (`ceph_glance_pool_name`) are the same for every entry
  (`roles/glance/templates/glance-api.conf.j2:68-75`). The section loop and the two copy loops do not test the entry's
  `enabled` flag (`roles/glance/tasks/external_ceph.yml:25`, `roles/glance/tasks/external_ceph.yml:35`); only
  `glance_store_backends` does.
- **The first 2024.1 run restarts `glance_api` on a Ceph cloud** [CODE]: its `config.json` changes text, and the task
  that writes it notifies the restart handler (`roles/glance/tasks/config.yml:56-67`). The 2023.1 files left in
  `<node_config_directory>/glance-api/` are no longer referenced; no task of the role removes them (no `state: absent`
  under `roles/glance/`).
- **The default store is computed once** [CODE]: `glance_default_backend` is `vmware`, else the first Ceph entry's
  name, else `swift`, else `s3`, else `file` (`roles/glance/defaults/main.yml:247`), and the template writes it in
  double quotes, `default_backend = "<name>"` (`roles/glance/templates/glance-api.conf.j2:60-61`). Whether Glance's
  option parser strips the quotes is service-side: [NOT AVAILABLE].
- **New S3 store** [CODE]: `glance_backend_s3` (default `no`, `group_vars/all.yml:1004`) adds an `s3` store and an
  `[s3]` section from the four `glance_backend_s3_*` values (`roles/glance/defaults/main.yml:220-223`,
  `roles/glance/templates/glance-api.conf.j2:89-95`), which default to `s3_url`, `s3_bucket`, `s3_access_key` and
  `s3_secret_key` (`roles/glance/defaults/main.yml:145-148`). The new precheck asserts only that the four variables are
  defined (`roles/glance/tasks/precheck.yml:28-38`); since the role defaults define them and
  `group_vars/all.yml:1282-1285` declares the `s3_*` variables with no value, the assertion does not detect an empty
  value. Enabling S3 also turns the file store off (`group_vars/all.yml:1001`).
- **Messaging and CORS** [CODE]: with the default quorum queues, `rabbit_quorum_queue = true` is rendered, plus
  `rabbit_stream_fanout` and `rabbit_transient_quorum_queue` when their options are on
  (`roles/glance/templates/glance-api.conf.j2:139-148`, `group_vars/all.yml:268-279`;
  [F17](../reference/findings.md#f17)). With `om_enable_queue_manager` (default `false`, `group_vars/all.yml:269`)
  `use_queue_manager` is set (`roles/glance/templates/glance-api.conf.j2:128-130`) and both containers mount `/dev/shm`
  (`roles/glance/defaults/main.yml:200`, `roles/glance/defaults/main.yml:209`). A new `[cors]` section allows the
  Horizon public endpoint (`roles/glance/templates/glance-api.conf.j2:170-171`, `group_vars/all.yml:1159`).
- **TLS proxy** [CODE]: `glance_tls_proxy_processes` and `glance_tls_proxy_process_cpu_map` are renamed
  `glance_tls_proxy_threads` and `glance_tls_proxy_thread_cpu_map` (`roles/glance/defaults/main.yml:286-287`), and the
  HAProxy `global` section uses `nbthread` and `cpu-map auto:1/all 0-63` instead of `nbproc` and one `cpu-map` per
  process (`roles/glance/templates/glance-tls-proxy.cfg.j2:9-12`). An override still set under the old names is no
  longer read.
- **Endpoints** [CODE]: the endpoints are built with `kolla_url`, the public one on `glance_api_public_port`, which
  follows the single external frontend option (`group_vars/all.yml:391`, `group_vars/all.yml:1015-1016`); the external
  HAProxy entries carry `external_fqdn` (`roles/glance/defaults/main.yml:25-36`).
- **Image side** [CODE]: the glance-api image adds `lsscsi` (kolla `docker/glance/glance-api/Dockerfile.j2:10-23`); the
  start script is unchanged (kolla `docker/glance/glance-api/extend_start.sh:1-27`).
- **Still holds in 2024.1** [CODE]: the two handlers, in the same order, with the module renamed `kolla_container`
  (`roles/glance/handlers/main.yml:2-34`); the upgrade task files differ from 2023.1 only by that rename; the play still
  takes `serial` from `kolla_serial`, default `0` (`site.yml:548`), and now also sets `max_fail_percentage`, default 100
  (`site.yml:549-552`), which never stops the play early ([Controlled batches
  §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)
- **Command:** [Command quick lookup by tag](../operations/command-quick-lookup.md)

### Impact and risk

- **What the tag executes (`glance`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row
  `<svc>`; [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `<svc>` API service
- **Sequence** [CODE]: `reconfigure` imports `deploy.yml` (`roles/glance/tasks/reconfigure.yml:2`), which runs
  registration, config, check-containers, the clone in dev mode, bootstrap, then a flush of the handlers
  (`roles/glance/tasks/deploy.yml:1-15`).
- **Risks:** [R20](../risk/risk-register.md#r20), [R21](../risk/risk-register.md#r21),
  [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet C §1](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#1-glance)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `glance-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **Bootstrap one-shots** [CODE]: on deploy and reconfigure, the database and its user are created from the first
  `glance-api` host unless `use_preconfigured_databases` (`roles/glance/tasks/bootstrap.yml:2-36`); then, on
  `glance_api_hosts[0]`, the MariaDB global variable `log_bin_trust_function_creators` is set to 1, one
  `bootstrap_glance` container runs `run_once` with `KOLLA_BOOTSTRAP`, and the variable is set back to 0
  (`roles/glance/tasks/bootstrap_service.yml:2-54`). The container runs `glance-manage db_sync`, then
  `glance-manage db_load_metadefs` (kolla `docker/glance/glance-api/extend_start.sh:5-9`).
- **Handlers:** [Tags §5](../risk/tags.md#5-role--handler-map-core-services); a change that concerns one container
  restarts both glance containers of that host through loop-notify ([Tags
  §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 6 (workload gates): no live migrations,
  resizes, image uploads or volume migrations in flight on the targeted hosts.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service: safe on its own "yes, it is the intended unit; it still runs Keystone registration and DB sync"; batch with
  `ANSIBLE_SERIAL`; the glance file backend has one host ([R20](../risk/risk-register.md#r20)). Prerequisites: MariaDB,
  RabbitMQ, memcached, Keystone (registration), HAProxy VIP. Glance and cinder transfers in progress are SIGKILLed after
  60 s (`docker_graceful_timeout`, `group_vars/all.yml:139`; [R24](../risk/risk-register.md#r24)).
- **First run after the upgrade from 2023.1** [CODE]: expect `glance_api` to restart for the quorum-queue option and
  the new `[cors]` section of `glance-api.conf`, and on a Ceph cloud for the new `config.json` and `ceph/` files
  ([What changed in 2024.1](#what-changed-in-20241), [F17](../reference/findings.md#f17)). A container that no 2024.1
  run
  has recreated or restarted yet is also flagged by the changed systemd unit text ([F16](../reference/findings.md#f16)).
- [R20](../risk/risk-register.md#r20), precautions for a Glance reconfigure or deploy: avoid during image-heavy
  operations.
- [R21](../risk/risk-register.md#r21), precautions for enabling Swift (or `glance_backend_ceph`, or now
  `glance_backend_s3`) on a running cloud: set `glance_backend_*` explicitly before enabling Swift. Still holds in
  2024.1 [CODE]: `glance_backend_swift` follows `enable_swift`, and `glance_backend_file` is true only when none of
  ceph, s3, swift and vmware is (`group_vars/all.yml:1001`, `group_vars/all.yml:1006`).
- [R22](../risk/risk-register.md#r22), precautions for an inventory reordering, after which glance moves (file backend):
  treat inventory order as configuration; never reorder casually. Still holds: `glance_api_hosts` is then the first
  host of `glance-api` (`group_vars/all.yml:1011`) [CODE].
- [fact sheet C §3.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#38-operational-notes), item 7:
  enabling `enable_cinder_backend_iscsi`/LVM also flips glance-api to privileged with `/dev`, so glance-api is
  recreated. In 2024.1 `cinder_backend_ceph` (with Cinder enabled) still makes glance-api privileged, without `/dev`
  (`roles/glance/defaults/main.yml:10`, `roles/glance/defaults/main.yml:202-203`) [CODE].
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
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers (for
  glance an `internal` and a `public` endpoint, `roles/glance/defaults/main.yml:97-98`), the API answers through the
  VIP, the container start times show which hosts restarted, and the haproxy container's start time shows whether
  HAProxy restarted.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `glance`: global
  `log_bin_trust_function_creators` toggle on every deploy/reconfigure; file backend = single host; backend switches
  silently when Swift/Ceph is enabled. Status: all three still hold in 2024.1 [CODE]
  (`roles/glance/tasks/bootstrap_service.yml:2-17`, `roles/glance/tasks/bootstrap_service.yml:39-54`;
  `group_vars/all.yml:1011`; `group_vars/all.yml:1001`, `roles/glance/defaults/main.yml:247`), and S3 is one more flag
  that turns the file store off.
- [Q12](../troubleshooting/open-questions.md#q12): "Glance backend switch on enabling Swift". Status: [NOT AVAILABLE].
- [What is not known](../troubleshooting/what-is-not-known.md#storage-and-images), row "Glance": the sources do not
  establish whether snapshots in progress fail ([R20](../risk/risk-register.md#r20)); whether existing file-store images
  stay readable, and boots from them still work, after Swift is enabled ([R21](../risk/risk-register.md#r21),
  [Q12](../troubleshooting/open-questions.md#q12)).
- [What is not known](../troubleshooting/what-is-not-known.md#upgrades-and-database-migrations): the sources do not
  establish whether `glance-manage db_load_metadefs`, without `--merge`, only adds namespaces that are not yet in the
  DB.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish the cost of the recursive chown on large trees (the glance store among them).
- Multi-cluster Ceph: what Glance does with several `rbd` stores on different clusters is service-side behaviour that
  the role does not establish: [NOT AVAILABLE].
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: "Glance adds `db_load_metadefs`";
  [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run), row
  `glance-api`: `glance-manage db_load_metadefs` runs on every deploy/reconfigure (kolla
  `docker/glance/glance-api/extend_start.sh:5-9`; `bootstrap_glance` runs once, on `glance_api_hosts[0]`,
  `roles/glance/tasks/bootstrap_service.yml:19-37`).
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored": an Ussuri
  finding that still does not hold in 2024.1. The role handlers pass `docker_common_options`
  (`roles/glance/handlers/main.yml:7-9`), which carries `graceful_timeout: "{{ docker_graceful_timeout }}"` (60 s) and
  `client_timeout` (120 s) (`group_vars/all.yml:105`, `group_vars/all.yml:139`, `group_vars/all.yml:142-153`), and the
  container's systemd unit stops it with `<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:32`). On every restart, a service still running 60 s after SIGTERM is killed
  with its in-flight work (heat-engine, cinder copies, glance uploads); the 10 s value is only the fallback when no
  `graceful_timeout` is passed (`library/kolla_container.py:370`, `module_utils/kolla_docker_worker.py:439-443`)
  [CODE] ([R24](../risk/risk-register.md#r24)).
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [fact sheet C §1.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#18-operational-notes),
  "Operational notes", seven items: backend switch via unrelated flags; inventory order matters; restart impact; rolling
  upgrade; the image cache is never pruned (no task or image of 2024.1 runs a glance cache pruner or cleaner: no match
  under `roles/glance/` or kolla `docker/glance/`); the sanity check (if enabled) creates and deletes an image on every
  deploy/reconfigure; Glance does not touch compute hosts. The sanity check still does not exist in 2024.1: the role has
  no `check.yml`, `tasks/deploy.yml` has no check step (`roles/glance/tasks/deploy.yml:1-15`), and
  `kolla_enable_sanity_glance` is not defined in `group_vars/all.yml` [CODE].
- **Upgrade paths** [CODE]: `upgrade.yml` runs `rolling_upgrade.yml` when `glance_enable_rolling_upgrade` (default
  `no`, `group_vars/all.yml:1008`), else `legacy_upgrade.yml` (`roles/glance/tasks/upgrade.yml:1-6`). The legacy path
  renders the config, checks the containers, runs the `db_sync` bootstrap, then flushes the handlers
  (`roles/glance/tasks/legacy_upgrade.yml:1-9`), so with the default serial 0 every `glance_api` restarts at once. The
  rolling path stops `glance_api` on `glance_api_hosts[0]` after rendering its config, runs the `expand` and `migrate`
  one-shots there (`KOLLA_UPGRADE` with `GLANCE_DB_EXPAND` or `GLANCE_DB_MIGRATE`), renders the config of the other
  hosts, checks the containers and flushes the handlers, then runs `contract`
  (`roles/glance/tasks/rolling_upgrade.yml:6-102`, kolla `docker/glance/glance-api/extend_start.sh:13-27`).
- [fact sheet C §8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#8-not-available-list),
  "NOT AVAILABLE list", items 1 to 4: NOT AVAILABLE: whether an existing glance file-store image stays readable after
  `enable_swift: yes` or `glance_backend_ceph: yes` is applied by reconfigure; glance-api start time with a large NFS
  `glance_file_datadir_volume`; whether the glance cinder store works with
  `cinder_catalog_info = volume:cinder:internalURL` (still set, `roles/glance/templates/glance-api.conf.j2:25`) and no
  `[cinder]` store section. Answered from code: Glance rolling upgrade with `ANSIBLE_SERIAL=1` runs the contract at the
  end of batch 1, before later batches are upgraded (the contract container is `run_once`, delegated to
  `glance_api_hosts[0]`, after the flush of handlers, `roles/glance/tasks/rolling_upgrade.yml:80-81`,
  `roles/glance/tasks/rolling_upgrade.yml:83-102`).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 10: recursive chown on data volumes at every
  start: `kolla_set_configs` makes one `chown` per file of the glance image store on every `COPY_ALWAYS` start
  (`roles/glance/templates/glance-api.json.j2:48-52`, `group_vars/all.yml:43`) [CODE].

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py glance -->

| Item | Value |
|---|---|
| Play | site.yml:544 |
| Tags | glance |
| Play host patterns | glance-api |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `glance_api`, `glance_tls_proxy` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, external_ceph.yml, legacy_upgrade.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, rolling_upgrade.yml, stop.yml, stop_service.yml, upgrade.yml |
| Templates | `glance-api.conf.j2`, `glance-api.json.j2`, `glance-cache.conf.j2`, `glance-swift.conf.j2`, `glance-tls-proxy.cfg.j2`, `glance-tls-proxy.json.j2` |
| Handlers (definition order) | Restart glance-api container; Restart glance-tls-proxy container |
| Key variables | `enable_glance`, `glance_backend_*`, `glance_api_hosts`, `glance_enable_rolling_upgrade` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — what `-t <svc> reconfigure` runs for an API
  service such as glance, with the risks and the verification
- [MariaDB/Galera](mariadb.md) — a Glance deploy or reconfigure toggles the global MariaDB variable
  `log_bin_trust_function_creators`
- [Swift](swift.md) — enabling Swift changes Glance's default backend
- [Cinder](cinder.md) — enabling its iSCSI/LVM or Ceph backend flips glance-api to privileged, so glance-api is
  recreated; Cinder has the same per-cluster Ceph layout in 2024.1
- [Nova](nova.md) — Nova needs Glance for image-backed boots
- [RabbitMQ](rabbitmq.md) — the quorum-queue default that changes `glance-api.conf`
  ([F17](../reference/findings.md#f17))
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the checks before every production run
- [Components](index.md) — the other component pages
