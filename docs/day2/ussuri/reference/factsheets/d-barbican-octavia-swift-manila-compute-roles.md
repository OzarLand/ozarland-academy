---
title: Fact sheet D
description: Fact sheet for Barbican, Octavia, Swift, Manila and every role that places containers on compute hosts, with the templates embedding host lists.
tags: [barbican, octavia, swift, manila, iscsi, scaling]
---

# Fact sheet D

Source: Kolla-Ansible tag `ussuri-eol`. All paths below are relative to the repo root.
Labels: **FACT** (the default, not written out) = read directly from the cited source: kolla-ansible, the kolla image
repository (cited as kolla `docker/...`) or Ansible (cited as ansible 2.9.27 `lib/ansible/...`). **NOT AVAILABLE** =
these sources do not establish it, often because it depends on upstream OpenStack, Swift, Ceph, libvirt, iSCSI or Docker
behaviour that is not in them.
Out of scope here, because other fact sheets cover them: site.yml mechanics, nova/nova-cell/neutron/openvswitch/common,
kolla_docker semantics, service-ks-register, service-rabbitmq, service-images-pull, service-stop. These are cited only
as cross-references.

Common facts used throughout:
- Every role below has `tasks/main.yml` = `include_tasks: "{{ kolla_action }}.yml"`. Every role except `multipathd` has
  a meta dependency on `common` (`ansible/roles/<role>/meta/main.yml`). `multipathd` has no `meta/` directory.
- Bootstrap containers are started with `kolla_docker action=start_container detach=False`. `remove_on_exit` defaults to
  `True` (`ansible/library/kolla_docker.py:992`, `:837-839`), so a bootstrap container (DB sync) is created afresh and
  **re-runs on every deploy/reconfigure** for any role whose `deploy.yml` imports `bootstrap.yml`.
- `kolla-ansible upgrade` and `reconfigure` pass `-e kolla_serial=${ANSIBLE_SERIAL}`, which defaults to 0
  (`tools/kolla-ansible:236,430,439`). In every play, `run_once` tasks (keystone registration, DB bootstrap) run once
  per serial batch: each batch is a separate run of the play, and `run_once` sends the task only to the first host left
  (ansible 2.9.27 `lib/ansible/executor/playbook_executor.py:161-169`,
  `lib/ansible/plugins/strategy/linear.py:288,315-316`).
- The transport URLs are global host lists:
  `ansible/group_vars/all.yml:206`
  `rpc_transport_url: "{{ om_rpc_transport }}://{% for host in groups[om_rpc_group] %}...{% endfor %}/{{ om_rpc_vhost }}"` with `om_rpc_group: "rabbitmq"` (`:203`). Similarly `notify_transport_url` at `:216` with `om_notify_group: "rabbitmq"` (`:213`).

---

## 1. Barbican

### 1.1 Plays in site.yml

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| haproxy loadbalancer include | `ansible/site.yml:144-148` | `haproxy` | `barbican` (`include_role tasks_from: loadbalancer`). The whole block applies only when `kolla_action in ['deploy','reconfigure','upgrade','config']` (`:390-392`) |
| Apply role barbican | `ansible/site.yml:995-1006` | `barbican-api`, `barbican-keystone-listener`, `barbican-worker`, `&enable_barbican_True` | `barbican`; `serial: kolla_serial` |

Default inventory: all three groups are children of `barbican`, which has `control` as its child
(`ansible/inventory/multinode:167-168,412-419`).

### 1.2 Services (`ansible/roles/barbican/defaults/main.yml:2-38`)

| Service | Container | Group | Enabled | Notable |
|---|---|---|---|---|
| barbican-api | `barbican_api` | barbican-api | `true` | haproxy `barbican_api` (internal) and `barbican_api_external`, both with `tls_backend: barbican_enable_tls_backend` (`:10-24`). Named volume `barbican:/var/lib/barbican/` (`:75`) |
| barbican-keystone-listener | `barbican_keystone_listener` | barbican-keystone-listener | `true` | no haproxy |
| barbican-worker | `barbican_worker` | barbican-worker | `true` | no haproxy |

Keystone registration: service type `key-manager` (`:125-132`), user `barbican` with admin on `service` (`:134-138`),
and roles `key-manager:service-admin`, `creator`, `observer`, `audit` (`:140-144`, `tasks/register.yml:2-8`).

### 1.3 Task flow per kolla_action

- **deploy** (`tasks/deploy.yml:1-14`): register.yml (keystone) → config.yml → check-containers.yml (compare_container,
  notify restart) → clone.yml (dev mode only) → bootstrap.yml → flush handlers.
- **reconfigure** = deploy (`tasks/reconfigure.yml:2`). So keystone registration and the DB bootstrap container **re-run
  on every reconfigure**.
- **upgrade** (`tasks/upgrade.yml:1-9`): config → check-containers → bootstrap_service (DB sync only, no DB/user
  creation) → flush. No keystone re-registration.
- **stop / pull / precheck / check / deploy-containers / loadbalancer** use the standard helpers. `check.yml:1-40`
  stores, fetches and deletes a secret, only if `kolla_enable_sanity_barbican` (default `no`,
  `ansible/group_vars/all.yml:56,58`). It passes the admin password on the `docker exec` command line.

### 1.4 Config files, overrides, handlers (`tasks/config.yml`)

| Output on host | Source and override chain | Notifies |
|---|---|---|
| `/etc/kolla/<svc>/config.json` | `templates/<svc>.json.j2` (`:54-65`) | Restart `<svc>` |
| `/etc/kolla/barbican-api/vassals/barbican-api.ini` (uwsgi) | merge: role template → `{{node_custom_config}}/barbican-api/barbican-api.ini` → `.../barbican-api/<host>/barbican-api.ini` (`:67-82`) | Restart barbican-api |
| `/etc/kolla/barbican-api/barbican-api-paste.ini` | only if `{{node_custom_config}}/barbican/barbican-api-paste.ini` exists (`:84-109`) | Restart barbican-api |
| `/etc/kolla/<svc>/barbican.conf` | merge: template → `global.conf` → `barbican.conf` → `barbican/<svc>.conf` → `barbican/<host>/barbican.conf` (`:111-129`) | Restart `<svc>` |
| policy file | first found in `{{node_custom_config}}/barbican/` (`:31-48,131-143`) | Restart `<svc>` |

Handlers (`handlers/main.yml:2-45`): `recreate_or_restart_container` for each of the 3 services, skipped when
`kolla_action == "config"`.

### 1.5 Dependencies (from templates)

- MariaDB: `sql_connection` (`templates/barbican.conf.j2:15`), DB created via `kolla_toolbox mysql_db/mysql_user`,
  delegated to `groups['barbican-api'][0]` (`tasks/bootstrap.yml:2-34`).
- RabbitMQ: `transport_url = {{ rpc_transport_url }}` (`barbican.conf.j2:17`) and the notifications transport (`:72`).
  Barbican does **not** use the `service-rabbitmq` role. In Ussuri only `nova-cell` does
  (`ansible/roles/nova-cell/tasks/rabbitmq.yml`).
- Memcached: `memcached_servers` loops over `groups['memcached']` (`barbican.conf.j2:69`).
- Keystone: authtoken (`:55-65`). **Keystone notifications are coupled**: `[keystone_notifications] enable = True`,
  `topic = barbican_notifications` (`barbican.conf.j2:49-53`). The keystone role adds the `barbican_notifications` topic
  when `enable_barbican` is set (`ansible/roles/keystone/defaults/main.yml:126-132`).
- Consumers: cinder (`ansible/roles/cinder/templates/cinder.conf.j2:198-201`), glance (`glance-api.conf.j2:133-136`),
  nova and nova-cell (`ansible/roles/nova-cell/templates/nova.conf.j2:234-237`, so **compute** `nova.conf` changes when
  barbican is enabled), octavia (`octavia.conf.j2:16-20`), magnum, tacker, murano.

### 1.6 Operationally notable

- **The crypto KEK lives in passwords.yml.** `barbican_crypto_plugin: "simple_crypto"`
  (`ansible/group_vars/all.yml:877`), and `kek = '{{ barbican_crypto_key }}'` (`barbican.conf.j2:42-46`). `kolla-genpwd`
  generates it as a Fernet key (`kolla_ansible/cmd/genpwd.py:130,86-87`) and only fills empty values (`:76`). **NOT
  AVAILABLE:** whether losing or changing `barbican_crypto_key` makes stored secrets undecryptable (simple_crypto
  semantics are Barbican code, which is not in the sources). This key must be in the passwords.yml backup.
- p11_crypto: the library path `/usr/lib/libCryptoki2_64.so` (`all.yml:878`) is not mounted into the containers
  (`defaults/main.yml:71-89`). No task generates the MKEK or HMAC keys: a grep for `mkek|gen_hmac|barbican-manage` in
  `ansible/` finds only the conf template. **NOT AVAILABLE:** what else an HSM setup needs (for example a custom image
  or extra volumes, plus manual key generation).
- Running `kolla-ansible deploy -t barbican` alone does not run the keystone play, so the `barbican_notifications` topic
  is not enabled in keystone.conf. **NOT AVAILABLE:** whether barbican-keystone-listener then receives project-deletion
  events.
- Copying the policy file uses `become: true`. That is fine.

---

## 2. Octavia

### 2.1 Plays

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| haproxy LB include | `ansible/site.yml:307-311` | haproxy | `octavia` |
| Apply role octavia | `ansible/site.yml:1183-1195` | `octavia-api`, `octavia-health-manager`, `octavia-housekeeping`, `octavia-worker`, `&enable_octavia_True` | `octavia`; serial kolla_serial |

Default inventory: all four groups are children of `octavia`, which is `control`
(`ansible/inventory/multinode:244-245,654-664`).

### 2.2 Services (`ansible/roles/octavia/defaults/main.yml:2-41`)

`octavia_api` (haproxy `octavia_api`/`octavia_api_external` on port 9876, **no `listen_port`, no tls_backend**),
`octavia_health_manager`, `octavia_housekeeping`, `octavia_worker`. All have `enabled: true` and no privileged or
special flags.
Keystone: service type `load-balancer` (`:133-140`). User `octavia` is given admin on `service` **and** on
`{{ octavia_service_auth_project }}`, default `service` (`:122-153`). Five `load-balancer_*` roles are created
(`:43-48`, `tasks/register.yml:9-20`).

### 2.3 Task flow

- **deploy** (`tasks/deploy.yml:1-11`): register → config → check-containers → bootstrap (DB/user, then
  `bootstrap_octavia` container) → flush.
- **reconfigure** = deploy (`tasks/reconfigure.yml:2`), so the DB sync and keystone registration re-run.
- **upgrade** (`tasks/upgrade.yml:1-24`): config → check-containers → bootstrap_service → flush → **"Removing octavia
  user from admin project"** (`:11-24`, `os_user_role state: absent`, `project: {{ keystone_admin_project }}`, which is
  `admin` per `all.yml:827`). Upgrade does **not** run register.yml.
  - **BUG (consequence NOT AVAILABLE):** if an operator kept Train behaviour with `octavia_service_auth_project: admin`,
    every upgrade removes the role that register.yml granted (`defaults/main.yml:150-153`). **NOT AVAILABLE:** whether
    Octavia service-auth then fails until the next deploy/reconfigure re-adds the role.
- `check.yml` is empty.

### 2.4 Config files and handlers (`tasks/config.yml`)

| Output | Source and overrides | Notifies |
|---|---|---|
| policy file | first-found in `{{node_custom_config}}/octavia/` (`:15-46`) | Restart `<svc>` |
| config.json | `templates/<svc>.json.j2` (`:52-63`) | Restart `<svc>` |
| `octavia.conf` (all 4 services) | merge: template → `global.conf` → `octavia.conf` → `octavia/<svc>.conf` → `octavia/<host>/octavia.conf` (`:65-83`) | Restart `<svc>` |
| 4 PEM files: `client.cert-and-key.pem`, `client_ca.cert.pem`, `server_ca.cert.pem`, `server_ca.key.pem` | plain `copy` from `{{node_custom_config}}/octavia/` into worker (`:85-102`), housekeeping (`:104-121`) and health-manager (`:123-140`) | Restart that service |

Handlers (`handlers/main.yml:2-60`) use `recreate_or_restart_container` for each service. Volumes are passed without
`reject('equalto','')`, which is harmless because kolla_docker skips empty volume strings
(`ansible/library/kolla_docker.py:659-661`).

### 2.5 OpenStack resources: Kolla creates none

In Ussuri the role does **not** create the amphora flavor, image, keypair, lb-mgmt network, security group or
certificates. There are no `os_*` network/flavor/secgroup tasks anywhere in `ansible/roles/octavia/tasks/`, and there is
no `octavia-certificates` command (`tools/kolla-ansible` has no octavia entry). The repo's own doc confirms this:
"Currently in Kolla Ansible it is necessary to manually register the OpenStack resources required by Octavia"
(`doc/source/reference/networking/octavia.rst:13-15`), followed by manual `flavor create`,
`keypair create ... octavia_ssh_key`, `network create lb-mgmt-net`, and security group with tcp 22/9443 (`:85-135`).
The template only consumes IDs:
- `amp_boot_network_list = {{ octavia_amp_boot_network_list }}`, `amp_secgroup_list`, `amp_flavor_id`
  (`templates/octavia.conf.j2:72-75`). All three are **empty by default** (`ansible/group_vars/all.yml:1003-1005`). **No
  precheck validates them**: `tasks/precheck.yml:1-57` checks only ports and the 4 PEM files.
- Hard-coded values: `amp_image_tag = amphora`, `amp_ssh_key_name = octavia_ssh_key` (`octavia.conf.j2:73,76`), and
  `heartbeat_key = insecure` (`:65`), which is a **security oddity** with no variable to change it except an override
  file.
- `[certificates] ca_private_key_passphrase = {{ octavia_ca_password }}` (`:13-15`) must match the operator-generated
  `server_ca.key.pem`.
- Barbican: if `enable_barbican`, the region and endpoint for the cert manager are set (`:16-20`). **NOT AVAILABLE:**
  whether TLS-terminated listeners need barbican.
- Upgrades from Train: resources registered in `admin` must be re-registered in `service` (`octavia.rst:17-25`;
  `defaults/main.yml:124-126`).

### 2.6 Health-manager network requirements

- `bind_ip = {{ octavia_network_interface_address }}`, `bind_port = {{ octavia_health_manager_port }}` (5555,
  `all.yml:415`) (`octavia.conf.j2:62-64`).
- `controller_ip_port_list` loops over **all** `groups['octavia-health-manager']` using
  `'octavia_network' | kolla_address(host)` (`octavia.conf.j2:66`). This needs facts for every HM host.
- `octavia_network_interface` defaults to `api_interface` (`all.yml:231`), and the address comes from
  `'octavia_network' | kolla_address` (`all.yml:253`). `kolla_address` raises `FilterError` if the interface or address
  family is missing on the host (`kolla_ansible/kolla_address.py:88-104`). The `[health_manager]` section is rendered
  into octavia.conf for **all four services**, so **every octavia host (api, worker and housekeeping too) must have
  `octavia_network_interface` with an address**, or templating fails.
- Kolla does not create the lb-mgmt interface, bridge or VLAN on the controllers. The doc says to bridge it to OVS
  manually (`doc/source/reference/networking/octavia.rst:153-166`).
- Precheck oddity: the HM free-port check uses `api_interface_address`, not `octavia_network_interface_address`
  (`tasks/precheck.yml:27-36`).
- Adding or removing a health-manager host changes octavia.conf on all octavia hosts and restarts them
  (`octavia.conf.j2:66`; `tasks/config.yml:65-83`). **NOT AVAILABLE:** whether the controller list is written into an
  amphora at boot, so that existing amphorae keep the old list until failover.
- Security spread: `server_ca.key.pem` (the CA private key) is copied to the worker, housekeeping **and** health-manager
  config dirs (`tasks/config.yml:85-140`).

### 2.7 Other dependencies

MariaDB (`octavia.conf.j2:26-30`), RabbitMQ rpc (`:6`) and notify (`:89-90`), memcached ×2 loops (`:44,60`), keystone
(`:32-60`), and glance, neutron and nova via internal endpoints (`:97-110`). Topology is
`octavia_loadbalancer_topology: "SINGLE"` (`all.yml:1002`).

---

## 3. Swift

### 3.1 Plays

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| haproxy LB include | `ansible/site.yml:360-364` | haproxy | `swift` |
| Apply role swift | `ansible/site.yml:643-655` | `swift-account-server`, `swift-container-server`, `swift-object-server`, `swift-proxy-server`, `&enable_swift_True` | `swift`; serial kolla_serial |

Default inventory: proxy is in `swift` (control); account, container and object servers are in `storage`
(`ansible/inventory/multinode:164-165,399-409`).

### 3.2 Services: "old-style" role

`swift_services` contains **only** `swift-proxy-server`, and only for haproxy
(`ansible/roles/swift/defaults/main.yml:2-16`). It has no container_name, image, volumes or check-containers. Containers
are started imperatively in `tasks/start.yml` with `kolla_docker action: start_container`:

| Container | Group | Notes (`tasks/start.yml`) |
|---|---|---|
| `swift_rsyncd` | any of account, container or object | `:36-49`. Rsync daemon on port `swift_rsync_port` 10873 (`all.yml:502`, `templates/swift-rsyncd.json.j2:2`). It is the only swift image that fixes disk ownership at start: it chowns `/srv/node` and its top-level mount points to `swift:swift` (kolla `docker/swift/swift-rsyncd/extend_start.sh:3`). The other swift images have no `extend_start` |
| `swift_account_server/auditor/replicator/reaper` (+ `_replication_server` if a separate replication net exists) | swift-account-server | `:51-127` |
| `swift_container_server/auditor/replicator/updater` (+ replication server) | swift-container-server | `:129-206` |
| `swift_object_server/auditor/replicator/updater/expirer` (+ replication server) | swift-object-server | `:208-301` |
| `swift_proxy_server` | swift-proxy-server | `:303-315`, only when `run_start_swift_proxy_server` |

Disks: `find_disks` runs via `docker exec kolla_toolbox ... -m find_disks name=KOLLA_SWIFT_DATA match_mode=strict`
(`start.yml:2-14`, `defaults/main.yml:62-64`). Each disk is then mounted `xfs` by UUID at `/srv/node/<fs_label>` with
`noatime,nodiratime,logbufs=8` (`start.yml:23-34`). The `find_disks` module is not in this repo (`ansible/library/` has
only 4 modules); it ships in the kolla_toolbox image.
Volumes: `/srv/node` with `:shared`, `/etc/kolla/swift` mounted at `/var/lib/kolla/swift` (ring files), and the named
volume `swift_recon_cache`. **No `kolla_logs` volume**: all swift logs go over UDP syslog to
`syslog_server = api_interface_address` (`defaults/main.yml:74`, `templates/object.conf.j2:8-12`).

### 3.3 Ring files

- Kolla **does not build rings**. Precheck fails unless `account|container|object.builder` and `.ring.gz` exist under
  `{{node_custom_config}}/swift/` (`tasks/precheck.yml:106-129`).
- `config.yml:183-197` copies them (plus `swift_extra_ring_files`) to `/etc/kolla/swift/` on **every host in the swift
  play**, with `backup: yes`. Timestamped backups accumulate on each host.
- Containers read the rings via `config.json`, for example `templates/swift-object-server.json.j2:4-15` (source
  `/var/lib/kolla/swift/*.ring.gz`). Under COPY_ALWAYS they are copied into `/etc/swift` at container start.

### 3.4 Task flow

- **deploy** (`tasks/deploy.yml:1-10`): register (keystone service, user, and the `ResellerAdmin` role at
  `tasks/register.yml:9-19`) → config → start.yml → check.yml (sanity, default off).
  - **No task in the swift role has `notify:`** (a grep for `notify` in `ansible/roles/swift/tasks/` finds nothing). The
    only handler is a no-op `debug` (`handlers/main.yml:2-4`), triggered only by service-cert-copy.
  - `start_container` recreates a container only when container properties differ (image, volumes, ...;
    `kolla_docker.py:809-813`). **So `deploy` does not apply swift config or ring changes to running containers**
    (verified in code): `start_container` compares only container properties and never runs `kolla_set_configs --check`,
    which only `compare_container` calls (`kolla_docker.py:326-350,805-821`); `kolla_set_configs` copies config and
    rings into the container only at container start (kolla `docker/base/start.sh:8`,
    `docker/base/set_configs.py:391-393`); every swift command reads those copies, not the bind-mounted sources
    (`/etc/swift/*.conf` or `/etc/rsyncd.conf` in `templates/swift-*.json.j2`; no template sets `swift_dir`); and no
    task notifies a handler. See [Kolla images §2](../../concepts/kolla-images.md#2-start-path-common-to-every-image).
- **reconfigure** (`tasks/reconfigure.yml:1-101`) is a different, legacy flow:
  1. It builds the list of all swift containers, plus replication servers if `swift_has_replication_network` (`:2-30`).
  2. It **fails if any listed container is not running** (`:32-41`), so reconfigure cannot repair a crashed container.
  3. It runs config.yml, then `docker exec -u root <c> kolla_set_configs --check` (`:45-53`).
  4. It removes and re-creates containers under COPY_ONCE (`:68-86`), or does a plain `restart_container` under
     COPY_ALWAYS when the check returns rc==1 (`:88-101`).
  - Under COPY_ALWAYS (the default, `all.yml:43`), all changed containers on all hosts of the batch restart in the same
    task (`:88-101`). With default `kolla_serial=0` (`tools/kolla-ansible:236`) the batch is every host of the play
    (ansible 2.9.27 `lib/ansible/executor/playbook_executor.py:276-278`), so **every changed proxy, on every proxy host,
    restarts in that one task**. **NOT AVAILABLE:** whether this opens an outage window.
- **upgrade** (`tasks/upgrade.yml`) uses `rolling_upgrade.yml` by default (`swift_enable_rolling_upgrade: "yes"`,
  `defaults/main.yml:77`). Despite the name, it stops **all storage containers on all storage hosts at once**
  (`rolling_upgrade.yml:28-38`, with a TODO admitting it), restarts them, then stops and starts the proxies (`:48-66`).
  The proxy start here omits `/etc/timezone` and `kolla_logs` (`:62-65`), which is consistent with start.yml.
- **stop** (`tasks/stop.yml`) contains a **bug**: the account-auditor stop checks
  `'swift_object_auditor' not in skip_stop_containers` (`:23-31`).

### 3.5 Config files (`tasks/config.yml`)

- Config dirs and config.json for **all 18 services are created on every host in the play**, with no group filter
  (`:2-29,35-59`). swift.conf is copied for all 17 services on every host (`:61-91`). `swift.conf` contains
  `swift_hash_path_suffix/prefix` from passwords.yml (`templates/swift.conf.j2:1-3`, `etc/kolla/passwords.yml:112-113`).
  **NOT AVAILABLE:** what changing them after data is written does (Swift semantics are not in the sources).
- account, container and object `*.conf` are written for their groups (`:93-155`). Override chain: template →
  `global.conf` → `swift/<type>.conf` → `swift/<svc>.conf` → `swift/<host>/<svc>.conf`.
- The proxy chain is template → global.conf → `swift/proxy-server.conf` → `swift/<host>/proxy-server.conf` (`:157-171`).
- `rsyncd.conf` is a plain template (not mergeable) bound to `'swift_replication' | kolla_address`
  (`templates/rsyncd.conf.j2:1`).
- policy.json is copied **without `become`** (`config.yml:206-230`).

### 3.6 Networks and ports

- Storage services bind to `swift_storage` (default `storage_interface`); `replicat*` services bind to
  `swift_replication` (`templates/object.conf.j2:1-3`, `account.conf.j2:1-3`; `all.yml:227-228`).
- `swift_has_replication_network` is true when the interfaces differ (`defaults/main.yml:70`). Replicators use
  `RSYNC_CONNECT_PROG: "nc %H 10873"` (`start.yml:85-86` etc.).
- Precheck **bug**: the rsync free-port check probes port **873** (`precheck.yml:84-93`), but rsyncd listens on 10873.

### 3.7 Dependencies

- Keystone authtoken (`proxy-server.conf.j2:36-51`).
- Memcached: two loops over `groups['memcached']` (`:25,51`).
- RabbitMQ only when `enable_ceilometer`: the ceilometer middleware uses `url = {{ notify_transport_url }}` (`:58-66`).
- No MariaDB.
- Cinder backup can point at swift (`ansible/roles/cinder/templates/cinder.conf.j2:49`). Ceilometer's register.yml
  grants `ResellerAdmin` when swift is enabled (`ansible/roles/ceilometer/tasks/register.yml:8-21`).

### 3.8 Oddities

- **`enable_swift_recon` is tested without `| bool`**: `{% if enable_swift_recon %}` (`account.conf.j2:15,17`,
  `container.conf.j2:15,17`, `object.conf.j2:19,22`). The default is the string `"no"` (`all.yml:703`), not a boolean.
  **NOT AVAILABLE:** whether the template treats that string as true and so always enables the recon middleware (the
  Jinja test of a string is not in the sources).
- The `proxy-logging` and `versioned_writes` filters are defined but not in the proxy pipeline
  (`proxy-server.conf.j2:13,33-34,92-94`).

---

## 4. Manila

### 4.1 Plays

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| haproxy LB include | `ansible/site.yml:244-248` | haproxy | `manila` |
| **Apply role neutron** | `ansible/site.yml:761-780` | includes **`manila-share`** (`:774`) and `compute` (`:773`) | `neutron` |
| Apply role manila | `ansible/site.yml:917-929` | `manila-api`, `manila-data`, `manila-share`, `manila-scheduler`, `&enable_manila_True` | `manila` |

Default inventory: `manila-share` is a child of **`network`** (`ansible/inventory/multinode:392-393`). The other groups
are under `manila` (control) (`:194-195,386-396`). `openvswitch` children include `manila-share` (`:144-147`).

**Why manila-share is in the neutron play:** the agent host_in_groups include manila-share hosts.
- OVS agent, only with the generic backend:
  `(enable_manila_backend_generic | bool and inventory_hostname in groups['manila-share'])`
  (`ansible/roles/neutron/defaults/main.yml:36`). openvswitch db and vswitchd have the same condition
  (`ansible/roles/openvswitch/defaults/main.yml:11,26`).
- Linuxbridge agent: whenever `enable_manila` is set, **for any backend** (`neutron/defaults/main.yml:71`). This is an
  inconsistency.
- Generic-driver share servers are plugged with `OVSInterfaceDriver` or `BridgeInterfaceDriver`
  (`templates/manila-share.conf.j2:140-144`).
- Ordering: the neutron play (`:761`) runs before manila (`:917`).

### 4.2 Services (`ansible/roles/manila/defaults/main.yml:2-43`)

| Service | Container | Notable |
|---|---|---|
| manila-api | `manila_api` | haproxy port 8786 (`all.yml:364`) |
| manila-scheduler | `manila_scheduler` | — |
| manila-share | `manila_share` | **privileged**, `/run:/run:shared`, `/lib/modules:ro` (`:81-88`). Its handler adds `ipc_mode: host` (`handlers/main.yml:48-63`), which is not in the services dict and not compared by check-containers |
| manila-data | `manila_data` | **privileged**, `/dev/:/dev/`, `/run:shared` (`:101-108`) |

Backends (`:138-163`): generic, hnas, cephfsnative, cephfsnfs, each gated by `enable_manila_backend_*`
(`all.yml:656-660`).

### 4.3 Task flow

- **deploy** (`tasks/deploy.yml:1-19`): clone (dev) → register (keystone `share` and `sharev2`, `defaults:188-202`) →
  config → check-containers → bootstrap (DB, then `bootstrap_manila`) → flush → **`fix_cephfs_owner.yml`** when
  cephfs_native is enabled and the host is in manila-share (`:16-19`).
- **reconfigure** = deploy. **upgrade**: config → check-containers → bootstrap_service → flush (`tasks/upgrade.yml`).
- **`fix_cephfs_owner.yml` runs on every deploy/reconfigure** (`:1-85`), `run_once` inside the `manila_share` container.
  It runs `ceph mon dump`, builds the mon address list, **mounts CephFS with `secret=<keyring secret>` on the command
  line** (`:48-55`), creates and chowns `/tmp/cephfs/volumes`, then unmounts. **Security (NOT AVAILABLE):** whether the
  secret appears in the process list and in Ansible logs at `-v`.

### 4.4 Config (`tasks/config.yml`)

| Output | Chain | Notifies |
|---|---|---|
| ceph.conf and keyring (`external_ceph.yml:2-33`) | `{{node_custom_config}}/manila/ceph.conf` (templated), `.../manila/{{ceph_manila_keyring}}` | Restart manila-share |
| config.json | `:43-54` | Restart `<svc>` |
| manila.conf (api, data, scheduler) | template → global.conf → manila.conf → `manila/<svc>.conf` → `manila/<host>/manila.conf` (`:56-75`) | Restart `<svc>` |
| manila-share manila.conf | `manila.conf.j2` **+** `manila-share.conf.j2` → global.conf → manila.conf → `{{node_custom_config}}/manila-share.conf` → manila/manila-share.conf → `manila/<host>/manila.conf` (`:77-99`) | Restart manila-share |
| policy | `:101-112`, **no `become`** | Restart `<svc>` |

### 4.5 Dependencies

- MariaDB (`manila.conf.j2:27-31`), RabbitMQ rpc (`:22`) and notify (`:49-56`), memcached (`:47`).
- manila-share.conf additionally loops over memcached 3× and holds **glance, cinder, nova and neutron service-user
  passwords** (`manila-share.conf.j2:73-135`).
- Ceph is external only: there is no ceph deployment role in Ussuri. The config is supplied by the operator
  (`external_ceph.yml`).

### 4.6 Operationally notable

- Kolla does not create share types, the service image or networks. `default_share_type = default_share_type` is
  hard-coded (`manila-share.conf.j2:71`) and `service_image_name = manila-service-image` (`:150`).
- The generic backend's service-instance credentials default to `manila`/`manila` (`defaults/main.yml:129-130`,
  `manila-share.conf.j2:148-149`).
- Endpoints use `kolla_internal_fqdn` and `kolla_external_fqdn` directly (`defaults/main.yml:119-124`).

---

## 5. Other roles that deploy containers onto `compute` hosts

Default multinode membership (compute ∈): chrony (`multinode:50-55`), collectd (`:57-58`), telegraf (`:81-86`),
monasca-agent (`:116-121`), cyborg and cyborg-agent (`:203-205,578-579`), iscsid (`:367-370`), ceilometer-compute and
ceilometer-ipmi (`:555-559`), multipathd (`:619-621`), zun-compute and zun-cni-daemon (`:699-703`), skydive-agent
(`:709-711`), prometheus-node-exporter and prometheus-cadvisor (`:744-765`), masakari-monitors (`:785-786`),
ovn-controller-compute (`:792-793`). The kuryr play targets `compute` directly (`site.yml:782-791`). Hyper-V uses a
separate `hyperv` group (`multinode:94-102`).

### 5.0 Summary table (compute-side)

| Role (enable flag, default) | Compute containers | Restart trigger (handler) | Config: per-host or global? | Data-plane / VM impact |
|---|---|---|---|---|
| ceilometer (`enable_ceilometer` no; ipmi `enable_ceilometer_ipmi` no, `all.yml:594`) | `ceilometer_compute` (privileged, `/run:shared`, `nova_libvirt` volume), `ceilometer_ipmi` | `handlers/main.yml:32-46`, `:48-61` | **Global**: rabbit rpc and notify, memcached | VM impact NOT AVAILABLE (`ceilometer_compute` runs only `ceilometer-polling`, `templates/ceilometer-compute.json.j2:2`) |
| iscsi (`enable_iscsid` derived, `all.yml:651`) | `iscsid` (privileged, ipc host, `/dev`, `/run:shared`, `/sys/kernel/config`, `iscsi_info:/etc/iscsi`) | `handlers/main.yml:2-17` | Per-host (config.json only) | **Risk topic**, outcome NOT AVAILABLE; see 5.2 |
| multipathd (`enable_multipathd` no) | `multipathd` (privileged, ipc host) | `handlers/main.yml:2-16` | Per-host (static template) | **Risk topic**, outcome NOT AVAILABLE; see 5.3 |
| collectd (no) | `collectd` (privileged, `/sys`, `/dev` ro) | `handlers/main.yml:2-16` | Per-host | none |
| telegraf (no) | `telegraf` (pid host, docker.sock ro) | `handlers/main.yml:2-19` | **Global**: influxdb hosts | none |
| prometheus (no) | `prometheus_node_exporter` (pid host, `/:/host:ro,rslave`), `prometheus_cadvisor` (`/var/run:rw`, `/var/lib/docker:ro`) | `handlers/main.yml:17-31`, `:78-91` | Per-host on compute. The **server** config lists every compute | none on compute; prometheus_server restarts when computes are added |
| masakari (no) | `masakari_instancemonitor` (privileged) | `handlers/main.yml:34-48` | Per-host | none directly; see 5.6 |
| zun (no) | `zun_compute` (privileged, `/var/lib/docker`, `/dev`, `/run:shared`), `zun_cni_daemon` (privileged) | `handlers/main.yml:38-54`, `:56-72`, plus a loopback copy at `:74-84` | **Global**: rabbit rpc, memcached ×2, **DB creds** | container workloads, outcome NOT AVAILABLE; see 5.7 |
| kuryr (no) | `kuryr` (privileged, NET_ADMIN, `/run:shared`, `/usr/lib/docker`) | `handlers/main.yml:2-17` | Per-host | docker network ops, outcome NOT AVAILABLE; see 5.8 |
| cyborg (no) | `cyborg_agent` (privileged) | `handlers/main.yml:34-48` | **Global**: rabbit rpc and notify, memcached, **DB creds**, placement creds | none |
| skydive (no) | `skydive_agent` (privileged, netns, OVS socket) | `handlers/main.yml:17-31` | **Global**: etcd or analyzer hosts, analyzer hosts. **Cloud admin creds** | CPU cost of packet capture NOT AVAILABLE |
| monasca (no) | `monasca_agent_collector` (pid host), `monasca_agent_forwarder`, `monasca_agent_statsd` | `handlers/main.yml:134,150,165` | Per-host | none |
| chrony (**yes**, `all.yml:597`) | `chrony` (privileged) | `handlers/main.yml:2-16` | Per-host (VIP and external servers) | clock step at start NOT AVAILABLE (see 5.12) |
| nova-hyperv (no; Windows `hyperv` group) | Windows services, not containers | `handlers/main.yml:2-15` (`win_service`) | **Global**: rabbit rpc and notify | nova-compute service restart |
| (cross-ref) ovn | `ovn_controller` | ovn role | **Global**: `ovn-remote` = SB host list | out of scope |

### 5.1 ceilometer

- Play: `ansible/site.yml:944-958`, hosts central, notification, compute, ipmi;
  `vars_files: roles/panko/defaults/main.yml` (`:946-947`).
- Services: `ansible/roles/ceilometer/defaults/main.yml:2-31`. Compute volumes include `/run/:/run/:shared` and
  `nova_libvirt:/var/lib/libvirt` (`:74-82`). ceilometer-ipmi has no `/dev` mount and is not privileged
  (`:25-31,83-89`). **NOT AVAILABLE:** whether local IPMI (`/dev/ipmi0`) is reachable from it.
- Flow: deploy = register → config → check-containers → clone → bootstrap → flush (`tasks/deploy.yml`). `bootstrap.yml`
  has a `TODO(Jeffrey4l): fix idempotent` comment and **always runs** the `bootstrap_ceilometer` container
  (ceilometer-upgrade against gnocchi), delegated to `groups['ceilometer-notification'][0]`
  (`tasks/bootstrap_service.yml:2-22`).
- Config: `ceilometer.conf` merge chain at `tasks/config.yml:196-214`. The template carries
  `transport_url = rpc_transport_url` (`templates/ceilometer.conf.j2:6`), `notify_transport_url` (`:38`) and
  `memcache_servers` over `groups['memcached']` (`:55`). The same file is rendered for ceilometer-compute on **every
  compute**, so a rabbitmq or memcached membership change restarts `ceilometer_compute` on every compute.
- Scaling oddities:
  - Several `delegate_to: localhost` stat/find tasks **lack `run_once`**: custom meters (`:15-35`), polling.yaml
    (`:106-110`), gnocchi_resources (`:133-137`), event_definitions (`:216-220`), event_pipeline (`:255-259`), pipeline
    (`:293-297`). That is roughly 6 local tasks per host, multiplied by the compute count.
  - "Clean default folder for dynamic pollsters definitions" has **no `become` and no host condition** (`:77-80`). It
    deletes `/etc/kolla/ceilometer-central/pollsters.d/` on every run, then recreates and recopies it (`:82-104`). **NOT
    AVAILABLE:** whether ceilometer-central then restarts on every deploy/reconfigure when `pollsters.d` exists, and
    whether the delete, having no become, hits permission errors for non-root ansible users (`config_owner_user: root`,
    `all.yml:20`).
- Precheck: fails unless gnocchi is enabled (`tasks/precheck.yml:8-15`).

### 5.2 iscsi (iscsid, tgtd)

- Play: `ansible/site.yml:512-522`, hosts `iscsid`, `tgtd`, `&enable_iscsid_True`.
- `enable_iscsid` is `(enable_cinder and enable_cinder_backend_iscsi) or enable_ironic`
  (`ansible/group_vars/all.yml:651`), and `enable_cinder_backend_iscsi` defaults to `enable_cinder_backend_lvm`
  (`:601-602`).
- Per-host enablement (`ansible/roles/iscsi/defaults/main.yml:67-78`): iscsid runs on compute, cinder-backup or
  cinder-volume hosts only when cinder and the iscsi backend are enabled, or on ironic-conductor hosts with ironic. tgtd
  runs only with the LVM backend and `cinder_target_helper == tgtadm`.
- Containers (`:2-20`): both privileged, `ipc_mode: host`, with volumes `/dev`, `/run:shared`, `/sys/fs/cgroup:ro`,
  `/lib/modules:ro`, `/sys/kernel/config:/configfs`, `cinder:/var/lib/cinder`, `iscsi_info:/etc/iscsi` (`:40-63`).
- Config: config.json only. The iscsid command is `iscsid -d 8 -f` (`templates/iscsid.json.j2:2`), which is **debug
  level 8, very verbose**. So the container restarts only on config.json, image, volume or dimension change, in practice
  **upgrade/pull of a new tag**. The flow for deploy, upgrade and reconfigure is config-host (loads `configfs`,
  `tasks/config-host.yml:1-10`) → config → check-containers → flush (`tasks/deploy.yml`, `upgrade.yml` = deploy).
- **Host interaction:** bootstrap-servers **removes host `open-iscsi` / `iscsi-initiator-utils`**
  (`ansible/roles/baremetal/defaults/main.yml:62-73`). **NOT AVAILABLE:** whether computes then have no iscsid at all
  when `enable_iscsid` is false (no cinder iSCSI backend, for example a third-party iSCSI SAN).
- **VM impact (NOT AVAILABLE):** whether iSCSI sessions survive an iscsid restart, and whether session recovery or
  re-login after a path or portal failure, and os-brick attach/detach from nova-compute, fail or stall while iscsid is
  down. The `iscsi_info` named volume holds the initiator IQN (kolla `docker/iscsid/extend_start.sh:3-7`). **NOT
  AVAILABLE:** whether recreating the volume (for example after `destroy`) changes the IQN and breaks array ACLs.
- **tgtd restart (consequences NOT AVAILABLE):** the command is only `tgtd -d 1 -f --iscsi portal=...` with empty
  `config_files` (`templates/tgtd.json.j2:2-3`), and the image adds no start script of its own. It only inserts
  `include /var/lib/cinder/volumes/*` into `/etc/tgt/targets.conf` (kolla `docker/tgtd/Dockerfile.j2:19`), and nothing
  runs `tgt-admin` at start. **NOT AVAILABLE:** whether tgtd keeps its target table only in memory, so that a restart
  drops every exported LVM target and its sessions until cinder-volume (for example at its own restart) or a manual
  `tgt-admin` run re-creates them from `/var/lib/cinder/volumes` (the `cinder` named volume, shared with cinder-volume,
  `ansible/roles/cinder/defaults/main.yml:114`), and whether I/O to attached LVM volumes stalls or fails meanwhile. See
  [Kolla images §5](../../concepts/kolla-images.md#5-per-image-start-behaviour).
- Precheck oddity: it checks that `iscsi_port` 3260 is free on the iscsid hosts (`tasks/precheck.yml:15-25`), but 3260
  is the **target** (tgtd) port.

### 5.3 multipathd

- Play: `ansible/site.yml:524-533`. Default `enable_multipathd: "no"` (`all.yml:666`). It has no meta dependency on
  common.
- Container: privileged, ipc host, with the same host mounts as iscsid, including `iscsi_info` and `cinder`
  (`ansible/roles/multipathd/defaults/main.yml:2-33`). There are **no `dimensions`**.
- Config: `multipath.conf` is a **plain role template with no override path** (`tasks/config.yml:28-39`). The content is
  `user_friendly_names yes`, `find_multipaths yes`, and an empty blacklist (`templates/multipath.conf.j2:1-7`). Changing
  it requires editing the role.
- The `dm-multipath` module is loaded by config-host (`tasks/config-host.yml:1-7`).
- Restart (handler `:2-16`): on config.json or multipath.conf change, or on image/volume change.
- **VM impact (NOT AVAILABLE):** whether dm maps persist across a restart, whether path checking and failback pause
  while multipathd is down, and whether a path failure in that window causes I/O errors or queueing depending on
  `no_path_retry`. Restarts run in the same handler step on all notified multipathd hosts of the batch (ansible 2.9.27
  `lib/ansible/plugins/strategy/__init__.py:1019-1035`), and with serial 0 by default the batch is every host
  (`lib/ansible/executor/playbook_executor.py:276-278`).

### 5.4 collectd and telegraf

- collectd: play `site.yml:394-403`. Privileged, `/sys` and `/dev` ro (`ansible/roles/collectd/defaults/main.yml:2-30`).
  collectd.conf is first-found (host → global → role template), with no merge (`tasks/config.yml:41-58`). The default
  sends to `{{ 'api' | kolla_address }}:{{ collectd_udp_port }}`, i.e. its own host (`templates/collectd.conf.j2:9-11`),
  where telegraf's `socket_listener` receives it if telegraf is enabled
  (`ansible/roles/telegraf/templates/telegraf.conf.j2:29-35`). Per-host only.
- telegraf: play `site.yml:438-447`. `pid_mode: host`, `/proc` and `/sys` ro, `/var/run/docker.sock:ro`
  (`ansible/roles/telegraf/defaults/main.yml:2-28`). telegraf.conf is first-found, not merged
  (`tasks/config.yml:32-48`). It **loops over `groups['influxdb']`** (`telegraf.conf.j2:14-24`), so adding or removing
  an influxdb host restarts telegraf on every host.
  - **Latent bug:** the "Copying over telegraf plugin files" task tests `item.value.enabled` inside a `with_fileglob`
    loop of path strings (`tasks/config.yml:50-64`). The glob is currently empty because `templates/config/` does not
    exist, but adding files there would break the task.
  - check-containers does not pass the `HOST_PROC`/`HOST_SYS` env, while the handler does (`handlers/main.yml:12-14`).

### 5.5 prometheus (node-exporter, cadvisor)

- Play: `site.yml:492-510`. Hosts include `prometheus-node-exporter` and `prometheus-cadvisor`, which contain compute
  (`multinode:744-765`).
- node_exporter: `pid_mode: host`, `/:/host:ro,rslave`, listens on `api_interface_address:9100`
  (`ansible/roles/prometheus/defaults/main.yml:16-23,195-200`; `templates/prometheus-node-exporter.json.j2:2`).
- cadvisor: `/var/run:/var/run:rw` (**this includes docker.sock read-write, which makes the container
  root-equivalent**), `/var/lib/docker:ro`, `/sys:ro`. The command is `/opt/cadvisor --port=18080` with **no listen
  address** (`defaults/main.yml:206-215`; `templates/prometheus-cadvisor.json.j2:2`). **NOT AVAILABLE:** whether it
  listens on all interfaces.
- Compute-side config is config.json only (per-host). The **server** config `prometheus.yml.j2` loops over
  node-exporter, cadvisor and other groups (`templates/prometheus.yml.j2:19-72`). Adding a compute changes
  prometheus.yml and restarts `prometheus_server` (`tasks/config.yml:79-98`), and rendering it needs facts for every
  compute.
- Scaling: "Find prometheus host config overrides" runs `delegate_to: localhost` **per host**, explicitly
  `run_once: false` (`tasks/config.yml:68-77`), even on hosts that are not prometheus servers.

### 5.6 masakari (monitors)

- Play: `site.yml:1250-1261`. Hosts are masakari-api, masakari-engine and `masakari-monitors` (= compute).
- Only `masakari-instancemonitor` is deployed (`ansible/roles/masakari/defaults/main.yml:28-35`). **There is no
  hostmonitor or processmonitor in Ussuri**: a grep for `hostmonitor|processmonitor` in `ansible/`, `etc/` and `doc/`
  finds nothing. Kolla-deployed masakari therefore cannot detect compute **host** failure on its own.
- Config: `masakari-monitors.conf` merge chain (`tasks/config.yml:88-108`). It is per-host and has no rabbit, memcached
  or DB. Libvirt is reached over `connection_uri = "qemu+tcp://{{ migration_interface_address }}/system"`
  (`templates/masakari-monitors.conf.j2:16-17`).
  - **Default libvirt auth (outcome NOT AVAILABLE):** nova-cell defaults to `libvirt_enable_sasl: true`
    (`ansible/roles/nova-cell/defaults/main.yml:431`), giving `auth_tcp = "sasl"`
    (`ansible/roles/nova-cell/templates/libvirtd.conf.j2:10-12`). `auth.conf` is provided only to nova-compute and
    nova-libvirt (`ansible/roles/nova-cell/tasks/config.yml:121-122`), not to masakari. With `libvirt_tls: true`,
    `listen_tcp = 0` (`libvirtd.conf.j2:1-3`). **NOT AVAILABLE:** whether masakari-instancemonitor can connect to
    libvirt with these defaults.
- **Bug:** "Copying over existing policy file" uses `dest: "{{ node_config_directory }}/{{ item }}/..."` with
  `with_dict` (`tasks/config.yml:34-46`, dest at `:37`). When a custom policy exists, the dest path renders a dict.
- Bootstrap (DB sync) runs on every deploy/reconfigure (`tasks/deploy.yml`, `bootstrap_service.yml`).

### 5.7 zun (zun-compute, zun-cni-daemon)

- Play: `site.yml:1197-1209`. The precheck requires kuryr (`ansible/roles/zun/tasks/precheck.yml:50-57`).
- Containers (`defaults/main.yml:39-54,104-121`): zun_compute is privileged with `/run:shared`, `/usr/lib/docker`,
  `/var/lib/docker`, `/dev`, `/lib/modules:ro`, and `iscsi_info:/etc/iscsi` when iscsid is enabled. zun_cni_daemon is
  privileged.
- Config: `zun.conf` is rendered for **all** zun services including compute (`tasks/config.yml:51-69`). It contains
  `transport_url = rpc_transport_url` (`templates/zun.conf.j2:10`), the full **`[database] connection` with password**
  (`:24-28`), memcached ×2 (`:49,71`), and `docker api_url = tcp://<api_ip>:2375` (`:123-126`).
  - The docker daemon on zun-compute hosts is opened on TCP 2375 **without TLS or auth** by bootstrap-servers when
    `docker_configure_for_zun` is set (`ansible/group_vars/all.yml:140-143`;
    `ansible/roles/baremetal/templates/docker_systemd_service.j2:4`). `docker_zun_config.cluster-store` loops over
    `groups['etcd']` into `/etc/docker/daemon.json` (`all.yml:142-143`; `baremetal/tasks/post-install.yml:63-68`).
- Handlers: check-containers notifies `"<svc> container changed"`, and handlers `listen` on that as well as being named
  "Restart <svc> container" (`tasks/check-containers.yml:16-20`; `handlers/main.yml:38-72`). On a zun-cni-daemon
  container change, the loopback binary is copied to the host `/opt/cni/bin` (`:74-84`).
- **NOT AVAILABLE:** whether restarting zun_compute stops user containers, and whether a zun_cni_daemon restart breaks
  CNI operations during the window.

### 5.8 kuryr

- Play: `site.yml:782-791`. Hosts are **`compute`** directly, and the service group is hard-coded to `compute`
  (`ansible/roles/kuryr/defaults/main.yml:10-20`).
- The container is privileged with `cap_add: NET_ADMIN`, `/run:shared` and `/usr/lib/docker` (`:31-40`). `kuryr.spec` is
  placed into `/usr/lib/docker/plugins/kuryr/` (`templates/kuryr.json.j2:11-15`).
- Config is per-host: `kuryr_uri` uses its own api IP, and kuryr.conf has no rabbit, memcached or DB
  (`templates/kuryr.conf.j2:1-29`).
- Keystone user registration runs from the compute-host play (`tasks/register.yml`, `tasks/deploy.yml:2`).
- **NOT AVAILABLE:** whether docker network create/attach fails while kuryr is restarting, and whether existing veth
  wiring persists.

### 5.9 cyborg (agent)

- Play: `site.yml:1021-1032` uses **`serial: '{{ serial|default("0") }}'`** (`:1028`), not `kolla_serial`.
  `ANSIBLE_SERIAL` is therefore ignored for cyborg on reconfigure and upgrade. This is an **oddity**.
- `cyborg-agent` runs on compute and is privileged (`ansible/roles/cyborg/defaults/main.yml:10-17`).
- `cyborg.conf` is rendered for all services (`tasks/config.yml:65-83`). It contains DB connection credentials
  (`templates/cyborg.conf.j2:13-16`), placement service credentials (`:33-43`), rabbit rpc and notify (`:7,51`) and
  memcached (`:21`). **Global, and it carries DB and placement credentials on compute.**
- **Bugs and oddities:**
  - `cyborg_services` has **no `haproxy` key**, so `loadbalancer.yml` configures nothing. Yet the keystone endpoints
    point to `kolla_internal_fqdn:6666` (`defaults/main.yml:82-84`). **NOT AVAILABLE:** whether that VIP endpoint is
    reachable.
  - The service type is `"cyborg"` (`:107`). **NOT AVAILABLE:** whether Nova expects `accelerator` instead (Nova's code
    is not in the sources).

### 5.10 skydive (agent)

- Play: `site.yml:1211-1221`. `skydive-agent` = compute + network (`multinode:709-711`).
- The agent is privileged and mounts `/var/run/openvswitch:ro` and `/var/run/netns:/host/run:shared`
  (`ansible/roles/skydive/defaults/main.yml:21-28,50-56`).
- Config is a plain template with **no override mechanism** (`tasks/config.yml:32-43`). It embeds the **cloud admin
  username and password** in two places (`templates/skydive-agent.conf.j2:3-5,48-52`). It loops over `groups['etcd']` or
  `groups['skydive-analyzer']` (`:14-24`) and over the analyzers (`:26-29`). It uses gopacket and ovssflow probes
  (`:33-46`), whose CPU cost is NOT AVAILABLE, and `ovsdb: tcp://127.0.0.1:{{ ovsdb_port }}` (`:64-69`).
- The analyzer config enumerates **every skydive-agent host**, using `hostvars[host].ansible_facts.hostname`
  (`templates/skydive-analyzer.conf.j2:47-57`). Adding a compute therefore restarts the analyzer, and rendering needs
  facts for every agent host.

### 5.11 monasca (agents)

- Play: `site.yml:960-979`. `monasca-agent` = compute, control, monitoring, network, storage
  (`multinode:116-121,439-446`).
- Collector: `pid_mode: host`, `/sys:ro`, `/dev/disk:ro` (`ansible/roles/monasca/defaults/main.yml:64-71,226-232`).
  Forwarder and statsd are not privileged (`:72-85`).
- Config is per-host (hostname, local forwarder) (`templates/monasca-agent-collector/agent-collector.yml.j2:1-9`).
  - The forwarder carries `monasca_agent_password` and listens with `non_local_traffic: True` on 17123
    (`templates/monasca-agent-forwarder/agent-forwarder.yml.j2:5-6,18-21`; `all.yml:380`).
  - statsd has `non_local_traffic: True` on 8125 (`agent-statsd.yml.j2:5-7`).
  - Plugin files are templated from the role and from `{{node_custom_config}}/monasca[/<host>]/agent_plugins/` via a
    per-host localhost `find` without run_once (`tasks/config.yml:65-89`).
- The deploy flow also runs `check.yml` and `post_config.yml`, which hold Grafana API calls with `run_once` and **no
  delegate** (`tasks/deploy.yml:13-15`; `tasks/post_config.yml:3-80`). These run on the first host of each batch
  (ansible 2.9.27 `lib/ansible/executor/playbook_executor.py:161-169`,
  `lib/ansible/plugins/strategy/linear.py:288,315-316`). **NOT AVAILABLE:** whether that host can be a compute host,
  using its kolla_toolbox.

### 5.12 chrony

- Play: `site.yml:114-124`. Hosts `chrony-server` (= haproxy) and `chrony` (= all node types including compute)
  (`multinode:47-55`). It is **enabled by default** (`all.yml:597`), and bootstrap-servers removes the host chrony
  package (`baremetal/defaults/main.yml:67,73`).
- The container is privileged (`ansible/roles/chrony/defaults/main.yml:2-10`).
- chrony.conf is first-found, not merged (`tasks/config.yml:36-53`). It syncs from
  `server {{ kolla_internal_vip_address }}` **plus all `external_ntp_servers`** (`templates/chrony.conf.j2:3-9`), and
  the default list is `0-3.pool.ntp.org` (`all.yml:96-100`). By default **every compute queries public pool servers**.
- Non-servers get `port 0` and `deny all` (`:36-39`). `bindaddress {{ kolla_internal_vip_address }}` is set on every
  host (`defaults:12`, `chrony.conf.j2:41`).
- `makestep 3 3` (`:22`): **NOT AVAILABLE:** whether a chrony restart (image or config change) on a drifted compute
  **steps** the clock by more than 3 s in the first updates.
- Config is per-host. It references only the VIP, so no host-list churn.

### 5.13 nova-hyperv

- Play: `site.yml:748-757`, hosts `hyperv` (Windows/WinRM; `multinode:94-102`). It prints a deprecation warning,
  "removed in Victoria" (`ansible/roles/nova-hyperv/tasks/main.yml:2-6`).
- Uses `win_template`/`win_service` (`tasks/config.yml:1-39`, `handlers/main.yml:2-15`). nova_hyperv.conf includes
  `transport_url = rpc_transport_url` (`templates/nova_hyperv.conf.j2:21`); neutron_hyperv_agent.conf has rpc and notify
  (`templates/neutron_hyperv_agent.conf.j2:7,20`). These are **global**, so a rabbit change restarts the Windows
  nova-compute.
- **Bugs:**
  - There is **no `upgrade.yml` or `deploy-containers.yml`**, so `include_tasks: "{{ kolla_action }}.yml"` fails for
    upgrade and deploy-containers when hyperv is enabled.
  - `copy-certs.yml` references the undefined `nova_hyperv_services` (`tasks/copy-certs.yml:6`).
  - The role has a meta dependency on `common` (`meta/main.yml:3`), whose tasks are Linux/docker tasks. **NOT
    AVAILABLE:** whether common runs, and fails, on the Windows `hyperv` hosts.

### 5.14 Cross-reference: ovn-controller on compute

`ovn/tasks/bootstrap.yml:9-16` sets `external_ids:ovn-remote={{ ovn_sb_connection }}`, which is a loop over
`groups['ovn-sb-db']` (`all.yml:420`). The command runs on every deploy. A neutron-ovn-metadata-agent ini on compute
also lists the NB and SB DBs (`ansible/roles/neutron/templates/neutron_ovn_metadata_agent.ini.j2:16-17`).

---

## 6. Per-cluster host lists in templates

### 6.1 grep `for host in groups` over `ansible/roles/*/templates`

Memcached loops appear in: aodh, barbican, blazar, **ceilometer**, cinder, cloudkitty, congress, **cyborg**, designate,
freezer, glance, gnocchi, heat (×2), horizon, ironic (×2), karbor, keystone, magnum, manila (×4), masakari (api/engine
only), mistral, murano, **neutron**, nova (×2), octavia (×2), panko, placement (×2), qinling, sahara, searchlight (×2),
senlin, solum, swift (×2), tacker, vitrage (×2), watcher, **zun (×2)**.

Other group loops:
- certificates `tls-backend`; designate `designate-backend-bind9`/`designate-worker`/`designate-mdns`; elasticsearch;
  haproxy-config backends; keepalived `haproxy`; keystone fernet-push `keystone`; galera `mariadb`; mongodb; nova-hyperv
  wsgate `hyperv`; octavia `octavia-health-manager`; prometheus.yml (9 groups); rabbitmq; **skydive** agent and
  analyzer; storm and zookeeper `zookeeper`; **telegraf** `influxdb`.
- Non-loop group references: `cinder.conf.j2:21` and `nova.conf.j2:63` use `groups['glance-api'] | length`; cinder
  coordination uses `groups['etcd'][0]` (`cinder.conf.j2:213`).
- Host lists defined as **variables** rather than template loops: `rpc_transport_url`/`notify_transport_url`
  (`all.yml:206,216`), `nova_cell_rpc/notify_transport_url` (`ansible/roles/nova-cell/defaults/main.yml:174-175`, groups
  default to `om_rpc_group` at `:159,168`), `ovn_nb/sb_connection` (`all.yml:419-420`), and
  `docker_zun_config.cluster-store` (etcd, `all.yml:142-143`).

### 6.2 Config files on COMPUTE hosts that embed per-cluster host lists

| File on compute (`/etc/kolla/...`) | Container restarted by its handler | Lists embedded | Evidence |
|---|---|---|---|
| `nova-compute/nova.conf` (and the other nova-cell compute services) | nova_compute, etc. (cross-ref) | cell rabbit rpc and notify | `nova-cell/templates/nova.conf.j2:42,184`; `nova-cell/defaults/main.yml:174-175` |
| `neutron-openvswitch-agent/neutron.conf` (also linuxbridge, ovn-metadata) | neutron agents (cross-ref) | rabbit rpc and notify, **memcached** | `neutron/templates/neutron.conf.j2:57,119,125`; rendered for agent services at `neutron/tasks/config.yml:77-90` |
| `neutron-ovn-metadata-agent/neutron_ovn_metadata_agent.ini` | ovn metadata agent (cross-ref) | OVN NB and SB DB hosts | `neutron_ovn_metadata_agent.ini.j2:16-17` |
| OVS DB `external_ids:ovn-remote` (not a file) | none (live setting) | OVN SB hosts | `ovn/tasks/bootstrap.yml:9-16` |
| `ceilometer-compute/ceilometer.conf`, `ceilometer-ipmi/ceilometer.conf` | ceilometer_compute, ceilometer_ipmi | rabbit rpc and notify, **memcached** | `ceilometer.conf.j2:6,38,55` |
| `zun-compute/zun.conf`, `zun-cni-daemon/zun.conf` | zun_compute, zun_cni_daemon | rabbit rpc, **memcached ×2** | `zun.conf.j2:10,49,71` |
| `cyborg-agent/cyborg.conf` | cyborg_agent | rabbit rpc and notify, **memcached** | `cyborg.conf.j2:7,21,51` |
| `skydive-agent/skydive.conf` | skydive_agent | etcd (or skydive-analyzer) hosts, analyzer hosts | `skydive-agent.conf.j2:14-29` |
| `telegraf/telegraf.conf` | telegraf | influxdb hosts | `telegraf.conf.j2:14-24` |
| `/etc/docker/daemon.json` (zun-compute, bootstrap-servers only) | dockerd (effect on the host's containers NOT AVAILABLE) | etcd hosts | `all.yml:142-143`; `baremetal/tasks/post-install.yml:63-68,138-142` |
| Windows `nova.conf` and `neutron_hyperv_agent.conf` (hyperv group) | Windows nova-compute and neutron-hyperv-agent services | rabbit rpc (and notify) | `nova_hyperv.conf.j2:21`; `neutron_hyperv_agent.conf.j2:7,20` |

Compute-side files with **no** cluster lists (per-host only): iscsid and tgtd config.json, multipath.conf,
collectd.conf, chrony.conf (VIP only), node-exporter and cadvisor config.json, masakari-monitors.conf, kuryr.conf,
monasca agent yml files, and the common/fluentd outputs (these use `elasticsearch_address` = internal FQDN,
`all.yml:758`; `common/templates/conf/output/01-es.conf.j2:5`).

**Implication (consequence NOT AVAILABLE):** adding or removing a host in `rabbitmq` or `memcached` (normally
controllers), then running deploy or reconfigure across the fleet:
- re-templates the files above on **every compute**;
- fires `recreate_or_restart_container` for ceilometer_compute, ceilometer_ipmi, zun_compute, zun_cni_daemon,
  cyborg_agent, the neutron agents, nova_compute (cross-ref) and others;
- runs those restarts in the same handler step on all notified hosts of the batch (ansible 2.9.27
  `lib/ansible/plugins/strategy/__init__.py:1019-1035`); with the default `kolla_serial=0` the batch is every host
  (`lib/ansible/executor/playbook_executor.py:276-278`). **NOT AVAILABLE:** whether this causes a fleet-wide reconnect
  storm on RabbitMQ.

Rendering each of these files also requires facts (`kolla_address(host)`) for every host in `rabbitmq` and `memcached`
(`kolla_ansible/kolla_address.py:60-104`). This matters for `--limit` runs (cross-ref gather-facts.yml).
Conversely, **adding a compute** changes non-compute configs: prometheus.yml (prometheus_server restart,
`prometheus.yml.j2:27,72`) and skydive-analyzer.conf (`skydive-analyzer.conf.j2:47-57`).

---

## 7. Consolidated bugs and oddities

1. Swift `stop.yml:23-31`: account-auditor guard checks `swift_object_auditor`.
2. Swift precheck checks rsync port 873, but rsyncd uses 10873 (`swift/tasks/precheck.yml:84-93` vs `all.yml:502`).
3. Swift `{% if enable_swift_recon %}` without `| bool` against the string `"no"` (`account.conf.j2:15`, etc.;
   `all.yml:703`). **NOT AVAILABLE:** whether recon is then always on.
4. Swift deploy never restarts on config or ring change (no notify anywhere; no-op handler at
   `swift/handlers/main.yml:2-4`). Reconfigure fails if any swift container is down (`reconfigure.yml:32-41`). The
   "rolling" upgrade stops all storage at once (`rolling_upgrade.yml:28-38`).
5. Octavia: `heartbeat_key = insecure` is hard-coded (`octavia.conf.j2:65`). The amp network, secgroup and flavor are
   empty by default with no precheck (`all.yml:1003-1005`). The upgrade unconditionally removes the octavia admin role
   on the admin project (`octavia/tasks/upgrade.yml:11-24`). The HM precheck uses the wrong address
   (`precheck.yml:27-36`). The CA private key is copied to 3 services (`config.yml:85-140`).
6. Manila: CephFS secret on the command line on every deploy (`fix_cephfs_owner.yml:48-55`). Policy copy has no `become`
   (`manila/tasks/config.yml:101-112`). Service-instance password defaults to `manila` (`defaults/main.yml:130`).
   Neutron host_in_groups for manila-share are asymmetric (OVS: generic only, `neutron/defaults/main.yml:36`; LB: any
   backend, `:71`).
7. Masakari: policy-file dest uses a dict `item` (`masakari/tasks/config.yml:37`). No hostmonitor. instancemonitor uses
   qemu+tcp without SASL credentials while SASL is on by default (`masakari-monitors.conf.j2:17`;
   `nova-cell/defaults/main.yml:431`).
8. Cyborg: the play uses `serial` instead of `kolla_serial` (`site.yml:1028`). There is no haproxy entry but endpoints
   are on the VIP (`cyborg/defaults/main.yml:2-24,82-84`). The keystone service type is `cyborg` (`:107`). DB
   credentials are on compute.
9. Telegraf: `item.value.enabled` in a `with_fileglob` loop (`telegraf/tasks/config.yml:50-64`).
10. Ceilometer: pollsters dir deleted every run without become (`ceilometer/tasks/config.yml:77-80`). Many localhost
    stats lack `run_once`. The bootstrap is explicitly non-idempotent (`tasks/bootstrap.yml:2`).
11. iscsid runs at debug `-d 8` (`iscsi/templates/iscsid.json.j2:2`). The precheck tests port 3260 on iscsid hosts
    (`iscsi/tasks/precheck.yml:15-25`).
12. multipathd has no meta, no dimensions, and no config override (`multipathd/tasks/config.yml:28-39`).
13. nova-hyperv lacks `upgrade.yml` and `deploy-containers.yml`, and references the undefined `nova_hyperv_services`
    (`nova-hyperv/tasks/copy-certs.yml:6`).
14. Security spread onto compute: cloud admin credentials (skydive `skydive-agent.conf.j2:3-5,48-52`); DB credentials
    (zun `zun.conf.j2:24-28`, cyborg `cyborg.conf.j2:13-16`); unauthenticated docker TCP 2375 for zun (`all.yml:141`);
    cadvisor with rw `/var/run` (docker.sock) (`prometheus/defaults/main.yml:212`); default chrony to public pool
    (`all.yml:96-100`).
15. Barbican and other bootstraps (octavia, manila, ceilometer, masakari, zun, cyborg) re-run their DB sync container on
    every deploy/reconfigure (bootstrap containers are auto-removed, `kolla_docker.py:992`).

## 8. NOT AVAILABLE list

- NOT AVAILABLE: whether the swift containers serve the new rings once `reconfigure` has restarted them. A changed ring
  file makes `--check` return rc 1 (the rings are `config_files` entries,
  `swift/templates/swift-object-server.json.j2:4-15`; kolla `docker/base/set_configs.py:160-171,213-235`;
  [Kolla images §3.3](../../concepts/kolla-images.md#33-exit-codes)), and `reconfigure` then restarts the container
  under COPY_ALWAYS (`swift/tasks/reconfigure.yml:88-101`). That `deploy` leaves the old rings in running containers is
  settled in code ([§3.4](#34-task-flow)).
- NOT AVAILABLE: the effective value of `enable_swift_recon` in the rendered `object-server.conf`.
- NOT AVAILABLE: what an iscsid, tgtd or multipathd restart does to attached volumes under I/O (session state, path
  failover, the guest view); for tgtd, whether the LVM targets come back without a cinder-volume restart.
- NOT AVAILABLE: whether masakari-instancemonitor can connect to libvirt with SASL on.
- NOT AVAILABLE: whether the fleet-wide restarts after adding a rabbitmq or memcached host cause a reconnect storm, with
  `kolla_serial=0` versus a set `ANSIBLE_SERIAL`.
- NOT AVAILABLE: Octavia amphora behaviour after a change in the health-manager host list.
- NOT AVAILABLE: whether chrony steps the clock when it restarts on a drifted compute.
- NOT AVAILABLE: whether common runs (and fails) on Windows hyperv hosts.
- NOT AVAILABLE: whether ceilometer-ipmi can reach local IPMI without privileged mode or `/dev`.

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
