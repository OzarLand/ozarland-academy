---
title: Glance
description: Where the 2025.1 study covers Glance (role glance), from the file-backend outage risk and the Swift store removal to per-backend Ceph users and open points.
tags: [glance, reconfigure, one-shot, inventory, risk, dependencies, bugs, unknowns]
---

# Glance

This page is the starting point for Glance, the `glance` role: the containers `glance_api` and `glance_tls_proxy`
(`roles/glance/defaults/main.yml:2-13`, `roles/glance/defaults/main.yml:38-46`), on the control nodes of the example
inventory (`inventory/multinode:96-97`, `inventory/multinode:222-223`), selected by the tag `glance`
(`site.yml:542-554`). With the file backend on the default named volume (`glance_file_datadir_volume: "glance"`), only
the first host of `glance-api` runs glance (`glance_api_hosts`, `group_vars/all.yml:1137`, `group_vars/all.yml:1142`,
`group_vars/all.yml:1146`; the role's `host_in_groups` still takes precedence over `group`,
`roles/glance/defaults/main.yml:6`, `kolla_ansible/filters.py:58-82`; [Component dependencies
§3](dependencies.md#3-control-plane-services)), and any restart is then a full Image API outage
([R20](../risk/risk-register.md#r20)).

**Changed in 2025.1** [CODE]:
- **The Swift store is gone, with no check:** `glance_backend_swift` and the `swift` entry of `glance_backends` are
  removed (`roles/glance/defaults/main.yml:224-239`), with the `[swift]` section, `glance-swift.conf` and its
  `config.json` entry. `glance_backend_file` is now true unless Ceph, S3 or VMware is on (`group_vars/all.yml:1137`) and
  `glance_default_backend` is `vmware`, else the first Ceph entry, else `s3`, else `file`
  (`roles/glance/defaults/main.yml:250`). No precheck looks at `enable_swift` or at a 2024.1 `glance_backend_swift`
  (no match for `swift` under `roles/glance/`, `roles/prechecks/` or `group_vars/all.yml`). A cloud whose images were
  in Swift therefore gets, on its first 2025.1 run, a Glance whose default store is `file`, on the first `glance-api`
  host only, and with no `swift` store configured ([Swift](swift.md)). What then happens to the images whose
  locations are in Swift is service-side: [NOT AVAILABLE], to be confirmed by the community.
- **Ceph: user and pool per backend:** each entry of `glance_ceph_backends` now carries `cluster` (default
  `ceph_cluster`, `"ceph"`), `pool` and `user` (`roles/glance/defaults/main.yml:241-247`, `group_vars/all.yml:1290`,
  `group_vars/all.yml:1295`, `group_vars/all.yml:1301`); the store section writes `rbd_store_user` and
  `rbd_store_pool` from the entry (`roles/glance/templates/glance-api.conf.j2:66-73`), and the keyring is
  `<cluster>.client.<user>.keyring`, built in the task (`roles/glance/tasks/external_ceph.yml:25-34`). The variable
  `ceph_glance_keyring` is removed: with the defaults the file name is still `ceph.client.glance.keyring`, but an
  override of `ceph_glance_keyring` is no longer read. The Ceph tasks notify nothing any more
  (`roles/glance/tasks/external_ceph.yml:14-34`); a changed `ceph.conf` or keyring restarts `glance_api` through the
  container check (below).
- **`cinder_catalog_info` is gone** from `glance-api.conf` (the `[DEFAULT]` section,
  `roles/glance/templates/glance-api.conf.j2:1-31`).
- **Restarts:** the config tasks notify nothing; `check-containers.yml` imports `service-check-containers`, which
  notifies `Restart <service> container` only for the container whose configuration or definition changed, so a change
  of `glance-api.conf` no longer restarts `glance_tls_proxy` ([Tags
  §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)). The handlers have no `kolla_action != "config"` guard
  any more (`roles/glance/handlers/main.yml:2-30`). New `check.yml` for `kolla-ansible check`
  (`roles/glance/tasks/check.yml:2-4`).
- **No rolling reconfigure or upgrade through the CLI:** `reconfigure` and `upgrade` force `kolla_serial=0`
  ([F19](../reference/findings.md#f19)); a batched reconfigure is `kolla-ansible deploy -t glance -e kolla_serial=N`.
- **First-run changes:** both containers always mount `/dev/shm` (`roles/glance/defaults/main.yml:204`,
  `roles/glance/defaults/main.yml:213`), so both are recreated; `use_queue_manager`, `rabbit_quorum_queue` and
  `rabbit_transient_quorum_queue` are always rendered (`roles/glance/templates/glance-api.conf.j2:114,120,125`;
  [F17](../reference/findings.md#f17)); `www_authenticate_uri` is `keystone_public_url` and
  `memcache_security_strategy` is a variable (`roles/glance/templates/glance-api.conf.j2:40,51`). The four HAProxy
  backends add `option httpchk` (`roles/glance/defaults/main.yml:24,36,57,70`), which a `-t glance` run renders but no
  longer applies by restarting HAProxy ([F18](../reference/findings.md#f18)).
- **Other:** `glance_copy_certs` drives the CA copy into the containers (`roles/glance/defaults/main.yml:308`); image
  names take `docker_image_name_prefix` (`roles/glance/defaults/main.yml:160,164`); the glance-api image adds
  `systemd-udev` (kolla `docker/glance/glance-api/Dockerfile.j2:10-16`).
- **Still holds from 2024.1:** the per-cluster layout under `glance-api/ceph/` and the copy of that directory over
  `/etc/ceph` (`roles/glance/templates/glance-api.json.j2:15-21`); the `merge_configs` copy of `<cluster>.conf`, which
  skips a missing source (`roles/glance/tasks/external_ceph.yml:14-23`); the quoted `default_backend`
  (`roles/glance/templates/glance-api.conf.j2:59`), whose parsing is [NOT AVAILABLE]; the S3 store and its precheck;
  the TLS proxy thread settings (`roles/glance/defaults/main.yml:289-290`); the `[cors]` section
  (`roles/glance/templates/glance-api.conf.j2:147-148`); the upgrade task files.

The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the service card follows them.

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
- **Handlers:** [Tags §5](../risk/tags.md#5-role--handler-map-core-services); changed in 2025.1, a change that concerns
  one container restarts only that container ([Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)).

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 6 (workload gates): no live migrations,
  resizes, image uploads or volume migrations in flight on the targeted hosts.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service: safe on its own "yes, it is the intended unit; it still runs Keystone registration and DB sync"; batch with
  `deploy -e kolla_serial=N` (`reconfigure` forces `kolla_serial=0`, [F19](../reference/findings.md#f19)); the glance file
  backend has one host ([R20](../risk/risk-register.md#r20)). Prerequisites: MariaDB,
  RabbitMQ, memcached, Keystone (registration), HAProxy VIP. Glance and cinder transfers in progress are SIGKILLed after
  60 s (`docker_graceful_timeout`, `group_vars/all.yml:148`; [R24](../risk/risk-register.md#r24)).
- **First run after the upgrade from 2024.1** [CODE]: expect `glance_api` (and `glance_tls_proxy` when enabled) to be
  recreated for the `/dev/shm` mount, and `glance-api.conf` to change for the queue settings, the public
  `www_authenticate_uri` and the removed `cinder_catalog_info` (Changed in 2025.1 above,
  [F17](../reference/findings.md#f17)). A container that no 2025.1 run has recreated or restarted yet is also flagged
  by the changed systemd unit text ([F16](../reference/findings.md#f16)). On a cloud that used the Swift store, stop
  before the run: Glance falls back to `file` (above).
- [R20](../risk/risk-register.md#r20), precautions for a Glance reconfigure or deploy: avoid during image-heavy
  operations.
- [R21](../risk/risk-register.md#r21), precautions for enabling `glance_backend_ceph`, `glance_backend_s3` or
  `glance_backend_vmware` on a running cloud: set `glance_backend_*` explicitly. Changed in 2025.1 [CODE]: Swift is no
  longer one of the flags, and `glance_backend_file` is true only when none of ceph, s3 and vmware is
  (`group_vars/all.yml:1137`); removing the Swift store is itself a backend switch (above).
- [R22](../risk/risk-register.md#r22), precautions for an inventory reordering, after which glance moves (file backend):
  treat inventory order as configuration; never reorder casually. Still holds: `glance_api_hosts` is then the first
  host of `glance-api` (`group_vars/all.yml:1146`) [CODE].
- [fact sheet C §3.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#38-operational-notes), item 7:
  enabling `enable_cinder_backend_iscsi`/LVM also flips glance-api to privileged with `/dev`, so glance-api is
  recreated. In 2025.1 `cinder_backend_ceph` (with Cinder enabled) still makes glance-api privileged, without `/dev`
  (`roles/glance/defaults/main.yml:10`, `roles/glance/defaults/main.yml:206-207`) [CODE].
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `--skip-tags haproxy` when you don't
  intend to change frontends; a `-t glance` run renders the frontends without restarting HAProxy
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
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers (for
  glance an `internal` and a `public` endpoint, `roles/glance/defaults/main.yml:101-102`), the API answers through the
    VIP and the container start times show which hosts restarted; HAProxy no longer restarts on a service tag
  ([F18](../reference/findings.md#f18)).

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `glance`: global
  `log_bin_trust_function_creators` toggle on every deploy/reconfigure; file backend = single host; backend switches
  silently when another store is enabled. Status: all three still hold in 2025.1 [CODE]
  (`roles/glance/tasks/bootstrap_service.yml:2-17`, `roles/glance/tasks/bootstrap_service.yml:39-54`;
  `group_vars/all.yml:1146`; `group_vars/all.yml:1137`, `roles/glance/defaults/main.yml:250`), with Ceph, S3 and VMware as the
  flags that turn the file store off; the Swift removal adds a silent switch to `file` for clouds that used Swift.
- [Q12](../troubleshooting/open-questions.md#q12): "Glance backend switch on enabling Swift". Status in 2025.1: no
  longer applies as asked (Kolla Ansible no longer deploys Swift); the reverse question, what Glance does with images
  stored in Swift once its `swift` store is gone, is [NOT AVAILABLE], to be confirmed by the community.
- [What is not known](../troubleshooting/what-is-not-known.md#storage-and-images), row "Glance": the sources do not
  establish whether snapshots in progress fail ([R20](../risk/risk-register.md#r20)); whether existing file-store images
  stay readable, and boots from them still work, after another store is enabled ([R21](../risk/risk-register.md#r21),
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
  finding that still does not hold in 2025.1. The role handlers pass `docker_common_options`
  (`roles/glance/handlers/main.yml:7-9`), which carries `graceful_timeout: "{{ docker_graceful_timeout }}"` (60 s) and
  `client_timeout` (120 s) (`group_vars/all.yml:114`, `group_vars/all.yml:148`, `group_vars/all.yml:151-162`), and the
  container's systemd unit stops it with `<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:33`). On every restart, a service still running 60 s after SIGTERM is killed
  with its in-flight work (heat-engine, cinder copies, glance uploads); the 10 s value is only the fallback when no
  `graceful_timeout` is passed (`library/kolla_container.py:366`, `module_utils/kolla_docker_worker.py:450-454`)
  [CODE] ([R24](../risk/risk-register.md#r24)).
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [fact sheet C §1.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#18-operational-notes),
  "Operational notes", seven items: backend switch via unrelated flags; inventory order matters; restart impact; rolling
  upgrade; the image cache is never pruned (no task or image of 2025.1 runs a glance cache pruner or cleaner: no match
  under `roles/glance/` or kolla `docker/glance/`); the sanity check (if enabled) creates and deletes an image on every
  deploy/reconfigure; Glance does not touch compute hosts. The image sanity check still does not exist in 2025.1: the new
  `check.yml` only runs the `service-check` role, which looks at the containers (`roles/glance/tasks/check.yml:2-4`),
  `tasks/deploy.yml` has no check step (`roles/glance/tasks/deploy.yml:1-15`), and `kolla_enable_sanity_glance` is not
  defined in `group_vars/all.yml` [CODE].
- **Upgrade paths** [CODE]: `upgrade.yml` runs `rolling_upgrade.yml` when `glance_enable_rolling_upgrade` (default
  `no`, `group_vars/all.yml:1143`), else `legacy_upgrade.yml` (`roles/glance/tasks/upgrade.yml:1-6`). The legacy path
  renders the config, checks the containers, runs the `db_sync` bootstrap, then flushes the handlers
  (`roles/glance/tasks/legacy_upgrade.yml:1-9`), so every `glance_api` restarts at once; in 2025.1 `upgrade` always
  runs with `kolla_serial=0` ([F19](../reference/findings.md#f19)). The
  rolling path stops `glance_api` on `glance_api_hosts[0]` after rendering its config, runs the `expand` and `migrate`
  one-shots there (`KOLLA_UPGRADE` with `GLANCE_DB_EXPAND` or `GLANCE_DB_MIGRATE`), renders the config of the other
  hosts, checks the containers and flushes the handlers, then runs `contract`
  (`roles/glance/tasks/rolling_upgrade.yml:6-102`, kolla `docker/glance/glance-api/extend_start.sh:13-27`).
- [fact sheet C §8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#8-not-available-list),
  "NOT AVAILABLE list", items 1 to 4: NOT AVAILABLE: whether an existing glance file-store image stays readable after
  `glance_backend_ceph: yes` is applied by reconfigure (and, new in 2025.1, what happens to Swift-stored images once the
  store is gone); glance-api start time with a large NFS `glance_file_datadir_volume`; whether the glance cinder store
  works with no `[cinder]` store section (in 2025.1 `cinder_catalog_info` is no longer set either). Changed in 2025.1
  [CODE]: the 2024.1 answer "a rolling upgrade with `ANSIBLE_SERIAL=1` runs the contract at the end of batch 1" no
  longer applies through the CLI, since `upgrade` runs every host at once ([F19](../reference/findings.md#f19)); the
  contract container is still `run_once`, delegated to `glance_api_hosts[0]`, after the flush of handlers
  (`roles/glance/tasks/rolling_upgrade.yml:80-81`, `roles/glance/tasks/rolling_upgrade.yml:83-102`).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 10: recursive chown on data volumes at every
  start: `kolla_set_configs` makes one `chown` per file of the glance image store on every `COPY_ALWAYS` start
  (`roles/glance/templates/glance-api.json.j2:48-52`, `group_vars/all.yml:49`) [CODE].

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py glance -->

| Item | Value |
|---|---|
| Play | site.yml:542 |
| Tags | glance |
| Play host patterns | glance-api |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `glance_api`, `glance_tls_proxy` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, external_ceph.yml, legacy_upgrade.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, rolling_upgrade.yml, stop.yml, stop_service.yml, upgrade.yml |
| Templates | `glance-api.conf.j2`, `glance-api.json.j2`, `glance-cache.conf.j2`, `glance-tls-proxy.cfg.j2`, `glance-tls-proxy.json.j2` |
| Handlers (definition order) | Restart glance-api container; Restart glance-tls-proxy container |
| Key variables | `enable_glance`, `glance_backend_*`, `glance_api_hosts`, `glance_enable_rolling_upgrade` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — what `-t <svc> reconfigure` runs for an API
  service such as glance, with the risks and the verification
- [MariaDB/Galera](mariadb.md) — a Glance deploy or reconfigure toggles the global MariaDB variable
  `log_bin_trust_function_creators`
- [Swift](swift.md) — removed in 2025.1; a cloud that used the Swift store falls back to `file`
- [Cinder](cinder.md) — enabling its iSCSI/LVM or Ceph backend flips glance-api to privileged, so glance-api is
  recreated; Cinder has the same per-cluster Ceph layout, with the user per backend in 2025.1
- [Nova](nova.md) — Nova needs Glance for image-backed boots
- [RabbitMQ](rabbitmq.md) — the queue settings, always on in 2025.1, that change `glance-api.conf`
  ([F17](../reference/findings.md#f17))
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the checks before every production run
- [Components](index.md) — the other component pages
