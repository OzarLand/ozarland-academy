---
title: Fact sheet C
description: "Fact sheet for Glance, Placement, Cinder, Horizon and Heat in 2025.1: per-role flow, bootstrap on reconfigure, dependencies and restart impact."
tags: [glance, placement, cinder, horizon, heat, reconfigure, one-shot]
---

# Fact sheet C

All paths are relative to the repo root (`$SRC`). Every claim comes from reading source code only: kolla-ansible at the
tag `2025.1-eom` (commit `7222f0f`), the kolla images repo at the tag `2025.1-eom` (commit `c4b53a2`), and, for Ansible
semantics, the Ansible source (cited as ansible-core 2.18.20 `lib/ansible/...:N`). Modules run inside the kolla-toolbox
image come from that image's `ansible-core==2.18.*` plus Ansible collections (kolla `docker/kolla-toolbox/Dockerfile.j2:107`,
`docker/kolla-toolbox/requirements.yml`); the collection sources installed in that image are not among the studied
trees.
- **FACT** (the default, not written out): shown by the cited source lines.
- **NOT AVAILABLE**: the sources do not establish it, for example upstream OpenStack runtime behaviour, durations, or
  what a restart does to work in progress. These points are to be confirmed by the community.

Behaviour inside the images (what `KOLLA_BOOTSTRAP`, `KOLLA_UPGRADE`, `KOLLA_OSM`, `GLANCE_DB_EXPAND` and similar
variables actually run) is defined in the separate `kolla` images repo, whose `2025.1-eom` tag was read (see
[Kolla images](../../concepts/kolla-images.md)). A statement that cites a kolla path, written as kolla `docker/...` (for
example kolla `docker/glance/glance-api/extend_start.sh` or kolla `docker/base/set_configs.py`), is read from that
source like any other code claim. Image-side behaviour without such a citation is NOT AVAILABLE.

**What changed since 2024.1, in one paragraph (FACT):** the five roles keep their task layout and `reconfigure.yml` is
still `import_tasks: deploy.yml`, so reconfigure still runs the bootstrap container. **Who decides a restart changed:**
the config tasks no longer notify (Placement's Apache virtual host task is the only exception); each role's
`check-containers.yml` imports `service-check-containers`, which compares every container and notifies only the
changed ones (`ansible/roles/service-check-containers/tasks/main.yml:4-41`). Each role gains a `check.yml` that imports
the `service-check` role. **Swift is gone:** the Glance `swift` store and the Cinder Swift backup driver are removed,
with no precheck ([Swift](../../components/swift.md)). Placement runs under uWSGI by default, Cinder gains HA and
coordination prechecks and a `block-storage` Keystone service, and every Glance, Cinder and Heat container mounts
`/dev/shm`.
`reconfigure` and `upgrade` now always run with `kolla_serial=0` ([F19](../findings.md#f19)).

> [!NOTE]
> **Key answers**
>
> - **Reconfigure runs the bootstrap (schema sync) container** in all five roles (for Horizon only with its DB backend),
>   exactly as deploy does; this still holds in 2025.1 ([§0](#0-cross-cutting-facts-apply-to-all-five-roles),
>   [§6](#6-summary-matrix-what-reconfigure-does-per-role)).
> - **Removed in 2025.1, Swift backends:** the Glance `swift` store and the Cinder Swift backup driver are gone and no
>   precheck looks for them; on a cloud whose only Glance store was Swift, `file` becomes the default store, on the
>   first `glance-api` host only ([§1.8](#18-operational-notes), [§3.4](#34-config-files-ansiblerolescindertasksconfigyml)).
> - **Changed in 2025.1, Placement under uWSGI:** `placement_wsgi_provider` defaults to `uwsgi`, so the first 2025.1
>   run replaces the Apache virtual host with a `placement-api-uwsgi.ini` and changes the container command
>   ([§2.4](#24-config-files-ansiblerolesplacementtasksconfigyml)).
> - **New in 2025.1, Cinder prechecks:** with more than one `cinder-volume` host and no `cinder_cluster_name`, or with
>   Ceph and no coordination backend, the prechecks fail; the upgrade does not register the new `block-storage`
>   service ([§3.3](#33-task-flow), [§3.6](#36-bootstrap)).
> - **Still holds:** the Glance file backend runs a single `glance-api` with no HA, Cinder's upgrade restarts every
>   Cinder container twice, and `bootstrap_heat` never updates the `heat_domain_admin` password
>   ([§1.8](#18-operational-notes), [§3.8](#38-operational-notes), [§5.6](#56-bootstrap)).

---

## 0. Cross-cutting facts (apply to all five roles)

| Topic | Fact | Evidence |
|---|---|---|
| Task dispatch | Every role's `tasks/main.yml` is `- include_tasks: "{{ kolla_action }}.yml"`. | e.g. `ansible/roles/glance/tasks/main.yml:2` (identical in placement/cinder/horizon/heat) |
| `reconfigure` | `reconfigure.yml` is just `- import_tasks: deploy.yml` in **all five** roles, so reconfigure performs keystone registration, DB create/grant and **the bootstrap (db sync) container**, exactly as deploy does. Still holds in 2025.1. | `ansible/roles/glance/tasks/reconfigure.yml:2` (identical in placement/cinder/horizon/heat) |
| `common` | None of the five roles has a `meta/` directory (each holds only `defaults`, `handlers`, `tasks`, `templates`, `vars`), so there is no role dependency on `common`. `common` is its own play, tagged `common`, on the `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` groups. | `ansible/roles/{glance,placement,cinder,horizon,heat}/` (no `meta/`); `ansible/site.yml:88-103` |
| Serial | Every play uses `serial: '{{ kolla_serial|default("0") }}'`. **Changed in 2025.1:** the Python CLI sets `kolla_serial` only for `reconfigure` and `upgrade`, and only to the constant `ANSIBLE_SERIAL = 0`, after the user's `-e`, so those two actions cannot be batched; a batched run is `deploy -e kolla_serial=N` ([F19](../findings.md#f19), [Controlled batches](../../operations/controlled-batches.md)). | `ansible/site.yml:547,582,596,729,743`; `kolla_ansible/cli/commands.py:22,136,278` |
| `max_fail_percentage` | Each of the five plays sets `max_fail_percentage: {{ <svc>_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}`. With the default 100 it never stops a play early: the ratio counts only the failures of the current batch (see [Controlled batches](../../operations/controlled-batches.md)). | `ansible/site.yml:548-551,583-586,597-600,730-733,744-747`; ansible-core 2.18.20 `lib/ansible/plugins/strategy/linear.py:335-349`, `lib/ansible/executor/task_queue_manager.py:323-333` |
| run_once + serial | Bootstrap, DB and keystone tasks are `run_once: True`. When `kolla_serial` > 0 (a `deploy -e kolla_serial=N`), Ansible runs the whole play once per batch and sends a `run_once` task only to the first host of the current batch, so `run_once` tasks run **once per batch**. So db sync and keystone registration repeat for each batch. | e.g. `ansible/roles/cinder/tasks/bootstrap_service.yml:19-20`; ansible-core 2.18.20 `lib/ansible/executor/playbook_executor.py:179-204`, `lib/ansible/plugins/strategy/linear.py:126,195,216` |
| Who notifies a restart | **Changed in 2025.1.** The config tasks have no `notify` (except Placement's Apache virtual host, [§2.4](#24-config-files-ansiblerolesplacementtasksconfigyml)). `check-containers.yml` = `import_role: service-check-containers`, which runs `compare_container` for each enabled, mapped service and notifies `Restart <key> container` for each changed one. The handlers lost their `kolla_action != "config"` guard, since `genconfig` no longer notifies anything. | `ansible/roles/glance/tasks/check-containers.yml:2-3` (identical in placement/cinder/horizon/heat); `ansible/roles/service-check-containers/tasks/main.yml:4-41`; [Tags §2.4](../../risk/tags.md#24-loop-notify-is-gone-in-20251-code) |
| Bootstrap container | `kolla_container action=start_container, detach: False, restart_policy: oneshot`. With Docker, a one-shot container gets no systemd unit and is started directly; the module waits for exit, then stops and removes it (`remove_on_exit` defaults to True), before it reports a non-zero exit. Nothing guards it with "already bootstrapped", so it **runs on every deploy/reconfigure**. | `ansible/library/kolla_container.py:293,312`; `ansible/module_utils/kolla_docker_worker.py:349-350,390-424`; e.g. `ansible/roles/glance/tasks/bootstrap_service.yml:19-37` |
| Restart semantics | Handlers use `recreate_or_restart_container` and pass `common_options: docker_common_options`, which carries `graceful_timeout: docker_graceful_timeout` (**60 s**) and `container_engine: kolla_container_engine`. Long-running containers run under a systemd unit `kolla-<name>-container.service` whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`; restarts and stops go through systemd `RestartUnit`/`StopUnit`. With Docker, SIGTERM is sent, then SIGKILL if the container is still running after 60 s. No role here overrides it. | `ansible/group_vars/all.yml:148,151-162`; `ansible/module_utils/kolla_systemd_worker.py:20-41,107-126`; `ansible/module_utils/kolla_docker_worker.py:352-374,426-470`; `ansible/library/kolla_container.py:366` |
| First 2025.1 check | The unit template changed again (`PartOf=kolla.target`) and the unit text is part of `compare_container`, so the first 2025.1 check of a container whose unit 2024.1 wrote reports it as changed and restarts it ([F16](../findings.md#f16)). The new unconditional `/dev/shm` volume of the Glance, Cinder and Heat containers changes their volume list too. | `ansible/module_utils/kolla_systemd_worker.py:27,155-168`; e.g. `ansible/roles/glance/defaults/main.yml:204,213` |
| Network | With Docker, all containers run with `network_mode: host`, so the container hostname is the node hostname (this matters for cinder `host`). | `ansible/module_utils/kolla_docker_worker.py:287` |
| Empty volume strings | Volume lists still contain `''` entries (timezone, dev-mode). `generate_volumes` skips empty entries, so the places that pass lists without `reject('equalto','')` are harmless. **Changed in 2025.1:** the `/dev/shm` entry is no longer conditional, so it is never empty. | `ansible/module_utils/kolla_container_worker.py:412-414` |
| Shared endpoints | `database_address: "{{ kolla_internal_fqdn }}"` (DB is reached through the VIP). `rpc_transport_url` / `notify_transport_url` enumerate **every** host in the rabbit groups. | `ansible/group_vars/all.yml:89,274,284` |
| memcached | Every service template (glance, placement, cinder, heat, horizon) enumerates **all** `groups['memcached']` hosts. Adding or removing a memcached or rabbitmq node therefore changes the config of all five services, and they restart on the next deploy/reconfigure. | e.g. `ansible/roles/heat/templates/heat.conf.j2:46,52` |
| RabbitMQ queues | **Changed in 2025.1:** `rabbit_quorum_queue = true` and `rabbit_transient_quorum_queue = true` are written unconditionally in the glance, cinder and heat configs, and `rabbit_stream_fanout` follows `om_enable_rabbitmq_stream_fanout` (default `true`); the `om_enable_rabbitmq_quorum_queues` switch is gone ([F17](../findings.md#f17)). Placement and Horizon have no `[oslo_messaging_rabbit]` section. | `ansible/group_vars/all.yml:292`; `ansible/roles/glance/templates/glance-api.conf.j2:120-126`; `ansible/roles/cinder/templates/cinder.conf.j2:83-89`; `ansible/roles/heat/templates/heat.conf.j2:84-90` |
| Workers | `openstack_service_workers: "{{ [ansible_facts.processor_vcpus, 5] | min }}"`. The value is per host. | `ansible/group_vars/all.yml:812` |
| Container checks | **New in 2025.1:** each role has a `check.yml` that imports the `service-check` role, which fails when an enabled container is missing, not running or reported unhealthy. The CLI has a `check` command that runs it with `kolla_action=check`. | e.g. `ansible/roles/glance/tasks/check.yml:2-4`; `ansible/roles/service-check/tasks/main.yml:3-40`; `kolla_ansible/cli/commands.py:495-506` |
| HAProxy | Each role's `loadbalancer.yml` is applied from the **loadbalancer play** (`site.yml:105-327`, tags `haproxy`, `keepalived`, `loadbalancer`), whose task block only runs when `enable_haproxy` and `kolla_action in ['deploy','reconfigure','upgrade','config']`. **Changed in 2025.1:** a `-t <service>` run no longer restarts HAProxy ([F18](../findings.md#f18)). | `ansible/site.yml:105-121,323-327` |
| TLS backend certs | **Changed in 2025.1:** `copy-certs.yml` (the `service-cert-copy` role) runs only when `<svc>_copy_certs` is true (`kolla_copy_ca_into_containers` or the service's `*_enable_tls_backend`). It copies the extra CA files, and the backend certificate and key only on hosts in the `tls-backend` group, each taken from the first file found among a per-host, a per-service and the global path. It notifies nothing: the container check decides the restart. | `ansible/roles/service-cert-copy/tasks/main.yml:2-45`; `ansible/roles/service-cert-copy/defaults/main.yml:4`; e.g. `ansible/roles/glance/tasks/config.yml:35-37`, `ansible/roles/glance/defaults/main.yml:308` |
| Service-to-host mapping | `host_in_groups` (used only by glance) takes precedence over `group` in the filter `service_mapped_to_host`, on which `select_services_enabled_and_mapped_to_host` is built. That filter drives pull/stop/cert-copy and the container check. | `kolla_ansible/filters.py:59-85,99-109` |
| Ansible forks | No `ansible.cfg` ships in the repo, so "all hosts restart together" really means up to `forks` hosts at once (Ansible default 5). **Changed in 2025.1:** the CLI has no `--forks` option, so `forks` comes from `ansible.cfg` or `ANSIBLE_FORKS`; the value in use is NOT AVAILABLE here. | `find . -name ansible.cfg` → none; `kolla_ansible/ansible.py:32-141`; ansible-core 2.18.20 `lib/ansible/config/base.yml:698-704`, `lib/ansible/executor/task_queue_manager.py:141,171-175` |
| Container engine | The module dispatches to a Podman worker when `kolla_container_engine` is not `docker` (default `docker`). Cinder-volume and cinder-backup then mount `/run` without `:shared` plus the `run_default_volumes_podman` sub-mounts. This sheet reads the Docker path; Podman behaviour on a host is NOT AVAILABLE. | `ansible/group_vars/all.yml:100,162,174-181`; `ansible/roles/cinder/defaults/main.yml:48,58,181,199` |

### site.yml order (relevant slice)

`loadbalancer` play (105) → … → **glance** (542) → ironic (556) → **cinder** (574) → **placement** (591) →
`import_playbook: nova.yml` (667) → … → **heat** (722) → **horizon** (738). Placement is therefore (re)deployed before
nova, and glance before cinder. Still holds in 2025.1 (`ansible/site.yml:105,542,556,574,591,667,722,738`).

---

## 1. GLANCE

### 1.1 Play

```yaml
# ansible/site.yml:542-554
- name: Apply role glance
  gather_facts: false
  hosts:
    - glance-api
    - '&enable_glance_True'
  serial: '{{ kolla_serial|default("0") }}'
  max_fail_percentage: >-
    {{ glance_max_fail_percentage |
       default(kolla_max_fail_percentage) |
       default(100) }}
  roles:
    - { role: glance,
        tags: glance }
```
- The role line has no `when: enable_glance`; the host pattern `&enable_glance_True` (group built at `site.yml:36`) does
  the selection.
- The LB include is at `ansible/site.yml:168-172` (tag `glance`, `when: enable_glance`).
- `enable_glance: "{{ enable_openstack_core | bool }}"` (`ansible/group_vars/all.yml:835`).

### 1.2 `glance_services` (`ansible/roles/glance/defaults/main.yml:2-72`)

| key | container | group / mapping | enabled | flags |
|---|---|---|---|---|
| glance-api | `glance_api` | `group: glance-api`, **`host_in_groups: inventory_hostname in glance_api_hosts`** (`defaults/main.yml:6`) | `true` | `privileged: enable_cinder and (enable_cinder_backend_iscsi or cinder_backend_ceph)` (`:10`); `environment: glance_api_container_proxy` = `container_proxy` (`:9`, `:219`). This is the only service in scope that receives http(s)_proxy. Volumes (`:197-207`): `glance_file_datadir_volume:/var/lib/glance/` (default named volume `glance`), **`/dev/shm` always** (changed in 2025.1, `:204`), and **`iscsi_info:/etc/iscsi` plus `/dev:/dev` when cinder iSCSI is enabled** (`:206-207`). |
| glance-tls-proxy | `glance_tls_proxy` | same `host_in_groups` (`defaults/main.yml:41`) | `glance_enable_tls_backend` (= `kolla_enable_tls_backend`, `all.yml:1148`) | HAProxy image (`<prefix>haproxy`, `defaults/main.yml:164`; changed in 2025.1, image names take `docker_image_name_prefix`). It listens on `api_interface_address:9292` with TLS and forwards to glance-api on `127.0.0.1`, port 9292 (`templates/glance-tls-proxy.cfg.j2:44-49`; glance-api `bind_host = 127.0.0.1` when TLS, `templates/glance-api.conf.j2:9-13`). It runs `nbthread {{ glance_tls_proxy_threads }}` (`defaults/main.yml:289`; `templates/glance-tls-proxy.cfg.j2:9`). |

**Critical mapping rule:**
```yaml
# ansible/group_vars/all.yml:1137,1142,1146
glance_backend_file: "{{ not (glance_backend_ceph | bool or glance_backend_s3 | bool or glance_backend_vmware | bool) }}"
glance_file_datadir_volume: "glance"
glance_api_hosts: "{{ [groups['glance-api'] | first] if glance_backend_file | bool and glance_file_datadir_volume == 'glance' else groups['glance-api'] }}"
```
With the default file backend on a local named volume, glance-api runs **only on the first host of `glance-api`**.
HAProxy members are built from `glance_api_hosts` too (`defaults/main.yml:90-91`), so glance has **no HA**. A glance-api
restart is a full Image API outage. The docs confirm this: "By default when using ``file`` backend only one
``glance-api`` container can be running" (`doc/source/reference/shared-services/glance-guide.rst:24-26`). **Changed in
2025.1:** `glance_backend_swift` is gone, so Swift no longer counts in `glance_backend_file`; a cloud whose only store
was Swift becomes a file-backend cloud with one `glance-api` ([§1.8](#18-operational-notes)).

HAProxy: client and server timeouts are **6h** (`defaults/main.yml:143-144`). In TLS mode the HAProxy members are the
`custom_member_list` `haproxy_tls_members`, which always carries `ssl verify required ca-file ...`
(`defaults/main.yml:58,71,91`), and **ignore `kolla_verify_tls_backend`**: the template prints a custom member list as
is (`ansible/roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:85-88`). Other services honour it
(`ansible/roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:93-97`).

### 1.3 Task flow per action

| action | flow |
|---|---|
| deploy / reconfigure | `deploy.yml`: `register.yml` → `config.yml` → `check-containers.yml` → (`clone.yml` if dev) → `bootstrap.yml` → `meta: flush_handlers` (`ansible/roles/glance/tasks/deploy.yml:1-15`; `ansible/roles/glance/tasks/reconfigure.yml:2`). |
| upgrade | `ansible/roles/glance/tasks/upgrade.yml:1-6`: `rolling_upgrade.yml` if `glance_enable_rolling_upgrade` (default `no`, `all.yml:1143`), else `legacy_upgrade.yml`. **No `register.yml`** in either path, so endpoints are not refreshed on upgrade. |
| legacy upgrade | `config.yml` → `check-containers.yml` → `bootstrap_service.yml` (db sync, new image) → flush (`ansible/roles/glance/tasks/legacy_upgrade.yml:1-9`). It does **not** stop glance-api first. The docs claim "This upgrade method will stop APIs during database schema migrations" (`glance-guide.rst:128`), but the code does not do that: the old glance-api keeps serving while the new-image bootstrap migrates the schema, and `check-containers.yml` notifies the restart that the flush runs afterwards. |
| rolling upgrade | see [§1.8](#18-operational-notes) |
| deploy-containers | `check-containers.yml` only, then handlers (`ansible/roles/glance/tasks/deploy-containers.yml:2`) |
| pull | `service-images-pull`. Only hosts where `host_in_groups` is true pull. |
| stop | `service-stop` with `glance_services` (`ansible/roles/glance/tasks/stop.yml:2-6`) |
| precheck | `service-precheck` (groups exist) plus a free-port check on 9292 when glance_api is not running (`ansible/roles/glance/tasks/precheck.yml:1-28`). When `glance_backend_s3`, an assert that the four `glance_backend_s3_*` variables are defined (`precheck.yml:30-40`). **No check for the removed Swift store.** |
| check | **New in 2025.1:** `check.yml` imports `service-check` ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). |
| config | `config.yml` only. Nothing is notified, so nothing restarts. |

### 1.4 Config files (`ansible/roles/glance/tasks/config.yml`)

**Changed in 2025.1:** no task in this table notifies a handler. The `check-containers.yml` step compares each container
and its `config.json` files and notifies the restart of each changed one
([§0](#0-cross-cutting-facts-apply-to-all-five-roles)).

| dest (under `/etc/kolla/`) | source / merge order | when |
|---|---|---|
| `glance-api/` and `glance-tls-proxy/` dirs | `file` (`config.yml:2-10`) | enabled and mapped |
| `glance-api/ceph/` dir | `file`, mode 0770 (`ansible/roles/glance/tasks/external_ceph.yml:2-12`) | `glance_backend_ceph` (`config.yml:12-14`) |
| `glance-api/ceph/<cluster>.conf` | `merge_configs` of `{{node_custom_config}}/glance/<cluster>.conf` + `glance/glance-api/<cluster>.conf`, once per entry of `glance_ceph_backends` (default one entry, cluster `ceph_cluster`, pool `ceph_glance_pool_name`, user `ceph_glance_user`, `defaults/main.yml:241-247`) | `glance_backend_ceph` (`external_ceph.yml:14-23`) |
| `glance-api/ceph/<cluster>.client.<user>.keyring` | **changed in 2025.1:** `template {{node_custom_config}}/glance/<cluster>.client.<user>.keyring`, the name built from each backend's `cluster` and `user`; the `ceph_glance_keyring` variable is gone. With the defaults the operator file is still `ceph.client.glance.keyring` | ceph (`external_ceph.yml:25-34`) |
| policy file | first found of `supported_policy_format_list` in `{{node_custom_config}}/glance/` (`config.yml:16-33`, `:114-124`) | if found |
| CA/TLS certs | `copy-certs.yml` → service-cert-copy (`config.yml:35-37`) | `glance_copy_certs` = `kolla_copy_ca_into_containers or glance_enable_tls_backend` (`defaults/main.yml:308`) |
| `glance-tls-proxy/glance-cert-and-key.pem` | `assemble` of `glance-(cert|key).pem` (`config.yml:39-49`) | TLS proxy enabled |
| `<svc>/config.json` | `glance-api.json.j2`, `glance-tls-proxy.json.j2` (`config.yml:51-57`) | – |
| `glance-api/glance-api.conf` | merge: `templates/glance-api.conf.j2` → `global.conf` → `glance.conf` → `glance/glance-api.conf` → `glance/<host>/glance-api.conf` (`config.yml:59-72`) | – |
| `glance-api/glance-cache.conf` | merge: template → `glance-cache.conf` → `glance/glance-cache.conf` → `glance/<host>/glance-cache.conf` (`config.yml:74-88`). Note that **no `global.conf`** is in this merge. | `enable_glance_image_cache` |
| `glance-api/glance-image-import.conf` | `copy {{node_custom_config}}/glance/glance-image-import.conf` (`config.yml:90-100`) | `glance_enable_interoperable_image_import` (default `no`, `all.yml:1145`) |
| `glance-api/property-protections-rules.conf` | `copy {{node_custom_config}}/glance/property-protections-rules.conf` (`config.yml:102-112`) | `glance_enable_property_protection` (default `no`, `all.yml:1144`) |
| `glance-tls-proxy/glance-tls-proxy.cfg` | first_found: `glance/<host>/glance-tls-proxy.cfg` → `glance/glance-tls-proxy.cfg` → role template (`config.yml:126-138`) | TLS proxy |

**Removed in 2025.1:** the `glance-swift.conf` task and template. A `glance-swift.conf` left in `/etc/kolla/glance-api/`
by 2024.1 is no longer listed in `config.json`, so it is no longer copied into the container; no task deletes it.

With Ceph, `glance-api.json.j2` copies the whole `ceph` directory to `/etc/ceph`
(`ansible/roles/glance/templates/glance-api.json.j2:15-21`).

`glance-api.json.j2:47-52` has
`"permissions": [{"path": "/var/lib/glance", "owner": "glance:glance", "recurse": true}]`. `/var/lib/glance` is the
`glance_file_datadir_volume` mount (`defaults/main.yml:201`), which with the file backend is the **entire image store**
(`filesystem_store_datadir = /var/lib/glance/images/`, `templates/glance-api.conf.j2:63`). kolla_set_configs walks it
and calls `os.chown` on every directory and file, unconditionally (kolla `docker/base/set_configs.py:347-409`).
It does this at every container start under the default `COPY_ALWAYS` (kolla `docker/base/start.sh:11`,
`set_configs.py:562-565`; `ansible/group_vars/all.yml:49`), and only on a container's first start under `COPY_ONCE`
(kolla `set_configs.py:566-575`); see
[Kolla images §2](../../concepts/kolla-images.md#2-start-path-common-to-every-image). NOT AVAILABLE: how long this
recursive chown takes at container start with a big NFS-backed `glance_file_datadir_volume`.

### 1.5 Handlers (`ansible/roles/glance/handlers/main.yml`)

- `Restart glance-api container` (`handlers/main.yml:2-16`): recreate_or_restart. It passes `privileged`,
  `environment` (the proxy), volumes, dimensions and healthcheck.
- `Restart glance-tls-proxy container` (`handlers/main.yml:18-30`): recreate_or_restart.
- Neither has special logic, and changed in 2025.1, neither has a `kolla_action != "config"` guard any more. There is
  no rolling restart and no wait for the API to come back.

### 1.6 Bootstrap

| step | where | re-runs on reconfigure? |
|---|---|---|
| `mysql_db glance` | `ansible/roles/glance/tasks/bootstrap.yml:2-16`, run_once, delegate `groups['glance-api'][0]`, unless `use_preconfigured_databases` | yes (idempotent) |
| `mysql_user glance` with password and `ALL` on `glance.*` | `bootstrap.yml:18-36` | yes. The task runs `mysql_user` through `kolla_toolbox`, which runs `ansible localhost -m mysql_user` inside the toolbox container (`ansible/library/kolla_toolbox.py:135-151`); the module comes from the `community.mysql` collection installed in that image (kolla `docker/kolla-toolbox/requirements.yml`). That collection's source is not among the studied trees, so whether each run resets the stored password when it differs is NOT AVAILABLE. |
| **Set GLOBAL `log_bin_trust_function_creators=1`** | `ansible/roles/glance/tasks/bootstrap_service.yml:2-17`, logged in as `glance_database_shard_root_user` (`root_shard_<id>` with ProxySQL, the 2025.1 default; the DB root user otherwise, `defaults/main.yml:129`), unless `use_preconfigured_databases` | **yes, on every deploy/reconfigure** |
| `bootstrap_glance` container, `KOLLA_BOOTSTRAP`: `glance-manage db_sync` then `glance-manage db_load_metadefs` (kolla `docker/glance/glance-api/extend_start.sh:5-9`) | `bootstrap_service.yml:19-37`, delegate `glance_api_hosts[0]` | **yes, so a schema sync runs on every reconfigure** |
| Set `log_bin_trust_function_creators=0` | `bootstrap_service.yml:39-54` | yes |
| Keystone: service `glance`/`image`, 2 endpoints (internal, public), user `glance` (admin in `service`) | `ansible/roles/glance/tasks/register.yml:2-7`; `defaults/main.yml:96-108` | yes (deploy/reconfigure); **not** on upgrade |

**Oddity / risk:** the enable/db_sync/disable sequence is still not wrapped in `block/always`. If the bootstrap
container fails, the global MariaDB variable stays at `1`. Whether this leftover state has security consequences is NOT
AVAILABLE.

**Reconfigure as uncontrolled upgrade:** if an operator bumps `openstack_tag`/`glance_tag` and runs `reconfigure`, the
new image runs the `KOLLA_BOOTSTRAP` branch (`glance-manage db_sync` and `db_load_metadefs`, kolla
`docker/glance/glance-api/extend_start.sh:5-9`) and the container check sees the new image, so glance-api is recreated
on it. For the glance role that is the default legacy upgrade (`glance_enable_rolling_upgrade: "no"`, `all.yml:1143`):
`legacy_upgrade.yml:2-9` runs the same config, check-containers, `bootstrap_service.yml` and flush steps, and
reconfigure only adds registration, DB/user creation and the dev-mode clone (`deploy.yml:2-15`).

### 1.7 Dependencies (from `templates/glance-api.conf.j2`)

- **MariaDB** via the VIP (`glance-api.conf.j2:32-36`); **RabbitMQ**: `transport_url = rpc_transport_url` (`:25`) and
  notifications (`:104-111`; topic `notifications` only if ceilometer, otherwise `driver = noop`,
  `defaults/main.yml:113-117`). **Changed in 2025.1:** `[oslo_messaging_rabbit]` always writes `use_queue_manager = true`,
  `rabbit_quorum_queue = true` and `rabbit_transient_quorum_queue = true`, and `rabbit_stream_fanout` by default
  (`glance-api.conf.j2:113-125`; [F17](../findings.md#f17)).
- **Keystone**: changed in 2025.1, `www_authenticate_uri` is `keystone_public_url` and `auth_url` is
  `keystone_internal_url` (`glance-api.conf.j2:38-49`); `memcache_security_strategy` comes from a variable (`:51`).
  **memcached**: all hosts (`:53`).
- **Cinder**: `enabled_backends` contains `cinder:cinder` whenever `enable_cinder` (`defaults/main.yml:237-239`;
  `glance-api.conf.j2:17-19`). **Changed in 2025.1:** `cinder_catalog_info` is no longer written, and Cinder registers a
  `block-storage` service next to the deprecated `cinderv3/volumev3` (`ansible/roles/cinder/defaults/main.yml:346-359`);
  the template still has no `[cinder]` store section. Which catalog entry the glance cinder store then looks up is NOT
  AVAILABLE. Nova now uses `catalog_info = block-storage::internalURL`
  (`ansible/roles/nova-cell/templates/nova.conf.j2:112`).
- **Ceph**: one `[<backend name>]` section per entry of `glance_ceph_backends` (default `[rbd]`), with
  `rbd_store_user/pool` taken from the backend and `rbd_store_ceph_conf = /etc/ceph/<cluster>.conf`
  (`glance-api.conf.j2:66-73`). The template still does not set `show_multiple_locations`
  (`grep -rn show_multiple_locations ansible/roles/glance` → nothing).
- **Default store**: `default_backend = "{{ glance_default_backend }}"` (`glance-api.conf.j2:59`), where
  `glance_default_backend` picks vmware, then the first Ceph backend, then s3, then file; changed in 2025.1, swift is no
  longer in that list (`defaults/main.yml:250`). The value is rendered between double quotes; how glance's config parser
  reads the quotes is NOT AVAILABLE.
- **Swift**: removed in 2025.1. There is no `[swift]` section and no `glance-swift.conf` any more
  ([Swift](../../components/swift.md)).
- **S3**: `[s3]` with `s3_store_host/access_key/secret_key/bucket` from `glance_backend_s3_*`, which default to the
  global `s3_url`, `s3_bucket`, `s3_access_key`, `s3_secret_key` (`glance-api.conf.j2:75-81`;
  `defaults/main.yml:149-152`; `all.yml:1390-1393`).
- **Barbican** (`glance-api.conf.j2:140-145`), **osprofiler** (`:132-138`), **VMware** (`:83-90`), and
  `[cors] allowed_origin = {{ horizon_public_endpoint }}` (`:147-148`).
- Cinder iSCSI flag toggles glance-api `/dev` and `iscsi_info`, and cinder iSCSI or `cinder_backend_ceph` toggles
  `privileged` (`defaults/main.yml:10,206-207`). How glance uses these mounts is NOT AVAILABLE.

### 1.8 Operational notes

1. **Backend switch via unrelated flags:** `glance_backend_file` is the negation of ceph/s3/vmware (`all.yml:1137`).
   Enabling `glance_backend_ceph` or `glance_backend_s3` on a running cloud does three things:
   - removes `file` from `enabled_backends` and drops the `[file]` section (`defaults/main.yml:228-230`;
     `glance-api.conf.j2:17-19,61-64`);
   - changes `default_backend` (`defaults/main.yml:250`; `glance-api.conf.j2:59`);
   - expands `glance_api_hosts` to every `glance-api` host (`all.yml:1146`).

   NOT AVAILABLE: whether existing images in the file store stay readable after the switch.

   A related doc mismatch, still present: the guide says ceph is enabled "automatically" (`glance-guide.rst:42`), but
   the default is `glance_backend_ceph: "no"` (`all.yml:1138`).
2. **Removed in 2025.1, the Swift store, with no check:** on a cloud that ran `enable_swift` with no other store, the
   first 2025.1 run turns `file` into the default store, shrinks `glance_api_hosts` to the first `glance-api` host and
   stops `glance-api` nowhere else: the other hosts keep their old containers, which no longer appear in the HAProxy
   members ([Swift](../../components/swift.md), [Glance](../../components/glance.md)). NOT AVAILABLE: what Glance does
   with images whose locations point at the removed `swift` store.
3. **Inventory order matters:** with the file backend, glance runs on `groups['glance-api']|first`. The INI parser reads
   the file line by line and adds each host in that order, and Ansible lists a group's hosts in the order they were
   added (ansible-core 2.18.20 `lib/ansible/plugins/inventory/ini.py`, `lib/ansible/inventory/group.py`), so reordering
   the inventory moves glance-api to another host, and the HAProxy members follow it (`all.yml:1146`;
   `defaults/main.yml:90-91`). NOT AVAILABLE: what the `glance` volume on the new host contains.
4. **Restart impact:** the HAProxy client and server timeouts are 6h (`defaults/main.yml:143-144`). Restarting
   glance-api stops it with the 60 s graceful timeout ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). With the
   file backend this is a total Image API outage, because glance-api is the only backend
   ([§1.2](#12-glance_services-ansiblerolesglancedefaultsmainyml2-72)). NOT AVAILABLE: what the restart does to
   in-flight uploads, downloads, nova snapshots and cinder upload-to-image operations, whether images are left in
   `saving`/`queued`, and whether nova boots that need an uncached image fail during the window.
5. **Rolling upgrade** (`ansible/roles/glance/tasks/rolling_upgrade.yml`), unchanged in 2025.1 apart from the restart
   decision:
   - Sequence: config on host[0] (`rolling_upgrade.yml:7-8`) → **stop glance-api on host[0]** (`:10-11`,
     `stop_service.yml`) → enable log_bin (`:13-28`) → `GLANCE_DB_EXPAND` (`:30-49`) → `GLANCE_DB_MIGRATE`, which
     notifies restart (`:51-73`) → config on the other hosts (`:75-76`) → check-containers (`:78`) → **flush
     handlers**, so all glance-api containers restart in the same handler run (`:80-81`) → `GLANCE_DB_CONTRACT`
     (`:83-102`) → disable log_bin (`:104-119`).
   - The `glance_upgrading` fact (`:2-4`, `:121-123`) is set but never read anywhere (dead code;
     `grep -rn glance_upgrading ansible/` finds only this file).
   - **Changed in 2025.1:** `upgrade` always runs with `kolla_serial=0` ([F19](../findings.md#f19)), so the 2024.1
     risk of a contract at the end of batch 1 no longer arises from the CLI. Each run_once step (`:25-26`, `:48-49`,
     `:69-70`, `:101-102`) runs once, on `glance_api_hosts[0]`.
   - The docs warn that rolling upgrade with a non-shared file backend leads to "a corrupt state"
     (`glance-guide.rst:119-121`).
6. **Image cache** is never pruned. The docs say "Glance caches are not cleaned up automatically"
   (`glance-guide.rst:158`); there is no cron/pruner container.
7. Glance does not touch compute hosts. Nova-compute reaches glance through `[glance] api_servers` =
   `glance_internal_endpoint` (internal FQDN, port 9292, `all.yml:414`;
   `ansible/roles/nova-cell/templates/nova.conf.j2:104-106`), and cinder through `glance_api_servers`
   (`ansible/roles/cinder/templates/cinder.conf.j2:18`).

---

## 2. PLACEMENT

### 2.1 Play

```yaml
# ansible/site.yml:591-603
- name: Apply role placement
  gather_facts: false
  hosts: [placement-api, '&enable_placement_True']
  serial: '{{ kolla_serial|default("0") }}'
  max_fail_percentage: '{{ placement_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}'
  roles: [{ role: placement, tags: placement }]
```
- `enable_placement: "{{ enable_nova | bool or enable_zun | bool }}"` (`all.yml:956`).
- **Oddity, still holds in 2025.1:** the LB include for placement **has no `when: enable_placement`**
  (`site.yml:248-251`), unlike every other service. When placement is disabled it still writes an (effectively empty)
  `services.d/placement-api.cfg`, because `placement-api.enabled: True` (`ansible/roles/placement/defaults/main.yml:7`)
  and the haproxy-config task checks only `service.enabled`, `service.haproxy` and `enable_haproxy`
  (`ansible/roles/haproxy-config/tasks/main.yml:17-20`). Only the inner haproxy entries carry `enable_placement`
  (`ansible/roles/placement/defaults/main.yml:14,23`), and the template skips disabled entries
  (`ansible/roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:121`).
- The play sits right before `import_playbook: nova.yml` (`site.yml:667`).

### 2.2 `placement_services` (`ansible/roles/placement/defaults/main.yml:2-31`)

| key | container | group | enabled | flags |
|---|---|---|---|---|
| placement-api | `placement_api` | `placement-api` | `True` | **Changed in 2025.1:** a `wsgi: "placement.wsgi.api:application"` key (`defaults/main.yml:11`) feeds the uWSGI config. No privileged, no host paths beyond config, localtime, timezone (Debian) and logs, plus the dev-mode source (`defaults/main.yml:85-90`). Unlike glance, cinder and heat it gets no `/dev/shm` entry. HAProxy internal and external on 8780, `tls_backend: placement_enable_tls_backend`, and new in 2025.1, `option httpchk GET /` on both entries (`defaults/main.yml:12-31`). |

### 2.3 Task flow

| action | flow |
|---|---|
| deploy / reconfigure | `register.yml` → (clone) → `config.yml` → `check-containers.yml` → `bootstrap.yml` → flush (`ansible/roles/placement/tasks/deploy.yml:1-14`) |
| upgrade | `register.yml` → (clone) → `config.yml` → `check-containers.yml` → `bootstrap.yml` (`KOLLA_BOOTSTRAP` with the new image: `placement-manage db sync` **and** `db online_data_migrations`, kolla `docker/placement/placement-api/extend_start.sh:5-9`, while the old placement-api is still running; the image's `KOLLA_UPGRADE` branch, db sync only, `:12-15`, is not used) → flush (all placement-api restart) → **`KOLLA_OSM` online data migrations** container, which runs them a second time (`ansible/roles/placement/tasks/upgrade.yml:1-34`) |
| deploy-containers | `check-containers.yml` |
| pull / stop | service-images-pull / service-stop |
| precheck | groups exist, port 8780 free if not running (`ansible/roles/placement/tasks/precheck.yml:1-29`) |
| check | **new in 2025.1:** `service-check` (`ansible/roles/placement/tasks/check.yml:2-4`) |
| config | `config.yml` |

### 2.4 Config files (`ansible/roles/placement/tasks/config.yml`)

| dest | sources | notifies |
|---|---|---|
| `placement-api/config.json` | `placement-api.json.j2` (`config.yml:35-41`). **Changed in 2025.1:** the command is `uwsgi /etc/placement/placement-api-uwsgi.ini` with the default `placement_wsgi_provider: "uwsgi"`, and Apache only with `apache` (`templates/placement-api.json.j2:3`; `defaults/main.yml:156`) | – |
| `placement-api/placement.conf` | merge: template → `global.conf` → `placement.conf` → `placement/placement-api.conf` → `placement/<host>/placement.conf` (`config.yml:43-56`) | – |
| `placement-api/placement-api-wsgi.conf` | first_found: `placement/<host>/placement-api-wsgi.conf` → `placement/placement-api-wsgi.conf` → template (`config.yml:58-74`). **Changed in 2025.1:** written only when `placement_wsgi_provider == "apache"`. | **Restart placement-api** (the only notify left in the five roles, `config.yml:73-74`) |
| `placement-api/placement-api-uwsgi.ini` | **new in 2025.1:** the shared `service-uwsgi-config` role, with port `placement_api_listen_port`, module from `wsgi`, workers `placement_api_workers`, and the TLS backend files when enabled (`config.yml:76-92`; `ansible/roles/service-uwsgi-config/templates/uwsgi.ini.j2`). Its log goes to `/var/log/kolla/placement/placement-api-uwsgi.log` (`ansible/roles/service-uwsgi-config/defaults/main.yml:4-5`). | – |
| `placement-api/migrate-db.rc` | `migrate-db.rc.j2` (`config.yml:94-102`) | – |
| policy | `{{node_custom_config}}/placement/` (`config.yml:12-29`, `:104-113`) | – |
| certs | service-cert-copy (`config.yml:31-33`) | – |

The first 2025.1 run on a cloud that kept the default therefore changes `config.json` (the command and the file list),
drops the Apache virtual host from it and adds the uWSGI file, so the container check recreates `placement_api`
([Placement](../../components/placement.md)). NOT AVAILABLE: whether a 2024.1 override of `placement-api-wsgi.conf`
still matters (it is only read with the `apache` provider).

`migrate-db.rc` still contains the **nova_api DB user and password** together with the placement DB creds
(`ansible/roles/placement/templates/migrate-db.rc.j2:1-8`; vars at `defaults/main.yml:124-127`). The defaults file
files these vars under "Upgrade" (`defaults/main.yml:121-123`); no task of the role uses it, and the container receives
it as `/etc/placement/migrate-db.rc` (`templates/placement-api.json.j2:31-36`). It spreads a nova secret into the
placement container, and a change of it restarts placement-api through the container check.

### 2.5 Handlers

`Restart placement-api container`: recreate_or_restart, no special logic and no `kolla_action` guard
(`ansible/roles/placement/handlers/main.yml:2-14`).

### 2.6 Bootstrap

- `mysql_db placement` and `mysql_user` (`ansible/roles/placement/tasks/bootstrap.yml:2-36`) re-run on reconfigure.
- `bootstrap_placement` with `KOLLA_BOOTSTRAP` (kolla image: `placement-manage db sync` then
  `placement-manage db online_data_migrations`, kolla `docker/placement/placement-api/extend_start.sh:5-9`) runs once,
  delegated to `groups['placement-api'][0]` (`ansible/roles/placement/tasks/bootstrap_service.yml:2-20`). **It re-runs
  on every reconfigure.**
- Keystone registration (service `placement`, 2 endpoints, internal and public, user `placement`,
  `defaults/main.yml:132-144`) happens in deploy, reconfigure **and upgrade** (`upgrade.yml:2`), unlike glance and heat.
- Online data migrations: the separate `KOLLA_OSM` container runs **only** in upgrade (`upgrade.yml:16-34`). Because the
  bootstrap container above also runs `db online_data_migrations`, placement OSM also runs on every deploy/reconfigure
  (`deploy.yml:11`, `reconfigure.yml:2`) and twice in upgrade (bootstrap at `upgrade.yml:11`, then `KOLLA_OSM`).

### 2.7 Dependencies (`templates/placement.conf.j2`)

- MariaDB `[placement_database]` with **`max_overflow = 1000` hard-coded** (`placement.conf.j2:14-19`).
- memcached `[cache]` and `keystone_authtoken` (`:21-42`); Keystone (`:27-38`), with `www_authenticate_uri` now the
  public Keystone URL (`:29`).
- The template sets no `transport_url` (placement does no RPC).
- `[DEFAULT]` holds only debug, log and state paths (`:1-6`); the log file is now named after the service
  (`log_file = /var/log/kolla/placement/{{ service_name }}.log`, `:4`).
- **Dead variables:** `placement_notification_topics` / `placement_enabled_notification_topics`
  (`defaults/main.yml:106-110`) are not referenced by any template. There is no `[oslo_messaging_notifications]`
  section.

### 2.8 Operational notes and the relation to nova

- **Consumers authenticate as the placement user.** nova-api/conductor/scheduler
  (`ansible/roles/nova/templates/nova.conf.j2:180-190`) and **nova-compute on every compute host**
  (`ansible/roles/nova-cell/templates/nova.conf.j2:224-234`) use `username = {{ placement_keystone_user }}` /
  `password = {{ placement_keystone_password }}`, `valid_interfaces = internal`. Neutron does the same with
  `endpoint_type = internal` (`ansible/roles/neutron/templates/neutron.conf.j2:185-193`), as does cyborg
  (`ansible/roles/cyborg/templates/cyborg.conf.j2:34-44`); zun does not (its `[placement_client]` has no credentials,
  `ansible/roles/zun/templates/zun.conf.j2:92-95`). Rotating `placement_keystone_password` therefore needs a
  reconfigure of placement **and** nova (all computes) **and** neutron. This dependency scales with the number of
  compute hosts.
- NOT AVAILABLE (upstream nova): how scheduling and the nova-compute resource tracker periodic task behave during a
  placement-api outage or restart. With serial=0 every placement-api restarts in the same handler flush, up to `forks`
  hosts at once ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)); whether and for how long no placement-api is
  serving is NOT AVAILABLE, and how uWSGI ends in-flight requests on stop is NOT AVAILABLE.
- The upgrade db sync and online data migrations (bootstrap container) run while the old placement-api is still serving
  (no stop).

---

## 3. CINDER

### 3.1 Play

```yaml
# ansible/site.yml:574-589
- name: Apply role cinder
  gather_facts: false
  hosts: [cinder-api, cinder-backup, cinder-scheduler, cinder-volume, '&enable_cinder_True']
  serial: '{{ kolla_serial|default("0") }}'
  max_fail_percentage: '{{ cinder_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}'
  roles: [{ role: cinder, tags: cinder }]
```
- LB include: `site.yml:143-147`.
- Defaults: `enable_cinder: "no"`, `enable_cinder_backup: "yes"`,
  `enable_cinder_backend_iscsi: "{{ enable_cinder_backend_lvm | bool }}"`, `enable_cinder_backend_lvm: "no"`
  (`all.yml:863-866`). `cinder_backend_ceph: "no"`, `cinder_backup_driver: "ceph"` (`all.yml:1170,1181`).
- Sample inventory: `cinder-api`/`cinder-scheduler` sit under `[cinder:children] control`.
  **`cinder-volume`/`cinder-backup` sit under `storage`** (`ansible/inventory/multinode:110-111,286-297`).

### 3.2 `cinder_services` (`ansible/roles/cinder/defaults/main.yml:2-60`)

| key | container | group | enabled | flags / host volumes |
|---|---|---|---|---|
| cinder-api | `cinder_api` | cinder-api | true | **Changed in 2025.1:** uWSGI on 8776 by default (`wsgi` key at `defaults/main.yml:11`; `cinder_wsgi_provider: "uwsgi"`, `:387`); HAProxy internal and external with `option httpchk` (`:12-31`); `/dev/shm` always (`:173`) |
| cinder-scheduler | `cinder_scheduler` | cinder-scheduler | true | `/dev/shm` always (`defaults/main.yml:191`) |
| cinder-volume | `cinder_volume` | cinder-volume | true | **`privileged: True`, `ipc_mode: host`** (`defaults/main.yml:45-46`), `tmpfs` for `/var/lib/cinder/conversion` only if `cinder_enable_conversion_tmpfs` (default false, `:47,212-216`). Volumes (`:193-202`, plus `run_default_volumes_<engine>`, empty for Docker, `:48`): **`/dev/:/dev/`, `/lib/modules:ro`, `/run:/run:shared`** (`:shared` only with Docker), `cinder:/var/lib/cinder`, **`iscsi_info:/etc/iscsi`** (if `enable_iscsid`), **`target_config:/etc/target`** (LVM and `lioadm`). |
| cinder-backup | `cinder_backup` | cinder-backup | `enable_cinder_backup` | **`privileged: True`** and, **new in 2025.1, `ipc_mode: host`** (`defaults/main.yml:56-57`). Volumes (`:175-183`, plus `run_default_volumes_<engine>`, `:58`): `/dev/`, `/lib/modules`, `/run` (`:shared` with Docker), `cinder:/var/lib/cinder`, `iscsi_info`. |

Related: `cinder_target_helper` is `lioadm` on RedHat and `tgtadm` otherwise (`all.yml:1176`). With `tgtadm` the targets
are served by a **separate `tgtd` container** from the `iscsi` role, which also deploys `iscsid` on `compute`,
`cinder-volume` and `cinder-backup` hosts (`ansible/roles/iscsi/defaults/main.yml:2-20,62-73`; play
`site.yml:454-467`).

### 3.3 Task flow

| action | flow |
|---|---|
| deploy / reconfigure | `register.yml` → `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` → flush (`ansible/roles/cinder/tasks/deploy.yml:1-14`) |
| upgrade | `config.yml` **only on `groups['cinder-api'][0]`** (`upgrade.yml:4-5`) → `bootstrap_service.yml` (db sync, new image, old services still running) (`:7`) → `config.yml` on all (`:9`) → `check-containers.yml` (`:11`) → flush, so **every cinder container that the check reports changed restarts in this flush**; with the new image that is every container on every host, cinder-volume and cinder-backup included; on upgrade a handler then pauses `cinder_rpc_version_startup_delay` (30 s) once (`:13-14`; `handlers/main.yml:71-81`; `defaults/main.yml:237`) → **`reload.yml`: `restart_container` of every enabled cinder container on the host again, "to remove RPC version pin"** (`upgrade.yml:16`; `ansible/roles/cinder/tasks/reload.yml:2-10`) → `KOLLA_OSM` online migrations (`upgrade.yml:18-36`). **Changed in 2025.1:** the 2024.1 `service-ks-register` step for the user's `service` role is gone. No `register.yml`, so services and endpoints are not refreshed: the new `block-storage` service appears only at the next deploy/reconfigure ([§3.6](#36-bootstrap)). `upgrade` always runs with `kolla_serial=0` ([F19](../findings.md#f19)). |
| deploy-containers | check-containers |
| pull / stop | helpers |
| precheck | groups; API port free; **at least one backend enabled** unless `skip_cinder_backend_check` (`ansible/roles/cinder/tasks/precheck.yml:29-46`); **`vgs cinder-volumes`** on cinder-volume hosts if LVM (`:48-58`); **new in 2025.1:** a coordination backend is required when `cinder_backend_ceph` is on and `cinder-volume` has more than one host, unless `skip_cinder_backend_check` (`:60-68`); an assert on the four `cinder_backup_s3_*` variables when `cinder_backup_driver == "s3"` (`:70-80`); **new in 2025.1:** an assert on the Lightbits variables (`:82-90`), and the two `cinder_cluster_name` checks: set with more than one `cinder-volume` host, empty with one, both skipped by `cinder_cluster_skip_precheck` (`:92-115`; `defaults/main.yml:381-382`). |
| check | **new in 2025.1:** `service-check` (`ansible/roles/cinder/tasks/check.yml:2-4`) |
| config | `config.yml` |

### 3.4 Config files (`ansible/roles/cinder/tasks/config.yml`)

**Changed in 2025.1:** only the Huawei XML task notifies (`ansible/roles/cinder/tasks/external_huawei.yml:10-11`); every
other change restarts a container through the container check ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)).

| dest | sources | when |
|---|---|---|
| `cinder-volume/ceph/`, `cinder-backup/ceph/` dirs | `file`, mode 0770 (`ansible/roles/cinder/tasks/external_ceph.yml:2-15`) | `cinder_backend_ceph` and host in volume/backup (`config.yml:18-22`) |
| `<svc>/ceph/<cluster>.conf` (cinder-volume, cinder-backup) | merge `cinder/<cluster>.conf` + `cinder/<svc>/<cluster>.conf`, once per service and per entry of `cinder_ceph_backends` (default one entry `rbd-1`, cluster `ceph_cluster`, user `ceph_cinder_user`, pool `ceph_cinder_pool_name`, `defaults/main.yml:278-284`) (`external_ceph.yml:17-37`) | `cinder_backend_ceph` and host in volume/backup |
| `cinder-volume/ceph/<cluster>.client.<user>.keyring` | **changed in 2025.1:** `cinder/cinder-volume/<cluster>.client.<user>.keyring`, the name built from each backend's `cluster` and `user`; `ceph_cinder_keyring` is gone (`external_ceph.yml:39-51`) | cephx |
| `cinder-backup/ceph/` keyrings (cinder plus cinder-backup) | `cinder/cinder-backup/<cluster>.client.<user>.keyring` for every backend and for `cinder_backup_ceph_backend`, which adds `ceph_cinder_backup_user` and `ceph_cinder_backup_pool_name` (`external_ceph.yml:53-67`; `defaults/main.yml:286-287`; `all.yml:1293-1300`) | cephx |
| Huawei XML files | **new in 2025.1** (`config.yml:12-16`; `external_huawei.yml:2-11`) | `cinder_backend_huawei` | 
| policy | `{{node_custom_config}}/cinder/` (`config.yml:24-41`, `:116-124`) | |
| certs | service-cert-copy (`config.yml:43-45`) | `cinder_copy_certs` |
| `<svc>/config.json` | `<svc>.json.j2` (`config.yml:47-53`) | |
| `cinder-api/cinder-wsgi.conf` | first_found: `cinder/<host>/cinder-wsgi.conf` → `cinder/cinder-wsgi.conf` → template (`config.yml:55-69`) | **changed in 2025.1:** only with `cinder_wsgi_provider == "apache"` |
| `cinder-api/cinder-api-uwsgi.ini` | **new in 2025.1:** `service-uwsgi-config` (`config.yml:71-88`) | `cinder_wsgi_provider == "uwsgi"` (the default) |
| `<svc>/cinder.conf` (one per service, `service_name` var) | merge: template → `global.conf` → `cinder.conf` → `cinder/<svc>.conf` → `cinder/<host>/cinder.conf` (`config.yml:90-103`). **Changed in 2025.1:** the rendered file differs per service ([§3.7](#37-dependencies-templatescinderconfj2)). | |
| `cinder-volume/hostnqn` | template `hostnqn.j2`, value `nqn.2014-08.org.nvmexpress:uuid:<to_uuid of the host name>` (`config.yml:105-114`); copied into the container as `/etc/nvme/hostnqn`, owner root (`templates/cinder-volume.json.j2:30-35`) | host in cinder-volume |
| `cinder-volume/nfs_shares` | first_found among 8 paths (`nfs_shares.j2` variants, then plain), `skip` unless NFS (`config.yml:126-145`); **changed in 2025.1:** the HNAS backend is removed | host in cinder-volume |

The Ceph files sit in `ceph/` and are copied to `/etc/ceph` (`templates/cinder-volume.json.j2:16-22`,
`templates/cinder-backup.json.j2:15-21`), as in 2024.1.

### 3.5 Handlers (`ansible/roles/cinder/handlers/main.yml`)

Four restart handlers (api `handlers/main.yml:2-14`, scheduler `:16-28`, volume `:30-45`, backup `:47-61`), all
recreate_or_restart. The volume handler passes `privileged`, `ipc_mode` and `tmpfs`; the backup handler passes
`privileged` and, new in 2025.1, `ipc_mode`. A fifth handler, `Wait for cinder services to update service versions`
(`:71-81`), listens to all four and pauses 30 s once, only when `kolla_action == 'upgrade'`. There is no drain logic,
and changed in 2025.1, no `kolla_action != "config"` guard.

### 3.6 Bootstrap

- `mysql_db cinder` and `mysql_user` run every deploy/reconfigure (`ansible/roles/cinder/tasks/bootstrap.yml:2-36`).
- `bootstrap_cinder` (`KOLLA_BOOTSTRAP`: `cinder-manage db sync`, kolla `docker/cinder/cinder-api/extend_start.sh:6-9`),
  run_once on `groups['cinder-api'][0]` (`ansible/roles/cinder/tasks/bootstrap_service.yml:2-20`). **It re-runs on
  every reconfigure.**
- Online data migrations (`KOLLA_OSM`) run only in upgrade.
- Keystone, **changed in 2025.1:** a `cinder` service of type `block-storage` with `/v3` endpoints (internal, public)
  and the `cinderv3/volumev3` service kept as deprecated, with its `/v3/%(tenant_id)s` endpoints; user `cinder` (admin
  in `service`); the `service` role granted to the cinder user in the `service` project
  (`defaults/main.yml:346-370`; `ansible/roles/cinder/tasks/register.yml:2-8`). The role does not pass
  `service_ks_register_roles` (default `[]`, `ansible/roles/service-ks-register/defaults/main.yml:29`), so it does not
  create the `service` role itself; which component creates it before the grant is NOT AVAILABLE from these roles.
  Services and endpoints are registered on deploy/reconfigure, not on upgrade. Nova now looks the volume API up as
  `catalog_info = block-storage::internalURL` (`ansible/roles/nova-cell/templates/nova.conf.j2:112`). NOT AVAILABLE:
  what nova does between the upgrade and the next deploy/reconfigure, when no `block-storage` service is registered
  yet.

### 3.7 Dependencies (`templates/cinder.conf.j2`)

- **Per-service file, new in 2025.1:** `cluster = <cinder_cluster_name>` only for cinder-volume and only when the name
  is set (`cinder.conf.j2:23-25`); `enabled_backends` and the backend sections only for cinder-volume (`:27-31`,
  `:150-170`); the backup driver settings only for cinder-backup (`:33-58`).
- **Glance**: `glance_api_servers` = `glance_internal_endpoint` (internal FQDN, port 9292) (`:18`).
  **`glance_num_retries = {{ groups['glance-api'] | length }}`** (`:20`) scales with the number of glance hosts. With
  the glance file backend only one glance-api exists, yet retries equal the group size.
- **Nova**: `[nova]` section authenticates with **`nova_keystone_user`/`nova_keystone_password`** (`:98-108`), so
  rotating the nova password needs a cinder reconfigure. In the other direction, nova-api and nova-compute use
  **`cinder_keystone_user/password`** (`ansible/roles/nova-cell/templates/nova.conf.j2:111-120`,
  `ansible/roles/nova/templates/nova.conf.j2:66-75`), so rotating the cinder password needs a reconfigure of all
  computes. Manila also uses the cinder creds (`ansible/roles/manila/templates/manila-share.conf.j2:29-30`).
- MariaDB (`cinder.conf.j2:110-114`); RabbitMQ RPC (`cinder.conf.j2:62`) and notify (`cinder.conf.j2:64-71`; topic `notifications` for ceilometer only,
  `defaults/main.yml:296-300`); `[oslo_messaging_rabbit]` with the queue settings always on (`cinder.conf.j2:73-89`,
  [F17](../findings.md#f17)); Keystone, with `www_authenticate_uri = keystone_public_url`, and memcached (`cinder.conf.j2:116-136`);
  Barbican (`cinder.conf.j2:262-267`); osprofiler (`cinder.conf.j2:254-260`).
- **Ceph**: one section per entry of `cinder_ceph_backends` (default `[rbd-1]`) with `volume_backend_name`,
  `rbd_pool` and `rbd_user` from the entry, `rbd_ceph_conf = /etc/ceph/<cluster>.conf`, `rbd_cluster_name`,
  `rbd_keyring_conf = /etc/ceph/<cluster>.client.<user>.keyring`, an optional `backend_availability_zone`, and
  `rbd_secret_uuid = cinder_rbd_secret_uuid` (`cinder.conf.j2:150-170`). The same UUID is installed into libvirt on computes by
  `ansible/roles/nova-cell/tasks/external_ceph.yml:162,188`, so the two must stay in sync.
- **Backup drivers**: ceph (`backup_ceph_conf = /etc/ceph/<cluster of cinder_backup_ceph_backend>.conf`, with the
  backup user and pool), nfs and s3 (`cinder.conf.j2:33-58`). **Removed in 2025.1:** the swift backup driver; with
  `cinder_backup_driver: swift` no `backup_driver` line is written ([Swift](../../components/swift.md)).
- **Coordination**: valkey (new in 2025.1, and first in the default), redis or etcd (`cinder.conf.j2:269-281`). The etcd URL is
  `etcd3+<internal_protocol>://{{ kolla_internal_fqdn }}:{{ etcd_client_port }}?api_version=v3` (`cinder.conf.j2:280`), and the etcd
  role defines an internal HAProxy entry on `etcd_client_port` (`ansible/roles/etcd/defaults/main.yml:11-17`), so
  cinder reaches etcd through the internal VIP. Default `cinder_coordination_backend` is `''` unless valkey, redis or
  etcd is enabled (`all.yml:1178`; `enable_etcd: "no"`, `enable_redis: "no"`, `enable_valkey: "no"`,
  `all.yml:878,959,965`).
- **LVM/iSCSI**: `target_helper`, `target_protocol = iscsi` (`cinder.conf.j2:141-148`).

### 3.8 Operational notes

1. **No `host`/`backend_host` set in cinder.conf** (`grep backend_host ansible/roles/cinder` returns nothing).
   **Changed in 2025.1:** `cluster` is set for cinder-volume when `cinder_cluster_name` is set, and the precheck asks
   for it as soon as `cinder-volume` has more than one host ([§3.3](#33-task-flow)). Because of `network_mode: host`,
   each cinder-volume container has the node hostname ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). Whether
   cinder then registers it as `<node-hostname>@<backend>` is upstream cinder behaviour and NOT AVAILABLE here.
   - NOT AVAILABLE (upstream cinder): what setting `cluster` on a running cloud does to the existing volumes and
     services, and whether, without it, every volume on a shared backend is owned by the host that created it.
   - The same question applies to renaming or replacing a storage node. The `hostnqn` is also derived from the host
     name (`tasks/config.yml:108`), so a renamed node gets a new NQN. The docs also note LVM issues in a
     multi-controller setup (`doc/source/reference/storage/cinder-guide.rst:70-73`).
2. **cinder-volume restart impact** (upstream cinder and os-brick behaviour, NOT AVAILABLE beyond the code facts):
   - Code facts: with LVM, the LIO config is kept in the `target_config` volume (`defaults/main.yml:202`) or the targets
     are served by the separate `tgtd` container ([§3.2](#32-cinder_services-ansiblerolescinderdefaultsmainyml2-60));
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
4. **Upgrade restarts every cinder-volume and cinder-backup at once, twice** (flush at `upgrade.yml:13-14`, then
   `reload.yml` at `upgrade.yml:16`; always serial 0 in 2025.1, [F19](../findings.md#f19)). There is no
   `[upgrade_levels]` pinning in the template. The code comment explains the second restart: after an upgrade, services
   keep an RPC version cap until all of them are restarted, and the role waits 30 s for the services to update their
   version in the database (`handlers/main.yml:63-81`). The `reload.yml` restart is a plain `restart_container`,
   without any condition, on every enabled cinder service mapped to the host (`tasks/reload.yml:2-10`). NOT AVAILABLE:
   whether 30 s is enough on a given cloud, and whether in-flight operations survive two restarts in a row.
5. **Oddity: backup driver vs. ceph files**, still holds in 2025.1. `cinder_backup_driver: "ceph"` is the default even
   when `cinder_backend_ceph` is `no`. cinder.conf then sets `backup_driver = ...CephBackupDriver`,
   `backup_ceph_conf=/etc/ceph/<cluster>.conf` (`cinder.conf.j2:34-41`; the backup backend entry exists even when the
   backend is disabled, `defaults/main.yml:278-287`). But `cinder-backup.json.j2` only copies the `ceph` directory
   `{% if cinder_backend_ceph %}` (`templates/cinder-backup.json.j2:15-21`), and `external_ceph.yml` only runs for
   `cinder_backend_ceph` (`config.yml:18-22`). With an LVM or NFS-only deployment and default backup settings,
   kolla-ansible therefore gives cinder-backup no ceph config. Whether its driver then fails is NOT AVAILABLE.
6. **Multipath** is never configured on the cinder side: no `use_multipath_for_image_xfer` / `volume_use_multipath` in
   the cinder templates (`grep multipath ansible/roles/cinder` returns nothing). On the nova side,
   `volume_use_multipath = true` is set in nova-compute's libvirt config when `enable_multipathd` is on
   (`ansible/roles/nova-cell/templates/nova.conf.d/libvirt.conf.j2:27-28`). The `multipathd` container is off by
   default (`all.yml:927`).
7. **Compute-host touchpoints:** the cinder role itself does not target computes. However, `iscsid` on computes (iscsi
   role) shares `iscsi_info`, nova-compute uses the cinder creds, and the RBD secret is shared with nova-libvirt.
   Enabling `enable_cinder_backend_iscsi`/LVM also flips glance-api to privileged with `/dev`, so **glance-api is
   recreated** (`ansible/roles/glance/defaults/main.yml:10,206-207`). `cinder_backend_ceph` (with Cinder enabled) also
   makes glance-api privileged, without `/dev` (`ansible/roles/glance/defaults/main.yml:10`).
8. External Ceph needs cinder-volume and cinder-backup hosts in the `storage` group, otherwise "Cinder and related
   services relying on this group [will] fail" (`doc/source/reference/storage/external-ceph-guide.rst:179-188`).
9. **Changed in 2025.1, container check:** the 2024.1 sheet noted that a sanity check, if enabled, would create a 1 GB
   volume on every deploy/reconfigure, and that no such check existed. The new `check.yml` only checks that the
   containers run and are healthy; it creates no volume ([§3.3](#33-task-flow)).

---

## 4. HORIZON

### 4.1 Play

```yaml
# ansible/site.yml:738-750
- name: Apply role horizon
  gather_facts: false
  hosts: [horizon, '&enable_horizon_True']
  serial: '{{ kolla_serial|default("0") }}'
  max_fail_percentage: '{{ horizon_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}'
  roles: [{ role: horizon, tags: horizon }]
```
- LB include: `site.yml:188-192`. `enable_horizon: "{{ enable_openstack_core | bool }}"` (`all.yml:887`).
- Horizon is the last of these plays.

### 4.2 `horizon_services` (`ansible/roles/horizon/defaults/main.yml:2-76`)

| key | container | group | enabled | flags |
|---|---|---|---|---|
| horizon | `horizon` | horizon | true | **`environment`: 17 `ENABLE_<PLUGIN>` flags plus `FORCE_GENERATE`** (`defaults/main.yml:8-26`). **Changed in 2025.1:** `ENABLE_VENUS` is new (`defaults/main.yml:23`). There is **no host `/tmp` bind** and, unlike glance, cinder and heat, no `/dev/shm`: the volumes are config, dev-mode sources, localtime, timezone and logs (`defaults/main.yml:126-131`). Settings use `LOCAL_PATH = '/tmp'` (`templates/_9998-kolla-settings.py.j2:43`), which is therefore the container's own `/tmp`. HAProxy uses `balance roundrobin` when `enable_memcached` or `horizon_backend_database`, `balance source` otherwise (`defaults/main.yml:40`, `:61`; `enable_memcached: "yes"`, `all.yml:842`, so `roundrobin` by default), and, new in 2025.1, `option httpchk` (`defaults/main.yml:41`, `:62`). Redirect frontends (`mode: redirect`, port 80) are added when internal or external TLS is on (`defaults/main.yml:43-50`, `:64-72`), and an `acme_client` backend is defined (`defaults/main.yml:73-76`); every frontend routes `/.well-known/acme-challenge/` to it (`defaults/main.yml:38`, `:50`, `:59`, `:72`). |

Because the plugin flags live in the container environment, and the container check compares `environment`
([§0](#0-cross-cutting-facts-apply-to-all-five-roles)), **enabling or disabling any service that has a horizon plugin**
(designate, octavia, magnum, …) changes the env. The horizon container is then **recreated** on the next
deploy/reconfigure even if no horizon config changed. On the first 2025.1 run the new `ENABLE_VENUS` flag alone changes
the environment of a container created by 2024.1.

### 4.3 Task flow

| action | flow |
|---|---|
| deploy / reconfigure | `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` **only if `horizon_backend_database`** → flush (`ansible/roles/horizon/tasks/deploy.yml:1-14`). There is **no keystone registration**. |
| upgrade | `config.yml` → `check-containers.yml` → (clone) → `bootstrap_service.yml` if DB backend → flush (`ansible/roles/horizon/tasks/upgrade.yml:1-14`) |
| precheck | groups; `horizon_listen_port` free (80, or 443 when `horizon_enable_tls_backend`; `all.yml:485`) (`ansible/roles/horizon/tasks/precheck.yml:17-28`) |
| check | **new in 2025.1:** `service-check` (`ansible/roles/horizon/tasks/check.yml:2-4`) |
| pull / stop / deploy-containers / config | standard |

### 4.4 Config files (`ansible/roles/horizon/tasks/config.yml`)

**Changed in 2025.1:** no task notifies; the container check restarts `horizon` when a file or its definition changed
([§0](#0-cross-cutting-facts-apply-to-all-five-roles)).

| dest | source |
|---|---|
| per-service policy files (`<svc>_policy.json/yaml`) | for each enabled service in the list (`config.yml:16-38`), `policy_item.yml` looks for `{{node_custom_config}}/horizon/<svc>_<policy file>` (`ansible/roles/horizon/tasks/policy_item.yml:3-25`) and copies the matches (`config.yml:92-101`) |
| `horizon/config.json` | `horizon.json.j2` (`config.yml:40-48`) |
| `horizon/horizon.conf` (Apache) | first_found: `horizon/<host>/horizon.conf` → `horizon/horizon.conf` → template (`config.yml:50-62`). This is a **whole-file override**, not a merge. |
| `horizon/_9998-kolla-settings.py` | first_found: `horizon/<host>/_9998-kolla-settings.py` → `horizon/_9998-kolla-settings.py` → `_9998-kolla-settings.py.j2` (`config.yml:64-76`). Whole-file override. |
| `horizon/_9999-custom-settings.py` | first_found, same pattern; the default template is empty (`config.yml:78-90`; `templates/_9999-custom-settings.py.j2` has 0 lines). |
| custom themes | `{{node_custom_config}}/horizon/themes/<name>` for each `horizon_custom_themes` entry (default `[]`, `defaults/main.yml:81`) (`config.yml:103-114`) |
| certs | service-cert-copy (`config.yml:116-118`) |

**Settings layout, as in 2024.1:** `horizon.json.j2` copies both files into
`/etc/openstack-dashboard/local_settings.d/` (`templates/horizon.json.j2:21-32`). The base `local_settings.py` is the
one the image ships: the kolla image copies Horizon's `local_settings.py.example` to
`/etc/openstack-dashboard/local_settings.py` and links the dashboard's `local_settings.d` to
`/etc/openstack-dashboard/local_settings.d` (kolla `docker/horizon/Dockerfile.j2:59-66`). Consequences read from the
code:

- An operator override kept under the 2023.1 names (`/etc/kolla/config/horizon/local_settings` or
  `custom_local_settings`) is still not looked up (`config.yml:64-90`).
- `_9998-kolla-settings.py` is a fragment, not a full settings file: it assigns into `CACHES['default']`
  (`templates/_9998-kolla-settings.py.j2:21-22`), so it relies on the base settings defining `CACHES`. How Horizon loads
  `local_settings.d` (order, error handling) is upstream Horizon behaviour and NOT AVAILABLE.
- **Removed in 2025.1:** the Swift settings (`SWIFT_FILE_TRANSFER_CHUNK_SIZE` and the `swiftclient` logger) are no
  longer written ([Swift](../../components/swift.md)).

### 4.5 Handlers

`Restart horizon container` (`ansible/roles/horizon/handlers/main.yml:2-15`): recreate_or_restart. It passes
`environment`; there is no other logic, and no `kolla_action` guard.

### 4.6 Bootstrap

- `horizon_backend_database: false` (`all.yml:1267`). Only when an operator sets it does deploy/reconfigure create the
  DB and user and run `bootstrap_horizon` (`KOLLA_BOOTSTRAP`: Django `manage.py migrate --noinput`, then exits; kolla
  `docker/horizon/extend_start.sh:27-30`) (`ansible/roles/horizon/tasks/bootstrap.yml:2-38`,
  `ansible/roles/horizon/tasks/bootstrap_service.yml:2-20`). In that case **the bootstrap re-runs on every
  reconfigure**.
- There is no keystone registration at all.

### 4.7 Dependencies (`templates/_9998-kolla-settings.py.j2`)

- **Keystone**: `OPENSTACK_KEYSTONE_URL = "{{ horizon_keystone_url }}/v3"` (`_9998-kolla-settings.py.j2:58`), with
  `horizon_keystone_url` = `keystone_internal_url`, or `keystone_public_url` when `horizon_use_keystone_public_url`
  (default False) (`defaults/main.yml:139,162`). `OPENSTACK_HOST = kolla_internal_fqdn` (`_9998-kolla-settings.py.j2:56`).
  `OPENSTACK_ENDPOINT_TYPE = "internalURL"` (`_9998-kolla-settings.py.j2:131`), so Horizon talks to **every** service's internal endpoint from its
  own container.
- **memcached**: `SESSION_ENGINE = cache` with all memcached hosts, `ignore_exc: True`, **unless** the DB backend is
  used (`_9998-kolla-settings.py.j2:19-23`). With the DB backend: `SESSION_ENGINE = db` plus MariaDB (`_9998-kolla-settings.py.j2:7-18`). The cache branch is chosen when
  `groups['memcached']` is not empty, not from `enable_memcached` (`_9998-kolla-settings.py.j2:19`), while the HAProxy balance still follows
  `enable_memcached` ([§4.2](#42-horizon_services-ansibleroleshorizondefaultsmainyml2-76)).
- **Cinder**: `enable_backup` follows `enable_cinder_backup` (`_9998-kolla-settings.py.j2:99`).
- **Glance**: Glance allows `horizon_public_endpoint` as CORS origin; changed in 2025.1, that endpoint is built from
  `horizon_external_fqdn` (default `kolla_external_fqdn`) (`all.yml:479-481`;
  `ansible/roles/glance/templates/glance-api.conf.j2:147-148`).
- `SECRET_KEY = horizon_secret_key` (`_9998-kolla-settings.py.j2:44`), which is the same on all nodes.
- Multi-region `AVAILABLE_REGIONS` (`_9998-kolla-settings.py.j2:49-54`).
- TLS: `SECURE_PROXY_SSL_HEADER` and secure cookies when either internal or external TLS is on (`_9998-kolla-settings.py.j2:25-29`).
  `horizon.conf.j2` only handles `horizon_enable_tls_backend` (`templates/horizon.conf.j2:3,43`), and the http→https
  redirects are HAProxy entries ([§4.2](#42-horizon_services-ansibleroleshorizondefaultsmainyml2-76)).

### 4.8 Operational notes

- Sessions live in memcached unless the DB backend is used (`_9998-kolla-settings.py.j2:7-23`), HAProxy uses
  `balance roundrobin` by default and `balance source` only when memcached is disabled and the DB backend is not used
  ([§4.2](#42-horizon_services-ansibleroleshorizondefaultsmainyml2-76)), and `LOCAL_PATH=/tmp` is the **container's**
  `/tmp`, so it does not survive a recreate. NOT AVAILABLE: whether a horizon restart or a **memcached restart** logs
  users out, what restarting a node does to in-flight requests (including image uploads,
  `HORIZON_IMAGES_UPLOAD_MODE = 'direct'` at `_9998-kolla-settings.py.j2:130`), and whether anything is staged in
  `LOCAL_PATH`.
- Image side (kolla `docker/horizon/extend_start.sh`): every start syncs each `ENABLE_<PLUGIN>` dashboard file into
  `openstack_dashboard/local/enabled` (`extend_start.sh:32-46,224-240`). `manage.py collectstatic --noinput --clear` and
  `compress --force` run **only** when `/var/lib/kolla/.settings.md5sum.txt` is missing, the md5 of `local_settings` +
  `custom_local_settings` + `local_settings.d` + (new in 2025.1) `themes` differs from it, a plugin file was just
  copied in or removed, or `FORCE_GENERATE=yes` (`extend_start.sh:38-45,206-223,244-248`). **Changed in 2025.1:** `compress` is run
  once, under `set -o errexit` (`extend_start.sh:3`, `extend_start.sh:246`); the 2024.1 loop of five attempts is gone, so the first failure ends
  the start. kolla-ansible sets `FORCE_GENERATE=yes` only when `horizon_dev_mode` is on, and `no` otherwise
  (`defaults/main.yml:26,155`). The settings set `COMPRESS_OFFLINE = True` (`_9998-kolla-settings.py.j2:3`).
  `/var/lib/kolla` is not a volume (`defaults/main.yml:126-131`), so the hash file lives in the container layer. A
  recreate (new image, plugin flag change, `COPY_ONCE`) starts without it (`extend_start.sh:6,247`). `collectstatic`
  and `compress` therefore run on the first start after a recreate or after a settings change, and not on a plain
  restart with unchanged settings and plugin flags. NOT AVAILABLE: how long they take. See
  [Kolla images §5](../../concepts/kolla-images.md#5-per-image-start-behaviour).
- Horizon config is independent of host count except for the memcached list.

---

## 5. HEAT

### 5.1 Play

```yaml
# ansible/site.yml:722-736
- name: Apply role heat
  gather_facts: false
  hosts: [heat-api, heat-api-cfn, heat-engine, '&enable_heat_True']
  serial: '{{ kolla_serial|default("0") }}'
  max_fail_percentage: '{{ heat_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}'
  roles: [{ role: heat, tags: heat }]
```
- LB include: `site.yml:183-187`. `enable_heat: "{{ enable_openstack_core | bool }}"` (`all.yml:886`).

### 5.2 `heat_services` (`ansible/roles/heat/defaults/main.yml:2-66`)

| key | container | group | enabled | flags |
|---|---|---|---|---|
| heat-api | `heat_api` | heat-api | true | Apache/mod_wsgi on 8004, HAProxy internal and external, each with `option httpchk` (new in 2025.1) (`defaults/main.yml:3-30`) |
| heat-api-cfn | `heat_api_cfn` | heat-api-cfn | true | Apache/mod_wsgi on 8000, HAProxy internal and external, each with `option httpchk` (`defaults/main.yml:31-58`) |
| heat-engine | `heat_engine` | heat-engine | true | No haproxy, not privileged. Volumes are config, localtime, timezone, dev-mode source and logs, plus **`/dev/shm` always** (changed in 2025.1) (`defaults/main.yml:170-176`). |

All three containers mount `/dev/shm` (`defaults/main.yml:162,169,176`), so the first 2025.1 run recreates them.

### 5.3 Task flow

| action | flow |
|---|---|
| deploy / reconfigure | `register.yml` → `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` → flush (`ansible/roles/heat/tasks/deploy.yml:1-15`) |
| upgrade | `config.yml` → `check-containers.yml` → `bootstrap_service.yml` (db sync with new image while the old engine and APIs still run) → flush, which restarts **all** heat-api, heat-api-cfn and heat-engine containers together (`ansible/roles/heat/tasks/upgrade.yml:1-9`). No `register.yml`. |
| precheck | ports 8004/8000 free on api/cfn hosts (`ansible/roles/heat/tasks/precheck.yml:18-38`). heat-engine is not checked. |
| check | **new in 2025.1:** `service-check` (`ansible/roles/heat/tasks/check.yml:2-4`) |
| pull / stop / deploy-containers / config | standard |

### 5.4 Config files (`ansible/roles/heat/tasks/config.yml`)

**Changed in 2025.1:** no task notifies; the container check restarts each heat container whose files or definition
changed ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). Since each container has its own `heat.conf`, a
change of it still reaches all three.

| dest | sources |
|---|---|
| `<svc>/config.json` | `<svc>.json.j2` (`config.yml:35-41`) |
| `<svc>/heat.conf` (`service_name` per container) | merge: template → `global.conf` → `heat.conf` → `heat/<svc>.conf` → `heat/<host>/heat.conf` (`config.yml:43-56`) |
| policy | `{{node_custom_config}}/heat/` (`config.yml:12-29`, `:58-66`) |
| `heat-api/wsgi-heat-api.conf`, `heat-api-cfn/wsgi-heat-api-cfn.conf` | `src: "{{ role_path }}/templates/..."` (`config.yml:68-86`). **No override path exists**, unlike cinder/placement wsgi. |
| certs | service-cert-copy (`config.yml:31-33`) |

The wsgi template sets no `python-path`; both `WSGIScriptAlias` and the `<Directory>` block use
`binary_path = /var/lib/kolla/venv/bin` (`ansible/roles/heat/templates/wsgi-heat-api.conf.j2:2,18,34`), as placement
does with its `wsgi_directory` (`ansible/roles/placement/templates/placement-api-wsgi.conf.j2:2`). Still holds in
2025.1; Heat has no uWSGI option.

### 5.5 Handlers

Three handlers: heat-api (`ansible/roles/heat/handlers/main.yml:2-14`), heat-api-cfn (`:16-28`), heat-engine
(`:30-42`). All recreate_or_restart, with no special logic and, changed in 2025.1, no `kolla_action` guard.

### 5.6 Bootstrap

- `mysql_db heat` and `mysql_user` (`ansible/roles/heat/tasks/bootstrap.yml:2-36`) run every deploy/reconfigure.
- `bootstrap_heat` container (`ansible/roles/heat/tasks/bootstrap_service.yml:2-30`) gets `KOLLA_BOOTSTRAP` plus the
  **cloud admin credentials as env vars** (`OS_AUTH_URL`, `OS_USERNAME`, `OS_PASSWORD`, `OS_PROJECT_NAME`, …) and
  `HEAT_DOMAIN_ADMIN_PASSWORD` (`bootstrap_service.yml:10-22`). The image runs `heat-manage db_sync`, then
  `openstack domain list`. Only if `heat_user_domain` is absent does it create the domain, the `heat_domain_admin` user
  (password `HEAT_DOMAIN_ADMIN_PASSWORD`) and that user's `admin` role on the domain (kolla
  `docker/heat/heat-api/extend_start.sh:5-17`). **It re-runs on every reconfigure** (and on upgrade,
  `ansible/roles/heat/tasks/upgrade.yml:6`), but once the domain exists it never touches the user. A changed
  `heat_domain_admin_password` (`etc/kolla/passwords.yml:104`) is therefore **not** pushed to Keystone, while
  `heat.conf` gets the new value (`ansible/roles/heat/templates/heat.conf.j2:11-12`). NOT AVAILABLE: whether
  stack-domain operations then fail authentication. The check looks only at the domain name, so if a run fails partway
  and leaves the domain without the user or its role, no later run repairs it. With Docker, the container is removed on
  exit, after a failure too (`ansible/module_utils/kolla_docker_worker.py:416-424`), so the passwords do not linger in
  `docker inspect`. But `kolla_start` runs with xtrace: when the bootstrap creates the domain, the
  `openstack user create … --password` line goes to stderr with `HEAT_DOMAIN_ADMIN_PASSWORD` expanded. The module
  returns that stderr in the task result (`ansible/module_utils/kolla_docker_worker.py:411-415`), which Ansible prints
  on failure or with `-v` (ansible-core 2.18.20 `lib/ansible/plugins/callback/default.py:49-70,103-104`,
  `lib/ansible/plugins/callback/__init__.py:210-212`), and the task sets no `no_log` (kolla `docker/base/start.sh:6`,
  `docker/heat/heat-api/extend_start.sh:12`;
  [Kolla images §2.2](../../concepts/kolla-images.md#22-kolla_start-step-by-step)).
- Keystone: services `heat/orchestration` (`/v1/%(tenant_id)s`) and `heat-cfn/cloudformation` (`/v1`), each with 2
  endpoints (internal, public); user `heat`; roles `heat_stack_owner` and `heat_stack_user`; **`heat_stack_owner`
  granted to the cloud admin user in the admin project** (`defaults/main.yml:186-190,224-251`;
  `ansible/roles/heat/tasks/register.yml:2-9`). **Changed in 2025.1:** the endpoint URLs are composed from
  `heat_internal_base_endpoint`, `heat_public_base_endpoint` and the CFN base endpoints, now defined in `all.yml`
  (`all.yml:465-466,472-473`); with the defaults the URL text is unchanged. This runs on deploy/reconfigure, not on
  upgrade.

### 5.7 Dependencies (`templates/heat.conf.j2`)

- **Public endpoints reached from inside VMs:** `heat_metadata_server_url` and `heat_waitcondition_server_url` use
  `heat_cfn_public_base_endpoint` (`heat.conf.j2:6-7`), i.e. **`public_protocol`, `heat_cfn_external_fqdn` and
  `heat_api_cfn_public_port`** (`all.yml:473`; the port follows the single external frontend option, `all.yml:476`).
  `server_keystone_endpoint_type = public` (`heat.conf.j2:23`). Instances that use wait conditions or software deployments must be
  able to reach the **external** VIP on that port and the public keystone endpoint.
- **All other services:** `[clients] endpoint_type = internalURL` (`heat.conf.j2:96-97`). heat-engine calls nova, neutron, cinder,
  glance and the other services through their internal catalog endpoints. The real dependency set is whatever the
  users' templates use.
- Keystone: `keystone_authtoken` (`heat.conf.j2:31-47`), with `www_authenticate_uri = keystone_public_url` (changed in 2025.1,
  `heat.conf.j2:33`), plus `[trustee]` with the heat service user (`heat.conf.j2:55-60`), plus `[ec2authtoken]` (`heat.conf.j2:62-63`).
  `stack_domain_admin` = `heat_domain_admin` / `heat_domain_admin_password` (`heat.conf.j2:11-12`).
- MariaDB (`heat.conf.j2:25-29`); RabbitMQ RPC (`heat.conf.j2:19`), notifications (ceilometer only, otherwise `driver = noop`; `heat.conf.j2:65-72`,
  `defaults/main.yml:215-219`) and `[oslo_messaging_rabbit]` with the queue settings always on (`heat.conf.j2:74-90`,
  [F17](../findings.md#f17)); memcached for authtoken and `[cache]` (`heat.conf.j2:44-53`); `[oslo_concurrency] lock_path`, now
  always written (`heat.conf.j2:114-115`).
- **Cinder backup, new in 2025.1:** `[volumes] backups_enabled = {{ enable_cinder_backup }}` (`heat.conf.j2:111-112`), so enabling
  or disabling cinder-backup changes `heat.conf` and restarts the heat containers.
- `num_engine_workers = heat_engine_workers` = `openstack_service_workers` (≤5) per engine host (`heat.conf.j2:16`;
  `defaults/main.yml:202`).

### 5.8 Operational notes

- **heat-engine restarts with stacks in progress:** Docker sends SIGTERM, then SIGKILL if heat-engine is still running
  after 60 s (`ansible/module_utils/kolla_systemd_worker.py:33`; `ansible/group_vars/all.yml:148,160`;
  [§0](#0-cross-cutting-facts-apply-to-all-five-roles)). NOT AVAILABLE (upstream heat): how that compares with the
  duration of long resource creates; whether stacks that a killed engine owned stay `*_IN_PROGRESS` until some engine
  starts again; whether heat-engine's `reset_stack_status` then marks them `FAILED` ("Engine went down during stack …");
  and whether users must then run `stack update` or a check/resume.
- With serial 0, **every heat-engine restarts in the same handler flush** on any heat.conf change. A memcached or rabbit
  membership change, a password rotation, an `openstack_service_workers` change, a cinder-backup switch, or the first
  2025.1 run (queue settings, `www_authenticate_uri`, `/dev/shm`, `backups_enabled`) is enough. Every in-progress stack
  in the cloud is therefore affected, not just a fraction. In 2025.1, `reconfigure` cannot be batched; a batched run is
  `deploy -t heat -e kolla_serial=N` ([F19](../findings.md#f19)).
- On upgrade the db sync runs while old engines are still active, and all engines restart together after it.
- Heat does not touch compute hosts. Its dependency on instance reachability to the external VIP (above) is the main
  network coupling.

---

## 6. Summary matrix: what `reconfigure` does per role

| role | keystone register | DB create/grant | bootstrap container (schema sync) on reconfigure | extra side effects on reconfigure | restarts (serial 0) |
|---|---|---|---|---|---|
| glance | yes | yes | **yes** (`KOLLA_BOOTSTRAP` on `glance_api_hosts[0]`) | **toggles GLOBAL `log_bin_trust_function_creators` 1→0** (unless `use_preconfigured_databases`) | glance-api (and tls-proxy) on `glance_api_hosts` only (1 host with the file backend), when the container check reports a change |
| placement | yes | yes | **yes** (also runs online data migrations) | – | all placement-api, when changed (the first 2025.1 run switches them to uWSGI) |
| cinder | yes (from 2025.1 also the `block-storage` service) | yes | **yes** | – | api, scheduler, **volume, backup on all storage hosts** at once if their container or files changed (the first 2025.1 run changes all of them) |
| horizon | **no** | only if `horizon_backend_database` (default `false`) | only if `horizon_backend_database` | env-driven recreate when plugin flags change | all horizon, when changed |
| heat | yes (also roles and a grant to admin) | yes | **yes** (with admin creds in env) | – | api, api-cfn, **all engines**, when changed |

The separate online-data-migration container (`KOLLA_OSM`) runs **only on `upgrade`**, for placement
(`ansible/roles/placement/tasks/upgrade.yml:16-34`) and cinder (`ansible/roles/cinder/tasks/upgrade.yml:18-36`).
Glance's expand/migrate/contract runs only in the rolling path. A reconfigure with a bumped image tag therefore runs
cinder's `db sync` without its OSM step (kolla `docker/cinder/cinder-api/extend_start.sh:6-14`), while placement's
bootstrap container runs both `db sync` and `db online_data_migrations` (kolla
`docker/placement/placement-api/extend_start.sh:5-9`). A reconfigure also skips cinder's second "remove RPC version pin"
restart, which only `ansible/roles/cinder/tasks/upgrade.yml:16` runs. In the other direction, a reconfigure registers
the cinder `block-storage` service, which the upgrade skips. Whether a reconfigure with a new tag leaves cinder in a
partially upgraded state is NOT AVAILABLE. See [Kolla images §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run).

## 7. Things that scale with host count

- memcached and rabbit host lists in every config ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). Any membership
  change rewrites the config of all 5 services and restarts every container of every service.
- `glance_num_retries = len(groups['glance-api'])` (`ansible/roles/cinder/templates/cinder.conf.j2:20`).
- HAProxy backend lists: glance uses `glance_api_hosts` (`ansible/roles/glance/defaults/main.yml:90-91`); the others
  use `groups[host_group]`.
- Placement and cinder credentials are embedded in nova-compute config on **every compute**. Password rotation therefore
  needs a reconfigure of the whole compute fleet ([§2.8](#28-operational-notes-and-the-relation-to-nova),
  [§3.7](#37-dependencies-templatescinderconfj2)).
- `run_once` tasks repeat per batch when `kolla_serial` is set, which in 2025.1 only `deploy -e kolla_serial=N` does
  ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)).
- **New in 2025.1:** the number of `cinder-volume` hosts decides which cluster precheck applies
  ([§3.3](#33-task-flow)).

## 8. NOT AVAILABLE list

All the points below are to be confirmed by the community.

1. NOT AVAILABLE: whether an existing glance file-store image stays readable after `glance_backend_ceph: yes` or
   `glance_backend_s3: yes` is applied by reconfigure, and what Glance does with images whose locations point at the
   removed `swift` store after the upgrade ([§1.8](#18-operational-notes)).
2. Answered from code, changed in 2025.1: the 2024.1 risk of a Glance rolling-upgrade contract at the end of batch 1 no
   longer arises from the CLI, since `upgrade` always runs with `kolla_serial=0` ([§1.8](#18-operational-notes) note 5;
   [F19](../findings.md#f19)).
3. NOT AVAILABLE: Glance-api start time with a large NFS `glance_file_datadir_volume` (recursive chown,
   `glance-api.json.j2:47-52`).
4. NOT AVAILABLE: which catalog entry the glance cinder store looks up now that `cinder_catalog_info` is no longer
   written and the template has no `[cinder]` store section ([§1.7](#17-dependencies-from-templatesglance-apiconfj2)).
5. NOT AVAILABLE: whether cinder-backup works with default `cinder_backup_driver=ceph` and `cinder_backend_ceph=no`
   (kolla-ansible gives it no ceph config, [§3.8](#38-operational-notes) oddity 5).
6. NOT AVAILABLE: what setting `cinder_cluster_name` on a running cloud does to the existing volumes and services, and,
   without it, whether volumes owned by one of several RBD cinder-volume nodes can still be managed while that node is
   down ([§3.8](#38-operational-notes) note 1).
7. Cinder RPC pinning after `kolla-ansible upgrade`: answered from code: the role does a second restart of every cinder
   service after the upgrade flush and a 30 s pause, to remove the RPC version pin
   (`ansible/roles/cinder/tasks/upgrade.yml:13-16`, `ansible/roles/cinder/tasks/reload.yml:2-10`,
   `ansible/roles/cinder/handlers/main.yml:63-81`; [§3.8](#38-operational-notes) note 4). Remaining NOT AVAILABLE:
   whether 30 s is always enough for all services to report their new version.
8. NOT AVAILABLE: Heat-engine restart with `CREATE_IN_PROGRESS` stacks: final state and recovery steps.
9. NOT AVAILABLE: Horizon restart: session survival (memcached) and start-up duration. When collectstatic/compress run
   is answered from kolla source ([§4.8](#48-operational-notes)); a single failed `compress` now ends the start.
10. Answered from kolla source: `bootstrap_heat` does **not** update the `heat_domain_admin` password once
    `heat_user_domain` exists (kolla `docker/heat/heat-api/extend_start.sh:10-14`; [§5.6](#56-bootstrap)). Remaining NOT
    AVAILABLE: how heat behaves after `heat_domain_admin_password` changes, when `heat.conf` gets the new value
    (`ansible/roles/heat/templates/heat.conf.j2:12`) but Keystone keeps the old one.
11. NOT AVAILABLE: whether the kolla-toolbox `mysql_user` task (from the `community.mysql` collection, whose source is
    not among the studied trees) resets the DB user's password on every deploy/reconfigure ([§1.6](#16-bootstrap)).
12. NOT AVAILABLE: how Horizon loads the `_9998`/`_9999` fragments of `local_settings.d` on top of the image's base
    `local_settings.py` ([§4.4](#44-config-files-ansibleroleshorizontasksconfigyml)), and which component creates the
    Keystone `service` role that the cinder role only grants ([§3.6](#36-bootstrap)).
13. New in 2025.1, NOT AVAILABLE: what nova does between the upgrade and the next deploy/reconfigure, when it looks up
    `block-storage` and that service is not registered yet ([§3.6](#36-bootstrap)), and how uWSGI ends in-flight
    Placement and Cinder API requests on stop ([§2.8](#28-operational-notes-and-the-relation-to-nova)).

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
