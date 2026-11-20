---
title: Glance
description: Where the study covers Glance (role glance), from its reconfigure and the file-backend outage risk to the silent backend switch, known bugs and open points.
tags: [glance, reconfigure, one-shot, inventory, risk, dependencies, bugs, unknowns]
---

# Glance

This page is the starting point for Glance, the `glance` role: the containers `glance_api` and `glance_tls_proxy`, on
the control nodes of the example inventory, selected by the tag `glance`. With the file backend on the default named
volume (`glance_file_datadir_volume: "glance"`), only `groups['glance-api'][0]` runs glance (`glance_api_hosts`,
`group_vars/all.yml:906,911,915`; [Component dependencies §3](dependencies.md#3-control-plane-services)), and any
restart is then a full Image API outage ([R20](../risk/risk-register.md#r20)). The lists below say where the study
covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open;
the service card follows them.

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
- **Risks:** [R20](../risk/risk-register.md#r20), [R21](../risk/risk-register.md#r21),
  [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet C §1](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#1-glance)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `glance-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 6 (workload gates): no live migrations,
  resizes, image uploads or volume migrations in flight on the targeted hosts.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service: safe on its own "yes, it is the intended unit; it still runs Keystone registration and DB sync"; batch with
  `ANSIBLE_SERIAL`; the glance file backend has one host ([R20](../risk/risk-register.md#r20)). Prerequisites: MariaDB,
  RabbitMQ, memcached, Keystone (registration), HAProxy VIP. Glance and cinder transfers in progress are SIGKILLed after
  60 s (`docker_graceful_timeout`, `group_vars/all.yml:140,152`; `module_utils/kolla_systemd_worker.py:33`;
  [R24](../risk/risk-register.md#r24)).
- [R20](../risk/risk-register.md#r20), precautions for a Glance reconfigure or deploy: avoid during image-heavy
  operations.
- [R21](../risk/risk-register.md#r21), precautions for enabling Swift (or `glance_backend_ceph`) on a running cloud: set
  `glance_backend_*` explicitly before enabling Swift.
- [R22](../risk/risk-register.md#r22), precautions for an inventory reordering, after which glance moves (file backend):
  treat inventory order as configuration; never reorder casually.
- [fact sheet C §3.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#38-operational-notes), item 7:
  enabling `enable_cinder_backend_iscsi`/LVM also flips glance-api to privileged with `/dev`, so glance-api is
  recreated. In 2023.1 `cinder_backend_ceph` (with Cinder enabled) also makes glance-api privileged, without `/dev`
  (`roles/glance/defaults/main.yml:10,192-193`) [CODE].
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `ANSIBLE_SERIAL=1` for haproxy changes;
  `--skip-tags haproxy` when you don't intend to change frontends.
- [R24](../risk/risk-register.md#r24), precautions for the container stop timeout (60 s in 2023.1: the systemd unit
  stops the container with `docker stop -t <docker_graceful_timeout>`): drain long operations before restarts; raise
  `docker_graceful_timeout` if needed (it reaches the unit on the next restart).
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible -t <svc> genconfig`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, the API
  answers through the VIP, the container start times show which hosts restarted, and `docker ps --filter name=haproxy`
  shows whether HAProxy restarted.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `glance`: global
  `log_bin_trust_function_creators` toggle on every deploy/reconfigure; file backend = single host; backend switches
  silently when Swift/Ceph is enabled. Status: [CODE].
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
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: "Glance adds `db_load_metadefs`";
  [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run), row
  `glance-api`: `glance-manage db_load_metadefs` runs on every deploy/reconfigure (kolla
  `docker/glance/glance-api/extend_start.sh:5-9`; `bootstrap_glance` runs once, on `glance_api_hosts[0]`,
  `roles/glance/tasks/bootstrap_service.yml:20-37`).
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
- [fact sheet C §1.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#18-operational-notes),
  "Operational notes", seven items: backend switch via unrelated flags; inventory order matters; restart impact; rolling
  upgrade; the image cache is never pruned (no task or image of 2023.1 runs a glance cache pruner or cleaner); the
  sanity check (if enabled) creates and deletes an image on every deploy/reconfigure; Glance does not touch compute
  hosts. The sanity check does not exist in 2023.1: the role has no `check.yml` and `tasks/deploy.yml` has no check
  step (service card below), and `kolla_enable_sanity_glance` is not defined in `group_vars/all.yml` [CODE].
- [fact sheet C §8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#8-not-available-list),
  "NOT AVAILABLE list", items 1 to 4: NOT AVAILABLE: whether an existing glance file-store image stays readable after
  `enable_swift: yes` or `glance_backend_ceph: yes` is applied by reconfigure; glance-api start time with a large NFS
  `glance_file_datadir_volume`; whether the glance cinder store works with
  `cinder_catalog_info = volume:cinder:internalURL` and no `[cinder]` store section. Answered from code: Glance rolling
  upgrade with `ANSIBLE_SERIAL=1` runs the contract at the end of batch 1, before later batches are upgraded (the
  contract container is `run_once`, delegated to `glance_api_hosts[0]`, after the flush of handlers,
  `roles/glance/tasks/rolling_upgrade.yml:80-102`).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 10: recursive chown on data volumes at every
  start: `kolla_set_configs` makes one `chown` per file of the glance image store on every `COPY_ALWAYS` start
  (`roles/glance/templates/glance-api.json.j2:54-58`, `group_vars/all.yml:43`) [CODE].

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py glance -->

| Item | Value |
|---|---|
| Play | site.yml:495 |
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
  recreated
- [Nova](nova.md) — Nova needs Glance for image-backed boots
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
