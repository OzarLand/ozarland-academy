---
title: Fact sheet C
description: "Fact sheet for Glance, Placement, Cinder, Horizon and Heat: per-role flow, bootstrap on reconfigure, dependencies and restart impact."
tags: [glance, placement, cinder, horizon, heat, reconfigure, one-shot]
---

# Fact sheet C

All paths are relative to the repo root (`$SRC`). Every claim comes from reading source code only: kolla-ansible at the
tag `2023.1-eol`, the kolla images repo at the tag `2023.1-eol`, and, for Ansible semantics, the Ansible source (cited
as ansible-core 2.14.18 `lib/ansible/...:N`). Modules run inside the kolla-toolbox image come from that image's
`ansible-core==2.14.*` plus Ansible collections (kolla `docker/kolla-toolbox/Dockerfile.j2:73,93-95`,
`docker/kolla-toolbox/requirements.yml`); the collection sources are not among the studied trees.
- **FACT** (the default, not written out): shown by the cited source lines.
- **NOT AVAILABLE**: the sources do not establish it, for example upstream OpenStack runtime behaviour, durations, or
  what a restart does to work in progress.

Behaviour inside the images (what `KOLLA_BOOTSTRAP`, `KOLLA_UPGRADE`, `KOLLA_OSM`, `GLANCE_DB_EXPAND` and similar
variables actually run) is defined in the separate `kolla` images repo. That repo is **not** in this checkout, but its
`2023.1-eol` tag was read separately (see [Kolla images](../../concepts/kolla-images.md)). A statement that cites a
kolla path, written as kolla `docker/...` (for example kolla `docker/glance/glance-api/extend_start.sh` or kolla
`docker/base/set_configs.py`), is read from that source like any other code claim. Image-side behaviour without such a
citation is NOT AVAILABLE.

---

## 0. Cross-cutting facts (apply to all five roles)

| Topic | Fact | Evidence |
|---|---|---|
| Task dispatch | Every role's `tasks/main.yml` is `- include_tasks: "{{ kolla_action }}.yml"`. | e.g. `ansible/roles/glance/tasks/main.yml:2` (identical in placement/cinder/horizon/heat) |
| `reconfigure` | `reconfigure.yml` is just `- import_tasks: deploy.yml` in **all five** roles, so reconfigure performs keystone registration, DB create/grant and **the bootstrap (db sync) container**, exactly as deploy does. | `ansible/roles/{glance,placement,cinder,horizon,heat}/tasks/reconfigure.yml:2` |
| `common` | In 2023.1 none of the five roles has a `meta/` directory, so there is no role dependency on `common`. `common` is its own play, tagged `common`, on the `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` groups. | `ansible/roles/{glance,placement,cinder,horizon,heat}/` (no `meta/`); `ansible/site.yml:86-97` |
| Serial | Every play uses `serial: '{{ kolla_serial|default("0") }}'`. The CLI passes `kolla_serial=${ANSIBLE_SERIAL}` (default `0`) only for `upgrade` and `reconfigure`. | `ansible/site.yml:500,527,537,638,648`; `tools/kolla-ansible:290,508,517` |
| run_once + serial | Bootstrap, DB and keystone tasks are `run_once: True`. When `kolla_serial` > 0, Ansible runs the whole play once per batch and sends a `run_once` task only to the first host of the current batch, so `run_once` tasks run **once per batch**. So db sync and keystone registration repeat for each batch. This matters for glance rolling upgrade ([§1.8](#18-operational-notes)). | e.g. `ansible/roles/cinder/tasks/bootstrap_service.yml:19-20`; ansible-core 2.14.18 `lib/ansible/executor/playbook_executor.py:181-190`, `lib/ansible/plugins/strategy/linear.py:217,247-248` |
| Bootstrap container | `kolla_docker action=start_container, detach: False, restart_policy: oneshot`. A one-shot container gets no systemd unit and is started directly; the module waits for exit and then stops and removes it (`remove_on_exit` defaults to True), before it reports a non-zero exit. Nothing guards it with "already bootstrapped", so it **runs on every deploy/reconfigure**. | `ansible/library/kolla_docker.py:285,304`; `ansible/module_utils/kolla_docker_worker.py:359-360,385-434`; e.g. `ansible/roles/glance/tasks/bootstrap_service.yml:19-37` |
| Restart semantics | Handlers use `recreate_or_restart_container` and pass `common_options: docker_common_options`, which carries `graceful_timeout: docker_graceful_timeout` (**60 s**). Long-running containers run under a systemd unit `kolla-<name>-container.service` whose `ExecStop` is `docker stop <name> -t <graceful_timeout>`; restarts and stops go through systemd `RestartUnit`/`StopUnit`. Docker sends SIGTERM, then SIGKILL if the container is still running after 60 s. No role here overrides it. The 10 s value is only the module default when no `graceful_timeout` is passed. | `ansible/group_vars/all.yml:140,143-153`; `ansible/module_utils/kolla_systemd_worker.py:33,101-117`; `ansible/module_utils/kolla_docker_worker.py:362-384,436-480`; [R24](../../risk/risk-register.md#r24) |
| Handler skip | All handlers have `when: kolla_action != "config"`, so `genconfig` never restarts anything. | e.g. `ansible/roles/cinder/handlers/main.yml:15-16` |
| Network | All containers run with `network_mode: host`, so the container hostname is the node hostname (this matters for cinder `host`). | `ansible/module_utils/kolla_docker_worker.py:288` |
| Empty volume strings | Volume lists contain `''` entries (timezone, dev-mode). `generate_volumes` skips empty entries, so the places that pass lists without `reject('equalto','')` (placement/cinder upgrade OSM, horizon) are harmless. | `ansible/module_utils/kolla_container_worker.py:415-417` |
| Shared endpoints | `database_address: "{{ kolla_internal_fqdn }}"` (DB is reached through the VIP). `rpc_transport_url` / `notify_transport_url` enumerate **every** host in the rabbit groups. | `ansible/group_vars/all.yml:83,212,222` |
| memcached | Every service template (glance, placement, cinder, heat, horizon) enumerates **all** `groups['memcached']` hosts. Adding or removing a memcached or rabbitmq node therefore changes the config of all five services, and they restart on the next deploy/reconfigure. | e.g. `ansible/roles/heat/templates/heat.conf.j2:46,52` |
| Workers | `openstack_service_workers: "{{ [ansible_facts.processor_vcpus, 5] | min }}"`. The value is per host. | `ansible/group_vars/all.yml:598` |
| Sanity checks | 2023.1 has no sanity checks: `kolla_enable_sanity_checks` and `kolla_enable_sanity_*` are defined nowhere under `ansible/`, glance and cinder have no `check.yml`, and the `check.yml` of placement, horizon and heat is empty. The CLI has no `check` action. | `grep -rn sanity ansible/` → nothing; `ansible/roles/{placement,horizon,heat}/tasks/check.yml:1`; `tools/kolla-ansible:429-574` |
| HAProxy | Each role's `loadbalancer.yml` is applied from the **loadbalancer play** (`site.yml:99-341`, tags `haproxy`, `keepalived`, `loadbalancer`), whose task block only runs when `enable_haproxy` and `kolla_action in ['deploy','reconfigure','upgrade','config']`. | `ansible/site.yml:99-110,339-341` |
| TLS backend certs | `service-cert-copy` copies `<project>-cert.pem`/`-key.pem` into a service's config dir only when one of its haproxy entries is enabled and one has `tls_backend` true, and `kolla_externally_managed_cert` is false. It notifies the container restart. | `ansible/roles/service-cert-copy/tasks/main.yml:14-56` |
| Service-to-host mapping | `host_in_groups` (used only by glance) takes precedence over `group` in the filter `select_services_enabled_and_mapped_to_host`. That filter drives pull/stop/cert-copy. | `kolla_ansible/filters.py:60-85,99-109` |
| Ansible forks | No `ansible.cfg` ships in the repo, so "all hosts restart together" really means up to `forks` hosts at once (Ansible default 5): Ansible starts at most `min(forks, batch size)` workers and queues each host's task on a free one. The `forks` value in use depends on the operator's config (`ansible.cfg`, `ANSIBLE_FORKS` or `kolla-ansible --forks`) and is NOT AVAILABLE here. | `find . -name ansible.cfg` → none; `tools/kolla-ansible:375-376`; ansible-core 2.14.18 `lib/ansible/config/base.yml:646-653`, `lib/ansible/executor/task_queue_manager.py:305-306`, `lib/ansible/plugins/strategy/__init__.py:364,374-404` |

### site.yml order (relevant slice)

`loadbalancer` play (99) → … → **glance** (495) → ironic (505) → **cinder** (519) → **placement** (532) →
`import_playbook: nova.yml` (544) → … → **heat** (631) → **horizon** (643). Placement is therefore (re)deployed before
nova, and glance before cinder.

---

## 1. GLANCE

### 1.1 Play

```yaml
# ansible/site.yml:495-503
- name: Apply role glance
  gather_facts: false
  hosts:
    - glance-api
    - '&enable_glance_True'
  serial: '{{ kolla_serial|default("0") }}'
  roles:
    - { role: glance,
        tags: glance }
```
- In 2023.1 the role line has no `when: enable_glance`; the host pattern `&enable_glance_True` (group built at
  `site.yml:33`) does the selection.
- The LB include is at `ansible/site.yml:163-167` (tag `glance`, `when: enable_glance`).
- `enable_glance: "{{ enable_openstack_core | bool }}"` (`ansible/group_vars/all.yml:621`).

### 1.2 `glance_services` (`ansible/roles/glance/defaults/main.yml:2-64`)

In 2023.1 the dict is at `ansible/roles/glance/defaults/main.yml:2-66`.

| key | container | group / mapping | enabled | flags |
|---|---|---|---|---|
| glance-api | `glance_api` | `group: glance-api`, **`host_in_groups: inventory_hostname in glance_api_hosts`** (:6) | `true` | `privileged: enable_cinder and (enable_cinder_backend_iscsi or cinder_backend_ceph)` (:10); `environment: glance_api_container_proxy` = `container_proxy` (:9, :204). This is the only service in scope that receives http(s)_proxy. Volumes (:184-193): `glance_file_datadir_volume:/var/lib/glance/` (default named volume `glance`), and **`iscsi_info:/etc/iscsi` plus `/dev:/dev` when cinder iSCSI is enabled** (:192-193). |
| glance-tls-proxy | `glance_tls_proxy` | same `host_in_groups` (:38) | `glance_enable_tls_backend` (= `kolla_enable_tls_backend`, `all.yml:917`) | HAProxy image (`.../haproxy`, :151-153). It listens on `api_interface_address:9292` with TLS and forwards to glance-api on `127.0.0.1:9292` (`templates/glance-tls-proxy.cfg.j2:42-47`; glance-api `bind_host = 127.0.0.1` when TLS, `templates/glance-api.conf.j2:9-13`). |

**Critical mapping rule:**
```yaml
# ansible/group_vars/all.yml:906,910-911,915
glance_backend_file: "{{ not (glance_backend_ceph | bool or glance_backend_swift | bool or glance_backend_vmware | bool) }}"
glance_backend_swift: "{{ enable_swift | bool }}"
glance_file_datadir_volume: "glance"
glance_api_hosts: "{{ [groups['glance-api'] | first] if glance_backend_file | bool and glance_file_datadir_volume == 'glance' else groups['glance-api'] }}"
```
With the default file backend on a local named volume, glance-api runs **only on the first host of `glance-api`**.
HAProxy members are built from `glance_api_hosts` too (`defaults/main.yml:84-85`), so glance has **no HA**. A glance-api
restart is a full Image API outage. The docs confirm this: "By default when using ``file`` backend only one
``glance-api`` container can be running" (`doc/source/reference/shared-services/glance-guide.rst:25-26`).

HAProxy: client and server timeouts are **6h** (`defaults/main.yml:137-138`). In TLS mode the HAProxy members are the
`custom_member_list` `haproxy_tls_members`, which always carries `ssl verify required ca-file ...`
(`defaults/main.yml:54,65,85`), and **ignore `kolla_verify_tls_backend`**: the template prints a custom member list as
is (`haproxy-config/templates/haproxy_single_service_split.cfg.j2:80-83`). Other services honour it in
`haproxy-config/templates/haproxy_single_service_split.cfg.j2:85-92`.

### 1.3 Task flow per action

| action | flow |
|---|---|
| deploy / reconfigure | `deploy.yml`: `register.yml` → `config.yml` → `check-containers.yml` → (`clone.yml` if dev) → `bootstrap.yml` → `meta: flush_handlers` (`tasks/deploy.yml:1-15`; `reconfigure.yml:2`). In 2023.1 there is no `check.yml` step. |
| upgrade | `upgrade.yml:1-6`: `rolling_upgrade.yml` if `glance_enable_rolling_upgrade` (default `no`, `all.yml:912`), else `legacy_upgrade.yml`. **No `register.yml`** in either path, so endpoints are not refreshed on upgrade. |
| legacy upgrade | `config.yml` → `check-containers.yml` → `bootstrap_service.yml` (db sync, new image) → flush (`tasks/legacy_upgrade.yml:1-9`). It does **not** stop glance-api first. The docs claim "This upgrade method will stop APIs during database schema migrations" (`glance-guide.rst:115`), but the code does not do that: the old glance-api keeps serving while the new-image bootstrap migrates the schema. |
| rolling upgrade | see [§1.8](#18-operational-notes) |
| deploy-containers | `check-containers.yml` only, then handlers (`tasks/deploy-containers.yml:2`) |
| pull | `service-images-pull`. Only hosts where `host_in_groups` is true pull (`roles/service-images-pull/tasks/main.yml:14`). |
| stop | `service-stop` with `glance_services` (`tasks/stop.yml:2-6`) |
| precheck | `service-precheck` (groups exist) plus a free-port check on 9292 when glance_api is not running (`tasks/precheck.yml:1-26`) |
| check | Not available in 2023.1: the role has no `check.yml`, and the CLI has no `check` action ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). |
| config | `config.yml` only. Handlers are notified but skipped. |

### 1.4 Config files (`ansible/roles/glance/tasks/config.yml`)

| dest (under `/etc/kolla/`) | source / merge order | when | notifies |
|---|---|---|---|
| `glance-api/` and `glance-tls-proxy/` dirs | `file` | enabled and mapped (:2-13) | – |
| `glance-api/ceph.conf` | `template: {{node_custom_config}}/glance/ceph.conf` (a single file, no merge) | `glance_backend_ceph` (`config.yml:14-16`; `external_ceph.yml:2-10`) | Restart glance-api |
| `glance-api/<ceph_glance_keyring>` | `template {{node_custom_config}}/glance/{{ ceph_glance_keyring }}` (default `ceph.client.glance.keyring`, `all.yml:1095`) | ceph (`external_ceph.yml:12-20`) | Restart glance-api |
| policy file | first found of `supported_policy_format_list` in `{{node_custom_config}}/glance/` (:18-35, :156-169) | if found | Restart glance-api |
| CA/TLS certs | `copy-certs.yml` → service-cert-copy (:37-39) | `kolla_copy_ca_into_containers or glance_enable_tls_backend` | Restart `<svc>` |
| `glance-tls-proxy/glance-cert-and-key.pem` | `assemble` of `glance-(cert|key).pem` (:41-54) | TLS proxy enabled | **no notify** (the cert copy notifies instead) |
| `<svc>/config.json` | `glance-api.json.j2`, `glance-tls-proxy.json.j2` (:56-67) | – | Restart `<svc>` |
| `glance-api/glance-api.conf` | merge: `templates/glance-api.conf.j2` → `global.conf` → `glance.conf` → `glance/glance-api.conf` → `glance/<host>/glance-api.conf` (:69-86) | – | Restart glance-api |
| `glance-api/glance-cache.conf` | merge: template → `glance-cache.conf` → `glance/glance-cache.conf` → `glance/<host>/glance-cache.conf` (:88-105). Note that **no `global.conf`** is in this merge. | `enable_glance_image_cache` | Restart glance-api |
| `glance-api/glance-swift.conf` | merge: template → `glance-swift.conf` → `glance/glance-swift.conf` → `glance/<host>/...` (:107-124) | `glance_backend_swift` | Restart glance-api |
| `glance-api/glance-image-import.conf` (new in 2023.1) | `copy {{node_custom_config}}/glance/glance-image-import.conf` (:126-139) | `glance_enable_interoperable_image_import` (default `no`, `all.yml:914`) | Restart glance-api |
| `glance-api/property-protections-rules.conf` (new in 2023.1) | `copy {{node_custom_config}}/glance/property-protections-rules.conf` (:141-154) | `glance_enable_property_protection` (default `no`, `all.yml:913`) | Restart glance-api |
| `glance-tls-proxy/glance-tls-proxy.cfg` | first_found: `glance/<host>/glance-tls-proxy.cfg` → `glance/glance-tls-proxy.cfg` → role template (:171-187) | TLS proxy | Restart glance-tls-proxy |

`glance-api.json.j2:53-58` has
`"permissions": [{"path": "/var/lib/glance", "owner": "glance:glance", "recurse": true}]`. `/var/lib/glance` is the
`glance_file_datadir_volume` mount (`defaults/main.yml:188`), which with the file backend is the **entire image store**
(`filesystem_store_datadir = /var/lib/glance/images/`, `templates/glance-api.conf.j2:73`). kolla_set_configs walks it
and calls `os.chown` on every directory and file, unconditionally (kolla `docker/base/set_configs.py:345-355,378-385`).
It does this at every container start under the default `COPY_ALWAYS` (kolla `docker/base/start.sh:11`,
`set_configs.py:538-541`; `ansible/group_vars/all.yml:43`), and only on a container's first start under `COPY_ONCE`
(kolla `set_configs.py:542-551`); see
[Kolla images §2](../../concepts/kolla-images.md#2-start-path-common-to-every-image). NOT AVAILABLE: how long this
recursive chown takes at container start with a big NFS-backed `glance_file_datadir_volume`.

### 1.5 Handlers (`ansible/roles/glance/handlers/main.yml`)

- `Restart glance-api container` (:2-18): recreate_or_restart. It passes `privileged`, `environment` (the proxy),
  volumes, dimensions and healthcheck.
- `Restart glance-tls-proxy container` (:20-34): recreate_or_restart.
- Neither has special logic beyond `kolla_action != "config"`. There is no rolling restart and no wait for the API to
  come back.

### 1.6 Bootstrap

| step | where | re-runs on reconfigure? |
|---|---|---|
| `mysql_db glance` | `tasks/bootstrap.yml:2-16`, run_once, delegate `groups['glance-api'][0]`, unless `use_preconfigured_databases` | yes (idempotent) |
| `mysql_user glance` with password and `ALL` on `glance.*` | `bootstrap.yml:18-36` | yes. The task runs `mysql_user` through `kolla_toolbox` (`ansible/library/kolla_toolbox.py:116-118`), whose image installs `ansible-core==2.14.*` (kolla `docker/kolla-toolbox/Dockerfile.j2:73`); ansible-core redirects `mysql_user` to `community.mysql.mysql_user` (ansible-core 2.14.18 `lib/ansible/config/ansible_builtin_runtime.yml:1401-1402`), installed in the image from `community.mysql <3` (kolla `docker/kolla-toolbox/requirements.yml:7-8`). That collection's source is not among the studied trees, so whether each run resets the stored password when it differs is NOT AVAILABLE. |
| **Set GLOBAL `log_bin_trust_function_creators=1`** | `bootstrap_service.yml:2-17`, logged in as `glance_database_shard_root_user` (the DB root user without ProxySQL, `defaults/main.yml:123`), unless `use_preconfigured_databases` | **yes, on every deploy/reconfigure** |
| `bootstrap_glance` container, `KOLLA_BOOTSTRAP`: `glance-manage db_sync` then `glance-manage db_load_metadefs` (kolla `docker/glance/glance-api/extend_start.sh:5-9`) | `bootstrap_service.yml:19-37`, delegate `glance_api_hosts[0]` | **yes, so a schema sync runs on every reconfigure** |
| Set `log_bin_trust_function_creators=0` | `bootstrap_service.yml:39-54` | yes |
| Keystone: service `glance`/`image`, 2 endpoints (internal, public), user `glance` (admin in `service`) | `tasks/register.yml`; `defaults/main.yml:90-102` | yes (deploy/reconfigure); **not** on upgrade |

**Oddity / risk:** the enable/db_sync/disable sequence is not wrapped in `block/always`. If the bootstrap container
fails, the global MariaDB variable stays at `1`. Whether this leftover state has security consequences is NOT AVAILABLE.
A related upstream fix for keystone appears in
`releasenotes/notes/bug-1987982-fix-keystone-log_bin_trust_function_creators-variables-8628098891513dac.yaml`.

**Reconfigure as uncontrolled upgrade:** if an operator bumps `openstack_tag`/`glance_tag` and runs `reconfigure`, the
new image runs the `KOLLA_BOOTSTRAP` branch (`glance-manage db_sync` and `db_load_metadefs`, kolla
`docker/glance/glance-api/extend_start.sh:5-9`) and the handler recreates glance-api on the new image. For the glance
role that is the default legacy upgrade (`glance_enable_rolling_upgrade: "no"`, `all.yml:912`): `legacy_upgrade.yml:2-9`
runs the same config, check-containers, `bootstrap_service.yml` and flush steps, and reconfigure only adds registration,
DB/user creation and the dev-mode clone (`deploy.yml:2-15`).

### 1.7 Dependencies (from `templates/glance-api.conf.j2`)

- **MariaDB** via the VIP (:34-38); **RabbitMQ**: `transport_url = rpc_transport_url` (:27) and notifications (:115-122;
  topic `notifications` only if ceilometer, otherwise `driver = noop`, `defaults/main.yml:107-111`).
- **Keystone**: `www_authenticate_uri` and `auth_url` are both `keystone_internal_url` (:40-51). **memcached**: all
  hosts (:53-55).
- **Cinder**: `cinder_catalog_info = volume:cinder:internalURL` (:25), and `enabled_backends` contains `cinder:cinder`
  whenever `enable_cinder` (`defaults/main.yml:222-224`; template :17-19). **Oddity:** in 2023.1 cinder registers only
  `cinderv3/volumev3` (`roles/cinder/defaults/main.yml:320-326`). No `volume/cinder` catalog entry exists, and the
  template has no `[cinder]` store section, so the glance cinder store is enabled without a matching catalog entry or
  store section. Whether it works if used is NOT AVAILABLE. Nova, by contrast, uses
  `catalog_info = volumev3:cinderv3:internalURL` (`roles/nova-cell/templates/nova.conf.j2:113`).
- **Ceph**: `[rbd] rbd_store_user/pool` (:76-80). In 2023.1 the template no longer sets `show_multiple_locations`
  (`grep -rn show_multiple_locations ansible/roles/glance` → nothing).
- **Swift**: `[swift]` section (:82-92) with **`swift_store_auth_insecure = True` hard-coded**. `glance-swift.conf`
  authenticates against `openstack_auth.auth_url` (= `keystone_internal_url`, `all.yml:895-896`) as `service:glance`
  (`templates/glance-swift.conf.j2:1-8`).
- **Barbican** (:150-155), **osprofiler** (:142-148), **VMware** (:94-101).
- Cinder iSCSI flag toggles glance-api `/dev` and `iscsi_info`, and cinder iSCSI or `cinder_backend_ceph` toggles
  `privileged` (`defaults/main.yml:10,192-193`). The code comment says the mounts are "to support Cinder iSCSI backends"
  (`defaults/main.yml:191`). How glance uses these mounts is NOT AVAILABLE.

### 1.8 Operational notes

1. **Backend switch via unrelated flags:** `glance_backend_swift` defaults to `enable_swift` (`all.yml:910`), and
   `glance_backend_file` is the negation of ceph/swift/vmware (`all.yml:906`). Enabling Swift (or `glance_backend_ceph`)
   on a running cloud does three things:
   - removes `file` from `enabled_backends` and drops the `[file]` section (`defaults/main.yml:209-212`; template
     :17-19,71-74);
   - changes `default_backend` (:60-69);
   - expands `glance_api_hosts` to every `glance-api` host (`all.yml:915`).

   NOT AVAILABLE: whether existing images in the file store stay readable after the switch.

   A related doc mismatch: the guide says ceph is enabled "automatically" (`glance-guide.rst:43`), but the default is
   `glance_backend_ceph: "no"` (`all.yml:907`).
2. **Inventory order matters:** with the file backend, glance runs on `groups['glance-api']|first`. The INI parser reads
   the file line by line and adds each host in that order, and Ansible lists a group's hosts in the order they were
   added (ansible-core 2.14.18 `lib/ansible/plugins/inventory/ini.py:159,216`,
   `lib/ansible/plugins/inventory/__init__.py:209-210`, `lib/ansible/inventory/group.py:224-228,266-278`,
   `lib/ansible/inventory/data.py:258-268`), so reordering the inventory moves glance-api to another host, and the
   HAProxy members follow it (`all.yml:915`; `defaults/main.yml:84-85`). NOT AVAILABLE: what the `glance` volume on the
   new host contains.
3. **Restart impact:** the HAProxy client and server timeouts are 6h (`defaults/main.yml:137-138`). Restarting
   glance-api stops it with the 60 s graceful timeout ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). With the
   file backend this is a total Image API outage, because glance-api is the only backend
   ([§1.2](#12-glance_services-ansiblerolesglancedefaultsmainyml2-64)). NOT AVAILABLE: what the restart does to
   in-flight uploads, downloads, nova snapshots and cinder upload-to-image operations, whether images are left in
   `saving`/`queued`, and whether nova boots that need an uncached image fail during the window.
4. **Rolling upgrade** (`tasks/rolling_upgrade.yml`):
   - Sequence: config on host[0] (:7-8) → **stop glance-api on host[0]** (:10-11, `stop_service.yml`) → enable log_bin
     (:13-28) → `GLANCE_DB_EXPAND` (:30-49) → `GLANCE_DB_MIGRATE`, which notifies restart (:51-72) → config on the other
     hosts (:75-76) → check-containers (:78) → **flush handlers**, so all glance-api containers restart in the same
     handler run (:80-81) → `GLANCE_DB_CONTRACT` (:83-102) → disable log_bin (:104-119).
   - The `glance_upgrading` fact (:2-4, :121-123) is set but never read anywhere (dead code).
   - With `kolla_serial` > 0, each batch re-runs the run_once expand/migrate/**contract** on `glance_api_hosts[0]`
     (:48-49, :69-70, :101-102), because Ansible runs the play once per batch and sends a `run_once` task to the first
     host of each batch ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). The contract therefore runs at the end
     of batch 1, while hosts in later batches still run the old glance-api containers.
   - The docs warn that rolling upgrade with a non-shared file backend leads to "a corrupt state"
     (`glance-guide.rst:108`).
5. **Image cache** is never pruned. The docs say "Glance caches are not cleaned up automatically"
   (`glance-guide.rst:145`); there is no cron/pruner container.
6. **Sanity check** (if enabled) creates and deletes an image on every deploy/reconfigure. Not available in 2023.1: the
   role has no `check.yml`, `tasks/deploy.yml:1-15` has no check step, and `kolla_enable_sanity_glance` is not defined
   ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)).
7. Glance does not touch compute hosts. Nova-compute reaches glance through `[glance] api_servers` =
   `glance_internal_endpoint` (internal FQDN, port 9292, `all.yml:919`;
   `roles/nova-cell/templates/nova.conf.j2:105-109`), and cinder through `glance_api_servers`
   (`roles/cinder/templates/cinder.conf.j2:18`).

---

## 2. PLACEMENT

### 2.1 Play

```yaml
# ansible/site.yml:532-541
- name: Apply role placement
  gather_facts: false
  hosts: [placement-api, '&enable_placement_True']
  serial: '{{ kolla_serial|default("0") }}'
  roles: [{ role: placement, tags: placement }]
```
- `enable_placement: "{{ enable_nova | bool or enable_zun | bool }}"` (`all.yml:740`).
- **Oddity:** the LB include for placement **has no `when: enable_placement`** (`site.yml:243-246`), unlike every other
  service. When placement is disabled it still writes an (effectively empty) `services.d/placement-api.cfg`, because
  `placement-api.enabled: True` (`roles/placement/defaults/main.yml:7`) and the haproxy-config task checks only
  `service.enabled`, `service.haproxy` and `enable_haproxy` (`roles/haproxy-config/tasks/main.yml:17-20`). Only the
  inner haproxy entries carry `enable_placement` (`roles/placement/defaults/main.yml:13,20`), and the template skips
  disabled entries (`roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:116`).
- The play sits right before `import_playbook: nova.yml` (`site.yml:544`).

### 2.2 `placement_services` (`ansible/roles/placement/defaults/main.yml:2-24`)

In 2023.1 the dict is at `ansible/roles/placement/defaults/main.yml:2-25`.

| key | container | group | enabled | flags |
|---|---|---|---|---|
| placement-api | `placement_api` | `placement-api` | `True` | Plain Apache/mod_wsgi. No privileged, no host paths beyond config, localtime, timezone (Debian) and logs, plus the dev-mode source (:79-84). HAProxy internal and external on 8780, `tls_backend: placement_enable_tls_backend` (:11-25). |

### 2.3 Task flow

| action | flow |
|---|---|
| deploy / reconfigure | `register.yml` → (clone) → `config.yml` → `check-containers.yml` → `bootstrap.yml` → flush (`tasks/deploy.yml:1-14`) |
| upgrade | `register.yml` → (clone) → `config.yml` → `check-containers.yml` → `bootstrap.yml` (`KOLLA_BOOTSTRAP` with the new image: `placement-manage db sync` **and** `db online_data_migrations`, kolla `docker/placement/placement-api/extend_start.sh:5-9`, while the old placement-api is still running; the image's `KOLLA_UPGRADE` branch, db sync only, `:12-15`, is not used) → flush (all placement-api restart) → **`KOLLA_OSM` online data migrations** container, which runs them a second time (`tasks/upgrade.yml:1-34`) |
| deploy-containers | `check-containers.yml` |
| pull / stop | service-images-pull / service-stop |
| precheck | groups exist, port 8780 free if not running (`tasks/precheck.yml:1-29`) |
| check | empty file (`tasks/check.yml:1`) |
| config | `config.yml` |

### 2.4 Config files (`ansible/roles/placement/tasks/config.yml`)

| dest | sources | notifies |
|---|---|---|
| `placement-api/config.json` | `placement-api.json.j2` (:38-49) | Restart placement-api |
| `placement-api/placement.conf` | merge: template → `global.conf` → `placement.conf` → `placement/placement-api.conf` → `placement/<host>/placement.conf` (:51-69) | Restart |
| `placement-api/placement-api-wsgi.conf` | first_found: `placement/<host>/placement-api-wsgi.conf` → `placement/placement-api-wsgi.conf` → template (:71-87) | Restart |
| `placement-api/migrate-db.rc` | `migrate-db.rc.j2` (:89-101) | Restart |
| policy | `{{node_custom_config}}/placement/` (:15-32, :103-115) | Restart |
| certs | service-cert-copy (:34-36) | Restart |

`migrate-db.rc` contains the **nova_api DB user and password** together with the placement DB creds
(`templates/migrate-db.rc.j2:1-8`; vars at `defaults/main.yml:121-124`). The defaults file files these vars under
"Upgrade" (`defaults/main.yml:118-120`); no task of the role uses it, and the container receives it as
`/etc/placement/migrate-db.rc` (`templates/placement-api.json.j2:25-26`). It spreads a nova secret into the placement
container and is notified on change.

### 2.5 Handlers

`Restart placement-api container`: recreate_or_restart, no special logic (`handlers/main.yml:2-16`).

### 2.6 Bootstrap

- `mysql_db placement` and `mysql_user` (`tasks/bootstrap.yml:2-36`) re-run on reconfigure.
- `bootstrap_placement` with `KOLLA_BOOTSTRAP` (kolla image: `placement-manage db sync` then
  `placement-manage db online_data_migrations`, kolla `docker/placement/placement-api/extend_start.sh:5-9`) runs once,
  delegated to `groups['placement-api'][0]` (`bootstrap_service.yml:2-20`). **It re-runs on every reconfigure.**
- Keystone registration (service `placement`, 2 endpoints, internal and public, user `placement`,
  `defaults/main.yml:129-140`) happens in deploy, reconfigure **and upgrade** (`upgrade.yml:2`), unlike glance and heat.
- Online data migrations: the separate `KOLLA_OSM` container runs **only** in upgrade (`upgrade.yml:16-34`). Because the
  bootstrap container above also runs `db online_data_migrations`, placement OSM also runs on every deploy/reconfigure
  (`deploy.yml:11`, `reconfigure.yml:2`) and twice in upgrade (bootstrap at `upgrade.yml:11`, then `KOLLA_OSM`).

### 2.7 Dependencies (`templates/placement.conf.j2`)

- MariaDB `[placement_database]` with **`max_overflow = 1000` hard-coded** (:14-19).
- memcached `[cache]` and `keystone_authtoken` (:21-42); Keystone (:27-38).
- In 2023.1 the template sets no `transport_url` (placement does no RPC).
- Leftovers: the Ussuri `osapi_compute_listen` and `my_ip` lines are gone in 2023.1; `[DEFAULT]` holds only debug, log
  and state paths (:1-6).
- **Dead variables:** `placement_notification_topics` / `placement_enabled_notification_topics`
  (`defaults/main.yml:103-107`) are not referenced by any template. There is no `[oslo_messaging_notifications]`
  section.

### 2.8 Operational notes and the relation to nova

- **Consumers authenticate as the placement user.** nova-api/conductor/scheduler
  (`roles/nova/templates/nova.conf.j2:179-189`) and **nova-compute on every compute host**
  (`roles/nova-cell/templates/nova.conf.j2:221-231`) use `username = {{ placement_keystone_user }}` /
  `password = {{ placement_keystone_password }}`, `valid_interfaces = internal`. Neutron does the same with
  `endpoint_type = internal` (`roles/neutron/templates/neutron.conf.j2:188-198`), as does cyborg
  (`roles/cyborg/templates/cyborg.conf.j2`); in 2023.1 zun does not. Rotating `placement_keystone_password` therefore
  needs a reconfigure of placement **and** nova (all computes) **and** neutron. This dependency scales with the number
  of compute hosts.
- NOT AVAILABLE (upstream nova): how scheduling and the nova-compute resource tracker periodic task behave during a
  placement-api outage or restart. With serial=0 every placement-api restarts in the same handler flush, up to `forks`
  hosts at once ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)); whether and for how long no placement-api is
  serving is NOT AVAILABLE.
- The upgrade db sync and online data migrations (bootstrap container) run while the old placement-api is still serving
  (no stop).

---

## 3. CINDER

### 3.1 Play

```yaml
# ansible/site.yml:519-530
- name: Apply role cinder
  gather_facts: false
  hosts: [cinder-api, cinder-backup, cinder-scheduler, cinder-volume, '&enable_cinder_True']
  serial: '{{ kolla_serial|default("0") }}'
  roles: [{ role: cinder, tags: cinder }]
```
- LB include: `site.yml:133-137`.
- Defaults: `enable_cinder: "no"`, `enable_cinder_backup: "yes"`,
  `enable_cinder_backend_iscsi: "{{ enable_cinder_backend_lvm | bool }}"`, `enable_cinder_backend_lvm: "no"`
  (`all.yml:650-654`). `cinder_backend_ceph: "no"`, `cinder_backup_driver: "ceph"` (`all.yml:945,954`).
- Sample inventory: `cinder-api`/`cinder-scheduler` sit under `[cinder:children] control`.
  **`cinder-volume`/`cinder-backup` sit under `storage`** (`ansible/inventory/multinode:128-129,321-331`).

### 3.2 `cinder_services` (`ansible/roles/cinder/defaults/main.yml:2-48`)

In 2023.1 the dict is at `ansible/roles/cinder/defaults/main.yml:2-53`.

| key | container | group | enabled | flags / host volumes |
|---|---|---|---|---|
| cinder-api | `cinder_api` | cinder-api | true | Apache/mod_wsgi on 8776; HAProxy internal and external (:11-25) |
| cinder-scheduler | `cinder_scheduler` | cinder-scheduler | true | – |
| cinder-volume | `cinder_volume` | cinder-volume | true | **`privileged: True`, `ipc_mode: host`** (:39-40), `tmpfs` for `/var/lib/cinder/conversion` only if `cinder_enable_conversion_tmpfs` (default false, :41,203-207). Volumes (:184-195): **`/dev/:/dev/`, `/lib/modules:ro`, `/run/:/run/:shared`**, `cinder:/var/lib/cinder`, **`iscsi_info:/etc/iscsi`** (if `enable_iscsid`), **`target_config:/etc/target`** (LVM and `lioadm`). |
| cinder-backup | `cinder_backup` | cinder-backup | `enable_cinder_backup` | **`privileged: True`** (no ipc host). Volumes (:167-177): `/dev/`, `/lib/modules`, `/run/:shared`, `cinder:/var/lib/cinder`, `iscsi_info`. |

Related: `cinder_target_helper` is `lioadm` on RedHat and `tgtadm` otherwise (`all.yml:949`). With `tgtadm` the targets
are served by a **separate `tgtd` container** from the `iscsi` role, which also deploys `iscsid` on `compute`,
`cinder-volume` and `cinder-backup` hosts (`roles/iscsi/defaults/main.yml:2-20,61-73`; play `site.yml:417-426`).

### 3.3 Task flow

| action | flow |
|---|---|
| deploy / reconfigure | `register.yml` → `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` → flush (`tasks/deploy.yml:1-14`). In 2023.1 there is no `check.yml` step. |
| upgrade | `config.yml` **only on `groups['cinder-api'][0]`** (:4-5) → `bootstrap_service.yml` (db sync, new image, old services still running) (:7) → `config.yml` on all (:9) → `check-containers.yml` (:11) → `service-ks-register` for the `service` role and the cinder user's `service` role only (:13-19) → flush, so **every cinder container on every host restarts in this flush (serial 0)**, cinder-volume and cinder-backup included; on upgrade a handler then pauses `cinder_rpc_version_startup_delay` (30 s) once (:21-22; `handlers/main.yml:70-88`; `defaults/main.yml:229`) → **`reload.yml`: `restart_container` of every enabled cinder container on the host again, "to remove RPC version pin"** (:24; `tasks/reload.yml:2-10`) → `KOLLA_OSM` online migrations (:26-44). No `register.yml`, so services and endpoints are not refreshed. |
| deploy-containers | check-containers |
| pull / stop | helpers |
| precheck | groups; API port free; **at least one backend enabled** unless `skip_cinder_backend_check` (:28-44); **`vgs cinder-volumes`** on cinder-volume hosts if LVM (`tasks/precheck.yml:46-56`) |
| check | Not available in 2023.1: the role has no `check.yml`, and `kolla_enable_sanity_cinder` is not defined ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). |
| config | `config.yml` |

### 3.4 Config files (`ansible/roles/cinder/tasks/config.yml`)

| dest | sources | when | notifies |
|---|---|---|---|
| `<svc>/ceph.conf` (cinder-volume, cinder-backup) | **merge** `cinder/ceph.conf` + `cinder/<svc>/ceph.conf` (`external_ceph.yml:2-20`) | `cinder_backend_ceph` and host in volume/backup (`config.yml:15-19`) | Restart `<svc>` |
| `cinder-volume/<ceph_cinder_keyring>` | `cinder/cinder-volume/ceph.client.cinder.keyring` (`external_ceph.yml:22-33`) | cephx | Restart cinder-volume |
| `cinder-backup/` keyrings (cinder plus cinder-backup) | `cinder/cinder-backup/...` (`external_ceph.yml:35-50`) | cephx | Restart cinder-backup |
| policy | `{{node_custom_config}}/cinder/` (:21-38, :95-107) | | Restart `<svc>` |
| certs | service-cert-copy (:40-42) | | |
| `<svc>/config.json` | `<svc>.json.j2` (:44-55) | | Restart `<svc>` |
| `cinder-api/cinder-wsgi.conf` | first_found: `cinder/<host>/cinder-wsgi.conf` → `cinder/cinder-wsgi.conf` → template (:57-73) | | Restart cinder-api |
| `<svc>/cinder.conf` (one per service, `service_name` var) | merge: template → `global.conf` → `cinder.conf` → `cinder/<svc>.conf` → `cinder/<host>/cinder.conf` (:75-93) | | Restart `<svc>` |
| `cinder-volume/nfs_shares` | first_found among 8 paths (`nfs_shares.j2` variants, then plain), `skip` unless NFS or HNAS (:109-128) | host in cinder-volume | Restart cinder-volume |

### 3.5 Handlers (`ansible/roles/cinder/handlers/main.yml`)

Four restart handlers (api :2-16, scheduler :18-32, volume :34-51, backup :53-68), all recreate_or_restart. The volume
handler passes `privileged`, `ipc_mode` and `tmpfs`; the backup handler passes `privileged`. A fifth handler,
`Wait for cinder services to update service versions` (:78-88), listens to all four and pauses 30 s once, only when
`kolla_action == 'upgrade'`. There is no drain logic.

### 3.6 Bootstrap

- `mysql_db cinder` and `mysql_user` run every deploy/reconfigure (`bootstrap.yml:2-36`).
- `bootstrap_cinder` (`KOLLA_BOOTSTRAP`: `cinder-manage db sync`, kolla `docker/cinder/cinder-api/extend_start.sh:6-9`),
  run_once on `groups['cinder-api'][0]` (`bootstrap_service.yml:2-20`). **It re-runs on every reconfigure.**
- Online data migrations (`KOLLA_OSM`) run only in upgrade.
- Keystone: in 2023.1 only `cinderv3/volumev3`, with 2 `/v3/%(tenant_id)s` endpoints (internal, public); user `cinder`
  (admin in `service`); a `service` role, granted to the cinder user in the `service` project
  (`defaults/main.yml:212-216,320-341`; `tasks/register.yml:2-9`). Services and endpoints are registered on
  deploy/reconfigure, not on upgrade.

### 3.7 Dependencies (`templates/cinder.conf.j2`)

- **Glance**: `glance_api_servers` = `glance_internal_endpoint` (internal FQDN, port 9292) (:18).
  **`glance_num_retries = {{ groups['glance-api'] | length }}`** (:20) scales with the number of glance hosts. With the
  glance file backend only one glance-api exists, yet retries equal the group size.
- **Nova**: `[nova]` section authenticates with **`nova_keystone_user`/`nova_keystone_password`** (:90-100), so rotating
  the nova password needs a cinder reconfigure. In the other direction, nova-api and nova-compute use
  **`cinder_keystone_user/password`** (`roles/nova-cell/templates/nova.conf.j2:112-122`,
  `roles/nova/templates/nova.conf.j2:66-76`), so rotating the cinder password needs a reconfigure of all computes.
  Manila also uses the cinder creds (`roles/manila/templates/manila-share.conf.j2:29-30`).
- MariaDB (:102-106); RabbitMQ RPC (:58) and notify (:60-67; topics for ceilometer/vitrage,
  `defaults/main.yml:276-282`); Keystone and memcached (:108-127); Barbican (:238-243); osprofiler (:230-236).
- **Ceph**: `[rbd-1]` with `rbd_secret_uuid = cinder_rbd_secret_uuid` (:142-152). The same UUID is installed into
  libvirt on computes by `roles/nova-cell/tasks/external_ceph.yml:152,177`, so the two must stay in sync.
- **Swift** backup: `backup_swift_url` internal (:43-50).
- **Coordination**: redis or etcd (:245-253). In 2023.1 the etcd URL is
  `etcd3+<internal_protocol>://{{ kolla_internal_fqdn }}:{{ etcd_client_port }}` (:252), and the etcd role defines an
  internal HAProxy entry on `etcd_client_port` (`roles/etcd/defaults/main.yml:26-31`), so cinder reaches etcd through
  the internal VIP rather than `groups['etcd'][0]` as in Ussuri. Default `cinder_coordination_backend` is `''` unless
  redis or etcd is enabled (`all.yml:951`; `enable_etcd: "no"`, `enable_redis: "no"`, `all.yml:664,743`).
- **LVM/iSCSI**: `target_helper`, `target_protocol = iscsi` (:133-140).

### 3.8 Operational notes

1. **No `host`/`backend_host`/`cluster` set in cinder.conf** (`templates/cinder.conf.j2` has none;
   `grep backend_host ansible/roles/cinder` returns nothing). Because of `network_mode: host`, each cinder-volume
   container has the node hostname ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). Whether cinder then registers
   it as `<node-hostname>@<backend>` is upstream cinder behaviour and NOT AVAILABLE here.
   - NOT AVAILABLE (upstream cinder): whether, with a shared backend (ceph `rbd-1`) on several cinder-volume hosts,
     every volume is owned by the host that created it.
   - NOT AVAILABLE: whether, if that node is down, its volumes cannot be attached, detached, deleted or snapshotted
     until the node returns or `cinder-manage volume update_host` is run.
   - The same question applies to renaming or replacing a storage node. The docs also note LVM issues in a
     multi-controller setup (`doc/source/reference/storage/cinder-guide.rst:52-55`).
2. **cinder-volume restart impact** (upstream cinder and os-brick behaviour, NOT AVAILABLE beyond the code facts):
   - Code facts: with LVM, the LIO config is kept in the `target_config` volume (`defaults/main.yml:193`) or the targets
     are served by the separate `tgtd` container ([§3.2](#32-cinder_services-ansiblerolescinderdefaultsmainyml2-48));
     with Ceph, the RBD secret is installed into libvirt on computes ([§3.7](#37-dependencies-templatescinderconfj2)).
     NOT AVAILABLE: whether the data path for attached volumes bypasses cinder-volume, and so whether existing
     attachments survive a cinder-volume restart.
   - In-flight operations: the stop sends SIGKILL if cinder-volume is still running after the 60 s graceful timeout
     ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). NOT AVAILABLE: whether this kills `qemu-img`/`dd` copies
     (image→volume, volume→image, migrate, retype) and what state they leave.
   - NOT AVAILABLE: what `init_host` does on start with resources left in `creating`, `downloading` or `uploading`, and
     whether it re-runs `ensure_export` for in-use volumes.
3. **cinder-backup restart:** NOT AVAILABLE: whether backups and restores in progress are killed and marked `error` on
   the next start. Because of the `cinder_backup_driver` default, see oddity 5.
4. **Upgrade restarts every cinder-volume and cinder-backup at once, twice** (flush at `upgrade.yml:21-22`, then
   `reload.yml` at `upgrade.yml:24`; serial 0 unless `ANSIBLE_SERIAL` is set). There is no `[upgrade_levels]` pinning in
   the template. The code comment explains the second restart: after an upgrade, services keep an RPC version cap until
   all of them are restarted, and the role waits 30 s for the services to update their version in the database
   (`handlers/main.yml:70-76`). The `reload.yml` restart is a plain `restart_container`, without
   `when: kolla_action != "config"` or any other condition, on every enabled cinder service mapped to the host
   (`tasks/reload.yml:2-10`). NOT AVAILABLE: whether 30 s is enough on a given cloud, and whether in-flight operations
   survive two restarts in a row.
5. **Oddity: backup driver vs. ceph files.** `cinder_backup_driver: "ceph"` is the default even when
   `cinder_backend_ceph` is `no`. cinder.conf then sets `backup_driver = ...CephBackupDriver`,
   `backup_ceph_conf=/etc/ceph/ceph.conf` (:27-36). But `cinder-backup.json.j2` only lists ceph.conf and the keyrings
   `{% if cinder_backend_ceph %}` (:15-36), and `external_ceph.yml` only runs for `cinder_backend_ceph`
   (`config.yml:15-19`). With an LVM or NFS-only deployment and default backup settings, kolla-ansible therefore gives
   cinder-backup no ceph config. Whether its driver then fails is NOT AVAILABLE.
6. **Multipath** is never configured on the cinder side: no `use_multipath_for_image_xfer` / `volume_use_multipath` in
   the cinder templates (`grep multipath ansible/roles/cinder` returns nothing). On the nova side, 2023.1 sets
   `volume_use_multipath = True` in nova-compute's libvirt config when `enable_multipathd` is on
   (`roles/nova-cell/templates/nova.conf.d/libvirt.conf.j2:27-28`). The `multipathd` container is off by default
   (`all.yml:714`).
7. **Compute-host touchpoints:** the cinder role itself does not target computes. However, `iscsid` on computes (iscsi
   role) shares `iscsi_info`, nova-compute uses the cinder creds, and the RBD secret is shared with nova-libvirt.
   Enabling `enable_cinder_backend_iscsi`/LVM also flips glance-api to privileged with `/dev`, so **glance-api is
   recreated** (`roles/glance/defaults/main.yml:10,192-193`). In 2023.1 `cinder_backend_ceph` (with Cinder enabled) also
   makes glance-api privileged, without `/dev` (`roles/glance/defaults/main.yml:10`).
8. External Ceph needs cinder-volume and cinder-backup hosts in the `storage` group, otherwise "Cinder and related
   services relying on this group [will] fail" (`doc/source/reference/storage/external-ceph-guide.rst:94-101`).
9. The sanity check (if enabled) creates a 1 GB volume on every deploy/reconfigure. Not available in 2023.1: the role
   has no `check.yml` ([§3.3](#33-task-flow)).

---

## 4. HORIZON

### 4.1 Play

```yaml
# ansible/site.yml:643-651
- name: Apply role horizon
  gather_facts: false
  hosts: [horizon, '&enable_horizon_True']
  serial: '{{ kolla_serial|default("0") }}'
  roles: [{ role: horizon, tags: horizon }]
```
- LB include: `site.yml:183-187`. `enable_horizon: "{{ enable_openstack_core | bool }}"` (`all.yml:673`).
- Horizon is the last of these plays.

### 4.2 `horizon_services` (`ansible/roles/horizon/defaults/main.yml:2-69`)

In 2023.1 the dict is at `ansible/roles/horizon/defaults/main.yml:2-72`.

| key | container | group | enabled | flags |
|---|---|---|---|---|
| horizon | `horizon` | horizon | true | **`environment`: 21 `ENABLE_<PLUGIN>` flags plus `FORCE_GENERATE`** (:8-30). In 2023.1 there is **no host `/tmp` bind**: the volumes are config, dev-mode sources, localtime, timezone and logs (:122-129). Settings use `LOCAL_PATH = '/tmp'` (`templates/local_settings.j2:154`), which is therefore the container's own `/tmp`. HAProxy uses `balance roundrobin` when `enable_memcached` or `horizon_backend_database`, `balance source` otherwise (:44, :61; `enable_memcached: "yes"`, `all.yml:628`, so `roundrobin` by default). Redirect frontends (`mode: redirect`, port 80) are added when internal or external TLS is on (:46-51, :63-68), and an `acme_client` backend is defined (:69-72). |

Because the plugin flags live in the container environment, and `check-containers` compares `environment`
(`tasks/check-containers.yml:11`), **enabling or disabling any service that has a horizon plugin** (designate, octavia,
magnum, …) changes the env. The horizon container is then **recreated** on the next deploy/reconfigure even if no
horizon config changed.

### 4.3 Task flow

| action | flow |
|---|---|
| deploy / reconfigure | `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` **only if `horizon_backend_database`** → flush (`tasks/deploy.yml:1-14`). There is **no keystone registration**. |
| upgrade | `config.yml` → `check-containers.yml` → (clone) → `bootstrap_service.yml` if DB backend → flush (`tasks/upgrade.yml:1-14`) |
| precheck | groups; `horizon_listen_port` free (80, or 443 when `horizon_enable_tls_backend`; `all.yml:353-355`) (`tasks/precheck.yml:16-27`) |
| check | empty (`tasks/check.yml:1`) |
| pull / stop / deploy-containers / config | standard |

### 4.4 Config files (`ansible/roles/horizon/tasks/config.yml`)

| dest | source | notifies |
|---|---|---|
| per-service policy files (`<svc>_policy.json/yaml`) | for each enabled service in the list (:19-46), `policy_item.yml` looks for `{{node_custom_config}}/horizon/<svc>_<policy file>` (`tasks/policy_item.yml:3-25`) and copies the matches (:116-129) | Restart horizon |
| `horizon/config.json` | `horizon.json.j2` (:48-60) | Restart horizon |
| `horizon/horizon.conf` (Apache) | first_found: `horizon/<host>/horizon.conf` → `horizon/horizon.conf` → template (:62-78). This is a **whole-file override**, not a merge. | Restart horizon |
| `horizon/local_settings` | first_found: `horizon/<host>/local_settings` → `horizon/local_settings` → `local_settings.j2` (:80-96). Whole-file override. | Restart horizon |
| `horizon/custom_local_settings` | first_found, same pattern; the default template is empty (:98-114). It is imported last by `local_settings` (`local_settings.j2:869-870`). | Restart horizon |
| custom themes (new in 2023.1) | `{{node_custom_config}}/horizon/themes/<name>` for each `horizon_custom_themes` entry (default `[]`, `defaults/main.yml:77`) (:131-145) | Restart horizon |
| certs | service-cert-copy (:147-149) | |

### 4.5 Handlers

`Restart horizon container` (`handlers/main.yml:2-17`): recreate_or_restart. It passes `environment`; there is no other
logic.

### 4.6 Bootstrap

- `horizon_backend_database: "{{ enable_murano | bool }}"` (`all.yml:1052`). Only then does deploy/reconfigure create
  the DB and user and run `bootstrap_horizon` (`KOLLA_BOOTSTRAP`: Django `manage.py migrate --noinput`, then exits;
  kolla `docker/horizon/extend_start.sh:27-30`) (`tasks/bootstrap.yml:2-38`, `bootstrap_service.yml:2-20`). In that case
  **the bootstrap re-runs on every reconfigure**.
- There is no keystone registration at all.

### 4.7 Dependencies (`templates/local_settings.j2`)

- **Keystone**: `OPENSTACK_KEYSTONE_URL = "{{ horizon_keystone_url }}/v3"` (template :210), with
  `horizon_keystone_url` = `keystone_internal_url`, or `keystone_public_url` when `horizon_use_keystone_public_url`
  (default False) (`defaults/main.yml:137,163`). `OPENSTACK_HOST = kolla_internal_fqdn` (:207).
  `OPENSTACK_ENDPOINT_TYPE = "internalURL"` (:424), so Horizon talks to **every** service's internal endpoint from its
  own container.
- **memcached**: `SESSION_ENGINE = cache` with all memcached hosts **unless** the DB backend is used (:177-185). With
  the DB backend: `SESSION_ENGINE = db` plus MariaDB (:32-44).
- **Cinder**: `enable_backup` follows `enable_cinder_backup` (:314). **Murano + Barbican**: `KEY_MANAGER` with murano
  creds (:858-866).
- `SECRET_KEY = horizon_secret_key` (:165), which is the same on all nodes.
- Multi-region `AVAILABLE_REGIONS` (:198-205).
- TLS: `SECURE_PROXY_SSL_HEADER` and secure cookies when either internal or external TLS is on (:58-62). The Ussuri
  FIXME in `horizon.conf.j2` ("enabling of either tls will break the other if not enabled too") is gone in 2023.1: the
  template only handles `horizon_enable_tls_backend` (`templates/horizon.conf.j2:3,43`), and the http→https redirects
  are HAProxy entries ([§4.2](#42-horizon_services-ansibleroleshorizondefaultsmainyml2-69)).

### 4.8 Operational notes

- Sessions live in memcached unless the DB backend is used (`local_settings.j2:177-185`), HAProxy uses
  `balance roundrobin` by default and `balance source` only when memcached is disabled and the DB backend is not used
  ([§4.2](#42-horizon_services-ansibleroleshorizondefaultsmainyml2-69)), and `LOCAL_PATH=/tmp` is the **container's**
  `/tmp`, so it does not survive a recreate ([§4.2](#42-horizon_services-ansibleroleshorizondefaultsmainyml2-69)). NOT
  AVAILABLE: whether a horizon restart or a **memcached restart** logs users out, what restarting a node does to
  in-flight requests (including legacy image uploads that go through Horizon), and whether those uploads are staged in
  `LOCAL_PATH`.
- Image side (kolla `docker/horizon/extend_start.sh`): every start syncs each `ENABLE_<PLUGIN>` dashboard file into
  `openstack_dashboard/local/enabled` (`:32-46,267-287`). `manage.py collectstatic --noinput --clear` and
  `compress --force` run **only** when `/var/lib/kolla/.settings.md5sum.txt` is missing, the md5 of `local_settings` +
  `custom_local_settings` + `local_settings.d` differs from it, a plugin file was just copied in or removed, or
  `FORCE_GENERATE=yes` (`:38-45,248-265,289-293`). kolla-ansible sets `FORCE_GENERATE=yes` only when `horizon_dev_mode`
  is on, and `no` otherwise (`defaults/main.yml:30,154`). The settings set `COMPRESS_OFFLINE = True`
  (`local_settings.j2:13`). `/var/lib/kolla` is not a volume (`defaults/main.yml:122-129`), so the hash file lives in
  the container layer. The handler restarts the container under `COPY_ALWAYS` (default, `all.yml:43`) and recreates it
  when image, env or volumes differ, or under `COPY_ONCE` (`module_utils/kolla_docker_worker.py:362-384`). Only this
  start script writes the hash file (`:6,292`; no other file under kolla `docker/` names it), so a new container starts
  without one. `collectstatic` and `compress` therefore run on the first start after a recreate (new image, plugin flag
  change, `COPY_ONCE`) or after a `local_settings`/`custom_local_settings` change, and not on a plain restart with
  unchanged settings and plugin flags. NOT AVAILABLE: how long they take. See
  [Kolla images §5](../../concepts/kolla-images.md#5-per-image-start-behaviour).
- Horizon config is independent of host count except for the memcached list.

---

## 5. HEAT

### 5.1 Play

```yaml
# ansible/site.yml:631-641
- name: Apply role heat
  gather_facts: false
  hosts: [heat-api, heat-api-cfn, heat-engine, '&enable_heat_True']
  serial: '{{ kolla_serial|default("0") }}'
  roles: [{ role: heat, tags: heat }]
```
- LB include: `site.yml:178-182`. `enable_heat: "{{ enable_openstack_core | bool }}"` (`all.yml:672`).

### 5.2 `heat_services` (`ansible/roles/heat/defaults/main.yml:2-53`)

In 2023.1 the dict is at `ansible/roles/heat/defaults/main.yml:2-56`.

| key | container | group | enabled | flags |
|---|---|---|---|---|
| heat-api | `heat_api` | heat-api | true | Apache/mod_wsgi on 8004, HAProxy internal and external (:11-25) |
| heat-api-cfn | `heat_api_cfn` | heat-api-cfn | true | Apache/mod_wsgi on 8000, HAProxy internal and external (:34-48) |
| heat-engine | `heat_engine` | heat-engine | true | No haproxy, not privileged. Volumes are config, localtime, timezone, dev-mode source and logs only (:158-163). |

### 5.3 Task flow

| action | flow |
|---|---|
| deploy / reconfigure | `register.yml` → `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` → flush (`tasks/deploy.yml:1-15`) |
| upgrade | `config.yml` → `check-containers.yml` → `bootstrap_service.yml` (db sync with new image while the old engine and APIs still run) → flush, which restarts **all** heat-api, heat-api-cfn and heat-engine containers together (`tasks/upgrade.yml:1-9`). The Ussuri step that removed `heat-engine/_deprecated.yaml` is gone in 2023.1. No `register.yml`. |
| precheck | ports 8004/8000 free on api/cfn hosts (`tasks/precheck.yml:17-37`). heat-engine is not checked. |
| check | empty (`tasks/check.yml:1`) |
| pull / stop / deploy-containers / config | standard |

### 5.4 Config files (`ansible/roles/heat/tasks/config.yml`)

| dest | sources | notifies |
|---|---|---|
| `<svc>/config.json` | `<svc>.json.j2` (:38-49) | Restart `<svc>` |
| `<svc>/heat.conf` (`service_name` per container) | merge: template → `global.conf` → `heat.conf` → `heat/<svc>.conf` → `heat/<host>/heat.conf` (:51-69) | Restart `<svc>` |
| policy | `{{node_custom_config}}/heat/` (:15-32, :71-83) | Restart `<svc>` |
| `heat-api/wsgi-heat-api.conf`, `heat-api-cfn/wsgi-heat-api-cfn.conf` | `src: "{{ role_path }}/templates/..."` (:85-111). **No override path exists**, unlike cinder/placement wsgi. | Restart heat-api / heat-api-cfn |
| certs | service-cert-copy (:34-36) | |

**Oddity:** in Ussuri `templates/wsgi-heat-api.conf.j2` (and the cfn twin) set a `python-path` that was not the venv
path. This no longer holds in 2023.1: the template sets no `python-path`, and both `WSGIScriptAlias` and the
`<Directory>` block use `binary_path = /var/lib/kolla/venv/bin` (`templates/wsgi-heat-api.conf.j2:2,18,34`), as
placement does with its `wsgi_directory` (`roles/placement/templates/placement-api-wsgi.conf.j2:2`).

### 5.5 Handlers

Three handlers: heat-api (:2-16), heat-api-cfn (:18-32), heat-engine (:34-48). All recreate_or_restart, with no special
logic.

### 5.6 Bootstrap

- `mysql_db heat` and `mysql_user` (`tasks/bootstrap.yml:2-36`) run every deploy/reconfigure.
- `bootstrap_heat` container (`bootstrap_service.yml:2-30`) gets `KOLLA_BOOTSTRAP` plus the **cloud admin credentials as
  env vars** (`OS_AUTH_URL`, `OS_USERNAME`, `OS_PASSWORD`, `OS_PROJECT_NAME`, …) and `HEAT_DOMAIN_ADMIN_PASSWORD`
  (:10-22). The image runs `heat-manage db_sync`, then `openstack domain list`. Only if `heat_user_domain` is absent
  does it create the domain, the `heat_domain_admin` user (password `HEAT_DOMAIN_ADMIN_PASSWORD`) and that user's
  `admin` role on the domain (kolla `docker/heat/heat-api/extend_start.sh:5-17`). **It re-runs on every reconfigure**
  (and on upgrade, `tasks/upgrade.yml:6`), but once the domain exists it never touches the user. A changed
  `heat_domain_admin_password` (`etc/kolla/passwords.yml:114`) is therefore **not** pushed to Keystone, while
  `heat.conf` gets the new value (`templates/heat.conf.j2:11-12`). NOT AVAILABLE: whether stack-domain operations then
  fail authentication. The check looks only at the domain name, so if a run fails partway and leaves the domain without
  the user or its role, no later run repairs it. The container is removed on exit, after a failure too
  (`module_utils/kolla_docker_worker.py:426-434`), so the passwords do not linger in `docker inspect`. But `kolla_start`
  runs with xtrace: when the bootstrap creates the domain, the `openstack user create … --password` line goes to stderr
  with `HEAT_DOMAIN_ADMIN_PASSWORD` expanded. `kolla_docker` returns that stderr in the task result
  (`module_utils/kolla_docker_worker.py:421-425`), which Ansible prints on failure or with `-v` (ansible-core 2.14.18
  `lib/ansible/plugins/callback/default.py:50-71,104-105`, `lib/ansible/plugins/callback/__init__.py:200-202`), and the
  task sets no `no_log` (kolla `docker/base/start.sh:6`, `docker/heat/heat-api/extend_start.sh:12`;
  [Kolla images §2.2](../../concepts/kolla-images.md#22-kolla_start-step-by-step)).
- Keystone: services `heat/orchestration` (`/v1/%(tenant_id)s`) and `heat-cfn/cloudformation` (`/v1`), each with 2
  endpoints (internal, public); user `heat`; roles `heat_stack_owner` and `heat_stack_user`; **`heat_stack_owner`
  granted to the cloud admin user in the admin project** (`defaults/main.yml:173-179,213-240`;
  `tasks/register.yml:2-9`). This runs on deploy/reconfigure, not on upgrade.

### 5.7 Dependencies (`templates/heat.conf.j2`)

- **Public endpoints reached from inside VMs:** `heat_metadata_server_url` and `heat_waitcondition_server_url` use
  `heat_cfn_public_base_endpoint` (:6-7), i.e. **`public_protocol` and `heat_cfn_external_fqdn`**
  (`defaults/main.yml:176`). `server_keystone_endpoint_type = public` (:23). Instances that use wait conditions or
  software deployments must be able to reach the **external** VIP on 8000 and the public keystone endpoint.
- **All other services:** `[clients] endpoint_type = internalURL` (:92-94). heat-engine calls nova, neutron, cinder,
  glance, swift, etc. through their internal catalog endpoints. The real dependency set is whatever the users' templates
  use.
- Keystone: `keystone_authtoken` (:31-46), plus `[trustee]` with the heat service user (:55-60), plus `[ec2authtoken]`
  (:62-63). `stack_domain_admin` = `heat_domain_admin` / `heat_domain_admin_password` (:11-13).
- MariaDB (:25-29); RabbitMQ RPC (:19) and notifications (ceilometer only, otherwise `driver = noop`; :65-72,
  `defaults/main.yml:204-208`); memcached for authtoken and `[cache]` (:44-52).
- `num_engine_workers = heat_engine_workers` = `openstack_service_workers` (≤5) per engine host (:15-17;
  `defaults/main.yml:191`).

### 5.8 Operational notes

- **heat-engine restarts with stacks in progress:** Docker sends SIGTERM, then SIGKILL if heat-engine is still running
  after 60 s (`module_utils/kolla_systemd_worker.py:33`; `group_vars/all.yml:140,152`;
  [§0](#0-cross-cutting-facts-apply-to-all-five-roles)). NOT AVAILABLE (upstream heat): how that compares with the
  duration of long resource creates; whether stacks that a killed engine owned stay `*_IN_PROGRESS` until some engine
  starts again; whether heat-engine's `reset_stack_status` then marks them `FAILED` ("Engine went down during stack …");
  and whether users must then run `stack update` or a check/resume.
- With serial 0, **every heat-engine restarts in the same handler flush** on any heat.conf change. A memcached or rabbit
  membership change, a password rotation or an `openstack_service_workers` change is enough. Every in-progress stack in
  the cloud is therefore affected, not just a fraction.
- On upgrade the db sync runs while old engines are still active, and all engines restart together after it.
- Heat does not touch compute hosts. Its dependency on instance reachability to the external VIP (above) is the main
  network coupling.

---

## 6. Summary matrix: what `reconfigure` does per role

| role | keystone register | DB create/grant | bootstrap container (schema sync) on reconfigure | extra side effects on reconfigure | restarts (serial 0) |
|---|---|---|---|---|---|
| glance | yes | yes | **yes** (`KOLLA_BOOTSTRAP` on `glance_api_hosts[0]`) | **toggles GLOBAL `log_bin_trust_function_creators` 1→0** (unless `use_preconfigured_databases`); the Ussuri optional sanity image does not exist in 2023.1 | glance-api (and tls-proxy) on `glance_api_hosts` only (1 host with the file backend) |
| placement | yes | yes | **yes** (also runs online data migrations) | – | all placement-api |
| cinder | yes | yes | **yes** | – (the Ussuri optional sanity volume does not exist in 2023.1) | api, scheduler, **volume, backup on all storage hosts** at once if their config changed |
| horizon | **no** | only if `horizon_backend_database` | only if `horizon_backend_database` | env-driven recreate when plugin flags change | all horizon |
| heat | yes (also roles and a grant to admin) | yes | **yes** (with admin creds in env) | – | api, api-cfn, **all engines** |

The separate online-data-migration container (`KOLLA_OSM`) runs **only on `upgrade`**, for placement
(`roles/placement/tasks/upgrade.yml:16-34`) and cinder (`roles/cinder/tasks/upgrade.yml:26-44`). Glance's
expand/migrate/contract runs only in the rolling path. A reconfigure with a bumped image tag therefore runs cinder's
`db sync` without its OSM step (kolla `docker/cinder/cinder-api/extend_start.sh:6-14`), while placement's bootstrap
container runs both `db sync` and `db online_data_migrations` (kolla
`docker/placement/placement-api/extend_start.sh:5-9`). A reconfigure also skips cinder's second "remove RPC version pin"
restart, which only `upgrade.yml:24` runs. Whether this leaves cinder in a partially upgraded state is NOT AVAILABLE.
See [Kolla images §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run).

## 7. Things that scale with host count

- memcached and rabbit host lists in every config ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). Any membership
  change rewrites the config of all 5 services and restarts every container of every service.
- `glance_num_retries = len(groups['glance-api'])` (`roles/cinder/templates/cinder.conf.j2:20`).
- HAProxy backend lists: glance uses `glance_api_hosts` (`roles/glance/defaults/main.yml:84-85`); the others use
  `groups[host_group]` (`roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:96`).
- Placement and cinder credentials are embedded in nova-compute config on **every compute**. Password rotation therefore
  needs a reconfigure of the whole compute fleet ([§2.8](#28-operational-notes-and-the-relation-to-nova),
  [§3.7](#37-dependencies-templatescinderconfj2)).
- `run_once` tasks repeat per batch when `ANSIBLE_SERIAL` is set ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)).

## 8. NOT AVAILABLE list

1. NOT AVAILABLE: whether an existing glance file-store image stays readable after `enable_swift: yes` or
   `glance_backend_ceph: yes` is applied by reconfigure.
2. Answered from code: Glance rolling upgrade with `ANSIBLE_SERIAL=1` runs the contract at the end of batch 1, before
   later batches are upgraded ([§1.8](#18-operational-notes) note 4;
   [§0](#0-cross-cutting-facts-apply-to-all-five-roles) run_once + serial;
   `roles/glance/tasks/rolling_upgrade.yml:80-102`).
3. NOT AVAILABLE: Glance-api start time with a large NFS `glance_file_datadir_volume` (recursive chown,
   `glance-api.json.j2:54-58`).
4. NOT AVAILABLE: whether the glance cinder store works with `cinder_catalog_info = volume:cinder:internalURL` and no
   `[cinder]` store section.
5. NOT AVAILABLE: whether cinder-backup works with default `cinder_backup_driver=ceph` and `cinder_backend_ceph=no`
   (kolla-ansible gives it no ceph config, [§3.8](#38-operational-notes) oddity 5).
6. NOT AVAILABLE: whether the volumes owned by one of several RBD cinder-volume nodes (`host`) can still be managed
   while that node is down, and what state an in-flight create-from-image is in after a cinder-volume restart.
7. Cinder RPC pinning after `kolla-ansible upgrade` (is a second restart needed?): answered from code for 2023.1: the
   role does a second restart of every cinder service after the upgrade flush and a 30 s pause, to remove the RPC
   version pin (`roles/cinder/tasks/upgrade.yml:21-24`, `tasks/reload.yml:2-10`, `handlers/main.yml:70-88`;
   [§3.8](#38-operational-notes) note 4). Remaining NOT AVAILABLE: whether 30 s is always enough for all services to
   report their new version.
8. NOT AVAILABLE: Heat-engine restart with `CREATE_IN_PROGRESS` stacks: final state and recovery steps.
9. NOT AVAILABLE: Horizon restart: session survival (memcached) and start-up duration. When collectstatic/compress run
   is answered from kolla source ([§4.8](#48-operational-notes)).
10. Answered from kolla source: `bootstrap_heat` does **not** update the `heat_domain_admin` password once
    `heat_user_domain` exists (kolla `docker/heat/heat-api/extend_start.sh:10-14`; [§5.6](#56-bootstrap)). Remaining NOT
    AVAILABLE: how heat behaves after `heat_domain_admin_password` changes, when `heat.conf` gets the new value
    (`roles/heat/templates/heat.conf.j2:12`) but Keystone keeps the old one.
11. NOT AVAILABLE: whether the kolla-toolbox `mysql_user` task (from `community.mysql <3`, whose source is not among the
    studied trees) resets the DB user's password on every deploy/reconfigure ([§1.6](#16-bootstrap)).

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
