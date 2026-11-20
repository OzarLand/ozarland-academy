---
title: Fact sheet D
description: Fact sheet for Barbican, Octavia, Swift, Manila and every role that places containers on compute hosts, with the templates embedding host lists.
tags: [barbican, octavia, swift, manila, iscsi, scaling]
---

# Fact sheet D

Source: Kolla-Ansible tag `2023.1-eol` (commit `4891a21`), kolla tag `2023.1-eol`, ansible-collection-kolla
`2023.1-eol`. All paths below are relative to the repo root.
Labels: **FACT** (the default, not written out) = read directly from the cited source: kolla-ansible, the kolla image
repository (cited as kolla `docker/...`) or Ansible (cited as ansible-core 2.14.18 `lib/ansible/...`). **NOT
AVAILABLE** = these sources do not establish it, often because it depends on upstream OpenStack, Swift, Ceph, libvirt,
iSCSI or Docker behaviour that is not in them.
Out of scope here, because other fact sheets cover them: site.yml mechanics, nova/nova-cell/neutron/openvswitch/common,
kolla_docker semantics, service-ks-register, service-rabbitmq, service-images-pull, service-stop. These are cited only
as cross-references.

Common facts used throughout:
- Every role below that still exists in 2023.1 has `tasks/main.yml` = `include_tasks: "{{ kolla_action }}.yml"` (for
  example `ansible/roles/barbican/tasks/main.yml:2`). **No role has a meta dependency on `common` any more**: no role in
  `ansible/roles/` has a `meta/` directory, and `common` is its own play tagged `common` (`ansible/site.yml:86-97`). The
  roles `chrony`, `skydive` and `nova-hyperv` do not exist in 2023.1, and `ansible/roles/monasca` holds only `defaults/`
  and `tasks/cleanup.yml`, used by `ansible/monasca_cleanup.yml` and by no play of `site.yml` (sections 5.10 to 5.13).
- Bootstrap containers are started with `kolla_docker action=start_container detach=False restart_policy=oneshot` (for
  example `ansible/roles/barbican/tasks/bootstrap_service.yml:6-17`); a `oneshot` container is started directly, without
  a systemd unit (`ansible/module_utils/kolla_docker_worker.py:400-406`). `remove_on_exit` defaults to `True`
  (`ansible/library/kolla_docker.py:304`; `ansible/module_utils/kolla_docker_worker.py:413-428`), so a bootstrap
  container (DB sync) is created afresh and **re-runs on every deploy/reconfigure** for any role whose `deploy.yml`
  imports `bootstrap.yml`.
- `kolla-ansible upgrade` and `reconfigure` pass `-e kolla_serial=${ANSIBLE_SERIAL}`, which defaults to 0
  (`tools/kolla-ansible:290,508,517`). In every play, `run_once` tasks (keystone registration, DB bootstrap) run once
  per serial batch: each batch is a separate run of the play, and `run_once` sends the task only to the first host left
  (ansible-core 2.14.18 `lib/ansible/executor/playbook_executor.py:181-190`,
  `lib/ansible/plugins/strategy/linear.py:217,247-248`).
- The transport URLs are global host lists:
  `ansible/group_vars/all.yml:212`
  `rpc_transport_url: "{{ om_rpc_transport }}://{% for host in groups[om_rpc_group] %}...{% endfor %}/{{ om_rpc_vhost }}"` with `om_rpc_group: "rabbitmq"` (`:209`). Similarly `notify_transport_url` at `:222` with `om_notify_group: "rabbitmq"` (`:219`).

---

## 1. Barbican

### 1.1 Plays in site.yml

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| loadbalancer include | `ansible/site.yml:118-122` | `loadbalancer` (the "Apply role loadbalancer" play, `:99-110`) | `barbican` (`include_role tasks_from: loadbalancer`, `when: enable_barbican`). The whole block applies only when `enable_haproxy` and `kolla_action in ['deploy','reconfigure','upgrade','config']` (`:339-341`) |
| Apply role barbican | `ansible/site.yml:765-775` | `barbican-api`, `barbican-keystone-listener`, `barbican-worker`, `&enable_barbican_True` | `barbican`; `serial: kolla_serial` (`:772`) |

Default inventory: all three groups are children of `barbican`, which has `control` as its child
(`ansible/inventory/multinode:146-147,383-390`).

### 1.2 Services (`ansible/roles/barbican/defaults/main.yml:2-41`)

| Service | Container | Group | Enabled | Notable |
|---|---|---|---|---|
| barbican-api | `barbican_api` | barbican-api | `true` | haproxy `barbican_api` (internal) and `barbican_api_external`, both with `tls_backend: barbican_enable_tls_backend` (`:11-25`). Named volume `barbican:/var/lib/barbican/` (`:135`) |
| barbican-keystone-listener | `barbican_keystone_listener` | barbican-keystone-listener | `true` | no haproxy |
| barbican-worker | `barbican_worker` | barbican-worker | `true` | no haproxy |

Keystone registration: service type `key-manager` (`:182-188`), user `barbican` with admin on `service` (`:190-194`),
and roles `key-manager:service-admin`, `creator`, `observer`, `audit` (`:162-165,196-200`, `tasks/register.yml:2-8`).

### 1.3 Task flow per kolla_action

- **deploy** (`tasks/deploy.yml:1-14`): register.yml (keystone) → config.yml → check-containers.yml (compare_container,
  notify restart) → clone.yml (dev mode only) → bootstrap.yml → flush handlers.
- **reconfigure** = deploy (`tasks/reconfigure.yml:2`). So keystone registration and the DB bootstrap container **re-run
  on every reconfigure**.
- **upgrade** (`tasks/upgrade.yml:1-9`): config → check-containers → bootstrap_service (DB sync only, no DB/user
  creation) → flush. No keystone re-registration.
- **stop / pull / precheck / deploy-containers / loadbalancer / config_validate** use the standard helpers
  (`config_validate` is new in 2023.1: `kolla-ansible validate-config` sets `kolla_action=config_validate`,
  `tools/kolla-ansible:544-547`). The Ussuri `check.yml` (a secret store/fetch/delete sanity check gated by
  `kolla_enable_sanity_barbican`) **no longer exists**: `ansible/roles/barbican/tasks/` has no `check.yml`, no
  `kolla_enable_sanity_*` variable is left in `ansible/`, and `tools/kolla-ansible` has no `check` subcommand.

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

- MariaDB: `sql_connection` (`templates/barbican.conf.j2:15`), DB created via `kolla_toolbox mysql_db/mysql_user`,
  delegated to `groups['barbican-api'][0]` (`tasks/bootstrap.yml:2-36`). The login user is
  `barbican_database_shard_root_user` (`defaults/main.yml:60`), which is `root_shard_<id>` when `enable_proxysql` is
  set.
- RabbitMQ: `transport_url = {{ rpc_transport_url }}` (`barbican.conf.j2:17`) and the notifications transport (`:73`).
  Barbican does **not** use the `service-rabbitmq` role.
- Memcached: `memcached_servers` loops over `groups['memcached']` (`barbican.conf.j2:70`).
- Keystone: authtoken (`:55-70`). **Keystone notifications are coupled**: `[keystone_notifications] enable = True`, and
  `topic = barbican_notifications` when `enable_keystone` (`barbican.conf.j2:49-53`). The keystone role adds the
  `barbican_notifications` topic when `enable_barbican` is set (`ansible/roles/keystone/defaults/main.yml:196-201`).
- Consumers: cinder (`ansible/roles/cinder/templates/cinder.conf.j2:238-243`), glance (`glance-api.conf.j2:150-155`),
  nova and nova-cell (`ansible/roles/nova-cell/templates/nova.conf.j2:246-251`, so **compute** `nova.conf` changes when
  barbican is enabled), octavia (`octavia.conf.j2:20-24`), magnum, tacker, murano, horizon, skyline (templates that test
  `enable_barbican`).

### 1.6 Operationally notable

- **The crypto KEK lives in passwords.yml.** `barbican_crypto_plugin: "simple_crypto"`
  (`ansible/group_vars/all.yml:926`), and `kek = '{{ barbican_crypto_key }}'` (`barbican.conf.j2:42-46`;
  `etc/kolla/passwords.yml:56`). `kolla-genpwd` generates it as a Fernet key (`kolla_ansible/cmd/genpwd.py:99-100,151`)
  and only fills empty values (`:90`). **NOT AVAILABLE:** whether losing or changing `barbican_crypto_key` makes stored
  secrets undecryptable (simple_crypto semantics are Barbican code, which is not in the sources). This key must be in
  the passwords.yml backup.
- p11_crypto: the library path `/usr/lib/libCryptoki2_64.so` (`all.yml:927`) is used only in the conf template
  (`barbican.conf.j2:32`) and is not mounted into the containers (`defaults/main.yml:131-149`). No task generates the
  MKEK or HMAC keys: a grep for `mkek|gen_hmac|barbican-manage` in `ansible/` finds only the conf template
  (`barbican.conf.j2:36,38`). **NOT AVAILABLE:** what else an HSM setup needs (for example a custom image or extra
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
| loadbalancer include | `ansible/site.yml:261-265` | loadbalancer | `octavia` |
| Apply role octavia | `ansible/site.yml:885-896` | `octavia-api`, `octavia-health-manager`, `octavia-housekeeping`, `octavia-worker`, `&enable_octavia_True` | `octavia`; serial kolla_serial |

Default inventory: all five groups (`octavia-api`, `octavia-driver-agent`, `octavia-health-manager`,
`octavia-housekeeping`, `octavia-worker`) are children of `octavia`, which is `control`
(`ansible/inventory/multinode:201-202,591-604`). The play does not list `octavia-driver-agent`; with the default
inventory its hosts are the same control hosts.

### 2.2 Services (`ansible/roles/octavia/defaults/main.yml:2-56`)

`octavia_api` (haproxy `octavia_api`/`octavia_api_external` on port 9876, now **with `listen_port` and
`tls_backend: octavia_enable_tls_backend`**, `:11-25`), `octavia_driver_agent` (new in 2023.1,
`enabled: enable_octavia_driver_agent`, `:26-32`; default: only with `neutron_plugin_agent: ovn`,
`ansible/group_vars/all.yml:735`), `octavia_health_manager`, `octavia_housekeeping`, `octavia_worker`. The other four
have `enabled: true`, and none has privileged or special flags.
Keystone: service type `load-balancer` (`:236-242`). User `octavia` is given admin on `service` **and** on
`{{ octavia_service_auth_project }}`, default `service` (`:225,244-255`). Five `load-balancer_*` roles are created
(`:58-63`, `tasks/register.yml:9-21`).

### 2.3 Task flow

- **deploy** (`tasks/deploy.yml:1-19`): register → **prepare.yml** when `octavia_auto_configure` (new, see 2.5) →
  **config-host.yml** (new: the health-manager interface when `octavia_network_type: tenant`,
  `tasks/config-host.yml:2-6`) → config → check-containers → clone (dev mode only) → bootstrap (DB/user, then
  `bootstrap_octavia` container) → flush.
- **reconfigure** = deploy (`tasks/reconfigure.yml:2`), so the DB sync, keystone registration and, with
  `octavia_auto_configure`, the resource creation re-run.
- **upgrade** (`tasks/upgrade.yml:1-9`): config → check-containers → bootstrap_service → flush. Upgrade does **not** run
  register.yml, prepare.yml or config-host.yml. The Ussuri task **"Removing octavia user from admin project"**
  (`os_user_role state: absent` on `keystone_admin_project`) **no longer exists** in 2023.1: `upgrade.yml` has only the
  four steps above.
  - **BUG (consequence NOT AVAILABLE):** the Ussuri bug (with `octavia_service_auth_project: admin`, every upgrade
    removed the role that register.yml granted) **does not apply to 2023.1**, since the removal task is gone
    (`tasks/upgrade.yml:1-9`). With `octavia_auto_configure` on, `upgrade` still runs `get_resources_info.yml` first
    (`tasks/config.yml:2-3`), which looks up the flavor, project, security groups and network by name;
    `ansible/group_vars/all.yml:1226-1227` says to set `octavia_auto_configure: no` and keep the previous Octavia
    configuration when upgrading from Ussuri. **NOT AVAILABLE:** what that lookup does when the resources were created
    manually under other names (the `os_*_info` modules are not in these sources).
- `check.yml` is empty.

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
services. Volumes are now passed with `reject('equalto','')` (for example `:12`); kolla_docker would skip empty volume
strings anyway (`ansible/module_utils/kolla_container_worker.py:415-417`).

### 2.5 OpenStack resources: Kolla creates none

**Changed in 2023.1: no longer true by default.** With `octavia_auto_configure` (default: true when `amphora` is in
`octavia_provider_drivers`, which it is by default, `ansible/group_vars/all.yml:1228`,
`ansible/roles/octavia/defaults/main.yml:361`), `deploy` and `reconfigure` run `prepare.yml`, which creates, `run_once`
and delegated to `groups['octavia-api'][0]`: the amphora flavor (`amphora`, 1 vCPU, 1024 MB, 5 GB, not public,
`defaults/main.yml:294-299`), the nova keypair, the security groups and their rules, the lb-mgmt network and subnet
(`octavia_amp_network_cidr: 10.1.0.0/24`, `:354`) and, for IPv6, a router (`tasks/prepare.yml:2-161`).
`kolla-ansible octavia-certificates` now generates the certificates (`tools/kolla-ansible:536-538`,
`ansible/octavia-certificates.yml`). Kolla still does **not** create the amphora image. The repo's own doc now describes
automatic registration as the default ("Option 1: Automatic resource registration (default, recommended)",
`doc/source/reference/networking/octavia.rst:113-128`).
The template consumes the IDs:
- With `octavia_auto_configure`, `amp_image_owner_id`, `amp_boot_network_list`, `amp_secgroup_list` and `amp_flavor_id`
  come from the facts that `get_resources_info.yml` registered (`templates/octavia.conf.j2:103-108`). With it off, each
  is written only if the operator defines `octavia_amp_boot_network_list`, `octavia_amp_secgroup_list` or
  `octavia_amp_flavor_id` (`octavia.conf.j2:90-102`); no group default defines them, and **no precheck validates them**:
  `tasks/precheck.yml:1-65` checks only the API and HM ports, the 4 PEM files (when the amphora provider is enabled) and
  the neutron plugin for `tenant`.
- Hard-coded values: `amp_image_tag = {{ octavia_amp_image_tag }}` (default `amphora`) and
  `amp_ssh_key_name = {{ octavia_amp_ssh_key_name }}` (default `octavia_ssh_key`) are now variables
  (`octavia.conf.j2:87-88`, `defaults/main.yml:268-270`), but `heartbeat_key = insecure` (`octavia.conf.j2:80`) is still
  a **security oddity** with no variable to change it except an override file.
- `[certificates] ca_private_key_passphrase = {{ octavia_ca_password }}` (`:16-19`) must match the `server_ca.key.pem`
  in use.
- Barbican: if `enable_barbican`, the region and endpoint for the cert manager are set (`:20-24`). **NOT AVAILABLE:**
  whether TLS-terminated listeners need barbican.
- Upgrades from Ussuri: the code comment says to set `octavia_auto_configure: no` and keep the existing configuration
  (`ansible/group_vars/all.yml:1226-1227`). The doc still notes that Train and earlier registered resources in `admin`
  (`octavia.rst:245-253`); `octavia_service_auth_project` defaults to `service` (`defaults/main.yml:225`).

### 2.6 Health-manager network requirements

- `bind_ip = {{ octavia_network_interface_address }}`, `bind_port = {{ octavia_health_manager_port }}` (5555,
  `all.yml:446`) (`octavia.conf.j2:77-79`).
- `controller_ip_port_list` loops over **all** `groups['octavia-health-manager']` using
  `'octavia_network' | kolla_address(host)` (`octavia.conf.j2:81`). This needs facts for every HM host.
- `octavia_network_interface` defaults to `api_interface`, or to `o-hm0` when `octavia_network_type: tenant`
  (`all.yml:244`; `octavia_network_type: "provider"` by default, `:1236`), and the address comes from
  `'octavia_network' | kolla_address` (`all.yml:269`). `kolla_address` raises `FilterError` if the interface or address
  family is missing on the host (`kolla_ansible/kolla_address.py:84-100,132-136`). The `[health_manager]` section is
  rendered into octavia.conf for **all services**, so **every octavia host (api, worker and housekeeping too) must have
  `octavia_network_interface` with an address**, or templating fails.
- With the default `provider` type, Kolla does not create the lb-mgmt interface, bridge or VLAN on the controllers; the
  doc says to bridge it to OVS manually (`doc/source/reference/networking/octavia.rst:84-99`). **New in 2023.1:** with
  `octavia_network_type: tenant` (and `octavia_auto_configure`), on each health-manager host Kolla creates a Neutron
  port, adds it to `br-int` with `docker exec openvswitch_vswitchd ovs-vsctl`, and installs and starts an
  `octavia-interface` systemd unit (`tasks/config-host.yml:2-6`, `tasks/hm-interface.yml:2-100`); a precheck rejects
  `tenant` unless `neutron_plugin_agent` is `openvswitch` (`tasks/precheck.yml:56-65`).
- Precheck oddity: the HM free-port check uses `api_interface_address`, not `octavia_network_interface_address`
  (`tasks/precheck.yml:29-38`). The two differ only when `octavia_network_interface` is not `api_interface` (for example
  with `tenant`).
- Adding or removing a health-manager host changes octavia.conf on all octavia hosts and restarts them
  (`octavia.conf.j2:81`; `tasks/config.yml:86-104`). **NOT AVAILABLE:** whether the controller list is written into an
  amphora at boot, so that existing amphorae keep the old list until failover.
- Security spread: `server_ca.key.pem` (the CA private key) is copied to the worker, housekeeping **and** health-manager
  config dirs (`tasks/config.yml:120-171`).

### 2.7 Other dependencies

MariaDB (`octavia.conf.j2:40-44`), RabbitMQ rpc (`:9`) and notify (`:122-123`), memcached ×2 loops (`:58,75`), keystone
(`:46-75`), and glance, neutron and nova via internal endpoints (`:143-156`). With `neutron_plugin_agent: ovn`, the OVN
NB and SB connections (`:29-33`). Topology is `octavia_loadbalancer_topology: "SINGLE"`
(`roles/octavia/defaults/main.yml:273`).

---

## 3. Swift

### 3.1 Plays

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| loadbalancer include | `ansible/site.yml:304-308` | loadbalancer | `swift` |
| Apply role swift | `ansible/site.yml:470-481` | `swift-account-server`, `swift-container-server`, `swift-object-server`, `swift-proxy-server`, `&enable_swift_True` | `swift`; serial kolla_serial |

Default inventory: proxy is in `swift` (control); account, container and object servers are in `storage`
(`ansible/inventory/multinode:143-144,370-380`).

### 3.2 Services: "old-style" role

`swift_services` contains **only** `swift-proxy-server`, and only for haproxy
(`ansible/roles/swift/defaults/main.yml:2-16`). It has no container_name, image, volumes or check-containers. Containers
are started imperatively in `tasks/start.yml` with `kolla_docker action: start_container`:

| Container | Group | Notes (`tasks/start.yml`) |
|---|---|---|
| `swift_rsyncd` | any of account, container or object | `:36-49`. Rsync daemon on port `swift_rsync_port` 10873 (`all.yml:544`, `templates/swift-rsyncd.json.j2:2`). It is the only swift image that fixes disk ownership at start: it chowns `/srv/node` and its top-level mount points to `swift:swift` (kolla `docker/swift/swift-rsyncd/extend_start.sh:3`). The other swift images have no `extend_start` (kolla `docker/swift/*/` hold only `Dockerfile.j2`, plus `swift_sudoers` in `swift-base`) |
| `swift_account_server/auditor/replicator/reaper` (+ `_replication_server` if a separate replication net exists) | swift-account-server | `:51-128` |
| `swift_container_server/auditor/replicator/updater` (+ replication server) | swift-container-server | `:130-208` |
| `swift_object_server/auditor/replicator/updater/expirer` (+ replication server) | swift-object-server | `:210-303` |
| `swift_proxy_server` | swift-proxy-server | `:305-317`, only when `run_start_swift_proxy_server` |

Disks: `find_disks` runs via `docker exec kolla_toolbox ... -m find_disks name=KOLLA_SWIFT_DATA match_mode=strict`
(`start.yml:2-14`; the command is now `{{ kolla_container_engine }} exec`, `:4`; `defaults/main.yml:57-59`). Each disk
is then mounted `xfs` by UUID at `/srv/node/<fs_label>` with `noatime,nodiratime,logbufs=8` (`start.yml:23-34`). The
`find_disks` module is not in this repo (`ansible/library/` has only 4 modules); it ships in the kolla_toolbox image.
Volumes: `/srv/node` with `:shared`, `/etc/kolla/swift` mounted at `/var/lib/kolla/swift` (ring files), and the named
volume `swift_recon_cache` (now also on the account and container servers, `start.yml:63,142`). **No `kolla_logs`
volume**: all swift logs go over UDP syslog to `syslog_server = api_interface_address` (`defaults/main.yml:69`,
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
  `tasks/register.yml:9-20`) → config → start.yml → check.yml (empty in 2023.1).
  - **No task in the swift role has `notify:`** (a grep for `notify` in `ansible/roles/swift/tasks/` finds nothing). The
    only handler is a no-op `debug` (`handlers/main.yml:2-4`), triggered only by service-cert-copy.
  - `start_container` recreates a container only when container properties differ (image, volumes, ...;
    `module_utils/kolla_docker_worker.py:390-394`). **So `deploy` does not apply swift config or ring changes to running
    containers** (verified in code): `start_container` compares only container properties and never runs
    `kolla_set_configs --check`, which only `compare_container` calls
    (`module_utils/kolla_container_worker.py:20,59-66`, `module_utils/kolla_docker_worker.py:155-190`);
    `kolla_set_configs` copies config and rings into the container only at container start (kolla
    `docker/base/start.sh:11`, `docker/base/set_configs.py:535-553`); every swift command reads those copies, not the
    bind-mounted sources (`/etc/swift/*.conf` or `/etc/rsyncd.conf` in `templates/swift-*.json.j2`; no template sets
    `swift_dir`); and no task notifies a handler. See
    [Kolla images §2](../../concepts/kolla-images.md#2-start-path-common-to-every-image).
- **reconfigure** (`tasks/reconfigure.yml:1-101`) is a different, legacy flow:
  1. It builds the list of all swift containers, plus replication servers if `swift_has_replication_network` (`:2-30`).
  2. It **fails if any listed container is not running** (`:32-41`), so reconfigure cannot repair a crashed container.
  3. It runs config.yml, then `{{ kolla_container_engine }} exec -u root <c> kolla_set_configs --check` (`:43-53`).
  4. It removes and re-creates containers under COPY_ONCE (`:68-86`), or does a plain `restart_container` under
     COPY_ALWAYS when the check returns rc==1 (`:88-101`). In 2023.1 `restart_container` restarts the container through
     its systemd unit (`module_utils/kolla_docker_worker.py:460-480`).
  - Under COPY_ALWAYS (the default, `all.yml:43`), all changed containers on all hosts of the batch restart in the same
    task (`:88-101`). With default `kolla_serial=0` (`tools/kolla-ansible:290`) the batch is every host of the play
    (ansible-core 2.14.18 `lib/ansible/executor/playbook_executor.py:300-302`), so **every changed proxy, on every proxy
    host, restarts in that one task**. **NOT AVAILABLE:** whether this opens an outage window.
- **upgrade** (`tasks/upgrade.yml:1-6`) uses `rolling_upgrade.yml` by default (`swift_enable_rolling_upgrade: "yes"`,
  `defaults/main.yml:72`). Despite the name, it stops **all storage containers on all storage hosts at once**
  (`rolling_upgrade.yml:31-38`, with a TODO admitting it at `:28-30`), restarts them, then stops and starts the proxies
  (`:48-66`). The proxy start here omits `/etc/timezone` and `kolla_logs` (`:62-65`), which is consistent with
  start.yml.
- **stop** (`tasks/stop.yml`) contains a **bug**: the account-auditor stop checks
  `'swift_object_auditor' not in skip_stop_containers` (`:23-31`).

### 3.5 Config files (`tasks/config.yml`)

- Config dirs and config.json for **all 18 services are created on every host in the play**, with no group filter
  (`:2-29,35-59`). swift.conf is copied for all 17 services on every host (`:61-91`). `swift.conf` contains
  `swift_hash_path_suffix/prefix` from passwords.yml (`templates/swift.conf.j2:1-3`, `etc/kolla/passwords.yml:109-110`).
  **NOT AVAILABLE:** what changing them after data is written does (Swift semantics are not in the sources).
- account, container and object `*.conf` are written for their groups (`:93-155`). Override chain: template →
  `global.conf` → `swift/<type>.conf` → `swift/<svc>.conf` → `swift/<host>/<svc>.conf`.
- The proxy chain is template → global.conf → `swift/proxy-server.conf` → `swift/<host>/proxy-server.conf` (`:157-171`).
- `rsyncd.conf` is a plain template (not mergeable) bound to `'swift_replication' | kolla_address`
  (`templates/rsyncd.conf.j2:1`).
- policy.json is copied **without `become`** (`config.yml:206-230`).

### 3.6 Networks and ports

- Storage services bind to `swift_storage`; `replicat*` services bind to `swift_replication`
  (`templates/object.conf.j2:1-3`, `account.conf.j2:1-3`). In 2023.1 `swift_storage_interface` defaults to
  `network_interface` and `swift_replication_interface` to `swift_storage_interface` (`all.yml:240-241`).
- `swift_has_replication_network` is true when the interfaces differ (`defaults/main.yml:65`). Replicators use
  `RSYNC_CONNECT_PROG: "nc %H {{ swift_rsync_port }}"` (`start.yml:87,105,166` etc.).
- Precheck **bug**: the rsync free-port check probes port **873** (`precheck.yml:86-95`), but rsyncd listens on 10873.

### 3.7 Dependencies

- Keystone authtoken (`proxy-server.conf.j2:36-51`).
- Memcached: two loops over `groups['memcached']` (`:25,51`).
- RabbitMQ only when `enable_ceilometer`: the ceilometer middleware uses `url = {{ notify_transport_url }}` (`:58-66`).
- No MariaDB.
- Cinder backup can point at swift (`ansible/roles/cinder/templates/cinder.conf.j2:43-50`). Ceilometer's register.yml
  grants `ResellerAdmin` when swift is enabled (`ansible/roles/ceilometer/tasks/register.yml:8-22`).

### 3.8 Oddities

- **`enable_swift_recon` is tested without `| bool`**: `{% if enable_swift_recon %}` (`account.conf.j2:15,17`,
  `container.conf.j2:15,17`, `object.conf.j2:19,22`). The default is the string `"no"` (`all.yml:750`), not a boolean.
  **NOT AVAILABLE:** whether the template treats that string as true and so always enables the recon middleware (the
  Jinja test of a string is not in the sources).
- The `proxy-logging` and `versioned_writes` filters are defined but not in the proxy pipeline
  (`proxy-server.conf.j2:13,33-34,92-94`).

---

## 4. Manila

### 4.1 Plays

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| loadbalancer include | `ansible/site.yml:208-212` | loadbalancer | `manila` |
| **Apply role neutron** | `ansible/site.yml:590-608` | includes **`manila-share`** (`:603`) and `compute` (`:602`) | `neutron` |
| Apply role manila | `ansible/site.yml:714-725` | `manila-api`, `manila-data`, `manila-share`, `manila-scheduler`, `&enable_manila_True` | `manila` |

Default inventory: `manila-share` is a child of **`network`** (`ansible/inventory/multinode:363-364`). The other groups
are under `manila` (control) (`:170-171,357-368`). `openvswitch` children include `manila-share` (`:123-126`).

**Why manila-share is in the neutron play:** the agent host_in_groups include manila-share hosts.
- OVS agent, only with the generic backend:
  `(enable_manila_backend_generic | bool and inventory_hostname in groups['manila-share'])`
  (`ansible/roles/neutron/defaults/main.yml:35`). openvswitch db and vswitchd have the same condition
  (`ansible/roles/openvswitch/defaults/main.yml:11,27`).
- Linuxbridge agent: whenever `enable_manila` is set, **for any backend** (`neutron/defaults/main.yml:59`). This is an
  inconsistency.
- Generic-driver share servers are plugged with `OVSInterfaceDriver` (openvswitch) or `BridgeInterfaceDriver`
  (linuxbridge) (`templates/manila-share.conf.j2:75-79`).
- Ordering: the neutron play (`:590`) runs before manila (`:714`).

### 4.2 Services (`ansible/roles/manila/defaults/main.yml:2-49`)

| Service | Container | Notable |
|---|---|---|
| manila-api | `manila_api` | haproxy port 8786 (`all.yml:383`) |
| manila-scheduler | `manila_scheduler` | — |
| manila-share | `manila_share` | **privileged**, `/run:/run:shared`, `/lib/modules:ro` (`:35`, `:155-162`). Its handler adds `ipc_mode: host` (`handlers/main.yml:51-67`, `ipc_mode` at `:62`), which is not in the services dict and not compared by check-containers (`tasks/check-containers.yml:2-18`) |
| manila-data | `manila_data` | **privileged**, `/dev/:/dev/`, `/run:shared` (`:44`, `:175-182`) |

Backends (`:215-245`): generic, hnas, cephfsnative, cephfsnfs and, new in 2023.1, glusterfsnfs, each gated by
`enable_manila_backend_*` (`all.yml:704-708`, all `"no"`).

### 4.3 Task flow

- **deploy** (`tasks/deploy.yml:1-14`): clone (dev) → register (keystone `share` and `sharev2`,
  `defaults/main.yml:270-282`) → config → check-containers → bootstrap (DB, then `bootstrap_manila`,
  `tasks/bootstrap.yml:2-38`) → flush. The Ussuri step **`fix_cephfs_owner.yml` no longer exists**: the role has no such
  file, and `deploy.yml` ends at the flush.
- **reconfigure** = deploy (`tasks/reconfigure.yml:2`). **upgrade**: config → check-containers → bootstrap_service →
  flush (`tasks/upgrade.yml:1-9`).
- **`fix_cephfs_owner.yml` runs on every deploy/reconfigure**: true in Ussuri, **not in 2023.1** (no
  `fix_cephfs_owner.yml` under `ansible/roles/manila/tasks/`, and no task of the role mounts CephFS or passes
  `secret=`). The Ussuri security point (the keyring secret on the mount command line) therefore does not apply. With a
  CephFS backend, config now includes `external_ceph.yml` on manila-share hosts (`tasks/config.yml:15-18`), see 4.4.

### 4.4 Config (`tasks/config.yml`)

| Output | Chain | Notifies |
|---|---|---|
| ceph.conf and keyring (`external_ceph.yml:2-33`), only with `enable_manila_backend_cephfs_native` or `_cephfs_nfs` on manila-share hosts (`config.yml:15-18`) | `{{node_custom_config}}/manila/ceph.conf` (templated), `.../manila/{{ceph_manila_keyring}}` | Restart manila-share |
| config.json | `:43-54` | Restart `<svc>` |
| manila.conf (api, data, scheduler) | template → global.conf → manila.conf → `manila/<svc>.conf` → `manila/<host>/manila.conf` (`:56-75`) | Restart `<svc>` |
| manila-share manila.conf | `manila.conf.j2` **+** `manila-share.conf.j2` → global.conf → manila.conf → `{{node_custom_config}}/manila-share.conf` → manila/manila-share.conf → `manila/<host>/manila.conf` (`:77-99`) | Restart manila-share |
| policy | `:101-112`, **no `become`** | Restart `<svc>` |

### 4.5 Dependencies

- MariaDB (`manila.conf.j2:27-31`), RabbitMQ rpc (`:22`) and notify (`:50-56`), memcached (`:48`).
- manila-share.conf additionally loops over memcached 3× and holds **glance, cinder, nova and neutron service-user
  passwords** (`manila-share.conf.j2:8-70`).
- Ceph is external only: there is no ceph deployment role in 2023.1 (`ansible/roles/` has no `ceph` role; only
  `ceph-rgw`, which has "no container deployment" and only configures the load balancer,
  `ansible/roles/ceph-rgw/defaults/main.yml:3-4`). The config is supplied by the operator (`external_ceph.yml`).

### 4.6 Operationally notable

- Kolla does not create share types, the service image or networks (no such task under `ansible/roles/manila/tasks/`).
  `default_share_type = default_share_type` is hard-coded (`manila-share.conf.j2:6`) and
  `service_image_name = manila-service-image` (`:85`).
- The generic backend's service-instance credentials default to `manila`/`manila` (`defaults/main.yml:205-206`,
  `manila-share.conf.j2:83-84`).
- Endpoints use `kolla_internal_fqdn` and `kolla_external_fqdn` directly (`defaults/main.yml:193-194`).

---

## 5. Other roles that deploy containers onto `compute` hosts

Default multinode membership (compute ∈): collectd (`multinode:55-56`), telegraf (`:73-78`), hacluster-remote (`:83-84`,
new in 2023.1), monasca-agent (`:98-103`, a group that no 2023.1 play deploys, see 5.11), cyborg and cyborg-agent
(`:179-181,536-537`), iscsid (`:347-350`), ceilometer-compute and ceilometer-ipmi (`:513-517`), multipathd (`:563-564`),
zun-compute and zun-cni-daemon (`:639-643`), prometheus-node-exporter, prometheus-cadvisor and, new in 2023.1,
prometheus-libvirt-exporter (`:683-688,699-704,718-719`), masakari-instancemonitor (`:733-734`), ovn-controller-compute
(`:740-741`). The kuryr play targets `compute` directly (`site.yml:610-618`). There is **no `chrony`, `skydive-agent` or
`hyperv` group** in the 2023.1 `inventory/multinode`.

### 5.0 Summary table (compute-side)

| Role (enable flag, default) | Compute containers | Restart trigger (handler) | Config: per-host or global? | Data-plane / VM impact |
|---|---|---|---|---|
| ceilometer (`enable_ceilometer` no; ipmi `enable_ceilometer_ipmi` no, `all.yml:643-644`) | `ceilometer_compute` (privileged, `/run:shared`, `nova_libvirt` volume), `ceilometer_ipmi` | `handlers/main.yml:34-49`, `:51-65` | **Global**: rabbit rpc and notify, memcached | VM impact NOT AVAILABLE (`ceilometer_compute` runs only `ceilometer-polling`, `templates/ceilometer-compute.json.j2:2`) |
| iscsi (`enable_iscsid` derived, `all.yml:700`) | `iscsid` (privileged, ipc host, `/dev`, `/run:shared`, `/sys/kernel/config`, `iscsi_info:/etc/iscsi`) | `handlers/main.yml:2-17` | Per-host (config.json only) | **Risk topic**, outcome NOT AVAILABLE; see 5.2 |
| multipathd (`enable_multipathd` no) | `multipathd` (privileged, ipc host) | `handlers/main.yml:2-16` | Per-host (role template or operator override) | **Risk topic**, outcome NOT AVAILABLE; see 5.3 |
| collectd (no) | `collectd` (privileged, `/sys`, `/dev` ro) | `handlers/main.yml:2-16` | Per-host | none |
| telegraf (no) | `telegraf` (pid host, docker.sock ro) | `handlers/main.yml:2-19` | **Global**: influxdb hosts | none |
| prometheus (no) | `prometheus_node_exporter` (pid host, `/:/host:ro,rslave`), `prometheus_cadvisor` (`/var/run:rw`, `/var/lib/docker:ro`), `prometheus_libvirt_exporter` (new: `/run/libvirt:ro`; enabled with prometheus when nova uses kvm or qemu, `all.yml:1138`) | `handlers/main.yml:17-32`, `:78-92`, `:154-168` | Per-host on compute. The **server** config lists every compute | none on compute; prometheus_server restarts when computes are added |
| masakari (no) | `masakari_instancemonitor` (privileged) | `handlers/main.yml:34-48` | Per-host | none directly; see 5.6 |
| hacluster (`enable_hacluster` = `enable_masakari_hostmonitor` = `enable_masakari`, `all.yml:671,712`) | `hacluster_pacemaker_remote` (ipc host), new in 2023.1 | `hacluster/handlers/main.yml:36-50` | Per-host (shared Pacemaker authkey) | NOT AVAILABLE; see 5.15 |
| zun (no) | `zun_compute` (privileged, `/var/lib/docker`, `/dev`, `/run:shared`), `zun_cni_daemon` (privileged) | `handlers/main.yml:40-57`, `:59-76`, plus a loopback copy at `:78-88` | **Global**: rabbit rpc, memcached ×2, **DB creds** | container workloads, outcome NOT AVAILABLE; see 5.7 |
| kuryr (no) | `kuryr` (privileged, NET_ADMIN, `/run:shared`, `/usr/lib/docker`) | `handlers/main.yml:2-18` | Per-host | docker network ops, outcome NOT AVAILABLE; see 5.8 |
| cyborg (no) | `cyborg_agent` (privileged) | `handlers/main.yml:36-51` | **Global**: rabbit rpc and notify, memcached, **DB creds**, placement and nova creds | none |
| skydive | **no role in 2023.1** (see 5.10) | – | – | – |
| monasca | **no agent deployed in 2023.1** (see 5.11) | – | – | – |
| chrony | **no role in 2023.1** (see 5.12) | – | – | – |
| nova-hyperv | **no role in 2023.1** (see 5.13) | – | – | – |
| (cross-ref) ovn-controller | `ovn_controller` | ovn-controller role | **Global**: `ovn-remote` = SB host list | out of scope |

### 5.1 ceilometer

- Play: `ansible/site.yml:739-750`, hosts central, notification, compute, ipmi. The Ussuri
  `vars_files: roles/panko/defaults/main.yml` is gone (no panko role in 2023.1).
- Services: `ansible/roles/ceilometer/defaults/main.yml:2-35`. Compute volumes include `/run/:/run/:shared` and
  `{{ ceilometer_libvirt_volume }}:/var/lib/libvirt` (`:135-143`), where `ceilometer_libvirt_volume` is `nova_libvirt`
  with the libvirt container and `/var/lib/libvirt` otherwise (`:158`). ceilometer-ipmi has no `/dev` mount and is not
  privileged (`:28-35,144-150`). **NOT AVAILABLE:** whether local IPMI (`/dev/ipmi0`) is reachable from it.
- Flow: deploy = register → config → check-containers → clone → bootstrap → flush (`tasks/deploy.yml`). `bootstrap.yml`
  has a `TODO(Jeffrey4l): fix idempotent` comment and **always runs** the `bootstrap_ceilometer` container
  (ceilometer-upgrade, with `CEILOMETER_DATABASE_TYPE` = `gnocchi` when gnocchi is enabled, `defaults/main.yml:192`),
  delegated to `groups['ceilometer-notification'][0]` (`tasks/bootstrap_service.yml:2-22`).
- Config: `ceilometer.conf` merge chain at `tasks/config.yml:196-214`. The template carries
  `transport_url = rpc_transport_url` (`templates/ceilometer.conf.j2:6`), `notify_transport_url` (`:36`) and
  `memcache_servers` over `groups['memcached']` (`:59`). The same file is rendered for ceilometer-compute on **every
  compute**, so a rabbitmq or memcached membership change restarts `ceilometer_compute` on every compute.
- Scaling oddities:
  - Several `delegate_to: localhost` stat/find tasks **lack `run_once`**: custom meters (`:15-31`), polling.yaml
    (`:106-110`), gnocchi_resources (`:133-137`), event_definitions (`:216-220`), event_pipeline (`:255-259`), pipeline
    (`:293-297`). That is roughly 6 local tasks per host, multiplied by the compute count.
  - "Clean default folder for dynamic pollsters definitions" has **no `become` and no host condition** (`:77-80`). It
    deletes `/etc/kolla/ceilometer-central/pollsters.d/` on every run, then recreates and recopies it (`:82-104`). **NOT
    AVAILABLE:** whether ceilometer-central then restarts on every deploy/reconfigure when `pollsters.d` exists, and
    whether the delete, having no become, hits permission errors for non-root ansible users (`config_owner_user: root`,
    `all.yml:20`).
- Precheck: fails unless gnocchi **or** `enable_ceilometer_prometheus_pushgateway` is enabled
  (`tasks/precheck.yml:8-15`).

### 5.2 iscsi (iscsid, tgtd)

- Play: `ansible/site.yml:417-426`, hosts `iscsid`, `tgtd`, `&enable_iscsid_True`.
- `enable_iscsid` is `enable_cinder and enable_cinder_backend_iscsi` (`ansible/group_vars/all.yml:700`; Ussuri also
  counted `enable_ironic`), and `enable_cinder_backend_iscsi` defaults to `enable_cinder_backend_lvm` (`:653-654`).
- Per-host enablement (`ansible/roles/iscsi/defaults/main.yml:61-72`): iscsid runs on compute, cinder-backup or
  cinder-volume hosts only when cinder and the iscsi backend are enabled, or on ironic-conductor hosts with ironic. tgtd
  runs only with the LVM backend and `cinder_target_helper == tgtadm`. Since the play only targets `&enable_iscsid_True`
  hosts, ironic without the cinder iSCSI backend gets no iscsid.
- Containers (`:2-20`): both privileged, `ipc_mode: host`, with volumes `/dev`, `/run:shared`, `/lib/modules:ro`,
  `/sys/kernel/config:/configfs`, and, for iscsid only, `iscsi_info:/etc/iscsi` (`:39-57`). The Ussuri
  `cinder:/var/lib/cinder` and `/sys/fs/cgroup` mounts are gone.
- Config: config.json only. The iscsid command is `iscsid -d 8 -f` (`templates/iscsid.json.j2:2`), which is **debug
  level 8, very verbose**. So the container restarts only on config.json, image, volume or dimension change, in practice
  **upgrade/pull of a new tag**. The flow for deploy, upgrade and reconfigure is config-host (loads `configfs`,
  `tasks/config-host.yml:1-10`) → config → check-containers → flush (`tasks/deploy.yml`, `upgrade.yml` = deploy).
- **Host interaction:** bootstrap-servers **removes host `open-iscsi`** on Debian/Ubuntu always, and
  `iscsi-initiator-utils` on RedHat only when `enable_nova_libvirt_container` (ansible-collection-kolla
  `roles/packages/defaults/main.yml:24-33`). **NOT AVAILABLE:** whether computes then have no iscsid at all when
  `enable_iscsid` is false (no cinder iSCSI backend, for example a third-party iSCSI SAN).
- **VM impact (NOT AVAILABLE):** whether iSCSI sessions survive an iscsid restart, and whether session recovery or
  re-login after a path or portal failure, and os-brick attach/detach from nova-compute, fail or stall while iscsid is
  down. The `iscsi_info` named volume holds the initiator IQN (kolla `docker/iscsid/extend_start.sh:3-7`). **NOT
  AVAILABLE:** whether recreating the volume (for example after `destroy`) changes the IQN and breaks array ACLs.
- **tgtd restart (consequences NOT AVAILABLE):** the command is only `tgtd -d 1 -f --iscsi portal=...` with empty
  `config_files` (`templates/tgtd.json.j2:2-3`), and the image adds no start script of its own. It only inserts
  `include /var/lib/cinder/volumes/*` into `/etc/tgt/targets.conf` (kolla `docker/tgtd/Dockerfile.j2:19`), and nothing
  runs `tgt-admin` at start. In 2023.1 the tgtd container **no longer mounts the `cinder` volume**
  (`ansible/roles/iscsi/defaults/main.yml:49-57`), so `/var/lib/cinder/volumes` inside it is not the cinder-volume data.
  **NOT AVAILABLE:** whether tgtd keeps its target table only in memory, so that a restart drops every exported LVM
  target and its sessions until cinder-volume (for example at its own restart) re-creates them, and whether I/O to
  attached LVM volumes stalls or fails meanwhile. The precheck now fails on RedHat-family hosts when tgtd is enabled
  (`tasks/precheck.yml:29-35`). See [Kolla images §5](../../concepts/kolla-images.md#5-per-image-start-behaviour).
- Precheck oddity: it checks that `iscsi_port` 3260 is free on the iscsid hosts (`tasks/precheck.yml:17-27`), but 3260
  is the **target** (tgtd) port.

### 5.3 multipathd

- Play: `ansible/site.yml:428-436`. Default `enable_multipathd: "no"` (`all.yml:714`). No role has a meta dependency on
  common in 2023.1.
- Container: privileged, ipc host, with `/dev`, `/run:shared`, `/lib/modules:ro`, `/sys/kernel/config:/configfs`
  (`ansible/roles/multipathd/defaults/main.yml:2-29`). In 2023.1 it **no longer mounts `iscsi_info` or `cinder`**. There
  are still **no `dimensions`**.
- Config: `multipath.conf` is now **first-found** from `{{node_custom_config}}/multipath/<host>/multipath.conf`, then
  `{{node_custom_config}}/multipath.conf`, then the role template (`tasks/config.yml:28-44`). The role template is
  `user_friendly_names no`, `find_multipaths yes`, `skip_kpartx yes`, and an empty blacklist
  (`templates/multipath.conf.j2:1-8`). An override no longer requires editing the role.
- The `dm-multipath` module is loaded by config-host (`tasks/config-host.yml:1-7`).
- Restart (handler `:2-16`): on config.json or multipath.conf change, or on image/volume change.
- **VM impact (NOT AVAILABLE):** whether dm maps persist across a restart, whether path checking and failback pause
  while multipathd is down, and whether a path failure in that window causes I/O errors or queueing depending on
  `no_path_retry`. Restarts run in the same handler step on all notified multipathd hosts of the batch (ansible-core
  2.14.18 `lib/ansible/plugins/strategy/__init__.py:934-942`, `lib/ansible/plugins/strategy/linear.py:118-123,234-243`),
  and with serial 0 by default the batch is every host (`lib/ansible/executor/playbook_executor.py:300-302`).

### 5.4 collectd and telegraf

- collectd: play `site.yml:343-351`. Privileged, `/sys` and `/dev` ro (`ansible/roles/collectd/defaults/main.yml:2-29`).
  collectd.conf is first-found (host → global → role template), with no merge (`tasks/config.yml:41-58`). The default
  sends to `{{ 'api' | kolla_address }}:{{ collectd_udp_port }}`, i.e. its own host (`templates/collectd.conf.j2:9-11`),
  where telegraf's `socket_listener` receives it if telegraf is enabled
  (`ansible/roles/telegraf/templates/telegraf.conf.j2:29-35`). Per-host only.
- telegraf: play `site.yml:363-371`. `pid_mode: host`, `/proc` and `/sys` ro, `/var/run/docker.sock:ro`
  (`ansible/roles/telegraf/defaults/main.yml:2-10,20-27`). telegraf.conf is first-found, not merged
  (`tasks/config.yml:32-48`). It **loops over `groups['influxdb']`** (`telegraf.conf.j2:14-24`), so adding or removing
  an influxdb host restarts telegraf on every host. The Ussuri chrony, zookeeper and kafka inputs are gone; the haproxy
  and elasticsearch inputs now test the `loadbalancer` and `opensearch` groups (`telegraf.conf.j2:50,58`).
  - **Latent bug:** the "Copying over telegraf plugin files" task tests `item.value.enabled` inside a `with_fileglob`
    loop of path strings (`tasks/config.yml:50-64`). The glob is currently empty because `templates/config/` does not
    exist, but adding files there would break the task.
  - check-containers does not pass the `HOST_PROC`/`HOST_SYS` env, while the handler does (`handlers/main.yml:12-14`).

### 5.5 prometheus (node-exporter, cadvisor, libvirt-exporter)

- Play: `site.yml:397-415`. Hosts include `prometheus-node-exporter`, `prometheus-cadvisor` and
  `prometheus-libvirt-exporter`, which contain compute (`multinode:683-688,699-704,718-719`).
- node_exporter: `pid_mode: host`, `/:/host:ro,rslave`, listens on `api_interface_address:9100`
  (`ansible/roles/prometheus/defaults/main.yml:17-24,245-250`; `templates/prometheus-node-exporter.json.j2:2`;
  `all.yml:475`).
- cadvisor: `/var/run:/var/run:rw` (**this includes docker.sock read-write, which makes the container
  root-equivalent**), `/var/lib/docker:ro`, `/sys:ro`, plus `/:/rootfs:ro` and `/dev/disk:ro`. The command is
  `/opt/cadvisor --port={{ prometheus_cadvisor_port }}` (18080, `all.yml:481`) with **no listen address**
  (`defaults/main.yml:256-265`; `templates/prometheus-cadvisor.json.j2:2`). **NOT AVAILABLE:** whether it listens on all
  interfaces.
- libvirt-exporter (new in 2023.1): `/run/libvirt:/run/libvirt:ro`, listening on `api_interface_address:9177`
  (`defaults/main.yml:115-121,287-291`; `templates/prometheus-libvirt-exporter.json.j2:2`; `all.yml:483,1138`).
- Compute-side config is config.json only (per-host). The **server** config `prometheus.yml.j2` loops over
  node-exporter, cadvisor, libvirt-exporter and other groups (`templates/prometheus.yml.j2:23-190`). Adding a compute
  changes prometheus.yml and restarts `prometheus_server` (`tasks/config.yml:79-98`), and rendering it needs facts for
  every compute.
- Scaling: "Find prometheus host config overrides" runs `delegate_to: localhost` **per host**, explicitly
  `run_once: false` (`tasks/config.yml:68-77`), even on hosts that are not prometheus servers.

### 5.6 masakari (monitors)

- Play: `site.yml:936-947`. Hosts are masakari-api, masakari-engine, `masakari-hostmonitor` (= control) and
  `masakari-instancemonitor` (= compute) (`multinode:730-734`).
- `masakari-instancemonitor` and, **new in 2023.1, `masakari-hostmonitor`** are deployed
  (`ansible/roles/masakari/defaults/main.yml:28-43`), both enabled with `enable_masakari` (`all.yml:711-712`). The
  Ussuri statement "there is no hostmonitor or processmonitor, so Kolla-deployed masakari cannot detect compute host
  failure on its own" **no longer holds for the hostmonitor**: it runs on the control hosts with
  `restrict_to_remotes = True` and `pacemaker_node_type = cluster` (`templates/masakari-monitors.conf.j2:21-43`), and
  the computes run `hacluster_pacemaker_remote` (5.15). There is still no processmonitor (no `processmonitor` in
  `ansible/`). **NOT AVAILABLE:** whether and how fast the hostmonitor detects a failed compute (masakari-monitors and
  Pacemaker code are not in the sources).
- Config: `masakari-monitors.conf` merge chain (`tasks/config.yml:88-110`). It is per-host and has no rabbit, memcached
  or DB. Libvirt is reached over `connection_uri = "qemu+tcp://{{ migration_interface_address }}/system"`
  (`templates/masakari-monitors.conf.j2:16-19`).
  - **Default libvirt auth (outcome NOT AVAILABLE):** nova-cell defaults to `libvirt_enable_sasl: true`
    (`ansible/roles/nova-cell/defaults/main.yml:562`), giving `auth_tcp = "sasl"`
    (`ansible/roles/nova-cell/templates/libvirtd.conf.j2:10-13`). **Changed in 2023.1:** `auth.conf` with the SASL
    credentials is now also copied to masakari-instancemonitor when `libvirt_enable_sasl`
    (`ansible/roles/masakari/tasks/config.yml:141-157`) and placed at `/var/lib/masakari/.config/libvirt/auth.conf`
    (`templates/masakari-instancemonitor.json.j2:9-15`). With `libvirt_tls: true`, `listen_tcp = 0`
    (`libvirtd.conf.j2:1-3`; default `libvirt_tls: false`, `nova-cell/defaults/main.yml:545`). **NOT AVAILABLE:**
    whether masakari-instancemonitor connects to libvirt with these defaults.
- **Bug:** "Copying over existing policy file" uses `dest: "{{ node_config_directory }}/{{ item }}/..."` with
  `with_dict` (`tasks/config.yml:34-47`, dest at `:37`). When a custom policy exists, the dest path renders a dict.
- Bootstrap (DB sync) runs on every deploy/reconfigure (`tasks/deploy.yml`, `bootstrap_service.yml`).

### 5.7 zun (zun-compute, zun-cni-daemon)

- Play: `site.yml:898-909`. The precheck requires kuryr (`ansible/roles/zun/tasks/precheck.yml:52-58`).
- Containers (`defaults/main.yml:41-58,179-198`): zun_compute is privileged with `/run:shared`, `/usr/lib/docker`,
  `/var/lib/docker`, `/dev`, `/lib/modules:ro`, `iscsi_info:/etc/iscsi` when iscsid is enabled, and
  `/var/lib/zun:shared` when `zun_configure_for_cinder_ceph`. zun_cni_daemon is privileged.
- Config: `zun.conf` is rendered for **all** zun services including compute (`tasks/config.yml:56-74`). It contains
  `transport_url = rpc_transport_url` (`templates/zun.conf.j2:10`), the full **`[database] connection` with password**
  (`:19-20`), memcached ×2 when `enable_memcached` (`:44,67`), and `docker api_url = tcp://<api_ip>:2375` (`:119-122`).
  - The docker daemon on zun-compute hosts is opened on TCP 2375 **without TLS or auth** by bootstrap-servers when
    `docker_configure_for_zun` is set (`ansible/group_vars/all.yml:123-124`; ansible-collection-kolla
    `roles/docker/templates/docker_systemd_service.j2:13`). `docker_zun_config.cluster-store` loops over
    `groups['etcd']` and is merged into `/etc/docker/daemon.json` on zun-compute hosts (`all.yml:125-126`;
    ansible-collection-kolla `roles/docker/tasks/config.yml:28-44`).
- Handlers: check-containers notifies `"<svc> container changed"`, and handlers `listen` on that as well as being named
  "Restart <svc> container" (`tasks/check-containers.yml:17-21`; `handlers/main.yml:40-76`). On a zun-cni-daemon
  container change, the loopback binary is copied to the host `/opt/cni/bin` (`:78-88`).
- **NOT AVAILABLE:** whether restarting zun_compute stops user containers, and whether a zun_cni_daemon restart breaks
  CNI operations during the window.

### 5.8 kuryr

- Play: `site.yml:610-618`. Hosts are **`compute`** directly, and the service group is hard-coded to `compute`
  (`ansible/roles/kuryr/defaults/main.yml:10-21`).
- The container is privileged with `cap_add: NET_ADMIN`, `/run:shared` and `/usr/lib/docker` (`:16-19,50-58`).
  `kuryr.spec` is placed into `/usr/lib/docker/plugins/kuryr/` (`templates/kuryr.json.j2:10-15`).
- Config is per-host: `kuryr_uri` uses its own api IP (`templates/kuryr.conf.j2:2`, `defaults/main.yml:95`), and
  kuryr.conf has no rabbit, memcached or DB (`templates/kuryr.conf.j2:1-29`).
- Keystone user registration runs from the compute-host play (`tasks/register.yml`, `tasks/deploy.yml:2`).
- **NOT AVAILABLE:** whether docker network create/attach fails while kuryr is restarting, and whether existing veth
  wiring persists.

### 5.9 cyborg (agent)

- Play: `site.yml:777-787` uses **`serial: '{{ serial|default("0") }}'`** (`:784`), not `kolla_serial`. `ANSIBLE_SERIAL`
  is therefore ignored for cyborg on reconfigure and upgrade. This is an **oddity**, still present in 2023.1.
- `cyborg-agent` runs on compute and is privileged (`ansible/roles/cyborg/defaults/main.yml:11-19`).
- `cyborg.conf` is rendered for all services (`tasks/config.yml:65-83`). It contains DB connection credentials
  (`templates/cyborg.conf.j2:12-15`), placement service credentials (`:34-44`), and in 2023.1 nova service credentials
  (`:46-56`), rabbit rpc and notify (`:6,64`) and memcached (`:21`). **Global, and it carries DB, placement and nova
  credentials on compute.**
- **Bugs and oddities:**
  - `cyborg_services` has **no `haproxy` key** (`defaults/main.yml:2-27`), so `loadbalancer.yml` configures nothing. Yet
    the keystone endpoints point to `kolla_internal_fqdn:6666` (`defaults/main.yml:144-145`, `all.yml:309`). **NOT
    AVAILABLE:** whether that VIP endpoint is reachable.
  - The Ussuri service type `"cyborg"` is now **`"accelerator"`** (`defaults/main.yml:166-172`), so the Ussuri question
    whether Nova expects `accelerator` no longer applies.

### 5.10 skydive (agent)

**No longer exists in 2023.1.** `ansible/roles/` has no `skydive` role, `site.yml` has no skydive play, and
`inventory/multinode` has no `skydive-agent` or `skydive-analyzer` group (a grep for `skydive` in `ansible/` finds
nothing). The Ussuri points (privileged agent with OVS socket and netns, cloud admin credentials in
`skydive-agent.conf`, analyzer config listing every agent host) do not apply.

### 5.11 monasca (agents)

**No monasca agent is deployed in 2023.1.** `site.yml` has no monasca play; `ansible/roles/monasca` holds only
`defaults/main.yml` and `tasks/cleanup.yml`, which stops and removes containers of **disabled** monasca services and
their config directories (`ansible/roles/monasca/tasks/cleanup.yml:2-20`), and it is applied only by
`ansible/monasca_cleanup.yml:1-12`. The `monasca-agent*` groups are still in `inventory/multinode` (`:98-103,410-417`),
and `monasca_agent_forwarder_port`/`monasca_agent_statsd_port` are still defined (`all.yml:414-415`), but no 2023.1
template renders an agent config. The Ussuri points (collector `pid_mode: host`, forwarder password with
`non_local_traffic`, Grafana calls from `post_config.yml`) do not apply.

### 5.12 chrony

**No longer exists in 2023.1** (see [Chrony](../../components/chrony.md)): `ansible/roles/` has no `chrony` role,
`site.yml` has no chrony play, and `inventory/multinode` has no `chrony` or `chrony-server` group. There is no chrony
container, `chrony.conf`, VIP time source, `external_ntp_servers` default or `makestep` setting to restart or
reconfigure on computes. Time sync is left to the host; `kolla-ansible prechecks` checks it
(`prechecks_enable_host_ntp_checks`, see the Chrony page). **NOT AVAILABLE:** which time source the hosts use.

### 5.13 nova-hyperv

**No longer exists in 2023.1** (the Ussuri role announced its removal in Victoria): `ansible/roles/` has no
`nova-hyperv` role, `site.yml` has no hyperv play, and `inventory/multinode` has no `hyperv` group (a grep for `hyperv`
in `ansible/` finds only unrelated comments and `hypervisor_inspector`). The Ussuri bugs (no
`upgrade.yml`/`deploy-containers.yml`, undefined `nova_hyperv_services`, meta dependency on `common` for Windows hosts)
do not apply.

### 5.14 Cross-reference: ovn-controller on compute

In 2023.1 this is the `ovn-controller` role (Ussuri: `ovn`). Its `setup-ovs.yml` sets
`external_ids:ovn-remote={{ ovn_sb_connection }}` in the local OVSDB through `kolla_toolbox openvswitch_db`
(`ansible/roles/ovn-controller/tasks/setup-ovs.yml:13-40`, `ovn-remote` at `:33`), which is a loop over
`groups['ovn-sb-db']` (`all.yml:458`). The task runs on every deploy (`tasks/deploy.yml:6`). A
neutron-ovn-metadata-agent ini on compute also lists the NB and SB DBs
(`ansible/roles/neutron/templates/neutron_ovn_metadata_agent.ini.j2:17-18`).

### 5.15 hacluster (pacemaker-remote), new in 2023.1

- Play: `site.yml:620-629`, hosts `hacluster` (= control) and `hacluster-remote` (= compute, `multinode:80-84`),
  `&enable_hacluster_True`. `enable_hacluster` defaults to `enable_masakari_hostmonitor`, which defaults to
  `enable_masakari` (`all.yml:671,712`): **enabling masakari puts a `hacluster_pacemaker_remote` container on every
  compute.**
- Container: `hacluster_pacemaker_remote`, `ipc_mode: host` (`ansible/roles/hacluster/defaults/main.yml:26-33`). Its
  config is config.json and the Pacemaker `authkey`, which the role generates once on the deploy host with
  `dd if=/dev/urandom` when it is missing (`tasks/bootstrap.yml:36-41`) and copies to every remote
  (`tasks/config.yml:81-96`); a change of either restarts the container (`handlers/main.yml:36-50`).
- Each compute is added as a Pacemaker `remote` resource named after its `nodename`, with its api address, by a
  `cibadmin --modify` delegated to the first `hacluster` host (`tasks/bootstrap_service.yml:10-32`).
- **NOT AVAILABLE:** what a `hacluster_pacemaker_remote` restart or a compute removal does to the Pacemaker cluster and
  to masakari host-failure handling (Pacemaker semantics are not in the sources); no task removes the `remote` resource
  of a deleted compute (no `cibadmin --delete` in `ansible/roles/hacluster/`).

---

## 6. Per-cluster host lists in templates

### 6.1 grep `for host in groups` over `ansible/roles/*/templates`

Memcached loops (`groups['memcached']`) appear in: aodh, barbican, blazar, **ceilometer**, cinder, cloudkitty,
**cyborg**, designate, freezer, glance, gnocchi, heat (×2), horizon, ironic (×2), keystone (×2), magnum, manila (×4),
masakari (api/engine only), mistral, murano, **neutron**, nova (×2), octavia (×2), placement (×2), sahara, senlin,
solum, swift (×2), tacker, venus, vitrage (×2), watcher, **zun (×2)** (33 roles in 2023.1; the Ussuri congress, karbor,
panko, qinling and searchlight roles no longer exist).

Other group loops:
- certificates `tls-backend` and `compute`; designate `designate-backend-bind9`/`designate-worker`/`designate-mdns`;
  opensearch `opensearch`; haproxy-config backends (`groups[host_group]`); loadbalancer (keepalived) `loadbalancer`;
  keystone fernet-push `keystone`; galera `mariadb` (per shard group); hacluster corosync `hacluster`
  (`hacluster/templates/hacluster_corosync.conf.j2:13`); octavia `octavia-health-manager`; prometheus.yml (12 groups,
  including `prometheus-node-exporter`, `prometheus-cadvisor` and `prometheus-libvirt-exporter`); rabbitmq; **telegraf**
  `influxdb`. The Ussuri elasticsearch, mongodb, nova-hyperv, skydive, storm and zookeeper template loops are gone (no
  such templates in 2023.1).
- Non-loop group references: `cinder.conf.j2:20` and `nova/templates/nova.conf.j2:62` use
  `groups['glance-api'] | length` (the nova-cell `nova.conf.j2` now has `num_retries = 3`, `:109`). Cinder coordination
  no longer uses `groups['etcd'][0]`: it is `redis_connection_string` or an etcd URL on `kolla_internal_fqdn`, depending
  on `cinder_coordination_backend` (`cinder.conf.j2:245-252`, `group_vars/all.yml:951`).
- Host lists defined as **variables** rather than template loops: `rpc_transport_url`/`notify_transport_url`
  (`all.yml:212,222`), `nova_cell_rpc/notify_transport_url` (`ansible/roles/nova-cell/defaults/main.yml:206-207`, groups
  default to `om_rpc_group` at `:191,200`), `ovn_nb/sb_connection` (`all.yml:457-458`), and
  `docker_zun_config.cluster-store` (etcd, `all.yml:125-126`).

### 6.2 Config files on COMPUTE hosts that embed per-cluster host lists

| File on compute (`/etc/kolla/...`) | Container restarted by its handler | Lists embedded | Evidence |
|---|---|---|---|
| `nova-compute/nova.conf` (and the other nova-cell compute services) | nova_compute, etc. (cross-ref) | cell rabbit rpc and notify | `nova-cell/templates/nova.conf.j2:37,184`; `nova-cell/defaults/main.yml:206-207` |
| `neutron-openvswitch-agent/neutron.conf` (also linuxbridge, ovn-metadata, ovn-agent) | neutron agents (cross-ref) | rabbit rpc and notify, **memcached** | `neutron/templates/neutron.conf.j2:58,125,128`; rendered for agent services at `neutron/tasks/config.yml:87-122` |
| `neutron-ovn-metadata-agent/neutron_ovn_metadata_agent.ini` | ovn metadata agent (cross-ref) | OVN NB and SB DB hosts | `neutron_ovn_metadata_agent.ini.j2:17-18` |
| OVS DB `external_ids:ovn-remote` (not a file) | none (live setting) | OVN SB hosts | `ovn-controller/tasks/setup-ovs.yml:13-40` |
| `ceilometer-compute/ceilometer.conf`, `ceilometer-ipmi/ceilometer.conf` | ceilometer_compute, ceilometer_ipmi | rabbit rpc and notify, **memcached** | `ceilometer.conf.j2:6,36,59` |
| `zun-compute/zun.conf`, `zun-cni-daemon/zun.conf` | zun_compute, zun_cni_daemon | rabbit rpc, **memcached ×2** | `zun.conf.j2:10,44,67` |
| `cyborg-agent/cyborg.conf` | cyborg_agent | rabbit rpc and notify, **memcached** | `cyborg.conf.j2:6,21,64` |
| `skydive-agent/skydive.conf` | – | **no skydive in 2023.1** (5.10) | – |
| `telegraf/telegraf.conf` | telegraf | influxdb hosts | `telegraf.conf.j2:14-24` |
| `/etc/docker/daemon.json` (zun-compute, bootstrap-servers only) | dockerd (effect on the host's containers NOT AVAILABLE) | etcd hosts | `all.yml:125-126`; ansible-collection-kolla `roles/docker/tasks/config.yml:28-44` |
| Windows `nova.conf` and `neutron_hyperv_agent.conf` (hyperv group) | – | **no nova-hyperv in 2023.1** (5.13) | – |

Compute-side files with **no** cluster lists (per-host only): iscsid and tgtd config.json, multipath.conf,
collectd.conf, node-exporter, cadvisor and libvirt-exporter config.json, masakari-monitors.conf, the
hacluster-pacemaker-remote config.json and authkey, kuryr.conf, and the common/fluentd outputs (these use
`elasticsearch_address` and `opensearch_address`, which default to the internal FQDN, `all.yml:793`;
`common/templates/conf/output/01-es.conf.j2:5`, `03-opensearch.conf.j2:5`).

**Implication (consequence NOT AVAILABLE):** adding or removing a host in `rabbitmq` or `memcached` (normally
controllers), then running deploy or reconfigure across the fleet:
- re-templates the files above on **every compute**;
- fires `recreate_or_restart_container` for ceilometer_compute, ceilometer_ipmi, zun_compute, zun_cni_daemon,
  cyborg_agent, the neutron agents, nova_compute (cross-ref) and others;
- runs those restarts in the same handler step on all notified hosts of the batch (ansible-core 2.14.18
  `lib/ansible/plugins/strategy/__init__.py:934-942`, `lib/ansible/plugins/strategy/linear.py:118-123,234-243`); with
  the default `kolla_serial=0` the batch is every host (`lib/ansible/executor/playbook_executor.py:300-302`). **NOT
  AVAILABLE:** whether this causes a fleet-wide reconnect storm on RabbitMQ.

Rendering each of these files also requires facts (`kolla_address(host)`) for every host in `rabbitmq` and `memcached`
(`kolla_ansible/kolla_address.py:56-100`). This matters for `--limit` runs (cross-ref gather-facts.yml).
Conversely, **adding a compute** changes non-compute configs: prometheus.yml (prometheus_server restart,
`prometheus.yml.j2:31,76,159`) and, with masakari, the Pacemaker CIB (a new `remote` resource, 5.15). The Ussuri
skydive-analyzer.conf case is gone.

---

## 7. Consolidated bugs and oddities

Status against 2023.1 in each item.

1. Swift `stop.yml:23-31`: account-auditor guard checks `swift_object_auditor`. Still present.
2. Swift precheck checks rsync port 873, but rsyncd uses 10873 (`swift/tasks/precheck.yml:86-95` vs `all.yml:544`).
   Still present.
3. Swift `{% if enable_swift_recon %}` without `| bool` against the string `"no"` (`account.conf.j2:15`, etc.;
   `all.yml:750`). Still present. **NOT AVAILABLE:** whether recon is then always on.
4. Swift deploy never restarts on config or ring change (no notify anywhere; no-op handler at
   `swift/handlers/main.yml:2-4`). Reconfigure fails if any swift container is down (`reconfigure.yml:32-41`). The
   "rolling" upgrade stops all storage at once (`rolling_upgrade.yml:31-38`). All still present.
5. Octavia: `heartbeat_key = insecure` is still hard-coded (`octavia.conf.j2:80`). The amp network, secgroup and flavor
   are now filled in by default from the resources that `octavia_auto_configure` creates, and stay unset with no
   precheck only when it is off (`octavia.conf.j2:90-108`, `all.yml:1228`). The upgrade **no longer** removes the
   octavia admin role on the admin project (`octavia/tasks/upgrade.yml:1-9`). The HM precheck still uses
   `api_interface_address` (`precheck.yml:29-38`). The CA private key is still copied to 3 services
   (`config.yml:120-171`).
6. Manila: the CephFS secret on the command line on every deploy is **gone** (no `fix_cephfs_owner.yml` in 2023.1).
   Policy copy still has no `become` (`manila/tasks/config.yml:101-112`). Service-instance password still defaults to
   `manila` (`defaults/main.yml:206`). Neutron host_in_groups for manila-share are still asymmetric (OVS: generic only,
   `neutron/defaults/main.yml:35`; LB: any backend, `:59`).
7. Masakari: policy-file dest still uses a dict `item` (`masakari/tasks/config.yml:37`). A hostmonitor **now exists**
   (5.6, 5.15); there is still no processmonitor. instancemonitor uses qemu+tcp, and **now receives** the SASL
   `auth.conf` when SASL is on (`masakari/tasks/config.yml:141-157`; `masakari-monitors.conf.j2:18`;
   `nova-cell/defaults/main.yml:562`).
8. Cyborg: the play still uses `serial` instead of `kolla_serial` (`site.yml:784`). There is still no haproxy entry but
   endpoints are on the VIP (`cyborg/defaults/main.yml:2-27,144-145`). The keystone service type is **now
   `accelerator`** (`:166-172`). DB credentials (and placement and nova credentials) are on compute.
9. Telegraf: `item.value.enabled` in a `with_fileglob` loop (`telegraf/tasks/config.yml:50-64`). Still present.
10. Ceilometer: pollsters dir deleted every run without become (`ceilometer/tasks/config.yml:77-80`). Many localhost
    stats lack `run_once`. The bootstrap is explicitly non-idempotent (`tasks/bootstrap.yml:2`). All still present.
11. iscsid runs at debug `-d 8` (`iscsi/templates/iscsid.json.j2:2`). The precheck tests port 3260 on iscsid hosts
    (`iscsi/tasks/precheck.yml:17-27`). Both still present.
12. multipathd has no meta and no dimensions (`multipathd/defaults/main.yml:2-10`); the "no config override" part is
    **fixed** in 2023.1 (first-found override, `multipathd/tasks/config.yml:28-44`).
13. nova-hyperv lacks `upgrade.yml` and `deploy-containers.yml`, and references the undefined `nova_hyperv_services`:
    **does not apply**, the role does not exist in 2023.1 (5.13).
14. Security spread onto compute: cloud admin credentials (skydive): **gone**, no skydive in 2023.1; DB credentials (zun
    `zun.conf.j2:19-20`, cyborg `cyborg.conf.j2:12-15`); unauthenticated docker TCP 2375 for zun (`all.yml:124`);
    cadvisor with rw `/var/run` (docker.sock) (`prometheus/defaults/main.yml:262`); default chrony to public pool:
    **gone**, no chrony in 2023.1 (5.12). New in 2023.1: the shared Pacemaker `authkey` on every compute when masakari
    is enabled (`hacluster/tasks/config.yml:81-96`).
15. Barbican and other bootstraps (octavia, manila, ceilometer, masakari, zun, cyborg) re-run their DB sync container on
    every deploy/reconfigure (bootstrap containers are auto-removed, `kolla_docker.py:304`). Still present.

## 8. NOT AVAILABLE list

- NOT AVAILABLE: whether the swift containers serve the new rings once `reconfigure` has restarted them. A changed ring
  file makes `--check` return rc 1 (the rings are `config_files` entries,
  `swift/templates/swift-object-server.json.j2:4-15`; kolla `docker/base/set_configs.py:165-198,220-242`;
  [Kolla images §3.3](../../concepts/kolla-images.md#33-exit-codes)), and `reconfigure` then restarts the container
  under COPY_ALWAYS (`swift/tasks/reconfigure.yml:88-101`). That `deploy` leaves the old rings in running containers is
  settled in code ([§3.4](#34-task-flow)).
- NOT AVAILABLE: the effective value of `enable_swift_recon` in the rendered `object-server.conf`.
- NOT AVAILABLE: what an iscsid, tgtd or multipathd restart does to attached volumes under I/O (session state, path
  failover, the guest view); for tgtd, whether the LVM targets come back without a cinder-volume restart.
- NOT AVAILABLE: whether masakari-instancemonitor can connect to libvirt with SASL on (it now receives `auth.conf`,
  5.6).
- NOT AVAILABLE: whether the fleet-wide restarts after adding a rabbitmq or memcached host cause a reconnect storm, with
  `kolla_serial=0` versus a set `ANSIBLE_SERIAL`.
- NOT AVAILABLE: Octavia amphora behaviour after a change in the health-manager host list.
- NOT AVAILABLE: whether chrony steps the clock when it restarts on a drifted compute. Does not apply to 2023.1 (no
  chrony role, 5.12).
- NOT AVAILABLE: whether common runs (and fails) on Windows hyperv hosts. Does not apply to 2023.1 (no nova-hyperv role,
  no meta dependencies, 5.13).
- NOT AVAILABLE: whether ceilometer-ipmi can reach local IPMI without privileged mode or `/dev`.
- NOT AVAILABLE (new in 2023.1): what `octavia_auto_configure` does during an upgrade from manually registered Ussuri
  resources with other names (2.3).
- NOT AVAILABLE (new in 2023.1): whether and how fast masakari-hostmonitor detects a failed compute, and what a
  `hacluster_pacemaker_remote` restart or a removed compute does to the Pacemaker cluster (5.6, 5.15).

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
