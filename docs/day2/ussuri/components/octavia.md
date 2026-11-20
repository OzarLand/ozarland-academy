---
title: Octavia
description: Where the study covers Octavia (role octavia), which has no operation page of its own, from its fact sheet to the manual amphora resources and known bugs.
tags: [octavia, upgrade, one-shot, dependencies, bugs, unknowns]
---

# Octavia

This page is the starting point for Octavia, the `octavia` role: the containers `octavia_api`, `octavia_health_manager`,
`octavia_housekeeping` and `octavia_worker`, on the control nodes of the example inventory, selected by the tag
`octavia`. The role creates no OpenStack resources: the amphora image, flavor, network and security group are all manual
in Ussuri ([Component dependencies §3](dependencies.md#3-control-plane-services)). The lists below say where the study
covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open;
the service card follows them.

## Where to look

### Operate

No operation page gives a command line for the `octavia` tag, and the tag has no row of its own in [Tags
§3](../risk/tags.md#3-what-a-tag-really-executes-master-table) or in the [Tag index](../risk/tag-index.md). What the
study says about running it is in fact sheet D: the plays the tag selects
([§2.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#21-plays)) and the task flow per action
([§2.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#23-task-flow)).

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet D §2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#2-octavia)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `octavia-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

### Before and after a run

- [fact sheet D §2.5][sheet-d-25], "OpenStack resources: Kolla creates none": in Ussuri the role does not create the
  amphora flavor, image, keypair, lb-mgmt network, security group or certificates; `amp_boot_network_list`,
  `amp_secgroup_list` and `amp_flavor_id` are empty by default, and no precheck validates them.
- [fact sheet D §2.6][sheet-d-26], health-manager network requirements: every octavia host (api, worker and housekeeping
  too) must have `octavia_network_interface` with an address, or templating fails; Kolla does not create the lb-mgmt
  interface, bridge or VLAN on the controllers.
- [fact sheet D §2.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#23-task-flow):
  `reconfigure` = `deploy`, so the DB sync and keystone registration re-run; `upgrade` does not run `register.yml`.
- [fact sheet C §4.2][sheet-c-42]: enabling or disabling any service that has a horizon plugin (designate, octavia,
  magnum, …) changes the horizon container environment; the horizon container is then recreated on the next
  deploy/reconfigure even if no horizon config changed.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `octavia`: upgrade removes the
  octavia admin role on `admin` without re-registering; no amphora resources are created. Status: [CODE].
- [fact sheet D §2.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#23-task-flow): BUG
  (consequence NOT AVAILABLE): if an operator kept Train behaviour with `octavia_service_auth_project: admin`, every
  upgrade removes the role that register.yml granted. NOT AVAILABLE: whether Octavia service-auth then fails until the
  next deploy/reconfigure re-adds the role.
- [fact sheet D §2.6][sheet-d-26]: adding or removing a health-manager host changes octavia.conf on all octavia hosts
  and restarts them. NOT AVAILABLE: whether the controller list is written into an amphora at boot, so that existing
  amphorae keep the old list until failover.
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  5: `heartbeat_key = insecure` is hard-coded; the amp network, secgroup and flavor are empty by default with no
  precheck; the upgrade unconditionally removes the octavia admin role on the admin project; the HM precheck uses the
  wrong address; the CA private key is copied to 3 services.
- [fact sheet D §2.5][sheet-d-25]: if `enable_barbican`, the region and endpoint for the cert manager are set in
  `octavia.conf`. NOT AVAILABLE: whether TLS-terminated listeners need barbican.
- [fact sheet D §8](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#8-not-available-list):
  NOT AVAILABLE: Octavia amphora behaviour after a change in the health-manager host list.
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  15: Barbican and other bootstraps (octavia, manila, ceilometer, masakari, zun, cyborg) re-run their DB sync container
  on every deploy/reconfigure.
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): fact sheet D has its own
  NOT AVAILABLE list, and its §2.3, §2.5 and §2.6 are among the sections that contain NOT AVAILABLE marks.
- [Open questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry on
  Octavia.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py octavia -->

| Item | Value |
|---|---|
| Play | site.yml:1183 |
| Tags | octavia |
| Play host patterns | octavia-api, octavia-health-manager, octavia-housekeeping, octavia-worker |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `octavia_api`, `octavia_health_manager`, `octavia_housekeeping`, `octavia_worker` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `octavia-api.json.j2`, `octavia-health-manager.json.j2`, `octavia-housekeeping.json.j2`, `octavia-worker.json.j2`, `octavia.conf.j2` |
| Handlers (definition order) | Restart octavia-api container; Restart octavia-health-manager container; Restart octavia-housekeeping container; Restart octavia-worker container |
| Key variables | `enable_octavia`, `octavia_amp_*`, `octavia_network_interface` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

## Related

- [fact sheet D §2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#2-octavia) — the per-role
  evidence: plays, services, task flow, config files and handlers, health-manager network requirements
- [Horizon](horizon.md) — octavia is one of the services with a horizon plugin: enabling or disabling it recreates the
  horizon container on the next deploy/reconfigure
- [Barbican](barbican.md) — if `enable_barbican`, `octavia.conf` gets the region and endpoint for the cert manager
- [Component dependencies §3](dependencies.md#3-control-plane-services) — Octavia's config references Nova, Neutron and
  Glance
- [Execution flow §2.2](../concepts/deployment-execution-flow.md#22-openstack-control-plane-deployment-order) — Octavia
  is near the end of the deployment order
- [Components](index.md) — the other component pages

[sheet-c-42]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#42-horizon_services-ansibleroleshorizondefaultsmainyml2-69
[sheet-d-25]: ../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#25-openstack-resources-kolla-creates-none
[sheet-d-26]: ../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#26-health-manager-network-requirements
