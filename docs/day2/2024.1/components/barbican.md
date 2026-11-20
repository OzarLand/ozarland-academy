---
title: Barbican
description: Where the 2024.1 study covers Barbican (role barbican), which has no operation page of its own, from its fact sheet to the fleet-wide effect of enable_barbican.
tags: [barbican, one-shot, risk, dependencies, unknowns]
---

# Barbican

This page is the starting point for Barbican, the `barbican` role: the containers `barbican_api`,
`barbican_keystone_listener` and `barbican_worker` (`roles/barbican/defaults/main.yml:4`,
`roles/barbican/defaults/main.yml:28`, `roles/barbican/defaults/main.yml:36`), on the control nodes of the example
inventory, selected by the tag `barbican` (`site.yml:853-867`; group `barbican` is a child of `control`,
`inventory/multinode:125-126`). Its DB sync (`bootstrap_barbican`, `run_once`,
`roles/barbican/tasks/bootstrap_service.yml:2-20`) runs on every deploy and reconfigure, and `barbican_crypto_key`
comes from `passwords.yml` (`etc/kolla/passwords.yml:56`, rendered as `kek` in
`roles/barbican/templates/barbican.conf.j2:50` with the default `simple_crypto` plugin, `group_vars/all.yml:1022`)
[CODE] ([Component dependencies §3](dependencies.md#3-control-plane-services)). The lists below say where the study
covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays
open; the service card follows them.

## What changed in 2024.1

- **Database options moved to `[database]`** [CODE]: `barbican.conf` no longer sets `sql_connection` in `[DEFAULT]`;
  it renders `[database] connection`, with `connection_recycle_time`, `max_pool_size` and `max_retries = -1`
  (`roles/barbican/templates/barbican.conf.j2:18-22`). A cloud coming from 2023.1 therefore gets a changed
  `barbican.conf` on each barbican host, and the config task notifies the restart of each barbican container
  (`roles/barbican/tasks/config.yml:111-129`). What Barbican does with the new options at runtime is
  [NOT AVAILABLE].
- **New messaging options** [CODE]: with the default quorum queues (`group_vars/all.yml:268`),
  `rabbit_quorum_queue = true` is rendered (`roles/barbican/templates/barbican.conf.j2:98-107`; see
  [F17](../reference/findings.md#f17)). With `om_enable_queue_manager` (default `false`, `group_vars/all.yml:269`) the
  three containers mount `/dev/shm` (`roles/barbican/defaults/main.yml:138`, `roles/barbican/defaults/main.yml:145`,
  `roles/barbican/defaults/main.yml:152`), and `barbican.conf` gets `use_queue_manager`
  (`roles/barbican/templates/barbican.conf.j2:87-89`) and an `[oslo_concurrency]` lock path
  (`roles/barbican/templates/barbican.conf.j2:117-120`).
- **Public URL and external frontend** [CODE]: the endpoints are built with the `kolla_url` filter, the public one on
  `barbican_api_public_port` (`group_vars/all.yml:1025-1026`), which becomes 443 or 80 with
  `haproxy_single_external_frontend` (default `false`) and otherwise stays 9311 (`group_vars/all.yml:340-341`,
  `group_vars/all.yml:931-932`). The external HAProxy entry now carries `external_fqdn` and the public port
  (`roles/barbican/defaults/main.yml:23-24`). `host_href` in `barbican.conf` is the public endpoint
  (`roles/barbican/templates/barbican.conf.j2:10`), so turning the single external frontend on changes `barbican.conf`
  too.
- **Container module renamed** [CODE]: the handlers, the check of the containers and the bootstrap container use
  `kolla_container` instead of `kolla_docker`, with the same actions (`roles/barbican/handlers/main.yml:2-48`,
  `roles/barbican/tasks/check-containers.yml:2-5`, `roles/barbican/tasks/bootstrap_service.yml:6-7`).
- **The play** [CODE]: it still takes `serial` from `kolla_serial`, default `0` (`site.yml:860`), and now also sets
  `max_fail_percentage`, default 100 (`site.yml:861-864`), which never stops the play early ([Controlled batches
  §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).
- The kolla barbican images are unchanged between the two tags (no difference under kolla `docker/barbican/`).

## Where to look

### Operate

No operation page gives a command line for the `barbican` tag, and the tag has no row of its own in [Tags
§3](../risk/tags.md#3-what-a-tag-really-executes-master-table) or in the [Tag index](../risk/tag-index.md). What the
study says about running it is in fact sheet D: the plays the tag selects
([§1.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#11-plays-in-siteyml)) and the task flow
per action
([§1.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#13-task-flow-per-kolla_action)). In
2024.1 the deploy flow is registration, config, check-containers, clone (dev mode only), bootstrap, then the handlers
(`roles/barbican/tasks/deploy.yml:2-14`); upgrade is config, check-containers, `bootstrap_service.yml`, then the
handlers (`roles/barbican/tasks/upgrade.yml:2-9`) [CODE].

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
  KEK lives in `passwords.yml` (`barbican_crypto_key`, `etc/kolla/passwords.yml:56`); this key must be in the
  `passwords.yml` backup.
- [fact sheet D
  §1.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#13-task-flow-per-kolla_action):
  `reconfigure` = `deploy` (`roles/barbican/tasks/reconfigure.yml:2`), so keystone registration and the DB bootstrap
  container re-run on every reconfigure [CODE].
- [R2](../risk/risk-register.md#r2), precautions for enabling or disabling a service that has a logrotate or fluentd
  input entry (`enable_X` for most OpenStack services, e.g. barbican: `roles/common/defaults/main.yml:157-158` for the
  fluentd input, `roles/common/tasks/config.yml:215` for logrotate): treat `enable_*` changes as fleet-wide changes;
  roll out with `--limit` batches; apply the `common` side deliberately with `-t common`. In 2024.1, as in 2023.1,
  `td-agent.conf` and `logrotate.conf` change only when the `common` play runs (an untagged run or `-t common`,
  `site.yml:88-103`), not under `-t barbican` [CODE].
- [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code), row
  `enable_barbican: yes` (Barbican not even deployed): `nova.conf` is rewritten everywhere (adds `[barbican]`,
  `roles/nova/templates/nova.conf.j2:217-222`, `roles/nova-cell/templates/nova.conf.j2:259-264`); all nova containers
  restart, libvirt included on every compute; `td-agent.conf` and `logrotate.conf` change too, but fluentd, cron and
  kolla_toolbox restart only at the next run of the `common` play, not under `-t nova` [CODE]. Cinder renders the same
  section (`roles/cinder/templates/cinder.conf.j2:264-269`).
- [R24](../risk/risk-register.md#r24), container stop timeout: in 2024.1 the stop goes through the container's systemd
  unit, whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:32`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:139`). The
  first 2024.1 check of a container whose unit 2023.1 wrote reports drift ([F16](../reference/findings.md#f16)).

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
  copying the policy file uses `become: true`. All four still hold in 2024.1 [CODE]: `etc/kolla/passwords.yml:56`;
  `barbican.conf.j2:34-46` sets `library_path`, `mkek_label` and `hmac_label`, while `barbican_library_path`
  (`group_vars/all.yml:1023`) appears nowhere else under `ansible/` (no task, no volume); the topic is enabled from the
  keystone role (`roles/keystone/defaults/main.yml:191-192`); `roles/barbican/tasks/config.yml:131-136` copies the
  policy file with `become: true`.
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  15: Barbican and other bootstraps (octavia, manila, ceilometer, masakari, zun, cyborg) re-run their DB sync container
  on every deploy/reconfigure. For Barbican, still holds in 2024.1: `bootstrap_barbican` has no `kolla_action` guard
  (`roles/barbican/tasks/bootstrap_service.yml:2-20`) [CODE].
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): fact sheet D has its own
  NOT AVAILABLE list, and its §1.6 is among the sections that contain NOT AVAILABLE marks.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), [Open
  questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry specific to
  Barbican.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py barbican -->

| Item | Value |
|---|---|
| Play | site.yml:853 |
| Tags | barbican |
| Play host patterns | barbican-api, barbican-keystone-listener, barbican-worker |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `barbican_api`, `barbican_keystone_listener`, `barbican_worker` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `barbican-api.ini.j2`, `barbican-api.json.j2`, `barbican-keystone-listener.json.j2`, `barbican-worker.json.j2`, `barbican.conf.j2` |
| Handlers (definition order) | Restart barbican-api container; Restart barbican-keystone-listener container; Restart barbican-worker container |
| Key variables | `enable_barbican`, `barbican_crypto_key (passwords.yml)` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [fact sheet D §1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#1-barbican) — the per-role
  evidence: plays, services, task flow, config files and dependencies
- [Keystone](keystone.md) — `-t barbican` alone does not run the keystone play, so the `barbican_notifications` topic is
  not enabled in keystone.conf
- [Nova](nova.md) — the compute `nova.conf` changes when barbican is enabled
- [Common: fluentd, cron, kolla_toolbox](common.md) — enabling a service such as barbican changes `td-agent.conf` and/or
  `logrotate.conf` on every host of the `common` play, when that play runs
- [RabbitMQ](rabbitmq.md) — quorum queues on by default in 2024.1, rendered into `barbican.conf`
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) — `enable_<new service>: yes`
  changes fluentd/logrotate on every host and `nova.conf` sections on every compute
- [Components](index.md) — the other component pages
