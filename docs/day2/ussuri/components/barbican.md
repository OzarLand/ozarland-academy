---
title: Barbican
description: Where the study covers Barbican (role barbican), which has no operation page of its own, from its fact sheet to the fleet-wide effect of enable_barbican.
tags: [barbican, one-shot, risk, dependencies, unknowns]
---

# Barbican

This page is the starting point for Barbican, the `barbican` role: the containers `barbican_api`,
`barbican_keystone_listener` and `barbican_worker`, on the control nodes of the example inventory, selected by the tag
`barbican`. Its DB sync runs on every deploy and reconfigure, and `barbican_crypto_key` comes from `passwords.yml`
([Component dependencies §3](dependencies.md#3-control-plane-services)). The lists below say where the study covers how
to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open; the
service card follows them.

## Where to look

### Operate

No operation page gives a command line for the `barbican` tag, and the tag has no row of its own in [Tags
§3](../risk/tags.md#3-what-a-tag-really-executes-master-table) or in the [Tag index](../risk/tag-index.md). What the
study says about running it is in fact sheet D: the plays the tag selects
([§1.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#11-plays-in-siteyml)) and the task flow
per action
([§1.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#13-task-flow-per-kolla_action)).

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet D §1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#1-barbican)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `barbican-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 8 (rollback material): previous
  `/etc/kolla/config`, `globals.yml`, `passwords.yml` and inventory under git.
- [fact sheet D
  §1.6](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#16-operationally-notable): the crypto
  KEK lives in `passwords.yml` (`barbican_crypto_key`); this key must be in the `passwords.yml` backup.
- [fact sheet D
  §1.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#13-task-flow-per-kolla_action):
  `reconfigure` = `deploy`, so keystone registration and the DB bootstrap container re-run on every reconfigure.
- [R2](../risk/risk-register.md#r2), precautions for enabling or disabling a service that has a logrotate or fluentd
  input entry (`enable_X` for most OpenStack services, e.g. barbican): treat `enable_*` changes as fleet-wide changes;
  roll out with `--limit` batches.
- [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code), row
  `enable_barbican: yes` (Barbican not even deployed): `nova.conf` is rewritten everywhere (adds `[barbican]`), with
  `td-agent.conf` and `logrotate.conf`; all nova containers restart, libvirt included on every compute, with fluentd,
  cron and kolla_toolbox [CODE].

### Known limits and open points

- [What is not known](../troubleshooting/what-is-not-known.md#storage-and-images): the sources do not establish whether
  a `[barbican]` section rendered before Barbican exists has any effect before encrypted volumes are used.
- [Execution flow §2.2](../concepts/deployment-execution-flow.md#22-openstack-control-plane-deployment-order): Barbican
  comes after Nova, Cinder and Glance in the deployment order; with `enable_barbican`, Nova and Cinder render a
  `[barbican]` section, and on a first deploy they start configured with it before Barbican exists [CODE].
- [fact sheet D
  §1.6](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#16-operationally-notable),
  "Operationally notable", four points: the crypto KEK lives in passwords.yml (NOT AVAILABLE: whether losing or changing
  `barbican_crypto_key` makes stored secrets undecryptable); p11_crypto: the library path is not mounted into the
  containers and no task generates the MKEK or HMAC keys (NOT AVAILABLE: what else an HSM setup needs); running
  `kolla-ansible deploy -t barbican` alone does not run the keystone play, so the `barbican_notifications` topic is not
  enabled in keystone.conf (NOT AVAILABLE: whether barbican-keystone-listener then receives project-deletion events);
  copying the policy file uses `become: true`.
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  15: Barbican and other bootstraps (octavia, manila, ceilometer, masakari, zun, cyborg) re-run their DB sync container
  on every deploy/reconfigure.
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): fact sheet D has its own
  NOT AVAILABLE list, and its §1.6 is among the sections that contain NOT AVAILABLE marks.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), [Open
  questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry on Barbican.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py barbican -->

| Item | Value |
|---|---|
| Play | site.yml:995 |
| Tags | barbican |
| Play host patterns | barbican-api, barbican-keystone-listener, barbican-worker |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `barbican_api`, `barbican_keystone_listener`, `barbican_worker` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `barbican-api.ini.j2`, `barbican-api.json.j2`, `barbican-keystone-listener.json.j2`, `barbican-worker.json.j2`, `barbican.conf.j2` |
| Handlers (definition order) | Restart barbican-api container; Restart barbican-keystone-listener container; Restart barbican-worker container |
| Key variables | `enable_barbican`, `barbican_crypto_key (passwords.yml)` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

## Related

- [fact sheet D §1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#1-barbican) — the per-role
  evidence: plays, services, task flow, config files and dependencies
- [Keystone](keystone.md) — `-t barbican` alone does not run the keystone play, so the `barbican_notifications` topic is
  not enabled in keystone.conf
- [Nova](nova.md) — the compute `nova.conf` changes when barbican is enabled
- [Common: fluentd, cron, kolla_toolbox](common.md) — enabling a service such as barbican changes `td-agent.conf` and/or
  `logrotate.conf` on every host
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) — `enable_<new service>: yes`
  changes fluentd/logrotate on every host and `nova.conf` sections on every compute
- [Components](index.md) — the other component pages
