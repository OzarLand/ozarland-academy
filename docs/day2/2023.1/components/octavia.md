---
title: Octavia
description: "Where the study covers Octavia (role octavia), which has no operation page: its fact sheet, the amphora resources it now creates and known bugs."
tags: [octavia, upgrade, one-shot, dependencies, bugs, unknowns]
---

# Octavia

This page is the starting point for Octavia, the `octavia` role: the containers `octavia_api`, `octavia_health_manager`,
`octavia_housekeeping` and `octavia_worker`, plus `octavia_driver_agent` when `enable_octavia_driver_agent` (default:
only
with `neutron_plugin_agent: ovn`, `group_vars/all.yml:735`), on the control nodes of the example inventory, selected by
the tag `octavia`. **Changed in 2023.1:** with `octavia_auto_configure` (default: true when `amphora` is in
`octavia_provider_drivers`, which it is by default, `group_vars/all.yml:1228`, `roles/octavia/defaults/main.yml:361`),
`deploy` and `reconfigure` create the amphora flavor, SSH keypair, security groups, lb-mgmt network and subnet (and a
router for IPv6), run_once on `octavia-api[0]` (`roles/octavia/tasks/deploy.yml:4-5`, `prepare.yml:2-160`). The amphora
image and the four certificate files are still the operator's ([Component dependencies
§3](dependencies.md#3-control-plane-services)). The lists below say where the study
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

- [fact sheet D §2.5][sheet-d-25], "OpenStack resources: Kolla creates none": **no longer true in 2023.1** with the
  default `octavia_auto_configure`. The role then creates the flavor (`amphora`, 1 vCPU, 1024 MB, 5 GB), the keypair,
  the security groups, `lb-mgmt-net`/`lb-mgmt-subnet` (`10.1.0.0/24` by default) and, for IPv6, `lb-mgmt-router`, and
  `octavia.conf` takes `amp_boot_network_list`, `amp_secgroup_list` and `amp_flavor_id` from what it looked up
  (`roles/octavia/tasks/prepare.yml:2-160`, `get_resources_info.yml`, `config.yml:2-3`,
  `templates/octavia.conf.j2:90-107`, `defaults/main.yml:294-299, :344-354`) [CODE]. It does not create the amphora
  image (`amp_image_tag = amphora`, `octavia.conf.j2:88`). The certificates come from `kolla-ansible
  octavia-certificates` or the operator; a precheck fails when one of the four files is missing from
  `/etc/kolla/config/octavia/` (`roles/octavia/tasks/precheck.yml:40-54`). With `octavia_auto_configure: no`, the three
  `amp_*` options are written only if the operator defines them (`octavia.conf.j2:90-102`), with no precheck.
- `octavia_auto_configure` and an upgrade from Ussuri: the comment in `group_vars/all.yml:1225-1227` says to set it to
  `no` and keep the previous Octavia configuration when upgrading from Ussuri. With it left at its default, `upgrade`
  runs `config.yml`, whose first step looks up the flavor, project, security groups and network by name
  (`roles/octavia/tasks/upgrade.yml:2`, `config.yml:2-3`, `get_resources_info.yml`) [CODE]; what happens when the
  manually created Ussuri resources have other names is [NOT AVAILABLE] (the `os_*_info` modules are not in these
  sources).
- [fact sheet D §2.6][sheet-d-26], health-manager network requirements: every octavia host (api, worker and housekeeping
  too) must have `octavia_network_interface` with an address, or templating fails (`octavia.conf.j2:79-81`,
  `group_vars/all.yml:244, :269`). With the default `octavia_network_type: provider`, the interface defaults to
  `api_interface` and Kolla creates nothing on the controllers. **New in 2023.1:** with `octavia_network_type: tenant`
  (and `octavia_auto_configure`), the interface defaults to `o-hm0`, and on each health-manager host Kolla creates a
  Neutron port, adds it to `br-int` with `docker exec openvswitch_vswitchd ovs-vsctl`, and installs and starts an
  `octavia-interface` systemd unit (`roles/octavia/tasks/config-host.yml:2-6`, `hm-interface.yml:2-100`); a precheck
  rejects `tenant` unless `neutron_plugin_agent` is `openvswitch` (`precheck.yml:56-65`) [CODE].
- [fact sheet D §2.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#23-task-flow):
  `reconfigure` = `deploy`, so the DB sync, keystone registration and, with `octavia_auto_configure`, the resource
  creation re-run; `upgrade` runs neither `register.yml` nor `prepare.yml` nor `config-host.yml`
  (`roles/octavia/tasks/reconfigure.yml:2`, `deploy.yml:2-19`, `upgrade.yml:2-9`) [CODE].
- [fact sheet C §4.2][sheet-c-42]: enabling or disabling any service that has a horizon plugin (designate, octavia,
  magnum, …) changes the horizon container environment; the horizon container is then recreated on the next
  deploy/reconfigure even if no horizon config changed.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `octavia`: both Ussuri items are
  gone in 2023.1. `upgrade.yml` no longer has the "Removing octavia user from admin project" task (it is config,
  check-containers, bootstrap_service, flush, `roles/octavia/tasks/upgrade.yml:2-9`), and amphora resources other than
  the image are created when `octavia_auto_configure` is on (above). Status: [CODE].
- [fact sheet D §2.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#23-task-flow): the Ussuri
  BUG about `octavia_service_auth_project: admin` losing its role on every upgrade does not apply to 2023.1, since the
  removal task is gone (`roles/octavia/tasks/upgrade.yml:2-9`) [CODE].
- [fact sheet D §2.6][sheet-d-26]: adding or removing a health-manager host changes octavia.conf on all octavia hosts
  and restarts them (`controller_ip_port_list` loops over `octavia-health-manager`, `octavia.conf.j2:81`). NOT
  AVAILABLE: whether the controller list is written into an amphora at boot, so that existing
  amphorae keep the old list until failover.
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  5, read against 2023.1: `heartbeat_key = insecure` is still hard-coded (`octavia.conf.j2:80`); the amp network,
  secgroup and flavor are filled in by default (`octavia_auto_configure`) and stay unchecked only with it off; the
  admin-role removal on upgrade is gone; the HM precheck still tests the port on `api_interface_address` while the
  health manager binds `octavia_network_interface_address` (`precheck.yml:29-38`, `octavia.conf.j2:79`), which differ
  only when `octavia_network_interface` is not `api_interface` (e.g. `tenant`); the CA private key
  (`server_ca.key.pem`) is still copied to worker, housekeeping and health-manager (`config.yml:120-171`) [CODE].
- [fact sheet D §2.5][sheet-d-25]: if `enable_barbican`, the region and endpoint for the cert manager are set in
  `octavia.conf` (`octavia.conf.j2:20-24`). NOT AVAILABLE: whether TLS-terminated listeners need barbican.
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
  Octavia. What the amphora resources created by `prepare.yml` do when they already exist with other settings (the
  `os_*` modules run with `state: present`) is [NOT AVAILABLE]: the modules are not in these sources.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py octavia -->

| Item | Value |
|---|---|
| Play | site.yml:885 |
| Tags | octavia |
| Play host patterns | octavia-api, octavia-health-manager, octavia-housekeeping, octavia-worker |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `octavia_api`, `octavia_driver_agent`, `octavia_health_manager`, `octavia_housekeeping`, `octavia_worker` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → prepare (if) → config-host → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config-host.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, get_resources_info.yml, hm-interface.yml, loadbalancer.yml, main.yml, openrc.yml, precheck.yml, prepare.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `octavia-api.json.j2`, `octavia-driver-agent.json.j2`, `octavia-health-manager.json.j2`, `octavia-housekeeping.json.j2`, `octavia-interface.service.j2`, `octavia-openrc.sh.j2`, `octavia-ssh-key.j2`, `octavia-worker.json.j2`, `octavia-wsgi.conf.j2`, `octavia.conf.j2` |
| Handlers (definition order) | Restart octavia-api container; Restart octavia-driver-agent container; Restart octavia-health-manager container; Restart octavia-housekeeping container; Restart octavia-worker container |
| Key variables | `enable_octavia`, `octavia_amp_*`, `octavia_network_interface` |
| Role dependencies | none |

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
