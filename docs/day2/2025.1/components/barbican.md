---
title: Barbican
description: Where the 2025.1 study covers Barbican (role barbican), which has no operation page of its own, from its fact sheet to the fleet-wide effect of enable_barbican.
tags: [barbican, one-shot, risk, dependencies, unknowns]
---

# Barbican

This page is the starting point for Barbican, the `barbican` role: the containers `barbican_api`,
`barbican_keystone_listener` and `barbican_worker` (`roles/barbican/defaults/main.yml:4`,
`roles/barbican/defaults/main.yml:32`, `roles/barbican/defaults/main.yml:40`), on the control nodes of the example
inventory, selected by the tag `barbican` (`site.yml:851-865`; group `barbican` is a child of `control`,
`inventory/multinode:122-123`). Its DB sync (`bootstrap_barbican`, `run_once`,
`roles/barbican/tasks/bootstrap_service.yml:2-20`) runs on every deploy and reconfigure, and `barbican_crypto_key`
comes from `passwords.yml` (`etc/kolla/passwords.yml:56`, rendered as `kek` in
`roles/barbican/templates/barbican.conf.j2:50` with the default `simple_crypto` plugin, `group_vars/all.yml:1154`)
[CODE] ([Component dependencies §3](dependencies.md#3-control-plane-services)).

**Changed in 2025.1** [CODE]:
- **Restarts:** the config tasks notify nothing; `check-containers.yml` imports `service-check-containers`
  (`roles/barbican/tasks/check-containers.yml:2-3`), which restarts only the containers whose configuration or
  definition changed ([Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)). The handlers have no
  `kolla_action != "config"` guard any more (`roles/barbican/handlers/main.yml:2-42`). New `check.yml`
  (`roles/barbican/tasks/check.yml:2-4`) for `kolla-ansible check`.
- **No rolling reconfigure or upgrade through the CLI** ([F19](../reference/findings.md#f19)); a batched reconfigure
  is `kolla-ansible deploy -t barbican -e kolla_serial=N`.
- **First-run changes:** the three containers always mount `/dev/shm` (`roles/barbican/defaults/main.yml:142`,
  `roles/barbican/defaults/main.yml:149`, `roles/barbican/defaults/main.yml:156`) and are recreated;
  `use_queue_manager` and the quorum settings are always rendered (`roles/barbican/templates/barbican.conf.j2:87-98`;
  [F17](../reference/findings.md#f17)); `www_authenticate_uri` is `keystone_public_url` and
  `memcache_security_strategy` a variable (`roles/barbican/templates/barbican.conf.j2:62,73`).
- **Other:** both HAProxy backends add `option httpchk` (`roles/barbican/defaults/main.yml:20,30`), rendered by
  `-t barbican` without restarting HAProxy ([F18](../reference/findings.md#f18)); `barbican_copy_certs`
  (`roles/barbican/defaults/main.yml:224`); the image names take `docker_image_name_prefix`. On the image side, the
  `barbican` user joins the `hsmusers` group too, and uWSGI is no longer installed by `barbican-base` but by
  `openstack-base` (kolla `docker/barbican/barbican-base/Dockerfile.j2:10`, kolla
  `docker/openstack-base/Dockerfile.j2:189`); `barbican_api` still runs `uwsgi --emperor`
  (`roles/barbican/templates/barbican-api.json.j2:2`).
- **Still holds from 2024.1:** the `[database]` section (`roles/barbican/templates/barbican.conf.j2:18`); `host_href`
  from the public endpoint (`roles/barbican/templates/barbican.conf.j2:10`), so turning the single external frontend on
  changes `barbican.conf`; the deploy and upgrade flows.

The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the service card follows them.

## Where to look

### Operate

No operation page gives a command line for the `barbican` tag, and the tag has no row of its own in [Tags
§3](../risk/tags.md#3-what-a-tag-really-executes-master-table) or in the [Tag index](../risk/tag-index.md). What the
study says about running it is in fact sheet D: the plays the tag selects
([§1.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#11-plays-in-siteyml)) and the task flow
per action
([§1.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#13-task-flow-per-kolla_action)). In
2025.1 the deploy flow is registration, config, check-containers, clone (dev mode only), bootstrap, then the handlers
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
  input entry (`enable_X` for most OpenStack services, e.g. barbican: `roles/common/defaults/main.yml:149-150` for the
  fluentd input, `roles/common/tasks/config.yml:181` for logrotate): treat `enable_*` changes as fleet-wide changes;
  roll out with `--limit` batches; apply the `common` side deliberately with `-t common`. In 2025.1, as in 2024.1,
  `td-agent.conf` and `logrotate.conf` change only when the `common` play runs (an untagged run or `-t common`,
  `site.yml:88-103`), not under `-t barbican` [CODE].
- [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code), row
  `enable_barbican: yes` (Barbican not even deployed): `nova.conf` is rewritten everywhere (adds `[barbican]`,
  `roles/nova/templates/nova.conf.j2:205-210`, `roles/nova-cell/templates/nova.conf.j2:249-254`); all nova containers
  restart, libvirt included on every compute; `td-agent.conf` and `logrotate.conf` change too, but fluentd, cron and
  kolla_toolbox restart only at the next run of the `common` play, not under `-t nova` [CODE]. Cinder renders the same
  section (`roles/cinder/templates/cinder.conf.j2:262-267`).
- [R24](../risk/risk-register.md#r24), container stop timeout: the stop goes through the container's systemd unit,
  whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:33`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:148`). The
  first 2025.1 check of a container whose unit 2024.1 wrote reports drift ([F16](../reference/findings.md#f16)).

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
  copying the policy file uses `become: true`. All four still hold in 2025.1 [CODE]: `etc/kolla/passwords.yml:56`;
  `roles/barbican/templates/barbican.conf.j2:34-46` sets `library_path`, `mkek_label` and `hmac_label`, while `barbican_library_path`
  (`group_vars/all.yml:1155`) appears nowhere else under `ansible/` (no task, no volume); the topic is enabled from the
  keystone role (`roles/keystone/defaults/main.yml:193-194`); `roles/barbican/tasks/config.yml:107-112` copies the
  policy file with `become: true`.
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  15: Barbican and other bootstraps (octavia, manila, ceilometer, masakari, zun, cyborg) re-run their DB sync container
  on every deploy/reconfigure. For Barbican, still holds in 2025.1: `bootstrap_barbican` has no `kolla_action` guard
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
| Play | site.yml:851 |
| Tags | barbican |
| Play host patterns | barbican-api, barbican-keystone-listener, barbican-worker |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `barbican_api`, `barbican_keystone_listener`, `barbican_worker` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
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
- [RabbitMQ](rabbitmq.md) — the queue settings, always rendered into `barbican.conf` in 2025.1
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) — `enable_<new service>: yes`
  changes fluentd/logrotate on every host and `nova.conf` sections on every compute
- [Components](index.md) — the other component pages
