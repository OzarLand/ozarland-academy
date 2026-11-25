---
title: Octavia
description: "Where the 2025.1 study covers Octavia (role octavia): the amphora resources it creates, the jobboard on Redis or Valkey, the persistence DB and known bugs."
tags: [octavia, upgrade, one-shot, prechecks, dependencies, bugs, unknowns]
---

# Octavia

This page is the starting point for Octavia, the `octavia` role: the containers `octavia_api`,
`octavia_health_manager`, `octavia_housekeeping` and `octavia_worker`, plus `octavia_driver_agent` when
`enable_octavia_driver_agent` (default: only with `neutron_plugin_agent: ovn`, `group_vars/all.yml:949`)
(`roles/octavia/defaults/main.yml:2-57`), on the control
nodes of the example inventory (`inventory/multinode:161-162`), selected by the tag `octavia` (`site.yml:979-994`).
**Still holds in 2025.1:** with `octavia_auto_configure` (default: true when `amphora` is in `octavia_provider_drivers`,
which it is by default, `group_vars/all.yml:1411`, `roles/octavia/defaults/main.yml:387`), `deploy` and `reconfigure`
create the amphora flavor, SSH keypair, security groups, lb-mgmt network and subnet (and a router for IPv6), run_once
on `octavia-api[0]` (`roles/octavia/tasks/deploy.yml:4-5`, `roles/octavia/tasks/prepare.yml:2-161`) [CODE]. The amphora
image and the four certificate files are still the operator's ([Component dependencies
§3](dependencies.md#3-control-plane-services)). As in 2024.1, the amphora provider also turns on the Octavia
jobboard by default (`group_vars/all.yml:950`), which needs Redis or, new in 2025.1, Valkey, and a second database,
`octavia_persistence` [CODE].

**Changed in 2025.1** [CODE]:
- **Jobboard on Valkey or Redis:** with `enable_valkey`, the `[task_flow]` section lists the `valkey` hosts with
  `valkey_master_password` and `valkey_sentinel_port`; otherwise, with `enable_redis`, the `redis` hosts as in 2024.1
  (`roles/octavia/templates/octavia.conf.j2:168-186`). The precheck now accepts either (`roles/octavia/tasks/precheck.yml:68-74`).
  Both `enable_redis` and `enable_valkey` default to `no` (`group_vars/all.yml:959`, `group_vars/all.yml:965`), so a
  default Octavia configuration still fails `prechecks` until one of them is on or `enable_octavia_jobboard: no`. The
  sentinel name is still written as `kolla` (`roles/octavia/templates/octavia.conf.j2:183`), which matches the default
  `valkey_sentinel_monitor_name` (`group_vars/all.yml:751`) but not an override of it.
- **`upgrade` no longer creates the persistence database:** the two persistence tasks added to `upgrade.yml` for the
  2023.2 → 2024.1 path are gone (`roles/octavia/tasks/upgrade.yml:1-9`); `deploy` and `reconfigure` still create it
  (`roles/octavia/tasks/bootstrap.yml:18-32`, `roles/octavia/tasks/bootstrap.yml:54-72`).
- **The OVN driver agent always talks to the OVN SB database directly:** `ovn_sb_connection` in `octavia.conf` is
  `ovn_sb_connection_no_relay` (`roles/octavia/templates/octavia.conf.j2:33`, `group_vars/all.yml:647`), so it does not
  follow the new OVN SB relays ([OVN](ovn.md)).
- **`[neutron] valid_interfaces = internal`** replaces `endpoint_type = internal`
  (`roles/octavia/templates/octavia.conf.j2:160-161`).
- **Resource tasks use the `openstack.cloud` collection:** `prepare.yml`, `get_resources_info.yml`, `hm-interface.yml`
  and `register.yml` call `openstack.cloud.*` modules instead of the old `os_*` names, and the openrc task's `become`
  follows `octavia_openrc_become` (default `true`).
- **Restarts:** the config tasks notify nothing; `check-containers.yml` imports `service-check-containers`, which
  restarts only the containers whose configuration or definition changed
  ([Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)); the five handlers have no
  `kolla_action != "config"` guard any more. `check.yml`, empty in 2024.1, runs the `service-check` role
  (`roles/octavia/tasks/check.yml:2-4`).
- **No rolling reconfigure or upgrade through the CLI** ([F19](../reference/findings.md#f19)).
- **First-run changes:** the queue settings and `use_queue_manager` are always rendered
  (`roles/octavia/templates/octavia.conf.j2:133-147`; [F17](../reference/findings.md#f17)), the containers always
  mount `/dev/shm`, `www_authenticate_uri` is `keystone_public_url` and `memcache_security_strategy` a variable
  (`roles/octavia/templates/octavia.conf.j2:57,63,74`). Every octavia container restarts or is recreated.
- **CLI:** `kolla-ansible prechecks` and `kolla-ansible octavia-certificates --check-expiry <days>` are now Python
  commands (`kolla_ansible/cli/commands.py:99-106`, `kolla_ansible/cli/commands.py:198-224`); they pass the same
  variables as the 2024.1 shell script.

The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the service card follows them.

## Since 2024.1, still in 2025.1

- **The jobboard and its database** [CODE]: `octavia.conf` gets a `[task_flow]` section with
  `persistence_connection` to `octavia_persistence` (`roles/octavia/templates/octavia.conf.j2:168-186`,
  `roles/octavia/defaults/main.yml:80-82`); the backend SSL options are written as `ssl:False`
  (`roles/octavia/templates/octavia.conf.j2:182`, `roles/octavia/templates/octavia.conf.j2:184`). The password
  `octavia_persistence_database_password` is a key of `etc/kolla/passwords.yml:136`. The assert runs only in the
  precheck action: the role includes `<kolla_action>.yml` (`roles/octavia/tasks/main.yml:2`) and `prechecks` sets
  `kolla_action=precheck` (`kolla_ansible/cli/commands.py:106`); `deploy`, `reconfigure` and `upgrade` render the
  `[task_flow]` section whether or not the Redis or Valkey play runs (`site.yml:385-411`). How Octavia behaves when
  the jobboard points at hosts with no Redis or Valkey is [NOT AVAILABLE].
- **The bootstrap container also runs `upgrade_persistence`** [CODE]: with `KOLLA_BOOTSTRAP`, the `octavia-api` image
  runs `octavia-db-manage upgrade head` then `octavia-db-manage upgrade_persistence` (kolla
  `docker/octavia/octavia-api/extend_start.sh:5-9`), on every deploy, reconfigure and upgrade
  (`roles/octavia/tasks/bootstrap_service.yml:2-20`). What `upgrade_persistence` does when the jobboard is off is
  [NOT AVAILABLE].
- **`kolla-ansible octavia-certificates --check-expiry <days>`** [CODE]: it adds
  `-e octavia_certs_check_expiry=yes -e octavia_certs_expiry_limit=<days>` (`kolla_ansible/cli/commands.py:217-222`);
  the `octavia-certificates` role, unchanged since 2024.1, then only reads `server_ca.cert.pem`, `client_ca.cert.pem`
  and `client.cert-and-key.pem` in `/etc/kolla/config/octavia/` and asserts that each one is still valid in `<days>`
  days (`roles/octavia-certificates/tasks/main.yml:10-12`, `roles/octavia-certificates/tasks/check_expiry.yml:2-24`).
  The CA private key `server_ca.key.pem` is not checked. The default validity is 365 days for the client certificate
  and 3650 days for both CAs (`roles/octavia-certificates/defaults/main.yml:22`,
  `roles/octavia-certificates/defaults/main.yml:30`, `roles/octavia-certificates/defaults/main.yml:38`).
- **Notifications** [CODE]: `driver = messagingv2` and `topics = notifications` only with Ceilometer, otherwise
  `driver = noop` (`roles/octavia/templates/octavia.conf.j2:125-129`).

## Where to look

### Operate

No operation page gives a command line for the `octavia` tag, and the tag has no row of its own in [Tags
§3](../risk/tags.md#3-what-a-tag-really-executes-master-table) or in the [Tag index](../risk/tag-index.md). What the
study says about running it is in fact sheet D: the plays the tag selects
([§2.1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#21-plays)) and the task flow per action
([§2.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#23-task-flow)). The certificate expiry
check is the command `kolla-ansible octavia-certificates --check-expiry <days>` (above); it runs on `localhost` only
(`ansible/octavia-certificates.yml:1-5`).

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Redis or Valkey** [CODE]: with the default jobboard, Octavia's config lists the `valkey` hosts, or else the `redis`
  hosts (`roles/octavia/templates/octavia.conf.j2:172`, `roles/octavia/templates/octavia.conf.j2:176`), and
  `prechecks` requires `enable_redis` or `enable_valkey` (`roles/octavia/tasks/precheck.yml:68-74`). In `site.yml` the
  redis and valkey plays come before the octavia play (`site.yml:385`, `site.yml:399`, `site.yml:979-994`).

### Evidence

- **Fact sheet:** [fact sheet D §2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#2-octavia)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `octavia-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

### Before and after a run

- Before `prechecks`, `deploy` or `upgrade` with the amphora provider, decide on the jobboard: `enable_valkey: yes`
  or `enable_redis: yes` (deployed by its own play) or `enable_octavia_jobboard: no`; and make sure `passwords.yml`
  has `octavia_persistence_database_password` (see [Since 2024.1](#since-20241-still-in-20251)) [CODE]. Switching an
  existing jobboard from Redis to Valkey changes `octavia.conf` on every octavia host; what happens to jobs in flight
  is [NOT AVAILABLE], to be confirmed by the community.
- [fact sheet D §2.5][sheet-d-25], "OpenStack resources: Kolla creates none": **still not true in 2025.1** with the
  default `octavia_auto_configure`. The role then creates the flavor (`amphora`, 1 vCPU, 1024 MB, 5 GB), the keypair,
  the security groups, `lb-mgmt-net`/`lb-mgmt-subnet` (`10.1.0.0/24` by default) and, for IPv6, `lb-mgmt-router`, and
  `octavia.conf` takes `amp_boot_network_list`, `amp_secgroup_list` and `amp_flavor_id` from what it looked up
  (`roles/octavia/tasks/prepare.yml:2-161`, `roles/octavia/tasks/get_resources_info.yml:2-75`,
  `roles/octavia/tasks/config.yml:2-3`, `roles/octavia/templates/octavia.conf.j2:91-109`,
  `roles/octavia/defaults/main.yml:320-325`, `roles/octavia/defaults/main.yml:370-383`) [CODE]. It does not create the
  amphora image (`amp_image_tag = amphora`, `roles/octavia/templates/octavia.conf.j2:89`,
  `roles/octavia/defaults/main.yml:296`). The certificates come from `kolla-ansible octavia-certificates` or the
  operator; a precheck fails when one of the four files is missing from `/etc/kolla/config/octavia/`
  (`roles/octavia/tasks/precheck.yml:41-55`). With `octavia_auto_configure: no`, the four `amp_*` options are written
  only if the operator defines them (`roles/octavia/templates/octavia.conf.j2:91-103`), with no precheck.
- `octavia_auto_configure` and older upgrades: the comment that says to set it to `no` when upgrading from Ussuri is
  still there (`group_vars/all.yml:1409-1410`), although 2025.1 upgrades from 2024.1. With it left at its default,
  `upgrade` runs `config.yml`, whose first step looks up the
  flavor, project, security groups and network by name (`roles/octavia/tasks/upgrade.yml:2`,
  `roles/octavia/tasks/config.yml:2-3`, `roles/octavia/tasks/get_resources_info.yml:2-75`) [CODE]; what happens when
  resources created by hand have other names is [NOT AVAILABLE] (the `openstack.cloud` modules are not in these
  sources).
- [fact sheet D §2.6][sheet-d-26], health-manager network requirements: every octavia host (api, worker and housekeeping
  too) must have `octavia_network_interface` with an address, or templating fails
  (`roles/octavia/templates/octavia.conf.j2:80-82`, `group_vars/all.yml:303`, `group_vars/all.yml:326`). With the
  default `octavia_network_type: provider` (`group_vars/all.yml:1419`), the interface defaults to `api_interface` and
  Kolla creates nothing on the controllers. With `octavia_network_type: tenant` (and `octavia_auto_configure`), the
  interface defaults to `o-hm0`, and on each health-manager host Kolla creates a Neutron port, adds it to `br-int` with
  `<engine> exec openvswitch_vswitchd ovs-vsctl`, and installs and starts an `octavia-interface` systemd unit
  (`roles/octavia/tasks/config-host.yml:2-6`, `roles/octavia/tasks/hm-interface.yml:2-100`); a precheck rejects
  `tenant` unless `neutron_plugin_agent` is `openvswitch` (`roles/octavia/tasks/precheck.yml:57-66`) [CODE].
- [fact sheet D §2.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#23-task-flow):
  `reconfigure` = `deploy`, so the database creation (two databases), the DB sync, keystone registration and, with
  `octavia_auto_configure`, the resource creation re-run; `upgrade` runs neither `register.yml` nor `prepare.yml` nor
  `config-host.yml` (`roles/octavia/tasks/reconfigure.yml:2`, `roles/octavia/tasks/deploy.yml:2-19`,
  `roles/octavia/tasks/upgrade.yml:1-9`) [CODE].
- [fact sheet C §4.2][sheet-c-42]: enabling or disabling a service that has a horizon plugin (designate, octavia,
  magnum, …) changes the horizon container environment. For Octavia this is `ENABLE_OCTAVIA`, from
  `enable_horizon_octavia`, which follows `enable_octavia` (`roles/horizon/defaults/main.yml:20`,
  `group_vars/all.yml:899`); the horizon check compares the environment
  (`roles/service-check-containers/tasks/main.yml:19`, `module_utils/kolla_container_worker.py:84`), so the horizon
  container is recreated on the next deploy/reconfigure even if no horizon config changed [CODE].

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `octavia`: both Ussuri items stay
  gone in 2025.1. `upgrade.yml` has no "Removing octavia user from admin project" task
  (`roles/octavia/tasks/upgrade.yml:1-9`), and amphora resources other than the image are created when
  `octavia_auto_configure` is on (above). Status: [CODE].
- Since 2024.1: the Redis (in 2025.1, Redis or Valkey) requirement of the jobboard is checked only by `prechecks`; an
  `upgrade` or `deploy` run without `prechecks` renders a jobboard configuration whether or not either is deployed
  (`roles/octavia/tasks/precheck.yml:68-74`, `roles/octavia/templates/octavia.conf.j2:168-186`) [CODE]. The effect on
  the Octavia services is [NOT AVAILABLE].
- [fact sheet D §2.6][sheet-d-26]: adding or removing a health-manager host changes octavia.conf on all octavia hosts
  and restarts them (`controller_ip_port_list` loops over `octavia-health-manager`,
  `roles/octavia/templates/octavia.conf.j2:82`) [CODE]. NOT AVAILABLE: whether the controller list is written into an
  amphora at boot, so that existing amphorae keep the old list until failover. Likewise, a change of the `valkey` or `redis` group
  changes `jobboard_backend_hosts` (`roles/octavia/templates/octavia.conf.j2:172`,
  `roles/octavia/templates/octavia.conf.j2:176`) and so octavia.conf on all octavia
  hosts [CODE].
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  5, read against 2025.1: `heartbeat_key = insecure` is still hard-coded (`roles/octavia/templates/octavia.conf.j2:81`);
  the amp network, secgroup and flavor are filled in by default (`octavia_auto_configure`) and stay unchecked only with
  it off; the admin-role removal on upgrade is gone; the HM precheck still tests the port on `api_interface_address`
  while the health manager binds `octavia_network_interface_address` (`roles/octavia/tasks/precheck.yml:30-39`,
  `roles/octavia/templates/octavia.conf.j2:80`), which differ only when `octavia_network_interface` is not
  `api_interface` (e.g. `tenant`); the CA private key (`server_ca.key.pem`) is still copied to worker, housekeeping and
  health-manager (`roles/octavia/tasks/config.yml:99-138`) [CODE]. Since 2024.1: the jobboard section writes
  `ssl:False` for both the Redis backend and the sentinel (`roles/octavia/templates/octavia.conf.j2:182`,
  `roles/octavia/templates/octavia.conf.j2:184`) [CODE].
- [fact sheet D §2.5][sheet-d-25]: if `enable_barbican`, the region and endpoint for the cert manager are set in
  `octavia.conf` (`roles/octavia/templates/octavia.conf.j2:21-25`). NOT AVAILABLE: whether TLS-terminated listeners
  need barbican.
- [fact sheet D §8](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#8-not-available-list):
  NOT AVAILABLE: Octavia amphora behaviour after a change in the health-manager host list.
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  15: Barbican and other bootstraps (octavia, manila, ceilometer, masakari, zun, cyborg) re-run their DB sync container
  on every deploy/reconfigure. For Octavia this now includes `upgrade_persistence` (kolla
  `docker/octavia/octavia-api/extend_start.sh:5-9`) [CODE].
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): fact sheet D has its own
  NOT AVAILABLE list, and its §2.3, §2.5 and §2.6 are among the sections that contain NOT AVAILABLE marks.
- [Open questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry on
  Octavia. What the amphora resources created by `prepare.yml` do when they already exist with other settings (the
  `openstack.cloud` modules run with `state: present`, `roles/octavia/tasks/prepare.yml:12`) is [NOT AVAILABLE]: the modules are
  not in these sources.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py octavia -->

| Item | Value |
|---|---|
| Play | site.yml:979 |
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
  Glance, and Redis or Valkey for the jobboard
- [Execution flow §2.2](../concepts/deployment-execution-flow.md#22-openstack-control-plane-deployment-order) — Octavia
  is near the end of the deployment order
- [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) — what the
  `bootstrap_octavia` container runs, including `upgrade_persistence`
- [Components](index.md) — the other component pages

[sheet-c-42]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#42-horizon_services-ansibleroleshorizondefaultsmainyml2-76
[sheet-d-25]: ../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#25-openstack-resources-kolla-creates-none
[sheet-d-26]: ../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#26-health-manager-network-requirements
