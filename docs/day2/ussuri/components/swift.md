---
title: Swift
description: Where the study covers Swift (role swift), an old-style role with its own reconfigure logic, from its fact sheet to known bugs and open points.
tags: [swift, reconfigure, upgrade, kolla-set-configs, dependencies, bugs, unknowns]
---

# Swift

This page is the starting point for Swift, the `swift` role: `swift_proxy_server`, `swift_rsyncd` and the account,
container and object containers (18 in all), on the control and storage nodes of the example inventory, selected by the
tag `swift`. The rings are operator-built ([Component dependencies §3](dependencies.md#3-control-plane-services)), and
`deploy` does not apply swift config or ring changes to running containers: no task of the role notifies a handler
([fact sheet D §3.4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#34-task-flow)). The lists
below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to check around
a run and what stays open; the service card follows them.

## Where to look

### Operate

No operation page gives a command line for the `swift` tag, and the tag has no row of its own in [Tags
§3](../risk/tags.md#3-what-a-tag-really-executes-master-table) or in the [Tag index](../risk/tag-index.md). What the
study says about running it is in fact sheet D: the plays the tag selects
([§3.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#31-plays)) and the task flow per action
([§3.4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#34-task-flow)). Its `reconfigure` is
not `deploy`: `swift` and `bifrost` have their own reconfigure logic ([Repository architecture
§4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy)).

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet D §3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#3-swift)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `swift-*`)

### Before and after a run

- [fact sheet D §3.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#33-ring-files), ring
  files: Kolla does not build rings; the precheck fails unless `account|container|object.builder` and `.ring.gz` exist
  under `{{node_custom_config}}/swift/`.
- [fact sheet D §3.4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#34-task-flow), `deploy`:
  it does not apply swift config or ring changes to running containers.
- [fact sheet D §3.4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#34-task-flow),
  `reconfigure`: it fails if any listed container is not running, so it cannot repair a crashed container; under
  COPY_ALWAYS (the default) it restarts a container when `kolla_set_configs --check` returns rc 1, and with the default
  `kolla_serial=0` every changed proxy, on every proxy host, restarts in that one task. NOT AVAILABLE: whether this
  opens an outage window.
- [fact sheet D §3.4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#34-task-flow), `upgrade`:
  by default it stops all storage containers on all storage hosts at once, restarts them, then stops and starts the
  proxies.
- [R21](../risk/risk-register.md#r21), precautions for enabling Swift (or `glance_backend_ceph`) on a running cloud: set
  `glance_backend_*` explicitly before enabling Swift.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `swift`: no handlers are notified
  (deploy does not apply config/ring changes); `stop.yml` wrong container name; precheck probes rsync port 873 vs 10873.
  Status: [CODE]; runtime effects [NOT AVAILABLE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat): the
  sources do not establish the runtime effects of the swift limitations.
- [Q12](../troubleshooting/open-questions.md#q12): "Glance backend switch on enabling Swift". Status: [NOT AVAILABLE].
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`" for 70 of the 72 roles that have a
  `tasks/reconfigure.yml`: only swift and bifrost have their own logic [CODE].
- [fact sheet D §3.8](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#38-oddities), "Oddities":
  `enable_swift_recon` is tested without `| bool` (NOT AVAILABLE: whether the template treats that string as true and so
  always enables the recon middleware); the `proxy-logging` and `versioned_writes` filters are defined but not in the
  proxy pipeline.
- [fact sheet D
  §3.5](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#35-config-files-tasksconfigyml):
  NOT AVAILABLE: what changing `swift_hash_path_suffix/prefix` after data is written does.
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), items
  1 to 4: the account-auditor guard of `stop.yml` checks `swift_object_auditor`; the precheck checks rsync port 873, but
  rsyncd uses 10873; `{% if enable_swift_recon %}` without `| bool` against the string `"no"`; deploy never restarts on
  config or ring change, reconfigure fails if any swift container is down, and the "rolling" upgrade stops all storage
  at once.
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
| Play | site.yml:643 |
| Tags | swift |
| Play host patterns | swift-account-server, swift-container-server, swift-object-server, swift-proxy-server |
| Node types in play (example inventory) | control, storage |
| Node types running its containers | control, storage |
| Containers | `swift_proxy_server`, `swift_rsyncd`, `swift_account_server`, `swift_account_auditor`, `swift_account_replication_server`, `swift_account_replicator`, `swift_account_reaper`, `swift_container_server`, `swift_container_auditor`, `swift_container_replication_server`, `swift_container_replicator`, `swift_container_updater`, `swift_object_server`, `swift_object_auditor`, `swift_object_replication_server`, `swift_object_replicator`, `swift_object_updater`, `swift_object_expirer` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → start → check |
| Task files | check.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, legacy_upgrade.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, rolling_upgrade.yml, start.yml, stop.yml, upgrade.yml |
| Templates | `account.conf.j2`, `container.conf.j2`, `object.conf.j2`, `proxy-server.conf.j2`, `rsyncd.conf.j2`, `swift-account-auditor.json.j2`, `swift-account-reaper.json.j2`, `swift-account-replication-server.json.j2`, `swift-account-replicator.json.j2`, `swift-account-server.json.j2`, `swift-container-auditor.json.j2`, `swift-container-replication-server.json.j2`, `swift-container-replicator.json.j2`, `swift-container-server.json.j2`, `swift-container-updater.json.j2`, `swift-object-auditor.json.j2`, `swift-object-expirer.json.j2`, `swift-object-replication-server.json.j2`, `swift-object-replicator.json.j2`, `swift-object-server.json.j2`, `swift-object-updater.json.j2`, `swift-proxy-server.json.j2`, `swift-rsyncd.json.j2`, `swift.conf.j2` |
| Handlers (definition order) | Restart swift-proxy-server container |
| Key variables | `enable_swift`, `swift_devices_*`, `swift_*_server ports` |
| Role dependencies | `common` (meta) |

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
