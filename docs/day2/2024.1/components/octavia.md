---
title: Octavia
description: "Where the 2024.1 study covers Octavia (role octavia): the amphora resources it creates, the jobboard and its Redis precheck, the persistence DB and known bugs."
tags: [octavia, upgrade, one-shot, prechecks, dependencies, bugs, unknowns]
---

# Octavia

This page is the starting point for Octavia, the `octavia` role: the containers `octavia_api`,
`octavia_health_manager`, `octavia_housekeeping` and `octavia_worker`, plus `octavia_driver_agent` when
`enable_octavia_driver_agent` (default: only with `neutron_plugin_agent: ovn`, `group_vars/all.yml:831`)
(`roles/octavia/defaults/main.yml:2-57`), on the control
nodes of the example inventory (`inventory/multinode:165-166`), selected by the tag `octavia` (`site.yml:981-996`).
**Still holds in 2024.1:** with `octavia_auto_configure` (default: true when `amphora` is in `octavia_provider_drivers`,
which it is by default, `group_vars/all.yml:1323`, `roles/octavia/defaults/main.yml:386`), `deploy` and `reconfigure`
create the amphora flavor, SSH keypair, security groups, lb-mgmt network and subnet (and a router for IPv6), run_once
on `octavia-api[0]` (`roles/octavia/tasks/deploy.yml:4-5`, `roles/octavia/tasks/prepare.yml:2-161`) [CODE]. The amphora
image and the four certificate files are still the operator's ([Component dependencies
§3](dependencies.md#3-control-plane-services)). **New in 2024.1:** the amphora provider also turns on the Octavia
jobboard by default, which needs Redis and a second database (see [What changed in 2024.1](#what-changed-in-20241)).
The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the service card follows them.

## What changed in 2024.1

- **The jobboard is on by default with the amphora provider** [CODE]. `enable_octavia_jobboard` defaults to
  `enable_octavia` and `'amphora' in octavia_provider_drivers` (`group_vars/all.yml:832`), so it is on in a default
  Octavia deployment. `octavia.conf` then gets a `[task_flow]` section
  (`roles/octavia/templates/octavia.conf.j2:177-189`) with:
  - `jobboard_backend_hosts`: the `api` address of every host of the `redis` group
    (`roles/octavia/templates/octavia.conf.j2:180`), which is the control group in the example inventory
    (`inventory/multinode:183-184`);
  - the Redis password `redis_master_password`, the sentinel port `redis_sentinel_port` (`26379`,
    `group_vars/all.yml:606`) and the sentinel name `kolla` (`roles/octavia/templates/octavia.conf.j2:181-186`), the
    name the redis role gives its sentinel master (`roles/redis/templates/redis-sentinel.conf.j2:8`);
  - `persistence_connection` to a new database, `octavia_persistence` (`roles/octavia/templates/octavia.conf.j2:188`,
    `roles/octavia/defaults/main.yml:80-82`).
- **A precheck requires Redis for the jobboard** [CODE]. `prechecks` fails with "Redis must be enabled when using
  octavia jobboard" when `enable_octavia_jobboard` is true and `enable_redis` is not
  (`roles/octavia/tasks/precheck.yml:67-73`), and `enable_redis` defaults to `no` (`group_vars/all.yml:840`). A default
  Octavia configuration therefore fails
  `prechecks` until the operator sets `enable_redis: yes` or `enable_octavia_jobboard: no` (both listed, commented, in
  `etc/kolla/globals.yml:403`, `etc/kolla/globals.yml:414`). The assert runs only in the precheck action: the role
  includes `<kolla_action>.yml` (`roles/octavia/tasks/main.yml:2`) and `prechecks` sets `kolla_action=precheck`
  (`tools/kolla-ansible:444-446`). `deploy`, `reconfigure` and `upgrade` do not assert it: they render the
  `[task_flow]` section from the `redis` group whether or not the redis play runs, and that play runs only on hosts
  where `enable_redis` is true (`site.yml:384-396`). How Octavia behaves when the jobboard points at hosts with no Redis
  is [NOT AVAILABLE] (the Octavia source is not in these sources).
- **A second database, `octavia_persistence`, is created** [CODE]. `deploy` and `reconfigure` create it and its user
  (`octavia_persistence`, all privileges on the schema) in `bootstrap.yml`, next to the main database
  (`roles/octavia/tasks/bootstrap.yml:18-32`, `roles/octavia/tasks/bootstrap.yml:54-72`). These tasks do not depend on
  the jobboard setting: their only condition is `not use_preconfigured_databases`. With ProxySQL, the user and the
  schema are part of Octavia's shard rules (`roles/octavia/defaults/main.yml:87-101`). The password
  `octavia_persistence_database_password` is a new key of `etc/kolla/passwords.yml:140`; it has no default anywhere
  under `ansible/` (grep), and it is used by those tasks, the shard users and `octavia.conf`
  (`roles/octavia/defaults/main.yml:96`, `roles/octavia/templates/octavia.conf.j2:188`). A `passwords.yml` written for
  2023.1 does not have it (2023.1 `etc/kolla/passwords.yml` has no such key).
- **`upgrade` now creates that database too** [CODE]. `upgrade.yml` runs config, check-containers, then the two
  persistence database tasks (with the comment "Run octavia persistence db tasks for upgrade"), then the bootstrap
  container and the handler flush (`roles/octavia/tasks/upgrade.yml:1-46`). The new `octavia.conf` with
  `persistence_connection` is written before the database exists, but the containers restart only at the flush, after
  the bootstrap container (`roles/octavia/tasks/upgrade.yml:43-46`).
- **The bootstrap container also runs `upgrade_persistence`** [CODE]. With `KOLLA_BOOTSTRAP`, the `octavia-api` image
  runs `octavia-db-manage upgrade head` then `octavia-db-manage upgrade_persistence` (kolla
  `docker/octavia/octavia-api/extend_start.sh:5-9`), on every deploy, reconfigure and upgrade
  (`roles/octavia/tasks/bootstrap_service.yml:2-20`). What `upgrade_persistence` does when the jobboard is off, and so
  `persistence_connection` is not rendered, is [NOT AVAILABLE].
- **`kolla-ansible octavia-certificates --check-expiry <days>`** [CODE]. The option is new
  (`tools/kolla-ansible:207`, `tools/kolla-ansible:411-414`); it adds `-e octavia_certs_check_expiry=yes -e
  octavia_certs_expiry_limit=<days>` (`tools/kolla-ansible:550-555`). The `octavia-certificates` role then only reads
  `server_ca.cert.pem`, `client_ca.cert.pem` and `client.cert-and-key.pem` in `/etc/kolla/config/octavia/` on the
  Ansible host and asserts that each one is still valid in `<days>` days
  (`roles/octavia-certificates/tasks/main.yml:10-12`, `roles/octavia-certificates/tasks/check_expiry.yml:2-24`); the
  generation and copy block is skipped (`roles/octavia-certificates/tasks/main.yml:14-51`). The CA private key
  `server_ca.key.pem` is not checked. Without the option the role behaves as before; its `openssl` steps carry
  `creates:`, so existing files in the work directory are kept (`roles/octavia-certificates/tasks/server_ca.yml:9`,
  `roles/octavia-certificates/tasks/server_ca.yml:29`). The default validity is 365 days for the client certificate and
  3650 days for both CAs (`roles/octavia-certificates/defaults/main.yml:22`,
  `roles/octavia-certificates/defaults/main.yml:30`, `roles/octavia-certificates/defaults/main.yml:38`).
- **Other changes to `octavia.conf` and the containers** [CODE]:
  - notifications: `driver = messagingv2` and `topics = notifications` only with Ceilometer, otherwise `driver = noop`
    (`roles/octavia/templates/octavia.conf.j2:123-130`, `roles/octavia/defaults/main.yml:276-280`); 2023.1 wrote no
    `driver` line;
  - RabbitMQ: `rabbit_quorum_queue = true` with the default quorum queues
    (`roles/octavia/templates/octavia.conf.j2:147-148`, [F17](../reference/findings.md#f17)); with
    `om_enable_queue_manager`, `use_queue_manager`, an `[oslo_concurrency]` lock path and a `/dev/shm` mount on all five
    containers (`roles/octavia/templates/octavia.conf.j2:133-138`, `roles/octavia/templates/octavia.conf.j2:191-194`,
    `roles/octavia/defaults/main.yml:192`);
  - HAProxy: the external frontend takes `external_fqdn` and `octavia_api_public_port`
    (`roles/octavia/defaults/main.yml:19-26`), which follows the single external frontend option
    (`group_vars/all.yml:535`);
  - `get_resources_info.yml` and `octavia.conf.j2` no longer fall back to the `openstack_*` result keys of older
    `os_*_info` modules (`roles/octavia/tasks/get_resources_info.yml:72-75`,
    `roles/octavia/templates/octavia.conf.j2:105-107`).
- **Still holds in 2024.1** [CODE]: the five handlers, in the same order, with the module renamed `kolla_container`
  and skipped when `kolla_action` is `config` (`roles/octavia/handlers/main.yml:2-79`); the play still takes `serial`
  from `kolla_serial` and now also sets `max_fail_percentage`, default 100 (`site.yml:989-993`), which never stops the
  play early ([Controlled batches §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).
  The first 2024.1 check of a container whose unit 2023.1 wrote reports drift ([F16](../reference/findings.md#f16)).

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
- **Redis** (new in 2024.1) [CODE]: with the default jobboard, Octavia's config lists the `redis` hosts
  (`roles/octavia/templates/octavia.conf.j2:180`) and `prechecks` requires `enable_redis`
  (`roles/octavia/tasks/precheck.yml:67-73`). In `site.yml` the redis play comes before the octavia play
  (`site.yml:384-396`, `site.yml:981-996`).

### Evidence

- **Fact sheet:** [fact sheet D §2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#2-octavia)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `octavia-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

### Before and after a run

- Before `prechecks`, `deploy` or `upgrade` with the amphora provider, decide on the jobboard: set `enable_redis: yes`
  (Redis is then deployed by its own play) or `enable_octavia_jobboard: no`; and make sure `passwords.yml` has
  `octavia_persistence_database_password` (see [What changed in 2024.1](#what-changed-in-20241)) [CODE].
- [fact sheet D §2.5][sheet-d-25], "OpenStack resources: Kolla creates none": **still not true in 2024.1** with the
  default `octavia_auto_configure`. The role then creates the flavor (`amphora`, 1 vCPU, 1024 MB, 5 GB), the keypair,
  the security groups, `lb-mgmt-net`/`lb-mgmt-subnet` (`10.1.0.0/24` by default) and, for IPv6, `lb-mgmt-router`, and
  `octavia.conf` takes `amp_boot_network_list`, `amp_secgroup_list` and `amp_flavor_id` from what it looked up
  (`roles/octavia/tasks/prepare.yml:2-161`, `roles/octavia/tasks/get_resources_info.yml:2-75`,
  `roles/octavia/tasks/config.yml:2-3`, `roles/octavia/templates/octavia.conf.j2:91-109`,
  `roles/octavia/defaults/main.yml:319-324`, `roles/octavia/defaults/main.yml:369-382`) [CODE]. It does not create the
  amphora image (`amp_image_tag = amphora`, `roles/octavia/templates/octavia.conf.j2:89`,
  `roles/octavia/defaults/main.yml:295`). The certificates come from `kolla-ansible octavia-certificates` or the
  operator; a precheck fails when one of the four files is missing from `/etc/kolla/config/octavia/`
  (`roles/octavia/tasks/precheck.yml:40-54`). With `octavia_auto_configure: no`, the four `amp_*` options are written
  only if the operator defines them (`roles/octavia/templates/octavia.conf.j2:91-103`), with no precheck.
- `octavia_auto_configure` and older upgrades: the comment that says to set it to `no` when upgrading from Ussuri is
  still there (`group_vars/all.yml:1320-1322`), but 2024.1 upgrades from `openstack_previous_release_name: "2023.2"`
  (`group_vars/all.yml:688`). With it left at its default, `upgrade` runs `config.yml`, whose first step looks up the
  flavor, project, security groups and network by name (`roles/octavia/tasks/upgrade.yml:2`,
  `roles/octavia/tasks/config.yml:2-3`, `roles/octavia/tasks/get_resources_info.yml:2-75`) [CODE]; what happens when
  resources created by hand have other names is [NOT AVAILABLE] (the `os_*` modules are not in these sources).
- [fact sheet D §2.6][sheet-d-26], health-manager network requirements: every octavia host (api, worker and housekeeping
  too) must have `octavia_network_interface` with an address, or templating fails
  (`roles/octavia/templates/octavia.conf.j2:80-82`, `group_vars/all.yml:292`, `group_vars/all.yml:317`). With the
  default `octavia_network_type: provider` (`group_vars/all.yml:1331`), the interface defaults to `api_interface` and
  Kolla creates nothing on the controllers. With `octavia_network_type: tenant` (and `octavia_auto_configure`), the
  interface defaults to `o-hm0`, and on each health-manager host Kolla creates a Neutron port, adds it to `br-int` with
  `<engine> exec openvswitch_vswitchd ovs-vsctl`, and installs and starts an `octavia-interface` systemd unit
  (`roles/octavia/tasks/config-host.yml:2-6`, `roles/octavia/tasks/hm-interface.yml:2-100`); a precheck rejects
  `tenant` unless `neutron_plugin_agent` is `openvswitch` (`roles/octavia/tasks/precheck.yml:56-65`) [CODE].
- [fact sheet D §2.3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#23-task-flow):
  `reconfigure` = `deploy`, so the database creation (now two databases), the DB sync, keystone registration and, with
  `octavia_auto_configure`, the resource creation re-run; `upgrade` runs neither `register.yml` nor `prepare.yml` nor
  `config-host.yml` (`roles/octavia/tasks/reconfigure.yml:2`, `roles/octavia/tasks/deploy.yml:2-19`,
  `roles/octavia/tasks/upgrade.yml:1-46`) [CODE].
- [fact sheet C §4.2][sheet-c-42]: enabling or disabling a service that has a horizon plugin (designate, octavia,
  magnum, …) changes the horizon container environment. For Octavia this is `ENABLE_OCTAVIA`, from
  `enable_horizon_octavia`, which follows `enable_octavia` (`roles/horizon/defaults/main.yml:20`,
  `group_vars/all.yml:785`); the horizon check compares the environment
  (`roles/horizon/tasks/check-containers.yml:11`, `module_utils/kolla_container_worker.py:84`), so the horizon
  container is recreated on the next deploy/reconfigure even if no horizon config changed [CODE].

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `octavia`: both Ussuri items stay
  gone in 2024.1. `upgrade.yml` has no "Removing octavia user from admin project" task
  (`roles/octavia/tasks/upgrade.yml:1-46`), and amphora resources other than the image are created when
  `octavia_auto_configure` is on (above). Status: [CODE].
- New in 2024.1: the Redis requirement of the jobboard is checked only by `prechecks`; an `upgrade` or `deploy` run
  without `prechecks` renders a jobboard configuration whether or not Redis is deployed
  (`roles/octavia/tasks/precheck.yml:67-73`, `roles/octavia/templates/octavia.conf.j2:177-189`) [CODE]. The effect on
  the Octavia services is [NOT AVAILABLE].
- [fact sheet D §2.6][sheet-d-26]: adding or removing a health-manager host changes octavia.conf on all octavia hosts
  and restarts them (`controller_ip_port_list` loops over `octavia-health-manager`,
  `roles/octavia/templates/octavia.conf.j2:82`) [CODE]. NOT AVAILABLE: whether the controller list is written into an
  amphora at boot, so that existing amphorae keep the old list until failover. Likewise, a change of the `redis` group
  changes `jobboard_backend_hosts` (`roles/octavia/templates/octavia.conf.j2:180`) and so octavia.conf on all octavia
  hosts [CODE].
- [fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities), item
  5, read against 2024.1: `heartbeat_key = insecure` is still hard-coded (`roles/octavia/templates/octavia.conf.j2:81`);
  the amp network, secgroup and flavor are filled in by default (`octavia_auto_configure`) and stay unchecked only with
  it off; the admin-role removal on upgrade is gone; the HM precheck still tests the port on `api_interface_address`
  while the health manager binds `octavia_network_interface_address` (`roles/octavia/tasks/precheck.yml:29-38`,
  `roles/octavia/templates/octavia.conf.j2:80`), which differ only when `octavia_network_interface` is not
  `api_interface` (e.g. `tenant`); the CA private key (`server_ca.key.pem`) is still copied to worker, housekeeping and
  health-manager (`roles/octavia/tasks/config.yml:120-171`) [CODE]. New in 2024.1: the jobboard section writes
  `ssl:False` for both the Redis backend and the sentinel (`roles/octavia/templates/octavia.conf.j2:185`,
  `roles/octavia/templates/octavia.conf.j2:187`) [CODE].
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
  `os_*` modules run with `state: present`, `roles/octavia/tasks/prepare.yml:12`) is [NOT AVAILABLE]: the modules are
  not in these sources.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py octavia -->

| Item | Value |
|---|---|
| Play | site.yml:981 |
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
  Glance, and in 2024.1 Redis for the jobboard
- [Execution flow §2.2](../concepts/deployment-execution-flow.md#22-openstack-control-plane-deployment-order) — Octavia
  is near the end of the deployment order
- [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) — what the
  `bootstrap_octavia` container runs, including `upgrade_persistence`
- [Components](index.md) — the other component pages

[sheet-c-42]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#42-horizon_services-ansibleroleshorizondefaultsmainyml2-69
[sheet-d-25]: ../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#25-openstack-resources-kolla-creates-none
[sheet-d-26]: ../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#26-health-manager-network-requirements
