---
title: Cinder
description: Where the study covers Cinder (role cinder), from the single-service reconfigure and the 10 s stop timeout to dependencies, known bugs and open points.
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
  transfers in progress are SIGKILLed after 10 s ([R24](../risk/risk-register.md#r24)).
- [fact sheet C §3.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#38-operational-notes), item 7:
  the cinder role itself does not target computes; enabling `enable_cinder_backend_iscsi`/LVM also flips glance-api to
  privileged with `/dev`, so glance-api is recreated.
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `ANSIBLE_SERIAL=1` for haproxy changes;
  `--skip-tags haproxy` when you don't intend to change frontends.
- [R24](../risk/risk-register.md#r24), precautions for the effective container stop timeout of 10 s: drain long
  operations before restarts; patch `kolla_docker` or pass `graceful_timeout` if needed.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible -t <svc> genconfig`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, e.g.
  `cinderv2` and `cinderv3` for cinder, the API answers through the VIP, the container start times show which hosts
  restarted, and `docker ps --filter name=haproxy` shows whether HAProxy restarted.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `cinder`: no
  `host`/`backend_host`/`cluster`; etcd coordination uses only the first etcd host; Ceph backup driver default without a
  Ceph config. Status: [CODE].
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored" [CODE]: on
  every restart, a service still running 10 s after SIGTERM is SIGKILLed with its in-flight work (heat-engine, cinder
  copies, glance uploads).
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [fact sheet C §3.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#38-operational-notes),
  "Operational notes", nine items: no `host`/`backend_host`/`cluster` set in cinder.conf; cinder-volume restart impact;
  cinder-backup restart; upgrade restarts every cinder-volume and cinder-backup at once; oddity: backup driver vs. ceph
  files; multipath is never configured; compute-host touchpoints; external Ceph needs cinder-volume and cinder-backup
  hosts in the `storage` group; the sanity check (if enabled) creates a 1 GB volume on every deploy/reconfigure.
- [fact sheet C §8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#8-not-available-list),
  "NOT AVAILABLE list", items 5 to 7: NOT AVAILABLE: whether cinder-backup works with default
  `cinder_backup_driver=ceph` and `cinder_backend_ceph=no`; whether the volumes owned by one of several RBD
  cinder-volume nodes can still be managed while that node is down, and what state an in-flight create-from-image is in
  after a cinder-volume restart; Cinder RPC pinning after `kolla-ansible upgrade`.
- [fact sheet C §6][sheet-c-6]: a reconfigure with a bumped image tag runs cinder's `db sync` without its online data
  migration step; whether this leaves cinder in a partially upgraded state is NOT AVAILABLE.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 10: recursive chown on data volumes at every
  start: `kolla_set_configs` makes one `chown` per file of the `cinder` volume, twice for cinder-volume, on every
  `COPY_ALWAYS` start [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): fact sheet C has its own
  NOT AVAILABLE list, and its §3.8 is among the sections that contain NOT AVAILABLE marks.
- [Open questions](../troubleshooting/open-questions.md) has no entry on Cinder.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py cinder -->

| Item | Value |
|---|---|
| Play | site.yml:683 |
| Tags | cinder |
| Play host patterns | cinder-api, cinder-backup, cinder-scheduler, cinder-volume |
| Node types in play (example inventory) | control, storage |
| Node types running its containers | control, storage |
| Containers | `cinder_api`, `cinder_scheduler`, `cinder_volume`, `cinder_backup` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers → check |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, external_ceph.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `cinder-api.json.j2`, `cinder-backup.json.j2`, `cinder-scheduler.json.j2`, `cinder-volume.json.j2`, `cinder-wsgi.conf.j2`, `cinder.conf.j2` |
| Handlers (definition order) | Restart cinder-api container; Restart cinder-scheduler container; Restart cinder-volume container; Restart cinder-backup container |
| Key variables | `enable_cinder`, `enable_cinder_backend_*`, `cinder_backend_ceph`, `cinder_backup_driver`, `cinder_coordination_backend` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — what `-t <svc> reconfigure` runs for an API
  service such as cinder, with the risks and the verification
- [iscsid / tgtd](iscsi.md) — the `iscsi` role, on which cinder-volume (LVM) depends
- [Glance](glance.md) — enabling the cinder iSCSI/LVM backend recreates glance-api
- [Nova](nova.md) — Nova needs Cinder for volume-backed boots
- [R24](../risk/risk-register.md#r24) — cinder-volume copies are among the in-flight work SIGKILLed 10 s after SIGTERM
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages

[sheet-c-6]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#6-summary-matrix-what-reconfigure-does-per-role
