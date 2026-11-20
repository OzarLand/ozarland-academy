---
title: Fact sheet D
description: Fact sheet for Barbican, Octavia, Swift, Manila and every role that places containers on compute hosts in 2024.1, with the templates embedding host lists.
tags: [barbican, octavia, swift, manila, iscsi, scaling]
---

# Fact sheet D

Source: Kolla-Ansible tag `2024.1-eom` (commit `890396f`), kolla tag `2024.1-eom` (commit `ed7a36a`),
ansible-collection-kolla `2024.1-eom` (commit `82a0f5c`). All paths below are relative to the repo root.
Labels: **FACT** (the default, not written out) = read directly from the cited source: kolla-ansible, the kolla image
repository (cited as kolla `docker/...`), the collection (cited as ansible-collection-kolla `roles/...`) or Ansible
(cited as ansible-core 2.16.20 `lib/ansible/...`). **NOT AVAILABLE** = these sources do not establish it, often because
it depends on upstream OpenStack, Swift, Ceph, libvirt, iSCSI, Redis, Pacemaker or container-engine behaviour that is
not in them.
Out of scope here, because other fact sheets cover them: site.yml mechanics, nova/nova-cell/neutron/openvswitch/common,
`kolla_container` semantics, service-ks-register, service-rabbitmq, service-images-pull, service-stop. These are cited
only as cross-references.

Common facts used throughout:
- Every role below that still exists in 2024.1 has `tasks/main.yml` = `include_tasks: "{{ kolla_action }}.yml"` (for
  example `ansible/roles/barbican/tasks/main.yml:2`). **No role has a meta dependency on `common`**: no role in
  `ansible/roles/` has a `meta/` directory, and `common` is its own play tagged `common` (`ansible/site.yml:88-103`).
  The roles `chrony`, `skydive`, `nova-hyperv` and, **new in 2024.1, `monasca`** do not exist: `ansible/roles/monasca`
  and `ansible/monasca_cleanup.yml` are gone, and no file of `ansible/` mentions monasca (sections 5.10 to 5.13).
- The container module is now `kolla_container` (`ansible/library/kolla_container.py`; `kolla_docker` is gone, see
  [Repository architecture §6](../../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)). Bootstrap containers are started with `kolla_container action=start_container detach=False restart_policy=oneshot` (for example `ansible/roles/barbican/tasks/bootstrap_service.yml:6-17`); a `oneshot` container is started directly, without a systemd unit (`ansible/module_utils/kolla_docker_worker.py:379-389`). `remove_on_exit` defaults to `True` (`ansible/library/kolla_container.py:314`; `ansible/module_utils/kolla_docker_worker.py:391-410`), so a bootstrap container (DB sync) is created afresh and **re-runs on every deploy/reconfigure** for any role whose `deploy.yml` imports `bootstrap.yml`.
- `kolla-ansible upgrade` and `reconfigure` pass `-e kolla_serial=${ANSIBLE_SERIAL}`, which defaults to 0
  (`tools/kolla-ansible:296,522,531`). In every play, `run_once` tasks (keystone registration, DB bootstrap) run once
  per serial batch: each batch is a separate run of the play, and a `run_once` task is queued for the first host left
  only (ansible-core 2.16.20 `lib/ansible/executor/playbook_executor.py:181-190`,
  `lib/ansible/plugins/strategy/linear.py:181,207-209`).
- Every play below now also sets `max_fail_percentage` (default 100, for example `ansible/site.yml:861-864` for
  barbican); with 100 it never stops a play early (see
  [Repository architecture](../../concepts/repository-architecture.md)).
- The transport URLs are global host lists:
  `ansible/group_vars/all.yml:248`
  `rpc_transport_url: "{{ om_rpc_transport }}://{% for host in groups[om_rpc_group] %}...{% endfor %}/{{ om_rpc_vhost }}"` with `om_rpc_group: "rabbitmq"` (`:245`). Similarly `notify_transport_url` at `:258` with `om_notify_group: "rabbitmq"` (`:255`).
- **Changed in 2024.1, common to most roles below:** RabbitMQ quorum queues are on by default, so
  `rabbit_quorum_queue = true` is now rendered in the `[oslo_messaging_rabbit]` section of the barbican, octavia,
  manila, ceilometer, zun, cyborg and masakari templates (for example
  `ansible/roles/barbican/templates/barbican.conf.j2:98-107`): a cloud that kept the 2023.1 default gets a changed
  config, and a restart, on its first 2024.1 run ([F17](../findings.md#f17)). The systemd unit template also changed, so
  the first 2024.1 check of a container whose unit 2023.1 wrote reports a difference ([F16](../findings.md#f16)).

---

## 1. Barbican

### 1.1 Plays in site.yml

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| loadbalancer include | `ansible/site.yml:128-132` | `loadbalancer` (the "Apply role loadbalancer" play, `:105-114`) | `barbican` (`include_role tasks_from: loadbalancer`, `when: enable_barbican`). The whole block applies only when `enable_haproxy` and `kolla_action in ['deploy','reconfigure','upgrade','config']` (`:324-326`) |
| Apply role barbican | `ansible/site.yml:853-867` | `barbican-api`, `barbican-keystone-listener`, `barbican-worker`, `&enable_barbican_True` | `barbican`; `serial: kolla_serial` (`:860`) |

Default inventory: all three groups are children of `barbican`, which has `control` as its child
(`ansible/inventory/multinode:125-126,340-347`).

### 1.2 Services (`ansible/roles/barbican/defaults/main.yml:2-42`)

| Service | Container | Group | Enabled | Notable |
|---|---|---|---|---|
| barbican-api | `barbican_api` | barbican-api | `true` | haproxy `barbican_api` (internal) and `barbican_api_external`, both with `tls_backend: barbican_enable_tls_backend`; the external entry now has `external_fqdn` and `barbican_api_public_port` (`:11-26`). Named volume `barbican:/var/lib/barbican/` (`:136`) |
| barbican-keystone-listener | `barbican_keystone_listener` | barbican-keystone-listener | `true` | no haproxy |
| barbican-worker | `barbican_worker` | barbican-worker | `true` | no haproxy |

New in 2024.1: each service mounts `/dev/shm` when `om_enable_queue_manager` is set (`defaults/main.yml:138,145,152`;
off by default).
Keystone registration: service type `key-manager` (`:186-192`), user `barbican` with admin on `service` (`:194-198`),
and roles `key-manager:service-admin`, `creator`, `observer`, `audit` (`:166-169,200-204`, `tasks/register.yml:2-8`).

### 1.3 Task flow per kolla_action

- **deploy** (`tasks/deploy.yml:1-14`): register.yml (keystone) → config.yml → check-containers.yml (compare_container,
  notify restart) → clone.yml (dev mode only) → bootstrap.yml → flush handlers.
- **reconfigure** = deploy (`tasks/reconfigure.yml:2`). So keystone registration and the DB bootstrap container **re-run
  on every reconfigure**. Still holds in 2024.1.
- **upgrade** (`tasks/upgrade.yml:1-9`): config → check-containers → bootstrap_service (DB sync only, no DB/user
  creation) → flush. No keystone re-registration.
- **stop / pull / precheck / deploy-containers / loadbalancer / config_validate** use the standard helpers
  (`kolla-ansible validate-config` sets `kolla_action=config_validate`, `tools/kolla-ansible:561-564`). There is still
  no `check.yml` in `ansible/roles/barbican/tasks/`.

### 1.4 Config files, overrides, handlers (`tasks/config.yml`)

| Output on host | Source and override chain | Notifies |
|---|---|---|
| `/etc/kolla/<svc>/config.json` | `templates/<svc>.json.j2` (`:54-65`) | Restart `<svc>` |
| `/etc/kolla/barbican-api/vassals/barbican-api.ini` (uwsgi) | merge: role template → `{{node_custom_config}}/barbican-api/barbican-api.ini` → `.../barbican-api/<host>/barbican-api.ini` (`:67-82`) | Restart barbican-api |
| `/etc/kolla/barbican-api/barbican-api-paste.ini` | only if `{{node_custom_config}}/barbican/barbican-api-paste.ini` exists (`:84-109`) | Restart barbican-api |
| `/etc/kolla/<svc>/barbican.conf` | merge: template → `global.conf` → `barbican.conf` → `barbican/<svc>.conf` → `barbican/<host>/barbican.conf` (`:111-129`) | Restart `<svc>` |
| policy file | first found in `{{node_custom_config}}/barbican/` (`:31-48,131-143`) | Restart `<svc>` |

Handlers (`handlers/main.yml:2-48`): `recreate_or_restart_container` for each of the 3 services, skipped when
`kolla_action == "config"`.

### 1.5 Dependencies (from templates)

- MariaDB: **changed in 2024.1**, the connection moved from `[DEFAULT] sql_connection` to `[database] connection`, with
  `connection_recycle_time`, `max_pool_size` and `max_retries = -1` (`templates/barbican.conf.j2:18-22`). The DB is
  created via `kolla_toolbox mysql_db/mysql_user`, delegated to `groups['barbican-api'][0]`
  (`tasks/bootstrap.yml:2-34`). The login user is `barbican_database_shard_root_user` (`defaults/main.yml:61`), which is
  `root_shard_<id>` when `enable_proxysql` is set.
- RabbitMQ: `transport_url = {{ rpc_transport_url }}` (`barbican.conf.j2:16`) and the notifications transport
  (`:77-84`). **New in 2024.1:** the notifications driver is `messagingv2` with topic `notifications` when
  `enable_ceilometer`, otherwise `noop` (`barbican.conf.j2:79-84`; `defaults/main.yml:209-213`). Barbican does **not**
  use the `service-rabbitmq` role.
- Memcached: `memcached_servers` loops over `groups['memcached']` (`barbican.conf.j2:75`).
- Keystone: authtoken (`:60-75`). **Keystone notifications are coupled**: `[keystone_notifications] enable = True`, and
  `topic = barbican_notifications` when `enable_keystone` (`barbican.conf.j2:54-58`). The keystone role adds the
  `barbican_notifications` topic when `enable_barbican` is set (`ansible/roles/keystone/defaults/main.yml:188-194`).
- Consumers: cinder (`ansible/roles/cinder/templates/cinder.conf.j2:264-269`), glance (`glance-api.conf.j2:163-168`),
  nova and nova-cell (`ansible/roles/nova-cell/templates/nova.conf.j2:259-264`, so **compute** `nova.conf` changes when
  barbican is enabled), octavia (`octavia.conf.j2:21-25`), magnum, tacker and skyline (templates that test
  `enable_barbican`). **Changed in 2024.1:** horizon and murano no longer test it (no `barbican` in
  `ansible/roles/horizon/`; no murano role).

### 1.6 Operationally notable

- **The crypto KEK lives in passwords.yml.** `barbican_crypto_plugin: "simple_crypto"`
  (`ansible/group_vars/all.yml:1022`), and `kek = '{{ barbican_crypto_key }}'` (`barbican.conf.j2:47-51`;
  `etc/kolla/passwords.yml:56`). `kolla-genpwd` generates it as a Fernet key (`kolla_ansible/cmd/genpwd.py:100-101,158`)
  and only fills empty values (`:91`). **NOT AVAILABLE:** whether losing or changing `barbican_crypto_key` makes stored
  secrets undecryptable (simple_crypto semantics are Barbican code, which is not in the sources). This key must be in
  the passwords.yml backup.
- p11_crypto: the library path `/usr/lib/libCryptoki2_64.so` (`all.yml:1023`) is used only in the conf template
  (`barbican.conf.j2:37`) and is not mounted into the containers (`defaults/main.yml:132-153`). No task generates the
  MKEK or HMAC keys: a grep for `mkek|gen_hmac|barbican-manage` in `ansible/` finds only the conf template
  (`barbican.conf.j2:41,43`). **NOT AVAILABLE:** what else an HSM setup needs (for example a custom image or extra
  volumes, plus manual key generation).
- Running `kolla-ansible deploy -t barbican` alone does not run the keystone play, so the `barbican_notifications` topic
  is not enabled in keystone.conf. **NOT AVAILABLE:** whether barbican-keystone-listener then receives project-deletion
  events.
- Copying the policy file uses `become: true` (`tasks/config.yml:136`). That is fine.

---

## 2. Octavia

### 2.1 Plays

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| loadbalancer include | `ansible/site.yml:266-270` | loadbalancer | `octavia` |
| Apply role octavia | `ansible/site.yml:981-996` | `octavia-api`, `octavia-health-manager`, `octavia-housekeeping`, `octavia-worker`, `&enable_octavia_True` | `octavia`; serial kolla_serial (`:989`) |

Default inventory: all five groups (`octavia-api`, `octavia-driver-agent`, `octavia-health-manager`,
`octavia-housekeeping`, `octavia-worker`) are children of `octavia`, which is `control`
(`ansible/inventory/multinode:165-166,467-480`). The play still does not list `octavia-driver-agent`; with the default
inventory its hosts are the same control hosts.

### 2.2 Services (`ansible/roles/octavia/defaults/main.yml:2-57`)

`octavia_api` (haproxy `octavia_api`/`octavia_api_external` on port 9876, with `listen_port` and
`tls_backend: octavia_enable_tls_backend`; the external entry now has `external_fqdn` and `octavia_api_public_port`,
`:11-26`), `octavia_driver_agent` (`enabled: enable_octavia_driver_agent`, `:27-33`; default: only with
`neutron_plugin_agent: ovn`, `ansible/group_vars/all.yml:831`), `octavia_health_manager`, `octavia_housekeeping`,
`octavia_worker`. The other four have `enabled: true`, and none has privileged or special flags.
Keystone: service type `load-balancer` (`:252-258`). User `octavia` is given admin on `service` **and** on
`{{ octavia_service_auth_project }}`, default `service` (`:241,260-271`). Five `load-balancer_*` roles are created
(`:59-64`, `tasks/register.yml:9-21`).

### 2.3 Task flow

- **deploy** (`tasks/deploy.yml:1-19`): register → **prepare.yml** when `octavia_auto_configure` (see 2.5) →
  **config-host.yml** (the health-manager interface when `octavia_network_type: tenant`, `tasks/config-host.yml:2-6`) →
  config → check-containers → clone (dev mode only) → bootstrap → flush. **Changed in 2024.1:** bootstrap now creates
  two databases and two users, `octavia` and the new **`octavia_persistence`**, before the `bootstrap_octavia` container
  (`tasks/bootstrap.yml:2-74`; `defaults/main.yml:80`).
- **reconfigure** = deploy (`tasks/reconfigure.yml:2`), so the DB sync, keystone registration and, with
  `octavia_auto_configure`, the resource creation re-run.
- **upgrade** (`tasks/upgrade.yml:1-46`): config → check-containers → **new in 2024.1:** create the
  `octavia_persistence` database and its user (`:6-41`, gated only by `not use_preconfigured_databases`, not by the
  jobboard flag) → bootstrap_service → flush. Upgrade still does **not** run register.yml, prepare.yml or
  config-host.yml, and there is still no task that removes a role from the octavia user.
  - With `octavia_auto_configure` on, `upgrade` (like every action that runs config.yml, `genconfig` included) still
    runs `get_resources_info.yml` first (`tasks/config.yml:2-3`), which looks up the flavor, project, security groups
    and network by name; the repo doc says genconfig and check mode need access to the Nova and Neutron APIs for this
    (`doc/source/reference/networking/octavia.rst:136-138`). `ansible/group_vars/all.yml:1321-1322` still says to set
    `octavia_auto_configure: no` and keep the previous Octavia configuration when upgrading from Ussuri. **NOT
    AVAILABLE:** what that lookup does when the resources were created manually under other names (the `os_*_info`
    modules are not in these sources).
- `check.yml` is empty (`tasks/check.yml:1`).
- **New in 2024.1:** `kolla-ansible octavia-certificates --check-expiry <days>` only checks the certificates and
  generates nothing (`tools/kolla-ansible:550-556`; `ansible/roles/octavia-certificates/tasks/main.yml:10-12,51`).

### 2.4 Config files and handlers (`tasks/config.yml`)

| Output | Source and overrides | Notifies |
|---|---|---|
| (lookup) | `get_resources_info.yml` when `octavia_auto_configure` (`:2-3`) | – |
| policy file | first-found in `{{node_custom_config}}/octavia/` (`:18-49`) | Restart `<svc>` |
| config.json | `templates/<svc>.json.j2` (`:55-66`) | Restart `<svc>` |
| `octavia-wsgi.conf` (octavia-api) | first-found: `octavia/<host>/octavia-wsgi.conf` → `octavia/octavia-wsgi.conf` → role template (`:68-84`) | Restart octavia-api |
| `octavia.conf` (all services) | merge: template → `global.conf` → `octavia.conf` → `octavia/<svc>.conf` → `octavia/<host>/octavia.conf` (`:86-104`) | Restart `<svc>` |
| SSH private key for the amphora keypair | role template `octavia-ssh-key.j2` into octavia-worker, only when `octavia_auto_configure` (`:108-118`) | Restart octavia-worker |
| 4 PEM files: `client.cert-and-key.pem`, `client_ca.cert.pem`, `server_ca.cert.pem`, `server_ca.key.pem` | plain `copy` from `{{node_custom_config}}/octavia/` into worker (`:120-133`), housekeeping (`:135-148`) and health-manager (`:150-163`); the block runs only when `'amphora' in octavia_provider_drivers` (`:165-171`) | Restart that service |

Handlers (`ansible/roles/octavia/handlers/main.yml:2-79`) use `recreate_or_restart_container` for each of the five
services. Volumes are passed with `reject('equalto','')` (for example `:12`); the module would skip empty volume strings
anyway (`ansible/module_utils/kolla_container_worker.py:412-414`).

### 2.5 OpenStack resources: Kolla creates none

**Still not true by default in 2024.1.** With `octavia_auto_configure` (default: true when `amphora` is in
`octavia_provider_drivers`, which it is by default, `ansible/group_vars/all.yml:1323`,
`ansible/roles/octavia/defaults/main.yml:386`), `deploy` and `reconfigure` run `prepare.yml`, which creates, `run_once`
and delegated to `groups['octavia-api'][0]`: the amphora flavor (`amphora`, 1 vCPU, 1024 MB, 5 GB, not public,
`defaults/main.yml:319-324`), the nova keypair, the security groups and their rules, the lb-mgmt network and subnet
(`octavia_amp_network_cidr: 10.1.0.0/24`, `:379`) and, for IPv6, a router (`tasks/prepare.yml:2-161`).
`kolla-ansible octavia-certificates` generates the certificates (`tools/kolla-ansible:550-556`,
`ansible/octavia-certificates.yml`). Kolla still does **not** create the amphora image. The repo's own doc describes
automatic registration as the default ("Option 1: Automatic resource registration (default, recommended)",
`doc/source/reference/networking/octavia.rst:123-138`).
The template consumes the IDs:
- With `octavia_auto_configure`, `amp_image_owner_id`, `amp_boot_network_list`, `amp_secgroup_list` and `amp_flavor_id`
  come from the facts that `get_resources_info.yml` registered (`templates/octavia.conf.j2:104-108`). **Changed in
  2024.1:** the fallbacks to the older `openstack_projects`/`secgroup` result keys are gone (`octavia.conf.j2:105,107`;
  `tasks/get_resources_info.yml:72-75`). With it off, each is written only if the operator defines
  `octavia_amp_image_owner_id`, `octavia_amp_boot_network_list`, `octavia_amp_secgroup_list` or `octavia_amp_flavor_id`
  (`octavia.conf.j2:91-103`); no group default defines them, and **no precheck validates them**:
  `tasks/precheck.yml:1-73` checks only the API and HM ports, the 4 PEM files (when the amphora provider is enabled),
  the neutron plugin for `tenant`, and Redis for the jobboard (below).
- `amp_image_tag = {{ octavia_amp_image_tag }}` (default `amphora`) and
  `amp_ssh_key_name = {{ octavia_amp_ssh_key_name }}` (default `octavia_ssh_key`) are variables
  (`octavia.conf.j2:88-89`, `defaults/main.yml:293-295`), but `heartbeat_key = insecure` (`octavia.conf.j2:81`) is still
  a **security oddity** with no variable to change it except an override file.
- `[certificates] ca_private_key_passphrase = {{ octavia_ca_password }}` (`:17-20`) must match the `server_ca.key.pem`
  in use.
- Barbican: if `enable_barbican`, the region and endpoint for the cert manager are set (`:21-25`). **NOT AVAILABLE:**
  whether TLS-terminated listeners need barbican.
- **New in 2024.1, the jobboard:** `enable_octavia_jobboard` defaults to true whenever octavia is enabled with the
  amphora provider (`ansible/group_vars/all.yml:832`). It renders a `[task_flow]` section with `jobboard_backend_hosts`
  looping over **`groups['redis']`**, the Redis password and sentinel port, and `persistence_connection` to the
  `octavia_persistence` database (`octavia.conf.j2:177-189`). A new precheck fails unless `enable_redis` is set
  (`tasks/precheck.yml:67-73`), and `enable_redis` defaults to `"no"` (`all.yml:840`): **with the defaults, enabling
  octavia with the amphora provider fails `prechecks` until `enable_redis: yes` (or `enable_octavia_jobboard: no`) is
  set.** `prechecks` is the only place that checks it: `deploy` does not run the precheck. **NOT AVAILABLE:** what
  Octavia does when the jobboard Redis is unreachable.
- Upgrades from Ussuri: the code comment says to set `octavia_auto_configure: no` and keep the existing configuration
  (`ansible/group_vars/all.yml:1321-1322`). The doc still notes that Train and earlier registered resources in `admin`
  (`octavia.rst:257-264`); `octavia_service_auth_project` defaults to `service` (`defaults/main.yml:241`).

### 2.6 Health-manager network requirements

- `bind_ip = {{ octavia_network_interface_address }}`, `bind_port = {{ octavia_health_manager_port }}` (5555,
  `all.yml:536`) (`octavia.conf.j2:78-80`).
- `controller_ip_port_list` loops over **all** `groups['octavia-health-manager']` using
  `'octavia_network' | kolla_address(host)` (`octavia.conf.j2:82`). This needs facts for every HM host.
- `octavia_network_interface` defaults to `api_interface`, or to `o-hm0` when `octavia_network_type: tenant`
  (`all.yml:292`; `octavia_network_type: "provider"` by default, `:1331`), and the address comes from
  `'octavia_network' | kolla_address` (`all.yml:317`). `kolla_address` raises `FilterError` if the interface or address
  family is missing on the host (`kolla_ansible/kolla_address.py:84-100,132-136`). The `[health_manager]` section is
  rendered into octavia.conf for **all services**, so **every octavia host (api, worker and housekeeping too) must have
  `octavia_network_interface` with an address**, or templating fails.
- With the default `provider` type, Kolla does not create the lb-mgmt interface, bridge or VLAN on the controllers; the
  doc says to bridge it to OVS manually (`doc/source/reference/networking/octavia.rst:91-109`). With
  `octavia_network_type: tenant` (and `octavia_auto_configure`), on each health-manager host Kolla creates a Neutron
  port, adds it to `br-int` through the `openvswitch_vswitchd` container, and installs and starts an `octavia-interface`
  systemd unit (`tasks/config-host.yml:2-6`, `tasks/hm-interface.yml:2-100`); a precheck rejects `tenant` unless
  `neutron_plugin_agent` is `openvswitch` (`tasks/precheck.yml:56-65`).
- Precheck oddity: the HM free-port check uses `api_interface_address`, not `octavia_network_interface_address`
  (`tasks/precheck.yml:29-38`). The two differ only when `octavia_network_interface` is not `api_interface` (for example
  with `tenant`). Still present.
- Adding or removing a health-manager host changes octavia.conf on all octavia hosts and restarts them
  (`octavia.conf.j2:82`; `tasks/config.yml:86-104`). **New in 2024.1:** the same holds for a host added to or removed
  from `redis`, through `jobboard_backend_hosts` (`octavia.conf.j2:180`). **NOT AVAILABLE:** whether the controller list
  is written into an amphora at boot, so that existing amphorae keep the old list until failover.
- Security spread: `server_ca.key.pem` (the CA private key) is copied to the worker, housekeeping **and** health-manager
  config dirs (`tasks/config.yml:120-171`).

### 2.7 Other dependencies

MariaDB (`octavia.conf.j2:41-45`, plus the persistence DB at `:188`), RabbitMQ rpc (`:10`) and notify (`:123-130`;
**new:** driver `messagingv2` with topic `notifications` when `enable_ceilometer`, else `noop`,
`defaults/main.yml:276-280`), memcached ×2 loops (`:59,76`), keystone (`:47-76`), glance, neutron and nova via internal
endpoints (`:163-176`) and, **new in 2024.1, Redis** with the jobboard (`:177-189`). With `neutron_plugin_agent: ovn`,
the OVN NB and SB connections (`:30-34`). Topology is `octavia_loadbalancer_topology: "SINGLE"`
(`roles/octavia/defaults/main.yml:298`).

---

## 3. Swift

### 3.1 Plays

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| loadbalancer include | `ansible/site.yml:294-298` | loadbalancer | `swift` |
| Apply role swift | `ansible/site.yml:511-526` | `swift-account-server`, `swift-container-server`, `swift-object-server`, `swift-proxy-server`, `&enable_swift_True` | `swift`; serial kolla_serial (`:519`) |

Default inventory: proxy is in `swift` (control); account, container and object servers are in `storage`
(`ansible/inventory/multinode:122-123,327-337`).

### 3.2 Services: "old-style" role

`swift_services` contains **only** `swift-proxy-server`, and only for haproxy
(`ansible/roles/swift/defaults/main.yml:2-17`; the external entry now has `external_fqdn`). It has no container_name,
image, volumes or check-containers. Containers are started imperatively in `tasks/start.yml` with
`kolla_container action: start_container`:

| Container | Group | Notes (`tasks/start.yml`) |
|---|---|---|
| `swift_rsyncd` | any of account, container or object | `:36-49`. Rsync daemon on port `swift_rsync_port` 10873 (`all.yml:628`, `templates/swift-rsyncd.json.j2:2`). It is the only swift image that fixes disk ownership at start: it chowns `/srv/node` and its top-level mount points to `swift:swift` (kolla `docker/swift/swift-rsyncd/extend_start.sh:3`). The other swift images have no `extend_start` (kolla `docker/swift/*/` hold only `Dockerfile.j2`, plus `swift_sudoers` in `swift-base`) |
| `swift_account_server/auditor/replicator/reaper` (+ `_replication_server` if a separate replication net exists) | swift-account-server | `:51-128` |
| `swift_container_server/auditor/replicator/updater` (+ replication server) | swift-container-server | `:130-208` |
| `swift_object_server/auditor/replicator/updater/expirer` (+ replication server) | swift-object-server | `:210-303` |
| `swift_proxy_server` | swift-proxy-server | `:305-317`, only when `run_start_swift_proxy_server` |

Disks: `find_disks` runs via
`{{ kolla_container_engine }} exec -t kolla_toolbox ... -m find_disks name=KOLLA_SWIFT_DATA match_mode=strict`
(`start.yml:2-14`; `defaults/main.yml:58-60`). Each disk is then mounted `xfs` by UUID at `/srv/node/<fs_label>` with
`noatime,nodiratime,logbufs=8` (`start.yml:23-34`). The `find_disks` module is not in this repo (`ansible/library/` does
not have it); it ships in the kolla_toolbox image.
Volumes: `/srv/node` with `:shared`, `/etc/kolla/swift` mounted at `/var/lib/kolla/swift` (ring files), and the named
volume `swift_recon_cache` (also on the account and container servers, `start.yml:63,142`). **No `kolla_logs` volume**:
all swift logs go over UDP syslog to `syslog_server = api_interface_address` (`defaults/main.yml:70`,
`templates/object.conf.j2:8-11`).

### 3.3 Ring files

- Kolla **does not build rings**. Precheck fails unless `account|container|object.builder` and `.ring.gz` exist under
  `{{node_custom_config}}/swift/` (`tasks/precheck.yml:108-131`).
- `config.yml:183-197` copies them (plus `swift_extra_ring_files`) to `/etc/kolla/swift/` on **every host in the swift
  play**, with `backup: yes`. Timestamped backups accumulate on each host.
- Containers read the rings via `config.json`, for example `templates/swift-object-server.json.j2:4-15` (source
  `/var/lib/kolla/swift/*.ring.gz`). Under COPY_ALWAYS they are copied into `/etc/swift` at container start.

### 3.4 Task flow

- **deploy** (`tasks/deploy.yml:1-10`): register (keystone service, user, and the `ResellerAdmin` role at
  `tasks/register.yml:9-20`) → config → start.yml → check.yml (empty).
  - **No task in the swift role has `notify:`** (a grep for `notify` in `ansible/roles/swift/tasks/` finds nothing). The
    only handler is a no-op `debug` (`handlers/main.yml:2-4`), triggered only by service-cert-copy.
  - `start_container` recreates a container only when container properties differ (image, volumes, ...;
    `module_utils/kolla_docker_worker.py:365-374`). **So `deploy` does not apply swift config or ring changes to running
    containers** (verified in code): `start_container` compares only container properties and never runs
    `kolla_set_configs --check`, which only `compare_container` calls
    (`module_utils/kolla_container_worker.py:20,58-65`, `module_utils/kolla_docker_worker.py:146-181`);
    `kolla_set_configs` copies config and rings into the container only at container start (kolla
    `docker/base/start.sh:11`, `docker/base/set_configs.py:535-553`; both files are byte-identical to 2023.1); every
    swift command reads those copies, not the bind-mounted sources (`/etc/swift/*.conf` or `/etc/rsyncd.conf` in
    `templates/swift-*.json.j2`; no template sets `swift_dir`); and no task notifies a handler. Still holds in 2024.1.
    See [Kolla images §2](../../concepts/kolla-images.md#2-start-path-common-to-every-image).
- **reconfigure** (`tasks/reconfigure.yml:1-105`) is a different, legacy flow:
  1. It builds the list of all swift containers, plus replication servers if `swift_has_replication_network` (`:2-30`).
  2. It **fails if any listed container is not running** (`:32-42`), so reconfigure cannot repair a crashed container.
  3. It runs config.yml, then `{{ kolla_container_engine }} exec -u root <c> kolla_set_configs --check` (`:44-54`).
  4. It removes and re-creates containers under COPY_ONCE (`:70-89`), or does a plain `restart_container` under
     COPY_ALWAYS when the check returns rc==1 (`:91-105`). `restart_container` restarts the container through its
     systemd unit (`module_utils/kolla_docker_worker.py:439-459`). **Changed in 2024.1:** these `kolla_container` calls
     now pass `common_options` (`reconfigure.yml:35,62,73,94`), so they follow `kolla_container_engine` like the other
     roles.
  - Under COPY_ALWAYS (the default, `all.yml:43`), all changed containers on all hosts of the batch restart in the same
    task (`:91-105`; the linear strategy queues a task for every host of the batch, ansible-core 2.16.20
    `lib/ansible/plugins/strategy/linear.py:50-93`). With default `kolla_serial=0` (`tools/kolla-ansible:296`) the batch
    is every host of the play (`lib/ansible/executor/playbook_executor.py:300-302`), so **every changed proxy, on every
    proxy host, restarts in that one task**. **NOT AVAILABLE:** whether this opens an outage window.
- **upgrade** (`tasks/upgrade.yml:1-6`) uses `rolling_upgrade.yml` by default (`swift_enable_rolling_upgrade: "yes"`,
  `defaults/main.yml:73`). Despite the name, it stops **all storage containers on all storage hosts at once**
  (`rolling_upgrade.yml:31-39`, with a TODO admitting it at `:28-30`), restarts them, then stops and starts the proxies
  (`:46-68`). The proxy start here omits `/etc/timezone` and `kolla_logs` (`:64-67`), which is consistent with
  start.yml.
- **stop** (`tasks/stop.yml`) still contains a **bug**: the account-auditor stop checks
  `'swift_object_auditor' not in skip_stop_containers` (`:23-31`).

### 3.5 Config files (`tasks/config.yml`)

`tasks/config.yml`, `tasks/precheck.yml` and every swift template are unchanged from 2023.1 (same text, same lines).
- Config dirs and config.json for **all 18 services are created on every host in the play**, with no group filter
  (`:2-29,35-59`). swift.conf is copied for all 17 services on every host (`:61-91`). `swift.conf` contains
  `swift_hash_path_suffix/prefix` from passwords.yml (`templates/swift.conf.j2:1-3`, `etc/kolla/passwords.yml:103-104`).
  **NOT AVAILABLE:** what changing them after data is written does (Swift semantics are not in the sources).
- account, container and object `*.conf` are written for their groups (`:93-155`). Override chain: template →
  `global.conf` → `swift/<type>.conf` → `swift/<svc>.conf` → `swift/<host>/<svc>.conf`.
- The proxy chain is template → global.conf → `swift/proxy-server.conf` → `swift/<host>/proxy-server.conf` (`:157-171`).
- `rsyncd.conf` is a plain template (not mergeable) bound to `'swift_replication' | kolla_address`
  (`templates/rsyncd.conf.j2:1`).
- policy.json is copied **without `become`** (`config.yml:206-230`).

### 3.6 Networks and ports

- Storage services bind to `swift_storage`; `replicat*` services bind to `swift_replication`
  (`templates/object.conf.j2:1-3`, `account.conf.j2:1-3`). `swift_storage_interface` defaults to `network_interface` and
  `swift_replication_interface` to `swift_storage_interface` (`all.yml:288-289`).
- `swift_has_replication_network` is true when the interfaces differ (`defaults/main.yml:66`). Replicators use
  `RSYNC_CONNECT_PROG: "nc %H {{ swift_rsync_port }}"` (`start.yml:87,105,166` etc.).
- Precheck **bug**: the rsync free-port check probes port **873** (`precheck.yml:86-95`), but rsyncd listens on 10873.
  Still present.

### 3.7 Dependencies

- Keystone authtoken (`proxy-server.conf.j2:36-51`).
- Memcached: two loops over `groups['memcached']` (`:25,51`).
- RabbitMQ only when `enable_ceilometer`: the ceilometer middleware uses `url = {{ notify_transport_url }}` (`:58-66`).
- No MariaDB.
- Cinder backup can point at swift (`ansible/roles/cinder/templates/cinder.conf.j2:43-50`). Ceilometer's register.yml
  grants `ResellerAdmin` when swift is enabled (`ansible/roles/ceilometer/tasks/register.yml:8-22`).

### 3.8 Oddities

- **`enable_swift_recon` is tested without `| bool`**: `{% if enable_swift_recon %}` (`account.conf.j2:15,17`,
  `container.conf.j2:15,17`, `object.conf.j2:19,22`). The default is the string `"no"` (`all.yml:844`), not a boolean.
  **NOT AVAILABLE:** whether the template treats that string as true and so always enables the recon middleware (the
  Jinja test of a string is not in the sources).
- The `proxy-logging` and `versioned_writes` filters are defined but not in the proxy pipeline
  (`proxy-server.conf.j2:13,33-34,92-94`).

---

## 4. Manila

### 4.1 Plays

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| loadbalancer include | `ansible/site.yml:218-222` | loadbalancer | `manila` |
| **Apply role neutron** | `ansible/site.yml:671-693` | includes **`manila-share`** (`:684`) and `compute` (`:683`) | `neutron` |
| Apply role manila | `ansible/site.yml:786-801` | `manila-api`, `manila-data`, `manila-share`, `manila-scheduler`, `&enable_manila_True` | `manila` |

Default inventory: `manila-share` is a child of **`network`** (`ansible/inventory/multinode:320-321`). The other groups
are under `manila` (control) (`:140-141,314-324`). `openvswitch` children include `manila-share` (`:105-108`).

**Why manila-share is in the neutron play:** the agent host_in_groups include manila-share hosts.
- OVS agent, only with the generic backend:
  `(enable_manila_backend_generic | bool and inventory_hostname in groups['manila-share'])`
  (`ansible/roles/neutron/defaults/main.yml:36`). openvswitch db and vswitchd have the same condition
  (`ansible/roles/openvswitch/defaults/main.yml:11,27`).
- Linuxbridge agent: whenever `enable_manila` is set, **for any backend** (`neutron/defaults/main.yml:60`). This
  inconsistency is still present.
- Generic-driver share servers are plugged with `OVSInterfaceDriver` (openvswitch) or `BridgeInterfaceDriver`
  (linuxbridge) (`templates/manila-share.conf.j2:75-79`).
- Ordering: the neutron play (`:671`) runs before manila (`:786`).

### 4.2 Services (`ansible/roles/manila/defaults/main.yml:2-50`)

| Service | Container | Notable |
|---|---|---|
| manila-api | `manila_api` | haproxy port 8786 (`all.yml:463`); **new:** `listen_port` on both entries and `external_fqdn`/`manila_api_public_port` on the external one |
| manila-scheduler | `manila_scheduler` | — |
| manila-share | `manila_share` | **privileged**, `/run:/run` (`:shared` only with Docker), `/lib/modules:ro`, plus the engine's `run_default_volumes_<engine>` (empty for Docker) (`:38-39`, `:158-166`; `ansible/group_vars/all.yml:165-172`). Its handler adds `ipc_mode: host` (`handlers/main.yml:51-67`, `ipc_mode` at `:62`), which is not in the services dict and not compared by check-containers (`tasks/check-containers.yml:2-18`) |
| manila-data | `manila_data` | **privileged**, `/dev/:/dev/`, `/run` as above (`:47-48`, `:181-188`) |

Backends: generic, hnas and glusterfsnfs in `manila_backends` (`:221-238`) and, **changed in 2024.1**, the two CephFS
backends moved to a new list `manila_ceph_backends`, each with a `share_name` and a `cluster` (default `ceph`)
(`:240-256`); `manila_enabled_backends` joins both lists (`:257`). Each is gated by `enable_manila_backend_*`
(`all.yml:799-803`, all `"no"`).

### 4.3 Task flow

- **deploy** (`tasks/deploy.yml:1-14`): clone (dev) → register (keystone `share` and `sharev2`,
  `defaults/main.yml:282-295`) → config → check-containers → bootstrap (DB, then `bootstrap_manila`,
  `tasks/bootstrap.yml:2-38`) → flush.
- **reconfigure** = deploy (`tasks/reconfigure.yml:2`). **upgrade**: config → check-containers → bootstrap_service →
  flush (`tasks/upgrade.yml:1-9`).
- There is still no `fix_cephfs_owner.yml` (no such file under `ansible/roles/manila/tasks/`, and no task of the role
  mounts CephFS or passes `secret=`). With a CephFS backend, config includes `external_ceph.yml` on manila-share hosts
  (`tasks/config.yml:15-18`), see 4.4.

### 4.4 Config (`tasks/config.yml`)

| Output | Chain | Notifies |
|---|---|---|
| **Changed in 2024.1:** a `manila-share/ceph/` sub-directory (`external_ceph.yml:2-14`), then per enabled entry of `manila_ceph_backends`: `ceph/<cluster>.conf` **merged** from `{{node_custom_config}}/manila/<cluster>.conf` and `.../manila/manila-share/<cluster>.conf` (`:16-29`), and the keyring `ceph/<cluster>.client.<user>.keyring` templated from `{{node_custom_config}}/manila/<cluster>.client.<user>.keyring` (`:31-42`; `ceph_manila_keyring: "client.{{ ceph_manila_user }}.keyring"`, `all.yml:1186`); only with `enable_manila_backend_cephfs_native` or `_cephfs_nfs` on manila-share hosts (`config.yml:15-18`) | For the default cluster `ceph` the operator file names are still `ceph.conf` and `ceph.client.manila.keyring`, but `config.json` now copies the whole `ceph/` directory to `/etc/ceph` (`templates/manila-share.json.j2:9-15`) and the backend sections read `/etc/ceph/<cluster>.conf` (`manila-share.conf.j2:108-143`) | Restart manila-share |
| config.json | `:43-54` | Restart `<svc>` |
| manila.conf (api, data, scheduler) | template → global.conf → manila.conf → `manila/<svc>.conf` → `manila/<host>/manila.conf` (`:56-75`) | Restart `<svc>` |
| manila-share manila.conf | `manila.conf.j2` **+** `manila-share.conf.j2` → global.conf → manila.conf → `{{node_custom_config}}/manila-share.conf` → manila/manila-share.conf → `manila/<host>/manila.conf` (`:77-99`) | Restart manila-share |
| policy | `:101-112`, **no `become`** | Restart `<svc>` |

Because the destination files and `config.json` change, a CephFS-backed manila-share is expected to see a config
difference, and a restart, on its first 2024.1 run (`kolla_set_configs --check` compares the config files it would copy,
[Kolla images §3](../../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).

### 4.5 Dependencies

- MariaDB (`manila.conf.j2:27-28`), RabbitMQ rpc (`:22`) and notify (`:50-51`), memcached (`:48`).
- manila-share.conf additionally loops over memcached 3× (`manila-share.conf.j2:35,52,70`) and holds **glance, cinder,
  nova and neutron service-user passwords** (`manila-share.conf.j2:8-70`).
- Ceph is external only: there is no ceph deployment role in 2024.1 (`ansible/roles/` has no `ceph` role; only
  `ceph-rgw`, which has "no container deployment" and only configures the load balancer,
  `ansible/roles/ceph-rgw/defaults/main.yml:3-4`). The config is supplied by the operator (`external_ceph.yml`).

### 4.6 Operationally notable

- Kolla does not create share types, the service image or networks (no such task under `ansible/roles/manila/tasks/`).
  `default_share_type = default_share_type` is hard-coded (`manila-share.conf.j2:6`) and
  `service_image_name = manila-service-image` (`:85`).
- The generic backend's service-instance credentials default to `manila`/`manila` (`defaults/main.yml:211-212`,
  `manila-share.conf.j2:83-84`).
- **Changed in 2024.1:** endpoints no longer use `kolla_internal_fqdn` and `kolla_external_fqdn` directly but
  `manila_internal_fqdn`/`manila_external_fqdn` through the `kolla_url` filter (`defaults/main.yml:199-200`); those two
  default to the global FQDNs (`all.yml:461-462`).

---

## 5. Other roles that deploy containers onto `compute` hosts

Default multinode membership (compute ∈): collectd (`multinode:56-57`), telegraf (`:71-76`), hacluster-remote
(`:81-82`), cyborg and cyborg-agent (`:149-151,425-426`), iscsid (`:305-308`), ceilometer-compute and ceilometer-ipmi
(`:402-406`), multipathd (`:452-454`), zun-compute and zun-cni-daemon (`:515-519`), prometheus-node-exporter,
prometheus-cadvisor and prometheus-libvirt-exporter (`:543-548,556-561,575-576`), masakari-instancemonitor (`:590-591`),
ovn-controller-compute (`:597-598`). The kuryr play targets `compute` directly (`site.yml:695-707`). There is **no
`chrony`, `skydive-agent`, `hyperv` or (new in 2024.1) `monasca-agent` group** in the 2024.1 `inventory/multinode`.

Podman note (new in 2024.1): the compute-side containers that mount `/run` (ceilometer_compute, iscsid, tgtd,
multipathd, zun_compute, zun_cni_daemon, kuryr) now mount it `:shared` only when `kolla_container_engine == 'docker'`
and add `run_default_volumes_<engine>`, which is empty for Docker (for example
`ansible/roles/iscsi/defaults/main.yml:10,46`; `ansible/group_vars/all.yml:165-172`). With the default Docker engine the
volume list is unchanged.

### 5.0 Summary table (compute-side)

| Role (enable flag, default) | Compute containers | Restart trigger (handler) | Config: per-host or global? | Data-plane / VM impact |
|---|---|---|---|---|
| ceilometer (`enable_ceilometer` no; ipmi `enable_ceilometer_ipmi` no, `all.yml:743-744`) | `ceilometer_compute` (privileged, `/run`, `nova_libvirt` volume), `ceilometer_ipmi` | `handlers/main.yml:34-49`, `:51-65` | **Global**: rabbit rpc and notify, memcached | VM impact NOT AVAILABLE (`ceilometer_compute` runs only `ceilometer-polling`, `templates/ceilometer-compute.json.j2:2`) |
| iscsi (`enable_iscsid` derived, `all.yml:794`) | `iscsid` (privileged, ipc host, `/dev`, `/run`, `/sys/kernel/config`, `iscsi_info:/etc/iscsi`) | `handlers/main.yml:2-17` | Per-host (config.json only) | **Risk topic**, outcome NOT AVAILABLE; see 5.2 |
| multipathd (`enable_multipathd` no) | `multipathd` (privileged, ipc host) | `handlers/main.yml:2-16` | Per-host (role template or operator override) | **Risk topic**, outcome NOT AVAILABLE; see 5.3 |
| collectd (no) | `collectd` (privileged, `/sys`, `/dev` ro) | `handlers/main.yml:2-16` | Per-host | none |
| telegraf (no) | `telegraf` (pid host, docker.sock ro) | `handlers/main.yml:2-19` | **Global**: influxdb hosts | none |
| prometheus (no) | `prometheus_node_exporter` (pid host, `/:/host:ro,rslave`), `prometheus_cadvisor` (`/var/run:rw`, `/var/lib/docker:ro`), `prometheus_libvirt_exporter` (`/run/libvirt:ro`; enabled with prometheus when nova uses kvm or qemu, `all.yml:1227`) | `handlers/main.yml:17-32`, `:63-77`, `:139-153` | Per-host on compute. The **server** config lists every compute | none on compute; prometheus_server restarts when computes are added |
| masakari (no) | `masakari_instancemonitor` (privileged) | `handlers/main.yml:34-48` | Per-host | none directly; see 5.6 |
| hacluster (`enable_hacluster` = `enable_masakari_hostmonitor` = `enable_masakari`, `all.yml:771,807`) | `hacluster_pacemaker_remote` (ipc host) | `hacluster/handlers/main.yml:36-50` | Per-host (shared Pacemaker authkey) | NOT AVAILABLE; see 5.15 |
| zun (no) | `zun_compute` (privileged, `/var/lib/docker`, `/dev`, `/run`), `zun_cni_daemon` (privileged) | `handlers/main.yml:40-57`, `:59-76`, plus a loopback copy at `:78-88` | **Global**: rabbit rpc, memcached ×2, **DB creds** | container workloads, outcome NOT AVAILABLE; see 5.7 |
| kuryr (no) | `kuryr` (privileged, NET_ADMIN, `/run`, `/usr/lib/docker`) | `handlers/main.yml:2-18` | Per-host | docker network ops, outcome NOT AVAILABLE; see 5.8 |
| cyborg (no) | `cyborg_agent` (privileged) | `handlers/main.yml:36-51` | **Global**: rabbit rpc and notify, memcached, **DB creds**, placement and nova creds | none |
| skydive | **no role in 2024.1** (see 5.10) | – | – | – |
| monasca | **no role at all in 2024.1** (see 5.11) | – | – | – |
| chrony | **no role in 2024.1** (see 5.12) | – | – | – |
| nova-hyperv | **no role in 2024.1** (see 5.13) | – | – | – |
| (cross-ref) ovn-controller | `ovn_controller` | ovn-controller role | **Global**: `ovn-remote` = SB host list | out of scope |

### 5.1 ceilometer

- Play: `ansible/site.yml:819-834`, hosts central, notification, compute, ipmi.
- Services: `ansible/roles/ceilometer/defaults/main.yml:2-35`. Compute volumes include `/run` and
  `{{ ceilometer_libvirt_volume }}:/var/lib/libvirt` (`:137-146`), where `ceilometer_libvirt_volume` is `nova_libvirt`
  with the libvirt container and `/var/lib/libvirt` otherwise (`:162`). ceilometer-ipmi has no `/dev` mount and is not
  privileged (`:28-35,147-154`). **NOT AVAILABLE:** whether local IPMI (`/dev/ipmi0`) is reachable from it.
- Flow: deploy = register → config → check-containers → clone → bootstrap → flush (`tasks/deploy.yml`). `bootstrap.yml`
  still has a `TODO(Jeffrey4l): fix idempotent` comment (`tasks/bootstrap.yml:2`) and **always runs** the
  `bootstrap_ceilometer` container (ceilometer-upgrade, with the database type `gnocchi` when gnocchi is enabled,
  `defaults/main.yml:196`), delegated to `groups['ceilometer-notification'][0]` (`tasks/bootstrap_service.yml:2-22`).
- Config: `ceilometer.conf` merge chain at `tasks/config.yml:196-214`. The template carries
  `transport_url = rpc_transport_url` (`templates/ceilometer.conf.j2:6`), `notify_transport_url` (`:36`) and
  `memcache_servers` over `groups['memcached']` (`:69`). The same file is rendered for ceilometer-compute on **every
  compute**, so a rabbitmq or memcached membership change restarts `ceilometer_compute` on every compute.
- **Changed in 2024.1:** `event_pipeline.yaml` is now a `merge_yaml` of the role template,
  `{{node_custom_config}}/ceilometer/event_pipeline.yaml` and a per-host file (`tasks/config.yml:255-270`), instead of
  "custom file if it exists, else template"; the `stat` on localhost for it is gone.
- Scaling oddities:
  - Several `delegate_to: localhost` stat/find tasks still **lack `run_once`**: custom meters (`:15-31`), polling.yaml
    (`:106-110`), gnocchi_resources (`:133-137`), event_definitions (`:216-220`), pipeline (`:272-276`). That is roughly
    6 local tasks per host (two for the custom meters), multiplied by the compute count.
  - "Clean default folder for dynamic pollsters definitions" has **no `become` and no host condition** (`:77-80`). It
    deletes `/etc/kolla/ceilometer-central/pollsters.d/` on every run, then recreates and recopies it (`:82-104`). **NOT
    AVAILABLE:** whether ceilometer-central then restarts on every deploy/reconfigure when `pollsters.d` exists, and
    whether the delete, having no become, hits permission errors for non-root ansible users (`config_owner_user: root`,
    `all.yml:20`).
- Precheck: an `assert` (was a `fail`) still requires gnocchi **or** `enable_ceilometer_prometheus_pushgateway` when
  ceilometer is enabled (`tasks/precheck.yml:8-14`).

### 5.2 iscsi (iscsid, tgtd)

- Play: `ansible/site.yml:439-452`, hosts `iscsid`, `tgtd`, `&enable_iscsid_True`.
- `enable_iscsid` is `enable_cinder and enable_cinder_backend_iscsi` (`ansible/group_vars/all.yml:794`), and
  `enable_cinder_backend_iscsi` defaults to `enable_cinder_backend_lvm` (`:753-754`).
- Per-host enablement (`ansible/roles/iscsi/defaults/main.yml:62-73`): iscsid runs on compute, cinder-backup or
  cinder-volume hosts only when cinder and the iscsi backend are enabled, or on ironic-conductor hosts with ironic. tgtd
  runs only with the LVM backend and `cinder_target_helper == tgtadm`. Since the play only targets `&enable_iscsid_True`
  hosts, ironic without the cinder iSCSI backend gets no iscsid.
- Containers (`:2-20`): both privileged, `ipc_mode: host`, with volumes `/dev`, `/run` (`:shared` with Docker),
  `/lib/modules:ro`, `/sys/kernel/config:/configfs`, and, for iscsid only, `iscsi_info:/etc/iscsi` (`:40-58`).
- Config: config.json only. The iscsid command is still `iscsid -d 8 -f` (`templates/iscsid.json.j2:2`), which is
  **debug level 8, very verbose**. So the container restarts only on config.json, image, volume or dimension change, in
  practice **upgrade/pull of a new tag** (and once for the changed systemd unit, [F16](../findings.md#f16)). The flow
  for deploy, upgrade and reconfigure is config-host (loads `configfs`, `tasks/config-host.yml:1-10`) → config →
  check-containers → flush (`tasks/deploy.yml`, `upgrade.yml` = deploy).
- **Host interaction:** bootstrap-servers **removes host `open-iscsi`** on Debian/Ubuntu always, and
  `iscsi-initiator-utils` on RedHat only when `enable_nova_libvirt_container` (ansible-collection-kolla
  `roles/packages/defaults/main.yml:25-34`, applied by `roles/packages/tasks/main.yml:17-21`). **NOT AVAILABLE:**
  whether computes then have no iscsid at all when `enable_iscsid` is false (no cinder iSCSI backend, for example a
  third-party iSCSI SAN).
- **VM impact (NOT AVAILABLE):** whether iSCSI sessions survive an iscsid restart, and whether session recovery or
  re-login after a path or portal failure, and os-brick attach/detach from nova-compute, fail or stall while iscsid is
  down. The `iscsi_info` named volume holds the initiator IQN (kolla `docker/iscsid/extend_start.sh:3-7`). **NOT
  AVAILABLE:** whether recreating the volume (for example after `destroy`) changes the IQN and breaks array ACLs.
- **tgtd restart (consequences NOT AVAILABLE):** the command is only `tgtd -d 1 -f --iscsi portal=...` with empty
  `config_files` (`templates/tgtd.json.j2:2-3`); **new in 2024.1**, the portal address is the variable
  `tgtd_interface_address`, default `api_interface_address` (`defaults/main.yml:22`). The image adds no start script of
  its own. It only inserts `include /var/lib/cinder/volumes/*` into `/etc/tgt/targets.conf` (kolla
  `docker/tgtd/Dockerfile.j2:19`), and nothing runs `tgt-admin` at start. The tgtd container does **not** mount the
  `cinder` volume (`ansible/roles/iscsi/defaults/main.yml:50-58`), so `/var/lib/cinder/volumes` inside it is not the
  cinder-volume data. **NOT AVAILABLE:** whether tgtd keeps its target table only in memory, so that a restart drops
  every exported LVM target and its sessions until cinder-volume (for example at its own restart) re-creates them, and
  whether I/O to attached LVM volumes stalls or fails meanwhile. The precheck fails on RedHat-family hosts when tgtd is
  enabled (`tasks/precheck.yml:29-35`). See
  [Kolla images §5](../../concepts/kolla-images.md#5-per-image-start-behaviour).
- Precheck oddity, still present: it checks that `iscsi_port` 3260 is free on the **iscsid** hosts
  (`tasks/precheck.yml:17-27`), but 3260 is the **target** (tgtd) port. The probed address is now
  `tgtd_interface_address` (`:19`), which makes the mismatch plainer.

### 5.3 multipathd

- Play: `ansible/site.yml:454-466`. Default `enable_multipathd: "no"` (`all.yml:809`). No role has a meta dependency on
  common.
- Container: privileged, ipc host, with `/dev`, `/run` (`:shared` with Docker), `/lib/modules:ro`,
  `/sys/kernel/config:/configfs` (`ansible/roles/multipathd/defaults/main.yml:2-29`). It does not mount `iscsi_info` or
  `cinder`. There are still **no `dimensions`**.
- Config: `multipath.conf` is **first-found** from `{{node_custom_config}}/multipath/<host>/multipath.conf`, then
  `{{node_custom_config}}/multipath.conf`, then the role template (`tasks/config.yml:28-44`). The role template is
  `user_friendly_names no`, `find_multipaths yes`, `skip_kpartx yes`, and an empty blacklist
  (`templates/multipath.conf.j2:1-8`).
- The `dm-multipath` module is loaded by config-host (`tasks/config-host.yml:1-7`).
- Restart (handler `:2-16`): on config.json or multipath.conf change, or on image/volume change.
- **VM impact (NOT AVAILABLE):** whether dm maps persist across a restart, whether path checking and failback pause
  while multipathd is down, and whether a path failure in that window causes I/O errors or queueing depending on
  `no_path_retry`. Restarts run in the same handler step on all notified multipathd hosts of the batch: `flush_handlers`
  puts the notified hosts in the handlers state and the linear strategy queues each handler like a task for every such
  host (ansible-core 2.16.20 `lib/ansible/plugins/strategy/__init__.py:952-963`,
  `lib/ansible/plugins/strategy/linear.py:90-91,129-198`); with serial 0 by default the batch is every host
  (`lib/ansible/executor/playbook_executor.py:300-302`).

### 5.4 collectd and telegraf

- collectd: play `site.yml:342-354`. Privileged, `/sys` and `/dev` ro (`ansible/roles/collectd/defaults/main.yml:2-29`).
  collectd.conf is first-found (host → global → role template), with no merge (`tasks/config.yml:41-58`). The default
  sends to `{{ 'api' | kolla_address }}:{{ collectd_udp_port }}`, i.e. its own host (`templates/collectd.conf.j2:9-11`),
  where telegraf's `socket_listener` receives it if telegraf is enabled
  (`ansible/roles/telegraf/templates/telegraf.conf.j2:29-35`). Per-host only.
- telegraf: play `site.yml:370-382`. `pid_mode: host`, `/proc` and `/sys` ro, `/var/run/docker.sock:ro`
  (`ansible/roles/telegraf/defaults/main.yml:2-10,20-27`). telegraf.conf is first-found, not merged
  (`tasks/config.yml:32-48`). It **loops over `groups['influxdb']`** (`telegraf.conf.j2:14-24`), so adding or removing
  an influxdb host restarts telegraf on every host. The haproxy and elasticsearch inputs test the `loadbalancer` and
  `opensearch` groups (`telegraf.conf.j2:50,58`); **new in 2024.1**, the outward-rabbitmq input is gone with outward
  RabbitMQ.
  - **Latent bug, still present:** the "Copying over telegraf plugin files" task tests `item.value.enabled` inside a
    `with_fileglob` loop of path strings (`tasks/config.yml:50-64`). The glob is currently empty because
    `templates/config/` does not exist, but adding files there would break the task.
  - check-containers does not pass the `HOST_PROC`/`HOST_SYS` env, while the handler does (`handlers/main.yml:12-14`;
    `tasks/check-containers.yml:2-16`).

### 5.5 prometheus (node-exporter, cadvisor, libvirt-exporter)

- Play: `site.yml:416-437`. Hosts include `prometheus-node-exporter`, `prometheus-cadvisor` and
  `prometheus-libvirt-exporter`, which contain compute (`multinode:543-548,556-561,575-576`).
- node_exporter: `pid_mode: host`, `/:/host:ro,rslave`, listens on `api_interface_address:9100`
  (`ansible/roles/prometheus/defaults/main.yml:25-32,260-265`; `templates/prometheus-node-exporter.json.j2:2`;
  `all.yml:565`).
- cadvisor: `/var/run:/var/run:rw` (**this includes docker.sock read-write, which makes the container
  root-equivalent**), `/var/lib/docker:ro`, `/sys:ro`, plus `/:/rootfs:ro` and `/dev/disk:ro`
  (`defaults/main.yml:271-280`). The command is `/opt/cadvisor --port={{ prometheus_cadvisor_port }}` (18080,
  `all.yml:571`) with **no listen address** (`templates/prometheus-cadvisor.json.j2:2`). **NOT AVAILABLE:** whether it
  listens on all interfaces.
- libvirt-exporter: `/run/libvirt:/run/libvirt:ro`, listening on `api_interface_address:9177`
  (`defaults/main.yml:118-124,302-306`; `templates/prometheus-libvirt-exporter.json.j2:2`; `all.yml:573,1227`).
- Compute-side config is config.json only (per-host). The **server** config `prometheus.yml.j2` loops over
  node-exporter, cadvisor, libvirt-exporter and other groups (`templates/prometheus.yml.j2:25-257`). Adding a compute
  changes prometheus.yml and restarts `prometheus_server` (`tasks/config.yml:79-98`), and rendering it needs facts for
  every compute. **Changed in 2024.1:** the haproxy exporter container is gone; prometheus.yml scrapes the
  `loadbalancer` hosts directly (`prometheus.yml.j2:63`), and the server now has a basic-auth `web.yml`
  (`tasks/config.yml:100-116`).
- Scaling: "Find prometheus host config overrides" runs `delegate_to: localhost` **per host**, explicitly
  `run_once: false` (`tasks/config.yml:68-77`), even on hosts that are not prometheus servers.

### 5.6 masakari (monitors)

- Play: `site.yml:1030-1045`. Hosts are masakari-api, masakari-engine, `masakari-hostmonitor` (= control) and
  `masakari-instancemonitor` (= compute) (`multinode:581-591`).
- `masakari-instancemonitor` and `masakari-hostmonitor` are deployed (`ansible/roles/masakari/defaults/main.yml:31-46`),
  both enabled with `enable_masakari` (`all.yml:806-807`). The hostmonitor runs on the control hosts with
  `restrict_to_remotes = True` and `pacemaker_node_type = cluster` (`templates/masakari-monitors.conf.j2:21-43`), and
  the computes run `hacluster_pacemaker_remote` (5.15). There is still no processmonitor (no `processmonitor` in
  `ansible/`). **NOT AVAILABLE:** whether and how fast the hostmonitor detects a failed compute (masakari-monitors and
  Pacemaker code are not in the sources).
- Config: `masakari-monitors.conf` merge chain (`tasks/config.yml:88-110`). It is per-host and has no rabbit, memcached
  or DB. Libvirt is reached over `connection_uri = "qemu+tcp://{{ migration_interface_address }}/system"`
  (`templates/masakari-monitors.conf.j2:16-19`).
  - **Default libvirt auth (outcome NOT AVAILABLE):** nova-cell defaults to `libvirt_enable_sasl: true`
    (`ansible/roles/nova-cell/defaults/main.yml:569`), giving `auth_tcp = "sasl"`
    (`ansible/roles/nova-cell/templates/libvirtd.conf.j2:9-13`). `auth.conf` with the SASL credentials is copied to
    masakari-instancemonitor when `libvirt_enable_sasl` (`ansible/roles/masakari/tasks/config.yml:141-157`) and placed
    at `/var/lib/masakari/.config/libvirt/auth.conf` (`templates/masakari-instancemonitor.json.j2:9-15`). With
    `libvirt_tls: true`, `listen_tcp = 0` (`libvirtd.conf.j2:1-3`; default `libvirt_tls: false`,
    `nova-cell/defaults/main.yml:552`). **NOT AVAILABLE:** whether masakari-instancemonitor connects to libvirt with
    these defaults.
- **Bug, still present:** "Copying over existing policy file" uses `dest: "{{ node_config_directory }}/{{ item }}/..."`
  with `with_dict` (`tasks/config.yml:34-47`, dest at `:37`). When a custom policy exists, the dest path renders a dict.
- Bootstrap (DB sync) runs on every deploy/reconfigure (`tasks/deploy.yml:11`, `bootstrap_service.yml`).

### 5.7 zun (zun-compute, zun-cni-daemon)

- Play: `site.yml:998-1013`. The precheck requires kuryr (`ansible/roles/zun/tasks/precheck.yml:52-58`).
- Containers (`defaults/main.yml:44-61,184-204`): zun_compute is privileged with `/run` (`:shared` with Docker),
  `/usr/lib/docker`, `/var/lib/docker`, `/dev`, `/lib/modules:ro`, `iscsi_info:/etc/iscsi` when iscsid is enabled, and
  `/var/lib/zun:shared` when `zun_configure_for_cinder_ceph`. zun_cni_daemon is privileged.
- Config: `zun.conf` is rendered for **all** zun services including compute (`tasks/config.yml:56-74`). It contains
  `transport_url = rpc_transport_url` (`templates/zun.conf.j2:10`), the full **`[database] connection` with password**
  (`:21-22`), memcached ×2 when `enable_memcached` (`:46,69`), and `docker api_url = tcp://<api_ip>:2375` (`:121-124`).
  - The docker daemon on zun-compute hosts is opened on TCP 2375 **without TLS or auth** by bootstrap-servers when
    `docker_configure_for_zun` is set (`ansible/group_vars/all.yml:123-124`; ansible-collection-kolla
    `roles/docker/templates/docker_systemd_service.j2:13`).
  - **Changed in 2024.1:** `docker_zun_config` is now `{}` (`all.yml:125`), so bootstrap-servers no longer merges an
    etcd `cluster-store` host list into `/etc/docker/daemon.json` on zun-compute hosts (ansible-collection-kolla
    `roles/docker/tasks/config.yml:35-37`).
  - New in 2024.1: the Ceph files for zun-compute are now `<zun_ceph_cluster>.conf` and `<zun_ceph_cluster>.<keyring>`
    (`zun_ceph_cluster: "ceph"`, `defaults/main.yml:251`; `tasks/external_ceph.yml`).
- Handlers: check-containers notifies `"<svc> container changed"`, and handlers `listen` on that as well as being named
  "Restart <svc> container" (`tasks/check-containers.yml:17-21`; `handlers/main.yml:40-76`). On a zun-cni-daemon
  container change, the loopback binary is copied to the host `/opt/cni/bin` (`:78-88`).
- **NOT AVAILABLE:** whether restarting zun_compute stops user containers, and whether a zun_cni_daemon restart breaks
  CNI operations during the window.

### 5.8 kuryr

- Play: `site.yml:695-707`. Hosts are **`compute`** directly, and the service group is hard-coded to `compute`
  (`ansible/roles/kuryr/defaults/main.yml:10-21`).
- The container is privileged with `cap_add: NET_ADMIN`, `/run` (`:shared` with Docker) and `/usr/lib/docker`
  (`:16-19,50-59`). `kuryr.spec` is placed into `/usr/lib/docker/plugins/kuryr/` (`templates/kuryr.json.j2:10-15`).
- Config is per-host: `kuryr_uri` uses its own api IP (`templates/kuryr.conf.j2:2`, `defaults/main.yml:95`), and
  kuryr.conf has no rabbit, memcached or DB (`templates/kuryr.conf.j2:1-29`). **Changed in 2024.1:** `capability_scope`
  is now `local` instead of `global` (`kuryr.conf.j2:6`), so kuryr.conf changes, and kuryr restarts, on every compute at
  the first 2024.1 run. **NOT AVAILABLE:** what the scope change means for existing Docker networks (kuryr-libnetwork
  and Docker code are not in the sources).
- Keystone user registration runs from the compute-host play (`tasks/register.yml`, `tasks/deploy.yml:2`).
- **NOT AVAILABLE:** whether docker network create/attach fails while kuryr is restarting, and whether existing veth
  wiring persists.

### 5.9 cyborg (agent)

- Play: `site.yml:869-883` still uses **`serial: '{{ serial|default("0") }}'`** (`:876`), not `kolla_serial`.
  `ANSIBLE_SERIAL` is therefore ignored for cyborg on reconfigure and upgrade. This **oddity** is still present in
  2024.1.
- `cyborg-agent` runs on compute and is privileged (`ansible/roles/cyborg/defaults/main.yml:11-19`).
- `cyborg.conf` is rendered for all services (`tasks/config.yml:65-83`). It contains DB connection credentials
  (`templates/cyborg.conf.j2:12-13`), placement service credentials (`:34-44`), nova service credentials (`:46-56`),
  rabbit rpc and notify (`:6,64`) and memcached (`:21`). **Global, and it carries DB, placement and nova credentials on
  compute.**
- **Bugs and oddities:**
  - `cyborg_services` has **no `haproxy` key** (`defaults/main.yml:2-27`), so `loadbalancer.yml` configures nothing, yet
    the keystone endpoints are built for port 6666 (`all.yml:369`) behind an FQDN.
  - **New in 2024.1:** the endpoints are `cyborg_internal_fqdn | kolla_url(...)` and
    `cyborg_external_fqdn | kolla_url(...)` (`defaults/main.yml:147-148`), but **no file of the 2024.1 tree defines
    `cyborg_internal_fqdn` or `cyborg_external_fqdn`** (a grep of the whole kolla-ansible tree finds only these two
    uses; `group_vars/all.yml` defines `<svc>_internal_fqdn` for other services, for example `manila_internal_fqdn` at
    `:461`). They are used by keystone registration (`tasks/register.yml`, `defaults/main.yml:169-175`). **NOT
    AVAILABLE** (not run): whether `deploy` then fails at cyborg registration unless the operator defines both
    variables; reviewer to confirm.
  - The keystone service type is `"accelerator"` (`defaults/main.yml:169-175`).

### 5.10 skydive (agent)

**Still does not exist in 2024.1.** `ansible/roles/` has no `skydive` role, `site.yml` has no skydive play, and
`inventory/multinode` has no `skydive-agent` or `skydive-analyzer` group (a grep for `skydive` in `ansible/` finds
nothing).

### 5.11 monasca (agents)

**No longer anything in 2024.1.** The 2023.1 leftovers are gone too: `ansible/roles/monasca` (with its
`tasks/cleanup.yml`), `ansible/monasca_cleanup.yml` and the `monasca_cleanup` command of `tools/kolla-ansible` do not
exist, the `monasca-agent*` groups are gone from `inventory/multinode`, and a grep for `monasca` in `ansible/` and
`tools/kolla-ansible` finds nothing. Containers that an older release left behind are therefore not cleaned up by any
2024.1 playbook.

### 5.12 chrony

**Still does not exist in 2024.1** (see [Chrony](../../components/chrony.md)): `ansible/roles/` has no `chrony` role,
`site.yml` has no chrony play, and `inventory/multinode` has no `chrony` or `chrony-server` group. There is no chrony
container or `chrony.conf` to restart or reconfigure on computes. Time sync is left to the host;
`kolla-ansible prechecks` checks it (`ansible/roles/prechecks/tasks/timesync_checks.yml`, see the Chrony page). **NOT
AVAILABLE:** which time source the hosts use.

### 5.13 nova-hyperv

**Still does not exist in 2024.1**: `ansible/roles/` has no `nova-hyperv` role, `site.yml` has no hyperv play, and
`inventory/multinode` has no `hyperv` group (a grep for `hyperv` in `ansible/` finds only `hypervisor_inspector` and a
comment, `ansible/roles/ceilometer/templates/ceilometer.conf.j2:9`, `ansible/roles/nova-cell/tasks/deploy.yml:21`).

### 5.14 Cross-reference: ovn-controller on compute

The `ovn-controller` role's `setup-ovs.yml` sets `external_ids:ovn-remote={{ ovn_sb_connection }}` in the local OVSDB
through `kolla_toolbox openvswitch_db` (`ansible/roles/ovn-controller/tasks/setup-ovs.yml:13-40`, `ovn-remote` at
`:33`), which is a loop over `groups['ovn-sb-db']` (`all.yml:549`). The task runs on every deploy
(`tasks/deploy.yml:6`). A neutron-ovn-metadata-agent ini on compute also lists the NB and SB DBs
(`ansible/roles/neutron/templates/neutron_ovn_metadata_agent.ini.j2:17-18`).

### 5.15 hacluster (pacemaker-remote)

- Play: `site.yml:709-722`, hosts `hacluster` (= control) and `hacluster-remote` (= compute, `multinode:78-82`),
  `&enable_hacluster_True`. `enable_hacluster` defaults to `enable_masakari_hostmonitor`, which defaults to
  `enable_masakari` (`all.yml:771,807`): **enabling masakari puts a `hacluster_pacemaker_remote` container on every
  compute.**
- Container: `hacluster_pacemaker_remote`, `ipc_mode: host` (`ansible/roles/hacluster/defaults/main.yml:26-33`). Its
  config is config.json and the Pacemaker `authkey`, which the role generates once on the deploy host with
  `dd if=/dev/urandom` when it is missing (`tasks/bootstrap.yml:36-41`) and copies to every remote
  (`tasks/config.yml:81-96`); a change of either restarts the container (`handlers/main.yml:36-50`).
- Each compute is added as a Pacemaker `remote` resource named after its `nodename`, with its api address, by a
  `cibadmin --modify` delegated to the first `hacluster` host (`tasks/bootstrap_service.yml:10-32`).
- **NOT AVAILABLE:** what a `hacluster_pacemaker_remote` restart or a compute removal does to the Pacemaker cluster and
  to masakari host-failure handling (Pacemaker semantics are not in the sources); no task removes the `remote` resource
  of a deleted compute (the only `cibadmin` in `ansible/roles/hacluster/` is the `--modify` at
  `tasks/bootstrap_service.yml:16`).

---

## 6. Per-cluster host lists in templates

### 6.1 grep `for host in groups` over `ansible/roles/*/templates`

Memcached loops (`groups['memcached']`) appear in: aodh, barbican, blazar, **ceilometer**, cinder, cloudkitty,
**cyborg**, designate, glance, gnocchi, heat (×2), horizon, ironic (×2), keystone (×2), magnum, manila (×4), masakari
(api/engine only), mistral, **neutron**, nova (×2), octavia (×2), placement (×2), swift (×2), tacker, venus, watcher,
**zun (×2)** (27 roles in 2024.1; the 2023.1 freezer, murano, sahara, senlin, solum and vitrage roles no longer exist).

Other group loops:
- certificates `tls-backend` and `compute`; designate `designate-backend-bind9`/`designate-worker`; opensearch
  `opensearch`; haproxy-config backends (`groups[host_group]`); loadbalancer (keepalived) `loadbalancer`; **new in
  2024.1:** letsencrypt `loadbalancer` (`letsencrypt/templates/crontab.j2:4,7`, `letsencrypt-lego-run.sh.j2:6,9`);
  keystone fernet-push `keystone`; galera `mariadb` (per shard group); hacluster corosync `hacluster`
  (`hacluster/templates/hacluster_corosync.conf.j2:13`); octavia `octavia-health-manager` and, **new in 2024.1,
  `redis`** (`octavia.conf.j2:82,180`); prometheus.yml (13 groups, including `prometheus-node-exporter`,
  `prometheus-cadvisor`, `prometheus-libvirt-exporter` and now `loadbalancer`); prometheus-alertmanager; rabbitmq;
  **telegraf** `influxdb`.
- Non-loop group references: `cinder.conf.j2:20` and `nova/templates/nova.conf.j2:62` use
  `groups['glance-api'] | length` (the nova-cell `nova.conf.j2` has `num_retries = 3`, `:109`). Cinder coordination is
  `redis_connection_string` or an etcd URL on `kolla_internal_fqdn`, depending on `cinder_coordination_backend`
  (`cinder.conf.j2:271-281`, `group_vars/all.yml:1047`).
- Host lists defined as **variables** rather than template loops: `rpc_transport_url`/`notify_transport_url`
  (`all.yml:248,258`), `nova_cell_rpc/notify_transport_url` (`ansible/roles/nova-cell/defaults/main.yml:206-207`, groups
  default to `om_rpc_group` at `:191,200`), `ovn_nb/sb_connection` (`all.yml:548-549`), and `redis_connection_string`
  (`all.yml:893`). **Changed in 2024.1:** `docker_zun_config` no longer holds an etcd list (`all.yml:125`).

### 6.2 Config files on COMPUTE hosts that embed per-cluster host lists

| File on compute (`/etc/kolla/...`) | Container restarted by its handler | Lists embedded | Evidence |
|---|---|---|---|
| `nova-compute/nova.conf` (and the other nova-cell compute services) | nova_compute, etc. (cross-ref) | cell rabbit rpc and notify | `nova-cell/templates/nova.conf.j2:37,184`; `nova-cell/defaults/main.yml:206-207` |
| `neutron-openvswitch-agent/neutron.conf` (also linuxbridge, ovn-metadata, ovn-agent) | neutron agents (cross-ref) | rabbit rpc and notify, **memcached** | `neutron/templates/neutron.conf.j2:58,123,126`; rendered for agent services at `neutron/tasks/config.yml:87-122` |
| `neutron-ovn-metadata-agent/neutron_ovn_metadata_agent.ini` | ovn metadata agent (cross-ref) | OVN NB and SB DB hosts | `neutron_ovn_metadata_agent.ini.j2:17-18` |
| OVS DB `external_ids:ovn-remote` (not a file) | none (live setting) | OVN SB hosts | `ovn-controller/tasks/setup-ovs.yml:13-40` |
| `ceilometer-compute/ceilometer.conf`, `ceilometer-ipmi/ceilometer.conf` | ceilometer_compute, ceilometer_ipmi | rabbit rpc and notify, **memcached** | `ceilometer.conf.j2:6,36,69` |
| `zun-compute/zun.conf`, `zun-cni-daemon/zun.conf` | zun_compute, zun_cni_daemon | rabbit rpc, **memcached ×2** | `zun.conf.j2:10,46,69` |
| `cyborg-agent/cyborg.conf` | cyborg_agent | rabbit rpc and notify, **memcached** | `cyborg.conf.j2:6,21,64` |
| `skydive-agent/skydive.conf` | – | **no skydive in 2024.1** (5.10) | – |
| `telegraf/telegraf.conf` | telegraf | influxdb hosts | `telegraf.conf.j2:14-24` |
| `/etc/docker/daemon.json` (zun-compute, bootstrap-servers only) | – | **no longer any host list in 2024.1** (`docker_zun_config: {}`, `all.yml:125`) | ansible-collection-kolla `roles/docker/tasks/config.yml:35-37` |
| Windows `nova.conf` and `neutron_hyperv_agent.conf` (hyperv group) | – | **no nova-hyperv in 2024.1** (5.13) | – |

Compute-side files with **no** cluster lists (per-host only): iscsid and tgtd config.json, multipath.conf,
collectd.conf, node-exporter, cadvisor and libvirt-exporter config.json, masakari-monitors.conf, the
hacluster-pacemaker-remote config.json and authkey, kuryr.conf, and the common/fluentd outputs (these use
`elasticsearch_address` and `opensearch_address`, which default to the internal FQDN, `all.yml:885`;
`common/templates/conf/output/01-es.conf.j2:5`, `03-opensearch.conf.j2:5`).

**Implication (consequence NOT AVAILABLE):** adding or removing a host in `rabbitmq` or `memcached` (normally
controllers), then running deploy or reconfigure across the fleet:
- re-templates the files above on **every compute**;
- fires `recreate_or_restart_container` for ceilometer_compute, ceilometer_ipmi, zun_compute, zun_cni_daemon,
  cyborg_agent, the neutron agents, nova_compute (cross-ref) and others;
- runs those restarts in the same handler step on all notified hosts of the batch (ansible-core 2.16.20
  `lib/ansible/plugins/strategy/__init__.py:952-963`, `lib/ansible/plugins/strategy/linear.py:90-91,129-198`); with the
  default `kolla_serial=0` the batch is every host (`lib/ansible/executor/playbook_executor.py:300-302`). **NOT
  AVAILABLE:** whether this causes a fleet-wide reconnect storm on RabbitMQ.

The same fleet-wide re-template happens once on the first 2024.1 run for a cloud that kept the 2023.1 classic-queue
default, because `rabbit_quorum_queue = true` is new in these files ([F17](../findings.md#f17)).

Rendering each of these files also requires facts (`kolla_address(host)`) for every host in `rabbitmq` and `memcached`
(`kolla_ansible/kolla_address.py:56-100`). This matters for `--limit` runs (cross-ref gather-facts.yml).
Conversely, **adding a compute** changes non-compute configs: prometheus.yml (prometheus_server restart,
`prometheus.yml.j2:37,102,198`) and, with masakari, the Pacemaker CIB (a new `remote` resource, 5.15).

---

## 7. Consolidated bugs and oddities

Status against 2024.1 in each item.

1. Swift `stop.yml:23-31`: account-auditor guard checks `swift_object_auditor`. Still present.
2. Swift precheck checks rsync port 873, but rsyncd uses 10873 (`swift/tasks/precheck.yml:86-95` vs `all.yml:628`).
   Still present.
3. Swift `{% if enable_swift_recon %}` without `| bool` against the string `"no"` (`account.conf.j2:15`, etc.;
   `all.yml:844`). Still present. **NOT AVAILABLE:** whether recon is then always on.
4. Swift deploy never restarts on config or ring change (no notify anywhere; no-op handler at
   `swift/handlers/main.yml:2-4`). Reconfigure fails if any swift container is down (`reconfigure.yml:32-42`). The
   "rolling" upgrade stops all storage at once (`rolling_upgrade.yml:31-39`). All still present.
5. Octavia: `heartbeat_key = insecure` is still hard-coded (`octavia.conf.j2:81`). The amp network, secgroup and flavor
   are filled in by default from the resources that `octavia_auto_configure` creates, and stay unset with no precheck
   only when it is off (`octavia.conf.j2:91-108`, `all.yml:1323`). The HM precheck still uses `api_interface_address`
   (`precheck.yml:29-38`). The CA private key is still copied to 3 services (`config.yml:120-171`). **New in 2024.1:**
   the jobboard is on by default with the amphora provider but needs Redis, which is off by default, so `prechecks`
   fails with the defaults (`all.yml:832,840`; `octavia/tasks/precheck.yml:67-73`).
6. Manila: policy copy still has no `become` (`manila/tasks/config.yml:101-112`). Service-instance password still
   defaults to `manila` (`defaults/main.yml:212`). Neutron host_in_groups for manila-share are still asymmetric (OVS:
   generic only, `neutron/defaults/main.yml:36`; LB: any backend, `:60`). **New in 2024.1:** the CephFS config moved to
   a `ceph/` sub-directory with per-cluster files (`manila/tasks/external_ceph.yml:2-42`), which changes the copied
   config on the first run.
7. Masakari: policy-file dest still uses a dict `item` (`masakari/tasks/config.yml:37`). A hostmonitor exists (5.6,
   5.15); there is still no processmonitor. instancemonitor uses qemu+tcp and receives the SASL `auth.conf` when SASL is
   on (`masakari/tasks/config.yml:141-157`; `masakari-monitors.conf.j2:18`; `nova-cell/defaults/main.yml:569`).
8. Cyborg: the play still uses `serial` instead of `kolla_serial` (`site.yml:876`). There is still no haproxy entry
   (`cyborg/defaults/main.yml:2-27`). **New in 2024.1:** the endpoints use
   `cyborg_internal_fqdn`/`cyborg_external_fqdn`, which nothing defines (`defaults/main.yml:147-148`). DB credentials
   (and placement and nova credentials) are on compute.
9. Telegraf: `item.value.enabled` in a `with_fileglob` loop (`telegraf/tasks/config.yml:50-64`). Still present.
10. Ceilometer: pollsters dir deleted every run without become (`ceilometer/tasks/config.yml:77-80`). Many localhost
    stats lack `run_once` (one fewer than in 2023.1, since event_pipeline is now merged). The bootstrap is explicitly
    non-idempotent (`tasks/bootstrap.yml:2`). All still present.
11. iscsid runs at debug `-d 8` (`iscsi/templates/iscsid.json.j2:2`). The precheck tests port 3260 on iscsid hosts, now
    on `tgtd_interface_address` (`iscsi/tasks/precheck.yml:17-27`). Both still present.
12. multipathd has no meta and no dimensions (`multipathd/defaults/main.yml:2-10`); config overrides are first-found
    (`multipathd/tasks/config.yml:28-44`). Still as in 2023.1.
13. nova-hyperv: **does not apply**, the role does not exist in 2024.1 (5.13).
14. Security spread onto compute: DB credentials (zun `zun.conf.j2:21-22`, cyborg `cyborg.conf.j2:12-13`);
    unauthenticated docker TCP 2375 for zun (`all.yml:124`); cadvisor with rw `/var/run` (docker.sock)
    (`prometheus/defaults/main.yml:277`); the shared Pacemaker `authkey` on every compute when masakari is enabled
    (`hacluster/tasks/config.yml:81-96`). No skydive or chrony in 2024.1.
15. Barbican and other bootstraps (octavia, manila, ceilometer, masakari, zun, cyborg) re-run their DB sync container on
    every deploy/reconfigure (bootstrap containers are auto-removed, `kolla_container.py:314`). Still present.
16. New in 2024.1: kuryr's `capability_scope` changed from `global` to `local` (`kuryr/templates/kuryr.conf.j2:6`), so
    every kuryr container restarts on the first 2024.1 run; the effect on existing networks is NOT AVAILABLE.

## 8. NOT AVAILABLE list

- NOT AVAILABLE: whether the swift containers serve the new rings once `reconfigure` has restarted them. A changed ring
  file makes `--check` return rc 1 (the rings are `config_files` entries,
  `swift/templates/swift-object-server.json.j2:4-15`; kolla `docker/base/set_configs.py:165-198,220-242`;
  [Kolla images §3.3](../../concepts/kolla-images.md#33-exit-codes)), and `reconfigure` then restarts the container
  under COPY_ALWAYS (`swift/tasks/reconfigure.yml:91-105`). That `deploy` leaves the old rings in running containers is
  settled in code ([§3.4](#34-task-flow)).
- NOT AVAILABLE: the effective value of `enable_swift_recon` in the rendered `object-server.conf`.
- NOT AVAILABLE: what an iscsid, tgtd or multipathd restart does to attached volumes under I/O (session state, path
  failover, the guest view); for tgtd, whether the LVM targets come back without a cinder-volume restart.
- NOT AVAILABLE: whether masakari-instancemonitor can connect to libvirt with SASL on (it receives `auth.conf`, 5.6).
- NOT AVAILABLE: whether the fleet-wide restarts after adding a rabbitmq or memcached host cause a reconnect storm, with
  `kolla_serial=0` versus a set `ANSIBLE_SERIAL`.
- NOT AVAILABLE: Octavia amphora behaviour after a change in the health-manager host list.
- NOT AVAILABLE: whether ceilometer-ipmi can reach local IPMI without privileged mode or `/dev`.
- NOT AVAILABLE: what `octavia_auto_configure` does during an upgrade from manually registered Ussuri resources with
  other names (2.3).
- NOT AVAILABLE: whether and how fast masakari-hostmonitor detects a failed compute, and what a
  `hacluster_pacemaker_remote` restart or a removed compute does to the Pacemaker cluster (5.6, 5.15).
- NOT AVAILABLE (new in 2024.1): what Octavia does when the jobboard Redis is unreachable or a Redis host is replaced
  (2.5, 2.6).
- NOT AVAILABLE (new in 2024.1): whether cyborg registration fails because `cyborg_internal_fqdn`/`cyborg_external_fqdn`
  are undefined (5.9).
- NOT AVAILABLE (new in 2024.1): what kuryr's `capability_scope = local` means for existing Docker networks (5.8).

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
