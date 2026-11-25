---
title: Fact sheet D
description: Fact sheet for Barbican, Octavia, Manila, the removed Swift role and every role that places containers on compute hosts in 2025.1.
tags: [barbican, octavia, swift, manila, iscsi, scaling]
---

# Fact sheet D

Source: Kolla-Ansible tag `2025.1-eom` (commit `7222f0f`), kolla tag `2025.1-eom` (commit `c4b53a2`),
ansible-collection-kolla `2025.1-eom` (commit `09189c7`). All paths below are relative to the repo root.
Labels: **FACT** (the default, not written out) = read directly from the cited source: kolla-ansible, the kolla image
repository (cited as kolla `docker/...`), the collection (cited as ansible-collection-kolla `roles/...`) or Ansible
(cited as ansible-core 2.18.20 `lib/ansible/...`). **NOT AVAILABLE** = these sources do not establish it, often because
it depends on upstream OpenStack, Ceph, libvirt, iSCSI, Redis, Valkey, Pacemaker or container-engine behaviour that is
not in them. The points marked NOT AVAILABLE are to be confirmed by the community.
Out of scope here, because other fact sheets cover them: site.yml mechanics, nova/nova-cell/neutron/openvswitch/common,
`kolla_container` semantics, service-ks-register, service-rabbitmq, service-images-pull, service-stop. These are cited
only as cross-references.

**What changed since 2024.1, in one paragraph (FACT):** **Swift is removed**: there is no `swift` role, play, tag or
image any more, and nothing stops or cleans up a deployed Swift ([§3](#3-swift)). In every role below, the config tasks
no longer notify: `check-containers.yml` imports `service-check-containers`, which restarts only the containers whose
definition or files changed, and the handlers lost their `kolla_action != "config"` guard
([Tags §2.4](../../risk/tags.md#24-loop-notify-is-gone-in-20251-code)). `reconfigure` and `upgrade` always run with
`kolla_serial=0` ([F19](../findings.md#f19)). The RabbitMQ queue settings (quorum queues, transient quorum queues,
`use_queue_manager`) are always rendered and `/dev/shm` is always mounted where the queue manager used to add it
([F17](../findings.md#f17)). Octavia's jobboard can use Valkey, Manila loses the Linux Bridge driver branch, and the
Ceph users, pools and keyrings of Manila follow the new `ceph_*` variables.

Common facts used throughout:
- Every role below has `tasks/main.yml` = `include_tasks: "{{ kolla_action }}.yml"` (for example
  `ansible/roles/barbican/tasks/main.yml:2`). **No role has a meta dependency on `common`**: no role in
  `ansible/roles/` has a `meta/` directory, and `common` is its own play tagged `common` (`ansible/site.yml:88-103`).
  The roles `chrony`, `skydive`, `nova-hyperv` and `monasca` still do not exist, and **removed in 2025.1, neither does
  `swift`** (sections 3 and 5.10 to 5.13).
- The container module is `kolla_container` (`ansible/library/kolla_container.py`, see
  [Repository architecture §6](../../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)). Bootstrap containers are started with `kolla_container action=start_container detach=False restart_policy=oneshot` (for example `ansible/roles/barbican/tasks/bootstrap_service.yml:6-17`); a `oneshot` container is started directly, without a systemd unit (`ansible/module_utils/kolla_docker_worker.py:390-400`). `remove_on_exit` defaults to `True` (`ansible/library/kolla_container.py:312`; `ansible/module_utils/kolla_docker_worker.py:402-421`), so a bootstrap container (DB sync) is created afresh and **re-runs on every deploy/reconfigure** for any role whose `deploy.yml` imports `bootstrap.yml`.
- **Changed in 2025.1:** the Python CLI passes `kolla_serial` only for `reconfigure` and `upgrade`, and only as the
  constant `ANSIBLE_SERIAL = 0` (`kolla_ansible/cli/commands.py:22,136,278`). A batched run is
  `deploy -e kolla_serial=N`; then, in every play, `run_once` tasks (keystone registration, DB bootstrap) run once per
  batch: each batch is a separate run of the play, and a `run_once` task is queued for the first host of the batch only
  (ansible-core 2.18.20 `lib/ansible/executor/playbook_executor.py:179-204`,
  `lib/ansible/plugins/strategy/linear.py:126,195,216`).
- Every play below sets `max_fail_percentage` (default 100, for example `ansible/site.yml:859-862` for barbican); with
  100 it never stops a play early (see [Repository architecture](../../concepts/repository-architecture.md)).
- The transport URLs are global host lists:
  `ansible/group_vars/all.yml:274`
  `rpc_transport_url: "{{ om_rpc_transport }}://{% for host in groups[om_rpc_group] %}...{% endfor %}/{{ om_rpc_vhost }}"` with `om_rpc_group: "rabbitmq"` (`ansible/group_vars/all.yml:271`). Similarly `notify_transport_url` at `ansible/group_vars/all.yml:284` with `om_notify_group: "rabbitmq"` (`ansible/group_vars/all.yml:281`).
- **Changed in 2025.1, common to most roles below:** `use_queue_manager`, `rabbit_quorum_queue` and
  `rabbit_transient_quorum_queue` are always rendered in the `[oslo_messaging_rabbit]` section of the barbican,
  octavia, manila, ceilometer, zun, cyborg and masakari templates (for example
  `ansible/roles/barbican/templates/barbican.conf.j2:86-98`), and the `/dev/shm` volume is no longer conditional: the
  first 2025.1 run changes these configs and recreates the containers ([F17](../findings.md#f17)). The systemd unit
  template changed again (`PartOf=kolla.target`), so the first 2025.1 check of a container whose unit 2024.1 wrote
  reports a difference ([F16](../findings.md#f16)).

---

## 1. Barbican

### 1.1 Plays in site.yml

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| loadbalancer include | `ansible/site.yml:128-132` | `loadbalancer` (the "Apply role loadbalancer" play, `ansible/site.yml:105-114`) | `barbican` (`include_role tasks_from: loadbalancer`, `when: enable_barbican`). The whole block applies only when `enable_haproxy` and `kolla_action in ['deploy','reconfigure','upgrade','config']` (`ansible/site.yml:325-327`) |
| Apply role barbican | `ansible/site.yml:851-865` | `barbican-api`, `barbican-keystone-listener`, `barbican-worker`, `&enable_barbican_True` | `barbican`; `serial: kolla_serial` (`ansible/site.yml:858`) |

Default inventory: all three groups are children of `barbican`, which has `control` as its child
(`ansible/inventory/multinode:122-123,329-336`).

### 1.2 Services (`ansible/roles/barbican/defaults/main.yml:2-46`)

| Service | Container | Group | Enabled | Notable |
|---|---|---|---|---|
| barbican-api | `barbican_api` | barbican-api | `true` | haproxy `barbican_api` (internal) and `barbican_api_external`, both with `tls_backend: barbican_enable_tls_backend` and, new in 2025.1, `option httpchk` (`defaults/main.yml:11-30`). Named volume `barbican:/var/lib/barbican/` (`defaults/main.yml:140`) |
| barbican-keystone-listener | `barbican_keystone_listener` | barbican-keystone-listener | `true` | no haproxy |
| barbican-worker | `barbican_worker` | barbican-worker | `true` | no haproxy |

**Changed in 2025.1:** each service always mounts `/dev/shm` (`defaults/main.yml:142,149,156`).
Keystone registration: service type `key-manager` (`defaults/main.yml:190-196`), user `barbican` with admin on
`service` (`defaults/main.yml:198-202`), and roles `key-manager:service-admin`, `creator`, `observer`, `audit`
(`defaults/main.yml:170-173,204-208`, `ansible/roles/barbican/tasks/register.yml:2-8`).

### 1.3 Task flow per kolla_action

- **deploy** (`ansible/roles/barbican/tasks/deploy.yml:1-14`): register.yml (keystone) → config.yml →
  check-containers.yml (compare_container, notify restart of the changed containers) → clone.yml (dev mode only) →
  bootstrap.yml → flush handlers.
- **reconfigure** = deploy (`ansible/roles/barbican/tasks/reconfigure.yml:2`). So keystone registration and the DB
  bootstrap container **re-run on every reconfigure**. Still holds in 2025.1.
- **upgrade** (`ansible/roles/barbican/tasks/upgrade.yml:1-9`): config → check-containers → bootstrap_service (DB sync
  only, no DB/user creation) → flush. No keystone re-registration.
- **stop / pull / precheck / deploy-containers / loadbalancer / config_validate** use the standard helpers
  (`kolla-ansible validate-config` sets `kolla_action=config_validate`, `kolla_ansible/cli/commands.py:145-155`).
  **New in 2025.1:** `check.yml` imports `service-check` (`ansible/roles/barbican/tasks/check.yml:2-4`).

### 1.4 Config files, overrides, handlers (`ansible/roles/barbican/tasks/config.yml`)

**Changed in 2025.1:** no task below notifies; the container check decides the restart.

| Output on host | Source and override chain |
|---|---|
| `/etc/kolla/<svc>/config.json` | `templates/<svc>.json.j2` (`config.yml:49-55`) |
| `/etc/kolla/barbican-api/vassals/barbican-api.ini` (uwsgi) | merge: role template → `{{node_custom_config}}/barbican-api/barbican-api.ini` → `.../barbican-api/<host>/barbican-api.ini` (`config.yml:57-68`) |
| `/etc/kolla/barbican-api/barbican-api-paste.ini` | only if `{{node_custom_config}}/barbican/barbican-api-paste.ini` exists (`config.yml:70-90`) |
| `/etc/kolla/<svc>/barbican.conf` | merge: template → `global.conf` → `barbican.conf` → `barbican/<svc>.conf` → `barbican/<host>/barbican.conf` (`config.yml:92-105`) |
| policy file | first found in `{{node_custom_config}}/barbican/` (`config.yml:26-43,107-115`) |

Handlers (`ansible/roles/barbican/handlers/main.yml:2-42`): `recreate_or_restart_container` for each of the 3 services,
with no `kolla_action` guard any more.

### 1.5 Dependencies (from templates)

- MariaDB: `[database] connection`, with `connection_recycle_time`, `max_pool_size` and `max_retries = -1`
  (`ansible/roles/barbican/templates/barbican.conf.j2:18-22`). The DB is created via
  `kolla_toolbox mysql_db/mysql_user`, delegated to `groups['barbican-api'][0]`
  (`ansible/roles/barbican/tasks/bootstrap.yml:2-36`). The login user is `barbican_database_shard_root_user`
  (`defaults/main.yml:65`), which is `root_shard_<id>` when `enable_proxysql` is set (the 2025.1 default).
- RabbitMQ: `transport_url = {{ rpc_transport_url }}` (`barbican.conf.j2:16`) and the notifications transport
  (`barbican.conf.j2:77-84`). The notifications driver is `messagingv2` with topic `notifications` when
  `enable_ceilometer`, otherwise `noop` (`barbican.conf.j2:79-84`; `defaults/main.yml:213-217`). Barbican does **not**
  use the `service-rabbitmq` role.
- Memcached: `memcached_servers` loops over `groups['memcached']` (`barbican.conf.j2:75`).
- Keystone: authtoken (`barbican.conf.j2:60-75`), with `www_authenticate_uri = keystone_public_url` (changed in 2025.1,
  `barbican.conf.j2:62`). **Keystone notifications are coupled**: `[keystone_notifications] enable = true`, and
  `topic = barbican_notifications` when `enable_keystone` (`barbican.conf.j2:54-58`). The keystone role adds the
  `barbican_notifications` topic when `enable_barbican` is set (`ansible/roles/keystone/defaults/main.yml:193-194`).
- Consumers: cinder (`ansible/roles/cinder/templates/cinder.conf.j2:262-267`), glance
  (`ansible/roles/glance/templates/glance-api.conf.j2:140-145`), nova and nova-cell
  (`ansible/roles/nova-cell/templates/nova.conf.j2:249-254`, so **compute** `nova.conf` changes when barbican is
  enabled), octavia (`ansible/roles/octavia/templates/octavia.conf.j2:21-25`), magnum, tacker and skyline (templates
  that test `enable_barbican`).

### 1.6 Operationally notable

- **The crypto KEK lives in passwords.yml.** `barbican_crypto_plugin: "simple_crypto"`
  (`ansible/group_vars/all.yml:1154`), and `kek = '{{ barbican_crypto_key }}'` (`barbican.conf.j2:48-50`;
  `etc/kolla/passwords.yml:56`). `kolla-genpwd` generates it as a Fernet key (`kolla_ansible/cmd/genpwd.py:100-101,158`)
  and only fills empty values (`kolla_ansible/cmd/genpwd.py:91`). **NOT AVAILABLE:** whether losing or changing
  `barbican_crypto_key` makes stored secrets undecryptable (simple_crypto semantics are Barbican code, which is not in
  the sources). This key must be in the passwords.yml backup.
- p11_crypto: the library path `/usr/lib/libCryptoki2_64.so` (`ansible/group_vars/all.yml:1155`) is used only in the
  conf template (`barbican.conf.j2:37`) and is not mounted into the containers (`defaults/main.yml:136-156`). No task
  generates the MKEK or HMAC keys: a grep for `mkek|gen_hmac|barbican-manage` in `ansible/` finds only the conf template
  (`barbican.conf.j2:41,43`). On the image side, changed in 2025.1, the `barbican` user also joins the `hsmusers` group
  (kolla `docker/barbican/barbican-base/Dockerfile.j2:10`). **NOT AVAILABLE:** what else an HSM setup needs (for
  example a custom image or extra volumes, plus manual key generation).
- Running `kolla-ansible deploy -t barbican` alone does not run the keystone play, so the `barbican_notifications` topic
  is not enabled in keystone.conf. **NOT AVAILABLE:** whether barbican-keystone-listener then receives project-deletion
  events.
- Copying the policy file uses `become: true` (`config.yml:112`). That is fine.

---


## 2. Octavia

### 2.1 Plays

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| loadbalancer include | `ansible/site.yml:266-270` | loadbalancer | `octavia` |
| Apply role octavia | `ansible/site.yml:979-994` | `octavia-api`, `octavia-health-manager`, `octavia-housekeeping`, `octavia-worker`, `&enable_octavia_True` | `octavia`; serial `kolla_serial` default `"0"` (`:987`) |

Default inventory: all five groups (`octavia-api`, `octavia-driver-agent`, `octavia-health-manager`,
`octavia-housekeeping`, `octavia-worker`) are children of `octavia`, which is `control`
(`ansible/inventory/multinode:161-162,456-469`). The play still does not list `octavia-driver-agent`; with the default
inventory its hosts are the same control hosts.

### 2.2 Services (`ansible/roles/octavia/defaults/main.yml:2-57`)

`octavia_api` (haproxy `octavia_api`/`octavia_api_external` on port 9876, with `listen_port`, `tls_backend` and, on the
external entry, `external_fqdn` and `octavia_api_public_port`, `:11-26`), `octavia_driver_agent`
(`enabled: enable_octavia_driver_agent`, `:27-33`; default: only with `neutron_plugin_agent: ovn`,
`ansible/group_vars/all.yml:949`), `octavia_health_manager`, `octavia_housekeeping`, `octavia_worker`. The other four
have `enabled: true`, and none has privileged or special flags. **Changed in 2025.1:** `/dev/shm` is always mounted into all five; in 2024.1 it came only with
`om_enable_queue_manager` (`defaults/main.yml:192,200,207,215,222`).
Keystone: service type `load-balancer` (`defaults/main.yml:252-258`). User `octavia` is given admin on `service`
**and** on `{{ octavia_service_auth_project }}`, default `service` (`defaults/main.yml:241,260-271`). Five
`load-balancer_*` roles are created (`defaults/main.yml:59-64`, `tasks/register.yml:1-21`).

### 2.3 Task flow

- **deploy** (`tasks/deploy.yml:1-19`): register → **prepare.yml** when `octavia_auto_configure` (see 2.5) →
  **config-host.yml** (the health-manager interface when `octavia_network_type: tenant`, `tasks/config-host.yml:2-6`) →
  config → check-containers → clone (dev mode only) → bootstrap → flush. Bootstrap creates two databases and two users,
  `octavia` and `octavia_persistence`, before the `bootstrap_octavia` container (`tasks/bootstrap.yml:2-74`;
  `defaults/main.yml:80`).
- **reconfigure** = deploy (`tasks/reconfigure.yml:2`), so the DB sync, keystone registration and, with
  `octavia_auto_configure`, the resource creation re-run.
- **upgrade** (`tasks/upgrade.yml:1-9`): config → check-containers → bootstrap_service → flush. **Changed in 2025.1:**
  upgrade no longer creates the `octavia_persistence` database and its user; it relies on the 2024.1 upgrade (or a
  `deploy`) having created them. Upgrade still does **not** run register.yml, prepare.yml or config-host.yml, and there
  is still no task that removes a role from the octavia user.
  - With `octavia_auto_configure` on, `upgrade` (like every action that runs config.yml, `genconfig` included) still
    runs `get_resources_info.yml` first (`tasks/config.yml:2-3`), which looks up the flavor, project, security groups
    and network by name; the repo doc says genconfig and check mode need access to the Nova and Neutron APIs for this
    (`doc/source/reference/networking/octavia.rst:136-138`). `ansible/group_vars/all.yml:1409-1411` still says to set
    `octavia_auto_configure: no` and keep the previous Octavia configuration when upgrading from Ussuri. **NOT
    AVAILABLE:** what that lookup does when the resources were created manually under other names (the
    `openstack.cloud` modules are not in these sources).
- **Changed in 2025.1:** `check.yml` imports the generic `service-check` role (`tasks/check.yml:2-4`).
- `kolla-ansible octavia-certificates --check-expiry <days>` only checks the certificates and generates nothing; it is
  now a Python CLI command (`kolla_ansible/cli/commands.py:198-224`, `--check-expiry` at `:205`, extra vars at
  `:217-222`; `ansible/roles/octavia-certificates/tasks/main.yml:10-12,51`).

### 2.4 Config files and handlers (`tasks/config.yml`)

| Output | Source and overrides | Notifies (2025.1) |
|---|---|---|
| (lookup) | `get_resources_info.yml` when `octavia_auto_configure` (`config.yml:2-3`) | – |
| policy file | first-found in `{{node_custom_config}}/octavia/` (`config.yml:15-42`), copied with `become` | none |
| backend TLS certs | `copy-certs.yml` when `octavia_copy_certs` (`config.yml:44-46`) | none |
| config.json | `templates/<svc>.json.j2` (`config.yml:48-54`) | none |
| `octavia-wsgi.conf` (octavia-api) | first-found: `octavia/<host>/octavia-wsgi.conf` → `octavia/octavia-wsgi.conf` → role template (`config.yml:56-68`) | none |
| `octavia.conf` (all services) | merge: template → `global.conf` → `octavia.conf` → `octavia/<svc>.conf` → `octavia/<host>/octavia.conf` (`config.yml:70-83`) | none |
| SSH private key for the amphora keypair | role template `octavia-ssh-key.j2` into octavia-worker, only when `octavia_auto_configure` (`config.yml:87-97`) | none |
| 4 PEM files: `client.cert-and-key.pem`, `client_ca.cert.pem`, `server_ca.cert.pem`, `server_ca.key.pem` | plain `copy` from `{{node_custom_config}}/octavia/` into worker (`config.yml:99-108`), housekeeping (`config.yml:110-119`) and health-manager (`config.yml:121-130`); the block runs only when `'amphora' in octavia_provider_drivers` (`config.yml:132-138`) | none |

**Changed in 2025.1:** none of these tasks notifies a handler. The restart decision is taken by `check-containers`,
which imports `service-check-containers` (`ansible/roles/service-check-containers/tasks/main.yml:4-41`). Handlers
(`ansible/roles/octavia/handlers/main.yml:2-69`) use `recreate_or_restart_container` for each of the five services.
Volumes are passed with `reject('equalto','')` (for example `handlers/main.yml:12`).

### 2.5 OpenStack resources: Kolla creates none

**Still not true by default in 2025.1.** With `octavia_auto_configure` (default: true when `amphora` is in
`octavia_provider_drivers`, which it is by default, `ansible/group_vars/all.yml:1411`;
`octavia_provider_drivers` at `ansible/roles/octavia/defaults/main.yml:387`), `deploy` and `reconfigure` run `prepare.yml`, which creates, `run_once`
and delegated to `groups['octavia-api'][0]`: the amphora flavor (`amphora`, 1 vCPU, 1024 MB, 5 GB, not public,
`defaults/main.yml:320-325`), the nova keypair, the security groups and their rules, the lb-mgmt network and subnet
(`octavia_amp_network_cidr: 10.1.0.0/24`, `defaults/main.yml:380`) and, for IPv6, a router
(`tasks/prepare.yml:2-161`). `kolla-ansible octavia-certificates` generates the certificates
(`kolla_ansible/cli/commands.py:198-224`, `ansible/octavia-certificates.yml`). Kolla still does **not** create the
amphora image. The repo's own doc describes automatic registration as the default ("Option 1: Automatic resource
registration (default, recommended)", `doc/source/reference/networking/octavia.rst:123-138`).
The template consumes the IDs:
- With `octavia_auto_configure`, `amp_image_owner_id`, `amp_boot_network_list`, `amp_secgroup_list` and `amp_flavor_id`
  come from the facts that `get_resources_info.yml` registered (`templates/octavia.conf.j2:104-108`;
  `tasks/get_resources_info.yml:72-75`). With it off, each is written only if the operator defines
  `octavia_amp_image_owner_id`, `octavia_amp_boot_network_list`, `octavia_amp_secgroup_list` or `octavia_amp_flavor_id`
  (`octavia.conf.j2:91-103`); no group default defines them, and **no precheck validates them**:
  `tasks/precheck.yml:1-74` checks only the API and HM ports, the 4 PEM files (when the amphora provider is enabled),
  the neutron plugin for `tenant`, and Redis or Valkey for the jobboard (below).
- `amp_image_tag = {{ octavia_amp_image_tag }}` (default `amphora`) and
  `amp_ssh_key_name = {{ octavia_amp_ssh_key_name }}` (default `octavia_ssh_key`) are variables
  (`octavia.conf.j2:88-89`, `defaults/main.yml:294-296`), but `heartbeat_key = insecure` (`octavia.conf.j2:81`) is still
  a **security oddity** with no variable to change it except an override file.
- `[certificates] ca_private_key_passphrase = {{ octavia_ca_password }}` (`octavia.conf.j2:17-20`) must match the
  `server_ca.key.pem` in use.
- Barbican: if `enable_barbican`, the region and endpoint for the cert manager are set (`octavia.conf.j2:21-25`).
  **NOT AVAILABLE:** whether TLS-terminated listeners need barbican.
- **The jobboard, changed in 2025.1:** `enable_octavia_jobboard` still defaults to true whenever octavia is enabled with
  the amphora provider (`ansible/group_vars/all.yml:950`). The `[task_flow]` section now loops over
  **`groups['valkey']`** when `enable_valkey` is set, else over `groups['redis']` when `enable_redis` is set
  (`octavia.conf.j2:168-186`), with the sentinel name hard-coded as `kolla` (`octavia.conf.j2:183`) and
  `persistence_connection` to the `octavia_persistence` database (`octavia.conf.j2:185`). The precheck now accepts
  either backend (`tasks/precheck.yml:68-74`); both `enable_redis` and `enable_valkey` default to `"no"`
  (`ansible/group_vars/all.yml:959,965`), so **with the defaults, enabling octavia with the amphora provider still fails
  `prechecks` until one of them (or `enable_octavia_jobboard: no`) is set.** If neither is set and `prechecks` was not
  run, the `[task_flow]` section is written with no `jobboard_backend_hosts` line. **NOT AVAILABLE:** what Octavia does
  when the jobboard backend is unreachable, and what happens to running flows when a cloud moves from Redis to Valkey.
- Upgrades from Ussuri: the code comment says to set `octavia_auto_configure: no` and keep the existing configuration
  (`ansible/group_vars/all.yml:1409-1411`). The doc still notes that Train and earlier registered resources in `admin`
  (`octavia.rst:257-263`); `octavia_service_auth_project` defaults to `service` (`defaults/main.yml:241`).

### 2.6 Health-manager network requirements

- `bind_ip = {{ octavia_network_interface_address }}`, `bind_port = {{ octavia_health_manager_port }}` (5555,
  `ansible/group_vars/all.yml:627`) (`octavia.conf.j2:78-80`).
- `controller_ip_port_list` loops over **all** `groups['octavia-health-manager']` using
  `'octavia_network' | kolla_address(host)` (`octavia.conf.j2:82`). This needs facts for every HM host.
- `octavia_network_interface` defaults to `api_interface`, or to `o-hm0` when `octavia_network_type: tenant`
  (`ansible/group_vars/all.yml:303`; `octavia_network_type: "provider"` by default, `:1419`), and the address comes from
  `'octavia_network' | kolla_address` (`all.yml:326`). `kolla_address` raises `FilterError` if the interface or address
  family is missing on the host (`kolla_ansible/kolla_address.py:110-123,155-160`). The `[health_manager]` section is
  rendered into octavia.conf for **all services**, so **every octavia host (api, worker and housekeeping too) must have
  `octavia_network_interface` with an address**, or templating fails.
- With the default `provider` type, Kolla does not create the lb-mgmt interface, bridge or VLAN on the controllers; the
  doc says to bridge it to OVS manually (`doc/source/reference/networking/octavia.rst:88-109`). With
  `octavia_network_type: tenant` (and `octavia_auto_configure`), on each health-manager host Kolla creates a Neutron
  port, adds it to `br-int` through the `openvswitch_vswitchd` container, and installs and starts an `octavia-interface`
  systemd unit (`tasks/config-host.yml:2-6`, `tasks/hm-interface.yml:2-100`); a precheck rejects `tenant` unless
  `neutron_plugin_agent` is `openvswitch` (`tasks/precheck.yml:57-66`).
- Precheck oddity: the HM free-port check uses `api_interface_address`, not `octavia_network_interface_address`
  (`tasks/precheck.yml:30-39`). The two differ only when `octavia_network_interface` is not `api_interface` (for example
  with `tenant`). Still present.
- Adding or removing a health-manager host changes octavia.conf on all octavia hosts; with 2025.1 the restart comes
  from the container check rather than a notify (`octavia.conf.j2:82`; `tasks/config.yml:70-83`). The same holds for a
  host added to or removed from `valkey` or `redis`, through `jobboard_backend_hosts` (`octavia.conf.j2:172,176`).
  **NOT AVAILABLE:** whether the controller list is written into an amphora at boot, so that existing amphorae keep the
  old list until failover.
- Security spread: `server_ca.key.pem` (the CA private key) is copied to the worker, housekeeping **and** health-manager
  config dirs (`tasks/config.yml:99-138`).

### 2.7 Other dependencies

MariaDB (`octavia.conf.j2:41-45`, plus the persistence DB at `:185`), RabbitMQ rpc (`:10`), notify (`:123-130`; driver
`messagingv2` with topic `notifications` when `enable_ceilometer`, else `noop`, `defaults/main.yml:276-280`) and,
**changed in 2025.1**, quorum and transient quorum queues always on, with stream fanout behind
`om_enable_rabbitmq_stream_fanout` (`octavia.conf.j2:132-147`). Memcached ×2 loops (`:59,76`), keystone (`:47-76`,
`www_authenticate_uri = keystone_public_url` at `:63`), glance, neutron (`valid_interfaces = internal`, `:159-162`) and
nova via internal endpoints (`:154-167`), and Valkey or Redis with the jobboard (`:168-186`). With
`neutron_plugin_agent: ovn`, the OVN NB connection and, **changed in 2025.1**, the SB connection that bypasses any OVN
relay, `ovn_sb_connection_no_relay` (`octavia.conf.j2:30-34`; `ansible/group_vars/all.yml:647`). Topology is
`octavia_loadbalancer_topology: "SINGLE"` (`ansible/roles/octavia/defaults/main.yml:299`).

---

## 3. Swift

**Removed in 2025.1.** Kolla Ansible 2025.1 has no `swift` role, no swift play in `ansible/site.yml`, no `enable_swift`
in `ansible/group_vars/all.yml`, and kolla 2025.1 builds no swift image (release note
`releasenotes/notes/remove-swift-5ebd7b5c4a2cb5b7.yaml`). The 2024.1 study of the role (plays, "old-style" services,
ring files, task flow, ports and oddities) is in the
[2024.1 fact sheet D, §3](../../../2024.1/reference/factsheets/d-barbican-octavia-swift-manila-compute-roles/#3-swift).

What this leaves on a cloud upgraded from 2024.1, all listed on the [Swift component page](../../components/swift.md):

- No precheck, stop or removal task looks at a deployed Swift, so the 2024.1 swift containers keep running on their
  2024.1 images, and `enable_swift: yes` left in `globals.yml` raises no error.
- The `swift_api` and `swift_api_external` HAProxy frontend files written by 2024.1 stay in `services.d/` and are still
  served, because `haproxy-config` writes the files of the role it runs for and removes nothing
  (`ansible/roles/haproxy-config/tasks/main.yml:2-21`).
- The Keystone `swift` service of type `object-store` stays registered.
- Glance loses its `swift` store with no check, Cinder backup loses its Swift driver branch, and Horizon loses its Swift
  settings (§1 to §4 of [fact sheet C](c-glance-placement-cinder-horizon-heat.md)).

**NOT AVAILABLE:** whether the old swift containers keep serving correctly once the rest of the control plane is on
2025.1. To be confirmed by the community.

---

## 4. Manila

### 4.1 Plays

| Play | Lines | Hosts | Tags |
|---|---|---|---|
| loadbalancer include | `ansible/site.yml:218-222` | loadbalancer | `manila` |
| **Apply role neutron** | `ansible/site.yml:669-691` | includes **`manila-share`** (`:682`) and `compute` (`:681`) | `neutron` |
| Apply role manila | `ansible/site.yml:784-799` | `manila-api`, `manila-data`, `manila-share`, `manila-scheduler`, `&enable_manila_True` | `manila` |

Default inventory: `manila-share` is a child of **`network`** (`ansible/inventory/multinode:322-323`). The other groups
are under `manila` (control) (`ansible/inventory/multinode:137-138,316-326`). `openvswitch` children include
`manila-share` (`ansible/inventory/multinode:105-108`).

**Why manila-share is in the neutron play:** the agent `host_in_groups` include manila-share hosts.
- OVS agent, only with the generic backend:
  `(enable_manila_backend_generic | bool and inventory_hostname in groups['manila-share'])`
  (`ansible/roles/neutron/defaults/main.yml:40`). openvswitch db and vswitchd have the same condition
  (`ansible/roles/openvswitch/defaults/main.yml:11,27`).
- **Changed in 2025.1:** the Linux Bridge agent is gone, and with it the asymmetry of 2024.1 (where the linuxbridge
  agent ran on manila-share hosts for any backend). The neutron defaults now name `manila-share` only in the OVS
  condition (`ansible/roles/neutron/defaults/main.yml:40`).
- Generic-driver share servers are always plugged with `OVSInterfaceDriver`; the `BridgeInterfaceDriver` branch is
  removed (`ansible/roles/manila/templates/manila-share.conf.j2:73-76`).
- Ordering: the neutron play (`ansible/site.yml:669`) runs before manila (`ansible/site.yml:784`).

### 4.2 Services (`ansible/roles/manila/defaults/main.yml:2-54`)

| Service | Container | Notable |
|---|---|---|
| manila-api | `manila_api` | haproxy port 8786 (`ansible/group_vars/all.yml:534`), `listen_port` on both entries, `external_fqdn`/`manila_api_public_port` on the external one; **new in 2025.1:** `option httpchk` on both backends (`defaults/main.yml:11-28`) |
| manila-scheduler | `manila_scheduler` | — |
| manila-share | `manila_share` | **privileged**, `/run:/run` (`:shared` only with Docker), `/lib/modules:ro`, plus the engine's `run_default_volumes_<engine>` (empty for Docker) (`defaults/main.yml:37-45,162-170`; `ansible/group_vars/all.yml:174-181`). Its handler adds `ipc_mode: host` (`handlers/main.yml:45-56`), which is not in the services dict, so `service-check-containers` does not compare it (`ansible/roles/service-check-containers/tasks/main.yml:21`) |
| manila-data | `manila_data` | **privileged**, `/dev/:/dev/`, `/run` as above (`defaults/main.yml:46-54,185-192`) |

**Changed in 2025.1:** `/dev/shm` is always mounted into `manila_api`, `manila_scheduler` and `manila_share` (not
`manila_data`); in 2024.1 it came only with `om_enable_queue_manager` (`defaults/main.yml:168,176,183`).

Backends: generic, hnas, glusterfsnfs and, **new in 2025.1**, a Pure Storage FlashBlade backend `fb1`, in
`manila_backends` (`defaults/main.yml:222-245`); the two CephFS backends in `manila_ceph_backends`, each with a
`share_name` and a `cluster`, now `"{{ ceph_cluster }}"` (`defaults/main.yml:247-262`); `manila_enabled_backends`
joins both lists (`defaults/main.yml:264`). Each is gated by `enable_manila_backend_*`
(`ansible/group_vars/all.yml:916-921`, all `"no"`).

### 4.3 Task flow

- **deploy** (`tasks/deploy.yml:1-14`): clone (dev) → register (keystone `share` and `sharev2`,
  `defaults/main.yml:289-301`) → config → check-containers → bootstrap (DB, then `bootstrap_manila`,
  `tasks/bootstrap.yml:2-38`) → flush.
- **reconfigure** = deploy (`tasks/reconfigure.yml:2`). **upgrade**: config → check-containers → bootstrap_service →
  flush (`tasks/upgrade.yml:2-9`).
- **Changed in 2025.1:** `check-containers.yml` imports `service-check-containers` (`tasks/check-containers.yml:2-3`),
  which restarts only the containers whose definition or configuration changed; the config tasks notify nothing.
- There is still no `fix_cephfs_owner.yml` (no such file under `ansible/roles/manila/tasks/`, and no task of the role
  mounts CephFS or passes `secret=`). With a CephFS backend, config includes `external_ceph.yml` on manila-share hosts
  (`tasks/config.yml:12-15`), see 4.4.

### 4.4 Config (`tasks/config.yml`)

| Output | Chain | Notifies (2025.1) |
|---|---|---|
| A `manila-share/ceph/` sub-directory (`external_ceph.yml:2-12`), then per enabled entry of `manila_ceph_backends`: `ceph/<cluster>.conf` **merged** from `{{node_custom_config}}/manila/<cluster>.conf` and `.../manila/manila-share/<cluster>.conf` (`external_ceph.yml:14-25`), and the keyring `ceph/<cluster>.client.<ceph_manila_user>.keyring` templated from `{{node_custom_config}}/manila/<cluster>.client.<ceph_manila_user>.keyring` (`external_ceph.yml:27-36`; `ceph_manila_user: "manila"`, `ansible/group_vars/all.yml:1303`); only with `enable_manila_backend_cephfs_native` or `_cephfs_nfs` on manila-share hosts (`config.yml:12-15`) | For the default cluster `ceph` the operator file names stay `ceph.conf` and `ceph.client.manila.keyring`; `config.json` copies the whole `ceph/` directory to `/etc/ceph` (`templates/manila-share.json.j2:9-15`) and the backend sections read `/etc/ceph/<cluster>.conf` (`manila-share.conf.j2:116-151`). **Changed in 2025.1:** `ceph_manila_keyring` is gone; an override of it is no longer read | none |
| backend CA bundle | `copy-certs.yml` when `kolla_copy_ca_into_containers` (`config.yml:36-38`) | none |
| config.json | `config.yml:40-46` | none |
| manila.conf (api, data, scheduler) | template → global.conf → manila.conf → `manila/<svc>.conf` → `manila/<host>/manila.conf` (`config.yml:48-63`) | none |
| manila-share manila.conf | `manila.conf.j2` **+** `manila-share.conf.j2` → global.conf → manila.conf → `{{node_custom_config}}/manila-share.conf` → manila/manila-share.conf → `manila/<host>/manila.conf` (`config.yml:65-83`) | none |
| policy | `config.yml:85-93`, **now with `become: true`** | none |

The restart decision is taken by the container check: a changed file restarts the container on that host
([Tags §2.4](../../risk/tags.md#24-loop-notify-is-gone-in-20251-code)).

### 4.5 Dependencies

- MariaDB (`manila.conf.j2:27-29`), RabbitMQ rpc (`manila.conf.j2:22`) and notify (`manila.conf.j2:50-51`), quorum
  queues always on (`manila.conf.j2:59-71`), memcached (`manila.conf.j2:48`).
- manila-share.conf additionally loops over memcached 3× (`manila-share.conf.j2:35,52,70`) and holds **glance, cinder,
  nova and neutron service-user passwords** (`manila-share.conf.j2:8-70`).
- Ceph is external only: there is no ceph deployment role in 2025.1 (`ansible/roles/` has no `ceph` role; only
  `ceph-rgw`, which has "no container deployment" and only configures the load balancer,
  `ansible/roles/ceph-rgw/defaults/main.yml:2-4`). The config is supplied by the operator (`external_ceph.yml`).

### 4.6 Operationally notable

- Kolla does not create share types, the service image or networks (no such task under `ansible/roles/manila/tasks/`).
  `default_share_type = default_share_type` is hard-coded (`manila-share.conf.j2:6`) and
  `service_image_name = manila-service-image` (`manila-share.conf.j2:83`).
- The generic backend's service-instance credentials default to `manila`/`manila` (`defaults/main.yml:212-213`,
  `manila-share.conf.j2:81-82`).
- Endpoints use `manila_internal_fqdn`/`manila_external_fqdn` through the `kolla_url` filter
  (`ansible/group_vars/all.yml:530-535`; role endpoints at `ansible/roles/manila/defaults/main.yml:203-207`), as since
  2024.1.
- The Ceph share sections loop over every entry of `manila_ceph_backends` whose `driver` matches, guarded only by the
  global flag, while the file tasks skip disabled entries (`external_ceph.yml:24,36`). **NOT AVAILABLE:** how Manila
  behaves with an operator-defined list where the two disagree.

---

## 5. Other roles that deploy containers onto `compute` hosts

Default multinode membership (compute ∈): collectd (`ansible/inventory/multinode:56-57`), telegraf
(`ansible/inventory/multinode:71-76`), hacluster-remote (`ansible/inventory/multinode:81-82`), cyborg-agent
(`ansible/inventory/multinode:414-415`), iscsid (`ansible/inventory/multinode:307-310`), ceilometer-compute and
ceilometer-ipmi (`ansible/inventory/multinode:391-395`), multipathd (`ansible/inventory/multinode:441-443`), zun-compute
and zun-cni-daemon (`ansible/inventory/multinode:504-508`), prometheus-node-exporter, prometheus-cadvisor and
prometheus-libvirt-exporter (`ansible/inventory/multinode:532-537,545-550,564-565`), masakari-instancemonitor
(`ansible/inventory/multinode:576-577`), ovn-controller-compute (`ansible/inventory/multinode:583-584`). The kuryr play
targets `compute` directly (`ansible/site.yml:693-705`). **Changed in 2025.1:** the `cyborg` parent group is `control`
only (`ansible/inventory/multinode:146-147`); in 2024.1 it also held `compute`, which put the cyborg-api and
cyborg-conductor groups on computes. There is still **no `chrony`, `skydive-agent`, `hyperv` or `monasca-agent` group**.

What changed for every role below in 2025.1 (the cross-cutting facts are in [fact sheet C
§0](c-glance-placement-cinder-horizon-heat.md#0-cross-cutting-facts-apply-to-all-five-roles)): the config tasks notify nothing,
and `check-containers.yml` imports `service-check-containers`, which compares each container with its definition and
configuration and notifies the restart handler only for the containers that differ
(`ansible/roles/service-check-containers/tasks/main.yml:4-41`). Each role also has a `check.yml` for
`kolla-ansible check`. On the first 2025.1 run, a container that no 2025.1 run has recreated yet is flagged by the
changed systemd unit text ([F16](../findings.md#f16)).

Podman note (since 2024.1): the compute-side containers that mount `/run` (ceilometer_compute, iscsid, tgtd,
multipathd, zun_compute, zun_cni_daemon, kuryr) mount it `:shared` only when `kolla_container_engine == 'docker'` and
add `run_default_volumes_<engine>`, which is empty for Docker (for example
`ansible/roles/iscsi/defaults/main.yml:46`; `ansible/group_vars/all.yml:174-181`).

### 5.0 Summary table (compute-side)

| Role (enable flag, default) | Compute containers | Restart trigger (2025.1) | Config: per-host or global? | Data-plane / VM impact |
|---|---|---|---|---|
| ceilometer (`enable_ceilometer` no; ipmi `enable_ceilometer_ipmi` no, `ansible/group_vars/all.yml:856-857`) | `ceilometer_compute` (privileged, `/run`, `nova_libvirt` volume), `ceilometer_ipmi` | container check | **Global**: rabbit rpc and notify, memcached | VM impact NOT AVAILABLE (`ceilometer_compute` runs only `ceilometer-polling`, `ansible/roles/ceilometer/templates/ceilometer-compute.json.j2:2`) |
| iscsi (`enable_iscsid` derived, `ansible/group_vars/all.yml:911`) | `iscsid` (privileged, ipc host, `/dev`, `/run`, `/sys/kernel/config`, `iscsi_info:/etc/iscsi`) | container check | Per-host (config.json only) | **Risk topic**, outcome NOT AVAILABLE; see 5.2 |
| multipathd (`enable_multipathd` no) | `multipathd` (privileged, ipc host) | container check | Per-host (role template or operator override) | **Risk topic**, outcome NOT AVAILABLE; see 5.3 |
| collectd (no) | `collectd` (privileged, `/sys`, `/dev` ro) | container check | Per-host | none |
| telegraf (no) | `telegraf` (pid host, docker.sock ro) | container check | **Global**: influxdb hosts | none |
| prometheus (no) | `prometheus_node_exporter` (pid host, `/:/host:ro,rslave`), `prometheus_cadvisor` (`/var/run:rw`, `/var/lib/docker:ro`), `prometheus_libvirt_exporter` (`/run/libvirt:ro`; enabled with prometheus when nova uses kvm or qemu, `ansible/group_vars/all.yml:1344`) | container check | Per-host on compute. The **server** config lists every compute | none on compute; prometheus_server restarts when computes are added |
| masakari (no) | `masakari_instancemonitor` (privileged) | container check | Per-host | none directly; see 5.6 |
| hacluster (`enable_hacluster` = `enable_masakari_hostmonitor` = `enable_masakari`, `ansible/group_vars/all.yml:885,925`) | `hacluster_pacemaker_remote` (ipc host) | container check | Per-host (shared Pacemaker authkey) | NOT AVAILABLE; see 5.15 |
| zun (no) | `zun_compute` (privileged, `/var/lib/docker`, `/dev`, `/run`), `zun_cni_daemon` (privileged) | container check, plus a loopback copy on a zun-cni-daemon restart | **Global**: rabbit rpc, memcached ×2, **DB creds** | container workloads, outcome NOT AVAILABLE; see 5.7 |
| kuryr (no) | `kuryr` (privileged, NET_ADMIN, `/run`, `/usr/lib/docker`) | container check | Per-host | docker network ops, outcome NOT AVAILABLE; see 5.8 |
| cyborg (no) | `cyborg_agent` (privileged) | container check | **Global**: rabbit rpc and notify, memcached, **DB creds**, placement and nova creds | none |
| skydive | **no role** (see 5.10) | – | – | – |
| monasca | **no role** (see 5.11) | – | – | – |
| chrony | **no role** (see 5.12) | – | – | – |
| nova-hyperv | **no role** (see 5.13) | – | – | – |
| (cross-ref) ovn-controller | `ovn_controller` | ovn-controller role | **Global**: `ovn-remote` = SB relay or SB host list | out of scope |

### 5.1 ceilometer

- Play: `ansible/site.yml:817-832`, hosts central, notification, compute, ipmi.
- Services: `ansible/roles/ceilometer/defaults/main.yml:2-35`. Compute volumes include `/run` and
  `{{ ceilometer_libvirt_volume }}:/var/lib/libvirt` (`ansible/roles/ceilometer/defaults/main.yml:137-146`), where
  `ceilometer_libvirt_volume` is `nova_libvirt` with the libvirt container and `/var/lib/libvirt` otherwise
  (`ansible/roles/ceilometer/defaults/main.yml:162`). ceilometer-ipmi has no `/dev` mount and is not privileged
  (`ansible/roles/ceilometer/defaults/main.yml:28-35,147-154`). **NOT AVAILABLE:** whether local IPMI (`/dev/ipmi0`)
  is reachable from it.
- **Changed in 2025.1:** the healthchecks of `ceilometer_central` and `ceilometer_compute` are switched off by default
  (`ceilometer_central_enable_healthchecks: "false"`, `ceilometer_compute_enable_healthchecks: "false"`,
  `ansible/roles/ceilometer/defaults/main.yml:83,96`), so both containers are recreated without a healthcheck on the
  first 2025.1 run; `/dev/shm` is always mounted (`ansible/roles/ceilometer/defaults/main.yml:144`). The keystone task
  that gave the ceilometer user the `ResellerAdmin` role when Swift was enabled is gone with Swift (§3).
- Flow: deploy = register → config → check-containers → clone → bootstrap → flush. `bootstrap.yml` still has a
  `TODO(Jeffrey4l): fix idempotent` comment (`ansible/roles/ceilometer/tasks/bootstrap.yml:2`) and **always runs** the
  `bootstrap_ceilometer` container (ceilometer-upgrade, with the database type `gnocchi` when gnocchi is enabled,
  `ansible/roles/ceilometer/defaults/main.yml:196`), delegated to the first `ceilometer-notification` host
  (`ansible/roles/ceilometer/tasks/bootstrap_service.yml:2-22`).
- Config: `ceilometer.conf` merge chain at `ansible/roles/ceilometer/tasks/config.yml:172-185`. The template carries
  `transport_url = rpc_transport_url` (`ansible/roles/ceilometer/templates/ceilometer.conf.j2:6`),
  `notify_transport_url` (`ceilometer.conf.j2:36`) and `memcache_servers` over `groups['memcached']`
  (`ceilometer.conf.j2:60`). The same file is rendered for ceilometer-compute on **every compute**, so a rabbitmq or
  memcached membership change restarts `ceilometer_compute` on every compute. `event_pipeline.yaml` is a `merge_yaml`
  of the role template, the operator file and a per-host file (`ansible/roles/ceilometer/tasks/config.yml:220-231`).
- Scaling oddities, still present:
  - Several `delegate_to: localhost` stat/find tasks still **lack `run_once`**: custom meters
    (`ansible/roles/ceilometer/tasks/config.yml:12-28`), polling.yaml (`config.yml:95-99`), gnocchi_resources
    (`config.yml:118-122`), event_definitions (`config.yml:187-191`), pipeline (`config.yml:233-237`). That is roughly
    6 local tasks per host, multiplied by the compute count.
  - "Clean default folder for dynamic pollsters definitions" has **no `become` and no host condition**
    (`config.yml:68-71`). It deletes `/etc/kolla/ceilometer-central/pollsters.d/` on every run, then recreates and
    recopies it (`config.yml:73-93`). **NOT AVAILABLE:** whether the container check then sees a difference and
    restarts ceilometer-central on every deploy or reconfigure when `pollsters.d` exists.
- Precheck: an `assert` still requires gnocchi **or** `enable_ceilometer_prometheus_pushgateway` when ceilometer is
  enabled (`ansible/roles/ceilometer/tasks/precheck.yml:8-14`).

### 5.2 iscsi (iscsid, tgtd)

- Play: `ansible/site.yml:454-467`, hosts `iscsid`, `tgtd`, `&enable_iscsid_True`.
- `enable_iscsid` is `enable_cinder and enable_cinder_backend_iscsi` (`ansible/group_vars/all.yml:911`), and
  `enable_cinder_backend_iscsi` defaults to `enable_cinder_backend_lvm` (`ansible/group_vars/all.yml:865-866`).
- Per-host enablement (`ansible/roles/iscsi/defaults/main.yml:62-73`): iscsid runs on compute, cinder-backup or
  cinder-volume hosts only when cinder and the iscsi backend are enabled, or on ironic-conductor hosts with ironic. tgtd
  runs only with the LVM backend and `cinder_target_helper == tgtadm`. Since the play only targets `&enable_iscsid_True`
  hosts, ironic without the cinder iSCSI backend gets no iscsid.
- Containers (`ansible/roles/iscsi/defaults/main.yml:2-20`): both privileged, `ipc_mode: host`, with volumes `/dev`,
  `/run` (`:shared` with Docker), `/lib/modules:ro`, `/sys/kernel/config:/configfs`, and, for iscsid only,
  `iscsi_info:/etc/iscsi` (`ansible/roles/iscsi/defaults/main.yml:40-58`).
- Config: config.json only. The iscsid command is still `iscsid -d 8 -f`
  (`ansible/roles/iscsi/templates/iscsid.json.j2:2`), which is **debug level 8, very verbose**. So the container
  restarts only on a config.json, image, volume or dimension change, in practice an **upgrade or pull of a new tag**,
  and once on the first 2025.1 run for the changed systemd unit text. The flow for deploy, upgrade and reconfigure is
  config-host (loads `configfs`, `ansible/roles/iscsi/tasks/config-host.yml:2-10`) → config → check-containers →
  flush (`ansible/roles/iscsi/tasks/deploy.yml:1-8`; `upgrade.yml` imports deploy).
- **Host interaction:** bootstrap-servers **removes host `open-iscsi`** on Debian/Ubuntu always, and
  `iscsi-initiator-utils` on RedHat only when `enable_nova_libvirt_container` (ansible-collection-kolla
  `roles/packages/defaults/main.yml:22-31`, applied by ansible-collection-kolla `roles/packages/tasks/main.yml:14-22`).
  **NOT AVAILABLE:** whether computes then have no iscsid at all when `enable_iscsid` is false (no cinder iSCSI
  backend, for example a third-party iSCSI SAN).
- **VM impact (NOT AVAILABLE):** whether iSCSI sessions survive an iscsid restart, and whether session recovery or
  re-login after a path or portal failure, and os-brick attach/detach from nova-compute, fail or stall while iscsid is
  down. The `iscsi_info` named volume holds the initiator IQN (kolla `docker/iscsid/extend_start.sh:3-7`). **NOT
  AVAILABLE:** whether recreating the volume (for example after `destroy`) changes the IQN and breaks array ACLs.
- **tgtd restart (consequences NOT AVAILABLE):** the command is only `tgtd -d 1 -f --iscsi portal=...` with empty
  `config_files` (`ansible/roles/iscsi/templates/tgtd.json.j2:2-3`); the portal address is `tgtd_interface_address`,
  default `api_interface_address` (`ansible/roles/iscsi/defaults/main.yml:22`). The image only inserts
  `include /var/lib/cinder/volumes/*` into `/etc/tgt/targets.conf` (kolla `docker/tgtd/Dockerfile.j2:19`), and
  nothing runs `tgt-admin` at start. The tgtd container does **not** mount the `cinder` volume
  (`ansible/roles/iscsi/defaults/main.yml:50-58`). **NOT AVAILABLE:** whether a tgtd restart drops every exported LVM
  target and its sessions until cinder-volume re-creates them, and whether I/O to attached LVM volumes stalls or fails
  meanwhile. The precheck fails on RedHat-family hosts when tgtd is enabled
  (`ansible/roles/iscsi/tasks/precheck.yml:30-36`). See
  [Kolla images §5](../../concepts/kolla-images.md#5-per-image-start-behaviour).
- Precheck oddity, still present: it checks that `iscsi_port` 3260 is free on the **iscsid** hosts, probing
  `tgtd_interface_address` (`ansible/roles/iscsi/tasks/precheck.yml:18-28`), but 3260 is the **target** (tgtd) port.
  **Changed in 2025.1:** the "is iscsid already running" test now reads `container_facts.containers['iscsid']`
  (`ansible/roles/iscsi/tasks/precheck.yml:26`).

### 5.3 multipathd

- Play: `ansible/site.yml:469-481`. Default `enable_multipathd: "no"` (`ansible/group_vars/all.yml:927`).
- Container: privileged, ipc host, with `/dev`, `/run` (`:shared` with Docker), `/lib/modules:ro`,
  `/sys/kernel/config:/configfs` (`ansible/roles/multipathd/defaults/main.yml:2-28`). It does not mount `iscsi_info` or
  `cinder`. There are still **no `dimensions`**.
- Config: `multipath.conf` is **first-found** from `{{node_custom_config}}/multipath/<host>/multipath.conf`, then
  `{{node_custom_config}}/multipath.conf`, then the role template
  (`ansible/roles/multipathd/tasks/config.yml:20-32`). The role template is `user_friendly_names no`,
  `find_multipaths yes`, `skip_kpartx yes`, and an empty blacklist
  (`ansible/roles/multipathd/templates/multipath.conf.j2:1-8`).
- The `dm-multipath` module is loaded by config-host (`ansible/roles/multipathd/tasks/config-host.yml:2-7`).
- Restart: when the container check finds a changed config.json or multipath.conf, or a changed image or volume.
- **VM impact (NOT AVAILABLE):** whether dm maps persist across a restart, whether path checking and failback pause
  while multipathd is down, and whether a path failure in that window causes I/O errors or queueing depending on
  `no_path_retry`. Restarts run in the same handler step on all notified multipathd hosts of the batch: at
  `flush_handlers` the notified hosts switch to the handlers state (ansible-core 2.18.20
  `lib/ansible/plugins/strategy/__init__.py:951-971`), and the linear strategy inserts the play's handlers like tasks
  for every such host (`lib/ansible/plugins/strategy/linear.py:87-88`); with serial 0 the batch is every host
  (`lib/ansible/executor/playbook_executor.py:294-296`).

### 5.4 collectd and telegraf

- collectd: play `ansible/site.yml:343-355`. Privileged, `/sys` and `/dev` ro
  (`ansible/roles/collectd/defaults/main.yml:8,27-28`). collectd.conf is first-found (host → global → role template),
  with no merge (`ansible/roles/collectd/tasks/config.yml:30-43`). The default sends to
  `{{ 'api' | kolla_address }}:{{ collectd_udp_port }}`, i.e. its own host
  (`ansible/roles/collectd/templates/collectd.conf.j2:9-11`), where telegraf's `socket_listener` receives it if
  telegraf is enabled (`ansible/roles/telegraf/templates/telegraf.conf.j2:29-35`). Per-host only.
- telegraf: play `ansible/site.yml:371-383`. `pid_mode: host`, `/proc` and `/sys` ro, `/var/run/docker.sock:ro`
  (`ansible/roles/telegraf/defaults/main.yml:2-10,20-27`). telegraf.conf is first-found, not merged
  (`ansible/roles/telegraf/tasks/config.yml:24-36`). It **loops over `groups['influxdb']`**
  (`ansible/roles/telegraf/templates/telegraf.conf.j2:14-17`), so adding or removing an influxdb host restarts
  telegraf on every host. The haproxy and opensearch inputs test the `loadbalancer` and `opensearch` groups
  (`telegraf.conf.j2:50,58`).
  - **Fixed in 2025.1:** the "Copying over telegraf plugin files" task now tests the telegraf service, not
    `item.value.enabled` inside a loop of path strings (`ansible/roles/telegraf/tasks/config.yml:38-48`).
  - Still present: the container check does not compare the `HOST_PROC`/`HOST_SYS` environment, which only the
    handler passes (`ansible/roles/telegraf/handlers/main.yml:12-14`): the services dict has no `environment`, so the
    check omits it (`ansible/roles/service-check-containers/tasks/main.yml:19`).

### 5.5 prometheus (node-exporter, cadvisor, libvirt-exporter)

- Play: `ansible/site.yml:431-452`. Hosts include `prometheus-node-exporter`, `prometheus-cadvisor` and
  `prometheus-libvirt-exporter`, which contain compute (`ansible/inventory/multinode:532-537,545-550,564-565`).
- node_exporter: `pid_mode: host`, `/:/host:ro,rslave`, listens on `api_interface_address` and port 9100
  (`ansible/roles/prometheus/defaults/main.yml:31-36,420-425`;
  `ansible/roles/prometheus/templates/prometheus-node-exporter.json.j2:2`; `ansible/group_vars/all.yml:668`).
- cadvisor: `/var/run:/var/run:rw` (**this includes docker.sock read-write, which makes the container
  root-equivalent**), `/var/lib/docker:ro`, `/sys:ro`, plus `/:/rootfs:ro` and `/dev/disk:ro`
  (`ansible/roles/prometheus/defaults/main.yml:431-440`). **Changed in 2025.1:** the command now passes
  `--listen_ip` with the host's api address, next to `--port={{ prometheus_cadvisor_port }}` (18080,
  `ansible/group_vars/all.yml:674`) (`ansible/roles/prometheus/templates/prometheus-cadvisor.json.j2:2`), so cadvisor
  no longer relies on its default listen address, and its config.json changes on the first 2025.1 run.
- libvirt-exporter: `/run/libvirt:/run/libvirt:ro`, listening on `api_interface_address` and port 9177
  (`ansible/roles/prometheus/defaults/main.yml:132-138,462-466`;
  `ansible/roles/prometheus/templates/prometheus-libvirt-exporter.json.j2:2`; `ansible/group_vars/all.yml:676,1344`).
- Compute-side config is config.json only (per-host). The **server** config `prometheus.yml.j2` loops over
  node-exporter, cadvisor, libvirt-exporter and other groups
  (`ansible/roles/prometheus/templates/prometheus.yml.j2:25-272`). Adding a compute changes prometheus.yml and, through
  the container check, restarts `prometheus_server` (`ansible/roles/prometheus/tasks/config.yml:69-84`), and rendering
  it needs facts for every compute. The server also has a basic-auth `web.yml`
  (`ansible/roles/prometheus/tasks/config.yml:86-98`).
- Scaling: "Find prometheus host config overrides" runs `delegate_to: localhost` **per host**, explicitly
  `run_once: false` (`ansible/roles/prometheus/tasks/config.yml:58-67`), even on hosts that are not prometheus servers.

### 5.6 masakari (monitors)

- Play: `ansible/site.yml:1028-1043`. Hosts are masakari-api, masakari-engine, `masakari-hostmonitor` (= control) and
  `masakari-instancemonitor` (= compute) (`ansible/inventory/multinode:567-577`).
- `masakari-instancemonitor` and `masakari-hostmonitor` are deployed
  (`ansible/roles/masakari/defaults/main.yml:35-50`), both enabled with `enable_masakari`
  (`ansible/group_vars/all.yml:924-925`). The hostmonitor runs on the control hosts with `restrict_to_remotes = true`
  and `pacemaker_node_type = cluster` (`ansible/roles/masakari/templates/masakari-monitors.conf.j2:22-43`), and the
  computes run `hacluster_pacemaker_remote` (5.15). There is still no processmonitor. **NOT AVAILABLE:** whether and how
  fast the hostmonitor detects a failed compute (masakari-monitors and Pacemaker code are not in the sources).
- Config: `masakari-monitors.conf` merge chain (`ansible/roles/masakari/tasks/config.yml:72-89`). It is per-host and
  has no rabbit, memcached or DB. Libvirt is reached over
  `connection_uri = "qemu+tcp://{{ migration_interface_address }}/system"`
  (`ansible/roles/masakari/templates/masakari-monitors.conf.j2:17-18`).
  - **Default libvirt auth (outcome NOT AVAILABLE):** nova-cell defaults to `libvirt_enable_sasl: true`
    (`ansible/roles/nova-cell/defaults/main.yml:578`), giving `auth_tcp = "sasl"`
    (`ansible/roles/nova-cell/templates/libvirtd.conf.j2:9-13`). `auth.conf` with the SASL credentials is copied to
    masakari-instancemonitor when `libvirt_enable_sasl` (`ansible/roles/masakari/tasks/config.yml:113-127`) and placed
    at `/var/lib/masakari/.config/libvirt/auth.conf`
    (`ansible/roles/masakari/templates/masakari-instancemonitor.json.j2:9-15`). With `libvirt_tls: true`,
    `listen_tcp = 0` (`ansible/roles/nova-cell/templates/libvirtd.conf.j2:1-3`; default `libvirt_tls: false`,
    `ansible/roles/nova-cell/defaults/main.yml:561`). **NOT AVAILABLE:** whether masakari-instancemonitor connects to
    libvirt with these defaults.
- **Fixed in 2025.1:** "Copying over existing policy file" now writes to `{{ node_config_directory }}/{{ item.key }}/`
  (`ansible/roles/masakari/tasks/config.yml:31-39`); in 2024.1 the path rendered a dict.
- **Changed in 2025.1:** the coordination backend can be Valkey (`ansible/group_vars/all.yml:573`).
- Bootstrap (DB sync) runs on every deploy/reconfigure (`ansible/roles/masakari/tasks/deploy.yml:11`).

### 5.7 zun (zun-compute, zun-cni-daemon)

- Play: `ansible/site.yml:996-1011`. The precheck requires kuryr (`ansible/roles/zun/tasks/precheck.yml:53-56`).
- Containers (`ansible/roles/zun/defaults/main.yml:48-65,188-208`): zun_compute is privileged with `/run` (`:shared`
  with Docker), `/usr/lib/docker`, `/var/lib/docker`, `/dev`, `/lib/modules:ro`, `iscsi_info:/etc/iscsi` when iscsid is
  enabled, and `/var/lib/zun:shared` when `zun_configure_for_cinder_ceph`. zun_cni_daemon is privileged.
- Config: `zun.conf` is rendered for **all** zun services including compute (`ansible/roles/zun/tasks/config.yml:48-61`).
  It contains `transport_url = rpc_transport_url` (`ansible/roles/zun/templates/zun.conf.j2:10`), the full
  **`[database] connection` with password** (`zun.conf.j2:22`), memcached ×2 (`zun.conf.j2:46,69`), and
  `docker api_url = tcp://<api_ip>:2375` (`zun.conf.j2:121-122`).
  - The docker daemon on zun-compute hosts is opened on TCP 2375 **without TLS or auth** by bootstrap-servers when
    `docker_configure_for_zun` is set (`ansible/group_vars/all.yml:132-133`; ansible-collection-kolla
    `roles/docker/templates/docker_systemd_service.j2:13`). `docker_zun_config` is `{}`
    (`ansible/group_vars/all.yml:134`).
  - **Changed in 2025.1:** `zun_ceph_cluster` is gone; the Ceph files for zun-compute are named after the global
    `ceph_cluster`, and the keyring after `ceph_cinder_user` (`ansible/roles/zun/tasks/external_ceph.yml:4,11`).
- Handlers: one restart handler per service (`ansible/roles/zun/handlers/main.yml:2-60`). On a zun-cni-daemon restart,
  the loopback binary is copied to the host `/opt/cni/bin` by a handler that listens on "Restart zun-cni-daemon
  container" (`ansible/roles/zun/handlers/main.yml:62-71`).
- **NOT AVAILABLE:** whether restarting zun_compute stops user containers, and whether a zun_cni_daemon restart breaks
  CNI operations during the window.

### 5.8 kuryr

- Play: `ansible/site.yml:693-705`. Hosts are **`compute`** directly, and the service group is hard-coded to `compute`
  (`ansible/roles/kuryr/defaults/main.yml:10-21`).
- The container is privileged with `cap_add: NET_ADMIN`, `/run` (`:shared` with Docker) and `/usr/lib/docker`
  (`ansible/roles/kuryr/defaults/main.yml:16-19,55-56`). `kuryr.spec` is placed into `/usr/lib/docker/plugins/kuryr/`
  (`ansible/roles/kuryr/templates/kuryr.json.j2:10-15`).
- Config is per-host: `kuryr_uri` uses its own api IP (`ansible/roles/kuryr/templates/kuryr.conf.j2:2`,
  `ansible/roles/kuryr/defaults/main.yml:95`), and kuryr.conf has no rabbit, memcached or DB
  (`ansible/roles/kuryr/templates/kuryr.conf.j2:1-32`); `capability_scope = local` (`kuryr.conf.j2:6`). **New in
  2025.1:** an `[oslo_concurrency]` lock path (`kuryr.conf.j2:30-32`), so kuryr.conf changes, and kuryr restarts, on
  every compute at the first 2025.1 run.
- Keystone user registration runs from the compute-host play (`ansible/roles/kuryr/tasks/deploy.yml:2`).
- **NOT AVAILABLE:** whether docker network create/attach fails while kuryr is restarting, and whether existing veth
  wiring persists.

### 5.9 cyborg (agent)

- Play: `ansible/site.yml:867-881` still uses **`serial: '{{ serial|default("0") }}'`** (`ansible/site.yml:874`), not
  `kolla_serial`. A batched run with `-e kolla_serial=N` is therefore ignored for cyborg. This **oddity** is still
  present in 2025.1.
- `cyborg-agent` runs on compute and is privileged (`ansible/roles/cyborg/defaults/main.yml:25-29`).
- `cyborg.conf` is rendered for all services (`ansible/roles/cyborg/tasks/config.yml:53-66`). It contains DB connection
  credentials (`ansible/roles/cyborg/templates/cyborg.conf.j2:13`), placement service credentials
  (`cyborg.conf.j2:34-44`), nova service credentials (`cyborg.conf.j2:46-56`), rabbit rpc and notify
  (`cyborg.conf.j2:6,64`) and memcached (`cyborg.conf.j2:21`). **Global, and it carries DB, placement and nova
  credentials on compute.**
- **Fixed in 2025.1:** the two 2024.1 bugs are gone. `cyborg_services` now has a `haproxy` key with `cyborg_api` and
  `cyborg_api_external` (`ansible/roles/cyborg/defaults/main.yml:11-24`), and `cyborg_internal_fqdn`,
  `cyborg_external_fqdn` and the port variables are defined (`ansible/group_vars/all.yml:388-392`), so the endpoints
  built at `ansible/roles/cyborg/defaults/main.yml:161-162` resolve. The keystone service type is still
  `"accelerator"` (`ansible/roles/cyborg/defaults/main.yml:185`).

### 5.10 skydive (agent)

**Still does not exist in 2025.1.** `ansible/roles/` has no `skydive` role, `ansible/site.yml` has no skydive play, and
`ansible/inventory/multinode` has no skydive group (a grep for `skydive` in `ansible/` finds nothing).

### 5.11 monasca (agents)

**Still nothing in 2025.1.** There is no `monasca` role, play, group or cleanup command (a grep for `monasca` in
`ansible/` finds nothing). Containers that an older release left behind are not cleaned up by any 2025.1 playbook.

### 5.12 chrony

**Still does not exist in 2025.1** (see [Chrony](../../components/chrony.md)): `ansible/roles/` has no `chrony` role,
`ansible/site.yml` has no chrony play, and `ansible/inventory/multinode` has no chrony group. Time sync is left to the
host; `kolla-ansible prechecks` checks it (`ansible/roles/prechecks/tasks/timesync_checks.yml`). **NOT AVAILABLE:**
which time source the hosts use.

### 5.13 nova-hyperv

**Still does not exist in 2025.1**: `ansible/roles/` has no `nova-hyperv` role, `ansible/site.yml` has no hyperv play,
and `ansible/inventory/multinode` has no `hyperv` group (a grep for `hyperv` in `ansible/` finds only
`hypervisor_inspector`, a comment and the hypervisor lookup of nova-cell,
`ansible/roles/ceilometer/templates/ceilometer.conf.j2:9`, `ansible/roles/nova-cell/tasks/deploy.yml:23`,
`ansible/roles/nova-cell/tasks/config.yml:56-110`).

### 5.14 Cross-reference: ovn-controller on compute

The `ovn-controller` role's `setup-ovs.yml` sets `external_ids:ovn-remote={{ ovn_sb_connection }}` in the local OVSDB
through `kolla_toolbox openvswitch_db` (`ansible/roles/ovn-controller/tasks/setup-ovs.yml:13-45`, `ovn-remote` at
`setup-ovs.yml:42`). The task runs on every deploy (`ansible/roles/ovn-controller/tasks/deploy.yml:6`). **Changed in
2025.1:** `ovn_sb_connection` is the list of **SB relays** (`groups['ovn-sb-db-relay']`) when `enable_ovn_sb_db_relay`
is set, which is the default with OVN, else the SB DB hosts (`ansible/group_vars/all.yml:646-648,953`). So the first
2025.1 deploy points every ovn-controller at the relays (see [OVN](../../components/ovn.md)). The
neutron-ovn-metadata-agent ini on compute also lists the NB and SB connections
(`ansible/roles/neutron/templates/neutron_ovn_metadata_agent.ini.j2:17-18`).

### 5.15 hacluster (pacemaker-remote)

- Play: `ansible/site.yml:707-720`, hosts `hacluster` (= control) and `hacluster-remote` (= compute,
  `ansible/inventory/multinode:78-82`), `&enable_hacluster_True`. `enable_hacluster` defaults to
  `enable_masakari_hostmonitor`, which defaults to `enable_masakari` (`ansible/group_vars/all.yml:885,925`):
  **enabling masakari puts a `hacluster_pacemaker_remote` container on every compute.**
- Container: `hacluster_pacemaker_remote`, `ipc_mode: host` (`ansible/roles/hacluster/defaults/main.yml:26-33`). Its
  config is config.json and the Pacemaker `authkey`, which the role generates once on the deploy host with
  `dd if=/dev/urandom` when it is missing (`ansible/roles/hacluster/tasks/bootstrap.yml:36-42`) and copies to every
  remote (`ansible/roles/hacluster/tasks/config.yml:61-72`); a change of either restarts the container through the
  container check (`ansible/roles/hacluster/handlers/main.yml:32-45`).
- Each compute is added as a Pacemaker `remote` resource named after its `nodename`, with its api address, by a
  `cibadmin --modify` delegated to the first `hacluster` host
  (`ansible/roles/hacluster/tasks/bootstrap_service.yml:10-29`).
- **NOT AVAILABLE:** what a `hacluster_pacemaker_remote` restart or a compute removal does to the Pacemaker cluster and
  to masakari host-failure handling; no task removes the `remote` resource of a deleted compute (the only `cibadmin` in
  `ansible/roles/hacluster/` is the `--modify` at `ansible/roles/hacluster/tasks/bootstrap_service.yml:16`).

---

## 6. Per-cluster host lists in templates

### 6.1 grep `for host in groups` over `ansible/roles/*/templates`

Memcached loops (`groups['memcached']`) appear in 26 roles in 2025.1 (27 in 2024.1): aodh, barbican, blazar, **ceilometer**, cinder,
cloudkitty, **cyborg**, designate, glance, gnocchi, heat (×2), horizon (×2), ironic (×2), keystone (×2), magnum,
manila (×4), masakari (api/engine only), mistral, **neutron**, nova (×2), octavia (×2), placement (×2), tacker, venus,
watcher, **zun (×2)**. Swift is gone (§3). Telegraf only tests whether the host itself is in the group
(`ansible/roles/telegraf/templates/telegraf.conf.j2:54`).

Other group loops:
- certificates `tls-backend` and `compute`; designate `designate-backend-bind9`/`designate-worker`; opensearch
  `opensearch`; haproxy-config backends (`groups[host_group]`); loadbalancer (keepalived) `loadbalancer`; letsencrypt
  `loadbalancer` (`ansible/roles/letsencrypt/templates/crontab.j2:5,9`,
  `ansible/roles/letsencrypt/templates/letsencrypt-lego-run.sh.j2:15,36`); keystone fernet-push `keystone`; galera
  `mariadb` (per shard group); hacluster corosync `hacluster`
  (`ansible/roles/hacluster/templates/hacluster_corosync.conf.j2:13`); octavia `octavia-health-manager` and, **changed
  in 2025.1, `valkey` or `redis`** (`ansible/roles/octavia/templates/octavia.conf.j2:82,172,176`); prometheus.yml
  (13 groups, including `prometheus-node-exporter`, `prometheus-cadvisor`, `prometheus-libvirt-exporter` and
  `loadbalancer`, `ansible/roles/prometheus/templates/prometheus.yml.j2:25-272`); prometheus-alertmanager; rabbitmq;
  **telegraf** `influxdb`.
- Non-loop group references: `ansible/roles/cinder/templates/cinder.conf.j2:20` and
  `ansible/roles/nova/templates/nova.conf.j2:62` use `groups['glance-api'] | length` (the nova-cell `nova.conf.j2` has
  `num_retries = 3`, `ansible/roles/nova-cell/templates/nova.conf.j2:108`). Cinder coordination is, **changed in
  2025.1**, `valkey_connection_string`, `redis_connection_string` or an etcd URL on `kolla_internal_fqdn`, depending on
  `cinder_coordination_backend` (`ansible/roles/cinder/templates/cinder.conf.j2:269-280`,
  `ansible/group_vars/all.yml:1178`).
- Host lists defined as **variables** rather than template loops: `rpc_transport_url`/`notify_transport_url`
  (`ansible/group_vars/all.yml:274,284`), `nova_cell_rpc/notify_transport_url`
  (`ansible/roles/nova-cell/defaults/main.yml:217-218`, groups default to `om_rpc_group` at
  `ansible/roles/nova-cell/defaults/main.yml:202,211`), `ovn_nb_connection` and `ovn_sb_connection`, **now relay-aware**
  (`ansible/group_vars/all.yml:645-648`), `redis_connection_string` (`ansible/group_vars/all.yml:1010`) and, **new in
  2025.1**, `valkey_connection_string` (`ansible/group_vars/all.yml:1016`). `docker_zun_config` holds no host list
  (`ansible/group_vars/all.yml:134`).

### 6.2 Config files on COMPUTE hosts that embed per-cluster host lists

In 2025.1 a changed file restarts its container through the container check (§5), not through a notify.

| File on compute (`/etc/kolla/...`) | Container restarted | Lists embedded | Evidence |
|---|---|---|---|
| `nova-compute/nova.conf` (and the other nova-cell compute services) | nova_compute, etc. (cross-ref) | cell rabbit rpc and notify | `ansible/roles/nova-cell/templates/nova.conf.j2:37,183`; `ansible/roles/nova-cell/defaults/main.yml:217-218` |
| `neutron-openvswitch-agent/neutron.conf` (also ovn-metadata, ovn-agent; Linux Bridge is gone) | neutron agents (cross-ref) | rabbit rpc and notify, **memcached** | `ansible/roles/neutron/templates/neutron.conf.j2:56,121,124`; rendered for agent services at `ansible/roles/neutron/tasks/config.yml:73-103` |
| `neutron-ovn-metadata-agent/neutron_ovn_metadata_agent.ini` | ovn metadata agent (cross-ref) | OVN NB hosts and SB relays (or SB hosts) | `ansible/roles/neutron/templates/neutron_ovn_metadata_agent.ini.j2:17-18` |
| OVS DB `external_ids:ovn-remote` (not a file) | none (live setting) | OVN SB relays (or SB hosts) | `ansible/roles/ovn-controller/tasks/setup-ovs.yml:13-45` |
| `ceilometer-compute/ceilometer.conf`, `ceilometer-ipmi/ceilometer.conf` | ceilometer_compute, ceilometer_ipmi | rabbit rpc and notify, **memcached** | `ansible/roles/ceilometer/templates/ceilometer.conf.j2:6,36,60` |
| `zun-compute/zun.conf`, `zun-cni-daemon/zun.conf` | zun_compute, zun_cni_daemon | rabbit rpc, **memcached ×2** | `ansible/roles/zun/templates/zun.conf.j2:10,46,69` |
| `cyborg-agent/cyborg.conf` | cyborg_agent | rabbit rpc and notify, **memcached** | `ansible/roles/cyborg/templates/cyborg.conf.j2:6,21,64` |
| `telegraf/telegraf.conf` | telegraf | influxdb hosts | `ansible/roles/telegraf/templates/telegraf.conf.j2:14-17` |
| `skydive-agent`, hyperv files, `/etc/docker/daemon.json` host lists | – | **none in 2025.1** (5.10, 5.13; `docker_zun_config: {}`) | – |

Compute-side files with **no** cluster lists (per-host only): iscsid and tgtd config.json, multipath.conf,
collectd.conf, node-exporter, cadvisor and libvirt-exporter config.json, masakari-monitors.conf, the
hacluster-pacemaker-remote config.json and authkey, kuryr.conf, and the common/fluentd outputs (these use
`elasticsearch_address` and `opensearch_address`, which default to the internal FQDN,
`ansible/group_vars/all.yml:1002`; `ansible/roles/common/templates/conf/output/01-es.conf.j2:6`,
`ansible/roles/common/templates/conf/output/03-opensearch.conf.j2:6`).

**Implication (consequence NOT AVAILABLE):** adding or removing a host in `rabbitmq` or `memcached` (normally
controllers), then running deploy or reconfigure across the fleet:
- re-templates the files above on **every compute**;
- makes the container check flag, and the handlers recreate or restart, ceilometer_compute, ceilometer_ipmi,
  zun_compute, zun_cni_daemon, cyborg_agent, the neutron agents, nova_compute (cross-ref) and others;
- runs those restarts in the same handler step on all notified hosts of the batch (ansible-core 2.18.20
  `lib/ansible/plugins/strategy/__init__.py:951-971`, `lib/ansible/plugins/strategy/linear.py:87-88`); with the
  default `kolla_serial` of `"0"` the batch is every host (`lib/ansible/executor/playbook_executor.py:294-296`), and
  the 2025.1 CLI no longer sets a serial of its own ([F19](../findings.md#f19)). **NOT AVAILABLE:** whether this
  causes a fleet-wide reconnect storm on RabbitMQ.

The same fleet-wide re-template happens once on the first 2025.1 run: the queue settings (`use_queue_manager`, quorum
and transient quorum queues) are now always rendered in these files, and a container that no 2025.1 run has recreated
yet is flagged by the changed systemd unit text ([F16](../findings.md#f16), [F17](../findings.md#f17)). On OVN clouds
the first 2025.1 deploy also moves `ovn-remote` to the SB relays (5.14).

Rendering each of these files also requires facts (`kolla_address(host)`) for every host in `rabbitmq` and `memcached`
(`kolla_ansible/kolla_address.py:54-61`). This matters for `--limit` runs (cross-ref gather-facts.yml).
Conversely, **adding a compute** changes non-compute configs: prometheus.yml (prometheus_server restart,
`ansible/roles/prometheus/templates/prometheus.yml.j2:37,109,205`) and, with masakari, the Pacemaker CIB (a new
`remote` resource, 5.15).

---

## 7. Consolidated bugs and oddities

Status against 2025.1 in each item.

1. to 4. **Swift: no longer apply**, the role is removed in 2025.1 (§3). The 2024.1 items stay in the
   [2024.1 sheet](../../../2024.1/reference/factsheets/d-barbican-octavia-swift-manila-compute-roles/#7-consolidated-bugs-and-oddities)
   for clouds that still run 2024.1.
5. Octavia: `heartbeat_key = insecure` is still hard-coded (`ansible/roles/octavia/templates/octavia.conf.j2:81`). The
   amp network, secgroup and flavor are filled in by default from the resources that `octavia_auto_configure` creates,
   and stay unset with no precheck only when it is off (`octavia.conf.j2:91-109`, `ansible/group_vars/all.yml:1411`).
   The HM precheck still uses `api_interface_address` (`ansible/roles/octavia/tasks/precheck.yml:30-39`). The CA
   private key is still copied to 3 services (`ansible/roles/octavia/tasks/config.yml:99-138`). The jobboard is still
   on by default with the amphora provider and still needs a backend that is off by default; **changed in 2025.1,**
   Valkey or Redis is accepted (`ansible/group_vars/all.yml:950,959,965`;
   `ansible/roles/octavia/tasks/precheck.yml:68-74`), the sentinel name is hard-coded as `kolla`
   (`octavia.conf.j2:183`), and `upgrade` no longer creates the persistence database
   (`ansible/roles/octavia/tasks/upgrade.yml:1-9`).
6. Manila: **fixed in 2025.1,** the policy copy now has `become: true`
   (`ansible/roles/manila/tasks/config.yml:85-93`). The service-instance password still defaults to `manila`
   (`ansible/roles/manila/defaults/main.yml:213`). The neutron `host_in_groups` asymmetry is **gone** with the Linux
   Bridge agent; only the OVS condition is left (`ansible/roles/neutron/defaults/main.yml:40`). The Ceph share
   sections ignore the `enabled` key of each `manila_ceph_backends` entry, while the file tasks honour it (4.6).
7. Masakari: **fixed in 2025.1,** the policy-file dest now uses `item.key`
   (`ansible/roles/masakari/tasks/config.yml:31-39`). There is still no processmonitor. instancemonitor uses qemu+tcp
   and receives the SASL `auth.conf` when SASL is on (`ansible/roles/masakari/tasks/config.yml:113-127`;
   `ansible/roles/masakari/templates/masakari-monitors.conf.j2:18`; `ansible/roles/nova-cell/defaults/main.yml:578`).
8. Cyborg: the play still uses `serial` instead of `kolla_serial` (`ansible/site.yml:874`). **Fixed in 2025.1:** the
   haproxy entry and the FQDN variables now exist (`ansible/roles/cyborg/defaults/main.yml:11-24`;
   `ansible/group_vars/all.yml:388-392`). DB credentials (and placement and nova credentials) are still on compute.
9. Telegraf: **fixed in 2025.1,** the plugin task no longer reads `item.value.enabled` in a `with_fileglob` loop
   (`ansible/roles/telegraf/tasks/config.yml:38-48`). The `HOST_PROC`/`HOST_SYS` environment is still not compared by
   the container check (5.4).
10. Ceilometer: pollsters dir deleted every run without become (`ansible/roles/ceilometer/tasks/config.yml:68-71`).
    Many localhost stats lack `run_once`. The bootstrap is explicitly non-idempotent
    (`ansible/roles/ceilometer/tasks/bootstrap.yml:2`). All still present. **New in 2025.1:** the central and compute
    healthchecks are off by default (`ansible/roles/ceilometer/defaults/main.yml:83,96`).
11. iscsid runs at debug `-d 8` (`ansible/roles/iscsi/templates/iscsid.json.j2:2`). The precheck tests port 3260 on
    iscsid hosts, on `tgtd_interface_address` (`ansible/roles/iscsi/tasks/precheck.yml:18-28`). Both still present.
12. multipathd has no meta and no dimensions (`ansible/roles/multipathd/defaults/main.yml:2-10`); config overrides are
    first-found (`ansible/roles/multipathd/tasks/config.yml:20-32`). Still as before.
13. nova-hyperv: **does not apply**, the role does not exist (5.13).
14. Security spread onto compute: DB credentials (zun `ansible/roles/zun/templates/zun.conf.j2:22`, cyborg
    `ansible/roles/cyborg/templates/cyborg.conf.j2:13`); unauthenticated docker TCP 2375 for zun
    (`ansible/group_vars/all.yml:133`); cadvisor with rw `/var/run` (docker.sock)
    (`ansible/roles/prometheus/defaults/main.yml:437`); the shared Pacemaker `authkey` on every compute when masakari is
    enabled (`ansible/roles/hacluster/tasks/config.yml:61-72`). No skydive or chrony.
15. Barbican and other bootstraps (octavia, manila, ceilometer, masakari, zun, cyborg) re-run their DB sync container on
    every deploy/reconfigure (bootstrap containers are removed on exit by default,
    `ansible/library/kolla_container.py:312`). Still present.
16. kuryr: `capability_scope = local` since 2024.1 (`ansible/roles/kuryr/templates/kuryr.conf.j2:6`); **new in
    2025.1,** an `[oslo_concurrency]` section changes kuryr.conf again on the first 2025.1 run (5.8).

## 8. NOT AVAILABLE list

To be confirmed by the community. None of these points was run on a lab.

- NOT AVAILABLE: whether 2024.1 swift containers left running keep serving correctly once the rest of the control plane
  is on 2025.1 (§3).
- NOT AVAILABLE: what an iscsid, tgtd or multipathd restart does to attached volumes under I/O (session state, path
  failover, the guest view); for tgtd, whether the LVM targets come back without a cinder-volume restart.
- NOT AVAILABLE: whether masakari-instancemonitor can connect to libvirt with SASL on (it receives `auth.conf`, 5.6).
- NOT AVAILABLE: whether the fleet-wide restarts after adding a rabbitmq or memcached host, or on the first 2025.1 run,
  cause a reconnect storm, with the default `kolla_serial` of `"0"` versus a set `-e kolla_serial=N`.
- NOT AVAILABLE: Octavia amphora behaviour after a change in the health-manager host list.
- NOT AVAILABLE: whether ceilometer-ipmi can reach local IPMI without privileged mode or `/dev`.
- NOT AVAILABLE: what `octavia_auto_configure` does during an upgrade from manually registered Ussuri resources with
  other names (2.3).
- NOT AVAILABLE: whether and how fast masakari-hostmonitor detects a failed compute, and what a
  `hacluster_pacemaker_remote` restart or a removed compute does to the Pacemaker cluster (5.6, 5.15).
- NOT AVAILABLE: what Octavia does when the jobboard backend is unreachable or replaced, including a move from Redis to
  Valkey (2.5, 2.6).
- NOT AVAILABLE: what kuryr's `capability_scope = local` means for existing Docker networks (5.8).
- NOT AVAILABLE (new in 2025.1): whether ceilometer-central restarts on every run once the container check compares the
  recreated `pollsters.d` (5.1).
- NOT AVAILABLE (new in 2025.1): how Manila behaves when an operator-defined `manila_ceph_backends` entry is disabled
  but its driver flag is on (4.6).
- NOT AVAILABLE (new in 2025.1): what moving every `ovn-remote` to the SB relays on the first 2025.1 deploy does to
  running ovn-controllers (5.14; see [OVN](../../components/ovn.md)).

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
- [2024.1 fact sheet D](../../../2024.1/reference/factsheets/d-barbican-octavia-swift-manila-compute-roles/) — the
  previous release, including the full Swift study
