---
title: Swift
description: Where the 2024.1 study covers Swift (role swift), an old-style role with its own reconfigure logic, from its fact sheet to known bugs and open points.
tags: [swift, reconfigure, upgrade, kolla-set-configs, dependencies, bugs, unknowns]
---

# Swift

This page is the starting point for Swift, the `swift` role: `swift_proxy_server`, `swift_rsyncd` and the account,
container and object containers (18 in all; the three `*_replication_server` containers start only when
`swift_replication_interface` differs from `swift_storage_interface`, which it does not by default, so 15 by default:
`roles/swift/tasks/start.yml:97,176,256`, `roles/swift/defaults/main.yml:66`, `group_vars/all.yml:288-289`), on the
control nodes (proxy, `inventory/multinode:122-123`, `inventory/multinode:327-328`) and storage nodes (account,
container and object servers, `inventory/multinode:330-337`) of the example inventory, selected by the tag `swift`
(`site.yml:511-526`). The rings are operator-built
([Component dependencies §3](dependencies.md#3-control-plane-services)),
and `deploy` does not apply swift config or ring changes to running containers: no task of the role notifies a handler,
and its only handler, `Restart swift-proxy-server container`, is a `debug` no-op (`roles/swift/handlers/main.yml:2-4`)
([fact sheet D §3.4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#34-task-flow)). Still
holds in 2024.1 [CODE]. The lists below say where the study covers how to operate it, its impact, its dependencies and
the evidence, what to check around a run and what stays open; the service card follows them.

## What changed in 2024.1

- **The reconfigure and upgrade tasks now pass `docker_common_options`** [CODE]. In 2023.1, the swift tasks that read
  the container state and environment, remove and restart containers (reconfigure), and stop containers (rolling and
  legacy upgrade) passed no `common_options`. In 2024.1 they pass them (`roles/swift/tasks/reconfigure.yml:35`,
  `roles/swift/tasks/reconfigure.yml:62`, `roles/swift/tasks/reconfigure.yml:73`,
  `roles/swift/tasks/reconfigure.yml:94`, `roles/swift/tasks/rolling_upgrade.yml:34`,
  `roles/swift/tasks/rolling_upgrade.yml:52`, `roles/swift/tasks/legacy_upgrade.yml:10`). What this changes in the
  2024.1 code:
  - the container engine is `kolla_container_engine` (`group_vars/all.yml:153`), not the module fallback `docker`
    (`library/kolla_container.py:372`);
  - the restart of the reconfigure goes through the container's systemd unit, which it rewrites when its text differs
    (`module_utils/kolla_docker_worker.py:439-459`, `module_utils/kolla_systemd_worker.py:172-183`). The unit is now
    built from `docker_common_options`: `-t <docker_graceful_timeout>` (60 s) and `Restart=always` from the default
    `unless-stopped` policy (`group_vars/all.yml:117`, `group_vars/all.yml:139`,
    `module_utils/kolla_systemd_worker.py:56-58`, `module_utils/kolla_systemd_worker.py:69-79`). Without
    `common_options`, the module falls back to a 10 s graceful timeout (`library/kolla_container.py:370`) and passes no
    restart policy, which the unit writes as `Restart=no` (`module_utils/kolla_systemd_worker.py:56`). The same
    fallbacks
    existed in the 2023.1 module (2023.1 tree: `library/kolla_docker.py`, lines 357 and 360;
    `module_utils/kolla_systemd_worker.py`, line 51), so a swift container restarted by the 2023.1 reconfigure may carry
    such a unit; what a
    given host holds is [NOT AVAILABLE].
- **External frontend** [CODE]: the external HAProxy entry now carries `external_fqdn`
  (`roles/swift/defaults/main.yml:16`),
  used by the single external frontend map (`roles/haproxy-config/tasks/main.yml:25-53`). Unlike most services, Swift
  has no public port variable: the public endpoint keeps `swift_proxy_server_port`, 8080
  (`group_vars/all.yml:623`, `group_vars/all.yml:1315`).
- **The play** [CODE]: it still takes `serial` from `kolla_serial`, default `0` (`site.yml:519`), and now also sets
  `max_fail_percentage`, default 100 (`site.yml:520-523`), which never stops the play early ([Controlled batches
  §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).
- **Not affected by [F16](../reference/findings.md#f16)** [CODE]: the swift role has no `check-containers.yml` and never
  calls `compare_container` (grep of `roles/swift/`). `deploy` runs `start_container`
  (`roles/swift/tasks/deploy.yml:6-8`),
  which recreates a container only when its parameters differ (image, volumes, environment and the other
  `check_container_differs` items) and writes the unit only when the container is not running
  (`module_utils/kolla_docker_worker.py:365-389`, `module_utils/kolla_container_worker.py:67-89`). So the changed unit
  template alone does not restart a running swift container.
- Everything else in the role is unchanged apart from the module rename `kolla_docker` → `kolla_container`: templates,
  prechecks, `start.yml` and `stop.yml` have the same tasks and line numbers. In kolla, only the base image changed: it
  copies `swift_api_audit_map.conf` into `/etc/swift/` (kolla `docker/swift/swift-base/Dockerfile.j2:40`).

## Where to look

### Operate

No operation page gives a command line for the `swift` tag, and the tag has no row of its own in [Tags
§3](../risk/tags.md#3-what-a-tag-really-executes-master-table) or in the [Tag index](../risk/tag-index.md). What the
study says about running it is in fact sheet D: the plays the tag selects
([§3.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#31-plays)) and the task flow per action
([§3.4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#34-task-flow)). Its `reconfigure` is
not `deploy`: `swift` and `bifrost` have their own reconfigure logic ([Repository architecture
§4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy)). The 2024.1 deploy flow is registration,
config, start, check (`roles/swift/tasks/deploy.yml:2-10`) [CODE].

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet D §3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#3-swift)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `swift-*`)

### Before and after a run

- [fact sheet D §3.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#33-ring-files), ring
  files: Kolla does not build rings; the precheck fails unless `account|container|object.builder` and `.ring.gz` exist
  under `{{node_custom_config}}/swift/` (`roles/swift/tasks/precheck.yml:108-131`) [CODE].
- [fact sheet D §3.4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#34-task-flow), `deploy`:
  it does not apply swift config or ring changes to running containers (see the introduction and [What changed in
  2024.1](#what-changed-in-20241)).
- [fact sheet D §3.4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#34-task-flow),
  `reconfigure`: it fails if any listed container is not running (`roles/swift/tasks/reconfigure.yml:32-42`), so it
  cannot repair a crashed container; it runs `kolla_set_configs --check` in each container through
  `<kolla_container_engine> exec -u root` (`roles/swift/tasks/reconfigure.yml:46-54`); under COPY_ALWAYS (the default,
  `group_vars/all.yml:43`) it restarts a container when that check returns rc 1
  (`roles/swift/tasks/reconfigure.yml:91-105`), and with the default `kolla_serial=0` every changed proxy, on every
  proxy host, restarts in that one task (`site.yml:519`) [CODE]. NOT AVAILABLE: whether this opens an outage window.
- [fact sheet D §3.4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#34-task-flow), `upgrade`:
  by default it stops all storage containers on all storage hosts at once, restarts them, then stops and starts the
  proxies (`swift_enable_rolling_upgrade: "yes"`, `roles/swift/defaults/main.yml:73`;
  `roles/swift/tasks/upgrade.yml:2-3`; `roles/swift/tasks/rolling_upgrade.yml:31-43`,
  `roles/swift/tasks/rolling_upgrade.yml:46-68`) [CODE]. Still holds in 2024.1, including the TODO comment that these
  tasks should run host by host (`roles/swift/tasks/rolling_upgrade.yml:28-30`).
- [R21](../risk/risk-register.md#r21), precautions for enabling Swift (or `glance_backend_ceph`) on a running cloud: set
  `glance_backend_*` explicitly before enabling Swift.
- [R24](../risk/risk-register.md#r24), container stop timeout: with `common_options` now passed, the stops and restarts
  of the swift reconfigure and upgrade use `docker_graceful_timeout` (60 s, `group_vars/all.yml:139`) through the
  container's unit (`module_utils/kolla_systemd_worker.py:32`) [CODE].

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `swift`: no handlers are notified
  (deploy does not apply config/ring changes); `stop.yml` wrong container name; precheck probes rsync port 873 vs 10873.
  Status: [CODE], all three still in 2024.1 (`roles/swift/tasks/stop.yml:23-31`, `roles/swift/tasks/precheck.yml:89`,
  `group_vars/all.yml:628`); runtime effects [NOT AVAILABLE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat): the
  sources do not establish the runtime effects of the swift limitations.
- [Q12](../troubleshooting/open-questions.md#q12): "Glance backend switch on enabling Swift". Status: [NOT AVAILABLE].
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`". In 2024.1, 54 roles have a `tasks/reconfigure.yml`: 52
  run `deploy.yml` (skyline through `include_tasks`), and only swift and bifrost have their own logic ([Repository
  architecture §4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy)) [CODE].
- [fact sheet D §3.8](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#38-oddities), "Oddities":
  `enable_swift_recon` is tested without `| bool` (NOT AVAILABLE: whether the template treats that string as true and so
  always enables the recon middleware); the `proxy-logging` and `versioned_writes` filters are defined but not in the
  proxy pipeline. Both still in 2024.1: `enable_swift_recon: "no"` (`group_vars/all.yml:844`) is tested as
  `{% if enable_swift_recon %}` (`roles/swift/templates/account.conf.j2:15,17`, `container.conf.j2:15,17`,
  `object.conf.j2:19,22`); `roles/swift/templates/proxy-server.conf.j2:13,33,92` [CODE].
- [fact sheet D
  §3.5](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#35-config-files-tasksconfigyml):
  NOT AVAILABLE: what changing `swift_hash_path_suffix/prefix` after data is written does. Both come from
  `passwords.yml` (`etc/kolla/passwords.yml:103-104`) and are rendered into `swift.conf`
  (`roles/swift/templates/swift.conf.j2:2-3`) [CODE].
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), items
  1 to 4: the account-auditor guard of `stop.yml` checks `swift_object_auditor`; the precheck checks rsync port 873, but
  rsyncd uses 10873; `{% if enable_swift_recon %}` without `| bool` against the string `"no"`; deploy never restarts on
  config or ring change, reconfigure fails if any swift container is down, and the "rolling" upgrade stops all storage
  at once. All four still hold in 2024.1 (citations above) [CODE].
- [fact sheet D §8](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#8-not-available-list):
  NOT AVAILABLE: whether the swift containers serve the new rings once `reconfigure` has restarted them; the effective
  value of `enable_swift_recon` in the rendered `object-server.conf`.
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): fact sheet D has its own
  NOT AVAILABLE list, and its §3.4, §3.5 and §3.8 are among the sections that contain NOT AVAILABLE marks.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py swift -->

| Item | Value |
|---|---|
| Play | site.yml:511 |
| Tags | swift |
| Play host patterns | swift-account-server, swift-container-server, swift-object-server, swift-proxy-server |
| Node types in play (example inventory) | control, storage |
| Node types running its containers | control, storage |
| Containers | `swift_proxy_server`, `swift_rsyncd`, `swift_account_server`, `swift_account_auditor`, `swift_account_replication_server`, `swift_account_replicator`, `swift_account_reaper`, `swift_container_server`, `swift_container_auditor`, `swift_container_replication_server`, `swift_container_replicator`, `swift_container_updater`, `swift_object_server`, `swift_object_auditor`, `swift_object_replication_server`, `swift_object_replicator`, `swift_object_updater`, `swift_object_expirer` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → start → check |
| Task files | check.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, legacy_upgrade.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, rolling_upgrade.yml, start.yml, stop.yml, upgrade.yml |
| Templates | `account.conf.j2`, `container.conf.j2`, `object.conf.j2`, `proxy-server.conf.j2`, `rsyncd.conf.j2`, `swift-account-auditor.json.j2`, `swift-account-reaper.json.j2`, `swift-account-replication-server.json.j2`, `swift-account-replicator.json.j2`, `swift-account-server.json.j2`, `swift-container-auditor.json.j2`, `swift-container-replication-server.json.j2`, `swift-container-replicator.json.j2`, `swift-container-server.json.j2`, `swift-container-updater.json.j2`, `swift-object-auditor.json.j2`, `swift-object-expirer.json.j2`, `swift-object-replication-server.json.j2`, `swift-object-replicator.json.j2`, `swift-object-server.json.j2`, `swift-object-updater.json.j2`, `swift-proxy-server.json.j2`, `swift-rsyncd.json.j2`, `swift.conf.j2` |
| Handlers (definition order) | Restart swift-proxy-server container |
| Key variables | `enable_swift`, `swift_devices_*`, `swift_*_server ports` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [fact sheet D §3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#3-swift) — the per-role
  evidence: plays, services, ring files, task flow, config files, networks and ports
- [Glance](glance.md) — enabling Swift changes Glance's default backend
- [Repository architecture §4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy) — swift is one of the
  two roles with their own reconfigure logic
- [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) — swift config and rings are copied only at
  container start
- [Predict and inspect a run](../operations/predict-a-run.md) — `kolla_set_configs --check`, which the swift reconfigure
  runs
- [Components](index.md) — the other component pages
